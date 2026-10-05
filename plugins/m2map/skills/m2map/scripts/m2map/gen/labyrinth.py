"""Labyrinths assembled from a dungeon kit.

The corpus labyrinth dungeons are DungeonBlock pieces on a black plane
(`reference/archetypes/12-dungeon_block.md`). `mine/dungeon_kits.py` turned each
family into a kit -- every piece's floor, its measured walk, its sockets, what
rides on it -- in `reference/labyrinth/kits.json`. This module builds a new
labyrinth out of one:

1. **A maze on a cell grid.** A perfect maze (randomised depth-first), then a
   share of the remaining walls reopened (`loops`), never past the highest
   junction the kit has (the maze kits have no cross piece).
2. **Nodes.** Every cell that is not a straight run-through gets a piece whose
   sockets, turned by a multiple of 90 degrees, face exactly its open sides:
   cap, corner, tee or cross, picked by corpus frequency. Its centre is where
   its socket axes cross.
3. **Runs.** Between two nodes the gap is filled EXACTLY with the kit's
   two-socket pieces, solved over position and socket width -- so a whitedragon
   room (10 m mouths) is reached through a door piece (10 m to 33 m), and an
   anglar cave corridor (31 m) meets a stone one (41 m) only through
   `anglar_cavegate2`. A run may overrun its gap by `OVERLAP_CM` (the pieces
   interpenetrate at the wall) and fall short by `SHORT_CM`, never more.
4. **Seams and dressing.** Seam covers (`skipia_passis4/5`, 1 m long) go on
   joints at the corpus rate; every piece carries the records that rode on it
   in a third or more of its corpus placements, at the same local offset.
5. **Native walls.** `spider` builds every arm of the room grid, as its source
   maps do, and closes the walls of the maze with the mined barricade: attr
   blocked from the arm tip inward and the cobweb row copied verbatim.
6. **Start and boss.** The entrance is the middle of one side, the boss at the
   border cell farthest along the maze from it. A room with a socket hangs off
   the outside of the grid; a room with none (an island, as the maze, monkey,
   whitedragon_02 and spider bosses are in the corpus) stands clear of it and is
   reached through a warp gate at a capped dead end.

Frames: engine coordinates, x east, y NORTH; a record's stored y is the engine
y (rule 3: stored_y = -terrain_y). Roll counter-clockwise, north up (rule 25).
"""

from __future__ import annotations

import json
import math
import pathlib
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..codec import areadata as ad
from ..mine.dungeon_kits import RES, SIDE_DEG, unpack
from .spec import SECTOR_TILES, SECTOR_UNITS, MapSpec, SpecError, stream_seed

KITS_JSON = pathlib.Path(__file__).resolve().parents[3] / "reference" / "labyrinth" / "kits.json"

#: What the miner cannot see: how a family makes its walls. `grid`: every arm
#: of a room grid built, the maze shut with barricades (spider). `warp`: the
#: maze cut into islands that close, joined by warp gates at capped dead ends
#: -- the maze and monkey dungeons are letter-shaped islands and 23-26 warp
#: gates, and their one corridor length (63.5 m) cannot close a grid whose
#: junction reaches differ by 7 m from row to row. `path`: corridors where the
#: maze runs, nothing else.
NATIVE = {"spider": {"mode": "grid"}}
NATIVE.update({k: {"mode": "warp"} for k in
               ("maze", "maze02", "maze03", "monkey", "monkey02", "monkey03")})
ISLAND_CELLS = 5       # warp mode: cells per island at most
WARP_BIAS = 55.0       # warpgate01 in the maze/monkey maps: +55 cm on 23 of 26

SEAM_CM = 500.0        # a two-socket piece shorter than this is a seam cover:
                       # `skipia_passis4/5` 4.6 m, against `passIs3` 6.2 m, the
                       # shortest real filler
ROOM_M2 = 2500         # a one-socket piece with more walk than this is a room
JOG_CM = 300.0         # a straight's two mouths may sit this far off one axis
ISLAND_M2 = 500        # an island with less walk was never a playable room
QUANT = 10.0           # cm, the run solver's position step
WARP_FALLBACK = 929619867   # effect/background/warpgate01.mse

SIDES = ("E", "N", "W", "S")                       # counter-clockwise
VEC = {"E": (1, 0), "N": (0, 1), "W": (-1, 0), "S": (0, -1)}
OPP = {"E": "W", "W": "E", "N": "S", "S": "N"}
STEP = {"E": (1, 0), "W": (-1, 0), "N": (0, -1), "S": (0, 1)}   # (col, row)


def turn(side: str, roll: int) -> str:
    return SIDES[(SIDES.index(side) + roll // 90) % 4]


def _rot(x, y, roll):
    t = math.radians(roll)
    c, s = math.cos(t), math.sin(t)
    return c * x - s * y, s * x + c * y


# --------------------------------------------------------------------------
# kit
# --------------------------------------------------------------------------

@dataclass
class Piece:
    crc: int
    name: str
    count: int
    bias: int
    bbox: Tuple[float, float, float, float]
    grid: dict
    walk: np.ndarray
    sockets: List[dict]
    dressing: List[dict]
    walk_m2: int
    kind: str = ""
    #: node centre in the piece frame: where its socket axes cross
    centre: Tuple[float, float] = (0.0, 0.0)

    @property
    def sides(self) -> List[str]:
        return [s["side"] for s in self.sockets]

    def socket(self, side: str) -> dict:
        return next(s for s in self.sockets if s["side"] == side)

    def reach(self, side: str) -> float:
        s = self.socket(side)
        dx, dy = s["x"] - self.centre[0], s["y"] - self.centre[1]
        return abs(dx) if side in ("E", "W") else abs(dy)

    def rolls_for(self, want: set) -> List[int]:
        if len(self.sockets) != len(want):
            return []
        return [r for r in (0, 90, 180, 270) if {turn(s, r) for s in self.sides} == want]


def _classify(p: Piece) -> None:
    n = len(p.sockets)
    if n == 0:
        p.kind = "island"
    elif n == 1:
        p.kind = "room" if p.walk_m2 > ROOM_M2 else "cap"
    elif n == 2 and OPP[p.sides[0]] == p.sides[1]:
        a, b = p.sockets
        length = abs(a["x"] - b["x"]) if a["side"] in ("E", "W") else abs(a["y"] - b["y"])
        jog = abs(a["y"] - b["y"]) if a["side"] in ("E", "W") else abs(a["x"] - b["x"])
        if jog > JOG_CM:
            # mouths on two different axes: a room the corridor passes
            # through off-line (`Mt_Thunder_centerroom`, 36 m), not a filler
            p.kind = "hub"
        else:
            p.kind = "seam" if length < SEAM_CM else "straight"
    elif n == 2:
        p.kind = "corner"
    elif n == 3 and len(set(p.sides)) == 3:
        p.kind = "tee"
    elif n == 4 and len(set(p.sides)) == 4:
        p.kind = "cross"
    else:
        p.kind = "hub"          # several mouths on one side: not a maze node
    xs = [s["x"] for s in p.sockets if s["side"] in ("N", "S")]
    ys = [s["y"] for s in p.sockets if s["side"] in ("E", "W")]
    x0, y0, x1, y1 = p.bbox
    cx = float(np.mean(xs)) if xs else (x0 + x1) / 2.0
    cy = float(np.mean(ys)) if ys else (y0 + y1) / 2.0
    if p.kind == "cap":
        # a cap's centre is its far end, so a dead-end cell holds the whole cap
        s = p.sockets[0]
        if s["side"] == "E":
            cx = x0
        elif s["side"] == "W":
            cx = x1
        elif s["side"] == "N":
            cy = y0
        else:
            cy = y1
    if p.kind == "room":
        cx, cy = p.sockets[0]["x"], p.sockets[0]["y"]   # hung by its mouth
    p.centre = (cx, cy)


@dataclass
class Kit:
    name: str
    pieces: Dict[int, Piece]
    barricade: Optional[dict]
    riders: Dict[str, dict]
    mode: str = "path"
    layouts: Dict[str, list] = field(default_factory=dict)
    #: the run solver's window, from the corpus joins (`kits.json` `joins`)
    short_cm: float = 150.0
    overlap_cm: float = 250.0

    def of(self, kind: str) -> List[Piece]:
        return [p for p in self.pieces.values() if p.kind == kind]

    @property
    def warp_crc(self) -> int:
        best = [(v["count"], int(c)) for c, v in self.riders.items()
                if v.get("name") and "warpgate" in v["name"].lower()]
        return max(best)[1] if best else WARP_FALLBACK

    @property
    def warp_crcs(self) -> set:
        return {int(c) for c, v in self.riders.items()
                if v.get("name") and "warpgate" in v["name"].lower()}

    @property
    def max_degree(self) -> int:
        return 4 if self.of("cross") else 3 if self.of("tee") else 2


def load_kit(name: str, path=KITS_JSON) -> Kit:
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    kits = data["kits"]
    if name not in kits:
        raise SpecError("unknown labyrinth kit %r; have %s" % (name, ", ".join(sorted(kits))))
    k = kits[name]
    pieces = {}
    for crc, pc in k["pieces"].items():
        g = pc["grid"]
        p = Piece(crc=int(crc), name=pc["name"], count=pc["count"], bias=pc["bias"],
                  bbox=tuple(pc["bbox"]), grid=g,
                  walk=unpack(pc["walk"], (g["ny"], g["nx"])),
                  sockets=pc["sockets"], dressing=pc["dressing"], walk_m2=pc["walk_m2"])
        _classify(p)
        pieces[p.crc] = p
    _families(pieces)
    joins = k.get("joins") or {"p5": 0, "p95": 0}
    return Kit(name=name, pieces=pieces, barricade=k.get("barricade"),
               riders=k.get("riders", {}), mode=NATIVE.get(name, {}).get("mode", "path"),
               layouts=k.get("layouts", {}),
               short_cm=-min(joins["p5"], 0) + 150.0,
               overlap_cm=max(joins["p95"], 0) + 250.0)


def _families(pieces: Dict[int, Piece]) -> None:
    """Which sockets fit which: the corridor profiles of a kit.

    Two sockets are one family when their pieces were joined there in the
    corpus. Measured widths cannot say it -- a 7 m cap closes an 18 m maze
    corridor (`maze_dungeon_cave04`), and a whitedragon room's 10 m mouth takes
    only a door, never a 32 m corridor. Families are the connected components
    of the observed joins; a door or `anglar_cavegate2` has one socket in each
    of two families, and that is what makes it an adapter.
    """
    keys = [(p.crc, i) for p in pieces.values() for i in range(len(p.sockets))]
    parent = {k: k for k in keys}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k
    for p in pieces.values():
        for i, sk in enumerate(p.sockets):
            for partner in sk.get("partners", {}):
                q = pieces.get(int(partner))
                if q is None:
                    continue
                for j, tk in enumerate(q.sockets):
                    if str(p.crc) in tk.get("partners", {}):
                        parent[find((p.crc, i))] = find((q.crc, j))
    ids = {}
    for p in pieces.values():
        for i, sk in enumerate(p.sockets):
            sk["family"] = ids.setdefault(find((p.crc, i)), len(ids))


# --------------------------------------------------------------------------
# maze
# --------------------------------------------------------------------------

def maze(cols: int, rows: int, loops: float, max_degree: int, rng: random.Random):
    """Open edges as a set of frozenset({(c, r), (c2, r2)})."""
    seen = {(0, 0)}
    stack = [(0, 0)]
    edges = set()
    deg = {}

    def nbrs(c, r):
        for s, (dc, dr) in STEP.items():
            n = (c + dc, r + dr)
            if 0 <= n[0] < cols and 0 <= n[1] < rows:
                yield n
    while stack:
        cur = stack[-1]
        options = [n for n in nbrs(*cur) if n not in seen and deg.get(cur, 0) < max_degree]
        if not options:
            stack.pop()
            continue
        n = rng.choice(options)
        edges.add(frozenset((cur, n)))
        deg[cur] = deg.get(cur, 0) + 1
        deg[n] = deg.get(n, 0) + 1
        seen.add(n)
        stack.append(n)
    if len(seen) < cols * rows:
        # max_degree 2 on a grid can strand cells; join each to a neighbour
        for c in range(cols):
            for r in range(rows):
                if (c, r) not in seen:
                    n = next(iter(nbrs(c, r)))
                    edges.add(frozenset(((c, r), n)))
    walls = [frozenset(((c, r), n)) for c in range(cols) for r in range(rows)
             for n in nbrs(c, r) if (c, r) < n and frozenset(((c, r), n)) not in edges]
    rng.shuffle(walls)
    # dead ends first: a loop that removes a dead end reads as a loop, one
    # between two corridors reads as a hole in a wall
    walls.sort(key=lambda w: -sum(1 for x in w if deg.get(x, 0) == 1))
    want = int(round(loops * len(walls)))
    for w in walls[:want]:
        a, b = tuple(w)
        if deg.get(a, 0) < max_degree and deg.get(b, 0) < max_degree:
            edges.add(w)
            deg[a] = deg.get(a, 0) + 1
            deg[b] = deg.get(b, 0) + 1
    return edges


def sides_of(cell, edges, extra=()) -> set:
    out = set(extra)
    for s, (dc, dr) in STEP.items():
        if frozenset((cell, (cell[0] + dc, cell[1] + dr))) in edges:
            out.add(s)
    return out


def bfs(start, edges):
    dist = {start: 0}
    q = [start]
    adj = {}
    for e in edges:
        a, b = tuple(e)
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    for cur in q:
        for n in adj.get(cur, []):
            if n not in dist:
                dist[n] = dist[cur] + 1
                q.append(n)
    return dist


# --------------------------------------------------------------------------
# runs
# --------------------------------------------------------------------------

class RunSolver:
    """Fill a gap with two-socket pieces, exactly, matching socket widths.

    Breadth-first over the number of pieces, each frontier a boolean array over
    position (10 cm) per width class; the back-trace picks among the pieces
    that fit by corpus frequency, so a long run reads like the source maps
    rather than all 90 m pieces.
    """

    def __init__(self, kit: Kit):
        self.items = []
        for p in kit.of("straight"):
            a, b = p.sockets
            ax = "x" if a["side"] in ("E", "W") else "y"
            length = abs(a[ax] - b[ax])
            for s_in, s_out in ((a, b), (b, a)):
                self.items.append((p, s_in, s_out, length))
        self.nfam = 1 + max((s["family"] for p in kit.pieces.values() for s in p.sockets),
                            default=0)
        self.short, self.over = kit.short_cm, kit.overlap_cm
        self._len = {}

    @staticmethod
    def misfit(over: float) -> float:
        """Cost of a run ``over`` cm longer than its gap: an overlap hides in the
        wall, a shortfall is a hole in the floor, so it costs three times as much."""
        return over if over >= 0 else -3.0 * over

    def lengths(self, f_in: int, f_out: int, upto: float) -> np.ndarray:
        """Bool over position (QUANT cm): a run from ``f_in`` to ``f_out`` of
        that length exists. Position 0 is the empty run."""
        key = (f_in, f_out)
        hit = self._len.get(key)
        n = int(upto // QUANT) + 2
        if hit is not None and len(hit) >= n:
            return hit
        steps = [(int(round(it[3] / QUANT)), it[1]["family"], it[2]["family"]) for it in self.items]
        cur = np.zeros((self.nfam, n), bool)
        cur[f_in, 0] = True
        seen = np.zeros((self.nfam, n), bool)
        seen |= cur
        for _ in range(400):
            nxt = np.zeros_like(cur)
            for L, ci, co in steps:
                if 0 < L < n:
                    nxt[co, L:] |= cur[ci, :n - L]
            nxt &= ~seen
            if not nxt.any():
                break
            seen |= nxt
            cur = nxt
        out = seen[f_out].copy()
        if f_in != f_out:
            out[0] = False
        self._len[key] = out
        return out

    def solve(self, gap: float, f_in: int, f_out: int, rng: random.Random,
              max_pieces=200, slack: float = 0.0):
        """[(piece, s_in, s_out, length)] or None: a run from a socket of family
        ``f_in`` to one of ``f_out`` whose length lands in the corpus join band."""
        lo_ok, hi_ok = gap - self.short - slack, gap + self.over
        if lo_ok <= 0 <= hi_ok and f_in == f_out:
            return []
        if hi_ok < 0 or not self.items:
            return None
        n = int(hi_ok // QUANT) + 2
        W = self.nfam
        front = [np.zeros((W, n), bool)]
        front[0][f_in, 0] = True
        steps = [(it, int(round(it[3] / QUANT)), [it[1]["family"]], [it[2]["family"]])
                 for it in self.items]
        lo_i, hi_i = max(0, int(math.ceil(lo_ok / QUANT))), int(hi_ok // QUANT)
        end_cls = [f_out]
        best_k = None
        for k in range(1, max_pieces + 1):
            nxt = np.zeros((W, n), bool)
            prev = front[-1]
            for it, L, cin, cout in steps:
                if L >= n or L <= 0:
                    continue
                src = prev[cin].any(axis=0)
                if not src.any():
                    continue
                for co in cout:
                    nxt[co, L:] |= src[:n - L]
            front.append(nxt)
            if nxt[end_cls, lo_i:hi_i + 1].any():
                if best_k is None:
                    best_k = k
                # one more piece now and then, for variety
                if k >= best_k + (1 if rng.random() < 0.3 else 0):
                    break
            if not nxt.any():
                break
        if best_k is None:
            return None
        k = len(front) - 1
        if not front[k][end_cls, lo_i:hi_i + 1].any():
            k = best_k
        cands = [(i, wc) for wc in end_cls for i in range(lo_i, hi_i + 1) if front[k][wc, i]]
        if slack:
            pos, wc = cands[len(cands) // 2]          # a cap: anywhere it fits
        else:
            pos, wc = min(cands, key=lambda c: self.misfit(c[0] * QUANT - gap))
        out = []
        while k > 0:
            opts = []
            for it, L, cin, cout in steps:
                if wc in cout and pos - L >= 0:
                    ok = [ci for ci in cin if front[k - 1][ci, pos - L]]
                    if ok:
                        opts.append((it, L, ok))
            tot = sum(o[0][0].count for o in opts)
            pick = rng.random() * tot
            for it, L, ok in opts:
                pick -= it[0].count
                if pick <= 0:
                    break
            out.append(it)
            pos -= L
            wc = rng.choice(ok)
            k -= 1
        out.reverse()
        return out


# --------------------------------------------------------------------------
# plan
# --------------------------------------------------------------------------

@dataclass
class Placed:
    piece: Piece
    x: float            # record position, engine cm (before the final shift)
    y: float
    roll: int
    bias: float


@dataclass
class Plan:
    kit: str
    pitch_cm: float
    placed: List[Placed] = field(default_factory=list)
    extra: List[ad.ObjectRecord] = field(default_factory=list)   # dressing, barricades, warps
    #: socket frames to shut: (point, normal, lateral, width, depth)
    shut: List[tuple] = field(default_factory=list)
    #: joins a run fell short of: (point, direction, gap cm, width) -- walk is
    #: painted across them, as the shipped attr is continuous through a join
    seams: List[tuple] = field(default_factory=list)
    shift: Tuple[float, float] = (0.0, 0.0)
    size: Tuple[int, int] = (1, 1)
    start: Tuple[float, float] = (0.0, 0.0)
    boss: Tuple[float, float] = (0.0, 0.0)
    #: warp gate pairs, engine cm after the shift: what a server quest links
    warps: List[Tuple[Tuple[float, float], Tuple[float, float]]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    #: a trench labyrinth's geometry (`labyrinth_terrain.TrenchShape`); None
    #: for a kit of pieces
    terrain: object = None
    _raster: object = None

    def raster(self, shape, seed=0):
        """Trench labyrinths: height, floor, walk and edge distance, once per shape."""
        if self._raster is None or self._raster["edge"].shape != tuple(shape):
            self._raster = self.terrain.raster(tuple(shape), seed)
        return self._raster

    def records(self, floor_z: float) -> List[ad.ObjectRecord]:
        sx, sy = self.shift
        out = []
        for p in self.placed:
            out.append(ad.ObjectRecord(x=round(p.x + sx, 1), y=round(p.y + sy, 1),
                                       z=floor_z, crc=p.piece.crc, roll=float(p.roll % 360),
                                       height_bias=float(p.bias)))
        for r in self.extra:
            out.append(ad.ObjectRecord(x=round(r.x + sx, 1), y=round(r.y + sy, 1), z=floor_z,
                                       crc=r.crc, roll=float(r.roll % 360),
                                       height_bias=r.height_bias))
        return out

    def masks(self, shape) -> Tuple[np.ndarray, np.ndarray]:
        """(walk, block) in tile space."""
        if self.terrain is not None:
            return self.raster(shape)["walk"], np.zeros(shape, bool)
        h, w = shape
        walk = np.zeros(shape, bool)
        sx, sy = self.shift
        for p in self.placed:
            g = p.piece.grid
            ii, jj = np.nonzero(p.piece.walk)
            lx = g["x0"] + (jj + 0.5) * RES
            ly = g["y0"] + (ii + 0.5) * RES
            ex, ey = _rot(lx, ly, p.roll)
            col = np.floor((p.x + sx + ex) / RES).astype(int)
            row = np.floor(-(p.y + sy + ey) / RES).astype(int)
            ok = (col >= 0) & (col < w) & (row >= 0) & (row < h)
            walk[row[ok], col[ok]] = True
        for (px, py), n, gap, width in self.seams:
            t = (-n[1], n[0])
            us = np.arange(-300.0, gap + 301.0, 50.0)
            vs = np.arange(-width / 2 + 300.0, width / 2 - 299.0, 50.0)
            U, V = np.meshgrid(us, vs)
            x = px + sx + n[0] * U + t[0] * V
            y = py + sy + n[1] * U + t[1] * V
            col = np.floor(x / RES).astype(int)
            row = np.floor(-y / RES).astype(int)
            ok = (col >= 0) & (col < w) & (row >= 0) & (row < h)
            walk[row[ok], col[ok]] = True
        block = np.zeros(shape, bool)
        for (px, py), n, t, width, depth in self.shut:
            us = np.arange(-depth, 151, 50.0)
            vs = np.arange(-(width / 2 + 200), width / 2 + 201, 50.0)
            U, V = np.meshgrid(us, vs)
            x = px + sx + n[0] * U + t[0] * V
            y = py + sy + n[1] * U + t[1] * V
            col = np.floor(x / RES).astype(int)
            row = np.floor(-y / RES).astype(int)
            ok = (col >= 0) & (col < w) & (row >= 0) & (row < h)
            block[row[ok], col[ok]] = True
        return walk, block


class _Builder:
    def __init__(self, spec: MapSpec, kit: Kit):
        self.spec, self.kit, self.lab = spec, kit, spec.labyrinth
        self.rng = random.Random(stream_seed("labyrinth", spec.seed))
        self.solver = RunSolver(kit)
        self.plan = Plan(kit=kit.name, pitch_cm=0.0)
        seams = kit.of("seam")
        joints = sum(p.count for p in kit.of("straight"))
        self.seam_rate = (sum(p.count for p in seams) / joints) if (seams and joints) else 0.0
        self.seams = seams

    # -- choice ------------------------------------------------------------
    def nodes_for(self, want: set) -> List[Tuple[Piece, List[int]]]:
        kinds = {1: ("cap",), 2: ("corner", "straight"), 3: ("tee",), 4: ("cross",)}[len(want)]
        out = []
        for p in self.kit.pieces.values():
            if p.kind in kinds:
                rolls = p.rolls_for(want)
                if rolls:
                    out.append((p, rolls))
        return out

    def pick(self, opts):
        tot = sum(p.count for p, _ in opts)
        x = self.rng.random() * tot
        for p, rolls in opts:
            x -= p.count
            if x <= 0:
                return p, self.rng.choice(rolls)
        p, rolls = opts[-1]
        return p, self.rng.choice(rolls)

    # -- geometry ----------------------------------------------------------
    def place_node(self, piece, roll, cx, cy):
        ox, oy = _rot(piece.centre[0], piece.centre[1], roll)
        self.plan.placed.append(Placed(piece, cx - ox, cy - oy, roll, piece.bias))
        self.dress(piece, cx - ox, cy - oy, roll)

    def node_socket(self, piece, roll, cx, cy, world_side):
        local = next(s for s in piece.sockets if turn(s["side"], roll) == world_side)
        dx, dy = _rot(local["x"] - piece.centre[0], local["y"] - piece.centre[1], roll)
        return (cx + dx, cy + dy), local

    def dress(self, piece, x, y, roll):
        # A warp gate is placed where it leads somewhere, and a barricade where
        # an arm is shut: the spider fences ride a third of the room placements
        # only because a third of the arms are fenced.
        skip = self.kit.warp_crcs
        if self.kit.mode == "grid" and self.kit.barricade and self.kit.barricade.get("template"):
            skip = skip | {r["crc"] for r in self.kit.barricade["template"]["records"]}
        for d in piece.dressing:
            if d["crc"] in skip:
                continue
            if d["share"] < 0.5 and self.rng.random() > d["share"]:
                continue
            dx, dy = _rot(d["x"], d["y"], roll)
            r = d["roll"] if d.get("absolute") else roll + d["roll"]
            self.plan.extra.append(ad.ObjectRecord(x=x + dx, y=y + dy, crc=d["crc"],
                                                   roll=float(r % 360),
                                                   height_bias=float(d["bias"])))

    def lay_run(self, start, side, chain, width):
        """Lay a solved run from a world socket point along a world side.

        Every join it makes is also a seam the walk is painted across: a
        piece's measured walk stops at the rim under its wall foot, ~2 m short
        of the mouth on the skipia rooms (75-80% of the socket band walkable),
        while the shipped attr runs straight through every join."""
        vx, vy = VEC[side]
        px, py = start
        heading = SIDE_DEG[side]
        self.plan.seams.append(((px, py), (vx, vy), 0.0, width))
        for i, (p, s_in, s_out, length) in enumerate(chain):
            local_dir = SIDE_DEG[s_out["side"]]
            roll = (heading - local_dir) % 360
            ox, oy = _rot(s_in["x"], s_in["y"], roll)
            # keep the run on its axis: drop the socket's lateral offset
            if side in ("E", "W"):
                rx, ry = px - ox, start[1] - oy
            else:
                rx, ry = start[0] - ox, py - oy
            self.plan.placed.append(Placed(p, rx, ry, roll, p.bias))
            self.dress(p, rx, ry, roll)
            if i and self.seams and self.rng.random() < self.seam_rate:
                self.seam_at((px, py) if side in ("E", "W") else (start[0], py), heading)
            px += vx * length
            py += vy * length
            self.plan.seams.append(((px if side in ("E", "W") else start[0],
                                     py if side in ("N", "S") else start[1]),
                                    (vx, vy), 0.0, min(width, s_out["width"])))

    def seam_at(self, point, heading):
        p = self.rng.choice(self.seams)
        a, b = p.sockets
        mx, my = (a["x"] + b["x"]) / 2.0, (a["y"] + b["y"]) / 2.0
        local_dir = SIDE_DEG[a["side"]]
        roll = (heading - local_dir) % 360
        ox, oy = _rot(mx, my, roll)
        self.plan.placed.append(Placed(p, point[0] - ox, point[1] - oy, roll, p.bias))

    # -- whole ---------------------------------------------------------------
    def build(self) -> Plan:
        kit, lab = self.kit, self.lab
        cols, rows = lab.cells
        grid_mode = kit.mode == "grid"
        if grid_mode:
            edges_open = maze(cols, rows, lab.loops, 4, self.rng)
            built = {frozenset(((c, r), (c + dc, r + dr)))
                     for c in range(cols) for r in range(rows)
                     for dc, dr in ((1, 0), (0, 1)) if c + dc < cols and r + dr < rows}
        else:
            edges_open = maze(cols, rows, lab.loops, kit.max_degree, self.rng)
            built = edges_open

        # entrance and boss. Each takes one more mouth, out of the grid, so
        # neither may already be at the kit's highest junction (the maze kits
        # have no cross piece).
        ent = lab.entrance
        maxdeg = 4 if grid_mode else kit.max_degree

        def deg(cell):
            return len(sides_of(cell, built))

        def on(cell, side):
            return self._on_side(cell, side, cols, rows)
        line = [(c, r) for c in range(cols) for r in range(rows) if on((c, r), ent)]
        centre = ((cols - 1) / 2.0, (rows - 1) / 2.0)
        line.sort(key=lambda x: abs(x[0] - centre[0]) + abs(x[1] - centre[1]))
        mid = next((x for x in line if deg(x) < maxdeg), line[0])
        dist = bfs(mid, edges_open)
        extra_sides: Dict[tuple, set] = {}
        outward = {}
        boss = None
        if lab.rooms:
            far = OPP[ent]
            cands = []
            for c in range(cols):
                for r in range(rows):
                    for side in SIDES:
                        if on((c, r), side) and side != ent and (c, r) != mid \
                                and deg((c, r)) < maxdeg:
                            cands.append(((dist.get((c, r), 0), side == far), (c, r), side))
            if cands:
                _k, boss, bside = max(cands)
                outward = {mid: ent, boss: bside}
            else:
                outward = {mid: ent}
            for cell, sd in outward.items():
                extra_sides.setdefault(cell, set()).add(sd)

        # pitch
        P = (lab.pitch_m * 100.0) if lab.pitch_m else self.auto_pitch(grid_mode)
        self.plan.pitch_cm = P
        self.plan.notes.append("labyrinth: kit %s, %s mode, %dx%d cells, pitch %.0f m, "
                               "%d open of %d built edges"
                               % (kit.name, kit.mode, cols, rows, P / 100.0,
                                  len(edges_open), len(built)))

        if kit.mode == "warp":
            self.build_warp(cols, rows, P, edges_open, extra_sides, mid, outward)
            self.frame()
            return self.plan
        # nodes, retried until every run fills
        for attempt in range(40):
            self.plan.placed, self.plan.extra, self.plan.shut = [], [], []
            self.plan.seams = []
            ok = self.assemble(cols, rows, P, built, edges_open, extra_sides, grid_mode)
            if ok:
                break
        else:
            raise SpecError("labyrinth: kit %s cannot fill its runs at pitch %.0f m -- "
                            "set labyrinth.pitch_m" % (kit.name, P / 100.0))
        if lab.rooms and boss is not None:
            self.rooms(mid, ent, boss, outward[boss], P)
        self.frame()
        return self.plan

    # -- warp mode -----------------------------------------------------------
    def build_warp(self, cols, rows, P, edges, outer, mid, outward):
        """Islands that close, joined by warp gates.

        Grown breadth-first from the entrance: a cell joins the island it
        touches while the island still closes (`assemble` on its cells alone),
        up to `ISLAND_CELLS`. Every maze edge left between two islands, and the
        entrance and boss mouths, becomes a capped stub with a warp gate in the
        cap; the two gates of an edge are a pair. Islands, and the start and
        boss rooms, are shelf-packed 40 m apart -- in the source maps the
        letters stand wherever, the warps are the maze.
        """
        adj = {}
        for e in edges:
            a, b = tuple(e)
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
        order = list(bfs(mid, edges))
        order += [(c, r) for c in range(cols) for r in range(rows) if (c, r) not in order]

        def stubs_for(cells, built):
            ex = {}
            for cell in cells:
                miss = sides_of(cell, edges) - sides_of(cell, built)
                miss |= set(outer.get(cell, ()))
                if miss:
                    ex[cell] = miss
            return ex

        def inner(cells):
            return {e for e in edges if all(x in cells for x in e)}

        def closes(cells):
            built = inner(cells)
            ex = stubs_for(cells, built)
            saved = (self.plan.placed, self.plan.extra, self.plan.shut, self.plan.seams)
            try:
                for _ in range(6):
                    self.plan.placed, self.plan.extra, self.plan.shut = [], [], []
                    self.plan.seams = []
                    if self.assemble(cols, rows, P, built, edges, ex, False, present=cells):
                        return True
                return False
            finally:
                self.plan.placed, self.plan.extra, self.plan.shut, self.plan.seams = saved

        assigned, islands = {}, []
        for seed in order:
            if seed in assigned:
                continue
            isl = {seed}
            queue = [seed]
            for cur in queue:
                for n in sorted(adj.get(cur, [])):
                    # a dead end always rides with its neighbour: alone it
                    # would be a cap with nothing to close
                    full = len(isl) >= ISLAND_CELLS and len(adj.get(n, [])) > 1
                    if n in assigned or n in isl or full:
                        continue
                    if closes(isl | {n}):
                        isl = isl | {n}
                        queue.append(n)
            for cell in isl:
                assigned[cell] = len(islands)
            islands.append(isl)

        # assemble each island for real, keep its pieces and its stubs
        blocks = []          # (placed, extra, stubs[(cell, side, point, family)])
        for isl in islands:
            built = inner(isl)
            ex = stubs_for(isl, built)
            for _ in range(40):
                self.plan.placed, self.plan.extra, self.plan.shut = [], [], []
                self.plan.seams = []
                if self.assemble(cols, rows, P, built, edges, ex, False, present=isl):
                    break
            else:
                raise SpecError("labyrinth: island %s of kit %s does not close"
                                % (sorted(isl), self.kit.name))
            stubs = []
            for cell, sides in ex.items():
                piece, roll = self.chosen[cell]
                for side in sides:
                    pt, sk = self.node_socket(piece, roll, self.X[cell[0]], -self.Y[cell[1]], side)
                    stubs.append((cell, side, pt, sk["family"], sk["width"]))
            blocks.append((self.plan.placed, self.plan.extra, stubs, self.plan.seams))

        # rooms: the island pieces, largest the boss
        rooms = sorted([p for p in self.kit.of("island") if p.walk_m2 >= ISLAND_M2],
                       key=lambda p: -p.walk_m2)
        boss_cell = next((c for c in outward if c != mid), None)
        room_for = {}
        if rooms and boss_cell is not None:
            room_for[(boss_cell, outward[boss_cell])] = ("boss", rooms[0])
        if len(rooms) > 1:
            room_for[(mid, outward[mid])] = ("start", rooms[1])
        room_blocks = []
        for key, (tag, room) in room_for.items():
            placed = [Placed(room, 0.0, 0.0, 0, room.bias)]
            room_blocks.append((key, tag, room, placed))

        # shelf-pack islands then rooms
        def bbox(placed):
            xs, ys = [], []
            for pl in placed:
                x0, y0, x1, y1 = pl.piece.bbox
                for lx, ly in ((x0, y0), (x0, y1), (x1, y0), (x1, y1)):
                    ex, ey = _rot(lx, ly, pl.roll)
                    xs.append(pl.x + ex)
                    ys.append(pl.y + ey)
            return min(xs), min(ys), max(xs), max(ys)
        units = [("island", i, b[0]) for i, b in enumerate(blocks)] + \
                [("room", i, rb[3]) for i, rb in enumerate(room_blocks)]
        boxes = [bbox(u[2]) for u in units]
        area = sum((b[2] - b[0] + 4000) * (b[3] - b[1] + 4000) for b in boxes)
        width = max(math.sqrt(area) * 1.2, max(b[2] - b[0] for b in boxes) + 4000)
        x = y = shelf = 0.0
        shift = []
        for b in boxes:
            w, h = b[2] - b[0], b[3] - b[1]
            if x and x + w > width:
                x, y, shelf = 0.0, y - shelf - 4000.0, 0.0
            shift.append((x - b[0], y - b[3]))        # top-left at (x, y)
            x += w + 4000.0
            shelf = max(shelf, h)

        self.plan.placed, self.plan.extra, self.plan.shut = [], [], []
        self.plan.seams = []
        stub_at = {}
        for (kind, i, placed), (dx, dy) in zip(units, shift):
            for pl in placed:
                pl.x += dx
                pl.y += dy
                self.plan.placed.append(pl)
            if kind == "island":
                for (px, py), n, g, wd in blocks[i][3]:
                    self.plan.seams.append(((px + dx, py + dy), n, g, wd))
                for r in blocks[i][1]:
                    r.x += dx
                    r.y += dy
                    self.plan.extra.append(r)
                for cell, side, (px, py), fam, wd in blocks[i][2]:
                    stub_at[(cell, side)] = (self.cap_mouth((px + dx, py + dy), side, fam, P, wd), side)
            else:
                key, tag, room, _pl = room_blocks[i]
                self.dress(room, placed[0].x, placed[0].y, 0)
                wc = self._walk_centre(room)
                room_pt = (placed[0].x + wc[0], placed[0].y + wc[1])
                stub_at[("room", key)] = (room_pt, None)
                self._mark(tag, room_pt)

        # warp pairs
        pairs = []
        done = set()
        for (cell, side), (pt, _s) in list(stub_at.items()):
            if cell == "room":
                continue
            n = (cell[0] + STEP[side][0], cell[1] + STEP[side][1])
            if (cell, side) in done:
                continue
            if (n, OPP[side]) in stub_at:
                pairs.append((pt, stub_at[(n, OPP[side])][0]))
                done |= {(cell, side), (n, OPP[side])}
            elif ("room", (cell, side)) in stub_at:
                pairs.append((pt, stub_at[("room", (cell, side))][0]))
                done.add((cell, side))
            elif cell == mid and side == outward.get(mid):
                self._mark("start", pt)
        for a, b in pairs:
            for x, y in (a, b):
                self.plan.extra.append(ad.ObjectRecord(x=x, y=y, crc=self.kit.warp_crc,
                                                       roll=0.0, height_bias=WARP_BIAS))
        self.plan.warps = pairs
        self.plan.notes.append("warp mode: %d island(s) of %s cells, %d warp pair(s) "
                               "(server warp quest not generated; pairs in the log)"
                               % (len(islands), "/".join(str(len(i)) for i in islands), len(pairs)))
        for tag, room in room_for.values():
            self.plan.notes.append("%s: island room %s, reached by warp" % (tag, room.name))

    def cap_mouth(self, point, side, family, P, width):
        """Close a mouth facing ``side`` at ``point`` with the kit's commonest cap,
        through an adapter run where the cap is of another family (a
        whitedragon room's 10 m mouth takes a door before its end cap). Returns
        a point inside the cap, for a warp gate or a spawn."""
        vx, vy = VEC[side]
        for cap in sorted(self.kit.of("cap"), key=lambda c: -c.count):
            chain = self.solver.solve(P / 4.0, family, cap.sockets[0]["family"], self.rng,
                                      slack=P / 4.0)
            if chain is None:
                continue
            length = sum(it[3] for it in chain)
            self.lay_run(point, side, chain, width)
            end = (point[0] + vx * length, point[1] + vy * length)
            self.place_at_socket(cap, OPP[side], end)
            pl = self.plan.placed[-1]
            wc = self._walk_centre(cap)
            ox, oy = _rot(wc[0], wc[1], pl.roll)
            return (pl.x + ox, pl.y + oy)
        self.plan.notes.append("! no cap closes a %s mouth; shut by attr" % side)
        self.plan.shut.append((point, (vx, vy), (-vy, vx), 3000.0, 600.0))
        return (point[0] - vx * 1500, point[1] - vy * 1500)

    @staticmethod
    def _on_side(cell, side, cols, rows):
        c, r = cell
        return {"N": r == 0, "S": r == rows - 1, "W": c == 0, "E": c == cols - 1}[side]

    def plain(self):
        """Junction pieces, less the rooms among them: a node more than twice
        the size of the kit's smallest junction is a room (`WDC_01_room_04`
        162 m against `WDC_01_cross_01` 49 m; `anglar_boss2` 114 m against
        `anglar_stonecave4` 56 m)."""
        nodes = [p for p in self.kit.pieces.values() if p.kind in ("corner", "tee", "cross")]
        if not nodes:
            return []
        size = lambda p: max(p.bbox[2] - p.bbox[0], p.bbox[3] - p.bbox[1])
        lim = 2.0 * min(size(p) for p in nodes)
        return [p for p in nodes if size(p) <= lim]

    def corpus_pitch(self) -> Optional[float]:
        """Median distance between a junction and the nearest junction on its
        axis, over the kit's source maps: anglar 107 m, maze 66.5, whitedragon_01
        131.5, whitedragon_02 60, spider 99, skipia 100.6. The cell pitch is
        aimed at it -- the shortest pitch that closes puts every skipia room
        against the next with no corridor between, which no source map does."""
        nodes = {p.crc: p for p in self.plain()}
        ds = []
        for lay in self.kit.layouts.values():
            pts = []
            for crc, x, y, roll, _bias in lay:
                p = nodes.get(crc)
                if p is not None:
                    ox, oy = _rot(p.centre[0], p.centre[1], roll)
                    pts.append((x + ox, -y + oy))
            pts = np.array(pts)
            for i, a in enumerate(pts):
                on_axis = (np.abs(pts[:, 0] - a[0]) < 300) | (np.abs(pts[:, 1] - a[1]) < 300)
                d = np.hypot(pts[:, 0] - a[0], pts[:, 1] - a[1])
                d = d[on_axis & (d > 1.0)]
                if len(d):
                    ds.append(d.min())
        return float(np.median(ds)) if ds else None

    def auto_pitch(self, grid_mode):
        """The pitch the kit's plain junctions join at.

        Grid mode: the room arms meet tip to tip, so it is twice the reach
        (spider 100 m, as shipped). Path mode: of the pitches within 0.7-1.4x
        the corpus spacing (`corpus_pitch`), those where the most corpus-
        weighted pairs of junction reaches fill a one-cell run, and of those the
        one nearest the corpus. `assemble` picks junctions and turns so the
        rest close.
        """
        nodes = self.plain()
        reach = [(p.reach(s), p.socket(s)["family"], p.count)
                 for p in nodes for s in p.sides]
        if grid_mode:
            return float(round(max(r for r, _f, _n in reach) * 2 / 100.0) * 100)
        lo = max(r for r, _f, _n in reach) * 2
        target = self.corpus_pitch() or lo * 1.5
        self._feas = getattr(self, "_feas", {})
        pairs = [(ra + rb, fa, fb, na * nb) for ra, fa, na in reach for rb, fb, nb in reach]
        tot = float(sum(w for *_x, w in pairs))
        scored = []
        for P in range(int(max(lo, 0.7 * target) / 50) * 50, int(1.4 * target), 50):
            ok = sum(w for r, fa, fb, w in pairs if self.feasible(P - r, fa, fb, 0.0))
            scored.append((ok / tot, P))
        if not scored:
            return float(lo)
        top = max(sc for sc, _P in scored)
        return float(min((abs(P - target), P) for sc, P in scored if sc >= top - 0.05)[1])

    def wreach(self, piece, roll, side):
        """Reach of a turned node toward a world side."""
        local = next(s["side"] for s in piece.sockets if turn(s["side"], roll) == side)
        return piece.reach(local)

    def wfam(self, piece, roll, side):
        return next(s["family"] for s in piece.sockets if turn(s["side"], roll) == side)

    def feasible(self, gap, fa, fb, slack):
        lo = gap - self.solver.short - slack
        hi = gap + self.solver.over
        if hi < 0:
            return False
        arr = self.solver.lengths(fa, fb, max(hi, 0) + 30000)
        i0, i1 = max(0, int(math.ceil(lo / QUANT))), int(hi // QUANT)
        return bool(arr[i0:i1 + 1].any())

    def assemble(self, cols, rows, P, built, edges_open, extra_sides, grid_mode, present=None):
        """Choose every node, place the columns and rows so every run fills,
        then lay it all.

        The grid is not uniform. Columns are placed west to east, each at the
        offset nearest the pitch at which every horizontal run that ends on it
        has a length the kit can build and no node body runs into the next one
        it is not joined to; rows the same, north to south. A kit with one
        corridor length (the maze kits: 63.5 m) closes this way, and a room
        pushes its column out instead of being refused -- the corpus maps are
        not on a uniform grid either. A cap is not pinned to its cell: it slides
        along its run by up to half a cell, as a dead end may stop anywhere.
        """
        chosen = {}
        for r in range(rows):
            for c in range(cols):
                if present is not None and (c, r) not in present:
                    continue
                want = sides_of((c, r), built, extra_sides.get((c, r), ()))
                if not grid_mode and len(want) == 2 and OPP[min(want)] == max(want) \
                        and (c, r) not in extra_sides:
                    continue                 # a straight run passes through
                opts = self.nodes_for(want)
                if not opts:
                    return False
                chosen[(c, r)] = self.weighted_order(opts)[0]
        X = self.solve_axis(cols, rows, P, chosen, built, True, present)
        Y = self.solve_axis(rows, cols, P, chosen, built, False, present) if X else None
        if X is None or Y is None:
            return False
        self.X, self.Y = X, Y

        def at(cell):
            return X[cell[0]], -Y[cell[1]]
        for cell, (p, roll) in chosen.items():
            if p.kind != "cap":
                self.place_node(p, roll, *at(cell))
        for (c, r), (p, roll) in chosen.items():
            for side in ("E", "S"):
                if side not in sides_of((c, r), built):
                    continue
                nc, nr = c + STEP[side][0], r + STEP[side][1]
                while (nc, nr) not in chosen:
                    nc, nr = nc + STEP[side][0], nr + STEP[side][1]
                q, qroll = chosen[(nc, nr)]
                a, sa = self.node_socket(p, roll, *at((c, r)), side)
                b, sb = self.node_socket(q, qroll, *at((nc, nr)), OPP[side])
                gap = (b[0] - a[0]) if side == "E" else (a[1] - b[1])
                slack = P / 2.0 if (p.kind == "cap" or q.kind == "cap") else 0.0
                chain = self.solver.solve(gap, sa["family"], sb["family"], self.rng, slack=slack)
                if chain is None:
                    return False
                length = sum(it[3] for it in chain)
                vx, vy = VEC[side]
                if p.kind == "cap":
                    # the run ends on the far node; the cap closes its near end
                    a = (b[0] - vx * length, b[1] - vy * length)
                    self.place_at_socket(p, side, a)
                elif q.kind == "cap":
                    self.place_at_socket(q, OPP[side], (a[0] + vx * length, a[1] + vy * length))
                elif gap - length > 0:
                    self.plan.seams.append(((a[0] + vx * length, a[1] + vy * length), (vx, vy),
                                            gap - length, min(sa["width"], sb["width"])))
                self.lay_run(a, side, chain, min(sa["width"], sb["width"]))
                if grid_mode and frozenset(((c, r), (nc, nr))) not in edges_open:
                    self.shut(a, side, sa["width"])
                    self.shut(b, OPP[side], sb["width"])
        self.chosen = chosen
        return True

    def solve_axis(self, n, m, P, chosen, built, horizontal, present=None):
        """Positions of the n columns (or rows), cm, the first at 0. Cells not
        ``present`` (another warp island's) are not there."""
        fwd, back = ("E", "W") if horizontal else ("S", "N")

        def cell(i, j):
            return (i, j) if horizontal else (j, i)
        runs = [[] for _ in range(n)]       # (j_from, reach sum, fa, fb, slack)
        clear = [[] for _ in range(n)]      # (j_from, needed distance)
        for j in range(m):
            last = None                     # (index, occupant extent toward fwd)
            for i in range(n):
                cl = cell(i, j)
                if present is not None and cl not in present:
                    continue
                node = chosen.get(cl)
                if node is not None:
                    p, roll = node
                    if last is not None:
                        li, lext, lnode, joined = last
                        if joined and lnode is not None:
                            q, qroll = lnode
                            slack = P / 2.0 if (p.kind == "cap" or q.kind == "cap") else 0.0
                            runs[i].append((li, self.wreach(q, qroll, fwd) + self.wreach(p, roll, back),
                                            self.wfam(q, qroll, fwd), self.wfam(p, roll, back), slack))
                        elif not joined:
                            clear[i].append((li, lext + self.extent(p, roll, back) + 200.0))
                    ext = self.extent(p, roll, fwd)
                else:
                    # a corridor passing through, across this axis or along it
                    p = None
                    ext = 2000.0
                    if last is not None and not last[3]:
                        clear[i].append((last[0], last[1] + 2000.0 + 200.0))
                nxt = cell(i + 1, j)
                joined = frozenset((cl, nxt)) in built
                if node is not None or not joined:
                    last = (i, ext, node, joined)
                elif last is not None:
                    # run continues through this cell: keep the node it started at
                    last = (last[0], last[1], last[2], True)
        pos = [0.0]
        cands = range(int(0.5 * P), int(2.2 * P), 10)
        for i in range(1, n):
            best = None
            for d in cands:
                x = pos[-1] + d
                if not all(x - pos[j] >= need for j, need in clear[i]):
                    continue
                cost = 0.002 * abs(d - P)
                for j, R, fa, fb, sl in runs[i]:
                    m = self.fit_cost(x - pos[j] - R, fa, fb, sl)
                    if m is None:
                        break
                    cost += m
                else:
                    if best is None or cost < best[0]:
                        best = (cost, x)
            if best is None:
                return None
            pos.append(float(best[1]))
        return pos

    def fit_cost(self, gap, fa, fb, slack):
        """Misfit of the best run for a gap, or None when none lands in the band."""
        if not self.feasible(gap, fa, fb, slack):
            return None
        if slack:
            return 0.0
        arr = self.solver.lengths(fa, fb, max(gap, 0) + 30000)
        i0 = max(0, int(math.ceil((gap - self.solver.short) / QUANT)))
        i1 = int((gap + self.solver.over) // QUANT)
        idx = np.nonzero(arr[i0:i1 + 1])[0]
        return min(RunSolver.misfit((i0 + k) * QUANT - gap) for k in idx)

    def weighted_order(self, opts):
        """Candidates in a corpus-frequency-weighted random order, rolls shuffled."""
        pool = list(opts)
        out = []
        while pool:
            tot = sum(p.count for p, _ in pool)
            x = self.rng.random() * tot
            for i, (p, rolls) in enumerate(pool):
                x -= p.count
                if x <= 0:
                    break
            p, rolls = pool.pop(i)
            rolls = list(rolls)
            self.rng.shuffle(rolls)
            out += [(p, r) for r in rolls]
        return out

    def fits(self, p, roll, cell, chosen, P, built, want):
        c, r = cell
        for side in ("W", "N"):
            dc, dr = STEP[side]
            n = (c + dc, r + dr)
            joined = frozenset((cell, n)) in built
            if joined:
                k = 1
                while n not in chosen:
                    k += 1
                    n = (n[0] + dc, n[1] + dr)
                q, qroll = chosen[n]
                gap = k * P - self.wreach(p, roll, side) - self.wreach(q, qroll, OPP[side])
                slack = P / 2.0 if (p.kind == "cap" or q.kind == "cap") else 0.0
                if not self.feasible(gap, self.wfam(q, qroll, OPP[side]),
                                     self.wfam(p, roll, side), slack):
                    return False
            elif n in chosen:
                q, qroll = chosen[n]
                if self.extent(p, roll, side) + self.extent(q, qroll, OPP[side]) > P - 200.0:
                    return False
        # and no body into a neighbour it is not joined to, east and south
        # (a run-through cell holds a corridor ~20 m either side of its axis)
        for side in ("E", "S"):
            n = (c + STEP[side][0], r + STEP[side][1])
            if frozenset((cell, n)) not in built and self.extent(p, roll, side) > P - 2000.0:
                return False
        return True

    def place_at_socket(self, piece, world_side, point):
        """Place a one-socket piece with its socket on a point, facing a world side."""
        roll = next(r for r in (0, 90, 180, 270) if turn(piece.sides[0], r) == world_side)
        sk = piece.sockets[0]
        ox, oy = _rot(sk["x"], sk["y"], roll)
        self.plan.placed.append(Placed(piece, point[0] - ox, point[1] - oy, roll, piece.bias))
        self.dress(piece, point[0] - ox, point[1] - oy, roll)

    @staticmethod
    def extent(piece, roll, side):
        """How far the turned piece reaches from its centre toward a world side."""
        x0, y0, x1, y1 = piece.bbox
        vx, vy = VEC[side]
        best = 0.0
        for lx, ly in ((x0, y0), (x0, y1), (x1, y0), (x1, y1)):
            ex, ey = _rot(lx - piece.centre[0], ly - piece.centre[1], roll)
            best = max(best, ex * vx + ey * vy)
        return best

    def shut(self, point, side, width):
        bar = self.kit.barricade
        if not bar:
            return
        n = VEC[side]
        t = (-n[1], n[0])
        self.plan.shut.append((point, n, t, width, float(bar["depth_cm"] or 2000)))
        tpl = bar.get("template")
        for rec in (tpl["records"] if tpl else []):
            x = point[0] + n[0] * rec["u"] + t[0] * rec["v"]
            y = point[1] + n[1] * rec["u"] + t[1] * rec["v"]
            self.plan.extra.append(ad.ObjectRecord(
                x=x, y=y, crc=rec["crc"], roll=float((SIDE_DEG[side] + rec["roll"]) % 360),
                height_bias=float(rec["bias"])))

    def rooms(self, start_cell, start_side, boss_cell, boss_side, P):
        kit = self.kit
        socketed = sorted(kit.of("room"), key=lambda p: -p.walk_m2)
        islands = sorted([p for p in kit.of("island") if p.walk_m2 >= ISLAND_M2],
                         key=lambda p: -p.walk_m2)
        boss = islands[0] if islands else (socketed[0] if socketed else None)
        rest = [p for p in socketed + islands if p is not boss]
        start = rest[0] if rest else None
        for cell, side, room, tag in ((boss_cell, boss_side, boss, "boss"),
                                      (start_cell, start_side, start, "start")):
            # the outward socket of the edge node is where the room hangs
            npiece, nroll = self.chosen[cell]
            (sx, sy), sk = self.node_socket(npiece, nroll, self.X[cell[0]], -self.Y[cell[1]], side)
            vx, vy = VEC[side]
            if room is not None and room.kind == "room":
                # one cell out, its mouth facing back in, the run solved to it
                chain = None
                for gap in (P / 2.0, 0.0, P):
                    chain = self.solver.solve(gap, sk["family"], room.sockets[0]["family"],
                                              self.rng, slack=P / 4.0 if gap else 0.0)
                    if chain is not None:
                        length = sum(it[3] for it in chain)
                        tx, ty = sx + vx * length, sy + vy * length
                        break
                if chain is None:
                    self.plan.notes.append("! %s room %s: no run fits; capped instead" % (tag, room.name))
                    room = None
                else:
                    self.lay_run((sx, sy), side, chain, min(sk["width"], room.sockets[0]["width"]))
                    roll = next(r for r in (0, 90, 180, 270) if turn(room.sides[0], r) == OPP[side])
                    self.place_node(room, roll, tx, ty)
                    far = self._far_point(room, roll, tx, ty)
                    self._mark(tag, far)
                    self.plan.notes.append("%s: room %s off the %s side" % (tag, room.name, side))
                    continue
            # capped mouth: a dead end that leads out of the grid
            inside = self.cap_mouth((sx, sy), side, sk["family"], P, sk["width"])
            if room is not None and room.kind == "island":
                # the island stands clear beyond the cap; a warp at each end
                gx, gy = room.grid["x0"], room.grid["y0"]
                rcx = (room.bbox[0] + room.bbox[2]) / 2.0
                rcy = (room.bbox[1] + room.bbox[3]) / 2.0
                half = max(room.bbox[2] - room.bbox[0], room.bbox[3] - room.bbox[1]) / 2.0
                cx_, cy_ = sx + vx * (half + 4000), sy + vy * (half + 4000)
                self.plan.placed.append(Placed(room, cx_ - rcx, cy_ - rcy, 0, room.bias))
                self.dress(room, cx_ - rcx, cy_ - rcy, 0)
                wc = self._walk_centre(room)
                warp = self.kit.warp_crc
                self.plan.extra.append(ad.ObjectRecord(x=inside[0], y=inside[1], crc=warp,
                                                       roll=float(SIDE_DEG[side] % 360),
                                                       height_bias=55.0))
                self.plan.extra.append(ad.ObjectRecord(x=cx_ - rcx + wc[0], y=cy_ - rcy + wc[1],
                                                       crc=warp, roll=0.0, height_bias=55.0))
                self._mark(tag, (cx_ - rcx + wc[0], cy_ - rcy + wc[1]))
                self.plan.warps.append((inside, (cx_ - rcx + wc[0], cy_ - rcy + wc[1])))
                self.plan.notes.append("%s: island %s %s of the grid, warp gate at the capped "
                                       "dead end (server warp not generated)" % (tag, room.name, side))
            else:
                self._mark(tag, inside)
                self.plan.notes.append("%s: capped dead end on the %s side" % (tag, side))

    def _cap_for(self, family):
        caps = [p for p in self.kit.of("cap") if p.sockets[0]["family"] == family]
        if not caps:
            return None
        return max(caps, key=lambda c: c.count)

    def _far_point(self, room, roll, x, y):
        wc = self._walk_centre(room)
        ox, oy = _rot(wc[0] - room.centre[0], wc[1] - room.centre[1], roll)
        return (x + ox, y + oy)

    @staticmethod
    def _walk_centre(p):
        ii, jj = np.nonzero(p.walk)
        if not len(ii):
            return ((p.bbox[0] + p.bbox[2]) / 2.0, (p.bbox[1] + p.bbox[3]) / 2.0)
        return (p.grid["x0"] + (jj.mean() + 0.5) * RES, p.grid["y0"] + (ii.mean() + 0.5) * RES)

    def _mark(self, tag, pt):
        setattr(self.plan, tag, pt)

    def frame(self):
        """Shift into the map: margin round the extent, sectors to fit."""
        xs, ys = [], []
        for pl in self.plan.placed:
            x0, y0, x1, y1 = pl.piece.bbox
            for lx, ly in ((x0, y0), (x0, y1), (x1, y0), (x1, y1)):
                ex, ey = _rot(lx, ly, pl.roll)
                xs.append(pl.x + ex)
                ys.append(pl.y + ey)
        m = self.lab.margin_m * 100.0
        sx = m - min(xs)
        sy = -m - max(ys)
        sx, sy = round(sx / 100.0) * 100.0, round(sy / 100.0) * 100.0
        w = max(xs) + sx + m
        h = -(min(ys) + sy) + m
        self.plan.shift = (sx, sy)
        self.plan.size = (max(1, int(math.ceil(w / SECTOR_UNITS))),
                          max(1, int(math.ceil(h / SECTOR_UNITS))))
        self.plan.warps = [((a[0] + sx, a[1] + sy), (b[0] + sx, b[1] + sy))
                           for a, b in self.plan.warps]
        self.plan.start = (self.plan.start[0] + sx, self.plan.start[1] + sy)
        self.plan.boss = (self.plan.boss[0] + sx, self.plan.boss[1] + sy)


def plan(spec: MapSpec, kits_json=KITS_JSON) -> Plan:
    from . import labyrinth_terrain
    if spec.labyrinth.kit in labyrinth_terrain.TRENCH_STYLES:
        return labyrinth_terrain.build(spec, Plan, maze, bfs, sides_of)
    kit = load_kit(spec.labyrinth.kit, kits_json)
    return _Builder(spec, kit).build()


def reach_check(plan: Plan, attr_cells: np.ndarray) -> List[str]:
    """Can the player get from the start to the boss on the attr as written?

    Walkable is attr without BLOCK; a warp pair joins the two components it
    stands in. Read off the attr grid the build produced, not the plan's own
    masks -- the border band, the barricades and the carve all land there.
    """
    return _reach(plan, attr_cells)


def _components(walk: np.ndarray) -> np.ndarray:
    try:
        from scipy import ndimage
        lab, _n = ndimage.label(walk)
        return lab
    except ImportError:
        h, w = walk.shape
        lab = np.zeros((h, w), np.int32)
        n = 0
        for y0, x0 in zip(*np.nonzero(walk)):
            if lab[y0, x0]:
                continue
            n += 1
            stack = [(y0, x0)]
            lab[y0, x0] = n
            while stack:
                y, x = stack.pop()
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < h and 0 <= xx < w and walk[yy, xx] and not lab[yy, xx]:
                        lab[yy, xx] = n
                        stack.append((yy, xx))
        return lab


def _reach(plan: Plan, attr_cells: np.ndarray) -> List[str]:
    walk = (attr_cells & 1) == 0
    lab = _components(walk)
    h, w = walk.shape

    def comp(pt, r=6):
        col, row = int(pt[0] // RES), int(-pt[1] // RES)
        win = lab[max(0, row - r):row + r + 1, max(0, col - r):col + r + 1]
        ids = win[win > 0]
        return int(np.bincount(ids).argmax()) if len(ids) else 0
    n = int(lab.max())
    parent = list(range(n + 1))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    dead = 0
    for a, b in plan.warps:
        ca, cb = comp(a), comp(b)
        if not ca or not cb:
            dead += 1
            continue
        parent[find(ca)] = find(cb)
    cs, cb = comp(plan.start), comp(plan.boss)
    ok = bool(cs and cb and find(cs) == find(cb))
    sizes = np.bincount(lab.ravel())[1:]
    big = int((sizes >= 50).sum())
    out = ["labyrinth check: %d walkable component(s) of 50+ m2, %d warp pair(s)%s; "
           "start -> boss %s" % (big, len(plan.warps),
                                 (", %d off the walk" % dead) if dead else "",
                                 "REACHABLE" if ok else "NOT REACHABLE")]
    if not ok:
        out[0] = "! " + out[0]
    return out

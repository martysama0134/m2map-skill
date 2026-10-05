"""Dungeon kits -- the modular DungeonBlock sets the labyrinth dungeons are built from.

A block dungeon is a black plane with ``.prd`` pieces laid on it
(`reference/archetypes/12-dungeon_block.md`). This miner turns the pieces of
one family into a *kit*: for every piece, what it looks like from above, where
the player can walk on it, where it joins its neighbours, and what is hung on it.

What it reads, per piece:

``floor``
    The lowest upward-facing surface of the mesh (normal z > 0.7, within 4 m of
    the bottom), rasterised at 1 m in the piece's own frame. Every walkable
    cell of every source map lies on one: P(floor | walkable) is 0.97-1.00 over
    the nine maps (anglar and maze at 0.97 are the boss-room slopes).

``walk``
    P(walkable) per local cell, averaged over every placement of the piece in
    the source maps' shipped ``attr.atr``. The floor is not the walk: the
    attr is the floor less a rim under the wall foot, 2 m on ``wdc_02``,
    ``skipia`` and the maze, 5 m and more on ``wdc_01`` and ``spider`` -- and
    a door is a blocked line across a floor that runs through. So the walk is
    measured, not eroded.

``sockets``
    Where the piece meets another one in the source maps -- the contact of two
    placed floors, clustered in the piece's frame. Each has a side, a centre,
    a width and how often it was used.

``dressing``
    Non-DungeonBlock records (torches, sparkles, cobwebs, collision proxies,
    warp gates) that ride on the piece at the same local offset and relative
    roll in at least a third of its placements.

``layouts``
    Every source map's records as ``[piece, x, y, roll, bias]`` in map-local
    centimetres, y de-negated, so a shipped layout can be replayed with any kit
    of the same geometry.

Frames: a piece's local ``+x`` is east and ``+y`` north at roll 0; a record at
``(x, y_stored)`` with roll ``r`` puts local ``(lx, ly)`` at engine
``(x + c*lx - s*ly, y_stored + s*lx + c*ly)``, ``c, s = cos r, sin r`` -- roll
counter-clockwise with north up (rule 25). Verified here: the opposite sign
drops P(floor | walkable) on ``whitedragoncave_01`` from 1.000 to 0.816.

``python -m m2map.mine.dungeon_kits --out reference/labyrinth/kits.json``
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import os
import pathlib
import sys
from collections import Counter, defaultdict

import numpy as np

_HERE = pathlib.Path(__file__).resolve()
if str(_HERE.parents[2]) not in sys.path:
    sys.path.insert(0, str(_HERE.parents[2]))

from m2map.codec.areadata import AreaData                     # noqa: E402
from m2map.codec.attr import read_attr                        # noqa: E402
from m2map.config import paths as _paths                      # noqa: E402
from m2map.mine.models import Decompressor, DEFAULTS, read_mesh  # noqa: E402

SKILL_ROOT = _HERE.parents[3]
CATALOG = SKILL_ROOT / "reference" / "catalog"

#: kit name -> the corpus maps it is mined from. The maze and monkey dungeons
#: are ONE geometry in six skins (identical bboxes, identical layouts); each
#: skin is its own kit because its CRCs differ.
KITS = {
    "anglar": ["metin2_map_anglar_dungeon_01"],
    "maze": ["metin2_map_maze_dungeon1"],
    "maze02": ["metin2_map_maze_dungeon2"],
    "maze03": ["metin2_map_maze_dungeon3"],
    "monkey": ["metin2_map_monkeydungeon"],
    "monkey02": ["metin2_map_monkeydungeon_02"],
    "monkey03": ["metin2_map_monkeydungeon_03"],
    "whitedragon_01": ["metin2_map_whitedragoncave_01"],
    "whitedragon_02": ["metin2_map_whitedragoncave_02"],
    "spider": ["metin2_map_spiderdungeon_02", "metin2_map_spiderdungeon_03"],
    "skipia": ["metin2_map_skipia_dungeon_01", "metin2_map_skipia_dungeon_02"],
    "mt_thunder": ["metin2_map_mt_th_dungeon_01"],
}

RES = 100.0                 # cm per local cell
FLOOR_MIN_M2 = 20           # less floor than this: a rider, not a piece
FOOTPRINT_MIN_M2 = 30       # ... or a smaller bbox (`Mt_Thunder_startroompillar` 18 m2)
FLOOR_RISE = 400.0          # a floor face lies wholly below this, cm
WALK_SHARE = 0.25          # open in this share of placements -> walk
SIDES = ("E", "N", "W", "S")
SIDE_VEC = {"E": (1, 0), "N": (0, 1), "W": (-1, 0), "S": (0, -1)}


# --------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------

def pack(mask: np.ndarray) -> str:
    return base64.b64encode(np.packbits(mask.astype(bool), axis=None).tobytes()).decode()


def unpack(text: str, shape) -> np.ndarray:
    bits = np.unpackbits(np.frombuffer(base64.b64decode(text), np.uint8))
    return bits[: shape[0] * shape[1]].reshape(shape).astype(bool)


class Grid:
    """A piece's local 1 m grid: ``mask[i, j]`` is the cell whose centre is
    ``(x0 + (j + .5) * RES, y0 + (i + .5) * RES)`` -- row 0 is the SOUTH edge."""

    def __init__(self, x0, y0, nx, ny):
        self.x0, self.y0, self.nx, self.ny = x0, y0, nx, ny

    @classmethod
    def around(cls, lo, hi):
        x0 = math.floor(lo[0] / RES) * RES
        y0 = math.floor(lo[1] / RES) * RES
        return cls(x0, y0, int(math.ceil((hi[0] - x0) / RES)),
                   int(math.ceil((hi[1] - y0) / RES)))

    @property
    def shape(self):
        return (self.ny, self.nx)

    def centres(self):
        jj, ii = np.meshgrid(np.arange(self.nx), np.arange(self.ny))
        return (self.x0 + (jj + 0.5) * RES, self.y0 + (ii + 0.5) * RES)

    def to_json(self):
        return {"x0": self.x0, "y0": self.y0, "nx": self.nx, "ny": self.ny}


def floor_mask(V, T, grid: Grid, step=25.0) -> np.ndarray:
    P = V[T]
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    nz = n[:, 2] / (np.linalg.norm(n, axis=1) + 1e-9)
    # Absolute, not from the mesh bottom: every kit stands its floor at z ~ 0
    # (0-220 cm), and a boss room with a sunken pit (`anglar_boss2`, -508 cm)
    # would otherwise lose its whole floor to the pit.
    sel = (nz > 0.7) & (P[:, :, 2].max(1) < FLOOR_RISE)
    out = np.zeros(grid.shape, bool)
    for a, b, c in P[sel]:
        e1, e2 = b[:2] - a[:2], c[:2] - a[:2]
        k = int(max(np.hypot(*e1), np.hypot(*e2)) / step) + 2
        u, v = np.meshgrid(np.linspace(0, 1, k), np.linspace(0, 1, k))
        m = (u + v) <= 1.0
        q = a[None, :2] + u[m][:, None] * e1 + v[m][:, None] * e2
        j = ((q[:, 0] - grid.x0) / RES).astype(int)
        i = ((q[:, 1] - grid.y0) / RES).astype(int)
        ok = (j >= 0) & (j < grid.nx) & (i >= 0) & (i < grid.ny)
        out[i[ok], j[ok]] = True
    return out


def place(lx, ly, rec):
    """Local cm -> map tile (col, row) for one record."""
    t = math.radians(rec.roll)
    c, s = math.cos(t), math.sin(t)
    ex = rec.x + c * lx - s * ly
    ey = rec.y + s * lx + c * ly
    return ex / RES, -ey / RES


def unplace(col, row, rec):
    """Map tile -> local cm, the inverse of :func:`place`."""
    ex, ey = col * RES - rec.x, -row * RES - rec.y
    t = math.radians(rec.roll)
    c, s = math.cos(t), math.sin(t)
    return c * ex + s * ey, -s * ex + c * ey


# --------------------------------------------------------------------------
# corpus
# --------------------------------------------------------------------------

def load_map(root: pathlib.Path):
    st = (root / "setting.txt").read_text(errors="replace").split()
    w, h = int(st[st.index("MapSize") + 1]), int(st[st.index("MapSize") + 2])
    walk = np.zeros((h * 256, w * 256), bool)
    recs = []
    for s in sorted(os.listdir(root)):
        if not (len(s) == 6 and s.isdigit()):
            continue
        sx, sy = int(s[:3]), int(s[3:])
        a = root / s / "attr.atr"
        if a.is_file():
            walk[sy * 256:(sy + 1) * 256, sx * 256:(sx + 1) * 256] = \
                (read_attr(a).cells & 1) == 0
        p = root / s / "areadata.txt"
        if p.is_file():
            recs += AreaData.parse(p.read_bytes()).records
    return walk, recs


def _sample(grid_world, col, row):
    h, w = grid_world.shape
    c = np.floor(col).astype(int)
    r = np.floor(row).astype(int)
    ok = (c >= 0) & (c < w) & (r >= 0) & (r < h)
    out = np.zeros(c.shape, bool)
    out[ok] = grid_world[r[ok], c[ok]]
    return out, ok


#: A join lies at the piece's edge; a contact further in is an overlay
#: (`skipia_passis4` laid across a corridor), not a socket.
EDGE_CM = 600.0


def _edge_gap(lx, ly, side, lo, hi):
    return {"E": hi[0] - lx, "W": lx - lo[0], "N": hi[1] - ly, "S": ly - lo[1]}[side]


def _side_of(lx, ly, lo, hi):
    """Nearest bbox side of a local point."""
    d = {"E": hi[0] - lx, "W": lx - lo[0], "N": hi[1] - ly, "S": ly - lo[1]}
    return min(d, key=d.get)


def mine_kit(name, maps, corpus, objs, models, dec, verbose=True):
    sources = [(m, *load_map(corpus / m)) for m in maps]
    kinds = {}
    for _m, _w, recs in sources:
        for r in recs:
            o = objs.get(str(r.crc))
            kinds[r.crc] = o["property_type"] if o else "?"
    blocks = sorted({c for c, k in kinds.items() if k == "DungeonBlock"})

    pieces = {}
    for crc in blocks:
        o = objs[str(crc)]
        V, T = read_mesh(o["model_file"].replace("d:/ymir work", str(_paths().ymir_work)), dec)
        lo, hi = V[:, :2].min(0), V[:, :2].max(0)
        g = Grid.around(lo, hi)
        pieces[crc] = {"name": o["property_name"], "grid": g, "lo": lo, "hi": hi,
                       "floor": floor_mask(V, T, g), "height": float(V[:, 2].max() - V[:, 2].min()),
                       "seen": np.zeros(g.shape, np.int32), "open": np.zeros(g.shape, np.int32),
                       "inst": []}
    # A DungeonBlock with next to no floor of its own is not a piece but
    # something laid on one: `Mt_Thunder_passagepillar` (3 x 3 m, 132 at the
    # passage joints), the start-room pillars, `anglar_cavegate1_door`. Kept as
    # riders, so they come back as dressing or are recognised as doors.
    for crc in [c for c, p in pieces.items()
                if p["floor"].sum() < FLOOR_MIN_M2
                or np.prod((p["hi"] - p["lo"]) / RES) < FOOTPRINT_MIN_M2]:
        del pieces[crc]

    # -- walk: shipped attr sampled in each piece's frame ---------------------
    for m, walk, recs in sources:
        for r in recs:
            p = pieces.get(r.crc)
            if p is None:
                continue
            p["inst"].append((m, r))
            gx, gy = p["grid"].centres()
            col, row = place(gx, gy, r)
            v, ok = _sample(walk, col, row)
            p["seen"] += ok
            p["open"] += v

    # -- sockets: contact of two placed floors --------------------------------
    contacts = defaultdict(list)          # crc -> [(lx, ly, side, partner, width)]
    pairs = []                            # (map, rec_a, rec_b, world contact centroid)
    for m, walk, recs in sources:
        inst = [r for r in recs if r.crc in pieces]
        world = []
        for r in inst:
            p = pieces[r.crc]
            gx, gy = p["grid"].centres()
            col, row = place(gx[p["floor"]], gy[p["floor"]], r)
            world.append(set(zip(np.floor(col).astype(int).tolist(),
                                 np.floor(row).astype(int).tolist())))
        for a in range(len(inst)):
            # dilate A by one cell: two floors that butt share an edge, not a cell
            da = {(c + dc, r + dr) for c, r in world[a]
                  for dc, dr in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))}
            for b in range(len(inst)):
                if a == b:
                    continue
                touch = da & world[b]
                if len(touch) < 3:
                    continue
                cs = np.array(sorted(touch), float) + 0.5
                ra, pa = inst[a], pieces[inst[a].crc]
                lx, ly = unplace(cs[:, 0], cs[:, 1], ra)
                mx, my = float(np.mean(lx)), float(np.mean(ly))
                side = _side_of(mx, my, pa["lo"], pa["hi"])
                if _edge_gap(mx, my, side, pa["lo"], pa["hi"]) > EDGE_CM:
                    continue        # an overlay inside the piece, not a join
                along = ly if side in ("E", "W") else lx
                width = float(np.ptp(along) + RES)
                contacts[ra.crc].append((mx, my, side, inst[b].crc, width))
                if a < b:
                    pairs.append((ra, inst[b], float(cs[:, 0].mean()), float(cs[:, 1].mean())))

    # -- dressing: other records riding on a piece ----------------------------
    riders = defaultdict(list)             # crc -> [(instance, crc2, lx, ly, roll, droll, bias)]
    for m, walk, recs in sources:
        inst = [r for r in recs if r.crc in pieces]
        others = [r for r in recs if r.crc not in pieces]
        for o in others:
            best = None
            for r in inst:
                p = pieces[r.crc]
                lx, ly = unplace(o.x / RES, -o.y / RES, r)
                if p["lo"][0] - 50 <= lx <= p["hi"][0] + 50 and p["lo"][1] - 50 <= ly <= p["hi"][1] + 50:
                    d = math.hypot(lx - (p["lo"][0] + p["hi"][0]) / 2, ly - (p["lo"][1] + p["hi"][1]) / 2)
                    if best is None or d < best[0]:
                        best = (d, r, lx, ly)
            if best is None:
                continue
            _d, r, lx, ly = best
            col, row = int(o.x // RES), int(-o.y // RES)
            shut = bool(0 <= row < walk.shape[0] and 0 <= col < walk.shape[1]
                        and not walk[max(0, row - 1):row + 2, max(0, col - 1):col + 2].any())
            riders[r.crc].append((id(r), o.crc, lx, ly, int(round(o.roll)) % 360,
                                  int(round(o.roll - r.roll)) % 360, o.height_bias, shut))

    # -- assemble --------------------------------------------------------------
    out_pieces = {}
    for crc, p in pieces.items():
        n = len(p["inst"])
        prob = np.where(p["seen"] > 0, p["open"] / np.maximum(p["seen"], 1), 0.0)
        # A quarter, not a half: a spider room arm is barricaded in 55% of its
        # placements, and the arm is still floor the kit can open. The rim under
        # the wall foot is blocked in every placement and stays out at any
        # threshold.
        walk_mask = (prob >= WALK_SHARE) & p["floor"]
        socks = _cluster_sockets(contacts.get(crc, []), n, p["lo"], p["hi"])
        _true_lateral(socks, p["floor"], p["grid"])
        dressing = _cluster_riders(riders[crc], n, walk_mask, p["grid"])
        rolls = Counter(int(round(r.roll)) % 360 for _m, r in p["inst"])
        biases = Counter(int(round(r.height_bias)) for _m, r in p["inst"])
        out_pieces[str(crc)] = {
            "crc": crc, "name": p["name"], "count": n,
            "bbox": [round(float(v)) for v in (*p["lo"], *p["hi"])],
            "height": round(p["height"]),
            "rolls": dict(sorted(rolls.items())),
            "bias": biases.most_common(1)[0][0],
            "grid": p["grid"].to_json(),
            "floor": pack(p["floor"]), "walk": pack(walk_mask),
            "floor_m2": int(p["floor"].sum()), "walk_m2": int(walk_mask.sum()),
            "sockets": socks,
            "shape": _shape(socks, walk_mask),
            "dressing": dressing,
        }
    barricade = _mine_barricades(sources, pieces, out_pieces, kinds)
    joins = _join_overlap(pairs, out_pieces)
    layouts = {}
    for m, _w, recs in sources:
        layouts[m] = [[r.crc, round(r.x), round(-r.y), int(round(r.roll)) % 360,
                       round(r.height_bias)] for r in recs]
    loose = Counter()
    for m, _w, recs in sources:
        for r in recs:
            if r.crc not in pieces:
                loose[r.crc] += 1
    st = (corpus / maps[0] / "setting.txt").read_text(errors="replace").split()
    setting = {k: st[st.index(k) + 1] for k in ("TextureSet", "Environment") if k in st}
    kit = {"name": name, "maps": maps, "setting": setting,
           "pieces": out_pieces, "layouts": layouts,
           "barricade": barricade, "joins": joins,
           "riders": {str(c): {"count": k, "type": kinds.get(c),
                               "name": objs.get(str(c), {}).get("property_name")}
                      for c, k in loose.most_common()}}
    if verbose:
        print("%-15s %2d pieces  %s" % (name, len(out_pieces), ", ".join(
            "%s:%s/%d" % (v["name"], v["shape"], len(v["sockets"]))
            for v in out_pieces.values())))
    return kit


SIDE_DEG = {"E": 0, "N": 90, "W": 180, "S": 270}
OPPOSITE = {"E": "W", "W": "E", "N": "S", "S": "N"}


def _cluster_riders(rows, n_inst, walk_mask=None, grid=None, radius=150.0, min_share=1.0 / 3.0):
    """What rides on a piece: riders of one CRC within 1.5 m of each other in the
    piece frame, kept when a third of the placements carry one.

    A rider's roll is either turned with the piece (a cobweb across a mouth) or
    fixed in the world (an effect: `fire_general_obj_charcoal` is roll 0 on
    217 of 217 anglar placements whatever the corridor's roll), and that is
    read per cluster: ``absolute`` when the world roll is one value and the
    relative roll is not.
    """
    groups = []
    for inst, c2, lx, ly, roll, droll, bias, shut in rows:
        for g in groups:
            if g["crc"] == c2 and math.hypot(g["x"] - lx, g["y"] - ly) < radius:
                g["rows"].append((inst, lx, ly, roll, droll, bias, shut))
                break
        else:
            groups.append({"crc": c2, "x": lx, "y": ly,
                           "rows": [(inst, lx, ly, roll, droll, bias, shut)]})
    out = []
    for g in groups:
        k = len({r[0] for r in g["rows"]})
        if k < 2 or k < min_share * n_inst:
            continue
        a = np.array([r[1:] for r in g["rows"]], float)
        # A door: the rider is shut in the corpus attr where the piece it rides
        # is open (it stands in a corridor that is walkable in the placements
        # without it) -- `anglar_cavegate1_door`, 37 of 56 cavegates. Dungeon
        # logic, never dressing.
        if walk_mask is not None and a[:, 5].mean() > 0.8:
            j = int((np.median(a[:, 0]) - grid.x0) // RES)
            i = int((np.median(a[:, 1]) - grid.y0) // RES)
            if 0 <= i < grid.ny and 0 <= j < grid.nx and walk_mask[i, j]:
                continue
        rolls, drolls = Counter(a[:, 2].astype(int)), Counter(a[:, 3].astype(int))
        absolute = rolls.most_common(1)[0][1] > drolls.most_common(1)[0][1]
        out.append({"crc": g["crc"], "x": round(float(np.median(a[:, 0]))),
                    "y": round(float(np.median(a[:, 1]))),
                    "roll": int((rolls if absolute else drolls).most_common(1)[0][0]),
                    "absolute": bool(absolute),
                    "bias": round(float(np.median(a[:, 4])), 1),
                    "share": round(min(1.0, k / n_inst), 2)})
    out.sort(key=lambda d: -d["share"])
    return out


def socket_frame(sock, rec):
    """World (engine) point, outward normal and left lateral of a placed socket."""
    t = math.radians(rec.roll)
    c, s = math.cos(t), math.sin(t)
    px = rec.x + c * sock["x"] - s * sock["y"]
    py = rec.y + s * sock["x"] + c * sock["y"]
    a = math.radians(rec.roll + SIDE_DEG[sock["side"]])
    n = (math.cos(a), math.sin(a))
    return (px, py), n, (-n[1], n[0])


def _true_lateral(socks, floor, grid):
    """Put each socket on the axis of the floor that reaches its edge.

    The contact centroid lies on the band two floors share, which is offset
    from the corridor axis by up to 1.7 m (`WDC_01_cross_02` read 3,172 for an
    arm whose floor is centred on 3,000) -- enough that a run of 30 m pieces no
    longer meets the next junction. The floor run at the edge, inside the
    contact band, gives the axis to the 10 cm.
    """
    ny, nx = floor.shape
    for sk in socks:
        side = sk["side"]
        k = 3                                         # cells in from the edge
        if side == "E":
            line = floor[:, max(0, nx - k):].any(axis=1)
            coord0, along = grid.y0, sk["y"]
        elif side == "W":
            line = floor[:, :k].any(axis=1)
            coord0, along = grid.y0, sk["y"]
        elif side == "N":
            line = floor[max(0, ny - k):, :].any(axis=0)
            coord0, along = grid.x0, sk["x"]
        else:
            line = floor[:k, :].any(axis=0)
            coord0, along = grid.x0, sk["x"]
        i = int((along - coord0) // RES)
        if not (0 <= i < len(line)) or not line[i]:
            continue
        a = i
        while a > 0 and line[a - 1]:
            a -= 1
        b = i
        while b < len(line) - 1 and line[b + 1]:
            b += 1
        run = (b - a + 1) * RES
        if run > sk["width"] + 1200:
            continue      # the floor runs on along the side: a room wall, keep the contact
        mid = coord0 + (a + b + 1) / 2.0 * RES
        if side in ("E", "W"):
            sk["y"] = round(mid / 10.0) * 10
        else:
            sk["x"] = round(mid / 10.0) * 10
        sk["floor_width"] = round(run)


def _join_overlap(pairs, out_pieces):
    """How far two joined pieces run into each other, cm (positive = overlap).

    Measured socket to socket along the join: for each corpus contact, the
    socket of either piece nearest the contact, both carried into the world,
    and the distance between them along the first one's outward normal. The
    run solver accepts a run whose length lands inside this band.
    """
    vals = []
    for ra, rb, cx, cy in pairs:
        pa, pb = out_pieces.get(str(ra.crc)), out_pieces.get(str(rb.crc))
        if not pa or not pb or not pa["sockets"] or not pb["sockets"]:
            continue
        best = []
        for rec, pc in ((ra, pa), (rb, pb)):
            frames = [socket_frame(sk, rec) for sk in pc["sockets"]]
            best.append(min(frames, key=lambda f: math.hypot(f[0][0] / RES - cx, -f[0][1] / RES - cy)))
        (ax, ay), n, _t = best[0]
        (bx, by), _n, _t2 = best[1]
        vals.append(-((bx - ax) * n[0] + (by - ay) * n[1]))
    if not vals:
        return None
    v = np.array(vals)
    return {"n": len(v), "p5": round(float(np.percentile(v, 5))),
            "p50": round(float(np.percentile(v, 50))),
            "p95": round(float(np.percentile(v, 95)))}


def _mine_barricades(sources, pieces, out_pieces, kinds, reach=1200.0):
    """How a kit closes a built arm: the spider dungeons build every arm of a
    5x5 room grid and make the maze by shutting arms -- the arm's attr blocked
    from the socket inward, and a row of cobwebs (`ob-7-02-01`/`-02`) across
    the mouth. Measured per placed socket: shut when the walk 1-7 m inside it
    is under 30%; the depth is where the walk comes back; the template is the
    shut socket carrying the most riders, copied verbatim (rule 25) in the
    socket's frame -- ``u`` outward, ``v`` to the left, roll relative to the
    outward normal.
    """
    shut, depths, best = 0, [], None
    total = 0
    for m, walk, recs in sources:
        others = [r for r in recs if kinds.get(r.crc) != "DungeonBlock"]
        for r in recs:
            pc = out_pieces.get(str(r.crc))
            if pc is None:
                continue
            for sk in pc["sockets"]:
                (px, py), n, t = socket_frame(sk, r)
                total += 1

                def open_at(d):
                    vs = []
                    for lat in np.linspace(-sk["width"] / 3, sk["width"] / 3, 5):
                        x = px - n[0] * d + t[0] * lat
                        y = py - n[1] * d + t[1] * lat
                        col, row = int(x // RES), int(-y // RES)
                        if 0 <= row < walk.shape[0] and 0 <= col < walk.shape[1]:
                            vs.append(walk[row, col])
                    return float(np.mean(vs)) if vs else 0.0
                if np.mean([open_at(d) for d in range(100, 800, 100)]) >= 0.3:
                    continue
                shut += 1
                d = next((d for d in range(100, 6000, 100) if open_at(d) > 0.5), None)
                if d is not None:
                    depths.append(d)
                riders = []
                for o in others:
                    dx, dy = o.x - px, o.y - py
                    u, v = dx * n[0] + dy * n[1], dx * t[0] + dy * t[1]
                    if -(d or 0) - reach <= u <= reach and abs(v) <= sk["width"] / 2 + 300:
                        riders.append({"crc": o.crc, "u": round(u), "v": round(v),
                                       "roll": int(round(o.roll - r.roll - SIDE_DEG[sk["side"]])) % 360,
                                       "bias": round(o.height_bias, 1)})
                if riders and (best is None or len(riders) > len(best["records"])):
                    best = {"records": riders, "width": sk["width"],
                            "source": "%s %s %s" % (m, pc["name"], sk["side"])}
    if not shut:
        return None
    return {"shut_share": round(shut / max(total, 1), 2), "sockets_shut": shut,
            "depth_cm": int(np.median(depths)) if depths else None,
            "template": best}


def _cluster_sockets(cs, n_inst, lo, hi, radius=400.0):
    """Contacts in the piece frame, clustered; kept when used at least twice
    (once, for a piece placed once).

    Clustered by position alone: a cap's contact sits on a corner of its bbox
    and flips between two sides from one placement to the next
    (`maze_dungeon_cave04` read as a corner until this). The side is the
    majority, the axial coordinate is snapped to the bbox edge -- pieces abut
    edge to edge, `WDC_01_Line_0x` at exactly 30/60/90 m -- and the lateral one
    is rounded to 50 cm.
    """
    groups = []
    for lx, ly, side, partner, width in cs:
        for g in groups:
            # never across opposite sides: a 1 m seam cover (`skipia_passis4`)
            # has its two mouths 1.2 m apart and is still two mouths
            if math.hypot(g["x"] - lx, g["y"] - ly) < radius and                     OPPOSITE[side] != g["sides"].most_common(1)[0][0]:
                g["pts"].append((lx, ly, width))
                g["sides"][side] += 1
                g["partners"][partner] += 1
                break
        else:
            groups.append({"x": lx, "y": ly, "pts": [(lx, ly, width)],
                           "sides": Counter({side: 1}),
                           "partners": Counter({partner: 1})})
    out = []
    for g in groups:
        if len(g["pts"]) < min(2, n_inst):
            continue
        a = np.array(g["pts"])
        side = g["sides"].most_common(1)[0][0]
        x, y = float(np.median(a[:, 0])), float(np.median(a[:, 1]))
        edge = {"E": hi[0], "W": lo[0], "N": hi[1], "S": lo[1]}[side]
        if side in ("E", "W"):
            x = edge if abs(x - edge) < 2 * RES else x
            y = round(y / 50.0) * 50.0
        else:
            y = edge if abs(y - edge) < 2 * RES else y
            x = round(x / 50.0) * 50.0
        out.append({"side": side, "x": round(x), "y": round(y),
                    "width": round(float(np.median(a[:, 2])) / 100.0) * 100,
                    "used": len(g["pts"]),
                    "partners": {str(k): v for k, v in g["partners"].most_common()}})
    out.sort(key=lambda s: (SIDES.index(s["side"]), s["x"], s["y"]))
    return out


def _shape(socks, walk):
    sides = sorted({s["side"] for s in socks}, key=SIDES.index)
    k = len(socks)
    if k == 0:
        return "island"
    if k == 1:
        return "end"
    if k == 2:
        a, b = (SIDE_VEC[s["side"]] for s in socks)
        return "straight" if a[0] + b[0] == 0 and a[1] + b[1] == 0 else "corner"
    if k == 3:
        return "tee"
    if k == 4 and len(sides) == 4:
        return "cross"
    return "hub%d" % k


def sheet(kit: dict, out_png, scale=2):
    """Contact sheet of a kit: floor grey, walk green, sockets red, north up."""
    from PIL import Image, ImageDraw
    tiles = []
    for pc in sorted(kit["pieces"].values(), key=lambda p: -p["count"]):
        g = pc["grid"]
        shape = (g["ny"], g["nx"])
        fl, wk = unpack(pc["floor"], shape), unpack(pc["walk"], shape)
        img = np.zeros(shape + (3,), np.uint8)
        img[fl] = (90, 90, 90)
        img[wk] = (60, 190, 60)
        im = Image.fromarray(img[::-1]).resize((g["nx"] * scale, g["ny"] * scale), Image.NEAREST)
        d = ImageDraw.Draw(im)
        for sk in pc["sockets"]:
            px = (sk["x"] - g["x0"]) / RES * scale
            py = (g["ny"] - (sk["y"] - g["y0"]) / RES) * scale
            half = sk["width"] / RES * scale / 2
            if sk["side"] in ("E", "W"):
                d.line([(px, py - half), (px, py + half)], fill=(230, 40, 40), width=3)
            else:
                d.line([(px - half, py), (px + half, py)], fill=(230, 40, 40), width=3)
        ox, oy = -g["x0"] / RES * scale, (g["ny"] + g["y0"] / RES) * scale
        d.ellipse([ox - 4, oy - 4, ox + 4, oy + 4], outline=(255, 255, 0))
        lab = Image.new("RGB", (max(im.width, 120), im.height + 28), (16, 16, 16))
        lab.paste(im, (0, 28))
        ImageDraw.Draw(lab).text((2, 1), "%s x%d" % (pc["name"], pc["count"]), fill=(255, 255, 255))
        ImageDraw.Draw(lab).text((2, 14), "%s %dx%dm" % (pc["shape"], (pc["bbox"][2] - pc["bbox"][0]) / 100,
                                                       (pc["bbox"][3] - pc["bbox"][1]) / 100), fill=(200, 200, 120))
        tiles.append(lab)
    width = 1600
    rows, row, x = [], [], 0
    for t in tiles:
        if row and x + t.width > width:
            rows.append(row)
            row, x = [], 0
        row.append(t)
        x += t.width + 8
    rows.append(row)
    H = sum(max(t.height for t in r) + 8 for r in rows)
    W = max(sum(t.width + 8 for t in r) for r in rows)
    out = Image.new("RGB", (W, H), (0, 0, 0))
    y = 0
    for r in rows:
        x = 0
        for t in r:
            out.paste(t, (x, y))
            x += t.width + 8
        y += max(t.height for t in r) + 8
    out.save(out_png)


def layout_sheet(kit: dict, map_name: str, out_png, px_per_m=0.5):
    """A source map's layout redrawn from the kit alone: floor grey, walk green,
    riders yellow, north up -- the shape the generator learned from."""
    from PIL import Image
    recs = kit["layouts"][map_name]
    pcs = kit["pieces"]
    pts = []
    for crc, x, y, roll, _b in recs:
        pc = pcs.get(str(crc))
        if pc is None:
            continue
        x0, y0, x1, y1 = pc["bbox"]
        t = math.radians(roll)
        for lx, ly in ((x0, y0), (x0, y1), (x1, y0), (x1, y1)):
            pts.append((x + math.cos(t) * lx - math.sin(t) * ly,
                        -y + math.sin(t) * lx + math.cos(t) * ly))
    a = np.array(pts)
    ox, oy = a[:, 0].min() - 2000, a[:, 1].max() + 2000
    w = int((a[:, 0].max() - ox + 2000) / 100 * px_per_m) + 1
    h = int((oy - a[:, 1].min() + 2000) / 100 * px_per_m) + 1
    img = np.zeros((h, w, 3), np.uint8)
    for layer, colour in (("floor", (80, 80, 80)), ("walk", (50, 170, 50))):
        for crc, x, y, roll, _b in recs:
            pc = pcs.get(str(crc))
            if pc is None:
                continue
            g = pc["grid"]
            ii, jj = np.nonzero(unpack(pc[layer], (g["ny"], g["nx"])))
            lx, ly = g["x0"] + (jj + 0.5) * RES, g["y0"] + (ii + 0.5) * RES
            t = math.radians(roll)
            ex = x + math.cos(t) * lx - math.sin(t) * ly
            ey = -y + math.sin(t) * lx + math.cos(t) * ly
            c = ((ex - ox) / 100 * px_per_m).astype(int)
            r = ((oy - ey) / 100 * px_per_m).astype(int)
            ok = (c >= 0) & (c < w) & (r >= 0) & (r < h)
            img[r[ok], c[ok]] = colour
    for crc, x, y, _roll, _b in recs:
        if str(crc) not in pcs:
            c, r = int((x - ox) / 100 * px_per_m), int((oy + y) / 100 * px_per_m)
            if 0 <= r < h and 0 <= c < w:
                img[r, c] = (240, 220, 40)
    Image.fromarray(img).save(out_png)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(SKILL_ROOT / "reference" / "labyrinth" / "kits.json"))
    ap.add_argument("--kit", action="append", help="only these kits")
    ap.add_argument("--sheets", help="also write one contact-sheet PNG per kit here")
    a = ap.parse_args(argv)
    objs = json.loads((CATALOG / "objects.json").read_text(encoding="utf-8"))["objects"]
    models = json.loads((CATALOG / "models.json").read_text(encoding="utf-8"))["models"]
    dec = Decompressor(DEFAULTS["grn"])
    corpus = pathlib.Path(_paths().corpus)
    out = pathlib.Path(a.out)
    kits = {}
    if out.is_file() and a.kit:
        kits = json.loads(out.read_text(encoding="utf-8"))["kits"]
    for name, maps in KITS.items():
        if a.kit and name not in a.kit:
            continue
        kits[name] = mine_kit(name, maps, corpus, objs, models, dec)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"schema": 1, "res_cm": RES, "kits": kits},
                              separators=(",", ":")), encoding="utf-8")
    print("wrote", out)
    if a.sheets:
        pathlib.Path(a.sheets).mkdir(parents=True, exist_ok=True)
        for name, kit in kits.items():
            sheet(kit, pathlib.Path(a.sheets) / ("%s.png" % name))
            for m in kit["maps"]:
                layout_sheet(kit, m, pathlib.Path(a.sheets) / ("layout_%s.png" % m))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

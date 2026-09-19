"""Readapt a merged map: make several maps that were stitched side by side into
one place a player can walk through.

A merge (MapForge, or ``modes/merge.md``) copies every sector verbatim. That is
the right thing for a merge to do and it leaves three faults behind, all
measured on three 2x2 guild maps stacked 2x6:

* the shared border vertices disagree -- each sector kept its OWN edge, so at a
  join the two copies of one vertex differ by 25-40 m on average and the terrain
  renders with slits you can see the sky through;
* every source map brought its own sealed mountain ring, so each join is a
  double wall, 100% blocked for 40-80 m;
* every source map brought its own datum: the floors either side of one join sat
  9.4 m apart.

``readapt`` finds the source maps again from the tears, levels them, welds the
joins, cuts a pass through each double wall and paints a road along it.

Everything works on three whole-map grids and is written back through the same
``to_sector_raw`` splitters the generator uses, so borders and skirts agree by
construction. Only files whose bytes changed are rewritten.

Units: the vertex grid is world centimetres, the cell grid is 2 m, the tile grid
1 m. ``water.wtr`` and ``height.raw`` are RAW (cm / HeightScale) and converted
at the file boundary only (SKILL rule 18).
"""

from __future__ import annotations

import heapq
import json
import math
import pathlib
import shutil
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..audit import rules as audit_rules
from ..codec import areadata as ad_codec
from ..codec import attr as attr_codec
from ..codec import height as height_codec
from ..codec import server_attr as sa_codec
from ..codec import setting as setting_codec
from ..codec import textureset as ts_codec
from ..codec import tile as tile_codec
from ..codec import water as water_codec
from ..gen import terrain as terrain_gen
from ..gen import texture as texture_gen
from ..gen.layout import _distance_to, catmull_rom
from ..gen.walkable import reachable
from ..mine.attr_stats import label_components

CELLS = 128                 # terrain cells per sector edge
TILES = 256                 # tiles per sector edge
HS = height_codec.DEFAULT_HEIGHT_SCALE
ATTR_BLOCK = 0x01
ATTR_WATER = 0x02
DRY = -1

#: A border whose two copies of the shared vertices differ by more than this on
#: average was never one piece of terrain -- the same line the audit draws
#: (M2MAP-HGT-001). Merged borders measured 1,712 / 2,466 / 2,697 / 4,047 cm.
TEAR_CM = audit_rules.TORN_BORDER_CM

#: Floors closer than this are one datum already; the road takes up the rest.
LEVEL_MIN_CM = 100.0

#: Deepest slot a sound sector border holds: corpus c1 493, n_desert_01 452,
#: b1 293, a1 284 cm. The overlap join on map_merge_test_03 measured 4,486.
SLOT_MAX_CM = 1000.0


@dataclass
class Options:
    level: bool = True
    #: Walkable floor of the pass. Corpus cuts through mountain: 12 / 16 / 20 m.
    floor_m: float = 16.0
    road_m: float = 7.0
    #: Cells over which a weld offset fades into each sector.
    feather_cells: int = 16
    #: Run-out past each mouth, so the road arrives rather than stops at the wall.
    apron_m: float = 14.0
    #: Steepest longitudinal grade before the report complains. Corpus mountain
    #: cuts run 5-18%.
    max_grade_pct: float = 18.0
    #: How far past a mouth the road is painted on to reach the map's own road.
    #: Further than this the pass is simply somewhere roads are not.
    road_reach_m: float = 150.0
    seed: int = 1
    #: ``{block: slot}`` overrides for the road texture.
    road_slots: Dict[int, int] = field(default_factory=dict)


@dataclass
class Link:
    a: int
    b: int
    path: List[Tuple[int, int]]              # cells, (x, y), a -> b
    line: List[Tuple[float, float]] = field(default_factory=list)   # smoothed, cells
    mouth_a_cm: float = 0.0
    mouth_b_cm: float = 0.0
    wall_cells: int = 0
    water_cells: int = 0                     # of the path, over water: a causeway
    tree: bool = False                       # levelled flat; a spare link is not


# --------------------------------------------------------------------------
# load


class MergedMap:
    """Every layer of a map on disk, stitched into whole-map grids."""

    def __init__(self, root) -> None:
        self.root = pathlib.Path(root)
        self.setting = setting_codec.Setting.load(self.root / "setting.txt")
        names = sorted(p.name for p in self.root.iterdir()
                       if p.is_dir() and len(p.name) == 6 and p.name.isdigit())
        if not names:
            raise ValueError("%s has no sector folders (a proxy map?)" % root)
        self.W = max(int(n[:3]) for n in names) + 1
        self.H = max(int(n[3:]) for n in names) + 1
        if len(names) != self.W * self.H:
            raise ValueError("ragged sector grid: %d folders for %dx%d"
                             % (len(names), self.W, self.H))

        self.hfile: Dict[Tuple[int, int], height_codec.HeightMap] = {}
        self.hwin: Dict[Tuple[int, int], np.ndarray] = {}
        self.attr = np.zeros((self.H * TILES, self.W * TILES), np.uint8)
        self.tile = np.zeros((self.H * TILES, self.W * TILES), np.uint8)
        self.wraw = np.full((self.H * CELLS, self.W * CELLS), DRY, np.int64)
        self.wfile: Dict[Tuple[int, int], water_codec.WaterMap] = {}
        self.areas: Dict[Tuple[int, int], ad_codec.AreaData] = {}
        self.ambs: Dict[Tuple[int, int], ad_codec.AreaAmbienceData] = {}

        for sx, sy in self.sectors():
            d = self.sector_dir(sx, sy)
            hm = height_codec.read_height(d / "height.raw")
            self.hfile[sx, sy] = hm
            self.hwin[sx, sy] = hm.raw[1:130, 1:130].astype(np.float64) * HS
            ts, cs = self._tslice(sx, sy), self._cslice(sx, sy)
            self.attr[ts] = attr_codec.read_attr(d / "attr.atr").cells
            self.tile[ts] = tile_codec.read_tile(d / "tile.raw").tiles
            wm = water_codec.read_water(d / "water.wtr")
            self.wfile[sx, sy] = wm
            table = np.asarray(list(wm.heights) + [DRY], np.int64)
            idx = np.where(wm.cells < len(wm.heights), wm.cells, len(wm.heights))
            self.wraw[cs] = table[idx]
            if (d / "areadata.txt").exists():
                self.areas[sx, sy] = ad_codec.AreaData.load(d / "areadata.txt")
            if (d / "areaambiencedata.txt").exists():
                self.ambs[sx, sy] = ad_codec.AreaAmbienceData.load(d / "areaambiencedata.txt")

        self.attr0 = self.attr.copy()
        self.tile0 = self.tile.copy()
        self.wraw0 = self.wraw.copy()

    # -- geometry ----------------------------------------------------------
    def sectors(self):
        return [(sx, sy) for sy in range(self.H) for sx in range(self.W)]

    def sector_dir(self, sx: int, sy: int, root=None) -> pathlib.Path:
        return pathlib.Path(root or self.root) / ("%06u" % (sx * 1000 + sy))

    @staticmethod
    def _tslice(sx, sy):
        return (slice(sy * TILES, (sy + 1) * TILES), slice(sx * TILES, (sx + 1) * TILES))

    @staticmethod
    def _cslice(sx, sy):
        return (slice(sy * CELLS, (sy + 1) * CELLS), slice(sx * CELLS, (sx + 1) * CELLS))

    @staticmethod
    def _vslice(sx, sy):
        return (slice(sy * CELLS, sy * CELLS + 129), slice(sx * CELLS, sx * CELLS + 129))

    def stitch(self, windows=None) -> Tuple[np.ndarray, np.ndarray]:
        """``(mean, tear)`` on the vertex grid. A shared vertex has two or four
        owners; ``tear`` is how far apart they put it."""
        windows = windows or self.hwin
        shape = (self.H * CELLS + 1, self.W * CELLS + 1)
        acc, cnt = np.zeros(shape), np.zeros(shape)
        lo, hi = np.full(shape, np.inf), np.full(shape, -np.inf)
        for key, win in windows.items():
            vs = self._vslice(*key)
            acc[vs] += win
            cnt[vs] += 1
            lo[vs] = np.minimum(lo[vs], win)
            hi[vs] = np.maximum(hi[vs], win)
        return acc / cnt, hi - lo

    # -- the source maps, recovered from the tears --------------------------
    def torn_borders(self, tear: np.ndarray) -> List[Tuple[Tuple[int, int], Tuple[int, int], float]]:
        out = []
        for sx, sy in self.sectors():
            if sx + 1 < self.W:
                t = tear[sy * CELLS:sy * CELLS + 129, (sx + 1) * CELLS]
                if np.median(t) > TEAR_CM:
                    out.append(((sx, sy), (sx + 1, sy), float(t.mean())))
            if sy + 1 < self.H:
                t = tear[(sy + 1) * CELLS, sx * CELLS:sx * CELLS + 129]
                # Median, not mean: a border that merely ENDS on a torn one
                # shares its corner vertex, and one 40 m corner in 129 vertices
                # is a 30-60 cm mean on a border that is perfectly sound.
                if np.median(t) > TEAR_CM:
                    out.append(((sx, sy), (sx, sy + 1), float(t.mean())))
        return out

    def blocks(self, torn) -> Dict[Tuple[int, int], int]:
        """Sectors joined across every border that is NOT torn = one source map."""
        parent = {s: s for s in self.sectors()}

        def find(s):
            while parent[s] != s:
                parent[s] = parent[parent[s]]
                s = parent[s]
            return s

        cut = {(a, b) for a, b, _ in torn}
        for sx, sy in self.sectors():
            for nb in ((sx + 1, sy), (sx, sy + 1)):
                if nb in parent and ((sx, sy), nb) not in cut:
                    parent[find(nb)] = find((sx, sy))
        roots = sorted({find(s) for s in parent}, key=lambda s: (s[1], s[0]))
        return {s: roots.index(find(s)) for s in parent}


# --------------------------------------------------------------------------
# routing


def _cell_free(attr: np.ndarray) -> np.ndarray:
    """A 2 m cell is free when all four of its tiles are neither block nor water."""
    bad = (attr & (ATTR_BLOCK | ATTR_WATER)) != 0
    h, w = bad.shape
    return ~bad.reshape(h // 2, 2, w // 2, 2).any(axis=(1, 3))


def _cell_z(z: np.ndarray) -> np.ndarray:
    return (z[:-1, :-1] + z[:-1, 1:] + z[1:, :-1] + z[1:, 1:]) * 0.25


def route(free_a: np.ndarray, free_b: np.ndarray, region: np.ndarray,
          cost: np.ndarray) -> Optional[List[Tuple[int, int]]]:
    """Cheapest 8-connected path from floor ``a`` to floor ``b`` inside
    ``region``. Returns cells ``(x, y)`` starting ON ``a`` and ending ON ``b``."""
    h, w = region.shape
    dist = np.full((h, w), np.inf)
    prev = np.full((h, w, 2), -1, np.int32)
    rim = free_a & _grow8(~free_a)
    heap = []
    for y, x in zip(*np.nonzero(rim)):
        dist[y, x] = 0.0
        heap.append((0.0, int(y), int(x)))
    heapq.heapify(heap)
    steps = [(-1, -1, math.sqrt(2)), (-1, 0, 1.0), (-1, 1, math.sqrt(2)), (0, -1, 1.0),
             (0, 1, 1.0), (1, -1, math.sqrt(2)), (1, 0, 1.0), (1, 1, math.sqrt(2))]
    end = None
    while heap:
        d, y, x = heapq.heappop(heap)
        if d > dist[y, x]:
            continue
        if free_b[y, x]:
            end = (y, x)
            break
        for dy, dx, ln in steps:
            ny, nx = y + dy, x + dx
            if not (0 <= ny < h and 0 <= nx < w) or not region[ny, nx] or free_a[ny, nx]:
                continue
            nd = d + ln * cost[ny, nx]
            if nd < dist[ny, nx]:
                dist[ny, nx] = nd
                prev[ny, nx] = (y, x)
                heapq.heappush(heap, (nd, ny, nx))
    if end is None:
        return None
    path = []
    y, x = end
    while y >= 0:
        path.append((int(x), int(y)))
        y, x = prev[y, x]
    return path[::-1]


def _grow8(mask: np.ndarray) -> np.ndarray:
    out = mask.copy()
    out[1:, :] |= mask[:-1, :]
    out[:-1, :] |= mask[1:, :]
    out[:, 1:] |= out[:, :-1].copy()
    out[:, :-1] |= out[:, 1:].copy()
    return out


def _rdp(pts: Sequence[Tuple[float, float]], eps: float) -> List[Tuple[float, float]]:
    if len(pts) < 3:
        return list(pts)
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    dx, dy = x1 - x0, y1 - y0
    n = math.hypot(dx, dy) or 1.0
    best, idx = 0.0, 0
    for i in range(1, len(pts) - 1):
        d = abs(dy * (pts[i][0] - x0) - dx * (pts[i][1] - y0)) / n
        if d > best:
            best, idx = d, i
    if best <= eps:
        return [pts[0], pts[-1]]
    return _rdp(pts[:idx + 1], eps)[:-1] + _rdp(pts[idx:], eps)


def centreline(path: Sequence[Tuple[int, int]], apron_cells: float, rng=None
               ) -> Tuple[List[Tuple[float, float]], float, float]:
    """Smooth the cell path and run it out past both mouths.

    Returns ``(line, s_a, s_b)``: samples every half cell, and the arc lengths
    at which the pass proper starts and ends (outside them is apron)."""
    pts = [(x + 0.5, y + 0.5) for x, y in path]
    key = _rdp(pts, 3.0)
    if len(key) == 2 and rng is not None:
        # Uniform rock gives a ruler-straight cheapest path, and a ruled trench
        # is the one shape a hand-cut pass never has. Bend it into a shallow S.
        (x0, y0), (x1, y1) = key
        ln = math.hypot(x1 - x0, y1 - y0)
        if ln > 16.0:
            amp = min(5.0, ln / 9.0) * (1.0 if rng.random() < 0.5 else -1.0)
            nx, ny = -(y1 - y0) / ln, (x1 - x0) / ln
            key = [key[0],
                   (x0 + (x1 - x0) / 3 + nx * amp, y0 + (y1 - y0) / 3 + ny * amp),
                   (x0 + (x1 - x0) * 2 / 3 - nx * amp, y0 + (y1 - y0) * 2 / 3 - ny * amp),
                   key[1]]

    def extend(p, q):
        dx, dy = p[0] - q[0], p[1] - q[1]
        n = math.hypot(dx, dy) or 1.0
        return (p[0] + dx / n * apron_cells, p[1] + dy / n * apron_cells)

    far = lambda seq: seq[min(len(seq) - 1, 8)]                  # noqa: E731
    key = [extend(pts[0], far(pts))] + key + [extend(pts[-1], far(pts[::-1]))]
    dense = np.asarray(catmull_rom(key, samples_per_span=32))
    seg = np.hypot(*np.diff(dense, axis=0).T)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    even = np.arange(0.0, s[-1], 0.5)
    line = np.stack([np.interp(even, s, dense[:, 0]), np.interp(even, s, dense[:, 1])], 1)
    return [tuple(p) for p in line], float(apron_cells), float(s[-1] - apron_cells)


def line_field(shape, line: np.ndarray, scale: float, reach: float
               ) -> Tuple[np.ndarray, np.ndarray, Tuple[slice, slice]]:
    """Distance to the centreline and the index of the nearest sample, on a grid
    whose unit is ``1/scale`` cells, within ``reach`` cells of the line.

    ``line`` is in cells. Returns ``(dist_cells, index, window)``."""
    pts = line * scale
    r = reach * scale
    y0 = max(0, int(pts[:, 1].min() - r)); y1 = min(shape[0], int(pts[:, 1].max() + r) + 2)
    x0 = max(0, int(pts[:, 0].min() - r)); x1 = min(shape[1], int(pts[:, 0].max() + r) + 2)
    gy, gx = np.mgrid[y0:y1, x0:x1].astype(np.float64)
    best = np.full(gy.shape, np.inf)
    arg = np.zeros(gy.shape, np.int32)
    for i, (px, py) in enumerate(pts):
        d = (gx - px) ** 2 + (gy - py) ** 2
        m = d < best
        best[m] = d[m]
        arg[m] = i
    return np.sqrt(best) / scale, arg, (slice(y0, y1), slice(x0, x1))


def _value_noise(shape, period: int, rng) -> np.ndarray:
    """Smooth noise in -1..1 with features ``period`` samples across."""
    gh, gw = shape[0] // period + 3, shape[1] // period + 3
    g = rng.random((gh, gw)) * 2.0 - 1.0
    ys, xs = np.arange(shape[0]) / period, np.arange(shape[1]) / period
    y0, x0 = ys.astype(int), xs.astype(int)
    ty, tx = _smoothstep(ys - y0)[:, None], _smoothstep(xs - x0)[None, :]
    a, b = g[np.ix_(y0, x0)], g[np.ix_(y0, x0 + 1)]
    c, e = g[np.ix_(y0 + 1, x0)], g[np.ix_(y0 + 1, x0 + 1)]
    return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + e * tx) * ty


def _smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def bank_cm(x_m: np.ndarray) -> np.ndarray:
    """How far the ground may leave the floor level ``x_m`` metres off the floor
    edge. A soft 31 deg foot for 3 m, then ~61 deg: corpus cuts stand +5 m at
    6 m and +11-19 m at 10-12 m."""
    x = np.maximum(x_m, 0.0)
    return 100.0 * (0.6 * x + 1.2 * np.maximum(x - 3.0, 0.0))


# --------------------------------------------------------------------------
# the edit


def readapt(src, out, opt: Optional[Options] = None, overwrite: bool = False) -> dict:
    opt = opt or Options()
    rng = np.random.default_rng(opt.seed)
    m = MergedMap(src)
    report: dict = {"source": str(src), "out": str(out), "grid": [m.W, m.H]}

    # 1. the source maps ----------------------------------------------------
    z0, tear = m.stitch()
    torn = m.torn_borders(tear)
    block_of = m.blocks(torn)
    nblocks = max(block_of.values()) + 1
    report["torn_borders"] = [{"a": "%03d%03d" % a, "b": "%03d%03d" % b,
                               "mean_tear_cm": round(t)} for a, b, t in torn]
    report["blocks"] = {b: ["%03d%03d" % s for s in sorted(block_of) if block_of[s] == b]
                        for b in range(nblocks)}
    if nblocks < 2:
        report["note"] = "no torn border: this map is one piece, nothing to readapt"
        return report

    bcell = np.zeros((m.H * CELLS, m.W * CELLS), np.int32)
    for s, b in block_of.items():
        bcell[m._cslice(*s)] = b
    btile = bcell.repeat(2, 0).repeat(2, 1)

    zc0 = _cell_z(z0)
    wet = (m.wraw != DRY) & (m.wraw * HS > zc0)
    free = _cell_free(m.attr) & ~wet
    # Filler is not a source map: an L or a staggered merge is squared off with
    # blank sectors (no paint, no attr), and they get no pass, no vote in the
    # weld and no share of the seam dither.
    void = [b for b in range(nblocks) if not m.tile[btile == b].any()]
    report["void_blocks"] = void
    # What a player can WALK is everything not blocked: c1's river carries the
    # water flag and no block -- it is forded, and bridged -- so "free and dry"
    # cut that map into three floors and sent a pass 850 m across open ground
    # from the largest one. The floor is one component of unblocked TILES (a
    # bridge deck is narrower than a cell); the pass still starts and ends dry.
    walk = (m.attr & ATTR_BLOCK) == 0
    floors = []
    for b in range(nblocks):
        comp = _largest(walk & (btile == b))
        floors.append(comp.reshape(comp.shape[0] // 2, 2, -1, 2).all(axis=(1, 3)))
    dry = free

    # 2. one pass per pair of neighbouring source maps -----------------------
    pairs = sorted({tuple(sorted((block_of[a], block_of[b]))) for a, b, _ in torn
                    if block_of[a] != block_of[b]
                    and block_of[a] not in void and block_of[b] not in void})
    links: List[Link] = []
    for a, b in pairs:
        seam = np.zeros(bcell.shape, bool)
        for sa, sb, _ in torn:
            if {block_of[sa], block_of[sb]} == {a, b}:
                (ax, ay), (bx, by) = sa, sb
                if ax != bx:
                    seam[ay * CELLS:(ay + 1) * CELLS, bx * CELLS - 1:bx * CELLS + 1] = True
                else:
                    seam[by * CELLS - 1:by * CELLS + 1, ax * CELLS:(ax + 1) * CELLS] = True
        near = _distance_to(seam, cap=96.0) < 96.0
        rel = np.zeros_like(zc0)
        for blk in (a, b):
            f = floors[blk] & near
            ref = np.median(zc0[f]) if f.any() else np.median(zc0[floors[blk]])
            rel[bcell == blk] = zc0[bcell == blk] - ref
        # Cutting rock costs by how much rock; water is nearly a wall; a second
        # floor that is not the target costs nothing extra.
        cost = np.where(free, 1.0, 3.0 + np.maximum(rel, 0.0) / 300.0)
        cost = np.where(wet | _cell_attr(m.attr, ATTR_WATER), 60.0, cost)
        # A floor is left and entered on dry ground; its fords are not a mouth.
        region = ((bcell == a) | (bcell == b)) & ~((floors[a] | floors[b]) & ~dry)
        path = route(floors[a] & dry, floors[b] & dry, region, cost)
        if path is None:
            report.setdefault("problems", []).append("no route between blocks %d and %d" % (a, b))
            continue
        lk = Link(a, b, path)
        lk.wall_cells = sum(1 for x, y in path if not free[y, x])
        over = wet | _cell_attr(m.attr, ATTR_WATER)
        lk.water_cells = sum(1 for x, y in path if over[y, x])
        lk.mouth_a_cm = _mouth(zc0, floors[a] & dry, path[0])
        lk.mouth_b_cm = _mouth(zc0, floors[b] & dry, path[-1])
        links.append(lk)

    # 3. one datum -----------------------------------------------------------
    delta = {b: 0.0 for b in range(nblocks)}
    # Three maps that all touch make a cycle, and a block has ONE datum: two
    # links can be levelled flat, the third gets whatever is left. Level along
    # the tree of thinnest walls; step 5 keeps a spare link only if it comes out
    # walkable.
    ref = int(np.argmax([0 if b in void else f.sum() for b, f in enumerate(floors)]))
    seen = {ref}
    while True:
        edge = [lk for lk in links if (lk.a in seen) != (lk.b in seen)]
        if not edge:
            break
        lk = min(edge, key=lambda e: e.wall_cells)
        lk.tree = True
        for me, other, zm, zo in ((lk.a, lk.b, lk.mouth_a_cm, lk.mouth_b_cm),
                                  (lk.b, lk.a, lk.mouth_b_cm, lk.mouth_a_cm)):
            if me in seen and other not in seen and opt.level:
                # Level to the ground the road JOINS -- the two mouths --
                # and to nothing wider. The map's median is wrong on a
                # tiered map (guild_01: 21 m off), and the commonest
                # floor within 120 m is wrong on rolling ground: between
                # desert dunes and a volcano's flank it left the mouths
                # 13 m apart and the pass at 26%.
                d = (zm + delta[me]) - zo
                delta[other] = round(d / HS) * HS if abs(d) >= LEVEL_MIN_CM else 0.0
        seen |= {lk.a, lk.b}
    # Filler has no floor to level to: it follows the borders it shares.
    for v in void:
        gaps = []
        for sa, sb, _ in torn:
            for mine, nb in ((sa, sb), (sb, sa)):
                if block_of[mine] == v and block_of[nb] not in void:
                    wm, wn = m.hwin[mine], m.hwin[nb] + delta[block_of[nb]]
                    if mine[0] != nb[0]:
                        e_m, e_n = (wm[:, -1], wn[:, 0]) if mine[0] < nb[0] else (wm[:, 0], wn[:, -1])
                    else:
                        e_m, e_n = (wm[-1], wn[0]) if mine[1] < nb[1] else (wm[0], wn[-1])
                    gaps.append(e_n - e_m)
        if gaps and opt.level:
            delta[v] = round(float(np.median(np.concatenate(gaps))) / HS) * HS
    report["level_cm"] = {b: delta[b] for b in range(nblocks)}

    windows = {s: m.hwin[s] + delta[block_of[s]] for s in m.hwin}
    for s, b in block_of.items():
        if delta[b]:
            cs = m._cslice(*s)
            w = m.wraw[cs]
            m.wraw[cs] = np.where(w == DRY, DRY, w + int(round(delta[b] / HS)))

    # 4. weld ------------------------------------------------------------------
    void_keys = {s for s, b in block_of.items() if b in void}
    # How far each cell is from walkable ground OF ITS OWN MAP. Measured across
    # the join, a1's floor 2 m away made the foot of b1's ring "ground we must
    # not reshape", and the two sides tied.
    near = np.full(free.shape, 8.0)
    for b in range(nblocks):
        if b not in void:
            mine = bcell == b
            near[mine] = _distance_to(free & mine, cap=8.0)[mine]
    z_mean = _weld_target(m, windows, near, void_keys)
    z = _weld(m, windows, z_mean, near, opt.feather_cells, void_keys)
    _fill_slots(z, torn)

    # 5. carve, open, paint ------------------------------------------------------
    hw = opt.floor_m / 2.0
    slots = _slots(m, btile, nblocks, opt, report, wet)
    # Filler's "ground" is slot 0, the eraser: painted from, it punches blank
    # holes in the road wherever a pass crosses a join.
    slots = {b: v for b, v in slots.items() if b not in void}
    removed_mask = np.zeros(m.attr.shape, bool)
    report["seam_tiles_dithered"] = _blend_seam(m.tile, btile, rng)
    for lk in links:
        line, s_a, s_b = centreline(lk.path, opt.apron_m / 2.0, rng)
        arr = np.asarray(line)
        s = np.arange(len(arr)) * 0.5
        za, zb = lk.mouth_a_cm + delta[lk.a], lk.mouth_b_cm + delta[lk.b]
        if not lk.tree and abs(zb - za) / max((s_b - s_a) * 2.0, 1.0) > opt.max_grade_pct:
            report.setdefault("skipped_links", []).append({
                "blocks": [lk.a, lk.b], "mouths_cm": [round(za), round(zb)],
                "why": "both maps are already joined through a third, and this "
                       "pass would climb %.0f%%" % (abs(zb - za) / max((s_b - s_a) * 2.0, 1.0))})
            continue
        lk.line = line
        target = za + (zb - za) * _smoothstep((s - s_a) / max(s_b - s_a, 1.0))

        d, idx, win = line_field(z.shape, arr, 1.0, hw / 2.0 + 24.0)
        # Walls that wander: the floor edge moves +-2 m and the batter +-25%.
        rough = _value_noise(d.shape, 6, rng)
        bk = bank_cm(d * 2.0 - hw - 2.0 * rough) * (1.0 + 0.25 * _value_noise(d.shape, 9, rng))
        t = target[idx]
        z[win] = np.clip(z[win], t - bk, t + bk)

        dt, _, wt = line_field(m.attr.shape, arr, 2.0, hw / 2.0 + 4.0)
        dm = dt * 2.0                                         # metres
        floor = dm <= hw - 1.0
        a_win = m.attr[wt]
        a_win[floor] &= np.uint8(~(ATTR_BLOCK | ATTR_WATER) & 0xFF)
        removed_mask[wt] |= dm <= hw + 1.0
        _paint(m.tile[wt], btile[wt], dm, hw, opt.road_m / 2.0, slots, rng)

        # A pass ends where the wall was thinnest, which is rarely where the
        # map's road is: paint on, over open floor, to the nearest one.
        reach = []
        for blk, cell in ((lk.a, lk.path[0]), (lk.b, lk.path[-1])):
            reach.append(_join_road(m, floors[blk] & dry, cell, slots[blk], btile, slots,
                                    opt, rng))

        length_m = (s_b - s_a) * 2.0
        grade = abs(zb - za) / max(length_m, 1.0)
        report.setdefault("links", []).append({
            "blocks": [lk.a, lk.b],
            "from_tile": [lk.path[0][0] * 2, lk.path[0][1] * 2],
            "to_tile": [lk.path[-1][0] * 2, lk.path[-1][1] * 2],
            "length_m": round(length_m, 1), "wall_m": lk.wall_cells * 2,
            "mouths_cm": [round(za), round(zb)], "grade_pct": round(grade, 1),
            "road_joined_m": reach, "water_m": lk.water_cells * 2,
        })
        if lk.water_cells:
            # Water costs 60x, so this was the only way through. It is filled,
            # not bridged: no merged map has needed a bridge yet, and a fit built
            # without one to render would be a guess (rule 27 has the measured
            # one, for a person to place).
            report.setdefault("notes", []).append(
                "link %d-%d crosses %d m of water on a causeway: a bridge there is a "
                "`bridges:`-style fit by hand (reference/structures.md sec 5)"
                % (lk.a, lk.b, lk.water_cells * 2))
        if grade > opt.max_grade_pct:
            report.setdefault("problems", []).append(
                "link %d-%d climbs %.0f%% (corpus cuts 5-18%%): level the blocks or lengthen the pass"
                % (lk.a, lk.b, grade))

    # No plane may stand over the new floor.
    zc = _cell_z(z)
    flooded = (m.wraw != DRY) & (m.wraw * HS > zc) & \
        removed_mask.reshape(removed_mask.shape[0] // 2, 2, -1, 2).any(axis=(1, 3)) & ~wet
    m.wraw[flooded] = DRY
    report["water_cells_dried"] = int(flooded.sum())

    # 6. objects ride the ground ---------------------------------------------------
    report["objects"] = _reseat(m, windows, z, delta, block_of, removed_mask)

    # 7. cross the boundary: is it one floor now? ----------------------------------
    whole = _largest(((m.attr & ATTR_BLOCK) == 0) & ~np.isin(btile, void))
    whole = whole.reshape(whole.shape[0] // 2, 2, -1, 2).all(axis=(1, 3))
    report["joined"] = {b: bool((whole & floors[b]).sum() > 0.9 * floors[b].sum())
                        for b in range(nblocks) if b not in void}

    # 8. write ---------------------------------------------------------------------
    report["written"] = _write(m, z, out, overwrite)
    report["tear_after_cm"] = _tear_on_disk(out)
    back = MergedMap(out)
    report["join_slot_cm"] = _join_slot(back, torn, block_of, void)
    if report["join_slot_cm"] > SLOT_MAX_CM:
        report.setdefault("problems", []).append(
            "a join is a slot %d cm deep: the border row is lower than the ground on BOTH "
            "sides of it" % report["join_slot_cm"])
    report["blank_tiles_added"] = int(((back.tile == 0) & (m.tile0 != 0)).sum())
    if report["blank_tiles_added"]:
        report.setdefault("problems", []).append(
            "%d painted tiles became slot 0 (blank)" % report["blank_tiles_added"])
    report["server_attr"] = _server_attr_on_disk(out, back)
    if not report["server_attr"]["agrees"]:
        report.setdefault("problems", []).append("server_attr disagrees with attr.atr")
    # Nothing here bakes either; WorldEditorRemix does, on F6.
    report["shadowmap_minimap"] = ("stale: open in WorldEditorRemix and press F6"
                                   if report["written"] else "unchanged")
    _previews(m, z0, z, links, pathlib.Path(out) / "_preview")
    (pathlib.Path(out) / "_readapt.json").write_text(json.dumps(report, indent=1), "ascii")
    return report


def _largest(mask: np.ndarray) -> np.ndarray:
    """The largest 4-connected component of ``mask``."""
    lab, n = label_components(mask, 4)
    if not n:
        return np.zeros_like(mask)
    return lab == int(np.argmax(np.bincount(lab.ravel())[1:])) + 1


def _cell_attr(attr: np.ndarray, flag: int) -> np.ndarray:
    a = (attr & flag) != 0
    return a.reshape(a.shape[0] // 2, 2, -1, 2).any(axis=(1, 3))


def _mouth(zc: np.ndarray, floor: np.ndarray, cell: Tuple[int, int], r: int = 8) -> float:
    x, y = cell
    ys, xs = slice(max(0, y - r), y + r + 1), slice(max(0, x - r), x + r + 1)
    f = floor[ys, xs]
    return float(np.median(zc[ys, xs][f])) if f.any() else float(zc[y, x])


def _weld_target(m: MergedMap, windows, near: np.ndarray, void_keys=()) -> np.ndarray:
    """What each shared vertex becomes: the mean of its owners, with walkable
    ground outvoting rock 50 to 1.

    Two sealed maps meet wall to wall and the plain mean is right. A map with an
    OPEN edge (n_desert_01 has no ring) brings its floor to the join, and a plain
    mean would lift that floor half-way up the neighbour's cliff in one row.
    Filler has no vote: it is all "walkable", and would drag a real map's ring
    down to its own blank plane."""
    shape = (m.H * CELLS + 1, m.W * CELLS + 1)
    acc, wsum = np.zeros(shape), np.zeros(shape)
    # The vote goes to every cell the fade in `_weld` will refuse to reshape --
    # walkable ground AND the 12 m round it -- not to walkable cells alone. An
    # overlap crops a map through its interior: a1's cut edge is floor, banks and
    # river at 238 m against the foot of b1's ring face at 145-157 m. The rock
    # and water ON that edge had no vote, the mean came out at 189 m, a1's side
    # would not move, and the join became a slot 45 m deep and one cell wide.
    held = near < 6.0
    for key, win in windows.items():
        f = held[m._cslice(*key)]
        v = np.zeros((129, 129), bool)
        v[:-1, :-1] |= f
        v[1:, :-1] |= f
        v[:-1, 1:] |= f
        v[1:, 1:] |= f
        w = np.where(v, 1.0, 0.02) if key not in void_keys else np.full((129, 129), 1e-6)
        vs = m._vslice(*key)
        acc[vs] += win * w
        wsum[vs] += w
    return acc / wsum


def _weld(m: MergedMap, windows, z_mean: np.ndarray, near: np.ndarray, n: int,
          void_keys=()) -> np.ndarray:
    """Pull each sector's border onto the shared value and fade the pull out over
    ``n`` cells, so a 40 m tear becomes a slope and not a spike.

    The fade stops short of walkable ground -- the wall is ours to reshape, the
    floor is not -- except on the border row itself, which must close."""
    k = np.arange(129, dtype=np.float64)
    f_lo = _smoothstep(1.0 - k / n)               # weight of the row-0 / col-0 edge
    f_hi = f_lo[::-1]
    guard = np.clip(near / 6.0, 0.0, 1.0)
    out = np.zeros_like(z_mean)
    cnt = np.zeros_like(z_mean)
    for key, win in windows.items():
        vs = m._vslice(*key)
        want = z_mean[vs]
        dt, db = want[0] - win[0], want[-1] - win[-1]
        dl, dr = want[:, 0] - win[:, 0], want[:, -1] - win[:, -1]
        num = (dt[None, :] * f_lo[:, None] + db[None, :] * f_hi[:, None]
               + dl[:, None] * f_lo[None, :] + dr[:, None] * f_hi[None, :])
        den = (f_lo[:, None] + f_hi[:, None] + f_lo[None, :] + f_hi[None, :])
        pull = num / np.maximum(den, 1.0)
        g = np.ones((129, 129))
        cs = m._cslice(*key)
        if key not in void_keys:                   # filler has no floor to spare
            g[:128, :128] = guard[cs]
        g[0, :] = g[-1, :] = 1.0
        g[:, 0] = g[:, -1] = 1.0
        out[vs] += win + pull * g
        cnt[vs] += 1
    return out / cnt


def _fill_slots(z: np.ndarray, torn) -> None:
    """A join row is never left lower than BOTH rows beside it.

    A map's outermost row plunges -- c1's edge stands 31 m below the row inside
    it -- so two rings meet in a ditch between two ridges, and the mean of two
    plunging edges is the bottom of it. The fade moves each side by what its
    edge moved, which keeps the plunge. One shared row is raised, so the skirts
    still agree."""
    for a, b, _t in torn:
        (ax, ay), (bx, by) = a, b
        if ax != bx:
            c, rows = bx * CELLS, slice(ay * CELLS, ay * CELLS + 129)
            z[rows, c] = np.maximum(z[rows, c], np.minimum(z[rows, c - 1], z[rows, c + 1]))
        else:
            r, cols = by * CELLS, slice(ax * CELLS, ax * CELLS + 129)
            z[r, cols] = np.maximum(z[r, cols], np.minimum(z[r - 1, cols], z[r + 1, cols]))


def _slots(m: MergedMap, btile: np.ndarray, nblocks: int, opt: Options, report: dict,
           wet: Optional[np.ndarray] = None):
    """Per source map: the ground slot, the cliff slots and a road slot, read off
    how the map itself is painted -- a merged palette is a union, and block 0's
    grass is not block 1's."""
    names = {}
    for cand in (m.root / m.setting.texture_set_path.replace("\\", "/"),
                 m.root / "textureset" / pathlib.PureWindowsPath(m.setting.texture_set).name):
        if cand.exists():
            ts = ts_codec.TextureSet.load(cand)
            names = {i: (e.filename if e else "") for i, e in enumerate(ts.slots)}
            break
    blocked = (m.attr & ATTR_BLOCK) != 0
    shore = np.zeros(m.tile.shape, bool)
    if wet is not None and wet.any():
        shore = _distance_to(wet.repeat(2, 0).repeat(2, 1), cap=12.0) < 10.0
    out = {}
    for b in range(nblocks):
        sel = btile == b
        n_all = np.bincount(m.tile[sel], minlength=256).astype(np.float64)
        n_blk = np.bincount(m.tile[sel & blocked], minlength=256).astype(np.float64)
        n_free = n_all - n_blk
        ground = int(np.argmax(n_free))
        with np.errstate(invalid="ignore", divide="ignore"):
            p_blk = np.where(n_all > 0, n_blk / n_all, 0.0)
        cliff = [i for i in range(1, 256) if n_all[i] > 0.01 * sel.sum() and p_blk[i] >= 0.75]
        road = opt.road_slots.get(b)
        if road is None:
            share = n_free / max(1.0, n_free.sum())
            cands = [i for i in np.argsort(share)[::-1]
                     if i and i != ground and i not in cliff and share[i] >= 0.02]
            fields = [i for i in cands if texture_gen.motif_of(names.get(i, "")) == "field"]
            # Not the most-used one: on b1, c1 and a1 that is `field 04`, a third
            # of it the band round the water, while the roads are `field 01` at
            # 3-8% of the map. A road is SOLID, WALKABLE and AWAY FROM WATER, and
            # the product picks field 01 on all three (0.49-0.56 against
            # 0.21-0.38).
            road = int(max(fields or cands or [ground],
                           key=lambda i: _roadness(m.tile, i, sel, blocked, shore)))
        out[b] = {"ground": ground, "cliff": cliff, "road": int(road)}
    report["slots"] = {b: dict(v, names={k: names.get(v[k], "") for k in ("ground", "road")})
                       for b, v in out.items()}
    return out


def _roadness(tile: np.ndarray, slot: int, sel: np.ndarray, blocked: np.ndarray,
              shore: np.ndarray) -> float:
    t = (tile == slot) & sel
    n = int(t.sum())
    if not n:
        return 0.0
    same = t.copy()
    same[1:, :] &= t[:-1, :]
    same[:-1, :] &= t[1:, :]
    same[:, 1:] &= t[:, :-1]
    same[:, :-1] &= t[:, 1:]
    return float(same.sum() / n * (1.0 - blocked[t].mean()) * (1.0 - shore[t].mean()))


def _blend_seam(tile: np.ndarray, btile: np.ndarray, rng, reach: int = 12) -> int:
    """Dither the two palettes into each other for ``reach`` metres either side
    of every join. Wall to wall nobody sees the join; where an open-edged map
    meets its neighbour the merge leaves sand against lava rock along a ruled
    line 1.5 km long, and nothing in the corpus is painted with a ruler."""
    seam = np.zeros(btile.shape, bool)
    seam[:, 1:] |= btile[:, 1:] != btile[:, :-1]
    seam[:, :-1] |= btile[:, 1:] != btile[:, :-1]
    seam[1:, :] |= btile[1:, :] != btile[:-1, :]
    seam[:-1, :] |= btile[1:, :] != btile[:-1, :]
    d = _distance_to(seam, cap=float(reach))
    ys, xs = np.nonzero(d < reach)
    # Borrow from a tile up to ``reach`` away; it counts only if it lies in the
    # OTHER source map, and less often the further this tile is from the join.
    sy = np.clip(ys + rng.integers(-reach, reach + 1, ys.size), 0, tile.shape[0] - 1)
    sx = np.clip(xs + rng.integers(-reach, reach + 1, xs.size), 0, tile.shape[1] - 1)
    fade = 0.9 * (1.0 - d[ys, xs] / reach)
    take = (btile[sy, sx] != btile[ys, xs]) & (rng.random(ys.size) < fade)
    src = tile.copy()
    # Slot 0 is the eraser (rule 8): filler is blank, and blank is not a palette.
    take &= (src[sy, sx] != 0) & (src[ys, xs] != 0)
    tile[ys[take], xs[take]] = src[sy[take], sx[take]]
    return int(take.sum())


def _paint(tile: np.ndarray, btile: np.ndarray, dm: np.ndarray, hw: float, road_hw: float,
           slots, rng) -> None:
    """Road solid in the core and dithered for ~3 m at its rim (rule 19); the
    rest of the new floor takes the block's own ground wherever it was rock."""
    noise = rng.random(tile.shape)
    # Blur which block a tile belongs to for ~8 m across the join, so the two
    # palettes hand over in a dither rather than along a ruled line.
    gy = np.gradient(btile.astype(np.float64), axis=0) != 0
    gx = np.gradient(btile.astype(np.float64), axis=1) != 0
    seam_d = _distance_to(gy | gx, cap=10.0)
    for b, sl in slots.items():
        mine = btile == b
        other = (~mine) & (seam_d < 8.0) & (rng.random(tile.shape) < 0.5 * (1.0 - seam_d / 8.0))
        own = (mine & ~((seam_d < 8.0) & (noise > 0.5 + 0.5 * seam_d / 8.0))) | other
        cliff = np.isin(tile, sl["cliff"])
        floor = own & (dm <= hw) & cliff & (noise < np.clip((hw + 1.5 - dm) / 2.5, 0.0, 1.0))
        tile[floor] = sl["ground"]
        p_road = np.clip((road_hw + 3.0 - dm) / 3.0, 0.0, 1.0)
        tile[own & (rng.random(tile.shape) < p_road)] = sl["road"]


def _road_cells(tile: np.ndarray, slot: int) -> np.ndarray:
    """Cells on a real road: solid in the slot, in a 10 m neighbourhood at least
    70% of it. Ground is a stipple (rule 11) and the road slot turns up in it a
    tile at a time -- the guild maps have patches of it at ~50% and no road at
    all, and at 40% the pass was painted 126 m to one of them. A road is solid
    (rule 19)."""
    on = (tile == slot).reshape(tile.shape[0] // 2, 2, -1, 2).mean(axis=(1, 3))
    c = np.pad(on, 3, mode="edge").cumsum(0).cumsum(1)
    c = np.pad(c, ((1, 0), (1, 0)))
    k = 5
    box = (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)
    box = box[1:1 + on.shape[0], 1:1 + on.shape[1]]
    return (on >= 1.0) & (box >= 0.7)


def _join_road(m: "MergedMap", floor: np.ndarray, cell: Tuple[int, int], slot: dict,
               btile: np.ndarray, slots, opt: Options, rng) -> Optional[float]:
    """Paint the road from a mouth to the block's nearest existing road, over
    walkable dry floor only. Paint and nothing else: no carve, no attr, nothing
    removed -- the ground there is already the map's own. Returns the metres
    painted, 0.0 when the mouth is on a road already, None when no road is
    within reach."""
    roads = _road_cells(m.tile0, slot["road"]) & floor
    if not roads.any():
        return None
    x, y = cell
    r = int(opt.road_reach_m / 2.0)
    ys, xs = slice(max(0, y - r), y + r + 1), slice(max(0, x - r), x + r + 1)
    start = np.zeros(floor.shape, bool)[ys, xs]
    start[y - ys.start, x - xs.start] = True
    path = route(start, roads[ys, xs] & ~start, floor[ys, xs] | start, np.ones(start.shape))
    if path is None or len(path) * 2.0 > opt.road_reach_m:
        return None
    if len(path) < 5:
        return 0.0
    path = [(px + xs.start, py + ys.start) for px, py in path]
    line, _, _ = centreline(path, 0.0)
    dt, _, wt = line_field(m.attr.shape, np.asarray(line), 2.0, opt.road_m / 2.0 + 4.0)
    _paint(m.tile[wt], btile[wt], dt * 2.0, 0.0, opt.road_m / 2.0, slots, rng)
    return round(len(path) * 2.0, 1)


def _bilinear(grid: np.ndarray, x_cm: float, y_cm: float) -> float:
    fx, fy = x_cm / 200.0, y_cm / 200.0
    x0 = int(np.clip(math.floor(fx), 0, grid.shape[1] - 2))
    y0 = int(np.clip(math.floor(fy), 0, grid.shape[0] - 2))
    tx, ty = np.clip(fx - x0, 0, 1), np.clip(fy - y0, 0, 1)
    return float(grid[y0, x0] * (1 - tx) * (1 - ty) + grid[y0, x0 + 1] * tx * (1 - ty)
                 + grid[y0 + 1, x0] * (1 - tx) * ty + grid[y0 + 1, x0 + 1] * tx * ty)


def _reseat(m: MergedMap, windows, z: np.ndarray, delta, block_of, removed_mask) -> dict:
    """``z`` moves by exactly what the ground under the record moved. The height
    bias is the author's offset FROM the ground and stays as written."""
    stats = {"moved": 0, "removed": 0, "stray": 0, "max_move_cm": 0.0}
    # One before-grid per source map: a record may sit a few metres outside the
    # sector whose file lists it, but never outside its own map.
    befores = {}
    for b in set(block_of.values()):
        own = {s: m.hwin[s] for s in m.hwin if block_of[s] == b}
        grid = np.zeros_like(z)
        for s, win in own.items():
            grid[m._vslice(*s)] = win
        befores[b] = grid
    for files in (m.areas, m.ambs):
        for key, area in files.items():
            sx, sy = key
            # What this sector's ground was BEFORE, datum shift excluded, so the
            # difference carries level + weld + carve in one number.
            before = befores[block_of[key]]
            keep = []
            for r in area.records:
                tx, ty = int(r.x // 100), int(-r.y // 100)
                inside = 0 <= ty < removed_mask.shape[0] and 0 <= tx < removed_mask.shape[1]
                if inside and removed_mask[ty, tx] and files is m.areas:
                    stats["removed"] += 1
                    continue
                if inside and block_of[tx // TILES, ty // TILES] == block_of[key]:
                    dz = _bilinear(z, r.x, -r.y) - _bilinear(before, r.x, -r.y)
                else:
                    # Listed by one source map, standing in another (or off the
                    # map): there is no ground of its own to follow.
                    dz = delta[block_of[key]]
                    stats["stray"] += 1
                if abs(dz) >= 0.5:
                    r.z = r.z + dz
                    stats["moved"] += 1
                    stats["max_move_cm"] = max(stats["max_move_cm"], abs(dz))
                keep.append(r)
            if len(keep) != len(area.records):
                area.records = keep
                area.declared_count = len(keep)
    return stats


def _write(m: MergedMap, z: np.ndarray, out, overwrite: bool) -> List[str]:
    out = pathlib.Path(out)
    if out.exists():
        if not overwrite:
            raise FileExistsError("%s exists; pass overwrite to replace it" % out)
        shutil.rmtree(out)
    shutil.copytree(m.root, out, ignore=shutil.ignore_patterns("_preview", "_readapt.json"))
    written = []

    def put(path: pathlib.Path, data: bytes) -> None:
        if path.read_bytes() != data:
            path.write_bytes(data)
            written.append(str(path.relative_to(out)).replace("\\", "/"))

    for sx, sy in m.sectors():
        d = m.sector_dir(sx, sy, out)
        raw = terrain_gen.to_sector_raw(z, sx, sy)
        put(d / "height.raw", height_codec.HeightMap(raw, m.hfile[sx, sy].trailing).to_bytes())
        ts, cs = m._tslice(sx, sy), m._cslice(sx, sy)
        if (m.tile[ts] != m.tile0[ts]).any():
            old = tile_codec.read_tile(d / "tile.raw")
            put(d / "tile.raw", tile_codec.TileMap(texture_gen.to_sector_raw(m.tile, sx, sy),
                                                  old.trailing).to_bytes())
        if (m.attr[ts] != m.attr0[ts]).any():
            put(d / "attr.atr", attr_codec.AttrMap(m.attr[ts]).to_bytes())
        if (m.wraw[cs] != m.wraw0[cs]).any():
            w = m.wraw[cs]
            levels = [int(v) for v in np.unique(w) if v != DRY]
            cells = np.full(w.shape, water_codec.NO_WATER, np.uint8)
            for i, v in enumerate(levels):
                cells[w == v] = i
            put(d / "water.wtr", water_codec.WaterMap(cells, levels,
                                                      m.wfile[sx, sy].legacy).to_bytes())
        for name, files in (("areadata.txt", m.areas), ("areaambiencedata.txt", m.ambs)):
            if (sx, sy) in files:
                put(d / name, files[sx, sy].to_bytes())
    # Derived, and stale the moment attr moved (rule 14): rebuilt from the attr
    # just written, masked to the three bits the server reads (rule 5).
    grids = {s: m.attr[m._tslice(*s)] for s in m.sectors()}
    data = sa_codec.from_attr_maps(grids, m.W, m.H).to_bytes()
    old = (out / "server_attr").read_bytes() if (out / "server_attr").exists() else None
    if data != old:
        (out / "server_attr").write_bytes(data)
        written.append("server_attr")
    return written


def _server_attr_on_disk(out, back: "MergedMap") -> dict:
    """Re-read the file: nothing above bit 2, and the same cells blocked as the
    client's ``attr.atr`` says."""
    sa = sa_codec.read_server_attr(pathlib.Path(out) / "server_attr")
    top, blocked, agrees = 0, 0, True
    for sx, sy in back.sectors():
        g = sa.to_attr_grid(sx, sy)
        top = max(top, int(g.max()))
        blocked += int((g & ATTR_BLOCK).astype(bool).sum())
        agrees &= bool(np.array_equal(g, back.attr[back._tslice(sx, sy)] & sa_codec.SERVER_ATTR_MASK))
    return {"max_value": top, "blocked_cells": blocked, "agrees": agrees and top <= 7}


def _join_slot(back: "MergedMap", torn, block_of, void) -> int:
    """The deepest place where a welded border row lies below the rows on BOTH
    sides of it. A closed tear is not a sound join: tear 0 and a 45 m slot came
    out of one run."""
    z, _ = back.stitch()
    worst = 0.0
    for a, b, _t in torn:
        if block_of[a] in void or block_of[b] in void:
            continue
        (ax, ay), (bx, by) = a, b
        if ax != bx:
            c, rows = bx * CELLS, slice(ay * CELLS + 4, ay * CELLS + 125)
            d = np.minimum(z[rows, c - 1], z[rows, c + 1]) - z[rows, c]
        else:
            r, cols = by * CELLS, slice(ax * CELLS + 4, ax * CELLS + 125)
            d = np.minimum(z[r - 1, cols], z[r + 1, cols]) - z[r, cols]
        worst = max(worst, float(d.max()))
    return int(round(worst))


def _tear_on_disk(out) -> float:
    """Re-read what was written: the worst disagreement left on any shared vertex."""
    _, tear = MergedMap(out).stitch()
    return float(tear.max())


def _previews(m: MergedMap, z0: np.ndarray, z: np.ndarray, links, out_dir) -> None:
    try:
        from PIL import Image
    except ImportError:                                    # pragma: no cover
        return
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    def shot(zz, attr, wraw, name, with_line):
        zc = _cell_z(zz)
        g = ((zc - zc.min()) / max(1.0, zc.max() - zc.min()) * 255).astype(np.uint8)
        g = g.repeat(2, 0).repeat(2, 1)
        rgb = np.stack([g, g, g], -1)
        blk = (attr & ATTR_BLOCK) != 0
        rgb[blk] = (rgb[blk] * 0.5 + np.array([90, 0, 0])).astype(np.uint8)
        sub = ((wraw != DRY) & (wraw * HS > zc)).repeat(2, 0).repeat(2, 1)
        rgb[sub] = (40, 90, 220)
        if with_line:
            for lk in links:
                for x, y in lk.line:
                    rgb[int(y * 2) - 1:int(y * 2) + 2, int(x * 2) - 1:int(x * 2) + 2] = (255, 220, 0)
        Image.fromarray(rgb).save(out_dir / name)

    shot(z0, m.attr0, m.wraw0, "readapt_before.png", False)
    shot(z, m.attr, m.wraw, "readapt_after.png", False)
    shot(z, m.attr, m.wraw, "readapt_route.png", True)
    pal = np.random.RandomState(3).randint(40, 255, (256, 3)).astype(np.uint8)
    Image.fromarray(pal[m.tile]).save(out_dir / "readapt_tile.png")

"""Labyrinths cut into the terrain: no dungeon pieces, the maze is a trench.

Measured on `metin2_map_orclabyrinth` (x 515-770 m, y 768-1538 m), the trench
labyrinth the user pointed at, and checked against the letter floor of
`metin2_map_devilscatacomb` (around 18, 553 m), which is the maze/monkey letter
layout cut into terrain:

========================  =================  ============================
                          orclabyrinth       devilscatacomb letters
========================  =================  ============================
plateau                   16,384 cm, flat    21,482 cm, rolling
trench depth              2,953 cm           3,664 cm
floor width (2x medial)   p50 16 m (12-22)   p50 16.7 m (8-26)
walkable width            p50 12 m (10-18)   p50 12 m (10-17)
wall: full height within  8 m (~75 deg)      ~25 m
ridge between trenches    p50 24 m (16-30)   --
floor relief              +-2 m              +-4 m
paint                     floor dc_field_01, wall and plateau dc_rock_01
attr                      floor less a 2 m rim walkable (P(floor|walk) 0.92);
                          walls and plateau blocked (99.6 %)
objects                   14: `warpgate01` on the letter tips, a bone tomb
========================  =================  ============================

The wall profile is the orc one, height over the floor by horizontal metres
from the floor edge: 1 m 7.5, 2 m 8.8, 3 m 17.9, 4 m 19.4, 5 m 23.9,
6 m 25.9, 7 m 28.9, 8 m 29.5 (all of it). The tips are rounded pads (up to
34 m across) and a frame ridge stands 27-50 m over the plateau around the whole
labyrinth.

The maze is the same cell graph as the kit labyrinths; a trench has no length
to fit, so any layout closes. With ``islands`` (the default, as both source
maps are) it is cut into letters of 4-9 cells joined by warp gates on their
tips; without, it is one connected cave maze.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..codec import areadata as ad
from .spec import SECTOR_UNITS, MapSpec, SpecError, stream_seed

#: Trench styles, by name in `labyrinth.kit`.
TRENCH_STYLES = {
    "orc_trench": {
        "source": "metin2_map_orclabyrinth x 515-770 m, y 768-1538 m",
        "plateau_cm": 16384.0,
        "depth_cm": 2953.0,
        "floor_m": 16.0,
        "walk_inset_m": 2.0,
        "ridge_m": 24.0,
        "pad_r_m": 11.0,              # tip pads: floor inner radius p90 9.7, max 17
        "arena_r_m": 30.0,
        #: (metres from the floor edge, cm over the floor)
        "profile": [(0, 0), (1, 750), (2, 876), (3, 1790), (4, 1938), (5, 2388),
                    (6, 2586), (7, 2887), (8, 2953)],
        "floor_relief_cm": 200.0,
        "edge_noise_m": 1.5,
        "frame_cm": 3000.0,
        "frame_m": 30.0,
        #: cells per letter: the orc glyphs are 100-130 m across at a 40 m
        #: pitch, the "皿" one a loop with three prongs
        "island_cells": (4, 9),
        "warp_crc": 929619867,          # effect/background/warpgate01.mse
        "warp_bias": 0.0,               # on the ground, 14 of 14
        "environment": "dark.msenv",
        #: texture roles the mapspec must declare
        "roles": ("floor", "wall", "floor_patch"),
        "patch_share": 0.10,            # dc_grass_00 on the orc floors
    },
}

#: plateau between two letters, metres (orclabyrinth: 40-70 m between glyphs)
LETTER_GAP_M = 50.0

STEP = {"E": (1, 0), "W": (-1, 0), "N": (0, -1), "S": (0, 1)}
OPP = {"E": "W", "W": "E", "N": "S", "S": "N"}


@dataclass
class TrenchShape:
    """The labyrinth as vectors in map tile metres (x east, y SOUTH)."""

    style: dict
    segments: List[Tuple[float, float, float, float]] = field(default_factory=list)
    pads: List[Tuple[float, float, float]] = field(default_factory=list)    # x, y, r
    bbox: Tuple[float, float, float, float] = (0, 0, 0, 0)
    seed: int = 0

    def shifted(self, dx, dy):
        self.segments = [(a + dx, b + dy, c + dx, d + dy) for a, b, c, d in self.segments]
        self.pads = [(x + dx, y + dy, r) for x, y, r in self.pads]
        x0, y0, x1, y1 = self.bbox
        self.bbox = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)

    # ------------------------------------------------------------------
    def edge_distance(self, shape) -> np.ndarray:
        """Signed metres to the trench floor edge on the 1 m tile grid
        (negative inside the floor), roughened by the measured edge noise."""
        h, w = shape
        half = self.style["floor_m"] / 2.0
        d = np.full(shape, 1e6)
        ys, xs = np.mgrid[0:h, 0:w] + 0.5
        for x0, y0, x1, y1 in self.segments:
            pad = half + 40
            c0, c1 = int(max(0, min(x0, x1) - pad)), int(min(w, max(x0, x1) + pad + 1))
            r0, r1 = int(max(0, min(y0, y1) - pad)), int(min(h, max(y0, y1) + pad + 1))
            if c0 >= c1 or r0 >= r1:
                continue
            px, py = xs[r0:r1, c0:c1], ys[r0:r1, c0:c1]
            vx, vy = x1 - x0, y1 - y0
            L2 = vx * vx + vy * vy or 1e-9
            t = np.clip(((px - x0) * vx + (py - y0) * vy) / L2, 0, 1)
            dd = np.hypot(px - (x0 + t * vx), py - (y0 + t * vy)) - half
            d[r0:r1, c0:c1] = np.minimum(d[r0:r1, c0:c1], dd)
        for x, y, r in self.pads:
            pad = r + 40
            c0, c1 = int(max(0, x - pad)), int(min(w, x + pad + 1))
            r0, r1 = int(max(0, y - pad)), int(min(h, y + pad + 1))
            if c0 >= c1 or r0 >= r1:
                continue
            dd = np.hypot(xs[r0:r1, c0:c1] - x, ys[r0:r1, c0:c1] - y) - r
            d[r0:r1, c0:c1] = np.minimum(d[r0:r1, c0:c1], dd)
        rng = np.random.default_rng(stream_seed("labyrinth-edge", self.seed))
        return d + self.style["edge_noise_m"] * _smooth_noise(rng, shape, 6)

    def raster(self, shape, rng_seed) -> Dict[str, np.ndarray]:
        """Height on the terrain vertex grid (cm), the floor/wall/plateau
        classes and the walk on the tile grid."""
        st = self.style
        h, w = shape
        d = self.edge_distance(shape)
        floor = d <= 0
        walk = d <= -st["walk_inset_m"]
        # height: sample the tile field at the vertices (every 2 tiles)
        vh, vw = h // 2 + 1, w // 2 + 1
        dv = d[np.clip(np.arange(vh) * 2, 0, h - 1)][:, np.clip(np.arange(vw) * 2, 0, w - 1)]
        prof = np.array(st["profile"], float)
        rise = np.interp(np.maximum(dv, 0), prof[:, 0], prof[:, 1]) * st["depth_cm"] / prof[-1, 1]
        rng = np.random.default_rng(stream_seed("labyrinth-floor", rng_seed))
        relief = st["floor_relief_cm"] * (2 * _smooth_noise(rng, (vh, vw), 12) - 1)
        height = st["plateau_cm"] - st["depth_cm"] + rise
        height = height + np.where(dv <= 0, relief, relief * np.clip(1 - dv / 8, 0, 1))
        # the frame: a rock ridge round the whole labyrinth, as orclabyrinth has
        x0, y0, x1, y1 = self.bbox
        fm = st["frame_m"]
        yy, xx = np.mgrid[0:vh, 0:vw] * 2.0
        out = np.maximum(np.maximum(x0 - xx, xx - x1), np.maximum(y0 - yy, yy - y1))
        ring = np.clip(1 - np.abs(out - fm) / fm, 0, 1)
        height = height + st["frame_cm"] * ring ** 1.5 * (0.75 + 0.5 * _smooth_noise(rng, (vh, vw), 10))
        return {"height": height, "floor": floor, "walk": walk, "edge": d}


def _smooth_noise(rng, shape, cell) -> np.ndarray:
    """Value noise in [0, 1], ~``cell`` tiles across."""
    h, w = shape
    gh, gw = h // cell + 3, w // cell + 3
    g = rng.random((gh, gw))
    ys = np.arange(h) / cell
    xs = np.arange(w) / cell
    y0, x0 = ys.astype(int), xs.astype(int)
    fy, fx = (ys - y0)[:, None], (xs - x0)[None, :]
    fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
    a = g[y0][:, x0]
    b = g[y0][:, x0 + 1]
    c = g[y0 + 1][:, x0]
    e = g[y0 + 1][:, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + e * fx) * fy


# --------------------------------------------------------------------------
# the maze, cut into letters
# --------------------------------------------------------------------------

def build(spec: MapSpec, plan_cls, maze_fn, bfs_fn, sides_fn):
    """A `labyrinth.Plan` whose geometry is a `TrenchShape`.

    The maze is cut into letters (or kept whole without ``islands``). Each
    letter is drawn on its own cell grid and the letters are shelf-packed
    `LETTER_GAP_M` apart, as both source maps lay their glyphs out in rows:
    left on the shared grid, two letters stood one ridge apart -- the same
    24 m as the ridges inside a letter -- and read as one maze. The boss arena
    is packed like a letter and reached by gate; the entrance is a stub out of
    its letter with the start on its pad.
    """
    lab = spec.labyrinth
    st = TRENCH_STYLES[lab.kit]
    rng = random.Random(stream_seed("labyrinth", spec.seed))
    cols, rows = lab.cells
    P = lab.pitch_m or (st["floor_m"] + st["ridge_m"])
    edges = maze_fn(cols, rows, lab.loops, 4, rng)
    islands_on = True if lab.islands is None else bool(lab.islands)

    def on(cell, side):
        c, r = cell
        return {"N": r == 0, "S": r == rows - 1, "W": c == 0, "E": c == cols - 1}[side]

    line = sorted([(c, r) for c in range(cols) for r in range(rows) if on((c, r), lab.entrance)],
                  key=lambda x: abs(x[0] - (cols - 1) / 2) + abs(x[1] - (rows - 1) / 2))
    mid = line[0]
    dist = bfs_fn(mid, edges)
    far = OPP[lab.entrance]
    cands = [((dist.get(cell, 0), side == far), cell, side)
             for cell in dist for side in STEP if on(cell, side) and side != lab.entrance
             and cell != mid]
    _k, boss, bside = max(cands)

    # -- letters: grown at random to 2..island_cells, dead ends ride along ----
    adj = {}
    for e in edges:
        a, b = tuple(e)
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    assigned, islands = {}, []
    order = list(dist)
    for seed in order:
        if seed in assigned:
            continue
        isl = {seed}
        if islands_on:
            target = rng.randint(*st["island_cells"])
            q = [seed]
            for cur in q:
                nb = [n for n in adj.get(cur, []) if n not in assigned and n not in isl]
                rng.shuffle(nb)
                for n in nb:
                    if len(isl) < target or len(adj.get(n, [])) == 1:
                        isl.add(n)
                        q.append(n)
        else:
            isl = set(order)
        for c in isl:
            assigned[c] = len(islands)
        islands.append(isl)
    # a lone cell is a pit with a gate in it, never a letter: it joins the
    # letter beside it
    for k, isl in enumerate(islands):
        if len(isl) == 1 and islands_on:
            (cell,) = tuple(isl)
            nb = [n for n in adj.get(cell, []) if len(islands[assigned[n]]) > 0 and assigned[n] != k]
            if nb:
                j = assigned[min(nb, key=lambda n: len(islands[assigned[n]]))]
                islands[j].add(cell)
                assigned[cell] = j
                islands[k] = set()
    keep = [i for i in islands if i]
    for n, isl in enumerate(keep):
        for c in isl:
            assigned[c] = n
    islands = keep

    # -- each letter on its own grid ------------------------------------------
    half = st["floor_m"] / 2.0
    wall = float(st["profile"][-1][0]) + 4.0
    units = []                       # dict(segs, pads, cells{cell: (x, y)}, box)
    deg = {cell: 0 for cell in assigned}
    cut = []
    for e in edges:
        a, b = sorted(tuple(e))
        if assigned[a] == assigned[b]:
            deg[a] += 1
            deg[b] += 1
        else:
            cut.append((a, b))
    for k, isl in enumerate(islands):
        c0 = min(c for c, _r in isl)
        r0 = min(r for _c, r in isl)
        pos = {cell: ((cell[0] - c0) * P, (cell[1] - r0) * P) for cell in isl}
        segs, pads = [], []
        for e in edges:
            a, b = tuple(e)
            if a in isl and b in isl:
                segs.append(pos[a] + pos[b])
        tips = [c for c in isl if deg[c] <= 1]
        for t in tips:
            pads.append(pos[t] + (st["pad_r_m"],))
        start = None
        if mid in isl:
            # the entrance: a stub out of the letter, the start on its pad
            ex, ey = STEP[lab.entrance]
            x, y = pos[mid]
            sx, sy = x + ex * P * 0.6, y + ey * P * 0.6
            segs.append((x, y, sx, sy))
            pads.append((sx, sy, st["pad_r_m"]))
            start = (sx, sy)
        bstub = None
        if boss in isl:
            bx, by = STEP[bside]
            x, y = pos[boss]
            tx, ty = x + bx * P * 0.5, y + by * P * 0.5
            segs.append((x, y, tx, ty))
            pads.append((tx, ty, st["pad_r_m"]))
            bstub = (tx, ty)
        xs = [v for s in segs for v in (s[0], s[2])] + [p[0] for p in pads] + [p[0] for p in pos.values()]
        ys = [v for s in segs for v in (s[1], s[3])] + [p[1] for p in pads] + [p[1] for p in pos.values()]
        reach = max(half, st["pad_r_m"]) + wall
        units.append({"segs": segs, "pads": pads, "pos": pos, "tips": tips,
                      "start": start, "bstub": bstub,
                      "box": (min(xs) - reach, min(ys) - reach, max(xs) + reach, max(ys) + reach)})
    ar = st["arena_r_m"]
    units.append({"segs": [], "pads": [(0.0, 0.0, ar)], "pos": {}, "tips": [], "start": None,
                  "bstub": None, "arena": True,
                  "box": (-ar - wall, -ar - wall, ar + wall, ar + wall)})

    # -- shelf-pack: the entrance letter first, then by distance --------------
    first = assigned[mid]
    rank = {k: min(dist.get(c, 0) for c in isl) for k, isl in enumerate(islands)}
    order_u = sorted(range(len(units)), key=lambda k: (k != first, rank.get(k, 1e9)))
    gap = LETTER_GAP_M
    area = sum((u["box"][2] - u["box"][0] + gap) * (u["box"][3] - u["box"][1] + gap) for u in units)
    width = max(math.sqrt(area) * 1.15, max(u["box"][2] - u["box"][0] for u in units))
    x = y = shelf = 0.0
    for k in order_u:
        u = units[k]
        w, h = u["box"][2] - u["box"][0], u["box"][3] - u["box"][1]
        if x and x + w > width:
            x, y, shelf = 0.0, y + shelf + gap, 0.0
        u["dx"], u["dy"] = x - u["box"][0], y - u["box"][1]
        x += w + gap
        shelf = max(shelf, h)

    def moved(u, p):
        return (p[0] + u["dx"], p[1] + u["dy"])

    shape = TrenchShape(style=st, seed=spec.seed)
    for u in units:
        for s in u["segs"]:
            a, b = moved(u, s[:2]), moved(u, s[2:])
            shape.segments.append(a + b)
        for p in u["pads"]:
            shape.pads.append(moved(u, p[:2]) + (p[2],))

    # -- gates: a spanning tree of the letters from the entrance --------------
    used = set()

    def spot(cell):
        u = units[assigned[cell]]
        free = [t for t in u["tips"] if t not in used and t != mid and t != boss]
        if not free:
            return moved(u, u["pos"][cell])
        t = min(free, key=lambda t: abs(t[0] - cell[0]) + abs(t[1] - cell[1]))
        used.add(t)
        return moved(u, u["pos"][t])
    warps = []
    reached = {assigned[mid]}
    rng.shuffle(cut)
    cut.sort(key=lambda e: min(dist.get(e[0], 0), dist.get(e[1], 0)))
    pending = list(cut)
    while pending:
        progress = False
        for e in list(pending):
            ia, ib = assigned[e[0]], assigned[e[1]]
            if (ia in reached) != (ib in reached):
                warps.append((spot(e[0]), spot(e[1])))
                reached |= {ia, ib}
                pending.remove(e)
                progress = True
        if not progress:
            break
    for e in pending:
        if rng.random() < lab.loops:
            warps.append((spot(e[0]), spot(e[1])))
    bu = units[assigned[boss]]
    arena = units[-1]
    boss_pt = moved(arena, (0.0, 0.0))
    warps.append((moved(bu, bu["bstub"]), boss_pt))
    su = units[assigned[mid]]
    start_pt = moved(su, su["start"])

    # -- frame, margin, size ----------------------------------------------------
    xs = [moved(u, u["box"][:2])[0] for u in units] + [moved(u, u["box"][2:])[0] for u in units]
    ys = [moved(u, u["box"][:2])[1] for u in units] + [moved(u, u["box"][2:])[1] for u in units]
    shape.bbox = (min(xs), min(ys), max(xs), max(ys))
    margin = lab.margin_m + st["frame_m"]
    dx, dy = margin - shape.bbox[0], margin - shape.bbox[1]
    shape.shifted(dx, dy)
    warps = [((a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy)) for a, b in warps]
    start_pt = (start_pt[0] + dx, start_pt[1] + dy)
    boss_pt = (boss_pt[0] + dx, boss_pt[1] + dy)
    W = shape.bbox[2] + margin
    H = shape.bbox[3] + margin

    plan = plan_cls(kit=lab.kit, pitch_cm=P * 100.0)
    plan.terrain = shape
    plan.size = (max(1, int(math.ceil(W * 100 / SECTOR_UNITS))),
                 max(1, int(math.ceil(H * 100 / SECTOR_UNITS))))
    # engine frame: x cm, y = -terrain_y cm
    plan.start = (start_pt[0] * 100.0, -start_pt[1] * 100.0)
    plan.boss = (boss_pt[0] * 100.0, -boss_pt[1] * 100.0)
    plan.warps = [((a[0] * 100.0, -a[1] * 100.0), (b[0] * 100.0, -b[1] * 100.0)) for a, b in warps]
    for a, b in plan.warps:
        for x, y in (a, b):
            plan.extra.append(ad.ObjectRecord(x=x, y=y, crc=st["warp_crc"], roll=0.0,
                                              height_bias=st["warp_bias"]))
    plan.notes.append("labyrinth: %s, %dx%d cells, pitch %.0f m, %s, %d gate pair(s) "
                      "(server warp quest not generated)"
                      % (lab.kit, cols, rows, P,
                         ("%d letters of %s cells" % (len(islands), "/".join(
                             str(len(i)) for i in islands))) if islands_on else "one connected maze",
                         len(plan.warps)))
    return plan


def paint(spec: MapSpec, ras: Dict[str, np.ndarray]) -> np.ndarray:
    """tile.raw indices: floor, wall and plateau, floor patches -- by role."""
    st = TRENCH_STYLES[spec.labyrinth.kit]
    slot = {}
    for i, t in enumerate(spec.textures, 1):
        slot.setdefault(t.role, i)
    missing = [r for r in st["roles"][:2] if r not in slot]
    if missing:
        raise SpecError("labyrinth %s needs texture slots with roles %s (missing %s)"
                        % (spec.labyrinth.kit, ", ".join(st["roles"]), ", ".join(missing)))
    d = ras["edge"]
    rng = np.random.default_rng(stream_seed("labyrinth-paint", spec.seed))
    tiles = np.full(d.shape, slot["wall"], np.uint8)
    floor = d <= 0
    tiles[floor] = slot["floor"]
    # the wall foot keeps some floor paint (orc: field_01 is a third of the
    # wall band), thinning out as the rock rises
    foot = (d > 0) & (d < 3)
    tiles[foot & (rng.random(d.shape) < (1 - d / 3) * 0.7)] = slot["floor"]
    if "floor_patch" in slot:
        patch = _smooth_noise(rng, d.shape, 7) > 1 - st["patch_share"] * 2.2
        tiles[floor & patch & (d < -2)] = slot["floor_patch"]
    return tiles

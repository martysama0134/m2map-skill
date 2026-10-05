"""Quality rules: maps that load and play, but were plainly never finished.

`rules.py` asks "will this map break?". These ask "did anybody finish it?" --
the worst cases a curator wants flagged on a mapper's map, measured against the
116 corpus maps that own terrain so that Ymir's own maps pass:

=============  =====================================================  ==================
rule           signal                                                 corpus (official)
=============  =====================================================  ==================
M2MAP-QA-001   walkable share of steep (>= 25 deg) ground painted     median 0.6 %,
               with a stone/rock/cliff texture                        p95 7.5 %, max 15 %
M2MAP-QA-002   blocked share of the whole attr grid                   p5 44 %, min 8.6 %
M2MAP-QA-003   road tiles within 3 m of a road's edge with at most    p5 7.1, median 24
               one road neighbour, per 100 m of edge (a dithered      per 100 m; 3 of 146
               rim)                                                   roads ~0
M2MAP-QA-004   longest run of map edge that is open -- not walled     0 m on 66 of 68
               (>= 5 m over the interior, or mostly blocked), not     outdoor maps; <= 32 m
               water -- in 16 m steps                                 (an entrance) else
=============  =====================================================  ==================

QA-004 skips interiors (`TerrainVisible 0`) and edge stretches that were never
painted (the smhgate stages are one walled town sector amid blank ones), lets
water through (a bay's
horizon is a horizon), counts a stretch lined with tall buildings as walled --
an empire castle's curtain wall hides the edge as well as a mountain does -- and
lets a gap up to `OPEN_EDGE_OK_M` through, which is what an entrance, the
S-shaped kind included, measures as at the edge.
"""

from __future__ import annotations

import pathlib
from typing import List, Optional

import numpy as np

from ..codec.attr import read_attr
from ..codec.height import read_height

ROCK_MOTIFS = ("stone", "rock", "cliff", "mountain")
STEEP_DEG = 25.0
ROCK_WALK_MAX = 0.30          # QA-001 above this (corpus max 0.15)
ROCK_MIN_TILES = 2000
BLOCKED_MIN = 0.02            # QA-002 below this (corpus min 0.086)
SPECKS_MIN = 2.0              # QA-003 below this per 100 m of edge (corpus min 3.75)
ROAD_MIN_TILES = 2000
EDGE_BAND_M = 30
EDGE_STEP_M = 16
WALL_LIFT_CM = 500.0
OPEN_EDGE_OK_M = 64           # QA-004 above this (corpus <= 32 m)
WALL_OBJECT_CM = 400.0        # a Building this tall standing in the band walls it
WALL_OBJECT_COVER = 0.6       # ... when footprints cover this much of the stretch

_CATALOG = pathlib.Path(__file__).resolve().parents[3] / "reference" / "catalog"
_TALL = None


def _tall_buildings():
    """CRC -> footprint half-extent (cm) of every Building >= WALL_OBJECT_CM tall."""
    global _TALL
    if _TALL is None:
        import json
        objs = json.loads((_CATALOG / "objects.json").read_text(encoding="utf-8"))["objects"]
        mods = json.loads((_CATALOG / "models.json").read_text(encoding="utf-8"))["models"]
        _TALL = {}
        for crc, o in objs.items():
            m = mods.get(crc) or {}
            size = m.get("size_xyz")
            if o.get("property_type") != "Building" or not size or m.get("degenerate"):
                continue
            if size[2] >= WALL_OBJECT_CM and max(size[0], size[1]) < 1e5:
                _TALL[int(crc)] = max(size[0], size[1]) / 2.0
    return _TALL


def _wall_objects(root: pathlib.Path, sectors, shape):
    """Tiles under the footprint of a tall building (a castle wall, a gate, a keep)."""
    from ..codec.areadata import AreaData
    tall = _tall_buildings()
    h, w = shape
    mask = np.zeros(shape, bool)
    for name in sectors:
        p = root / name / "areadata.txt"
        if not p.is_file():
            continue
        for r in AreaData.parse(p.read_bytes()).records:
            half = tall.get(r.crc)
            if half is None:
                continue
            cx, cy, rr = int(r.x // 100), int(-r.y // 100), int(half // 100)
            mask[max(0, cy - rr):min(h, cy + rr + 1), max(0, cx - rr):min(w, cx + rr + 1)] = True
    return mask


def _dilate(m, k):
    out = m.copy()
    for _ in range(k):
        o = out.copy()
        o[1:] |= out[:-1]
        o[:-1] |= out[1:]
        o[:, 1:] |= out[:, :-1]
        o[:, :-1] |= out[:, 1:]
        out = o
    return out


def _specks(mask, band):
    """Road tiles in `band` with at most one road neighbour (4-connected): the
    loose tiles a dithered rim is made of. A flood fill stopped at 4 tiles chopped
    every big road into false specks (4.4 per 100 m on a clean L) and was slow."""
    n = np.zeros(mask.shape, np.int8)
    n[1:] += mask[:-1]
    n[:-1] += mask[1:]
    n[:, 1:] += mask[:, :-1]
    n[:, :-1] += mask[:, 1:]
    return int((mask & band & (n <= 1)).sum())


def rim_specks(road):
    """Loose road tiles within 3 m of the road's edge per 100 m of edge (QA-003)."""
    core = ~_dilate(~road, 2)
    band = _dilate(road, 3) & ~core
    edge = int((road & _dilate(~road, 1)).sum())
    return 100.0 * _specks(road, band) / max(edge, 1)


def _grids(root: pathlib.Path, sectors, size):
    """Whole-map height (vertex grid, cm), attr and water from the sector files."""
    W, H = size
    hv = np.zeros((H * 128 + 1, W * 128 + 1))
    att = np.zeros((H * 256, W * 256), np.uint8)
    for name in sectors:
        sx, sy = int(name[:3]), int(name[3:])
        if sx >= W or sy >= H:
            continue
        d = root / name
        if (d / "height.raw").is_file():
            hv[sy * 128:sy * 128 + 129, sx * 128:sx * 128 + 129] = \
                read_height(d / "height.raw").raw[1:130, 1:130].astype(float) * 0.5
        if (d / "attr.atr").is_file():
            att[sy * 256:(sy + 1) * 256, sx * 256:(sx + 1) * 256] = read_attr(d / "attr.atr").cells
    return hv, att


def _where(mask, cap=4):
    """The sectors holding most of a mask, as 'XXXYYY (n tiles)' strings."""
    h, w = mask.shape
    cells = []
    for sy in range(h // 256):
        for sx in range(w // 256):
            n = int(mask[sy * 256:(sy + 1) * 256, sx * 256:(sx + 1) * 256].sum())
            if n:
                cells.append((n, "%03d%03d" % (sx, sy)))
    cells.sort(reverse=True)
    return ", ".join("%s (%d m2)" % (s, n) for n, s in cells[:cap])


def edge_stretches(hu, walk, water, tiles, walls):
    """The map edge in EDGE_STEP_M stretches, each judged on the outer EDGE_BAND_M:
    ``(side, start_m, length_m, kind)``, kind one of void / water / wall / open.
    `edit/curate.py` raises its ridge on exactly the stretches this calls open."""
    H, W = walk.shape
    b, step = EDGE_BAND_M, EDGE_STEP_M
    inner = hu[b * 3:H - b * 3, b * 3:W - b * 3]
    iw = walk[b * 3:H - b * 3, b * 3:W - b * 3]
    ref = float(np.median(inner[iw])) if iw.any() else float(np.median(hu))
    out = []
    for side in "NESW":
        L = W if side in "NS" else H
        for i in range(0, L - step + 1, step):
            sl = {"N": (slice(0, b), slice(i, i + step)), "S": (slice(H - b, H), slice(i, i + step)),
                  "W": (slice(i, i + step), slice(0, b)), "E": (slice(i, i + step), slice(W - b, W))}[side]
            lift = float(np.median(hu[sl])) - ref
            along = walls[sl].any(axis=1 if side in "WE" else 0)
            if (tiles[sl] == 0).mean() > 0.5:
                kind = "void"        # unpainted sectors: no world here to see the end of
            elif water[sl].mean() > 0.3:
                kind = "water"
            elif along.mean() >= WALL_OBJECT_COVER:
                kind = "wall"        # a castle wall hides the edge as a mountain does
            elif lift > WALL_LIFT_CM or walk[sl].mean() < 0.3:
                kind = "wall"
            else:
                kind = "open"
            out.append((side, i, step, kind))
    return out


def open_runs(stretches):
    """Consecutive open stretches along one side: ``(length_m, (side, start_m))``."""
    runs, cur, start, last_side = [], 0, None, None
    for side, i, step, kind in stretches:
        if side != last_side and cur:
            runs.append((cur, start))
            cur = 0
        last_side = side
        if kind == "open":
            if not cur:
                start = (side, i)
            cur += step
        elif cur:
            runs.append((cur, start))
            cur = 0
    if cur:
        runs.append((cur, start))
    return runs


def quality(view, textureset_dir=None) -> List:
    """Findings for a map that owns terrain (`rules.MapView`)."""
    from .rules import Finding
    from ..mine import roads, tile_stats

    out = []
    st = view.setting
    if st is None or not view.sectors:
        return out
    size = tuple(st.map_size)
    root = view.terrain_root or view.root
    pack = pathlib.Path(textureset_dir).parent if textureset_dir else tile_stats.DEFAULT_PACK_DIR
    mt = tile_stats.load_map(root, pack)
    if mt is None:
        return out
    hv, att = _grids(root, view.sectors, size)
    # MapSize and the sector folders disagree on some shipped maps (the smhgate
    # stages ship folders past their declared size): judge the extent both cover
    H = min(att.shape[0], mt.grid.shape[0])
    W = min(att.shape[1], mt.grid.shape[1])
    att = att[:H, :W]
    hv = hv[:H // 2 + 1, :W // 2 + 1]
    tiles = mt.grid[:H, :W]
    hu = np.repeat(np.repeat(hv, 2, 0), 2, 1)[:H, :W]
    gy, gx = np.gradient(hv, 200.0)
    slope = np.repeat(np.repeat(np.degrees(np.arctan(np.hypot(gx, gy))), 2, 0), 2, 1)[:H, :W]
    walk = (att & 1) == 0
    water = (att & 2) != 0
    interior = getattr(st, "terrain_visible", None) == 0

    # QA-002 nobody made the attr
    blocked = float((~walk).mean())
    if blocked < BLOCKED_MIN:
        out.append(Finding(
            "M2MAP-QA-002", "major", str(root),
            "The whole map is walkable: mountains, cliffs and the map edge included.",
            "%.1f%% of the attr grid is blocked (official maps: 8.6%% at the least, 44%% at p5) -- "
            "the attr was never made" % (100 * blocked),
            "Generate it: block steep ground and the border band, then regenerate server_attr "
            "(rules 5, 14; `reference/attributes.md`)."))

    if mt.textureset is None:
        out.append(Finding(
            "M2MAP-QA-000", "info", str(root),
            "The quality pass could not read the textureset.",
            "%s not found next to the map or under %s: the rock and road checks "
            "(QA-001, QA-003) did not run" % (st.texture_set, pack),
            "Pass --textureset-dir pointing at the folder holding it."))

    # QA-001 steep rock you can walk on
    rock_ids = []
    for idx in mt.used_indices():
        name = (mt.slot_name(idx) or "").replace("\\", "/").lower().split("/")[-1]
        if any(k in name for k in ROCK_MOTIFS):
            rock_ids.append(idx)
    if rock_ids and not interior:
        steep_rock = np.isin(tiles, rock_ids) & (slope >= STEEP_DEG)
        n = int(steep_rock.sum())
        if n >= ROCK_MIN_TILES:
            bad = steep_rock & walk
            share = float(bad.sum()) / n
            if share > ROCK_WALK_MAX:
                out.append(Finding(
                    "M2MAP-QA-001", "major", str(root),
                    "Players walk up painted cliffs: rock-textured slopes with no block on them.",
                    "%.0f%% of %d m2 of steep (>= %d deg) stone/rock/cliff ground is walkable "
                    "(official maps: 0.6%% median, 15%% at worst); most in %s"
                    % (100 * share, n, STEEP_DEG, _where(bad)),
                    "Block the rock skin (rule 19: the cliff paint covers exactly the ground the "
                    "player cannot walk on); regenerate server_attr."))

    # QA-003 roads cut with a ruler
    try:
        stats = roads.classify_path_indices(mt)
    except Exception:                                      # noqa: BLE001
        stats = []
    for s in stats:
        if not s.get("is_path"):
            continue
        road = tiles == s["index"]
        if road.sum() < ROAD_MIN_TILES:
            continue
        per100 = rim_specks(road)
        if per100 < SPECKS_MIN:
            out.append(Finding(
                "M2MAP-QA-003", "minor", "%s slot %d (%s)" % (root, s["index"], mt.slot_name(s["index"])),
                "A road painted with hard straight edges; may read as pasted on.",
                "%.1f loose road tiles per 100 m of road edge (official roads: p5 7.1, median "
                "24; 3 of 146 are hard-edged too) -- the rim is not dithered" % per100,
                "Dither the rim ~3 m into the ground with a sibling of the road texture "
                "(rule 19, `reference/taste.md` 1.9). Flag only -- some styles want it."))

    # QA-004 the world ends in plain sight
    if not interior:
        runs = open_runs(edge_stretches(hu, walk, water, tiles, _wall_objects(root, view.sectors, (H, W))))
        long = [r for r in runs if r[0] > OPEN_EDGE_OK_M]
        if long:
            total = sum(r[0] for r in runs)
            desc = ", ".join("%s edge from %d m: %d m" % (s, i, n) for n, (s, i) in sorted(long, reverse=True)[:4])
            out.append(Finding(
                "M2MAP-QA-004", "minor", str(root),
                "The map edge is open: no mountain, no wall of buildings, no water horizon -- the "
                "player sees where the world stops.",
                "%d m of edge open in all; longest %s (official outdoor maps: 0 m, an entrance "
                "at most 32 m)" % (total, desc),
                "Wall it in -- a border ridge (`reference/taste.md`, ring lift median 13.5 m) or a "
                "curtain wall of buildings -- or end it in water; a gap only where an entrance bends "
                "out of sight (`thunder_zone_gate_east`)."))
    return out

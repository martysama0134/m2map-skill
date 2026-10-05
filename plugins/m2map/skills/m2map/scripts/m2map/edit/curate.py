"""curate -- repair the worst cases the quality rules flag, on somebody's map.

`audit/quality.py` finds them (M2MAP-QA-001..004); this fixes them, one fix per
rule, each confined to a region (sectors) and never touching anything else:

==========  =========  ==============================================================
fix         rule       what it writes
==========  =========  ==============================================================
``rock``    QA-001     BLOCK on stone/rock/cliff-painted ground of 25 deg or more
                       (`attr.atr`; rule 19: the cliff paint is the unwalkable ground)
``attr``    QA-002     a whole attr layer for a map that has none: BLOCK on slope
                       >= 20 deg (the Youden cut over 59 slope_driven maps,
                       `attributes.md`), on steep rock, on a 4 m border band, under
                       every Building of 2 m or more (its `.mdatr` collision box,
                       turned by its roll: 51 of 103 maps paint it) and under
                       water; roads stay open (rule 21); blocks under 30 m2 that are
                       not rock are dropped as noise (rule 31); flat ground the
                       terrain strands is sealed (`gen/walkable.py`). Rebuilt over
                       Ymir's own maps with their attr wiped: 92-94% of cells agree
                       on a1, a2, trent, 85% on n_desert_01 (dunes over 20 deg it
                       leaves walkable), 77% on milgyo (its low ground is a separate
                       piece the cut cannot tell from a played one)
``road``    QA-003     a dithered rim on a road slot: road paint stippled up to 3 m
                       out into the ground and ground up to 2 m into the road, thinning
                       with distance (rule 19, `taste.md` 1.9). Seeded, so the same
                       map gets the same rim
``border``  QA-004     a mountain rim raised along exactly the edge stretches the
                       audit calls open -- 15 m over 48 m in (outdoor ring lift
                       median 13.5 m), tapered 32 m at either end so it does not stop
                       in a cliff, relief-broken like the generator's rim, painted with
                       the map's commonest rock where it is steep and blocked where it
                       rose; objects standing on it are lifted with it
``water``   WTR-005    the plane carried over the shallows (ground within 8 m of the
            WTR-004    surface) for up to 16 m, until the terrain rises through it and
            ATR-002    draws the waterline instead of the plane's 2 m grid; then WATER
                       set under all visible water IF the map flags its water at all
                       (28 official maps never do; BLOCK too where the map blocks
                       it), and cleared where no plane is
==========  =========  ==============================================================

Every fix reads and writes the whole map in memory -- shared sector borders stay
identical -- and only sectors whose bytes changed are written back. `server_attr`
is regenerated whenever any attr changed (rule 14). The original is copied
beside the map first unless told not to.
"""

from __future__ import annotations

import datetime
import pathlib
import shutil
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import numpy as np

from ..audit import quality as Q
from ..codec import server_attr as sa_codec
from ..codec.areadata import AreaData
from ..codec.attr import AttrMap, read_attr, write_attr, ATTR_BLOCK, ATTR_WATER
from ..codec.height import HeightMap, read_height, write_height
from ..codec.setting import Setting
from ..codec.tile import TileMap, read_tile, write_tile
from ..codec.water import WaterMap, read_water, write_water
from ..gen import terrain as T
from ..gen import texture as TX
from ..gen import walkable

FIXES = ("rock", "attr", "road", "border", "water", "water_level")
BLOCK_SLOPE_DEG = 20.0
BORDER_BAND_M = 4
NOISE_BLOCK_M2 = 30
STRANDED_MAIN_SHARE = 0.6
RIM_OUT_M, RIM_IN_M = 3, 2
RIM_OUT_P, RIM_IN_P = 0.55, 0.35
RIDGE_LIFT_CM = 1500.0
RIDGE_WIDTH_M = 48.0
RIDGE_TAPER_M = 32.0
RIDGE_PAINT_DEG = 20.0
RIDGE_BLOCK_CM = 150.0
RIDGE_CREST = 0.35
RIDGE_WANDER = 0.35
SHORE_GROW_CELLS = 8            # 16 m: how far a plane may reach for its shore
SHORE_MAX_DEPTH_CM = 800.0      # never over a lip (gen/water.py PLANE_MAX_DEPTH_CM)
#: Water calibration over the 114 corpus maps with terrain (56 with deep water):
#: stray WATER bits reach 469 cells / 3.6% of the flagged ones (eastplain_03)
#: except duel and its copy pvp_arena, 10524 / 32% -- the catalog's ATR-002 case.
STRAY_WATER_MIN, STRAY_WATER_SHARE = 1000, 0.05
#: The exposed shore runs 0.2-2.7% on outdoor maps; over 30% only on milgyo,
#: smhgate_c1 and eastplain_03, pools set into carved floors (WTR-005, info).
SHORE_EXPOSED_MAX = 0.30
#: Whether a map flags its water at all is a CONVENTION: 28 official maps leave
#: 85-100% of their deep water unflagged (e1, t2-t4, wl_01, capedragonhead...),
#: while the maps that flag it miss 0-23%. WTR-004 is judged only on a map that
#: flags (>= half its deep water), and only past 25% missed: no official map.
FLAGS_WATER_SHARE, WATER_MISSED_MAX = 0.5, 0.25
DEEP_CM = 50.0
#: A perched plane -- its surface over flat banks, so no growth finds a shore --
#: gets a bank instead: the ground under its new edge raised this far over the
#: surface, held flat BANK_HOLD vertices (2 m each), eased back to the old ground
#: over BANK_FEATHER more.
BANK_CM = 10.0
#: How far an upper level may spread down a seam, cells (2 m).
SEAM_SPREAD_CELLS = 16
#: ...and only over ground it covers this shallowly: deeper, the ground between
#: two levels is the bank of a real drop, not a hole (a 5 m cascade spread its
#: upper level down the slope and stood a water cliff at the bottom).
SEAM_MAX_DEPTH_CM = 100.0
#: `water_level`: levels of one body within this of their neighbour become one.
#: Ymir does step its rivers -- a1's runs 5 levels over 85 m -- so a real drop
#: stays a step; a lake cut into bands a metre apart does not.
LEVEL_SPAN_CM = 300.0
#: Two levels may only meet where TERRAIN parts them: the shared edge buried in
#: ground over the higher surface. "Two water levels close enough will always be
#: terrible" (the user); the corpus agrees -- visible contact edges run 0-36 a
#: map (12zi_stage 509, e1 75 aside), the test river 188. Over this: WTR-006.
CONTACT_MAX = 40
#: Separating them: the upper plane is pulled back off the drop through cells it
#: covers deeper than SEP_DEPTH_CM (up to SEP_REACH cells), and a sill raised to
#: SILL_CM over its surface under its new edge.
SEP_DEPTH_CM = 100.0
#: 12 cells left a 6.5 m dam mid-slab on the test river: a slab that wide IS the
#: fault, so it is pulled back until the upper water is shallow, wherever that is.
SEP_REACH = 256
SILL_CM = 30.0
SILL_HOLD, SILL_FEATHER = 1, 6
BANK_HOLD = 2
BANK_FEATHER = 6


@dataclass
class Grids:
    """A whole map in memory: vertex heights (cm), tiles, attr, plus the originals."""

    root: pathlib.Path
    setting: Setting
    size: Tuple[int, int]
    sectors: List[str]
    height: np.ndarray
    tiles: np.ndarray
    attr: np.ndarray
    mt: object
    orig: Dict[str, np.ndarray] = field(default_factory=dict)
    #: water surface per 2 m cell (cm), -inf where dry
    water: Optional[np.ndarray] = None
    objects_dz: Optional[np.ndarray] = None
    #: tiles whose trees go: ground a fix turned into bare rock
    no_trees: Optional[np.ndarray] = None
    notes: List[str] = field(default_factory=list)
    #: where to point the camera for a before/after pair, tile metres
    spots: Dict[str, Tuple[float, float]] = field(default_factory=dict)

    @property
    def slope_tiles(self) -> np.ndarray:
        gy, gx = np.gradient(self.height, 200.0)
        s = np.degrees(np.arctan(np.hypot(gx, gy)))
        H, W = self.tiles.shape
        return np.repeat(np.repeat(s, 2, 0), 2, 1)[:H, :W]

    @property
    def submerged_cells(self) -> np.ndarray:
        """2 m cells whose water surface is above the ground: the only real water.
        A buried plane is invisible and unflagged in every shipped map. Ground is
        the cell's own vertex, as `M2MAP-WTR-004` reads it."""
        return self.water > self.height[:-1, :-1]

    @property
    def submerged(self) -> np.ndarray:
        H, W = self.tiles.shape
        return np.repeat(np.repeat(self.submerged_cells, 2, 0), 2, 1)[:H, :W]

    def rock_ids(self) -> List[int]:
        out = []
        for idx in self.mt.used_indices():
            name = (self.mt.slot_name(idx) or "").replace("\\", "/").lower().split("/")[-1]
            if any(k in name for k in Q.ROCK_MOTIFS):
                out.append(idx)
        return out


def load(map_dir, textureset_dir=None) -> Grids:
    from ..mine import tile_stats
    root = pathlib.Path(map_dir)
    st = Setting.load(root / "setting.txt")
    W, H = st.map_size
    pack = pathlib.Path(textureset_dir).parent if textureset_dir else tile_stats.DEFAULT_PACK_DIR
    mt = tile_stats.load_map(root, pack)
    if mt is None:
        raise ValueError("%s has no tile.raw: nothing to curate" % root)
    sectors = sorted(p.name for p in root.iterdir() if p.is_dir() and len(p.name) == 6 and p.name.isdigit()
                     and int(p.name[:3]) < W and int(p.name[3:]) < H)
    hv = np.zeros((H * 128 + 1, W * 128 + 1))
    att = np.zeros((H * 256, W * 256), np.uint8)
    tiles = np.zeros((H * 256, W * 256), np.uint8)
    wsurf = np.full((H * 128, W * 128), -np.inf)          # water surface per 2 m cell, cm
    for name in sectors:
        sx, sy = int(name[:3]), int(name[3:])
        d = root / name
        if (d / "height.raw").is_file():
            hv[sy * 128:sy * 128 + 129, sx * 128:sx * 128 + 129] = \
                read_height(d / "height.raw").raw[1:130, 1:130].astype(float) * T.HEIGHT_SCALE
        if (d / "attr.atr").is_file():
            att[sy * 256:(sy + 1) * 256, sx * 256:(sx + 1) * 256] = read_attr(d / "attr.atr").cells
        if (d / "tile.raw").is_file():
            tiles[sy * 256:(sy + 1) * 256, sx * 256:(sx + 1) * 256] = read_tile(d / "tile.raw").tiles
        if (d / "water.wtr").is_file():
            wm = read_water(d / "water.wtr")
            lv = np.array(wm.world_heights(T.HEIGHT_SCALE) + [-np.inf])
            idx = np.where(wm.cells == 0xFF, len(lv) - 1, np.minimum(wm.cells, len(lv) - 1))
            wsurf[sy * 128:(sy + 1) * 128, sx * 128:(sx + 1) * 128] = lv[idx]
    g = Grids(root, st, (W, H), sectors, hv, tiles, att, mt)
    g.water = wsurf
    g.orig = {"height": hv.copy(), "tiles": tiles.copy(), "attr": att.copy(), "water": wsurf.copy()}
    return g


def region_mask(g: Grids, sectors: Optional[Iterable[str]]) -> np.ndarray:
    """Tile mask of the chosen sectors ("XXXYYY" names); None = the whole map."""
    H, W = g.tiles.shape
    if not sectors:
        return np.ones((H, W), bool)
    m = np.zeros((H, W), bool)
    for name in sectors:
        sx, sy = int(name[:3]), int(name[3:])
        m[sy * 256:(sy + 1) * 256, sx * 256:(sx + 1) * 256] = True
    return m


# --------------------------------------------------------------------------
# fixes
# --------------------------------------------------------------------------

def fix_rock(g: Grids, region: np.ndarray) -> str:
    rock = np.isin(g.tiles, g.rock_ids()) & (g.slope_tiles >= Q.STEEP_DEG) & region
    new = rock & ((g.attr & ATTR_BLOCK) == 0)
    g.attr[new] |= ATTR_BLOCK
    return "rock: blocked %d m2 of walkable steep rock" % int(new.sum())


def fix_attr(g: Grids, region: np.ndarray) -> str:
    from ..mine import roads
    slope = g.slope_tiles
    H, W = g.attr.shape
    rock = np.isin(g.tiles, g.rock_ids())
    block = (slope >= BLOCK_SLOPE_DEG) | (rock & (slope >= Q.STEEP_DEG))
    # drop specks that are not rock: a 2 m bump is not a wall (rule 31)
    block = _drop_small(block & ~rock, NOISE_BLOCK_M2) | (block & rock)
    b = BORDER_BAND_M
    edge = np.zeros((H, W), bool)
    edge[:b, :] = edge[-b:, :] = edge[:, :b] = edge[:, -b:] = True
    block |= edge
    # gentle ground the terrain cuts off from the playable interior: Ymir strands
    # none (`gen/walkable.py`; the crests of a1's rim are flat and 100% blocked).
    # Terrain only -- a river or a row of houses splits a map without stranding
    # either side. And only when one piece IS the interior: map_a2's ramps are
    # steeper than the cut, so slope alone breaks it into a dozen 4-12% pieces,
    # all of them played; there the stranded ground is left to the user
    free = ~block & (g.tiles > 0)
    main = walkable.reachable(free)
    stranded = free & ~main
    if main.sum() >= STRANDED_MAIN_SHARE * free.sum():
        block |= stranded
    elif stranded.any():
        g.notes.append("attr: slope splits the walkable ground into pieces (largest %.0f%%); "
                       "none was sealed as stranded -- look for flat shelves left walkable"
                       % (100.0 * main.sum() / max(free.sum(), 1)))
    block |= _building_footprints(g)
    block |= (g.attr & ATTR_WATER) != 0
    wet = g.submerged & region
    g.attr[wet] |= ATTR_WATER
    block |= g.submerged
    try:
        paths = [s["index"] for s in roads.classify_path_indices(g.mt) if s.get("is_path")]
    except Exception:                                      # noqa: BLE001
        paths = []
    if paths:
        block &= ~(np.isin(g.tiles, paths) & ~edge & ((g.attr & ATTR_WATER) == 0))
    # additive: whatever block somebody did paint stays
    before = int(((g.attr & ATTR_BLOCK) != 0)[region].sum())
    g.attr[block & region] |= ATTR_BLOCK
    after = int(((g.attr & ATTR_BLOCK) != 0)[region].sum())
    return "attr: blocked share of the region %.1f%% -> %.1f%% (slope >= %d deg, steep rock, %d m band, water; %d road slot(s) kept open)" % (
        100.0 * before / max(region.sum(), 1), 100.0 * after / max(region.sum(), 1), BLOCK_SLOPE_DEG, b, len(paths))


def fix_road(g: Grids, region: np.ndarray, seed: int = 0) -> str:
    """Dither the rim of every road slot QA-003 flags; roads already dithered stay."""
    from ..mine import roads
    stats = roads.classify_path_indices(g.mt)
    rng = np.random.default_rng(seed)
    keep_out = np.isin(g.tiles, g.rock_ids()) | ((g.attr & ATTR_WATER) != 0) | (g.tiles == 0)
    done = []
    for s in stats:
        if not s.get("is_path"):
            continue
        idx = s["index"]
        road = g.tiles == idx
        if road.sum() < Q.ROAD_MIN_TILES or Q.rim_specks(road) >= Q.SPECKS_MIN:
            continue
        # the ground beside the road, carried inward so a rim tile knows what to become
        ground = np.where(road, 0, g.tiles).astype(np.uint8)
        for _ in range(RIM_IN_M + 1):
            ground = _fill_from_neighbours(ground, road)
        changed = 0
        before = g.tiles.copy()
        for k in range(1, RIM_OUT_M + 1):                   # road stippled out
            ring = Q._dilate(road, k) & ~Q._dilate(road, k - 1)
            p = RIM_OUT_P * (1.0 - (k - 1) / RIM_OUT_M)
            hit = ring & region & ~keep_out & (rng.random(road.shape) < p)
            g.tiles[hit] = idx
            changed += int(hit.sum())
        for k in range(1, RIM_IN_M + 1):                    # ground stippled in
            ring = road & Q._dilate(~road, k) & ~Q._dilate(~road, k - 1)
            p = RIM_IN_P * (1.0 - (k - 1) / RIM_IN_M)
            hit = ring & region & (ground > 0) & (rng.random(road.shape) < p)
            g.tiles[hit] = ground[hit]
            changed += int(hit.sum())
        done.append("slot %d: %d tiles" % (idx, changed))
        ys, xs = np.nonzero(g.tiles != before)
        if len(ys):
            k = len(ys) // 2                                # a tile the dither actually touched
            g.spots["road%d" % idx] = (float(xs[k]), float(ys[k]))
    return "road: rim dithered on %s" % (", ".join(done) or "no hard-edged road slot")


def fix_border(g: Grids, region: np.ndarray, seed: int = 0) -> str:
    H, W = g.tiles.shape
    hu = np.repeat(np.repeat(g.height, 2, 0), 2, 1)[:H, :W]
    walk = (g.attr & ATTR_BLOCK) == 0
    water = (g.attr & ATTR_WATER) != 0
    walls = Q._wall_objects(g.root, g.sectors, (H, W))
    runs = [r for r in Q.open_runs(Q.edge_stretches(hu, walk, water, g.tiles, walls))
            if r[0] > Q.OPEN_EDGE_OK_M]
    if not runs:
        return "border: no open edge over %d m" % Q.OPEN_EDGE_OK_M
    vh, vw = g.height.shape
    weight = np.zeros((vh, vw))
    ys = np.arange(vh, dtype=float)[:, None]
    xs = np.arange(vw, dtype=float)[None, :]
    width = RIDGE_WIDTH_M / 2.0                             # in 2 m vertices
    taper = RIDGE_TAPER_M / 2.0
    used = []
    rng = np.random.default_rng(seed)
    # the band's reach wanders along the edge, so its foot is no ruler line
    reach = width * (1.0 - RIDGE_WANDER + 2.0 * RIDGE_WANDER * T.fbm(rng, vh, vw, octaves=2, base_cells=24))
    for length, (side, start) in runs:
        a, b = start / 2.0, (start + length) / 2.0          # metres -> vertices
        if side in "NS":
            along = xs
            d = ys if side == "N" else (vh - 1) - ys
        else:
            along = ys
            d = xs if side == "W" else (vw - 1) - xs
        t_along = np.clip(np.minimum(along - (a - taper), (b + taper) - along) / taper, 0.0, 1.0)
        # a face, then a crest: the outer RIDGE_CREST of the band is the top, so
        # the rim reads as a mountain and not as a ramp up to the edge
        t_in = np.clip((1.0 - d / reach) / (1.0 - RIDGE_CREST), 0.0, 1.0)
        w = t_in * t_along
        weight = np.maximum(weight, w * w * (3.0 - 2.0 * w))
        used.append("%s %d-%d m" % (side, start, start + length))
        mid, inset = start + length / 2.0, 40.0              # look at the foot of the new rim
        g.spots["edge_%s%d" % (side, start)] = {
            "N": (mid, inset), "S": (mid, H - inset), "W": (inset, mid), "E": (W - inset, mid)}[side]
    relief = T.fbm(rng, vh, vw, octaves=3, base_cells=40, gain=0.55)
    lift = weight * (0.62 + 0.76 * relief) * RIDGE_LIFT_CM
    rv = np.zeros((vh, vw), bool)                           # region on the vertex grid
    rv[:-1, :-1] = region[::2, ::2]
    rv[-1, :-1] = rv[-2, :-1]
    rv[:, -1] = rv[:, -2]
    lift *= rv
    g.height = g.height + lift
    lt = np.repeat(np.repeat(lift, 2, 0), 2, 1)[:H, :W]
    slope = g.slope_tiles
    rock_ids = g.rock_ids()
    if rock_ids:
        commonest = max(rock_ids, key=lambda i: int((g.tiles == i).sum()))
        wt = np.repeat(np.repeat(weight, 2, 0), 2, 1)[:H, :W]
        skin = _rock_skin(lt, wt, slope, region, rng)
        g.tiles[skin] = commonest
        # a tree on the bare rock of a cliff face reads as a mistake (the user,
        # on the first rim): the ones it lifted there go
        face = skin & (lt > RIDGE_BLOCK_CM)                 # the massif, not its speckled foot
        g.no_trees = face if g.no_trees is None else (g.no_trees | face)
    else:
        g.notes.append("border: the palette has no rock texture; the ridge is not repainted")
    g.attr[(lt > RIDGE_BLOCK_CM) & region] |= ATTR_BLOCK
    g.objects_dz = lift if g.objects_dz is None else g.objects_dz + lift
    dried = _dry_buried(g, region)
    if dried:
        g.notes.append("border: the rim rose through water; WATER cleared from %d cells it lifted dry" % dried)
    return "border: ridge raised on %s (up to %.0f m)" % (", ".join(used), lift.max() / 100.0)


def _water_convention(g: Grids):
    """(deep submerged cells, those carrying WATER on any of their 4 attr tiles,
    whether this map flags its water at all)."""
    deep = g.submerged_cells & ((g.water - g.height[:-1, :-1]) > DEEP_CM)
    f = (g.attr & ATTR_WATER) != 0
    h, w = deep.shape
    fc = f[0::2, 0::2][:h, :w] | f[1::2, 0::2][:h, :w] | f[0::2, 1::2][:h, :w] | f[1::2, 1::2][:h, :w]
    share = float((deep & fc).sum()) / max(int(deep.sum()), 1)
    return deep, fc, bool(deep.sum() >= 100 and share >= FLAGS_WATER_SHARE)


def water_findings(g: Grids) -> List[Dict]:
    """The three water rules, map-wide, in the menu's shape. The audit reads them
    per sector (`audit/rules.py`); a plane runs across sector borders."""
    out = []
    H, W = g.tiles.shape
    wet_t = np.repeat(np.repeat(np.isfinite(g.water), 2, 0), 2, 1)[:H, :W]
    flag = (g.attr & ATTR_WATER) != 0
    stray = flag & ~wet_t
    if stray.sum() > STRAY_WATER_MIN and stray.sum() > STRAY_WATER_SHARE * flag.sum():
        out.append({"rule": "M2MAP-ATR-002", "severity": "major", "fix": "water",
                    "where": Q._where(stray), "symptom": "Player swims in mid-air.",
                    "detail": "%d attr cells carry WATER with no water plane over them (%.0f%% of the "
                              "flagged; official maps <= 3.6%% bar duel)" % (int(stray.sum()), 100.0 * stray.sum() / flag.sum())})
    deep, fc, flags = _water_convention(g)
    missed = deep & ~fc
    if flags and missed.sum() > WATER_MISSED_MAX * deep.sum():
        m_t = np.repeat(np.repeat(missed, 2, 0), 2, 1)[:H, :W]
        out.append({"rule": "M2MAP-WTR-004", "severity": "major", "fix": "water",
                    "where": Q._where(m_t), "symptom": "Some lakes swim, some are walked on.",
                    "detail": "this map flags its water but %d of %d deep cells are missed (official "
                              "maps that flag: 0-23%%)" % (int(missed.sum()), int(deep.sum()))})
    holes = seam_holes(g)
    banded = [(levels, grp) for body, levels in water_bodies(g) for grp in _level_groups(levels, LEVEL_SPAN_CM)]
    if banded:
        out.append({"rule": "curate:water_level", "severity": "choice", "fix": "water_level",
                    "where": Q._where(np.repeat(np.repeat(holes, 2, 0), 2, 1)[:H, :W]) if holes.any() else "",
                    "symptom": "Water cut into levels a little apart: the band edges show as strips of sand.",
                    "detail": "%d run(s) of levels within %.0f m of each other (%s); %d cells of bare ground "
                              "between two levels. Ymir steps descending rivers too (a1: 5 levels over 85 m) -- "
                              "a choice, not a fault: one level suits a lake or a slow reach"
                              % (len(banded), LEVEL_SPAN_CM / 100,
                                 ", ".join("%.1f-%.1f m" % (g_[0] / 100, g_[-1] / 100) for _, g_ in banded[:4]),
                                 int(holes.sum()))})
    n_contacts, up_cells, _ = level_contacts(g)
    if n_contacts > CONTACT_MAX:
        out.append({"rule": "M2MAP-WTR-006", "severity": "minor", "fix": "water",
                    "where": Q._where(np.repeat(np.repeat(up_cells, 2, 0), 2, 1)[:H, :W]),
                    "symptom": "Two water levels meet in the open: a slab of water hangs over the lower one.",
                    "detail": "%d cell edges where two levels touch with no terrain between them "
                              "(official maps 0-36 bar 12zi_stage and e1) -- levels must be parted by "
                              "ground, or be one level" % n_contacts})
    b, exposed = _shore(g)
    if b.sum() >= 40 and exposed.sum() > SHORE_EXPOSED_MAX * b.sum():
        e_t = np.repeat(np.repeat(exposed, 2, 0), 2, 1)[:H, :W]
        out.append({"rule": "M2MAP-WTR-005", "severity": "info", "fix": "water",
                    "where": Q._where(e_t), "symptom": "The shoreline is a staircase of 2 m steps.",
                    "detail": "%d of %d cells on the planes' outer edge stand over ground below the "
                              "surface (outdoor maps 0.2-2.7%%); a pool set in a carved floor does this "
                              "by design" % (int(exposed.sum()), int(b.sum()))})
    return out


def _low_corner(g: Grids) -> np.ndarray:
    h = g.height
    return np.minimum.reduce([h[:-1, :-1], h[1:, :-1], h[:-1, 1:], h[1:, 1:]])


def _shore(g: Grids):
    """The water planes' outer boundary, and the part of it the player sees: an
    edge cell whose ground (any corner) is under the surface."""
    wet = np.isfinite(g.water)
    if not wet.any():
        z = np.zeros_like(wet)
        return z, z
    edge = wet & ~_erode4(wet)
    edge[0, :] = edge[-1, :] = edge[:, 0] = edge[:, -1] = False   # the map's own rim
    return edge, edge & (g.water > _low_corner(g))


def _erode4(m):
    out = m.copy()
    out[1:] &= m[:-1]
    out[:-1] &= m[1:]
    out[:, 1:] &= m[:, :-1]
    out[:, :-1] &= m[:, 1:]
    return out


def _shift(a, dy, dx, fill):
    out = np.full_like(a, fill)
    h, w = a.shape
    out[max(dy, 0):h + min(dy, 0), max(dx, 0):w + min(dx, 0)] = \
        a[max(-dy, 0):h + min(-dy, 0), max(-dx, 0):w + min(-dx, 0)]
    return out


def fix_water(g: Grids, region: np.ndarray, level_span_cm: float = LEVEL_SPAN_CM,
              merge_levels: bool = True) -> str:
    """WTR-005, then WTR-004 and ATR-002. The plane is carried out over the
    shallows until the terrain rises through it -- the corpus waterline is drawn
    by the ground, not by the plane's 2 m grid (`gen/water.py` PLANE_OVERRUN) --
    and then the WATER bit is made to match the water the player sees."""
    rc = region[::2, ::2][:g.water.shape[0], :g.water.shape[1]]
    merged = fix_water_level(g, region, level_span_cm) if merge_levels else ""
    contacts0 = level_contacts(g)[0]
    pulled, sills = _separate_levels(g, rc)
    holes0 = int(seam_holes(g).sum())
    seams = _close_seams(g, rc)
    _, exp0 = _shore(g)
    before = np.isfinite(g.water)
    grown = 0
    for _ in range(SHORE_GROW_CELLS):
        _, exposed = _shore(g)
        if not exposed.any():
            break
        src = np.where(exposed, g.water, -np.inf)
        best = np.maximum.reduce([_shift(src, dy, dx, -np.inf)
                                  for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))])
        # the dry neighbours of an exposed edge -- never over a lip
        take = (~np.isfinite(g.water) & np.isfinite(best) & rc
                & (g.height[:-1, :-1] >= best - SHORE_MAX_DEPTH_CM))
        if not take.any():
            break
        g.water[take] = best[take]
        grown += int(take.sum())
    # a front that never found its shore flooded flat ground: take it back, and
    # bank the plane where it was
    _, exposed = _shore(g)
    new = np.isfinite(g.water) & ~before
    lost = _flood(exposed & new, new)
    g.water[lost] = -np.inf
    grown -= int(lost.sum())
    banked = _bank(g, rc)
    b, exp1 = _shore(g)
    H, W = g.tiles.shape
    flag = (g.attr & ATTR_WATER) != 0
    # Flag the water only on a map that flags its water (28 official maps never
    # do), and block it too only where this map blocks what it flagged
    _, _, flags = _water_convention(g)
    add = np.zeros_like(flag)
    blocks_water = False
    if flags:
        was = g.submerged & flag
        blocks_water = float(((g.attr[was] & ATTR_BLOCK) != 0).mean()) > 0.5
        add = g.submerged & region & ~flag
        g.attr[add] |= np.uint8(ATTR_WATER | (ATTR_BLOCK if blocks_water else 0))
    wet_t = np.repeat(np.repeat(np.isfinite(g.water), 2, 0), 2, 1)[:H, :W]
    stray = flag & ~wet_t & region
    g.attr[stray] &= np.uint8(~ATTR_WATER & 0xFF)
    _dry_buried(g, region)
    if exp0.any():
        ys, xs = np.nonzero(exp0)
        k = len(ys) // 2
        g.spots["shore"] = (float(xs[k] * 2), float(ys[k] * 2))
    return ((merged + "; " if merged else "") +
            "water: levels meeting with no terrain between %d -> %d edges (%d cells of hanging "
            "slab pulled back, %d cells of sill); " % (contacts0, level_contacts(g)[0], pulled, sills) +
            "seam holes between levels %d -> %d (%d cells given to the upper level); "
            "plane carried %d m2 onto its shore, banked %d m of perched edge, exposed edge "
            "%d -> %d of %d cells; %s; WATER cleared from %d cells with no water over them"
            % (holes0, int(seam_holes(g).sum()), seams,
               grown * 4, banked * 2, int(exp0.sum()), int(exp1.sum()), int(b.sum()),
               ("WATER set on %d cells%s" % (int(add.sum()), " and BLOCK, as this map blocks its water"
                                             if blocks_water else "")) if flags
               else "this map does not flag its water (like 28 official maps), so none was added",
               int(stray.sum())))


def _dry_buried(g: Grids, region: np.ndarray) -> int:
    """Clear WATER where this run raised the ground out of the water: a buried
    plane is unflagged in every shipped map."""
    was = g.orig["water"] > g.orig["height"][:-1, :-1]
    H, W = g.tiles.shape
    dry = np.repeat(np.repeat(was & ~g.submerged_cells, 2, 0), 2, 1)[:H, :W]
    hit = dry & region & ((g.attr & ATTR_WATER) != 0)
    g.attr[hit] &= np.uint8(~ATTR_WATER & 0xFF)
    return int(hit.sum())


def _high_corner(g: Grids) -> np.ndarray:
    h = g.height
    return np.maximum.reduce([h[:-1, :-1], h[1:, :-1], h[:-1, 1:], h[1:, 1:]])


def seam_holes(g: Grids) -> np.ndarray:
    """Cells where two water levels meet and bare ground shows between them: the
    cell belongs to the LOWER plane, its ground pokes out of that plane, and a
    neighbour's HIGHER plane would still cover it. The generator's river bands
    leave these (the test fixture: 188); the corpus 0-36 visible steps a map."""
    w = g.water
    up = np.maximum.reduce([_shift(np.where(np.isfinite(w), w, -np.inf), dy, dx, -np.inf)
                            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))])
    return (np.isfinite(w) & (up > w + 10.0) & (_high_corner(g) > w) & (_low_corner(g) < up)
            & (_low_corner(g) >= up - SEAM_MAX_DEPTH_CM))


def _close_seams(g: Grids, rc: np.ndarray) -> int:
    """Give each seam hole to the higher level beside it, repeatedly: the bare
    strip between the waters goes under the upper plane, and the levels then
    meet as a step of water where the ground drops, not as a gap."""
    moved = 0
    for _ in range(SEAM_SPREAD_CELLS):
        holes = seam_holes(g) & rc
        if not holes.any():
            break
        w = g.water
        up = np.maximum.reduce([_shift(np.where(np.isfinite(w), w, -np.inf), dy, dx, -np.inf)
                                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))])
        g.water[holes] = up[holes]
        moved += int(holes.sum())
    return moved


def water_bodies(g: Grids):
    """Connected water planes: (cells mask, sorted distinct levels cm)."""
    from ..mine import tile_stats
    wet = np.isfinite(g.water)
    lab = tile_stats._components(wet)
    lab = lab[0] if isinstance(lab, tuple) else lab
    out = []
    for i in range(1, int(lab.max()) + 1 if lab.size else 1):
        m = lab == i
        if m.sum() >= 50:
            out.append((m, sorted(float(v) for v in np.unique(g.water[m]))))
    return out


def _level_groups(levels, span_cm):
    """Neighbouring levels within span_cm of each other, as groups."""
    groups = [[levels[0]]]
    for v in levels[1:]:
        if v - groups[-1][-1] <= span_cm and v - groups[-1][0] <= span_cm:
            groups[-1].append(v)
        else:
            groups.append([v])
    return [grp for grp in groups if len(grp) > 1]


def fix_water_level(g: Grids, region: np.ndarray, span_cm: float = LEVEL_SPAN_CM) -> str:
    """One level for each run of a body's levels within span_cm: the lowest, so
    the upper reach shows its ground instead of water standing over the lower. A lake cut into bands shows its band
    edges as strips of sand (the user, on the first curated map); a real drop of
    a river stays a step."""
    rc = region[::2, ::2][:g.water.shape[0], :g.water.shape[1]]
    low = _low_corner(g)
    done = []
    for body, levels in water_bodies(g):
        for grp in _level_groups(levels, span_cm):
            cells = body & rc & np.isin(g.water, grp)
            if not cells.any():
                continue
            # the LOWEST level: it floods nothing and perches nothing. Picking the
            # one that kept most water visible chose 5.5 m for a 3.1-5.5 m reach,
            # stood it over 1-3 m ground and the shore fix built 4.8 m dykes
            best = grp[0]
            g.water[cells] = best
            done.append("%d levels %.1f-%.1f m -> %.1f m" % (len(grp), grp[0] / 100, grp[-1] / 100, best / 100))
    return "water_level: %s" % ("; ".join(done) or "no body has levels within %.0f m of each other" % (span_cm / 100))


def level_contacts(g: Grids):
    """Edges where two water levels meet with no terrain between: both cells wet,
    levels apart, and a vertex of the shared edge under the higher surface.
    Returns (edge count, upper-side cells, the lower level each of them meets)."""
    w, h = g.water, g.height
    up_cells = np.zeros(w.shape, bool)
    meets = np.full(w.shape, -np.inf)
    n = 0
    with np.errstate(invalid="ignore"):
        for axis in (0, 1):
            if axis == 1:
                a, b = w[:, :-1], w[:, 1:]
                e = np.minimum(h[:-1, 1:-1], h[1:, 1:-1])
            else:
                a, b = w[:-1, :], w[1:, :]
                e = np.minimum(h[1:-1, :-1], h[1:-1, 1:])
            m = np.isfinite(a) & np.isfinite(b) & (np.abs(a - b) > 10.0) & (e < np.maximum(a, b))
            n += int(m.sum())
            a_up, b_up = m & (a > b), m & (b > a)
            sa = (slice(None), slice(0, -1)) if axis == 1 else (slice(0, -1), slice(None))
            sb = (slice(None), slice(1, None)) if axis == 1 else (slice(1, None), slice(None))
            up_cells[sa] |= a_up
            up_cells[sb] |= b_up
            meets[sa] = np.where(a_up, np.maximum(meets[sa], b), meets[sa])
            meets[sb] = np.where(b_up, np.maximum(meets[sb], a), meets[sb])
    return n, up_cells, meets


def _separate_levels(g: Grids, rc: np.ndarray) -> Tuple[int, int]:
    """Part every pair of touching levels with terrain. The upper plane is pulled
    back off the drop -- through the cells it covers more than SEP_DEPTH_CM deep,
    the slab that hung over the slope -- each of them handed to the lower level
    where the ground is under it, left dry where not; then the ground under the
    upper plane's new edge is raised SILL_CM over its surface, so both planes end
    inside terrain."""
    pulled = sills = 0
    low = _low_corner(g)
    for _ in range(4):
        n, up_cells, meets = level_contacts(g)
        if not n:
            break
        for L in sorted({float(v) for v in g.water[up_cells & rc]}, reverse=True):
            mine = (g.water == L) & rc
            seed = up_cells & mine
            if not seed.any():
                continue
            lower = float(meets[seed].max())
            deep = mine & ((L - low) > SEP_DEPTH_CM)
            slab = seed & deep
            for _ in range(SEP_REACH):
                nxt = (slab | _shift(slab, 1, 0, False) | _shift(slab, -1, 0, False)
                       | _shift(slab, 0, 1, False) | _shift(slab, 0, -1, False)) & deep
                if (nxt == slab).all():
                    break
                slab = nxt
            g.water[slab & (low < lower)] = lower
            g.water[slab & (low >= lower)] = -np.inf
            pulled += int(slab.sum())
            # the new edge of the upper plane, wherever it meets lower water or dry ground
            left = (g.water == L) & rc
            other = ~(g.water == L)
            edge = left & (_shift(other, 1, 0, False) | _shift(other, -1, 0, False)
                           | _shift(other, 0, 1, False) | _shift(other, 0, -1, False))
            edge &= _dilate_cells(slab | seed, 1)
            # the sill: up to SILL_CM over the upper surface under the plane's new
            # edge, eased down the dry side and into the lower water
            _raise_eased(g, _cell_vertices(edge, np.full(edge.shape, L + SILL_CM)),
                         left & ~edge, rc, SILL_HOLD, SILL_FEATHER)
            sills += int(edge.sum())
            low = _low_corner(g)
    return pulled, sills


def _dilate_cells(m, k):
    out = m.copy()
    for _ in range(k):
        out = out | _shift(out, 1, 0, False) | _shift(out, -1, 0, False) | _shift(out, 0, 1, False) | _shift(out, 0, -1, False)
    return out


def _flood(seed, within):
    """The cells of `within` 4-connected to `seed`."""
    out = seed & within
    while True:
        nxt = (out | _shift(out, 1, 0, False) | _shift(out, -1, 0, False)
               | _shift(out, 0, 1, False) | _shift(out, 0, -1, False)) & within
        if (nxt == out).all():
            return out
        out = nxt


def _bank(g: Grids, rc: np.ndarray) -> int:
    """Carry each still-exposed edge one cell out and raise the ground under that
    cell to BANK_CM over the surface, feathered back outward: the terrain then
    rises through the plane at its edge and draws the waterline."""
    _, exposed = _shore(g)
    if not exposed.any():
        return 0
    src = np.where(exposed, g.water, -np.inf)
    best = np.maximum.reduce([_shift(src, dy, dx, -np.inf)
                              for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))])
    rim = ~np.isfinite(g.water) & np.isfinite(best) & rc
    if not rim.any():
        return 0
    g.water[rim] = best[rim]
    _raise_eased(g, _cell_vertices(rim, best + BANK_CM), np.isfinite(g.water) & ~rim, rc,
                 BANK_HOLD, BANK_FEATHER)
    return int(rim.sum())


def _cell_vertices(cells, values):
    """Per vertex, the highest value of the cells it is a corner of (-inf: none)."""
    vh, vw = cells.shape[0] + 1, cells.shape[1] + 1
    out = np.full((vh, vw), -np.inf)
    v = np.where(cells, values, -np.inf)
    for dy in (0, 1):
        for dx in (0, 1):
            out[dy:dy + cells.shape[0], dx:dx + cells.shape[1]] = np.maximum(
                out[dy:dy + cells.shape[0], dx:dx + cells.shape[1]], v)
    return out


def _raise_eased(g: Grids, target: np.ndarray, keep_cells: np.ndarray, rc: np.ndarray,
                 hold: int, feather: int) -> None:
    """Raise the ground to `target` (per vertex, -inf = leave), hold it for `hold`
    vertices outward, then ease it back to the old ground over `feather` more --
    a landform, not a kerb. Vertices of `keep_cells` (water that must keep its
    depth) and outside the region are never touched by the easing. Objects ride."""
    vh, vw = g.height.shape
    keepv = np.isfinite(_cell_vertices(keep_cells, np.zeros(keep_cells.shape)))
    rv = np.isfinite(_cell_vertices(rc, np.zeros(rc.shape)))
    old = g.height.copy()
    on = np.isfinite(target)
    g.height[on] = np.maximum(g.height[on], target[on])
    ring = on.copy()
    reach = target.copy()
    for k in range(1, hold + feather + 1):
        grow = np.maximum.reduce([_shift(reach, dy, dx, -np.inf)
                                  for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))])
        nxt = np.isfinite(grow) & ~ring & ~keepv & rv
        # held flat, then eased down: a 30 cm lip falling straight back to the
        # perched-under ground drew a dark kerb along the shore, and a one-cell
        # sill between two water levels stood as a wall with a 4 m cliff behind it
        t = max(0.0, (k - hold) / float(feather + 1))
        w = 1.0 - t * t * (3.0 - 2.0 * t)
        lift = np.where(nxt, old + (grow - old) * w, -np.inf)
        g.height[nxt] = np.maximum(g.height[nxt], lift[nxt])
        reach = np.where(nxt, grow, -np.inf)
        ring |= nxt
    dz = g.height - old
    g.objects_dz = dz if g.objects_dz is None else g.objects_dz + dz


def _rock_skin(lift, weight, slope, region, rng):
    """Where the new rim is painted rock: its faces and its crest, as one massif
    -- closed so the crest has no grass holes, opened so no rock speck stands
    alone -- then speckled out past its foot the way Ymir's cliffs are
    (`gen/texture.py` `_feather_massif`: ~5 tiles, decaying, then nothing)."""
    raw = (lift > RIDGE_BLOCK_CM) & ((slope >= RIDGE_PAINT_DEG) | (weight > 0.9))
    massif = TX._dilate(TX._erode(raw, 2), 2)
    massif = TX._erode(TX._dilate(massif, 3), 3) & (lift > 0)
    out = massif.copy()
    prev = massif
    for step in range(1, TX.FEATHER_REACH + 1):
        cur = TX._dilate(massif, step)
        p = TX.FEATHER_HEAD * (TX.FEATHER_DECAY ** (step - 1))
        out |= cur & ~prev & (rng.random(lift.shape) < p)
        prev = cur
    return out & region


_BOXES = None


def _boxes():
    """CRC -> collision box (cx, cy, hx, hy) cm of every Building: the `.mdatr`
    proxy where it exists (median 1.01x the painted attr, `attributes.md`), the
    GR2 box shrunk as the generator does otherwise."""
    global _BOXES
    if _BOXES is None:
        import json
        cat = pathlib.Path(Q._CATALOG)
        mods = json.loads((cat / "models.json").read_text(encoding="utf-8"))["models"]
        _BOXES = {}
        for crc, m in mods.items():
            if m.get("type") != "Building" or m.get("degenerate"):
                continue
            md = m.get("mdatr") or {}
            lo, hi = md.get("collision_bbox_min"), md.get("collision_bbox_max")
            if lo and hi:
                box = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (hi[0] - lo[0]) / 2, (hi[1] - lo[1]) / 2)
            elif m.get("size_xyz") and m.get("center"):
                sx, sy = m["size_xyz"][:2]
                box = (m["center"][0], m["center"][1], 0.45 * sx, 0.45 * sy)
            else:
                continue
            if min(box[2], box[3]) >= 100.0 and max(box[2], box[3]) < 5e4:
                _BOXES[int(crc)] = box
    return _BOXES


def _building_footprints(g: Grids) -> np.ndarray:
    """Tiles under a Building's collision box, turned by its roll (`gen/attribute.py`)."""
    import math
    boxes = _boxes()
    H, W = g.tiles.shape
    out = np.zeros((H, W), bool)
    for name in g.sectors:
        p = g.root / name / "areadata.txt"
        if not p.is_file():
            continue
        for r in AreaData.parse(p.read_bytes()).records:
            box = boxes.get(r.crc)
            if box is None:
                continue
            cx, cy, hx, hy = (v / 100.0 for v in box)
            c, s_ = math.cos(math.radians(r.roll)), math.sin(math.radians(r.roll))
            # the box centre in tiles: model offset turned, y flipped to the grid
            fx = r.x / 100.0 + cx * c - cy * s_
            fy = -r.y / 100.0 - (cx * s_ + cy * c)
            reach = int(math.ceil(math.hypot(hx, hy))) + 1
            x0, x1 = int(max(0, fx - reach)), int(min(W, fx + reach + 1))
            y0, y1 = int(max(0, fy - reach)), int(min(H, fy + reach + 1))
            if x1 <= x0 or y1 <= y0:
                continue
            ys, xs = np.mgrid[y0:y1, x0:x1]
            dx, dy = xs + 0.5 - fx, -(ys + 0.5 - fy)
            u, v = dx * c + dy * s_, -dx * s_ + dy * c
            out[y0:y1, x0:x1] |= (np.abs(u) <= hx) & (np.abs(v) <= hy)
    return out


def _drop_small(mask, min_m2):
    """Clear 4-connected components smaller than min_m2 tiles."""
    from collections import deque
    h, w = mask.shape
    seen = np.zeros_like(mask)
    out = mask.copy()
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        comp, q = [], deque([(y0, x0)])
        seen[y0, x0] = True
        while q:
            y, x = q.popleft()
            comp.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                yy, xx = y + dy, x + dx
                if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not seen[yy, xx]:
                    seen[yy, xx] = True
                    q.append((yy, xx))
        if len(comp) < min_m2:
            ys, xs = zip(*comp)
            out[list(ys), list(xs)] = False
    return out


def _fill_from_neighbours(values, holes):
    """One step of carrying non-zero values into zero cells under `holes`."""
    out = values.copy()
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        src = np.roll(values, (dy, dx), axis=(0, 1))
        take = holes & (out == 0) & (src > 0)
        out[take] = src[take]
    return out


# --------------------------------------------------------------------------
# write back
# --------------------------------------------------------------------------

def backup(map_dir) -> pathlib.Path:
    root = pathlib.Path(map_dir)
    dst = root.with_name("%s_backup_%s" % (root.name, datetime.datetime.now().strftime("%Y%m%d_%H%M%S")))
    shutil.copytree(root, dst)
    return dst


def write(g: Grids) -> List[str]:
    """Write back the sectors whose bytes changed; server_attr if any attr did."""
    written = []
    attr_changed = False
    W, H = g.size
    for name in g.sectors:
        sx, sy = int(name[:3]), int(name[3:])
        d = g.root / name
        ts = (slice(sy * 256, (sy + 1) * 256), slice(sx * 256, (sx + 1) * 256))
        vs = (slice(sy * 128, sy * 128 + 129), slice(sx * 128, sx * 128 + 129))
        if not np.array_equal(g.height[vs], g.orig["height"][vs]):
            write_height(d / "height.raw", HeightMap(T.to_sector_raw(g.height, sx, sy)))
            written.append(name + "/height.raw")
        if _edit_objects(g, d, sx, sy):
            written.append(name + "/areadata.txt")
        if not np.array_equal(g.tiles[ts], g.orig["tiles"][ts]):
            write_tile(d / "tile.raw", TileMap(TX.to_sector_raw(g.tiles, sx, sy)))
            written.append(name + "/tile.raw")
        cs = (slice(sy * 128, (sy + 1) * 128), slice(sx * 128, (sx + 1) * 128))
        if not np.array_equal(g.water[cs], g.orig["water"][cs]):
            write_water(d / "water.wtr", _water_map(g.water[cs], d / "water.wtr"))
            written.append(name + "/water.wtr")
        if not np.array_equal(g.attr[ts], g.orig["attr"][ts]):
            write_attr(d / "attr.atr", AttrMap(g.attr[ts].copy()))
            written.append(name + "/attr.atr")
            attr_changed = True
    if attr_changed:
        grids = {(int(n[:3]), int(n[3:])): g.attr[int(n[3:]) * 256:(int(n[3:]) + 1) * 256,
                                                   int(n[:3]) * 256:(int(n[:3]) + 1) * 256]
                 for n in g.sectors}
        sa_codec.write_server_attr(g.root / "server_attr", sa_codec.from_attr_maps(grids, W, H))
        written.append("server_attr")
    return written


def _water_map(surf: np.ndarray, old_path: pathlib.Path) -> WaterMap:
    """One sector's surfaces (cm) as a WaterMap: the old layers keep their
    indices, a surface the sector did not have becomes a new layer. Written in
    the current int32 form -- the legacy one loads with garbage heights."""
    heights = list(read_water(old_path).heights) if old_path.is_file() else []
    raw = np.where(np.isfinite(surf), np.round(surf / T.HEIGHT_SCALE), -1).astype(np.int64)
    cells = np.full(surf.shape, 0xFF, np.uint8)
    for v in np.unique(raw[raw >= 0]):
        v = int(v)
        if v not in heights:
            heights.append(v)
        cells[raw == v] = heights.index(v)
    return WaterMap(cells, heights)


_TREES = None


def _tree_crcs():
    global _TREES
    if _TREES is None:
        import json
        objs = json.loads((pathlib.Path(Q._CATALOG) / "objects.json").read_text(encoding="utf-8"))["objects"]
        _TREES = {int(k) for k, o in objs.items() if o.get("property_type") == "Tree"}
    return _TREES


def _edit_objects(g: Grids, d: pathlib.Path, sx: int, sy: int) -> bool:
    """Lift the records standing where the ground was raised by the same amount,
    and drop the trees standing on ground a fix turned to bare rock."""
    p = d / "areadata.txt"
    if (g.objects_dz is None and g.no_trees is None) or not p.is_file():
        return False
    area = AreaData.parse(p.read_bytes())
    moved = 0
    if g.objects_dz is not None:
        vh, vw = g.objects_dz.shape
        for r in area.records:
            cx = min(vw - 1, max(0, int(round(r.x / 200.0))))
            cy = min(vh - 1, max(0, int(round(-r.y / 200.0))))
            dz = float(g.objects_dz[cy, cx])
            if dz:
                r.z += dz
                moved += 1
    dropped = 0
    if g.no_trees is not None:
        trees, H, W = _tree_crcs(), g.no_trees.shape[0], g.no_trees.shape[1]
        keep = []
        for r in area.records:
            tx, ty = int(r.x // 100), int(-r.y // 100)
            if r.crc in trees and 0 <= ty < H and 0 <= tx < W and g.no_trees[ty, tx]:
                dropped += 1
                continue
            keep.append(r)
        area.records = keep
        g.trees_dropped = getattr(g, "trees_dropped", 0) + dropped
    if moved or dropped:
        p.write_bytes(area.to_bytes())
        return True
    return False


def curate(map_dir, fixes: Sequence[str], sectors: Optional[Iterable[str]] = None,
           textureset_dir=None, make_backup: bool = True, seed: int = 0,
           level_span_cm: float = LEVEL_SPAN_CM) -> Dict:
    """Apply the chosen fixes inside the chosen sectors; returns a report."""
    bad = [f for f in fixes if f not in FIXES]
    if bad:
        raise ValueError("unknown fix %s; choose from %s" % (bad, ", ".join(FIXES)))
    report = {"map": str(map_dir), "fixes": list(fixes), "sectors": list(sectors or []) or "all"}
    if make_backup:
        report["backup"] = str(backup(map_dir))
    g = load(map_dir, textureset_dir)
    region = region_mask(g, sectors)
    lines = []
    # terrain first (the border moves the ground), then the water that ground
    # decides, then the attr built from both, the rock on top of it, the paint
    for name in ("border", "water_level", "water", "attr", "rock", "road"):
        if name not in fixes:
            continue
        if name == "water_level" and "water" in fixes:
            continue                                        # `water` merges the levels itself
        fn = {"attr": fix_attr, "rock": fix_rock,
              "water": lambda g_, r_: fix_water(g_, r_, level_span_cm),
              "water_level": lambda g_, r_: fix_water_level(g_, r_, level_span_cm)}.get(name)
        if fn:
            lines.append(fn(g, region))
        elif name == "road":
            lines.append(fix_road(g, region, seed))
        else:
            lines.append(fix_border(g, region, seed))
    report["written"] = write(g)
    if getattr(g, "trees_dropped", 0):
        g.notes.append("border: %d trees taken off the new bare rock" % g.trees_dropped)
    report["changes"] = lines + g.notes
    report["spots"] = {k: [round(v[0]), round(v[1])] for k, v in g.spots.items()}
    return report

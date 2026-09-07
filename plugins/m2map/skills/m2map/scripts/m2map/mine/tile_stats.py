"""Texture-splatting statistics miner.

Measures how the shipped Ymir/GF maps actually paint ``tile.raw``: which
palette slot carries the ground, which are trim, how much of a declared
TextureSet is dead weight, how blotchy the splatting is, and whether any tile
byte points outside the palette.

Everything is measured on the **stitched** map grid: the 256x256 usable window
of every sector's ``tile.raw`` (border stripped, per
``reference/mapformat/tile-raw.md``) pasted into one
``(maxSectorY+1)*256 x (maxSectorX+1)*256`` array.  Stitching matters because
a patch that straddles a sector boundary is one patch in the world and two if
you count per file.

Units
-----
1 tile = 100 world units = 1 m (``tile.raw`` is 2x the 200-unit cell grid).
1 sector = 256 tiles = 25,600 units.  Sector folder name is
``printf("%06u", x*1000 + y)`` -- first three digits X (column), last three Y
(row), per ``reference/mapformat/README.md:36``.

CLI
---
``python -m m2map.mine.tile_stats [--maps <CORPUS>] [--out stats-tiles.json]``
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import pathlib
import re
import sys

import numpy as np

try:
    import cv2
except ImportError:                                    # pragma: no cover
    cv2 = None

from ..codec.setting import Setting
from ..codec.textureset import TextureSet
from ..codec.tile import ERASER, TILE_SCALE, TILE_SIZE, TileMap

__all__ = [
    "DEFAULT_MAPS_DIR", "DEFAULT_PACK_DIR", "SECTOR_TILES", "SECTOR_UNITS",
    "SECTOR_RE", "MapTiles", "load_map", "iter_maps", "resolve_textureset",
    "texture_role", "coverage_stats", "patch_stats", "splat_texture_stats",
    "solid_retention", "adjacency_pairs",
    "out_of_range_report", "map_report", "main",
]

DEFAULT_MAPS_DIR = pathlib.Path("<CORPUS>")
DEFAULT_PACK_DIR = pathlib.Path(
    r"<CLIENT_PACK>")
DEFAULT_ART_ROOT = pathlib.Path("D:/")

SECTOR_TILES = TILE_SIZE                # 256 usable tiles per sector axis
SECTOR_UNITS = SECTOR_TILES * TILE_SCALE  # 25,600 world units
SECTOR_RE = re.compile(r"^(\d{3})(\d{3})$")


# --------------------------------------------------------------------------
# palette role classification
# --------------------------------------------------------------------------
#: Ymir's terrain art has no texture literally called "road"/"path"/"trail" --
#: the whole 355-file ``d:/ymir work/terrainmaps`` vocabulary is
#: field/grass/stone/tile/sand/beach/snow/valcano/cliff/river/lava/ice/rock
#: (measured: see ``roads.json:texture_role_vocabulary``).  Roads are painted
#: with the *bare-earth* ("field", "sand") and *paved* ("tile", "stone_tile")
#: families over a grass/snow base, so the name role below is deliberately
#: coarse; ``roads.py`` refines it with a measured shape score.
_ROLE_PATTERNS = (
    ("paved",   (r"tile", r"stone_tile", r"12t_stone_tile", r"temple_stone")),
    ("dirt",    (r"field", r"feild")),                # "feild" typo is shipped
    ("sand",    (r"sand", r"beach", r"blacksand")),
    ("grass",   (r"grass", r"seagrass")),
    ("rock",    (r"stone", r"rock", r"cliff")),
    ("snow",    (r"snow", r"ice")),
    ("lava",    (r"valcano", r"volcano", r"lava", r"magma", r"crack")),
    ("water",   (r"water", r"river")),
    ("void",    (r"black",)),
)


def texture_role(filename: str) -> str:
    """Coarse art-family role for a TextureSet entry, from its .dds path.

    Matched against the *basename* first, then the directory, so
    ``dungeon/devilcave/dc_stone_lava_00.dds`` lands on "lava" rather than
    "rock" only if lava wins the basename race -- the tuple order above is the
    precedence.
    """
    p = (filename or "").replace("\\", "/").lower()
    base = p.rsplit("/", 1)[-1]
    for role, pats in _ROLE_PATTERNS:
        for pat in pats:
            if re.search(pat, base):
                return role
    for role, pats in _ROLE_PATTERNS:
        for pat in pats:
            if re.search(pat, p):
                return role
    return "other"


def resolve_textureset(setting: Setting, map_dir: pathlib.Path,
                       pack_dir: pathlib.Path = DEFAULT_PACK_DIR):
    """``setting.txt``'s ``TextureSet`` -> an on-disk path, or ``None``.

    ``CMapOutdoor::LoadSetting`` prefixes ``textureset\\`` when the value
    lacks it, then resolves against the pack root; all 70 sets referenced by
    the 139 maps that have a ``setting.txt`` resolve inside
    ``<pack>/textureset/``.
    """
    raw = (setting.texture_set or "").replace("\\", "/").strip()
    if not raw:
        return None
    rel = raw if raw.lower().startswith("textureset") else "textureset/" + raw
    # the pack nests the folder twice: <pack>/textureset/textureset/*.txt, and
    # LoadSetting's value already carries one "textureset\" level.
    for cand in (pack_dir / "textureset" / rel, pack_dir / rel):
        if cand.exists():
            return cand
    local = map_dir / pathlib.Path(rel).name
    return local if local.exists() else None


# --------------------------------------------------------------------------
# stitched map
# --------------------------------------------------------------------------
class MapTiles:
    """A whole map's ``tile.raw`` layers stitched into one array.

    Attributes
    ----------
    grid : (H, W) uint8
        Texture index per tile; 0 in cells with no sector on disk.
    valid : (H, W) bool
        True where a sector actually shipped a ``tile.raw``.
    sector_shape : (rows, cols)
        Sector grid extent, taken from the sector folders present -- **not**
        from ``MapSize``, because shipped maps ship folders past their
        declared size (``metin2_map_devilscatacomb`` declares 7x7 and ships a
        whole x=7 column).
    """

    __slots__ = ("name", "path", "setting", "textureset", "textureset_path",
                 "grid", "valid", "sector_shape", "sectors", "declared_size",
                 "base_position")

    def __init__(self, name, path, setting, textureset, textureset_path,
                 grid, valid, sector_shape, sectors):
        self.name = name
        self.path = path
        self.setting = setting
        self.textureset = textureset
        self.textureset_path = textureset_path
        self.grid = grid
        self.valid = valid
        self.sector_shape = sector_shape
        self.sectors = sectors
        self.declared_size = tuple(setting.map_size) if setting else (0, 0)
        self.base_position = tuple(setting.base_position) if setting else (0, 0)

    # -- geometry ----------------------------------------------------------
    @property
    def shape(self):
        return self.grid.shape

    def tile_to_world(self, tx, ty):
        """Tile (col, row) -> world (x, y) in centimetres, tile centre."""
        bx, by = self.base_position
        return (bx + (tx + 0.5) * TILE_SCALE, by + (ty + 0.5) * TILE_SCALE)

    # -- palette -----------------------------------------------------------
    @property
    def declared_count(self):
        return self.textureset.declared_count if self.textureset else 0

    def slot_name(self, index):
        if not self.textureset:
            return None
        e = self.textureset.get(index)
        return e.filename if e is not None else None

    def slot_role(self, index):
        fn = self.slot_name(index)
        return texture_role(fn) if fn else "unknown"

    def used_indices(self):
        vals = np.unique(self.grid[self.valid]) if self.valid.any() else np.array([], np.uint8)
        return [int(v) for v in vals if v != ERASER]

    def __repr__(self):
        return "MapTiles(%s, %dx%d tiles, %d sectors)" % (
            self.name, self.grid.shape[1], self.grid.shape[0], len(self.sectors))


def _sector_dirs(map_dir: pathlib.Path):
    out = {}
    for child in sorted(map_dir.iterdir()):
        if not child.is_dir():
            continue
        m = SECTOR_RE.match(child.name)
        if not m:
            continue
        out[(int(m.group(1)), int(m.group(2)))] = child   # (x, y)
    return out


def load_map(map_dir, pack_dir=DEFAULT_PACK_DIR, require_tiles=True):
    """Load and stitch one map folder.  Returns ``None`` if it has no tiles."""
    map_dir = pathlib.Path(map_dir)
    setting_path = map_dir / "setting.txt"
    setting = Setting.load(setting_path) if setting_path.exists() else None
    ts_path = resolve_textureset(setting, map_dir, pack_dir) if setting else None
    ts = TextureSet.load(ts_path) if ts_path else None

    secs = {k: v for k, v in _sector_dirs(map_dir).items()
            if (v / "tile.raw").exists()}
    if not secs:
        if require_tiles:
            return None
        cols = rows = 0
    else:
        cols = max(k[0] for k in secs) + 1
        rows = max(k[1] for k in secs) + 1

    H, W = rows * SECTOR_TILES, cols * SECTOR_TILES
    grid = np.zeros((H, W), np.uint8)
    valid = np.zeros((H, W), bool)
    for (sx, sy), d in secs.items():
        tm = TileMap.from_bytes((d / "tile.raw").read_bytes())
        y0, x0 = sy * SECTOR_TILES, sx * SECTOR_TILES
        grid[y0:y0 + SECTOR_TILES, x0:x0 + SECTOR_TILES] = tm.tiles
        valid[y0:y0 + SECTOR_TILES, x0:x0 + SECTOR_TILES] = True
    return MapTiles(map_dir.name, map_dir, setting, ts,
                    str(ts_path) if ts_path else None,
                    grid, valid, (rows, cols), sorted(secs))


def iter_maps(maps_dir=DEFAULT_MAPS_DIR, pack_dir=DEFAULT_PACK_DIR):
    for d in sorted(pathlib.Path(maps_dir).iterdir()):
        if not d.is_dir():
            continue
        mt = load_map(d, pack_dir)
        if mt is not None:
            yield mt


# --------------------------------------------------------------------------
# statistics
# --------------------------------------------------------------------------
def _components(mask):
    """4-connected components of a bool mask -> (labels, areas[1:])."""
    if cv2 is not None:
        n, lab, stats, _ = cv2.connectedComponentsWithStats(
            mask.astype(np.uint8), connectivity=4)
        return lab, stats[1:, cv2.CC_STAT_AREA].astype(np.int64)
    # numpy fallback: union-find over rows
    return _components_py(mask)


def _components_py(mask):                              # pragma: no cover
    H, W = mask.shape
    lab = np.zeros((H, W), np.int32)
    parent = [0]

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    nxt = 1
    for y in range(H):
        for x in range(W):
            if not mask[y, x]:
                continue
            up = lab[y - 1, x] if y and mask[y - 1, x] else 0
            lf = lab[y, x - 1] if x and mask[y, x - 1] else 0
            if up and lf:
                a, b = find(up), find(lf)
                lab[y, x] = min(a, b)
                parent[max(a, b)] = min(a, b)
            elif up or lf:
                lab[y, x] = up or lf
            else:
                lab[y, x] = nxt
                parent.append(nxt)
                nxt += 1
    for i in range(1, nxt):
        parent[i] = find(i)
    roots = {}
    for i in range(1, nxt):
        roots.setdefault(parent[i], len(roots) + 1)
    remap = np.zeros(nxt, np.int32)
    for i in range(1, nxt):
        remap[i] = roots[parent[i]]
    lab = remap[lab]
    areas = np.bincount(lab.ravel())[1:]
    return lab, areas.astype(np.int64)


def _perimeter(mask):
    """Count of 4-neighbour boundary edges (outside-the-array counts as edge)."""
    p = 0
    p += int((mask[:, :1]).sum()) + int((mask[:, -1:]).sum())
    p += int((mask[:1, :]).sum()) + int((mask[-1:, :]).sum())
    p += int((mask[:, :-1] & ~mask[:, 1:]).sum()) + int((~mask[:, :-1] & mask[:, 1:]).sum())
    p += int((mask[:-1, :] & ~mask[1:, :]).sum()) + int((~mask[:-1, :] & mask[1:, :]).sum())
    return p


def _run_lengths(row_major_mask):
    """Mean run length of True along axis 1."""
    m = row_major_mask
    if not m.any():
        return 0.0
    pad = np.zeros((m.shape[0], 1), bool)
    padded = np.concatenate([pad, m, pad], axis=1)
    starts = int((~padded[:, :-1] & padded[:, 1:]).sum())
    return float(m.sum()) / starts if starts else 0.0


def _quantiles(a, qs=(0.5, 0.9, 0.99)):
    if len(a) == 0:
        return [0.0] * len(qs)
    return [float(np.quantile(a, q)) for q in qs]


def coverage_stats(mt: MapTiles):
    """Per-slot coverage over the valid window."""
    g = mt.grid[mt.valid]
    total = int(g.size)
    counts = np.bincount(g, minlength=256)
    painted = total - int(counts[ERASER])
    out = {}
    for i in range(1, 256):
        c = int(counts[i])
        if c == 0:
            continue
        out[i] = {"tiles": c,
                  "fraction_of_valid": c / total if total else 0.0,
                  "fraction_of_painted": c / painted if painted else 0.0}
    return out, total, painted


def patch_stats(mt: MapTiles, indices=None, min_area=1):
    """Contiguous-region statistics per texture index (stitched, 4-conn)."""
    indices = indices if indices is not None else mt.used_indices()
    out = {}
    for i in indices:
        mask = (mt.grid == i) & mt.valid
        area = int(mask.sum())
        if area == 0:
            continue
        lab, areas = _components(mask)
        areas = areas[areas >= min_area]
        per = _perimeter(mask)
        big = int(areas.max()) if len(areas) else 0
        med, p90, p99 = _quantiles(areas)
        out[i] = {
            "tiles": area,
            "components": int(len(areas)),
            "component_area_mean": float(areas.mean()) if len(areas) else 0.0,
            "component_area_median": med,
            "component_area_p90": p90,
            "component_area_max": big,
            "largest_component_share": big / area if area else 0.0,
            "singleton_components": int((areas == 1).sum()),
            "singleton_fraction": float((areas == 1).mean()) if len(areas) else 0.0,
            "perimeter": per,
            "perimeter_over_area": per / area,
            # 4*sqrt(A)/P == 1 for a square, -> 0 for a filament
            "compactness": (4.0 * math.sqrt(area) / per) if per else 0.0,
            "mean_run_h": _run_lengths(mask),
            "mean_run_v": _run_lengths(mask.T),
            "solid_retention": solid_retention(mask),
        }
    return out


def solid_retention(mask, min_component=30):
    """Share of an index's tiles that survive de-dithering.

    Ymir blends two textures by stippling single tiles of one into the other,
    so an index mask is a solid core plus a stipple fringe.  ``open(3x3)``
    deletes the fringe and ``close(3x3)`` refills pinholes; what is left is
    the geometry the artist actually drew.  Slots retaining under ~0.10 are
    *dither-only* -- they exist purely as blend noise and never as a region
    (``metin2_map_a1`` grass 02 keeps 0.020 of its 163,420 tiles).
    """
    m = np.asarray(mask, np.uint8)
    if not m.any():
        return 0.0
    if cv2 is None:                                    # pragma: no cover
        return None
    k = np.ones((3, 3), np.uint8)
    c = cv2.morphologyEx(m, cv2.MORPH_OPEN, k)
    c = cv2.morphologyEx(c, cv2.MORPH_CLOSE, k)
    n, lab, st, _ = cv2.connectedComponentsWithStats(c, connectivity=8)
    keep = np.zeros(n, bool)
    if n > 1:
        keep[1:] = st[1:, cv2.CC_STAT_AREA] >= min_component
    return round(float(keep[lab].sum()) / float(m.sum()), 4)


def adjacency_pairs(mt: MapTiles, top=12):
    """Which texture pairs touch, and how stippled the contact is.

    ``contacts`` counts 4-adjacent tile pairs carrying the two indices.
    ``interleave`` = contacts / min(area) -- a clean border between two
    regions gives well under 1 (only the boundary tiles touch); a stippled
    blend gives 2-4, because every tile of the minority texture is surrounded
    by the majority one.
    """
    g = mt.grid.astype(np.int32)
    v = mt.valid
    counts = np.bincount(mt.grid[v], minlength=256)
    pairs = collections.Counter()
    for a, b, ok in ((g[:, :-1], g[:, 1:], v[:, :-1] & v[:, 1:]),
                     (g[:-1, :], g[1:, :], v[:-1, :] & v[1:, :])):
        d = ok & (a != b)
        lo = np.minimum(a[d], b[d])
        hi = np.maximum(a[d], b[d])
        key = lo * 256 + hi
        u, c = np.unique(key, return_counts=True)
        for k, n in zip(u.tolist(), c.tolist()):
            pairs[(k // 256, k % 256)] += n
    out = []
    for (i, j), n in pairs.most_common():
        if i == ERASER:
            continue
        m = int(min(counts[i], counts[j]))
        out.append({"a": int(i), "b": int(j),
                    "texture_a": mt.slot_name(int(i)),
                    "texture_b": mt.slot_name(int(j)),
                    "contacts": int(n),
                    "min_area": m,
                    "interleave": round(n / m, 3) if m else None})
        if len(out) >= top:
            break
    return out


def splat_texture_stats(mt: MapTiles):
    """Map-level blotchiness / blockiness of the splat."""
    g = mt.grid.astype(np.int16)
    v = mt.valid
    hv = v[:, :-1] & v[:, 1:]
    vv = v[:-1, :] & v[1:, :]
    h_diff = (g[:, :-1] != g[:, 1:]) & hv
    v_diff = (g[:-1, :] != g[1:, :]) & vv
    n_h, n_v = int(hv.sum()), int(vv.sum())
    edges = int(h_diff.sum()) + int(v_diff.sum())
    pairs = n_h + n_v
    # cell-grid snap: one terrain cell is 2 tiles, so a brush that works at
    # cell resolution puts every vertical transition on an odd column index
    # (between tile 2k+1 and 2k+2).  Measure the bias.
    cols = np.nonzero(h_diff.any(axis=0))[0]
    xs = np.repeat(np.arange(g.shape[1] - 1)[None, :], g.shape[0], 0)[h_diff]
    ys = np.repeat(np.arange(g.shape[0] - 1)[:, None], g.shape[1], 1)[v_diff]
    odd_x = float((xs % 2 == 1).mean()) if xs.size else 0.0
    odd_y = float((ys % 2 == 1).mean()) if ys.size else 0.0

    # neighbourhood agreement: fraction of tiles whose 4 neighbours all match
    same = np.ones_like(v)
    same[:, :-1] &= ~h_diff | ~hv
    same[:, 1:] &= ~h_diff | ~hv
    same[:-1, :] &= ~v_diff | ~vv
    same[1:, :] &= ~v_diff | ~vv
    counts = np.bincount(mt.grid[v], minlength=256)[1:]
    p = counts[counts > 0] / counts.sum() if counts.sum() else np.array([1.0])
    entropy = float(-(p * np.log2(p)).sum())
    return {
        "edge_density": edges / pairs if pairs else 0.0,
        "edge_density_h": int(h_diff.sum()) / n_h if n_h else 0.0,
        "edge_density_v": int(v_diff.sum()) / n_v if n_v else 0.0,
        "interior_fraction": float(same[v].mean()) if v.any() else 0.0,
        "transition_odd_x_bias": odd_x,
        "transition_odd_y_bias": odd_y,
        "coverage_entropy_bits": entropy,
        "effective_textures_2exH": float(2.0 ** entropy),
    }


def out_of_range_report(mt: MapTiles, max_samples=8):
    """Tile bytes the palette cannot resolve.

    Two failure modes, both render the error texture
    (``reference/mapformat/tile-raw.md`` "Pitfalls"):
    ``index > TextureCount`` and ``index <= TextureCount`` but the block is
    missing (``CTextureSet::Load`` ``continue``s over gaps).
    """
    if mt.textureset is None:
        return {"reason": "textureset unresolved"}
    dc = mt.textureset.declared_count
    bad = []
    for i in mt.used_indices():
        entry = mt.textureset.get(i)
        if i > dc:
            kind = "above_TextureCount"
        elif entry is None:
            kind = "empty_slot"
        else:
            continue
        mask = (mt.grid == i) & mt.valid
        ys, xs = np.nonzero(mask)
        samples = []
        step = max(1, len(ys) // max_samples)
        for k in range(0, len(ys), step):
            if len(samples) >= max_samples:
                break
            tx, ty = int(xs[k]), int(ys[k])
            samples.append({
                "tile": [tx, ty],
                "sector": "%03d%03d" % (tx // SECTOR_TILES, ty // SECTOR_TILES),
                "sector_tile": [tx % SECTOR_TILES, ty % SECTOR_TILES],
                "world_cm": [round(v, 1) for v in mt.tile_to_world(tx, ty)],
            })
        bad.append({"index": i, "kind": kind, "declared_count": dc,
                    "tiles": int(mask.sum()), "samples": samples})
    return bad


def map_report(mt: MapTiles, archetype=None):
    cov, total, painted = coverage_stats(mt)
    patches = patch_stats(mt)
    order = sorted(cov, key=lambda i: -cov[i]["tiles"])
    slots = []
    for i in order:
        fn = mt.slot_name(i)
        slots.append({
            "index": i,
            "texture": fn,
            "role": texture_role(fn) if fn else "unresolved",
            "tiles": cov[i]["tiles"],
            "fraction_of_painted": round(cov[i]["fraction_of_painted"], 6),
            "components": patches[i]["components"],
            "component_area_mean": round(patches[i]["component_area_mean"], 2),
            "component_area_median": patches[i]["component_area_median"],
            "component_area_max": patches[i]["component_area_max"],
            "largest_component_share": round(patches[i]["largest_component_share"], 4),
            "singleton_fraction": round(patches[i]["singleton_fraction"], 4),
            "perimeter_over_area": round(patches[i]["perimeter_over_area"], 4),
            "compactness": round(patches[i]["compactness"], 4),
            "mean_run_h": round(patches[i]["mean_run_h"], 3),
            "mean_run_v": round(patches[i]["mean_run_v"], 3),
            "solid_retention": patches[i]["solid_retention"],
            "dither_only": (patches[i]["solid_retention"] is not None
                            and patches[i]["solid_retention"] < 0.10),
        })
    dc = mt.declared_count
    used = set(cov)
    declared_slots = set(range(1, dc + 1))
    empty_slots = [i for i in declared_slots
                   if mt.textureset and mt.textureset.get(i) is None]
    base = slots[0] if slots else None
    trim = [s["index"] for s in slots if s["fraction_of_painted"] < 0.05]
    # stipple pairs: two slots whose contact count exceeds the smaller slot's
    # own area, i.e. every tile of the minority texture touches the majority
    # one on more than one side.  That is not a border, it is a dither blend.
    by_index = {s["index"]: s for s in slots}
    pairs = adjacency_pairs(mt)
    stipple = []
    for pr in pairs:
        if (pr["interleave"] or 0) < 1.0:
            continue
        a, b = by_index.get(pr["a"]), by_index.get(pr["b"])
        if not a or not b:
            continue
        minor, major = (a, b) if a["tiles"] < b["tiles"] else (b, a)
        stipple.append({
            "major": major["index"], "minor": minor["index"],
            "major_texture": major["texture"], "minor_texture": minor["texture"],
            "interleave": pr["interleave"],
            "minor_over_major_area": round(minor["tiles"] / major["tiles"], 4),
            "minor_solid_retention": minor["solid_retention"],
            "major_solid_retention": major["solid_retention"],
            "same_art_family": major["role"] == minor["role"],
        })
    return {
        "map": mt.name,
        "archetype": archetype,
        "sector_grid": [mt.sector_shape[1], mt.sector_shape[0]],
        "declared_map_size": list(mt.declared_size),
        "sectors_with_tiles": len(mt.sectors),
        "tiles_total": total,
        "tiles_painted": painted,
        "eraser_tiles": total - painted,
        "eraser_fraction": round((total - painted) / total, 6) if total else 0.0,
        "textureset": mt.setting.texture_set if mt.setting else None,
        "textureset_path": mt.textureset_path,
        "declared_count": dc,
        "declared_empty_slots": empty_slots,
        "used_count": len(used),
        "declared_but_unused": sorted(declared_slots - used),
        "unused_fraction": round(len(declared_slots - used) / dc, 4) if dc else 0.0,
        "base_slot": base["index"] if base else None,
        "base_texture": base["texture"] if base else None,
        "base_role": base["role"] if base else None,
        "base_share": round(base["fraction_of_painted"], 4) if base else 0.0,
        "top3_share": round(sum(s["fraction_of_painted"] for s in slots[:3]), 4),
        "trim_slots": trim,
        "dither_only_slots": [s["index"] for s in slots if s["dither_only"]],
        "dither_only_tile_share": round(
            sum(s["fraction_of_painted"] for s in slots if s["dither_only"]), 5),
        "adjacency_pairs": pairs,
        "stipple_pairs": stipple,
        "slots": slots,
        "splat": {k: (round(v, 6) if isinstance(v, float) else v)
                  for k, v in splat_texture_stats(mt).items()},
        "out_of_range": out_of_range_report(mt),
    }


# --------------------------------------------------------------------------
# aggregation
# --------------------------------------------------------------------------
def _agg(vals):
    a = np.asarray([v for v in vals if v is not None], float)
    if a.size == 0:
        return None
    return {"n": int(a.size), "mean": round(float(a.mean()), 5),
            "median": round(float(np.median(a)), 5),
            "min": round(float(a.min()), 5), "max": round(float(a.max()), 5)}


def aggregate(reports, key):
    groups = collections.defaultdict(list)
    for r in reports:
        groups[r.get(key) or "unclassified"].append(r)
    out = {}
    for name, rs in sorted(groups.items()):
        role_tiles = collections.Counter()
        for r in rs:
            for s in r["slots"]:
                role_tiles[s["role"]] += s["tiles"]
        tot = sum(role_tiles.values()) or 1
        out[name] = {
            "maps": sorted(r["map"] for r in rs),
            "map_count": len(rs),
            "tiles_total": sum(r["tiles_painted"] for r in rs),
            "base_share": _agg([r["base_share"] for r in rs]),
            "top3_share": _agg([r["top3_share"] for r in rs]),
            "used_count": _agg([r["used_count"] for r in rs]),
            "declared_count": _agg([r["declared_count"] for r in rs]),
            "unused_fraction": _agg([r["unused_fraction"] for r in rs]),
            "eraser_fraction": _agg([r["eraser_fraction"] for r in rs]),
            "edge_density": _agg([r["splat"]["edge_density"] for r in rs]),
            "interior_fraction": _agg([r["splat"]["interior_fraction"] for r in rs]),
            "coverage_entropy_bits": _agg([r["splat"]["coverage_entropy_bits"] for r in rs]),
            "transition_odd_x_bias": _agg([r["splat"]["transition_odd_x_bias"] for r in rs]),
            "dither_only_slots_per_map": _agg([len(r["dither_only_slots"]) for r in rs]),
            "dither_only_tile_share": _agg([r["dither_only_tile_share"] for r in rs]),
            "singleton_fraction_of_base": _agg(
                [r["slots"][0]["singleton_fraction"] for r in rs if r["slots"]]),
            "mean_run_h_of_base": _agg(
                [r["slots"][0]["mean_run_h"] for r in rs if r["slots"]]),
            "stipple_pairs_per_map": _agg([len(r["stipple_pairs"]) for r in rs]),
            "stipple_interleave": _agg([p["interleave"] for r in rs
                                        for p in r["stipple_pairs"]]),
            "stipple_minor_over_major_area": _agg(
                [p["minor_over_major_area"] for r in rs for p in r["stipple_pairs"]]),
            "stipple_same_family_share": (
                round(sum(1 for r in rs for p in r["stipple_pairs"] if p["same_art_family"])
                      / max(sum(len(r["stipple_pairs"]) for r in rs), 1), 4)),
            "base_role_histogram": dict(collections.Counter(r["base_role"] for r in rs)),
            "role_tile_share": {k: round(v / tot, 5)
                                for k, v in role_tiles.most_common()},
        }
    return out


# --------------------------------------------------------------------------
def load_archetypes(taxonomy_path):
    try:
        with open(taxonomy_path, encoding="utf-8") as fh:
            tax = json.load(fh)
    except (OSError, ValueError):
        return {}
    return {k: v.get("archetype") for k, v in tax.get("maps", {}).items()}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--maps", default=str(DEFAULT_MAPS_DIR))
    ap.add_argument("--pack", default=str(DEFAULT_PACK_DIR))
    ap.add_argument("--taxonomy", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--only", default=None, help="substring filter on map name")
    args = ap.parse_args(argv)

    here = pathlib.Path(__file__).resolve()
    catalog = here.parents[3] / "reference" / "catalog"
    tax_path = args.taxonomy or (catalog / "map-taxonomy.json")
    out_path = pathlib.Path(args.out or (catalog / "stats-tiles.json"))
    arche = load_archetypes(tax_path)

    reports, skipped = [], []
    for d in sorted(pathlib.Path(args.maps).iterdir()):
        if not d.is_dir():
            continue
        if args.only and args.only not in d.name:
            continue
        mt = load_map(d, pathlib.Path(args.pack))
        if mt is None:
            skipped.append({"map": d.name, "reason": "no sector ships tile.raw"})
            continue
        reports.append(map_report(mt, arche.get(d.name)))
        print("  %-42s %2d slots used / %2d declared  base=%s" % (
            mt.name, reports[-1]["used_count"], reports[-1]["declared_count"],
            reports[-1]["base_texture"]), file=sys.stderr)

    doc = {
        "schema_version": 1,
        "generated_from": {
            "maps_dir": str(args.maps), "pack_dir": str(args.pack),
            "maps_analysed": len(reports), "maps_skipped": len(skipped),
            "spec": "reference/mapformat/tile-raw.md, client-global-refs.md",
        },
        "units": {
            "tile": "1 tile = 100 world units = 1 m; tile.raw is 258x258, "
                    "usable window 256x256 (border stripped before stitching)",
            "sector": "256 tiles = 25,600 world units",
            "areas": "all *_area* and *tiles* values are tile counts (m^2)",
        },
        "corpus_totals": None,
        "by_archetype": aggregate(reports, "archetype"),
        "skipped": skipped,
        "maps": {r["map"]: r for r in reports},
    }
    tot_tiles = sum(r["tiles_painted"] for r in reports)
    role_tiles = collections.Counter()
    for r in reports:
        for s in r["slots"]:
            role_tiles[s["role"]] += s["tiles"]
    doc["corpus_totals"] = {
        "maps": len(reports),
        "sectors": sum(r["sectors_with_tiles"] for r in reports),
        "tiles_total": sum(r["tiles_total"] for r in reports),
        "tiles_painted": tot_tiles,
        "role_tile_share": {k: round(v / tot_tiles, 6)
                            for k, v in role_tiles.most_common()},
        "base_share": _agg([r["base_share"] for r in reports]),
        "used_count": _agg([r["used_count"] for r in reports]),
        "declared_count": _agg([r["declared_count"] for r in reports]),
        "unused_fraction": _agg([r["unused_fraction"] for r in reports]),
        "edge_density": _agg([r["splat"]["edge_density"] for r in reports]),
        "interior_fraction": _agg([r["splat"]["interior_fraction"] for r in reports]),
        "dither_only_slots_per_map": _agg(
            [len(r["dither_only_slots"]) for r in reports]),
        "dither_only_tile_share": _agg(
            [r["dither_only_tile_share"] for r in reports]),
        "transition_odd_x_bias": _agg(
            [r["splat"]["transition_odd_x_bias"] for r in reports]),
        "stipple_pairs_per_map": _agg([len(r["stipple_pairs"]) for r in reports]),
        "stipple_interleave": _agg([p["interleave"] for r in reports
                                    for p in r["stipple_pairs"]]),
        "stipple_minor_over_major_area": _agg(
            [p["minor_over_major_area"] for r in reports for p in r["stipple_pairs"]]),
        "stipple_same_family_share": round(
            sum(1 for r in reports for p in r["stipple_pairs"] if p["same_art_family"])
            / max(sum(len(r["stipple_pairs"]) for r in reports), 1), 4),
        "maps_with_no_stipple": sorted(
            r["map"] for r in reports if not r["stipple_pairs"]),
        "maps_with_out_of_range": sorted(
            r["map"] for r in reports
            if isinstance(r["out_of_range"], list) and r["out_of_range"]),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    print("wrote %s (%d maps)" % (out_path, len(reports)), file=sys.stderr)
    return doc


if __name__ == "__main__":
    main()

"""Corpus-wide object-placement miner.

Parses every ``areadata.txt`` in the map corpus, resolves each record's CRC
against the client property database, joins the placement against the terrain
grids underneath it (``tile.raw`` / ``height.raw`` / ``attr.atr`` /
``water.wtr``) and emits the three catalog documents that describe *where
objects go*:

* ``stats-objects.json``  -- frequency, density, spacing, clustering,
  rotation, height bias, spatial habits
* ``affinity.json``       -- per-CRC / per-family distribution over ground
  texture and terrain slope, including the hard exclusions
* ``cooccurrence.json``   -- CRC pairs that co-locate far above chance at
  5 m / 15 m / 40 m

Everything here is measurement, not opinion: every aggregate carries its ``n``.

Coordinate conventions (reference/mapformat/areadata-txt.md, README.md)
----------------------------------------------------------------------
``areadata`` positions are **map-local world centimetres** and ``y`` is stored
**negated** (``terrain_y == -y``).  A sectree ``(ax, ay)`` -- folder ``%06u`` of
``ax*1000 + ay`` -- spans ``x in [ax*25600, (ax+1)*25600)`` and ``terrain_y in
[ay*25600, (ay+1)*25600)``.  Grids under a placement:

===================  =========  ==========================================
grid                 cell size  index from world cm
===================  =========  ==========================================
tile.raw (258x258)   100 cm     ``raw[ty%256 + 1, tx%256 + 1]``
attr.atr (256x256)   100 cm     ``cells[ty%256, tx%256]``
height.raw (131x131) 200 cm     vertex ``raw[cy%128 + 1, cx%128 + 1]``
water.wtr (128x128)  200 cm     ``cells[cy%128, cx%128]``
===================  =========  ==========================================

Usage
-----
``python -m m2map.mine.object_stats --out <catalog dir>``

``--cache <dir>`` keeps the parsed placement table between runs; ``--rescan``
forces a re-parse.
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import re
import sys
import time
from collections import Counter, defaultdict

import numpy as np

_HERE = pathlib.Path(__file__).resolve()
if str(_HERE.parents[2]) not in sys.path:                 # .../scripts
    sys.path.insert(0, str(_HERE.parents[2]))

from m2map.codec.areadata import AreaData                  # noqa: E402
from m2map.codec.attr import AttrMap                       # noqa: E402
from m2map.codec.height import HeightMap                   # noqa: E402
from m2map.codec.property import scan_property_dir         # noqa: E402
from m2map.codec.setting import Setting                    # noqa: E402
from m2map.codec.textureset import TextureSet              # noqa: E402
from m2map.codec.tile import TileMap                       # noqa: E402
from m2map.codec.water import WaterMap                     # noqa: E402

# --- host locations -------------------------------------------------------
# Resolved through m2map.config, never hardcoded. A literal path here is both
# wrong for every other machine and a scrub_paths.py failure; the scrubber used
# to rewrite it to a "<CORPUS>" string that no longer resolved at runtime.
from m2map.config import paths as _paths


def _cfg(key, *parts):
    """Configured path (or None when unset), so --flags stay overridable."""
    base = getattr(_paths(), key, None)
    if base is None:
        return None
    for p in parts:
        base = base / p
    return str(base)


__all__ = [
    "DEFAULTS", "PropInfo", "build_property_index", "terrain_class",
    "TextureSetCache", "chamfer_distance", "scan_corpus", "build_reports",
    "main",
]

# --------------------------------------------------------------------------
# configuration
# --------------------------------------------------------------------------

SKILL_ROOT = _HERE.parents[3]                              # .../skills/m2map

DEFAULTS = {
    "maps": _cfg("corpus"),
    "property": _cfg("client_pack", "property", "property"),
    "textureset": _cfg("client_pack", "textureset", "textureset"),
    "taxonomy": str(SKILL_ROOT / "reference" / "catalog" / "map-taxonomy.json"),
    "out": str(SKILL_ROOT / "reference" / "catalog"),
}

SECTOR_CM = 25600          # client sectree edge
CELL_CM = 200              # terrain cell
TILE_CM = 100              # tile / attr half-cell
CELLS = 128                # terrain cells per sector edge
TILES = 256                # tiles per sector edge

#: co-occurrence radii, centimetres (5 m / 15 m / 40 m)
CO_RADII = (500, 1500, 4000)

#: nearest-neighbour histogram edges, centimetres
NN_EDGES = (0, 100, 200, 300, 500, 750, 1000, 1500, 2000, 3000, 5000, 10000, 10 ** 9)

#: slope histogram edges, degrees
SLOPE_EDGES = (0, 2, 5, 10, 15, 20, 30, 45, 90)

#: distance histogram edges, centimetres
DIST_EDGES = (0, 200, 500, 1000, 2000, 4000, 8000, 16000, 10 ** 9)

#: how many CRCs get a full per-CRC record in stats-objects.json
TOP_CRC_DETAIL = 420


# --------------------------------------------------------------------------
# property index
# --------------------------------------------------------------------------

class PropInfo(object):
    """One resolved property row: what a CRC actually is."""

    __slots__ = ("crc", "name", "type", "model", "family", "species", "path")

    def __init__(self, crc, name, ptype, model, family, species, path):
        self.crc = crc
        self.name = name
        self.type = ptype
        self.model = model
        self.family = family
        self.species = species
        self.path = path

    def as_dict(self):
        return {"crc": self.crc, "name": self.name, "type": self.type,
                "model": self.model, "family": self.family}


_TREE_PREFIX = re.compile(r"^([a-z]+\d*)_")


def _kr(text):
    """Repair a CP949 path that the latin-1 text codec handed back verbatim.

    ``property.py`` decodes every byte as latin-1 (that is what the engine
    does), so Korean folder names such as ``zone/공용`` arrive as
    mojibake.  Round-tripping latin-1 -> cp949 restores them; anything that
    does not round-trip is left alone.
    """
    try:
        raw = text.encode("latin-1")
    except UnicodeEncodeError:
        return text
    if all(b < 0x80 for b in raw):
        return text
    try:
        return raw.decode("cp949")
    except UnicodeDecodeError:
        return text


def _norm_model(path):
    if not path:
        return ""
    p = _kr(path).lower().replace("\\", "/").strip().strip('"')
    if "ymir work/" in p:                     # everything ships under d:/ymir work/
        p = p.split("ymir work/", 1)[1]
    return p


def model_family(model, ptype):
    """Art family = the model's directory under ``ymir work/``.

    Trees collapse to ``tree/<species-prefix>`` (``b1``, ``b2``, ``b3``, ``n1``,
    ``n2`` ...) because the whole SpeedTree set lives in one flat ``tree/``
    folder and the prefix *is* the biome.
    """
    p = _norm_model(model)
    if not p:
        return "(no model)"
    folder = p.rsplit("/", 1)[0] if "/" in p else ""
    if ptype == "Tree" or folder == "tree":
        base = p.rsplit("/", 1)[-1]
        m = _TREE_PREFIX.match(base)
        return "tree/" + (m.group(1) if m else "other")
    return folder or "(root)"


def tree_species(model):
    base = _norm_model(model).rsplit("/", 1)[-1]
    return base.rsplit(".", 1)[0] if base else ""


def build_property_index(root):
    """CRC -> :class:`PropInfo` for the whole client property pack."""
    reg = scan_property_dir(root)
    out = {}
    for crc, prop in reg.items():
        ptype = prop.property_type
        model = _norm_model(prop.model_file or "")
        out[crc] = PropInfo(
            crc=crc, name=_kr(prop.name), ptype=ptype, model=model,
            family=model_family(model, ptype),
            species=tree_species(model) if ptype == "Tree" else "",
            path=str(prop.path) if prop.path else "",
        )
    return out


# --------------------------------------------------------------------------
# terrain texture classification
# --------------------------------------------------------------------------

#: Ordered rules, first match wins.  Derived by enumerating all 355 distinct
#: texture paths across the 99 shipped texturesets.
_TEX_RULE_SRC = (
    ("water", (r"beach ?water", r"river", r"/water")),
    ("lava", (r"lava", r"magma")),
    ("tile", (r"tile", r"grasstile")),        # tileNN = the paved / stone-tile set
    ("snow", (r"snow", r"ice_", r"/ice")),
    ("sand", (r"sand", r"beach", r"blacksand")),
    ("rock", (r"stone", r"rock", r"cliff", r"crack", r"valcano", r"volcano")),
    ("grass", (r"grass", r"seagrass")),
    ("field", (r"field", r"feild")),
)
_TEX_RULES = tuple((k, tuple(re.compile(p) for p in v)) for k, v in _TEX_RULE_SRC)


def terrain_class(path):
    """Coarse ground class of a terrain texture path.

    Classification runs on the **basename** first and only falls back to the
    full path, because folder names lie: everything in ``n/snow.m/`` would
    otherwise read as snow, including ``stone03.dds`` and ``field 02.dds``.

    ``tile`` is the ``tileNN`` / ``stone_tile`` pavement family.  It is NOT the
    same thing as "road": measured on the corpus, the empire road network is
    painted with ``b/field/field 01.dds`` (a1 index 1, 7.5 % of the map, clean
    ribbons) while ``b/tile/tile01.dds`` covers only the 0.21 % town plaza.
    Road/path membership is therefore detected geometrically per map --
    see :func:`detect_path_textures` -- not from the texture name.
    """
    p = (path or "").lower().replace("\\", "/")
    if not p:
        return "(none)"
    base = p.rsplit("/", 1)[-1]
    for probe in (base, p):
        for name, pats in _TEX_RULES:
            for pat in pats:
                if pat.search(probe):
                    return name
    return "other"


#: geometric path-detection thresholds, calibrated against the visually
#: verified road networks of metin2_map_a1 (index 1 = b/field/field 01.dds),
#: metin2_map_b1 and metin2_map_capedragonhead (index 7 = stone_tile_002).
PATH_AREA_MIN = 0.005
PATH_AREA_MAX = 0.10
PATH_E2_MIN = 0.25
PATH_E2_MAX = 0.85
PATH_E5_MAX = 0.45


def _erode(mask, k):
    """Binary erosion by ``k`` steps of a 4-neighbour structuring element."""
    m = mask
    for _ in range(k):
        e = m.copy()
        e[1:, :] &= m[:-1, :]
        e[:-1, :] &= m[1:, :]
        e[:, 1:] &= m[:, :-1]
        e[:, :-1] &= m[:, 1:]
        m = e
    return m


def detect_path_textures(cellgrid, present):
    """Which texture indices of one map form its road / path network.

    A road is a *ribbon*: it covers a modest slice of the map, survives an
    erosion of 2 cells (4 m -- roads are 4-8 m wide) but not one of 5 cells
    (10 m), which is exactly what separates it both from the big ground blobs
    (they survive) and from the 1-2 cell blend fringes the editor paints along
    every texture boundary (they die at 2).

    Returns ``{index: {"area_share", "e2", "e5"}}`` for the indices that pass.
    Verified against metin2_map_a1, where this selects index 1
    (``b/field/field 01.dds``) -- the visible road web -- and rejects index 4
    (its halo), the grass/stone blobs and the beaches.
    """
    total = int(present.sum())
    out = {}
    if total <= 0:
        return out
    for idx in np.unique(cellgrid[present]):
        if idx == 0:
            continue
        m = (cellgrid == idx) & present
        a = int(m.sum())
        share = a / total
        if not (PATH_AREA_MIN <= share <= PATH_AREA_MAX):
            continue
        e2 = _erode(m, 2).sum() / a
        e5 = _erode(m, 5).sum() / a
        if PATH_E2_MIN <= e2 <= PATH_E2_MAX and e5 < PATH_E5_MAX:
            out[int(idx)] = {"area_share": round(share, 5),
                             "e2": round(float(e2), 3), "e5": round(float(e5), 3)}
    return out


def short_texture(path):
    p = (path or "").lower().replace("\\", "/")
    if "terrainmaps/" in p:
        p = p.split("terrainmaps/", 1)[1]
    elif "ymir work/" in p:
        p = p.split("ymir work/", 1)[1]
    return p


class TextureSetCache(object):
    """Resolves a ``setting.txt`` TextureSet ref to per-slot path + class."""

    def __init__(self, root):
        self.root = pathlib.Path(root)
        self._cache = {}
        self._dir = None

    def _find(self, key):
        if self._dir is None:
            self._dir = {p.name.lower(): p for p in self.root.iterdir() if p.is_file()}
        return self._dir.get(key)

    def get(self, ref):
        key = (ref or "").lower().replace("\\", "/").rsplit("/", 1)[-1]
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        paths = [""] * 256
        classes = ["(none)"] * 256
        f = self._find(key)
        if f is not None:
            try:
                ts = TextureSet.load(f)
                # slots are indexed exactly like a tile.raw byte: slot 0 is the
                # eraser (always None), slot N is block Texture%03dN.
                for i in range(256):
                    e = ts.get(i)
                    if e is None:
                        continue
                    paths[i] = short_texture(e.filename)
                    classes[i] = terrain_class(e.filename)
            except Exception:
                pass
        self._cache[key] = (paths, classes)
        return self._cache[key]


# --------------------------------------------------------------------------
# distance transform
# --------------------------------------------------------------------------

_SQRT2 = math.sqrt(2.0)
_SQRT5 = math.sqrt(5.0)


def chamfer_distance(mask, cell_size=1.0):
    """Two-pass 5x5 chamfer distance to the nearest ``True`` cell.

    Weights ``(1, sqrt2, sqrt5)`` -- the 3x3 neighbours plus the knight moves.
    Measured against exact Euclidean on a single-source grid the worst-case
    relative error is 2.8 % (mean 1.3 %; the cheaper 3x3 form peaks at 8.2 %), which is far below
    the 100 cm bins this catalog reports.  The horizontal recurrence
    ``row[x] = min(row[x], row[x-1] + 1)`` is solved exactly as
    ``x + min_{k<=x}(row[k] - k)`` via ``np.minimum.accumulate``, so only the
    row loop is Python.  Returns ``float32`` distances in ``cell_size`` units;
    an all-``False`` mask yields ``+inf`` everywhere.
    """
    mask = np.asarray(mask, dtype=bool)
    h, w = mask.shape
    INF = np.float32(1e18)
    d = np.where(mask, np.float32(0.0), INF).astype(np.float32)
    if not mask.any():
        d[:] = np.inf
        return d
    idx = np.arange(w, dtype=np.float32)
    a = np.float32(1.0)
    b = np.float32(_SQRT2)
    c = np.float32(_SQRT5)

    def horiz(row):
        np.minimum(row, np.minimum.accumulate(row - idx) + idx, out=row)
        rev = row[::-1].copy()
        np.minimum(rev, np.minimum.accumulate(rev - idx) + idx, out=rev)
        np.minimum(row, rev[::-1], out=row)

    def sweep(row, near, far):
        """Fold in the finished row one back (``near``) and two back (``far``).

        Offsets and weights: (1,0)=1, (1,+-1)=sqrt2, (1,+-2)=sqrt5,
        (2,+-1)=sqrt5.  (2,+-2) is *not* a knight move -- it costs 2*sqrt2 and
        is already covered by two (1,+-1) steps.
        """
        np.minimum(row, near + a, out=row)
        np.minimum(row[1:], near[:-1] + b, out=row[1:])
        np.minimum(row[:-1], near[1:] + b, out=row[:-1])
        np.minimum(row[2:], near[:-2] + c, out=row[2:])
        np.minimum(row[:-2], near[2:] + c, out=row[:-2])
        if far is not None:
            np.minimum(row[1:], far[:-1] + c, out=row[1:])
            np.minimum(row[:-1], far[1:] + c, out=row[:-1])

    for y in range(h):
        row = d[y]
        if y:
            sweep(row, d[y - 1], d[y - 2] if y > 1 else None)
        horiz(row)
    for y in range(h - 2, -1, -1):
        sweep(d[y], d[y + 1], d[y + 2] if y + 2 < h else None)
        horiz(d[y])
    return d * np.float32(cell_size)


# --------------------------------------------------------------------------
# corpus scan
# --------------------------------------------------------------------------

_SECTOR_DIR = re.compile(r"^\d{6}$")


def _sector_xy(name):
    n = int(name)
    return n // 1000, n % 1000


def _load_sector_grids(sdir):
    """Load the four terrain grids of one sectree; missing files -> ``None``."""
    out = {}
    try:
        out["tile"] = TileMap.from_bytes((sdir / "tile.raw").read_bytes())
    except Exception:
        out["tile"] = None
    try:
        out["height"] = HeightMap.from_bytes((sdir / "height.raw").read_bytes())
    except Exception:
        out["height"] = None
    try:
        out["attr"] = AttrMap.from_bytes((sdir / "attr.atr").read_bytes())
    except Exception:
        out["attr"] = None
    try:
        out["water"] = WaterMap.from_bytes((sdir / "water.wtr").read_bytes())
    except Exception:
        out["water"] = None
    return out


def _nn_distances(x, y):
    """Nearest-neighbour distance (cm) for each point in a set. n<2 -> ``inf``."""
    n = len(x)
    if n < 2:
        return np.full(n, np.inf, dtype=np.float64)
    px = np.asarray(x, dtype=np.float64)
    py = np.asarray(y, dtype=np.float64)
    out = np.empty(n, dtype=np.float64)
    step = max(1, int(4_000_000 // max(n, 1)))
    for s in range(0, n, step):
        e = min(n, s + step)
        dx = px[s:e, None] - px[None, :]
        dy = py[s:e, None] - py[None, :]
        d2 = dx * dx + dy * dy
        for i in range(e - s):
            d2[i, s + i] = np.inf
        out[s:e] = np.sqrt(d2.min(axis=1))
    return out


def _nn_cross(x, y, labels):
    """Nearest neighbour whose label differs -- the cross-species spacing."""
    n = len(x)
    if n < 2:
        return np.full(n, np.inf, dtype=np.float64)
    px = np.asarray(x, dtype=np.float64)
    py = np.asarray(y, dtype=np.float64)
    lab = np.asarray(labels)
    out = np.full(n, np.inf, dtype=np.float64)
    step = max(1, int(4_000_000 // max(n, 1)))
    for s in range(0, n, step):
        e = min(n, s + step)
        dx = px[s:e, None] - px[None, :]
        dy = py[s:e, None] - py[None, :]
        d2 = dx * dx + dy * dy
        same = lab[s:e, None] == lab[None, :]
        d2 = np.where(same, np.inf, d2)
        out[s:e] = np.sqrt(d2.min(axis=1))
    return out


def scan_corpus(maps_root, prop_index, ts_cache, taxonomy, verbose=True, only=None):
    """Parse every areadata record in the corpus and join it to the terrain.

    Returns ``(table, maps_meta, problems)`` where ``table`` is a dict of
    parallel numpy arrays, one entry per placement.  ``only`` restricts the
    scan to a set of map-folder names (used by the tests).
    """
    maps_root = pathlib.Path(maps_root)
    map_dirs = sorted([p for p in maps_root.iterdir() if p.is_dir()])
    if only:
        want = set(only)
        map_dirs = [p for p in map_dirs if p.name in want]
    cols = defaultdict(list)
    maps_meta = {}
    problems = []
    t0 = time.time()

    for mi, mdir in enumerate(map_dirs):
        mname = mdir.name
        tax = (taxonomy or {}).get(mname, {})
        arche = tax.get("archetype", "(unclassified)")

        setting = None
        for cand in ("setting.txt", "Setting.txt"):
            f = mdir / cand
            if f.exists():
                try:
                    setting = Setting.load(f)
                except Exception as exc:
                    problems.append("%s: setting.txt unreadable (%s)" % (mname, exc))
                break
        ts_ref = setting.texture_set if setting else ""
        tex_paths, tex_classes = ts_cache.get(ts_ref)

        sectors = {}
        for sd in sorted(mdir.iterdir()):
            if sd.is_dir() and _SECTOR_DIR.match(sd.name):
                sectors[_sector_xy(sd.name)] = sd
        if not sectors:
            maps_meta[mname] = {"archetype": arche, "sectors": 0, "objects": 0,
                                "textureset": ts_ref, "proxy": True}
            continue

        gw = max(ax for ax, _ in sectors) + 1
        gh = max(ay for _, ay in sectors) + 1
        if setting and setting.map_size:
            gw = max(gw, int(setting.map_size[0]))
            gh = max(gh, int(setting.map_size[1]))

        # ---- map-global cell grids (200 cm cells) -------------------------
        cw, ch = gw * CELLS, gh * CELLS
        tilegrid = np.zeros((ch * 2, cw * 2), dtype=np.uint8)   # 100 cm indices
        present_t = np.zeros((ch * 2, cw * 2), dtype=bool)
        tilecls = np.zeros((ch, cw), dtype=bool)        # tileNN / stone_tile class
        wet = np.zeros((ch, cw), dtype=bool)
        present = np.zeros((ch, cw), dtype=bool)
        grids = {}
        slopes = {}
        for (ax, ay), sd in sectors.items():
            g = _load_sector_grids(sd)
            grids[(ax, ay)] = g
            y0, x0 = ay * CELLS, ax * CELLS
            if g["tile"] is not None:
                t = g["tile"].tiles                       # 256x256, 100 cm
                tilegrid[y0 * 2:y0 * 2 + TILES, x0 * 2:x0 * 2 + TILES] = t
                present_t[y0 * 2:y0 * 2 + TILES, x0 * 2:x0 * 2 + TILES] = True
                is_tile = np.array([tex_classes[v] == "tile" for v in range(256)])
                tm = is_tile[t]
                tilecls[y0:y0 + CELLS, x0:x0 + CELLS] = (
                    tm[0::2, 0::2] | tm[1::2, 0::2] |
                    tm[0::2, 1::2] | tm[1::2, 1::2])
                present[y0:y0 + CELLS, x0:x0 + CELLS] = True
            if g["water"] is not None:
                wet[y0:y0 + CELLS, x0:x0 + CELLS] = g["water"].wet_mask
            elif g["attr"] is not None:
                am = (g["attr"].cells & 0x02) != 0
                wet[y0:y0 + CELLS, x0:x0 + CELLS] = (
                    am[0::2, 0::2] | am[1::2, 0::2] |
                    am[0::2, 1::2] | am[1::2, 1::2])
            if g["height"] is not None:
                slopes[(ax, ay)] = g["height"].slope_degrees()

        # Path detection runs on the native 100 cm tile grid -- the erosion
        # thresholds are calibrated in tiles, not cells.
        path_tex = detect_path_textures(tilegrid, present_t)
        road_t = np.zeros_like(present_t)
        for idx in path_tex:
            road_t |= (tilegrid == idx) & present_t
        road = (road_t[0::2, 0::2] | road_t[1::2, 0::2] |
                road_t[0::2, 1::2] | road_t[1::2, 1::2])
        road |= tilecls                                   # plazas count as road

        d_road = chamfer_distance(road, CELL_CM) if road.any() else None
        d_water = chamfer_distance(wet, CELL_CM) if wet.any() else None
        # distance to the edge of the terrain: pad by one cell so a complete
        # rectangular map still has an "outside" to measure against
        pad = np.ones((ch + 2, cw + 2), dtype=bool)
        pad[1:-1, 1:-1] = ~present
        d_edge = chamfer_distance(pad, CELL_CM)[1:-1, 1:-1]
        road_cov = float(road.sum() / max(1, present.sum()))
        water_cov = float(wet.sum() / max(1, present.sum()))

        # ---- placements ---------------------------------------------------
        m_x, m_y, m_crc, m_fam = [], [], [], []
        first = len(cols["crc"])
        n_map = 0
        for (ax, ay), sd in sorted(sectors.items()):
            af = sd / "areadata.txt"
            if not af.exists():
                continue
            try:
                area = AreaData.load(af)
            except Exception as exc:
                problems.append("%s/%s: areadata unreadable (%s)" % (mname, sd.name, exc))
                continue
            g = grids[(ax, ay)]
            slope = slopes.get((ax, ay))
            for rec in area:
                pi = prop_index.get(rec.crc)
                ty = rec.terrain_y
                tx_g = int(rec.x // TILE_CM)
                ty_g = int(ty // TILE_CM)
                cx_g = int(rec.x // CELL_CM)
                cy_g = int(ty // CELL_CM)
                ltx, lty = tx_g - ax * TILES, ty_g - ay * TILES
                lcx, lcy = cx_g - ax * CELLS, cy_g - ay * CELLS
                in_sector = 0 <= ltx < TILES and 0 <= lty < TILES

                tile_idx = -1
                if in_sector and g["tile"] is not None:
                    tile_idx = int(g["tile"].tiles[lty, ltx])
                attr_b = -1
                if in_sector and g["attr"] is not None:
                    attr_b = int(g["attr"].cells[lty, ltx])
                slope_d = np.nan
                terr_z = np.nan
                if 0 <= lcx < CELLS and 0 <= lcy < CELLS:
                    if slope is not None:
                        slope_d = float(slope[lcy, lcx])
                    if g["height"] is not None:
                        terr_z = float(g["height"].vertices[lcy, lcx]) * 0.5
                wet_here = 0
                if 0 <= lcx < CELLS and 0 <= lcy < CELLS and g["water"] is not None:
                    wet_here = int(bool(g["water"].wet_mask[lcy, lcx]))

                def _samp(grid, default=np.nan):
                    if grid is None:
                        return default
                    if 0 <= cy_g < ch and 0 <= cx_g < cw:
                        v = float(grid[cy_g, cx_g])
                        return v if v < 1e17 else np.inf
                    return default

                cols["map"].append(mname)
                cols["archetype"].append(arche)
                cols["sector"].append("%03d%03d" % (ax, ay))
                cols["crc"].append(rec.crc)
                cols["name"].append(pi.name if pi else "")
                cols["ptype"].append(pi.type if pi else "(unresolved)")
                cols["family"].append(pi.family if pi else "(unresolved)")
                cols["species"].append(pi.species if pi else "")
                cols["x"].append(rec.x)
                cols["y"].append(ty)
                cols["z"].append(rec.z)
                cols["bias"].append(rec.height_bias)
                cols["yaw"].append(rec.yaw)
                cols["pitch"].append(rec.pitch)
                cols["roll"].append(rec.roll)
                cols["ntok"].append(rec.token_count)
                cols["rotshape"].append(0 if rec.rotation_token is None
                                        else (3 if "#" in rec.rotation_token else 1))
                cols["tile"].append(tile_idx)
                cols["tex"].append(tex_paths[tile_idx] if tile_idx >= 0 else "")
                cols["tclass"].append(tex_classes[tile_idx] if tile_idx >= 0 else "(none)")
                cols["slope"].append(slope_d)
                cols["terr_z"].append(terr_z)
                cols["attr"].append(attr_b)
                cols["wet"].append(wet_here)
                cols["d_road"].append(_samp(d_road, np.inf))
                cols["d_water"].append(_samp(d_water, np.inf))
                cols["d_edge"].append(_samp(d_edge, np.inf))
                m_x.append(rec.x)
                m_y.append(ty)
                m_crc.append(rec.crc)
                m_fam.append(pi.family if pi else "(unresolved)")
                n_map += 1

        # ---- per-map nearest neighbours -----------------------------------
        if n_map:
            ax_ = np.asarray(m_x, dtype=np.float64)
            ay_ = np.asarray(m_y, dtype=np.float64)
            nn_any = _nn_distances(ax_, ay_)
            nn_crc = np.full(n_map, np.inf)
            nn_fam = np.full(n_map, np.inf)
            crc_arr = np.asarray(m_crc)
            fam_arr = np.asarray(m_fam)
            for key in np.unique(crc_arr):
                sel = np.where(crc_arr == key)[0]
                nn_crc[sel] = _nn_distances(ax_[sel], ay_[sel])
            for key in np.unique(fam_arr):
                sel = np.where(fam_arr == key)[0]
                nn_fam[sel] = _nn_distances(ax_[sel], ay_[sel])
            nn_xcrc = _nn_cross(ax_, ay_, crc_arr)
            nn_xfam = _nn_cross(ax_, ay_, fam_arr)
            cols["nn_any"].extend(nn_any.tolist())
            cols["nn_crc"].extend(nn_crc.tolist())
            cols["nn_fam"].extend(nn_fam.tolist())
            cols["nn_xcrc"].extend(nn_xcrc.tolist())
            cols["nn_xfam"].extend(nn_xfam.tolist())

        maps_meta[mname] = {
            "archetype": arche,
            "sectors": len(sectors),
            "sectors_with_terrain": int(present[::CELLS, ::CELLS].sum()),
            "grid": [gw, gh],
            "objects": n_map,
            "textureset": ts_ref,
            "road_cover": round(road_cov, 5),
            "water_cover": round(water_cov, 5),
            "path_textures": {str(k): {"texture": tex_paths[k], "class": tex_classes[k],
                                       **v} for k, v in sorted(path_tex.items())},
            "tile_class_cover": round(float(tilecls.sum() / max(1, present.sum())), 5),
            "area_cm2": float(present.sum()) * CELL_CM * CELL_CM,
            "first_row": first,
            "proxy": False,
        }
        if verbose:
            print("  [%3d/%3d] %-42s %5d obj  %2d sec  %5.1fs"
                  % (mi + 1, len(map_dirs), mname, n_map, len(sectors), time.time() - t0),
                  flush=True)

    table = {}
    for k, v in cols.items():
        if k in ("map", "archetype", "sector", "name", "ptype", "family",
                 "species", "tex", "tclass"):
            table[k] = np.asarray(v, dtype=object)
        elif k in ("crc", "tile", "attr", "wet", "ntok", "rotshape"):
            table[k] = np.asarray(v, dtype=np.int64)
        else:
            table[k] = np.asarray(v, dtype=np.float64)
    return table, maps_meta, problems


# --------------------------------------------------------------------------
# helpers for the report stage
# --------------------------------------------------------------------------

def _q(a, qs=(5, 25, 50, 75, 95)):
    a = np.asarray(a, dtype=np.float64)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return None
    return {("p%d" % q): round(float(np.percentile(a, q)), 2) for q in qs}


def _stat(a, qs=(5, 25, 50, 75, 95)):
    a = np.asarray(a, dtype=np.float64)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return {"n": 0}
    out = {"n": int(a.size), "mean": round(float(a.mean()), 2),
           "min": round(float(a.min()), 2), "max": round(float(a.max()), 2)}
    out.update(_q(a, qs) or {})
    return out


def _hist(a, edges):
    a = np.asarray(a, dtype=np.float64)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return {}
    h, _ = np.histogram(a, bins=list(edges))
    out = {}
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        key = ("%g+" % lo) if hi >= 10 ** 8 else ("%g-%g" % (lo, hi))
        out[key] = int(h[i])
    return out


def _share(counter, top=None, total=None):
    tot = total if total is not None else sum(counter.values())
    items = counter.most_common(top) if top else sorted(counter.items(), key=lambda kv: -kv[1])
    return {k: {"n": v, "share": round(v / tot, 4) if tot else 0.0} for k, v in items}


def _clark_evans(nn, n, area_cm2):
    """Clark-Evans nearest-neighbour index R = mean(NN) / (0.5/sqrt(density)).

    R < 1 clustered, R = 1 Poisson/CSR, R > 1 regular/dispersed.
    """
    nn = np.asarray(nn, dtype=np.float64)
    nn = nn[np.isfinite(nn)]
    if nn.size < 8 or not area_cm2 or n < 8:
        return None
    lam = n / area_cm2
    expected = 0.5 / math.sqrt(lam)
    if expected <= 0:
        return None
    r = float(nn.mean()) / expected
    # z-score of the Clark-Evans statistic
    se = 0.26136 / math.sqrt(n * n / area_cm2)
    z = (float(nn.mean()) - expected) / se if se else 0.0
    return {"R": round(r, 3), "expected_nn_cm": round(expected, 1),
            "observed_nn_cm": round(float(nn.mean()), 1), "n": int(nn.size),
            "z": round(z, 1),
            "verdict": "clustered" if r < 0.9 else ("regular" if r > 1.1 else "poisson")}


def _circ_stats(deg):
    """Circular mean / resultant length / uniformity for an angle sample."""
    a = np.asarray(deg, dtype=np.float64)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return {"n": 0}
    r = np.deg2rad(a % 360.0)
    c, s = float(np.cos(r).mean()), float(np.sin(r).mean())
    R = math.hypot(c, s)
    mean = (math.degrees(math.atan2(s, c))) % 360.0
    # Rayleigh test for non-uniformity
    n = a.size
    z = n * R * R
    p = math.exp(-z) * (1 + (2 * z - z * z) / (4 * n)) if n > 8 else float("nan")
    h36, _ = np.histogram(a % 360.0, bins=36, range=(0, 360))
    return {"n": int(n), "mean_deg": round(mean, 1), "resultant_R": round(R, 4),
            "rayleigh_p": (round(p, 6) if p == p else None),
            "uniform": bool(R < 0.05),
            "zero_share": round(float((np.abs(a % 360.0) < 0.5).mean()), 4),
            "hist36": h36.tolist()}


def _snap_share(deg, step):
    a = np.asarray(deg, dtype=np.float64)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return 0.0
    r = np.minimum(np.abs(a % step), step - np.abs(a % step))
    return round(float((r < 0.5).mean()), 4)


# --------------------------------------------------------------------------
# reports
# --------------------------------------------------------------------------

def build_reports(table, maps_meta, prop_index, problems, sources):
    t = table
    n = len(t["crc"])
    crc = t["crc"]
    fam = t["family"]
    arche = t["archetype"]
    ptype = t["ptype"]
    mapn = t["map"]

    stats = {
        "schema_version": 1,
        "generated_from": sources,
        "corpus": {
            "maps_scanned": len(maps_meta),
            "maps_with_objects": sum(1 for m in maps_meta.values() if m["objects"]),
            "placements": int(n),
            "distinct_crcs": int(len(set(crc.tolist()))),
            "distinct_families": int(len(set(fam.tolist()))),
            "unresolved_crcs": int((ptype == "(unresolved)").sum()),
            "property_rows": len(prop_index),
        },
        "conventions": {
            "units": "world centimetres; 1 cell = 200 cm, 1 tile = 100 cm, "
                     "1 sectree = 25600 cm",
            "y": "areadata y is stored negated; every coordinate here is "
                 "terrain_y = -stored_y",
            "road_class": "no Metin2 terrain texture is named 'road'; the "
                          "<biome>/tile/tileNN.dds family is the path/pavement "
                          "set and is classified 'road' here",
            "distances": "5x5 chamfer (1, sqrt2, sqrt5) distance transform on "
                         "the 200 cm terrain-cell grid; worst-case 2.8 % off "
                         "true Euclidean, mean 1.3 %",
            "clark_evans": "R = mean(nearest-neighbour) / (0.5 / sqrt(density)); "
                           "<0.9 clustered, 0.9-1.1 Poisson, >1.1 regular",
        },
        "problems": problems[:200],
    }

    # ---- frequency --------------------------------------------------------
    order = Counter(crc.tolist())
    ranked = order.most_common()
    per_crc = []
    for rank, (c, cnt) in enumerate(ranked, 1):
        sel = crc == c
        pi = prop_index.get(int(c))
        maps_c = Counter(mapn[sel].tolist())
        arch_c = Counter(arche[sel].tolist())
        row = {
            "rank": rank, "crc": int(c), "n": int(cnt),
            "name": pi.name if pi else "", "type": pi.type if pi else "(unresolved)",
            "family": pi.family if pi else "(unresolved)",
            "model": pi.model if pi else "",
            "maps": len(maps_c),
            "top_maps": [{"map": k, "n": v} for k, v in maps_c.most_common(5)],
            "archetypes": {k: v for k, v in arch_c.most_common()},
        }
        if rank <= TOP_CRC_DETAIL:
            row["nn_same_crc_cm"] = _stat(t["nn_crc"][sel])
            row["nn_other_crc_cm"] = _stat(t["nn_xcrc"][sel])
            row["nn_any_cm"] = _stat(t["nn_any"][sel])
            row["nn_same_crc_hist_cm"] = _hist(t["nn_crc"][sel], NN_EDGES)
            row["height_bias_cm"] = _stat(t["bias"][sel])
            row["yaw"] = _circ_stats(t["yaw"][sel])
            row["roll"] = _circ_stats(t["roll"][sel])
            row["pitch_nonzero_share"] = round(
                float((np.abs(t["pitch"][sel]) > 0.5).mean()), 4)
            row["slope_deg"] = _stat(t["slope"][sel])
        per_crc.append(row)
    stats["by_crc"] = per_crc
    stats["working_vocabulary"] = {
        "note": "CRCs ranked by total placements. The first 100 cover %.1f%% of "
                "all placements, the first 400 cover %.1f%%."
                % (100.0 * sum(c for _, c in ranked[:100]) / n,
                   100.0 * sum(c for _, c in ranked[:400]) / n),
        "coverage": {str(k): round(100.0 * sum(c for _, c in ranked[:k]) / n, 2)
                     for k in (25, 50, 100, 200, 300, 400, 600, 1000)},
        "count": len(ranked),
    }

    # ---- families / types -------------------------------------------------
    fam_rows = {}
    for f, cnt in Counter(fam.tolist()).most_common():
        sel = fam == f
        fam_rows[f] = {
            "n": int(cnt),
            "distinct_crcs": int(len(set(crc[sel].tolist()))),
            "maps": int(len(set(mapn[sel].tolist()))),
            "types": dict(Counter(ptype[sel].tolist())),
            "archetypes": dict(Counter(arche[sel].tolist()).most_common(8)),
            "nn_same_family_cm": _stat(t["nn_fam"][sel]),
            "nn_other_family_cm": _stat(t["nn_xfam"][sel]),
            "nn_same_crc_cm": _stat(t["nn_crc"][sel]),
            "nn_other_crc_cm": _stat(t["nn_xcrc"][sel]),
            "nn_any_cm": _stat(t["nn_any"][sel]),
            "nn_hist_cm": _hist(t["nn_fam"][sel], NN_EDGES),
            "nn_other_family_hist_cm": _hist(t["nn_xfam"][sel], NN_EDGES),
            "height_bias_cm": _stat(t["bias"][sel]),
            "height_bias_negative_share": round(float((t["bias"][sel] < -0.5).mean()), 4),
            "height_bias_zero_share": round(float((np.abs(t["bias"][sel]) < 0.5).mean()), 4),
            "slope_deg": _stat(t["slope"][sel]),
            "slope_hist": _hist(t["slope"][sel], SLOPE_EDGES),
            "yaw": _circ_stats(t["yaw"][sel]),
            "roll": _circ_stats(t["roll"][sel]),
            "pitch": _circ_stats(t["pitch"][sel]),
            "roll_snap_90": _snap_share(t["roll"][sel], 90.0),
            "roll_snap_45": _snap_share(t["roll"][sel], 45.0),
            "roll_snap_15": _snap_share(t["roll"][sel], 15.0),
            "roll_snap_5": _snap_share(t["roll"][sel], 5.0),
            "roll_snap_1": _snap_share(t["roll"][sel], 1.0),
            "pitch_nonzero_share": round(float((np.abs(t["pitch"][sel]) > 0.5).mean()), 4),
            "yaw_nonzero_share": round(float((np.abs(t["yaw"][sel]) > 0.5).mean()), 4),
            "d_road_cm": _stat(t["d_road"][sel]),
            "d_road_hist": _hist(t["d_road"][sel], DIST_EDGES),
            "d_water_cm": _stat(t["d_water"][sel]),
            "d_water_hist": _hist(t["d_water"][sel], DIST_EDGES),
            "d_edge_cm": _stat(t["d_edge"][sel]),
            "on_water_share": round(float((t["wet"][sel] == 1).mean()), 4),
            "top_crcs": [{"crc": int(c), "n": int(v),
                          "name": (prop_index[int(c)].name if int(c) in prop_index else "")}
                         for c, v in Counter(crc[sel].tolist()).most_common(8)],
        }
    stats["by_family"] = fam_rows

    type_rows = {}
    for p, cnt in Counter(ptype.tolist()).most_common():
        sel = ptype == p
        type_rows[p] = {
            "n": int(cnt),
            "distinct_crcs": int(len(set(crc[sel].tolist()))),
            "height_bias_cm": _stat(t["bias"][sel]),
            "slope_deg": _stat(t["slope"][sel]),
            "nn_any_cm": _stat(t["nn_any"][sel]),
            "roll": _circ_stats(t["roll"][sel]),
            "yaw_nonzero_share": round(float((np.abs(t["yaw"][sel]) > 0.5).mean()), 4),
            "pitch_nonzero_share": round(float((np.abs(t["pitch"][sel]) > 0.5).mean()), 4),
        }
    stats["by_type"] = type_rows

    # ---- density / archetype ---------------------------------------------
    arch_area = defaultdict(float)
    arch_maps = defaultdict(list)
    for m, meta in maps_meta.items():
        if meta.get("proxy") or not meta.get("area_cm2"):
            continue
        arch_area[meta["archetype"]] += meta["area_cm2"]
        arch_maps[meta["archetype"]].append(m)

    arch_rows = {}
    for a in sorted(set(arche.tolist())):
        sel = arche == a
        cnt = int(sel.sum())
        area = arch_area.get(a, 0.0)
        ha = area / 1e8                    # cm^2 -> hectare (10 000 m^2)
        row = {
            "placements": cnt,
            "maps": len(arch_maps.get(a, [])),
            "terrain_area_cm2": area,
            "terrain_area_ha": round(ha, 2),
            "sectors": sum(maps_meta[m]["sectors_with_terrain"] for m in arch_maps.get(a, [])),
            "objects_per_ha": round(cnt / ha, 2) if ha else None,
            "objects_per_100m2": round(cnt / (area / 1e6), 4) if area else None,
            "objects_per_sector": round(
                cnt / max(1, sum(maps_meta[m]["sectors_with_terrain"]
                                 for m in arch_maps.get(a, []))), 1),
            "distinct_crcs": int(len(set(crc[sel].tolist()))),
            "by_type": {},
            "by_family": {},
            "nn_any_cm": _stat(t["nn_any"][sel]),
            "clark_evans_all": _clark_evans(t["nn_any"][sel], cnt, area),
            "top_crcs": [{"crc": int(c), "n": int(v),
                          "name": (prop_index[int(c)].name if int(c) in prop_index else "")}
                         for c, v in Counter(crc[sel].tolist()).most_common(20)],
        }
        for p in sorted(set(ptype[sel].tolist())):
            s2 = sel & (ptype == p)
            k = int(s2.sum())
            row["by_type"][p] = {
                "n": k,
                "per_ha": round(k / ha, 2) if ha else None,
                "per_100m2": round(k / (area / 1e6), 4) if area else None,
                "share": round(k / cnt, 4),
            }
        for f, v in Counter(fam[sel].tolist()).most_common(14):
            s2 = sel & (fam == f)
            row["by_family"][f] = {
                "n": int(v),
                "per_ha": round(v / ha, 2) if ha else None,
                "share": round(v / cnt, 4),
                "nn_same_family_cm": _stat(t["nn_fam"][s2], qs=(5, 25, 50, 75, 95)),
                "clark_evans": _clark_evans(t["nn_fam"][s2], int(v), area),
            }
        arch_rows[a] = row
    stats["by_archetype"] = arch_rows

    # ---- per map ----------------------------------------------------------
    stats["by_map"] = {}
    for m, meta in sorted(maps_meta.items()):
        sel = mapn == m
        cnt = int(sel.sum())
        area = meta.get("area_cm2", 0.0)
        stats["by_map"][m] = {
            "archetype": meta["archetype"],
            "objects": cnt,
            "sectors": meta["sectors"],
            "grid": meta.get("grid"),
            "objects_per_ha": round(cnt / (area / 1e8), 2) if area else None,
            "road_cover": meta.get("road_cover"),
            "water_cover": meta.get("water_cover"),
            "distinct_crcs": int(len(set(crc[sel].tolist()))) if cnt else 0,
            "top_families": dict(Counter(fam[sel].tolist()).most_common(6)) if cnt else {},
        }

    # ---- rotation policy summary -----------------------------------------
    stats["rotation_policy"] = {
        "note": "index 4 of an areadata record is yaw#pitch#roll in degrees. "
                "The engine reads it with atoi, so fractions are truncated; "
                "roll is the heading around Z and is the only channel most "
                "objects use.",
        "token_shapes": dict(Counter(t["rotshape"].tolist())),
        "token_shape_legend": {"0": "no rotation token (4-token record)",
                               "1": "bare value = roll only (legacy)",
                               "3": "yaw#pitch#roll"},
        "channel_use": {
            "yaw_nonzero": int((np.abs(t["yaw"]) > 0.5).sum()),
            "pitch_nonzero": int((np.abs(t["pitch"]) > 0.5).sum()),
            "roll_nonzero": int((np.abs(t["roll"]) > 0.5).sum()),
            "all_zero": int(((np.abs(t["yaw"]) < 0.5) & (np.abs(t["pitch"]) < 0.5)
                             & (np.abs(t["roll"]) < 0.5)).sum()),
        },
        "roll_integer_share": round(float((np.abs(t["roll"] - np.round(t["roll"])) < 1e-6).mean()), 4),
    }

    # ---- height-bias summary ---------------------------------------------
    dz = t["z"] + t["bias"] - t["terr_z"]
    stats["height_model"] = {
        "note": "final_z = z + heightBias. terrain_z is the height.raw vertex "
                "under the placement (raw * 0.5). dz = final_z - terrain_z.",
        "bias_cm": _stat(t["bias"]),
        "bias_zero_share": round(float((np.abs(t["bias"]) < 0.5).mean()), 4),
        "bias_negative_share": round(float((t["bias"] < -0.5).mean()), 4),
        "dz_cm": _stat(dz),
        "dz_within_50cm_share": round(float((np.abs(dz[np.isfinite(dz)]) < 50).mean()), 4)
        if np.isfinite(dz).any() else None,
    }

    return stats


TERRAIN_ART_ROOT = r"D:/ymir work/terrainmaps"
YMIR_ART_ROOT = r"D:/ymir work"


def texture_catalog(paths, art_root=TERRAIN_ART_ROOT, ymir_root=YMIR_ART_ROOT):
    """Measured mean RGB of each terrain texture, next to its name-derived class.

    The class rules read filenames, and filenames lie -- ``A/stone/stone01.dds``
    is a tan dirt texture (mean RGB 159,135,112), not grey stone.  Publishing
    the measured colour lets a reader audit every class assignment.
    """
    root = pathlib.Path(art_root)
    out = {}
    for rel in sorted(set(paths)):
        if not rel:
            continue
        row = {"class": terrain_class(rel)}
        # A few textureset entries are absolute under "ymir work" rather than
        # relative to terrainmaps (zone/dungeon/**), and one ships a stray
        # leading slash ("/b/tile/tile01.dds"), so probe both roots.
        cand = [root / rel, pathlib.Path(ymir_root) / rel,
                root / rel.lstrip("/")]
        row["mean_rgb"] = None
        for f in cand:
            try:
                from PIL import Image
                with Image.open(f) as im:
                    a = np.asarray(im.convert("RGB"), dtype=np.float64)
                    row["mean_rgb"] = [int(round(v)) for v in a.reshape(-1, 3).mean(0)]
                    row["size"] = list(im.size)
                break
            except Exception:
                continue
        if row["mean_rgb"] is None:
            row["missing_on_disk"] = True
        out[rel] = row
    return out


def build_affinity(table, prop_index):
    t = table
    crc, fam = t["crc"], t["family"]
    out = {
        "schema_version": 1,
        "note": "Ground-texture and slope affinity for every placement, joined "
                "from tile.raw (the byte under the object indexes the map's "
                "TextureSet) and height.raw (per-cell slope). Classes: "
                + ", ".join(k for k, _ in _TEX_RULE_SRC) + ", other, (none).",
        "class_rules": {k: [p for p in v] for k, v in _TEX_RULE_SRC},
        "corpus_baseline": {},
        "by_family": {},
        "by_crc": {},
        "by_archetype": {},
    }
    out["texture_catalog"] = texture_catalog(t["tex"].tolist())
    base = Counter(t["tclass"].tolist())
    out["corpus_baseline"] = {
        "class_share": _share(base),
        "slope_deg": _stat(t["slope"]),
        "slope_hist": _hist(t["slope"], SLOPE_EDGES),
        "attr_block_share": round(float(((t["attr"] & 0x01) == 1).mean()), 4),
        "on_water_share": round(float((t["wet"] == 1).mean()), 4),
    }

    for a in sorted(set(t["archetype"].tolist())):
        sel = t["archetype"] == a
        out["by_archetype"][a] = {
            "n": int(sel.sum()),
            "class_share": _share(Counter(t["tclass"][sel].tolist())),
            "slope_deg": _stat(t["slope"][sel]),
            "slope_hist": _hist(t["slope"][sel], SLOPE_EDGES),
        }

    base_tot = sum(base.values())
    for f, cnt in Counter(fam.tolist()).most_common():
        sel = fam == f
        c = Counter(t["tclass"][sel].tolist())
        tot = sum(c.values())
        lift = {}
        for k in base:
            obs = c.get(k, 0) / tot if tot else 0.0
            exp = base[k] / base_tot
            lift[k] = round(obs / exp, 3) if exp else None
        out["by_family"][f] = {
            "n": int(cnt),
            "class_share": _share(c),
            "class_lift_vs_corpus": lift,
            "never_on": sorted(k for k in base if c.get(k, 0) == 0 and base[k] >= 200),
            "slope_deg": _stat(t["slope"][sel]),
            "slope_hist": _hist(t["slope"][sel], SLOPE_EDGES),
            "top_textures": _share(Counter(t["tex"][sel].tolist()), top=10),
            "on_water_share": round(float((t["wet"][sel] == 1).mean()), 4),
            "attr_block_share": round(float(((t["attr"][sel] & 0x01) == 1).mean()), 4),
            "attr_banpk_share": round(float(((t["attr"][sel] & 0x04) == 4).mean()), 4),
            "attr_byte_top": _share(Counter(t["attr"][sel].tolist()), top=6),
            "d_road_cm": _stat(t["d_road"][sel]),
            "d_water_cm": _stat(t["d_water"][sel]),
            "d_edge_cm": _stat(t["d_edge"][sel]),
        }

    for c_, cnt in Counter(crc.tolist()).most_common(TOP_CRC_DETAIL):
        sel = crc == c_
        pi = prop_index.get(int(c_))
        cc = Counter(t["tclass"][sel].tolist())
        out["by_crc"][str(int(c_))] = {
            "n": int(cnt),
            "name": pi.name if pi else "",
            "type": pi.type if pi else "",
            "family": pi.family if pi else "",
            "class_share": _share(cc),
            "never_on": sorted(k for k in base if cc.get(k, 0) == 0 and base[k] >= 200),
            "slope_deg": _stat(t["slope"][sel]),
            "slope_hist": _hist(t["slope"][sel], SLOPE_EDGES),
            "top_textures": _share(Counter(t["tex"][sel].tolist()), top=6),
            "d_road_cm": _q(t["d_road"][sel]),
            "d_water_cm": _q(t["d_water"][sel]),
            "d_edge_cm": _q(t["d_edge"][sel]),
            "on_water_share": round(float((t["wet"][sel] == 1).mean()), 4),
        }
    return out


def build_cooccurrence(table, maps_meta, prop_index, min_obs=10, top=900):
    """Pair lift: observed co-locations vs the CSR expectation, per radius.

    ``E = n_a * n_b * pi r^2 / A`` summed over maps (``A`` = that map's terrain
    area), i.e. what you would see if both CRCs were scattered independently
    and uniformly.  ``lift = O/E``.  Pass 1 counts observations; pass 2 only
    computes expectations for pairs that were actually observed, which keeps
    the accumulator small.
    """
    t = table
    crcs = sorted(set(t["crc"].tolist()))
    cid = {c: i for i, c in enumerate(crcs)}
    NC = len(crcs)
    ids_all = np.array([cid[c] for c in t["crc"].tolist()], dtype=np.int64)

    obs = {r: Counter() for r in CO_RADII}
    self_obs = {r: Counter() for r in CO_RADII}
    per_map = []

    for m, meta in maps_meta.items():
        if not meta.get("objects"):
            continue
        area = meta.get("area_cm2") or 0.0
        if area <= 0:
            continue
        sel = np.where(t["map"] == m)[0]
        if len(sel) < 2:
            continue
        x = t["x"][sel]
        y = t["y"][sel]
        ids = ids_all[sel]
        per_map.append((Counter(ids.tolist()), area))
        rmax = max(CO_RADII)
        bx = np.floor(x / rmax).astype(np.int64)
        by = np.floor(y / rmax).astype(np.int64)
        buckets = defaultdict(list)
        for i in range(len(sel)):
            buckets[(int(bx[i]), int(by[i]))].append(i)
        for key, idxs in buckets.items():
            ja = np.asarray(idxs)
            for dxb, dyb in ((0, 0), (0, 1), (1, -1), (1, 0), (1, 1)):
                nk = (key[0] + dxb, key[1] + dyb)
                nb = buckets.get(nk)
                if nb is None:
                    continue
                jb = np.asarray(nb)
                same = (dxb == 0 and dyb == 0)
                dx = x[ja][:, None] - x[jb][None, :]
                dy = y[ja][:, None] - y[jb][None, :]
                d2 = dx * dx + dy * dy
                if same:
                    d2 = np.triu(d2, 1) + np.tril(np.full_like(d2, np.inf))
                a_ = ids[ja][:, None]
                b_ = ids[jb][None, :]
                lo = np.minimum(a_, b_)
                hi = np.maximum(a_, b_)
                pk = lo * NC + hi
                for r in CO_RADII:
                    hit = d2 <= float(r) * r
                    if not hit.any():
                        continue
                    k, c = np.unique(pk[hit], return_counts=True)
                    for kk, cc in zip(k.tolist(), c.tolist()):
                        a2, b2 = divmod(kk, NC)
                        if a2 == b2:
                            self_obs[r][a2] += cc
                        else:
                            obs[r][(a2, b2)] += cc

    # pass 2: expectations, only for pairs that were observed
    want = {r: set(obs[r]) for r in CO_RADII}
    want_self = {r: set(self_obs[r]) for r in CO_RADII}
    exp = {r: defaultdict(float) for r in CO_RADII}
    self_exp = {r: defaultdict(float) for r in CO_RADII}
    for counts, area in per_map:
        keys = sorted(counts)
        for r in CO_RADII:
            frac = math.pi * r * r / area
            w, ws = want[r], want_self[r]
            for i, a_ in enumerate(keys):
                na = counts[a_]
                if a_ in ws:
                    self_exp[r][a_] += na * (na - 1) / 2.0 * frac
                for b_ in keys[i + 1:]:
                    if (a_, b_) in w:
                        exp[r][(a_, b_)] += na * counts[b_] * frac

    def _info(i):
        c = crcs[i]
        pi = prop_index.get(int(c))
        return int(c), (pi.name if pi else ""), (pi.family if pi else "")

    out = {
        "schema_version": 1,
        "note": "Observed co-locations within r vs the complete-spatial-"
                "randomness expectation E = n_a * n_b * pi r^2 / A summed over "
                "maps (A = that map's terrain area). lift = O/E. Pairs are "
                "unordered and counted once per object pair; same-CRC "
                "self-clumping is reported separately. Only pairs with "
                "obs >= %d are listed." % min_obs,
        "radii_cm": list(CO_RADII),
        "pairs": {},
        "self_clumping": {},
    }
    for r in CO_RADII:
        rows = []
        for (ia, ib), o in obs[r].items():
            e = exp[r].get((ia, ib), 0.0)
            if o < min_obs or e <= 0:
                continue
            ca, na_, fa = _info(ia)
            cb, nb_, fb = _info(ib)
            rows.append({"a": ca, "b": cb, "a_name": na_, "b_name": nb_,
                         "a_family": fa, "b_family": fb,
                         "obs": int(o), "exp": round(e, 2),
                         "lift": round(o / e, 2)})
        rows.sort(key=lambda d: -d["lift"])
        out["pairs"][str(r)] = rows[:top]
        srows = []
        for ia, o in self_obs[r].items():
            e = self_exp[r].get(ia, 0.0)
            if o < min_obs or e <= 0:
                continue
            c, nm, fm = _info(ia)
            srows.append({"crc": c, "name": nm, "family": fm, "obs": int(o),
                          "exp": round(e, 2), "lift": round(o / e, 2)})
        srows.sort(key=lambda d: -d["lift"])
        out["self_clumping"][str(r)] = srows[:top]

    # family-level co-occurrence, same measure but aggregated
    fam_of = {}
    for c in crcs:
        pi = prop_index.get(int(c))
        fam_of[cid[c]] = pi.family if pi else "(unresolved)"
    fam_rows = {}
    for r in CO_RADII:
        fo = Counter()
        fe = defaultdict(float)
        for (ia, ib), o in obs[r].items():
            fa, fb = fam_of[ia], fam_of[ib]
            k = (fa, fb) if fa <= fb else (fb, fa)
            fo[k] += o
            fe[k] += exp[r].get((ia, ib), 0.0)
        for ia, o in self_obs[r].items():
            k = (fam_of[ia], fam_of[ia])
            fo[k] += o
            fe[k] += self_exp[r].get(ia, 0.0)
        rows = [{"a_family": a, "b_family": b, "obs": int(o),
                 "exp": round(fe[(a, b)], 2),
                 "lift": round(o / fe[(a, b)], 2)}
                for (a, b), o in fo.items() if fe.get((a, b), 0) > 0 and o >= min_obs]
        rows.sort(key=lambda d: -d["lift"])
        fam_rows[str(r)] = rows[:200]
    out["family_pairs"] = fam_rows

    # per-CRC companion lists at 15 m -- the directly usable form: "when you
    # place A, what else is usually within 15 m of it".
    comp = defaultdict(list)
    r = 1500
    for (ia, ib), o in obs[r].items():
        e = exp[r].get((ia, ib), 0.0)
        if o < 5 or e <= 0:
            continue
        ca, na_, _ = _info(ia)
        cb, nb_, _ = _info(ib)
        comp[ca].append({"crc": cb, "name": nb_, "obs": int(o), "lift": round(o / e, 2)})
        comp[cb].append({"crc": ca, "name": na_, "obs": int(o), "lift": round(o / e, 2)})
    companions = {}
    for c, rows in comp.items():
        rows.sort(key=lambda d: -d["obs"])
        pi = prop_index.get(int(c))
        companions[str(c)] = {"name": pi.name if pi else "",
                              "family": pi.family if pi else "",
                              "top_by_obs": rows[:10],
                              "top_by_lift": sorted(rows, key=lambda d: -d["lift"])[:10]}
    out["companions_15m"] = companions
    return out


# --------------------------------------------------------------------------
# cache / cli
# --------------------------------------------------------------------------

def _save_cache(path, table, maps_meta, problems):
    path = pathlib.Path(path)
    path.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path / "placements.npz",
                        **{k: v for k, v in table.items()})
    (path / "maps_meta.json").write_text(
        json.dumps({"maps": maps_meta, "problems": problems}, indent=1),
        encoding="utf-8")


def _load_cache(path):
    path = pathlib.Path(path)
    f = path / "placements.npz"
    g = path / "maps_meta.json"
    if not f.exists() or not g.exists():
        return None
    z = np.load(f, allow_pickle=True)
    table = {k: z[k] for k in z.files}
    meta = json.loads(g.read_text(encoding="utf-8"))
    return table, meta["maps"], meta["problems"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--maps", default=DEFAULTS["maps"])
    ap.add_argument("--property", dest="property_root", default=DEFAULTS["property"])
    ap.add_argument("--textureset", default=DEFAULTS["textureset"])
    ap.add_argument("--taxonomy", default=DEFAULTS["taxonomy"])
    ap.add_argument("--out", default=DEFAULTS["out"])
    ap.add_argument("--cache", default=None)
    ap.add_argument("--rescan", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    verbose = not args.quiet
    tax = {}
    if args.taxonomy and pathlib.Path(args.taxonomy).exists():
        tax = json.loads(pathlib.Path(args.taxonomy).read_text(encoding="utf-8")).get("maps", {})

    if verbose:
        print("indexing properties ...", flush=True)
    prop_index = build_property_index(args.property_root)
    ts_cache = TextureSetCache(args.textureset)

    cached = None
    if args.cache and not args.rescan:
        cached = _load_cache(args.cache)
    if cached:
        table, maps_meta, problems = cached
        if verbose:
            print("loaded %d placements from cache" % len(table["crc"]), flush=True)
    else:
        if verbose:
            print("scanning %s ..." % args.maps, flush=True)
        table, maps_meta, problems = scan_corpus(args.maps, prop_index, ts_cache,
                                                 tax, verbose=verbose)
        if args.cache:
            _save_cache(args.cache, table, maps_meta, problems)

    sources = {
        "maps": args.maps, "property": args.property_root,
        "textureset": args.textureset, "taxonomy": args.taxonomy,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if verbose:
        print("building stats-objects.json ...", flush=True)
    stats = build_reports(table, maps_meta, prop_index, problems, sources)
    (out / "stats-objects.json").write_text(
        json.dumps(stats, indent=1, ensure_ascii=False), encoding="utf-8")

    if verbose:
        print("building affinity.json ...", flush=True)
    aff = build_affinity(table, prop_index)
    aff["generated_from"] = sources
    (out / "affinity.json").write_text(
        json.dumps(aff, indent=1, ensure_ascii=False), encoding="utf-8")

    if verbose:
        print("building cooccurrence.json ...", flush=True)
    co = build_cooccurrence(table, maps_meta, prop_index)
    co["generated_from"] = sources
    (out / "cooccurrence.json").write_text(
        json.dumps(co, indent=1, ensure_ascii=False), encoding="utf-8")

    if verbose:
        for f in ("stats-objects.json", "affinity.json", "cooccurrence.json"):
            print("  wrote %s (%.1f KB)" % (out / f, (out / f).stat().st_size / 1024))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Measure the attribute (collision) grammar of a Metin2 map corpus.

Reads every ``<map>/<XXXYYY>/attr.atr`` in a corpus, joins it against the
sector's ``height.raw`` (slope), ``water.wtr`` (water truth) and
``areadata.txt`` (object placements, CRC-resolved through ``property/**``),
and emits one JSON document describing how the shipped maps actually use the
eight attribute bits.

Specs consulted: ``reference/mapformat/attr-atr.md`` (flag bits, paint-byte
conventions, 2x resolution vs the heightmap), ``height-raw.md`` (131x131 skirt,
``worldZ = raw * 0.5``, cell = 200 cm), ``water-wtr.md`` (128x128 layer grid,
``0xFF`` = dry, "painting water also stamps ``ATTRIBUTE_WATER`` into the 2x2
attr cells"), ``server-attr.md`` (the documented 2x2 upsample), and
``areadata-txt.md`` (map-local cm, Y negated).

Grid alignment used throughout
------------------------------
====================  =========  ==============  =====================
Grid                  Per sector Cell edge (cm)  Brought to attr res by
====================  =========  ==============  =====================
attr.atr              256x256    100             --
height.raw cells      128x128    200             ``np.repeat(...,2,axis)``
water.wtr             128x128    200             ``np.repeat(...,2,axis)``
====================  =========  ==============  =====================

So one attr cell is 1 m and every count in the output can be read as square
metres.  Slope is computed per terrain cell from the 129x129 vertex grid
(``height.slope_degrees``) and each terrain cell's slope is shared by its 2x2
attr cells.

What it measures
----------------
* per-flag coverage and the full attribute-byte histogram, per map / archetype
  / attr-style / corpus;
* ``BLOCK`` against terrain slope -- the joint distribution, and the threshold
  ``slope >= T`` that best separates blocked from walkable (Youden's *J*, which
  unlike F1 does not degenerate when almost everything is blocked);
* a **block budget** charging every blocked cell to exactly one cause
  (slope, water, object halo, out-of-bounds, residual), which is how the
  question "how much block does slope *not* explain" gets answered;
* ``ATTRIBUTE_WATER`` against ``water.wtr``, both raw and against the
  *submerged* predicate (wet **and** terrain below the layer surface);
* ``ATTRIBUTE_BANPK`` component shapes -- the editor's circular brush leaves a
  fill ratio of pi/4, which the report detects and reports as a diameter;
* map borders, as the consecutive BLOCK run inward from every edge cell plus
  the edge-connected out-of-bounds component;
* per-CRC footprint size implied by the blocked cells around each placement,
  and whether a map paints footprints at all (local-control lift).

CLI
---
``python -m m2map.mine.attr_stats --corpus <CORPUS> --out stats-attr.json``

Optional ``--taxonomy`` joins each map to its archetype (from
``reference/catalog/map-taxonomy.json``); ``--property-root`` resolves
areadata CRCs to property type / model path so footprints can be reported per
model (``--crc-cache FILE`` memoises that scan).
``--selftest-server-attr <mapdir>`` checks the documented ``attr.atr`` ->
``server_attr`` 2x2 upsample by building one and reading it back.

Findings this produced are written up in ``reference/attributes.md``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from typing import Dict, List, Optional, Tuple

import numpy as np

if __package__ in (None, ""):                                # direct execution
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))

from m2map.codec import attr as attr_codec
from m2map.codec import height as height_codec
from m2map.codec import water as water_codec
from m2map.codec.areadata import AreaData
from m2map.codec.property import PropertyFile
from m2map.codec.setting import Setting

# --------------------------------------------------------------------------
# constants
# --------------------------------------------------------------------------

ATTR_N = attr_codec.WIDTH                       # 256 attr cells per sector edge
ATTR_CM = attr_codec.CELL_SCALE                 # 100 cm per attr cell
SECTOR_CM = height_codec.SECTOR_SIZE            # 25,600 cm per sector edge

#: Slope histogram edges in degrees; last bin is [80, 90].
SLOPE_EDGES = (0.0, 1.0, 2.0, 3.0, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0, 25.0,
               30.0, 35.0, 40.0, 45.0, 50.0, 60.0, 70.0, 80.0, 90.0001)

#: Integer-degree sweep used to pick the F1-optimal "slope explains block" cut.
SWEEP_DEG = tuple(range(0, 81))

#: Window (attr cells = metres) sampled around an object placement.
FOOTPRINT_WINDOW = 32
#: Chebyshev distance (attr cells) to the nearest *other* solid placement
#: required before a placement counts as "isolated" for footprint estimation.
#: Effects and ambience emitters are ignored -- they routinely sit *inside* a
#: building (campfire in a hut) and would veto every placement.
FOOTPRINT_ISOLATION = 8
FOOTPRINT_SOLID_TYPES = ("Building", "DungeonBlock", "Tree")
#: Ring must be at least this full of BLOCK to still count as footprint.
FOOTPRINT_FILL = 0.5
#: Chebyshev halo (metres) around a placement used to attribute BLOCK to
#: objects and to exclude object-influenced cells from the slope regression.
OBJECT_HALO = 12
#: Offset (metres) of the control samples used to decide whether a map paints
#: building footprints into attr or leaves collision to the model.
CONTROL_OFFSET = 30

#: Row/column is part of the border band while at least this fraction of its
#: valid cells carry BLOCK.
BORDER_STRICT = 0.90
BORDER_LOOSE = 0.50

#: Safezone components smaller than this are noise, not a zone.
SAFEZONE_MIN_CELLS = 16

FLAG_BITS = tuple(attr_codec.FLAG_NAMES)        # ((0x01,"block"), ...)
FLAG_NAMES = [name for _bit, name in FLAG_BITS]


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def _pct(num: int, den: int) -> float:
    return round(100.0 * num / den, 6) if den else 0.0


def _frac(num: int, den: int) -> float:
    return round(float(num) / den, 8) if den else 0.0


def _quantiles(values, qs=(0.05, 0.25, 0.5, 0.75, 0.95)) -> Dict[str, float]:
    if not len(values):
        return {}
    arr = np.asarray(values, dtype=np.float64)
    out = {"n": int(arr.size), "min": float(arr.min()), "max": float(arr.max()),
           "mean": round(float(arr.mean()), 4)}
    for q in qs:
        out["p%02d" % int(round(q * 100))] = round(float(np.quantile(arr, q)), 4)
    return out


def sector_dirs(map_dir: str) -> List[Tuple[int, int, str]]:
    """``(sx, sy, path)`` for every ``XXXYYY`` folder, sorted."""
    out = []
    try:
        names = sorted(os.listdir(map_dir))
    except OSError:
        return out
    for name in names:
        if len(name) != 6 or not name.isdigit():
            continue
        path = os.path.join(map_dir, name)
        if os.path.isdir(path):
            out.append((int(name[:3]), int(name[3:]), path))
    return out


def label_components(mask: np.ndarray, connectivity: int = 4):
    """4- or 8-connected components of a boolean mask.

    Returns ``(labels_int32, count)``; label 0 is background.  Run-length
    union-find (no scipy in this environment): each row is reduced to maximal
    True runs and adjacent rows' overlapping runs are merged, which keeps the
    cost proportional to the number of runs rather than the number of cells.
    """
    mask = np.asarray(mask, dtype=bool)
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    if not mask.any():
        return labels, 0

    slack = 1 if connectivity == 8 else 0
    parent: List[int] = [0]                     # index 0 unused

    def find(a: int) -> int:
        root = a
        while parent[root] != root:
            root = parent[root]
        while parent[a] != root:
            parent[a], a = root, parent[a]
        return root

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    zero = np.zeros(1, dtype=np.int8)
    prev: List[Tuple[int, int, int]] = []       # (start, end_exclusive, run_id)
    runs: List[Tuple[int, int, int, int]] = []  # (row, start, end, run_id)
    for y in range(h):
        row = mask[y].view(np.int8)
        d = np.diff(np.concatenate((zero, row, zero)))
        starts = np.flatnonzero(d == 1)
        ends = np.flatnonzero(d == -1)
        cur: List[Tuple[int, int, int]] = []
        j = 0
        for s, e in zip(starts.tolist(), ends.tolist()):
            parent.append(len(parent))
            rid = len(parent) - 1
            while j < len(prev) and prev[j][1] + slack <= s:
                j += 1
            k = j
            while k < len(prev) and prev[k][0] < e + slack:
                union(rid, prev[k][2])
                k += 1
            cur.append((s, e, rid))
            runs.append((y, s, e, rid))
        prev = cur

    remap: Dict[int, int] = {}
    for y, s, e, rid in runs:
        root = find(rid)
        lab = remap.get(root)
        if lab is None:
            lab = len(remap) + 1
            remap[root] = lab
        labels[y, s:e] = lab
    return labels, len(remap)


def component_at(mask: np.ndarray, cy: int, cx: int,
                 connectivity: int = 4) -> np.ndarray:
    """Boolean mask of the component of ``mask`` containing ``(cy, cx)``.

    Iterative 4/8-connected dilation constrained to ``mask`` -- cheap for the
    small footprint windows this module uses.
    """
    mask = np.asarray(mask, dtype=bool)
    out = np.zeros_like(mask)
    if not mask[cy, cx]:
        return out
    out[cy, cx] = True
    while True:
        grown = out.copy()
        grown[1:, :] |= out[:-1, :]
        grown[:-1, :] |= out[1:, :]
        grown[:, 1:] |= out[:, :-1]
        grown[:, :-1] |= out[:, 1:]
        if connectivity == 8:
            grown[1:, 1:] |= out[:-1, :-1]
            grown[1:, :-1] |= out[:-1, 1:]
            grown[:-1, 1:] |= out[1:, :-1]
            grown[:-1, :-1] |= out[1:, 1:]
        grown &= mask
        if np.array_equal(grown, out):
            return out
        out = grown


# --------------------------------------------------------------------------
# CRC registry
# --------------------------------------------------------------------------

def build_crc_index(property_root: str) -> Dict[int, Dict[str, str]]:
    """``crc -> {type, name, model}`` over every ``property/**/*.pr?``.

    Last file wins on a duplicate CRC, matching ``CPropertyManager::Register``.
    """
    import pathlib

    index: Dict[int, Dict[str, str]] = {}
    for p in sorted(pathlib.Path(property_root).rglob("*")):
        if not p.is_file() or not p.suffix.lower().startswith(".pr"):
            continue
        try:
            prop = PropertyFile.load(p)
        except (ValueError, OSError):
            continue
        index[prop.crc] = {
            "type": prop.property_type,
            "name": prop.name,
            "model": (prop.model_file or "").replace("\\", "/"),
        }
    return index


def load_crc_index(property_root: Optional[str], cache: Optional[str]):
    if cache and os.path.exists(cache):
        with open(cache, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        return {int(k): v for k, v in raw.items()}
    if not property_root:
        return {}
    index = build_crc_index(property_root)
    if cache:
        with open(cache, "w", encoding="utf-8") as fh:
            json.dump({str(k): v for k, v in index.items()}, fh)
    return index


# --------------------------------------------------------------------------
# assembled map grids
# --------------------------------------------------------------------------

class MapGrids:
    """One map's attr / slope / water grids stitched into map-local space.

    All arrays are ``[row, col]`` = ``[y, x]`` at attr resolution (1 m), sized
    ``(sy_max + 1) * 256`` by ``(sx_max + 1) * 256`` over the sector folders
    that actually exist.  ``valid`` marks cells backed by a real sector.
    """

    __slots__ = ("name", "path", "setting", "sectors", "gw", "gh",
                 "attr", "slope", "water", "submerged", "valid",
                 "has_water_file", "byte_hist", "problems")

    def __init__(self, name, path):
        self.name = name
        self.path = path
        self.setting = None
        self.sectors: List[Tuple[int, int, str]] = []
        self.gw = self.gh = 0
        self.attr = self.slope = self.water = self.valid = None
        self.submerged = None
        self.has_water_file = 0
        self.byte_hist = np.zeros(256, dtype=np.int64)
        self.problems: List[str] = []

    @classmethod
    def load(cls, map_dir: str, height_scale: Optional[float] = None) -> "MapGrids":
        name = os.path.basename(map_dir.rstrip("\\/"))
        g = cls(name, map_dir)
        setting_path = os.path.join(map_dir, "setting.txt")
        if os.path.exists(setting_path):
            try:
                g.setting = Setting.load(setting_path)
            except Exception as exc:                         # noqa: BLE001
                g.problems.append("setting.txt unreadable: %s" % exc)
        hs = height_scale
        if hs is None:
            hs = g.setting.height_scale if g.setting else height_codec.DEFAULT_HEIGHT_SCALE
        if not hs:
            hs = height_codec.DEFAULT_HEIGHT_SCALE

        g.sectors = sector_dirs(map_dir)
        if not g.sectors:
            return g
        g.gw = (max(s[0] for s in g.sectors) + 1) * ATTR_N
        g.gh = (max(s[1] for s in g.sectors) + 1) * ATTR_N
        g.attr = np.zeros((g.gh, g.gw), dtype=np.uint8)
        g.slope = np.full((g.gh, g.gw), np.nan, dtype=np.float32)
        g.water = np.zeros((g.gh, g.gw), dtype=bool)
        g.submerged = np.zeros((g.gh, g.gw), dtype=bool)
        g.valid = np.zeros((g.gh, g.gw), dtype=bool)

        for sx, sy, spath in g.sectors:
            y0, x0 = sy * ATTR_N, sx * ATTR_N
            ap = os.path.join(spath, "attr.atr")
            if not os.path.exists(ap):
                g.problems.append("%s: no attr.atr" % os.path.basename(spath))
                continue
            try:
                amap = attr_codec.read_attr(ap)
            except (ValueError, OSError) as exc:
                g.problems.append("%s: attr.atr rejected (%s)" % (os.path.basename(spath), exc))
                continue
            g.attr[y0:y0 + ATTR_N, x0:x0 + ATTR_N] = amap.cells
            g.valid[y0:y0 + ATTR_N, x0:x0 + ATTR_N] = True
            g.byte_hist += np.bincount(amap.cells.ravel(), minlength=256)

            cell_z = None
            hp = os.path.join(spath, "height.raw")
            if os.path.exists(hp):
                try:
                    hm = height_codec.read_height(hp)
                    slope = hm.slope_degrees(height_scale=hs).astype(np.float32)
                    g.slope[y0:y0 + ATTR_N, x0:x0 + ATTR_N] = np.repeat(
                        np.repeat(slope, 2, axis=0), 2, axis=1)
                    v = hm.vertices.astype(np.float64) * float(hs)
                    cell_z = np.minimum(np.minimum(v[:-1, :-1], v[:-1, 1:]),
                                        np.minimum(v[1:, :-1], v[1:, 1:]))
                except (ValueError, OSError) as exc:
                    g.problems.append("%s: height.raw rejected (%s)"
                                      % (os.path.basename(spath), exc))

            wp = os.path.join(spath, "water.wtr")
            if os.path.exists(wp):
                g.has_water_file += 1
                try:
                    wm = water_codec.read_water(wp)
                    wet = wm.wet_mask
                    g.water[y0:y0 + ATTR_N, x0:x0 + ATTR_N] = np.repeat(
                        np.repeat(wet, 2, axis=0), 2, axis=1)
                    if cell_z is not None and wet.any():
                        n = len(wm.heights)
                        table = np.asarray(list(wm.heights) + [0], dtype=np.float64) * float(hs)
                        idx = np.where(wet, np.minimum(wm.cells, n), n)
                        sub = wet & (cell_z < table[idx])
                        g.submerged[y0:y0 + ATTR_N, x0:x0 + ATTR_N] = np.repeat(
                            np.repeat(sub, 2, axis=0), 2, axis=1)
                except (ValueError, OSError) as exc:
                    g.problems.append("%s: water.wtr rejected (%s)"
                                      % (os.path.basename(spath), exc))
        return g

    # -- derived masks -----------------------------------------------------
    def flag_mask(self, bit: int) -> np.ndarray:
        return (self.attr & np.uint8(bit)) != 0

    @property
    def is_rectangular(self) -> bool:
        """True when every sector of the bounding box exists (no ragged edge)."""
        have = {(sx, sy) for sx, sy, _ in self.sectors}
        return len(have) == (self.gw // ATTR_N) * (self.gh // ATTR_N)


def load_objects(map_dir: str, crc_index) -> List[dict]:
    """Every ``areadata.txt`` record of a map, in attr-cell coordinates.

    ``areadata`` stores map-local cm with Y negated, so the attr cell is
    ``(x / 100, -y / 100)``.
    """
    out = []
    for sx, sy, spath in sector_dirs(map_dir):
        ap = os.path.join(spath, "areadata.txt")
        if not os.path.exists(ap):
            continue
        try:
            area = AreaData.load(ap)
        except (ValueError, OSError):
            continue
        for rec in area.records:
            info = crc_index.get(rec.crc) if crc_index else None
            out.append({
                "crc": rec.crc,
                "cx": int(rec.x // ATTR_CM),
                "cy": int(rec.terrain_y // ATTR_CM),
                "sector": (sx, sy),
                "type": (info or {}).get("type", ""),
                "model": (info or {}).get("model", ""),
                "name": (info or {}).get("name", ""),
            })
    return out


# --------------------------------------------------------------------------
# accumulators
# --------------------------------------------------------------------------

class Accum:
    """Additive counters so map / archetype / corpus share one code path."""

    def __init__(self):
        self.cells = 0
        self.sectors = 0
        self.maps = 0
        self.flag_cells = Counter()
        self.byte_hist = np.zeros(256, dtype=np.int64)
        # paint-byte usage
        self.high_bit_cells = 0
        self.maps_using_high_bits = 0
        self.block_and_water = 0
        self.safezone_and_block = 0
        # slope joint
        self.slope_total = np.zeros(len(SLOPE_EDGES) - 1, dtype=np.int64)
        self.slope_block = np.zeros(len(SLOPE_EDGES) - 1, dtype=np.int64)
        self.slope_cells = 0
        self.sweep_steep = np.zeros(len(SWEEP_DEG), dtype=np.int64)
        self.sweep_steep_block = np.zeros(len(SWEEP_DEG), dtype=np.int64)
        self.block_cells_with_slope = 0
        # "clean" set: slope-bearing cells that are neither water nor within
        # OBJECT_HALO m of a placement, so slope is the only candidate cause
        self.clean_cells = 0
        self.clean_block = 0
        self.clean_total = np.zeros(len(SLOPE_EDGES) - 1, dtype=np.int64)
        self.clean_blockbin = np.zeros(len(SLOPE_EDGES) - 1, dtype=np.int64)
        self.clean_steep = np.zeros(len(SWEEP_DEG), dtype=np.int64)
        self.clean_steep_block = np.zeros(len(SWEEP_DEG), dtype=np.int64)
        # water
        self.w_attr = 0
        self.w_wtr = 0
        self.w_both = 0
        self.w_attr_only = 0
        self.w_wtr_only = 0
        self.w_sub = 0
        self.w_sub_and_attr = 0
        self.w_sub_only = 0
        self.w_attr_not_sub = 0
        self.w_wtr_only_blocked = 0
        self.w_maps_painted = 0
        self.w_maps_with_water = 0
        # object attribution of block
        self.block_near_obj = 0
        self.block_far_obj = 0
        self.obj_maps = 0
        # block budget (first-match-wins attribution)
        self.blk_total = 0
        self.blk_rim = 0
        self.blk_water = 0
        self.blk_slope = 0
        self.blk_object = 0
        self.blk_residual = 0
        self.rim_cells = 0
        # safezone
        self.sz_components: List[int] = []
        self.sz_bbox: List[float] = []
        self.sz_fill: List[float] = []
        self.sz_shapes = Counter()
        self.sz_maps_with = 0
        # objects
        self.obj_center_block = Counter()
        self.obj_total = Counter()

    def add(self, other: "Accum") -> None:
        self.cells += other.cells
        self.sectors += other.sectors
        self.maps += other.maps
        self.flag_cells.update(other.flag_cells)
        self.byte_hist += other.byte_hist
        self.slope_total += other.slope_total
        self.slope_block += other.slope_block
        self.slope_cells += other.slope_cells
        self.sweep_steep += other.sweep_steep
        self.sweep_steep_block += other.sweep_steep_block
        self.block_cells_with_slope += other.block_cells_with_slope
        self.clean_cells += other.clean_cells
        self.clean_block += other.clean_block
        self.clean_total += other.clean_total
        self.clean_blockbin += other.clean_blockbin
        self.clean_steep += other.clean_steep
        self.clean_steep_block += other.clean_steep_block
        for k in ("w_attr", "w_wtr", "w_both", "w_attr_only", "w_wtr_only",
                  "w_sub", "w_sub_and_attr", "w_sub_only", "w_attr_not_sub",
                  "w_wtr_only_blocked", "w_maps_painted", "w_maps_with_water",
                  "block_near_obj", "block_far_obj", "obj_maps", "sz_maps_with",
                  "high_bit_cells", "maps_using_high_bits", "block_and_water",
                  "safezone_and_block", "blk_total", "blk_rim", "blk_water",
                  "blk_slope", "blk_object", "blk_residual", "rim_cells"):
            setattr(self, k, getattr(self, k) + getattr(other, k))
        self.sz_components += other.sz_components
        self.sz_bbox += other.sz_bbox
        self.sz_fill += other.sz_fill
        self.sz_shapes.update(other.sz_shapes)
        self.obj_center_block.update(other.obj_center_block)
        self.obj_total.update(other.obj_total)

    # -- reporting ---------------------------------------------------------
    def flag_report(self) -> Dict[str, dict]:
        return {name: {"cells": int(self.flag_cells[name]),
                       "pct_of_cells": _pct(self.flag_cells[name], self.cells)}
                for name in FLAG_NAMES}

    @staticmethod
    def _bins(total, block):
        out = []
        for i in range(len(SLOPE_EDGES) - 1):
            t, b = int(total[i]), int(block[i])
            out.append({"lo_deg": SLOPE_EDGES[i],
                        "hi_deg": round(SLOPE_EDGES[i + 1], 4),
                        "cells": t, "blocked": b, "p_block": _frac(b, t)})
        return out

    @staticmethod
    def _sweep(steep, steep_block, total_cells, total_block, min_deg=1):
        """Youden-J and F1 optimal cuts of ``slope >= T`` predicting BLOCK.

        J = TPR - FPR is used as the headline statistic because F1 degenerates
        to T = 0 whenever P(block) is near 1 (every dungeon interior), while J
        is invariant to the class prior.
        """
        neg = total_cells - total_block
        best_j = best_f1 = None
        for i, deg in enumerate(SWEEP_DEG):
            if deg < min_deg:
                continue
            s = int(steep[i])
            tp = int(steep_block[i])
            fp = s - tp
            tpr = tp / total_block if total_block else 0.0
            fpr = fp / neg if neg else 0.0
            prec = tp / s if s else 0.0
            f1 = (2 * prec * tpr / (prec + tpr)) if (prec + tpr) else 0.0
            row = {"deg": deg, "steep_cells": s, "tp": tp, "fp": fp,
                   "fn": total_block - tp, "tpr": round(tpr, 6),
                   "fpr": round(fpr, 6), "precision": round(prec, 6),
                   "f1": round(f1, 6), "youden_j": round(tpr - fpr, 6)}
            if best_j is None or row["youden_j"] > best_j["youden_j"]:
                best_j = row
            if best_f1 is None or row["f1"] > best_f1["f1"]:
                best_f1 = row
        return best_j, best_f1

    @staticmethod
    def _crossing(bins, p=0.5, min_cells=1000):
        for b in bins:
            if b["cells"] >= min_cells and b["p_block"] >= p:
                return b["lo_deg"]
        return None

    def slope_report(self) -> dict:
        bins = self._bins(self.slope_total, self.slope_block)
        total_block = int(self.slope_block.sum())
        total_cells = int(self.slope_total.sum())
        cbins = self._bins(self.clean_total, self.clean_blockbin)
        cb = int(self.clean_blockbin.sum())
        ct = int(self.clean_total.sum())

        out = {
            "cells_with_slope": total_cells,
            "blocked_cells": total_block,
            "block_rate": _frac(total_block, total_cells),
            "bins": bins,
            "p50_crossing_deg": self._crossing(bins),
            "flat_block_rate": _frac(int(self.slope_block[0]), int(self.slope_total[0])),
            "clean": {
                "definition": "cells with slope, no ATTRIBUTE_WATER, not wet in "
                              "water.wtr, and no areadata placement within %d m"
                              % OBJECT_HALO,
                "cells": ct, "blocked_cells": cb,
                "block_rate": _frac(cb, ct),
                "flat_block_rate": _frac(int(self.clean_blockbin[0]),
                                         int(self.clean_total[0])),
                "bins": cbins,
                "p50_crossing_deg": self._crossing(cbins),
            },
        }
        bj, bf = self._sweep(self.sweep_steep, self.sweep_steep_block,
                             total_cells, total_block)
        if bj:
            out["best_youden"] = bj
            out["best_f1"] = bf
        cj, cf = self._sweep(self.clean_steep, self.clean_steep_block, ct, cb)
        if cj:
            out["clean"]["best_youden"] = cj
            out["clean"]["best_f1"] = cf
            t = cj["deg"]
            idx = SWEEP_DEG.index(t)
            out["threshold_deg"] = t
            explained = int(self.sweep_steep_block[idx])
            out["block_explained_by_slope"] = explained
            out["block_unexplained"] = total_block - explained
            out["pct_block_unexplained"] = _pct(total_block - explained, total_block)
            out["steep_but_walkable"] = int(self.sweep_steep[idx]) - explained
            out["pct_steep_walkable"] = _pct(int(self.sweep_steep[idx]) - explained,
                                             int(self.sweep_steep[idx]))
        return out

    def budget_report(self, threshold_deg=None) -> dict:
        t = self.blk_total
        return {
            "order": ["slope", "water", "object_halo", "out_of_bounds", "residual"],
            "slope_threshold_deg": threshold_deg,
            "object_halo_m": OBJECT_HALO,
            "block_cells": t,
            "slope": self.blk_slope, "pct_slope": _pct(self.blk_slope, t),
            "water": self.blk_water, "pct_water": _pct(self.blk_water, t),
            "object_halo": self.blk_object,
            "pct_object_halo": _pct(self.blk_object, t),
            "out_of_bounds": self.blk_rim,
            "pct_out_of_bounds": _pct(self.blk_rim, t),
            "residual": self.blk_residual,
            "pct_residual": _pct(self.blk_residual, t),
            "pct_not_slope": _pct(t - self.blk_slope, t),
        }

    def water_report(self) -> dict:
        union = self.w_attr + self.w_wtr_only
        sub_union = self.w_attr + self.w_sub_only
        return {"attr_water_cells": self.w_attr, "wtr_wet_cells": self.w_wtr,
                "both": self.w_both, "attr_only": self.w_attr_only,
                "wtr_only": self.w_wtr_only,
                "jaccard": _frac(self.w_both, union) if union else None,
                "pct_attr_without_wtr": _pct(self.w_attr_only, self.w_attr),
                "pct_wtr_without_attr": _pct(self.w_wtr_only, self.w_wtr),
                "wtr_only_and_blocked": self.w_wtr_only_blocked,
                "pct_wtr_only_blocked": _pct(self.w_wtr_only_blocked,
                                             self.w_wtr_only),
                # "submerged" = wet in water.wtr AND the terrain cell's lowest
                # corner is below that layer's surface -> the water you can see
                "submerged_cells": self.w_sub,
                "submerged_and_attr": self.w_sub_and_attr,
                "submerged_only": self.w_sub_only,
                "attr_not_submerged": self.w_attr_not_sub,
                "jaccard_vs_submerged": _frac(self.w_sub_and_attr, sub_union)
                if sub_union else None,
                "precision_vs_submerged": _frac(self.w_sub_and_attr, self.w_attr),
                "recall_vs_submerged": _frac(self.w_sub_and_attr, self.w_sub),
                "maps_with_water": self.w_maps_with_water,
                "maps_painting_the_flag": self.w_maps_painted}

    def safezone_report(self) -> dict:
        return {"maps_with_safezone": self.sz_maps_with,
                "components": len(self.sz_components),
                "component_area_m2": _quantiles(self.sz_components),
                "component_bbox_edge_m": _quantiles(self.sz_bbox),
                "component_fill_ratio": _quantiles(self.sz_fill),
                "component_shapes": dict(self.sz_shapes)}

    def object_report(self) -> dict:
        out = {}
        for t, n in sorted(self.obj_total.items(), key=lambda kv: -kv[1]):
            out[t or "<unresolved>"] = {
                "placements": n,
                "center_cell_blocked": int(self.obj_center_block[t]),
                "pct_center_blocked": _pct(self.obj_center_block[t], n)}
        return out


# --------------------------------------------------------------------------
# per-map analysis
# --------------------------------------------------------------------------

def analyse_map(grids: MapGrids, objects: List[dict],
                footprints: Optional[dict] = None,
                diag: Optional[Counter] = None) -> Tuple[dict, Accum]:
    """Measure one map.  Returns ``(json_report, accumulator)``."""
    acc = Accum()
    rep: Dict[str, object] = {
        "sectors": len(grids.sectors),
        "grid_sectors": [grids.gw // ATTR_N, grids.gh // ATTR_N] if grids.gw else [0, 0],
        "rectangular": grids.is_rectangular if grids.gw else None,
        "objects": len(objects),
    }
    if grids.setting is not None:
        rep["declared_map_size"] = list(grids.setting.map_size)
    if grids.problems:
        rep["problems"] = grids.problems
    if grids.attr is None:
        rep["empty"] = True
        return rep, acc

    acc.maps = 1
    acc.sectors = len(grids.sectors)
    valid = grids.valid
    n_cells = int(valid.sum())
    acc.cells = n_cells
    acc.byte_hist = grids.byte_hist.copy()
    rep["cells"] = n_cells

    attr = grids.attr
    block = ((attr & np.uint8(attr_codec.ATTR_BLOCK)) != 0) & valid

    # -- 1. flag coverage --------------------------------------------------
    flags = {}
    for bit, name in FLAG_BITS:
        m = ((attr & np.uint8(bit)) != 0) & valid
        c = int(m.count_nonzero()) if hasattr(m, "count_nonzero") else int(np.count_nonzero(m))
        acc.flag_cells[name] = c
        flags[name] = {"cells": c, "pct_of_cells": _pct(c, n_cells)}
    rep["flags"] = flags
    hist = grids.byte_hist
    top = np.argsort(hist)[::-1][:12]
    rep["top_bytes"] = [{"byte": int(b), "hex": "0x%02X" % int(b),
                         "cells": int(hist[b]), "pct": _pct(int(hist[b]), n_cells),
                         "paint": attr_codec.PAINT_KINDS.get(int(b))}
                        for b in top if hist[b]]
    rep["distinct_bytes"] = int(np.count_nonzero(hist))
    acc.high_bit_cells = int(hist[8:].sum())
    acc.maps_using_high_bits = 1 if acc.high_bit_cells else 0
    rep["paint_bytes"] = {
        "cells_above_0x07": acc.high_bit_cells,
        "pct_above_0x07": _pct(acc.high_bit_cells, n_cells),
        "uses_paint_convention": bool(acc.high_bit_cells),
    }
    wmask_a = ((attr & np.uint8(attr_codec.ATTR_WATER)) != 0) & valid
    szmask = ((attr & np.uint8(attr_codec.ATTR_BANPK)) != 0) & valid
    acc.block_and_water = int(np.count_nonzero(block & wmask_a))
    acc.safezone_and_block = int(np.count_nonzero(block & szmask))
    rep["flag_overlap"] = {
        "block_and_water": acc.block_and_water,
        "pct_of_water_blocked": _pct(acc.block_and_water,
                                     int(np.count_nonzero(wmask_a))),
        "safezone_and_block": acc.safezone_and_block,
        "pct_of_safezone_blocked": _pct(acc.safezone_and_block,
                                        int(np.count_nonzero(szmask))),
    }

    # -- map border (needed first: the rim is excluded from the slope fit) --
    border_rep, rim, oob = _border_report(block, valid, grids)
    rep["border"] = border_rep

    # -- object halo (needed by the slope "clean" set) ---------------------
    near = np.zeros_like(valid)
    pts = None
    if objects:
        pts = np.array([[o["cx"], o["cy"]] for o in objects], dtype=np.int64)
        gh, gw = block.shape
        keep = ((pts[:, 0] >= 0) & (pts[:, 0] < gw)
                & (pts[:, 1] >= 0) & (pts[:, 1] < gh))
        for x, y in pts[keep]:
            near[max(0, y - OBJECT_HALO):y + OBJECT_HALO + 1,
                 max(0, x - OBJECT_HALO):x + OBJECT_HALO + 1] = True

    # -- 2. block vs slope -------------------------------------------------
    have_slope = valid & np.isfinite(grids.slope)
    slope = grids.slope
    sv = slope[have_slope]
    bv = block[have_slope]
    acc.slope_cells = int(sv.size)
    edges = np.asarray(SLOPE_EDGES[1:-1], dtype=np.float32)
    if sv.size:
        idx = np.digitize(sv, edges)
        acc.slope_total = np.bincount(idx, minlength=len(SLOPE_EDGES) - 1).astype(np.int64)
        acc.slope_block = np.bincount(idx[bv], minlength=len(SLOPE_EDGES) - 1).astype(np.int64)
        for i, deg in enumerate(SWEEP_DEG):
            steep = sv >= deg
            acc.sweep_steep[i] = int(np.count_nonzero(steep))
            acc.sweep_steep_block[i] = int(np.count_nonzero(steep & bv))
        acc.block_cells_with_slope = int(np.count_nonzero(bv))
        rep["slope_deg"] = {q: round(float(v), 3) for q, v in
                            zip(("p50", "p75", "p90", "p95", "p99", "max"),
                                np.quantile(sv, [.5, .75, .9, .95, .99, 1.0]))}
        rep["terrain_class"] = ("sculpted" if rep["slope_deg"]["p95"] >= 10.0
                                else "flat")
    clean = have_slope & ~near & ~rim & ~grids.water & ~(
        (attr & np.uint8(attr_codec.ATTR_WATER)) != 0)
    csv_ = slope[clean]
    cbv = block[clean]
    acc.clean_cells = int(csv_.size)
    acc.clean_block = int(np.count_nonzero(cbv))
    if csv_.size:
        cidx = np.digitize(csv_, edges)
        acc.clean_total = np.bincount(cidx, minlength=len(SLOPE_EDGES) - 1).astype(np.int64)
        acc.clean_blockbin = np.bincount(cidx[cbv],
                                         minlength=len(SLOPE_EDGES) - 1).astype(np.int64)
        for i, deg in enumerate(SWEEP_DEG):
            steep = csv_ >= deg
            acc.clean_steep[i] = int(np.count_nonzero(steep))
            acc.clean_steep_block[i] = int(np.count_nonzero(steep & cbv))
    rep["block_vs_slope"] = acc.slope_report()
    rep["block_vs_slope"]["clean"]["excludes"] = "rim band, water, object halo"

    # -- 2b. block budget --------------------------------------------------
    # Every BLOCK cell is charged to exactly one cause, first match wins:
    # slope >= T -> water -> object halo -> out-of-bounds -> residual.
    # Slope is charged first so ``pct_slope`` answers "how much BLOCK does
    # terrain steepness explain" directly, and before out-of-bounds because a
    # mountain rim IS edge-connected -- charging it to "out of bounds" would
    # hide the terrain signal.  What lands in out_of_bounds is therefore
    # *flat* paint that seals the map; residual is interior paint with no
    # cause at all.
    thr = rep["block_vs_slope"].get("threshold_deg")
    wet_any = grids.water | ((attr & np.uint8(attr_codec.ATTR_WATER)) != 0)
    steep = have_slope & (slope >= (thr if thr is not None else 90.0))
    left = block.copy()
    acc.blk_total = int(np.count_nonzero(left))
    acc.blk_slope = int(np.count_nonzero(left & steep))
    left &= ~steep
    acc.blk_water = int(np.count_nonzero(left & wet_any))
    left &= ~wet_any
    acc.blk_object = int(np.count_nonzero(left & near))
    left &= ~near
    acc.blk_rim = int(np.count_nonzero(left & oob))
    left &= ~oob
    acc.blk_residual = int(np.count_nonzero(left))
    acc.rim_cells = int(np.count_nonzero(oob))
    rep["block_budget"] = acc.budget_report(thr)

    # -- 3. block vs water -------------------------------------------------
    wattr = ((attr & np.uint8(attr_codec.ATTR_WATER)) != 0) & valid
    wwtr = grids.water & valid
    wsub = grids.submerged & valid
    acc.w_attr = int(np.count_nonzero(wattr))
    acc.w_wtr = int(np.count_nonzero(wwtr))
    acc.w_both = int(np.count_nonzero(wattr & wwtr))
    acc.w_attr_only = acc.w_attr - acc.w_both
    acc.w_wtr_only = acc.w_wtr - acc.w_both
    acc.w_sub = int(np.count_nonzero(wsub))
    acc.w_sub_and_attr = int(np.count_nonzero(wsub & wattr))
    acc.w_sub_only = acc.w_sub - acc.w_sub_and_attr
    acc.w_attr_not_sub = acc.w_attr - acc.w_sub_and_attr
    acc.w_wtr_only_blocked = int(np.count_nonzero(wwtr & ~wattr & block))
    acc.w_maps_with_water = 1 if acc.w_wtr else 0
    # "paints the flag" = the map's ATTRIBUTE_WATER covers >= 20% of what the
    # watermap says is visibly submerged
    acc.w_maps_painted = 1 if (acc.w_sub and
                               acc.w_sub_and_attr / float(acc.w_sub) >= 0.2) else 0
    rep["water"] = acc.water_report()
    rep["water"]["sectors_with_wtr"] = grids.has_water_file
    rep["water"]["paints_the_flag"] = bool(acc.w_maps_painted)

    # -- 4. safezone shape -------------------------------------------------
    sz = ((attr & np.uint8(attr_codec.ATTR_BANPK)) != 0) & valid
    sz_rep = {"cells": int(np.count_nonzero(sz))}
    if sz_rep["cells"]:
        acc.sz_maps_with = 1
        labels, n = label_components(sz, connectivity=8)
        comps = []
        for lid in range(1, n + 1):
            ys, xs = np.nonzero(labels == lid)
            area = int(ys.size)
            if area < SAFEZONE_MIN_CELLS:
                continue
            h = int(ys.max() - ys.min() + 1)
            w = int(xs.max() - xs.min() + 1)
            fill = area / float(w * h)
            # the editor's circular attr brush leaves fill = pi/4 = 0.785 in a
            # square bbox; a square/rect flood leaves fill ~ 1
            if 0.72 <= fill <= 0.85 and 0.9 <= w / float(h) <= 1.111:
                shape = "circle_brush_d%d" % ((w + h) // 2)
            elif fill >= 0.97:
                shape = "rect_fill"
            else:
                shape = "irregular"
            comps.append({"area_m2": area, "bbox_m": [w, h],
                          "fill": round(fill, 4), "shape": shape,
                          "center_m": [int(xs.mean()), int(ys.mean())]})
            acc.sz_components.append(area)
            acc.sz_bbox.append(max(w, h))
            acc.sz_fill.append(fill)
            acc.sz_shapes[shape.split("_d")[0]] += 1
        comps.sort(key=lambda c: -c["area_m2"])
        sz_rep["components"] = len(comps)
        sz_rep["shapes"] = dict(Counter(c["shape"].split("_d")[0] for c in comps))
        sz_rep["circle_diameters_m"] = sorted(
            int(c["shape"].split("_d")[1]) for c in comps
            if c["shape"].startswith("circle"))
        sz_rep["small_components_dropped"] = n - len(comps)
        sz_rep["largest"] = comps[:6]
        # how close is safezone to buildings?
        if objects:
            bpos = [(o["cx"], o["cy"]) for o in objects
                    if o["type"] in ("Building", "DungeonBlock")]
            if bpos and comps:
                arr = np.asarray(bpos, dtype=np.float64)
                d = []
                for c in comps:
                    cx, cy = c["center_m"]
                    d.append(float(np.min(np.hypot(arr[:, 0] - cx, arr[:, 1] - cy))))
                sz_rep["dist_to_nearest_building_m"] = _quantiles(d)
    rep["safezone"] = sz_rep

    # -- 5. object joins ---------------------------------------------------
    if objects:
        acc.obj_maps = 1
        _object_join(grids, block, valid, near, objects, acc, rep, footprints, diag)

    return rep, acc


def out_of_bounds_mask(block: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """BLOCK cells connected (8-way) to the outer boundary of the map.

    This is the honest definition of "out of bounds": the blocked mass the
    player cannot get past because it reaches the edge of the world.  In a
    field map it is the mountain rim; in a dungeon box it is the whole wall
    slab that the corridors are carved out of.
    """
    solid = block & valid
    if not solid.any():
        return np.zeros_like(solid)
    labels, n = label_components(solid, connectivity=8)
    if not n:
        return np.zeros_like(solid)
    inner = valid.copy()
    inner[1:, :] &= valid[:-1, :]
    inner[:-1, :] &= valid[1:, :]
    inner[:, 1:] &= valid[:, :-1]
    inner[:, :-1] &= valid[:, 1:]
    inner[0, :] = inner[-1, :] = inner[:, 0] = inner[:, -1] = False
    boundary = valid & ~inner
    seeds = np.unique(labels[boundary & (labels > 0)])
    if not seeds.size:
        return np.zeros_like(solid)
    return np.isin(labels, seeds)


def _edge_runs(block, valid, axis: str):
    """Consecutive BLOCK run length (metres) inward from one map edge."""
    if axis == "north":
        b, v = block, valid
    elif axis == "south":
        b, v = block[::-1, :], valid[::-1, :]
    elif axis == "west":
        b, v = block.T, valid.T
    else:                                            # east
        b, v = block.T[::-1, :], valid.T[::-1, :]
    cols = v[0]                                      # only lines that exist
    if not cols.any():
        return None
    bb = b[:, cols]
    depth = bb.shape[0]
    full = bb.all(axis=0)
    runs = np.where(full, depth, np.argmin(bb, axis=0))
    return runs


def _border_report(block, valid, grids) -> dict:
    """Band width (metres) of BLOCK along each map edge."""
    out = {}
    gh, gw = block.shape

    def band(get_line, n_lines):
        strict = loose = 0
        profile = []
        for i in range(n_lines):
            b, v = get_line(i)
            nv = int(np.count_nonzero(v))
            f = _frac(int(np.count_nonzero(b)), nv)
            profile.append(round(f, 4))
            if f < BORDER_LOOSE and i > 0:
                break                                   # band already ended
        for f in profile:
            if f >= BORDER_STRICT:
                strict += 1
            else:
                break
        for f in profile:
            if f >= BORDER_LOOSE:
                loose += 1
            else:
                break
        return strict, loose, profile[:16]

    edges = {
        "north": (lambda i: (block[i, :], valid[i, :]), gh),
        "south": (lambda i: (block[gh - 1 - i, :], valid[gh - 1 - i, :]), gh),
        "west": (lambda i: (block[:, i], valid[:, i]), gw),
        "east": (lambda i: (block[:, gw - 1 - i], valid[:, gw - 1 - i]), gw),
    }
    widths_strict, widths_loose = [], []
    for name, (fn, n) in edges.items():
        s, l, prof = band(fn, n)
        out[name] = {"band_m_strict": s, "band_m_loose": l, "profile": prof}
        widths_strict.append(s)
        widths_loose.append(l)
    out["min_band_m_strict"] = int(min(widths_strict))
    out["min_band_m_loose"] = int(min(widths_loose))
    out["max_band_m_loose"] = int(max(widths_loose))
    out["sealed_strict"] = bool(min(widths_strict) > 0)
    out["sealed_loose"] = bool(min(widths_loose) > 0)
    # a band deeper than a quarter of the map is not a rim, it is a map that
    # is mostly blocked (dungeon box); flag it
    out["band_is_runaway"] = bool(max(widths_loose) >= max(1, min(gh, gw) // 4))

    # per-edge seal depth: how many metres of BLOCK a player meets walking in
    # from each edge cell (the row-mean band above hides holes; this does not)
    seal = {}
    all_runs = []
    for axis in ("north", "east", "south", "west"):
        runs = _edge_runs(block, valid, axis)
        if runs is None:
            continue
        all_runs.append(runs)
        seal[axis] = {"edge_cells": int(runs.size),
                      "pct_edge_blocked": _pct(int(np.count_nonzero(runs)), runs.size),
                      "run_m": _quantiles(runs)}
    out["seal"] = seal
    if all_runs:
        cat = np.concatenate(all_runs)
        out["seal_all_edges"] = {
            "edge_cells": int(cat.size),
            "pct_edge_blocked": _pct(int(np.count_nonzero(cat)), cat.size),
            "holes_m": int(np.count_nonzero(cat == 0)),
            "run_m": _quantiles(cat)}

    oob = out_of_bounds_mask(block, valid)
    out["out_of_bounds_cells"] = int(np.count_nonzero(oob))
    out["pct_map_out_of_bounds"] = _pct(int(np.count_nonzero(oob)),
                                        int(np.count_nonzero(valid)))

    # geometric edge strip, used only to keep the out-of-bounds paint out of
    # the slope regression; clamped so a mostly-blocked map cannot swallow
    # itself
    cap_y, cap_x = max(1, gh // 4), max(1, gw // 4)
    strip = np.zeros_like(valid)
    n_ = min(out["north"]["band_m_loose"], cap_y)
    s_ = min(out["south"]["band_m_loose"], cap_y)
    w_ = min(out["west"]["band_m_loose"], cap_x)
    e_ = min(out["east"]["band_m_loose"], cap_x)
    if n_:
        strip[:n_, :] = True
    if s_:
        strip[gh - s_:, :] = True
    if w_:
        strip[:, :w_] = True
    if e_:
        strip[:, gw - e_:] = True
    strip &= valid
    out["regression_strip_m"] = [n_, e_, s_, w_]
    # is the rim also terrain-steep?  (does height do the sealing, or paint?)
    if grids.slope is not None:
        ok = valid & np.isfinite(grids.slope)
        rim_s = strip & ok
        inner = ok & ~strip
        if rim_s.any() and inner.any():
            out["rim_slope_deg_median"] = round(float(np.median(grids.slope[rim_s])), 3)
            out["interior_slope_deg_median"] = round(float(np.median(grids.slope[inner])), 3)
            steep = grids.slope >= 25.0
            out["pct_rim_block_that_is_steep"] = _pct(
                int(np.count_nonzero(rim_s & block & steep)),
                int(np.count_nonzero(rim_s & block)))
    return out, strip, oob


def _object_join(grids, block, valid, near, objects, acc, rep, footprints, diag) -> None:
    """Block-vs-object attribution + per-CRC footprint radius estimation."""
    gh, gw = block.shape
    pts = np.array([[o["cx"], o["cy"]] for o in objects], dtype=np.int64)
    inside = (pts[:, 0] >= 0) & (pts[:, 0] < gw) & (pts[:, 1] >= 0) & (pts[:, 1] < gh)
    rep["objects_inside_grid"] = int(inside.sum())

    # centre-cell block rate per property type
    for o, ok in zip(objects, inside.tolist()):
        acc.obj_total[o["type"]] += 1
        if ok and block[o["cy"], o["cx"]]:
            acc.obj_center_block[o["type"]] += 1
    rep["object_center_block"] = acc.object_report()

    # Does this map paint building footprints into attr at all, or does it
    # leave building collision to the model's own ``.mdatr``?  The map-wide
    # block rate is a poor control (dungeon interiors are ~90% block), so use
    # a *local* control: the same placement shifted CONTROL_OFFSET m in each
    # of the four cardinal directions.
    base = _frac(int(np.count_nonzero(block)), int(np.count_nonzero(valid)))
    nb = hb = cn = ch = 0
    D = CONTROL_OFFSET
    for i, o in enumerate(objects):
        if o["type"] not in ("Building", "DungeonBlock") or not inside[i]:
            continue
        x, y = int(pts[i][0]), int(pts[i][1])
        nb += 1
        hb += bool(block[y, x])
        for dx, dy in ((D, 0), (-D, 0), (0, D), (0, -D)):
            cx, cy = x + dx, y + dy
            if 0 <= cx < gw and 0 <= cy < gh and valid[cy, cx]:
                cn += 1
                ch += bool(block[cy, cx])
    rate = _frac(hb, nb)
    ctrl = _frac(ch, cn)
    lift = round(rate / ctrl, 3) if ctrl else None
    policy = "no_buildings"
    if nb >= 10 and lift is not None:
        if rate >= 0.6 and lift >= 1.3:
            policy = "painted"
        elif lift <= 1.05:
            policy = "model_only"
        else:
            policy = "mixed"
    rep["footprint_policy"] = {
        "policy": policy, "buildings": nb, "on_block": hb,
        "center_block_rate": rate,
        "control_offset_m": D, "control_block_rate": ctrl,
        "local_lift": lift, "map_block_rate": base,
    }

    acc.block_near_obj = int(np.count_nonzero(block & near))
    acc.block_far_obj = int(np.count_nonzero(block & ~near))
    slope_ok = np.isfinite(grids.slope)
    thr = rep["block_vs_slope"].get("threshold_deg")
    unexp = block & slope_ok & (grids.slope < (thr if thr is not None else 0))
    rep["block_attribution"] = {
        "halo_m": OBJECT_HALO,
        "block_near_object": acc.block_near_obj,
        "block_far_from_object": acc.block_far_obj,
        "pct_block_near_object": _pct(acc.block_near_obj,
                                      acc.block_near_obj + acc.block_far_obj),
        "slope_threshold_deg": thr,
        "unexplained_block": int(np.count_nonzero(unexp)),
        "unexplained_block_near_object": int(np.count_nonzero(unexp & near)),
        "pct_unexplained_near_object": _pct(int(np.count_nonzero(unexp & near)),
                                            int(np.count_nonzero(unexp))),
    }

    if footprints is None:
        return

    # -- footprint radius per placement ------------------------------------
    W = FOOTPRINT_WINDOW
    B = FOOTPRINT_ISOLATION
    # isolation is judged against *solid* placements only -- effects and
    # ambience emitters sit inside buildings and would veto everything
    solid = [i for i, o in enumerate(objects)
             if o["type"] in FOOTPRINT_SOLID_TYPES and inside[i]]
    buckets: Dict[Tuple[int, int], List[int]] = {}
    for i in solid:
        x, y = pts[i]
        buckets.setdefault((int(x) // B, int(y) // B), []).append(i)

    def isolated(i, x, y):
        bx, by = x // B, y // B
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in buckets.get((bx + dx, by + dy), ()):
                    if j == i:
                        continue
                    ox, oy = pts[j]
                    if max(abs(int(ox) - x), abs(int(oy) - y)) <= B:
                        return False
        return True

    if diag is None:
        diag = Counter()
    ring_idx = _ring_index(W)
    for i, o in enumerate(objects):
        diag["placements"] += 1
        if not inside[i]:
            diag["reject_outside_grid"] += 1
            continue
        x, y = int(pts[i][0]), int(pts[i][1])
        if x - W < 0 or y - W < 0 or x + W + 1 > gw or y + W + 1 > gh:
            diag["reject_window_off_map"] += 1
            continue
        win = block[y - W:y + W + 1, x - W:x + W + 1]
        if not valid[y - W:y + W + 1, x - W:x + W + 1].all():
            diag["reject_window_has_missing_sector"] += 1
            continue
        centre = bool(win[W, W])
        radius = 0
        area = 0
        bbox = None
        saturated = False
        if centre:
            for r in range(1, W + 1):
                if float(win[ring_idx[r]].mean()) < FOOTPRINT_FILL:
                    break
                radius = r
            comp = component_at(win, W, W, connectivity=4)
            area = int(comp.sum())
            ys, xs = np.nonzero(comp)
            bbox = (int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1))
            saturated = bool(comp[0, :].any() or comp[-1, :].any()
                             or comp[:, 0].any() or comp[:, -1].any())
        rec = footprints.setdefault(o["crc"], {
            "crc": o["crc"], "type": o["type"], "model": o["model"],
            "name": o["name"], "n": 0, "n_center_block": 0, "n_isolated": 0,
            "n_saturated": 0, "n_measured": 0,
            "_r_all": [], "_r_iso": [], "_a_iso": [], "_bx": [], "_by": [],
            "maps": set()})
        rec["n"] += 1
        rec["maps"].add(grids.name)
        if centre:
            rec["n_center_block"] += 1
            rec["_r_all"].append(radius)
        if saturated:
            rec["n_saturated"] += 1
        iso = isolated(i, x, y)
        if iso:
            rec["n_isolated"] += 1
        if not centre:
            diag["reject_centre_not_blocked"] += 1
        elif saturated:
            diag["reject_component_saturates_window"] += 1
        elif not iso:
            diag["reject_not_isolated"] += 1
        else:
            diag["measured"] += 1
        if iso and centre and not saturated:
            rec["n_measured"] += 1
            rec["_r_iso"].append(radius)
            rec["_a_iso"].append(area)
            rec["_bx"].append(min(bbox))
            rec["_by"].append(max(bbox))


_RING_CACHE: Dict[int, List[np.ndarray]] = {}


def _ring_index(W: int) -> List[np.ndarray]:
    """Boolean masks of the Chebyshev rings r = 0..W in a (2W+1)^2 window."""
    if W in _RING_CACHE:
        return _RING_CACHE[W]
    yy, xx = np.mgrid[-W:W + 1, -W:W + 1]
    cheb = np.maximum(np.abs(yy), np.abs(xx))
    rings = [cheb == r for r in range(W + 1)]
    _RING_CACHE[W] = rings
    return rings


# --------------------------------------------------------------------------
# server_attr cross-check
# --------------------------------------------------------------------------

def check_server_attr(map_dir: str) -> Optional[dict]:
    """Verify the documented ``attr.atr`` -> ``server_attr`` 2x2 upsample.

    Only meaningful for maps that actually ship ``server_attr``; returns
    ``None`` otherwise.  Reads each server block back through the codec and
    compares it cell-for-cell with the client grid the spec says it came from
    (``server-attr.md`` "Generation recipe").
    """
    from m2map.codec import server_attr as sa_codec

    path = os.path.join(map_dir, "server_attr")
    if not os.path.exists(path):
        return None
    sa = sa_codec.read_server_attr(path)
    grids = MapGrids.load(map_dir)
    cw, ch = sa.sectree_size
    total = mismatch = 0
    for sy, sx, _p in [(s[1], s[0], s[2]) for s in grids.sectors]:
        if sx >= cw or sy >= ch:
            continue
        rebuilt = sa.to_attr_grid(sx, sy)
        want = grids.attr[sy * ATTR_N:(sy + 1) * ATTR_N, sx * ATTR_N:(sx + 1) * ATTR_N]
        total += want.size
        mismatch += int(np.count_nonzero(rebuilt != want))
    return {"header": [sa.width, sa.height], "sectrees": [cw, ch],
            "cells_compared": total, "mismatched_cells": mismatch,
            "pct_mismatch": _pct(mismatch, total)}


def selftest_server_attr(map_dir: str) -> dict:
    """Synthetic check of the 2x2 relationship when no ``server_attr`` ships.

    Builds one from the map's own ``attr.atr`` files with
    ``server_attr.from_attr_maps`` and asserts the documented inverse
    (``to_attr_grid``) reproduces the client bytes exactly.
    """
    from m2map.codec import server_attr as sa_codec

    grids = MapGrids.load(map_dir)
    mw = grids.gw // ATTR_N
    mh = grids.gh // ATTR_N
    have = {(sx, sy): grids.attr[sy * ATTR_N:(sy + 1) * ATTR_N,
                                 sx * ATTR_N:(sx + 1) * ATTR_N]
            for sx, sy, _ in grids.sectors}
    sa = sa_codec.from_attr_maps(have, mw, mh)
    blob = sa.to_bytes()
    back = sa_codec.ServerAttr.from_bytes(blob)
    total = mismatch = 0
    for (sx, sy), want in have.items():
        got = back.to_attr_grid(sx, sy)
        total += want.size
        mismatch += int(np.count_nonzero(got != want))
    return {"map": grids.name, "sectrees": [mw, mh],
            "header": [back.width, back.height],
            "bytes": len(blob), "cells_compared": total,
            "mismatched_cells": mismatch,
            "roundtrip_lossless": mismatch == 0}


# --------------------------------------------------------------------------
# cross-check against the GR2/mdatr model pass
# --------------------------------------------------------------------------

def crosscheck_models(fp_rows: List[dict], models_path: str,
                      min_measured: int = 3) -> dict:
    """Compare the attr-derived footprint against ``catalog/models.json``.

    ``models.json`` carries, per CRC, the GR2 bounding box (``size_xyz``, cm)
    and, where a ``.mdatr`` exists, ``mdatr.collision_size_xyz``.  The attr
    estimate is a 1 m-quantised paint footprint, so the interesting quantity is
    the *ratio* attr / model on each axis: > 1 means the artist painted wider
    than the mesh.
    """
    with open(models_path, "r", encoding="utf-8") as fh:
        models = json.load(fh).get("models", {})
    rows = []
    for r in fp_rows:
        if r["n_measured"] < min_measured or not r.get("footprint_bbox_m_est"):
            continue
        mrec = models.get(str(r["crc"]))
        if not mrec or not mrec.get("size_xyz"):
            continue
        gx, gy = sorted(float(v) / 100.0 for v in mrec["size_xyz"][:2])
        ax, ay = r["footprint_bbox_m_est"]
        row = {"crc": r["crc"], "type": r["type"], "model": r["model"],
               "n_placements": r["n"], "n_measured": r["n_measured"],
               "attr_bbox_m": [ax, ay],
               "gr2_bbox_m": [round(gx, 2), round(gy, 2)],
               "gr2_footprint_r_m": round(float(mrec.get("footprint_r", 0)) / 100.0, 3),
               "attr_equiv_r_m": r.get("equiv_radius_m_est"),
               "ratio_short": round(ax / gx, 3) if gx else None,
               "ratio_long": round(ay / gy, 3) if gy else None}
        md = mrec.get("mdatr") or {}
        if md.get("collision_size_xyz"):
            cx, cy = sorted(float(v) / 100.0 for v in md["collision_size_xyz"][:2])
            row["mdatr_bbox_m"] = [round(cx, 2), round(cy, 2)]
            row["ratio_short_vs_mdatr"] = round(ax / cx, 3) if cx else None
        rows.append(row)
    out = {"models_json": models_path, "min_measured": min_measured,
           "crcs_compared": len(rows), "rows": rows}
    for key in ("ratio_short", "ratio_long", "ratio_short_vs_mdatr"):
        vals = [r[key] for r in rows if r.get(key)]
        if vals:
            out[key] = _quantiles(vals)
    by_type: Dict[str, List[float]] = {}
    for r in rows:
        if r.get("ratio_short"):
            by_type.setdefault(r["type"], []).append(r["ratio_short"])
    out["ratio_short_by_type"] = {k: _quantiles(v) for k, v in by_type.items()}
    return out


# --------------------------------------------------------------------------
# corpus driver
# --------------------------------------------------------------------------

def run(corpus: str, taxonomy_path: Optional[str] = None,
        property_root: Optional[str] = None, crc_cache: Optional[str] = None,
        limit: Optional[int] = None, verbose: bool = True,
        models_path: Optional[str] = None) -> dict:
    t0 = time.time()
    crc_index = load_crc_index(property_root, crc_cache)
    archetype_of: Dict[str, str] = {}
    if taxonomy_path and os.path.exists(taxonomy_path):
        with open(taxonomy_path, "r", encoding="utf-8") as fh:
            tx = json.load(fh)
        for name, entry in tx.get("maps", {}).items():
            archetype_of[name] = entry.get("archetype") or "unclassified"

    names = sorted(d for d in os.listdir(corpus)
                   if os.path.isdir(os.path.join(corpus, d)))
    if limit:
        names = names[:limit]

    maps: Dict[str, dict] = {}
    per_arch: Dict[str, Accum] = {}
    per_style: Dict[str, Accum] = {}
    total = Accum()
    footprints: Dict[int, dict] = {}
    fp_diag: Counter = Counter()
    server_attr_found: List[dict] = []

    for i, name in enumerate(names):
        map_dir = os.path.join(corpus, name)
        grids = MapGrids.load(map_dir)
        objects = load_objects(map_dir, crc_index)
        rep, acc = analyse_map(grids, objects, footprints, fp_diag)
        arch = archetype_of.get(name, "unclassified")
        rep["archetype"] = arch
        sa = check_server_attr(map_dir)
        if sa:
            rep["server_attr"] = sa
            server_attr_found.append({"map": name, **sa})
        # attr style: does the map paint BLOCK on flat, open, object-free
        # ground?  That separates sculpted outdoor terrain (where slope drives
        # collision) from the hand-boxed interiors.
        flat_rate = rep.get("block_vs_slope", {}).get("clean", {}).get(
            "flat_block_rate")
        style = "unknown"
        if flat_rate is not None:
            style = "slope_driven" if flat_rate < 0.25 else "painted_box"
        rep["attr_style"] = style
        maps[name] = rep
        if acc.cells:
            per_arch.setdefault(arch, Accum()).add(acc)
            per_style.setdefault(style, Accum()).add(acc)
            total.add(acc)
        if verbose:
            sys.stderr.write("[%3d/%3d] %-42s %6d cells  %5d obj\n"
                             % (i + 1, len(names), name, acc.cells, len(objects)))

    # -- server_attr: verify the documented 2x2 upsample --------------------
    roundtrips = []
    if not server_attr_found:
        picks = [n for n in names
                 if maps.get(n, {}).get("sectors") and not maps[n].get("empty")]
        for n in picks[:2] + picks[-1:]:
            try:
                roundtrips.append(selftest_server_attr(os.path.join(corpus, n)))
            except Exception as exc:                     # noqa: BLE001
                roundtrips.append({"map": n, "error": str(exc)})

    # -- per-CRC footprint table ------------------------------------------
    fp_rows = []
    for crc, rec in footprints.items():
        r_iso = rec.pop("_r_iso")
        r_all = rec.pop("_r_all")
        a_iso = rec.pop("_a_iso")
        bx = rec.pop("_bx")
        by = rec.pop("_by")
        rec["maps"] = sorted(rec["maps"])
        rec["n_maps"] = len(rec["maps"])
        rec["pct_center_blocked"] = _pct(rec["n_center_block"], rec["n"])
        rec["inradius_m_all"] = _quantiles(r_all) if r_all else {}
        rec["inradius_m_isolated"] = _quantiles(r_iso) if r_iso else {}
        rec["footprint_area_m2_isolated"] = _quantiles(a_iso) if a_iso else {}
        rec["footprint_bbox_short_m"] = _quantiles(bx) if bx else {}
        rec["footprint_bbox_long_m"] = _quantiles(by) if by else {}
        if r_iso:
            rec["footprint_edge_m_est"] = round(2 * float(np.median(r_iso)) + 1, 2)
        if bx:
            rec["footprint_bbox_m_est"] = [float(np.median(bx)), float(np.median(by))]
        if a_iso:
            rec["equiv_radius_m_est"] = round(
                float(np.sqrt(np.median(a_iso) / np.pi)), 3)
        rec["maps"] = rec["maps"][:8]
        fp_rows.append(rec)
    fp_rows.sort(key=lambda r: (-r["n_measured"], -r["n"]))

    out = {
        "schema_version": 1,
        "generated_from": {
            "corpus": corpus,
            "maps_scanned": len(names),
            "taxonomy": taxonomy_path,
            "property_root": property_root,
            "crc_index_size": len(crc_index),
            "elapsed_s": round(time.time() - t0, 1),
        },
        "method": {
            "attr_cell_cm": ATTR_CM,
            "slope": "height.slope_degrees on the 129x129 vertex grid, "
                     "HeightScale from setting.txt (0.5), cell 200 cm; each "
                     "terrain cell's slope shared by its 2x2 attr cells",
            "slope_threshold": "argmax F1 of (slope >= T) as a predictor of "
                               "ATTRIBUTE_BLOCK, T swept 0..80 deg",
            "footprint": "Chebyshev ring fill on the BLOCK mask around each "
                         "areadata placement; radius = last r with ring fill "
                         ">= %.2f; window %d m; 'isolated' = no other "
                         "placement within %d m Chebyshev"
                         % (FOOTPRINT_FILL, FOOTPRINT_WINDOW, FOOTPRINT_ISOLATION),
            "border": "band = consecutive edge rows/cols whose BLOCK fraction "
                      "over valid cells is >= %.2f (strict) / %.2f (loose)"
                      % (BORDER_STRICT, BORDER_LOOSE),
        },
        "corpus": {
            "maps": total.maps, "sectors": total.sectors, "cells": total.cells,
            "objects_resolved": sum(total.obj_total.values()),
        },
        "global": _report(total),
        "archetypes": {k: _report(v) for k, v in sorted(per_arch.items())},
        "attr_styles": {k: _report(v) for k, v in sorted(per_style.items())},
        "maps": maps,
        "crc_footprints": fp_rows,
        "footprint_diagnostics": dict(fp_diag),
        "gr2_crosscheck": (crosscheck_models(fp_rows, models_path)
                           if models_path and os.path.exists(models_path)
                           else None),
        "server_attr": {
            "maps_shipping_server_attr": len(server_attr_found),
            "found": server_attr_found,
            "note": ("`server_attr` is a server-side file; if the corpus is a "
                     "client map pack none will be present, so the documented "
                     "2x2 upsample is verified synthetically instead: build a "
                     "server_attr from the map's own attr.atr files, re-read "
                     "it and compare cell for cell."),
            "synthetic_roundtrip": roundtrips,
        },
    }
    return out


def _report(acc: Accum) -> dict:
    hist = acc.byte_hist
    order = np.argsort(hist)[::-1]
    return {
        "maps": acc.maps, "sectors": acc.sectors, "cells": acc.cells,
        "flags": acc.flag_report(),
        "byte_histogram_top": [
            {"byte": int(b), "hex": "0x%02X" % int(b), "cells": int(hist[b]),
             "pct": _pct(int(hist[b]), acc.cells),
             "paint": attr_codec.PAINT_KINDS.get(int(b)),
             "flags": [n for bit, n in FLAG_BITS if int(b) & bit]}
            for b in order[:24] if hist[b]],
        "distinct_bytes": int(np.count_nonzero(hist)),
        "paint_bytes": {
            "cells_above_0x07": acc.high_bit_cells,
            "pct_above_0x07": _pct(acc.high_bit_cells, acc.cells),
            "maps_using_paint_convention": acc.maps_using_high_bits,
        },
        "flag_overlap": {
            "block_and_water": acc.block_and_water,
            "pct_of_water_blocked": _pct(acc.block_and_water,
                                         acc.flag_cells.get("water", 0)),
            "safezone_and_block": acc.safezone_and_block,
            "pct_of_safezone_blocked": _pct(acc.safezone_and_block,
                                            acc.flag_cells.get("safezone", 0)),
        },
        "block_vs_slope": acc.slope_report(),
        "block_budget": acc.budget_report("per-map fitted"),
        "rim_cells": acc.rim_cells,
        "block_attribution": {
            "block_near_object": acc.block_near_obj,
            "block_far_from_object": acc.block_far_obj,
            "pct_block_near_object": _pct(
                acc.block_near_obj, acc.block_near_obj + acc.block_far_obj),
        },
        "water": acc.water_report(),
        "safezone": acc.safezone_report(),
        "objects": acc.object_report(),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corpus", default="<CORPUS>")
    ap.add_argument("--taxonomy", default=None)
    ap.add_argument("--property-root", default=None)
    ap.add_argument("--crc-cache", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--models", default=None,
                    help="catalog/models.json from the GR2 pass, to "
                         "cross-check the attr-derived footprints")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--selftest-server-attr", default=None,
                    metavar="MAPDIR", help="round-trip one map's attr.atr "
                                           "through server_attr and exit")
    ap.add_argument("--out", required=False)
    args = ap.parse_args(argv)

    if args.selftest_server_attr:
        print(json.dumps(selftest_server_attr(args.selftest_server_attr), indent=2))
        return 0

    data = run(args.corpus, args.taxonomy, args.property_root, args.crc_cache,
               args.limit, verbose=not args.quiet, models_path=args.models)
    text = json.dumps(data, indent=1, sort_keys=False)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        sys.stderr.write("wrote %s (%.1f KB)\n" % (args.out, len(text) / 1024.0))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

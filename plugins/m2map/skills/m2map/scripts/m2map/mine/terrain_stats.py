"""Terrain (``height.raw``) statistics miner.

Walks a map corpus, decodes every ``<map>/<XXXYYY>/height.raw`` with
:mod:`m2map.codec.height`, and emits per-map + per-archetype terrain
statistics plus a library of signature 64x64-cell height patches.

Ground truth
------------
* ``reference/mapformat/height-raw.md`` -- 131x131 ``uint16`` LE, headerless,
  34,322 bytes; logical vertex ``(sx, sy)`` (``sx, sy in [-1, 129]``) lives at
  ``raw[(sy+1)*131 + (sx+1)]``; ``worldZ = raw * HeightScale``.
* ``reference/mapformat/README.md`` -- sectree folder name is
  ``printf("%06u", x*1000 + y)``; 1 sectree = 128x128 cells; 1 cell =
  ``CELL_SCALE`` = 200 world units (cm); sector edge = 25,600 cm.
* ``reference/mapformat/water-wtr.md`` -- 128x128 cell water layer indices,
  ``0xFF`` = dry.

Every map in the corpus that ships terrain declares ``CellScale 200`` and
``HeightScale 0.5`` (139/139 maps that have a setting.txt), so those are the
defaults; they are still read per map when a taxonomy is supplied.

Units
-----
All world distances are centimetres.  Slope is in degrees.  Raw values are the
stored ``uint16``; ``cm = raw * 0.5``.

Mosaic convention
-----------------
A map's sectors are stitched into a single vertex mosaic so that seams,
low-frequency form and patch extraction see continuous terrain::

    mosaic[(sy - y0)*128 + vy, (sx - x0)*128 + vx] = sector(sx, sy).vertices[vy, vx]

Shared edge vertices (``vy`` or ``vx`` == 128) are written by both neighbours;
the *mismatch* between the two writers is measured first (see
:func:`seam_stats`) and the later write wins.  Missing sectors stay NaN/invalid.

Sampling
--------
Nothing is subsampled: every ``height.raw`` in the corpus is read in full.
Counts (``n_*`` fields) sit next to every statistic.

CLI
---
    python -m m2map.mine.terrain_stats --maps <CORPUS> \
        --taxonomy .../catalog/map-taxonomy.json \
        --out .../catalog/stats-terrain.json \
        --patch-dir .../catalog/patches
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG_PARENT = os.path.dirname(os.path.dirname(_HERE))
if _PKG_PARENT not in sys.path:
    sys.path.insert(0, _PKG_PARENT)

from m2map.codec import attr as attr_codec               # noqa: E402
from m2map.codec import height as height_codec           # noqa: E402
from m2map.codec import water as water_codec             # noqa: E402

__all__ = [
    "CELL_SCALE", "HEIGHT_SCALE", "SECTOR_CELLS", "PATCH_CELLS",
    "Hist", "slope_grid", "load_map_heights", "build_mosaic",
    "seam_stats", "map_terrain_stats", "aggregate", "run",
]

CELL_SCALE = height_codec.CELL_SCALE               # 200 cm per cell
HEIGHT_SCALE = height_codec.DEFAULT_HEIGHT_SCALE   # 0.5 cm per raw unit
SECTOR_CELLS = height_codec.CELL_COUNT             # 128
VERTEX_SIZE = height_codec.VERTEX_SIZE             # 129
RAW_SIZE = height_codec.RAW_SIZE                   # 131
PATCH_CELLS = 64
PATCH_VERTS = PATCH_CELLS + 1                      # 65
PATCH_STRIDE = 32                                  # vertices between candidates

SLOPE_BIN = 0.05          # degrees per histogram bin
SLOPE_BINS = 1801         # 0 .. 90
ROUGH_BIN = 1.0           # cm per histogram bin
ROUGH_BINS = 30001
FLAT_THRESHOLDS = (2.0, 5.0, 10.0, 20.0)
LAP_SCALES = (1, 2, 4)    # stencil radius in vertices (200, 400, 800 cm)
STD_SCALES = (3, 9, 17)   # window edge in vertices
# slope bands used for the attr.atr walkability cross-check
BLOCK_BANDS = (0, 2, 5, 10, 15, 20, 25, 30, 35, 45, 60, 90)

_SECTOR_RE = re.compile(r"^\d{6}$")


# --------------------------------------------------------------------------
# histogram helper (exact aggregation across maps without keeping all samples)
# --------------------------------------------------------------------------
class Hist:
    """Fixed-width histogram supporting exact-count percentile queries.

    ``lo`` is the left edge of bin 0, ``width`` the bin width.  Values below
    ``lo`` clamp into bin 0, values at/above the top clamp into the last bin
    (an overflow bucket -- ``overflow`` counts them).  ``total``, ``sum``,
    ``sumsq``, ``vmin`` and ``vmax`` are exact.
    """

    __slots__ = ("counts", "lo", "width", "total", "sum", "sumsq",
                 "vmin", "vmax", "overflow")

    def __init__(self, nbins, lo=0.0, width=1.0):
        self.counts = np.zeros(int(nbins), dtype=np.int64)
        self.lo = float(lo)
        self.width = float(width)
        self.total = 0
        self.sum = 0.0
        self.sumsq = 0.0
        self.vmin = None
        self.vmax = None
        self.overflow = 0

    def add(self, values):
        v = np.asarray(values, dtype=np.float64).ravel()
        if v.size == 0:
            return
        idx = np.floor((v - self.lo) / self.width).astype(np.int64)
        n = self.counts.size
        self.overflow += int(np.count_nonzero(idx >= n))
        np.clip(idx, 0, n - 1, out=idx)
        self.counts += np.bincount(idx, minlength=n).astype(np.int64)
        self.total += int(v.size)
        self.sum += float(v.sum())
        self.sumsq += float(np.dot(v, v))
        lo, hi = float(v.min()), float(v.max())
        self.vmin = lo if self.vmin is None else min(self.vmin, lo)
        self.vmax = hi if self.vmax is None else max(self.vmax, hi)

    def merge(self, other):
        self.counts += other.counts
        self.total += other.total
        self.sum += other.sum
        self.sumsq += other.sumsq
        self.overflow += other.overflow
        if other.vmin is not None:
            self.vmin = other.vmin if self.vmin is None else min(self.vmin, other.vmin)
            self.vmax = other.vmax if self.vmax is None else max(self.vmax, other.vmax)
        return self

    @property
    def mean(self):
        return self.sum / self.total if self.total else None

    @property
    def std(self):
        if not self.total:
            return None
        m = self.mean
        return float(np.sqrt(max(self.sumsq / self.total - m * m, 0.0)))

    def pct(self, q, center=True):
        """Value at quantile ``q`` (0..1).  Bin-centre estimate by default."""
        if not self.total:
            return None
        cum = np.cumsum(self.counts)
        idx = int(np.searchsorted(cum, q * self.total, side="left"))
        idx = min(idx, self.counts.size - 1)
        return self.lo + (idx + (0.5 if center else 0.0)) * self.width

    def frac_below(self, value):
        """Exact fraction of samples in bins strictly left of ``value``."""
        if not self.total:
            return None
        idx = int(np.floor((value - self.lo) / self.width))
        idx = max(0, min(idx, self.counts.size))
        return float(self.counts[:idx].sum()) / self.total

    def summary(self, quantiles=(0.5, 0.9, 0.99), nd=3):
        out = {"n": self.total, "mean": _r(self.mean, nd), "std": _r(self.std, nd),
               "min": _r(self.vmin, nd), "max": _r(self.vmax, nd)}
        for q in quantiles:
            out["p%g" % (q * 100)] = _r(self.pct(q), nd)
        if self.overflow:
            out["overflow_n"] = self.overflow
        return out


def _r(v, nd=3):
    if v is None:
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    f = float(v)
    if not np.isfinite(f):
        return None
    return round(f, nd)


def _pcts(arr, quantiles=(0, 5, 25, 50, 75, 90, 95, 99, 100), nd=2):
    a = np.asarray(arr, dtype=np.float64).ravel()
    a = a[np.isfinite(a)]
    if a.size == 0:
        return {"n": 0}
    qs = np.percentile(a, quantiles)
    out = {"n": int(a.size), "mean": _r(a.mean(), nd), "std": _r(a.std(), nd)}
    for q, v in zip(quantiles, qs):
        out["p%g" % q] = _r(v, nd)
    return out


# --------------------------------------------------------------------------
# geometry primitives
# --------------------------------------------------------------------------
def slope_grid(vertices, height_scale=HEIGHT_SCALE, cell_scale=CELL_SCALE):
    """Per-cell slope in degrees for any (H+1)x(W+1) vertex grid -> HxW.

    Identical formula to :func:`m2map.codec.height.slope_degrees` (mean of the
    two X edges / two Y edges of the cell, ``atan(hypot(gx, gy))``), minus its
    129x129 shape assertion so it can run on mosaics and patches.
    :func:`_selftest` asserts the two agree on a 129x129 grid.
    """
    v = np.asarray(vertices, dtype=np.float64) * float(height_scale)
    gx = ((v[:-1, 1:] - v[:-1, :-1]) + (v[1:, 1:] - v[1:, :-1])) * 0.5 / cell_scale
    gy = ((v[1:, :-1] - v[:-1, :-1]) + (v[1:, 1:] - v[:-1, 1:])) * 0.5 / cell_scale
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def _integral(a):
    out = np.zeros((a.shape[0] + 1, a.shape[1] + 1), dtype=np.float64)
    np.cumsum(np.cumsum(a, axis=0), axis=1, out=out[1:, 1:])
    return out


def _box_sums(a, k):
    ii = _integral(a)
    return ii[k:, k:] - ii[:-k, k:] - ii[k:, :-k] + ii[:-k, :-k]


def box_std(z, valid, k):
    """Local std (cm) over every fully-valid kxk vertex window."""
    if z.shape[0] < k or z.shape[1] < k:
        return np.empty(0)
    zf = np.where(valid, z, 0.0)
    s = _box_sums(zf, k)
    s2 = _box_sums(zf * zf, k)
    c = _box_sums(valid.astype(np.float64), k)
    full = c >= k * k - 0.5
    if not full.any():
        return np.empty(0)
    n = float(k * k)
    m = s[full] / n
    var = s2[full] / n - m * m
    return np.sqrt(np.maximum(var, 0.0))


def abs_laplacian(z, valid, s):
    """|4h - h(+-s in x) - h(+-s in y)| in cm, over fully-valid stencils."""
    if z.shape[0] <= 2 * s or z.shape[1] <= 2 * s:
        return np.empty(0)
    c = z[s:-s, s:-s]
    lap = (4.0 * c - z[s:-s, :-2 * s] - z[s:-s, 2 * s:]
           - z[:-2 * s, s:-s] - z[2 * s:, s:-s])
    ok = (valid[s:-s, s:-s] & valid[s:-s, :-2 * s] & valid[s:-s, 2 * s:]
          & valid[:-2 * s, s:-s] & valid[2 * s:, s:-s])
    return np.abs(lap[ok])


def _norm_coords(h, w):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    xn = (xx / (w - 1)) * 2.0 - 1.0 if w > 1 else xx
    yn = (yy / (h - 1)) * 2.0 - 1.0 if h > 1 else yy
    return xn, yn


def fit_plane(z, valid):
    """Least-squares plane on normalised [-1,1] coords."""
    h, w = z.shape
    xn, yn = _norm_coords(h, w)
    m = valid
    n = int(m.sum())
    if n < 8:
        return None
    a = np.column_stack([np.ones(n), xn[m], yn[m]])
    coef, *_ = np.linalg.lstsq(a, z[m], rcond=None)
    fit = coef[0] + coef[1] * xn + coef[2] * yn
    resid = z[m] - fit[m]
    tot = float(z[m].std())
    return {
        "dz_dx_cm_per_halfspan": float(coef[1]),
        "dz_dy_cm_per_halfspan": float(coef[2]),
        "residual_std_cm": float(resid.std()),
        "total_std_cm": tot,
        "residual_ratio": float(resid.std() / tot) if tot > 1e-9 else None,
    }


def fit_quadratic(z, valid):
    """Least-squares quadratic; returns Hessian eigenvalues (cm per unit^2)."""
    h, w = z.shape
    xn, yn = _norm_coords(h, w)
    m = valid
    n = int(m.sum())
    if n < 24:
        return None
    a = np.column_stack([np.ones(n), xn[m], yn[m],
                         xn[m] ** 2, xn[m] * yn[m], yn[m] ** 2])
    coef, *_ = np.linalg.lstsq(a, z[m], rcond=None)
    d, e, f = coef[3], coef[4], coef[5]
    hess = np.array([[2 * d, e], [e, 2 * f]], dtype=np.float64)
    ev = np.linalg.eigvalsh(hess)          # ascending: k1 <= k2
    return {"k1_cm": float(ev[0]), "k2_cm": float(ev[1])}


def classify_form(quad, thresh_cm=300.0):
    """Name the dominant large-scale shape from the fitted Hessian."""
    if quad is None:
        return "unknown"
    k1, k2 = quad["k1_cm"], quad["k2_cm"]
    t = thresh_cm
    if k1 > t and k2 > t:
        return "basin"
    if k1 < -t and k2 < -t:
        return "dome"
    if k1 < -t and k2 > t:
        return "saddle"
    if k2 > t and abs(k1) <= t:
        return "trough"          # valley along one axis
    if k1 < -t and abs(k2) <= t:
        return "ridge"
    return "planar"


def _downsample(z, valid, target=64):
    """Box-mean then index-sample to <=target x target."""
    zf = np.where(valid, z, 0.0)
    k = max(1, min(z.shape) // target)
    if k > 1:
        s = _box_sums(zf, k)
        c = _box_sums(valid.astype(np.float64), k)
        with np.errstate(invalid="ignore", divide="ignore"):
            zb = np.where(c > 0, s / np.maximum(c, 1e-9), np.nan)
        vb = c > 0
    else:
        zb = np.where(valid, z, np.nan)
        vb = valid.copy()
    hh, ww = zb.shape
    ri = np.linspace(0, hh - 1, min(target, hh)).astype(int)
    ci = np.linspace(0, ww - 1, min(target, ww)).astype(int)
    return zb[np.ix_(ri, ci)], vb[np.ix_(ri, ci)]


def spectral_bands(z, valid):
    """Power fraction by radial wavenumber (cycles per map) after plane detrend."""
    m = valid
    if int(m.sum()) < 64:
        return None
    fill = float(z[m].mean())
    zz = np.where(m, z, fill)
    h, w = zz.shape
    xn, yn = _norm_coords(h, w)
    a = np.column_stack([np.ones(zz.size), xn.ravel(), yn.ravel()])
    coef, *_ = np.linalg.lstsq(a, zz.ravel(), rcond=None)
    zz = zz - (coef[0] + coef[1] * xn + coef[2] * yn)
    p = np.abs(np.fft.fft2(zz)) ** 2
    p[0, 0] = 0.0
    ky = np.fft.fftfreq(h) * h
    kx = np.fft.fftfreq(w) * w
    kxx, kyy = np.meshgrid(kx, ky)
    kr = np.hypot(kxx, kyy)
    tot = float(p.sum())
    if tot <= 0:
        return None
    out = {}
    for b in (1, 2, 4, 8, 16):
        out["frac_power_k_le_%d" % b] = _r(float(p[kr <= b + 1e-9].sum()) / tot, 4)
    out["frac_power_k_gt_16"] = _r(float(p[kr > 16].sum()) / tot, 4)
    out["nan_fill_fraction"] = _r(1.0 - float(m.sum()) / m.size, 4)
    return out


# --------------------------------------------------------------------------
# corpus IO
# --------------------------------------------------------------------------
def sector_dirs(map_dir):
    try:
        names = sorted(os.listdir(map_dir))
    except OSError:
        return []
    return [n for n in names
            if _SECTOR_RE.match(n) and os.path.isdir(os.path.join(map_dir, n))]


def find_nested_sector_dirs(maps_root):
    """Sector dirs that themselves contain a sector dir holding a height.raw.

    The client builds sectree paths as ``<map>/%06u/<file>`` and never
    recurses, so anything one level deeper is unreachable orphan data.  A
    corpus walker that globs ``**/height.raw`` will pick these up and
    double-count; :func:`sector_dirs` deliberately does not.
    """
    out = []
    for m in sorted(os.listdir(maps_root)):
        md = os.path.join(maps_root, m)
        if not os.path.isdir(md):
            continue
        for s in sector_dirs(md):
            sd = os.path.join(md, s)
            for inner in sector_dirs(sd):
                if os.path.isfile(os.path.join(sd, inner, "height.raw")):
                    out.append("%s/%s/%s" % (m, s, inner))
    return out


def parse_sector_name(name):
    """``printf("%06u", x*1000 + y)`` -> ``(x, y)`` (mapformat/README.md:36)."""
    n = int(name)
    return n // 1000, n % 1000


def load_map_heights(map_dir, want_water=True, want_attr=True):
    """-> ({(x,y): HeightMap}, {(x,y): {...masks}}, [warnings]).

    The second dict carries per-sector 128x128 boolean masks derived from the
    sibling layers: ``wet`` from ``water.wtr`` and ``block`` from ``attr.atr``
    (``ATTR_BLOCK`` 0x01, OR-reduced from the 256x256 half-cell grid down to
    the 128x128 terrain-cell grid so it aligns with the slope array).
    """
    heights, side, warn = {}, {}, []
    for name in sector_dirs(map_dir):
        x, y = parse_sector_name(name)
        hp = os.path.join(map_dir, name, "height.raw")
        if os.path.isfile(hp):
            size = os.path.getsize(hp)
            if size != height_codec.FILE_SIZE:
                warn.append("%s/height.raw is %d bytes (expected %d)"
                            % (name, size, height_codec.FILE_SIZE))
            try:
                heights[(x, y)] = height_codec.read_height(hp)
            except Exception as exc:                      # noqa: BLE001
                warn.append("%s/height.raw unreadable: %s" % (name, exc))
        else:
            warn.append("%s has no height.raw" % name)
        slot = side.setdefault((x, y), {})
        if want_water:
            wp = os.path.join(map_dir, name, "water.wtr")
            if os.path.isfile(wp):
                try:
                    slot["wet"] = water_codec.read_water(wp).wet_mask
                except Exception as exc:                  # noqa: BLE001
                    warn.append("%s/water.wtr unreadable: %s" % (name, exc))
        if want_attr:
            ap = os.path.join(map_dir, name, "attr.atr")
            if os.path.isfile(ap):
                try:
                    g = attr_codec.read_attr(ap).cells
                    blk = (g & attr_codec.ATTR_BLOCK) != 0
                    slot["block"] = blk.reshape(SECTOR_CELLS, 2,
                                                SECTOR_CELLS, 2).any(axis=(1, 3))
                except Exception as exc:                  # noqa: BLE001
                    warn.append("%s/attr.atr unreadable: %s" % (name, exc))
    return heights, side, warn


def build_mosaic(heights):
    """Stitch sector vertex grids into one array. -> (raw, valid, origin, dims)."""
    xs = [k[0] for k in heights]
    ys = [k[1] for k in heights]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    nx, ny = x1 - x0 + 1, y1 - y0 + 1
    hgt = ny * SECTOR_CELLS + 1
    wid = nx * SECTOR_CELLS + 1
    raw = np.zeros((hgt, wid), dtype=np.float64)
    valid = np.zeros((hgt, wid), dtype=bool)
    for (x, y), hm in sorted(heights.items()):
        r = (y - y0) * SECTOR_CELLS
        c = (x - x0) * SECTOR_CELLS
        raw[r:r + VERTEX_SIZE, c:c + VERTEX_SIZE] = hm.vertices
        valid[r:r + VERTEX_SIZE, c:c + VERTEX_SIZE] = True
    return raw, valid, (x0, y0), (nx, ny)


def build_cell_mosaic(side, key, origin, dims):
    """Cell-resolution boolean mosaic (``key`` of the side dict) + known mask."""
    x0, y0 = origin
    nx, ny = dims
    grid = np.zeros((ny * SECTOR_CELLS, nx * SECTOR_CELLS), dtype=bool)
    known = np.zeros_like(grid)
    for (x, y), slot in side.items():
        m = slot.get(key)
        if m is None:
            continue
        r = (y - y0) * SECTOR_CELLS
        c = (x - x0) * SECTOR_CELLS
        if (r < 0 or c < 0 or r + SECTOR_CELLS > grid.shape[0]
                or c + SECTOR_CELLS > grid.shape[1]):
            continue
        grid[r:r + SECTOR_CELLS, c:c + SECTOR_CELLS] = m
        known[r:r + SECTOR_CELLS, c:c + SECTOR_CELLS] = True
    return grid, known


# --------------------------------------------------------------------------
# seam continuity
# --------------------------------------------------------------------------
def seam_stats(heights):
    """Do neighbouring sectors' shared edges actually match?

    Two independent checks per adjacent pair:

    ``shared_edge``   the 129 world vertices on the common border, stored once
                      in each sector (A vertex col 128 vs B vertex col 0).
                      These are the *same* world vertex; any difference is a
                      real crack in the rendered mesh.
    ``skirt_fwd``     the low sector's ``sx=129`` / ``sy=129`` skirt against the
                      high sector's ``sx=1`` / ``sy=1`` interior column/row.
    ``skirt_bwd``     the high sector's ``sx=-1`` / ``sy=-1`` skirt against the
                      low sector's ``sx=127`` / ``sy=127`` interior column/row.

    Both skirt checks come from height-raw.md ("the skirt must be kept in sync
    with neighbor sectors"); they affect normals/lighting only, not the mesh.
    They are reported separately because the two directions are *not* equally
    well maintained in shipped data.
    """
    shared, fwd, bwd = [], [], []
    pairs = 0
    for (x, y), a in heights.items():
        for dx, dy in ((1, 0), (0, 1)):
            b = heights.get((x + dx, y + dy))
            if b is None:
                continue
            pairs += 1
            if dx:
                shared.append(np.abs(a.vertices[:, -1].astype(np.int64)
                                     - b.vertices[:, 0].astype(np.int64)))
                fwd.append(np.abs(a.raw[1:130, 130].astype(np.int64)
                                  - b.raw[1:130, 2].astype(np.int64)))
                bwd.append(np.abs(b.raw[1:130, 0].astype(np.int64)
                                  - a.raw[1:130, 128].astype(np.int64)))
            else:
                shared.append(np.abs(a.vertices[-1, :].astype(np.int64)
                                     - b.vertices[0, :].astype(np.int64)))
                fwd.append(np.abs(a.raw[130, 1:130].astype(np.int64)
                                  - b.raw[2, 1:130].astype(np.int64)))
                bwd.append(np.abs(b.raw[0, 1:130].astype(np.int64)
                                  - a.raw[128, 1:130].astype(np.int64)))
    if not pairs:
        return {"n_adjacent_pairs": 0}
    return {
        "n_adjacent_pairs": pairs,
        "shared_edge": _seam_block(np.concatenate(shared)),
        "skirt_fwd": _seam_block(np.concatenate(fwd)),
        "skirt_bwd": _seam_block(np.concatenate(bwd)),
        "skirt_mirror": _seam_block(np.concatenate(fwd + bwd)),
    }


def _seam_block(d):
    per = d.astype(np.float64)
    nz = per[per > 0]
    extra = {}
    if nz.size:
        extra = {
            "n_mismatched": int(nz.size),
            "mismatch_p50_raw": _r(float(np.percentile(nz, 50)), 2),
            "mismatch_p90_raw": _r(float(np.percentile(nz, 90)), 2),
        }
    return dict(extra, **{
        "n_vertices": int(per.size),
        "frac_exact": _r(float(np.count_nonzero(per == 0)) / per.size, 6),
        "frac_le_1_raw": _r(float(np.count_nonzero(per <= 1)) / per.size, 6),
        "mean_abs_raw": _r(per.mean(), 4),
        "p99_abs_raw": _r(float(np.percentile(per, 99)), 3),
        "max_abs_raw": int(per.max()),
        "mean_abs_cm": _r(per.mean() * HEIGHT_SCALE, 4),
        "max_abs_cm": _r(float(per.max()) * HEIGHT_SCALE, 3),
    })


# --------------------------------------------------------------------------
# quantisation
# --------------------------------------------------------------------------
def quantisation_stats(counts):
    """From a 65536-bin bincount of raw uint16 values."""
    total = int(counts.sum())
    used = np.nonzero(counts)[0]
    if total == 0 or used.size == 0:
        return None
    modal = int(used[np.argmax(counts[used])])
    out = {
        "n_samples": total,
        "distinct_raw_values": int(used.size),
        "raw_min": int(used[0]),
        "raw_max": int(used[-1]),
        "modal_raw": modal,
        "modal_share": _r(float(counts[modal]) / total, 5),
        "modal_is_blank_fill_0x7FFF": modal == height_codec.BLANK_RAW,
    }
    for k in (2, 4, 8, 16, 32, 64, 128, 256):
        idx = used[used % k == 0]
        out["frac_multiple_of_%d" % k] = _r(float(counts[idx].sum()) / total, 5)
    g = 0
    base = int(used[0])
    for v in used.tolist():
        g = int(np.gcd(g, v - base))
        if g == 1:
            break
    out["gcd_of_offsets_from_min"] = g
    if used.size > 1:
        gaps = np.diff(used)
        out["min_gap_raw"] = int(gaps.min())
        out["median_gap_raw"] = _r(float(np.median(gaps)), 2)
    return out


# --------------------------------------------------------------------------
# per-map statistics
# --------------------------------------------------------------------------
def map_terrain_stats(map_name, map_dir, meta=None, collect_patches=True):
    meta = meta or {}
    hs = float(meta.get("height_scale") or HEIGHT_SCALE)
    cs = float(meta.get("cell_scale") or CELL_SCALE)
    heights, side, warn = load_map_heights(map_dir)
    if not heights:
        return None, warn, None, None

    raw, valid, origin, dims = build_mosaic(heights)
    z = raw * hs                                   # cm
    nx, ny = dims

    # ---- height distribution (each world vertex counted exactly once) ------
    hcounts = np.bincount(raw[valid].astype(np.int64), minlength=65536).astype(np.int64)
    hzs = z[valid]

    # ---- slope: per sector, 128x128 cells, no overlap ---------------------
    shist = Hist(SLOPE_BINS, 0.0, SLOPE_BIN)
    walk_hist = Hist(SLOPE_BINS, 0.0, SLOPE_BIN)
    blocked_hist = Hist(SLOPE_BINS, 0.0, SLOPE_BIN)
    band_n = np.zeros(len(BLOCK_BANDS) - 1, dtype=np.int64)
    band_blocked = np.zeros(len(BLOCK_BANDS) - 1, dtype=np.int64)
    n_attr_cells = 0
    smax = 0.0
    relief = []
    sector_rows = {}
    for key, hm in sorted(heights.items()):
        sl = slope_grid(hm.vertices, hs, cs)
        shist.add(sl)
        smax = max(smax, float(sl.max()))
        blk = side.get(key, {}).get("block")
        if blk is not None:
            n_attr_cells += blk.size
            walk_hist.add(sl[~blk])
            blocked_hist.add(sl[blk])
            idx = np.clip(np.searchsorted(np.asarray(BLOCK_BANDS[1:-1], dtype=float),
                                          sl.ravel(), side="right"),
                          0, len(band_n) - 1)
            band_n += np.bincount(idx, minlength=len(band_n)).astype(np.int64)
            band_blocked += np.bincount(idx, weights=blk.ravel().astype(np.float64),
                                        minlength=len(band_n)).astype(np.int64)
        vz = hm.vertices.astype(np.float64) * hs
        rel = float(vz.max() - vz.min())
        relief.append(rel)
        sector_rows["%06d" % (key[0] * 1000 + key[1])] = {
            "relief_cm": _r(rel, 1),
            "mean_cm": _r(float(vz.mean()), 1),
            "raw_min": int(hm.vertices.min()),
            "raw_max": int(hm.vertices.max()),
            "slope_p50": _r(float(np.percentile(sl, 50)), 3),
            "slope_p95": _r(float(np.percentile(sl, 95)), 3),
            "slope_max": _r(float(sl.max()), 3),
            "frac_lt_5deg": _r(float(np.count_nonzero(sl < 5.0)) / sl.size, 4),
        }

    # ---- roughness --------------------------------------------------------
    rough = {}
    lap_hists, std_hists = {}, {}
    for s in LAP_SCALES:
        h = Hist(ROUGH_BINS, 0.0, ROUGH_BIN)
        h.add(abs_laplacian(z, valid, s))
        lap_hists[s] = h
        rough["abs_laplacian_r%d_cm" % s] = h.summary()
    for k in STD_SCALES:
        h = Hist(ROUGH_BINS, 0.0, ROUGH_BIN)
        h.add(box_std(z, valid, k))
        std_hists[k] = h
        rough["local_std_%dx%d_cm" % (k, k)] = h.summary()

    # ---- large-scale form -------------------------------------------------
    zd, vd = _downsample(z, valid, 64)
    vd = vd & np.isfinite(zd)
    zd = np.where(vd, zd, 0.0)
    plane = fit_plane(zd, vd)
    quad = fit_quadratic(zd, vd)
    hh, ww = zd.shape
    xn, yn = _norm_coords(hh, ww)
    cheb = np.maximum(np.abs(xn), np.abs(yn))
    rim = vd & (cheb >= 0.85)
    core = vd & (cheb <= 0.40)
    form = {
        "downsampled_to": [int(hh), int(ww)],
        "plane_fit": {k: _r(v, 4) for k, v in (plane or {}).items()},
        "quadratic": {k: _r(v, 2) for k, v in (quad or {}).items()},
        "form_class": classify_form(quad),
        "rim_mean_cm": _r(float(zd[rim].mean()) if rim.any() else None, 1),
        "core_mean_cm": _r(float(zd[core].mean()) if core.any() else None, 1),
        "rim_minus_core_cm": _r(float(zd[rim].mean() - zd[core].mean())
                                if (rim.any() and core.any()) else None, 1),
        "spectrum": spectral_bands(zd, vd),
    }
    if plane:
        gmag = np.hypot(plane["dz_dx_cm_per_halfspan"], plane["dz_dy_cm_per_halfspan"])
        halfspan_cm = max(nx, ny) * SECTOR_CELLS * cs / 2.0
        form["plane_tilt_deg"] = _r(float(np.degrees(np.arctan(gmag / halfspan_cm))), 4)

    # ---- water ------------------------------------------------------------
    wetg, known = build_cell_mosaic(side, "wet", origin, dims)
    wet_frac = (float(np.count_nonzero(wetg & known)) / float(np.count_nonzero(known))
                if known.any() else None)

    # ---- walkability cross-check against attr.atr ATTR_BLOCK --------------
    walk = None
    if n_attr_cells:
        bands = []
        for i in range(len(band_n)):
            if band_n[i] == 0:
                continue
            bands.append({
                "slope_lo": BLOCK_BANDS[i], "slope_hi": BLOCK_BANDS[i + 1],
                "n_cells": int(band_n[i]),
                "cell_share": _r(float(band_n[i]) / band_n.sum(), 5),
                "blocked_fraction": _r(float(band_blocked[i]) / band_n[i], 5),
            })
        walk = {
            "n_cells_with_attr": int(n_attr_cells),
            "blocked_fraction_all_cells": _r(float(blocked_hist.total) / n_attr_cells, 5),
            "slope_deg_walkable": _slope_summary(walk_hist, walk_hist.vmax or 0.0),
            "slope_deg_blocked": _slope_summary(blocked_hist, blocked_hist.vmax or 0.0),
            "blocked_fraction_by_slope_band": bands,
            "slope_at_50pct_blocked_deg": _r(_cross50(bands), 2),
            "slope_at_50pct_blocked_note": ("interpolated from the >=2 deg "
                                            "bands only; see _cross50"),
        }

    stats = {
        "map": map_name,
        "archetype": meta.get("archetype"),
        "declared_map_size": meta.get("size"),
        "sector_grid_origin": list(origin),
        "sector_grid_dims": [nx, ny],
        "n_sectors_with_height": len(heights),
        "n_sectors_in_bounding_grid": nx * ny,
        "height_scale": hs,
        "cell_scale": cs,
        "mosaic_vertices": [int(z.shape[0]), int(z.shape[1])],
        "world_span_cm": [nx * SECTOR_CELLS * cs, ny * SECTOR_CELLS * cs],
        "height_cm": _pcts(hzs, (0, 5, 25, 50, 75, 95, 100), 1),
        "raw_range_used": [int(raw[valid].min()), int(raw[valid].max())],
        "relief_cm_map": _r(float(hzs.max() - hzs.min()), 1),
        "relief_cm_per_sector": _pcts(relief, (0, 25, 50, 75, 100), 1),
        "slope_deg": _slope_summary(shist, smax),
        "roughness": rough,
        "seams": seam_stats(heights),
        "large_scale_form": form,
        "quantisation": quantisation_stats(hcounts),
        "water_cell_fraction": _r(wet_frac, 5),
        "walkability": walk,
        "n_cells_slope": shist.total,
        "n_vertices": int(np.count_nonzero(valid)),
        "warnings": warn,
    }

    acc = {"hcounts": hcounts, "shist": shist, "smax": smax, "relief": relief,
           "lap": lap_hists, "std": std_hists, "form": form,
           "seams": stats["seams"], "n_sectors": len(heights),
           "walk_hist": walk_hist, "blocked_hist": blocked_hist,
           "band_n": band_n, "band_blocked": band_blocked,
           "n_attr_cells": n_attr_cells,
           "wet_cells": int(np.count_nonzero(wetg & known)),
           "known_cells": int(np.count_nonzero(known))}

    patches = []
    if collect_patches:
        patches = _scan_patches(map_name, meta, raw, valid, wetg, known,
                                origin, hs, cs)
    return stats, warn, acc, (patches, sector_rows)


def _cross50(bands, min_slope=2.0):
    """Slope (deg) where the blocked fraction first crosses 0.5, interpolated.

    Bands below ``min_slope`` are skipped on purpose: near-zero-slope cells are
    dominated by dungeon floors, water plates and blank fill that are blocked
    for reasons unrelated to steepness, so including them makes the curve start
    above 0.5 and the crossing meaningless.  From 2 deg upward the blocked
    fraction is monotone in slope in every archetype.
    """
    prev = None
    for b in bands:
        if b["slope_lo"] < min_slope:
            continue
        mid = (b["slope_lo"] + b["slope_hi"]) / 2.0
        f = b["blocked_fraction"]
        if f is None:
            continue
        if f >= 0.5:
            if prev is None or prev[1] >= 0.5:
                return mid
            pm, pf = prev
            return pm + (0.5 - pf) * (mid - pm) / (f - pf)
        prev = (mid, f)
    return None


def _slope_summary(shist, smax):
    out = {"n_cells": shist.total,
           "bin_width_deg": SLOPE_BIN,
           "mean": _r(shist.mean, 3), "std": _r(shist.std, 3),
           "max_exact": _r(smax, 3)}
    for q in (0.5, 0.75, 0.9, 0.95, 0.99):
        out["p%g" % (q * 100)] = _r(shist.pct(q), 3)
    for t in FLAT_THRESHOLDS:
        out["frac_lt_%gdeg" % t] = _r(shist.frac_below(t), 5)
    return out


# --------------------------------------------------------------------------
# signature patch extraction
# --------------------------------------------------------------------------
FEATURES = ("flat_fill", "flat_field", "gentle_slope", "cliff_face",
            "valley_floor", "ridge_line", "coastal_shelf",
            "mountain_ring_border")

FEATURE_RULES = {
    "flat_fill": ("relief_cm < 20 -- a mathematically flat plate, i.e. terrain "
                  "the artist never touched (usually the 0x7FFF NewHeightMap "
                  "fill or a single constant).  Catalogued as the *negative* "
                  "example: this is what unauthored terrain looks like."),
    "flat_field": ("slope_p95 < 2.0 deg AND 30 <= relief_cm <= 1000 -- flat "
                   "but not a blank plate.  NOTE: no 64x64-cell window anywhere "
                   "in the corpus is both flat and *gently undulating*; every "
                   "flat patch has slope_p50 = 0.000, i.e. authored flat ground "
                   "is piecewise-constant plateaus joined by small steps, never "
                   "smooth noise.  Ranked by relief so the most structured flat "
                   "ground wins."),
    "gentle_slope": ("2 <= slope_p50 <= 10 AND slope_p99 < 25 AND relief_cm >= "
                     "300 AND plane_residual_ratio < 0.65 (a consistent tilt, "
                     "not noise)"),
    "cliff_face": "slope_p99 >= 50 deg AND frac_gt_45deg >= 0.04",
    "valley_floor": ("both quadratic Hessian eigenvalues > 600 cm (basin) AND "
                     "slope_p90 < 25 AND slope_p95 < 35 (excludes dungeon pits "
                     "with vertical walls) AND 0.25 <= frac_lt_5deg AND "
                     "frac_lt_2deg <= 0.80 AND slope_p50 >= 1.5 (excludes a "
                     "flat dungeon floor whose edge walls fake a basin fit)"),
    "ridge_line": ("k1 < -900 cm AND |k2| <= 0.45*|k1| (one-axis crest) AND "
                   "slope_p50 >= 4 AND frac_lt_2deg < 0.40 (excludes a flat "
                   "floor with one wall through it)"),
    "coastal_shelf": ("0.15 <= water.wtr wet fraction <= 0.85 over the 64x64 "
                      "cells AND slope_p90 < 18 AND relief_cm >= 150"),
    "mountain_ring_border": ("patch touches the map's outer mosaic boundary AND "
                             "outer-8-cell band mean exceeds central 32x32 mean "
                             "by > 800 cm AND slope_p95 > 20"),
}


def describe_patch(block, wetblk, wetknown, hs, cs, touches_border):
    """Descriptor for one 65x65-vertex / 64x64-cell candidate."""
    v = block.astype(np.float64) * hs
    sl = slope_grid(block, hs, cs)
    q = np.percentile(sl, [50, 75, 90, 95, 99])
    zq = np.percentile(v, [5, 50, 95])
    ones = np.ones(v.shape, dtype=bool)
    quad = fit_quadratic(v, ones)
    plane = fit_plane(v, ones)
    band = np.ones(v.shape, dtype=bool)
    band[8:-8, 8:-8] = False
    core = np.zeros(v.shape, dtype=bool)
    core[16:-16, 16:-16] = True
    wf = (float(np.count_nonzero(wetblk)) / wetblk.size) if wetknown else None
    return {
        "slope_p50": float(q[0]), "slope_p75": float(q[1]), "slope_p90": float(q[2]),
        "slope_p95": float(q[3]), "slope_p99": float(q[4]),
        "slope_max": float(sl.max()), "slope_mean": float(sl.mean()),
        "frac_lt_2deg": float(np.count_nonzero(sl < 2) / sl.size),
        "frac_lt_5deg": float(np.count_nonzero(sl < 5) / sl.size),
        "frac_gt_45deg": float(np.count_nonzero(sl > 45) / sl.size),
        "height_cm_min": float(v.min()), "height_cm_max": float(v.max()),
        "height_cm_p5": float(zq[0]), "height_cm_p50": float(zq[1]),
        "height_cm_p95": float(zq[2]),
        "relief_cm": float(v.max() - v.min()),
        "raw_min": int(block.min()), "raw_max": int(block.max()),
        "k1_cm": quad["k1_cm"] if quad else None,
        "k2_cm": quad["k2_cm"] if quad else None,
        "plane_residual_ratio": plane["residual_ratio"] if plane else None,
        "rim_minus_core_cm": float(v[band].mean() - v[core].mean()),
        "wet_fraction": wf,
        "touches_map_border": bool(touches_border),
    }


def gates(d):
    """Which feature labels this patch qualifies for -> {feature: score}."""
    out = {}
    if d["relief_cm"] < 20.0:
        out["flat_fill"] = -d["relief_cm"]
    if d["slope_p95"] < 2.0 and 30.0 <= d["relief_cm"] <= 1000.0:
        out["flat_field"] = d["relief_cm"]
    if (2.0 <= d["slope_p50"] <= 10.0 and d["slope_p99"] < 25.0
            and d["relief_cm"] >= 300.0
            and d["plane_residual_ratio"] is not None
            and d["plane_residual_ratio"] < 0.65):
        out["gentle_slope"] = -d["plane_residual_ratio"]
    if d["slope_p99"] >= 50.0 and d["frac_gt_45deg"] >= 0.04:
        out["cliff_face"] = d["slope_p99"]
    if (d["k1_cm"] is not None and d["k1_cm"] > 600.0 and d["k2_cm"] > 600.0
            and d["slope_p90"] < 25.0 and d["slope_p95"] < 35.0
            and d["frac_lt_5deg"] >= 0.25 and d["frac_lt_2deg"] <= 0.80
            and d["slope_p50"] >= 1.5):
        out["valley_floor"] = d["k1_cm"] + d["k2_cm"]
    if (d["k1_cm"] is not None and d["k1_cm"] < -900.0
            and abs(d["k2_cm"]) <= 0.45 * abs(d["k1_cm"])
            and d["slope_p50"] >= 4.0 and d["frac_lt_2deg"] < 0.40):
        out["ridge_line"] = -d["k1_cm"]
    if (d["wet_fraction"] is not None and 0.15 <= d["wet_fraction"] <= 0.85
            and d["slope_p90"] < 18.0 and d["relief_cm"] >= 150.0):
        out["coastal_shelf"] = -abs(d["wet_fraction"] - 0.5)
    if (d["touches_map_border"] and d["rim_minus_core_cm"] > 800.0
            and d["slope_p95"] > 20.0):
        out["mountain_ring_border"] = d["rim_minus_core_cm"]
    return out


def _scan_patches(map_name, meta, raw, valid, wetg, known, origin, hs, cs,
                  per_map_per_feature=2):
    hgt, wid = raw.shape
    best = {}
    x0, y0 = origin
    for r in range(0, hgt - PATCH_VERTS + 1, PATCH_STRIDE):
        for c in range(0, wid - PATCH_VERTS + 1, PATCH_STRIDE):
            if not valid[r:r + PATCH_VERTS, c:c + PATCH_VERTS].all():
                continue
            block = raw[r:r + PATCH_VERTS, c:c + PATCH_VERTS].astype(np.uint16)
            wb = wetg[r:r + PATCH_CELLS, c:c + PATCH_CELLS]
            wk = bool(known[r:r + PATCH_CELLS, c:c + PATCH_CELLS].all())
            touches = (r == 0 or c == 0 or r + PATCH_VERTS == hgt
                       or c + PATCH_VERTS == wid)
            d = describe_patch(block, wb, wk, hs, cs, touches)
            for feat, score in gates(d).items():
                lst = best.setdefault(feat, [])
                lst.append((score, r, c, d, block))
                lst.sort(key=lambda t: -t[0])
                del lst[per_map_per_feature:]
    out = []
    for feat, lst in best.items():
        for score, r, c, d, block in lst:
            sx = x0 + c // SECTOR_CELLS
            sy = y0 + r // SECTOR_CELLS
            out.append({
                "map": map_name,
                "archetype": meta.get("archetype"),
                "feature": feat,
                "score": float(score),
                "origin_sector": "%06d" % (sx * 1000 + sy),
                "cell_offset_in_map": [int(c), int(r)],
                "cell_offset_in_sector": [int(c % SECTOR_CELLS), int(r % SECTOR_CELLS)],
                "world_origin_cm": [int(c * cs), int(r * cs)],
                "shape_vertices": [PATCH_VERTS, PATCH_VERTS],
                "cells": PATCH_CELLS,
                "height_scale": hs, "cell_scale": cs,
                "stats": {k: (_r(v, 4) if isinstance(v, float) else v)
                          for k, v in d.items()},
                "_block": block,
            })
    return out


def select_patches(all_patches, per_feature=12, max_per_map=2):
    """Greedy: best score first, one per map / archetype before doubling up."""
    chosen = []
    for feat in FEATURES:
        cands = sorted([p for p in all_patches if p["feature"] == feat],
                       key=lambda p: -p["score"])
        picked, seen_map, seen_arch = [], {}, {}
        taken = set()
        for want_new_arch in (True, False):
            for p in cands:
                if len(picked) >= per_feature:
                    break
                if id(p) in taken:
                    continue
                cap = 1 if want_new_arch else max_per_map
                if seen_map.get(p["map"], 0) >= cap:
                    continue
                if want_new_arch and seen_arch.get(p["archetype"], 0) >= 1:
                    continue
                taken.add(id(p))
                picked.append(p)
                seen_map[p["map"]] = seen_map.get(p["map"], 0) + 1
                seen_arch[p["archetype"]] = seen_arch.get(p["archetype"], 0) + 1
        chosen.extend(picked)
    return chosen


# --------------------------------------------------------------------------
# archetype / corpus aggregation
# --------------------------------------------------------------------------
def aggregate(accs):
    hc = np.zeros(65536, dtype=np.int64)
    shist = Hist(SLOPE_BINS, 0.0, SLOPE_BIN)
    smax = 0.0
    relief = []
    lap = {s: Hist(ROUGH_BINS, 0.0, ROUGH_BIN) for s in LAP_SCALES}
    std = {k: Hist(ROUGH_BINS, 0.0, ROUGH_BIN) for k in STD_SCALES}
    forms, tilts, rims, k1s, k2s, spec = [], [], [], [], [], []
    seam_pairs = 0
    seam_acc = {k: {"n": 0, "exact": 0.0, "le1": 0.0, "max": 0, "sumabs": 0.0}
                for k in ("shared_edge", "skirt_fwd", "skirt_bwd", "skirt_mirror")}
    maps_with_perfect_shared = 0
    maps_with_seams = 0
    nsec = 0
    walk_hist = Hist(SLOPE_BINS, 0.0, SLOPE_BIN)
    blocked_hist = Hist(SLOPE_BINS, 0.0, SLOPE_BIN)
    band_n = np.zeros(len(BLOCK_BANDS) - 1, dtype=np.int64)
    band_blocked = np.zeros(len(BLOCK_BANDS) - 1, dtype=np.int64)
    n_attr_cells = 0
    wet_cells = known_cells = 0
    for a in accs:
        walk_hist.merge(a["walk_hist"])
        blocked_hist.merge(a["blocked_hist"])
        band_n += a["band_n"]
        band_blocked += a["band_blocked"]
        n_attr_cells += a["n_attr_cells"]
        wet_cells += a["wet_cells"]
        known_cells += a["known_cells"]
        hc += a["hcounts"]
        shist.merge(a["shist"])
        smax = max(smax, a["smax"])
        relief.extend(a["relief"])
        for s in LAP_SCALES:
            lap[s].merge(a["lap"][s])
        for k in STD_SCALES:
            std[k].merge(a["std"][k])
        f = a["form"]
        forms.append(f["form_class"])
        if f.get("plane_tilt_deg") is not None:
            tilts.append(f["plane_tilt_deg"])
        if f.get("rim_minus_core_cm") is not None:
            rims.append(f["rim_minus_core_cm"])
        q = f.get("quadratic") or {}
        if q.get("k1_cm") is not None:
            k1s.append(q["k1_cm"])
            k2s.append(q["k2_cm"])
        if f.get("spectrum"):
            spec.append(f["spectrum"])
        sm = a["seams"]
        if sm.get("n_adjacent_pairs"):
            maps_with_seams += 1
            seam_pairs += sm["n_adjacent_pairs"]
            for k, acc in seam_acc.items():
                b = sm[k]
                acc["n"] += b["n_vertices"]
                acc["exact"] += b["frac_exact"] * b["n_vertices"]
                acc["le1"] += b["frac_le_1_raw"] * b["n_vertices"]
                acc["sumabs"] += b["mean_abs_raw"] * b["n_vertices"]
                acc["max"] = max(acc["max"], b["max_abs_raw"])
            if sm["shared_edge"]["max_abs_raw"] == 0:
                maps_with_perfect_shared += 1
        nsec += a["n_sectors"]

    total = int(hc.sum())
    cum = np.cumsum(hc)

    def hpct(q):
        return int(np.searchsorted(cum, q * total, side="left"))

    used = np.nonzero(hc)[0]
    form_counts = {}
    for f in forms:
        form_counts[f] = form_counts.get(f, 0) + 1
    spec_mean = {}
    if spec:
        for key in spec[0]:
            vals = [s[key] for s in spec if s.get(key) is not None]
            if vals:
                spec_mean[key] = _r(float(np.mean(vals)), 4)
    walk = None
    if n_attr_cells:
        bands = []
        for i in range(len(band_n)):
            if band_n[i] == 0:
                continue
            bands.append({
                "slope_lo": BLOCK_BANDS[i], "slope_hi": BLOCK_BANDS[i + 1],
                "n_cells": int(band_n[i]),
                "cell_share": _r(float(band_n[i]) / band_n.sum(), 5),
                "blocked_fraction": _r(float(band_blocked[i]) / band_n[i], 5),
            })
        walk = {
            "n_cells_with_attr": int(n_attr_cells),
            "blocked_fraction_all_cells": _r(float(blocked_hist.total) / n_attr_cells, 5),
            "slope_deg_walkable": _slope_summary(walk_hist, walk_hist.vmax or 0.0),
            "slope_deg_blocked": _slope_summary(blocked_hist, blocked_hist.vmax or 0.0),
            "blocked_fraction_by_slope_band": bands,
            "slope_at_50pct_blocked_deg": _r(_cross50(bands), 2),
            "slope_at_50pct_blocked_note": ("interpolated from the >=2 deg "
                                            "bands only; see _cross50"),
        }
    return {
        "n_maps": len(accs),
        "n_sectors": nsec,
        "n_vertices": total,
        "n_cells_slope": shist.total,
        "height_cm": {
            "n": total,
            "min": _r(int(used[0]) * HEIGHT_SCALE, 1),
            "max": _r(int(used[-1]) * HEIGHT_SCALE, 1),
            "mean": _r(float((hc * np.arange(65536, dtype=np.float64)).sum())
                       / total * HEIGHT_SCALE, 1),
            "p5": _r(hpct(0.05) * HEIGHT_SCALE, 1),
            "p50": _r(hpct(0.50) * HEIGHT_SCALE, 1),
            "p95": _r(hpct(0.95) * HEIGHT_SCALE, 1),
        },
        "raw_range_used": [int(used[0]), int(used[-1])],
        "slope_deg": _slope_summary(shist, smax),
        "walkability": walk,
        "water_cell_fraction": (_r(float(wet_cells) / known_cells, 5)
                                if known_cells else None),
        "relief_cm_per_sector": _pcts(relief, (0, 25, 50, 75, 90, 100), 1),
        "roughness": dict(
            [("abs_laplacian_r%d_cm" % s, lap[s].summary()) for s in LAP_SCALES]
            + [("local_std_%dx%d_cm" % (k, k), std[k].summary()) for k in STD_SCALES]),
        "seams": dict(
            [("n_maps_with_adjacent_sectors", maps_with_seams),
             ("n_adjacent_pairs", seam_pairs),
             ("n_maps_shared_edge_perfect", maps_with_perfect_shared)]
            + [(k, {"n_vertices": a["n"],
                    "frac_exact": _r(a["exact"] / a["n"], 6) if a["n"] else None,
                    "frac_le_1_raw": _r(a["le1"] / a["n"], 6) if a["n"] else None,
                    "mean_abs_raw": _r(a["sumabs"] / a["n"], 4) if a["n"] else None,
                    "max_abs_raw": a["max"],
                    "max_abs_cm": _r(a["max"] * HEIGHT_SCALE, 2)})
               for k, a in seam_acc.items()]),
        "large_scale_form": {
            "form_class_counts": form_counts,
            "plane_tilt_deg": _pcts(tilts, (0, 50, 100), 4),
            "rim_minus_core_cm": _pcts(rims, (0, 25, 50, 75, 100), 1),
            "k1_cm": _pcts(k1s, (0, 50, 100), 1),
            "k2_cm": _pcts(k2s, (0, 50, 100), 1),
            "mean_spectrum": spec_mean,
        },
        "quantisation": quantisation_stats(hc),
    }


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------
def _selftest():
    rng = np.random.default_rng(0)
    v = rng.integers(0, 65535, size=(129, 129)).astype(np.uint16)
    assert np.allclose(slope_grid(v), height_codec.slope_degrees(v))
    hm = height_codec.HeightMap(rng.integers(0, 65535, size=(131, 131)).astype("<u2"))
    assert np.allclose(hm.slope_degrees(), slope_grid(hm.vertices))
    a = np.arange(36, dtype=np.float64).reshape(6, 6)
    ok = np.ones_like(a, dtype=bool)
    assert abs(float(box_std(a, ok, 3)[0]) - float(a[:3, :3].std())) < 1e-9


def run(maps_root, taxonomy_path, out_path, patch_dir, only=None, no_patches=False):
    _selftest()
    t0 = time.time()
    tax = {}
    if taxonomy_path and os.path.isfile(taxonomy_path):
        with open(taxonomy_path, "r", encoding="utf-8") as fh:
            tax = json.load(fh)
    meta_by_map = tax.get("maps", {})

    names = sorted(n for n in os.listdir(maps_root)
                   if os.path.isdir(os.path.join(maps_root, n)))
    if only:
        names = [n for n in names if n in set(only)]

    per_map, skipped, all_patches, warnings = {}, {}, [], {}
    acc_by_arch, acc_all, sector_detail = {}, [], {}
    for i, name in enumerate(names):
        md = os.path.join(maps_root, name)
        meta = meta_by_map.get(name, {})
        stats, warn, acc, extra = map_terrain_stats(
            name, md, meta, collect_patches=not no_patches)
        if stats is None:
            skipped[name] = {
                "reason": "no height.raw in any sector directory",
                "archetype": meta.get("archetype"),
                "sector_file_profile": meta.get("sector_file_profile"),
                "terrain_source": meta.get("terrain_source"),
                "parent_map": meta.get("parent_map"),
                "n_sector_dirs": len(sector_dirs(md)),
            }
            if warn:
                warnings[name] = warn
            continue
        per_map[name] = stats
        if warn:
            warnings[name] = warn
        arch = meta.get("archetype") or "unclassified"
        acc_by_arch.setdefault(arch, []).append(acc)
        acc_all.append(acc)
        patches, srows = extra
        sector_detail[name] = srows
        all_patches.extend(patches)
        sys.stderr.write("[%3d/%3d] %-46s sectors=%-3d %6.1fs\n"
                         % (i + 1, len(names), name,
                            stats["n_sectors_with_height"], time.time() - t0))
        sys.stderr.flush()

    by_arch = {a: aggregate(v) for a, v in sorted(acc_by_arch.items())}
    corpus = aggregate(acc_all) if acc_all else {}

    patch_index = []
    if not no_patches and all_patches:
        os.makedirs(patch_dir, exist_ok=True)
        chosen = select_patches(all_patches)
        seq = {}
        for p in chosen:
            n = seq.get(p["feature"], 0)
            seq[p["feature"]] = n + 1
            fn = "%s_%02d_%s_%s_c%03d_r%03d.npy" % (
                p["feature"], n, p["map"], p["origin_sector"],
                p["cell_offset_in_sector"][0], p["cell_offset_in_sector"][1])
            np.save(os.path.join(patch_dir, fn), p["_block"])
            rec = {k: v for k, v in p.items() if k != "_block"}
            rec["file"] = fn
            rec["dtype"] = "uint16"
            rec["note"] = ("raw height.raw uint16 vertex block, row-major, "
                           "row 0 = north; world cm = value * height_scale")
            patch_index.append(rec)
        with open(os.path.join(patch_dir, "index.json"), "w", encoding="utf-8") as fh:
            json.dump({
                "schema_version": 1,
                "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "generator": "m2map.mine.terrain_stats",
                "corpus_root": maps_root,
                "patch_cells": PATCH_CELLS,
                "patch_vertices": PATCH_VERTS,
                "candidate_stride_vertices": PATCH_STRIDE,
                "n_maps_scanned": len(per_map),
                "n_candidates_gated": len(all_patches),
                "n_saved": len(patch_index),
                "feature_rules": FEATURE_RULES,
                "patches": patch_index,
            }, fh, indent=1)

    doc = {
        "schema_version": 1,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "generator": "m2map.mine.terrain_stats",
        "corpus_root": maps_root,
        "taxonomy": taxonomy_path,
        "sampling": {
            "policy": "census -- every height.raw in the corpus, no subsampling",
            "n_map_dirs_scanned": len(names),
            "n_maps_with_terrain": len(per_map),
            "n_maps_skipped": len(skipped),
            "n_sectors": sum(s["n_sectors_with_height"] for s in per_map.values()),
            "n_vertices": corpus.get("n_vertices"),
            "n_cells_slope": corpus.get("n_cells_slope"),
            "orphan_nested_sector_dirs": find_nested_sector_dirs(maps_root),
            "orphan_nested_note": ("unreachable second-level sectree dirs -- the "
                                   "client only ever opens <map>/%06u/<file>. "
                                   "Excluded from every statistic here; a "
                                   "**/height.raw glob would double-count them."),
        },
        "conventions": {
            "cell_scale_cm": CELL_SCALE,
            "height_scale": HEIGHT_SCALE,
            "sector_cells": SECTOR_CELLS,
            "world_cm_per_raw_unit": HEIGHT_SCALE,
            "slope_definition": ("atan(hypot(gx,gy)) in degrees; gx/gy = mean of "
                                 "the cell's two X / two Y vertex deltas divided "
                                 "by CellScale; identical to "
                                 "m2map.codec.height.slope_degrees"),
            "slope_histogram_bin_deg": SLOPE_BIN,
            "roughness_histogram_bin_cm": ROUGH_BIN,
            "percentile_note": ("percentiles from histograms are bin-centre "
                                "estimates (+-%.3f deg slope, +-%.1f cm "
                                "roughness); n/mean/std/min/max are exact"
                                % (SLOPE_BIN / 2, ROUGH_BIN / 2)),
            "height_percentiles": ("exact -- computed from a 65536-bin bincount "
                                   "of the raw uint16 values"),
        },
        "corpus": corpus,
        "by_archetype": by_arch,
        "by_map": per_map,
        "per_sector": sector_detail,
        "skipped_maps": skipped,
        "warnings": warnings,
        "elapsed_s": round(time.time() - t0, 1),
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    return doc


def main(argv=None):
    root = os.path.abspath(os.path.join(_PKG_PARENT, "..", "reference", "catalog"))
    ap = argparse.ArgumentParser(description="mine height.raw terrain statistics")
    ap.add_argument("--maps", default="<CORPUS>")
    ap.add_argument("--taxonomy", default=os.path.join(root, "map-taxonomy.json"))
    ap.add_argument("--out", default=os.path.join(root, "stats-terrain.json"))
    ap.add_argument("--patch-dir", default=os.path.join(root, "patches"))
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--no-patches", action="store_true")
    ns = ap.parse_args(argv)
    doc = run(os.path.abspath(ns.maps), os.path.abspath(ns.taxonomy),
              os.path.abspath(ns.out), os.path.abspath(ns.patch_dir),
              only=ns.only, no_patches=ns.no_patches)
    s = doc["sampling"]
    sys.stderr.write("maps=%d/%d sectors=%d vertices=%s cells=%s in %.1fs\n"
                     % (s["n_maps_with_terrain"], s["n_map_dirs_scanned"],
                        s["n_sectors"], s["n_vertices"], s["n_cells_slope"],
                        doc["elapsed_s"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

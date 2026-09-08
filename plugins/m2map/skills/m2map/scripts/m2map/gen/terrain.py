"""Stage 3 -- height.raw.

Procedural macro-form, then every parameter clamped to the archetype's measured
distribution. The clamping is the point: unconstrained fBm produces terrain that
is perfectly plausible and reads as a modern heightmap generator rather than
2005 Ymir.

What the corpus says (stats-terrain.json):

* Raw slope is **bimodal**, not smooth. 42.2% of cells are under 2 degrees and
  33.6% are over 35; almost nothing lives between. Quoting a single "median
  slope" and generating to it produces uniformly rolling ground that exists
  nowhere in the corpus.
* **Walkable** slope is the constraint that matters: p50 4.6, p75 10.7, p90 18.3,
  p95 23.9. The steep third is cliff and mountain the player never stands on.
* ``0x7FFF`` blank fill is 16% of all vertices corpus-wide (56% in
  ``dungeon_block``) -- it is the editor's "untouched" value, not an anomaly.
* Shared sector borders are bit-exact in 99.86% of cases. Seams must be
  reconciled explicitly; they do not come out right by accident.

Heights are stored as ``uint16`` and scaled by 0.5, so the representable step is
0.5 cm and the ceiling is 32,767.5 cm.
"""

from __future__ import annotations

import numpy as np

from .spec import CELL_SCALE, HEIGHT_SCALE, MapSpec, SECTOR_CELLS

#: height.raw is stored 131x131 with a 1-vertex skirt on each side around the
#: 129x129 logical vertex grid (see reference/mapformat/height-raw.md).
STORED = 131
LOGICAL = 129

#: The WorldEditor's "never touched" fill (MapAccessorTerrain.cpp:1031).
BLANK = 0x7FFF


def _value_noise(rng: np.random.Generator, h: int, w: int, cells: int) -> np.ndarray:
    """Smooth 2-D value noise on a ``cells``-spaced lattice, bilinear upsampled.

    Deliberately not Perlin: the corpus's low-frequency form is broad and
    rounded, and value noise reproduces that with far less machinery.
    """
    gh, gw = max(2, h // cells + 2), max(2, w // cells + 2)
    lattice = rng.random((gh, gw))

    ys = np.linspace(0, gh - 1, h)
    xs = np.linspace(0, gw - 1, w)
    y0 = np.floor(ys).astype(int)
    x0 = np.floor(xs).astype(int)
    y1 = np.minimum(y0 + 1, gh - 1)
    x1 = np.minimum(x0 + 1, gw - 1)
    fy = (ys - y0)[:, None]
    fx = (xs - x0)[None, :]
    # smoothstep -- plain bilinear leaves visible lattice creases
    fy = fy * fy * (3 - 2 * fy)
    fx = fx * fx * (3 - 2 * fx)

    top = lattice[np.ix_(y0, x0)] * (1 - fx) + lattice[np.ix_(y0, x1)] * fx
    bot = lattice[np.ix_(y1, x0)] * (1 - fx) + lattice[np.ix_(y1, x1)] * fx
    return top * (1 - fy) + bot * fy


def fbm(rng: np.random.Generator, h: int, w: int, octaves: int = 5,
        base_cells: int = 96, gain: float = 0.5, ridged: bool = False) -> np.ndarray:
    """Fractal sum in [0, 1]. ``ridged`` folds each octave to make ridge lines."""
    out = np.zeros((h, w), np.float64)
    amp, cells, total = 1.0, base_cells, 0.0
    for _ in range(octaves):
        layer = _value_noise(rng, h, w, max(2, cells))
        if ridged:
            layer = 1.0 - np.abs(layer * 2.0 - 1.0)
        out += layer * amp
        total += amp
        amp *= gain
        cells = max(2, cells // 2)
    out /= total
    lo, hi = out.min(), out.max()
    return (out - lo) / (hi - lo) if hi > lo else out


def slope_degrees(height_cm: np.ndarray, cell_scale: int = CELL_SCALE) -> np.ndarray:
    """Per-vertex slope in degrees from a world-cm height grid."""
    gy, gx = np.gradient(height_cm.astype(np.float64), cell_scale)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def _plateau(field: np.ndarray, flat_fraction: float,
             compress: float = 0.12) -> np.ndarray:
    """Split a smooth field into plains and relief.

    Corpus slope is **bimodal**: 42.2% of cells under 2 degrees, 33.6% over 35,
    and almost nothing between. A plain fBm field is unimodal, so scaling it to
    a target median produces uniformly rolling ground that exists nowhere in the
    corpus -- correct on paper, obviously synthetic in game.

    This takes the lowest ``flat_fraction`` of the *area*, squashes it into a
    narrow band (the plains), and stretches everything above it over the rest of
    the range (the relief). The split point is a quantile, so the requested flat
    fraction is achieved by construction rather than by tuning an exponent.
    """
    f = float(np.clip(flat_fraction, 0.0, 0.95))
    if f <= 0.0:
        return field
    t = float(np.quantile(field, f))
    if t <= 0.0 or t >= 1.0:
        return field

    out = np.empty_like(field)
    low = field <= t
    # Plains: keep a little internal variation so they are not a dead plane.
    out[low] = (field[low] / t) * compress
    # Relief: the remaining range, starting where the plains stop.
    out[~low] = compress + (field[~low] - t) / (1.0 - t) * (1.0 - compress)
    return out


def _fit_flat_fraction(field: np.ndarray, lo: float, hi: float, spec,
                       tol: float = 0.03, iterations: int = 12) -> np.ndarray:
    """Binary-search the plateau split so the SLOPE flat fraction hits target.

    ``flat_fraction`` is the share of cells under 2 degrees. Setting the plateau
    quantile to that number gets nowhere near it, because a flat share of the
    *height* range is not a flat share of the *gradient*. A dozen bisection steps
    cost nothing next to the noise generation and remove the guesswork.
    """
    target = float(np.clip(spec.flat_fraction, 0.0, 0.95))
    if target <= 0.0:
        return _match_slope(lo + field * (hi - lo), spec.slope_p50, spec.slope_p95)

    best, best_err = None, None
    q_lo, q_hi = target, 0.98
    for _ in range(iterations):
        q = (q_lo + q_hi) / 2.0
        h = _match_slope(lo + _plateau(field, q) * (hi - lo),
                         spec.slope_p50, spec.slope_p95)
        got = float((slope_degrees(h) < 2.0).mean())
        err = abs(got - target)
        if best_err is None or err < best_err:
            best, best_err = h, err
        if err <= tol:
            break
        if got < target:
            q_lo = q          # not flat enough -- widen the plateau
        else:
            q_hi = q
    return best if best is not None else lo + field * (hi - lo)


def _match_slope(height_cm: np.ndarray, p50: float, p95: float,
                 iterations: int = 24) -> np.ndarray:
    """Scale the field until its walkable-slope quantiles match the archetype.

    Slope scales with amplitude, so a single global factor moves the whole
    distribution. Iterating on the p95 converges quickly and keeps the shape
    the noise produced, which a per-cell clamp would destroy.
    """
    out = height_cm.astype(np.float64)
    for _ in range(iterations):
        s = slope_degrees(out)
        walkable = s[s <= 45.0]
        if walkable.size < 16:
            break
        cur95 = float(np.percentile(walkable, 95))
        if cur95 < 1e-6:
            break
        ratio = p95 / cur95
        if 0.99 < ratio < 1.01:
            break
        out *= np.clip(ratio, 0.5, 2.0)
    return out


def _flatten_mask(height_cm: np.ndarray, mask: np.ndarray,
                  strength: float = 0.85, passes: int = 3) -> np.ndarray:
    """Pull masked cells towards their local mean -- roads and building pads.

    Corridors in the corpus are measurably flatter than their surroundings; a
    road that follows raw terrain reads as a painted stripe rather than a route.
    """
    out = height_cm.astype(np.float64).copy()
    if not mask.any():
        return out
    for _ in range(passes):
        blur = out.copy()
        blur[1:-1, 1:-1] = (out[:-2, 1:-1] + out[2:, 1:-1] +
                            out[1:-1, :-2] + out[1:-1, 2:] +
                            out[1:-1, 1:-1]) / 5.0
        out[mask] = out[mask] * (1 - strength) + blur[mask] * strength
    return out


def build(spec: MapSpec, flatten_mask: np.ndarray | None = None) -> np.ndarray:
    """Whole-map vertex height grid in world cm.

    Returns ``(h*128+1, w*128+1)`` -- the shared logical vertex grid. Splitting
    it into per-sector 131x131 blocks happens in :func:`to_sector_raw`, which is
    what makes borders bit-exact by construction: neighbouring sectors read the
    *same* vertices rather than each generating their own.
    """
    sx, sy = spec.size
    h = sy * SECTOR_CELLS + 1
    w = sx * SECTOR_CELLS + 1
    lo, hi = spec.height_range_cm

    if spec.is_box():
        # Interiors are a flat plane. dungeon_block terrain is literally that:
        # a single texture at luminance 0 with TerrainVisible 0.
        return np.full((h, w), lo, np.float64)

    rng = np.random.default_rng(abs(hash(("terrain", spec.seed))) % (2 ** 32))

    form = fbm(rng, h, w, octaves=5, base_cells=96, gain=0.5, ridged=True)
    detail = fbm(rng, h, w, octaves=4, base_cells=24, gain=0.55)
    field = form * (1.0 - spec.roughness * 0.5) + detail * (spec.roughness * 0.5)

    # The plateau split is a quantile of HEIGHT, but flat_fraction is defined on
    # SLOPE, and the two are only loosely related. Solve for the split that
    # actually lands the requested slope fraction instead of assuming they match.
    height = _fit_flat_fraction(field, lo, hi, spec)
    height = np.clip(height, 0.0, 32767.5)

    if flatten_mask is not None and flatten_mask.any():
        height = _flatten_mask(height, flatten_mask)

    return height


def to_raw(height_cm: np.ndarray) -> np.ndarray:
    """World cm -> the stored ``uint16`` quantisation (step 0.5 cm)."""
    return np.clip(np.round(height_cm / HEIGHT_SCALE), 0, 65535).astype("<u2")


def to_sector_raw(height_cm: np.ndarray, cx: int, cy: int) -> np.ndarray:
    """The 131x131 ``height.raw`` block for sector ``(cx, cy)``.

    The logical 129x129 vertices sit at ``[1:130, 1:130]``; the outer ring is
    the skirt, filled from the neighbouring sector's vertices where they exist
    and clamped at the map edge. Because every sector samples the same shared
    grid, shared border vertices are identical by construction -- the corpus
    achieves 99.86% and the remaining 0.14% are genuine authoring cracks.
    """
    h, w = height_cm.shape
    y0, x0 = cy * SECTOR_CELLS, cx * SECTOR_CELLS
    out = np.empty((STORED, STORED), np.float64)

    # Source window including one vertex of overlap on every side.
    ys = np.clip(np.arange(y0 - 1, y0 + LOGICAL + 1), 0, h - 1)
    xs = np.clip(np.arange(x0 - 1, x0 + LOGICAL + 1), 0, w - 1)
    out[:, :] = height_cm[np.ix_(ys, xs)]
    return to_raw(out)


def stats(height_cm: np.ndarray) -> dict:
    """Descriptive statistics in the same shape the corpus miner emits."""
    s = slope_degrees(height_cm)
    walk = s[s <= 45.0]
    q = lambda a, p: float(np.percentile(a, p)) if a.size else 0.0  # noqa: E731
    return {
        "height_cm": {"min": float(height_cm.min()), "max": float(height_cm.max()),
                      "mean": float(height_cm.mean())},
        "slope_deg": {"p50": q(s, 50), "p90": q(s, 90), "p95": q(s, 95),
                      "max": float(s.max())},
        "walkable_slope_deg": {"p50": q(walk, 50), "p75": q(walk, 75),
                               "p90": q(walk, 90), "p95": q(walk, 95)},
        "flat_fraction_2deg": float((s < 2.0).mean()),
        "steep_fraction_35deg": float((s > 35.0).mean()),
    }

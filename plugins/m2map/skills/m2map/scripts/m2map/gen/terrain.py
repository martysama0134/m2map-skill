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

from .spec import CELL_SCALE, HEIGHT_SCALE, MapSpec, SECTOR_CELLS, stream_seed

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
        return _match_slope(lo + field * (hi - lo), spec.slope_p50,
                            spec.slope_p95, base=lo)

    best, best_err = None, None
    q_lo, q_hi = target, 0.98
    for _ in range(iterations):
        q = (q_lo + q_hi) / 2.0
        h = _match_slope(lo + _plateau(field, q) * (hi - lo),
                         spec.slope_p50, spec.slope_p95, base=lo)
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
                 iterations: int = 24, base: float = 0.0) -> np.ndarray:
    """Scale the field's RELIEF until its walkable-slope quantiles match.

    Slope scales with amplitude, so a single global factor moves the whole
    distribution. Iterating on the p95 converges quickly and keeps the shape
    the noise produced, which a per-cell clamp would destroy.

    ``base`` is the floor the scaling pivots on, and it has to be
    ``height_range_cm[0]``. Scaling about **zero** -- which this did -- moves the
    terrain's absolute altitude as well as its relief, so a spec asking for
    16,000-23,000 cm came out at 3,486-8,348: the band was rescaled bodily
    toward the origin. Nothing in the map looks wrong on its own, because slope
    and relief are both still right; what breaks is anything expressed in
    absolute world cm, and ``WaterSpec.surface_z`` is exactly that. A lake at a
    surface picked from the requested range ends up a hundred metres above the
    ground it was meant to fill.

    Archetypes whose floor is 0 are unaffected -- pivoting on 0 and on the floor
    are the same operation there.
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
        out = base + (out - base) * np.clip(ratio, 0.5, 2.0)
    return out


def _flatten_mask(height_cm: np.ndarray, mask: np.ndarray,
                  strength: float = 0.90, passes: int = 16) -> np.ndarray:
    """Pull masked cells towards the mean of their MASKED neighbours.

    Corridors in the corpus are measurably flatter than their surroundings --
    slope inside the corridor over a [6, 24] m control band, median **0.21**
    across the 37 confirmed road maps. A road that follows raw terrain reads as
    a painted stripe rather than a route.

    Restricting the neighbourhood to the mask is the whole point. Averaging a
    corridor cell against ALL of its neighbours averages it against the
    hillside it is cut into, so every pass drags the road back up the slope it
    was meant to be levelled out of. Measured with the unrestricted stencil: 3
    passes and 40 passes both left the ratio at 0.90-0.93 against the corpus's
    0.21, and no strength or pass count moved it. Restricted, diffusion runs
    ALONG the corridor rather than across its banks and converges on a smooth
    longitudinal profile -- which is what a road is.
    """
    out = height_cm.astype(np.float64).copy()
    if not mask.any():
        return out
    m = mask.astype(np.float64)
    for _ in range(passes):
        acc = out * m
        cnt = m.copy()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            acc += np.roll(np.roll(out * m, dy, axis=0), dx, axis=1)
            cnt += np.roll(np.roll(m, dy, axis=0), dx, axis=1)
        blur = np.divide(acc, cnt, out=out.copy(), where=cnt > 0)
        out[mask] = out[mask] * (1 - strength) + blur[mask] * strength
    return out


def _level_pad(height_cm: np.ndarray, mask: np.ndarray,
               skirt: int = 4) -> np.ndarray:
    """Cut a level pad under ``mask``, graded to the surrounding ground.

    A plaza is built, not grown: the corpus measures 0.0-1.9 deg under every
    shipped paved disc, against 4-5 deg for the map around it. Smoothing cannot
    get there -- three passes of :func:`_flatten_mask` left the reference disc
    at 9.0 deg -- because smoothing preserves relief it merely blurs.

    The pad is set to the MEDIAN height under the mask rather than the mean, so
    one corner poking into a hillside does not drag the whole plaza up, and the
    skirt blends linearly over ``skirt`` cells so the rim reads as a slope
    instead of a step.
    """
    out = height_cm.astype(np.float64).copy()
    if not mask.any():
        return out
    level = float(np.median(out[mask]))

    # Distance outward from the pad, in cells, capped at the skirt width.
    near = mask.copy()
    weight = np.where(mask, 1.0, 0.0)
    for step in range(1, skirt + 1):
        grown = near.copy()
        grown[1:, :] |= near[:-1, :]
        grown[:-1, :] |= near[1:, :]
        grown[:, 1:] |= near[:, :-1]
        grown[:, :-1] |= near[:, 1:]
        ring = grown & ~near
        weight[ring] = 1.0 - step / float(skirt + 1)
        near = grown

    return out * (1.0 - weight) + level * weight


def build(spec: MapSpec, flatten_mask: np.ndarray | None = None,
          carve_cm: np.ndarray | None = None,
          ridge_gap: np.ndarray | None = None,
          pads: "list | None" = None,
          scarp_cm: np.ndarray | None = None,
          benches: "list | None" = None,
          bridges: "list | None" = None,
          channels: "list | None" = None) -> np.ndarray:
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

    rng = np.random.default_rng(stream_seed("terrain", spec.seed))

    form = fbm(rng, h, w, octaves=5, base_cells=96, gain=0.5, ridged=True)
    detail = fbm(rng, h, w, octaves=4, base_cells=24, gain=0.55)
    field = form * (1.0 - spec.roughness * 0.5) + detail * (spec.roughness * 0.5)

    # The plateau split is a quantile of HEIGHT, but flat_fraction is defined on
    # SLOPE, and the two are only loosely related. Solve for the split that
    # actually lands the requested slope fraction instead of assuming they match.
    height = _fit_flat_fraction(field, lo, hi, spec)
    height = np.clip(height, 0.0, 32767.5)


    # Wall the map in before the water bed is cut, so a river running off the
    # edge still carves through the rim rather than being buried by it.
    if spec.border_ridge_cm > 0:
        height = height + border_ridge(
            height.shape, spec.border_ridge_cm, spec.border_ridge_width_m,
            gap=(_to_cells(ridge_gap, height.shape)
                 if ridge_gap is not None else None),
            rng=np.random.default_rng(
                stream_seed("ridge", spec.seed)))
        height = np.clip(height, 0.0, 32767.5)

    # Scarps before the corridor levelling, so a road that crosses one is
    # levelled over the face it finds rather than cutting a face through a road
    # that was already flat.
    if scarp_cm is not None and scarp_cm.any():
        height = height - _to_cells(scarp_cm, height.shape)
        height = np.clip(height, 0.0, 32767.5)

    # Crest-driven scarps: pull the standing side to an absolute height. See
    # `ScarpSpec.crest_cm` -- this is how a wall gets sized to the prop that
    # will hang on it rather than the other way round.
    for weight, target in (benches or []):
        w = np.clip(_to_cells(weight, height.shape), 0.0, 1.0)
        height = height * (1.0 - w) + float(target) * w
        height = np.clip(height, 0.0, 32767.5)

    # Corridors and pads are levelled AFTER the ridge, not before. A road that
    # runs to the map edge crosses the wall, and `ridge_gap` only opens a saddle
    # for it -- the saddle still has to be levelled or the route is a switchback
    # over the rim. Measured on the desert reference spec: levelling first gave
    # a corridor slope ratio of 1.02 against its own control band (the road was
    # no flatter than the hillside beside it); levelling after gives 0.58.
    if flatten_mask is not None and flatten_mask.any():
        height = _flatten_mask(height, flatten_mask)

    # Pads after the smoothing pass, so the level surface is not blurred back
    # into the hillside it was cut from.
    for pad in (pads or []):
        height = _level_pad(height, pad)

    # Copied landforms after the pads and before the water: a stamped mountain
    # is not to be levelled by anything, and a river may still cut its foot.
    for rs in getattr(spec, "relief_stamps", None) or []:
        height = stamp_relief(height, rs)

    # Cut the water bed last, so flattening cannot fill it back in. Without a
    # bed the water plane lies on top of the ground as a flat slab; with one it
    # sits in a channel and the banks read as banks.
    if carve_cm is not None and carve_cm.any():
        height = height - _to_cells(carve_cm, height.shape)
        height = np.clip(height, 0.0, 32767.5)

    # A river with a stated surface gets an absolute bed under it -- see
    # `Layout.channels`. `min`, not assignment: ground already lower stays.
    for grade, surface, depth in (channels or []):
        g = _to_cells(grade, height.shape)
        height = np.where(g > 0.0, np.minimum(height, float(surface) - g * float(depth)), height)

    # Bridges last of all: both banks to ONE height, then the channel cut to the
    # span under it. After the river bed, so the cut deepens a channel that
    # exists rather than being softened by it, and after the road levelling, so
    # "the ground at the two ends" is already the road's own level.
    for fit in (bridges or []):
        core = _to_cells(fit.bank_core.astype(np.float64), height.shape) > 0.5
        # The bank is set from the WATER where the water has a stated level:
        # a stone bridge stands 2-5 m over it, a rope bridge 10-40 m. Only a
        # dry crossing, or an auto-levelled river, falls back to the ground.
        level = fit.spec.bank_cm
        if level is None and fit.water_cm is not None:
            level = fit.water_cm + float(fit.model["water_below_bank_cm"])
        if level is None:
            level = float(np.median(height[core])) if core.any() else float(np.median(height))
        fit.bank_cm = float(level)
        w = np.clip(_to_cells(fit.bank_weight, height.shape), 0.0, 1.0)
        height = height * (1.0 - w) + level * w
        bed = level - float(fit.model["bed_below_bank_cm"])
        c = np.clip(_to_cells(fit.cut_weight, height.shape), 0.0, 1.0)
        height = np.minimum(height, height * (1.0 - c) + bed * c)
        height = np.clip(height, 0.0, 32767.5)

    return height


def stamp_relief(height_cm: np.ndarray, rs) -> np.ndarray:
    """``height_cm`` with a `ReliefStampSpec` raised on it.

    The pattern's grid is sampled bilinearly through the block's turn (the same
    sign as `setpiece.rotate`: offsets turn clockwise in y-down metres), so a
    cone lands between vertices and at any angle without being resampled twice.
    The base is read off the TARGET the way it was read off the source -- the
    25th percentile of the feather ring -- and the ground is ``base + dz``
    inside, fading to the target's own across the ring.
    """
    src = np.asarray(rs.rows, dtype=np.float64)
    gh, gw = src.shape
    t = np.radians(float(rs.rotate_deg))
    c, sn = np.cos(t), np.sin(t)
    ax, ay = rs.anchor
    R, F = float(rs.radius_m), max(float(rs.feather_m), 1e-6)
    cell = CELL_SCALE / 100.0
    j0, j1 = max(int((ay - R) // cell), 0), min(int((ay + R) // cell) + 2, height_cm.shape[0])
    i0, i1 = max(int((ax - R) // cell), 0), min(int((ax + R) // cell) + 2, height_cm.shape[1])
    if j0 >= j1 or i0 >= i1:
        return height_cm
    yy, xx = np.mgrid[j0:j1, i0:i1]
    x, y = xx * cell - ax, yy * cell - ay
    r = np.hypot(x, y)
    u = ((x * c - y * sn) - rs.origin_m[0]) / float(rs.cell_m)      # back into the source
    v = ((x * sn + y * c) - rs.origin_m[1]) / float(rs.cell_m)
    inside = (u >= 0) & (u <= gw - 1) & (v >= 0) & (v <= gh - 1) & (r <= R)
    u0 = np.clip(np.floor(u).astype(int), 0, gw - 2)
    v0 = np.clip(np.floor(v).astype(int), 0, gh - 2)
    fu, fv = np.clip(u - u0, 0.0, 1.0), np.clip(v - v0, 0.0, 1.0)
    dz = (src[v0, u0] * (1 - fu) * (1 - fv) + src[v0, u0 + 1] * fu * (1 - fv)
          + src[v0 + 1, u0] * (1 - fu) * fv + src[v0 + 1, u0 + 1] * fu * fv)
    win = height_cm[j0:j1, i0:i1]
    ring = inside & (r >= R - F)
    base = float(np.percentile(win[ring], 25)) if ring.any() else float(np.median(win))
    k = np.clip((R - r) / F, 0.0, 1.0)
    w = np.where(inside, k * k * (3.0 - 2.0 * k), 0.0)
    out = height_cm.copy()
    out[j0:j1, i0:i1] = np.clip(win * (1.0 - w) + (base + dz) * w, 0.0, 32767.5)
    return out


def _to_cells(tile_grid: np.ndarray, shape) -> np.ndarray:
    """Tile-space (1 m) field -> terrain vertex grid (2 m), taking the max.

    Max rather than mean: a 3 m stream straddling a cell boundary must still
    carve that cell, or the channel develops gaps the water leaks out of.
    """
    h, w = shape
    th, tw = tile_grid.shape
    out = np.zeros(shape, tile_grid.dtype)
    uh, uw = min(h, th // 2), min(w, tw // 2)
    blk = tile_grid[:uh * 2, :uw * 2].reshape(uh, 2, uw, 2)
    out[:uh, :uw] = blk.max(axis=(1, 3))
    return out


def border_ridge(shape, lift_cm: float, width_m: float = 64.0,
                 gap: np.ndarray | None = None,
                 rng: np.random.Generator | None = None) -> np.ndarray:
    """A rim that rises toward every edge, so the player cannot see off the map.

    Outdoor maps in the corpus wall themselves: median lift of the outer 64 m is
    1,351 cm over the interior across 61 maps, and the flagships run 3,500-4,700.
    Interiors measure exactly 0 and use fog instead.

    ``max`` of the two axis ramps rather than their sum, so the wall has uniform
    height all the way round INCLUDING the corners -- a sum peaks at the corners
    and sags along the edges, which leaves a visible notch mid-edge where the
    player can see out. Smoothstepped, because a linear ramp reads as a
    perfectly conical embankment.
    """
    h, w = shape
    width_cells = max(2.0, width_m / 2.0)          # metres -> 2 m terrain cells
    ys = np.arange(h, dtype=np.float64)[:, None]
    xs = np.arange(w, dtype=np.float64)[None, :]

    dy = np.minimum(ys, (h - 1) - ys)
    dx = np.minimum(xs, (w - 1) - xs)
    ry = np.clip(1.0 - dy / width_cells, 0.0, 1.0)
    rx = np.clip(1.0 - dx / width_cells, 0.0, 1.0)
    ramp = np.maximum(rx, ry)
    ramp = ramp * ramp * (3.0 - 2.0 * ramp)

    # Break the wall into peaks and saddles. A pure ramp is a smooth conical
    # bowl, which reads as a crater rather than as a mountain range -- the
    # corpus rims are irregular, and the eye reads regularity as machine-made.
    if rng is not None:
        relief = fbm(rng, h, w, octaves=3, base_cells=40, gain=0.55)
        ramp = ramp * (0.62 + 0.76 * relief)

    out = ramp * float(lift_cm)

    # Cut a gorge where water leaves the map. Without this the rim lifts the
    # riverbed at the boundary and the river climbs the mountain: on the first
    # attempt it broke a continuous watercourse into three pieces at different
    # levels, each stepping UP toward the edge. Real maps let the valley through
    # the ring -- the wall stops the player, not the river.
    if gap is not None and gap.any():
        out = out * (1.0 - np.clip(gap, 0.0, 1.0))
    return out


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

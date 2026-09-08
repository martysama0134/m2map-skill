"""Stage 6 -- areadata.txt.

The placement grammar, as measured over all 48,774 shipped object records rather
than assumed. The rules the corpus actually supports:

* **Heading is roll, not yaw.** Yaw is zero in 96.4% of records corpus-wide
  (1,767 non-zero of 48,774; 94.2-99.7% per property type); it and pitch
  are tilt channels used almost exclusively by debris (3.6% overall, concentrated
  in ``snakevalley`` spear rocks and ``devils_dragon_island`` bone).
* **Everything snaps to 15 degrees.** Zero non-integer rolls in 48,774 records,
  99.7% multiples of 15, only 148 distinct values. Buildings additionally favour
  90/180/270 (29.5% of their non-zero rolls).
* **Trees are mostly unrotated**: roll is exactly 0 in 67% of ``tree/b1``, 60% of
  ``n2``, 83% of ``n1``. Forest variety comes from species mixing and
  ``TreeSize``/``TreeVariance``, not from yaw jitter -- a uniform-random heading
  reads as wrong.
* **Rocks sink.** Negative height bias is the norm for debris.

Coordinates: ``areadata.txt`` stores **map-local centimetres with Y negated**.
Tile space is 1 m, so ``x_cm = tile_x * 100`` and ``stored_y = -(tile_y * 100)``.
``BasePosition`` is NOT added -- that is the server's job, and adding it here
puts every object outside the map.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..codec import areadata as ad
from .layout import Layout
from .spec import MapSpec, ObjectTier, SECTOR_TILES, stream_seed

#: Heading snap, from the corpus: 99.7% of rolls are multiples of this.
ROLL_SNAP = 15.0

#: Families whose heading is essentially never randomised.
TREE_ZERO_ROLL_SHARE = 0.67
BUILDING_CARDINAL_SHARE = 0.30


class _Grid:
    """Uniform grid for Poisson-disk rejection -- O(1) neighbour queries."""

    def __init__(self, w: float, h: float, cell: float):
        self.cell = max(1.0, cell)
        self.cols = int(w / self.cell) + 1
        self.rows = int(h / self.cell) + 1
        self.buckets: Dict[Tuple[int, int], List[Tuple[float, float]]] = {}

    def add(self, x: float, y: float) -> None:
        self.buckets.setdefault((int(x / self.cell), int(y / self.cell)), []).append((x, y))

    def too_close(self, x: float, y: float, r: float) -> bool:
        cx, cy = int(x / self.cell), int(y / self.cell)
        span = int(r / self.cell) + 1
        r2 = r * r
        for gy in range(cy - span, cy + span + 1):
            for gx in range(cx - span, cx + span + 1):
                for px, py in self.buckets.get((gx, gy), ()):
                    if (px - x) ** 2 + (py - y) ** 2 < r2:
                        return True
        return False


def _sample_roll(rng, tier: ObjectTier) -> float:
    """Heading, following the measured per-family distribution."""
    fam = (tier.name or "").lower()
    is_tree = "tree" in fam or tier.tier == "filler" and "tree" in fam
    if is_tree and rng.random() < TREE_ZERO_ROLL_SHARE:
        return 0.0
    if "building" in fam or "house" in fam or "wall" in fam:
        if rng.random() < BUILDING_CARDINAL_SHARE:
            return float(rng.choice((90.0, 180.0, 270.0)))
    steps = int(360.0 / ROLL_SNAP)
    return float(rng.randrange(steps)) * ROLL_SNAP


def _candidate_mask(spec: MapSpec, lay: Layout, tier: ObjectTier,
                    tiles: np.ndarray, slope: np.ndarray,
                    submerged: np.ndarray, wet: np.ndarray = None) -> np.ndarray:
    """Where this prop is allowed to stand."""
    ok = np.ones(lay.shape, bool)

    if tier.on_tiles:
        allowed = np.zeros(lay.shape, bool)
        for t in tier.on_tiles:
            allowed |= tiles == t
        ok &= allowed

    ok &= slope <= tier.max_slope
    if submerged is not None:
        ok &= ~submerged
    # Vegetation in the shore band reads as trees growing in the river. Only
    # props that explicitly nominate the shore tile may stand there.
    if wet is not None and not tier.on_tiles:
        ok &= ~wet

    # Nothing stands on a road surface. Buildings sit beside one; trees keep
    # well clear -- the measured clearance is per-family, from the spec.
    ok &= ~lay.road_mask
    if tier.road_clearance_cm > 0 and lay.corridors:
        ok &= lay.road_distance >= (tier.road_clearance_cm / 100.0)

    # Distance to water, both directions. The corpus measures d(water) per CRC
    # and the two ends are genuinely different rules: desert flora keeps AWAY
    # (tree/n2 p50 20,009 cm) while oasis and shore decoration hugs the edge.
    lo, hi = tier.water_distance_m
    if (lo > 0 or hi != float("inf")) and wet is not None and wet.any():
        dist = _water_distance(wet)
        if lo > 0:
            ok &= dist >= lo
        if hi != float("inf"):
            ok &= dist <= hi

    # Keep placements off the sealed border band.
    b = max(1, int(spec.border_band_m))
    ok[:b, :] = ok[-b:, :] = False
    ok[:, :b] = ok[:, -b:] = False
    return ok


def build(spec: MapSpec, lay: Layout, height_cm: np.ndarray, slope_deg: np.ndarray,
          tiles: np.ndarray, submerged: Optional[np.ndarray] = None,
          wet: Optional[np.ndarray] = None, bbox_lookup=None):
    """Place every tier. Returns ``(records, footprints)``.

    ``records`` are whole-map :class:`ObjectRecord`s in map-local cm;
    ``footprints`` are ``(tile_x, tile_y, radius_tiles)`` for stage 7.
    ``bbox_lookup(crc) -> (sx, sy, sz) cm`` supplies real model extents from the
    catalog; without it, spacing falls back to the spec.
    """
    h, w = lay.shape
    rng = spec.rng("objects")
    np_rng = np.random.default_rng(stream_seed("objects", spec.seed))

    slope_t = _upsample(slope_deg, h, w)
    height_t = _upsample(height_cm, h, w)

    records: List[ad.ObjectRecord] = []
    footprints: List[Tuple[float, float, float]] = []
    #: (tier name, requested, placed, why) -- surfaced by the pipeline. Silent
    #: under-placement reads as "the density was applied" when in fact the
    #: filters left nowhere to stand.
    shortfalls: List[Tuple[str, int, int, str]] = []

    # Spacing is PER SPECIES, not global. A shared grid makes the largest
    # spacing on the map apply to every pair of objects, so a landmark with a
    # 30 m radius cannot be placed anywhere near a tree and silently drops out.
    # The corpus measures nearest-neighbour distance per CRC precisely because
    # different species interleave freely.
    own_grids: Dict[int, _Grid] = {}
    # One shared grid with a small radius stops different species occupying the
    # same square metre.
    overlap = _Grid(w, h, cell=4.0)
    OVERLAP_M = 1.5

    for tier in spec.objects:
        mask = _candidate_mask(spec, lay, tier, tiles, slope_t, submerged, wet)
        available = int(mask.sum())
        if available == 0:
            shortfalls.append((tier.name or str(tier.crc), tier.count or -1, 0,
                               "no candidate tiles: max_slope=%.0f, on_tiles=%s, "
                               "road_clearance=%.0fcm"
                               % (tier.max_slope, tier.on_tiles or "any",
                                  tier.road_clearance_cm)))
            continue

        spacing_cm = tier.spacing_cm
        if spacing_cm <= 0 and bbox_lookup is not None:
            box = bbox_lookup(tier.crc)
            if box:
                # Footprint radius from the model's own extent -- you cannot
                # space trees sensibly without knowing how wide they are.
                spacing_cm = max(box[0], box[1]) * 1.15
        spacing = max(0.5, spacing_cm / 100.0)

        if tier.count > 0:
            target = tier.count
        else:
            target = int(round(tier.density * available / 100.0))
        if target <= 0:
            continue

        ys, xs = np.nonzero(mask)

        # Clustering. A uniform candidate order plus a hard minimum distance
        # jams into a maximal packing -- a visibly regular lattice, which is the
        # opposite of the corpus (trees measure as clustered, not regular).
        # Weighting the order by a low-frequency field produces groves and
        # clearings, and leaves the spacing rule doing what it is for: stopping
        # trunks intersecting, not dictating the layout.
        from .terrain import fbm
        clump = fbm(np_rng, h, w, octaves=3, base_cells=40, gain=0.6)
        strength = 4.0 if tier.tier == "filler" else 1.0
        weight = (0.05 + clump[ys, xs]) ** strength
        weight = weight / weight.sum()
        take = min(len(xs), max(target * 40, target + 64))
        order = np_rng.choice(len(xs), size=take, replace=False, p=weight)
        placed = 0
        # Dart-throwing with a generous attempt budget: the acceptance rate
        # falls as the region fills, and stopping early silently under-populates.
        for i in order:
            if placed >= target:
                break
            tx = float(xs[i]) + float(np_rng.random())
            ty = float(ys[i]) + float(np_rng.random())
            own = own_grids.setdefault(tier.crc, _Grid(w, h, cell=max(4.0, spacing)))
            # Jittered radius: a single hard minimum distance packs into a
            # lattice. Real stands vary, and the corpus's nearest-neighbour
            # distribution has a long tail rather than a spike.
            r = spacing * (0.6 + 0.8 * float(np_rng.random()))
            if own.too_close(tx, ty, r):
                continue
            if overlap.too_close(tx, ty, OVERLAP_M):
                continue
            own.add(tx, ty)
            overlap.add(tx, ty)

            gz = float(height_t[min(h - 1, int(ty)), min(w - 1, int(tx))])
            bias_lo, bias_hi = tier.height_bias
            bias = bias_lo if bias_hi <= bias_lo else rng.uniform(bias_lo, bias_hi)

            records.append(ad.ObjectRecord(
                x=tx * 100.0,
                y=-(ty * 100.0),           # areadata stores Y NEGATED
                z=gz,
                crc=tier.crc,
                yaw=0.0, pitch=0.0,        # heading lives in roll
                roll=_sample_roll(rng, tier),
                height_bias=round(bias, 6),
            ))
            placed += 1

            box = bbox_lookup(tier.crc) if bbox_lookup else None
            if box and tier.tier != "accent":
                radius = max(box[0], box[1]) / 200.0     # cm -> tiles, halved
                if radius >= 1.0:
                    footprints.append((tx, ty, radius))

        if placed < target:
            shortfalls.append((
                tier.name or str(tier.crc), target, placed,
                "%d of %d placed -- %d candidate tiles at %.1f m spacing is not "
                "enough room" % (placed, target, available, spacing)))

    return records, footprints, shortfalls


def _upsample(grid: np.ndarray, h: int, w: int) -> np.ndarray:
    gh, gw = grid.shape
    ys = np.clip((np.arange(h) * gh) // max(1, h), 0, gh - 1)
    xs = np.clip((np.arange(w) * gw) // max(1, w), 0, gw - 1)
    return grid[np.ix_(ys, xs)]


def _water_distance(wet: np.ndarray, cap: float = 260.0) -> np.ndarray:
    """Distance in tiles (metres) to the nearest wet cell, capped.

    Vectorised dilation rather than a per-cell chamfer: each step is one numpy
    pass, and the loop stops at ``cap``, so a 1024x1024 map costs the same as a
    256x256 one for the same threshold. Cells beyond the cap read as ``cap``,
    which is fine because every rule using this is a threshold, not a metric --
    "at least 200 m from water" does not care whether the true answer is 300 or
    3,000.
    """
    if not wet.any():
        return np.full(wet.shape, cap, np.float32)
    d = np.where(wet, 0.0, np.inf).astype(np.float32)
    frontier = wet.copy()
    step = 0.0
    while step < cap:
        step += 1.0
        grown = frontier.copy()
        grown[1:, :] |= frontier[:-1, :]
        grown[:-1, :] |= frontier[1:, :]
        grown[:, 1:] |= frontier[:, :-1]
        grown[:, :-1] |= frontier[:, 1:]
        new = grown & ~np.isfinite(d)
        if not new.any():
            break
        d[new] = step
        frontier = grown
    d[~np.isfinite(d)] = cap
    return d


def split_by_sector(records: Sequence[ad.ObjectRecord], spec: MapSpec
                    ) -> Dict[Tuple[int, int], List[ad.ObjectRecord]]:
    """Bucket records into their sectors.

    Y is de-negated first: a record at stored y=-30000 lives in sector row 1,
    not row -2. This is the single easiest place to mirror an entire object
    layer about the X axis without noticing.
    """
    out: Dict[Tuple[int, int], List[ad.ObjectRecord]] = {}
    edge = SECTOR_TILES * 100.0
    for rec in records:
        cx = int(rec.x // edge)
        cy = int((-rec.y) // edge)
        cx = min(max(cx, 0), spec.size[0] - 1)
        cy = min(max(cy, 0), spec.size[1] - 1)
        out.setdefault((cx, cy), []).append(rec)
    return out


def stats(records: Sequence[ad.ObjectRecord]) -> dict:
    if not records:
        return {"count": 0}
    rolls = [r.roll for r in records]
    snapped = sum(1 for r in rolls if abs(r / ROLL_SNAP - round(r / ROLL_SNAP)) < 1e-6)
    return {
        "count": len(records),
        "distinct_crcs": len({r.crc for r in records}),
        "roll_snap_15_share": round(snapped / len(rolls), 4),
        "roll_zero_share": round(sum(1 for r in rolls if r == 0.0) / len(rolls), 4),
        "yaw_nonzero_share": round(
            sum(1 for r in records if r.yaw) / len(records), 4),
        "all_y_negative": all(r.y <= 0 for r in records),
    }

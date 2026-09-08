"""Stage 2 -- the layout graph.

Roads, rivers and region polygons live here at full precision, independent of
grid resolution; every later stage rasterises from them. Widening a road is a
parameter change on a spline, not a raster edit that has to be undone first.

Coordinates are **tile space**: 1 tile = 1 m = 100 world units, origin at the
map's north-west corner, y growing south. That matches ``tile.raw`` and
``attr.atr`` directly and is half the terrain-cell pitch, which is deliberate --
the corpus paints its splat at 1 m, not at the 2 m cell (measured
``transition_odd_x_bias`` 0.499 across all 114 maps).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

import numpy as np

from .spec import MapSpec, SECTOR_CELLS, SECTOR_TILES

Point = Tuple[float, float]


def catmull_rom(points: Sequence[Point], samples_per_span: int = 24,
                closed: bool = False) -> List[Point]:
    """Smooth centreline through the waypoints.

    Catmull-Rom passes *through* its control points, which is what a map author
    means by "the road goes here". A Bezier would treat them as pulls and drift
    off the intended route.
    """
    pts = [tuple(map(float, p)) for p in points]
    if len(pts) < 2:
        return pts
    if closed:
        pts = [pts[-1]] + pts + [pts[0], pts[1]]
    else:
        pts = [pts[0]] + pts + [pts[-1]]

    out: List[Point] = []
    for i in range(len(pts) - 3):
        p0, p1, p2, p3 = pts[i:i + 4]
        for s in range(samples_per_span):
            t = s / samples_per_span
            t2, t3 = t * t, t * t * t
            out.append((
                0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t +
                       (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
                       (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3),
                0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t +
                       (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
                       (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3),
            ))
    out.append(tuple(pts[-2]))
    return out


def distance_field(shape: Tuple[int, int], polyline: Sequence[Point]) -> np.ndarray:
    """Distance in tiles from every cell to the polyline.

    Exact segment distance rather than a chamfer approximation: corridor edges
    and clearance rules both read this, and a 1-2 tile error there is a visible
    kink in a 5 m road.
    """
    h, w = shape
    ys, xs = np.mgrid[0:h, 0:w]
    best = np.full((h, w), np.inf)
    for (x0, y0), (x1, y1) in zip(polyline, polyline[1:]):
        dx, dy = x1 - x0, y1 - y0
        seg2 = dx * dx + dy * dy
        if seg2 < 1e-9:
            d = np.hypot(xs - x0, ys - y0)
        else:
            t = np.clip(((xs - x0) * dx + (ys - y0) * dy) / seg2, 0.0, 1.0)
            d = np.hypot(xs - (x0 + t * dx), ys - (y0 + t * dy))
        np.minimum(best, d, out=best)
    return best


def polygon_mask(shape: Tuple[int, int], polygon: Sequence[Point]) -> np.ndarray:
    """Even-odd fill, no dependencies."""
    h, w = shape
    mask = np.zeros((h, w), bool)
    if len(polygon) < 3:
        return mask
    poly = [tuple(map(float, p)) for p in polygon]
    ys = np.arange(h) + 0.5
    for i, y in enumerate(ys):
        xs: List[float] = []
        for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
            if (y0 <= y < y1) or (y1 <= y < y0):
                xs.append(x0 + (y - y0) / (y1 - y0) * (x1 - x0))
        xs.sort()
        for a, b in zip(xs[::2], xs[1::2]):
            lo, hi = int(np.ceil(a - 0.5)), int(np.floor(b - 0.5))
            if hi >= lo:
                mask[i, max(0, lo):min(w, hi + 1)] = True
    return mask


def _distance_to(mask: np.ndarray, cap: float = 48.0) -> np.ndarray:
    """Distance in tiles from every cell to the nearest masked cell."""
    if not mask.any():
        return np.full(mask.shape, cap, np.float32)
    d = np.where(mask, 0.0, np.inf).astype(np.float32)
    frontier = mask.copy()
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


def _distance_inside(mask: np.ndarray, cap: float = 64.0) -> np.ndarray:
    """Distance in tiles from each masked cell to the nearest cell outside it.

    Used to grade a river or lake bed: deepest in the middle, zero at the shore.
    Capped dilation, so a wide lake costs the same as a narrow stream.
    """
    inside = mask.copy()
    dist = np.zeros(mask.shape, np.float32)
    step = 0.0
    while step < cap and inside.any():
        step += 1.0
        eroded = inside.copy()
        eroded[1:, :] &= inside[:-1, :]
        eroded[:-1, :] &= inside[1:, :]
        eroded[:, 1:] &= inside[:, :-1]
        eroded[:, :-1] &= inside[:, 1:]
        if not eroded.any():
            break
        dist[eroded] = step
        inside = eroded
    return dist


@dataclass
class Corridor:
    """A rasterised road: its centreline, its surface and its blend fringe."""

    centreline: List[Point]
    core: np.ndarray            # tiles to paint with the corridor texture
    fringe: np.ndarray          # 1-2 m transition band
    distance: np.ndarray        # tiles from the centreline
    tile_index: int
    width_m: float


@dataclass
class Plaza:
    """A rasterised safe-zone disc. See :class:`spec.PlazaSpec` for the shape
    evidence -- this is only the mask."""

    mask: np.ndarray
    tile_index: int
    safezone: bool
    centre: Point
    radius_m: float


@dataclass
class Layout:
    """Everything stage 2 produces, in tile space."""

    shape: Tuple[int, int]                       # (h, w) tiles
    corridors: List[Corridor] = field(default_factory=list)
    water_masks: List[np.ndarray] = field(default_factory=list)
    water_surfaces: List[float | None] = field(default_factory=list)
    #: Centreline per water feature (empty for a lake). Water bands ALONG this,
    #: not by height value -- see gen/water.py.
    water_lines: List[List[Point]] = field(default_factory=list)
    regions: Dict[str, np.ndarray] = field(default_factory=dict)
    plazas: List[Plaza] = field(default_factory=list)
    flatten: np.ndarray | None = None            # tile-space flatten request
    #: Depth in cm to cut out of the terrain under each water body, graded to 0
    #: at the shoreline. Without a carved bed the water renders as a flat slab
    #: lying on top of the ground instead of sitting in a channel.
    carve_cm: np.ndarray | None = None
    #: True where the water body is a lake (one flat surface, not banded).
    lake_mask: np.ndarray | None = None
    #: 0..1 suppression of the border ridge, so water can leave the map.
    ridge_gap: np.ndarray | None = None

    @property
    def road_mask(self) -> np.ndarray:
        m = np.zeros(self.shape, bool)
        for c in self.corridors:
            m |= c.core
        return m

    @property
    def road_distance(self) -> np.ndarray:
        """Distance to the nearest corridor centreline; inf when there are none."""
        if not self.corridors:
            return np.full(self.shape, np.inf)
        out = self.corridors[0].distance.copy()
        for c in self.corridors[1:]:
            np.minimum(out, c.distance, out=out)
        return out

    @property
    def water_mask(self) -> np.ndarray:
        m = np.zeros(self.shape, bool)
        for w in self.water_masks:
            m |= w
        return m

    def flatten_mask_cells(self) -> np.ndarray:
        """Tile-space flatten request downsampled to the terrain vertex grid.

        Terrain works on 2 m cells, the layout on 1 m tiles, so this halves the
        resolution. Using ``any`` rather than a majority keeps a 3 m road from
        vanishing when it straddles the cell boundary.
        """
        h, w = self.shape
        src = self.flatten if self.flatten is not None else np.zeros((h, w), bool)
        ch, cw = h // 2 + 1, w // 2 + 1
        out = np.zeros((ch, cw), bool)
        block = src[:(h // 2) * 2, :(w // 2) * 2].reshape(h // 2, 2, w // 2, 2)
        out[:h // 2, :w // 2] = block.any(axis=(1, 3))
        return out

    def pad_masks_cells(self) -> List[np.ndarray]:
        """Plaza discs on the terrain vertex grid, one mask each.

        Separate from ``flatten_mask_cells`` because the two want different
        treatment: a road is SMOOTHED so it follows the ground, a plaza is
        LEVELLED so it does not. Sharing one mask gave a disc of mean slope
        9.0 deg where the corpus measures 0.0-1.9.
        """
        h, w = self.shape
        ch, cw = h // 2 + 1, w // 2 + 1
        out: List[np.ndarray] = []
        for pz in self.plazas:
            m = np.zeros((ch, cw), bool)
            block = pz.mask[:(h // 2) * 2, :(w // 2) * 2].reshape(h // 2, 2, w // 2, 2)
            m[:h // 2, :w // 2] = block.any(axis=(1, 3))
            if m.any():
                out.append(m)
        return out


def build(spec: MapSpec) -> Layout:
    shape = (spec.height_tiles, spec.width_tiles)
    lay = Layout(shape=shape)
    flatten = np.zeros(shape, bool)

    for road in spec.roads:
        line = catmull_rom(road.waypoints, closed=road.closed)
        dist = distance_field(shape, line)
        half = max(0.5, road.width_m / 2.0)
        core = dist <= half
        fringe = (dist > half) & (dist <= half + 1.5)
        lay.corridors.append(Corridor(centreline=line, core=core, fringe=fringe,
                                      distance=dist, tile_index=road.tile_index,
                                      width_m=road.width_m))
        # Flatten wider than the surface so the road does not sit in a trench
        # with abrupt shoulders. The corpus blend band is median 3 m, so a
        # shoulder of about that width is what the paint expects to find.
        flatten |= dist <= (half + 3.0)

    carve = np.zeros(shape, np.float64)
    lakes = np.zeros(shape, bool)

    for wat in spec.water:
        if wat.lake:
            mask = polygon_mask(shape, wat.waypoints)
            lakes |= mask
            line = []
        else:
            line = catmull_rom(wat.waypoints)
            mask = distance_field(shape, line) <= max(0.5, wat.width_m / 2.0)
        lay.water_masks.append(mask)
        lay.water_lines.append(line)
        lay.water_surfaces.append(wat.surface_z)

        # Cut a bed, graded from 0 at the shoreline to `depth` in the middle, so
        # the banks rise around the water instead of the water lying on flat
        # ground. The grading also hides the level steps of a banded river:
        # a step inside a channel reads as a riffle, the same step on an open
        # plain reads as a terrace.
        if mask.any():
            # A lake carries no `width_m` -- it is a polygon -- so both the depth
            # and the grading scale have to come from its own area, or the
            # expression below degenerates. With `width_m` 0 the depth clamped to
            # its 120 cm floor and `clip(inner / max(1, 0))` saturated at the
            # first tile inside the shore, which cut a flat pan with vertical
            # walls: in the editor the waterline came out as a visible staircase
            # instead of a beach.
            eff_w = wat.width_m
            if eff_w <= 0.0:
                eff_w = 2.0 * float(np.sqrt(mask.sum() / np.pi))
            depth = max(120.0, min(600.0, eff_w * 22.0))
            inner = _distance_inside(mask)
            grade = np.clip(inner / max(1.0, eff_w * 0.35), 0.0, 1.0)
            carve = np.maximum(carve, grade * depth * mask)

    lay.carve_cm = carve
    lay.lake_mask = lakes

    # Where water meets the map edge the rim must open into a gorge, or the
    # ridge lifts the bed and the river runs uphill off the map. Widened well
    # past the channel so the opening has shoulders rather than a slot.
    gap = np.zeros(shape, np.float64)
    for mask, wat in zip(lay.water_masks, spec.water):
        if not mask.any():
            continue
        # ONLY for water that actually reaches the map edge. The rim opens so a
        # river can leave; a body that stays inside has nothing to leave through,
        # and suppressing the ridge around it erases the very high ground the
        # feature was placed against. Measured: a basin sited on the east rim to
        # hold the top of a waterfall came back with its ground at 16,064 cm --
        # the plateau floor -- because the gap had levelled the 31 m of rim
        # underneath it.
        touches_edge = (mask[0, :].any() or mask[-1, :].any() or
                        mask[:, 0].any() or mask[:, -1].any())
        if not touches_edge:
            continue
        reach = max(6.0, wat.width_m * 1.6)
        d = _distance_to(mask)
        gap = np.maximum(gap, np.clip(1.0 - d / reach, 0.0, 1.0))

    # Roads need a pass through the wall for the same reason water needs a
    # gorge. Corpus roads run off the map edge -- that is how a route continues
    # onto the neighbouring map -- and without this the ridge is added after the
    # corridor is levelled and simply buries it: measured road slope 14.9 deg
    # against 6.4 deg for the same corridor on the map interior.
    #
    # Only PARTIAL suppression, unlike water. A river must reach the edge at bed
    # level or it runs uphill; a road only has to be passable, and the corpus
    # keeps its horizon walled (taste.md sec "Every map occludes its horizon").
    # 0.65 opens a saddle in the wall rather than a hole through it.
    for corr in lay.corridors:
        reach = max(12.0, corr.width_m * 2.5)
        gap = np.maximum(gap, 0.65 * np.clip(1.0 - corr.distance / reach, 0.0, 1.0))

    lay.ridge_gap = gap

    for reg in spec.regions:
        mask = polygon_mask(shape, reg.polygon)
        prev = lay.regions.get(reg.kind)
        lay.regions[reg.kind] = mask if prev is None else (prev | mask)
        if reg.flatten:
            flatten |= mask

    # Plazas last, so a disc laid over a road wins: the corpus paints the
    # junction disc on top of the road web, never the other way round.
    for pz in spec.plazas:
        cx, cy = pz.centre
        ys, xs = np.ogrid[:shape[0], :shape[1]]
        mask = (xs - cx) ** 2 + (ys - cy) ** 2 <= pz.radius_m ** 2
        if not mask.any():
            continue
        lay.plazas.append(Plaza(mask=mask, tile_index=pz.tile_index,
                                safezone=pz.safezone, centre=(cx, cy),
                                radius_m=pz.radius_m))
        # Flat, and flat past the rim -- measured slope under the shipped discs
        # is 0.0-1.9 deg, and a disc on a slope reads as a decal.
        flatten |= ((xs - cx) ** 2 + (ys - cy) ** 2
                    <= (pz.radius_m + 3.0) ** 2)

    lay.flatten = flatten
    return lay

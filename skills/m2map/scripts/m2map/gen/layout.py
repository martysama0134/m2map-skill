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
from typing import Optional, Dict, List, Sequence, Tuple

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


def _signed_distance(shape: Tuple[int, int],
                     polyline: Sequence[Point]) -> np.ndarray:
    """Distance to the polyline, negative on its left and positive on its right.

    The sign is taken from the cross product with the segment that is nearest,
    which is what lets a scarp leave one side of a line standing.
    """
    h, w = shape
    ys, xs = np.mgrid[0:h, 0:w]
    best = np.full((h, w), np.inf)
    sign = np.ones((h, w))
    for (x0, y0), (x1, y1) in zip(polyline, polyline[1:]):
        dx, dy = x1 - x0, y1 - y0
        seg2 = dx * dx + dy * dy
        if seg2 < 1e-9:
            continue
        t = np.clip(((xs - x0) * dx + (ys - y0) * dy) / seg2, 0.0, 1.0)
        px, py = x0 + t * dx, y0 + t * dy
        d = np.hypot(xs - px, ys - py)
        cross = dx * (ys - y0) - dy * (xs - x0)
        closer = d < best
        sign = np.where(closer, np.where(cross >= 0, 1.0, -1.0), sign)
        np.minimum(best, d, out=best)
    return best * sign


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


#: Open ground kept on each side of a road's painted core, metres.
ROAD_SHOULDER_M = 2.5

#: How far inside the stated lip a bridge's gorge wall starts, metres -- what
#: max-pooling the cut onto the 2 m vertex grid gives back. Calibrated by walking
#: the axis of built bridges the way the corpus ones were measured.
LIP_POOL_M = 1.25


@dataclass
class BridgeFit:
    """A `BridgeSpec` rasterised: where to level, where to cut, where to walk."""

    spec: object
    model: dict
    #: 0..1 pull toward the bank height: the two approaches and the abutments
    bank_weight: np.ndarray
    #: the solid core of the two approaches, for reading the bank level back
    bank_core: np.ndarray
    #: 0..1 pull DOWN to the bed: 1 across the gap, ramped at the two walls,
    #: faded along the river so the cut joins the channel
    cut_weight: np.ndarray
    #: the walkable deck
    deck: np.ndarray
    #: the stated surface of the water under mid-span, if it has one
    water_cm: Optional[float] = None
    #: filled in by the terrain stage
    bank_cm: float = 0.0


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
    #: Height to subtract for each scarp face, cm, in tile space.
    scarp_cm: np.ndarray | None = None
    #: ``(weight, target_cm)`` per crest-driven scarp: pull the terrain toward
    #: ``target_cm`` with weight in [0, 1]. Tile space.
    benches: List[Tuple[np.ndarray, float]] = field(default_factory=list)
    #: True where the water body is a lake (one flat surface, not banded).
    lake_mask: np.ndarray | None = None
    #: ``(grade, surface_cm, depth_cm)`` per river with a STATED surface: the
    #: bed is cut to an absolute level under it, not relative to the ground it
    #: crosses. Tile space; ``grade`` is 0 at the shore and 1 mid-channel.
    channels: List[Tuple[np.ndarray, float, float]] = field(default_factory=list)
    #: One per `BridgeSpec` -- the masks its terrain fit and attr need.
    bridges: List["BridgeFit"] = field(default_factory=list)
    #: 0..1 suppression of the border ridge, so water can leave the map.
    ridge_gap: np.ndarray | None = None
    #: `IslandsSpec` rasterised: the 0..1 wall profile on the terrain VERTEX
    #: grid (1 = a top, 0 = the canyon bed), and in tile space everything that
    #: is not a top. None without islands. See `gen/islands.py`.
    island_t: np.ndarray | None = None
    void: np.ndarray | None = None
    #: cm to add along the lips of the tops -- the rock berm. Vertex grid.
    island_berm: np.ndarray | None = None

    @property
    def road_mask(self) -> np.ndarray:
        m = np.zeros(self.shape, bool)
        for c in self.corridors:
            m |= c.core
        return m

    @property
    def road_clear(self) -> np.ndarray:
        """The road AND its shoulder: what collision and the rock skin both keep
        off. `ROAD_SHOULDER_M` past the painted core on each side.

        Opening only the core left a road through a rock hump as a 5 m slot
        between saw-toothed block, with the block standing on the road's own
        dithered rim where no stone is painted. In the corpus block never runs
        ahead of the rock toward a road: by distance from the road paint,
        `map_a2` measures rock 20.6 / 24.5 / 28.8 / 35.3% against block
        19.3 / 21.4 / 24.6 / 30.9% (1-2, 2-3, 3-5, 5-8 m), and
        `metin2_map_n_desert_01` is 2% blocked anywhere inside 5 m.
        """
        m = np.zeros(self.shape, bool)
        for c in self.corridors:
            m |= c.distance <= (max(0.5, c.width_m / 2.0) + ROAD_SHOULDER_M)
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
            if wat.surface_z is not None and not wat.lake:
                # A river with a STATED level is a moat: one flat surface, so the
                # bed has to be absolute too. Carved relative to the ground it
                # crosses, the channel climbs every rise with it and the single
                # plane is buried on the hills and floods the hollows. On
                # `metin2_map_a1` the river is one level (15,305 cm) under four
                # of its seven bridges; it is the BANKS that vary.
                lay.channels.append((grade * mask, float(wat.surface_z), depth))
            else:
                carve = np.maximum(carve, grade * depth * mask)

    # Bridges. In span coordinates: s along the deck from mid-span, t along the
    # river. See `BridgeSpec` for the measurements behind each number.
    if spec.bridges:
        from .spec import BRIDGE_MODELS
        ys, xs = np.mgrid[0:shape[0], 0:shape[1]]
        for br in spec.bridges:
            m = BRIDGE_MODELS[br.model]
            dx, dy = br.span_dir()
            px, py = xs + 0.5 - br.centre[0], ys + 0.5 - br.centre[1]
            s_ = px * dx + py * dy
            t_ = -px * dy + py * dx
            deck_s, deck_t = np.abs(s_), np.abs(t_)       # the deck is tile space, as is
            # The terrain weights are pooled onto the 2 m vertex grid, and vertex
            # v takes tiles 2v and 2v+1 -- centred a metre PAST the vertex. Left
            # alone, every lip lands 1 m toward the map origin: a span reaching
            # south or east sat 2 m further onto its far bank than one reaching
            # north or west. Sample a metre back so the pool is centred.
            px, py = px - 1.0, py - 1.0
            s_ = px * dx + py * dy
            t_ = -px * dy + py * dx
            half = m["length_cm"] / 200.0
            wid = m["width_cm"] / 200.0
            # The bank reaches full height at the lip, and the two lips are not
            # the same distance from mid-span on a rope bridge: `s_` runs from the
            # ORIGIN end (-half) to the far end (+half). See `BRIDGE_MODELS`.
            lip = np.where(s_ < 0.0,
                           half - m.get("lip_inset_near_m", m["lip_inset_m"]),
                           half - m.get("lip_inset_far_m", m["lip_inset_m"]))
            a_s, a_t = np.abs(s_), np.abs(t_)
            # banks: from the lip out to the end of the approach, a road-and-a-bit wide
            # `LIP_POOL_M`: the pool takes the MAX, so the cut spreads a vertex
            # outward; the wall starts that much inside the lip it is meant to leave
            # Under a rounded lip the bank is set all the way down the curve, so
            # the wall falls from the BANK level and not from whatever relief the
            # top happened to have there -- the cut below takes it back out.
            pool = float(m["lip_round_m"]) if "lip_round_m" in m else LIP_POOL_M
            along = np.clip((a_s - (lip - pool - 1.0)) / 1.0, 0.0, 1.0) * \
                np.clip((half + br.approach_m + 8.0 - a_s) / 8.0, 0.0, 1.0)
            across = np.clip((wid + 10.0 - a_t) / 6.0, 0.0, 1.0)
            bank_w = along * across
            core = (a_s >= lip) & (a_s <= half + br.approach_m) & (a_t <= wid + 2.0)
            # the cut: walls ramp over 3 m inside the lip, and the gorge runs
            # along the river well past the deck before it fades
            if "lip_round_m" in m:
                # a rope bridge's lip is rounded: see `BRIDGE_MODELS`
                wall = np.clip((lip - a_s) / float(m["lip_round_m"]), 0.0, 1.0) ** 2
            else:
                wall = np.clip((lip - LIP_POOL_M - a_s) / 3.0, 0.0, 1.0)
            run = np.clip((wid + 40.0 - a_t) / 24.0, 0.0, 1.0)
            cut_w = wall * run
            deck = (deck_s <= half) & (deck_t <= max(1.0, wid - 1.0))
            under = None
            cy_, cx_ = int(br.centre[1]), int(br.centre[0])
            for wmask, wsurf in zip(lay.water_masks, lay.water_surfaces):
                if wsurf is not None and wmask[cy_, cx_]:
                    under = float(wsurf)
                    break
            lay.bridges.append(BridgeFit(spec=br, model=m, bank_weight=bank_w,
                                         bank_core=core, cut_weight=cut_w, deck=deck,
                                         water_cm=under))

    # Scarps: a signed cut that leaves one side of a line standing and drops the
    # other. Signed distance comes from the cross product against the nearest
    # segment, so "which side" follows the direction of travel -- the face looks
    # to the right of the line.
    scarp = np.zeros(shape, np.float64)
    for sc in spec.scarps:
        line = catmull_rom(sc.waypoints)
        if len(line) < 2:
            continue
        sd = _signed_distance(shape, line)
        run = max(0.5, sc.run_m)
        reach = max(run, sc.reach_m)
        # 0 on the standing side, 1 across the face, then held out to `reach`
        # and faded back so the cut does not end in a step of its own.
        if sc.crest_cm is not None:
            # Crest-driven: raise the STANDING side (sd < 0) to an absolute
            # height and leave the falling side alone. Full weight within the
            # run, blending back to natural terrain by `reach`. Not touching the
            # falling side is the point -- it is what keeps a lake sitting
            # beside the face from being deepened, and so keeps the water level
            # the crest was chosen against.
            # Full weight AT the line, blending back to natural terrain over
            # `reach` going into the standing side. `run` plays no part here:
            # the face is the step across the line itself, from untouched ground
            # on one side to the crest on the other, which is the steepest a
            # heightfield can be.
            #
            # Behind the crest the ground returns to whatever it was -- on a
            # border rim that means a ledge at the crest with the rim rising
            # again behind it, which is what a waterfall lip looks like and
            # leaves the horizon still walled.
            weight = np.where(sd <= 0.0,
                              np.clip(1.0 + sd / max(1e-6, reach), 0.0, 1.0),
                              0.0)
            if weight.any():
                lay.benches.append((weight, float(sc.crest_cm)))
            # and FALL THROUGH: the drop still digs the falling side. Capping
            # the crest without it leaves no face at all -- the basin is what
            # gives the wall its height, and skipping it put the pool back up
            # at the natural floor with a 1.4 m step in front of it.
        t = np.clip(sd / run, 0.0, 1.0)
        fade = np.clip(1.0 - (sd - run) / max(1e-6, reach - run), 0.0, 1.0)
        fade = np.where(sd <= run, 1.0, fade)
        scarp = np.maximum(scarp, sc.drop_cm * t * fade)
    lay.scarp_cm = scarp

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

    if getattr(spec, "islands", None) is not None:
        from . import islands
        lay.island_t, _rim = islands.profile(spec)
        lay.void = islands.void_tiles(lay.island_t, shape)
        # no rock on a road, a plaza or a set-piece's pad: all three are in
        # `flatten`, and the berm goes on after they were levelled
        lay.island_berm = islands.berm(
            spec, _distance_to(flatten, cap=16.0) if flatten.any() else None)
    return lay

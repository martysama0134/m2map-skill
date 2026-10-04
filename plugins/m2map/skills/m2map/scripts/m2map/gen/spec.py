"""``mapspec`` -- the contract between intent and generation.

The model turns a free-text request into one of these, shows it to the user, and
only then builds. Everything downstream reads the spec and nothing else, so a
map is reproducible from ``(spec, seed)`` and an ``improve`` is a spec diff.

The spec is deliberately explicit: every taste decision it encodes -- palette
roles, object densities, attr policy -- is a value a human can argue with before
a byte is written, rather than a judgement buried in a generator.

Stored as YAML when PyYAML is available, JSON otherwise; both load through
:func:`load`.
"""

from __future__ import annotations

import json
import math
import pathlib
import random
import zlib
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:                                     # optional -- JSON is the fallback
    import yaml                          # type: ignore
except ImportError:                      # pragma: no cover
    yaml = None

#: World geometry, fixed by the engine (see reference/mental-model.md).
CELL_SCALE = 200          # world units per terrain cell
HEIGHT_SCALE = 0.5        # raw uint16 -> world cm
SECTOR_CELLS = 128        # terrain cells per sector axis
SECTOR_TILES = 256        # 1 m tiles per sector axis

#: Saved set-piece patterns (`gen/setpiece.py`, `reference/setpieces/README.md`).
SETPIECE_DIR = pathlib.Path(__file__).resolve().parents[3] / "reference" / "setpieces"


def resolve_pattern(name) -> Optional[pathlib.Path]:
    """A pattern by bare name under `reference/setpieces/` (`desert_camp`), by
    file name (`desert_camp.json`) or by path. None when nothing is there."""
    cand = [pathlib.Path(str(name))]
    if not str(name).lower().endswith(".json"):
        cand.append(pathlib.Path(str(name) + ".json"))
    cand += [SETPIECE_DIR / c.name for c in list(cand)]
    for c in cand:
        if c.is_file():
            return c
    return None
SECTOR_UNITS = SECTOR_CELLS * CELL_SCALE   # 25,600 cm

#: A map's origin must be a multiple of this (four maps in the corpus violate
#: it; the editor still writes multiples of 25,600).
BASE_ALIGN = SECTOR_UNITS


def stream_seed(salt: str, seed: int) -> int:
    """A stable 32-bit seed for one generation stage.

    NOT ``hash()``. Python salts the hash of str and bytes per process
    (PYTHONHASHSEED), so ``hash(("terrain", seed))`` returns a different value
    in every run -- which silently made the whole generator non-reproducible
    across processes while looking deterministic inside one. Measured before the
    fix: the same spec built in three processes gave three different maps.

    crc32 is stable across processes, versions and platforms, which is what a
    seed has to be if a mapspec is going to mean anything.
    """
    return zlib.crc32(("%s/%d" % (salt, int(seed))).encode("utf-8")) & 0xFFFFFFFF


class SpecError(ValueError):
    """The spec cannot produce a loadable map."""


@dataclass
class TextureSlot:
    """One entry in the generated textureset.

    ``role`` is advisory and MULTI-VALUED in the catalog: the corpus has no road
    texture, so the same ``field`` texture is ground in one map and the road
    surface in another. The generator picks by role but a texture may carry
    several.
    """

    path: str
    role: str = "base"
    u_scale: float = 4.0
    v_scale: float = 4.0
    #: Relative weight in the stipple field. Ignored for `path`/`shore`, which
    #: are painted as solid features from the layout splines.
    weight: float = 1.0
    #: Paint this slot as the dithered RIM of another slot (1-based index), not
    #: as ground of its own.
    #:
    #: This is how a hand-painted oasis is built: one green (`grass 02`) laid as
    #: a carpet, and the damp sand (`sand02`) only in the band where the green
    #: gives way -- not at the waterline, and not as a texture in its own right.
    #: The bed keeps the base sand. A slot painted this way needs no weight of
    #: its own; `fringe_width_m` sets how far the band reaches.
    fringe_of: int = 0
    #: Width of that band in metres, and the odds a tile inside it takes this
    #: slot rather than the one it fringes.
    fringe_width_m: float = 4.0
    fringe_mix: float = 0.55
    #: Confine this slot to a named `RegionSpec.kind`. Empty = the whole map.
    #:
    #: An `accent` with no region is sprinkled over everything the role allows,
    #: which for grass on a desert means green flecks across open sand from one
    #: side of the map to the other. Grass belongs to the oasis; naming the
    #: region says so, instead of relying on a suitability term to imply it.
    region: str = ""


@dataclass
class ObjectTier:
    """A slice of the object palette.

    Tiers exist because real maps are not one uniform scatter: a handful of
    signature props define the biome, a bulk filler sets the density, and rare
    accents break the monotony.
    """

    crc: int
    name: str = ""
    #: signature | filler | accent
    tier: str = "filler"
    #: For authored `positions` only: hang the prop at this absolute height
    #: (world cm) instead of a bias over the ground -- `height_bias` becomes
    #: `absolute_z - ground`. A bridge is fitted to its banks, not to the river
    #: bed under its origin: two `a1-024` placements store biases of 0 and -290
    #: and land on the same datum to 3 cm.
    absolute_z: Optional[float] = None
    #: stamp the model's rectangle into attr.atr (authored buildings). False for
    #: a bridge, whose deck is the one place the player must be able to walk.
    footprint: bool = True
    #: placements per 100 m^2 (0 for `count`-driven props)
    density: float = 0.0
    #: exact number to place, when the prop is a landmark rather than scatter
    count: int = 0
    #: minimum centre-to-centre spacing, cm. Falls back to the catalog bbox.
    spacing_cm: float = 0.0
    #: tile indices this prop may stand on; empty = any non-path tile
    on_tiles: List[int] = field(default_factory=list)
    #: maximum ground slope in degrees
    max_slope: float = 25.0
    #: Exact placements, in map-local tile coordinates (1 tile = 1 m, y-down).
    #: Either ``(x, y)`` or ``(x, y, roll)`` -- the three-tuple carries its own
    #: heading, which is what a curving run needs: every panel of an arc points
    #: a different way, so a single :attr:`roll_deg` cannot express one.
    #:
    #: When set, the prop is placed HERE and every candidate filter above is
    #: skipped -- slope, water distance, road clearance, spacing.
    #:
    #: Landmarks are authored, not scattered, and a waterfall is the clearest
    #: case: it has to hang at the lip of the basin that feeds it, and no
    #: combination of "steep" and "near water" can say WHICH water. Constrained
    #: placement put one at the foot of the drop, beside the lower pool, 23 m
    #: below the tarn it was supposed to fall from.
    positions: List[Tuple[float, float]] = field(default_factory=list)
    #: Explicit heading in degrees, written straight into `roll`. Overrides both
    #: the per-family sampler and `align_to_slope`.
    #:
    #: For an authored landmark the heading is part of the placement, not a
    #: sample from a distribution: a warp gate has to face the road it stands on,
    #: and a random rung of the 15 degree ladder gives the player its side.
    #: `None` keeps the sampled behaviour.
    roll_deg: Optional[float] = None
    #: Turn the prop to face down the slope it stands on, instead of taking a
    #: heading from the 15 deg ladder. For anything that has to read as attached
    #: to a face -- a waterfall above all -- a random heading puts the visible
    #: side into the rock. `fall_7`'s roll is zero in only **13.6%** of its 44
    #: placements against 90.2% for Effects as a class, so it IS deliberately
    #: turned; measured against the terrain gradient underneath it the alignment
    #: is real but loose (circular resultant 0.35, 52% within +/-45 deg of the
    #: downhill bearing, and several maps sit within a few degrees of it). So
    #: this is the right default for such a prop, not a law.
    align_to_slope: bool = False
    #: MINIMUM ground slope in degrees. Rarely useful and occasionally
    #: essential: a handful of props only make sense on a face. `fall_7`, the
    #: waterfall, measures slope p50 71.4 deg with 26 of its 44 placements above
    #: 45 -- expressed with `max_slope` alone it lands on the flat and the sheet
    #: of water hangs in the air.
    min_slope: float = 0.0
    #: keep this far from a road corridor edge, cm
    road_clearance_cm: float = 0.0
    #: allowed distance band to the nearest water, metres, as (min, max).
    #: This is a first-class filter because the corpus measures it per CRC and
    #: the two ends mean opposite things: desert flora AVOIDS water (tree/n2
    #: d(water) p50 = 20,009 cm, so a min), while anything decorating an oasis
    #: or a shore hugs it (a max). Pinning shore props to a texture instead does
    #: not work -- the splat is a stipple, so only a handful of tiles near the
    #: water actually carry the shore slot.
    water_distance_m: Tuple[float, float] = (0.0, float("inf"))
    height_bias: Tuple[float, float] = (0.0, 0.0)     # sampled uniformly


@dataclass
class RoadSpec:
    """A corridor in the layout graph.

    Waypoints are in tile coordinates (1 m), map-local, y-down. Stage 2 fits a
    spline through them; stage 5 rasterises the corridor and paints it with an
    ordinary ground texture -- Ymir has no road texture.
    """

    waypoints: List[Tuple[float, float]]
    width_m: float = 5.0
    #: textureset slot to paint the corridor with
    tile_index: int = 1
    #: flatten the terrain under the corridor to this slope, degrees
    flatten_to: float = 3.0
    closed: bool = False


@dataclass
class WaterSpec:
    """A river or lake. ``surface_z`` is world cm; None = auto from terrain."""

    waypoints: List[Tuple[float, float]]
    width_m: float = 10.0
    surface_z: Optional[float] = None
    lake: bool = False


@dataclass
class RegionSpec:
    """A named area with its own object density multiplier."""

    kind: str                       # settlement | forest | clearing | rocky | shore
    polygon: List[Tuple[float, float]]
    density_scale: float = 1.0
    flatten: bool = False


@dataclass
class ScarpSpec:
    """A near-vertical rock face cut along a line.

    The reason this exists is `fall_7`. The corpus hangs its waterfall on ground
    of slope p50 **71.4 deg** (p75 86.6, p95 87.8, n = 44) -- a wall. A generated
    border ridge is a smooth 41-52 deg ramp, and a flat quad hung on a ramp
    either floats clear of it or sinks half into it. No height-bias tuning fixes
    that, because the fault is the terrain.

    A heightfield cannot express 90 degrees: the steepest face is one cell of run
    per drop, and a cell is 200 cm. At the default ``run_m`` of 3 a 20 m drop is
    **81 deg**, which is inside the corpus band. Shorten the run or deepen the
    drop for a harder face.

    The ground on the ``waypoints`` side of the line keeps its height; the other
    side is cut down by ``drop_cm``. Which side is which follows the direction of
    travel along the line: the fall is on its **right**.
    """

    waypoints: List[Tuple[float, float]]
    #: Height lost across the face, cm.
    drop_cm: float = 2000.0
    #: Horizontal distance the drop takes, metres. Small means steep.
    run_m: float = 3.0
    #: How far the cut reaches past the face before it fades back into the
    #: surrounding terrain, metres.
    reach_m: float = 24.0
    #: Absolute height of the face's TOP, world cm. When set, the standing side
    #: is raised (or lowered) to meet it and ``drop_cm`` is ignored -- the face
    #: then runs from the natural ground on the falling side up to this crest.
    #:
    #: This is how you fit terrain to a prop instead of a prop to terrain. A
    #: waterfall sheet has a fixed height, so the wall it hangs on has to match
    #: it: set ``crest_cm`` to ``pool_surface + sheet_height`` and it spans from
    #: lip to waterline exactly. Chasing the same result with ``height_bias``
    #: cannot work when the wall and the sheet are different sizes.
    #:
    #: The falling side is left ALONE in this mode. That is deliberate: it is
    #: what stops the operation deepening the basin it is standing next to, and
    #: so what keeps the lake -- and the water level the crest was derived from
    #: -- where they are.
    crest_cm: Optional[float] = None


@dataclass
class PlazaSpec:
    """A safe-zone disc -- the town-square / duel-ring stamp.

    Measured, not invented. Isolating every `tile*` component in the corpus and
    scoring area against its own bounding box turns up 27 near-circular ones at
    fill 0.70-0.85 (a filled circle scores pi/4 = 0.785; a filled square scores
    1.0) and aspect 1.00-1.10, at radii 8, 10, 14, 18, 20, 22 and 25 m. The same
    areas recur verbatim across unrelated maps -- 1,264 tiles in
    ``metin2_map_a1``, ``metin2_map_smhgate_a1`` and
    ``metin2_map_capedragonhead``; 316 in ``metin2_map_a3``, ``metin2_map_c1``,
    ``metin2_map_smhgate_c1`` and ``metin2_map_guild_battle`` -- so these are
    copy-pasted stamps, not hand-painted shapes.

    On every map that uses the safe-zone flag at all the disc is **100%**
    ``ATTR_SAFEZONE`` against a map baseline of 0.2%. The maps that measure 0%
    (``metin2_map_smhgate_*``, ``metin2_map_t1``) have a map baseline of 0.0%:
    they are paint-only clones that never wrote attr, not counter-examples.

    The disc is painted UNMIXED. Its slot measures solid 0.84-0.87 -- nearly
    every tile has all eight neighbours the same -- against 0.36-0.56 for a
    dirt road in the same palette. It is the one place on an outdoor map where
    the dither is switched off, which is exactly what makes it read as built
    rather than grown.
    """

    #: Map-local metres. 1 tile = 1 m, so this is also tile coordinates.
    centre: Tuple[float, float]
    radius_m: float = 20.0
    #: Palette slot to paint solid; 0 leaves the ground alone and the disc is
    #: an attr feature only.
    tile_index: int = 0
    safezone: bool = True


#: The bridge models, with the fit each one was measured at on the seven
#: bridges of `metin2_map_a1` (`reference/structures.md` sec 5). Lengths are
#: the catalog bounding boxes. `axis` is the model axis the deck runs along and
#: `origin` says where on the span the model's origin sits -- the stone bridges
#: are placed by their middle, in the channel; the rope bridges by ONE END,
#: standing on the lip of a bank and reaching out along +Y.
#:
#: `datum_below_bank_cm` is `bank - (z + height_bias)`: 951 / 948 on the two
#: `a1-024` placements whose stored biases are 0 and -290, which is the point --
#: the bias is whatever makes the datum right, never a constant.
BRIDGE_MODELS: Dict[str, Dict[str, Any]] = {
    "a1_stone": {"crc": 359886641, "name": "a1-024-10m-bridge", "length_cm": 2893.0,
                 "width_cm": 818.0, "axis": "x", "origin": "centre",
                 "datum_below_bank_cm": 950.0, "lip_inset_m": 2.0,
                 "bed_below_bank_cm": 820.0, "water_below_bank_cm": 225.0},
    "b1_stone": {"crc": 2349765063, "name": "b1-022-10m-bridge", "length_cm": 3946.0,
                 "width_cm": 1369.0, "axis": "x", "origin": "centre",
                 "datum_below_bank_cm": 1706.0, "lip_inset_m": 2.0,
                 "bed_below_bank_cm": 900.0, "water_below_bank_cm": 490.0},
    # A rope bridge does NOT sit evenly on its banks. Walking the model's axis on
    # 40 placements (a1, a3, b1, c1, map_a2, threeway): the ORIGIN end has
    # 1.5-4 m of bank-level ground under it (median 2.5) and the FAR end 7-12
    # (median 9.3 / 7.1) -- the far end carries the landing, and the deck sags
    # straight off the origin post. Fitted 6 / 6, the landing hangs over the
    # water and the bank comes up through the deck behind the origin.
    #
    # Those figures count ground within 150 cm of the datum. The LEVEL ground
    # stops sooner, because the lip is rounded, not sheer: past the origin the
    # corpus median falls 0.7 m at 2 m, 3.8 at 4, 11 at 6, 18 at 8 -- about
    # 0.28 x d^2 -- and the deck sags less than that, so nothing shows through
    # it. `lip_inset_*` is where level ground ends (0.8 / 7.8); `lip_round_m` is
    # the run over which the wall reaches the bed, squared.
    "suspension01": {"crc": 59728437, "name": "general_obj_suspension bridge01",
                     "length_cm": 7177.0, "width_cm": 1045.0, "axis": "y", "origin": "end",
                     "datum_below_bank_cm": 5.0, "lip_inset_m": 6.0,
                     "lip_inset_near_m": 0.8, "lip_inset_far_m": 7.8, "lip_round_m": 16.0,
                     "bed_below_bank_cm": 2000.0, "water_below_bank_cm": 1500.0,
                     # map_a2 hangs 21 of these 53-95 m over its water
                     "water_below_bank_max_cm": 9600.0},
    "suspension02": {"crc": 1244865174, "name": "general_obj_suspension bridge02",
                     "length_cm": 4759.0, "width_cm": 1044.0, "axis": "y", "origin": "end",
                     "datum_below_bank_cm": 5.0, "lip_inset_m": 6.0,
                     "lip_inset_near_m": 0.8, "lip_inset_far_m": 5.6, "lip_round_m": 16.0,
                     "bed_below_bank_cm": 2000.0, "water_below_bank_cm": 1500.0,
                     # map_a2 hangs 21 of these 53-95 m over its water
                     "water_below_bank_max_cm": 9600.0},
}


@dataclass
class BridgeSpec:
    """A bridge, and the ground built for it.

    Rule 23 again: the prop is fixed, the terrain is not. On `metin2_map_a1` the
    two banks of every bridge stand at ONE height (2-7 cm apart under the stone
    ones, 10-82 cm under the rope ones), the approach is flat for 20 m behind
    each end, the channel is cut lip-to-lip to the span, and `attr.atr` is
    cleared of block AND water under the deck while the river 15 m to either
    side is 91-100% blocked. None of that comes from placing a model on a river.

    ``centre`` is mid-span in tile metres whichever way the model is anchored;
    ``roll_deg`` is the model's roll (multiples of 15). The span runs along
    model X for the stone bridges and along +Y from the origin for the rope
    ones, so a stone bridge carrying a north-south road has roll 90 and a rope
    bridge reaching south from its anchor has roll 180. Route the road through
    ``centre`` along the span; put a river under it.
    """

    model: str
    centre: Tuple[float, float] = (0.0, 0.0)
    roll_deg: float = 0.0
    #: absolute bank height, world cm. None = the stated surface of the water
    #: under mid-span plus the model's measured clearance (`WaterSpec.surface_z`
    #: -- give the river one, it is what makes it a moat); failing that, the
    #: ground at the two ends, averaged.
    bank_cm: Optional[float] = None
    #: how far the levelled approach reaches behind each end
    approach_m: float = 20.0

    def __post_init__(self):
        self.centre = (float(self.centre[0]), float(self.centre[1]))

    def span_dir(self) -> Tuple[float, float]:
        """Unit vector along the span in y-down tile space."""
        t = math.radians(self.roll_deg)
        if BRIDGE_MODELS[self.model]["axis"] == "x":
            return (math.cos(t), -math.sin(t))
        return (-math.sin(t), -math.cos(t))

    def anchor(self) -> Tuple[float, float]:
        """Where the model's origin goes, tile metres."""
        m = BRIDGE_MODELS[self.model]
        if m["origin"] == "centre":
            return self.centre
        dx, dy = self.span_dir()
        half = m["length_cm"] / 200.0
        return (self.centre[0] - dx * half, self.centre[1] - dy * half)


@dataclass
class GroundStampSpec:
    """Paint copied from under a set-piece -- what `expand` makes of a
    pattern's `Ground`, already turned.

    ``rows[j][i]`` is a digit into ``palette`` (texture PATHS) or ``-``; tile
    ``(i, j)`` lands on ``anchor + origin_m + (i, j)``. The texture stage paints
    each tile whose path the map's own palette declares and skips the rest, so a
    camp copied onto a map without `field 04` keeps its core and loses its halo
    rather than painting the wrong texture. Roads and plazas are painted after
    it and win.
    """

    anchor: Tuple[float, float]
    origin_m: Tuple[float, float]
    palette: List[str]
    rows: List[str]
    label: str = ""

    def __post_init__(self):
        self.anchor = (float(self.anchor[0]), float(self.anchor[1]))
        self.origin_m = (float(self.origin_m[0]), float(self.origin_m[1]))


@dataclass
class ReliefStampSpec:
    """The landform under a set-piece -- what `expand` makes of a pattern's
    `Relief`. A volcano is one smoke effect standing in a crater: the record is
    nothing without the mountain, so the mountain is copied with it.

    ``rows[j][i]`` is the height in cm above the source's own base level at
    ``origin_m + (i, j) * cell_m`` in the pattern's UNTURNED y-down metres;
    ``rotate_deg`` turns it about the anchor at sampling time. The terrain stage
    reads the target's base off the ring between ``radius_m - feather_m`` and
    ``radius_m`` (its 25th percentile, as the source's was), sets the ground to
    ``base + dz`` inside and fades to the target's own ground across the ring.
    """

    anchor: Tuple[float, float]
    origin_m: Tuple[float, float]
    rows: List[List[int]]
    radius_m: float
    feather_m: float = 16.0
    cell_m: float = 2.0
    rotate_deg: float = 0.0
    label: str = ""
    #: water that came with the landform: surface in cm about the base, and
    #: the source plane's 2 m cells (`1`) on the grid of ``rows``
    water_surface_cm: Optional[float] = None
    water_rows: Optional[List[str]] = None
    #: the source's `attr & 0x07` per 1 m tile (`-` = leave), forced last
    attr_origin_m: Optional[Tuple[float, float]] = None
    attr_rows: Optional[List[str]] = None
    #: `ring` or `pivot`: where the base is read (see `setpiece.Relief.base_at`)
    base_at: str = "ring"
    #: the base the terrain stage read off the target; the water stage needs it
    base_cm: Optional[float] = None

    def __post_init__(self):
        self.anchor = (float(self.anchor[0]), float(self.anchor[1]))
        self.origin_m = (float(self.origin_m[0]), float(self.origin_m[1]))

    def lookup(self, x, y, origin_m, cell_m):
        """Grid indices ``(u, v)`` (float arrays) of map points ``x, y`` (metres)
        in a grid of this stamp, back through the turn -- the sign of
        `setpiece.rotate`: offsets turn clockwise in y-down metres."""
        import numpy as np
        t = np.radians(float(self.rotate_deg))
        c, sn = np.cos(t), np.sin(t)
        dx, dy = x - self.anchor[0], y - self.anchor[1]
        return (((dx * c - dy * sn) - origin_m[0]) / float(cell_m),
                ((dx * sn + dy * c) - origin_m[1]) / float(cell_m))


@dataclass
class SetPieceSpec:
    """A shipped compound stamped whole from a saved pattern.

    Three generated versions of the desert camp -- posts on a ring, an arc at
    the corpus median pitch, a "run" chained from nearby records -- each read as
    debris while every statistic passed. The one that matched the source render
    copied the compound verbatim: every record within 32 m of a point,
    offsets, rolls and height biases as shipped, moved as a block. Patterns
    live in ``reference/setpieces/`` about their centroid; `pipeline.run`
    expands each entry here into authored `ObjectTier`s (`gen/setpiece.py`)
    and, unless ``pad_radius_m`` is 0, a levelling pad centred on the anchor --
    the camp's 32 records stand on one plane in the source.
    """

    #: name under `reference/setpieces/` (`desert_camp`), or a path to a .json
    pattern: str
    #: tile metres, y-down; the pattern's pivot (its centroid) lands here
    anchor: Tuple[float, float] = (0.0, 0.0)
    #: turn the whole block, degrees in the sense of `roll` -- counter-clockwise
    #: with north up (measured on 1,681 corpus fences). Keep to multiples of
    #: 15 so the copied rolls stay on the ladder (`taste.md` 1.2).
    rotate_deg: float = 0.0
    label: str = ""
    #: levelling pad radius in metres. None = the pattern's extent + 4 m
    #: (clamped to the plaza band, 4-40); 0 = no pad.
    pad_radius_m: Optional[float] = None
    tier: str = "filler"
    #: paint the pattern's own ground under it, where the palette has the
    #: textures (see `GroundStampSpec`). False leaves the ground to the map.
    ground: bool = True
    #: For a SHORE pattern (one saved with `water_cm`): the surface of the water
    #: it is being put on, world cm. Every piece then hangs as far over this
    #: water as it did over the source's, and no levelling pad is added.
    water_cm: Optional[float] = None

    def __post_init__(self):
        self.anchor = tuple(self.anchor)


@dataclass
class IslandsSpec:
    """Mesas over one sheet of water -- the form of `map_a2`.

    `map_a2` is about twenty flat-topped islands cut out of one plateau by
    canyons of nearly constant width, all flooded by ONE water plane. Measured
    under its 21 `suspension bridge01`: the two tops a bridge joins stand at the
    same height (63 -> 63 m, 67 -> 67 m over the water), **54-60 m lip to lip**,
    the wall falls from the lip to below the water in **12-18 m** of run, the bed
    is flat at 9 or 15 m under the surface, and the tops stand **53-95 m** over
    the water (median 66). The rim of the map is one more mesa, higher, that no
    bridge reaches. Rock is painted down the walls AND across the bed (99.9% of
    submerged tiles are `stone01`/`stone02`).

    That is a Voronoi diagram with its edges widened, so that is how it is
    stated: one ``site`` per island, in tile metres. The canyon between two
    islands runs along their bisector, ``gap_m`` across; where three meet the
    corners round off into a pool (a soft minimum over the bisectors, not a
    hard one). ``gap_m`` is the bridge, not a taste: 60 m is what a 72 m
    `suspension01` spans with 6 m of deck on each bank.

    The tops are whatever the terrain stage made -- roads levelled, pads cut --
    and the cut comes after, so a road drawn from one island to the next is a
    road on both and nothing in between. Put a `BridgeSpec` where it crosses.
    """

    sites: List[Tuple[float, float]]
    #: lip to lip across a canyon, metres
    gap_m: float = 60.0
    #: horizontal run of the wall from the lip down to the bed, metres
    wall_m: float = 15.0
    #: the one water plane, world cm
    surface_cm: float = 10000.0
    #: the canyon floor, world cm
    bed_cm: float = 8800.0
    #: how far in from the map edge the rim mesa's lip stands, metres
    rim_m: float = 100.0
    #: how far the coast wanders off the straight bisector, metres
    wobble_m: float = 7.0
    #: corner rounding where canyons meet, metres (0 = sharp Voronoi corners)
    round_m: float = 22.0
    #: how far the canyons bend off their bisectors between bridges, metres.
    #: Faded to 0 within 45 m of every `BridgeSpec.centre`.
    warp_m: float = 40.0
    #: radius the rim canyon turns on at the map corners, metres
    rim_corner_m: float = 420.0
    #: The rock berm along every lip. `map_a2`'s tops do not run flat to the
    #: edge: 14-34 m inside the lip the ground stands +2.5 m (median), +8 m
    #: (p75), +16 m (p90) over the walkable level and is 50-65% blocked, open
    #: again by 50 m -- a broken parapet of rock humps, absent at bridge heads
    #: and where a road passes. ``berm_cm`` is the height of the tallest humps,
    #: ``berm_m`` how far in from the lip they reach. 0 = a bare knife edge.
    berm_cm: float = 1600.0
    berm_m: float = 32.0

    def __post_init__(self):
        self.sites = [(float(p[0]), float(p[1])) for p in self.sites]


@dataclass
class LabyrinthSpec:
    """A labyrinth assembled from one dungeon kit (`gen/labyrinth.py`).

    The kits are the DungeonBlock sets of the corpus labyrinths, mined into
    `reference/labyrinth/kits.json` (`mine/dungeon_kits.py`): `anglar`,
    `whitedragon_01`, `whitedragon_02`, `skipia`, `spider`, and the one maze
    geometry in six skins `maze`/`maze02`/`maze03`/`monkey`/`monkey02`/
    `monkey03`. Each is built the way its source map is -- `spider` as a full
    room grid whose maze is barricades, the others as corridors only where the
    paths run. `reference/labyrinth/README.md`.
    """

    kit: str
    #: maze cells (columns, rows)
    cells: Tuple[int, int] = (5, 5)
    #: share of the walls a perfect maze leaves that are reopened as loops.
    #: 0 = one solution and every dead end; the corpus anglar/skipia are braided
    loops: float = 0.15
    #: centre-to-centre distance of two cells, metres; None = the kit's own
    pitch_m: Optional[float] = None
    #: start room and boss room at the two far ends of the longest path
    rooms: bool = True
    #: the side of the grid the entrance is on
    entrance: str = "S"
    #: clear margin round the assembly, metres
    margin_m: float = 40.0

    def __post_init__(self):
        self.cells = (int(self.cells[0]), int(self.cells[1]))


@dataclass
class MapSpec:
    """Everything needed to build a map, and nothing that can be derived."""

    name: str
    archetype: str
    size: Tuple[int, int] = (2, 2)                 # sectors (x, y)
    seed: int = 0
    base_position: Tuple[int, int] = (0, 0)
    #: sculpted = outdoor terrain; box = flat interior (dungeon_block/themed).
    #: 44 of 142 corpus maps are `box` and cannot be produced by the sculpted
    #: stages at all.
    style: str = "sculpted"

    environment: str = ""                          # .msenv filename
    textureset_name: str = ""                      # written to textureset/
    textures: List[TextureSlot] = field(default_factory=list)

    roads: List[RoadSpec] = field(default_factory=list)
    water: List[WaterSpec] = field(default_factory=list)
    regions: List[RegionSpec] = field(default_factory=list)
    plazas: List[PlazaSpec] = field(default_factory=list)
    scarps: List[ScarpSpec] = field(default_factory=list)
    bridges: List[BridgeSpec] = field(default_factory=list)
    setpieces: List[SetPieceSpec] = field(default_factory=list)
    #: filled by `setpiece.expand`; written out so the map rebuilds from its spec
    ground_stamps: List[GroundStampSpec] = field(default_factory=list)
    relief_stamps: List[ReliefStampSpec] = field(default_factory=list)
    objects: List[ObjectTier] = field(default_factory=list)
    #: mesas over one water plane (`map_a2`); see `IslandsSpec`
    islands: Optional[IslandsSpec] = None
    #: a dungeon-kit labyrinth (`style: box` only); see `LabyrinthSpec`
    labyrinth: Optional[LabyrinthSpec] = None

    # --- terrain shaping, clamped to the archetype's mined statistics ------
    height_range_cm: Tuple[float, float] = (0.0, 4000.0)
    slope_p50: float = 4.0
    slope_p95: float = 24.0
    flat_fraction: float = 0.55
    roughness: float = 0.5

    # --- border occlusion --------------------------------------------------
    #: Height added at the map edge, cm. Outdoor maps wall themselves in so the
    #: player cannot see past the world: measured median ring lift is 1,351 cm
    #: over the outer 64 m (n=61 outdoor maps), and the flagship maps are far
    #: higher -- metin2_map_a1 4,518, c1 4,662, n_desert_01 4,474.
    #:
    #: Interiors are EXACTLY 0 (n=50, median and corner lift both 0). They
    #: occlude with fog instead: `dark.msenv` and friends. Leave this at 0 for
    #: `style: box`, and for the outdoor archetypes that also choose fog --
    #: snow_field measures -1,338 (the map sits ON the high ground) and pairs it
    #: with `Fog.NearDistance 1`, haze starting at the camera.
    #:
    #: The rule is not "always build mountains", it is "always occlude the
    #: horizon"; ridge and fog are the two instruments. See taste.md.
    border_ridge_cm: float = 0.0
    #: Width of the rise, metres. The measurement ring was 64 m.
    border_ridge_width_m: float = 64.0

    # --- attr policy ------------------------------------------------------
    #: slope_driven (outdoor: block above a threshold) or painted_box (interior:
    #: paint everything, carve the walkable corridor). The corpus splits 59/57
    #: over the 116 maps that ship attr.atr (catalog/stats-attr.json).
    attr_style: str = "slope_driven"
    block_slope_deg: float = 20.0
    border_band_m: int = 4
    safezone_regions: List[str] = field(default_factory=list)

    notes: str = ""

    # ------------------------------------------------------------------
    @property
    def sector_count(self) -> int:
        return self.size[0] * self.size[1]

    @property
    def width_tiles(self) -> int:
        return self.size[0] * SECTOR_TILES

    @property
    def height_tiles(self) -> int:
        return self.size[1] * SECTOR_TILES

    def sectors(self) -> List[Tuple[int, int]]:
        return [(x, y) for y in range(self.size[1]) for x in range(self.size[0])]

    def rng(self, salt: str = "") -> random.Random:
        """Deterministic sub-stream, so stages do not perturb each other.

        Re-running stage 5 must not change stage 6's placements, which a single
        shared generator would guarantee it does.
        """
        return random.Random(stream_seed(salt, self.seed))

    def is_box(self) -> bool:
        return self.style == "box"

    # ------------------------------------------------------------------
    def validate(self) -> List[str]:
        """Everything wrong with this spec, worst first. Empty = buildable."""
        out: List[str] = []
        # The `metin2_map_*` prefix is a CONVENTION, not a requirement, and the
        # corpus disproves treating it as one: gm_guild_build, map_a2,
        # map_b_fielddungeon, map_n_snowm_01 and map_n_threeway all ship without
        # it -- map_a2 is the very file used as ground truth for server_attr.
        # What actually matters is that the name works as a folder and as an
        # index key.
        if not self.name:
            out.append("name is empty")
        elif any(c in self.name for c in '/\\:*?"<>|') or \
                any(c.isspace() or ord(c) < 32 for c in self.name):
            # Whitespace and control characters matter as much as the obvious
            # path separators: the server index is line-based, so a name with a
            # newline in it silently truncates or corrupts the entry.
            out.append("name %r contains a character that is illegal in a "
                       "folder name or breaks the server index lookup" % self.name)
        sx, sy = self.size
        if not (1 <= sx <= 256 and 1 <= sy <= 256):
            out.append("size %r outside 1..256 (MAX_MAPSIZE)" % (self.size,))
        if self.style not in ("sculpted", "box"):
            out.append("style %r must be 'sculpted' or 'box'" % self.style)
        if self.attr_style not in ("slope_driven", "painted_box"):
            out.append("attr_style %r must be 'slope_driven' or 'painted_box'"
                       % self.attr_style)

        for i, v in enumerate(self.base_position):
            if v % BASE_ALIGN:
                out.append("base_position[%d]=%d is not a multiple of %d "
                           "(sector edge); the client tolerates it but regen "
                           "and atlas maths assume alignment" % (i, v, BASE_ALIGN))

        n = len(self.textures)
        if n == 0:
            out.append("no textures -- terrain renders as the error texture")
        if n > 255:
            out.append("%d textures exceeds the 255 usable slots "
                       "(slot 0 is the built-in eraser)" % n)

        lo, hi = self.height_range_cm
        if hi <= lo:
            out.append("height_range_cm %r is not increasing" % (self.height_range_cm,))
        if hi > 32767.5:
            out.append("height_range_cm max %.1f exceeds the uint16 ceiling "
                       "(65535 * 0.5 = 32767.5 cm)" % hi)

        for r in self.roads:
            if len(r.waypoints) < 2:
                out.append("road with %d waypoint(s) -- need at least 2"
                           % len(r.waypoints))
            if not 0 <= r.tile_index <= n:
                out.append("road tile_index %d outside the palette (0..%d)"
                           % (r.tile_index, n))
        for w in self.water:
            if len(w.waypoints) < (3 if w.lake else 2):
                out.append("water feature has too few waypoints")
        span_tiles = (self.width_tiles, self.height_tiles)
        for o in self.objects:
            for pos in o.positions:
                px, py = pos[0], pos[1]
                if not (0 <= px < span_tiles[0] and 0 <= py < span_tiles[1]):
                    out.append("object %s has a position (%.0f, %.0f) outside "
                               "the %dx%d m map"
                               % (o.name or o.crc, px, py, *span_tiles))
        for br in self.bridges:
            m = BRIDGE_MODELS.get(br.model)
            if m is None:
                out.append("unknown bridge model %r (known: %s)"
                           % (br.model, ", ".join(sorted(BRIDGE_MODELS))))
                continue
            if br.roll_deg % 15:
                out.append("bridge %s roll %g is not a multiple of 15" % (br.model, br.roll_deg))
            reach = m["length_cm"] / 200.0 + br.approach_m
            dx, dy = br.span_dir()
            for sgn in (-1.0, 1.0):
                ex, ey = br.centre[0] + sgn * dx * reach, br.centre[1] + sgn * dy * reach
                if not (0 <= ex < span_tiles[0] and 0 <= ey < span_tiles[1]):
                    out.append("bridge %s at (%g, %g) runs off the %dx%d m map with its "
                               "approach" % (br.model, br.centre[0], br.centre[1], *span_tiles))
                    break
        if self.islands is not None:
            isl = self.islands
            if len(isl.sites) < 2:
                out.append("islands needs at least 2 sites")
            if not isl.bed_cm < isl.surface_cm < lo:
                out.append("islands: want bed_cm < surface_cm < height_range_cm[0] "
                           "(%.0f < %.0f < %.0f) -- the tops stand over the water, "
                           "the water over the bed" % (isl.bed_cm, isl.surface_cm, lo))
            if isl.wall_m * 2.0 >= isl.gap_m:
                out.append("islands: two walls of %.0f m do not fit a %.0f m canyon"
                           % (isl.wall_m, isl.gap_m))
            for px, py in isl.sites:
                if not (0 <= px < span_tiles[0] and 0 <= py < span_tiles[1]):
                    out.append("island site (%.0f, %.0f) outside the %dx%d m map"
                               % (px, py, *span_tiles))
        for sc in self.scarps:
            if len(sc.waypoints) < 2:
                out.append("scarp with %d waypoint(s) -- need at least 2"
                           % len(sc.waypoints))
            if sc.run_m <= 0:
                out.append("scarp run_m must be positive")
            elif sc.crest_cm is None and sc.drop_cm / max(1e-6, sc.run_m * 100.0) < 1.0:
                out.append(
                    "scarp drop %.0f cm over %.1f m is only %.0f deg -- that is a "
                    "slope, not a face. fall_7 sits on 71 deg median."
                    % (sc.drop_cm, sc.run_m,
                       __import__("math").degrees(__import__("math").atan(
                           sc.drop_cm / max(1e-6, sc.run_m * 100.0)))))

        for pz in self.plazas:
            if not 0 <= pz.tile_index <= n:
                out.append("plaza tile_index %d outside the palette (0..%d)"
                           % (pz.tile_index, n))
            # The shipped stamps run 8 to 25 m. Outside that band the disc stops
            # reading as a plaza: under 6 m it is smaller than the buildings that
            # ring it, over 40 m it is a field with a hard edge. A levelling pad
            # (`tile_index=0`, no safezone) paints nothing and has no edge to
            # read, and a town's pad is wider than any disc: `b1_town_square`
            # needs 70 m.
            is_pad = pz.tile_index == 0 and not pz.safezone
            if not is_pad and not 4.0 <= pz.radius_m <= 40.0:
                out.append("plaza radius %.1f m outside the corpus band "
                           "(8-25 m measured, 4-40 tolerated)" % pz.radius_m)
            cx, cy = pz.centre
            if not (pz.radius_m <= cx <= span_tiles[0] - pz.radius_m and
                    pz.radius_m <= cy <= span_tiles[1] - pz.radius_m):
                out.append("plaza at (%.0f, %.0f) r=%.0f runs off the %dx%d m map"
                           % (cx, cy, pz.radius_m, span_tiles[0], span_tiles[1]))
        for sps in self.setpieces:
            if resolve_pattern(sps.pattern) is None:
                out.append("set-piece pattern %r not found -- a name under "
                           "reference/setpieces/ or a path to a .json" % sps.pattern)
            ax, ay = sps.anchor
            if not (0 <= ax < span_tiles[0] and 0 <= ay < span_tiles[1]):
                out.append("set-piece %s anchored at (%.0f, %.0f) outside the "
                           "%dx%d m map" % (sps.label or sps.pattern, ax, ay, *span_tiles))
            if sps.pad_radius_m is not None and sps.pad_radius_m < 0:
                out.append("set-piece %s pad_radius_m must be >= 0"
                           % (sps.label or sps.pattern))
        # Archetype tables state distances measured on 2x4 to 6x6 maps. Copied
        # onto a small map they exclude the whole surface, and the failure is
        # silent -- the tier simply places nothing. Catch it here rather than
        # letting the shortfall report explain it after the build.
        span_m = min(self.size) * SECTOR_TILES
        for o in self.objects:
            if o.density <= 0 and o.count <= 0 and not o.positions:
                out.append("object %s (%d) has neither density, count nor "
                           "positions" % (o.name or "?", o.crc))
            for t in o.on_tiles:
                if not 0 <= t <= n:
                    out.append("object %s references tile %d outside the palette"
                               % (o.name or o.crc, t))
            lo, hi = o.water_distance_m
            if hi < lo:
                out.append("object %s water_distance_m %r is inverted"
                           % (o.name or o.crc, o.water_distance_m))
            if self.water and lo >= span_m * 0.45:
                out.append(
                    "object %s keeps %.0f m from water on a map only %d m across "
                    "-- nothing will place. The archetype tables measure these on "
                    "2x4 to 6x6 maps; scale the distance to the map and say so"
                    % (o.name or o.crc, lo, span_m))
            if o.road_clearance_cm / 100.0 >= span_m * 0.45 and self.roads:
                out.append(
                    "object %s keeps %.0f m from the road on a map only %d m "
                    "across -- nothing will place"
                    % (o.name or o.crc, o.road_clearance_cm / 100.0, span_m))
        if self.is_box() and self.water:
            out.append("style 'box' with water features -- interiors have none")
        if self.labyrinth is not None:
            lab = self.labyrinth
            if not self.is_box() or self.attr_style != "painted_box":
                out.append("labyrinth needs style 'box' and attr_style 'painted_box' -- "
                           "the kits are interiors on a black plane")
            if min(lab.cells) < 2 or max(lab.cells) > 24:
                out.append("labyrinth cells %r outside 2..24" % (lab.cells,))
            if not 0.0 <= lab.loops <= 1.0:
                out.append("labyrinth loops %r outside 0..1" % lab.loops)
            if lab.entrance not in ("N", "E", "S", "W"):
                out.append("labyrinth entrance %r must be N, E, S or W" % lab.entrance)
        return out

    def require_valid(self) -> None:
        problems = self.validate()
        if problems:
            raise SpecError("mapspec %r is not buildable:\n  - %s"
                            % (self.name, "\n  - ".join(problems)))

    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def dump(self, path=None) -> str:
        d = self.to_dict()
        if yaml is not None:
            text = yaml.safe_dump(d, sort_keys=False, default_flow_style=False)
        else:
            text = json.dumps(d, indent=2)
        if path is not None:
            pathlib.Path(path).write_text(text, encoding="utf-8", newline="\n")
        return text

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MapSpec":
        d = dict(d)
        d["textures"] = [TextureSlot(**t) for t in d.get("textures", [])]
        d["roads"] = [RoadSpec(**r) for r in d.get("roads", [])]
        d["water"] = [WaterSpec(**w) for w in d.get("water", [])]
        d["regions"] = [RegionSpec(**r) for r in d.get("regions", [])]
        d["plazas"] = [PlazaSpec(**p) for p in d.get("plazas", [])]
        d["scarps"] = [ScarpSpec(**x) for x in d.get("scarps", [])]
        d["bridges"] = [BridgeSpec(**x) for x in d.get("bridges", [])]
        d["setpieces"] = [SetPieceSpec(**x) for x in d.get("setpieces", [])]
        d["ground_stamps"] = [GroundStampSpec(**x) for x in d.get("ground_stamps", [])]
        d["relief_stamps"] = [ReliefStampSpec(**x) for x in d.get("relief_stamps", [])]
        d["objects"] = [ObjectTier(**o) for o in d.get("objects", [])]
        if d.get("islands") is not None:
            d["islands"] = IslandsSpec(**d["islands"])
        if d.get("labyrinth") is not None:
            d["labyrinth"] = LabyrinthSpec(**d["labyrinth"])
        for k in ("size", "base_position", "height_range_cm"):
            if k in d and d[k] is not None:
                d[k] = tuple(d[k])
        known = {f for f in cls.__dataclass_fields__}      # noqa: SLF001
        unknown = set(d) - known
        if unknown:
            raise SpecError("unknown mapspec keys: %s" % ", ".join(sorted(unknown)))
        return cls(**d)

    @classmethod
    def load(cls, path) -> "MapSpec":
        text = pathlib.Path(path).read_text(encoding="utf-8")
        if yaml is not None:
            data = yaml.safe_load(text)
        else:
            data = json.loads(text)
        return cls.from_dict(data)

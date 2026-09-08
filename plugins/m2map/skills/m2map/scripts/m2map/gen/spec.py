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
    #: When set, the prop is placed HERE and every candidate filter above is
    #: skipped -- slope, water distance, road clearance, spacing.
    #:
    #: Landmarks are authored, not scattered, and a waterfall is the clearest
    #: case: it has to hang at the lip of the basin that feeds it, and no
    #: combination of "steep" and "near water" can say WHICH water. Constrained
    #: placement put one at the foot of the drop, beside the lower pool, 23 m
    #: below the tarn it was supposed to fall from.
    positions: List[Tuple[float, float]] = field(default_factory=list)
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
    objects: List[ObjectTier] = field(default_factory=list)

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
            for px, py in o.positions:
                if not (0 <= px < span_tiles[0] and 0 <= py < span_tiles[1]):
                    out.append("object %s has a position (%.0f, %.0f) outside "
                               "the %dx%d m map"
                               % (o.name or o.crc, px, py, *span_tiles))
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
            # ring it, over 40 m it is a field with a hard edge.
            if not 4.0 <= pz.radius_m <= 40.0:
                out.append("plaza radius %.1f m outside the corpus band "
                           "(8-25 m measured, 4-40 tolerated)" % pz.radius_m)
            cx, cy = pz.centre
            if not (pz.radius_m <= cx <= span_tiles[0] - pz.radius_m and
                    pz.radius_m <= cy <= span_tiles[1] - pz.radius_m):
                out.append("plaza at (%.0f, %.0f) r=%.0f runs off the %dx%d m map"
                           % (cx, cy, pz.radius_m, span_tiles[0], span_tiles[1]))
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
        d["objects"] = [ObjectTier(**o) for o in d.get("objects", [])]
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

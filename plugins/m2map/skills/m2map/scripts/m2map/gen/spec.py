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
    #: keep this far from a road corridor edge, cm
    road_clearance_cm: float = 0.0
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
    objects: List[ObjectTier] = field(default_factory=list)

    # --- terrain shaping, clamped to the archetype's mined statistics ------
    height_range_cm: Tuple[float, float] = (0.0, 4000.0)
    slope_p50: float = 4.0
    slope_p95: float = 24.0
    flat_fraction: float = 0.55
    roughness: float = 0.5

    # --- attr policy ------------------------------------------------------
    #: slope_driven (outdoor: block above a threshold) or painted_box (interior:
    #: paint everything, carve the walkable corridor). The corpus splits 59/55.
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
        return random.Random("%d/%s" % (self.seed, salt))

    def is_box(self) -> bool:
        return self.style == "box"

    # ------------------------------------------------------------------
    def validate(self) -> List[str]:
        """Everything wrong with this spec, worst first. Empty = buildable."""
        out: List[str] = []
        if not self.name:
            out.append("name is empty")
        elif not self.name.startswith("metin2_map_") and not self.name.startswith("metin2_"):
            out.append("name %r does not follow the metin2_map_* convention "
                       "(the client does not care, but every tool and the "
                       "server index do)" % self.name)
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
        for o in self.objects:
            if o.density <= 0 and o.count <= 0:
                out.append("object %s (%d) has neither density nor count"
                           % (o.name or "?", o.crc))
            for t in o.on_tiles:
                if not 0 <= t <= n:
                    out.append("object %s references tile %d outside the palette"
                               % (o.name or o.crc, t))
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

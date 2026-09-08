"""``setting.txt`` / ``mapproperty.txt`` / ``areaproperty.txt`` codecs.

All three are flat ``key<sep>token...`` scripts read through
``LoadMultipleTextData``/``LoadTextData`` (no ``Start``/``End`` blocks), so
:func:`m2map.codec.textfile.parse_flat` handles them all.

Readers  : ``CMapOutdoor::LoadSetting`` (GameLib/MapOutdoorLoad.cpp:291-492),
           ``CMapBase::LoadProperty``   (GameLib/MapBase.cpp:52-98),
           ``MapOutdoorLoad.cpp:206-234`` for areaproperty.
Writers  : ``CMapOutdoorAccessor::SaveSetting``  (WorldEditor/DataCtrl/MapAccessorOutdoor.cpp:117-204),
           ``CMapOutdoorAccessor::SaveProperty`` (MapAccessorOutdoor.cpp:81-103),
           ``CTerrainAccessor::SaveProperty``    (MapAccessorTerrain.cpp:997-1019).

Every class keeps the parsed :class:`~m2map.codec.textfile.FlatDoc`, so
:meth:`to_bytes` re-emits the source byte for byte.  :meth:`render_canonical`
produces the layout the WorldEditor writes from scratch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .textfile import FlatDoc, KeyItem, atof, atoi, encode, parse_flat, quote, SourcePreserving

__all__ = ["Setting", "MapProperty", "AreaProperty"]

CRLF = "\r\n"

#: Keys the WorldEditor rewrites from compile-time constants on every save
#: (MapAccessorOutdoor.cpp:151-157) -- the loaded value is discarded.
EDITOR_FORCED = {"cellscale": "200", "heightscale": "0.500000", "viewradius": "128"}


def _norm_texture_set(path: str) -> str:
    """``LoadSetting`` prefixes ``textureset\\`` when the path lacks it."""
    if "textureset" in path.lower().replace("/", "\\"):
        return path
    return "textureset\\" + path


@dataclass
class Setting(SourcePreserving):
    """``setting.txt`` -- the map root descriptor.

    The server opens this file as ``Setting.txt`` (capital S,
    sectree_manager.cpp:759) and reads only ``MapSize``, ``BasePosition`` and
    ``CellScale``.
    """

    script_type: str = "MapSetting"
    cell_scale: int = 200
    height_scale: float = 0.5
    view_radius: int = 128
    map_size: Tuple[int, int] = (1, 1)
    base_position: Tuple[int, int] = (0, 0)
    texture_set: str = ""
    environment: str = ""
    terrain_visible: Optional[int] = None
    #: Keys outside the documented set, in file order.  Seen in the corpus:
    #: ``Environment1..Environment8`` and ``EnvironmentRange1/2`` (newer GF
    #: clients; absent from the WorldEditorRemix source tree), plus junk lines
    #: left by truncated in-place rewrites.
    extras: List[Tuple[str, List[str]]] = field(default_factory=list)
    doc: Optional[FlatDoc] = None

    # -- read --------------------------------------------------------------
    @classmethod
    def parse(cls, data) -> "Setting":
        doc = parse_flat(data)
        s = cls(doc=doc)
        known = {"scripttype", "cellscale", "heightscale", "viewradius",
                 "mapsize", "baseposition", "textureset", "environment",
                 "terrainvisible"}
        for item in doc.items:
            if not isinstance(item, KeyItem):
                continue
            k, v = item.key, item.values
            if k not in known:
                s.extras.append((k, list(v)))
                continue
            if k == "scripttype":
                s.script_type = v[0] if v else ""
            elif k == "cellscale":
                s.cell_scale = atoi(v[0]) if v else 0
            elif k == "heightscale":
                s.height_scale = atof(v[0]) if v else 0.0
            elif k == "viewradius":
                s.view_radius = atoi(v[0]) if v else 0
            elif k == "mapsize":
                s.map_size = (atoi(v[0]), atoi(v[1])) if len(v) > 1 else (0, 0)
            elif k == "baseposition":
                s.base_position = (atoi(v[0]), atoi(v[1])) if len(v) > 1 else (0, 0)
            elif k == "textureset":
                s.texture_set = v[0] if v else ""
            elif k == "environment":
                s.environment = v[0] if v else ""
            elif k == "terrainvisible":
                s.terrain_visible = atoi(v[0]) if v else 1
        s._snapshot()
        return s

    @classmethod
    def load(cls, path) -> "Setting":
        with open(path, "rb") as fh:
            return cls.parse(fh.read())

    # -- derived quantities ------------------------------------------------
    @property
    def is_valid(self) -> bool:
        return self.script_type.lower() == "mapsetting"

    @property
    def texture_set_path(self) -> str:
        return _norm_texture_set(self.texture_set)

    @property
    def world_size(self) -> Tuple[int, int]:
        """World span in cm: ``CellScale * 128 * MapSize`` per axis."""
        return (self.cell_scale * 128 * self.map_size[0],
                self.cell_scale * 128 * self.map_size[1])

    @property
    def server_sector_origin(self) -> Tuple[int, int]:
        """Global server sector id of the map origin (BasePosition / 6400)."""
        return (self.base_position[0] // 6400, self.base_position[1] // 6400)

    def problems(self) -> List[str]:
        out = []
        if not self.is_valid:
            out.append("ScriptType is %r, not MapSetting" % self.script_type)
        if self.cell_scale != 200:
            out.append("CellScale %d != 200 desyncs server geometry" % self.cell_scale)
        for axis, n in zip("XY", self.map_size):
            if not 1 <= n <= 256:
                out.append("MapSize%s %d outside 1..256" % (axis, n))
        for axis, b in zip("XY", self.base_position):
            if b % 25600:
                out.append("BasePosition%s %d is not a multiple of 25600" % (axis, b))
        return out

    # -- write -------------------------------------------------------------
    def render(self) -> str:
        """Byte-exact re-render of the parsed source (canonical if built fresh)."""
        if self.doc is not None and not self.dirty:
            return self.doc.render()
        return self.render_canonical()

    def to_bytes(self) -> bytes:
        return encode(self.render())

    def render_canonical(self) -> str:
        """The layout ``SaveSetting`` writes (MapAccessorOutdoor.cpp:145-172).

        ``fopen(..., "w")`` on Windows turns every ``\\n`` into ``\\r\\n``.
        Note the editor forces CellScale/HeightScale/ViewRadius to constants;
        this writer emits the object's values so a round trip is faithful.
        """
        out = [
            "ScriptType\t%s" % self.script_type, "",
            "CellScale\t%d" % self.cell_scale,
            "HeightScale\t%f" % self.height_scale, "",
            "ViewRadius\t%d" % self.view_radius, "",
            "MapSize\t%d\t%d" % self.map_size,
            "BasePosition\t%d\t%d" % self.base_position,
            "TextureSet\t%s" % self.texture_set,
            "Environment\t%s" % self.environment, "",
        ]
        if self.terrain_visible is not None:
            out.append("TerrainVisible\t%d" % self.terrain_visible)
        for key, vals in self.extras:
            out.append("\t".join([key] + list(vals)))
        return "".join(l + CRLF for l in out)


@dataclass
class MapProperty(SourcePreserving):
    """``mapproperty.txt`` -- client-only map kind descriptor."""

    script_type: str = "MapProperty"
    map_type: str = "Outdoor"
    parent_map_name: Optional[str] = None
    #: True when the source quoted the value (the editor always does).
    parent_quoted: bool = True
    doc: Optional[FlatDoc] = None

    @classmethod
    def parse(cls, data) -> "MapProperty":
        doc = parse_flat(data)
        p = cls(doc=doc)
        for item in doc.items:
            if not isinstance(item, KeyItem):
                continue
            if item.key == "scripttype":
                p.script_type = item.values[0] if item.values else ""
            elif item.key == "maptype":
                p.map_type = item.values[0] if item.values else ""
            elif item.key == "parentmapname" and item.values:
                p.parent_map_name = item.values[0]
                raw = doc.lines[item.line].tokens
                p.parent_quoted = len(raw) > 1 and raw[1].startswith('"')
        p._snapshot()
        return p

    @classmethod
    def load(cls, path) -> "MapProperty":
        with open(path, "rb") as fh:
            return cls.parse(fh.read())

    @property
    def is_valid(self) -> bool:
        return self.script_type.lower() == "mapproperty"

    @property
    def is_indoor(self) -> bool:
        """Only ``Indoor`` is indoor; ``Outdoor`` and ``Invalid`` both load
        as outdoor (MapBase.cpp:52-98)."""
        return self.map_type.lower() == "indoor"

    def render(self) -> str:
        if self.doc is not None and not self.dirty:
            return self.doc.render()
        return self.render_canonical()

    def to_bytes(self) -> bytes:
        return encode(self.render())

    def render_canonical(self) -> str:
        """``SaveProperty`` layout (MapAccessorOutdoor.cpp:89-98).

        The editor never writes ``ParentMapName``; when present we append it in
        the shape the shipped files use.
        """
        out = ["ScriptType %s" % self.script_type, "",
               "MapType %s" % quote(self.map_type), ""]
        if self.parent_map_name is not None:
            name = quote(self.parent_map_name) if self.parent_quoted else self.parent_map_name
            out += ["ParentMapName %s" % name, ""]
        return "".join(l + CRLF for l in out)


@dataclass
class AreaProperty(SourcePreserving):
    """``<map>/<XXXYYY>/areaproperty.txt`` -- the "this sector exists" marker."""

    script_type: str = "AreaProperty"
    area_name: str = ""
    num_water: Optional[int] = None
    doc: Optional[FlatDoc] = None

    @classmethod
    def parse(cls, data) -> "AreaProperty":
        doc = parse_flat(data)
        a = cls(doc=doc)
        for item in doc.items:
            if not isinstance(item, KeyItem):
                continue
            if item.key == "scripttype":
                a.script_type = item.values[0] if item.values else ""
            elif item.key == "areaname":
                a.area_name = item.values[0] if item.values else ""
            elif item.key == "numwater":
                a.num_water = atoi(item.values[0]) if item.values else 0
        a._snapshot()
        return a

    @classmethod
    def load(cls, path) -> "AreaProperty":
        with open(path, "rb") as fh:
            return cls.parse(fh.read())

    @property
    def is_valid(self) -> bool:
        return self.script_type.lower() == "areaproperty"

    def render(self) -> str:
        if self.doc is not None and not self.dirty:
            return self.doc.render()
        return self.render_canonical()

    def to_bytes(self) -> bytes:
        return encode(self.render())

    def render_canonical(self) -> str:
        """``CTerrainAccessor::SaveProperty`` layout (MapAccessorTerrain.cpp:1006-1016).

        ``NumWater`` is written by the editor but never read back -- the live
        count comes from the ``water.wtr`` header.
        """
        out = ["ScriptType %s" % self.script_type, "",
               "AreaName %s" % quote(self.area_name), "",
               "NumWater %d" % (self.num_water or 0), ""]
        return "".join(l + CRLF for l in out)

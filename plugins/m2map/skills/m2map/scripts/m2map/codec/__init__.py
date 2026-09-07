"""Map-format codecs, one module per on-disk format.

Text formats (shared Ymir tokenizer):

===================  ================================================
module               format
===================  ================================================
:mod:`textfile`      the tokenizer -- ``Start/End`` flat blocks and
                     ``Group``/``List`` nesting
:mod:`setting`       ``setting.txt``, ``mapproperty.txt``, ``areaproperty.txt``
:mod:`areadata`      ``areadata.txt``, ``areaambiencedata.txt``
:mod:`textureset`    ``textureset/*.txt``
:mod:`msenv`         ``*.msenv`` environment presets
:mod:`property`      ``property/**/*.pr?`` YPRT containers + ``reserve``
:mod:`regen`         ``regen/npc/boss/stone.txt``, ``index``, ``Town.txt``,
                     ``dungeon.txt``, ``MonsterArrange.txt``
===================  ================================================

Binary map-layer codecs (numpy), one module per on-disk format.

===================  ================================================
module               format
===================  ================================================
:mod:`height`        ``height.raw``      131x131 uint16 heightmap
:mod:`tile`          ``tile.raw``        258x258 uint8 texture indices
:mod:`attr`          ``attr.atr``        6-byte header + 256x256 flags
:mod:`water`         ``water.wtr``       7-byte header + 128x128 + heights
:mod:`shadow`        ``shadowmap.raw``   256x256 RGB555 (+ ``.dds``)
:mod:`minimap`       ``minimap.dds``     DDS tile (DXT1/3/5, 16/24/32bpp)
:mod:`dds`           DDS container + DXT / mask pixel codecs
:mod:`server_attr`   ``server_attr``     LZO1X-compressed server grid
:mod:`lzo1x`         pure-Python LZO1X-1 compress/decompress
===================  ================================================

Every reader keeps enough of the source file (padding skirts, legacy height
widths, DDS mip payloads, LZO block streams) that ``write(read(f)) == f``
byte-for-byte on shipped data; see tests/test_codec_binary.py.
"""

from . import (areadata, attr, dds, height, lzo1x, minimap, msenv, property,
               regen, server_attr, setting, shadow, textfile, textureset, tile,
               water)
from .areadata import AmbienceRecord, AreaAmbienceData, AreaData, ObjectRecord
from .msenv import Environment
from .property import PropertyFile, PropertyReserve
from .regen import (DungeonFile, MapIndex, MonsterArrange, RegenFile, RegenRow,
                    TownFile)
from .setting import AreaProperty, MapProperty, Setting
from .textfile import FlatDoc, GroupDoc, Line, parse_flat, parse_groups, parse_lines
from .textureset import TextureEntry, TextureSet
from .attr import AttrMap, read_attr, write_attr
from .dds import DDS, read_dds, write_dds
from .height import HeightMap, read_height, write_height
from .minimap import MiniMap, read_minimap, write_minimap
from .server_attr import ServerAttr, read_server_attr, write_server_attr
from .shadow import ShadowMap, read_shadow_raw, write_shadow_raw
from .tile import TileMap, read_tile, write_tile
from .water import WaterMap, read_water, write_water

__all__ = [
    "areadata", "msenv", "property", "regen", "setting", "textfile", "textureset",
    "AmbienceRecord", "AreaAmbienceData", "AreaData", "ObjectRecord",
    "AreaProperty", "MapProperty", "Setting",
    "Environment", "PropertyFile", "PropertyReserve",
    "DungeonFile", "MapIndex", "MonsterArrange", "RegenFile", "RegenRow", "TownFile",
    "FlatDoc", "GroupDoc", "Line", "parse_flat", "parse_groups", "parse_lines",
    "TextureEntry", "TextureSet",
    "attr", "dds", "height", "lzo1x", "minimap", "server_attr", "shadow", "tile", "water",
    "AttrMap", "read_attr", "write_attr",
    "DDS", "read_dds", "write_dds",
    "HeightMap", "read_height", "write_height",
    "MiniMap", "read_minimap", "write_minimap",
    "ServerAttr", "read_server_attr", "write_server_attr",
    "ShadowMap", "read_shadow_raw", "write_shadow_raw",
    "TileMap", "read_tile", "write_tile",
    "WaterMap", "read_water", "write_water",
]

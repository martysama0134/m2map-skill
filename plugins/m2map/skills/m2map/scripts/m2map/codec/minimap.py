"""``minimap.dds`` -- per-sectree minimap tile.

Spec: reference/mapformat/minimap-dds.md
Engine: save ``SaveMiniMapFromD3DTexture9``
(WorldEditor/DataCtrl/MapAccessorTerrain.cpp:1413-1461), load
``CTerrain::LoadMiniMapTexture`` (GameLib/AreaTerrain.cpp:70-86).

A top-down 256x256 render of one sectree covering exactly 25,600x25,600 world
units, i.e. **1 texel = 100 world units = 1 attr cell**.  It is an ordinary DDS,
so this module is a thin, minimap-flavoured wrapper over :mod:`m2map.codec.dds`,
which implements the encodings Pillow does not cover.

What the corpus actually contains (<CORPUS>, 1332 minimap.dds):

===============================  =======  =====
encoding                         bytes    files
===============================  =======  =====
DXT1 256x256, no mips            32,896   1270
DXT1 256x256, 9 mips             43,832     62
===============================  =======  =====

The "262,272-byte X8R8G8B8" case named in the spec does not occur for
minimap.dds in this corpus (it does for one shadowmap.dds, as 24bpp) -- always
parse the header.

Directional variants (``minimap_top.dds``, ``minimap_leftbottom.dds``, ...)
appear in some maps; they are the same format and read with the same code.
"""

from __future__ import annotations

import numpy as np

from . import dds as _dds
from .dds import DDS, A8R8G8B8, R5G6B5, X8R8G8B8

__all__ = [
    "SIZE",
    "TEXEL_SCALE",
    "SECTOR_SIZE",
    "VARIANT_NAMES",
    "MiniMap",
    "read_minimap",
    "write_minimap",
    "from_rgba",
    "DDS",
    "X8R8G8B8",
    "A8R8G8B8",
    "R5G6B5",
]

SIZE = 256              # texels per side of a sectree tile
TEXEL_SCALE = 100       # world units per texel (1 m)
SECTOR_SIZE = SIZE * TEXEL_SCALE    # 25,600 world units

VARIANT_NAMES = (
    "minimap.dds", "minimap_top.dds", "minimap_bottom.dds", "minimap_left.dds",
    "minimap_right.dds", "minimap_lefttop.dds", "minimap_righttop.dds",
    "minimap_leftbottom.dds", "minimap_rightbottom.dds",
)


class MiniMap:
    """A minimap tile: the parsed :class:`DDS` plus convenience accessors.

    The underlying DDS payload is kept verbatim, so ``write_minimap`` on an
    unmodified tile reproduces the source file byte for byte, whatever encoding
    it uses.  Assigning :attr:`pixels` re-encodes in the file's own format.
    """

    __slots__ = ("dds",)

    def __init__(self, image):
        if not isinstance(image, DDS):
            raise TypeError("expected a DDS instance")
        self.dds = image

    # --- pixels ------------------------------------------------------------
    @property
    def pixels(self):
        """Top mip decoded to an ``(h, w, 4)`` uint8 RGBA array."""
        return self.dds.to_rgba(0)

    @pixels.setter
    def pixels(self, rgba):
        self.dds.set_rgba(rgba, 0)

    def rgb(self):
        return self.pixels[..., :3]

    def mip(self, level):
        return self.dds.to_rgba(level)

    # --- metadata ----------------------------------------------------------
    @property
    def width(self):
        return self.dds.width

    @property
    def height(self):
        return self.dds.height

    @property
    def format_name(self):
        return self.dds.format_name

    def world_bounds(self, coord_x, coord_y):
        """Map-local world rectangle ``(x0, y0, x1, y1)`` this tile covers."""
        x0 = coord_x * SECTOR_SIZE
        y0 = coord_y * SECTOR_SIZE
        return (x0, y0, x0 + SECTOR_SIZE, y0 + SECTOR_SIZE)

    # --- serialisation -----------------------------------------------------
    @classmethod
    def from_bytes(cls, blob):
        return cls(DDS.from_bytes(blob))

    def to_bytes(self):
        return self.dds.to_bytes()

    def __repr__(self):
        return "MiniMap(%r)" % (self.dds,)


def from_rgba(rgba, fmt=b"DXT1", mipmaps=1):
    """Build a minimap tile from pixels (default DXT1 no-mips, the corpus norm)."""
    return MiniMap(DDS.from_rgba(np.asarray(rgba, dtype=np.uint8), fmt=fmt, mipmaps=mipmaps))


def read_minimap(path):
    with open(path, "rb") as fh:
        return MiniMap.from_bytes(fh.read())


def write_minimap(path, tile):
    blob = tile.to_bytes() if isinstance(tile, (MiniMap, DDS)) else bytes(tile)
    with open(path, "wb") as fh:
        fh.write(blob)


# module-level alias so callers can reach the generic reader for the odd
# directional tiles without importing dds explicitly
read_dds = _dds.read_dds

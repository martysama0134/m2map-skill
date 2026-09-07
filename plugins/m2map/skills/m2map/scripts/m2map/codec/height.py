"""``height.raw`` -- per-sectree terrain heightmap.

Spec: reference/mapformat/height-raw.md
Engine: ``CTerrainImpl::LoadHeightMap`` (PRTerrainLib/Terrain.cpp:69-86),
``CTerrainAccessor::SaveHeightMap`` (WorldEditor/DataCtrl/MapAccessorTerrain.cpp:1041-1053).

Headerless, row-major ``uint16`` little-endian, always 131x131 = 34,322 bytes.

Padding convention
------------------
A sectree is 128x128 terrain *cells* -> 129x129 *vertices*
(``HEIGHTMAP_XSIZE = XSIZE+1``).  The file stores 131x131
(``HEIGHTMAP_RAW_XSIZE = XSIZE+3``): a one-sample skirt on every side that
duplicates the neighbouring sectors' edge vertices so normals/patches blend
across sector borders.  Logical vertex ``(sx, sy)`` with ``sx, sy in [-1, 129]``
lives at ``raw[(sy + 1) * 131 + (sx + 1)]`` (``Terrain.h:139-142``), so the
129x129 usable window is ``raw[1:130, 1:130]``.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "RAW_SIZE",
    "VERTEX_SIZE",
    "CELL_COUNT",
    "CELL_SCALE",
    "SECTOR_SIZE",
    "DEFAULT_HEIGHT_SCALE",
    "BLANK_RAW",
    "FILE_SIZE",
    "HeightMap",
    "read_height",
    "write_height",
    "new_blank",
    "slope_degrees",
]

RAW_SIZE = 131               # HEIGHTMAP_RAW_XSIZE = XSIZE + 3
VERTEX_SIZE = 129            # HEIGHTMAP_XSIZE = XSIZE + 1
CELL_COUNT = 128             # XSIZE
CELL_SCALE = 200             # world units per terrain cell (2 m)
SECTOR_SIZE = CELL_COUNT * CELL_SCALE   # 25,600 world units
DEFAULT_HEIGHT_SCALE = 0.5   # WorldEditor hard-codes this on save
BLANK_RAW = 0x7FFF           # NewHeightMap fill (MapAccessorTerrain.cpp:1031-1033)
FILE_SIZE = RAW_SIZE * RAW_SIZE * 2      # 34,322


class HeightMap:
    """131x131 ``uint16`` heightmap with the +1 skirt kept intact.

    ``raw`` is indexed ``[row, col]`` = ``[y + 1, x + 1]`` in logical vertex
    coordinates.  Row 0 is the north edge; X grows east, Y grows south.
    """

    __slots__ = ("raw", "trailing")

    def __init__(self, raw, trailing=b""):
        raw = np.asarray(raw, dtype="<u2")
        if raw.shape != (RAW_SIZE, RAW_SIZE):
            raise ValueError("height raw must be %dx%d, got %r" % (RAW_SIZE, RAW_SIZE, raw.shape))
        self.raw = raw
        # the loader memcpys exactly 34,322 bytes and ignores anything after;
        # keep it so an over-long file still round-trips
        self.trailing = bytes(trailing)

    # --- views -------------------------------------------------------------
    @property
    def vertices(self):
        """129x129 view of the usable vertex grid (skirt stripped)."""
        return self.raw[1:1 + VERTEX_SIZE, 1:1 + VERTEX_SIZE]

    def get(self, sx, sy):
        """Sample logical vertex ``(sx, sy)``, ``sx``/``sy`` in ``[-1, 129]``."""
        if not (-1 <= sx <= VERTEX_SIZE) or not (-1 <= sy <= VERTEX_SIZE):
            raise IndexError("vertex (%d, %d) outside [-1, %d]" % (sx, sy, VERTEX_SIZE))
        return int(self.raw[sy + 1, sx + 1])

    def set(self, sx, sy, value):
        if not (-1 <= sx <= VERTEX_SIZE) or not (-1 <= sy <= VERTEX_SIZE):
            raise IndexError("vertex (%d, %d) outside [-1, %d]" % (sx, sy, VERTEX_SIZE))
        self.raw[sy + 1, sx + 1] = value

    # --- conversions -------------------------------------------------------
    def world_z(self, height_scale=DEFAULT_HEIGHT_SCALE, skirt=False):
        """World Z (centimetres) per vertex: ``raw * HeightScale``."""
        grid = self.raw if skirt else self.vertices
        return grid.astype(np.float64) * float(height_scale)

    def slope_degrees(self, height_scale=DEFAULT_HEIGHT_SCALE, cell_scale=CELL_SCALE):
        """Per-cell terrain slope in degrees -> 128x128 array.

        For cell ``(cx, cy)`` the four corner vertices are
        ``v[cy:cy+2, cx:cx+2]``; the gradient is the mean of the two X edges
        and the two Y edges, divided by the cell size, and the slope is
        ``atan(hypot(gx, gy))``.
        """
        return slope_degrees(self.vertices, height_scale, cell_scale)

    # --- serialisation -----------------------------------------------------
    @classmethod
    def from_bytes(cls, data):
        if len(data) < FILE_SIZE:
            raise ValueError("height.raw must be >= %d bytes, got %d" % (FILE_SIZE, len(data)))
        arr = np.frombuffer(data, dtype="<u2", count=RAW_SIZE * RAW_SIZE)
        return cls(arr.reshape(RAW_SIZE, RAW_SIZE).copy(), trailing=bytes(data[FILE_SIZE:]))

    def to_bytes(self):
        return self.raw.astype("<u2", copy=False).tobytes() + self.trailing

    def __eq__(self, other):
        return (isinstance(other, HeightMap) and np.array_equal(self.raw, other.raw)
                and self.trailing == other.trailing)

    def __repr__(self):
        return "HeightMap(min=%d, max=%d)" % (int(self.raw.min()), int(self.raw.max()))


def slope_degrees(vertices, height_scale=DEFAULT_HEIGHT_SCALE, cell_scale=CELL_SCALE):
    """Slope in degrees for each of the 128x128 cells of a 129x129 vertex grid."""
    v = np.asarray(vertices, dtype=np.float64) * float(height_scale)
    if v.shape != (VERTEX_SIZE, VERTEX_SIZE):
        raise ValueError("expected a %dx%d vertex grid" % (VERTEX_SIZE, VERTEX_SIZE))
    gx = ((v[:-1, 1:] - v[:-1, :-1]) + (v[1:, 1:] - v[1:, :-1])) * 0.5 / cell_scale
    gy = ((v[1:, :-1] - v[:-1, :-1]) + (v[1:, 1:] - v[:-1, 1:])) * 0.5 / cell_scale
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def new_blank(value=BLANK_RAW):
    """Blank heightmap, filled like the editor's ``NewHeightMap`` (0x7FFF)."""
    return HeightMap(np.full((RAW_SIZE, RAW_SIZE), value, dtype="<u2"))


def read_height(path):
    with open(path, "rb") as fh:
        return HeightMap.from_bytes(fh.read())


def write_height(path, heightmap):
    if not isinstance(heightmap, HeightMap):
        heightmap = HeightMap(heightmap)
    with open(path, "wb") as fh:
        fh.write(heightmap.to_bytes())

"""``water.wtr`` -- per-sectree water layer map.

Spec: reference/mapformat/water-wtr.md
Engine: ``CTerrainImpl::LoadWaterMapFile`` (PRTerrainLib/Terrain.cpp:201-296),
``SaveWaterMap`` (WorldEditor/DataCtrl/MapAccessorTerrain.cpp:1230-1264).

Layout: ``uint16`` magic 5426 (0x1532), ``uint16`` width 128, ``uint16``
height 128, ``uint8`` layer count N, 128x128 cell indices (``0xFF`` = dry),
then N heights.  Heights are ``int32`` in the current format (what the
WorldEditor writes) and ``uint16`` in legacy files; the loader tells them apart
purely by the remaining byte count -- ``16384 + 4*N`` vs ``16384 + 2*N``
(Terrain.cpp:259-292).  Total size therefore 16,391 + 4*N (or +2*N).

Heights are raw height units, same scale as height.raw:
``worldZ = value * HeightScale`` (0.5 in practice).  Water cells are at terrain
cell resolution: 1 cell = 200 world units.

Legacy caveat (engine bug, Terrain.cpp:286-292): after converting WORD heights
the loader falls through and re-copies ``4*N`` bytes over them, so legacy files
load with garbage heights in the real client.  This codec converts them
correctly and re-emits them in their original width so files round-trip
byte-identically; pass ``legacy=False`` when you want to upgrade one.
"""

from __future__ import annotations

import struct

import numpy as np

__all__ = [
    "MAGIC",
    "WIDTH",
    "HEIGHT",
    "HEADER_SIZE",
    "CELL_COUNT",
    "CELL_SCALE",
    "NO_WATER",
    "MAX_WATER_NUM",
    "BASE_SIZE",
    "WaterMap",
    "read_water",
    "write_water",
    "new_blank",
]

MAGIC = 5426            # 0x1532
WIDTH = 128
HEIGHT = 128
HEADER_SIZE = 7         # magic, w, h, layer count
CELL_COUNT = WIDTH * HEIGHT         # 16,384
CELL_SCALE = 200        # world units per water cell (2 m)
NO_WATER = 0xFF
MAX_WATER_NUM = 255
BASE_SIZE = HEADER_SIZE + CELL_COUNT    # 16,391 (+ 4*N or 2*N)


class WaterMap:
    """128x128 layer-index grid plus the per-layer raw heights."""

    __slots__ = ("cells", "heights", "legacy")

    def __init__(self, cells, heights=(), legacy=False):
        cells = np.asarray(cells, dtype=np.uint8)
        if cells.shape != (HEIGHT, WIDTH):
            raise ValueError("water grid must be %dx%d, got %r" % (WIDTH, HEIGHT, cells.shape))
        heights = [int(h) for h in heights]
        if len(heights) > MAX_WATER_NUM:
            raise ValueError("at most %d water layers (got %d)" % (MAX_WATER_NUM, len(heights)))
        self.cells = cells
        self.heights = heights
        self.legacy = bool(legacy)

    # --- queries -----------------------------------------------------------
    @property
    def num_layers(self):
        return len(self.heights)

    @property
    def wet_mask(self):
        """Boolean 128x128 mask of cells that carry water."""
        return self.cells != NO_WATER

    def height_at(self, x, y, height_scale=0.5):
        """World Z of the water surface at cell ``(x, y)``, or ``None`` if dry."""
        idx = int(self.cells[y, x])
        if idx == NO_WATER:
            return None
        if idx >= len(self.heights):
            raise IndexError("cell (%d, %d) references layer %d of %d"
                             % (x, y, idx, len(self.heights)))
        return self.heights[idx] * float(height_scale)

    def world_heights(self, height_scale=0.5):
        return [h * float(height_scale) for h in self.heights]

    def validate(self):
        """Return a list of problems (dangling layer indices)."""
        problems = []
        used = np.unique(self.cells)
        for v in used:
            v = int(v)
            if v != NO_WATER and v >= len(self.heights):
                problems.append("cell value %d >= layer count %d" % (v, len(self.heights)))
        return problems

    # --- serialisation -----------------------------------------------------
    @classmethod
    def from_bytes(cls, data):
        if len(data) < BASE_SIZE:
            raise ValueError("water.wtr shorter than %d bytes (%d)" % (BASE_SIZE, len(data)))
        magic, w, h = struct.unpack_from("<HHH", data, 0)
        if magic != MAGIC:
            raise ValueError("bad water.wtr magic 0x%04X (expected 0x%04X)" % (magic, MAGIC))
        if (w, h) != (WIDTH, HEIGHT):
            raise ValueError("bad water.wtr dims %dx%d (expected %dx%d)" % (w, h, WIDTH, HEIGHT))
        num = data[6]
        cells = np.frombuffer(data, dtype=np.uint8, count=CELL_COUNT,
                              offset=HEADER_SIZE).reshape(HEIGHT, WIDTH).copy()
        rest = len(data) - BASE_SIZE
        if rest == num * 4:
            legacy = False
            heights = list(struct.unpack_from("<%di" % num, data, BASE_SIZE)) if num else []
        elif rest == num * 2:
            legacy = True
            heights = list(struct.unpack_from("<%dH" % num, data, BASE_SIZE)) if num else []
        else:
            raise ValueError("bad water.wtr size: %d trailing bytes for %d layers"
                             % (rest, num))
        return cls(cells, heights, legacy=legacy)

    def to_bytes(self):
        out = struct.pack("<HHHB", MAGIC, WIDTH, HEIGHT, len(self.heights))
        out += self.cells.astype(np.uint8, copy=False).tobytes()
        if self.heights:
            fmt = "<%d%s" % (len(self.heights), "H" if self.legacy else "i")
            out += struct.pack(fmt, *self.heights)
        return out

    def __eq__(self, other):
        return (isinstance(other, WaterMap)
                and np.array_equal(self.cells, other.cells)
                and self.heights == other.heights
                and self.legacy == other.legacy)

    def __repr__(self):
        return "WaterMap(layers=%d, wet=%d%s)" % (
            self.num_layers, int(np.count_nonzero(self.wet_mask)),
            ", legacy" if self.legacy else "")


def new_blank():
    """Dry sector: all cells 0xFF, no layers (the engine's fallback state)."""
    return WaterMap(np.full((HEIGHT, WIDTH), NO_WATER, dtype=np.uint8), [])


def read_water(path):
    with open(path, "rb") as fh:
        return WaterMap.from_bytes(fh.read())


def write_water(path, watermap):
    with open(path, "wb") as fh:
        fh.write(watermap.to_bytes())

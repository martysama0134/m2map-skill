"""``attr.atr`` -- per-sectree client attribute grid.

Spec: reference/mapformat/attr-atr.md
Engine: ``CTerrainImpl::LoadAttrMap`` (PRTerrainLib/Terrain.cpp:106-155),
``SaveAttrMap`` (WorldEditor/DataCtrl/MapAccessorTerrain.cpp:1091-1114).

Layout: ``uint16`` magic 2634 (0x0A4A), ``uint16`` width 256, ``uint16``
height 256, then 256x256 attribute bytes row-major -> 65,542 bytes.  No border
padding (unlike height/tile).  One attr cell = 100 world units = 1 m.

Flag bits
---------
Only bits 0..2 are engine-defined client-side (``PRTerrainLib/Terrain.h:68-72``);
``MAX_ATTRIBUTE_NUM = 8`` is the usable bit count.  The remaining bits are
editor/paint conventions with no client meaning.

**Bits 3..7 must NOT reach ``server_attr``.**  ``ServerAttrGenerator.cpp:118-130``
does copy the whole byte, but Ymir's own shipped files do not: in ``map_a2`` and
``map_n_snowm_01`` every server cell holds only bits 0..2.  That difference is
load-bearing, because the server reads bit 7 as ``ATTR_OBJECT`` and blocks
movement on ``ATTR_BLOCK|ATTR_OBJECT`` (``char.cpp:5648``,
``sectree_manager.cpp:823``), while the paint convention puts bit 7 on
*walkable* "mountain" cells.  Copying the whole byte server-blocks the entire
map: measured on ``map_a2``, 9,437,184 of 9,437,184 cells against the shipped
6,246,724.  17 corpus maps carry 0x80 on 100% of their cells.
:func:`m2map.codec.server_attr.from_attr_maps` therefore masks to 0x07 by
default.  Names for bits 3..7 follow the WorldEditor overlay / community tooling
(M2-MapForge ``index.html:311-319``).

============  ======  ==============  ==========================================
Constant      Hex     Bit             Defined by
============  ======  ==============  ==========================================
ATTR_BLOCK    0x01    0               engine (ATTRIBUTE_BLOCK)
ATTR_WATER    0x02    1               engine (ATTRIBUTE_WATER)
ATTR_BANPK    0x04    2               engine (ATTRIBUTE_BANPK, "safezone")
ATTR_BANSHOP  0x08    3               editor convention
ATTR_FLAG5    0x10    4               unused / editor convention
ATTR_FLAG6    0x20    5               unused / editor convention
ATTR_FLAG7    0x40    6               paint convention: "ground" family bit
ATTR_OBJECT   0x80    7               paint convention; would mean server
                                      ATTR_OBJECT if leaked into server_attr
============  ======  ==============  ==========================================

Never mask bits off when saving *this* file: official maps use values like 0xC9
(mountain + block) whose high bits carry the editor's paint conventions, and a
rewrite that drops them loses information the overlay depends on.

The opposite rule applies one step downstream: mask to 0x07 when generating
``server_attr``.  The two are not in tension -- ``attr.atr`` keeps everything,
the server file keeps only what the server reads.
"""

from __future__ import annotations

import struct

import numpy as np

__all__ = [
    "MAGIC",
    "WIDTH",
    "HEIGHT",
    "HEADER_SIZE",
    "FILE_SIZE",
    "CELL_SCALE",
    "ATTR_BLOCK",
    "ATTR_WATER",
    "ATTR_BANPK",
    "ATTR_SAFEZONE",
    "ATTR_BANSHOP",
    "ATTR_FLAG5",
    "ATTR_FLAG6",
    "ATTR_FLAG7",
    "ATTR_OBJECT",
    "FLAG_NAMES",
    "AttrMap",
    "read_attr",
    "write_attr",
    "new_blank",
    "has_flag",
    "set_flag",
    "clear_flag",
    "describe_byte",
]

MAGIC = 2634            # 0x0A4A
WIDTH = 256
HEIGHT = 256
HEADER_SIZE = 6
FILE_SIZE = HEADER_SIZE + WIDTH * HEIGHT    # 65,542
CELL_SCALE = 100        # world units per attr cell (1 m)

# --- flag bits -------------------------------------------------------------
ATTR_BLOCK = 0x01       # engine ATTRIBUTE_BLOCK
ATTR_WATER = 0x02       # engine ATTRIBUTE_WATER
ATTR_BANPK = 0x04       # engine ATTRIBUTE_BANPK
ATTR_SAFEZONE = ATTR_BANPK   # editor/UI name for the same bit
ATTR_BANSHOP = 0x08
ATTR_FLAG5 = 0x10
ATTR_FLAG6 = 0x20
ATTR_FLAG7 = 0x40
ATTR_OBJECT = 0x80      # server ATTR_OBJECT (movement blocker server-side)

FLAG_NAMES = (
    (ATTR_BLOCK, "block"),
    (ATTR_WATER, "water"),
    (ATTR_BANPK, "safezone"),
    (ATTR_BANSHOP, "banshop"),
    (ATTR_FLAG5, "flag5"),
    (ATTR_FLAG6, "flag6"),
    (ATTR_FLAG7, "flag7"),
    (ATTR_OBJECT, "object"),
)

#: Paint-convention byte values seen in Ymir's own maps (attr-atr.md).
PAINT_KINDS = {
    0x40: "land, walkable",
    0x41: "building footprint, blocked",
    0x44: "safezone, walkable",
    0xC8: "mountain, walkable",
    0xC9: "mountain, blocked",
    0xCA: "bridge, walkable (water)",
    0xCB: "water on mountain, blocked",
    0xCC: "safezone on mountain",
}


# --- bitwise helpers (work on scalars and numpy arrays alike) --------------
def has_flag(value, flag):
    """True where ``value`` has ``flag`` set."""
    if isinstance(value, np.ndarray):
        return (value & np.uint8(flag)) != 0
    return (int(value) & flag) != 0


def set_flag(value, flag):
    if isinstance(value, np.ndarray):
        return value | np.uint8(flag)
    return int(value) | flag


def clear_flag(value, flag):
    if isinstance(value, np.ndarray):
        return value & np.uint8(~flag & 0xFF)
    return int(value) & (~flag & 0xFF)


def describe_byte(value):
    """``(list_of_flag_names, paint_kind_or_None)`` for one attribute byte."""
    value = int(value) & 0xFF
    names = [name for bit, name in FLAG_NAMES if value & bit]
    return names, PAINT_KINDS.get(value)


class AttrMap:
    """256x256 ``uint8`` attribute grid, indexed ``[y, x]``."""

    __slots__ = ("cells",)

    def __init__(self, cells):
        cells = np.asarray(cells, dtype=np.uint8)
        if cells.shape != (HEIGHT, WIDTH):
            raise ValueError("attr grid must be %dx%d, got %r" % (WIDTH, HEIGHT, cells.shape))
        self.cells = cells

    # --- queries -----------------------------------------------------------
    def get(self, x, y):
        return int(self.cells[y, x])

    def set(self, x, y, value):
        self.cells[y, x] = value

    def mask(self, flag):
        """Boolean 256x256 mask of cells carrying ``flag``."""
        return has_flag(self.cells, flag)

    def counts(self):
        """``{flag_name: cell_count}`` over all 8 bits."""
        return {name: int(np.count_nonzero(self.cells & np.uint8(bit)))
                for bit, name in FLAG_NAMES}

    def apply(self, mask, flag, on=True):
        """Set/clear ``flag`` where the boolean ``mask`` is True (in place)."""
        mask = np.asarray(mask, dtype=bool)
        if on:
            self.cells[mask] |= np.uint8(flag)
        else:
            self.cells[mask] &= np.uint8(~flag & 0xFF)

    # --- serialisation -----------------------------------------------------
    @classmethod
    def from_bytes(cls, data):
        if len(data) != FILE_SIZE:
            raise ValueError("attr.atr must be %d bytes, got %d" % (FILE_SIZE, len(data)))
        magic, w, h = struct.unpack_from("<HHH", data, 0)
        if magic != MAGIC:
            raise ValueError("bad attr.atr magic 0x%04X (expected 0x%04X)" % (magic, MAGIC))
        if (w, h) != (WIDTH, HEIGHT):
            raise ValueError("bad attr.atr dims %dx%d (expected %dx%d)" % (w, h, WIDTH, HEIGHT))
        cells = np.frombuffer(data, dtype=np.uint8, count=WIDTH * HEIGHT,
                              offset=HEADER_SIZE).reshape(HEIGHT, WIDTH).copy()
        return cls(cells)

    def to_bytes(self):
        return struct.pack("<HHH", MAGIC, WIDTH, HEIGHT) + \
            self.cells.astype(np.uint8, copy=False).tobytes()

    def __eq__(self, other):
        return isinstance(other, AttrMap) and np.array_equal(self.cells, other.cells)

    def __repr__(self):
        return "AttrMap(%s)" % ", ".join("%s=%d" % kv for kv in self.counts().items() if kv[1])


def new_blank(value=0):
    return AttrMap(np.full((HEIGHT, WIDTH), value, dtype=np.uint8))


def read_attr(path):
    with open(path, "rb") as fh:
        return AttrMap.from_bytes(fh.read())


def write_attr(path, attrmap):
    if not isinstance(attrmap, AttrMap):
        attrmap = AttrMap(attrmap)
    with open(path, "wb") as fh:
        fh.write(attrmap.to_bytes())

"""``server_attr`` -- server-side attribute map (LZO1X-compressed).

Spec: reference/mapformat/server-attr.md
Server: ``SECTREE_MANAGER::LoadAttribute``
(m2dev-server-src/src/game/sectree_manager.cpp:450-548), compression via
``lzo1x_1_compress`` / ``lzo1x_decompress_safe`` (``lzo_manager.cpp:24,32-40``).
Generation recipe: ``WorldEditor/DataCtrl/ServerAttrGenerator.cpp:109-160``.

Layout::

    int32 LE  width          server-sector columns  (= MapSizeX * 4)
    int32 LE  height         server-sector rows     (= MapSizeY * 4)
    for y in range(height):          # y-major, x inner
        for x in range(width):
            uint32 LE size           compressed byte count
            uint8[size]              LZO1X stream -> exactly 65,536 bytes
                                     = 128x128 uint32 LE cells, row-major

Grid math: server sector = 6,400 world units, server cell = 50 units, so
128 cells per server sector, 4x4 server sectors per client sectree, and 2x2
server cells per client attr cell.

Byte fidelity
-------------
Re-compressing a block cannot reproduce the original bytes (the shipped files
were produced by a specific minilzo build; see :mod:`m2map.codec.lzo1x`).  This
class therefore keeps every block's compressed stream verbatim and only
re-compresses blocks you actually modify, so read -> write of an untouched file
is byte-identical.
"""

from __future__ import annotations

import struct

import numpy as np

from . import lzo1x

__all__ = [
    "SECTREE_SIZE",
    "CELL_SIZE",
    "CELLS_PER_SECTOR",
    "BLOCK_CELLS",
    "BLOCK_BYTES",
    "SECTORS_PER_SECTREE",
    "ATTR_BLOCK",
    "ATTR_WATER",
    "ATTR_BANPK",
    "ATTR_OBJECT",
    "ServerAttr",
    "read_server_attr",
    "write_server_attr",
    "from_attr_maps",
]

SECTREE_SIZE = 6400         # server sector edge, world units (sectree.h:6-11)
CELL_SIZE = 50              # server attribute cell edge, world units
CELLS_PER_SECTOR = SECTREE_SIZE // CELL_SIZE        # 128
BLOCK_CELLS = CELLS_PER_SECTOR * CELLS_PER_SECTOR   # 16,384
BLOCK_BYTES = BLOCK_CELLS * 4                       # 65,536
SECTORS_PER_SECTREE = 4     # 25,600 / 6,400

# sectree.h:25-31 -- identical low bits to attr.atr, plus ATTR_OBJECT
ATTR_BLOCK = 0x01
ATTR_WATER = 0x02
ATTR_BANPK = 0x04
ATTR_OBJECT = 0x80


class ServerAttr:
    """The whole ``server_attr`` file: header dims + one block per server sector."""

    __slots__ = ("width", "height", "_raw", "_grids", "trailing")

    def __init__(self, width, height, raw_blocks=None, trailing=b""):
        self.width = int(width)
        self.height = int(height)
        n = self.width * self.height
        self._raw = list(raw_blocks) if raw_blocks is not None else [None] * n
        if len(self._raw) != n:
            raise ValueError("expected %d blocks, got %d" % (n, len(self._raw)))
        self._grids = {}
        self.trailing = trailing        # bytes after the last block (normally b"")

    # --- indexing ----------------------------------------------------------
    @property
    def block_count(self):
        return self.width * self.height

    def index(self, sx, sy):
        """Block index of server sector ``(sx, sy)`` -- y-major, x inner."""
        if not (0 <= sx < self.width and 0 <= sy < self.height):
            raise IndexError("server sector (%d, %d) outside %dx%d"
                             % (sx, sy, self.width, self.height))
        return sy * self.width + sx

    def compressed_block(self, sx, sy):
        """The stored LZO stream for one sector (``None`` if never written)."""
        return self._raw[self.index(sx, sy)]

    def block(self, sx, sy):
        """Decompressed 128x128 ``uint32`` attribute grid for a server sector."""
        i = self.index(sx, sy)
        grid = self._grids.get(i)
        if grid is None:
            blob = self._raw[i]
            if blob is None:
                grid = np.zeros((CELLS_PER_SECTOR, CELLS_PER_SECTOR), dtype="<u4")
            else:
                data = lzo1x.decompress(blob, BLOCK_BYTES)
                grid = np.frombuffer(data, dtype="<u4").reshape(
                    CELLS_PER_SECTOR, CELLS_PER_SECTOR).copy()
            self._grids[i] = grid
        return grid

    def set_block(self, sx, sy, grid):
        """Replace one sector's grid (re-compressed on write)."""
        grid = np.asarray(grid, dtype="<u4")
        if grid.shape != (CELLS_PER_SECTOR, CELLS_PER_SECTOR):
            raise ValueError("server block must be %dx%d" % (CELLS_PER_SECTOR,) * 2)
        i = self.index(sx, sy)
        self._grids[i] = grid
        self._raw[i] = None     # force re-compression

    def blocks(self):
        """Iterate ``(sx, sy, grid)`` in file order."""
        for sy in range(self.height):
            for sx in range(self.width):
                yield sx, sy, self.block(sx, sy)

    # --- conversions -------------------------------------------------------
    @property
    def sectree_size(self):
        """Client map size in sectrees ``(w, h)``."""
        return self.width // SECTORS_PER_SECTREE, self.height // SECTORS_PER_SECTREE

    def to_attr_grid(self, cx, cy):
        """Rebuild one client sectree's 256x256 ``uint8`` attr grid.

        Inverse of the generator: takes the top-left server cell of each 2x2
        block and keeps the low byte.
        """
        out = np.zeros((256, 256), dtype=np.uint8)
        for qy in range(SECTORS_PER_SECTREE):
            for qx in range(SECTORS_PER_SECTREE):
                g = self.block(cx * SECTORS_PER_SECTREE + qx, cy * SECTORS_PER_SECTREE + qy)
                sub = (g[::2, ::2] & 0xFF).astype(np.uint8)     # 64x64
                out[qy * 64:(qy + 1) * 64, qx * 64:(qx + 1) * 64] = sub
        return out

    def attribute(self, world_x, world_y, base_x=0, base_y=0):
        """Attribute DWORD at a world position (map-local unless a base given)."""
        lx = world_x - base_x
        ly = world_y - base_y
        sx, sy = int(lx // SECTREE_SIZE), int(ly // SECTREE_SIZE)
        cx = int((lx % SECTREE_SIZE) // CELL_SIZE)
        cy = int((ly % SECTREE_SIZE) // CELL_SIZE)
        return int(self.block(sx, sy)[cy, cx])

    # --- serialisation -----------------------------------------------------
    @classmethod
    def from_bytes(cls, data):
        if len(data) < 8:
            raise ValueError("server_attr shorter than its 8-byte header")
        width, height = struct.unpack_from("<ii", data, 0)
        if width <= 0 or height <= 0 or width > 8192 or height > 8192:
            raise ValueError("implausible server_attr dims %dx%d" % (width, height))
        raw = []
        off = 8
        for _ in range(width * height):
            if off + 4 > len(data):
                raise ValueError("truncated server_attr at block %d" % len(raw))
            (size,) = struct.unpack_from("<I", data, off)
            off += 4
            if off + size > len(data):
                raise ValueError("truncated block %d (%d bytes)" % (len(raw), size))
            raw.append(data[off:off + size])
            off += size
        return cls(width, height, raw, trailing=data[off:])

    def to_bytes(self):
        out = bytearray(struct.pack("<ii", self.width, self.height))
        for i in range(self.block_count):
            blob = self._raw[i]
            if blob is None:
                grid = self._grids.get(i)
                if grid is None:
                    grid = np.zeros((CELLS_PER_SECTOR, CELLS_PER_SECTOR), dtype="<u4")
                blob = lzo1x.compress(grid.astype("<u4", copy=False).tobytes())
                self._raw[i] = blob
            out += struct.pack("<I", len(blob))
            out += blob
        out += self.trailing
        return bytes(out)

    def verify(self):
        """Decompress every block; returns ``(ok_count, [(index, error), ...])``."""
        ok = 0
        bad = []
        for i in range(self.block_count):
            blob = self._raw[i]
            if blob is None:
                ok += 1
                continue
            try:
                data = lzo1x.decompress(blob, BLOCK_BYTES)
                if len(data) != BLOCK_BYTES:
                    raise lzo1x.LZOError("size %d" % len(data))
                ok += 1
            except Exception as exc:            # noqa: BLE001 - reported, not raised
                bad.append((i, str(exc)))
        return ok, bad

    def __repr__(self):
        return "ServerAttr(%dx%d server sectors = %dx%d sectrees)" % (
            (self.width, self.height) + self.sectree_size)


#: Bits the shipped Ymir ``server_attr`` files actually carry.  ``Terrain.h:70-72``
#: defines only ATTRIBUTE_BLOCK (0x01), WATER (0x02) and BANPK (0x04); everything
#: above bit 2 is client-side paint bookkeeping with no server meaning.
SERVER_ATTR_MASK = 0x07


def from_attr_maps(attr_grids, map_w, map_h, mask=SERVER_ATTR_MASK):
    """Generate a ``server_attr`` from client ``attr.atr`` grids.

    ``attr_grids`` maps ``(cx, cy)`` sectree coordinates to a 256x256 ``uint8``
    array (or an :class:`~m2map.codec.attr.AttrMap`); missing sectrees become
    zero-filled blocks.  Each masked client attr byte is copied into a DWORD and
    upsampled 2x2, per ServerAttrGenerator.cpp:109-160.

    **The default mask is not optional in practice.**  The server reads bit 7 as
    ``ATTR_OBJECT`` and blocks movement on ``ATTR_BLOCK|ATTR_OBJECT``
    (``char.cpp:5648``, ``char_manager.cpp:290``, ``sectree_manager.cpp:823``).
    Ymir's paint convention puts bit 7 on *walkable* "mountain" cells, so copying
    the whole byte -- which is literally what ``ServerAttrGenerator.cpp:118-130``
    does -- turns walkable terrain into server-blocked terrain.  Measured on
    ``map_a2``: the shipped ``server_attr`` has 1,561,681 server-blocked cells;
    the whole-byte copy produces 2,359,296, i.e. *every cell on the map*, while
    ``mask=0x07`` reproduces the shipped 1,561,681 exactly.  17 corpus maps carry
    0x80 on 100% of their cells and would be bricked outright.

    Shipped files agree with the mask, not with the editor source: in
    ``map_a2`` and ``map_n_snowm_01`` no cell matches ``attr.atr`` on the full
    byte and every cell matches on ``& 0x07``.  Maps whose attr bytes are already
    plain flags (``metin2_map_n_flame_01``, ``metin2_map_n_snow_dungeon_01``,
    ``metin2_map_privatewar``) match either way.

    Pass ``mask=None`` to opt into the raw whole-byte copy.  Only do that to
    reproduce the editor's behaviour for comparison; it is not a shippable map.
    """
    width = map_w * SECTORS_PER_SECTREE
    height = map_h * SECTORS_PER_SECTREE
    sa = ServerAttr(width, height)
    zero = np.zeros((256, 256), dtype=np.uint8)
    cache = {}
    for sy in range(height):
        for sx in range(width):
            key = (sx // SECTORS_PER_SECTREE, sy // SECTORS_PER_SECTREE)
            grid = cache.get(key)
            if grid is None:
                src = attr_grids.get(key)
                if src is None:
                    grid = zero
                else:
                    grid = np.asarray(getattr(src, "cells", src), dtype=np.uint8)
                    if grid.shape != (256, 256):
                        raise ValueError("attr grid %r must be 256x256" % (key,))
                if mask is not None:
                    grid = grid & np.uint8(mask)
                cache[key] = grid
            ox = (sx % SECTORS_PER_SECTREE) * 64
            oy = (sy % SECTORS_PER_SECTREE) * 64
            quad = grid[oy:oy + 64, ox:ox + 64].astype("<u4")
            block = np.repeat(np.repeat(quad, 2, axis=0), 2, axis=1)   # 128x128
            sa.set_block(sx, sy, block)
    return sa


def read_server_attr(path):
    with open(path, "rb") as fh:
        return ServerAttr.from_bytes(fh.read())


def write_server_attr(path, server_attr):
    with open(path, "wb") as fh:
        fh.write(server_attr.to_bytes())

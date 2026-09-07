"""``tile.raw`` -- per-sectree ground-texture index map.

Spec: reference/mapformat/tile-raw.md
Engine: ``CTerrainImpl::RAW_LoadTileMap`` (PRTerrainLib/Terrain.cpp:161-179),
``RAW_SaveTileMap`` (WorldEditor/DataCtrl/MapAccessorTerrain.cpp:1073-1089),
splat generation ``CTerrain::RAW_GenerateSplat`` (GameLib/AreaTerrain.cpp:646-768).

Headerless, row-major ``uint8``, always 258x258 = 66,564 bytes.

Padding convention
------------------
The tile grid is 2x the terrain-cell grid: 256x256 usable tiles per sectree
(1 tile = 100 world units = 1 m).  Stored as 258x258 -- a one-tile border on
each edge duplicating the neighbour sectors' edge tiles, needed because splat
alpha generation samples all 8 neighbours.  Logical tile ``(tx, ty)`` with
``tx, ty in [-1, 256]`` is ``raw[(ty + 1) * 258 + (tx + 1)]``; the usable
window is ``raw[1:257, 1:257]``.

Splat semantics
---------------
A byte is an index into the map's TextureSet.  **0 = eraser/blank** and is
never splatted (all splat loops start at 1, AreaTerrain.cpp:557,656); 1..255
are texture slots (``MAXTERRAINTEXTURES = 256`` = 255 usable + eraser).
Higher indices paint over lower ones (painter's order = index order).
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "RAW_SIZE",
    "TILE_SIZE",
    "TILE_SCALE",
    "ERASER",
    "MAX_TEXTURES",
    "FILE_SIZE",
    "TileMap",
    "read_tile",
    "write_tile",
    "new_blank",
    "splat_alpha",
]

RAW_SIZE = 258          # TILEMAP_RAW_XSIZE = 256 + 2
TILE_SIZE = 256         # TILEMAP_XSIZE = XSIZE * 2
TILE_SCALE = 100        # world units per tile (1 m)
ERASER = 0              # index 0 = blank, never splatted
MAX_TEXTURES = 256      # MAXTERRAINTEXTURES (255 usable + eraser)
FILE_SIZE = RAW_SIZE * RAW_SIZE     # 66,564


class TileMap:
    """258x258 ``uint8`` tile-index grid with its 1-tile border kept intact.

    ``trailing`` holds any bytes past the 66,564 the engine memcpys (the loader
    ignores them; ``<CORPUS>/gm_guild_build/000000/tile.raw`` ships 3 extra
    ``0x02`` bytes).  They are re-emitted so such files still round-trip.
    """

    __slots__ = ("raw", "trailing")

    def __init__(self, raw, trailing=b""):
        raw = np.asarray(raw, dtype=np.uint8)
        if raw.shape != (RAW_SIZE, RAW_SIZE):
            raise ValueError("tile raw must be %dx%d, got %r" % (RAW_SIZE, RAW_SIZE, raw.shape))
        self.raw = raw
        self.trailing = bytes(trailing)

    # --- views -------------------------------------------------------------
    @property
    def tiles(self):
        """256x256 view of the usable tile window (border stripped)."""
        return self.raw[1:1 + TILE_SIZE, 1:1 + TILE_SIZE]

    def get(self, tx, ty):
        """Sample logical tile ``(tx, ty)``, ``tx``/``ty`` in ``[-1, 256]``."""
        if not (-1 <= tx <= TILE_SIZE) or not (-1 <= ty <= TILE_SIZE):
            raise IndexError("tile (%d, %d) outside [-1, %d]" % (tx, ty, TILE_SIZE))
        return int(self.raw[ty + 1, tx + 1])

    def set(self, tx, ty, value):
        if not (-1 <= tx <= TILE_SIZE) or not (-1 <= ty <= TILE_SIZE):
            raise IndexError("tile (%d, %d) outside [-1, %d]" % (tx, ty, TILE_SIZE))
        self.raw[ty + 1, tx + 1] = value

    # --- splat helpers -----------------------------------------------------
    def used_indices(self, include_border=True):
        """Sorted texture indices actually referenced (eraser 0 excluded)."""
        grid = self.raw if include_border else self.tiles
        idx = np.unique(grid)
        return [int(i) for i in idx if i != ERASER]

    def coverage(self, include_border=False):
        """``{index: tile_count}`` for the usable window (or the full raw)."""
        grid = self.raw if include_border else self.tiles
        vals, counts = np.unique(grid, return_counts=True)
        return {int(v): int(c) for v, c in zip(vals, counts)}

    def splat_alpha(self, index):
        """258x258 ``uint8`` alpha layer for texture ``index`` (engine rule)."""
        return splat_alpha(self.raw, index)

    def top_index_image(self):
        """256x256 array of the visible (highest) index per tile."""
        return self.tiles.copy()

    # --- serialisation -----------------------------------------------------
    @classmethod
    def from_bytes(cls, data):
        if len(data) < FILE_SIZE:
            raise ValueError("tile.raw must be >= %d bytes, got %d" % (FILE_SIZE, len(data)))
        grid = np.frombuffer(data, dtype=np.uint8, count=FILE_SIZE).reshape(RAW_SIZE, RAW_SIZE)
        return cls(grid.copy(), trailing=bytes(data[FILE_SIZE:]))

    def to_bytes(self):
        return self.raw.astype(np.uint8, copy=False).tobytes() + self.trailing

    def __eq__(self, other):
        return (isinstance(other, TileMap) and np.array_equal(self.raw, other.raw)
                and self.trailing == other.trailing)

    def __repr__(self):
        return "TileMap(indices=%r)" % (self.used_indices(),)


def splat_alpha(raw, index):
    """Alpha map for one texture index, per ``RAW_GenerateSplat``.

    ``0xFF`` where ``tile == index``; where ``tile > index``, also ``0xFF`` if
    any of the 8 neighbours equals ``index`` (the 1-texel bleed that hides
    seams); ``0x00`` elsewhere.  Result is 258x258, matching the engine's
    pre-downsample alpha buffer.
    """
    raw = np.asarray(raw, dtype=np.uint8)
    if index == ERASER:
        raise ValueError("index 0 is the eraser and is never splatted")
    eq = raw == index
    alpha = eq.copy()
    higher = raw > index
    neigh = np.zeros_like(eq)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            shifted = np.zeros_like(eq)
            ys = slice(max(0, dy), raw.shape[0] + min(0, dy))
            xs = slice(max(0, dx), raw.shape[1] + min(0, dx))
            yd = slice(max(0, -dy), raw.shape[0] + min(0, -dy))
            xd = slice(max(0, -dx), raw.shape[1] + min(0, -dx))
            shifted[yd, xd] = eq[ys, xs]
            neigh |= shifted
    alpha |= higher & neigh
    return (alpha.astype(np.uint8)) * 255


def new_blank(value=ERASER):
    return TileMap(np.full((RAW_SIZE, RAW_SIZE), value, dtype=np.uint8))


def read_tile(path):
    with open(path, "rb") as fh:
        return TileMap.from_bytes(fh.read())


def write_tile(path, tilemap):
    if not isinstance(tilemap, TileMap):
        tilemap = TileMap(tilemap)
    with open(path, "wb") as fh:
        fh.write(tilemap.to_bytes())

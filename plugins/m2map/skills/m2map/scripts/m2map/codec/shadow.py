"""``shadowmap.raw`` + ``shadowmap.dds`` -- baked terrain shadows.

Spec: reference/mapformat/shadowmap.md
Engine: ``CTerrain::LoadShadowMap`` (GameLib/AreaTerrain.cpp:104-130), decode
``PRTerrainLib/Terrain.cpp:298-318``, save ``SaveShadowFromD3DTexture9``
(WorldEditor/DataCtrl/MapAccessorTerrain.cpp:1284-1411).

``shadowmap.raw``: headerless 256x256 ``uint16`` little-endian = 131,072 bytes
(strictly validated by the loader), **RGB555** -- bit 15 unused, bits 14..10 R,
9..5 G, 4..0 B.  The in-source "R5G6B5" comment is wrong; the editor writes
``((r>>3)<<10) | ((g>>3)<<5) | (b>>3)`` (MapAccessorTerrain.cpp:1394).  Row 0
is the north edge.  Missing file = unshadowed (all 0xFFFF).

``shadowmap.dds`` is the GPU-side copy of the same 256x256 image; it is a plain
DDS and its encoding varies in the wild (DXT1 with and without mips, DXT5,
24-bit RGB) -- see :mod:`m2map.codec.dds`.  Both files must stay in sync: the
client renders with the .dds and point-samples the .raw.
"""

from __future__ import annotations

import numpy as np

from . import dds as _dds

__all__ = [
    "SIZE",
    "FILE_SIZE",
    "UNSHADOWED",
    "ShadowMap",
    "read_shadow_raw",
    "write_shadow_raw",
    "read_shadow_dds",
    "write_shadow_dds",
    "new_blank",
    "rgb555_to_rgb",
    "rgb_to_rgb555",
    "engine_sample_color",
]

SIZE = 256
FILE_SIZE = SIZE * SIZE * 2     # 131,072
UNSHADOWED = 0xFFFF             # white


def rgb555_to_rgb(words):
    """(H, W) uint16 RGB555 -> (H, W, 3) uint8 (channels expanded ``<< 3``)."""
    w = np.asarray(words, dtype=np.uint16).astype(np.uint32)
    r = ((w >> 10) & 0x1F) << 3
    g = ((w >> 5) & 0x1F) << 3
    b = (w & 0x1F) << 3
    return np.stack([r, g, b], axis=-1).astype(np.uint8)


def rgb_to_rgb555(rgb):
    """(H, W, 3|4) uint8 -> (H, W) uint16 RGB555, exactly as the editor packs it."""
    a = np.asarray(rgb, dtype=np.uint8).astype(np.uint32)
    return (((a[..., 0] >> 3) << 10) | ((a[..., 1] >> 3) << 5)
            | (a[..., 2] >> 3)).astype(np.uint16)


def engine_sample_color(word):
    """Replicate ``GetShadowMapColor``: ``(G<<16) | (G<<8) | R`` (Terrain.cpp:317).

    The client's CPU sampler duplicates green into red and drops blue.  Only
    useful when mimicking engine behaviour byte-for-byte; for display use
    :func:`rgb555_to_rgb`.
    """
    word = int(word)
    r = ((word >> 10) & 0x1F) << 3
    g = ((word >> 5) & 0x1F) << 3
    return (g << 16) | (g << 8) | r


class ShadowMap:
    """256x256 RGB555 shadow grid (``shadowmap.raw``)."""

    __slots__ = ("words",)

    def __init__(self, words):
        words = np.asarray(words, dtype="<u2")
        if words.shape != (SIZE, SIZE):
            raise ValueError("shadowmap must be %dx%d, got %r" % (SIZE, SIZE, words.shape))
        self.words = words

    def to_rgb(self):
        return rgb555_to_rgb(self.words)

    def luminance(self):
        """0..255 shadow intensity per texel (mean of the three channels)."""
        return self.to_rgb().mean(axis=2).round().astype(np.uint8)

    @classmethod
    def from_rgb(cls, rgb):
        return cls(rgb_to_rgb555(rgb))

    @classmethod
    def from_bytes(cls, data):
        if len(data) != FILE_SIZE:
            raise ValueError("shadowmap.raw must be %d bytes, got %d" % (FILE_SIZE, len(data)))
        return cls(np.frombuffer(data, dtype="<u2").reshape(SIZE, SIZE).copy())

    def to_bytes(self):
        return self.words.astype("<u2", copy=False).tobytes()

    def __eq__(self, other):
        return isinstance(other, ShadowMap) and np.array_equal(self.words, other.words)

    def __repr__(self):
        return "ShadowMap(mean_luma=%.1f)" % float(self.luminance().mean())


def new_blank(value=UNSHADOWED):
    return ShadowMap(np.full((SIZE, SIZE), value, dtype="<u2"))


def read_shadow_raw(path):
    with open(path, "rb") as fh:
        return ShadowMap.from_bytes(fh.read())


def write_shadow_raw(path, shadowmap):
    if not isinstance(shadowmap, ShadowMap):
        shadowmap = ShadowMap(shadowmap)
    with open(path, "wb") as fh:
        fh.write(shadowmap.to_bytes())


def read_shadow_dds(path):
    """Read ``shadowmap.dds`` (any encoding) as a :class:`m2map.codec.dds.DDS`."""
    return _dds.read_dds(path)


def write_shadow_dds(path, image):
    _dds.write_dds(path, image)

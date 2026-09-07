"""DDS container + pixel codecs shared by ``minimap.dds`` and ``shadowmap.dds``.

Both map DDS files are plain ``D3DXSaveSurfaceToFile`` output, but the encoding
varies across the shipped corpus -- the specs' "X8R8G8B8, 262,272 bytes" is
*not* what Ymir actually shipped.  Measured over <CORPUS> (142 maps, 1332
minimap.dds + 1332 shadowmap.dds):

===============================  =========  =====================
encoding                         bytes      files
===============================  =========  =====================
DXT1, 256x256, no mips           32,896     1270 minimap, 1 shadowmap
DXT1, 256x256, 9 mips            43,832     62 minimap, 1328 shadowmap
DXT5, 256x256, 9 mips            87,536     2 shadowmap
R8G8B8 (24bpp), 256x256, 9 mips  262,271    1 shadowmap
===============================  =========  =====================

So: parse the header, never assume the format.  This module implements
DXT1/DXT3/DXT5 and arbitrary mask-based uncompressed formats (16/24/32 bpp,
X8R8G8B8, A8R8G8B8, R8G8B8, R5G6B5, A1R5G5B5, A4R4G4B4, ...) in numpy, because
Pillow cannot write DXT and cannot read every one of these variants.

:class:`DDS` keeps the *whole* payload (all mip levels) verbatim, so reading and
re-writing an untouched file is byte-identical; the header is rebuilt field by
field from the parsed values rather than copied, which makes the round-trip a
real test of the parser.
"""

from __future__ import annotations

import struct

import numpy as np

__all__ = [
    "MAGIC",
    "HEADER_SIZE",
    "DDPF_ALPHAPIXELS",
    "DDPF_ALPHA",
    "DDPF_FOURCC",
    "DDPF_RGB",
    "DDPF_LUMINANCE",
    "DDS",
    "read_dds",
    "write_dds",
    "decode_dxt",
    "encode_dxt",
    "decode_uncompressed",
    "encode_uncompressed",
    "X8R8G8B8",
    "A8R8G8B8",
    "R8G8B8",
    "R5G6B5",
    "A1R5G5B5",
]

MAGIC = b"DDS "
HEADER_SIZE = 128       # magic + 124-byte DDSURFACEDESC2

DDSD_CAPS = 0x1
DDSD_HEIGHT = 0x2
DDSD_WIDTH = 0x4
DDSD_PITCH = 0x8
DDSD_PIXELFORMAT = 0x1000
DDSD_MIPMAPCOUNT = 0x20000
DDSD_LINEARSIZE = 0x80000

DDPF_ALPHAPIXELS = 0x1
DDPF_ALPHA = 0x2
DDPF_FOURCC = 0x4
DDPF_RGB = 0x40
DDPF_LUMINANCE = 0x20000

DDSCAPS_COMPLEX = 0x8
DDSCAPS_TEXTURE = 0x1000
DDSCAPS_MIPMAP = 0x400

# (pf_flags, fourcc, bpp, rmask, gmask, bmask, amask)
X8R8G8B8 = (DDPF_RGB, b"\0\0\0\0", 32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0x00000000)
A8R8G8B8 = (DDPF_RGB | DDPF_ALPHAPIXELS, b"\0\0\0\0", 32,
            0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
R8G8B8 = (DDPF_RGB, b"\0\0\0\0", 24, 0x00FF0000, 0x0000FF00, 0x000000FF, 0x00000000)
R5G6B5 = (DDPF_RGB, b"\0\0\0\0", 16, 0xF800, 0x07E0, 0x001F, 0x0000)
A1R5G5B5 = (DDPF_RGB | DDPF_ALPHAPIXELS, b"\0\0\0\0", 16, 0x7C00, 0x03E0, 0x001F, 0x8000)


# ---------------------------------------------------------------------------
# block-compressed codecs
# ---------------------------------------------------------------------------
def _unpack565(v):
    v = v.astype(np.uint32)
    r = ((v >> 11) & 0x1F).astype(np.uint32)
    g = ((v >> 5) & 0x3F).astype(np.uint32)
    b = (v & 0x1F).astype(np.uint32)
    r = (r << 3) | (r >> 2)
    g = (g << 2) | (g >> 4)
    b = (b << 3) | (b >> 2)
    return r.astype(np.uint8), g.astype(np.uint8), b.astype(np.uint8)


def _pack565(rgb):
    r = (rgb[..., 0].astype(np.uint32) >> 3) & 0x1F
    g = (rgb[..., 1].astype(np.uint32) >> 2) & 0x3F
    b = (rgb[..., 2].astype(np.uint32) >> 3) & 0x1F
    return ((r << 11) | (g << 5) | b).astype(np.uint16)


def _blocks_to_image(pixels, width, height, bw, bh):
    """(nblocks, 16, 4) uint8 -> (height, width, 4) uint8."""
    img = pixels.reshape(bh, bw, 4, 4, 4).transpose(0, 2, 1, 3, 4)
    img = img.reshape(bh * 4, bw * 4, 4)
    return img[:height, :width].copy()


def _image_to_blocks(rgba, bw, bh):
    """(height, width, 4) -> (nblocks, 16, 4) with edge padding."""
    h, w = rgba.shape[:2]
    padded = np.zeros((bh * 4, bw * 4, 4), dtype=np.uint8)
    padded[:h, :w] = rgba
    if bh * 4 > h:
        padded[h:, :w] = rgba[h - 1:h]
    if bw * 4 > w:
        padded[:, w:] = padded[:, w - 1:w]
    blocks = padded.reshape(bh, 4, bw, 4, 4).transpose(0, 2, 1, 3, 4)
    return blocks.reshape(bh * bw, 16, 4)


def decode_dxt(data, width, height, fourcc):
    """Decode a DXT1/DXT2/DXT3/DXT4/DXT5 surface to ``(h, w, 4)`` RGBA uint8."""
    fourcc = bytes(fourcc)
    bw, bh = (width + 3) // 4, (height + 3) // 4
    nb = bw * bh
    block_bytes = 8 if fourcc == b"DXT1" else 16
    need = nb * block_bytes
    if len(data) < need:
        raise ValueError("%s surface needs %d bytes, got %d"
                         % (fourcc.decode("ascii", "replace"), need, len(data)))
    raw = np.frombuffer(data[:need], dtype=np.uint8).reshape(nb, block_bytes)

    color_off = 0 if fourcc == b"DXT1" else 8
    c = raw[:, color_off:color_off + 8].astype(np.uint32)
    c0 = c[:, 0] | (c[:, 1] << 8)
    c1 = c[:, 2] | (c[:, 3] << 8)
    bits = c[:, 4] | (c[:, 5] << 8) | (c[:, 6] << 16) | (c[:, 7] << 24)

    r0, g0, b0 = _unpack565(c0)
    r1, g1, b1 = _unpack565(c1)
    palette = np.zeros((nb, 4, 4), dtype=np.uint8)
    palette[:, 0, 0], palette[:, 0, 1], palette[:, 0, 2] = r0, g0, b0
    palette[:, 1, 0], palette[:, 1, 1], palette[:, 1, 2] = r1, g1, b1
    palette[:, :2, 3] = 255

    f0 = np.stack([r0, g0, b0], axis=1).astype(np.uint16)
    f1 = np.stack([r1, g1, b1], axis=1).astype(np.uint16)
    four = (c0 > c1) if fourcc == b"DXT1" else np.ones(nb, dtype=bool)
    c2_four = ((2 * f0 + f1 + 1) // 3).astype(np.uint8)
    c3_four = ((f0 + 2 * f1 + 1) // 3).astype(np.uint8)
    c2_three = ((f0 + f1) // 2).astype(np.uint8)
    palette[:, 2, :3] = np.where(four[:, None], c2_four, c2_three)
    palette[:, 3, :3] = np.where(four[:, None], c3_four, 0)
    palette[:, 2, 3] = 255
    palette[:, 3, 3] = np.where(four, 255, 0).astype(np.uint8)

    shifts = (2 * np.arange(16)).astype(np.uint32)
    idx = ((bits[:, None] >> shifts[None, :]) & 3).astype(np.intp)
    pixels = palette[np.arange(nb)[:, None], idx]          # (nb, 16, 4)

    if fourcc in (b"DXT2", b"DXT3"):
        a = raw[:, :8].astype(np.uint64)
        abits = np.zeros(nb, dtype=np.uint64)
        for i in range(8):
            abits |= a[:, i] << np.uint64(8 * i)
        ashift = (4 * np.arange(16)).astype(np.uint64)
        nib = ((abits[:, None] >> ashift[None, :]) & np.uint64(0xF)).astype(np.uint8)
        pixels[:, :, 3] = nib * 17
    elif fourcc in (b"DXT4", b"DXT5"):
        a0 = raw[:, 0].astype(np.uint16)
        a1 = raw[:, 1].astype(np.uint16)
        abits = np.zeros(nb, dtype=np.uint64)
        for i in range(6):
            abits |= raw[:, 2 + i].astype(np.uint64) << np.uint64(8 * i)
        ashift = (3 * np.arange(16)).astype(np.uint64)
        aidx = ((abits[:, None] >> ashift[None, :]) & np.uint64(7)).astype(np.intp)
        apal = np.zeros((nb, 8), dtype=np.uint8)
        apal[:, 0] = a0
        apal[:, 1] = a1
        eight = a0 > a1
        for i in range(1, 7):
            v8 = ((7 - i) * a0 + i * a1) // 7
            apal[:, i + 1] = np.where(eight, v8, 0)
        for i in range(1, 5):
            v6 = ((5 - i) * a0 + i * a1) // 5
            apal[:, i + 1] = np.where(eight, apal[:, i + 1], v6)
        apal[:, 6] = np.where(eight, apal[:, 6], 0)
        apal[:, 7] = np.where(eight, apal[:, 7], 255)
        pixels[:, :, 3] = apal[np.arange(nb)[:, None], aidx]

    return _blocks_to_image(pixels, width, height, bw, bh)


def encode_dxt(rgba, fourcc):
    """Encode ``(h, w, 4)`` RGBA to DXT1/DXT3/DXT5 (bounding-box endpoint fit).

    Lossy, and not bit-compatible with any particular D3DX/NVTT encoder -- it is
    here so a modified minimap/shadowmap can be written back at all.  Preserve
    ``DDS.data`` verbatim whenever the pixels were not modified.
    """
    fourcc = bytes(fourcc)
    rgba = np.asarray(rgba, dtype=np.uint8)
    h, w = rgba.shape[:2]
    bw, bh = (w + 3) // 4, (h + 3) // 4
    blocks = _image_to_blocks(rgba, bw, bh).astype(np.int32)      # (nb, 16, 4)
    nb = blocks.shape[0]
    rgb = blocks[:, :, :3]
    lo = rgb.min(axis=1)
    hi = rgb.max(axis=1)

    c0 = _pack565(hi.astype(np.uint8))
    c1 = _pack565(lo.astype(np.uint8))
    # DXT1 needs c0 > c1 for the opaque 4-colour mode; equal endpoints are a
    # flat block, which decodes correctly with index 0 everywhere.
    swap = c0 < c1
    c0, c1 = np.where(swap, c1, c0), np.where(swap, c0, c1)

    r0, g0, b0 = _unpack565(c0)
    r1, g1, b1 = _unpack565(c1)
    f0 = np.stack([r0, g0, b0], axis=1).astype(np.int32)
    f1 = np.stack([r1, g1, b1], axis=1).astype(np.int32)
    pal = np.stack([f0, f1, (2 * f0 + f1 + 1) // 3, (f0 + 2 * f1 + 1) // 3], axis=1)  # (nb,4,3)
    d = ((rgb[:, :, None, :] - pal[:, None, :, :]) ** 2).sum(axis=3)                  # (nb,16,4)
    idx = d.argmin(axis=2).astype(np.uint32)
    bits = np.zeros(nb, dtype=np.uint32)
    for i in range(16):
        bits |= idx[:, i] << np.uint32(2 * i)

    color_block = np.zeros((nb, 8), dtype=np.uint8)
    color_block[:, 0] = c0 & 0xFF
    color_block[:, 1] = (c0 >> 8) & 0xFF
    color_block[:, 2] = c1 & 0xFF
    color_block[:, 3] = (c1 >> 8) & 0xFF
    for i in range(4):
        color_block[:, 4 + i] = (bits >> np.uint32(8 * i)) & 0xFF

    if fourcc == b"DXT1":
        return color_block.tobytes()

    alpha = blocks[:, :, 3]
    if fourcc in (b"DXT2", b"DXT3"):
        nib = ((alpha + 8) // 17).clip(0, 15).astype(np.uint64)
        abits = np.zeros(nb, dtype=np.uint64)
        for i in range(16):
            abits |= nib[:, i] << np.uint64(4 * i)
        ablock = np.zeros((nb, 8), dtype=np.uint8)
        for i in range(8):
            ablock[:, i] = ((abits >> np.uint64(8 * i)) & np.uint64(0xFF)).astype(np.uint8)
        return np.concatenate([ablock, color_block], axis=1).tobytes()

    if fourcc in (b"DXT4", b"DXT5"):
        a0 = alpha.max(axis=1).astype(np.int32)
        a1 = alpha.min(axis=1).astype(np.int32)
        span = np.maximum(a0 - a1, 1)
        # 8-alpha mode palette: a0, a1, then 6 interpolated steps
        t = ((a0[:, None] - alpha) * 7 + span[:, None] // 2) // span[:, None]
        aidx = np.zeros_like(t)
        aidx[t == 0] = 0
        aidx[t == 7] = 1
        mid = (t > 0) & (t < 7)
        aidx[mid] = t[mid] + 1
        aidx[(a0 == a1)[:, None].repeat(16, axis=1)] = 0
        aidx = aidx.astype(np.uint64)
        abits = np.zeros(nb, dtype=np.uint64)
        for i in range(16):
            abits |= aidx[:, i] << np.uint64(3 * i)
        ablock = np.zeros((nb, 8), dtype=np.uint8)
        ablock[:, 0] = a0.astype(np.uint8)
        ablock[:, 1] = a1.astype(np.uint8)
        for i in range(6):
            ablock[:, 2 + i] = ((abits >> np.uint64(8 * i)) & np.uint64(0xFF)).astype(np.uint8)
        return np.concatenate([ablock, color_block], axis=1).tobytes()

    raise ValueError("unsupported FourCC %r" % (fourcc,))


# ---------------------------------------------------------------------------
# uncompressed codecs
# ---------------------------------------------------------------------------
def _mask_info(mask):
    if mask == 0:
        return 0, 0
    shift = (mask & -mask).bit_length() - 1
    bits = bin(mask >> shift).count("1")
    return shift, bits


def _expand_simple(value, bits):
    """Channel expansion by ``round(v * 255 / max)`` (exact for 1/4/5/6/8 bits)."""
    if bits == 0:
        return None
    maxv = (1 << bits) - 1
    return ((value.astype(np.uint32) * 255 + maxv // 2) // maxv).astype(np.uint8)


def decode_uncompressed(data, width, height, bpp, rmask, gmask, bmask, amask, pitch=None):
    """Decode a mask-described uncompressed surface to ``(h, w, 4)`` RGBA."""
    if bpp not in (8, 16, 24, 32):
        raise ValueError("unsupported bit depth %d" % bpp)
    row_bytes = width * bpp // 8
    stride = pitch if pitch else row_bytes
    need = stride * height
    if len(data) < need:
        raise ValueError("surface needs %d bytes, got %d" % (need, len(data)))
    buf = np.frombuffer(data[:need], dtype=np.uint8).reshape(height, stride)[:, :row_bytes]

    if bpp == 32:
        px = buf.reshape(height, width, 4).astype(np.uint32)
        val = px[..., 0] | (px[..., 1] << 8) | (px[..., 2] << 16) | (px[..., 3] << 24)
    elif bpp == 24:
        px = buf.reshape(height, width, 3).astype(np.uint32)
        val = px[..., 0] | (px[..., 1] << 8) | (px[..., 2] << 16)
    elif bpp == 16:
        px = buf.reshape(height, width, 2).astype(np.uint32)
        val = px[..., 0] | (px[..., 1] << 8)
    else:
        val = buf.reshape(height, width).astype(np.uint32)

    out = np.zeros((height, width, 4), dtype=np.uint8)
    for ch, mask in enumerate((rmask, gmask, bmask)):
        shift, bits = _mask_info(mask)
        if bits:
            out[..., ch] = _expand_simple((val & mask) >> shift, bits)
    shift, bits = _mask_info(amask)
    out[..., 3] = _expand_simple((val & amask) >> shift, bits) if bits else 255
    return out


def encode_uncompressed(rgba, bpp, rmask, gmask, bmask, amask):
    """Encode ``(h, w, 4)`` RGBA into a mask-described uncompressed surface."""
    rgba = np.asarray(rgba, dtype=np.uint8)
    height, width = rgba.shape[:2]
    val = np.zeros((height, width), dtype=np.uint32)
    for ch, mask in enumerate((rmask, gmask, bmask, amask)):
        shift, bits = _mask_info(mask)
        if not bits:
            continue
        maxv = (1 << bits) - 1
        q = (rgba[..., ch].astype(np.uint32) * maxv + 127) // 255
        val |= (q << shift) & mask
    if bpp == 32:
        px = np.stack([val & 0xFF, (val >> 8) & 0xFF, (val >> 16) & 0xFF,
                       (val >> 24) & 0xFF], axis=2)
    elif bpp == 24:
        px = np.stack([val & 0xFF, (val >> 8) & 0xFF, (val >> 16) & 0xFF], axis=2)
    elif bpp == 16:
        px = np.stack([val & 0xFF, (val >> 8) & 0xFF], axis=2)
    elif bpp == 8:
        px = val[..., None] & 0xFF
    else:
        raise ValueError("unsupported bit depth %d" % bpp)
    return px.astype(np.uint8).tobytes()


# ---------------------------------------------------------------------------
# container
# ---------------------------------------------------------------------------
class DDS:
    """A DDS file: fully parsed header + verbatim payload (all mip levels)."""

    __slots__ = ("flags", "height", "width", "pitch_or_linear", "depth", "mipmaps",
                 "reserved1", "pf_size", "pf_flags", "fourcc", "bpp",
                 "rmask", "gmask", "bmask", "amask",
                 "caps", "caps2", "caps3", "caps4", "reserved2", "data", "header_size")

    def __init__(self, **kw):
        for name in self.__slots__:
            setattr(self, name, kw.get(name))

    # --- properties --------------------------------------------------------
    @property
    def compressed(self):
        return bool(self.pf_flags & DDPF_FOURCC)

    @property
    def format_name(self):
        if self.compressed:
            return self.fourcc.decode("ascii", "replace").strip("\0")
        names = {
            (32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0x00000000): "X8R8G8B8",
            (32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000): "A8R8G8B8",
            (24, 0x00FF0000, 0x0000FF00, 0x000000FF, 0x00000000): "R8G8B8",
            (16, 0xF800, 0x07E0, 0x001F, 0x0000): "R5G6B5",
            (16, 0x7C00, 0x03E0, 0x001F, 0x8000): "A1R5G5B5",
            (16, 0x7C00, 0x03E0, 0x001F, 0x0000): "X1R5G5B5",
            (16, 0x0F00, 0x00F0, 0x000F, 0xF000): "A4R4G4B4",
        }
        key = (self.bpp, self.rmask, self.gmask, self.bmask, self.amask)
        return names.get(key, "RGB%d(%08X/%08X/%08X/%08X)" % key)

    @property
    def mip_count(self):
        return max(1, int(self.mipmaps or 0))

    def level_size(self, level=0):
        """Byte size of mip ``level`` of this surface."""
        w = max(1, self.width >> level)
        h = max(1, self.height >> level)
        if self.compressed:
            bb = 8 if self.fourcc == b"DXT1" else 16
            return ((w + 3) // 4) * ((h + 3) // 4) * bb
        return ((w * self.bpp + 7) // 8) * h

    def level_offset(self, level=0):
        return sum(self.level_size(i) for i in range(level))

    def expected_data_size(self):
        return sum(self.level_size(i) for i in range(self.mip_count))

    # --- pixels ------------------------------------------------------------
    def to_rgba(self, level=0):
        """Decode mip ``level`` to an ``(h, w, 4)`` uint8 RGBA array."""
        off = self.level_offset(level)
        chunk = self.data[off:off + self.level_size(level)]
        w = max(1, self.width >> level)
        h = max(1, self.height >> level)
        if self.compressed:
            if not self.fourcc.startswith(b"DXT"):
                raise ValueError("unsupported compressed format %r" % (self.fourcc,))
            return decode_dxt(chunk, w, h, self.fourcc)
        return decode_uncompressed(chunk, w, h, self.bpp,
                                   self.rmask, self.gmask, self.bmask, self.amask)

    def set_rgba(self, rgba, level=0):
        """Replace mip ``level`` with encoded pixels (same format, same size)."""
        rgba = np.asarray(rgba, dtype=np.uint8)
        w = max(1, self.width >> level)
        h = max(1, self.height >> level)
        if rgba.shape[:2] != (h, w):
            raise ValueError("level %d expects %dx%d, got %r" % (level, w, h, rgba.shape[:2]))
        if rgba.ndim == 3 and rgba.shape[2] == 3:
            rgba = np.concatenate([rgba, np.full((h, w, 1), 255, np.uint8)], axis=2)
        if self.compressed:
            blob = encode_dxt(rgba, self.fourcc)
        else:
            blob = encode_uncompressed(rgba, self.bpp, self.rmask, self.gmask,
                                       self.bmask, self.amask)
        off = self.level_offset(level)
        size = self.level_size(level)
        if len(blob) != size:
            raise ValueError("encoded %d bytes, level holds %d" % (len(blob), size))
        self.data = self.data[:off] + blob + self.data[off + size:]

    # --- serialisation -----------------------------------------------------
    @classmethod
    def from_bytes(cls, blob):
        if len(blob) < HEADER_SIZE or blob[:4] != MAGIC:
            raise ValueError("not a DDS file")
        (size, flags, height, width, pitch, depth, mipmaps) = struct.unpack_from("<7I", blob, 4)
        reserved1 = struct.unpack_from("<11I", blob, 32)
        (pf_size, pf_flags) = struct.unpack_from("<2I", blob, 76)
        fourcc = blob[84:88]
        (bpp, rmask, gmask, bmask, amask) = struct.unpack_from("<5I", blob, 88)
        (caps, caps2, caps3, caps4, reserved2) = struct.unpack_from("<5I", blob, 108)
        if size != 124:
            raise ValueError("bad DDS header size %d" % size)
        if fourcc == b"DX10":
            raise ValueError("DX10-extended DDS is not used by Metin2 maps")
        return cls(header_size=size, flags=flags, height=height, width=width,
                   pitch_or_linear=pitch, depth=depth, mipmaps=mipmaps,
                   reserved1=reserved1, pf_size=pf_size, pf_flags=pf_flags,
                   fourcc=fourcc, bpp=bpp, rmask=rmask, gmask=gmask, bmask=bmask,
                   amask=amask, caps=caps, caps2=caps2, caps3=caps3, caps4=caps4,
                   reserved2=reserved2, data=blob[HEADER_SIZE:])

    def to_bytes(self):
        out = bytearray(MAGIC)
        out += struct.pack("<7I", self.header_size, self.flags, self.height, self.width,
                           self.pitch_or_linear, self.depth, self.mipmaps)
        out += struct.pack("<11I", *self.reserved1)
        out += struct.pack("<2I", self.pf_size, self.pf_flags)
        out += self.fourcc
        out += struct.pack("<5I", self.bpp, self.rmask, self.gmask, self.bmask, self.amask)
        out += struct.pack("<5I", self.caps, self.caps2, self.caps3, self.caps4, self.reserved2)
        out += self.data
        return bytes(out)

    # --- construction ------------------------------------------------------
    @classmethod
    def from_rgba(cls, rgba, fmt=X8R8G8B8, mipmaps=1):
        """Build a DDS from an ``(h, w, 4)`` RGBA array.

        ``fmt`` is either one of the mask tuples in this module
        (``X8R8G8B8`` ...) or a FourCC such as ``b"DXT1"``/``b"DXT5"``.
        Mip levels are box-filtered when ``mipmaps`` > 1 (``0`` = full chain).
        """
        rgba = np.asarray(rgba, dtype=np.uint8)
        if rgba.ndim == 3 and rgba.shape[2] == 3:
            rgba = np.concatenate(
                [rgba, np.full(rgba.shape[:2] + (1,), 255, np.uint8)], axis=2)
        h, w = rgba.shape[:2]
        if isinstance(fmt, (bytes, bytearray)):
            pf_flags, fourcc, bpp = DDPF_FOURCC, bytes(fmt), 0
            rmask = gmask = bmask = amask = 0
        else:
            pf_flags, fourcc, bpp, rmask, gmask, bmask, amask = fmt
        levels = []
        cur = rgba
        n = mipmaps if mipmaps else 64
        for i in range(n):
            levels.append(cur)
            cw, ch = max(1, cur.shape[1] // 2), max(1, cur.shape[0] // 2)
            if cur.shape[0] == 1 and cur.shape[1] == 1:
                break
            cur = cur.reshape(ch, cur.shape[0] // ch, cw, cur.shape[1] // cw, 4)
            cur = cur.mean(axis=(1, 3)).round().astype(np.uint8)
        payload = bytearray()
        for lv in levels:
            if pf_flags & DDPF_FOURCC:
                payload += encode_dxt(lv, fourcc)
            else:
                payload += encode_uncompressed(lv, bpp, rmask, gmask, bmask, amask)
        flags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT
        caps = DDSCAPS_TEXTURE
        if len(levels) > 1:
            flags |= DDSD_MIPMAPCOUNT
            caps |= DDSCAPS_COMPLEX | DDSCAPS_MIPMAP
        if pf_flags & DDPF_FOURCC:
            flags |= DDSD_LINEARSIZE
            bb = 8 if fourcc == b"DXT1" else 16
            pitch = ((w + 3) // 4) * ((h + 3) // 4) * bb
        else:
            flags |= DDSD_PITCH
            pitch = (w * bpp + 7) // 8
        return cls(header_size=124, flags=flags, height=h, width=w,
                   pitch_or_linear=pitch, depth=0, mipmaps=len(levels),
                   reserved1=(0,) * 11, pf_size=32, pf_flags=pf_flags, fourcc=fourcc,
                   bpp=bpp, rmask=rmask, gmask=gmask, bmask=bmask, amask=amask,
                   caps=caps, caps2=0, caps3=0, caps4=0, reserved2=0, data=bytes(payload))

    def __repr__(self):
        return "DDS(%dx%d, %s, mips=%d, %d bytes)" % (
            self.width, self.height, self.format_name, self.mip_count, len(self.data))


def read_dds(path):
    with open(path, "rb") as fh:
        return DDS.from_bytes(fh.read())


def write_dds(path, image):
    with open(path, "wb") as fh:
        fh.write(image.to_bytes())

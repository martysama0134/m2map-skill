"""``textureset/<name>.txt`` codec -- the terrain texture palette.

``tile.raw`` bytes index into this list.  Reader ``CTextureSet::Load``
(PRTerrainLib/TextureSet.cpp:25-94), writer ``CTextureSet::Save``
(TextureSet.cpp:244-276).

Rules taken from the source:

* **Slot 0 is the implicit eraser** -- ``Create()`` calls ``AddEmptyTexture()``
  before any block is read (TextureSet.cpp:22, :48), and ``Save`` writes
  ``GetTextureCount()-1``.  So ``TextureCount`` counts *usable* textures only
  and ``tile.raw`` byte 0 means "erased".
* Blocks are ``Texture%03d``, **1-based**: block *N* fills slot *N*
  (``_snprintf(..., "texture%03d", i + 1)``, TextureSet.cpp:58).
* Missing blocks are skipped and leave the slot empty (``continue``, :62) --
  the corpus really does this (``metin2_bayblacksand.txt`` has no
  ``Texture003``, ``metin2_guild_village.txt`` starts at ``Texture002``).
* ``MAXTERRAINTEXTURES`` is 256 including the eraser, so **255 usable** is the
  cap.
* A block is read positionally by index 0..7 -- filename, UScale, VScale,
  UOffset, VOffset, bSplat, Begin, End -- so any stray token inside a block
  shifts every later field.  ``metin2_test_zon.txt`` has a Korean comment
  after the filename, which makes the engine read UScale as 0.
* Render-time transform: ``scale = fTerrainTexCoordBase * UScale`` with
  ``fTerrainTexCoordBase = 1 / (PATCH_XSIZE * CELLSCALE) = 1 / (16 * 200)``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .textfile import (BlockItem, FlatDoc, KeyItem, atof, atoi, encode, fmt_f,
                       parse_flat, quote, SourcePreserving)

__all__ = ["TextureEntry", "TextureSet", "MAX_TERRAIN_TEXTURES",
           "MAX_USABLE_TEXTURES", "TERRAIN_TEXCOORD_BASE"]

CRLF = "\r\n"

MAX_TERRAIN_TEXTURES = 256          # including slot 0, the eraser
MAX_USABLE_TEXTURES = 255
TERRAIN_TEXCOORD_BASE = 1.0 / (16 * 200)


@dataclass
class TextureEntry:
    """One palette slot.  ``b_splat``/``begin``/``end`` are parsed and stored
    by the engine but never read at render time."""

    filename: str = ""
    u_scale: float = 4.0
    v_scale: float = 4.0
    u_offset: float = 0.0
    v_offset: float = 0.0
    b_splat: int = 0
    begin: int = 0
    end: int = 0
    #: Tokens beyond index 7, if the source block carried junk.
    extra_tokens: List[str] = field(default_factory=list)

    @classmethod
    def from_tokens(cls, t) -> "TextureEntry":
        if len(t) < 8:
            raise ValueError("texture block needs 8 tokens, got %d" % len(t))
        return cls(filename=t[0], u_scale=atof(t[1]), v_scale=atof(t[2]),
                   u_offset=atof(t[3]), v_offset=atof(t[4]),
                   b_splat=atoi(t[5]),
                   begin=atoi(t[6]) & 0xFFFF, end=atoi(t[7]) & 0xFFFF,
                   extra_tokens=list(t[8:]))

    def render(self, index: int) -> str:
        out = ["Start Texture%03d" % index,
               "    " + quote(self.filename),
               "    " + fmt_f(self.u_scale),
               "    " + fmt_f(self.v_scale),
               "    " + fmt_f(self.u_offset),
               "    " + fmt_f(self.v_offset),
               "    %d" % self.b_splat,
               "    %d" % (self.begin & 0xFFFF),
               "    %d" % (self.end & 0xFFFF),
               "End Texture%03d" % index]
        return "".join(l + CRLF for l in out)

    @property
    def uv_scale(self):
        """Actual UV scale applied by the terrain shader."""
        return (TERRAIN_TEXCOORD_BASE * self.u_scale,
                TERRAIN_TEXCOORD_BASE * self.v_scale)


@dataclass
class TextureSet(SourcePreserving):
    """A parsed texture set.

    :attr:`slots` is indexed the way ``tile.raw`` is: ``slots[0]`` is always
    ``None`` (the eraser), ``slots[1..]`` hold textures, and a gap in the
    source leaves ``None`` behind.
    """

    slots: List[Optional[TextureEntry]] = field(default_factory=lambda: [None])
    declared_count: int = 0
    doc: Optional[FlatDoc] = None
    has_header_key: bool = True
    has_count_key: bool = True
    #: Blocks whose index is past ``TextureCount`` (never loaded), or repeated.
    ignored_blocks: List[str] = field(default_factory=list)

    # -- read --------------------------------------------------------------
    @classmethod
    def parse(cls, data, strict: bool = False) -> "TextureSet":
        doc = parse_flat(data)
        ts = cls(doc=doc)
        ts.has_header_key = doc.has("textureset")
        count = doc.get("texturecount")
        ts.has_count_key = count is not None
        if strict and not (ts.has_header_key and ts.has_count_key):
            raise ValueError("not a TextureSet script")
        ts.declared_count = atoi(count[0]) if count else 0
        ts.slots = [None] * (ts.declared_count + 1)
        by_key = {}
        for blk in doc.blocks:
            if blk.key in by_key:
                ts.ignored_blocks.append(blk.name)    # first wins
                continue
            by_key[blk.key] = blk
        for i in range(1, ts.declared_count + 1):
            blk = by_key.pop("texture%03d" % i, None)
            if blk is None:
                continue                              # engine: `continue`
            ts.slots[i] = TextureEntry.from_tokens(blk.values)
        ts.ignored_blocks += [b.name for b in by_key.values()]
        ts._snapshot()
        return ts

    @classmethod
    def load(cls, path, strict: bool = False) -> "TextureSet":
        with open(path, "rb") as fh:
            return cls.parse(fh.read(), strict=strict)

    # -- access ------------------------------------------------------------
    def __len__(self) -> int:
        """Usable texture count, i.e. what ``TextureCount`` should say."""
        return max(len(self.slots) - 1, 0)

    def get(self, tile_index: int) -> Optional[TextureEntry]:
        """Resolve a ``tile.raw`` byte; out of range renders the error texture."""
        if 0 <= tile_index < len(self.slots):
            return self.slots[tile_index]
        return None

    @property
    def textures(self) -> List[Optional[TextureEntry]]:
        """Slots 1..N (the eraser excluded)."""
        return self.slots[1:]

    def problems(self) -> List[str]:
        out = []
        if not self.has_header_key:
            out.append("missing TextureSet key -- CTextureSet::Load rejects it")
        if not self.has_count_key:
            out.append("missing TextureCount -- CTextureSet::Load rejects it")
        missing = [i for i in range(1, len(self.slots)) if self.slots[i] is None]
        if missing:
            out.append("empty slot(s) %s -- tile.raw bytes pointing there render "
                       "the error texture" % missing)
        if self.ignored_blocks:
            out.append("block(s) never loaded (duplicate index or past "
                       "TextureCount): %s" % ", ".join(self.ignored_blocks))
        if len(self) > MAX_USABLE_TEXTURES:
            out.append("%d textures exceeds the %d usable slots"
                       % (len(self), MAX_USABLE_TEXTURES))
        for i, t in enumerate(self.slots):
            if t is not None and t.extra_tokens:
                out.append("Texture%03d has %d junk token(s) after the 8 fields "
                           "(%r) -- shifts nothing but proves the file is dirty"
                           % (i, len(t.extra_tokens), t.extra_tokens[0]))
        return out

    # -- write -------------------------------------------------------------
    def render(self) -> str:
        if self.doc is not None and not self.dirty:
            return self.doc.render()
        return self.render_canonical()

    def to_bytes(self) -> bytes:
        return encode(self.render())

    def render_canonical(self, blank_after_count: bool = True) -> str:
        """The ``CTextureSet::Save`` layout (TextureSet.cpp:244-276).

        ``Save`` emits a blank line after ``TextureCount`` (TextureSet.cpp:250),
        and 47 of the 171 shipped sets match that byte for byte.  An older
        writer generation omitted it (another 10 match exactly that way, plus
        49 more that differ only in trailing blank-line padding left by
        truncating in-place rewrites); pass ``blank_after_count=False`` for
        that dialect.  Empty slots are skipped, exactly as ``Save`` would after
        a ``RemoveTexture``.

        The remaining shipped files cannot be reproduced by any single writer:
        some pad ``TextureCount`` to two digits (``TextureCount 08``), and
        ``metin2_guild_pve.txt`` is missing its final CRLF.
        """
        parts = ["TextureSet" + CRLF, CRLF,
                 "TextureCount %d%s" % (len(self), CRLF)]
        if blank_after_count:
            parts.append(CRLF)
        for i in range(1, len(self.slots)):
            entry = self.slots[i]
            if entry is not None:
                parts.append(entry.render(i))
        return "".join(parts)

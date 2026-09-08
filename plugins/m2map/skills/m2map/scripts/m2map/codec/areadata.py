"""``areadata.txt`` and ``areaambiencedata.txt`` codecs.

Both are ``Start Object%03d ... End`` scripts read through
``LoadMultipleTextData``, so **fields are addressed by INDEX** into one
flattened token vector -- the line breaks the writer emits are cosmetic.

Readers: ``CArea::__Load_LoadObject``   (GameLib/Area.cpp:795-890)
         ``CArea::__Load_LoadAmbience`` (GameLib/Area.cpp:892-965)
Writers: ``CAreaAccessor::__SaveObjects``   (WorldEditor/DataCtrl/MapAccessorArea.cpp:1043-1109)
         ``CAreaAccessor::__SaveAmbiences`` (MapAccessorArea.cpp:1111-1160)

Traps reproduced here, all verified against the source and the 142-map corpus:

* **Y is stored negated** -- ``stored_y == -terrain_y``; plot top-down at
  ``(x, -y)``.  Every one of the 48 858 records in <CORPUS> has negative Y.
* **Rotation is written ``%f#%f#%f`` but read with ``atoi``**, so it truncates
  to whole degrees.  Worse, yaw is read as ``substr(0, s-1)``
  (Area.cpp:850) -- the character immediately before the first ``#`` is
  dropped.  Harmless for ``120.000000`` (``120.00000``), fatal for a bare
  ``90#0#0`` (yaw becomes 9).  :attr:`ObjectRecord.engine_rotation` reproduces
  the defect; :attr:`rotation` gives the honest value.
* **Records may legally have 4, 5, 6 or more tokens.**  4 = position+CRC,
  5 adds rotation, 6 adds height bias, 6+ are portal IDs.  This is the
  format's only versioning.
* **``ObjectCount`` is required** and drives the read loop; blocks past it are
  never looked up.  Missing ``AreaDataFile``/``ObjectCount`` = file rejected.
* Duplicate keys resolve **first-wins** (``std::map::insert``, Util.cpp:100).
  ``metin2_map_t1`` ships areadata files with two ``ObjectCount`` lines whose
  first value is 0 -- the client therefore loads zero objects from them.
* ``areaambiencedata.txt`` index 4 is *range*, not rotation.  Mixing the two
  schemas corrupts records silently.

Undocumented extension found in the corpus: ``metin2_map_treasure_hunt``
writes index 3 as ``<crc>#<sx>#<sy>#<sz>`` -- a per-object scale triplet
appended to the CRC token (all 9 of its sectors, e.g.
``3579485406#0.350000#0.350000#0.350000``).  Vanilla degrades gracefully
because ``atoi`` stops at the ``#``, so the object just renders unscaled.
:attr:`ObjectRecord.scale` exposes it and :attr:`crc_token` preserves it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from .textfile import (BlockItem, FlatDoc, KeyItem, atof, atoi, encode, fmt_f,
                       parse_flat)

__all__ = ["ObjectRecord", "AmbienceRecord", "AreaData", "AreaAmbienceData",
           "PORTAL_ID_MAX_NUM"]

CRLF = "\r\n"

#: ``TObjectData::abyPortalID`` capacity (GameLib/AreaTypes.h).
PORTAL_ID_MAX_NUM = 8


def _split_rotation(tok: str) -> Tuple[float, float, float]:
    """Honest read of ``yaw#pitch#roll``; a bare value is roll only."""
    if "#" in tok:
        parts = tok.split("#")
        while len(parts) < 3:
            parts.append("0")
        return atof(parts[0]), atof(parts[1]), atof(parts[2])
    return 0.0, 0.0, atof(tok)


def _engine_rotation(tok: str) -> Tuple[int, int, int]:
    """Bit-for-bit reproduction of Area.cpp:846-861, ``atoi`` truncation and
    the ``substr(0, s-1)`` yaw defect included."""
    s = tok.find("#")
    if s < 0:
        return 0, 0, atoi(tok)
    yaw = atoi(tok[:max(s - 1, 0)])
    p = s + 1
    s2 = tok.find("#", p)
    if s2 < 0:                       # std::string::npos -> substr(p, npos-p)
        pitch = atoi(tok[p:])
        roll = atoi(tok[len(tok):])
    else:
        pitch = atoi(tok[p:s2])
        roll = atoi(tok[s2 + 1:])
    return yaw, pitch, roll


@dataclass
class ObjectRecord:
    """One ``areadata.txt`` record.  Coordinates are map-local centimetres."""

    x: float = 0.0
    y: float = 0.0                   # stored NEGATED: terrain_y == -y
    z: float = 0.0
    crc: int = 0                     # unsigned 32-bit property CRC
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    height_bias: float = 0.0         # cm, added to z
    portals: List[int] = field(default_factory=list)
    #: Per-object scale, from the undocumented ``crc#sx#sy#sz`` form.
    scale: Optional[Tuple[float, float, float]] = None
    #: How many tokens the source record carried (4/5/6/6+).
    token_count: int = 6
    #: The rotation token exactly as written, kept so the engine-side defect
    #: can be replayed and so a round trip is faithful.
    rotation_token: Optional[str] = None
    #: The CRC token exactly as written (may carry the ``#scale`` suffix).
    crc_token: Optional[str] = None

    # -- convenience -------------------------------------------------------
    @property
    def terrain_y(self) -> float:
        """De-negated Y -- the value ``GetTerrainHeight(x, -y)`` wants."""
        return -self.y

    @property
    def rotation(self) -> Tuple[float, float, float]:
        return (self.yaw, self.pitch, self.roll)

    @property
    def engine_rotation(self) -> Tuple[int, int, int]:
        """What the client actually applies, defect and all.

        Uses the source token only while it still matches ``rotation`` -- after
        an edit it would report the OLD heading, which is worse than useless for
        an audit check asking "what will the player see".
        """
        tok = (self.rotation_token if self._rotation_token_is_current()
               else "%f#%f#%f" % self.rotation)
        return _engine_rotation(tok)

    @property
    def final_z(self) -> float:
        return self.z + self.height_bias

    def sector(self, sector_size: int = 25600) -> Tuple[int, int]:
        """Sectree cell this record falls in (Y de-negated first)."""
        return (int(self.x // sector_size), int(self.terrain_y // sector_size))

    # -- codec -------------------------------------------------------------
    @classmethod
    def from_tokens(cls, t: Sequence[str]) -> "ObjectRecord":
        r = cls(token_count=len(t))
        if len(t) < 4:
            raise ValueError("areadata record needs >= 4 tokens, got %d" % len(t))
        r.x, r.y, r.z = atof(t[0]), atof(t[1]), atof(t[2])
        r.crc_token = t[3]
        r.crc = atoi(t[3]) & 0xFFFFFFFF          # atoi stops at the '#'
        if "#" in t[3]:
            parts = t[3].split("#")[1:]
            while len(parts) < 3:
                parts.append("1")
            r.scale = (atof(parts[0]), atof(parts[1]), atof(parts[2]))
        if len(t) > 4:
            r.rotation_token = t[4]
            r.yaw, r.pitch, r.roll = _split_rotation(t[4])
        if len(t) > 5:
            r.height_bias = atof(t[5])
        if len(t) > 6:
            r.portals = [atoi(x) for x in t[6:]]
        return r

    # -- token freshness ---------------------------------------------------
    #
    # The source tokens are kept so an untouched record round-trips byte-for-byte
    # (they preserve the original float formatting, and the rotation token also
    # carries the engine's substr defect). But a token that no longer agrees with
    # its semantic field is STALE, and emitting it silently discards the edit --
    # which is what `improve`, `reskin` and any CRC remap do. So each token is
    # used only while it still decodes to the current value.

    def _crc_token_is_current(self) -> bool:
        tok = self.crc_token
        if tok is None:
            return False
        if (atoi(tok) & 0xFFFFFFFF) != (self.crc & 0xFFFFFFFF):
            return False
        if "#" in tok:
            parts = tok.split("#")[1:]
            while len(parts) < 3:
                parts.append("1")
            return self.scale == (atof(parts[0]), atof(parts[1]), atof(parts[2]))
        return self.scale is None

    def _rotation_token_is_current(self) -> bool:
        tok = self.rotation_token
        return tok is not None and _split_rotation(tok) == self.rotation

    def render(self, index: int) -> str:
        """``__SaveObjects`` block layout (MapAccessorArea.cpp:1075-1099)."""
        if self._rotation_token_is_current():
            rot = self.rotation_token
        else:
            rot = "%s#%s#%s" % (fmt_f(self.yaw), fmt_f(self.pitch), fmt_f(self.roll))
        if self._crc_token_is_current():
            crc = self.crc_token
        else:
            crc = "%u" % (self.crc & 0xFFFFFFFF)
            if self.scale is not None:
                crc += "#%s#%s#%s" % tuple(fmt_f(s) for s in self.scale)
        out = ["Start Object%03d" % index,
               "    %s %s %s" % (fmt_f(self.x), fmt_f(self.y), fmt_f(self.z)),
               "    " + crc,
               "    " + rot,
               "    " + fmt_f(self.height_bias)]
        if self.portals and self.portals[0] != 0:
            # writer emits "   " then " %d" per id, deduplicated, stopping at 0
            seen, ids = set(), []
            for pid in self.portals[:PORTAL_ID_MAX_NUM]:
                if pid == 0:
                    break
                if pid in seen:
                    continue
                seen.add(pid)
                ids.append(pid)
            out.append("   " + "".join(" %d" % p for p in ids))
        out.append("End Object")
        return "".join(l + CRLF for l in out)


@dataclass
class AmbienceRecord:
    """One ``areaambiencedata.txt`` record.  Index 4 is *range*, not rotation."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    crc: int = 0
    range: int = 0                    # audible radius in cm; 0 disables
    max_volume_area_pct: float = 0.0  # 0..1 inner full-volume fraction
    token_count: int = 6

    @property
    def terrain_y(self) -> float:
        return -self.y

    @classmethod
    def from_tokens(cls, t: Sequence[str]) -> "AmbienceRecord":
        if len(t) < 5:
            raise ValueError("ambience record needs >= 5 tokens, got %d" % len(t))
        r = cls(token_count=len(t))
        r.x, r.y, r.z = atof(t[0]), atof(t[1]), atof(t[2])
        r.crc = atoi(t[3]) & 0xFFFFFFFF
        r.range = atoi(t[4])
        if len(t) >= 6:
            r.max_volume_area_pct = atof(t[5])
        return r

    def render(self, index: int) -> str:
        """``__SaveAmbiences`` block layout (MapAccessorArea.cpp:1143-1150)."""
        out = ["Start Object%03d" % index,
               "    %s %s %s" % (fmt_f(self.x), fmt_f(self.y), fmt_f(self.z)),
               "    %u" % (self.crc & 0xFFFFFFFF),
               "    %u" % self.range,
               "    " + fmt_f(self.max_volume_area_pct),
               "End Object"]
        return "".join(l + CRLF for l in out)


class _AreaFileBase:
    """Shared container logic for the two Start/End object files."""

    HEADER = ""
    RECORD = ObjectRecord

    def __init__(self, records=None, doc: Optional[FlatDoc] = None,
                 header: Optional[str] = None,
                 declared_count: Optional[int] = None):
        self.records = list(records or [])
        self.doc = doc
        self.header = header if header is not None else self.HEADER
        #: The ``ObjectCount`` the file declares (first-wins), which is what
        #: the engine loops to -- may disagree with ``len(self.records)``.
        self.declared_count = (len(self.records) if declared_count is None
                               else declared_count)
        self.has_header_key = True
        self.has_object_count = True
        #: Blocks present in the file but beyond ``ObjectCount`` (never loaded).
        self.orphan_blocks: List[str] = []

    # -- read --------------------------------------------------------------
    @classmethod
    def parse(cls, data, strict: bool = False):
        doc = parse_flat(data)
        obj = cls(doc=doc)
        obj.has_header_key = doc.has(cls.HEADER.lower())
        count_tokens = doc.get("objectcount")
        obj.has_object_count = count_tokens is not None
        if strict and not (obj.has_header_key and obj.has_object_count):
            raise ValueError("missing %s or ObjectCount" % cls.HEADER)
        obj.declared_count = atoi(count_tokens[0]) if count_tokens else 0
        by_key = {}
        for blk in doc.blocks:
            by_key.setdefault(blk.key, blk)          # first wins
        used = set()
        for i in range(obj.declared_count):
            key = "object%03d" % i
            blk = by_key.get(key)
            if blk is None:
                continue                              # engine: `continue`
            used.add(key)
            obj.records.append(cls.RECORD.from_tokens(blk.values))
        obj.orphan_blocks = [b.name for b in doc.blocks if b.key not in used]
        obj._snapshot()
        return obj

    @classmethod
    def load(cls, path, strict: bool = False):
        with open(path, "rb") as fh:
            return cls.parse(fh.read(), strict=strict)

    # -- write -------------------------------------------------------------
    #
    # Replaying the parsed document preserves the source byte-for-byte, which is
    # what the round-trip guarantee rests on. But it also means an edit to a
    # record never reaches the output: the caller changes `rec.x`, the document
    # is re-emitted unchanged, and the mutation is silently lost. Every mode this
    # skill offers is a mutation, so the container tracks whether the semantic
    # model still matches what was parsed, and re-renders from the records once
    # it does not.

    @staticmethod
    def _fingerprint(rec) -> str:
        """Value identity of a record, ignoring the source-formatting tokens."""
        state = {k: v for k, v in vars(rec).items()
                 if k not in ("rotation_token", "crc_token", "token_count")}
        return repr(sorted(state.items(), key=lambda kv: kv[0]))

    def _snapshot(self) -> None:
        self._src_state = (
            [self._fingerprint(r) for r in self.records],
            self.declared_count,
            self.header,
        )

    @property
    def dirty(self) -> bool:
        """True once the records diverge from what was parsed."""
        if self.doc is None:
            return True
        src = getattr(self, "_src_state", None)
        if src is None:
            return True
        return src != ([self._fingerprint(r) for r in self.records],
                       self.declared_count, self.header)

    def render(self) -> str:
        if self.doc is not None and not self.dirty:
            return self.doc.render()
        return self.render_canonical()

    def to_bytes(self) -> bytes:
        return encode(self.render())

    def render_canonical(self) -> str:
        """Exactly what the WorldEditor writes.

        ``HEADER\\r\\n`` + blank + back-to-back blocks + blank +
        ``ObjectCount N\\r\\n``.  With zero records that collapses to the two
        consecutive blank lines seen in every empty file in the corpus.
        """
        parts = [self.header + CRLF, CRLF]
        for i, rec in enumerate(self.records):
            parts.append(rec.render(i))
        parts.append(CRLF)
        parts.append("ObjectCount %d%s" % (len(self.records), CRLF))
        return "".join(parts)

    # -- misc --------------------------------------------------------------
    def __len__(self) -> int:
        return len(self.records)

    def __iter__(self):
        return iter(self.records)

    def crcs(self) -> List[int]:
        return [r.crc for r in self.records]

    def problems(self) -> List[str]:
        out = []
        if not self.has_header_key:
            out.append("missing %s key -- client rejects the file" % self.HEADER)
        if not self.has_object_count:
            out.append("missing ObjectCount -- client rejects the file")
        if self.declared_count != len(self.records):
            out.append("ObjectCount %d but %d blocks resolved"
                       % (self.declared_count, len(self.records)))
        if self.orphan_blocks:
            out.append("%d block(s) past ObjectCount are never loaded: %s"
                       % (len(self.orphan_blocks), ", ".join(self.orphan_blocks[:5])))
        return out


class AreaData(_AreaFileBase):
    """``<map>/<XXXYYY>/areadata.txt`` -- placed buildings/trees/effects."""

    HEADER = "AreaDataFile"
    RECORD = ObjectRecord


class AreaAmbienceData(_AreaFileBase):
    """``<map>/<XXXYYY>/areaambiencedata.txt`` -- ambient sound emitters."""

    HEADER = "AreaAmbienceDataFile"
    RECORD = AmbienceRecord

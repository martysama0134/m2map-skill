"""``property/**/*.pr?`` codec -- the object database ``areadata.txt`` CRCs point at.

Container (GameLib/Property.cpp:105-215 write, :218-255 read):

===========  ==============================================================
offset 0     ``"YPRT"`` FourCC (``59 50 52 54``)
offset 4     ``\\r\\n`` -- mandatory, validated by ``ReadFromMemory``
offset 6     text body, ``\\r\\n``-terminated lines
===========  ==============================================================

Body:

* **Line 0 is the CRC** as decimal ASCII.  It is stored in ``m_stCRC`` as a
  *string* and written back verbatim (``file.Write(m_stCRC...)``,
  Property.cpp:191) -- it is generated once at first save and **never
  recomputed from the filename**.  Never regenerate it.
* Remaining lines are ``key\\t\\t"value"`` (``"%s\\t"`` for the key then
  ``"\\t\\"%s\\""`` per value, Property.cpp:200-206), so a multi-value key is
  ``key\\t\\t"v0"\\t"v1"``.  Keys are lowercased on write and on read.
* Order is ``std::map<std::string>`` iteration order = plain byte-wise
  ascending.  All 2113 shipped files are already sorted.
* Duplicate keys resolve first-wins (``PutVector`` uses ``insert``,
  Property.cpp:90).

Type schemas come from the ``propertytype`` **value**, not the extension.

Undocumented key found in the shipped pack: **``isattributedata``**, present in
152 of the 1734 ``.prb`` files (always ``"0"``, always on Buildings).  It is
not read by any code in the WorldEditorRemix tree -- it is dead metadata from
a newer content pipeline -- but it must be preserved on write or the file
stops being byte-identical.

``property/reserve`` is a plain list of retired CRCs, one per line.  The
shipped file terminates lines with ``\\r\\r\\n`` (text-mode append on a string
that already ended ``\\r``), which ``Bind`` splits into *two* breaks -- an
empty line between every CRC.  Harmless, because blank lines are skipped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .textfile import ENCODING, atoi, decode, encode, split_lines, tokenize, unquote

__all__ = ["PropertyFile", "PropertyReserve", "MAGIC", "PROPERTY_TYPES",
           "TYPE_EXTENSION", "REQUIRED_KEYS", "OPTIONAL_KEYS",
           "UNDOCUMENTED_KEYS"]

MAGIC = b"YPRT"
CRLF = "\r\n"

#: ``PropertyType`` value -> conventional extension (prt::GetPropertyType).
TYPE_EXTENSION = {
    "Tree": ".prt",
    "Building": ".prb",
    "Effect": ".pre",
    "Ambience": ".pra",
    "DungeonBlock": ".prd",
}
PROPERTY_TYPES = tuple(TYPE_EXTENSION)

#: Keys each type must carry (schemas in WorldEditor/MapType.cpp).
REQUIRED_KEYS = {
    "Tree": ("propertyname", "propertytype", "treefile", "treesize", "treevariance"),
    "Building": ("propertyname", "propertytype", "buildingfile"),
    "Effect": ("propertyname", "propertytype", "effectfile"),
    "Ambience": ("propertyname", "propertytype", "playtype", "playinterval",
                 "playintervalvariation", "ambiencesoundvector"),
    "DungeonBlock": ("propertyname", "propertytype", "dungeonblockfile"),
}
OPTIONAL_KEYS = {
    "Tree": (),
    "Building": ("shadowflag", "isattributedata"),
    "Effect": (),
    "Ambience": ("maxvolumeareapercentage",),
    "DungeonBlock": ("isattributedata",),
}
#: Keys present in shipped data but read by nothing in the engine source.
UNDOCUMENTED_KEYS = ("isattributedata",)

#: The model-path key per type; also what the CRC was originally seeded from.
MODEL_KEY = {
    "Tree": "treefile",
    "Building": "buildingfile",
    "Effect": "effectfile",
    "DungeonBlock": "dungeonblockfile",
    "Ambience": None,          # no model path -> timestamp+filename seed
}


@dataclass
class PropertyFile:
    """One ``.pr?`` file.

    :attr:`crc_text` is the line-0 string exactly as stored; :attr:`crc` is its
    integer value.  Writing re-emits ``crc_text``, never a recomputed CRC.
    """

    crc_text: str = "0"
    #: Ordered ``(lowercased key, [values])`` pairs, first-wins on duplicates.
    entries: List[Tuple[str, List[str]]] = field(default_factory=list)
    #: Lines of the body that did not parse as ``key<tab>"value"``.
    malformed: List[str] = field(default_factory=list)
    path: Optional[str] = None
    #: True when the body's last line ended with CRLF (all shipped files do).
    trailing_crlf: bool = True

    # -- read --------------------------------------------------------------
    @classmethod
    def parse(cls, data: bytes, path: Optional[str] = None) -> "PropertyFile":
        if data[:4] != MAGIC:
            raise ValueError("not a YPRT property file (magic %r)" % data[:4])
        if data[4:6] != b"\r\n":
            raise ValueError("missing mandatory CRLF at offset 4")
        body = decode(data[6:])
        p = cls(path=path)
        p.trailing_crlf = body.endswith(CRLF) or body.endswith("\n") or body.endswith("\r")
        lines = split_lines(body)
        if lines and lines[-1] == ("", ""):
            lines = lines[:-1]
        if not lines:
            raise ValueError("empty property body -- no CRC line")
        p.crc_text = lines[0][0]
        seen = set()
        for content, _ in lines[1:]:
            _, tokens, _, _ = tokenize(content)
            if not tokens:
                continue
            key = unquote(tokens[0]).lower()
            values = [unquote(t) for t in tokens[1:]]
            if not values or "\t" not in content:
                p.malformed.append(content)
                continue
            if key in seen:                     # PutVector uses insert()
                continue
            seen.add(key)
            p.entries.append((key, values))
        return p

    @classmethod
    def load(cls, path) -> "PropertyFile":
        with open(path, "rb") as fh:
            return cls.parse(fh.read(), path=str(path))

    # -- access ------------------------------------------------------------
    @property
    def crc(self) -> int:
        return atoi(self.crc_text) & 0xFFFFFFFF

    def get(self, key: str) -> Optional[List[str]]:
        key = key.lower()
        for k, v in self.entries:
            if k == key:
                return v
        return None

    def get_str(self, key: str, default: Optional[str] = None) -> Optional[str]:
        v = self.get(key)
        return v[0] if v else default

    def set(self, key: str, *values: str) -> None:
        key = key.lower()
        for i, (k, _) in enumerate(self.entries):
            if k == key:
                self.entries[i] = (key, list(values))
                return
        self.entries.append((key, list(values)))

    @property
    def keys(self) -> List[str]:
        return [k for k, _ in self.entries]

    @property
    def property_type(self) -> str:
        """Authoritative type -- trust this, never the file extension."""
        return self.get_str("propertytype", "") or ""

    @property
    def name(self) -> str:
        return self.get_str("propertyname", "") or ""

    @property
    def model_file(self) -> Optional[str]:
        key = MODEL_KEY.get(self.property_type)
        return self.get_str(key) if key else None

    @property
    def collision_file(self) -> Optional[str]:
        """Buildings and dungeon blocks derive ``.mdatr`` from the model path."""
        if self.property_type not in ("Building", "DungeonBlock"):
            return None
        model = self.model_file
        if not model:
            return None
        return model.rsplit(".", 1)[0] + ".mdatr"

    @property
    def sounds(self) -> List[str]:
        return list(self.get("ambiencesoundvector") or [])

    def problems(self) -> List[str]:
        out = []
        ptype = self.property_type
        if ptype not in TYPE_EXTENSION:
            out.append("unknown PropertyType %r" % ptype)
            return out
        for key in REQUIRED_KEYS[ptype]:
            if self.get(key) is None:
                out.append("missing required key %s for %s" % (key, ptype))
        allowed = set(REQUIRED_KEYS[ptype]) | set(OPTIONAL_KEYS[ptype])
        for k in self.keys:
            if k not in allowed:
                out.append("unexpected key %s for %s" % (k, ptype))
        if self.keys != sorted(self.keys):
            out.append("keys are not in std::map order -- a rewrite will reorder them")
        if self.path and ptype in TYPE_EXTENSION:
            want = TYPE_EXTENSION[ptype]
            if not str(self.path).lower().endswith(want):
                out.append("extension does not match PropertyType %s (expected %s)"
                           % (ptype, want))
        if self.malformed:
            out.append("%d malformed body line(s)" % len(self.malformed))
        return out

    # -- write -------------------------------------------------------------
    def render_body(self, sort: bool = True) -> str:
        entries = sorted(self.entries) if sort else list(self.entries)
        parts = [self.crc_text, CRLF]
        for key, values in entries:
            parts.append(key)
            parts.append("\t")
            for v in values:
                parts.append('\t"%s"' % v)
            parts.append(CRLF)
        return "".join(parts)

    def to_bytes(self, sort: bool = True) -> bytes:
        """Rebuild the whole file.

        Byte-identical to the source for every shipped file: the CRC line is
        re-emitted verbatim and keys are re-sorted into the same std::map order
        they were written in.
        """
        return MAGIC + b"\r\n" + encode(self.render_body(sort=sort))

    def save(self, path, sort: bool = True) -> None:
        with open(path, "wb") as fh:
            fh.write(self.to_bytes(sort=sort))


@dataclass
class PropertyReserve:
    """``property/reserve`` -- retired CRCs, never reissued."""

    crcs: List[int] = field(default_factory=list)
    #: Record terminator for a fresh write; shipped data uses ``\\r\\r\\n``.
    eol: str = "\r\r\n"
    source: Optional[str] = None

    @classmethod
    def parse(cls, data: bytes) -> "PropertyReserve":
        text = decode(data)
        lines = split_lines(text)
        eol = "\r\r\n" if "\r\r\n" in text else (
            next((e for _, e in lines if e), "\r\n"))
        crcs = [atoi(c) & 0xFFFFFFFF for c, _ in lines if c.strip()]
        return cls(crcs, eol, text)

    @classmethod
    def load(cls, path) -> "PropertyReserve":
        with open(path, "rb") as fh:
            return cls.parse(fh.read())

    def to_bytes(self) -> bytes:
        if self.source is not None:
            return encode(self.source)
        return encode(self.render_canonical())

    def render_canonical(self) -> str:
        return "".join("%u%s" % (c, self.eol) for c in self.crcs)

    def __contains__(self, crc: int) -> bool:
        return crc in self.crcs

    def __len__(self) -> int:
        return len(self.crcs)


def scan_property_dir(root) -> Dict[int, PropertyFile]:
    """Build the CRC -> property registry the way ``CPropertyManager`` does.

    Recursive scan; on a duplicate CRC the **last** file wins, matching
    ``CPropertyManager::Register`` (which logs and overwrites).
    """
    import pathlib

    registry: Dict[int, PropertyFile] = {}
    for p in sorted(pathlib.Path(root).rglob("*")):
        if not p.is_file() or not p.suffix.lower().startswith(".pr"):
            continue
        try:
            prop = PropertyFile.load(p)
        except ValueError:
            continue
        registry[prop.crc] = prop
    return registry

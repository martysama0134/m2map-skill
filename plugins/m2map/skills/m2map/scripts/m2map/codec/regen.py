"""Server spawn/registration text files.

``regen.txt`` / ``npc.txt`` / ``boss.txt`` / ``stone.txt`` all share one
grammar (``regen_load``/``read_line``, m2dev-server-src/src/game/regen.cpp:89-236,
:684-797) -- the split into four filenames is organisational only, the parser
is identical and all four are loaded per map.

**The server tokenizer is character-level, not line-level.**  ``get_word``
(regen.cpp:27-77) pulls whitespace-delimited words straight off the ``FILE*``,
so a record is simply the next 11 words (6 for an ``e`` row) wherever they
happen to fall -- newlines carry no meaning at all.  ``"quoted"`` words are
supported, and a word whose first two characters are ``//`` swallows the rest
of the physical line.  We reproduce that exactly, while still recording line
numbers so an editor can point at the source.

Column semantics (regen.cpp:105-236):

===  ==========  =========================================================
 0   type        only ``token[0]`` matters, plus ``a`` at ``token[1]`` for ``ga``
 1   cx          rect centre X in units of 100 (metres)
 2   cy          rect centre Y
 3   sx          **half-extent** in X, not a start coordinate
 4   sy          half-extent in Y
 5   z           Z-section byte; ``e`` rows END HERE
 6   dir         0 = random, 1..8 -> (dir-1)*45 degrees
 7   time        digits + ``s``/``m``/``h``, additive; bare digits are DISCARDED
 8   percent     parsed and thrown away (regen.cpp:222-224)
 9   count       max simultaneous spawns
10   vnum        mob vnum / group id / group-group id
===  ==========  =========================================================

World rect: ``sx_world = (cx - sx)*100 + baseX``, ``ex_world = (cx + sx)*100 + baseX``
(the parser does ``sx -= i; ex = sx + i*2; sx *= 100; ex *= 100`` then adds the
base).  Exception rows get the x100 but **not** the base offset.

Also here: ``index``, ``Town.txt`` and ``dungeon.txt`` (sectree_manager.cpp:322-448,
:733-814) and the WorldEditor's ``MonsterArrange.txt``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Tuple

from .textfile import ENCODING, decode, encode

__all__ = ["RegenRow", "RegenFile", "TownFile", "MapIndex", "DungeonFile",
           "MonsterArrange", "REGEN_TYPES", "parse_duration", "format_duration"]

CRLF = "\r\n"

#: ``token[0][0]`` -> regen type (regen.cpp:107-130).  Anything else is a
#: fatal error that exits the server process.
REGEN_TYPES = {
    "m": "MOB",             # mob_proto vnum
    "g": "GROUP",           # group.txt id ('ga' also sets is_aggressive)
    "r": "GROUP_GROUP",     # group_group.txt id
    "s": "ANYWHERE",        # mob vnum, random position on the whole map
    "e": "EXCEPTION",       # no-spawn rect; row ends after column 5
}


def parse_duration(tok: str) -> int:
    """``MODE_REGEN_TIME`` (regen.cpp:187-217): digits accumulate, a suffix
    flushes them, and **anything left unflushed is discarded**.

    So ``"1h30m"`` -> 5400, ``"60s"`` -> 60, but ``"60"`` -> **0**, which
    disables the line entirely (``time == 0`` skips even the initial spawn,
    regen.cpp:766).
    """
    total = 0
    acc = 0
    for ch in tok:
        if ch == "h":
            total += acc * 3600
            acc = 0
        elif ch == "m":
            total += acc * 60
            acc = 0
        elif ch == "s":
            total += acc
            acc = 0
        elif ch.isdigit():
            acc = acc * 10 + (ord(ch) - 48)
    return total


def format_duration(seconds: int) -> str:
    """Normalise to a suffixed form the parser will actually accept."""
    if seconds <= 0:
        return "0s"
    if seconds % 3600 == 0:
        return "%dh" % (seconds // 3600)
    if seconds % 60 == 0:
        return "%dm" % (seconds // 60)
    return "%ds" % seconds


def _str_to_number(tok: str) -> int:
    """``str_to_number`` is a strtol wrapper; junk yields 0."""
    tok = tok.strip()
    neg = tok[:1] == "-"
    if tok[:1] in "+-":
        tok = tok[1:]
    digits = ""
    for ch in tok:
        if not ch.isdigit():
            break
        digits += ch
    if not digits:
        return 0
    v = int(digits)
    return -v if neg else v


@dataclass
class _Word:
    text: str
    line: int
    is_comment: bool = False


def _get_words(text: str) -> Iterator[_Word]:
    """Reimplementation of ``get_word`` (regen.cpp:27-77).

    Whitespace (space/tab/CR/LF) separates words and is skipped between them.
    A leading ``"`` switches to quoted mode until the closing ``"``.  As soon
    as the first two characters of a word are ``//`` the word is emitted as a
    comment marker and the caller skips to the next ``\\n``.
    """
    i, n = 0, len(text)
    line = 1
    while i < n:
        # skip leading whitespace
        while i < n and text[i] in " \t\r\n":
            if text[i] == "\n":
                line += 1
            i += 1
        if i >= n:
            return
        start_line = line
        if text[i] == '"':
            i += 1
            buf = []
            while i < n and text[i] != '"':
                if text[i] == "\n":
                    line += 1
                buf.append(text[i])
                i += 1
            i += 1                       # consume closing quote (or hit EOF)
            yield _Word("".join(buf), start_line)
            continue
        buf = []
        while i < n and text[i] not in " \t\r\n":
            buf.append(text[i])
            i += 1
            if len(buf) == 2 and buf[0] == "/" and buf[1] == "/":
                # comment: emit marker, then skip to end of physical line
                while i < n and text[i] != "\n":
                    i += 1
                yield _Word("//", start_line, is_comment=True)
                buf = None
                break
        if buf is not None:
            yield _Word("".join(buf), start_line)


@dataclass
class RegenRow:
    """One spawn line.  ``sx``/``sy`` are half-extents around ``(cx, cy)``."""

    type: str = "m"          # the token as written, e.g. "m", "g", "ga", "m1"
    cx: int = 0
    cy: int = 0
    sx: int = 0              # half-extent
    sy: int = 0
    z: int = 0
    dir: int = 0
    time: str = "1m"         # as written
    percent: int = 100       # parsed and discarded by the server
    count: int = 1
    vnum: int = 0
    line: int = 0            # 1-based source line of the type token

    # -- semantics ---------------------------------------------------------
    @property
    def kind(self) -> str:
        return REGEN_TYPES.get(self.type[:1].lower(), "INVALID")

    @property
    def is_aggressive(self) -> bool:
        """Only ``ga`` sets it -- ``ma``/``ra`` silently degrade to ``m``/``r``."""
        return self.type[:1].lower() == "g" and self.type[1:2].lower() == "a"

    @property
    def is_exception(self) -> bool:
        return self.kind == "EXCEPTION"

    @property
    def time_seconds(self) -> int:
        return parse_duration(self.time)

    @property
    def is_point_spawn(self) -> bool:
        """``sx==ex && sy==ey`` takes the point path *before* the type switch
        (regen.cpp:417), so a group row with zero extents never spawns its
        group -- ``SpawnMob`` gets the group id as a mob vnum."""
        return self.sx == 0 and self.sy == 0

    def world_rect(self, base_x: int = 0, base_y: int = 0) -> Tuple[int, int, int, int]:
        """``(sx, sy, ex, ey)`` in world cm.  Exception rows ignore the base."""
        if self.is_exception:
            base_x = base_y = 0
        sx = (self.cx - self.sx) * 100 + base_x
        ex = (self.cx + self.sx) * 100 + base_x
        sy = (self.cy - self.sy) * 100 + base_y
        ey = (self.cy + self.sy) * 100 + base_y
        if sx > ex:
            sx, ex = ex, sx
        if sy > ey:
            sy, ey = ey, sy
        return sx, sy, ex, ey

    def problems(self) -> List[str]:
        out = []
        if self.kind == "INVALID":
            out.append("unknown regen type %r -- the server calls exit(1)" % self.type)
        if not self.is_exception:
            if self.time_seconds == 0:
                out.append("time %r parses to 0 -- the line never spawns at all"
                           % self.time)
            if self.kind in ("GROUP", "GROUP_GROUP") and self.is_point_spawn:
                out.append("%s row with 0/0 extents takes the point-spawn path; "
                           "the group id is used as a mob vnum and nothing spawns"
                           % self.kind)
            if not 0 <= self.dir <= 8:
                out.append("dir %d outside 0..8" % self.dir)
        return out

    # -- write -------------------------------------------------------------
    def render(self) -> str:
        if self.is_exception:
            cols = [self.type, self.cx, self.cy, self.sx, self.sy, self.z]
        else:
            cols = [self.type, self.cx, self.cy, self.sx, self.sy, self.z,
                    self.dir, self.time, self.percent, self.count, self.vnum]
        return "\t".join(str(c) for c in cols)


HEADER_COMMENT = "//type\tcx\tcy\tsx\tsy\tz\tdir\ttime\tpercent\tcount\tvnum"


@dataclass
class RegenFile:
    """``regen.txt`` / ``npc.txt`` / ``boss.txt`` / ``stone.txt``."""

    rows: List[RegenRow] = field(default_factory=list)
    #: Raw source, kept so :meth:`render` can re-emit the file byte for byte.
    source: Optional[str] = None
    #: A trailing partial record (fewer than 11 words) the server would drop.
    truncated: bool = False

    @classmethod
    def parse(cls, data) -> "RegenFile":
        text = decode(data) if isinstance(data, (bytes, bytearray)) else data
        f = cls(source=text)
        words = [w for w in _get_words(text) if not w.is_comment]
        i, n = 0, len(words)
        while i < n:
            row = RegenRow(line=words[i].line)
            row.type = words[i].text
            if row.kind == "INVALID":
                # the server exits here; we record and stop consuming
                f.rows.append(row)
                break
            need = 6 if row.kind == "EXCEPTION" else 11
            if i + need > n:
                f.truncated = True
                break
            vals = [w.text for w in words[i:i + need]]
            row.cx = _str_to_number(vals[1])
            row.cy = _str_to_number(vals[2])
            row.sx = _str_to_number(vals[3])
            row.sy = _str_to_number(vals[4])
            row.z = _str_to_number(vals[5])
            if need == 11:
                row.dir = _str_to_number(vals[6])
                row.time = vals[7]
                row.percent = _str_to_number(vals[8])
                row.count = _str_to_number(vals[9])
                row.vnum = _str_to_number(vals[10])
            f.rows.append(row)
            i += need
        return f

    @classmethod
    def load(cls, path) -> "RegenFile":
        with open(path, "rb") as fh:
            return cls.parse(fh.read())

    def __len__(self) -> int:
        return len(self.rows)

    def __iter__(self):
        return iter(self.rows)

    def vnums(self) -> List[int]:
        seen, out = set(), []
        for r in self.rows:
            if r.is_exception or r.vnum in seen:
                continue
            seen.add(r.vnum)
            out.append(r.vnum)
        return out

    def problems(self) -> List[str]:
        out = []
        for r in self.rows:
            out += ["line %d: %s" % (r.line, p) for p in r.problems()]
        if self.truncated:
            out.append("file ends mid-record; the trailing words are ignored")
        return out

    def render(self) -> str:
        return self.source if self.source is not None else self.render_canonical()

    def to_bytes(self) -> bytes:
        return encode(self.render())

    def render_canonical(self, header: bool = True) -> str:
        """Tab-separated rows with the conventional column header comment."""
        out = []
        if header:
            out.append(HEADER_COMMENT)
            out.append("//" + "-" * 83)
        out += [r.render() for r in self.rows]
        return "".join(l + CRLF for l in out)


@dataclass
class TownFile:
    """``Town.txt`` -- spawn points, map-local units of 100 (metres).

    ``LoadMapRegion`` (sectree_manager.cpp:373-448) uses ``fscanf``, so the
    file is just eight whitespace-separated integers; line structure is
    irrelevant.  The three empire pairs are used **only if all six are
    present**.  A missing or unreadable ``Town.txt`` aborts the entire
    map-loading pass, not just that map.
    """

    x: int = 0
    y: int = 0
    empire: Optional[List[Tuple[int, int]]] = None
    source: Optional[str] = None

    @classmethod
    def parse(cls, data) -> "TownFile":
        text = decode(data) if isinstance(data, (bytes, bytearray)) else data
        nums = [_str_to_number(w.text) for w in _get_words(text) if not w.is_comment]
        t = cls(source=text)
        if len(nums) >= 2:
            t.x, t.y = nums[0], nums[1]
        if len(nums) >= 8:
            t.empire = [(nums[2], nums[3]), (nums[4], nums[5]), (nums[6], nums[7])]
        return t

    @classmethod
    def load(cls, path) -> "TownFile":
        with open(path, "rb") as fh:
            return cls.parse(fh.read())

    def world_spawn(self, base_x: int, base_y: int) -> Tuple[int, int]:
        return base_x + self.x * 100, base_y + self.y * 100

    def render(self) -> str:
        return self.source if self.source is not None else self.render_canonical()

    def to_bytes(self) -> bytes:
        return encode(self.render())

    def render_canonical(self) -> str:
        out = ["%d\t%d" % (self.x, self.y)]
        if self.empire:
            out += ["%d\t%d" % pair for pair in self.empire]
        return "".join(l + CRLF for l in out)


@dataclass
class MapIndex:
    """``<MapPath>/index`` -- ``<mapIndex> <mapFolderName>`` per line."""

    entries: List[Tuple[int, str]] = field(default_factory=list)
    source: Optional[str] = None

    @classmethod
    def parse(cls, data) -> "MapIndex":
        text = decode(data) if isinstance(data, (bytes, bytearray)) else data
        idx = cls(source=text)
        for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            s = raw.strip()
            if not s or s.startswith("//") or s.startswith("#"):
                continue
            parts = s.split()
            if len(parts) < 2:
                continue
            idx.entries.append((_str_to_number(parts[0]), parts[1]))
        return idx

    @classmethod
    def load(cls, path) -> "MapIndex":
        with open(path, "rb") as fh:
            return cls.parse(fh.read())

    def problems(self) -> List[str]:
        out = []
        if self.source is not None and self.source and not self.source.endswith("\n"):
            out.append("last line has no newline -- Build() does "
                       "*strrchr(buf, '\\n') = 0 and dereferences NULL")
        seen = set()
        for i, name in self.entries:
            if i in seen:
                out.append("duplicate map index %d" % i)
            seen.add(i)
        return out

    def render(self) -> str:
        return self.source if self.source is not None else self.render_canonical()

    def to_bytes(self) -> bytes:
        return encode(self.render())

    def render_canonical(self) -> str:
        return "".join("%d\t%s%s" % (i, n, CRLF) for i, n in self.entries)


@dataclass
class DungeonArea:
    name: str
    x: int
    y: int
    sx: int          # half-extent as written
    sy: int
    dir: int

    def rect(self) -> Tuple[int, int, int, int]:
        """``LoadDungeon``'s conversion (sectree_manager.cpp:346-351).
        No x100 scaling here -- these are raw world units."""
        x = self.x - self.sx
        y = self.y - self.sy
        return x, y, self.sx * 2 + x, self.sy * 2 + y


@dataclass
class DungeonFile:
    """``dungeon.txt`` -- ``<name> <x> <y> <sx> <sy> <dir>`` named areas."""

    areas: List[DungeonArea] = field(default_factory=list)
    source: Optional[str] = None

    @classmethod
    def parse(cls, data) -> "DungeonFile":
        text = decode(data) if isinstance(data, (bytes, bytearray)) else data
        d = cls(source=text)
        for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            if not raw or raw[0] == "#" or raw[:2] == "//":
                continue
            parts = raw.split()
            if len(parts) < 6:
                continue                       # ins.fail() -> skipped
            d.areas.append(DungeonArea(parts[0], *[_str_to_number(p)
                                                   for p in parts[1:6]]))
        return d

    @classmethod
    def load(cls, path) -> "DungeonFile":
        with open(path, "rb") as fh:
            return cls.parse(fh.read())

    def render(self) -> str:
        return self.source if self.source is not None else self.render_canonical()

    def to_bytes(self) -> bytes:
        return encode(self.render())

    def render_canonical(self) -> str:
        return "".join("%s\t%d\t%d\t%d\t%d\t%d%s"
                       % (a.name, a.x, a.y, a.sx, a.sy, a.dir, CRLF)
                       for a in self.areas)


@dataclass
class MonsterArrange:
    """``MonsterArrange.txt`` -- deduplicated vnum list the WorldEditor emits
    alongside ``regen.txt`` (MapAccessorOutdoor.cpp:1620-1655).  Nothing in the
    engine or the server reads it; it is a content-pipeline aid."""

    vnums: List[int] = field(default_factory=list)
    source: Optional[str] = None

    @classmethod
    def parse(cls, data) -> "MonsterArrange":
        text = decode(data) if isinstance(data, (bytes, bytearray)) else data
        vnums = [_str_to_number(w.text) for w in _get_words(text)
                 if not w.is_comment and w.text.strip()]
        return cls(vnums, text)

    @classmethod
    def load(cls, path) -> "MonsterArrange":
        with open(path, "rb") as fh:
            return cls.parse(fh.read())

    @classmethod
    def from_regen(cls, *files: RegenFile) -> "MonsterArrange":
        seen, out = set(), []
        for f in files:
            for v in f.vnums():
                if v not in seen:
                    seen.add(v)
                    out.append(v)
        return cls(out)

    def render(self) -> str:
        return self.source if self.source is not None else self.render_canonical()

    def to_bytes(self) -> bytes:
        return encode(self.render())

    def render_canonical(self) -> str:
        return "".join("%d%s" % (v, CRLF) for v in self.vnums)

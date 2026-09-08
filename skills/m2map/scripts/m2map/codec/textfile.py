"""Ymir text-script tokenizer -- the shared front end for every text map format.

Two front ends live here, both taken from the real engine code (paths below are
relative to ``WorldEditorRemix/Srcs``):

(a) :func:`parse_flat` -- the ``Start <name> ... End`` form used by
    ``areadata.txt``, ``areaambiencedata.txt`` and ``textureset/*.txt``.
    Implemented from ``Client/EterLib/Util.cpp:51-110``
    (``LoadMultipleTextData``).  **Every token between ``Start X`` and ``End``
    is flattened into one positional vector** -- line breaks inside a block are
    purely cosmetic and fields are addressed by INDEX, never by name.

(b) :func:`parse_groups` -- the ``Group <name> { ... }`` / ``List <name> { ... }``
    nesting form used by ``.msenv``, ``group.txt`` and the pack-build scripts.
    Implemented from ``Client/EterLib/TextFileLoader.cpp:203-305``
    (``CTextFileLoader::LoadGroup``).

Both sit on the same primitives:

* :func:`split_lines` -- byte-exact reimplementation of
  ``CMemoryTextFileLoader::Bind`` (``Client/EterBase/FileLoader.cpp:144-178``).
* :func:`tokenize`   -- byte-exact reimplementation of
  ``CMemoryTextFileLoader::SplitLine`` (``FileLoader.cpp:82-123``),
  delimiter set ``" \\t"``, quoted tokens keep their inner spaces.

Everything is layout preserving: a parsed document re-renders to the exact
input bytes, so round-tripping a real file never perturbs it.

Text is handled as ``latin-1``-decoded ``str`` throughout, which maps bytes
1:1 and re-encodes losslessly -- the files contain CP949 Korean in places and
must not be transcoded.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields as dc_fields, is_dataclass
from typing import Iterable, Iterator, List, Optional, Sequence, Tuple

__all__ = [
    "ENCODING",
    "DELIMITERS",
    "Line",
    "TextDocument",
    "KeyItem",
    "BlockItem",
    "FlatDoc",
    "GroupNode",
    "GroupDoc",
    "decode",
    "encode",
    "split_lines",
    "tokenize",
    "parse_lines",
    "parse_flat",
    "parse_groups",
    "quote",
    "unquote",
    "fmt_f",
    "atoi",
    "atof",
]

#: The engine never transcodes; bytes are handled 1:1 as latin-1 code points.
ENCODING = "latin-1"

#: Default delimiter set of ``CMemoryTextFileLoader::SplitLine``
#: (``FileLoader.h:20``: ``const char * c_szDelimeter = " \t"``).
DELIMITERS = " \t"

_BREAK = "\r\n"


def decode(data: bytes) -> str:
    return data.decode(ENCODING)


def encode(text: str) -> bytes:
    return text.encode(ENCODING)


# --------------------------------------------------------------------------
# line splitting -- CMemoryTextFileLoader::Bind
# --------------------------------------------------------------------------

def split_lines(text: str, dbcs: bool = True) -> List[Tuple[str, str]]:
    """Split ``text`` into ``(content, eol)`` pairs exactly like ``Bind``.

    ``Bind`` (``FileLoader.cpp:153-177``) treats **either** ``\\r`` **or**
    ``\\n`` as a line break and, if the very next byte is also ``\\r`` or
    ``\\n``, swallows that one into the same break.  Consequences, all of
    which show up in the corpus:

    * ``\\r\\n`` is one break (normal case).
    * ``\\n\\n`` in an LF-only file is *one* break, so a blank line written
      with bare LFs is silently swallowed by the engine.
    * ``\\r\\n\\r\\n`` is two breaks, so a CRLF blank line survives.
    * ``\\r\\r\\n`` -- the terminator ``property/reserve`` actually uses -- is
      **two** breaks (``\\r\\r`` then ``\\n``), i.e. it yields an extra blank
      line, not one fused break.  (mapformat/client-global-refs.md claims the
      opposite; the source disagrees and the source wins.)  Harmless there
      because blank lines are skipped anyway.

    When ``dbcs`` is true (the engine default) a byte >= 0x80 consumes the
    following byte unconditionally (``FileLoader.cpp:166-170``), so a trailing
    lead byte can eat a newline.  That is a real corruption vector for CP949
    text and is reproduced here.

    ``"".join(c + e for c, e in split_lines(t)) == t`` always holds.
    """
    out: List[Tuple[str, str]] = []
    buf: List[str] = []
    pos = 0
    n = len(text)
    while pos < n:
        c = text[pos]
        pos += 1
        if c in _BREAK:
            eol = c
            if pos < n and text[pos] in _BREAK:
                eol += text[pos]
                pos += 1
            out.append(("".join(buf), eol))
            buf = []
        elif dbcs and ord(c) >= 0x80:
            buf.append(c)
            if pos < n:
                buf.append(text[pos])
                pos += 1
        else:
            buf.append(c)
    out.append(("".join(buf), ""))
    return out


# --------------------------------------------------------------------------
# tokenizing -- CMemoryTextFileLoader::SplitLine
# --------------------------------------------------------------------------

def tokenize(content: str) -> Tuple[str, List[str], List[str], bool]:
    """Split one line into ``(indent, raw_tokens, gaps, unterminated_quote)``.

    ``raw_tokens[i]`` is the token *as written* (a quoted token keeps its
    surrounding quotes so the line can be re-rendered byte-exactly); use
    :func:`unquote` for the value.  ``gaps[i]`` is the whitespace that follows
    token *i*, so::

        indent + "".join(t + g for t, g in zip(raw_tokens, gaps)) == content

    Quoting follows the engine: a ``"`` is only special when it is the *first*
    character of a token; the token then runs to the next ``"``.  An
    unterminated quote makes ``SplitLine`` reject the whole line
    (``FileLoader.cpp:105-107``); we flag it instead of throwing so callers can
    decide.
    """
    n = len(content)
    i = 0
    while i < n and content[i] in DELIMITERS:
        i += 1
    indent = content[:i]
    tokens: List[str] = []
    gaps: List[str] = []
    unterminated = False
    while i < n:
        if content[i] == '"':
            close = content.find('"', i + 1)
            if close < 0:
                unterminated = True
                tokens.append(content[i:])
                gaps.append("")
                i = n
                break
            tokens.append(content[i:close + 1])
            i = close + 1
        else:
            j = i
            while j < n and content[j] not in DELIMITERS:
                j += 1
            tokens.append(content[i:j])
            i = j
        j = i
        while j < n and content[j] in DELIMITERS:
            j += 1
        gaps.append(content[i:j])
        i = j
    return indent, tokens, gaps, unterminated


def unquote(raw: str) -> str:
    """Strip the engine's quoting from a raw token."""
    if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
        return raw[1:-1]
    if raw[:1] == '"':          # unterminated -- engine would reject the line
        return raw[1:]
    return raw


def quote(value: str) -> str:
    return '"%s"' % value


# --------------------------------------------------------------------------
# Line / TextDocument
# --------------------------------------------------------------------------

@dataclass
class Line:
    """One physical line, preserving indent, inter-token gaps and EOL."""

    indent: str = ""
    tokens: List[str] = field(default_factory=list)   # raw, quotes included
    gaps: List[str] = field(default_factory=list)
    eol: str = _BREAK
    unterminated_quote: bool = False

    # -- construction ------------------------------------------------------
    @classmethod
    def parse(cls, content: str, eol: str) -> "Line":
        indent, tokens, gaps, bad = tokenize(content)
        return cls(indent, tokens, gaps, eol, bad)

    @classmethod
    def make(cls, *values: str, indent: str = "", sep: str = " ",
             eol: str = _BREAK) -> "Line":
        vals = list(values)
        gaps = [sep] * (len(vals) - 1) + ([""] if vals else [])
        return cls(indent, vals, gaps, eol)

    @classmethod
    def blank(cls, eol: str = _BREAK) -> "Line":
        return cls("", [], [], eol)

    # -- access ------------------------------------------------------------
    @property
    def is_blank(self) -> bool:
        """True when ``SplitLine`` would reject the line (engine skips it)."""
        return not self.tokens

    def values(self) -> List[str]:
        return [unquote(t) for t in self.tokens]

    @property
    def key(self) -> Optional[str]:
        """Lowercased first token -- the engine lowercases keys, not values."""
        if not self.tokens:
            return None
        return unquote(self.tokens[0]).lower()

    def content(self) -> str:
        return self.indent + "".join(t + g for t, g in zip(self.tokens, self.gaps))

    def render(self) -> str:
        return self.content() + self.eol

    def __str__(self) -> str:  # pragma: no cover - debugging aid
        return self.render()


@dataclass
class TextDocument:
    """An ordered list of :class:`Line`; renders back to the source bytes."""

    lines: List[Line] = field(default_factory=list)

    def render(self) -> str:
        return "".join(l.render() for l in self.lines)

    def to_bytes(self) -> bytes:
        return encode(self.render())

    def __iter__(self) -> Iterator[Line]:
        return iter(self.lines)

    def __len__(self) -> int:
        return len(self.lines)


def parse_lines(data, dbcs: bool = True) -> TextDocument:
    """Parse bytes/str into a layout-preserving :class:`TextDocument`."""
    text = decode(data) if isinstance(data, (bytes, bytearray)) else data
    return TextDocument([Line.parse(c, e) for c, e in split_lines(text, dbcs)])


# --------------------------------------------------------------------------
# front end (a): Start/End flattened blocks -- LoadMultipleTextData
# --------------------------------------------------------------------------

@dataclass
class KeyItem:
    """A top-level ``key v0 v1 ...`` line outside any block."""

    key: str                       # lowercased
    values: List[str]              # tokens AFTER the key, unquoted
    line: int                      # index into FlatDoc.lines


@dataclass
class BlockItem:
    """A ``Start <name> ... End`` block, tokens flattened positionally."""

    key: str                       # lowercased block name, e.g. "object000"
    name: str                      # as written, e.g. "Object000"
    values: List[str]              # every token between Start and End
    start_line: int
    end_line: int                  # index of the ``End`` line, -1 if EOF-ended


@dataclass
class FlatDoc(TextDocument):
    """Result of :func:`parse_flat`."""

    items: List[object] = field(default_factory=list)   # KeyItem | BlockItem

    # ``LoadMultipleTextData`` stores into a std::map via ``insert``, so on a
    # duplicate key the FIRST occurrence wins and later ones are dropped
    # (Util.cpp:100 / :105).  ``get`` reproduces that; ``get_all`` exposes the
    # rest.
    def get(self, key: str) -> Optional[List[str]]:
        key = key.lower()
        for it in self.items:
            if it.key == key:
                return it.values
        return None

    def get_all(self, key: str) -> List[List[str]]:
        key = key.lower()
        return [it.values for it in self.items if it.key == key]

    def has(self, key: str) -> bool:
        return self.get(key) is not None

    @property
    def blocks(self) -> List[BlockItem]:
        return [i for i in self.items if isinstance(i, BlockItem)]

    @property
    def duplicate_keys(self) -> List[str]:
        seen, dups = set(), []
        for it in self.items:
            if it.key in seen:
                dups.append(it.key)
            else:
                seen.add(it.key)
        return dups


def parse_flat(data, dbcs: bool = True) -> FlatDoc:
    """Parse the ``Start/End`` form (``LoadMultipleTextData``).

    Blank lines are skipped, ``Start``/``End`` are matched case-insensitively,
    the word after ``End`` is ignored, and all tokens inside a block are
    flattened into one positional list.
    """
    doc = parse_lines(data, dbcs)
    items: List[object] = []
    lines = doc.lines
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if line.is_blank:
            i += 1
            continue
        key = line.key
        if key == "start":
            vals = line.values()
            name = vals[1] if len(vals) > 1 else ""
            start = i
            toks: List[str] = []
            end = -1
            i += 1
            while i < n:
                inner = lines[i]
                if inner.is_blank:
                    i += 1
                    continue
                if inner.key == "end":
                    end = i
                    i += 1
                    break
                toks.extend(inner.values())
                i += 1
            items.append(BlockItem(name.lower(), name, toks, start, end))
        else:
            items.append(KeyItem(key, line.values()[1:], i))
            i += 1
    doc_flat = FlatDoc(lines, items)
    return doc_flat


# --------------------------------------------------------------------------
# front end (b): Group/List nesting -- CTextFileLoader::LoadGroup
# --------------------------------------------------------------------------

@dataclass
class GroupNode:
    """One ``Group`` scope (or the implicit ``global`` root)."""

    name: str = "global"                # as written
    key: str = "global"                 # lowercased
    entries: List[Tuple[str, List[str]]] = field(default_factory=list)
    lists: List[Tuple[str, List[str]]] = field(default_factory=list)
    children: List["GroupNode"] = field(default_factory=list)
    parent: Optional["GroupNode"] = None
    start_line: int = -1
    end_line: int = -1

    # std::map::insert semantics again (TextFileLoader.cpp:39) -> first wins.
    def get(self, key: str) -> Optional[List[str]]:
        key = key.lower()
        for k, v in self.entries:
            if k == key:
                return v
        return None

    def get_list(self, key: str) -> Optional[List[str]]:
        key = key.lower()
        for k, v in self.lists:
            if k == key:
                return v
        return None

    def child(self, key: str) -> Optional["GroupNode"]:
        key = key.lower()
        for c in self.children:
            if c.key == key:
                return c
        return None

    def get_str(self, key: str, default: Optional[str] = None) -> Optional[str]:
        v = self.get(key)
        return v[0] if v else default

    def get_float(self, key: str, default: float = 0.0) -> float:
        v = self.get(key)
        return atof(v[0]) if v else default

    def get_int(self, key: str, default: int = 0) -> int:
        v = self.get(key)
        return atoi(v[0]) if v else default

    def get_floats(self, key: str, count: int,
                   default: Optional[Sequence[float]] = None) -> Optional[List[float]]:
        v = self.get(key)
        if v is None or len(v) < count:
            return list(default) if default is not None else None
        return [atof(x) for x in v[:count]]


@dataclass
class GroupDoc(TextDocument):
    """Result of :func:`parse_groups`."""

    root: GroupNode = field(default_factory=GroupNode)
    balanced: bool = True

    def child(self, key: str) -> Optional[GroupNode]:
        return self.root.child(key)

    def get(self, key: str) -> Optional[List[str]]:
        return self.root.get(key)

    def get_str(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self.root.get_str(key, default)


def parse_groups(data, dbcs: bool = True) -> GroupDoc:
    """Parse the ``Group``/``List`` brace form (``CTextFileLoader::LoadGroup``).

    Follows the engine: blank lines skipped, keys lowercased, a bare ``{`` or
    ``}`` only changes depth, ``List`` bodies are flattened into one token
    vector exactly like block bodies, and duplicate keys keep the first value.
    """
    doc = parse_lines(data, dbcs)
    lines = doc.lines
    n = len(lines)
    root = GroupNode()
    node = root
    depth_ok = True
    i = 0
    while i < n:
        line = lines[i]
        if line.is_blank:
            i += 1
            continue
        key = line.key
        first = line.tokens[0]
        if first.startswith("{"):
            i += 1
            continue
        if first.startswith("}"):
            if node.parent is None:
                depth_ok = False
            else:
                node.end_line = i
                node = node.parent
            i += 1
            continue
        vals = line.values()
        if key == "group" and len(vals) == 2:
            child = GroupNode(name=vals[1], key=vals[1].lower(), parent=node,
                              start_line=i)
            node.children.append(child)
            node = child
            i += 1
            continue
        if key == "list" and len(vals) == 2:
            lkey = vals[1].lower()
            toks: List[str] = []
            i += 1
            while i < n:
                inner = lines[i]
                if inner.is_blank:
                    i += 1
                    continue
                t0 = inner.tokens[0]
                if t0.startswith("{"):
                    i += 1
                    continue
                if t0.startswith("}"):
                    i += 1
                    break
                toks.extend(inner.values())
                i += 1
            node.lists.append((lkey, toks))
            continue
        node.entries.append((key, vals[1:]))
        i += 1
    if node is not root:
        depth_ok = False
    return GroupDoc(lines, root, depth_ok)


# --------------------------------------------------------------------------
# C-runtime lookalikes -- the engine parses with atoi/atof, which never throw
# --------------------------------------------------------------------------

def atoi(s: str) -> int:
    """``atoi``: leading whitespace, optional sign, digits; junk -> 0."""
    i, n = 0, len(s)
    while i < n and s[i] in " \t\r\n\v\f":
        i += 1
    j = i
    if j < n and s[j] in "+-":
        j += 1
    k = j
    while k < n and s[k].isdigit():
        k += 1
    if k == j:
        return 0
    try:
        return int(s[i:k])
    except ValueError:                        # pragma: no cover
        return 0


def atof(s: str) -> float:
    """``atof``: parse the longest leading float; junk -> 0.0."""
    i, n = 0, len(s)
    while i < n and s[i] in " \t\r\n\v\f":
        i += 1
    j = i
    if j < n and s[j] in "+-":
        j += 1
    seen_digit = False
    while j < n and s[j].isdigit():
        j += 1
        seen_digit = True
    if j < n and s[j] == ".":
        j += 1
        while j < n and s[j].isdigit():
            j += 1
            seen_digit = True
    if not seen_digit:
        return 0.0
    if j < n and s[j] in "eE":
        k = j + 1
        if k < n and s[k] in "+-":
            k += 1
        if k < n and s[k].isdigit():
            while k < n and s[k].isdigit():
                k += 1
            j = k
    try:
        return float(s[i:j])
    except ValueError:                        # pragma: no cover
        return 0.0


def fmt_f(v: float) -> str:
    """C ``printf("%f")``: always six decimals, keeps the sign of -0.0."""
    return "%f" % v


# ---------------------------------------------------------------------------
# Source preservation vs. mutation
# ---------------------------------------------------------------------------
#
# Every text container here keeps the parsed document so an untouched file
# round-trips byte-for-byte -- original float formatting, key order, whitespace
# and all. Replaying it unconditionally, however, means an edit to the semantic
# model never reaches the output: the caller sets `setting.map_size`, the stored
# document is re-emitted verbatim, and the change is silently dropped.
#
# That matters because every mode this skill offers is a mutation. The mixin
# below keeps both properties: replay the source while the model still matches
# what was parsed, re-render from the model once it does not.

#: Attribute names that carry source formatting rather than meaning, at any
#: nesting depth. Excluded from the comparison so that re-rendering a value
#: (which legitimately drops its captured token) does not read as a change.
FORMATTING_ATTRS = frozenset({
    "doc", "source", "raw", "_raw", "_src_state",
    "rotation_token", "crc_token", "token_count",
    "layout", "block_layout", "trailing",
})


def _value_state(v):
    """Value identity, recursing into dataclasses and sequences."""
    if is_dataclass(v) and not isinstance(v, type):
        return "{" + ",".join(
            "%s=%s" % (f.name, _value_state(getattr(v, f.name, None)))
            for f in dc_fields(v) if f.name not in FORMATTING_ATTRS
        ) + "}"
    if isinstance(v, (list, tuple)):
        return "[" + ",".join(_value_state(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ",".join("%r:%s" % (k, _value_state(v[k]))
                              for k in sorted(v, key=repr)) + "}"
    return repr(v)


def semantic_state(obj, exclude=()) -> str:
    """Comparable value identity of a container, ignoring formatting."""
    skip = FORMATTING_ATTRS | frozenset(exclude)
    return "|".join("%s=%s" % (k, _value_state(v))
                    for k, v in sorted(vars(obj).items()) if k not in skip)


class SourcePreserving:
    """Replay the parsed source byte-for-byte until the model diverges.

    Containers call :meth:`_snapshot` at the end of ``parse`` and gate their
    ``render`` on :attr:`dirty`::

        def render(self):
            if self.doc is not None and not self.dirty:
                return self.doc.render()
            return self.render_canonical()
    """

    #: Extra attribute names this class treats as formatting-only.
    _SNAPSHOT_EXCLUDE: tuple = ()

    def _snapshot(self) -> None:
        self._src_state = semantic_state(self, self._SNAPSHOT_EXCLUDE)

    @property
    def dirty(self) -> bool:
        """True once the semantic model differs from what was parsed."""
        src = getattr(self, "_src_state", None)
        if src is None:
            return True
        return src != semantic_state(self, self._SNAPSHOT_EXCLUDE)

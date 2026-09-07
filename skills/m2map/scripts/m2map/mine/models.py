"""Model miner -- turns a property-catalog entry into a *physical* description.

The property database (``codec/property.py``) gives a prop's CRC, name and the
path of its art asset.  It says nothing about how big that asset is, so every
placement decision downstream -- spacing, clearance, collision, "does this fit
in the courtyard" -- is unanswerable from the catalog alone.  This module fills
that gap by reading the art files themselves.

Three sources, in descending order of usefulness
------------------------------------------------

``.gr2`` (Granny2 mesh, 2123 files under ``ymir work/zone``)
    The authoritative render geometry.  Yields the vertex-extent bounding box,
    mesh/vertex/triangle counts and the referenced ``.dds`` texture names.
    **Every shipped section is Oodle1-compressed** (measured: 14865 sections
    format 2, 2119 format 0 -- the format-0 ones are the empty sections), so
    the file must be decompressed before the object graph can be walked.
    Decompression is delegated to OpenGranny's ``grn-preprocessor.exe``
    (pure Rust, MIT, *no* ``granny2.dll``); everything after that is pure
    Python here.  See ``reference/models.md`` for why there is no pure-Python
    Oodle1 path.

``.mdatr`` (AttributeData collision proxy, 1579 files)
    Parsed natively here -- no external tool.  This is the *collision* volume
    the player actually bumps into, which for placement is often a better
    footprint than the render bbox (a tree's canopy is not solid; a house's
    eaves are not either).  Format from
    ``WorldEditorRemix/Srcs/Client/EterLib/AttributeData.cpp:44-130``.

``.spt`` (SpeedTree, 87 files under ``ymir work/tree`` + 31 under ``zone``)
    A *procedural description*, not a mesh.  The real bounding box only exists
    after ``CSpeedTreeRT::Compute()`` (proprietary static lib, no DLL), so it
    cannot be extracted here.  What *can* be read is the authored tree size
    token, and that is what the engine actually uses -- see below.

The tree size trap
------------------

``.prt`` files carry ``treesize`` / ``treevariance``, and it is tempting to use
them for spacing.  Do not:

* All 85 shipped ``Tree`` properties have ``treesize == "1000.000000"`` and
  ``treevariance == "0.000000"``.  The key has zero discriminating power.
* Worse, it is never applied.  ``CSpeedTreeForest::GetMainTree`` calls
  ``pTree->LoadTree(name, data, size)``
  (``SpeedTreeLib/SpeedTreeForest.cpp:86``) and ``CSpeedTreeWrapper::LoadTree``
  defaults ``fSize = -1.0f`` (``SpeedTreeWrapper.h:102``); ``SetTreeSize`` is
  only called ``if (fSize >= 0.0f && fSizeVariance >= 0.0f)``
  (``SpeedTreeWrapper.cpp:339-340``).  The editor's preview
  (``MapObjectPropertyPageTree.cpp:237``) and cursor
  (``SceneMapCursor.cpp:327``) also use the default.  Nothing in either tree
  passes a size.

The size that *is* used comes from the ``.spt`` itself.  Token ``0x07D1``
carries a float that takes exactly four values across the 87 shipped trees --
50 (16 files: aloevera, fern, banana), 400 (8: spruce, whitepine, palmetto),
600 (5: shingleoak) and 1100 (58: the full-size broadleaf/conifer set) -- which
tracks plant size, so this module reports it as ``spt_size``.  It is a height
in world centimetres, not a footprint; horizontal spread stays unknown.

Units
-----

GR2 vertex positions are world centimetres in the model's own space, Z up
(measured: ``a1-001-house3.gr2`` spans ``z[-1.06, 1071.44]`` with a flat floor
at z~0).  ``size_xyz`` is therefore ``(width, depth, height)`` in cm, and
``footprint_r`` is the horizontal half-diagonal -- the radius a rotation-
agnostic spacing rule should use.

Usage
-----

``python -m m2map.mine.models --out <catalog dir>``
    Walk the property database, read every referenced art file, write
    ``models.json``.

``python -m m2map.mine.models --one "d:/ymir work/zone/a/building/a1-001-house3.gr2"``
    Dump one file to stdout (accepts ``.gr2``, ``.mdatr`` or ``.spt``).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import pathlib
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from collections import Counter

_HERE = pathlib.Path(__file__).resolve()
if str(_HERE.parents[2]) not in sys.path:                  # .../scripts
    sys.path.insert(0, str(_HERE.parents[2]))

from m2map.codec.property import scan_property_dir          # noqa: E402

__all__ = [
    "DEFAULTS", "Gr2Error", "Gr2File", "read_gr2", "read_mdatr", "read_spt",
    "resolve_art_path", "scan", "shape_envelope", "main",
]

SKILL_ROOT = _HERE.parents[3]                              # .../skills/m2map

DEFAULTS = {
    "property": r"<CLIENT_PACK>/property/property",
    "art": r"D:/ymir work",
    "grn": r"<OPENGRANNY>/target/release/grn-preprocessor.exe",
    "out": str(SKILL_ROOT / "reference" / "catalog"),
}

#: The declared prefix every property model path starts with.
ART_PREFIX = "d:/ymir work/"


# ==========================================================================
# GR2 container + self-describing type walker
# ==========================================================================

class Gr2Error(Exception):
    """Raised for anything the GR2 reader refuses to guess at."""


#: ``granny_member_type`` -> label (docs/03-type-system.md).
MEMBER_NAMES = {
    0: "End", 1: "Inline", 2: "Ref", 3: "RefToArray", 4: "ArrayOfRefs",
    5: "VariantRef", 6: "Removed", 7: "RefToVariantArray", 8: "String",
    9: "Transform", 10: "Real32", 11: "Int8", 12: "UInt8", 13: "BinormalInt8",
    14: "NormalUInt8", 15: "Int16", 16: "UInt16", 17: "BinormalInt16",
    18: "NormalUInt16", 19: "Int32", 20: "UInt32", 21: "Real16",
    22: "EmptyRef",
}

#: Fixed-width member sizes.  ``Transform`` is 68 and is *not* multiplied by
#: ``ArrayWidth`` (OpenGranny ``typewalker.rs:member_size``).
_SCALAR_SIZE = {
    10: 4, 11: 1, 12: 1, 13: 1, 14: 1, 15: 2, 16: 2, 17: 2, 18: 2,
    19: 4, 20: 4, 21: 2,
}

#: Magic signatures as ``struct.unpack('<4I')`` reads them.
#:
#: The SDK-2.11 row matches docs/01-gr2-format.md exactly.  The *legacy* row
#: does not: the doc lists the bytes as ``CA B0 67 B8 0F B1 6D F8 ...`` with
#: ``u32[0] == 0xB867B0CA``, but every legacy file in this corpus starts
#: ``B8 67 B0 CA F8 6D B1 0F 84 72 8C 7E 5E 19 00 1E`` -- each 4-byte group is
#: byte-reversed relative to the doc.  Measured on
#: ``ymir work/zone/a/building/a1-001-house3.gr2`` and 1765 others; the
#: measurement wins, so the constants below are the observed ones.
_MAGIC_32LE = {
    (0xC06CDE29, 0x2B53A4BA, 0xA5B7F525, 0xEEE266F6),   # SDK 2.11, v7   (357 files)
    (0xCAB067B8, 0x0FB16DF8, 0x7E8C7284, 0x1E00195E),   # legacy,   v6   (1766 files)
}
_MAGIC_64LE = {
    (0xC06CDE29, 0x2B53A4BA, 0xA5B7F525, 0xEEE366F6),
    (0xCAB067B8, 0x0FB16DF8, 0x7E8C7284, 0x1E01195E),
}

TYPE_DEF_STRIDE_32 = 32          # MemberType, Name*, RefType*, Width, Extra[3], Unused
MAX_TYPE_MEMBERS = 4096


class Gr2File:
    """A GR2 whose sections are already uncompressed (``Format == 0``).

    Pointers are resolved through the section fixup tables, never through the
    bytes stored in the pointer slot -- those hold serialised garbage until a
    loader overwrites them (docs/01-gr2-format.md section 4, and OpenGranny
    ``oodle1.rs`` module docstring).
    """

    def __init__(self, data: bytes):
        if len(data) < 128:
            raise Gr2Error("file too short (%d bytes)" % len(data))
        magic = struct.unpack_from("<4I", data, 0)
        if magic in _MAGIC_64LE:
            raise Gr2Error("64-bit GR2 not supported by this reader")
        if magic not in _MAGIC_32LE:
            raise Gr2Error("not a little-endian 32-bit GR2 (magic %s)"
                           % " ".join("%08X" % m for m in magic))
        self.header_size, self.header_format = struct.unpack_from("<2I", data, 16)
        if self.header_format != 0:
            raise Gr2Error("compressed header (HeaderFormat=%d)" % self.header_format)
        (self.version, self.total_size, self.crc,
         section_array_offset, section_count) = struct.unpack_from("<5I", data, 32)
        off = 52
        rt_sec, rt_off, ro_sec, ro_off = struct.unpack_from("<4I", data, off)
        self.root_type = (rt_sec, rt_off)
        self.root_obj = (ro_sec, ro_off)
        self.type_tag = struct.unpack_from("<I", data, off + 16)[0]
        self.ptr_size = 4

        self.sections: list[bytes] = []
        self.fixups: list[dict] = []
        base = 32 + section_array_offset
        for i in range(section_count):
            (fmt, data_off, data_size, expanded, _align, _f16, _f8,
             pf_off, pf_count, _mm_off, _mm_count) = struct.unpack_from(
                "<11I", data, base + 44 * i)
            if fmt != 0:
                raise Gr2Error("section %d is compressed (format %d) -- "
                               "run grn-preprocessor decompress first" % (i, fmt))
            self.sections.append(data[data_off:data_off + expanded])
            fx = {}
            for j in range(pf_count):
                from_off, to_sec, to_off = struct.unpack_from(
                    "<3I", data, pf_off + 12 * j)
                fx[from_off] = (to_sec, to_off)
            self.fixups.append(fx)
        self._type_cache: dict = {}

    # -- primitives --------------------------------------------------------
    def ptr(self, sec: int, off: int):
        """Resolve the pointer stored at ``(sec, off)``; ``None`` for NULL."""
        return self.fixups[sec].get(off)

    def i32(self, sec: int, off: int) -> int:
        return struct.unpack_from("<i", self.sections[sec], off)[0]

    def u32(self, sec: int, off: int) -> int:
        return struct.unpack_from("<I", self.sections[sec], off)[0]

    def cstr(self, ref):
        if ref is None:
            return None
        sec, off = ref
        buf = self.sections[sec]
        end = buf.find(b"\0", off)
        return buf[off:end if end >= 0 else len(buf)].decode("cp1252", "replace")

    # -- type metadata -----------------------------------------------------
    def member_size(self, m) -> int:
        t, w, p = m["t"], max(m["w"], 1), self.ptr_size
        if t == 1:
            return self.type_size(m["ref"]) * w
        if t in (2, 8, 22):
            return p
        if t in (3, 4):
            return 4 + p                 # count + pointer
        if t == 5:
            return 2 * p                 # type* + object*
        if t == 7:
            return 4 + 2 * p             # type* + count + object* (see note)
        if t == 9:
            return 68
        if t == 6:
            return 0
        return _SCALAR_SIZE.get(t, 4) * w

    def type(self, ref):
        """Parse the type-definition array at ``ref`` into member records.

        Each record carries the byte offset of its field inside the object;
        ``_size`` on every record is the total object size.
        """
        if ref is None:
            return []
        cached = self._type_cache.get(ref)
        if cached is not None:
            return cached
        self._type_cache[ref] = []                      # recursion guard
        sec, off = ref
        buf = self.sections[sec]
        members = []
        o = off
        while o + TYPE_DEF_STRIDE_32 <= len(buf) and len(members) < MAX_TYPE_MEMBERS:
            mt = struct.unpack_from("<I", buf, o)[0]
            if mt == 0:
                break
            members.append({
                "t": mt,
                "name": self.cstr(self.ptr(sec, o + 4)),
                "ref": self.ptr(sec, o + 8),
                "w": struct.unpack_from("<I", buf, o + 12)[0],
            })
            o += TYPE_DEF_STRIDE_32
        cur = 0
        for m in members:
            m["off"] = cur
            cur += self.member_size(m)
        for m in members:
            m["_size"] = cur
        self._type_cache[ref] = members
        return members

    def type_size(self, ref) -> int:
        ms = self.type(ref)
        return ms[0]["_size"] if ms else 0

    @staticmethod
    def member(members, name):
        for m in members:
            if m["name"] == name:
                return m
        return None

    # -- field accessors ---------------------------------------------------
    def array_of_refs(self, members, obj, name):
        """``ArrayOfReferencesMember`` -> list of object refs."""
        m = self.member(members, name)
        if m is None:
            return []
        sec, off = obj
        count = self.i32(sec, off + m["off"])
        table = self.ptr(sec, off + m["off"] + 4)
        if table is None or count <= 0:
            return []
        return [self.ptr(table[0], table[1] + 4 * i) for i in range(count)]

    def ref_to_array(self, members, obj, name):
        """``ReferenceToArrayMember`` -> ``(count, ref_to_first_element)``."""
        m = self.member(members, name)
        if m is None:
            return 0, None
        sec, off = obj
        return self.i32(sec, off + m["off"]), self.ptr(sec, off + m["off"] + 4)

    def variant_array(self, members, obj, name):
        """``ReferenceToVariantArrayMember`` -> ``(type_ref, count, data_ref)``.

        The on-disk field order is ``type*, count, object*`` -- **not** the
        ``count, type*, object*`` order both docs/01-gr2-format.md and
        OpenGranny's ``typesys.rs:29`` comment imply.  Verified on
        ``a1-001-house3.gr2``: the word at +0 fixes up into the type section,
        +4 reads 3119 (== 99808 section bytes / 32-byte stride) and +8 fixes up
        to section 1 offset 0.
        """
        m = self.member(members, name)
        if m is None:
            return None, 0, None
        sec, off = obj
        base = off + m["off"]
        return self.ptr(sec, base), self.i32(sec, base + 4), self.ptr(sec, base + 8)

    def get_ref(self, members, obj, name):
        m = self.member(members, name)
        return None if m is None else self.ptr(obj[0], obj[1] + m["off"])

    def get_str(self, members, obj, name):
        m = self.member(members, name)
        return None if m is None else self.cstr(self.ptr(obj[0], obj[1] + m["off"]))

    def get_i32(self, members, obj, name):
        m = self.member(members, name)
        return None if m is None else self.i32(obj[0], obj[1] + m["off"])


# ==========================================================================
# decompression front-end
# ==========================================================================

def _is_uncompressed(data: bytes) -> bool:
    """True when every non-empty section is already ``Format == 0``."""
    try:                                    # header@32: ver, size, crc, secOff, secCount
        section_array_offset, count = struct.unpack_from("<2I", data, 44)
    except struct.error:
        return False
    base = 32 + section_array_offset
    for i in range(count):
        try:
            fmt = struct.unpack_from("<I", data, base + 44 * i)[0]
        except struct.error:
            return False
        if fmt != 0:
            return False
    return True


class Decompressor:
    """Wraps OpenGranny ``grn-preprocessor.exe decompress``.

    A pure-Python Oodle1 decoder is not provided: the codec is a 7-bit-per-byte
    range coder with adaptive binary-tree models (OpenGranny ``oodle1.rs``,
    816 lines reconstructed from the decompiled DLL) and would decode the
    corpus's ~300 MB of expanded sections at Python speed.  See
    ``reference/models.md``.
    """

    def __init__(self, exe: str | None, workdir: pathlib.Path | None = None):
        self.exe = exe
        self._tmp = None
        if workdir is None:
            self._tmp = tempfile.TemporaryDirectory(prefix="m2map-gr2-")
            workdir = pathlib.Path(self._tmp.name)
        self.workdir = pathlib.Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.out = self.workdir / "_decompressed.gr2"
        self.calls = 0

    def available(self) -> bool:
        return bool(self.exe) and pathlib.Path(self.exe).is_file()

    def load(self, path) -> bytes:
        path = pathlib.Path(path)
        data = path.read_bytes()
        if _is_uncompressed(data):
            return data
        if not self.available():
            raise Gr2Error("compressed GR2 and no grn-preprocessor.exe "
                           "(pass --grn or set M2MAP_GRN)")
        proc = subprocess.run(
            [self.exe, "decompress", str(path), "-output", str(self.out)],
            capture_output=True, text=True)
        self.calls += 1
        if proc.returncode != 0 or not self.out.is_file():
            raise Gr2Error("grn-preprocessor failed: %s"
                           % (proc.stderr or proc.stdout).strip()[:200])
        return self.out.read_bytes()

    def close(self):
        if self._tmp is not None:
            self._tmp.cleanup()
            self._tmp = None


# ==========================================================================
# .gr2
# ==========================================================================

def _bbox_union(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return [min(a[i], b[i]) for i in range(3)] + [max(a[3 + i], b[3 + i]) for i in range(3)]


def _vertex_bbox(f: Gr2File, type_ref, count: int, data_ref):
    """Min/max of the ``Position`` member over ``count`` vertices."""
    vt = f.type(type_ref)
    if not vt:
        raise Gr2Error("vertex array has no type definition")
    stride = vt[0]["_size"]
    pos = f.member(vt, "Position")
    if pos is None:
        raise Gr2Error("vertex type has no Position member")
    if pos["t"] != 10 or max(pos["w"], 1) != 3:
        raise Gr2Error("Position is %s[%d], expected Real32[3]"
                       % (MEMBER_NAMES.get(pos["t"], pos["t"]), max(pos["w"], 1)))
    buf = f.sections[data_ref[0]]
    start = data_ref[1] + pos["off"]
    if start + (count - 1) * stride + 12 > len(buf):
        raise Gr2Error("vertex array overruns section (%d vertices x %d stride)"
                       % (count, stride))
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    unpack = struct.Struct("<3f").unpack_from
    for i in range(count):
        v = unpack(buf, start + i * stride)
        for k in range(3):
            if v[k] < lo[k]:
                lo[k] = v[k]
            if v[k] > hi[k]:
                hi[k] = v[k]
    return lo + hi, stride, tuple((m["name"], m["t"], max(m["w"], 1)) for m in vt)


def read_gr2(path, decomp: "Decompressor | None" = None) -> dict:
    """Extract geometry + material facts from one ``.gr2``.

    Returns a dict with ``ok`` True/False; on failure ``error`` says why.
    """
    path = pathlib.Path(path)
    out = {"ok": False, "file": str(path)}
    decomp = decomp or Decompressor(os.environ.get("M2MAP_GRN") or DEFAULTS["grn"])
    try:
        f = Gr2File(decomp.load(path))
    except (OSError, Gr2Error, struct.error) as exc:
        out["error"] = "%s: %s" % (type(exc).__name__, exc)
        return out

    try:
        fi = f.type(f.root_type)
        if not fi:
            raise Gr2Error("root type definition is empty")
        root = f.root_obj

        vd_t = f.type(f.member(fi, "VertexDatas")["ref"]) if f.member(fi, "VertexDatas") else []
        tt_t = f.type(f.member(fi, "TriTopologies")["ref"]) if f.member(fi, "TriTopologies") else []
        me_t = f.type(f.member(fi, "Meshes")["ref"]) if f.member(fi, "Meshes") else []
        tx_t = f.type(f.member(fi, "Textures")["ref"]) if f.member(fi, "Textures") else []
        ma_t = f.type(f.member(fi, "Materials")["ref"]) if f.member(fi, "Materials") else []
        mo_t = f.type(f.member(fi, "Models")["ref"]) if f.member(fi, "Models") else []
        sk_t = f.type(f.member(fi, "Skeletons")["ref"]) if f.member(fi, "Skeletons") else []

        bbox = None
        vertices = 0
        formats = set()
        for vd in f.array_of_refs(fi, root, "VertexDatas"):
            if vd is None:
                continue
            type_ref, count, data_ref = f.variant_array(vd_t, vd, "Vertices")
            if count <= 0 or data_ref is None or type_ref is None:
                continue
            bb, _stride, fmt = _vertex_bbox(f, type_ref, count, data_ref)
            bbox = _bbox_union(bbox, bb)
            vertices += count
            formats.add(fmt)

        triangles = 0
        for tt in f.array_of_refs(fi, root, "TriTopologies"):
            if tt is None:
                continue
            n32, _ = f.ref_to_array(tt_t, tt, "Indices")
            n16, _ = f.ref_to_array(tt_t, tt, "Indices16")
            triangles += (n32 or n16) // 3

        meshes = [f.get_str(me_t, m, "Name") for m in f.array_of_refs(fi, root, "Meshes") if m]
        models = [f.get_str(mo_t, m, "Name") for m in f.array_of_refs(fi, root, "Models") if m]
        materials = [f.get_str(ma_t, m, "Name") for m in f.array_of_refs(fi, root, "Materials") if m]
        textures = [f.get_str(tx_t, t, "FromFileName") for t in f.array_of_refs(fi, root, "Textures") if t]

        bones = 0
        for sk in f.array_of_refs(fi, root, "Skeletons"):
            if sk:
                n, _ = f.ref_to_array(sk_t, sk, "Bones")
                bones += n

        placement = None
        ip = f.member(mo_t, "InitialPlacement") if mo_t else None
        for m in f.array_of_refs(fi, root, "Models"):
            if m is None or ip is None:
                continue
            sec, off = m
            flags = f.u32(sec, off + ip["off"])
            pos = struct.unpack_from("<3f", f.sections[sec], off + ip["off"] + 4)
            if flags or any(abs(v) > 1e-4 for v in pos):
                placement = {"flags": flags, "pos": [round(v, 3) for v in pos]}

        if bbox is None:
            out["error"] = "no vertex data"
            return out

        # One shipped asset (zone/dungeon/haven_dungeon/skipia_collision.gr2,
        # 3 vertices) stores junk in its vertex buffer and yields extents of
        # 1e17 cm.  Flag rather than silently poison a spacing rule: the whole
        # map grid is 102400 cm across, so 1e6 cm is far past any real model.
        degenerate = any((not math.isfinite(v)) or abs(v) > 1e6 for v in bbox)

        size = [round(bbox[3 + i] - bbox[i], 2) for i in range(3)]
        if degenerate:
            out["degenerate"] = True
            out["error"] = "implausible vertex extents -- treat size as unknown"
        out.update({
            "ok": True,
            "gr2_version": f.version,
            "bbox_min": [round(bbox[i], 2) for i in range(3)],
            "bbox_max": [round(bbox[3 + i], 2) for i in range(3)],
            "size_xyz": size,
            "center": [round((bbox[i] + bbox[3 + i]) / 2.0, 2) for i in range(3)],
            "footprint_r": round(math.hypot(size[0], size[1]) / 2.0, 2),
            "height": size[2],
            "vertices": vertices,
            "triangles": triangles,
            "meshes": len(meshes),
            "mesh_names": meshes,
            "models": models,
            "materials": materials,
            "textures": textures,
            "bones": bones,
            "vertex_formats": sorted(
                "+".join("%s:%s[%d]" % (n, MEMBER_NAMES.get(t, t), w) for n, t, w in fmt)
                for fmt in formats),
            "source_max_file": f.get_str(fi, root, "FromFileName"),
        })
        if placement:
            out["initial_placement"] = placement
    except (Gr2Error, struct.error, IndexError, KeyError, TypeError) as exc:
        out["error"] = "%s: %s" % (type(exc).__name__, exc)
    return out


# ==========================================================================
# .mdatr  (EterLib/AttributeData.cpp:44-130)
# ==========================================================================

MDATR_MAGIC = b"AttributeData\0"

#: ``ECollisionType`` -> (label, dimension floats)  (EterLib/CollisionData.h:42)
COLLISION_TYPES = {
    0: ("plane", 2), 1: ("box", 3), 2: ("sphere", 1),
    3: ("cylinder", 2), 4: ("aabb", 3), 5: ("obb", 3),
}


def shape_envelope(label, dims, quat):
    """Local-frame ``(lo, hi)`` offsets from ``v3Position`` for one primitive.

    Read straight off ``EterLib/CollisionData.cpp:29-210``
    (``CBaseCollisionInstance::New``).  **The units are not consistent between
    types** -- this is an engine quirk, not a guess:

    ==========  ===================================================  ==========
    type        how the engine reads ``fDimensions``                 rotated?
    ==========  ===================================================  ==========
    plane       ``fHalfWidth = d[0]/2``, ``fHalfLength = d[1]/2``     yes
                -> **full** extents, quad in local XY, normal on Z    (:42-58)
    box         ``d[0]/2`` on X, ``d[2]/2`` on **Y**, ``d[1]/2`` on   no
                **Z** -- full extents with the Y/Z axes swapped       (:94-102)
    aabb        ``pos +/- d[k]`` -> **half** extents                  no (:125)
    obb         ``pos +/- d[k]`` -> **half** extents; ``matRot`` is   no (:149)
                the object's world matrix, not ``quatRotation``
    sphere      ``fRadius = d[0]``                                    n/a (:188)
    cylinder    ``fRadius = d[0]``, ``fHeight = d[1]``, and the       no (:202)
                ``+ fHeight/2`` on the centre is commented out, so
                the cylinder runs from ``pos.z`` to ``pos.z + d[1]``
    ==========  ===================================================  ==========

    Only the plane case applies ``quatRotation``; every other branch builds its
    volume from the position and dimensions alone.

    Shipped data uses only plane (11243), cylinder (456) and sphere (217).
    Treating the plane's dims as half-extents inflates the envelope by 2x --
    measured median collision/render on X went from 1.35 to 0.95 after the
    ``/2`` was applied.
    """
    d = list(dims) + [0.0, 0.0, 0.0]
    if label == "plane":
        half = (d[0] / 2.0, d[1] / 2.0, 0.0)
        ext = _aabb_of_rotated_box(half, quat)
        return [-e for e in ext], list(ext)
    if label == "box":
        half = (d[0] / 2.0, d[2] / 2.0, d[1] / 2.0)
    elif label in ("aabb", "obb"):
        half = (d[0], d[1], d[2])
    elif label == "sphere":
        half = (d[0], d[0], d[0])
    elif label == "cylinder":
        return [-d[0], -d[0], 0.0], [d[0], d[0], d[1]]
    else:
        half = (0.0, 0.0, 0.0)
    return [-h for h in half], list(half)


def _aabb_of_rotated_box(half, quat):
    """World-axis half-extents of a box with half-extents ``half`` rotated by
    ``quat`` (D3DXQUATERNION order x, y, z, w).

    ``extent[k] = sum_j |R[k][j]| * half[j]`` -- the standard OBB-to-AABB
    envelope, exact rather than the half-diagonal over-estimate.
    """
    x, y, z, w = quat
    n = x * x + y * y + z * z + w * w
    if n <= 1e-12:
        return list(half)
    s = 2.0 / n
    xx, yy, zz = x * x * s, y * y * s, z * z * s
    xy, xz, yz = x * y * s, x * z * s, y * z * s
    wx, wy, wz = w * x * s, w * y * s, w * z * s
    rot = (
        (1.0 - (yy + zz), xy - wz, xz + wy),
        (xy + wz, 1.0 - (xx + zz), yz - wx),
        (xz - wy, yz + wx, 1.0 - (xx + yy)),
    )
    return [sum(abs(rot[k][j]) * half[j] for j in range(3)) for k in range(3)]


def read_mdatr(path) -> dict:
    """Parse a per-model collision/height proxy.

    Layout: ``"AttributeData\\0"``, ``u32 collisionCount``, ``u32 heightCount``,
    then per collision ``u32 type``, ``char name[32]``, ``float pos[3]``,
    ``float dims[n]`` (n from the type), ``float quat[4]``; then per height
    record ``char name[32]``, ``u32 vertexCount``, ``float xyz[3] * count``.
    """
    path = pathlib.Path(path)
    out = {"ok": False, "file": str(path)}
    try:
        b = path.read_bytes()
    except OSError as exc:
        out["error"] = str(exc)
        return out
    if b[:len(MDATR_MAGIC)] != MDATR_MAGIC:
        out["error"] = "bad magic %r" % b[:14]
        return out
    o = len(MDATR_MAGIC)
    try:
        n_col, n_hgt = struct.unpack_from("<2I", b, o)
        o += 8
        shapes = []
        lo = [math.inf] * 3
        hi = [-math.inf] * 3
        for _ in range(n_col):
            ctype = struct.unpack_from("<I", b, o)[0]
            o += 4
            name = b[o:o + 32].split(b"\0")[0].decode("cp1252", "replace")
            o += 32
            pos = struct.unpack_from("<3f", b, o)
            o += 12
            label, ndim = COLLISION_TYPES.get(ctype, ("unknown", 0))
            dims = struct.unpack_from("<%df" % ndim, b, o) if ndim else ()
            o += 4 * ndim
            quat = struct.unpack_from("<4f", b, o)
            o += 16
            shapes.append({"type": label, "name": name,
                           "pos": [round(v, 2) for v in pos],
                           "dims": [round(v, 2) for v in dims],
                           "quat": [round(v, 4) for v in quat]})
            elo, ehi = shape_envelope(label, dims, quat)
            for k in range(3):
                lo[k] = min(lo[k], pos[k] + elo[k])
                hi[k] = max(hi[k], pos[k] + ehi[k])
        heights = []
        for _ in range(n_hgt):
            name = b[o:o + 32].split(b"\0")[0].decode("cp1252", "replace")
            o += 32
            n_v = struct.unpack_from("<I", b, o)[0]
            o += 4
            vs = struct.unpack_from("<%df" % (3 * n_v), b, o) if n_v else ()
            o += 12 * n_v
            for i in range(n_v):
                for k in range(3):
                    v = vs[3 * i + k]
                    lo[k] = min(lo[k], v)
                    hi[k] = max(hi[k], v)
            heights.append({"name": name, "vertices": n_v})
    except struct.error as exc:
        out["error"] = "truncated: %s" % exc
        return out
    if o != len(b):
        out["trailing_bytes"] = len(b) - o
    out.update({
        "ok": True,
        "collision_shapes": len(shapes),
        "height_planes": len(heights),
        "shape_types": dict(Counter(s["type"] for s in shapes)),
        "shapes": shapes,
        "height_plane_names": [h["name"] for h in heights],
    })
    if math.isfinite(lo[0]):
        out["collision_bbox_min"] = [round(v, 2) for v in lo]
        out["collision_bbox_max"] = [round(v, 2) for v in hi]
        out["collision_size_xyz"] = [round(hi[i] - lo[i], 2) for i in range(3)]
    return out


# ==========================================================================
# .spt  (SpeedTree RT "__IdvSpt_02_")
# ==========================================================================

SPT_MAGIC = b"__IdvSpt_02_"
SPT_TOKEN_SIZE = b"\xd1\x07\x00\x00"        # 0x07D1
SPT_TOKEN_VARIANCE = b"\xd2\x07\x00\x00"    # 0x07D2


def read_spt(path) -> dict:
    """Read what little the SpeedTree file exposes without the RT library.

    The bounding box requires ``CSpeedTreeRT::Compute()``; only the authored
    size / variance tokens can be recovered here.
    """
    path = pathlib.Path(path)
    out = {"ok": False, "file": str(path)}
    try:
        b = path.read_bytes()
    except OSError as exc:
        out["error"] = str(exc)
        return out
    if SPT_MAGIC not in b[:64]:
        out["error"] = "not an __IdvSpt_02_ file"
        return out
    i = b.find(SPT_TOKEN_SIZE)
    j = b.find(SPT_TOKEN_VARIANCE)
    out["ok"] = True
    out["bytes"] = len(b)
    if i >= 0:
        out["spt_size"] = round(struct.unpack_from("<f", b, i + 4)[0], 2)
    if j >= 0:
        out["spt_variance"] = round(struct.unpack_from("<f", b, j + 4)[0], 4)
    out["bbox_available"] = False
    out["note"] = "procedural; bounding box needs CSpeedTreeRT::Compute()"
    return out


# ==========================================================================
# catalog pass
# ==========================================================================

def resolve_art_path(declared: str, art_root) -> pathlib.Path | None:
    """Map a property's ``d:/ymir work/...`` path onto ``art_root``."""
    if not declared:
        return None
    p = declared.replace("\\", "/").strip().lower()
    if p.startswith(ART_PREFIX):
        p = p[len(ART_PREFIX):]
    elif p.startswith("d:/"):
        p = p[3:]
    return pathlib.Path(art_root) / p


def _case_insensitive_find(path: pathlib.Path):
    """Windows is case-insensitive, but be explicit so Linux runs work too."""
    if path.is_file():
        return path
    parent = path.parent
    if not parent.is_dir():
        return None
    want = path.name.lower()
    for c in parent.iterdir():
        if c.name.lower() == want and c.is_file():
            return c
    return None


def scan(property_root, art_root, grn=None, limit=None, verbose=True) -> dict:
    """Walk the property database and read every referenced art file."""
    registry = scan_property_dir(property_root)
    decomp = Decompressor(grn)
    entries = {}
    stats = Counter()
    problems = []
    t0 = time.time()
    items = sorted(registry.items())
    if limit:
        items = items[:limit]
    for n, (crc, prop) in enumerate(items, 1):
        rec = {
            "crc": crc,
            "name": prop.name,
            "type": prop.property_type,
            "property_file": pathlib.Path(prop.path).name if prop.path else None,
            "model": prop.model_file,
        }
        stats["properties"] += 1
        declared = prop.model_file
        if not declared:
            rec["status"] = "no-model-path"          # Ambience has none
            stats["no-model"] += 1
            entries[str(crc)] = rec
            continue
        art = resolve_art_path(declared, art_root)
        real = _case_insensitive_find(art) if art else None
        if real is None:
            rec["status"] = "missing-file"
            stats["missing-file"] += 1
            problems.append({"crc": crc, "name": prop.name,
                             "problem": "art file not found", "path": str(art)})
            entries[str(crc)] = rec
            continue
        rec["art_path"] = str(real).replace("\\", "/")
        ext = real.suffix.lower()
        if ext == ".gr2":
            info = read_gr2(real, decomp)
            if info.pop("ok"):
                info.pop("file", None)
                rec.update(info)
                if info.get("degenerate"):
                    rec["status"] = "gr2-degenerate"
                    stats["gr2-degenerate"] += 1
                    problems.append({"crc": crc, "name": prop.name,
                                     "problem": info.get("error"),
                                     "path": rec["art_path"]})
                else:
                    rec["status"] = "ok"
                    stats["gr2-ok"] += 1
            else:
                rec["status"] = "gr2-failed"
                rec["error"] = info.get("error")
                stats["gr2-failed"] += 1
                problems.append({"crc": crc, "name": prop.name,
                                 "problem": info.get("error"), "path": rec["art_path"]})
        elif ext == ".spt":
            info = read_spt(real)
            if info.pop("ok"):
                info.pop("file", None)
                rec.update(info)
                rec["status"] = "spt-partial"
                stats["spt-partial"] += 1
            else:
                rec["status"] = "spt-failed"
                rec["error"] = info.get("error")
                stats["spt-failed"] += 1
        else:
            rec["status"] = "unsupported-extension"
            stats["unsupported-extension"] += 1

        # collision proxy, when the model declares one
        coll = prop.collision_file
        if coll:
            cpath = resolve_art_path(coll, art_root)
            creal = _case_insensitive_find(cpath) if cpath else None
            if creal is not None:
                cinfo = read_mdatr(creal)
                if cinfo.pop("ok"):
                    rec["mdatr"] = {
                        k: cinfo[k] for k in
                        ("collision_shapes", "height_planes", "shape_types",
                         "collision_bbox_min", "collision_bbox_max",
                         "collision_size_xyz")
                        if k in cinfo
                    }
                    stats["mdatr-ok"] += 1
                else:
                    stats["mdatr-failed"] += 1
            else:
                stats["mdatr-absent"] += 1
        entries[str(crc)] = rec
        if verbose and n % 200 == 0:
            print("  %4d/%d  %.1fs" % (n, len(items), time.time() - t0), flush=True)
    decomp.close()
    return {
        "generated_from": {
            "property": str(property_root),
            "art": str(art_root),
            "grn": grn,
            "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "elapsed_s": round(time.time() - t0, 1),
        },
        "counts": dict(stats),
        "problems": problems,
        "models": entries,
    }


# ==========================================================================
# thumbnails -- WorldEditorRemix headless
# ==========================================================================

#: ``--size W,H`` sizes the *frame*; the 3D view loses the docking bars, so
#: the PNG comes out ``(W - 220) x (H - 59)``.  Measured: 732,571 -> 512x512;
#: 1400,900 -> 1180x841; 900,900 -> 680x841.
WE_CHROME = (220, 59)


def we_size_for(width: int, height: int) -> str:
    return "%d,%d" % (width + WE_CHROME[0], height + WE_CHROME[1])


def shoot(we_exe, data_dir, art_path, out_png, width=512, height=512,
          timeout=120) -> dict:
    """Render one ``.gr2`` / ``.msm`` with WorldEditorRemix's headless mode.

    ``art_path`` must be *relative to* ``data_dir`` (the editor resolves art
    against its own working directory).  Returns a dict with ``ok``.

    The editor **always exits 0 and always writes a PNG**, even when the model
    fails to load or the extension is unsupported (``.spt`` is not renderable
    -- ``WorldEditor.cpp:693`` logs "unsupported --file extension" and leaves
    the default scene up, and MfcRelease does not surface that trace on
    stderr).  So success is decided by comparing against the null render, not
    by the exit code.
    """
    out_png = pathlib.Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    if out_png.exists():
        out_png.unlink()
    cmd = [str(we_exe), "--file", str(art_path), "--size",
           we_size_for(width, height), "--shot", str(out_png), "--quit"]
    res = {"cmd": cmd, "ok": False}
    try:
        subprocess.run(cmd, cwd=str(data_dir), capture_output=True,
                       timeout=timeout)
    except subprocess.TimeoutExpired:
        res["error"] = "timeout after %ds" % timeout
        return res
    if not out_png.is_file():
        res["error"] = "no png written"
        return res
    res["bytes"] = out_png.stat().st_size
    # A frame with nothing in it compresses to ~2 KB at 512x512; a real model
    # render is >8 KB.  Callers that need certainty should also hash-compare
    # against a null render taken with a deliberately bogus --file.
    if res["bytes"] < 4096:
        res["error"] = "blank render (%d bytes) -- model probably failed to load" % res["bytes"]
        return res
    res["ok"] = True
    return res


def _find_grn(explicit):
    for cand in (explicit, os.environ.get("M2MAP_GRN"), DEFAULTS["grn"]):
        if cand and pathlib.Path(cand).is_file():
            return str(cand)
    which = shutil.which("grn-preprocessor")
    return which


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m m2map.mine.models",
        description="Read physical size / mesh / texture facts out of the art files "
                    "the property catalog points at.")
    ap.add_argument("--property", dest="property_root", default=DEFAULTS["property"])
    ap.add_argument("--art", default=DEFAULTS["art"],
                    help="root that 'd:/ymir work/' maps onto")
    ap.add_argument("--grn", default=None,
                    help="grn-preprocessor.exe (else $M2MAP_GRN, else the default path)")
    ap.add_argument("--out", default=DEFAULTS["out"])
    ap.add_argument("--limit", type=int, default=None,
                    help="only the first N properties (by CRC)")
    ap.add_argument("--one", default=None,
                    help="dump a single .gr2 / .mdatr / .spt to stdout and exit")
    ap.add_argument("--thumbs", default=None, metavar="DIR",
                    help="render thumbnails for the models in models.json "
                         "(needs --we; .spt cannot be rendered)")
    ap.add_argument("--we", default=r"D:/WorldEditorRemix_MfcRelease_x64.exe",
                    help="WorldEditorRemix executable for --thumbs")
    ap.add_argument("--we-cwd", default="D:/",
                    help="data dir the editor runs in (holds pack/ and ymir work/)")
    ap.add_argument("--thumb-size", type=int, default=512)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    verbose = not args.quiet
    grn = _find_grn(args.grn)

    if args.one:
        p = pathlib.Path(args.one)
        ext = p.suffix.lower()
        if ext == ".gr2":
            info = read_gr2(p, Decompressor(grn))
        elif ext == ".mdatr":
            info = read_mdatr(p)
        elif ext == ".spt":
            info = read_spt(p)
        else:
            print("unsupported extension %s" % ext, file=sys.stderr)
            return 2
        print(json.dumps(info, indent=1, ensure_ascii=False))
        return 0 if info.get("ok") else 1

    if args.thumbs:
        src = pathlib.Path(args.out) / "models.json"
        if not src.is_file():
            print("run the scan first: %s does not exist" % src, file=sys.stderr)
            return 2
        doc = json.loads(src.read_text(encoding="utf-8"))
        data_dir = pathlib.Path(args.we_cwd)
        dest = pathlib.Path(args.thumbs)
        done = failed = skipped = 0
        t0 = time.time()
        for crc, m in sorted(doc["models"].items()):
            art = m.get("art_path")
            if not art or not art.lower().endswith((".gr2", ".msm")):
                skipped += 1
                continue
            try:
                rel = pathlib.Path(art).relative_to(data_dir)
            except ValueError:
                skipped += 1
                continue
            png = dest / ("%s.png" % crc)
            if png.is_file():
                done += 1
                continue
            r = shoot(args.we, data_dir, rel, png,
                      args.thumb_size, args.thumb_size)
            if r["ok"]:
                done += 1
            else:
                failed += 1
                if verbose:
                    print("  thumb FAILED %s (%s): %s"
                          % (crc, m.get("name"), r.get("error")), file=sys.stderr)
            if verbose and (done + failed) % 25 == 0:
                print("  %d rendered, %d failed, %.0fs"
                      % (done, failed, time.time() - t0), flush=True)
        if verbose:
            print("thumbnails: %d ok, %d failed, %d skipped (%.0fs)"
                  % (done, failed, skipped, time.time() - t0))
        return 0 if failed == 0 else 1

    if grn is None and verbose:
        print("warning: grn-preprocessor.exe not found -- compressed .gr2 will fail",
              file=sys.stderr)
    doc = scan(args.property_root, args.art, grn, args.limit, verbose)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / "models.json"
    dest.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    if verbose:
        print("wrote %s (%.1f KB)" % (dest, dest.stat().st_size / 1024))
        for k, v in sorted(doc["counts"].items()):
            print("  %-24s %d" % (k, v))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

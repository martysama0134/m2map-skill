"""Mutation tests -- the gap that the preservation suite could not see.

The existing codec tests prove that shipped data reads and writes back
byte-identically. Every one of the six planned modes, however, is a *mutation*:
``improve`` edits, ``reskin`` swaps CRCs, ``merge`` remaps tile indices,
``generate`` writes new files. Nothing tested that path, and two independent
reviews found the same consequence: edits were silently discarded, because
``render()`` preferred the token captured at parse time over the field the
caller had just changed.

Every test here follows the same shape, which is the shape a preservation test
cannot have:

    parse -> change ONE thing -> render -> assert the change is in the bytes
                                        -> assert nothing else moved

The second assertion matters as much as the first. A codec that regenerates the
whole record from scratch would pass the first and destroy formatting fidelity.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "skills" / "m2map" / "scripts"))

from m2map.codec import areadata as ad  # noqa: E402

CRLF = "\r\n"

SRC = (
    "AreaDataFile" + CRLF + CRLF +
    "Start Object000" + CRLF +
    "    10892.386719 -18171.355469 17784.789062" + CRLF +
    "    26807040" + CRLF +
    "    0.000000#0.000000#120.000000" + CRLF +
    "    -35.000000" + CRLF +
    "End Object" + CRLF + CRLF +
    "Start Object001" + CRLF +
    "    20801.746094 -13522.107422 18009.205078" + CRLF +
    "    569394331" + CRLF +
    "    0.000000#15.000000#225.000000" + CRLF +
    "    0.000000" + CRLF +
    "End Object" + CRLF + CRLF +
    "ObjectCount 2" + CRLF
)

# The undocumented per-object scale form, only map in the corpus that uses it.
SRC_SCALED = (
    "AreaDataFile" + CRLF + CRLF +
    "Start Object000" + CRLF +
    "    100.000000 -200.000000 300.000000" + CRLF +
    "    142625613#1.000000#1.000000#1.000000" + CRLF +
    "    0.000000#0.000000#90.000000" + CRLF +
    "    0.000000" + CRLF +
    "End Object" + CRLF + CRLF +
    "ObjectCount 1" + CRLF
)


def parse(src: str) -> ad.AreaData:
    return ad.AreaData.parse(src.encode("ascii"))


def render(doc: ad.AreaData) -> str:
    out = doc.to_bytes()
    return out.decode("ascii") if isinstance(out, (bytes, bytearray)) else out


# --- baseline: preservation still holds -----------------------------------

def test_untouched_record_still_round_trips_byte_identically():
    """The freshness check must not cost the fidelity the tokens exist for."""
    assert render(parse(SRC)) == SRC


# --- the bug: edits must reach the bytes ----------------------------------

def test_editing_crc_changes_the_output():
    doc = parse(SRC)
    doc.records[0].crc = 88
    out = render(doc)
    assert "88" in out
    assert "26807040" not in out, "stale crc_token was emitted; the edit was lost"


def test_editing_roll_changes_the_output():
    doc = parse(SRC)
    doc.records[0].roll = 180.0
    out = render(doc)
    assert "180.000000" in out
    assert "120.000000" not in out, "stale rotation_token was emitted"


def test_editing_yaw_and_pitch_changes_the_output():
    doc = parse(SRC)
    r = doc.records[1]
    r.yaw, r.pitch = 45.0, 0.0
    out = render(doc)
    assert "45.000000#0.000000#225.000000" in out
    assert "0.000000#15.000000#225.000000" not in out


def test_editing_scale_changes_the_output():
    doc = parse(SRC_SCALED)
    doc.records[0].scale = (2.0, 2.0, 2.0)
    out = render(doc)
    assert "142625613#2.000000#2.000000#2.000000" in out
    assert "#1.000000#1.000000#1.000000" not in out


def test_clearing_scale_drops_the_suffix():
    doc = parse(SRC_SCALED)
    doc.records[0].scale = None
    out = render(doc)
    assert "142625613" in out
    assert "#1.000000" not in out


def test_engine_rotation_follows_the_edit():
    """An audit asking 'what heading will the player see' must not get the old one."""
    doc = parse(SRC)
    r = doc.records[0]
    assert r.engine_rotation == (0, 0, 120)
    r.roll = 200.0
    assert r.engine_rotation == (0, 0, 200)


# --- and must not disturb anything else -----------------------------------

def test_editing_one_record_leaves_the_other_byte_identical():
    doc = parse(SRC)
    doc.records[0].crc = 88
    out = render(doc)
    assert "20801.746094 -13522.107422 18009.205078" in out
    assert "569394331" in out
    assert "0.000000#15.000000#225.000000" in out, "untouched record was reformatted"


def test_editing_crc_leaves_rotation_formatting_untouched():
    doc = parse(SRC)
    doc.records[0].crc = 88
    assert "0.000000#0.000000#120.000000" in render(doc)


def test_editing_rotation_leaves_position_formatting_untouched():
    doc = parse(SRC)
    doc.records[0].roll = 7.0
    assert "10892.386719 -18171.355469 17784.789062" in render(doc)


@pytest.mark.parametrize("field,value", [
    ("x", 1.5), ("y", -2.5), ("z", 3.5), ("height_bias", -12.0),
])
def test_editing_plain_float_fields(field, value):
    doc = parse(SRC)
    setattr(doc.records[0], field, value)
    out = render(doc)
    assert ("%f" % value) in out


# --- constructing from scratch (the generate path) ------------------------

def test_record_built_from_scratch_renders_its_fields():
    """No tokens exist, so nothing can shadow the fields."""
    doc = ad.AreaData()
    doc.records.append(ad.ObjectRecord(x=100.0, y=-200.0, z=300.0,
                                       crc=12345, roll=90.0, height_bias=-5.0))
    doc.declared_count = 1
    out = render(doc)
    assert "12345" in out
    assert "90.000000" in out
    assert "ObjectCount 1" in out


def test_round_trip_of_a_generated_file_is_stable():
    doc = ad.AreaData()
    doc.records.append(ad.ObjectRecord(x=1.0, y=-2.0, z=3.0, crc=7, roll=15.0))
    doc.declared_count = 1
    once = render(doc)
    assert render(parse(once)) == once


# ---------------------------------------------------------------------------
# The same defect lived in every text container: render() replayed the parsed
# document unconditionally, so render_canonical() was dead code on any parsed
# file and no semantic edit could reach the bytes. These pin both halves of the
# contract -- untouched files stay byte-identical, edited ones actually change.
# ---------------------------------------------------------------------------

from m2map.codec import msenv as me      # noqa: E402
from m2map.codec import regen as rg      # noqa: E402
from m2map.codec import setting as st    # noqa: E402
from m2map.codec import textureset as tset  # noqa: E402
from m2map.config import paths as _paths  # noqa: E402

P = _paths()


def _need(p):
    if p is None or not pathlib.Path(p).exists():
        pytest.skip("not configured/present: %s" % p)
    return pathlib.Path(p)


def test_setting_untouched_is_byte_identical_and_not_dirty():
    f = _need(P.corpus and P.corpus / "metin2_map_a1" / "setting.txt")
    s = st.Setting.load(f)
    assert not s.dirty
    assert s.to_bytes() == f.read_bytes()


def test_setting_map_size_edit_reaches_the_bytes():
    f = _need(P.corpus and P.corpus / "metin2_map_a1" / "setting.txt")
    s = st.Setting.load(f)
    s.map_size = (8, 9)
    assert s.dirty
    out = s.to_bytes().decode("latin-1")
    assert any("MapSize" in ln and "8" in ln and "9" in ln for ln in out.splitlines())


def test_textureset_untouched_then_edited():
    f = _need(P.client_pack and P.texturesets / "metin2_a1.txt")
    t = tset.TextureSet.load(f)
    assert not t.dirty and t.to_bytes() == f.read_bytes()
    t.slots[1].u_scale = 99.0
    assert t.dirty and b"99.000000" in t.to_bytes()


def test_msenv_untouched_then_edited():
    f = _need(P.client_pack and P.environments / "a1.msenv")
    e = me.Environment.load(f)
    assert not e.dirty and e.to_bytes() == f.read_bytes()
    e.fog_far_distance = 12345.0
    assert e.dirty
    assert b"12345.000000" in e.to_bytes()


def test_monsterarrange_untouched_then_edited():
    f = _need(P.corpus and P.corpus / "metin2_map_a1" / "monsterarrange.txt")
    m = rg.MonsterArrange.parse(f.read_bytes())
    assert not m.dirty and m.to_bytes() == f.read_bytes()
    m.vnums.append(9999)
    assert m.dirty and b"9999" in m.to_bytes()


def test_areadata_untouched_corpus_file_stays_clean():
    """The dirty check must not misfire on real data with odd formatting."""
    root = _need(P.corpus)
    checked = 0
    for mapname in ("metin2_map_a1", "map_a2", "metin2_map_b1"):
        d = root / mapname
        if not d.is_dir():
            continue
        for sec in sorted(d.glob("[0-9]" * 6))[:4]:
            f = sec / "areadata.txt"
            if not f.exists():
                continue
            doc = ad.AreaData.parse(f.read_bytes())
            assert not doc.dirty, "%s read as dirty straight after parse" % f
            assert doc.to_bytes() == f.read_bytes()
            checked += 1
    assert checked >= 4


# ---------------------------------------------------------------------------
# Write-path losses: data the reader understands but the writer drops.
# ---------------------------------------------------------------------------

def test_msenv_preserves_fog_is_density():
    """Read into fog_is_density, never written back -- silently lost on rewrite.

    The canonical-output test could not see this: it compared the first
    canonical render against the second, and the key was already gone from both.
    """
    src = (
        "ScriptType         EnvrionmentData\r\n"
        "ScriptVersion      1.0000\r\n"
        "\r\n"
        "Group Fog\r\n"
        "{\r\n"
        "    Enable        1\r\n"
        "    IsDensity     1\r\n"
        "    NearDistance  5000.000000\r\n"
        "    FarDistance   20000.000000\r\n"
        "    Color         0.690196 0.741176 0.839216 1.000000\r\n"
        "}\r\n"
    )
    e = me.Environment.parse(src.encode("latin-1"))
    assert e.fog_is_density == 1
    out = e.render_canonical()
    assert "IsDensity" in out, "fog IsDensity dropped by the canonical writer"
    assert me.Environment.parse(out.encode("latin-1")).fog_is_density == 1


def test_msenv_omits_is_density_when_source_had_none():
    """Absent stays absent -- do not invent a key the file never carried."""
    src = ("ScriptType EnvrionmentData\r\n\r\nGroup Fog\r\n{\r\n"
           "    Enable        1\r\n    NearDistance  1.000000\r\n"
           "    FarDistance   2.000000\r\n"
           "    Color         0.0 0.0 0.0 1.0\r\n}\r\n")
    e = me.Environment.parse(src.encode("latin-1"))
    assert e.fog_is_density is None
    assert "IsDensity" not in e.render_canonical()


def test_dds_set_rgba_regenerates_the_whole_mip_chain():
    """Editing mip 0 must not leave levels 1..N holding the old picture.

    1328 shipped shadowmap.dds carry 9 levels; a stale chain renders the OLD
    bake at distance while looking correct in a viewer.
    """
    import numpy as np
    from m2map.codec import dds

    base = np.zeros((64, 64, 4), np.uint8)
    base[..., 3] = 255
    base[..., 0] = 200                                   # red
    d = dds.DDS.from_rgba(base, dds.X8R8G8B8, mipmaps=0)
    assert d.mip_count > 1

    new = np.zeros((64, 64, 4), np.uint8)
    new[..., 3] = 255
    new[..., 1] = 200                                    # green
    d.set_rgba(new)

    for lvl in range(d.mip_count):
        px = d.to_rgba(lvl)
        assert px[..., 1].mean() > 150, f"level {lvl} was not regenerated"
        assert px[..., 0].mean() < 50, f"level {lvl} still holds the old image"


def test_dds_set_rgba_can_opt_out_of_mip_regeneration():
    import numpy as np
    from m2map.codec import dds

    base = np.zeros((32, 32, 4), np.uint8)
    base[..., 3] = 255
    d = dds.DDS.from_rgba(base, dds.X8R8G8B8, mipmaps=0)
    new = np.full((32, 32, 4), 255, np.uint8)
    d.set_rgba(new, regenerate_mips=False)
    assert d.to_rgba(0)[..., 0].mean() > 200
    assert d.to_rgba(1)[..., 0].mean() < 50, "opt-out should leave level 1 alone"

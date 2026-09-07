"""Round-trip verification for the TEXT map-format codecs.

Run against the real corpora on this machine::

    py -m pytest tests/test_codec_text.py -v

Corpora (all READ-ONLY; nothing here writes outside a tmp dir):

* ``<CORPUS>``                       -- 142 official Ymir/GF maps
* ``<pack>/textureset/textureset``  -- 177 texture-set scripts
* ``<pack>/yw_etc/ymir work/environment`` -- 104 ``.msenv``
* ``<pack>/property/property``      -- 2113 ``.pr?`` + ``reserve``

Two levels of assertion, deliberately distinguished:

**Byte identity.**  Every codec keeps the parsed line layout, so
``parse(b).to_bytes() == b`` must hold for *every* file, including the corrupt
ones -- a tokenizer that loses a token, a gap or an EOL fails this.  For
``property.PropertyFile`` the round trip is stronger still: the file is fully
*rebuilt* from the parsed model (CRC line re-emitted verbatim, keys re-sorted
into std::map order), so byte identity there proves the whole container model.

**Canonical identity.**  ``render_canonical()`` rebuilds a file from the
semantic model alone, in the exact layout the WorldEditor writes.  It cannot
be byte-identical for every shipped file, because many were written by other
tools or damaged by in-place rewrites, so those tests assert byte identity on
the subset that already follows the canonical layout and *report the counts*.
Where a float cannot round-trip through ``%f`` we assert semantic equality
instead; see ``test_areadata_canonical_matches_writer``.
"""

from __future__ import annotations

import os
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "skills" / "m2map" / "scripts"))

from m2map.codec import areadata as ad                    # noqa: E402
from m2map.codec import msenv as me                       # noqa: E402
from m2map.codec import property as pr                    # noqa: E402
from m2map.codec import regen as rg                       # noqa: E402
from m2map.codec import setting as st                     # noqa: E402
from m2map.codec import textfile as tf                    # noqa: E402
from m2map.codec import textureset as ts                  # noqa: E402

# --------------------------------------------------------------------------
# corpora
# --------------------------------------------------------------------------

from m2map.config import paths as _paths                  # noqa: E402

# Resolved from m2map.paths.json (gitignored), overridable per-key by
# M2MAP_CORPUS / M2MAP_CLIENT_PACK. Never hardcode a host path here: this file
# is committed, and tools/scrub_paths.py would rewrite an absolute path to a
# "<CORPUS>" literal that no longer resolves -- silently turning the whole
# suite into skips.
_P = _paths()
MAPS = _P.corpus or pathlib.Path("corpus-not-configured")
PACK = _P.client_pack or pathlib.Path("client-pack-not-configured")
TEXTURESETS = PACK / "textureset" / "textureset"
ENVIRONMENTS = PACK / "yw_etc" / "ymir work" / "environment"
PROPERTIES = PACK / "property" / "property"

#: >= 12 maps spanning archetypes: outdoor field, city, desert, snow, dungeon,
#: instanced boss room, guild/PvP arena, event map, and the two known-corrupt
#: ones (``metin2_map_t1`` truncated areadata, ``metin2_map_treasure_hunt``
#: lowercase key).
SAMPLE_MAPS = [
    "metin2_map_a1",                  # outdoor field, Shinsoo empire start
    "map_a2",                         # outdoor field, canonical spec example
    "metin2_map_b1",                  # outdoor field, Chunjo
    "metin2_map_c1",                  # outdoor field, Jinno
    "metin2_map_n_desert_01",         # large desert
    "map_n_snowm_01",                 # snow field
    "metin2_map_deviltower1",         # dungeon w/ portal IDs in areadata
    "metin2_map_devilscatacomb",      # multi-level dungeon
    "metin2_map_spiderdungeon_02",    # dungeon w/ npc/boss/town.txt
    "metin2_guild_village",           # guild map, unquoted ParentMapName
    "metin2_map_duel",                # small arena
    "metin2_map_battlearena01",       # PvP arena
    "metin2_map_oxevent",             # event map
    "metin2_12zi_stage",              # Environment1..8 multi-environment
    "metin2_map_elemental_01",        # EnvironmentRange1/2
    "metin2_map_t1",                  # KNOWN CORRUPT: truncated areadata
    "metin2_map_treasure_hunt",       # lowercase key + areadata scale ext
    "metin2_map_monkeydungeon_02",    # instanced dungeon
    "metin2_guild_village_01",        # bare (unquoted) ParentMapName
]

_missing = [m for m in SAMPLE_MAPS if not (MAPS / m).is_dir()]
_have_maps = MAPS.is_dir() and not _missing
_have_ts = TEXTURESETS.is_dir()
_have_env = ENVIRONMENTS.is_dir()
_have_pr = PROPERTIES.is_dir()

needs_maps = pytest.mark.skipif(not _have_maps, reason="map corpus %s missing %s"
                                % (MAPS, _missing))
needs_ts = pytest.mark.skipif(not _have_ts, reason="no %s" % TEXTURESETS)
needs_env = pytest.mark.skipif(not _have_env, reason="no %s" % ENVIRONMENTS)
needs_pr = pytest.mark.skipif(not _have_pr, reason="no %s" % PROPERTIES)


def _sample_dirs():
    return [MAPS / m for m in SAMPLE_MAPS if (MAPS / m).is_dir()]


def _glob(pattern, root=None):
    root = root or MAPS
    return sorted(root.glob(pattern))


def _sample_files(name):
    out = []
    for d in _sample_dirs():
        f = d / name
        if f.is_file():
            out.append(f)
        for sub in sorted(p for p in d.iterdir() if p.is_dir()):
            g = sub / name
            if g.is_file():
                out.append(g)
    return out


def _rt(path, cls, **kw):
    """Parse ``path`` and assert the codec re-emits the source byte for byte."""
    raw = path.read_bytes()
    obj = cls.parse(raw, **kw) if kw else cls.parse(raw)
    assert obj.to_bytes() == raw, "byte round trip failed for %s" % path
    return obj


# ==========================================================================
# 1. the tokenizer itself
# ==========================================================================

class TestTokenizer:
    def test_split_lines_is_lossless_and_matches_bind(self):
        # CMemoryTextFileLoader::Bind: \r or \n breaks; a second break char
        # right after is swallowed into the same break.
        cases = {
            "a\r\nb":      [("a", "\r\n"), ("b", "")],
            "a\r\n\r\nb":  [("a", "\r\n"), ("", "\r\n"), ("b", "")],
            "a\n\nb":      [("a", "\n\n"), ("b", "")],      # blank line swallowed
            # property/reserve's terminator: \r\r is one break, then \n is
            # another -- it yields an EXTRA blank line, contradicting
            # mapformat/client-global-refs.md's "folds into a single break".
            "a\r\r\nb":    [("a", "\r\r"), ("", "\n"), ("b", "")],
            "a\rb":        [("a", "\r"), ("b", "")],
            "":            [("", "")],
        }
        for text, want in cases.items():
            got = tf.split_lines(text, dbcs=False)
            assert got == want, text
            assert "".join(c + e for c, e in got) == text

    def test_split_lines_dbcs_lead_byte_eats_the_newline(self):
        # FileLoader.cpp:166-170 -- a byte >= 0x80 consumes the next byte
        # unconditionally, so a trailing CP949 lead byte swallows the break.
        text = "a\xb0\nb"
        assert tf.split_lines(text, dbcs=True) == [("a\xb0\nb", "")]
        assert tf.split_lines(text, dbcs=False) == [("a\xb0", "\n"), ("b", "")]

    def test_tokenize_round_trips_and_keeps_quoted_spaces(self):
        line = '    "d:\\ymir work\\a b.dds"\t 5.000000  0 '
        indent, tokens, gaps, bad = tf.tokenize(line)
        assert not bad
        assert indent + "".join(t + g for t, g in zip(tokens, gaps)) == line
        assert [tf.unquote(t) for t in tokens] == [
            "d:\\ymir work\\a b.dds", "5.000000", "0"]

    def test_tokenize_quote_is_only_special_at_token_start(self):
        _, tokens, _, _ = tf.tokenize('a"b c"d')
        assert [tf.unquote(t) for t in tokens] == ['a"b', 'c"d']

    def test_tokenize_flags_unterminated_quote(self):
        _, _, _, bad = tf.tokenize('x "no close')
        assert bad is True

    def test_flat_blocks_flatten_across_lines(self):
        # line breaks inside a Start/End block are cosmetic (Util.cpp:88-96)
        one = b"Start Obj\r\n 1 2 3\r\n 4\r\nEnd Object\r\nCount 1\r\n"
        two = b"Start Obj\r\n 1\r\n 2 3 4\r\nEnd\r\nCount 1\r\n"
        assert tf.parse_flat(one).get("obj") == tf.parse_flat(two).get("obj")
        assert tf.parse_flat(one).get("obj") == ["1", "2", "3", "4"]

    def test_flat_duplicate_key_is_first_wins(self):
        # std::map::insert, Util.cpp:100/:105
        doc = tf.parse_flat(b"ObjectCount 0\r\nObjectCount 20\r\n")
        assert doc.get("objectcount") == ["0"]
        assert doc.get_all("objectcount") == [["0"], ["20"]]

    def test_group_form_nests_and_flattens_lists(self):
        doc = tf.parse_groups(
            b"Group A\r\n{\r\n  K 1 2\r\n  Group B\r\n  {\r\n    K 3\r\n  }\r\n"
            b"  List L\r\n  {\r\n    1 2\r\n    3 4\r\n  }\r\n}\r\n")
        a = doc.child("a")
        assert a.get("k") == ["1", "2"]
        assert a.child("b").get("k") == ["3"]
        assert a.get_list("l") == ["1", "2", "3", "4"]
        assert doc.balanced

    def test_atoi_atof_match_the_c_runtime(self):
        assert tf.atoi("120.000000") == 120
        assert tf.atoi("  -7abc") == -7
        assert tf.atoi("abc") == 0
        assert tf.atof("-35.5x") == -35.5
        assert tf.atof("") == 0.0


# ==========================================================================
# 2. setting.txt / mapproperty.txt / areaproperty.txt
# ==========================================================================

@needs_maps
class TestSettingFamily:
    def test_setting_round_trip_all_maps(self):
        files = _glob("*/setting.txt")
        assert len(files) >= 130, "expected the full corpus, got %d" % len(files)
        for f in files:
            _rt(f, st.Setting)

    def test_setting_semantics_on_sample(self):
        a1 = st.Setting.load(MAPS / "metin2_map_a1" / "setting.txt")
        assert a1.is_valid and a1.cell_scale == 200
        assert a1.map_size == (4, 5)
        assert a1.base_position == (409600, 896000)
        assert a1.texture_set == r"textureset\metin2_A1.txt"
        assert a1.environment == "A1.msenv"
        assert a1.world_size == (200 * 128 * 4, 200 * 128 * 5)
        assert a1.problems() == []

    def test_setting_canonical_layout_matches_most_of_the_corpus(self):
        files = _glob("*/setting.txt")
        exact = [f for f in files
                 if st.Setting.parse(f.read_bytes()).render_canonical()
                 == tf.decode(f.read_bytes())]
        # 110/139 follow SaveSetting's layout verbatim; the rest carry extra
        # keys (Environment1..8, EnvironmentRange1/2), a missing trailing
        # blank line, a double tab after Environment, or junk from a truncated
        # in-place rewrite.  All 139 still round-trip byte-exactly.
        assert len(exact) == 110, "%d/%d canonical" % (len(exact), len(files))

    def test_setting_undocumented_multi_environment_keys(self):
        s = st.Setting.load(MAPS / "metin2_12zi_stage" / "setting.txt")
        keys = [k for k, _ in s.extras]
        assert keys == ["environment%d" % i for i in range(1, 9)]
        e = st.Setting.load(MAPS / "metin2_map_elemental_01" / "setting.txt")
        assert [k for k, _ in e.extras] == [
            "environment1", "environmentrange1", "environmentrange2"]
        # EnvironmentRange is "x1 y1 x2 y2 <msenv>" -- 5 tokens.
        assert len(dict(e.extras)["environmentrange1"]) == 5

    def test_setting_corrupt_t1_still_round_trips(self):
        f = MAPS / "metin2_map_t1" / "setting.txt"
        s = _rt(f, st.Setting)
        # a truncated in-place rewrite left a headless "ungeon2.msenv" line
        assert ("ungeon2.msenv", []) in s.extras

    def test_mapproperty_round_trip_all_maps(self):
        files = _glob("*/mapproperty.txt")
        assert len(files) == 142
        for f in files:
            _rt(f, st.MapProperty)

    def test_mapproperty_semantics_and_unquoted_parent(self):
        p = st.MapProperty.load(MAPS / "map_a2" / "mapproperty.txt")
        assert p.is_valid and p.map_type == "Outdoor" and not p.is_indoor
        # quoted form (the shape the editor would write if it wrote the key)
        q = st.MapProperty.load(MAPS / "metin2_map_e1_01" / "mapproperty.txt")
        assert q.parent_map_name == "metin2_map_e1" and q.parent_quoted
        # and the bare tab-separated form some guild maps ship
        g = st.MapProperty.load(MAPS / "metin2_guild_village_01" / "mapproperty.txt")
        assert g.parent_map_name == "metin2_guild_village"
        assert g.parent_quoted is False

    def test_mapproperty_canonical_counts(self):
        files = _glob("*/mapproperty.txt")
        exact = [f for f in files
                 if tf.encode(st.MapProperty.parse(f.read_bytes()).render_canonical())
                 == f.read_bytes()]
        # 115/142.  The residue writes ParentMapName in a shape the editor
        # never produces (it never writes the key at all) or drops the
        # trailing blank line; all of them still round-trip byte-exactly.
        assert len(exact) == 115, "%d/%d canonical" % (len(exact), len(files))

    def test_areaproperty_round_trip_every_sector(self):
        files = _glob("*/*/areaproperty.txt")
        assert len(files) >= 1300, "only %d sectors found" % len(files)
        for f in files:
            _rt(f, st.AreaProperty)

    def test_areaproperty_canonical_is_byte_identical_for_every_sector(self):
        # this one really is 100%: SaveProperty's layout is the only one in
        # the wild, across all 1341 sectors.
        files = _glob("*/*/areaproperty.txt")
        bad = [f for f in files
               if tf.encode(st.AreaProperty.parse(f.read_bytes()).render_canonical())
               != f.read_bytes()]
        assert bad == [], "%d sectors deviate, e.g. %s" % (len(bad), bad[:3])


# ==========================================================================
# 3. areadata.txt / areaambiencedata.txt
# ==========================================================================

@needs_maps
class TestAreaData:
    def test_areadata_round_trip_sample_maps(self):
        files = _sample_files("areadata.txt")
        assert len(files) >= 100, "only %d sector files" % len(files)
        for f in files:
            _rt(f, ad.AreaData)

    def test_areadata_round_trip_whole_corpus(self):
        files = _glob("*/*/areadata.txt")
        assert len(files) >= 1300
        for f in files:
            _rt(f, ad.AreaData)

    def test_areaambiencedata_round_trip_whole_corpus(self):
        files = _glob("*/*/areaambiencedata.txt")
        assert len(files) >= 1300
        for f in files:
            _rt(f, ad.AreaAmbienceData)

    def test_areadata_canonical_matches_writer(self):
        """``render_canonical`` reproduces ``__SaveObjects`` byte for byte.

        Floats survive because every value in the corpus was written with
        ``%f`` (six decimals) and re-parsing then re-formatting a six-decimal
        decimal string through a double is exact at these magnitudes -- a scan
        of all 442 631 numeric tokens under <CORPUS> found six decimals or a
        bare integer, nothing else.  The rotation token is re-emitted verbatim
        rather than reformatted, because the engine reads it with ``atoi`` and
        we must not "fix" a legacy shape.
        """
        files = _glob("*/*/areadata.txt")
        exact = mismatch = 0
        bad = []
        for f in files:
            raw = f.read_bytes()
            obj = ad.AreaData.parse(raw)
            if tf.encode(obj.render_canonical()) == raw:
                exact += 1
            else:
                mismatch += 1
                bad.append(f)
        # Only metin2_map_t1's seven damaged sectors deviate: their
        # "ObjectCount 0" sits *inside* the file (see the corruption test
        # below), so blocks past it are unreachable and a canonical rewrite
        # legitimately drops them.
        assert all("metin2_map_t1" in str(f) for f in bad), bad[:5]
        assert mismatch == 7, "%d/%d canonical, deviating: %s" % (
            exact, len(files), [str(f) for f in bad])

    def test_areaambience_canonical_matches_writer(self):
        files = _glob("*/*/areaambiencedata.txt")
        bad = [f for f in files
               if tf.encode(ad.AreaAmbienceData.parse(f.read_bytes()).render_canonical())
               != f.read_bytes()]
        assert bad == [], "%d deviate, e.g. %s" % (len(bad), bad[:3])

    def test_areadata_fields_and_negated_y(self):
        a = ad.AreaData.load(MAPS / "metin2_map_a1" / "000000" / "areadata.txt")
        r = a.records[0]
        assert (round(r.x, 6), round(r.y, 6), round(r.z, 6)) == (
            20801.746094, -13522.107422, 18009.205078)
        assert r.crc == 569394331
        assert r.rotation == (0.0, 0.0, 180.0)
        assert r.height_bias == -40.0
        assert r.final_z == 18009.205078 - 40.0
        assert r.terrain_y == 13522.107422           # Y is stored negated
        assert all(rec.y <= 0 for rec in a.records)

    def test_every_record_in_the_corpus_has_non_positive_y(self):
        neg = tot = 0
        for f in _glob("*/*/areadata.txt"):
            for r in ad.AreaData.parse(f.read_bytes()).records:
                tot += 1
                neg += (r.y <= 0)
        assert tot > 40000
        assert neg == tot, "%d of %d records have positive Y" % (tot - neg, tot)

    def test_engine_rotation_reproduces_the_substr_defect(self):
        # Area.cpp:850 reads yaw as substr(0, s-1) -- one char short.
        r = ad.ObjectRecord.from_tokens(
            ["0", "0", "0", "1", "120.000000#0.000000#45.000000", "0"])
        assert r.rotation == (120.0, 0.0, 45.0)
        assert r.engine_rotation == (120, 0, 45)      # harmless for %f form
        legacy = ad.ObjectRecord.from_tokens(["0", "0", "0", "1", "90#0#0"])
        assert legacy.rotation == (90.0, 0.0, 0.0)
        assert legacy.engine_rotation == (9, 0, 0)    # bare ints break
        bare = ad.ObjectRecord.from_tokens(["0", "0", "0", "1", "45.000000"])
        assert bare.rotation == (0.0, 0.0, 45.0)      # no '#' -> roll only

    def test_undocumented_per_object_scale_on_the_crc_token(self):
        """``metin2_map_treasure_hunt`` writes index 3 as ``crc#sx#sy#sz``.

        Vanilla degrades gracefully -- ``atoi`` stops at the ``#`` so the CRC
        still resolves and the object renders unscaled -- but the suffix must
        survive a rewrite or the extension is silently deleted.
        """
        f = MAPS / "metin2_map_treasure_hunt" / "000002" / "areadata.txt"
        a = _rt(f, ad.AreaData)
        r = a.records[0]
        assert r.crc == 3579485406
        assert r.crc_token == "3579485406#0.350000#0.350000#0.350000"
        assert r.scale == (0.35, 0.35, 0.35)
        assert tf.encode(a.render_canonical()) == f.read_bytes()
        # every treasure_hunt sector uses it; nothing else in the corpus does
        scaled = sum(1 for g in _glob("*/*/areadata.txt")
                     for rec in ad.AreaData.parse(g.read_bytes()).records
                     if rec.scale is not None)
        assert scaled > 0
        maps_with = {g.parent.parent.name for g in _glob("*/*/areadata.txt")
                     if any(rec.scale is not None
                            for rec in ad.AreaData.parse(g.read_bytes()).records)}
        assert maps_with == {"metin2_map_treasure_hunt"}, maps_with
        # a record built from the model alone reproduces the shape
        fresh = ad.ObjectRecord(crc=7, scale=(2.0, 2.0, 2.0))
        assert "    7#2.000000#2.000000#2.000000\r\n" in fresh.render(0)

    def test_short_records_are_legal(self):
        for toks, want in [
            (["1", "-2", "3", "77"], (0.0, 0.0, 0.0, 0.0)),
            (["1", "-2", "3", "77", "0.0#0.0#90.0"], (0.0, 0.0, 90.0, 0.0)),
            (["1", "-2", "3", "77", "0.0#0.0#90.0", "-5.0"], (0.0, 0.0, 90.0, -5.0)),
        ]:
            r = ad.ObjectRecord.from_tokens(toks)
            assert (r.yaw, r.pitch, r.roll, r.height_bias) == want
            assert r.token_count == len(toks)
        with pytest.raises(ValueError):
            ad.ObjectRecord.from_tokens(["1", "2", "3"])

    def test_portal_ids_at_index_six_and_beyond(self):
        f = MAPS / "metin2_map_deviltower1" / "000000" / "areadata.txt"
        a = _rt(f, ad.AreaData)
        assert a.records[0].portals == [1]
        m = ad.AreaData.load(MAPS / "metin2_map_maze_dungeon1" / "000000"
                             / "areadata.txt") if (
            MAPS / "metin2_map_maze_dungeon1").is_dir() else None
        if m is not None:
            assert any(r.portals for r in m.records)

    def test_object_count_is_required(self):
        with pytest.raises(ValueError):
            ad.AreaData.parse(b"AreaDataFile\r\n\r\n", strict=True)
        with pytest.raises(ValueError):
            ad.AreaData.parse(b"ObjectCount 0\r\n", strict=True)
        loose = ad.AreaData.parse(b"AreaDataFile\r\n\r\n")
        assert "missing ObjectCount" in " ".join(loose.problems())

    def test_t1_corruption_is_detected_not_silently_accepted(self):
        """metin2_map_t1's areadata files carry two ObjectCount keys.

        A truncated in-place rewrite overwrote the first ``Start Object000``
        line with ``ObjectCount 0``.  Because ``LoadMultipleTextData`` inserts
        into a std::map, the FIRST value wins -- so the live client loads zero
        objects from these sectors even though 20 blocks follow.
        """
        f = MAPS / "metin2_map_t1" / "000000" / "areadata.txt"
        a = _rt(f, ad.AreaData)
        assert a.declared_count == 0
        assert a.records == []
        assert a.orphan_blocks                    # blocks the engine never reads
        assert any("never loaded" in p for p in a.problems())
        assert tf.parse_flat(f.read_bytes()).get_all("objectcount") == [["0"], ["20"]]

    def test_empty_file_canonical_shape(self):
        empty = ad.AreaData()
        assert empty.render_canonical() == "AreaDataFile\r\n\r\n\r\nObjectCount 0\r\n"
        amb = ad.AreaAmbienceData()
        assert amb.render_canonical() == \
            "AreaAmbienceDataFile\r\n\r\n\r\nObjectCount 0\r\n"

    def test_ambience_index4_is_range_not_rotation(self):
        f = MAPS / "metin2_map_a1" / "001002" / "areaambiencedata.txt"
        a = ad.AreaAmbienceData.load(f)
        assert len(a) == 1
        r = a.records[0]
        assert r.crc == 2293772605 and r.range == 9000
        assert abs(r.max_volume_area_pct - 0.6) < 1e-9
        with pytest.raises(ValueError):
            ad.AmbienceRecord.from_tokens(["0", "0", "0", "1"])


# ==========================================================================
# 4. textureset/*.txt  -- every file in the pack
# ==========================================================================

@needs_ts
class TestTextureSet:
    def test_round_trip_all_texturesets(self):
        files = [p for p in sorted(TEXTURESETS.rglob("*")) if p.is_file()]
        assert len(files) >= 99, "only %d texture sets" % len(files)
        for f in files:
            _rt(f, ts.TextureSet)

    def test_slot_zero_is_the_eraser_and_is_not_counted(self):
        t = ts.TextureSet.load(TEXTURESETS / "metin2_a1.txt")
        assert t.declared_count == 17
        assert len(t) == 17                    # usable textures
        assert len(t.slots) == 18              # +1 for the implicit eraser
        assert t.get(0) is None                # slot 0 = erased
        assert t.slots[1].filename == r"d:\ymir work\terrainmaps\b\field\field 01.dds"
        assert t.slots[1].u_scale == 5.0 and t.slots[1].v_scale == 5.0
        assert t.slots[17].filename.endswith("tile03.dds")

    def test_blocks_are_one_based(self):
        t = ts.TextureSet.parse(
            b'TextureSet\r\n\r\nTextureCount 1\r\nStart Texture001\r\n'
            b'    "a.dds"\r\n 1\r\n 2\r\n 3\r\n 4\r\n 1\r\n 5\r\n 6\r\nEnd Texture001\r\n')
        e = t.slots[1]
        assert (e.u_scale, e.v_scale, e.u_offset, e.v_offset) == (1, 2, 3, 4)
        assert (e.b_splat, e.begin, e.end) == (1, 5, 6)

    def test_canonical_matches_shipped_layout_for_wellformed_files(self):
        """Byte identity is only achievable for the writer generations we know.

        Two writer dialects exist (blank line after ``TextureCount`` or not),
        and many files were truncated in place, leaving trailing blank-line
        padding.  So: assert exact identity where one dialect reproduces the
        file, exact-modulo-trailing-blanks otherwise, and *count* the rest.
        """
        files = [p for p in sorted(TEXTURESETS.rglob("*")) if p.is_file()]
        exact, padded, other = [], [], []
        for f in files:
            raw = f.read_bytes()
            t = ts.TextureSet.parse(raw)
            if not t.has_header_key:
                continue                       # pack-build script, not a set
            forms = [tf.encode(t.render_canonical(b)) for b in (True, False)]
            if any(raw == x for x in forms):
                exact.append(f)
            elif any(raw.startswith(x) and not raw[len(x):].strip(b"\r\n")
                     for x in forms):
                padded.append(f)
            else:
                other.append(f)
        assert len(exact) == 57, len(exact)
        assert len(padded) == 49, len(padded)
        # The residue is genuinely unreproducible: a zero-padded count
        # ("TextureCount 08"), a missing final CRLF, or duplicate/gapped
        # blocks.  Every one of them still parses and still round-trips
        # byte-exactly through the layout-preserving path above.
        assert len(other) == 65, len(other)
        for f in other:
            assert ts.TextureSet.parse(f.read_bytes()).to_bytes() == f.read_bytes()

    def test_gaps_and_duplicate_blocks_are_surfaced(self):
        gap = ts.TextureSet.load(TEXTURESETS / "metin2_bayblacksand.txt")
        assert gap.declared_count == 11
        assert gap.slots[3] is None            # Texture003 block is missing
        assert any("empty slot" in p for p in gap.problems())

        head = ts.TextureSet.load(TEXTURESETS / "metin2_guild_village.txt")
        assert head.slots[1] is None           # file starts at Texture002

        dup = ts.TextureSet.load(TEXTURESETS / "metin2_map_naga1.txt")
        assert dup.ignored_blocks              # Texture012 appears twice
        assert any("never loaded" in p for p in dup.problems())

    def test_inline_comment_shifts_every_positional_field(self):
        # metin2_test_zon.txt has a Korean comment after the filename, so the
        # engine reads UScale from a non-numeric token -> 0.
        t = ts.TextureSet.load(TEXTURESETS / "metin2_test_zon.txt")
        assert t.slots[1].u_scale == 0.0
        assert t.slots[1].extra_tokens         # the 8-field slot overflowed
        assert any("junk token" in p for p in t.problems())

    def test_pack_build_scripts_are_not_texturesets(self):
        # metin2_siege_0*.txt are pack-build scripts that landed in the
        # textureset folder; they use the Group/List form and have no
        # TextureSet key, so CTextureSet::Load rejects them.
        t = ts.TextureSet.load(TEXTURESETS / "metin2_siege_01.txt")
        assert not t.has_header_key and not t.has_count_key
        assert len(t) == 0
        doc = tf.parse_groups((TEXTURESETS / "metin2_siege_01.txt").read_bytes())
        assert doc.get_str("foldername") == "pack_map"
        assert doc.root.get_list("compressextnamelist")
        with pytest.raises(ValueError):
            ts.TextureSet.load(TEXTURESETS / "metin2_siege_01.txt", strict=True)

    def test_cap_is_255_usable(self):
        assert ts.MAX_TERRAIN_TEXTURES == 256
        assert ts.MAX_USABLE_TEXTURES == 255
        big = ts.TextureSet(slots=[None] * (ts.MAX_USABLE_TEXTURES + 2))
        assert any("exceeds" in p for p in big.problems())


# ==========================================================================
# 5. *.msenv -- every environment in the pack
# ==========================================================================

@needs_env
class TestMsEnv:
    def test_round_trip_all_environments(self):
        files = sorted(ENVIRONMENTS.glob("*.msenv"))
        assert len(files) >= 100, "only %d msenv" % len(files)
        for f in files:
            _rt(f, me.Environment)

    def test_round_trip_map_local_environments(self):
        # maps may ship their own .msenv next to setting.txt
        files = sorted(MAPS.glob("*/*.msenv")) if MAPS.is_dir() else []
        files += sorted((PACK / "maps").glob("*/*.msenv"))
        assert len(files) >= 19, "only %d map-local msenv" % len(files)
        for f in files:
            _rt(f, me.Environment)

    def test_full_key_inventory_is_read(self):
        e = me.Environment.load(ENVIRONMENTS / "a1.msenv")
        assert e.script_type == "EnvrionmentData"        # the historical typo
        assert abs(e.script_version - 1.0) < 1e-6
        assert [round(v, 6) for v in e.direction] == [0.350156, 0.562609, -0.748907]
        assert e.background.enable == 1
        assert [round(v, 6) for v in e.background.diffuse] == [1.0, 0.972549, 0.972549, 1.0]
        assert [round(v, 6) for v in e.character.ambient] == [0.15, 0.15, 0.15, 1.0]
        assert [round(v, 6) for v in e.material_emissive] == [0.321569, 0.321569, 0.411765, 1.0]
        assert e.fog_enable == 1
        assert (e.fog_near_distance, e.fog_far_distance) == (5000.0, 20000.0)
        assert e.filter_enable == 0
        assert (e.filter_alpha_src, e.filter_alpha_dest) == (1, 2)
        sb = e.skybox
        assert sb.scale == [3500.0, 3500.0, 3500.0]
        assert (sb.gradient_level_upper, sb.gradient_level_lower) == (4, 1)
        assert sb.cloud_scale == [200000.0, 200000.0]
        assert sb.cloud_height == 30000.0
        assert sb.cloud_texture_file_name.endswith("clouds_zone01.tga")
        assert len(sb.cloud_color) == 8
        assert len(sb.gradient) == 5 and all(len(g) == 8 for g in sb.gradient)
        assert e.lensflare_enable in (0, 1)
        assert e.wind_enable is None            # vanilla files have no Wind group

    def test_skybox_faces_are_read_when_present(self):
        e = me.Environment.load(ENVIRONMENTS / "12zi_stage_01_02.msenv")
        assert e.skybox.has_faces
        assert e.skybox.faces[0].endswith("CapeDragonHead_f.dds")
        assert e.skybox.faces[5] == ""          # BottomFaceFileName ""

    def test_gradient_entry_count_must_equal_upper_plus_lower(self):
        # MapUtil.cpp:181-184: size%8==0 AND size/8 == upper+lower, else the
        # whole gradient is discarded.
        for f in sorted(ENVIRONMENTS.glob("*.msenv")):
            e = me.Environment.parse(f.read_bytes())
            sb = e.skybox
            if sb.has_gradient_list and sb.gradient_accepted:
                assert len(sb.gradient) == (sb.gradient_level_upper
                                            + sb.gradient_level_lower), f

    def test_canonical_write_preserves_the_typo(self):
        e = me.Environment.load(ENVIRONMENTS / "a1.msenv")
        out = e.render_canonical()
        assert out.startswith("ScriptType         EnvrionmentData\r\n")
        assert "Group DirectionalLight" in out
        assert "List CloudColor" in out and "List Gradient" in out
        # and it re-parses to the same semantics
        again = me.Environment.parse(tf.encode(out))
        assert again.skybox.gradient == e.skybox.gradient
        assert again.fog_color == e.fog_color
        assert again.script_type == "EnvrionmentData"

    def test_canonical_round_trip_is_semantically_stable_for_every_file(self):
        """Byte identity against the shipped ``.msenv`` is impossible.

        The files were hand-edited and written by several tool generations, so
        their whitespace, key order and optional blocks vary.  What must hold
        is that re-parsing our canonical output yields the same semantics -- a
        fixed point after one pass.
        """
        checked = 0
        for f in sorted(ENVIRONMENTS.glob("*.msenv")):
            e = me.Environment.parse(f.read_bytes())
            once = e.render_canonical()
            twice = me.Environment.parse(tf.encode(once)).render_canonical()
            assert once == twice, f
            checked += 1
        assert checked >= 100

    def test_wind_group_is_the_remix_extension(self):
        src = (b"ScriptType EnvrionmentData\r\nGroup Wind\r\n{\r\n"
               b"    Enable 1\r\n    Strength 0.5\r\n    Random 0.25\r\n}\r\n")
        e = me.Environment.parse(src)
        assert e.wind_enable == 1 and e.wind_strength == 0.5
        assert e.to_bytes() == src
        assert "Group Wind" in e.render_canonical()


# ==========================================================================
# 6. property/**/*.pr? -- all 2113 files
# ==========================================================================

def _property_files():
    return [p for p in sorted(PROPERTIES.rglob("*"))
            if p.is_file() and p.suffix.lower().startswith(".pr")]


@needs_pr
class TestProperty:
    def test_round_trip_all_property_files(self):
        files = _property_files()
        assert len(files) == 2113, "expected 2113 property files, got %d" % len(files)
        for f in files:
            raw = f.read_bytes()
            p = pr.PropertyFile.parse(raw, path=str(f))
            # this rebuilds the WHOLE container from the model: magic, CRLF,
            # verbatim CRC line, sorted key\t\t"value" lines.
            assert p.to_bytes() == raw, f

    def test_container_shape(self):
        f = PROPERTIES / "12temple" / "12t_12statue_01.prb"
        raw = f.read_bytes()
        assert raw[:4] == b"YPRT"
        assert raw[4:6] == b"\r\n"
        p = pr.PropertyFile.parse(raw, path=str(f))
        assert p.crc_text == "4138947403" and p.crc == 4138947403
        assert p.property_type == "Building"
        assert p.name == "12T_12statue_01"
        assert p.model_file == "d:/ymir work/zone/12temple/12t_12statue_01.gr2"
        assert p.collision_file == "d:/ymir work/zone/12temple/12t_12statue_01.mdatr"
        assert p.get("shadowflag") == ["1"]
        assert p.problems() == []

    def test_magic_and_crlf_are_validated(self):
        with pytest.raises(ValueError):
            pr.PropertyFile.parse(b"XPRT\r\n1\r\n")
        with pytest.raises(ValueError):
            pr.PropertyFile.parse(b"YPRT\n1\n")

    def test_crc_is_read_verbatim_never_recomputed(self):
        f = next(p for p in _property_files() if p.suffix.lower() == ".prt")
        raw = f.read_bytes()
        p = pr.PropertyFile.parse(raw, path=str(f))
        original = p.crc_text
        p.set("propertyname", "renamed")
        p.set("treefile", "d:/somewhere/else.spt")
        assert p.crc_text == original          # model path change must NOT move it
        assert p.to_bytes().split(b"\r\n")[1] == original.encode()

    def test_all_five_types_present_and_dispatched_by_value_not_extension(self):
        seen = {}
        for f in _property_files():
            p = pr.PropertyFile.parse(f.read_bytes(), path=str(f))
            seen.setdefault(p.property_type, []).append(f)
        assert set(seen) == set(pr.PROPERTY_TYPES)
        counts = {k: len(v) for k, v in seen.items()}
        assert counts == {"Building": 1734, "DungeonBlock": 195, "Effect": 97,
                          "Tree": 85, "Ambience": 2}, counts
        # extension always agrees with PropertyType in this pack, but the
        # codec keys off the value regardless
        for ptype, files in seen.items():
            for f in files:
                assert f.suffix.lower() == pr.TYPE_EXTENSION[ptype]

    def test_ambience_multi_value_key(self):
        amb = [f for f in _property_files() if f.suffix.lower() == ".pra"]
        assert len(amb) == 2
        p = pr.PropertyFile.parse((PROPERTIES / "b" / "ambience" / "warp.pra")
                                  .read_bytes())
        assert p.property_type == "Ambience"
        assert p.get("playtype") == ["LOOP"]
        assert p.sounds == ["sound/ambience/warp_test.mp3"]
        assert p.model_file is None            # no model path -> timestamp CRC seed

    def test_undocumented_isattributedata_key(self):
        """152 shipped ``.prb`` files carry ``isattributedata``.

        Nothing in the WorldEditorRemix source reads it -- it is metadata from
        a newer content pipeline.  It must survive a rewrite untouched or the
        file stops being byte-identical.
        """
        holders = []
        values = set()
        for f in _property_files():
            p = pr.PropertyFile.parse(f.read_bytes(), path=str(f))
            v = p.get("isattributedata")
            if v is not None:
                holders.append(f)
                values.add((p.property_type, f.suffix.lower(), v[0]))
        assert len(holders) == 152, len(holders)
        assert values == {("Building", ".prb", "0")}
        assert "isattributedata" in pr.UNDOCUMENTED_KEYS
        # and it does not trip the schema checker
        p = pr.PropertyFile.parse(holders[0].read_bytes(), path=str(holders[0]))
        assert p.problems() == []

    def test_keys_are_lowercase_and_std_map_ordered(self):
        for f in _property_files():
            p = pr.PropertyFile.parse(f.read_bytes(), path=str(f))
            assert p.keys == [k.lower() for k in p.keys]
            assert p.keys == sorted(p.keys), f

    def test_registry_scan_and_the_one_duplicate_crc(self):
        crcs = {}
        for f in _property_files():
            p = pr.PropertyFile.parse(f.read_bytes(), path=str(f))
            crcs.setdefault(p.crc, []).append(f.name)
        dups = {c: n for c, n in crcs.items() if len(n) > 1}
        # exactly one collision in the shipped pack; last registered wins.
        assert dups == {1740984444: ["mtthunder_thorn01.prb",
                                     "obj_mtthund_thorn01.prb"]}, dups
        assert len(crcs) == 2112

    def test_reserve_file_tolerates_the_double_cr(self):
        f = PROPERTIES / "reserve"
        raw = f.read_bytes()
        r = pr.PropertyReserve.parse(raw)
        assert r.eol == "\r\r\n"
        assert len(r) == 16
        assert r.to_bytes() == raw
        assert 3752064404 in r


# ==========================================================================
# 7. regen.txt / npc.txt / boss.txt / stone.txt, index, Town.txt, dungeon.txt
# ==========================================================================

@needs_maps
class TestRegen:
    def test_round_trip_every_spawn_file_in_the_corpus(self):
        files = []
        for name in ("regen.txt", "npc.txt", "boss.txt", "stone.txt"):
            files += _glob("*/%s" % name)
        assert len(files) >= 28, "only %d spawn files" % len(files)
        for f in files:
            _rt(f, rg.RegenFile)

    def test_eleven_columns_parse(self):
        f = MAPS / "metin2_map_spiderdungeon_02" / "boss.txt"
        r = rg.RegenFile.load(f)
        assert len(r) == 1
        row = r.rows[0]
        assert row.type == "g" and row.kind == "GROUP" and not row.is_aggressive
        assert (row.cx, row.cy, row.sx, row.sy) == (387, 867, 1, 1)
        assert (row.z, row.dir) == (0, 0)
        assert row.time == "7200s" and row.time_seconds == 7200
        assert row.percent == 100 and row.count == 1 and row.vnum == 2019

    def test_world_rect_math(self):
        row = rg.RegenRow(type="g", cx=783, cy=205, sx=491, sy=113,
                          time="1m", count=174, vnum=62)
        assert row.world_rect(204800, 486400) == (234000, 495600, 332200, 518200)
        assert row.time_seconds == 60

    def test_sx_sy_are_half_extents_and_zero_means_point_spawn(self):
        row = rg.RegenRow(type="m", cx=109, cy=1427, sx=0, sy=0,
                          time="1m", count=1, vnum=10016)
        assert row.is_point_spawn
        assert row.world_rect(0, 0) == (10900, 142700, 10900, 142700)
        assert row.problems() == []
        grp = rg.RegenRow(type="g", cx=1, cy=1, sx=0, sy=0, time="1m", vnum=5)
        assert any("point-spawn path" in p for p in grp.problems())

    def test_time_without_a_suffix_is_discarded(self):
        assert rg.parse_duration("1h30m") == 5400
        assert rg.parse_duration("60s") == 60
        assert rg.parse_duration("1m") == 60
        assert rg.parse_duration("60") == 0        # bare digits are dropped
        assert rg.format_duration(5400) == "1h30m" or rg.format_duration(5400) == "90m"
        row = rg.RegenRow(type="m", time="60", vnum=1)
        assert any("never spawns" in p for p in row.problems())

    def test_character_level_tokenizer_ignores_line_structure(self):
        # get_word reads words off the FILE*, so a record may straddle lines.
        one = b"m\t1\t2\t3\t4\t0\t0\t1m\t100\t5\t101\r\n"
        split = b"m 1 2\r\n3 4 0\r\n0 1m 100\r\n5 101\r\n"
        a, b = rg.RegenFile.parse(one), rg.RegenFile.parse(split)
        assert len(a) == len(b) == 1
        for fld in ("type", "cx", "cy", "sx", "sy", "z", "dir", "time",
                    "percent", "count", "vnum"):
            assert getattr(a.rows[0], fld) == getattr(b.rows[0], fld)

    def test_comments_and_quoted_tokens(self):
        src = (b"//type\tcx\tcy\tsx\tsy\tz\tdir\ttime\tpercent\tcount\tvnum\r\n"
               b"//------\r\n"
               b'm\t1\t2\t3\t4\t0\t0\t"1m"\t100\t5\t101\t// trailing note\r\n')
        f = rg.RegenFile.parse(src)
        assert len(f) == 1 and f.rows[0].vnum == 101 and f.rows[0].time == "1m"
        assert f.to_bytes() == src

    def test_exception_rows_stop_after_column_five(self):
        src = b"e\t10\t20\t5\t5\t0\r\nm\t1\t2\t3\t4\t0\t0\t1m\t100\t1\t99\r\n"
        f = rg.RegenFile.parse(src)
        assert len(f) == 2
        assert f.rows[0].is_exception and f.rows[0].kind == "EXCEPTION"
        assert f.rows[1].vnum == 99            # the short row did not desync us
        # exception rects get the x100 but not the base offset
        assert f.rows[0].world_rect(100000, 100000) == (500, 1500, 1500, 2500)
        assert f.rows[0].render().count("\t") == 5

    def test_ga_is_aggressive_but_ma_and_ra_are_not(self):
        assert rg.RegenRow(type="ga").is_aggressive
        assert not rg.RegenRow(type="ma").is_aggressive
        assert not rg.RegenRow(type="ra").is_aggressive
        assert rg.RegenRow(type="ma").kind == "MOB"       # degrades to plain m
        assert rg.RegenRow(type="ra").kind == "GROUP_GROUP"

    def test_unknown_type_is_flagged_not_silently_parsed(self):
        f = rg.RegenFile.parse(b"x 1 2 3 4 0 0 1m 100 1 1\r\n")
        assert f.rows[0].kind == "INVALID"
        assert any("exit(1)" in p for p in f.problems())

    def test_corpus_rows_are_all_eleven_column_and_sane(self):
        total = 0
        kinds = set()
        for name in ("regen.txt", "npc.txt", "boss.txt", "stone.txt"):
            for f in _glob("*/%s" % name):
                rf = rg.RegenFile.parse(f.read_bytes())
                assert not rf.truncated, f
                for row in rf.rows:
                    total += 1
                    kinds.add(row.kind)
                    assert row.kind != "INVALID", (f, row.line)
                    assert row.time_seconds > 0, (f, row.line, row.time)
        assert total >= 1000, total
        assert kinds <= {"MOB", "GROUP", "GROUP_GROUP", "ANYWHERE"}

    def test_town_file(self):
        f = MAPS / "metin2_map_spiderdungeon_02" / "town.txt"
        t = _rt(f, rg.TownFile)
        assert (t.x, t.y) == (384, 273)
        assert t.empire == [(384, 273), (384, 273), (384, 273)]
        assert t.world_spawn(204800, 486400) == (204800 + 38400, 486400 + 27300)
        # fewer than 8 numbers -> no per-empire spawns
        assert rg.TownFile.parse(b"10 20\r\n").empire is None

    def test_map_index(self):
        src = b"//comment\r\n#another\r\n1\tmetin2_map_a1\r\n2\tmap_a2\r\n"
        i = rg.MapIndex.parse(src)
        assert i.entries == [(1, "metin2_map_a1"), (2, "map_a2")]
        assert i.to_bytes() == src
        assert i.problems() == []
        # Build() does *strrchr(buf,'\n')=0 -> NULL deref without a final newline
        assert any("NULL" in p for p in rg.MapIndex.parse(b"1 a").problems())

    def test_dungeon_file_rect_conversion(self):
        src = b"# comment\r\nboss_room\t100\t200\t10\t20\t3\r\n"
        d = rg.DungeonFile.parse(src)
        assert d.to_bytes() == src
        a = d.areas[0]
        assert (a.name, a.x, a.y, a.sx, a.sy, a.dir) == ("boss_room", 100, 200, 10, 20, 3)
        # LoadDungeon: x-=sx; y-=sy; sx=x+2*sx; sy=y+2*sy -- no x100 scaling
        assert a.rect() == (90, 180, 110, 220)

    def test_monsterarrange_is_derived_from_regen(self):
        f = rg.RegenFile.parse(b"m 1 2 3 4 0 0 1m 100 1 101\r\n"
                               b"m 1 2 3 4 0 0 1m 100 1 101\r\n"
                               b"g 1 2 3 4 0 0 1m 100 1 202\r\n")
        ma = rg.MonsterArrange.from_regen(f)
        assert ma.vnums == [101, 202]
        assert ma.render_canonical() == "101\r\n202\r\n"
        for g in _glob("*/monsterarrange.txt"):
            _rt(g, rg.MonsterArrange)


# ==========================================================================
# 8. cross-format integration
# ==========================================================================

@needs_maps
@needs_pr
def test_areadata_crcs_resolve_against_the_property_pack():
    """Every areadata CRC in the sample must exist in the property DB.

    An unregistered CRC is silently dropped at load (Area.cpp:880-886), so this
    is the check that separates "map looks fine" from "half the objects are
    invisible".
    """
    registry = {}
    for f in _property_files():
        p = pr.PropertyFile.parse(f.read_bytes(), path=str(f))
        registry[p.crc] = p
    total = resolved = 0
    unknown = set()
    for g in _glob("*/*/areadata.txt"):
        for r in ad.AreaData.parse(g.read_bytes()).records:
            total += 1
            if r.crc in registry:
                resolved += 1
            else:
                unknown.add(r.crc)
    assert total > 40000, total
    # Measured: 48774/48774 across all 142 maps -- every CRC the corpus places
    # exists in this client's property pack.  A miss would mean the object is
    # silently dropped at load, so 100% is the right bar, not a ratio.
    assert unknown == set(), ("%d of %d areadata CRCs do not resolve (%d "
                              "distinct)" % (total - resolved, total, len(unknown)))


@needs_maps
@needs_ts
def test_setting_textureset_references_resolve():
    missing = []
    for d in _sample_dirs():
        f = d / "setting.txt"
        if not f.is_file():
            continue
        s = st.Setting.parse(f.read_bytes())
        name = pathlib.PurePath(s.texture_set_path.replace("\\", "/")).name
        if not (TEXTURESETS / name).is_file():
            missing.append((d.name, name))
    assert not missing, missing

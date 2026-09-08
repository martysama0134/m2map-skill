"""Round-trip + semantics tests for the binary map-layer codecs.

The contract these tests enforce: for every binary layer of every sampled map,
``write(read(f))`` must be **byte-identical** to the file on disk.  A codec that
cannot reproduce shipped data is not a codec.

Corpus:  ``<CORPUS>`` (142 official Ymir/GF maps), override with ``M2MAP_CORPUS``.
``server_attr`` does not ship inside that corpus; the six real ones live in map
folders on ``D:/`` (override the root with ``M2MAP_SERVER_ATTR_ROOT``).

Run everything, including the sweep over all 142 maps::

    M2MAP_FULL_CORPUS=1 python -m pytest tests/test_codec_binary.py -v
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import numpy as np
import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "m2map" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from m2map.codec import (attr, dds, height, lzo1x, minimap, server_attr,  # noqa: E402
                         shadow, tile, water)

from m2map.config import paths as _paths  # noqa: E402

# Resolved from m2map.paths.json (gitignored), overridable per-key by
# M2MAP_CORPUS. Never hardcode a host path here: this file is committed, and
# tools/scrub_paths.py would rewrite an absolute path to a "<CORPUS>" literal
# that no longer resolves -- silently turning the whole suite into skips.
CORPUS = _paths().corpus or Path("corpus-not-configured")
SERVER_ATTR_ROOT = Path(os.environ.get("M2MAP_SERVER_ATTR_ROOT", "D:/"))
SECTOR_RE = re.compile(r"^\d{6}$")

#: 16 maps spanning the archetypes present in the corpus.
SAMPLE_MAPS = [
    "metin2_map_a1",                    # kingdom field (Shinsoo)
    "map_a2",                           # large field, 6x6 sectrees
    "metin2_map_b1",                    # kingdom field (Chunjo)
    "metin2_map_c1",                    # old-beta layout: 5 files per sectree
    "metin2_map_n_desert_01",           # desert field, dry sectors (N=0 water)
    "metin2_map_n_flame_01",            # flame field
    "metin2_map_n_snow_dungeon_01",     # instanced dungeon
    "metin2_map_deviltower1",           # tower dungeon
    "metin2_map_milgyo",                # temple / town
    "metin2_map_trent",                 # forest
    "metin2_map_guild_battle",          # DXT5 shadowmap.dds variant
    "metin2_map_capedragonhead",        # 24bpp mipped shadowmap.dds variant
    "gm_guild_build",                   # GM sandbox, malformed 66,567-byte tile.raw
    "metin2_map_pvp_arena",             # PvP arena (single sectree)
    "metin2_map_miniboss_01",           # has a nested duplicate sector folder
    "metin2_map_sungzi_snow",           # snow field
]

#: name -> reader.  Every binary layer a sectree can carry.
LAYERS = {
    "height.raw": height.HeightMap.from_bytes,
    "tile.raw": tile.TileMap.from_bytes,
    "attr.atr": attr.AttrMap.from_bytes,
    "water.wtr": water.WaterMap.from_bytes,
    "shadowmap.raw": shadow.ShadowMap.from_bytes,
    "shadowmap.dds": dds.DDS.from_bytes,
    "minimap.dds": minimap.MiniMap.from_bytes,
}
#: directional minimap tiles a few maps carry alongside minimap.dds
EXTRA_DDS = tuple(n for n in minimap.VARIANT_NAMES if n != "minimap.dds")

STATS = {"files": 0, "sectors": 0, "maps": 0, "bytes": 0}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _require_corpus():
    if not CORPUS.is_dir():
        pytest.skip("map corpus not available at %s" % CORPUS)


def sector_dirs(map_dir):
    return sorted(p for p in map_dir.iterdir() if p.is_dir() and SECTOR_RE.match(p.name))


def roundtrip_file(path):
    """Read `path` with its codec and return ``(original, rewritten)`` bytes."""
    blob = path.read_bytes()
    name = path.name.lower()
    reader = LAYERS.get(name)
    if reader is None and name.endswith(".dds"):
        reader = dds.DDS.from_bytes
    if reader is None:
        raise KeyError(name)
    return blob, reader(blob).to_bytes()


def roundtrip_map(map_dir):
    """Round-trip every binary layer of every sectree; returns per-file results."""
    results = []
    for sec in sector_dirs(map_dir):
        for name in list(LAYERS) + list(EXTRA_DDS):
            f = sec / name
            if not f.exists():
                continue
            blob, again = roundtrip_file(f)
            results.append((f, blob == again, len(blob)))
    return results


# ---------------------------------------------------------------------------
# byte-identical round-trip over the sampled maps
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("map_name", SAMPLE_MAPS)
def test_sector_layers_roundtrip(map_name):
    _require_corpus()
    map_dir = CORPUS / map_name
    if not map_dir.is_dir():
        pytest.skip("%s not in corpus" % map_name)
    results = roundtrip_map(map_dir)
    assert results, "no binary layers found in %s" % map_dir
    bad = [str(p) for p, ok, _ in results if not ok]
    assert not bad, "not byte-identical after write: %s" % bad[:5]
    STATS["maps"] += 1
    STATS["sectors"] += len(sector_dirs(map_dir))
    STATS["files"] += len(results)
    STATS["bytes"] += sum(n for _, _, n in results)


def test_sample_covers_every_layer_kind():
    """The sample must actually exercise all seven per-sectree binary layers."""
    _require_corpus()
    seen = set()
    for map_name in SAMPLE_MAPS:
        map_dir = CORPUS / map_name
        if not map_dir.is_dir():
            continue
        for sec in sector_dirs(map_dir):
            seen.update(n for n in LAYERS if (sec / n).exists())
    assert seen == set(LAYERS), "sample misses %s" % (set(LAYERS) - seen)


def test_dds_encoding_variants_are_covered():
    """DXT1 with and without mips, DXT5 and 24bpp all appear in the sample."""
    _require_corpus()
    seen = set()
    for map_name in SAMPLE_MAPS:
        map_dir = CORPUS / map_name
        if not map_dir.is_dir():
            continue
        for sec in sector_dirs(map_dir):
            for name in ("minimap.dds", "shadowmap.dds"):
                f = sec / name
                if f.exists():
                    d = dds.DDS.from_bytes(f.read_bytes())
                    seen.add((d.format_name, d.mip_count > 1))
    assert ("DXT1", False) in seen
    assert ("DXT1", True) in seen
    assert ("DXT5", True) in seen
    assert ("R8G8B8", True) in seen


@pytest.mark.skipif(os.environ.get("M2MAP_FULL_CORPUS") != "1",
                    reason="set M2MAP_FULL_CORPUS=1 for the 142-map sweep")
def test_full_corpus_roundtrip():
    _require_corpus()
    files = ok = 0
    bad = []
    for map_dir in sorted(p for p in CORPUS.iterdir() if p.is_dir()):
        for f, good, _ in roundtrip_map(map_dir):
            files += 1
            ok += bool(good)
            if not good:
                bad.append(str(f))
    print("\nfull corpus: %d/%d files byte-identical" % (ok, files))
    assert not bad, bad[:10]


# ---------------------------------------------------------------------------
# writers actually hit the disk
# ---------------------------------------------------------------------------
def test_writers_produce_identical_files(tmp_path):
    _require_corpus()
    checked = 0
    for map_name in SAMPLE_MAPS[:6]:
        map_dir = CORPUS / map_name
        if not map_dir.is_dir():
            continue
        secs = sector_dirs(map_dir)
        if not secs:
            continue
        sec = secs[0]
        pairs = [
            ("height.raw", height.read_height, height.write_height),
            ("tile.raw", tile.read_tile, tile.write_tile),
            ("attr.atr", attr.read_attr, attr.write_attr),
            ("water.wtr", water.read_water, water.write_water),
            ("shadowmap.raw", shadow.read_shadow_raw, shadow.write_shadow_raw),
            ("shadowmap.dds", shadow.read_shadow_dds, shadow.write_shadow_dds),
            ("minimap.dds", minimap.read_minimap, minimap.write_minimap),
        ]
        for name, rd, wr in pairs:
            src = sec / name
            if not src.exists():
                continue
            dst = tmp_path / ("%s_%s_%s" % (map_name, sec.name, name))
            wr(str(dst), rd(str(src)))
            assert dst.read_bytes() == src.read_bytes(), "%s != %s" % (dst, src)
            checked += 1
    assert checked >= 20


# ---------------------------------------------------------------------------
# height.raw
# ---------------------------------------------------------------------------
def test_height_padding_and_scale():
    _require_corpus()
    f = CORPUS / "map_a2" / "000000" / "height.raw"
    if not f.exists():
        pytest.skip("map_a2 missing")
    hm = height.read_height(str(f))
    assert hm.raw.shape == (131, 131)
    assert hm.vertices.shape == (129, 129)
    assert len(f.read_bytes()) == height.FILE_SIZE == 34322
    # spec: first sample 0xAE4B = 44619 -> worldZ 22309.5
    assert int(hm.raw[0, 0]) == 44619
    assert hm.get(-1, -1) == 44619
    assert hm.world_z()[0, 0] == hm.get(0, 0) * 0.5
    # skirt indexing: vertex (sx, sy) == raw[sy+1, sx+1]
    assert hm.get(7, 3) == int(hm.raw[4, 8])


def test_height_slope_and_blank():
    flat = height.new_blank()
    assert int(flat.raw[0, 0]) == height.BLANK_RAW == 0x7FFF
    assert np.allclose(flat.slope_degrees(), 0.0)
    ramp = height.new_blank(0)
    # 1 raw unit per cell = 0.5 cm rise over 200 cm run
    ramp.raw[:, :] = (np.arange(131) * 1).astype("<u2")[None, :]
    expected = np.degrees(np.arctan(0.5 / 200.0))
    assert np.allclose(ramp.slope_degrees(), expected)
    assert height.HeightMap.from_bytes(flat.to_bytes()) == flat


# ---------------------------------------------------------------------------
# tile.raw
# ---------------------------------------------------------------------------
def test_tile_window_and_splat():
    _require_corpus()
    f = CORPUS / "metin2_map_a1" / "000000" / "tile.raw"
    if not f.exists():
        pytest.skip("metin2_map_a1 missing")
    tm = tile.read_tile(str(f))
    assert tm.raw.shape == (258, 258)
    assert tm.tiles.shape == (256, 256)
    assert tm.get(-1, -1) == int(tm.raw[0, 0])
    assert tile.ERASER == 0 and 0 not in tm.used_indices()

    grid = np.zeros((258, 258), np.uint8)
    grid[10, 10] = 3
    grid[10, 11] = 7          # higher index, neighbour of the 3 -> bleeds
    grid[10, 20] = 7          # higher index, far away -> stays clear
    tm2 = tile.TileMap(grid)
    a3 = tm2.splat_alpha(3)
    assert a3[10, 10] == 255 and a3[10, 11] == 255 and a3[10, 20] == 0
    a7 = tm2.splat_alpha(7)
    assert a7[10, 11] == 255 and a7[10, 10] == 0      # lower index never bleeds up
    with pytest.raises(ValueError):
        tm2.splat_alpha(tile.ERASER)


def test_tile_malformed_trailing_bytes_still_roundtrip():
    """<CORPUS>/gm_guild_build/000000/tile.raw is 3 bytes too long (66,567).

    The engine memcpys the first 66,564 bytes and ignores the rest, so the codec
    keeps the tail rather than rejecting or silently dropping it.
    """
    _require_corpus()
    f = CORPUS / "gm_guild_build" / "000000" / "tile.raw"
    if not f.exists():
        pytest.skip("gm_guild_build missing")
    blob = f.read_bytes()
    assert len(blob) == tile.FILE_SIZE + 3
    tm = tile.TileMap.from_bytes(blob)
    assert tm.trailing == b"\x02\x02\x02"
    assert tm.to_bytes() == blob
    with pytest.raises(ValueError):
        tile.TileMap.from_bytes(blob[:100])


# ---------------------------------------------------------------------------
# attr.atr
# ---------------------------------------------------------------------------
def test_attr_header_and_flags():
    _require_corpus()
    f = CORPUS / "map_a2" / "000000" / "attr.atr"
    if not f.exists():
        pytest.skip("map_a2 missing")
    blob = f.read_bytes()
    assert len(blob) == attr.FILE_SIZE == 65542
    assert blob[:6] == b"\x4a\x0a\x00\x01\x00\x01"      # magic 2634, 256, 256
    am = attr.read_attr(str(f))
    assert am.cells.shape == (256, 256)
    assert am.to_bytes() == blob
    with pytest.raises(ValueError):
        attr.AttrMap.from_bytes(b"\x00\x00" + blob[2:])

    assert (attr.ATTR_BLOCK, attr.ATTR_WATER, attr.ATTR_BANPK) == (0x01, 0x02, 0x04)
    assert attr.ATTR_SAFEZONE == attr.ATTR_BANPK
    assert (attr.ATTR_BANSHOP, attr.ATTR_FLAG5, attr.ATTR_FLAG6,
            attr.ATTR_FLAG7, attr.ATTR_OBJECT) == (0x08, 0x10, 0x20, 0x40, 0x80)
    assert [n for _, n in attr.FLAG_NAMES] == [
        "block", "water", "safezone", "banshop", "flag5", "flag6", "flag7", "object"]

    names, kind = attr.describe_byte(0xC9)
    assert names == ["block", "banshop", "flag7", "object"] and "mountain" in kind
    assert attr.has_flag(0xC9, attr.ATTR_BLOCK)
    assert not attr.has_flag(0xC8, attr.ATTR_BLOCK)
    assert attr.set_flag(0x40, attr.ATTR_WATER) == 0x42
    assert attr.clear_flag(0xC9, attr.ATTR_BLOCK) == 0xC8
    assert bool(attr.has_flag(am.cells, attr.ATTR_BLOCK).any())


def test_attr_high_bits_are_preserved():
    """Official maps carry paint bytes like 0xC9; nothing may mask them off."""
    _require_corpus()
    f = CORPUS / "map_a2" / "000000" / "attr.atr"
    if not f.exists():
        pytest.skip("map_a2 missing")
    am = attr.read_attr(str(f))
    assert int(am.cells.max()) > 0x07
    assert attr.AttrMap.from_bytes(am.to_bytes()).cells.max() == am.cells.max()


# ---------------------------------------------------------------------------
# water.wtr
# ---------------------------------------------------------------------------
def test_water_header_layers_and_dry_sectors():
    _require_corpus()
    dry = wet = 0
    for map_name in ("metin2_map_n_desert_01", "map_a2", "metin2_map_a1"):
        map_dir = CORPUS / map_name
        if not map_dir.is_dir():
            continue
        for sec in sector_dirs(map_dir):
            f = sec / "water.wtr"
            if not f.exists():
                continue
            blob = f.read_bytes()
            wm = water.read_water(str(f))
            assert blob[:7][:6] == b"\x32\x15\x80\x00\x80\x00"      # 5426, 128, 128
            assert len(blob) == water.BASE_SIZE + 4 * wm.num_layers
            assert not wm.legacy
            assert wm.to_bytes() == blob
            assert wm.validate() == []
            if wm.num_layers:
                wet += 1
                y, x = np.argwhere(wm.wet_mask)[0]
                assert wm.height_at(int(x), int(y)) is not None
            else:
                dry += 1
                assert wm.cells.min() == water.NO_WATER == 0xFF
    assert dry and wet, "expected both dry (N=0) and watered sectors"


def test_water_legacy_uint16_variant():
    """The legacy 2-byte height layout is detected by size and re-emitted as-is."""
    wm = water.new_blank()
    wm.cells[0, 0] = 0
    wm.heights = [19880]
    wm.legacy = True
    blob = wm.to_bytes()
    assert len(blob) == water.BASE_SIZE + 2
    back = water.WaterMap.from_bytes(blob)
    assert back.legacy and back.heights == [19880]
    assert back.to_bytes() == blob
    back.legacy = False
    assert len(back.to_bytes()) == water.BASE_SIZE + 4
    assert back.height_at(0, 0) == 9940.0


# ---------------------------------------------------------------------------
# shadowmap
# ---------------------------------------------------------------------------
def test_shadow_raw_rgb555():
    _require_corpus()
    f = CORPUS / "metin2_map_a1" / "000000" / "shadowmap.raw"
    if not f.exists():
        pytest.skip("metin2_map_a1 missing")
    blob = f.read_bytes()
    assert len(blob) == shadow.FILE_SIZE == 131072
    sm = shadow.read_shadow_raw(str(f))
    assert sm.words.shape == (256, 256)
    assert sm.to_bytes() == blob
    with pytest.raises(ValueError):
        shadow.ShadowMap.from_bytes(blob[:-2])       # loader is strict on size

    assert shadow.rgb555_to_rgb(np.array([[0x7FFF]], np.uint16))[0, 0].tolist() == [248, 248, 248]
    assert int(shadow.rgb_to_rgb555(np.array([[[255, 255, 255]]], np.uint8))[0, 0]) == 0x7FFF
    packed = shadow.rgb_to_rgb555(np.array([[[8, 16, 24]]], np.uint8))
    assert shadow.rgb555_to_rgb(packed)[0, 0].tolist() == [8, 16, 24]
    # engine sampler quirk: (G<<16)|(G<<8)|R, blue dropped
    assert shadow.engine_sample_color(0x7FFF) == (248 << 16) | (248 << 8) | 248
    assert shadow.engine_sample_color((1 << 10) | (2 << 5) | 3) == (16 << 16) | (16 << 8) | 8


# ---------------------------------------------------------------------------
# DDS / minimap
# ---------------------------------------------------------------------------
def test_minimap_parses_and_decodes():
    _require_corpus()
    f = CORPUS / "metin2_map_a1" / "000000" / "minimap.dds"
    if not f.exists():
        pytest.skip("metin2_map_a1 missing")
    blob = f.read_bytes()
    mm = minimap.read_minimap(str(f))
    assert (mm.width, mm.height) == (256, 256)
    assert mm.format_name == "DXT1"
    assert mm.to_bytes() == blob
    px = mm.pixels
    assert px.shape == (256, 256, 4) and px.dtype == np.uint8
    assert mm.dds.expected_data_size() == len(mm.dds.data)
    assert mm.world_bounds(1, 2) == (25600, 51200, 51200, 76800)


def test_dds_all_encodings_decode():
    """Every DDS in the sample decodes to a full-size RGBA surface."""
    _require_corpus()
    seen = {}
    for map_name in SAMPLE_MAPS:
        map_dir = CORPUS / map_name
        if not map_dir.is_dir():
            continue
        for sec in sector_dirs(map_dir):
            for f in sec.glob("*.dds"):
                d = dds.DDS.from_bytes(f.read_bytes())
                px = d.to_rgba(0)
                assert px.shape == (d.height, d.width, 4)
                assert d.expected_data_size() == len(d.data)
                seen.setdefault(d.format_name, 0)
                seen[d.format_name] += 1
    assert "DXT1" in seen and "DXT5" in seen and "R8G8B8" in seen


@pytest.mark.parametrize("fourcc", [b"DXT1", b"DXT3", b"DXT5"])
def test_dxt_encode_decode_roundtrip(fourcc):
    rng = np.random.default_rng(7)
    base = rng.integers(0, 256, size=(64, 64, 3), dtype=np.uint8)
    # smooth the image so block endpoint fitting is meaningful
    base = np.repeat(np.repeat(base[::4, ::4], 4, 0), 4, 1)
    rgba = np.concatenate([base, np.full((64, 64, 1), 255, np.uint8)], axis=2)
    blob = dds.encode_dxt(rgba, fourcc)
    assert len(blob) == 16 * 16 * (8 if fourcc == b"DXT1" else 16)
    back = dds.decode_dxt(blob, 64, 64, fourcc)
    err = np.abs(back[..., :3].astype(int) - rgba[..., :3].astype(int)).mean()
    assert err < 6.0, "DXT round-trip error too high: %.2f" % err
    assert (back[..., 3] == 255).all()


def test_dxt5_alpha_roundtrip():
    rgba = np.zeros((8, 8, 4), np.uint8)
    rgba[..., :3] = 128
    rgba[..., 3] = np.tile(np.array([0, 36, 73, 109, 146, 182, 219, 255], np.uint8), (8, 1))
    blob = dds.encode_dxt(rgba, b"DXT5")
    back = dds.decode_dxt(blob, 8, 8, b"DXT5")
    assert np.abs(back[..., 3].astype(int) - rgba[..., 3].astype(int)).max() <= 8


@pytest.mark.parametrize("fmt", [dds.X8R8G8B8, dds.A8R8G8B8, dds.R8G8B8,
                                 dds.R5G6B5, dds.A1R5G5B5])
def test_uncompressed_formats_roundtrip(fmt):
    rng = np.random.default_rng(3)
    rgba = rng.integers(0, 256, size=(16, 16, 4), dtype=np.uint8)
    pf_flags, fourcc, bpp, rm, gm, bm, am = fmt
    blob = dds.encode_uncompressed(rgba, bpp, rm, gm, bm, am)
    assert len(blob) == 16 * 16 * bpp // 8
    back = dds.decode_uncompressed(blob, 16, 16, bpp, rm, gm, bm, am)
    tol = 4 if bpp >= 24 else 12
    assert np.abs(back[..., :3].astype(int) - rgba[..., :3].astype(int)).max() <= tol
    if am:
        assert np.abs(back[..., 3].astype(int) - rgba[..., 3].astype(int)).max() <= 128
    else:
        assert (back[..., 3] == 255).all()


def test_dds_container_rebuild_is_exact():
    """The header is rebuilt field by field, so a clean re-write proves the parse."""
    rng = np.random.default_rng(11)
    rgba = rng.integers(0, 256, size=(32, 32, 4), dtype=np.uint8)
    for fmt, mips in ((dds.X8R8G8B8, 1), (b"DXT1", 6), (b"DXT5", 1)):
        img = dds.DDS.from_rgba(rgba, fmt=fmt, mipmaps=mips)
        blob = img.to_bytes()
        again = dds.DDS.from_bytes(blob)
        assert again.to_bytes() == blob
        assert again.expected_data_size() == len(again.data)
        assert again.to_rgba(0).shape == (32, 32, 4)


def test_dds_rejects_non_dds():
    with pytest.raises(ValueError):
        dds.DDS.from_bytes(b"NOPE" + bytes(200))


# ---------------------------------------------------------------------------
# LZO1X
# ---------------------------------------------------------------------------
def test_lzo_roundtrip_synthetic():
    rng = np.random.default_rng(5)
    cases = [b"", b"a", b"abc" * 5, b"\x00" * 65536, bytes(range(256)) * 32,
             b"hello world " * 4096,
             rng.integers(0, 256, 40000, dtype=np.uint8).tobytes(),
             rng.integers(0, 4, 65536, dtype=np.uint8).tobytes()]
    for data in cases:
        blob = lzo1x.compress(data)
        assert blob.endswith(b"\x11\x00\x00")
        assert lzo1x.decompress(blob, len(data)) == data
    with pytest.raises(lzo1x.LZOError):
        lzo1x.decompress(lzo1x.compress(b"abc" * 100), 999)


def test_lzo_literal_and_match_shapes():
    """Exercise every literal-run and match encoding branch."""
    rng = np.random.default_rng(9)
    noise = rng.integers(0, 256, 300, dtype=np.uint8).tobytes()
    cases = [
        b"A" * 5000,                                  # long M2/M3 run
        noise + b"Z" * 40 + noise,                     # long literal run + far match
        (b"pattern" * 3) + noise[:2] + (b"pattern" * 3),
        bytes(70000),                                  # match longer than 65535
        noise * 200,                                   # many repeated matches
        # a match at distance > 16 KiB forces the M4 encoding
        (rng.integers(0, 256, 20000, dtype=np.uint8).tobytes() * 1)[:20000] + noise[:100]
        + rng.integers(0, 256, 40, dtype=np.uint8).tobytes(),
    ]
    for data in cases:
        assert lzo1x.decompress(lzo1x.compress(data), len(data)) == data
    # explicit M4 (distance > 0x4000) case: repeat the head far downstream
    head = rng.integers(0, 256, 20000, dtype=np.uint8).tobytes()
    far = head + noise + head[:400] + bytes(40)
    assert lzo1x.decompress(lzo1x.compress(far), len(far)) == far
    assert lzo1x.worst_case_size(65536) == 65536 + 4096 + 67


def test_lzo_rejects_truncated_stream():
    blob = lzo1x.compress(b"x" * 5000)
    with pytest.raises(lzo1x.LZOError):
        lzo1x.decompress(blob[:len(blob) // 2])


# ---------------------------------------------------------------------------
# server_attr
# ---------------------------------------------------------------------------
def _server_attr_paths():
    names = ["map_a2", "map_n_snowm_01", "metin2_map_c1", "metin2_map_n_flame_01",
             "metin2_map_n_snow_dungeon_01", "metin2_map_privatewar"]
    return [SERVER_ATTR_ROOT / n / "server_attr" for n in names]


@pytest.mark.parametrize("path", _server_attr_paths(), ids=lambda p: p.parent.name)
def test_server_attr_roundtrip(path):
    if not path.exists():
        pytest.skip("no server_attr at %s" % path)
    blob = path.read_bytes()
    sa = server_attr.ServerAttr.from_bytes(blob)
    assert sa.width % 4 == 0 and sa.height % 4 == 0
    assert sa.trailing == b""
    assert sa.to_bytes() == blob, "server_attr not byte-identical after write"
    ok, bad = sa.verify()
    assert not bad, "blocks that fail to decompress: %r" % bad[:3]
    assert ok == sa.block_count


def test_server_attr_block_layout_and_recompression():
    path = SERVER_ATTR_ROOT / "map_a2" / "server_attr"
    if not path.exists():
        pytest.skip("no map_a2 server_attr")
    blob = path.read_bytes()
    sa = server_attr.ServerAttr.from_bytes(blob)
    assert (sa.width, sa.height) == (24, 24)            # 6x6 sectrees * 4
    assert sa.sectree_size == (6, 6)
    assert blob[:8] == b"\x18\x00\x00\x00\x18\x00\x00\x00"
    grid = sa.block(0, 0)
    assert grid.shape == (128, 128) and grid.dtype == np.dtype("<u4")

    # our compressor is not byte-compatible with the shipped minilzo output,
    # but must be data-compatible in both directions
    raw = grid.tobytes()
    assert len(raw) == server_attr.BLOCK_BYTES == 65536
    assert lzo1x.decompress(lzo1x.compress(raw), 65536) == raw
    original = sa.compressed_block(0, 0)
    assert lzo1x.decompress(original, 65536) == raw

    # touching one block only re-compresses that block; the rest stay verbatim
    sa.set_block(1, 0, grid)
    out = sa.to_bytes()
    assert out != blob
    back = server_attr.ServerAttr.from_bytes(out)
    assert np.array_equal(back.block(1, 0), grid)
    for sy in range(sa.height):
        for sx in range(sa.width):
            if (sx, sy) != (1, 0):
                assert back.compressed_block(sx, sy) == sa.compressed_block(sx, sy)


@pytest.mark.parametrize("map_name", ["metin2_map_n_flame_01",
                                      "metin2_map_n_snow_dungeon_01",
                                      "metin2_map_privatewar"])
def test_server_attr_matches_client_attr(map_name):
    """y-major block order + 2x2 upsampling reproduce the client attr grids.

    These three maps' shipped server_attr copies the whole attr byte, so the
    reconstruction must be exact.
    """
    root = SERVER_ATTR_ROOT / map_name
    if not (root / "server_attr").exists():
        pytest.skip("no %s server_attr" % map_name)
    sa = server_attr.read_server_attr(str(root / "server_attr"))
    cw, ch = sa.sectree_size
    compared = 0
    for cy in range(ch):
        for cx in range(cw):
            f = root / ("%03d%03d" % (cx, cy)) / "attr.atr"
            if not f.exists():
                continue
            client = attr.read_attr(str(f)).cells
            assert np.array_equal(client, sa.to_attr_grid(cx, cy))
            compared += 1
    assert compared


def test_server_attr_ymir_files_mask_the_paint_bits():
    """map_a2's shipped server_attr keeps only bits 0..2 of the attr bytes.

    This contradicts ServerAttrGenerator.cpp (which copies the full byte) and is
    why :func:`server_attr.from_attr_maps` takes a ``mask`` argument.
    """
    root = SERVER_ATTR_ROOT / "map_a2"
    if not (root / "server_attr").exists():
        pytest.skip("no map_a2 server_attr")
    sa = server_attr.read_server_attr(str(root / "server_attr"))
    client = attr.read_attr(str(root / "000000" / "attr.atr")).cells
    rebuilt = sa.to_attr_grid(0, 0)
    assert int(client.max()) > 0x07
    assert not np.array_equal(client, rebuilt)
    assert np.array_equal(client & 0x07, rebuilt & 0x07)
    assert int(rebuilt.max()) <= 0x07


def test_server_attr_generation_roundtrip():
    """Generate from attr grids, then read the blocks back."""
    _require_corpus()
    map_dir = next((CORPUS / n for n in ("metin2_map_privatewar", "metin2_map_guild_01",
                                        "metin2_map_trent")
                    if (CORPUS / n).is_dir() and sector_dirs(CORPUS / n)), None)
    if map_dir is None:
        pytest.skip("no small map available")
    secs = sector_dirs(map_dir)
    grids = {}
    for sec in secs:
        f = sec / "attr.atr"
        if f.exists():
            cx, cy = int(sec.name[:3]), int(sec.name[3:])
            grids[(cx, cy)] = attr.read_attr(str(f)).cells
    w = max(k[0] for k in grids) + 1
    h = max(k[1] for k in grids) + 1
    sa = server_attr.from_attr_maps(grids, w, h)
    assert (sa.width, sa.height) == (w * 4, h * 4)
    blob = sa.to_bytes()
    back = server_attr.ServerAttr.from_bytes(blob)
    assert back.to_bytes() == blob
    # The DEFAULT masks to 0x07 -- see from_attr_maps' docstring. Asserting
    # equality with the raw grid here is what let the whole-byte default ship.
    for (cx, cy), grid in grids.items():
        assert np.array_equal(back.to_attr_grid(cx, cy), grid & 0x07)
    # opting out reproduces the editor's (unshippable) whole-byte copy
    raw = server_attr.from_attr_maps(grids, w, h, mask=None)
    for (cx, cy), grid in grids.items():
        assert np.array_equal(raw.to_attr_grid(cx, cy), grid)


def test_from_attr_maps_default_reproduces_shipped_server_attr():
    """The generator's DEFAULT must reproduce Ymir's own file byte-for-byte.

    Regression guard for the critical bug found in review: the default copied
    the whole client attr byte, but the server reads bit 7 as ATTR_OBJECT and
    blocks on ATTR_BLOCK|ATTR_OBJECT (char.cpp:5648). Ymir paints bit 7 on
    *walkable* mountain cells, so the whole-byte copy server-blocked every cell
    of map_a2 -- 9,437,184 of 9,437,184 -- against the shipped 6,246,724.
    17 corpus maps carry 0x80 on 100% of cells and were all bricked.
    """
    root = SERVER_ATTR_ROOT / "map_a2"
    if not (root / "server_attr").exists():
        pytest.skip("no map_a2 server_attr")
    shipped = server_attr.read_server_attr(str(root / "server_attr"))
    cw, ch = shipped.sectree_size

    grids = {}
    for cy in range(ch):
        for cx in range(cw):
            f = root / ("%03d%03d" % (cx, cy)) / "attr.atr"
            if f.exists():
                grids[(cx, cy)] = attr.read_attr(str(f)).cells
    assert len(grids) == cw * ch, "map_a2 should have every sector"

    built = server_attr.from_attr_maps(grids, cw, ch)
    for sy in range(shipped.height):
        for sx in range(shipped.width):
            assert np.array_equal(shipped.block(sx, sy), built.block(sx, sy)), \
                "block (%d,%d) differs from the shipped file" % (sx, sy)

    # and the failure mode itself: whole-byte blocks the entire map
    def blocked(sa):
        return sum(int(np.count_nonzero(sa.block(x, y) & 0x81))
                   for y in range(sa.height) for x in range(sa.width))

    total = shipped.width * shipped.height * 128 * 128
    assert blocked(built) == blocked(shipped)
    assert blocked(server_attr.from_attr_maps(grids, cw, ch, mask=None)) == total


def test_server_attr_rejects_truncated():
    with pytest.raises(ValueError):
        server_attr.ServerAttr.from_bytes(b"\x04\x00\x00\x00")
    with pytest.raises(ValueError):
        server_attr.ServerAttr.from_bytes(
            b"\x01\x00\x00\x00\x01\x00\x00\x00" + b"\xff\xff\x00\x00" + b"\x00")


# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------
def test_zz_summary():
    print("\nround-tripped %d files (%.1f MiB) over %d sectors in %d maps"
          % (STATS["files"], STATS["bytes"] / 1048576.0, STATS["sectors"], STATS["maps"]))
    if STATS["maps"]:
        assert STATS["maps"] >= 12, "fewer than 12 maps were exercised"
        assert STATS["files"] >= 500


# ---------------------------------------------------------------------------
# optional: cross-check LZO against a real liblzo2 build
# ---------------------------------------------------------------------------
def _load_liblzo2():
    import ctypes
    candidates = [os.environ.get("M2MAP_LZO_DLL"),
                  "<HOME>/Documents/git/vcpkg/buildtrees/lzo/x64-windows-rel/lzo2.dll",
                  "lzo2.dll", "liblzo2.so.2"]
    for path in candidates:
        if not path:
            continue
        try:
            lib = ctypes.CDLL(path)
        except OSError:
            continue
        lib.__lzo_init_v2(ctypes.c_uint(0x2090), *([ctypes.c_int(-1)] * 9))
        return lib
    return None


def test_lzo_matches_liblzo2_oracle():
    """Both directions against a real minilzo/liblzo2 build, when one is present.

    The point is production safety: the game server decompresses with
    ``lzo1x_decompress_safe``, so anything :func:`lzo1x.compress` writes must be
    readable by the C library, and anything the C library wrote must be readable
    by :func:`lzo1x.decompress`.
    """
    import ctypes
    lib = _load_liblzo2()
    if lib is None:
        pytest.skip("no liblzo2 available (set M2MAP_LZO_DLL)")

    def c_compress(data):
        dst = ctypes.create_string_buffer(lzo1x.worst_case_size(len(data)))
        dlen = ctypes.c_size_t(0)
        wrk = ctypes.create_string_buffer(1 << 18)
        rc = lib.lzo1x_1_compress(ctypes.create_string_buffer(data, len(data)),
                                  ctypes.c_size_t(len(data)), dst, ctypes.byref(dlen), wrk)
        assert rc == 0
        return dst.raw[:dlen.value]

    def c_decompress(data, cap):
        dst = ctypes.create_string_buffer(cap)
        dlen = ctypes.c_size_t(cap)
        rc = lib.lzo1x_decompress_safe(ctypes.create_string_buffer(data, len(data)),
                                       ctypes.c_size_t(len(data)), dst, ctypes.byref(dlen), None)
        assert rc == 0, "liblzo2 rejected our stream (rc=%d)" % rc
        return dst.raw[:dlen.value]

    rng = np.random.default_rng(13)
    samples = [b"A" * 5000,
               rng.integers(0, 256, 20000, dtype=np.uint8).tobytes(),
               rng.integers(0, 3, 65536, dtype=np.uint8).tobytes(),
               bytes(65536)]
    path = SERVER_ATTR_ROOT / "map_a2" / "server_attr"
    if path.exists():
        sa = server_attr.ServerAttr.from_bytes(path.read_bytes())
        for sx, sy in ((0, 0), (3, 5), (23, 23)):
            samples.append(sa.block(sx, sy).tobytes())
            # our decoder on the shipped minilzo stream
            assert lzo1x.decompress(sa.compressed_block(sx, sy), 65536) == \
                c_decompress(sa.compressed_block(sx, sy), 65536)
    for data in samples:
        assert lzo1x.decompress(c_compress(data), len(data)) == data
        assert c_decompress(lzo1x.compress(data), len(data) + 4096) == data

"""Readapting a merged map: two walled bowls stacked 1x2, at different datums,
become one floor.

The properties under test all cross the file boundary and come back (SKILL
rule 18), because every one of them is a unit or an ownership question that an
in-memory assertion answers wrongly:

* the shared border vertices agree ON DISK;
* a walkable route joins the two floors;
* the pond is as deep as it was and the object stands on the ground as it did,
  after a 9 m datum shift that touched terrain, water and ``z`` -- and left the
  height bias alone.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "skills" / "m2map" / "scripts"))

from m2map.audit.rules import torn_borders                        # noqa: E402
from m2map.codec import areadata as ad                            # noqa: E402
from m2map.codec import attr as attr_codec                        # noqa: E402
from m2map.codec import height as height_codec                    # noqa: E402
from m2map.codec import tile as tile_codec                        # noqa: E402
from m2map.codec import water as water_codec                      # noqa: E402
from m2map.edit import readapt                                    # noqa: E402
from m2map.gen.walkable import reachable                          # noqa: E402

SETTING = ("ScriptType\tMapSetting\r\n\r\nCellScale\t200\r\nHeightScale\t0.500000\r\n\r\n"
           "ViewRadius\t128\r\n\r\nMapSize\t1\t2\r\nBasePosition\t0\t0\r\n"
           "TextureSet\ttextureset\\none.txt\r\nEnvironment\ta1.msenv\r\n")
FLOORS = (17300.0, 16384.0)          # the two source maps' datums, cm
POND_DEPTH = 150.0
BIAS = -35.0
CRC = 26807040


FORD_ROWS = slice(76, 80)            # a river across bowl 0, flagged water, NOT blocked
FILLER_CM = 20000.0
ROAD_ROWS = slice(150, 158)          # tiles; south of the pond in each bowl


def _bowl(floor_cm: float, seed: int, ford: bool = False):
    """One sealed source map: flat floor, a 40-cell mountain ring, a pond."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:129, 0:129]
    edge = np.minimum(np.minimum(xx, 128 - xx), np.minimum(yy, 128 - yy))
    wall = np.clip((40 - edge) / 40.0, 0, 1)
    z = floor_cm + wall * (4000 + rng.random((129, 129)) * 1500)
    pond = (xx - 64) ** 2 + (yy - 64) ** 2 < 8 ** 2
    z[pond] -= POND_DEPTH + 100
    if ford:
        river = np.zeros((129, 129), bool)
        river[FORD_ROWS, :] = edge[FORD_ROWS, :] > 36       # bank to bank, into the rock
        z[river] -= POND_DEPTH + 100
        pond = pond | river
    return z, pond[:128, :128]


def _write_filler(d: pathlib.Path) -> None:
    """What a merge squares an L off with: a blank plane, no paint, no attr."""
    d.mkdir()
    raw = np.full((131, 131), FILLER_CM / 0.5).astype("<u2")
    height_codec.write_height(d / "height.raw", height_codec.HeightMap(raw))
    attr_codec.write_attr(d / "attr.atr", attr_codec.AttrMap(np.zeros((256, 256), np.uint8)))
    tiles = tile_codec.new_blank(1)
    tiles.raw[:] = 0
    tile_codec.write_tile(d / "tile.raw", tiles)
    water_codec.write_water(d / "water.wtr", water_codec.WaterMap(
        np.full((128, 128), water_codec.NO_WATER, np.uint8), []))
    (d / "areaproperty.txt").write_bytes(b"ScriptType AreaProperty\r\n")


def _write_merged(root: pathlib.Path, ford: bool = False, filler: bool = False,
                  road: bool = False) -> None:
    root.mkdir()
    (root / "setting.txt").write_bytes(SETTING.encode("ascii"))
    if filler:
        for sy in range(2):
            _write_filler(root / ("%06u" % (1000 + sy)))
    for sy, floor in enumerate(FLOORS):
        d = root / ("%06u" % sy)
        d.mkdir()
        z, pond = _bowl(floor, sy, ford and sy == 0)
        raw = np.pad(np.round(z / 0.5), 1, mode="edge").astype("<u2")
        height_codec.write_height(d / "height.raw", height_codec.HeightMap(raw))
        steep = np.zeros((128, 128), bool)
        steep |= (z[:-1, :-1] > floor + 60)
        cells = np.where(steep, 1, 0).astype(np.uint8)
        cells[pond] |= 2
        attr_codec.write_attr(d / "attr.atr", attr_codec.AttrMap(cells.repeat(2, 0).repeat(2, 1)))
        tiles = tile_codec.new_blank(1)
        tiles.raw[1:257, 1:257][steep.repeat(2, 0).repeat(2, 1)] = 2
        if road:
            # Slot 4 is everywhere, a tile at a time; slot 3 is a road: a solid
            # strip, 8 m wide, a fraction of the share.
            inner = tiles.raw[1:257, 1:257]
            speck = (np.random.default_rng(7 + sy).random((256, 256)) < 0.3) & (inner == 1)
            inner[speck] = 4
            inner[ROAD_ROWS, 84:172] = 3
        tile_codec.write_tile(d / "tile.raw", tiles)
        wc = np.full((128, 128), water_codec.NO_WATER, np.uint8)
        wc[pond] = 0
        water_codec.write_water(d / "water.wtr",
                                water_codec.WaterMap(wc, [int((floor - 100) / 0.5)]))
        rec = ad.ObjectRecord(x=9000.0, y=-(sy * 25600 + 9000.0), z=floor, crc=CRC,
                              height_bias=BIAS)
        (d / "areadata.txt").write_bytes(ad.AreaData([rec]).to_bytes())
        (d / "areaproperty.txt").write_bytes(b"ScriptType AreaProperty\r\n")


def test_readapt_joins_levels_and_keeps_every_relation(tmp_path):
    src, out = tmp_path / "merged", tmp_path / "readapted"
    _write_merged(src)
    assert torn_borders(src, ["000000", "000001"]), "the fixture must start torn"

    report = readapt.readapt(src, out)

    assert report["blocks"] == {0: ["000000"], 1: ["000001"]}
    assert all(report["joined"].values())
    assert not report.get("problems")
    shift = FLOORS[1] - FLOORS[0]
    assert sorted(abs(v) for v in report["level_cm"].values()) == [0.0, abs(shift)]

    # -- read it back ------------------------------------------------------
    assert torn_borders(out, ["000000", "000001"]) == []
    assert report["tear_after_cm"] == 0.0
    assert (out / "server_attr").exists(), "attr changed, so the server file is rebuilt (rule 14)"
    assert report["server_attr"]["agrees"] and report["server_attr"]["max_value"] <= 7

    m = readapt.MergedMap(out)
    z, _ = m.stitch()
    zc = readapt._cell_z(z)
    free = readapt._cell_free(m.attr)
    whole = reachable(free)
    assert whole[64 - 20, 64] and whole[128 + 64 - 20, 64], "one floor, both bowls on it"

    for sy in range(2):
        pond_z = m.wraw[sy * 128 + 64, 64] * 0.5
        assert abs((pond_z - zc[sy * 128 + 64, 64]) - POND_DEPTH) < 1.0, "pond kept its depth"
        rec = m.areas[0, sy].records[0]
        assert abs(rec.z - readapt._bilinear(z, rec.x, -rec.y)) < 1.0, "object rides the ground"
        assert rec.height_bias == BIAS, "the bias is the author's, not ours"

    floors = [np.median(zc[sy * 128 + 50:sy * 128 + 60, 50:60]) for sy in range(2)]
    assert abs(floors[0] - floors[1]) < 1.0, "one datum"


def test_no_level_leaves_the_datums_and_grades_the_road(tmp_path):
    src, out = tmp_path / "merged", tmp_path / "readapted"
    _write_merged(src)
    report = readapt.readapt(src, out, readapt.Options(level=False))
    assert set(report["level_cm"].values()) == {0.0}
    assert all(report["joined"].values())
    a, b = report["links"][0]["mouths_cm"]
    assert abs(abs(a - b) - abs(FLOORS[0] - FLOORS[1])) < 60


def test_a_sound_border_ending_on_a_torn_one_is_not_torn(tmp_path):
    """2x2: the left column is one source map, the right column another, 40 m
    higher. The two horizontal borders are sound, but each ENDS on the torn
    vertical one and shares its corner vertex -- one 40 m corner in 129 vertices
    is a 31 cm mean, and with any relief a false tear. On map_merge_test_02 the
    mean called four such borders torn (57-67 cm) and paired a block with
    itself."""
    for sx in range(2):
        for sy in range(2):
            d = tmp_path / ("%06u" % (sx * 1000 + sy))
            d.mkdir()
            z = np.full((129, 129), 16000.0 + 8000.0 * sx)
            z[:, 0 if sx else 128] += 60.0        # relief on the torn edge only
            raw = np.pad(np.round(z / 0.5), 1, mode="edge").astype("<u2")
            height_codec.write_height(d / "height.raw", height_codec.HeightMap(raw))
    torn = torn_borders(tmp_path, ["000000", "000001", "001000", "001001"])
    assert sorted((a, b) for a, b, _, _ in torn) == [("000000", "001000"), ("000001", "001001")]


def test_a_forded_river_does_not_split_the_floor(tmp_path):
    """c1's river carries the water flag and no block. Read as a wall it cut that
    map into three floors, and the pass set out from the largest: 850 m across
    open ground, the whole way carved into a ramp (map_merge_test_03)."""
    src, out = tmp_path / "merged", tmp_path / "readapted"
    _write_merged(src, ford=True)
    report = readapt.readapt(src, out)
    (link,) = report["links"]
    assert link["from_tile"][1] >= FORD_ROWS.stop * 2, "the pass leaves from the near bank"
    assert all(report["joined"].values()) and not report.get("problems")


def test_filler_is_not_a_source_map(tmp_path):
    """A staggered merge is squared off with blank sectors. They are not routed
    to, they do not outvote a real ring in the weld, and their slot 0 -- the
    eraser -- is never painted from."""
    src, out = tmp_path / "merged", tmp_path / "readapted"
    _write_merged(src, filler=True)
    report = readapt.readapt(src, out)
    assert report["void_blocks"] == [1]
    assert [lk["blocks"] for lk in report["links"]] == [[0, 2]]
    assert report["tear_after_cm"] == 0.0 and report["blank_tiles_added"] == 0
    assert not report.get("problems")
    m = readapt.MergedMap(out)
    ring = m.hwin[0, 0][40:90, 128] - report["level_cm"][0]
    was = readapt.MergedMap(src).hwin[0, 0][40:90, 128]
    assert np.abs(ring - was).max() < 1.0, "the ring kept its crest; the filler came to it"


def test_the_pass_is_painted_on_to_the_maps_own_road(tmp_path):
    """The road slot is the one that is solid, walkable and dry -- not the one
    used most: on b1, c1 and a1 the most-used `field` slot is the band round the
    water. And a pass ends where the wall is thinnest, so its road runs on, over
    open floor, to the nearest real one."""
    src, out = tmp_path / "merged", tmp_path / "readapted"
    _write_merged(src, road=True)
    report = readapt.readapt(src, out)
    assert [v["road"] for v in report["slots"].values()] == [3, 3]
    (link,) = report["links"]
    assert all(d is not None and 0 < d <= 150 for d in link["road_joined_m"])
    m = readapt.MergedMap(out)
    gap = m.tile[256 + 96:256 + ROAD_ROWS.start - 4, :]        # bowl 1: floor north of its road
    assert (gap == 3).sum() > 100, "road painted across the floor between them"
    assert not report.get("problems")

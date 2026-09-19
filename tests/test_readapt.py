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


def _bowl(floor_cm: float, seed: int):
    """One sealed source map: flat floor, a 40-cell mountain ring, a pond."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:129, 0:129]
    edge = np.minimum(np.minimum(xx, 128 - xx), np.minimum(yy, 128 - yy))
    wall = np.clip((40 - edge) / 40.0, 0, 1)
    z = floor_cm + wall * (4000 + rng.random((129, 129)) * 1500)
    pond = (xx - 64) ** 2 + (yy - 64) ** 2 < 8 ** 2
    z[pond] -= POND_DEPTH + 100
    return z, pond[:128, :128]


def _write_merged(root: pathlib.Path) -> None:
    root.mkdir()
    (root / "setting.txt").write_bytes(SETTING.encode("ascii"))
    for sy, floor in enumerate(FLOORS):
        d = root / ("%06u" % sy)
        d.mkdir()
        z, pond = _bowl(floor, sy)
        raw = np.pad(np.round(z / 0.5), 1, mode="edge").astype("<u2")
        height_codec.write_height(d / "height.raw", height_codec.HeightMap(raw))
        steep = np.zeros((128, 128), bool)
        steep |= (z[:-1, :-1] > floor + 60)
        cells = np.where(steep, 1, 0).astype(np.uint8)
        cells[pond] |= 2
        attr_codec.write_attr(d / "attr.atr", attr_codec.AttrMap(cells.repeat(2, 0).repeat(2, 1)))
        tiles = tile_codec.new_blank(1)
        tiles.raw[1:257, 1:257][steep.repeat(2, 0).repeat(2, 1)] = 2
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

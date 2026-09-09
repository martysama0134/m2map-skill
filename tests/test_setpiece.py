"""Set-piece copying: a compound read off one map reappears on another with
its spatial relationships intact.

The property under test is not "the records exist" but "the panels still
meet": every pairwise distance and every heading of the source is reproduced,
because that is exactly what three generated versions of the same camp lost.
"""

from __future__ import annotations

import itertools
import math
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "skills" / "m2map" / "scripts"))

from m2map.codec import areadata as ad                            # noqa: E402
from m2map.gen import pipeline, setpiece                         # noqa: E402
from m2map.gen.spec import PlazaSpec                             # noqa: E402

from test_generate import make_spec                              # noqa: E402

# A five-panel rail read off metin2_map_n_desert_01 at (333, 307): world
# position in cm (areadata frame, y NEGATED), roll, bias, crc. Steps between
# panels are 520 / 362 / 232 / 238 cm -- three different panel lengths
# (the source reads 231 / 237; these coordinates are its two-decimal table).
RAIL = [
    (31356.0, -30455.0, 60.0, -5.0, 1339763610),
    (31675.0, -30044.0, 225.0, -5.0, 2600313213),
    (31985.0, -29857.0, 210.0, -5.0, 2157974046),
    (32207.0, -29791.0, 195.0, -5.0, 3248083804),
    (32415.0, -29675.0, 210.0, -5.0, 311819914),
]
TENT = (31411.0, -31583.0, 105.0, -5.0, 1099929426)      # 11 m off, other side
FAR = (40000.0, -40000.0, 0.0, 0.0, 1099929426)          # 122 m off: excluded


def _write_map(root: pathlib.Path, recs, sector=(1, 1)) -> pathlib.Path:
    """A one-sector 'map' holding `recs` in areadata form."""
    d = root / "metin2_map_fake" / ("%03d%03d" % sector)
    d.mkdir(parents=True)
    area = ad.AreaData(records=[
        ad.ObjectRecord(x=x, y=y, z=17826.0, crc=crc, roll=roll, height_bias=bias)
        for x, y, roll, bias, crc in recs])
    area.declared_count = len(area.records)
    (d / "areadata.txt").write_bytes(area.to_bytes())
    return d.parent


def _pair_distances(points):
    return sorted(round(math.hypot(a[0] - b[0], a[1] - b[1]), 1)
                  for a, b in itertools.combinations(points, 2))


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    return _write_map(tmp_path_factory.mktemp("src"), RAIL + [TENT, FAR])


def test_extract_reads_the_radius_and_de_negates_y(source):
    pieces = setpiece.extract(source, (333, 307), 32)
    assert len(pieces) == 6                              # FAR is outside
    by_crc = {p.crc: p for p in pieces if p.crc != 1099929426}
    first = by_crc[1339763610]
    # world (31356, terrain_y 30455) is 19.44 m west, 2.45 m north of (333, 307)
    assert first.dx == pytest.approx(-19.44, abs=0.01)
    assert first.dy == pytest.approx(-2.45, abs=0.01)
    assert first.roll == 60.0 and first.height_bias == -5.0
    # ordered by distance, so the table is stable
    ds = [math.hypot(p.dx, p.dy) for p in pieces]
    assert ds == sorted(ds)
    assert setpiece.relief_cm(pieces) == 0.0             # one plane in the source
    assert setpiece.headings(pieces)[210.0] == 2


def test_stamp_keeps_every_roll_and_bias_and_never_rotates(source):
    pieces = setpiece.extract(source, (333, 307), 32)
    tiers = setpiece.stamp(pieces, anchor=(88.0, 108.0), label="camp")
    # one tier per (crc, bias); the rail's five CRCs plus the tent
    assert len(tiers) == 6
    assert all(t.height_bias == (-5.0, -5.0) for t in tiers)
    assert all(t.max_slope == 90.0 and t.density == 0.0 for t in tiers)
    placed = [pos for t in tiers for pos in t.positions]
    assert all(len(pos) == 3 for pos in placed)
    src = [(p.dx, p.dy) for p in pieces]
    dst = [(x - 88.0, y - 108.0) for x, y, _ in placed]
    assert _pair_distances(src) == _pair_distances(dst)
    assert sorted(p.roll for p in pieces) == sorted(r for _, _, r in placed)


def test_stamped_piece_survives_the_pipeline_with_its_geometry(source):
    """Build a map with the copied rail and read the records back: the panel
    steps must be the fixture's 520 / 362 / 232 / 238 cm and the rolls the
    source's, at the anchor, on the levelled pad."""
    pieces = [p for p in setpiece.extract(source, (333, 307), 32)
              if p.crc != 1099929426]
    anchor = (88.0, 108.0)
    spec = make_spec(
        objects=setpiece.stamp(pieces, anchor, label="rail"),
        plazas=[PlazaSpec(centre=anchor, radius_m=30.0, tile_index=0, safezone=False)],
    )
    b = pipeline.run(spec)
    recs = sorted((r for r in b.records if r.crc in {p.crc for p in pieces}),
                  key=lambda r: r.x)
    assert len(recs) == 5
    steps = [round(math.hypot(b_.x - a.x, b_.y - a.y))
             for a, b_ in zip(recs, recs[1:])]
    assert steps == [520, 362, 232, 238]
    assert [r.roll for r in recs] == [60.0, 225.0, 210.0, 195.0, 210.0]
    assert all(r.height_bias == -5.0 for r in recs)
    # the anchor really is where the source point landed
    first = recs[0]
    assert first.x / 100.0 == pytest.approx(anchor[0] - 19.44, abs=0.02)
    assert first.terrain_y / 100.0 == pytest.approx(anchor[1] - 2.45, abs=0.02)

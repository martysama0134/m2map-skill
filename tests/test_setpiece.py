"""Set-piece copying: a compound read off one map reappears on another with
its spatial relationships intact -- translated, and turned about its centre.

The property under test is not "the records exist" but "the panels still
meet": every pairwise distance and every heading of the source is reproduced,
because that is exactly what three generated versions of the same camp lost.
For rotation the check is the measured invariant, roll + bearing-to-neighbour
(mod 180): a turn with the right sign keeps it, a turn with the wrong sign
scatters it.
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
RAIL_CRCS = {r[4] for r in RAIL}
TENT = (31411.0, -31583.0, 105.0, -5.0, 1099929426)      # 11 m off, other side
FAR = (40000.0, -40000.0, 0.0, 0.0, 1099929426)          # 122 m off: excluded
PATTERN = REPO_ROOT / "skills" / "m2map" / "reference" / "setpieces" / "desert_camp.json"


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
    sp = setpiece.extract(source, (333, 307), 32, pivot="centre")
    assert len(sp.pieces) == 6                           # FAR is outside
    assert sp.source_map == "metin2_map_fake" and sp.pivot_m == (333.0, 307.0)
    by_crc = {p.crc: p for p in sp.pieces if p.crc != 1099929426}
    first = by_crc[1339763610]
    # world (31356, terrain_y 30455) is 19.44 m west, 2.45 m north of (333, 307)
    assert first.dx == pytest.approx(-19.44, abs=0.01)
    assert first.dy == pytest.approx(-2.45, abs=0.01)
    assert first.roll == 60.0 and first.height_bias == -5.0
    # ordered by distance, so the table is stable
    ds = [math.hypot(p.dx, p.dy) for p in sp.pieces]
    assert ds == sorted(ds)
    assert sp.relief_cm() == 0.0                         # one plane in the source
    assert sp.headings()[210.0] == 2


def test_centroid_pivot_is_the_blocks_own_centre(source):
    sp = setpiece.extract(source, (333, 307), 32)
    assert sp.pivot == "centroid"
    assert sum(p.dx for p in sp.pieces) == pytest.approx(0.0, abs=1e-9)
    assert sum(p.dy for p in sp.pieces) == pytest.approx(0.0, abs=1e-9)
    # the pivot is where the mean of the records sits on the source map
    xs = [r[0] for r in RAIL + [TENT]]
    ys = [-r[1] for r in RAIL + [TENT]]
    assert sp.pivot_m[0] == pytest.approx(sum(xs) / len(xs) / 100.0)
    assert sp.pivot_m[1] == pytest.approx(sum(ys) / len(ys) / 100.0)
    # and the geometry is the same block as about the centre
    sc = setpiece.extract(source, (333, 307), 32, pivot="centre")
    assert _pair_distances([(p.dx, p.dy) for p in sp.pieces]) == \
        _pair_distances([(p.dx, p.dy) for p in sc.pieces])


def test_exclude_drops_the_next_compound_before_the_centroid(source):
    """A disc cannot always take one compound and nothing of its neighbour.

    The b1 town square at 60 m clips four corners and the gate of the walled
    estate beside it; they are named out, and the centroid is of what is left.
    """
    names = {1099929426: "general_obj_tent01", 1339763610: "general_obj_fence01"}
    sp = setpiece.extract(source, (333, 307), 32, names=names, exclude=["TENT"])
    assert len(sp.pieces) == 5 and all(p.crc in RAIL_CRCS for p in sp.pieces)
    assert sum(p.dx for p in sp.pieces) == pytest.approx(0.0, abs=1e-9)
    # a CRC works too, for a prop the catalog has no name for
    sp = setpiece.extract(source, (333, 307), 32, exclude=["1099929426"])
    assert len(sp.pieces) == 5


def test_stamp_keeps_every_roll_and_bias(source):
    sp = setpiece.extract(source, (333, 307), 32)
    tiers = sp.stamp(anchor=(88.0, 108.0), label="camp")
    # one tier per (crc, bias); the rail's five CRCs plus the tent
    assert len(tiers) == 6
    assert all(t.height_bias == (-5.0, -5.0) for t in tiers)
    assert all(t.max_slope == 90.0 and t.density == 0.0 for t in tiers)
    placed = [pos for t in tiers for pos in t.positions]
    assert all(len(pos) == 3 for pos in placed)
    src = [(p.dx, p.dy) for p in sp.pieces]
    dst = [(x - 88.0, y - 108.0) for x, y, _ in placed]
    assert _pair_distances(src) == _pair_distances(dst)
    assert sorted(p.roll for p in sp.pieces) == sorted(r for _, _, r in placed)


@pytest.mark.parametrize("deg", [90.0, 45.0, 180.0, 270.0, 15.0])
def test_rotation_is_rigid_and_keeps_the_roll_bearing_invariant(source, deg):
    sp = setpiece.extract(source, (333, 307), 32)
    rail = [p for p in sp.pieces if p.crc in RAIL_CRCS]
    turned = setpiece.rotate(rail, deg)
    # rigid about the pivot
    assert _pair_distances([(p.dx, p.dy) for p in rail]) == \
        pytest.approx(_pair_distances([(p.dx, p.dy) for p in turned]), abs=1e-6)
    assert [math.hypot(p.dx, p.dy) for p in rail] == \
        pytest.approx([math.hypot(p.dx, p.dy) for p in turned])
    # every roll gains deg
    assert [(p.roll - q.roll) % 360.0 for p, q in zip(turned, rail)] == \
        pytest.approx([deg % 360.0] * len(rail))
    # the measured invariant: roll + bearing to the neighbour is unchanged
    c0, m0, n0 = setpiece.alignment(rail)
    c1, m1, n1 = setpiece.alignment(turned)
    assert n0 == n1 == 5 and c0 > 0.9
    assert c1 == pytest.approx(c0, abs=1e-6)
    assert m1 == pytest.approx(m0, abs=1e-6)


def test_the_wrong_handedness_would_fail_the_invariant(source):
    """The check has teeth: rotating offsets one way and rolls the other
    (what an earlier template stamper did) shifts roll + bearing by twice the
    angle. At 45 that is 90 -- every panel across its own line. (At 90 or 180
    the shift is 0 mod 180 and the check is blind; the sign comes from the
    corpus measurement, not from here.)"""
    sp = setpiece.extract(source, (333, 307), 32)
    rail = [p for p in sp.pieces if p.crc in RAIL_CRCS]
    a = math.radians(45.0)
    wrong = [setpiece.Piece(dx=p.dx * math.cos(a) - p.dy * math.sin(a),
                            dy=p.dx * math.sin(a) + p.dy * math.cos(a),
                            roll=(p.roll + 45.0) % 360.0, height_bias=p.height_bias,
                            crc=p.crc) for p in rail]
    c0, m0, _ = setpiece.alignment(rail)
    c1, m1, _ = setpiece.alignment(wrong)
    assert c1 == pytest.approx(c0, abs=1e-6)             # still a rail, but...
    assert abs(((m1 - m0) + 90.0) % 180.0 - 90.0) == pytest.approx(90.0, abs=1e-6)
    # ...while the right turn leaves it where it was
    c2, m2, _ = setpiece.alignment(setpiece.rotate(rail, 45.0))
    assert m2 == pytest.approx(m0, abs=1e-6)


def test_rotations_compose_and_undo(source):
    sp = setpiece.extract(source, (333, 307), 32)
    twice = sp.rotated(45.0).rotated(45.0)
    once = sp.rotated(90.0)
    for p, q in zip(twice.pieces, once.pieces):
        assert (p.dx, p.dy, p.roll) == pytest.approx((q.dx, q.dy, q.roll))
    back = sp.rotated(90.0).rotated(-90.0)
    for p, q in zip(back.pieces, sp.pieces):
        assert (p.dx, p.dy, p.roll % 360.0) == pytest.approx((q.dx, q.dy, q.roll % 360.0))
    assert once.rotation_deg == 90.0 and back.rotation_deg == 0.0


def test_pattern_round_trips_through_json(source, tmp_path):
    sp = setpiece.extract(source, (333, 307), 32, name="fake_camp")
    sp.notes = "test"
    path = sp.save(tmp_path / "fake_camp.json")
    back = setpiece.load(path)
    assert back.name == "fake_camp" and back.notes == "test"
    assert back.source_map == sp.source_map and back.pivot_m == pytest.approx(sp.pivot_m)
    assert back.source_point_m == (333.0, 307.0) and back.radius_m == 32.0
    for p, q in zip(back.pieces, sp.pieces):
        assert (p.dx, p.dy) == pytest.approx((q.dx, q.dy), abs=1e-4)
        assert (p.roll, p.height_bias, p.crc, p.z) == (q.roll, q.height_bias, q.crc, q.z)
    with pytest.raises(ValueError):
        setpiece.SetPiece.from_dict({"format": "something-else", "name": "x", "pieces": []})


def test_shipped_desert_camp_pattern_is_intact():
    """The saved pattern is the 32-record camp about its centroid."""
    sp = setpiece.load(PATTERN)
    assert sp.source_map == "metin2_map_n_desert_01"
    assert sp.source_point_m == (333.0, 307.0) and len(sp.pieces) == 32
    assert sp.pivot == "centroid"
    assert sum(p.dx for p in sp.pieces) == pytest.approx(0.0, abs=1e-3)
    assert sum(p.dy for p in sp.pieces) == pytest.approx(0.0, abs=1e-3)
    heads = sp.headings()
    assert heads[105.0] == 12 and heads[315.0] == 6 and heads[285.0] == 5
    assert sp.relief_cm() == pytest.approx(58.0, abs=1.0)
    fences = [p.crc for p in sp.pieces if "fence" in p.name.lower()]
    conc, mean, n = setpiece.alignment(sp.pieces, only=fences)
    assert n == 11 and conc > 0.8                        # both rails, linked


def test_stamped_piece_survives_the_pipeline_turned_or_not(source):
    """Build a map with the copied rail, turned 90, and read the records back:
    the panel steps must be the fixture's 520 / 362 / 232 / 238 cm, every roll
    90 more than the source's, and the pivot on the anchor."""
    sp = setpiece.extract(source, (333, 307), 32)
    sp.pieces = [p for p in sp.pieces if p.crc in RAIL_CRCS]
    anchor = (88.0, 108.0)
    spec = make_spec(
        objects=sp.rotated(90.0).stamp(anchor, label="rail"),
        plazas=[PlazaSpec(centre=anchor, radius_m=30.0, tile_index=0, safezone=False)],
    )
    b = pipeline.run(spec)
    recs = [r for r in b.records if r.crc in RAIL_CRCS]
    assert len(recs) == 5
    # order them as the source rail: by the source roll sequence via crc
    order = {crc: i for i, (_, _, _, _, crc) in enumerate(RAIL)}
    recs.sort(key=lambda r: order[r.crc])
    steps = [round(math.hypot(b_.x - a.x, b_.y - a.y))
             for a, b_ in zip(recs, recs[1:])]
    assert steps == [520, 362, 232, 238]
    assert [r.roll for r in recs] == [150.0, 315.0, 300.0, 285.0, 300.0]
    assert all(r.height_bias == -5.0 for r in recs)
    # a 90 turn in the sense of roll (counter-clockwise with north up) sends an
    # offset (dx, dy) to (dy, -dx) in y-down tile terms: east goes north
    src = next(p for p in sp.pieces if p.crc == 1339763610)
    first = recs[0]
    assert first.x / 100.0 == pytest.approx(anchor[0] + src.dy, abs=0.02)
    assert first.terrain_y / 100.0 == pytest.approx(anchor[1] - src.dx, abs=0.02)


# --- from a mapspec ----------------------------------------------------------

def test_yaml_setpieces_expand_into_tiers_and_a_pad():
    """A `setpieces:` entry is all a YAML spec needs: expand() turns it into
    the pattern's tiers about the anchor and a levelling pad on the same point."""
    import json
    from m2map.gen.spec import MapSpec, SetPieceSpec
    try:
        import yaml
    except ImportError:                                   # pragma: no cover
        yaml = None
    spec = make_spec(setpieces=[SetPieceSpec(pattern="desert_camp",
                                            anchor=(120.0, 150.0), rotate_deg=90.0)])
    assert spec.validate() == []
    # survives the spec's own text form
    text = spec.dump()
    data = yaml.safe_load(text) if yaml else json.loads(text)
    back = MapSpec.from_dict(data)
    assert back.setpieces[0].pattern == "desert_camp"
    assert back.setpieces[0].anchor == (120.0, 150.0)
    assert back.setpieces[0].rotate_deg == 90.0

    ex = setpiece.expand(back)
    assert ex.setpieces == [] and back.setpieces           # a copy, not a mutation
    placed = [pos for t_ in ex.objects[len(back.objects):] for pos in t_.positions]
    assert len(placed) == 32
    pattern = setpiece.load(PATTERN).rotated(90.0)
    # the centroid sits on the anchor
    assert sum(x for x, _, _ in placed) / 32 == pytest.approx(120.0, abs=1e-3)
    assert sum(y for _, y, _ in placed) / 32 == pytest.approx(150.0, abs=1e-3)
    assert sorted(r for _, _, r in placed) == sorted(p.roll for p in pattern.pieces)
    pad = ex.plazas[-1]
    assert pad.centre == (120.0, 150.0) and pad.tile_index == 0 and not pad.safezone
    x0, x1, y0, y1 = pattern.extent_m()
    assert pad.radius_m == pytest.approx(max(abs(x0), abs(x1), abs(y0), abs(y1)) + 4.0)
    # and the pipeline does the expansion itself
    b = pipeline.run(back)
    crcs = {p.crc for p in pattern.pieces}
    assert sum(1 for r in b.records if r.crc in crcs) >= 32


def test_yaml_setpieces_are_validated():
    from m2map.gen.spec import SetPieceSpec
    bad = make_spec(setpieces=[SetPieceSpec(pattern="no_such_pattern", anchor=(10.0, 10.0))])
    assert any("not found" in p for p in bad.validate())
    off = make_spec(setpieces=[SetPieceSpec(pattern="desert_camp", anchor=(300.0, 10.0))])
    assert any("outside" in p for p in off.validate())
    nopad = make_spec(setpieces=[SetPieceSpec(pattern="desert_camp", anchor=(120.0, 150.0),
                                             pad_radius_m=0)])
    ex = setpiece.expand(nopad)
    assert len(ex.plazas) == len(nopad.plazas)

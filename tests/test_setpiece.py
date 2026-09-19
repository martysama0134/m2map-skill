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


def test_a_pasted_group_registers_without_a_radius(source, tmp_path):
    """A hand-picked selection IS the group: every record, no disc to argue with.

    The three c1 encampments arrived as `areadata.txt` text copied out of the
    editor. A radius cannot reproduce that -- the east camp's bounding box also
    holds two stray fence panels and a tree the author left out.
    """
    picked = source / "001001" / "areadata.txt"           # rail + tent + FAR
    sp = setpiece.from_areadata(picked, source_map="metin2_map_c1", name="picked")
    assert len(sp.pieces) == 7 and sp.source_map == "metin2_map_c1"
    assert sp.pivot == "centroid"
    assert sum(p.dx for p in sp.pieces) == pytest.approx(0.0, abs=1e-9)
    assert sp.source_point_m == sp.pivot_m                 # there is no query point
    far = max(math.hypot(p.dx, p.dy) for p in sp.pieces)
    assert far <= sp.radius_m < far + 1.0                  # the radius is a description
    assert {p.roll for p in sp.pieces} >= {60.0, 225.0, 105.0}

    out = tmp_path / "picked.json"
    assert setpiece.main(["--from-areadata", str(picked), "--source-map", "metin2_map_c1",
                          "--name", "picked", "--save", str(out)]) == 0
    again = setpiece.load(out)
    assert [(p.crc, p.roll) for p in again.pieces] == [(p.crc, p.roll) for p in sp.pieces]


def test_a_paste_is_checked_against_the_map_it_came_from(source, tmp_path):
    """Same count in the bounding box, same records -- and name what differs.

    Eight pastes were checked this way by hand before it became a function. Seven
    matched exactly; the c1 east camp's box held 71 records against 68 pasted,
    and the three extras (two stray panels, a tree) were the author's choice.
    """
    picked = tmp_path / "picked.txt"
    area = ad.AreaData(records=[
        ad.ObjectRecord(x=x, y=y, z=17826.0, crc=crc, roll=roll, height_bias=bias)
        for x, y, roll, bias, crc in RAIL[:2] + RAIL[3:]])          # panel 3 left out
    area.declared_count = len(area.records)
    picked.write_bytes(area.to_bytes())

    rep = setpiece.verify_against(picked, source)
    assert rep["pasted"] == 4 and rep["in_bbox"] == 5
    assert rep["missing_from_map"] == []                 # every pasted record exists
    assert [(r["crc"], r["roll"]) for r in rep["left_out"]] == [(RAIL[2][4], RAIL[2][2])]
    assert not rep["exact"]

    # a record that is NOT on the map is the serious case: a typo, or the wrong map
    area.records[0].roll = 61.0
    picked.write_bytes(area.to_bytes())
    rep = setpiece.verify_against(picked, source)
    assert len(rep["missing_from_map"]) == 1 and rep["missing_from_map"][0]["roll"] == 61.0


def test_a_shore_pattern_hangs_from_the_water_not_the_ground(source, tmp_path):
    """Rafts, piers and fish huts are fitted to the WATER SURFACE.

    The a1 fishing bays: three raft decks within -32..+50 cm of the river's
    15,305 cm while the sand under them is 1.0-1.4 m down, a hut +120 on dry
    sand, a pier +300 running 32 m out. Their stored biases (+60..+220) are
    whatever made that true on that shore; on another shore they are wrong.
    """
    sp = setpiece.extract(source, (333, 307), 32, exclude=["1099929426"])
    sp.water_cm = 17826.0 - 5.0 - 100.0          # source ground 17826, bias -5 => decks 100 over water
    path = sp.save(tmp_path / "rafts.json")
    assert setpiece.load(path).water_cm == sp.water_cm

    from m2map.gen.spec import SetPieceSpec
    spec = make_spec(plazas=[], objects=[], height_range_cm=(16000.0, 19000.0))
    spec.setpieces = [SetPieceSpec(pattern=str(path), anchor=(128.0, 60.0), water_cm=16400.0)]
    b = pipeline.run(spec)
    rail = [r for r in b.records if r.crc in RAIL_CRCS]
    assert len(rail) == 5
    for r in rail:
        assert r.z + r.height_bias == pytest.approx(16400.0 + 100.0, abs=1.0)
    # no levelling pad was added for it: a pad would flatten the shore it stands on
    assert not [p for p in b.layout.plazas if abs(p.centre[0] - 128.0) < 1 and abs(p.centre[1] - 60.0) < 1]


# --- the ground under a compound ------------------------------------------
#
# A pattern is records only, and half of what makes a camp read is paint: the
# three c1 encampments each stand on a solid `field 01` core with a `field 04`
# halo, and a disc of road dirt was only an approximation of that.

DIRT = "d:/ymir work/terrainmaps/b/field/field 03.dds"      # a slot make_spec() has
GRASS = "d:/ymir work/terrainmaps/b/grass/grass 01.dds"


def _paint_source(map_dir: pathlib.Path):
    """Give the fake map a palette and a dirt blob east of the rail."""
    import numpy as np
    (map_dir / "setting.txt").write_text(
        "ScriptType\tMapSetting\nTextureSet\ttextureset\\fake.txt\n", encoding="ascii")
    ts = map_dir / "textureset"
    ts.mkdir(exist_ok=True)
    block = ("Start Texture%03d\n    \"%s\"\n    4.0\n    4.0\n    0.0\n    0.0\n"
             "    0\n    0\n    0\nEnd Texture%03d\n")
    (ts / "fake.txt").write_text(
        "TextureSet\n\nTextureCount 2\n\n" + block % (1, GRASS.replace("/", "\\"), 1)
        + block % (2, DIRT.replace("/", "\\"), 2), encoding="ascii")
    grid = np.ones((258, 258), np.uint8)
    # sector (1,1): local tile = metres - 256. The rail's centroid is near
    # (319, 300); paint 320..339 x 296..305 -- a bar reaching EAST of it.
    grid[1 + 296 - 256:1 + 306 - 256, 1 + 320 - 256:1 + 340 - 256] = 2
    (map_dir / "001001" / "tile.raw").write_bytes(grid.tobytes())


def test_ground_is_read_by_texture_path_and_turns_with_the_block(source):
    _paint_source(source)
    sp = setpiece.extract(source, (333, 307), 32, exclude=["1099929426"])
    sp = setpiece.with_ground(sp, source, keep=["field"], margin_m=20)
    g = sp.ground
    assert g is not None and g.palette == [DIRT]          # grass is not kept; paths, not indices
    cells = g.cells()
    assert len(cells) == 200                              # 20 x 10 tiles
    assert min(dx for dx, _dy, _p in cells) > 0           # the bar lies east of the pivot...
    turned = sp.rotated(90.0).ground.cells()
    assert 190 <= len(turned) <= 210                      # nearest-neighbour, area kept
    assert max(dy for _dx, dy, _p in turned) < 0          # ...and north of it after +90 of roll
    # and it survives the JSON
    again = setpiece.SetPiece.from_dict(sp.to_dict())
    assert again.ground.rows == g.rows and again.ground.palette == g.palette
    assert again.ground.origin_m == pytest.approx(g.origin_m, abs=1e-4)


def test_stamped_ground_paints_the_matching_slot_and_only_that(source, tmp_path):
    import numpy as np
    _paint_source(source)
    sp = setpiece.with_ground(
        setpiece.extract(source, (333, 307), 32, exclude=["1099929426"]),
        source, keep=["field"], margin_m=20)
    path = sp.save(tmp_path / "bar.json")
    spec = make_spec(water=[], plazas=[], objects=[])
    from m2map.gen.spec import SetPieceSpec
    spec.setpieces = [SetPieceSpec(pattern=str(path), anchor=(128.0, 190.0))]
    b = pipeline.run(spec)
    slot = [i for i, t in enumerate(spec.textures, 1) if t.path == DIRT][0]
    dx, dy, _p = sp.ground.cells()[0]
    assert b.tiles[int(190.0 + dy), int(128.0 + dx)] == slot
    painted = sum(b.tiles[int(190.0 + y), int(128.0 + x)] == slot for x, y, _ in sp.ground.cells())
    assert painted == 200
    assert any("ground" in line for line in b.log)

    spec.setpieces = [SetPieceSpec(pattern=str(path), anchor=(128.0, 190.0), ground=False)]
    off = pipeline.run(spec)
    assert sum(off.tiles[int(190.0 + y), int(128.0 + x)] == slot
               for x, y, _ in sp.ground.cells()) < 120

    # a palette without the texture paints nothing and says so
    spec.setpieces = [SetPieceSpec(pattern=str(path), anchor=(128.0, 190.0))]
    spec.textures = [t for t in spec.textures if t.path != DIRT]
    spec.plazas = []
    for r in spec.roads:
        r.tile_index = 1
    lost = pipeline.run(spec)
    assert any("no slot for" in line and "field 03" in line for line in lost.log)


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

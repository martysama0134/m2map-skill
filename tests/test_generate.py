"""End-to-end generation: spec -> map on disk -> reads back -> audits clean.

These are the tests that would catch a regression in the engine, and they are
deliberately whole-pipeline rather than per-stage: almost every bug found while
building it was an *interaction* (attr running before objects, the texture stage
getting an unrasterised water mask, sector splitting forgetting to de-negate Y),
and a per-stage unit test sees none of those.

A 1x1 map keeps this fast enough to run on every commit.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "skills" / "m2map" / "scripts"))

from m2map.audit import rules                                    # noqa: E402
from m2map.codec import areadata, attr, height, server_attr, textureset, tile  # noqa: E402
from m2map.gen import pipeline                                   # noqa: E402
from m2map.gen.spec import (MapSpec, ObjectTier, RegionSpec,     # noqa: E402
                            RoadSpec, SpecError, TextureSlot, WaterSpec)


def make_spec(**over) -> MapSpec:
    spec = MapSpec(
        name="metin2_map_pytest",
        archetype="field_empire",
        size=(1, 1),
        seed=4242,
        base_position=(25600, 51200),
        environment="a1.msenv",
        textureset_name="metin2_pytest",
        textures=[
            TextureSlot("d:/ymir work/terrainmaps/b/field/field 01.dds", role="path"),
            TextureSlot("d:/ymir work/terrainmaps/b/grass/grass 01.dds", role="base", weight=0.55),
            TextureSlot("d:/ymir work/terrainmaps/b/field/field 03.dds", role="mid", weight=0.30),
            TextureSlot("d:/ymir work/terrainmaps/b/stone/stone01.dds", role="cliff", weight=0.15),
        ],
        roads=[RoadSpec(waypoints=[(30, 0), (120, 120), (200, 255)], width_m=6.0,
                        tile_index=1)],
        water=[WaterSpec(waypoints=[(0, 190), (120, 200), (255, 210)], width_m=14.0)],
        regions=[RegionSpec(kind="settlement",
                            polygon=[(150, 20), (240, 20), (240, 90), (150, 90)],
                            flatten=True)],
        objects=[ObjectTier(crc=1288452050, name="tree", tier="filler",
                            density=0.25, spacing_cm=1100, max_slope=22,
                            road_clearance_cm=1200, height_bias=(-20.0, 0.0))],
        height_range_cm=(0.0, 3000.0),
        slope_p50=4.5, slope_p95=23.0, flat_fraction=0.40,
        attr_style="slope_driven", block_slope_deg=20.0, border_band_m=4,
        safezone_regions=["settlement"],
    )
    for k, v in over.items():
        setattr(spec, k, v)
    return spec


@pytest.fixture(scope="module")
def built():
    return pipeline.run(make_spec())


@pytest.fixture(scope="module")
def written(built, tmp_path_factory):
    out = tmp_path_factory.mktemp("map") / "metin2_map_pytest"
    pipeline.write(built, out)
    return out


# --- the spec is a contract, not a suggestion -----------------------------

def test_valid_spec_reports_no_problems():
    assert make_spec().validate() == []


@pytest.mark.parametrize("field,value,fragment", [
    ("size", (0, 4), "outside 1..256"),
    ("textures", [], "error texture"),
    ("height_range_cm", (100.0, 50.0), "not increasing"),
    ("height_range_cm", (0.0, 99999.0), "uint16 ceiling"),
    ("style", "nonsense", "sculpted"),
    ("attr_style", "nonsense", "slope_driven"),
    ("base_position", (12345, 0), "multiple of"),
])
def test_bad_spec_is_caught_before_building(field, value, fragment):
    spec = make_spec(**{field: value})
    problems = " ".join(spec.validate())
    assert fragment in problems, problems
    if fragment != "multiple of":                     # that one is only a warning
        with pytest.raises(SpecError):
            spec.require_valid()


def test_seed_is_deterministic():
    a, b = pipeline.run(make_spec()), pipeline.run(make_spec())
    assert np.array_equal(a.tiles, b.tiles)
    assert np.array_equal(a.attr_cells, b.attr_cells)
    assert len(a.records) == len(b.records)
    assert [r.crc for r in a.records] == [r.crc for r in b.records]


def test_different_seeds_differ():
    a = pipeline.run(make_spec(seed=1))
    b = pipeline.run(make_spec(seed=2))
    assert not np.array_equal(a.tiles, b.tiles)


# --- the measured targets the archetypes are written against --------------

def test_terrain_hits_the_requested_flat_fraction(built):
    from m2map.gen import terrain
    got = float((terrain.slope_degrees(built.height_cm) < 2.0).mean())
    assert abs(got - built.spec.flat_fraction) < 0.12, (
        "flat fraction %.2f vs requested %.2f -- terrain shaping regressed"
        % (got, built.spec.flat_fraction))


def test_splat_is_a_stipple_not_regions(built):
    from m2map.gen import texture
    st = texture.stipple_stats(built.tiles)
    # Corpus: median run length 2, base share median 0.52. A run length of 1 is
    # uniform white noise; 4+ is region fill. Both look obviously wrong in game.
    assert 1.5 <= st["run_length_median"] <= 3.5, st
    assert st["base_share"] <= 0.72, st
    assert st["used_slots"] >= 3, st


def test_headings_follow_the_measured_grammar(built):
    from m2map.gen import objects
    s = objects.stats(built.records)
    assert s["count"] > 0
    assert s["roll_snap_15_share"] == 1.0, "rolls must snap to 15 degrees"
    assert s["yaw_nonzero_share"] == 0.0, "yaw is a tilt channel, not the heading"
    assert s["all_y_negative"], "areadata Y must be stored negated"


def test_objects_avoid_road_and_water(built):
    lay = built.layout
    for rec in built.records:
        tx, ty = int(rec.x / 100.0), int(-rec.y / 100.0)
        tx = min(max(tx, 0), lay.shape[1] - 1)
        ty = min(max(ty, 0), lay.shape[0] - 1)
        assert not lay.road_mask[ty, tx], "object placed on the road surface"
        assert not built.submerged[ty, tx], "object placed in water"


def test_attr_blocks_steep_ground_and_clears_the_road(built):
    from m2map.codec import attr as ac
    blocked = (built.attr_cells & ac.ATTR_BLOCK).astype(bool)

    # The border band is sealed on purpose and a road may run into it, so the
    # corridor is only required to be walkable inside the map proper.
    b = built.spec.border_band_m
    interior = np.zeros_like(blocked)
    interior[b:-b, b:-b] = True
    road = built.layout.road_mask & interior

    assert not blocked[road].any(), (
        "the road corridor must stay walkable -- including where it crosses "
        "water, which is a ford (Ymir paints 0xCA: bridge, walkable)")
    assert 0.02 < blocked.mean() < 0.75, blocked.mean()


def test_a_ford_keeps_its_water_flag(built):
    """Clearing BLOCK on a crossing must not also clear WATER."""
    from m2map.codec import attr as ac
    crossing = built.layout.road_mask & built.submerged
    if not crossing.any():
        pytest.skip("this seed's road does not cross the water")
    cells = built.attr_cells
    assert not (cells[crossing] & ac.ATTR_BLOCK).any(), "ford is blocked"
    assert (cells[crossing] & ac.ATTR_WATER).all(), "ford lost its water flag"


def test_water_is_continuous_not_puddles(built):
    """A single flat plane over a sloping bed leaves the river mostly dry."""
    assert len(built.water_heights) >= 1
    wet_cells = int(built.wet.sum())
    assert wet_cells > 0
    assert built.submerged.sum() > wet_cells * 0.5, (
        "less than half the water body is actually submerged -- the surface "
        "levelling regressed and the river will render as disconnected puddles")


# --- what lands on disk ---------------------------------------------------

FIXED = {"height.raw": 34322, "tile.raw": 66564, "attr.atr": 65542,
         "shadowmap.raw": 131072}


def test_every_fixed_size_file_is_exact(written):
    sectors = [p for p in written.iterdir() if p.is_dir() and p.name.isdigit()]
    assert sectors
    for sec in sectors:
        for name, want in FIXED.items():
            f = sec / name
            assert f.exists(), "%s missing" % f
            assert f.stat().st_size == want, "%s is %d, want %d" % (f, f.stat().st_size, want)


def test_every_sector_has_areaproperty(written):
    """areaproperty.txt DEFINES the sector -- without it the sector vanishes."""
    for sec in [p for p in written.iterdir() if p.is_dir() and p.name.isdigit()]:
        assert (sec / "areaproperty.txt").exists()


def test_tile_indices_are_within_the_palette(written):
    ts = textureset.TextureSet.load(written / "textureset" / "metin2_pytest.txt")
    for sec in [p for p in written.iterdir() if p.is_dir() and p.name.isdigit()]:
        tm = tile.read_tile(sec / "tile.raw")
        assert max(tm.used_indices()) <= ts.declared_count


def test_server_attr_never_carries_paint_bits(written):
    sa = server_attr.read_server_attr(written / "server_attr")
    ok, bad = sa.verify()
    assert not bad
    worst = max(int(sa.block(x, y).max())
                for y in range(sa.height) for x in range(sa.width))
    assert worst <= 0x07, (
        "server_attr max %d -- anything above 0x07 blocks the whole map on the "
        "server (see codec/server_attr.py)" % worst)


def test_written_files_round_trip(written):
    sec = next(p for p in written.iterdir() if p.is_dir() and p.name.isdigit())
    a = areadata.AreaData.load(sec / "areadata.txt")
    assert a.to_bytes() == (sec / "areadata.txt").read_bytes()
    assert a.problems() == []
    ts_path = written / "textureset" / "metin2_pytest.txt"
    assert textureset.TextureSet.load(ts_path).to_bytes() == ts_path.read_bytes()


def test_generated_map_audits_clean(written):
    findings = rules.audit(written, textureset_dir=written / "textureset")
    serious = [f for f in findings if f.severity in ("blocker", "major")]
    assert not serious, "\n".join(str(f) for f in serious)


def test_mapspec_is_written_beside_the_map(written):
    """Without it the build is not reproducible and improve cannot diff."""
    assert (written / "mapspec.yaml").exists()
    reloaded = MapSpec.load(written / "mapspec.yaml")
    assert reloaded.seed == 4242
    assert reloaded.validate() == []


# --- box style ------------------------------------------------------------

def test_box_style_produces_a_flat_interior():
    spec = make_spec(style="box", attr_style="painted_box", water=[])
    b = pipeline.run(spec)
    assert float(b.height_cm.std()) == 0.0, "a box interior must be a flat plane"
    assert len(np.unique(b.tiles)) == 1, "interiors use a single floor texture"
    from m2map.codec import attr as ac
    blocked = (b.attr_cells & ac.ATTR_BLOCK).astype(bool)
    assert blocked.mean() > 0.3, "painted_box paints, then carves"
    assert not blocked.all(), "a fully blocked interior cannot be entered"


# --- naming: convention, not requirement ---------------------------------

@pytest.mark.parametrize("name", [
    "map_a2",              # shipped, and the server_attr ground-truth file
    "gm_guild_build",      # shipped
    "map_b_fielddungeon",  # shipped
    "map_n_snowm_01",      # shipped
    "map_n_threeway",      # shipped
    "metin2_map_a1",       # the common form
    "map_skill_test_01",
])
def test_map_names_without_the_metin2_prefix_are_valid(name):
    """5 of 142 shipped maps have no `metin2_` prefix. It is a convention.

    An earlier validator rejected these outright, which would have refused to
    build a map named after one of the corpus's own files.
    """
    spec = make_spec(name=name)
    assert [p for p in spec.validate() if "name" in p] == []
    spec.require_valid()


@pytest.mark.parametrize("name", [
    "bad name", "bad/name", "bad\\name", "a:b", "", "trailing\n", "tab\there",
])
def test_names_that_break_a_folder_or_index_are_rejected(name):
    spec = make_spec(name=name)
    assert [p for p in spec.validate() if "name" in p]

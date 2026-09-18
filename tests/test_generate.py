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
from m2map.gen import texture as texture_stage                  # noqa: E402
from m2map.gen.spec import (MapSpec, ObjectTier, PlazaSpec,      # noqa: E402
                            RegionSpec, RoadSpec, SpecError, TextureSlot,
                            WaterSpec)


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
            # TWO mids, deliberately. A corpus palette uses a median of 7 slots
            # and the run-length statistic below is a property of several mids
            # interleaving. With the base painted as a carpet and the cliff as a
            # region, a single-mid palette has nothing left to dither and
            # measures a run length of 7 -- correct for that palette, and not
            # representative of anything Ymir shipped.
            TextureSlot("d:/ymir work/terrainmaps/b/field/field 03.dds", role="mid", weight=0.18),
            TextureSlot("d:/ymir work/terrainmaps/b/grass/grass 02.dds", role="mid", weight=0.14),
            TextureSlot("d:/ymir work/terrainmaps/b/stone/stone01.dds", role="cliff", weight=0.15),
            TextureSlot("d:/ymir work/terrainmaps/b/tile/tile01.dds", role="path"),
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
        plazas=[PlazaSpec(centre=(195.0, 55.0), radius_m=18.0, tile_index=6)],
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


def test_stream_seeds_are_stable_across_processes():
    """The mapspec promises reproducibility from (spec, seed). It must hold.

    Python salts the hash of str/bytes per process, so `hash(("terrain", seed))`
    returns a different value in every run. The generator used that, which made
    every map irreproducible across processes while looking perfectly
    deterministic inside one -- exactly what test_seed_is_deterministic below
    checks, which is why it never caught it. Measured before the fix: one spec
    built in three processes gave three different maps.

    These constants are the point of the test. If someone reintroduces hash(),
    they change per run and this fails.
    """
    from m2map.gen.spec import stream_seed
    assert stream_seed("terrain", 4242) == 162036731
    assert stream_seed("texture", 4242) == stream_seed("texture", 4242)
    assert stream_seed("terrain", 4242) != stream_seed("texture", 4242)
    assert stream_seed("terrain", 1) != stream_seed("terrain", 2)


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


# --- server spawns --------------------------------------------------------
#
# The rule that matters is walkability: a zone on blocked ground spawns monsters
# inside terrain, unreachable, and nothing in the client or server warns you.

def test_spawns_land_on_walkable_ground(built):
    from m2map.gen import spawns
    sets = spawns.place(built.spec, built.layout, built.attr_cells,
                        monsters=[(101, 5), (102, 4)], npcs=[9001],
                        bosses=[2001], stones=[(8001, 2)])
    assert sum(len(v) for v in sets.values()) > 0
    problems = []
    for zs in sets.values():
        problems += spawns.audit_zones(zs, built.attr_cells, built.spec)
    assert problems == [], problems


def test_npcs_prefer_the_settlement(built):
    from m2map.gen import spawns
    settlement = built.layout.regions.get("settlement")
    if settlement is None or not settlement.any():
        pytest.skip("no settlement region in the fixture spec")
    sets = spawns.place(built.spec, built.layout, built.attr_cells,
                        npcs=[9001, 9002, 9003])
    assert sets["npc"], "no NPC placed"
    for z in sets["npc"]:
        assert settlement[int(z.cy), int(z.cx)], (
            "NPC at (%.0f, %.0f) is outside the settlement" % (z.cx, z.cy))


def test_monsters_keep_off_the_road_corridor(built):
    from m2map.gen import spawns
    if not built.layout.corridors:
        pytest.skip("no road in the fixture spec")
    sets = spawns.place(built.spec, built.layout, built.attr_cells,
                        monsters=[(101, 5), (102, 5), (103, 5)])
    for z in sets["regen"]:
        assert built.layout.road_distance[int(z.cy), int(z.cx)] > 12.0, (
            "monster zone sits on the only route through the map")


def test_regen_coordinates_are_tiles_not_centimetres(built):
    """regen is in units of 100 -- metres. Not cm, and NOT negated."""
    from m2map.gen import spawns
    sets = spawns.place(built.spec, built.layout, built.attr_cells,
                        monsters=[(101, 3)])
    rf = spawns.to_regen_file(sets["regen"])
    h, w = built.layout.shape
    for row in rf.rows:
        assert 0 <= row.cx < w and 0 <= row.cy < h, (
            "regen coordinate %r looks like centimetres or a negated Y"
            % ((row.cx, row.cy),))


def test_regen_file_round_trips_and_derives_monsterarrange(built, tmp_path):
    from m2map.codec import regen as rc
    from m2map.gen import spawns
    sets = spawns.place(built.spec, built.layout, built.attr_cells,
                        monsters=[(101, 5)], npcs=[9001], bosses=[2001],
                        stones=[(8001, 1)])
    written = spawns.write(tmp_path, sets)
    assert "monsterarrange.txt" in written
    rf = rc.RegenFile.load(tmp_path / "regen.txt")
    assert rf.to_bytes() == (tmp_path / "regen.txt").read_bytes()
    assert rf.problems() == []
    ma = rc.MonsterArrange.load(tmp_path / "monsterarrange.txt")
    assert 101 in ma.vnums and 9001 in ma.vnums and 2001 in ma.vnums


# --- unit boundaries at the write edge ------------------------------------
#
# The in-memory model can be right while the FILE is wrong, which is exactly
# what happened: water surfaces were written in centimetres into a field the
# format defines in raw units, so every plane landed at half its altitude --
# reliably below the terrain. The pipeline reported 7.2% submerged, the file
# contained 0%, and nothing caught it until the map was opened in WorldEditor
# and had no water in it.

def test_written_water_matches_the_in_memory_model(built, written):
    """water.wtr stores RAW units (worldZ = value * HeightScale), not cm."""
    import numpy as np
    from m2map.codec import height as hc
    from m2map.codec import water as wc

    sectors = [p for p in written.iterdir() if p.is_dir() and p.name.isdigit()]
    total_sub = 0
    for sec in sectors:
        wm = wc.read_water(sec / "water.wtr")
        hm = hc.read_height(sec / "height.raw")
        surfaces = list(wm.world_heights())
        if not surfaces:
            continue
        terrain = hm.raw[1:129, 1:129].astype(float) * 0.5
        sub = np.zeros(wm.cells.shape, bool)
        for i, s in enumerate(surfaces):
            m = wm.cells == i
            if m.any():
                sub |= m & (float(s) > terrain)
        total_sub += int(sub.sum())

    expected = int(built.submerged.sum()) // 4      # tile mask -> 2 m cells
    assert total_sub > 0, (
        "no submerged cell survived the write -- water heights are probably in "
        "centimetres where the format wants raw units (factor of 1/HeightScale)")
    assert total_sub >= expected * 0.5, (
        "written submerged area %d is far below the in-memory %d"
        % (total_sub, expected))


def test_water_surfaces_are_plausible_against_terrain(written):
    """A plane far below every terrain cell it covers is invisible in game."""
    import numpy as np
    from m2map.codec import height as hc
    from m2map.codec import water as wc

    for sec in [p for p in written.iterdir() if p.is_dir() and p.name.isdigit()]:
        wm = wc.read_water(sec / "water.wtr")
        surfaces = list(wm.world_heights())
        if not surfaces:
            continue
        terrain = hc.read_height(sec / "height.raw").raw[1:129, 1:129].astype(float) * 0.5
        lo, hi = float(terrain.min()), float(terrain.max())
        for i, s in enumerate(surfaces):
            if not (wm.cells == i).any():
                continue
            assert lo - 5000 <= float(s) <= hi + 5000, (
                "water layer %d at %.0f cm against terrain %.0f..%.0f -- off by "
                "a unit conversion?" % (i, s, lo, hi))


# what happened: a two-level oasis -- an upper basin on a shelf, a lower pool at
# the foot of the wall. The lower pool's plane runs past its shore by design, the
# shelf is higher than the lower surface so the depth clip keeps it, and the
# lower plane was written second: it took every cell of the upper basin. On disk
# the upper basin was 0 submerged cells of 97, under a waterfall anchored "in the
# upper water". Both map_skill_test_04 and _05 shipped that way; the 2D previews
# and the audit passed.

def test_an_overrun_never_takes_another_basin():
    """A plane's overrun is for its own beach, not for a neighbour's bowl."""
    from types import SimpleNamespace
    from m2map.gen import water as water_stage

    spec = make_spec()
    height_cm = np.full((128, 128), 16000.0)
    height_cm[:, 70:] = 17300.0                      # the shelf, east
    height_cm[40:80, 30:66] = 15600.0                # the lower bowl, west
    upper = np.zeros((256, 256), bool)
    upper[100:140, 150:180] = True                   # tiles; cells 50-70 x 75-90
    lower = np.zeros((256, 256), bool)
    lower[84:156, 64:128] = True
    lay = SimpleNamespace(shape=(256, 256), water_masks=[upper, lower],
                          water_surfaces=[17472.0, None],
                          lake_mask=upper | lower, water_lines=[None, None])

    cells, heights, _wet, _sub = water_stage.build(spec, lay, height_cm)

    basin = cells[50:70, 75:90]
    assert heights[0] == 17472.0
    assert (basin == 0).all(), (
        "%d of %d upper-basin cells belong to another layer -- a later plane's "
        "overrun overwrote the authored basin" % ((basin != 0).sum(), basin.size))
    assert (heights[0] > height_cm[50:70, 75:90]).all()


# --- border occlusion -----------------------------------------------------
#
# Outdoor maps wall their edges so the player cannot see past the world
# (measured outdoor median +1,351 cm over the outer 64 m); interiors measure
# exactly 0 and occlude with fog instead.

def test_border_ridge_walls_every_edge_including_corners():
    from m2map.gen.terrain import border_ridge
    r = border_ridge((129, 129), 4000.0, 64.0)
    mid_edge = float(r[0, 64])
    corner = float(r[0, 0])
    centre = float(r[64, 64])
    assert centre < 1.0, "the rim must not lift the playable interior"
    assert mid_edge > 3000.0, "mid-edge is not walled"
    # max-of-ramps, not sum: a sum peaks at corners and sags mid-edge, leaving a
    # notch the player can see through.
    assert abs(mid_edge - corner) < 1.0, (
        "corner %.0f vs mid-edge %.0f -- uneven rim leaves a gap" % (corner, mid_edge))


def test_border_ridge_opens_where_water_leaves_the_map():
    """A rim across a river's exit makes the river climb the mountain."""
    import numpy as np
    from m2map.gen.terrain import border_ridge
    gap = np.zeros((129, 129))
    gap[62:67, :] = 1.0                       # a channel crossing both edges
    r = border_ridge((129, 129), 4000.0, 64.0, gap=gap)
    assert float(r[64, 0]) < 1.0, "no gorge: the rim blocks the watercourse"
    assert float(r[0, 64]) > 3000.0, "the gorge removed the rest of the wall too"


def test_ridge_statistics_must_be_read_on_the_interior():
    """Archetype slope targets describe ground the player stands on.

    The rim is a ~41 degree wall by design, so including it makes the whole-map
    figures look like a broken generator: measured, it moved slope p50 from 4.1
    to 16.0 and the flat fraction from 37% to 6%. The interior will not match
    the target exactly either -- the target was fitted across the whole grid,
    and trimming the rim also removes the map's own natural edge relief -- so
    the invariant that matters is that the interior is markedly CLOSER.
    """
    from m2map.gen import terrain
    walled = make_spec(border_ridge_cm=3500.0, border_ridge_width_m=40.0)
    b = pipeline.run(walled)
    m = int(walled.border_ridge_width_m / 2.0) + 2
    inner = b.height_cm[m:-m, m:-m]

    target = walled.flat_fraction
    whole = float((terrain.slope_degrees(b.height_cm) < 2.0).mean())
    interior = float((terrain.slope_degrees(inner) < 2.0).mean())

    assert abs(interior - target) < abs(whole - target), (
        "interior %.2f is no closer to the target %.2f than the whole map %.2f "
        "-- the rim is not being excluded" % (interior, target, whole))
    assert abs(interior - target) < 0.20, (
        "interior flat fraction %.2f vs requested %.2f" % (interior, target))


def test_box_style_never_gets_a_ridge():
    """Interiors measure exactly 0 ring lift; they use fog."""
    import numpy as np
    spec = make_spec(style="box", attr_style="painted_box", water=[],
                     border_ridge_cm=0.0)
    b = pipeline.run(spec)
    assert float(b.height_cm.std()) == 0.0


# --- ground painting conventions (reference/textures.md sec 4f-4k) --------
#
# Every rule below was measured on the corpus before it was coded; the numbers
# quoted in the assertions are the corpus figures, and the tolerances are wide
# enough that only a real regression trips them.


@pytest.mark.parametrize("path,expect", [
    ("d:/ymir work/terrainmaps/b/field/field 01.dds", "field"),
    ("d:/ymir work/terrainmaps/a/beach/beach sand 01.dds", "sand"),
    ("d:/ymir work/terrainmaps/n/desert/sand/sand01.dds", "sand"),
    ("d:/ymir work/terrainmaps/b/stone/stone02.dds", "stone"),
    ("d:/ymir work/terrainmaps/b/tile/tile01.dds", "tile"),
    ("capedragonhead/capedragon_cliff002.dds", "cliff"),
    ("d:/ymir work/terrainmaps/b/grass/grass 01.dds", "grass"),
    ("something_unrecognised.dds", ""),
])
def test_motif_reads_the_ymir_naming_convention(path, expect):
    """`beach sand` must beat `sand`, and an unknown name must stay unknown.

    The motif is only ever a prior -- it picks a road's dither partner and
    nothing else -- but a wrong answer here silently pairs a road with a cliff.
    """
    assert texture_stage.motif_of(path) == expect


def test_road_rim_dithers_with_a_sibling_of_its_own_motif(built):
    """map_a2 paints `field 01` and enriches `field 02` at the rim 23.9x.

    The reference palette is slot 1 `field 01` (the road) and slot 3
    `field 03`, so the partner must resolve to 3 -- not to the grass base, and
    not to the stone cliff, which the corpus DEPLETES at the rim (0.52x).
    """
    spec = make_spec()
    assert texture_stage._fringe_partner(spec, 1) == 3

    tiles = built.tiles
    rim = np.zeros(tiles.shape, bool)
    for corr in built.layout.corridors:
        rim |= corr.fringe & ~corr.core
    assert rim.any()
    on_rim = tiles[rim]
    # Both the road surface and its sibling live in the blend band.
    assert (on_rim == 1).sum() > 0, "no road colour in the rim"
    assert (on_rim == 3).sum() > 0, "no motif sibling in the rim"
    # ...and the cliff slot is not what the rim is made of.
    assert (on_rim == 4).mean() < (tiles == 4).mean() + 0.05


def test_cliff_is_a_solid_skin_not_a_dither(built):
    """massif / raw over the corpus: 0.86 (mt_thunder) to 0.99 (n_desert_01).

    `taste.md` §1.5 -- ground is a per-tile stipple, not region fill -- is a
    statement about GROUND. The cliff is the exception, and sampling it per tile
    like the ground gave a ratio of **0.02**: rock as pepper, no rock face
    anywhere on the map. That is the most visible possible error in a landscape
    screenshot and every automated check passed while it was true.
    """
    tiles = built.tiles
    mask = tiles == 5                                     # the cliff slot
    assert mask.any(), "no cliff painted at all"
    massif = texture_stage._dilate(texture_stage._erode(mask, 2), 2)
    ratio = massif.sum() / float(mask.sum())
    assert ratio >= 0.85, \
        "cliff survives opening at %.2f -- the corpus measures 0.86-0.99" % ratio


def test_cliff_share_rises_with_slope(built):
    """P(cliff | slope) is monotone in the corpus: a1 7% at 0-5 deg, 92% at 60+.

    Where the ramp turns is a per-map decision (n_desert_01 is still at 12% by
    15-20 deg where a1 is at 34%), so this only asserts the direction.
    """
    tiles, slope = built.tiles, built.slope_deg
    h, w = slope.shape
    ys, xs = np.mgrid[:tiles.shape[0], :tiles.shape[1]]
    sl = slope[np.clip(ys // 2, 0, h - 1), np.clip(xs // 2, 0, w - 1)]
    mask = tiles == 5
    bands = [(0, 10), (10, 20), (20, 30), (30, 90)]
    shares = []
    for lo, hi in bands:
        sel = (sl >= lo) & (sl < hi)
        if sel.sum() > 500:
            shares.append(float(mask[sel].mean()))
    assert len(shares) >= 3, "not enough slope range to measure"
    assert shares[-1] > shares[0], \
        "cliff share does not rise with slope: %r" % [round(x, 3) for x in shares]


def test_rock_feathers_out_of_the_massif_and_then_stops(built):
    """Corpus tail: a1 9.6 -> 6.8 -> 3.6 -> 2.1 -> 1.3 -> 0.9%, far field 0.00%.

    Both halves are the rule. A generator that only reproduces the decay and
    keeps sprinkling rock across open ground turns the map into gravel.
    """
    tiles = built.tiles
    cliff = 5
    mask = tiles == cliff
    if not mask.any():
        pytest.skip("no cliff painted on this seed")
    massif = texture_stage._dilate(texture_stage._erode(mask, 2), 2)
    if not massif.any():
        pytest.skip("no massif survives opening on this seed")

    shares, prev = [], massif
    for step in range(1, 7):
        cur = texture_stage._dilate(massif, step)
        ring = cur & ~prev
        prev = cur
        if ring.sum() < 50:
            break
        shares.append(float(mask[ring].mean()))

    assert len(shares) >= 4, "no measurable rim"
    assert shares[0] > 0.01, "no feather at all: rock stops at a hard line"
    # Monotone-ish decay -- allow one non-decreasing step, as metin2_map_b1 has
    # one (16.2 -> 16.4) in the corpus.
    rises = sum(1 for a, b in zip(shares, shares[1:]) if b > a + 1e-9)
    assert rises <= 1, "feather does not decay: %r" % shares
    assert shares[-1] < shares[0], "feather does not thin: %r" % shares

    far = ~texture_stage._dilate(massif, 20)
    if far.sum() > 500:
        assert float(mask[far].mean()) < 0.02, \
            "rock is sprinkled over the far field; the corpus measures 0.00%"


def test_plaza_is_painted_unmixed(built):
    """Corpus discs measure solid 0.84-0.87; a road in the same palette 0.36-0.56.

    The plaza is the one place on an outdoor map where the stipple is off, and
    that is what makes it read as built rather than grown.
    """
    tiles = built.tiles
    assert built.layout.plazas, "the reference spec declares a plaza"
    pz = built.layout.plazas[0]
    inside = tiles[pz.mask]
    assert (inside == pz.tile_index).all(), \
        "plaza is dithered: %d of %d tiles are not the plaza slot" % (
            int((inside != pz.tile_index).sum()), inside.size)
    # And it does not leak: the slot must not appear as field noise.
    assert (tiles == pz.tile_index).sum() == int(pz.mask.sum())


def test_plaza_disc_is_circular_and_the_right_size(built):
    """fill = area / bbox: pi/4 = 0.785 for a circle, 1.0 for a square."""
    pz = built.layout.plazas[0]
    ys, xs = np.nonzero(pz.mask)
    bh = ys.max() - ys.min() + 1
    bw = xs.max() - xs.min() + 1
    fill = pz.mask.sum() / float(bh * bw)
    aspect = max(bh, bw) / float(min(bh, bw))
    assert 0.70 <= fill <= 0.85, "fill %.3f outside the corpus band" % fill
    assert aspect <= 1.10, "aspect %.3f -- not a disc" % aspect
    radius = np.sqrt(pz.mask.sum() / np.pi)
    assert 8.0 <= radius <= 25.0, "radius %.1f m outside the shipped 8-25 m" % radius


def test_plaza_is_safe_and_walkable(built):
    """Corpus: 100% ATTR_SAFEZONE inside the disc against a 0.2% baseline.

    Cleared of block too -- unlike a safe-zone REGION, which overlaps block in
    72% of the corpus's safe cells because it is painted over a whole town.
    """
    pz = built.layout.plazas[0]
    cells = built.attr_cells
    assert ((cells[pz.mask] & attr.ATTR_SAFEZONE) > 0).all(), \
        "plaza is not flagged safe"
    assert not ((cells[pz.mask] & attr.ATTR_BLOCK) > 0).any(), \
        "plaza is flagged safe but the player cannot stand on it"


def test_plaza_is_flat(built):
    """Measured slope under the shipped discs is 0.0-1.9 deg.

    Slope, not height span: a 36 m disc laid over a gentle rise spans a few
    metres of height at well under a degree, and the corpus figure is the
    gradient. The first version of this test asserted on the span and failed a
    disc measuring 0.6 deg, which is inside the corpus band.
    """
    pz = built.layout.plazas[0]
    h, w = built.slope_deg.shape
    ys, xs = np.nonzero(pz.mask)
    cy = np.clip(ys // 2, 0, h - 1)
    cx = np.clip(xs // 2, 0, w - 1)
    slope = built.slope_deg[cy, cx]
    assert float(slope.mean()) < 3.0, \
        "plaza mean slope %.2f deg -- the corpus measures 0.0-1.9" % slope.mean()


@pytest.mark.parametrize("plaza,fragment", [
    (PlazaSpec(centre=(120.0, 120.0), radius_m=60.0, tile_index=6), "outside the corpus band"),
    (PlazaSpec(centre=(120.0, 120.0), radius_m=2.0, tile_index=6), "outside the corpus band"),
    (PlazaSpec(centre=(5.0, 120.0), radius_m=18.0, tile_index=6), "runs off"),
    (PlazaSpec(centre=(120.0, 120.0), radius_m=18.0, tile_index=99), "outside the palette"),
])
def test_bad_plaza_is_caught_before_building(plaza, fragment):
    spec = make_spec(plazas=[plaza])
    problems = " ".join(spec.validate())
    assert fragment in problems, problems


def test_plaza_survives_a_spec_round_trip(tmp_path):
    """A mapspec that cannot be reloaded is not a contract."""
    spec = make_spec()
    path = tmp_path / "spec.yaml"
    spec.dump(path)
    back = MapSpec.load(path)
    assert len(back.plazas) == 1
    assert back.plazas[0].radius_m == spec.plazas[0].radius_m
    assert back.plazas[0].tile_index == spec.plazas[0].tile_index
    assert back.plazas[0].safezone is True

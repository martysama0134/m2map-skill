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


def test_the_playable_interior_is_the_largest_ground_not_the_middle():
    """A moat through the centre of the map must not become "the interior".

    Reachability was seeded from the free cell nearest the map centre. With a
    walled river running through (128, 128) that cell is the flat river bed: the
    flood filled the channel, judged every bank unreachable, and the whole map
    came out blocked (99%) and painted rock. The corpus rule is about the
    LARGEST component -- its complement is 0.00-0.13% of a map.
    """
    from m2map.gen import walkable
    free = np.zeros((200, 200), bool)
    free[10:190, 10:90] = True              # the west bank: 14,400 tiles
    free[10:190, 96:106] = True             # a channel through the centre: 1,800
    free[10:190, 112:150] = True            # the east bank: 6,840, unconnected
    keep = walkable.reachable(free)
    assert keep[100, 50] and not keep[100, 100] and not keep[100, 130]
    assert keep.sum() == 180 * 80
    # a seed still wins when one is given
    seed = np.zeros_like(free)
    seed[100, 130] = True
    assert walkable.reachable(free, seed)[100, 130]


# --- bridges ---------------------------------------------------------------
#
# Measured on the seven bridges of metin2_map_a1. A bridge is not placed ON the
# terrain, the terrain is built FOR it (rule 23): both banks at one height
# (2-7 cm apart under the three stone bridges, 10-82 cm under the four rope
# ones), the channel cut to the span, the model hung at a fixed datum below the
# bank, and attr cleared under the deck while the river beside it is 91-100%
# blocked.

MOAT_CM = 16400.0


def _bridge_spec(model="a1_stone", roll=90.0):
    from m2map.gen.spec import BridgeSpec
    return make_spec(
        plazas=[], objects=[], regions=[], safezone_regions=[],
        height_range_cm=(16000.0, 19000.0),          # a gorge needs ground to be cut from
        roads=[RoadSpec(waypoints=[(128, 0), (128, 128), (128, 255)], width_m=5.0, tile_index=1)],
        water=[WaterSpec(waypoints=[(0, 128), (128, 128), (255, 128)], width_m=18.0,
                         surface_z=MOAT_CM)],
        bridges=[BridgeSpec(model=model, centre=(128.0, 128.0), roll_deg=roll)])


def test_bridge_gets_level_banks_a_cut_channel_and_its_datum():
    from m2map.gen.spec import BRIDGE_MODELS
    b = pipeline.run(_bridge_spec())
    m = BRIDGE_MODELS["a1_stone"]
    half = m["length_cm"] / 200.0                       # metres
    h = b.height_cm                                     # 2 m vertex grid, [y, x]
    north, south = h[int((128 - half) / 2), 64], h[int((128 + half) / 2) + 1, 64]
    assert abs(north - south) <= 10.0, "banks %.0f / %.0f -- a1 measures 2-7 cm" % (north, south)
    bank = (north + south) / 2.0
    for d in (4, 10, 18):                               # the approach is flat for 20 m
        assert abs(h[int((128 - half - d) / 2), 64] - bank) <= 60.0
        assert abs(h[int((128 + half + d) / 2) + 1, 64] - bank) <= 60.0
    # the bank comes from the WATER: a1 stone bridges stand 210-237 cm over it
    assert bank == pytest.approx(MOAT_CM + m["water_below_bank_cm"], abs=10.0)
    # ...and the moat is one continuous surface, whatever ground it crosses
    mid = b.submerged[128, 8:248]
    assert mid.mean() > 0.95, "the river is dry along %.0f%% of its length" % (100 * (1 - mid.mean()))
    assert len(b.water_heights) == 1 and b.water_heights[0] == MOAT_CM
    assert not any(line.startswith("! bridge") for line in b.log)
    bed = h[64, 64]
    assert bank - bed >= 600.0, "bed only %.0f below the bank; a1 measures 658-978" % (bank - bed)

    rec = [r for r in b.records if r.crc == m["crc"]]
    assert len(rec) == 1 and rec[0].roll == 90.0
    assert rec[0].x == pytest.approx(12800.0) and -rec[0].y == pytest.approx(12800.0)
    datum = rec[0].z + rec[0].height_bias
    assert datum == pytest.approx(bank - m["datum_below_bank_cm"], abs=15.0)

    a = b.attr_cells
    deck = a[128 - int(half) + 1:128 + int(half), 126:131]
    assert not (deck & 0x03).any(), "block or water flag under the deck"
    beside = a[120:137, 148]                            # the river 20 m downstream
    assert (beside & 0x03).any()
    assert any(line.startswith("bridge:") for line in b.log)


def test_a_rope_bridge_is_anchored_at_one_end():
    from m2map.gen.spec import BRIDGE_MODELS
    m = BRIDGE_MODELS["suspension02"]
    b = pipeline.run(_bridge_spec(model="suspension02", roll=180.0))   # spans south from its origin
    rec = [r for r in b.records if r.crc == m["crc"]][0]
    half = m["length_cm"] / 2.0
    assert rec.x == pytest.approx(12800.0, abs=1.0)
    assert -rec.y == pytest.approx(12800.0 - half, abs=1.0)            # the NORTH end of the span
    h = b.height_cm
    north, south = h[int((128 - half / 100.0) / 2), 64], h[int((128 + half / 100.0) / 2) + 1, 64]
    assert abs(north - south) <= 10.0
    assert rec.z + rec.height_bias == pytest.approx(north - m["datum_below_bank_cm"], abs=15.0)
    assert north - h[64, 64] >= 1400.0, "a rope bridge hangs over a gorge: a1 measures 15-43 m"


def _islands_spec():
    from m2map.gen.spec import BridgeSpec, IslandsSpec
    return make_spec(
        size=(2, 1), plazas=[], objects=[], regions=[], safezone_regions=[], water=[],
        height_range_cm=(16200.0, 17200.0), flat_fraction=0.7, border_ridge_cm=0.0,
        roads=[RoadSpec(waypoints=[(150, 128), (220, 128), (292, 128), (362, 128)],
                        width_m=5.0, tile_index=1)],
        bridges=[BridgeSpec(model="suspension01", centre=(256.0, 128.0), roll_deg=90.0)],
        islands=IslandsSpec(sites=[(150.0, 128.0), (362.0, 128.0)], rim_m=40.0,
                            surface_cm=10000.0, bed_cm=8800.0))


def _seat(b, model):
    """Metres of bank-level ground under each end of a rope bridge, walking the
    model's own axis from its origin -- how the corpus ones were measured."""
    from m2map.gen.spec import BRIDGE_MODELS, BridgeSpec
    m = BRIDGE_MODELS[model]
    length = m["length_cm"] / 100.0
    r = [x for x in b.records if x.crc == m["crc"]][0]
    dx, dy = BridgeSpec(model=model, roll_deg=r.roll).span_dir()
    ox, oy, datum = r.x / 100.0, -r.y / 100.0, r.z + r.height_bias
    s = np.arange(-20.0, length + 20.0, 0.25)
    g = np.array([b.height_cm[int(round((oy + dy * t) / 2.0)), int(round((ox + dx * t) / 2.0))]
                  for t in s])
    bank = g > datum - 150.0
    return s[(s < length / 2) & bank].max(), length - s[(s > length / 2) & bank].min()


@pytest.mark.parametrize("roll", [90.0, 270.0])
def test_a_rope_bridge_sits_unevenly_and_the_same_whichever_way_it_points(roll):
    """40 corpus placements: 1.5-4 m of bank under the origin end, 7-12 under
    the far end. Fitted 6 / 6 the landing hung over the water; and the pooled
    masks sat a metre off, so east and west spans seated 2 m apart."""
    from m2map.gen.spec import BridgeSpec
    spec = _islands_spec()
    spec.bridges = [BridgeSpec(model="suspension01", centre=(256.0, 128.0), roll_deg=roll)]
    spec.islands.berm_cm = spec.islands.warp_m = spec.islands.wobble_m = 0.0
    near, far = _seat(pipeline.run(spec), "suspension01")
    assert 1.0 <= near <= 4.0, "origin end rests %.1f m on its bank (corpus 1.5-4)" % near
    assert 7.0 <= far <= 12.0, "far end rests %.1f m on its bank (corpus 7-12)" % far


def test_block_without_rock_is_never_a_sliver(built):
    """Steep for a few metres is not a wall: a blocked strip under 9 tiles wide
    with no cliff paint near it is an invisible fence."""
    from m2map.gen import attribute
    from m2map.gen.texture import _dilate, _erode
    a, t = built.attr_cells, built.tiles
    blocked = (a & 0x01).astype(bool) & ~(a & 0x02).astype(bool)
    cliff = [i for i, sl in enumerate(built.spec.textures, start=1) if sl.role == "cliff"]
    rock = _dilate(np.isin(t, cliff), 4)
    k = attribute.SLIVER_TILES // 2
    thin = blocked & ~_dilate(_erode(blocked, k), k + 1) & ~rock
    bb = built.spec.border_band_m + 1
    thin[:bb, :] = thin[-bb:, :] = False
    thin[:, :bb] = thin[:, -bb:] = False
    for fx, fy, *rest in built.footprints:                 # props block what they stand on
        r = int(max(rest[:2]) if len(rest) > 1 else rest[0]) + 3
        thin[max(0, int(fy) - r):int(fy) + r + 1, max(0, int(fx) - r):int(fx) + r + 1] = False
    assert thin.mean() < 0.0005, "%.2f%% of the map is unpainted sliver block" % (100 * thin.mean())


def test_levelling_a_road_leaves_no_saw_tooth_on_its_verge():
    """The corridor mask is binary on a 2 m grid: along a diagonal road cut
    across a slope, levelled ground met raw ground at a new height on every step
    of the staircase -- 2 m teeth down the verge (`map_ad3`: 618 cm against 245
    unlevelled)."""
    from m2map.gen import layout, terrain

    def verge_roughness(levelled):
        spec = _hilly_road_spec()
        lay = layout.build(spec)
        flat = lay.flatten_mask_cells()
        h = terrain.build(spec, flatten_mask=flat if levelled else np.zeros_like(flat),
                          ridge_gap=lay.ridge_gap)
        lap = np.abs(4 * h[1:-1, 1:-1] - h[:-2, 1:-1] - h[2:, 1:-1] - h[1:-1, :-2] - h[1:-1, 2:])
        rd = lay.road_distance[::2, ::2][1:h.shape[0] - 1, 1:h.shape[1] - 1]
        m = np.zeros_like(lap, bool)
        m[:rd.shape[0], :rd.shape[1]] = (rd >= 4.0) & (rd <= 14.0)
        m[:8, :] = m[-8:, :] = False
        m[:, :8] = m[:, -8:] = False
        return float(np.percentile(lap[m], 95))

    raw, cut = verge_roughness(False), verge_roughness(True)
    assert cut <= raw * 1.15, "verge roughness p95 %.0f levelled vs %.0f raw" % (cut, raw)


def _hilly_road_spec():
    return make_spec(plazas=[], objects=[], regions=[], safezone_regions=[], water=[],
                     height_range_cm=(0.0, 9000.0), slope_p50=18.0, slope_p95=44.0,
                     flat_fraction=0.05, roughness=0.8)


def _shoulder_block(b):
    lay = b.layout
    bb = b.spec.border_band_m
    inner = np.zeros(lay.shape, bool)
    inner[bb:-bb, bb:-bb] = True
    shoulder = lay.road_clear & ~lay.road_mask & inner
    return float((b.attr_cells[shoulder] & 0x01).astype(bool).mean())


def test_a_road_keeps_a_shoulder_and_block_never_runs_ahead_of_the_rock(monkeypatch):
    """A road through a rock hump was a 5 m slot between saw-toothed block
    standing on the road's own rim, where no stone is painted. `map_a2`: rock
    20.6 / 24.5 / 28.8% against block 19.3 / 21.4 / 24.6% at 1-2, 2-3, 3-5 m."""
    from m2map.gen import layout
    assert _shoulder_block(pipeline.run(_hilly_road_spec())) == 0.0
    monkeypatch.setattr(layout, "ROAD_SHOULDER_M", 0.0)
    wide = layout.Layout.road_clear
    monkeypatch.setattr(layout.Layout, "road_clear", property(
        lambda self: np.logical_or.reduce([c.core for c in self.corridors])))
    b = pipeline.run(_hilly_road_spec())
    monkeypatch.setattr(layout.Layout, "road_clear", wide)
    monkeypatch.setattr(layout, "ROAD_SHOULDER_M", 2.5)
    assert _shoulder_block(b) > 0.05, "the hilly fixture no longer squeezes its road"


def test_islands_are_mesas_over_one_sea_joined_only_by_the_deck():
    """`map_a2`: equal tops either side of a bridge, a flooded canyon between,
    rock and block on all of it, and the road stopping at each lip."""
    b = pipeline.run(_islands_spec())
    h = b.height_cm
    west, east, mid = h[64, 100], h[64, 156], h[64, 128]
    assert abs(west - east) <= 10.0, "tops %.0f / %.0f across the bridge" % (west, east)
    assert mid == pytest.approx(8800.0, abs=1.0), "no causeway under the deck"
    assert west - 10000.0 >= 5000.0, "a2 stands 53-95 m over its water"
    assert b.water_heights == [10000.0]
    assert b.submerged[128, 256] and not b.submerged[128, 200]
    assert not b.wet.any(), "the sea is not an authored basin; flora ignores it"
    assert not any(line.startswith("! bridge") for line in b.log)

    a, t = b.attr_cells, b.tiles
    assert not (a[126:131, 224:289] & 0x03).any(), "the deck is walkable"
    assert (a[100:118, 256] & 0x01).all(), "the canyon beside the deck is blocked"
    assert (a[128, 150:215] & 0x01).sum() == 0, "the road on the top is open"
    cliff = [i for i, sl in enumerate(b.spec.textures, start=1) if sl.role == "cliff"]
    assert np.isin(t[90:120, 250:262], cliff).all(), "the bed is rock, as a2 paints it"
    assert np.isin(t[128, 236:276], cliff).all(), "no road paint across the canyon"
    # both tops are one playable interior, through the road over the deck
    assert not (a[128, 160] & 0x01) and not (a[128, 350] & 0x01)


def test_bad_bridges_are_caught_before_building():
    from m2map.gen.spec import BridgeSpec
    spec = _bridge_spec()
    spec.bridges = [BridgeSpec(model="drawbridge", centre=(128.0, 128.0))]
    assert any("bridge model" in p for p in spec.validate())
    spec.bridges = [BridgeSpec(model="a1_stone", centre=(5.0, 128.0), roll_deg=0.0)]
    assert any("runs off" in p for p in spec.validate())
    spec.bridges = [BridgeSpec(model="a1_stone", centre=(128.0, 128.0), roll_deg=50.0)]
    assert any("multiple of 15" in p for p in spec.validate())


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


def test_scatter_keeps_off_plazas_and_pads(built):
    """A disc is clear in the corpus, and a pad holds a compound copied whole.

    map_skill_test_06: ten scattered trees landed inside the b1 town square,
    between its stalls -- the candidate mask knew roads and water and nothing
    about plazas.
    """
    pz = built.layout.plazas[0]
    inside = [r for r in built.records
              if pz.mask[int(-r.y / 100.0), int(r.x / 100.0)]]
    assert not inside, "%d scattered records stand on the plaza" % len(inside)


def test_authored_buildings_block_their_footprint_but_not_the_road():
    """A copied town is made of `positions`, and those never stamped attr.

    field_empire blocks 85.7% of Building centre cells; map_skill_test_06 had
    0 of 10 -- hotel, guesthouses and workhouse all walk-through on the server.
    The footprint is the model's own rectangle turned by its roll (a 36 x 20 m
    hall stamped as a disc seals the square), and the road keeps its core: the
    b1 hotel stands ON the north spoke, which runs through its gate.
    """
    spec = make_spec(water=[], plazas=[], objects=[])
    core = pipeline.run(spec).layout.corridors[0].core
    ry = 80
    rx = int(np.nonzero(core[ry])[0].mean())           # a tile on the road
    hall = ObjectTier(crc=2286315329, name="hall", tier="signature", density=0.0,
                      positions=[(60.0, 200.0, 0.0), (float(rx), float(ry), 90.0)])
    spec.objects = [hall]
    box = {2286315329: (3600.0, 2000.0, 1500.0)}
    b = pipeline.run(spec, bbox_lookup=box.get)
    blocked = (b.attr_cells & 1).astype(bool)
    # off the road, unturned: 36 m along x, 20 m along y
    assert blocked[200, 60] and blocked[200, 60 + 15] and blocked[200 + 8, 60]
    assert not blocked[200 + 15, 60], "the hall was stamped as a disc of its long side"
    # on the road, turned 90: the long axis is y now, and the road runs through
    near = np.zeros_like(core)
    near[ry - 22:ry + 23, rx - 22:rx + 23] = True      # the border seal is elsewhere
    assert not blocked[core & near].any(), "a building footprint sealed the road"
    assert blocked[ry + 14, rx - 7] and blocked[ry - 14, rx + 7]   # the corners off the route


def test_shore_paint_stays_at_the_water():
    """`shore` is an overlay for the waterline, not ground cover.

    Its suitability kept a 0.05 floor everywhere, and the overlay normalises by
    the mean: on a map with a small pond the floor IS the mean, so beach sand
    was sprinkled at its full weight over the whole map -- 5% of a town square
    120 m from the water. Corpus: `beach sand 01` has 100% of its tiles within
    4 m of water.
    """
    spec = make_spec()
    spec.textures = list(spec.textures) + [
        TextureSlot("d:/ymir work/terrainmaps/b/beach/beach sand 01.dds",
                    role="shore", weight=0.5)]
    spec.water = [WaterSpec(waypoints=[(60, 180), (90, 170), (100, 200), (70, 210)],
                            width_m=0.0, lake=True)]
    b = pipeline.run(spec)
    sand = b.tiles == len(spec.textures)
    assert sand.any(), "no shore tile was painted at all"
    from m2map.gen.objects import _water_distance
    far = sand & (_water_distance(b.submerged) > 8.0)
    assert far.sum() <= 0.05 * sand.sum(), (
        "%d of %d shore tiles are more than 8 m from the waterline"
        % (far.sum(), sand.sum()))


def test_a_levelling_pad_is_not_held_to_the_plaza_band():
    """The 8-25 m band is measured on PAINTED discs. A pad paints nothing.

    `b1_town_square` spans 60 m about its centre and the hotel on its rim is
    36 x 20 m, so its pad is 70 m -- and the expanded spec was refused as a
    plaza too big to read as one.
    """
    pad = PlazaSpec(centre=(128.0, 128.0), radius_m=70.0, tile_index=0, safezone=False)
    assert not [p for p in make_spec(plazas=[pad]).validate() if "corpus band" in p]
    flagged = PlazaSpec(centre=(128.0, 128.0), radius_m=70.0, tile_index=0, safezone=True)
    assert [p for p in make_spec(plazas=[flagged]).validate() if "corpus band" in p]


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

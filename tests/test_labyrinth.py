"""Labyrinths from dungeon kits: every kit closes, and the player can walk it.

The kits are read from `reference/labyrinth/kits.json`, which ships with the
skill, so none of this needs the corpus. What is checked is what went wrong
while the generator was built: runs that do not meet their junctions, a room
mouth joined to a corridor without its door, a boss nobody can reach, rolls off
the cardinal four, a CRC that is not in the property catalog.
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "m2map"
sys.path.insert(0, str(SKILL / "scripts"))

from m2map.gen import labyrinth                                  # noqa: E402
from m2map.gen.spec import LabyrinthSpec, MapSpec, SpecError     # noqa: E402

KITS = json.loads((SKILL / "reference/labyrinth/kits.json").read_text(encoding="utf-8"))["kits"]
CATALOG = json.loads((SKILL / "reference/catalog/objects.json").read_text(encoding="utf-8"))["objects"]

#: one kit per geometry; the five other maze/monkey skins share `maze`'s
FAMILIES = ["anglar", "maze", "whitedragon_01", "whitedragon_02", "spider", "skipia",
            "mt_thunder"]


def spec_for(kit, cells=(4, 4), seed=3, loops=0.15):
    s = MapSpec(name="lab_" + kit, archetype="dungeon_block", style="box",
                attr_style="painted_box", seed=seed)
    s.labyrinth = LabyrinthSpec(kit=kit, cells=cells, loops=loops)
    return s


def attr_of(plan):
    """The attr the pipeline would paint: block, carve the walk, re-block the
    barricades, seal a 4 m border."""
    shape = (plan.size[1] * 256, plan.size[0] * 256)
    walk, block = plan.masks(shape)
    cells = np.ones(shape, np.uint8)
    cells[walk & ~block] = 0
    cells[:4, :] = cells[-4:, :] = 1
    cells[:, :4] = cells[:, -4:] = 1
    return cells


@pytest.mark.parametrize("kit", FAMILIES)
def test_every_kit_closes_and_is_walkable(kit):
    plan = labyrinth.plan(spec_for(kit))
    assert plan.placed, "nothing placed"
    line = labyrinth.reach_check(plan, attr_of(plan))[0]
    assert "REACHABLE" in line and "NOT" not in line, line


@pytest.mark.parametrize("kit", FAMILIES)
def test_records_are_catalog_crcs_on_cardinal_rolls(kit):
    plan = labyrinth.plan(spec_for(kit))
    for r in plan.records(16484.0):
        assert str(r.crc) in CATALOG, "CRC %d not in the property catalog (rule 2)" % r.crc
        assert r.y <= 0.0, "areadata y is stored negated (rule 3)"
    for p in plan.placed:
        assert p.roll % 90 == 0, "%s at roll %s: kits turn by 90 only" % (p.piece.name, p.roll)


def test_room_mouths_take_a_door():
    """A whitedragon room's 10 m mouth is its own socket family; only the door
    pieces carry it to the 32 m corridor."""
    kit = labyrinth.load_kit("whitedragon_01")
    by = {p.name: p for p in kit.pieces.values()}
    room = by["WDC_01_room_04"].sockets[0]["family"]
    line = by["WDC_01_Line_01"].sockets[0]["family"]
    door = {s["family"] for s in by["WDC_01_door_02"].sockets}
    assert room != line
    assert door == {room, line}


def test_spider_is_a_barricaded_grid():
    plan = labyrinth.plan(spec_for("spider", cells=(4, 4)))
    assert plan.shut, "a grid kit shuts its walls with barricades"
    fences = {r["crc"] for r in KITS["spider"]["barricade"]["template"]["records"]}
    assert sum(1 for r in plan.extra if r.crc in fences) >= len(plan.shut)


def test_maze_kit_is_warp_islands():
    plan = labyrinth.plan(spec_for("maze", cells=(4, 4)))
    assert plan.warps, "the maze kits are islands joined by warp gates"


def test_unknown_kit_is_refused():
    with pytest.raises(SpecError):
        labyrinth.plan(spec_for("no_such_kit"))


def test_spec_round_trips_and_validates():
    s = spec_for("skipia")
    s.textures = []
    back = MapSpec.from_dict(s.to_dict())
    assert back.labyrinth.kit == "skipia" and back.labyrinth.cells == (4, 4)
    sculpted = spec_for("skipia")
    sculpted.style = "sculpted"
    assert any("labyrinth needs style 'box'" in m for m in sculpted.validate())


@pytest.mark.parametrize("kit", FAMILIES)
@pytest.mark.parametrize("seed", [1, 2])
def test_unbraided_mazes_stay_connected(kit, seed):
    """No loops is the hard case: every join is the only way through. Skipia
    split into 2-5 pieces here until the walk was painted across each join --
    a room's measured walk stops ~2 m short of its mouth."""
    plan = labyrinth.plan(spec_for(kit, cells=(3, 3), seed=seed, loops=0.0))
    line = labyrinth.reach_check(plan, attr_of(plan))[0]
    assert "NOT" not in line, line


def test_pillars_and_doors_are_not_pieces():
    """A DungeonBlock with no floor of its own rides a piece: the mt_thunder
    joint pillars come back as dressing, anglar's quest doors not at all."""
    kit = labyrinth.load_kit("mt_thunder")
    names = {p.name for p in kit.pieces.values()}
    assert "Mt_Thunder_passagepillar" not in names
    assert "Mt_Thunder_startroompillar" not in names
    pillar = 2874598244
    assert any(d["crc"] == pillar for p in kit.pieces.values() for d in p.dressing)
    anglar = labyrinth.load_kit("anglar")
    door = 3565590118
    assert not any(d["crc"] == door for p in anglar.pieces.values() for d in p.dressing)


def test_offset_mouths_are_not_fillers():
    kit = labyrinth.load_kit("mt_thunder")
    centre = next(p for p in kit.pieces.values() if p.name == "Mt_Thunder_centerroom")
    assert centre.kind != "straight"


# --- trench labyrinths: the maze cut into the terrain -----------------------

def trench_spec(islands=None, cells=(6, 6), seed=5):
    from m2map.gen.spec import TextureSlot
    s = spec_for("orc_trench", cells=cells, seed=seed, loops=0.1)
    s.labyrinth.islands = islands
    s.archetype = "dungeon_themed"
    s.textures = [TextureSlot(path="d:/ymir work/terrainmaps/dungeon/devilcave/dc_field_01.dds", role="floor"),
                  TextureSlot(path="d:/ymir work/terrainmaps/dungeon/devilcave/dc_rock_01.dds", role="wall"),
                  TextureSlot(path="d:/ymir work/terrainmaps/dungeon/devilcave/dc_grass_00.dds", role="floor_patch")]
    return s


@pytest.mark.parametrize("islands", [None, False])
def test_trench_is_reachable_and_cut_to_the_measured_depth(islands):
    from m2map.gen import labyrinth_terrain as LT
    spec = trench_spec(islands)
    plan = labyrinth.plan(spec)
    shape = (plan.size[1] * 256, plan.size[0] * 256)
    ras = plan.raster(shape, spec.seed)
    st = LT.TRENCH_STYLES["orc_trench"]
    walk, floor = ras["walk"], ras["floor"]
    assert walk.any() and not (walk & ~floor).any(), "walk lies inside the floor"
    hv = ras["height"]
    fl = floor[::2, ::2][:hv.shape[0], :hv.shape[1]]
    depth = st["plateau_cm"] - np.median(hv[:fl.shape[0], :fl.shape[1]][fl])
    assert abs(depth - st["depth_cm"]) < 300, depth
    cells = np.ones(shape, np.uint8)
    cells[walk] = 0
    line = labyrinth.reach_check(plan, cells)[0]
    assert "NOT" not in line, line
    if islands is None:
        assert len(plan.warps) >= 2, "letters joined by gates"
    for r in plan.records(0.0):
        assert str(r.crc) in CATALOG


def test_trench_build_writes_visible_terrain(tmp_path):
    from m2map.gen import pipeline
    spec = trench_spec(cells=(4, 4))
    b = pipeline.run(spec)
    assert any("REACHABLE" in l and "NOT" not in l for l in b.log)
    out = tmp_path / "map"
    pipeline.write(b, out)
    text = (out / "setting.txt").read_text()
    assert "TerrainVisible" not in text, "a trench labyrinth IS its terrain"

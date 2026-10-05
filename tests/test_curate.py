"""Curate (`edit/curate.py`): each quality finding broken into a finished map is
cleared by its fix, inside the chosen sectors only, with a backup beside it."""

from __future__ import annotations

import pathlib
import shutil
import sys

import numpy as np
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "skills" / "m2map" / "scripts"))

from m2map.audit import quality as Q                             # noqa: E402
from m2map.audit.rules import resolve                            # noqa: E402
from m2map.codec import server_attr as sa_codec                  # noqa: E402
from m2map.codec.areadata import AreaData                        # noqa: E402
from m2map.codec.attr import read_attr, write_attr               # noqa: E402
from m2map.codec.height import read_height                       # noqa: E402
from m2map.codec.tile import read_tile, write_tile               # noqa: E402
from m2map.edit import curate                                    # noqa: E402
from m2map.gen import pipeline                                   # noqa: E402

from test_generate import make_spec                              # noqa: E402


@pytest.fixture(scope="module")
def finished(tmp_path_factory):
    out = tmp_path_factory.mktemp("curate") / "metin2_map_pytest"
    pipeline.write(pipeline.run(make_spec(border_ridge_cm=2200.0, border_ridge_width_m=48.0)), out)
    return out


@pytest.fixture(scope="module")
def flat(tmp_path_factory):
    out = tmp_path_factory.mktemp("curate_flat") / "metin2_map_pytest"
    pipeline.write(pipeline.run(make_spec(border_ridge_cm=0.0)), out)
    return out


def copy(src, tmp_path):
    dst = tmp_path / "work" / src.name
    shutil.copytree(src, dst)
    return dst


def rules_of(m):
    return {f.rule for f in Q.quality(resolve(m), str(m / "textureset"))}


def ts(m):
    return str(m / "textureset")


def test_attr_and_rock_come_back_on_a_map_without_attr(finished, tmp_path):
    m = copy(finished, tmp_path)
    a = read_attr(m / "000000" / "attr.atr")
    a.cells[:] = 0
    write_attr(m / "000000" / "attr.atr", a)
    assert {"M2MAP-QA-001", "M2MAP-QA-002"} <= rules_of(m)
    rep = curate.curate(m, ["attr", "rock"], textureset_dir=ts(m))
    assert pathlib.Path(rep["backup"]).is_dir()
    assert not rules_of(m) & {"M2MAP-QA-001", "M2MAP-QA-002"}
    # server_attr follows the attr (rule 14)
    cells = read_attr(m / "000000" / "attr.atr").cells
    assert np.array_equal(sa_codec.read_server_attr(m / "server_attr").to_bytes(),
                          sa_codec.from_attr_maps({(0, 0): cells}, 1, 1).to_bytes())
    # the backup is the broken original
    assert not read_attr(pathlib.Path(rep["backup"]) / "000000" / "attr.atr").cells.any()


def test_a_ruler_road_gets_a_dithered_rim(finished, tmp_path):
    m = copy(finished, tmp_path)
    tm = read_tile(m / "000000" / "tile.raw")
    t = tm.tiles
    t[t == 1] = 2
    t[124:130, 8:248] = 1
    t[8:248, 60:66] = 1
    write_tile(m / "000000" / "tile.raw", tm)
    assert "M2MAP-QA-003" in rules_of(m)
    before = read_tile(m / "000000" / "tile.raw").tiles.copy()
    rep = curate.curate(m, ["road"], textureset_dir=ts(m), make_backup=False)
    assert "M2MAP-QA-003" not in rules_of(m)
    after = read_tile(m / "000000" / "tile.raw").tiles
    changed = after != before
    assert changed.any() and "road1" in rep["spots"]
    # only the rim moved: nothing more than 3 m from the original road edge
    road = before == 1
    assert not (changed & ~Q._dilate(road, 3)).any()
    assert not (changed & ~Q._dilate(~road, 2)).any()


def test_the_same_seed_gives_the_same_rim(finished, tmp_path):
    outs = []
    for i in range(2):
        m = copy(finished, tmp_path / str(i))
        tm = read_tile(m / "000000" / "tile.raw")
        tm.tiles[tm.tiles == 1] = 2
        tm.tiles[124:130, 8:248] = 1
        write_tile(m / "000000" / "tile.raw", tm)
        curate.curate(m, ["road"], textureset_dir=ts(m), make_backup=False, seed=7)
        outs.append((m / "000000" / "tile.raw").read_bytes())
    assert outs[0] == outs[1]


def test_an_open_edge_gets_a_ridge_and_its_objects_ride_up(flat, tmp_path):
    m = copy(flat, tmp_path)
    assert "M2MAP-QA-004" in rules_of(m)
    rec0 = AreaData.load(m / "000000" / "areadata.txt").records
    h0 = read_height(m / "000000" / "height.raw").raw.astype(float)
    rep = curate.curate(m, ["border"], textureset_dir=ts(m), make_backup=False)
    assert "M2MAP-QA-004" not in rules_of(m), rep["changes"]
    h1 = read_height(m / "000000" / "height.raw").raw.astype(float)
    dz = (h1 - h0) * 0.5
    assert dz.min() >= 0 and dz.max() > 800
    assert dz[60:70, 60:70].max() == 0, "the middle of the map is not touched"
    rec1 = AreaData.load(m / "000000" / "areadata.txt").records
    # trees on the new bare rock go (test below); every survivor rides up
    left = {(r.crc, round(r.x, 2), round(r.y, 2)): r for r in rec1}
    assert left
    for r0 in rec0:
        r1 = left.get((r0.crc, round(r0.x, 2), round(r0.y, 2)))
        if r1 is None:
            continue
        vx, vy = int(round(r0.x / 200.0)), int(round(-r0.y / 200.0))
        assert r1.z - r0.z == pytest.approx(dz[vy + 1, vx + 1], abs=1.0)
    assert rep["spots"]


def test_fixes_stay_inside_the_chosen_sectors(flat, tmp_path):
    """A 1x1 map has only sector 000000: naming no other sector changes nothing."""
    m = copy(flat, tmp_path)
    a = read_attr(m / "000000" / "attr.atr")
    a.cells[:] = 0
    write_attr(m / "000000" / "attr.atr", a)
    snap = {p.relative_to(m): p.read_bytes() for p in m.rglob("*") if p.is_file()}
    g = curate.load(m, ts(m))
    region = curate.region_mask(g, ["001001"])
    assert not region.any()
    curate.fix_attr(g, region)
    curate.fix_border(g, region)
    assert curate.write(g) == []
    assert snap == {p.relative_to(m): p.read_bytes() for p in m.rglob("*") if p.is_file()}


def test_unknown_fix_is_refused(finished, tmp_path):
    with pytest.raises(ValueError):
        curate.curate(copy(finished, tmp_path), ["prettify"], make_backup=False)


def test_the_cli_lists_then_fixes(finished, tmp_path, capsys):
    """--list is the menu the mode asks from; --fix applies only what was picked."""
    import json
    sys.path.insert(0, str(REPO_ROOT / "skills" / "m2map" / "scripts"))
    import curate_map
    m = copy(finished, tmp_path)
    a = read_attr(m / "000000" / "attr.atr")
    a.cells[:] = 0
    write_attr(m / "000000" / "attr.atr", a)
    assert curate_map.main([str(m), "--list"]) == 0
    menu = json.loads(capsys.readouterr().out)["flagged"]
    assert {f["fix"] for f in menu if f["fix"]} >= {"attr", "rock"}
    assert curate_map.main([str(m), "--fix", "attr", "--no-backup"]) == 0
    rep = json.loads(capsys.readouterr().out)
    assert "M2MAP-QA-002" in rep["flagged_before"] and "M2MAP-QA-002" not in rep["flagged_after"]
    assert "backup" not in rep


def test_a_shore_clipped_to_its_water_is_carried_out_or_banked(flat, tmp_path):
    """The fixture's river plane stops at its water: its own 2 m grid is the
    shoreline (WTR-005). The fix grows it over the shallows, banks it where the
    surface is perched over flat ground, and floods no land doing so."""
    m = copy(flat, tmp_path)
    g = curate.load(m, ts(m))
    assert "M2MAP-WTR-005" in {f["rule"] for f in curate.water_findings(g)}
    wet0 = np.isfinite(g.water).sum()
    curate.fix_water(g, curate.region_mask(g, None))
    b, exposed = curate._shore(g)
    assert exposed.sum() <= 0.05 * b.sum()
    assert np.isfinite(g.water).sum() < 1.5 * wet0, "the river was carried to its shore, not across the plain"
    assert not (g.height < g.orig["height"] - 1e-6).any(), "a bank only raises"
    curate.write(g)
    assert "M2MAP-WTR-005" not in {f["rule"] for f in curate.water_findings(curate.load(m, ts(m)))}


def test_stray_water_bits_are_cleared_and_unflagged_maps_stay_unflagged(flat, tmp_path):
    m = copy(flat, tmp_path)
    a = read_attr(m / "000000" / "attr.atr")
    a.cells[:] &= np.uint8(~2 & 0xFF)          # a map that never flags its water...
    a.cells[10:60, 10:60] |= 2                 # ...and somebody's stray water brush on dry land
    write_attr(m / "000000" / "attr.atr", a)
    g = curate.load(m, ts(m))
    assert "M2MAP-ATR-002" in {f["rule"] for f in curate.water_findings(g)}
    curate.fix_water(g, curate.region_mask(g, None))
    wet_t = np.repeat(np.repeat(np.isfinite(g.water), 2, 0), 2, 1)
    assert not ((g.attr & 2) != 0)[~wet_t].any()
    assert not ((g.attr & 2) != 0)[wet_t].any(), "28 official maps never flag water: none is added"


def test_the_audit_water_attr_check_runs(finished, tmp_path):
    """It used to read `world_heights` as an attribute, raise, and be swallowed:
    the check never ran. A sector that flags its water but misses half fires."""
    from m2map.audit import rules
    from m2map.codec.water import read_water
    m = copy(finished, tmp_path)
    g = curate.load(m, ts(m))
    deep = g.submerged_cells & ((g.water - g.height[:-1, :-1]) > 50)
    assert deep.sum() >= 100
    assert "M2MAP-WTR-004" not in {f.rule for f in rules.audit(m)}
    a = read_attr(m / "000000" / "attr.atr")
    ys, xs = np.nonzero(deep)
    half = ys < np.median(ys)
    for y, x in zip(ys[half], xs[half]):
        a.cells[2 * y:2 * y + 2, 2 * x:2 * x + 2] &= np.uint8(~2 & 0xFF)
    write_attr(m / "000000" / "attr.atr", a)
    assert rules._submerged_mask(read_water(m / "000000" / "water.wtr"),
                                 read_height(m / "000000" / "height.raw")) is not None
    assert "M2MAP-WTR-004" in {f.rule for f in rules.audit(m)}


def test_water_level_merges_close_levels_and_keeps_real_drops(flat, tmp_path):
    """The fixture's river runs 3.1, 3.8, 5.5, 10.6, 11.6 m: the band edges show
    as strips of sand. Within 3 m they become one level; the 5 m drop stays."""
    m = copy(flat, tmp_path)
    g = curate.load(m, ts(m))
    assert "curate:water_level" in {f["rule"] for f in curate.water_findings(g)}
    curate.fix_water_level(g, curate.region_mask(g, None))
    levels = sorted({round(float(v)) for v in g.water[np.isfinite(g.water)]})
    assert len(levels) == 2 and levels[1] - levels[0] > curate.LEVEL_SPAN_CM
    assert "curate:water_level" not in {f["rule"] for f in curate.water_findings(g)}


def test_seam_holes_close_only_where_the_upper_level_is_shallow(flat, tmp_path):
    m = copy(flat, tmp_path)
    g = curate.load(m, ts(m))
    rc = np.ones(g.water.shape, bool)
    w0 = g.water.copy()
    curate._close_seams(g, rc)
    assert not curate.seam_holes(g).any()
    moved = g.water != w0
    moved &= np.isfinite(w0)
    # never a water cliff: everything handed up is covered by at most a metre
    assert (g.water[moved] - curate._low_corner(g)[moved] <= curate.SEAM_MAX_DEPTH_CM + 1e-6).all()


def test_the_rim_takes_its_trees_off_the_bare_rock(flat, tmp_path):
    from m2map.edit.curate import _tree_crcs
    m = copy(flat, tmp_path)
    before = AreaData.load(m / "000000" / "areadata.txt").records
    rep = curate.curate(m, ["border"], textureset_dir=ts(m), make_backup=False)
    after = AreaData.load(m / "000000" / "areadata.txt").records
    trees = _tree_crcs()
    gone = sum(r.crc in trees for r in before) - sum(r.crc in trees for r in after)
    assert gone > 0 and any("trees taken off" in c for c in rep["changes"])
    assert sum(r.crc not in trees for r in before) == sum(r.crc not in trees for r in after), \
        "only trees go, and only off the rock (keep the scatter)"


def test_two_levels_never_meet_without_terrain_between(flat, tmp_path):
    """The user's rule: different levels only where ground parts them; levels
    close together become one. The fixture river's 5 m drop hung a slab of upper
    water over the slope (188 open contact edges, corpus 0-36)."""
    m = copy(flat, tmp_path)
    g = curate.load(m, ts(m))
    assert "M2MAP-WTR-006" in {f["rule"] for f in curate.water_findings(g)}
    curate.fix_water(g, curate.region_mask(g, None))
    assert curate.level_contacts(g)[0] == 0
    levels = sorted({round(float(v)) for v in g.water[np.isfinite(g.water)]})
    assert all(b - a > curate.LEVEL_SPAN_CM for a, b in zip(levels, levels[1:]))
    # the sill is a landform: no vertex stands more than 3 m over a neighbour
    h = g.height
    assert max(np.abs(np.diff(h, axis=0)).max(), np.abs(np.diff(h, axis=1)).max()) < \
        max(300.0, np.abs(np.diff(g.orig["height"], axis=0)).max() + 1)

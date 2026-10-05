"""Quality rules (`audit/quality.py`): a finished map stays quiet, and each of
the four worst cases -- no attr, walkable cliffs, ruler-cut roads, an open
edge -- is flagged once someone breaks a finished map that way."""

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
from m2map.codec.attr import read_attr, write_attr               # noqa: E402
from m2map.codec.tile import read_tile, write_tile               # noqa: E402
from m2map.gen import pipeline                                   # noqa: E402

from test_generate import make_spec                              # noqa: E402


@pytest.fixture(scope="module")
def finished(tmp_path_factory):
    """A generated 1x1 with its mountain rim: what a finished map looks like."""
    out = tmp_path_factory.mktemp("quality") / "metin2_map_pytest"
    spec = make_spec(border_ridge_cm=2200.0, border_ridge_width_m=48.0)
    pipeline.write(pipeline.run(spec), out)
    return out


def rules_of(map_dir):
    return {f.rule for f in Q.quality(resolve(map_dir), str(map_dir / "textureset"))}


def copy(src, tmp_path):
    dst = tmp_path / src.name
    shutil.copytree(src, dst)
    return dst


def test_a_finished_map_is_quiet(finished):
    assert not rules_of(finished) & {"M2MAP-QA-001", "M2MAP-QA-002", "M2MAP-QA-003", "M2MAP-QA-004"}


def test_a_map_nobody_made_attr_for(finished, tmp_path):
    m = copy(finished, tmp_path)
    a = read_attr(m / "000000" / "attr.atr")
    a.cells[:] = 0
    write_attr(m / "000000" / "attr.atr", a)
    got = rules_of(m)
    assert "M2MAP-QA-002" in got
    assert "M2MAP-QA-001" in got, "its painted cliffs are walkable too"
    assert "M2MAP-QA-004" not in got, "the mountain rim still walls the edge"


def test_a_road_cut_with_a_ruler(finished, tmp_path):
    """Repaint the road as a 6 m L with nothing blended into its
    edges -- what an unblended polygon brush leaves."""
    m = copy(finished, tmp_path)
    tm = read_tile(m / "000000" / "tile.raw")
    t = tm.tiles
    t[t == 1] = 2
    t[124:130, 8:248] = 1
    t[8:248, 60:66] = 1
    write_tile(m / "000000" / "tile.raw", tm)
    assert "M2MAP-QA-003" in rules_of(m)


def test_a_flat_map_edge_is_open_and_water_is_not(finished, tmp_path):
    spec = make_spec(border_ridge_cm=0.0)
    out = tmp_path / "metin2_map_pytest"
    pipeline.write(pipeline.run(spec), out)
    assert "M2MAP-QA-004" in rules_of(out)


def test_a_curtain_wall_of_buildings_closes_the_edge(finished, tmp_path, monkeypatch):
    """An empire castle walls its edge with buildings, not rock: tall objects
    lining a stretch count as a wall."""
    spec = make_spec(border_ridge_cm=0.0)
    out = tmp_path / "metin2_map_pytest"
    pipeline.write(pipeline.run(spec), out)
    every = np.ones((256, 256), bool)
    monkeypatch.setattr(Q, "_wall_objects", lambda root, sectors, shape: every)
    assert "M2MAP-QA-004" not in rules_of(out)

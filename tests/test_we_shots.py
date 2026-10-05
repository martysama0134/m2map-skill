"""The editor-shot helper, as far as it can be tested without the editor."""

from __future__ import annotations

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "skills" / "m2map" / "scripts"))

from m2map import config                                          # noqa: E402
from m2map.edit import we_shots                                   # noqa: E402

SETTING = ("ScriptType\tMapSetting\r\n\r\nCellScale\t200\r\nHeightScale\t0.500000\r\n\r\n"
           "ViewRadius\t128\r\n\r\nMapSize\t1\t1\r\nBasePosition\t0\t0\r\n"
           "TextureSet\ttextureset\\merged.txt\r\nEnvironment\ta1.msenv\r\n")


def test_a_pass_is_looked_at_in_its_middle():
    report = {"links": [{"blocks": [0, 3], "from_tile": [230, 1236], "to_tile": [230, 1280]}]}
    assert we_shots.link_spots(report) == {"link03": (230.0, 1258.0)}


def test_the_textureset_is_staged_where_the_editor_looks(tmp_path):
    """The editor resolves the textureset against its data root, not the map.
    Missing, the shot is an untextured plane and exit 0 -- and the editor leaves
    a ``TextureCount 0`` stub there, which must be overwritten."""
    mp, data = tmp_path / "map", tmp_path / "data"
    (mp / "textureset").mkdir(parents=True)
    (mp / "setting.txt").write_bytes(SETTING.encode("ascii"))
    (mp / "textureset" / "merged.txt").write_bytes(b"TextureSet\r\nTextureCount 2\r\n")
    (data / "textureset").mkdir(parents=True)
    (data / "textureset" / "merged.txt").write_bytes(b"TextureSet\r\nTextureCount 0\r\n")

    assert we_shots.stage_textureset(mp, data)
    assert b"TextureCount 2" in (data / "textureset" / "merged.txt").read_bytes()
    assert we_shots.stage_textureset(mp, data) is None, "already there: nothing written"


def test_an_unconfigured_editor_is_said_not_hidden(monkeypatch):
    monkeypatch.setattr(config, "paths", lambda: config.Paths())
    with pytest.raises(we_shots.RenderUnavailable, match="worldeditor_exe"):
        we_shots.editor()


def test_a_bake_is_read_off_the_editor_log(monkeypatch):
    """v61 logs "bake: shadowmap minimap on N terrains"; that line, and only that
    line, says the bake happened."""
    log = ("1005 13:48:02996 :: automation: bake mask 3\n"
           "1005 13:48:03279 :: bake: shadowmap minimap on 9 terrains\n")
    monkeypatch.setattr(we_shots, "_run", lambda m, extra, timeout: log)
    assert we_shots.bake("D:/somewhere") == 9
    monkeypatch.setattr(we_shots, "_run", lambda m, extra, timeout: "automation: loading map x\n")
    with pytest.raises(RuntimeError, match="v61"):
        we_shots.bake("D:/somewhere")


def test_a_failed_script_is_reported(monkeypatch):
    monkeypatch.setattr(we_shots, "_run",
                        lambda m, extra, timeout: "automation: script C:/x.py -> FAILED\n")
    with pytest.raises(RuntimeError, match="raised"):
        we_shots.run_script("D:/somewhere", __file__)
    monkeypatch.setattr(we_shots, "_run", lambda m, extra, timeout: "automation: script C:/x.py -> ok\n")
    assert "-> ok" in we_shots.run_script("D:/somewhere", __file__)

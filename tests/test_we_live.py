"""WorldEditorRemix's Python API, live: the draw bindings run inside the editor on a
copy of corpus a1, the map is saved, and the saved files are read back with this
skill's codecs. Opt-in (it starts the editor twice, about a minute):

    M2MAP_WE_LIVE=1 python -m pytest tests/test_we_live.py

Every binding passing here passed the same way on v61 (fixme100); `reference/we-api.md`.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import sys

import numpy as np
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "skills" / "m2map" / "scripts"))

from m2map.codec.areadata import AreaData                        # noqa: E402
from m2map.codec.attr import read_attr                           # noqa: E402
from m2map.codec.height import read_height                       # noqa: E402
from m2map.codec.tile import read_tile                           # noqa: E402
from m2map.codec.water import read_water                         # noqa: E402
from m2map.config import paths                                   # noqa: E402
from m2map.edit import we_shots                                  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent / "we_live"

pytestmark = pytest.mark.skipif(os.environ.get("M2MAP_WE_LIVE") != "1",
                                reason="starts WorldEditorRemix: set M2MAP_WE_LIVE=1")


def _a1():
    P = paths()
    src = pathlib.Path(P.corpus) / "metin2_map_a1" if P.corpus else None
    if not src or not src.is_dir():
        pytest.skip("corpus metin2_map_a1 not on this machine")
    try:
        we_shots.editor()
    except we_shots.RenderUnavailable as e:
        pytest.skip(str(e))
    return src


def _run(src, script, tmp_path, result):
    """Copy a1 and the script, run it inside the editor with --save, return its JSON."""
    work = tmp_path / "map"
    shutil.copytree(src, work)
    sdir = tmp_path / "script"
    sdir.mkdir()
    shutil.copy(HERE / script, sdir / script)
    we_shots.run_script(work, sdir / script, save=True)
    return work, json.loads((sdir / result).read_text())


def sec(gx, gy):
    return "%03d%03d" % (gx // 128, gy // 128), gx % 128, gy % 128


def test_every_draw_binding_lands_live_and_on_disk(tmp_path):
    src = _a1()
    out, res = _run(src, "draw_api.py", tmp_path, "draw_api_result.json")
    bad = {k: v[1] for k, v in res["live"].items() if not v[0]}
    assert not bad, "live: %s" % bad
    did = res["did"]

    for key in ("height_pixel", "set_height"):
        gx, gy, h = did[key]
        s, cx, cy = sec(gx, gy)
        assert int(read_height(out / s / "height.raw").raw[cy + 1, cx + 1]) == h, key
    x1, y1, x2, y2, h = did["height_region"]
    s, cx, cy = sec(x1, y1)
    blk = read_height(out / s / "height.raw").raw[cy + 1:cy + 2 + y2 - y1, cx + 1:cx + 2 + x2 - x1]
    assert (blk == h).all(), "height_region"

    gx, gy, tex, _ = did["texture_brush"]
    s, cx, cy = sec(gx, gy)
    assert read_tile(out / s / "tile.raw").tiles[2 * cy, 2 * cx] == tex

    gx, gy, level, _ = did["water_brush"]
    s, cx, cy = sec(gx, gy)
    wm = read_water(out / s / "water.wtr")
    assert wm.heights[wm.cells[cy, cx]] == level, "the brush's raw height is the layer's"

    for key, on in (("attr_brush", True), ("attr_erase", False)):
        x, y, f = did[key]
        a = read_attr(out / ("%03d%03d" % (x // 25600, y // 25600)) / "attr.atr").cells
        assert bool(a[int(y % 25600 // 100), int(x % 25600 // 100)] & f) == on, key

    victim, n_before, deleted, _ = did["delete"]
    assert deleted == n_before
    assert not [r for r in AreaData.load(out / "001001" / "areadata.txt").records if r.crc == victim], \
        "scope 0 deletes from the sector GotoSector went to"
    crc, ix, iy, bias, roll = did["insert"][:5]
    hit = [r for r in AreaData.load(out / "002001" / "areadata.txt").records
           if r.crc == crc and abs(r.x - ix) < 1 and abs(-r.y - iy) < 1]
    assert hit and hit[0].height_bias == pytest.approx(bias) and hit[0].roll == pytest.approx(roll)

    # and nothing else moved: every grid, every sector, outside the edited spots
    edits = {}
    for key in ("height_pixel", "set_height", "height_brush", "texture_brush", "water_brush"):
        s, cx, cy = sec(*did[key][:2])
        edits.setdefault(s, []).append((cx, cy, 8))
    s, cx, cy = sec(x1, y1)
    edits.setdefault(s, []).append((cx + 2, cy + 1, 6))
    for key in ("attr_brush", "attr_erase"):
        x, y = did[key][:2]
        edits.setdefault("%03d%03d" % (x // 25600, y // 25600), []).append(
            (int(x % 25600 // 200), int(y % 25600 // 200), 8))
    yy, xx = np.mgrid[0:128, 0:128]
    for d in sorted(p for p in src.iterdir() if p.is_dir() and p.name.isdigit()):
        near = np.zeros((128, 128), bool)
        for cx, cy, r in edits.get(d.name, []):
            near |= (np.abs(xx - cx) <= r) & (np.abs(yy - cy) <= r)
        for f, rd, get in (("height.raw", read_height, lambda m: m.raw[1:129, 1:129]),
                           ("tile.raw", read_tile, lambda m: m.tiles[::2, ::2]),
                           ("attr.atr", read_attr, lambda m: m.cells[::2, ::2])):
            if (d / f).is_file():
                a, b = get(rd(d / f)), get(rd(out / d.name / f))
                assert not ((a != b) & ~near).any(), "%s/%s changed outside the edits" % (d.name, f)
        if d.name not in ("001001", "002001") and (d / "areadata.txt").is_file():
            key = lambda r: (r.crc, round(r.x), round(r.y), round(r.z))
            assert sorted(map(key, AreaData.load(d / "areadata.txt").records)) == \
                sorted(map(key, AreaData.load(out / d.name / "areadata.txt").records)), d.name


def test_init_base_texture_survives_the_save(tmp_path):
    src = _a1()
    out, res = _run(src, "init_texture.py", tmp_path, "init_texture_result.json")
    assert res["InitBaseTexture"][0], res["InitBaseTexture"][1]
    for p in sorted(out.glob("[0-9]*/tile.raw")):
        assert (read_tile(p).tiles == 2).all(), p.parent.name

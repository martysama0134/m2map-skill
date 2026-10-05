"""Headless WorldEditorRemix screenshots: the same camera on two maps.

The 2D previews cannot show a tear, a blank tile or a plane hanging over a bank;
only the engine draws those (SKILL.md, "Verification"). This is the verified
recipe from ``reference/we-api.md`` as a function, so a before/after pair costs
one call instead of a hand-built command per shot.

Two machine paths are needed, both configured (``m2map.paths.json``):

* ``worldeditor_exe``  -- the editor binary;
* ``worldeditor_data`` -- the data root it must run FROM, the folder holding
  ``pack/`` and ``ymir work/``. Defaults to the folder the exe is in.

The editor resolves ``textureset\\<name>.txt`` against that data root, not
against the map, so the map's textureset is copied there first; without it the
shot is an untextured plane, exit 0, and the editor leaves a 32-byte
``TextureCount 0`` stub behind that must be overwritten.

``--regen`` is never passed. Before WorldEditorRemix v61 it pressed F6 on the
frame the map loaded and baked BLACK minimaps into every sector of a textured
map; v61 renders 10 frames first and names it ``--bake`` (fixme096). Use
:func:`bake`, which checks the editor's log that the bake really ran.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .. import config
from ..codec import setting as setting_codec

FLAGS = "terrain,object,tree,water,-grid,-compass"
CAM = (45.0, 0.0, 9000.0)
SIZE = (1400, 1000)
#: Idle ticks before the grab. 30 (the editor's default) catches a half-loaded map.
FRAMES = 60
#: A shot of nothing -- no map, or the window never painted -- compresses to a
#: few kilobytes. Real ones measured 1.9-2.4 MB at 1400x1000.
MIN_PNG_BYTES = 100_000


class RenderUnavailable(RuntimeError):
    """The editor is not configured on this machine. Say so; do not pretend."""


def editor() -> Tuple[pathlib.Path, pathlib.Path]:
    """``(exe, data_root)``, or :class:`RenderUnavailable` with how to set them."""
    p = config.paths()
    try:
        exe = p.require("worldeditor_exe")
    except config.ConfigError as e:
        raise RenderUnavailable(str(e)) from None
    data = p.worldeditor_data or exe.parent
    if not (data / "pack").is_dir():
        raise RenderUnavailable(
            "%s has no pack/ folder: set worldeditor_data to the editor's data root" % data)
    return exe, data


def stage_textureset(map_dir, data_root) -> Optional[str]:
    """Copy the map's textureset to where the editor looks for it. Returns the
    destination when a file was written."""
    map_dir, data_root = pathlib.Path(map_dir), pathlib.Path(data_root)
    rel = setting_codec.Setting.load(map_dir / "setting.txt").texture_set_path.replace("\\", "/")
    src = map_dir / rel
    if not src.is_file():
        src = map_dir / "textureset" / pathlib.PurePosixPath(rel).name
    if not src.is_file():
        return None                      # a stock textureset: already in the pack
    dst = data_root / rel
    if dst.is_file() and dst.read_bytes() == src.read_bytes():
        return None
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return str(dst)


def shoot(map_dir, target_cm: Tuple[float, float], png, cam: Sequence[float] = CAM,
          size: Sequence[int] = SIZE, frames: int = FRAMES, timeout: int = 300) -> pathlib.Path:
    """One screenshot. ``target_cm`` is world centimetres with a POSITIVE y
    (tile metres x 100); the editor negates it."""
    exe, data = editor()
    png = pathlib.Path(png).resolve()
    png.parent.mkdir(parents=True, exist_ok=True)
    png.unlink(missing_ok=True)
    stage_textureset(map_dir, data)
    subprocess.run(
        [str(exe), "--map", str(pathlib.Path(map_dir).resolve()),
         "--target", "%d,%d" % (round(target_cm[0]), round(target_cm[1])),
         "--cam", ",".join("%g" % v for v in cam), "--flags", FLAGS,
         "--size", "%d,%d" % tuple(size), "--shot-frames", str(frames),
         "--shot", str(png), "--quit"],
        cwd=str(data), timeout=timeout, check=False)
    if not png.is_file() or png.stat().st_size < MIN_PNG_BYTES:
        raise RuntimeError("the editor wrote no usable shot at %s" % png)
    return png


#: what --bake* asks for, by name
BAKE_SWITCH = {"all": "--bake", "shadows": "--bake-shadows", "minimap": "--bake-minimap"}


def _run(map_dir, extra, timeout):
    exe, data = editor()
    stage_textureset(map_dir, data)
    log = data / "log.txt"
    before = log.stat().st_mtime if log.is_file() else 0.0
    subprocess.run([str(exe), "--map", str(pathlib.Path(map_dir).resolve())] + list(extra) + ["--quit"],
                   cwd=str(data), timeout=timeout, check=False)
    if not log.is_file() or log.stat().st_mtime <= before:
        raise RuntimeError("the editor wrote no log: it is older than v61 (no --bake / --script, "
                           "no log in a Release build), or it did not start")
    return log.read_text(errors="replace")


def bake(map_dir, what: str = "all", timeout: int = 900) -> int:
    """F6 headless: regenerate the shadowmap and/or minimap of every sector, in the
    map folder, through WorldEditorRemix v61+. Returns the number of terrains baked.

    The generator writes `shadowmap.raw` and a flat-shaded minimap but no
    `shadowmap.dds` -- the editor logs "ShadowTexture is Empty" for every sector of
    a fresh map -- and only the editor's own renderer makes the real ones.
    """
    text = _run(map_dir, [BAKE_SWITCH[what]], timeout)
    for line in reversed(text.splitlines()):
        if "bake:" in line and "terrains" in line:
            return int(line.split(" on ")[-1].split()[0])
    raise RuntimeError("the editor ran but logged no bake (needs WorldEditorRemix v61+)")


def run_script(map_dir, script, save: bool = False, timeout: int = 900) -> str:
    """Run a Python file inside the editor on a loaded map (module ``WorldEditor``,
    `reference/we-api.md`), optionally ``SaveMap`` after it. v61+. Returns the log;
    a script reports back by writing its own file."""
    extra = ["--script", str(pathlib.Path(script).resolve())] + (["--save"] if save else [])
    text = _run(map_dir, extra, timeout)
    if "automation: script" not in text:
        raise RuntimeError("the editor ran no script (needs WorldEditorRemix v61+)")
    if "-> FAILED" in text.split("automation: script")[-1].splitlines()[0]:
        raise RuntimeError("the script raised; its traceback is in syserr.txt in the editor data root")
    return text


def pairs(before_map, after_map, spots: Dict[str, Tuple[float, float]], out_dir,
          cam: Sequence[float] = CAM) -> List[dict]:
    """Every spot on both maps with one camera, and a contact sheet of the lot
    (``we_sheet.png``: before on the left, after on the right) so the whole
    result is one picture to look at. ``spots`` maps a name to TILE metres."""
    out_dir = pathlib.Path(out_dir)
    done = []
    for name, (tx, ty) in spots.items():
        row = {"name": name, "tile": [round(tx), round(ty)]}
        for tag, mp in (("before", before_map), ("after", after_map)):
            row[tag] = str(shoot(mp, (tx * 100.0, ty * 100.0),
                                 out_dir / ("we_%s_%s.png" % (name, tag)), cam).name)
        done.append(row)
    _sheet(out_dir, done)
    return done


def _sheet(out_dir: pathlib.Path, rows: Iterable[dict], cell_w: int = 700) -> None:
    try:
        from PIL import Image, ImageDraw
    except ImportError:                                    # pragma: no cover
        return
    rows = list(rows)
    if not rows:
        return
    tiles = []
    for r in rows:
        pair = []
        for tag in ("before", "after"):
            im = Image.open(out_dir / r[tag]).convert("RGB")
            im = im.resize((cell_w, round(im.height * cell_w / im.width)))
            ImageDraw.Draw(im).text((8, 6), "%s  %s  tile %s" % (r["name"], tag, r["tile"]),
                                    fill=(255, 255, 0))
            pair.append(im)
        tiles.append(pair)
    h = tiles[0][0].height
    sheet = Image.new("RGB", (cell_w * 2, h * len(tiles)))
    for i, pair in enumerate(tiles):
        for j, im in enumerate(pair):
            sheet.paste(im, (j * cell_w, i * h))
    sheet.save(out_dir / "we_sheet.png")


def link_spots(report: dict) -> Dict[str, Tuple[float, float]]:
    """Where to look at a readapted map: the middle of every pass."""
    spots = {}
    for lk in report.get("links", []):
        (ax, ay), (bx, by) = lk["from_tile"], lk["to_tile"]
        spots["link%d%d" % tuple(lk["blocks"])] = ((ax + bx) / 2.0, (ay + by) / 2.0)
    return spots

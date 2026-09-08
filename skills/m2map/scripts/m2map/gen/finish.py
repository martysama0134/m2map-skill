"""Stage 8 -- everything that is not a terrain layer.

``setting.txt``, ``mapproperty.txt``, per-sector ``areaproperty.txt``, the
environment reference, baked ``shadowmap`` and ``minimap``, and the server-side
files.

Two things here are easy to get wrong and fatal:

* ``setting.txt`` must carry all six required keys or the client rejects the map.
* ``areaproperty.txt`` **defines the sector**. Deleting it deletes the sector
  even when every binary layer is present.
"""

from __future__ import annotations

import pathlib
from typing import Dict, List, Sequence, Tuple

import numpy as np

from ..codec import minimap as mm_codec
from ..codec import shadow as sh_codec
from ..codec import setting as st_codec
from .spec import CELL_SCALE, HEIGHT_SCALE, MapSpec, SECTOR_TILES

#: Deliberately conservative: 128 is what 116 of 142 corpus maps use, and the
#: editor forces it on its own save path.
VIEW_RADIUS = 128


def build_setting(spec: MapSpec) -> st_codec.Setting:
    return st_codec.Setting(
        script_type="MapSetting",
        cell_scale=CELL_SCALE,
        height_scale=HEIGHT_SCALE,
        view_radius=VIEW_RADIUS,
        map_size=tuple(spec.size),
        base_position=tuple(spec.base_position),
        texture_set="textureset\\%s.txt" % (spec.textureset_name or spec.name),
        environment=spec.environment or "%s.msenv" % spec.name,
    )


def build_map_property(spec: MapSpec) -> st_codec.MapProperty:
    # Every one of the 142 corpus maps says "Outdoor", including the interiors --
    # MapType is not how the client distinguishes them.
    return st_codec.MapProperty(script_type="MapProperty", map_type="Outdoor")


def build_area_property(name: str = "") -> st_codec.AreaProperty:
    return st_codec.AreaProperty(script_type="AreaProperty", area_name=name,
                                 num_water=0)


def bake_shadow(height_cm: np.ndarray, size: int = 256,
                sun=(0.35, 0.56, -0.75)) -> np.ndarray:
    """A cheap lambert shade of the terrain, for shadowmap.raw.

    Not a ray-traced bake -- it gives the terrain visible relief in-game and in
    the minimap without a renderer. A real bake is WorldEditor's job.
    """
    gy, gx = np.gradient(height_cm.astype(np.float64), CELL_SCALE)
    nz = 1.0 / np.sqrt(gx * gx + gy * gy + 1.0)
    nx, ny = -gx * nz, -gy * nz
    lx, ly, lz = sun
    ln = float(np.sqrt(lx * lx + ly * ly + lz * lz))
    lam = np.clip((nx * lx + ny * ly + nz * lz) / ln, 0.0, 1.0)
    return (lam * 0.75 + 0.25)


def _resize(a: np.ndarray, size: int) -> np.ndarray:
    h, w = a.shape
    ys = np.clip((np.arange(size) * h) // size, 0, h - 1)
    xs = np.clip((np.arange(size) * w) // size, 0, w - 1)
    return a[np.ix_(ys, xs)]


def sector_shadow(shade: np.ndarray, cx: int, cy: int) -> sh_codec.ShadowMap:
    """256x256 uint16 shadow block for one sector."""
    cells = SECTOR_TILES // 2
    y0, x0 = cy * cells, cx * cells
    block = shade[y0:y0 + cells, x0:x0 + cells]
    if block.size == 0:
        block = np.ones((cells, cells))
    grid = _resize(block, sh_codec.SIZE)
    raw = np.clip(grid * 65535.0, 0, 65535).astype("<u2")
    return sh_codec.ShadowMap(raw)


def sector_minimap(tiles: np.ndarray, shade: np.ndarray, palette: Sequence,
                   cx: int, cy: int) -> mm_codec.MiniMap:
    """A readable minimap tile from the splat and the shading.

    Colours come from a per-slot palette so the minimap shows the same regions
    the ground does; without the real .dds decoded, a stable hashed hue per slot
    is far better than a flat grey square.
    """
    y0, x0 = cy * SECTOR_TILES, cx * SECTOR_TILES
    block = tiles[y0:y0 + SECTOR_TILES, x0:x0 + SECTOR_TILES]
    if block.shape != (SECTOR_TILES, SECTOR_TILES):
        pad = np.zeros((SECTOR_TILES, SECTOR_TILES), np.uint8)
        pad[:block.shape[0], :block.shape[1]] = block
        block = pad

    rgba = np.zeros((mm_codec.SIZE, mm_codec.SIZE, 4), np.uint8)
    idx = _resize(block, mm_codec.SIZE)
    lam = _resize(shade[y0 // 2:y0 // 2 + 128, x0 // 2:x0 // 2 + 128]
                  if shade.size else np.ones((128, 128)), mm_codec.SIZE)
    for slot in np.unique(idx):
        colour = _slot_colour(int(slot), palette)
        m = idx == slot
        for c in range(3):
            rgba[..., c][m] = np.clip(colour[c] * lam[m], 0, 255).astype(np.uint8)
    rgba[..., 3] = 255
    # DXT1 with no mips is what 1270 of 1332 shipped minimap.dds use; the
    # 262,272-byte uncompressed form the spec calls "typical" appears zero times.
    return mm_codec.MiniMap(mm_codec.DDS.from_rgba(rgba, b"DXT1", mipmaps=1))


def _slot_colour(slot: int, palette: Sequence) -> Tuple[int, int, int]:
    if slot == 0:
        return (24, 24, 28)
    entry = palette[slot - 1] if 0 < slot <= len(palette) else None
    role = getattr(entry, "role", "base") if entry else "base"
    base = {
        "base": (108, 128, 74), "mid": (126, 118, 82), "path": (146, 128, 96),
        "cliff": (122, 116, 110), "shore": (150, 142, 108),
        "accent": (96, 112, 78), "interior": (46, 44, 48),
    }.get(role, (110, 118, 84))
    jitter = (hash((role, slot)) % 31) - 15
    return tuple(int(np.clip(c + jitter, 0, 255)) for c in base)


def write_map(out_dir, spec: MapSpec, layers: Dict, palette) -> List[str]:
    """Write every file. Returns the relative paths written, for reporting."""
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: List[str] = []

    def _w(rel: str, data: bytes) -> None:
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        written.append(rel)

    _w("setting.txt", build_setting(spec).to_bytes())
    _w("mapproperty.txt", build_map_property(spec).to_bytes())

    for (cx, cy), sector in layers["sectors"].items():
        d = "%03d%03d" % (cx, cy)
        _w("%s/areaproperty.txt" % d, build_area_property().to_bytes())
        _w("%s/height.raw" % d, sector["height"].tobytes())
        _w("%s/tile.raw" % d, sector["tile"].tobytes())
        _w("%s/attr.atr" % d, sector["attr"].to_bytes())
        _w("%s/water.wtr" % d, sector["water"].to_bytes())
        _w("%s/shadowmap.raw" % d, sector["shadow"].to_bytes())
        _w("%s/minimap.dds" % d, sector["minimap"].to_bytes())
        _w("%s/areadata.txt" % d, sector["areadata"].to_bytes())
        _w("%s/areaambiencedata.txt" % d, sector["ambience"].to_bytes())

    if layers.get("server_attr") is not None:
        _w("server_attr", layers["server_attr"].to_bytes())
    return written

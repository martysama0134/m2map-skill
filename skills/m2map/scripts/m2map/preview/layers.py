"""2-D layer previews -- the verification step that runs on every build.

A map that parses is not a map that plays. These renders exist so the skill can
*look* at its own output before handing it over: does the road read as a road,
is the splatting blotchy in the right way, are objects clustered where they
should be, does the collision match the terrain.

Pure Python + Pillow, no WorldEditor needed. The 3-D check (floating models,
cliff seams, intersecting geometry) needs the real renderer and is a separate,
optional step.

Every render is whole-map: per-sector images hide exactly the faults that matter
most, which are the ones at sector boundaries.
"""

from __future__ import annotations

import pathlib
from typing import Dict, Iterable, Optional, Sequence, Tuple

import numpy as np

try:
    from PIL import Image, ImageDraw
except ImportError:                                    # pragma: no cover
    Image = ImageDraw = None

from ..codec import attr as attr_codec

#: attr bit -> (label, RGB). Only bits 0..2 have engine meaning; the rest are
#: paint conventions, which is why they are muted here.
ATTR_COLOURS = (
    (attr_codec.ATTR_BLOCK,    "block",    (206, 68, 62)),
    (attr_codec.ATTR_WATER,    "water",    (64, 116, 208)),
    (attr_codec.ATTR_SAFEZONE, "safezone", (86, 176, 96)),
    (attr_codec.ATTR_BANSHOP,  "banshop",  (206, 176, 62)),
)


def _need_pil() -> None:
    if Image is None:
        raise RuntimeError("Pillow is required for previews: pip install pillow")


def _to_image(rgb: np.ndarray) -> "Image.Image":
    return Image.fromarray(np.ascontiguousarray(rgb.astype(np.uint8)), "RGB")


def height_png(height_cm: np.ndarray) -> "Image.Image":
    """Hypsometric tint plus hillshade -- flat greyscale hides real relief."""
    _need_pil()
    lo, hi = float(height_cm.min()), float(height_cm.max())
    span = max(1.0, hi - lo)
    t = (height_cm - lo) / span

    ramp = np.array([(38, 62, 92), (58, 104, 84), (110, 142, 78),
                     (168, 158, 96), (196, 176, 140), (238, 238, 238)], float)
    pos = t * (len(ramp) - 1)
    i0 = np.clip(pos.astype(int), 0, len(ramp) - 1)
    i1 = np.clip(i0 + 1, 0, len(ramp) - 1)
    f = (pos - i0)[..., None]
    rgb = ramp[i0] * (1 - f) + ramp[i1] * f

    gy, gx = np.gradient(height_cm.astype(float), 200.0)
    shade = np.clip(1.0 / np.sqrt(gx * gx + gy * gy + 1.0), 0.25, 1.0)[..., None]
    return _to_image(rgb * (0.55 + 0.45 * shade))


def slope_png(slope_deg: np.ndarray, block_at: float = 20.0) -> "Image.Image":
    """Slope, with the blocking threshold marked -- shows why attr looks as it does."""
    _need_pil()
    t = np.clip(slope_deg / 60.0, 0, 1)
    rgb = np.stack([40 + 200 * t, 190 - 150 * t, 120 - 90 * t], axis=-1)
    edge = np.abs(slope_deg - block_at) < 0.6
    rgb[edge] = (255, 255, 255)
    return _to_image(rgb)


def tile_png(tiles: np.ndarray, palette: Optional[Sequence] = None) -> "Image.Image":
    """The splat. Distinct hue per slot so stipple and regions are both visible."""
    _need_pil()
    top = int(tiles.max()) + 1
    lut = np.zeros((max(top, 2), 3), float)
    for i in range(top):
        if i == 0:
            lut[i] = (20, 20, 24)
            continue
        role = ""
        if palette is not None and 0 < i <= len(palette):
            role = getattr(palette[i - 1], "role", "")
        base = {"base": (104, 132, 72), "mid": (140, 126, 84),
                "path": (176, 152, 112), "cliff": (128, 122, 116),
                "shore": (196, 182, 138), "accent": (86, 118, 74),
                "interior": (52, 50, 56)}.get(role)
        if base is None:
            h = (i * 47) % 360
            base = _hsv(h, 0.42, 0.72)
        lut[i] = base
    return _to_image(lut[np.clip(tiles, 0, len(lut) - 1)])


def _hsv(h: float, s: float, v: float) -> Tuple[float, float, float]:
    c = v * s
    x = c * (1 - abs(((h / 60.0) % 2) - 1))
    m = v - c
    r, g, b = [(c, x, 0), (x, c, 0), (0, c, x),
               (0, x, c), (x, 0, c), (c, 0, x)][int(h // 60) % 6]
    return ((r + m) * 255, (g + m) * 255, (b + m) * 255)


def attr_png(cells: np.ndarray) -> "Image.Image":
    """Collision. Every flag overlaid, because the dominant-flag view lies."""
    _need_pil()
    h, w = cells.shape
    rgb = np.full((h, w, 3), 28.0)
    for bit, _name, colour in ATTR_COLOURS:
        m = (cells & bit).astype(bool)
        if m.any():
            rgb[m] = colour
    # Block on top of water reads as "wall in the lake", which is a real and
    # common authoring mistake worth seeing.
    both = ((cells & attr_codec.ATTR_BLOCK) & (cells & attr_codec.ATTR_WATER)).astype(bool)
    rgb[both] = (150, 90, 190)
    return _to_image(rgb)


def water_png(wet: np.ndarray, submerged: np.ndarray) -> "Image.Image":
    """Wet vs submerged -- the distinction a naive audit rule gets wrong.

    452 of 1343 shipped sectors carry water cells whose surface is BELOW the
    terrain: invisible, and correctly unflagged in attr.
    """
    _need_pil()
    h, w = wet.shape
    rgb = np.full((h, w, 3), 30.0)
    rgb[wet] = (70, 80, 110)                    # present but buried
    rgb[submerged] = (64, 128, 220)             # actually water
    return _to_image(rgb)


def objects_png(shape: Tuple[int, int], records: Iterable, tiles=None,
                palette=None) -> "Image.Image":
    """Placements over the splat, coloured by CRC.

    Plotted at ``(x, -y)`` because areadata stores Y negated -- getting this
    wrong mirrors the whole layer and still looks plausible.
    """
    _need_pil()
    img = (tile_png(tiles, palette) if tiles is not None
           else _to_image(np.full(shape + (3,), 30.0)))
    img = img.convert("RGB")
    d = ImageDraw.Draw(img)
    for rec in records:
        tx = rec.x / 100.0
        ty = (-rec.y) / 100.0                  # de-negate
        colour = _hsv((rec.crc * 37) % 360, 0.85, 1.0)
        d.ellipse([tx - 1.5, ty - 1.5, tx + 1.5, ty + 1.5],
                  fill=tuple(int(c) for c in colour))
    return img


def sector_grid(img: "Image.Image", sector_tiles: int = 256) -> "Image.Image":
    """Overlay the sector lattice -- seams are the faults you cannot see otherwise."""
    _need_pil()
    out = img.copy()
    d = ImageDraw.Draw(out)
    w, h = out.size
    for x in range(sector_tiles, w, sector_tiles):
        d.line([(x, 0), (x, h)], fill=(255, 255, 255), width=1)
    for y in range(sector_tiles, h, sector_tiles):
        d.line([(0, y), (w, y)], fill=(255, 255, 255), width=1)
    return out


def render_all(build, out_dir, grid: bool = True) -> Dict[str, str]:
    """Write every layer preview for a :class:`~m2map.gen.pipeline.Build`."""
    _need_pil()
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: Dict[str, str] = {}

    def save(name: str, img) -> None:
        if img is None:
            return
        if grid:
            img = sector_grid(img, 256 if img.size[0] >= 256 else 128)
        p = out / ("%s.png" % name)
        img.save(p)
        written[name] = str(p)

    if build.height_cm is not None:
        save("height", height_png(build.height_cm))
    if build.slope_deg is not None:
        save("slope", slope_png(build.slope_deg, build.spec.block_slope_deg))
    if build.tiles is not None:
        save("tile", tile_png(build.tiles, build.spec.textures))
    if build.attr_cells is not None:
        save("attr", attr_png(build.attr_cells))
    if build.wet is not None and build.submerged is not None:
        save("water", water_png(build.wet, build.submerged))
    if build.records:
        save("objects", objects_png(build.layout.shape, build.records,
                                    build.tiles, build.spec.textures))
    return written

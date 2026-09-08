"""Stage 4 -- water.wtr, and the wet mask everything downstream needs.

Runs *before* texture and attr, not after: both need the rasterised wet and
submerged masks, which the vector polygons alone cannot give them.

The distinction that matters, and that a naive generator gets wrong:

* **wet** -- a water cell exists here.
* **submerged** -- a water cell exists here *and its surface is above the
  terrain*, i.e. the player would actually be in water.

The corpus is full of water planes that sit below the ground and are therefore
invisible and correctly unflagged in ``attr.atr``. Asserting "every non-0xFF
water cell carries attr 0x02" fires on 452 of 1343 shipped sectors -- in
``map_a2/000000`` alone, 443 of 2283 wet cells are buried. Only *submerged*
cells get the water attribute.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from ..codec import water as wtr
from .layout import Layout
from .spec import MapSpec, SECTOR_CELLS

#: water.wtr is a 128x128 cell grid per sector; 0xFF means "no water here".
CELLS = 128
NO_WATER = 0xFF


def _tiles_to_cells(mask: np.ndarray, ch: int, cw: int) -> np.ndarray:
    """1 m tile mask -> 2 m terrain-cell mask (any tile wet => cell wet)."""
    h, w = mask.shape
    out = np.zeros((ch, cw), bool)
    uh, uw = min(ch, h // 2), min(cw, w // 2)
    blk = mask[:uh * 2, :uw * 2].reshape(uh, 2, uw, 2)
    out[:uh, :uw] = blk.any(axis=(1, 3))
    return out


def build(spec: MapSpec, lay: Layout, height_cm: np.ndarray):
    """Return ``(cell_index_grid, surface_heights, wet, submerged)``.

    ``cell_index_grid`` is whole-map, one byte per terrain cell, indexing into
    ``surface_heights``; ``0xFF`` is dry. The masks are whole-map tile space, so
    texture and attr can use them directly.
    """
    h_tiles, w_tiles = lay.shape
    ch, cw = spec.size[1] * SECTOR_CELLS, spec.size[0] * SECTOR_CELLS

    cells = np.full((ch, cw), NO_WATER, np.uint8)
    heights: List[float] = []
    wet_tiles = np.zeros((h_tiles, w_tiles), bool)

    if spec.is_box() or not lay.water_masks:
        return cells, heights, wet_tiles, np.zeros_like(wet_tiles)

    for mask, surface in zip(lay.water_masks, lay.water_surfaces):
        cell_mask = _tiles_to_cells(mask, ch, cw)
        if not cell_mask.any():
            continue
        if surface is None:
            # Auto: sit the surface just under the local terrain median so the
            # feature reads as a river bed rather than a slab on the hillside.
            hv = height_cm[:ch, :cw][cell_mask]
            surface = float(np.percentile(hv, 35)) if hv.size else 0.0
        if len(heights) >= wtr.MAX_WATER_NUM:
            break
        heights.append(float(surface))
        cells[cell_mask] = len(heights) - 1
        wet_tiles |= mask

    # submerged = wet AND surface above terrain
    submerged_cells = np.zeros((ch, cw), bool)
    if heights:
        hgrid = height_cm[:ch, :cw]
        for i, surf in enumerate(heights):
            m = cells == i
            submerged_cells |= m & (surf > hgrid)

    submerged_tiles = _cells_to_tiles(submerged_cells, h_tiles, w_tiles)
    return cells, heights, wet_tiles, submerged_tiles


def _cells_to_tiles(mask: np.ndarray, h: int, w: int) -> np.ndarray:
    out = np.repeat(np.repeat(mask, 2, axis=0), 2, axis=1)
    padded = np.zeros((h, w), bool)
    hh, ww = min(h, out.shape[0]), min(w, out.shape[1])
    padded[:hh, :ww] = out[:hh, :ww]
    return padded


def to_sector(cells: np.ndarray, heights: List[float], cx: int, cy: int):
    """The :class:`WaterMap` for one sector, renumbered to its own layers.

    Each sector stores only the layers it uses, so a map-wide table has to be
    compacted per sector -- otherwise every sector declares every lake on the
    map and the indices no longer mean what the file says they mean.
    """
    y0, x0 = cy * SECTOR_CELLS, cx * SECTOR_CELLS
    block = cells[y0:y0 + CELLS, x0:x0 + CELLS]
    if block.shape != (CELLS, CELLS):
        pad = np.full((CELLS, CELLS), NO_WATER, np.uint8)
        pad[:block.shape[0], :block.shape[1]] = block
        block = pad

    used = sorted(int(v) for v in np.unique(block) if v != NO_WATER)
    remap: Dict[int, int] = {old: new for new, old in enumerate(used)}
    out = np.full((CELLS, CELLS), NO_WATER, np.uint8)
    for old, new in remap.items():
        out[block == old] = new
    local = [heights[o] for o in used]
    return wtr.WaterMap(cells=out, heights=local)

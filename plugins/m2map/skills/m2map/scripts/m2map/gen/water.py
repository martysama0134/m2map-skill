"""Stage 4 -- water.wtr, and the wet mask everything downstream needs.

Runs *before* texture and attr, not after: both need the rasterised wet and
submerged masks, which the vector polygons alone cannot give them.

The distinction that matters, and that a naive generator gets wrong:

* **wet** -- the AUTHORED basin: the polygon or channel the spec asked for.
  This is what the shore texture and the object water-distance rules read, so it
  stays the feature's own footprint rather than the drawn extent.
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
from .spec import HEIGHT_SCALE, MapSpec, SECTOR_CELLS

#: water.wtr is a 128x128 cell grid per sector; 0xFF means "no water here".
CELLS = 128
NO_WATER = 0xFF


#: How far the drawn water plane runs past the authored basin, as a fraction of
#: the basin's own radius. **This is the lever for a smooth shoreline**, not the
#: depth clip: measured against the share of a plane's outer boundary standing
#: over ground below its surface -- every such cell being a visible 2 m grid
#: edge -- the generator reads
#:
#:     overrun  0.45  ->  19-25% of the boundary exposed
#:              0.80  ->   8-9%
#:              1.20  ->   0-1%     <-- corpus is 0.3-2.5%
#:
#: while no value of the depth clip moved it below 15%. The plane has to reach
#: far enough inland that its edge is buried in the beach. The corpus plane is far larger than its wet area --
#: only 23% of `metin2_map_n_desert_01`'s water cells are actually submerged,
#: 41% of `metin2_map_a1`'s, 58% over the six maps measured -- because the
#: visible waterline is where the TERRAIN rises through the plane, not where the
#: polygon ends. A plane that stops at the shoreline shows its own 2 m cell grid
#: as a staircase.
PLANE_OVERRUN = 1.20


def _dilate_cells(mask: np.ndarray, steps: int) -> np.ndarray:
    out = mask
    for _ in range(int(steps)):
        nxt = out.copy()
        nxt[1:, :] |= out[:-1, :]
        nxt[:-1, :] |= out[1:, :]
        nxt[:, 1:] |= out[:, :-1]
        nxt[:, :-1] |= out[:, 1:]
        out = nxt
    return out


#: How far below the surface the ground may be for a plane cell to survive.
#: Cells deeper than this are dropped UNLESS they are enclosed by surviving ones
#: -- see :func:`_fill_holes` -- so a basin keeps its deep middle while a plane
#: overhanging a lip loses the part that hangs in the air.
#:
#: The measure this is tuned against is the share of a plane's outer boundary
#: whose ground is below the surface, because every such cell is a straight
#: 2 m grid edge the player can see. The corpus runs **0.3-2.5%**
#: (`metin2_map_c1` 0.3, `b1` 0.4, `n_desert_01` 1.2, `a1` 2.5).
PLANE_MAX_DEPTH_CM = 800.0


def _fill_holes(mask: np.ndarray) -> np.ndarray:
    """Add back any region of ``~mask`` that does not touch the grid border.

    A depth clip on its own would eat the middle of every basin, which is the
    deepest part of it. Enclosure is what separates "the bed of this lake" from
    "the ground at the bottom of the cliff this lake is pouring over": the first
    is surrounded by water, the second opens out.
    """
    free = ~mask
    seen = np.zeros_like(mask)
    seen[0, :] |= free[0, :]
    seen[-1, :] |= free[-1, :]
    seen[:, 0] |= free[:, 0]
    seen[:, -1] |= free[:, -1]
    frontier = seen.copy()
    while frontier.any():
        grown = np.zeros_like(frontier)
        grown[1:, :] |= frontier[:-1, :]
        grown[:-1, :] |= frontier[1:, :]
        grown[:, 1:] |= frontier[:, :-1]
        grown[:, :-1] |= frontier[:, 1:]
        frontier = grown & free & ~seen
        seen |= frontier
    return mask | (free & ~seen)


def _plane_mask(cell_mask: np.ndarray, height_cm=None, surface=None) -> np.ndarray:
    """The cells the water plane is actually drawn on.

    Wider than the basin by :data:`PLANE_OVERRUN` of its radius, so the terrain
    around the shore hides the plane and draws a smooth waterline over it.

    Clipped to ground within :data:`PLANE_MAX_DEPTH_CM` of the surface. Without
    that clip an upper basin perched on a shelf spills its plane over the lip and
    it renders as a slab of water hanging 25 m above the floor below -- the
    overrun is for beaches, not for cliffs.
    """
    area = float(cell_mask.sum())
    if area <= 0:
        return cell_mask
    radius = (area / np.pi) ** 0.5
    grown = _dilate_cells(cell_mask, max(2, int(round(radius * PLANE_OVERRUN))))
    if height_cm is not None and surface is not None:
        # Clip the OVERRUN only. Its whole job is to reach onto the beach, where
        # the ground is at or above the surface and hides the plane's edge; where
        # it reaches over a lip instead, the ground falls away and the edge hangs
        # in the air. The authored basin is exempt -- clipping that by depth cuts
        # the plane inside the bowl, and the resulting boundary sits three metres
        # UNDER water, which is exposed grid edge everywhere. Measured: exposed
        # boundary went from 8.6% to 30.7% doing it that way.
        deep = height_cm < (float(surface) - PLANE_MAX_DEPTH_CM)
        grown = _fill_holes((grown & ~deep) | cell_mask)
    return grown


def _claim(cells: np.ndarray, basin: np.ndarray, plane: np.ndarray, index: int) -> None:
    """Give ``index`` its basin, and whatever of its overrun is still dry.

    The overrun exists to reach onto this body's own beach. Written
    unconditionally it also reached into the next body's bowl: on a two-level
    oasis the shelf stands higher than the lower pool's surface, so the depth
    clip keeps it, and the lower plane -- written second -- took all 97 cells of
    the upper basin. The file had a waterfall anchored in water that was not
    there, and nothing in 2D showed it.
    """
    cells[basin | (plane & (cells == NO_WATER))] = index


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

    lake_tiles = lay.lake_mask if lay.lake_mask is not None else None

    for idx, (mask, surface) in enumerate(zip(lay.water_masks, lay.water_surfaces)):
        cell_mask = _tiles_to_cells(mask, ch, cw)
        if not cell_mask.any():
            continue

        # A lake is ONE flat plane. Banding it produces visible terraces across
        # the surface -- water does not step. Only a river descending its bed
        # needs several levels.
        is_lake = (lake_tiles is not None and mask.any()
                   and bool((mask & lake_tiles).sum() > mask.sum() * 0.5))
        if surface is None and is_lake:
            hv = height_cm[:ch, :cw][cell_mask]
            if len(heights) < wtr.MAX_WATER_NUM and hv.size:
                # The 35th percentile of the BASIN, not the 92nd. Taking the
                # high end put the plane above the rim of the bowl it was
                # filling, so the water flooded outward to the polygon edge,
                # left no beach, and showed its own cell grid as a staircase.
                # Sitting it inside the bowl gives the corpus shape: a plane
                # below the surrounding ground, with the shore drawn by the
                # terrain that rises through it. Corpus median depth is
                # 174-410 cm.
                heights.append(float(np.percentile(hv, 35)) + 40.0)
                _claim(cells, cell_mask,
                       _plane_mask(cell_mask, height_cm[:ch, :cw], heights[-1]),
                       len(heights) - 1)
                wet_tiles |= mask
            continue

        if surface is not None:
            if len(heights) >= wtr.MAX_WATER_NUM:
                break
            heights.append(float(surface))
            _claim(cells, cell_mask,
                   _plane_mask(cell_mask, height_cm[:ch, :cw], float(surface)),
                   len(heights) - 1)
            wet_tiles |= mask
            continue

        # Auto-levelled water. A water layer is a single FLAT plane, so one
        # surface across a river that descends 20 m leaves the upper reach
        # buried and the lower reach flooding the banks -- the river renders as
        # a chain of disconnected puddles. Real maps solve this the same way the
        # format allows: many layers, each covering a stretch at its own level
        # (water.wtr holds up to 255).
        line_tiles = (lay.water_lines[idx] if idx < len(lay.water_lines) else None)
        # centreline is in TILES, the water grid is in 2 m cells
        line_cells = ([(x / 2.0, y / 2.0) for (x, y) in line_tiles]
                      if line_tiles else None)
        for band, level in _level_bands(cell_mask, height_cm[:ch, :cw],
                                        line=line_cells):
            if len(heights) >= wtr.MAX_WATER_NUM:
                break
            heights.append(level)
            # Each band's plane also runs past its own edge, for the same reason
            # -- a channel that stops at its banks shows the cell grid along
            # them. Each band claims its own stretch, so the overrun of one is
            # trimmed by the next and only the outer rim of the whole channel
            # widens.
            _claim(cells, band, _plane_mask(band, height_cm[:ch, :cw], level),
                   len(heights) - 1)
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


def _along_channel(mask: np.ndarray, line) -> np.ndarray:
    """Position along the centreline, in tiles, for every masked cell.

    Bands have to be contiguous ALONG the river. Grouping by height value
    instead -- which is what this did first -- puts scattered cells from the
    whole length into one band whenever the bed is noisy, so that band's single
    plane floods some of them and leaves others dry. In the editor that renders
    as alternating stripes of water and exposed bed down the whole channel.
    """
    h, w = mask.shape
    ys, xs = np.mgrid[0:h, 0:w]
    best = np.full((h, w), np.inf, np.float64)
    along = np.zeros((h, w), np.float64)
    travelled = 0.0
    for (x0, y0), (x1, y1) in zip(line, line[1:]):
        dx, dy = x1 - x0, y1 - y0
        seg = float(np.hypot(dx, dy))
        if seg < 1e-9:
            continue
        tpar = np.clip(((xs - x0) * dx + (ys - y0) * dy) / (seg * seg), 0.0, 1.0)
        d = np.hypot(xs - (x0 + tpar * dx), ys - (y0 + tpar * dy))
        closer = d < best
        best[closer] = d[closer]
        along[closer] = travelled + tpar[closer] * seg
        travelled += seg
    return along


def _level_bands(mask: np.ndarray, height_cm: np.ndarray, line=None,
                 segment_m: float = 26.0, depth_cm: float = 110.0):
    """Split a water body into flat reaches that each hold water.

    Yields ``(band_mask, surface_cm)``. Each band is a contiguous stretch of the
    channel, and its surface sits ``depth_cm`` above the highest bed cell in that
    stretch, so every cell in the band is genuinely submerged.

    Falls back to height banding only when there is no centreline (which in
    practice means a lake, and lakes take the single-plane path before reaching
    here).
    """
    if mask.sum() == 0:
        return
    if line and len(line) >= 2:
        along = _along_channel(mask, line)
        vals = along[mask]
        lo, hi = float(vals.min()), float(vals.max())
        n = max(1, int(np.ceil((hi - lo) / max(1.0, segment_m))))
        edges = np.linspace(lo, hi, n + 1)
        key = along
    else:
        vals = height_cm[mask]
        lo, hi = float(vals.min()), float(vals.max())
        n = max(1, int(np.ceil((hi - lo) / 150.0)))
        edges = np.linspace(lo, hi, n + 1)
        key = height_cm

    for i in range(n):
        a = edges[i]
        b = edges[i + 1] + (1e-3 if i == n - 1 else 0.0)
        band = mask & (key >= a) & (key < b)
        if not band.any():
            continue
        yield band, float(height_cm[band].max()) + depth_cm


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

    # water.wtr stores heights in RAW units, the same scale as height.raw --
    # worldZ = value * HeightScale (reference/mapformat/water-wtr.md, and
    # AreaTerrain.cpp:1086). Everything upstream of here works in world
    # centimetres, so convert on the way out.
    #
    # Storing centimetres directly puts every water plane at HALF its intended
    # altitude, which is reliably below the terrain: the water is invisible in
    # game, and the attr WATER flags computed from the in-memory (correct)
    # heights no longer match the file. Found by loading a generated map in
    # WorldEditor and seeing no water at all.
    local = [float(heights[o]) / HEIGHT_SCALE for o in used]
    return wtr.WaterMap(cells=out, heights=local)

"""Stage 7 -- attr.atr and server_attr.

Runs **after** objects, because object footprints are an input. The original
design had this backwards; the consequence was that ``reskin`` (which re-runs
texture, objects and finish) left collision belonging to the *previous* object
set -- invisible walls where a building used to be and nothing under its
replacement.

Two styles, because the corpus has two and they share almost nothing:

``slope_driven`` (59 maps, outdoor)
    Block above a slope threshold, plus water, plus a border seal, plus object
    footprints. The measured block budget is 72.6% slope, 14.8% water, 8.8%
    border, 2.5% footprint, 1.4% residual. The Youden-optimal slope cut is
    **20 degrees** (TPR 0.807, FPR 0.103).

``painted_box`` (55 maps, interior)
    Paint everything blocked, then carve the walkable corridor. There is no
    slope rule at all -- fitting one to these maps produces meaningless
    thresholds like 9 or 10 degrees, which is an artefact of wholesale paint.

``server_attr`` is masked to ``0x07``. See ``codec/server_attr.py``: the
whole-byte copy blocks every cell of a Ymir-style map.
"""

from __future__ import annotations

from typing import Iterable, List, Tuple

import numpy as np

from ..codec import attr as attr_codec
from ..codec import server_attr as sa_codec
from .layout import Layout
from .spec import MapSpec, SECTOR_TILES

#: attr.atr is exactly 256x256 per sector -- no border padding, unlike
#: height.raw and tile.raw.
CELLS = 256


def build(spec: MapSpec, lay: Layout, slope_deg: np.ndarray,
          submerged: np.ndarray, footprints: Iterable[Tuple[float, float, float]] = ()):
    """Whole-map attribute grid in tile space, ``(h, w)`` uint8.

    ``footprints`` is ``(tile_x, tile_y, radius_tiles)`` per blocking placement.
    """
    h, w = lay.shape
    cells = np.zeros((h, w), np.uint8)

    if spec.attr_style == "painted_box":
        cells |= attr_codec.ATTR_BLOCK
        walk = np.zeros((h, w), bool)
        for corr in lay.corridors:
            walk |= corr.core | corr.fringe
        for kind in ("settlement", "clearing"):
            if kind in lay.regions:
                walk |= lay.regions[kind]
        if not walk.any():
            # No corridor was specified; leave a walkable inset rather than
            # shipping a map the player cannot enter at all.
            walk[8:-8, 8:-8] = True
        cells[walk] &= np.uint8(~attr_codec.ATTR_BLOCK & 0xFF)
    else:
        slope_tiles = _upsample(slope_deg, h, w)
        cells[slope_tiles >= spec.block_slope_deg] |= attr_codec.ATTR_BLOCK

    # Water: only cells whose surface is actually above the terrain. A buried
    # water plane is invisible and correctly unflagged in every shipped map.
    if submerged is not None and submerged.any():
        cells[submerged] |= attr_codec.ATTR_WATER | attr_codec.ATTR_BLOCK

    # The road corridor is cleared LAST of the terrain rules, after slope and
    # water, because a road is a route by definition: it cuts through steep
    # ground (the corpus leaves ~4% of steep cells open and they are almost all
    # corridors) and it crosses water as a ford or bridge. Clearing before the
    # water pass instead let a river re-block the crossing, sealing the route
    # with no way through -- and the map still looked fine in every layer
    # preview except attr.
    #
    # ATTR_WATER stays set on a ford: Ymir paints exactly this as 0xCA
    # ("bridge, walkable" over water). Only BLOCK is lifted.
    for corr in lay.corridors:
        cells[corr.core] &= np.uint8(~attr_codec.ATTR_BLOCK & 0xFF)

    # Border seal. Maps stop the player with a block band at the edge; measured
    # widths cluster at a few metres.
    b = max(0, int(spec.border_band_m))
    if b:
        cells[:b, :] |= attr_codec.ATTR_BLOCK
        cells[-b:, :] |= attr_codec.ATTR_BLOCK
        cells[:, :b] |= attr_codec.ATTR_BLOCK
        cells[:, -b:] |= attr_codec.ATTR_BLOCK

    # Object footprints -- the reason this stage runs after placement.
    for fx, fy, radius in footprints:
        if radius <= 0:
            continue
        x0, x1 = int(max(0, fx - radius)), int(min(w, fx + radius + 1))
        y0, y1 = int(max(0, fy - radius)), int(min(h, fy + radius + 1))
        if x1 <= x0 or y1 <= y0:
            continue
        ys, xs = np.mgrid[y0:y1, x0:x1]
        disc = (xs - fx) ** 2 + (ys - fy) ** 2 <= radius * radius
        cells[y0:y1, x0:x1][disc] |= attr_codec.ATTR_BLOCK

    for kind in spec.safezone_regions:
        mask = lay.regions.get(kind)
        if mask is not None:
            cells[mask] |= attr_codec.ATTR_SAFEZONE
            cells[mask] &= np.uint8(~attr_codec.ATTR_BLOCK & 0xFF)

    return cells


def _upsample(grid: np.ndarray, h: int, w: int) -> np.ndarray:
    gh, gw = grid.shape
    ys = np.clip((np.arange(h) * gh) // max(1, h), 0, gh - 1)
    xs = np.clip((np.arange(w) * gw) // max(1, w), 0, gw - 1)
    return grid[np.ix_(ys, xs)]


def to_sector(cells: np.ndarray, cx: int, cy: int) -> attr_codec.AttrMap:
    y0, x0 = cy * SECTOR_TILES, cx * SECTOR_TILES
    block = cells[y0:y0 + CELLS, x0:x0 + CELLS]
    if block.shape != (CELLS, CELLS):
        pad = np.zeros((CELLS, CELLS), np.uint8)
        pad[:block.shape[0], :block.shape[1]] = block
        block = pad
    return attr_codec.AttrMap(cells=block.astype(np.uint8))


def build_server_attr(spec: MapSpec, cells: np.ndarray):
    """The server collision file, masked to the bits the server reads."""
    grids = {}
    for cx, cy in spec.sectors():
        grids[(cx, cy)] = to_sector(cells, cx, cy).cells
    return sa_codec.from_attr_maps(grids, spec.size[0], spec.size[1])


def coverage(cells: np.ndarray) -> dict:
    total = cells.size
    return {
        "block": float((cells & attr_codec.ATTR_BLOCK).astype(bool).mean()),
        "water": float((cells & attr_codec.ATTR_WATER).astype(bool).mean()),
        "safezone": float((cells & attr_codec.ATTR_SAFEZONE).astype(bool).mean()),
        "cells": int(total),
    }

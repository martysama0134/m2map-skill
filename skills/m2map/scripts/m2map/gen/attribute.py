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

``painted_box`` (57 maps, interior)
    Paint everything blocked, then carve the walkable corridor. There is no
    slope rule at all -- fitting one to these maps produces meaningless
    thresholds like 9 or 10 degrees, which is an artefact of wholesale paint.

``server_attr`` is masked to ``0x07``. See ``codec/server_attr.py``: the
whole-byte copy blocks every cell of a Ymir-style map.
"""

from __future__ import annotations

import math
from typing import Iterable, List, Tuple

import numpy as np

from ..codec import attr as attr_codec
from ..codec import server_attr as sa_codec
from . import walkable
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
        # Steep ground, the border band, AND anything walkable-by-slope that is
        # cut off from the playable interior. That last term is what seals the
        # flat crest of the border ridge: measured over five corpus maps the
        # high third of the outer 64 m ring is 100% blocked, so Ymir walls the
        # rim all the way over the top rather than only on its faces. See
        # `gen/walkable.py`.
        cells[walkable.terrain_block(spec, slope_deg, (h, w),
                                     roads=lay.road_mask)] |= attr_codec.ATTR_BLOCK

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
    authored = np.zeros((h, w), bool)
    for fp in footprints:
        if len(fp) == 5:
            # An authored building: its own rectangle, turned by its roll. Roll
            # is counter-clockwise with north up and the tile grid is y-down
            # (`placement.md` 6.w), so the offset is flipped before it is turned
            # back into the model's frame.
            fx, fy, hx, hy, roll = fp
            reach = int(math.ceil(math.hypot(hx, hy))) + 1
            x0, x1 = int(max(0, fx - reach)), int(min(w, fx + reach + 1))
            y0, y1 = int(max(0, fy - reach)), int(min(h, fy + reach + 1))
            if x1 <= x0 or y1 <= y0:
                continue
            ys, xs = np.mgrid[y0:y1, x0:x1]
            dx, dy = xs - fx, -(ys - fy)
            c, s_ = math.cos(math.radians(roll)), math.sin(math.radians(roll))
            u, v = dx * c + dy * s_, -dx * s_ + dy * c
            authored[y0:y1, x0:x1] |= (np.abs(u) <= hx) & (np.abs(v) <= hy)
            continue
        fx, fy, radius = fp
        if radius <= 0:
            continue
        x0, x1 = int(max(0, fx - radius)), int(min(w, fx + radius + 1))
        y0, y1 = int(max(0, fy - radius)), int(min(h, fy + radius + 1))
        if x1 <= x0 or y1 <= y0:
            continue
        ys, xs = np.mgrid[y0:y1, x0:x1]
        disc = (xs - fx) ** 2 + (ys - fy) ** 2 <= radius * radius
        cells[y0:y1, x0:x1][disc] |= attr_codec.ATTR_BLOCK

    # ...and the road keeps its core through them. Tents, warp gates and the b1
    # hotel all stand ON the route (d(road) p50 0 cm); the hotel's gate is the
    # north spoke of its square.
    for corr in lay.corridors:
        authored &= ~corr.core
    cells[authored] |= attr_codec.ATTR_BLOCK

    # The deck of a bridge is the one strip across a river the player walks.
    # On `metin2_map_a1` it carries neither BLOCK nor WATER under all seven
    # bridges, while the river 15 m to either side is 91-100% blocked.
    for fit in getattr(lay, "bridges", []):
        cells[fit.deck] &= np.uint8(~(attr_codec.ATTR_BLOCK | attr_codec.ATTR_WATER) & 0xFF)

    # Named regions declared safe. Note that these are NOT cleared of block:
    # safe-zone and block overlap freely in the corpus -- 923,325 of the
    # 1,282,946 safe-zone cells across the 37 maps that use the flag also carry
    # block (72%), because Ymir paints the safe area over a town wholesale,
    # walls and scenery included. Only the walkable disc below is cleared.
    for kind in spec.safezone_regions:
        mask = lay.regions.get(kind)
        if mask is not None:
            cells[mask] |= attr_codec.ATTR_SAFEZONE

    # Plaza discs. Unlike a region, the disc IS the floor the player stands on,
    # so it is cleared of block: measured 100% safe-flagged and walkable in
    # metin2_map_a1, a3, b1, b3, c1, c3, guild_war2 and wedding_01, against a
    # map baseline of 0.2%. (The discs that measure 0% -- smhgate_*, t1 -- sit
    # on maps whose baseline is also 0.0%: paint-only clones that never wrote
    # attr, not counter-examples.)
    for pz in lay.plazas:
        if not pz.safezone:
            continue
        cells[pz.mask] |= attr_codec.ATTR_SAFEZONE
        cells[pz.mask] &= np.uint8(~attr_codec.ATTR_BLOCK & 0xFF)

    # The collision a copied landform came with, forced last: a bridge deck over
    # a moat is a record, and nothing above knows the water under it is crossed.
    for rs in getattr(spec, "relief_stamps", None) or []:
        if not rs.attr_rows:
            continue
        src = np.array([[-1 if ch_ == "-" else int(ch_) for ch_ in row]
                        for row in rs.attr_rows], np.int16)
        yy, xx = np.mgrid[0:cells.shape[0], 0:cells.shape[1]]
        u, v = rs.lookup(xx + 0.5, yy + 0.5,
                         (rs.attr_origin_m[0] + 0.5, rs.attr_origin_m[1] + 0.5), 1.0)
        ui, vi = np.rint(u).astype(int), np.rint(v).astype(int)
        ok = (ui >= 0) & (ui < src.shape[1]) & (vi >= 0) & (vi < src.shape[0])
        val = np.full(cells.shape, -1, np.int16)
        val[ok] = src[vi[ok], ui[ok]]
        hit = val >= 0
        cells[hit] = (cells[hit] & np.uint8(0xF8)) | val[hit].astype(np.uint8)

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

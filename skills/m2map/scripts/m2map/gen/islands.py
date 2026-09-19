"""Mesas over one water plane -- the landform of `map_a2`.

See :class:`spec.IslandsSpec` for the measurements. This module turns the sites
into one field on the terrain vertex grid:

    ``t`` = 1 on a top (an island, or the rim mesa), 0 on the canyon bed, and
    the wall profile between.

Everything else reads that: the terrain stage cuts ``bed + (h - bed) * t``, the
water stage floods what ends up below the surface, and the texture and attr
stages keep rock and block on every tile where ``t < 1`` -- the *void* -- however
a road crosses it. Only a bridge deck is walked.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np

from .spec import MapSpec, SECTOR_CELLS, stream_seed


def edge_distance(spec: MapSpec) -> Tuple[np.ndarray, np.ndarray]:
    """``(e, rim)`` on the vertex grid: metres from the nearest canyon
    centreline, and whether the vertex belongs to the rim mesa.

    The canyon between two islands is their bisector; the distance from a point
    in site *a*'s cell to the bisector with *j* is
    ``(|p-j|^2 - |p-a|^2) / (2 |a-j|)``, and the cell boundary is the least of
    those. A SOFT minimum, so three canyons meeting round their corners off
    into a pool the way `map_a2`'s do instead of meeting at a point.
    """
    isl = spec.islands
    sx, sy = spec.size
    h, w = sy * SECTOR_CELLS + 1, sx * SECTOR_CELLS + 1
    ys, xs = np.mgrid[0:h, 0:w]
    px, py = xs * 2.0, ys * 2.0                       # vertex -> tile metres

    # Bend the whole diagram. Straight bisectors and a square rim read as a
    # diagram; `map_a2`'s canyons curve. The warp is a smooth displacement of
    # the sample point, faded to nothing round every bridge so the canyon still
    # crosses each span at its midpoint and square to it.
    if isl.warp_m > 0:
        from .terrain import fbm
        rng = np.random.default_rng(stream_seed("islands-warp", spec.seed))
        wx = (fbm(rng, h, w, octaves=2, base_cells=70, gain=0.45) - 0.5) * 2.0
        wy = (fbm(rng, h, w, octaves=2, base_cells=70, gain=0.45) - 0.5) * 2.0
        hold = np.ones((h, w), np.float64)
        for br in spec.bridges:
            d = np.hypot(px - br.centre[0], py - br.centre[1])
            k_ = np.clip((d - 45.0) / 90.0, 0.0, 1.0)
            hold = np.minimum(hold, k_ * k_ * (3.0 - 2.0 * k_))
        # ...and toward the map edge, so the rim mesa keeps its width: it is what
        # stands between the player and the end of the world.
        to_edge = np.minimum(np.minimum(px, (w - 1) * 2.0 - px),
                             np.minimum(py, (h - 1) * 2.0 - py))
        k_ = np.clip((to_edge - float(isl.rim_m)) / 200.0, 0.0, 1.0)
        hold = hold * (0.25 + 0.75 * k_ * k_ * (3.0 - 2.0 * k_))
        px = px + wx * hold * float(isl.warp_m)
        py = py + wy * hold * float(isl.warp_m)

    sites = np.asarray(isl.sites, np.float64)
    d2 = np.stack([(px - x) ** 2 + (py - y) ** 2 for x, y in sites])
    near = np.argmin(d2, axis=0)
    d2_near = np.take_along_axis(d2, near[None], axis=0)[0]

    k = max(1e-6, float(isl.round_m))
    acc = np.zeros((h, w), np.float64)
    hard = np.full((h, w), np.inf)
    for j, (x, y) in enumerate(sites):
        sep = np.hypot(sites[near, 0] - x, sites[near, 1] - y)
        ej = np.where(near == j, np.inf,
                      (d2[j] - d2_near) / (2.0 * np.maximum(sep, 1e-6)))
        hard = np.minimum(hard, ej)
        acc += np.exp(-np.minimum(ej, 1e6) / k)
    soft = -k * np.log(np.maximum(acc, 1e-300))
    e = soft if isl.round_m > 0 else hard          # soft <= hard everywhere

    # The rim is one more mesa: its canyon runs `rim_m` in from the edge.
    # A rounded box, not a square: the corner of the rim canyon turns on a
    # radius, so the corner islands are not slabs with a point.
    dx_ = np.minimum(px, (w - 1) * 2.0 - px)
    dy_ = np.minimum(py, (h - 1) * 2.0 - py)
    R = max(float(isl.rim_m), float(isl.rim_corner_m))
    R = min(R, 0.35 * 2.0 * (min(h, w) - 1))          # a small map keeps its middle
    edge = np.where((dx_ < R) & (dy_ < R),
                    R - np.hypot(R - dx_, R - dy_), np.minimum(dx_, dy_))
    c = edge - float(isl.rim_m)
    rim = c < 0.0
    e = np.where(rim, -c, np.minimum(e, c))

    if isl.wobble_m > 0:
        from .terrain import fbm
        rng = np.random.default_rng(stream_seed("islands", spec.seed))
        e = e + (fbm(rng, h, w, octaves=3, base_cells=28, gain=0.5) - 0.5) \
            * 2.0 * float(isl.wobble_m)
    return e, rim


def profile(spec: MapSpec) -> Tuple[np.ndarray, np.ndarray]:
    """``(t, rim)``: the 0..1 wall profile and the rim mask, vertex grid.

    The lip is sharp and the foot is not: `map_a2`'s walls drop 30-60 m in the
    first 6 m and run out over the next 6-12, which is ``t ** 1.5`` near enough.
    The run itself wanders between 0.6 and 1.4 of ``wall_m`` so the wall is not
    one extruded section all the way round.
    """
    isl = spec.islands
    e, rim = edge_distance(spec)
    from .terrain import fbm
    rng = np.random.default_rng(stream_seed("islands-wall", spec.seed))
    run = float(isl.wall_m) * (0.6 + 0.8 * fbm(rng, *e.shape, octaves=2,
                                                base_cells=20, gain=0.5))
    lip = float(isl.gap_m) / 2.0
    t = np.clip((e - (lip - run)) / np.maximum(run, 1e-6), 0.0, 1.0)
    return t ** 1.5, rim


def berm(spec: MapSpec, built_distance=None) -> np.ndarray:
    """Height to ADD along the lips, cm, vertex grid -- `IslandsSpec.berm_cm`.

    A hump that peaks a third of the way in from the lip and is gone by
    ``berm_m``, broken by noise into separate rocks (about a third of the coast
    has none), and pressed flat within 12 m of anything levelled -- a road, a
    plaza, a pad (``built_distance``, tiles) -- so the way to a bridge head is
    open. The bridge fit levels its own approaches afterwards.
    """
    isl = spec.islands
    e, rim = edge_distance(spec)
    if isl.berm_cm <= 0 or isl.berm_m <= 0:
        return np.zeros_like(e)
    from .terrain import fbm
    u = np.clip((e - float(isl.gap_m) / 2.0) / float(isl.berm_m), 0.0, 1.0)
    bump = np.sin(np.pi * u ** 0.6)
    rng = np.random.default_rng(stream_seed("islands-berm", spec.seed))
    n = fbm(rng, *e.shape, octaves=3, base_cells=14, gain=0.55)
    n = np.clip((n - 0.38) / 0.42, 0.0, 1.0) ** 1.3
    out = float(isl.berm_cm) * bump * n
    out[rim] = 0.0                                # the rim has the border ridge
    if built_distance is not None:
        h, w = e.shape
        rd = built_distance[::2, ::2]
        keep = np.ones_like(e)
        hh, ww = min(h, rd.shape[0]), min(w, rd.shape[1])
        k = np.clip((rd[:hh, :ww] - 2.0) / 10.0, 0.0, 1.0)
        keep[:hh, :ww] = k * k * (3.0 - 2.0 * k)
        out *= keep
    return out


def void_tiles(t: np.ndarray, shape) -> np.ndarray:
    """Tile mask of everything that is not a top: walls and bed."""
    h, w = shape
    cell = t[:h // 2, :w // 2] < 1.0
    # a tile is void if any vertex of its cell is off the top
    cell = cell | (t[1:h // 2 + 1, :w // 2] < 1.0) | (t[:h // 2, 1:w // 2 + 1] < 1.0) \
        | (t[1:h // 2 + 1, 1:w // 2 + 1] < 1.0)
    return np.repeat(np.repeat(cell, 2, axis=0), 2, axis=1)[:h, :w]

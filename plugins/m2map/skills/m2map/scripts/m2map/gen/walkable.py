"""Where the player can actually stand.

Slope alone does not answer this, and the difference is visible from the air.
A flat shelf on top of a cliff is gentle ground the player can never reach, and
a generator that blocks on slope leaves it walkable -- so it gets ground texture
and reads as a sandy plateau floating above the mountains.

Ymir does not leave any. Measured over five maps, the block rate on the outer
64 m ring and within the ring by height band:

    map                     ring    low 1/3   mid 1/3   high 1/3
    metin2_map_a1            97%       97%       93%      100%
    metin2_map_n_desert_01   96%       87%      100%      100%
    metin2_map_b1            98%      100%       94%      100%
    metin2_map_c1            99%      100%       96%      100%
    metin2_map_a3            96%       88%      100%      100%

**The high third of the rim is 100% blocked on every one.** The crest is sealed
along with the faces -- the wall is blocked all the way over the top, not just
on its slopes.

And the corollary: ground that is walkable by slope but cut off from the rest of
the map barely exists in the corpus. As a share of the map, the largest
component's complement measures 0.01% on `metin2_map_a1`, 0.00% on
`metin2_map_n_desert_01`, 0.13% on `metin2_map_b1`, 0.02% on `metin2_map_c1`
and 0.02% on `metin2_map_a3`. Ymir leaves no stranded shelves at all.

So the rule this module implements: **blocked = too steep, or on the border
band, or unreachable from the playable interior.** Both the attr stage and the
texture stage read it, which is what keeps the rock skin and the collision map
on the same footprint.
"""

from __future__ import annotations

import numpy as np

from .spec import MapSpec


def _grow(mask: np.ndarray) -> np.ndarray:
    out = mask.copy()
    out[1:, :] |= mask[:-1, :]
    out[:-1, :] |= mask[1:, :]
    out[:, 1:] |= mask[:, :-1]
    out[:, :-1] |= mask[:, 1:]
    return out


def reachable(free: np.ndarray, seed: np.ndarray | None = None) -> np.ndarray:
    """The playable interior: the LARGEST 4-connected component of ``free``,
    or the one holding ``seed`` when a seed is given.

    It used to be the component nearest the map centre, on the grounds that the
    centre is always playable. A moat through the middle of the map disproves
    that: the nearest free cell was the flat river bed between its two walls, so
    the channel became "the interior" and both banks were sealed as stranded --
    99% of the map blocked and painted rock. The corpus figure this module
    quotes is about the largest component, so that is what it keeps.

    The centre-nearest component is still tried first, because it nearly always
    IS the largest and one flood then settles it.
    """
    h, w = free.shape
    if not free.any():
        return np.zeros_like(free)

    def flood(start: np.ndarray) -> np.ndarray:
        seen = start & free
        frontier = seen.copy()
        while frontier.any():
            frontier = _grow(frontier) & free & ~seen
            seen |= frontier
        return seen

    if seed is not None and (seed & free).any():
        return flood(seed)

    left = free.copy()
    best = np.zeros_like(free)
    best_n = 0
    while True:
        n_left = int(left.sum())
        if n_left <= best_n:                 # nothing unvisited can beat it
            return best
        ys, xs = np.nonzero(left)
        i = int(np.argmin((ys - h // 2) ** 2 + (xs - w // 2) ** 2))
        start = np.zeros_like(free)
        start[ys[i], xs[i]] = True
        comp = flood(start)
        n = int(comp.sum())
        if n > best_n:
            best, best_n = comp, n
        left &= ~comp


def terrain_block(spec: MapSpec, slope_deg: np.ndarray, shape, roads=None,
                  jitter: np.ndarray | None = None,
                  void: np.ndarray | None = None) -> np.ndarray:
    """The block mask that follows from terrain alone, in TILE space.

    Object footprints are added later by the attr stage; they are not terrain and
    the texture stage must not see them -- a barrel does not turn the sand under
    it into rock.

    ``roads`` is the corridor mask. A road is carved through the border band and
    over steep ground deliberately (`taste.md` §1.8: block rate inside a corridor
    is 5.9% against 69.4% beside it), so it is cleared here before reachability
    runs. Otherwise a route leaving the map is walled off at the rim and
    everything beyond the wall is judged unreachable.

    ``jitter`` is a field in [-1, 1] that wobbles the slope threshold, so the
    rock line reads as geology rather than as a contour of the terrain. The band
    is a quarter of the threshold: on a 25 degree cut, rock starts at 19 and is
    certain by 31. The texture stage passes one; the attr stage does not, and
    must not -- collision has to be reproducible from the slope alone.
    """
    h, w = shape
    sl = _upsample(slope_deg, h, w)
    cut = float(spec.block_slope_deg)
    if jitter is not None:
        cut = cut + max(2.0, cut * 0.25) * np.clip(jitter, -1.0, 1.0)
    blocked = sl > cut

    b = max(0, int(spec.border_band_m))
    if b:
        blocked[:b, :] = True
        blocked[-b:, :] = True
        blocked[:, :b] = True
        blocked[:, -b:] = True

    free = ~blocked
    if roads is not None:
        free |= roads

    keep = reachable(free)
    # Anything walkable-by-slope but cut off from the playable interior is
    # sealed. In the corpus this set is 0.00-0.13% of a map, because Ymir does
    # not leave stranded shelves; here it is what closes the top of the border
    # ridge, whose crest is flat and would otherwise read as a sandy plateau
    # above the mountains.
    stranded = free & ~keep
    blocked |= stranded
    if roads is not None:
        blocked &= ~roads
    # Between mesas (`IslandsSpec`) a road is a route only as far as the lip. It
    # still joins the islands above -- that is what makes the far one reachable
    # -- but the canyon under it is wall and bed, blocked and rock; the deck of
    # the bridge is opened by the attr stage and nothing else is.
    if void is not None:
        blocked |= void
    return blocked


def _upsample(grid: np.ndarray, h: int, w: int) -> np.ndarray:
    gh, gw = grid.shape
    ys = np.clip((np.arange(h) * gh) // max(1, h), 0, gh - 1)
    xs = np.clip((np.arange(w) * gw) // max(1, w), 0, gw - 1)
    return grid[np.ix_(ys, xs)]

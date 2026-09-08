"""Stage 5 -- textureset + tile.raw.

The single most important thing this stage gets right is that **Ymir's ground is
a dither, not a set of regions**. Measured over 114 maps:

* median run length of a texture index along either axis: **2 tiles**
* half of all connected components are a **single tile**
* 22.5% of slots retain under 10% of their area after opening -- they exist only
  as dither partners and never form geometry
* the splat is painted at **1 m tile** resolution, not the 2 m terrain cell
  (``transition_odd_x_bias`` 0.499, flat across every map)
* a map uses a median of 7 slots while declaring 10

So the model is: **smooth fields decide the local mixture, per-tile sampling
decides the pixel.** Region-fill-then-perturb-the-edges produces clean blobs with
noisy borders, which is the opposite of what the corpus looks like -- there the
interior is noisy and there are barely any borders at all.

Roads are painted here too, and they are *not* a special texture: no road, path,
trail or track texture exists in Ymir's art (all 355 distinct .dds searched).
``metin2_map_a1``'s road web is ``b/field/field 01.dds``, an ordinary ground
texture also used as ground elsewhere. Corridors are solid features painted with
whichever palette slot the spec nominates.
"""

from __future__ import annotations

from typing import List

import numpy as np

from ..codec import textureset as ts_codec
from .layout import Layout
from .spec import MapSpec, SECTOR_TILES

#: tile.raw is stored 258x258 -- the usable 256x256 window plus a 1-tile skirt
#: that must mirror the neighbouring sector.
STORED = 258
USABLE = 256


def build_textureset(spec: MapSpec) -> ts_codec.TextureSet:
    """The palette.

    Slot 0 is the built-in eraser: it is never declared and ``TextureCount``
    excludes it, so ``slots[0]`` stays None and a ``tile.raw`` byte of 0 means
    "blank", not "the first texture".
    """
    slots: List[ts_codec.TextureEntry | None] = [None]
    for slot in spec.textures:
        slots.append(ts_codec.TextureEntry(
            filename=slot.path, u_scale=slot.u_scale, v_scale=slot.v_scale,
            u_offset=0.0, v_offset=0.0, b_splat=0, begin=0, end=0))
    return ts_codec.TextureSet(slots=slots, declared_count=len(spec.textures))


def _suitability(spec: MapSpec, lay: Layout, slope: np.ndarray,
                 height: np.ndarray, wet: np.ndarray) -> np.ndarray:
    """Per-slot preference field, shape ``(n_slots, h, w)``, before sampling.

    Every term here is a *smooth* function of terrain. All the high-frequency
    character comes from the sampling step, never from the fields.
    """
    h, w = lay.shape
    n = len(spec.textures)
    scores = np.zeros((n, h, w), np.float64)

    hi = max(1.0, float(height.max()) - float(height.min()))
    norm_h = (height - float(height.min())) / hi
    norm_s = np.clip(slope / 45.0, 0.0, 1.0)

    for i, slot in enumerate(spec.textures):
        role = slot.role
        s = np.full((h, w), float(slot.weight))
        if role == "base":
            s *= 1.0 - 0.6 * norm_s
        elif role == "mid":
            s *= 0.35 + 0.9 * norm_s * (1.0 - norm_s) * 4.0 * 0.25
        elif role == "cliff":
            s *= 0.05 + 2.5 * np.clip((slope - 22.0) / 25.0, 0.0, 1.0)
        elif role == "shore":
            s *= 0.05 + 2.0 * wet.astype(np.float64)
        elif role == "accent":
            s *= 0.25 * (0.5 + norm_h)
        elif role == "interior":
            s *= 1.0
        # `path` slots are painted as solid features, never sampled
        if role == "path":
            s *= 0.0

        for kind, mask in lay.regions.items():
            if kind == "forest" and role in ("base", "mid"):
                s = np.where(mask, s * 1.25, s)
            elif kind == "rocky" and role in ("cliff", "mid"):
                s = np.where(mask, s * 1.8, s)
            elif kind == "settlement" and role == "base":
                s = np.where(mask, s * 1.4, s)
        scores[i] = s
    return scores


def build(spec: MapSpec, lay: Layout, height_cm: np.ndarray,
          slope_deg: np.ndarray, wet: np.ndarray) -> np.ndarray:
    """Whole-map tile index grid, ``(h_tiles, w_tiles)`` uint8.

    ``height_cm`` and ``slope_deg`` arrive on the terrain vertex grid (2 m) and
    are upsampled here; the splat itself is decided at 1 m.
    """
    h, w = lay.shape
    if not spec.textures:
        return np.zeros((h, w), np.uint8)

    if spec.is_box():
        # Interiors are a single texture over the whole floor. dungeon_block
        # palettes hold as few as 1 slot and cover 100% of their tiles with it.
        return np.ones((h, w), np.uint8)

    slope = _upsample(slope_deg, h, w)
    height = _upsample(height_cm, h, w)

    rng = np.random.default_rng(abs(hash(("texture", spec.seed))) % (2 ** 32))

    scores = _suitability(spec, lay, slope, height, wet)

    # Patchiness. Without this the terrain fields alone vary far too slowly, so
    # one slot wins almost everywhere and the result is a single base colour with
    # uniform pepper on top -- base share 0.61 against the corpus median 0.52.
    # A mid-frequency field per slot makes the local MIXTURE wander, which is
    # what produces the corpus's patchy character.
    from .terrain import fbm  # local import: terrain does not depend on texture
    for i in range(len(spec.textures)):
        if spec.textures[i].role == "path":
            continue
        patch = fbm(rng, h, w, octaves=3, base_cells=48, gain=0.55)
        scores[i] *= 0.35 + 1.65 * patch

    scores = np.maximum(scores, 0.0)
    scores = _fit_shares(scores, spec)
    total = scores.sum(axis=0)
    total[total <= 0] = 1.0
    prob = scores / total

    # Per-tile categorical sampling, on a SLIGHTLY correlated draw field.
    # Fully independent draws give run length 1 -- pure white noise. The corpus
    # measures a median run of 2 with half of all components a single tile,
    # which is a lightly smoothed draw, not an independent one.
    draw = rng.random((h, w))
    # More slots means more chances for neighbouring tiles to disagree, so a
    # fixed softening that gives run length 2 on a 6-slot palette gives 1 on a
    # 17-slot one. Scale with the EFFECTIVE slot count (Simpson diversity of the
    # mean probabilities), not the declared count -- a map declaring 17 while
    # three slots hold 90% of the ground behaves like a 3-slot map.
    mean_p = prob.mean(axis=(1, 2))
    effective = 1.0 / max(1e-9, float((mean_p ** 2).sum()))
    # One softening pass is not enough past ~6 effective slots: with 16 bins each
    # spanning about 1/16 of the draw range, neighbouring tiles cross a boundary
    # even when their draws are close. Passes, not weight, is the lever -- each
    # pass widens the correlation radius by a tile.
    passes = int(np.clip(round(effective / 3.0), 1, 5))
    for _ in range(passes):
        draw = _soften(draw, weight=0.65)
    cum = np.cumsum(prob, axis=0)
    idx = (draw[None, :, :] > cum).sum(axis=0)
    tiles = np.clip(idx, 0, len(spec.textures) - 1).astype(np.uint8) + 1

    # Solid features last so they overwrite the field rather than dither with it.
    for corr in lay.corridors:
        band = np.clip(corr.tile_index, 1, len(spec.textures))
        tiles[corr.core] = band
        # The fringe dithers between corridor and surroundings, which is how the
        # corpus transitions: a hard edge reads as a decal laid on the ground.
        fr = corr.fringe & ~corr.core
        if fr.any():
            coin = rng.random((h, w)) < 0.45
            tiles[fr & coin] = band

    return tiles


def _fit_shares(scores: np.ndarray, spec: MapSpec, iterations: int = 40
                ) -> np.ndarray:
    """Scale each slot so its achieved ground share matches its ``weight``.

    Without this, ``weight`` is a nudge whose real effect depends on how the
    terrain terms happen to interact, and the dominant slot runs away with the
    map -- measured base share 0.70 against the corpus median 0.52. Iterative
    proportional fitting makes the weights mean what they say: normalised, they
    ARE the intended coverage.

    Slots the terrain gates (cliff on steep ground, shore on wet) keep their
    gating -- fitting only redistributes within where each is allowed to appear,
    so a cliff texture on a flat map stays rare rather than being forced to its
    nominal share.
    """
    n = scores.shape[0]
    target = np.array([max(1e-6, s.weight) for s in spec.textures], float)
    # `path` slots are painted as solid features and must not claim field share.
    for i, slot in enumerate(spec.textures):
        if slot.role == "path":
            target[i] = 1e-9
    target /= target.sum()

    gain = np.ones(n)
    for _ in range(iterations):
        adj = scores * gain[:, None, None]
        tot = adj.sum(axis=0)
        tot[tot <= 0] = 1.0
        share = (adj / tot).mean(axis=(1, 2))
        share[share <= 0] = 1e-9
        ratio = target / share
        if np.all(np.abs(ratio - 1.0) < 0.02):
            break
        gain *= np.clip(ratio, 0.5, 2.0) ** 0.5     # damped, or it oscillates
    return scores * gain[:, None, None]


def _soften(draw: np.ndarray, weight: float = 0.5) -> np.ndarray:
    """Blend each draw with its 4-neighbourhood.

    Lengthens runs from 1 to about 2 without turning the field into blobs: at
    ``weight`` 0.5 a tile still disagrees with its neighbour often enough that
    half of all connected components stay a single tile, which is what the
    corpus shows.
    """
    out = draw.copy()
    out[1:-1, 1:-1] = (draw[1:-1, 1:-1] * (1 - weight) +
                       weight * 0.25 * (draw[:-2, 1:-1] + draw[2:, 1:-1] +
                                        draw[1:-1, :-2] + draw[1:-1, 2:]))
    return out


def _upsample(grid: np.ndarray, h: int, w: int) -> np.ndarray:
    """Terrain vertex grid (2 m) -> tile grid (1 m), nearest neighbour."""
    gh, gw = grid.shape
    ys = np.clip((np.arange(h) * gh) // max(1, h), 0, gh - 1)
    xs = np.clip((np.arange(w) * gw) // max(1, w), 0, gw - 1)
    return grid[np.ix_(ys, xs)]


def to_sector_raw(tiles: np.ndarray, cx: int, cy: int) -> np.ndarray:
    """The 258x258 ``tile.raw`` block for one sector.

    The usable 256x256 window sits at ``[1:257, 1:257]``. The surrounding skirt
    mirrors the neighbouring sector, which is why this reads from the shared
    whole-map grid with one tile of overlap instead of slicing a 256 block: a
    per-sector generator has to reconcile the skirt afterwards and the corpus
    shows the editor does not reliably manage it (46% of adjacent pairs
    disagree, which is why the audit rule for this is INFO not ERROR).
    """
    h, w = tiles.shape
    y0, x0 = cy * SECTOR_TILES, cx * SECTOR_TILES
    ys = np.clip(np.arange(y0 - 1, y0 + USABLE + 1), 0, h - 1)
    xs = np.clip(np.arange(x0 - 1, x0 + USABLE + 1), 0, w - 1)
    return tiles[np.ix_(ys, xs)].astype(np.uint8)


def stipple_stats(tiles: np.ndarray) -> dict:
    """The statistics the corpus was measured on, for verifying our own output."""
    runs: List[int] = []
    for row in tiles[:: max(1, tiles.shape[0] // 64)]:
        cur, n = row[0], 1
        for v in row[1:]:
            if v == cur:
                n += 1
            else:
                runs.append(n)
                cur, n = v, 1
        runs.append(n)
    used = np.unique(tiles)
    counts = np.bincount(tiles.ravel(), minlength=int(tiles.max()) + 1)
    share = counts / max(1, tiles.size)
    return {
        "used_slots": int(used.size),
        "run_length_median": float(np.median(runs)) if runs else 0.0,
        "base_share": float(share.max()),
        "slot_share": {int(i): round(float(s), 4)
                       for i, s in enumerate(share) if s > 0},
    }

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

**That is true of `mid` and `accent` and of nothing else.** Solidity by role over
the outdoor corpus -- the share of a slot's tiles surviving one erosion:

    base 62.7%   shore 72.7%   path 56.0%   cliff 27.2%   mid 17.8%   accent 5.1%

So the base lays down as a carpet (`base_carpet`), the rock as a massif
(`cliff_massif`), and the mids stipple in what is left. Sampling all three the
same way gave a base of 13% solid against the corpus's 63%, and the render read
as camouflage rather than ground. `metin2_n_desert1` is the clearest case:
`sand01` 31.3% at solid **93.6%**, with `sand02` 26.2% at 1.2% and `sand03`
26.4% at 0.8% interleaving in the gaps.

Roads are painted here too, and they are *not* a special texture: no road, path,
trail or track texture exists in Ymir's art (all 355 distinct .dds searched).
``metin2_map_a1``'s road web is ``b/field/field 01.dds``, an ordinary ground
texture also used as ground elsewhere. Corridors are solid features painted with
whichever palette slot the spec nominates.
"""

from __future__ import annotations

import math
from typing import List

import numpy as np

from ..codec import textureset as ts_codec
from .layout import Layout
from .spec import MapSpec, SECTOR_TILES, stream_seed

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


#: How far from water a `shore` overlay may reach, in 1 m tiles. Corpus:
#: `beach sand 01` has 100% of its tiles within 4 m of water and >=70% of all
#: shore tiles are; 6 leaves room for the plane's overrun past the basin.
SHORE_BAND_TILES = 6


def _tex_key(path: str) -> str:
    return str(path).replace("\\", "/").strip().lower()


def paint_ground_stamps(spec: MapSpec, tiles: np.ndarray = None) -> List[str]:
    """Paint `spec.ground_stamps` into ``tiles``; return one log line per stamp.

    Matching is by texture path against the map's own palette. A texture the
    palette does not declare is skipped, never substituted: the wrong dirt is
    worse than none, and the line says which slot to add. Called with
    ``tiles=None`` it only reports.
    """
    slot_of = {_tex_key(t.path): i for i, t in enumerate(spec.textures, start=1)}
    lines = []
    for gs in spec.ground_stamps:
        painted, missing = 0, {}
        ax, ay = gs.anchor[0] + gs.origin_m[0], gs.anchor[1] + gs.origin_m[1]
        for j, row in enumerate(gs.rows):
            ty = int(math.floor(ay + j + 0.5))
            for i, ch in enumerate(row):
                if ch == "-":
                    continue
                tex = gs.palette[int(ch, 36)]
                slot = slot_of.get(_tex_key(tex))
                if slot is None:
                    missing[tex] = missing.get(tex, 0) + 1
                    continue
                tx = int(math.floor(ax + i + 0.5))
                if tiles is not None and 0 <= ty < tiles.shape[0] and 0 <= tx < tiles.shape[1]:
                    tiles[ty, tx] = slot
                painted += 1
        line = "ground: %s painted %d tiles" % (gs.label or "set-piece", painted)
        for tex, n in sorted(missing.items()):
            line += "; no slot for %s (%d tiles skipped)" % (tex, n)
        lines.append(line)
    return lines


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

        if slot.region:
            gate = lay.regions.get(slot.region)
            s = s * gate if gate is not None else s * 0.0

        for kind, mask in lay.regions.items():
            if kind == "forest" and role in ("base", "mid"):
                s = np.where(mask, s * 1.25, s)
            elif kind == "rocky" and role in ("cliff", "mid"):
                s = np.where(mask, s * 1.8, s)
            elif kind == "settlement" and role == "base":
                s = np.where(mask, s * 1.4, s)
            elif kind == "oasis" and role in ("shore", "accent"):
                # The green apron. `metin2_map_n_desert_01` rings its oasis with
                # grass and damp sand over the whole basin, not just at the
                # waterline -- a band tens of metres wide that fades into dry
                # sand. Without a region to name it, a water-gated shore slot
                # only ever reaches a few tiles out.
                s = np.where(mask, s * 12.0, s)
        scores[i] = s
    return scores


def build(spec: MapSpec, lay: Layout, height_cm: np.ndarray,
          slope_deg: np.ndarray, wet: np.ndarray,
          submerged: np.ndarray | None = None) -> np.ndarray:
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
    # What is actually under water, which is wider than the authored basin once
    # the plane overruns its shore (gen/water.py). Ground under water is not
    # ground: no rock skin, no green apron, no damp rim.
    water = wet if submerged is None else (wet | submerged)

    rng = np.random.default_rng(stream_seed("texture", spec.seed))

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
        # Only for the roles that form REGIONS. A wandering mixture is what
        # gives the base carpet and the rock its shape; applied to the mids it
        # gathers them into broad patches instead of letting them interleave,
        # and those patches are what read as dark shapes on open ground. Corpus
        # mid solidity is 1-18% (median 17.8); with the patch field on the mids
        # the generator sat at 32%.
        if spec.textures[i].role not in ("base", "cliff", "shore"):
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

    # The base lays down as a carpet first, and the mids sample only in the
    # gaps -- see `base_carpet`. Painting it into the same categorical draw as
    # the mids is what made every slot equally dithered.
    base_slots = [i for i, sl in enumerate(spec.textures, start=1)
                  if sl.role == "base"]
    if base_slots:
        carpet = base_carpet(spec, scores, rng)
        if carpet.any():
            if len(base_slots) == 1:
                tiles = np.where(carpet, np.uint8(base_slots[0]), tiles)
            else:
                sub = np.stack([np.maximum(scores[i - 1], 1e-9) for i in base_slots])
                sub /= sub.sum(axis=0)
                pick = (draw[None, :, :] > np.cumsum(sub, axis=0)).sum(axis=0)
                chosen = np.take(np.array(base_slots, np.uint8),
                                 np.clip(pick, 0, len(base_slots) - 1))
                tiles = np.where(carpet, chosen, tiles)
            # Everything outside the carpet is repainted as fine stipple --
            # not just the tiles the carpet displaced. The main categorical draw
            # is a smoothed field weighted by the fitted scores, and left in
            # place it keeps the heavier mid in broad coherent regions: measured
            # sand02 at 26% solid with 27% of its tiles in one component, where
            # `metin2_n_desert1` has 1.2% and a largest component of a few
            # tiles. Those regions are the dark shapes that appear on open
            # ground.
            #
            # MIDS ONLY. Accents and shore are overlaid afterwards at their own
            # rates and with their own gates; letting them fill the gap made
            # them ground cover, which they are not.
            gaps = ~carpet
            mid_slots = [i for i, sl in enumerate(spec.textures, start=1)
                         if sl.role == "mid"]
            if gaps.any() and mid_slots:
                wts = np.array([max(1e-9, spec.textures[i - 1].weight)
                                for i in mid_slots], float)
                wts /= wts.sum()
                # Barely softened. Fully independent draws give a run length of
                # 1 -- white noise -- against the corpus median of 2; one pass
                # at 0.25 restores the run without gathering the mids into
                # patches (measured solidity 4.8% and 9.7%, inside the corpus
                # mid band of 4.7-35.2%).
                alt_draw = _soften(rng.random((h, w)), weight=0.25)
                pick = np.clip(np.searchsorted(np.cumsum(wts), alt_draw),
                               0, len(mid_slots) - 1)
                tiles = np.where(gaps,
                                 np.take(np.array(mid_slots, np.uint8), pick),
                                 tiles)
            elif gaps.any() and len(base_slots) == 1:
                # No mids at all: the base owns the whole ground.
                tiles = np.where(gaps, np.uint8(base_slots[0]), tiles)

    # `shore` and `accent` are overlays, not ground. Each is sprinkled at its
    # declared share over the tiles its own suitability field allows -- shore
    # only near water (>=70% of corpus shore tiles are within 4 m of it), accent
    # anywhere, at under 1.5% cover and a corpus median solidity of 5.1%.
    for i, slot in enumerate(spec.textures, start=1):
        if slot.fringe_of:
            continue                    # painted as a rim, below
        if slot.role not in ("shore", "accent") or slot.weight <= 0:
            continue
        field = scores[i - 1]
        allowed = field > 1e-6
        if slot.role == "shore" and not slot.region:
            # At the water, and only there. The suitability keeps a small floor
            # away from it, and the rate below is normalised by the MEAN of the
            # field: on a map with one pond the floor is the mean, so the beach
            # was sprinkled at its full weight over the whole map. `weight` is
            # the share of this band, not of the map.
            #
            # Measured from what is SUBMERGED, not from the authored basin: the
            # surface sits inside its bowl (rule 22), so a band around the
            # polygon is a pale ring round a green crater, 5-10 m from the
            # waterline it is meant to be. The dry rim of the bowl is beach.
            surf = submerged if submerged is not None and submerged.any() else water
            if surf is None or not surf.any():
                continue
            allowed &= _dilate(surf, SHORE_BAND_TILES) & ~surf
        elif water is not None:
            allowed &= ~water
        if not allowed.any():
            continue
        # Density FOLLOWS the suitability field rather than being uniform over
        # it. A flat rate spreads an overlay evenly wherever it is permitted, so
        # a shore texture gated on "near water" appears as often 10 m inland as
        # at the edge, and a green apron cannot be concentrated on the oasis at
        # all -- the corpus paints a dense band at the waterline that thins
        # outward. Scaling the field so its mean over the allowed area equals
        # the declared weight keeps the share while restoring the gradient.
        rate = float(np.clip(slot.weight, 0.0, 1.0))
        norm = field / max(1e-9, float(field[allowed].mean()))
        p_hit = np.clip(norm * rate, 0.0, 1.0)
        # Threshold a COHERENT field, not per-tile noise. Independent draws give
        # a 50/50 pepper that reads as green dust settled on sand rather than as
        # grass growing in patches.
        #
        # Softening the draw instead does not work and the reason is worth
        # keeping: smoothing compresses a uniform field toward 0.5, so a
        # threshold of 0.22 fires far less often than 22% of the time -- the
        # apron came out completely empty. An fbm field keeps a broad marginal
        # while being spatially correlated, so the share survives the coherence.
        patch = fbm(rng, h, w, octaves=3, base_cells=10, gain=0.55)
        # RANK-transform it. `fbm` returns [0, 1] but its marginal is bunched
        # around the middle, so comparing it against a probability under-fires
        # badly -- a target share of 22% came out at 4%. Replacing each value by
        # its rank among the allowed cells makes the marginal uniform by
        # construction, so the threshold means what it says while the field
        # stays spatially correlated.
        rank = np.zeros((h, w))
        vals = patch[allowed]
        order = np.argsort(vals, kind="stable")
        r = np.empty(vals.size)
        r[order] = np.linspace(0.0, 1.0, vals.size, endpoint=False)
        rank[allowed] = r
        hit = allowed & (rank < p_hit)
        tiles = np.where(hit, np.uint8(i), tiles)

    # Fringe slots: the dithered band where one ground gives way to another.
    # `metin2_map_n_desert_01`'s oasis is one green over a solid apron with the
    # damp sand appearing only along its edge; painting that sand as a texture
    # in its own right instead spreads it over the bed and the shore, which is
    # both wrong and muddy. See `TextureSlot.fringe_of`.
    for i, slot in enumerate(spec.textures, start=1):
        if not slot.fringe_of:
            continue
        target = np.uint8(np.clip(slot.fringe_of, 1, len(spec.textures)))
        core = tiles == target
        if not core.any():
            continue
        steps = max(1, int(round(slot.fringe_width_m)))
        band = _dilate(core, steps) & ~_erode(core, 1)
        if water is not None:
            band &= ~water
        if slot.region:
            gate = lay.regions.get(slot.region)
            if gate is not None:
                band &= gate
        coin = rng.random((h, w)) < float(np.clip(slot.fringe_mix, 0.0, 1.0))
        tiles = np.where(band & coin, np.uint8(i), tiles)

    # The rock skin is region fill, not stipple -- see `cliff_massif`. Inside
    # the massif the cliff slots still dither AMONG THEMSELVES, which is how the
    # corpus reads: metin2_a2's stone01/stone02 pair is 45% / 20% of the same
    # rock face. So this only decides rock-versus-ground; which rock is still
    # the sampler's answer, re-drawn over the cliff slots alone.
    cliff_slots = [i for i, sl in enumerate(spec.textures, start=1)
                   if sl.role == "cliff"]
    if cliff_slots:
        massif = cliff_massif(spec, slope, rng,
                              slope_deg_src=slope_deg,
                              road_mask=lay.road_clear, void=lay.void)
        # A LAKE BED IS NOT ROCK. `taste.md` 1.10 says rock covers the ground the
        # player cannot walk on, and a basin floor qualifies -- it is blocked,
        # and after a scarp cuts it, steep. The rule was written about mountains
        # and it swallowed the water: 76% of the oasis bed came out stone03
        # against a hand-painted reference that is plainly sand. The bed keeps
        # whatever the ground carpet gave it.
        #
        # The sea between mesas is the exception the other way: `map_a2` paints
        # 99.9% of its submerged tiles `stone01`/`stone02`, the same rock as the
        # walls that run down into it. Only authored basins keep their bed.
        if water is not None and water.any():
            massif &= ~(water if lay.void is None else (water & ~lay.void))
        if massif.any():
            # ONE texture, flat across the whole face. See `dominant_cliff`.
            tiles = np.where(massif, np.uint8(dominant_cliff(spec)), tiles)
            # Ground must not survive inside the massif, and rock must not be
            # left scattered outside it -- the feather below puts back exactly
            # as much as the corpus measures.
            stray = np.isin(tiles, cliff_slots) & ~massif
            if stray.any():
                fallback = _dominant_non_cliff(spec)
                tiles = np.where(stray, np.uint8(fallback), tiles)

    # Feather before the solid features, so the rock tail never lands on a road
    # or inside a plaza. In the corpus it never does.
    tiles = _feather_massif(tiles, spec, rng)

    # The ground copied from under a set-piece: after the generated field, before
    # the map's own roads and plazas, which win where they cross it.
    paint_ground_stamps(spec, tiles)

    # Solid features last so they overwrite the field rather than dither with it.
    for corr in lay.corridors:
        band = np.clip(corr.tile_index, 1, len(spec.textures))
        # a road stops at the lip of a mesa; the bridge carries it, not the paint
        land = np.ones((h, w), bool) if lay.void is None else ~lay.void
        tiles[corr.core & land] = band
        # The fringe dithers between corridor and surroundings, which is how the
        # corpus transitions: a hard edge reads as a decal laid on the ground.
        # Measured blend band over the 37 confirmed road maps: median 3 m,
        # p25 1 m, p75 7 m, and `hard_edge` false on every one of them.
        fr = corr.fringe & ~corr.core & land
        if fr.any():
            coin = rng.random((h, w)) < 0.45
            tiles[fr & coin] = band
            # ...and a sibling of the road's own motif takes a smaller share of
            # the rim. This is the `field 01` core / `field 02` edge pairing
            # that `map_a2` enriches 23.9x. See `_fringe_partner`.
            partner = _fringe_partner(spec, int(band))
            if partner:
                coin2 = rng.random((h, w)) < 0.18
                tiles[fr & coin2 & ~coin] = partner

    # Plazas are the one place on an outdoor map where the dither is switched
    # off. Corpus discs measure solid 0.84-0.87 against 0.36-0.56 for a dirt
    # road in the same palette, so this is a flat fill with no coin toss in it.
    for pz in lay.plazas:
        if pz.tile_index:
            tiles[pz.mask] = np.clip(pz.tile_index, 1, len(spec.textures))

    return tiles


def _dominant_non_cliff(spec: MapSpec) -> int:
    """The slot stray rock is replaced with: the heaviest non-cliff ground.

    Not slot 1 -- slot 1 is frequently the road in a corpus-ordered palette, and
    replacing rock with road would carve tracks across the hillside.
    """
    best, best_w = 1, -1.0
    for i, sl in enumerate(spec.textures, start=1):
        if sl.role in ("cliff", "path"):
            continue
        if sl.weight > best_w:
            best, best_w = i, sl.weight
    return best


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


#: Filename motifs, longest first so ``beach sand`` wins over ``sand``.
#: Ymir names ground art by motif, and the motif carries a strong role prior.
#: Measured over the outdoor corpus, P(motif | role):
#:
#:   cliff  n=94   stone 62%  cliff 11%  other 9%  grass 4%  rock 4%
#:   path   n=28   tile 64%   field 18%  other 7%  sand 4%   grass 4%
#:   shore  n=20   sand 55%   field 15%  other 15% grass 15%
#:   mid    n=130  grass 35%  field 34%  tile 9%   sand 8%   stone 6%
#:
#: This is a PRIOR for picking a slot, not a classifier: what a slot actually
#: does is measured per (textureset, slot), and the same ``stone01.dds`` is
#: `base` in ``metin2_guild_war4`` and `cliff` in ``metin2_a1``.
#: See reference/textures.md sec 3 and sec 4f.
_MOTIFS = ("beach sand", "sand", "field", "grass", "stone", "cliff", "rock",
           "tile", "snow", "valcano", "lava", "ice", "water", "dirt")


def motif_of(path: str) -> str:
    """The art motif a texture filename claims, or ``""``.

    Used for choosing which slot a road dithers WITH, and for reporting. Never
    for deciding a slot's role -- the spec says that.
    """
    base = path.replace("\\", "/").rsplit("/", 1)[-1].lower()
    for m in _MOTIFS:
        if base.startswith(m):
            return "sand" if m == "beach sand" else m
    for m in _MOTIFS:
        if m in base:
            return "sand" if m == "beach sand" else m
    return ""


def _fringe_partner(spec: MapSpec, band: int) -> int:
    """The second texture a road rim dithers with, 1-based, or 0 for none.

    A corpus road is one texture down the middle and two at the rim. Ring-1
    share against the far field, over the 37 confirmed road maps:

    | motif at the rim | n | median enrichment |
    |---|---|---|
    | `tile` | 8 | 66.96 |
    | `field` | 24 | 2.23 |
    | `grass` | 46 | 2.16 |
    | `sand` | 10 | 0.74 |
    | `stone` | 32 | **0.52** |
    | `cliff` | 7 | **0.49** |

    Sharpest where the partner shares the road's own motif: ``map_a2`` paints
    ``a/field/field 01`` and enriches ``field 02`` at the rim **23.9x**;
    ``metin2_map_a1`` paints ``b/field/field 01`` and enriches ``field 04``
    4.8x. The cliff motifs are pushed AWAY (0.30-0.41) -- the same fact as
    "roads do not climb mountains", seen from the paint side.

    Prefer a sibling of the road's own motif; fall back to none, in which case
    the caller dithers the road colour into whatever ground is already there,
    which is the corpus's second-commonest rim (grass at 2.16x).
    """
    if not (1 <= band <= len(spec.textures)):
        return 0
    want = motif_of(spec.textures[band - 1].path)
    if not want:
        return 0
    # A `path` slot is a legitimate partner. It is never sampled into the
    # ground, so nominating it here paints it ONLY in the rim -- which is
    # exactly what `map_a2` does with `field 02` (0.015 of the ring-1 tiles,
    # enriched 23.9x, and essentially absent from the open field). Excluding
    # path slots left a single-ground-texture palette with no partner at all.
    for i, slot in enumerate(spec.textures, start=1):
        if i == band:
            continue
        if motif_of(slot.path) == want:
            return i
    return 0


def _dilate(mask: np.ndarray, steps: int = 1) -> np.ndarray:
    out = mask
    for _ in range(steps):
        nxt = out.copy()
        nxt[1:, :] |= out[:-1, :]
        nxt[:-1, :] |= out[1:, :]
        nxt[:, 1:] |= out[:, :-1]
        nxt[:, :-1] |= out[:, 1:]
        out = nxt
    return out


def _erode(mask: np.ndarray, steps: int = 1) -> np.ndarray:
    return ~_dilate(~mask, steps)


def _drop_islands(mask: np.ndarray, coarse: int = 4, min_blocks: int = 4
                  ) -> np.ndarray:
    """Remove massif fragments too small to read as rock.

    A 20-tile outcrop stranded in open field is the pepper artefact this whole
    stage exists to avoid, and it also wrecks the statistic: those fragments
    vanish under a 5x5 opening, so they count as raw cliff with no massif behind
    them and drag massif/raw from 0.86 down to 0.77.

    The corpus miner drops components under 30 tiles before measuring anything
    (``roads.json.method.constants.MIN_CORE_COMPONENT``); this is the same idea
    at the same scale -- 4 blocks of 4x4 is 64 tiles.

    Labelled on a ``coarse``-downsampled grid so a whole-map flood fill stays
    cheap on a 6x6 map (1,536^2 tiles becomes 384^2 blocks).
    """
    h, w = mask.shape
    ch, cw = (h + coarse - 1) // coarse, (w + coarse - 1) // coarse
    pad = np.zeros((ch * coarse, cw * coarse), bool)
    pad[:h, :w] = mask
    blocks = pad.reshape(ch, coarse, cw, coarse).any(axis=(1, 3))

    keep = np.zeros_like(blocks)
    seen = np.zeros_like(blocks)
    for sy, sx in zip(*np.nonzero(blocks)):
        if seen[sy, sx]:
            continue
        stack = [(sy, sx)]
        seen[sy, sx] = True
        comp = []
        while stack:
            y, x = stack.pop()
            comp.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < ch and 0 <= nx < cw and blocks[ny, nx] \
                        and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        if len(comp) >= min_blocks:
            for y, x in comp:
                keep[y, x] = True

    up = np.repeat(np.repeat(keep, coarse, axis=0), coarse, axis=1)[:h, :w]
    return mask & up


def _majority(mask: np.ndarray) -> np.ndarray:
    """Set each cell to the majority of its 3x3 neighbourhood.

    Cheaper and gentler than an open-then-close pair: it removes single-tile
    noise on a boundary without pulling the boundary inward, which erosion does
    and which would shrink every massif by a tile per pass.
    """
    a = mask.astype(np.uint8)
    acc = np.zeros(a.shape, np.uint8)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            acc += np.roll(np.roll(a, dy, axis=0), dx, axis=1)
    return acc >= 5


#: How much spatial noise is mixed into the slope score that decides the
#: massif. 0 would make the rock line a contour of the terrain, which reads as
#: machine-made; too much dissolves the massif back into pepper.
MASSIF_JITTER = 0.35


#: Spatial jitter mixed into the base carpet's threshold. Higher than the
#: massif's because the carpet answers to nothing but its own field -- there is
#: no slope ranking underneath it to keep the shape plausible.
#: Feature size of the carpet field, in tiles. The corpus base is ONE
#: percolating region -- its largest connected component holds 78% of the base
#: tiles on `metin2_map_a1`, 81% on `metin2_map_b1`, 51% on
#: `metin2_map_n_desert_01`. At 40 the threshold cut the field into separate
#: blobs tens of metres across, which is what scattered hard-edged dark shapes
#: over the walkable ground.
CARPET_CELLS = 140

CARPET_JITTER = 1.0


def base_carpet(spec: MapSpec, scores: np.ndarray, rng) -> np.ndarray:
    """Where the base texture lays down as solid ground.

    The `base` role is not a stipple partner. Measured over the outdoor corpus,
    the share of a slot's tiles surviving one erosion is **62.7%** median for
    `base` (p25 43.1, p75 74.3) against **17.8%** for `mid` and **5.1%** for
    `accent`. `metin2_n_desert1` is the extreme and the clearest: `sand01` 31.3%
    of the ground at solid **93.6%**, with `sand02` 26.2% at 1.2% and `sand03`
    26.4% at 0.8% interleaving in the gaps. That is a carpet plus a checkerboard,
    not three sands sampled against each other -- and sampling them the same way
    gave a base of 13.2% solid and a map that reads as camouflage.

    Shape comes from the slot's own suitability field, so the carpet still
    prefers the ground the spec says it should, plus a low-frequency jitter so
    the boundary is not a contour of the terrain.
    """
    base = [i for i, sl in enumerate(spec.textures, start=1) if sl.role == "base"]
    if not base:
        return np.zeros(scores.shape[1:], bool)
    # Against the MIDS only. `shore` is gated by water and `accent` is
    # decorative speckle -- neither competes with the base for ground cover, so
    # neither belongs in the split that decides how much ground the carpet
    # takes. Counting them shrank the carpet and handed the remainder to them,
    # which on a palette whose only ground texture is the base meant grass and
    # shoreline sand scattered over open desert.
    #
    # The corollary is the useful one: a palette with NO mids gives a carpet
    # that covers everything, which is how a map gets a single ground texture.
    share = sum(max(0.0, spec.textures[i - 1].weight) for i in base)
    mids = sum(max(0.0, sl.weight) for sl in spec.textures if sl.role == "mid")
    frac = float(np.clip(share / (share + mids), 0.0, 1.0)) if share > 0 else 0.0
    if frac <= 0.01:
        return np.zeros(scores.shape[1:], bool)
    if frac >= 0.999:
        return np.ones(scores.shape[1:], bool)

    from .terrain import fbm
    field = np.zeros(scores.shape[1:], np.float64)
    for i in base:
        field += scores[i - 1]
    hi = float(np.percentile(field, 99)) or 1.0
    score = np.clip(field / hi, 0.0, 1.0)
    h, w = score.shape
    score = score + CARPET_JITTER * (fbm(rng, h, w, octaves=2,
                                         base_cells=CARPET_CELLS,
                                         gain=0.5) - 0.5)
    mask = score >= float(np.quantile(score, 1.0 - frac))

    # Smooth only. No opening: a carpet is allowed thin arms and bays, and the
    # 5x5 opening the massif needs would eat them. Two majority passes take
    # solidity to roughly the corpus median without squaring the shape off.
    for _ in range(2):
        mask = _majority(mask)
    return mask


def cliff_massif(spec: MapSpec, slope: np.ndarray, rng,
                 slope_deg_src: np.ndarray | None = None,
                 road_mask: np.ndarray | None = None,
                 void: np.ndarray | None = None) -> np.ndarray:
    """Where the rock skin covers the ground: **everywhere the player cannot
    walk**.

    This is a walkability rule, not a share rule, and tying it to the same
    threshold the attr stage uses makes paint and collision agree by
    construction. Measured P(blocked | cliff-painted) over eight corpus maps:
    c1 0.99, map_a2 0.99, b1 0.98, a3 0.98, n_desert_01 0.97, a1 0.95, b3 0.95,
    mt_thunder 0.91. Stone is a subset of unwalkable ground on every one.

    The converse is looser -- P(cliff | blocked) runs 0.29 to 0.95 -- because
    block also covers object footprints, the border seal and steep grass. So the
    rule only runs one way, and `metin2_map_n_desert_01` is where the two masks
    very nearly coincide: IoU **0.93**.

    An earlier version ranked tiles by slope and took as many as the palette
    weights asked for. That produced rock in roughly the right places for the
    wrong reason, and it drifted off the block mask whenever the weights and the
    terrain disagreed -- stone on ground the player could walk, sand on cliffs
    they could not.

    `taste.md` 1.5 -- ground is a per-tile stipple -- does not apply here.
    """
    cliff = [i for i, sl in enumerate(spec.textures, start=1) if sl.role == "cliff"]
    if not cliff:
        return np.zeros(slope.shape, bool)

    from .terrain import fbm
    from . import walkable
    h, w = slope.shape

    if spec.attr_style == "slope_driven":
        # The SHARED walkability mask, so the rock skin and the collision map
        # have the same footprint. Steep ground alone is not enough: the crest of
        # the border ridge is flat, so blocking on slope left it walkable, it
        # took ground texture, and it read as a sandy plateau sitting on top of
        # the mountains. Ymir seals the whole rim -- the high third of the outer
        # 64 m ring is 100% blocked on all five maps measured. See
        # `gen/walkable.py`.
        jitter = (fbm(rng, h, w, octaves=3, base_cells=32, gain=0.55) - 0.5) * 2.0
        mask = walkable.terrain_block(
            spec, slope_deg_src if slope_deg_src is not None else slope,
            (h, w), roads=road_mask, jitter=jitter, void=void)
    else:
        # Interiors and painted_box maps have no slope rule to borrow, so fall
        # back to the palette's own weights: rank by slope, take the top share.
        share = sum(max(0.0, spec.textures[i - 1].weight) for i in cliff)
        total = sum(max(0.0, sl.weight) for sl in spec.textures
                    if sl.role != "path") or 1.0
        frac = float(np.clip(share / total, 0.0, 0.9))
        if frac <= 0.001:
            return np.zeros(slope.shape, bool)
        hi = max(1.0, float(np.percentile(slope, 99)))
        score = np.clip(slope / hi, 0.0, 1.0)
        score = score + MASSIF_JITTER * (fbm(rng, h, w, octaves=3, base_cells=32,
                                             gain=0.55) - 0.5)
        mask = score >= float(np.quantile(score, 1.0 - frac))

    for _ in range(2):
        mask = _majority(mask)

    # Minimum thickness, at the same 5x5 the massif/raw statistic is measured
    # with. Without it, ridges two or three tiles wide survive the smoothing and
    # die under the opening, which pinned the ratio at 0.78 with 2.4% of the
    # map's rock stranded in open field -- and no amount of tuning the feather
    # moved either number, because the feather was never the cause.
    mask = _dilate(_erode(mask, 2), 2)
    mask = _erode(_dilate(mask, 2), 2)
    return _drop_islands(mask)


def dominant_cliff(spec: MapSpec) -> int:
    """The single texture the massif interior is painted with, 1-based.

    The corpus does not dither the rock face. Share of the massif interior held
    by its commonest slot: `n_desert_01` **100%**, `map_a2` **100%**,
    `mt_thunder` 94%, `c1` 88%, `b1` 75%, `a3` 64%, `a1` 59%. Where a second
    slot appears at all it is a partner over the same face rather than a
    separate feature, and the rim is where the mixing happens -- the dominant
    slot goes from 4-17% one tile outside the massif to 63-99% at the rim.
    """
    best, best_w = 0, -1.0
    for i, sl in enumerate(spec.textures, start=1):
        if sl.role == "cliff" and sl.weight > best_w:
            best, best_w = i, sl.weight
    return best


#: Rock share in the first tile outside the massif, and its per-tile decay.
#: Fitted to the corpus tail in :func:`_feather_massif`, at the gentle end of
#: the measured range so the feather reads as grit and not as a second biome.
FEATHER_HEAD = 0.10
FEATHER_DECAY = 0.62
FEATHER_REACH = 8


def _feather_massif(tiles: np.ndarray, spec: MapSpec, rng) -> np.ndarray:
    """Speckle the rock texture out past the rim of the rock massif.

    Ymir's cliffs do not stop at a line. Opening the cliff mask with a 5x5 box
    to recover the massif -- so the measurement is not circular, which a first
    attempt binning distance from the cliff tiles themselves was -- and then
    reading the raw cliff share outward from that rim gives a decaying tail:

    | map | +1 m | +2 | +3 | +4 | +5 | +6 | far field |
    |---|---|---|---|---|---|---|---|
    | `metin2_map_a1` | 9.6% | 6.8 | 3.6 | 2.1 | 1.3 | 0.9 | **0.00%** |
    | `metin2_map_n_desert_01` | 4.9% | 3.4 | 2.7 | 1.9 | 1.4 | 1.2 | **0.06%** |
    | `metin2_map_b1` | 16.2% | 16.4 | 10.6 | 7.2 | 4.8 | 2.7 | **0.00%** |

    Two facts matter equally. The tail is real -- roughly geometric, five to
    seven tiles long. And it STOPS: the far field is 0.00%, so rock is never
    sprinkled over open ground as generic noise. A generator that dithers rock
    globally gets the first fact right and the second one badly wrong.

    ``map_a2`` is the instructive exception. Its cliff slot survives opening at
    only 0.2%, because ``a/stone/stone02.dds`` there is not a massif skin but a
    dither partner spread over the whole ``stone01`` base -- 40% near rock and
    17.9% in the far field. Where a palette works that way there is no massif
    to feather and this function correctly does almost nothing.
    """
    cliff = [i for i, sl in enumerate(spec.textures, start=1) if sl.role == "cliff"]
    if not cliff:
        return tiles
    mask = np.isin(tiles, cliff)
    massif = _dilate(_erode(mask, 2), 2)
    if not massif.any():
        return tiles
    out = tiles
    prev = massif
    for step in range(1, FEATHER_REACH + 1):
        cur = _dilate(massif, step)
        ring = cur & ~prev
        prev = cur
        if not ring.any():
            break
        p = FEATHER_HEAD * (FEATHER_DECAY ** (step - 1))
        pick = ring & (rng.random(tiles.shape) < p)
        if pick.any():
            # The lowest cliff index, not a random one: a multi-slot rock
            # palette should not scatter its rarest variant as far as its
            # commonest, and in the corpus the tail is the massif's own skin.
            out = np.where(pick, np.uint8(dominant_cliff(spec)), out)
    return out


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

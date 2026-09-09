# 03 -- `desert`

**Desert and desert frontier.** 10 maps (8 with own terrain), 99 sectors,
4,113 object placements. Reference map `metin2_map_n_desert_01`.

---

## Identity

Flat sun-bleached sand under a long warm haze, broken by dark rock scarps and planted
with dense low scrub. Nine of the ten members declare the same environment,
`milgyo.msenv` -- the second largest environment-sharing group in the corpus -- and its
signature is unmistakable: `Fog.NearDistance 1` (fog starts at the camera) with
`FarDistance 40,000-50,000 cm`, the longest sightlines in the game.

The terrain is the flattest of the four "open field" archetypes: slope p50 6.5 deg,
46.5 % of cells under 5 deg, and water cover **1.98 %** -- a fiftieth of `field_empire`'s.
The flora is exclusively the `n2_` arid SpeedTree set (CinnamonFern, AloeVera,
JoshuaTree, CurlyPalm, DatePalm, CoconutPalm); all 1,149 tree records in
`metin2_map_n_desert_01` are `n2_`. And the ground is the textbook
**base + double-dither**: one solid sand carpet with two sibling sand textures scattered
through it that have almost no interior at all.

The one thing that surprises people: **desert flora avoids water**, median distance to a
wet cell 20,009 cm (`placement.md` sec 5). The oases in this corpus are prop-decorated, not
planted.

---

## Reference maps

| Map | Size | Sectors | Textureset | Environment | Objects | Terrain |
|---|---|---|---|---|---|---|
| **`metin2_map_n_desert_01`** (reference) | 6x6 | 36 | `metin2_n_desert1.txt` | `milgyo.msenv` | 1,889 | own |
| `metin2_map_wl_01` | 4x4 | 16 | `metin2_wl_01.txt` | `milgyo.msenv` | 1,120 | own |
| `metin2_map_sungzi_desert_01` | 4x4 | 16 | `metin2_n_desert1.txt` | `milgyo.msenv` | 51 | own |
| `metin2_map_sungzi_desert_hill_01/02/03` | 2x4 | 8 each | `metin2_n_desert1.txt` | `milgyo.msenv` | 110 each | own (byte-identical triplet) |
| `metin2_map_nusluck01` | 2x2 | 4 | `metin2_wl_01.txt` | `milgyo.msenv` | 322 | own |
| `metin2_map_golden_land_stage` | 3x1 | 3 | `metin2_map_golden_land.txt` | `metin2_map_golden_land_stage.msenv` | 401 | own |
| `metin2_map_golden_land` | 2x1 | 0 | `metin2_map_golden_land.txt` | `metin2_map_golden_land.msenv` | 0 | `proxy:golden_land_stage` |
| `metin2_map_smhgate_desert` | 6x6 declared | 0 | `metin2_n_desert1.txt` | `milgyo.msenv` | 0 | `proxy:n_desert_01` |

- **Typical size 2x4**, **flagship 6x6**. Histogram: 2x1 x1, 2x2 x1, 2x4 x3, 3x1 x1,
  4x4 x2, 6x6 x2.
- `sungzi_desert_hill_01/02/03` are three byte-identical copies of one map, as are the
  `sungzi_flame_hill` and `sungzi_snow_pass` triplets in their archetypes. Two members
  ship zero sectors.

There are **two sub-recipes** here and they are visually different:

- the **pure desert** (`metin2_n_desert1.txt`, 6 maps) -- sand carpet, 79 % sand ground;
- the **vegetated frontier** (`metin2_wl_01.txt`, `wl_01` + `nusluck01`) -- a 17-slot
  palette that mixes A/B/C-empire stone and grass into the sand, with 80 % of `wl_01`'s
  451 tree records still `n2_`.

---

## Terrain

`style: sculpted` for `n_desert_01`, `nusluck01` and `wl_01`; the sungzi instances are
`box`-flat with painted collision. `stats-terrain.json` `by_archetype.desert`, 8 maps,
99 sectors.

| Quantity | Value |
|---|---|
| `height_range_cm` | 5,175.0 - 29,237.0; **p5 16,044**, p50 17,444, p95 22,836 |
| Relief per sector | p25 2,546 cm, **p50 6,824 cm**, p75 9,313 cm, p90 11,478 cm |
| `slope_p50` | **6.5 deg** |
| `slope_p95` | **66.3 deg** (p75 22.9 deg, p90 53.3 deg, mean 15.9 deg) |
| `flat_fraction` (< 5 deg) | **0.465** (< 2 deg 0.391, < 10 deg 0.576, < 20 deg 0.723) |
| `roughness` (abs Laplacian r=1) | **p50 7.5 cm**, p90 182.5, p99 1,280.5 |
| Local std 3x3 | p50 21.5 cm, p90 232.5 cm |
| Water cells | **1.98 %** |
| Blocked cells | 62.1 % |

The p5-to-p50 height spread is only 1,400 cm -- **the desert floor is a plateau**. Almost
all of the height variation lives above p50, in the scarps. The r=1 roughness median of
7.5 cm is the lowest of any outdoor archetype: the sand is genuinely smooth at 2 m scale,
and what looks like dune texture in game is the *ground stipple*, not geometry.

Generate: a near-flat pan at ~17,400 cm, a handful of 40-60 deg rock walls, and 3-5 m of
gentle undulation across the pan. Do not fractalise it.

---

## Textureset recipe

> **`sand02` and `sand03` do not hold up at generated UV scales.** The measured
> palette splits the ground `sand01` 31.3% / `sand02` 26.2% / `sand03` 26.4%, and
> reproducing that split produced blotches rather than sand on every attempt to
> tune it. Declare `sand01` alone as the `base` and let it carry the whole
> walkable surface; keep `stone03` for the rock, `field 01` for the road with
> `field 02` as its rim partner, `field 03` for the shore band and the grasses
> for the oasis rim. See `textures.md` §4c2.


Reference palette **`metin2_n_desert1.txt`**, 12 slots, measured on
`metin2_map_n_desert_01` and its five siblings (`textures.json`
`texturesets["metin2_n_desert1.txt"]`). `weight` = measured `ground_share`; sums to
1.000.

| slot | role | path | U/V | repeat | weight |
|---|---|---|---|---|---|
| 1 | `base` | `d:/ymir work/terrainmaps/n/desert/sand/sand01.dds` | 3/3 | 10.7 m | 0.313 |
| 2 | `mid` (dither) | `d:/ymir work/terrainmaps/n/desert/sand/sand02.dds` | 6/6 | 5.3 m | 0.262 |
| 3 | `mid` (dither) | `d:/ymir work/terrainmaps/n/desert/sand/sand03.dds` | 5/5 | 6.4 m | 0.264 |
| 4 | `path` / road | `d:/ymir work/terrainmaps/n/desert/field/field 01.dds` | 6/6 | 5.3 m | 0.022 |
| 5 | `accent` | `d:/ymir work/terrainmaps/n/desert/field/field 02.dds` | 9/9 | 3.6 m | 0.000 |
| 6 | `shore` | `d:/ymir work/terrainmaps/n/desert/field/field 03.dds` | 8/8 | 4.0 m | 0.001 |
| 7 | `cliff` | `d:/ymir work/terrainmaps/n/desert/stone/stone01.dds` | 4/4 | 8.0 m | 0.000 |
| 8 | `unused` | `d:/ymir work/terrainmaps/n/desert/stone/stone02.dds` | 4/4 | 8.0 m | 0.000 |
| 9 | `cliff` | `d:/ymir work/terrainmaps/n/desert/stone/stone03.dds` | 4/4 | 8.0 m | 0.124 |
| 10 | `accent` | `d:/ymir work/terrainmaps/n/desert/grass/grass 01.dds` | 4/4 | 8.0 m | 0.001 |
| 11 | `accent` | `d:/ymir work/terrainmaps/n/desert/grass/grass 02.dds` | 4/4 | 8.0 m | 0.007 |
| 12 | `cliff` | `d:/ymir work/terrainmaps/n/desert/grass/grass 03.dds` | 4/4 | 8.0 m | 0.005 |

**This is the clearest example of the stipple rule in the corpus.** `sand01` is the
carpet: 31.3 % cover, clump 7.81 of 8, **93.6 % of its tiles survive an erosion**.
`sand02` and `sand03` cover a comparable 26.2 % and 26.4 % at clump 4.00 and 4.01 with
**1.2 % and 0.8 % non-edge**. They are pure noise, sprinkled through `sand01` to hide its
10.7 m repeat. Paint them as regions and the map reads as three deserts sitting next to
each other (`textures.md` sec 6 `desert`).

`stone03` (slot 9) is the *solid* cliff: 12.4 % cover, clump 7.86, 94.6 % non-edge, mean
slope 46.3 deg. Its sibling `stone01` is declared and painted 0.03 %. The dark scarp is
one texture, and it is solid.

`n/desert/field/field 01.dds` (slot 4) is the road: 2.2 % cover, clump 6.09, 40 %
non-edge, mean slope 4.36 deg. Set `RoadSpec.tile_index = 4`.

**Alternate palettes.**

- `metin2_map_golden_land.txt` (12 slots, `golden_land` + `_stage`) has the same 12
  textures in the same order and collapses to a single carpet: `sand01` at **78.6 %**.
- `metin2_wl_01.txt` (17 slots, `wl_01` + `nusluck01`) inverts the pair -- `sand02` is the
  base at 47.2 % (clump 7.01, 71 % non-edge) and `sand01` is painted zero tiles. It
  imports `a/stone/stone01`, `a/stone/stone04`, `b/stone/stone01`, `b/stone/stone03_02`,
  `c/stone/c_stone04_bb`, `a/grass/grass 02` (its second base at 14.8 %),
  `a/grass/grass 03`, `a/field/field 05`, `ema1/*` and `g/field/field 06`. This is the
  vegetated frontier variant -- use it if the map is meant to border on green land. Note
  `textures.md` sec 3: the same file can be `base` in one map and `mid` in another; `sand02`
  is exactly that case.

**How the archetype paints** (`stats-tiles.json` `by_archetype.desert`):
role share **sand 78.5 %**, rock 13.8 %, grass 5.0 %, dirt 2.7 %, paved 0.00001;
base role is `sand` in all 8 maps; median 7.5 slots used of 12 declared (unused fraction
0.439); top-3 share median **0.985**; **dither-only tile share median 0.673** -- two
thirds of the ground is a slot that never forms geometry; `stipple_same_family_share`
0.381 (lower than the field archetypes because the wl_01 palette dithers across art
packs); singleton fraction of base 0.508.

---

## Environment

**Canonical `milgyo.msenv`** -- cluster C08 `sand_haze` -- on 8 of 10 maps. All three envs
in the archetype are C08; this is one of six **cluster-pure** archetypes in the corpus
(`environments.md` sec 5).

| Parameter | Observed over all 10 maps |
|---|---|
| `Fog.Enable` | 1 x10 |
| `Fog.NearDistance` | **1 cm** x10 -- fog starts at the camera |
| `Fog.FarDistance` | 40,000 - 50,000 cm (**median 50,000**) -- the longest in the corpus |
| `Fog.Color` | `#E6CDAC` (milgyo) / `#978572` (golden_land); hue 30.8-34.1 deg, sat 0.245-0.252 |
| `Background.Ambient` | `#C8B19C` (level 0.6967), also `#978E85`, `#746E6B` -- a high ambient floor |
| `Character.Ambient` | level 0.8467 = Background + 0.15 |
| `Background.Diffuse` | `#CAA891` (warmth 0.2235), also `#C8C3C1`, `#E1DDD8` |
| `Direction` | `0.596551 0.28178 -0.751483` (sun elev 48.7 deg, az 244.7 deg) x10 |
| Gradient | **Upper 5 / Lower 1** x10 |
| Sky zenith -> horizon -> nadir | `#2F0F05` -> `#D7C9B7` / `#A89274` -> `#AC977C` / `#61533F` |
| Cloud | `clouds_zone01.tga`, scale 200000, **texture scale 5**, **speed 0.01**, height 30000 |
| Skybox faces | none ; `Filter.Enable` 0 x10 |

The recipe is: haze that starts at zero, reaches half a kilometre, is warm and
high-value, and sits under a deep red-brown zenith over a bleached horizon, with the
ambient floor lifted to 0.70 so nothing goes dark. `FarDistance 50,000` also means the
client draws textured terrain out to 500 m -- that is two sectors of real geometry, and
it is the most expensive environment budget in the corpus. It is also what makes a
desert read as *open*.

---

## Object palette

**Density 6.34 obj/ha = 0.0634 per 100 m^2 = 41.5 per sector**, 307 distinct CRCs across
648.81 ha. Mix: Tree 49.8 %, Building 48.5 %, Effect 1.8 %
(`stats-objects.json` `by_archetype.desert`).

Family budget:

| Family | n | per ha | NN same-family p25/p50/p75 (cm) | Clark-Evans R |
|---|---|---|---|---|
| `tree/n2` | 1,864 | 2.87 | 181 / **342** / 724 | 0.244 clustered |
| `zone/b/obj` | 1,040 | 1.60 | 121 / **236** / 489 | 0.153 clustered |
| `zone/n/obj/map_n_desert_01` | 641 | 0.99 | 178 / **243** / 369 | 0.152 clustered |
| `zone/golden_land` | 114 | 0.18 | 275 / 381 / 1,279 | 0.091 |
| `tree/b3` | 109 | 0.17 | 898 / 1,802 / 3,519 | 0.268 |
| `zone/n/desert` | 101 | 0.16 | 174 / 1,056 / 1,483 | 0.148 |
| `zone/nusluck` | 87 | 0.13 | 245 / 426 / 1,560 | 0.089 |
| `effect/background` | 70 | 0.11 | 881 / 1,811 / 3,855 | 0.524 |

**`tree/n2` is not a forest.** Its same-family NN median is 342 cm -- four times tighter
than any temperate tree set. It is ground cover: ferns and aloe planted in dense mixed
patches. Reproducing it with the temperate 10-17 m spacing gives you an empty desert.

### Tier table (directly usable as `MapSpec.objects`)

`density` per 100 m^2; `spacing_cm` = NN(same CRC) p5; `max_slope` = per-CRC slope p95;
`road_clearance_cm` = per-CRC d(road) p25; `height_bias` = (bias p25, bias p75).
`on_tiles` indexes the 12-slot `metin2_n_desert1.txt` palette.

| tier | crc | name | density | spacing_cm | on_tiles | max_slope | road_clear_cm | height_bias | water_m |
|---|---|---|---|---|---|---|---|---|---|
| signature | 2958806645 | `CinnamonFern_RT_01` (Tree, `tree/n2`) | 0.00610 | 97 | 1,2,3,11 | 22 | 1047 | (-5, 0) | 51/204/314 **(51, inf)** |
| signature | 1453870486 | `CinnamonFern_RT_02` (Tree, `tree/n2`) | 0.00391 | 83 | 1,2,3,11 | 30 | 1009 | (-15, 0) | 2/120/262 **(2, inf)** |
| signature | 802175187 | `AloeVera_RT_Flowers_02` (Tree, `tree/n2`) | 0.00321 | 255 | 1,2,3,11 | 37 | 400 | (-25, -5) | 91/226/320 **(91, inf)** |
| signature | 1030411250 | `AloeVera_RT_Flowers_01` (Tree, `tree/n2`) | 0.00216 | 241 | 1,2,3,11 | 31 | 400 | (-25, -1) | 22/168/315 **(22, inf)** |
| signature | 2323701221 | `CinnamonFern_RT_03` (Tree, `tree/n2`) | 0.00162 | 83 | 1,2,3 | 25 | 2525 | (-15, 0) | 21/193/277 **(21, inf)** |
| signature | 1105271114 | `JoshuaTree_RT_01` (Tree, `tree/n2`) | 0.00129 | 1233 | 1,2,9 | 49 | 200 | (-827, -35) | 200/389/589 **(200, inf)** |
| signature | 1609982784 | `JoshuaTree_RT_03` (Tree, `tree/n2`) | 0.00113 | 636 | 1,2,9 | 55 | 50 | (-879, -60) | 180/350/592 **(180, inf)** |
| signature | 3498019135 | `JoshuaTree_RT_02` (Tree, `tree/n2`) | 0.00103 | 1249 | 1,2,9 | 59 | 200 | (-827, -60) | 183/304/452 **(183, inf)** |
| signature | 760653991 | `CurlyPalm_RT_03` (Tree, `tree/n2`) | 0.00120 | 3538 | 1,11 | 34 | 1131 | (-33, -5) | 99/237/366 **(99, inf)** |
| filler | 2157974046 | `general_obj_fence03.gr2` (Building, `zone/n/obj/map_n_desert_01`) | 0.00134 | 357 | 1,2,10,11 | 10 | 0 | (-25, 0) | 298/350/405 **(298, inf)** |
| filler | 2600313213 | `general_obj_fence02.gr2` (Building, same) | 0.00106 | 310 | 1,2,10,11 | 8 | 0 | (-15, 0) | 257/329/386 **(257, inf)** |
| filler | 3248083804 | `general_obj_fence04.GR2` (Building, same) | 0.00092 | 476 | 1,2,11 | 7 | 0 | (-20, 0) | 264/328/402 **(264, inf)** |
| filler | 311819914 | `general_obj_fence05.GR2` (Building, same) | 0.00074 | 636 | 1,2,11 | 3 | 0 | (-22, 0) | 262/326/400 **(262, inf)** |
| filler | 358206493 | `ob-b1-005-woodbarrel` (Building, `zone/b/obj`) | 0.00100 | 73 | 1,2,4 | 10 | 0 | (-5, 0) | 20/85/261 (0, inf) |
| filler | 538957537 | `general_obj_fence03` (Building, `zone/b/obj`) | 0.00088 | 335 | 1,2,4 | 24 | 447 | (-15, 0) | 12/51/134 (0, inf) |
| accent | 2108962507 | `DatePalm_RT_02` (Tree, `tree/n2`) | 0.00088 | 2246 | 1,11 | 31 | 1697 | (-82, -5) | 111/226/317 **(111, inf)** |
| accent | 2114741906 | `DatePalm_RT_01` (Tree, `tree/n2`) | 0.00082 | 2559 | 1,11 | 36 | 447 | (-108, -5) | 80/245/383 **(80, inf)** |
| accent | 3924497413 | `CurlyPalm_RT_01` (Tree, `tree/n2`) | 0.00089 | 2403 | 1,11 | 33 | 200 | (-40, 0) | 0/36/287 (0, inf) |
| accent | 104215490 | `CoconutPalm_RT_02` (Tree, `tree/n2`) | 0.00069 | 2287 | 1,2,10,11 | 37 | 350 | (-95, 0) | 0/6/132 (0, inf) |
| accent | 529292477 | `CoconutPalm_RT_01` (Tree, `tree/n2`) | 0.00069 | 1932 | 1,2,10,11 | 28 | 0 | (-72, 0) | 0/30/202 (0, inf) |

`water_m` = observed distance to the nearest water, p25/p50/p75 in metres (`affinity.json` `by_crc[crc].d_water_cm`; `~` = the family's figure where the CRC has none). The bold `(min, inf)` is the suggested `MapSpec.water_distance_m` for species that measurably avoid water. A species that tolerates it gets no constraint; give oasis or shore decoration a `(0, max)` band instead -- do NOT try to pin it to the shore texture, which is a stipple and covers only a handful of tiles.


`JoshuaTree_RT_03` carries `height_bias` p50 **-697 cm** -- the deepest sink of any CRC in
the corpus. Its model is authored well above its origin; without the sink it floats
seven metres in the air (`placement.md` sec 1.3). All three JoshuaTrees need bias in the
-830...-35 range and they are the only desert flora that likes rock (29-34 % of their
ground is rock, and their top textures are `mtthunder/mtthunder_stone02.dds`) -- plant
them on the scarps, not the pan.

`460 of the 1,122 records` in `zone/n/obj/map_n_desert_01` corpus-wide are fence CRCs
(`placement.md` sec 6). Fences run in sequences of 3-5 segments, roll almost never 0
(3-6 % zero-share).

---

## Placement rules

**Ground affinity** (`affinity.json` `by_archetype.desert`, n = 4,113):
**sand 64.0 %**, grass 24.9 %, field 8.2 %, rock 2.9 % -- and nothing else at all. Object
slope p50 0.92 deg, p75 9.77 deg, p95 29.45 deg.

**Positive rules**

1. **Plant in mixed patches, never as specimens.** The strongest co-occurrences in the
   archetype (`cooccurrence.json`, `placement.md` sec 6):
   `CinnamonFern_RT_02` + `_01` obs 300 at 5 m (x111); `_02` + `_03` obs 273 (x294);
   `AloeVera_RT_Flowers_01` + `CinnamonFern_RT_01` obs 120 (x153);
   `cactus_04` + `CinnamonFern_RT_01` obs 139 (x736); `cactus_04` + `cactus_05` obs 31
   (x2,653). A patch is 3-4 species inside a 2-5 m circle.
2. **Buildings 730 cm from a road, trees 2,400 cm** (`placement.md` sec 5).
3. Road grammar (pooled, see caveat): width median 6.0 m, road core fraction 0.053,
   density 7,625 m/km^2, tortuosity 1.25, 6.67 junctions/km, 1.03 loops/km, radius of
   curvature 32 m, **blend band 3.0 m** -- the widest transition band of any archetype,
   which is the sand feathering into the track.
4. **Fences carry the settlement.** 90 % of `zone/n/obj/map_n_desert_01` records sit on
   blocked attr; they are mostly fences and they run along the roads (d(road) p25 = 0,
   p50 = 200-283 cm).
5. **Sink the scrub lightly.** `tree/n2` bias median -15 cm -- the shallowest tree sink of
   any family. Only the JoshuaTrees go deep.
6. Effects are 1.8 % of placements -- the highest effect share of any *green* archetype,
   carried by `effect/background` at 0.11/ha with a regular-ish R of 0.524.

**Negative rules**

- **`tree/n2` is never placed on lava.** `tree/n2` on pavement: 1 record in 3,256
  corpus-wide (lift x0.009). Several members additionally never touch snow, tile,
  `(none)` or `other`; `DatePalm_RT_02`, `CoconutPalm_RT_01/02` never on **rock**
  (`affinity.json.by_crc` `never_on`).
- **No B-family or A-family trees as the main flora.** `tree/b3` has 109 records and
  `tree/b1` 60 across the whole archetype; they are frontier decoration on `wl_01`, not
  desert planting.
- **Desert flora avoids water.** `tree/n2` d(water) p50 = 20,009 cm corpus-wide; here
  the JoshuaTrees sit at 35,000-39,000 cm. Do not ring an oasis with ferns -- decorate it
  with props.
- **No snow, no lava, no `tile` pavement.** The archetype's ground affinity has exactly
  four classes and none of them is `tile`.
- **No DungeonBlock records.**

---

## The oasis, built

**`metin2_map_n_desert_01` ships exactly one `fall_7`. Copy its geometry rather
than deriving one.** Read off that placement and the terrain under it:

| | |
|---|---|
| anchor z | **24,618** — the UPPER basin's bed, at its lip |
| `height_bias` | **+130** |
| top | 24,748 — **42 cm below** the upper water surface |
| upper surface | **24,790** |
| lower surface | **20,122** — a **46.7 m** drop, 24 m away horizontally |
| roll | **270** |
| slope beneath it | **85.4°** |

The thing that is easy to get wrong: **the anchor sits in the upper water, at the
lip** — not at the top of the visible sheet, and not scaled to the drop. The
effect hangs from the lip and the cliff below is as tall as it likes; the sheet
does not have to reach the bottom, and a 46.7 m drop proves it cannot. Chasing a
`height_bias` that makes the sheet span the wall is chasing a relationship the
corpus does not have.

So the parts, in order:

1. **A shelf**, carrying the upper basin. `ScarpSpec` with `crest_cm` raises the
   standing side to the shelf level while `drop_cm` cuts the floor below it; the
   step between them is the cliff.
2. **The upper basin** on the shelf, as a lake with an explicit `surface_z`. The
   shipped basin is **172 cm** deep over its bed, so use that. Its western edge
   is the lip.
3. **The lower pool** at the foot, `surface_z=None` so it levels in its own bowl
   (`taste.md` §1.12).
4. **The fall at the lip**, `ObjectTier.positions`, biased so its origin sits a
   few tens of cm under the upper surface.
5. **Green and palms at the lower waterline only.**

Two traps, both of which cost a rebuild:

- **Anchor where the cliff IS the local slope.** `align_to_slope` reads the
  gradient at the anchor tile. Two tiles back on the shelf that gradient is the
  shelf's own tilt and the roll came out **75**; at the lip it reads **270**,
  matching the shipped fall.
- **Clip the upper plane to the shelf.** A water plane overruns its basin by
  design (§1.12), and a perched basin's overrun runs straight over the lip and
  renders as a slab hanging in the air. `gen/water.py` clips the overrun to
  ground within `PLANE_MAX_DEPTH_CM` of the surface — the overrun is for
  beaches, not for cliffs.

**On a small map, scale the ratios, not the numbers.** The corpus drop is 46.7 m;
a 1×1 map walled by a 40 m ridge has about 30 m between rim and floor, and
`map_skill_test_04` builds the same shape at 18.4 m.

---|---|
| ground class under it | **rock 72.7 %**, field 13.6 %, grass 6.8 %, sand 4.5 % |
| never on | lava, snow, tile, `(none)`, other |
| slope beneath | p50 **71.4°**, p75 86.6°, 26 of 44 above 45° |
| `on_water_share` | **0.841** |
| distance to water | p50 **0 cm**, p75 0 cm |
| distance to map edge | p50 18,700 cm |
| top textures under it | `b/stone/stone01_01` 18 %, `dawnmistwood_rock001` 11 %, `b/stone/stone01` 9 %, `b/stone/stone04` 9 % |

Read together: **`fall_7` stands in the water, on a near-vertical rock face, in
the middle of the map.** All four constraints hold at once, and any one of them
alone lets it be placed somewhere it will look broken — floating off a cliff
with no water under it, or standing in a pond on flat ground.

**The two-level form needs a plateau.** `metin2_map_n_desert_01` is 6x6 and has
room for one. On a 1x1 map walled by a 40 m border ridge there is nowhere to put
the upper basin: measured on a generated 1x1, the rim is a continuous 25-54 deg
ramp with no shelf, and the crest above 18,900 cm is only **6-9 cells (12-18 m)
wide per side**. A lake polygon placed there floods the outer slope instead of
filling a bowl, and the editor shows water running down the hillside in sheets.
On a small map, drop the upper basin and let the fall emerge from the rock face
as a spring -- `fall_7` is on water in 84 % of its placements, which leaves 16 %
that are not.

**Place the waterfall by hand.** "Steep and near water" cannot express *which*
water: constrained placement puts every sheet at the foot of the drop beside the
lower pool, tens of metres below the basin that feeds it. Use
`ObjectTier.positions`, and set `align_to_slope` so each sheet faces the fall
line -- `fall_7`'s roll is zero in only 13.6 % of corpus placements against
90.2 % for Effects as a class, and the 15 deg ladder every other prop uses puts
the visible face into the rock about half the time.

**Raise it.** `height_bias` p25 **+78 cm**, p50 **+288**, p75 **+1,378**,
p95 **+3,692**. A negative bias sinks the sheet into the ground.

Assembly, in order:

1. **Cut the wall.** A `ScarpSpec` along the side of the oasis the fall will come
   down: `drop_cm` 1,800 over `run_m` 3 is **81°**, against the 71.4° median the
   corpus gives this prop. Direction of travel decides which side stands — the
   cut is on the line's right. Blend it back over 40–60 m (`reach_m`) so the
   floor below is a basin and not a trench.
2. **Pool at the foot**, as a `WaterSpec` lake with `surface_z=None`. Auto-level
   puts the plane inside the bowl and the plane is drawn past the shore, so the
   waterline comes out as a curve with a beach — see `taste.md` §1.12. A
   hand-picked absolute surface is the reliable way to get this wrong.
3. **The fall at the FOOT of the wall, lifted to the lip.** Place it with
   `ObjectTier.positions` — "steep and near water" cannot say *which* water, and
   constrained placement puts the sheet at the bottom of the drop instead of on
   it. `align_to_slope` turns it to the fall line + 90°. One sheet: it renders
   ~40 m across, so two or three on the same wall overlap into a slab.

   Anchor it a tile or two **in front** of the face rather than on the crest:
   anchored on the crest the rock clips through the sheet, anchored at the foot
   it stands clear, and `height_bias` then places it vertically.

   **`fall_7` is about 18 m tall and its anchor is its TOP.** Measured on the
   reference map: at bias +1,443 the top sat exactly on the 18,021 cm crest and
   the base hung 12 m clear of the water; at +300 the base met the shoreline;
   +150 puts it 1.5 m under. The wall is 29.6 m lip-to-pool, so one sheet cannot
   span it — and when it cannot, **the base wins**. A fall ending in mid-air
   reads as broken; one emerging from the rock partway up the face reads as a
   spring, which is what 16% of the corpus placements are. Size the scarp drop
   to ~18 m if you want it to span.

   Read that ground value from the **built terrain**, not from a cell profile:
   placement samples the tile grid and tiles map two to a cell, so the number at
   a tile is not the number at `cell[x // 2]`. Deriving it put the sheet 8 m
   above the crest.
4. **Green only at the waterline.** `grass 01/02` as accents, gated to the wet
   band. The archetype is 64% sand and a green surround at any scale stops
   reading as desert.
5. **Palms, not the archetype's flora.** `tree/n2` sits a median 200 m from water
   corpus-wide and the JoshuaTrees 350–390 m. `DatePalm`, `CoconutPalm` and
   `CurlyPalm` are the exception that belongs at the edge.

**The two-level form needs a plateau.** `metin2_map_n_desert_01` is 6×6 and has
one. On a 1×1 map walled by a 40 m ridge there is nowhere for the upper basin:
the rim is a continuous 25–54° ramp and the crest above 18,900 cm is only 6–9
cells (12–18 m) wide per side, so a lake there floods the outer slope instead of
filling a bowl. Cut a scarp and let the fall come off the face as a spring —
`fall_7` is on water in 84% of its placements, which leaves 16% that are not.

---

## Filling the open ground

A desert map is not empty sand with a feature in one corner. Composition per
sector, measured on the three shipped desert maps:

| family | `n_desert_01` | `wl_01` | `nusluck01` |
|---|---|---|---|
| `tree_speedtree` | 31.9 | 28.2 | 35.5 |
| `wall_fence` | **8.1** | 3.9 | — |
| `clutter` | 6.4 | **9.2** | 1.5 |
| `opaque_serial` | 4.0 | **15.1** | 10.2 |
| `vegetation` (cacti) | — | 3.6 | 5.8 |
| `rock` | 0.2 | 3.8 | 3.0 |
| `light_fire` | 0.4 | 1.6 | 1.8 |
| `building` (tents) | 0.8 | 1.6 | 2.2 |
| `bone_debris` | — | — | **16.0** |

Totals are 52, 70 and 80 objects per sector across **101, 173 and 49** distinct
CRCs. A generated map that hits the count with ten CRCs is the right density and
the wrong map: flora is only 60 % of what is out there.

### The caravan camp

Authored, not scattered — scattering the same CRCs at the same densities puts
tents in three corners and a fire on its own. The measured constraints:

| | slope p50 / p95 | d(road) p50 | nn same p50 |
|---|---|---|---|
| `tent01` / `tent02` | 0.0 / **0.1** | **0 cm** | 3,154 cm |
| `general_obj_charcoa` | 0.0 / 7.0 | 283 cm | — |
| `ob-b1-005-woodbarrel` | 0.0 / 9.8 | 400 cm | **135 cm** |
| `ob-b1-001-box02` | 0.0 / 9.9 | 447 cm | — |
| `general_obj_fence03` | 0.0 / 10.1 | 200 cm | **975 cm** |

Two things fall out. **Tents stand on the road**, not near it — a d(road)
median of 0 across 43 placements is not rounding. And they want ground flatter
than a generated desert has anywhere off the corridor: p95 **0.1°** against a
best-case 0.8 mean / 2.9 max at the flattest site. So level a pad first.

> **A `PlazaSpec` with `tile_index=0` and `safezone=False` is a levelling pad.**
> It paints nothing and flags nothing; all it does is cut a flat platform, which
> is exactly what a building group needs. The camp pad measures 0.00°.

Then: a fence ring at the 975 cm pitch with one bearing left open for the way
in, two tents either side of a fire, and the stores heaped — barrels at their
own 135 cm spacing, not spread.

### The warp gate is three objects, and they share one heading

`warpgate02_01` is only the dais. Its companions within 15 m are `warpgate02`
the **Building** at obs 24 / **lift 241.7** and `warpgate02` the **Effect** at
obs 6 / lift 138.8 — the arch and the spiral inside it. Place all three at one
position; measured height biases are −5, 0 and 0.

**The arch always carries its effect.** Pairing rate against any Effect within
6 m, per model:

| model | n | paired | offset p50 |
|---|---|---|---|
| `warpgate02` (arch) | 30 | **93 %** | 35 cm |
| `warpgate03_01` | 50 | 86 % | 13 cm |
| `warpgate02_01` (dais) | 56 | 59 % | 146 cm |
| `warpgate03` | 35 | 37 % | 10 cm |

61 % of all pairs sit within 50 cm — concentric, not merely nearby. The dais is
the one that stands alone, because a landing pad without an arch is still a
warp destination; wherever the **arch** is present the spiral is too.

> **Rule:** never place an arch without its effect at the same coordinates.

**One heading for the whole compound.** Left to the per-family sampler these
three drew **345, 285 and 105** — independent rungs of the 15° ladder for three
pieces of one object. Set `ObjectTier.roll_deg` and give them all the same
value.

**Aim it at the road.** Like the tents it stands *on* the corridor — d(road) p50
**0 cm** over 56 placements, slope p50 0.1 / p95 2.9 — and the arch has to be
turned across the route so the player walks through the opening rather than past
its side. On the reference map the road bears 68° there and the gate is set to
15°.

---

## Attr policy

**Mixed, and the split matters**: `slope_driven` on `metin2_map_n_desert_01`,
`metin2_map_nusluck01`, `metin2_map_wl_01`; `painted_box` on
`golden_land_stage`, `sungzi_desert_01` and the three `sungzi_desert_hill` copies
(`stats-attr.json` `maps.*.attr_style`).

| Setting | Value (for a sculpted desert) |
|---|---|
| `attr_style` | `slope_driven` |
| `block_slope_deg` | **23-27**; `n_desert_01` fitted 27, `wl_01` 23, `nusluck01` 17 |
| `border_band_m` | **332 m** archetype median seal; strict bands 22-213 m per map |
| `safezone_regions` | rare -- 2 of 8 maps, 4 components |

The archetype-level block budget is **misleading if read naively**: slope 34.2 %, water
0.6 %, object halo 0.9 %, **out-of-bounds 62.5 %**, residual 1.8 %. That 62.5 % comes
almost entirely from the five `painted_box` instances (`sungzi_desert_01` is 94.3 %
out-of-bounds; the three hill copies are 84.0 % each). On the sculpted members the
picture is the normal one -- `n_desert_01` is 75.2 % slope, `wl_01` 75.3 %.

Use the `slope_driven` corpus figure (block at slope >= 20 deg, ~73 % of block from slope)
for a real desert map, and the archetype's fitted 27 deg only if you want `n_desert_01`'s
specific permissiveness -- it blocks only **27.0 %** of its cells, the most open map in
this archetype.

- **Almost no water flag.** 3 of 8 maps have any wet cells; 1 paints the flag; Jaccard
  against `water.wtr` 0.129. Do not bother with `ATTRIBUTE_WATER` unless the map has a
  real oasis.
- **No paint bytes above `0x07` anywhere** -- 0 cells, 0 maps. Only 6 distinct attr bytes
  exist across the whole archetype (`0x00 0x01 0x02 0x03 0x04 0x05`). This is the
  cleanest attr data in the corpus; match it.
- **Footprint policy is split** -- `model_only` on 4 maps, `painted` on 2, `mixed` on 1.
  49.9 % of Building centre cells are blocked (versus 85.7 % in `field_empire`) and only
  13.3 % of Tree centre cells. Prefer `model_only`: place the fences and props on cleared
  flat ground and let the `.mdatr` do the collision.
- **Rim slope median 3 deg versus interior 5 deg** (`attributes.md` sec 8) -- the desert border is
  *not* a mountain wall. The seal is paint, and it is deep: 332 m median. A desert map
  ends because the artist painted it blocked, not because there is a cliff.
- Safezone: 4 components in 2 maps, 1 rectangular fill and 3 irregular; median area
  1,090 m^2, median bbox edge 39 m.

---

## Tells

1. **`NearDistance 1` with `FarDistance 50000`.** Haze at the camera, visibility to
   500 m. No other archetype has this pair.
2. **One carpet, two invisible dithers.** `sand01` solid at 31 %; `sand02` and `sand03`
   at 26 % each with ~1 % interior. This ratio *is* the desert.
3. **Sand is 78.5 % of the painted ground and rock is 13.8 %** -- and the rock is one
   texture, `stone03`, which is genuinely solid (94.6 % non-edge) at 46 deg mean slope.
4. **Scrub at 2-8 m, not 10-17 m.** `tree/n2` NN p50 342 cm. Mixed clumps of 3-4 species.
5. **JoshuaTrees on the scarps, sunk 7 m.** The only desert flora that stands on rock,
   and the deepest height bias in the corpus.
6. **Fence runs.** Five distinct `general_obj_fence0*` CRCs from
   `zone/n/obj/map_n_desert_01` at ~4.1/ha combined, laid in 3-5 segment sequences along
   the roads, 90 % on blocked attr.
7. **A flat plateau, not dunes.** Roughness p50 7.5 cm, height p5->p50 spread of 14 m.
   Dune *appearance* comes from the stipple, not the heightmap.
8. **Essentially no water.** 1.98 % of cells. An oasis is a prop arrangement.
9. **Six attr bytes, no paint convention.** Clean `0x00`-`0x05` only.

---

## Road grammar confidence

**1 of 5 road-bearing maps here are confirmed roads (20%.)** The rest are
`terrain_ribbon` or `ambiguous` -- soft-edged regions the corridor detector picks
up as tracks. `roads.json.by_archetype` is now filtered to the confirmed set, but
with n=1 the width, curvature and junction figures are **indicative, not
measured**. Treat them as a starting point and check the result by eye.

The path-texture identification and the `d(road)` setbacks are unaffected: both
come from per-slot and per-CRC statistics, not from corridor detection.

## Border occlusion

**Mixed.** Median ring lift is only **+350 cm**, but that median hides a split: the flagship maps wall themselves properly while the small instanced siblings do not. Follow the reference map, not the median.

Measured over the outer 64 m against the interior; see `../taste.md` for the corpus-wide table and the two traps when building a rim.

## Sources

`corpus-overview.md` sec 4 ; `catalog/map-taxonomy.json` `archetypes.desert` ;
`catalog/stats-terrain.json` `by_archetype.desert` ;
`catalog/stats-tiles.json` `by_archetype.desert` ;
`textures.md` sec 3, sec 6 `desert` ; `catalog/textures.json`
`texturesets["metin2_n_desert1.txt"]`, `["metin2_wl_01.txt"]`,
`["metin2_map_golden_land.txt"]` ; `environments.md` sec 5, sec 6 `desert` ;
`catalog/environments.json` `archetype_presets.desert` ; `placement.md` sec 1.3, sec 3.1,
sec 4.1, sec 5, sec 6, sec 8 ; `catalog/stats-objects.json` `by_archetype.desert`, `by_crc` ;
`catalog/affinity.json` `by_archetype.desert`, `by_crc`, `by_family` ;
`catalog/cooccurrence.json` ; `attributes.md` sec 4, sec 8, sec 10 ;
`catalog/stats-attr.json` `archetypes.desert`, `maps.*` ; `catalog/roads.json`
`by_archetype.desert` -- pooled and unfiltered, see `roads.json.by_archetype_caveat`.

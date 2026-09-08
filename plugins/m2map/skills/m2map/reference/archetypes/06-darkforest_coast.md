# 06 -- `darkforest_coast`

**Dark-forest coast and the Devils Dragon Island continent.** 8 maps (5 with own
terrain), 110 sectors, 5,875 object placements. Reference map
`metin2_map_capedragonhead`.

---

## Identity

A steep, wet, hand-furnished coast: black-sand bays, 30-40 deg cliff faces carrying the
ground itself, a mixed temperate/arid forest, and an orc camp with whale bones on the
beach. This is the corpus's **most authored** outdoor archetype -- 491 distinct CRCs
across five maps and the highest object-slope median anywhere (15.3 deg, p95 50.3 deg) -- and
its most steeply built one.

The evidence that binds it is object-side, not terrain-side: `zone/devils_dragon_island`
and its two sub-folders (`camp`, `bone`) appear at 51-531 records per map here and at
**<=36 records anywhere else in the corpus** (`map-taxonomy.json`
`archetypes.darkforest_coast.evidence`). The terrain palettes are four bespoke coastal
art packs -- `capedragonhead`, `bayblacksand`, `dawnmistwood`, `mtthunder` -- that
cross-borrow freely from one another.

It is also the one archetype where the **skybox cube actually renders**: four of its five
environments set `bTextureRenderMode 1` and name real face sets.

---

## Reference maps

| Map | Size | Sectors | Textureset | Environment | Objects | CRCs | Terrain |
|---|---|---|---|---|---|---|---|
| **`metin2_map_capedragonhead`** (reference) | 6x6 | 36 | `metin2_CapeDragonHead.txt` | `CapeDragonHead.msenv` | 1,965 | 219 | own |
| `metin2_map_mt_thunder` | 4x6 | 24 | `metin2_mtthunder.txt` | `mtthunder.msenv` | 1,481 | **255** | own |
| `metin2_map_dawnmistwood` | 7x4 | 28 | `metin2_DawnMistWood.txt` | `DawnMistWood.msenv` | 1,162 | 158 | own (`ViewRadius 512`) |
| `metin2_map_bayblacksand` | 3x6 | 18 | `metin2_BayBlackSand.txt` | `bayblacksand.msenv` | 881 | 122 | own |
| `metin2_map_e1` | 2x2 | 4 | `metin2_map_e1.txt` | `e1.msenv` | 386 | 165 | own (**`ViewRadius 4096`**) |
| `metin2_map_e1_01/_02/_03` | 2x2 | 0 | `metin2_map_e1.txt` | `e1.msenv` | 0 | 0 | `proxy:metin2_map_e1` |

- **Typical and flagship size 6x6.**
- `metin2_map_e1` and its three proxies are the four maps in the entire corpus with
  `ViewRadius 4096` (`corpus-overview.md` sec 1); `dawnmistwood` is one of two with 512.
  If you are cloning e1, carry the `ViewRadius` -- the whole point of that map is the
  long view.
- `mt_thunder` at 255 distinct CRCs is the most varied object palette of any shipped map.

---

## Terrain

`style: sculpted`, all five. `stats-terrain.json` `by_archetype.darkforest_coast`,
5 maps, 110 sectors.

| Quantity | Value |
|---|---|
| `height_range_cm` | 12,023.5 - **32,767.5** (the uint16 ceiling); p5 15,255, **p50 17,827**, p95 24,561 |
| Relief per sector | p25 5,513 cm, **p50 6,871 cm**, p75 9,315 cm, p90 11,028 cm |
| `slope_p50` | **16.6 deg** |
| `slope_p95` | **59.6 deg** (p75 36.2 deg, p90 52.1 deg, mean 22.5 deg) |
| `flat_fraction` (< 5 deg) | **0.209** (< 2 deg **0.092**, < 10 deg 0.369, < 20 deg 0.551) |
| `roughness` (abs Laplacian r=1) | p50 25.5 cm, p90 152.5, p99 492.5 |
| Local std 3x3 | p50 52.5 cm, p90 206.5 cm |
| Water cells | **21.6 %** |
| Blocked cells | 69.6 % |

`frac_lt_2deg` of **0.092** is the lowest of any outdoor archetype -- under a tenth of
this land is genuinely level. Yet the slope distribution has a much shorter upper tail
than `field_empire` (p95 59.6 deg vs 70.7 deg). This is not a plain fenced by cliffs; it is
**continuously sloped ground everywhere**, which is why objects here sit at a median
slope of 15.3 deg rather than 1-3 deg.

Height reaches the uint16 ceiling (32,767.5 cm = 65535 x 0.5). Anything you generate at
this scale must clamp there or `height.raw` wraps.

---

## Textureset recipe

Five palettes, all bespoke, all cross-borrowing. Reference for the archetype's *look* is
**`metin2_CapeDragonHead.txt`** (12 slots, `metin2_map_capedragonhead`); `textures.json`
nominates `metin2_map_e1.txt` (7 slots) as the archetype reference because it serves four
map indices. Both are given.

**`metin2_CapeDragonHead.txt`** -- `weight` = measured `ground_share`, sums to 1.000:

| slot | role | path | U/V | repeat | weight |
|---|---|---|---|---|---|
| 1 | `mid` | `d:/ymir work/terrainmaps/capedragonhead/capedragon_grass001.dds` | 2/2 | 16.0 m | 0.019 |
| 2 | `base` | `d:/ymir work/terrainmaps/capedragonhead/capedragon_grass002.dds` | 2/2 | 16.0 m | 0.143 |
| 3 | `mid` | `d:/ymir work/terrainmaps/capedragonhead/capedragon_field001.dds` | 2/2 | 16.0 m | 0.084 |
| 4 | `base` | `d:/ymir work/terrainmaps/capedragonhead/capedragon_cliff002.dds` | 1/1 | 32.0 m | 0.406 |
| 5 | `accent` | `d:/ymir work/terrainmaps/capedragonhead/capedragon_field003.dds` | 2/2 | 16.0 m | 0.003 |
| 6 | `shore` | `d:/ymir work/terrainmaps/capedragonhead/capedragon_sand002.dds` | 2/2 | 16.0 m | 0.193 |
| 7 | `path` / road | `d:/ymir work/terrainmaps/capedragonhead/stone_tile_002.dds` | 2/2 | 16.0 m | 0.009 |
| 8 | `cliff` | `d:/ymir work/terrainmaps/capedragonhead/capedragon_cliff003.dds` | 1/1 | 32.0 m | 0.035 |
| 9 | `accent` | `d:/ymir work/terrainmaps/mtthunder/mtthunder_field01.dds` | 2/2 | 16.0 m | 0.003 |
| 10 | `mid` | `d:/ymir work/terrainmaps/capedragonhead/capedragon_stone001.dds` | 2/2 | 16.0 m | 0.034 |
| 11 | `mid` | `d:/ymir work/terrainmaps/capedragonhead/capedragon_grass003.dds` | 2/2 | 16.0 m | 0.070 |
| 12 | `path` | `d:/ymir work/terrainmaps/capedragonhead/stone_tile_001.dds` | 2/2 | 16.0 m | 0.001 |

**The cliff texture is the base.** `capedragon_cliff002.dds` at `UScale 1` -- a 32 m
repeat -- covers 40.6 % of the map at clump 7.22 and 73 % non-edge, on 32 deg mean ground.
Because the whole map is sloped, the "cliff skin" *is* the ground carpet. This inversion
is the archetype's defining palette decision and it does not occur anywhere else.

`capedragon_sand002.dds` (slot 6) is the shore at 19.3 %, with **100 % of its tiles
within 4 m of water** and clump 7.87 -- a genuinely solid beach, not a dither.

`stone_tile_002.dds` (slot 7) is the road: 0.88 % cover, clump 6.74, 56 % non-edge,
3.63 deg mean slope, and it is the index the geometric road detector selects on
`metin2_map_capedragonhead` (`placement.md` sec 5). Set `RoadSpec.tile_index = 7`.

`metin2_CapeDragonHead.txt` is also the cleanest proof of the texel-density rule
(`textures.md` sec 4b): ten of its twelve slots land on **exactly 32 px/m**, pairing 512 px
art with `UScale 2` and 1024 px art with `UScale 1`.

**`metin2_bayblacksand.txt`** (11 slots, `metin2_map_bayblacksand`) is the black-sand
variant -- `bayblacksand_blacksand.dds` base at 34.1 %, `bayblacksand_rock001.dds` second
base at 27.4 % (`UScale 1`), `bayblacksand_grass.dds` 17.5 %, with three
`capedragonhead/` textures imported. **It is missing its `Texture003` block entirely**
and the map paints 33 tiles there anyway -- those render the error texture
(`textures.json` `texturesets["metin2_bayblacksand.txt"].problems`). Do not reproduce
that hole.

**How the archetype paints** (`stats-tiles.json` `by_archetype.darkforest_coast`):
role share rock 43.1 %, sand 25.3 %, grass 19.1 %, dirt 12.0 %, paved 0.5 %; base role
`rock` in 4 maps and `sand` in 1; median 12 slots used of 11 declared (some maps paint
past `TextureCount`); **unused fraction 0.000** -- these palettes are fully exercised,
unlike every other archetype; `dither_only_tile_share` median **0.00003**;
`stipple_pairs_per_map` median **0**; `mean_run_h_of_base` median 10.8 tiles;
`coverage_entropy_bits` median 2.52 -- the highest in the corpus.

That last cluster of numbers matters: **`darkforest_coast` barely stipples.** Like
`flame_field` it paints in regions, but unlike `flame_field` it paints *many* of them --
twelve live slots at high entropy with 10-tile runs. The texture variety comes from
region mosaic, not from dither.

---

## Environment

**Canonical `e1.msenv`** -- cluster C03 `warm_dusk`, on the four e1 map indices. But this
is the **widest environment spread of any outdoor archetype**: 5 envs across 4 clusters,
and every one of the four non-e1 members is off-cluster
(`environments.json` `archetype_presets.darkforest_coast`).

| Env | Maps | Cluster |
|---|---|---|
| `e1.msenv` | 4 | C03 `warm_dusk` |
| `bayblacksand.msenv` | 1 | C01 `murky_lowlight` |
| `capedragonhead.msenv` | 1 | C00 `clear_blue_noon` |
| `dawnmistwood.msenv` | 1 | C01 `murky_lowlight` |
| `mtthunder.msenv` | 1 | C19 `singleton_mtthunder` |

| Parameter | Observed over all 8 maps |
|---|---|
| `Fog.Enable` | 1 x8 |
| `Fog.NearDistance` | 1,000 - 20,000 cm (median 5,000) |
| `Fog.FarDistance` | 20,000 - **80,000 cm** (median 25,000) |
| `Fog.Color` | `#2A2A3B`, `#423D62`, `#8B4F1B`, `#975A2A`, `#AFBCD6` |
| `Background.Ambient` | level 0.242 - 0.311 (median 0.243) |
| `Character.Ambient` | Background + 0.15 |
| `Background.Diffuse` | `#9C799E`, **`#F3FD00`**, `#F6D1D1`, `#FFF8F8` |
| light warmth | -0.008 - **0.953** (median 0.028) |
| sun elevation / azimuth | 16.5 - 47.8 deg / 97.2, 99.1, 143.0, 153.4, 193.4 deg |
| Gradient | Upper 4 x6, 1 x1, 2 x1 / Lower 1 x8 |
| Sky zenith | `#000000`, `#1849A8`, `#4B5049`, `#918260`, `#B1751F` |
| Cloud | `clouds_zone05.tga` / `clouds_zone06.tga`, scale 200000, texture scale 4, speed 0.001-0.004 |
| **Skybox faces** | **`bayblacksand`, `capedragonhead`, `dawnmistwood`, `thunder` -- 4 of 8 at `bTextureRenderMode 1`** |
| `Filter.Enable` | 1 x5 (`bayblacksand.msenv` carries the real additive `#4B1818` tint) |

Three things are unique to this archetype:

1. **The skybox cube is live.** Only 15 of 104 corpus files set `bTextureRenderMode 1`,
   and four of them are here. Writing face textures without the flag does nothing
   (`environments.md` sec 4.2); here you must set it.
2. **The sun comes from the east.** Azimuths 97-153 deg against 211-245 deg everywhere else,
   and `Direction` vectors with a negative X. Every other archetype's sun sits in the
   south-west.
3. **`FarDistance 80,000 cm`** on one member -- 800 m of textured terrain, which is what
   `ViewRadius 4096` on e1 exists to serve.

Pick by map, not by archetype: `capedragonhead.msenv` for a bright coast,
`bayblacksand.msenv`/`dawnmistwood.msenv` for a murky one, `e1.msenv` for warm dusk.

---

## Object palette

**Density 8.15 obj/ha = 0.0815 per 100 m^2 = 53.4 per sector**, **491 distinct CRCs**
across 720.9 ha. Mix: **Building 64.8 %**, Tree 34.2 %, Effect 1.0 %.

Family budget:

| Family | n | per ha | NN same-family p25/p50/p75 (cm) | Clark-Evans R |
|---|---|---|---|---|
| `zone/b/obj` | 1,765 | 2.45 | 161 / **319** / 607 | 0.247 |
| `tree/b1` | 1,311 | 1.82 | 648 / **1,680** / 3,017 | 0.555 |
| `zone/devils_dragon_island` | 861 | 1.19 | 243 / **642** / 1,211 | 0.273 |
| `zone/devils_dragon_island/camp` | 684 | 0.95 | 513 / **809** / 1,395 | 0.259 |
| `tree/n2` | 464 | 0.64 | 325 / **593** / 1,224 | 0.196 |
| `zone/devils_dragon_island/bone` | 242 | 0.34 | 413 / **699** / 1,107 | 0.145 |
| `zone/n/obj/map_n_desert_01` | 140 | 0.19 | 287 / 530 / 1,071 | 0.129 |
| `tree/b3` | 129 | 0.18 | 2,836 / 5,793 / 9,157 | 0.599 |
| `tree/b2` | 105 | 0.15 | 2,848 / 4,600 / 6,504 | 0.361 |
| `zone/n/desert` | 61 | 0.08 | 285 / 339 / 489 | 0.043 |
| `effect/background` | 46 | 0.06 | 108 / 2,707 / 8,823 | 0.710 |
| `zone/b/building` | 22 | 0.03 | 3,398 / 5,185 / 6,514 | 0.188 |
| `zone/e1` | 12 | 0.02 | 1,884 / 3,175 / 7,480 | 0.121 |

**Mixing arid flora into a temperate coast is the visual signature.** 464 `tree/n2`
records -- JoshuaTrees on the black sand and the mtthunder scarps -- alongside 1,311
`tree/b1`. No other temperate archetype does this.

### Tier table (directly usable as `MapSpec.objects`)

`density` per 100 m^2; `spacing_cm` = NN(same CRC) p5; `max_slope` = per-CRC slope p95;
`road_clearance_cm` = per-CRC d(road) p25; `height_bias` = (bias p25, bias p75).
`on_tiles` indexes the 12-slot `metin2_CapeDragonHead.txt` palette above.

| tier | crc | name | density | spacing_cm | on_tiles | max_slope | road_clear_cm | height_bias | water_m |
|---|---|---|---|---|---|---|---|---|---|
| signature | 1214881363 | `gaint_fence04` (Building, `.../camp`) | 0.00128 | 515 | 2,3,4,11 | 41 | 0 | (-212, -30) | 180/282/353 **(180, inf)** |
| signature | 308757728 | `thing_fire_stand_bowl_00` (Building, `zone/devils_dragon_island`) | 0.00080 | 884 | 2,3,4,11 | 21 | 0 | (-28, -1) | 144/256/314 **(144, inf)** |
| signature | 1609982784 | `JoshuaTree_RT_03` (Tree, `tree/n2`) | 0.00209 | 636 | 4,6 | 55 | 50 | (-879, -60) | 180/350/592 **(180, inf)** |
| signature | 3498019135 | `JoshuaTree_RT_02` (Tree, `tree/n2`) | 0.00129 | 1249 | 4,6 | 59 | 200 | (-827, -60) | 183/304/452 **(183, inf)** |
| signature | 1105271114 | `JoshuaTree_RT_01` (Tree, `tree/n2`) | 0.00112 | 1233 | 4,6 | 49 | 200 | (-827, -35) | 200/389/589 **(200, inf)** |
| signature | 4014868700 | `ob-bigstone03` (Building, `zone/b/obj`) | 0.00166 | 455 | 2,4,11 | 44 | 1295 | (-152, -61) | 86/174/287 **(86, inf)** |
| signature | 1211097993 | `ob-bigstone02` (Building, `zone/b/obj`) | 0.00119 | 353 | 2,4,11 | 46 | 647 | (-152, -31) | 59/206/281 **(59, inf)** |
| signature | 673027490 | `ob-bigstone04` (Building, `zone/b/obj`) | 0.00104 | 507 | 2,4,11 | 45 | 812 | (-152, -65) | 58/164/274 **(58, inf)** |
| signature | 2653701801 | `ob-bigstone01` (Building, `zone/b/obj`) | 0.00103 | 471 | 2,4,11 | 48 | 1000 | (-160, -91) | 94/178/273 **(94, inf)** |
| filler | 569394331 | `Pagoda1` (Tree, `tree/b1`) | 0.00336 | 1709 | 1,2,3,11 | 47 | 565 | (-358, -25) | 14/75/187 (0, inf) |
| filler | 2376089798 | `Pagoda2` (Tree, `tree/b1`) | 0.00319 | 2397 | 1,2,3,11 | 46 | 600 | (-273, -20) | 18/61/181 (0, inf) |
| filler | 1107711305 | `Pagoda3` (Tree, `tree/b1`) | 0.00313 | 1503 | 1,2,3,11 | 46 | 565 | (-152, -20) | 17/68/178 (0, inf) |
| filler | 2399205967 | `Beech2` (Tree, `tree/b1`) | 0.00209 | 2934 | 1,2,3,11 | 44 | 600 | (-91, -13) | 21/61/149 (0, inf) |
| filler | 3689520799 | `Beech4` (Tree, `tree/b1`) | 0.00144 | 2025 | 1,2,3,11 | 45 | 282 | (-91, -9) | 27/64/143 (0, inf) |
| filler | 1353164984 | `Beech1` (Tree, `tree/b1`) | 0.00128 | 2765 | 1,2,3,11 | 46 | 262 | (-76, -16) | 19/68/167 (0, inf) |
| filler | 3748653682 | `MontereyCypress3` (Tree, `tree/b1`) | 0.00119 | 2794 | 1,2,3,11 | 46 | 200 | (-152, -5) | 4/43/105 (0, inf) |
| filler | 3455398876 | `Beech3` (Tree, `tree/b3`) | 0.00118 | 2662 | 1,2,3,11 | 41 | 400 | (-60, -5) | 22/71/168 (0, inf) |
| filler | 1289994135 | `MontereyCypress4` (Tree, `tree/b1`) | 0.00082 | 3095 | 1,2,3,11 | 45 | 0 | (-92, -17) | 12/43/117 (0, inf) |
| filler | 358206493 | `ob-b1-005-woodbarrel` (Building, `zone/b/obj`) | 0.00110 | 73 | 3,6 | 10 | 0 | (-5, 0) | 20/85/261 (0, inf) |
| accent | 1471924893 | `ob-7-02-01` (Building, `zone/b/obj`) | 0.00085 | 213 | 3,7 | 22 | 0 | (-20, 108) | 51/119/230 **(51, inf)** |

`water_m` = observed distance to the nearest water, p25/p50/p75 in metres (`affinity.json` `by_crc[crc].d_water_cm`; `~` = the family's figure where the CRC has none). The bold `(min, inf)` is the suggested `MapSpec.water_distance_m` for species that measurably avoid water. A species that tolerates it gets no constraint; give oasis or shore decoration a `(0, max)` band instead -- do NOT try to pin it to the shore texture, which is a stipple and covers only a handful of tiles.


The **bone set** deserves its own note even though its individual CRCs fall below the
420-row per-CRC cutoff. `zone/devils_dragon_island/bone` is 242 records here (234 of them
in `bayblacksand`), **86.9 % of them on sand**, median distance to water 4,160 cm, and
**35.6 % standing in water** (`placement.md` sec 8). They are whale and turtle skeletons on
the black beach, and they are the archetype's most distinctive silhouette.

Bones and boulders are also the corpus's tilt families: `.../bone` has **yaw != 0 in
26.2 % and pitch != 0 in 33.0 %** of records, and `ob-bigstone01` here is 38.2 % yaw and
37.4 % pitch. Everywhere else in the corpus, yaw and pitch are near zero
(`placement.md` sec 1.1).

---

## Placement rules

**Ground affinity** (`affinity.json` `by_archetype.darkforest_coast`, n = 5,875):
grass 33.5 %, rock 31.9 %, sand 19.7 %, field 12.6 %, tile 2.1 %. Object slope
p50 **15.32 deg**, p75 29.22 deg, p95 50.27 deg -- the steepest object placement in the corpus.
Only 605 of 5,864 placements sit below 2 deg.

**Positive rules**

1. **Place on slopes.** This is the inversion of the usual rule. Boulders sit at 18-20 deg
   median and 44-48 deg at p95; camp fences at 19 deg; only the crates and warpgates want flat
   ground.
2. **Sink hard.** `ob-bigstone01` bias p50 -152 cm, `ob-bigstone03` -110, `ob-bigstone04`
   -104 (`placement.md` sec 1.3). `gaint_fence04` -152. The JoshuaTrees -697.
3. **Tilt the debris.** Yaw and pitch at +/-15 deg or +/-30 deg on bones, big stones and thorns --
   and *only* on those. Buildings never tilt (`zone/b/building` yaw != 0 in 0.1 %).
4. **The camp is a set.** `gaint_fence04` (92 records, NN p50 815 cm, d(road) p25 = 0),
   `camp_woodhut_fence00/01`, `fortMS_fence_body02` + `fortMS_fence_pillar` in a
   body/pillar alternation (obs 42 at 5 m, x1,215). `thing_fire_stand_bowl_00` marks the
   fire.
5. **Roads are wide, looped and heavily blended.** Width median 9.0 m (distance-transform
   7.0 m) -- the widest of any archetype -- road core fraction 0.099, density
   12,470 m/km^2, 9.33 junctions/km, 3.76 loops/km, and **blend band 7.0 m**, more than
   double any other archetype. The track feathers broadly into the ground.
6. **Buildings 1,131 cm from a road, trees 1,542 cm** (`placement.md` sec 5) -- the two are
   nearly equal here, unlike the 600/2,200 split of `field_empire`. The forest comes
   right up to the track.
7. **Bones on the beach, in the water.** 86.9 % on sand, 35.6 % wet.

**Negative rules**

- **`gaint_fence04` is never on `(none)`, lava, other, sand, snow or tile** -- it is a
  rock/grass/field prop, so it does not go on the beach.
- **`ob-bigstone01` never on lava, other, sand or snow**; `ob-bigstone02/03/04` never on
  lava, other, snow (and `02` not on tile).
- **`tree/b1` never on lava or snow**; `tree/n2` never on lava; `JoshuaTree_RT_01/02/03`
  additionally never on snow or tile.
- **No `tree/n1`.** Zero winter conifers despite the murky environments.
- **No DungeonBlock records.**
- Do not paint a large plaza: `paved` is 0.5 % of the ground and `stone_tile_001` covers
  0.05 %.

---

## Attr policy

`attr_style: slope_driven` on **all five** maps with terrain. Footprint policy
`painted` on all five -- the only archetype with unanimous agreement on both.

| Setting | Value |
|---|---|
| `attr_style` | `slope_driven` |
| `block_slope_deg` | **15** (fitted thresholds 13, 15, 16, 16, 17; median 16) |
| `border_band_m` | **119 m** median seal; strict bands 34-111 m |
| `safezone_regions` | 2 irregular components, median **42,090 m^2**, bbox edge 248 m |

Block budget over 4,962,737 cells: **slope 69.8 %**, water 14.4 %, object halo 4.8 %,
out-of-bounds 8.0 %, residual 3.0 %. 68.8 % of cells blocked.

- **The fitted threshold is low -- 15 deg, against the corpus `slope_driven` optimum of
  20 deg.** That is a direct consequence of the terrain: with slope p50 at 16.6 deg, a 20 deg
  rule would leave far too much of the map walkable. Use 15 here.
- **Object halo is the highest of any archetype at 4.8 %**, and **21.2 % of all block
  cells are within 12 m of a placement** (against a `slope_driven` corpus figure of
  11.4 %). This is a hand-furnished map: the props themselves carve the collision.
- **98.7 % of Building centre cells and 96.8 % of Tree centre cells are blocked.** Stamp
  everything -- including trees, which is unusual (`field_empire` blocks only 8 % of tree
  centres). On this archetype the artist painted around the forest.
- **`ATTRIBUTE_WATER` is essentially unused.** 5 of 5 maps have wet cells (1,556,320 of
  them) and **0 maps paint the flag**; Jaccard 0.027. Water is blocked by slope and by
  the submerged predicate, not by the flag. Reproduce that: paint `BLOCK` on submerged
  cells and leave `WATER` clear.
- **No paint bytes above `0x07`**; only 7 distinct attr bytes.
- Safezone: 2 huge irregular components (median 42,090 m^2, 248 m bbox) -- these are
  whole-region peace zones, not town discs. Fill ratio 0.681.
- Rim slope median 20 deg versus interior 14 deg -- a shallow ridge. All five maps sealed
  strict.

---

## Tells

1. **The cliff texture is the ground.** `capedragon_cliff002.dds` at `UScale 1` covers
   40.6 % of the reference map. A coast where the rock skin is the carpet.
2. **`UScale` 1 and 2 only** -- 16 m and 32 m repeats, at exactly 32 px/m.
3. **A real skybox cube.** Four of five environments set `bTextureRenderMode 1` and name
   `bayblacksand` / `capedragonhead` / `dawnmistwood` / `thunder` face sets.
4. **The sun is in the east.** Azimuth 97-153 deg, `Direction.x` negative -- inverted against
   every other archetype.
5. **Bones on black sand, half of them in the water**, tilted with real yaw and pitch.
6. **Arid flora in a temperate forest.** 464 `tree/n2` JoshuaTree records among 1,311
   `tree/b1`.
7. **Big stones everywhere, sunk a metre and a half.** Four `ob-bigstone0*` CRCs at
   ~0.5/ha combined, bias -103 to -152 cm, on 18-20 deg ground, 20 m from the nearest road.
8. **7 m road blend band.** Twice any other archetype.
9. **Objects sit at 15 deg median.** Nothing else in the corpus places on ground this steep.
10. **Palettes with zero unused slots and entropy 2.52.** Twelve live textures in a
    region mosaic, essentially no stipple.

---

## Road grammar confidence

**4 of 5 road-bearing maps here are confirmed roads (80%.)** The rest are
`terrain_ribbon` or `ambiguous` -- soft-edged regions the corridor detector picks
up as tracks. `roads.json.by_archetype` is now filtered to the confirmed set, but
with n=4 the width, curvature and junction figures are **indicative, not
measured**. Treat them as a starting point and check the result by eye.

The path-texture identification and the `d(road)` setbacks are unaffected: both
come from per-slot and per-CRC statistics, not from corridor detection.

## Border occlusion

**Terrain ridge.** The outer 64 m sits **+1260 cm** above the interior (corner ring +880 cm). Set `border_ridge_cm` near that and let the fog keep a clear foreground.

Scale the *width* to the map: the measurement ring is 64 m, which on a 1x1 map (256 m) would consume half the playable surface. Keep the lift, narrow the rise.

Measured over the outer 64 m against the interior; see `../taste.md` for the corpus-wide table and the two traps when building a rim.

## Sources

`corpus-overview.md` sec 1, sec 4 ; `catalog/map-taxonomy.json`
`archetypes.darkforest_coast`, `maps.*` ; `catalog/stats-terrain.json`
`by_archetype.darkforest_coast` ; `catalog/stats-tiles.json`
`by_archetype.darkforest_coast` ; `textures.md` sec 4b, sec 6 `darkforest_coast` ;
`catalog/textures.json` `texturesets["metin2_capedragonhead.txt"]`,
`["metin2_bayblacksand.txt"]` ; `environments.md` sec 4.2, sec 5, sec 6 `darkforest_coast` ;
`catalog/environments.json` `archetype_presets.darkforest_coast` ;
`placement.md` sec 1.1, sec 1.3, sec 5, sec 6, sec 8 ; `catalog/stats-objects.json`
`by_archetype.darkforest_coast`, `by_crc` ; `catalog/affinity.json`
`by_archetype.darkforest_coast`, `by_crc` ; `attributes.md` sec 4, sec 5, sec 8, sec 10 ;
`catalog/stats-attr.json` `archetypes.darkforest_coast`, `maps.*` ;
`catalog/roads.json` `by_archetype.darkforest_coast` -- pooled and unfiltered, see
`roads.json.by_archetype_caveat`.

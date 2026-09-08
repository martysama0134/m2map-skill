# 05 -- `flame_field`

**Flame land / volcanic field.** 6 maps (5 with own terrain), 61 sectors,
496 object placements. Reference map `metin2_map_n_flame_01`.

---

## Identity

Black basalt and magma under a burning orange sky, lit by a **cool teal key light**, and
almost completely empty. At **1.24 obj/ha** this is the sparsest archetype in the corpus
-- a tenth of the density of `arena_pvp` -- and that emptiness is the art direction, not
an omission.

The whole visual identity is carried by seven textures from one folder
(`terrainmaps/n/flame area/`) and one environment (`map_n_flame_01.msenv`,
cluster C06 `ember_orange`). The environment is the strongest tell: `GradientLevelUpper 7`
-- the highest band count in the corpus -- a near-black `#1F0000` zenith over a
`#87381F` horizon with a **`#FF8700` nadir**, the strongest below-horizon colour in the
game, and a directional diffuse of `#5DAA9A` giving `light_warmth -0.2431`. The artist
lit a lava field with a teal key against a hot sky, and that contrast is what makes it
read as volcanic rather than merely brown.

Vegetation is two CRCs. All of it. `IvySpy_Winter2` (178) and `IvySpy_Winter1` (116),
family `tree/b2` -- dead vines on rock.

---

## Reference maps

| Map | Size | Sectors | Textureset | Environment | Objects | Terrain |
|---|---|---|---|---|---|---|
| **`metin2_map_n_flame_01`** (reference) | 6x6 | 36 | `metin2_n_flame_01.txt` | `map_n_flame_01.msenv` | 404 | own |
| `metin2_map_sungzi_flame_hill_01/02/03` | 2x4 | 8 each | `metin2_n_flame_01.txt` | `map_n_flame_01.msenv` | 14 each | own (byte-identical triplet) |
| `metin2_map_labyrinth` | 1x1 | 1 | `metin2_boss_entrance.txt` | `map_boss_entrance.msenv` | 50 | own |
| `metin2_map_smhgate_flame` | 6x6 declared | 0 | `metin2_n_flame_01.txt` | `map_n_flame_01.msenv` | 0 | `proxy:n_flame_01` |

- **Typical size 2x4**, **flagship 6x6**.
- The `sungzi_flame_hill` triplet carries **14 objects each** -- ten `effect/background`
  and four `zone/b/obj`. There is no vegetation and no architecture. That is a real,
  shipped, deliberately empty map.
- `metin2_map_labyrinth` is the boss-entrance variant: same seven textures in the same
  order via `metin2_boss_entrance.txt` (plus one `dawnmistwood` accent), and its own
  near-clone environment `map_boss_entrance.msenv` (differs from `map_n_flame_01.msenv`
  by ~0.001 per channel).

---

## Terrain

`style: sculpted` for `n_flame_01` and `labyrinth`; the three sungzi hills are
`box`-flat. `stats-terrain.json` `by_archetype.flame_field`, 5 maps, 61 sectors.

| Quantity | Value |
|---|---|
| `height_range_cm` | 11,385.5 - 27,266.0; p5 14,363.5, **p50 16,383.5**, p95 20,015.0 |
| Relief per sector | p25 6,386 cm, **p50 6,934 cm**, p75 8,191 cm, p90 10,314 cm |
| `slope_p50` | **11.3 deg** |
| `slope_p95` | **63.7 deg** (p75 35.6 deg, p90 55.8 deg, mean 20.5 deg) |
| `flat_fraction` (< 5 deg) | **0.345** (< 2 deg 0.236, < 10 deg 0.474, < 20 deg 0.619) |
| `roughness` (abs Laplacian r=1) | p50 16.5 cm, p90 160.5, p99 845.5 |
| Local std 3x3 | p50 35.5 cm, p90 239.5 cm |
| Water cells | **0.000** |
| Blocked cells | 65.6 % |

Like `snow_field`, the floor is high (min 11,385 cm) and the relief per sector is modest
(6.9 m median). This is a plateau of hardened flows with ridges, not a mountain range.
No water -- but see the `lava` texture role below: molten ground here is *paint*, not a
`water.wtr` surface.

---

## Textureset recipe

**`metin2_n_flame_01.txt`**, 7 slots, the whole `terrainmaps/n/flame area/` folder,
measured across five maps (`textures.json`
`texturesets["metin2_n_flame_01.txt"]`). `weight` = measured `ground_share`; sums to
1.000.

| slot | role | path | U/V | repeat | weight |
|---|---|---|---|---|---|
| 1 | `base` | `d:/ymir work/terrainmaps/n/flame area/valcano_01.dds` | 2/2 | 16.0 m | 0.291 |
| 2 | `path` | `d:/ymir work/terrainmaps/n/flame area/valcano_02.dds` | 3/3 | 10.7 m | 0.019 |
| 3 | `base` | `d:/ymir work/terrainmaps/n/flame area/valcano_03.dds` | 3/3 | 10.7 m | 0.233 |
| 4 | `cliff` | `d:/ymir work/terrainmaps/n/flame area/valcano_04.dds` | 2/2 | 16.0 m | 0.147 |
| 5 | `mid` (magma) | `d:/ymir work/terrainmaps/n/flame area/valcano_magma_01.dds` | 3/3 | 10.7 m | 0.068 |
| 6 | `path` / road | `d:/ymir work/terrainmaps/n/flame area/tile01.dds` | 3/3 | 10.7 m | 0.039 |
| 7 | `base` | `d:/ymir work/terrainmaps/n/flame area/valcano_rock.dds` | 2/2 | 16.0 m | 0.202 |

**This is the one archetype where the base is a *set*, not a single texture.**
`valcano_01` (29.1 %, clump 7.50, 85 % non-edge), `valcano_03` (23.3 %, clump 6.75, 63 %
non-edge) and `valcano_rock` (20.2 %, clump 6.61, 52 % non-edge) all score `base`. Three
solid carpets side by side.

The consequence shows up in the tile statistics: `stipple_pairs_per_map` median **0**,
`dither_only_tile_share` median **0.000**, `mean_run_h_of_base` median **111.6 tiles**,
`interior_fraction` median **0.928** and `edge_density` median **0.028**. Against a
corpus median run length of 2 tiles, this archetype's base runs for over a hundred.
**`flame_field` is the corpus's one exception to the "ground is a stipple" rule** -- and
`metin2_map_n_flame_01` is on the `maps_with_no_stipple` list in
`stats-tiles.json`. Paint it in large regions, not as dither.

`valcano_magma_01` (slot 5) is the molten ground: 6.8 % of the map, clump 7.17, 70 %
non-edge, and it is where the smoke effects go (73 % of `volcano_greatsmoke.mse`
placements stand on the `lava` class, 64 % of them on this exact texture).

`n/flame area/tile01.dds` (slot 6) is the road and plaza: 3.9 % cover, clump 6.85, 59 %
non-edge, mean slope **4.01 deg** -- the flattest slot in the palette. Set
`RoadSpec.tile_index = 6`.

The `metin2_boss_entrance.txt` variant (8 slots, `metin2_map_labyrinth`) reuses the same
seven textures in the same order and collapses to a single **69.7 %** `valcano_03` base,
adding `dawnmistwood/dawnmistwood_field001.dds` as an 0.6 % accent.

**How the archetype paints** (`stats-tiles.json` `by_archetype.flame_field`):
role share **lava 75.9 %**, rock 20.1 %, paved 4.0 %, dirt 0.0001; base role `lava` in 4
maps and `rock` in 1; median 5 slots used of 7 declared; top-3 share median 0.890;
`stipple_same_family_share` 0.5 (over the four stipple pairs that exist at all).

---

## Environment

**Canonical `map_n_flame_01.msenv`** -- cluster C06 `ember_orange`, on 5 of 6 maps; the
sixth (`labyrinth`) uses its near-clone `map_boss_entrance.msenv`, also C06.

| Parameter | Value |
|---|---|
| `Fog.Enable` | 1 x6 |
| `Fog.NearDistance` / `FarDistance` | 1,000 / **30,000 cm** |
| `Fog.Color` | `#85361C` -- hue 14.9 deg, **sat 0.789**, value 0.522 |
| `Background.Ambient` | `#623101` (level 0.1948) |
| `Character.Ambient` | level 0.3448 = Background + 0.15 |
| `Background.Diffuse` | **`#5DAA9A`** -- `light_warmth -0.2431`, a cool teal key |
| `Direction` | `0.620509 0.492475 -0.610275` (sun elev 37.6 deg, az 231.6 deg) |
| Gradient | **Upper 7** / Lower 1 -- the highest band count in the corpus |
| Sky zenith -> horizon -> nadir | `#1F0000` -> `#87381F` -> **`#FF8700`** |
| `Material.Ambient` | `#3F13E1` -- a violet material ambient, unique here |
| Cloud | **`clouds_zone02.tga`**, scale 200000, texture scale 5, speed 0.01, height 30000 |
| Skybox faces | none ; `Filter.Enable` 0 ; `LensFlare.Enable` 0 |

Two things a generator must not average away: the **teal diffuse against the orange
sky** (warmth -0.24 is the most negative in any outdoor archetype), and the **nadir
`#FF8700`**. The below-horizon band is what lights the ground from underneath and sells
the "standing on cooling lava" read. `map_n_flame_01` and `map_boss_entrance` push it to
`#FF8700`; the C06 siblings `trent.msenv` and `moonlight05.msenv` go to pure `#FF0000`
(`environments.md` sec 5 C06).

Fog saturation 0.789 is the highest of any outdoor archetype.

---

## Object palette

**Density 1.24 obj/ha = 0.0124 per 100 m^2 = 8.1 per sector** -- the emptiest archetype --
53 distinct CRCs across 399.77 ha. Mix: Tree 61.5 %, Building 26.0 %,
**Effect 12.5 %** (the highest effect share of any outdoor archetype).
Clark-Evans R = 0.690, the *least* clustered outdoor archetype.

Family budget:

| Family | n | per ha | NN same-family p25/p50/p75 (cm) | Clark-Evans R |
|---|---|---|---|---|
| `tree/b2` | 294 | 0.74 | 2,820 / **3,756** / 4,742 | 0.654 clustered |
| `effect/background` | 62 | 0.16 | 3,553 / 14,041 / 17,176 | **0.973 Poisson** |
| `zone/n/obj/map_n_flame_01` | 48 | 0.12 | 1,109 / 1,659 / 3,220 | 0.243 |
| `zone/b/obj` | 33 | 0.08 | 112 / 154 / 231 | 0.015 |
| `zone/dungeon/flame_dungeon` | 31 | 0.08 | 984 / 1,417 / 2,078 | 0.081 |
| `tree/b3` | 11 | 0.03 | 1,883 / 2,402 / 3,441 | 0.088 |
| `zone/n/flame` | 7 | 0.02 | ~28,600-30,600 | -- |
| `zone/dungeon/flame_dragon` | 6 | 0.02 | 481 / 3,681 / 5,754 | -- |
| `zone/dungeon/boss_dungeon_awake` | 4 | 0.01 | -- | -- |

`effect/background` at R = 0.973 is one of only two families in the corpus scored
Poisson-random. Smoke plumes are scattered one per vent, not clumped.

### Tier table (directly usable as `MapSpec.objects`)

`density` per 100 m^2; `spacing_cm` = NN(same CRC) p5; `max_slope` = per-CRC slope p95;
`road_clearance_cm` = per-CRC d(road) p25; `height_bias` = (bias p25, bias p75).
`on_tiles` indexes the 7-slot palette above.

| tier | crc | name | density | spacing_cm | on_tiles | max_slope | road_clear_cm | height_bias | water_m |
|---|---|---|---|---|---|---|---|---|---|
| signature | 974491171 | `IvySpy_Winter2` (Tree, `tree/b2`) | 0.00445 | 1274 | 1,3,4,7 | 46 | 200 | (-72, 0) | 33/164/574 **(33, inf)** |
| signature | 3449844455 | `IvySpy_Winter1` (Tree, `tree/b2`) | 0.00290 | 1467 | 1,3,4,7 | 45 | 0 | (-120, 0) | 37/102/228 **(37, inf)** |
| signature | 1178450968 | `volcano_greatsmoke.mse` (Effect, `effect/background`) | 0.00100 | 1628 | 5,4 | 67 | 0 | (-200, 0) | 85/134/524 **(85, inf)** |
| signature | 1253733280 | `volcano_biglongsmoke.mse` (Effect, `effect/background`) | 0.00030 | `TODO: no catalog evidence` (outside the 420-row per-CRC block) | 5,4 | -- | -- | -- | n/a |
| filler | 163114965 | `general_obj_bigtower03.gr2` (Building, `zone/n/obj/map_n_flame_01`) | 0.00050 | 2270 | 1,2,3 | 20 | 0 | (-15, 0) | 212/656/666 **(212, inf)** |
| filler | 1484581411 | `flame_fence_01` (Building, `zone/dungeon/flame_dungeon`) | 0.00020 | 867 | 3,4,7 | 57 | 447 | (0, 47) | 89/101/102 **(89, inf)** |
| accent | 1013185983 | `warpgate02_01` (Building, `zone/b/obj`) | 0.00023 | 12363 | 6 | 3 | 0 | (-10, 0) | 14/127/202 **(14, inf)** |
| accent | 2077239231 | `warpgate02` (Building, `zone/b/obj`) | 0.00023 | 23176 | 6 | 5 | 0 | (-5, 0) | 35/166/327 **(35, inf)** |
| accent | 1812446801 | `warpgate03` (Effect, `effect/background`) | 0.00015 | 7800 | 6 | 5 | 0 | (-20, 0) | 78/128/199 **(78, inf)** |
| accent | 929619867 | `warpgate01` (Effect, `effect/background`) | 0.00008 | 5512 | 6 | 3 | 0 | (55, 55) | 31/123/225 **(31, inf)** |
| accent | 2406144081 | `Pagoda_Winter2` (Tree, `tree/b3`) | 0.00015 | 0 | 1,3 | 43 | 1247 | (-165, -4) | 9/65/142 (0, inf) |
| accent | 2399981002 | `Pagoda_Winter1` (Tree, `tree/b3`) | 0.00013 | 0 | 1,3 | 45 | 860 | (-165, 0) | 10/90/165 (0, inf) |
| accent | 4083482882 | `bigstone_bridge.GR2` (Building, `zone/n/flame`) | 0.00018 | `TODO: no catalog evidence` | 1,3 | -- | -- | -- | n/a |
| accent | 1753372283 | `general_obj_bigtower05.gr2` (Building, `zone/n/obj/map_n_flame_01`) | 0.00013 | `TODO: no catalog evidence` | 1,3 | -- | -- | -- | n/a |
| accent | 2750674910 | `boss_d_gate_01` (Building, `zone/dungeon/boss_dungeon_awake`) | 0.00010 | `TODO: no catalog evidence` | 3 | -- | -- | -- | n/a |
| accent | 1370453778 | `stone02` (Building, `zone/dungeon/flame_dungeon`) | 0.00010 | `TODO: no catalog evidence` | 3,7 | -- | -- | -- | n/a |
| accent | 1877709817 | `dragon_gate` (Building, `zone/dungeon/flame_dragon`) | 0.00008 | `TODO: no catalog evidence` | 3 | -- | -- | -- | n/a |
| accent | 123351605 | `general_obj_stonedoor.gr2` (Building, `zone/n/obj/map_n_flame_01`) | 0.00008 | `TODO: no catalog evidence` | 1,3 | -- | -- | -- | n/a |
| accent | 501538206 | `general_obj_bigtower06.gr2` (Building, `zone/n/obj/map_n_flame_01`) | 0.00008 | `TODO: no catalog evidence` | 1,3 | -- | -- | -- | n/a |
| accent | 885871462 | `general_obj_bigtower07.gr2` (Building, `zone/n/obj/map_n_flame_01`) | 0.00008 | `TODO: no catalog evidence` | 1,3 | -- | -- | -- | n/a |

`water_m` = observed distance to the nearest water, p25/p50/p75 in metres (`affinity.json` `by_crc[crc].d_water_cm`; `~` = the family's figure where the CRC has none). The bold `(min, inf)` is the suggested `MapSpec.water_distance_m` for species that measurably avoid water. A species that tolerates it gets no constraint; give oasis or shore decoration a `(0, max)` band instead -- do NOT try to pin it to the shore texture, which is a stipple and covers only a handful of tiles.


The CRCs marked `TODO` are real and used, but their placement counts fall below the
420-row cutoff at which `stats-objects.json.by_crc` publishes per-CRC spacing, rotation,
bias and slope. Use the family figures above for them, or leave them out -- they are
1-7 records each.

`general_obj_bigtower03.gr2` is worth noting for its rotation: **yaw non-zero in 32 % of
records and pitch non-zero in 36 %**. It is one of the few Buildings in the corpus that
tilts (`placement.md` sec 1.1) -- a leaning basalt tower.

---

## Placement rules

**Ground affinity** (`affinity.json` `by_archetype.flame_field`, n = 496):
**rock 76.0 %**, tile 13.3 %, lava 10.3 %, field 0.4 %. Nothing on grass, sand or snow at
all. Object slope p50 5.1 deg, p75 13.35 deg, **p95 48.0 deg** -- the widest object slope band of
any archetype, because the smoke effects go on the steep vents (their own slope p50 is
27.9 deg).

**Positive rules**

1. **Emptiness is the art direction.** 1.24 obj/ha, 8.1 per sector. A 6x6 flame map
   carries ~400 objects. Do not fill it.
2. **Two vine CRCs and nothing else growing.** `IvySpy_Winter2` + `IvySpy_Winter1`,
   `tree/b2`, NN p50 3,756 cm. They cling to rock: 66-71 % of their ground is rock.
   d(road) p25 0-200 cm -- the vines grow *on* the paths.
3. **Smoke on the magma, one per vent.** `volcano_greatsmoke.mse` sits on
   `valcano_magma_01` in 64 % of records, at 27.9 deg median slope, d(road) p50 = 0, and it
   is scattered near-Poisson. Effects are raised: corpus-wide, Effect bias p50 is
   +410 cm and 93.2 % of Effect records have positive bias (`placement.md` sec 1.3).
4. **The warpgate cluster is the only "settlement".** Four warpgate CRCs, all on
   `n/flame area/tile01.dds`, all at d(road) 0, all on 0-5 deg ground. If the map has a hub
   it is a paved pad with a warp on it.
5. Road grammar (pooled, n = 2 maps, see caveat): width median 7.0 m, tortuosity 1.41
   (the twistiest measured), 7.42 junctions/km, 1.59 loops/km, blend band 3.0 m.

**Negative rules**

- **`tree/b2` is never placed on `(none)` or snow.** `flame_fence_01` is never on
  `(none)`, grass, lava, other, sand, snow or tile -- 93 % of its records are on rock.
- **`volcano_greatsmoke.mse` is never on `(none)`, field, grass, sand, snow or tile.**
  It only goes on lava, other and rock.
- **No grass, sand or snow ground anywhere.** Four ground classes exist in this
  archetype and one of them (field) is 0.4 %.
- **No water.** `water_cell_fraction` 0.0, zero wet cells, zero `ATTRIBUTE_WATER`.
- **No `tree/b1`, `n1`, `n2`.** Only `b2` (294) and a token 11 `b3`.
- **No dither.** This is the exception to the corpus stipple rule; regions are correct
  here and only here (plus `eastplain` and the block dungeons -- see
  `stats-tiles.json.maps_with_no_stipple`).

---

## Attr policy

`slope_driven` on `metin2_map_n_flame_01` and `metin2_map_labyrinth`; `painted_box` on
the three sungzi hills.

| Setting | Value (for a sculpted flame field) |
|---|---|
| `attr_style` | `slope_driven` |
| `block_slope_deg` | **21** (`n_flame_01`'s fitted threshold; `labyrinth` fits 10) |
| `border_band_m` | **303 m** archetype median seal; `n_flame_01` strict band 49 m |
| `safezone_regions` | 4 tiny components across 4 maps -- median 154 m^2, bbox edge 14 m |

Archetype block budget over 2,602,495 cells: slope 53.0 %, water 0.0 %, object halo
0.5 %, out-of-bounds 44.6 %, residual 1.8 %. On `n_flame_01` alone: **slope 75.3 %**,
out-of-bounds 19.3 %, object halo 0.9 %. The 44.6 % archetype figure is the three sungzi
hills, which block 96.5 % of their cells.

- **Only four distinct attr bytes exist in the whole archetype** and **no paint bytes
  above `0x07`**. Alongside `desert`, this is the cleanest attr data in the corpus.
- **Never paint `ATTRIBUTE_WATER`.** Zero wet cells.
- **Footprint policy is `no_buildings` on three of five maps** -- literally nothing to
  stamp. On `n_flame_01` it is `painted`: 72.1 % of Building centre cells and **85.5 % of
  Effect centre cells** are blocked, but only 7.5 % of Tree centre cells. Blocking under
  a smoke plume is unusual and worth reproducing: the vents are not walkable.
- Safezone components here are the **smallest in the corpus**: median 154 m^2, 14 m
  bbox edge -- a single 14 m disc, presumably a warp pad. Three circle-brush, one
  rectangular fill (the `labyrinth` sector).
- Rim slope median 21 deg versus interior 12 deg (`attributes.md` sec 8) -- a modest ridge, not a
  wall.

---

## Tells

1. **`GradientLevelUpper 7`.** No other file in the corpus uses seven bands.
2. **Teal light on an orange world.** Diffuse `#5DAA9A`, warmth -0.2431, against fog
   `#85361C` at saturation 0.789.
3. **`#FF8700` nadir.** The below-horizon band is the brightest thing in the sky.
4. **Three bases, no dither.** `valcano_01` + `valcano_03` + `valcano_rock` at 29/23/20 %,
   all solid; stipple pairs per map = 0; base run length 112 tiles.
5. **`UScale` 2 or 3 only.** Repeats of 16 m and 10.7 m -- the coarsest ground in any
   outdoor archetype, matching 512-1024 px art at ~32 px/m.
6. **1.24 objects per hectare.** Eight per sector. Emptiness.
7. **Two vine CRCs.** `IvySpy_Winter1/2` and nothing else grows.
8. **12.5 % effects.** Smoke plumes on the magma, near-Poisson, raised, and standing on
   blocked cells.
9. **`clouds_zone02.tga`** rather than the near-universal `clouds_zone01`.
10. **Zero water, four attr bytes, no paint convention.**

---

## Road grammar confidence

**1 of 2 road-bearing maps here are confirmed roads (50%.)** The rest are
`terrain_ribbon` or `ambiguous` -- soft-edged regions the corridor detector picks
up as tracks. `roads.json.by_archetype` is now filtered to the confirmed set, but
with n=1 the width, curvature and junction figures are **indicative, not
measured**. Treat them as a starting point and check the result by eye.

The path-texture identification and the `d(road)` setbacks are unaffected: both
come from per-slot and per-CRC statistics, not from corridor detection.

## Sources

`corpus-overview.md` sec 4 ; `catalog/map-taxonomy.json` `archetypes.flame_field` ;
`catalog/stats-terrain.json` `by_archetype.flame_field` ;
`catalog/stats-tiles.json` `by_archetype.flame_field`, `maps_with_no_stipple` ;
`textures.md` sec 6 `flame_field` ; `catalog/textures.json`
`texturesets["metin2_n_flame_01.txt"]`, `["metin2_boss_entrance.txt"]` ;
`environments.md` sec 5 C06, sec 6 `flame_field` ; `catalog/environments.json`
`archetype_presets.flame_field` ; `placement.md` sec 1.1, sec 1.3, sec 2, sec 8 ;
`catalog/stats-objects.json` `by_archetype.flame_field`, `by_crc` ;
`catalog/affinity.json` `by_archetype.flame_field`, `by_crc` ;
`attributes.md` sec 4, sec 8, sec 10 ; `catalog/stats-attr.json` `archetypes.flame_field`,
`maps.*` ; `catalog/roads.json` `by_archetype.flame_field` -- pooled and unfiltered,
n = 2 maps, see `roads.json.by_archetype_caveat`.

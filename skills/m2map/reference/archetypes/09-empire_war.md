# 09 -- `empire_war`

**Empire siege-war arenas (three seasonal skins).** 6 maps (3 with own terrain),
12 sectors, 575 object placements. Reference map `metin2_map_empirewar02`.

---

## Identity

**One 2x2 siege layout, shipped three times in three seasons.** `empirewar01` is the
snow skin, `empirewar02` the summer/empire skin, `empirewar03` the desert skin; each has
a `battlearena0N` proxy that reuses its terrain. The three texturesets are the same
13-slot template filled from three different art folders -- `empirewar/snow/`,
`empirewar/summer/`, `empirewar/desert/` -- and they paint almost identically
(`tile03`: 4.698 % vs 4.695 %; `tile01`: 4.117 % vs 3.978 %). This is the cleanest
evidence in the corpus that **a Ymir palette is a template filled from an art folder**
(`textures.md` sec 6 `empire_war`).

The gameplay identity is the `*-bigdam-*` siege-wall family: modular dam/rampart
segments laid on a **1,000 cm or 3,000 cm pitch** on perfectly flat ground (slope p50
and p95 both exactly 0.0 deg). The prop set follows the seasonal skin exactly --
`zone/n/obj/snow.m` 148 records in the snow map, `zone/b/obj` 153 in the empire map,
`zone/n/desert` 147 in the desert map.

It is also the **only archetype in the corpus with unsealed map borders**.

---

## Reference maps

| Map | Size | Sectors | Textureset | Environment | Objects | Terrain |
|---|---|---|---|---|---|---|
| **`metin2_map_empirewar02`** (reference, summer) | 2x2 | 4 | `metin2_map_empirewar02.txt` | `A1.msenv` | 181 | own |
| `metin2_map_empirewar03` (desert) | 2x2 | 4 | `metin2_map_empirewar03.txt` | `desert_02.msenv` | 207 | own |
| `metin2_map_empirewar01` (snow) | 2x2 | 4 | `metin2_map_empirewar01.txt` | `snowm02.msenv` | 187 | own |
| `metin2_map_battlearena01/02/03` | 2x2 | 0 | matching | matching | 0 | `proxy:empirewarNN` |

- **Typical and flagship size 2x2** -- every member.
- Half the archetype is proxies. Three maps carry all the content.
- `empirewar01` and `empirewar03` ship a **loose copy of their own `.msenv`** in the map
  root (`snowm02.msenv`, `desert_02.msenv`); `empirewar02` ships `a1.msenv`. Resolution
  order is map dir first, but in this corpus every one of them is byte-identical to the
  global copy, so nothing changes (`environments.md` sec 8).

---

## Terrain

`style: sculpted`. `stats-terrain.json` `by_archetype.empire_war`, 3 maps, 12 sectors --
the smallest terrain sample of any archetype.

| Quantity | Value |
|---|---|
| `height_range_cm` | **2,947.5** - 28,475.0; p5 15,990, **p50 17,295**, p95 22,991 |
| Relief per sector | p25 14,591 cm, **p50 18,966 cm**, p75 19,554 cm, p90 20,144 cm |
| `slope_p50` | **16.1 deg** |
| `slope_p95` | **77.8 deg** (p75 52.1 deg, p90 70.0 deg, mean 27.0 deg) |
| `flat_fraction` (< 5 deg) | **0.396** (< 2 deg 0.327, < 10 deg 0.455, < 20 deg 0.527) |
| `roughness` (abs Laplacian r=1) | p50 24.5 cm, p90 339.5, **p99 1,609.5** |
| Local std 3x3 | p50 52.5 cm, p90 430.5, p99 2,057.5 |
| Water cells | **32.9 %** -- the highest of any archetype |
| Blocked cells | 52.3 % -- the lowest of any sculpted archetype |

This shape is unusual and worth reading carefully. **Relief per sector is 19 m** -- the
highest in the corpus by a wide margin, on maps of only four sectors -- while
`frac_lt_2deg` is 0.327 and only 52 % of cells are blocked. The layout is: a large flat
arena floor, a third of the map under water, and a violently steep rim. The p99 roughness
of 1,610 cm confirms it: there are cliff edges here with 16 m steps.

Build it as **a flat pan inside a moat inside a wall**, not as rolling terrain.

---

## Textureset recipe

**`metin2_map_empirewar01.txt`** (snow), 13 slots, measured on `empirewar01` +
`battlearena01`. The summer set `metin2_map_empirewar02.txt` is structurally identical --
same 13 slots, same motif order (`field01-03`, `grass01-02`, `stone01-03`, `tile01-04`,
`river01`), same UV scales, only the folder differs. `weight` = measured `ground_share`;
sums to 1.000.

| slot | role | path (snow skin) | U/V | repeat | weight |
|---|---|---|---|---|---|
| 1 | `mid` | `d:/ymir work/terrainmaps/empirewar/snow/field01.dds` | 5/5 | 6.4 m | 0.247 |
| 2 | `accent` | `d:/ymir work/terrainmaps/empirewar/snow/field02.dds` | 6/6 | 5.3 m | 0.003 |
| 3 | `mid` | `d:/ymir work/terrainmaps/empirewar/snow/field03.dds` | 5/5 | 6.4 m | 0.254 |
| 4 | `mid` | `d:/ymir work/terrainmaps/empirewar/snow/grass01.dds` | 6/6 | 5.3 m | 0.075 |
| 5 | `shore` | `d:/ymir work/terrainmaps/empirewar/snow/grass02.dds` | 9/9 | 3.6 m | 0.000 |
| 6 | `cliff` | `d:/ymir work/terrainmaps/empirewar/snow/stone01.dds` | 8/8 | 4.0 m | 0.173 |
| 7 | `cliff` | `d:/ymir work/terrainmaps/empirewar/snow/stone02.dds` | 9/9 | 3.6 m | 0.001 |
| 8 | `cliff` | `d:/ymir work/terrainmaps/empirewar/snow/stone03.dds` | 5/5 | 6.4 m | 0.147 |
| 9 | `mid` | `d:/ymir work/terrainmaps/empirewar/snow/tile01.dds` | 4/4 | 8.0 m | 0.041 |
| 10 | `accent` | `d:/ymir work/terrainmaps/empirewar/snow/tile02.dds` | 5/5 | 6.4 m | 0.013 |
| 11 | `mid` | `d:/ymir work/terrainmaps/empirewar/snow/tile03.dds` | 5/5 | 6.4 m | 0.047 |
| 12 | `unused` | `d:/ymir work/terrainmaps/empirewar/snow/tile04.dds` | 5/5 | 6.4 m | 0.000 |
| 13 | `unused` | `d:/ymir work/terrainmaps/empirewar/snow/river01.dds` | 5/5 | 6.4 m | 0.000 |

To build the **summer** skin, substitute `empirewar/summer/` for `empirewar/snow/` in
every path and keep everything else. To build the **desert** skin, use
`metin2_map_empirewar03.txt`'s 11 slots: replace the first two `field` entries with
`empirewar/desert/sand01.dds` and `sand02.dds`, and drop `tile04` and `river01`.

**`river01` and `tile04` are dead in every season.** Declare them for fidelity or drop
them; they are painted zero tiles in all three maps.

There is no `path` slot in the snow or summer palettes -- the pavement here is
`tile01`/`tile03`, scored `mid` because they carry 4-5 % of the ground rather than the
<4 % the `path` rule requires. **`paved` is 9.6 % of this archetype's painted tiles**,
the second-highest in the corpus after `arena_pvp`. If you need a road, use slot 9 or 11.

**How the archetype paints** (`stats-tiles.json` `by_archetype.empire_war`):
role share dirt 41.0 %, rock 29.9 %, sand 13.7 %, **paved 9.6 %**, grass 5.9 %; base role
`dirt` x2, `sand` x1; median 10 slots used of 13; base share 0.254; **`edge_density`
0.397 and `interior_fraction` 0.281** -- this ground is nearly all boundary;
**`mean_run_h_of_base` 2.49 tiles**, essentially the corpus median of 2;
5 dither-only slots per map carrying 36.6 % of tiles; `stipple_same_family_share` 0.231.

`empire_war` is one of the most heavily stippled archetypes in the corpus -- the opposite
of `flame_field`.

---

## Environment

**Three envs, two maps each, and no majority** -- each seasonal pair borrows the
environment of the terrain it is cut from (`environments.json`
`archetype_presets.empire_war`). `desert_02.msenv` is nominated canonical only because
C02 is the modal cluster.

| Env | Maps | Cluster | Use for |
|---|---|---|---|
| `snowm02.msenv` | `empirewar01`, `battlearena01` | C02 `overcast_haze` | the snow skin |
| `A1.msenv` | `empirewar02`, `battlearena02` | C00 `clear_blue_noon` | the summer/empire skin |
| `desert_02.msenv` | `empirewar03`, `battlearena03` | C02 `overcast_haze` | the desert skin |

**Pick by terrain, not by archetype.**

| Parameter | Observed over all 6 |
|---|---|
| `Fog.Enable` | 1 x6 |
| `Fog.NearDistance` | 1 - 5,000 cm (median 2) |
| `Fog.FarDistance` | 20,000 - 40,000 cm (median 30,000) |
| `Fog.Color` | `#AEAFBA` (snow), `#B0BDD6` (summer), `#AC9C85` (desert) |
| `Background.Ambient` | `#000000` (summer) or `#44464B` (snow/desert) |
| `Background.Diffuse` | `#FFF8F8`, `#A8A8A8`, `#FFFFFF`; warmth 0.0 - 0.028 |
| sun elevation / azimuth | 48.5 - 48.7 deg / 211.9 deg, 244.7 deg |
| Gradient | Upper 5 x4, 4 x2 / Lower 1 x6 |
| Sky zenith -> horizon | `#1849A8` -> `#D9E6FF` (summer); `#0A2D59` -> `#AEB0BA` (snow); `#010F69` -> `#B5834B` (desert) |
| Cloud | `clouds_zone01` (200000/4/0.004) or `clouds_zone05` (**280000**/5/0.01) |
| Skybox faces | none ; `Filter.Enable` 0 ; `LensFlare.Enable` 0 |

`snowm02.msenv` carries `CloudScale 280000` -- the snow signature shared with
`n-snowm01.msenv` and `metin2_map_n_snow_dungeon_01.msenv`, three files in the corpus.

---

## Object palette

**Density 7.31 obj/ha = 0.0731 per 100 m^2 = 47.9 per sector**, 117 distinct CRCs across
78.64 ha. Mix: **Building 78.8 %**, Tree 19.7 %, Effect 1.6 %. Clark-Evans R = 0.608 --
one of the least clustered archetypes, because the siege walls are laid on a grid.

Family budget -- note how evenly the three seasonal prop sets split:

| Family | n | per ha | NN same-family p25/p50/p75 (cm) | Clark-Evans R |
|---|---|---|---|---|
| `zone/b/obj` (summer) | 153 | 1.95 | 100 / **781** / 1,208 | 0.549 |
| `zone/n/obj/snow.m` (snow) | 148 | 1.88 | 464 / **995** / 1,117 | 0.282 |
| `zone/n/desert` (desert) | 147 | 1.87 | 500 / **873** / 1,000 | 0.231 |
| `tree/n2` | 45 | 0.57 | 2,713 / 3,817 / 5,212 | 0.597 |
| `tree/n1` | 34 | 0.43 | 3,145 / 4,724 / 6,023 | 0.596 |
| `tree/b1` | 34 | 0.43 | 3,228 / 4,654 / 6,013 | 0.603 |
| `effect/background` | 9 | 0.11 | 15,954 / 15,954 / 42,053 | **1.623 regular** |
| `zone/b/building` | 5 | 0.06 | 3,815 / 8,653 / 24,647 | -- |

`effect/background` at R = 1.623 is the **most regular family in the entire corpus** --
nine warpgates, one per spawn point.

### Tier table (directly usable as `MapSpec.objects`)

`density` per 100 m^2; `spacing_cm` = NN(same CRC) p5; `max_slope` = per-CRC slope p95;
`road_clearance_cm` = per-CRC d(road) p25; `height_bias` = (bias p25, bias p75).
`on_tiles` indexes the 13-slot palette above.

Use **one** seasonal block, not all three.

| tier | crc | name | skin | density | spacing_cm | on_tiles | max_slope | road_clear_cm | height_bias | water_m |
|---|---|---|---|---|---|---|---|---|---|---|
| signature | 2384266347 | `snow-bigdam-02` (Building, `zone/n/obj/snow.m`) | snow | 0.00560 | **1000** | 1,3,4 | 0 | 626 | (-10, -10) | 0/4/11 (0, inf) |
| signature | 695307364 | `snow-bigdam-04` (Building, `zone/n/obj/snow.m`) | snow | 0.00280 | **3000** | 1,3,4,9 | 0 | 697 | (-10, -10) | 0/2/8 (0, inf) |
| signature | 2289739122 | `desert-bigdam-02` (Building, `zone/n/desert`) | desert | 0.00381 | **1000** | 1,9 | 0 | 450 | (0, 0) | 31/76/177 (0, inf) |
| signature | 2698076810 | `desert-bigdam-04` (Building, `zone/n/desert`) | desert | 0.00242 | `TODO: no catalog evidence` | 1,9 | -- | -- | -- | n/a |
| signature | 178856905 | `ob-bigdam-03` (Building, `zone/b/obj`) | summer | 0.00254 | **2000** | 1,3,4,9 | 54 | 400 | (-10, -10) | 0/0/4 (0, inf) |
| signature | 3476577188 | `ob-bigdam-04` (Building, `zone/b/obj`) | summer | 0.00242 | **3000** | 1,3,4 | 49 | 1122 | (-10, -10) | 0/2/10 (0, inf) |
| signature | 589233579 | `ob-bigdam-02` (Building, `zone/b/obj`) | summer | 0.00216 | `TODO: no catalog evidence` | 1,3,4 | -- | -- | -- | n/a |
| filler | 1401373405 | `ob-7-03-01` (Building, `zone/b/obj`) | summer | 0.00254 | 336 | 4,9 | 29 | 3248 | (-50, 0) | 2/27/63 (0, inf) |
| filler | 1861988977 | `desert_woodfence03` (Building, `zone/n/desert`) | desert | 0.00165 | 394 | 1,9 | 31 | -- | (-46, 0) | 39/101/535 **(39, inf)** |
| accent | 1609982784 | `JoshuaTree_RT_03` (Tree, `tree/n2`) | desert | 0.00178 | 636 | 1,6,8 | 55 | 50 | (-879, -60) | 180/350/592 **(180, inf)** |
| accent | 333987398 | `Palmetto_RT_03` (Tree, `tree/n2`) | desert | 0.00165 | 3817 | 1,3 | 36 | 1135 | (-95, -28) | 6/96/163 (0, inf) |
| accent | 1107711305 | `Pagoda3` (Tree, `tree/b1`) | summer | 0.00165 | 1503 | 1,3,4 | 47 | 565 | (-152, -20) | 17/68/178 (0, inf) |

`water_m` = observed distance to the nearest water, p25/p50/p75 in metres (`affinity.json` `by_crc[crc].d_water_cm`; `~` = the family's figure where the CRC has none). The bold `(min, inf)` is the suggested `MapSpec.water_distance_m` for species that measurably avoid water. A species that tolerates it gets no constraint; give oasis or shore decoration a `(0, max)` band instead -- do NOT try to pin it to the shore texture, which is a stipple and covers only a handful of tiles.


**The dam kit is the whole archetype.** `snow-bigdam-02` has NN(same CRC) at exactly
1,000 cm for p25, p50 *and* p75 -- a wall segment laid on a 10 m module.
`snow-bigdam-04` and `ob-bigdam-04` sit at exactly 3,000 cm. `ob-bigdam-03` at 2,000 cm.
All of them at slope p50 **0.0 deg** and bias **-10 cm**.

Every dam CRC also has **yaw zero in 100 % of records** -- a siege wall never tilts. Roll
zero-share runs 0.08-0.64, so headings do vary, but only around Z and only in multiples
of 15 deg like everything else.

---

## Placement rules

**Positive rules**

1. **Flatten the arena floor to 0 deg, then lay the wall on a module.** Segment pitch
   1,000 / 2,000 / 3,000 cm, bias -10 cm, yaw and pitch exactly 0.
2. **Match the prop family to the skin.** snow -> `zone/n/obj/snow.m`;
   summer -> `zone/b/obj`; desert -> `zone/n/desert`. Roughly 148 records per map either
   way. Do not mix.
3. **Put the walls near the water.** `snow-bigdam-02` d(water) p25 = 0, p50 = 400 cm;
   34 % of its records stand on a wet cell. `ob-bigdam-03` d(water) p50 = 0 and 44 % on
   water. The dam is *in* the moat.
4. **Buildings 1,579 cm from the road, trees 6,827 cm** (`placement.md` sec 5).
5. **One warpgate per spawn.** Nine `effect/background` records at R = 1.623. Space them
   deliberately, not randomly.
6. Trees are sparse decoration at 38-47 m spacing, mixed across whichever seasonal tree
   family fits (n2 desert, n1 snow, b1 summer -- 34-45 records each).

**Negative rules**

- **`snow-bigdam-02` is never on `(none)`, lava, other, sand, snow or tile;**
  `desert-bigdam-02` never on `(none)`, grass, lava, other, sand or snow;
  `snow-bigdam-04` additionally never on rock. These are *field-and-grass* props even in
  the snow and desert skins, because the skin is a texture swap and the terrain
  underneath is the same layout.
- **Do not paint `river01` or `tile04`.** Dead in all three seasons.
- **No safezone.** Zero components across the archetype.
- **No `zone/b/building` town.** 5 records.
- **No DungeonBlock records.**

---

## Attr policy

`attr_style: slope_driven` on all three maps with terrain; footprint policy `painted` on
all three.

| Setting | Value |
|---|---|
| `attr_style` | `slope_driven` |
| `block_slope_deg` | **26** (fitted 26, 26, 21) |
| `border_band_m` | **0 m** -- see below |
| `safezone_regions` | none |

Block budget over 398,562 cells: **slope 79.3 %**, water 9.4 %, object halo 6.0 %,
out-of-bounds 4.1 %, residual 1.2 %. Only **50.7 %** of cells blocked -- the most open
archetype in the corpus.

- **The border is not sealed.** `metin2_map_empirewar01` and `_02` have **45.4 % of edge
  cells blocked, 1,118 m of holes and a median edge run of 0 m** -- they are two of the
  five unsealed maps in the whole corpus (`attributes.md` sec 8). `empirewar03` is sealed
  with a 20 m band. If you are reproducing the archetype faithfully, **do not seal the
  border**; the arena's edges are open because the server confines the players.
- **Rim slope median 51 deg versus interior 12 deg** -- the second-steepest rim in the corpus.
  The wall is there geometrically; it just is not painted blocked.
- **All three maps paint `ATTRIBUTE_WATER`** (3 of 3, the best rate in the corpus), but
  Jaccard against `water.wtr` is only 0.088 -- they paint the flag on a small subset.
- **Object halo is 6.0 % of block and 17.8 % of block cells are within 12 m of a
  placement.** The dam walls carve a lot of the collision.
- 83.4 % of Building centre cells blocked, 37.2 % of Tree, **0 % of Effect** -- warpgates
  are deliberately walkable.
- Only **three distinct attr bytes** in the whole archetype; no paint bytes above `0x07`.

---

## Tells

1. **One layout, three folders.** `empirewar/{snow,summer,desert}/` filling the same
   13-slot template with the same UV scales.
2. **`river01` and `tile04` declared and never painted**, in all three seasons.
3. **A wall on a 10 m module.** `snow-bigdam-02` NN p25 = p50 = p75 = 1,000 cm.
4. **Everything flat.** Object slope p50 0.0 deg for the whole dam family.
5. **A third of the map is water and the dam stands in it.** 32.9 % water cover, walls
   at d(water) 0-400 cm.
6. **19 m of relief per sector.** A flat pan inside a very steep rim.
7. **Unsealed borders.** Two of the corpus's five unsealed maps.
8. **9.6 % paved ground.** Second only to `arena_pvp`.
9. **Nine warpgates at Clark-Evans R = 1.623** -- the most regularly spaced family in the
   corpus.
10. **Three attr bytes, no safezone, 50.7 % block.** The most open collision in the
    corpus.

---

## Border occlusion

**Terrain ridge.** The outer 64 m sits **+1724 cm** above the interior (corner ring +2001 cm). Set `border_ridge_cm` near that and let the fog keep a clear foreground.

Scale the *width* to the map: the measurement ring is 64 m, which on a 1x1 map (256 m) would consume half the playable surface. Keep the lift, narrow the rise.

Measured over the outer 64 m against the interior; see `../taste.md` for the corpus-wide table and the two traps when building a rim.

## Sources

`corpus-overview.md` sec 4 ; `catalog/map-taxonomy.json` `archetypes.empire_war`,
`maps.*` ; `catalog/stats-terrain.json` `by_archetype.empire_war` ;
`catalog/stats-tiles.json` `by_archetype.empire_war` ; `textures.md` sec 6 `empire_war` ;
`catalog/textures.json` `texturesets["metin2_map_empirewar01.txt"]`,
`["metin2_map_empirewar02.txt"]`, `["metin2_map_empirewar03.txt"]` ;
`environments.md` sec 6 `empire_war`, sec 8 ; `catalog/environments.json`
`archetype_presets.empire_war` ; `placement.md` sec 1.1, sec 5, sec 8 ;
`catalog/stats-objects.json` `by_archetype.empire_war`, `by_crc` ;
`catalog/affinity.json` `by_archetype.empire_war`, `by_crc` ;
`attributes.md` sec 4, sec 8, sec 10 ; `catalog/stats-attr.json` `archetypes.empire_war`,
`maps.*`.

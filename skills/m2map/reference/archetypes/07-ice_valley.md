# 07 -- `ice_valley`

**Snake valley / white-dragon ice valley.** 3 maps, 47 sectors, 1,549 object
placements. Reference map `metin2_map_snakevalley`.

---

## Identity

A high, narrow, snow-dusted ravine system with near-vertical rock walls and spear-shaped
standing stones jammed into the cliff faces at an angle. It is the **steepest archetype
in the corpus**: slope p50 28.4 deg, only 7.6 % of cells under 2 deg, and only 16.2 % under 5 deg.

Its palettes are a blend rather than a family -- the bespoke `snakevalley/` art pack
mixed with `n/snow.m` snow, `capedragonhead` stone and a little `dawnmistwood` and
`mtthunder`. Its object identity is `zone/snakevalley`: 332 records of `SpearRock_00*`
and `invocation_stone0*`, all in `metin2_map_snakevalley`, and they are **the most
extreme placement in the corpus** -- slope p50 26.3 deg, p75 40.3 deg, bias p50 -86 cm, yaw
non-zero in 39.9 % and pitch non-zero in 33.6 % of records, and a median distance to the
nearest road of 10,909 cm (`placement.md` sec 8).

Recognise it by: the tilt. Nowhere else does the corpus rotate objects on all three axes
this often, and nowhere else does it place them this far from any path.

---

## Reference maps

| Map | Size | Sectors | Textureset | Environment | Objects | Terrain |
|---|---|---|---|---|---|---|
| **`metin2_map_snakevalley`** (reference) | 6x3 | 18 | `metin2_map_snakevalley.txt` | `snakevalley.msenv` | 591 | own |
| `metin2_map_icecrystalcave` | 5x4 | 20 | `metin2_map_whitdragonvalley.txt` | `metin2_map_icecrystalcave.msenv` | 502 | own |
| `metin2_map_whitdragonvalley` | 3x3 | 9 | `metin2_map_whitdragonvalley.txt` | `metin2_map_whitdragonvalley.msenv` | 456 | own |

- **Typical size 6x3.** Three maps, three sizes, three environments; two texturesets.
- All three ship `sungma_attr.txt` in the map root (per-map Sungma stat caps --
  `sungma_str 25 / sungma_hp 15 / sungma_move 25 / sungma_immune 30`,
  `corpus-overview.md` sec 5.3). Only 14 maps in the corpus carry that file and three of
  them are this archetype.
- `snakevalley` and `whitdragonvalley` also ship the edge-blend minimap set
  (`minimap_top.dds`, `minimap_lefttop.dds`, ...) -- 8 maps in the corpus do.

The two sub-recipes differ sharply: `snakevalley` is a **20-slot rock mosaic** with
`zone/snakevalley` props; `whitdragonvalley`/`icecrystalcave` are a **14-slot snow
palette** (70 % `n/snow.m/snow02.dds`) with the `zone/n/obj/snow.m` kit. Choose one.

---

## Terrain

`style: sculpted`, all three. `stats-terrain.json` `by_archetype.ice_valley`, 3 maps,
47 sectors.

| Quantity | Value |
|---|---|
| `height_range_cm` | 5,623.5 - **32,767.5** (uint16 ceiling); p5 15,107, **p50 18,452**, p95 26,254 |
| Relief per sector | p25 7,372 cm, **p50 10,672 cm**, p75 12,955 cm, p90 16,137 cm |
| `slope_p50` | **28.4 deg** -- the steepest in the corpus |
| `slope_p95` | **66.0 deg** (p75 49.1 deg, p90 60.8 deg, mean 29.9 deg) |
| `flat_fraction` (< 5 deg) | **0.162** (< 2 deg **0.076**, < 10 deg 0.284, < 20 deg 0.421) |
| `roughness` (abs Laplacian r=1) | p50 30.5 cm, p90 160.5, p99 451.5 |
| Local std 3x3 | p50 92.5 cm, p90 287.5 cm |
| Water cells | **9.1 %** |
| Blocked cells | 70.3 % |

Relief of 10.7 m per sector at a 28 deg median slope: this is a ravine system, not a
mountain range with valleys. Height spans nearly the whole uint16 range (5,624 to
32,767 cm) -- the deepest floor-to-peak span of any archetype.

---

## Textureset recipe

Two palettes. Given here: **`metin2_map_snakevalley.txt`**, 20 slots, on
`metin2_map_snakevalley` only. `weight` = measured `ground_share`; sums to 1.000.
It is the most *evenly* spread palette in the corpus -- its largest single share is 23.1 %.

| slot | role | path | U/V | repeat | weight |
|---|---|---|---|---|---|
| 1 | `mid` | `d:/ymir work/terrainmaps/b/stone/stone01_01.dds` | 2/2 | 16.0 m | 0.025 |
| 2 | `mid` | `d:/ymir work/terrainmaps/snakevalley/grass01.dds` | 1/1 | 32.0 m | 0.079 |
| 3 | `cliff` | `d:/ymir work/terrainmaps/capedragonhead/capedragon_stone001.dds` | 2/2 | 16.0 m | 0.138 |
| 4 | `accent` | `d:/ymir work/terrainmaps/snakevalley/field02_1.dds` | 2/2 | 16.0 m | 0.014 |
| 5 | `mid` | `d:/ymir work/terrainmaps/capedragonhead/capedragon_field001.dds` | 2/2 | 16.0 m | 0.064 |
| 6 | `mid` | `d:/ymir work/terrainmaps/a/beach/beach sand 01.dds` | 2/2 | 16.0 m | 0.024 |
| 7 | `mid` | `d:/ymir work/terrainmaps/snakevalley/grass01_1.dds` | 2/2 | 16.0 m | 0.017 |
| 8 | `cliff` | `d:/ymir work/terrainmaps/snakevalley/cliff01.dds` | 2/2 | 16.0 m | 0.231 |
| 9 | `cliff` | `d:/ymir work/terrainmaps/snakevalley/cliff02.dds` | 2/2 | 16.0 m | 0.030 |
| 10 | `cliff` | `d:/ymir work/terrainmaps/snakevalley/cliff03.dds` | 2/2 | 16.0 m | 0.011 |
| 11 | `path` / road | `d:/ymir work/terrainmaps/snakevalley/field03_1.dds` | 1/1 | 32.0 m | 0.015 |
| 12 | `base` | `d:/ymir work/terrainmaps/snakevalley/field02.dds` | 2/2 | 16.0 m | 0.134 |
| 13 | `mid` | `d:/ymir work/terrainmaps/snakevalley/field03.dds` | 1/1 | 32.0 m | 0.065 |
| 14 | `unused` | `d:/ymir work/terrainmaps/capedragonhead/capedragon_grass003.dds` | 2/2 | 16.0 m | 0.000 |
| 15 | `cliff` | `d:/ymir work/terrainmaps/n/snow.m/stone03.dds` | 2/2 | 16.0 m | 0.056 |
| 16 | `shore` | `d:/ymir work/terrainmaps/b/beach/beach sand 01.dds` | 4/4 | 8.0 m | 0.077 |
| 17 | `cliff` | `d:/ymir work/terrainmaps/dawnmistwood/dawnmistwood_rock001.dds` | 2/2 | 16.0 m | 0.015 |
| 18 | `accent` | `d:/ymir work/terrainmaps/dawnmistwood/dawnmistwood_grass001.dds` | 2/2 | 16.0 m | 0.003 |
| 19 | `accent` | `d:/ymir work/terrainmaps/mtthunder/mtthunder_field04.dds` | 4/4 | 8.0 m | 0.002 |
| 20 | `accent` | `d:/ymir work/terrainmaps/b/field/field 03_01.dds` | 4/4 | 8.0 m | 0.000 |

**Six cliff slots.** `cliff01` (23.1 %, 42 deg mean slope), `capedragon_stone001` (13.8 %,
41 deg), `n/snow.m/stone03` (5.6 %, 37 deg), `cliff02` (3.0 %, 55 deg), `dawnmistwood_rock001`
(1.5 %, 47 deg), `cliff03` (1.1 %, 56 deg). On terrain with a 28 deg median slope, that is
correct: most of the map *is* cliff, and the artist gave it six distinct rock skins to
avoid repeat.

`snakevalley/field03_1.dds` (slot 11) is the road: 1.47 % cover, clump 6.16, 38 %
non-edge, 2.73 deg mean slope. Set `RoadSpec.tile_index = 11`.

**The alternate palette `metin2_map_whitdragonvalley.txt`** (14 slots, on
`metin2_map_icecrystalcave` + `metin2_map_whitdragonvalley`) inverts the emphasis: slot
12 `n/snow.m/snow02.dds` is the base at **70.0 %**, and the `snakevalley/` art is demoted
to cliffs and accents. Three of its 14 slots are dead and three more sit below 0.01 %.
Use it for a snow ravine, the 20-slot set for a rock ravine.

**How the archetype paints** (`stats-tiles.json` `by_archetype.ice_valley`):
role share snow 43.2 %, rock 25.7 %, dirt 19.3 %, grass 8.0 %, sand 3.9 %; base role
`snow` x2, `rock` x1; median 11 slots used of 14 declared; median base share 0.677 but
the range is 0.231-0.752 across only three maps; `mean_run_h_of_base` median 9.4 tiles;
**`stipple_same_family_share` 0.000** -- when this archetype dithers, it always dithers
*across* art packs, never within one. That is unique in the corpus and it is a direct
consequence of the palette being a mosaic of five folders.

---

## Environment

Three maps, three one-off environments, but they share a structural signature
(`environments.json` `archetype_presets.ice_valley`):

| Env | Map | Cluster |
|---|---|---|
| **`metin2_map_icecrystalcave.msenv`** (canonical) | `icecrystalcave` | C00 `clear_blue_noon` |
| `metin2_map_whitdragonvalley.msenv` | `whitdragonvalley` | C00 `clear_blue_noon` |
| `snakevalley.msenv` | `snakevalley` | C01 `murky_lowlight` (off-cluster) |

| Parameter | Observed over all 3 |
|---|---|
| `Fog.Enable` | 1 x3 |
| `Fog.NearDistance` | 100 - 5,000 cm (median 100) |
| `Fog.FarDistance` | 20,000 - 29,000 cm (median 25,000) |
| `Fog.Color` | `#A4C8FF`, `#7E8CAE`, `#4C4F33` |
| `Background.Ambient` | `#282B38`, `#282C39`, `#3D4246` (level 0.182 - 0.258) |
| `Background.Diffuse` | `#919AAC`, `#A0AEA3`, `#A5C6DE` -- **light warmth -0.012 to -0.224, always cool** |
| `Direction` | `0.609035 0.37155 -0.700733` x3 (sun elev 44.5 deg, az 238.6 deg) |
| **Gradient** | **Upper 2 / Lower 2 x3** |
| Sky zenith | `#003371`, `#0C2855`, `#1C1672` |
| Cloud | `clouds_zone01.tga`, scale 200000, texture scale 4, **speed 0.001**, **height 10000** |
| Skybox faces | `bayblacksand` declared at `bTextureRenderMode 0` -- never displayed |

**`GradientLevelLower 2` is the signature.** Only five files in the whole corpus use
Lower 2 and **three of them are here** (`environments.md` sec 6 `ice_valley`). Combined
with `GradientLevelUpper 2`, `CloudHeight 10000` (against the near-universal 30000),
`CloudSpeed 0.001` and a consistently cool blue diffuse, the three files are clearly one
authored family despite clustering apart.

Declare the `bayblacksand` face set if you want fidelity, but know it never renders --
`bTextureRenderMode` is 0 in all three (`environments.md` sec 4.2).

---

## Object palette

**Density 5.03 obj/ha = 0.0503 per 100 m^2 = 33.0 per sector**, 136 distinct CRCs across
308.02 ha. Mix: **Building 62.8 %**, Tree 36.9 %, Effect 0.3 %.

Family budget:

| Family | n | per ha | NN same-family p25/p50/p75 (cm) | Clark-Evans R |
|---|---|---|---|---|
| `tree/n1` | 492 | 1.60 | 1,076 / **1,800** / 2,977 | 0.555 |
| `zone/n/obj/snow.m` | 343 | 1.11 | 327 / **369** / 412 | 0.085 |
| `zone/snakevalley` | 332 | 1.08 | 451 / **683** / 1,378 | 0.237 |
| `zone/b/obj` | 237 | 0.77 | 0 / **115** / 170 | 0.060 |
| `tree/b3` | 72 | 0.23 | 0 / 669 / 1,994 | 0.178 |
| `zone/n/icemount/icebon` | 27 | 0.09 | 1,642 / 2,142 / 3,279 | 0.176 |
| `zone/eastplain` | 19 | 0.06 | 2,588 / 5,041 / 7,708 | 0.280 |
| `zone/ydragon` | 9 | 0.03 | 5,665 / 9,716 / 10,045 | 0.288 |

`zone/n/obj/snow.m` at NN p25/p50/p75 = 327/369/412 cm is one of the tightest and most
*regular*-within-cluster distributions in the corpus -- a fence kit laid at a fixed pitch.

### Tier table (directly usable as `MapSpec.objects`)

`density` per 100 m^2; `spacing_cm` = NN(same CRC) p5; `max_slope` = per-CRC slope p95;
`road_clearance_cm` = per-CRC d(road) p25; `height_bias` = (bias p25, bias p75).
`on_tiles` indexes the 20-slot `metin2_map_snakevalley.txt` palette above.

| tier | crc | name | density | spacing_cm | on_tiles | max_slope | road_clear_cm | height_bias |
|---|---|---|---|---|---|---|---|---|
| signature | 2713011117 | `SpearRock_002` (Building, `zone/snakevalley`) | 0.00295 | 451 | 3,8,9,10,12 | 66 | **7766** | (-157, -31) |
| signature | 687416296 | `SpearRock_003` (Building, `zone/snakevalley`) | 0.00237 | 0 | 3,8,12 | 45 | **6119** | (-106, -11) |
| signature | 997685939 | `SpearRock_004` (Building, `zone/snakevalley`) | 0.00097 | 0 | 3,8,12 | 58 | **10418** | (-311, -3) |
| signature | 711692756 | `invocation_stone03` (Building, `zone/snakevalley`) | 0.00084 | 1908 | 8,12 | 50 | 7299 | (-385, 0) |
| signature | 2142209084 | `invocation_stone02` (Building, `zone/snakevalley`) | 0.00081 | 1640 | 8,12 | 58 | 6215 | (-406, -91) |
| signature | 1416455319 | `invocation_stone01` (Building, `zone/snakevalley`) | 0.00058 | `TODO: no catalog evidence` | 8,12 | -- | -- | -- |
| filler | 3370024845 | `WhitePine1` (Tree, `tree/n1`) | 0.00354 | 2681 | 2,7,12,13 | 19 | 0 | (-40, -31) |
| filler | 239479779 | `ColoradoBlueSpruce1` (Tree, `tree/n1`) | 0.00240 | 1305 | 2,7,12,13 | 21 | 565 | (-80, -8) |
| filler | 2988076545 | `ColoradoBlueSpruce2` (Tree, `tree/n1`) | 0.00211 | 1129 | 2,7,12,13 | 24 | 282 | (-80, -31) |
| filler | 1313531708 | `Beech_Winter3` (Tree, `tree/n1`) | 0.00201 | 2933 | 2,7,12,13 | 26 | 1372 | (-80, -40) |
| filler | 2418081500 | `Beech_Winter1` (Tree, `tree/n1`) | 0.00198 | 2717 | 2,7,12,13 | 25 | 847 | (-80, -12) |
| filler | 4193629000 | `MontereyCypress_Winter2` (Tree, `tree/n1`) | 0.00179 | 2509 | 2,7,12,13 | 37 | 262 | (-80, -40) |
| filler | 3641533454 | `MontereyCypress_Winter1` (Tree, `tree/n1`) | 0.00101 | 1809 | 2,7,12,13 | 26 | 1094 | (-80, -31) |
| filler | 1155967375 | `ob-7-02-01` (Building, `zone/n/obj/snow.m`) | 0.00205 | 323 | 12,13 | 14 | 7892 | (-41, -15) |
| filler | 3874655559 | `ob-7-03-01` (Building, `zone/n/obj/snow.m`) | 0.00205 | 380 | 12,15 | 39 | 4912 | (-55, -18) |
| filler | 923239313 | `general_obj_fence03` (Building, `zone/n/obj/snow.m`) | 0.00198 | 358 | 12,15 | 9 | 0 | (-29, 0) |
| accent | 2399981002 | `Pagoda_Winter1` (Tree, `tree/b3`) | 0.00104 | 0 | 2,12 | 46 | 860 | (-165, 0) |
| accent | 2406144081 | `Pagoda_Winter2` (Tree, `tree/b3`) | 0.00058 | 0 | 2,12 | 43 | 1247 | (-165, -4) |
| accent | 1552435463 | `B_general_obj_22` (Building, `zone/b/obj`) | 0.00094 | 53 | 12,13 | 9 | 0 | (-5, 0) |
| accent | 2487845082 | `ob-7-01` (Building, `zone/n/obj/snow.m`) | 0.00062 | 1067 | 12,13 | 9 | 5630 | (-64, -24) |

---

## Placement rules

**Ground affinity** (`affinity.json` `by_archetype.ice_valley`, n = 1,549):
snow 34.3 %, field 26.3 %, rock 26.3 %, grass 7.5 %, `(none)` 5.3 %, sand 0.3 %. Object
slope p50 8.07 deg, p75 17.18 deg, **p95 43.76 deg**. The `(none)` share of 5.3 % is the highest
in the corpus -- 82 placements sit on unpainted `tile.raw` byte 0.

**Positive rules**

1. **Jam the spear rocks into the cliffs, at an angle, far from anything.**
   `SpearRock_002/003/004`: slope p50 19.6-39.2 deg, p95 45-66 deg; `never_on` snow, sand,
   lava, other, tile -- they go on rock and field only; **yaw non-zero in 54-60 % and
   pitch non-zero in 36-38 % of records**; bias p50 -47 to -174 cm; d(road) p25
   6,100-10,400 cm. This is the most distinctive placement rule in the whole corpus.
2. **`invocation_stone01/02/03` go even harder**: `invocation_stone02` has **pitch
   non-zero in 60 % of records** and sits on rock 92 % of the time at 25.9 deg median
   slope, sunk 182 cm.
3. **Trees are the winter conifer set at 18 m spacing.** `tree/n1` NN p50 1,800 cm,
   sunk -80 cm (except `WhitePine1` at -40), roll zero in 80-94 % of records, pitch
   exactly 0.
4. **The snow prop kit is a fence at a fixed pitch.** `zone/n/obj/snow.m` NN
   327/369/412 cm, roll almost never 0 (2.7-21 % zero-share), placed 5,000-8,000 cm from
   the road.
5. **Roads are heavily blended and busy.** Width median 7.0 m, 9.37 junctions/km,
   tortuosity 1.29, **blend band 9.0 m** -- the widest in the corpus after nothing;
   `ring1_path_share` 0.266.

**Negative rules**

- **`SpearRock_004` and `invocation_stone02/03` are never on grass, lava, other, sand,
  snow or tile.** They are rock/field props exclusively.
- **`tree/n1` never on lava, other or sand**; `tree/b3` `Pagoda_Winter1/2` never on
  lava, snow or tile.
- **No `tree/b1` to speak of** -- 7 records in 1,549.
- **No `tree/n2`.** No arid flora in an ice valley.
- **No safezone.** Zero components across all three maps.
- **No DungeonBlock records.**

---

## Attr policy

`attr_style: slope_driven` on all three maps; footprint policy `painted` on all three.

| Setting | Value |
|---|---|
| `attr_style` | `slope_driven` |
| `block_slope_deg` | **22** (fitted 17, 22, 24) |
| `border_band_m` | **185 m** median seal; strict bands 61-82 m |
| `safezone_regions` | none -- 0 components |

Block budget over 2,141,264 cells: **slope 80.1 %**, water 9.4 %, out-of-bounds 8.6 %,
object halo 1.6 %, residual 0.3 %. 69.5 % of cells blocked. Only four distinct attr
bytes; **no paint bytes above `0x07`**.

- Alongside `field_valley` (81.1 %) and `guild_village` (88.3 %), this is one of the
  three most purely slope-explained archetypes in the corpus. Get the ravine geometry
  right and the collision follows.
- **Water agrees almost perfectly with `water.wtr`: Jaccard 0.924** -- the highest in the
  corpus. One map (`snakevalley`) has water and it paints the flag. On `snakevalley`
  water is 25.7 % of block.
- **96.3 % of Building centre cells blocked, 36.1 % of Tree centre cells.** Stamp the
  spear rocks; leave most conifers walkable.
- Rim slope median 36 deg versus interior 14 deg -- a real wall, and all three sealed strict.
- **No safezone anywhere.** If you generate one, you have left the archetype.

---

## Tells

1. **Tilt.** Yaw non-zero in 40 % and pitch in 34 % of `zone/snakevalley` records. The
   only place in the corpus where three-axis rotation is normal rather than exceptional.
2. **Objects 60-100 m from the nearest road.** `SpearRock_004` d(road) p25 = 10,418 cm.
   Nothing else in any outdoor archetype is placed this remotely.
3. **Six cliff textures.** On a map that is 72 % steeper than 20 deg, one rock skin repeats
   visibly; the artist used six.
4. **`GradientLevelUpper 2` + `GradientLevelLower 2`.** Three of the corpus's five
   `Lower 2` files.
5. **`CloudHeight 10000`** against the near-universal 30000, at `CloudSpeed 0.001`.
6. **Cool light, always.** Diffuse warmth -0.012 to -0.224 in all three files.
7. **Stipple across art packs, never within one.** `stipple_same_family_share` 0.000.
8. **`sungma_attr.txt` in the map root.** All three carry it.
9. **`ATTRIBUTE_WATER` matches `water.wtr` at Jaccard 0.924.** If you paint water here,
   paint it right -- this archetype is the corpus's best-behaved example.
10. **No safezone, no town, no plaza.** 5.3 % of placements stand on unpainted ground.

---

## Sources

`corpus-overview.md` sec 1, sec 4, sec 5.3 ; `catalog/map-taxonomy.json`
`archetypes.ice_valley`, `maps.*` ; `catalog/stats-terrain.json`
`by_archetype.ice_valley` ; `catalog/stats-tiles.json` `by_archetype.ice_valley` ;
`textures.md` sec 6 `ice_valley` ; `catalog/textures.json`
`texturesets["metin2_map_snakevalley.txt"]`, `["metin2_map_whitdragonvalley.txt"]` ;
`environments.md` sec 4.2, sec 6 `ice_valley` ; `catalog/environments.json`
`archetype_presets.ice_valley` ; `placement.md` sec 1.1, sec 1.4, sec 8 ;
`catalog/stats-objects.json` `by_archetype.ice_valley`, `by_crc` ;
`catalog/affinity.json` `by_archetype.ice_valley`, `by_crc` ;
`attributes.md` sec 4, sec 6, sec 8, sec 10 ; `catalog/stats-attr.json` `archetypes.ice_valley`,
`maps.*` ; `catalog/roads.json` `by_archetype.ice_valley` -- pooled and unfiltered, see
`roads.json.by_archetype_caveat`.

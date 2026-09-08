# 11 -- `arena_pvp`

**PvP arena, OX event and shop plaza.** 6 maps, 15 sectors, 1,226 object placements.
Reference map `metin2_map_oxevent`.

---

## Identity

**The densest archetype in the corpus: 12.47 obj/ha, 81.7 objects per sector, 84.6 %
Building.** These are flat paved stages walled by a repeating segment and filled with
props. Object slope p50 is **0.0 deg** and 41.1 % of terrain cells are under 2 deg -- the
flattest walkable ground the corpus ships.

The identifying object is `a1-038-wall-lin2_duel` (CRC 2929491352): 149 records with
nearest-neighbour p5, p25 and p50 all **exactly 1,000 cm**, slope p50 = p95 = 0.0 deg,
bias 0. It is a wall kit laid on a 10 m module around a circular arena, and it appears in
three maps (`duel`, `pvp_arena`, `oxevent`) at 174/174/171 records combined with its
siblings (`objects.md` sec 3).

The other identifying number is **safezone: 58.7 % of all cells** -- by far the highest in
the corpus. `metin2_map_privateshop` and `metin2_map_oxevent` each mark their **entire
2x2 map** (262,144 cells) as `ATTRIBUTE_BANPK` (`attributes.md` sec 7).

---

## Reference maps

| Map | Size | Sectors | Textureset | Environment | Objects | CRCs |
|---|---|---|---|---|---|---|
| **`metin2_map_oxevent`** (reference) | 2x2 | 4 | `metin2_map_oxevent.txt` | `a1.msenv` | 442 | 99 |
| `metin2_map_guild_battle_base` | 1x1 | 1 | `metin2_map_guild_battle.txt` | `metin2_map_guild_battle_01.msenv` | 253 | 72 |
| `metin2_map_duel` | 1x1 | 1 | `metin2_duel.txt` | `A1.msenv` | 157 | 18 |
| `metin2_map_pvp_arena` | 1x1 | 1 | `metin2_duel.txt` | `A1.msenv` | 157 | 18 |
| `metin2_map_guild_battle` | 2x2 | 4 | `metin2_map_guild_battle.txt` | `metin2_map_guild_battle_01.msenv` | 130 | 51 |
| `metin2_map_privateshop` | 2x2 | 4 | `metin2_map_oxevent.txt` | `a1.msenv` | 87 | 11 |

- **Typical and flagship size 2x2.** All six have their own terrain -- no proxies.
- `metin2_map_duel` and `metin2_map_pvp_arena` are the same content at different
  `BasePosition` (157 objects, 18 CRCs, identical family histogram).
- `metin2_map_privateshop` is 87 objects of which **80 are `zone/b/building`** -- a shop
  plaza, nothing else.

---

## Terrain

**Mixed style.** `slope_driven` on `guild_battle`, `guild_battle_base`, `privateshop`;
`painted_box` on `duel`, `pvp_arena`, `oxevent`.
`stats-terrain.json` `by_archetype.arena_pvp`, 6 maps, 15 sectors.

| Quantity | Value |
|---|---|
| `height_range_cm` | 11,463.5 - 25,661.0; p5 15,921, **p50 16,547**, p95 21,609 |
| Relief per sector | p25 7,622 cm, **p50 7,996 cm**, p75 9,133 cm, p90 9,351 cm |
| `slope_p50` | **16.3 deg** |
| `slope_p95` | **70.9 deg** (p75 54.4 deg, p90 66.8 deg, mean 26.7 deg) |
| `flat_fraction` (< 5 deg) | **0.438** (< 2 deg **0.411**, < 10 deg 0.472, < 20 deg 0.516) |
| `roughness` (abs Laplacian r=1) | p50 16.5 cm, p90 216.5, p99 667.5 |
| Water cells | **13.3 %** |
| Blocked cells | **78.8 %** |

Read the distribution, not the median: **41.1 % of cells are under 2 deg and only 51.6 %
under 20 deg**, with p75 at 54 deg. There is essentially no middle ground. The arena is a dead
flat floor surrounded by a near-vertical wall of terrain, and 78.8 % of the map is
blocked. The 16.3 deg "median slope" is an artefact of averaging those two populations.

Generate: a flat plate, then a rim that goes vertical immediately.

---

## Textureset recipe

**`metin2_map_oxevent.txt`**, 17 slots, on `metin2_map_oxevent` + `metin2_map_privateshop`
(`textures.json` `texturesets["metin2_map_oxevent.txt"]`). `weight` = measured
`ground_share`; sums to 1.000.

| slot | role | path | U/V | repeat | weight |
|---|---|---|---|---|---|
| 1 | `cliff` | `d:/ymir work/terrainmaps/a/stone/stone01.dds` | 5/5 | 6.4 m | 0.164 |
| 2 | `unused` | `d:/ymir work/terrainmaps/a/stone/stone04.dds` | 6/6 | 5.3 m | 0.000 |
| 3 | `mid` | `d:/ymir work/terrainmaps/c/tile/tile04.dds` | 5/5 | 6.4 m | 0.085 |
| 4 | `mid` | `d:/ymir work/terrainmaps/c/tile/tile05.dds` | 6/6 | 5.3 m | 0.063 |
| 5 | `accent` | `d:/ymir work/terrainmaps/a/tile/tile02.dds` | 9/9 | 3.6 m | 0.002 |
| 6 | `accent` | `d:/ymir work/terrainmaps/a/grass/grass 02.dds` | 8/8 | 4.0 m | 0.006 |
| 7 | `mid` | `d:/ymir work/terrainmaps/a/grass/grass 03.dds` | 9/9 | 3.6 m | 0.312 |
| 8 | `unused` | `d:/ymir work/terrainmaps/ema1/tile/tile01.dds` | 5/5 | 6.4 m | 0.000 |
| 9 | `unused` | `d:/ymir work/terrainmaps/b/grass/grass 02_01.dds` | 4/4 | 8.0 m | 0.000 |
| 10 | `unused` | `d:/ymir work/terrainmaps/trent/tile/tile01.dds` | 5/5 | 6.4 m | 0.000 |
| 11 | `mid` | `d:/ymir work/terrainmaps/a/field/field 05.dds` | 5/5 | 6.4 m | 0.313 |
| 12 | `mid` | `d:/ymir work/terrainmaps/trent/tile/tile02.dds` | 5/5 | 6.4 m | 0.049 |
| 13 | `unused` | `d:/ymir work/terrainmaps/a/tile/tile01.dds` | 5/5 | 6.4 m | 0.000 |
| 14 | `accent` | `d:/ymir work/terrainmaps/n/desert/sand/sand03.dds` | 5/5 | 6.4 m | 0.004 |
| 15 | `unused` | `d:/ymir work/terrainmaps/b/tile/tile03.dds` | 5/5 | 6.4 m | 0.000 |
| 16 | `cliff` | `d:/ymir work/terrainmaps/ema1/beach/beach sand 03.dds` | 5/5 | 6.4 m | 0.000 |
| 17 | `unused` | `d:/ymir work/terrainmaps/ema1/stone/stone03.dds` | 7/7 | 4.6 m | 0.000 |

**Seven of seventeen slots are dead.** This palette is an editor scratch pad assembled
from five art packs (`a/**`, `b/**`, `c/tile`, `trent/tile`, `ema1/**`, `n/desert`), and
the map paints only ten of them. Two textures -- `a/field/field 05.dds` (31.3 %) and
`a/grass/grass 03.dds` (31.2 %) -- carry nearly two thirds of the ground as an interleaved
pair. `dither_only_tile_share` median for the archetype is **0.722**.

**`paved` is 13.5 % of the archetype's painted tiles** -- the highest in the corpus. Four
distinct pavement textures (`c/tile/tile04`, `c/tile/tile05`, `trent/tile/tile02`,
`a/tile/tile02`) are live. Build a real plaza.

**Broken data to know about.** `metin2_map_guild_battle.txt` is **the most damaged
palette in the pack**: 6 of its 17 slots point at `terrainmaps/guild_battle/`, which does
not exist in the extracted art dump, and those 6 carry **92.2 %** of the ground of
`metin2_map_guild_battle` + `_base` (`guild_cliff01.dds` alone is 61.0 %). Everything
measured about them comes from `tile.raw` only -- no colour, no resolution
(`textures.md` sec 6 `arena_pvp`, sec 7.2). Prefer `metin2_map_oxevent.txt` as a template.

`metin2_duel.txt` (5 slots, `duel` + `pvp_arena`) is the minimal variant.

**How the archetype paints** (`stats-tiles.json` `by_archetype.arena_pvp`):
role share rock 30.5 %, dirt 26.8 %, grass 26.5 %, **paved 13.5 %**, sand 2.7 %;
base role `grass` x3, `rock` x2, `dirt` x1; median 7.5 slots used of 17 declared
(unused fraction 0.412); `edge_density` median 0.466 and `interior_fraction` 0.173 -- the
most boundary-dominated ground in the corpus; `mean_run_h_of_base` median **1.88 tiles**,
below the corpus median of 2.

---

## Environment

**Canonical `a1.msenv`** -- cluster C00 `clear_blue_noon` on both envs; one of six
cluster-pure archetypes. `metin2_map_guild_battle_01.msenv` differs from `a1.msenv` only
in that it writes the skybox face block with `bTextureRenderMode 0` and five **empty**
face strings -- visually identical (`environments.md` sec 6 `arena_pvp`).

| Parameter | Value (identical across all 6 maps) |
|---|---|
| `Fog.Enable` | 1 |
| `Fog.NearDistance` / `FarDistance` | 5,000 / 20,000 cm |
| `Fog.Color` | `#B0BDD6` |
| `Background.Ambient` | `#000000` (level 0.0) |
| `Character.Ambient` | level 0.15 = Background + 0.15 |
| `Background.Diffuse` | `#FFF8F8`, warmth 0.0275 |
| `Direction` | `0.350156 0.562609 -0.748907` (sun elev 48.5 deg, az 211.9 deg) |
| Gradient | Upper 4 / Lower 1 |
| Sky zenith -> horizon -> nadir | `#1849A8` -> `#D9E6FF` -> `#88909F` |
| Cloud | `clouds_zone01.tga`, 200000 / 4 / 0.004 / 30000 |
| Skybox faces | none rendered ; `Filter.Enable` 0 ; `LensFlare.Enable` 0 |

This is the game's default sky, unmodified. An arena is a gameplay space, not a mood
piece -- do not invent an environment for it.

---

## Object palette

**Density 12.47 obj/ha = 0.1247 per 100 m^2 = 81.7 per sector**, 193 distinct CRCs
across 98.3 ha. Mix: **Building 84.6 %**, Tree 11.3 %, **Effect 4.2 %**.

Family budget:

| Family | n | per ha | NN same-family p25/p50/p75 (cm) | Clark-Evans R |
|---|---|---|---|---|
| `zone/b/obj` | 530 | **5.39** | 165 / **255** / 622 | 0.266 |
| `zone/b/building` | 180 | 1.83 | 900 / **1,000** / 2,253 | 0.399 |
| `zone/duel` | 179 | 1.82 | **1,000 / 1,000 / 1,000** | 0.312 |
| `tree/b1` | 91 | 0.93 | 1,402 / 1,974 / 3,980 | 0.738 |
| `zone/a/building` | 56 | 0.57 | 1,003 / 1,530 / 2,919 | 0.334 |
| `zone/guild_battle` | 56 | 0.57 | 428 / 857 / 1,233 | 0.131 |
| `effect/background` | 49 | 0.50 | 967 / 1,014 / 2,206 | 0.313 |
| `tree/b3` | 42 | 0.43 | 2,276 / 3,102 / 4,517 | 0.486 |
| `zone/c/building` | 13 | 0.13 | 2,409 / 2,953 / 3,526 | 0.266 |

`zone/duel` with p25 = p50 = p75 = **1,000 cm** is the wall. Nothing else in the corpus
has a flat NN quartile spread.

### Tier table (directly usable as `MapSpec.objects`)

`density` per 100 m^2; `spacing_cm` = NN(same CRC) p5; `max_slope` = per-CRC slope p95;
`road_clearance_cm` = per-CRC d(road) p25; `height_bias` = (bias p25, bias p75).
`on_tiles` indexes the 17-slot `metin2_map_oxevent.txt` palette above.

| tier | crc | name | density | spacing_cm | on_tiles | max_slope | road_clear_cm | height_bias | water_m |
|---|---|---|---|---|---|---|---|---|---|
| signature | 2929491352 | `a1-038-wall-lin2_duel` (Building, `zone/duel`) | 0.01516 | **1000** | 3,7,11 | **0** | 2094 | (0, 0) | 0/0/2 (0, inf) |
| signature | 93804060 | `b1-bigdam-04` (Building, `zone/b/building`) | 0.00549 | 1000 | 3,4,11 | 0 | 0 | (0, 0) | 65/120/185 **(65, inf)** |
| signature | 4147623174 | `b1-bigdam-05` (Building, `zone/b/building`) | 0.00326 | 0 | 3,4,11 | 0 | 0 | (0, 0) | 82/124/203 **(82, inf)** |
| signature | 3686638315 | `b1-bigdam-06` (Building, `zone/b/building`) | 0.00285 | 4000 | 3,4,11 | 0 | 0 | (0, 0) | 57/118/193 **(57, inf)** |
| signature | 3050870705 | `a1_018-stonelight-1` (Building, `zone/a/building`) | 0.00326 | 958 | 7,11 | 17 | 100 | (-5, 0) | 0/14/43 (0, inf) |
| filler | 1471924893 | `ob-7-02-01` (Building, `zone/b/obj`) | 0.00661 | 213 | 3,11 | 22 | 0 | (-20, 108) | 51/119/230 **(51, inf)** |
| filler | 2401125466 | `general_obj_flag` (Building, `zone/b/obj`) | 0.00336 | 612 | 3,11,14 | 18 | 0 | (0, 0) | 22/44/96 (0, inf) |
| accent | 2237878140 | `fire_ob-11-02-stonelight01.mse` (Effect, `effect/background`) | 0.00346 | 23 | 3,7,11 | 1 | 0 | (0, 0) | 30/39/69 (0, inf) |

`water_m` = observed distance to the nearest water, p25/p50/p75 in metres (`affinity.json` `by_crc[crc].d_water_cm`; `~` = the family's figure where the CRC has none). The bold `(min, inf)` is the suggested `MapSpec.water_distance_m` for species that measurably avoid water. A species that tolerates it gets no constraint; give oasis or shore decoration a `(0, max)` band instead -- do NOT try to pin it to the shore texture, which is a stipple and covers only a handful of tiles.


**`fire_ob-11-02-stonelight01.mse` is the corpus's only fully parasitic effect: 100 % of
its 36 records lie within 1 m of a non-Effect object** (`placement.md` sec 6) -- it is the
flame on `a1_018-stonelight-1`. Its Clark-Evans R is 0.946, nearly Poisson, because the
lamps themselves are laid at ~1,000 cm around the ring.

Fill the remaining `zone/b/obj` budget (530 records, 5.39/ha) from the generic kit using
`cooccurrence.json.companions_15m`.

---

## Placement rules

**Positive rules**

1. **Build a flat paved ring and wall it at a 10 m pitch.** `a1-038-wall-lin2_duel`
   at exactly 1,000 cm, slope 0.0 deg, bias 0, yaw 0 in 100 % of records, roll zero-share
   0.28 (so headings vary in 15 deg steps as the wall curves).
2. **Fill with props at 2.5 m.** `zone/b/obj` NN p50 255 cm at 5.39/ha.
3. **Buildings 566 cm from paved ground; trees 1,371 cm** (`placement.md` sec 8).
4. **The `b1-bigdam-0*` gate/rampart set is on a 750-3,000 cm module** at slope 0.0 deg and
   d(road) 0-241 cm -- it lines the plaza edge.
5. **Lamps on the ring, flames on the lamps.** `a1_018-stonelight-1` at ~1,000 cm pitch
   with `fire_ob-11-02-stonelight01.mse` inside 1 m.
6. **Flags on the pavement.** `general_obj_flag`, 33 records, slope 0.0 deg, d(road) p25 =
   p50 = 0.
7. **Effects are 4.2 % of placements** -- the highest of any non-dungeon archetype.

**Negative rules**

- **`a1-038-wall-lin2_duel` is never on `(none)`, lava, other, sand or snow** -- field,
  grass, tile and a little rock only. Note it *is* on a wet cell in **71.1 %** of records
  (the duel arena floor sits over water); water is not an exclusion here.
- `b1-bigdam-04/05/06` never on lava, other, sand or snow; `fire_ob-11-02-stonelight01`
  never on `(none)`, lava, other, rock, sand or snow.
- **Do not slope the floor.** Slope p95 of 0.0-0.14 deg on the whole wall and gate set.
- Trees are decoration: 138 records, 11.3 %, at 20-31 m spacing.
- No DungeonBlock records.

---

## Attr policy

**Split 3 `slope_driven` / 3 `painted_box`, and the fitted thresholds collapse to 1 deg on
four maps** -- which is the signature of wholesale paint rather than a terrain rule
(`attributes.md` sec 4). Treat the archetype as `painted_box` unless you are building a
sculpted battleground like `metin2_map_guild_battle`.

| Setting | Value |
|---|---|
| `attr_style` | `painted_box` (carve the arena out of a blocked slab) |
| `block_slope_deg` | not meaningful -- do not fit one. If sculpting, `guild_battle` fitted 12 deg |
| `border_band_m` | **155 m** median seal; strict bands 17-183 m |
| `safezone_regions` | **whole-map fill** on `privateshop` and `oxevent` |

Block budget over 767,873 cells: slope 69.5 %, **object halo 14.2 %** (the highest in the
corpus), out-of-bounds 11.8 %, water 3.8 %, residual 0.8 %. **78.8 % of cells blocked.**

- **25.5 % of all block cells sit within 12 m of a placement.** The props carve the
  arena's collision more than the terrain does. On `metin2_map_oxevent`, object halo is
  **28.5 %** of block.
- **Safezone is 58.7 % of all cells** -- `metin2_map_privateshop` and `metin2_map_oxevent`
  each mark their entire 262,144-cell map. Two components are rectangular fills and two
  are irregular; median area **144,310 m^2**, median bbox edge 368.5 m
  (`attributes.md` sec 7). On these maps the safezone freely overlaps block.
  **Use a whole-map rectangle, not a disc.** That is the opposite of the
  `field_empire` rule.
- Footprint policy: `mixed` x3, `painted` x2, `model_only` x1. 85.8 % of Building and
  88.4 % of Tree centre cells blocked.
- Water: 5 of 6 maps have wet cells, 3 paint the flag, Jaccard 0.317.
- 11 distinct attr bytes -- the most of any outdoor archetype -- and 2 maps write above
  `0x07`.
- Rim slope median 44 deg versus interior **0 deg** (`attributes.md` sec 8). A vertical wall
  around a dead-flat floor.

---

## Tells

1. **A wall at exactly 10 m.** `a1-038-wall-lin2_duel`, NN p5 = p25 = p50 = 1,000 cm.
2. **Slope 0.0 deg on every structural prop**, p95 included.
3. **12.47 obj/ha.** Ten times a lava field, 1.5x an empire capital.
4. **13.5 % paved ground across four distinct pavement textures.**
5. **The whole map is a safezone.** Rectangular `ATTRIBUTE_BANPK` fill on two maps.
6. **The default sky, unmodified.** `a1.msenv`, ambient 0, fog 5,000->20,000.
7. **41 % of cells under 2 deg and 79 % blocked.** A plate inside a vertical wall.
8. **Lamps with flames inside 1 m** -- the corpus's only 100 %-anchored effect.
9. **Seven dead palette slots of seventeen**, and a 61 %-of-ground texture that does not
   exist on disk (`guild_battle/guild_cliff01.dds`).
10. **Object halo is 14.2 % of block.** The furniture is the level.

---

## Road grammar confidence

**3 of 4 road-bearing maps here are confirmed roads (75%.)** The rest are
`terrain_ribbon` or `ambiguous` -- soft-edged regions the corridor detector picks
up as tracks. `roads.json.by_archetype` is now filtered to the confirmed set, but
with n=3 the width, curvature and junction figures are **indicative, not
measured**. Treat them as a starting point and check the result by eye.

The path-texture identification and the `d(road)` setbacks are unaffected: both
come from per-slot and per-CRC statistics, not from corridor detection.

## Sources

`corpus-overview.md` sec 4 ; `catalog/map-taxonomy.json` `archetypes.arena_pvp`,
`maps.*` ; `catalog/stats-terrain.json` `by_archetype.arena_pvp` ;
`catalog/stats-tiles.json` `by_archetype.arena_pvp` ; `textures.md` sec 6 `arena_pvp`,
sec 7.2 ; `catalog/textures.json` `texturesets["metin2_map_oxevent.txt"]`,
`["metin2_map_guild_battle.txt"]`, `["metin2_duel.txt"]` ; `environments.md` sec 6
`arena_pvp` ; `catalog/environments.json` `archetype_presets.arena_pvp` ;
`objects.md` sec 3 ; `placement.md` sec 6, sec 8 ; `catalog/stats-objects.json`
`by_archetype.arena_pvp`, `by_crc` ; `catalog/affinity.json` `by_archetype.arena_pvp`,
`by_crc` ; `catalog/cooccurrence.json` ; `attributes.md` sec 4, sec 5, sec 7, sec 8, sec 10 ;
`catalog/stats-attr.json` `archetypes.arena_pvp`, `maps.*`.

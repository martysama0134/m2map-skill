# 17 -- `dev_stub`

**Developer test stub.** 4 maps, 12 sectors, 182 loaded object placements.
Reference map `metin2_map_t1`.

---

## This is a stub, deliberately

**`dev_stub` is not a biome and there is not enough coherent evidence to write it as
one.** These are four unfinished editor test maps that were shipped by accident. They
share no art direction, no environment cluster, no object identity and no consistent
geometry; what they share is that every one of them is **broken in a way the rest of the
corpus is not**.

Use this page as a **negative example and a parser test set**, not as a template. If a
user asks for something that lands here, the right answer is almost always a different
archetype.

Everything below is real and measured, but the honest summary is: n = 4 maps, 12 sectors,
182 objects, 36 distinct CRCs, and four separate shipped defects.

---

## Reference maps

| Map | Size | Sectors | Textureset | Environment | Objects (file / loaded) | `BasePosition` |
|---|---|---|---|---|---|---|
| **`metin2_map_t1`** (reference) | 3x3 | 9 | `metin2_map_t1.txt` | `t1.msenv` | 121 / **44** | (0, 0) |
| `metin2_map_t3` | 1x1 | 1 | `metin2_map_t3.txt` | `moonlight05.msenv` | 64 | **(32000, 0)** |
| `metin2_map_t2` | 1x1 | 1 | `metin2_map_t2.txt` | `t2.msenv` | 42 | **(6400, 0)** |
| `metin2_map_t4` | 1x1 | 1 | `metin2_map_t3.txt` | `moonlight05.msenv` | 32 | **(57600, 0)** |

- Typical size 1x1, "flagship" 3x3.
- **`metin2_map_t2/t3/t4` violate the `BasePosition` alignment rule.** The spec requires
  a multiple of 25,600 (the client sectree); these are 6,400, 32,000 and 57,600 -- all
  multiples of 6,400 (the *server* sector) but not of the sectree
  (`corpus-overview.md` sec 5.4). `gm_guild_build` is the fourth such map and it lives in
  `guild_village`.
- **`metin2_map_t1/setting.txt` is corrupt**: it ends with a stray line `ungeon2.msenv`
  -- a truncated `Environment` value. The shared tokenizer swallows it as a valueless key
  so the client loads the map fine, but a parser that asserts "every key has >= 1 token"
  will not (`corpus-overview.md` sec 5.6).
- **`metin2_map_t1` is the one map where the engine loads fewer objects than the file
  contains.** Its nine `areadata.txt` files each carry **two `ObjectCount` lines** and the
  tokenizer is first-wins, so **44 of 121 blocks load** (`placement.md` sec 8). That is the
  entire 48,851 vs 48,774 discrepancy between `map-taxonomy.json` and
  `stats-objects.json`.
- `t1.msenv` and `t2.msenv` are byte-identical, and identical in content to `war2.msenv`
  bar the fog near value.

---

## Terrain

`slope_driven` on t2/t3/t4, `painted_box` on t1. `stats-terrain.json`
`by_archetype.dev_stub`, 4 maps, 12 sectors.

| Quantity | Value |
|---|---|
| `height_range_cm` | 7,668.0 - **32,767.5** (uint16 ceiling); p5 13,353, **p50 20,640.5**, p95 28,284.5 |
| Relief per sector | p25 12,872 cm, **p50 13,624 cm**, p75 14,476, p90 16,105 |
| `slope_p50` | **48.4 deg** -- by far the steepest in the corpus |
| `slope_p95` | **77.8 deg** (p75 65.3 deg, p90 74.3 deg, mean 43.0 deg) |
| `flat_fraction` (< 5 deg) | **0.136** (< 2 deg 0.104, < 20 deg 0.249) |
| `roughness` (abs Laplacian r=1) | p50 70.5 cm, p90 334.5, p99 959.5 |
| Water cells | **53.9 %** -- the highest in the corpus |
| Blocked cells | **90.2 %** |

**Half of this "terrain" is water and a quarter of it is walkable.** Median slope 48.4 deg
against a corpus median of 5.8 deg. These are not landscapes; they are unfinished
heightmaps.

Do not copy these numbers into a `MapSpec`.

---

## Textureset recipe

**`metin2_map_t3.txt`**, 5 slots, on `t3` + `t4` (`textures.json`
`texturesets["metin2_map_t3.txt"]`). `weight` = measured `ground_share`.

| slot | role | path | U/V | repeat | weight |
|---|---|---|---|---|---|
| 1 | `mid` | `d:/ymir work/terrainmaps/g/field/field 05.dds` | 5/5 | 6.4 m | 0.058 |
| 2 | `mid` | `d:/ymir work/terrainmaps/g/field/field 01.dds` | 6/6 | 5.3 m | 0.060 |
| 3 | `base` | `d:/ymir work/terrainmaps/g/field/cliff_swp_05.dds` | 4/4 | 8.0 m | 0.518 |
| 4 | `base` | `d:/ymir work/terrainmaps/g/field/field 06.dds` | 4/4 | 8.0 m | 0.359 |
| 5 | `accent` | `d:/ymir work/terrainmaps/g/field/field 02.dds` | 4/4 | 8.0 m | 0.005 |

**Three shipped defects in three palettes:**

1. **`metin2_map_t1.txt` (17 slots)** is byte-identical to `metin2_a1.txt` /
   `metin2_b1.txt` / `metin2_c1.txt` -- a verbatim copy of the empire palette. It paints
   very little of it.
2. **`metin2_map_t2.txt` (17 slots) references three textures that do not exist** --
   `g/field/field 03`, `field 04`, `grass 01` -- **and its map paints two of them anyway,
   so 16.6 % of its ground draws the error texture.** It paints only 8 of its 17 slots
   (`textures.md` sec 6 `dev_stub`, sec 7.2).
3. **`metin2_map_t3.txt` writes tile index 8 into a 5-slot palette** -- out of range
   (`textures.md` sec 7.3).

**How the archetype paints** (`stats-tiles.json` `by_archetype.dev_stub`):
role share rock 64.9 %, dirt 23.8 %, grass 10.3 %, paved 0.9 %; base role `rock` x4;
7 slots used of 11 declared (unused fraction 0.306); base share 0.518;
`mean_run_h_of_base` 6.6 tiles; `stipple_same_family_share` 0.667.

Archetype-wide, the most-painted textures are the empire B-pack:
`b/stone/stone01.dds` 44.1 %, `b/field/field 03.dds` 14.1 %, `b/stone/stone04.dds` 8.9 %,
`g/field/cliff_swp_05.dds` 8.6 %, `b/grass/grass 01.dds` 8.4 %.

---

## Environment

**Canonical `moonlight05.msenv`** -- cluster C06 `ember_orange`, on t3 + t4.
`t1.msenv` and `t2.msenv` are C01 `murky_lowlight` (`environments.json`
`archetype_presets.dev_stub`).

| Parameter | Observed over all 4 |
|---|---|
| `Fog.Enable` | 1 x4 |
| `Fog.NearDistance` | 2 - 10,000 cm (median 5,001) |
| `Fog.FarDistance` | 20,000 - 40,000 cm (median 30,000) |
| `Fog.Color` | `#250F10` (moonlight05), `#69594E` (t1/t2) |
| `Background.Ambient` | `#3F504F`, `#725353` (level 0.290 - 0.366) |
| `Background.Diffuse` | `#FFFFFF`, `#A39494` |
| `Direction` | **`0.5 0.5 -0.5`** (moonlight05 -- the engine default) and `0.596551 0.28178 -0.751483` |
| Gradient | Upper 1 x2, 5 x2 / Lower 1 x4 |
| Sky zenith -> horizon -> nadir | `#001326` -> `#2F1500` -> **`#FF0000`** (moonlight05); `#0C0505` -> `#69594E` -> `#2D110F` (t1/t2) |
| Cloud | `clouds_zone01` / `clouds_zone05`, 200000, texture scale 4/5, speed 0.001/0.01, height **4000** / 30000 |

`moonlight05.msenv` is `trent.msenv` with the light direction reset to the engine default
`0.5 0.5 -0.5`, fog moved from 0->18,000 to 10,000->20,000, `CloudHeight` 4,500->4,000 and
`CloudTextureScale` 6->4. **Nothing here is worth generalising from**
(`environments.md` sec 6 `dev_stub`).

---

## Object palette

**Density 2.31 obj/ha = 0.0231 per 100 m^2 = 15.2 per sector**, 36 distinct CRCs across
78.64 ha. Mix: Building 63.2 %, Tree 31.9 %, Effect 4.9 %.
Clark-Evans R = **0.226** -- the most clustered archetype in the corpus, which on
182 objects means "the artist dropped a few piles and stopped".

| Family | n | per ha | NN same-family p25/p50/p75 (cm) | Clark-Evans R |
|---|---|---|---|---|
| `zone/b/obj` | 115 | 1.46 | 104 / **180** / 453 | 0.151 |
| `tree/b1` | 47 | 0.60 | 1,107 / 1,631 / 2,579 | 0.302 |
| `tree/b3` | 11 | 0.14 | 4,705 / 5,228 / 13,052 | 0.667 |
| `effect/background` | 9 | 0.11 | 235 / 236 / 238 | 0.016 |

Generic `zone/b/obj` clutter and b-family trees. Nothing else.

### Tier table

Given for completeness only. `density` per 100 m^2; `spacing_cm` = NN(same CRC) p5;
`max_slope` = per-CRC slope p95; `height_bias` = (bias p25, bias p75).

| tier | crc | name | density | spacing_cm | max_slope | height_bias | water_m |
|---|---|---|---|---|---|---|---|
| filler | 628240070 | `ob-7-02-02` (Building, `zone/b/obj`) | 0.00381 | 143 | 37 | (-20, 0) | 0/5/71 (0, inf) |
| filler | 1401373405 | `ob-7-03-01` (Building, `zone/b/obj`) | 0.00381 | 336 | 29 | (-50, 0) | 2/27/63 (0, inf) |
| filler | 2399205967 | `Beech2` (Tree, `tree/b1`) | 0.00114 | 2934 | 45 | (-91, -13) | 21/61/149 (0, inf) |

`water_m` = observed distance to the nearest water, p25/p50/p75 in metres (`affinity.json` `by_crc[crc].d_water_cm`; `~` = the family's figure where the CRC has none). The bold `(min, inf)` is the suggested `MapSpec.water_distance_m` for species that measurably avoid water. A species that tolerates it gets no constraint; give oasis or shore decoration a `(0, max)` band instead -- do NOT try to pin it to the shore texture, which is a stipple and covers only a handful of tiles.


If you actually want this look, build a `field_empire` map at low density instead.

---

## Attr policy

`slope_driven` on t2/t3/t4, `painted_box` on t1; footprint policy `model_only` x3,
`painted` x1.

| Setting | Value |
|---|---|
| `attr_style` | `slope_driven` |
| `block_slope_deg` | archetype median **10** (fitted 1, 4, 16, 31 -- no signal) |
| `border_band_m` | **93 m** median seal; strict bands 16-64 m |
| `safezone_regions` | none |

Block budget over 705,914 cells: slope 75.6 %, out-of-bounds 16.5 %, water 7.8 %,
object halo 0.1 %, **residual 0.0 %**. **90.2 % of cells blocked.**

Two things worth taking away, both cautionary:

- **All 786,432 cells write paint bytes above `0x07`** -- `flag7` and `object` at 100 %,
  `banshop` at 83 %. All four maps are in the 17-map set that would become **fully
  impassable server-side** under the naive `server_attr` recipe (copy the client byte
  verbatim, read bit 7 as `ATTR_OBJECT`) because `0x80` is set on every cell
  (`attributes.md` sec Discrepancies 3).
- **423,708 wet cells in `water.wtr`, zero `ATTRIBUTE_WATER` painted** (Jaccard 0.000).

Only **22.6 % of Building and 15.5 % of Tree centre cells are blocked** -- the lowest in
the corpus. Nothing was stamped.

---

## Tells

There are no positive tells. The identifying features are the defects:

1. **A corrupt `setting.txt`** (`t1`, stray `ungeon2.msenv` line).
2. **Duplicate `ObjectCount` lines** -- 44 of 121 blocks load in `t1`.
3. **`BasePosition` off the 25,600 sectree grid** on t2/t3/t4.
4. **A palette referencing three textures that do not exist**, two of which are painted
   (`t2`, 16.6 % error texture).
5. **A tile index past `TextureCount`** (`t3` writes 8 into a 5-slot palette).
6. **`0x80` on every attr cell**, four maps.
7. **53.9 % water and 48.4 deg median slope** -- unfinished heightmaps.
8. **A verbatim copy of the empire palette** in `metin2_map_t1.txt`.

Every one of those is a useful regression test for a codec. None of them is a design
decision.

---

## Road grammar confidence

**No map in this archetype has a confirmed road.** 4 of its maps trip the
`has_roads` flag, but the miner's own `road_verdict` classifies every one as a
`terrain_ribbon` or `ambiguous` -- large soft-edged regions the corridor detector
mistakes for tracks. Any corridor grammar previously quoted here (width, loops,
junctions, tortuosity, curvature, blend band) is **withdrawn**, not corrected:
there is no measurement behind it.

If the map needs a road, borrow the grammar from a confirmed-road archetype
(`field_empire`, `field_valley`, `guild_village`) and keep this archetype's own
path texture and setbacks.

## Border occlusion

**Fog, not terrain.** Ring lift is **-36 cm** -- this archetype does not wall its border, and for the negative cases the map sits ON the high ground with the edges falling away. Occlusion comes from the environment instead. Leave `border_ridge_cm` at 0 and keep the archetype's `Fog.NearDistance`, which is what does the work.

Measured over the outer 64 m against the interior; see `../taste.md` for the corpus-wide table and the two traps when building a rim.

## Sources

`corpus-overview.md` sec 4, sec 5.4, sec 5.6, sec 5.7 ; `catalog/map-taxonomy.json`
`archetypes.dev_stub`, `maps.*` ; `catalog/stats-terrain.json`
`by_archetype.dev_stub` ; `catalog/stats-tiles.json` `by_archetype.dev_stub` ;
`textures.md` sec 6 `dev_stub`, sec 7.2, sec 7.3 ; `catalog/textures.json`
`texturesets["metin2_map_t3.txt"]`, `["metin2_map_t2.txt"]`, `["metin2_map_t1.txt"]` ;
`environments.md` sec 6 `dev_stub` ; `catalog/environments.json`
`archetype_presets.dev_stub` ; `placement.md` sec 8, sec 10 ;
`catalog/stats-objects.json` `by_archetype.dev_stub`, `by_crc` ;
`catalog/affinity.json` `by_archetype.dev_stub` ; `attributes.md` sec 10,
sec Discrepancies ; `catalog/stats-attr.json` `archetypes.dev_stub`, `maps.*`.

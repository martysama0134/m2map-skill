# 14 -- `elemental`

**Elemental (Sungma) forest zones.** 4 maps, 77 sectors, 965 object placements.
Reference map `metin2_map_elemental_01`.

---

## Identity

**The purest vegetation archetype in the corpus: 87.1 % Tree, and only 89 building
records across four maps.** It is also nearly empty -- 1.91 obj/ha, second only to
`flame_field` -- and built as a `painted_box`: 90.5 % of cells blocked, walkable
corridors carved through a slab, with the trees standing on the corridor floor.

The palette trick is unmistakable and identical across all three texturesets: **slot 3
is `capedragonhead/capedragon_field001.dds` at `UScale 1` -- a 32 m repeat -- carrying
75.2 %, 75.6 % and 76.4 % of the ground** of `elemental_01/02/03` at clump 7.97. One
enormous low-frequency carpet, then sixteen to nineteen tiny accents on top
(`textures.md` sec 6 `elemental`).

The other signature is engineering rather than art: `metin2_map_elemental_01` and `_02`
are two of only four maps in the corpus that declare **multiple environments**, and the
only two that use `EnvironmentRange` -- a north/south split of the 5x5 map
(`corpus-overview.md` sec 5.2).

---

## Reference maps

| Map | Size | Sectors | Textureset | Environment | Objects | CRCs | `ViewRadius` |
|---|---|---|---|---|---|---|---|
| **`metin2_map_elemental_01`** (reference) | 5x5 | 25 | `metin2_map_elemental_01.txt` | `metin2_map_elemental_01.msenv` (+ `_01_01`) | 361 | 20 | 256 |
| `metin2_map_elemental_03` | 5x5 | 25 | `metin2_map_elemental_03.txt` | `metin2_map_elemental_03.msenv` | 320 | 46 | 256 |
| `metin2_map_elemental_02` | 5x5 | 25 | `metin2_map_elemental_02.txt` | `metin2_map_elemental_02.msenv` (+ `_02_01`) | 250 | 23 | 256 |
| `metin2_map_elemental_04` | 1x2 | 2 | `metin2_map_elemental_01.txt` | `metin2_map_elemental_04.msenv` | 34 | 11 | 256 |

- **Typical and flagship size 5x5.**
- All four ship `contents.obv` in every sector -- a per-sector extra the format spec does
  not list, and the only four maps in the corpus that carry it
  (`corpus-overview.md` sec 1).
- `elemental_01` and `elemental_02` declare `Environment1` plus
  `EnvironmentRange1 <x0> <y0> <x1> <y1> <name>.msenv`. On the 5x5 `elemental_01` the two
  ranges are `0 0 1280 640` and `0 640 1280 1280` -- 5 sectors x 256 = 1280, so **the
  units are half-cells (1 m)**, matching `tile.raw` and `attr.atr` resolution. That is
  inferred from two files only and is not confirmed against loader source
  (`corpus-overview.md` sec 5.2).

---

## Terrain

**`style: box`** -- all four `painted_box`. `stats-terrain.json`
`by_archetype.elemental`, 4 maps, 77 sectors.

| Quantity | Value |
|---|---|
| `height_range_cm` | **0.0** - 31,507.5; **p5 0.0, p50 0.0**, p95 26,130.5 |
| Relief per sector | p25 1,086 cm, **p50 20,658 cm**, p75 25,454 cm, p90 30,123 cm |
| `slope_p50` | **0.025 deg** |
| `slope_p95` | **78.0 deg** (p75 18.6 deg, p90 67.1 deg) |
| `flat_fraction` (< 5 deg) | **0.668** (< 2 deg 0.638, < 20 deg 0.755) |
| `roughness` (abs Laplacian r=1) | **p50 0.5 cm**, p90 109.5, p99 549.5 |
| Water cells | **0.3 %** |
| Blocked cells | **90.5 %** -- the second-highest of any archetype |

**The median height is 0.0 cm.** More than half the terrain sits on the raw floor, and
p95 is 26,130 cm -- the map is a flat plate at zero with 260 m towers of geometry rising
out of it. Relief per sector is 207 m at the median. That combination --
`p50 slope 0.025 deg` with `p50 relief 20,658 cm` -- means the height field is a **step
function**: flat floor, vertical wall, flat mesa.

Build it that way. Do not interpolate the walls.

---

## Textureset recipe

**`metin2_map_elemental_01.txt`**, 19 slots, on `elemental_01` + `elemental_04`
(`textures.json` `texturesets["metin2_map_elemental_01.txt"]`). `weight` = measured
`ground_share`; sums to 1.000.

| slot | role | path | U/V | repeat | weight |
|---|---|---|---|---|---|
| 1 | `path` | `d:/ymir work/zone/dungeon/snow_dungeon/tile_ice00.dds` | 2/2 | 16.0 m | 0.021 |
| 2 | `accent` | `d:/ymir work/zone/dungeon/snow_dungeon/tile_rock00.dds` | 3/3 | 10.7 m | 0.012 |
| 3 | **`base`** | `d:/ymir work/terrainmaps/capedragonhead/capedragon_field001.dds` | **1/1** | **32.0 m** | **0.752** |
| 4 | `cliff` | `d:/ymir work/zone/dungeon/snow_dragon/crack.dds` | 3/3 | 10.7 m | 0.027 |
| 5 | `mid` | `d:/ymir work/terrainmaps/elemental_01/elemental_01_02.dds` | 2/2 | 16.0 m | 0.018 |
| 6 | `mid` | `d:/ymir work/terrainmaps/elemental_01/elemental_01_03.dds` | 2/2 | 16.0 m | 0.024 |
| 7 | `cliff` | `d:/ymir work/terrainmaps/elemental_01/elemental_01_04.dds` | 2/2 | 16.0 m | 0.052 |
| 8 | `path` | `d:/ymir work/terrainmaps/elemental_01/elemental_01_01.dds` | 2/2 | 16.0 m | 0.018 |
| 9 | `shore` | `d:/ymir work/terrainmaps/elemental_01/elemental_01_05.dds` | 4/4 | 8.0 m | 0.003 |
| 10 | `cliff` | `d:/ymir work/terrainmaps/elemental_01/elemental_01_06.dds` | 4/4 | 8.0 m | 0.024 |
| 11 | `cliff` | `d:/ymir work/terrainmaps/elemental_01/elemental_01_07.dds` | 4/4 | 8.0 m | 0.012 |
| 12 | `unused` | `d:/ymir work/terrainmaps/n/snow.m/tile04.dds` | 4/4 | 8.0 m | 0.000 |
| 13 | `unused` | `d:/ymir work/terrainmaps/n/snow.m/tile05.dds` | 4/4 | 8.0 m | 0.000 |
| 14 | `accent` | `d:/ymir work/terrainmaps/n/snow.m/tile02.dds` | 4/4 | 8.0 m | 0.003 |
| 15 | `accent` | `d:/ymir work/terrainmaps/n/snow.m/grass 02.dds` | 4/4 | 8.0 m | 0.001 |
| 16 | `accent` | `d:/ymir work/terrainmaps/guild_village/guild_village_field003.dds` | 2/2 | 16.0 m | 0.010 |
| 17 | `cliff` | `d:/ymir work/terrainmaps/guild_village/guild_village_cliff002.dds` | 2/2 | 16.0 m | 0.022 |
| 18 | `unused` | `d:/ymir work/terrainmaps/n/snow.m/grass 03.dds` | 4/4 | 8.0 m | 0.000 |
| 19 | `accent` | `d:/ymir work/terrainmaps/b/tile/tile03.dds` | 4/4 | 8.0 m | 0.002 |

**Slots 1, 2 and 4 point into `zone/dungeon/**`, not `terrainmaps/**`** -- this is one of
only four palettes in the whole pack that reach outside `terrainmaps/`
(`textures.md` sec 6 `elemental`). Keep the `zone/` prefix; it is a real, resolvable path.

Slots 12-17 are shared verbatim across `elemental_01/02/03`, and `tile04`/`tile05` are
dead in every map.

**How the archetype paints** (`stats-tiles.json` `by_archetype.elemental`):
role share **dirt 78.5 %** (that is `capedragon_field001.dds` by filename motif),
other 10.4 %, rock 5.8 %, lava 2.1 %, paved 1.7 %, grass 0.9 %, sand 0.7 %; base role
`dirt` in all 4; base share median **0.754**; `mean_run_h_of_base` median **440 tiles**;
`interior_fraction` 0.867; `edge_density` 0.062; `singleton_fraction_of_base`
0.817 on three maps and 0.000 on one.

Note the contradiction that is real: the base runs 440 tiles but 82 % of its connected
components are single tiles. One enormous region plus a dust of isolated pixels -- which
is exactly what "one carpet plus nineteen accents" produces.

---

## Environment

**Canonical `metin2_map_elemental_01_01.msenv`** -- cluster C00 `clear_blue_noon`.
Four maps, **six envs**, because `elemental_01` and `_02` each ship a second preset
swapped in by `EnvironmentRange` (`environments.json`
`archetype_presets.elemental`).

| Env | Cluster | Note |
|---|---|---|
| `metin2_map_elemental_01_01.msenv` | C00 `clear_blue_noon` | the `_01` range variant, `Fog.Enable 1` |
| `metin2_map_elemental_01.msenv` | C11 `blue_fog_off` | the base file, `Fog.Enable` **0** |
| `metin2_map_elemental_02_01.msenv` | C00 `clear_blue_noon` | |
| `metin2_map_elemental_02.msenv` | C10 `dusk_fog_off` | `Fog.Enable` **0** |
| `metin2_map_elemental_03.msenv` | C01 `murky_lowlight` | |
| `metin2_map_elemental_04.msenv` | C00 `clear_blue_noon` | |

**The range switch is literally a fog toggle plus a warmer/cooler horizon.** The `_01`
suffix variants have `Fog.Enable 1`; the base files have `Fog.Enable 0`.

| Parameter | Observed over all 4 maps / 6 envs |
|---|---|
| `Fog.Enable` | 1 x4, **0 x2** |
| `Fog.NearDistance` | 1,000 - 5,000 cm (median 5,000) |
| `Fog.FarDistance` | 20,000 - 30,000 cm (median 20,000) |
| `Fog.Color` | `#91B5E6`, `#ECF3FF`, `#BAC8D2`, `#E0E3F0`, `#B86041`, `#1B163F` |
| `Background.Ambient` | `#000000` or `#41586C` (level 0.0 - 0.341) |
| `Background.Diffuse` | `#FFF8F8`, `#FFFFFF`, `#8194AB`; warmth -0.165 - 0.028 |
| sun elevation / azimuth | 32.9 - 48.5 deg / 211.9 deg, 249.5 deg |
| Gradient | Upper 4 / Lower 1 x6 |
| Sky zenith | `#00289D`, `#1D42BC`, `#5D7BDF`, `#375285`, `#042455`, `#000212` |
| Cloud | `clouds_zone01` / `clouds_zone05`, 200000 / 4 / 0.004, height **20000** or 30000 |
| Skybox faces | **`snow_dragon`** (5 of 6) and **`smh`** (elemental_03) -- all at `bTextureRenderMode 0` |

Five of the six write a face block at render mode 0, so **none of the cube textures ever
display** -- including `elemental_03`'s `smh-*.dds` set, which does not exist on disk and
therefore causes no visible breakage (`environments.md` sec 4.2).

---

## Object palette

**Density 1.91 obj/ha = 0.0191 per 100 m^2 = 12.5 per sector**, 65 distinct CRCs across
504.63 ha. Mix: **Tree 87.1 %**, Building 9.2 %, Effect 3.7 %.

Four tree families mixed roughly evenly -- that even mixing is the archetype's forest
recipe:

| Family | n | per ha | NN same-family p25/p50/p75 (cm) | Clark-Evans R |
|---|---|---|---|---|
| `tree/n1` | 310 | 0.61 | 849 / **1,306** / 1,973 | 0.250 |
| `tree/b2` | 237 | 0.47 | 748 / **1,254** / 2,654 | 0.245 |
| `tree/b1` | 187 | 0.37 | 1,121 / **1,614** / 2,037 | 0.199 |
| `tree/n2` | 85 | 0.17 | 146 / **225** / 713 | 0.089 |
| `zone/b/obj` | 78 | 0.15 | 1,157 / 1,457 / 2,457 | 0.574 |
| `effect/background` | 36 | 0.07 | 4,558 / 7,507 / 34,141 | 0.898 |
| `tree/b3` | 21 | 0.04 | 4,876 / 6,209 / 7,799 | 0.286 |

Four biome tree sets in one forest is unique to this archetype. Winter conifers, dead
vines, temperate deciduous and arid scrub all at once.

### Tier table (directly usable as `MapSpec.objects`)

`density` per 100 m^2; `spacing_cm` = NN(same CRC) p5; `max_slope` = per-CRC slope p95;
`road_clearance_cm` = per-CRC d(road) p25; `height_bias` = (bias p25, bias p75).
`on_tiles` indexes the 19-slot palette above.

| tier | crc | name | density | spacing_cm | on_tiles | max_slope | road_clear_cm | height_bias | water_m |
|---|---|---|---|---|---|---|---|---|---|
| signature | 974491171 | `IvySpy_Winter2` (Tree, `tree/b2`) | 0.00228 | 1274 | 3,7,10,11 | 46 | 200 | (-72, 0) | 33/164/574 **(33, inf)** |
| signature | 1114715370 | `Tulip_Winter1` (Tree, `tree/n1`) | 0.00224 | 1278 | 6,7,10 | 42 | **0** | (-99, -80) | 85/190/596 **(85, inf)** |
| signature | 3449844455 | `IvySpy_Winter1` (Tree, `tree/b2`) | 0.00131 | 1467 | 3,7,10,11 | 45 | 0 | (-120, 0) | 37/102/228 **(37, inf)** |
| signature | 476855675 | `CommonOlive_Winter` (Tree, `tree/n1`) | 0.00101 | 2950 | 2,6,14 | 34 | 200 | (-80, -80) | 25/104/442 **(25, inf)** |
| filler | 3689520799 | `Beech4` (Tree, `tree/b1`) | 0.00095 | 2025 | 3,5,6 | 45 | 282 | (-91, -9) | 27/64/143 (0, inf) |
| filler | 2988076545 | `ColoradoBlueSpruce2` (Tree, `tree/n1`) | 0.00093 | 1129 | 2,14 | 24 | 282 | (-80, -31) | 20/55/241 (0, inf) |
| filler | 1353164984 | `Beech1` (Tree, `tree/b1`) | 0.00087 | 2765 | 3,5,6 | 46 | 262 | (-76, -16) | 19/68/167 (0, inf) |

`water_m` = observed distance to the nearest water, p25/p50/p75 in metres (`affinity.json` `by_crc[crc].d_water_cm`; `~` = the family's figure where the CRC has none). The bold `(min, inf)` is the suggested `MapSpec.water_distance_m` for species that measurably avoid water. A species that tolerates it gets no constraint; give oasis or shore decoration a `(0, max)` band instead -- do NOT try to pin it to the shore texture, which is a stipple and covers only a handful of tiles.


`Tulip_Winter1` is the archetype's own species: 113 of its records here, on
`elemental_01/elemental_01_04.dds` (42 %) and `elemental_01/elemental_01_03.dds` (22 %), sunk 80-100 cm, roll
zero in **93.5 %** of records, and **d(road) p25 = p50 = 0** -- the paths run through the
trees (`placement.md` sec 8: tree d(road) p50 = 200 cm, the shortest of any archetype).

Fill the rest of the tree budget from the four families' shared species lists:
`IvySpy_Winter1/2`, `Tulip_Winter1`, `CommonOlive_Winter`, Beech, ColoradoBlueSpruce,
WhitePine.

---

## Placement rules

**Positive rules**

1. **Mix four tree families evenly.** `n1` 310, `b2` 237, `b1` 187, `n2` 85. Nowhere else
   does the corpus do this.
2. **The path runs through the forest.** Tree d(road) p50 = **200 cm** -- every other
   outdoor archetype puts trees 1,500-11,000 cm back. Object slope p50 11.7 deg
   (`placement.md` sec 8).
3. **Sink deep.** `Tulip_Winter1` and `CommonOlive_Winter` at -80 cm p25 *and* p75;
   `IvySpy_Winter1` at -120 cm p25.
4. **Trees mostly unrotated**: roll zero in 79-94 % of the signature species.
5. **Effects are scattered near-Poisson** (R = 0.898), 36 records, 75 m apart.
6. **Almost no buildings.** 89 records in 505 ha. If you place a settlement you have left
   the archetype.

**Negative rules**

- **`Tulip_Winter1` never on grass, lava, sand or tile**; `IvySpy_Winter1/2` never on
  `(none)` or snow; `CommonOlive_Winter` never on `(none)`, lava or sand
  (`affinity.json.by_crc`).
- **No water.** 0.3 % of cells, `attr_water_cells` **0**, and **no map paints the flag**.
- **`tile04`/`tile05` are declared and never painted** in any of the three palettes.
- **No DungeonBlock records** despite the box construction -- the walls are terrain, not
  geometry.
- **No safezone.** Zero components.

---

## Attr policy

**`attr_style: painted_box`** on all four maps; footprint policy `model_only` x3,
`no_buildings` x1.

| Setting | Value |
|---|---|
| `attr_style` | `painted_box` |
| `block_slope_deg` | not meaningful (fitted 23-33, an artefact of wholesale paint) |
| `border_band_m` | **707 m** archetype median seal -- the deepest in the corpus |
| `safezone_regions` | none |

Block budget over 4,550,098 cells: slope 23.4 %, **out-of-bounds 74.6 %**, object halo
1.6 %, water 0.0007 %, residual 0.4 %. **90.5 % of cells blocked.**

- **Only two distinct attr bytes in the entire archetype** -- `0x00` and `0x01`. No water,
  no safezone, no paint convention, no flags. This is the simplest `attr.atr` data in the
  corpus and it is worth matching exactly.
- **Paint everything, carve the corridors.** 74.6 % of block is edge-connected. The
  residual is only 0.4 %, so the carve is clean and geometric.
- **61.5 % of Tree centre cells are blocked** and 43.8 % of Building -- lower than the
  other box archetypes, because most of the map is already blocked and the trees stand in
  the carved-out part.
- Rim slope median 0 deg and interior median 1 deg (`attributes.md` sec 8). The seal is pure
  paint, and it runs away -- hence the 707 m band. Use a **15-30 m block shell** when
  generating; do not try to reproduce a 700 m band literally.
- 3 of 4 maps have wet cells in `water.wtr` (15,000 total) and **none paints
  `ATTRIBUTE_WATER`**.

---

## Tells

1. **One 32 m carpet at 75 % of the ground.** `capedragon_field001.dds` at `UScale 1`.
2. **A palette that reaches into `zone/dungeon/**`.** Three slots do.
3. **87 % Tree, four families, evenly mixed.**
4. **Paths through the trees.** d(road) p50 = 200 cm.
5. **Median height 0.0 cm with 207 m of relief per sector.** A step function, not a
   landscape.
6. **`EnvironmentRange`** -- two of only four multi-environment maps in the corpus, and
   the only two using the range form.
7. **The range switch is a fog toggle.** `_01` variants fog on, base files fog off.
8. **`contents.obv` in every sector.** Four maps in the corpus have it; these are they.
9. **Two attr bytes.** `0x00` and `0x01`, nothing else.
10. **90.5 % blocked, 707 m seal, no safezone, no water flag.**

---

## Road grammar confidence

**2 of 4 road-bearing maps here are confirmed roads (50%.)** The rest are
`terrain_ribbon` or `ambiguous` -- soft-edged regions the corridor detector picks
up as tracks. `roads.json.by_archetype` is now filtered to the confirmed set, but
with n=2 the width, curvature and junction figures are **indicative, not
measured**. Treat them as a starting point and check the result by eye.

The path-texture identification and the `d(road)` setbacks are unaffected: both
come from per-slot and per-CRC statistics, not from corridor detection.

## Border occlusion

**Fog, not terrain.** Ring lift is **+0 cm** -- this archetype does not wall its border, and for the negative cases the map sits ON the high ground with the edges falling away. Occlusion comes from the environment instead. Leave `border_ridge_cm` at 0 and keep the archetype's `Fog.NearDistance`, which is what does the work.

Measured over the outer 64 m against the interior; see `../taste.md` for the corpus-wide table and the two traps when building a rim.

## Sources

`corpus-overview.md` sec 1, sec 4, sec 5.2 ; `catalog/map-taxonomy.json`
`archetypes.elemental`, `maps.*` ; `catalog/stats-terrain.json`
`by_archetype.elemental` ; `catalog/stats-tiles.json` `by_archetype.elemental` ;
`textures.md` sec 6 `elemental` ; `catalog/textures.json`
`texturesets["metin2_map_elemental_01.txt"]` ; `environments.md` sec 4.2, sec 6 `elemental` ;
`catalog/environments.json` `archetype_presets.elemental`, `multi_environment_maps` ;
`placement.md` sec 8 ; `catalog/stats-objects.json` `by_archetype.elemental`, `by_crc` ;
`catalog/affinity.json` `by_archetype.elemental`, `by_crc` ;
`attributes.md` sec 4, sec 8, sec 10 ; `catalog/stats-attr.json` `archetypes.elemental`,
`maps.*`.

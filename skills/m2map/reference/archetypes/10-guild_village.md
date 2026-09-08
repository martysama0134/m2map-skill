# 10 -- `guild_village`

**Guild village and small guild-war grounds.** 7 maps (4 with own terrain), 7 sectors,
541 object placements. Reference map `metin2_guild_village`.

---

## Identity

A small settlement carved into a hillside: 1x1 or 2x2 sectors, a five-or-six-slot
palette from the exclusive `terrainmaps/guild_village/` folder, and the densest prop
scatter in the corpus after the arenas -- **11.79 obj/ha, 77.3 per sector**, of which
67 % is the generic `zone/b/obj` kit.

The defining measurement is the pairing of high object density with steep ground: object
slope p50 **13.2 deg**, p95 **56.7 deg** (`placement.md` sec 8), on terrain whose own slope median
is 22.5 deg. Everywhere else in the corpus, dense prop scatter means flat ground. Here it
does not -- the village is terraced into a slope, and the flat parts are the paved
terraces (`paved` is **11.9 %** of the archetype's painted tiles, the highest outdoor
figure in the corpus).

"Guild" as a *category* does not survive the evidence -- `guild_war2`/`_war4` and
`guild_01/02/03` sit on plain empire and valley palettes and belong to other archetypes
(`corpus-overview.md` sec 4). What survives is this shared `guild_village` art.

---

## Reference maps

| Map | Size | Sectors | Textureset | Environment | Objects | Terrain |
|---|---|---|---|---|---|---|
| **`metin2_guild_village`** (reference) | 2x2 | 4 | `metin2_guild_village.txt` | `guild_village.msenv` | 155 | own |
| `metin2_guild_war3` | 1x1 | 1 | `metin2_guild_war3.txt` | `metin2_guild_war3.msenv` | 175 | own |
| `gm_guild_build` | 1x1 | 1 | `gm_guild_build.txt` | `gm_guild_build.msenv` | 158 | own |
| `metin2_guild_war1` | 1x1 | 1 | `metin2_guild_war1.txt` | `metin2_guild_war1.msenv` | 53 | own |
| `metin2_guild_village_01/02/03` | -- | 0 | -- | -- | 0 | `proxy:metin2_guild_village` |

- **Typical and flagship size 1x1.** The whole archetype is 7 sectors.
- `metin2_guild_village_01/02/03` have **no `setting.txt` at all** -- only a
  `mapproperty.txt` with `ParentMapName metin2_guild_village`. They are guild-land slots
  (`corpus-overview.md` sec 1). Any tool walking the corpus must handle a missing
  `setting.txt`.
- `metin2_guild_war1.txt` and `metin2_guild_war3.txt` are md5-identical; so are
  `metin2_guild_war1.msenv` and `metin2_guild_war3.msenv`.
- `gm_guild_build` is a **build/test map** -- see the warnings below.

---

## Terrain

`style: sculpted`. `stats-terrain.json` `by_archetype.guild_village`, 4 maps, 7 sectors --
the smallest terrain sample after `empire_war`.

| Quantity | Value |
|---|---|
| `height_range_cm` | 11,406.5 - 22,818.0; p5 16,027.5, **p50 17,160**, p95 20,486 |
| Relief per sector | p25 5,953 cm, **p50 7,039 cm**, p75 8,401 cm, p90 9,129 cm |
| `slope_p50` | **22.5 deg** |
| `slope_p95` | **66.3 deg** (p75 46.4 deg, p90 60.7 deg, mean 26.1 deg) |
| `flat_fraction` (< 5 deg) | **0.321** (< 2 deg 0.270, < 10 deg 0.376, < 20 deg 0.475) |
| `roughness` (abs Laplacian r=1) | p50 35.5 cm, p90 237.5, p99 745.5 |
| Local std 3x3 | p50 74.5 cm, p90 281.5 cm |
| Water cells | **7.6 %** |
| Blocked cells | 63.3 % |

The distribution is sharply bimodal: 27 % of cells under 2 deg and 47.5 % under 20 deg, with a
p75 of 46 deg. Flat terraces and steep banks with almost nothing in between. That is exactly
what a village cut into a hillside looks like, and it is why the fitted slope thresholds
in this archetype scatter so widely (5 deg to 42 deg).

Height span is only 11.4 km of raw range -- the narrowest of any sculpted archetype.

---

## Textureset recipe

**`metin2_guild_village.txt`**, 6 declared slots, on `metin2_guild_village`
(`textures.json` `texturesets["metin2_guild_village.txt"]`). `weight` = measured
`ground_share`.

| slot | role | path | U/V | repeat | weight |
|---|---|---|---|---|---|
| 1 | **`empty`** | *(no `Texture001` block -- see warning)* | -- | -- | 0.000 |
| 2 | `base` | `d:/ymir work/terrainmaps/guild_village/guild_village_grass002.dds` | 2/2 | 16.0 m | 0.317 |
| 3 | `mid` | `d:/ymir work/terrainmaps/guild_village/guild_village_field001.dds` | 2/2 | 16.0 m | 0.113 |
| 4 | `base` | `d:/ymir work/terrainmaps/guild_village/guild_village_cliff002.dds` | 1/1 | 32.0 m | 0.407 |
| 5 | `mid` | `d:/ymir work/terrainmaps/guild_village/guild_village_field003.dds` | 2/2 | 16.0 m | 0.025 |
| 6 | `base` | `d:/ymir work/terrainmaps/guild_village/stone_tile_002.dds` | 2/2 | 16.0 m | 0.138 |

**Two shipped defects to avoid.**

1. `metin2_guild_village.txt` **has no `Texture001` block** -- the file starts at
   `Texture002`, so slot 1 is an error-texture hole. The map also paints index 7, one
   past its `TextureCount 6`, on 5 tiles (`textures.md` sec 6 `guild_village`). Write a real
   slot 1.
2. `gm_guild_build` paints indices 2, 4, 6, 7, 3, 9, 10, 13 -- **three of them out of
   range for its 7-slot palette** -- and its `tile.raw` is the **only oversized one in the
   corpus** (`textures.md` sec 7.4). Its palette's seven slots record zero painted tiles as a
   result. It is a build/test map; do not use it as a template.

The archetype's real recipe is three carpets and a stipple: `guild_village_cliff002.dds`
at `UScale 1` (32 m repeat, 40.7 %, clump 7.20, 73 % non-edge -- the terraced bank),
`guild_village_grass002.dds` at 31.7 % (the lawn) and `stone_tile_002.dds` at 13.8 %
with 50 % non-edge -- **a genuinely solid pavement, and the archetype's most distinctive
slot**. `guild_village_field001.dds` is the dither over the grass.

**`metin2_guild_war1.txt` / `_war3.txt`** (5 slots each, md5-identical) shift the weights
-- `cliff002` 44.8 %, `grass002` 26.4 %, `field003` **23.4 %** (a base rather than a
stipple), `stone_tile_002` demoted to a 3.4 % `path` on 1.23 deg ground. Use those for a
small war ground; use `metin2_guild_village.txt` for a village.

**How the archetype paints** (`stats-tiles.json` `by_archetype.guild_village`):
role share rock 43.5 %, grass 31.2 %, dirt 13.3 %, **paved 11.9 %**; base role `rock` x3,
`grass` x1; median 5.5 slots used of 5.5 declared; top-3 share median 0.912;
`mean_run_h_of_base` median 9.6 tiles; `stipple_same_family_share` 0.111.

---

## Environment

**Canonical `guild_village.msenv`** -- cluster C00 `clear_blue_noon` on all four envs.
One of six **cluster-pure** archetypes (`environments.json`
`archetype_presets.guild_village`).

| Parameter | Observed over all 7 maps |
|---|---|
| `Fog.Enable` | 1 x7 |
| `Fog.NearDistance` | 5,000 - 7,000 cm (**median 7,000**) |
| `Fog.FarDistance` | **20,000 cm x7** |
| `Fog.Color` | `#C1CCE2` (guild_village), `#AFBCD6` (the others) |
| `Background.Ambient` | `#32383E`, `#355054`, `#534C3E` (level 0.220 - 0.289) |
| `Character.Ambient` | Background + 0.15 |
| `Background.Diffuse` | `#FFF8F8` x7, warmth 0.0275 |
| sun elevation / azimuth | **27.5 deg** (guild_village) / 48.5 deg / 52.7 deg; az 207.6, 211.9, 243.8 deg |
| `Direction` | `0.411157 0.785894 -0.461867` (guild_village), `0.350156 0.562609 -0.748907`, `0.544326 0.267763 -0.794992` |
| Gradient | Upper 4 / Lower 1 x7 |
| Sky zenith -> horizon -> nadir | `#1849A8` -> `#D9E6FF` -> `#88909F` x7 |
| Cloud | `clouds_zone01.tga`, 200000 / 4 / 0.004 / 30000 |
| Skybox faces | none ; `Filter.Enable` 0 |

All four files are `a1.msenv` with the ambient lifted off zero (`environments.md` sec 6
`guild_village`). `guild_village.msenv` additionally **moves the sun to 27.5 deg elevation**
-- a low afternoon light that rakes across the terraces -- and pushes fog near to 7,000 cm
with a paler `#C1CCE2`.

That low sun is the archetype's environment tell. Everything else here is the empire
default sky.

---

## Object palette

**Density 11.79 obj/ha = 0.1179 per 100 m^2 = 77.3 per sector** -- second densest in the
corpus -- with 151 distinct CRCs across only 45.88 ha. Mix: **Building 73.6 %**,
Tree 25.9 %, Effect 0.6 %.

Family budget:

| Family | n | per ha | NN same-family p25/p50/p75 (cm) | Clark-Evans R |
|---|---|---|---|---|
| `zone/b/obj` | 362 | **7.89** | 131 / **288** / 575 | 0.294 |
| `tree/b1` | 122 | 2.66 | 1,007 / **1,741** / 3,580 | 0.763 |
| `zone/b/building` | 29 | 0.63 | 519 / 1,267 / 2,253 | 0.352 |
| `tree/b3` | 15 | 0.33 | 1,306 / 3,029 / 4,909 | 0.421 |
| `zone/[CP949 "common"]` (CP949 "common") | 4 | 0.09 | 23 / 25 / 274 | -- |

**7.89 `zone/b/obj` records per hectare** is the highest single-family density in the
corpus. This archetype is almost pure generic prop kit -- crates, jars, barrels, fences,
boulders -- at 2.9 m median spacing.

### Tier table (directly usable as `MapSpec.objects`)

`density` per 100 m^2; `spacing_cm` = NN(same CRC) p5; `max_slope` = per-CRC slope p95;
`road_clearance_cm` = per-CRC d(road) p25; `height_bias` = (bias p25, bias p75).
`on_tiles` indexes the 6-slot `metin2_guild_village.txt` palette above.

| tier | crc | name | density | spacing_cm | on_tiles | max_slope | road_clear_cm | height_bias | water_m |
|---|---|---|---|---|---|---|---|---|---|
| signature | 565526255 | `general_obj_jar_red02` (Building, `zone/b/obj`) | 0.00305 | 91 | 2,3,6 | 17 | 0 | (-20, 0) | 42/106/274 **(42, inf)** |
| signature | 2395018297 | `general_obj_jar_blue02` (Building, `zone/b/obj`) | 0.00283 | 72 | 2,3,6 | 9 | 0 | (-5, 0) | 13/76/165 (0, inf) |
| signature | 673027490 | `ob-bigstone04` (Building, `zone/b/obj`) | 0.00371 | 507 | 2,4 | 45 | 812 | (-152, -65) | 58/164/274 **(58, inf)** |
| signature | 4014868700 | `ob-bigstone03` (Building, `zone/b/obj`) | 0.00240 | 455 | 2,4 | 44 | 1295 | (-152, -61) | 86/174/287 **(86, inf)** |
| filler | 2376089798 | `Pagoda2` (Tree, `tree/b1`) | 0.00610 | 2397 | 2,3 | 47 | 600 | (-273, -20) | 18/61/181 (0, inf) |
| filler | 569394331 | `Pagoda1` (Tree, `tree/b1`) | 0.00588 | 1709 | 2,3 | 47 | 565 | (-358, -25) | 14/75/187 (0, inf) |
| filler | 1107711305 | `Pagoda3` (Tree, `tree/b1`) | 0.00436 | 1503 | 2,3 | 47 | 565 | (-152, -20) | 17/68/178 (0, inf) |
| filler | 3689520799 | `Beech4` (Tree, `tree/b1`) | 0.00218 | 2025 | 2,3 | 45 | 282 | (-91, -9) | 27/64/143 (0, inf) |
| filler | 3748653682 | `MontereyCypress3` (Tree, `tree/b1`) | 0.00218 | 2794 | 2,3 | 47 | 200 | (-152, -5) | 4/43/105 (0, inf) |

`water_m` = observed distance to the nearest water, p25/p50/p75 in metres (`affinity.json` `by_crc[crc].d_water_cm`; `~` = the family's figure where the CRC has none). The bold `(min, inf)` is the suggested `MapSpec.water_distance_m` for species that measurably avoid water. A species that tolerates it gets no constraint; give oasis or shore decoration a `(0, max)` band instead -- do NOT try to pin it to the shore texture, which is a stipple and covers only a handful of tiles.


The rest of the 151 CRCs fall below the 420-row per-CRC cutoff in
`stats-objects.json.by_crc`. Fill the `zone/b/obj` budget from the corpus-wide kit
(`ob-b1-001-box01/02/03`, `ob-b1-005-woodbarrel`, `general_obj_fence01/02/03`,
`general_obj_jar_yellow01/02`, `general_obj_stone06..12`) using
`cooccurrence.json.companions_15m` to pick partners -- jars come in pairs
(`general_obj_jar_yellow01` + `_02` obs 29 at x2,272), crates in threes.

Add **one empire house family** for the settlement: `zone/b/building` at 29 records
(0.63/ha), NN p50 1,267 cm.

---

## Placement rules

**Positive rules**

1. **Terrace first, then furnish.** Object slope p50 13.2 deg, p95 56.7 deg -- objects sit on
   the banks as well as the flats. Do not restrict placement to the level ground.
2. **Props at 2.9 m.** `zone/b/obj` NN p50 288 cm at 7.89/ha. This is a cluttered
   courtyard, not a scatter.
3. **Jars on the pavement, at the road edge.** `general_obj_jar_red02` /
   `_blue02` d(road) p25 = 0, p50 = 200-283 cm, slope p95 9-17 deg, NN p5 72-92 cm -- they
   come in tight pairs beside the path.
4. **Boulders on the banks, far out.** `ob-bigstone03/04` slope p50 18-20 deg, sunk 104-110
   cm, d(road) p50 8,600-20,500 cm.
5. **Buildings 1,000 cm from a road, trees 1,600 cm** (`placement.md` sec 8).
6. **Tile ground is 16.5 % of what objects stand on** (`placement.md` sec 8) -- paint real
   pavement and put things on it.
7. Trees at 17 m spacing, roll zero in ~60-70 % of records, sunk 20-45 cm.

**Negative rules**

- `ob-bigstone03/04` never on `(none)`, lava, other or snow; the jars never on lava,
  other or snow; `tree/b1` never on lava or snow (`affinity.json.by_crc`).
- **No safezone.** Zero components across the whole archetype, despite it being a town.
- **No `tree/n1`, `n2` or dedicated guild-castle art.** The
  `property/guild_construction/` folder (25 props) is **spawned at runtime, never
  authored into a map** -- all 25 models are missing from the client pack and only 2 are
  ever placed (`objects.md` sec 3). Do not put guild buildings in `areadata.txt`.
- No DungeonBlock records.

---

## Attr policy

`attr_style: slope_driven` on all four maps with terrain; footprint policy `painted` on
all four.

| Setting | Value |
|---|---|
| `attr_style` | `slope_driven` |
| `block_slope_deg` | **14** (fitted 5, 10, 18, 42 -- see caveat) |
| `border_band_m` | **56 m** median seal -- the shallowest of any sculpted archetype |
| `safezone_regions` | none |

Block budget over 286,276 cells: **slope 88.3 %** -- the highest of any archetype --
object halo 5.2 %, out-of-bounds 4.7 %, water 1.5 %, residual 0.2 %. 62.4 % of cells
blocked.

- **88.3 % of block is explained by terrain slope alone.** Sculpt the terraces correctly
  and the collision follows almost entirely from them.
- **The fitted thresholds scatter wildly** (5 deg on `metin2_guild_village`, 42 deg on
  `gm_guild_build`) because the maps are tiny -- one to four sectors -- and the terrain is
  bimodal. The archetype median of 14 deg is the honest figure; the corpus `slope_driven`
  optimum of 20 deg is also defensible. Prefer 14 deg for a village with usable terraces.
- **28.0 % of block cells lie within 12 m of a placement** -- the highest in the corpus.
  On a 1x1 map with 158 objects, the props *are* the level design.
- **100 % of Tree centre cells are blocked**, and 95.0 % of Building. Stamp everything,
  trees included. This is one of only two archetypes with total tree blocking (the other
  is `darkforest_coast` at 96.8 %).
- Water: 2 of 4 maps have wet cells, both paint the flag, Jaccard 0.517.
- `gm_guild_build` writes paint bytes above `0x07` on **all 65,536 of its cells**.
- **No safezone anywhere.** A guild village is not a peace zone in the shipped data.
- Rim slope median 43 deg versus interior 6 deg; all four sealed strict, with a shallow 56 m
  band.

---

## Tells

1. **11.79 obj/ha on 22 deg ground.** Dense clutter on a slope.
2. **A 32 m cliff carpet.** `guild_village_cliff002.dds` at `UScale 1` covers 40.7 %.
3. **11.9 % paved ground** -- the highest outdoor share -- and `stone_tile_002.dds` is
   genuinely solid at 50 % non-edge.
4. **Jar pairs on the path.** 72-92 cm apart, d(road) 0.
5. **A low sun at 27.5 deg.** `guild_village.msenv` is the only file in the archetype that
   moves the light; everything else is the empire default.
6. **Fog near 7,000, far 20,000.** The tightest fog band in the corpus.
7. **88.3 % of block from slope**, 28 % of it within 12 m of a prop.
8. **Every tree centre cell blocked.**
9. **A missing `Texture001`.** The shipped reference palette has an error-texture hole
   in slot 1.
10. **1x1 sectors and no `setting.txt` on the instanced slots.**

---

## Sources

`corpus-overview.md` sec 1, sec 4 ; `catalog/map-taxonomy.json`
`archetypes.guild_village`, `maps.*` ; `catalog/stats-terrain.json`
`by_archetype.guild_village` ; `catalog/stats-tiles.json`
`by_archetype.guild_village` ; `textures.md` sec 6 `guild_village`, sec 7.4 ;
`catalog/textures.json` `texturesets["metin2_guild_village.txt"]`,
`["metin2_guild_war1.txt"]`, `["gm_guild_build.txt"]` ; `environments.md` sec 6
`guild_village` ; `catalog/environments.json` `archetype_presets.guild_village` ;
`objects.md` sec 3 ; `placement.md` sec 6, sec 8 ; `catalog/stats-objects.json`
`by_archetype.guild_village`, `by_crc` ; `catalog/affinity.json`
`by_archetype.guild_village`, `by_crc` ; `catalog/cooccurrence.json` ;
`attributes.md` sec 4, sec 5, sec 8, sec 10 ; `catalog/stats-attr.json`
`archetypes.guild_village`, `maps.*`.

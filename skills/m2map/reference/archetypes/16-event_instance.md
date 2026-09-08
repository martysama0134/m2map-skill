# 16 -- `event_instance`

**Bespoke event / instance stage.** 10 maps, 129 sectors, 3,895 object placements.
Reference map `metin2_12zi_stage`.

---

## Identity

**Not a visual archetype -- a bag of server-driven stages.** Each member owns a
single-use `zone/<name>` art family, its own textureset and its own `.msenv`, and shares
almost nothing with its neighbours: 8 palettes, **16 environments across 8 clusters**,
453 distinct CRCs, `coverage_entropy_bits` ranging from 0.11 to 3.91.

The one rule that transfers is compositional: **invent one prop family and use it for
60-90 % of the objects** (`placement.md` sec 8). `zone/dungeon/temple_dungeon` is 667 of
`12zi_stage`'s 983; `zone/geuglagsa` is 484 of `snake_temple_01`'s 570;
`zone/treasure_hunt` is 150 of `treasure_hunt`'s 288.

The other transferable fact is the terrain: **42.2 % water cover, the highest in the
corpus** -- driven mostly by `metin2_map_defensewave`, which is a ship deck on a 99 %
submerged map.

If you need a generic "event" look, take the `12zi_stage_*` environment family. Otherwise
treat each member as an individual reference.

---

## Reference maps

| Map | Size | Sectors | Textureset | Environment | Objects | CRCs | `ViewRadius` |
|---|---|---|---|---|---|---|---|
| `metin2_map_battleroyale` | 6x6 | 36 | `metin2_battleroyale.txt` | `metin2_map_battleroyale.msenv` | 1,464 | 167 | 128 |
| **`metin2_12zi_stage`** (reference) | 6x6 | 36 | `metin2_12temple.txt` | `12zi_stage_01_02.msenv` (+8 more) | 983 | 124 | 128 |
| `metin2_map_snake_temple_01` | 3x3 | 9 | `metin2_map_snake_temple.txt` | `metin2_map_snake_temple.msenv` | 570 | 21 | 256 |
| `metin2_map_mists_of_island` | 3x3 | 9 | `metin2_map_mists_of_island.txt` | matching | 294 | 56 | 128 |
| `metin2_map_treasure_hunt` | 3x3 | 9 | `metin2_map_treasure_hunt.txt` | matching | 288 | 59 | **512** |
| `metin2_map_defensewave` | 3x3 | 9 | `metin2_map_defensewave.txt` | `defensewave_blue.msenv` | 131 | 38 | 128 |
| `metin2_map_miniboss_02` | 2x2 | 4 | `metin2_map_miniboss.txt` | `miniboss.msenv` | 62 | 22 | 128 |
| `metin2_map_miniboss_01` | 2x2 | 4 | `metin2_map_miniboss.txt` | `miniboss.msenv` | 58 | 31 | 128 |
| `metin2_guild_pve` | 2x2 | 4 | `metin2_guild_pve.txt` | `metin2_guild_pve.msenv` | 27 | 12 | 256 |
| `metin2_map_defensewave_port` | 3x3 | 9 | `metin2_map_defensewave.txt` | `defensewave_blue.msenv` | 18 | 14 | **384** |

- **Typical size 3x3**, **flagship 6x6**. All ten have their own terrain.
- **`metin2_12zi_stage` declares `Environment1`...`Environment8`** -- eight extra
  environments in one `setting.txt`, the only map in the corpus that does
  (`corpus-overview.md` sec 5.2).
- **`metin2_map_treasure_hunt` writes an extended CRC token**: field 3 is
  `CRC#sx#sy#sz` -- a per-object scale triple appended to the CRC -- in **all 288 of its
  records**, and it is the only map in the corpus that does. The vanilla client survives
  it because field 3 is read with `atoi`; a strict `int(token)` parser throws.
  **Split on `#` and take element 0** (`corpus-overview.md` sec 5.1, `placement.md` sec 10).
- `metin2_map_defensewave_port` (`ViewRadius 384`) is the corpus's only 384.

---

## Terrain

**Split** 6 `slope_driven` / 4 `painted_box`. `stats-terrain.json`
`by_archetype.event_instance`, 10 maps, 129 sectors.

| Quantity | Value |
|---|---|
| `height_range_cm` | **0.0** - 32,518.5; p5 11,466, **p50 16,903.5**, p95 23,794.5 |
| Relief per sector | p25 6,074 cm, **p50 8,642 cm**, p75 10,936 cm, p90 15,391 cm |
| `slope_p50` | **18.1 deg** |
| `slope_p95` | **73.1 deg** (p75 45.2 deg, p90 64.7 deg, mean 26.2 deg) |
| `flat_fraction` (< 5 deg) | **0.256** (< 2 deg 0.187, < 10 deg 0.364, < 20 deg 0.524) |
| `roughness` (abs Laplacian r=1) | p50 23.5 cm, p90 264.5, p99 1,458.5 |
| Water cells | **42.2 %** -- the highest of any archetype |
| Blocked cells | 75.8 % |

The 42.2 % water figure is dominated by `metin2_map_defensewave`, whose map is **99 %
submerged with a mean terrain slope of 0.2 deg** -- `a/beach/beach water.dds` scores as its
`base` texture (`textures.md` sec 6 `event_instance`). Exclude it and the archetype's water
cover is ordinary.

Because this archetype has no shared identity, **do not average its terrain**. Copy the
member you are cloning.

---

## Textureset recipe

**`metin2_map_defensewave.txt`**, 8 slots, on `defensewave` + `defensewave_port` --
nominated as reference by `textures.json`, though the archetype has no representative
palette. `weight` = measured `ground_share`; sums to 1.000.

| slot | role | path | U/V | repeat | weight |
|---|---|---|---|---|---|
| 1 | `void` | `d:/ymir work/terrainmaps/dungeon/field 01.dds` | 5/5 | 6.4 m | 0.006 |
| 2 | `base` | `d:/ymir work/terrainmaps/a/beach/beach water.dds` | 4/4 | 8.0 m | 0.590 |
| 3 | `path` | `d:/ymir work/terrainmaps/bayblacksand/bayblacksand_blacksand.dds` | 4/4 | 8.0 m | 0.002 |
| 4 | `base` | `d:/ymir work/terrainmaps/12temple/stone_02.dds` | 4/4 | 8.0 m | 0.222 |
| 5 | `cliff` | `d:/ymir work/terrainmaps/snakevalley/cliff01.dds` | 2/2 | 16.0 m | 0.106 |
| 6 | `accent` | `d:/ymir work/terrainmaps/snakevalley/field03.dds` | 4/4 | 8.0 m | 0.002 |
| 7 | `mid` | `d:/ymir work/terrainmaps/snakevalley/field02.dds` | 4/4 | 8.0 m | 0.064 |
| 8 | `path` | `d:/ymir work/terrainmaps/snakevalley/grass01.dds` | 4/4 | 8.0 m | 0.010 |

The other seven palettes span 4 to **37** slots across **29 art families**:

- **`metin2_battleroyale.txt` (37 slots, 11 families) is the largest palette in the
  corpus** and reads like an artist's scratch pad -- desert, snow, volcanic and elemental
  packs stacked in one list, with slots 16, 23, 28, 34 and 35 never painted. Its slots
  33-35 are also among the only four palettes reaching outside `terrainmaps/`.
- `metin2_12temple.txt` (23 slots, `metin2_12zi_stage`);
- `metin2_map_treasure_hunt.txt` (17 slots -- paints 10);
- `metin2_map_snake_temple.txt` (14 slots);
- `metin2_map_mists_of_island.txt` (10 slots);
- `metin2_map_miniboss.txt` (4 slots);
- `metin2_guild_pve.txt` (4 slots).

**Archetype-wide most-painted textures**: `a/beach/beach water.dds` 11.5 %,
`b/stone/stone01_01.dds` 6.9 %, `n/desert/sand/sand01.dds` 6.8 %,
`12temple/stone_02.dds` 5.9 %, `b/stone/stone01.dds` 5.8 %,
`b/grass/grass 02_01.dds` 4.8 %, `geuglagsa/capedragon_cliff002.dds` 3.7 %,
`dawnmistwood/dawnmistwood_grass001.dds` 3.5 %.

**How the archetype paints** (`stats-tiles.json` `by_archetype.event_instance`):
role share rock 33.3 %, grass 21.6 %, sand 18.8 %, dirt 10.7 %, snow 5.1 %, lava 4.6 %,
other 4.1 %, paved 1.3 %, void 0.4 % -- **nine roles, more than any other archetype**;
base role `rock` x7, `sand` x3; median 7.5 slots used of 9 declared;
`mean_run_h_of_base` median 9.0 tiles (range 3.8 to 638);
`coverage_entropy_bits` median 1.91 with a range of 0.11-3.91.

---

## Environment

**16 envs across 8 clusters.** They split into the **9-file `12zi_stage_*` family** and a
set of one-offs (`environments.json` `archetype_presets.event_instance`).

**Canonical `12zi_stage_02_02.msenv`** -- cluster C04 `12zi_stylized_stage`.

The 12zi family has a uniform structure and wildly different chroma per stage:

| Parameter | 12zi family (C04, 7 files) |
|---|---|
| Gradient | Upper 2 / Lower 1 |
| Skybox faces | `capedragonhead` declared at **`bTextureRenderMode 0`** -- never shown, gradient wins |
| `CloudHeight` | **100** |
| `CloudTextureFileName` | **`clouds_zone08.tga`** |
| `CloudSpeed` | **0.08** -- the fastest in the corpus, 20x the a1 default |
| `Background.Ambient` | mean level **0.567** -- the highest in the corpus |
| `Fog.NearDistance` | 100 - 700 cm |
| `Fog.Color` | ~`#614045` cluster mean, per-stage chroma |

Across all 16 envs: `Fog.Enable` 1 x16 / 0 x2; near 0-10,000 cm (median 325);
far 20,000-50,000 cm (median 27,500); 16 distinct fog colours; ambient level 0.0-0.637;
sun elevation 17.2-68.6 deg across **eight azimuths**; gradient Upper 2 x9, 3 x5, 4 x2,
1 x1, 5 x1; face sets `bayblacksand`, `capedragonhead`, `dawnmistwood`.

Nine of the sixteen are off-cluster. **There is no archetype preset -- pick a member.**

---

## Object palette

**Density 4.61 obj/ha = 0.0461 per 100 m^2 = 30.2 per sector**, **453 distinct CRCs**
across 845.41 ha. Mix: **Building 64.5 %**, Tree 33.9 %, Effect 1.5 %,
DungeonBlock 0.1 %.

Family budget -- each belongs to essentially one map:

| Family | n | per ha | NN same-family p25/p50/p75 (cm) | Clark-Evans R | home |
|---|---|---|---|---|---|
| `zone/dungeon/temple_dungeon` | 667 | 0.79 | **16 / 29 / 501** | 0.051 | `12zi_stage` |
| `tree/n2` | 616 | 0.73 | 226 / 424 / 907 | 0.155 | several |
| `zone/geuglagsa` | 484 | 0.57 | **700 / 900 / 1,000** | 0.149 | `snake_temple_01` |
| `tree/b1` | 371 | 0.44 | 726 / 1,831 / 4,323 | 0.355 | several |
| `zone/n/obj/map_n_desert_01` | 340 | 0.40 | 141 / 237 / 359 | 0.034 | `treasure_hunt` |
| `zone/b/obj` | 308 | 0.36 | 112 / 254 / 1,962 | 0.154 | everywhere |
| `tree/b2` | 169 | 0.20 | 1,981 / 2,898 / 3,968 | 0.285 | |
| `zone/treasure_hunt` | 150 | 0.18 | 144 / 247 / 327 | 0.034 | `treasure_hunt` |
| `zone/dungeon/dawnmistwood_dungeon` | 126 | 0.15 | 290 / 679 / 1,305 | 0.092 | |
| `zone/defensewave` | 104 | 0.12 | 159 / 318 / 653 | 0.029 | `defensewave` |
| `zone/mists_of_island` | 89 | 0.11 | 514 / 1,007 / 2,680 | 0.121 | `mists_of_island` |

**`zone/dungeon/temple_dungeon` at NN p25 = 16 cm and p50 = 29 cm** is the tightest
placement in the corpus by an order of magnitude -- a nested statue/wall kit whose parts
overlap.

### Tier table (directly usable as `MapSpec.objects`)

`density` per 100 m^2; `spacing_cm` = NN(same CRC) p5; `max_slope` = per-CRC slope p95;
`road_clearance_cm` = per-CRC d(road) p25; `height_bias` = (bias p25, bias p75).
Slot indices depend on which member's palette you take; they are named instead.

| tier | crc | name | home stage | density | spacing_cm | max_slope | road_clear_cm | height_bias |
|---|---|---|---|---|---|---|---|---|
| signature | 3812975508 | `gls_A_wall-lin2` (Building, `zone/geuglagsa`) | snake temple | 0.00345 | **1000** | 32 | 782 | (0, 0) |
| signature | 1806594480 | `gls_A_wall-corner` (Building, `zone/geuglagsa`) | snake temple | 0.00105 | 800 | 44 | 1012 | (0, 0) |
| signature | 3499218645 | `12t_statue_base` (Building, `zone/dungeon/temple_dungeon`) | 12zi | 0.00128 | 1680 | 8 | 0 | (0, 0) |
| filler | 802175187 | `AloeVera_RT_Flowers_02` (Tree, `tree/n2`) | desert stages | 0.00105 | 255 | 37 | 400 | (-25, -5) |
| filler | 3449844455 | `IvySpy_Winter1` (Tree, `tree/b2`) | volcanic stages | 0.00104 | 1467 | 45 | 0 | (-120, 0) |
| filler | 1453870486 | `CinnamonFern_RT_02` (Tree, `tree/n2`) | desert stages | 0.00083 | 83 | 30 | 1009 | (-15, 0) |

`zone/geuglagsa` is the corpus's clearest wall-kit signature: **98.4 % of its rolls are
multiples of 90 deg**, NN histogram is a spike at 700-1,500 cm with **nothing below 500 cm**,
and yaw is exactly 0 in 100 % of records (`placement.md` sec 3.3).

---

## Placement rules

**Positive rules**

1. **One art family, 60-90 % of the objects.** That is the archetype's only universal
   rule.
2. **Wall kits at 700-1,000 cm on a 90 deg snap.** `gls_A_wall-lin2` at NN p5 = p25 = p50 =
   1,000 cm.
3. **Statue kits nest.** `zone/dungeon/temple_dungeon` at 16-29 cm -- parts of one
   assembly, placed as separate records.
4. **Trees exist but stand far back.** 34 % of placements, at d(road) p50 **6,625 cm**
   (`placement.md` sec 5). Buildings sit at 1,094 cm.
5. **Effects are rare** -- 58 records, 1.5 %.
6. Road grammar (pooled, see caveat): the archetype-level figures pool ten unrelated maps
   and should not be used. Take the member's own row from `roads.json.maps`.

**Negative rules**

- **`zone/geuglagsa` is never on lava, other, sand, snow or tile** -- 82-84 % of its
  records are on grass.
- `12t_statue_base` never on `(none)`, other, sand or snow.
- **Do not mix two stages' art families.** They do not co-occur in the shipped data.
- **Watch the `#` token on `treasure_hunt`.** If you clone it, either strip the scale
  triple or reproduce it deliberately.

---

## Attr policy

**Split 6 `slope_driven` / 4 `painted_box`, and five maps fit a 1 deg threshold** -- the
signature of wholesale paint. Footprint policy `painted` x5, `model_only` x4, `mixed` x1.

| Setting | Value |
|---|---|
| `attr_style` | take it from the member; `painted_box` for a small stage, `slope_driven` for a 6x6 |
| `block_slope_deg` | **26** for the sculpted members (`battleroyale` 27, `snake_temple_01` 16, `treasure_hunt` 15) |
| `border_band_m` | **512 m** archetype median -- a runaway band, i.e. wholesale paint |
| `safezone_regions` | one irregular component in one map, 1,551 m^2 |

Block budget over 6,374,715 cells: **slope 71.0 %**, water 18.8 %, out-of-bounds 8.8 %,
object halo 1.2 %, residual 0.3 %. 75.4 % of cells blocked.

- **Water is 18.8 % of block** -- second only to `eastplain`. On
  `metin2_map_defensewave` it is **99.2 %**: the map is a flooded plane and everything
  except the ship deck is water-blocked.
- 9 of 10 maps have wet cells (3,570,200); **3 paint the flag**; Jaccard 0.349.
- **No paint bytes above `0x07` anywhere** and only 6 distinct attr bytes -- clean data.
- 87.2 % of Building, 91.4 % of Effect and 45.4 % of Tree centre cells blocked.
- Rim slope median 28 deg versus interior 14 deg (`attributes.md` sec 8); all ten sealed strict.
- Safezone is essentially absent (0.018 % of cells).

---

## Tells

1. **One invented prop family per stage**, carrying most of the objects.
2. **A wall kit at 700-1,000 cm with 98 % of rolls on 90 deg.**
3. **A nested statue kit at 16-29 cm spacing.**
4. **The 12zi sky**: `CloudHeight 100`, `clouds_zone08.tga` at `CloudSpeed 0.08`,
   ambient 0.567, gradient Upper 2, declared cube faces that never render.
5. **42 % water cover** -- and one member that is 99 % submerged.
6. **The largest palette in the corpus** (`metin2_battleroyale.txt`, 37 slots,
   11 families, 5 never painted).
7. **Eight `Environment1..8` declarations** on `metin2_12zi_stage`.
8. **`CRC#sx#sy#sz`** in every `areadata.txt` record of `metin2_map_treasure_hunt`.
9. **Nine ground roles.** More than any other archetype.
10. **Clean attr: six bytes, no paint convention, no safezone.**

---

## Sources

`corpus-overview.md` sec 4, sec 5.1, sec 5.2 ; `catalog/map-taxonomy.json`
`archetypes.event_instance`, `maps.*` ; `catalog/stats-terrain.json`
`by_archetype.event_instance` ; `catalog/stats-tiles.json`
`by_archetype.event_instance` ; `textures.md` sec 6 `event_instance` ;
`catalog/textures.json` `texturesets["metin2_map_defensewave.txt"]`,
`["metin2_battleroyale.txt"]` ; `environments.md` sec 5 C04, sec 6 `event_instance` ;
`catalog/environments.json` `archetype_presets.event_instance`,
`multi_environment_maps` ; `placement.md` sec 3.3, sec 5, sec 8, sec 10 ;
`catalog/stats-objects.json` `by_archetype.event_instance`, `by_crc` ;
`catalog/affinity.json` `by_archetype.event_instance`, `by_crc` ;
`attributes.md` sec 4, sec 8, sec 10 ; `catalog/stats-attr.json`
`archetypes.event_instance`, `maps.*` ; `catalog/roads.json` -- the archetype row pools
ten unrelated maps and is unusable; see `roads.json.by_archetype_caveat`.

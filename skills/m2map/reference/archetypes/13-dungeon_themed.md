# 13 -- `dungeon_themed`

**Themed dungeon / ruin (biome-skinned interior).** 21 maps (12 with own terrain),
158 sectors, 4,334 object placements. Reference map `metin2_map_dawnmist_dungeon_01`.

---

## Identity

Same construction as `dungeon_block` -- a blocked slab with rooms carved out of it -- but
**skinned as a biome**. It fails the block-dungeon rule on both counts: 4-17 real texture
slots instead of <=5, and a coloured environment instead of black fog
(`map-taxonomy.json` `archetypes.dungeon_themed.evidence`).

The mix is what separates them: **65 % Building / 21 % DungeonBlock / 7 % Tree / 7 %
Effect** against `dungeon_block`'s 72 % Effect / 23 % DungeonBlock / 0 Tree. Trees exist
here, and they are `tree/b2` -- IvySpy dead vines, 209 of 313 records.

Each member owns one dedicated art family, and they are wildly different from each other:
`zone/secretdungeon` flowers on a water plane, `zone/otherworld` skeletons on lava,
`zone/dungeon/dawnmistwood_dungeon` on the steepest interior in the corpus,
`zone/whitedragoncave/*` on pure black, `zone/dungeon/flame_dungeon` on rock. **This is
the most heterogeneous archetype in the corpus** -- 11 palettes, 11 environments across
8 clusters, 484 distinct CRCs.

The rule that does hold is structural: **14 of 21 maps use `GradientLevelUpper 1`, and in
10 of those the zenith, horizon and nadir are literally the same colour** -- a flat
single-tone dome tinted to the biome. **Fog colour, not the sky, carries the theme**
(`environments.md` sec 6 `dungeon_themed`).

---

## Reference maps

| Map | Size | Sectors | Textureset | Environment | Objects | CRCs |
|---|---|---|---|---|---|---|
| **`metin2_map_dawnmist_dungeon_01`** (reference) | 3x4 | 12 | `metin2_DawnMistWood_dungeon.txt` | `DawnMistWood_dungeon.msenv` | 786 | 142 |
| `metin2_map_devilscatacomb` | 7x7 | **54** | `metin2_map_devilsCatacomb.txt` | `map_devilsCatacomb.msenv` | 977 | 180 |
| `metin2_map_secretdungeon_01` | 2x2 | 4 | `metin2_map_secretdungeon.txt` | `metin2_map_secretdungeon.msenv` | 582 | 53 |
| `metin2_map_otherworld_01` | 2x2 | 4 | `metin2_map_otherworld_01.txt` | `metin2_map_otherworld_01.msenv` | 531 | 24 |
| `metin2_map_otherworld_02` | 3x3 | 9 | `metin2_map_otherworld_02.txt` | `metin2_map_otherworld_02.msenv` | 415 | 46 |
| `metin2_map_whitedragoncave_01` | 6x6 | 36 | `metin2_map_whitedragoncave_01.txt` | `..._01.msenv` | 302 | 16 |
| `metin2_map_n_flame_dungeon_01` | 3x3 | 9 | `metin2_map_n_flame_dungeon_01.txt` | matching | 254 | 38 |
| `metin2_map_smhgate_devils` | 2x2 | 4 | `metin2_map_devilsCatacomb.txt` | `map_devilsCatacomb.msenv` | 182 | 39 |
| `metin2_map_n_snow_dungeon_01` | 4x3 | 12 | `metin2_map_n_snow_dungeon_01.txt` | matching | 145 | 24 |
| `metin2_map_whitedragoncave_02` | 3x3 | 9 | `metin2_map_whitedragoncave_02.txt` | matching | 96 | 11 |
| `metin2_map_n_flame_dragon` | 1x1 | 1 | `metin2_map_n_flame_dragon_01.txt` | matching | 59 | 23 |
| `metin2_map_whitedragoncave_boss` | 2x2 | 4 | `metin2_map_whitedragoncave_03.txt` | matching | 5 | 4 |
| 6x `boss_awaken_*` / `boss_crack_*`, `smhgate_dawnmist`, `otherworld_03/04` | -- | 0 | inherited | inherited | 0 | -- |

- **Typical size 2x2**, **flagship 3x4**; range 1x1 to 7x7.
- **`metin2_map_devilscatacomb` declares `MapSize 7 7` but ships 54 sector directories
  including a whole `x=7` column.** The extra folders are dead data a loader never reads
  but a folder-walking tool will (`corpus-overview.md` sec 5.5).
- `metin2_map_otherworld_02` is the one map in the corpus where **object evidence
  deliberately overrides terrain evidence**: it sits on the `field_empire` B-palette but
  84 % of its objects are `zone/secretdungeon` (209) and `zone/otherworld` (114), so it
  is classified here.
- `metin2_map_devilscatacomb` ships a loose `map_dd_teste.msenv` in its root that it
  **never loads** -- its `setting.txt` names `map_devilsCatacomb.msenv`. `map_dd_teste`
  is also the corpus's only gradient-free file: `GradientLevelUpper 0`,
  `GradientLevelLower 0`, and `SkyBox.cpp:419` returns early, so it renders **no sky at
  all** (`environments.md` sec 4.7).

---

## Terrain

**`style: box`** for most members, but not uniformly -- this archetype straddles the
line. `stats-terrain.json` `by_archetype.dungeon_themed`, 12 maps, 158 sectors.

| Quantity | Value |
|---|---|
| `height_range_cm` | 8,721.0 - **32,767.5**; p5 15,635.5, **p50 16,383.5**, p95 24,501.5 |
| Relief per sector | **p25 0.0 cm**, p50 4,128 cm, p75 8,888 cm, p90 14,281 cm |
| `slope_p50` | **0.025 deg** |
| `slope_p95` | **64.2 deg** (p75 17.8 deg, p90 53.5 deg) |
| `flat_fraction` (< 5 deg) | **0.689** (< 2 deg 0.668, < 20 deg 0.759) |
| `roughness` (abs Laplacian r=1) | **p50 0.5 cm**, p90 153.5, p99 1,361.5 |
| Water cells | **7.7 %** |
| Blocked cells | **88.7 %** -- the highest of any archetype |

Read the relief quartiles: **p25 = 0.0 cm, p90 = 14,281 cm**. A quarter of the sectors
are perfectly flat plates and a tenth have 143 m of relief. Some members
(`whitedragoncave_01`, `whitedragoncave_02`) are literal boxes; others
(`dawnmist_dungeon_01`, `n_flame_dragon`) are sculpted caverns. The archetype median of
0.025 deg slope is the flat half winning the count.

Choose per map. `p50 16,383.5 cm` is again the editor's default plane (raw 32768), so
build the floor there and cut the caverns out of it.

---

## Textureset recipe

**`metin2_DawnMistWood_dungeon.txt`**, 9 slots, on `dawnmist_dungeon_01` and its three
proxies (`textures.json` `texturesets["metin2_dawnmistwood_dungeon.txt"]`).
`weight` = measured `ground_share`; sums to 1.000.

| slot | role | path | U/V | repeat | weight |
|---|---|---|---|---|---|
| 1 | `base` | `d:/ymir work/terrainmaps/dungeon/dawnmistwood_dungeon/dmw_dungeon_grass00.dds` | 2/2 | 16.0 m | 0.796 |
| 2 | `mid` | `d:/ymir work/terrainmaps/dungeon/dawnmistwood_dungeon/dmw_dungeon_field_00.dds` | 2/2 | 16.0 m | 0.056 |
| 3 | `path` | `d:/ymir work/terrainmaps/dungeon/dawnmistwood_dungeon/dmw_dungeon_field_01.dds` | 2/2 | 16.0 m | 0.038 |
| 4 | `shore` | `d:/ymir work/terrainmaps/dungeon/dawnmistwood_dungeon/dmw_dungeon_field_02.dds` | 2/2 | 16.0 m | 0.045 |
| 5 | `cliff` | `d:/ymir work/terrainmaps/dungeon/dawnmistwood_dungeon/dmw_dungeon_grass00.dds` | 2/2 | 16.0 m | 0.002 |
| 6 | `mid` | `d:/ymir work/terrainmaps/dungeon/dawnmistwood_dungeon/dmw_dungeon_grass02.dds` | 2/2 | 16.0 m | 0.028 |
| 7 | `accent` | `d:/ymir work/terrainmaps/dawnmistwood/dawnmistwood_sand001.dds` | 2/2 | 16.0 m | 0.012 |
| 8 | `path` | `d:/ymir work/terrainmaps/dungeon/dawnmistwood_dungeon/dmw_dungeon_tile000.dds` | 2/2 | 16.0 m | 0.022 |
| 9 | `void` | `d:/ymir work/terrainmaps/dungeon/field 01.dds` | 1/1 | 32.0 m | 0.003 |

Note **slot 5 repeats slot 1's texture at a different role** -- the same file scored
`base` at 79.6 % and `cliff` at 0.17 %, because the role is per `(textureset, slot)` and
the artist used the same art twice.

Set `RoadSpec.tile_index = 3` or `8` -- `dmw_dungeon_field_01` (3.8 %, `path`) and
`dmw_dungeon_tile000` (2.1 %, clump 6.98, 67 % non-edge, 4.8 deg slope) are the corridor
surfaces.

**`void` is a mask, not a floor.** `black.dds` is still **26.9 %** of the archetype's
painted ground, almost all of it from the whitedragoncave trio, where slot 4 `black.dds`
covers 32-100 %. Those three palettes are a progression:

- `metin2_map_whitedragoncave_01.txt` (4 slots) -- **99.99 % black**;
- `metin2_map_whitedragoncave_02.txt` (4 slots) -- 62 % dungeon-black + 32 % black + a
  little ice;
- `metin2_map_whitedragoncave_03.txt` (4 slots) -- inverts to 80 % black / 18 %
  dungeon-black.

**How the archetype paints** (`stats-tiles.json` `by_archetype.dungeon_themed`):
role share rock 27.4 %, **void 26.9 %**, grass 26.0 %, dirt 7.9 %, paved 7.9 %,
lava 3.2 %, snow 0.4 %; base role histogram `rock` x5, `grass` x2, `void` x2, `paved`,
`lava`, `dirt` x1 each -- **six different base roles across twelve maps**; median 6 slots
used of 6.5 declared; base share median 0.750; `mean_run_h_of_base` median 34.5 tiles
(min 5.2, max 1,498); `dither_only_tile_share` median 0.00002.

Like the block dungeons, this archetype paints in regions. Unlike them, it paints
several.

**Archetype-wide most-painted textures:** `black.dds` 26.9 % (`void`),
`dungeon/devilcave/dc_grass_00.dds` 18.1 % (`base`),
`dungeon/devilcave/dc_rock_00.dds` 14.6 % (`base`),
`dmw_dungeon_grass00.dds` 6.1 %, `b/stone/stone01.dds` 6.0 %,
`zone/dungeon/snow_dungeon/tile_rock00.dds` 5.4 %,
`n/flame area/valcano_rock.dds` 5.0 %, `dungeon/field 01.dds` 4.8 % (`void`).

---

## Environment

**Canonical `dawnmistwood_dungeon.msenv`** -- cluster C01 `murky_lowlight`.
**11 envs across 8 clusters**, 10 of them off-cluster. There is no single preset.

| Env | Maps | Cluster |
|---|---|---|
| `dawnmistwood_dungeon.msenv` | 4 | C01 `murky_lowlight` |
| `metin2_map_n_flame_dungeon_01.msenv` | 3 | C03 `warm_dusk` |
| `metin2_map_n_snow_dungeon_01.msenv` | 3 | C16 singleton |
| `metin2_map_otherworld_01.msenv` | 3 | C17 singleton |
| `map_devilscatacomb.msenv` | 2 | C07 `unfogged_cave` |
| `metin2_map_whitedragoncave_01/_02.msenv` | 1 each | C09 `void_pastel_fog` |
| `metin2_map_n_flame_dragon_01.msenv` | 1 | C03 `warm_dusk` |
| `metin2_map_otherworld_02.msenv` | 1 | C00 `clear_blue_noon` |
| `metin2_map_secretdungeon.msenv` | 1 | C00 `clear_blue_noon` |
| `metin2_map_whitedragoncave_boss.msenv` | 1 | C18 singleton |

| Parameter | Observed over all 21 maps |
|---|---|
| `Fog.Enable` | 1 x18, 0 x3 |
| `Fog.NearDistance` | 0 - 5,000 cm (median 1,000) |
| `Fog.FarDistance` | 20,000 - **1,000,000 cm** (median 25,000) |
| `Fog.Color` | 11 distinct: `#2A2A3B` dawnmist, `#814823` flame, `#8391E4`/`#8A94D0`/`#8DACE5` snow and cave, `#1AC6F0`, ... |
| `Background.Ambient` | 9 distinct, level 0.0 - 0.633 (median 0.244) |
| `Character.Ambient` | Background + 0.15 |
| light warmth | -0.357 - 0.318 (median 0.145) |
| sun elevation / azimuth | 17.2 - 48.7 deg / six distinct azimuths incl. **333.8 deg** |
| **Gradient** | **Upper 1 x14**, 2 x5, 4 x1, 5 x1 / Lower 1 x19, 2 x2 |
| Sky | flat single-tone in 10 of 21 -- dawnmist `#2A2A3B`, flame `#814823`, snow `#495983`, whitedragoncave `#000000` |
| Cloud | `clouds_zone01/06/08`, scale 5000 / 200000 / 280000, height **100** or 30000 |
| Skybox faces | `capedragonhead` (one map) |

**`metin2_map_whitedragoncave_02.msenv` sets `FarDistance 1000000`** -- one million
centimetres. Since `Fog.FarDistance` is also the terrain texture-draw budget
(`environments.md` sec 4.3), that effectively disables the untextured third band entirely.
It is legal and shipped; it is also the single most expensive draw setting in the corpus.

**The recipe: pick a fog colour for the biome, collapse the gradient to one flat band of
that colour, and let the fog do all the work.**

---

## Object palette

**Density 4.19 obj/ha = 0.0419 per 100 m^2 = 27.4 per sector**, **484 distinct CRCs**
across 1,035.47 ha. Mix: **Building 65.3 %, DungeonBlock 20.7 %, Tree 7.2 %,
Effect 6.7 %.**

Family budget -- note that each family belongs to essentially one map:

| Family | n | per ha | NN same-family p25/p50/p75 (cm) | Clark-Evans R | home map |
|---|---|---|---|---|---|
| `zone/secretdungeon` | 751 | 0.73 | 185 / **283** / 400 | 0.074 | `secretdungeon_01` |
| `zone/otherworld` | 619 | 0.60 | 191 / **252** / 344 | 0.052 | `otherworld_01/02` |
| `zone/dungeon/dawnmistwood_dungeon` | 618 | 0.60 | 231 / **589** / 1,004 | 0.119 | `dawnmist_dungeon_01` |
| `zone/b/obj` | 603 | 0.58 | 308 / 595 / 1,766 | 0.188 | everywhere |
| `zone/whitedragoncave/whitedragoncave_01` | 301 | 0.29 | 0 / **1,900** / 4,243 | 0.318 | `whitedragoncave_01` |
| `effect/background` | 288 | 0.28 | 164 / 1,177 / 4,989 | 0.354 | -- |
| `zone/dungeon/flame_dungeon` | 236 | 0.23 | 525 / 759 / 1,057 | 0.112 | `n_flame_dungeon_01` |
| `tree/b2` | 209 | 0.20 | 1,189 / 2,593 / 3,897 | 0.271 | -- |
| `zone/c/building` | 200 | 0.19 | 600 / **900** / 1,000 | 0.082 | -- |
| `tree/b1` | 84 | 0.08 | 1,335 / 1,666 / 2,264 | 0.113 | -- |
| `zone/dungeon/snow_dungeon` | 73 | 0.07 | 1,528 / 2,811 / 4,581 | 0.196 | `n_snow_dungeon_01` |
| `zone/devilcave` | 61 | 0.06 | 868 / 1,936 / 4,900 | 0.216 | `devilscatacomb` |

### Tier table (directly usable as `MapSpec.objects`)

`density` per 100 m^2; `spacing_cm` = NN(same CRC) p5; `max_slope` = per-CRC slope p95;
`height_bias` = (bias p25, bias p75). `on_tiles` indexes the 9-slot
`metin2_DawnMistWood_dungeon.txt` palette above where the object belongs to that map;
otherwise the slot is named in the note.

**Pick one theme block.** These families do not co-occur.

| tier | crc | name | theme | density | spacing_cm | max_slope | height_bias | water_m |
|---|---|---|---|---|---|---|---|---|
| signature | 2352670231 | `otherworld_skelleton_00` (DungeonBlock, `zone/otherworld`) | lava | 0.00204 | 113 | 30 | (0, 0) | ~0/0/0 (0, inf) |
| signature | 2391912034 | `otherworld_skelleton_01` (DungeonBlock, same) | lava | 0.00135 | 172 | 33 | (0, 0) | ~0/0/0 (0, inf) |
| signature | 3625228596 | `otherworld_skelleton_02` (DungeonBlock, same) | lava | 0.00055 | 285 | 36 | (-12, 0) | ~0/0/0 (0, inf) |
| signature | 2324583116 | `flower_01` (Building, `zone/secretdungeon`) | water garden | 0.00118 | 141 | 34 | (-24, -7) | 0/0/0 (0, inf) |
| signature | 752518565 | `flower_02` (Building, same) | water garden | 0.00061 | 218 | 32 | (-32, -3) | 0/0/0 (0, inf) |
| signature | 883725486 | `flower_05` (Building, same) | water garden | 0.00048 | 223 | 32 | (-7, -7) | ~0/0/0 (0, inf) |
| signature | 4090524507 | `WDC_01_door_02` (DungeonBlock, `zone/whitedragoncave/whitedragoncave_01`) | black cave | 0.00077 | **3000** | 0 | (0, 0) | n/a |
| signature | 1727101311 | `WDC_01_Line_02` (DungeonBlock, same) | black cave | 0.00049 | **6000** | 0 | (0, 0) | n/a |
| filler | 646376885 | `c1-038-wall-lin2` (Building, `zone/c/building`) | any | 0.00066 | **900** | 20 | (0, +5) | 9/13/51 (0, inf) |

`water_m` = observed distance to the nearest water, p25/p50/p75 in metres (`affinity.json` `by_crc[crc].d_water_cm`; `~` = the family's figure where the CRC has none). The bold `(min, inf)` is the suggested `MapSpec.water_distance_m` for species that measurably avoid water. A species that tolerates it gets no constraint; give oasis or shore decoration a `(0, max)` band instead -- do NOT try to pin it to the shore texture, which is a stipple and covers only a handful of tiles.


`c1-038-wall-lin2` is the same 10 m wall module as `arena_pvp`'s
`a1-038-wall-lin2_duel`, in the Empire-C skin: NN p5 900, p25 = p50 = 1,000 cm, yaw 0 in
100 % of records.

Fill the remaining budget from `zone/b/obj` (603 records, 0.58/ha) and `tree/b2`
(IvySpy dead vines, 209 records, 26 m spacing).

---

## Placement rules

**Ground affinity** (`affinity.json` `by_archetype.dungeon_themed`, n = 4,334):
grass 29.6 %, rock 27.6 %, field 12.5 %, **lava 11.9 %**, other 7.6 %, tile 6.7 %,
`(none)` 2.5 %, snow 1.6 %. Object slope p50 6.07 deg, p75 27.76 deg, **p95 56.34 deg** -- the
second-steepest object placement in the corpus, and a genuinely bimodal one (1,787 of
4,225 placements below 2 deg, 962 above 30 deg).

**Positive rules**

1. **One art family per map, carrying 60-90 % of the objects.** That is the archetype's
   organising principle.
2. **Skeletons on lava.** `otherworld_skelleton_00/01/02` at 84-91 % on
   `dungeon/devilcave/dc_lava_red_00.dds`, packed at 250-310 cm, bias 0, with
   **pitch non-zero in 9-35 % of records** -- they lie tumbled.
3. **Flowers on the water plane.** `zone/secretdungeon` d(water) p25 = p50 = p75 = **0**
   and `flower_01` stands on a wet cell in **61.5 %** of records
   (`placement.md` sec 8). NN p50 283 cm, sunk 7-24 cm, on grass 81-96 %.
4. **The whitedragoncave kit is a corridor on a 3,000-6,000 cm module**, on `black.dds`
   in 94-96 % of records, slope 0.0 deg, bias 0.
5. **Wall kits at 900-1,000 cm** with yaw 0.
6. **Trees are `tree/b2`** -- IvySpy dead vines, 209 of 313 tree records.
7. `zone/dungeon/dawnmistwood_dungeon` sits at slope p50 **18.7 deg** -- the steepest
   interior placement in the corpus (`placement.md` sec 8).

**Negative rules**

- **`otherworld_skelleton_*` never on grass, other, sand, snow or tile.** Lava, rock and
  field only.
- **`WDC_01_door_02` / `WDC_01_Line_02` never on field, grass, lava, rock, sand, snow or
  tile** -- `black.dds` and nothing else.
- **`flower_01/02/05` never on `(none)`, lava, other, sand or snow.**
- **Do not mix themes.** `secretdungeon` flowers do not appear in `otherworld`, and vice
  versa; the only shared families are `zone/b/obj` and the tree sets.
- No roads worth speaking of (paved 7.9 % of ground and it is corridor, not network).

---

## Attr policy

**`attr_style: painted_box`** on 10 of 12 maps with attr data;
`slope_driven` on `otherworld_01` and `smhgate_devils` only.

| Setting | Value |
|---|---|
| `attr_style` | `painted_box` |
| `block_slope_deg` | **not meaningful** -- five maps fit 1 deg, the rest scatter 12-29 deg |
| `border_band_m` | **421 m** median seal; strict bands 12-349 m |
| `safezone_regions` | one irregular component in one map, 4,577 m^2 |

Block budget over 9,129,489 cells: slope 27.5 %, water 3.0 %, object halo 2.3 %,
**out-of-bounds 56.9 %**, residual **10.4 %**. **88.7 % of cells blocked -- the highest of
any archetype.**

- **The residual is 10.4 %**, the second-highest in the corpus after `dungeon_block`'s
  14.5 %. That is genuinely unexplained artist paint: interior walls that follow neither
  slope, water, object nor edge.
- **Paint everywhere, carve the rooms.** 56.9 % of block is edge-connected.
- **94.0 % of Building, 97.1 % of Tree and 78.8 % of Effect centre cells are blocked, but
  only 54.4 % of DungeonBlock.** The block kit is the walkable floor; everything else is
  scenery inside the walls.
- Water: 4 of 12 maps have wet cells (801,384), **1 paints the flag**, Jaccard 0.077.
  `zone/secretdungeon` stands directly on the water plane, so the water is decorative,
  not a barrier.
- **18 distinct attr bytes** -- the most of any archetype; 2 maps write above `0x07`
  covering 4.8 % of cells; `flag5` (4.8 %) and `flag6` (1.8 %) appear here and almost
  nowhere else.
- Rim slope median 6 deg versus interior 7 deg (`attributes.md` sec 8) -- the border is paint.
  Use a **15-30 m block shell**.

---

## Tells

1. **A flat one-tone sky.** `GradientLevelUpper 1` in 14 of 21, with zenith = horizon =
   nadir in 10 of those. The fog colour is the theme.
2. **One art family per map at 60-90 % of the objects.**
3. **`black.dds` is 26.9 % of the ground** -- void used as a mask, not a floor.
4. **Six different base roles across twelve maps.** rock, grass, void, paved, lava, dirt.
5. **88.7 % of cells blocked** and 10.4 % of block unexplained by any rule.
6. **Trees, and they are dead vines.** `tree/b2` IvySpy, 209 records.
7. **Skeletons tumbled on lava with real pitch**; flowers standing in water.
8. **Relief p25 = 0 cm, p90 = 143 m.** Half the archetype is a box, half a cavern.
9. **18 attr bytes**, including `flag5` and `flag6` which barely exist elsewhere.
10. **`FarDistance 1000000`** on `whitedragoncave_02` -- a million centimetres.
11. **`devilscatacomb` ships 54 sectors for a declared 7x7** and a `.msenv` it never
    loads.

---

## Road grammar confidence

**2 of 6 road-bearing maps here are confirmed roads (33%.)** The rest are
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

`corpus-overview.md` sec 4, sec 5.5 ; `catalog/map-taxonomy.json`
`archetypes.dungeon_themed`, `maps.*` ; `catalog/stats-terrain.json`
`by_archetype.dungeon_themed` ; `catalog/stats-tiles.json`
`by_archetype.dungeon_themed` ; `textures.md` sec 6 `dungeon_themed` ;
`catalog/textures.json` `texturesets["metin2_dawnmistwood_dungeon.txt"]`,
`["metin2_map_whitedragoncave_01.txt"]` ; `environments.md` sec 4.3, sec 4.7, sec 6
`dungeon_themed`, sec 8 ; `catalog/environments.json`
`archetype_presets.dungeon_themed` ; `placement.md` sec 5, sec 8 ;
`catalog/stats-objects.json` `by_archetype.dungeon_themed`, `by_crc` ;
`catalog/affinity.json` `by_archetype.dungeon_themed`, `by_crc` ;
`attributes.md` sec 4, sec 8, sec 10 ; `catalog/stats-attr.json` `archetypes.dungeon_themed`,
`maps.*`.

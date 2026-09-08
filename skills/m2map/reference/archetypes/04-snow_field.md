# 04 -- `snow_field`

**Snow field / snow mountain.** 6 maps (5 with own terrain), 69 sectors,
1,681 object placements. Reference map `map_n_snowm_01`.

---

## Identity

A cold whiteout: unbroken snow, dark grey stone bluffs, winter conifers sunk deep into
the drifts, and no water anywhere. This is the tidiest archetype in the corpus -- a
perfect 6 maps : 1 textureset : 1 environment group, every member on
`metin2_N_snowm.txt` and `N-snowm01.msenv` with nothing off-cluster
(`map-taxonomy.json` `archetypes.snow_field`).

You recognise it by: 87.4 % of painted tiles resolving to the snow role and
**96.8 % of objects standing on snow**; the `n1_` winter SpeedTree set
(ColoradoBlueSpruce, Beech_Winter, WhitePine2, CommonOlive_Winter,
MontereyCypress_Winter) and nothing else; a **height bias of exactly -80 cm on almost
every tree**; `water_cell_fraction 0.0` -- not one wet cell in 4.5 M; and the fog, which
starts at the camera and is a flat, desaturated `#AEB0BA` that reads as whiteout rather
than as haze.

`terrainmaps/n/snow.m/` is also the target folder of every one of the 78
`textureset/snow/` re-skins in the pack -- this is the game's canonical "winter"
(`textures.md` sec 4e). If you want any other archetype in snow, remap its motifs onto
these nine textures rather than authoring new art.

---

## Reference maps

| Map | Size | Sectors | Textureset | Environment | Objects | Terrain |
|---|---|---|---|---|---|---|
| **`map_n_snowm_01`** (reference) | 6x6 | 36 | `metin2_N_snowm.txt` | `N-snowm01.msenv` | 1,230 | own |
| `metin2_map_sungzi_snow` | 3x3 | 9 | `metin2_N_snowm.txt` | `N-snowm01.msenv` | 94 | own |
| `metin2_map_sungzi_snow_pass01/02/03` | 2x4 | 8 each | `metin2_N_snowm.txt` | `N-snowm01.msenv` | 119 each | own (byte-identical triplet) |
| `metin2_map_smhgate_snow` | 6x6 declared | 0 | `metin2_N_snowm.txt` | `N-snowm01.msenv` | 0 | `proxy:map_n_snowm_01` |

- **Typical size 2x4**, **flagship 6x6**.
- `sungzi_snow_pass01/02/03` are three byte-identical copies of one 2x4 map -- the same
  pattern as `sungzi_desert_hill` and `sungzi_flame_hill`.
- The whole archetype is one hub (`map_n_snowm_01`, 1,230 objects) plus four small
  instanced passes (94-119 objects each) and one terrain-less proxy.

---

## Terrain

`style: sculpted` for `map_n_snowm_01`; the four sungzi instances are `box`-flat with
painted collision. `stats-terrain.json` `by_archetype.snow_field`, 5 maps, 69 sectors.

| Quantity | Value |
|---|---|
| `height_range_cm` | 11,428.5 - 32,498.5; p5 16,383.5, **p50 18,929.0**, p95 23,305.0 |
| Relief per sector | p25 6,916 cm, **p50 7,748 cm**, p75 9,779 cm, p90 12,071 cm |
| `slope_p50` | **18.8 deg** |
| `slope_p95` | **64.4 deg** (p75 44.8 deg, p90 58.6 deg, mean 25.1 deg) |
| `flat_fraction` (< 5 deg) | **0.275** (< 2 deg 0.194, < 10 deg 0.389, < 20 deg 0.511) |
| `roughness` (abs Laplacian r=1) | p50 16.5 cm, p90 100.5, p99 393.5 |
| Local std 3x3 | p50 57.5 cm, p90 267.5 cm |
| Water cells | **0.000** |
| Blocked cells | 74.5 % |

Two things stand out. **The floor is high** -- minimum 11,428 cm, p5 16,383 -- this is a
mountain plateau, not a valley. And the **roughness p90 of 100.5 cm is the lowest of any
sculpted outdoor archetype**: snow smooths the fine detail. Slopes are steep (p50 18.8 deg)
but locally smooth. Build big smooth masses and let the texture do the surface work.

There is **no water at all**. Do not author a `WaterSpec` for this archetype.

---

## Textureset recipe

**`metin2_N_snowm.txt`**, 9 slots, the entire `terrainmaps/n/snow.m/` folder, measured
across all six maps (`textures.json` `texturesets["metin2_n_snowm.txt"]`). `weight` =
measured `ground_share`; sums to 1.000.

| slot | role | path | U/V | repeat | weight |
|---|---|---|---|---|---|
| 1 | `base` / `mid` | `d:/ymir work/terrainmaps/n/snow.m/snow01.dds` | 5/5 | 6.4 m | 0.448 |
| 2 | `mid` (dither) | `d:/ymir work/terrainmaps/n/snow.m/snow02.dds` | 5/5 | 6.4 m | 0.351 |
| 3 | `mid` (solid highlight) | `d:/ymir work/terrainmaps/n/snow.m/snow03.dds` | 5/5 | 6.4 m | 0.074 |
| 4 | `path` / road | `d:/ymir work/terrainmaps/n/snow.m/field 01.dds` | 5/5 | 6.4 m | 0.024 |
| 5 | `unused` | `d:/ymir work/terrainmaps/n/snow.m/field 02.dds` | 5/5 | 6.4 m | 0.000 |
| 6 | `unused` | `d:/ymir work/terrainmaps/n/snow.m/field 03.dds` | 5/5 | 6.4 m | 0.000 |
| 7 | `cliff` | `d:/ymir work/terrainmaps/n/snow.m/stone01.dds` | 5/5 | 6.4 m | 0.093 |
| 8 | `cliff` | `d:/ymir work/terrainmaps/n/snow.m/stone03.dds` | 5/5 | 6.4 m | 0.010 |
| 9 | `accent` | `d:/ymir work/terrainmaps/n/snow.m/ice_quest.dds` **(missing on disk)** | 4/4 | 8.0 m | 0.000 |

Every `UScale` is 5 except the dead slot 9 -- the flattest UV profile in the corpus.

`snow01` + `snow02` are the base/dither pair, and **neither scores `base` under the
role rule** because neither forms solid ground: 44.8 % at clump 4.76 / 18 % non-edge and
35.1 % at clump 3.93 / **0.8 % non-edge**. The solid ground is actually `snow03` --
7.4 % cover, clump 7.89, **96.1 % non-edge**. Read that as: the snow field is 80 %
interleaved noise with occasional solid drifts.

Slot 9 points at `ice_quest.dds`, which was disabled by renaming to `XXXice_quest.dds`
in the art dump (`textures.md` sec 7.2). The 0.014 % of tiles painted with it **draw the
error texture** in game. Do not reproduce that: either drop slot 9 or point it at a real
file. `TODO: no catalog evidence for a valid replacement -- no other ice texture exists in the n/snow.m folder.`

`n/snow.m/field 01.dds` (slot 4) is the road: 2.38 % cover, clump 6.54, 56 % non-edge,
mean slope 4.67 deg. Set `RoadSpec.tile_index = 4`.

**How the archetype paints** (`stats-tiles.json` `by_archetype.snow_field`):
role share **snow 87.4 %**, rock 10.3 %, dirt 2.4 %; base role is `snow` in all 5 maps;
median 5 slots used of 9 declared; **top-3 share median 0.984** -- three textures carry
the whole map; 2 stipple pairs per map, interleave 1.69; dither-only tile share median
0.388; singleton fraction of base 0.486.

---

## Environment

**`N-snowm01.msenv`** on all six maps -- cluster C02 `overcast_haze`, one env, no range.
One of six cluster-pure archetypes (`environments.json` `archetype_presets.snow_field`).

| Parameter | Value |
|---|---|
| `Fog.Enable` | 1 |
| `Fog.NearDistance` / `FarDistance` | **1** / **40,000 cm** |
| `Fog.Color` | `#AEB0BA` -- hue 230 deg, sat **0.065**, value 0.729 |
| `Background.Ambient` | `#45474C` (level 0.2824) |
| `Character.Ambient` | level 0.4324 = Background + 0.15 |
| `Background.Diffuse` | `#A8A8A8`, **warmth 0.0** -- a perfectly neutral key light |
| `Direction` | `0.596551 0.28178 -0.751483` (sun elev 48.7 deg, az 244.7 deg) |
| Gradient | Upper 5 / Lower 1 |
| Sky zenith -> horizon -> nadir | `#0A2D5A` -> `#AEB0BA` -> `#0F0050` |
| Cloud | `clouds_zone01.tga`, **scale 280000**, texture scale 5, speed 0.01, height 30000 |
| Skybox faces | none ; `Filter.Enable` 0 ; `LensFlare.Enable` 0 |

Two signatures: **`CloudScale 280000`** appears in only three files in the whole corpus
and the other two are this file's siblings (`snowm02.msenv` for the empire_war snow skin
and `metin2_map_n_snow_dungeon_01.msenv`). And **fog saturation 0.065** -- the most
desaturated fog in the corpus. Combined with `NearDistance 1` and `FarDistance 40,000`,
that is what makes distance read as whiteout: the horizon is the same grey as the fog
(`#AEB0BA` is literally both the fog colour and the sky horizon).

The diffuse warmth of exactly 0.0 is worth reproducing -- every other outdoor archetype
has a warm or cool bias, snow has none.

---

## Object palette

**Density 3.72 obj/ha = 0.0372 per 100 m^2 = 24.4 per sector**, only **68 distinct CRCs**
across 452.2 ha (`stats-objects.json` `by_archetype.snow_field`). Mix:
**Tree 67.1 %**, Building 30.1 %, DungeonBlock 2.1 %, Effect 0.7 %.

The DungeonBlock share is an oddity worth naming: 36 records of `ice_01`
(CRC 2688839387), an ice slab placed in `map_n_snowm_01` only. It is the only outdoor
archetype in the corpus with any DungeonBlock records at all
(`placement.md` sec 2 says no outdoor archetype uses DungeonBlock; the 36 `ice_01`
placements are the exception and they are a terrain feature, not a corridor kit).

Family budget:

| Family | n | per ha | NN same-family p25/p50/p75 (cm) | Clark-Evans R |
|---|---|---|---|---|
| `tree/n1` | 1,128 | 2.49 | 907 / **1,174** / 1,677 | 0.482 clustered |
| `zone/n/obj/snow.m` | 532 | 1.18 | 367 / **886** / 3,435 | 0.476 clustered |
| `effect/background` | 11 | 0.02 | 409 / 412 / 519 | 0.370 |
| `zone/b/obj` | 5 | 0.01 | -- | -- |
| `zone/b/building` | 4 | 0.01 | -- | -- |
| `zone/n/icemount` | 1 | 0.00 | -- | -- |

Two families carry 98.6 % of everything. `zone/n/obj/snow.m` is a **lakeside prop set**
by measurement -- its median distance to a wet cell corpus-wide is 849 cm
(`placement.md` sec 8) -- yet there is no water in this archetype at all. It gets used here
as a general boulder/fence kit.

### Tier table (directly usable as `MapSpec.objects`)

`density` per 100 m^2; `spacing_cm` = NN(same CRC) p5; `max_slope` = per-CRC slope p95;
`road_clearance_cm` = per-CRC d(road) p25; `height_bias` = (bias p25, bias p75).
`on_tiles` indexes the 9-slot palette above.

| tier | crc | name | density | spacing_cm | on_tiles | max_slope | road_clear_cm | height_bias |
|---|---|---|---|---|---|---|---|---|
| signature | 239479779 | `ColoradoBlueSpruce1` (Tree, `tree/n1`) | 0.00462 | 1305 | 1,2,3 | 21 | 565 | (-80, -8) |
| signature | 2418081500 | `Beech_Winter1` (Tree, `tree/n1`) | 0.00383 | 2717 | 1,2,3 | 25 | 847 | (-80, -12) |
| signature | 2988076545 | `ColoradoBlueSpruce2` (Tree, `tree/n1`) | 0.00310 | 1129 | 1,2,3 | 24 | 282 | (-80, -31) |
| signature | 2350806930 | `Beech_Winter2` (Tree, `tree/n1`) | 0.00287 | 2659 | 1,2,3 | 25 | 1094 | (-80, -80) |
| signature | 772935195 | `ColoradoBlueSpruce3` (Tree, `tree/n1`) | 0.00232 | 1107 | 1,2,3 | 27 | 848 | (-80, -22) |
| signature | 1313531708 | `Beech_Winter3` (Tree, `tree/n1`) | 0.00190 | 2933 | 1,2,3 | 26 | 1372 | (-80, -40) |
| signature | 2661267695 | `WhitePine2` (Tree, `tree/n1`) | 0.00148 | 1064 | 1,2,3 | 13 | 730 | (0, 0) |
| signature | 476855675 | `CommonOlive_Winter` (Tree, `tree/n1`) | 0.00124 | 2950 | 1,2,3 | 33 | 200 | (-80, -80) |
| signature | 3641533454 | `MontereyCypress_Winter1` (Tree, `tree/n1`) | 0.00117 | 1809 | 1,2,3 | 26 | 1094 | (-80, -31) |
| signature | 4193629000 | `MontereyCypress_Winter2` (Tree, `tree/n1`) | 0.00100 | 2509 | 1,2,3 | 36 | 262 | (-80, -40) |
| accent | 886252439 | `MontereyCypress_Winter3` (Tree, `tree/n1`) | 0.00049 | 1755 | 1,2,3 | 33 | 1600 | (-80, -15) |
| filler | 3785232591 | `general_obj_stone10` (Building, `zone/n/obj/snow.m`) | 0.00077 | 4093 | 1,2 | 19 | 2459 | (-25, 0) |
| filler | 923239313 | `general_obj_fence03` (Building, `zone/n/obj/snow.m`) | 0.00075 | 358 | 1,2,7 | 8 | 0 | (-29, 0) |
| filler | 1595676473 | `general_obj_stone13` (Building, `zone/n/obj/snow.m`) | 0.00073 | 2774 | 1,2 | 19 | 2015 | (-25, 0) |
| filler | 3904665691 | `general_obj_stone14` (Building, `zone/n/obj/snow.m`) | 0.00055 | 9935 | 1,2 | 16 | 1815 | (-12, 5) |
| filler | 3911262344 | `general_obj_stone07` (Building, `zone/n/obj/snow.m`) | 0.00053 | 6378 | 1,2 | 20 | 3673 | (-25, -15) |
| filler | 2519560232 | `general_obj_fence02` (Building, `zone/n/obj/snow.m`) | 0.00053 | 307 | 1,2 | 6 | 800 | (0, 0) |
| filler | 3590562120 | `general_obj_stone18` (Building, `zone/n/obj/snow.m`) | 0.00051 | 8005 | 1,2 | 15 | 3612 | (-25, 0) |
| filler | 981658005 | `general_obj_stone1` (Building, `zone/n/obj/snow.m`) | 0.00046 | 5081 | 1,2 | 25 | 2541 | (-25, 0) |
| accent | 2688839387 | `ice_01` (DungeonBlock, `zone/n/obj/snow.m`) | 0.00080 | 127 | 9 | 13 | 370 | (0, 0) |

**`WhitePine2` is the exception that proves the sink rule**: bias exactly 0 at p25, p50
and p75, roll zero-share only 0.20, `never_on` everything except snow and field, slope
p95 13.3 deg. It is a flat-ground, always-rotated, never-sunk tree -- treat it as a separate
species with its own rules rather than folding it into the conifer group.

`ice_01` sits on `n/snow.m/ice_quest.dds` in 97 % of its records -- the *missing*
texture. It is an ice sheet placed over a patch of error-texture ground.

---

## Placement rules

**Ground affinity** (`affinity.json` `by_archetype.snow_field`, n = 1,681):
**snow 96.8 %**, field 2.1 %, rock 0.8 %, `(none)` 0.2 %. Object slope p50 6.44 deg,
p75 12.15 deg, p95 22.91 deg -- a *narrower* slope band than any other archetype (only 2 of
1,677 placements are above 45 deg).

**Positive rules**

1. **Sink every tree 80 cm.** `tree/n1` bias p25 = p50 = -80 cm on nine of ten species --
   the deepest and most uniform sink in the corpus (`placement.md` sec 1.3). This hides the
   SpeedTree root flare in the drift, and it is the single most recognisable snow habit.
2. **Trees are the map.** 67 % of placements, at NN p50 1,174 cm. Tighter than
   `field_empire` (1,686) and much tighter than `trent_forest` (2,729).
3. **Trees are mostly unrotated** -- 82.7 % of `tree/n1` corpus-wide has roll exactly 0,
   and here the per-species zero-share runs 0.74-0.94. Only `WhitePine2` (0.20) breaks it.
   Yaw is zero in 99.3-100 % of records and pitch is **exactly 0 in every single
   `tree/n1` record**. Do not tilt a conifer.
4. **Roads are wide and looped.** Width median 8.0 m (distance-transform 5.0 m),
   4.88 loops/km -- the loopiest network of any archetype measured -- 7.51 junctions/km,
   tortuosity 1.29, radius of curvature 27 m, **blend band 1.0 m** (a hard edge; snow
   does not feather into the track). Buildings and trees both sit ~3,700-3,800 cm from
   it (`placement.md` sec 5), the largest building setback of any field archetype.
5. **Boulders far out, fences on the road.** `general_obj_stone*` d(road) p25 = 1,800 -
   3,700 cm; `general_obj_fence02/03` d(road) p25 = 0-800 cm. The stone set is the
   wilderness, the fence set is the pass.

**Negative rules**

- **`tree/n1` is never placed on lava or sand.** Several members additionally never on
  `other`, `grass`, `tile` or `rock`; `WhitePine2`'s `never_on` list is everything except
  snow and field (`affinity.json.by_crc`).
- **No `b1`/`b2`/`b3`/`n2` trees.** All 1,128 tree records are `tree/n1`.
- **No water.** `water_cell_fraction` 0.0, `attr_water_cells` 0, `wtr_wet_cells` 0. The
  `zone/n/obj/snow.m` set *is* a lakeside kit in other maps, but there is no lake here.
- **`general_obj_stone13/07/18/1` never on field, grass, rock, sand, tile, lava, other** --
  100 % of their records are on snow. Nine of the eighteen ground classes are simply
  unreachable in this archetype.
- No `zone/b/building`-style settlement: 4 records in the whole archetype.

---

## Attr policy

`slope_driven` on `map_n_snowm_01` only; `painted_box` on the four sungzi instances
(`stats-attr.json` `maps.*.attr_style`).

| Setting | Value (for a sculpted snow field) |
|---|---|
| `attr_style` | `slope_driven` |
| `block_slope_deg` | **18** (`map_n_snowm_01`'s fitted threshold; the archetype median of 25 is an artefact of the four painted instances) |
| `border_band_m` | **512 m** archetype median seal; `map_n_snowm_01` strict band 72 m |
| `safezone_regions` | 6 circle-brush stamps across 4 maps, median 862 m^2, bbox edge 29.5 m |

Archetype block budget over 3,349,034 cells: slope 63.6 %, **water 0.0 %**, object halo
3.3 %, out-of-bounds 32.8 %, residual 0.3 %. On `map_n_snowm_01` alone it is
**slope 85.7 %**, out-of-bounds 11.3 %, object halo 2.2 % -- one of the cleanest
slope-driven maps in the corpus. The 32.8 % archetype figure comes from the sungzi
instances, which block 95.1-97.6 % of their cells outright.

- **Never paint `ATTRIBUTE_WATER`.** Zero water cells archetype-wide.
- **Footprint policy: `painted` on the hub, `model_only` on the instances.** 84.6 % of
  Building centre cells are blocked but only 26.1 % of Tree centre cells and **0 % of
  DungeonBlock (`ice_01`) centre cells** -- the ice slabs are deliberately walkable.
- **The border is not a wall.** Rim slope median 20 deg versus interior 27 deg
  (`attributes.md` sec 8) -- this is the only archetype where the rim is *flatter* than the
  interior. A snow field is fenced by paint on a plateau, not by a raised ridge.
  All 5 maps are sealed strict.
- One map (`map_n_snowm_01`) writes paint bytes above `0x07`, covering 52.2 % of the
  archetype's cells. It is one of the 17 maps that set `0x80` on every cell of a sector
  -- mask before writing `server_attr` (`attributes.md` sec Discrepancies 3).
- Safezone: 6 components, **all circle-brush**, in 4 of 5 maps. Median area 862 m^2,
  median bbox edge 29.5 m, fill 0.824.

---

## Tells

1. **Bias exactly -80.** Nine of the ten conifer species carry `-80 cm` at both p25 and
   p50. Nothing else in the corpus is that uniform.
2. **Whiteout fog.** `NearDistance 1`, `FarDistance 40,000`, colour `#AEB0BA` at
   saturation 0.065 -- and the sky horizon is the *same* colour. There is no visible
   horizon line.
3. **`CloudScale 280000`.** Three files in the corpus, all snow.
4. **Diffuse warmth 0.0.** A perfectly neutral `#A8A8A8` key light.
5. **Two textures do 80 % of the work and neither is solid.** `snow01` 44.8 % at 18 %
   non-edge, `snow02` 35.1 % at 0.8 % non-edge; `snow03` is the only solid slot and it
   is 7.4 %.
6. **All `UScale 5`.** Nine slots, one scale.
7. **Zero water.** Not one wet cell.
8. **A flat rim.** Rim slope 20 deg against interior 27 deg -- the only archetype whose border
   is flatter than its middle.
9. **`ice_quest.dds` renders as the error texture.** Slot 9 is broken in the shipped
   data. Reproducing the palette faithfully means reproducing a visible bug; don't.
10. **This is the winter re-skin target.** Every `textureset/snow/*.txt` in the pack
    remaps some other palette onto these nine textures by motif -- `field*` ->
    `field 01.dds`, `stone*` -> `stone01.dds`, `grass*` -> `snow01.dds`, `tile*` ->
    `snow03.dds`, `beach`/`sand*` -> `snow01.dds` (`textures.md` sec 4e).

---

## Sources

`corpus-overview.md` sec 4 ; `catalog/map-taxonomy.json` `archetypes.snow_field` ;
`catalog/stats-terrain.json` `by_archetype.snow_field` ;
`catalog/stats-tiles.json` `by_archetype.snow_field` ;
`textures.md` sec 4e, sec 6 `snow_field`, sec 7.2 ; `catalog/textures.json`
`texturesets["metin2_n_snowm.txt"]` ; `environments.md` sec 5, sec 6 `snow_field` ;
`catalog/environments.json` `archetype_presets.snow_field` ;
`placement.md` sec 1.3, sec 2, sec 3.1, sec 4.1, sec 5, sec 8 ; `catalog/stats-objects.json`
`by_archetype.snow_field`, `by_crc` ; `catalog/affinity.json`
`by_archetype.snow_field`, `by_crc` ; `attributes.md` sec 4, sec 8, sec 10, sec Discrepancies ;
`catalog/stats-attr.json` `archetypes.snow_field`, `maps.*` ; `catalog/roads.json`
`by_archetype.snow_field` -- pooled and unfiltered, see
`roads.json.by_archetype_caveat`.

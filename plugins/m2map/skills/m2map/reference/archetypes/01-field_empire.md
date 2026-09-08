# 01 -- `field_empire`

**Empire temperate field and capitals (B-family terrain).** 18 maps, 167 sectors,
8,927 object placements. Reference map `metin2_map_a1`.

---

## Identity

This is the default Metin2 look and the safest thing a generator can emit: a green
temperate overworld of rolling grass and dirt fields, grey stone bluffs, wide rivers
and sand shorelines, under a clear blue noon sky. The three empire capitals -- `a1`,
`b1`, `c1` -- are *not* three biomes; they are three copies of this one. Their
texturesets are byte-identical files (md5-verified) and `a1.msenv` is byte-identical to
`c1.msenv` (`corpus-overview.md` sec 2). What separates them is a single thing: the
building family in `areadata.txt` -- `zone/a/building` in a1 (54 records),
`zone/b/building` in b1 (282), `zone/c/building` in c1 (71).

You recognise it by: `terrainmaps/b/**` and nothing else; the `b1_`/`b3_` deciduous
SpeedTrees (Beech, Pagoda, MontereyCypress) and *zero* winter or arid trees; a visible
road web painted in an ordinary dirt texture; and beaches. 28.9 % of all cells in this
archetype are water (`stats-terrain.json` `by_archetype.field_empire.water_cell_fraction`)
-- the highest of any outdoor archetype. An empire field without a river reads wrong.

---

## Reference maps

| Map | Size | Sectors | Textureset | Environment | Objects | Terrain |
|---|---|---|---|---|---|---|
| **`metin2_map_a1`** (reference) | 4x5 | 20 | `metin2_A1.txt` | `A1.msenv` | 1,226 | own |
| `metin2_map_b1` | 4x5 | 20 | `metin2_B1.txt` | `B1.msenv` | 1,284 | own |
| `metin2_map_c1` | 4x5 | 20 | `metin2_C1.txt` | `C1.msenv` | 891 | own |
| `metin2_map_a3` | 4x4 | 16 | `metin2_A3.txt` | `A3.msenv` | 1,116 | own |
| `metin2_map_b3` | 4x4 | 16 | `metin2_B3.txt` | `B3.msenv` | 1,030 | own |
| `metin2_map_c3` | 4x4 | 16 | `metin2_C3.txt` | `C3.msenv` | 629 | own |
| `metin2_map_milgyo` | 4x4 | 16 | `metin2_milgyo.txt` | `milgyo.msenv` | 862 | own |
| `metin2_guild_war2` | 3x3 | 9 | `metin2_guild_war2.txt` | `war2.msenv` | 62 | own |
| `map_b_fielddungeon` | 2x2 | 4 | `metin2_B_fielddungeon.txt` | `map_b_fielddungeo.msenv` | 173 | own |
| `metin2_guild_war4` | 2x2 | 4 | `metin2_guild_war4.txt` | `war4.msenv` | 256 | own |
| `metin2_map_battlefied` | 2x2 | 4 | `metin2_battlefield.txt` | `battlefield.msenv` | 68 | own |
| `metin2_map_guild_02` | 2x2 | 4 | `metin2_C1.txt` | `C1.msenv` | 130 | own |
| `metin2_map_guild_03` | 2x2 | 4 | `metin2_B1.txt` | `B1.msenv` | 237 | own |
| `metin2_map_sungzi` | 2x2 | 4 | `metin2_A1.txt` | `sungzi.msenv` | 3 | own |
| `metin2_map_wedding_01` | 1x1 | 1 | `metin2_map_wedding_01.txt` | `A1.msenv` | 65 | own |
| `metin2_map_smhgate_a1/_b1/_c1` | 4x5 declared | 3 each | parent's | parent's | 318 / 349 / 228 | `partial:` parent |

(`map-taxonomy.json` `maps.*` and `archetypes.field_empire`.)

- **Typical size 2x2**, modal over the 15 members with their own terrain.
- **Reference (flagship) size 4x5** -- a1, b1, c1 and the three `smhgate_*` cut-outs.
- Size histogram: 1x1 x1, 2x2 x6, 3x3 x1, 4x4 x4, 4x5 x6.

Use 2x2 for a side field, 4x5 for a capital overworld tile.

---

## Terrain

`style: sculpted`. All numbers from `stats-terrain.json` `by_archetype.field_empire`
(n = 2,750,104 vertices, 2,736,128 slope cells, 167 sectors).

| Quantity | Value |
|---|---|
| `height_range_cm` | 0.0 - 32,243.5; p5 8,015.5, **p50 17,868.5**, p95 25,129.5 |
| Relief per sector | p25 6,840 cm, **p50 9,215 cm**, p75 11,659 cm, p90 15,880 cm |
| `slope_p50` | **12.8 deg** |
| `slope_p95` | **70.7 deg** (p75 43.4 deg, p90 62.8 deg, mean 23.4 deg) |
| `flat_fraction` (< 5 deg) | **0.361** (< 2 deg 0.281, < 10 deg 0.460, < 20 deg 0.575) |
| `roughness` (abs Laplacian r=1) | p50 18.5 cm, p90 211.5 cm, p99 909.5 cm |
| Local std 3x3 | p50 41.5 cm, p90 313.5 cm |
| Water cells | **28.9 %** |
| Blocked cells | 61.2 % |

Read that shape carefully: the median slope is 12.8 deg but the 75th percentile jumps to
43 deg and the 90th to 63 deg. That is not a smooth landscape with a long tail -- it is a
**bimodal one**: 36 % of the map is near-flat walkable field and roughly a third of it is
near-vertical cliff wall, with very little in between. Empire fields are flat pans
fenced by rock. Generate the flat part first, then cut the cliffs; do not fractal-noise
the whole thing to a uniform 20 deg.

The 17,868 cm median height is a consequence of the sea level: rivers and coast sit
low and the field plateau sits high, which is what produces the 9.2 m median relief
per sector.

---

## Textureset recipe

Reference palette **`metin2_A1.txt`**, 17 slots, measured across `metin2_map_a1`,
`metin2_map_smhgate_a1`, `metin2_map_sungzi` (`textures.json`
`texturesets["metin2_a1.txt"]`). It is byte-identical to `metin2_b1.txt`,
`metin2_c1.txt`, `metin2_b_fielddungeon.txt`, `metin2_map_n__trent.txt`,
`metin2_map_otherworld_02.txt` and `metin2_map_t1.txt` -- one file serving three empires
and a dungeon.

The slot order is literally the `terrainmaps/b/` directory listing
(`field 01-04`, `grass 01-03`, `stone01-04`, `tile01-02`, `beach sand 01-03`, `tile03`).
Because painter's order is index order, that folder convention *incidentally* puts
roads and beaches last, where they overpaint the ground (`textures.md` sec 4a).

`weight` is the measured `ground_share` on the reference map; the column sums to 1.000
by construction.

| slot | role | path | U/V | repeat | weight |
|---|---|---|---|---|---|
| 1 | `road` (see note) | `d:/ymir work/terrainmaps/b/field/field 01.dds` | 5/5 | 6.4 m | 0.142 |
| 2 | `cliff` | `d:/ymir work/terrainmaps/b/field/field 02.dds` | 6/6 | 5.3 m | 0.001 |
| 3 | `accent` | `d:/ymir work/terrainmaps/b/field/field 03.dds` | 5/5 | 6.4 m | 0.000 |
| 4 | `mid` | `d:/ymir work/terrainmaps/b/field/field 04.dds` | 6/6 | 5.3 m | 0.093 |
| 5 | `base` | `d:/ymir work/terrainmaps/b/grass/grass 01.dds` | 9/9 | 3.6 m | 0.237 |
| 6 | `mid` | `d:/ymir work/terrainmaps/b/grass/grass 02.dds` | 8/8 | 4.0 m | 0.107 |
| 7 | `mid` | `d:/ymir work/terrainmaps/b/grass/grass 03.dds` | 9/9 | 3.6 m | 0.041 |
| 8 | `cliff` | `d:/ymir work/terrainmaps/b/stone/stone01.dds` | 5/5 | 6.4 m | 0.167 |
| 9 | `cliff` | `d:/ymir work/terrainmaps/b/stone/stone02.dds` | 4/4 | 8.0 m | 0.096 |
| 10 | `cliff` | `d:/ymir work/terrainmaps/b/stone/stone03.dds` | 5/5 | 6.4 m | 0.003 |
| 11 | `cliff` | `d:/ymir work/terrainmaps/b/stone/stone04.dds` | 5/5 | 6.4 m | 0.011 |
| 12 | `path` | `d:/ymir work/terrainmaps/b/tile/tile01.dds` | 5/5 | 6.4 m | 0.002 |
| 13 | `unused` | `d:/ymir work/terrainmaps/b/tile/tile02.dds` | 5/5 | 6.4 m | 0.000 |
| 14 | `shore` | `d:/ymir work/terrainmaps/b/beach/beach sand 01.dds` | 5/5 | 6.4 m | 0.082 |
| 15 | `shore` | `d:/ymir work/terrainmaps/b/beach/beach sand 02.dds` | 5/5 | 6.4 m | 0.000 |
| 16 | `shore` | `d:/ymir work/terrainmaps/b/beach/beach sand 03.dds` | 5/5 | 6.4 m | 0.018 |
| 17 | `cliff` | `d:/ymir work/terrainmaps/b/tile/tile03.dds` | 7/7 | 4.6 m | 0.000 |

**Note on slot 1 -- a real source conflict, resolved.** `textures.json` scores
`b/field/field 01.dds` as `base` (14.2 % cover, clump 5.40, 29 % non-edge) because its
rule is pooled over cover and clumping. `placement.md` sec 5 and sec 10 are right that on
`metin2_map_a1` this slot *is* the road web -- it was visually verified against the
rendered tile grid, and it is the index the geometric road detector selects while
rejecting slot 4 as its blend halo. **There is no road texture in Ymir's art**
(all 355 distinct `.dds` searched, `roads.json.texture_role_vocabulary.road_like_names`
is empty). Roles are multi-valued: this file is ground in `metin2_map_b1` and road
surface in `metin2_map_a1`. Set `RoadSpec.tile_index = 1` for this archetype; keep
`role: "road"` on the slot so the stipple stage does not also scatter it.

`b/tile/tile01.dds` (slot 12) is the *plaza*, not the road: 0.24 % cover but clump 7.64
and 86 % non-edge on 0 deg ground -- a small paved town square.

**How the archetype paints, corpus-wide** (`stats-tiles.json` `by_archetype.field_empire`):

- role share of all painted tiles: rock 37.8 %, grass 32.1 %, dirt 20.7 %, sand 6.4 %,
  paved 2.9 %;
- median 10 slots used of 17 declared (unused fraction 0.353);
- median base share 0.344, top-3 share 0.782;
- **4.5 dither-only slots per map**, carrying 21.8 % of tiles -- nearly a quarter of the
  ground exists only as speckle;
- 3 stipple pairs per map, interleave 1.82, `stipple_same_family_share` 0.746 -- the
  dither partner is almost always a sibling from the same art folder
  (`grass 01`/`grass 02`, `field 04`/`field 01`);
- singleton fraction of the base index 0.510: half the base texture's connected
  components are a single 1 m tile.

Other palettes in the archetype: `metin2_A3.txt`/`metin2_B3.txt`/`metin2_C3.txt`/
`metin2_map_wedding_01.txt` (11 slots -- the same 11 motifs in a later `_01` re-colour),
`metin2_battlefield.txt` (5), `metin2_milgyo.txt` (12), `metin2_guild_war2.txt` and
`metin2_guild_war4.txt` (17 each).

---

## Environment

**Canonical `A1.msenv`** -- cluster C00 `clear_blue_noon`, used by `metin2_map_a1`,
`metin2_map_smhgate_a1`, `metin2_map_wedding_01`; byte-identical to `c1.msenv` and
`war4.msenv`. 12 distinct envs across 18 maps, 12 of them in C00
(`environments.json` `archetype_presets.field_empire`).

| Parameter | Observed over all 18 maps |
|---|---|
| `Fog.Enable` | 1 x18 |
| `Fog.NearDistance` | 0 - 5,000 cm (p25 250, **median 5,000**) |
| `Fog.FarDistance` | 20,000 - 50,000 cm (**median 20,000**) |
| `Fog.Color` | `#B0BDD6` (a1/c1) -- full set `#272522 #4FA4AF #69594E #8C7761 #A19B94 #B0BDD6 #D8E6FF #E6CDAC` |
| `Background.Ambient` | `#000000` (median level 0.0; max 0.6967) |
| `Character.Ambient` | Background + 0.15 per channel, exactly, in all 104 corpus files |
| `Background.Diffuse` | `#FFF8F8` most common; warmth 0.0275 |
| `Direction` | `0.350156 0.562609 -0.748907` (sun elev 48.5 deg, az 211.9 deg); also `0.5 0.5 -0.5` and `0.596551 0.28178 -0.751483` |
| Gradient | Upper 4 x15 / Lower 1 x18 |
| Sky zenith -> horizon | `#1849A8` -> `#D9E6FF`, nadir `#88909F` |
| Cloud | `clouds_zone01.tga`, scale 200000, texture scale 4, speed 0.004, height 30000 |
| Skybox faces | none; `bTextureRenderMode` absent in 17 of 18 |

The archetype's fog is a *short* fog: near 5,000 cm, far 20,000 cm. Remember that
`Fog.FarDistance` is also the terrain texture-draw budget (`environments.md` sec 4.3) --
beyond FogFar + 1,600 cm the client draws untextured patches flat-filled with
`Fog.Color`. 20,000 cm is under one sector; that is deliberate and it is what makes an
empire field feel enclosed.

Six members sit off-cluster: `a3`/`b3`/`c3` in C02 `overcast_haze`,
`map_b_fielddungeo` in C06 `ember_orange`, `milgyo` in C08 `sand_haze` (shared with
`desert`), `war2` in C01 `murky_lowlight`. If you want the "third-tier field" look
rather than the capital look, take `A3.msenv`.

---

## Object palette

**Density 8.16 obj/ha = 0.0816 per 100 m^2 = 53.5 per sector**, 366 distinct CRCs across
1,094.45 ha (`stats-objects.json` `by_archetype.field_empire`). Mix: Building 58.3 %,
Tree 40.9 %, Effect 0.8 %, DungeonBlock 0 %.

Family budget:

| Family | n | per ha | NN same-family p25/p50/p75 (cm) | Clark-Evans R |
|---|---|---|---|---|
| `zone/b/obj` | 4,174 | 3.81 | 201 / **367** / 932 | 0.339 clustered |
| `tree/b1` | 2,231 | 2.04 | 1,192 / **1,686** / 2,497 | 0.572 clustered |
| `tree/b3` | 1,097 | 1.00 | 1,050 / **1,431** / 2,872 | 0.620 clustered |
| `zone/b/building` | 742 | 0.68 | 249 / **998** / 1,900 | 0.248 strongly clustered |
| `zone/c/building` | 131 | 0.12 | 800 / 1,000 / 2,379 | 0.156 |
| `zone/a/building` | 86 | 0.08 | 999 / 1,541 / 2,435 | 0.145 |
| `effect/background` | 46 | 0.04 | 997 / 25,902 / 45,038 | **1.268 regular** |

`effect/background` is the only family in the whole corpus that is placed *more* evenly
than chance. Everything else clumps.

### Tier table (directly usable as `MapSpec.objects`)

`density` = placements per 100 m^2 over the archetype's whole terrain area.
`spacing_cm` = the observed NN(same CRC) p5, i.e. the floor the artists respected.
`max_slope` = per-CRC slope p95. `road_clearance_cm` = per-CRC d(road) p25.
`height_bias` = (p25, p75) of the stored bias, sampled uniformly.
`on_tiles` refers to the 17-slot palette above.

| tier | crc | name | density | spacing_cm | on_tiles | max_slope | road_clear_cm | height_bias |
|---|---|---|---|---|---|---|---|---|
| signature | 3689520799 | `Beech4` (Tree, `tree/b1`) | 0.00224 | 2025 | 1,4,5,6,7 | 45 | 280 | (-91, -9) |
| signature | 569394331 | `Pagoda1` (Tree, `tree/b1`) | 0.00201 | 1709 | 1,4,5,6,7 | 47 | 565 | (-358, -25) |
| signature | 2376089798 | `Pagoda2` (Tree, `tree/b1`) | 0.00186 | 2397 | 1,4,5,6,7 | 46 | 600 | (-273, -20) |
| signature | 3748653682 | `MontereyCypress3` (Tree, `tree/b1`) | 0.00185 | 2794 | 1,4,5,6,7 | 46 | 200 | (-152, -5) |
| signature | 3455398876 | `Beech3` (Tree, `tree/b3`) | 0.00185 | 2662 | 1,4,5,6,7 | 41 | 400 | (-60, -5) |
| signature | 1107711305 | `Pagoda3` (Tree, `tree/b1`) | 0.00183 | 1503 | 1,4,5,6,7 | 46 | 565 | (-152, -20) |
| signature | 2399205967 | `Beech2` (Tree, `tree/b1`) | 0.00169 | 2934 | 1,4,5,6,7 | 44 | 600 | (-91, -13) |
| signature | 1289994135 | `MontereyCypress4` (Tree, `tree/b1`) | 0.00157 | 3095 | 1,4,5,6,7 | 45 | 0 | (-92, -17) |
| signature | 2188671155 | `MontereyCypress1` (Tree, `tree/b1`) | 0.00157 | 3039 | 1,4,5,6,7 | 41 | 282 | (-100, -3) |
| signature | 486960621 | `MontereyCypress2` (Tree, `tree/b1`) | 0.00148 | 2447 | 1,4,5,6,7 | 34 | 282 | (-60, 0) |
| signature | 1353164984 | `Beech1` (Tree, `tree/b1`) | 0.00140 | 2765 | 1,4,5,6,7 | 46 | 262 | (-76, -16) |
| signature | 1671224775 | `MontereyCypress5` (Tree, `tree/b1`) | 0.00112 | 2469 | 1,4,5,6,7 | 47 | 200 | (-92, -5) |
| filler | 1401373405 | `ob-7-03-01` (Building, `zone/b/obj`) | 0.00197 | 336 | 4,5,6,7 | 29 | 3248 | (-50, 0) |
| filler | 538957537 | `general_obj_fence03` (Building, `zone/b/obj`) | 0.00143 | 335 | 1,4,5,6,14 | 24 | 447 | (-15, 0) |
| filler | 358206493 | `ob-b1-005-woodbarrel` (Building, `zone/b/obj`) | 0.00121 | 73 | 1,4,5,6 | 10 | 0 | (-5, 0) |
| filler | 1535330398 | `general_obj_fence01` (Building, `zone/b/obj`) | 0.00121 | 427 | 4,5,6,8 | 24 | 447 | (-30, 0) |
| filler | 1817296008 | `general_obj_fence02` (Building, `zone/b/obj`) | 0.00099 | 299 | 4,5,6 | 18 | 400 | (-30, 0) |
| filler | 1167113627 | `ob-b1-001-box02` (Building, `zone/b/obj`) | 0.00095 | 86 | 1,4,5,6 | 10 | 0 | (-5, 0) |
| accent | 1985750273 | `b1-middledam-02` (Building, `zone/b/building`) | 0.00110 | 996 | 5,6,12 | 0 | 730 | (0, 0) |
| accent | 3193282972 | `Sassafras_Fall1` (Tree, `tree/b1`) | 0.00099 | 4603 | 1,4,5,6 | 28 | 0 | (-45, -30) |

The empire discriminator is not in this table because it is small and map-specific: add
**one** house family and only one -- `zone/a/building` (86 records archetype-wide, NN
p50 1,541 cm) for Empire A, `zone/b/building` (742, NN p50 998 cm) for Empire B,
`zone/c/building` (131, NN p50 1,000 cm) for Empire C. Do not mix two; no shipped map
does except by accident (`metin2_map_a1` has exactly 1 stray `zone/b/building` record
out of 1,226).

For companions inside a tier use `cooccurrence.json.companions_15m`. The measured
forest recipe for `Pagoda1` is `Pagoda3` (obs 64, x4.1), `Pagoda2` (61, x3.8),
`Beech4` (50, x4.4), `MontereyCypress4` (41, x5.4), `ob-bigstone03` (31, x8.0) --
three Pagoda variants, a Beech, a Cypress and the occasional boulder
(`placement.md` sec 6).

---

## Placement rules

**Ground affinity** (`affinity.json` `by_archetype.field_empire`, n = 8,927):
field 52.6 %, grass 35.9 %, tile 6.2 %, rock 4.5 %, sand 0.8 %. Object slope
p50 0.81 deg, p75 7.16 deg, p95 22.92 deg -- objects sit on the *flat* part of a map whose
terrain p50 is 12.8 deg. Placement is not slope-blind sampling; it is confined to the
walkable pan.

**Positive rules**

1. **Lay the road web first.** 14 of 18 members carry a detectable road network;
   median centreline width 5.0 m (distance-transform median 4.3 m), road core fraction
   0.095 of the map, density 11,932 m/km^2, tortuosity 1.20, 6.84 junctions/km,
   2.07 loops/km, radius of curvature median 46 m
   (`roads.json.by_archetype.field_empire` -- see the caveat below). Junction mix is
   T 37 % / Y 36 % corpus-wide.
2. **Buildings hug the road, trees stand back.** Building d(road) p50 **600 cm**,
   tree d(road) p50 **2,200 cm** (`placement.md` sec 5). Per-CRC the tree quartiles run
   200-600 cm at p25 and 3,700-16,000 cm at p75 -- the upper quartile is what creates
   the wilderness behind the treeline.
3. **Flatten before you build.** `zone/b/building` slope p50 0.0 deg, p95 8.45 deg
   (n = 1,016); `zone/a/building` p50 0.14 deg, p95 16.2 deg; `zone/c/building` p50 0.0 deg,
   p95 22.2 deg.
4. **Props travel in packs.** 60 % of `zone/b/obj` records have another prop within 5 m.
   Crates come in threes: `ob-b1-001-box01` self-clumps at x1,804 within 5 m,
   `ob-b1-005-woodbarrel` + `ob-b1-001-box01` obs 148 at x722. Fences run 3-5 segments.
5. **Sink the trees.** `tree/b1` bias median -45 cm, `tree/b3` -35 cm. 74.8 % of all
   Tree records have negative bias.
6. **Buildings do not sink.** `zone/b/building` bias is exactly 0 in 83.6 % of records.
7. **Effects last, on landmarks, raised.** Only 46 in the archetype;
   `fire_general_obj_campfire.mse` carries +570 cm bias; effect d(road) p25/p50 = 0/0.

**Negative rules -- these are absolute in the shipped data**

- **No `tree/n1` and no `tree/n2` species belong here.** All 618 tree records in
  `metin2_map_a1` are b-family (561 `b1_*` + 57 `b3_*`), zero `n1_`/`n2_`
  (`map-taxonomy.json` evidence string). The 182 `tree/n2` records that exist
  archetype-wide are imported patches in `a3`/`b3`, Clark-Evans R = 0.054 -- extreme
  clumps, not scatter.
- **`tree/b1` is never placed on lava or snow. `tree/b3` never on lava, snow or tile**
  (`affinity.json.by_crc` `never_on`). `tree/b1` on snow: 0 records in 5,968 corpus-wide.
- **`zone/a/building` is never on lava, snow or "other"**, and effectively never on rock
  (1.4 %) or sand (0.5 %) -- the empire house set does not go on a beach.
- **`ob-7-03-01` is never on `(none)`, lava, other, sand, snow or tile** -- it is a
  grass/field prop only.
- **No DungeonBlock records.** No outdoor archetype in the corpus contains one.
- Do not place buildings on the cliff band. 9.4 % of Buildings corpus-wide sit above
  30 deg and almost all of those are rocks, not houses.

**Water is not an exclusion zone.** 14.5 % of Buildings and 12.6 % of Trees corpus-wide
stand on a cell flagged wet in `water.wtr`. With 28.9 % water cover here, shoreline
vegetation standing in the shallows is correct.

---

## Attr policy

`attr_style: slope_driven` for 14 of 18 members; `painted_box` for
`metin2_guild_war2`, `metin2_guild_war4`, `metin2_map_milgyo`, `metin2_map_sungzi`
(`stats-attr.json` `maps.*.attr_style`).

| Setting | Value |
|---|---|
| `attr_style` | `slope_driven` |
| `block_slope_deg` | **20** (median of the 18 per-map fitted thresholds; quartiles 17-21) |
| `border_band_m` | **123 m** median seal depth; per-map strict bands 19-165 m |
| `safezone_regions` | circular stamps, d = 24-56 m, on the town square |

Block budget over the archetype's 6,600,121 block cells: slope 65.1 %, water 16.9 %,
out-of-bounds seal 14.5 %, object halo 3.1 %, residual 0.4 %
(`stats-attr.json` `archetypes.field_empire.block_budget`). Overall 60.3 % of cells are
blocked.

- **Water is the second-largest cause here**, unusually so -- 16.9 % versus a
  `slope_driven` corpus figure of 14.8 %. On `metin2_map_b1` and `metin2_map_c1` water
  accounts for 42.6 % and 44.2 % of block respectively. Paint `WATER | BLOCK` on
  submerged cells.
- **Footprint policy: `painted` on 14 of 18 maps.** 85.7 % of Building centre cells are
  blocked. Stamp the building footprint into `attr.atr`; a generator that skips it makes
  walk-through houses.
- Trees are the opposite: only 8.0 % of Tree centre cells are blocked.
- **Border.** All 18 maps are sealed except `smhgate_a1` and `smhgate_b1` (partial
  cut-outs of a1/b1, so their inner edges are open by design). Rim slope median 34 deg
  versus interior 6 deg -- the border is a mountain wall the artist raised, then let the
  slope rule seal.
- **Safezone.** 11 of 18 maps use it, 29 components, 21 of them circle-brush stamps;
  median component area 1,264 m^2, median bbox edge 41 m, fill ratio 0.786 ~ pi/4.
  a1 has 4 discs (a 56 m town core plus two 32 m and one 24 m); c1 has 48/36/36/32 m;
  b1 has 44/28/24/24 m. Safezone is essentially never on blocked ground here
  (a1 0.4 %, b1 0.0 %, c1 0.0 %).
- 5 of 18 maps write paint bytes above `0x07` (29.3 % of cells) -- the `0xC8`/`0xC9`
  "mountain" family. It is cosmetic editor bookkeeping, not a gameplay flag.

---

## Tells

These are the small conventions that make a map read as *empire field* rather than as
generic green terrain.

1. **Slot 1 is a road, painted in dirt.** A visible, looping, 4-6 m wide track web with
   T and Y junctions, painted with an ordinary field texture and flattened under itself.
   No paved road exists in the art. The paved `tile01` appears only as a ~0.2 % town plaza.
2. **A river and a beach.** 28.9 % water cover, and the beach slots (14/16) carry 10 % of
   the ground. `beach sand 01` has 100 % of its tiles within 4 m of water and clump 7.80
   -- the shoreline is one of the few genuinely *solid* regions in the palette.
3. **The ground is stipple, not regions.** Half of the base texture's connected
   components are a single 1 m tile; `grass 02` covers 10.7 % of a1 with clump 3.81 and
   **1 % non-edge**. It exists only as noise sprinkled through `grass 01`.
4. **Species mixing, not rotation jitter.** Eight to twelve b-family SpeedTrees on one
   map. Two thirds of tree records have roll exactly 0 (`Beech4` 66.6 %, `Pagoda1`
   60.7 %, `MontereyCypress5` 78.0 %); the rest are multiples of 15 deg. Variety comes from
   the species list and from `TreeSize`/`TreeVariance`, never from random yaw.
5. **Cliffs are `stone01`/`stone02`, and they are steep.** Mean slope 38 deg under both,
   75 % of their tiles above 20 deg. `stone01` alone is 16.7 % of a1's ground and is the
   most-painted texture in the whole archetype (14.4 %).
6. **One house family per map.** The town is inside the overworld tile, not a separate
   map -- a1/b1/c1 each embed their capital in a 4x5 field.
7. **Camp set-pieces.** A campfire building with a flame effect 7 cm away, chairs, a
   tent and crates inside a 15 m circle. That single motif appears across the whole
   corpus and is the strongest co-occurrence signal in it.
8. **A short blue fog.** Fog far 20,000 cm and a `#1849A8` -> `#D9E6FF` sky. Anything
   longer starts to read as `desert` or `darkforest_coast`.

---

## Sources

`corpus-overview.md` sec 2, sec 4 ; `catalog/map-taxonomy.json` `archetypes.field_empire`,
`maps.*` ; `catalog/stats-terrain.json` `by_archetype.field_empire` ;
`catalog/stats-tiles.json` `by_archetype.field_empire` ;
`textures.md` sec 4, sec 6 `field_empire` ; `catalog/textures.json`
`texturesets["metin2_a1.txt"]`, `archetype_recipes.field_empire` ;
`environments.md` sec 5, sec 6 `field_empire` ; `catalog/environments.json`
`archetype_presets.field_empire` ; `placement.md` sec 1-sec 8 ;
`catalog/stats-objects.json` `by_archetype.field_empire`, `by_crc` ;
`catalog/affinity.json` `by_archetype.field_empire`, `by_crc`, `by_family` ;
`attributes.md` sec 4, sec 7, sec 8, sec 10 ; `catalog/stats-attr.json`
`archetypes.field_empire`, `maps.*` ; `catalog/roads.json`
`by_archetype.field_empire` -- **road figures are pooled and unfiltered**; the miner
itself rejected 29 of 73 "road" maps as terrain ribbons after these aggregates were
produced (`roads.json.by_archetype_caveat`). Treat road grammar as indicative.

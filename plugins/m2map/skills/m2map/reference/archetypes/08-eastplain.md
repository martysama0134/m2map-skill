# 08 -- `eastplain`

**Eastplain and empire castle.** 4 maps, 50 sectors, 1,507 object placements.
Reference map `metin2_map_eastplain_01`.

---

## Identity

A ruined giants' plain: broken twin pillars, dead trees, ant hills and long fence runs
scattered over rolling grass and rock, far from any road, under a flat warm-dusk sky
where the light comes from the fog rather than from the sun.

Two measurements identify it. First, **86.5 % of placements are Building** -- the most
building-dominated outdoor archetype in the corpus, and yet there is no settlement:
`zone/eastplain` at 932 records is architecture-as-scenery. Second, the palette
`metin2_eastplain.txt` shops across five older art packs -- `dawnmistwood`, `mtthunder`,
`a/stone`, `b/**`, `empirewar/tille` -- rather than shipping its own, which makes it the
one archetype whose art you cannot identify from a single folder name.

The `zone/eastplain` family is used by nobody else in the corpus.

---

## Reference maps

| Map | Size | Sectors | Textureset | Environment | Objects | CRCs | `ViewRadius` |
|---|---|---|---|---|---|---|---|
| **`metin2_map_eastplain_01`** (reference) | 4x5 | 20 | `metin2_eastplain.txt` | `Eastplain_01.msenv` | 728 | 180 | 256 |
| `metin2_map_eastplain_02` | 3x6 | 18 | `metin2_eastplain.txt` | `Eastplain_02.msenv` | 342 | 43 | 256 |
| `metin2_map_eastplain_03` | 4x2 | 8 | `metin2_eastplain.txt` | `Eastplain_03.msenv` | 264 | 51 | 128 |
| `metin2_map_empirecastle` | 2x2 | 4 | `metin2_map_empirecastle.txt` | `empirecastle.msenv` | 173 | 34 | 128 |

- **Typical and flagship size 4x5.** All four have their own terrain.
- All four ship `sungma_attr.txt`; `empirecastle` additionally ships a **loose
  `a1.msenv` in its map root** that it never loads -- its `setting.txt` names
  `empirecastle.msenv` (`corpus-overview.md` sec 5.3, `environments.md` sec 8).
- `eastplain_01` and `eastplain_03` ship the edge-blend minimap set.
- `eastplain_01.msenv` and `eastplain_03.msenv` are **byte-identical**;
  `empirecastle.msenv` is `eastplain_01.msenv` with `Fog.Enable` flipped to 0 and the
  ambient nudged.

---

## Terrain

`style: sculpted`, all four. `stats-terrain.json` `by_archetype.eastplain`, 4 maps,
50 sectors.

| Quantity | Value |
|---|---|
| `height_range_cm` | **2,947.5** - 29,762.0; p5 14,001, **p50 17,366**, p95 22,883 |
| Relief per sector | p25 5,065 cm, **p50 6,972 cm**, p75 9,849 cm, p90 12,935 cm |
| `slope_p50` | **11.4 deg** |
| `slope_p95` | **62.6 deg** (p75 35.5 deg, p90 54.8 deg, mean 20.5 deg) |
| `flat_fraction` (< 5 deg) | **0.328** (< 2 deg 0.185, < 10 deg 0.472, < 20 deg 0.620) |
| `roughness` (abs Laplacian r=1) | p50 19.5 cm, p90 192.5, p99 626.5 |
| Local std 3x3 | p50 36.5 cm, p90 224.5 cm |
| Water cells | **26.6 %** |
| Blocked cells | 73.3 % |

Look at `slope_at_50pct_blocked_deg` = **4.16**, the lowest in the corpus. That is the
first sign that this archetype's collision is not driven by terrain shape -- see the attr
section. Otherwise the geometry is unremarkable: gentle plain (p50 11 deg) with steep edges
and a quarter of it water.

---

## Textureset recipe

**`metin2_eastplain.txt`**, 17 slots, measured on `eastplain_01/02/03`
(`textures.json` `texturesets["metin2_eastplain.txt"]`). `weight` = measured
`ground_share`; sums to 1.000.

| slot | role | path | U/V | repeat | weight |
|---|---|---|---|---|---|
| 1 | `cliff` | `d:/ymir work/terrainmaps/dawnmistwood/dawnmistwood_rock001.dds` | 2/2 | 16.0 m | 0.149 |
| 2 | `cliff` | `d:/ymir work/terrainmaps/mtthunder/mtthunder_stone01.dds` | 1/1 | 32.0 m | 0.096 |
| 3 | `cliff` | `d:/ymir work/terrainmaps/a/stone/stone01.dds` | 3/3 | 10.7 m | 0.111 |
| 4 | `accent` | `d:/ymir work/terrainmaps/dawnmistwood/dawnmistwood_sand001.dds` | **3/2** | 10.7 m | 0.002 |
| 5 | `mid` | `d:/ymir work/terrainmaps/b/field/field 03_01.dds` | 3/3 | 10.7 m | 0.039 |
| 6 | `cliff` | `d:/ymir work/terrainmaps/b/stone/stone02.dds` | 1/1 | 32.0 m | 0.015 |
| 7 | `mid` | `d:/ymir work/terrainmaps/dawnmistwood/dawnmistwood_grass002.dds` | **3/2** | 10.7 m | 0.026 |
| 8 | `mid` | `d:/ymir work/terrainmaps/dawnmistwood/dawnmistwood_grass001.dds` | 2/2 | 16.0 m | 0.109 |
| 9 | `shore` | `d:/ymir work/terrainmaps/b/beach/beach sand 01.dds` | 1/1 | 32.0 m | 0.063 |
| 10 | `base` | `d:/ymir work/terrainmaps/mtthunder/mtthunder_grass02.dds` | 2/2 | 16.0 m | 0.126 |
| 11 | `mid` | `d:/ymir work/terrainmaps/b/field/field 04.dds` | 1/1 | 32.0 m | 0.059 |
| 12 | `shore` | `d:/ymir work/terrainmaps/dawnmistwood/dawnmistwood_feild002.dds` | 4/4 | 8.0 m | 0.143 |
| 13 | `mid` | `d:/ymir work/terrainmaps/dawnmistwood/dawnmistwood_field001.dds` | 4/4 | 8.0 m | 0.027 |
| 14 | `accent` | `d:/ymir work/terrainmaps/mtthunder/mtthunder_field01.dds` | 4/4 | 8.0 m | 0.013 |
| 15 | `mid` | `d:/ymir work/terrainmaps/mtthunder/mtthunder_field04.dds` | 4/4 | 8.0 m | 0.015 |
| 16 | `accent` | `d:/ymir work/terrainmaps/dawnmistwood/dawnmistwood_grass004.dds` | 4/4 | 8.0 m | 0.007 |
| 17 | `accent` | `d:/ymir work/terrainmaps/empirewar/tille/empire_tile02.dds` | 4/4 | 8.0 m | 0.001 |

**No single texture reaches 15 %.** Seventeen live slots, base share 0.252 median,
`coverage_entropy_bits` median **2.97** -- the highest of any archetype. This is a mosaic,
not a carpet.

Slots 4 and 7 carry `UScale 3 / VScale 2` -- **two of the seven anisotropic entries in the
entire corpus** (`textures.md` sec 6 `eastplain`). If you are reproducing this palette
faithfully, keep them unequal.

`metin2_map_eastplain_02` **writes tile indices 18 and 19 into this 17-slot palette**
(`textures.md` sec 7.3). Those bytes render the error texture. Do not reproduce it.

**No road slot.** The `path` role does not appear in either eastplain palette; the road
detector's ribbons here are painted with ordinary ground textures. If you need a
corridor, use slot 12 `dawnmistwood_feild002.dds` (14.3 %, the archetype's most solid
non-cliff) or slot 13.

**How the archetype paints** (`stats-tiles.json` `by_archetype.eastplain`):
role share rock 37.9 %, dirt 28.0 %, grass 27.3 %, sand 6.0 %, paved 0.9 %; base role
`rock` in all 4; median 16.5 slots used of 17 declared (unused fraction 0.029);
**`stipple_pairs_per_map` median 0** -- all three eastplain maps are on
`stats-tiles.json.maps_with_no_stipple`; `mean_run_h_of_base` median 7.8 tiles;
`singleton_fraction_of_base` 0.611.

Like `flame_field` and `darkforest_coast`, **`eastplain` paints regions, not dither** --
but it paints seventeen of them.

---

## Environment

**Canonical `eastplain_01.msenv`** -- cluster C03 `warm_dusk`. Four maps, four envs, but
three of them are the same idea (`environments.json` `archetype_presets.eastplain`).

| Parameter | Observed over all 4 |
|---|---|
| `Fog.Enable` | 1 x3, **0 x1** (`empirecastle`) |
| `Fog.NearDistance` | 5,000 - 15,000 cm (median 5,000) |
| `Fog.FarDistance` | 25,000 - 50,000 cm (median 25,000) |
| `Fog.Color` | `#3D5A5D` / `#3D595D` (eastplain), `#280F2F` (eastplain_02) |
| `Background.Ambient` | `#4B4B58`, `#493F52`, `#565680` (level 0.285 - 0.392) |
| `Character.Ambient` | Background + 0.15 |
| `Background.Diffuse` | `#CBC9C0`, `#BCBAC1`, `#FBEBA8`; warmth -0.020 to 0.326 |
| sun elevation / azimuth | 39.3 - 68.6 deg / **35.1 deg** and 266.7 deg |
| `Direction` | `0.772081 0.044283 -0.633979`, `-0.210052 -0.298942 -0.930866` |
| Gradient | **Upper 3 / Lower 1 x4** |
| Sky zenith -> horizon -> nadir | `#315480` / `#503D2A` -> `#3D5A5D` / `#434561` -> `#353A44` / `#3D595D` / `#434561` |
| Cloud | `clouds_zone01.tga` (200000 / 4 / 0.004) or **`clouds_zone10.tga` (2,900,000 / 20 / 0.001)** |
| Skybox faces | **`eastplain`, `smhtower`** -- `eastplain_02` is the only map at render mode 1 |

Two things to reproduce. **The gradient is nearly flat**: cluster C03's mean zenith
`#5B514D` versus horizon `#58514F` (`environments.md` sec 5). The light comes from the fog,
not from the sky -- which is why `empirecastle` can disable fog entirely and still look
like the same place.

And `eastplain_02.msenv` is a genuine one-off: the only file in the corpus using the
`smhtower` face set, `CloudScale 2,900,000` and `CloudTextureScale 20`. If you want the
weird sky, take that file; if you want the archetype, take `eastplain_01.msenv`.

Note also `sun_azimuth 35.1 deg` on `empirecastle` -- a north-east sun with a
**`Direction.z` of -0.93**, nearly straight down (elevation 68.6 deg).

---

## Object palette

**Density 4.60 obj/ha = 0.046 per 100 m^2 = 30.1 per sector**, 210 distinct CRCs across
327.68 ha. Mix: **Building 86.5 %**, Tree 12.7 %, Effect 0.7 %, DungeonBlock 0.1 %.

Family budget:

| Family | n | per ha | NN same-family p25/p50/p75 (cm) | Clark-Evans R |
|---|---|---|---|---|
| `zone/eastplain` | 932 | 2.84 | 563 / **840** / 1,635 | 0.439 |
| `tree/b1` | 132 | 0.40 | 1,225 / 2,476 / 5,146 | 0.497 |
| `zone/dungeon/dawnmistwood_dungeon` | 127 | 0.39 | 558 / 1,034 / 1,939 | 0.297 |
| `zone/eastplain/obj` | 108 | 0.33 | 109 / 515 / 1,597 | 0.101 |
| `zone/b/obj` | 53 | 0.16 | 320 / 657 / 1,030 | 0.147 |
| `tree/b3` | 48 | 0.15 | 2,428 / 3,305 / 5,795 | 0.383 |
| `zone/ghost/obj` | 41 | 0.13 | 208 / 441 / 800 | 0.060 |
| `zone/eastplain/building` | 32 | 0.10 | 2,989 / 3,750 / 5,295 | 0.353 |

Trees are decoration only -- 192 records, 12.7 %, at 25-33 m spacing.

### Tier table (directly usable as `MapSpec.objects`)

`density` per 100 m^2; `spacing_cm` = NN(same CRC) p5; `max_slope` = per-CRC slope p95;
`road_clearance_cm` = per-CRC d(road) p25; `height_bias` = (bias p25, bias p75).
`on_tiles` indexes the 17-slot palette above.

| tier | crc | name | density | spacing_cm | on_tiles | max_slope | road_clear_cm | height_bias | water_m |
|---|---|---|---|---|---|---|---|---|---|
| signature | 3967461885 | `double_01` (Building, `zone/eastplain`) | 0.00220 | 629 | 1,2,8,10 | 33 | 282 | (-273, -17) | 111/234/372 **(111, inf)** |
| signature | 732124720 | `double_02` (Building, `zone/eastplain`) | 0.00198 | 307 | 1,2,8,10 | 31 | 400 | (-91, 0) | 85/160/342 **(85, inf)** |
| signature | 3999910207 | `double_04` (Building, `zone/eastplain`) | 0.00198 | 647 | 1,2,8,10 | 45 | 282 | (-31, 0) | 101/181/323 **(101, inf)** |
| signature | 2221821084 | `double_03` (Building, `zone/eastplain`) | 0.00183 | 417 | 1,2,8,10 | 32 | 282 | (-15, 5) | 78/157/287 **(78, inf)** |
| signature | 513101969 | `gaint_fence05_d` (Building, `zone/eastplain`) | 0.00162 | 900 | 5,8,10,11 | 26 | 565 | (0, 34) | 36/100/315 **(36, inf)** |
| signature | 4171822572 | `gaint_fence04_d` (Building, `zone/eastplain`) | 0.00085 | 655 | 7,8,10 | 30 | 1827 | (-72, 0) | 49/69/192 (0, inf) |
| signature | 2788543263 | `gaint_pillar00_d` (Building, `zone/eastplain`) | 0.00085 | 617 | 5,8,10,14 | 49 | 400 | (0, 51) | 52/156/363 **(52, inf)** |
| filler | 921849695 | `deadwood_05` (Building, `zone/eastplain`) | 0.00092 | 4997 | 2,3,10,11 | 47 | 400 | (-284, 0) | 202/314/393 **(202, inf)** |
| filler | 1502496769 | `deadwood_01` (Building, `zone/eastplain`) | 0.00082 | 1983 | 1,2,5,10 | 52 | 241 | (-62, 0) | 82/234/300 **(82, inf)** |
| accent | 196033080 | `anthill_05` (Building, `zone/eastplain`) | 0.00085 | 8902 | 2,3,10,11 | 53 | 659 | (-275, -31) | 208/294/430 **(208, inf)** |

`water_m` = observed distance to the nearest water, p25/p50/p75 in metres (`affinity.json` `by_crc[crc].d_water_cm`; `~` = the family's figure where the CRC has none). The bold `(min, inf)` is the suggested `MapSpec.water_distance_m` for species that measurably avoid water. A species that tolerates it gets no constraint; give oasis or shore decoration a `(0, max)` band instead -- do NOT try to pin it to the shore texture, which is a stipple and covers only a handful of tiles.


`double_01..04` are the archetype's silhouette: broken twin pillars, 262 records
combined, planted 8-14 m apart on grass and rock. All four have **roll zero-share of
0.00-0.17 and yaw non-zero in 12-38 % of records with pitch non-zero in 8-23 %** -- they
are *leaning* ruins, not upright buildings. That places them with the corpus's debris
families (`placement.md` sec 1.1), not with its architecture.

`gaint_fence05_d` runs at a fixed ~1,000 cm pitch (NN p5 900, p50 1,012) -- a wall kit.

---

## Placement rules

**Ground affinity** (`affinity.json` `by_archetype.eastplain`, n = 1,507). Object slope
p50 comes out at 8-14 deg for the ruin set. The `zone/eastplain` family sits on grass
50-61 %, rock 28-42 %, field 3-17 %, and **98.2 % of its records are on a cell painted
blocked** (`placement.md` sec 4.3).

**Positive rules**

1. **Everything is far from the road.** Buildings d(road) p50 **3,542 cm**, trees
   **6,804 cm** (`placement.md` sec 5) -- the largest setbacks of any outdoor archetype
   except `trent_forest`. This is wilderness ruin. Do not snap the ruins to the path web.
2. **Lean the pillars.** Yaw and pitch non-zero on `double_01..04` and `deadwood_*`; roll
   almost never zero. Sink the big ones 90-280 cm.
3. **Fences run at a 10 m pitch.** `gaint_fence04_d` / `gaint_fence05_d` / `gaint_pillar00_d`
   at NN p50 840-1,012 cm, yaw exactly 0 in 100 % of records -- the fences do *not* tilt
   even though the pillars do.
4. **Roads, where they exist, are dense and looped.** 12.52 junctions/km and 5.28
   loops/km on `eastplain_01` -- the busiest network measured -- with a **10 m blend band**.
   But almost nothing is placed on them.
5. **Ant hills are landmarks**: `anthill_05`, NN p5 8,902 cm, on 21 deg ground, sunk 88 cm.

**Negative rules**

- **The entire `zone/eastplain` set is never on `(none)`, lava, other, sand, snow or
  tile.** Grass, rock and field only. That is seven of the ten ground classes excluded,
  uniformly across every member.
- **No `tree/n2`, no `tree/n1`** (1 record), no desert or winter flora.
- **No settlement.** 32 `zone/eastplain/building` records in four maps.
- Do not paint pavement: `paved` is 0.9 % of the ground and slot 17
  (`empire_tile02.dds`) covers 0.09 %.
- **No dither.** All three eastplain maps are stipple-free.

---

## Attr policy

`attr_style: slope_driven` on all four; footprint policy `painted` on all four.

| Setting | Value |
|---|---|
| `attr_style` | `slope_driven` |
| `block_slope_deg` | **11** (fitted 10, 11, 11, 13) -- the lowest outdoor threshold in the corpus |
| `border_band_m` | **152 m** median seal; strict bands 17-41 m |
| `safezone_regions` | 2 components, median **13,220 m^2**, bbox edge 145 m |

Block budget over 2,373,992 cells: slope 64.5 %, **water 23.0 %**, out-of-bounds 7.5 %,
object halo 4.3 %, residual 0.8 %. 72.4 % of cells blocked.

- **Water is the second-largest cause of block at 23.0 %** -- the highest share of any
  archetype (`field_empire` is 16.9 %). On `eastplain_01` water alone accounts for
  **34.4 %** of block. A quarter of the map is water and almost all of it blocks.
- **But the water *flag* is barely painted.** 4 maps have wet cells (872,868 of them),
  2 paint the flag, and Jaccard is 0.067. Follow the corpus: block the submerged cells,
  leave `ATTRIBUTE_WATER` mostly clear.
- **The fitted slope threshold is 11 deg**, roughly half the corpus `slope_driven` optimum
  of 20 deg, and `slope_at_50pct_blocked_deg` is 4.16. This map blocks aggressively at low
  slope. Reproduce it: the eastplain is a *narrow* walkable ribbon through a mostly
  blocked plain.
- **94.3 % of Building and 91.1 % of Tree centre cells are blocked.** Stamp everything,
  trees included.
- **14.8 % of all block cells sit within 12 m of a placement** -- second only to
  `darkforest_coast`. The ruins carve their own collision.
- No paint bytes above `0x07`; 6 distinct attr bytes.
- Safezone: 2 components, one circle-brush and one rectangular fill, median 13,220 m^2,
  145 m bbox -- much larger than the town discs of `field_empire`.
- Rim slope median 22 deg versus interior 8 deg; all four sealed strict.

---

## Tells

1. **86.5 % Building, and not one town.** Ruins as scenery.
2. **`double_01..04`.** Broken twin pillars, 262 records, leaning on all three axes.
3. **Seventeen live slots, entropy 2.97, no dither.** The most varied and least
   stippled ground in the corpus.
4. **A borrowed palette.** `dawnmistwood` + `mtthunder` + `a/stone` + `b/**` +
   `empirewar/tille`. No `eastplain/` terrain folder exists.
5. **Two anisotropic UV entries** (`UScale 3 / VScale 2` on slots 4 and 7) -- two of the
   corpus's seven.
6. **A flat sky.** Gradient Upper 3, zenith and horizon within a few percent luminance
   of each other; `empirecastle` turns fog off entirely and looks the same.
7. **Objects 35-68 m from the nearest road.**
8. **Fences upright, pillars leaning.** Yaw is exactly 0 in 100 % of fence records and
   non-zero in 12-38 % of pillar records.
9. **A 4 deg block threshold and 23 % of block from water.** This plain is mostly not
   walkable.
10. **`sungma_attr.txt` in every map root.**

---

## Road grammar confidence

**2 of 3 road-bearing maps here are confirmed roads (67%.)** The rest are
`terrain_ribbon` or `ambiguous` -- soft-edged regions the corridor detector picks
up as tracks. `roads.json.by_archetype` is now filtered to the confirmed set, but
with n=2 the width, curvature and junction figures are **indicative, not
measured**. Treat them as a starting point and check the result by eye.

The path-texture identification and the `d(road)` setbacks are unaffected: both
come from per-slot and per-CRC statistics, not from corridor detection.

## Sources

`corpus-overview.md` sec 5.3 ; `catalog/map-taxonomy.json` `archetypes.eastplain`,
`maps.*` ; `catalog/stats-terrain.json` `by_archetype.eastplain` ;
`catalog/stats-tiles.json` `by_archetype.eastplain`, `maps_with_no_stipple` ;
`textures.md` sec 6 `eastplain`, sec 7.3 ; `catalog/textures.json`
`texturesets["metin2_eastplain.txt"]` ; `environments.md` sec 5 C03, sec 6 `eastplain`, sec 8 ;
`catalog/environments.json` `archetype_presets.eastplain` ; `placement.md` sec 1.1, sec 4.3,
sec 5, sec 8 ; `catalog/stats-objects.json` `by_archetype.eastplain`, `by_crc` ;
`catalog/affinity.json` `by_archetype.eastplain`, `by_crc` ;
`attributes.md` sec 4, sec 5, sec 6, sec 8, sec 10 ; `catalog/stats-attr.json`
`archetypes.eastplain`, `maps.*` ; `catalog/roads.json` `by_archetype.eastplain` --
pooled and unfiltered, see `roads.json.by_archetype_caveat`.

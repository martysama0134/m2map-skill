# 15 -- `trent_forest`

**Trent night forest.** 2 maps, 20 sectors, 608 object placements. Reference map
`metin2_map_trent02`.

---

## Identity

A night forest read as sparse silhouettes: **the most widely spaced temperate forest in
the corpus** (`tree/b1` NN p50 **2,729 cm** against `field_empire`'s 1,686) and the
**furthest anything is placed from a road in any outdoor archetype** (trees at 10,889 cm,
buildings at 7,025 cm -- `placement.md` sec 8).

The terrain palette `terrainmaps/trent/{field,grass,stone,tile}` is used by nothing else.
It follows the standard folder order and carries **the highest `UScale` band in the
corpus**: `grass 02`, `grass 03` and `stone01` all sit at **10**, a 3.2 m repeat. The
ground is finely detailed and the trees are far apart -- the inverse of every other
forest here.

The two environments are wildly different from each other and both are one-offs.
`trent.msenv` is **the only file in the corpus whose light direction points slightly UP**
(sun elevation -1.5 deg -- the sun is below the horizon); `trent02.msenv` is a pink-lit
oddity (ambient `#E37E7E`, diffuse `#8F4661`) that clusters with nothing
(`environments.md` sec 6 `trent_forest`).

---

## Reference maps

| Map | Size | Sectors | Textureset | Environment | Objects | CRCs |
|---|---|---|---|---|---|---|
| **`metin2_map_trent02`** (reference) | 3x3 | **16** | `metin2_map_trent.txt` | `trent02.msenv` | 413 | 51 |
| `metin2_map_trent` | 2x2 | 4 | `metin2_map_trent.txt` | `trent.msenv` | 195 | 49 |

- **Typical and flagship size 3x3.**
- **`metin2_map_trent02` declares `MapSize 3 3` but ships a full 4x4 = 16 sector
  directories.** The extra folders are dead data a loader never reads
  (`corpus-overview.md` sec 5.5). Do not reproduce it, but do handle it when walking.
- Two maps is a thin sample. Everything below is n = 2 at the map level; the per-CRC and
  per-family figures are pooled across the whole corpus and are solid.

---

## Terrain

**Mixed**: `slope_driven` on `metin2_map_trent`, `painted_box` on `metin2_map_trent02`.
`stats-terrain.json` `by_archetype.trent_forest`, 2 maps, 20 sectors.

| Quantity | Value |
|---|---|
| `height_range_cm` | 7,448.5 - 26,834.5; p5 12,316.5, **p50 15,870.0**, p95 19,899.5 |
| Relief per sector | p25 6,946 cm, **p50 8,446 cm**, p75 9,685 cm, p90 11,682 cm |
| `slope_p50` | **4.5 deg** |
| `slope_p95` | **71.5 deg** (p75 28.3 deg, p90 63.3 deg, mean 17.7 deg) |
| `flat_fraction` (< 5 deg) | **0.512** (< 2 deg 0.430, < 10 deg 0.614, < 20 deg 0.713) |
| `roughness` (abs Laplacian r=1) | p50 9.5 cm, p90 258.5, p99 1,025.5 |
| Local std 3x3 | p50 15.5 cm, p90 325.5 cm |
| Water cells | **15.7 %** |
| Blocked cells | 66.2 % |

Half the map is under 5 deg and a quarter is over 28 deg: a broad gentle forest floor with
steep wooded banks. Roughness p50 of 9.5 cm is low -- the floor is smooth, and the visual
complexity comes from the 3.2 m texture repeat and from the trees, not from the
heightmap.

---

## Textureset recipe

**`metin2_map_trent.txt`**, 11 slots, on both maps (`textures.json`
`texturesets["metin2_map_trent.txt"]`). A pure single-family palette from
`terrainmaps/trent/{field,grass,stone,tile}` in folder order. `weight` = measured
`ground_share`; sums to 1.000.

| slot | role | path | U/V | repeat | weight |
|---|---|---|---|---|---|
| 1 | `mid` | `d:/ymir work/terrainmaps/trent/field/field 01.dds` | 5/5 | 6.4 m | 0.034 |
| 2 | `mid` | `d:/ymir work/terrainmaps/trent/field/field 02.dds` | 6/6 | 5.3 m | 0.056 |
| 3 | `mid` | `d:/ymir work/terrainmaps/trent/field/field 03.dds` | 5/5 | 6.4 m | 0.159 |
| 4 | `mid` | `d:/ymir work/terrainmaps/trent/grass/grass 01.dds` | 6/6 | 5.3 m | 0.069 |
| 5 | `accent` | `d:/ymir work/terrainmaps/trent/grass/grass 02.dds` | **10/10** | **3.2 m** | 0.008 |
| 6 | `mid` | `d:/ymir work/terrainmaps/trent/grass/grass 03.dds` | **10/10** | **3.2 m** | 0.200 |
| 7 | `base` | `d:/ymir work/terrainmaps/trent/stone/stone01.dds` | **10/10** | **3.2 m** | 0.395 |
| 8 | `cliff` | `d:/ymir work/terrainmaps/trent/stone/stone02.dds` | 6/6 | 5.3 m | 0.073 |
| 9 | `cliff` | `d:/ymir work/terrainmaps/trent/stone/stone03.dds` | 6/6 | 5.3 m | 0.002 |
| 10 | `unused` | `d:/ymir work/terrainmaps/trent/tile/tile01.dds` | 5/5 | 6.4 m | 0.000 |
| 11 | `path` / road | `d:/ymir work/terrainmaps/trent/tile/tile02.dds` | 5/5 | 6.4 m | 0.004 |

**`stone01` is the forest floor, not rock.** 39.5 % of the ground at clump 7.34 despite
the "stone" name -- another instance of the filename trap (`textures.md` sec 3, sec 6
`trent_forest`). The measured mean RGB of the `A/stone` family is a tan dirt; the same
applies here.

**`UScale 10` on the three highest-coverage slots** (`grass 02`, `grass 03`, `stone01`)
gives a 3.2 m repeat -- the tightest ground detail in the corpus. Combined with the low
roughness and the sparse trees, that is what makes the floor read as leaf litter rather
than as terrain.

`trent/tile/tile02.dds` (slot 11) is the road: 0.37 % of the ground. Set
`RoadSpec.tile_index = 11` -- but note the road here is vestigial (see Placement).

**How the archetype paints** (`stats-tiles.json` `by_archetype.trent_forest`):
role share rock 47.0 %, grass 27.7 %, dirt 25.0 %, **paved 0.4 %**; base role `rock` x2;
9.5 slots used of 11; base share 0.351; `coverage_entropy_bits` 2.30;
**4.5 dither-only slots per map carrying 32.3 % of tiles**; 3 stipple pairs,
`stipple_same_family_share` 0.500; `mean_run_h_of_base` 16.1 tiles.

---

## Environment

**Two maps, two one-off environments.** `trent.msenv` is C06 `ember_orange`;
`trent02.msenv` is C20, a singleton that clusters with nothing
(`environments.json` `archetype_presets.trent_forest`).

**Canonical `trent.msenv`** (used by `metin2_map_trent`):

| Parameter | Observed across both |
|---|---|
| `Fog.Enable` | 1 x2 |
| `Fog.NearDistance` | 0 - 500 cm (median 250) |
| `Fog.FarDistance` | **15,000 - 18,000 cm** (median 16,500) -- the shortest in the corpus |
| `Fog.Color` | `#200E0E`, `#250F10` -- hue 0/357 deg, sat 0.56-0.60, **value 0.125-0.145** |
| `Background.Ambient` | `#3F504F` (trent) / **`#E37E7E`** (trent02); level 0.290 - 0.626 |
| `Character.Ambient` | Background + 0.15 (`trent02.msenv` overflows past 1.0: `1.040196 0.644118 0.644118`) |
| `Background.Diffuse` | `#FFFFFF` (trent) / **`#8F4661`** (trent02) |
| **sun elevation / azimuth** | **-1.5 deg** (trent) / 41.9 deg (trent02); az 204.3 deg, 232.5 deg |
| `Direction` | **`0.411789 0.910903 0.026193`** (trent -- positive Z, sun below horizon) / `0.590855 0.453329 -0.66737` |
| Gradient | **Upper 1 / Lower 1 x2** |
| Sky zenith -> horizon -> nadir | `#001326` -> `#2F1500` -> **`#FF0000`** (trent); `#C88190` -> `#533B15` -> `#FFFFFF` (trent02) |
| Cloud | `clouds_zone05.tga`, 200000, texture scale 4 / **6**, speed 0.001, height **4500** / 30000 |
| Skybox faces | none ; `Filter.Enable` 0 |

Three things nothing else in the corpus does:

1. **The sun is below the horizon.** `trent.msenv` is the only file with a positive
   `Direction.z` -- 103 of 104 have z < 0 (`environments.md` sec 4.5). Elevation -1.5 deg.
2. **`FarDistance 15,000-18,000 cm`.** The shortest draw budget shipped. Combined with
   fog value 0.13, the forest fades to near-black at 150 m.
3. **A pure `#FF0000` nadir** on `trent.msenv` and a `#FFFFFF` one on `trent02.msenv`.

Pick `trent.msenv` for the night forest. `trent02.msenv` is a genuine one-off and should
be treated as a reference, not a preset.

---

## Object palette

**Density 4.64 obj/ha = 0.0464 per 100 m^2 = 30.4 per sector**, 74 distinct CRCs across
131.07 ha. Mix: **Tree 62.5 %**, Building 37.0 %, Effect 0.5 %.
Clark-Evans R = **0.698** -- the least clustered outdoor archetype after `flame_field`.

| Family | n | per ha | NN same-family p25/p50/p75 (cm) | Clark-Evans R |
|---|---|---|---|---|
| `tree/b1` | 303 | 2.31 | 2,039 / **2,729** / 3,614 | **0.888** |
| `zone/b/obj` | 216 | 1.65 | 1,566 / **2,659** / 4,191 | **0.767** |
| `tree/b3` | 77 | 0.59 | 2,136 / **4,982** / 6,998 | **0.780** |
| `zone/n/milgyo` | 6 | 0.05 | 1,339 / 3,253 / 5,472 | -- |
| `effect/background` | 3 | 0.02 | 38,902 | -- |

Those R values are the highest family-level figures in the corpus outside `effect`
families. **A trent forest is nearly evenly spread**, which is the opposite of every
other vegetation archetype.

### Tier table (directly usable as `MapSpec.objects`)

`density` per 100 m^2; `spacing_cm` = NN(same CRC) p5; `max_slope` = per-CRC slope p95;
`road_clearance_cm` = per-CRC d(road) p25; `height_bias` = (bias p25, bias p75).
`on_tiles` indexes the 11-slot palette above.

| tier | crc | name | density | spacing_cm | on_tiles | max_slope | road_clear_cm | height_bias | water_m |
|---|---|---|---|---|---|---|---|---|---|
| signature | 2376089798 | `Pagoda2` (Tree, `tree/b1`) | 0.00435 | 2397 | 3,4,6,7 | 47 | 600 | (-273, -20) | 18/61/181 (0, inf) |
| signature | 3455398876 | `Beech3` (Tree, `tree/b3`) | 0.00397 | 2662 | 3,4,6,7 | 41 | 400 | (-60, -5) | 22/71/168 (0, inf) |
| signature | 1107711305 | `Pagoda3` (Tree, `tree/b1`) | 0.00381 | 1503 | 3,4,6,7 | 47 | 565 | (-152, -20) | 17/68/178 (0, inf) |
| signature | 3689520799 | `Beech4` (Tree, `tree/b1`) | 0.00381 | 2025 | 3,4,6,7 | 45 | 282 | (-91, -9) | 27/64/143 (0, inf) |
| signature | 569394331 | `Pagoda1` (Tree, `tree/b1`) | 0.00374 | 1709 | 3,4,6,7 | 47 | 565 | (-358, -25) | 14/75/187 (0, inf) |
| filler | 865570388 | `general_obj_stone10` (Building, `zone/b/obj`) | 0.00282 | 1001 | 1,3,6,7 | 30 | 0 | (-100, -20) | 26/56/133 (0, inf) |

`water_m` = observed distance to the nearest water, p25/p50/p75 in metres (`affinity.json` `by_crc[crc].d_water_cm`; `~` = the family's figure where the CRC has none). The bold `(min, inf)` is the suggested `MapSpec.water_distance_m` for species that measurably avoid water. A species that tolerates it gets no constraint; give oasis or shore decoration a `(0, max)` band instead -- do NOT try to pin it to the shore texture, which is a stipple and covers only a handful of tiles.


The remaining `zone/b/obj` budget (216 records, 1.65/ha) is boulders -- the
`general_obj_stone0*` set, as in `field_valley`. Fill it from
`cooccurrence.json.companions_15m` around `general_obj_stone10`.

Only **three effect records in the whole archetype**, 389 m apart.

---

## Placement rules

**Positive rules**

1. **Space the trees at 27 m.** `tree/b1` NN p50 2,729 cm, `tree/b3` 4,982 cm. That is
   1.6x `field_empire` and 2.3x `snow_field`. A night forest reads as silhouettes with
   air between them.
2. **Put everything far from the road.** Trees d(road) p50 **10,889 cm**, buildings
   **7,025 cm** -- the largest setbacks in the corpus (`placement.md` sec 8). The `path` slot
   covers 0.37 % of the ground; there is barely a road to be near.
3. **Ground affinity is grass 50.8 % / field 44.1 %** (`placement.md` sec 8). Trees on the
   forest floor, not on the rock.
4. **Sink the trees** 45 cm (`b1`) and 35 cm (`b3`); the boulders 20-100 cm.
5. **Two thirds of tree rolls are exactly 0**, the rest multiples of 15 deg.
6. **Boulders, not props.** No crates, no fences, no camp: `zone/b/obj` here is the
   `general_obj_stone*` set.

**Negative rules**

- `tree/b1` never on lava or snow; `tree/b3` never on lava, sand, snow or tile;
  `general_obj_stone10` never on `(none)`, lava, other, sand, snow or tile
  (`affinity.json.by_crc`).
- **No `tree/n1`, `n2`, `b2`.** Only `b1` (303) and `b3` (77).
- **No settlement.** 2 `zone/c/building` records in two maps.
- **No plaza.** `paved` is 0.4 % of the ground and slot 10 (`tile01`) is dead.
- **No effects to speak of.** Three records.
- No DungeonBlock records.

---

## Attr policy

**Split**: `slope_driven` on `metin2_map_trent` (fitted 26 deg), `painted_box` on
`metin2_map_trent02` (fitted 22 deg). Footprint policy `painted` on both.

| Setting | Value |
|---|---|
| `attr_style` | `slope_driven` for a sculpted forest |
| `block_slope_deg` | **22-26**; use 24 as the archetype median, or 20 for the corpus rule |
| `border_band_m` | **167 m** median seal; strict bands 10-26 m |
| `safezone_regions` | 2 circle-brush stamps, median 2,584 m^2, bbox edge **56 m** |

Archetype block budget over 847,747 cells: slope 38.9 %, **water 21.3 %**,
out-of-bounds 35.0 %, object halo 3.7 %, residual 1.1 %. 64.7 % of cells blocked.

On `metin2_map_trent` alone it is **slope 92.5 %**, out-of-bounds 4.4 %, water 0.0 % --
one of the cleanest slope-driven maps in the corpus. The archetype's water and
out-of-bounds shares come entirely from `trent02`, which is `painted_box` and 24.5 %
water.

- **`metin2_map_trent02` has 206,124 wet cells in `water.wtr` and paints
  `ATTRIBUTE_WATER` on zero of them** (Jaccard 0.000). The water is blocked by the
  submerged predicate, not by the flag. Follow that.
- **85.8 % of Building centre cells blocked but only 30.3 % of Tree.** Stamp the
  boulders; leave the forest walkable.
- **Both maps write paint bytes above `0x07` on 65 % of the archetype's cells** -- the
  `0x80` family. `metin2_map_trent` is one of the 17 maps that would become fully
  impassable server-side under the naive `server_attr` recipe
  (`attributes.md` sec Discrepancies 3). Mask before writing.
- Safezone: 2 circle-brush components, 56 m bbox, fill 0.788 ~ pi/4 -- the standard
  editor brush print.
- Rim slope median 25 deg versus interior 10 deg; both sealed strict with a shallow band.

---

## Tells

1. **27 m between trunks.** The widest temperate spacing in the corpus, and family
   Clark-Evans R near 0.9 -- almost evenly spread.
2. **Everything 70-110 m from the nearest road.**
3. **`UScale 10` on three slots.** A 3.2 m ground repeat, the finest shipped.
4. **`stone01` is the forest floor at 39.5 %.**
5. **A sun below the horizon.** `trent.msenv`, elevation -1.5 deg, the only positive
   `Direction.z` in 104 files.
6. **Fog far 15,000-18,000 cm at value 0.13.** The shortest, darkest fog in the corpus.
7. **`GradientLevelUpper 1` with a `#FF0000` nadir.**
8. **Boulders, not clutter.** `general_obj_stone*` and nothing else in `zone/b/obj`.
9. **A single-family palette**, `terrainmaps/trent/**`, used by no other map.
10. **`trent02` ships 16 sectors for a declared 3x3.**

---

## Border occlusion

**Terrain ridge.** The outer 64 m sits **+738 cm** above the interior (corner ring -101 cm). Set `border_ridge_cm` near that and let the fog keep a clear foreground.

Scale the *width* to the map: the measurement ring is 64 m, which on a 1x1 map (256 m) would consume half the playable surface. Keep the lift, narrow the rise.

Measured over the outer 64 m against the interior; see `../taste.md` for the corpus-wide table and the two traps when building a rim.

## Sources

`corpus-overview.md` sec 4, sec 5.5 ; `catalog/map-taxonomy.json`
`archetypes.trent_forest`, `maps.*` ; `catalog/stats-terrain.json`
`by_archetype.trent_forest` ; `catalog/stats-tiles.json`
`by_archetype.trent_forest` ; `textures.md` sec 3, sec 6 `trent_forest` ;
`catalog/textures.json` `texturesets["metin2_map_trent.txt"]` ;
`environments.md` sec 4.5, sec 5 C06, sec 6 `trent_forest` ; `catalog/environments.json`
`archetype_presets.trent_forest` ; `placement.md` sec 5, sec 8 ;
`catalog/stats-objects.json` `by_archetype.trent_forest`, `by_crc` ;
`catalog/affinity.json` `by_archetype.trent_forest`, `by_crc` ;
`attributes.md` sec 4, sec 6, sec 7, sec 8, sec 10, sec Discrepancies ; `catalog/stats-attr.json`
`archetypes.trent_forest`, `maps.*`.

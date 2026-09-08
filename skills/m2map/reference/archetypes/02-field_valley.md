# 02 -- `field_valley`

**Green valley / three-way field (A-family terrain).** 4 maps, 76 sectors,
2,068 object placements. Reference map `map_a2`.

---

## Identity

A steep green valley cut by a braided road web, walled by tan-grey rock. It is the
sibling of `field_empire` and its exact complement: `field_empire` is the whole
`terrainmaps/b/` art pack, `field_valley` is the whole `terrainmaps/a/` pack, and the
Jaccard similarity of their texture sets is **0.00** -- a hard split with no shared
texture (`map-taxonomy.json` `archetypes.field_valley.evidence`).

You recognise it by three things. First, the ground is *rock*: 65.9 % of all painted
tiles resolve to the rock role, and `a/stone/stone01.dds` alone is 45.4 % of the ground
-- despite being, by measured colour, a tan dirt (mean RGB 159,135,112, `textures.md`
sec 4 naming trap). Second, the terrain is genuinely mountainous: slope p50 34.2 deg, more
than 2.5x `field_empire`. Third, the road web is everywhere -- both buildings *and*
trees have a median distance to road of **0 cm** (`placement.md` sec 8). Nothing here is
placed away from a path.

Only one palette (`metin2_A2.txt`) and one environment (`A2.msenv`) exist in the whole
archetype, and `map_a2` / `map_n_threeway` are byte-identical map *content* -- threeway
is a verbatim relocation of a2 by `BasePosition`. There is no interior variation to
sample; this archetype is one map.

---

## Reference maps

| Map | Size | Sectors | Textureset | Environment | Objects | Terrain |
|---|---|---|---|---|---|---|
| **`map_a2`** (reference) | 6x6 | 36 | `metin2_A2.txt` | `A2.msenv` | 961 | own |
| `map_n_threeway` | 6x6 | 36 | `metin2_A2.txt` | `A2.msenv` | 961 | own (byte-identical to a2) |
| `metin2_map_guild_01` | 2x2 | 4 | `metin2_A2.txt` | `A2.msenv` | 146 | own |
| `metin2_map_smhgate_threeway` | 6x6 declared | 0 | `metin2_A2.txt` | `A2.msenv` | 0 | `proxy:map_a2` |

- **Typical size 6x6** and **reference size 6x6** -- unusually, they agree. Sizes: 2x2 x1,
  6x6 x3.
- `metin2_map_smhgate_threeway` ships **no sector directories at all**; it exists so the
  server can register a second map index over a2's terrain. Any tool walking this
  archetype must handle `sector_count == 0`.

---

## Terrain

`style: sculpted`. `stats-terrain.json` `by_archetype.field_valley`, n = 3 maps with
own terrain, 76 sectors, 4,980,736 cells.

| Quantity | Value |
|---|---|
| `height_range_cm` | 7,838.5 - 31,505.0; p5 8,579.5, **p50 16,586.5**, p95 21,876.0 |
| Relief per sector | p25 10,235 cm, **p50 14,113 cm**, p75 16,846 cm, p90 20,036 cm |
| `slope_p50` | **34.2 deg** |
| `slope_p95` | **78.3 deg** (p75 63.5 deg, p90 74.4 deg, mean 35.2 deg) |
| `flat_fraction` (< 5 deg) | **0.248** (< 2 deg 0.173, < 10 deg 0.332, < 20 deg 0.415) |
| `roughness` (abs Laplacian r=1) | p50 48.5 cm, p90 297.5 cm, p99 936.5 cm |
| Local std 3x3 | p50 117.5 cm, p90 586.5 cm |
| Water cells | **27.6 %** |
| Blocked cells | 67.1 % |

**Note the floor.** Minimum height is 7,838.5 cm, not 0 -- this terrain never touches the
raw floor. Set `height_range_cm = (7838, 31505)` and the valley sits at the right
altitude relative to its water plane.

This is the steepest of the four "field" archetypes and roughly 2.5x the slope median of
`field_empire` at the same water cover. Only a quarter of the map is walkable at under
5 deg. The relief per sector is 14 m median against `field_empire`'s 9 m. Build it as
narrow flat valley floors between large rock masses, not as gentle rolling ground.

---

## Textureset recipe

**`metin2_A2.txt`**, 10 slots -- the shortened form of the 17-slot empire template
(`field` x2, `grass` x2, `stone` x2, `tile` x2, `beach` x2) with the same folder
ordering. Measured across all four maps that load it, 4,980,734 painted tiles
(`textures.json` `texturesets["metin2_a2.txt"]`). `weight` = measured `ground_share`;
sums to 1.000.

| slot | role | path | U/V | repeat | weight |
|---|---|---|---|---|---|
| 1 | `mid` / `road` | `d:/ymir work/terrainmaps/a/field/field 01.dds` | 5/5 | 6.4 m | 0.100 |
| 2 | `accent` | `d:/ymir work/terrainmaps/a/field/field 02.dds` | 6/6 | 5.3 m | 0.004 |
| 3 | `mid` | `d:/ymir work/terrainmaps/a/grass/grass 01.dds` | 9/9 | 3.6 m | 0.154 |
| 4 | `mid` | `d:/ymir work/terrainmaps/a/grass/grass 02.dds` | 8/8 | 4.0 m | 0.084 |
| 5 | `base` | `d:/ymir work/terrainmaps/a/stone/stone01.dds` | 5/5 | 6.4 m | 0.454 |
| 6 | `cliff` | `d:/ymir work/terrainmaps/a/stone/stone02.dds` | 4/4 | 8.0 m | 0.205 |
| 7 | `accent` | `d:/ymir work/terrainmaps/a/tile/tile01.dds` | 5/5 | 6.4 m | 0.000 |
| 8 | `path` | `d:/ymir work/terrainmaps/a/tile/tile02.dds` | 5/5 | 6.4 m | 0.000 |
| 9 | `unused` | `d:/ymir work/terrainmaps/a/beach/beach sand 01.dds` | 5/5 | 6.4 m | 0.000 |
| 10 | `unused` | `d:/ymir work/terrainmaps/a/beach/beach sand 02.dds` | 5/5 | 6.4 m | 0.000 |

The base/cliff pair is the whole trick: `stone01` and `stone02` are the same art folder
and the same "stone" name, and they separate only on behaviour. `stone01` covers 45.4 %
at clump 6.27 with 54 % of its tiles surviving one erosion; `stone02` covers 20.5 % at
clump 4.28 with **7 %** surviving, sitting on 50.9 deg ground. One is the carpet, the
other is the skin on the cliff faces.

`grass 02` is the archetype's clearest dither slot: 8.4 % of the ground at clump 3.71
and **0.3 % non-edge**. It has no interior at all -- it exists purely as noise sprinkled
through `grass 01`.

**Both beach slots are dead in all four maps**, despite 27.6 % water cover. Water in
this valley is river gorge, not shoreline: it is walled by rock, not by sand. That is a
real difference from `field_empire` and it is why `beach sand 01/02` were declared and
never painted.

**Roads.** `a/tile/tile02.dds` (slot 8) is scored `path` on 427 tiles total (0.01 % of
the ground) at clump 6.30 and 37 % non-edge on 4 deg ground -- that is a tiny plaza, not the
road network. The actual road web on `map_a2` is painted with slot 1
`a/field/field 01.dds`, an ordinary dirt texture, and covers **8.6 %** of the map
(`placement.md` sec 8). Set `RoadSpec.tile_index = 1`.

**How the archetype paints** (`stats-tiles.json` `by_archetype.field_valley`):
role share rock 65.9 %, grass 23.7 %, dirt 10.4 %, paved 0.02 %; 7 of 10 slots used;
base share 0.479; top-3 share 0.828; 3 dither-only slots carrying 27.9 % of tiles;
3 stipple pairs, interleave 1.71, `stipple_same_family_share` 0.778;
singleton fraction of base 0.483.

---

## Environment

**`A2.msenv`** on all four maps -- cluster C02 `overcast_haze`. There is no range to
sample: one file, four maps (`environments.json` `archetype_presets.field_valley`).

| Parameter | Value |
|---|---|
| `Fog.Enable` | 1 |
| `Fog.NearDistance` / `FarDistance` | 5,000 / 20,000 cm |
| `Fog.Color` | `#5C6E64` -- hue 146.7 deg, sat 0.164, value 0.431. Green-grey, unique in the corpus |
| `Background.Ambient` | `#0C1611` (level 0.0667) |
| `Character.Ambient` | level 0.2167 = Background + 0.15 exactly |
| `Background.Diffuse` | `#FFF8F8`, warmth 0.0275 |
| `Direction` | `0.350156 0.562609 -0.748907` (sun elev 48.5 deg, az 211.9 deg) |
| Gradient | Upper 4 / Lower 1 |
| Sky zenith -> horizon -> nadir | `#072A2E` -> `#9AB6A7` -> `#3F5340` |
| Cloud | `clouds_zone01.tga`, scale 200000, texture scale 4, speed 0.004, height 30000 |
| Skybox faces | none ; `Filter.Enable` 0 ; `LensFlare.Enable` 0 |

The dark teal zenith over a pale green-grey horizon is the tell. Fog far is 20,000 cm --
the same short draw budget as `field_empire`, which on a 6x6 map means you cannot see
more than about three quarters of a sector. That is what makes a2 feel like a valley
rather than a plain.

---

## Object palette

**Density 4.15 obj/ha = 0.0415 per 100 m^2 = 27.2 per sector** -- half of `field_empire`
-- with only **54 distinct CRCs** across 498.07 ha (`stats-objects.json`
`by_archetype.field_valley`). Mix: Tree 51.8 %, Building 47.8 %, Effect 0.3 %.

Family budget:

| Family | n | per ha | NN same-family p25/p50/p75 (cm) | Clark-Evans R |
|---|---|---|---|---|
| `tree/b1` | 988 | 1.98 | 1,060 / **1,315** / 1,948 | 0.490 clustered |
| `zone/b/obj` | 969 | 1.95 | 342 / **1,112** / 2,495 | 0.526 clustered |
| `tree/b3` | 84 | 0.17 | 8,286 / **12,681** / 15,966 | **1.087 Poisson** |
| `zone/a/building` | 18 | 0.04 | 990 / 990 / 1,044 | 0.038 |
| `effect/background` | 5 | 0.01 | -- | -- |

There is **no dedicated building set**. 18 `zone/a/building` records across the whole
archetype: a2 has 9, threeway has the same 9 (it is a copy), guild_01 has none. This is
wilderness with a road through it, not a settled land.

`tree/b3` at R = 1.087 is the only family in the entire corpus scored *Poisson* rather
than clustered -- 84 Beech3 spread across 500 ha at ~127 m apart. Treat it as a lone
landmark tree, not a forest.

### Tier table (directly usable as `MapSpec.objects`)

`density` per 100 m^2; `spacing_cm` = NN(same CRC) p5; `max_slope` = per-CRC slope p95;
`road_clearance_cm` = per-CRC d(road) p25; `height_bias` = (bias p25, bias p75).
`on_tiles` indexes the 10-slot palette above.

| tier | crc | name | density | spacing_cm | on_tiles | max_slope | road_clear_cm | height_bias |
|---|---|---|---|---|---|---|---|---|
| signature | 3689520799 | `Beech4` (Tree, `tree/b1`) | 0.00255 | 2025 | 1,3,4 | 45 | 282 | (-91, -9) |
| signature | 3193282972 | `Sassafras_Fall1` (Tree, `tree/b1`) | 0.00245 | 4603 | 1,3,4 | 28 | 0 | (-45, -30) |
| signature | 2376089798 | `Pagoda2` (Tree, `tree/b1`) | 0.00187 | 2397 | 1,3,4 | 46 | 600 | (-273, -20) |
| signature | 1289994135 | `MontereyCypress4` (Tree, `tree/b1`) | 0.00167 | 3095 | 1,3,4 | 45 | 0 | (-92, -17) |
| signature | 569394331 | `Pagoda1` (Tree, `tree/b1`) | 0.00143 | 1709 | 1,3,4 | 47 | 565 | (-358, -25) |
| signature | 1671224775 | `MontereyCypress5` (Tree, `tree/b1`) | 0.00143 | 2469 | 1,3,4 | 47 | 200 | (-92, -5) |
| signature | 3748653682 | `MontereyCypress3` (Tree, `tree/b1`) | 0.00143 | 2794 | 1,3,4 | 46 | 200 | (-152, -5) |
| signature | 1107711305 | `Pagoda3` (Tree, `tree/b1`) | 0.00135 | 1503 | 1,3,4 | 46 | 565 | (-152, -20) |
| signature | 2399205967 | `Beech2` (Tree, `tree/b1`) | 0.00118 | 2934 | 1,3,4 | 44 | 600 | (-91, -13) |
| signature | 4138381346 | `Sassafras_Fall2` (Tree, `tree/b1`) | 0.00116 | 6213 | 1,3,4 | 29 | 0 | (-45, -35) |
| signature | 486960621 | `MontereyCypress2` (Tree, `tree/b1`) | 0.00112 | 2447 | 1,3,4 | 34 | 282 | (-60, 0) |
| filler | 2679105379 | `general_obj_stone07` (Building, `zone/b/obj`) | 0.00173 | 2089 | 1,3,4 | 29 | 0 | (-60, -20) |
| filler | 2767369424 | `general_obj_stone11` (Building, `zone/b/obj`) | 0.00149 | 228 | 1,3,4 | 26 | 0 | (-20, 28) |
| filler | 3280855028 | `general_obj_stone08` (Building, `zone/b/obj`) | 0.00145 | 944 | 1,3,4 | 26 | 0 | (-55, -20) |
| filler | 865570388 | `general_obj_stone10` (Building, `zone/b/obj`) | 0.00143 | 1001 | 1,3,4 | 30 | 0 | (-100, -20) |
| filler | 2534098066 | `general_obj_stone06` (Building, `zone/b/obj`) | 0.00139 | 2334 | 1,3,4 | 29 | 0 | (-55, -9) |
| filler | 2233363945 | `general_obj_stone12` (Building, `zone/b/obj`) | 0.00131 | 604 | 1,3,4 | 25 | 0 | (-59, -20) |
| filler | 2763472928 | `general_obj_stone09` (Building, `zone/b/obj`) | 0.00122 | 1654 | 1,3,4 | 25 | 0 | (-40, -20) |
| filler | 4122892297 | `general_obj_stone04` (Building, `zone/b/obj`) | 0.00110 | 1008 | 1,3,4 | 32 | 0 | (-30, 0) |
| accent | 3455398876 | `Beech3` (Tree, `tree/b3`) | 0.00169 | 2662 | 1,3,4 | 41 | 400 | (-60, -5) |

The `general_obj_stone04..12` boulder run is this archetype's signature more than any
tree is: nine distinct boulder CRCs, together ~7 per hectare, all sunk 20-60 cm, all
with d(road) p25 = 0. They line the road.

---

## Placement rules

**Ground affinity** (`affinity.json` `by_archetype.field_valley`, n = 2,068):
field 63.9 %, grass 32.6 %, rock 3.4 %, tile 0.1 %. Object slope p50 **2.95 deg**,
p75 8.0 deg, p95 22.75 deg.

That is the archetype's sharpest internal contrast: the *terrain* has slope p50 34.2 deg,
but the *objects* sit at p50 2.95 deg. Objects occupy the ~25 % of the map that is flat,
and rock -- 65.9 % of the painted ground -- carries only 3.4 % of the objects. Nothing is
placed on the cliffs.

**Positive rules**

1. **Everything is on the road.** Both buildings and trees have d(road) p50 = 0 cm
   (`placement.md` sec 8); the road web covers 8.6 % of `map_a2`. Lay the corridors first
   and hang the entire object budget off them.
2. Road grammar (pooled, see caveat): centreline width median 8.0 m (distance-transform
   median 5.0 m), road core fraction 0.050, density 5,956 m/km^2, tortuosity 1.21,
   3.7 junctions/km, **0.29 loops/km**, radius of curvature 47 m. Compared with
   `field_empire`, this web is wider, straighter and much less looped -- a through-route
   valley, not a settlement grid.
3. **Boulders, not props.** `zone/b/obj` here is the `general_obj_stone*` set, not
   crates and fences. Sink them 20-60 cm.
4. **Trees at 10-13 m.** `tree/b1` NN p50 1,315 cm, tighter than `field_empire`'s
   1,686 cm. Sink `b1` about 45 cm, `b3` about 35 cm.
5. Two thirds of tree rolls are exactly 0; the `Sassafras_Fall` pair is 83 %
   unrotated. The rest are multiples of 15 deg.

**Negative rules**

- **No B-family terrain textures.** Jaccard 0.00 against `field_empire`. Mixing
  `b/grass/grass 01.dds` into an A-palette is the single most visible way to get this
  archetype wrong.
- **No beach.** Both `a/beach` slots are painted zero tiles in all four maps.
- **No `tree/n1`, `tree/n2`, `tree/b2`.** Only `b1` (988) and `b3` (84) appear.
- `tree/b1` never on lava or snow; `tree/b3` never on lava, sand, snow or tile;
  the `general_obj_stone0*` boulders never on `(none)`, lava, other, snow or tile, and
  `stone08`/`stone09`/`stone10` never on sand either
  (`affinity.json.by_crc` `never_on`).
- **Almost no buildings.** 18 records in 500 ha. Do not settle this valley.
- **No DungeonBlock records.**

---

## Attr policy

`attr_style: slope_driven` on all 3 maps with terrain.

| Setting | Value |
|---|---|
| `attr_style` | `slope_driven` |
| `block_slope_deg` | **23** (map_a2 and threeway both fitted 23; guild_01 degenerates to 3) |
| `border_band_m` | **142 m** median seal depth (a2/threeway strict band 94 m, guild_01 38 m) |
| `safezone_regions` | one 32 m circular stamp in the whole archetype |

Block budget over 3,304,667 block cells: **slope 81.1 %**, water 12.7 %, out-of-bounds
4.7 %, object halo 0.6 %, residual 0.9 % (`stats-attr.json`
`archetypes.field_valley.block_budget`). 66.3 % of cells blocked.

This is the *purest* slope-driven archetype in the corpus: 81 % of block is explained by
the terrain alone, against 72.6 % for the pooled `slope_driven` set. If you build the
mountain correctly here, the collision falls out of it.

- **Footprint policy `model_only` on a2 and threeway.** Only 7.9 % of Building centre
  cells are blocked and 4.0 % of Tree centre cells. Buildings are *not* stamped into
  `attr.atr` here -- collision is left to the `.mdatr`. This is one of the two footprint
  policies in the corpus and it is the minority one; do not stamp footprints for this
  archetype.
- Water agrees well with `water.wtr`: Jaccard 0.807, the highest of any archetype.
  2 of 3 maps paint the flag. Set `WATER | BLOCK` on submerged cells.
- **Rim slope median 50 deg versus interior 18 deg** -- the steepest border wall in the corpus
  (`attributes.md` sec 8). All three maps are sealed strict.
- **All 4,980,736 cells carry paint bytes above `0x07`** (`flag7`/`object` at 100 %).
  `map_a2` is one of the 17 maps where `0x80` is set on every cell. The naive
  `server_attr` recipe -- copy the client byte verbatim and read bit 7 as
  `ATTR_OBJECT` -- makes this map **fully impassable server-side**
  (`attributes.md` sec Discrepancies 3). Mask before writing `server_attr`.
- Safezone is negligible: one circle-brush component, 812 m^2, 32 m bbox, fill 0.793.

---

## Tells

1. **A-pack only.** Every texture from `terrainmaps/a/{field,grass,stone,tile,beach}`
   and nothing else. Zero overlap with the empire B-pack.
2. **`stone01` is the ground, not the cliff.** 45.4 % of the map is painted with a file
   called "stone" that is actually tan dirt. The cliff is `stone02`, distinguished only
   by slope and by having no solid interior.
3. **Steep, and objects only in the flat quarter.** Terrain slope p50 34 deg, object slope
   p50 3 deg.
4. **The road is the map.** Roads cover 8.6 % of a2; d(road) p50 is 0 for both trees and
   buildings. There is no wilderness-behind-the-treeline here; there is only roadside.
5. **Boulder litter.** Nine `general_obj_stone*` CRCs at ~7/ha, sunk, roll mostly
   non-zero (only 7-24 % unrotated) -- the opposite of trees.
6. **Green-grey overcast, not blue noon.** Fog `#5C6E64`, zenith `#072A2E`. Swapping in
   `A1.msenv` immediately turns it into an empire field.
7. **No beach even though a quarter of the map is water.** River gorges walled in rock.
8. **Almost no houses.** If you place a settlement, you have left the archetype.
9. **One map, three names.** a2, threeway and smhgate_threeway are the same terrain. If
   you generate two `field_valley` maps that look different from each other, you have
   gone further than the corpus ever did.

---

## Sources

`corpus-overview.md` sec 2, sec 4 ; `catalog/map-taxonomy.json` `archetypes.field_valley` ;
`catalog/stats-terrain.json` `by_archetype.field_valley` ;
`catalog/stats-tiles.json` `by_archetype.field_valley` ;
`textures.md` sec 4c, sec 6 `field_valley` ; `catalog/textures.json`
`texturesets["metin2_a2.txt"]` ; `environments.md` sec 5, sec 6 `field_valley` ;
`catalog/environments.json` `archetype_presets.field_valley` ;
`placement.md` sec 5, sec 8 ; `catalog/stats-objects.json`
`by_archetype.field_valley`, `by_crc` ; `catalog/affinity.json`
`by_archetype.field_valley`, `by_crc` ; `attributes.md` sec 4, sec 8, sec 10, sec Discrepancies ;
`catalog/stats-attr.json` `archetypes.field_valley`, `maps.map_a2` ;
`catalog/roads.json` `by_archetype.field_valley` -- pooled and unfiltered, see
`roads.json.by_archetype_caveat`.

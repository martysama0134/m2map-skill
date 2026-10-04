# 12 -- `dungeon_block`

**Flat black-box block dungeon (interior).** 23 maps (18 with own terrain), 232 sectors,
10,232 object placements. Reference map `metin2_map_skipia_dungeon_02`.

---

## Identity

**The terrain is a black plane and everything the player sees is `.prd` geometry placed
through `areadata.txt`.** `terrainmaps/dungeon/field 01.dds` and `terrainmaps/black.dds`
both decode to luminance 0.000, and between them they cover **100 % of every block
dungeon's ground** -- 15.2 M tiles across 23 maps.

Every measurement in this archetype is degenerate in the same direction:

- slope p50 **0.025 deg**, 93.3 % of cells under 2 deg, relief per sector **137 cm**;
- `base_share` median **1.000**, `used_count` median **1 slot**,
  `coverage_entropy_bits` **0.000**, `stipple_pairs_per_map` **0**,
  `mean_run_h_of_base` **768 tiles**;
- `water_cell_fraction` **0.0**;
- **zero Tree records**, in any of the 23 maps.

The formal separation rule from `dungeon_themed` is measurable: **textureset texture
count <= 5 AND maximum fog channel <= 0.20** (`map-taxonomy.json`
`archetypes.dungeon_block.evidence`). 18 of the corpus's 19 `TerrainVisible 0` maps are
here.

This archetype **cannot be produced by the sculpted terrain stages at all**
(`spec.py` `MapSpec.style` docstring). Set `style: "box"`.

---

## Reference maps

23 maps; 18 with own terrain, 3 pure proxies, 2 partial (one sector holding only
`attr.atr` -- a collision patch over the parent's terrain,
`corpus-overview.md` sec 1).

| Map | Size | Sectors | Textureset | Environment | Objects | CRCs |
|---|---|---|---|---|---|---|
| **`metin2_map_skipia_dungeon_02`** (reference) | 6x6 | 36 | `metin2_n_saguidungeon.txt` | `skipia_dungeon.msenv` | 3,847 | 22 |
| `metin2_map_skipia_dungeon_01` | 6x6 | 36 | `metin2_n_saguidungeon.txt` | `skipia_dungeon.msenv` | 3,717 | 17 |
| `metin2_map_mt_th_dungeon_01` | 3x3 | 9 | `metin2_mtthunder_dungeon.txt` | `dark.msenv` | 821 | 14 |
| `metin2_map_anglar_dungeon_01` | 6x6 | 36 | `metin2_map_anglar_dungeon_01.txt` | `anglar_dungeon_01.msenv` | 788 | 21 |
| `metin2_map_spiderdungeon_02` | 4x4 | 16 | `metin2_n_saguidungeon.txt` | `skipia_dungeon.msenv` | 138 | 7 |
| `metin2_map_monkeydungeon` / `_02` / `_03` | 3x3 | 9 each | `metin2_map_deviltower1.txt` | `dark` / `monkeydungeon_02` / `_03` | 114 each | 7 |
| `metin2_map_maze_dungeon1` / `2` / `3` | 3x3 | 9 each | `metin2_map_deviltower1.txt` | `moonlight04.msenv` | 111 each | 7 |
| `metin2_map_snake_temple_02` | 3x3 | 9 | `metin2_map_smhtower_d.txt` | `dark.msenv` | 110 | 28 |
| `metin2_map_spiderdungeon_03` | 3x3 | 9 | `metin2_map_spiderd.txt` | `dark.msenv` | 62 | 9 |
| `metin2_map_skipia_dungeon_boss` | 2x2 | 4 | `metin2_n_saguidungeon.txt` | `skipia_dungeon.msenv` | 42 | 4 |
| `metin2_map_spiderdungeon` | 3x3 | 9 | `metin2_map_spiderd.txt` | `dark.msenv` | 14 | 7 |
| `metin2_map_deviltower1` | 3x3 | 9 | `metin2_map_deviltower1.txt` | `dark.msenv` | 10 | 4 |
| `metin2_map_smhdungeon_02` | 2x2 | 4 | `metin2_map_smhtower_d.txt` | `dark.msenv` | 6 | 6 |
| `metin2_map_smhdungeon_01` | 1x1 | 1 | `metin2_map_spiderd.txt` | `dark.msenv` | 2 | 2 |
| `metin2_map_monkey_dungeon_11/12/13` | 3x3 | 0 | `metin2_map_deviltower1.txt` | `dark.msenv` | 0 | -- |
| `metin2_map_boss_awaken_skipia` / `boss_crack_skipia` | 6x6 | 1 (attr only) | `metin2_n_saguidungeon.txt` | `skipia_dungeon.msenv` | 0 | -- |

- **Typical size 3x3** (14 of 23), **flagship 6x6** (5).
- Object counts range from **2 to 3,847**. Density is meaningless as a single number --
  see below.
- `metin2_map_smhdungeon_02` sectors **have no `minimap.dds`** -- one of the corpus's
  three sector-level exceptions.

---

## Terrain

**`style: box`.** `stats-terrain.json` `by_archetype.dungeon_block`, 18 maps,
232 sectors.

| Quantity | Value |
|---|---|
| `height_range_cm` | 7,131.5 - 23,179.5; **p5 16,307, p50 16,383.5, p95 16,561.5** |
| Relief per sector | p25 **113.5 cm**, p50 **136.8 cm**, p75 404.2, p90 1,379.5 |
| `slope_p50` | **0.025 deg** |
| `slope_p95` | **5.1 deg** (p75 0.025 deg, p90 0.025 deg, p99 40.9 deg) |
| `flat_fraction` (< 5 deg) | **0.949** (< 2 deg 0.933) |
| `roughness` (abs Laplacian r=1) | **p50 0.5 cm**, p90 4.5, p99 179.5 |
| Water cells | **0.0** |
| Blocked cells | 82.7 % |

The height p5-to-p95 spread is **254 cm across 232 sectors**. Set
`height_range_cm = (16300, 16600)` and fill it flat. The 7,131-23,180 outer range comes
from a handful of ramp cells; 93 % of the map is a single plane at ~16,384 cm -- which is
raw value 32768, exactly the uint16 midpoint. **That is almost certainly deliberate: the
editor's default height.**

Do not generate noise. `roughness` p50 of 0.5 cm is the quantisation floor.

---

## Textureset recipe

**`metin2_map_deviltower1.txt`**, **one slot** (`textures.json`
`texturesets["metin2_map_deviltower1.txt"]`) -- byte-identical to
`metin2_map_anglar_dungeon_01.txt` and `metin2_n_saguidungeon.txt`.

| slot | role | path | U/V | repeat | weight |
|---|---|---|---|---|---|
| 1 | `void` | `d:/ymir work/terrainmaps/dungeon/field 01.dds` | 5/5 | 6.4 m | **1.000** |

That is the entire recipe. **Fill `tile.raw` with `0x01`.**

The archetype's other palettes add nothing that gets painted:

- `metin2_map_spiderd.txt` (2 slots), `metin2_map_smhtower_d.txt` (3 slots) -- the extras
  are `black.dds`, which is the only other texture ever painted here (5.58 % of the
  archetype's ground);
- `metin2_mtthunder_dungeon.txt` (5 slots) -- carries four `mtthunder/` **outdoor**
  textures that **no map ever touches**.

Across the six palettes there are 13 slots, of which 7 are `void` and 6 are `unused`.

**How the archetype paints** (`stats-tiles.json` `by_archetype.dungeon_block`):
role share **dirt 94.4 %** (that is `dungeon/field 01.dds`, classified by filename motif)
+ **void 5.6 %**; `base_share` 1.000; `edge_density` **0.000**;
`interior_fraction` **1.000**; `dither_only_slots_per_map` **0**;
`singleton_fraction_of_base` **0**; `mean_run_h_of_base` 768 tiles (min 256, max 1,536 --
i.e. whole sectors).

**If you generate a block dungeon: one slot, one black texture, `UScale 5`, fill
`tile.raw` with `0x01`.** Anything else is wrong for this archetype.

---

## Environment

**Two sub-recipes**, both reading as "no sky" (`environments.json`
`archetype_presets.dungeon_block`):

| Env | Maps | Cluster | Trick |
|---|---|---|---|
| **`dark.msenv`** (canonical) | 11 | C05 `black_box` | ambient 0, fog `#000000` 5,000->20,000, `GradientLevelUpper 1` with an all-zero gradient, no cloud texture |
| `skipia_dungeon.msenv` | 6 | C07 `unfogged_cave` | **`Fog.Enable` 0**, ambient raised to 0.57, and **`blackout.dds` bound as the CLOUD texture** to paint the dome black |
| `moonlight04.msenv` | 3 | C05 `black_box` | keeps a real ramp (`#1A0046` -> `#6E5936`) |
| `anglar_dungeon_01.msenv` | 1 | C01 `murky_lowlight` | fog 0.05/0.00/0.10 |
| `monkeydungeon_02.msenv` / `_03.msenv` | 1 each | C05 `black_box` | |

| Parameter | Observed over all 23 maps |
|---|---|
| `Fog.Enable` | **1 x17, 0 x6** |
| `Fog.NearDistance` | 1 - 5,000 cm (median 5,000) |
| `Fog.FarDistance` | **20,000 cm x23** |
| `Fog.Color` | `#000000`, `#0E011A`, `#1F1F28` -- max channel <= 0.20 by construction |
| `Background.Ambient` | `#000000` (median level 0.0) or `#83839E`/`#93839E` (0.55-0.57) |
| `Character.Ambient` | Background + 0.15 |
| Gradient | **Upper 1 x20**, 4 x3 / Lower 1 x23 |
| Sky zenith / horizon / nadir luminance | **median 0.000** |
| Cloud | **`blackout.dds`**, `clouds_zone02.tga`, `clouds_zone06.tga` |
| Skybox faces | none |

`moonlight04.msenv` is also the corpus's **only file where `Background.Diffuse` differs
from `Character.Diffuse`** (bg 0.251/0.251/0.333 vs ch 0.475/0.475/0.592) -- the sole
exception to that invariant in 104 files (`environments.md` sec 3).

Reproduce one of the two tricks, not a blend: either black fog with a collapsed gradient
(`dark`), or fog off with a raised ambient and `blackout.dds` as the cloud sheet
(`skipia_dungeon`).

---

## Object palette

**Density 6.73 obj/ha = 0.0673 per 100 m^2 = 44.1 per sector**, but that average is
misleading: `metin2_map_skipia_dungeon_02` alone carries 3,847 objects and
`metin2_map_smhdungeon_01` carries 2. Mix: **Effect 72.0 %, DungeonBlock 23.4 %,
Building 4.7 %, Tree 0 %.**

143 distinct CRCs across 1,520.44 ha.

| Family | n | per ha | Modal same-family NN | Clark-Evans R |
|---|---|---|---|---|
| `zone/dungeon/haven_dungeon` | 7,602 | 5.00 | **1,155-1,161 cm** | 0.492 |
| `effect/background` | 848 | 0.56 | 653 / 2,038 / 4,056 | 0.597 |
| `zone/dungeon/mt_thunder_dungeon` | 604 | 0.40 | **1,200 cm** | 0.145 |
| `zone/dungeon/anglar_dungeon` | 389 | 0.26 | **3,000 / 5,091 cm** | 0.309 |
| `zone/dungeon/maze_dungeon` | 264 | 0.17 | **3,860 cm** | 0.360 |
| `zone/dungeon/monkey_dungeon` | 264 | 0.17 | **3,860 cm** | 0.360 |
| `zone/b/obj` | 151 | 0.10 | 331 / 343 / 345 | 0.018 |
| `zone/dungeon/spider_dungeon` | 57 | 0.04 | 9,900 cm | 0.384 |

**Corridor kits are laid on a fixed module.** That is the placement grammar of this
archetype: a pitch, not a scatter.

### Tier table (directly usable as `MapSpec.objects`)

`density` per 100 m^2; `spacing_cm` = NN(same CRC) p5; `max_slope` = per-CRC slope p95;
`height_bias` = (bias p25, bias p75). `on_tiles` is `[1]` for everything -- there is one
slot.

| tier | crc | name | density | spacing_cm | max_slope | height_bias | water_m |
|---|---|---|---|---|---|---|---|
| signature | 807123463 | `smallb_resorce` (Effect, `zone/dungeon/haven_dungeon`) | **0.03357** | 1058 | 7 | (**+308, +473**) | n/a |
| signature | 3982077190 | `smalla_resorce` (Effect, same) | 0.00911 | 1927 | 15 | (**+1470, +1527**) | n/a |
| signature | 3453634549 | `skipia_passi` (DungeonBlock, same) | 0.00185 | **6300** | 0 | (-120, 0) | n/a |
| signature | 703712134 | `skipia_collision` (Building, same) | 0.00213 | 2270 | 15 | (-85, -80) | n/a |
| signature | 2874598244 | `Mt_Thunder_passagepillar` (DungeonBlock, `.../mt_thunder_dungeon`) | 0.00087 | 1726 | 68 | (0, 0) | n/a |
| signature | 3600435032 | `mt_thunder_passage02` (DungeonBlock, same) | 0.00076 | 2851 | 0 | (0, 0) | n/a |
| signature | 133683983 | `mt_thunder_passage03` (DungeonBlock, same) | 0.00070 | `TODO: no catalog evidence` | -- | -- | n/a |
| filler | 1755164826 | `fire_general_obj_campfire.mse` (Effect, `effect/background`) | 0.00180 | 644 | 3 | (**+410, +571**) | 0/0/124 (0, inf) |
| filler | 2753626294 | `fire_general_obj_charcoal.mse` (Effect, same) | 0.00143 | 630 | 1 | (**+360, +410**) | 49/131/249 **(49, inf)** |
| filler | 929619867 | `warpgate01` (Effect, same) | 0.00098 | 5512 | 3 | (+55, +55) | 31/123/225 **(31, inf)** |
| filler | 1471924893 | `ob-7-02-01` (Building, `zone/b/obj`) | 0.00087 | 213 | 22 | (-20, +108) | 51/119/230 **(51, inf)** |

`water_m` = observed distance to the nearest water, p25/p50/p75 in metres (`affinity.json` `by_crc[crc].d_water_cm`; `~` = the family's figure where the CRC has none). The bold `(min, inf)` is the suggested `MapSpec.water_distance_m` for species that measurably avoid water. A species that tolerates it gets no constraint; give oasis or shore decoration a `(0, max)` band instead -- do NOT try to pin it to the shore texture, which is a stipple and covers only a handful of tiles.


**`smallb_resorce` and `smalla_resorce` are 6,489 of the archetype's 10,232 placements**
and they exist in exactly three maps (`skipia_dungeon_01/02/boss`). They are resource
sparkles on a **1,155-1,161 cm grid** with `roll` zero in 96.6-97.6 % of records and yaw
and pitch exactly 0. They are the most mechanically placed objects in the corpus.

**Effects here are raised hard**: `smalla_resorce` at **+1,519 cm** median bias,
`smallb_resorce` at +356, `fire_general_obj_campfire.mse` at +570. A particle system is a
billboard and has to be lifted to eye height (`placement.md` sec 1.3).

`skipia_collision` (324 records) is **invisible geometry placed only to block movement** --
family `collision_proxy` in `objects.json` sec 5. It renders as nothing.

---

## Placement rules

**Ground affinity** (`affinity.json` `by_archetype.dungeon_block`, n = 10,232):
**field 98.5 %**, other 1.1 %, `(none)` 0.4 %. Object slope p25 = p50 = p75 = **0.0 deg**.

**Positive rules**

1. **Lay the corridor kit on its module.** `mt_thunder_passage01-03` at 1,200 cm;
   `maze_dungeon_cave0*` / `monkey_dungeon_cave0*` at 3,860 cm; `anglar_*` at 3,000 and
   5,091 cm; `zone/geuglagsa` wall kit at 900/1,000 cm.
2. **Snap the rotation to 90 deg.** Rolls are multiples of 90 deg in **98.9-100 %** of every
   kit (`placement.md` sec 8). This is the one archetype where the 15 deg ladder collapses to
   the cardinal four.
3. **One constant bias per kit.** `maze_dungeon` +20 cm on 98.9 % of records,
   `anglar_dungeon` +5 cm on ~100 %, `mt_thunder` 0 cm.
4. **DungeonBlocks are the corpus's only grid-snapped objects**: 70.6 % are integral cm
   and 26.7 % sit exactly on a metre (`placement.md` sec 1.2). Everywhere else, do not
   quantise; here, do.
5. **Raise every effect.** +356 to +1,519 cm.
6. **Add invisible collision proxies** where the geometry does not block by itself.

**Negative rules**

- **Zero Tree records.** Not one, in 23 maps. `MapSpec.objects` must contain no `Tree`
  for this archetype.
- **No water, no roads.** `water_cell_fraction` 0, `attr_water_cells` 0, and the road
  detector finds nothing.
- **`smallb_resorce` / `smalla_resorce` are never on grass, lava, other, rock, sand, snow
  or tile** -- there is only one ground class to be on.
- **Do not paint a second texture.** `base_share` is 1.000 on 17 of 18 maps.
- **Do not sculpt.** Relief 137 cm per sector.

---

## Attr policy

**`attr_style: painted_box`** on 18 of 20 maps with attr data. The two exceptions
(`boss_awaken_skipia`, `boss_crack_skipia`) are single-sector attr-only patches with
**100 % out-of-bounds block and no seal at all**.

| Setting | Value |
|---|---|
| `attr_style` | `painted_box` |
| `block_slope_deg` | **not applicable -- do not fit one** |
| `border_band_m` | **218 m** median seal; the shell is pure paint |
| `safezone_regions` | rectangular fill only, in 3 of 20 maps |

Block budget over 12,556,634 cells: **slope 3.9 %**, water 0.0 %, object halo 10.2 %,
**out-of-bounds 71.4 %**, residual 14.5 %. **81.9 % of cells blocked.**

That 3.9 % slope figure is the archetype's headline attr fact: **slope explains almost
nothing here.** Fitting a threshold on these maps is meaningless
(`attributes.md` sec 4) -- Youden's *J* for `slope >= T` on `painted_box` maps is 0.176, and
the per-map fitted thresholds here scatter from 1 deg to 75 deg with no signal.

**The procedure is: paint `BLOCK` everywhere, then carve the corridors and rooms out of
it.** 71.4 % of the block ends up edge-connected, which is exactly what "a slab with
tunnels in it" measures as.

- **Never paint `ATTRIBUTE_WATER`.** Zero wet cells.
- Footprint policy is `model_only` on 11 maps and `no_buildings` on 4 -- buildings sit in
  the carved space and collision comes from the `.mdatr`. Only **10.2 % of DungeonBlock
  centre cells are blocked** (they are the walkable floor), against 88.7 % of Effect
  centre cells (the effects mark the *walls*).
- **Rim slope median 0 deg and interior median 0 deg** (`attributes.md` sec 8). The border is
  paint. Use a **15-30 m block shell**, not a raised ridge.
- 6 of 20 maps write paint bytes above `0x07`, covering 23.1 % of the archetype's cells.
- Safezone: 2 rectangular-fill components in 3 maps, median 34,568 m^2, fill ratio
  **1.000**. `metin2_map_smhdungeon_01` marks one whole sector. If the dungeon has a
  peace room, use a rectangle.

---

## Tells

1. **One texture, black, `tile.raw` all `0x01`.** `base_share` 1.000, entropy 0.000.
2. **Height 16,383.5 cm everywhere** -- raw 32768, the uint16 midpoint -- with 137 cm of
   relief per sector.
3. **72 % Effect, 23 % DungeonBlock, 0 Tree.**
4. **Rolls are multiples of 90 deg, not 15 deg.**
5. **A corridor kit on a fixed pitch**: 1,155 / 1,200 / 3,000 / 3,860 / 5,091 cm.
6. **Effects raised 3.5 to 15 metres.**
7. **`TerrainVisible 0`** on 18 of the corpus's 19 such maps.
8. **Block is 71 % edge-connected paint and 4 % slope.**
9. **Invisible collision proxies** (`skipia_collision`, 324 records).
10. **Fog `#000000` at 5,000->20,000, or fog off with `blackout.dds` as the cloud sheet.**
11. **695 records in eight of these maps carry portal IDs** in token 7+ -- the only
    records in the corpus that do (`placement.md` sec 1.6).

---

## Labyrinths

Six of these maps are labyrinths built from a modular kit -- `anglar_dungeon_01`,
`whitedragoncave_01/02` (themed, same build), `skipia_dungeon_01/02`,
`spiderdungeon_02/03` and the maze/monkey six. Their pieces, sockets, measured
walk and dressing are mined into `../labyrinth/kits.json`; a new labyrinth is a
`labyrinth:` block in the mapspec, not hand-placed records. See
`../labyrinth/README.md`.

## Border occlusion

**Fog, not terrain.** Ring lift is **+0 cm** -- this archetype does not wall its border, and for the negative cases the map sits ON the high ground with the edges falling away. Occlusion comes from the environment instead. Leave `border_ridge_cm` at 0 and keep the archetype's `Fog.NearDistance`, which is what does the work.

Measured over the outer 64 m against the interior; see `../taste.md` for the corpus-wide table and the two traps when building a rim.

## Sources

`corpus-overview.md` sec 1, sec 4 ; `catalog/map-taxonomy.json` `archetypes.dungeon_block`,
`maps.*` ; `catalog/stats-terrain.json` `by_archetype.dungeon_block` ;
`catalog/stats-tiles.json` `by_archetype.dungeon_block` ; `textures.md` sec 6
`dungeon_block` ; `catalog/textures.json` `texturesets["metin2_map_deviltower1.txt"]`,
`["metin2_mtthunder_dungeon.txt"]` ; `environments.md` sec 3, sec 5 C05/C07, sec 6
`dungeon_block` ; `catalog/environments.json` `archetype_presets.dungeon_block` ;
`objects.md` sec 3, sec 5 ; `placement.md` sec 1.2, sec 1.3, sec 1.6, sec 2, sec 3.3, sec 4.4, sec 8 ;
`catalog/stats-objects.json` `by_archetype.dungeon_block`, `by_crc` ;
`catalog/affinity.json` `by_archetype.dungeon_block`, `by_crc` ;
`attributes.md` sec 4, sec 8, sec 10 ; `catalog/stats-attr.json` `archetypes.dungeon_block`,
`maps.*` ; `scripts/m2map/gen/spec.py` `MapSpec.style`.

# Object Placement Grammar

How Ymir/GF actually placed objects in the 142 shipped maps: what goes where, how far
apart, at what angle, sunk how deep, on which ground, and next to what. Every rule below
is a measurement over the whole corpus with its `n`; nothing here is inferred from
screenshots or lore.

**Source of the numbers.** `scripts/m2map/mine/object_stats.py` parses every
`areadata.txt` under `<CORPUS>` (142 maps, 1 343 sectree folders), resolves each record's
CRC against the 2 112-file client property pack
(`M2-v24.0.0.0/pack/property/property`), and joins each placement to the terrain
underneath it — `tile.raw` for the ground texture, `height.raw` for slope and terrain Z,
`attr.atr` for the paint/collision byte, `water.wtr` for wetness. Output:
`catalog/stats-objects.json`, `catalog/affinity.json`, `catalog/cooccurrence.json`.
Regenerate with `python -m m2map.mine.object_stats`.

**Corpus totals.** 48 774 placements, 1 684 distinct CRCs, 0 unresolved CRCs, 114 maps
that contain objects (28 are terrain-less `ParentMapName` proxies or empty).
428 of the 2 112 shipped properties are never placed by any official map.

| Type | Placements | Distinct CRCs | Median NN (any object) |
|---|---|---|---|
| Building | 23 044 (47.2 %) | 1 369 | 384 cm |
| Tree | 14 281 (29.3 %) | 84 | 920 cm |
| Effect | 8 117 (16.6 %) | 63 | 959 cm |
| DungeonBlock | 3 332 (6.8 %) | 168 | 1 190 cm |

`Building` is a catch-all: it holds houses *and* every rock, crate, fence and bush that
is a `.gr2`. Read the family (`zone/b/obj`, `zone/b/building`, …), not the type, when
you want to know what an object is.

---

## 1. Universal laws

These hold across every archetype. Break them and the map reads as machine-made.

### 1.1 Rotation snaps to 15°, and only roll is used

* **Every one of the 48 774 rotation values in the corpus is an integer degree.** Not one
  fractional angle exists (`roll_integer_share = 1.0`). The engine truncates with `atoi`
  anyway, but the shipped files were already integral.
* **99.69 % of roll values are multiples of 15°** (`mod15 == 0`); 99.75 % are multiples
  of 5. The WorldEditor rotate gizmo snaps at 15°, and the artists never fought it.
  Only 148 distinct roll values exist in the whole corpus, all in `[0, 357]`.
* **Roll is the heading.** `D3DXMatrixRotationYawPitchRoll` puts roll around Z, which is
  up in Metin2. 26 129 records have non-zero roll; only 1 767 use yaw and 1 802 use
  pitch (3.6 % each). Yaw/pitch are the *tilt* channels — used to lean a rock, a
  shipwreck or a bone, never to turn a building.
* **22 251 records (45.6 %) have rotation `0#0#0`.** Zero rotation is normal, not lazy.
* Cardinal headings are over-represented: among non-zero building rolls, 90/180/270 each
  appear ~3× as often as a generic 15° step (29.5 % are multiples of 90, 47.2 % of 45).
* **Trees are not uniformly rotated.** 67.2 % of `tree/b1`, 60.3 % of `tree/n2` and
  82.7 % of `tree/n1` records have roll exactly 0. The remainder is spread over the 15°
  ladder with a resultant length R = 0.64–0.82 — strongly non-uniform. Variety in a
  forest comes from *species mixing and TreeVariance*, not from yaw jitter.

Which channels each family uses (share of records with |angle| > 0.5°):

| Family | roll ≠ 0 | yaw ≠ 0 | pitch ≠ 0 | n |
|---|---|---|---|---|
| `zone/b/obj` | 84.4 % | 6.2 % | 6.1 % | 10 792 |
| `tree/b1` | 32.8 % | 2.4 % | 2.7 % | 5 968 |
| `zone/snakevalley` (spear rocks) | 67.3 % | **39.9 %** | **33.6 %** | 333 |
| `zone/devils_dragon_island/bone` | 72.7 % | **26.2 %** | **33.0 %** | 267 |
| `zone/dungeon/mt_thunder_dungeon` | 74.3 % | 0 % | 0 % | 604 |
| `zone/b/building` | 76.9 % | 0.1 % | 0.1 % | 1 021 |

Rule: **buildings and dungeon blocks never tilt; natural debris (rocks, bones,
shipwrecks, thorns) does, at ±15° or ±30°.**

### 1.2 Positions are free-hand, not grid-snapped

Only 14.8 % of X coordinates are whole centimetres; 10.4 % land on a 1 m tile boundary
and 5.6 % on a 2 m cell boundary. Trees are the least snapped (5.7 % on a metre),
Effects almost never (0.3 %). **DungeonBlocks are the exception: 70.6 % are integral cm
and 26.7 % sit exactly on a metre**, because they are laid out as a connected corridor
kit.

Do not quantise positions when generating. Metin2 maps were dragged with a mouse.

### 1.3 Height: `final_z = z + heightBias`, and the bias is the sink

* Median bias 0 cm, mean +45.75 cm, p5 −273 cm, p95 +478 cm (n = 48 774).
* 30.0 % of records have bias exactly 0, **47.3 % are negative** (object pushed into the
  ground), 22.7 % positive.
* `final_z − terrain_z` (terrain sampled from the `height.raw` vertex under the object)
  has median −5 cm and 55.4 % of records land within 50 cm of the terrain surface. The
  stored `z` is essentially the terrain height at authoring time; the bias is the
  artist's nudge.

Per type:

| Type | bias p25 | p50 | p75 | negative | exactly 0 | positive |
|---|---|---|---|---|---|---|
| Building | −30 | **0** | 0 | 49.6 % | 40.0 % | 10.4 % |
| Tree | −80 | **−37** | 0 | **74.8 %** | 24.4 % | 0.8 % |
| Effect | +304 | **+410** | +480 | 3.4 % | 3.4 % | **93.2 %** |
| DungeonBlock | 0 | **0** | +5 | 20.9 % | 49.2 % | 29.9 % |

* **Trees get sunk.** `tree/n1` (winter) median −80 cm, `tree/b1` −45 cm, `tree/b3`
  −35 cm, `tree/n2` −15 cm. Sinking hides the SpeedTree root flare on uneven ground.
* **Effects get raised.** `fire_general_obj_campfire.mse` +570 cm (n = 324),
  `fire_general_obj_charcoal.mse` +410 (n = 259), `smalla_resorce` +1 519 (n = 1 385),
  `metinstone_loop_4_orange.mse` +952 (n = 35). An effect is a billboard/particle system
  and has to be lifted to eye height.
* **Big rocks get sunk hardest.** `ob-bigstone01` −152 cm (n = 123), `ob-bigstone03`
  −110 (n = 178), `ob-bigstone04` −104 (n = 133), `general_obj_stone19` −100 (n = 112);
  the desert `JoshuaTree_RT_03` is the extreme at −697 cm (n = 270) — its model is
  authored well above its origin.
* **Buildings do not sink**: `zone/b/building` has bias 0 in 83.6 % of records
  (n = 1 021), `zone/c/building` 61.9 % (n = 352). A house sits on the ground, and the
  ground is flattened for it (see §1.4).

### 1.4 Buildings demand flat ground; trees do not

Slope is the per-cell terrain slope from `height.raw` (mean of the two X edges and the
two Y edges, `atan(hypot)`).

| Type | slope p50 | p90 | p99 | > 30° |
|---|---|---|---|---|
| Building | 1.9° | 29.0° | 62.2° | 9.4 % |
| Tree | 8.3° | 31.9° | 56.5° | 11.3 % |
| Effect | 0.0° | 8.0° | 50.7° | 2.1 % |
| DungeonBlock | 0.0° | 2.7° | 37.0° | 2.6 % |

The archetypal *house* families are far flatter than the aggregate: `zone/b/building`
slope p50 = 0.0°, p95 = 8.45° (n = 1 016); `zone/a/building` p50 = 0.14°, p95 = 16.2°
(n = 214); `zone/c/building` p50 = 0.0°, p95 = 22.2° (n = 352). **Flatten before you
build.** Rocks and vegetation, by contrast, are deliberately put on slopes:
`zone/devils_dragon_island` p50 = 9.2°, p75 = 23.5°; `zone/snakevalley` spear rocks
p50 = 26.3°, p75 = 40.3° (n = 320).

### 1.5 Objects can stand in water

14.5 % of Buildings and 12.6 % of Trees sit on a cell flagged wet in `water.wtr`
(n = 23 044 / 14 281); Effects 1.6 %, DungeonBlocks 0.09 %. Coastal maps carry 20–40 %
water cover, so this is shoreline and shallows, not a bug — but it does mean *water is
not an exclusion zone for vegetation*.

### 1.6 Record shape

All 48 774 records carry ≥ 6 tokens (position, CRC, `yaw#pitch#roll`, bias): 48 079 have
exactly 6, 686 have 7, 9 have 8. The 695 records with portal IDs (token 7+) live in
**eight maps, all `dungeon_block`** — `monkeydungeon`/`_02`/`_03` (114 each),
`maze_dungeon1`/`2`/`3` (111 each), `spiderdungeon` (11), `deviltower1` (9) — carried by
the `maze_dungeon` (264) and `monkey_dungeon` (264) block kits plus their 147 effects.
Not one legacy 4- or 5-token record survives in the shipped corpus, and not one
bare-integer rotation token — so the `substr(0, s-1)` yaw defect never fires on official
data. Write the `%f#%f#%f` form and you are safe.

---

## 2. Density

`obj/ha` = placements per hectare (10 000 m²) of terrain the archetype actually ships;
`obj/sector` = per 256 × 256 m sectree. Corpus mean is 5.6 obj/ha.

| Archetype | maps | area (ha) | placements | obj/ha | obj/100 m² | obj/sector |
|---|---|---|---|---|---|---|
| arena_pvp | 6 | 98.3 | 1 226 | **12.47** | 0.125 | 81.7 |
| guild_village | 4 | 45.9 | 541 | **11.79** | 0.118 | 77.3 |
| field_empire | 18 | 1 094.5 | 8 927 | 8.16 | 0.082 | 53.5 |
| darkforest_coast | 5 | 720.9 | 5 875 | 8.15 | 0.082 | 53.4 |
| empire_war | 3 | 78.6 | 575 | 7.31 | 0.073 | 47.9 |
| dungeon_block | 18 | 1 520.4 | 10 232 | 6.73 | 0.067 | 44.1 |
| desert | 8 | 648.8 | 4 113 | 6.34 | 0.063 | 41.5 |
| ice_valley | 3 | 308.0 | 1 549 | 5.03 | 0.050 | 33.0 |
| trent_forest | 2 | 131.1 | 608 | 4.64 | 0.046 | 30.4 |
| event_instance | 10 | 845.4 | 3 895 | 4.61 | 0.046 | 30.2 |
| eastplain | 4 | 327.7 | 1 507 | 4.60 | 0.046 | 30.1 |
| dungeon_themed | 12 | 1 035.5 | 4 334 | 4.19 | 0.042 | 27.4 |
| field_valley | 3 | 498.1 | 2 068 | 4.15 | 0.042 | 27.2 |
| snow_field | 5 | 452.2 | 1 681 | 3.72 | 0.037 | 24.4 |
| dev_stub | 4 | 78.6 | 182 | 2.31 | 0.023 | 15.2 |
| elemental | 4 | 504.6 | 965 | 1.91 | 0.019 | 12.5 |
| flame_field | 5 | 399.8 | 496 | **1.24** | 0.012 | 8.1 |

Read this as a 10× span: an arena plaza is ten times as furnished as a lava field. The
useful anchors:

* **Open outdoor field: 4–8 obj/ha, ~30–55 per sector.**
* **Plaza / village / arena: 12 obj/ha, 75–85 per sector.**
* **Barren biome (flame, elemental forest): 1–2 obj/ha.**

Composition per archetype (share of placements):

| Archetype | Building | Tree | Effect | DungeonBlock |
|---|---|---|---|---|
| field_empire | 58.3 % | 40.9 % | 0.8 % | — |
| field_valley | 47.8 % | 51.8 % | 0.3 % | — |
| desert | 48.5 % | 49.8 % | 1.8 % | — |
| snow_field | 30.1 % | **67.1 %** | 0.7 % | 2.1 % |
| elemental | 9.2 % | **87.1 %** | 3.7 % | — |
| flame_field | 26.0 % | 61.5 % | 12.5 % | — |
| darkforest_coast | 64.8 % | 34.2 % | 1.0 % | — |
| eastplain | **86.5 %** | 12.7 % | 0.7 % | 0.1 % |
| arena_pvp | **84.6 %** | 11.3 % | 4.2 % | — |
| dungeon_block | 4.7 % | — | **72.0 %** | 23.4 % |
| dungeon_themed | 65.3 % | 7.2 % | 6.7 % | 20.7 % |

**No outdoor archetype uses DungeonBlock, and no block dungeon contains a single Tree
record.** That is a hard partition in the shipped data.

---

## 3. Spacing

Nearest-neighbour distances, measured inside each map, in centimetres.

### 3.1 Trees

| Family | n | NN(same family) p25 / p50 / p75 | NN(any object) p50 |
|---|---|---|---|
| `tree/b1` deciduous | 5 968 | 1 073 / **1 641** / 2 770 | 1 091 |
| `tree/b3` deciduous | 1 783 | 1 105 / **1 899** / 5 656 | 1 035 |
| `tree/n1` winter | 2 084 | 952 / **1 328** / 2 227 | 1 127 |
| `tree/n2` arid | 3 256 | 184 / **386** / 816 | 327 |
| `tree/b2` dead vine / cedar | 1 190 | 1 265 / **2 669** / 4 076 | 1 342 |

**A temperate forest is 10–17 m between trunks; a desert scrub is 2–8 m.** The `n2`
arid set is not a forest at all — it is ground cover (ferns, aloe) placed in dense
patches, which is why its spacing is four times tighter.

Reference maps: `metin2_map_a1` trees p10/25/50/75/90 =
681 / 953 / **1 491** / 2 625 / 4 158 cm (n = 618);
`map_n_snowm_01` = 868 / 1 023 / **1 289** / 1 811 / 3 139 (n = 853);
`metin2_map_n_desert_01` = 132 / 229 / **476** / 960 / 1 938 (n = 1 149).

The long right tail matters as much as the median: a real forest has clumps at 7–10 m
and gaps of 30–40 m. Reproducing only the median gives you an orchard.

### 3.2 Props and buildings

| Family | n | NN(same family) p25/p50/p75 | NN(other family) p50 |
|---|---|---|---|
| `zone/b/obj` generic props | 10 792 | 181 / **363** / 994 | 998 |
| `zone/n/obj/map_n_desert_01` | 1 122 | 182 / **244** / 394 | 428 |
| `zone/n/obj/snow.m` | 1 082 | 356 / **520** / 1 401 | 1 087 |
| `zone/b/building` empire houses | 1 021 | 479 / **1 000** / 2 121 | 1 781 |
| `zone/c/building` | 352 | 700 / **900** / 1 435 | 1 294 |
| `zone/a/building` | 216 | 1 001 / **1 340** / 2 041 | 967 |
| `zone/eastplain` | 964 | 575 / **867** / 1 762 | 10 911 |
| `zone/devils_dragon_island` | 919 | 256 / **690** / 1 353 | 845 |
| `zone/secretdungeon` flowers | 751 | 185 / **283** / 400 | 727 |

**Props cluster at 2–5 m, houses at 9–13 m.** The `zone/b/obj` NN histogram
(n = 10 792): 1 061 pairs under 1 m, 1 940 at 1–2 m, 1 481 at 2–3 m, 2 031 at 3–5 m —
i.e. 60 % of all props have another prop within 5 m. Props travel in packs.

### 3.3 Dungeon blocks are laid on a pitch

DungeonBlock corridors are a kit snapped to a fixed module. Modal same-family NN:

| Family | n | modal NN |
|---|---|---|
| `zone/dungeon/maze_dungeon` / `monkey_dungeon` | 264 each | **3 860 cm** |
| `zone/dungeon/anglar_dungeon` | 389 | 3 000 / 5 091 cm |
| `zone/dungeon/mt_thunder_dungeon` | 604 | **1 200 cm** |
| `zone/whitedragoncave/whitedragoncave_01` | 301 | 0 (stacked) / 3 000 / 4 243 cm |
| `zone/geuglagsa` wall kit | 498 | **900 / 1 000 cm** |
| `zone/dungeon/haven_dungeon` | 7 602 | **1 155–1 161 cm** |

`zone/geuglagsa` also shows the wall-kit signature: 98.4 % of its rolls are multiples of
90°, and the NN histogram is a spike at 700–1 500 cm with nothing below 500.

### 3.4 Clustering: nothing is Poisson

Clark-Evans index `R = mean(NN) / (0.5 / sqrt(density))`, computed against each
archetype's full terrain area. `R < 0.9` = clustered, `≈1` = random, `>1.1` = regular.

**Every archetype is clustered** — R from 0.23 (`dev_stub`) to 0.70 (`dungeon_block`),
median ≈ 0.41. Per family inside `field_empire` (n = 8 927):

| Family | n | R | verdict |
|---|---|---|---|
| `zone/b/obj` | 4 174 | 0.339 | clustered |
| `tree/b1` | 2 231 | 0.572 | clustered |
| `tree/b3` | 1 097 | 0.620 | clustered |
| `zone/b/building` | 742 | 0.248 | strongly clustered |
| `tree/n2` (imported patches) | 182 | 0.054 | extreme clumps |
| `effect/background` | 46 | 1.268 | **regular** |

Two readable rules: **buildings clump harder than trees** (they form settlements),
and **effects are the only thing ever placed regularly** — they are scattered one per
landmark, so they end up more evenly spread than chance.

---

## 4. Terrain affinity — which objects sit on what

Ground class is derived from the texture path *basename* under each placement
(`affinity.json.class_rules`); the measured mean RGB of every texture is published in
`affinity.json.texture_catalog` so class assignments can be audited. Corpus baseline
over all 48 774 placements: field 42.2 %, grass 24.6 %, rock 12.0 %, sand 8.8 %,
snow 4.9 %, tile 3.5 %, other 1.6 %, lava 1.2 %.

> **Naming trap.** `tile` is the `tileNN` / `stone_tile` *pavement* family, not "the
> road". And filenames lie about appearance: `A/stone/stone01.dds` is a tan dirt
> texture (measured mean RGB 159,135,112), not grey rock. Always read
> `texture_catalog[path].mean_rgb` before trusting a class name.

### 4.1 Trees are biome-locked, hard

| Family | dominant ground | lift vs corpus | **never placed on** |
|---|---|---|---|
| `tree/b1` (Beech, Pagoda, MontereyCypress) | grass 44.4 %, field 34.9 % | grass ×1.80 | **lava, snow** |
| `tree/b3` (Beech, UmbrellaThorn) | grass 48.5 %, field 39.0 % | — | **lava, snow, tile** |
| `tree/n1` (ColoradoBlueSpruce, Beech_Winter) | snow 75.4 % | snow **×15.5** | **lava, sand** |
| `tree/n2` (CinnamonFern, AloeVera, JoshuaTree) | sand 52.8 %, grass 26.9 % | sand ×6.0, tile ×0.009 | **lava** |
| `tree/b2` (IvySpy_Winter, CedarOfLebanon) | rock 58.6 % | — | **snow** |

`tree/n2` on pavement: 1 record in 3 256. `tree/b1` on snow: 0 in 5 968. These
exclusions are absolute in the shipped data and should be treated as hard constraints.

### 4.2 Buildings prefer grass and pavement

`zone/b/building` (n = 1 021): grass 38.8 %, field 21.5 %, **tile 21.4 % (lift ×6.11)**,
rock 17.0 %; never on lava, sand or "other". `zone/a/building` (n = 216): grass 53.7 %
(×2.18), field 38.4 %, tile 5.1 %; never on lava, snow or "other" — and effectively
never on rock (1.4 %) or sand (0.5 %).

So: **the empire house set is placed on grass or on a paved plaza, and never on a
beach.** Meanwhile the generic prop set `zone/b/obj` (n = 10 792) has an empty
`never_on` list — crates, fences and rocks go anywhere.

### 4.3 The `attr.atr` paint under an object

Buildings are placed on cells that were painted blocked: `attr & 0x01` is set under
75.5 % of `zone/b/obj`, 86.5 % of `zone/b/building`, 89.9 % of the desert prop set,
98.2 % of `zone/eastplain`, 98.7 % of the devils-island camp set. Trees are the
opposite: `attr & 0x01` under only 42.6 % of `tree/b1`, 24.6 % of `tree/b3`, 24.7 % of
`tree/n2`.

**Placing a building means also painting its footprint as blocked.** The corpus is
consistent about it; a generator that skips the `attr.atr` stamp produces walk-through
houses.

Note the Ymir paint conventions leaking through: `tree/n1` sits on byte `0xC8`
(mountain, walkable) 36.1 % of the time, `zone/n/obj/snow.m` on `0xC9` (mountain,
blocked) 26.9 %. See `mapformat/attr-atr.md` §"paint layers".

### 4.4 Interiors have exactly one ground

`zone/dungeon/haven_dungeon` (n = 7 602): field 99.8 % — a single texture,
`dungeon/field 01.dds`, and *never* grass, lava, rock, sand, snow or tile.
`zone/dungeon/anglar_dungeon` (n = 389): field 100.0 %.
`zone/whitedragoncave/whitedragoncave_01` (n = 301): `black.dds` 94.0 %.
Block dungeons paint one texture (or pure black) and put the geometry on top.

---

## 5. Spatial habits — road, water, edge

Distance-to-road uses a **road network detected geometrically per map**, not by texture
name: a road is a texture covering 0.5–10 % of the map that survives a 2-cell erosion
but not a 5-cell one (ribbons 4–8 m wide). Verified visually on
`metin2_map_a1` (selects index 1 = `b/field/field 01.dds`, the visible road web, and
rejects index 4, its blend halo), `metin2_map_b1`, `metin2_map_capedragonhead`
(index 7 = `stone_tile_002.dds`), `map_a2`, `map_n_snowm_01`, `metin2_map_n_desert_01`.
The `tileNN` pavement class is unioned in so town plazas count. Distances are a 5×5
chamfer transform (weights 1, √2, √5) on the 200 cm cell grid — worst case 2.8 % off
true Euclidean, mean 1.3 %.

**In every outdoor archetype, buildings hug the road and trees stand back.**

| Archetype | Building d(road) p50 | Tree d(road) p50 |
|---|---|---|
| field_empire | **600 cm** | 2 200 cm |
| desert | 730 | 2 400 |
| darkforest_coast | 1 131 | 1 542 |
| eastplain | 3 542 | 6 804 |
| snow_field | 3 730 | 3 802 |
| event_instance | 1 094 | 6 625 |
| empire_war | 1 579 | 6 827 |
| arena_pvp | 566 | 1 371 |
| guild_village | 1 000 | 1 600 |
| trent_forest | 7 025 | 10 889 |

Family-level, corpus-wide: `effect/background` d(road) p25/p50/p75 = **0 / 0 / 1 094 cm**
— effects sit *on* the road or plaza; `zone/b/building` 0 / 600 / 1 846;
`zone/b/obj` 0 / 730 / 6 827; `tree/b1` 400 / 1 600 / 7 273; `tree/b3` 1 003 / 2 989 /
16 102. The upper quartiles are what create the "wilderness behind the treeline".

Distance to water (`water.wtr` wet cells): `zone/n/obj/snow.m` p50 = 849 cm — the snow
prop set is a *lakeside* set; `zone/secretdungeon` and `zone/otherworld` p50 = 0 cm
(placed directly on the water plane); `tree/n2` p50 = 20 009 cm — desert flora avoids
water, which is the opposite of intuition but consistent (oases in this corpus are
prop-decorated, not planted).

Distance to map edge: p50 ≈ 15 000–30 000 cm everywhere. There is no border avoidance
rule beyond "the outer sectors are usually cliff/blocked terrain and get less content".

---

## 6. Set-pieces — what goes next to what

`cooccurrence.json` reports, for radii of 5 m / 15 m / 40 m, the observed number of
co-located CRC pairs against `E = n_a · n_b · πr² / A` summed per map (complete spatial
randomness). `lift = O/E`. These are the hand-composed groupings; reproducing them is
most of what makes a map look authored.

**Camp / storage cluster** (the single strongest motif in the corpus, `zone/b/obj`):

| pair @ 5 m | obs | lift |
|---|---|---|
| `ob-b1-005-woodbarrel` + `ob-b1-001-box01` | 148 | ×722 |
| `ob-b1-001-box02` + `ob-b1-001-box01` | 139 | ×956 |
| `ob-b1-001-box02` + `ob-b1-001-box03` | 131 | ×968 |
| `ob-b1-005-woodbarrel` + `ob-b1-001-box03` | 137 | ×592 |
| `general_obj_tent01` + `general_obj_woodbed` | 35 | ×1 720 |
| `general_obj_jar_yellow01` + `general_obj_jar_yellow02` | 29 | ×2 272 |
| `general_obj_jar_red01` + `general_obj_jar_yellow01` | 31 | ×1 798 |

Self-clumping (same CRC within 5 m) is just as strong: `ob-b1-001-box01` ×1 804
(obs 107), `ob-b1-001-box03` ×1 792 (obs 88), `ob-b1-005-woodbarrel` ×747 (obs 267).
**Crates come in threes, not ones.**

**Fence runs**: `fortMS_fence_body02` + `fortMS_fence_pillar` obs 42 @ 5 m, ×1 215 —
a body/pillar alternation. `general_obj_fence03` + `fence01` obs 235 @ 15 m, ×91;
`fence03` + `fence02` obs 228, ×115. Fences are placed as sequences of 3–5 segments,
`zone/n/obj/map_n_desert_01` fence CRCs alone account for 460 of that family's 1 122
records.

**Desert scrub**: `CinnamonFern_RT_02` + `CinnamonFern_RT_01` obs 300 @ 5 m (×111);
`CinnamonFern_RT_02` + `_03` obs 273 (×294); `AloeVera_RT_Flowers_01` +
`CinnamonFern_RT_01` obs 120 (×153); `cactus_04` + `CinnamonFern_RT_01` obs 139 (×736);
`cactus_04` + `cactus_05` obs 31 (×2 653). Desert vegetation is planted in mixed
2–5 m patches of 3–4 species, never as isolated specimens.

**Fire set-piece**: `general_obj_campfire` (Building, the wood pile) →
`fire_general_obj_campfire.mse` (Effect, the flame): of the campfire buildings that
share a map with the effect, **84 % have a flame within 100 cm (median offset 7 cm,
n = 19)**, and the effect carries a +570 cm bias to lift the particle to flame height.
Its 15 m companions are `general_obj_woodchair` (obs 53, ×367), `general_obj_tent02`
(obs 21, ×82), `B_general_obj_22` (obs 31, ×84) and crates. That is a camp: fire,
chairs, tent, crates, inside a 15 m circle.

**Effects are not generally parasitic on props.** Corpus-wide, only 4.1 % of Effect
placements lie within 100 cm of a non-Effect object (n = 8 117, median distance
1 717 cm). The anchored ones are specific: `fire_ob-11-02-stonelight01.mse` 100 %
within 1 m (n = 36), `metinstone_loop_4_orange.mse` 91 % (n = 35), `warpgate03` 56 %
(n = 27). Everything else — resource sparkles, volcano smoke, waterfalls — is placed
free-standing.

**Family-level affinities @ 15 m** (`cooccurrence.json.family_pairs`):
`zone/ghost/obj` with itself ×663, `zone/b/obj` + `zone/ghost/obj` ×402,
`zone/n/obj/map_n_desert_01` + `zone/n/obj/snow.m` ×340 (the two "generic outdoor prop"
sets are used interchangeably in mixed-biome maps), `effect/background` +
`zone/defensewave` ×149.

For a generator, `cooccurrence.json.companions_15m[crc]` gives, per CRC, its ten most
frequent and ten highest-lift neighbours — e.g. `Pagoda1` (569394331) →
`Pagoda3` (64, ×4.1), `Pagoda2` (61, ×3.8), `Beech4` (50, ×4.4),
`MontereyCypress4` (41, ×5.4), `ob-bigstone03` (31, ×8.0). Even the forest is a
recipe: three Pagoda variants + Beech + Cypress + the occasional boulder.

---

### 6.w A fence is a RUN, not a scatter

Measured over **2,308** fence placements on 47 maps, pooling all 53 fence
models:

| | |
|---|---|
| fences living in a run of 3+ (linked at 600 cm) | **62 %** |
| longest run | **33** segments |
| gap between adjacent panels | p25 241 · **p50 361** · p75 392 cm |
| turn between consecutive panels | **p50 18°** |

So a fence is panels laid end to end on a **3.6 m pitch**, each rolled tangent
to the line, turning gently — a windbreak or a stock pen, curving. Placed as a
density with a per-record roll it reads as scattered debris, which is what it
was on the first pass.

> **Rule:** copy a shipped set-piece whole rather than generating one —
> `gen/setpiece.py` `extract` + `stamp`. `ObjectTier.positions` takes
> `(x, y, roll)` triples precisely for this.

**A computed pitch leaves gaps, and the reason is the models.** The six fence
models are *different lengths*, which is why the shipped runs mix them — the
short ones close what the long ones leave. Generating an arc from the corpus
median pitch of 361 cm with one model gives panels that do not meet, because
`general_obj_fence03` is not 361 cm long. The real run at (333, 307) in
`metin2_map_n_desert_01` steps **232, 232, 362, 521 cm** through
fence05 → 04 → 03 → 02 → 01.

So take the geometry verbatim — and take **the whole set-piece**, not a run
lifted out of it. The camp at (333, 307) is not one enclosure: it is **two
rails, of 5 and 6 panels, one either side of three tents**, with a brazier and
its stall clutter behind and the planting between. Chaining "the nearest
unvisited fence within 12 m" from a seed panel walked across both rails and
into a third, and produced a 20-panel "template" that exists on no map — a blob
of several runs stamped over each other, which is what "no spatiality" looks
like. The dump that settled it was the plain one: every record within 32 m of
the point, as the file has them.

`gen/setpiece.py` does exactly that and nothing cleverer: `extract(map_dir,
(333, 307), 32)` returns the 32 records as offsets with their own roll and
`height_bias`; `stamp(pieces, anchor)` turns them into one authored tier per
`(crc, bias)` at the new anchor. Rendered from the same camera as the source,
the copy is indistinguishable — rail A steps match the source's 520 / 362 /
231 / 237 cm to the centimetre the pasted table rounds to, rolls identical.
Three rules when reusing one:

- **Copy the compound, not the fence.** The rail is placed against the tent; on
  its own it is a curve with nothing to curve around. Take everything inside the
  radius — the source stamps its trees with the same headings as its buildings
  (105 / 285 / 315 across all 32 records), which is the tell that the whole
  thing was turned as a unit.
- **Do not rotate a copied piece — stamp it as it stands.** Rotating one turns
  the offsets *and* the rolls, which looks correct and is not: the offsets are
  y-down tile coordinates and `roll` is a compass heading, and the two frames do
  not agree in handedness. The panels come apart, and **no measurement of the
  template alone shows it** — the rotated template still reports a 2.4 m median
  spacing against the corpus's 3.0. It only shows in a render. Until the
  relationship between the two frames is pinned down, `setpiece` has no
  rotation argument, and a piece that must face another way needs a different
  source.
- **Render the reference before comparing.** The blob passed every statistic it
  was checked against; a headless render of `n_desert_01` at the same target
  and camera exposed it in one frame. Two rails and three tents cannot be told
  from one 20-panel run by spacing percentiles.

The source stands on one plane (31 of 32 records at z 17,826; the outlying palm
58 cm lower): level a pad under
the target with `PlazaSpec(tile_index=0, safezone=False)` sized to `extent_m`,
and check `relief_cm` of the source before assuming any other piece was flat.

**Pool the family for this question.** Any *single* fence model is **84 %**
singletons and the per-CRC nearest-neighbour reads 975 cm, which says "scatter"
and is wrong: real runs are built from mixed models, so the chain is invisible
until you pool them. That is the mirror image of the trap in
`failure-atlas.md` §3.9 — there a pooled figure hid a per-CRC rule, here a
per-CRC figure hides a family rule. Neither level is automatically right; the
one that matches the *question* is.

### 6.x A compound is placed as a unit, not sampled

Everything above this point describes **scatter**: a density, a spacing, a set
of filters, and the engine picks the spots. A set-piece is the opposite, and
trying to express one as a density fails in three specific ways, all measured:

| | what scatter does | what the piece needs |
|---|---|---|
| position | anywhere the filters allow | `ObjectTier.positions` — "steep and near water" cannot say *which* water; a waterfall came out at the foot of its own drop |
| heading | one draw per record | `ObjectTier.roll_deg` — a warp gate's dais, arch and effect drew **345, 285 and 105** independently |
| companions | independent tiers | co-located by construction — the arch carries its effect in **93 %** of corpus placements, offset p50 **35 cm** |

So: author the parts, give them one heading, and put the paired effect at the
same coordinates. `reference/structures.md` carries the kit geometry — the 10 m
wall module, the 90° snap for structural pieces, and the rule that dressing
inside the same compound does *not* snap.

## 7. The working vocabulary

1 684 CRCs are used at all, but the distribution is steep:

| top N CRCs | share of all placements |
|---|---|
| 25 | 33.7 % |
| 50 | 44.6 % |
| 100 | 57.0 % |
| 200 | 71.2 % |
| **400** | **83.9 %** |
| 600 | 90.5 % |
| 1 000 | 97.1 % |

**400 CRCs is the working vocabulary.** `stats-objects.json.by_crc` carries the full
ranked list; the first 420 rows also carry per-CRC spacing, rotation, bias and slope
statistics.

The most-placed props, excluding the two `haven_dungeon` resource effects that dominate
by sheer count (5 104 + 1 385 in three maps):

| # | CRC | Name | Type | Family | n | maps |
|---|---|---|---|---|---|---|
| 3 | 569394331 | Pagoda1 | Tree | tree/b1 | 746 | 51 |
| 4 | 2376089798 | Pagoda2 | Tree | tree/b1 | 690 | 44 |
| 5 | 3689520799 | Beech4 | Tree | tree/b1 | 662 | 48 |
| 6 | 1107711305 | Pagoda3 | Tree | tree/b1 | 650 | 41 |
| 7 | 2399205967 | Beech2 | Tree | tree/b1 | 532 | 42 |
| 8 | 3455398876 | Beech3 | Tree | tree/b3 | 522 | 41 |
| 9 | 2958806645 | CinnamonFern_RT_01 | Tree | tree/n2 | 473 | 12 |
| 10 | 3748653682 | MontereyCypress3 | Tree | tree/b1 | 450 | 45 |
| 19 | 1471924893 | ob-7-02-01 | Building | zone/b/obj | 336 | 18 |
| 20 | 358206493 | ob-b1-005-woodbarrel | Building | zone/b/obj | 329 | 24 |
| 21 | 1755164826 | fire_general_obj_campfire.mse | Effect | effect/background | 324 | 14 |
| 24 | 1401373405 | ob-7-03-01 | Building | zone/b/obj | 295 | 12 |
| 34 | 538957537 | general_obj_fence03 | Building | zone/b/obj | 227 | 21 |
| 35 | 1535330398 | general_obj_fence01 | Building | zone/b/obj | 220 | 25 |
| 37 | 2767369424 | general_obj_stone11 | Building | zone/b/obj | 206 | 23 |
| 41 | 929619867 | warpgate01 | Effect | effect/background | 190 | 29 |

Breadth matters more than count: `general_obj_stone06` appears in 31 maps,
`warpgate01` in 29, `general_obj_fence01` in 25. **The `zone/b/obj` set (273 CRCs
placed, 10 792 records, 80 maps) is the universal kit** — it appears in every archetype
including 151 records inside block dungeons.

---

## 8. Per-archetype recipes

Each entry: density, mix, the art families that carry the identity, spacing, ground, and
the road/tree relationship. Reference map in brackets.

### field_empire — 18 maps, 8 927 objects [metin2_map_a1]
8.16 obj/ha · 53.5 per sector · 58 % Building / 41 % Tree.
Families: `zone/b/obj` 4 174 (3.81/ha, NN 367 cm), `tree/b1` 2 231 (2.04/ha, NN
1 686 cm), `tree/b3` 1 097, `zone/b/building` 742 (0.68/ha, NN 998 cm), plus the
empire-specific house set (`zone/a/building` 86, `zone/c/building` 131 — this is the
*only* discriminator between a1/b1/c1).
Ground under objects: field 52.6 %, grass 35.9 %, tile 6.2 %, rock 4.5 %; slope p50 0.8°,
p95 22.9°.
Trees: 8 species dominate — Beech1-4, Pagoda1-3, MontereyCypress1-5. Zero `n1`/`n2`.
Buildings sit 600 cm from a road, trees 2 200 cm. Houses on flat grass, props along the
road, forest in the gaps between road loops.

### field_valley — 3 maps, 2 068 objects [map_a2]
4.15 obj/ha · 27.2 per sector · 48 % Building / 52 % Tree. Half the density of
field_empire and no dedicated building set: `tree/b1` 988 and `zone/b/obj` 969 carry
almost everything, `zone/a/building` only 18. Ground field 63.9 % / grass 32.6 %; slope
p50 3.0°. Both buildings and trees have d(road) p50 = 0 — everything is placed on or
beside the path web (roads cover 8.6 % of `map_a2`). Signature props:
`general_obj_stone07/08/11` boulders (86/72/74 records).

### desert — 8 maps, 4 113 objects [metin2_map_n_desert_01]
6.34 obj/ha · 41.5 per sector · 48 % Building / 50 % Tree.
`tree/n2` 1 864 (2.87/ha, NN **342 cm** — patch planting), `zone/b/obj` 1 040,
`zone/n/obj/map_n_desert_01` 641 (NN 243 cm, 90 % on blocked attr — mostly fences).
Ground sand 64.0 %, grass 24.9 %; slope p50 0.9°. Species: CinnamonFern_RT_01/02/03,
AloeVera_RT_Flowers_01/02, JoshuaTree_RT_01/02/03, CurlyPalm_RT_03. Plant them in mixed
clumps 2–5 m apart (§6), never evenly. Buildings 730 cm from road, trees 2 400 cm.

### snow_field — 5 maps, 1 681 objects [map_n_snowm_01]
3.72 obj/ha · 24.4 per sector · **67 % Tree**, and 100 % of those trees are `tree/n1`
(1 128 records; ColoradoBlueSpruce1-3, Beech_Winter1-3, WhitePine2, CommonOlive_Winter,
MontereyCypress_Winter). Tree NN 1 174 cm, sunk −80 cm — the deepest sink of any family.
`zone/n/obj/snow.m` 532 props (NN 886 cm), whose median distance to water is 849 cm: this
is a lakeside prop set. Ground snow 96.8 %; trees never touch lava or sand.

### flame_field — 5 maps, 496 objects [metin2_map_n_flame_01]
**1.24 obj/ha — the emptiest archetype.** 62 % Tree, and the entire flora is two CRCs:
`IvySpy_Winter2` (178) + `IvySpy_Winter1` (116), family `tree/b2`, NN 3 756 cm. 12.5 %
Effect — `volcano_greatsmoke.mse` (40), `volcano_biglongsmoke.mse` (12) — the highest
effect share of any outdoor archetype. Ground rock 76.0 %, tile 13.3 %, lava 10.3 %.
Emptiness *is* the art direction here.

### darkforest_coast — 5 maps, 5 875 objects [metin2_map_capedragonhead]
8.15 obj/ha · 53.4 per sector · 65 % Building / 34 % Tree, on the steepest outdoor
terrain in the corpus (object slope p50 15.3°, p95 50.3°).
`zone/b/obj` 1 765, `tree/b1` 1 311, `zone/devils_dragon_island` 861 (NN 690 cm),
`.../camp` 684 (NN 800 cm), `.../bone` 242, `tree/n2` 464 (mixing arid flora into a
temperate coast — the visual signature).
The camp and bone sets are the identity: `gaint_fence04` (92), `camp_woodhut_fence00/01`,
`fortMS_fence_body02`+`pillar`, whale/turtle bones on black sand (`bone` family is 86.9 %
on sand, d(water) 4 160 cm, 35.6 % standing in water). Bones tilt: yaw ≠ 0 in 26 %,
pitch ≠ 0 in 33 %.

### ice_valley — 3 maps, 1 549 objects [metin2_map_snakevalley]
5.03 obj/ha · 63 % Building. `tree/n1` 492, `zone/n/obj/snow.m` 343,
`zone/snakevalley` 332. The spear-rock set is the signature and the most extreme
placement in the corpus: slope p50 26.3°/p75 40.3°, bias p50 −86 cm, **yaw ≠ 0 in
39.9 % and pitch ≠ 0 in 33.6 %** of records, d(road) p50 10 909 cm. Rocks are jammed
into cliff faces at an angle, far from any path.

### eastplain — 4 maps, 1 507 objects [metin2_map_eastplain_01]
4.60 obj/ha · **86.5 % Building**, the most building-dominated outdoor archetype.
`zone/eastplain` 932 (2.84/ha, NN 867 cm, 98.2 % on blocked attr, ground grass 51.8 % /
rock 27.9 %). Signature CRCs `double_01..04` (72/65/65/60) and `gaint_fence04_d/05_d`.
Trees are decoration only (192 records, 12.7 %). Everything is far from roads
(buildings 3 542 cm, trees 6 804 cm) — this is wilderness ruin, not settlement.

### empire_war — 3 maps, 575 objects [metin2_map_empirewar02]
7.31 obj/ha on 2×2 sector arenas. 79 % Building, and the prop set follows the seasonal
skin exactly: `zone/n/obj/snow.m` 148 / `zone/b/obj` 153 / `zone/n/desert` 147 in the
three variants. Signature: the `*-bigdam-*` siege-wall family (`snow-bigdam-02` 44,
`desert-bigdam-02` 30, `ob-bigdam-03/04`). Object slope p50 0.0° — siege ground is flat.

### arena_pvp — 6 maps, 1 226 objects [metin2_map_oxevent]
**12.47 obj/ha, 81.7 per sector — the densest archetype.** 84.6 % Building.
`zone/b/obj` 530 (5.39/ha, NN 255 cm), `zone/b/building` 180, `zone/duel` 179 (the
`a1-038-wall-lin2_duel` ring wall, 149 records, NN exactly 1 000 cm — a wall kit).
Ground grass 42.2 % / field 37.0 % / **tile 16.2 %**; slope p50 0.0°. Buildings sit 566 cm from paved ground. Build a flat paved ring, wall it with a repeating segment at 10 m
pitch, fill with props at 2.5 m.

### guild_village — 4 maps, 541 objects [metin2_guild_village]
11.79 obj/ha · 77.3 per sector · 74 % Building. `zone/b/obj` 362 (7.89/ha, NN 288 cm) —
almost pure generic kit — plus 122 `tree/b1`. Notable: object slope p50 13.2°, p95
56.7° (the guild village is carved into a hillside) and tile ground 16.5 %.

### trent_forest — 2 maps, 608 objects [metin2_map_trent02]
4.64 obj/ha · 62.5 % Tree, `tree/b1` 303 + `tree/b3` 77 with NN **2 729 cm** — the most
widely spaced temperate forest in the corpus (a night forest reads as sparse silhouettes).
`zone/b/obj` 216 boulders. Ground grass 50.8 % / field 44.1 %. Furthest from roads of
any outdoor archetype (trees 10 889 cm).

### elemental — 4 maps, 965 objects [metin2_map_elemental_01]
**1.91 obj/ha and 87.1 % Tree** — the purest vegetation archetype, with only 89 building
records in four maps. Four tree families mixed roughly evenly (`n1` 310, `b2` 237,
`b1` 187, `n2` 85): `IvySpy_Winter2`, `Tulip_Winter1`, `CommonOlive_Winter`, Beech,
ColoradoBlueSpruce, WhitePine. Tree d(road) p50 = 200 cm — the paths run through the
trees. Object slope p50 11.7°.

### event_instance — 10 maps, 3 895 objects [metin2_12zi_stage]
4.61 obj/ha on small bespoke stages. Each member owns one art family:
`zone/dungeon/temple_dungeon` 667 (NN **29 cm** — a tightly nested statue/wall kit),
`zone/geuglagsa` 484 (wall kit at 900–1 000 cm, 98 % 90°-snapped),
`zone/n/obj/map_n_desert_01` 340, `zone/treasure_hunt` 150. Trees 34 % but scattered
6 625 cm from roads. If you build an instance stage, invent one prop family and use it
for 60–90 % of the objects.

### dungeon_block — 18 maps, 10 232 objects [metin2_map_skipia_dungeon_02]
6.73 obj/ha · **72 % Effect, 23 % DungeonBlock, 4.7 % Building, 0 Tree.**
`zone/dungeon/haven_dungeon` alone is 7 602 records across 3 maps: `smallb_resorce`
(5 104) and `smalla_resorce` (1 385) resource sparkles at a 1 155–1 161 cm pitch with
+356 / +1 519 cm bias, plus `skipia_collision` (324) and the `skipia_pass*` corridor
blocks. Ground is one texture (field 98.5 %), slope p50 0.0°, no roads and no water.
Corridor kits: `mt_thunder_passage01-03` at 1 200 cm, `maze/monkey_dungeon_cave0*` at
3 860 cm, `anglar_*` at 3 000/5 091 cm. Rolls are multiples of 90° in 98.9–100 % of every kit; bias is a single
constant per kit (`maze_dungeon` +20 cm on 98.9 % of records, `anglar_dungeon` +5 cm on
~100 %).

### dungeon_themed — 12 maps, 4 334 objects [metin2_map_dawnmist_dungeon_01]
4.19 obj/ha · 65 % Building / 21 % DungeonBlock / 7 % Tree — the mix that separates it
from `dungeon_block`. One dedicated family per map: `zone/secretdungeon` 751 (flowers,
NN 283 cm, on the water plane at d(water) 0), `zone/otherworld` 619 (skeletons on lava,
69.5 % lava ground), `zone/dungeon/dawnmistwood_dungeon` 618 (slope p50 18.7° — the
steepest interior), `zone/whitedragoncave/whitedragoncave_01` 301 (on `black.dds`),
`zone/dungeon/flame_dungeon` 236 (82.8 % rock, 11.5 % lava).
Trees appear, and they are `tree/b2` (IvySpy dead vines, 209 of 313).

### dev_stub — 4 maps, 182 objects [metin2_map_t1]
2.31 obj/ha, generic `zone/b/obj` + b-family trees only. `metin2_map_t1` is also the
one map where the *engine* loads fewer objects than the file contains: its nine
`areadata.txt` files each carry two `ObjectCount` lines and the tokenizer is first-wins,
so 44 of 121 blocks load. Use it as a negative example, not a template.

---

## 9. Procedure — placing objects convincingly

1. **Pick the archetype**, then take its density from §2 and multiply by your terrain
   area. A 4×5-sector empire field at 8.16 obj/ha over 1 310 000 m² ⇒ ~1 070 objects
   (metin2_map_a1 ships 1 226).
2. **Split by type** using the archetype's mix (§2). Outdoor: never emit DungeonBlock.
   Interior: never emit Tree.
3. **Lay the road web first.** It is the skeleton everything else references — buildings
   at 4–8 m from it, trees at 15–25 m, effects on it.
4. **Place buildings on flattened ground** (slope < 8°), snapped to the road, spaced
   9–13 m, roll a multiple of 15° with a bias toward 90/180/270, bias 0. Stamp the
   footprint into `attr.atr` as blocked.
5. **Plant trees by species-group**, one group per biome (§4.1). Temperate 10–17 m
   between trunks, arid 2–8 m, and always with a long tail: clumps of 3–5 within 7 m,
   then gaps of 30–40 m. Two thirds get roll 0; the rest a multiple of 15°. Sink them:
   `b1` −45 cm, `b3` −35, `n1` −80, `n2` −15.
6. **Scatter props in packs, not singly.** 60 % of `zone/b/obj` records have another prop
   within 5 m. Use `cooccurrence.json.companions_15m` to pick the partners — crates with
   barrels, fences in runs of 3–5, jars in pairs, a campfire with chairs and a tent.
7. **Add effects last, on landmarks**, raised 250–600 cm, roll usually 0, and give them
   the most *regular* spread of anything on the map (they are the only family with a
   Clark-Evans R above 1).
8. **Do not quantise positions.** Free-hand cm values; only dungeon kits are integral.

---

## 10. Traps and caveats

* **`tile.raw` byte N indexes TextureSet slot N, where slot 0 is the eraser.** Using
  `TextureSet.textures` (which is `slots[1:]`) shifts every lookup by one and turned
  `metin2_map_a1`'s road web into "26 % of the map is pavement". Use
  `TextureSet.get(byte)`.
* **`tile` ≠ road.** In the B-family empire palettes the road network is painted with
  `b/field/field 01.dds`; `b/tile/tile01.dds` covers only the 0.21 % town plaza of a1.
  Any rule written against texture names will be wrong on at least one biome.
* The sibling `catalog/textures.json` classifies palette slots by a different rule
  (`path` = < 4 % cover, very solid, flat) and labels a1's `b/field/field 01.dds` as
  `base`, not `path`. Both classifications are defensible at their own granularity;
  this document's road masks were visually verified against the rendered tile grids
  (see §5), so where the two disagree, use this one for *distance-to-road* and
  `textures.json` for *palette composition*.
* **Property type is not the object's nature.** 1 369 of the 1 684 placed CRCs are
  `Building`, including every rock and shrub. Family is the useful key.
* `metin2_map_treasure_hunt` writes `CRC#sx#sy#sz` in field 3 (288/288 records) — the
  only map that does. `int(token)` throws; split on `#` and take element 0. The codec
  already handles it and exposes the scale triple as `ObjectRecord.scale`.
* Object counts here (48 774) differ from `map-taxonomy.json` (48 851) by exactly the
  77 `metin2_map_t1` blocks that the client never loads (duplicate `ObjectCount`,
  first-wins). This document counts what the engine loads.
* Two families still carry Korean folder names (`zone/공용`, CP949 decoded from the
  latin-1 text codec). They are small (38 + 4 records) but real.
* Clark-Evans R per family is computed against the archetype's **total** terrain area, so
  a family that only exists in one corner of one map reads as extremely clustered. That
  is the intended signal (objects are not spread over the map), but do not read R as a
  within-cluster statistic.
* 12 of the 245 ground textures that appear under an object cannot be colour-verified:
  `g/field/field 03/04`, the five `guild_battle/*`, `n/snow.m/ice_quest`, and the four
  `treasure_hunt/*` are referenced by shipped texturesets but absent from the extracted
  `D:/ymir work/terrainmaps` dump. They are flagged `missing_on_disk` in
  `affinity.json.texture_catalog`. One textureset entry also ships a stray leading slash
  (`/b/tile/tile01.dds`); the catalog probes the unslashed path too.
* Distances use a 5×5 chamfer metric (worst case 2.8 % off Euclidean, mean 1.3 %) on the
  200 cm cell grid; nothing in this document is binned finer than 100 cm, so the
  approximation never changes a conclusion.

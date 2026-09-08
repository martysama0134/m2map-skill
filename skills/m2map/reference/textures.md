# Terrain Texture Palettes — Vocabulary, Roles and Per-Archetype Recipes

What a `textureset/*.txt` actually contains, what each slot is *for*, and the
canonical palette composition of every map archetype in the corpus.

Companion data: [`catalog/textures.json`](catalog/textures.json) — every texture,
every slot, every measured number quoted below.
Archetype partition: [`catalog/map-taxonomy.json`](catalog/map-taxonomy.json).
Format spec: [`mapformat/client-global-refs.md`](mapformat/client-global-refs.md) §1,
[`mapformat/tile-raw.md`](mapformat/tile-raw.md).

---

## 1. The mechanism, in one screen

A map's `setting.txt` names one `textureset/<name>.txt`. That file is an ordered
list of `.dds` paths — the palette. Every byte of every `tile.raw` is an index
into it. Nothing else selects ground art.

- **Slot 0 is the built-in eraser.** `TextureCount` excludes it; `tile.raw` byte 0
  means *unpainted*. Blocks are `Texture001..TextureNNN`, 1-based, and block *N*
  fills slot *N*.
- **One tile = 100 cm = 1 m.** A sector holds 256x256 tiles stored as a 258x258
  grid with a 1-tile skirt duplicating the neighbours.
- **Painter's order is index order.** `RAW_GenerateSplat` builds the alpha layers
  from index 1 upward, so a higher slot number paints *over* a lower one
  (`GameLib/AreaTerrain.cpp:646-768`). Slot position is therefore a design
  decision, not just bookkeeping — see §4.
- **UV:** `scale = (1 / (16 * 200)) * UScale`, so the texture repeats once every
  **32 / UScale metres**. `UScale 5` -> 6.4 m, `UScale 2` -> 16 m, `UScale 9` -> 3.6 m.
- `UOffset`/`VOffset`, `bSplat`, `Begin`, `End` are parsed and stored but never read
  at render time. In the shipped data they are effectively constant — see §7.

## 2. What is on disk

| | count |
|---|---|
| `.txt` files in `textureset/` (top level) | 99 |
| ...of which are actually TextureSet scripts | 96 |
| ...of which are pack-build manifests misfiled here | 3 (`metin2_siege_01.txt, metin2_siege_02.txt, metin2_siege_03.txt`) |
| winter re-skins in `textureset/snow/` | 78 |
| texture entries across the 99 top-level sets | 1032 |
| distinct `.dds` paths referenced | 354 |
| ...present under `D:/ymir work` | 292 (288 under `terrainmaps/`, 4 under `zone/`) |
| ...**referenced but absent** | 62 |
| `.dds` files under `terrainmaps/` on disk | 383 (+23 stray `vssver.scc`) |
| ...never referenced by any palette | 95 |
| texturesets loaded by at least one corpus map | 70 of 99 |
| declared slots in those 70 sets | 774 |
| ...never painted by any map that loads them | 134 (**17.3%**) |

22 of the 99 top-level sets are byte-for-byte duplicates of another
(7 md5 groups). The largest group is seven files —
`metin2_a1.txt`, `metin2_b1.txt`, `metin2_c1.txt`, `metin2_b_fielddungeon.txt`,
`metin2_map_n__trent.txt`, `metin2_map_otherworld_02.txt`, `metin2_map_t1.txt` —
one identical 17-slot `terrainmaps/b/**` palette serving three different empires
and a dungeon. **The palette does not identify the map; the paint does.**

---

## 3. The role taxonomy

Roles were **not** read off filenames. Every `(textureset, slot)` pair was scored
against the 114 corpus maps that ship their own terrain: all 1,341 `tile.raw`
sectors were stitched into per-map label grids, and each slot measured for

- **ground share** — its fraction of all painted tiles in the maps that load the set;
- **clump (0-8)** — mean number of the 8 neighbours that carry the same index.
  This is the workhorse. 8 = solid interior, ~4 = checkerboard dither, ~1 = speckle;
- **solid / core fraction** — share of the slot's tiles surviving 1 / 2 erosions;
- **slope** — mean terrain slope under those tiles, from `height.raw`
  (129x129 vertices per sector, `worldZ = raw * HeightScale`, cell = 200 cm),
  plus the ratio to the map's own mean slope (`slope_enrich`);
- **water context** — share of tiles within 2 cells (4 m) of a `water.wtr` cell,
  and the ratio to the map's baseline;
- **luminance** — mean brightness of the decoded `.dds` (smallest useful mip).

The cascade below is applied in order; the first match wins.

| role | what it is | measured rule |
|---|---|---|
| `void` | pure-black "no terrain" fill under block dungeons | decoded luminance < 0.03 |
| `shore` | water margin: beach, riverbed, wet sand | >=70% of tiles within 4 m of water **and** >=1.6x the map baseline **and** slope < 25 deg (skipped where the whole map is waterfront) |
| `base` | the dominant contiguous ground carpet | ground share >=25% with clump >=5.2 (or >=12% with clump >=5.2 and solid >=20%) |
| `cliff` | rock skin confined to steep faces | mean slope >=28 deg (or >=60% of tiles above 20 deg) **and** >=1.25x the map's own mean slope |
| `path` | road, paved trail, plaza | ground share <4% **but** clump >=6.0, solid >=35%, slope <15 deg |
| `mid` | secondary ground stippled over the base | ground share >=1.5%, nothing above matched |
| `accent` | rare decorative speckle | ground share <1.5% |
| `unused` | dead slot | 0 tiles in every map that loads the set |
| `empty` | `TextureCount` covers the slot but no `Texture%03d` block exists | tile bytes here draw the error texture |

Result over the 774 declared slots of the 70 loaded sets:

`mid` 193 · `cliff` 134 · `unused` 134 · `accent` 128 · `base` 86 · `path` 42 ·
`shore` 33 · `void` 22 · `empty` 2.

### `interior` was tested and dropped

The brief proposed `interior` (dungeon floor) as a role. It does not survive
contact with the data: dungeon-art textures behave *functionally* exactly like
outdoor ones. `dungeon/devilcave/dc_grass_00.dds` is a textbook `base`
(49.3% of `metin2_map_devilscatacomb` + `smhgate_devils`, clump 7.90, 97.5% non-edge);
`dungeon/devilcave/dc_rock_00.dds` is a second `base` at 39.6%;
`dungeon/dawnmistwood_dungeon/dmw_dungeon_tile000.dds` is a `path`
(2.1% cover, clump 6.98, 67% non-edge, slope 4.8 deg). "Interior" is a *palette
family* (`terrainmaps/dungeon/**`, `zone/dungeon/**`), i.e. an art-pack axis,
not a usage class. `textures.json` carries it as `family`, alongside a `motif`
token parsed from the filename.

What *is* a distinct interior role is **`void`** — and it is much starker than
"dungeon floor" suggests: see §6 `dungeon_block`.

### The role a filename claims is not the role it plays

Filename motif and measured role agree only loosely. Same file, opposite jobs:

| texture | in | share | clump | slope | role |
|---|---|---|---|---|---|
| `b/stone/stone01.dds` | `metin2_guild_war4.txt` | 77.5% | 7.59 | 36 deg | `base` |
| `b/stone/stone01.dds` | `metin2_a1.txt` | 16.7% | 5.28 | 38.5 deg | `cliff` |
| `n/desert/sand/sand02.dds` | `metin2_wl_01.txt` | 47.2% | 7.01 | 15.5 deg | `base` |
| `n/desert/sand/sand02.dds` | `metin2_n_desert1.txt` | 26.2% | 4.00 | 6.1 deg | `mid` |
| `a/beach/beach water.dds` | `metin2_map_defensewave.txt` | 59.0% | 7.94 | 2.3 deg | `base` (flooded map) |
| `capedragonhead/capedragon_cliff002.dds` | `metin2_capedragonhead.txt` | 40.6% | 7.22 | 32 deg | `base` |

Roles in `textures.json` are therefore stored **per `(textureset, slot)`**, with a
`dominant_role` rolled up per texture by tiles painted.

That is the whole of the caveat, and it is narrower than it looks. The filename
is a weak *classifier* and a strong *prior*: knowing a slot is called `stone02`
does not tell you it is the cliff in this map, but if you need a cliff, `stone*`
is what you reach for 62% of the time. Sec 4f measures the prior in both
directions — it is the table to use when composing a new palette, and sec 3's
table is the one to use when reading an existing one.

---

## 4. Cross-cutting composition rules

**(a) Slots are ordered by art-folder motif, not by role.** The classic 17-slot
empire palette is literally the `terrainmaps/b/` folder listing:
`field 01..04`, `grass 01..03`, `stone01..04`, `tile01..02`, `beach sand 01..03`,
`tile03`. Because painter's order is index order, that convention *incidentally*
produces the right layering — roads and beaches are near the end and overpaint
the ground. Mean normalised slot position (0 = first slot, 1 = last), over the
loaded sets with >=4 slots:

| role | n | mean slot position |
|---|---|---|
| `mid` | 193 | 0.444 |
| `base` | 86 | 0.445 |
| `shore` | 33 | 0.556 |
| `cliff` | 134 | 0.561 |
| `void` | 16 | 0.585 |
| `accent` | 128 | 0.601 |
| `unused` | 132 | 0.630 |
| `path` | 42 | 0.666 |

Base and mid first, path last. Put a road at slot 1 and the ground will paint over it.

**(b) `UScale` tracks texture resolution, not role.** This kills the "UV scale
tells you the role" hypothesis. Median `UScale` by decoded texture width:
**128 px -> 5.0**, **256 px -> 5.0**, **512 px -> 4.0**, **1024 px -> 2.0**.
Median by role only spans 3.0-5.0. The invariant the artists actually held is
**texel density**: median 48 px/m over all 967 measurable entries
(p10 32, p90 96); by role it moves only between 32 and 64 px/m.
Rule of thumb for a new entry: `UScale ~= 1536 / texture_width_px`, then clamp
into the shipped 1-10 band.

**(c) Ground is painted as a dither, not as regions.** This is the single most
important thing to reproduce. The corpus median run length of a texture index
along either axis is **2 tiles** (n = 786 slot/map pairs carrying >=500 tiles;
489 of them sit at exactly 2, 157 at 1), and the typical `mid` slot has 0-5% of its
tiles surviving a single erosion. Example — `metin2_a2.txt` across all four maps
that load it (`map_a2`, `map_n_threeway`, `metin2_map_guild_01`,
`metin2_map_smhgate_threeway`), 4,980,734 painted tiles:

| slot | texture | share | clump | solid | slope | role |
|---|---|---|---|---|---|---|
| 5 | `a/stone/stone01.dds` | 45.37% | 6.27 | 54.2% | 47.9 deg | `base` |
| 6 | `a/stone/stone02.dds` | 20.49% | 4.28 | 7.1% | 50.9 deg | `cliff` |
| 3 | `a/grass/grass 01.dds` | 15.35% | 5.11 | 23.0% | 7.8 deg | `mid` |
| 1 | `a/field/field 01.dds` | 9.98% | 5.96 | 41.4% | 11.8 deg | `mid` |
| 4 | `a/grass/grass 02.dds` | 8.36% | 3.71 | 0.3% | 7.9 deg | `mid` |
| 8 | `a/tile/tile02.dds` | 0.009% | 6.30 | 36.8% | 4.3 deg | `path` |
| 9-10 | `a/beach/beach sand 01/02.dds` | 0.00% | - | - | - | `unused` |

`grass 02` covers 8.4% of the ground and yet **0.3%** of its tiles have all eight
neighbours the same — it exists purely as noise sprinkled through `grass 01`.
Meanwhile `tile02` covers 427 tiles in total and is *more* solid than most of the
palette: that is a road. And `stone01`/`stone02` are the base/cliff pair — same
folder, same "stone" name, 45% versus 20%, separated only by the fact that
`stone02` sits on 50.9 deg ground with almost no interior.

**(d) A palette carries far more than it uses.** 17.3% of all declared slots are
never painted, and the tail sets are worse: `metin2_map_t2.txt` paints 6 of 17,
`metin2_b_fielddungeon.txt` 5 of 17, `metin2_map_treasure_hunt.txt` 10 of 17.
Palettes are copied wholesale and then over-painted.

**(e) `textureset/snow/` is a mechanical motif substitution, not new art.**
All 78 files pair 1:1 with a top-level set, keep the slot count and keep the
UV scales in 734 of 818 slots. Every texture is remapped onto the small
`terrainmaps/n/snow.m/` pack by motif:

| source motif | -> snow texture | agreement |
|---|---|---|
| `field*` | `n/snow.m/field 01.dds` | 204/227 (90%) |
| `stone*` | `n/snow.m/stone01.dds` | 130/149 (87%) |
| `grass*` | `n/snow.m/snow01.dds` | 129/148 (87%) |
| `tile*` | `n/snow.m/snow03.dds` | 95/117 (81%) |
| `beach`/`sand*` | `n/snow.m/snow01.dds` | 69/91 (76%) |
| `cliff*` | `n/snow.m/stone01.dds` | 13/21 (62%) |
| `valcano*` | `n/snow.m/snow02.dds` | 13/21 (62%) |

That table is the artists' own motif classification, and it is directly reusable
for re-skinning a generated palette.

**(f) The filename motif is a strong prior on the job.** Sec 3 warns that the
name is not the role, and that is true per slot. Pooled, the naming convention
is real and usable. Two directions, both measured over the **outdoor** corpus
(interiors excluded: dungeon black-fill is filed under `field*` and swamps the
tile-weighted counts).

*Given a role, what is it called* — P(motif | role), one vote per painted slot:

| role | n | 1st | 2nd | 3rd |
|---|---|---|---|---|
| `cliff` | 94 | **stone 62%** | cliff 11% | other 9% |
| `path` | 28 | **tile 64%** | field 18% | other 7% |
| `shore` | 20 | **sand 55%** | field 15% | other 15% |
| `mid` | 130 | grass 35% | field 34% | tile 9% |
| `base` | 53 | field 25% | grass 19% | stone 15% |
| `accent` | 86 | field 38% | tile 20% | grass 20% |

*Given a name, what does it do* — P(role | motif), one vote per painted slot:

| motif | n | `base` | `mid` | `cliff` | `path` | `shore` | `accent` |
|---|---|---|---|---|---|---|---|
| `stone*` | 105 | 17% | 10% | **67%** | 0% | 0% | 7% |
| `grass*` | 118 | 14% | **53%** | 9% | 2% | 4% | 20% |
| `field*` | 156 | 10% | **42%** | 2% | 5% | 5% | 27% |
| `sand*` | 48 | 15% | 23% | 8% | 4% | **27%** | 23% |
| `tile*` | 83 | 6% | 23% | 2% | **34%** | 1% | **34%** |
| `cliff*` | 23 | 44% | 0% | **52%** | 0% | 0% | 4% |
| `rock*` | 13 | 31% | 0% | **54%** | 0% | 0% | 15% |

Physical character, tile-weighted, over the whole corpus:

| motif | slots | mean share | clump8 | solid | mean slope |
|---|---|---|---|---|---|
| `stone*` | 105 | 29.4% | 6.23 | 51.5% | **41.7°** |
| `cliff*` | 23 | 35.4% | 6.83 | 63.8% | **39.1°** |
| `rock*` | 13 | 38.5% | 7.34 | 78.7% | 28.7° |
| `grass*` | 118 | 23.7% | 5.57 | 36.5% | 14.9° |
| `sand*` | 48 | 25.6% | 6.22 | 52.9% | 11.2° |
| `tile*` | 83 | 9.3% | 6.50 | 58.0% | **6.4°** |
| `field*` | 156 | 70.5% | 7.28 | 80.2% | **5.7°** |

> **Rule:** compose a palette by motif — `stone*` for the massifs, `field*` for
> ground and roads, `grass*` for green cover, `sand*` for shore and riverbed,
> `tile*` for the paved disc. Then set `role` from the job you intend, not from
> the name, because the generator reads `role` and nothing else.

**(g) `path` is two different features wearing one label.** The tables above
disagree with themselves: `path` slots are 64% `tile*`, yet the most-painted
`path` file in the corpus is `b/field/field 01.dds`. Both are true, because two
unrelated features share the role. Splitting the 28 outdoor `path` slots by
motif:

| | slots | total tiles | median tiles/slot | median half-width | solid |
|---|---|---|---|---|---|
| `field*` roads | 5 | 315,289 | 41,301 | 9 tiles | **0.36–0.56** |
| `tile*` discs | 18 | 272,106 | 4,648 | 13 tiles | **0.84–0.87** |

`solid` is the discriminator, and it is not subtle. A road is a dithered ribbon
— barely half its tiles have all eight neighbours the same. A disc is a **flat
fill**: 86% of its tiles are pure interior. It is the one place on an outdoor
map where the stipple is switched off, and that is exactly what makes it read as
*built* rather than *grown*.

**(h) The paved disc is a copy-pasted stamp, and it is the safe zone.** Scoring
every `tile*` connected component by area against its own bounding box (a filled
circle scores π/4 = 0.785, a filled square 1.0) finds 27 at fill **0.70–0.85**
and aspect **1.00–1.10**:

| radius | area (tiles) | maps |
|---|---|---|
| 8.0–8.1 m | 200, 208 | `b1`, `b3`, `smhgate_b1` |
| 9.8–10.0 m | 303, 310, 311, 316 | `a3`, `c1`, `smhgate_c1`, `guild_battle` |
| 14.0 m | 616 | `b3` |
| 17.9–18.0 m | 1,007, 1,020 | `wedding_01`, `c3` |
| 19.6–20.3 m | 1,205, 1,250, 1,264, 1,297 | `a1`, `smhgate_a1`, `capedragonhead`, `guild_war2`, `t1` |
| 21.3–22.1 m | 1,422, 1,528 | `a3`, `b1`, `smhgate_b1` |
| 25.1 m | 1,980 | `c1`, `smhgate_c1` |

The areas recur **verbatim** across unrelated maps — 1,264 tiles in
`metin2_map_a1`, `metin2_map_smhgate_a1` and `metin2_map_capedragonhead`; 316 in
four more — so these are stamps, not hand-painted shapes. Ground under them is
flat (slope 0.0–1.9°).

And they are the safe zone, not merely a decoration of one. Reading `attr.atr`
under each disc:

| | ATTR_SAFEZONE inside the disc | map baseline |
|---|---|---|
| `a1`, `a3`, `b1`, `b3`, `c3`, `guild_war2`, `wedding_01` | **100%** | 0.2–10.9% |
| `c1` | 90.9% | 0.4% |
| `smhgate_a1/b1/c1`, `t1`, `guild_battle`, `capedragonhead` | 0% | **0.0%** |

The zeroes are not counter-examples: those maps have a baseline of 0.0% because
they never wrote the flag at all — `smhgate_*` are paint-only clones of `a1`,
`b1` and `c1`. Where the flag is used, the disc carries it completely.

> **Rule:** a paved disc is a `PlazaSpec` — flat ground, one `tile*` slot filled
> solid with no dither, `ATTR_SAFEZONE` set and `ATTR_BLOCK` cleared, radius 8
> to 25 m. Square rings exist for duels but are rare: only 1 of 138 components
> scored as a filled square.

**Do not "fix" safe-zone cells that also carry block.** Across the 37 maps that
use the flag, **923,325 of 1,282,946** safe-zone cells (72%) are also blocked,
because Ymir paints the safe *area* over a whole town — walls, buildings and
scenery included — and only the disc itself is guaranteed walkable. An audit
rule that flags the overlap fires on almost every shipped map.

**(i) The road rim dithers with a sibling of the road's own motif.** Over the 37
confirmed road maps the blend band is median **3 m** (p25 1, p75 7) and
`hard_edge` is false on every one. What sits in that band is specific — ring-1
share against the far field:

| motif at the rim | n | median enrichment |
|---|---|---|
| `tile` | 8 | 66.96 |
| `field` | 24 | 2.23 |
| `grass` | 46 | 2.16 |
| `sand` | 10 | 0.74 |
| `stone` | 32 | **0.52** |
| `cliff` | 7 | **0.49** |

Worked examples:

| map | road surface | enriched at the rim | depleted at the rim |
|---|---|---|---|
| `map_a2` | `a/field/field 01` | **`field 02` 23.9×**, `grass 01` 2.8× | `stone02` 0.41× |
| `metin2_map_a1` | `b/field/field 01` | `field 04` 4.8×, `grass 02` 2.5×, `grass 01` 2.3× | `stone01` 0.30×, `stone02` 0.32× |
| `metin2_map_n_desert_01` | `sand03` + `field 01` | `grass 02` 4.1× | `stone03` 0.58×, `sand01` 0.80× |

So the road is **one texture down the middle and two at the rim**: its own motif
sibling plus the local ground. The rock motifs are pushed *away* from the rim —
which is the same fact as "roads do not climb mountains", seen from the paint
side rather than the attr side.

**(j) Roads do not cross blocked mountain.** The ratio in `roads.json`
(`block_rate_ratio_inside_over_control`, median 0.49) understates this badly,
because it is a ratio and the surroundings are not uniformly blocked. The
absolute rates, over the same 37 maps:

| | median | p90 |
|---|---|---|
| block rate **inside** the corridor | **5.9%** | 35.5% |
| block rate in the control band | **69.4%** | — |

The land a road crosses is 70% impassable; the road itself is 6%. 27 of 37
corridors are under 15% blocked, 17 of 37 under 5%. The high outliers are
`metin2_map_eastplain_02/03` (38–40%) and `metin2_guild_war1` (45%), all three
maps whose "roads" are mostly plaza and courtyard rather than open-country
route.

> **Rule:** clear the corridor of `ATTR_BLOCK` for its whole length, and route
> it around massifs rather than over them. A road that climbs a blocked slope is
> the single most visible tell of a generated map.

**(k) The cliff is region fill, and (c) does not apply to it.** Rule (c) — the
ground is a dither, not regions — is the most important thing on this page and
it is about **ground**. Rock is the exception. Share of cliff paint surviving a
5×5 opening:

| map | raw | massif | massif ÷ raw |
|---|---|---|---|
| `metin2_map_n_desert_01` | 26.4 % | 26.2 % | 0.99 |
| `metin2_map_a1` | 32.9 % | 32.3 % | 0.98 |
| `metin2_map_a3` | 33.8 % | 33.0 % | 0.98 |
| `metin2_map_b1` | 27.0 % | 26.5 % | 0.98 |
| `metin2_map_c1` | 28.4 % | 27.7 % | 0.97 |
| `metin2_map_capedragonhead` | 3.5 % | 3.3 % | 0.94 |
| `metin2_map_b3` | 17.2 % | 15.8 % | 0.92 |
| `metin2_map_mt_thunder` | 23.5 % | 20.1 % | 0.86 |

`P(cliff | slope)` is a monotone ramp whose turn is per-map — `metin2_map_a1`
reaches 34 % by 15–20°, `metin2_map_n_desert_01` only 12 %, and
`metin2_map_mt_thunder` plateaus at 40 % and never goes higher. Rank by slope,
jitter the ranking so the rock line is not a contour, take what the weights ask
for.

Two consequences that are easy to get wrong:

* **Inside the massif, cliff slots still dither among themselves** — (c)'s
  `metin2_a2` table is one rock face split 45 % `stone01` / 20 % `stone02`.
  Solid means rock-versus-ground.
* **The massif needs minimum thickness.** A ridge two or three tiles wide
  survives a 3×3 smoothing and dies under the 5×5 opening this ratio is measured
  with. Left in, it counts as raw cliff with no massif behind it and pins the
  ratio at 0.78 with 2.4 % of the map's rock stranded more than 20 m from any
  rock face.

**(l) The rock massif has a feathered rim, and then it stops.** Opening the
cliff mask with a 5×5 box recovers the massif independently of the individual
tiles; the raw cliff share measured *outward* from that rim is a decaying tail,
not a step:

| map | +1 m | +2 | +3 | +4 | +5 | +6 | far field (>20 m) |
|---|---|---|---|---|---|---|---|
| `metin2_map_a1` | 9.6% | 6.8 | 3.6 | 2.1 | 1.3 | 0.9 | **0.00%** |
| `metin2_map_n_desert_01` | 4.9% | 3.4 | 2.7 | 1.9 | 1.4 | 1.2 | **0.06%** |
| `metin2_map_b1` | 16.2% | 16.4 | 10.6 | 7.2 | 4.8 | 2.7 | **0.00%** |

Both halves matter. The tail is real — roughly geometric, five to seven tiles
long, so the rock grit is still visible a few paces out onto the sand. And it
**stops**: the far field is 0.00%. Rock is never sprinkled over open ground as
generic noise, which is what a globally-dithered palette would do.

`map_a2` is the instructive exception: its cliff slot survives opening at only
0.2% of the ground, because `a/stone/stone02.dds` there is not a massif skin at
all but a dither partner spread over the whole `stone01` base — 40% near rock,
17.9% in the far field. Sec 4c already showed that pair from the share side;
this is the same fact from the shape side.

---

## 5. How to read a recipe section

Each archetype below gives: the palettes it uses, the reference palette's full
slot->role table, the role budget across *all* its palettes, the `UScale` band per
role, and the textures its maps actually put on the ground (ranked by tiles
painted across every map of the archetype). "ground" percentages in the slot
table are that slot's share of the painted tiles of the maps loading **that**
palette; percentages in the "reaches for" table are shares of the archetype's
whole painted area.

---

## 6. The recipes

### `field_empire` — Empire temperate field and capitals (B-family terrain)

18 maps, 12 palettes, 10,943,634 painted tiles.
Slot count 5-17 (median 14.5). Art families: `b/beach`, `b/field`, `b/grass`, `b/stone`, `b/tile`, `dungeon/devilcave`.

**Reference palette `metin2_c1.txt`** (`metin2_map_c1`, `metin2_map_guild_02`, `metin2_map_smhgate_c1`):

| slot | role | texture | U/V | repeat | ground |
|---|---|---|---|---|---|
| 1 | `mid` | `b/field/field 01.dds` | 5/5 | 6.4 m | 8.00% |
| 2 | `accent` | `b/field/field 02.dds` | 6/6 | 5.3 m | 0.43% |
| 3 | `accent` | `b/field/field 03.dds` | 5/5 | 6.4 m | 0.87% |
| 4 | `base` | `b/field/field 04.dds` | 6/6 | 5.3 m | 15.73% |
| 5 | `mid` | `b/grass/grass 01.dds` | 9/9 | 3.6 m | 13.42% |
| 6 | `mid` | `b/grass/grass 02.dds` | 8/8 | 4.0 m | 11.11% |
| 7 | `mid` | `b/grass/grass 03.dds` | 9/9 | 3.6 m | 1.87% |
| 8 | `cliff` | `b/stone/stone01.dds` | 5/5 | 6.4 m | 23.32% |
| 9 | `cliff` | `b/stone/stone02.dds` | 4/4 | 8.0 m | 5.11% |
| 10 | `cliff` | `b/stone/stone03.dds` | 5/5 | 6.4 m | 0.59% |
| 11 | `cliff` | `b/stone/stone04.dds` | 5/5 | 6.4 m | 3.28% |
| 12 | `path` | `b/tile/tile01.dds` | 5/5 | 6.4 m | 0.26% |
| 13 | `unused` | `b/tile/tile02.dds` | 5/5 | 6.4 m | 0.00% |
| 14 | `shore` | `b/beach/beach sand 01.dds` | 5/5 | 6.4 m | 10.43% |
| 15 | `unused` | `b/beach/beach sand 02.dds` | 5/5 | 6.4 m | 0.00% |
| 16 | `shore` | `b/beach/beach sand 03.dds` | 5/5 | 6.4 m | 5.57% |
| 17 | `unused` | `b/tile/tile03.dds` | 7/7 | 4.6 m | 0.00% |

Role budget across all 12 palettes: base x16, mid x33, cliff x29, path x11, shore x8, accent x23, unused x43.
`UScale` by role (median, range): base 5.5 (2-15); mid 7 (5-15); cliff 5 (4-10); path 5 (3-7); shore 5 (5-6); accent 5 (3-10).

**What the maps actually reach for** (share of this archetype's painted ground):

| share of ground | dominant role (corpus-wide) | texture |
|---|---|---|
| 14.37% | `base` | `b/stone/stone01.dds` |
| 12.24% | `base` | `b/field/field 04.dds` |
| 10.44% | `mid` | `b/grass/grass 01.dds` |
| 9.18% | `base` | `b/grass/grass 01_01.dds` |
| 7.43% | `base` | `b/stone/stone01_01.dds` |
| 5.59% | `mid` | `b/grass/grass 02.dds` |
| 5.23% | `shore` | `b/beach/beach sand 01.dds` |
| 5.02% | `mid` | `b/grass/grass 02_01.dds` |

Other palettes: `metin2_a1.txt` (17 slots, `metin2_map_a1`, `metin2_map_smhgate_a1`, `metin2_map_sungzi`), `metin2_b1.txt` (17 slots, `metin2_map_b1`, `metin2_map_guild_03`, `metin2_map_smhgate_b1`), `metin2_a3.txt` (11 slots, `metin2_map_a3`), `metin2_b3.txt` (11 slots, `metin2_map_b3`), `metin2_b_fielddungeon.txt` (17 slots, `map_b_fielddungeon`), `metin2_battlefield.txt` (5 slots, `metin2_map_battlefied`), `metin2_c3.txt` (11 slots, `metin2_map_c3`), `metin2_guild_war2.txt` (17 slots, `metin2_guild_war2`), `metin2_guild_war4.txt` (17 slots, `metin2_guild_war4`), `metin2_map_wedding_01.txt` (11 slots, `metin2_map_wedding_01`), `metin2_milgyo.txt` (12 slots, `metin2_map_milgyo`).

**Note.** This is the corpus' reference palette and the one to copy. Seven files
share its md5 byte-for-byte — `metin2_a1`, `metin2_b1`, `metin2_c1`,
`metin2_b_fielddungeon`, `metin2_map_n__trent`, `metin2_map_otherworld_02`,
`metin2_map_t1` — so the three empire capitals are *palette-identical* and differ
only in what they paint and which buildings they place. The 17 slots are literally
the `terrainmaps/b/` directory listing in folder order
(`field 01-04`, `grass 01-03`, `stone01-04`, `tile01-02`, `beach sand 01-03`, `tile03`),
which is where the ground-first / roads-last painter's order comes from.
The `_01`-suffixed variants (`field 01_01`, `grass 01_01`, `stone01_01`) are a
later re-colour of the same 11 motifs used by `a3`/`b3`/`c3`/`wedding_01`.
`b/stone/stone01.dds` is the single most-painted texture in the archetype (14.4%)
and flips between `base` and `cliff` depending on the map — see §3.

### `field_valley` — Green valley / three-way field (A-family terrain)

4 maps, 1 palette, 4,980,734 painted tiles.
Slot count 10 (median 10). Art families: `a/beach`, `a/field`, `a/grass`, `a/stone`, `a/tile`.

**Reference palette `metin2_a2.txt`** (`map_a2`, `map_n_threeway`, `metin2_map_guild_01`, `metin2_map_smhgate_threeway`):

| slot | role | texture | U/V | repeat | ground |
|---|---|---|---|---|---|
| 1 | `mid` | `a/field/field 01.dds` | 5/5 | 6.4 m | 9.98% |
| 2 | `accent` | `a/field/field 02.dds` | 6/6 | 5.3 m | 0.43% |
| 3 | `mid` | `a/grass/grass 01.dds` | 9/9 | 3.6 m | 15.35% |
| 4 | `mid` | `a/grass/grass 02.dds` | 8/8 | 4.0 m | 8.36% |
| 5 | `base` | `a/stone/stone01.dds` | 5/5 | 6.4 m | 45.37% |
| 6 | `cliff` | `a/stone/stone02.dds` | 4/4 | 8.0 m | 20.49% |
| 7 | `accent` | `a/tile/tile01.dds` | 5/5 | 6.4 m | 0.01% |
| 8 | `path` | `a/tile/tile02.dds` | 5/5 | 6.4 m | 0.01% |
| 9 | `unused` | `a/beach/beach sand 01.dds` | 5/5 | 6.4 m | 0.00% |
| 10 | `unused` | `a/beach/beach sand 02.dds` | 5/5 | 6.4 m | 0.00% |

Role budget across all 1 palettes: base x1, mid x3, cliff x1, path x1, accent x2, unused x2.
`UScale` by role (median, range): base 5 (5-5); mid 8 (5-9); cliff 4 (4-4); path 5 (5-5); accent 5.5 (5-6).

**What the maps actually reach for** (share of this archetype's painted ground):

| share of ground | dominant role (corpus-wide) | texture |
|---|---|---|
| 45.37% | `base` | `a/stone/stone01.dds` |
| 20.49% | `cliff` | `a/stone/stone02.dds` |
| 15.35% | `mid` | `a/grass/grass 01.dds` |
| 9.98% | `mid` | `a/field/field 01.dds` |
| 8.36% | `mid` | `a/grass/grass 02.dds` |
| 0.43% | `accent` | `a/field/field 02.dds` |
| 0.01% | `accent` | `a/tile/tile01.dds` |
| 0.01% | `accent` | `a/tile/tile02.dds` |

**Note.** One palette, four maps, and **zero** texture overlap with `field_empire`:
this is the whole `terrainmaps/a/` pack and the empire fields are the whole
`terrainmaps/b/` pack. Same 10-slot skeleton though (`field` x2, `grass` x2,
`stone` x2, `tile` x2, `beach` x2) — the shortened form of the 17-slot template.
Both `beach` slots are dead in all four maps.

### `eastplain` — Eastplain and empire castle

4 maps, 2 palettes, 3,276,651 painted tiles.
Slot count 13-17 (median 15). Art families: `a/stone`, `b/beach`, `b/field`, `b/stone`, `dawnmistwood`, `elemental_01`, `empirewar/summer`, `empirewar/tille` (+1 more).

**Reference palette `metin2_eastplain.txt`** (`metin2_map_eastplain_01`, `metin2_map_eastplain_02`, `metin2_map_eastplain_03`):

| slot | role | texture | U/V | repeat | ground |
|---|---|---|---|---|---|
| 1 | `cliff` | `dawnmistwood/dawnmistwood_rock001.dds` | 2/2 | 16.0 m | 14.94% |
| 2 | `cliff` | `mtthunder/mtthunder_stone01.dds` | 1/1 | 32.0 m | 9.55% |
| 3 | `cliff` | `a/stone/stone01.dds` | 3/3 | 10.7 m | 11.07% |
| 4 | `accent` | `dawnmistwood/dawnmistwood_sand001.dds` | 3/2 | 10.7 m | 0.19% |
| 5 | `mid` | `b/field/field 03_01.dds` | 3/3 | 10.7 m | 3.87% |
| 6 | `cliff` | `b/stone/stone02.dds` | 1/1 | 32.0 m | 1.53% |
| 7 | `mid` | `dawnmistwood/dawnmistwood_grass002.dds` | 3/2 | 10.7 m | 2.61% |
| 8 | `mid` | `dawnmistwood/dawnmistwood_grass001.dds` | 2/2 | 16.0 m | 10.86% |
| 9 | `shore` | `b/beach/beach sand 01.dds` | 1/1 | 32.0 m | 6.34% |
| 10 | `base` | `mtthunder/mtthunder_grass02.dds` | 2/2 | 16.0 m | 12.57% |
| 11 | `mid` | `b/field/field 04.dds` | 1/1 | 32.0 m | 5.89% |
| 12 | `shore` | `dawnmistwood/dawnmistwood_feild002.dds` | 4/4 | 8.0 m | 14.33% |
| 13 | `mid` | `dawnmistwood/dawnmistwood_field001.dds` | 4/4 | 8.0 m | 2.67% |
| 14 | `accent` | `mtthunder/mtthunder_field01.dds` | 4/4 | 8.0 m | 1.29% |
| 15 | `mid` | `mtthunder/mtthunder_field04.dds` | 4/4 | 8.0 m | 1.52% |
| 16 | `accent` | `dawnmistwood/dawnmistwood_grass004.dds` | 4/4 | 8.0 m | 0.68% |
| 17 | `accent` | `empirewar/tille/empire_tile02.dds` | 4/4 | 8.0 m | 0.09% |

Role budget across all 2 palettes: base x2, mid x13, cliff x5, shore x2, accent x5, unused x3.
`UScale` by role (median, range): base 2 (2-2); mid 3 (1-4); cliff 2 (1-9); shore 2.5 (1-4); accent 4 (3-5).

**What the maps actually reach for** (share of this archetype's painted ground):

| share of ground | dominant role (corpus-wide) | texture |
|---|---|---|
| 17.52% | `base` | `dawnmistwood/dawnmistwood_rock001.dds` |
| 13.18% | `shore` | `dawnmistwood/dawnmistwood_feild002.dds` |
| 12.00% | `base` | `mtthunder/mtthunder_grass02.dds` |
| 10.42% | `mid` | `dawnmistwood/dawnmistwood_grass001.dds` |
| 10.19% | `base` | `a/stone/stone01.dds` |
| 8.79% | `cliff` | `mtthunder/mtthunder_stone01.dds` |
| 5.83% | `shore` | `b/beach/beach sand 01.dds` |
| 5.42% | `base` | `b/field/field 04.dds` |

Other palettes: `metin2_map_empirecastle.txt` (13 slots, `metin2_map_empirecastle`).

**Note.** A late palette that shops across five older packs
(`dawnmistwood`, `mtthunder`, `a/stone`, `b/`, `empirewar/tille`) rather than
shipping its own. It also holds two of the seven `UScale != VScale` entries in
the corpus (slots 4 and 7, 3/2). `metin2_map_eastplain_02` writes indices 18 and
19 into a 17-slot palette.

### `darkforest_coast` — Dark-forest coast and Devils Dragon Island continent

8 maps, 5 palettes, 7,207,394 painted tiles.
Slot count 7-14 (median 11). Art families: `bayblacksand`, `capedragonhead`, `dawnmistwood`, `mtthunder`.

**Reference palette `metin2_map_e1.txt`** (`metin2_map_e1`, `metin2_map_e1_01`, `metin2_map_e1_02`, `metin2_map_e1_03`):

| slot | role | texture | U/V | repeat | ground |
|---|---|---|---|---|---|
| 1 | `mid` | `capedragonhead/capedragon_field003.dds` | 2/2 | 16.0 m | 6.95% |
| 2 | `mid` | `capedragonhead/capedragon_stone001.dds` | 2/2 | 16.0 m | 8.50% |
| 3 | `base` | `capedragonhead/capedragon_field001.dds` | 2/2 | 16.0 m | 14.32% |
| 4 | `base` | `capedragonhead/capedragon_cliff002.dds` | 1/1 | 32.0 m | 43.89% |
| 5 | `cliff` | `capedragonhead/capedragon_cliff003.dds` | 1/1 | 32.0 m | 3.14% |
| 6 | `accent` | `capedragonhead/capedragon_sand002.dds` | 2/2 | 16.0 m | 0.01% |
| 7 | `mid` | `capedragonhead/capedragon_grass003.dds` | 2/2 | 16.0 m | 23.19% |

Role budget across all 5 palettes: base x10, mid x21, cliff x5, path x4, shore x4, accent x8, unused x1, empty x1.
`UScale` by role (median, range): base 2 (1-3); mid 2 (1-3); cliff 1 (1-2); path 2.5 (2-3); shore 2.5 (2-3); accent 2 (2-3).

**What the maps actually reach for** (share of this archetype's painted ground):

| share of ground | dominant role (corpus-wide) | texture |
|---|---|---|
| 14.90% | `base` | `capedragonhead/capedragon_cliff002.dds` |
| 11.78% | `base` | `dawnmistwood/dawnmistwood_rock001.dds` |
| 6.92% | `base` | `mtthunder/mtthunder_stone02.dds` |
| 6.32% | `shore` | `capedragonhead/capedragon_sand002.dds` |
| 5.58% | `base` | `bayblacksand/bayblacksand_blacksand.dds` |
| 4.75% | `base` | `dawnmistwood/dawnmistwood_grass002.dds` |
| 4.68% | `base` | `capedragonhead/capedragon_grass002.dds` |
| 4.49% | `base` | `bayblacksand/bayblacksand_rock001.dds` |

Other palettes: `metin2_bayblacksand.txt` (11 slots, `metin2_map_bayblacksand`), `metin2_capedragonhead.txt` (12 slots, `metin2_map_capedragonhead`), `metin2_dawnmistwood.txt` (14 slots, `metin2_map_dawnmistwood`), `metin2_mtthunder.txt` (10 slots, `metin2_map_mt_thunder`).

**Note.** Four bespoke coastal art packs (`capedragonhead`, `bayblacksand`,
`dawnmistwood`, `mtthunder`) that cross-borrow freely — `metin2_bayblacksand.txt`
pulls three `capedragonhead/` textures, `metin2_dawnmistwood.txt` pulls one
`bayblacksand/`. `UScale` here is uniformly low (median 2, cliffs at 1) because
the art is 512-1024 px, and `metin2_capedragonhead.txt` is the cleanest proof in
the corpus of the texel-density rule (§4b): ten of its twelve slots land on
**exactly 32 px/m**, achieved by pairing 512 px with `UScale 2` and 1024 px
with `UScale 1`. `metin2_bayblacksand.txt` is missing its `Texture003` block and
the map paints 33 tiles there anyway.

### `trent_forest` — Trent night forest

2 maps, 1 palette, 1,310,720 painted tiles.
Slot count 11 (median 11). Art families: `trent/field`, `trent/grass`, `trent/stone`, `trent/tile`.

**Reference palette `metin2_map_trent.txt`** (`metin2_map_trent`, `metin2_map_trent02`):

| slot | role | texture | U/V | repeat | ground |
|---|---|---|---|---|---|
| 1 | `mid` | `trent/field/field 01.dds` | 5/5 | 6.4 m | 3.42% |
| 2 | `mid` | `trent/field/field 02.dds` | 6/6 | 5.3 m | 5.60% |
| 3 | `mid` | `trent/field/field 03.dds` | 5/5 | 6.4 m | 15.93% |
| 4 | `mid` | `trent/grass/grass 01.dds` | 6/6 | 5.3 m | 6.92% |
| 5 | `accent` | `trent/grass/grass 02.dds` | 10/10 | 3.2 m | 0.79% |
| 6 | `mid` | `trent/grass/grass 03.dds` | 10/10 | 3.2 m | 20.01% |
| 7 | `base` | `trent/stone/stone01.dds` | 10/10 | 3.2 m | 39.46% |
| 8 | `cliff` | `trent/stone/stone02.dds` | 6/6 | 5.3 m | 7.29% |
| 9 | `cliff` | `trent/stone/stone03.dds` | 6/6 | 5.3 m | 0.21% |
| 10 | `unused` | `trent/tile/tile01.dds` | 5/5 | 6.4 m | 0.00% |
| 11 | `path` | `trent/tile/tile02.dds` | 5/5 | 6.4 m | 0.37% |

Role budget across all 1 palettes: base x1, mid x5, cliff x2, path x1, accent x1, unused x1.
`UScale` by role (median, range): base 10 (10-10); mid 6 (5-10); cliff 6 (6-6); path 5 (5-5); accent 10 (10-10).

**What the maps actually reach for** (share of this archetype's painted ground):

| share of ground | dominant role (corpus-wide) | texture |
|---|---|---|
| 39.46% | `base` | `trent/stone/stone01.dds` |
| 20.01% | `mid` | `trent/grass/grass 03.dds` |
| 15.93% | `mid` | `trent/field/field 03.dds` |
| 7.29% | `cliff` | `trent/stone/stone02.dds` |
| 6.92% | `mid` | `trent/grass/grass 01.dds` |
| 5.60% | `mid` | `trent/field/field 02.dds` |
| 3.42% | `mid` | `trent/field/field 01.dds` |
| 0.79% | `accent` | `trent/grass/grass 02.dds` |

**Note.** A pure single-family palette (`terrainmaps/trent/{field,grass,stone,tile}`)
following the standard folder order, and the highest `UScale` band in the corpus:
`grass 02`, `grass 03` and `stone01` all sit at **10** (3.2 m repeat). `stone01`
is the base at 39.5% with clump 7.34 despite the "stone" name — this is forest
floor, not rock.

### `desert` — Desert and desert frontier

10 maps, 3 palettes, 6,488,062 painted tiles.
Slot count 12-17 (median 12). Art families: `a/beach`, `a/field`, `a/grass`, `a/stone`, `a/tile`, `b/grass`, `b/stone`, `c/stone` (+7 more).

**Reference palette `metin2_n_desert1.txt`** (`metin2_map_n_desert_01`, `metin2_map_smhgate_desert`, `metin2_map_sungzi_desert_01`, `metin2_map_sungzi_desert_hill_01`, `metin2_map_sungzi_desert_hill_02`, `metin2_map_sungzi_desert_hill_03`):

| slot | role | texture | U/V | repeat | ground |
|---|---|---|---|---|---|
| 1 | `base` | `n/desert/sand/sand01.dds` | 3/3 | 10.7 m | 31.31% |
| 2 | `mid` | `n/desert/sand/sand02.dds` | 6/6 | 5.3 m | 26.18% |
| 3 | `mid` | `n/desert/sand/sand03.dds` | 5/5 | 6.4 m | 26.45% |
| 4 | `path` | `n/desert/field/field 01.dds` | 6/6 | 5.3 m | 2.22% |
| 5 | `accent` | `n/desert/field/field 02.dds` | 9/9 | 3.6 m | 0.00% |
| 6 | `shore` | `n/desert/field/field 03.dds` | 8/8 | 4.0 m | 0.07% |
| 7 | `cliff` | `n/desert/stone/stone01.dds` | 4/4 | 8.0 m | 0.03% |
| 8 | `unused` | `n/desert/stone/stone02.dds` | 4/4 | 8.0 m | 0.00% |
| 9 | `cliff` | `n/desert/stone/stone03.dds` | 4/4 | 8.0 m | 12.44% |
| 10 | `accent` | `n/desert/grass/grass 01.dds` | 4/4 | 8.0 m | 0.10% |
| 11 | `accent` | `n/desert/grass/grass 02.dds` | 4/4 | 8.0 m | 0.66% |
| 12 | `cliff` | `n/desert/grass/grass 03.dds` | 4/4 | 8.0 m | 0.53% |

Role budget across all 3 palettes: base x4, mid x8, cliff x15, path x1, shore x2, accent x8, unused x3.
`UScale` by role (median, range): base 4 (3-8); mid 5.5 (4-9); cliff 5 (4-9); path 6 (6-6); shore 6 (4-8); accent 5 (4-9).

**What the maps actually reach for** (share of this archetype's painted ground):

| share of ground | dominant role (corpus-wide) | texture |
|---|---|---|
| 29.81% | `mid` | `n/desert/sand/sand02.dds` |
| 26.42% | `base` | `n/desert/sand/sand01.dds` |
| 21.67% | `mid` | `n/desert/sand/sand03.dds` |
| 9.69% | `cliff` | `n/desert/stone/stone03.dds` |
| 3.00% | `mid` | `a/grass/grass 02.dds` |
| 1.88% | `path` | `n/desert/field/field 01.dds` |
| 1.70% | `cliff` | `a/stone/stone04.dds` |
| 1.05% | `cliff` | `c/stone/c_stone04_bb.dds` |

Other palettes: `metin2_map_golden_land.txt` (12 slots, `metin2_map_golden_land`, `metin2_map_golden_land_stage`), `metin2_wl_01.txt` (17 slots, `metin2_map_nusluck01`, `metin2_map_wl_01`).

**Note.** The textbook base + double-dither. `n/desert/sand/sand01.dds` is the
carpet (31.3%, clump 7.81, 93.6% non-edge); `sand02` and `sand03` cover a
comparable 26.2% and 26.4% but at clump 4.00/4.01 with **1.2% and 0.8%** non-edge
— they exist only as noise scattered through `sand01` to hide its 10.7 m repeat.
Reproduce that ratio and the desert reads correctly; paint `sand02` as regions
and it reads as three deserts.

### `snow_field` — Snow field / snow mountain

6 maps, 1 palette, 4,521,984 painted tiles.
Slot count 9 (median 9). Art families: `n/snow.m`.

**Reference palette `metin2_n_snowm.txt`** (`map_n_snowm_01`, `metin2_map_smhgate_snow`, `metin2_map_sungzi_snow`, `metin2_map_sungzi_snow_pass01`, `metin2_map_sungzi_snow_pass02`, `metin2_map_sungzi_snow_pass03`):

| slot | role | texture | U/V | repeat | ground |
|---|---|---|---|---|---|
| 1 | `mid` | `n/snow.m/snow01.dds` | 5/5 | 6.4 m | 44.83% |
| 2 | `mid` | `n/snow.m/snow02.dds` | 5/5 | 6.4 m | 35.09% |
| 3 | `mid` | `n/snow.m/snow03.dds` | 5/5 | 6.4 m | 7.43% |
| 4 | `path` | `n/snow.m/field 01.dds` | 5/5 | 6.4 m | 2.38% |
| 5 | `unused` | `n/snow.m/field 02.dds` | 5/5 | 6.4 m | 0.00% |
| 6 | `unused` | `n/snow.m/field 03.dds` | 5/5 | 6.4 m | 0.00% |
| 7 | `cliff` | `n/snow.m/stone01.dds` | 5/5 | 6.4 m | 9.26% |
| 8 | `cliff` | `n/snow.m/stone03.dds` | 5/5 | 6.4 m | 0.99% |
| 9 | `accent` | `n/snow.m/ice_quest.dds **(missing)**` | 4/4 | 8.0 m | 0.01% |

Role budget across all 1 palettes: mid x3, cliff x2, path x1, accent x1, unused x2.
`UScale` by role (median, range): mid 5 (5-5); cliff 5 (5-5); path 5 (5-5); accent 4 (4-4).

**What the maps actually reach for** (share of this archetype's painted ground):

| share of ground | dominant role (corpus-wide) | texture |
|---|---|---|
| 44.83% | `mid` | `n/snow.m/snow01.dds` |
| 35.09% | `mid` | `n/snow.m/snow02.dds` |
| 9.26% | `cliff` | `n/snow.m/stone01.dds` |
| 7.43% | `mid` | `n/snow.m/snow03.dds` |
| 2.38% | `mid` | `n/snow.m/field 01.dds` |
| 0.99% | `cliff` | `n/snow.m/stone03.dds` |
| 0.01% | `accent` | `n/snow.m/ice_quest.dds` |
| 0.00% | `unused` | `n/snow.m/field 02.dds` |

**Note.** One nine-slot palette from the single `terrainmaps/n/snow.m/` folder
serves all six snow maps. `snow01` + `snow02` are the classic base/dither pair
(44.8% at clump 4.76 and 35.1% at clump 3.93 — both scored `mid` because neither
forms solid ground), with `snow03` supplying the solid highlights (7.4%, clump
7.89, 96.1% non-edge). Slot 9 points at `ice_quest.dds`, which was disabled by
renaming to `XXXice_quest.dds` (§7.2) — those tiles render the error texture.
This same folder is the target of every `textureset/snow/` re-skin (§4e).

### `flame_field` — Flame land / volcanic field

6 maps, 2 palettes, 3,997,696 painted tiles.
Slot count 7-8 (median 7.5). Art families: `dawnmistwood`, `n/flame area`.

**Reference palette `metin2_n_flame_01.txt`** (`metin2_map_n_flame_01`, `metin2_map_smhgate_flame`, `metin2_map_sungzi_flame_hill_01`, `metin2_map_sungzi_flame_hill_02`, `metin2_map_sungzi_flame_hill_03`):

| slot | role | texture | U/V | repeat | ground |
|---|---|---|---|---|---|
| 1 | `base` | `n/flame area/valcano_01.dds` | 2/2 | 16.0 m | 29.13% |
| 2 | `path` | `n/flame area/valcano_02.dds` | 3/3 | 10.7 m | 1.94% |
| 3 | `base` | `n/flame area/valcano_03.dds` | 3/3 | 10.7 m | 23.27% |
| 4 | `cliff` | `n/flame area/valcano_04.dds` | 2/2 | 16.0 m | 14.72% |
| 5 | `mid` | `n/flame area/valcano_magma_01.dds` | 3/3 | 10.7 m | 6.82% |
| 6 | `path` | `n/flame area/tile01.dds` | 3/3 | 10.7 m | 3.93% |
| 7 | `base` | `n/flame area/valcano_rock.dds` | 2/2 | 16.0 m | 20.19% |

Role budget across all 2 palettes: base x4, mid x4, cliff x1, path x2, accent x4.
`UScale` by role (median, range): base 2.5 (2-3); mid 2.5 (2-3); cliff 2 (2-2); path 3 (3-3); accent 3 (2-4).

**What the maps actually reach for** (share of this archetype's painted ground):

| share of ground | dominant role (corpus-wide) | texture |
|---|---|---|
| 28.67% | `base` | `n/flame area/valcano_01.dds` |
| 24.03% | `base` | `n/flame area/valcano_03.dds` |
| 20.09% | `base` | `n/flame area/valcano_rock.dds` |
| 14.59% | `cliff` | `n/flame area/valcano_04.dds` |
| 6.72% | `mid` | `n/flame area/valcano_magma_01.dds` |
| 3.98% | `path` | `n/flame area/tile01.dds` |
| 1.92% | `path` | `n/flame area/valcano_02.dds` |
| 0.01% | `mid` | `dawnmistwood/dawnmistwood_field001.dds` |

Other palettes: `metin2_boss_entrance.txt` (8 slots, `metin2_map_labyrinth`).

**Note.** The one archetype where the base is a *set* rather than a single
texture: `valcano_01` (29.1%), `valcano_03` (23.3%) and `valcano_rock` (20.2%)
all score `base` in `metin2_n_flame_01.txt`, each with clump 6.6-7.5. The
`metin2_boss_entrance.txt` variant reuses the same seven textures in the same
order and collapses to a single 69.7% `valcano_03` base.

### `ice_valley` — Snake valley / white-dragon ice valley

3 maps, 2 palettes, 3,080,192 painted tiles.
Slot count 14-20 (median 17). Art families: `a/beach`, `b/beach`, `b/field`, `b/stone`, `capedragonhead`, `dawnmistwood`, `mtthunder`, `n/snow.m` (+1 more).

**Reference palette `metin2_map_whitdragonvalley.txt`** (`metin2_map_icecrystalcave`, `metin2_map_whitdragonvalley`):

| slot | role | texture | U/V | repeat | ground |
|---|---|---|---|---|---|
| 1 | `accent` | `snakevalley/grass01.dds` | 1/1 | 32.0 m | 0.00% |
| 2 | `unused` | `capedragonhead/capedragon_stone001.dds` | 2/2 | 16.0 m | 0.00% |
| 3 | `cliff` | `snakevalley/field02_1.dds` | 2/2 | 16.0 m | 5.52% |
| 4 | `unused` | `capedragonhead/capedragon_field001.dds` | 2/2 | 16.0 m | 0.00% |
| 5 | `mid` | `snakevalley/grass01_1.dds` | 2/2 | 16.0 m | 6.75% |
| 6 | `unused` | `snakevalley/cliff01.dds` | 2/2 | 16.0 m | 0.00% |
| 7 | `cliff` | `snakevalley/cliff02.dds` | 2/2 | 16.0 m | 2.22% |
| 8 | `cliff` | `snakevalley/cliff03.dds` | 2/2 | 16.0 m | 3.93% |
| 9 | `accent` | `snakevalley/field03_1.dds` | 1/1 | 32.0 m | 1.34% |
| 10 | `accent` | `snakevalley/field02.dds` | 2/2 | 16.0 m | 0.00% |
| 11 | `mid` | `snakevalley/field03.dds` | 1/1 | 32.0 m | 1.88% |
| 12 | `base` | `n/snow.m/snow02.dds` | 2/2 | 16.0 m | 70.04% |
| 13 | `mid` | `n/snow.m/field 01.dds` | 4/4 | 8.0 m | 4.26% |
| 14 | `mid` | `n/snow.m/stone01.dds` | 4/4 | 8.0 m | 4.06% |

Role budget across all 2 palettes: base x2, mid x10, cliff x9, path x1, shore x1, accent x7, unused x4.
`UScale` by role (median, range): base 2 (2-2); mid 2 (1-4); cliff 2 (2-2); path 1 (1-1); shore 4 (4-4); accent 2 (1-4).

**What the maps actually reach for** (share of this archetype's painted ground):

| share of ground | dominant role (corpus-wide) | texture |
|---|---|---|
| 43.22% | `mid` | `n/snow.m/snow02.dds` |
| 8.83% | `cliff` | `snakevalley/cliff01.dds` |
| 5.29% | `cliff` | `capedragonhead/capedragon_stone001.dds` |
| 5.14% | `base` | `snakevalley/field02.dds` |
| 4.81% | `mid` | `snakevalley/grass01_1.dds` |
| 3.93% | `cliff` | `snakevalley/field02_1.dds` |
| 3.65% | `mid` | `snakevalley/field03.dds` |
| 3.03% | `mid` | `snakevalley/grass01.dds` |

Other palettes: `metin2_map_snakevalley.txt` (20 slots, `metin2_map_snakevalley`).

**Note.** Two palettes that share the `snakevalley/` pack but weight it very
differently. `metin2_map_whitdragonvalley.txt` is 70% `n/snow.m/snow02.dds` with
the snakevalley art demoted to cliffs and accents; `metin2_map_snakevalley.txt`
spreads its 20 slots evenly (largest single share 23.1%). Three of
whitdragonvalley's 14 slots are dead and three more sit below 0.01%.

### `empire_war` — Empire siege-war arenas (three seasonal skins)

6 maps, 3 palettes, 786,432 painted tiles.
Slot count 11-13 (median 13). Art families: `empirewar/desert`, `empirewar/snow`, `empirewar/summer`.

**Reference palette `metin2_map_empirewar01.txt`** (`metin2_map_battlearena01`, `metin2_map_empirewar01`):

| slot | role | texture | U/V | repeat | ground |
|---|---|---|---|---|---|
| 1 | `mid` | `empirewar/snow/field01.dds` | 5/5 | 6.4 m | 24.71% |
| 2 | `accent` | `empirewar/snow/field02.dds` | 6/6 | 5.3 m | 0.25% |
| 3 | `mid` | `empirewar/snow/field03.dds` | 5/5 | 6.4 m | 25.36% |
| 4 | `mid` | `empirewar/snow/grass01.dds` | 6/6 | 5.3 m | 7.50% |
| 5 | `shore` | `empirewar/snow/grass02.dds` | 9/9 | 3.6 m | 0.01% |
| 6 | `cliff` | `empirewar/snow/stone01.dds` | 8/8 | 4.0 m | 17.28% |
| 7 | `cliff` | `empirewar/snow/stone02.dds` | 9/9 | 3.6 m | 0.09% |
| 8 | `cliff` | `empirewar/snow/stone03.dds` | 5/5 | 6.4 m | 14.66% |
| 9 | `mid` | `empirewar/snow/tile01.dds` | 4/4 | 8.0 m | 4.12% |
| 10 | `accent` | `empirewar/snow/tile02.dds` | 5/5 | 6.4 m | 1.34% |
| 11 | `mid` | `empirewar/snow/tile03.dds` | 5/5 | 6.4 m | 4.70% |
| 12 | `unused` | `empirewar/snow/tile04.dds` | 5/5 | 6.4 m | 0.00% |
| 13 | `unused` | `empirewar/snow/river01.dds` | 5/5 | 6.4 m | 0.00% |

Role budget across all 3 palettes: base x1, mid x14, cliff x9, path x1, shore x2, accent x4, unused x6.
`UScale` by role (median, range): base 5 (5-5); mid 5 (4-6); cliff 8 (5-9); path 4 (4-4); shore 8.5 (8-9); accent 5 (5-6).

**What the maps actually reach for** (share of this archetype's painted ground):

| share of ground | dominant role (corpus-wide) | texture |
|---|---|---|
| 10.01% | `cliff` | `empirewar/desert/sand01.dds` |
| 8.45% | `mid` | `empirewar/snow/field03.dds` |
| 8.24% | `mid` | `empirewar/snow/field01.dds` |
| 8.05% | `mid` | `empirewar/summer/field01.dds` |
| 6.62% | `mid` | `empirewar/summer/field03.dds` |
| 5.96% | `cliff` | `empirewar/desert/stone01.dds` |
| 5.93% | `cliff` | `empirewar/summer/stone01.dds` |
| 5.76% | `cliff` | `empirewar/snow/stone01.dds` |

Other palettes: `metin2_map_empirewar02.txt` (13 slots, `metin2_map_battlearena02`, `metin2_map_empirewar02`), `metin2_map_empirewar03.txt` (11 slots, `metin2_map_battlearena03`, `metin2_map_empirewar03`).

**Note.** Three seasonal skins of one layout. `empirewar01` (snow) and
`empirewar02` (summer) are structurally identical — same 13 slots, same motif
order `field01-03, grass01-02, stone01-03, tile01-04, river01`, same UV scales,
only the folder differs (`empirewar/snow/` vs `empirewar/summer/`) — and their
maps paint them almost identically (`tile03`: 4.698% vs 4.695%; `tile01`: 4.117%
vs 3.978%). `empirewar03` (desert) drops to 11 slots by replacing the first two
`field` entries with `sand01`/`sand02` and dropping `tile04`/`river01`.
`river01` and `tile04` are dead in every season. This is the cleanest evidence in
the corpus that a palette is a *template* filled from an art folder.

### `arena_pvp` — PvP arena, OX event and shop plaza

6 maps, 3 palettes, 983,040 painted tiles.
Slot count 5-17 (median 17). Art families: `a/beach`, `a/field`, `a/grass`, `a/stone`, `a/tile`, `b/beach`, `b/field`, `b/grass` (+11 more).

**Reference palette `metin2_map_oxevent.txt`** (`metin2_map_oxevent`, `metin2_map_privateshop`):

| slot | role | texture | U/V | repeat | ground |
|---|---|---|---|---|---|
| 1 | `cliff` | `a/stone/stone01.dds` | 5/5 | 6.4 m | 16.41% |
| 2 | `unused` | `a/stone/stone04.dds` | 6/6 | 5.3 m | 0.00% |
| 3 | `mid` | `c/tile/tile04.dds` | 5/5 | 6.4 m | 8.52% |
| 4 | `mid` | `c/tile/tile05.dds` | 6/6 | 5.3 m | 6.34% |
| 5 | `accent` | `a/tile/tile02.dds` | 9/9 | 3.6 m | 0.22% |
| 6 | `accent` | `a/grass/grass 02.dds` | 8/8 | 4.0 m | 0.64% |
| 7 | `mid` | `a/grass/grass 03.dds` | 9/9 | 3.6 m | 31.23% |
| 8 | `unused` | `ema1/tile/tile01.dds` | 5/5 | 6.4 m | 0.00% |
| 9 | `unused` | `b/grass/grass 02_01.dds` | 4/4 | 8.0 m | 0.00% |
| 10 | `unused` | `trent/tile/tile01.dds` | 5/5 | 6.4 m | 0.00% |
| 11 | `mid` | `a/field/field 05.dds` | 5/5 | 6.4 m | 31.29% |
| 12 | `mid` | `trent/tile/tile02.dds` | 5/5 | 6.4 m | 4.94% |
| 13 | `unused` | `a/tile/tile01.dds` | 5/5 | 6.4 m | 0.00% |
| 14 | `accent` | `n/desert/sand/sand03.dds` | 5/5 | 6.4 m | 0.37% |
| 15 | `unused` | `b/tile/tile03.dds` | 5/5 | 6.4 m | 0.00% |
| 16 | `cliff` | `ema1/beach/beach sand 03.dds` | 5/5 | 6.4 m | 0.04% |
| 17 | `unused` | `ema1/stone/stone03.dds` | 7/7 | 4.6 m | 0.00% |

Role budget across all 3 palettes: base x2, mid x10, cliff x5, path x1, shore x1, accent x8, unused x12.
`UScale` by role (median, range): base 5 (2-8); mid 5 (2-9); cliff 5 (5-9); path 3 (3-3); shore 4 (4-4); accent 5.5 (2-9).

**What the maps actually reach for** (share of this archetype's painted ground):

| share of ground | dominant role (corpus-wide) | texture |
|---|---|---|
| 20.32% | `base` | `guild_battle/guild_cliff01.dds` |
| 16.69% | `mid` | `a/field/field 05.dds` |
| 16.66% | `mid` | `a/grass/grass 03.dds` |
| 8.75% | `base` | `a/stone/stone01.dds` |
| 5.24% | `mid` | `b/grass/grass 03.dds` |
| 5.07% | `mid` | `g/field/field 01.dds` |
| 4.71% | `mid` | `guild_battle/guild_field001.dds` |
| 4.54% | `mid` | `c/tile/tile04.dds` |

Other palettes: `metin2_duel.txt` (5 slots, `metin2_map_duel`, `metin2_map_pvp_arena`), `metin2_map_guild_battle.txt` (17 slots, `metin2_map_guild_battle`, `metin2_map_guild_battle_base`).

**Note.** `metin2_map_guild_battle.txt` is the most damaged palette in the pack:
6 of its 17 slots point at `terrainmaps/guild_battle/`, which does not exist in
this art dump, and those 6 carry **92.2%** of the ground of
`metin2_map_guild_battle` + `_base` (`guild_cliff01.dds` alone is 61.0%). Everything measured about them here comes
from `tile.raw` only — no colour or resolution data.

### `guild_village` — Guild village and small guild-war grounds

4 maps, 4 palettes, 458,059 painted tiles.
Slot count 5-7 (median 5.5). Art families: `b/tile`, `guild_village`, `n/snow.m`.

**Reference palette `metin2_guild_village.txt`** (`metin2_guild_village`):

| slot | role | texture | U/V | repeat | ground |
|---|---|---|---|---|---|
| 1 | `empty` | `*(empty slot)*` | 0/0 | - | 0.00% |
| 2 | `base` | `guild_village/guild_village_grass002.dds` | 2/2 | 16.0 m | 31.72% |
| 3 | `mid` | `guild_village/guild_village_field001.dds` | 2/2 | 16.0 m | 11.30% |
| 4 | `base` | `guild_village/guild_village_cliff002.dds` | 1/1 | 32.0 m | 40.66% |
| 5 | `mid` | `guild_village/guild_village_field003.dds` | 2/2 | 16.0 m | 2.53% |
| 6 | `base` | `guild_village/stone_tile_002.dds` | 2/2 | 16.0 m | 13.78% |

Role budget across all 4 palettes: base x9, mid x9, path x1, accent x1, unused x2, empty x1.
`UScale` by role (median, range): base 2 (1-2); mid 2 (2-2); path 2 (2-2); accent 2 (2-2).

**What the maps actually reach for** (share of this archetype's painted ground):

| share of ground | dominant role (corpus-wide) | texture |
|---|---|---|
| 43.53% | `base` | `guild_village/guild_village_cliff002.dds` |
| 31.21% | `base` | `guild_village/guild_village_grass002.dds` |
| 11.23% | `base` | `guild_village/stone_tile_002.dds` |
| 7.65% | `mid` | `guild_village/guild_village_field001.dds` |
| 5.70% | `accent` | `guild_village/guild_village_field003.dds` |
| 0.69% | `path` | `b/tile/tile01.dds` |
| 0.00% | `mid` | `n/snow.m/snow01.dds` |

Other palettes: `gm_guild_build.txt` (7 slots, `gm_guild_build`), `metin2_guild_war1.txt` (5 slots, `metin2_guild_war1`), `metin2_guild_war3.txt` (5 slots, `metin2_guild_war3`).

**Note.** `metin2_guild_village.txt` has **no `Texture001` block** — the file
starts at `Texture002`, so slot 1 is an error-texture hole, and the map paints
index 7 (5 tiles) past its `TextureCount 6`. `gm_guild_build` is a build/test
map: its palette's seven slots are painted **zero** tiles, because its single
sector paints indices 2,4,6,7,3,9,10,13 — three of them out of range — and its
`tile.raw` is the only oversized one in the corpus (§7.4).
`metin2_guild_war1.txt` and `metin2_guild_war3.txt` are md5-identical.

### `elemental` — Elemental (Sungma) forest zones

4 maps, 3 palettes, 5,046,272 painted tiles.
Slot count 19-20 (median 19). Art families: `a/grass`, `b/tile`, `capedragonhead`, `dungeon/devilcave`, `elemental_01`, `empirewar/desert`, `guild_village`, `n/desert/sand` (+6 more).

**Reference palette `metin2_map_elemental_01.txt`** (`metin2_map_elemental_01`, `metin2_map_elemental_04`):

| slot | role | texture | U/V | repeat | ground |
|---|---|---|---|---|---|
| 1 | `path` | `zone/dungeon/snow_dungeon/tile_ice00.dds` | 2/2 | 16.0 m | 2.07% |
| 2 | `accent` | `zone/dungeon/snow_dungeon/tile_rock00.dds` | 3/3 | 10.7 m | 1.18% |
| 3 | `base` | `capedragonhead/capedragon_field001.dds` | 1/1 | 32.0 m | 75.23% |
| 4 | `cliff` | `zone/dungeon/snow_dragon/crack.dds` | 3/3 | 10.7 m | 2.72% |
| 5 | `mid` | `elemental_01/elemental_01_02.dds` | 2/2 | 16.0 m | 1.75% |
| 6 | `mid` | `elemental_01/elemental_01_03.dds` | 2/2 | 16.0 m | 2.43% |
| 7 | `cliff` | `elemental_01/elemental_01_04.dds` | 2/2 | 16.0 m | 5.20% |
| 8 | `path` | `elemental_01/elemental_01_01.dds` | 2/2 | 16.0 m | 1.84% |
| 9 | `shore` | `elemental_01/elemental_01_05.dds` | 4/4 | 8.0 m | 0.34% |
| 10 | `cliff` | `elemental_01/elemental_01_06.dds` | 4/4 | 8.0 m | 2.36% |
| 11 | `cliff` | `elemental_01/elemental_01_07.dds` | 4/4 | 8.0 m | 1.15% |
| 12 | `unused` | `n/snow.m/tile04.dds` | 4/4 | 8.0 m | 0.00% |
| 13 | `unused` | `n/snow.m/tile05.dds` | 4/4 | 8.0 m | 0.00% |
| 14 | `accent` | `n/snow.m/tile02.dds` | 4/4 | 8.0 m | 0.27% |
| 15 | `accent` | `n/snow.m/grass 02.dds` | 4/4 | 8.0 m | 0.07% |
| 16 | `accent` | `guild_village/guild_village_field003.dds` | 2/2 | 16.0 m | 0.98% |
| 17 | `cliff` | `guild_village/guild_village_cliff002.dds` | 2/2 | 16.0 m | 2.19% |
| 18 | `unused` | `n/snow.m/grass 03.dds` | 4/4 | 8.0 m | 0.00% |
| 19 | `accent` | `b/tile/tile03.dds` | 4/4 | 8.0 m | 0.21% |

Role budget across all 3 palettes: base x3, mid x7, cliff x16, path x4, shore x1, accent x22, unused x5.
`UScale` by role (median, range): base 1 (1-1); mid 2 (2-3); cliff 4 (2-4); path 2.5 (2-4); shore 4 (4-4); accent 4 (2-8).

**What the maps actually reach for** (share of this archetype's painted ground):

| share of ground | dominant role (corpus-wide) | texture |
|---|---|---|
| 75.73% | `base` | `capedragonhead/capedragon_field001.dds` |
| 1.82% | `cliff` | `elemental_01/elemental_01_04.dds` |
| 1.78% | `base` | `n/flame area/valcano_rock.dds` |
| 1.62% | `base` | `dungeon/devilcave/dc_rock_00.dds` |
| 1.54% | `base` | `guild_village/guild_village_cliff002.dds` |
| 1.05% | `cliff` | `elemental_01/elemental_02_04.dds` |
| 0.95% | `cliff` | `zone/dungeon/snow_dragon/crack.dds` |
| 0.93% | `mid` | `dungeon/devilcave/dc_field_01.dds` |

Other palettes: `metin2_map_elemental_02.txt` (20 slots, `metin2_map_elemental_02`), `metin2_map_elemental_03.txt` (19 slots, `metin2_map_elemental_03`).

**Note.** All three palettes open with the same trick: slot 3 is
`capedragonhead/capedragon_field001.dds` at **`UScale 1` — a 32 m repeat** — and
it carries 75.2% / 75.6% / 76.4% of the ground of `elemental_01/02/03`
respectively at clump 7.97. One enormous low-frequency carpet, then 16-19 tiny
accents on top. Slots 12-17 are shared verbatim across all three
(`n/snow.m/tile04`, `tile05`, `tile02`, `grass 02`, `guild_village/guild_village_field003`,
`guild_village/guild_village_cliff002`), and `tile04`/`tile05` are dead in every
map. `metin2_map_elemental_01.txt` is also one of only four palettes in the pack
that reach outside `terrainmaps/`: its slots 1, 2 and 4 point into
`zone/dungeon/snow_dungeon/` and `zone/dungeon/snow_dragon/` (the others are
`metin2_battleroyale.txt` slots 33-35, `metin2_map_n_snow_dragon.txt` slots 2-5
and `metin2_map_n_snow_dungeon_01.txt` slots 2-3).

### `dungeon_themed` — Themed dungeon / ruin (biome-skinned interior)

21 maps, 11 palettes, 10,336,057 painted tiles.
Slot count 4-17 (median 6). Art families: `(root)`, `b/beach`, `b/field`, `b/grass`, `b/stone`, `b/tile`, `capedragonhead`, `dawnmistwood` (+8 more).

**Reference palette `metin2_dawnmistwood_dungeon.txt`** (`metin2_map_boss_awaken_dawnmist`, `metin2_map_boss_crack_dawnmist`, `metin2_map_dawnmist_dungeon_01`, `metin2_map_smhgate_dawnmist`):

| slot | role | texture | U/V | repeat | ground |
|---|---|---|---|---|---|
| 1 | `base` | `dungeon/dawnmistwood_dungeon/dmw_dungeon_grass00.dds` | 2/2 | 16.0 m | 79.59% |
| 2 | `mid` | `dungeon/dawnmistwood_dungeon/dmw_dungeon_field_00.dds` | 2/2 | 16.0 m | 5.61% |
| 3 | `path` | `dungeon/dawnmistwood_dungeon/dmw_dungeon_field_01.dds` | 2/2 | 16.0 m | 3.82% |
| 4 | `shore` | `dungeon/dawnmistwood_dungeon/dmw_dungeon_field_02.dds` | 2/2 | 16.0 m | 4.47% |
| 5 | `cliff` | `dungeon/dawnmistwood_dungeon/dmw_dungeon_grass00.dds` | 2/2 | 16.0 m | 0.17% |
| 6 | `mid` | `dungeon/dawnmistwood_dungeon/dmw_dungeon_grass02.dds` | 2/2 | 16.0 m | 2.75% |
| 7 | `accent` | `dawnmistwood/dawnmistwood_sand001.dds` | 2/2 | 16.0 m | 1.16% |
| 8 | `path` | `dungeon/dawnmistwood_dungeon/dmw_dungeon_tile000.dds` | 2/2 | 16.0 m | 2.15% |
| 9 | `void` | `dungeon/field 01.dds` | 1/1 | 32.0 m | 0.27% |

Role budget across all 11 palettes: base x12, mid x19, cliff x9, path x3, shore x7, accent x5, void x13, unused x13.
`UScale` by role (median, range): base 2 (1-5); mid 3 (1-4); cliff 3 (2-9); path 2 (2-4); shore 6 (2-9); accent 4 (2-4); void 5 (1-5).

**What the maps actually reach for** (share of this archetype's painted ground):

| share of ground | dominant role (corpus-wide) | texture |
|---|---|---|
| 26.93% | `void` | `black.dds` |
| 18.14% | `base` | `dungeon/devilcave/dc_grass_00.dds` |
| 14.58% | `base` | `dungeon/devilcave/dc_rock_00.dds` |
| 6.07% | `base` | `dungeon/dawnmistwood_dungeon/dmw_dungeon_grass00.dds` |
| 6.04% | `base` | `b/stone/stone01.dds` |
| 5.36% | `base` | `zone/dungeon/snow_dungeon/tile_rock00.dds` |
| 4.96% | `base` | `n/flame area/valcano_rock.dds` |
| 4.83% | `void` | `dungeon/field 01.dds` |

Other palettes: `metin2_map_n_flame_dungeon_01.txt` (6 slots, `metin2_map_boss_awaken_flame`, `metin2_map_boss_crack_flame`, `metin2_map_n_flame_dungeon_01`), `metin2_map_n_snow_dungeon_01.txt` (4 slots, `metin2_map_boss_awaken_snow`, `metin2_map_boss_crack_snow`, `metin2_map_n_snow_dungeon_01`), `metin2_map_otherworld_01.txt` (8 slots, `metin2_map_otherworld_01`, `metin2_map_otherworld_03`, `metin2_map_otherworld_04`), `metin2_map_devilscatacomb.txt` (12 slots, `metin2_map_devilscatacomb`, `metin2_map_smhgate_devils`), `metin2_map_n_flame_dragon_01.txt` (7 slots, `metin2_map_n_flame_dragon`), `metin2_map_otherworld_02.txt` (17 slots, `metin2_map_otherworld_02`), `metin2_map_secretdungeon.txt` (6 slots, `metin2_map_secretdungeon_01`), `metin2_map_whitedragoncave_01.txt` (4 slots, `metin2_map_whitedragoncave_01`), `metin2_map_whitedragoncave_02.txt` (4 slots, `metin2_map_whitedragoncave_02`), `metin2_map_whitedragoncave_03.txt` (4 slots, `metin2_map_whitedragoncave_boss`).

**Note.** The split from `dungeon_block` shows up cleanly in the palette:
these carry 4-17 slots of real biome art and use `void` only as a mask
(`black.dds` is still 26.9% of the archetype's ground, mostly from the
whitedragoncave trio, where slot 4 `black.dds` covers 32-100%). The
`whitedragoncave_01/02/03` palettes are a three-stage progression — `_01` is
99.99% black, `_02` is 62% dungeon-black plus 32% black plus a little ice,
`_03` inverts to 80% black / 18% dungeon-black.

### `dungeon_block` — Flat black-box block dungeon (interior)

23 maps, 6 palettes, 15,204,350 painted tiles.
Slot count 1-5 (median 1.5). Art families: `(root)`, `a/beach`, `dungeon`, `mtthunder`.

**Reference palette `metin2_map_deviltower1.txt`** (`metin2_map_deviltower1`, `metin2_map_maze_dungeon1`, `metin2_map_maze_dungeon2`, `metin2_map_maze_dungeon3`, `metin2_map_monkey_dungeon_11`, `metin2_map_monkey_dungeon_12`, `metin2_map_monkey_dungeon_13`, `metin2_map_monkeydungeon`, `metin2_map_monkeydungeon_02`, `metin2_map_monkeydungeon_03`):

| slot | role | texture | U/V | repeat | ground |
|---|---|---|---|---|---|
| 1 | `void` | `dungeon/field 01.dds` | 5/5 | 6.4 m | 100.00% |

Role budget across all 6 palettes: void x7, unused x6.
`UScale` by role (median, range): void 5 (5-5).

**What the maps actually reach for** (share of this archetype's painted ground):

| share of ground | dominant role (corpus-wide) | texture |
|---|---|---|
| 94.42% | `void` | `dungeon/field 01.dds` |
| 5.58% | `void` | `black.dds` |
| 0.00% | `mid` | `a/beach/beach sand 01.dds` |
| 0.00% | `mid` | `mtthunder/mtthunder_field01.dds` |
| 0.00% | `mid` | `mtthunder/mtthunder_field02.dds` |
| 0.00% | `accent` | `mtthunder/mtthunder_field03.dds` |
| 0.00% | `base` | `mtthunder/mtthunder_stone02.dds` |

Other palettes: `metin2_n_saguidungeon.txt` (1 slot, `metin2_map_boss_awaken_skipia`, `metin2_map_boss_crack_skipia`, `metin2_map_skipia_dungeon_01`), `metin2_map_spiderd.txt` (2 slots, `metin2_map_smhdungeon_01`, `metin2_map_spiderdungeon`, `metin2_map_spiderdungeon_03`), `metin2_map_smhtower_d.txt` (3 slots, `metin2_map_smhdungeon_02`, `metin2_map_snake_temple_02`), `metin2_map_anglar_dungeon_01.txt` (1 slot, `metin2_map_anglar_dungeon_01`), `metin2_mtthunder_dungeon.txt` (5 slots, `metin2_map_mt_th_dungeon_01`).

**Note.** The starkest recipe in the game: **the terrain is a black plane**.
`terrainmaps/dungeon/field 01.dds` and `terrainmaps/black.dds` both decode to
luminance 0.000, and between them they cover 100% of every block dungeon's ground
(15.2 M tiles across 23 maps). Everything a player sees is `.prd` DungeonBlock
geometry placed through `areadata.txt`. Six palettes hold 13 slots between them
and 6 of those are never painted — `metin2_mtthunder_dungeon.txt` carries four
`mtthunder/` outdoor textures that no map ever touches.
If you generate a block dungeon: one slot, one black texture, `UScale 5`, fill
`tile.raw` with `0x01`.

### `event_instance` — Bespoke event / instance stage

10 maps, 8 palettes, 8,454,127 painted tiles.
Slot count 4-37 (median 12). Art families: `(root)`, `12temple`, `a/beach`, `a/grass`, `a/tile`, `b/beach`, `b/field`, `b/grass` (+21 more).

**Reference palette `metin2_map_defensewave.txt`** (`metin2_map_defensewave`, `metin2_map_defensewave_port`):

| slot | role | texture | U/V | repeat | ground |
|---|---|---|---|---|---|
| 1 | `void` | `dungeon/field 01.dds` | 5/5 | 6.4 m | 0.57% |
| 2 | `base` | `a/beach/beach water.dds` | 4/4 | 8.0 m | 58.98% |
| 3 | `path` | `bayblacksand/bayblacksand_blacksand.dds` | 4/4 | 8.0 m | 0.15% |
| 4 | `base` | `12temple/stone_02.dds` | 4/4 | 8.0 m | 22.17% |
| 5 | `cliff` | `snakevalley/cliff01.dds` | 2/2 | 16.0 m | 10.64% |
| 6 | `accent` | `snakevalley/field03.dds` | 4/4 | 8.0 m | 0.15% |
| 7 | `mid` | `snakevalley/field02.dds` | 4/4 | 8.0 m | 6.38% |
| 8 | `path` | `snakevalley/grass01.dds` | 4/4 | 8.0 m | 0.96% |

Role budget across all 8 palettes: base x12, mid x27, cliff x24, path x9, shore x5, accent x23, void x2, unused x15.
`UScale` by role (median, range): base 3.5 (0.9-6); mid 4 (2-8); cliff 4 (2-4); path 4 (3-8); shore 4 (4-6); accent 4 (2-9); void 5 (5-5).

**What the maps actually reach for** (share of this archetype's painted ground):

| share of ground | dominant role (corpus-wide) | texture |
|---|---|---|
| 11.48% | `base` | `a/beach/beach water.dds` |
| 6.90% | `base` | `b/stone/stone01_01.dds` |
| 6.81% | `base` | `n/desert/sand/sand01.dds` |
| 5.91% | `base` | `12temple/stone_02.dds` |
| 5.76% | `base` | `b/stone/stone01.dds` |
| 4.76% | `mid` | `b/grass/grass 02_01.dds` |
| 3.65% | `base` | `geuglagsa/capedragon_cliff002.dds` |
| 3.53% | `mid` | `dawnmistwood/dawnmistwood_grass001.dds` |

Other palettes: `metin2_map_miniboss.txt` (4 slots, `metin2_map_miniboss_01`, `metin2_map_miniboss_02`), `metin2_12temple.txt` (23 slots, `metin2_12zi_stage`), `metin2_battleroyale.txt` (37 slots, `metin2_map_battleroyale`), `metin2_guild_pve.txt` (4 slots, `metin2_guild_pve`), `metin2_map_mists_of_island.txt` (10 slots, `metin2_map_mists_of_island`), `metin2_map_snake_temple.txt` (14 slots, `metin2_map_snake_temple_01`), `metin2_map_treasure_hunt.txt` (17 slots, `metin2_map_treasure_hunt`).

**Note.** The catch-all, and it shows: 8 palettes drawn from 20 art families with
`TextureCount` from 4 to 37 across 29 art families. `metin2_battleroyale.txt`
(37 slots, 11 families) is the **largest palette in the corpus** and reads like an
artist's scratch pad — desert, snow, volcanic and elemental packs stacked in one
list, with slots 16, 23, 28, 34 and 35 never painted.
`metin2_map_defensewave.txt` is the opposite extreme: its map is 99% submerged
(mean terrain slope 0.2 deg), so `a/beach/beach water.dds` scores as the `base`.

### `dev_stub` — Developer test stub

4 maps, 3 palettes, 786,423 painted tiles.
Slot count 5-17 (median 17). Art families: `b/beach`, `b/field`, `b/grass`, `b/stone`, `b/tile`, `g/field`.

**Reference palette `metin2_map_t3.txt`** (`metin2_map_t3`, `metin2_map_t4`):

| slot | role | texture | U/V | repeat | ground |
|---|---|---|---|---|---|
| 1 | `mid` | `g/field/field 05.dds` | 5/5 | 6.4 m | 5.78% |
| 2 | `mid` | `g/field/field 01.dds` | 6/6 | 5.3 m | 6.00% |
| 3 | `base` | `g/field/cliff_swp_05.dds` | 4/4 | 8.0 m | 51.81% |
| 4 | `base` | `g/field/field 06.dds` | 4/4 | 8.0 m | 35.88% |
| 5 | `accent` | `g/field/field 02.dds` | 4/4 | 8.0 m | 0.52% |

Role budget across all 3 palettes: base x7, mid x7, cliff x2, path x1, accent x6, unused x16.
`UScale` by role (median, range): base 5 (4-9); mid 6 (5-9); cliff 4.5 (4-5); path 7 (7-7); accent 5.5 (4-9).

**What the maps actually reach for** (share of this archetype's painted ground):

| share of ground | dominant role (corpus-wide) | texture |
|---|---|---|
| 44.12% | `base` | `b/stone/stone01.dds` |
| 14.10% | `base` | `b/field/field 03.dds` |
| 8.89% | `cliff` | `b/stone/stone04.dds` |
| 8.64% | `base` | `g/field/cliff_swp_05.dds` |
| 8.44% | `mid` | `b/grass/grass 01.dds` |
| 5.98% | `base` | `g/field/field 06.dds` |
| 3.27% | `cliff` | `b/stone/stone02.dds` |
| 1.60% | `mid` | `b/grass/grass 03.dds` |

Other palettes: `metin2_map_t1.txt` (17 slots, `metin2_map_t1`), `metin2_map_t2.txt` (17 slots, `metin2_map_t2`).

**Note.** These are unfinished. `metin2_map_t2.txt` references three textures that
do not exist (`g/field/field 03`, `field 04`, `grass 01`) and its map paints two
of them anyway (16.6% of its ground draws the error texture); it paints only 8 of
its 17 slots. `metin2_map_t3.txt` writes index 8 into a 5-slot palette.
Their `BasePosition` values also break the 25,600 alignment rule
(see `corpus-overview.md`). Do not use any of these as a template.

---

## 7. Broken, dead and undocumented data

Everything here was measured, not inferred. Full lists live under
`anomalies` and `missing_textures` in `catalog/textures.json`.

### 7.1 Three files in `textureset/` are not texturesets

`metin2_siege_01.txt`, `metin2_siege_02.txt`, `metin2_siege_03.txt` are
**pack-build manifests** — they open with `FolderName "pack_map"` and contain
`List ExcludedFolderNameList { "CVS" }`, `ExcludedPathList`,
`ExcludedFileNameList`. They have no `TextureSet` and no `TextureCount` key, so
`CTextureSet::Load` rejects them outright. No corpus map references them. A tool
that globs `textureset/*.txt` must tolerate this.

### 7.2 62 referenced textures do not exist under `D:/ymir work`

Grouped by folder (main sets only; the `snow/` variants add nothing new):

| folder | missing | referenced by |
|---|---|---|
| `terrainmaps/naga/` | 14 | `metin2_map_naga1.txt` |
| `terrainmaps/empirewar/` (flat) | 13 | `metin2_map_empirewar_a01.txt` |
| `terrainmaps/dungeon/underground/` | 12 | `metin2_map_dd.txt` |
| `terrainmaps/war/` | 7 | `metin2_map_t5.txt` |
| `terrainmaps/guild_battle/` | 6 | `metin2_map_guild_battle.txt`, `metin2_map_treasure_hunt.txt` |
| `terrainmaps/treasure_hunt/` | 5 | `metin2_map_treasure_hunt.txt` |
| `terrainmaps/g/field/` | 3 | `metin2_map_t2.txt` |
| `terrainmaps/field/` | 1 | `metin2_b1_ane.txt` |
| `terrainmaps/n/snow.m/ice_quest.dds` | 1 | `metin2_n_snowm.txt`, `metin2_battleroyale.txt` |

Three of these are diagnosable rather than merely absent:

- **`terrainmaps/empirewar/*.dds` was reorganised into season subfolders.**
  `metin2_map_empirewar_a01.txt` asks for `empirewar/field01.dds`; what exists is
  `empirewar/summer/field01.dds`, `empirewar/snow/field01.dds`,
  `empirewar/desert/field01.dds`. The `a01` palette is a stale pre-split copy,
  and no corpus map loads it.
- **`n/snow.m/ice_quest.dds` was disabled by renaming**: the folder holds
  `XXXice_quest.dds`. The two palettes that still point at it paint it anyway —
  `metin2_n_snowm.txt` slot 9 covers 0.014% of the snow field, `metin2_battleroyale.txt`
  slot 32 covers 0.32%. Those tiles render the error texture in a stock client.
- **`terrainmaps/field/field 04.dds`** (`metin2_b1_ane.txt` slot 5) drops the
  `a/`,`b/`,`c/` empire prefix — a typo for `b/field/field 04.dds`, which exists.

`naga/`, `guild_battle/` and `treasure_hunt/` folders are absent from the
extraction entirely; two of those palettes *are* used by corpus maps
(`metin2_map_guild_battle`, `metin2_map_treasure_hunt` paint 42% and 30% of
their ground with textures this art dump does not contain), so those three are
best read as "not in this extraction" rather than "not in the game".

### 7.3 11 maps write tile indices the palette cannot resolve

`tile.raw` bytes above `TextureCount` render the error texture
(`tile-raw.md` pitfall 3). It happens in shipped data:

| map | palette | TextureCount | out-of-range indices (tiles) |
|---|---|---|---|
| `metin2_map_mt_thunder` | `metin2_mtthunder.txt` | 10 | 12 (853), 13 (118), 14 (559) |
| `metin2_map_b1` | `metin2_b1.txt` | 17 | 19 (870) |
| `metin2_map_devilscatacomb` | `metin2_map_devilscatacomb.txt` | 12 | 13 (467) |
| `metin2_map_eastplain_02` | `metin2_eastplain.txt` | 17 | 18 (144), 19 (2) |
| `gm_guild_build` | `gm_guild_build.txt` | 7 | 9 (21), 10 (5), 13 (7) |
| `metin2_map_n_flame_dragon` | `metin2_map_n_flame_dragon_01.txt` | 7 | 8 (17) |
| `metin2_map_t3` | `metin2_map_t3.txt` | 5 | 8 (9) |
| `metin2_12zi_stage` | `metin2_12temple.txt` | 23 | 32 (7) |
| `metin2_guild_village` | `metin2_guild_village.txt` | 6 | 7 (5) |
| `metin2_map_smhgate_b1` | `metin2_b1.txt` | 17 | 19 (3) |

Separately, **`metin2_bayblacksand.txt` has no `Texture003` block** yet
`metin2_map_bayblacksand` paints 33 tiles with index 3, and
**`metin2_guild_village.txt` starts at `Texture002`** (slot 1 empty). Both are
"empty slot" cases: the count covers the slot, the block is missing, the tiles
draw the error texture.

Do not clamp silently when generating — but *do* tolerate this when reading.

### 7.4 One `tile.raw` is the wrong size

`<CORPUS>/gm_guild_build/000000/tile.raw` is **66,567 bytes**, three more than the
66,564 the loader `memcpy`s — three trailing `0x02` bytes. It is the only
non-conforming `tile.raw` in 1,341 sectors (all 1,341 `height.raw` are exactly
34,322). The client is unaffected because `RAW_LoadTileMap` does no size check;
a parser asserting `size === 66564` rejects a shipped map. Read the first
66,564 bytes and ignore the tail.

### 7.5 Fields that are documented as live but are dead in practice

Across all 1,032 texture entries of the 99 top-level sets:

- **`Begin` and `End` are `0` in every single entry.** No exceptions.
- **`UOffset`/`VOffset` are `0.0` everywhere** except `metin2_test_zon.txt` slot 1,
  and that file is corrupt anyway (see 7.6).
- **`bSplat`**: `0` x833, `1` x192, **`90` x7**. The value 90 is literal in the
  file (`metin2_guild_village.txt` slot 3 reads `    90` where the flag belongs);
  it appears in `gm_guild_build`, `metin2_capedragonhead`, `metin2_guild_village`,
  `metin2_guild_war1`, `metin2_guild_war3`, `metin2_map_e1`,
  `metin2_map_guild_battle` — six of the seven on a `*_field001.dds`. Since the
  splat renderer never reads `bSplat`, this is inert; parse it as an int, not a bool.
- **`UScale != VScale` in only 7 of 1,032 entries** (`metin2_battlefield.txt` 2/3,
  `metin2_eastplain.txt` slots 4 and 7 3/2, `metin2_map_empirecastle.txt` 3/2,
  both `mists_of_island` sets 2/3, `metin2_ydragon.txt` 3/2). Treat U and V as
  one number unless you have a reason not to.

### 7.6 Individual file defects

- **`metin2_test_zon.txt`** has Korean comments *inside* texture blocks
  (`TextureCount 02  <----...`, and a comment after the filename token). The
  positional block reader takes tokens 0..7, so the comment shifts everything:
  the engine reads `UScale` as `0`. Also note `TextureCount` written zero-padded
  as `02`.
- **`metin2_map_naga1.txt`** declares `Texture012` twice (lines 114-123 and
  124-133). First occurrence wins; slot 12's second definition is dead.
- **`gm_guild_build.txt` slot 7** is
  `"D:\ymir work\terrainmaps\\b\tile\tile01.dds"` — a doubled separator. Win32
  collapses it, so the client loads it; a naive POSIX-style joiner produces
  `/b/tile/tile01.dds` and fails. Collapse runs of separators before resolving.
- **`metin2_guild_village_01/02/03`** ship no `setting.txt` at all (only
  `mapproperty.txt` with `ParentMapName`), so they have no `TextureSet` key —
  they inherit `metin2_guild_village`'s palette through the parent.
- 29 of the 99 top-level palettes are loaded by **no** corpus map:
  `metin2_12temple_001..005`, `metin2_a1_aa`, `metin2_b1_ane`, `metin2_b2`,
  `metin2_b_c`, `metin2_battle_guild`, `metin2_c2`, `metin2_ema1`, `metin2_map_dd`,
  `metin2_map_empirewar_a01`, `metin2_map_n__trent`, `metin2_map_n_snow_dragon`,
  `metin2_map_naga1`, `metin2_map_t5`, `metin2_middle_flame`,
  `metin2_mists_of_island`, `metin2_n_desert_01`, `metin2_n_desert_1`,
  `metin2_resources_zon`, `metin2_siege_01..03`, `metin2_snakevalley`,
  `metin2_test_zon`, `metin2_ydragon`. `metin2_resources_zon.txt` and
  `metin2_test_zon.txt` are template stubs pointing at `Dungeon\field 01.DDS`.

### 7.7 The eraser really is used

13 of the 114 terrain-bearing maps contain unpainted (index 0) tiles.
`metin2_map_devilscatacomb` has 18,142 of them (0.51% of its ground) and
`metin2_guild_war3` 655 (1.0%); the other eleven have between 1 and 10 tiles —
stray brush slips. A renderer must draw index 0 as *nothing*, not as slot 1.

---

## 8. Authoring a new palette

A checklist that falls straight out of the measurements above.

1. **Pick an art family, not individual files.** Every shipped palette but a
   handful draws from one or two `terrainmaps/<pack>/` folders. Mixing packs is
   what `metin2_battleroyale.txt` (37 slots, 11 families) does, and it is the
   outlier, not the pattern.
2. **Size the palette to the archetype.** Median `TextureCount` by archetype
   ranges from 1 (`dungeon_block`) to 19 (`elemental`); the mode across the
   corpus is a 10-17 slot outdoor palette.
3. **Order slots by motif, low-to-high: field -> grass -> stone -> tile -> beach.**
   That single convention gives you the correct painter's order for free
   (§4a): ground first, roads and shoreline last.
4. **Budget the roles.** A typical outdoor palette is
   1-2 `base`, 3-5 `mid`, 2-4 `cliff`, 1 `path`, 0-2 `shore`, 2-3 `accent`,
   and — if you want to look shipped — 2-3 slots you never paint.
5. **Set `UScale` from the texture's pixel width, not from its role:**
   `UScale ~= 1536 / width_px` (256 px -> 6, 512 px -> 3, 1024 px -> 1.5), then
   round into 1..10. Check the result lands near 48 texels per world metre.
   Set `VScale = UScale`. Leave `UOffset`, `VOffset`, `bSplat`, `Begin`, `End` at 0.
6. **Paint with a dither, not with regions.** Target clump ~7-8 for the `base`,
   ~4 for each `mid`, and let the `mid` layers interpenetrate at tile resolution
   (median run length 2 tiles). A `mid` layer that forms solid patches reads as a
   second base and flattens the ground.
7. **Reserve solidity for meaning.** `path` and `shore` are the only small-area
   roles that should be solid (clump >= 6, >= 35% non-edge). If a 0.2%-coverage
   texture is solid, the player reads it as a road; if it is scattered, they read
   it as debris.
8. **Anchor `cliff` to the heightmap, not to the palette.** A `cliff` slot only
   works if you actually paint it where the terrain is steep: the shipped
   discriminator is a mean slope >= 28 deg and >= 1.25x the map's own mean.
9. **Keep tile indices <= `TextureCount`.** The engine will not stop you (§7.3),
   but the error texture is the ugliest thing in Metin2.
10. **For a winter variant, do not author new art** — apply the §4e substitution
    table onto `terrainmaps/n/snow.m/` and keep every `UScale`.

# Taste -- the rules that hold across every archetype

What Ymir actually did, measured over all 142 shipped maps rather than assumed. Every
rule below states its measurement and its `n`, and cites the file it came from. Where a
figure in `scripts/m2map/gen/spec.py` or in the original design brief disagrees with the
mined catalogs, the catalog wins and the disagreement is recorded in sec 9.

Per-biome recipes live in [`archetypes/`](archetypes/); start with
[`archetypes/README.md`](archetypes/README.md).

**Corpus.** 142 maps, 1,343 sector directories ~ 88.0 km^2 of terrain, 48,851
`areadata.txt` records of which **48,774 are what the engine actually loads**, 1,684
distinct CRCs, **0 unresolved** against the 2,112-entry client property index. 114 maps
contain objects; 116 have `attr.atr`; 28 are terrain-less proxies or empty.
(`corpus-overview.md` sec 1, `placement.md` intro, `catalog/stats-objects.json.corpus`.)

---

## 1. The universal rules

The design brief that preceded this corpus proposed six "universal" rules. **Mining
contradicted five of them.** 1.1-1.6 are the measured versions of those six.
1.7-1.11 were added later, from ground-truth screenshots of `metin2_map_a1`,
`map_a2` and `metin2_map_n_desert_01` that named conventions the first mining
pass had measured but not connected: what the art filenames mean, what a road
does that nothing else does, why a plaza is the one undithered thing on an
outdoor map, and — the one that had shipped as a real defect — that the rock
skin is region fill and §1.5 does not apply to it.

These are the highest-value rules in this document: break any one and the map
reads as machine-made.

---

### 1.1 Heading is **roll**, not yaw

`areadata.txt` field 4 is `yaw#pitch#roll` in degrees. `D3DXMatrixRotationYawPitchRoll`
puts **roll around Z**, and Z is up in Metin2 -- so roll is the compass heading and
yaw/pitch are the *tilt* channels.

| Channel | Non-zero records | Share |
|---|---|---|
| roll | **26,129** | 53.6 % |
| pitch | 1,802 | 3.69 % |
| yaw | 1,767 | 3.62 % |
| all three zero | 22,251 | **45.6 %** |

`n = 48,774`, `catalog/stats-objects.json.rotation_policy.channel_use`.

Per type, the share of records with a non-zero **yaw**
(`catalog/stats-objects.json.by_type`):

| Type | n | roll zero-share | yaw != 0 | pitch != 0 |
|---|---|---|---|---|
| Building | 23,044 | 0.213 | 5.77 % | 5.96 % |
| Tree | 14,281 | 0.668 | 2.74 % | 2.42 % |
| Effect | 8,117 | 0.902 | 0.31 % | 0.23 % |
| DungeonBlock | 3,332 | 0.265 | 0.63 % | 1.95 % |

**Tilt is a debris channel and nothing else.** The families that use it are
`zone/snakevalley` spear rocks (yaw != 0 in **39.9 %**, pitch in **33.6 %**, n = 333) and
`zone/devils_dragon_island/bone` whale skeletons (26.2 % / 33.0 %, n = 267), plus big
stones (`ob-bigstone01` 38.2 % / 37.4 %) and the `eastplain` leaning pillars
(`double_01` 37.5 % / 22.2 %). `zone/b/building` uses yaw and pitch in **0.1 %** of
1,021 records and `zone/dungeon/mt_thunder_dungeon` in **0 %** of 604
(`placement.md` sec 1.1).

> **Rule:** write the heading into roll. Leave yaw and pitch at 0 for buildings, dungeon
> blocks, trees and effects. Use +/-15 deg or +/-30 deg yaw/pitch **only** on rocks, bones,
> shipwrecks and thorns, and only in the archetypes whose files say so.

---

### 1.2 Everything snaps to 15 deg

- **Not one fractional angle exists in the corpus.** `roll_integer_share = 1.0`,
  n = 48,774. The engine truncates with `atoi` anyway, but the shipped files were already
  integral.
- **99.69 % of roll values are multiples of 15 deg**; 99.75 % are multiples of 5.
- **Only 148 distinct roll values exist in the entire corpus**, all in `[0, 357]`.
- Every one of the 48,774 records writes the 3-token `yaw#pitch#roll` form
  (`token_shapes = {3: 48774}`). Not one legacy bare-integer rotation token survives, so
  the `substr(0, s-1)` yaw defect never fires on official data. **Write `%f#%f#%f`.**

Buildings additionally favour the cardinals: among non-zero building rolls,
**29.5 % are multiples of 90** and 47.2 % of 45 -- 90/180/270 each appear about three
times as often as a generic 15 deg step.

Dungeon-block corridor kits go further: rolls are multiples of **90 deg** in
**98.9-100 %** of every kit, and `zone/geuglagsa` is 98.4 % 90 deg-snapped
(`placement.md` sec 1.1, sec 3.3, sec 8).

> **Rule:** `roll = 15 * randint(0, 23)`. For buildings, bias toward 90/180/270. For
> interior corridor kits, use 90 deg only.

---

### 1.3 Trees are mostly **unrotated**

| Family | n | roll exactly 0 | resultant R |
|---|---|---|---|
| `tree/n1` winter | 2,084 | **82.7 %** | 0.64-0.93 |
| `tree/b1` deciduous | 5,968 | **67.2 %** | 0.61-0.79 |
| `tree/n2` arid | 3,256 | **60.3 %** | 0.55-0.96 |
| all Tree records | 14,281 | **66.8 %** | 0.7075 |

`placement.md` sec 1.1, `catalog/stats-objects.json.by_type.Tree.roll`.

The remainder is spread over the 15 deg ladder with a resultant length of 0.64-0.82 --
**strongly non-uniform**. A uniform-random heading is wrong twice over: it fills in the
zero mode that should hold two thirds of the records, and it flattens the ladder.

**Variety in a forest comes from species mixing and from `TreeSize`/`TreeVariance`, not
from yaw jitter.** A `field_empire` map runs eight to twelve b-family SpeedTrees; an
`elemental` map mixes four whole tree *families*; a `desert` patch is three to four
species inside a 2-5 m circle.

> **Rule:** two thirds of trees get roll 0; the rest a multiple of 15 deg. Get your variety
> from the species list.

---

### 1.4 There is **no road texture** in Ymir's art

All **355 distinct `.dds` paths** referenced by the 99 shipped texturesets were searched
for road/path/trail/track naming. `roads.json.texture_role_vocabulary.road_like_names`
is **empty**.

Roads are painted with ordinary ground textures:

| Map | Road slot | Texture | Cover |
|---|---|---|---|
| `metin2_map_a1` | 1 | `b/field/field 01.dds` | 14.2 % |
| `map_a2` | 1 | `a/field/field 01.dds` | 10.0 % (roads cover 8.6 % of the map) |
| `metin2_map_n_desert_01` | 4 | `n/desert/field/field 01.dds` | 2.2 % |
| `map_n_snowm_01` | 4 | `n/snow.m/field 01.dds` | 2.4 % |
| `metin2_map_capedragonhead` | 7 | `capedragonhead/stone_tile_002.dds` | 0.9 % |

The `tileNN` / `stone_tile` family is **pavement**, not road: `b/tile/tile01.dds` covers
only the **0.21 %** town plaza of `metin2_map_a1` (`placement.md` sec 10).

Corpus road grammar (`catalog/roads.json.corpus`, 73 maps, 516,413 m of centreline --
**see the caveat in sec 9**): median width 6.5 m (distance-transform median 5.0 m),
tortuosity 1.26, 7.5 junctions/km, 2.4 loops/km, radius of curvature 29 m, junction mix
T 36.7 % / Y 35.8 % / X-skew 13.1 % / star5 5.5 %.

> **Rule:** `RoadSpec.tile_index` names an ordinary palette slot. Rasterise the corridor,
> flatten the terrain under it (`flatten_to` ~ 3 deg), paint it solid, and let a `mid` or
> `base` texture be the surface. Do not invent a road texture; there is none to invent.

---

### 1.5 Ground is a per-tile **stipple** at 1 m, not region fill

This is the single most important thing to reproduce, and the easiest to get backwards.

**It is about ground.** Three features are painted solid and are *not* stipple:
the **cliff** (§1.10), the **road surface** (§1.8, dithered only at its rim) and
the **plaza disc** (§1.9, no dither at all). Applying this rule to the rock skin
turns every mountain into pepper — measured, and it happened.

Measured over the 114 maps with terrain, 87.9 M painted tiles
(`catalog/stats-tiles.json`, `textures.md` sec 4c):

- **Median run length of a texture index along either axis: 2 tiles.**
  n = 786 slot/map pairs carrying >= 500 tiles; **489 of them sit at exactly 2, 157 at 1**.
- **Half of all connected components are a single tile.** Median `singleton_fraction`
  across those 786 slots is **0.522**, and **63 %** of them have a median component area
  of exactly 1 tile.
- **22.5 % of those slots are dither-only** -- 177 of 786 retain under a tenth of their
  area after one opening. They exist *only* as a partner sprinkled through another slot
  and never form geometry.
- The splat is painted at the **1 m tile**, not the 2 m terrain cell:
  `transition_odd_x_bias` is 0.499 (median across 114 maps), flat everywhere.
- A map declares a median of **10.5** slots and paints **7**;
  `unused_fraction` median 0.172.
- **1.9 stipple pairs per map**, interleave 1.53, and the partner is a sibling from the
  same art folder **47.4 %** of the time.

The canonical example (`textures.md` sec 4c), `metin2_a2.txt` over its four maps,
4,980,734 painted tiles:

| slot | texture | share | clump/8 | solid | role |
|---|---|---|---|---|---|
| 5 | `a/stone/stone01.dds` | 45.37 % | 6.27 | 54.2 % | `base` |
| 3 | `a/grass/grass 01.dds` | 15.35 % | 5.11 | 23.0 % | `mid` |
| 4 | `a/grass/grass 02.dds` | 8.36 % | 3.71 | **0.3 %** | `mid` |
| 8 | `a/tile/tile02.dds` | 0.009 % | 6.30 | 36.8 % | `path` |

`grass 02` covers 8.4 % of the ground and **0.3 %** of its tiles have all eight
neighbours the same. It is noise, deliberately.

**The model is: smooth fields decide the local mixture, per-tile sampling decides the
pixel.** Region-fill-then-perturb-the-edges produces clean blobs with noisy borders --
the exact opposite of the corpus, where the interior is noisy and there are barely any
borders at all (`scripts/m2map/gen/texture.py` docstring).

**Four archetypes are genuine exceptions** and paint regions instead:
`flame_field` (0 stipple pairs, base run 112 tiles), `eastplain` (0 pairs),
`darkforest_coast` (0 pairs, dither-only share 0.00003) and both dungeon archetypes.
36 maps are on `stats-tiles.json.maps_with_no_stipple`. Their archetype files say so.

> **Rule:** sample per 1 m tile from a smooth per-slot suitability field. Give every
> `mid` slot a dither partner from its own art folder. Expect ~2 tile runs and ~50 %
> singleton components.

---

### 1.6 Block attr is mostly **slope** -- on half the corpus only

The 116 maps with `attr.atr` split into two authoring styles, separated on a measurement:
the block rate on *clean* cells (has slope, not water, not in the border strip, no
`areadata` placement within 12 m).

| Style | Maps | Block % of map | Block rate on clean flat ground (< 1 deg) |
|---|---|---|---|
| `slope_driven` | **59** | 60.4 % | **0.052** |
| `painted_box` | **57** | 87.2 % | **0.852** |

`attributes.md` sec 4, `catalog/stats-attr.json.attr_styles`.

**Block budget** -- every BLOCK cell charged to exactly one cause, first match wins:
`slope >= T` -> water -> within 12 m of a placement -> connected to the map edge -> residual.
`T` is each map's own fitted threshold.

| Group | Block cells | slope | water | object halo | out-of-bounds | residual |
|---|---|---|---|---|---|---|
| whole corpus (116) | 64,949,908 | 44.8 % | 7.4 % | 4.0 % | 38.9 % | 4.9 % |
| **`slope_driven` (59)** | 26,598,513 | **72.6 %** | **14.8 %** | 2.5 % | **8.8 %** | 1.4 % |
| `painted_box` (57) | 38,351,395 | 25.6 % | 2.2 % | 5.0 % | 59.8 % | 7.4 % |

On a sculpted outdoor map, roughly **27 % of the block is not terrain** -- and almost all
of that is water surfaces (14.8 %) plus the flat paint that seals the map edge (8.8 %).
Only **1.4 %** is genuinely unexplained interior artist intent. On a painted interior it
is the other way round: 74 % of block is not slope, dominated by the wall slab.

**The threshold, fitted on the 59 `slope_driven` maps only:**

- **Youden-optimal cut `slope >= 20 deg`** -- TPR 0.807, FPR 0.103, precision 0.784,
  *J* = 0.704.
- F1-optimal cut 23 deg; `P(block)` crosses 1/2 at 25-30 deg (interpolating ~ 27 deg).
- Per-map fitted thresholds: median **17 deg**, quartiles 10-21 deg. Nine maps degenerate to
  1 deg (they block almost everything).
- **4.3 % of steep cells are walkable** at the fitted threshold -- steep-but-passable ramps
  and paths cut into hillsides. A generator that blocks every cell over the threshold
  seals mountain passes the originals left open.

**Do not fit a slope threshold on a `painted_box` map.** Youden's *J* there is 0.176.
The procedure is: paint `BLOCK` everywhere, carve the corridors and rooms out of it, and
expect 60-75 % of the block to end up edge-connected.

> **Rule:** `attr_style: "slope_driven"` -> `block_slope_deg = 20` (or the archetype's own
> fitted value), then water, then the object halo, then patch the residual edge cells.
> `attr_style: "painted_box"` -> no slope rule at all.

---

### 1.7 The art's filenames are a usable palette vocabulary

§1.4 establishes that Ymir ships **no road texture** and §1.5 that ground is a
per-tile stipple. Neither means the filenames are noise. Pooled over the outdoor
corpus, the motif in a `.dds` name is a strong prior on the job it is given:

| you need | reach for | share of that role's slots |
|---|---|---|
| a cliff / mountain skin | `stone*` | **62 %** (+ `cliff*` 11 %, `rock*` 4 %) |
| a paved plaza or ring | `tile*` | **64 %** |
| a shore, riverbed or beach | `sand*`, `beach sand*` | **55 %** |
| green ground cover | `grass*` | 35 % of `mid` |
| a road, and general ground | `field*` | 34 % of `mid`, and the most-painted `path` file in the corpus |

`n = 53–130` slots per role, interiors excluded. The inverse holds too:
`stone*` slots are `cliff` 67 % of the time and sit on 41.7° mean ground;
`field*` slots sit on 5.7°.

This is a prior for **composing** a palette. It is not a classifier: the same
`b/stone/stone01.dds` is the `base` of `metin2_guild_war4` (77.5 % cover) and
the `cliff` of `metin2_a1` (16.7 %). Set `TextureSlot.role` from the job you
intend — the generator reads `role` and never the filename.

Full tables, both directions, in `textures.md` §4f.

### 1.8 Three things a road does that nothing else does

Measured over the 37 maps whose corridors pass the road verdict (`roads.json`):

1. **It is cleared of block.** Block rate inside the corridor median **5.9 %**
   against **69.4 %** in the control band beside it — the land is 70 %
   impassable and the road is 6 %. 27 of 37 under 15 %.
2. **It is flattened.** Slope ratio inside over control, median **0.21**
   (p25 0.13, p75 0.38, worst confirmed road 0.56).

   **The generator only gets part of the way there, and knows it.** That figure
   is route selection *and* earthworks: Ymir laid roads along ground that was
   already gentle. `gen/` levels whatever line the spec names — corridor
   levelling is implemented, route-finding is not. Three bugs found while
   measuring this, all now fixed, all of which looked like "the flattener is too
   weak":

   - the corridor was smoothed against its **off-road** neighbours, so every
     pass dragged the road back up the hillside — 3 passes and 40 passes both
     landed at 0.90;
   - the border ridge was raised **after** the corridor was levelled, burying a
     road that runs to the map edge (road slope 14.9° whole-map against 6.4°
     on the interior);
   - `ridge_gap` opened a saddle for water but not for roads, though corpus
     roads leave the map — that is how a route continues onto the next one.

   With all three fixed the desert reference spec measures **0.58**, level with
   the corpus's worst confirmed road. Every build now prints its own ratio; if
   it reads above about 0.5, **move the waypoints** — the generator is levelling
   correctly and the route is the problem.
3. **Its rim dithers with a sibling of its own motif.** Blend band median 3 m,
   `hard_edge` false on all 37. `map_a2` paints `field 01` and enriches
   `field 02` at the rim **23.9×**; `metin2_map_a1` paints `field 01` and
   enriches `field 04` 4.8×. Meanwhile `stone*` is *depleted* at the rim
   (median 0.52×) and `cliff*` more so (0.49×) — the paint-side statement of
   "roads do not climb mountains".

`textures.md` §4i–4j.

### 1.9 The safe zone is an unmixed disc, and it is a stamp

Every other feature on an outdoor map is dithered. The plaza is not: its slot
measures **solid 0.84–0.87** against 0.36–0.56 for a dirt road in the same
palette. 27 corpus components score fill 0.70–0.85 (a filled circle is
π/4 = 0.785) at aspect 1.00–1.10, radius **8–25 m**, on ground of slope
0.0–1.9° — and identical areas recur verbatim across unrelated maps (1,264
tiles in `metin2_map_a1`, `smhgate_a1` and `capedragonhead`). These are
copy-pasted stamps.

On every map that writes the safe-zone flag at all, the disc is **100 %
`ATTR_SAFEZONE`** against a map baseline of 0.2 %.

But do **not** infer that safe-zone implies walkable in general: 923,325 of the
1,282,946 safe-zone cells across the 37 maps that use the flag (**72 %**) also
carry block, because the flag is painted over a whole town including its walls.
Only the disc itself is guaranteed clear.

Build it with `PlazaSpec`. `textures.md` §4g–4h.

### 1.10 The cliff is region fill — the one exception to §1.5

§1.5 says ground is a per-tile stipple and not region fill. That is a statement
about **ground**. The rock skin is the exception, and it is the most visible
thing in a landscape screenshot. Share of cliff paint surviving a 5×5 opening
(massif ÷ raw):

| map | raw | massif | ratio |
|---|---|---|---|
| `metin2_map_n_desert_01` | 26.4 % | 26.2 % | **0.99** |
| `metin2_map_a1` | 32.9 % | 32.3 % | **0.98** |
| `metin2_map_a3` | 33.8 % | 33.0 % | **0.98** |
| `metin2_map_b1` | 27.0 % | 26.5 % | **0.98** |
| `metin2_map_c1` | 28.4 % | 27.7 % | **0.97** |
| `metin2_map_capedragonhead` | 3.5 % | 3.3 % | **0.94** |
| `metin2_map_b3` | 17.2 % | 15.8 % | **0.92** |
| `metin2_map_mt_thunder` | 23.5 % | 20.1 % | **0.86** |

Eight maps, 0.86 to 0.99, including one whose cliff covers only 3.5 % of the
ground. The rock is a **solid skin on steep terrain**, not a slot in the
stipple.

This was found the expensive way. The generator sampled cliff per tile exactly
like the ground and scored **0.02** on that ratio — rock as pepper, no rock face
anywhere — while every audit rule and every test passed. It took building the
desert reference spec and measuring the same statistic on the output to see it.

`P(cliff | slope)` is a monotone ramp, and where it turns is a per-map decision,
not a constant:

| slope | 0–5° | 15–20° | 25–30° | 40–50° | 60°+ |
|---|---|---|---|---|---|
| `metin2_map_a1` | 7 % | 34 % | 64 % | 83 % | 92 % |
| `metin2_map_n_desert_01` | 5 % | 12 % | 27 % | 79 % | 98 % |
| `metin2_map_mt_thunder` | 7 % | 26 % | 32 % | 34 % | 40 % |

So do not hard-code a slope threshold. Rank tiles by slope, jitter the ranking
with a smooth field so the rock line is organic rather than a terrain contour,
and take as many as the palette weights ask for. `gen/texture.py.cliff_massif`.

**Inside the massif the cliff slots still dither among themselves.** §4c's
`metin2_a2` example is the same rock face split 45 % `stone01` / 20 % `stone02`.
Solid means *rock versus ground*, not one texture.

> **Trap:** the massif must be thick enough to survive the opening it is
> measured with. A ridge two or three tiles wide passes a 3×3 smoothing and
> vanishes under a 5×5 opening, which put the generator at ratio 0.78 with 2.4 %
> of its rock stranded in open field — and no amount of tuning the feather moved
> either number, because the feather was never the cause.

### 1.11 Rock has a feathered rim, and open ground has none

The cliff texture does not stop at a line. Measuring the raw cliff share outward
from the *opened* massif rim — so the measurement is not circular — gives a
decaying tail about five to seven tiles long: `metin2_map_a1` 9.6 → 6.8 → 3.6 →
2.1 → 1.3 → 0.9 %; `metin2_map_b1` 16.2 → 16.4 → 10.6 → 7.2 → 4.8 → 2.7 %.

And then it stops: rock share in the far field, more than 20 m out, is
**0.00 %** on both (0.06 % on `metin2_map_n_desert_01`). A generator that
dithers rock globally reproduces the tail and destroys the stop, and the map
reads as gravel scattered over sand. `textures.md` §4l.

---

## 2. Geometry constants

These never vary and should be treated as fixed (`corpus-overview.md` sec 1,
`scripts/m2map/gen/spec.py`):

| Constant | Value | Evidence |
|---|---|---|
| `CellScale` | **200** world units per terrain cell | all 139 maps with a `setting.txt` |
| `HeightScale` | **0.500000** | all 139 |
| `MapType` | **`Outdoor`** | all 142 `mapproperty.txt` -- **not one `Indoor` map exists** |
| Sector | 128 cells = **256 tiles = 25,600 cm** | |
| `tile.raw` | 258x258 stored, 256x256 usable (1-tile skirt mirroring the neighbour) | |
| Height ceiling | 65535 x 0.5 = **32,767.5 cm** | reached by `darkforest_coast`, `ice_valley`, `dungeon_themed`, `dev_stub` |
| `BasePosition` alignment | multiple of 25,600 | **violated by 4 maps**: `gm_guild_build`, `metin2_map_t2/t3/t4` |
| `ViewRadius` | **not constant**: 128 x116, 256 x16, **4096 x4**, 512 x2, 384 x1 | |
| Slot 0 | the built-in eraser; `TextureCount` excludes it; `tile.raw` byte 0 = unpainted | |
| Painter's order | index order -- a higher slot paints **over** a lower one | `GameLib/AreaTerrain.cpp:646-768` |
| UV | `repeat_m = 32 / UScale`. `UScale 5` -> 6.4 m, `2` -> 16 m, `9` -> 3.6 m | |

**Size distribution:** 2x2 (35 maps), 3x3 (29), 6x6 (18), 1x1 (13), 2x4 (9), 4x5 (7),
4x4 (7). Median 3x3; largest `metin2_map_devilscatacomb` at 7x7. **Nothing approaches the
256x256 format limit.**

**`UScale` tracks texture resolution, not role** (`textures.md` sec 4b). Median `UScale` by
decoded width: 128 px -> 5.0, 256 px -> 5.0, 512 px -> 4.0, 1024 px -> 2.0. The invariant the
artists actually held is **texel density**: median 48 px/m over 967 measurable entries
(p10 32, p90 96); by role it moves only between 32 and 64 px/m. Rule of thumb for a new
entry: `UScale ~ 1536 / texture_width_px`, clamped into the shipped 1-10 band.

---

## 3. Density, spacing and clustering

**Corpus mean 5.6 obj/ha.** Per-archetype figures span a 10x range
(`placement.md` sec 2):

- **Open outdoor field: 4-8 obj/ha, 30-55 per sector.**
- **Plaza / village / arena: 12 obj/ha, 75-85 per sector.**
- **Barren biome (flame, elemental forest): 1-2 obj/ha.**

Type mix corpus-wide (`placement.md` intro):

| Type | Placements | Distinct CRCs | Median NN (any object) |
|---|---|---|---|
| Building | 23,044 (47.2 %) | 1,369 | 384 cm |
| Tree | 14,281 (29.3 %) | 84 | 920 cm |
| Effect | 8,117 (16.6 %) | 63 | 959 cm |
| DungeonBlock | 3,332 (6.8 %) | 168 | 1,190 cm |

`Building` is a catch-all: it holds houses *and* every rock, crate, fence and bush that
is a `.gr2`. **Read the family, not the type** -- 1,369 of the 1,684 placed CRCs are
`Building`.

**Hard partition:** no outdoor archetype uses `DungeonBlock` and no block dungeon
contains a single `Tree` record. The one exception is 36 `ice_01` slabs in
`map_n_snowm_01`, which are terrain features, not a corridor kit.

**Spacing** (`placement.md` sec 3):

| Family | n | NN(same family) p25 / p50 / p75 |
|---|---|---|
| `tree/b1` deciduous | 5,968 | 1,073 / **1,641** / 2,770 |
| `tree/b3` deciduous | 1,783 | 1,105 / **1,899** / 5,656 |
| `tree/n1` winter | 2,084 | 952 / **1,328** / 2,227 |
| `tree/n2` arid | 3,256 | 184 / **386** / 816 |
| `tree/b2` dead vine / cedar | 1,190 | 1,265 / **2,669** / 4,076 |
| `zone/b/obj` generic props | 10,792 | 181 / **363** / 994 |
| `zone/b/building` houses | 1,021 | 479 / **1,000** / 2,121 |

**A temperate forest is 10-17 m between trunks; a desert scrub is 2-8 m; props cluster at
2-5 m; houses at 9-13 m.** The `n2` arid set is not a forest at all -- it is ground cover
planted in dense patches.

**The long right tail matters as much as the median.** A real forest has clumps at 7-10 m
and gaps of 30-40 m. `metin2_map_a1` trees, n = 618: p10/25/50/75/90 =
681 / 953 / **1,491** / 2,625 / 4,158 cm. Reproducing only the median gives you an
orchard.

**Nothing is Poisson.** Clark-Evans `R = mean(NN) / (0.5 / sqrt(density))` computed
against each archetype's full terrain area: **every archetype is clustered**, R from 0.23
(`dev_stub`) to 0.70 (`dungeon_block`), median ~ 0.41. Two readable sub-rules:

- **Buildings clump harder than trees** -- they form settlements. In `field_empire`,
  `zone/b/building` R = 0.248 against `tree/b1` R = 0.572.
- **Effects are the only thing ever placed regularly.** `effect/background` is the sole
  family with R > 1 -- 1.268 in `field_empire`, **1.623 in `empire_war`** (nine warpgates,
  one per spawn). They are scattered one per landmark, so they end up more evenly spread
  than chance.

**Props travel in packs.** 60 % of `zone/b/obj` records have another prop within 5 m
(n = 10,792: 1,061 pairs under 1 m, 1,940 at 1-2 m, 1,481 at 2-3 m, 2,031 at 3-5 m).
Self-clumping within 5 m: `ob-b1-001-box01` x1,804, `ob-b1-001-box03` x1,792,
`ob-b1-005-woodbarrel` x747. **Crates come in threes, not ones**
(`placement.md` sec 6).

**Positions are free-hand.** Only 14.8 % of X coordinates are whole centimetres, 10.4 %
land on a 1 m tile boundary and 5.6 % on a 2 m cell boundary; trees are the least snapped
at 5.7 % and effects almost never (0.3 %). **DungeonBlocks are the exception**: 70.6 %
integral cm and 26.7 % exactly on a metre, because they are a connected corridor kit.
**Do not quantise positions.** Metin2 maps were dragged with a mouse
(`placement.md` sec 1.2).

**The working vocabulary is 400 CRCs.** 1,684 are used at all, but the top 25 cover
33.7 % of placements, the top 100 cover 57.0 % and the top 400 cover **83.9 %**. 428 of
the 2,112 shipped properties are never placed by any official map
(`placement.md` sec 7, `objects.md` sec 3).

---

## 4. Height bias -- the sink

`final_z = z + heightBias`. The stored `z` is essentially the terrain height at authoring
time; the bias is the artist's nudge (`placement.md` sec 1.3,
`catalog/stats-objects.json.height_model`).

- Median bias **0 cm**, mean +45.75, p5 -273, p95 +478 (n = 48,774).
- **30.0 % of records have bias exactly 0; 47.3 % are negative; 22.7 % positive.**
- `final_z - terrain_z` has median -5 cm, and **55.4 %** of records land within 50 cm of
  the terrain surface.

| Type | p25 | p50 | p75 | negative | exactly 0 | positive |
|---|---|---|---|---|---|---|
| Building | -30 | **0** | 0 | 49.6 % | 40.0 % | 10.4 % |
| Tree | -80 | **-37** | 0 | **74.8 %** | 24.4 % | 0.8 % |
| Effect | +304 | **+410** | +480 | 3.4 % | 3.4 % | **93.2 %** |
| DungeonBlock | 0 | **0** | +5 | 20.9 % | 49.2 % | 29.9 % |

- **Trees get sunk**: `tree/n1` -80 cm, `tree/b1` -45, `tree/b3` -35, `tree/n2` -15.
  Sinking hides the SpeedTree root flare on uneven ground.
- **Effects get raised**: `fire_general_obj_campfire.mse` +570 cm (n = 324),
  `fire_general_obj_charcoal.mse` +410 (n = 259), `smalla_resorce` **+1,519** (n = 1,385),
  `metinstone_loop_4_orange.mse` +952 (n = 35). A particle system is a billboard and has
  to be lifted to eye height.
- **Big rocks get sunk hardest**: `ob-bigstone01` -152 cm, `ob-bigstone03` -110,
  `ob-bigstone04` -104, `general_obj_stone19` -100; the desert `JoshuaTree_RT_03` is the
  extreme at **-697 cm** (n = 270) because its model is authored well above its origin.
- **Buildings do not sink**: `zone/b/building` bias is exactly 0 in 83.6 % of records.

---

## 5. Ground affinity -- what stands on what

Ground class is derived from the texture basename under each placement
(`catalog/affinity.json.class_rules`); the measured mean RGB of every texture is
published in `affinity.json.texture_catalog` so class assignments can be audited.

Corpus baseline over 48,774 placements
(`catalog/affinity.json.corpus_baseline.class_share`): **field 42.2 %, grass 24.6 %,
rock 12.0 %, sand 8.8 %, snow 4.9 %, tile 3.5 %, other 1.6 %, lava 1.2 %,
`(none)` 1.2 %, water 0.03 %.** Object slope p50 2.09 deg, p75 11.65 deg, p95 38.09 deg;
`attr_block_share` 0.655; `on_water_share` 0.108.

> **Naming trap.** `tile` is the `tileNN` / `stone_tile` *pavement* family, not "the
> road". And filenames lie about appearance: `A/stone/stone01.dds` is a tan dirt texture
> (measured mean RGB 159,135,112), not grey rock, and `trent/stone/stone01.dds` is forest
> floor. Always read `texture_catalog[path].mean_rgb` before trusting a class name
> (`placement.md` sec 4, `textures.md` sec 3).

**Trees are biome-locked, hard** (`placement.md` sec 4.1). These exclusions are **absolute**
in the shipped data and should be treated as constraints, not preferences:

| Family | Dominant ground | Lift vs corpus | **Never placed on** |
|---|---|---|---|
| `tree/b1` (Beech, Pagoda, MontereyCypress) | grass 44.4 %, field 34.9 % | grass x1.80 | **lava, snow** |
| `tree/b3` (Beech, UmbrellaThorn) | grass 48.5 %, field 39.0 % | -- | **lava, snow, tile** |
| `tree/n1` (ColoradoBlueSpruce, Beech_Winter) | snow 75.4 % | snow **x15.5** | **lava, sand** |
| `tree/n2` (CinnamonFern, AloeVera, JoshuaTree) | sand 52.8 %, grass 26.9 % | sand x6.0 | **lava** |
| `tree/b2` (IvySpy_Winter, CedarOfLebanon) | rock 58.6 % | -- | **snow** |

`tree/n2` on pavement: **1 record in 3,256**. `tree/b1` on snow: **0 in 5,968**.

**Buildings prefer grass and pavement.** `zone/b/building` (n = 1,021): grass 38.8 %,
field 21.5 %, **tile 21.4 % (lift x6.11)**, rock 17.0 %; never on lava, sand or "other".
`zone/a/building` (n = 216): grass 53.7 % (x2.18), field 38.4 %, tile 5.1 %; never on
lava, snow or "other", and effectively never on rock (1.4 %) or sand (0.5 %). **The
empire house set does not go on a beach.**

Meanwhile the generic prop set `zone/b/obj` (n = 10,792) has an **empty `never_on` list**
-- crates, fences and rocks go anywhere. **The universal kit** appears in every archetype,
including 151 records inside block dungeons: 273 CRCs placed, 10,792 records, 80 maps.

**Buildings demand flat ground; trees do not** (`placement.md` sec 1.4):

| Type | slope p50 | p90 | p99 | > 30 deg |
|---|---|---|---|---|
| Building | 1.9 deg | 29.0 deg | 62.2 deg | 9.4 % |
| Tree | 8.3 deg | 31.9 deg | 56.5 deg | 11.3 % |
| Effect | 0.0 deg | 8.0 deg | 50.7 deg | 2.1 % |
| DungeonBlock | 0.0 deg | 2.7 deg | 37.0 deg | 2.6 % |

The archetypal *house* families are far flatter than the aggregate: `zone/b/building`
p50 0.0 deg, p95 8.45 deg; `zone/a/building` p50 0.14 deg, p95 16.2 deg; `zone/c/building` p50 0.0 deg,
p95 22.2 deg. **Flatten before you build.** Rocks and vegetation are deliberately put on
slopes: `zone/devils_dragon_island` p50 9.2 deg / p75 23.5 deg; `zone/snakevalley` spear rocks
p50 **26.3 deg** / p75 40.3 deg.

**Water is not an exclusion zone.** 14.5 % of Buildings and 12.6 % of Trees corpus-wide
sit on a cell flagged wet in `water.wtr`. Coastal maps carry 20-40 % water cover, so this
is shoreline and shallows, not a bug.

**In every outdoor archetype, buildings hug the road and trees stand back**
(`placement.md` sec 5):

| Archetype | Building d(road) p50 | Tree d(road) p50 |
|---|---|---|
| `arena_pvp` | 566 cm | 1,371 cm |
| `field_empire` | **600** | 2,200 |
| `desert` | 730 | 2,400 |
| `guild_village` | 1,000 | 1,600 |
| `event_instance` | 1,094 | 6,625 |
| `darkforest_coast` | 1,131 | 1,542 |
| `empire_war` | 1,579 | 6,827 |
| `eastplain` | 3,542 | 6,804 |
| `snow_field` | 3,730 | 3,802 |
| `trent_forest` | **7,025** | **10,889** |

Family-level, corpus-wide: `effect/background` d(road) p25/p50/p75 = **0 / 0 / 1,094 cm**
-- effects sit *on* the road or plaza; `zone/b/building` 0 / 600 / 1,846;
`tree/b1` 400 / 1,600 / 7,273; `tree/b3` 1,003 / 2,989 / 16,102. **The upper quartiles are
what create the wilderness behind the treeline.**

**Set-pieces.** Reproducing the hand-composed groupings is most of what makes a map look
authored (`catalog/cooccurrence.json`, `placement.md` sec 6). The strongest:

- **camp / storage** -- `woodbarrel` + `box01` obs 148 x722; `box02` + `box01` obs 139
  x956; `tent01` + `woodbed` obs 35 x1,720; `jar_yellow01` + `jar_yellow02` obs 29
  x2,272;
- **fence runs** -- `fortMS_fence_body02` + `fortMS_fence_pillar` obs 42 x1,215, a
  body/pillar alternation; fences go in sequences of 3-5;
- **fire** -- of the `general_obj_campfire` buildings that share a map with the flame
  effect, **84 % have a flame within 100 cm** (median offset 7 cm), and the effect carries
  +570 cm bias. Its 15 m companions are chairs, a tent and crates: that is a camp;
- **forest** -- `Pagoda1` -> `Pagoda3` (x4.1), `Pagoda2` (x3.8), `Beech4` (x4.4),
  `MontereyCypress4` (x5.4), `ob-bigstone03` (x8.0). Even the forest is a recipe.

**Effects are not generally parasitic.** Corpus-wide only **4.1 %** of Effect placements
lie within 100 cm of a non-Effect object (n = 8,117, median distance 1,717 cm). The
anchored ones are specific: `fire_ob-11-02-stonelight01.mse` **100 %** within 1 m (n = 36),
`metinstone_loop_4_orange.mse` 91 %, `warpgate03` 56 %. Everything else -- resource
sparkles, volcano smoke, waterfalls -- is free-standing.

---

## 6. Attr detail beyond the slope rule

`attr.atr` is one byte per **1 m cell** (`catalog/stats-attr.json.method`). Corpus totals
over 116 maps / 88,014,848 cells (`catalog/stats-attr.json.global`):

| Flag | Cells | % |
|---|---|---|
| block (`0x01`) | 64,949,908 | **73.79 %** |
| bit 3 ("banshop") | 14,164,330 | 16.09 % |
| bit 7 | 14,212,200 | 16.15 % |
| bit 6 ("object") | 13,832,490 | 15.72 % |
| water (`0x02`) | 4,008,929 | 4.55 % |
| safezone (`0x04`) | 1,282,946 | 1.46 % |
| bit 5 | 496,744 | 0.56 % |

**37 distinct bytes exist corpus-wide, but 116 of 142 maps write nothing above `0x07`**
and 81.3 % of all cells are `0x00`-`0x05`. The `0xC8`/`0xC9` "mountain" paint family is a
26-map convention, not the norm (`attributes.md` sec Discrepancies 1).

**Water: the flag is not the truth.** 62 maps have wet cells in `water.wtr`; **30 paint
`ATTRIBUTE_WATER`**; Jaccard between the two is **0.310**, and 68.9 % of wet cells carry
no flag. The real invariant is the *submerged* predicate (water surface above terrain):
Jaccard 0.416, precision 0.773, recall 0.474 -- and only about half the maps honour even
that. 95.1 % of flagged water cells are also blocked, and 80.2 % of unflagged wet cells
are blocked (`attributes.md` sec 6). **Block the submerged cells; paint the flag only if
your archetype's file says its members do.**

**Object footprints are bimodal.** Corpus-wide 82.3 % of Building centre cells, 86.6 % of
Effect, 35.7 % of Tree and 22.1 % of DungeonBlock are blocked. Per map the policy is
either `painted` (stamp the footprint into `attr.atr`) or `model_only` (leave collision to
the `.mdatr`) -- see each archetype's attr section. **A generator that skips the stamp on a
`painted` archetype produces walk-through houses** (`placement.md` sec 4.3).

**Safezone.** 37 of 116 maps use it, 1.46 % of all cells, **58 components of >= 16 m^2**:
34 circular brush stamps, 8 solid rectangles, 16 irregular. The circular ones are literal
editor brush prints -- fill ratio clusters at pi/4 = 0.785 (measured median 0.788, quartiles
0.766-0.817). Observed diameters, all even: 14 (x6), 20, 24 (x4), 28, 32 (x4), 36, 40, 44
(x4), 48, 56 (x2), 68 m. Median component area **1,539 m^2**, median bbox edge **44 m**.

It is anchored on the spawn point and **essentially never on blocked ground** for town
discs (a1 0.4 %, b1 0.0 %, c1 0.0 %). The 8 rectangular ones are a different intent --
whole-map peace zones (`metin2_map_privateshop`, `metin2_map_oxevent`,
`map_b_fielddungeon`, one sector each of `smhdungeon_01` and `labyrinth`) -- and there the
safezone freely overlaps block (`attributes.md` sec 7).

> **Rule:** circular stamp, d = 24-56 m, centred on the spawn / town centre, on walkable
> ground. Whole-map rectangle only for a no-combat map type.

**Borders.** On the 59 `slope_driven` maps: **100 %** of edge cells blocked (median across
maps), median seal depth **119 m** (quartiles 76-206 m), and at the 5th percentile of edge
cells the seal is still 52 m deep. 17 of 59 have at least one hole. **Rim slope median
40.3 deg versus interior 10.7 deg**, and 77.9 % of the rim's blocked cells are steeper than 25 deg
-- the border is a mountain wall the artist raised, not just paint. On `painted_box` maps
the rim is flat (median 0.0 deg) and the band runs away.

**Five maps in the corpus are not sealed**: `metin2_map_empirewar01`/`02` (45.4 % of edge
cells blocked, 1,118 m of holes), `metin2_map_smhgate_a1` (69.2 %), and
`boss_awaken_skipia`/`boss_crack_skipia` (88.4 %) (`attributes.md` sec 8).

> **Rule (sculpted):** raise terrain above 25 deg for 60-120 m around the perimeter, let the
> slope rule seal it, then patch the residual edge cells (~ 9 % of block).
> **Rule (box):** paint a 15-30 m block shell instead.

---

## 7. Environment invariants

These hold in **all 104 shipped `.msenv` files**, or the stated exception is the only one
(`environments.md` sec 3, `catalog/environments.json.global_invariants`):

| Invariant | Evidence |
|---|---|
| `ScriptType EnvrionmentData` (the historical typo) | 104/104, never validated by the loader |
| `ScriptVersion 1.0000` | 104/104 |
| `SkyBox.Scale 3500 3500 3500` | 104/104 -- never varied, not a tuning knob |
| `DirectionalLight.Background.Enable` / `Character.Enable` = 1 | 104/104 |
| **`Character.Ambient == Background.Ambient + 0.15`, exact, per channel** | **104/104** -- a generator that sets the two independently will look wrong |
| `Background.Diffuse == Character.Diffuse` | 103/104; sole exception `moonlight04.msenv` |
| `LensFlare.Enable 0` | 104/104 -- the entire LensFlare group is dead data |
| `Filter.AlphaDest 2` | 104/104; `Filter.Enable 1` in only 9, and 5 of those specify an identity blend |
| `List Gradient` length == `GradientLevelUpper + GradientLevelLower` | 104/104 |
| `CloudColor` all-zero | 92/104 |

Two engine semantics that change how you read the numbers (`environments.md` sec 4):

1. **`Fog.FarDistance` is also the terrain texture-draw distance**, whether or not
   `Fog.Enable` is 1. Patches beyond `FogFar + 1600` are drawn untextured, flat-filled
   with `Fog.Color`. Doubling it doubles the textured-patch budget. Values in the corpus
   run 15,000 cm (`trent`) to **1,000,000** (`whitedragoncave_02`).
2. **Skybox face textures are inert unless `bTextureRenderMode` is 1.** 59 files name
   cube faces; only **15** set the flag. The other 44 load five `.dds` each that are never
   displayed -- which is also why missing face art causes no visible breakage.

Gradient entry order is **zenith -> horizon -> nadir**: zenith = `gradient[0].FirstColor`,
horizon = `gradient[Upper-1].SecondColor`, nadir = `gradient[-1].SecondColor`.
`DirectionalLight.Direction` is a `D3DLIGHT9` direction -- the direction light *travels*;
the sun sits at `-Direction`, and all but one file have `z < 0`.

Sample from the shipped distributions rather than inventing: `CloudScale` 200000 x88 /
5000 x10 / 280000 x3; `CloudHeight` 30000 x86 / 100 x9 / 10000 x4; `CloudTextureScale`
4 x69 / 5 x21 / 3 x10; `CloudSpeed` 0.004 x48 / 0.01 x24 / 0.001 x17 / 0.08 x10;
`GradientLevelUpper` 4 x34 / 1 x23 / 2 x18 / 5 x15 / 3 x11 / 7 x2 / 0 x1;
`GradientLevelLower` 1 x98 / 2 x5 / 0 x1.

At the coarsest useful clustering cut the corpus splits cleanly in two: **48 bright
outdoor daylight files vs 54 dim/interior**, driven almost entirely by
`Background.Ambient` and the zenith luminance -- the single most load-bearing pair of
numbers in the format.

---

## 8. The procedure, in order

1. **Pick the archetype** (`archetypes/README.md` Step 1), then take its size, terrain
   statistics, palette, environment and object palette from its file.
2. **Set `style`.** `sculpted` or `box`. 44 of 142 corpus maps are `box` and cannot be
   produced by the sculpted stages at all.
3. **Shape the terrain** to the archetype's `height_range_cm`, `slope_p50`, `slope_p95`,
   `flat_fraction` and `roughness`. Most archetypes are bimodal -- flat walkable ground
   plus steep walls -- not a uniform fractal.
4. **Lay the road web.** It is the skeleton everything else references. Flatten under it.
5. **Paint the ground as a stipple** (sec 1.5) with the archetype's `weight` column as the
   target coverage share; paint the road corridor solid with the nominated slot.
6. **Place buildings on flattened ground** (slope < 8 deg), snapped to the road, spaced
   9-13 m, roll a multiple of 15 deg biased to 90/180/270, bias 0. Stamp the footprint into
   `attr.atr` if the archetype's policy is `painted`.
7. **Plant trees by species-group**, one group per biome (sec 5), with the archetype's
   spacing and its long tail: clumps of 3-5 within 7 m, then gaps of 30-40 m. Two thirds
   get roll 0. Sink them.
8. **Scatter props in packs, not singly.** Use `cooccurrence.json.companions_15m` to pick
   partners.
9. **Add effects last, on landmarks**, raised 250-600 cm, roll usually 0, and give them
   the most *regular* spread of anything on the map.
10. **Write `attr.atr`** per sec 1.6 and sec 6, then the border seal and the safezone.
11. **Do not quantise positions.** Free-hand centimetres; only dungeon kits are integral.

---

## 9. Known source conflicts

Recorded rather than silently resolved.

**a. `metin2_a1` slot 1 -- resolved in favour of `placement.md`.**
`catalog/textures.json` scores `b/field/field 01.dds` as `base` (14.2 % cover, clump 5.40)
because its role rule is pooled over cover and clumping. `placement.md` sec 5/sec 10 is right
that on `metin2_map_a1` this slot **is** the road web: it was visually verified against
the rendered tile grid, and it is the index the geometric road detector selects while
rejecting slot 4 as its blend halo. **Roles are multi-valued** -- the same texture is
ground in `metin2_map_b1` and road surface in `metin2_map_a1`. Use `placement.md` for
distance-to-road and `textures.json` for palette composition; `placement.md` sec 10 says so
explicitly.

**b. The `attr_style` split is 59/57, not 59/55.**
`scripts/m2map/gen/spec.py`'s `MapSpec.attr_style` docstring says "The corpus splits
59/55". `catalog/stats-attr.json.attr_styles` and `attributes.md` sec 4 both report
**`slope_driven` 59, `painted_box` 57**, summing to the 116 maps that have `attr.atr`.
Use 59/57.

**c. The yaw zero-share range.**
`spec.py` and the design brief say "Yaw is zero in 89-99.7 % of records". The catalog's
per-type figures are **94.2-99.7 %** (Building 94.2 %, Tree 97.3 %, DungeonBlock 99.4 %,
Effect 99.7 %) and the corpus-wide figure is 96.4 % (1,767 non-zero of 48,774). The 89 %
lower bound does not appear at type level; the lowest *per-family* yaw-zero share is
46.2 % (`SpearRock_002`) and the lowest per-family-of-note is 60.1 %
(`zone/snakevalley`). The direction of the rule is unaffected.

**d. Object counts differ by 77 between two catalogs.**
`catalog/map-taxonomy.json` counts 48,851 `areadata.txt` records;
`catalog/stats-objects.json` counts 48,774. The difference is exactly the 77
`metin2_map_t1` blocks the client never loads -- its nine `areadata.txt` files each carry
two `ObjectCount` lines and the tokenizer is first-wins, so 44 of 121 blocks load.
**`stats-objects.json` counts what the engine loads**; use it for density.

**e. `catalog/roads.json` aggregates are stale and pooled.**
Its own `by_archetype_caveat` says the per-archetype blocks were produced **before** the
`road_verdict` filter existed and pool all maps with `has_roads`, including the 29
`terrain_ribbon` and 7 `ambiguous` ones the miner itself rejected
(`road_verdict_counts`: road 37, terrain_ribbon 29, ambiguous 7). **Half the maps feeding
the width/tortuosity/junction statistics are not roads.** Every archetype file marks its
road figures as indicative.

**f. `reference/mapformat` disagrees with the corpus in five places**
(`attributes.md` sec Discrepancies, `corpus-overview.md` sec "There are no beta-era maps here"):

1. `attr-atr.md`'s paint-convention table is not the corpus norm -- 116 of 142 maps write
   nothing above `0x07`.
2. `attr-atr.md` and `codec/attr.py` name bits 3-7 that the engine does not name.
   `WorldEditor.rc:1388-1396` labels only Block / Water / No-PVP. In particular **bit 3 is
   not a "banshop"**: it is a map-wide constant present on 100 % of the cells of 17 maps
   and absent from 121.
3. **The documented `server_attr` recipe will brick 17 maps.** "Copy each client attr byte
   verbatim into a DWORD" plus "the server reads bit 7 as `ATTR_OBJECT`" makes
   `metin2_map_a3`, `c3`, `trent`, `guild_war1/2`, `guild_01/03`, `monkeydungeon` x3,
   `t1`-`t4`, `map_a2`, `map_n_snowm_01` and `map_n_threeway` fully impassable
   server-side, because `0x80` is set on every cell. **Mask before writing.**
4. "Keep `ATTRIBUTE_WATER` consistent with `water.wtr`" describes an invariant the shipped
   data does not hold -- see sec 6.
5. The README's claim that `metin2_map_c1` is a 5-file beta map is **false**:
   `metin2_map_c1/000000/` holds all ten modern files, and **there are no beta-era maps in
   this corpus at all**.

**g. Format findings not in the spec** (`corpus-overview.md` sec 5), all of which a parser
must handle:

- `metin2_map_treasure_hunt` writes field 3 as `CRC#sx#sy#sz` in all 288 records -- the
  only map that does. **Split on `#` and take element 0.**
- `setting.txt` supports undocumented `Environment1`...`Environment8`
  (`metin2_12zi_stage`, `elemental_01/02`) and
  `EnvironmentRange<N> x0 y0 x1 y1 <name>.msenv` (`elemental_01/02`, units are half-cells
  = 1 m -- inferred from two files, not confirmed against loader source).
- `metin2_map_t1/setting.txt` ends with a stray truncated line `ungeon2.msenv`.
- **Sector directories can exceed `MapSize`**: `devilscatacomb` declares 7x7 and ships 54
  folders including a whole `x=7` column; `trent02` declares 3x3 and ships 4x4 = 16.
- Four maps break the `BasePosition` 25,600 alignment rule.
- Three maps ship a partial or attr-only sector set; 26 ship none at all; three
  (`metin2_guild_village_01/02/03`) have **no `setting.txt`**.

---

## Sources

`corpus-overview.md` ; `placement.md` ; `textures.md` ; `environments.md` ;
`attributes.md` ; `objects.md` ; `catalog/map-taxonomy.json` ;
`catalog/stats-objects.json` ; `catalog/stats-terrain.json` ;
`catalog/stats-tiles.json` ; `catalog/stats-attr.json` ; `catalog/affinity.json` ;
`catalog/cooccurrence.json` ; `catalog/textures.json` ; `catalog/environments.json` ;
`catalog/roads.json` ; `scripts/m2map/gen/spec.py` ;
`scripts/m2map/gen/texture.py` ; `scripts/m2map/gen/objects.py`

---

## Distance to water is a per-species rule, and it cuts both ways

`affinity.json` measures `d_water_cm` for 349 of 420 catalogued CRCs and all 72
families, and the spread between archetypes is large enough that ignoring it
produces visibly wrong maps:

| Family | d(water) p25 / p50 / p75, metres | Reading |
|---|---|---|
| `tree/n2` (arid) | 37 / **200** / 345 | avoids water |
| `tree/n1` (winter) | 30 / **107** / 334 | avoids water |
| `tree/b1` (broadleaf) | 16 / **54** / 146 | indifferent |
| `tree/b3` | 12 / **53** / 131 | indifferent |
| `zone/b/obj` (clutter) | 14 / **62** / 150 | indifferent |

Every archetype's tier table now carries a `water_m` column with the observed
p25/p50/p75 and a suggested `MapSpec.water_distance_m` band. 74 of 221 rows
warrant a minimum; the other 124 are unconstrained.

**Use the band, not the texture.** The obvious-looking way to put props at a
waterline is to pin them to the shore texture with `on_tiles`. It does not work,
and it fails *silently*: the splat is a per-tile stipple (see sec 5), so on a
1x1 map with an oasis only about a dozen tiles actually carry the shore slot.
Measured: pinning 20 palms and 10 barrels that way placed 3 palms and 0 barrels.
Switching to `water_distance_m=(0, 11)` placed all of them.

**Scale the magnitude to the map.** These distances were measured on 2x4 to 6x6
maps. A 200 m minimum on a 1x1 map (256 m across) excludes the entire surface.
Keep the *rule* -- arid flora stands back from water -- and scale the number to
the map, saying that you did.

**The corpus decorates oases with props, not plants.** `03-desert.md` puts it
plainly: "do not ring an oasis with ferns -- decorate it with props". Palms
around a desert pool are an authored choice, not corpus behaviour; if you make
it, say so rather than presenting it as measured.

---

## Every map occludes its horizon. Only the instrument varies.

A player must never see past the world. The corpus does this two ways, and which
one an archetype uses is measurable.

**Measured**: stitch each map's `height.raw` into one grid and compare the outer
64 m ring to the interior, per archetype (n=111 maps with own terrain).

| Archetype | ring lift vs interior | instrument |
|---|---|---|
| `field_valley` | **+3,836 cm** | terrain ridge |
| `field_empire` | +2,579 | terrain ridge |
| `ice_valley` | +2,570 | terrain ridge |
| `arena_pvp` | +2,104 | terrain ridge |
| `empire_war` | +1,724 | terrain ridge |
| `guild_village` | +1,456 | terrain ridge |
| `darkforest_coast` | +1,260 | terrain ridge |
| `event_instance` | +1,024 | terrain ridge |
| `eastplain` | +829 | terrain ridge |
| `trent_forest` | +738 | terrain ridge |
| `desert` | +350 median, **+4,474 on the reference map** | mixed |
| `dungeon_block` | **0** | fog |
| `dungeon_themed` | **0** | fog |
| `elemental` | 0 | fog |
| `flame_field` | -188 | fog |
| `snow_field` | **-1,338** | fog |

Outdoor median **+1,351 cm**; interior median **exactly 0**, corner lift also
exactly 0. 62% of outdoor maps exceed +300 cm, and the flagships are far higher:
`metin2_map_a1` +4,518, `c1` +4,662, `a3` +4,655, `n_desert_01` +4,474.

### The discriminator is `Fog.NearDistance`, not distance

Read from the `.msenv` files themselves:

| Environment | ring lift | `NearDistance` | `FarDistance` |
|---|---|---|---|
| `a1.msenv` (field_empire) | +4,518 | **5,000** | 20,000 |
| `dark.msenv` (dungeon) | 0 | 5,000 | 20,000 |
| `milgyo.msenv` (desert) | +4,474 on ref | **1** | 50,000 |
| `N-snowm01.msenv` (snow) | -1,338 | **1** | 40,000 |

`NearDistance 5000` leaves a clear 50 m foreground, so something solid has to
stop the eye — a ridge outdoors, walls in a dungeon. `NearDistance 1` starts the
haze at the camera and accumulates over the whole view, which occludes on its
own. That is why `snow_field` sits *on* the high ground with edges falling away
and still reads as enclosed, and why the desert needs less rim than the empire
field despite being open.

**So the rule is not "always build mountains".** It is: pick an instrument and
commit. A map with `NearDistance 5000` and no rim lets the player see the world
end. A map with a rim *and* haze from the camera is merely wasteful.

### Two traps when building the rim

**Water must cut through it.** A ridge raised across a river's exit lifts the
bed and the river runs uphill off the map — on the first attempt here it broke a
continuous watercourse into three pieces stepping up toward each edge. Suppress
the ridge where water reaches the boundary so the valley passes through. The wall
stops the player, not the river.

**The rim invalidates the archetype's terrain statistics.** A 3,500 cm rise over
40 m is a ~41° wall. Including it moved the reported slope p50 from 4.1 to 16.0
and the flat fraction from 37% to 6% — figures that look like a broken generator
when checked against archetype targets, because those targets describe *ground
the player stands on*. Measure and report the interior; report the rim
separately.

**Corners specifically.** Use the max of the two axis ramps, not their sum. A sum
peaks at the corners and sags mid-edge, leaving a notch the player can see
through — which is the opposite of the requirement.

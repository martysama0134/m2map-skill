# The attribute (collision) grammar

What the 8 bits of `attr.atr` are actually used for in the 142-map Ymir/GF
corpus, and what a generator should emit per archetype. Everything here is a
measurement over `<CORPUS>`; the raw numbers live in
[`catalog/stats-attr.json`](catalog/stats-attr.json) and are reproducible with

```
python -m m2map.mine.attr_stats --corpus <CORPUS> \
  --taxonomy reference/catalog/map-taxonomy.json \
  --property-root <pack>/property/property \
  --out reference/catalog/stats-attr.json
```

**Corpus measured:** 116 maps with sector data (26 of the 142 are parent-map
proxies with no sectors), **1,343 sectors**, **88,014,848 attr cells**
(1 cell = 100 cm, so every count below reads as square metres), joined against
**48,774** `areadata.txt` placements resolved through 2,112 property CRCs.

**Method.** `attr.atr` is 256×256 per sector; `height.raw` and `water.wtr` are
128×128. Slope comes from `height.slope_degrees` on the 129×129 vertex grid
(HeightScale from `setting.txt`, 0.5 everywhere; cell 200 cm) and each terrain
cell's slope is shared by its 2×2 attr cells — the same 2×2 mapping the water
brush uses (`MapAccessorTerrain.cpp:393-397`). Object placements land at attr
cell `(x/100, -y/100)`; that mapping was verified against three deliberately
wrong ones (Building centre-block rate 0.89/0.92/0.92 on a1/b1/c1 versus
0.21–0.37 for transposed or Y-mirrored variants, map block rate 0.50–0.58).

---

## 1. Which flags are real

| Bit | Hex | Engine name | Cells | % of corpus | Maps using it | Verdict |
|---|---|---|---|---|---|---|
| 0 | `0x01` | `ATTRIBUTE_BLOCK` | 64,949,908 | **73.79 %** | all | real, the only one that matters for movement |
| 1 | `0x02` | `ATTRIBUTE_WATER` | 4,008,929 | **4.56 %** | 62 have water at all, 30 paint the flag | real but under-painted (§6) |
| 2 | `0x04` | `ATTRIBUTE_BANPK` | 1,282,946 | **1.46 %** | 37 | real, brush-stamped (§7) |
| 3 | `0x08` | — ("banshop") | 14,164,330 | 16.09 % | 21 | **not a flag.** A map-wide constant marker |
| 4 | `0x10` | — ("flag5") | 496,744 | 0.56 % | **2** | vestigial |
| 5 | `0x20` | — ("flag6") | 182,474 | 0.21 % | **1** | vestigial |
| 6 | `0x40` | — ("flag7") | 14,212,200 | 16.15 % | 24 | **not a flag.** Map-wide constant marker |
| 7 | `0x80` | — ("object", server `ATTR_OBJECT`) | 13,832,490 | 15.72 % | 20 | **not a flag, and a hazard** (§3) |

Only bits 0–2 are named anywhere in the engine. `WorldEditor.rc:1388-1396`
labels the eight brush checkboxes `"Block"`, `"Water"`, `"No-PVP"`, then
literally `"3"`, `"4"`, `"5"`, `"6"`, `"7"`. The names `banshop`/`flag5..7`/
`object` in `codec/attr.py` and in M2-MapForge (`index.html:311-319`) are
community inventions with **no engine backing** — bit 3 is not a shop ban.

Top attribute bytes across the corpus (24 more in the JSON, 37 distinct values
total):

| Byte | Cells | % | Engine bits | Where |
|---|---|---|---|---|
| `0x01` | 50,504,686 | 57.38 | block | everywhere |
| `0x00` | 17,581,130 | 19.98 | — | everywhere |
| `0xC9` | 7,463,812 | 8.48 | block | the paint family (§3) |
| `0xC8` | 3,297,020 | 3.75 | — | the paint family |
| `0x03` | 2,438,090 | 2.77 | block+water | everywhere |
| `0x09` | 1,566,050 | 1.78 | block | maze/monkey dungeons |
| `0xC0` | 1,343,092 | 1.53 | — | map_a2 family |
| `0xCB` | 1,282,960 | 1.46 | block+water | the paint family |
| `0x05` | 658,072 | 0.75 | block+safezone | town/arena |
| `0x04` | 214,260 | 0.24 | safezone | town cores |
| `0x02` | 178,197 | 0.20 | water | shorelines |

**116 of 142 maps write nothing above `0x07`.** The clean three-bit encoding is
the corpus norm; 81.3 % of all cells are one of `0x00`–`0x05`.

---

## 2. Generator rule for the flag bits

> Emit `0x00`–`0x07` only. Never set bits 3–7.

That is what 90 of the 116 sector-bearing maps do, it is what every engine code
path reads, and it is the only encoding that cannot break server collision (§3).
The `attr-atr.md` paint-convention table (`0x40` land / `0xC8` mountain / …) is
descriptive of one authoring family, not a requirement — see the discrepancy
list at the end.

---

## 3. The paint-byte family, and why `0x80` is dangerous

26 maps carry bytes above `0x07`. In all of them the low three bits still carry
the correct engine meaning; the high bits are a constant overlay:

| Overlay | Maps | Coverage within those maps |
|---|---|---|
| `+0x08` | 21 | 100 % of cells in 17 of them; 68.1 % (map_a2, map_n_threeway), 56.3 % (trent02), 53.4 % (duel, pvp_arena) |
| `+0x40` | 24 | 100 % in 20; partial in devilscatacomb (8.5 %), smhgate_devils (7.5 %), trent02 (56.3 %) |
| `+0x80` | 20 | **100 % in 17 maps**: map_a2, map_n_snowm_01, map_n_threeway, guild_war1, guild_war2, **a3**, **c3**, guild_01, guild_03, monkeydungeon ×3, t1–t4, trent. Partial: duel/pvp_arena 53.4 %, trent02 56.3 % |

So `metin2_map_a3` and `metin2_map_c3` — two shipped highland field maps — have
`0x80` set on **every single cell**, giving byte values `0xC8` (walkable) and
`0xC9` (blocked).

**The hazard.** `server-attr.md` documents, and
`WorldEditor/DataCtrl/ServerAttrGenerator.cpp:109-138` implements, a generator
that copies the attr byte *verbatim* into a DWORD (`BuildSectorCellsFromAttr`;
the `sanitizeWeirdFlags` path only clears bits ≥ `0x100`, which a byte can never
have). The server treats `0x80` as `ATTR_OBJECT` and its movement check is
`ATTR_BLOCK | ATTR_OBJECT` (`sectree.h:25-31`). Regenerate `server_attr` from
`metin2_map_a3/**/attr.atr` with the documented recipe and **the entire map
becomes impassable server-side**.

No map in the corpus ships a `server_attr` (`rglob("server_attr")` over
`<CORPUS>` → 0 hits), so the original Ymir pipeline's masking behaviour cannot be
observed. Either it masked to `0x07`, or those maps' server files were authored
by hand.

**Generator rule:** when producing `server_attr`, mask the attr byte to `0x07`
unless you deliberately want object collision, and never emit `0x80` into
`attr.atr` in the first place.

---

## 4. Block vs slope

The corpus splits cleanly into two authoring styles, measured (not assumed) by
the block rate on *clean* cells — cells that have slope, are not water, are not
in the border strip, and have no `areadata` placement within 12 m:

| Style | Maps | Block % of map | Block rate on clean **flat** ground (slope < 1°) |
|---|---|---|---|
| `slope_driven` | 59 | 60.4 % | **0.052** |
| `painted_box` | 57 | 87.2 % | **0.852** |

A `painted_box` map (every dungeon interior, the elemental and sungzi
instances, the arenas) paints block wholesale and slope explains nothing there:
Youden's *J* for `slope ≥ T` predicting block is only 0.176. Fitting a slope
threshold on those maps is meaningless — **do not**.

### The threshold, measured on the 59 `slope_driven` maps

`P(BLOCK | slope)` on the clean set:

| Slope band | Cells | Blocked | P(block) |
|---|---|---|---|
| 0–1° | 1,393,350 | 71,895 | 0.052 |
| 1–5° | 2,659,514 | 125,910 | 0.047 |
| 5–10° | 2,723,996 | 195,656 | 0.072 |
| 10–15° | 1,723,527 | 223,340 | 0.130 |
| **15–20°** | 1,090,900 | 251,282 | **0.230** |
| **20–25°** | 737,843 | 280,564 | **0.380** |
| **25–30°** | 562,248 | 313,837 | **0.558** ← crosses ½ |
| 30–35° | 471,044 | 337,327 | 0.716 |
| 35–40° | 437,188 | 363,919 | 0.832 |
| 40–45° | 421,810 | 380,049 | 0.901 |
| 45–50° | 406,762 | 386,054 | 0.949 |
| 50–60° | 742,704 | 727,699 | 0.980 |
| 60–70° | 544,711 | 541,247 | 0.994 |
| 70–80° | 263,257 | 260,515 | 0.990 |
| 80–90° | 49,767 | 42,937 | 0.863 |

* **Youden-optimal cut: `slope ≥ 20°`** — TPR 0.807, FPR 0.103, precision 0.784, J = 0.704.
* F1-optimal cut: `slope ≥ 23°` — precision 0.833, recall 0.771, F1 0.800.
* P(block) crosses ½ at **25–30°** (interpolating ≈ 27°).
* Per-map fitted thresholds (59 maps): median **17°**, quartiles 10°–21°. Nine maps degenerate to 1° (they block almost everything).

F1 is reported only as a secondary statistic: with P(block) near 1 it collapses
to T = 0 (on the whole corpus its optimum is literally 0°). Youden's J is
prior-invariant, which is why the miner uses it.

### How much block does slope *not* explain

Every BLOCK cell is charged to exactly one cause, first match wins:
`slope ≥ T` → water → within 12 m of a placement → connected to the map edge
(out of bounds) → residual. T is the map's own fitted threshold.

| Group | Block cells | slope | water | object halo | flat out-of-bounds | residual |
|---|---|---|---|---|---|---|
| **whole corpus** | 64,949,908 | **44.8 %** | 7.4 % | 4.0 % | 38.9 % | 4.9 % |
| `slope_driven` (59) | 26,598,513 | **72.6 %** | 14.8 % | 2.5 % | 8.8 % | 1.4 % |
| `painted_box` (57) | 38,351,395 | **25.6 %** | 2.2 % | 5.0 % | 59.8 % | 7.4 % |

So on a sculpted outdoor map, roughly **27 % of the block is not terrain** —
and almost all of that 27 % is water surfaces (14.8 %) plus the flat paint that
seals the map edge (8.8 %). Only **1.4 %** is genuinely unexplained interior
artist intent. On a painted interior it is the other way round: 74 % of block is
not slope, dominated by the wall slab.

Counter-examples matter too: at the fitted threshold, **4.3 %** of steep cells
corpus-wide are *walkable* (steep-but-passable ramps and paths cut into
hillsides). A generator that blocks every cell over the threshold will seal
mountain passes that the originals left open.

---

## 5. Block vs objects

### Two footprint policies, and they are bimodal

For each map, compare the Building/DungeonBlock centre-cell block rate against a
**local** control — the same placement offset 30 m N/E/S/W (the map-wide block
rate is a useless control when a dungeon is 90 % block):

| Policy | Maps | Median centre-block rate | Median local lift | Pooled rate |
|---|---|---|---|---|
| `painted` | 51 | 0.909 | **1.75×** | 15,851 / 17,299 = **0.916** |
| `mixed` | 17 | — | 1.05–1.30× | — |
| `model_only` | 35 | 0.091 | **0.14×** | 666 / 5,450 = **0.122** |
| no buildings | 11 | — | — | — |

`model_only` maps place buildings on cells that are *less* blocked than their
surroundings — the artist deliberately cleared flat ground for them and left
collision to the model's own `.mdatr` (`property.collision_file`, derived from
`buildingfile`). `map_a2` and its verbatim copy `map_n_threeway`, `wl_01`,
`t1`–`t3` and most dungeon-block maps work this way.

By archetype: `darkforest_coast`, `eastplain`, `empire_war`, `guild_village`,
`ice_valley`, `trent_forest` are 100 % `painted`; `field_empire` is 14 painted /
2 mixed / 1 model_only; `dungeon_block` is 11 model_only / 4 no-buildings /
2 mixed / 1 painted; `elemental` and `snow_field` are mostly `model_only`.

Corpus-wide centre-cell block rate by property type (all maps pooled):
Building 82.3 % (n=23,044), Effect 86.6 % (n=8,117), Tree 35.7 % (n=14,281),
DungeonBlock 22.1 % (n=3,332).

### Footprint size implied by the blocked cells — a weak signal

Method: 65×65 m window around each placement, Chebyshev ring fill on the BLOCK
mask, footprint radius = the last ring at least 50 % full; component bbox and
area from the 4-connected blocked component containing the centre; a placement
counts only if it is ≥ 8 m (Chebyshev) from any other Building/DungeonBlock/Tree
and its component does not touch the window edge.

**Only 881 of 48,774 placements (1.8 %) yield a clean measurement.** The
rejection breakdown is the finding:

| Reason | Placements |
|---|---|
| blocked component saturates the 32 m window | **25,417** |
| centre cell is not blocked at all | 16,758 |
| another solid placement within 8 m | 5,037 |
| window falls off the map / over a missing sector | 681 |
| **measured** | **881** |

In shipped maps a building footprint is not a discrete stamp — it is fused into
a larger painted blob (town ground, mountain, dungeon wall). Anything bigger
than ~30 m across is unmeasurable this way.

What survives, per property type (CRCs with ≥ 3 clean measurements):

| Type | CRCs | Median bbox (short × long) | Median equivalent radius |
|---|---|---|---|
| Building | 80 | **5 × 6 m** | 2.86 m |
| Tree | 21 | **2 × 2 m** | 1.13 m |
| Effect | 1 | 15.5 × 16 m | 8.14 m |

Best-sampled individual models (full table: `crc_footprints` in the JSON, 1,676
CRCs, sorted by `n_measured`):

| CRC | Model | n | measured | bbox | equiv r |
|---|---|---|---|---|---|
| 943480121 | `zone/b/obj/general_obj_bigtoewr03.gr2` | 88 | 45 | 4 × 4 | 2.26 |
| 865570388 | `zone/b/obj/general_obj_stone10.gr2` | 173 | 24 | 3 × 4 | 1.95 |
| 2288483325 | `zone/b/obj/ob-b1-013-lamp02.gr2` | 65 | 22 | 1 × 1 | 0.56 |
| 163114965 | `zone/n/obj/map_n_flame_01/general_obj_bigtower03.gr2` | 25 | 15 | 7 × 8 | 3.57 |
| 481554143 | `zone/eastplain/deadmushroom_05.gr2` | 19 | 13 | 14 × 18 | 7.46 |
| 3456333148 | `zone/b/obj/general_obj_stone18.gr2` | 131 | 11 | 7 × 7 | 3.61 |
| 26807040 | `zone/b/obj/general_obj_stone19.gr2` | 110 | 9 | 7 × 8 | 3.95 |

### Cross-check against the GR2 / `.mdatr` pass

`catalog/models.json` carries the GR2 bounding box (`size_xyz`, cm) and, where a
`.mdatr` exists, `mdatr.collision_size_xyz`. Joining on CRC gives **80 models**
with both an attr-derived footprint (≥ 3 clean measurements) and a mesh size —
run by the miner itself with `--models catalog/models.json`, written to
`gr2_crosscheck` in the JSON.

Ratio of attr footprint to model size, per axis (attr / model, so > 1 = painted
wider than the mesh):

| Comparison | n | p05 | p25 | **median** | p75 | p95 |
|---|---|---|---|---|---|---|
| attr short edge / GR2 short edge | 80 | 0.47 | 0.94 | **1.13** | 1.37 | 7.50 |
| attr long edge / GR2 long edge | 80 | 0.23 | 0.94 | **1.11** | 1.26 | 2.54 |
| attr short edge / `.mdatr` collision short edge | 73 | 0.54 | 0.78 | **1.01** | 1.23 | 4.07 |

**The two independent estimates agree.** For the middle half of models the attr
paint is within ±30 % of the GR2 XY box, and it is centred almost exactly on the
`.mdatr` collision box (median 1.01). Worked examples:

| Model | attr bbox | GR2 XY | `.mdatr` XY |
|---|---|---|---|
| `general_obj_stone19.gr2` | 7 × 8 m | 6.47 × 7.06 | 6.68 × 6.68 |
| `general_obj_stone13.gr2` | 7.5 × 8 m | 6.86 × 7.83 | 7.37 × 7.37 |
| `general_obj_stone18.gr2` | 7 × 7 m | 6.33 × 6.34 | 6.22 × 6.22 |
| `eastplain/deadmushroom_05.gr2` | 14 × 18 m | 14.10 × 18.71 | 14.26 × 18.30 |
| `eastplain/deadmushroom_03.gr2` | 5 × 6 m | 5.38 × 5.58 | 5.71 × 5.71 |
| `b_general_obj_01_1.gr2` | 8.5 × 9.5 m | 7.93 × 8.43 | 10.94 × 14.92 |

The tails are all explainable, and they tell you where *not* to trust attr:

* **Sub-metre meshes.** `sign.gr2` is a 0.1 m-thick plane, attr says 1 × 2 m
  (ratio 9.9); `general_obj_stonepillar_01/02` are 0.8–0.9 m, attr says 2 × 2 m
  (ratio 2.2–2.5). One attr cell is the floor.
* **Meshes whose bbox is not their footprint.** `n/desert/cactus_01.gr2` has a
  13.6 × 17.5 m GR2 box but only 4 × 4 m of attr — the arms spread far above the
  ground. Its `.mdatr` agrees with attr (2.97 m). Use `.mdatr`, not `size_xyz`,
  whenever it exists (1,482 of 2,112 properties have one).
* **Trees contribute nothing.** All 80 comparable rows are Buildings; `.spt`
  trees come back as `spt-partial` in the model pass and their attr footprint is
  the degenerate 2 × 2 m anyway.

**Further guidance when joining the two passes.** Join on
`crc_footprints[].model`; expect these biases, in this order of size:

* The attr grid quantises to 1 m and a stamp is at least one cell, so anything
  whose model is < 1 m reads as 1 × 1 — the estimate is an **over**-estimate at
  the small end (`ob-b1-013-lamp02` is a lamp post).
* Trees measure 2 × 2 m regardless of species, and their median ring inradius is
  **0.0** — the centre cell is blocked but ring 1 is not. Trees have no painted
  footprint; that 35.7 % centre-block rate is the tree standing on ground that
  was blocked for another reason. **Do not derive tree collision from attr.**
* Anything above ~30 m is missing entirely (saturated), so the table has no
  large buildings in it. A GR2 pass will produce sizes attr cannot confirm.
* Every measurement comes from a `painted` map by construction; `model_only`
  maps contribute nothing.

---

## 6. Water flag vs `water.wtr` — which is authoritative

`water.wtr` is the authority for *where water is*; `ATTRIBUTE_WATER` is a
partial, hand-painted subset of it.

| | Cells |
|---|---|
| `water.wtr` wet (at attr resolution) | 12,817,324 |
| `ATTRIBUTE_WATER` set | 4,008,929 |
| both | 3,986,495 |
| **wet with no flag** | **8,830,829 (68.9 % of wet)** |
| flag with no wet cell | 22,434 (0.56 % of flagged) |

Only **3 of 62** water-bearing maps agree exactly. So the spec's "keep both in
sync" is not what shipped. The editor itself stamps 1:1 — `SetWaterMap`
(`MapAccessorTerrain.cpp:366-484`) sets/clears `ATTRIBUTE_WATER` on the 2×2 attr
block for every water cell it paints or erases — so the disagreement is
authoring, not tooling.

**The rule the good maps follow.** Define *submerged* = wet in `water.wtr`
**and** the terrain cell's lowest corner is below that layer's surface
(`min(4 corner vertices) * 0.5 < layerHeight * 0.5`). Against that predicate the
flag is far better behaved:

| Group | precision vs submerged | recall vs submerged |
|---|---|---|
| whole corpus | 0.773 | 0.474 |
| `slope_driven` maps (44 with water) | 0.782 | 0.547 |
| **`field_empire`** (15 with water) | **0.980** | **0.847** |
| `empire_war` | 1.000 | 0.394 |
| `field_valley` | 0.765 | 0.941 |
| `ice_valley` | 0.763 | 0.936 |
| `guild_village` | 0.530 | 0.995 |

Per-map: `metin2_map_a1` flags 50,431 of 57,296 submerged cells (precision
0.987, recall 0.869); `metin2_map_c1` 87,679 / 89,149; `metin2_map_b1`
72,365 / 75,833. Meanwhile `metin2_map_capedragonhead` flags 2,508 of 111,539
submerged cells, `metin2_map_eastplain_01` 6,681 of 104,558, and
`metin2_12zi_stage` 825 of 110,381 — those maps simply never painted it. 30 of
62 water maps paint the flag at all (≥ 20 % of submerged area covered).

The other half of the story: 80.2 % of the wet-but-unflagged cells are BLOCK.
Deep water on these maps is fenced off with collision rather than marked as
water.

**Generator rule:** derive `ATTRIBUTE_WATER` from `water.wtr` ∧ *submerged*.
That reproduces the empire capitals to ~98 % precision, and it is the only rule
that keeps the renderer (which trusts `water.wtr`) and the client's
`isAttrOn(ATTRIBUTE_WATER)` from disagreeing.

---

## 7. Safezone (`ATTRIBUTE_BANPK`)

37 of 116 maps use it; 1.46 % of all cells. 58 components of ≥ 16 m² across the
corpus. Component shapes:

| Shape | Components |
|---|---|
| circular brush stamp (fill 0.72–0.85 in a square bbox) | **34** |
| solid rectangle / whole map or whole sector (fill ≥ 0.97) | 8 |
| irregular (overlapping stamps, hand-edited) | 16 |

The circular ones are literal editor brush prints — fill ratio clusters at
π/4 = 0.785 (measured median 0.788, quartiles 0.766–0.817). Observed diameters,
all even: **14 (×6), 20, 24 (×4), 28, 32 (×4), 36, 40, 44 (×4), 48, 56 (×2),
68 m**. Area follows πr² exactly: the 56 m disc is 2,472 cells (π·28² = 2,463).

Extent: median component area **1,539 m²**, quartiles 665–10,531 m²; median
bbox edge **44 m**, quartiles 31–127 m.

**Where it goes.** On the six empire capitals it is a small number of clean
discs over the town squares, and it is essentially *never* on blocked ground:
a1 0.4 % of safezone cells are BLOCK, b1 0.0 %, c1 0.0 %, b3 0.0 %, c3 0.1 %,
a3 1.5 %. a1 has 4 discs (d = 56 m town core at (646, 586), two d = 32 m, one
d = 24 m); c1 has 4 (d = 48, 36, 36, 32); b1 has 4 (d = 44, 28, 24, 24).

It is anchored on the spawn point. `metin2_map_spiderdungeon_02` is the one map
in the corpus that ships a server `town.txt`: spawn `384 273` (units of 100 cm),
and its single safezone component's centroid is `(385, 273)` — a 1 m offset,
with the nearest Building 2 m away. Median distance from a safezone centroid to
the nearest Building is 1–30 m across the corpus.

The 8 rectangular ones are a different intent: whole-map peace zones —
`metin2_map_privateshop` and `metin2_map_oxevent` (both 262,144 cells = the
entire 2×2 map), `map_b_fielddungeon` (entire map, bytes `0x0C`/`0x0D`),
`metin2_map_smhdungeon_01` and `metin2_map_labyrinth` (one whole sector each).
On those the safezone freely overlaps block (69–96 % of safezone cells blocked).

**Generator rule:** circular stamp, diameter 24–56 m, centred on the spawn/town
centre, on walkable ground. Whole-map fill only for a no-combat map type.

---

## 8. Map borders

The player is stopped by a BLOCK band, and on outdoor maps that band sits on
terrain the artist also raised.

Measured as the consecutive BLOCK run inward from each edge cell (this exposes
holes that a row-average would hide), over the 59 `slope_driven` maps:

* **100 %** of edge cells are blocked (median across maps).
* Median seal depth **119 m** (quartiles 76–206 m); at the 5th percentile of
  edge cells the seal is still **52 m** deep.
* 17 of 59 maps have at least one hole (a run of 0) somewhere on the perimeter.
* Rim slope median **40.3°** versus interior median **10.7°**, and **77.9 %** of
  the rim's blocked cells are steeper than 25°. The border is a mountain wall,
  not just paint.

On `painted_box` maps the rim is flat (median rim slope 0.0°, only 21 % of rim
block is steep) — the seal is pure paint, and the "band" runs away because the
whole map is a blocked slab with corridors carved out.

Exceptions worth knowing (the only maps in the corpus that are not sealed):

| Map | Edge cells blocked | Holes | Median run |
|---|---|---|---|
| `metin2_map_empirewar01` / `02` | 45.4 % | 1,118 m | 0 m |
| `metin2_map_smhgate_a1` | 69.2 % | 394 m | 35 m |
| `metin2_map_boss_awaken_skipia` / `boss_crack_skipia` | 88.4 % | 119 m | 256 m |

Per-archetype rim vs interior slope (medians, degrees):
`field_valley` 50/18, `empire_war` 51/12, `arena_pvp` 44/0, `guild_village`
43/6, `ice_valley` 36/14, `field_empire` 34/6, `event_instance` 28/14,
`trent_forest` 25/10, `eastplain` 22/8, `snow_field` 20/27, `darkforest_coast`
20/14, `dungeon_themed` 6/7, `desert` 3/5, `elemental` 0/1, `dungeon_block`
0/0.

**Generator rule:** raise terrain to > 25° for 60–120 m around the perimeter,
then set BLOCK from the slope rule; fill any remaining edge cell that the slope
rule missed. For a box-type map, paint a 15–30 m block shell instead.

---

## 9. `server_attr` vs `attr.atr`

**No map in the corpus ships one** — `server_attr` is a server-side file and
`<CORPUS>` is a client pack (`pathlib.Path("<CORPUS>").rglob("server_attr")` → 0
hits, and the same search over the client pack finds none either). The
documented 2×2 relationship therefore cannot be checked against shipped bytes;
the miner verifies it synthetically instead (`--selftest-server-attr <mapdir>`),
building a `server_attr` from a map's own `attr.atr` files with
`server_attr.from_attr_maps` and comparing `to_attr_grid` back against the
client bytes:

| Map | Sectrees | Header | Bytes | Cells compared | Mismatched |
|---|---|---|---|---|---|
| `gm_guild_build` | 1 × 1 | 4 × 4 | 13,079 | 65,536 | **0** |
| `map_a2` | 6 × 6 | **24 × 24** | 735,861 | 2,359,296 | **0** |
| `metin2_map_wl_01` | 4 × 4 | 16 × 16 | 231,637 | 1,048,576 | **0** |
| `metin2_map_a1` | 4 × 5 | 16 × 20 | 345,391 | 1,310,720 | **0** |

The relationship holds exactly: header = `MapSize × 4`, one client attr byte →
a 2 × 2 block of DWORDs, y-major block order. `map_a2`'s header `24 × 24`
matches the byte-level validation quoted in `server-attr.md`. Our file is
735,861 bytes against the documented shipped 589,506 — same data, different LZO
encoder, which is expected (`codec/lzo1x.py` is a greedy single-slot-hash
encoder, not minilzo's).

Disagreement rate against shipped data: **unmeasurable, 0 samples.** Do not
claim it is zero in production; claim only that the transform is lossless.

---

## 10. Per-archetype policy

Block budget percentages are of that archetype's BLOCK cells, at each map's own
fitted slope threshold. `sz %` is safezone as a fraction of the archetype's
cells; `seal` is the median per-map median edge run.

| Archetype | Maps | style (slope/box) | block % | thr | slope % | water % | obj % | out-of-bounds % | residual % | sz % | seal m | footprint policy |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `field_empire` | 18 | 14 / 4 | 60.3 | 20° | 65.1 | 16.9 | 3.1 | 14.5 | 0.4 | 3.49 | 123 | painted 14 / mixed 2 / model 1 |
| `field_valley` | 3 | 3 / 0 | 66.3 | 22° | 81.1 | 12.7 | 0.6 | 4.7 | 0.9 | 0.02 | 142 | model 2 / mixed 1 |
| `darkforest_coast` | 5 | 5 / 0 | 68.8 | 15° | 69.8 | 14.4 | 4.8 | 8.0 | 3.0 | 1.17 | 119 | painted 5 |
| `eastplain` | 4 | 4 / 0 | 72.4 | 12° | 64.5 | 23.0 | 4.3 | 7.5 | 0.8 | 0.81 | 152 | painted 4 |
| `ice_valley` | 3 | 3 / 0 | 69.5 | 20° | 80.1 | 9.4 | 1.6 | 8.6 | 0.3 | 0.00 | 185 | painted 3 |
| `guild_village` | 4 | 4 / 0 | 62.4 | 7° | 88.3 | 1.5 | 5.2 | 4.7 | 0.2 | 0.00 | 56 | painted 4 |
| `empire_war` | 3 | 3 / 0 | 50.7 | 21° | 79.3 | 9.4 | 5.9 | 4.1 | 1.2 | 0.00 | **0** | painted 3 |
| `trent_forest` | 2 | 1 / 1 | 64.7 | 22° † | 38.9 | 21.3 | 3.7 | 35.0 | 1.1 | 0.39 | 167 | painted 2 |
| `desert` | 8 | 3 / 5 | 61.6 | 29° † | 34.2 | 0.6 | 0.9 | **62.5** | 1.8 | 0.93 | 332 | model 4 / painted 2 / mixed 1 |
| `snow_field` | 5 | 1 / 4 | 74.1 | 19° † | 63.6 | 0.0 | 3.3 | 32.8 | 0.3 | 0.13 | 512 | model 4 / painted 1 |
| `flame_field` | 5 | 2 / 3 | 65.1 | 21° † | 53.0 | 0.0 | 0.5 | 44.6 | 1.8 | 1.65 | 303 | none 3 / mixed 1 / painted 1 |
| `event_instance` | 10 | 6 / 4 | 75.4 | 26° | 71.0 | 18.8 | 1.2 | 8.8 | 0.3 | 0.02 | 512 | painted 5 / model 4 / mixed 1 |
| `arena_pvp` | 6 | 3 / 3 | 78.1 | 9° † | 69.5 | 3.8 | 14.2 | 11.8 | 0.8 | **58.7** | 155 | mixed 3 / painted 2 / model 1 |
| `dungeon_themed` | 12 | 2 / 10 | 88.2 | 18° † | 27.5 | 3.0 | 2.3 | 56.9 | 10.4 | 0.04 | 421 | mixed 6 / painted 3 / model 2 |
| `dungeon_block` | 20 | 2 / 18 | 81.9 | 10° † | 3.9 | 0.0 | 10.2 | **71.4** | 14.5 | 0.45 | 218 | model 11 / none 4 / mixed 2 |
| `elemental` | 4 | 0 / 4 | 90.2 | 31° † | 23.4 | 0.0 | 1.6 | 74.6 | 0.4 | 0.00 | 707 | model 3 / none 1 |
| `dev_stub` | 4 | 3 / 1 | 89.8 | 31° | 75.6 | 7.8 | 0.1 | 16.5 | 0.0 | 0.00 | 93 | model 3 / painted 1 |

† = the archetype is majority `painted_box`, so its fitted threshold is an
artefact of wholesale paint, not a terrain rule; use the `slope_driven` figure
(20°) for anything sculpted.

### Recipe by style

**Sculpted outdoor** (`field_*`, `darkforest_coast`, `eastplain`, `ice_valley`,
`guild_village`, `empire_war`, `trent_forest`):

1. `BLOCK` where slope ≥ **20°** (expect ~73 % of your block to come from here;
   keep ~4 % of steep cells walkable where a path crosses).
2. `WATER` + `BLOCK` on `water.wtr` ∧ submerged (≈ 15 % of block).
3. Optional building footprints if going for the `painted` policy — a 1.75×
   local lift, ~92 % of buildings on block; otherwise leave collision to
   `.mdatr` and place buildings on cleared flat ground.
4. Perimeter: raise terrain and let step 1 seal it; patch the residual edge
   cells (≈ 9 % of block).
5. Safezone: circular stamps d = 24–56 m on the town square, on walkable ground.

**Interior / instanced box** (`dungeon_block`, `dungeon_themed`, `elemental`,
most `desert`/`snow_field`/`flame_field` instances):

1. Paint `BLOCK` everywhere, carve corridors and rooms out of it (60–75 % of
   block ends up edge-connected).
2. No slope rule. No `WATER` (0 % in `dungeon_block`, `elemental`,
   `snow_field`, `flame_field`).
3. `model_only` footprints — buildings sit in the carved-out space.
4. Safezone only if the map has a peace room; then a rectangle, not a disc.

---

## Discrepancies against `reference/mapformat`

1. **`attr-atr.md`'s paint-convention table is not the corpus norm.** It reads
   as though Ymir's maps generally carry `0x40`/`0xC0`-family bytes ("map_a2's
   first sector is full of `0xC9`"). Measured: **116 of 142 maps write nothing
   above `0x07`**, and 81.3 % of all cells are `0x00`–`0x05`. The paint family
   is 26 maps.
2. **`attr-atr.md` / `codec/attr.py` name bits 3–7 that the engine does not
   name.** `WorldEditor.rc:1388-1396` labels only Block / Water / No-PVP; bits
   3–7 are checkboxes labelled `"3"`…`"7"`. In particular **bit 3 is not a
   "banshop"** — it is a map-wide constant present on 100 % of the cells of 17
   maps and absent from 121, which is not how a per-cell gameplay flag behaves.
3. **The documented `server_attr` recipe will brick 17 maps.** "Copy each
   client attr byte verbatim into a DWORD" plus "the server reads bit 7 as
   `ATTR_OBJECT` — a movement blocker" means `metin2_map_a3`, `metin2_map_c3`,
   `metin2_map_trent`, `metin2_guild_war1/2`, `metin2_map_guild_01/03`,
   `monkeydungeon`×3, `t1`–`t4`, `map_a2`, `map_n_snowm_01`, `map_n_threeway`
   become fully impassable server-side, because `0x80` is set on every cell.
   The doc's "never mask bits off on save" advice is actively harmful for those
   maps.
4. **`water-wtr.md` / `attr-atr.md`: "keep `ATTRIBUTE_WATER` consistent with
   `water.wtr`" describes an invariant the shipped data does not hold.** 68.9 %
   of wet cells carry no flag; only 3 of 62 water maps agree exactly. The
   real invariant is the *submerged* predicate (§6), and only about half the
   maps honour even that.
5. **No `server_attr` exists anywhere in the corpus or the client pack**, so
   `server-attr.md`'s "Validation (map_a2, 589,506 bytes)" cannot be
   re-verified here. The header dimensions it quotes (24 × 24) do reproduce.
6. Unresolvable from this data: whether the original Ymir server-side pipeline
   masked the attr byte before writing `server_attr`. Both readings of the
   `0x80` situation are consistent with what is on disk.

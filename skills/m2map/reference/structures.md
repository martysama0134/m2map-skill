# Built Structures — Wall Kits, Compounds and Rotation

**Status: groundwork, not an implemented mode.** Nothing in `scripts/m2map/gen/`
assembles a compound yet; objects are placed as scatter with per-species rules
(`placement.md`). This file records what the corpus says about kit assembly so
the work does not start from scratch. It is measured, not designed.

---

## 1. The one rule that matters most: structural pieces snap to 90°

`taste.md` §1.2 measures the corpus-wide rotation snap at 15°. Kit pieces are
far stricter than that. Roll histograms in 36 bins of 10° for the `c1-038` wall
family — every non-zero bin, across every placement:

| piece | crc | n | non-zero roll bins | angles |
|---|---|---|---|---|
| `c1-038-wall-lin2` | 646376885 | 106 | 0, 9, 18, 27 | 0°, 90°, 180°, 270° |
| `c1-038-wall-lin` | 239800711 | 46 | 0, 9, 18, 27 | 0°, 90°, 180°, 270° |
| `c1-038-wall-corner` | 1977136400 | 48 | 0, 9, 18, 27 | 0°, 90°, 180°, 270° |
| `c1-038-wall-door` | 3268994556 | 21 | 0, 9, 18, 27 | 0°, 90°, 180°, 270° |

**221 placements, zero exceptions.** A wall segment is never at 45°, never at
15°, never at anything but an axis-aligned quarter turn. The four bins are used
fairly evenly (`wall-lin2`: 36/26/24/20), which is what a rectangular compound
needs — two runs on each axis, each facing outward.

Decoration inside the same compound does **not** follow this. `general_obj_
brazier_01` (crc 753920647, n = 40) spreads across 11 of the 36 bins with a
resultant of 0.40. So the rule is not "everything in a compound is axis-aligned"
— it is **structure snaps, dressing scatters**, and mixing the two up is what
makes a hand-built compound look wrong.

> **Rule:** roll ∈ {0, 90, 180, 270} for every wall, gate and corner piece. Keep
> yaw and pitch at 0 — `taste.md` §1.1 measures tilt as a debris channel that
> buildings use in 5.8% of records and `zone/b/building` in 0.1%.

### A compound shares ONE heading

The corollary of §1, and it bites on anything placed as several CRCs at one
spot. Left to the per-family sampler, a warp gate's dais, arch and effect drew
**345, 285 and 105 degrees** — three independent rungs of the ladder for three
pieces of the same object. Nothing in the scatter machinery knows they belong
together.

`ObjectTier.roll_deg` writes an explicit heading and overrides both the sampler
and `align_to_slope`. Use it for every authored compound, and give each piece
the same value.

A *copied* set-piece refines this: the 32 records of the desert camp share
**three** headings — 105, 285 and 315 — and the trees take them too. One
heading per compound you author; a compound you copy brings its own small set,
which is part of what is being copied. `gen/setpiece.py` keeps them, and
`SetPiece.rotated` turns them all together by the measured sign
(`placement.md` §6.w).

---

## 2. The wall module is 10 m exactly

Nearest-neighbour distance to another instance of the **same** piece:

| piece | p25 | p50 | p75 |
|---|---|---|---|
| `c1-038-wall-lin2` | **1000.0 cm** | **1000.0 cm** | **1000.0 cm** |
| `c1-038-wall-lin` | 752.9 cm | 921.9 cm | 1175.2 cm |
| `c1-038-wall-door` | 2687.0 cm | 3394.1 cm | 3700.0 cm |
| `c1-038-wall-corner` | 2261.8 cm | 3800.0 cm | 4800.0 cm |

`wall-lin2` has **no spread at all** — quartiles identical to the centimetre.
That is a module laid end to end on a 10 m pitch, not a hand-placed prop. `lin`
is the shorter variant used to close a run that does not divide evenly, which is
why its distribution is loose. Corners and doors are one per side or one per
compound, so their spacing is a compound dimension rather than a module.

Implication for assembly: lay a rectangle, walk each side in 10 m steps with
`lin2`, patch the remainder with `lin`, put `corner` at each turn and `door`
where the road meets the wall. Do not solve it as a scatter problem.

---

## 3. A worked compound

Supplied as a real example (a guild/village compound in the `c1` art family),
with every CRC resolved against the 2,112-entry property index:

| crc | property | type | corpus n | maps |
|---|---|---|---|---|
| 646376885 | `c1-038-wall-lin2` | Building | 106 | 4 |
| 239800711 | `c1-038-wall-lin` | Building | 46 | 4 |
| 1977136400 | `c1-038-wall-corner` | Building | 48 | 4 |
| 3268994556 | `c1-038-wall-door` | Building | 21 | 5 |
| 452233971 | `c1-landmark-01-bellhouse` | Building | 3 | 3 |
| 75301998 | `c1-010-bank` | Building | 3 | 3 |
| 2664510881 | `B_general_obj_18` | Building | 40 | 13 |
| 2435647381 | `general_obj_charcoa` | Building | 97 | 20 |
| 2753626294 | `fire_general_obj_charcoal.mse` | Effect | 259 | 8 |
| 753920647 | `general_obj_brazier_01` | Building | 40 | 8 |
| 569394331 | `Pagoda1` | Tree | 746 | 51 |

Counts in the example: 20 × `wall-lin2`, 6 × `wall-lin`, 5 × `wall-corner`,
1 × `wall-door`, 1 × `bellhouse`, 1 × `bank`, 2 × `charcoal` + 2 × its fire
effect, 2 × `brazier`, 1 × `B_general_obj_18`, 1 × `Pagoda1`.

Three things to read off that list rather than from the geometry:

1. **Five corners for a four-corner rectangle.** The compound is not a plain
   box; it has an internal division or a re-entrant corner. Expect L-shapes.
2. **`general_obj_charcoa` and `fire_general_obj_charcoal.mse` come in pairs.**
   The building is the brazier body, the effect is its flame, and they are
   placed as a unit at the same spot. `cooccurrence.json` carries the pairing.
   The effect is placed 259 times against the building's 97, so the flame is
   reused on other bodies too — pair it, do not assume exclusivity.
3. **`Pagoda1` is typed `Tree`.** It is a `.prt` property in `a/나무` (the tree
   folder) and the engine treats it as vegetation. `objects.json`'s
   `identity_traps` covers this class of mismatch; do not filter a compound's
   parts by `property_type`.

---

## 4. What is still unknown

- **Compound footprint.** No bbox is mined for these CRCs (`bbox: null` on all
  eleven), so wall thickness and gate width are unmeasured. The 10 m module is
  the only hard dimension available.
- **Where the gate faces.** The `door` piece almost certainly opens onto the
  road web, but that has not been measured against `roads.json` corridors.
- **Attr under a compound.** Whether the wall run is blocked by object
  footprint or by a painted band is not established for this family.
- **Interior layout.** Which buildings sit where relative to the gate.

Answer these before writing an assembler; each one is a corpus query, not a
design decision.

---

## 5. Bridges -- the terrain is built for the bridge

Measured on the seven bridges of `metin2_map_a1`, which the map's author pointed
out one by one. Rule 23 applies without modification: the model is fixed, so the
ground is what gets fitted.

### 5.1 Two kinds, anchored differently

| model | key | size | deck runs along | origin | material |
|---|---|---|---|---|---|
| `general_obj_suspension bridge01` | `suspension01` | 71.8 x 10.5 m | model **Y** | **one end**, on the lip of a bank | wood and rope |
| `general_obj_suspension bridge02` | `suspension02` | 47.6 x 10.4 m | model **Y** | one end | wood and rope |
| `a1-024-10m-bridge` | `a1_stone` | 28.9 x 8.2 m | model **X** | **mid-span**, in the channel | stone arch |
| `b1-022-10m-bridge` | `b1_stone` | 39.5 x 13.7 m | model **X** | mid-span | stone, flat deck |

Roll is counter-clockwise with north up, so in y-down tile space the span runs
along `(cos r, -sin r)` for a stone bridge and along `(-sin r, -cos r)` **from
the origin** for a rope one: roll 270 reaches east, 0 north, 180 south. A stone
bridge carrying a north-south road has roll 90.

### 5.2 What every one of the seven has

| | stone (n = 3) | rope (n = 4) |
|---|---|---|
| **the two banks stand at ONE height** | 2, 2 and 7 cm apart | 10, 36, 56 and 82 cm |
| approach behind each end | flat within 0-40 cm for 20 m (one slopes 1.7 m) | flat or rising away |
| where the bank reaches full height | ~2 m inside the bridge end | 4 m inside end A, 8-11 m inside end B |
| channel, lip to lip | = the bridge length less ~4 m | 57-59 m under the 72 m, 36 m under the 48 m |
| walls | bank to water in ~4 m | **68-78 deg** |
| **water below the bank** | **210 / 237 / 488 cm** | **1,033 / 1,706 / 1,751 / 4,027 cm** |
| bed below the bank | 658 / 895 / 978 cm | 1,554 - 4,346 cm |
| `z + height_bias` below the bank | **948 / 951** (`a1-024`), **1,706** (`b1-022`) | **0 - 15** |
| stored `height_bias` | 0, -290, -930 | -15, 0, -5, -5 |
| road texture at both ends | slot 1 (the road) on all three | grass, rock or road |
| `attr` under the deck | **0 % block, 0 % water** | **0 % block, 0 % water** |
| `attr` 15 m up- or downstream | 100 % blocked, 65-87 % water-flagged | 91-100 % blocked |

Three things to take from that table.

**The bias is an output.** The two `a1-024` placements store 0 and -290 and land
on the same datum to 3 cm, because one origin sits on a bed 290 cm higher than
the other. What is constant is `bank - (z + bias)`. Compute the bias from the
bank; never copy one.

**The river is the constant, the banks are the variable.** Four of the seven
stand over the same water, 15,305 cm -- one level for the whole river. The stone
bridge there has its banks 4.9 m above it; the rope bridges 17 m and 40 m. So
the kind of bridge is chosen by **how high the banks stand over the water**:
2-5 m takes stone, 10 m and up takes rope. A rope bridge over a 3 m bank is a
hammock over a ditch.

**The deck is the only strip across.** Under all seven, `attr` carries neither
block nor water, while the river beside it is blocked end to end. Note this is
not the `0xCA` "bridge, walkable over water" byte of a ford (`attributes.md`):
under a bridge the water flag is cleared too.

### 5.3 In a mapspec

```yaml
water:
  - waypoints: [[0, 128], [128, 128], [255, 128]]
    width_m: 20
    surface_z: 15700          # a STATED level makes the river a moat -- see below
roads:
  - waypoints: [[60, 0], [60, 128], [60, 255]]     # through the bridge centre, along the span
    width_m: 5
    tile_index: 1
bridges:
  - {model: a1_stone, centre: [60, 128], roll_deg: 90}
```

`gen/spec.py` `BRIDGE_MODELS` holds the table above. The terrain stage, last of
all: sets both banks to `surface_z + water_below_bank` (or `bank_cm` if given, or
the ground at the two ends if the water has no stated level), levels the
approaches, and cuts the channel under the span to `bank - bed_below_bank` with
the cut running 40 m along the river before it fades. The model is hung at
`bank - datum_below_bank` whatever the ground under its origin is, and the attr
stage clears the deck. The build log prints one line per bridge and marks it `!`
if the water is outside 0.6-3x the model's measured clearance, or missing.

**Give the river a `surface_z`.** An auto-levelled river is banded to follow the
ground it crosses, which is right for a stream and wrong under a bridge: the
bands sit at different heights, the levelled banks cut across them, and the
planes hang in the air over the grass (`failure-atlas.md` sec 5). With a stated
surface the bed is cut to an ABSOLUTE level -- a moat, one continuous plane, 0 %
exposed edge -- and the waterline falls exactly on the channel edge.

For a rope bridge the surrounding land has to be high already. `bank_cm` will
raise two mesas out of a plain if asked, and they will look like it.

---

## 6. Shore props hang from the water

The a1 fishing bays -- three rafts, a fish hut and a 32 m pier along 112 m of
beach -- are the same lesson from the other side:

| prop | deck vs WATER | ground under its origin vs water | stored bias |
|---|---|---|---|
| raft `B_general_obj_01_2` (x3) | **-32 / +30 / +50 cm** | -105 ... -140 (standing in the shallows) | +110 / +135 / +155 |
| hut `B_general_obj_01_1` | +120 | +60, on dry sand 5 m back | +60 |
| pier `B_general_obj_01` | +300 | +80 at the root, -150 at the far end | +220 |

The biases are whatever put the deck at the surface on that beach. Saved as a
pattern with `water_cm` (`reference/setpieces/a1_fishing_bays.json`) and stamped
with the target's surface, each piece keeps its clearance over the water and no
levelling pad is added -- a pad would flatten the shore it stands on. See
`reference/setpieces/README.md`.

The shore has to be where the pattern expects it, and on a generated LAKE it is
not: the bowl is graded over ~0.35 x its width, so the waterline lands 14-40 m
inside the polygon. Put shore props on a river with a stated `surface_z`, whose
waterline is its channel edge; a1's bank reaches 1.2 m of water within ~5 m.

---

## 7. Mesas over one sea -- `map_a2`, and `islands:`

`map_a2` is not a valley with rivers. It is about twenty flat-topped islands cut
out of one plateau by canyons of near-constant width, flooded by ONE water plane
(9,940 cm, the only layer on the map), and joined by 21 `suspension bridge01` and
one `bridge02`. Measured along every one of the 21 spans:

| | |
|---|---|
| the two tops a bridge joins | the **same height** to the metre (63 -> 63, 67 -> 67 m over the water) |
| lip to lip | **54-60 m** -- the 72 m model less 6 m of deck on each bank |
| the wall | lip to below the water in **12-18 m** of run; 30-60 m of it in the first 6 |
| the bed | flat, **9 or 15 m** under the surface |
| tops over the water | **53-95 m**, median 66 (walkable ground p5 15,313 / p50 16,734 / p95 18,568) |
| the plane | 25.4% of the map's cells, 16.3% actually submerged |
| paint | `stone01`/`stone02` down the walls AND over the bed: 99.9% of submerged tiles |
| the rim | one more mesa, higher, that no bridge reaches; 66% of the map is blocked |
| the lip | **not flat to the edge**: 14-34 m inside it the ground stands +2.5 m (median), +8 m (p75), +16 m (p90) over the walkable level and is 50-65% blocked, open again by 50 m -- a broken berm of rock humps, absent at bridge heads |

That is a Voronoi diagram with its edges widened, and `islands:` states it that
way -- one site per island:

```yaml
islands:
  sites: [[768, 768], [768, 468], ...]   # tile metres
  gap_m: 60            # the bridge, not a taste: what suspension01 spans
  wall_m: 15
  surface_cm: 10000
  bed_cm: 8800
  rim_m: 100           # the rim mesa's canyon, in from the map edge
height_range_cm: [16200, 19500]          # the TOPS; must clear surface_cm
roads:                                   # site to site, through the bridge, along its span
  - waypoints: [[768, 800], [768, 668], [768, 568], [768, 468]]
    tile_index: 2
bridges:
  - {model: suspension01, centre: [768, 618], roll_deg: 0}
```

What the generator does with it, and why each step is where it is:

- **The canyons are cut AFTER the roads and pads** (`gen/islands.py`,
  `terrain.build`): `bed + (h - bed) * t`, with `t` the wall profile. A road
  drawn from one island to the next is then level ground on both and nothing
  between. Cut first, the corridor smoothing -- which diffuses along the road --
  builds a causeway across the canyon.
- **A bridge goes at the midpoint of two sites, along the line between them**,
  roll snapped to 15: the canyon is their bisector, so that line is its normal.
  For a rope bridge `roll = atan2(-dx, -dy)`. The bridge fit then closes what
  the snap left open -- it fills each bank out to the lip and cuts the gorge to
  the canyon bed, not to the model's 20 m.
- **The banks come from the ground**, because the sea is not a `water:` entry:
  the median of the two approaches, both set to it. Keep the tops' relief low
  (`flat_fraction` 0.6, `slope_p95` ~24) or the two ends start metres apart.
- **One plane, written last, run 5 cells into the walls** (rule 22). It is not
  part of `wet`: that is the authored basins, which desert flora keeps 50-300 m
  from, and an island is nowhere that far from the sea.
- **Everything that is not a top is void**: blocked whatever a road does, and
  rock -- including under water, which is the one place a bed is painted stone
  (`taste.md` 1.10 keeps a LAKE bed sand). The road still joins the islands for
  reachability, so the far top is not sealed as a stranded shelf; its paint and
  its open attr stop at the lip, and the deck is the only strip across.
- Corners round off into pools where three canyons meet (`round_m`, a soft
  minimum over the bisectors) and the coast wanders `wobble_m` off the line.
- **The canyons bend** (`warp_m`, 40): the sample point is displaced by a smooth
  field before the diagram is read, faded to nothing within 45 m of every bridge
  centre -- so each span still crosses its canyon square and at the midpoint --
  and toward the map edge, so the rim mesa keeps its width. Without it the map
  is a ruled diagram in a square frame; the rim canyon also turns its corners on
  a radius (`rim_corner_m`).
- **The berm** (`berm_cm` 1,600, `berm_m` 32) goes on after roads and pads and
  is pressed flat within 12 m of anything levelled, so bridge heads, gates and
  camps stay open. Rendered beside `map_a2` from one camera, the bare-lipped
  version read as a table top; with it the block share went 59% -> 68% (a2: 66%).

`D:/map_ad3` is the worked example (hub + 6 + 12 sites, 27 `suspension01`); its
`_make_spec.py` computes sites, bridge rolls and road waypoints together.

An island no road reaches is sealed and painted rock, top included -- correct
for the rim, a mistake anywhere else. Link every site.

---

## Sources

`catalog/stats-objects.json.by_crc` (roll histograms, `nn_same_crc_cm`),
`catalog/objects.json` (property resolution), `catalog/cooccurrence.json`
(building/effect pairing), `taste.md` §1.1–1.2 (rotation channels and snap).

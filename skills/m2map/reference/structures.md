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
which is part of what is being copied. `gen/setpiece.py` keeps them, and does
not rotate.

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

## Sources

`catalog/stats-objects.json.by_crc` (roll histograms, `nn_same_crc_cm`),
`catalog/objects.json` (property resolution), `catalog/cooccurrence.json`
(building/effect pairing), `taste.md` §1.1–1.2 (rotation channels and snap).

# generate — a new map from a description

Free text in, a complete map on disk. The middle step is what makes this
trustworthy: you resolve the request into an explicit **mapspec**, show it, and
build only after the user has had a chance to argue with it.

## Flow

```
free text  ->  archetype  ->  mapspec.yaml  ->  [user approves]  ->  build
                                                                 ->  preview
                                                                 ->  LOOK
                                                                 ->  audit
                                                                 ->  emit
```

## 1. Pick the archetype

Load `reference/archetypes/README.md` and walk its two-step tree. Pick exactly
one. If the request straddles two ("snowy forest with a desert edge"), pick the
dominant one and note the deviation in the spec's `notes` — do not average two
archetypes together, which produces terrain belonging to neither.

Then decide `style`:

- **`sculpted`** — outdoor terrain, the default.
- **`box`** — flat interior. `dungeon_block` and `dungeon_themed`, 44 of 142
  corpus maps. Terrain is a constant plane, the palette is one or two slots, and
  the layout is kit assembly rather than density scatter. Do not try to sculpt
  one.

## 2. Fill the spec

Read the archetype doc and copy its tables into `MapSpec` — that is what they
are for. Then adjust for what the user actually asked.

Decisions the user's words usually leave open, with the defaults to use:

| Field | Default |
|---|---|
| `size` | 2x2 unless they said how big. State the metres: one sector is 256 m. |
| `seed` | Any fixed integer. Record it — it is what makes the map reproducible. |
| `base_position` | A multiple of 25,600. Ask if it must not collide with an existing map. |
| `height_range_cm`, `slope_p50/p95`, `flat_fraction` | The archetype's measured values. Do not invent. |
| `attr_style` | `slope_driven` for outdoor, `painted_box` for interiors. |
| `border_band_m` | 4 |

### The features beyond scatter

Four spec surfaces exist for things a density and a polygon cannot say. Each was
added because a map needed it and the alternative did not work.

| Want | Use | Key numbers |
|---|---|---|
| A paved safe-zone disc | `PlazaSpec` | radius **8–25 m**, painted **unmixed**, 100% `ATTR_SAFEZONE`, block cleared. `taste.md` §1.9 |
| A near-vertical rock face | `ScarpSpec` | a heightfield's steepest is one 200 cm cell of run per drop; 1,800 cm over 3 m is **81°**. `taste.md` §1.14 |
| A face of a CHOSEN height | `ScarpSpec.crest_cm` | fits terrain to a prop instead of hunting a `height_bias`. `taste.md` §1.13 |
| A landmark at an exact spot | `ObjectTier.positions` | `(x, y)` or `(x, y, roll)`; skips every candidate filter. A waterfall cannot be expressed as "steep and near water" — that cannot say *which* water |
| A fence run or any curving line | `positions` with `(x, y, roll)` | corpus fences: **62 %** in runs of 3+, gap p50 **361 cm**, turn p50 **18°**, rolled tangent — but the six models are different lengths, so do not generate one; copy it. `placement.md` §6.w |
| A camp, yard or any shipped compound | **`setpieces:`** in the mapspec — a pattern from `reference/setpieces/`, an `anchor`, a `rotate_deg` | every record within a radius, offsets / rolls / biases verbatim, about the block's **centroid**; turned as one block by multiples of 15 with the measured sign (roll CCW north-up, so y-down offsets turn clockwise); a levelling pad is added on the anchor (extent + 4 m) unless `pad_radius_m: 0`. `reference/setpieces/README.md` |
| A field encampment | **`setpieces: c1_camp_north`** / `_southwest` / `_east`; declare `b/field/field 01` and `field 04` so its own ground is painted | pick the facing nearest the road, then `rotate_deg = (facing − wanted) mod 360`. `reference/setpieces/README.md` |
| A town square | **`setpieces: b1_town_square`** + a `PlazaSpec` on the same anchor; declare `field 01`, `field 04`, `tile01` | records and the dirt apron come from the pattern; safezone disc, spokes and pad are the spec's. `reference/setpieces/README.md` |
| A beach | a `shore` slot, `weight` = share **of the 6 m band at the waterline** | measured from the submerged cells, not the authored polygon -- the surface sits inside its bowl |
| A prop facing out of a slope | `ObjectTier.align_to_slope` | roll = fall line **+ 90°**; the plane lies along the heading |
| An authored compound aimed deliberately | `ObjectTier.roll_deg` | one heading for every piece. Left to the sampler a warp gate's three parts drew 345, 285 and 105 |
| A prop that needs a face | `ObjectTier.min_slope` | `fall_7` is p50 **71.4°**; with `max_slope` alone it lands on the flat |

A set-piece in the spec is three lines:

```yaml
setpieces:
  - pattern: desert_camp        # reference/setpieces/desert_camp.json
    anchor: [88, 108]           # tile metres; the pattern's centroid lands here
    rotate_deg: 90              # optional, multiples of 15
```

`pipeline.run` expands it into authored `ObjectTier`s and a
`PlazaSpec(tile_index=0, safezone=False)` pad before validating, so the stamped
positions and the pad are checked against the map like anything else. Do not
hand-author a camp from the archetype's densities — `03-desert.md` explains
why, three times over.

**Fit the terrain to the prop, not the prop to the terrain.** A prop's geometry
is fixed; the ground is not. When a fixed-size effect has to meet a landform,
derive the landform's dimension from the effect and build to it. Two passes
where a water level is involved, since the level is an output: build, read it,
set the crest, build again. `taste.md` §1.13.

**Authored positions belong to a seed.** `positions` skips every candidate
filter, `max_slope` included, so a coordinate carried to another seed lands on
whatever ground is there now. The warp gate site that measured 1.8° on
`map_skill_test_04` measured **8–15°** with a 54° cell beside it on `_05`, same
spec, new seed — against a corpus p95 of 2.9°. After the first build, read the
slope under each authored landmark from the written `height.raw` and move it to
the flattest on-road patch if it fails. Absolute heights (`crest_cm`,
`surface_z`) need the same re-read.

**A big pad eats the terrain targets.** `flat_fraction` and the slope percentiles
are fitted over the whole interior, pad included. With a 70 m pad on a 1x1 the
fit took the pad as "the flat part" and made everything else steep: 79% of the
ground outside the town came out rock, block 62%, and every scattered tree
landed inside the square because that was the only grass. Ask for a flatter map
than the archetype table says (`slope_p50` 3, `slope_p95` 22, `flat_fraction`
0.70 gave block 40% and a green ring round the town).

**Roads before everything.** Lay the corridor waypoints first; terrain flattens
under them, texture paints them, objects clear them. A road added afterwards
sits on terrain that ignores it.

**Object densities are per 100 m².** A 2x2 map is ~262,000 m², so a density of
0.35 is roughly 900 props. Sanity-check the count before building, not after.

## 3. Show the spec, then stop

Present it as YAML with a short plain-language summary — size in metres,
what the roads do, roughly how many objects, what the collision policy is.

**Wait for approval.** The spec exists so taste decisions are arguable before a
byte is written; building immediately throws that away.

## 4. Build

```
python scripts/build_map.py spec.yaml --out <dir> --preview --audit
```

Watch the stage log. Every line is a measurement you can check against the
archetype doc:

```
terrain: slope p50 2.8 / p95 23.9 deg, flat 39%
texture: 6 slots used, run-length median 2.0, base share 0.54
objects: 765 placed, 2 distinct CRCs, roll-snap 100%
attr:    block 12%, water 1%, safezone 5%
```

A `!` line means a tier could not place what it was asked to — usually
`max_slope` or `road_clearance_cm` leaving nowhere to stand. Fix the spec; do
not ignore it, because the map will simply be emptier than intended.

### Read the build log before the previews

Three lines report a measurement against the corpus rather than a fact about the
run. Each was added after a fault that looked fine in every other check:

| Line | Corpus | If it is off |
|---|---|---|
| `road: ... ratio` | median **0.21**, worst confirmed road 0.56 | above ~0.5 means the route crosses steep ground. **Move the waypoints** — the generator levels the line it is given but does not choose one |
| `shoreline: ...% exposed` | **0.3–2.5%** | the water plane's own 2 m cell edge is what the player sees; the shore will step. Widen `PLANE_OVERRUN`, do not clip the plane |
| `texture: run-length, base share` | run **2**, base share **0.52** | run 1 is white noise, 4+ is region fill; a 1-mid palette legitimately reads high |

## 5. Look at the previews

Non-negotiable. See SKILL.md "Verification". The specific failures worth
looking for, all of which have happened:

- **tile.png** uniform pepper on one colour → the mixture is not varying; check
  the slot `weight`s sum sensibly and that more than one has real coverage.
- **objects.png** a regular lattice → spacing is doing the layout instead of the
  clustering; reduce density or increase spread.
- **objects.png** props in the river or on the road → a filter is missing.
- **attr.png** blocked ground that does not match the steep ground in
  **slope.png** → the threshold or the footprints are wrong.
- **height.png** uniformly rolling with no flats → `flat_fraction` did not take.
- **water.png** a rectangular outline → the plane stops at its basin; the shore
  will render as a staircase.
- **tile.png** ground texture on the high ground behind a cliff → that ground is
  unreachable and should be rock. `gen/walkable.py` should have sealed it.

## 6. Audit and emit

`audit_map.py` must report **zero blockers**. Then hand over: the map path, what
was written, the seed, the spec path, and a one-line note of anything you
assumed. Say which archetype you used and why.

## Refusals worth making

- **The user names a prop you cannot find in the catalog.** Say so and offer the
  nearest family match. Never invent a CRC (rule 2).
- **The request needs a texture that is not in `terrainmaps/`.** Same.
- **"Make it look exactly like <screenshot>"** — take style cues, say which, and
  be explicit that models are chosen by family, not matched from pixels.

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

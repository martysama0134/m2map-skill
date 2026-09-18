# Set-piece patterns

A set-piece is a shipped compound copied **whole** — every `areadata` record
within a radius of a point on a corpus map, as offsets from the block's own
centroid, each with the roll and `height_bias` it was shipped with. It is kept
here as JSON and stamped onto a new map by `gen/setpiece.py`, translated to an
anchor and, if it must face another way, turned as **one block about that
centroid**.

It exists because assembling a compound from statistics does not work. Three
generated versions of the desert camp — posts on a ring with a roll per record,
an arc at the corpus median pitch, a "run" chained from the nearest unvisited
fence — each read as debris while every spacing figure passed. The one that
matched the source render did no generating at all (`placement.md` §6.w,
`failure-atlas.md` §3.10).

## The patterns

| file | source | records | pivot | extent about pivot (m) | relief | headings |
|---|---|---|---|---|---|---|
| `desert_camp.json` | `metin2_map_n_desert_01`, 32 m around (333, 307) | 32 | centroid, at (326.91, 319.33) on the source | x −22.4 … +23.9 · y −22.8 … +18.8 | 58 cm (31 of 32 on one plane) | 105 ×12 · 315 ×6 · 285 ×5 · others ×9 |
| `b1_town_square.json` | `metin2_map_b1`, 60 m around (638, 638), `b1-038-wall*` excluded | 80 | **centre** -- the safezone disc's centre | x −58.9 … +51.9 · y −56.6 … +56.8 | 258 cm | 0 ×15 · 30 ×10 · 180 ×8 · others |

`desert_camp`: two fence rails of 5 and 6 panels (fence01…05 mixed, steps
232–521 cm) flanking three tents, a brazier with its stall clutter, banana
trees, ferns and aloes. Verified in WorldEditor from the same camera as the
source, unturned and turned 90°: rails connected both ways.

`b1_town_square`: the 44 m `tile01` safezone disc of Empire B's capital, ringed
by lamps and stone lanterns, the twin-hall hotel on the north spoke (the road
runs through its gate), two guesthouses and a workhouse east, market stalls
north-east and south-east, a jar-and-crate yard west. Verified in WorldEditor
against the source from the same camera (`map_skill_test_06`).

A pattern is **records only**. What makes this one read as a town is also paint
and attr, and the spec has to bring them:

```yaml
plazas:
  - {centre: [112, 150], radius_m: 22, tile_index: 7, safezone: true}   # tile01, on the anchor
setpieces:
  - {pattern: b1_town_square, anchor: [112, 150], pad_radius_m: 70}     # hotel is 36 x 20 m on the rim
regions:
  - {kind: settlement, polygon: [...66 m octagon on the anchor...], flatten: true}
textures:
  - {path: '.../b/field/field 04.dds', role: accent, region: settlement, weight: 0.7}   # the dirt apron
roads:     # spokes through the anchor; N runs through the hotel gate at dx +2, dy -57
```

`role: accent` with a `region` is the patchy, coherent overlay (`mid` scores by
slope and lands on the pad's rim; `interior` is for box maps). Scatter keeps off
every plaza and pad by itself, and authored buildings stamp their own rectangle
into `attr.atr` with the road core kept open.

## Using one

In a mapspec (`build_map.py spec.yaml`):

```yaml
setpieces:
  - pattern: desert_camp        # a name here, a file name, or a path to a .json
    anchor: [82, 120]           # tile metres, y-down; the centroid lands here
    rotate_deg: 90              # optional; multiples of 15
    # pad_radius_m: 34          # optional; default = extent + 4 m, 0 = no pad
    # label: camp
```

`pipeline.run` expands each entry into authored `ObjectTier`s and a levelling
pad before validation (`gen/setpiece.py` `expand`). The same from Python:

```python
from m2map.gen import setpiece
from m2map.gen.spec import PlazaSpec

camp = setpiece.load(REF / "setpieces" / "desert_camp.json")
anchor = (82.0, 120.0)                       # tile metres; the centroid lands here
objects += camp.rotated(90.0).stamp(anchor, label="camp")
plazas.append(PlazaSpec(centre=anchor, radius_m=34.0, tile_index=0, safezone=False))
```

- **The pad is not a plaza.** A `PlazaSpec(tile_index=0, safezone=False)` is
  exempt from the 4-40 m disc band; give `pad_radius_m` the extent plus the
  largest footprint on the rim (70 m for `b1_town_square`).
- **The pad.** `relief_cm` says how flat the source was (58 cm here — one
  plane). Level a `PlazaSpec(tile_index=0, safezone=False)` under the anchor,
  radius past `extent_m`, **centred on the anchor** so a turned block stays on
  it.
- **Turning.** `rotated(θ)` adds θ to every roll and turns the offsets about
  the centroid with the measured sign (below). Keep θ a multiple of 15: every
  corpus heading sits on that ladder (`taste.md` §1.2) and the copied rolls
  should stay on it.
- **Never rotate part of it.** The rail is placed against the tent; on its own
  it is a curve around nothing.

## Which way roll turns

The tile offsets are y-down and `roll` is a compass heading; turn them the same
way and the panels of a copied rail come apart while every spacing statistic
still passes. The sign is measured on **1,681** corpus fences whose nearest
neighbour is within 6 m: `roll + atan2(Δy_tile, Δx_tile)` is constant
(concentration 0.84, mean 179° mod 180) and `roll − bearing` is noise (0.08).
So roll increases **counter-clockwise with north up**, and a turn of θ is

```
roll' = roll + θ
dx'   =  dx·cos θ + dy·sin θ        (y-down tile metres: clockwise)
dy'   = −dx·sin θ + dy·cos θ
```

`setpiece.alignment(pieces, only=fence_crcs)` reports the `roll + bearing`
concentration of the linked pieces so a turned pattern can be checked against
its source without a render — except at exactly 90° and 180°, where a
wrong-signed turn shifts it by a full 180 and a fence, having no front, hides
it. The render is the last word.

## Making one

```
python -m m2map.gen.setpiece <CORPUS>/metin2_map_n_desert_01 333 307 32 \
    --name desert_camp --notes "..." --save reference/setpieces/desert_camp.json
```

`--exclude NAME|CRC` (repeatable) drops records before the centroid is taken. A
disc cannot always take one compound and nothing of the next: at 60 m the b1
square clips four corners and the gate of the walled estate beside it, and half
a wall is worse than none.

prints the table as a Python literal (about the centroid, with names from the
catalog), the extent, relief, heading histogram and fence alignment, and saves
the JSON. `--pivot centre` keeps the offsets about the point asked for instead;
`--rotate θ` turns before printing.

Before saving, **render the source at the same target and camera** and look at
it: the 20-panel "run" that was a blob of three rails passed every number and
failed in one frame. The radius should take the whole compound and nothing of
the next one — trees included, since Ymir turned the planting with the tents
(105 / 285 / 315 across all 32 records of the camp).

## Format `m2map-setpiece/1`

```json
{
  "format": "m2map-setpiece/1",
  "name": "desert_camp",
  "source_map": "metin2_map_n_desert_01",
  "source_point_m": [333.0, 307.0],
  "radius_m": 32.0,
  "pivot": "centroid",
  "pivot_m": [326.906, 319.3281],
  "rotation_deg": 0.0,
  "notes": "...",
  "count": 32,
  "extent_m": [-22.35, 23.93, -22.83, 18.8],
  "relief_cm": 58.0,
  "headings": {"105": 12, "315": 6, "285": 5},
  "pieces": [
    {"dx": 4.8, "dy": -1.05, "roll": 285.0, "bias": -5.0, "crc": 1099929426,
     "z": 17826.5, "name": "tent01"}
  ]
}
```

`dx`/`dy` are metres east/south of the pivot; `roll` degrees; `bias` cm added
to the ground height; `z` the source ground height in cm (for `relief_cm`
only); `name` is for reading, the CRC is what is placed. Nothing in a pattern
is a host path — the source is named by map, not by directory.

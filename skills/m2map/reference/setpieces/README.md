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

`desert_camp`: two fence rails of 5 and 6 panels (fence01…05 mixed, steps
232–521 cm) flanking three tents, a brazier with its stall clutter, banana
trees, ferns and aloes. Verified in WorldEditor from the same camera as the
source, unturned and turned 90°: rails connected both ways.

## Using one

```python
from m2map.gen import setpiece
from m2map.gen.spec import PlazaSpec

camp = setpiece.load(REF / "setpieces" / "desert_camp.json")
anchor = (82.0, 120.0)                       # tile metres; the centroid lands here
objects += camp.rotated(90.0).stamp(anchor, label="camp")
plazas.append(PlazaSpec(centre=anchor, radius_m=34.0, tile_index=0, safezone=False))
```

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

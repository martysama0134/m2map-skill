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
| `c1_camp_north.json` | `metin2_map_c1`, author's selection about (452, 933) | 49 | centroid | x −19.4 … +25.6 · y −27.8 … +17.1 | 0 cm | opens **north** (0) |
| `c1_camp_southwest.json` | `metin2_map_c1`, author's selection about (194, 570) | 73 | centroid | x −20.8 … +12.8 · y −17.7 … +22.7 | 0 cm | opens **south-west** (225) |
| `c1_camp_east.json` | `metin2_map_c1`, author's selection about (618, 300) | 68 | centroid | x −17.0 … +17.7 · y −26.3 … +29.0 | 101 cm | opens **east** (90) |
| `desert_camp_west.json` | `metin2_map_n_desert_01`, author's selection about (1435, 721) | 78 | centroid | x -21.0 … +25.7 · y -23.1 … +26.4 | 5 cm | opens **west** (270) |
| `desert_camp_south.json` | same map, about (891, 146) | 80 | centroid | x -27.7 … +22.8 · y -25.7 … +20.1 | 15 cm | opens **south** (180) |
| `desert_camp_northwest.json` | same map, about (435, 709) | 83 | centroid | x -38.2 … +16.5 · y -28.9 … +18.9 | 27 cm | opens **north-west** (315) |
| `desert_camp_northeast.json` | same map, about (158, 981) | 135 | centroid | x -37.5 … +41.6 · y -40.8 … +36.9 | 191 cm | opens **north-east** (45) |
| `desert_camp_west2.json` | same map, about (429, 1207) | 157 | centroid | x -42.1 … +43.2 · y -50.0 … +33.4 | 70 cm | opens **west** (270) |

`desert_camp`: two fence rails of 5 and 6 panels (fence01…05 mixed, steps
232–521 cm) flanking three tents, a brazier with its stall clutter, banana
trees, ferns and aloes. Verified in WorldEditor from the same camera as the
source, unturned and turned 90°: rails connected both ways.

`b1_town_square`: the 44 m `tile01` safezone disc of Empire B's capital, ringed
by lamps and stone lanterns, the twin-hall hotel on the north spoke (the road
runs through its gate), two guesthouses and a workhouse east, market stalls
north-east and south-east, a jar-and-crate yard west. Verified in WorldEditor
against the source from the same camera (`map_skill_test_06`).

`c1_camp_*`: three Empire C field encampments, each two large tents and a small
one with a carriage, a cart, stalls, racks, barrels and crates, and fence arcs on
the closed sides (fence `roll + bearing` concentration 0.88-0.97). They were
registered from `areadata.txt` text the map author copied out of the editor --
a hand selection, no trees -- and each matched the corpus record for record
(49/49, 73/73, 68 of the 71 in its bounding box: two stray panels and a Pagoda
are not camp). Stamped copies verified against the source from the same camera,
and `c1_camp_east` turned 90 verified to open north.

`desert_camp_*` (the five with a direction): desert encampments registered the
same way, each matching `metin2_map_n_desert_01` record for record
(78 / 80 / 83 / 135 / 157), flora included -- the palms and ferns are part of the
composition here, where the c1 selections left their trees out. Three sizes:
`west`, `south` and `northwest` are 45-55 m rings of huts or tents behind fence
arcs; `northeast` is a 79 m village of ten tents round a warp-gate dais with a
lion statue; `west2` is an 85 m ring of four hut groups with 57 fence panels.
Their ground is three different things, and each is saved with its pattern:

| pattern | floor |
|---|---|
| `west`, `south`, `northwest`, and the original `desert_camp` | a **solid `sand02` patch** -- 1,100-1,800 tiles, the dark damp-looking floor -- with `grass 01`/`grass 02` dithered under the palm clumps |
| `northeast` | grass under each tent group (4,025 tiles, two greens dithered), bare sand in the middle |
| `west2` | no floor at all: a web of `field 01` tracks meeting in the middle (2,101 tiles) |

Declare `sand02`, `grass 01`, `grass 02` and `field 01` (`weight: 0.0` for the
ones the map does not otherwise use). Verified against the source from the same
camera, and `desert_camp_west` turned 90 verified to open south
(`map_setpiece_check_desert`).

A camp **faces** somewhere: the side without fence, where the road arrives. The
facing is a compass bearing in the pattern's notes, and since roll turns
counter-clockwise with north up,

```
rotate_deg = (facing - wanted_bearing) mod 360        # multiples of 15
```

so `c1_camp_east` (90) opens north (0) at `rotate_deg: 90`, and south at 270.
Pick the variant whose facing is nearest and turn it the rest -- the three are
different layouts, not one camp turned. Each carries its own ground (below): a
solid `field 01` core, a `field 04` halo 4-8 m wide and a road spur on the open
side, so the spec is two lines and a palette that declares both textures:

```yaml
textures:
  - {path: 'd:/ymir work/terrainmaps/b/field/field 04.dds', role: accent, weight: 0.0}   # declared, not scattered
setpieces:
  - {pattern: c1_camp_north, anchor: [68, 66]}
```

## The ground under a pattern

Half of what makes a compound read is paint, and `areadata.txt` has none of it.
A pattern can carry the ground it stood on as a small grid about the pivot:

```json
"ground": {
  "origin_m": [-27.39, -35.4],
  "size": [63, 62],
  "palette": ["d:/ymir work/terrainmaps/b/field/field 04.dds",
              "d:/ymir work/terrainmaps/b/field/field 01.dds"],
  "rows": ["-----000011100--...", "..."]
}
```

- **Texture paths, not indices.** A `tile.raw` byte means nothing away from its
  textureset. Each digit indexes `palette`; `-` leaves the tile to the target.
- **Name the feature.** `--ground-keep field` keeps the dirt and drops the meadow.
  Copy the whole window and its square edge shows wherever the target's grass
  differs. (`b1_town_square` keeps `field` and `tile`: apron and paved disc.)
- **It turns with the block** -- same sign as the offsets, nearest tile.
- **Painted by path match.** The texture stage paints each tile whose texture the
  map's palette declares, after the generated field and before the map's own
  roads and plazas. A missing texture is skipped, never substituted, and the
  build log says `! ground: <label> ... no slot for <path>` -- add the slot
  (`weight: 0.0` keeps it out of the scatter). `ground: false` on the set-piece
  leaves the ground to the map.
- The expanded spec written beside the map holds the stamp as `ground_stamps:`,
  so the map still rebuilds from its own `mapspec.yaml`.

```
python -m m2map.gen.setpiece --from-areadata picked.txt --source-map metin2_map_c1 \
    --ground-from <CORPUS>/metin2_map_c1 --ground-keep field --name ... --save ...
```

Measured on the three camps: 2,021 / 2,051 / 2,288 tiles, `field 01` core to
`field 04` halo about 1 : 1. Under a disc of road dirt instead, the copy read as
a decal; with its own ground it cannot be told from the source frame.

A pattern's records and ground are still not the whole compound. For a town the
spec also brings the safezone disc, the pad and the roads:

```yaml
plazas:
  - {centre: [112, 150], radius_m: 22, tile_index: 7, safezone: true}   # tile01, on the anchor
setpieces:
  - {pattern: b1_town_square, anchor: [112, 150], pad_radius_m: 70}     # hotel is 36 x 20 m on the rim
textures:
  - {path: '.../b/field/field 04.dds', role: accent, weight: 0.0}       # for the shipped apron
roads:     # spokes through the anchor; N runs through the hotel gate at dx +2, dy -57
```

The dirt apron is the pattern's ground. (Without one, a region-confined
`role: accent` slot is the patchy, coherent overlay to use -- `mid` scores by
slope and lands on the pad's rim; `interior` is for box maps.) Scatter keeps off
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

**From a selection instead of a radius.** A group picked by hand in the editor is
its own definition -- paste the `areadata.txt` text into a file and

```
python -m m2map.gen.setpiece --from-areadata picked.txt --source-map metin2_map_c1     --name c1_camp_north --notes "..." --save reference/setpieces/c1_camp_north.json
```

takes every record in it, about their centroid (`source_point_m` repeats the
pivot and `radius_m` is only the reach of the farthest record). Check the paste
against the corpus first when the source is a shipped map: same count inside the
bounding box, same CRC multiset -- and look at whatever differs, because that is
what the author chose to leave out.

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

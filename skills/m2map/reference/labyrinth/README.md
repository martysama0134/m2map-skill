# Labyrinths — dungeon kits

A labyrinth is a block dungeon (`archetypes/12-dungeon_block.md`) assembled from
one family of DungeonBlock pieces. The corpus has six such families across
thirteen maps; each was mined into a **kit** in `kits.json` and the generator
(`scripts/m2map/gen/labyrinth.py`) builds new mazes out of one.

```yaml
style: box
attr_style: painted_box
archetype: dungeon_block
environment: metin2_map_whitedragoncave_01.msenv     # the kit's own, below
textures:
  - {path: "d:/ymir work/terrainmaps/dungeon/field 01.dds", role: void, u_scale: 5.0, v_scale: 5.0}
height_range_cm: [16383.5, 16384.0]
labyrinth:
  kit: whitedragon_01      # anglar | whitedragon_01 | whitedragon_02 | skipia | spider
                           # | mt_thunder | maze maze02 maze03 monkey monkey02 monkey03
                           # | orc_trench (no pieces: cut into the terrain, below)
  cells: [5, 5]            # maze cells, columns x rows (2..24)
  loops: 0.15              # share of the leftover walls reopened; 0 = one solution
  pitch_m: null            # null = aimed at the kit's corpus junction spacing
  rooms: true              # start + boss room at the two ends of the longest path
  entrance: S
  margin_m: 40
```

`size` grows to whatever the assembly needs (the log says so). The build log
prints the start and boss positions in metres and every warp pair, and ends
with `labyrinth check: ... start -> boss REACHABLE`, which is read off the attr
as written. A `NOT REACHABLE` line is a broken map.

## The families

Sheets in `sheets/`: `<kit>.png` is every piece from above (floor grey, measured
walk green, sockets red, origin yellow); `layout_<map>.png` is each source map
redrawn from the kit alone — the shapes this was learned from. Those layouts
are also kept verbatim in `kits.json` (`layouts`, records as
`[crc, x, y_terrain, roll, bias]`).

| kit | source maps | how it makes walls | pitch (corpus) | corridor | env |
|---|---|---|---|---|---|
| `anglar` | `anglar_dungeon_01` | path: corridors where the maze runs | 107.5 m | cave 30-32 m, stone 41 m | `anglar_dungeon_01.msenv` |
| `whitedragon_01` | `whitedragoncave_01` | path | 102.5 m | 32 m, rooms 10 m mouths | `metin2_map_whitedragoncave_01.msenv` |
| `whitedragon_02` | `whitedragoncave_02` | path | 60 m | 20 m | `metin2_map_whitedragoncave_02.msenv` |
| `skipia` | `skipia_dungeon_01`, `_02` | path, every junction a 77 m room | 100.6 m | 26 m | `skipia_dungeon.msenv` |
| `spider` | `spiderdungeon_02`, `_03` | **grid**: every arm of a 5x5 room grid built, the maze shut with fences | 99 m | 26 m | `skipia_dungeon.msenv` |
| `maze` … `monkey03` | `maze_dungeon1-3`, `monkeydungeon/_02/_03` | **warp**: letter-shaped islands joined by warp gates | 66.5 m | 18-19 m | `moonlight04` / `dark` / `monkeydungeon_02/_03` |
| `mt_thunder` | `mt_th_dungeon_01` | path: the concentric maze of short passages | 60 m | 22 m | `dark.msenv` |

The maze and monkey dungeons are **one geometry in six skins** — identical
bboxes, identical layouts, different CRCs. Their textureset is
`metin2_map_deviltower1.txt`; all of them paint slot 1 = `dungeon/field 01.dds`
over the whole map (archetype 12).

### Pieces by job

| kit | straight (run fillers) | corner | tee | cross | cap | room / island |
|---|---|---|---|---|---|---|
| anglar | `cavegate1` 30, `cave1` 30, `cave2` 39, `stonecave1` 73, `stonegate1` 36, `stonegate2` 73, **`cavegate2` 33 (cave 31 m ↔ stone 41 m adapter)** | `cave5` 60, `stonecave4` 56 | `cave4` 90x60, `stonecave3` 72x56 | `cave3` 90, `stonecave2` 72, `boss2` 114 (room) | `stonegate3` | `boss1` 102x173 (boss, one mouth) |
| whitedragon_01 | `Line_01/03/02` 30/60/90, **`door_02` 21, `door_01` 24 (room 10 m ↔ corridor 33 m)**, `room_06` 162 | `cross_01` 49, `room_05` 130 | `cross_02` 60x49, `room_04` 162x130 | `cross_03` 60 | `End_01`, `door_03_LM` | `room_02` 130x98 (boss); `room_01` 201x278 has four mouths on one side and is not used |
| whitedragon_02 | `Line_01/02/03` 60 | `L_01`, `L_02` 43 | `T_01` 60x44 | — | `End`, `door`, `door2` | `room` 89x84 island (boss, by warp) |
| skipia | `passi` 63.5, `passis1` 26, `passis2` 12.6 and seven short variants; **`passis4/5` are 1 m seam covers** laid over joints (`seam_rate`) | `passl` 77 | `passt` 76 | `passc` 76 | `passic` | `passp` 80 (boss, one mouth); `skipia_boss` has no measured walk and is not used |
| spider | — (arms meet tip to tip) | `01` 82 | `02` 100x110 | `03` 100 | `06` | `04` 82x64 (start); `boss03` island (boss, by warp) |
| maze | `cave01` 63.5 **only** | `cave02` 42x50 | `cave03` 63x50 | — | `cave04` 7x18 | `dungeon01` 85x69 (start), `dungeon02` 84x96 (boss), both islands |
| mt_thunder | `passage01/02` 12, `passage03` 25; `closinggate` 3.7 a seam (all 46 stand on walkable attr) | `conerroom` 34 | `three-way` 44x33 | — | `startroom`, `finishroom` | `centerroom` 66x88 has its mouths 36 m off one axis and is not used; the joint pillars ride the passages as dressing |

Every piece rides its kit's modal height bias (`anglar` +5, maze +20, skipia 0
or -178 on the seam covers) and turns by 90 degrees only (98.9-100 % in the
corpus).

## Trench labyrinths: no pieces at all (`orc_trench`)

`kit: orc_trench` cuts the maze into the terrain instead of laying pieces. It
was measured on `metin2_map_orclabyrinth` (x 515-770, y 768-1538 m; a user map,
not in the corpus) and checked against the letter floor of
`metin2_map_devilscatacomb` (around 18, 553 m) -- which is the maze/monkey
letter layout carved into terrain. `sheets/trench_orclabyrinth.png` and
`trench_devilscatacomb.png`: plateau red, wall brown, floor dark, walk green.

| | orclabyrinth | devilscatacomb letters |
|---|---|---|
| plateau | 16,384 cm flat, blocked 99.6 % | 21,482 cm rolling |
| trench depth | **29.5 m** | 36.6 m |
| floor width | p50 **16 m** (12-22) | 16.7 m |
| walkable width | p50 **12 m**: the floor less a 2 m rim | 12 m |
| wall | full height within **8 m** (~75 deg): 7.5 m at 1 m out, 17.9 at 3, 23.9 at 5, 29.5 at 8 | ~25 m run |
| ridge between trenches | p50 **24 m** (16-30) | -- |
| paint | floor `dc_field_01`, walls and plateau `dc_rock_01`, `dc_grass_00` patches | `dc_rock_00` |
| objects | 14 `warpgate01` on letter tips, bias 0 | `warpgate02/03`, ivy, pagodas, bone tunnels |

The generator: the same cell maze at a 40 m pitch (16 m floor + 24 m ridge),
cut into letters of 4-9 cells (`islands: false` for one connected maze), each
letter drawn on its own grid with rounded pads on its tips, the letters
shelf-packed 50 m apart inside a frame ridge (orc: +27-50 m), a gate pair per
letter along a spanning tree (more only at the `loops` rate), the entrance a
stub out of the first letter, the boss a 30 m round arena reached by gate. The
mapspec declares three texture roles -- `floor`, `wall`, `floor_patch` -- and
the terrain is left visible.

```yaml
style: box
attr_style: painted_box
archetype: dungeon_themed
environment: dark.msenv
textures:
  - {path: "d:/ymir work/terrainmaps/dungeon/devilcave/dc_field_01.dds", role: floor, u_scale: 3.0, v_scale: 3.0}
  - {path: "d:/ymir work/terrainmaps/dungeon/devilcave/dc_rock_01.dds", role: wall, u_scale: 3.0, v_scale: 3.0}
  - {path: "d:/ymir work/terrainmaps/dungeon/devilcave/dc_grass_00.dds", role: floor_patch, u_scale: 3.0, v_scale: 3.0}
labyrinth: {kit: orc_trench, cells: [8, 8], loops: 0.1}
```

## What was measured, and how

`scripts/m2map/mine/dungeon_kits.py` (`--sheets DIR` redraws the sheets).

- **Roll is counter-clockwise, north up** (rule 25): a record at
  `(x, y_stored)` puts local `(lx, ly)` at `(x + c lx - s ly, y + s lx + c ly)`.
  With that sign every walkable cell of every source map lies on a placed
  floor — P(floor | walkable) 0.97-1.00 over nine maps; the other sign drops
  `whitedragoncave_01` to 0.82.
- **Floor ≠ walk.** The floor is the lowest upward-facing mesh surface under
  4 m (absolute: `anglar_boss2` has a pit to -5 m). The walk is the shipped
  attr sampled in the piece frame over every placement, open in ≥ 25 % — the
  rim under the wall foot is 2 m on wdc_02/skipia/maze, 5 m+ on wdc_01/spider,
  and a quarter (not a half) keeps the spider arms, which are fenced in 55 % of
  placements.
- **Sockets** are where two placed floors touch in the corpus, clustered in the
  piece frame (never across opposite sides: a seam cover's two mouths are
  1.2 m apart), snapped axially to the bbox edge (pieces abut edge to edge —
  wdc joins measure 0 cm overlap p5-p95) and laterally to the axis of the floor
  at the edge (contact bands sit up to 1.7 m off it).
- **Socket families**, not widths, decide what joins: two sockets are one
  family when their pieces were joined there. A 7 m cap closes an 18 m maze
  corridor; a 10 m room mouth takes only a door. An adapter is a piece with a
  socket in each of two families.
- **Join band** per kit (`joins` p5/p95): a run may overlap by p95 + 2.5 m and
  fall short by -p5 + 1.5 m. A shortfall is painted walkable across (`seams`).
- **Dressing**: non-block records within 1.5 m of the same piece-frame spot in a
  third of the placements — anglar's torches (335 of 399), skipia's sparkle
  lattice and its invisible `skipia_collision` posts (6,739 of 6,778). A
  rider's roll is absolute when the world roll is constant (every effect) and
  relative otherwise.
- **Riders, not pieces**: a DungeonBlock with under 20 m2 of floor or a
  footprint under 30 m2 is laid on a piece, not joined to one --
  `Mt_Thunder_passagepillar` (132 at the joints) comes back as dressing. A rider
  shut in the corpus attr where its host is open is a quest door
  (`anglar_cavegate1_door`) and is never placed.
- **Barricade** (spider): a shut socket has its walk blocked 23 m in from the
  tip and 4-7 `ob-7-02-01/02` spiked fences across the mouth 16-19 m in. The
  template is copied verbatim in the socket frame.

## How a labyrinth is assembled

1. Perfect maze by randomised depth-first search, then `loops` of the leftover
   walls reopened, dead ends first, never past the kit's highest junction.
2. A node per cell that is not a straight run-through, chosen by corpus
   frequency among the pieces whose sockets turn onto the cell's open sides.
3. **The grid is not uniform.** Columns are placed west to east, each at the
   offset nearest the pitch where every horizontal run ending on it has a
   buildable length and no body runs into an unjoined neighbour; rows the
   same. A room pushes its column out.
4. Runs solved exactly over position (10 cm) and socket family, picked by
   corpus frequency, landing nearest the gap (a shortfall costs 3x an overlap).
   A cap slides along its run up to half a cell.
5. Start: middle of the `entrance` side. Boss: the border cell farthest along
   the maze. A one-mouth room hangs off the outside; an island room stands
   clear, reached through a warp gate at a capped dead end.
6. Kit floors stand **1 m over the terrain plane** and `TerrainVisible 0` is
   written — a floor on the plane z-fights it in black streaks, and the editor
   draws the terrain whatever the setting says.

**Warp mode** (maze/monkey): their one corridor length cannot close a grid
whose junction reaches differ by 7 m row to row, and the source maps do not try
— they are letters and 23-26 warp gates. The maze is grown into islands that
close (≤ 5 cells, dead ends always ride along), every edge between islands and
both room mouths become capped stubs with paired `warpgate01`, and the islands
are shelf-packed 40 m apart.

## Not generated

- **The server side of a warp**: the gates are client effects. The pairs are in
  the build log in map metres; a quest has to move the player.
- **Quest doors**: `anglar_cavegate1_door` (37 placements) and the attr lines
  the whitedragon doors close are dungeon logic, not maze walls.
- `WDC_01_room_01` (four mouths on one side) and `skipia_boss` (no walkable
  attr in any placement) are kept in the kit but never placed.

# readapt — turn a merged map into one place

A merge copies every sector verbatim. That is the right thing for a merge to do
— MapForge's is stable and should stay the tool for it — and it is not a
finished map. `readapt` is what comes after: the source maps are found again,
brought to one datum, welded, and joined by a road through the mountains between
them.

Measured on `map_merge_test_01`, three 2x2 guild maps stacked 2x6:

| What the merge leaves | Measured | What the player sees |
|---|---|---|
| Shared border vertices disagree — each sector kept its **own** copy of the edge | 1,712 – 4,047 cm mean per border, 6,720 max; corpus borders agree on 99.86% of vertices | Slits along the join with the sky behind them |
| Every source map brought its sealed mountain ring | 100% blocked for 68 – 86 m across each join | Two maps you cannot walk between |
| Every source map brought its own datum | floors 9.3 m and 5.8 m apart at the two joins | A road that would have to climb a wall |

The audit reports the first as `M2MAP-HGT-001`. Before that rule existed the
merged map audited **clean** — every file was valid; the fault is between files.

The second map it was run on, `map_merge_test_02` (`n_desert_01` beside
`n_flame_01`, 11x6), broke the first version three ways — each is marked **(02)**
below. The third, `map_merge_test_03` (`b1`, `c1`, `a1` merged with overlap, 7x9,
two blank filler blocks), ran to exit 0 and was wrong four ways -- **(03)**.
Expect the next map to find another: the procedure is the part to keep.

## Procedure

1. `python scripts/audit_map.py <map>` — `M2MAP-HGT-001` lines confirm it is a
   merge and name the torn borders. No such line: it is one map, use `improve`.
2. `python scripts/readapt_map.py <map> --out <map>_readapt`. Exit 1 means a
   `problems` entry or a floor that did not join — read the report, do not retry
   blind.
3. Read `_readapt.json` against what you know of the map: are `blocks` the
   source maps, and `void_blocks` the filler? Is each `level_cm` plausible?
   `grade_pct` ≤ 18? `joined` all true, `tear_after_cm` 0, `blank_tiles_added`
   0? `removed` objects few, `stray` near zero? **Is every `length_m` close to
   its `wall_m`?** `server_attr.agrees` true, `max_value` ≤ 7? A pass much longer than its wall is crossing open floor --
   the floors are wrong, not the route **(03)**.
4. Look at `_preview/readapt_route.png` — where the pass went, and what it
   crossed — then `readapt_tile.png` at the pass.
5. `python scripts/readapt_map.py <map> --out <map>_readapt --render-only` (or `--render` on the first run): every pass shot in WorldEditorRemix **before
   and after with one camera**, the textureset staged for the editor, and one
   contact sheet -- `_preview/we_sheet.png`. **Read the sheet.** Add `--at X,Y`
   (tile metres, repeatable) for anything else worth a look: a spot the user
   pointed at, one long open join, a filler border. `NOT RENDERED` means the
   editor is not configured (`worldeditor_exe`, `worldeditor_data` in
   `m2map.paths.json`) -- tell the user the map was not checked in the engine.
6. Show the user the renders. Whatever they correct becomes code, a line in this
   file, a test and a failure-atlas entry. Tell them the one step left to
   them: **F6 in WorldEditorRemix** (shadowmap + minimap) — then `tools/sync.py`,
   `tests/run-all.sh`, commit.

If it breaks, the three questions that found every fault so far: *are the blocks
right* (`MergedMap.torn_borders` / `.blocks`), *is there floor on the join*
(`_cell_free` along the seam column), *how long is the path* (`route`).

## Run it

```
python scripts/readapt_map.py <merged map> --out <new folder>
python scripts/readapt_map.py <merged map> --out <new folder> --no-level --floor 12
```

Never in place. The merged map is copied to `--out` and only files whose bytes
changed are rewritten. The report is printed and kept as `<out>/_readapt.json`;
`<out>/_preview/readapt_{before,after,route,tile}.png` are the 2D check.

## What it does, in the order it has to

1. **Find the source maps from the tears.** A border whose two copies of the
   shared vertices differ by more than 50 cm on average was never one piece of
   terrain. Sectors joined across every border that is *not* torn are one block.
   Nothing about the merge needs to be remembered or passed in — a 2x6 stack, a
   row, or an L all fall out of the same test.

   **(02)** The test is the border's **median**, not its mean. A sound border
   that *ends* on a torn one shares its corner vertex, and one 40 m corner in 129
   vertices is a 31 cm mean: four borders inside `n_desert_01` read 57–67 cm,
   were called torn, and the tool tried to route a block to itself.

   **(03)** A block with no paint at all is **filler** -- a staggered or
   overlapped merge is squared off with blank sectors. It is reported as
   `void_blocks`, gets no pass, no vote in the weld (it is all "walkable" and
   would drag a real ring down to its plane), takes the datum of the borders it
   shares, and is never painted from: its ground slot is 0, the eraser, and
   dithered across a join it punches lime-green holes in the road.

2. **Route one pass per pair of neighbouring blocks.** The floor of a block is
   its largest component of **unblocked tiles** -- **(03)** not "free and dry":
   `c1`'s river has the water flag and no block (forded, bridged), and read as a
   wall it cut the map into three floors and sent two passes 857 m and 897 m
   across open ground, carved into ramps the whole way. Tiles, because a bridge
   deck is narrower than a 2 m cell. Only the two mouths must be dry. The pass is the cheapest path from one
   floor to the other: rock costs by how much of it stands above the local
   floor, water is nearly a wall (60×), open ground is free. It finds the thin
   place in the double ring by itself — and on the test map it crossed a moat at
   its very end rather than through the middle, which is where a person would
   have put the causeway.

3. **Level.** Each block is shifted so the two **mouths** of the link — the
   median floor within 16 m of each end of the pass — stand at one height.
   Walkable, DRY cells only: no mountain enters it, and **(03)** no ford or
   lakebed either -- a mouth beside `b1`'s lake read 35 cm low with them in.
   Nothing wider. `guild_01` is tiered (islands at 17,320 and 19,720 cm): its
   median would have sunk the island the road lands on 21 m below its neighbour.
   **(02)** And "the commonest floor within 120 m" is only right on flat maps:
   between desert dunes and a volcano's flank it left the mouths 13.3 m apart
   and the pass at 26%. Levelled by the mouths the flame map rises 13.63 m and
   the pass is flat. Mouths already within 1 m are left alone.

   **(03)** Three maps that all touch make a cycle, and a block has one datum:
   two links level flat and the third takes what is left (68 m, here). Levelling
   follows the tree of **thinnest walls**; a spare link is kept only if it comes
   out under `max_grade_pct`, and is otherwise listed in `skipped_links` -- the
   two maps are already joined through the third.

   A datum shift moves **three** things by the same number, and forgetting any
   one is invisible in the other two:

   | Layer | Field | Unit at the file |
   |---|---|---|
   | terrain | every vertex of the block's `height.raw` | RAW (`cm / HeightScale`) |
   | water | every layer height the block's sectors use | RAW — same scale |
   | objects, ambience | `z` — **not** the height bias | cm |

   The bias is the author's offset *from* the ground; the ground moved, the
   offset did not. `--no-level` keeps every datum and lets the pass climb
   instead; the report flags a grade over 18% (corpus cuts run 5–18%).

4. **Weld.** Every shared vertex takes the mean of its owners — **(02)** with
   walkable ground outvoting rock 50 to 1. Two sealed maps meet wall to wall and
   the plain mean is right; `n_desert_01` has no ring on that side, its floor
   runs to the join (548 free cells on the seam column, 0 opposite), and a plain
   mean lifts that floor half-way up the neighbour's cliff in one row. Each sector
   is pulled onto it with a smoothstep fade over 16 cells, so a 40 m tear becomes
   a slope rather than a spike. The fade stops short of walkable ground — the
   wall is ours to reshape, the floor is not — except on the border row itself,
   which must close. Sectors are written through `to_sector_raw`, so the skirts
   agree by construction.

5. **Carve.** The path is smoothed (and bent into a shallow S when the rock was
   uniform — a cheapest path through uniform cost is ruler-straight, and a ruled
   trench is the one shape a hand-cut pass never has). Along it the ground is
   *clamped*, not replaced: `z = clip(z, target − bank, target + bank)`, with
   `bank` zero on the 16 m floor, a 31° foot for 3 m and ~61° beyond. One
   formula cuts through rock, fills across a dip and leaves alone everything
   that already fits. Corpus cuts through mountain measure 12 / 16 / 20 m wide
   with walls +5 m at 6 m out and +11 – 19 m at 10 – 12 m.

6. **Open and paint.** `attr` is cleared of block **and** water on the floor.
   The road is solid in a 7 m core and dithered for 3 m at the rim (rule 19).
   A merged palette is a union, so ground, cliff and road slots are read **per
   block** off how that block is painted: ground is the commonest slot on its
   walkable tiles, cliff is any slot ≥ 75% blocked, road is its most-used other
   `field*` slot. The two palettes hand over in an 8 m dither across the join.
   `--road-slot BLOCK:SLOT` overrides.

   **(02)** Every join is dithered for 12 m either side along its whole length,
   not only at the pass. Wall to wall nobody sees it; sand against lava rock
   along a ruled line 1.5 km long is the first thing anyone sees. A faint line
   survives at the sector edge itself — the splat is per sector — and only a
   re-save in the editor softens that.

7. **Objects ride the ground.** Every record's `z` moves by exactly what the
   terrain under it moved — level, weld and carve in one number. Records on the
   new floor are removed and counted. A record listed by one block but standing
   in another gets the datum shift only, and is counted as `stray`.

8. **`server_attr` is rebuilt** from the `attr` just written, masked `& 0x07`
   (rules 5, 14) -- `codec/server_attr.py`, pure Python, seconds. It used to be
   deleted and left to the user; the codec was in the repo the whole time.

9. **Read it back** (rule 18). From the files just written: the worst tear left
   on any shared vertex (must be 0), and whether one walkable component now
   holds every block's floor. On the test map also: submerged cells per block
   13,079 / 534 / 2,858 → 13,036 / 534 / 2,858 (the 43 are the causeway), and
   object-to-ground offsets p5/p50/p95 −7 / 0 / 4 cm before and after.

## Then look at it

`--render` / `--render-only` (step 5). The 2D previews cannot show a tear, a
blank tile or a plane over a bank; only the engine draws one. On
`map_merge_test_03` the lime-green eraser holes passed every number and were
found in the first shot. Ten shots and the sheet take about a minute.

## What it does not do

- **`shadowmap` and `minimap` are left as merged.** They are stale over the
  pass, and along every welded join. Open the result in WorldEditorRemix and
  press **F6**: that regenerates both, and for now it is the only way -- the
  headless `--regen` is the same key and bakes black minimaps (`we-api.md`), nothing
  in this repo bakes a shadowmap or a minimap, and rebaking two sectors here
  would put a lighting seam where there was none. Say so when handing the map
  over; the report carries the same line as `shadowmap_minimap`.
- **Spawns** are not touched: `regen.txt` heights are the server's business and
  the coordinates did not move.
- **No bridge.** A pass that must cross water becomes a causeway. If the water
  is wide, put a `bridges:`-style fit there by hand (rule 27,
  `reference/structures.md` §5).
- **An overlap crops a map, and the crop is not repaired.** Where `c1` was laid
  over `b1` and `a1`, a lake and a road end at the join against the newcomer's
  ring. The weld makes that a cliff; ending the road somewhere is an `improve`.
- **One pass per pair of blocks.** Want a second, or a specific place? That is
  an `improve` on the result.

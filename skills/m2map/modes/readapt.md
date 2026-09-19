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

2. **Route one pass per pair of neighbouring blocks.** The floor of a block is
   its largest walkable, dry component. The pass is the cheapest path from one
   floor to the other: rock costs by how much of it stands above the local
   floor, water is nearly a wall (60×), open ground is free. It finds the thin
   place in the double ring by itself — and on the test map it crossed a moat at
   its very end rather than through the middle, which is where a person would
   have put the causeway.

3. **Level.** Each block is shifted so the floor the road **joins** matches
   across the link — the commonest floor height within 120 m of each mouth, not
   the map's median and not the mouth itself. `guild_01` is tiered (islands at
   17,320 and 19,720 cm): its median would have sunk the island the road lands
   on 21 m below its neighbour. Floors already within 1 m are left alone.

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

4. **Weld.** Every shared vertex takes the mean of its owners, and each sector
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

7. **Objects ride the ground.** Every record's `z` moves by exactly what the
   terrain under it moved — level, weld and carve in one number. Records on the
   new floor are removed and counted. A record listed by one block but standing
   in another gets the datum shift only, and is counted as `stray`.

8. **Read it back** (rule 18). From the files just written: the worst tear left
   on any shared vertex (must be 0), and whether one walkable component now
   holds every block's floor. On the test map also: submerged cells per block
   13,079 / 534 / 2,858 → 13,036 / 534 / 2,858 (the 43 are the causeway), and
   object-to-ground offsets p5/p50/p95 −7 / 0 / 4 cm before and after.

## Then look at it

Render each link in WorldEditor **before and after, same camera** — target the
midpoint of `from_tile`/`to_tile` from the report (×100 for world cm), `--cam
45,0,9000`. Copy the merged textureset beside the editor first or the shot is
untextured. The 2D previews cannot show a tear; only the engine draws one.

## What it does not do

- **`shadowmap` and `minimap` are left as merged.** They are stale over the
  pass. Re-save the map in WorldEditor to rebake them; rebaking two sectors here
  would put a lighting seam where there was none.
- **`server_attr` is dropped**, as in a merge — `attr` changed, regenerate it
  (rule 14).
- **Spawns** are not touched: `regen.txt` heights are the server's business and
  the coordinates did not move.
- **No bridge.** A pass that must cross water becomes a causeway. If the water
  is wide, put a `bridges:`-style fit there by hand (rule 27,
  `reference/structures.md` §5).
- **One pass per pair of blocks.** Want a second, or a specific place? That is
  an `improve` on the result.

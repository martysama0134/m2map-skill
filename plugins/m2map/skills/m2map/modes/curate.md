# curate — finish what a mapper left unfinished

Somebody's map loads and plays, but parts of it were never finished. `audit`
finds the worst of it with the quality rules (`M2MAP-QA-001..004`); `curate`
fixes it, along with the three water rules the audit knows
(`M2MAP-WTR-005/004`, `ATR-002`), measured map-wide here because a plane runs
across sectors. **It is interactive. Never fix anything the user did not pick.** The
user knows which parts of the map are deliberate.

| Flag | What the player sees | Fix | What it writes |
|---|---|---|---|
| `M2MAP-QA-002` | the whole map walkable: mountains and the edge too | `attr` | a block layer: slope ≥ 20°, steep rock, a 4 m border band, Building collision boxes, water, ground the terrain strands. Roads stay open. Additive: blocks already there stay |
| `M2MAP-QA-001` | players walk up painted cliffs | `rock` | BLOCK on rock-painted ground ≥ 25° |
| `M2MAP-QA-003` | a road cut with a ruler | `road` | dithers the rim of each flagged road slot: road 3 m out, ground 2 m in, thinning. Seeded |
| `M2MAP-WTR-005` (info) | the shoreline is a staircase of 2 m water cells | `water` | carries the plane over the shallows (up to 16 m, never over a lip deeper than 8 m) until the ground rises through it; where the surface is perched over flat ground and no shore is in reach, takes that growth back and raises a 30 cm bank under the plane's edge instead, feathered over 6 m. Objects on it ride up |
| `M2MAP-WTR-004` | some water swims, some is walked on | `water` | WATER on the deep water it missed, BLOCK too if the map blocks its water -- only on a map that flags its water at all |
| `M2MAP-ATR-002` | swimming in mid-air | `water` | clears WATER where no plane is |
| `M2MAP-QA-004` | the world ends in plain sight | `border` | a rock rim along the open stretches only: about 15 m high (9–21 m with relief), a face and then a crest, its foot wandering, tapered at the ends. Painted with the map's commonest rock, blocked, objects lifted with the ground |

Every fix also regenerates `server_attr` whenever attr changes (rule 14). It
writes only the sectors whose bytes changed.

## Procedure

1. **List.** `python scripts/curate_map.py <map> --list` prints the flagged
   findings as JSON, each with the `fix` that answers it.
   - A `QA-000` entry means the textureset was not found, so the rock and road
     checks did not run. Pass `--textureset-dir`. The script already tries the
     map's own `textureset/`, the client pack and the editor's data root.
   - A `QA-004` entry carrying `"after": "attr"` may come from the missing attr
     alone: the edge test counts a mostly-blocked band as a wall. Offer `attr`
     now and the border only after a fresh `--list`. On `metin2_map_a1` with its
     attr wiped, the attr fix cleared all three flags.

2. **Ask.** Use AskUserQuestion with multiSelect. Make one option per flagged fix,
   and put the evidence (the `detail` line, in plain words) in its description.
   Ask about scope in the same call:
   - whole map, or
   - only the sectors the findings name (`where` / `detail` list them as
     `XXXYYY`), or
   - "Other" for their own list.

   Nothing flagged: say so and stop. Do not invent work.

3. **Apply.** Run `python scripts/curate_map.py <map> --fix <picked> [--sectors ...] --render`.
   - It first copies the map to `<map>_backup_<time>`. Never pass `--no-backup`
     on someone's map.
   - `--seed N` gives a different dither or ridge. The same seed always gives
     the same result.

4. **Check the report.**
   - `flagged_after` should have lost every rule that was fixed.
   - `changes` gives one line per fix. "no hard-edged road slot" or "no open
     edge" means there was nothing to do.
   - `notes` are things the user must hear. Example: the attr fix found the
     walkable ground split into pieces and sealed none of them as stranded.

5. **Show it.** `--render` shoots every changed spot in WorldEditorRemix, the
   backup on the left and the result on the right, into
   `<map>/_curate/we_sheet.png`. Send the sheet. If it printed "NOT RENDERED",
   say the result was not checked in the editor. Attr-only fixes have nothing to
   see; say so.

6. **Finish.**
   - Raised terrain leaves the editor's shadow and minimap stale. Bake them with
     `we_shots.bake(<map>)` (WorldEditorRemix v61, `--bake`), or have the user
     press F6.
   - Ask whether to keep the backup.

## Limits, measured

- **attr.** The attr fix was run on Ymir's own maps with their attr wiped.
  - Cell agreement:

    | Map | Agreement | Where it differs |
    |---|---|---|
    | `metin2_map_a1` | 94% | |
    | `map_a2` | 92% | |
    | `metin2_map_trent` | 92% | |
    | `n_desert_01` | 85% | blocks the dunes over 20° that Ymir left walkable |
    | `milgyo` | 77% | |

  - On `milgyo`, the low ground under the temple cliffs is its own piece of
    terrain. A slope cut cannot tell it from a piece people play on. The fix
    seals stranded ground only when one piece holds at least 60% of the
    walkable ground.
  - On `map_a2` the ramps are steeper than 20°, so slope alone splits the map
    into a dozen pieces of 4–12% each. There the stranded ground is left open,
    and a note says so.
  - Buildings use their `.mdatr` collision box. Some maps leave the collision
    to the model and paint no block under buildings: `map_a2`,
    `wl_01`/`t1`–`t3` and most dungeon blocks (`attributes.md`). On those maps
    the fix blocks more than Ymir did.
- **water.**
  - Flagging water at all is a convention. 28 official maps leave 85–100% of
    their deep water unflagged; the ones that flag it miss 0–23%.
  - So the fix adds WATER only on a map that already flags its water, and
    WTR-004 fires only there.
  - The exposed shore measures 0.2–2.7% on official outdoor maps, and 0–0.7% on
    the skill's own builds. It is over 30% only on milgyo, smhgate_c1 and
    eastplain_03: pools set into carved floors, where the staircase is by
    design. Ask before banking a pool like that.
  - Steps between two water levels that meet (a river's level bands) are not
    fixed. The corpus shows 0–36 such cells per map.
  - Raising terrain out of the water (a rim or a bank) clears WATER from the
    cells it lifted dry.
- **road.** A hard edge can be a style choice: 3 of 146 official roads are
  hard-edged too. That is why QA-003 is minor. Ask before fixing it; never fix
  it unasked.
- **border.** The rim is terrain only. Where the map wants a curtain wall
  (a castle or a town edge), this rim is the wrong answer. Say so, and offer a
  set piece from `reference/setpieces/` instead. The rule already counts a line
  of buildings 4 m or taller as a wall. A bay with a water horizon, and an
  entrance up to 64 m wide, are not flagged.

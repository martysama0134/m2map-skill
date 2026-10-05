---
name: m2map
description: >
  Use when creating, modifying, auditing, merging, reskinning or populating
  Metin2 client maps — user says "/m2map", "make a map", "generate a map",
  "add a road", "the north sector is empty", "why do my objects not show up",
  "register this pattern", "save this group of objects", pasted AreaDataFile text,
  "players fall through the floor", "merge these maps", "connect these merged
  maps", "there are gaps where the maps join", "add spawns", "make a labyrinth",
  "maze dungeon"; provides a
  map folder or a screenshot of terrain to match; or references any map file
  (setting.txt, height.raw, tile.raw, attr.atr, water.wtr, areadata.txt,
  server_attr, a textureset, an .msenv, a .pr* property file, an XXXYYY sector
  folder).
---

# /m2map — Metin2 Map Generator

<SUBAGENT-STOP>
Dispatched as a subagent with a specific task? Skip mode detection and execute the task directly — the parent agent already loaded m2map context and picked the mode.
</SUBAGENT-STOP>

## Mode Detection

Priority order:

1. **Explicit keyword**: args start with `generate`, `improve`, `audit`, `merge`, `readapt`, `curate`, `reskin`, `server` or `register` → that mode
1b. **One map that is already a merge** — "connect them", "join the maps with a road", "gaps / slits where the maps meet", "the merged maps are at different heights", or an audit showing `M2MAP-HGT-001` → **readapt mode**. Merging is step one and MapForge does it; readapt is step two
1a. **Pasted `areadata.txt` text** (`AreaDataFile`, `Start Object000` …) or "register / save this group / pattern for later" → **register mode**. A paste is a selection to keep, not a map to audit
1c. **"Is this map finished / low quality / what's wrong with this mapper's map"** → **audit mode**; the `M2MAP-QA-*` quality rules flag walkable cliffs, missing attr, ruler-cut roads and open map edges (`modes/audit.md`). **"Fix / upgrade / curate / polish this mapper's map"** → **curate mode** (`modes/curate.md`): list the flags, ASK which to fix and where, back up, fix, render before/after
2. **Symptom report**: args contain a visible-fault phrase ("objects don't show", "falls through the floor", "blocked in open ground", "error texture", "map won't load", "seams", "blank minimap", "walks on water") → **audit mode first**, then `improve` if a fix is wanted
3. **Two or more map paths**, or "combine"/"stitch"/"expand" → merge mode
4. **One map path + a biome word** ("make it snowy", "desert version") → reskin mode
5. **One map path + a change description** → improve mode
6. **One map path alone** → audit mode
7. **Spawn words** ("regen", "spawns", "npc", "boss", "stone", "add monsters") → server mode
8. **Text description of a place** → generate mode
9. **Image attached** → generate mode, using the image only for *style cues* (biome, density, palette feel). See "Screenshots" below.
10. **No args**: ask — "(a) Generate a new map, (b) Improve an existing one, (c) Audit for problems, (d) Merge or expand, (e) Reskin to another biome, (f) Add spawns, (g) Register a group of objects as a reusable pattern, (h) Readapt a merged map — level it, close the joins, connect the pieces, (i) Curate somebody's map — fix the unfinished parts the quality rules flag" — then dispatch

Read the matching mode file from `modes/` adjacent to this SKILL.md.

## Before Doing Anything

**Mandatory floor (always load):**

1. `reference/mental-model.md` — the three grids, centimetre units, negated `areadata` Y, sector-name arithmetic, the positional-array text grammar, textureset slot 0, the YPRT property container. Skipping this produces confidently wrong output.

**Conditional load (only what the task needs):**

| Task | Load |
|------|------|
| Generating a new map | `reference/archetypes/README.md` → walk its selection tree → the one archetype doc |
| Any placement decision | `reference/placement.md` — the family's section |
| Registering a new pattern | `modes/register.md` — verify the paste, read the ground, render source and copy |
| Joining the pieces of a merged map | `modes/readapt.md` — blocks from the tears, the three-layer datum shift, weld, pass, road |
| Fixing an unfinished map somebody else made | `modes/curate.md` — the four QA fixes, ask first, backup, render |
| A labyrinth / maze dungeon built from dungeon pieces | `reference/labyrinth/README.md` — the six kits, `labyrinth:` in the mapspec |
| A bridge, a moat, a pier or anything at a waterline | `reference/structures.md` §5-6 — the measured fit, `BRIDGE_MODELS`, shore patterns |
| Reusing a shipped compound (camp, town square, yard, shrine) | `reference/setpieces/README.md` — the patterns, and how to turn and stamp one |
| Choosing or composing a palette | `reference/textures.md` |
| Choosing lighting/fog | `reference/environments.md` |
| Identifying what a prop *is* | `reference/objects.md`, then `catalog/objects.json` |
| Collision policy | `reference/attributes.md` |
| A reported symptom | `reference/failure-atlas.md` — the matching entry FIRST |
| A byte layout question | `reference/mapformat/<file>.md` — **ground truth** |
| Driving WorldEditor | `reference/we-api.md` — the binding's entry, and its warnings |
| Cross-archetype conventions | `reference/taste.md` |

Load the *section* you need, not the whole file. Several are 60-80KB.

## Output Targets

| Output | Path |
|--------|------|
| Map folder | `<output_dir>/<map name>/` (configured; see `m2map.paths.json`) |
| Textureset | `<client pack>/textureset/textureset/<name>.txt` |
| Environment | `<client pack>/yw_etc/ymir work/environment/<name>.msenv` |
| Generated spec | `<map>/mapspec.yaml` — committed beside the map |
| WorldEditor script | wherever the user wants; emit, don't run |

## Critical Rules

All modes, all generated output. Reference files cite these by number — numbering is frozen; new rules append.

1. **A map is not self-contained.** `tile.raw` stores indices into an external textureset; `areadata.txt` stores CRCs into an external property DB. Ship them together or the map renders as error texture with missing objects.
2. <EXTREMELY-IMPORTANT>
   **Never invent a CRC, a `.dds` path, an `.spt`/`.gr2` path or an `.msenv` name.** Every one must exist in `reference/catalog/` or on disk. An unregistered CRC is **silently dropped at load** — no error, no log, no placeholder, the object simply is not there. Verify against `catalog/objects.json`; if you need something absent, say so rather than guessing.
   </EXTREMELY-IMPORTANT>
3. <EXTREMELY-IMPORTANT>
   **`areadata.txt` stores Y NEGATED** (`stored_y = -terrain_y`) in **map-local** centimetres. `BasePosition` is NOT added — that is the server's job. Getting the sign wrong mirrors the entire object layer about the X axis and still looks plausible.
   </EXTREMELY-IMPORTANT>
4. **Fixed file sizes are load-bearing**: `height.raw` 34,322 · `tile.raw` 66,564 · `attr.atr` 65,542 · `shadowmap.raw` 131,072. Stored dims exceed logical ones (131 vs 129, 258 vs 256). The loaders `memcpy` blindly — a wrong size is silent corruption.
5. <EXTREMELY-IMPORTANT>
   **`server_attr` masks to `& 0x07`.** The server blocks on `ATTR_BLOCK|ATTR_OBJECT` (`0x01|0x80`) and Ymir paints bit 7 on *walkable* mountain. Copying the whole byte — which `ServerAttrGenerator.cpp` does — blocks **every cell of the map**. Measured on `map_a2`: 9,437,184 of 9,437,184 against the shipped 6,246,724.
   </EXTREMELY-IMPORTANT>
6. **Keep the high bits in `attr.atr` itself.** Rules 5 and 6 are not in tension: the client file keeps every bit, the server file keeps only bits 0-2.
7. **`areaproperty.txt` defines the sector.** Delete it and the sector vanishes even with every binary layer present.
8. **Slot 0 is the eraser.** `TextureCount` excludes it; blocks are 1-based `%03d`; a `tile.raw` byte of 0 means blank. Cap 255 usable.
9. **Heading is `roll`, not `yaw`**, snapped to 15°. Yaw and pitch are tilt channels used almost exclusively by debris. Trees are unrotated ~2/3 of the time.
10. **There is no road texture.** Roads are ordinary field textures painted in a corridor.
11. **Ground is a 1 m per-tile stipple**, not region fill: median run length 2 tiles, half of all components a single tile. **Ground only** — see rule 19.
12. **Water flags follow *submerged*, not *wet*.** A water plane below the terrain is invisible and correctly unflagged; 452 of 1343 shipped sectors have one.
13. **Proxy maps own no terrain.** 26 of 142 maps have zero sectors and a `ParentMapName`; 3 have no `setting.txt`. Resolve before assuming.
14. **Regenerate `server_attr` whenever `attr.atr` changes**, or client and server disagree about collision.
15. <EXTREMELY-IMPORTANT>
    **The vendored `mapformat/` spec is ground truth EXCEPT where the corpus disproved it.** Known errata, all marked inline in those files: DDS is DXT1 not the 262,272-byte uncompressed form (0 of 1332 files); `server_attr` masks; duplicate keys are **first**-wins not last; there are no beta-era 5-file maps.
    </EXTREMELY-IMPORTANT>
16. **Do not run WorldEditor scripts.** Emit them and hand them over.
17. **ASCII-only in emitted Python.** cp1252/cp949 build encodings.
18. <EXTREMELY-IMPORTANT>
    **Five unit conventions live in one map. Convert at the write boundary, and verify by reading back.** `water.wtr` heights are RAW (`worldZ = value * HeightScale`), `height.raw` is RAW, `areadata` is map-local centimetres with Y NEGATED, regen/Town are units of 100, and `ViewRadius` is DOUBLED by the engine on load. A byte round-trip cannot catch a unit error -- it preserves the wrong unit perfectly in both directions -- and neither can an in-memory assertion, because the model is right. The only check that works crosses the boundary and comes back: write, re-read, and assert something that depends on the unit ("the water is above the terrain", "the object is inside the map"). See `reference/failure-atlas.md` section 4.
    </EXTREMELY-IMPORTANT>
19. <EXTREMELY-IMPORTANT>
    **Three features are painted SOLID and rule 11 does not apply to them.** The **cliff** is a region-filled skin covering **exactly the ground the player cannot walk on** — P(blocked | cliff-painted) is 0.91–0.99 across eight maps, and on `metin2_map_n_desert_01` the two masks have an IoU of 0.93. Unwalkable means **unreachable**, not steep: the high third of the border ring is 100% blocked on all five maps measured, so the wall is sealed over its crest, and stranded walkable ground is 0.00–0.13% of a corpus map. Drive it off `gen/walkable.py`, which both the attr and texture stages read, paint the interior with **one** texture (the corpus dominant slot holds 100/100/94/88/75/64/59 % across seven maps) and mix only at the rim. Everything walkable and off the road is grass or sand — measured massif÷raw 0.86–0.99 across eight maps, against 0.02 when it was sampled per tile like the ground, which made every mountain read as pepper. Its rim feathers out over 5–7 tiles and then stops dead (far field 0.00%). The **road surface** is solid, dithered only in a ~3 m rim, and the rim's partner is a sibling of the road's own motif (`field 01` core, `field 02` edge). The **plaza disc** has no dither anywhere: solid 0.84–0.87, an 8–25 m circle, 100% `ATTR_SAFEZONE` with block cleared. See `reference/taste.md` §1.8–1.11.
    </EXTREMELY-IMPORTANT>
20. **`stone*` is the mountain, `tile*` is the plaza, `field*` is the road and the ground, `sand*` is the shore, `grass*` is the green.** The filename motif is a strong prior for *composing* a palette (`cliff` slots are `stone*` 62% of the time; `path` slots `tile*` 64%) and a weak classifier for *reading* one — the same `stone01.dds` is `base` in one map and `cliff` in another. Set `TextureSlot.role` from the job you intend; the generator reads `role`, never the filename. `reference/textures.md` §4f.
21. **Roads do not cross blocked mountain.** Block rate inside a corridor: median 5.9% against 69.4% in the control band beside it. Clear the corridor for its whole length and route around massifs, not over them.

22. <EXTREMELY-IMPORTANT>
    **The terrain draws the waterline.** `water.wtr` is 2 m axis-aligned cells, so a plane that stops at its basin renders the shore as a staircase. Corpus planes run far wider than the water: only **23–57%** of water-flagged cells are actually submerged (58% over six maps). Draw the plane past the basin and let the ground that rises through it make the shore. The surface belongs **inside** the bowl — corpus depth median 174–410 cm — or the lake floods to its polygon and there is no beach.
    </EXTREMELY-IMPORTANT>
23. <EXTREMELY-IMPORTANT>
    **Fit the terrain to the prop, not the prop to the terrain.** A prop's geometry is fixed; the ground is not. `fall_7` is ~18.14 m tall anchored at its top, so on a 29.6 m wall no `height_bias` avoids either a top 11 m below the crest or a base 12 m above the water. Place the prop, derive the crest (`pool_surface + sheet_height − bite`), and build the wall to it with `ScarpSpec.crest_cm`. Two passes: the water level is an output, so build, read it, set the crest, build again — it converges in one. See `taste.md` §1.13.
    </EXTREMELY-IMPORTANT>
24. **A waterfall needs a wall.** `fall_7` sits on slope p50 **71.4°** in the corpus and is a flat quad ~40 m across; a 41–52° ridge is a ramp, and a quad on a ramp floats or buries. Cut a `ScarpSpec` first (1,800 cm over a 3 m run is 81°, the steepest a heightfield can hold is one 200 cm cell of run per drop), then place the sheet on it — raised into its measured bias band (+78/+288/+1,378 cm) and rolled to the fall line **+90°**, because the plane lies along the heading.
25. **A compound is copied whole, not assembled — and turned only as a block.** Three generated versions of the desert camp — posts on a ring, an arc at the corpus median pitch, a "run" chained from nearby records — each read as debris while every statistic passed; the copy that matched the reference render did no generating: every record within 32 m of (333, 307) in `metin2_map_n_desert_01`, offsets, rolls and height biases verbatim (`gen/setpiece.py`; the pattern is `reference/setpieces/desert_camp.json`, about its centroid — in a mapspec, `setpieces: [{pattern: desert_camp, anchor: [x, y], rotate_deg: θ}]`). To face it another way use `SetPiece.rotated(θ)`, θ a multiple of 15: roll increases **counter-clockwise with north up** (1,681 corpus fences: `roll + atan2(Δy_tile, Δx_tile)` constant at concentration 0.84, the difference 0.08), so the y-down offsets turn clockwise — turn both the same way and the rails come apart while every spacing statistic still passes. Level a pad under the pivot, and render the source at the same camera before judging the copy. `reference/placement.md` §6.w, `reference/setpieces/README.md`, `failure-atlas.md` §3.10.
26. **A pattern is records, and the ground if it was saved with them.** Copying a compound (rule 25) copies what `areadata.txt` holds, plus -- when the pattern has a `ground` -- the paint under it, keyed by texture path and painted only where the map's palette declares that texture (declare it at `weight: 0.0`; a `! ground: ... no slot for` line means it was skipped). The safezone disc, the road spokes, the levelling pad and the collision are still the spec's to supply: a `PlazaSpec` on the same anchor, `pad_radius_m` past the largest footprint on the rim. Scatter keeps off plazas and pads, and authored buildings block their own rectangle with the road kept open through it -- the b1 hotel stands on its road. `reference/setpieces/README.md`, `failure-atlas.md` §3.11.
27. **A bridge is fitted to the water, and the banks to the bridge.** Seven bridges on `metin2_map_a1`: both banks at ONE height (2-7 cm apart under stone, 10-82 cm under rope), the channel cut lip-to-lip to the span, `attr` cleared of block AND water under the deck while the river beside it is 91-100% blocked. The river is one level and the banks vary -- **2-5 m over the water takes a stone bridge, 10 m and up a rope one** -- and `bank − (z + bias)` is a constant per model (948/951 cm on two `a1-024` whose stored biases are 0 and −290), so the bias is computed, never copied. Use `bridges:` with a river that has a `surface_z`; an auto-levelled river is banded to the ground and its planes hang over the levelled banks. Shore props (rafts, piers) follow the same rule from the other side: a pattern saved with `water_cm` is stamped against the target's surface. `reference/structures.md` §5-6.

28. <EXTREMELY-IMPORTANT>
    **A merge is not a map: the borders are torn, the rings are double and the datums differ.** Sectors are copied verbatim, so each keeps its OWN copy of the shared border vertices — 1,712–4,047 cm apart on average on three merged guild maps, against 99.86% agreement in the corpus — and the terrain renders with slits. Every file is valid, so the audit passed until `M2MAP-HGT-001` compared neighbours. `scripts/readapt_map.py` recovers the source maps from the tears, then: **a datum shift moves terrain, water layers and object `z` by the same number — never the height bias**, and levels to the two **mouths** of the pass, nothing wider (a tiered map has no single floor — the median would have sunk `guild_01`'s landing island 21 m — and on rolling ground the commonest floor within 120 m left the mouths 13 m apart); a border is torn by its **median**, because a sound border ending on a torn one shares a 40 m corner; borders are welded to a mean in which walkable ground outvotes rock 50:1 (an open-edged map brings its floor to the join), with a 16-cell fade that spares walkable ground; the palettes are dithered 12 m either side of every join; the pass is the cheapest path between the two floors, cut by *clamping* the ground to `target ± bank` so one formula cuts rock and fills a moat; road, ground and cliff slots are read **per source map**, because a merged palette is a union; a floor is unblocked **tiles** -- a forded river is not a wall -- blank filler blocks are not maps (no pass, no weld vote, never painted from), and three maps in a cycle level along the thinnest walls with the spare link kept only under 18%. Verify from disk: tear 0, one walkable component, pond depths and object-to-ground offsets unchanged. `modes/readapt.md`, `failure-atlas.md` §3.12.
    </EXTREMELY-IMPORTANT>

29. **Some records are nothing without their mountain, and a paste may have no position.** A volcano is ONE effect record (roll 0, bias 0) on a crater floor; the cone, the lava disc and the block are terrain. Such a thing is a **landform pattern** -- saved with `--relief-radius`, stamped as heights above the base of its own outer ring plus the paint on it, no pad, after roads and pads (`br_volcano_*`). And a WorldEditorRemix `WE_OBJECTS_V1` paste holds offsets from its own box with **y growing north**: it is found on its map by its rarest CRC (`--from-we-objects FILE --locate-on MAP`) and the pattern is built from the map's records. A landform may hold water: the plane is saved about the same base and the source collision is forced last, because a bridge deck over a moat is a record and the generator only sees submerged ground (`moat_island_*`). And **a map-edge entrance is angular**: behind the gate the road runs on, painted and blocked, ~25 m and then bends 60-90 degrees behind rock, so a player looking through never sees the void (`thunder_zone_gate_east`, base read at the pivot because a gully's ring is cliff). `reference/setpieces/README.md` "Landforms", `modes/register.md`.

30. **Islands are cut out of a plateau, not raised from a sea.** `map_a2` is ~20 mesas at one level (tops equal to the metre across each of its 21 rope bridges), canyons 54-60 m lip to lip because that is what `suspension bridge01` spans, walls down in 12-18 m, ONE water plane 53-95 m below with rock painted across its bed. State it as `islands:` -- one site per island, the canyons are the bisectors -- and let the stage cut them AFTER roads and pads: cut first, road levelling builds a causeway under every bridge. A road joins two tops for reachability but its paint and open attr stop at the lip; an island no road reaches is sealed as rock. The sea is not `wet` -- desert flora keeps 50-300 m from authored water and no island is that wide. `reference/structures.md` §7.

31. **Block without rock is a bug to the player.** The slope rule is per cell; the rock skin drops anything under ~5 tiles thick. So a low hump whose flank touches the threshold for a few metres comes out blocked and still sand -- an invisible fence in open ground (1.45% of a generated 1x1, strips of 3-6 m all over `map_ad3`'s tops). `attribute._open_slivers` reopens whatever slope-block is thinner than 9 tiles, has no cliff paint within 3, and is not void or border. Rock may be blocked; sand that is blocked must be under a prop or under water. And **a rope bridge sits unevenly on a rounded lip** -- 2.5 m of bank under its origin, 9.3 under its far end, the wall falling as 0.28 d^2 -- measured by walking the model's axis, in all four directions, because the pooled masks were a metre off by compass. `reference/structures.md` §5.2b.
32. **A road keeps a shoulder, and block never runs ahead of the rock.** Stone does not have to be blocked -- by distance from the road paint `map_a2` measures rock 20.6 / 24.5 / 28.8 / 35.3% against block 19.3 / 21.4 / 24.6 / 30.9% (1-2, 2-3, 3-5, 5-8 m), rock ahead at every step, and `metin2_map_n_desert_01` is 2% blocked anywhere inside 5 m -- but block without stone beside a road is a saw-toothed slot. Opening only the painted core did that wherever a road crossed a hump: 42% blocked against 9% rock 2.5-4 m out. `Layout.road_clear` is the core plus `ROAD_SHOULDER_M` (2.5) and BOTH the attr stage and the rock skin read it, so the two retreat together.
33. **A rebuild keeps the scatter.** Rebuilding over an existing map of the same size, seed and object tiers keeps every scattered object at its x, y, roll and bias and only re-seats it on the new ground; one is replaced only if its spot became a road core, a plaza, void or water, and the top-up is thrown only in the sectors that lost something. Authored placements are laid again from the spec. The dart order is seeded but the candidate mask is not the same mask after any terrain change, so without this **577 of 577** objects moved for one added road. `build_map.py` does it by default (`objects: kept N ...` in the log); `--rescatter` is the explicit request for a new throw. The author has walked the map -- do not reshuffle it under them for a fix two sectors away.
34. **A levelled corridor is feathered out, never cut at its mask.** The corridor mask is binary on the 2 m grid; along a diagonal road crossing a slope, levelled ground met raw ground at a new height on every step of the staircase and the verge came out as 2 m saw-teeth (`map_ad3`, one verge: roughness 618 cm against 245 with no levelling). `terrain._feather_out` carries the levelled surface 5 cells outward and mixes it back through a BLURRED mask, which has no staircase in it. Isolate a terrain artefact by switching stages off one at a time and measuring -- the berm beside that road was the obvious suspect and was innocent.

35. **A labyrinth is assembled from a kit, never placed piece by piece from statistics.** The corpus labyrinths (anglar, whitedragon 01/02, skipia, spider, mt_thunder, maze/monkey) are mined into `reference/labyrinth/kits.json`: each piece's floor, its walk measured from the shipped attr, its sockets and what rides on it. Pieces join where their **socket families** joined in the corpus -- a whitedragon room's 10 m mouth only through a door, anglar's 31 m cave corridor and 41 m stone corridor only through `anglar_cavegate2` -- and a run between two junctions is solved to the centimetre from the kit's straights, on a grid whose columns and rows move so the runs close. Each family keeps its own way of making walls: `spider` builds the whole room grid and fences arms shut, the maze/monkey kits are letter islands joined by warp gates (their one 63.5 m corridor cannot close a grid), the rest lay corridors only where the maze runs. The floors stand 1 m over the hidden terrain and `TerrainVisible 0` is written, or the plane z-fights every floor. The build log must end `start -> boss REACHABLE`, read off the attr as written. A labyrinth with **no objects** is `kit: orc_trench`: the same maze cut into the terrain as 29.5 m trenches (16 m floor, 12 m walkable, walls up in 8 m, 24 m ridges), letters joined by warp gates, measured on `metin2_map_orclabyrinth`. `reference/labyrinth/README.md`.
36. **Curating somebody's map fixes only what the user picked, after a backup.** `scripts/curate_map.py --list` turns the `M2MAP-QA-*` findings into a menu (one fix per rule: `attr`, `rock`, `road`, `border`, and `water` for the staircase shore `WTR-005`, half-flagged water `WTR-004` and stray water bits `ATR-002`); ask with AskUserQuestion which fixes and which sectors, never assume -- a hard road edge or a low rim may be the mapper's style. The fixes are additive (blocks already painted stay), confined to the chosen sectors, seeded, and regenerate `server_attr`. With no attr at all every rim reads open, so the border is offered only after the attr is back (`a1` with its attr wiped: the attr fix alone cleared QA-004). A rebuilt attr agrees with Ymir's own on 77-94% of cells (`modes/curate.md`). A raised rim is a face and a crest with a wandering foot, painted as one feathered massif: a band of constant width left a ruler-straight rock line, the same fault QA-003 flags on roads. Whether a map flags its water at all is a convention (28 official maps never do): follow the map, never impose it. One water level or several is the user's call too -- Ymir steps descending rivers (a1: 5 levels over 85 m) but a lake in bands shows sand strips at every band edge; `water_level` merges levels within `--level-span-m` (3 m), and a wider span can dry an upper reach. A rim takes the trees off its new bare rock, and nothing else. `modes/curate.md`.

## Verification — not optional

<EXTREMELY-IMPORTANT>
Every mutating mode renders the 2D previews and **looks at them** before emitting. A map that parses is not a map that plays, and the statistics routinely read fine while the picture is obviously wrong — during development this step caught uniform salt-and-pepper splatting, one texture at 0.70 coverage, and trees in a regular lattice, all while the numbers looked reasonable.
</EXTREMELY-IMPORTANT>

```
python scripts/build_map.py spec.yaml --out <dir> --preview --audit
python scripts/audit_map.py <dir>
```

Then read `_preview/*.png` and ask:

- **tile** — does the road read as a road? Is the ground patchy, or uniform noise on one colour? Are regions visible without hard borders?
- **objects** — groves and clearings, or a lattice? Anything standing in water or on the road?
- **attr** — does blocked ground match the steep ground in `slope.png`? Any block in open field?
- **height** — plains and relief, or uniform rolling? Seams at sector lines?
- **water** — is anything marked submerged that should be dry?

<EXTREMELY-IMPORTANT>
**Then load it in WorldEditor.** The 2D pass needs nothing installed; this one needs the editor, and it is not a formality. Three separate faults have reached a map that every 2D preview, every in-memory assertion and every audit rule passed:

| Fault | What the checks said |
|---|---|
| Water heights written in centimetres into a raw-unit field, so every plane sat at half altitude and below the terrain | Pipeline reported 7.2% submerged; the file contained 0%. The byte round-trip passed, because it preserves a wrong unit perfectly. |
| `attr` cleared the road corridor before the water pass, sealing the route where the road crossed the river | Every layer preview looked correct except `attr` |
| Object spacing pinned to a stipple texture; 17 of 20 props never placed | Placement is best-effort, so "fewer than asked" was not an error |

The generator writes no `shadowmap.dds` and only a flat-shaded minimap; with WorldEditorRemix v61+ `build_map.py --bake` has the editor bake both headless (F6), and the build log says so -- or says `bake: NOT DONE` and why.

The 2D previews validate the **model**, and in all three cases the model was right. Only the real engine validates the **boundary between the model and the bytes**. `reference/we-api.md` has the verified command — run it from the data dir, aim `--target` at a sector centre, and use `--shot-frames 60` or the shot catches a half-loaded map.

If the editor is genuinely unavailable, say so when you hand the map over rather than implying it was checked.
</EXTREMELY-IMPORTANT>

## Pre-Emit Self-Review

<EXTREMELY-IMPORTANT>
Mandatory before any output to the user or any file write, on every emission including edits.
</EXTREMELY-IMPORTANT>

Verify each item against the draft; any failure → revise and re-check.

1. Rule 2: every CRC, `.dds`, `.spt`/`.gr2` and `.msenv` verified against the catalog or disk
2. Rule 3: `areadata` Y negative, map-local, no `BasePosition` added
3. Rule 4: every fixed-size file exactly the right length
4. Rule 5: `server_attr` max value ≤ 7
5. Rule 8: no `tile.raw` index above `TextureCount`
6. Rule 9: rolls snap to 15°; yaw/pitch zero except for debris
7. Rule 12: water attr follows submerged, not wet
8. Rule 7: every sector has `areaproperty.txt`
9. Rule 14: `server_attr` regenerated if `attr.atr` changed
10. `audit_map.py` reports **zero blockers**
11. Previews rendered **and actually looked at**
12. Rule 18: every unit-converted field re-read from the written file and checked against something that depends on the unit -- water above terrain, records inside the map, regen coordinates in tile range
13. Loaded in WorldEditor and looked at, or the user told it was not
14. The mapspec is written beside the map, so the result is reproducible

## Screenshots

Screenshot input is **best-effort and low-priority**. If a user attaches an image, read it for
*style cues only* — biome, density, palette warmth, how open or enclosed it feels, roughly what
props appear — and fold those into the mapspec. Then say plainly which cues you took.

Do **not** attempt to identify specific models from pixels. The catalog has geometry for
1780 of 2112 props but no rendered thumbnails, so there is nothing to pattern-match against;
guessing produces invented CRCs, and rule 2 exists because an invented CRC makes the object
silently vanish. Pick props by archetype and family from the catalog instead, and tell the user
that is what you did.

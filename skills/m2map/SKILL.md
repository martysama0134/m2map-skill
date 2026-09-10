---
name: m2map
description: >
  Use when creating, modifying, auditing, merging, reskinning or populating
  Metin2 client maps — user says "/m2map", "make a map", "generate a map",
  "add a road", "the north sector is empty", "why do my objects not show up",
  "players fall through the floor", "merge these maps", "add spawns"; provides a
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

1. **Explicit keyword**: args start with `generate`, `improve`, `audit`, `merge`, `reskin` or `server` → that mode
2. **Symptom report**: args contain a visible-fault phrase ("objects don't show", "falls through the floor", "blocked in open ground", "error texture", "map won't load", "seams", "blank minimap", "walks on water") → **audit mode first**, then `improve` if a fix is wanted
3. **Two or more map paths**, or "combine"/"stitch"/"expand" → merge mode
4. **One map path + a biome word** ("make it snowy", "desert version") → reskin mode
5. **One map path + a change description** → improve mode
6. **One map path alone** → audit mode
7. **Spawn words** ("regen", "spawns", "npc", "boss", "stone", "add monsters") → server mode
8. **Text description of a place** → generate mode
9. **Image attached** → generate mode, using the image only for *style cues* (biome, density, palette feel). See "Screenshots" below.
10. **No args**: ask — "(a) Generate a new map, (b) Improve an existing one, (c) Audit for problems, (d) Merge or expand, (e) Reskin to another biome, (f) Add spawns" — then dispatch

Read the matching mode file from `modes/` adjacent to this SKILL.md.

## Before Doing Anything

**Mandatory floor (always load):**

1. `reference/mental-model.md` — the three grids, centimetre units, negated `areadata` Y, sector-name arithmetic, the positional-array text grammar, textureset slot 0, the YPRT property container. Skipping this produces confidently wrong output.

**Conditional load (only what the task needs):**

| Task | Load |
|------|------|
| Generating a new map | `reference/archetypes/README.md` → walk its selection tree → the one archetype doc |
| Any placement decision | `reference/placement.md` — the family's section |
| Reusing a shipped compound (camp, yard, shrine) | `reference/setpieces/README.md` — the patterns, and how to turn and stamp one |
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

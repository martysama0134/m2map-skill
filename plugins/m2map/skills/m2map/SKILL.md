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
11. **Ground is a 1 m per-tile stipple**, not region fill: median run length 2 tiles, half of all components a single tile.
12. **Water flags follow *submerged*, not *wet*.** A water plane below the terrain is invisible and correctly unflagged; 452 of 1343 shipped sectors have one.
13. **Proxy maps own no terrain.** 26 of 142 maps have zero sectors and a `ParentMapName`; 3 have no `setting.txt`. Resolve before assuming.
14. **Regenerate `server_attr` whenever `attr.atr` changes**, or client and server disagree about collision.
15. <EXTREMELY-IMPORTANT>
    **The vendored `mapformat/` spec is ground truth EXCEPT where the corpus disproved it.** Known errata, all marked inline in those files: DDS is DXT1 not the 262,272-byte uncompressed form (0 of 1332 files); `server_attr` masks; duplicate keys are **first**-wins not last; there are no beta-era 5-file maps.
    </EXTREMELY-IMPORTANT>
16. **Do not run WorldEditor scripts.** Emit them and hand them over.
17. **ASCII-only in emitted Python.** cp1252/cp949 build encodings.

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

3D screenshots via WorldEditor headless when it is available (`reference/we-api.md`); the 2D pass needs nothing.

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
12. The mapspec is written beside the map, so the result is reproducible

## Screenshots

Screenshot input is **best-effort and low-priority**. If a user attaches an image, read it for
*style cues only* — biome, density, palette warmth, how open or enclosed it feels, roughly what
props appear — and fold those into the mapspec. Then say plainly which cues you took.

Do **not** attempt to identify specific models from pixels. The catalog has geometry for
1780 of 2112 props but no rendered thumbnails, so there is nothing to pattern-match against;
guessing produces invented CRCs, and rule 2 exists because an invented CRC makes the object
silently vanish. Pick props by archetype and family from the catalog instead, and tell the user
that is what you did.

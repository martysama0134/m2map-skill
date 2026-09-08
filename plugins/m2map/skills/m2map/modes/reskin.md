# reskin — rebias a map to another biome

Keep the terrain shape, the layout and the spawns; swap the palette, the props
and the lighting. The cheap way to get a snow version of a field map.

## What changes and what does not

| Kept | Replaced |
|---|---|
| `height.raw` | textureset + `tile.raw` |
| `water.wtr` | `areadata.txt` (props swapped by family) |
| regen and spawn files | `.msenv` |
| `MapSize`, `BasePosition` | `attr.atr` + `server_attr` (footprints moved) |

Re-runs stages 5 (texture), 6 (objects), 7 (attr) and 8 (finish).

<EXTREMELY-IMPORTANT>
**Attr must re-run.** The original design re-ran texture, objects and finish and
left collision untouched, which leaves invisible blockers where the old
buildings stood and no collision under their replacements. Object footprints are
an input to attr.
</EXTREMELY-IMPORTANT>

## Swapping props by family

Load the target archetype doc and map each source family to its counterpart:
broadleaf to conifer, field rock to snow rock, and so on.
`catalog/objects.json` groups props by family and folder, which is what makes
this mechanical rather than a guess.

Rules:

- **Match by family and role, not by name similarity.** `PropertyName` is not
  unique — 130 names are shared by 263 properties with different CRCs, and
  `temple/` vs `12temple/` is a re-authored copy with identical names and
  different CRCs.
- **Preserve position, roll and height bias** unless the replacement's footprint
  differs enough to intersect something.
- **A prop with no counterpart is a decision, not an error.** Either drop it and
  say so, or keep it and say so. Do not substitute something unrelated.
- **Never invent a CRC** (rule 2).

## Texture remap by role

Do not map texture-to-texture by index. Map by **role**: the source's `base`
becomes the target's `base`, `cliff` to `cliff`, and so on. The snow textureset
family in the corpus is exactly this — a mechanical motif substitution that
keeps slot count and UV scales and only changes the art folder.

## Verify against the target, not the source

Render previews and compare the statistics to the **target** archetype: base
share, run length, object density, block fraction. A reskin that keeps the
source's density reads as the old biome wearing new textures.

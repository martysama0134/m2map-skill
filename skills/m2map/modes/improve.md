# improve — change an existing map

Point at a map, describe the change, get it done. The two decisions that matter
are **which stage owns the change** and **whether to write bytes or emit a
WorldEditor script**.

## 1. Which stage owns it?

The pipeline is re-entrant, so a change re-runs from the owning stage downward
rather than regenerating the map.

| The user says | Stage | What re-runs |
|---|---|---|
| "widen the road", "move the road", "add a path to the lake" | 2 layout | 2→8 |
| "flatten this area", "make the hills higher", "too steep" | 3 terrain | 3→8 |
| "the river is too shallow", "add a lake" | 4 water | 4→8 |
| "ground looks blotchy/bare", "more sand near the water" | 5 texture | 5, 8 |
| "add undergrowth", "too many trees", "the north sector is empty" | 6 objects | 6, 7, 8 |
| "players get stuck here", "let them walk up this slope" | 7 attr | 7, 8 |
| "change the fog", "make it darker" | 8 finish | 8 |

**Objects always drag attr with them.** Footprints are an input to collision, so
re-running placement without re-running attr leaves blockers where the old props
were and nothing under the new ones.

## 2. Bytes or a WorldEditor script?

| Prefer bytes when | Prefer a WE script when |
|---|---|
| Bulk and mechanical (retexture, mass delete, whole-sector) | Small, positional, judgement-laden |
| The map has no hand edits worth preserving | The user wants to *see* it and undo it |
| Running headless | The editor is already open on this map |
| Thousands of records | A few dozen |

Ask if it is genuinely ambiguous. Emitting a script the user did not want costs
them a manual step; rewriting bytes they wanted to review costs them their work.

**Never run the script.** Emit it, say what it does, hand it over (rule 16).

## 3. Preserve what you did not touch

The codecs replay the parsed source byte-for-byte until the semantic model
diverges, so **reading a file and writing it back changes nothing**. Edit only
the records or fields you mean to. Do not rebuild a container from scratch to
change one field — that discards the original float formatting and produces a
diff touching every line.

If the map has a `mapspec.yaml` beside it, the honest edit is a **spec diff**:
change the spec, re-run the owning stage, and the change is reproducible and
reviewable. Say so when you do it.

If it has no spec (a hand-authored or shipped map), work on the files directly
and say that the change is not reproducible from a seed.

## 4. Sector-scoped edits cross their borders

`tile.raw` is stored 258×258 with a 1-tile skirt mirroring the neighbour, and
`height.raw` shares its border vertices. Re-running a stage for a subset of
sectors must also update the adjacent border rows and columns, or a seam appears
at the join. The whole-map grids in the pipeline do this by construction; a
hand-rolled per-sector edit does not.

## 5. Verify the change, not the map

Render previews before and after, and look at both. The question is not "is this
a valid map" but "did the thing the user asked for actually happen, and did
anything else move".

Then audit. Report:

- what changed, in the user's terms
- which stages re-ran
- whether it is a spec diff or a direct edit
- anything you deliberately left alone

## Common requests, and the trap in each

**"The north sector is empty."** Usually true and usually intentional in the
spec's region masks. Check whether a density is zero there before adding scatter
the archetype would not have.

**"Players fall through the floor."** That is an audit finding, not an improve
request. Run audit first — it is almost always missing `attr.atr`, a stale
`server_attr`, or `server_attr` carrying paint bits (rule 5).

**"Make the road wider."** Change `RoadSpec.width_m` and re-run from layout.
Editing `tile.raw` directly paints a wider stripe but leaves the terrain
flattening, the object clearance and the attr corridor at the old width.

**"Add more variety to the ground."** Almost never means more textures. It means
the slot weights are too concentrated — the corpus median base share is 0.52,
and a map using 7 slots with one at 0.8 reads as bare.

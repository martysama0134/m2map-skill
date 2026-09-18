# register — save a group of objects as a reusable pattern

Someone hands over a compound — a camp, a yard, a town square — and wants it
available to every later map as `setpieces: [{pattern: <name>, ...}]`. This is
how the eight encampments and the b1 town square in `reference/setpieces/` were
made, in the order it was done. Rule 25 is why it exists: a compound is copied
whole, never assembled from statistics.

Load `reference/setpieces/README.md` first. It has the file format, the turning
rule and the ground block; this file is the procedure.

## What arrives

| Input | How to read it |
|---|---|
| **`areadata.txt` text pasted from the editor** (starts `AreaDataFile`, `Start Object000` …) | a hand selection. Save it verbatim to a scratch file; it IS the group. Go to step 1 |
| **A map, a point and a radius** ("b1, around (638, 638), 60 m") | `setpiece.py <map> x y r`. A disc takes whatever is inside it, so look for a clipped neighbour and name it out with `--exclude` (the b1 square at 60 m cut a walled estate in half). Skip step 1 |
| **A scratch map holding only the group** | its `areadata.txt` is the selection. Step 1 does not apply — there is no corpus to check against |
| A label with a direction ("looking at north", "opens west") | the **facing**. Keep it; it goes in the notes (step 4) |
| Minimap crops with arrows | orientation hints only. Do not read objects off them |

Ask for nothing else up front. The name, the pivot and the ground can all be
decided from the data.

## 1. Check the paste against the map it came from

```
python -m m2map.gen.setpiece --from-areadata picked.txt \
    --verify-against <CORPUS>/<map> --source-map <map> --name tmp
```

- **`exact match`** — go on. Seven of the eight pastes so far were.
- **`left out by the author`** — records the map holds inside the same box that
  the paste does not. They are a choice, not an error: on `c1_camp_east` they
  were two stray fence panels and a Pagoda. Read them, keep them out, and say so
  in the notes.
- **`NOT ON THE MAP`** (exit 1) — a pasted record with no twin. Wrong map, a
  typo, or an edited selection. Stop and ask; do not save a pattern whose source
  cannot be rendered.

Then rule 2, as always: every CRC must be in `catalog/objects.json`. A pattern
with an unregistered CRC stamps objects that vanish at load.

## 2. Look at the ground before choosing what to keep

Print the texture histogram and an ASCII map of the window (extent + 8 m). The
feature is whatever is **solid under the group and absent round it**, and it is
not the same texture twice:

| Source | The feature | `--ground-keep` |
|---|---|---|
| c1 encampments | `field 01` core, `field 04` halo 4–8 m wide, a spur to the road | `field` |
| b1 town square | the same dirt apron, plus the `tile01` safezone disc | `field`, `tile` |
| desert camps (4 of 6) | a **solid `sand02` floor** — dither noise everywhere else on that map — with grass under the palms | `sand02`, `grass`, `field` |
| desert village | grass under each tent group, bare sand between | same |
| large desert ring | no floor; a web of `field 01` tracks | same |

Never keep the map's own base ground (`grass 01` in a meadow, `sand01` in a
desert): the window's square edge shows wherever the target's ground differs.

## 3. Render the source

```
--map <CORPUS>/<map> --target <pivot_x*100>,<pivot_y*100> --cam 55,0,<dist>
```

`dist` 8000 for a 45 m camp, 13000–14000 for an 80 m one, 16000 for the town.
Look at it **before writing the notes** — the notes describe what is there, and
a description written from the CRC list alone got one camp's layout wrong.
Keep the PNG (`ref_<name>.png`); step 6 compares against it.

## 4. Save

```
python -m m2map.gen.setpiece --from-areadata picked.txt --source-map <map> \
    --ground-from <CORPUS>/<map> --ground-keep <feature> [--ground-keep ...] \
    --name <name> --notes "..." --save reference/setpieces/<name>.json
```

- **Name**: `<where>_<what>[_<facing>]` — `c1_camp_north`, `desert_camp_west2`,
  `b1_town_square`. It is the `pattern:` key, so it is forever.
- **Pivot**: the centroid, unless the compound has a real centre a `PlazaSpec`
  must land on (the town's safezone disc) — then `--pivot centre` on that point.
- **Notes** carry, in this order: who selected it and how many records; **the
  facing in words and degrees** (`OPENS WEST (facing 270)`); what is in it, from
  the render; what the floor is; anything left out in step 1; and the turning
  rule with the number filled in: `rotate_deg = (270 - B) mod 360`.

## 5. Build a check sheet

One flat map per biome, every new pattern stamped once, **plus one copy turned
by 90** whose expected facing you work out beforehand
(`facing' = facing − rotate_deg`). Palette = a base, a road slot, and every
texture the patterns' grounds need declared at `weight: 0.0`. No scatter.
`D:/map_setpiece_check` and `_desert` are the two that exist; rebuild them
rather than starting a third.

The build log must show `ground: <label> painted N tiles` for each with **no
`! … no slot for` line** — that line means the ground was skipped.

Install the check map's textureset under the data dir before rendering
(`we-api.md` — a missing one renders untextured and leaves a stub).

## 6. Render the copies from the source camera, and compare

Same `--cam`, target = anchor × 100. Open source and copy side by side. They
should be indistinguishable apart from the surrounding terrain; the turned copy
should open the way you predicted, fences on the far side, track leaving through
the gap. If the rails have come apart the handedness is wrong — that is
`failure-atlas.md` §3.10 and the render is the only check that sees it at 90°.

## 7. Write it down

- a row in the table of `reference/setpieces/README.md`, and a paragraph if the
  pattern does something the others do not (a different floor, a facing, a pad
  bigger than its extent);
- a row in `modes/generate.md` "features beyond scatter" so generate mode finds it;
- a line in the archetype doc the source map belongs to;
- anything the ground taught about a texture goes in that archetype doc too —
  the `sand02` floor was found this way.

Then `python tools/sync.py` and `bash tests/run-all.sh`.

## Hand over

Per pattern: records, size, facing, floor. What matched and what was left out in
step 1. Where the source and copy renders are. Which textures a map must declare
to get the ground. Commit only when asked.

## Refusals worth making

- **A pasted record that is not on the named map.** Ask which map; do not guess.
- **A group with an unregistered CRC.** Say which; offer to register the pattern
  without it, never with it.
- **"Make me a camp like this one."** That is generate mode with a pattern, not a
  new pattern — pick the nearest registered one and turn it.

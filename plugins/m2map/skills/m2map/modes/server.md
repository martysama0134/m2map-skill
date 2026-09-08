# server — spawns and registration

The server-side files: `regen.txt`, `npc.txt`, `boss.txt`, `stone.txt`,
`Town.txt`, the `index` entry, `dungeon.txt`, and `monsterareainfo.txt`.

## Coordinates are not centimetres here

<EXTREMELY-IMPORTANT>
Regen and Town coordinates are in **units of 100** — metres, i.e. half-cell
counts. The server multiplies by 100 and adds `BasePosition`. Meanwhile
`areadata` is in centimetres, map-local, with Y negated. That is three
conventions in one map, and mixing them puts spawns a hundred times too far out.
</EXTREMELY-IMPORTANT>

The server also parses these with its own character-level tokenizer
(`regen.cpp`), not the client's, so comment and quoting rules differ per file.
See `reference/mapformat/server-regen.md`.

## Placing spawns

Spawn zones must be **walkable**. Cross-check every zone against `attr.atr`: a
zone whose cells are blocked spawns monsters inside terrain, where they are
unreachable and often unkillable.

Use the map's regions where it has a spec — settlement areas are where NPCs go,
clearings and open field are where monsters go, and the road corridor is usually
kept clear so players can travel it.

`monsterarrange.txt` is a deduplicated vnum list derived from the regen files.
Nothing in the engine or the server reads it; it is a content-pipeline aid.
Generate it from the spawns rather than hand-maintaining it.

## Boundary with m2dev

`m2map` owns the **placement** of spawns — where in the map, on what ground, at
what density. It does not own mob definitions, drop tables or quest wiring; that
is the `m2dev` skill's territory. If the user needs a new mob vnum, say so and
point there rather than inventing an entry.

## Verify

- every spawn zone lies on walkable ground
- no zone extends past `MapSize`
- referenced vnums exist, or are flagged as needing definition
- the `index` entry matches the map folder name exactly

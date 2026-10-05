# audit — find what will break in game

Read-only. Never writes. Reports symptom-first, because "players fall through
the floor near the bridge" is how a fault is actually reported.

```
python scripts/audit_map.py <map dir> [--severity major]
```

## Severity means something

| | Meaning |
|---|---|
| `blocker` | Map does not load, or is unplayable: no collision anywhere, every cell impassable, a sector silently dropped |
| `major` | Visible, reproducible fault: invisible objects, walk-through walls, error texture |
| `minor` | Wrong but survivable: dead sector folders, unaligned base position |
| `info` | Worth knowing and **not a defect** — shipped Ymir maps do this too |

<EXTREMELY-IMPORTANT>
Do not report `info` findings as problems. 46% of adjacent sector pairs in
official maps disagree on their tile skirt, 452 of 1343 sectors carry water
below the terrain, and no client-side map ships `server_attr`. A checker that
calls those errors reports 142 broken official maps and teaches the user to
ignore it.
</EXTREMELY-IMPORTANT>

## Resolve before judging

Stage 0 runs first. 26 of 142 maps have **no sector folders at all** — they
carry a `ParentMapName` and reuse the parent's terrain — and three have no
`setting.txt`. Sector-scope rules run against the resolved terrain root. Pass
`--corpus` so the parent can be found; without it a proxy map looks empty.

## Reading a finding

Each carries symptom, cause, location, and the smallest correct fix. Lead with
the symptom when reporting, then the cause. `M2MAP-ATR-004` is not "server_attr
has values above 7" — it is "every cell of the map is impassable on the server",
*because* server_attr carries paint bits.

## Quality: was this map ever finished?

`M2MAP-QA-*` (`scripts/m2map/audit/quality.py`) flag a map that loads and plays
but that nobody finished -- the worst cases a curator wants found on a mapper's
map before upgrading it. Each threshold sits well past the worst official map,
so QA-001, -002 and -004 fire on 0 of the 116 corpus maps with terrain
and QA-003 on 3 official roads of 146:

| Rule | Flags | Official maps |
|---|---|---|
| QA-001 major | steep (>= 25 deg) stone/rock/cliff paint you can walk on, > 30% | median 0.6%, worst 15% |
| QA-002 major | a map with no attr: < 2% blocked | at least 8.6%, p5 44% |
| QA-003 minor | a road with an undithered, ruler-cut edge: < 2 loose rim tiles per 100 m | p5 7.1 -- but 3 of 146 official roads are hard-edged too, so it is a flag, not a fault |
| QA-004 minor | an open map edge > 64 m: no mountain, no wall of tall buildings (a castle's curtain wall counts), no water horizon | 0 m; an entrance (the S-shaped kind too) <= 32 m; unpainted void is not an edge |

Report them as "this map looks unfinished here", with the sectors the finding
names, and offer `improve` for the fix. QA-003 especially: say it may be a style.

## Judgement the tool cannot make

The rules catch mechanical faults. These need you to look:

- **Aesthetic failures.** Uniform splatting, lattice object placement, a road
  that goes nowhere. Render previews and look at them.
- **Design failures.** A map with no route through it, a settlement with no
  approach, spawn zones inside blocked terrain.
- **Intent.** An empty sector may be a bug or a deliberate clearing. Say which
  you think it is and why, rather than asserting.

## When the user asked for a fix

Audit is read-only by contract. Report, then offer `improve`. Do not silently
repair — the user may want to know how it broke, especially if a tool of theirs
produced it.

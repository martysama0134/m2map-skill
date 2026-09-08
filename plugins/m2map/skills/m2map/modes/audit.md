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

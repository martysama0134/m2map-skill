# `areaambiencedata.txt` — Ambient Sound Placement

Per-sectree ambient sound emitters. Same container syntax as [areadata-txt.md](areadata-txt.md), different record fields.

- **Path:** `<map>/<XXXYYY>/areaambiencedata.txt`
- **Source:** read `CArea::__Load_LoadAmbience` (`GameLib/Area.cpp:892-965`), write `CAreaAccessor::__SaveAmbiences` (`WorldEditor/DataCtrl/MapAccessorArea.cpp:1111-1160`)

## Structure

```
AreaAmbienceDataFile

Start Object000
    <x> <y> <z>         float, world position (cm, y negated — same as areadata)
    <CRC>               uint, ambience property CRC (.pra)
    <range>             uint, audible radius (cm); 0 disables
    <maxVolumeAreaPct>  float 0..1, optional — inner full-volume radius fraction
End Object
...

ObjectCount <N>
```

| Index | Field | Parsed with | Required |
|---|---|---|---|
| 0–2 | position | `atof` | yes |
| 3 | property CRC | `atoi` | yes — must be a registered property (the loader checks registration only, not type; by convention always an Ambience `.pra`) |
| 4 | range | `atoi` | **yes** (read unconditionally) |
| 5 | max volume area % | `atof` | optional (old files have 5 tokens; the current writer always emits 6) |

Play behavior (`ONCE`/`STEP`/`LOOP`), interval, and the actual `.wav` list come from the referenced `.pra` property, not from this file.

## Real example (map_a2 `000000`, verbatim — empty case)

```
AreaAmbienceDataFile


ObjectCount 0
```

A populated record:

```
Start Object000
    12800.000000 -12800.000000 9940.000000
    2293772605
    5000
    0.300000
End Object
```

→ waterfall loop at sector center, audible within 50 m, full volume within the inner 30 %.

## Pitfalls

- No rotation/height-bias fields — token 4 is *range* here, not rotation. Mixing up the two area file schemas corrupts records silently.
- Records whose CRC isn't a registered ambience property are dropped on load.

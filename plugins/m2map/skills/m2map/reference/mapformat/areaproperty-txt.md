# `areaproperty.txt` — Sectree Property

Per-sectree descriptor. Its existence with a valid `ScriptType` is what tells the engine "this sector exists" — `LoadTerrain` only proceeds to `height.raw`/`tile.raw`/etc. after this file parses (`GameLib/MapOutdoorLoad.cpp:206-289`).

- **Path:** `<map>/<XXXYYY>/areaproperty.txt`
- **Source:** read `MapOutdoorLoad.cpp:206-234`, write `CTerrainAccessor::SaveProperty` (`WorldEditor/DataCtrl/MapAccessorTerrain.cpp:997-1019`)

## Keys

| Key | Tokens | Required | Meaning |
|---|---|---|---|
| `ScriptType` | `AreaProperty` | **yes** | File type tag; wrong value = sector skipped |
| `AreaName` | quoted string | **yes** (may be `""`) | Editor display name for the sector |
| `NumWater` | uint | no | Water layer count — **written by the editor, never read back** (the live count comes from `water.wtr`'s header) |

## Canonical file (map_a2 `000000`, verbatim, 56 bytes)

```
ScriptType AreaProperty

AreaName ""

NumWater 1

```

## Pitfalls

- Deleting this file effectively deletes the sector from the map even if all binaries are present.
- Keep `NumWater` matching `water.wtr` for tidiness, but don't trust it when reading — parse the wtr header.

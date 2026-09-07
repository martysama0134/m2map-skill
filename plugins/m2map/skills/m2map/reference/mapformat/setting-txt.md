# `setting.txt` — Map Root Settings

Master per-map configuration: dimensions, world origin, scale factors, texture set and environment references. Read by client, WorldEditor **and** server (which uses 3 keys of it — see [server-map-files.md](server-map-files.md)).

- **Path:** `<map>/setting.txt` client-side; the **server opens `Setting.txt`** (capital S, `sectree_manager.cpp:759`) — on case-sensitive server filesystems (FreeBSD/Linux) the server copy must use that exact name
- **Encoding:** plain text; keys case-insensitive; tokens separated by spaces/tabs (writer uses tabs); blank lines ignored
- **Source:** read `CMapOutdoor::LoadSetting` (`GameLib/MapOutdoorLoad.cpp:291-492`), write `CMapOutdoorAccessor::SaveSetting` (`WorldEditor/DataCtrl/MapAccessorOutdoor.cpp:117-204`)

## Keys

| Key | Tokens | Required | Meaning |
|---|---|---|---|
| `ScriptType` | `MapSetting` | **yes** | File type tag; loader rejects other values |
| `CellScale` | int | **yes** | Cell size in world units. The **client** ignores the value (uses the compile-time constant 200), but the **server** multiplies map dimensions by it (`sectree_manager.cpp:262,276`) — any value other than `200` desyncs server geometry. Write `200` |
| `HeightScale` | float | **yes** | Raw-height → world-Z multiplier. WorldEditor hard-codes `0.500000` on save |
| `ViewRadius` | int | **yes** | Render distance basis; editor writes `128` (WorldEditor build doubles it internally on load) |
| `MapSize` | int int | **yes** | Sectree count X, Y. Valid range 1..256 per axis (`MAX_MAPSIZE`) — enforced by the editor; the client loader doesn't actually reject out-of-range values (`SetTerrainCount`'s check result is ignored, `MapOutdoorLoad.cpp:398`) |
| `TextureSet` | path | **yes** | TextureSet file; loader prefixes `textureset\` if not already present |
| `BasePosition` | int int | no | Global world origin of this map in world units (cm). Must be a multiple of 25,600 to align client sectrees (and thus of 6,400 for server sectors) |
| `Environment` | name | no | `.msenv` file; resolved as `<mapdir>\<name>` then `d:/ymir work/environment/<name>` |
| `TerrainVisible` | 0/1 | no | Default 1; editor writes it only when 0 |

(`EncryptionSet`, `SpecialWaterPath`, `SpecialWaterCount` exist behind optional compile flags in modified clients — not part of the vanilla format.)

## Canonical file (map_a2, verbatim)

```
ScriptType	MapSetting

CellScale	200
HeightScale	0.500000

ViewRadius	128

MapSize	6	6
BasePosition	256000	665600
TextureSet	textureset\metin2_A2.txt
Environment	A2.msenv
```

6×6 sectrees → world span 6 × 25,600 = 153,600 units (1,536 m) per axis, origin at (256000, 665600).

## Writer normalization

Round-tripping through the WorldEditor rewrites `CellScale 200`, `HeightScale 0.500000`, `ViewRadius 128` from constants regardless of loaded values — treat those three as fixed.

## JS parsing

Split lines, split tokens on `/[ \t]+/`, lowercase the first token as key. Quoted tokens (`"..."`) keep inner spaces (not used in this file, but the shared tokenizer supports it).

## Pitfalls

- `MapSize` order is X then Y (columns, rows).
- All six required keys must exist or the client rejects the map.
- `BasePosition` ties into `atlasinfo.txt` client-side and regen/town coordinate math server-side — changing it moves the map in the world and invalidates absolute references.

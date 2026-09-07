# `water.wtr` — Water Layer Map

Per-sectree water definition: which cells have water and at what heights. Supports up to 255 independent water planes ("layers") per sector.

- **Path:** `<map>/<XXXYYY>/water.wtr`
- **Size:** **16,391 + 4·N bytes** (N = layer count; legacy files: 16,391 + 2·N)
- **Source:** `CTerrainImpl::LoadWaterMapFile` (`PRTerrainLib/Terrain.cpp:201-296`), `SaveWaterMap` (`WorldEditor/DataCtrl/MapAccessorTerrain.cpp:1230-1264`)

## Layout

| Offset | Type | Value | Meaning |
|---|---|---|---|
| 0 | `uint16` LE | **5426** (`0x1532`) | Magic. Only accepted value |
| 2 | `uint16` LE | **128** | Width — must equal 128 |
| 4 | `uint16` LE | **128** | Height — must equal 128 |
| 6 | `uint8` | N | Layer count (`m_byNumWater`, 0–255) |
| 7 | `uint8[16384]` | — | Water layer index per cell, row-major 128×128. **`0xFF` = no water**; else index into height array |
| 16391 | `int32[N]` LE | — | Raw water height per layer (**current format**) |
| 16391 | `uint16[N]` LE | — | Raw water height per layer (**legacy format**) |

The loader distinguishes current vs legacy purely by remaining file size: `rest == 16384 + 4·N` → int32 heights; `rest == 16384 + 2·N` → uint16 heights (`Terrain.cpp:259-292`). The WorldEditor always **writes** the 4-byte variant.

**Engine bug in the legacy path:** after converting the WORD heights, the loader falls through and unconditionally re-copies `4·N` bytes from the same offset (`Terrain.cpp:286-292`), overwriting the converted values with misread data whenever `N > 0`. Legacy files are *recognized* but load with corrupt heights in this engine — treat the 2-byte layout as read-detect-and-convert territory for tools, and always write the 4-byte form.

## Semantics

- Water grid is at **heightmap cell resolution**: 128×128, one water cell = one terrain cell = **200×200 world units** (2 m).
- Height values are in **raw height units**, same scale as `height.raw`: `worldZ = value * HeightScale` (0.5 by default). Water plane render: `z = height * HeightScale` (`GameLib/AreaTerrain.cpp:1086`); `GetWaterHeight` returns `value / 2` (`AreaTerrain.cpp:529`).
- Layers exist so one sector can hold ponds at different elevations. Editor caps at 255 distinct heights (`MAX_WATER_NUM = 255`, `MapAccessorTerrain.cpp:340-343`).
- Missing/corrupt file is **non-fatal**: engine fills the map with `0xFF`, N=0.
- Painting water also stamps `ATTRIBUTE_WATER` (0x02) into the 2×2 corresponding cells of `attr.atr` — keep both in sync.

## JS parsing

```js
const buf = await file.arrayBuffer();
const dv = new DataView(buf);
if (dv.getUint16(0, true) !== 5426) throw new Error("bad water.wtr magic");
const w = dv.getUint16(2, true), h = dv.getUint16(4, true);
if (w !== 128 || h !== 128) throw new Error("bad water.wtr dims");
const numLayers = dv.getUint8(6);
const cells = new Uint8Array(buf, 7, 128 * 128);            // 0xFF = dry
const rest = buf.byteLength - 7 - 128 * 128;
if (rest !== numLayers * 4 && rest !== numLayers * 2)
  throw new Error("bad water.wtr size");
const heights = [];
for (let i = 0; i < numLayers; i++) {
  heights.push(rest === numLayers * 4
    ? dv.getInt32(7 + 16384 + i * 4, true)        // current
    : dv.getUint16(7 + 16384 + i * 2, true));     // legacy
}
const worldZ = (i) => heights[i] * 0.5;
```

## Pitfalls

- Layer indices in the cell grid must be `< N` or `0xFF`; anything else indexes garbage heights.
- Height array element size differs between old and current files — never assume 4 bytes without the size check.
- No border padding (like attr.atr).

## Validation (map_a2)

`D:\map_a2\000000\water.wtr` = 16,395 bytes = 7 + 16384 + 4 → 1 layer, raw height 19880 (`A8 4D 00 00`) → worldZ 9,940. Header `32 15 80 00 80 00 01` = magic 5426, 128×128, N=1 ✓. Desert map sectors: 16,391 bytes → N=0 ✓.

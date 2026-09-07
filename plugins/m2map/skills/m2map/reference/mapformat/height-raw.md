# `height.raw` — Terrain Heightmap

Per-sectree raw heightmap. Defines the terrain elevation for one 128×128-cell sector.

- **Path:** `<map>/<XXXYYY>/height.raw` (see [README](README.md) for sectree folder naming)
- **Size:** always **34,322 bytes** = 131 × 131 × 2
- **Layout:** headerless, row-major grid of `uint16` (little-endian)
- **Source:** `CTerrainImpl::LoadHeightMap` (`PRTerrainLib/Terrain.cpp:69-86`), `CTerrainAccessor::SaveHeightMap` (`WorldEditor/DataCtrl/MapAccessorTerrain.cpp:1041-1053`)

## Layout

| Offset | Type | Count | Meaning |
|---|---|---|---|
| 0 | `uint16[131*131]` | 17,161 | Height samples, row-major (`row * 131 + col`) |

There is no header, no magic, no version. The engine does a blind `memcpy` of exactly `131*131*2` bytes and performs **no size validation** on load.

## Why 131×131?

A sector is 128×128 terrain cells, so its vertex grid is 129×129 (`HEIGHTMAP_XSIZE = XSIZE+1`). The stored grid is padded by one extra sample on **every** side: `HEIGHTMAP_RAW_XSIZE = XSIZE+3 = 131`. Logical vertex `(sx, sy)` with `sx, sy ∈ [-1, 129]` maps to:

```
value = raw[(sy + 1) * 131 + (sx + 1)]
```

(`CTerrainImpl::GetHeightMapValue`, `Terrain.h:139-142`). The 1-sample skirt duplicates the neighboring sectors' edge values so normals and patch meshes blend seamlessly across sector borders. **When editing, the skirt must be kept in sync with neighbor sectors** — the WorldEditor writes shared edge vertices into all adjacent sectors' rawmaps.

## Height → world conversion

```
worldZ = rawValue * HeightScale        // HeightScale from map setting.txt
```

- `HeightScale` is read from `setting.txt` but the WorldEditor **hard-codes `0.5` on save** (`MapAccessorOutdoor.cpp:156`), so in practice `worldZ = rawValue / 2` (world units = cm).
- Blank/new maps are filled with `0x7FFF` (32767) → worldZ ≈ 16383 (`NewHeightMap`, `MapAccessorTerrain.cpp:1031-1033`).
- Value range: 0..65535 → world 0..32767.5 cm with the default scale.
- In-game height at an arbitrary point is bilinear across the cell's two triangles, split on the diagonal by `xdist <= ydist` (`CTerrain::GetHeight`, `GameLib/AreaTerrain.cpp:369-430`).

## Grid scale

- 1 cell = `CELLSCALE` = **200 world units** (2 m; 100 units = 1 m).
- Sector edge = 128 cells × 200 = **25,600 units** (256 m).

## JS parsing

```js
const buf = await file.arrayBuffer();            // 34322 bytes
if (buf.byteLength !== 131 * 131 * 2) throw new Error("bad height.raw size");
const heights = new Uint16Array(buf);            // fine: file is little-endian
// vertex (sx, sy), sx/sy in [-1, 129]:
const h = heights[(sy + 1) * 131 + (sx + 1)];
const worldZ = h * 0.5;
```

`Uint16Array` over the raw buffer works because the format is little-endian and byte offset 0 is aligned; use `DataView.getUint16(off, true)` if slicing at odd offsets.

## Pitfalls

- Row-major with X advancing fastest; Y row 0 is the **north** (top) edge as rendered by the WorldEditor/minimap.
- Don't forget the +1 skirt offset — indexing `[sy*131+sx]` without the shift misreads the whole grid by one row/column.
- No validation on load: a wrong-size file silently corrupts terrain (reads garbage). Validate the 34,322-byte size in tools.
- Editing edge vertices without mirroring into neighbor sectors produces visible seams/cracks in-game.

## Validation (map_a2)

`D:\map_a2\000000\height.raw` = 34,322 bytes ✓. First sample `0xAE4B` = 44619 → worldZ 22309.5.

# `tile.raw` — Texture Tile Map

Per-sectree ground-texture index map. Each byte selects which TextureSet texture covers one tile; the engine turns this into alpha-blended splat layers at load.

- **Path:** `<map>/<XXXYYY>/tile.raw`
- **Size:** always **66,564 bytes** = 258 × 258
- **Layout:** headerless, row-major grid of `uint8`
- **Source:** `CTerrainImpl::RAW_LoadTileMap` (`PRTerrainLib/Terrain.cpp:161-179`), `RAW_SaveTileMap` (`WorldEditor/DataCtrl/MapAccessorTerrain.cpp:1073-1089`)

## Layout

| Offset | Type | Count | Meaning |
|---|---|---|---|
| 0 | `uint8[258*258]` | 66,564 | Texture index per tile, row-major (`row * 258 + col`) |

No header, no version. Loader does a blind `memcpy` of 66,564 bytes, no size validation.

## Resolution & border

- Tile grid is **2× the heightmap cell grid**: 256×256 tiles per sector (`TILEMAP_XSIZE = XSIZE*2`), so one tile = **100×100 world units** (1 m).
- Stored grid is 258×258 (`TILEMAP_RAW_XSIZE = 256+2`): a **1-tile border on every edge** duplicating neighbor sectors' edge tiles. Needed because splat alpha generation samples all 8 neighbors of each tile — the border lets edge tiles blend seamlessly across sector boundaries.
- Logical tile `(tx, ty)` with `tx, ty ∈ [-1, 256]` → `raw[(ty + 1) * 258 + (tx + 1)]`.

## Byte semantics

- Value = **index into the map's TextureSet** (see [client-global-refs.md](client-global-refs.md)): `1..255` = texture slots, matching `Texture001..` blocks.
- **`0` = blank/eraser** — never splatted. All splat loops start at index 1 (`GameLib/AreaTerrain.cpp:557,656`); the editor's erase brush writes 0.
- Max distinct textures: TextureSet holds 256 slots total = 255 usable + eraser (`MAXTERRAINTEXTURES = 256`).

## Splat generation (how the client renders it)

`CTerrain::RAW_GenerateSplat` (`AreaTerrain.cpp:646-768`): for each used texture index `i > 0`, builds a 258×258 alpha map: `0xFF` where `tile == i`; where `tile > i`, also `0xFF` if **any of the 8 neighbors** equals `i` (1-texel bleed across borders); else `0x00`. The 258-wide alpha is box-downsampled to a 256×256 mip-chained `A8R8G8B8` texture (`AddTexture32`, `AreaTerrain.cpp:770-897`). Higher index paints over lower — painter's order = texture index order. A 2D editor can reproduce the look by drawing layers bottom-up with those alphas, or simply color per-tile by top index.

## JS parsing

```js
const tiles = new Uint8Array(await file.arrayBuffer()); // 66564 bytes
if (tiles.length !== 258 * 258) throw new Error("bad tile.raw size");
const idx = (tx, ty) => tiles[(ty + 1) * 258 + (tx + 1)]; // tx,ty in [-1,256]
```

## Pitfalls

- Same +1 border-shift trap as `height.raw` — inner grid starts at offset `[1][1]`.
- Painting a tile at a sector edge requires mirroring into the adjacent sector's border row/column (the WorldEditor does this automatically).
- Indices above the TextureSet's `TextureCount` render as error texture; keep tile values ≤ count.

## Validation (map_a2)

`D:\map_a2\000000\tile.raw` = 66,564 bytes ✓.

# `minimap.dds` — Per-Sectree Minimap Tile

Top-down snapshot of one sector, rendered by the WorldEditor. The client shows it in the in-game minimap; atlas images for the world map are composited from these tiles.

- **Path:** `<map>/<XXXYYY>/minimap.dds`
- **Format:** standard DDS — `"DDS "` magic + 124-byte header + pixels
- **Typical encoding:** uncompressed **X8R8G8B8, 256×256, no mips** → **262,272 bytes** (map_a2 verified). Other tools may have written 16-bit or compressed variants (e.g. 32,896 bytes = 128×128×16bpp) — parse the header.
- **Source:** save `SaveMiniMapFromD3DTexture9` (`WorldEditor/DataCtrl/MapAccessorTerrain.cpp:1413-1461`); load `CTerrain::LoadMiniMapTexture` (`GameLib/AreaTerrain.cpp:70-86`)

## Generation

Rendered by `CMiniMapRenderHelper` (`MiniMapRenderHelper.cpp`): 256×256 X8R8G8B8 render target, orthographic top-down projection covering exactly the sector's **25,600 × 25,600 world units**, camera centered at `((coordX*2+1)*12800, -(coordY*2+1)*12800)` (Y negated, matching the render-space Y flip; `MiniMapRenderHelper.cpp:70`). Saved via `D3DXSaveSurfaceToFile(..., D3DXIFF_DDS, ...)`. Old `minimap.bmp` is deleted first.

So: 1 minimap texel = 100 world units = 1 attr cell (at 256×256).

## Atlas

`CMapManagerAccessor::SaveAtlas` (`MapManagerAccessor.cpp:1742-1876`) composites all sectors' `minimap.dds` into `<map>_atlas.bmp|png` (256 px/tile) and `<map>_MAI_atlas` (1024 px/tile). Atlases live outside the map folder and are not needed to load the map.

## JS parsing

Minimal DDS reader for the common case:

```js
const dv = new DataView(buf);
if (dv.getUint32(0, true) !== 0x20534444) throw new Error("not DDS"); // "DDS "
const height = dv.getUint32(12, true);
const width  = dv.getUint32(16, true);
const pfFlags = dv.getUint32(80, true);   // 0x40 = uncompressed RGB
const bpp     = dv.getUint32(88, true);   // 32
const rMask   = dv.getUint32(92, true);   // 0x00FF0000 for X8R8G8B8
// pixel data starts at 128 for uncompressed, row-major top-down
```

For an editor, treating minimap tiles as read-only display images (and regenerating them elsewhere) is the pragmatic choice — generating them requires rendering the 3D scene.

## Pitfalls

- Missing file is non-fatal (client shows nothing for that tile).
- Don't hardcode 262,272 bytes; header-driven parsing handles the in-the-wild variants.
- X8R8G8B8 byte order in memory is BGRA per pixel (little-endian) — swap for canvas `ImageData` (RGBA).

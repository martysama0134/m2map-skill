# Metin2 Map Format Specification

Complete file-format documentation for Metin2 maps (modern "40k-era" format — the one every current client/server uses). Extracted from the WorldEditorRemix C++ sources (client `GameLib`/`PRTerrainLib` loaders + WorldEditor savers), the m2dev server sources (`sectree_manager.cpp`, `regen.cpp`), cross-checked against the decompiled Map-Converter v1.4 and byte-verified against official map files (`map_a2`, `metin2_map_n_desert_01`, …).

All multi-byte binary values are **little-endian**. All world distances are in **world units = centimeters** (100 units = 1 m) unless stated.

## Map anatomy

```
metin2_map_xyz/
├── setting.txt              map size, origin, scales, textureset+env refs   → setting-txt.md
├── mapproperty.txt          map type tag (client-only)                      → mapproperty-txt.md
├── server_attr              server collision grid (server-only)             → server-attr.md
├── regen.txt  npc.txt
│   boss.txt  stone.txt      spawn definitions (server; WE writes regen.txt) → server-regen.md
├── Town.txt                 spawn points (server-only)                      → server-map-files.md
├── monsterarrange.txt       used-vnum list (pipeline aid, read by nothing)
└── 000000/ 000001/ … XXXYYY/    one folder per sectree (name = x·1000+y, see below)
    ├── areaproperty.txt     sector marker + name                            → areaproperty-txt.md
    ├── height.raw           heightmap 131×131 uint16                        → height-raw.md
    ├── tile.raw             texture indices 258×258 bytes                   → tile-raw.md
    ├── attr.atr             client attributes 256×256 bytes                 → attr-atr.md
    ├── water.wtr            water layers 128×128 + heights                  → water-wtr.md
    ├── shadowmap.raw/.dds   baked shadows 256×256                           → shadowmap.md
    ├── minimap.dds          minimap tile 256×256                            → minimap-dds.md
    ├── areadata.txt         object placements (CRC refs)                    → areadata-txt.md
    └── areaambiencedata.txt ambient sounds                                  → areaambiencedata-txt.md
```

External references (a map is not self-contained): `textureset/*.txt`, `environment/*.msenv`, `property/**` — see [client-global-refs.md](client-global-refs.md). Server map registration (`index`, `Town.txt`, `dungeon.txt`) — see [server-map-files.md](server-map-files.md).

Old-beta maps (e.g. `metin2_map_c1`) have only 5 files per sectree (no areadata/ambience/shadowmap/minimap) — the loaders treat all of those as optional/non-fatal, so the modern spec covers them as a superset.

## Sectree naming

Folder name = `printf("%06u", x * 1000 + y)` — first 3 digits X (column), last 3 Y (row). `001000` = (x=1, y=0); `000001` = (x=0, y=1). Grid dims come from `setting.txt` `MapSize`.

## The three grids

Everything hangs off one sectree = **128×128 terrain cells**, 1 cell = **200 units** (2 m), sector edge = **25,600 units** (256 m):

| Grid | Per sectree | Cell size | Used by |
|---|---|---|---|
| Terrain cells | 128×128 (129×129 vertices, stored 131×131) | 200 | height.raw, water.wtr |
| Half-cells | 256×256 | 100 (1 m) | tile.raw (stored 258×258), attr.atr, shadowmap, minimap texels |
| Server cells | 512×512 (as 4×4 sub-sectors of 128×128) | 50 | server_attr |

Server sector = 6,400 units (64 m) → 4×4 server sectors per client sectree.

## Coordinate conventions

- World origin of a map = `setting.txt` `BasePosition` (multiple of 25,600). Client files use **map-local** coordinates; server adds the base.
- `areadata`/`areaambiencedata` store `y` **negated** (`stored_y = -terrain_y`); plot top-down at `(x, -y)`.
- Regen/Town coordinates are in **units of 100 (= meters = half-cell counts)**; server multiplies by 100 and adds the base.
- Heights: `world_z = raw_uint16 * HeightScale` with `HeightScale = 0.5` in practice.
- Row 0 of every grid file is the north edge; X grows east, Y grows south.

## Limits

| Limit | Value | Source |
|---|---|---|
| Map size | 1..256 × 1..256 sectrees (≈ 65.5 km side max; editor-enforced, client load doesn't validate) | `MAX_MAPSIZE 256`, `MapOutdoor.h:22` |
| Terrain textures | 255 + eraser slot 0 | `MAXTERRAINTEXTURES 256` |
| Water layers per sectree | 255 (index 0xFF = none) | `MAX_WATER_NUM 255` |
| Attribute flags | 8 bits/cell client, 32 bits/cell server | `Terrain.h`, `sectree.h` |
| Sectrees loaded at once (client) | 3×3 window | `AROUND_AREA_NUM` |
| Raw height range | 0..65535 → 0..32,767.5 cm | uint16 × 0.5 |

## Per-sectree file sizes (fixed)

| File | Bytes | Formula |
|---|---|---|
| height.raw | 34,322 | 131² × 2 |
| tile.raw | 66,564 | 258² |
| attr.atr | 65,542 | 6 + 256² |
| water.wtr | 16,391 + 4·N | 7 + 128² + 4·layers |
| shadowmap.raw | 131,072 | 256² × 2 |
| shadowmap.dds / minimap.dds | 262,272 typical | 128 + 256²×4 (X8R8G8B8; parse header) |

`server_attr` (map root): 8 + Σ(4 + compressed) over `(4·MapSizeX)·(4·MapSizeY)` LZO blocks.

## Text-file grammar (client-side, shared)

All **client** map text files use the same tokenizer (`EterBase/FileLoader.cpp`): lines split on `\r`/`\n`/`\r\n`; tokens split on runs of spaces/tabs; `"quoted"` tokens keep spaces; keys are case-insensitive (lowercased); blank lines skipped. `setting/mapproperty/areaproperty/areadata/areaambiencedata` additionally use the `Start <name> … End` block form, which **flattens every token between the markers into one positional array** (`EterLib/Util.cpp:51-111`). The `.msenv` and property/group files use the other front-end: `Group <name> { … }` / `List <name> { … }` nesting.

The **server** parses its files with separate, simpler code: regen files use a character-level tokenizer (`regen.cpp:27-78`), `Setting.txt`/`Town.txt`/`index`/`dungeon.txt` use `fgets`+`sscanf`. Comment and quoting rules therefore differ per file — see the individual docs.

## Doc index

| Doc | Covers |
|---|---|
| [setting-txt.md](setting-txt.md) | Map root settings |
| [mapproperty-txt.md](mapproperty-txt.md) | Map type tag |
| [height-raw.md](height-raw.md) | Heightmap |
| [tile-raw.md](tile-raw.md) | Texture tile map + splatting |
| [attr-atr.md](attr-atr.md) | Client attributes + flag values |
| [water-wtr.md](water-wtr.md) | Water layers |
| [shadowmap.md](shadowmap.md) | shadowmap.raw + .dds |
| [minimap-dds.md](minimap-dds.md) | Minimap tiles + atlas |
| [areaproperty-txt.md](areaproperty-txt.md) | Sector marker |
| [areadata-txt.md](areadata-txt.md) | Object placement records |
| [areaambiencedata-txt.md](areaambiencedata-txt.md) | Ambient sound records |
| [server-attr.md](server-attr.md) | Server collision binary (LZO) |
| [server-regen.md](server-regen.md) | regen/npc/boss/stone grammar |
| [server-map-files.md](server-map-files.md) | index, Setting/Town/dungeon server view |
| [client-global-refs.md](client-global-refs.md) | TextureSet, .msenv, property DB |

## Notes for a JS implementation

- Binary files: `DataView` with `littleEndian = true`; `Uint16Array`/`Uint8Array` views work directly on aligned offsets.
- `server_attr` needs an LZO1X codec (minilzo-compatible), not zlib.
- CRCs are unsigned 32-bit — `parseInt(s) >>> 0`.
- Validate the fixed file sizes above before parsing; the C++ loaders range-check magics/dims but height/tile/shadow raws are blind memcpys.
- DDS files in the wild vary (uncompressed X8R8G8B8, DXT1/3/5, 16-bit) — parse headers, don't assume.

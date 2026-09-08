# `attr.atr` — Client Attribute Map

Per-sectree gameplay attribute grid (collision, water, PK-ban) used by the client. The server uses its own aggregate file ([server-attr.md](server-attr.md)), generated from these.

- **Path:** `<map>/<XXXYYY>/attr.atr`
- **Size:** always **65,542 bytes** = 6-byte header + 256 × 256
- **Source:** `CTerrainImpl::LoadAttrMap` (`PRTerrainLib/Terrain.cpp:106-155`), `SaveAttrMap` (`WorldEditor/DataCtrl/MapAccessorTerrain.cpp:1091-1114`)

## Layout

| Offset | Type | Value | Meaning |
|---|---|---|---|
| 0 | `uint16` LE | **2634** (`0x0A4A`) | Magic. Loader rejects anything else |
| 2 | `uint16` LE | **256** | Width — must equal 256 exactly |
| 4 | `uint16` LE | **256** | Height — must equal 256 exactly |
| 6 | `uint8[65536]` | — | Attribute flags per cell, row-major (`row * 256 + col`) |

Payload must be exactly 65,536 bytes after the header or the loader rejects the file. **No other versions exist** — one magic, fixed dims.

## Flags

From `PRTerrainLib/Terrain.h:68-72`:

| Bit | Hex | Name | Meaning |
|---|---|---|---|
| 0 | `0x01` | `ATTRIBUTE_BLOCK` | Movement blocked (collision) |
| 1 | `0x02` | `ATTRIBUTE_WATER` | Water surface present |
| 2 | `0x04` | `ATTRIBUTE_BANPK` | PK (player-kill) forbidden zone |

Bits 3–7 have **no engine meaning** client-side (the WorldEditor overlay can display them, nothing consumes them). Server-side, bit 7 (`0x80`, `ATTR_OBJECT`) marks object-derived collision, but that flag lives in `server_attr`, not here. `MAX_ATTRIBUTE_NUM = 8` = usable bit count.

### Official maps use the high bits as paint layers

Ymir's own maps carry byte values way beyond `0x07` — map_a2's first sector is full of `0xC9`. These are editor "terrain kind" paint conventions layered on top of the engine flags; community tools (Map-Converter) decode the low nibble as the kind and the `0x40`/`0xC0` high bits as ground-vs-mountain:

| Byte | Meaning (convention) | Engine sees |
|---|---|---|
| `0x40` (64) | Land, walkable | nothing (bits 0–2 clear) |
| `0x41` (65) | Building footprint, blocked | `BLOCK` |
| `0x44` (68) | Safezone, walkable | `BANPK` |
| `0xC8` (200) | Mountain, walkable | nothing |
| `0xC9` (201) | Mountain, blocked | `BLOCK` |
| `0xCB` (203) | Water on mountain, blocked | `BLOCK`+`WATER` |
| `0xCA` (202) | Bridge, walkable | `WATER` |
| `0xCC` (204) | Safezone on mountain | `BANPK` |

The "engine sees" column is the client view (bits 0–2). Bits 3–7 are editor paint conventions with no client meaning. **Preserve the full byte when editing `attr.atr`** — a rewrite that drops values loses information the editor's overlay depends on.

> **ERRATUM (m2map, 2026-09-08).** An earlier revision of this paragraph said server_attr generation copies the **full byte** (`ServerAttrGenerator.cpp:109-138`) and concluded that the `0xC0`-family paints "also encode server collision". The editor source does do that; Ymir's shipped `server_attr` files do not, and following the source bricks the map.
>
> `0xC8` is mountain **walkable** and `0xC9` is mountain **blocked** — bit 0 already carries the collision, bit 7 only marks "mountain". Since the server blocks on `ATTR_BLOCK|ATTR_OBJECT` (`0x01|0x80`), an unmasked copy turns every walkable mountain cell into a blocker. Measured on `map_a2`: verbatim blocks 9,437,184 of 9,437,184 cells vs the shipped 6,246,724, which `& 0x07` reproduces exactly.
>
> **Preserve the full byte in `attr.atr`; mask to `& 0x07` when generating `server_attr`.** See [server-attr.md](server-attr.md) and audit rule `M2MAP-ATR-004`.

## Resolution

- 256×256 attribute cells per sector = **2× heightmap cell resolution** → one attr cell = **100×100 world units** (1 m), 2×2 attr cells per terrain cell.
- Water brushes stamp `ATTRIBUTE_WATER` into the 2×2 attr block covering each 128-grid water cell (`MapAccessorTerrain.cpp:393-397`).
- Client lookup: `m_abyAttrMap[y * 256 + x]` (`GameLib/AreaTerrain.cpp:483-505`); collision checks `ATTRIBUTE_BLOCK`.

## JS parsing

```js
const buf = await file.arrayBuffer();
const dv = new DataView(buf);
if (dv.getUint16(0, true) !== 2634) throw new Error("bad attr.atr magic");
const w = dv.getUint16(2, true), h = dv.getUint16(4, true); // both 256
if (w !== 256 || h !== 256 || buf.byteLength !== 6 + w * h)
  throw new Error("bad attr.atr dims");
const attr = new Uint8Array(buf, 6);
const isBlocked = (x, y) => (attr[y * 256 + x] & 0x01) !== 0;
```

## Pitfalls

- Unlike height/tile there is **no border padding** — grid is exactly the sector's 256×256 cells, no ±1 skirt.
- Never strip the high bits of `attr.atr` "for cleanliness" — bits 3–7 carry the paint conventions above and the editor overlay reads them. (Do strip them on the way into `server_attr`: mask `& 0x07`. See the erratum above.)
- Keep `ATTRIBUTE_WATER` consistent with `water.wtr` — the client trusts the flag, the renderer trusts the watermap; desync = invisible water collision or dry "water".

## Validation (map_a2)

`D:\map_a2\000000\attr.atr` = 65,542 bytes, header `4A 0A 00 01 00 01` = magic 2634, 256×256 ✓.

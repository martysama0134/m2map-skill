# Mental Model — how a Metin2 map is actually put together

Read this before touching a map. It deprograms the assumptions a modern
heightmap/terrain-tool background brings, which are wrong here in specific and
expensive ways.

Ground truth for every byte layout is `mapformat/` next to this file. This
document is the shape of the thing, not the spec.

---

## 1. A map is not self-contained

A map folder holds geometry and references. It does **not** hold its own art.

```
metin2_map_foo/
  setting.txt        -> names a textureset and an environment, both external
  000000/ .. XXXYYY/
    tile.raw         -> stores INDICES into that external textureset
    areadata.txt     -> stores CRC NUMBERS into the external property database
```

So a map that looks fine on your disk renders as error-texture and missing
objects on someone else's client if the textureset, the `.msenv` or the
property files did not travel with it. Three external dependencies, all
resolved by name or number, none validated at load:

| Reference | Lives in | Failure when missing |
|---|---|---|
| `TextureSet` | `textureset/<name>.txt` | terrain renders the error texture |
| `Environment` | `<map>/` then `d:/ymir work/environment/` | falls back by last-2-chars of map name |
| Property CRCs | `property/**/*.pr*` | object is **silently dropped** at load |

That last one is the cruel case: an unregistered CRC produces no error, no log,
no placeholder. The object simply is not there. Any tool that writes
`areadata.txt` must validate CRCs against the property DB, because the engine
will not.

## 2. Three grids, not one

Everything hangs off one sectree = **128×128 terrain cells**. One cell is
**200 units**, a sector edge is **25,600 units** (256 m). But different files
sample that same square at three different resolutions:

| Grid | Per sector | Cell size | Files |
|---|---|---|---|
| Terrain cells | 128×128 (129×129 vertices, **stored 131×131**) | 200 | `height.raw`, `water.wtr` |
| Half-cells | 256×256 | 100 (1 m) | `tile.raw` (**stored 258×258**), `attr.atr`, shadowmap, minimap |
| Server cells | 512×512 (as 4×4 sub-sectors of 128×128) | 50 | `server_attr` |

The stored dimensions exceed the logical ones (131 vs 129, 258 vs 256). That
padding is not decoration — writing a 129×129 height array produces a 34,062-byte
file where 34,322 is required, and the loader `memcpy`s blindly. **Validate the
fixed sizes before parsing and after writing:**

| File | Bytes | Formula |
|---|---|---|
| `height.raw` | 34,322 | 131² × 2 |
| `tile.raw` | 66,564 | 258² |
| `attr.atr` | 65,542 | 6 + 256² |
| `water.wtr` | 16,391 + 4·N | 7 + 128² + 4·layers |
| `shadowmap.raw` | 131,072 | 256² × 2 |

## 3. Units are centimetres, and Y is negated

- All world distances are **centimetres**. 100 units = 1 m. A tree 1,450 units
  tall is 14.5 m.
- `world_z = raw_uint16 × HeightScale`, and `HeightScale` is 0.5 in every real
  map. So the raw range 0..65535 maps to 0..32,767.5 cm.
- Client map files use **map-local** coordinates. The server adds
  `BasePosition` from `setting.txt`.
- **`areadata.txt` and `areaambiencedata.txt` store Y negated**
  (`stored_y = -terrain_y`). Every real file has negative Y. Plot top-down at
  `(x, -y)`. Getting this wrong mirrors your entire object layer about the X
  axis, which looks plausible enough to ship and is completely wrong.
- Regen and Town coordinates are in **units of 100** (metres / half-cell
  counts), not centimetres. The server multiplies by 100 and adds the base.
  Two different coordinate conventions in one map — do not mix them.
- Row 0 of every grid file is the **north** edge. X grows east, Y grows south.

## 4. Sector naming is arithmetic, not a path

Folder name = `printf("%06u", x * 1000 + y)`. First three digits are X (column),
last three are Y (row).

```
000000 = (0,0)    001000 = (1,0)    000001 = (0,1)    003004 = (3,4)
```

Grid dimensions come from `MapSize` in `setting.txt`. A folder that does not
match the declared `MapSize` is not loaded and produces no warning.

## 5. The text format has one very sharp edge

Client map text files share a tokenizer with a `Start <name> … End` block form.
That form **flattens every token between the markers into one positional
array**. Line breaks inside a block are cosmetic. Fields are addressed **by
index**, never by name.

```
Start Object000
    10892.386719 -18171.355469 17784.789062     <- indices 0,1,2  position
    26807040                                    <- index 3        property CRC
    0.000000#0.000000#120.000000                <- index 4        yaw#pitch#roll
    -35.000000                                  <- index 5        height bias
End Object
```

Consequences that bite:

- Records may legally have **4, 5, 6 or more** tokens. Four is position+CRC.
  This is the format's implicit versioning; old files simply have fewer fields.
  A parser that requires six drops valid data.
- Rotation is written as `%f` but **read by the engine with `atoi`** — it is
  truncated to integer degrees. There is also a parsing defect that drops the
  character before the first `#`. Harmless for `120.000000`; destroys bare
  integer forms (`90#0#0` yields yaw 9). **Always write the `%f` form.**
- Keys are case-insensitive and lowercased. `End Object`'s trailing word is
  ignored — only `End` matters.

`.msenv` and the property files use a *different* front end: `Group <name> { … }`
and `List <name> { … }` nesting. Two grammars, one codebase.

## 6. Slot 0 is the eraser

`TextureCount` in a textureset **excludes** slot 0, which is the built-in
eraser. Blocks are named `Texture001..TextureNNN`, 1-based, `%03d`. A `tile.raw`
byte of 0 means blank, not "first texture".

Cap is 256 slots, so 255 usable textures. Merging two maps whose texturesets
union past 255 is unrepresentable, which is why merge has to remap indices
rather than concatenate.

## 7. Property files are a binary header wrapping text

```
offset 0   "YPRT"                 FourCC, validated
offset 4   \r\n                   mandatory
offset 6   text body, \r\n-terminated lines
           line 0: the CRC, decimal ASCII
           then:   <key>\t\t"<value>"     lowercased keys, alphabetical
```

The CRC on line 0 is **read verbatim and never recomputed** from the filename or
path. It is generated once at save time and is the identity of the asset
forever. `property/reserve` lists retired CRCs that must never be reissued.

The `PropertyType` **value inside the file** drives parsing — not the file
extension. Do not trust the extension.

Five types: `Building` (`.prb`, `.gr2`, collision derived as the same path with
`.mdatr`), `Tree` (`.prt`, `.spt`, plus `TreeSize`/`TreeVariance`), `Effect`
(`.pre`, `.mse`), `DungeonBlock` (`.prd`, `.gr2`), `Ambience` (`.pra`, wav
vector). Ambience records live in `areaambiencedata.txt`, **not** `areadata.txt`.

## 8. Two sources of truth for collision

`attr.atr` is the client's 8-bit-per-half-cell attribute grid. `server_attr` is
the server's, at 2× the resolution, LZO1X-compressed. They are generated from
each other, and they can drift.

When they disagree, the player experiences it as the two classic bugs: walking
through a wall the client draws, or being stopped by nothing the client draws.
Any tool that edits `attr.atr` must regenerate `server_attr`, and any audit must
check that the 2×2 upsample relationship still holds.

Client flags: `0x01` block, `0x02` water, `0x04` safezone, `0x08` banshop, then
four more. The server uses 32 bits per cell.

## 9. Optional means optional

The loaders treat `areadata.txt`, `areaambiencedata.txt`, `shadowmap` and
`minimap` as optional and non-fatal, so **"file missing" is not an error
condition by itself**. A reader that requires all ten files is wrong.

But do not expect to meet a five-file sector: **there are no beta-era maps in
the corpus.** All 1,343 sector folders carry the full modern ten-file set — the
vendored spec's claim that `metin2_map_c1` is a five-file beta map is false, and
`ls` on `metin2_map_c1/000000/` returns all ten. The real partial sectors are
three specific exceptions: `boss_awaken_skipia` and `boss_crack_skipia` each
have one sector holding only `attr.atr` (a collision override), and
`smhdungeon_02`'s sectors have no `minimap.dds`.

The shape you *will* meet instead is the **proxy map**: 26 of 142 maps have no
sector folders at all, shipping only `setting.txt` + `mapproperty.txt` with a
`ParentMapName` and reusing the parent's terrain. Three of those
(`metin2_guild_village_01/02/03`) have no `setting.txt` either — only
`mapproperty.txt`. Any tool that assumes a map owns terrain breaks on 18% of the
corpus. See `corpus-overview.md`.

## 10. What the client loads at once

Three sectors by three. `ViewRadius` in `setting.txt` and the 3×3 window mean a
map is streamed, not loaded whole. Sector-border continuity therefore matters
visually — a height mismatch at a shared edge shows as a seam the player walks
across — but the engine does not enforce it, and real Ymir maps carry a
measurable, non-zero amount of it.

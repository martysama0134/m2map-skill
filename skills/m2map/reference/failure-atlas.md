# Metin2 Map Failure Atlas

Every known way a generated, merged or reskinned map breaks — organised **symptom → cause → detection → fix**, because the symptom is what you get handed ("the map loads but everything's black").

Three sources, all cited inline:

1. **MapForge's merge implementation** (`<MAPFORGE>/index.html:810-1140`) — battle-tested against real maps; every guard in it encodes a failure someone hit. Section 2 documents its algorithms in full.
2. **The format spec** (`reference/mapformat/*.md`) — all 16 Pitfalls sections consolidated.
3. **The corpus** — 142 official Ymir/GF maps in `<CORPUS>`, 1,343 sector folders, cross-referenced against the 2,112-entry property DB and 177 texturesets in `<CLIENT_PACK>`. Every "measured" number below came out of a scan of that corpus.

Machine-readable rule list: [`catalog/audit-rules.json`](catalog/audit-rules.json). Rule ids (`M2MAP-XXX-NNN`) are the join key between the two files.

---

## 0. Corpus baseline — what "normal" actually looks like

Before flagging anything, know what ships. Measured over all 142 maps:

| Fact | Measured |
|---|---|
| Maps / sector folders | 142 / 1,343 |
| Maps with **zero** sector folders | **26** (`metin2_map_battlearena01..03`, `boss_awaken_*`, `boss_crack_*`, `smhgate_*`, `e1_01..03`, `monkey_dungeon_11..13`, `otherworld_03/04`, `golden_land`, `guild_village_01..03`) — contain only `mapproperty.txt` (± `setting.txt`) |
| Maps with **no `setting.txt`** | 3 (`metin2_guild_village_01/02/03` — `mapproperty.txt` only) |
| Maps shipping `server_attr` | **0 of 142** — it is server-side only, never in a client pack |
| Most common sector file set | 10 files, 1,176 sectors (areaproperty, height.raw, tile.raw, attr.atr, water.wtr, areadata.txt, areaambiencedata.txt, shadowmap.raw, shadowmap.dds, minimap.dds) |
| Smallest *working* sector set | 7 files, 5 sectors (`metin2_map_devilscatacomb/000007` — no shadowmap, no minimap) |
| Degenerate sectors | 2 (`metin2_map_boss_awaken_skipia/000000`, `metin2_map_boss_crack_skipia/000000`) contain **only `attr.atr`** |
| `shadowmap.raw` size | 131,072 in **1,336 / 1,336** — 100 % conformance |
| Water layers per sector | 0 in 848, 1 in 320, 2 in 100, 3 in 38, … max **17** |
| Highest tile index seen | **37**; 232 sectors top out at index 1 |
| Distinct `attr.atr` byte values | 36, max **205**: {0–9, 12, 13, 16, 17, 48–51, 64, 68, 69, 80, 81, 83, 112, 113, 115, 192–195, 200–205} |
| areadata records | 48,851 total. Token counts: 6 → 48,156; 7 → 686; 8 → 9. **Never fewer than 6** |
| areadata property types | Building 22,871 · Tree 14,239 · Effect 8,121 · DungeonBlock 3,332 · Ambience **0** |
| areaambiencedata records | 28, all exactly 6 tokens |
| regen lines (all 4 files, all maps) | 1,073 — types `r` 668, `g` 361, `m` 44; **all 11 columns**; 0 bare-digit times; 0 group point-spawn traps |
| `Environment` refs unresolved | **0 of 142** (121 `.msenv` in the pack) |

**Files in shipped sectors that the spec does not document** (`M2MAP-SEC-002`) — a strict "unknown file" check will false-positive on all of these:

| File | Sectors | Note |
|---|---|---|
| `minimap_top/bottom/left/right/lefttop/righttop/leftbottom/rightbottom.dds` | ~70 (all `metin2_map_eastplain_0*`) | edge-blend minimap tiles for a multi-map world-map seam |
| `height.tga` | 39 (`metin2_map_b1`, …) | editor-side heightmap export, unread by the engine |
| `contents.obv` | 29 (`metin2_map_elemental_0*`) | unknown; not opened by any loader in the spec |

---

## 1. The atlas

Severity key: **BLOCKER** = map or sector will not load · **MAJOR** = loads but is visibly/functionally broken · **MINOR** = cosmetic or latent · **INFO** = occurs in shipped data, report but do not fail.

---

### A. "The map doesn't load at all"

#### A1 — Client refuses the map / falls back to the login screen · `M2MAP-SET-001` · BLOCKER

**Cause.** One of the six required `setting.txt` keys is missing (`ScriptType MapSetting`, `CellScale`, `HeightScale`, `ViewRadius`, `MapSize`, `TextureSet`), or `ScriptType` is not literally `MapSetting`. `CMapOutdoor::LoadSetting` (`MapOutdoorLoad.cpp:291-492`) rejects the map.

**Detection.** Parse `setting.txt` with the shared tokenizer (split lines on `\r`/`\n`, tokens on `/[ \t]+/`, lowercase key). Fail if any of the six keys is absent or if `scripttype[0].toLowerCase() !== "mapsetting"`.

**Fix.** Emit all six. The WorldEditor normalises three of them from constants on every save — write `CellScale 200`, `HeightScale 0.500000`, `ViewRadius 128` verbatim (`MapAccessorOutdoor.cpp:117-204`).

**Corpus.** 3 maps ship with no `setting.txt` at all (`metin2_guild_village_01/02/03`). They are stubs, not playable maps — the audit should report them as such rather than as a format error.

---

#### A2 — Server aborts *all* map loading, not just the broken one · `M2MAP-SRV-001` · BLOCKER

**Cause.** `SECTREE_MANAGER::Build` returns failure the moment any map listed in `index` is missing `Setting.txt` or `Town.txt` (`sectree_manager.cpp:764-778`). One bad map takes down the whole boot pass.

**Detection.** For every line of `<MapPath>/index` (`<int> <folder>`, `//`/`#` comments), assert the map folder contains a file named exactly `Setting.txt` **and** exactly `Town.txt`. Compare with `os.listdir` byte-for-byte, not case-insensitively — the server is usually on FreeBSD/Linux.

**Fix.** Ship `Setting.txt` (capital S) and `Town.txt` (capital T) alongside the lowercase `server_attr`, `regen.txt`, `npc.txt`, `boss.txt`, `stone.txt`, `dungeon.txt`. A Windows-authored map that works locally will fail on the live server for exactly this reason.

---

#### A3 — Sector silently missing from the world · `M2MAP-SEC-001` · BLOCKER (per sector)

**Cause.** `areaproperty.txt` absent or its `ScriptType` isn't `AreaProperty`. `LoadTerrain` (`MapOutdoorLoad.cpp:206-289`) never reaches `height.raw`/`tile.raw` — the folder's binaries are ignored entirely. Deleting one file deletes the sector.

**Detection.** For every folder matching `^\d{6}$`, require `areaproperty.txt` with `ScriptType AreaProperty`.

**Corpus.** 2 sector folders violate this: `metin2_map_boss_awaken_skipia/000000` and `metin2_map_boss_crack_skipia/000000` contain **only** `attr.atr`. Both maps declare `MapSize 6 6` — so 36 sectors are claimed and 0 actually load.

---

#### A4 — Whole sector loads as garbage terrain · `M2MAP-HGT-001` / `M2MAP-TIL-001` · BLOCKER

**Cause.** `height.raw` or `tile.raw` is not exactly the fixed size. Both loaders are **blind `memcpy`s with no size validation** (`Terrain.cpp:69-86`, `161-179`) — a short file reads past the buffer, a long one is truncated mid-row.

**Detection.** Byte-exact sizes: `height.raw` = 34,322 (131²×2); `tile.raw` = 66,564 (258²); `attr.atr` = 65,542 (6+256²); `shadowmap.raw` = 131,072 (256²×2, this one *is* validated on load and rejected otherwise).

**Corpus.** One violation in 1,343 sectors: `gm_guild_build/000000/tile.raw` is **66,567 bytes** — 3 trailing bytes past the grid. The engine's blind `memcpy(66564)` ignores them, so the map plays fine; any tool that asserts the size (MapForge's `buildSector` returns `null`, blanking the layer) will refuse to render it. Tolerate `>= 66564` on read, always write exactly 66,564.

---

#### A5 — `attr.atr` rejected · `M2MAP-ATR-001` · BLOCKER

**Cause.** Unlike height/tile, `attr.atr` **is** validated: magic must be `2634` (`0x0A4A`), width and height must both be `256`, payload exactly 65,536 bytes (`Terrain.cpp:106-155`). Anything else and the attribute grid is dropped.

**Detection.** `u16le[0]==2634 && u16le[1]==256 && u16le[2]==256 && size==65542`.

**Downstream trap.** MapForge's `attrGrid()` (`index.html:1130`) returns `null` on this check, and `generateServerAttr` then writes attribute `0` for that sector — producing a `server_attr` where an entire client sectree (4×4 = 16 server sectors) has **no collision at all**. A silent size error becomes walk-through-the-world on the server.

---

#### A6 — Server runs with no collision anywhere · `M2MAP-SRV-002` · BLOCKER

**Cause.** `server_attr` missing, or an LZO block that doesn't decompress to exactly 65,536 bytes. `LoadAttribute` bails on the size mismatch, but `Build` **ignores that failure and continues** (`sectree_manager.cpp:789-790`) — the map boots and every wall is walkable.

**Detection.** Walk the file: `int32 W`, `int32 H` at offset 0/4, then `W*H` blocks of `uint32 size` + `size` bytes. Assert (a) `W == MapSizeX*4 && H == MapSizeY*4`, (b) the offset chain lands exactly on EOF, (c) each block decompresses (LZO1X) to 65,536. Iteration is **y-major**: `for y in 0..H-1: for x in 0..W-1`.

**Fix.** Regenerate from the `attr.atr` files. Recipe (`ServerAttrGenerator.cpp:109-160`, and MapForge `generateServerAttr`, `index.html:1136-1165`): for server sector `(sx, sy)`, take client sectree `(sx>>2, sy>>2)`, offset `((sx&3)*64, (sy&3)*64)` into its 256×256 grid, and copy each attr byte **masked to `& 0x07`** into a uint32, upsampled 2×2 into the 128×128 server grid.

> **Mask to 0x07 — do not copy the whole byte.** `ServerAttrGenerator.cpp` and MapForge both copy the full byte, and both are wrong against Ymir's own output. See D2: the whole-byte copy server-blocks the entire map. Verified: `from_attr_maps` with the 0x07 default reproduces `D:/map_a2/server_attr` byte-for-byte across all 576 blocks.

**Corpus.** No map under the corpus dir ships `server_attr` — it is a server-side file, absent from an extracted client, and that absence is expected. Six real ones do exist beside their map folders on `D:/` (`map_a2`, `map_n_snowm_01`, `metin2_map_c1`, `metin2_map_n_flame_01`, `metin2_map_n_snow_dungeon_01`, `metin2_map_privatewar`) and are the ground truth for generation. Its absence in a map you are about to deploy is fatal.

---

#### A7 — Map is bigger (or smaller) than it says · `M2MAP-SET-002` · MAJOR

**Cause.** Sector folders exist outside the `MapSize` rectangle. The client only iterates `0..MapSizeX-1 × 0..MapSizeY-1`, so surplus sectors are dead data; the server derives `worldWidth = CellScale*128*MapSizeX` from the same value, so the two disagree about where the map ends.

**Detection.** `max(sectorX) < MapSizeX && max(sectorY) < MapSizeY`.

**Corpus.** 2 real violations. `metin2_map_devilscatacomb`: `MapSize 7 7` but 54 folders with max `(6, 7)` — a whole `y=7` row is unreachable. `metin2_map_trent02`: `MapSize 3 3` but 16 folders forming a 4×4 grid with max `(3, 3)` — 7 sectors never load.

---

#### A8 — Sparse sector grid · `M2MAP-SET-003` · INFO

**Cause.** Fewer sector folders than `MapSizeX * MapSizeY`. This is **legal and common** — the client just renders nothing there.

**Detection.** `len(sectors) != MapSizeX*MapSizeY`. Report, don't fail.

**Corpus.** 7 maps. `metin2_map_smhgate_a1/b1/c1` declare 4×5=20 and ship 3 sectors each; `metin2_map_smhgate_b1`'s sectors start at `(2,0)` — the grid need not touch the origin. `metin2_map_boss_awaken_skipia`/`boss_crack_skipia` declare 6×6 and ship 1.

**Merge relevance.** MapForge's quadrant layout (`totalW = max(w_TL,w_BL) + max(w_TR,w_BR)`) deliberately produces sparse grids when the four inputs have unequal dimensions. That is fine; do not "fix" it by padding.

---

### B. "The terrain is wrong"

#### B1 — Bright pink / checkerboard "error" ground texture · `M2MAP-TIL-002` · MAJOR

**Cause.** A `tile.raw` byte exceeds the TextureSet's `TextureCount`. The splat generator has no slot for it and D3D falls back to the error texture (`TextureSet.cpp:25-94`; `MAXTERRAINTEXTURES 256`).

**Detection.** Resolve `setting.txt` → `TextureSet` → `textureset/<name>.txt` (the loader prefixes `textureset\` if absent). Parse `TextureCount N`. Then `max(byte) over all 66,564 bytes of every tile.raw <= N`.

**Corpus — this ships broken.** 47 sectors across 5 maps index past their own `TextureCount`:

| Map | TextureSet | Count | Index used |
|---|---|---|---|
| `metin2_12zi_stage` | `metin2_12temple.txt` | 23 | 32 |
| `metin2_guild_village` | `metin2_guild_village.txt` | 6 | 7 |
| `metin2_map_b1` | `metin2_B1.txt` | 17 | 19 |

So the check is real but must be a **warning with a whitelist**, not a hard error, if you audit official maps.

---

#### B2 — Error texture even though the index is in range · `M2MAP-TXS-001` · MAJOR

**Cause.** The TextureSet has a **hole**: `TextureCount` says N but the block `Texture%03d` for some slot ≤ N is missing. The loader fills slots *by block name*, so the slot stays empty and any tile pointing at it renders the error texture (`TextureSet.cpp:25-94`, "Missing `Texture%03d` blocks are skipped").

**Detection.** Parse block names with `/^\s*Start\s+Texture(\d+)\s*$/i` and build the **set of slot numbers**, not a list. Assert `slots ⊇ {1..TextureCount}` and `slots ⊆ {1..TextureCount}`. Then assert every `tile.raw` byte `v` satisfies `v == 0 || v ∈ slots`.

**Corpus — two shipped texturesets have holes, and both are used:**

| TextureSet | `TextureCount` | Blocks present | Hole |
|---|---|---|---|
| `metin2_guild_village.txt` | 6 | Texture002…Texture006 | **slot 1 missing** |
| `metin2_BayBlackSand.txt` | 11 | Texture001, 002, 004…011 | **slot 3 missing** |
| `metin2_map_naga1.txt` | 14 | 15 blocks — **`Texture012` appears twice** | duplicate |

9 sectors of `metin2_map_bayblacksand` paint tile index 3 — which resolves to nothing.

**This is the single most dangerous input for a merge/reskin tool** — see §2.3.

---

#### B3 — `TextureSet` reference doesn't resolve at all · `M2MAP-TXS-002` · BLOCKER

**Cause.** The referenced file is missing, or is not a textureset. Every tile renders as error texture.

**Detection.** Resolve the path (strip directories, match case-insensitively inside `textureset/`), then require the file to contain a `TextureCount` line **and** at least one `Start Texture%03d` block. A file with neither is not a textureset.

**Corpus.** 6 of 177 files in `pack/textureset/textureset/` are not texturesets — `metin2_siege_01/02/03.txt` and their `snow_` twins are pack manifests (`FolderName "pack_map"`, `List ExcludedFolderNameList { … }`). A tool that assumes "it's in `textureset/` so it's a textureset" parses zero entries and remaps every tile to 0.

---

#### B4 — Ground textures tile at obviously wrong scale · `M2MAP-TXS-003` · MINOR

**Cause.** `UScale`/`VScale` in the TextureSet entry. Render scale is `fTerrainTexCoordBase * UScale` with `fTerrainTexCoordBase = 1/(16*200)` (patch size × cellscale). A texture authored for `5.0` dropped into a set that uses `2.0` looks 2.5× too big.

**Detection.** After a merge/reskin union, flag any texture path that appears in the union with **more than one distinct `(UScale, VScale)` pair** across the source sets — dedup collapsed them to one entry and one of the source maps now tiles differently.

**Fix.** MapForge's `parseTextureSet` deliberately keeps each entry's **full body verbatim** (`cur.body.push(...)`) so nothing is lost on write, but its union dedups on path alone (`keyOf = e => e.file.toLowerCase().replace(/\\/g,'/')`). Dedup on `(path, uscale, vscale, uoffset, voffset)` if you care about this; otherwise emit the warning.

---

#### B5 — Untextured black/void patches in the ground · `M2MAP-TIL-003` · MINOR

**Cause.** Tile index `0` = the eraser slot. Splat loops all start at index 1 (`AreaTerrain.cpp:557,656`), so a `0` tile gets no layer painted at all.

**Detection.** Count `tile.raw` bytes == 0 **in the inner grid only** — `raw[(ty+1)*258 + (tx+1)]` for `tx,ty ∈ [0,255]`. Border bytes being 0 is harmless.

**Corpus.** 39 sectors have eraser tiles in the inner grid; `metin2_map_devilscatacomb` has 765 per sector across 8 sectors (indoor catacomb — deliberate). Report as INFO with the count.

---

#### B6 — Visible crack / step at a sector border · `M2MAP-HGT-002` · MAJOR

**Cause.** `height.raw` is 131×131 for a 129×129 vertex grid: a **1-sample skirt on every side** duplicating the neighbour's edge vertices, so normals and patch meshes blend across the seam. Logical vertex `(sx,sy)`, `sx,sy ∈ [-1,129]` → `raw[(sy+1)*131 + (sx+1)]`. Edit one sector's edge without mirroring into the neighbour and you get a crack.

**Detection (E–W pair, sectors A=(x,y) and B=(x+1,y)).**
```
for sy in 0..128:
    assert A[(sy+1)*131 + 129] == B[(sy+1)*131 + 1]
```
(A's logical `sx=128` is B's logical `sx=0`.) N–S is the transpose: `A[130*131 + sx+1] == B[1*131 + sx+1]` for `sx ∈ 0..128`.

**Corpus.** Measured over all 972 E–W adjacent pairs: **934 match exactly, 38 mismatch** — 96 % conformance, so the invariant is real and editor-enforced. Worst offenders: `metin2_guild_war4 000000|001000` (13 of 129 vertices differ), `metin2_map_a3 001003|002003` (7), `metin2_map_b3 000003|001003` (6). Treat a mismatch as MAJOR in generated output, INFO when auditing shipped maps.

---

#### B7 — Texture bleeds wrongly across a sector border · `M2MAP-TIL-004` · INFO

**Cause.** `tile.raw`'s 258×258 grid has the same 1-tile skirt, needed because splat alpha generation samples all 8 neighbours of each tile.

**Detection.** Same shape as B6: `A[(ty+1)*258 + 257] == B[(ty+1)*258 + 1]` for `ty ∈ 0..255`.

**Corpus — do NOT make this an error.** Over the same 972 pairs: **522 match, 450 mismatch** (46 %). The WorldEditor does not reliably mirror tile borders, and the maps look fine. Downgrade to INFO; only the *inner* grid is worth asserting.

---

#### B8 — Whole sector is dead flat · `M2MAP-HGT-003` · INFO

**Cause.** Either intentional (indoor/dungeon floor) or a never-edited sector left at the `NewHeightMap` fill value `0x7FFF` = 32767 → worldZ 16383.5 (`MapAccessorTerrain.cpp:1031-1033`).

**Detection.** `len(set(height.raw)) == 1`. Flag specially if the constant is exactly 32767 (untouched default).

**Corpus.** 101 flat sectors. Constants: 32767 ×35 (the untouched default), 32646 ×35, 32752 ×22, 32614 ×3, 30770 ×2, **0 ×4**.

---

#### B9 — Player falls through the world / spawns at the bottom of the map · `M2MAP-HGT-004` · MAJOR

**Cause.** Raw height 0 → worldZ 0, i.e. absolute floor. Objects and spawns authored at a normal Z (≈16000–20000) hang 160 m in the air over it; anything placed relative to terrain snaps to zero.

**Detection.** `min(height.raw) == 0`. Escalate to MAJOR when the sector is **entirely** zero.

**Corpus.** 96 sectors contain a raw 0. Four are entirely zero: `metin2_map_elemental_01/000002`, `metin2_map_elemental_01/004003`, `metin2_map_elemental_03/004003`, `metin2_map_elemental_03/004004`.

---

#### B10 — Terrain spikes to the sky · `M2MAP-HGT-005` · MINOR

**Cause.** Raw 65535 → worldZ 32,767.5 cm (327 m), the top of the representable range. Usually a brush overflow or an unsigned wrap in a generator.

**Detection.** `max(height.raw) == 65535`, or per-sector range `max-min > 40000` raw (200 m of relief inside one 256 m sector).

**Corpus.** 6 sectors contain 65535 (`metin2_map_mt_thunder/000001`, `/001003`, `metin2_map_smhgate_devils/000001`, `metin2_map_t1/000000`, `metin2_map_whitdragonvalley/000002`, `/002000`). 80 sectors exceed the 40000 range threshold — that one is INFO, not an error.

---

### C. "Water is wrong"

#### C1 — Water renders at the wrong height / a lake floats above the valley · `M2MAP-WTR-001` · MAJOR

**Cause.** Water layer heights are **raw height units**, same scale as `height.raw`: `worldZ = value * HeightScale` (`AreaTerrain.cpp:1086`, `GetWaterHeight` returns `value/2`). Writing centimetres instead of raw units doubles every water plane.

**Detection.** For each layer height `h`: `0 <= h <= 65535`. Sanity-band it against terrain: `min(height.raw) - 4000 <= h <= max(height.raw) + 4000`. A layer far outside its own sector's terrain range is almost certainly unit-confused.

---

#### C2 — Water heights load as garbage · `M2MAP-WTR-002` · BLOCKER

**Cause.** The legacy 2-byte height array. The loader detects current-vs-legacy purely by remaining size (`rest == 16384 + 4N` → int32, `rest == 16384 + 2N` → uint16), but the legacy path has an **engine bug**: after converting the WORDs it falls through and unconditionally re-copies `4·N` bytes from the same offset, overwriting the converted values with misread data whenever `N > 0` (`Terrain.cpp:286-292`). Legacy files are *recognised* and load *wrong*.

**Detection.** `rest = size - 16391`. Flag `rest == 2*N && N > 0`.

**Fix.** Always write the 4-byte form. MapForge's `serializeWater` (`index.html:948`) does exactly this: `7 + 16384 + 4N`, `setInt32(..., true)`.

**Corpus.** 0 legacy files in 142 maps — every shipped `water.wtr` is the 4-byte form. Still write the check; converters produce them.

---

#### C3 — Water plane at a random elevation, or invisible · `M2MAP-WTR-003` · MAJOR

**Cause.** A cell's layer index is `>= NumWater` and not `0xFF`, so it indexes past the height array into whatever follows.

**Detection.** `for c in cells: assert c == 0xFF or c < N`. Plus header: magic `5426`, width `128`, height `128`, `size == 16391 + 4*N`.

**Corpus.** 0 violations. Also: 0 sectors with duplicate layer heights, so the "distinct heights" assumption a global water reindex relies on holds in practice.

---

#### C4 — Player swims through dry ground, or walks on the water surface · `M2MAP-WTR-004` / `M2MAP-ATR-002` · MAJOR

**Cause.** `water.wtr` and the `ATTRIBUTE_WATER` (`0x02`) bit in `attr.atr` disagree. The renderer trusts `water.wtr`; movement/swim logic trusts the attr bit. Painting water in the editor stamps the flag into the 2×2 attr block covering each 128-grid water cell (`MapAccessorTerrain.cpp:393-397`) — but nothing keeps them in sync afterwards.

**Detection — the naive rule is unusable; here is the one that works.**

Naive rule ("every non-`0xFF` water cell must have the attr flag"): fires on **452 of 1,343 sectors**, e.g. `map_a2/000000` reports 443 of 2,283 wet cells unflagged. Useless.

Reason: a water *cell* only means "this cell is inside a water brush footprint". If the layer's height is **below** the terrain at that cell, the water is buried and invisible, and the editor correctly leaves the attr flag clear. The rule must be height-aware:

```
for cy in 0..127, cx in 0..127:
    v = water.cells[cy*128 + cx]
    if v == 0xFF or v >= N: continue
    terrain = height.raw[(cy+1)*131 + (cx+1)]          # water grid == terrain cell grid
    if water.heights[v] > terrain:                      # water is ABOVE ground -> visible
        flagged = any(attr[(cy*2+dy)*256 + (cx*2+dx)] & 0x02
                      for dy in (0,1) for dx in (0,1))  # 2x2 attr cells per water cell
        assert flagged                                  # else: VISIBLE water, no swim flag
```

**Measured, same sectors:**

| Sector | Layers | Cells above terrain | Cells below terrain | Visible-but-unflagged |
|---|---|---|---|---|
| `map_a2/000000` | 1 | 606 | 1,677 | **0** |
| `metin2_map_duel/000000` | 1 | 2,749 | 3,689 | **0** |
| `metin2_map_b3/001002` | 8 | 3,190 | 3,378 | 566 |

The height-aware rule goes to zero false positives on single-layer maps and isolates a genuine multi-layer defect in `metin2_map_b3`.

**The reverse direction** (attr `0x02` set where there is no water cell → the player swims in mid-air / can't run) is rarer and should stay an error: 16 sectors corpus-wide, worst `metin2_map_duel/000000` with 2,611 cells, then `metin2_map_dawnmist_dungeon_01/000002` with 51.

**Fix.** After any water edit, recompute the attr `0x02` bit from the height-aware predicate above, then **OR** it into the existing byte. Do not mask `attr.atr` itself when doing so — this is the client file, and its paint bits must survive. (Distinct from the `server_attr` rule in D2, which masks on the way *out* to the server file.)

---

### D. "Collision is wrong"

#### D1 — Player blocked in open ground / walks through a wall · `M2MAP-ATR-003` · MAJOR

**Cause.** Client and server read different files. The client checks `attr.atr` bit `0x01` (`AreaTerrain.cpp:483-505`); the server checks `server_attr`'s `ATTR_BLOCK|ATTR_OBJECT` (`0x01|0x80`). `server_attr` is a **generated** copy of the attr bytes — stale generation = the two disagree.

**Detection.** Regenerate `server_attr` in memory from the current `attr.atr` files (recipe in A6) and diff against the on-disk file block by block. Any differing block is a stale-generation hit. A cheaper proxy: compare mtimes, `server_attr` must be newer than every `attr.atr`.

**Fix.** Regenerate. MapForge drops `server_attr` on merge (`if(base==='server_attr') continue`, and it's in `skipRoot`) and its status line ends with "regenerate server_attr before use" — follow that rule for any merge or reskin.

---

#### D2 — Entire map is impassable on the server · `M2MAP-ATR-004` · BLOCKER

> Earlier revisions of this entry said the opposite — that masking the high bits causes walk-through buildings, and that you must "never strip" them. That was wrong, and it was wrong in the dangerous direction. Corrected against Ymir's shipped files.

**Cause.** Copying the **whole** `attr.atr` byte into `server_attr` instead of masking to `& 0x07`. The server blocks movement on `ATTR_BLOCK|ATTR_OBJECT` = `0x01|0x80` (`char.cpp:5648`, `char_manager.cpp:290`, `sectree_manager.cpp:823`). Ymir's paint convention puts bit 7 on **walkable** mountain ground, so an unmasked copy marks that ground as an object blocker.

Read the paint values and it is immediate — bit 0 already carries the real collision, bit 7 only says "this is mountain":

| Byte | Meaning | `& 0x07` | Server sees (masked) | Server sees (unmasked) |
|---|---|---|---|---|
| `0x40` | land walkable | `0x00` | walkable ✓ | walkable ✓ |
| `0x41` | building footprint blocked | `0x01` | blocked ✓ | blocked ✓ |
| `0xC8` | **mountain walkable** | `0x00` | walkable ✓ | **blocked ✗** |
| `0xC9` | mountain blocked | `0x01` | blocked ✓ | blocked ✓ |

**Detection.** Regenerate `server_attr` from the current `attr.atr` with the 0x07 mask and diff block-by-block. Generator-side: assert no server DWORD exceeds `0x07`. Corpus check: `to_attr_grid()` of any shipped `server_attr` has `max() <= 0x07`.

**Measured.** On `map_a2` the whole-byte copy blocks 9,437,184 of 9,437,184 server cells; the shipped file blocks 6,246,724, which `mask=0x07` reproduces exactly. **17 corpus maps carry `0x80` on 100% of their cells** (`map_a2`, `map_n_snowm_01`, `map_n_threeway`, `guild_war1/2`, `metin2_map_a3`, `metin2_map_c3`, `guild_01/03`, `monkeydungeon` ×3, `t1`–`t4`, `trent`) — every one of them is bricked outright by the unmasked copy.

**Corpus.** 36 distinct attr byte values, max 205. The `0x80` bit appears **only** in the `0xC0` family (192–195, 200–205) — never as bare `0x80`. Documented meanings: `0x40` land walkable · `0x41` building footprint blocked · `0x44` safezone · `0xC8` mountain walkable · `0xC9` mountain blocked · `0xCA` bridge (water) · `0xCB` water-on-mountain blocked · `0xCC` safezone on mountain.

---

#### D3 — Object visible but has no collision on the server · `M2MAP-PRP-001` · MAJOR

**Cause.** A `Building`/`DungeonBlock` property's collision mesh is the `.gr2` path with the extension swapped to `.mdatr`. If that file doesn't exist, the object renders but nothing derives collision from it.

**Detection.** For every `.prb`/`.prd` in the property DB, read `BuildingFile`/`DungeonBlockFile`, map `d:\ymir work\...` → the extracted art root, and test that `<same path>.mdatr` exists.

**Corpus.** **183 of 400 sampled `.prb` files have no `.mdatr` on disk** (e.g. `D:\ymir work\zone\12temple\12t_12statue_01.mdatr`). Nearly half the building catalogue carries no derived collision — which is why official maps paint the `0xC0`-family bytes into `attr.atr` by hand instead of relying on object collision. **A generator that places buildings and expects collision to appear by itself will produce walk-through buildings.** Paint the attr bytes.

---

### E. "Objects are wrong"

#### E1 — Object simply isn't there · `M2MAP-ARD-001` · MAJOR

**Cause.** The record's CRC isn't registered in the property DB. `CPropertyManager::Get(crc)` misses and the record is **silently dropped** at load (`Area.cpp:498-531`). No log, no placeholder.

**Detection.** Build `{crc → property}` by reading every file under `property/`: require the `"YPRT"` FourCC at offset 0 and `\r\n` at offset 4; the CRC is **line 0 of the body as decimal ASCII** — read it verbatim, never recompute it from the filename. Then assert every areadata token[3] is in that set.

**Corpus.** 2,112 CRCs from 2,605 files (492 are `.gr2`/`.mdatr` art and the `reserve` list sitting inside the property tree — skip anything without the FourCC). One duplicate CRC, `1740984444`, claimed by both `devils_dragon_island/mtthunder_thorn01.prb` and `devils_dragon_island/thing/obj_mtthund_thorn01.prb`; registration is last-one-wins, so which model you get depends on scan order.

---

#### E2 — Strict parser rejects a shipped map's CRC field · `M2MAP-ARD-002` · INFO (but it will crash your tool)

**Cause.** A non-vanilla editor extension: the CRC token carries an appended scale triple.

**Corpus.** All 288 object records in **`metin2_map_treasure_hunt`** look like:
```
Start Object000
    19700.000000 -25400.000000 20302.500000
    142625613#1.000000#1.000000#1.000000
    0.000000#0.000000#0.000000
    0.000000
End Object
```
Token 3 is `<crc>#<scaleX>#<scaleY>#<scaleZ>`. The vanilla engine reads it with `atoi`, which stops at the `#` and gets the right CRC — so the map works in-game. Python `int()` / JS `parseInt` with a radix check will throw or return NaN. All 288 CRCs resolve cleanly after stripping (193 Building, 95 Tree).

**Detection / fix.** Parse the CRC as `atoi` does: `int(re.match(r'-?\d+', tok).group())`, or `parseInt(tok, 10)` in JS (which already truncates at `#`). Preserve the suffix on round-trip if you want to keep the scale.

---

#### E3 — One object per sector silently vanishes · `M2MAP-ARD-003` · MAJOR

**Cause.** `ObjectCount` appears **twice**, or an `Object%03d` block declared by the count doesn't exist. The tokenizer flattens `Start X … End` into one positional array keyed by block name; a missing name means the loop over `0..count-1` finds nothing for that index.

**Detection.**
```
blocks = parse_start_end(text)                    # keys lowercased, "objectcount" is top-level
declared = int(blocks["objectcount"][0])
present  = {k for k in blocks if k.startswith("object") and k != "objectcount"}
assert len(present) == declared
assert all(f"object{i:03d}" in present for i in range(declared))
assert text.lower().count("objectcount") == 1     # catches the duplicate-key case
```
The `k != "objectcount"` exclusion matters — `objectcount` itself starts with `object` and produces a universal off-by-one if you forget it.

**Corpus — shipped corruption.** 7 sectors of **`metin2_map_t1`** (`000000`, `000001`, `001000`, `001001`, `001002`, `002000`, `002002`). The `Start Object000` line was overwritten with `ObjectCount 0`:
```
AreaDataFile


ObjectCount 0
    51590.296875 -64230.015625 19492.724609
    1671224775
    0.000000#0.000000#0.000000
    -55.000000
End Object

ObjectCount 1
```
Object000's tokens leak into the top-level namespace and the file carries two `ObjectCount` keys. Whichever wins, `Object000` never exists — one object is lost per affected sector. In `002002` that is the only object, so the sector loads empty.

---

#### E4 — Objects pop in and out as you walk · `M2MAP-ARD-004` · MINOR

**Cause.** An object is listed in sector A's `areadata.txt` but stands inside sector B. The client only loads a **3×3 sectree window** (`AROUND_AREA_NUM`), so the object exists only while A is inside that window — it appears and disappears at a boundary that has nothing to do with where it stands.

**Detection.** areadata coordinates are **map-local cm**, not sector-local, and **y is stored negated** (`stored_y = -terrain_y`). For sector `(ax, ay)`:
```
assert ax*25600 <= x  <= (ax+1)*25600
assert ay*25600 <= -y <= (ay+1)*25600
```
Report the overshoot distance so you can threshold it.

**Corpus.** 553 records (of 48,851) sit outside their own sector. Median overshoot **5,900 cm**, p90 **79,848 cm**, max **101,801 cm** (four sectors away). Only 114 are within 1,000 cm — the "large building straddling the border" case. 407 are within half a sector. So: overshoot ≤ 1,280 cm (half a sectree) is INFO; beyond that it is a placement bug worth reporting. Worst offenders: `map_n_snowm_01/002005` (y = −127,610 in a sector spanning −128,000…−153,600), `metin2_12zi_stage` (many).

---

#### E5 — Object buried in the ground or floating above it · `M2MAP-ARD-005` · MAJOR

**Cause.** Final Z = `token[2] + token[5]` (position Z plus height bias, both cm). A generator that writes terrain height in **raw units** instead of `raw * HeightScale` buries everything at half depth; one that forgets the bias floats them.

**Detection.** Sample terrain height at the object's `(x, -y)` — bilinear across the cell's two triangles, split on `xdist <= ydist` (`AreaTerrain.cpp:369-430`), or nearest-vertex for an audit — and compare:
```
terrainZ = height.raw[(vy+1)*131 + (vx+1)] * HeightScale
delta    = (z + bias) - terrainZ
```
Flag `|delta| > 2000` cm (20 m) as suspicious, and `|bias| > 2000` cm as a separate signal.

**Corpus.** 120 records carry `|bias| > 2000` cm — legitimately (`metin2_12zi_stage/001003 object002 bias=4987`, `metin2_map_dawnmist_dungeon_01/001000 object023 bias=-3000`). Large biases are how Ymir sinks pillars and raises platforms, so this is a MINOR signal on its own; combine it with the terrain delta before escalating.

---

#### E6 — Object rotated 10× wrong, or not at all · `M2MAP-ARD-006` · MINOR

**Cause.** Token 4 is `yaw#pitch#roll` in degrees, **read with `atoi`** (truncated to integers). Two engine defects compound:
- yaw is extracted with `substr(0, s-1)`, dropping the character immediately before the first `#` (`Area.cpp:850`). Harmless for `%f`-style values (`120.000000` → `120.00000`), **destructive for bare integers**: `90#0#0` → `9#0#0` → yaw 9°.
- A token with no `#` is read as **roll only** (legacy shape), so a bare `90` sets roll, not yaw.

**Detection.** Assert token 4 matches `^-?\d+\.\d{6}#-?\d+\.\d{6}#-?\d+\.\d{6}$`. Flag any token 4 without a `#`.

**Fix.** Always write the three-part `%f` form: `0.000000#0.000000#120.000000`.

**Corpus.** 0 bare-integer rotations in 48,851 records — every shipped record uses the `%f#%f#%f` form. The trap is entirely a generator hazard.

---

#### E7 — Ambient sound at range 0, or an areadata record in the ambience file · `M2MAP-AMB-001` / `M2MAP-ARD-007` · MINOR

**Cause.** The two area files share a container syntax but **not a schema**. In `areadata.txt` token 4 is *rotation*; in `areaambiencedata.txt` token 4 is *range in cm* (read unconditionally, `Area.cpp:892-965`) and token 5 is *maxVolumeAreaPct* (0..1). Swap the files and you get silent emitters and unrotated objects.

**Detection.** In `areaambiencedata.txt`: require `>= 5` tokens, header `AreaAmbienceDataFile`, token 4 an integer `> 0`, and token 3 resolving to a property whose `PropertyType` is `Ambience`. In `areadata.txt`: require `>= 4` tokens (6 in practice) and a property type of Tree/Building/Effect/DungeonBlock.

**Corpus.** 28 ambience records total, all exactly 6 tokens, all resolving to `Ambience` properties. 48,851 areadata records, **zero** of them Ambience-typed. The separation holds in shipped data — enforce it.

---

### F. "Minimap and shadows are wrong"

#### F1 — Minimap tile blank · `M2MAP-MMP-001` · MINOR

**Cause.** `minimap.dds` missing (non-fatal — the client shows nothing for that tile) or in a format your reader doesn't handle.

**Detection.** Presence, then parse the DDS header — **never assume a size**. Magic `"DDS "` at 0, height at 12, width at 16, mipcount at 28, pixel-format flags at 80, FourCC at 84, bpp at 88.

**Corpus — the spec is wrong here and the measurement wins.** `mapformat/minimap-dds.md` and `shadowmap.md` call "uncompressed X8R8G8B8, 256×256, no mips → 262,272 bytes" the typical case. Measured over all 1,332 sectors that ship them:

| File | Size | n | Actual format |
|---|---|---|---|
| `minimap.dds` | 32,896 | **1,270** | DXT1, 256×256, **0 mips** |
| `minimap.dds` | 43,832 | 62 | DXT1, 256×256, 9 mips |
| `shadowmap.dds` | 43,832 | **1,328** | DXT1, 256×256, 9 mips |
| `shadowmap.dds` | 32,896 | 1 | DXT1, 256×256, 0 mips |
| `shadowmap.dds` | 87,536 | 2 | **DXT5**, 256×256, 9 mips |
| `shadowmap.dds` | 262,271 | 1 | uncompressed 24 bpp (`metin2_map_capedragonhead/005003`) |

**Not one file in the corpus is 262,272 bytes.** The pack is essentially all DXT1. A size-based DDS check will reject every official map; a header-based one handles all six variants. (Note 32,896 = 128 header + 32,768 = 8 bytes/block × 4,096 blocks for DXT1 at 256×256.)

**Corpus counts.** 11 sectors have no `minimap.dds`, 11 have no `shadowmap.dds`.

---

#### F2 — Minimap misaligned with the world map · `M2MAP-SET-004` · MAJOR

**Cause.** `BasePosition` disagrees with the client's `atlasinfo.txt` (`mapname baseX baseY sizeX sizeY` per line, `MapManager.cpp:573-611`), or `BasePosition` isn't sectree-aligned. A client sectree is 25,600 units; a server sector is 6,400.

**Detection.**
```
assert baseX % 25600 == 0 and baseY % 25600 == 0     # client sectree alignment
assert baseX %  6400 == 0 and baseY %  6400 == 0     # server sector alignment (implied)
assert atlasinfo[map] == (baseX, baseY, MapSizeX, MapSizeY)
```

**Corpus.** 4 maps are 6,400-aligned but **not** 25,600-aligned: `gm_guild_build` (83,200 → 25600 remainder 6,400), `metin2_map_t2` (6,400), `metin2_map_t3` (32,000), `metin2_map_t4` (57,600). All four are guild/instance maps where the misalignment is tolerated. Emit the 6,400 check as an error and the 25,600 check as a warning.

---

#### F3 — Shadows absent, or terrain shading doesn't match the baked shadows · `M2MAP-SHD-001` · MINOR

**Cause.** `.dds` and `.raw` out of sync. The client renders terrain with `shadowmap.dds` and samples point shadow colour from `shadowmap.raw` (`GetShadowMapColor`). Regenerate one without the other and lighting on characters disagrees with the ground.

**Detection.** Both present or both absent. `shadowmap.raw` **exactly** 131,072 bytes — this one *is* strictly validated on load and rejected otherwise. Decode is **RGB555** (`b=(t&0x1f)<<3`, `g=((t>>5)&0x1f)<<3`, `r=((t>>10)&0x1f)<<3`) despite an in-source comment claiming R5G6B5. Row 0 is the **north** edge (the writer iterates bottom-up to compensate for the D3D surface flip).

**Corpus.** 1,336 / 1,336 `shadowmap.raw` are exactly 131,072 — perfect conformance. 7 sectors have none (non-fatal: terrain renders unshadowed).

**Engine quirk worth mimicking only if you are byte-emulating.** `GetShadowMapColor` returns `(G<<16)|(G<<8)|R` — green duplicated into red, blue discarded (`Terrain.cpp:317`). Invisible for grayscale shadow data; decode faithfully for everything else.

---

#### F4 — Map looks flat and grey; fog and sky are engine defaults · `M2MAP-ENV-001` · MINOR

**Cause.** `setting.txt`'s `Environment` reference doesn't resolve. Resolution order is `<mapdir>\<name>` → `d:/ymir work/environment/<name>` → a fallback on the last two characters of the map name (`MapUtil.cpp:76-232`).

**Detection.** Assert one of those three paths exists. `ScriptType` inside the `.msenv` is written but **never validated** — old files say `EnvrionmentData` (the historical typo) and load fine, so don't check it.

**Fix.** Ship the `.msenv` or point at an existing one. Defaults when keys are absent: fog 12,800/17,920, skybox scale 3500³, cloud scale 200000², cloud height 30,000.

**Corpus.** 121 `.msenv` in the pack, **0 unresolved references** across all 142 maps.

---

### G. "Spawns are wrong"

#### G1 — A whole regen line never spawns anything · `M2MAP-RGN-001` · MAJOR

**Cause.** `time == 0` disables the line entirely — not even the initial spawn happens (`regen.cpp:766`). And the time parser **discards digits without an `s`/`m`/`h` suffix** (`regen.cpp:187-217`), so `60` parses to 0.

**Detection.** Column 7 must match `^(\d+[smh])+$`. Reject bare digits, reject `0`.

**Corpus.** 1,073 regen lines across all four file types in all 142 maps: **0 bare-digit times**. The trap is generator-only.

---

#### G2 — A `g`/`ga`/`r` line spawns nothing (or one wrong mob) · `M2MAP-RGN-002` · MAJOR

**Cause.** The spawn dispatcher tests `sx==ex && sy==ey` *before* the type switch (`regen.cpp:417`). Group lines with `0 0` half-extents take the point path, which calls `SpawnMob` with the **group id as if it were a mob vnum**. The group never spawns.

**Detection.** `if type[0] in "gr": assert (sx, sy) != (0, 0)`.

**Corpus.** 1,073 lines, types `r` 668 / `g` 361 / `m` 44 — **0 point-spawn traps**. Again generator-only.

---

#### G3 — Spawns land in the wrong place after a merge · `M2MAP-RGN-003` · MAJOR

**Cause.** Regen coordinates are in **units of 100 world-units (metres)**, map-local, and the server adds `BasePosition`:
```
sx_world = (cx - sxHalf) * 100 + BaseX
ey_world = (cy + syHalf) * 100 + BaseY
```
`sx`/`sy` are **half-extents around the centre**, not start coordinates, despite the column names. One sectree = 25,600 cm = **256 regen units**.

**Detection.** `0 <= cx <= MapSizeX * 256` and `0 <= cy <= MapSizeY * 256`, after shifting.

**Fix (merge).** MapForge shifts by whole sectors: `scx = (ox - s.minx) * 256`, `r.x += scx` (`index.html:1010-1018`). Note `e` (exception) rows get the ×100 scaling but **not** the base offset — they are compared map-locally — and they end after column 5, so a column-count-strict parser must special-case them.

**Also:** column 8 `percent` is parsed and thrown away (`regen.cpp:222-224`). Keep writing `100` for byte-compat, never surface it as meaningful.

---

#### G4 — Player spawns in the void · `M2MAP-SRV-003` · BLOCKER

**Cause.** `Town.txt` coordinates are map-local **units of 100**, `world = Base + value * 100`, and are not validated against the terrain. A `Town.txt` copied from a differently-sized map puts the spawn outside the sector grid.

**Detection.** `0 <= townX <= MapSizeX*256` and `0 <= townY <= MapSizeY*256`; the covering sector folder must exist; the terrain height there must be non-zero. If the optional 6 per-empire ints are present, **all six** must be — the server ignores a partial set.

**Contrast:** `dungeon.txt` uses **raw world units with no ×100 scaling** (`LoadDungeon`, `sectree_manager.cpp:322-365`). Mixing the two conventions is a classic.

---

## 2. MapForge's merge — the algorithms, and what each guard is for

Source: `<MAPFORGE>/index.html`. `m2map`'s **merge** and **reskin** modes both need §2.3 (tile remapping) and §2.4 (water reindexing).

### 2.1 The `ingestSlot` guards (`index.html:816-857`) · `M2MAP-MRG-007`

```js
if(!slot.sectors.length){ this.setState({mergeMsg:'that folder has no XXXYYY sectors'}); return; }
```

`ingestSlot` first strips a common path prefix (a drag-and-drop of `metin2_map_a1/` arrives with every key prefixed), then collects sector ids with `/^(\d{6})\//`. **Zero sectors is the fail-fast** — it catches the two most common drops: the wrong folder level (the parent of the map), and a map whose sector folders are named anything but six digits.

Then `w = setting.mapSizeX || (maxx-minx+1)` — dimensions come from `setting.txt` when present and are **inferred from the sector bounds** when not. `minx`/`miny` are kept per slot because the offset math normalises each source to its own origin (see 2.5). This is what makes `metin2_map_smhgate_b1` (sectors starting at x=2) mergeable at all.

### 2.2 The scale-equality gate (`index.html:960-965`) · `M2MAP-MRG-001`

```js
const prim = filled[0].s;
for(const {s} of filled){
  if(String(s.setting.cellScale)   !== String(prim.setting.cellScale) ||
     String(s.setting.heightScale) !== String(prim.setting.heightScale)){
    this.setState({mergeMsg:'✗ CellScale/HeightScale differ between maps — cannot merge safely'}); return;
  }
}
```

**Why it exists.** The merged map gets **one** `setting.txt` and therefore one `CellScale` and one `HeightScale`. Every `height.raw` is copied verbatim, so its raw values are reinterpreted under the survivor's `HeightScale` — mixing 0.5 and 1.0 halves or doubles one map's entire elevation. `CellScale` is worse: the client ignores the value and hard-codes 200, but the **server** multiplies map dimensions by it (`sectree_manager.cpp:262,276`), so a non-200 value desyncs server geometry from client geometry across the whole merged map.

Note the comparison is `String(...)` on both sides, so `0.5` vs `0.500000` **fails** the gate. That is over-strict but safe; if you loosen it, compare `parseFloat` with an epsilon and normalise the output to `0.500000`.

**Corpus:** every one of the 139 maps with a `setting.txt` uses `CellScale 200` and `HeightScale 0.500000`. The gate never fires on official data — it exists for community maps.

### 2.3 TextureSet union + tile-index remapping (`index.html:975-1000`) · `M2MAP-MRG-002` (missing set) · `M2MAP-MRG-003` (remap) · `M2MAP-TXS-004` (255 ceiling) — the important one

**The problem.** `tile.raw` bytes are indices into *that map's* TextureSet. Two maps both using index 3 almost certainly mean different textures. Concatenating maps without remapping repaints the ground at random.

**The algorithm.**

```js
const tsFiles = filled.map(({s}) => this.findTextureSetFile(s));
if(!tsFiles.every(Boolean)){
  // hard stop, named per slot
  this.setState({mergeMsg:'✗ attach a textureset .txt for: '+missing.join(', ')
    +' (needed to remap tiles + rewrite the TextureSet field)…'}); return;
}
const lists = await Promise.all(tsFiles.map(t => this.parseTextureSet(await t.file.text())));
union = []; const posByName = {};
const keyOf = e => e.file.toLowerCase().replace(/\\/g,'/');

filled.forEach(({i}, k) => {
  const list = lists[k].entries;
  const rm = { 0: 0 };                       // eraser stays eraser
  for(let idx = 0; idx < list.length; idx++){
    const key = keyOf(list[idx]);
    let pos = posByName[key];
    if(pos === undefined){                   // first sighting: append to the union
      union.push(list[idx]);
      pos = union.length;                    // 1-BASED union slot number
      posByName[key] = pos;
    }
    rm[idx + 1] = pos;                       // source slot idx+1 -> union slot pos
  }
  remaps[i] = rm;
});
if(union.length > 255) warn = ' ⚠ merged textureset has '+union.length+' textures (>255 limit)';
```

Then, per sector file:

```js
async remapTileFile(file, remap){
  const b = new Uint8Array(await file.arrayBuffer());
  const out = new Uint8Array(b.length);
  for(let i = 0; i < b.length; i++){
    const v = b[i];
    out[i] = (remap[v] !== undefined) ? remap[v] : v;   // passthrough for unmapped
  }
  return new File([out], 'tile.raw');
}
```

**Five things this encodes.**

1. **Index 0 maps to 0.** Slot 0 is the built-in eraser, excluded from `TextureCount`. The `{0:0}` seed is what keeps erased ground erased.
2. **Union slots are 1-based** (`pos = union.length` *after* the push). Off-by-one here shifts every texture on the map by one — the classic reskin bug.
3. **Dedup by lowercased forward-slashed path.** Shared ground textures (`d:\ymir work\terrainmaps\b\field\field 01.dds` appears in most A-series sets) collapse to one union slot, so the union stays small and identical ground stays identical across the seam. The path may be quoted and contain spaces — `extractTexPath` handles `^\s*"([^"]*)"` first, bare token second.
4. **The 255 ceiling.** `MAXTERRAINTEXTURES = 256` = 255 usable + eraser, and a tile byte cannot exceed 255 anyway. MapForge only **warns** — it still writes the file. That is a deliberate choice (the excess textures are unreachable but the map loads); an audit should treat it as an error because slots 256+ are silently unpaintable.
5. **`findTextureSetFile` and the missing-textureset error path.** The TextureSet lives **outside** the map folder, so a dragged map folder usually doesn't contain it. `findTextureSetFile` tries, in order: an explicitly attached file → a file whose basename matches `setting.txt`'s `TextureSet` value → any `textureset*.txt` in the drop. If it comes back null for any slot, the merge **refuses** and names the slots (`TL`, `TR`, `BL`, `BR`) that need one. Merging without it is not degradable — you would either leave the indices wrong or lose the palette.

**The defect to fix in `m2map` — verified against the corpus.** `parseTextureSet` collects entries **positionally** (`entries.push(cur)` in file order) and the remap uses `idx+1` as the source slot. The engine assigns slots by **block name** (`Texture%03d`). These agree only when the file is dense and sequential. It is not always:

| TextureSet | `TextureCount` | Blocks | Positional slot for the 2nd entry | Engine slot |
|---|---|---|---|---|
| `metin2_guild_village.txt` | 6 | `Texture002…006` (slot 1 missing) | 2 | **3** |
| `metin2_BayBlackSand.txt` | 11 | `Texture001,002,004…011` (slot 3 missing) | 3 | **4** |
| `metin2_map_naga1.txt` | 14 | 15 blocks, `Texture012` twice | — | last wins |

Merging `metin2_guild_village` with MapForge's positional parser shifts **every tile on the map by one texture**. Fix:

```js
const m = trimmed.match(/^start\s+texture(\d+)$/i);
if(m){ cur = { slot: parseInt(m[1], 10), file: null, body: [] }; continue; }
...
rm[cur.slot] = pos;    // NOT idx+1
```
and on write, emit a full dense `Texture001..TextureN` run so the output never has a hole.

**Also note the passthrough** in `remapTileFile`: a byte with no remap entry (index above the source's own `TextureCount` — 47 sectors in the corpus do this, §B1) keeps its original value, which now points at an unrelated union slot. Prefer mapping unknown indices to `0` (eraser) and reporting them.

**Reskin mode is the same algorithm with one slot**: build the new palette, produce `remap[oldSlot] = newSlot`, run `remapTileFile` over all 66,564 bytes (the border included — the skirt must be remapped too or sector edges keep the old textures), and rewrite `setting.txt`'s `TextureSet`.

### 2.4 Water-height table reindexing (`index.html:1002-1010`, `serializeWater` at `:947`) · `M2MAP-MRG-004`

**The problem.** Water layer indices are **per-sector**. Sector A's layer 0 might be a mountain lake at raw 40,000 and sector B's layer 0 a river at raw 18,000. Any tool that treats layer ids as global (several 3D editors do) shows water at the wrong Z after a merge.

**Pass 1 — collect the global height table:**
```js
const gHeights = []; const gById = new Map();
for(const {s} of filled)
  for(const path of Object.keys(s.files)){
    if(!/^\d{3}\d{3}\/water\.wtr$/.test(path)) continue;
    const w = this.parseWater(await s.files[path].arrayBuffer()); if(!w) continue;
    for(let c = 0; c < 16384; c++){
      const v = w.cells[c];
      if(v === 0xFF || v >= w.heights.length) continue;   // <-- the sentinel guard
      const h = w.heights[v];
      if(!gById.has(h)){ gById.set(h, gHeights.length); gHeights.push(h); }
    }
  }
if(gHeights.length > 255) waterWarn = ' ⚠ '+gHeights.length+' distinct water heights (>255) — water left per-sector';
const useWater = doWater && gHeights.length > 0 && gHeights.length <= 255;
```

**Pass 2 — rewrite each sector:**
```js
const nc = new Uint8Array(16384);
for(let c = 0; c < 16384; c++){
  const v = w.cells[c];
  nc[c] = (v === 0xFF || v >= w.heights.length) ? 0xFF : gById.get(w.heights[v]);
}
merged[nfolder+'/water.wtr'] = new File([this.serializeWater(nc, gHeights)], 'water.wtr');
```

**The 0xFF sentinel handling is the subtle part**, and it appears in three places:
- **Collection:** `v === 0xFF` is "dry", not a layer index — skipping it is what keeps 255 from entering the height table.
- **Corruption tolerance:** `v >= w.heights.length` is an out-of-range index (C3). MapForge treats it as dry rather than throwing — a repair, not a crash. That is the right call for a merge tool, but log it.
- **Rewrite:** both conditions collapse to `0xFF` in the output, so a corrupt index is *healed* by the merge.

**The >255 guard is load-bearing**: `NumWater` is a single `uint8` at offset 6. 256 distinct heights would write `0` and every cell would then be out of range. The guard's response is to **abandon normalisation entirely** and leave every sector's water as it was — degrade, don't corrupt.

**`serializeWater` always writes the 4-byte form** (`setInt32(7+16384+i*4, ..., true)`), never the legacy 2-byte form — correct, per C2.

**Corpus check:** max layers in any shipped sector is 17, and no sector has duplicate layer heights, so the "distinct height → id" mapping is total and the union across 4 quadrants stays far under 255 in practice.

### 2.5 Sector renaming and coordinate shifting (`index.html:966-1030`) · `M2MAP-MRG-005` (shifts) · `M2MAP-MRG-006` (stale artefacts)

**Quadrant layout.** Slots are TL/TR/BL/BR (indices 0-3):
```js
const col0 = Math.max(w(0), w(2)),  col1 = Math.max(w(1), w(3));
const row0 = Math.max(h(0), h(1)),  row1 = Math.max(h(2), h(3));
const off  = [[0,0], [col0,0], [0,row0], [col0,row0]];
const totalW = col0 + col1, totalH = row0 + row1;
```
Column width is the max of the two maps stacked in it; unequal sizes leave holes, which is legal (§A8).

**Three shifts, three different units — get one wrong and everything is off by a sector.**

| What | Unit | Code | Why |
|---|---|---|---|
| Sector folder | sectors | `nx = (+m[1] - s.minx) + ox; nfolder = pad3(nx)+pad3(ny)` | normalise the source to its own origin, then offset into the quadrant |
| regen `cx`/`cy` | 256 per sector | `scx = (ox - s.minx) * 256; r.x += scx` | regen units are 1/100 world units, 25,600 cm / 100 = 256 |
| areadata `x`/`y` | 25,600 cm per sector | `cmx = (ox - s.minx) * 256 * 100; o.x += cmx; o.y -= cmy` | areadata is cm — **and `y` is subtracted, not added, because areadata y is stored negated** |

That `o.y -= cmy` is the single easiest line to get wrong in a merge, and it is silent: objects end up mirrored across the map's horizontal axis.

**Files handled specially in the copy loop:**
```js
if(base === 'areadata.txt') continue;     // rebuilt below, with the cm shift
if(base === 'server_attr')  continue;     // must be regenerated
if(base === 'tile.raw' && rm){ ... }      // remapped
if(base === 'water.wtr' && useWater){ ... } // reindexed
merged[nfolder+'/'+base] = file;          // everything else copies verbatim
```
Everything else — `height.raw`, `attr.atr`, `areaproperty.txt`, `areaambiencedata.txt`, both shadowmaps, the minimap — is **copied byte-for-byte** into the renamed folder. That is correct: none of them contain coordinates. But it means **height skirts are not re-stitched** at the new internal seams (§B6) and minimaps stay per-sector-correct while the atlas needs rebuilding (§F2).

**Root files:** the primary slot's root files carry over, minus `skipRoot = {setting.txt, regen.txt, boss.txt, stone.txt, npc.txt, server_attr}` and the old textureset. `setting.txt` is rebuilt with the new `MapSize`, the primary's `BasePosition`/`Environment`, and `TextureSet textureset\<merged name>.txt`.

**What the merge leaves for you.** Its own status line is the checklist: `'merged N maps → WxH · water: K global layers · regenerate server_attr before use'` + any texture/water warnings. `server_attr`, the height skirts at new seams, the minimap atlas, and `atlasinfo.txt` are all stale afterwards.

---

## 3. Consolidated pitfalls from the format spec

Every Pitfalls section in `reference/mapformat/`, deduplicated against the atlas above.

**setting.txt** — `MapSize` is X then Y (columns, rows). All six required keys or the client rejects the map. `BasePosition` ties into `atlasinfo.txt` client-side and regen/Town math server-side: changing it moves the map and invalidates every absolute reference.

**height.raw** — Row-major, X fastest, row 0 is **north**. The +1 skirt offset: indexing `[sy*131+sx]` instead of `[(sy+1)*131+(sx+1)]` misreads the whole grid by one row and one column. No load validation — a wrong-size file silently corrupts terrain. Edge vertices must be mirrored into neighbours.

**tile.raw** — Same +1 border trap (`[(ty+1)*258+(tx+1)]`). Painting an edge tile requires mirroring into the adjacent sector's border row/column. Indices above `TextureCount` render as error texture.

**attr.atr** — **No border padding** (exactly 256×256, unlike height/tile). Keep the high bits *in `attr.atr`* (bits 3-6 carry paint conventions the editor relies on), but **mask to `& 0x07` when generating `server_attr`** — bit 7 marks walkable mountain, and letting it through makes the server treat it as `ATTR_OBJECT` and block the whole map (see D2). Keep `ATTRIBUTE_WATER` consistent with `water.wtr`.

**water.wtr** — Cell indices must be `< N` or `0xFF`. Height element size differs between legacy and current — never assume 4 bytes without the size check. No border padding.

**shadowmap** — `.dds` and `.raw` must stay in sync. `.raw` is rejected at any size other than 131,072. Missing files are non-fatal.

**minimap.dds** — Missing is non-fatal. Don't hardcode a size; parse the header. X8R8G8B8 in memory is BGRA per pixel — swap for canvas `ImageData`.

**areaproperty.txt** — Deleting it deletes the sector even with all binaries present. `NumWater` is written but never read back — parse the `water.wtr` header instead.

**areadata.txt** — Keys are case-insensitive; `End Object`'s trailing word is ignored, only `End` matters. CRCs repeat across records (same model instanced). Ambience CRCs belong in the other file. Write rotation as `%f#%f#%f`. Plot top-down at `(x, -y)`.

**areaambiencedata.txt** — No rotation or height-bias fields — **token 4 is range, not rotation**. Records whose CRC isn't registered are dropped.

**mapproperty.txt** — `MapType` conventionally quoted. Practically every playable map is `"Outdoor"`; the indoor pipeline is vestigial.

**server_attr** — Iteration is **y-major**, x inner — the opposite nesting from what `X*1000+Y` folder naming suggests. No `server_attr` = no collision at all server-side. Regeneration from `attr.atr` is lossless **only if the attr bytes are preserved in full**.

**server-regen** — `sx`/`sy` are half-extents. `percent` does nothing. `e` lines are 6 tokens. Bare-digit `time` silently zeroes the line. The parser only checks `token[0][0]`, so `mob` parses as `m`; community `ma`/`ra` "aggressive" variants silently degrade to `m`/`r` — only `ga` is honoured.

**server-map-files** — `Setting.txt`/`Town.txt` capitalised, everything else lowercase. Missing either aborts the **whole** map-loading pass. `atlasinfo.txt` must agree with each map's `BasePosition`/`MapSize`.

**client-global-refs** — Property key lookup is case-insensitive but files on disk are lowercase. **Don't trust extensions; trust the `PropertyType` value.** CRC is unsigned 32-bit (`parseInt(s) >>> 0`). The `\t\t` after keys and the quoting of every value are part of the canonical shape. TextureSet slot 0 is the eraser and is excluded from `TextureCount`.

---

## 4. Ranked pre-flight checklist for a generated map

Run in this order; each stage is worthless if the previous one fails.

1. **Loads at all** — A1, A3, A5, A6, A2 (`M2MAP-SET-001`, `SEC-001`, `ATR-001`, `SRV-001/002`)
2. **Geometry is coherent** — A4, A7, B6 (`HGT-001`, `TIL-001`, `SET-002`, `HGT-002`)
3. **Ground renders** — B1, B2, B3 (`TIL-002`, `TXS-001`, `TXS-002`)
4. **You can walk on it** — D1, D2, C4 (`ATR-003`, `ATR-004`, `WTR-004`)
5. **Objects appear where intended** — E1, E3, E4, E5 (`ARD-001`, `ARD-003`, `ARD-004`, `ARD-005`)
6. **Water behaves** — C1, C2, C3 (`WTR-001/002/003`)
7. **Spawns fire** — G1, G2, G3, G4 (`RGN-001/002/003`, `SRV-003`)
8. **Cosmetics** — F1, F2, F3, B5, B8 (`MMP-001`, `SET-004`, `SHD-001`, `TIL-003`, `HGT-003`)

After **any** merge or reskin, four artefacts are stale by construction: `server_attr`, the height skirts at new internal seams, every `minimap.dds`-derived atlas, and `atlasinfo.txt`.

---

## 4. Unit boundaries — the faults a round trip cannot see

Every entry above describes a file that is wrong in a way some check can notice.
This section is about the class that slips through **every** check the skill had,
and it earned its own section by producing three separate bugs.

The shape is always the same: the in-memory model is correct, the file is
correct-looking, and the *conversion between them* is wrong.

- A **byte round trip passes**, because reading and writing preserve the wrong
  unit symmetrically.
- An **in-memory assertion passes**, because the model really is right.
- The **audit passes**, because the file is structurally valid.
- The map **loads**, and is wrong only when a human looks at it.

### The three that happened

| Fault | Symptom | Why nothing caught it |
|---|---|---|
| Water heights written in cm into a raw-unit field | No water in game; `attr` says water is there | Round-trip preserved the wrong unit; pipeline reported 7.2% submerged and the file had 0% |
| `attr` cleared the road corridor before the water pass | Route sealed where the road crossed the river | Every layer preview looked right except `attr` |
| Object spacing pinned to a stipple texture | 17 of 20 props silently not placed | Placement is best-effort by design, so "fewer than asked" was not an error |

### The check that does catch it

**Cross the boundary and come back.** Write the file, re-read it with the codec,
and assert a property that *depends on the unit*:

```
water   -- the surface is above the terrain it covers
objects -- every record lands inside the map, Y negative
terrain -- the slope distribution still matches what was requested
regen   -- coordinates fall inside the tile grid, not 100x out
```

Each of those fails loudly on a factor-of-2, a sign flip, or a missing offset,
and none of them can be satisfied by a symmetric round trip.

### Where to expect them

Any field whose **stored** unit differs from its **working** unit. In this format
that is: `water.wtr` heights (raw, not cm), `height.raw` (raw, not cm),
`areadata` Y (negated) and its coordinates (map-local, not world),
regen/Town coordinates (units of 100, not cm), and `ViewRadius`
(doubled on load). Five conventions in one map.

### And look at it in the editor

All three faults above were found by **loading the map in WorldEditor**, not by
any automated check. The 2D previews validate the model; only the real engine
validates the boundary. `reference/we-api.md` has the working headless command.

---

## 5. Water that is technically correct and visibly wrong

Three faults in a row, all found by loading the map in WorldEditor, none
detectable from the file or the 2D previews. Water is disproportionately
represented in this atlas because `water.wtr` is the format's most indirect
layer: a cell index into a table of flat planes, with the terrain a separate
file entirely.

### A river rendered as alternating stripes of water and dry bed

**Cause.** Banding the surface by **height value**. A water body larger than one
flat plane has to be split into several, and the obvious split is by bed
elevation. But on a noisy bed, cells of similar height occur *scattered along
the whole channel*, so one band covers patches at both ends and its single plane
floods some of them while missing others.

**Fix.** Band **along the channel**, not by height: project each cell onto the
centreline, cut the river into contiguous reaches, and give each reach one plane
sitting above its own highest bed cell. Contiguity is the property that matters;
elevation is only a proxy for it, and a poor one.

### A lake rendered as terraces

**Cause.** Applying the same banding to a lake. Water does not step. A lake is
one flat surface by definition, and any banding of it is visible as blocky
level changes across the pool.

**Fix.** Lakes get exactly one plane. Only a descending river needs several.

### Water lying on the ground as a flat slab

**Cause.** No bed. Rasterising a water polygon and putting a plane over it gives
a sheet of water sitting on unmodified terrain, with no banks.

**Fix.** Carve the bed in the terrain stage, graded from zero at the shoreline
to full depth in the middle. The grading also hides what remains of the reach
steps: a level change inside a channel reads as a riffle, the same change on
open ground reads as a terrace.

Ordering note: the carve must come from the **layout** (stage 2), because terrain
is stage 3 and water is stage 4. The water polygons are known early; only their
surface levels need the finished terrain.

---

## 6. Non-determinism that looks deterministic

The mapspec's whole value is that a map is reproducible from `(spec, seed)`: it
is what makes `improve` a spec diff, what lets a user re-create a map from a
committed file, and what makes a bug report actionable. That guarantee is easy
to break in a way no obvious test catches.

**What happened.** Every stage seeded numpy with
`abs(hash(("terrain", spec.seed)))`. Python salts the hash of `str` and `bytes`
per process, so the same spec built a different map in every run:

```
tiles 155287   height mean 235.401   objects 120
tiles 155436   height mean 302.389   objects 120
tiles 154879   height mean 286.433   objects 122
```

**Why the test missed it.** `test_seed_is_deterministic` built the map twice and
compared — but *inside one process*, where the salt is constant. It asserted the
right property at the wrong scope, and passed for months.

**The symptom was elsewhere.** It surfaced as a flaky assertion about border
terrain. The flakiness was the tell; the terrain underneath was simply different
each run.

### Rules

- **Never seed from `hash()`.** Use `spec.stream_seed(salt, seed)` — a crc32 of
  `"salt/seed"`, stable across processes, versions and platforms.
- **Give each stage its own salt.** Re-running stage 5 must not shift stage 6's
  placements, which a single shared generator guarantees it will.
- **Test the derived value, not just the output.** Pin the constant:
  `stream_seed("terrain", 4242) == 162036731`. An output-comparison test cannot
  see a per-process salt; a pinned constant fails the moment someone
  reintroduces `hash()`.
- **A determinism test must cross a process boundary**, or it is testing that
  one process agrees with itself.

### The general shape

Sources of accidental non-determinism to check before claiming reproducibility:
`hash()` of anything but an int, `set` and `dict` iteration order over unsorted
keys, `os.walk` and `glob` ordering, floating-point reductions whose order
depends on thread count, and any default RNG that is not explicitly seeded.

# Identifying what a model actually *is*

The property catalog gives a prop's CRC, name and art path. It says nothing
about **how big** the prop is or **what it looks like**, so every placement
decision downstream is unanswerable from it. This document records what was
tried, what works, what does not, and the exact commands.

Everything below was measured on this machine, not read off a spec. Where the
vendored spec and the measurement disagree, the discrepancy is called out.

Implementation: `scripts/m2map/mine/models.py`.
Output: `reference/catalog/models.json`.

---

## Headline

| Question | Answer |
|---|---|
| Bounding box for every `.gr2`? | **Yes.** 5453/5453 mesh-bearing `.gr2` under `D:/ymir work` parse and yield extents (100%, zero reader errors). The other 2581 are animation-only files with zero meshes. Exactly one of the 5453 has junk vertex bytes and is flagged `degenerate`. |
| Pure Python, no `granny2.dll`? | **Almost.** The object graph, bbox, mesh/vertex/triangle counts and texture names are pure Python. Oodle1 *decompression* is delegated to OpenGranny's `grn-preprocessor.exe` (pure Rust, no DLL). There is no `granny2.dll` anywhere in the pipeline. |
| Bounding box for `.spt` trees? | **No.** It only exists after `CSpeedTreeRT::Compute()`. The authored *height* is recoverable; horizontal spread is not. |
| Is `treesize` enough for tree spacing? | **No, and it is worse than useless** — see [The tree size trap](#the-tree-size-trap). |
| Thumbnails? | **Yes**, via WorldEditorRemix headless. `gr2_viewer.exe` is a GUI app with no CLI. |
| Collision footprint? | **Yes**, bonus find: `.mdatr` parses in pure Python, 1482 of 1780 catalogued models have one. |

---

## 1. GR2 — what the shipped files actually are

Measured over all 2123 `.gr2` under `D:/ymir work/zone`:

| Property | Value |
|---|---|
| Container version | v6 legacy ×1766, v7 SDK-2.11 ×357 |
| Pointer size / endianness | 32-bit little-endian, all of them |
| Section compression | **format 2 (Oodle1) ×14865**, format 0 ×2119 (only the empty sections) |
| BitKnit / BitKnit2 | **zero occurrences** |
| Vertex formats (all 5453 mesh files) | 3 only: `P3f N3f UV2f` (2757), `P3f BW4×u8n BI4×u8 N3f UV2f` (3088), `P3f N3f UV2f UV2f` (225) |
| Triangle indices | 32-bit, always (`Indices16` never populated) |
| Skeletons | 1 bone in 145/152 sampled files, max 5 |

`Position` is `Real32[3]` at offset 0 in **every** format, so the bbox pass never
has to handle packed or half-float positions.

### Spec discrepancies found

1. **Legacy magic bytes are wrong in the vendored spec.**
   `reference/mapformat` does not cover GR2; `OpenGranny/docs/01-gr2-format.md`
   lists the legacy signature as bytes `CA B0 67 B8 0F B1 6D F8 7E 8C 72 84
   1E 00 19 5E` with `u32[0] == 0xB867B0CA`. Every legacy file here actually
   starts `B8 67 B0 CA F8 6D B1 0F 84 72 8C 7E 5E 19 00 1E`, i.e. each 4-byte
   group is byte-reversed relative to the doc, giving `u32[0] == 0xCAB067B8`.
   Verified on `zone/a/building/a1-001-house3.gr2` (hexdump) and 1765 others.
   The SDK-2.11 row in the same table *is* correct. `models.py` uses the
   measured constants.

2. **`ReferenceToVariantArrayMember` field order is wrong in the docs.**
   `01-gr2-format.md` describes it as "int32 + ptr"; `OpenGranny
   opengranny/src/typesys.rs:29` comments "count + type_ptr + obj_ptr". The
   size (12 bytes on 32-bit) is right in both, the **order is not**. Measured on
   `a1-001-house3.gr2`, `VertexData.Vertices` at section 0 offset 1044:

   ```
   +0  fixes up to (6, 2368)   -> type definition
   +4  = 3119                  -> vertex count   (3119 * 32 == 99808 == section 1 length)
   +8  fixes up to (1, 0)      -> vertex bytes
   ```

   So the layout is `type*, count, object*`. Reading it as `count, type*,
   object*` yields a count of 66577688 and a null type pointer.

### The decompression question, answered plainly

**A pure-Python reader cannot open a shipped Metin2 `.gr2` on its own.** Every
section that holds anything is Oodle1. Three candidate routes:

| Route | Verdict |
|---|---|
| `pygr2/fmt_GR2reader126.py`, `fmt_GR2reader1261.py` | **Dead on this machine.** Both call `ctypes.WinDLL("granny2.dll")` (`fmt_GR2reader126.py:2598`, `fmt_GR2reader1261.py:2766`) and bind 32-bit stdcall exports (`_GrannyDecompressData@32`). `granny2.dll` here is 32-bit; the installed Python is `3.13.5 … 64 bit (AMD64)`, and `ctypes.WinDLL(...granny2.dll)` fails with `WinError 193 — not a valid Win32 application`. They are also Noesis plugins and need the `noesis` module. |
| Port Oodle1 to Python | **Rejected, not attempted.** OpenGranny's `opengranny/src/oodle1.rs` is 816 lines reconstructed from the decompiled DLL: a 7-bit-per-byte range coder driving adaptive arithmetic models with binary-tree walk tables. It would have to decode ~300 MB of expanded section data at Python speed, and a subtle porting bug produces *plausible-looking wrong geometry* — the worst possible failure mode here. |
| OpenGranny `grn-preprocessor.exe decompress` | **Works.** Pure Rust, no `granny2.dll`, ~23 ms per model including process spawn. This is what `models.py` uses. |

`grn-preprocessor info` only prints the container header and section table — it
does **not** walk the object graph, so it cannot give a bbox by itself. The
walk is done in Python here, driven by the file's own type-definition sector.

Note: `decompress` also runs the SDK type conversion, so a v6 input comes back
as v7 with `TypeTag 0x80000039`. That is fine (and convenient — the object
graph is then in one known layout), but it means the rewritten file is *not*
byte-identical to the source. Nothing is ever written back to `D:/`.

### Commands

```bash
# decompress one file (writes a v7, format-0 GR2)
<OPENGRANNY>/target/release/grn-preprocessor.exe \
    decompress "D:/ymir work/zone/a/building/a1-001-house3.gr2" -output out.gr2

# one model, everything models.py can extract
cd <REPO>/skills/m2map/scripts
python -m m2map.mine.models --one "D:/ymir work/zone/a/building/a1-001-house3.gr2"

# full catalog pass -> reference/catalog/models.json
python -m m2map.mine.models
```

### Result on `a1-001-house3.gr2`

```
bbox_min  [-410.86, -428.73,   -1.06]      vertices  3119
bbox_max  [ 406.45,  428.91, 1071.44]      triangles 1610
size_xyz  [ 817.30,  857.64, 1072.50] cm   meshes    1
textures  D:\YMIR WORK\zone\A\building\a1-001-house3.dds
```

### Units and origin convention (measured, not assumed)

* Positions are **world centimetres**, **Z up**. `a1-001-house3` spans
  `z[-1.06, 1071.44]` with a flat floor at z≈0 — a 10.7 m pavilion.
* Models are authored **centred on their own origin**: over 1779 catalogued
  models, `|centre_xy| / footprint_r` has median **0.035**.
* Models **sit on z = 0**: `bbox_min.z` has median **−6.5 cm**.
* But the tail matters — p90 of `|centre_xy| / footprint_r` is **0.92** and p99
  is **6.9**. `b1-bigdam-04` is 3000 cm long with its pivot at one end
  (`centre = [1500, 0, 1250]`). Always use the `center` field, never assume
  the areadata position is the model's middle.
* `granny_model.InitialPlacement` is **non-identity on 375 of 1779 models**, but
  the client never reads it — `grep -rn "InitialPlacement" WorldEditorRemix/Srcs/Client/`
  outside `Srcs/Extern` returns nothing. So mesh-space extents *are* world-space
  extents. `models.py` records the placement anyway when it is non-zero.

### Independent validation

Two checks, neither of which uses the GR2 reader:

**1. Corpus placement spacing.** Parsed all 1343 `areadata.txt` in `<CORPUS>`,
took each CRC's within-map nearest-neighbour distances, and compared to the
measured model size. Modular pieces are laid end-to-end at exactly their own
length:

| model | measured `size_x` | median NN | 5th-pct NN | n placements |
|---|---|---|---|---|
| `gls_A_wall-lin2` | 1000.0 | **1000.0** | 1000.0 | 292 |
| `a1-038-wall-lin2_duel` | 1000.0 | **1000.0** | 1000.0 | 149 |
| `b1-bigdam-04` | 3000.0 | **3000.0** | 1000.0 | 130 |
| `ob-7-03-01` | 394.9 | 380.7 | 335.1 | 295 |
| `ob-7-02-01` | 352.2 | 346.3 | 209.4 | 336 |
| `general_obj_fence03` | 377.3 | 369.7 | 345.4 | 227 |

Across the 157 CRCs with ≥40 placements and ≥20 measurable neighbours, the
5th-percentile nearest-neighbour distance over `mean(size_x, size_y)` has
median **1.50** (p10 0.69, p90 6.18) — i.e. the tightest packing the level
designers used is right around one model-width, exactly as it should be. Only
15/157 CRCs pack closer than half their own longest side.

**2. Collision proxies.** For the 1465 models that have both a GR2 and an
`.mdatr`, `collision_size / render_size` is:

```
X  p10 0.60   median 0.99   p90 1.09
Y  p10 0.57   median 0.99   p90 1.13
Z  p10 0.41   median 0.97   p90 1.42
```

Two entirely independent files — a Granny mesh and a hand-authored collision
proxy — agree to within 1–3% at the median. 60% of models match within 25% on
both horizontal axes; the low tail is expected, since collision covers the
solid core and not overhanging roofs or canopies. `guild_pvp_gatebase` renders
`6681.7 × 5010.2 × 519.2` and collides `6699.4 × 5028.6 × 519.1` (0.3%).

That agreement only appears once the collision dimensions are decoded exactly
as the engine does — see [section 6](#6-mdatr--the-collision-proxy-bonus-pure-python).
The first attempt treated plane `fDimensions` as half-extents and produced
medians of 1.35 / 1.23, which is the sort of quietly-wrong 2× that would have
poisoned every clearance rule downstream.

### Failure inventory — all of it

Over every `.gr2` under `D:/ymir work` (8034 files):

```
5453  bbox extracted
2581  no vertex data  -> all of them have meshes=0, animations>0 (animation clips)
   0  reader errors
```

Zone subtree specifically: **2116 / 2123 = 99.67%**; the 7 "failures" are
`b1-middledam-*door_ani_*.gr2` and `spider_dungeon_gate.gr2`, all
`meshes=0 animations=1`.

One genuinely broken shipped asset:
`zone/dungeon/haven_dungeon/skipia_collision.gr2` has 3 vertices whose bytes are
not floats, giving extents of 1.4e17 cm. It is placed **324 times** in the
corpus (it is an invisible collision helper). `models.py` flags it
`"degenerate": true` and sets `status: "gr2-degenerate"` rather than letting a
1e17 poison a spacing rule. Threshold: any coordinate non-finite or
`|v| > 1e6 cm` (the whole map grid is 102400 cm across).

---

## 2. SpeedTree `.spt`

87 files under `D:/ymir work/tree` plus 31 under `zone/`. Format is
`__IdvSpt_02_` — a token stream describing a **procedural** tree, not a mesh.

`CSpeedTreeWrapper::LoadTree` (`SpeedTreeLib/SpeedTreeWrapper.cpp:303-346`) only
obtains a bounding box *after* `m_pSpeedTree->Compute(NULL, nSeed)`:

```cpp
if (m_pSpeedTree->Compute(NULL, nSeed))
    m_pSpeedTree->GetBoundingBox(m_afBoundingBox);
```

`CSpeedTreeRT` ships only as `Srcs/Extern/lib/SpeedTreeRT-static.lib` (and the
x64 twin) — a static library, no DLL. **There is no way to get a tree bounding
box from Python.** Getting one at all would mean writing a small C++ tool that
links that lib and dumps `GetBoundingBox` per `.spt`; that is a build in the
WorldEditorRemix tree, not something this skill can do.

What *is* readable: `.spt` token `0x07D1` carries a float. Across all 87 files it
takes exactly four values, and they track plant size:

| value | n | examples |
|---|---|---|
| 50 | 16 | `n2_aloevera_rt_flowers_01`, `n2_cinnamonfern_rt_01`, `n2_bananatree_rt_01` |
| 400 | 8 | `n1_coloradobluespruce_rt_01`, `n1_whitepine_rt_low_01`, `n2_palmetto_rt_01` |
| 600 | 5 | `b3_shingleoak_rt` … `b3_shingleoak_rt5` |
| 1100 | 58 | `b1_baobab_rt`, `b1_beech_rt`, `b1_montereycypress_rt`, … |

Token `0x07D2` is 0.0 in all 87 (the variance). `models.py` reports these as
`spt_size` / `spt_variance` with `bbox_available: false`. Treat `spt_size` as an
approximate **height in cm** and nothing more — it says nothing about canopy
radius, which is what spacing actually needs.

### The tree size trap

Do **not** use the `.prt` `treesize` / `treevariance` keys.

1. They carry no information. All 85 shipped `Tree` properties have
   `treesize == "1000.000000"` and `treevariance == "0.000000"`. Every single
   one.
2. They are **never applied**. The load path is
   `CSpeedTreeForest::GetMainTree` → `pTree->LoadTree(c_pszFileName, data, size)`
   (`SpeedTreeForest.cpp:86`), and `CSpeedTreeWrapper::LoadTree` declares
   `float fSize = -1.0f, float fSizeVariance = -1.0f`
   (`SpeedTreeWrapper.h:102`). `SetTreeSize` is guarded by
   `if (fSize >= 0.0f && fSizeVariance >= 0.0f)` (`SpeedTreeWrapper.cpp:339`).
   No call site in either the client or the editor ever passes a size — the
   editor's property preview (`MapObjectPropertyPageTree.cpp:237`) and the
   placement cursor (`SceneMapCursor.cpp:327`) both use the default too. The
   size that reaches the renderer is the one baked into the `.spt`.

So a generator that spaces trees by `treesize` is spacing every species
identically, using a number the engine discards.

**Use the corpus instead.** `mine/object_stats.py` measures real per-CRC
spacing and clustering from all 1343 `areadata.txt` files; for the 85 tree CRCs
that empirical nearest-neighbour distribution is the only footprint evidence
that exists.

---

## 3. Rendering — what works on this machine

### `gr2_viewer.exe` — **no**

`<OPENGRANNY>/gr2_viewer.exe` opens a GUI window
titled *"Granny Viewer"* and blocks forever — bare, and with `--help`, `-h` and
`/?` alike (all three still running after 8 s, 0 bytes on stdout **and**
stderr; had to `Stop-Process` each). No screenshot switch, no headless mode.
`grn.exe` in the same directory produces no output at all for `--help` or bare.
Neither is built from the OpenGranny workspace (`Cargo.toml` lists only
`opengranny`, `opengranny-ffi`, `opengranny-preprocessor`), so there is no
source to add a `--shot` flag to.

### WorldEditorRemix headless — **yes**

```bash
# from D:\ (the data dir holding pack/ and "ymir work/")
<WORLDEDITOR_EXE> \
    --file "ymir work\zone\a\building\a1-001-house3.gr2" \
    --size 732,571 \
    --shot "C:/.../out.png" \
    --quit
```

Verified working: renders the fully textured model, framed by `FitCamera`, on a
grey grid. ~2.5 s per model wall-clock (measured 17 models in 42 s through
`models.py --thumbs`, and 3 individual runs at 2.3–2.5 s).

**`--size` sizes the frame, not the image.** The 3D view loses the docking bars,
so the PNG comes out `(W − 220) × (H − 59)`. Measured: `732,571 → 512×512`,
`1400,900 → 1180×841`, `900,900 → 680×841`. `models.py` has `we_size_for()`.

**Three traps, all confirmed by experiment:**

1. **`.spt` is not renderable.** `--file` dispatches on extension and only
   handles `mse`, `gr2`, `msm`, `msf` (`WorldEditor.cpp:663-694`); anything else
   hits `Tracenf("automation: unsupported --file extension %s")`. So the 84
   catalogued trees get **no thumbnail** by this route.
2. **Exit code is always 0** — for a missing file, a failed load and an
   unsupported extension alike. A PNG is always written.
3. **MfcRelease does not surface the `automation:` traces on stderr.** stderr
   carries only startup noise (`pack/root: Pack file does not exist`,
   `PythonDynLoad: …`). There is no textual failure signal at all.

Detection therefore has to be done on the image. A `.gr2` that fails to load
renders a **blank 2228-byte** 512×512 PNG (the object scene is `Clear()`ed
first), while a real model render is 8–28 KB. An unsupported extension leaves
the *previous* scene up — the `.spt` runs produced a 15052-byte PNG of the
default character, which the size heuristic would wrongly pass, so filter by
extension before dispatching rather than relying on the size check.

Nothing is written to `D:/` by these runs (`D:/syserr.txt` was last modified
2026-09-01, well before the session).

### Cheapest visual ID: the diffuse texture

Every catalogued model carries its `.dds` path in the GR2. **1756 of 1779
(98.7%)** resolve to a file on disk (1463 of 1488 distinct textures, 98.3%).
`codec/dds.py` already decodes them. For "what is this thing" purposes a
128×128 crop of the diffuse texture costs milliseconds and needs no GPU, no
editor and no D3D device — worth doing for the whole catalog before spending an
hour on 3D renders.

---

## 4. Recommended pipeline

**Sizes — do this first, it is cheap and complete.**

```bash
cd <REPO>/skills/m2map/scripts
python -m m2map.mine.models              # 45 s, writes reference/catalog/models.json
```

Gives, per CRC: `bbox_min/max`, `size_xyz`, `center`, `footprint_r`, `height`,
`vertices`, `triangles`, `meshes`, `mesh_names`, `materials`, `textures`,
`bones`, `vertex_formats`, `source_max_file`, optional `initial_placement`, and
an `mdatr` block with the collision envelope.

Use `footprint_r` (horizontal half-diagonal) for rotation-agnostic spacing and
`mdatr.collision_size_xyz` when you need what the player actually collides with
(the two agree to within 1% at the median, so either is defensible; collision
is the tighter, "solid core" number).

**Thumbnails — second pass, ~74 min for the 1780 buildings/dungeon blocks.**

```bash
python -m m2map.mine.models --thumbs <dir> \
    --we <WORLDEDITOR_EXE> --we-cwd <WORLDEDITOR_DATA>
```

Skips non-`.gr2`/`.msm` entries, skips PNGs that already exist (so it is
resumable), and reports a blank render as a failure instead of silently
banking it.

**Trees — no mesh route exists.** Combine:
* `spt_size` from `models.json` for a height class (50 / 400 / 600 / 1100), and
* the empirical per-CRC nearest-neighbour spacing from `mine/object_stats.py`
  for the footprint.

If exact tree bounds ever become worth the effort, the only route is a C++ tool
linked against `WorldEditorRemix/Srcs/Extern/lib/SpeedTreeRT-static.lib` that
calls `LoadTree` → `Compute` → `GetBoundingBox` per `.spt` and dumps 87 rows.
Adding `.spt` to the editor's `--file` dispatch (`WorldEditor.cpp:663`) would
also unlock tree thumbnails.

---

## 5. Catalog coverage as generated

```
properties               2112      2113 files, but mtthunder_thorn01.prb and
                                   obj_mtthund_thorn01.prb both carry CRC
                                   1740984444; CPropertyManager::Register keeps
                                   the last, so does scan_property_dir
gr2-ok                   1779
gr2-degenerate              1      skipia_collision.gr2
spt-partial                84      size token only, no bbox
missing-file              156      art not extracted -- 79 of them whole absent folders
                                   (zone/12temple 36, guild/building 16, guild/inside01 7,
                                    plus authoring paths like
                                    "c:/documents and settings/ibakoon/...")
unsupported-extension      90      Effect properties pointing at .mse scripts
no-model-path               2      the two Ambience properties, by design
mdatr-ok                 1482
mdatr-absent              298
```

**Every art file that exists on disk was read successfully.** The 156 misses are
extraction-coverage gaps in `D:/ymir work`, not reader failures — the generator
must treat those CRCs as unsized, not assume a default.

Distribution of the 1779 sized models (cm):

```
size_x    min 18.5   p10 130   median 837   p90 4449   max 28914
size_y    min  3.2   p10  82   median 563   p90 3689   max 34781
height    min  0.0   p10 125   median 796   p90 3476   max 27461
footprint_r                    median 570   p90 3140
vertices                       median 586             max 62864
triangles                      median 440             max 42292
```

The very large entries are real: `cliff_dome_00` (283 × 348 m),
`cliff_wall_up` (236 × 288 × 183 m), `WDC_01_room_01` (201 × 278 m) — dungeon
and terrain shells that span multiple sectors, not errors.

---

## 6. `.mdatr` — the collision proxy (bonus, pure Python)

1579 files under `zone/`, derived from the model path by
`CFileNameHelper::NoExtension(model) + ".mdatr"` (`GameLib/MapType.cpp:142`).
Parser is `CAttributeData::OnLoad`, `EterLib/AttributeData.cpp:44-130`:

```
"AttributeData\0"            14 bytes
u32 collisionCount
u32 heightCount
per collision:
    u32   type              0 plane, 1 box, 2 sphere, 3 cylinder, 4 aabb, 5 obb
                            (EterLib/CollisionData.h:42)
    char  name[32]
    f32   pos[3]
    f32   dims[n]           n = 2/3/1/2/3/3 by type
    f32   quat[4]           D3DXQUATERNION order x, y, z, w
per height record:
    char  name[32]
    u32   vertexCount
    f32   xyz[3] * vertexCount
```

### `fDimensions` means something different for every shape type

This is the trap in this file, and it is not documented anywhere. Read off
`CBaseCollisionInstance::New`, `EterLib/CollisionData.cpp:29-210`:

| type | how the engine reads `fDimensions` | `quatRotation` used? |
|---|---|---|
| `plane` (0) | `fHalfWidth = d[0]/2`, `fHalfLength = d[1]/2` → **full** extents; quad lies in local XY, normal on local Z (`:42-58`) | **yes** (`:36`) |
| `box` (1) | `d[0]/2` on X, `d[2]/2` on **Y**, `d[1]/2` on **Z** → full extents with Y and Z swapped (`:94-102`) | no |
| `aabb` (4) | `pos ± d[k]` → **half** extents (`:125-130`) | no |
| `obb` (5) | `pos ± d[k]` → half extents; `matRot` is the object's world matrix, `quatRotation` is loaded into a local and never used (`:149-160`) | no |
| `sphere` (2) | `fRadius = d[0]` (`:188`) | n/a |
| `cylinder` (3) | `fRadius = d[0]`, `fHeight = d[1]`, and the `+ fHeight/2` on the centre is **commented out** — so it runs `pos.z` → `pos.z + d[1]`, not centred (`:202-206`) | no |

Shipped data uses only `plane` (11243), `cylinder` (456) and `sphere` (217).

`models.py:shape_envelope()` implements all six branches, and for the plane
converts the rotated box to a world-axis envelope with the exact rule
`extent[k] = Σ_j |R[k][j]| · half[j]`.

Getting this wrong is expensive and silent. Two earlier attempts, and what
they did to the collision/render median:

| decode | X | Y |
|---|---|---|
| half-diagonal sphere around each shape | 2.46 | 3.02 |
| axis-correct, but dims read as half-extents | 1.35 | 1.23 |
| **engine-exact (current)** | **0.99** | **0.99** |

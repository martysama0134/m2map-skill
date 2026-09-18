# WorldEditorRemix Python API — verified reference

Authoritative source for every claim below:

| What | Path |
|---|---|
| The 281 bindings | `<WORLDEDITOR>/Srcs/Tools/WorldEditor/PythonWorldEditorModule.cpp` (6597 lines) |
| Arg-parse helpers | `Srcs/Client/ScriptLib/PythonUtils.cpp` / `.h` |
| Terrain accessor | `Srcs/Tools/WorldEditor/DataCtrl/MapAccessorTerrain.h` / `.cpp` |
| Outdoor accessor | `Srcs/Tools/WorldEditor/DataCtrl/MapAccessorOutdoor.h` / `.cpp` |
| Area accessor | `Srcs/Tools/WorldEditor/DataCtrl/MapAccessorArea.cpp` |
| Manager accessor | `Srcs/Tools/WorldEditor/DataCtrl/MapManagerAccessor.cpp` |
| Engine terrain/map | `Srcs/Client/PRTerrainLib/Terrain.h`, `Srcs/Client/GameLib/MapOutdoor*.cpp`, `AreaTerrain.cpp`, `Area.h` |
| server_attr | `Srcs/Tools/WorldEditor/DataCtrl/ServerAttrGenerator.h` / `.cpp` |
| CLI / automation | `Srcs/Tools/WorldEditor/WorldEditor.cpp` (`InitInstance`, `__ProcessAutomation`), `WorldEditor.h` (`SAutomation`), `DockingBar/MapFilePage.cpp` (`ApplyOptionFlag`, `LoadMapFromPath`) |
| Python wrapper | `Srcs/Tools/bin/lib38/WorldEditorRemix.py`, `lib38/WorldEditorRemixWrapper/{main,terrain_operations,ui}.py` |

Verification marks used per entry:

- **[V]** — I read the C++ binding body **and** the accessor/engine function it calls. Signature and semantics both verified.
- **[V-sig]** — I read the C++ binding body (arg count, arg types, return shape exact) but did **not** open the downstream accessor. Semantics are as-named and unverified.
- Nothing here is **UNVERIFIED** at the signature level: every one of the 281 bindings' C++ body was read.

---

## 0. How the module is reached

- Native module name is `WorldEditor`; `import WorldEditor as we`.
- The editor runs `lib38/WorldEditorRemix.py` (or `lib38-x64/…` on x64) when you press **F5** in the 3D view — `WorldEditorView.cpp:394-403`, gated on `globals::dft::ENABLE_PYTHON` and `pydyn::IsInitialized()`. There is no other entry point and **no CLI switch that runs a script**.
- Python 3.8; `sys.path` is `<cwd>/lib38/python38.zip` + `<cwd>/lib38` (`WorldEditor.cpp:376-402`).
- `dbg` module provides `dbg.Tracen(...)` (log) and `dbg.LogBox(...)` (modal message box).
- The script runs **synchronously inside the message loop**. No frame is rendered between two Python statements. This has hard consequences — see §2.4.

### 0.1 Argument parsing is loose — read this before writing any call

`PythonUtils.cpp:23-38, 61-184`:

```cpp
PyObject * Py_BuildException(const char * c_pszErr = NULL, ...)  // default arg, PythonUtils.h:25
{
    if (!c_pszErr) PyErr_Clear();
    else PyErr_SetString(PyExc_RuntimeError, szErrBuf);
    return Py_BuildNone();          // <-- returns Py_None, NOT NULL
}
bool PyTuple_GetLong(PyObject* poArgs, int pos, long* ret)
{
    if (pos >= PyTuple_Size(poArgs)) return false;
    *ret = PyLong_AsLong(PyTuple_GetItem(poArgs, pos));
    return true;                    // <-- true even if PyLong_AsLong failed
}
```

Consequences, all load-bearing:

1. **Too few arguments → silent no-op.** The binding hits `return Py_BuildException();` with no message, which calls `PyErr_Clear()` and returns `None`. `we.InsertObject(1,2,3)` returns `None` and does nothing. It does **not** raise, and it does **not** crash. Wrong arity is therefore invisible — the generator must get arity right by construction, not by try/except.
2. **A float where a `long` is expected is silently wrong.** `PyLong_AsLong(<float>)` raises `TypeError` internally and returns `-1`, but the helper returns `true`, so the binding proceeds with `-1` and a *pending* exception. Only `DrawHeightPixel` checks `PyErr_Occurred()`. Always pass `int()` for `long` params.
3. **An int where a `double` is expected is fine** (`PyFloat_AsDouble` accepts int).
4. Returning non-NULL with an error set violates the CPython protocol; you may see a `SystemError: … returned a result with an error set` at an unrelated later call. Treat any `SystemError` as "an earlier binding got bad args".
5. Extra trailing arguments are ignored (except where a binding explicitly reads optional args: `SaveMap`, `InitBaseTexture`, `SelectNextMonsterAreaInfo`, `DeleteObjectsByCRCList`, `ReplaceObjectsByCRC`, `PlaceGrassPropsByTexture`, `DrawHeightBrush`, `GenerateServerAttr`).
6. String params go through `pydyn::StringCheck` and **do** fail cleanly on a non-string.

---

## 1. Coordinate spaces — the #1 source of silent corruption

Six distinct spaces appear in this API. **The name of a binding does not tell you which one it uses.**

| # | Space | Range | Unit | How to spot it in the C++ |
|---|---|---|---|---|
| **W** | **World centimetres** | `0 … countX*25600` in x; **negative** in y (`0 … -countY*25600`) | 1 cm | value is passed straight to a `float` accessor, or divided by `TERRAIN_XSIZE` (25600) |
| **C** | **Global cell** | `0 … countX*128-1` | 200 cm | `lX / TERRAIN_SIZE` where `TERRAIN_SIZE == 128` |
| **S** | **Sector / terrain coord** | `0 … countX-1` | 25600 cm | passed to `GetTerrainNumFromCoord` / `PreloadTerrainAndArea` |
| **L** | **Terrain-local cell** | `0 … 127` | 200 cm | `lX % TERRAIN_SIZE` |
| **H** | **Half-cell (attr / tile pixel)** | `0 … 255` | 100 cm | `ATTRMAP_XSIZE`/`TILEMAP` indices, `bySubCellX = (cell%4)*2` |
| **N** | **Resident-window slot** | `0 … 8` | — | `BYTE byTerrainNum` from `GetTerrainNumFromCoord`; **not** a global sector id |

Sign convention: the editor stores object/camera **Y negated** (south is negative). `CMapOutdoor::GetTerrainNum` and `CMapOutdoor::Update` do `if (fy < 0) fy = -fy;` internally; `CMapOutdoor::GetAttr/isAttrOn/GetWaterHeight(int,int)` do **not** (they reject `iY < 0`). So `we.GetAttrAt(x, y)` needs a **positive** y, while `we.InsertObject(x, y, …)` needs a **negative** y for the same physical spot.

### 1.1 Constants (from `Srcs/Client/PRTerrainLib/Terrain.h:18-72` and `TerrainType.h:7-11`)

```
TERRAIN_SIZE      = 128     XSIZE = YSIZE = 128 cells per sector
CELLSCALE         = 200     cm per cell
TERRAIN_XSIZE     = 25600   cm per sector edge  (= MAPBASE)
HEIGHTMAP_XSIZE   = 129     HEIGHTMAP_RAW_XSIZE = 131  (1-sample skirt)
ATTRMAP_XSIZE     = 256     half-cell grid, 100 cm per pixel
TILEMAP_XSIZE     = 256     TILEMAP_RAW_XSIZE = 258    (1-pixel skirt)
WATERMAP_XSIZE    = 128     one water sample per cell
PATCH_XSIZE       = 16      PATCH_XCOUNT = 8
MAX_WATER_NUM     = 255     water-height table has MAX_WATER_NUM+1 = 256 entries
AROUND_AREA_NUM   = 9       LOAD_SIZE_WIDTH = 1  ->  3x3 resident window
MAXTERRAINTEXTURES= 256
ATTRIBUTE_BLOCK=1  ATTRIBUTE_WATER=2  ATTRIBUTE_BANPK=4
```

Height units: `height.raw` holds `uint16`. `worldZ = raw * HeightScale`, and the editor hard-codes `HeightScale = 0.5` on save, so **`worldZ_cm = raw / 2`** (`AreaTerrain.cpp:396`, and `reference/mapformat/height-raw.md`). Every height-related binding here deals in **raw uint16**, never in cm.

Attr↔tile mapping (identical resolution, offset by the tile skirt) — `ApplyAttrToTerrainByTile`, `PlaceGrassPropsByTexture`, `GetTileValueAt` all use it:

```
attr index   = attrY * 256 + attrX                     attrX,attrY in [0,255]
tile index   = (attrY+1) * 258 + (attrX+1)             the +1 is the tile.raw skirt
world x (cm) = sectorX*25600 + attrX*100 + 50          centre of the half-cell
world y (cm) = -(sectorY*25600 + attrY*100 + 50)       note the negation
```

### 1.2 Trap table — bindings whose name lies about their space or behaviour

| Binding | Name suggests | Actually **[V]** | Evidence |
|---|---|---|---|
| `GetHeightAt(x,y)` | world cm | **space C** (global cell). Does `lX/128`. Returns **raw uint16**, not cm. | `PythonWorldEditorModule.cpp:311-343` |
| `SetHeightAt(x,y,h)` | world cm | **space C**. `h` is raw uint16. | `:349-381` |
| `WorldToTerrainCoords(x,y)` | world cm → sector+cell | input is **space C**, not cm. `terrainNum = x/128`, `cell = x%128`. | `:388-406` |
| `TerrainToWorldCoords(tx,ty,cx,cy)` | → world cm | returns **space C** (`tx*128+cx`), not cm. | `:408-425` |
| `GetMapBounds()` | cm | returns `baseX + countX*128` — mixes a cm base with a cell span. **Numerically meaningless.** | `:450-471` |
| `GetTerrainWorldBounds(tx,ty)` | cm | same defect: `baseX + tx*128`. **Do not use.** | `:4903-4931` |
| `GetAttrAt(x,y)` | pairs with `SetAttrAt` | **space W (world cm, positive y)**. Calls `CMapOutdoor::GetAttr(float,float)`. | `:1441-1463` → `MapOutdoor.cpp:1085,1117` |
| `IsAttrOn(x,y,f)` | — | **space W (positive y)**. | `:1500-1523` → `MapOutdoor.cpp:1076,1094` |
| `SetAttrAt(x,y,f)` | pairs with `GetAttrAt` | **space C**, *and it is broken*: it computes `terrainNumX/Y` then passes them into `DrawAttrBrush`'s `lCellX/lCellY` params. See §1.3. | `:1465-1498` |
| `DrawAttrBrush(x,y,f,size,erase)` | — | same defect as `SetAttrAt`. | `:1525-1563` |
| `SetAttrAtWorld(x,y,f)` | world cm | **space C**. `lX/128`. Correctly reaches the right sector and cell (unlike `SetAttrAt`). | `:4986-5033` |
| `DrawHeightBrush(x,y,…)` | positions on the map | computes `terrainNumX/Y` and **throws them away**; the brush always lands on the **current edit terrain** at `(x%128, y%128)`. | `:2086-2131` |
| `GetPropertyType(int)` | name → type | takes an **int**, returns the **extension string** (`prt::GetPropertyExtension`). | `:111-119` |
| `GetPropertyExtension(str)` | type → extension | takes a **string**, returns the **int type** (`prt::GetPropertyType`). The two are swapped. | `:121-129` |
| `GetObjectList(...)` | list objects | **stub**: `return Py_BuildValue("()")`. Always an empty tuple. | `:131-134` |
| `GetBrushType()` | current brush type | **stub**: returns `0` always. Comment in source: `// GetBrushType doesn't exist`. | `:2178-2188` |
| `GetSplatValue()` / `SetSplatValue(f)` | per-cell splat alpha | a single global float that scales the splat-alpha **texture matrix** (`m_matSplatAlpha._41/_42 = m_fTerrainTexCoordBase * v`). Nothing to do with per-pixel blending. | `:4699-4735` → `MapAccessorOutdoor.cpp:50-56` |
| `GetTerrainNumFromCoord(sx,sy)` | global sector index | **space N**: a slot 0..8 in the 3×3 resident window. Returns `-1` only when the computed BYTE exceeds 9. Off-by-one: the engine test is `> AROUND_AREA_NUM` (9), not `>= 9`. | `:4778-4802` → `MapOutdoor.cpp:659-666` |
| `GetTerrainNum(x,y)` | global sector index | **space N** too; input is **space W** (y auto-abs'd). | `:3137-3156` → `MapOutdoor.cpp:439-453` |
| `RefreshSelectedInfo()` | refreshes | body is inside `#ifdef CWE_AREA_ACCESSOR_MISSING_REFRESH`; normally compiles to nothing. | `:1621-1635` |
| `EnableWind(b)` | — | body inside `#ifdef ENABLE_WIND_OPTION`; may be a no-op. | `:2627-2646` |
| `GetSelectedMonsterAreaInfo()` | index/handle | returns `0` if a selection exists, `-1` otherwise. Carries no information. | `:3312-3327` |
| `GetObjectData(i)` → `crc` | unsigned CRC | built with `Py_BuildValue("…i…")` → **signed 32-bit**. CRCs ≥ 2³¹ come back negative. | `:708-731` |
| `GetLastSelectedObjectData()["crc"]` | unsigned CRC | `PyLong_FromLong((long)dwCRC)` → also **signed**. | `:5341-5381` |
| `MoveSelectedObject(dx,dy)` | move to | **relative delta** in world cm, applied to every selected object in all 9 areas. | `:733-752` → `MapAccessorArea.cpp:533,1607` |
| `MoveSelectedObjectHeight(dz)` | set height | relative delta added to `Position.z`. | same |
| `RotateSelectedObject(y,p,r)` | set rotation | **adds** to current rotation (`AddSelectedObjectRotation`). | `:787-808` |
| `SelectObjectsByRect(x1,y1,x2,y2)` | rect select | world cm, **strict `>` / `<`, no auto-swap**. With negative editor Y you must pass the more-negative y first. | `:620-643` → `MapAccessorArea.cpp:398-418` |
| `UpdateTargetPosition(dx,dy)` | set target | **relative delta** in world cm, **integer only** (`PyTuple_GetLong`). | `:153-171` → `WorldEditorView.cpp:228`, `SceneMap.cpp:1958` |
| `GenerateServerAttr(path,…)` | uses in-memory map | reads `<path>\<XXXYYY>\attr.atr` **from disk**. Unsaved edits are not included. | `:6080-6108` → `ServerAttrGenerator.cpp:55,275` |

### 1.3 `SetAttrAt` / `DrawAttrBrush` are wired wrong — proof

`CTerrainAccessor::DrawAttrBrush` (`MapAccessorTerrain.h:53-61`, impl `MapAccessorTerrain.cpp:211-311`):

```cpp
void DrawAttrBrush(DWORD dwBrushShape, BYTE byAttrFlag,
                   long lCellX, long lCellY,          // terrain-LOCAL cell, 0..127
                   BYTE bySubCellX, BYTE bySubCellY,  // half-cell, 0..7
                   BYTE byBrushSize, bool bErase);
// attr pixel = lCellX*2 + bySubCellX   (fAttrHeightRatio = 256/128 = 2)
```

`weSetAttrAt` (`PythonWorldEditorModule.cpp:1465-1498`; the bad call is line `1496`) passes `terrainNumX, terrainNumY` into `lCellX, lCellY`:

```cpp
long terrainNumX = lX / TERRAIN_SIZE;      // 0..countX-1
long cellX       = lX % TERRAIN_SIZE;
BYTE bySubCellX  = (BYTE)((cellX % 4) * 2);
pTerrainAccessor->DrawAttrBrush(BRUSH_SHAPE_CIRCLE, attrFlag,
                                terrainNumX, terrainNumY,   // <-- should be cellX, cellY
                                bySubCellX, bySubCellY, 1, false);
```

Compare `weSetAttrAtWorld` (`:4986-5033`; its `DrawAttrBrush` call is line `5029`), which passes `cellX, cellY` correctly. So:

- `SetAttrAt(x, y, flag)` writes attr pixel `(x/128*2 + (x%4)*2, …)` of the **current edit terrain**, i.e. always inside the first few cells of whatever sector the camera is on.
- **Never use `SetAttrAt` or `DrawAttrBrush` from a generator.** Use `SetAttrAtWorld` (per half-cell, global-cell coords) or `ApplyAttrToTerrainByTile` (bulk, per sector).
- `WorldEditorWrapper.BatchSetAttrRegion` (`main.py:951-958`, via the forwarder at `main.py:366-367`) calls `SetAttrAt` in a loop and inherits the bug.

### 1.4 The 3×3 resident window — why "whole map" loops don't cover the whole map

`MapOutdoor.h:18-20`: `LOAD_SIZE_WIDTH = 1`, `AROUND_AREA_NUM = 1 + (1*2)*(1*2)*2 = 9`.

`CMapOutdoor::AssignTerrainPtr` (`MapOutdoorLoad.cpp:107-154`) fills `m_pTerrain[9]` / `m_pArea[9]` **only** with sectors inside `m_CurCoordinate ± 1`. Every sector ever loaded lives in `m_TerrainVector`, but `GetTerrainPointer(byTerrainNum)` (`MapOutdoor.cpp:913-928`) indexes `m_pTerrain[0..8]` only.

`m_CurCoordinate` is advanced only by `CMapOutdoor::Update(x,y,z)` (`MapOutdoorUpdate.cpp:57-107`), reached from `CMapManagerAccessor::UpdateMap`, which is called from `CSceneMap::OnUpdate` (`SceneMap.cpp:198`) — i.e. **once per rendered frame**. `UpdateMap` is **not exposed to Python**.

Therefore, for a Python script running synchronously:

- `PreloadTerrainAndArea(sx, sy)` and `PreloadAllTerrainsAndAreas()` **load the data into `m_TerrainVector`** but do **not** put it into the addressable window.
- `GetTerrainNumFromCoord(sx, sy)` returns a usable slot only for `|sx - curX| <= 1 && |sy - curY| <= 1`.
- Everything that loops the map inside C++ — `PlaceGrassPropsByTexture`, `RefreshAllTerrainAttrs`, `CleanupWaterWithoutAttr`, `GetTerrainUsedTextures`, `GetTileValueAt`, `ApplyAttrToTerrainByTile`, `DeleteObjectsByCRCList(scope=2)`, `ReplaceObjectsByCRC(scope=2)` — **actually only touches the ≤9 sectors around the camera**, silently skipping the rest (`GetTerrainNumFromCoord` fails → `continue`).
- The one exception is `SetAllWaterHeight`, which iterates `m_TerrainVector` directly (`MapManagerAccessor.cpp:1940-1954`) and then does a save/close/reload cycle.

**The editor's own idiom for a whole-map pass** is the regen loop, `SceneMap.cpp:245-266`:

```cpp
for (y…) for (x…) {
    pView->UpdateTargetPosition(-target.x + x*TERRAIN_XSIZE, -target.y - y*TERRAIN_YSIZE);
    D3DXVECTOR3 p = ms_Camera->GetTarget();
    m_pMapManagerAccessor->SetTerrainModified();
    m_pMapManagerAccessor->UpdateMap(p.x, p.y, 0.0f);   // <-- the window shift
    …per-sector work…
}
```

A generator cannot reproduce this from Python, because `UpdateMap` has no binding. Practical options:

1. Keep every edit within the 3×3 window around wherever the camera is, and drive the camera from **outside** Python (headless `--target`, one process per region), or
2. Press F5 repeatedly, moving the camera by hand between runs, or
3. Do the bulk edit **on the files** (the `m2map` codec) and use the editor only for verification screenshots.

Option 3 is what this skill should do for anything larger than 3×3 sectors.

### 1.5 Selection index spaces do not agree

| Binding | Which area it reads |
|---|---|
| `GetObjectCount`, `GetObjectData`, `GetObjectDataCount`, `GetObjectHeightBias`, `SetObjectHeightBias`, `GetObjectRotation`, `SetObjectRotation`, `GetLastSelectedObjectData`, `AccumulateSelectionPivot`, `CollectPortalNumber` | `GetEditArea()` — slot from `m_wEditTerrainNumX/Y` (follows the **editing cursor**) — `MapManagerAccessor.cpp:1560-1575` |
| `SelectObject(i)`, `IsObjectSelected(i)`, `IsIntersectingSelection(i)` | area at `m_iLastPickedAreaIndex` (set by the last mouse pick, or by `SetLastPickedAreaIndex`) — `:1161-1168, 1134-1141` |
| `GetSelectedObjectCount()` | **hard-coded slot 4** (window centre) — `:572-583` |
| `GetPickedObjectIndex()` | scans slots in order `{4,0,1,2,3,5,6,7,8}` and sets `m_iLastPickedAreaIndex` — `:678-690` |
| `CancelSelect`, `DeleteSelectedObject`, `MoveSelectedObject*`, `RotateSelectedObject*`, `SetSelectedObjectRotation`, `ResetSelectedObjectHeightToTerrain`, `IsSelected`, `GetSelectionPivot`, `SelectObjectsByRect` | **all 9 areas** |

So an index from `GetObjectData` is only usable with `SelectObject` when the edit terrain and the last-picked area happen to be the same slot. Before any index-driven work, call `we.SetLastPickedAreaIndex(we.GetEditArea()… )`? — there is no binding that returns the edit **slot** directly; `GetEditTerrainNum()` does return exactly that slot (`(editY-curY+1)*3 + (editX-curX+1)`, `MapManagerAccessor.cpp:1607-1611`). **Idiom:**

```python
we.SetLastPickedAreaIndex(we.GetEditTerrainNum())   # now indices line up
```

---

## 2. Bindings by group

### 2.1 Map lifecycle & identity

| Binding | Signature | Notes |
|---|---|---|
| `IsMapReady()` | `-> int 0/1` | **[V]** 0 when no app/accessor. `:35-44` |
| `IsMapLoaded()` | `-> int 0/1` | **[V]** identical to `IsMapReady`. `:439-448` |
| `GetMapName()` | `-> str` | **[V]** the folder path passed to `LoadMap`. `:427-437` |
| `GetMapType()` | `-> int` | **[V]** `MAPTYPE_INVALID/INDOOR/OUTDOOR`. `:46-56` |
| `GetSceneType()` | `-> int` | **[V]** `SCENE_MAP/OBJECT/EFFECT/FLY/MAX`. `:58-69` |
| `GetBaseXY()` | `-> (int,int)` | **[V]** map origin in **world cm**, from atlasinfo. `:71-83` |
| `GetTerrainCount()` | `-> (int,int)` | **[V]** sectors in x,y. `:85-97` |
| `GetTerrainSize()` | `-> int` | **[V]** constant `128`. **Cells, not cm.** `:383-386` |
| `GetMapBounds()` | `-> (minX,minY,maxX,maxY)` | **[V]** unit-mixing bug (§1.2). |
| `GetMapID()` / `SetMapID(int)` | `-> int` / `-> None` | **[V]** from `index`/atlasinfo lookup; `-1` if not ready. `:4341-4377` |
| `NewMap(str path)` | `-> int 0/1` | **[V]** creates the folder if missing, then builds a new map. `:3057-3072` |
| `CreateNewOutdoorMap()` | `-> int 0/1` | **[V-sig]** uses the pending `SetNewMapName/SizeX/SizeY` values. `:3074-3084` |
| `SetNewMapName(str)` / `SetNewMapSizeX(int)` / `SetNewMapSizeY(int)` | `-> None` | **[V]** stage the parameters for `CreateNewOutdoorMap`. `:3086-3135` |
| `CloseMap()` | `-> None` | **[V]** no auto-save. `:4498-4508` |
| `ReloadMap()` | `-> int 0/1` | **[V]** saves first **iff** `IsAutoSave()`, then `CloseMap` + `LoadMap(sameName)`. `:1688-1704` |
| `UpdateMapInfo()` | `-> None` | **[V]** re-applies BaseXY + TerrainCount from the atlasinfo table. Does **not** move the resident window. `:4463-4475` |
| `UpdateBaseMapInfo(int baseX,int baseY)` | `-> int 0/1` | **[V]** edits the in-memory atlasinfo entry only. `:4477-4496` |
| `GetEnvironmentDataName()` | `-> str` | **[V]** e.g. `ymir work/environment/xxx.msenv`. `:99-109` |
| `TrimMemory()` | `-> None` | **[V-sig]** `MapManagerAccessor::TrimMemory`. `:6110-6110` |
| `PreloadTerrainAndArea(int sx,int sy)` | **space S** `-> None` | **[V]** `LoadTerrain` + `LoadArea`; pushes into `m_TerrainVector`, does **not** add to the 3×3 window. `:4737-4759` |
| `PreloadAllTerrainsAndAreas()` | `-> int 0/1` | **[V]** loops all sectors calling the above. `:4449-4461` → `MapManagerAccessor.cpp:2261-2279` |
| `GetTerrainNum(float x,float y)` | **space W** `-> int` (**space N**) | **[V]** y auto-abs'd. `:3137-3156` |
| `GetEditTerrainNum()` | `-> int` (**space N**) | **[V]** slot of the current edit terrain. `:3158-3170` |
| `GetTerrainNumFromCoord(int sx,int sy)` | **space S** `-> int` (**space N**) or `-1` | **[V]** §1.4. `:4778-4802` |
| `GetEditArea()` | `-> (editX,editY,subX,subY,terrainNumX,terrainNumY)` | **[V]** `editX/editY` = **space L** cell, `subX/subY` = 0..7 half-cell, `terrainNumX/Y` = **space S**. `:1802-1817` |
| `GetEditTerrain()` | `-> int 0/1` | **[V]** just "is there an edit terrain". `:4510-4524` |
| `SetTerrainModified()` | `-> None` | **[V]** marks dirty so `SaveTerrains` writes. `:4526-4538` |
| `RefreshTerrain()` | `-> None` | **[V]** identical body to `SetTerrainModified` — calls `SetTerrainModified()`. `:1660-1672` |
| `GetLastPickedAreaIndex()` / `SetLastPickedAreaIndex(int)` | `-> int` / `-> None` | **[V]** **space N**. See §1.5. `:4540-4566` |

### 2.2 Camera

| Binding | Signature | Notes |
|---|---|---|
| `GetTargetPosition()` | `-> (float x, float y)` | **[V]** camera target, **world cm**, y negative. `:136-151` |
| `UpdateTargetPosition(int dx,int dy)` | `-> None` | **[V]** **relative** move in world cm, clamped to map bounds, camera z re-fit to terrain+100. **Integer args only** — passing a float yields `-1` (§0.1). `:153-171` → `SceneMap.cpp:1958-1978` |
| `GetCameraPosition()` | `-> (x,y,z)` | **[V]** eye, world cm. `:232-244` |
| `GetCameraTarget()` | `-> (x,y,z)` | **[V]** target, world cm. `:246-258` |
| `SetCameraPosition(fx,fy,fz)` | `-> None` | **[V]** sets eye, keeps target/up, calls `SetViewParams`. `:260-288` |
| `SetCameraTarget(fx,fy,fz)` | `-> None` | **[V]** `pCamera->SetTarget`. Does **not** call `UpdateMap`, so the resident window does not move. `:290-316` |

### 2.3 Terrain height

All height values are **raw uint16 heightmap samples** (`worldZ_cm = raw * 0.5`).

| Binding | Signature | Notes |
|---|---|---|
| `GetHeightPixel(int x,int y)` | **space C** `-> int raw` | **[V]** `GetHeightPixel(x/128, y/128, x%128, y%128)`. `:173-199` |
| `DrawHeightPixel(int x,int y,int h)` | **space C** `-> None` | **[V]** the **only** binding that checks `PyErr_Occurred()`. Writes the raw sample, recomputes normals + patch, `RAW_UpdateAttrSplat`. `:201-230` |
| `GetHeightAt(float x,float y)` | **space C** (despite float args) `-> int raw` | **[V]** identical body to `GetHeightPixel` with a `(long)` cast. `:318-347` |
| `SetHeightAt(float x,float y,int h)` | **space C** `-> None` | **[V]** identical to `DrawHeightPixel`, minus the error check. `:349-381` |
| `GetHeightRegion(x1,y1,x2,y2)` | **space C**, ints `-> list[int]` | **[V]** row-major, `(x2-x1+1)*(y2-y1+1)` entries; swaps if `x1>x2`. `:516-570` |
| `DrawHeightRegion(x1,y1,x2,y2,h)` | **space C**, ints `-> None` | **[V]** per-pixel loop; swaps if inverted. No patch batching — slow for large regions. `:473-514` |
| `DrawHeightBrush(fx,fy,shape,type,size,strength[,refreshObjects])` | **broken space** `-> None` | **[V]** see §1.2. `shape` ∈ `BRUSH_SHAPE_*`, `type` ∈ `BRUSH_TYPE_UP/DOWN/PLATEAU/NOISE/SMOOTH`, `size`/`strength` are BYTEs. Optional 7th arg (int) → also calls `RefreshObjectHeight(fx, fy, size*200)`. `:2086-2131` |
| `ArrangeTerrainHeight()` | `-> None` | **[V-sig]** `CMapOutdoorAccessor::ArrangeTerrainHeight` — stitches sector-edge heights. `:4761-4776` |
| `WorldToTerrainCoords(fx,fy)` | **space C** `-> (tnx,tny,cellX,cellY)` | **[V]** pure arithmetic, no map needed. `:388-406` |
| `TerrainToWorldCoords(tnx,tny,cx,cy)` | `-> (x,y)` in **space C** | **[V]** pure arithmetic. `:408-425` |
| `GetTerrainWorldBounds(int sx,int sy)` | `-> (minX,minY,maxX,maxY)` | **[V]** unit-mixing bug (§1.2). `:4903-4931` |

### 2.4 Textures / splatting

Texture indices are into the map-global `CTextureSet` (from `textureset/*.txt`). **Index 0 is the eraser/blank entry** (`TextureSet.cpp:105-107`); real textures are `1 … GetTextureCount()-1`.

| Binding | Signature | Notes |
|---|---|---|
| `DrawTextureBrush(fx,fy,list texNums,int size,int erase,int onlyBlank)` | **space C** `-> None` | **[V]** correctly forwards `(terrainNumX, terrainNumY, cellX, cellY, subX, subY)` to `CMapOutdoorAccessor::DrawTextureBrush`, so it does reach the right sector — unlike the attr/height brushes. `texNums` must be a **list** of ints (a random one is chosen per tile). `subX/subY = (cell%4)*2`. `:2252-2311` |
| `SetTextureBrushVector(list)` | `-> None` | **[V]** sets the UI brush's texture list. No map required. `:5685-5718` |
| `SetInitTextureBrushVector(list)` | `-> None` | **[V]** the "base texture" list used by `InitBaseTexture`. `:5720-5755` |
| `SetEraseTexture(int)` / `SetDrawOnlyOnBlankTile(int)` | `-> None` | **[V]** UI toggles for the interactive brush; `DrawTextureBrush` takes its own flags instead. `:2313-2345` |
| `AddTerrainTexture(str filename)` | `-> int 0/1` | **[V]** appends to the global `CTextureSet` with `uScale=vScale=4.0`, `uOffset=vOffset=0`, `bSplat=true`, `texCoordBase = 1/(16*200)`; then `ResetTerrainTexture()`. New index = `GetTextureCount()-1` after the call. Rejects duplicates by filename and refuses at 256. `:2347-2364` → `MapManagerAccessor.cpp:739-750`, `TextureSet.cpp:197-252` |
| `RemoveTerrainTexture(int idx)` | `-> int 0/1` | **[V]** `vector::erase` — **shifts every higher index down**, silently invalidating every `tile.raw` byte above `idx`. Practically unusable on a populated map. `:2366-2383` |
| `ResetTerrainTexture()` | `-> None` | **[V-sig]** rebuilds splat resources for all terrains. `:2385-2397` |
| `InitBaseTexture([str mapName])` | `-> int 0/1` | **[V]** fills every tile with the init-brush vector. Optional arg. `:2399-2419` |
| `GetTerrainTextureFilename(int idx)` | `-> str` | **[V]** raises (`RuntimeError`-ish, see §0.1) when out of range — this is how `GetTextureIdsByPattern` in `terrain_operations.py` finds the end. Works with **no map loaded** (reads the static `CTerrain::GetTextureSet()`). `:4821-4838` |
| `GetTerrainUsedTextures(int sx,int sy)` | **space S** `-> list[int]` | **[V]** distinct non-zero bytes of that sector's `tile.raw`. Calls `PreloadTerrainAndArea` first, then `GetTerrainNumFromCoord` — so it fails outside the 3×3 window (§1.4). `:4840-4901` |
| `GetTileValueAt(float x,float y)` | **space C** `-> int` or `-1` | **[V]** reads `tileMap[(cellY*2+1)*258 + (cellX*2+1)]` — sub-tile (0,0) of the cell. `-1` if the sector is not in the window or the tilemap is null. `:4933-4984` |
| `RAW_ResetTextures()` | `-> None` | **[V]** rebuilds tile splats for the **edit terrain only**. `:4804-4819` |
| `ReloadTerrainTextures()` | `-> None` | **[V-sig]** `:5757-5772` |
| `ReloadBuildingTexture()` | `-> None` | **[V-sig]** `:5774-5789` |
| `GetSplatValue()` / `SetSplatValue(float)` | `-> float` / `-> None` | **[V]** global splat-alpha **UV scale**, not per-pixel alpha (§1.2). `:4699-4735` |

### 2.5 Attributes

Attr map is 256×256 per sector, one byte per **half-cell** (100 cm). Flags are a bitmask: `ATTRIBUTE_BLOCK=1`, `ATTRIBUTE_WATER=2`, `ATTRIBUTE_BANPK=4`.

| Binding | Signature | Notes |
|---|---|---|
| `GetAttrAt(float x,float y)` | **space W, positive y** `-> int` | **[V]** returns `0` when out of range (indistinguishable from "no flags"). `:1441-1463` |
| `IsAttrOn(float x,float y,int flag)` | **space W, positive y** `-> int 0/1` | **[V]** `:1500-1523` |
| `SetAttrAt(float x,float y,int flag)` | **BROKEN — do not use** | **[V]** §1.3. `:1465-1498` |
| `DrawAttrBrush(fx,fy,flag,size,erase)` | **BROKEN — do not use** | **[V]** §1.3. `size` is the radius in cells; the brush is always `BRUSH_SHAPE_CIRCLE` regardless of `SetBrushShape`. `:1525-1563` |
| `SetAttrAtWorld(float x,float y,int flag)` | **space C** (name lies) `-> None` | **[V]** ORs `flag` into one half-cell of the correct sector, then `RAW_UpdateAttrSplat()`. Fails with an exception if the sector is outside the 3×3 window. This is the correct per-pixel setter. `:4986-5033` |
| `ApplyAttrToTerrainByTile(int sx,int sy,list texIds,int flag)` | **space S** `-> int pixelsSet` | **[V]** the bulk workhorse. Calls `PreloadTerrainAndArea(sx,sy)`, maps each of the 256×256 attr pixels to `tileMap[(ay+1)*258+(ax+1)]`, and ORs `flag` where the tile id is in `texIds`. Only ids `1..255` are honoured (`if (texId > 0 && texId < 256)`). Returns `0` (not an exception) if the sector isn't addressable. Calls `RAW_UpdateAttrSplat()` at the end. `:5035-5123` |
| `RefreshAllTerrainAttrs()` | `-> int terrainsRefreshed` | **[V]** loops all sectors: `PreloadTerrainAndArea`, `RAW_NotifyAttrModified`, `RAW_UpdateAttrSplat`; then `SetTerrainModified()` + `pView->Invalidate(FALSE)`. Subject to §1.4 — the count tells you how many sectors were actually reachable. `:5125-5170` |
| `GetSelectedAttrFlag()` / `SetSelectedAttrFlag(int)` | `-> int` / `-> None` | **[V]** the UI brush's current flag. Not required by `SetAttrAtWorld`/`ApplyAttrToTerrainByTile`. `:1565-1591` |
| `SetEraseAttr(int)` | `-> None` | **[V]** UI toggle for the interactive attr brush. `:2984-2999` |
| `ResetToDefaultAttr()` | `-> int 0/1` | **[V-sig]** `MapManagerAccessor::ResetToDefaultAttr`. `:1593-1605` |
| `RenderAttr()` | `-> None` | **[V-sig]** immediate-mode debug draw. `:4407-4419` |
| `RenderAccessorTerrain(int renderMode,int attrFlag)` | `-> None` | **[V-sig]** `CMapOutdoorAccessor::RenderAccessorTerrain((BYTE)mode,(BYTE)flag)`. `:5550-5572` |

### 2.6 Water

Water map is 128×128 per sector (one sample per cell). A sample of `0xFF` means "no water"; otherwise it indexes the sector's 256-entry water-height table. Water heights are **raw uint16** on the same scale as terrain height.

| Binding | Signature | Notes |
|---|---|---|
| `GetWaterHeight(float x,float y)` | **space W** `-> int raw` or `-1` | **[V]** `CMapOutdoor::GetWaterHeight(int,int)` divides the sector-local offset by `WATERMAP_XSIZE` (**128**) rather than `CELLSCALE` (200) — `MapOutdoor.cpp:632-653`. This is an **upstream engine bug**: the sampled cell is wrong by a factor of 200/128. Treat the return as unreliable; read `water.wtr` with the codec instead. `:1948-1969` |
| `DrawWaterBrush(fx,fy,int waterHeight,int size,int erase)` | **space C** `-> None` | **[V]** correctly forwards `(terrainNumX, terrainNumY, cellX, cellY)` to `CMapOutdoorAccessor::DrawWaterBrush`. Shape is always `BRUSH_SHAPE_CIRCLE`. `waterHeight` is cast to `WORD`. `:1971-2006` |
| `SetAllWaterHeight(int h)` | `-> None` | **[V]** **the only whole-map binding that really covers the whole map**: `PreloadAllTerrainsAndAreas()` then iterates `m_TerrainVector` directly, then `SaveMap` + `CloseMap` + `LoadMap`. Destructive and it *saves*. `:2008-2025` → `MapManagerAccessor.cpp:1932-1955` |
| `GetNumWater()` / `SetNumWater(int)` | `-> int` / `-> None` | **[V]** count of used water-height slots on the **edit terrain**. `:4586-4622` |
| `GetWaterHeightArray()` | `-> list[int]` of **256** | **[V]** the edit terrain's `m_lWaterHeight[0..MAX_WATER_NUM]`. `:4624-4654` |
| `SetWaterHeightArray(list)` | `-> None` | **[V]** copies up to 256 entries; **pads the remainder with `-1`**. Shorter lists therefore clear the tail. `:4656-4697` |
| `GetBrushWaterHeight()` / `SetBrushWaterHeight(int)` | `-> int` / `-> None` | **[V]** UI brush value. `:2027-2053` |
| `SetEraseWater(int)` | `-> None` | **[V]** UI toggle. `:2055-2070` |
| `PreviewEditWater()` | `-> None` | **[V-sig]** `MapManagerAccessor::PreviewEditWater`. `:2072-2084` |
| `CleanupWaterWithoutAttr()` | `-> (cleaned, checked, withWater, withWaterAttr, withWaterNoAttr, totalWaterPixels, waterPixelsWithAttr)` | **[V]** for each water sample ≠ `0xFF`, checks the 2×2 attr block at `(waterX*2, waterY*2)` for `ATTRIBUTE_WATER`; if none of the four has it, sets the sample to `0xFF` and flags the patch dirty. On any change: `SetNumWater(0)` + `CalculateTerrainPatch()`. Ends with `SetTerrainModified()` + `Invalidate`. Subject to §1.4. **Note `SetNumWater(0)` wipes the sector's water-height table binding**, so a partially-cleaned sector loses its remaining water heights. `:5172-5339` |

### 2.7 Objects & selection

`CArea::TObjectData` (`Client/gamelib/Area.h:24-47`):

```cpp
TObjectPosition Position;       // D3DXVECTOR3, world cm, y negative, z = terrain height
DWORD           dwCRC;          // property CRC
BYTE            abyPortalID[PORTAL_ID_MAX_NUM];
float           m_fYaw, m_fPitch, m_fRoll;   // degrees, normalised to [0,360)
float           m_fHeightBias;  // cm added to Position.z at render time
DWORD           dwRange;                     // ambience only
float           fMaxVolumeAreaPercentage;    // ambience only
```

| Binding | Signature | Notes |
|---|---|---|
| **`InsertObject(fx,fy,fz,fYaw,fPitch,fRoll,int scale,int crc)`** | **8 args**, world cm `-> None` | **[V]** **`fz` is NOT a z coordinate — it becomes `m_fHeightBias`.** `Position.z` is recomputed as `pTerrainAccessor->GetHeight((int)fx, -(int)fy)`. `fy` must be **negative** (editor convention); the `-(int)fy` inside is what makes the height lookup work. Angles are normalised into `[0,360)` by `while` loops. `scale` is only used for `PROPERTY_TYPE_AMBIENCE`, where it becomes `dwRange` (and `fMaxVolumeAreaPercentage` is read from the property). Fails **silently** if the CRC is not in `CPropertyManager`, or if the target sector is not in the 3×3 window (`GetTerrain`/`GetArea` return false). `:1146-1178` → `MapManagerAccessor.cpp:647-700` |
| **`GetObjectData(int idx)`** | `-> (x, y, z, crc, yaw, pitch, roll)` | **[V]** 7-tuple. `crc` is **signed** (§1.2) — compare with `crc & 0xFFFFFFFF` or `struct`-convert. Index is into the **edit area** (§1.5). Raises "Invalid object index" out of range. **Does not expose `m_fHeightBias`** — use `GetObjectHeightBias(idx)`. `:708-731` |
| `GetObjectCount()` / `GetObjectDataCount()` | `-> int` | **[V]** identical bodies; count in the **edit area**. `0` if not ready. `:692-706` and `:1786-1800` |
| `GetObjectHeightBias(int idx)` | `-> float` | **[V]** edit area. `:5974-5995` |
| **`SetObjectHeightBias(int idx,float bias)`** | `-> None` | **[V]** writes `m_fHeightBias` **directly on the struct**. Does **not** call `UpdateObject`, so the rendered instance does not move until something else refreshes it (`RefreshObjectHeight`, area reload). Also **not undoable** — no `BackupObject` is taken. `:5997-6022` |
| `GetObjectRotation(int idx)` | `-> (yaw,pitch,roll)` | **[V]** edit area. `:6024-6045` |
| **`SetObjectRotation(int idx,fYaw,fPitch,fRoll)`** | `-> None` | **[V]** writes the three floats **directly**, no normalisation, no `UpdateObject`, no undo backup. Pass values already in `[0,360)`. `:6047-6078` |
| `SelectObject(int idx)` | `-> None` | **[V]** acts on `m_iLastPickedAreaIndex` (§1.5). Returns `None`, **not** a bool. |
| `SelectObjectsByRect(fx1,fy1,fx2,fy2)` | world cm `-> int 0/1` | **[V]** strict `>`/`<`, no swap; also **deselects** anything now outside the rect. `:620-643` |
| `CancelSelect()` | `-> None` | **[V]** all 9 areas. `:645-657` |
| `IsObjectSelected(int idx)` | `-> int 0/1` | **[V]** last-picked area. `:659-676` |
| `IsSelected()` | `-> int 0/1` | **[V]** "is anything selected" across all 9. `:4196-4207` |
| `GetSelectedObjectCount()` | `-> int` | **[V]** **slot 4 only** (§1.5). `:572-583` |
| `GetSelectedObjectName()` | `-> str` | **[V]** `"No object selected"` when not ready. `:585-599` |
| `SetSelectedObjectName(str)` | `-> None` | **[V-sig]** `CMapOutdoorAccessor::SetSelectedObjectName`. `:5460-5480` |
| `GetPickedObjectIndex()` | `-> int` or `-1` | **[V]** scans `{4,0,1,2,3,5,6,7,8}` and updates `m_iLastPickedAreaIndex`. `:678-690` |
| `IsIntersectingSelection(int idx)` | `-> int 0/1` | **[V]** last-picked area. `:4568-4584` |
| **`MoveSelectedObject(fdx,fdy)`** | **relative**, world cm `-> None` | **[V]** applies to every selected object in all 9 areas. Does not touch z; the instance transform is refreshed inside `__RefreshObjectPosition`. `:733-752` |
| `MoveSelectedObjectHeight(fdz)` | **relative** `-> None` | **[V]** adds to `Position.z` (not to `m_fHeightBias`). `:754-771` |
| `ResetSelectedObjectHeightToTerrain()` | `-> None` | **[V-sig]** `:773-785` |
| `RotateSelectedObject(y,p,r)` | **relative degrees** `-> None` | **[V]** `AddSelectedObjectRotation`. `:787-808` |
| `SetSelectedObjectRotation(y,p,r)` | **absolute degrees** `-> None` | **[V]** calls the accessor with `bSetYaw=bSetPitch=bSetRoll=true`; values are normalised into `[0,360)`. `:810-831` |
| `RotateSelectedObjectAroundPivot(fRollDeg)` | `-> None` | **[V]** pivot = mean of `(x, y, z + heightBias)` over all selected objects across all 9 areas. `:833-850` |
| `GetSelectionPivot()` | `-> (x,y,z)` | **[V]** same mean; **raises** when nothing is selected. `:1357-1371` |
| `AccumulateSelectionPivot()` | `-> (x,y,z)` | **[V]** same idea but **edit area only**, returns `(0,0,0)` when empty instead of raising. `:5383-5409` |
| `DeleteSelectedObject()` | `-> None` | **[V]** all 9 areas. `:852-864` |
| **`DeleteObjectsByCRCList(list crcs[, int scope=1])`** | `-> int deletedCount` | **[V]** `scope`: `0` = the edit sector only, `1` = the 3×3 around the edit sector (**default**), `2` = the full `countX × countY` loop. CRCs are read with `PyLong_AsUnsignedLong`, so pass **unsigned** values. Empty list → exception. For each sector: `PreloadTerrainAndArea`, `GetTerrainNumFromCoord`, `CancelSelect`, select every matching index, `DeleteSelectedObject`. **Scope 2 is limited by §1.4.** `:866-986` |
| **`ReplaceObjectsByCRC(srcCrc,dstCrc[, int scope=1])`** | `-> int replacedCount` | **[V]** same scope semantics. Captures only `(x, y, m_fHeightBias, yaw, pitch, roll)` per matched object, deletes them, then `InsertObject(x, y, heightBias, yaw, pitch, roll, 0, dstCrc)`. **Lost in the round trip:** portal IDs, `dwRange`, `fMaxVolumeAreaPercentage`, and the original `Position.z` (recomputed from terrain). `scale` is forced to `0`. `:988-1144` |
| **`PlaceGrassPropsByTexture(list texIds,list crcs[, float minDistM=10.0])`** | `-> (inserted, skipped)` | **[V]** two passes over all sectors. Pass 1 collects positions of every existing object whose CRC is in `crcs`. Pass 2 walks the 256×256 attr grid of each sector **skipping a 2-pixel border** (`attrX < 2 || attrX >= 254`), reads `tileMap[(attrY+1)*258 + (attrX+1)]`, and where the tile id is in `texIds` places a random CRC from `crcs` at the half-cell centre with `roll = rand()%360`, `yaw = pitch = 0`, `heightBias = 0`, `scale = 0`. Rejection radius is `minDistM * 100` cm, checked against a **linear scan** of all placed positions → O(n²), very slow past a few thousand props. `texIds` are filtered to `1..255`. Subject to §1.4. `:1180-1355` |
| `CopySelectedObjects()` / `CopySelectedObjectsToClipboard()` | `-> None` | **[V]** identical bodies. `:1875-1887` and `:5482-5494` |
| `PasteObjects(fx,fy,fz)` / `PasteObjectsFromClipboard(fx,fy,fz)` | world cm `-> None` | **[V]** identical bodies; the vector is the paste base. `:1889-1911` and `:5496-5518` |
| `SetSelectedObjectPortalNumber(int)` / `DelSelectedObjectPortalNumber(int)` | `-> None` | **[V]** `:1373-1409` |
| `GetSelectedObjectPortalNumbers()` / `GetSelectedObjectPortalVectorRef()` | `-> list[int]` | **[V]** identical bodies. `:1411-1439` and `:5520-5548` |
| `CollectPortalNumber()` | `-> list[int]` | **[V]** distinct portal ids in the **edit area**. `:5411-5441` |
| `ClearSelectedPortalNumber()` | `-> None` | **[V-sig]** `:5443-5458` |
| `EnablePortal(int)` | `-> None` | **[V-sig]** `:4177-4194` |
| `GetLastSelectedObjectData()` | `-> dict` | **[V]** keys: `position` (x,y,z), `rotation` (yaw,pitch,roll), `crc` (**signed**), `height_bias` (float), `range` (int), `max_volume_area_percentage` (float). Empty dict when nothing selected. Edit area. `:5341-5381` |
| `AddSelectedAmbienceScale(int)` | `-> None` | **[V-sig]** relative. `:4209-4226` |
| `AddSelectedAmbienceMaxVolumeAreaPercentage(float)` | `-> None` | **[V-sig]** relative. `:4228-4245` |
| `RefreshObjectHeight(fx,fy,fHalfSize)` | world cm `-> None` | **[V]** for every object in all 9 areas within an axis-aligned `fHalfSize` box of `(fx,fy)`, sets `Position.z = GetTerrainHeight(x, -y)` and calls `UpdateObject`. Skips `PROPERTY_TYPE_DUNGEON_BLOCK`. Use this after any height edit that moved ground under props. `:1637-1658` → `MapManagerAccessor.cpp:702-737` |
| `RefreshArea()` | `-> None` | **[V-sig]** `:1607-1619` |
| `RefreshSelectedInfo()` | `-> None` | **[V]** compiled out unless `CWE_AREA_ACCESSOR_MISSING_REFRESH`. `:1621-1635` |
| `GetPropertyType(int)` | `-> str` | **[V]** swapped name (§1.2). `:111-119` |
| `GetPropertyExtension(str)` | `-> int` | **[V]** swapped name. `:121-129` |
| `GetObjectList(...)` | `-> ()` | **[V]** stub. `:131-134` |

### 2.8 Monster areas (MAI)

| Binding | Signature | Notes |
|---|---|---|
| `AddNewMonsterAreaInfo(originX,originY,sizeX,sizeY,type,vid,count,dir)` | **8 ints** `-> 0` on success / `-1` | **[V]** all args `long`. `type` ∈ `MONSTERAREAINFOTYPE_*`, `dir` ∈ `MONSTER_DIR_*`. Origin/size are passed through untouched to `CMapOutdoor::AddMonsterAreaInfo(lOriginX, lOriginY, lSizeX, lSizeY)` — **space unverified at the MAI layer**, but the MAI file format stores world cm (see `reference/mapformat`). `:3386-3420` |
| `GetMonsterAreaInfoCount()` | `-> int` | **[V]** `:3298-3310` |
| `GetSelectedMonsterAreaInfo()` | `-> 0` / `-1` | **[V]** useless return (§1.2). `:3312-3327` |
| `RemoveMonsterAreaInfoPtr(int vectorIndex)` | `-> int 0/1` | **[V]** looks the pointer up by vector index, then removes it. `:5832-5854` |
| `SelectNextMonsterAreaInfo([int forward=1])` | `-> None` | **[V]** optional arg. `:3329-3349` |
| `SelectMonsterAreaInfoStart()` / `SelectMonsterAreaInfoEnd()` / `IsSelectMonsterAreaInfoStarted()` | `-> None`/`-> None`/`-> int` | **[V]** rubber-band selection state. `:3351-3384` |
| `SaveMonsterAreaInfo()` | `-> int 0/1` | **[V-sig]** writes the MAI file. Also called implicitly by `SaveMap`. `:3284-3296` |
| `ShowAllMonsterAreaInfo(int)` / `IsShowAllMonsterAreaInfo()` | `-> None`/`-> int` | **[V]** render toggle. `:3256-3282` |
| `SetMonsterNames()` | `-> None` | **[V-sig]** re-resolves vnum → name labels. `:5856-5871` |
| `SetMonsterAreaInfoEditing(int)` / `IsMonsterAreaInfoEditing()` | `-> None`/`-> int` | **[V]** `:2928-2954` |

### 2.9 Environment, lighting, sky, flare

All of these require `IsMapReady()`; all are **[V]** at the binding level and **[V-sig]** for the accessor unless noted. Colours are floats in `0..1`.

**Light / fog / wind / material / screen filter**
`SetLightDirection(x,y,z)`, `SetLightDiffuseColor(r,g,b)`, `SetLightAmbientColor(r,g,b)`, `EnableLight(int)`, `SetFogColor(r,g,b)`, `SetFogNearDistance(float cm)`, `SetFogFarDistance(float cm)`, `EnableFog(int)`, `SetWindStrength(float)`, `SetWindRandom(float)`, `EnableWind(int)` *(may be `#ifdef`-ed out)*, `SetMaterialDiffuseColor(r,g,b)`, `SetMaterialAmbientColor(r,g,b)`, `SetMaterialEmissiveColor(r,g,b)`, `SetFilteringColor(r,g,b)`, `SetFilteringAlpha(float)`, `SetFilteringAlphaSrc(int)`, `SetFilteringAlphaDest(int)`, `EnableFiltering(int)` — all `-> None`. `:2421-2814`

**Read-back**
`GetEnvironmentData()` **[V]** `-> dict` with `light_direction`, `light_diffuse`, `light_ambient`, `material_diffuse`, `material_ambient`, `material_emissive`, `fog_color` (all 3-tuples), `light_enable`, `fog_enable` (0/1), `fog_near`, `fog_far` (floats). Only the `ENV_DIRLIGHT_BACKGROUND` light is exposed. Empty dict if the env data pointer is null. `:5625-5683`

**Scripts / refresh**
`LoadEnvironmentScript(str)`, `SaveEnvironmentScript(str)`, `InitializeEnvironmentData()`, `RefreshEnvironment()`, `RefreshScreenFilter()`, `RefreshSkyBox()`, `RefreshLensFlare()` — all `-> None`. `:4248-4358, 1648-1660`

**Skybox** (`:4313-4325`) — every getter/setter pair below writes **directly through a reference**, so no refresh happens automatically; call `RefreshSkyBox()` after:
`SetSkyBoxTextureRenderMode(int)` / `IsSkyBoxTextureRenderMode()`,
`SetSkyBoxFaceTexture(str filename,int faceIndex)` / `GetSkyBoxFaceTexture(int faceIndex) -> str`,
`GetSkyBoxScale() -> (x,y,z)` / `SetSkyBoxScale(x,y,z)`,
`GetSkyBoxCloudScale() -> (x,y)` / `SetSkyBoxCloudScale(x,y)`,
`GetSkyBoxCloudTextureScale() -> (x,y)` / `SetSkyBoxCloudTextureScale(x,y)`,
`GetSkyBoxCloudSpeed() -> (x,y)` / `SetSkyBoxCloudSpeed(x,y)`,
`GetSkyBoxCloudHeight() -> float` / `SetSkyBoxCloudHeight(float)`,
`GetSkyBoxCloudTextureFileName() -> str` / `SetSkyBoxCloudTextureFileName(str)`,
`GetSkyBoxGradientUpper() -> int` / `SetSkyBoxGradientUpper(int)` (BYTE),
`GetSkyBoxGradientLower() -> int` / `SetSkyBoxGradientLower(int)` (BYTE),
`InsertGradientUpper()`, `InsertGradientLower()`, `DeleteGradient(int index)`.

**Lens flare** (`:4327-4339`) — same reference-write pattern; call `RefreshLensFlare()`:
`GetLensFlareEnable() -> int` / `SetLensFlareEnable(int)`,
`GetLensFlareBrightnessColor() -> (r,g,b,a)` / `SetLensFlareBrightnessColor(r,g,b,a)`,
`GetLensFlareMaxBrightness() -> float` / `SetLensFlareMaxBrightness(float)`,
`GetMainFlareEnable() -> int` / `SetMainFlareEnable(int)`,
`GetMainFlareTextureFileName() -> str` / `SetMainFlareTextureFileName(str)`,
`GetMainFlareSize() -> float` / `SetMainFlareSize(float)`.

### 2.10 Undo / redo

`CWorldEditorDoc::GetUndoBuffer()`; all **[V]** at the binding level.

| Binding | Signature | Notes |
|---|---|---|
| `Undo()` / `Redo()` | `-> None` | **[V]** raise if there is no document/undo buffer. `:5873-5901` |
| `CanUndo()` / `CanRedo()` | `-> int 0/1` | **[V]** return `0` (never raise) when unavailable. `:5903-5929` |
| `GetUndoCount()` / `GetRedoCount()` | `-> int` | **[V]** `:5931-5957` |
| `ClearUndoBuffer()` | `-> None` | **[V]** `:5959-5972` |
| `BackupObject()` / `BackupTerrain()` | `-> None` | **[V-sig]** push an undo snapshot of the **3×3 window**. Call **before** an edit. `:3001-3027` |
| `BackupObjectCurrent()` / `BackupTerrainCurrent()` | `-> None` | **[V-sig]** snapshot of the **current** sector only. `:3029-3055` |

**`LoadMap` clears the undo buffer** (`MapManagerAccessor.cpp:1957-1969`, `@fixme143`). None of the direct-struct writers (`SetObjectHeightBias`, `SetObjectRotation`, `SetAttrAtWorld`, `ApplyAttrToTerrainByTile`, `CleanupWaterWithoutAttr`) take a backup — those edits are **not undoable**.

### 2.11 Save / export

| Binding | Signature | Notes |
|---|---|---|
| **`SaveMap([str folder])`** | `-> int 0/1` | **[V]** with no arg it saves to `GetMapName()`. Writes, in order: auto-backup (if `IsAutoBackup()`), `SaveMapProperty`, `SaveMapSetting`, `SaveTerrains`, `SaveAreas`, `SaveMonsterAreaInfo`. **Pops a modal `LogBox("Save complete")` unless `IsAutoSave()` is on** — call `we.SetAutoSave(1)` first in a script, or run headless where LogBox is suppressed. Fails if the folder doesn't exist. `:1706-1726` → `MapManagerAccessor.cpp:1343-1462` |
| `SaveMapProperty()` / `SaveMapSetting()` | `-> int 0/1` | **[V]** always to `GetMapName()`; no folder argument. `:1728-1756` |
| `SaveTerrains()` | `-> int 0/1` | **[V]** writes `height.raw` / `tile.raw` / `attr.atr` / `water.wtr` for every **modified** terrain. `:1758-1770` |
| `SaveAreas()` | `-> int 0/1` | **[V]** writes `areadata.txt` etc. `:1772-1784` |
| `SaveMiniMap()` / `SaveAtlas()` | `-> None` | **[V-sig]** `:3228-3254` |
| `UpdateTerrainShadowMap()`, `ReloadTerrainShadowTexture()`, `DestroyShadowTexture()`, `RecreateShadowTexture()` | `-> None` | **[V-sig]** `:3172-3226` |
| **`GenerateServerAttr(str mapPath,int countX,int countY[,int sanitize=0])`** | `-> (code, path, detail)` | **[V]** Reads `<mapPath>\<XXXYYY>\attr.atr` **from disk** for each sector (`ServerAttrGenerator.cpp:55`), LZO-compresses, writes `<mapPath>\server_attr` (`ServerAttrGenerator.cpp:275`). `code` is `server_attr::ErrorCode`: `0 Ok`, `1 OutputNotWritable`, `2 OutputWriteFailed`, `3 AttrNotReadable`, `4 AttrInvalidHeader`, `5 AttrInvalidPayloadSize`, `6 CompressionFailed`, `7 ValidationFailed`, `8 InvalidRequest`. `sanitize != 0` strips non-standard attr bits. **`countX/countY` are parsed with `PyTuple_GetInteger`, and `countX <= 0 || countY <= 0 || empty path` raises.** No map needs to be loaded — it is a pure disk operation, so **`SaveMap`/`SaveTerrains` first**. `:6080-6108` |
| `SetAutoSave(int)` / `IsAutoSave()` | `-> None`/`-> int` | **[V]** `IsAutoSave()` also suppresses the "Save complete" LogBox. `:4098-4124` |
| `SetAutoBackup(int)` / `IsAutoBackup()` | `-> None`/`-> int` | **[V]** backup goes to `globals::dft::AUTO_BACKUP_FOLDER` (default `_backup`), layout per `AUTO_BACKUP_SUBFOLDER_MODE` 0..3. `:4126-4152` |
| `GetTimeSave()` / `SetNextTimeSave()` | `-> int` / `-> None` | **[V]** autosave timer. `:4154-4175` |

### 2.12 Brushes & editing mode

These configure the **interactive** (mouse-driven) brush that `UpdateEditing()` applies; the `Draw*Brush` bindings mostly take their own parameters instead.

| Binding | Signature | Notes |
|---|---|---|
| `SetBrushSize(int)` / `GetBrushSize()` | `-> None`/`-> int` | **[V]** BYTE, radius in cells. `:1819-1845` |
| `SetBrushSizeY(int)` / `GetBrushSizeY()` | `-> None`/`-> int` | **[V]** `:2190-2216` |
| `SetBrushStrength(int)` / `GetBrushStrength()` | `-> None`/`-> int` | **[V]** BYTE. `:1847-1873` |
| `SetBrushShape(int)` / `GetBrushShape()` | `-> None`/`-> int` | **[V]** `BRUSH_SHAPE_NONE=0, CIRCLE=1, SQUARE=2`. `:2133-2159` |
| `SetBrushType(int)` / `GetBrushType()` | `-> None`/`-> int` | **[V]** getter is a **stub returning 0**. Types: `NONE=0, UP=1, DOWN=2, PLATEAU=4, NOISE=8, SMOOTH=16`. `:2161-2188` |
| `SetMaxBrushSize(int)` / `SetMaxBrushStrength(int)` | `-> None` | **[V]** BYTE caps. `:2218-2250` |
| `SetHeightEditing(int)` / `IsHeightEditing()` | `-> None`/`-> int` | **[V]** `:2816-2842` |
| `SetTextureEditing(int)` / `IsTextureEditing()` | | **[V]** `:2844-2870` |
| `SetWaterEditing(int)` / `IsWaterEditing()` | | **[V]** `:2872-2898` |
| `SetAttrEditing(int)` / `IsAttrEditing()` | | **[V]** `:2900-2926` |
| `EditingStart()` / `EditingEnd()` | `-> None` | **[V]** bracket an interactive drag. `:2956-2982` |
| `UpdateEditing()` | `-> None` | **[V]** applies the active brush at `GetEditingCursorPosition()`; for height editing it also calls `RefreshObjectHeight(cursor, brushSize*200)`. `:4435-4447` → `MapManagerAccessor.cpp:395-430` |
| `SetEditingCursorPosition(fx,fy,fz)` / `GetEditingCursorPosition()` | world cm | **[V]** `:4042-4074` |
| `GetPickingCoordinate()` | `-> (x,y,z, cellX,cellY, subX,subY, terrainNumX,terrainNumY)` or `()` | **[V]** 9-tuple; `x,y,z` world cm, `cellX/cellY` **space L**, `subX/subY` half-cell 0..7, `terrainNum*` **space S**. Empty tuple on miss. Depends on the last rendered ray → useless in a headless/synchronous script. `:4076-4096` |
| `GetPickingCoordinateWithRay(ox,oy,oz,dx,dy,dz)` | **6 floats** `-> same 9-tuple or ()` | **[V]** builds `CRay(origin, dir, 10000.0f)` — the range is hard-coded to **10000 cm**, so a ray from a distant camera will miss. Direction is not normalised for you. `:5791-5830` |

### 2.13 Rendering / view

| Binding | Signature | Notes |
|---|---|---|
| `SetWireframe(int)` / `IsWireframe()` / `ToggleWireframe()` | | **[V]** `:1918-1944, 4402-4414` |
| `RenderSelectedObject()`, `RenderAttr()`, `RenderObjectCollision()`, `RenderToShadowMap()`, `RenderShadow()`, `RenderMiniMap()`, `RenderAccessorTerrain(mode,flag)` | `-> None` | **[V-sig]** immediate-mode draws. Calling these outside a render pass has no useful effect. `:4415-4451, 5594-5652` |

### 2.14 Misc / constants

`defWorldEditor()` (`:6510-6595`) registers **66** module ints:

```
SCENE_MAP SCENE_OBJECT SCENE_EFFECT SCENE_FLY SCENE_MAX
MAPTYPE_INVALID MAPTYPE_INDOOR MAPTYPE_OUTDOOR
PROPERTY_TYPE_NONE PROPERTY_TYPE_TREE PROPERTY_TYPE_BUILDING PROPERTY_TYPE_EFFECT
PROPERTY_TYPE_AMBIENCE PROPERTY_TYPE_DUNGEON_BLOCK PROPERTY_TYPE_MAX_NUM
TERRAIN_SIZE(128) TERRAIN_PATCHSIZE(16) TERRAIN_PATCHCOUNT(8) MAXTERRAINTEXTURES(256) MAPBASE(25600)
BRUSH_SHAPE_NONE/CIRCLE/SQUARE/MAX
BRUSH_TYPE_NONE/UP/DOWN/PLATEAU/NOISE/SMOOTH/MAX
BOUNDARY_LOAD_INVALID/NOBOUNDARY/TOPLEFT/TOP/TOPRIGHT/LEFT/RIGHT/BOTTOMLEFT/BOTTOM/BOTTOMRIGHT/ALLBOUNDARY
MONSTERAREAINFOTYPE_INVALID/MONSTER/GROUP
MONSTER_DIR_RANDOM/NORTH/NORTHEAST/EAST/SOUTHEAST/SOUTH/SOUTHWEST/WEST/NORTHWEST
AROUND_AREA_NUM(9) MAX_WATER_NUM(255) ENV_DIRLIGHT_BACKGROUND
TILEMAP_RAW_XSIZE(258) TILEMAP_RAW_YSIZE(258) ATTRMAP_XSIZE(256) ATTRMAP_YSIZE(256)
CELLSCALE_IN_METER(2) HALF_CELLSCALE_IN_METER(1)
ATTRIBUTE_BLOCK(1) ATTRIBUTE_WATER(2) ATTRIBUTE_BANPK(4)
```

Note `MAPBASE` is a literal `25600` written into the module (not derived), and `CELLSCALE` itself is **not** exported — only `CELLSCALE_IN_METER = 2`.

---

## 3. `WorldEditorWrapper` (`lib38/WorldEditorRemixWrapper/main.py`, 1273 lines)

```python
from WorldEditorRemixWrapper import WorldEditorWrapper, CONSTANTS, terrain_operations
WE = WorldEditorWrapper()
```

- `__getattr__` forwards **any** unknown attribute to the `WorldEditor` module, so `WE.Anything` works even without an explicit method.
- ~250 thin methods that mostly just coerce `0/1` ↔ `bool` (`SetWireframe(True)` → `we.SetWireframe(1)`; `IsWireframe()` → `we.IsWireframe() != 0`).
- `CONSTANTS` is a dict snapshot of 34 of the module ints, via `getattr(we, name, None)`.
- Statics: `SceneName(i)`, `PropertyName(i)`, `PrefixEnv()` → `"d:/ymir work/environment/"`.

### Genuinely useful helpers

| Method | What it does |
|---|---|
| `GetRealTargetPosition()` | camera target in **metres, y sign-flipped** (`int(x/100), -int(y/100)`) — this is the coordinate the editor's status bar shows. |
| `AdjustBaseCoordinates(x,y)` | rounds BaseXY down to a multiple of `MAPBASE` (25600) and LogBoxes if it had to. |
| `RecalculateHeightPixel(x,y)` | read-then-write the same height (forces a normal/patch recompute). |
| `AdvanceHeightPixel(x,y,delta)` | read, add, write — the correct way to raise terrain by a fixed raw amount. |
| `GetTerrainBounds()` | `(baseX, baseY, baseX + countX*128, baseY + countY*128)` — inherits the cm/cell unit bug of `GetMapBounds`. |
| `GetHeightmapStatistics(x1,y1,x2,y2)` | min/max/mean/median/std_dev over a **space C** rect. |
| `FindFlatAreas(x1,y1,x2,y2,threshold)` | 2×2 raw-height variation test. |
| `SafeOperation(fn,*a,**kw)` | calls `fn`, and on exception replays `Undo()` while `CanUndo()`. Only helps for operations that actually took an undo backup. |

### Broken / misleading wrapper helpers — do not copy these

| Method | Defect |
|---|---|
| `_find_object_index_by_name`, `FindObjectsByType`, `GetObjectStatistics` | assume `GetObjectData(i)[0]` is a **name string**. It is `x` (a float). `GetPropertyType(float)` then misbehaves. `main.py:924-932, 1001-1010, 1025-1038` |
| `GetObjectBounds(i)`, `FindObjectsInRegion`, `ValidateObjectPlacement` | use `data[1], data[2], data[3]` as `x, y, z`. They are actually `y, z, crc`. `main.py:994-999, 1012-1023, 1128-1139` |
| `BatchMoveObjects` | `if self.SelectObject(idx):` — `SelectObject` returns `None`, so the body never runs. `main.py:910-922` |
| `GetObjectsByPortal`, `ValidatePortals` | same `if self.SelectObject(i):` defect. `main.py:1040-1049, 1157-1174` |
| `BatchSetAttrRegion` | loops the broken `SetAttrAt` (§1.3). `main.py:951-958` (and the `SetAttrAt` forwarder at `main.py:366-367`) |
| `MoveToRealTargetPosition(x,y)` | passes **floats** to `UpdateTargetPosition`, which uses `PyTuple_GetLong` → `TypeError`/`-1` in Python 3 (§0.1). `main.py:248-254` |
| `WorldToPixel` / `PixelToWorld` | divide/multiply by `GetTerrainSize()` (128) and call the result "world" — same cell/cm confusion. `main.py:970-980` |
| `TransactionBegin/End` | a bare counter; no undo grouping actually happens. `main.py:1174-1183` |

---

## 4. `terrain_operations.py` — the worked idioms to follow

`lib38/WorldEditorRemixWrapper/terrain_operations.py` (289 lines). These are the patterns the generator should reuse.

### `GetTextureIdsByPattern(pattern) -> set[int]`
The canonical way to discover texture indices. Starts at **1** (index 0 is the eraser) and walks until `GetTerrainTextureFilename` raises:

```python
texIndex = 1
while True:
    try:
        filename = we.GetTerrainTextureFilename(texIndex)
        if filename and patternLower in filename.lower():
            textureIds.add(texIndex)
        texIndex += 1
    except:
        break
```

Caveat: given §0.1, `Py_BuildException("Texture index out of range")` sets the error *and* returns `None`, so the loop terminates on the resulting `SystemError`/`RuntimeError`. It works, but it is relying on the protocol violation. A cleaner form is to stop when `filename` is empty or falsy.

### `ApplyAttributesByTexturePattern()`
The bulk-attr idiom. Per sector: `GetTerrainNumFromCoord` → skip on `-1` → `PreloadTerrainAndArea` → `ApplyAttrToTerrainByTile` once per flag → accumulate the pixel counts. Finishes with a single `RefreshAllTerrainAttrs()`.

```python
countX, countY = WE.GetTerrainCount()
for y in range(countY):
    for x in range(countX):
        if WE.GetTerrainNumFromCoord(x, y) < 0:
            continue
        WE.PreloadTerrainAndArea(x, y)
        n = we.ApplyAttrToTerrainByTile(x, y, stoneList, we.ATTRIBUTE_BLOCK)
        ...
we.RefreshAllTerrainAttrs()
```

Note the order in the shipped code: `GetTerrainNumFromCoord` is called **before** `PreloadTerrainAndArea`. That is backwards for a cold sector; and neither call escapes §1.4 — sectors outside the 3×3 window silently contribute 0.

### `CleanupWaterWithoutAttr()`
Thin wrapper over the C++ binding; unpacks the 7-tuple and logs each figure. Copy the unpack order:
`(terrainsCleaned, terrainsChecked, terrainsWithWater, terrainsWithWaterAttr, terrainsWithWaterButNoAttr, totalWaterPixels, waterPixelsWithAttr)`.

### `PlaceGrassOnGrassTextures(min_distance_meters=10.0)` and `PlaceObjectsOnSpecificTextures(objectList, texturePrefix, min_distance_meters=10.0)`
Both reduce to `WE.PlaceGrassPropsByTexture(list(textureIds), crcList, min_distance_meters)` and return the `(inserted, skipped)` tuple. `CRCLIST_PLANTS` at the top of the module is the shipped example CRC set, each entry annotated with its property path — **do that for every CRC constant you emit.**

### `DeleteGrassObjectsByCRCList(scope=1)` / `DeleteObjectsByCRCList(objectList, scope=1)`
Both call `we.DeleteObjectsByCRCList(list, scope)` **twice** and report the second result as "remaining". One pass only touches the objects that were selectable in that iteration, so a second pass is the shipped way to confirm convergence — the second return value should be `0`.

### `BatchGenerateServerAttr(mapBasePath, sanitize=False)`
The end-to-end server_attr recipe. For each subdirectory containing `Setting.txt`, parse `MapSize <x> <y>` (`_ParseSettingTxt`: lowercased first token, `int` of the next two), then:

```python
code, path, detail = we.GenerateServerAttr(mapDir, countX, countY, 1 if sanitize else 0)
if code == 0: ...
```

No map needs to be loaded. Returns `(succeeded, failed)`.

### `ReplaceObjectsByCRC(source_crc, target_crc, scope=1)`
Direct pass-through; logs the count.

### `ui.py` (576 lines)
A pure-ctypes Win32 side panel (`WNDCLASSW`, `CreateWindowExW`, a `WNDPROC` callback, a 2 s `WM_TIMER` refresh). It exposes exactly five buttons wired to `terrain_operations`: apply-attrs, cleanup-water, place-grass, delete-grass, replace-objects; plus eight read-only labels (map name, terrain count, base xy, camera pos, real camera pos, selected count, scene type, env). `show_ui()` / `get_or_create_ui()` / `cleanup_ui()` are the entry points; `WorldEditorRemix.py` calls `show_ui()` at the bottom of every F5 run inside a `try/except`. Nothing in it is needed for headless generation — it is only relevant as evidence that the editor's own message loop keeps running while the panel exists.

---

## 5. Headless CLI

Source: `WorldEditor.cpp:243-300` (parsing), `:624-765` (`__ProcessAutomation`), `:766+` (`__SaveSceneShot`), `WorldEditor.h:91-114` (`SAutomation`), `DockingBar/MapFilePage.cpp:432-461` (`ApplyOptionFlag`), `:463-478` (`LoadMapFromPath`).

```
WorldEditorRemix_<Cfg>[_x64].exe
    [--map <dir>] [--file <path>] [--view map|object|effect|fly]
    [--size w,h] [--target x,y] [--cam pitch,roll,dist] [--flags a,-b,+c]
    [--regen] [--atlas] [--shot out.png] [--shot-frames N] [--quit]
```

### Switch semantics — all **[V]**

| Switch | Value | Meaning |
|---|---|---|
| `--map <dir>` | path to a map folder | `CMapFilePage::LoadMapFromPath` → `CMapManagerAccessor::LoadMap`. Sets `bMapReady`, which **gates `--target`, `--flags`, `--regen` and `--atlas`**. |
| `--file <path>` | `.gr2` / `.msm` / `.mse` / `.msf` | loaded into the object / effect / fly scene. `.mse` also calls `PlayLoop()`; `.gr2`/`.msm` call `Refresh() + FitCamera() + MovePosition(0,0)`. An unrecognised extension logs `automation: unsupported --file extension`. |
| `--view <s>` | `map`\|`object`\|`effect`\|`fly` | sends the corresponding `ID_VIEW_*` toolbar command. If omitted but `--file` is given, it is inferred: `.mse`→effect, `.msf`→fly, anything else→object. |
| `--size w,h` | `%d,%d` | resizes the **client** area (window is grown by the frame deltas). Exercises the RT-recreate path. |
| `--target x,y` | `%f,%f`, **world cm** | after the map loads: `UpdateMap(x, -y, 0)` then `UpdateTargetPosition(x - target.x, -y - target.y)`. **You pass a positive y and the editor negates it** (same convention as the Goto dialog). This is the *only* documented way to place the resident 3×3 window. |
| `--cam pitch,roll,dist` | `%f,%f,%f`, degrees/degrees/**cm** | `RotateEyeAroundTarget(pitch - GetPitch(), roll - GetRoll())` then `SetDistance(dist)`, then a `UpdateTargetPosition(0,0)` to refresh the frustum. Applied whether or not the map loaded. |
| `--flags <list>` | comma list, `-x` off, `+x`/`x` on | each token goes to `CMapFilePage::ApplyOptionFlag`. Valid names: `wire grid grid2 patchgrid water compass char collision object objshadow terrain tree effect ambience`. Unknown names log `automation: unknown flag <x>` and are ignored. |
| `--regen` | (no value) | after the map load, sends `VK_INSERT` to the active scene → `CSceneMap` regenerates every sector's shadowmap + minimap (+ MAI atlas) on the following renders. Slow. |
| `--atlas` | (no value) | after the frame count elapses, `GetMapManagerAccessor()->SaveAtlas()` — **writes into the map folder**. |
| `--shot <out.png>` | path | after the frame count, grabs the back buffer → system-memory surface → **PNG**. |
| `--shot-frames N` | int, **default 30** | frames to render before the atlas/shot step. |
| `--quit` | (no value) | `PostMessage(WM_CLOSE)` after the shot. Without it the editor stays open and `SetLogBoxSuppressed(false)` restores modal dialogs. |

### Mechanics you need to know

- **Any** of these switches sets `m_kAuto.bAny`, which sets `iState = 1` and calls `SetLogBoxSuppressed(true)` — modal `LogBox` calls (including `SaveMap`'s "Save complete") are muted for the whole automation run.
- The state machine lives in `CWorldEditorApp::OnIdle` (`WorldEditor.cpp:607-623`). State 1 waits 3 frames for the view to settle, then does size → view → file → map → regen → target → flags → cam, all in one idle tick, and moves to state 2. State 2 counts `iShotFrames` idle ticks, then atlas → shot → state 3 → quit.
- `--map --shot x` (a missing value) is detected: the parser sees a flag where a value was expected, logs `automation: option is missing its value` and drops the pending option.
- Switches are matched **case-insensitively** against `-map`, `-shot`, … — MFC strips the first `-`, so `-map` and `--map` both work.
- **Data-dir requirement.** The process must be started with its **current directory** set to the data root — the one containing `pack/` and `ymir work/`. `InitInstance` does `PackInitialize("pack")` at `WorldEditor.cpp:215` and probes `pack/property.eix` + `pack/property.epk` at `:307-310` before anything else; `CNonPlayerCharacterInfo` then reads `globals::dft::MOB_PROTO_PATH` and `group.txt` relative to the cwd. On this machine that root is `D:\`. Per `CLAUDE.md`, an exe copied into `D:\` must be **gran212-patched** (`granny2.dll` → `gran212.dll` in the import table); `prepare_package.py` does that for releases. The x64 build links granny statically and does not need the patch.
- Config: `WorldEditorRemix.ini` is read from the cwd (`globals::readGlobalConfigs`). `PRELOAD_ALL_TERRAINS` there makes `LoadMapFromPath` call `PreloadAllTerrainsAndAreas()` and disables the save-on-sector-crossing behaviour (`MapAccessorOutdoor.cpp:58-69`).
- Only `MfcRelease`/`MfcDebug` configs exist; binaries land in `Srcs\Tools\bin\`.

### Screenshot verification recipe

```bat
cd /d D:\
WorldEditorRemix_MfcRelease.exe ^
  --map "<CORPUS>\metin2_map_a1" ^
  --target 640000,320000 ^
  --cam 45,0,6000 ^
  --flags terrain,object,tree,water,-grid,-compass ^
  --size 1600,900 ^
  --shot-frames 60 ^
  --shot "C:\tmp\a1_check.png" ^
  --quit
```

- Raise `--shot-frames` when trees/effects still pop in — the count is idle ticks, not seconds.
- `--target` is in **world cm with a positive y**; convert from cell coords with `cellX * 200`, `cellY * 200`.
- Add `--regen` only when you actually changed heights or textures and want the shadowmap/minimap rebuilt; it is slow and it **writes files**.
- For a model or effect instead of a map, use `--file` and skip `--map`/`--target`.

---

## 6. Recipes the generator should follow

### 6.1 Bulk attribute pass from a texture pattern (3×3 window only)

```python
import WorldEditor as we
from WorldEditorRemixWrapper import WorldEditorWrapper, terrain_operations
WE = WorldEditorWrapper()

stone = [i for i in terrain_operations.GetTextureIdsByPattern("stone")]
cx, cy = WE.GetTerrainCount()
total = 0
for sy in range(cy):
    for sx in range(cx):
        WE.PreloadTerrainAndArea(sx, sy)         # load first
        if WE.GetTerrainNumFromCoord(sx, sy) < 0:  # then check addressability
            continue
        total += we.ApplyAttrToTerrainByTile(sx, sy, stone, we.ATTRIBUTE_BLOCK)
we.RefreshAllTerrainAttrs()
we.SetAutoSave(1)          # suppress the modal "Save complete"
we.SaveMap()
```

### 6.2 Place one object correctly

```python
# world cm; y NEGATIVE; the 3rd argument is heightBias, not z
we.InsertObject(float(cellX*200 + 100), -float(cellY*200 + 100),
                0.0,                 # heightBias
                0.0, 0.0, float(yawDeg),   # yaw, pitch, roll  (roll is the ground-plane spin)
                0,                   # scale: only meaningful for AMBIENCE
                crc)                 # unsigned int
```

Note that `PlaceGrassPropsByTexture` puts the ground-plane rotation into **roll** (`rand()%360` as the 6th arg), not yaw — match that if you want props to look like the editor's own.

### 6.3 Read every object in the edit sector, with correct CRCs

```python
we.SetLastPickedAreaIndex(we.GetEditTerrainNum())   # align the index spaces
n = we.GetObjectCount()
for i in range(n):
    x, y, z, crc, yaw, pitch, roll = we.GetObjectData(i)
    crc &= 0xFFFFFFFF                               # the binding returns it signed
    bias = we.GetObjectHeightBias(i)
```

### 6.4 Per-pixel attribute edit (correct setter)

```python
# global CELL coords -- SetAttrAtWorld's name is wrong, it is NOT world cm
we.SetAttrAtWorld(float(cellX), float(cellY), we.ATTRIBUTE_BLOCK)
```

Use `we.GetAttrAt(cellX*200 + 100, cellY*200 + 100)` — **world cm, positive y** — to read it back. The read and the write are in different spaces; there is no way around it.

### 6.5 server_attr for a whole map tree

```python
ok, fail = terrain_operations.BatchGenerateServerAttr("<CORPUS>")
```
or for one map, after saving:
```python
we.SaveMap()
countX, countY = we.GetTerrainCount()
code, path, detail = we.GenerateServerAttr(we.GetMapName(), countX, countY, 0)
assert code == 0, detail
```

### 6.6 Height edit that keeps props on the ground

```python
we.BackupTerrain()                     # undoable
for cy in range(y0, y1+1):
    for cx in range(x0, x1+1):
        h = we.GetHeightPixel(cx, cy)  # raw uint16
        we.DrawHeightPixel(cx, cy, h + delta_raw)   # delta_raw = delta_cm * 2
we.RefreshObjectHeight((x0+x1)*100.0, -(y0+y1)*100.0,
                       max(x1-x0, y1-y0) * 200.0)   # world cm, half-size box
we.SetTerrainModified()
```

---

## 7. Things this API cannot do

- **Move the resident 3×3 sector window from Python.** `CMapManagerAccessor::UpdateMap` is not bound. See §1.4.
- **Run a script from the command line.** F5 in the view is the only trigger.
- **Set an object's absolute position.** Only `MoveSelectedObject(dx,dy)` (relative) and `InsertObject` (create) exist; there is no `SetObjectPosition(index, x, y)`.
- **Set an object's scale.** The `scale` argument of `InsertObject` becomes `dwRange` for ambience only; nothing else reads it.
- **Read the attr/tile/water/height buffers as arrays.** `GetHeightRegion` is the only bulk reader, and it is per-pixel Python calls under the hood. For bulk data, parse the files with the `m2map` codec.
- **Enumerate objects across the whole map.** `GetObjectCount`/`GetObjectData` are edit-area only, and `GetObjectList` is a stub.
- **Distinguish "attr is 0" from "out of range"** — `GetAttrAt` returns `0` for both.

---

# Headless verification — a working recipe

Verified on this machine, 2026-09-08, against a generated map. This is the
fastest way to see whether a map is actually right, and it found three faults no
automated check caught.

## The command

```
cd <data dir>                      # the dir holding pack/ and ymir work/
WorldEditorRemix_MfcRelease_x64.exe \
    --map    d:/map_skill_test_01 \
    --target 12800,12800 \
    --cam    30,0,22000 \
    --size   1600,1000 \
    --shot   d:/map_skill_test_01/_preview/we_render.png \
    --shot-frames 60 \
    --quit
```

Exits 0 and writes the PNG. About 30 s for a 1x1 map, most of it asset loading.

## What each argument actually does

| Argument | Unit / meaning | Notes |
|---|---|---|
| `--map` | map directory | Forward slashes work. Any switch enables headless mode and mutes the LogBox. |
| `--target x,y` | **world centimetres** | The camera look-at. Sector centre is `sector*25600 + 12800`. The status bar shows it in metres, so `12800,12800` reads as `128.00 / 128.00`. |
| `--cam pitch,roll,dist` | degrees, degrees, **cm** | `30,0,22000` gives a raised three-quarter view of one sector. Larger `dist` for bigger maps. |
| `--size w,h` | pixels | Render target size. |
| `--shot <path>` | PNG out | Directory must exist. |
| `--shot-frames N` | frames to settle | **Use 60.** Fewer and terrain streaming or trees may not have finished; the shot comes out half-loaded. |
| `--quit` | — | Exits after the shot. Without it the window stays open. |

## Getting it wrong

- **Run from the data directory.** Not from the map directory and not from the
  repo. The editor resolves `pack/` and `ymir work/` relative to the working
  directory, and without them you get a grey screen with no error.
- **Install the textureset under the data directory first.** `setting.txt` says
  `TextureSet textureset\<name>.txt` and the editor resolves that against its
  working directory, not against the map -- the copy `build_map.py` writes to
  `<map>/textureset/` is not read. Copy it to `<data dir>/textureset/<name>.txt`
  before the first shot. Without it the terrain renders as flat untextured
  colour -- no road, no rock, no green -- with exit code 0, **and the editor
  leaves a 32-byte `TextureCount 0` stub at that path**. The stub is then what
  every later run loads, so overwrite it; checking that the file exists is not
  enough.
- **An exe copied to `D:\` needs the gran212 import patch** (`granny2.dll` ->
  `gran212.dll`). `prepare_package.py` does this for releases. An unpatched copy
  fails at load with no useful message.
- **Aim the camera.** With no `--target` the camera sits at the map corner
  looking outward and the shot is mostly sky. This is the single most common
  reason a headless shot looks broken when the map is fine.
- **Check the render, not the window.** Screen-capturing the editor window
  catches whatever else is on the desktop, including always-on-top utilities.
  `--shot` renders the viewport directly and cannot pick up an overlay.

## Reading the info panel

The left panel reports the loaded map, and two of its fields are easy to
misread:

- **"Topography"** is *not* a map size. It is the row for
  `IDC_STATIC_VIEW_RADIUS` and prints `ViewRadius * CellScale / 100` metres.
  Since the engine doubles `ViewRadius` on load (`MapOutdoorLoad.cpp:387`), a
  normal map with `ViewRadius 128` reads **512.00 meter** regardless of whether
  it is 1x1 or 6x6.
- **"Max"** is the height ceiling (`65535 * 0.5 = 327.67 meter`), not the map's
  own maximum terrain height.

`Cell Size`, `Starting Point` and `Environment Variable` do read literally, and
are worth checking against `setting.txt` after a generate.

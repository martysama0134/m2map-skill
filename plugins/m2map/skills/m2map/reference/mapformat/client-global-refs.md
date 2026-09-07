# Global Client References — TextureSet, Environment, Property Files

Files outside the map folder that maps reference: the terrain texture palette (`textureset/*.txt`), the environment preset (`*.msenv`), and the object property database (`property/**`). A map is not self-contained — `tile.raw` indexes the textureset, `areadata.txt` CRCs index the property DB.

---

## 1. TextureSet (`textureset/<name>.txt`)

Referenced by `setting.txt` `TextureSet`. Defines the ordered texture palette that `tile.raw` bytes index.

- **Source:** `CTextureSet::Load/Save` (`PRTerrainLib/TextureSet.cpp:25-94, 244-276`)

### Grammar

```
TextureSet

TextureCount <N>
Start Texture001
    "<texture path (.dds/.tga)>"
    <UScale>      float, tiling scale (default 4.0)
    <VScale>      float
    <UOffset>     float, UV translation (default 0)
    <VOffset>     float
    <bSplat>      0|1 — parsed and stored, never read by the splat renderer
    <Begin>       uint16 — parsed and stored, unused at render time
    <End>         uint16 — parsed and stored, unused at render time
End Texture001
Start Texture002
...
```

- Blocks are named `Texture001..TextureNNN` (1-based, `%03d`); block N fills **slot N**.
- **Slot 0 is always the built-in "eraser"** — `TextureCount` excludes it. `tile.raw` byte 0 = erased/blank.
- Hard cap: 256 slots total (255 usable textures) — editor-enforced (`TextureSet.cpp:193-197`); `MAXTERRAINTEXTURES = 256`.
- Missing `Texture%03d` blocks are skipped (slot stays empty); out-of-range indices render the error texture.
- UV transform applied at render: `scale = fTerrainTexCoordBase * UScale` where `fTerrainTexCoordBase = 1 / (16 * 200)` (patch size × cellscale).

### Real sample (`D:\textureset\metin2_a1.txt`, excerpt)

```
TextureSet

TextureCount 17
Start Texture001
    "d:\ymir work\terrainmaps\b\field\field 01.dds"
    5.000000
    5.000000
    0.000000
    0.000000
    0
    0
    0
End Texture001
```

---

## 2. Environment (`<name>.msenv`)

Referenced by `setting.txt` `Environment`. Lighting, fog, skybox, filter, lens flare preset. Resolution order: `<mapdir>\<name>` → `d:/ymir work/environment/<name>` → fallback `<last-2-chars-of-mapname>.msenv`.

- **Source:** load `Environment_Load` (`GameLib/MapUtil.cpp:76-232`), write `SaveEnvironmentScript` (`WorldEditor/DataCtrl/MapManagerEnvironment.cpp:350-486`)
- **Syntax:** hierarchical `Group Name { ... }` / `List Name { ... }` script (`CTextFileLoader`), keys case-insensitive. `ScriptType` line is written but never validated (old files say `EnvrionmentData` — the historical typo — and load fine).

### Key inventory

| Group | Keys |
|---|---|
| *(top)* | `ScriptType`, `ScriptVersion` |
| `DirectionalLight` | `Direction x y z`; sub-groups `Background` and `Character`, each `Enable`, `Diffuse r g b a`, `Ambient r g b a` |
| `Material` | `Diffuse`, `Ambient`, `Emissive` (RGBA) |
| `Fog` | `Enable`, `NearDistance`, `FarDistance`, `Color` (+ legacy `IsDensity`, read-only) |
| `Filter` | `Enable`, `Color` (RGBA), `AlphaSrc`, `AlphaDest` (D3DBLEND enum values) |
| `SkyBox` | `bTextureRenderMode`, `Scale x y z`, `GradientLevelUpper`, `GradientLevelLower`, `FrontFaceFileName`…`BottomFaceFileName` (quoted), `CloudScale u v`, `CloudHeight`, `CloudTextureScale u v`, `CloudSpeed u v`, `CloudTextureFileName`, `List CloudColor` (8 floats = 2 RGBA rows), `List Gradient` (8 floats per entry; entry count must equal upper+lower) |
| `LensFlare` | `Enable`, `BrightnessColor`, `MaxBrightness`, `MainFlareEnable`, `MainFlareTextureFileName`, `MainFlareSize` |
| `Wind` | `Enable`, `Strength`, `Random` — WorldEditorRemix extension, absent in vanilla files |

Gradient entries are the sky dome color stops: each is FirstColor RGBA + SecondColor RGBA.

Defaults when keys are absent: fog 12,800/17,920, skybox scale 3500³, cloud scale 200000², cloud height 30000 (`Environment_Init`, `MapUtil.cpp:4-74`).

### Real sample (`D:\ymir work\environment\a1.msenv`, excerpt)

```
ScriptType         EnvrionmentData
ScriptVersion      1.0000

Group DirectionalLight
{
    Direction     0.350156 0.562609 -0.748907
    Group Background
    {
        Enable        1
        Diffuse       1.000000 0.972549 0.972549 1.000000
        Ambient       0.000000 0.000000 0.000000 1.000000
    }
    ...
}
Group Fog
{
    Enable        1
    NearDistance  5000.000000
    FarDistance   20000.000000
    Color         0.690196 0.741176 0.839216 1.000000
}
```

---

## 3. Property files (`property/**/*.pr?`)

The object database. Each file describes one placeable asset; `areadata.txt`/`areaambiencedata.txt` reference them by CRC.

- **Source:** container `CProperty` (`GameLib/Property.cpp`), registry `CPropertyManager` (`GameLib/PropertyManager.cpp`), schemas `MapType.cpp`

### Container format (all types)

Binary magic + text body:

| Offset | Content |
|---|---|
| 0 | `"YPRT"` FourCC (`59 50 52 54`) |
| 4 | `\r\n` (mandatory, validated) |
| 6 | text lines, `\r\n`-terminated |

Text body:
- **Line 0: the property CRC** as decimal ASCII — this exact number is what areadata records store. The CRC is generated once at save (CRC32 of the normalized model path; types without a model path — notably Ambience — and legacy mode use a timestamp+filename seed instead; uniquified on collision) and **read back verbatim** — never recomputed from the filename.
- Remaining lines: `<key>\t\t"<value>"[\t"<value>"...]` — lowercased keys, alphabetically ordered (std::map), values quoted.

### Type schemas

The `PropertyType` value inside the file (not the extension) drives parsing:

| Ext | PropertyType | Keys |
|---|---|---|
| `.prt` | `Tree` | `PropertyName`, `TreeFile` (.spt), `TreeSize` (float), `TreeVariance` (float) — all required |
| `.prb` | `Building` | `PropertyName`, `BuildingFile` (.gr2), `ShadowFlag` (0/1, optional). Collision file derived: same path with `.mdatr` |
| `.pre` | `Effect` | `PropertyName`, `EffectFile` (.mse) |
| `.pra` | `Ambience` | `PropertyName`, `PlayType` (`ONCE`\|`STEP`\|`LOOP`), `PlayInterval`, `PlayIntervalVariation`, `MaxVolumeAreaPercentage` (optional), `AmbienceSoundVector` (multi-value: wav paths) |
| `.prd` | `DungeonBlock` | `PropertyName`, `DungeonBlockFile` (.gr2). `.mdatr` derived like buildings |

### Real sample (`D:\property\...\baobab.prt`, reconstructed body)

```
1288452050
propertyname		"Baobab"
propertytype		"Tree"
treefile		"d:/ymir work/tree/b1_baobab_rt.spt"
treesize		"1000.000000"
treevariance		"0.000000"
```

### Registration & the `reserve` file

- The client scans the property pack (or the editor scans the `property\` folder recursively) and registers every file into a CRC→property map. Duplicate CRC: last one wins (logged).
- `property/reserve`: plain text, one decimal CRC per line — CRCs of deleted properties, excluded from future generation so IDs never get reused. (Written in text-append mode; lines in the wild end `\r\r\n` — tolerate any line ending.)

### Resolution chain

```
areadata.txt CRC ──> CPropertyManager::Get(crc) ──> CProperty (file whose line-0 == crc)
                     └─ PropertyType key ──> Tree/Building/Effect/Ambience/DungeonBlock instance
```

An unregistered CRC = object silently dropped at load. **A 2D map editor must ship or scan the property set to display object names/types** — the map files alone identify objects only by number.

## Pitfalls

- Property key lookup is case-insensitive but files on disk are lowercased — write lowercase.
- Don't trust extensions; trust the `PropertyType` value.
- CRC is unsigned 32-bit; parse with `parseInt(s) >>> 0` in JS.
- The double-tab `\t\t` after keys and quoting of every value are part of the canonical shape — keep byte-compatible when writing.

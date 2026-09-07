# Environment presets (`.msenv`)

Distilled from the 104 `.msenv` files in
`<CLIENT_PACK>/yw_etc/ymir work/environment`,
cross-referenced against the 142-map corpus in `<CORPUS>` and the 17-archetype partition in
`reference/catalog/map-taxonomy.json`. Machine-readable companion:
**`reference/catalog/environments.json`** (every parsed field, every gradient stop, the full
cluster assignment and the per-archetype ranges).

Parsed with `skills/m2map/scripts/m2map/codec/msenv.py`; all 104 files parse clean, zero problems
reported by `Environment.problems()`. Engine behaviour verified against WorldEditorRemix
(`Srcs/Client/GameLib/MapUtil.cpp`, `MapOutdoor.cpp`, `MapOutdoorRenderHTP.cpp`, `MapManager.cpp`,
`Srcs/Client/EterLib/SkyBox.cpp`, `LensFlare.cpp`).

---

## 1. What is actually in the folder

`ls` returns **121 entries**: **104 `.msenv`**, **16 loose asset files**, and **1 sub-directory** (`skybox/`).

### The 16 non-`.msenv` files

| File | Bytes | What it is |
|---|---:|---|
| `blackout.dds` | 5504 | DXT5 64x64, solid black. Used as a CLOUD texture by skipia_dungeon.msenv and as MainFlareTextureFileName by blackout.msenv - i.e. a "no sky" cheat, not a flare. |
| `clouds_zone01.tga` | 262162 | uncompressed 32-bit TGA 256x256, cloud layer scroll texture (the default; 54 references). |
| `clouds_zone02.tga` | 262188 | uncompressed 32-bit TGA 256x256, denser/darker cloud sheet (16 references). |
| `clouds_zone05.tga` | 262188 | 32-bit TGA 256x256 cloud sheet (9 references). |
| `clouds_zone06.tga` | 204 | RLE 32-bit TGA but only 32x32 and 204 bytes on disk - a STUB. The 6 files that use it (dawnmistwood, dawnmistwood_dungeon, defensewave_blue, miniboss, anglar_dungeon_01) render effectively no cloud detail. |
| `clouds_zone07.tga` | 262188 | 32-bit TGA 256x256 cloud sheet (2 references). |
| `clouds_zone08.tga` | 262188 | 32-bit TGA 256x256 cloud sheet (9 references, all 12zi/otherworld). |
| `clouds_zone10.tga` | 262188 | 32-bit TGA 256x256 cloud sheet (1 reference: eastplain_02). |
| `flare1.dds` | 11064 | DXT1 128x128 lens-flare ghost. NOT named by any .msenv - hardcoded in EterLib/LensFlare.cpp g_strFiles[]. |
| `flare2.dds` | 11064 | DXT1 128x128 lens-flare ghost, hardcoded (used 3x in the 8-ghost chain). |
| `flare3.dds` | 11064 | DXT1 128x128 lens-flare ghost, hardcoded. |
| `flare4.dds` | 11064 | DXT1 128x128 lens-flare ghost, hardcoded. |
| `flare5.dds` | 11064 | DXT1 128x128 lens-flare ghost - present but not even in the hardcoded table; dead file. |
| `flare6.dds` | 11064 | DXT1 128x128 lens-flare ghost, hardcoded. |
| `moon.dds` | 349652 | uncompressed A8R8G8B8 256x256. Referenced by NOTHING in the environment corpus - no .msenv names it. Dead unless a fork wires it up. |
| `sunflare.dds` | 349652 | uncompressed A8R8G8B8 256x256, the main sun sprite. MainFlareTextureFileName in 73 of 104 files. |

`skybox/` holds **41** files: seven 5-face cube sets (`bayblacksand, capedragonhead, dawnmistwood, late_summer, smhtower, snow_dragon, thunder`) plus six `ruins_*.jpg`.
Every face set ships exactly 5 faces (-f -b -l -r -t); no set ships a bottom face. ruins_{up,down,north,south,east,west}.jpg are referenced by nothing.

Three groups of assets are **dead weight**:

- `flare1.dds` .. `flare6.dds` are named by no `.msenv`. `flare1/2/3/4/6` are hardcoded in
  `EterLib/LensFlare.cpp:39-49` as the 8-ghost chain; `flare5.dds` is not even in that table.
- `moon.dds` (256x256 A8R8G8B8) is referenced by nothing at all.
- `skybox/ruins_{up,down,north,south,east,west}.jpg` are referenced by nothing.

And two references point at files that are **not in the pack** (both harmless, see §4):

- `skybox/eastplain_{f,b,l,r,t}.dds` <- `eastplain.msenv`, `eastplain_01.msenv`, `eastplain_03.msenv`, `empirecastle.msenv`
- `skybox/smh-{f,b,l,r,t}.dds + smh-bottom.dds` <- `metin2_map_elemental_03.msenv`

---

## 2. Key inventory - what the shipped files actually write

A raw token scan (not the parser) over all 104 files. **No key outside
`reference/mapformat/client-global-refs.md` §2 appears anywhere.** The interesting result is what
is documented but never written.

| Group | Key | Files writing it |
|---|---|---:|
| (top) | `ScriptType` | 104 |
| (top) | `ScriptVersion` | 104 |
| (top) | `Reserved` | 0 |
| DirectionalLight | `Direction` | 104 |
| DirectionalLight.Background | `Enable` | 104 |
| DirectionalLight.Background | `Diffuse` | 104 |
| DirectionalLight.Background | `Ambient` | 104 |
| DirectionalLight.Character | `Enable` | 104 |
| DirectionalLight.Character | `Diffuse` | 104 |
| DirectionalLight.Character | `Ambient` | 104 |
| Material | `Diffuse` | 104 |
| Material | `Ambient` | 104 |
| Material | `Emissive` | 104 |
| Fog | `Enable` | 104 |
| Fog | `IsDensity` | 0 |
| Fog | `NearDistance` | 104 |
| Fog | `FarDistance` | 104 |
| Fog | `Color` | 104 |
| Filter | `Enable` | 104 |
| Filter | `Color` | 104 |
| Filter | `AlphaSrc` | 104 |
| Filter | `AlphaDest` | 104 |
| SkyBox | `bTextureRenderMode` | 59 |
| SkyBox | `Scale` | 104 |
| SkyBox | `GradientLevelUpper` | 104 |
| SkyBox | `GradientLevelLower` | 104 |
| SkyBox | `FrontFaceFileName` | 59 |
| SkyBox | `BackFaceFileName` | 59 |
| SkyBox | `LeftFaceFileName` | 59 |
| SkyBox | `RightFaceFileName` | 59 |
| SkyBox | `TopFaceFileName` | 59 |
| SkyBox | `BottomFaceFileName` | 59 |
| SkyBox | `CloudScale` | 104 |
| SkyBox | `CloudHeight` | 104 |
| SkyBox | `CloudTextureScale` | 104 |
| SkyBox | `CloudSpeed` | 104 |
| SkyBox | `CloudTextureFileName` | 104 |
| LensFlare | `Enable` | 104 |
| LensFlare | `BrightnessColor` | 104 |
| LensFlare | `MaxBrightness` | 104 |
| LensFlare | `MainFlareEnable` | 104 |
| LensFlare | `MainFlareTextureFileName` | 104 |
| LensFlare | `MainFlareSize` | 104 |
| Wind | `Enable` | 0 |
| Wind | `Strength` | 0 |
| Wind | `Random` | 0 |
| SkyBox | `List CloudColor` | 104 |
| SkyBox | `List Gradient` | 103 |

- `Reserved`, `Fog.IsDensity` and the whole `Group Wind` are **never written** - 0 of 104.
  `Reserved` *is* read (`MapUtil.cpp:85`, into `bReserve`); `IsDensity` is read into `bDensityFog`
  and would switch the fog to `D3DFOG_EXP` at a hardcoded density of `0.00015`
  (`MapManager.cpp:235-240`). `Wind` is a WorldEditorRemix-only extension.
- The 45 files with no face block also omit `bTextureRenderMode`. The WorldEditor writer emits
  both or neither, so the two are perfectly correlated.
- `map_dd_teste.msenv` is the one file with no `List Gradient` (and `GradientLevelUpper 0`,
  `GradientLevelLower 0`) - `SkyBox.cpp:419` bails, so it renders no sky at all.

---

## 3. Hard invariants a generator must reproduce

These are not tendencies. They hold in **all 104 files**, or the stated exception is the only one.

| Invariant | Evidence |
|---|---|
| `ScriptType` | EnvrionmentData in all 104 (the historical typo). Never validated by the loader. |
| `ScriptVersion` | 1.0000 in all 104. |
| `SkyBox.Scale` | 3500 3500 3500 in all 104 - never varied. Not a tuning knob. |
| `DirectionalLight.Background.Enable / Character.Enable` | 1 in all 104. |
| `Character.Ambient == Background.Ambient + 0.15` | exact, per channel, in all 104 files. A generator that does not reproduce this offset will look wrong. |
| `Background.Diffuse == Character.Diffuse` | 103/104. Sole exception moonlight04.msenv (bg 0.251/0.251/0.333 vs ch 0.475/0.475/0.592). |
| `LensFlare.Enable` | 0 in all 104 -> the entire LensFlare group is dead data in the shipped corpus (CLensFlare::m_bEnabled gates Update, Render and Initialize, LensFlare.cpp:184/273/286/304). MainFlareEnable=1 in 84 files changes nothing. |
| `Filter.AlphaDest` | 2 (D3DBLEND_ONE) in all 104. AlphaSrc is 1 (D3DBLEND_ZERO) in 90, 2 in 14. |
| `Filter.Enable` | 1 in only 9 of 104: 12zi_stage_02_01, a3, b3, c3, bayblacksand, e1, metin2_guild_pve, metin2_guild_pvp, metin2_map_guild_battle_03. Of those 9, five (12zi_stage_02_01, a3, b3, c3, e1) use AlphaSrc 1 = D3DBLEND_ZERO with AlphaDest 2 = D3DBLEND_ONE, i.e. dest = 0*quad + 1*frame - an identity blend that tints nothing even if the filter ran. Only the four AlphaSrc 2 files (bayblacksand, metin2_guild_pve, metin2_guild_pvp, metin2_map_guild_battle_03, all colour #4B1818) describe a real additive tint. a3/b3/c3 additionally set Color 0 0 0 0. |
| `List Gradient length` | always exactly (GradientLevelUpper + GradientLevelLower) entries - 0 files trip the MapUtil.cpp:181-184 mismatch that silently discards the gradient. |
| `CloudColor` | all-zero in 92/104 - the cloud tint is unused in most files. |

The `Character.Ambient == Background.Ambient + 0.15` rule is worth restating: it is exact per
channel, in every file, including the two that overflow past 1.0
(`metin2_map_otherworld_01.msenv` -> `1.126471 0.644118 0.577451`, `trent02.msenv` ->
`1.040196 0.644118 0.644118`). It is clearly a fixed offset applied by the WorldEditor UI, and a
generated file that sets the two independently will read as wrong.

Other tight distributions worth sampling from rather than inventing:

| Field | Distribution over 104 files |
|---|---|
| `SkyBox.Scale` | `3500 3500 3500` x104 - never varied |
| `SkyBox.CloudScale` | `200000` x88, `5000` x10, `280000` x3, then 1 each of 2900000 / 900000 / 50000 |
| `SkyBox.CloudHeight` | `30000` x86, `100` x9, `10000` x4, then 1 each of 200/20000/4000/1000/4500 |
| `SkyBox.CloudTextureScale` | `4` x69, `5` x21, `3` x10, then 1 each of 1/20/14 |
| `SkyBox.CloudSpeed` | `0.004` x48, `0.01` x24, `0.001` x17, `0.08` x10, `0.003` x2, `0.0` x1 |
| `LensFlare.MaxBrightness` | `0.74` x90, `1.0` x14 |
| `LensFlare.MainFlareSize` | `0.35` x86, `0.2` x14, `0.34` x2, `0.36` x1, `0.0` x1 |
| `LensFlare.BrightnessColor` | `1 0.886275 0.886275 1` x84, `0.976471^3 1` x14, 2 others |
| `GradientLevelUpper` | 4 x34, 1 x23, 2 x18, 5 x15, 3 x11, 7 x2, 0 x1 |
| `GradientLevelLower` | 1 x98, 2 x5, 0 x1 |
| `Filter.Color` | 40 files repeat `0.556863 0.329412 0.329412 0` (the editor default) even with Enable 0 |
| `List CloudColor` | all-zero in 92 of 104 |

---

## 4. Engine semantics that change how you read these numbers

**1. Gradient entry order is zenith -> horizon -> nadir.**

> EterLib/SkyBox.cpp:325-352 - upper band i spans z from 1-(i+1)/upper to 1-i/upper (z=1 zenith, z=0 horizon); SetSkyColor (SkyBox.cpp:596-630) assigns m_FirstColor to the band TOP vertices and m_SecondColor to the band BOTTOM vertices. So zenith = gradient[0].FirstColor, horizon = gradient[Upper-1].SecondColor, nadir = gradient[-1].SecondColor. Lower bands run z=0 down to z=-1.

**2. Skybox face textures are inert unless bTextureRenderMode is 1.**

> MapOutdoor.cpp:310 maps bSkyBoxTextureRenderMode to SKY_RENDER_MODE_TEXTURE else SKY_RENDER_MODE_DIFFUSE; SkyBox.cpp:417/464 then builds either the gradient dome or the cube. 59 files name faces but only 15 set the flag - 44 files load 5 cube .dds each that are never displayed.

**3. Fog.FarDistance is also the terrain texture-draw distance, whether or not Fog.Enable is 1.**

> MapOutdoorRenderHTP.cpp:76-77 partitions the patch list at FogNear-3200 and FogFar+1600 with no reference to bFogEnable. Beyond FogFar+1600 patches are drawn by __HardwareTransformPatch_RenderPatchNone with COLORARG1=D3DTA_TFACTOR, and TFACTOR is set to the fog colour at line 60. Distant terrain is therefore a flat sheet of Fog.Color even in the 11 files with Fog.Enable 0.

**4. Fog distances are raw centimetres, unscaled.**

> SEnvironmentData::GetFogNearDistance/GetFogFarDistance (MapType.cpp:5-13) return the member verbatim; MapManager.cpp:252-253 bit-casts them straight into D3DRS_FOGSTART/FOGEND.

**5. DirectionalLight.Direction is a D3DLIGHT9 Direction - the direction light TRAVELS.**

> MapUtil.cpp:93-106 stores one vector into both DirLights[].Direction; DirLights is D3DLIGHT9[]. The sun sits at -Direction. All but one file have z<0, i.e. light travelling downward in the Z-up world. Derived sun_elevation_deg/sun_azimuth_deg in this file use sun = -Direction, elevation = asin(sun.z), azimuth = atan2(sun.x, sun.y) with 0deg = +Y.

**6. Environment resolution order is map dir first, then the global folder.**

> client-global-refs.md section 2. 10 map dirs ship a .msenv; 2 of those differ from the global file of the same name, so the map-local copy is what actually renders. metin2_map_spiderdungeon_02/skipia_dungeon.msenv overrides Material.Diffuse (0.509804 0.431373 0.607843 violet -> 1.0 0.984314 0.984314 near-white); metin2_map_devilscatacomb/map_dd_teste.msenv overrides Material.Ambient (0 0 0 -> 0.952941 0.984314 1.0) but is never loaded, because that map names setting.txt points at map_devilsCatacomb.msenv instead.

**7. The only gradient-free file renders no sky at all.**

> map_dd_teste.msenv has GradientLevelUpper 0, GradientLevelLower 0 and no List Gradient; SkyBox.cpp:419 returns early when upper+lower <= 0.

**8. Group Filter is hard-disabled in the WorldEditorRemix client source.**

> EterLib/ScreenFilter.cpp:29-32 reads "void CScreenFilter::SetEnable(BOOL /*bFlag*/) { m_bEnable = FALSE; }" - the setter discards its argument and always clears the flag, and CScreenFilter::Render() returns immediately on !m_bEnable. MapOutdoor.cpp:298 is the only caller. So in this codebase Filter.Enable / Color / AlphaSrc / AlphaDest have no effect at all. The commented-out parameter name shows this was a deliberate neutering, so it may not reflect the original Ymir binary - but it is what the source we can read does. Independently, 5 of the 9 Enable-1 files specify an identity blend anyway.

**9. Fog.IsDensity would switch to exponential fog at a hardcoded density of 0.00015.**

> MapManager.cpp:235-240. No shipped file sets it, and the WorldEditor writer never emits the key, so a round trip silently drops it.

The two that matter most for generation:

- **`Fog.FarDistance` is the terrain draw budget, not just a fog knob.** Doubling it does not just
  soften the haze, it doubles the number of textured terrain patches the client submits. The three
  bands are `< FogNear-3200` (textured, fog off), `FogNear-3200 .. FogFar+1600` (textured, fogged),
  and `> FogFar+1600` (untextured flat `Fog.Color`). `metin2_map_whitedragoncave_02.msenv` sets
  `FarDistance 1000000` - one million cm - which effectively disables the third band entirely.
- **Writing skybox faces without `bTextureRenderMode 1` does nothing.** 59 files name cube faces;
  only **15** set the flag. The other 44 load five `.dds` each that are never displayed, which is
  also why the missing `eastplain_*.dds` and `smh-*.dds` cause no visible breakage - all five files
  that reference them are at render mode 0.

The 15 files that genuinely show a textured skybox: `bayblacksand.msenv`, `blackout.msenv`, `capedragonhead.msenv`, `dawnmistwood.msenv`, `defensewave_blue.msenv`, `eastplain_02.msenv`, `latesummer.msenv`, `metin2_guild_pve.msenv`, `metin2_guild_pvp.msenv`, `metin2_map_guild_battle_03.msenv`, `metin2_map_n_snow_dragon.msenv`, `metin2_map_treasure_hunt.msenv`, `miniboss.msenv`, `mt_th_dragon.msenv`, `mtthunder.msenv`.

---

## 5. Clustering

Clustered on the numbers only - no filename, no map name, no archetype label fed into the distance.

- **Features:** fog colour (w3) + fog enable (w3) + fog near/far normalised (w2) + Background.Ambient (w2.5) + Background.Diffuse (w1.5) + Character.Ambient (w1.5) + Material.Ambient/Emissive (w1) + the sky gradient resampled at 5 heights (w2) + unit light direction (w1) + flags for faces/lensflare/cloud/filter/stop-count.
- **Algorithm:** average-linkage agglomerative on Euclidean distance, cut at 3.2 -> 22 clusters. Cuts at 2.2/2.8/3.6/5.0 are in the working set; 5.0 collapses to a clean 2-way split: bright outdoor daylight (48 files) vs dim/interior (54), plus blackout and trent02 alone.

At the coarsest useful cut the corpus splits cleanly in two: **48 bright outdoor daylight files**
vs **54 dim/interior files**, with `blackout.msenv` and `trent02.msenv` refusing to join either.
That first split is driven almost entirely by `Background.Ambient` and the zenith luminance, which
is the single most load-bearing pair of numbers in the format.

The working cut (threshold 3.2) gives **22 clusters**; 10 of them are singletons. The 12 that
carry weight:

| ID | n | Fog near->far | Fog colour | Bg ambient | Zenith -> horizon | Members |
|---|---:|---|---|---|---|---|
| **C00** clear_blue_noon | 25 | 0-20000 -> 20000-80000 | ~#AAB9CD | 0.10 | #16408B -> #C8D5EB | a1, b1, battlefield, c1, capedragonhead, gm_guild_build, guild_village, metin2_guild_war1, metin2_guild_war3, metin2_map_elemental_01_01, metin2_map_elemental_02_01, metin2_map_elemental_03_01, metin2_map_elemental_04, metin2_map_guild_battle_01, metin2_map_guild_battle_02, metin2_map_icecrystalcave, metin2_map_mists_of_island, metin2_map_n_snow_dragon, metin2_map_otherworld_02, metin2_map_secretdungeon, metin2_map_treasure_hunt, metin2_map_whitdragonvalley, metin2_mists_of_island, sungzi, war4 |
| **C01** murky_lowlight | 13 | 1-20000 -> 20000-50000 | ~#3A3339 | 0.34 | #0E0C15 -> #282524 | anglar_dungeon_01, bayblacksand, dawnmistwood, dawnmistwood_dungeon, map_dd_teste, metin2_guild_pve, metin2_guild_pvp, metin2_map_elemental_03, metin2_map_guild_battle_03, snakevalley, t1, t2, war2 |
| **C02** overcast_haze | 12 | 0-5000 -> 20000-40000 | ~#89837A | 0.17 | #141C33 -> #B2AB9E | a2, a3, b2, b3, battle_guild01, c2, c3, desert_02, map_n_desert_01, n-snowm01, snowm02, t5 |
| **C03** warm_dusk | 10 | 450-15000 -> 20000-50000 | ~#51433E | 0.30 | #5B514D -> #58514F | defensewave_blue, e1, eastplain, eastplain_01, eastplain_02, eastplain_03, latesummer, metin2_map_n_flame_dragon_01, metin2_map_n_flame_dungeon_01, miniboss |
| **C04** 12zi_stylized_stage | 7 | 100-700 -> 20000-50000 | ~#614045 | 0.57 | #03232B -> #7D635B | 12zi_stage_02_02, 12zi_stage_03_01, 12zi_stage_03_02, 12zi_stage_04_01, 12zi_stage_04_02, 12zi_stage_05_01, 12zi_stage_05_02 |
| **C05** black_box | 6 | 5000-5000 -> 20000-20000 | ~#090A0E | 0.00 | #090515 -> #171412 | dark, map_dd, monkeydungeon, monkeydungeon_02, monkeydungeon_03, moonlight04 |
| **C06** ember_orange | 6 | 0-10000 -> 18000-40000 | ~#482216 | 0.18 | #0D080E -> #5B3521 | map_b_fielddungeo, map_boss_entrance, map_n_flame_01, metin2_map_golden_land_night, moonlight05, trent |
| **C07** unfogged_cave | 4 | 1-100 -> 20000-40000 | ~#15161C | 0.43 | #07080E -> #06070A | map_devilscatacomb, resources_zon, skipia_dungeon, spiderdungeon |
| **C08** sand_haze | 4 | 1-1 -> 30000-50000 | ~#C3AC8F | 0.60 | #2F0F05 -> #CBBBA6 | metin2_battleroyale, metin2_map_golden_land, metin2_map_golden_land_stage, milgyo |
| **C09** void_pastel_fog | 3 | 0-5000 -> 20000-1000000 | ~#B69799 | 0.00 | #000000 -> #000000 | metin2_map_whitedragoncave_01, metin2_map_whitedragoncave_02, mt_th_dragon |
| **C10** dusk_fog_off | 2 | 5000-5000 -> 20000-25000 | ~#7B5D4F | 0.16 | #434858 -> #7B5D4F | empirecastle, metin2_map_elemental_02 |
| **C11** blue_fog_off | 2 | 5000-5000 -> 20000-20000 | ~#A0B9DE | 0.00 | #3A62C3 -> #B5CEF3 | metin2_map_elemental_01, metin2_map_snake_temple |

- **C00 `clear_blue_noon`** - The vanilla daylight sky: zenith #1849A8, horizon #D9E6FF, Upper 4 / Lower 1, cloud sheet clouds_zone01 scrolling at 0.004, black or near-black Background.Ambient, fog 5000->20000 in pale blue-grey. 25 files. Spans field_empire, arena_pvp, guild_village, elemental, ice_valley and two dungeon_themed strays.
- **C01 `murky_lowlight`** - Low-light and desaturated: 8 of 13 collapse the dome to Upper 1 / Lower 1 (6 of those to pure black), Background.Ambient is raised to ~0.34 to compensate, and the fog does the work - near ~1000 cm, far 30,000-40,000 cm (300-400 m, i.e. 1.2-1.6 sectors), in a muddy brown/purple (mean #3A3339). The 'overcast forest at dusk / lit interior' look. Also the only cluster that contains `map_dd_teste.msenv`, the one file with no sky at all.
- **C02 `overcast_haze`** - Overcast earth tones. Fog starts at the camera (near 0-2 cm) and reaches 30,000-40,000 cm (300-400 m); fog colour is warm grey to tan; no skybox faces, always a cloud sheet. 12 files, and it owns the whole a2/a3/b2/b3/c2/c3 second- and third-tier field set plus the snow and desert war maps.
- **C03 `warm_dusk`** - Warm dusk. Dark brown/olive fog (cluster mean #51433E), moderate ambient ~0.30, and 9 of 10 files declare real skybox face textures. The gradient is nearly flat - mean zenith #5B514D vs mean horizon #58514F - so the light comes from the fog, not the sky. Covers eastplain, e1, defensewave, miniboss and the flame dungeons.
- **C04 `12zi_stylized_stage`** - The 12zi stage family. Uniform structure - Upper 2 / Lower 1, the capedragonhead face set declared but at bTextureRenderMode 0 (so the cube never shows and the gradient wins), CloudHeight 100, clouds_zone08 at CloudSpeed 0.08 (the fastest in the corpus, 20x the a1 default) - with wildly different chroma per stage. Ambient is the highest in the corpus (mean 0.567).
- **C05 `black_box`** - The black box. Background.Ambient exactly 0, fog #000000-#1F1F28 at 5000->20000, and in 4 of 6 the gradient is collapsed to a single all-black band (Upper 1 / Lower 1) with no cloud texture. `map_dd` (2+2, #1C2136) and `moonlight04` (4+1, #1A0046 -> #6E5936) are the two that keep a real ramp. 6 files, 16 dungeon_block maps.
- **C06 `ember_orange`** - Ember orange. Near-black zenith (mean #0D080E) over a brown-orange horizon (mean #5B3521), with the strongest colour in the BELOW-horizon band - mean nadir #E55E1C, and `map_n_flame_01`/`map_boss_entrance` push it to #FF8700, `trent`/`moonlight05` to pure #FF0000. Fog ~#482216, cloud sheet clouds_zone02/05. 6 files: the lava fields, trent, moonlight05, golden_land_night.
- **C07 `unfogged_cave`** - Unfogged cave. Fog.Enable 0 (all four), ambient lifted to ~0.43, everything black. Distinguished from C05 by the disabled fog and the raised ambient - the map is lit flat instead of falling off.
- **C08 `sand_haze`** - Sand haze. Warm high-value fog (#978572-#E6CDAC, cluster mean #C3AC8F), NearDistance 1, FarDistance 40,000-50,000 cm (400-500 m - the longest sightlines in the corpus), Upper 5 / Lower 1 with a deep red-brown zenith #2F0F05 over a bleached #D7C9B7 horizon, ambient 0.44-0.70, cloud speed 0.01 with CloudTextureScale 5. Owns the entire desert archetype.
- **C09 `void_pastel_fog`** - Void with pastel fog: pure-black sky dome, ambient 0, but a bright lilac/pink fog colour. whitedragoncave_01/02 and mt_th_dragon.
- **C10 `dusk_fog_off`** - Dusk with fog disabled - empirecastle and elemental_02. Same gradient as their fogged twins.
- **C11 `blue_fog_off`** - Blue sky with fog disabled - elemental_01 and snake_temple.

The 10 singletons (`12zi_stage_01_02`, `12zi_stage_02_01`, `blackout`, `metin2_map_battleroyale`, `metin2_map_n_snow_dungeon_01`, `metin2_map_otherworld_01`, `metin2_map_whitedragoncave_boss`, `mtthunder`, `trent02`, `ydragon`) are each a genuine one-off and are listed in full in the JSON.

### Cluster vs archetype

The correspondence is strong but not one-to-one, and the mismatches are the interesting part:

| Archetype | Cluster spread (map-weighted) |
|---|---|
| `field_empire` | C00 clear_blue_noon x12, C02 overcast_haze x3, C06 ember_orange x1, C08 sand_haze x1, C01 murky_lowlight x1 |
| `field_valley` | C02 overcast_haze x4 |
| `desert` | C08 sand_haze x10 |
| `snow_field` | C02 overcast_haze x6 |
| `flame_field` | C06 ember_orange x6 |
| `darkforest_coast` | C03 warm_dusk x4, C01 murky_lowlight x2, C00 clear_blue_noon x1, C19 singleton_mtthunder x1 |
| `ice_valley` | C00 clear_blue_noon x2, C01 murky_lowlight x1 |
| `eastplain` | C03 warm_dusk x3, C10 dusk_fog_off x1 |
| `empire_war` | C02 overcast_haze x4, C00 clear_blue_noon x2 |
| `guild_village` | C00 clear_blue_noon x7 |
| `arena_pvp` | C00 clear_blue_noon x6 |
| `dungeon_block` | C05 black_box x16, C07 unfogged_cave x6, C01 murky_lowlight x1 |
| `dungeon_themed` | C01 murky_lowlight x4, C03 warm_dusk x4, C16 singleton_metin2_map_n_snow_dungeon_01 x3, C17 singleton_metin2_map_otherworld_01 x3, C07 unfogged_cave x2, C00 clear_blue_noon x2, C09 void_pastel_fog x2, C18 singleton_metin2_map_whitedragoncave_boss x1 |
| `elemental` | C00 clear_blue_noon x3, C11 blue_fog_off x1, C10 dusk_fog_off x1, C01 murky_lowlight x1 |
| `trent_forest` | C06 ember_orange x1, C20 singleton_trent02 x1 |
| `event_instance` | C04 12zi_stylized_stage x7, C03 warm_dusk x4, C00 clear_blue_noon x2, C12 singleton_12zi_stage_01_02 x1, C13 singleton_12zi_stage_02_01 x1, C01 murky_lowlight x1, C15 singleton_metin2_map_battleroyale x1, C11 blue_fog_off x1 |
| `dev_stub` | C06 ember_orange x2, C01 murky_lowlight x2 |

Six archetypes are cluster-pure: `field_valley`, `desert`, `snow_field`, `flame_field`,
`guild_village`, `arena_pvp`. Their env is a constant, not a distribution.

---

## 6. Canonical presets per archetype

For each archetype: the representative `.msenv`, then the observed range across **every** env that
archetype's maps reference, weighted by how many maps use it. Sample from the ranges, not the
single file.

### `field_empire` - 18 maps, 12 distinct envs

The three empire capitals plus their satellite fields. `a1`/`c1`/`war4` are byte-identical; `b1` differs only in fog colour (#D8E6FF vs #B0BDD6) and the last two gradient rows. This is the game's default sky and the safest thing a generator can emit.

**Canonical: `a1.msenv`** (cluster C00 `clear_blue_noon`; used by `metin2_map_a1`, `metin2_map_smhgate_a1`, `metin2_map_wedding_01`)

| Env | Maps | Cluster |
|---|---:|---|
| `a1.msenv` | 3 | C00 `clear_blue_noon` |
| `b1.msenv` | 3 | C00 `clear_blue_noon` |
| `c1.msenv` | 3 | C00 `clear_blue_noon` |
| `a3.msenv` | 1 | C02 `overcast_haze` |
| `b3.msenv` | 1 | C02 `overcast_haze` |
| `battlefield.msenv` | 1 | C00 `clear_blue_noon` |
| `c3.msenv` | 1 | C02 `overcast_haze` |
| `map_b_fielddungeo.msenv` | 1 | C06 `ember_orange` |
| `milgyo.msenv` | 1 | C08 `sand_haze` |
| `sungzi.msenv` | 1 | C00 `clear_blue_noon` |
| `war2.msenv` | 1 | C01 `murky_lowlight` |
| `war4.msenv` | 1 | C00 `clear_blue_noon` |

| Parameter | Observed range |
|---|---|
| `Fog.Enable` | 1 x18 |
| `Fog.NearDistance` | 0-5000 (med 5000) cm |
| `Fog.FarDistance` | 20000-50000 (med 20000) cm |
| `Fog.Color` | #272522, #4FA4AF, #69594E, #8C7761, #A19B94, #B0BDD6, #D8E6FF, #E6CDAC |
| fog hue / sat / value | 24.4-219.5 (med 218.5) deg / 0.081-0.549 (med 0.178) / 0.153-1 (med 0.839) |
| `Background.Ambient` | #000000, #3F504F, #725353, #C8B19C (mean level 0-0.6967 (med 0)) |
| `Character.Ambient` level | 0.15-0.8467 (med 0.15) (always Background + 0.15) |
| `Background.Diffuse` | #695D56, #A39494, #CAA891, #FFF8F8, #FFFFFF |
| light warmth (R-B of diffuse) | 0-0.2235 (med 0.0275) |
| sun elevation / azimuth | 35.3-48.7 (med 48.5) deg / 211.9, 225.0, 244.7 deg |
| `Direction` vectors | `0.350156 0.562609 -0.748907`, `0.5 0.5 -0.5`, `0.596551 0.28178 -0.751483` |
| `Material.Ambient` / `Emissive` | #5D5D5D, #695446, #715F40, #CDAF93, #E1DAC8 / #000000, #0E0000, #36332F, #413C3C, #4B3732 ... (6 total) |
| `GradientLevelUpper` / `Lower` | 4 x15, 5 x2, 2 x1 / 1 x18 |
| sky zenith | #0C0505, #0E0807, #1849A8, #2C1A08, #2E3139, #2F0F05 |
| sky horizon | #69594E, #8BABC8, #978E87, #C6B3A0, #D7C9B7, #D9E6FF |
| sky nadir (below-horizon band) | #2D110F, #65332F, #87909E, #88909F, #AC977C, #DAE1E2 ... (7 total) |
| `bTextureRenderMode` | absent x17, 0 x1 |
| skybox face sets | none |
| `CloudTextureFileName` | clouds_zone01.tga, clouds_zone02.tga |
| `CloudScale` / `CloudTextureScale` / `CloudSpeed` / `CloudHeight` | 200000 / 4, 5 / 0.003, 0.004, 0.01 / 30000 |
| `Filter.Enable` / colour / AlphaSrc | 0 x15, 1 x3 / #000000 / 1 |
| `LensFlare.Enable` / `MainFlareEnable` | 0 x18 / 1 x18 |

**Off-cluster members** (6):

- `a3.msenv` (metin2_map_a3) sits in **C02 `overcast_haze`**, not the archetype modal **C00 `clear_blue_noon`**
- `b3.msenv` (metin2_map_b3) sits in **C02 `overcast_haze`**, not the archetype modal **C00 `clear_blue_noon`**
- `c3.msenv` (metin2_map_c3) sits in **C02 `overcast_haze`**, not the archetype modal **C00 `clear_blue_noon`**
- `map_b_fielddungeo.msenv` (map_b_fielddungeon) sits in **C06 `ember_orange`**, not the archetype modal **C00 `clear_blue_noon`**
- `milgyo.msenv` (metin2_map_milgyo) sits in **C08 `sand_haze`**, not the archetype modal **C00 `clear_blue_noon`** - also used by `desert`
- `war2.msenv` (metin2_guild_war2) sits in **C01 `murky_lowlight`**, not the archetype modal **C00 `clear_blue_noon`**

### `field_valley` - 4 maps, 1 distinct env

One env for four maps - `a2.msenv`, verbatim, on map_a2 and its three relocated copies. Green-grey fog, dark teal zenith. A single sample, no range to speak of.

**Canonical: `a2.msenv`** (cluster C02 `overcast_haze`; used by `map_a2`, `map_n_threeway`, `metin2_map_guild_01`, `metin2_map_smhgate_threeway`)

| Env | Maps | Cluster |
|---|---:|---|
| `a2.msenv` | 4 | C02 `overcast_haze` |

| Parameter | Observed range |
|---|---|
| `Fog.Enable` | 1 x4 |
| `Fog.NearDistance` | 5000 cm |
| `Fog.FarDistance` | 20000 cm |
| `Fog.Color` | #5C6E64 |
| fog hue / sat / value | 146.7 deg / 0.164 / 0.431 |
| `Background.Ambient` | #0C1611 (mean level 0.0667) |
| `Character.Ambient` level | 0.2167 (always Background + 0.15) |
| `Background.Diffuse` | #FFF8F8 |
| light warmth (R-B of diffuse) | 0.0275 |
| sun elevation / azimuth | 48.5 deg / 211.9 deg |
| `Direction` vectors | `0.350156 0.562609 -0.748907` |
| `Material.Ambient` / `Emissive` | #E1DAC8 / #282A2A |
| `GradientLevelUpper` / `Lower` | 4 x4 / 1 x4 |
| sky zenith | #072A2E |
| sky horizon | #9AB6A7 |
| sky nadir (below-horizon band) | #3F5340 |
| `bTextureRenderMode` | absent x4 |
| skybox face sets | none |
| `CloudTextureFileName` | clouds_zone01.tga |
| `CloudScale` / `CloudTextureScale` / `CloudSpeed` / `CloudHeight` | 200000 / 4 / 0.004 / 30000 |
| `Filter.Enable` / colour / AlphaSrc | 0 x4 / n/a / 1 |
| `LensFlare.Enable` / `MainFlareEnable` | 0 x4 / 1 x4 |

### `desert` - 10 maps, 3 distinct envs

Dominated by `milgyo.msenv` (8 of 10 maps). Distinctive shape: `NearDistance 1` with a very long `FarDistance` (40,000-50,000 cm = 400-500 m, roughly 2 sectors) and a high ambient floor - sun-bleached haze that starts at the camera. The two golden_land variants are the same recipe at lower value.

**Canonical: `milgyo.msenv`** (cluster C08 `sand_haze`; used by `metin2_map_n_desert_01`, `metin2_map_nusluck01`, `metin2_map_smhgate_desert`, `metin2_map_sungzi_desert_01`, `metin2_map_sungzi_desert_hill_01`, `metin2_map_sungzi_desert_hill_02`, `metin2_map_sungzi_desert_hill_03`, `metin2_map_wl_01`)

| Env | Maps | Cluster |
|---|---:|---|
| `milgyo.msenv` | 8 | C08 `sand_haze` |
| `metin2_map_golden_land.msenv` | 1 | C08 `sand_haze` |
| `metin2_map_golden_land_stage.msenv` | 1 | C08 `sand_haze` |

| Parameter | Observed range |
|---|---|
| `Fog.Enable` | 1 x10 |
| `Fog.NearDistance` | 1 cm |
| `Fog.FarDistance` | 40000-50000 (med 50000) cm |
| `Fog.Color` | #978572, #E6CDAC |
| fog hue / sat / value | 30.8-34.1 (med 34.1) deg / 0.245-0.252 (med 0.252) / 0.592-0.902 (med 0.902) |
| `Background.Ambient` | #746E6B, #978E85, #C8B19C (mean level 0.4353-0.6967 (med 0.6967)) |
| `Character.Ambient` level | 0.5853-0.8467 (med 0.8467) (always Background + 0.15) |
| `Background.Diffuse` | #C8C3C1, #CAA891, #E1DDD8 |
| light warmth (R-B of diffuse) | 0.0275-0.2235 (med 0.2235) |
| sun elevation / azimuth | 48.7 deg / 244.7 deg |
| `Direction` vectors | `0.596551 0.28178 -0.751483` |
| `Material.Ambient` / `Emissive` | #000000, #5D5D5D / #000000, #48413F, #A7A3A3 |
| `GradientLevelUpper` / `Lower` | 5 x10 / 1 x10 |
| sky zenith | #2F0F05 |
| sky horizon | #A89274, #D7C9B7 |
| sky nadir (below-horizon band) | #61533F, #AC977C |
| `bTextureRenderMode` | absent x8, 0 x2 |
| skybox face sets | none |
| `CloudTextureFileName` | clouds_zone01.tga |
| `CloudScale` / `CloudTextureScale` / `CloudSpeed` / `CloudHeight` | 200000 / 5 / 0.01 / 30000 |
| `Filter.Enable` / colour / AlphaSrc | 0 x10 / n/a / 1 |
| `LensFlare.Enable` / `MainFlareEnable` | 0 x10 / 1 x10 |

### `snow_field` - 6 maps, 1 distinct env

One env, `n-snowm01.msenv`, on all six. `CloudScale 280000` is a snow signature - only three files in the corpus use it and the other two are its sibling `snowm02.msenv` (empire_war snow) and `metin2_map_n_snow_dungeon_01.msenv`. Fog starts at the camera (`NearDistance 1`) and reaches 40,000 cm (400 m) in a flat #AEB0BA, so distance reads as whiteout rather than as haze.

**Canonical: `n-snowm01.msenv`** (cluster C02 `overcast_haze`; used by `map_n_snowm_01`, `metin2_map_smhgate_snow`, `metin2_map_sungzi_snow`, `metin2_map_sungzi_snow_pass01`, `metin2_map_sungzi_snow_pass02`, `metin2_map_sungzi_snow_pass03`)

| Env | Maps | Cluster |
|---|---:|---|
| `n-snowm01.msenv` | 6 | C02 `overcast_haze` |

| Parameter | Observed range |
|---|---|
| `Fog.Enable` | 1 x6 |
| `Fog.NearDistance` | 1 cm |
| `Fog.FarDistance` | 40000 cm |
| `Fog.Color` | #AEB0BA |
| fog hue / sat / value | 230 deg / 0.065 / 0.729 |
| `Background.Ambient` | #45474C (mean level 0.2824) |
| `Character.Ambient` level | 0.4324 (always Background + 0.15) |
| `Background.Diffuse` | #A8A8A8 |
| light warmth (R-B of diffuse) | 0 |
| sun elevation / azimuth | 48.7 deg / 244.7 deg |
| `Direction` vectors | `0.596551 0.28178 -0.751483` |
| `Material.Ambient` / `Emissive` | #ABAAAC / #343437 |
| `GradientLevelUpper` / `Lower` | 5 x6 / 1 x6 |
| sky zenith | #0A2D5A |
| sky horizon | #AEB0BA |
| sky nadir (below-horizon band) | #0F0050 |
| `bTextureRenderMode` | absent x6 |
| skybox face sets | none |
| `CloudTextureFileName` | clouds_zone01.tga |
| `CloudScale` / `CloudTextureScale` / `CloudSpeed` / `CloudHeight` | 280000 / 5 / 0.01 / 30000 |
| `Filter.Enable` / colour / AlphaSrc | 0 x6 / n/a / 1 |
| `LensFlare.Enable` / `MainFlareEnable` | 0 x6 / 1 x6 |

### `flame_field` - 6 maps, 2 distinct envs

`map_n_flame_01.msenv` and its near-clone `map_boss_entrance.msenv` differ by ~0.001 per channel. Highest gradient band count in the corpus (Upper 7) and a deliberately COOL directional diffuse (#5DAB9B, warmth -0.24) against a hot orange sky - the artist lit the lava field with a teal key.

**Canonical: `map_n_flame_01.msenv`** (cluster C06 `ember_orange`; used by `metin2_map_n_flame_01`, `metin2_map_smhgate_flame`, `metin2_map_sungzi_flame_hill_01`, `metin2_map_sungzi_flame_hill_02`, `metin2_map_sungzi_flame_hill_03`)

| Env | Maps | Cluster |
|---|---:|---|
| `map_n_flame_01.msenv` | 5 | C06 `ember_orange` |
| `map_boss_entrance.msenv` | 1 | C06 `ember_orange` |

| Parameter | Observed range |
|---|---|
| `Fog.Enable` | 1 x6 |
| `Fog.NearDistance` | 1000 cm |
| `Fog.FarDistance` | 30000 cm |
| `Fog.Color` | #85361C |
| fog hue / sat / value | 14.9 deg / 0.789 / 0.522 |
| `Background.Ambient` | #623101, #623201 (mean level 0.1935-0.1948 (med 0.1948)) |
| `Character.Ambient` level | 0.3435-0.3448 (med 0.3448) (always Background + 0.15) |
| `Background.Diffuse` | #5DAA9A, #5DAB9B |
| light warmth (R-B of diffuse) | -0.2431--0.2392 (med -0.2431) |
| sun elevation / azimuth | 37.6 deg / 231.6 deg |
| `Direction` vectors | `0.620509 0.492475 -0.610275` |
| `Material.Ambient` / `Emissive` | #3F13E1 / #6D3C3C, #6D523B |
| `GradientLevelUpper` / `Lower` | 7 x6 / 1 x6 |
| sky zenith | #1F0000 |
| sky horizon | #87381F |
| sky nadir (below-horizon band) | #FF8700 |
| `bTextureRenderMode` | absent x5, 0 x1 |
| skybox face sets | none |
| `CloudTextureFileName` | clouds_zone02.tga |
| `CloudScale` / `CloudTextureScale` / `CloudSpeed` / `CloudHeight` | 200000 / 5 / 0.01 / 30000 |
| `Filter.Enable` / colour / AlphaSrc | 0 x6 / n/a / 1 |
| `LensFlare.Enable` / `MainFlareEnable` | 0 x6 / 1 x6 |

### `darkforest_coast` - 8 maps, 5 distinct envs

The widest spread of any outdoor archetype: 5 envs across 4 clusters. This is the one archetype where the skybox cube is actually used - 4 of the 5 set bTextureRenderMode 1 and reference real face sets (thunder, bayblacksand, capedragonhead, dawnmistwood). Fog far ranges 20,000-80,000 cm (200-800 m).

**Canonical: `e1.msenv`** (cluster C03 `warm_dusk`; used by `metin2_map_e1`, `metin2_map_e1_01`, `metin2_map_e1_02`, `metin2_map_e1_03`)

| Env | Maps | Cluster |
|---|---:|---|
| `e1.msenv` | 4 | C03 `warm_dusk` |
| `bayblacksand.msenv` | 1 | C01 `murky_lowlight` |
| `capedragonhead.msenv` | 1 | C00 `clear_blue_noon` |
| `dawnmistwood.msenv` | 1 | C01 `murky_lowlight` |
| `mtthunder.msenv` | 1 | C19 `singleton_mtthunder` |

| Parameter | Observed range |
|---|---|
| `Fog.Enable` | 1 x8 |
| `Fog.NearDistance` | 1000-20000 (med 5000) cm |
| `Fog.FarDistance` | 20000-80000 (med 25000) cm |
| `Fog.Color` | #2A2A3B, #423D62, #8B4F1B, #975A2A, #AFBCD6 |
| fog hue / sat / value | 26.4-248.1 (med 27.9) deg / 0.182-0.806 (med 0.764) / 0.231-0.839 (med 0.545) |
| `Background.Ambient` | #383D46, #3F3D3D, #3F3E3E, #48495D, #5B5D34 (mean level 0.2418-0.3111 (med 0.2431)) |
| `Character.Ambient` level | 0.3918-0.4611 (med 0.3931) (always Background + 0.15) |
| `Background.Diffuse` | #9C799E, #F3FD00, #F6D1D1, #FFF8F8 |
| light warmth (R-B of diffuse) | -0.0078-0.9529 (med 0.0275) |
| sun elevation / azimuth | 16.5-47.8 (med 47.55) deg / 97.2, 99.1, 143.0, 153.4, 193.4 deg |
| `Direction` vectors | `-0.669884 0.10788 -0.734587`, `-0.666346 0.083646 -0.740936`, `-0.498026 0.661216 -0.561038`, `-0.429878 0.857227 -0.28349` ... (5 total) |
| `Material.Ambient` / `Emissive` | #4B2A6E, #60777C, #726844, #89C3D6, #8BC5D6 / #3F5057, #42425D, #425444, #535353 |
| `GradientLevelUpper` / `Lower` | 4 x6, 1 x1, 2 x1 / 1 x8 |
| sky zenith | #000000, #1849A8, #4B5049, #918260, #B1751F |
| sky horizon | #000000, #2D2B3C, #9B4C00, #D9E6FF, #FCAF26 |
| sky nadir (below-horizon band) | #000000, #322647, #6D361A, #88909F, #CBAC51 |
| `bTextureRenderMode` | 0 x4, 1 x4 |
| skybox face sets | bayblacksand, capedragonhead, dawnmistwood, thunder |
| `CloudTextureFileName` | clouds_zone05.tga, clouds_zone06.tga |
| `CloudScale` / `CloudTextureScale` / `CloudSpeed` / `CloudHeight` | 200000 / 4 / 0.001, 0.004 / 30000 |
| `Filter.Enable` / colour / AlphaSrc | 1 x5, 0 x3 / #4B1818, #8E5454 / 1, 2 |
| `LensFlare.Enable` / `MainFlareEnable` | 0 x8 / 1 x6, 0 x2 |

**Off-cluster members** (4):

- `bayblacksand.msenv` (metin2_map_bayblacksand) sits in **C01 `murky_lowlight`**, not the archetype modal **C03 `warm_dusk`**
- `capedragonhead.msenv` (metin2_map_capedragonhead) sits in **C00 `clear_blue_noon`**, not the archetype modal **C03 `warm_dusk`**
- `dawnmistwood.msenv` (metin2_map_dawnmistwood) sits in **C01 `murky_lowlight`**, not the archetype modal **C03 `warm_dusk`**
- `mtthunder.msenv` (metin2_map_mt_thunder) sits in **C19 `singleton_mtthunder`**, not the archetype modal **C03 `warm_dusk`**

### `ice_valley` - 3 maps, 3 distinct envs

Three one-off envs that share a structural signature: `GradientLevelUpper 2` + `GradientLevelLower 2` (only 5 files in the whole corpus use Lower 2, and 3 of them are here), `CloudHeight 10000`, `CloudSpeed 0.001`, the bayblacksand face set with render mode 0, and a cool blue-biased diffuse.

**Canonical: `metin2_map_icecrystalcave.msenv`** (cluster C00 `clear_blue_noon`; used by `metin2_map_icecrystalcave`)

| Env | Maps | Cluster |
|---|---:|---|
| `metin2_map_icecrystalcave.msenv` | 1 | C00 `clear_blue_noon` |
| `metin2_map_whitdragonvalley.msenv` | 1 | C00 `clear_blue_noon` |
| `snakevalley.msenv` | 1 | C01 `murky_lowlight` |

| Parameter | Observed range |
|---|---|
| `Fog.Enable` | 1 x3 |
| `Fog.NearDistance` | 100-5000 (med 100) cm |
| `Fog.FarDistance` | 20000-29000 (med 25000) cm |
| `Fog.Color` | #4C4F33, #7E8CAE, #A4C8FF |
| fog hue / sat / value | 66.4-222.5 (med 216.3) deg / 0.276-0.357 (med 0.354) / 0.31-1 (med 0.682) |
| `Background.Ambient` | #282B38, #282C39, #3D4246 (mean level 0.1817-0.2575 (med 0.1843)) |
| `Character.Ambient` level | 0.3317-0.4075 (med 0.3343) (always Background + 0.15) |
| `Background.Diffuse` | #919AAC, #A0AEA3, #A5C6DE |
| light warmth (R-B of diffuse) | -0.2235--0.0118 (med -0.1059) |
| sun elevation / azimuth | 44.5 deg / 238.6 deg |
| `Direction` vectors | `0.609035 0.37155 -0.700733` |
| `Material.Ambient` / `Emissive` | #595C68, #5D6483, #9A978E / #272931, #393A47, #3B3846 |
| `GradientLevelUpper` / `Lower` | 2 x3 / 2 x3 |
| sky zenith | #003371, #0C2855, #1C1672 |
| sky horizon | #596533, #7E8CAE, #A4C8FF |
| sky nadir (below-horizon band) | #000000, #7E8CAE, #A4C8FF |
| `bTextureRenderMode` | 0 x3 |
| skybox face sets | bayblacksand |
| `CloudTextureFileName` | clouds_zone01.tga |
| `CloudScale` / `CloudTextureScale` / `CloudSpeed` / `CloudHeight` | 200000 / 4 / 0.001 / 10000 |
| `Filter.Enable` / colour / AlphaSrc | 0 x3 / n/a / 2 |
| `LensFlare.Enable` / `MainFlareEnable` | 0 x3 / 0 x3 |

**Off-cluster members** (1):

- `snakevalley.msenv` (metin2_map_snakevalley) sits in **C01 `murky_lowlight`**, not the archetype modal **C00 `clear_blue_noon`**

### `eastplain` - 4 maps, 4 distinct envs

`eastplain_01` and `eastplain_03` are byte-identical; `empirecastle` is `eastplain_01` with Fog.Enable flipped to 0 and the ambient nudged. `eastplain_02` is the outlier - the only map in the corpus using the smhtower face set, CloudScale 2,900,000 and CloudTextureScale 20.

**Canonical: `eastplain_01.msenv`** (cluster C03 `warm_dusk`; used by `metin2_map_eastplain_01`)

| Env | Maps | Cluster |
|---|---:|---|
| `eastplain_01.msenv` | 1 | C03 `warm_dusk` |
| `eastplain_02.msenv` | 1 | C03 `warm_dusk` |
| `eastplain_03.msenv` | 1 | C03 `warm_dusk` |
| `empirecastle.msenv` | 1 | C10 `dusk_fog_off` |

| Parameter | Observed range |
|---|---|
| `Fog.Enable` | 1 x3, 0 x1 |
| `Fog.NearDistance` | 5000-15000 (med 5000) cm |
| `Fog.FarDistance` | 25000-50000 (med 25000) cm |
| `Fog.Color` | #280F2F, #3D595D, #3D5A5D |
| fog hue / sat / value | 185.6-286.9 (med 186.55) deg / 0.344-0.681 (med 0.344) / 0.184-0.365 (med 0.365) |
| `Background.Ambient` | #493F52, #4B4B58, #565680 (mean level 0.285-0.3922 (med 0.3517)) |
| `Character.Ambient` level | 0.435-0.5422 (med 0.5017) (always Background + 0.15) |
| `Background.Diffuse` | #BCBAC1, #CBC9C0, #FBEBA8 |
| light warmth (R-B of diffuse) | -0.0196-0.3255 (med 0.1843) |
| sun elevation / azimuth | 39.3-68.6 (med 39.3) deg / 35.1, 266.7 deg |
| `Direction` vectors | `-0.210052 -0.298942 -0.930866`, `0.772081 0.044283 -0.633979` |
| `Material.Ambient` / `Emissive` | #5D4F6E, #8D8D8D, #AEAEAE / #261F3D, #373B46, #484848 |
| `GradientLevelUpper` / `Lower` | 3 x4 / 1 x4 |
| sky zenith | #315480, #503D2A |
| sky horizon | #3D5A5D, #434561 |
| sky nadir (below-horizon band) | #353A44, #3D595D, #434561 |
| `bTextureRenderMode` | 0 x3, 1 x1 |
| skybox face sets | eastplain, smhtower |
| `CloudTextureFileName` | clouds_zone01.tga, clouds_zone10.tga |
| `CloudScale` / `CloudTextureScale` / `CloudSpeed` / `CloudHeight` | 200000, 2.9e+06 / 4, 20 / 0.001, 0.004 / 30000 |
| `Filter.Enable` / colour / AlphaSrc | 0 x4 / n/a / 1 |
| `LensFlare.Enable` / `MainFlareEnable` | 0 x4 / 1 x3, 0 x1 |

**Off-cluster members** (1):

- `empirecastle.msenv` (metin2_map_empirecastle) sits in **C10 `dusk_fog_off`**, not the archetype modal **C03 `warm_dusk`**

### `empire_war` - 6 maps, 3 distinct envs

Three envs, two maps each, and no majority: the battlearena/empirewar pairs each borrow the env of the terrain they are cut from (snow -> snowm02, empire -> a1, desert -> desert_02). Pick by terrain, not by archetype.

**Canonical: `desert_02.msenv`** (cluster C02 `overcast_haze`; used by `metin2_map_battlearena03`, `metin2_map_empirewar03`)

| Env | Maps | Cluster |
|---|---:|---|
| `a1.msenv` | 2 | C00 `clear_blue_noon` |
| `desert_02.msenv` | 2 | C02 `overcast_haze` |
| `snowm02.msenv` | 2 | C02 `overcast_haze` |

| Parameter | Observed range |
|---|---|
| `Fog.Enable` | 1 x6 |
| `Fog.NearDistance` | 1-5000 (med 2) cm |
| `Fog.FarDistance` | 20000-40000 (med 30000) cm |
| `Fog.Color` | #AC9C85, #AEAFBA, #B0BDD6 |
| fog hue / sat / value | 35.4-235 (med 219.5) deg / 0.065-0.227 (med 0.178) / 0.675-0.839 (med 0.729) |
| `Background.Ambient` | #000000, #44464B (mean level 0-0.2784 (med 0)) |
| `Character.Ambient` level | 0.15-0.4284 (med 0.15) (always Background + 0.15) |
| `Background.Diffuse` | #A8A8A8, #FFF8F8, #FFFFFF |
| light warmth (R-B of diffuse) | 0-0.0275 (med 0) |
| sun elevation / azimuth | 48.5-48.7 (med 48.7) deg / 211.9, 244.7 deg |
| `Direction` vectors | `0.350156 0.562609 -0.748907`, `0.596551 0.28178 -0.751483` |
| `Material.Ambient` / `Emissive` | #705D3F, #AAAAAC, #E1DAC8 / #343436, #525269, #563D31 |
| `GradientLevelUpper` / `Lower` | 5 x4, 4 x2 / 1 x6 |
| sky zenith | #010F69, #0A2D59, #1849A8 |
| sky horizon | #AEB0BA, #B5834B, #D9E6FF |
| sky nadir (below-horizon band) | #0F0050, #88909F, #B5834B |
| `bTextureRenderMode` | absent x6 |
| skybox face sets | none |
| `CloudTextureFileName` | clouds_zone01.tga, clouds_zone05.tga |
| `CloudScale` / `CloudTextureScale` / `CloudSpeed` / `CloudHeight` | 200000, 280000 / 4, 5 / 0.004, 0.01 / 30000 |
| `Filter.Enable` / colour / AlphaSrc | 0 x6 / n/a / 1 |
| `LensFlare.Enable` / `MainFlareEnable` | 0 x6 / 1 x6 |

**Off-cluster members** (1):

- `a1.msenv` (metin2_map_battlearena02, metin2_map_empirewar02) sits in **C00 `clear_blue_noon`**, not the archetype modal **C02 `overcast_haze`** - also used by `field_empire`, `arena_pvp`

### `guild_village` - 7 maps, 4 distinct envs

All four envs are `a1.msenv` with the Background/Character ambient lifted off zero. `guild_village.msenv` additionally moves the sun (`Direction 0.411157 0.785894 -0.461867`, elevation 27.5 deg vs a1's 48.5) and pushes fog near to 7000 with a paler #C1CCE2. `metin2_guild_war1.msenv` and `war3.msenv` are byte-identical to each other. The three metin2_guild_village_0N maps have no setting.txt at all and inherit guild_village.msenv through ParentMapName.

**Canonical: `guild_village.msenv`** (cluster C00 `clear_blue_noon`; used by `metin2_guild_village`, `metin2_guild_village_01*`, `metin2_guild_village_02*`, `metin2_guild_village_03*`)

| Env | Maps | Cluster |
|---|---:|---|
| `guild_village.msenv` | 4 | C00 `clear_blue_noon` |
| `gm_guild_build.msenv` | 1 | C00 `clear_blue_noon` |
| `metin2_guild_war1.msenv` | 1 | C00 `clear_blue_noon` |
| `metin2_guild_war3.msenv` | 1 | C00 `clear_blue_noon` |

| Parameter | Observed range |
|---|---|
| `Fog.Enable` | 1 x7 |
| `Fog.NearDistance` | 5000-7000 (med 7000) cm |
| `Fog.FarDistance` | 20000 cm |
| `Fog.Color` | #AFBCD6, #C1CCE2 |
| fog hue / sat / value | 220 deg / 0.146-0.182 (med 0.146) / 0.839-0.886 (med 0.886) |
| `Background.Ambient` | #32383E, #355054, #534C3E (mean level 0.2196-0.2889 (med 0.2837)) |
| `Character.Ambient` level | 0.3696-0.4389 (med 0.4337) (always Background + 0.15) |
| `Background.Diffuse` | #FFF8F8 |
| light warmth (R-B of diffuse) | 0.0275 |
| sun elevation / azimuth | 27.5-52.7 (med 27.5) deg / 207.6, 211.9, 243.8 deg |
| `Direction` vectors | `0.350156 0.562609 -0.748907`, `0.411157 0.785894 -0.461867`, `0.544326 0.267763 -0.794992` |
| `Material.Ambient` / `Emissive` | #CFD8AF, #E1DAC8, #FFFFFF / #000000, #46466B, #525269 |
| `GradientLevelUpper` / `Lower` | 4 x7 / 1 x7 |
| sky zenith | #1849A8 |
| sky horizon | #D9E6FF |
| sky nadir (below-horizon band) | #88909F |
| `bTextureRenderMode` | absent x7 |
| skybox face sets | none |
| `CloudTextureFileName` | clouds_zone01.tga |
| `CloudScale` / `CloudTextureScale` / `CloudSpeed` / `CloudHeight` | 200000 / 4 / 0.004 / 30000 |
| `Filter.Enable` / colour / AlphaSrc | 0 x7 / n/a / 1 |
| `LensFlare.Enable` / `MainFlareEnable` | 0 x7 / 1 x7 |

### `arena_pvp` - 6 maps, 2 distinct envs

Every arena map uses `a1.msenv` or `metin2_map_guild_battle_01.msenv`, and those two files differ only in that guild_battle_01 writes the skybox face block (with bTextureRenderMode 0 and 5 empty face strings). Visually identical to a1.

**Canonical: `a1.msenv`** (cluster C00 `clear_blue_noon`; used by `metin2_map_duel`, `metin2_map_oxevent`, `metin2_map_privateshop`, `metin2_map_pvp_arena`)

| Env | Maps | Cluster |
|---|---:|---|
| `a1.msenv` | 4 | C00 `clear_blue_noon` |
| `metin2_map_guild_battle_01.msenv` | 2 | C00 `clear_blue_noon` |

| Parameter | Observed range |
|---|---|
| `Fog.Enable` | 1 x6 |
| `Fog.NearDistance` | 5000 cm |
| `Fog.FarDistance` | 20000 cm |
| `Fog.Color` | #B0BDD6 |
| fog hue / sat / value | 219.5 deg / 0.178 / 0.839 |
| `Background.Ambient` | #000000 (mean level 0) |
| `Character.Ambient` level | 0.15 (always Background + 0.15) |
| `Background.Diffuse` | #FFF8F8 |
| light warmth (R-B of diffuse) | 0.0275 |
| sun elevation / azimuth | 48.5 deg / 211.9 deg |
| `Direction` vectors | `0.350156 0.562609 -0.748907` |
| `Material.Ambient` / `Emissive` | #E1DAC8 / #525269 |
| `GradientLevelUpper` / `Lower` | 4 x6 / 1 x6 |
| sky zenith | #1849A8 |
| sky horizon | #D9E6FF |
| sky nadir (below-horizon band) | #88909F |
| `bTextureRenderMode` | absent x4, 0 x2 |
| skybox face sets | none |
| `CloudTextureFileName` | clouds_zone01.tga |
| `CloudScale` / `CloudTextureScale` / `CloudSpeed` / `CloudHeight` | 200000 / 4 / 0.004 / 30000 |
| `Filter.Enable` / colour / AlphaSrc | 0 x6 / n/a / 1 |
| `LensFlare.Enable` / `MainFlareEnable` | 0 x6 / 1 x6 |

### `dungeon_block` - 23 maps, 6 distinct envs

Two sub-recipes. `dark.msenv` (11 maps) is the flat black box: ambient 0, fog #000000 5000->20000, GradientLevelUpper 1 with an all-zero gradient, no cloud texture. `skipia_dungeon.msenv` (6 maps) is the opposite trick - Fog.Enable 0, ambient raised to 0.57, and `blackout.dds` bound as the CLOUD texture to paint the dome black. Both read as 'no sky'.

**Canonical: `dark.msenv`** (cluster C05 `black_box`; used by `metin2_map_deviltower1`, `metin2_map_monkey_dungeon_11`, `metin2_map_monkey_dungeon_12`, `metin2_map_monkey_dungeon_13`, `metin2_map_monkeydungeon`, `metin2_map_mt_th_dungeon_01`, `metin2_map_smhdungeon_01`, `metin2_map_smhdungeon_02`, `metin2_map_snake_temple_02`, `metin2_map_spiderdungeon`, `metin2_map_spiderdungeon_03`)

| Env | Maps | Cluster |
|---|---:|---|
| `dark.msenv` | 11 | C05 `black_box` |
| `skipia_dungeon.msenv` | 6 | C07 `unfogged_cave` |
| `moonlight04.msenv` | 3 | C05 `black_box` |
| `anglar_dungeon_01.msenv` | 1 | C01 `murky_lowlight` |
| `monkeydungeon_02.msenv` | 1 | C05 `black_box` |
| `monkeydungeon_03.msenv` | 1 | C05 `black_box` |

| Parameter | Observed range |
|---|---|
| `Fog.Enable` | 1 x17, 0 x6 |
| `Fog.NearDistance` | 1-5000 (med 5000) cm |
| `Fog.FarDistance` | 20000 cm |
| `Fog.Color` | #000000, #0E011A, #1F1F28 |
| fog hue / sat / value | 0-271.2 (med 0) deg / 0-0.962 (med 0) / 0-0.157 (med 0) |
| `Background.Ambient` | #000000, #83839E, #93839E (mean level 0-0.5699 (med 0)) |
| `Character.Ambient` level | 0.15-0.7199 (med 0.15) (always Background + 0.15) |
| `Background.Diffuse` | #203D1C, #404055, #4D2929, #BFB6C1, #C1B8B6, #FFF8F8 |
| light warmth (R-B of diffuse) | -0.0824-0.1412 (med 0.0275) |
| sun elevation / azimuth | 48.5-69.4 (med 48.5) deg / 211.9, 244.7, 254.8 deg |
| `Direction` vectors | `0.33981 0.092631 -0.935921`, `0.350156 0.562609 -0.748907`, `0.596551 0.28178 -0.751483` |
| `Material.Ambient` / `Emissive` | #000000, #212128, #36443B, #564F4F, #E1DAC8 / #030101, #0A050F, #353945, #495D46, #525269 ... (6 total) |
| `GradientLevelUpper` / `Lower` | 1 x20, 4 x3 / 1 x23 |
| sky zenith | #000000, #1A0046 |
| sky horizon | #000000, #6E5936 |
| sky nadir (below-horizon band) | #000000, #2F0505 |
| `bTextureRenderMode` | absent x23 |
| skybox face sets | none |
| `CloudTextureFileName` | blackout.dds, clouds_zone02.tga, clouds_zone06.tga |
| `CloudScale` / `CloudTextureScale` / `CloudSpeed` / `CloudHeight` | 200000 / 1, 4, 5 / 0, 0.003, 0.004, 0.01 / 30000 |
| `Filter.Enable` / colour / AlphaSrc | 0 x23 / n/a / 1 |
| `LensFlare.Enable` / `MainFlareEnable` | 0 x23 / 1 x23 |

**Off-cluster members** (2):

- `skipia_dungeon.msenv` (metin2_map_boss_awaken_skipia, metin2_map_boss_crack_skipia, metin2_map_skipia_dungeon_01, metin2_map_skipia_dungeon_02, metin2_map_skipia_dungeon_boss, metin2_map_spiderdungeon_02) sits in **C07 `unfogged_cave`**, not the archetype modal **C05 `black_box`**
- `anglar_dungeon_01.msenv` (metin2_map_anglar_dungeon_01) sits in **C01 `murky_lowlight`**, not the archetype modal **C05 `black_box`**

### `dungeon_themed` - 21 maps, 11 distinct envs

The most heterogeneous archetype: 11 envs across 8 clusters. The rule that does hold is structural, not chromatic - 14 of 21 maps use `GradientLevelUpper 1`, and in 10 of those the zenith, horizon and nadir are literally the same colour: a flat single-tone dome tinted to the biome (dawnmist #2A2A3B, flame #814823, snow #495983, whitedragoncave #000000). Fog colour, not the sky, carries the theme.

**Canonical: `dawnmistwood_dungeon.msenv`** (cluster C01 `murky_lowlight`; used by `metin2_map_boss_awaken_dawnmist`, `metin2_map_boss_crack_dawnmist`, `metin2_map_dawnmist_dungeon_01`, `metin2_map_smhgate_dawnmist`)

| Env | Maps | Cluster |
|---|---:|---|
| `dawnmistwood_dungeon.msenv` | 4 | C01 `murky_lowlight` |
| `metin2_map_n_flame_dungeon_01.msenv` | 3 | C03 `warm_dusk` |
| `metin2_map_n_snow_dungeon_01.msenv` | 3 | C16 `singleton_metin2_map_n_snow_dungeon_01` |
| `metin2_map_otherworld_01.msenv` | 3 | C17 `singleton_metin2_map_otherworld_01` |
| `map_devilscatacomb.msenv` | 2 | C07 `unfogged_cave` |
| `metin2_map_n_flame_dragon_01.msenv` | 1 | C03 `warm_dusk` |
| `metin2_map_otherworld_02.msenv` | 1 | C00 `clear_blue_noon` |
| `metin2_map_secretdungeon.msenv` | 1 | C00 `clear_blue_noon` |
| `metin2_map_whitedragoncave_01.msenv` | 1 | C09 `void_pastel_fog` |
| `metin2_map_whitedragoncave_02.msenv` | 1 | C09 `void_pastel_fog` |
| `metin2_map_whitedragoncave_boss.msenv` | 1 | C18 `singleton_metin2_map_whitedragoncave_boss` |

| Parameter | Observed range |
|---|---|
| `Fog.Enable` | 1 x18, 0 x3 |
| `Fog.NearDistance` | 0-5000 (med 1000) cm |
| `Fog.FarDistance` | 20000-1000000 (med 25000) cm |
| `Fog.Color` | #161A2A, #1AC6F0, #2A2A3B, #804823, #814823, #8391E4, #8A94D0, #8DACE5 ... (11 total) |
| fog hue / sat / value | 8.6-240 (med 218.9) deg / 0.164-0.904 (med 0.476) / 0.165-0.941 (med 0.694) |
| `Background.Ambient` | #000000, #161616, #1D2954, #37383E, #383D46, #576392, #585858, #597E97 ... (9 total) (mean level 0-0.6327 (med 0.2444)) |
| `Character.Ambient` level | 0.15-0.7827 (med 0.3944) (always Background + 0.15) |
| `Background.Diffuse` | #7B724D, #A0D4FB, #A39E9E, #B27D61, #F6D1D1, #F8FCFF, #FFCFCC, #FFF8F8 ... (9 total) |
| light warmth (R-B of diffuse) | -0.3569-0.3176 (med 0.1451) |
| sun elevation / azimuth | 17.2-48.7 (med 31.9) deg / 149.8, 193.4, 211.9, 231.3, 244.7, 333.8 deg |
| `Direction` vectors | `-0.480032 0.825766 -0.296109`, `0.214282 0.900026 -0.379521`, `0.350156 0.562609 -0.748907`, `0.37428 -0.76174 -0.528836` ... (6 total) |
| `Material.Ambient` / `Emissive` | #2A4C1F, #57794C, #60777C, #7590B3, #947C65 ... (8 total) / #37383E, #425444, #524F4F, #525269, #525662 ... (9 total) |
| `GradientLevelUpper` / `Lower` | 1 x14, 2 x5, 4 x1, 5 x1 / 1 x19, 2 x2 |
| sky zenith | #000000, #18013A, #1849A8, #1C2136, #2A2A3B, #495983 ... (9 total) |
| sky horizon | #000000, #161A2A, #2A2A3B, #495983, #804823, #814823 ... (9 total) |
| sky nadir (below-horizon band) | #000000, #1D2236, #2A2A3B, #814823, #88909F, #FFFFFF |
| `bTextureRenderMode` | absent x12, 0 x9 |
| skybox face sets | capedragonhead |
| `CloudTextureFileName` | clouds_zone01.tga, clouds_zone06.tga, clouds_zone08.tga |
| `CloudScale` / `CloudTextureScale` / `CloudSpeed` / `CloudHeight` | 5000, 200000, 280000 / 3, 4, 5 / 0.001, 0.004, 0.01, 0.08 / 100, 30000 |
| `Filter.Enable` / colour / AlphaSrc | 0 x21 / n/a / 1, 2 |
| `LensFlare.Enable` / `MainFlareEnable` | 0 x21 / 1 x14, 0 x7 |

**Off-cluster members** (10):

- `metin2_map_n_flame_dungeon_01.msenv` (metin2_map_boss_awaken_flame, metin2_map_boss_crack_flame, metin2_map_n_flame_dungeon_01) sits in **C03 `warm_dusk`**, not the archetype modal **C01 `murky_lowlight`**
- `metin2_map_n_snow_dungeon_01.msenv` (metin2_map_boss_awaken_snow, metin2_map_boss_crack_snow, metin2_map_n_snow_dungeon_01) sits in **C16 `singleton_metin2_map_n_snow_dungeon_01`**, not the archetype modal **C01 `murky_lowlight`**
- `metin2_map_otherworld_01.msenv` (metin2_map_otherworld_01, metin2_map_otherworld_03, metin2_map_otherworld_04) sits in **C17 `singleton_metin2_map_otherworld_01`**, not the archetype modal **C01 `murky_lowlight`**
- `map_devilscatacomb.msenv` (metin2_map_devilscatacomb, metin2_map_smhgate_devils) sits in **C07 `unfogged_cave`**, not the archetype modal **C01 `murky_lowlight`**
- `metin2_map_n_flame_dragon_01.msenv` (metin2_map_n_flame_dragon) sits in **C03 `warm_dusk`**, not the archetype modal **C01 `murky_lowlight`**
- `metin2_map_otherworld_02.msenv` (metin2_map_otherworld_02) sits in **C00 `clear_blue_noon`**, not the archetype modal **C01 `murky_lowlight`**
- `metin2_map_secretdungeon.msenv` (metin2_map_secretdungeon_01) sits in **C00 `clear_blue_noon`**, not the archetype modal **C01 `murky_lowlight`**
- `metin2_map_whitedragoncave_01.msenv` (metin2_map_whitedragoncave_01) sits in **C09 `void_pastel_fog`**, not the archetype modal **C01 `murky_lowlight`**
- `metin2_map_whitedragoncave_02.msenv` (metin2_map_whitedragoncave_02) sits in **C09 `void_pastel_fog`**, not the archetype modal **C01 `murky_lowlight`**
- `metin2_map_whitedragoncave_boss.msenv` (metin2_map_whitedragoncave_boss) sits in **C18 `singleton_metin2_map_whitedragoncave_boss`**, not the archetype modal **C01 `murky_lowlight`**

### `elemental` - 4 maps, 6 distinct envs

Four maps, six envs, because elemental_01 and elemental_02 each ship a second preset swapped in by `EnvironmentRange`. The `_01` suffix variants have Fog.Enable 1; the base files have Fog.Enable 0 - so the range switch is literally a fog toggle plus a warmer/cooler horizon. Five of the six write a face block at bTextureRenderMode 0: `snow_dragon` for elemental_01, _01_01, _02, _02_01 and the orphan _03_01, and a nonexistent `smh-*.dds` set for elemental_03. `metin2_map_elemental_04.msenv` writes no face block at all.

**Canonical: `metin2_map_elemental_01_01.msenv`** (cluster C00 `clear_blue_noon`; used by `metin2_map_elemental_01`)

| Env | Maps | Cluster |
|---|---:|---|
| `metin2_map_elemental_01.msenv` | 1 | C11 `blue_fog_off` |
| `metin2_map_elemental_01_01.msenv` | 1 | C00 `clear_blue_noon` |
| `metin2_map_elemental_02.msenv` | 1 | C10 `dusk_fog_off` |
| `metin2_map_elemental_02_01.msenv` | 1 | C00 `clear_blue_noon` |
| `metin2_map_elemental_03.msenv` | 1 | C01 `murky_lowlight` |
| `metin2_map_elemental_04.msenv` | 1 | C00 `clear_blue_noon` |

| Parameter | Observed range |
|---|---|
| `Fog.Enable` | 1 x4, 0 x2 |
| `Fog.NearDistance` | 1000-5000 (med 5000) cm |
| `Fog.FarDistance` | 20000-30000 (med 20000) cm |
| `Fog.Color` | #1B163F, #91B5E6, #B86041, #BAC8D2, #E0E3F0, #ECF3FF |
| fog hue / sat / value | 15.6-247.3 (med 216.25) deg / 0.067-0.651 (med 0.242) / 0.247-1 (med 0.863) |
| `Background.Ambient` | #000000, #41586C (mean level 0-0.3412 (med 0)) |
| `Character.Ambient` level | 0.15-0.4912 (med 0.15) (always Background + 0.15) |
| `Background.Diffuse` | #8194AB, #FFF8F8, #FFFFFF |
| light warmth (R-B of diffuse) | -0.1647-0.0275 (med 0) |
| sun elevation / azimuth | 32.9-48.5 (med 32.9) deg / 211.9, 249.5 deg |
| `Direction` vectors | `0.350156 0.562609 -0.748907`, `0.786209 0.293521 -0.543802` |
| `Material.Ambient` / `Emissive` | #8A96B8, #B6A16E, #E1DAC8 / #525269, #655D83, #858585 |
| `GradientLevelUpper` / `Lower` | 4 x6 / 1 x6 |
| sky zenith | #000212, #00289D, #042455, #1D42BC, #375285, #5D7BDF |
| sky horizon | #1B163F, #91B5E6, #B1C5E8, #B86041, #BAC8D2, #E0E3F0 |
| sky nadir (below-horizon band) | #1B163F, #91B5E6, #B86041, #BAC8D2, #E0E3F0, #ECF3FF |
| `bTextureRenderMode` | 0 x6 |
| skybox face sets | smh, snow_dragon |
| `CloudTextureFileName` | clouds_zone01.tga, clouds_zone05.tga |
| `CloudScale` / `CloudTextureScale` / `CloudSpeed` / `CloudHeight` | 200000 / 4 / 0.004 / 20000, 30000 |
| `Filter.Enable` / colour / AlphaSrc | 0 x6 / n/a / 1 |
| `LensFlare.Enable` / `MainFlareEnable` | 0 x6 / 1 x6 |

**Off-cluster members** (3):

- `metin2_map_elemental_01.msenv` (metin2_map_elemental_01) sits in **C11 `blue_fog_off`**, not the archetype modal **C00 `clear_blue_noon`**
- `metin2_map_elemental_02.msenv` (metin2_map_elemental_02) sits in **C10 `dusk_fog_off`**, not the archetype modal **C00 `clear_blue_noon`**
- `metin2_map_elemental_03.msenv` (metin2_map_elemental_03) sits in **C01 `murky_lowlight`**, not the archetype modal **C00 `clear_blue_noon`**

### `trent_forest` - 2 maps, 2 distinct envs

Two maps, two wildly different envs. `trent.msenv` is the only file in the corpus whose light direction points slightly UP (sun elevation -1.5 deg) - the sun is below the horizon. `trent02.msenv` is a pink-lit oddity (ambient #E37E7E, diffuse #8F4661) that clusters with nothing.

**Canonical: `trent.msenv`** (cluster C06 `ember_orange`; used by `metin2_map_trent`)

| Env | Maps | Cluster |
|---|---:|---|
| `trent.msenv` | 1 | C06 `ember_orange` |
| `trent02.msenv` | 1 | C20 `singleton_trent02` |

| Parameter | Observed range |
|---|---|
| `Fog.Enable` | 1 x2 |
| `Fog.NearDistance` | 0-500 (med 250) cm |
| `Fog.FarDistance` | 15000-18000 (med 16500) cm |
| `Fog.Color` | #200E0E, #250F10 |
| fog hue / sat / value | 0-357.3 (med 178.65) deg / 0.562-0.595 (med 0.5785) / 0.125-0.145 (med 0.135) |
| `Background.Ambient` | #3F504F, #E37E7E (mean level 0.2902-0.6261 (med 0.4582)) |
| `Character.Ambient` level | 0.4402-0.7761 (med 0.6081) (always Background + 0.15) |
| `Background.Diffuse` | #8F4661, #FFFFFF |
| light warmth (R-B of diffuse) | 0-0.1804 (med 0.0902) |
| sun elevation / azimuth | -1.5-41.9 (med 20.2) deg / 204.3, 232.5 deg |
| `Direction` vectors | `0.411789 0.910903 0.026193`, `0.590855 0.453329 -0.66737` |
| `Material.Ambient` / `Emissive` | #689152, #7E7250 / #333333, #AC8E8E |
| `GradientLevelUpper` / `Lower` | 1 x2 / 1 x2 |
| sky zenith | #001326, #C88190 |
| sky horizon | #2F1500, #533B15 |
| sky nadir (below-horizon band) | #FF0000, #FFFFFF |
| `bTextureRenderMode` | absent x2 |
| skybox face sets | none |
| `CloudTextureFileName` | clouds_zone05.tga |
| `CloudScale` / `CloudTextureScale` / `CloudSpeed` / `CloudHeight` | 200000 / 4, 6 / 0.001 / 4500, 30000 |
| `Filter.Enable` / colour / AlphaSrc | 0 x2 / n/a / 2 |
| `LensFlare.Enable` / `MainFlareEnable` | 0 x2 / 0 x2 |

**Off-cluster members** (1):

- `trent02.msenv` (metin2_map_trent02) sits in **C20 `singleton_trent02`**, not the archetype modal **C06 `ember_orange`**

### `event_instance` - 10 maps, 16 distinct envs

Not a visual archetype - a bag of server-driven instances. Its 16 envs split into the 9-file `12zi_stage_*` family (one preset per boss stage, uniformly high ambient ~0.57, tiny fog near 100-700, `capedragonhead` faces, CloudHeight 100) and a set of one-offs. If the generator needs an 'event' look, sample the 12zi family; treat the rest as individual references.

**Canonical: `12zi_stage_02_02.msenv`** (cluster C04 `12zi_stylized_stage`; used by `metin2_12zi_stage`)

| Env | Maps | Cluster |
|---|---:|---|
| `defensewave_blue.msenv` | 2 | C03 `warm_dusk` |
| `miniboss.msenv` | 2 | C03 `warm_dusk` |
| `12zi_stage_01_02.msenv` | 1 | C12 `singleton_12zi_stage_01_02` |
| `12zi_stage_02_01.msenv` | 1 | C13 `singleton_12zi_stage_02_01` |
| `12zi_stage_02_02.msenv` | 1 | C04 `12zi_stylized_stage` |
| `12zi_stage_03_01.msenv` | 1 | C04 `12zi_stylized_stage` |
| `12zi_stage_03_02.msenv` | 1 | C04 `12zi_stylized_stage` |
| `12zi_stage_04_01.msenv` | 1 | C04 `12zi_stylized_stage` |
| `12zi_stage_04_02.msenv` | 1 | C04 `12zi_stylized_stage` |
| `12zi_stage_05_01.msenv` | 1 | C04 `12zi_stylized_stage` |
| `12zi_stage_05_02.msenv` | 1 | C04 `12zi_stylized_stage` |
| `metin2_guild_pve.msenv` | 1 | C01 `murky_lowlight` |
| `metin2_map_battleroyale.msenv` | 1 | C15 `singleton_metin2_map_battleroyale` |
| `metin2_map_mists_of_island.msenv` | 1 | C00 `clear_blue_noon` |
| `metin2_map_snake_temple.msenv` | 1 | C11 `blue_fog_off` |
| `metin2_map_treasure_hunt.msenv` | 1 | C00 `clear_blue_noon` |

| Parameter | Observed range |
|---|---|
| `Fog.Enable` | 1 x16, 0 x2 |
| `Fog.NearDistance` | 0-10000 (med 325) cm |
| `Fog.FarDistance` | 20000-50000 (med 27500) cm |
| `Fog.Color` | #272A3F, #2A758C, #2F3144, #362F1C, #3A3B5B, #44416B, #464660, #4B5B59 ... (16 total) |
| fog hue / sat / value | 0-244.3 (med 209.7) deg / 0.011-1 (med 0.3765) / 0.212-0.839 (med 0.412) |
| `Background.Ambient` | #000000, #262D33, #585347, #595C5E, #5D5223, #606467, #606BB1, #708393 ... (15 total) (mean level 0-0.6366 (med 0.4437)) |
| `Character.Ambient` level | 0.15-0.7866 (med 0.5938) (always Background + 0.15) |
| `Background.Diffuse` | #6B90C4, #898B92, #898E9A, #D4C9B5, #DADFE2, #DAE8E2, #E8DBD3, #E8F2F9 ... (14 total) |
| light warmth (R-B of diffuse) | -0.349-0.4745 (med -0.0138) |
| sun elevation / azimuth | 17.2-68.6 (med 47.9) deg / 35.1, 99.1, 101.0, 143.0, 149.8, 211.9, 222.0, 244.7 deg |
| `Direction` vectors | `-0.669884 0.10788 -0.734587`, `-0.630525 0.122095 -0.766506`, `-0.498026 0.661216 -0.561038`, `-0.480032 0.825766 -0.296109` ... (8 total) |
| `Material.Ambient` / `Emissive` | #5B5050, #8E8772, #8EAAAA, #93AAAA, #95907E ... (15 total) / #151311, #3B3838, #3B3B42, #504242, #525269 ... (7 total) |
| `GradientLevelUpper` / `Lower` | 2 x9, 3 x5, 4 x2, 1 x1, 5 x1 / 1 x18 |
| sky zenith | #000000, #0028FF, #008087, #030E21, #052F03, #0A0005 ... (9 total) |
| sky horizon | #000000, #088CAC, #3F3F6B, #434561, #508084, #61B380 ... (14 total) |
| sky nadir (below-horizon band) | #000000, #434561, #5D2929, #88909F, #ADAEAC, #DAE1E2 ... (8 total) |
| `bTextureRenderMode` | 0 x12, 1 x6 |
| skybox face sets | bayblacksand, capedragonhead, dawnmistwood |
| `CloudTextureFileName` | clouds_zone01.tga, clouds_zone06.tga, clouds_zone07.tga, clouds_zone08.tga |
| `CloudScale` / `CloudTextureScale` / `CloudSpeed` / `CloudHeight` | 5000, 200000 / 3, 4, 5 / 0.001, 0.004, 0.01, 0.08 / 100, 200, 30000 |
| `Filter.Enable` / colour / AlphaSrc | 0 x16, 1 x2 / #413628, #4B1818 / 1, 2 |
| `LensFlare.Enable` / `MainFlareEnable` | 0 x18 / 1 x13, 0 x5 |

**Off-cluster members** (9):

- `defensewave_blue.msenv` (metin2_map_defensewave, metin2_map_defensewave_port) sits in **C03 `warm_dusk`**, not the archetype modal **C04 `12zi_stylized_stage`**
- `miniboss.msenv` (metin2_map_miniboss_01, metin2_map_miniboss_02) sits in **C03 `warm_dusk`**, not the archetype modal **C04 `12zi_stylized_stage`**
- `12zi_stage_01_02.msenv` (metin2_12zi_stage) sits in **C12 `singleton_12zi_stage_01_02`**, not the archetype modal **C04 `12zi_stylized_stage`**
- `12zi_stage_02_01.msenv` (metin2_12zi_stage) sits in **C13 `singleton_12zi_stage_02_01`**, not the archetype modal **C04 `12zi_stylized_stage`**
- `metin2_guild_pve.msenv` (metin2_guild_pve) sits in **C01 `murky_lowlight`**, not the archetype modal **C04 `12zi_stylized_stage`**
- `metin2_map_battleroyale.msenv` (metin2_map_battleroyale) sits in **C15 `singleton_metin2_map_battleroyale`**, not the archetype modal **C04 `12zi_stylized_stage`**
- `metin2_map_mists_of_island.msenv` (metin2_map_mists_of_island) sits in **C00 `clear_blue_noon`**, not the archetype modal **C04 `12zi_stylized_stage`**
- `metin2_map_snake_temple.msenv` (metin2_map_snake_temple_01) sits in **C11 `blue_fog_off`**, not the archetype modal **C04 `12zi_stylized_stage`**
- `metin2_map_treasure_hunt.msenv` (metin2_map_treasure_hunt) sits in **C00 `clear_blue_noon`**, not the archetype modal **C04 `12zi_stylized_stage`**

### `dev_stub` - 4 maps, 3 distinct envs

Four unfinished test maps. `t1.msenv` and `t2.msenv` are byte-identical (and identical in content to `war2.msenv` bar the fog near). t3/t4 share `moonlight05.msenv`, which is `trent.msenv` with the light direction reset to the engine default `0.5 0.5 -0.5`, fog moved from 0->18000 to 10000->20000, CloudHeight 4500->4000 and CloudTextureScale 6->4. Nothing here is worth generalising from.

**Canonical: `moonlight05.msenv`** (cluster C06 `ember_orange`; used by `metin2_map_t3`, `metin2_map_t4`)

| Env | Maps | Cluster |
|---|---:|---|
| `moonlight05.msenv` | 2 | C06 `ember_orange` |
| `t1.msenv` | 1 | C01 `murky_lowlight` |
| `t2.msenv` | 1 | C01 `murky_lowlight` |

| Parameter | Observed range |
|---|---|
| `Fog.Enable` | 1 x4 |
| `Fog.NearDistance` | 2-10000 (med 5001) cm |
| `Fog.FarDistance` | 20000-40000 (med 30000) cm |
| `Fog.Color` | #250F10, #69594E |
| fog hue / sat / value | 24.4-357.3 (med 190.85) deg / 0.257-0.595 (med 0.426) / 0.145-0.412 (med 0.2785) |
| `Background.Ambient` | #3F504F, #725353 (mean level 0.2902-0.366 (med 0.3281)) |
| `Character.Ambient` level | 0.4402-0.516 (med 0.4781) (always Background + 0.15) |
| `Background.Diffuse` | #A39494, #FFFFFF |
| light warmth (R-B of diffuse) | 0-0.0588 (med 0.0294) |
| sun elevation / azimuth | 35.3-48.7 (med 42) deg / 225.0, 244.7 deg |
| `Direction` vectors | `0.5 0.5 -0.5`, `0.596551 0.28178 -0.751483` |
| `Material.Ambient` / `Emissive` | #715F40, #7E7250 / #333333, #413C3C |
| `GradientLevelUpper` / `Lower` | 1 x2, 5 x2 / 1 x4 |
| sky zenith | #001326, #0C0505 |
| sky horizon | #2F1500, #69594E |
| sky nadir (below-horizon band) | #2D110F, #FF0000 |
| `bTextureRenderMode` | absent x4 |
| skybox face sets | none |
| `CloudTextureFileName` | clouds_zone01.tga, clouds_zone05.tga |
| `CloudScale` / `CloudTextureScale` / `CloudSpeed` / `CloudHeight` | 200000 / 4, 5 / 0.001, 0.01 / 4000, 30000 |
| `Filter.Enable` / colour / AlphaSrc | 0 x4 / n/a / 1, 2 |
| `LensFlare.Enable` / `MainFlareEnable` | 0 x4 / 0 x2, 1 x2 |

**Off-cluster members** (2):

- `t1.msenv` (metin2_map_t1) sits in **C01 `murky_lowlight`**, not the archetype modal **C06 `ember_orange`**
- `t2.msenv` (metin2_map_t2) sits in **C01 `murky_lowlight`**, not the archetype modal **C06 `ember_orange`**

---

## 7. Surprising env choices

The cases where a map's environment does not match what its archetype would predict, ranked by
how much it matters to a generator.

**`metin2_map_milgyo` (field_empire) uses `milgyo.msenv`, a desert preset.** milgyo is classified field_empire on its terrain and object families, but its env is the same sand-haze file (`NearDistance 1`, `FarDistance 50000`, fog #E6CDAC, ambient 0.70) that 8 desert maps use. It is the only env in the corpus shared across two archetypes other than a1. Generating a temple map on empire terrain should therefore pull the desert preset, not the a1 one.

**`metin2_map_capedragonhead` (darkforest_coast) uses the brightest fog span in the corpus.** `capedragonhead.msenv` is fog 20000 -> 80000 cm - the widest span of any file except whitedragoncave_02's degenerate 1,000,000, and 3.2x the corpus median far distance. It is a clear-blue-noon (C00) preset dropped into an archetype whose other four members are dusk/murk. It is also one of the 15 files that actually renders its skybox cube.

**`metin2_map_otherworld_02` and `metin2_map_secretdungeon_01` (dungeon_themed) use daylight skies.** Both sit in C00 with a full 4+1 blue gradient and clouds_zone01, i.e. they are outdoor-looking maps filed as dungeons. `metin2_map_otherworld_02.msenv` is close to `a1.msenv` with the ambient lifted to 0.345.

**`metin2_map_elemental_01/02` toggle fog via `EnvironmentRange`, not colour.** The base file has `Fog.Enable 0`, the `_01` variant has `Fog.Enable 1` with the same fog distances. Crossing the y=640 half-cell line literally switches fog on. This is the only use of `EnvironmentRange` in the corpus and the only place fog is used as a gameplay-region cue.

**`metin2_map_empirecastle` (eastplain) is `eastplain_01` with the fog switched off.** Same gradient, same face set, same cloud sheet; `Fog.Enable 0` and a slightly different ambient. Because the HTP renderer still uses `Fog.Color`/`FarDistance` for the far terrain band, the map still fades to a flat #3D595D beyond 26,600 cm (266 m, just over one sector) - the toggle only removes the mid-range fog blend.

**`map_n_flame_01.msenv` lights a lava field with a teal key.** `Background.Diffuse #5DAB9B` (warmth -0.243) under a #87381F horizon and #85361C fog. Four other files use a cool diffuse the same way; the strongest is `metin2_map_n_snow_dungeon_01.msenv` at -0.357.

**`trent.msenv` puts the sun below the horizon.** `Direction 0.411789 0.910903 0.026193` - the only file with a positive z, i.e. the light travels upward. Derived sun elevation -1.5 deg. Every other file is between 16.5 and 69.4 deg.

**`skipia_dungeon.msenv` paints the sky black with a cloud texture.** `Fog.Enable 0`, gradient collapsed to 1+1, and `CloudTextureFileName "blackout.dds"` - a 64x64 solid-black DXT5. Six dungeon_block maps use it. `blackout.msenv` does the same thing through `MainFlareTextureFileName` instead, which does nothing because LensFlare.Enable is 0.

**`metin2_guild_war2` (field_empire) is on a murky dev preset.** `war2.msenv` is byte-identical to `t1.msenv` and `t2.msenv` (the dev stubs) apart from one line - `NearDistance 700` vs `2` - giving a fog #69594E 700 -> 40000 under a collapsed brown sky,  while `metin2_guild_war1`, `war3` and `war4` are all on the a1 daylight sky. The guild-war set never got a coherent look.

**`eastplain_02` is the only user of three otherwise-unused knobs.** `CloudScale 2900000` (14.5x the corpus norm), `CloudTextureScale 20`, `clouds_zone10.tga` and the `smhtower` face set - all singletons in the corpus.

---

## 8. Duplicates, orphans and map-local overrides

### Byte-identical groups

104 files, **92 distinct MD5s**. The 9 duplicate groups:

- `a1.msenv` = `c1.msenv` = `war4.msenv`
- `a2.msenv` = `b2.msenv` = `c2.msenv`
- `a3.msenv` = `b3.msenv` = `c3.msenv`
- `eastplain_01.msenv` = `eastplain_03.msenv`
- `metin2_guild_pve.msenv` = `metin2_guild_pvp.msenv`
- `metin2_guild_war1.msenv` = `metin2_guild_war3.msenv`
- `metin2_map_elemental_03_01.msenv` = `metin2_map_guild_battle_02.msenv`
- `metin2_map_mists_of_island.msenv` = `metin2_mists_of_island.msenv`
- `t1.msenv` = `t2.msenv`

Note `b1.msenv` is **not** in the a1/c1/war4 group - it differs in exactly two places:
`Fog.Color` (#B0BDD6 -> #D8E6FF) and the last two gradient rows.

### Orphans

**23 of 104** are named by no `setting.txt` in the corpus:

`b2.msenv`, `battle_guild01.msenv`, `blackout.msenv`, `c2.msenv`, `eastplain.msenv`, `latesummer.msenv`, `map_dd.msenv`, `map_dd_teste.msenv`, `map_n_desert_01.msenv`, `metin2_battleroyale.msenv`, `metin2_guild_pvp.msenv`, `metin2_map_elemental_03_01.msenv`, `metin2_map_golden_land_night.msenv`, `metin2_map_guild_battle_02.msenv`, `metin2_map_guild_battle_03.msenv`, `metin2_map_n_snow_dragon.msenv`, `metin2_mists_of_island.msenv`, `monkeydungeon.msenv`, `mt_th_dragon.msenv`, `resources_zon.msenv`, `spiderdungeon.msenv`, `t5.msenv`, `ydragon.msenv`

Present in the pack but named by no setting.txt in the 142-map corpus. Several are the obvious A/B twin of a shipped file (b2/c2 vs a2, metin2_guild_pvp vs metin2_guild_pve, metin2_mists_of_island vs metin2_map_mists_of_island, metin2_map_elemental_03_01) and are safe to sample from; map_dd_teste and map_dd are editor scratch.

### Map-local overrides (these win - resolution is map dir first)

| Map | File | Same as global? | Referenced by its own setting.txt? |
|---|---|---|---|
| `metin2_map_devilscatacomb` | `map_dd_teste.msenv` | **NO** | no |
| `metin2_map_devilscatacomb` | `map_dd_teste_old.msenv` | no global twin | no |
| `metin2_map_empirecastle` | `a1.msenv` | yes | no |
| `metin2_map_empirewar01` | `snowm02.msenv` | yes | yes |
| `metin2_map_empirewar02` | `a1.msenv` | yes | yes |
| `metin2_map_empirewar03` | `desert_02.msenv` | yes | yes |
| `metin2_map_skipia_dungeon_01` | `skipia_dungeon.msenv` | yes | yes |
| `metin2_map_skipia_dungeon_02` | `skipia_dungeon.msenv` | yes | yes |
| `metin2_map_skipia_dungeon_boss` | `skipia_dungeon.msenv` | yes | yes |
| `metin2_map_spiderdungeon_02` | `skipia_dungeon.msenv` | **NO** | yes |

Two of the ten are real overrides:

- `<CORPUS>/metin2_map_spiderdungeon_02/skipia_dungeon.msenv` changes **`Material.Diffuse`**
  (line 24) from `0.509804 0.431373 0.607843` (global - a violet tint modulated onto every
  terrain patch and object) to `1.000000 0.984314 0.984314` (local, near-white, i.e. no tint).
  The five other maps that name `skipia_dungeon.msenv` get the violet one; spiderdungeon_02
  does not.
- `<CORPUS>/metin2_map_devilscatacomb/map_dd_teste.msenv` changes **`Material.Ambient`** (line 25) from
  `0 0 0` to `0.952941 0.984314 1.0` - but that map's setting.txt names
  `map_devilsCatacomb.msenv`, so the local file (and its identical twin `map_dd_teste_old.msenv`)
  is editor scratch that never loads.

### Multi-environment maps

- **`metin2_12zi_stage`**: Environment + Environment1..Environment8 = 9 presets, one per boss stage, switched by the server. No EnvironmentRange.
- **`metin2_map_elemental_01`**: Environment + Environment1 plus EnvironmentRange1 "0 0 1280 640" and EnvironmentRange2 "0 640 1280 1280". 5x5 sectors x 256 half-cells = 1280, so the rect is in half-cells (100 cm). Splits the map north/south.
- **`metin2_map_elemental_02`**: same shape as elemental_01.
- metin2_map_elemental_03 ships only one Environment even though metin2_map_elemental_03_01.msenv exists in the pack (orphan).

---

## 9. Gotchas for the generator

- `ScriptType` must be written as the misspelled `EnvrionmentData`. All 104 shipped files carry the typo; the loader never validates it, but WorldEditorRemix's corrected spelling is what makes its output diff against every vanilla file. `msenv.py` preserves the typo by default.
- Gradient entry order is **zenith first**. `gradient[0].FirstColor` is the sky directly overhead; `gradient[Upper-1].SecondColor` is the horizon; entries `Upper..Upper+Lower-1` are the below-horizon band and `gradient[-1].SecondColor` is the nadir. Reading it backwards produces a sky that is bright at the top and dark at the horizon, which no shipped file does.
- `len(List Gradient) / 8` must equal `GradientLevelUpper + GradientLevelLower` exactly, or `MapUtil.cpp:181-184` discards the whole gradient with no error and the dome renders untinted. Zero shipped files trip this, so there is no in-corpus example of the failure to imitate.
- Setting `*FaceFileName` without `bTextureRenderMode 1` is inert. If the generator wants a cube sky it must set both; if it wants a gradient sky it should omit the whole face block the way the 45 face-less files do (they omit `bTextureRenderMode` too).
- Only 7 skybox face sets exist in the pack (`bayblacksand`, `capedragonhead`, `dawnmistwood`, `late_summer`, `smhtower`, `snow_dragon`, `thunder`) and none of them ships a bottom face. Every shipped file writes `BottomFaceFileName ""`. Do not invent set names - `metin2_map_elemental_03.msenv` references `smh-*.dds` and `eastplain*.msenv` reference `eastplain_*.dds`, neither of which exist.
- `clouds_zone06.tga` is a 204-byte 32x32 stub. Six files use it; if the generator wants visible clouds it should pick `clouds_zone01` (54 uses), `02` (16), `05` (9), `08` (9), `07` (2) or `10` (1).
- The whole `Group LensFlare` is dead - `Enable` is 0 in all 104 files and `m_bEnabled` gates every path in `LensFlare.cpp`. Write the group for round-trip fidelity (all six keys, with the modal values `0 / 1 0.886275 0.886275 1 / 0.74 / 1 / sunflare.dds / 0.35`) but do not expect a visual.
- Fog distances are centimetres, unscaled, and `FarDistance` doubles as the terrain texture-draw radius. Values above ~40000 cm are a real performance decision, not a look decision. The corpus median far is 25000 cm = 125 cells = just under one sector.
- `Fog.Enable 0` does **not** turn off the fog colour's influence: the far terrain band is still flat-filled with `Fog.Color` (`MapOutdoorRenderHTP.cpp:60`). Eleven files ship with fog disabled and all eleven still set a meaningful fog colour.
- `Group Filter` is as dead as `Group LensFlare`, for two independent reasons. `EterLib/ScreenFilter.cpp:29-32` is `void CScreenFilter::SetEnable(BOOL /*bFlag*/) { m_bEnable = FALSE; }` - the setter throws its argument away - and `Render()` bails on `!m_bEnable`. And even if it ran, 5 of the 9 `Enable 1` files (a3, b3, c3, e1, 12zi_stage_02_01) specify `AlphaSrc 1` = D3DBLEND_ZERO with `AlphaDest 2` = D3DBLEND_ONE, which is an identity blend. Only bayblacksand, metin2_guild_pve, metin2_guild_pvp and metin2_map_guild_battle_03 (`AlphaSrc 2`, colour #4B1818) describe a real additive red tint. Write the group; do not use it as a look knob.
- Case is inconsistent in `setting.txt` references (`A1.msenv` vs `a1.msenv`, `N-snowm01.msenv`, `DawnMistWood.msenv`, `map_devilsCatacomb.msenv`, `CapeDragonHead.msenv`). Windows does not care; anything case-sensitive must fold. The same applies to the asset paths inside the files, which mix `D:\Ymir Work\`, `D:\YMIR WORK\`, `d:/ymir work/` and both slash directions - sometimes within one file.
- `metin2_guild_village_01/02/03` have no `setting.txt` at all and therefore no `Environment` key; they inherit `guild_village.msenv` through `ParentMapName`. Any tool that assumes every map names an env will drop three maps.
- Do not derive an env from the map name. `a1.msenv` is used by 9 maps across 3 archetypes; `metin2_map_a1`'s own env is not distinguishable from `metin2_map_c1`'s (they are byte-identical). Conversely `metin2_map_e1_01/02/03` are proxies with no sectors that still name `e1.msenv`.

---

## 10. Where to find what

| Question | JSON path in `reference/catalog/environments.json` |
|---|---|
| Everything about one file | `environments["<name>.msenv"]` (83 fields incl. every gradient stop) |
| Which maps use it, and their archetypes | `environments[...].used_by_maps` / `.archetypes` |
| Which cluster it landed in | `environments[...].cluster` -> `clusters["C.."]` |
| The preset to sample for archetype X | `archetype_presets["X"].canonical_env` + `.ranges` |
| Off-cluster members of archetype X | `archetype_presets["X"].surprises` |
| What every non-`.msenv` file is for | `folder_inventory.non_msenv` |
| Every `Environment*` / `EnvironmentRange*` line in the corpus | `map_references` |
| Byte-identical files | `duplicate_groups` |
| Files a map dir overrides | `map_local_overrides` |
| The engine facts above, with source line numbers | `engine_semantics` |


# The Object Vocabulary — `property/**/*.pr?`

How to read Ymir's 2 113 static-object definitions: what a prop is, how to tell from its name and
path, and where the traps are.

Machine-readable companion: [`catalog/objects.json`](catalog/objects.json) — one entry per CRC.
Codec: `scripts/m2map/codec/property.py`. Container format: see that module's docstring.

Everything below was measured from
`<CLIENT_PACK>/property/property` (2 113 files),
`D:/ymir work/` (27 203 art files), and the 142-map corpus in `<CORPUS>`
(1 341 `areadata.txt` files, 48 774 object records).

---

## 1. The shape of the database

| PropertyType | Ext | Count | Model key | Model kind |
|---|---|---|---|---|
| `Building` | `.prb` | 1 734 | `buildingfile` | `.gr2` Granny mesh |
| `DungeonBlock` | `.prd` | 195 | `dungeonblockfile` | `.gr2` Granny mesh |
| `Effect` | `.pre` | 97 | `effectfile` | `.mse` effect script |
| `Tree` | `.prt` | 85 | `treefile` | `.spt` SpeedTree |
| `Ambience` | `.pra` | 2 | *(none)* | sound paths only |

2 113 files → **2 112 distinct CRCs**. All 2 113 parse with **zero schema violations**: no missing
required key, no unexpected key, no extension/type mismatch, no key out of `std::map` order, no
malformed body line, no non-canonical CRC text. This database is unusually clean — the mess is all
in *what the files point at*, not in the files.

**`PropertyType` is authoritative; the extension is a convention.** Read the key, never the suffix.

### Keys you will actually see

- `shadowflag` — on **all 1 734** Buildings and nothing else. Nominally optional, universal in
  practice: emit it on every new Building. 1 706 are `1`, 28 are `0`.
- `treesize` = `1000.000000` and `treevariance` = `0.000000` on **all 85** Trees. Both are
  required-but-constant; they carry no information in shipped data. Emit those exact literals.
- `isattributedata` — 152 Buildings, always `"0"`, all under `b/`. See §6.
- Ambience carries `playtype` / `playinterval` / `playintervalvariation` /
  `maxvolumeareapercentage` / `ambiencesoundvector`. Both shipped files are `LOOP`, interval 0:
  `warp` (`sound/ambience/warp_test.mp3`, 0.5) and `waterfall` (`sound/ambience/waterfall.wav`,
  0.3). Neither is placed in any map in the corpus.

### `shadowflag = 0` means "thin or see-through"

All 28 are geometry a blob shadow would smear: 10 chains (`5st_chain_001..008`,
`flame_chain_001..008`), 3 fences (`5st_fence_002..004`), 3 `rock_pillar`, `ice_pillar_s05`,
`icicle_up_05`, `cliff_wall_up`, 3 `treasure_hunt_rock`, `treasure_hunt_cave_01`, `boss_d_gate_01`,
`ep-007-itemshop`. **20 of the 28 also have no `.mdatr`** — decorative and non-colliding. Rule of
thumb: set `shadowflag 0` iff the mesh is thin or alpha-cut.

---

## 2. Identity: address props by CRC, and only by CRC

Three separate reasons the obvious alternatives break.

**`PropertyName` is not unique.** 130 names are shared by 263 properties with different CRCs. The
worst case is `temple/` vs `12temple/`: **12temple is a re-authored copy of the temple set with the
same PropertyNames and different CRCs** — `5st_wall_001` is `723775272` in `temple/` and
`1238046944` in `12temple/`. Same for `5st_cliff_hom01..05`, `5st_gate_001/002`,
`5st_pillar_001/002`, `5st_bell_001`. Matching by name silently picks the wrong one.

**The model path is not unique either.** 13 `.gr2`/`.spt`/`.mse` paths are claimed by two CRCs
each — `b3_beech_rt3.spt`, `b-general_external01..04.gr2`, `b-general_wbridge01.gr2`, `sign.gr2`,
`b1-024-10m-bridge.gr2`, `dawnmist_gate.gr2`, `tent_ss_lamp.mse`. Typically one entry per continent
folder (`Beech3` exists as `3455398876` in `a/나무/` with 522 placements and `2585303992` in
`b/03.웅귀촌/나무/` with 88). Deduplicating by model path would merge distinct CRCs and corrupt
existing maps.

**The filename is not the name.** Some files are `<model>.gr2.prb` — `b/10.공용/hay_01.gr2.prb`,
`guild_construction/forge.gr2.prb`, `n/milgyo/milgyo_pavilion.gr2.prb`. The `.gr2` is part of the
stem, and in those files `PropertyName` often keeps a literal `.GR2` too. Read line 0 for the CRC
and the `propertyname` key for the name; derive neither from the path.

**One real CRC collision.** `1740984444` is written by two files —
`devils_dragon_island/mtthunder_thorn01.prb` and
`devils_dragon_island/thing/obj_mtthund_thorn01.prb` — which are **byte-identical**
(md5 `a008d9e8929c47c1a87edebebd2318ad`). `CPropertyManager::Register` lets the last-scanned file
win; because they are identical it is harmless, but CRC → file is not 1:1.

---

## 3. Folder → biome

The top-level directory under `property/` is the **authoring zone**, and it maps cleanly onto the
map archetypes that consume it. Korean folder names on disk are CP949 bytes mis-decoded as latin-1
by whatever unpacked the client; recover them with `name.encode("latin-1").decode("cp949")`.
`objects.json` carries both the raw on-disk path (`file`) and the readable form
(`file_dir_korean`).

### The three empire capitals

| Dir | Korean | Props | Reads as |
|---|---|---|---|
| `a/01.성` | 성 = castle | 32 | Empire A (Shinsoo) city |
| `a/나무` | 나무 = tree | 17 | **the shared temperate tree set** |
| `b/01.성` | | 41 | Empire B (Chunjo) city |
| `c/01.성` | | 36 | Empire C (Jinno) city |

`a/나무`'s 17 SpeedTrees are placed by `a1`, `b1`, `c1`, `a2`, `threeway` and `smhgate_a1` alike —
they are the common temperate vegetation of **all three** capitals, not an Empire-A set. They are
also the most-placed props in the game after the Skipia resource sparkles: `Pagoda1` 746,
`Pagoda2` 690, `Beech4` 662, `Pagoda3` 650.

### `b/` — the oldest folder and the game-wide common vocabulary

466 props, the largest. Its numbered Korean sub-directories are the Empire-B sub-biomes, and the
number in the folder name matches the number embedded in the `ob-<N>-…` prop names:

| Folder | Korean | English | Props |
|---|---|---|---|
| `b/01.성` | 성 | castle / city | 41 |
| `b/02.감염&해골탑` | 감염&해골탑 | infection & skeleton tower | 54 (+16 나무) |
| `b/03.웅귀촌` | 웅귀촌 | Ungwi (bear-spirit) village | 10 (+16 나무) |
| `b/04.뾰족산지역` | 뾰족산지역 | jagged-mountain region | 1 |
| `b/05.무덤가` | 무덤가 | graveyard | 15 |
| `b/06.늑대숲` | 늑대숲 | wolf forest | 1 |
| `b/07.밀교사원` | 밀교사원 | esoteric (tantric) temple | 7 |
| `b/08.숲지역` | 숲지역 | forest region | 1 |
| `b/09.절벽` | 절벽 | cliff | 2 |
| `b/10.공용` | 공용 | **common / shared** | 180 (+7 in `10_01`) |
| `b/11.랜드마크` | 랜드마크 | landmark | 2 |
| `b/12.공용` | 공용 | common (second batch) | 9 |
| `b/13.바위` | 바위 | rock | 29 |
| `b/eff` | | effects | 73 |
| `b/ambience` | | **both `.pra` files in the game** | 2 |

`b/10.공용` is the single most important directory in the database: it holds the `general_obj_*`
clutter vocabulary that every later zone re-skins.

### `n/` — continent N, one sub-directory per biome

363 props. `n/desert`, `n/icemount`, `n/milgyo`, `n/nersluck`, `n/oxevent`, `n/obj/flame`,
`n/obj/map_n_desert_01` (+`나무`), `n/obj/snow.m` (+`icebon`, `icemount`, `나무`).

### The rest, with their dominant consumers

| Dir | Props | Placed | Theme / archetype | Top consumer |
|---|---|---|---|---|
| `devils_dragon_island` | 192 | 181 | coastal dark forest; `camp/` orc camp, `thing/bone/` whale skeletons | dawnmistwood 1133 |
| `dawnmistwood_dungeon` | 114 | 101 | turtle dungeon — heavily reused outside itself | dawnmist_dungeon_01 859 |
| `eastplain` | 99 | 94 | giant/desert plain; `building/`, `gaint_desert/`, `obj/` | eastplain_01 1006 |
| `ghost` | 76 | 30 | haunted set — most under-used non-dark folder | eastplain_01 45 |
| `temple` | 70 | 68 | Ochao/temple dungeon | 12zi_stage 694 |
| `defensewave` | 51 | 39 | ship-deck siege event | defensewave 109 |
| `otherworld` | 44 | 42 | Yohara-era | otherworld_01 505 |
| `flame_dungeon` | 41 | 40 | volcano | n_flame_dungeon_01 270 |
| `12temple` | 37 | **0** | zodiac temple — **entirely dark**, all 37 models missing | — |
| `secretdungeon` | 37 | 36 | | secretdungeon_01 751 |
| `treasure_hunt` | 33 | 28 | event | treasure_hunt 150 |
| `thief_dungeon` | 31 | 23 | **31 props carry the corpus's heaviest load**: skipia_dungeon_01/02/boss place 7576/7267/6493 | skipia_dungeon_01 |
| `geuglagsa` | 30 | 26 | snake temple | snake_temple_01 484 |
| `whitedragoncave` | 29 | 27 | 3 sub-dirs (`_01`, `_02`, `boss`) | whitedragoncave_01 301 |
| `mists_of_island` | 28 | 22 | | mists_of_island 92 |
| `ydragon` | 27 | **3** | desert — **effectively dark**, 26/27 models missing | — |
| `guild_construction` | 25 | **2** | guild-castle buildings — **spawned at runtime**, not authored into maps; all 25 models missing | — |
| `miniboss` | 23 | 18 | | miniboss_01 40 |
| `golden_land` | 21 | 21 | event stage | golden_land_stage 114 |
| `snakevalley` | 20 | 20 | | snakevalley 333 |
| `anglar_dungeon` / `maze_dungeon` / `monkey_dungeon` | 18 each | 17/18/18 | dungeon block sets | 389 / 88×3 / 88×3 |
| `dragon_map` | 17 | **3** | snow-dragon lair — 14/17 models missing (the 3 that resolve, under `zone/dungeon/flame_dragon/`, are exactly the 3 ever placed) | — |
| `mt_thunder_dungeon` | 15 | 11 | | mt_th_dungeon_01 604 |
| `snow_dungeon` | 15 | 15 | | n_snow_dungeon_01 73 |
| `resources_picking` | 14 | **0** | gathering nodes — **runtime-spawned** | — |
| `devil_underground` / `smh_tower` / `guild_battle` | 9 each | 9 | | |
| `spider_dungeon` | 8 | 7 | | spiderdungeon_03 57 |
| `e1` | 6 | 6 | | e1 14 |
| `duel` | 5 | 5 | arena floor rings — same ring in pvp_arena/duel/oxevent (174/174/171) | |
| `deviltower` / `guild_pvp` | 4 each | 4 | | |
| `boss_d` | 1 | 1 | one boss door | labyrinth 4 |
| `sample` | 1 | 1 | editor junk named `666`, model missing, **yet placed 5× each in `smhgate_devils` and `devilscatacomb`** | |

**428 of 2 112 properties are never placed anywhere in the corpus** — 20 %. Concentrated in
`n` (104), `b` (69), `ghost` (46), `12temple` (37), `ydragon` (24), `guild_construction` (23).

Conversely: **1 684 distinct CRCs are referenced by the 142 maps, and 1 684 of 1 684 (100 %)
resolve** against this catalog. There are no dangling references anywhere in the corpus.

---

## 4. Naming conventions — how to read an unfamiliar asset

### SpeedTrees (`.spt`, 85 props)

```
<continent><biome-index>_<species>_rt[<variant>][_<season>][_<NN>].spt
```

All 85 `treefile` paths point at the **flat** `d:/ymir work/tree/` — there is no per-zone tree
directory. A tree's biome is encoded in the `.spt` prefix, and separately in which
`property/<zone>/나무/` directory the `.prt` sits in.

| Prefix | n | Biome | Species |
|---|---|---|---|
| `b1` | 15 | Empire-B temperate | baobab, beech, montereycypress, pagodatree, sassafras |
| `b2` | 16 | Empire-B second belt | cedaroflebanon, ivyspy, japanesemaple, redoak (+`_winter`, `_fall`) |
| `b3` | 17 | Empire-B third belt | beech, pagodatree, shingleoak, umbrellathorn (+`_winter`, `_fall`, `_flowers`) |
| `n1` | 14 | **snow** | every stem is `_winter`, or a cold species (coloradobluespruce, whitepine) |
| `n2` | 22 | **desert / tropical** | aloevera, bananatree, cinnamonfern, coconutpalm, curlypalm, datepalm, joshuatree, palmetto |
| — | 1 | seasonal event | `christmastree.spt` (model **missing**) |

`rt` = SpeedTree *RealTime* export. A trailing bare digit (`rt2`, `rt3`) is a shape variant of the
same species, not a different plant.

### Effects (`.mse`, 97 props)

86 of 97 point at the flat `d:/ymir work/effect/background/`. The rest: `effect/etc/fall` (4),
`effect/etc/christmas` (3, all missing), and 4 that abuse a zone dir
(`zone/dungeon/haven_dungeon/*.mse`).

- **`fire_<building-name>.mse`** — 9 of the 11 `fire_*` effects are named after the exact
  `PropertyName` of a Building: `fire_general_obj_lamp` → `general_obj_lamp`,
  `fire_ob-11-02-stonelight01` → `ob-11-02-stonelight01`, `fire_ob-b1-013-lamp02`,
  `fire_ob-12-03gate06`, `fire_general_obj_campfire`. **A lit prop is two placements at the same
  coordinate** — the Building mesh plus its Effect flame. Place only the mesh and the lamp is dark.
  (`fire_blue1` and `fire_camp1` are the two generic exceptions.)
- **`metinstone_loop_<N>_<colour>.mse`** — 27 variants. `N` ∈ 2..4 is the aura size tier; colour ∈
  {none, aqua, blue, orange, pink, purple, whitepurple, whitered, yellow}. These are the Metin-stone
  auras.
- **`volcano_<size>smoke[<variant>].mse`** — 16: `smallsmoke` < `bigsmoke` < `biglongsmoke` <
  `greatsmoke`, plus `blacksmoke`/`whitesmoke` colour forms and `_snake01..04` for the snake-temple
  reskin.
- **`warpgate0N`** — `01`, `01_yview`, `02`, `03`, `03_1`. `_yview` is the top-down variant.
- **`resource[_N|_big|_group].mse`** — the gathering sparkle used by `resources_picking/`.

### Buildings (`.gr2`, 1 734 props)

- **`b1-NNN-<role>`** — Empire-B city buildings: a hard 3-digit serial plus an English role word.
  `b1-006-castle`, `b1-007-itemshop`, `b1-009-hotel`, `b1-010-bank`, `b1-011-workhouse`,
  `b1-031-tower`. The most readable naming Ymir ever used.
- **`ob-<biome>-<NN>[-<role>]`** — `ob` = object. **The first number is the `b/` sub-biome index**
  and matches the numbered Korean folder: `ob-7-*` ↔ `b/03.웅귀촌`, `ob-10-*`/`ob-11-*` ↔
  `b/02.감염&해골탑`, `ob-12-*` ↔ `b/05.무덤가`, `ob-4-*`/`ob-5-*` ↔ `b/07.밀교사원`. Where the two
  disagree, the number in the *name* is the original and the folder is a later re-filing.
- **`general_obj_<thing>`** — the shared clutter vocabulary, English and descriptive: `bottle`,
  `brazier`, `brimstone`, `campfire`, `carriage`, `drum`, `fence01..03`, `flag`,
  `jar_{blue,red,yellow}0N`, `lamp`, `pieceofstone0N`, `pillar`, `stump`, `txtstone`, `woodchair`.
  Read these directly.
- **Zone prefixes mirror the folder** — `ep_` eastplain, `wdc_` whitedragoncave, `gls_` geuglagsa,
  `dmw_` dawnmistwood, `smh_` Demon Tower, `nsm_` n-snow-map, `5st_`/`4st_` temple stage N, `12t_`
  zodiac temple, `sn_` snow, `mt_th_` Mt Thunder. **A prefixed clone is a re-skin of the `b/`
  original** — `ep_B_general_obj_36` is eastplain's copy of `B_general_obj_36`.
- **Shape suffixes** — `_01..NN` variant; `_1.._4` appended to an already-numbered name is a later
  clone of that exact variant; `-corner` / `-lin` / `-lin2` / `-door` are wall-tile roles (corner,
  straight run, straight run alt, doorway); `_up` / `_low` vertical half; `_s0N` small.

### DungeonBlocks (`.gr2`, 195 props)

Room-sized tiles snapped together into an interior. **The name is the room role, and it is
consistently English**: `startroom`, `bossroom`, `eggroom`, `passage0N`, `passis` / `passic`
(passage-straight / passage-corner), `three-way`, `conerroom`, `stonecave`, `dungeon_bN`, `stair`.
Almost all model paths sit under `d:/ymir work/zone/dungeon/<dungeon-name>/`.

### The 261 props you cannot read

**`B_general_obj_NN`, `obj-NNNN`, `ob-N-NN`, `miniboss_NN`, `gls_A_NN`, `horn0N`, `double_0N`** are
pure catalogue serials with no descriptive token at all — 261 properties, 15 % of all Buildings.
**You cannot tell what these are from the name; you must open the `.gr2`.** They are the single
biggest gap in name-based reasoning about the vocabulary, and they are concentrated exactly where it
hurts most: 152 in `b/` (the shared vocabulary), 33 in `n/`, 22 in `miniboss/`, 21 in `eastplain/`.
The later `bbox`/`textures`/`caption` pass over the model headers is what will close this.

### Ymir's typos are the real names

Greps must match the misspelling, not the correct spelling.

| Shipped | Means | Count |
|---|---|---|
| `gaint` | giant | 38 (`eastplain/gaint_desert/`, `devils_dragon_island/camp/gaint_gate_*`) |
| `bigtoewr` | bigtower | 25 — **and the correct `general_obj_bigtower*` also ships**; both spellings coexist |
| `skelleton` | skeleton | 4 (`otherworld/otherworld_skelleton_*`) |
| `resorce` | resource | 4 (`thief_dungeon/haven_dungeon/eff/`) |
| `hause` | house | 2 (`ob-004-hause2`, `snow-004-hause2`) |
| `conerroom` | cornerroom | 2 (`mt_thunder_dungeon/`) |
| `ston_` | stone_ | 4 (`secretdungeon/secret_boundary_ston_00..03`) |
| `scoccer` | soccer | 1 (`n/oxevent/scoccer_line`) |
| `charcoa` | charcoal | the Building is `general_obj_charcoa`, its paired effect is `fire_general_obj_charcoal.mse` — **the pair disagrees** |
| `nersluck` / `nusluck` | — | the folder is `n/nersluck/`, the props are `nusluck_*`, the models live in `zone/nusluck/`. Three spellings in one 13-prop set. |

---

## 5. Families

`objects.json` tags every entry with a `family`. Counts over all 2 112 CRCs:

| Family | n | Family | n |
|---|---|---|---|
| `opaque_serial` | 261 | `pillar` | 47 |
| `building` | 230 | `light_fire` | 40 |
| `rock` | 209 | `terrain_piece` | 36 |
| `dungeon_block` | 195 | `warp_gate` | 29 |
| `wall_fence` | 149 | `cliff` | 28 |
| `clutter` | 131 | `water_ice` | 18 |
| `vegetation` | 126 | `ship_part` | 13 |
| `bridge` | 104 | `collision_proxy` | 10 |
| `tower` | 99 | `unclassified` | 11 |
| `effect` | 97 | `ambience` | 2 |
| `tree_speedtree` | 85 | | |
| `gate_door` | 71 | | |
| `statue_shrine` | 70 | | |
| `bone_debris` | 52 | | |

Families are assigned by an ordered regex over `PropertyName` + model path, with
`opaque_serial` matched on the name alone so a zone token in the path cannot out-rank it. The rule
list is in the `families` section of `objects.json`; 11 props (0.5 %) resist classification and are
tagged honestly rather than forced.

Two families worth knowing about:

- **`collision_proxy` (10)** — invisible geometry placed only to block movement:
  `skipia_collision` (324 placements), `miniboss_01_coll`, `miniboss_01_b_coll`,
  `secret_boundary_ston_00..03`, `dummy01/02`, and defensewave's `main_dot`/`back_dot`/`front_dot`
  markers. They render as nothing and exist for the `.mdatr`.
- **`ship_part` (13)** — all in `defensewave/`: `vent01..07`, `rail_crack01..06`, `steerhandle`,
  `left`/`right`/`top`. Deck furniture for the ship-siege event.

---

## 6. `isattributedata` — a generation marker, not a flag

Present on **152 of 1 734 Buildings**, always the single value `"0"`, **exclusively under `b/`**
(152/152; the other 40 top-level folders have zero). It is **inert at runtime** and means nothing
semantic. Every plausible hypothesis fails against the data:

| Hypothesis | Result |
|---|---|
| "the prop has collision data" | `.mdatr` exists for 144/152 with it and 203/207 without it — statistically identical. **8 files that have it have no `.mdatr` at all.** |
| "it tracks `shadowflag`" | all 152 are `shadowflag=1` — but so are 1 554 of the 1 582 without it |
| "it marks props actually used" | 141/152 with it are placed, 174/207 without it are placed |
| "some engine code reads it" | grep for `isattributedata` over WorldEditorRemix `Srcs/**/*.cpp,*.h,*.py` returns **zero hits**. `EterLib/AttributeData.cpp` (`CAttributeData`) is the `.mdatr` loader and never consults a property key. |

What it *does* track is **authoring generation**, and the cut is exact. In `b/10.공용`:

```
B_general_obj_01 .. _17      isattributedata present   (17/17)
B_general_obj_18 .. _42      absent                    (0/25)
B_general_obj_01_1.._01_4,
  _05_1, _10_1, _21_1,
  _25_1, _25-2               absent                    (0/7)
```

Same shape elsewhere: `ob-11-01-skeletontower` has it, `ob-11-01-skeletontower01..06` do not.
The key was emitted by the original Empire-B authoring pass and by no tool run since.

**Generator rule:** never invent it, never add it to a new property. Preserve it verbatim when
round-tripping an existing `b/` property, or the file stops being byte-identical.

The 8 files that carry it with no `.mdatr`: `ob-11-01-skeletontower`, `ob-11-03-bonetunnel04`,
`ob-12-03gate`, `general_obj_bottle`, `general_obj_pieceofstone01..04`.

---

## 7. `property/reserve` — retired CRCs, never reissued

206 bytes, **16 CRCs**, one per record.

```
3752064404  682846659  3664238165  1820773723  1078519397  4276088242
1616547981  2009789342  1926853745  2985193027  1467311299  3210823683
 926224884  3363244466  4212807540  3804322919
```

**Role.** A tombstone list. WorldEditor appends a property's CRC here when the property is deleted,
so the CRC is never handed to a new asset. Legacy maps may still hold `areadata.txt` records
pointing at a retired CRC; `CPropertyManager::Get` finds nothing and `CArea::__Load_LoadObject`
silently drops the record — **a retired CRC degrades to an invisible object, never a crash**.
Reissuing one would resurrect the wrong model in every legacy map that still references it.

**Verified clean.** All 16 are disjoint from the 2 112 live CRCs (intersection empty), and none of
the 16 appears in any of the 48 774 `areadata.txt` records across `<CORPUS>`. Nothing still points at
a tombstone.

**Write trap.** Every record ends `\r\r\n`, not `\r\n` — a text-mode append onto a string that
already ended in `\r`. The engine tokenizer splits that into two breaks, so a blank line follows
every CRC. Blank lines are skipped so it is harmless, but reproduce it byte-for-byte on rewrite.
`PropertyReserve` in the codec defaults `eol` to `"\r\r\n"` for exactly this reason.

---

## 8. Missing models — the generator landmines

**156 of 2 110 model paths (7.4 %) do not exist under `D:/ymir work/`.** A property whose model is
missing still loads; it just renders nothing. Placing one produces an invisible object.

| Cause | n |
|---|---|
| individually-absent files | 46 |
| `zone/12temple/` — directory absent | 36 |
| `zone/ydragon/` — files absent | 26 |
| `d:/ymir work/guild/` — root absent from this extract (`building/`, `inside01/`) | 23 |
| `zone/dungeon/snow_dragon/` — directory absent | 12 |
| editor scratch (`zone/metin_test/`, `zone/test001.gr2`, `zone/sample0000/`) | 5 |
| **author's desktop path** | 3 |
| Korean zone dir `d:/ymir work/zone/공용/` | 2 |
| bare drive root `d:/maiinbase.gr2` | 1 |
| **typo drive letter `dd:/`** | 1 |
| old root `d:/work/metin2/main/data/...` | 1 |

The pathological ones are worth naming individually — these are paths that never worked on anyone's
machine but the author's:

| CRC | Property file | `buildingfile` |
|---|---|---|
| `1120512985` | `n/oxevent/tree.prb` | `c:/documents and settings/sun.sun/바탕 화면/tree.gr2` |
| `1171457321` | `dawnmistwood_dungeon/turtle_00.prb` | `c:/documents and settings/ibakoon/바탕 화면/turtle_00.gr2` |
| `3666876900` | `dawnmistwood_dungeon/test_m.prb` | `c:/documents and settings/ibakoon/바탕 화면/test_m.gr2` |
| `3030942020` | `devils_dragon_island/thing/thing_barricade_00.prb` | `dd:/ymir work/...` — doubled drive letter |
| `2574997096` | `guild_construction/maiinbase.gr2.prb` | `d:/maiinbase.gr2` |
| `4255883519` | `12temple/cloud.prb` | `d:/work/metin2/main/data/zone/12temple/cloud.gr2` |
| `3520529729` / `3481091450` | `b/10.공용/hay_01.gr2.prb`, `hay_02.gr2.prb` | `d:/ymir work/zone/공용/hay_0N.gr2` |

(`바탕 화면` = "desktop".)

### Collision files

Buildings and DungeonBlocks derive a `.mdatr` from the model path by swapping the extension.
Of 1 929 expected: **1 484 present, 445 missing**. Of those 445, **298 have a model that *does*
exist** — a real mesh with no collision data, so the player walks straight through it. Worst
offenders: `devils_dragon_island` 111, `dawnmistwood_dungeon` 63, `flame_dungeon` 22,
`otherworld` 16, `temple` 13, `mists_of_island` 12, `secretdungeon` 11.

Note that a missing `.mdatr` is not automatically a bug — 20 of the 28 `shadowflag=0` props are
deliberately non-colliding decoration. But for a wall, a building or a cliff it is a hole in the map.

### Art shipped inside `property/`

`property/n/obj/snow.m/` contains **491 non-property files** — `.gr2`, `.mdatr` and `.dds` for the
snow set, sitting in the property tree instead of under `D:/ymir work/`. No other folder does this.
Any tool that walks `property/` must filter on `.pr?` or it will try to parse Granny meshes as
YPRT text. (`scan_property_dir` in the codec already does.)

---

## 9. Checklist for a generator

1. Address props by **CRC only**. Never by name (130 collisions), never by model path (13
   collisions), never by filename.
2. Copy the CRC line **verbatim** — it is stored as a string and written back unchanged. Never
   recompute one, never reuse a `reserve` CRC.
3. Emit `shadowflag` on every Building (`1` unless the mesh is thin or alpha-cut).
4. Emit `treesize 1000.000000` and `treevariance 0.000000` on every Tree.
5. Never emit `isattributedata`; preserve it when round-tripping a `b/` file.
6. Before placing a CRC, check `model_exists` in `objects.json` — 156 props render as nothing.
7. For a lamp/brazier/campfire, place **both** the Building and its `fire_<name>` Effect at the same
   coordinate.
8. Keys are lowercased and sorted in `std::map` (byte-ascending) order; the body is
   `key\t\t"value"` with `\r\n` terminators after the `YPRT\r\n` magic.

---

*`bbox`, `textures` and `caption` are `null` for every entry in `objects.json`; a later pass fills
them from the `.gr2`/`.spt`/`.mse` headers. That pass is also what will finally identify the 261
`opaque_serial` props.*

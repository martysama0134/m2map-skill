# Metin2 Map Corpus — Overview and Archetype Partition

Survey of the 142 official Ymir/GF maps in `<CORPUS>`, cross-referenced against the shipped client pack
(`M2-v24.0.0.0/pack`). Machine-readable companion: [`catalog/map-taxonomy.json`](catalog/map-taxonomy.json).

**Sources measured**

| What | Where | Count |
|---|---|---|
| Map folders | `<CORPUS>` | 142 |
| `setting.txt` | `<map>/setting.txt` | 139 (3 missing — see below) |
| `mapproperty.txt` | `<map>/mapproperty.txt` | 142 |
| Sector directories | `<map>/XXXYYY/` | 1,343 |
| `areadata.txt` object records | `<map>/XXXYYY/areadata.txt` | 48,851 |
| TextureSets | `pack/textureset/textureset` | 99 `.txt` shipped (+1 `snow` subfolder), 70 referenced |
| Environments | `pack/yw_etc/ymir work/environment` | 104 `.msenv` shipped (121 entries incl. skybox/cloud/flare art), 72 referenced |
| Property files (CRC → model) | `pack/property/property` | 2,113 files, 2,112 CRCs indexed |

All 48,851 areadata CRCs resolve against the property index — **0 unresolved**. That is the strongest single
confirmation that this corpus and this client pack belong together.

---

## 1. What the corpus actually is

- **1,343 sectors ≈ 88.0 km² of terrain.** Sector edge is 25,600 cm (256 m), so 1,343 × 256² m² = 88.0 km².
- **Every map is `MapType "Outdoor"`.** Not one `Indoor` map exists — the indoor pipeline is fully vestigial,
  even for maps that are dungeon interiors in every other respect.
- **`CellScale 200` and `HeightScale 0.500000` in all 139 maps that have a `setting.txt`.** No exceptions.
  Treat both as constants when generating.
- **Size distribution:** 2×2 (35 maps), 3×3 (29), 6×6 (18), 1×1 (13), 2×4 (9), 4×5 (7), 4×4 (7). Median 3×3;
  the biggest is `metin2_map_devilscatacomb` at 7×7. Nothing approaches the 256×256 format limit.
- **`ViewRadius` is not the constant the spec implies.** 128 in 116 maps, but 256 in 16, **4096** in 4
  (`metin2_map_e1` and its three proxies), 512 in 2 and 384 in 1.

### There are no beta-era maps here

The starting brief and the `mapformat/README.md` both expect "old beta" maps with 5 files per sector and no
areadata/minimap/shadowmap. **The corpus contains none.** Every sector directory that exists carries the full
modern 10-file set (`areaambiencedata.txt`, `areadata.txt`, `areaproperty.txt`, `attr.atr`, `height.raw`,
`minimap.dds`, `shadowmap.dds`, `shadowmap.raw`, `tile.raw`, `water.wtr`). The README names `metin2_map_c1`
as the beta example; `metin2_map_c1/000000/` in fact holds all ten files. Every map is tagged `era: "modern"`.

Three sector-level exceptions, all deliberate:

- `metin2_map_boss_awaken_skipia` and `metin2_map_boss_crack_skipia` ship exactly one sector containing only
  `attr.atr` (a collision patch over the parent's terrain).
- `metin2_map_smhdungeon_02` sectors have no `minimap.dds`.

Fifteen maps add per-sector *extras* the spec does not list:

- `contents.obv` — the 4 `elemental_*` maps.
- `height.tga` — `metin2_map_b1`, `metin2_map_b3`, `metin2_map_smhgate_b1` (an editor by-product; `height.raw` is still present and authoritative).
- edge-blend minimaps `minimap_{top,bottom,left,right,lefttop,righttop,leftbottom,rightbottom}.dds` — the 3
  `eastplain_*` maps plus `empirecastle`, `icecrystalcave`, `snake_temple_01`, `snakevalley`, `whitdragonvalley`.

### A third of the corpus has no terrain of its own

**31 of 142 maps carry `ParentMapName`.** Of those, **26 have zero sector directories** — they are pure
client-side proxies that copy the parent's `setting.txt` verbatim and reuse the parent's terrain, existing only
so the server can register a separate map index (dungeon instances, seasonal arenas, guild-land slots). The
remaining 5 (`smhgate_a1/b1/c1`, `smhgate_devils`, `boss_*_skipia`) ship a partial sector subset.

`metin2_guild_village_01/02/03` go further: they have **no `setting.txt` at all**, only a `mapproperty.txt`
with `ParentMapName metin2_guild_village`.

Any tool that walks this corpus must handle `sector_count == 0` and `setting.txt` absent. The taxonomy records
this as `terrain_source: "own" | "proxy:<parent>" | "partial:<parent>"`.

---

## 2. Why filenames are not the grouping

Three measurements kill the naive name-based partition:

1. **`metin2_map_a1`, `metin2_map_b1` and `metin2_map_c1` are terrain-identical.** Their texturesets
   `metin2_a1.txt`, `metin2_b1.txt` and `metin2_c1.txt` are **byte-identical files** (md5-verified), all 17
   textures drawn from `terrainmaps/B/**` — the `A`/`B`/`C` in the name refers to the *empire*, not the art set.
   Worse, `a1.msenv` and `c1.msenv` are byte-identical too. The only thing that separates the three capitals is
   the **building family** in `areadata.txt`: `zone/a/building` (54 objects in a1), `zone/b/building` (282 in b1),
   `zone/c/building` (71 in c1).
2. **`map_a2` and `map_n_threeway` are the same map.** Byte-identical content across every sector file; only
   `BasePosition` differs. Likewise `sungzi_desert_hill_01/02/03`, `sungzi_flame_hill_01/02/03` and
   `sungzi_snow_pass01/02/03` are each three copies of one map.
3. **"Guild" is a server function, not a look.** `metin2_guild_war1`/`_war3` sit on the bespoke `guild_village`
   terrain family, but `guild_war2`/`_war4` and `guild_01/02/03` sit on plain empire field palettes with zero
   guild-specific art. A `guild` archetype does not survive the evidence and was dissolved.

The reverse also happens: `metin2_map_snake_temple_01` (bespoke `zone/geuglagsa` temple, 484 objects, own
14-texture palette) and `metin2_map_snake_temple_02` (black-fog `dark.msenv`, 87 % effects, `metin2_map_smhtower_d.txt`)
share a name prefix and end up in **different** archetypes.

---

## 3. Method

Each map was scored on three independent axes, and a pair was linked when at least two agreed:

| Axis | Measurement |
|---|---|
| **Terrain palette** | Jaccard similarity ≥ 0.5 over the set of `.dds` paths parsed out of the referenced `textureset/*.txt` |
| **Environment** | md5-identical `.msenv` file (fog colour, near/far, skybox gradient, cloud texture, filter) |
| **Object palette** | cosine similarity ≥ 0.5 over the per-map histogram of `zone/**` art families, obtained by resolving every `areadata.txt` CRC through the 2,112-entry property index |

Proxy maps (no objects) were linked on terrain + environment only. The resulting connected components were then
merged where two components could not be separated on any axis, and split where a component clearly held two
identities (see `dungeon_block` vs `dungeon_themed` below). Full per-cluster evidence strings live in the JSON.

The object axis is what makes this trustworthy: terrain and fog are heavily recycled across the corpus
(`dark.msenv` is used by 11 maps, `milgyo.msenv` by 9, `A1.msenv`/`a1.msenv` by 9, `metin2_map_deviltower1.txt`
by 10), whereas the `zone/<theme>` art family is almost always unique to one visual identity.

---

## 4. The partition — 17 archetypes

| Key | Maps | Typical size | Reference map | Defining evidence |
|---|---|---|---|---|
| `field_empire` | 18 | 2×2 (flagships 4×5) | `metin2_map_a1` | `terrainmaps/B/**` only; `b1_`/`b3_` deciduous trees; empire told apart by `zone/{a,b,c}/building` |
| `field_valley` | 4 | 6×6 | `map_a2` | `terrainmaps/A/**` only (Jaccard 0.00 vs B); all four on `A2.msenv` |
| `desert` | 10 | 2×4 (flagship 6×6) | `metin2_map_n_desert_01` | `n/desert/**`; `n2_` arid SpeedTrees; 9 of 10 on `milgyo.msenv` |
| `snow_field` | 6 | 2×4 (flagship 6×6) | `map_n_snowm_01` | `n/snow.m`; `n1_` winter conifers; perfect 6:1:1 map/textureset/env group |
| `flame_field` | 6 | 2×4 (flagship 6×6) | `metin2_map_n_flame_01` | `n/flame area`; only vegetation is `b2_ivyspy_rt_winter*` |
| `darkforest_coast` | 8 | 6×6 | `metin2_map_capedragonhead` | chained bayblacksand→capedragonhead→mtthunder palettes; `zone/devils_dragon_island/**` dominant in all (51–531 records vs ≤36 anywhere else) |
| `ice_valley` | 3 | 6×3 | `metin2_map_snakevalley` | `snakevalley` + `n/snow.m` + capedragonhead mix; `zone/snakevalley` art |
| `eastplain` | 4 | 4×5 | `metin2_map_eastplain_01` | `zone/eastplain` art, used by nobody else; shared `empirewar/tille` terrain |
| `empire_war` | 6 | 2×2 | `metin2_map_empirewar02` | one 2×2 siege layout in 3 exclusive skins (`empirewar/{snow,summer,desert}`) + 3 proxies |
| `guild_village` | 7 | 1×1 | `metin2_guild_village` | the `guild_village` terrain folder; `guild_war1.msenv` ≡ `guild_war3.msenv` |
| `arena_pvp` | 6 | 2×2 | `metin2_map_oxevent` | `zone/duel` props + `zone/b/building` plazas; highest object density in the corpus (110–253/sector) |
| `dungeon_block` | 23 | 3×3 | `metin2_map_skipia_dungeon_02` | ≤5-texture palette **and** max fog channel ≤ 0.20; 77–100 % DungeonBlock+Effect; 18 of the corpus's 19 `TerrainVisible 0` maps |
| `dungeon_themed` | 21 | 2×2 | `metin2_map_dawnmist_dungeon_01` | same construction, biome-skinned: themed multi-texture palette + coloured `.msenv` |
| `elemental` | 4 | 5×5 | `metin2_map_elemental_01` | the `elemental_01` terrain folder, exclusive; 76–94 % of objects are Trees |
| `trent_forest` | 2 | 3×3 | `metin2_map_trent02` | `trent/**` terrain used by nothing else; matching night fog |
| `event_instance` | 10 | 3×3 | `metin2_12zi_stage` | each owns a single-use `zone/<name>` art family + its own textureset + its own `.msenv` |
| `dev_stub` | 4 | 1×1 | `metin2_map_t1` | `BasePosition` not sectree-aligned; corrupt line in `t1/setting.txt`; texturesets are verbatim copies |

### Clusters that were merged

- **town/village → `field_empire`.** There is no standalone town map in this corpus. The capitals *are* the
  field maps: a1, b1 and c1 each embed their town inside a 4×5 overworld tile. Town architecture
  (`zone/{a,b,c}/building`) appears in 14 different maps across 5 archetypes and never forms a cluster of its own.
- **guild → dissolved.** Split between `guild_village` (real shared art), `field_empire`/`field_valley`
  (`guild_01/02/03`, `guild_war2`, `guild_war4` — plain field palettes), `arena_pvp` (`guild_battle*`) and
  `event_instance` (`guild_pve`).
- **boss-arena → `dungeon_themed` + `event_instance`.** The eight `boss_awaken_*` / `boss_crack_*` maps are
  sector-less proxies of themed dungeons and inherit their parent's identity exactly; the bespoke boss stages
  (`miniboss_01/02`) sit in `event_instance`.
- **deep-forest → `trent_forest` + `darkforest_coast`.** `trent`/`trent02` are the only maps on the `trent/**`
  palette; the rest of the "dark forest" content is the `devils_dragon_island` continent.

### The one cluster that was split

`dungeon_interior` held two clearly separable identities and was split on a measurable rule:

- **`dungeon_block`** — textureset texture count ≤ 5 **and** max fog channel ≤ 0.20. These are flat black boxes:
  `metin2_map_anglar_dungeon_01.txt`, `metin2_map_deviltower1.txt` and `metin2_n_saguidungeon.txt` are three
  byte-identical *single-texture* palettes, and `dark.msenv` / `skipia_dungeon.msenv` / `monkeydungeon_02.msenv`
  / `monkeydungeon_03.msenv` all declare `Fog Color 0 0 0`. All geometry is DungeonBlock props; zero Tree records.
- **`dungeon_themed`** — everything that fails that rule: `dawnmist_dungeon` (9 textures, fog 0.16/0.16/0.23),
  `whitedragoncave` (4, 0.54/0.58/0.82), `otherworld_01` (8, 0.69/0.16/0.07), `n_snow_dungeon_01`
  (4, 0.10/0.78/0.94), `devilscatacomb` (12, 0.09/0.10/0.16 — dark but far too many textures to be a black box).

`metin2_map_otherworld_02` is the one place where object evidence deliberately overrides terrain evidence: it
sits on the `field_empire` B-palette but 84 % of its objects are `zone/secretdungeon` (209) and `zone/otherworld`
(114), so it goes with `dungeon_themed`.

---

## 5. Format findings not covered by `reference/mapformat`

These were measured here and should be folded into the spec.

1. **`areadata.txt` has an extended CRC token.** `metin2_map_treasure_hunt` writes field 3 as
   `CRC#sx#sy#sz` — e.g. `142625613#1.000000#1.000000#1.000000` — a per-object scale triple appended to the CRC.
   All 288 of its records use it, and it is the only map in the corpus that does. The vanilla client survives it
   because field 3 is read with `atoi`, which stops at the `#`; a strict parser (`int(token)`) throws.
   **Split on `#` and take element 0.**
2. **`setting.txt` supports multiple environments.** Undocumented keys found in the wild:
   - `Environment1` … `Environment8` — `metin2_12zi_stage` (8 extra), `metin2_map_elemental_01`, `metin2_map_elemental_02` (1 each).
   - `EnvironmentRange<N> <x0> <y0> <x1> <y1> <name>.msenv` — `elemental_01` and `elemental_02`. On the 5×5
     `elemental_01` the two ranges are `0 0 1280 640` and `0 640 1280 1280`, i.e. a north/south split; 5 sectors
     × 256 = 1280, so the **units are half-cells (1 m)**, matching `tile.raw`/`attr.atr` resolution. *(Inferred
     from two files only — not confirmed against loader source.)*
3. **Undocumented map-root files.**
   - `sungma_attr.txt` — 14 maps (anglar_dungeon_01, eastplain_01/02/03, empirecastle, icecrystalcave,
     maze_dungeon1/2/3, snake_temple_01, snakevalley, whitdragonvalley, whitedragoncave_01/02). Body is
     tab-separated `sungma_str 25 / sungma_hp 15 / sungma_move 25 / sungma_immune 30` — per-map Sungma stat caps.
   - `monsterareainfo.txt` — 2 maps (`metin2_map_a1`, `metin2_map_b3`); regen-like grid `type cx cy sx sy z dir time percent count vnum`.
   - `atlas.sub` — 1 map (`metin2_map_milgyo`); a `title subImage` block naming `metin2_map_milgyo_atlas.dds` with an L/T/R/B rect.
   - Loose `.msenv` files sitting in map roots (`metin2_map_devilscatacomb/map_dd_teste.msenv`,
     `metin2_map_skipia_dungeon_*/skipia_dungeon.msenv`, …). Note the resolution order still finds the *global*
     copy for every map in this corpus — no map actually resolves its environment from its own folder.
4. **`BasePosition` alignment is violated in the shipped data.** The spec requires a multiple of 25,600.
   Four maps break it: `gm_guild_build` (83200, 0), `metin2_map_t2` (6400, 0), `metin2_map_t3` (32000, 0),
   `metin2_map_t4` (57600, 0). All four are multiples of 6,400 (the server sector) but not of the client sectree.
5. **Sector directories can exceed `MapSize`.** `metin2_map_devilscatacomb` declares `MapSize 7 7` but ships 54
   directories including a whole `x=7` column; `metin2_map_trent02` declares `3 3` but ships a full 4×4 = 16.
   The extra folders are dead data — a loader that trusts `MapSize` never reads them, but a folder-walking tool
   will.
6. **A shipped `setting.txt` is corrupt.** `metin2_map_t1/setting.txt` ends with a stray line `ungeon2.msenv`
   (a truncated `Environment` value). The shared tokenizer swallows it as a valueless key, so the client loads
   the map fine — a parser that asserts "every key has ≥1 token" will not.
7. **Asset reuse is heavy; dedupe before caching.** Byte-identical shipped texturesets:
   `metin2_a1/b1/c1/b_fielddungeon/map_n__trent/map_otherworld_02/map_t1`;
   `metin2_map_anglar_dungeon_01/deviltower1/n_saguidungeon/resources_zon`;
   `metin2_n_desert1/n_desert_01/n_desert_1`; `metin2_a3/map_wedding_01`; `metin2_b3/c3`;
   `metin2_guild_war1/war3`; `metin2_map_mists_of_island/mists_of_island`.
   Byte-identical `.msenv`: `a1/c1/war4`; `a2/b2/c2`; `a3/b3/c3`; `eastplain_01/03`; `guild_pve/guild_pvp`;
   `guild_war1/war3`; `elemental_03_01/guild_battle_02`; `mists_of_island` ×2; `t1/t2`.

---

## 6. Using this as a generator

For a new map of archetype *K*, start from `archetypes[K].reference_map` and copy its `TextureSet` +
`Environment` verbatim — those two lines carry most of the visual identity, and every archetype here has at
least one palette/environment pair that several shipped maps already share. Then take the object palette from
`archetypes[K].dominant_object_families`: those are the `zone/**` folders whose property CRCs the reference map
actually places. Sizing: use `typical_size` for an instanced stage and `reference_size` for a flagship overworld
tile — the two differ in most archetypes because each biome ships one large hub plus several small side maps.

Per-map facts for all 142 (size, base position, textureset, environment, sector list, terrain source, object
family histogram, root files) are in `catalog/map-taxonomy.json` under `maps`.

# m2map Archetypes -- the 17 biomes, and how to pick one

Each file in this directory is a complete recipe for one map archetype: terrain
statistics, a textureset table you can paste into `MapSpec.textures`, an environment
preset, a three-tier object palette you can paste into `MapSpec.objects`, the placement
rules (including the negative ones), and the attr policy.

The partition is measured, not named. Every archetype was scored on three independent
axes -- terrain palette (Jaccard over `.dds` paths), environment (md5-identical `.msenv`)
and object palette (cosine over `zone/**` family histograms) -- and a pair was linked only
when at least two agreed. See `../corpus-overview.md` sec 3 for the method and
`../catalog/map-taxonomy.json` for the machine-readable membership.

**Pick exactly one archetype.** They are mutually exclusive: no shipped map belongs to
two, and mixing two palettes is the single most visible way to produce something that
reads as machine-made.

---

## Step 1 -- free text to one archetype key

Read the user's request and take the **first** row that matches. Rows are ordered so that
the more specific claim wins.

| The request says... | Archetype | File |
|---|---|---|
| black box, corridor dungeon, cave with no sky, "just rooms", instanced dungeon, `TerrainVisible 0` | `dungeon_block` | [`12-dungeon_block.md`](12-dungeon_block.md) |
| themed dungeon, ruin interior, lava cave, ice cave, catacomb, otherworld, secret garden, boss lair with a look | `dungeon_themed` | [`13-dungeon_themed.md`](13-dungeon_themed.md) |
| PvP arena, duel ring, OX event, shop plaza, flat walled stage, "everyone spawns here" | `arena_pvp` | [`11-arena_pvp.md`](11-arena_pvp.md) |
| siege, castle war, empire war, three seasonal skins of one battleground | `empire_war` | [`09-empire_war.md`](09-empire_war.md) |
| guild village, guild land, small terraced settlement, guild-war ground | `guild_village` | [`10-guild_village.md`](10-guild_village.md) |
| event stage, instance, boss stage, zodiac temple, treasure hunt, defence wave, battle royale | `event_instance` | [`16-event_instance.md`](16-event_instance.md) |
| desert, sand, dunes, oasis, arid frontier, golden land | `desert` | [`03-desert.md`](03-desert.md) |
| snow field, winter, whiteout, snow pass, ice plateau (open air) | `snow_field` | [`04-snow_field.md`](04-snow_field.md) |
| lava, volcano, flame land, basalt, magma, "burning wasteland" | `flame_field` | [`05-flame_field.md`](05-flame_field.md) |
| ice ravine, snake valley, white-dragon valley, standing stones on cliffs | `ice_valley` | [`07-ice_valley.md`](07-ice_valley.md) |
| dark coast, black sand, whale bones, orc camp, dawnmist, mt thunder, devils dragon island | `darkforest_coast` | [`06-darkforest_coast.md`](06-darkforest_coast.md) |
| night forest, sparse silhouettes, trent, "forest at dusk with nothing in it" | `trent_forest` | [`15-trent_forest.md`](15-trent_forest.md) |
| giants' plain, broken pillars, ruined wilderness, eastplain, empire castle | `eastplain` | [`08-eastplain.md`](08-eastplain.md) |
| elemental zone, sungma, dense mixed forest on a plateau, "tree map" | `elemental` | [`14-elemental.md`](14-elemental.md) |
| green valley, gorge, three-way, steep river valley with a road through it | `field_valley` | [`02-field_valley.md`](02-field_valley.md) |
| empire field, capital, town, starting zone, generic green overworld, "a normal Metin2 map" | `field_empire` | [`01-field_empire.md`](01-field_empire.md) |
| nothing above, or an explicit request for a test/scratch map | **stop and ask** -- do *not* use `dev_stub` | [`17-dev_stub.md`](17-dev_stub.md) |

**Tie-breakers**

- **Interior vs outdoor first.** If the map has no sky, it is `dungeon_block` or
  `dungeon_themed`, whatever biome words the request uses. `MapSpec.style` must be
  `"box"` and 44 of the 142 corpus maps cannot be produced by the sculpted stages at all.
- **Then function vs look.** "Guild", "boss", "event" and "war" are *server functions*.
  A guild map on an empire palette is `field_empire`, not `guild_village`; the corpus
  dissolved a naive `guild` cluster for exactly this reason (`../corpus-overview.md` sec 4).
- **Then art pack, not name.** `metin2_map_a1`, `b1` and `c1` share a byte-identical
  textureset and environment; only the building family differs. If the user wants
  "Empire B", that is `field_empire` with `zone/b/building`, not a separate archetype.
- **`dev_stub` is not a design choice.** It is four broken shipped test maps. If a
  request lands there, pick the closest real archetype and say so.

**Sizing.** Every archetype file lists a *typical size* (modal over its members) and a
*reference size* (its flagship). Use typical for an instanced side map, reference for a
hub or overworld tile (`../corpus-overview.md` sec 6).

---

## Step 2 -- which sections to read

Read the whole file if you are generating from scratch. If you are answering a narrower
question, these are the sections that matter:

| You are deciding... | Read |
|---|---|
| whether the archetype is right at all | **Identity**, **Tells** |
| `MapSpec.size`, `base_position`, which map to clone | **Reference maps** |
| `height_range_cm`, `slope_p50`, `slope_p95`, `flat_fraction`, `roughness`, `style` | **Terrain** |
| `MapSpec.textures`, `textureset_name`, `RoadSpec.tile_index` | **Textureset recipe** |
| `MapSpec.environment` and what to write into the `.msenv` | **Environment** |
| `MapSpec.objects` -- crc, tier, density, spacing, on_tiles, max_slope, road_clearance, water_distance_m, height_bias | **Object palette** |
| where things go relative to roads, water, slope and each other; what must never appear | **Placement rules** |
| `attr_style`, `block_slope_deg`, `border_band_m`, `safezone_regions` | **Attr policy** |
| whether your output will read as authored or as generated | **Tells** |

Then read [`../taste.md`](../taste.md) -- the six rules that hold across every archetype,
five of which contradict the obvious assumption. In particular: heading is **roll**, not
yaw; everything snaps to 15 deg; trees are mostly unrotated; **there is no road texture in
Ymir's art**; ground is a per-tile stipple at 1 m, not region fill; and block attr is
slope-driven on only half the corpus.

---

## The 17, in taxonomy order

| # | Key | Maps | Typical | Reference map | One line |
|---|---|---|---|---|---|
| 01 | `field_empire` | 18 | 2x2 | `metin2_map_a1` | the default green overworld; the three capitals are this map three times |
| 02 | `field_valley` | 4 | 6x6 | `map_a2` | steep A-pack gorge; everything sits on the road |
| 03 | `desert` | 10 | 2x4 | `metin2_map_n_desert_01` | sand carpet + double dither, haze at the camera, scrub in patches |
| 04 | `snow_field` | 6 | 2x4 | `map_n_snowm_01` | whiteout; conifers sunk exactly 80 cm; no water at all |
| 05 | `flame_field` | 6 | 2x4 | `metin2_map_n_flame_01` | teal light on an orange sky; 1.24 obj/ha; emptiness is the art |
| 06 | `darkforest_coast` | 8 | 6x6 | `metin2_map_capedragonhead` | the cliff texture *is* the ground; bones on black sand; a live skybox cube |
| 07 | `ice_valley` | 3 | 6x3 | `metin2_map_snakevalley` | spear rocks tilted into cliff faces 100 m from any path |
| 08 | `eastplain` | 4 | 4x5 | `metin2_map_eastplain_01` | 86 % Building and no town -- leaning ruins in a mostly-blocked plain |
| 09 | `empire_war` | 6 | 2x2 | `metin2_map_empirewar02` | one siege layout, three seasonal folders, a wall on a 10 m module |
| 10 | `guild_village` | 7 | 1x1 | `metin2_guild_village` | dense clutter terraced into a hillside; 88 % of block from slope |
| 11 | `arena_pvp` | 6 | 2x2 | `metin2_map_oxevent` | the densest maps in the corpus; whole-map safezone; flat plate, vertical rim |
| 12 | `dungeon_block` | 23 | 3x3 | `metin2_map_skipia_dungeon_02` | one black texture, `tile.raw` all `0x01`, corridor kits on a fixed pitch |
| 13 | `dungeon_themed` | 21 | 2x2 | `metin2_map_dawnmist_dungeon_01` | the same box, skinned; one flat-tone sky per biome; one art family per map |
| 14 | `elemental` | 4 | 5x5 | `metin2_map_elemental_01` | one 32 m carpet at 75 % of the ground; four tree families mixed; paths through the trees |
| 15 | `trent_forest` | 2 | 3x3 | `metin2_map_trent02` | 27 m between trunks, a sun below the horizon, the shortest fog shipped |
| 16 | `event_instance` | 10 | 3x3 | `metin2_12zi_stage` | not a look -- invent one prop family and use it for 60-90 % of the objects |
| 17 | `dev_stub` | 4 | 1x1 | `metin2_map_t1` | four broken test maps; a parser regression suite, not a template |

---

## Reading the numbers

Every figure in these files carries its source inline. A few conventions:

- **`weight` in a textureset table is the measured `ground_share` of the reference
  palette**, and each table sums to 1.000 by construction. It is an *intended coverage
  share*, not a multiplier -- `TextureSlot.weight` is normalised across slots.
- **`density` in an object table is placements per 100 m^2** over the archetype's whole
  terrain area. A 4x5-sector field is 1,310,000 m^2 = 13,100 units, so
  `density x 13,100` is the object count.
- **`spacing_cm` is the observed NN(same CRC) 5th percentile** -- the floor the artists
  respected, suitable as a Poisson-disk radius. The per-family median is quoted in prose
  and is what the *mixture* should reproduce.
- **`max_slope` is the per-CRC slope p95**, `road_clearance_cm` the per-CRC d(road) p25,
  and `height_bias` the (p25, p75) of the stored bias, sampled uniformly.
- **CRCs are real.** Every one appears in `../catalog/stats-objects.json.by_crc`. Where a
  prop is used but falls below the 420-row cutoff at which per-CRC statistics are
  published, the cell reads `TODO: no catalog evidence` rather than a plausible guess --
  an invented CRC makes the object silently vanish in game.
- **Road figures are caveated.** `../catalog/roads.json` aggregates were produced before
  the `road_verdict` filter existed and pool 29 terrain-ribbon maps the miner itself
  later rejected. Treat road grammar as indicative, not measured
  (`roads.json.by_archetype_caveat`).

---

## Cross-references

- Universal rules -> [`../taste.md`](../taste.md)
- The partition and its evidence -> [`../corpus-overview.md`](../corpus-overview.md)
- Placement grammar in full -> [`../placement.md`](../placement.md)
- Palette vocabulary and role taxonomy -> [`../textures.md`](../textures.md)
- `.msenv` keys, invariants and clusters -> [`../environments.md`](../environments.md)
- Collision grammar -> [`../attributes.md`](../attributes.md)
- Asset vocabulary by family -> [`../objects.md`](../objects.md)
- The spec these tables feed -> `../../scripts/m2map/gen/spec.py`

---

## Using the tables: pooled weights are not one map's weights

The `weight` column in each palette table is the archetype's **pooled** ground
share -- measured across every member map. That is the right number for "what
does this biome look like on average", and it is *not* what any single map does.

Verified by building one: `field_empire`'s pooled 17-slot palette produces a
brown-grey blend with a base share of 0.38, because pooling spreads coverage
across slots that individual maps use in different proportions. A real
`metin2_map_a1` uses about 12 of those slots with a base share near 0.5 and
reads distinctly greener.

So when you fill a `MapSpec`:

- **Take the paths, roles and UV scales verbatim** -- those are per-slot facts
  and they transfer.
- **Treat the weights as a starting distribution, not a target.** Pick the 6-10
  slots the map actually needs and concentrate the weight: one `base` around
  0.45-0.55 (the corpus median base share is 0.52), two or three `mid` slots
  sharing most of the rest, and `cliff`/`shore`/`accent` small.
- Slots with a pooled weight near 0.000 are dither partners or rarities. Include
  them only if you want that texture present at all; they will never form
  geometry.

The generator fits the achieved coverage to whatever weights you give it, so
the weights mean exactly what they say -- which is why getting them right
matters more than it would if they were only a nudge.

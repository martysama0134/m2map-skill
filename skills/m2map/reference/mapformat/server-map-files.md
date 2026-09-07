# Server Map Registration — `index`, `Setting.txt`, `Town.txt`, `dungeon.txt`

How the game server discovers and configures maps (`SECTREE_MANAGER::Build`, `m2dev-server-src/src/game/sectree_manager.cpp:733-814`). Per map folder the server opens exactly: `Setting.txt`, `Town.txt`, `server_attr`, `regen.txt`, `npc.txt`, `boss.txt`, `stone.txt`, `dungeon.txt` — nothing else. `mapproperty.txt`, `monsterarrange.txt`, `atlasinfo.txt`, texturesets and `.msenv` are client-only.

## `index` (map list)

`<MapPath>/index`, one map per line:

```
<mapIndex:int> <mapFolderName>
```

`//` or `#` starts a comment line. The folder name doubles as the map's display/registry name. Attribute/regen loading only happens for maps this game core hosts (`map_allow_find`).

## `Setting.txt` (server view)

Same physical file as the client's ([setting-txt.md](setting-txt.md)); the server reads **only three keys** (`sectree_manager.cpp:254-265`) and ignores everything else:

| Key | Tokens | Use |
|---|---|---|
| `MapSize` | int int | sectree counts X Y |
| `BasePosition` | int int | world origin (units) |
| `CellScale` | int | must be non-zero; used in the size formula |

Derived world size (`sectree_manager.cpp:270-279`):

```
worldWidth  = CellScale * 128 * MapSizeX      // e.g. 200*128*6 = 153,600
worldHeight = CellScale * 128 * MapSizeY
serverSectorsPerAxis = worldWidth / 6400      // e.g. 24
```

Server sector IDs are global: `(BaseX/6400 + x, BaseY/6400 + y)` packed as two 16-bit fields. **BasePosition must be a multiple of 6400** for clean sector alignment (official maps are: e.g. 256000, 665600).

## `Town.txt` (spawn points)

Read by `LoadMapRegion` (`sectree_manager.cpp:373-448`):

```
<townX> <townY> [<e1x> <e1y> <e2x> <e2y> <e3x> <e3y>]
```

- First pair: default spawn. Optional next 6 ints: per-empire spawns (Shinsoo/Chunjo/Jinno), used only if all 6 present.
- Coordinates are map-local **units of 100** (meters): `world = Base + value * 100`.

## `dungeon.txt` (named areas)

Read by `LoadDungeon` (`sectree_manager.cpp:322-365`). Per line:

```
<name> <x> <y> <sx> <sy> <dir>
```

`#`/`//` comments allowed. `(x, y)` = center, `(sx, sy)` = half-extents; loader converts to a top-left/bottom-right rect (`x-=sx; y-=sy; sx=x+2*sx; sy=y+2*sy`). **No ×100 scaling** here — values are raw world units. Used by dungeon quest scripts to reference named zones.

## Private/instanced maps

`CreatePrivateMap` clones a base map in memory (instance index = `base*10000 + n`); no extra files involved.

## Pitfalls

- Filenames: server opens `Setting.txt` / `Town.txt` capitalized, `server_attr`/`regen.txt`/etc. lowercase — matters on case-sensitive filesystems (FreeBSD/Linux servers).
- Missing or unreadable `Town.txt` (or `Setting.txt`) makes `Build` return failure immediately (`sectree_manager.cpp:764-778`) — **one broken map aborts the whole map-loading pass**, not just that map. Every map listed in `index` needs both files.
- The client's `atlasinfo.txt` (`mapname baseX baseY sizeX sizeY` per line, `MapManager.cpp:573-611`) must agree with each map's `Setting.txt` `BasePosition`/`MapSize`, or client minimap/world-map coordinates desync from the server.

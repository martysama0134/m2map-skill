# `regen.txt` / `npc.txt` / `boss.txt` / `stone.txt` — Server Spawn Files

Server-side spawn definitions, all four sharing one grammar (`regen_load`, `m2dev-server-src/src/game/regen.cpp:684-797`). Conventionally: `regen.txt` = monsters, `npc.txt` = NPCs, `boss.txt` = bosses, `stone.txt` = metin stones — but the parser is identical; the split is organizational.

- **Path:** `<server map dir>/regen.txt` (etc.), loaded per map at boot
- **Encoding:** plain text, whitespace/tab-separated tokens, `"quoted"` tokens allowed, `//` token starts a comment through end of line

## Line grammar

Canonical header comment (written by tools, ignored by parser):

```
//type	cx	cy	sx	sy	z	dir	time	percent	count	vnum
```

| # | Column | Type | Meaning |
|---|---|---|---|
| 0 | `type` | letter(s) | Spawn kind — see below. Only the first char (plus `a` for `ga`) matters |
| 1 | `cx` | int | Rect center X, map-local units of 100 (i.e. meters) |
| 2 | `cy` | int | Rect center Y, same units |
| 3 | `sx` | int | **Half-range** in X (radius, not a start coord, despite the name) |
| 4 | `sy` | int | **Half-range** in Y |
| 5 | `z` | byte | Z-section — passed only through the point-spawn path (`SpawnMob` Z); ranged/group/anywhere spawns ignore it. 0 = ground |
| 6 | `dir` | byte | Facing: `0` = random (one of 8×45°); `1..8` → angle `(dir-1) * 45°`. Only applied to point spawns |
| 7 | `time` | duration | Respawn interval: digits + `s`/`m`/`h` suffixes, additive (`1h30m` = 5400 s). Digits **without a suffix are discarded** (`regen.cpp:187-217`), and `time == 0` disables the line completely — not even the initial spawn happens (`regen.cpp:766`). Always write a suffix |
| 8 | `percent` | int | **Parsed and discarded** — the server ignores this column entirely (`regen.cpp:222-224`) |
| 9 | `count` | int | Max simultaneous spawns from this line |
| 10 | `vnum` | int | Mob vnum (`m`), group id from `group.txt` (`g`/`ga`), or group-group id from `group_group.txt` (`r`) |

### Type letters (`regen.cpp:107-130`)

| Token | Type | vnum meaning | Notes |
|---|---|---|---|
| `m` | MOB | mob_proto vnum | `m1`, `m2`… also parse as `m` (trailing chars ignored) |
| `g` | GROUP | group id | spawns the whole group from `group.txt` — **requires nonzero extents** (see below) |
| `ga` | GROUP aggressive | group id | same + `is_aggressive = true` |
| `r` | GROUP_GROUP | group-group id | picks a weighted random group from `group_group.txt` — same extent caveat |
| `s` | ANYWHERE | mob vnum | random position anywhere on the map; rect ignored |
| `e` | EXCEPTION | — | no-spawn rectangle; line ends after column 5 (`z`) — no dir/time/percent/count/vnum. **Dead in stock source**: the only `is_regen_exception` check is commented out (`char_manager.cpp:453-461`), so `e` rows are parsed and stored but have no effect |

**Point-spawn trap:** the spawn dispatcher checks `sx==ex && sy==ey` *before* the type switch (`regen.cpp:417`). A `g`/`ga`/`r` line with `0 0` extents takes the point path, which calls `SpawnMob` with the *group id as if it were a mob vnum* — the group never spawns. Give group lines a nonzero range.

Any other letter = fatal error (server exits).

## Coordinate math (`regen.cpp:142-170, 707-742`)

```
sx_world = (cx - sxHalf) * 100 + BasePosition.x
ex_world = (cx + sxHalf) * 100 + BasePosition.x
sy_world = (cy - syHalf) * 100 + BasePosition.y
ey_world = (cy + syHalf) * 100 + BasePosition.y
```

- Columns are in **1/100 world units** (= meters); the parser multiplies by 100. Equivalently: one regen unit = one client attr half-cell, so valid `cx` ∈ [0, MapSizeX·256] — community tools (Map-Converter) overlay regen points directly on the 256/sectree attribute grid.
- `BasePosition` comes from the map's `Setting.txt`.
- If `sxHalf == 0 && syHalf == 0` the rect degenerates to a point → exact-position spawn (used for NPCs).
- Exception (`e`) rects get the ×100 scaling but **not** the base offset (they're compared map-locally).

### Worked example (`metin2_map_n_desert_01`, base 204800×486400)

```
g	783	205	491	113	0	0	1m	100	174	62
```
→ GROUP id 62, respawn 60 s, up to 174 groups, world rect X [29,200 + 204,800 = 234,000 … 332,200], Y [495,600 … 518,200].

```
m	109	1427	0	0	0	0	1m	100	1	10016
```
→ single mob vnum 10016 at exact point (10,900, 142,700) + base.

## Referenced global files

- **`group.txt`** (`mob_manager.cpp:309-378`) — `CTextFileLoader` brace format:
  ```
  Group  Name
  {
      Vnum    101
      Leader  "label"  2001      ← 2nd token = leader mob vnum
      1       "label"  2002      ← numbered members 1..255, 2nd token = mob vnum
      2       "label"  2002
  }
  ```
- **`group_group.txt`** (`mob_manager.cpp:248-307`) — same shape; numbered rows are `<groupVnum> [probabilityWeight]`.

## WorldEditor's regen dialect (compatibility note)

The WorldEditor reads/writes a map-root `regen.txt` with the same 11 columns but only understands types `m` and `g`, requires all 11 tokens, and always writes `z=0`, `time=1m`, `percent=100` (`MapAccessorOutdoor.cpp:1620-1655`). It also emits `MonsterArrange.txt` — a deduplicated list of used vnums, one per line, read by nothing in the engine (content-pipeline aid). An editor supporting full server regen syntax (all 6 types, `e` short rows, time suffixes) is a superset of the WorldEditor dialect.

## Pitfalls

- `sx`/`sy` column names collide with "start x/y" intuition — they are **half-extents** around the center.
- `percent` does nothing; don't surface it as meaningful (keep writing `100` for byte-compat).
- `e` lines are shorter (6 tokens); a column-count-strict parser must special-case them.
- `time` without a suffix silently zeroes the interval and kills the line (see column table) — normalize to `Ns`/`Nm`/`Nh` on save.
- The parser only checks `token[0][0]`, so junk like `mob` parses as `m` — don't rely on it when writing. Community tools emit `ma`/`ra` as "aggressive" variants, but the server only honors the `a` suffix on `ga` — `ma`/`ra` silently degrade to plain `m`/`r`.
- `time` accepts bare digits (seconds) and mixed suffixes; normalize on save (`1m` style is conventional).

"""Server-side spawn placement -- regen/npc/boss/stone, Town, index.

The mode doc is `modes/server.md`; this is the engine behind it.

The whole job is picking *where*, and the constraint that makes it non-trivial
is that a spawn zone must be **walkable**. A zone whose cells are blocked drops
monsters inside terrain, where they are unreachable and frequently unkillable --
and nothing in the client or the server warns you, because from their point of
view the coordinates are perfectly valid.

Coordinates are the third convention in the map (see `modes/server.md`):

* ``areadata.txt``   map-local **centimetres**, Y negated
* ``attr.atr``       half-cell indices, 1 m
* ``regen`` / Town   **units of 100** -- metres, i.e. half-cell counts. The
                     server multiplies by 100 and adds ``BasePosition``.

So a spawn at tile (x, y) is written as (x, y) directly, with **no negation and
no base offset**. Getting that wrong puts spawns a hundred times too far out,
which is why the conversion lives in one place here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from ..codec import attr as attr_codec
from ..codec import regen as regen_codec
from .layout import Layout
from .spec import MapSpec

#: regen.txt type letters (see reference/mapformat/server-regen.md).
T_MONSTER = "m"
T_GROUP = "g"
T_EXCEPTION = "e"
T_STONE = "s"
T_NPC = "n"


@dataclass
class SpawnZone:
    """One regen entry, in tile space before conversion."""

    vnum: int
    kind: str = T_MONSTER
    #: centre in tiles (1 m)
    cx: float = 0.0
    cy: float = 0.0
    #: half-extent in tiles; the server spawns within this box
    sx: int = 10
    sy: int = 10
    z: int = 0
    direction: int = 0
    #: respawn time, server format ("5s", "1m", ...)
    time: str = "1m"
    percent: int = 100
    count: int = 1


def walkable_mask(attr_cells: np.ndarray) -> np.ndarray:
    """Cells a player can actually stand on."""
    return (attr_cells & attr_codec.ATTR_BLOCK) == 0


def _zone_is_walkable(walk: np.ndarray, z: SpawnZone, min_share: float = 0.6) -> bool:
    """A zone is usable when most of its box is open ground.

    Not *all* of it: real regen boxes routinely clip a rock or a building edge,
    and demanding 100% rejects placements the corpus is full of.
    """
    h, w = walk.shape
    x0, x1 = int(max(0, z.cx - z.sx)), int(min(w, z.cx + z.sx + 1))
    y0, y1 = int(max(0, z.cy - z.sy)), int(min(h, z.cy + z.sy + 1))
    if x1 <= x0 or y1 <= y0:
        return False
    box = walk[y0:y1, x0:x1]
    return float(box.mean()) >= min_share


def place(spec: MapSpec, lay: Layout, attr_cells: np.ndarray,
          monsters: Sequence[Tuple[int, int]] = (),
          npcs: Sequence[int] = (),
          bosses: Sequence[int] = (),
          stones: Sequence[Tuple[int, int]] = (),
          ) -> Dict[str, List[SpawnZone]]:
    """Choose spawn zones.

    ``monsters`` and ``stones`` are ``(vnum, count)``; ``npcs`` and ``bosses``
    are bare vnums placed once each.

    Placement follows the map's own regions, which is what the corpus does:
    NPCs stand in the settlement, monsters fill open ground away from it, and
    the road corridor is kept clear so a player can travel without being
    ambushed on the only route.
    """
    walk = walkable_mask(attr_cells)
    h, w = walk.shape
    rng = spec.rng("spawns")

    settlement = lay.regions.get("settlement")
    road_near = lay.road_distance <= 12.0 if lay.corridors else np.zeros_like(walk)

    open_ground = walk & ~road_near
    if settlement is not None:
        open_ground &= ~settlement
    # keep zones off the sealed border
    b = max(4, int(spec.border_band_m) + 4)
    open_ground[:b, :] = open_ground[-b:, :] = False
    open_ground[:, :b] = open_ground[:, -b:] = False

    out: Dict[str, List[SpawnZone]] = {"regen": [], "npc": [], "boss": [], "stone": []}

    def pick(mask: np.ndarray, sx: int, sy: int, tries: int = 400):
        ys, xs = np.nonzero(mask)
        if not len(xs):
            return None
        for _ in range(tries):
            i = rng.randrange(len(xs))
            z = SpawnZone(vnum=0, cx=float(xs[i]), cy=float(ys[i]), sx=sx, sy=sy)
            if _zone_is_walkable(walk, z):
                return z
        return None

    for vnum, count in monsters:
        z = pick(open_ground, 18, 18)
        if z is None:
            continue
        z.vnum, z.count, z.kind = vnum, count, T_MONSTER
        z.time = "1m"
        out["regen"].append(z)

    for vnum, count in stones:
        z = pick(open_ground, 12, 12)
        if z is None:
            continue
        z.vnum, z.count, z.kind = vnum, count, T_STONE
        z.time = "5m"
        out["stone"].append(z)

    npc_ground = walk.copy()
    if settlement is not None and (settlement & walk).any():
        npc_ground &= settlement
    for vnum in npcs:
        z = pick(npc_ground, 2, 2)
        if z is None:
            continue
        z.vnum, z.count, z.kind = vnum, 1, T_NPC
        z.time = "1m"
        out["npc"].append(z)

    for vnum in bosses:
        z = pick(open_ground, 8, 8)
        if z is None:
            continue
        z.vnum, z.count, z.kind = vnum, 1, T_MONSTER
        z.time = "30m"
        out["boss"].append(z)

    return out


def to_regen_file(zones: Iterable[SpawnZone]) -> regen_codec.RegenFile:
    """Build a RegenFile. Coordinates go out in units of 100 -- see module doc."""
    rows = []
    for z in zones:
        rows.append(regen_codec.RegenRow(
            type=z.kind,
            cx=int(round(z.cx)), cy=int(round(z.cy)),
            sx=int(z.sx), sy=int(z.sy),
            z=int(z.z), dir=int(z.direction),
            time=z.time, percent=int(z.percent),
            count=int(z.count), vnum=int(z.vnum)))
    return regen_codec.RegenFile(rows=rows)


def audit_zones(zones: Iterable[SpawnZone], attr_cells: np.ndarray,
                spec: MapSpec) -> List[str]:
    """Problems a spawn set can have that nothing downstream will report."""
    walk = walkable_mask(attr_cells)
    h, w = walk.shape
    out: List[str] = []
    for z in zones:
        if not (0 <= z.cx < w and 0 <= z.cy < h):
            out.append("vnum %d at (%.0f, %.0f) is outside the map (%dx%d tiles)"
                       % (z.vnum, z.cx, z.cy, w, h))
            continue
        box_ok = _zone_is_walkable(walk, z)
        if not box_ok:
            x0, x1 = int(max(0, z.cx - z.sx)), int(min(w, z.cx + z.sx + 1))
            y0, y1 = int(max(0, z.cy - z.sy)), int(min(h, z.cy + z.sy + 1))
            share = float(walk[y0:y1, x0:x1].mean()) if x1 > x0 and y1 > y0 else 0.0
            out.append("vnum %d zone at (%.0f, %.0f) is only %.0f%% walkable -- "
                       "monsters will spawn inside terrain, unreachable"
                       % (z.vnum, z.cx, z.cy, 100 * share))
        if z.count <= 0:
            out.append("vnum %d has count %d" % (z.vnum, z.count))
    return out


def write(out_dir, spawn_sets: Dict[str, List[SpawnZone]]) -> List[str]:
    """Write regen.txt / npc.txt / boss.txt / stone.txt + monsterarrange.txt."""
    import pathlib
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: List[str] = []
    files = {}
    for name in ("regen", "npc", "boss", "stone"):
        zones = spawn_sets.get(name) or []
        if not zones:
            continue
        rf = to_regen_file(zones)
        files[name] = rf
        (out / ("%s.txt" % name)).write_bytes(rf.to_bytes())
        written.append("%s.txt" % name)

    if files:
        # Derived, never hand-maintained. Nothing reads it -- it is a
        # content-pipeline aid the WorldEditor emits beside regen.txt.
        ma = regen_codec.MonsterArrange.from_regen(*files.values())
        (out / "monsterarrange.txt").write_bytes(ma.to_bytes())
        written.append("monsterarrange.txt")
    return written

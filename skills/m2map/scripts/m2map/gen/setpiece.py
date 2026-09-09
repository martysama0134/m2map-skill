"""Copy a shipped set-piece whole, and stamp it somewhere else unchanged.

A camp, a shrine, a fenced yard: the thing that makes it read as a *place* is
the relationships between its parts -- the rails against the tents, the stall
clutter against the brazier, three panel lengths mixed so the run closes. No
density, spacing or per-CRC statistic carries that. Every attempt to generate
the fenced camp of ``metin2_map_n_desert_01`` from measurements failed in a new
way: posts on a circle (roll drawn per record), an arc at the corpus median
pitch (gaps -- the six fence models are different lengths), a "run template"
chained from nearby records (a blob of several runs stamped over each other).
The version that finally matched the reference render was the one that did no
generating at all: every record within 32 m of the point, offsets, rolls and
height biases verbatim, translated as a block.

So this module does two small things and refuses to do a third:

* :func:`extract` -- read every ``areadata`` record within ``radius_m`` of a
  point on a source map, as offsets from that point.
* :func:`stamp` -- turn those offsets into authored :class:`ObjectTier` s
  anchored at a point on the new map, each record keeping its own roll and
  ``height_bias``.
* it does **not** rotate. The tile offsets are y-down map coordinates and
  ``roll`` is a compass heading; the handedness between the two is not pinned
  down, and a rotated compound looked right in every number and came apart in
  the render. Translate only; if the piece has to face another way, pick a
  different source.

Two facts about the copied compound the caller should know: the source stands
on one plane (all 32 records of that camp share ``z`` to the centimetre), so
level a pad under the target with ``PlazaSpec(tile_index=0, safezone=False)``
-- :func:`relief_cm` reports how flat the source was; and its parts share a
handful of headings (105 / 285 / 315 there, trees included), which is the
signature of something turned as a unit and the reason a set-piece is copied
rather than assembled.

Run as a script it prints the table as a Python literal, ready to paste into a
spec::

    python -m m2map.gen.setpiece <CORPUS>/metin2_map_n_desert_01 333 307 32
"""

from __future__ import annotations

import json
import math
import pathlib
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from ..codec import areadata as ad
from .spec import ObjectTier

__all__ = ["Piece", "extract", "stamp", "extent_m", "relief_cm", "headings"]


@dataclass(frozen=True)
class Piece:
    """One copied record: where it stands relative to the anchor, in metres of
    the y-down tile frame (``dx`` east, ``dy`` south), and what it is."""

    dx: float
    dy: float
    roll: float
    height_bias: float
    crc: int
    #: ground z the source placed it on, cm -- for :func:`relief_cm` only
    z: float = 0.0


def _sector_files(map_dir: pathlib.Path) -> List[pathlib.Path]:
    return sorted(p for p in map_dir.glob("[0-9][0-9][0-9][0-9][0-9][0-9]/areadata.txt"))


def extract(map_dir, centre_m: Tuple[float, float], radius_m: float) -> List[Piece]:
    """Every record within ``radius_m`` of ``centre_m`` on ``map_dir``.

    ``centre_m`` is in metres of the map-local frame the editor's status bar
    shows -- ``(333, 307)`` for the desert camp. Records come back sorted by
    distance from the centre so the table is stable across runs.
    """
    map_dir = pathlib.Path(map_dir)
    cx, cy = float(centre_m[0]) * 100.0, float(centre_m[1]) * 100.0
    r_cm = float(radius_m) * 100.0
    out: List[Tuple[float, Piece]] = []
    for f in _sector_files(map_dir):
        for rec in ad.AreaData.load(f).records:
            dx_cm = rec.x - cx
            dy_cm = rec.terrain_y - cy          # areadata stores Y negated
            d = math.hypot(dx_cm, dy_cm)
            if d > r_cm:
                continue
            out.append((d, Piece(dx=dx_cm / 100.0, dy=dy_cm / 100.0,
                                 roll=float(rec.roll) % 360.0,
                                 height_bias=float(rec.height_bias),
                                 crc=int(rec.crc), z=float(rec.z))))
    out.sort(key=lambda t: (t[0], t[1].crc))
    return [p for _, p in out]


def stamp(pieces: Iterable[Piece], anchor: Tuple[float, float],
          label: str = "set-piece", names: Optional[Dict[int, str]] = None,
          tier: str = "filler") -> List[ObjectTier]:
    """Authored tiers that reproduce ``pieces`` around ``anchor`` (tile metres).

    One tier per ``(crc, height_bias)`` so every record keeps the bias it was
    shipped with; positions are ``(x, y, roll)`` triples so every record keeps
    its heading. ``max_slope`` is 90 because authored positions skip the
    candidate filters anyway, and a set-piece is levelled with a pad, not
    rejected by a slope test.
    """
    ax, ay = float(anchor[0]), float(anchor[1])
    groups: Dict[Tuple[int, float], List[Tuple[float, float, float]]] = {}
    order: List[Tuple[int, float]] = []
    for p in pieces:
        key = (p.crc, p.height_bias)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append((ax + p.dx, ay + p.dy, p.roll))
    tiers = []
    for crc, bias in order:
        nm = (names or {}).get(crc) or str(crc)
        tiers.append(ObjectTier(crc=crc, name="%s %s" % (label, nm), tier=tier,
                                density=0.0, spacing_cm=0.0, max_slope=90.0,
                                road_clearance_cm=0.0,
                                positions=list(groups[(crc, bias)]),
                                height_bias=(bias, bias)))
    return tiers


def extent_m(pieces: Sequence[Piece]) -> Tuple[float, float, float, float]:
    """``(min dx, max dx, min dy, max dy)`` -- how much ground the piece wants."""
    if not pieces:
        return (0.0, 0.0, 0.0, 0.0)
    xs = [p.dx for p in pieces]
    ys = [p.dy for p in pieces]
    return (min(xs), max(xs), min(ys), max(ys))


def relief_cm(pieces: Sequence[Piece]) -> float:
    """Spread of source ground heights under the piece. Near zero means the
    compound was built on a levelled plane and the target needs one too."""
    if not pieces:
        return 0.0
    zs = [p.z for p in pieces]
    return max(zs) - min(zs)


def headings(pieces: Sequence[Piece]) -> Dict[float, int]:
    """Roll histogram. A hand-turned compound shows two or three values."""
    out: Dict[float, int] = {}
    for p in pieces:
        out[p.roll] = out.get(p.roll, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


# --- as a script: print a table to paste into a spec -------------------------

def _catalog_names() -> Dict[int, str]:
    cat = pathlib.Path(__file__).resolve().parents[3] / "reference" / "catalog" / "objects.json"
    if not cat.exists():
        return {}
    try:
        objs = json.loads(cat.read_text(encoding="utf-8"))["objects"]
    except (OSError, ValueError, KeyError):
        return {}
    return {int(c): (e.get("property_name") or "") for c, e in objs.items()}


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        description="dump every areadata record around a point as a set-piece table")
    ap.add_argument("map_dir")
    ap.add_argument("x_m", type=float)
    ap.add_argument("y_m", type=float)
    ap.add_argument("radius_m", type=float)
    a = ap.parse_args(argv)
    pieces = extract(a.map_dir, (a.x_m, a.y_m), a.radius_m)
    names = _catalog_names()
    print("# %d records within %.0f m of (%.0f, %.0f) in %s"
          % (len(pieces), a.radius_m, a.x_m, a.y_m, pathlib.Path(a.map_dir).name))
    x0, x1, y0, y1 = extent_m(pieces)
    print("# spans x %+.1f..%+.1f  y %+.1f..%+.1f m; source relief %.0f cm; headings %s"
          % (x0, x1, y0, y1, relief_cm(pieces),
             " ".join("%g x%d" % kv for kv in headings(pieces).items())))
    print("SETPIECE = [")
    print("    # (dx m, dy m, roll, bias, crc) -- two decimals is 1 cm; a pasted")
    print("    # table can land a panel a centimetre off, extract() itself does not round")
    for p in pieces:
        print("    (%7.2f, %7.2f, %5g, %5g, %10d),  # %s"
              % (p.dx, p.dy, p.roll, p.height_bias, p.crc, names.get(p.crc, "")))
    print("]")
    return 0


if __name__ == "__main__":       # pragma: no cover
    raise SystemExit(main())

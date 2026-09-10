"""Copy a shipped set-piece whole, keep it as a pattern, stamp it anywhere --
turned as one block about its own centre.

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
height biases verbatim, moved as a block.

So a :class:`SetPiece` is that block: records as offsets from a **pivot**, by
default the centroid of the records, so the block can be turned about its own
centre and placed by that centre. Three operations:

* :func:`extract` -- read every ``areadata`` record within ``radius_m`` of a
  point on a source map.
* :meth:`SetPiece.rotated` -- turn the whole block by an angle, in the sense of
  ``roll``. The sign is measured, not assumed (below).
* :meth:`SetPiece.stamp` -- authored :class:`ObjectTier` s that put the pivot
  at an anchor on the new map, every record keeping its roll and
  ``height_bias``.

Patterns are saved as JSON under ``reference/setpieces/`` and come back with
:func:`load`.

**Which way roll turns.** ``roll`` is a heading around Z, and the tile frame
is y-down, so turning a block means turning the offsets one way and the rolls
the other -- get it wrong and every panel of a copied rail comes apart while
every spacing statistic still passes. Measured on 1,681 corpus fences whose
nearest neighbour is within 6 m: ``roll + atan2(dy_tile, dx_tile)`` is
constant (circular concentration **0.84**, mean 179 deg mod 180) and
``roll - bearing`` is noise (0.08). So roll is **counter-clockwise in the
y-up world**; seen in y-down tile offsets, adding ``deg`` to every roll turns
the offsets **clockwise**::

    dx' =  dx*cos + dy*sin
    dy' = -dx*sin + dy*cos
    roll' = roll + deg

:func:`rotate` does exactly that, and :func:`alignment` reports the
``roll + bearing`` concentration so a turned block can be checked against its
source without a render.

Two facts about the copied camp the caller should know: the source stands on
one plane (31 of 32 records share ``z``; the outlying palm is 58 cm lower), so
level a pad under the target with ``PlazaSpec(tile_index=0, safezone=False)``
sized to :meth:`SetPiece.extent_m` -- :meth:`SetPiece.relief_cm` says how flat
the source was; and its parts share a handful of headings (105 / 285 / 315
there, trees included), which is the signature of something turned as a unit
and the reason a set-piece is copied rather than assembled.

Run as a script it prints the table as a Python literal and can save the
pattern::

    python -m m2map.gen.setpiece <CORPUS>/metin2_map_n_desert_01 333 307 32 \\
        --name desert_camp --save reference/setpieces/desert_camp.json
"""

from __future__ import annotations

import json
import math
import pathlib
from dataclasses import dataclass, replace
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

from ..codec import areadata as ad
from .spec import ObjectTier

__all__ = ["Piece", "SetPiece", "extract", "load", "rotate", "stamp", "expand",
           "alignment", "extent_m", "relief_cm", "headings", "FORMAT"]

FORMAT = "m2map-setpiece/1"
#: every corpus heading sits on this ladder (taste.md 1.2); a turn that is not a
#: multiple of it takes the copied rolls off the ladder, which is legal and
#: looks hand-placed in the wrong way.
ROLL_STEP = 15.0


@dataclass(frozen=True)
class Piece:
    """One copied record: where it stands relative to the pivot, in metres of
    the y-down tile frame (``dx`` east, ``dy`` south), and what it is."""

    dx: float
    dy: float
    roll: float
    height_bias: float
    crc: int
    #: ground z the source placed it on, cm -- for :func:`relief_cm` only
    z: float = 0.0
    #: property name, for reading the table; not used for placement
    name: str = ""


@dataclass
class SetPiece:
    """A block of records about a pivot, with where it came from."""

    name: str
    pieces: List[Piece]
    source_map: str = ""
    #: the point :func:`extract` was asked for, map-local metres on the source
    source_point_m: Tuple[float, float] = (0.0, 0.0)
    radius_m: float = 0.0
    #: where the pivot sits on the source, map-local metres. Offsets are about
    #: this point; :meth:`stamp` puts it on the anchor.
    pivot_m: Tuple[float, float] = (0.0, 0.0)
    pivot: str = "centroid"
    #: how far this instance has been turned from the source, degrees of roll
    rotation_deg: float = 0.0
    notes: str = ""

    # --- geometry ---------------------------------------------------------
    def rotated(self, deg: float) -> "SetPiece":
        """The same block turned by ``deg`` about its pivot, in the sense of
        ``roll`` (see module docstring for the measured sign)."""
        return replace(self, pieces=rotate(self.pieces, deg),
                       rotation_deg=(self.rotation_deg + deg) % 360.0)

    def stamp(self, anchor: Tuple[float, float], label: Optional[str] = None,
              tier: str = "filler") -> List[ObjectTier]:
        return stamp(self.pieces, anchor, label=label or self.name, tier=tier)

    def extent_m(self) -> Tuple[float, float, float, float]:
        return extent_m(self.pieces)

    def relief_cm(self) -> float:
        return relief_cm(self.pieces)

    def headings(self) -> Dict[float, int]:
        return headings(self.pieces)

    def alignment(self) -> Tuple[float, float, int]:
        return alignment(self.pieces)

    # --- persistence ------------------------------------------------------
    def to_dict(self) -> Dict:
        x0, x1, y0, y1 = self.extent_m()
        return {
            "format": FORMAT,
            "name": self.name,
            "source_map": self.source_map,
            "source_point_m": [float(self.source_point_m[0]), float(self.source_point_m[1])],
            "radius_m": float(self.radius_m),
            "pivot": self.pivot,
            "pivot_m": [round(float(self.pivot_m[0]), 4), round(float(self.pivot_m[1]), 4)],
            "rotation_deg": float(self.rotation_deg),
            "notes": self.notes,
            "count": len(self.pieces),
            "extent_m": [round(x0, 2), round(x1, 2), round(y0, 2), round(y1, 2)],
            "relief_cm": round(self.relief_cm(), 1),
            "headings": {("%g" % k): v for k, v in self.headings().items()},
            "pieces": [
                {"dx": round(p.dx, 4), "dy": round(p.dy, 4), "roll": p.roll,
                 "bias": p.height_bias, "crc": p.crc, "z": p.z, "name": p.name}
                for p in self.pieces],
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "SetPiece":
        if d.get("format") != FORMAT:
            raise ValueError("not a %s document: format=%r" % (FORMAT, d.get("format")))
        pieces = [Piece(dx=float(e["dx"]), dy=float(e["dy"]), roll=float(e["roll"]),
                        height_bias=float(e.get("bias", 0.0)), crc=int(e["crc"]),
                        z=float(e.get("z", 0.0)), name=str(e.get("name", "")))
                  for e in d["pieces"]]
        return cls(name=d["name"], pieces=pieces, source_map=d.get("source_map", ""),
                   source_point_m=tuple(d.get("source_point_m", (0.0, 0.0))),
                   radius_m=float(d.get("radius_m", 0.0)),
                   pivot_m=tuple(d.get("pivot_m", (0.0, 0.0))),
                   pivot=d.get("pivot", "centroid"),
                   rotation_deg=float(d.get("rotation_deg", 0.0)),
                   notes=d.get("notes", ""))

    def save(self, path) -> pathlib.Path:
        path = pathlib.Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=1) + "\n", encoding="utf-8",
                        newline="\n")
        return path


def load(path) -> SetPiece:
    """A pattern saved by :meth:`SetPiece.save`."""
    return SetPiece.from_dict(json.loads(pathlib.Path(path).read_text(encoding="utf-8")))


# --- reading a source map ------------------------------------------------

def _sector_files(map_dir: pathlib.Path) -> List[pathlib.Path]:
    return sorted(p for p in map_dir.glob("[0-9][0-9][0-9][0-9][0-9][0-9]/areadata.txt"))


def extract(map_dir, centre_m: Tuple[float, float], radius_m: float,
            name: str = "", pivot: str = "centroid",
            names: Optional[Dict[int, str]] = None) -> SetPiece:
    """Every record within ``radius_m`` of ``centre_m`` on ``map_dir``, as a
    :class:`SetPiece` about its pivot.

    ``centre_m`` is in metres of the map-local frame the editor's status bar
    shows -- ``(333, 307)`` for the desert camp. ``pivot`` is ``"centroid"``
    (the mean of the record positions -- the block's own centre, which is what
    to turn it about) or ``"centre"`` (the point asked for). Records come back
    sorted by distance from the pivot so the table is stable across runs.
    """
    map_dir = pathlib.Path(map_dir)
    cx, cy = float(centre_m[0]) * 100.0, float(centre_m[1]) * 100.0
    r_cm = float(radius_m) * 100.0
    hits = []
    for f in _sector_files(map_dir):
        for rec in ad.AreaData.load(f).records:
            x, y = rec.x, rec.terrain_y          # areadata stores Y negated
            if math.hypot(x - cx, y - cy) <= r_cm:
                hits.append((x, y, rec))
    if pivot == "centroid" and hits:
        px = sum(h[0] for h in hits) / len(hits)
        py = sum(h[1] for h in hits) / len(hits)
    elif pivot in ("centroid", "centre", "center"):
        px, py = cx, cy
    else:
        raise ValueError("pivot must be 'centroid' or 'centre', got %r" % pivot)
    names = names or {}
    pieces = [Piece(dx=(x - px) / 100.0, dy=(y - py) / 100.0,
                    roll=float(rec.roll) % 360.0, height_bias=float(rec.height_bias),
                    crc=int(rec.crc), z=float(rec.z), name=names.get(int(rec.crc), ""))
              for x, y, rec in hits]
    pieces.sort(key=lambda p: (math.hypot(p.dx, p.dy), p.crc))
    return SetPiece(name=name or "%s_%d_%d" % (map_dir.name, round(centre_m[0]), round(centre_m[1])),
                    pieces=pieces, source_map=map_dir.name,
                    source_point_m=(float(centre_m[0]), float(centre_m[1])),
                    radius_m=float(radius_m), pivot_m=(px / 100.0, py / 100.0),
                    pivot="centroid" if pivot == "centroid" else "centre")


# --- turning and stamping --------------------------------------------------

def rotate(pieces: Iterable[Piece], deg: float) -> List[Piece]:
    """Turn a block about ``(0, 0)`` by ``deg`` in the sense of ``roll``.

    Roll is counter-clockwise in the y-up world (fences, n = 1,681: ``roll +
    atan2(dy_tile, dx_tile)`` concentration 0.84 against 0.08 for the
    difference), and the offsets are y-down, so the same turn is clockwise in
    them. Rolls gain ``deg``; they stay on the 15 deg ladder only if ``deg``
    is a multiple of it.
    """
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    out = []
    for p in pieces:
        out.append(replace(p, dx=p.dx * c + p.dy * s, dy=-p.dx * s + p.dy * c,
                           roll=(p.roll + deg) % 360.0))
    return out


def stamp(pieces: Union[SetPiece, Iterable[Piece]], anchor: Tuple[float, float],
          label: str = "set-piece", tier: str = "filler") -> List[ObjectTier]:
    """Authored tiers that reproduce ``pieces`` with the pivot on ``anchor``
    (tile metres).

    One tier per ``(crc, height_bias)`` so every record keeps the bias it was
    shipped with; positions are ``(x, y, roll)`` triples so every record keeps
    its heading. ``max_slope`` is 90 because authored positions skip the
    candidate filters anyway, and a set-piece is levelled with a pad, not
    rejected by a slope test.
    """
    ps = _pieces(pieces)
    ax, ay = float(anchor[0]), float(anchor[1])
    groups: Dict[Tuple[int, float], List[Tuple[float, float, float]]] = {}
    order: List[Tuple[int, float]] = []
    nm: Dict[int, str] = {}
    for p in ps:
        key = (p.crc, p.height_bias)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append((ax + p.dx, ay + p.dy, p.roll))
        if p.name:
            nm[p.crc] = p.name
    tiers = []
    for crc, bias in order:
        tiers.append(ObjectTier(crc=crc, name="%s %s" % (label, nm.get(crc) or crc),
                                tier=tier, density=0.0, spacing_cm=0.0, max_slope=90.0,
                                road_clearance_cm=0.0,
                                positions=list(groups[(crc, bias)]),
                                height_bias=(bias, bias)))
    return tiers


# --- from a mapspec ------------------------------------------------------------

def expand(spec):
    """A copy of ``spec`` with every `SetPieceSpec` turned into authored tiers
    and a levelling pad, and ``setpieces`` emptied.

    Called at the top of `pipeline.run`, so a YAML mapspec can say::

        setpieces:
          - pattern: desert_camp
            anchor: [88, 108]
            rotate_deg: 90

    The pad is a `PlazaSpec(tile_index=0, safezone=False)` centred on the
    anchor -- it paints and flags nothing, it only levels -- with radius
    ``pad_radius_m`` or, by default, the pattern's extent plus 4 m clamped to
    the plaza band. A turned block stays inside it because it turns about the
    same point.
    """
    from dataclasses import replace as _replace
    from .spec import PlazaSpec, SpecError, resolve_pattern

    if not getattr(spec, "setpieces", None):
        return spec
    objects = list(spec.objects)
    plazas = list(spec.plazas)
    for sps in spec.setpieces:
        path = resolve_pattern(sps.pattern)
        if path is None:
            raise SpecError("set-piece pattern %r not found" % sps.pattern)
        sp = load(path)
        if sps.rotate_deg:
            sp = sp.rotated(sps.rotate_deg)
        objects += sp.stamp(tuple(sps.anchor), label=sps.label or sp.name, tier=sps.tier)
        r = sps.pad_radius_m
        if r is None:
            x0, x1, y0, y1 = sp.extent_m()
            r = min(40.0, max(4.0, max(abs(x0), abs(x1), abs(y0), abs(y1)) + 4.0))
        if r > 0:
            plazas.append(PlazaSpec(centre=tuple(sps.anchor), radius_m=float(r),
                                    tile_index=0, safezone=False))
    return _replace(spec, objects=objects, plazas=plazas, setpieces=[])


# --- describing a block ------------------------------------------------------

def _pieces(x: Union[SetPiece, Iterable[Piece]]) -> List[Piece]:
    return list(x.pieces) if isinstance(x, SetPiece) else list(x)


def extent_m(pieces) -> Tuple[float, float, float, float]:
    """``(min dx, max dx, min dy, max dy)`` -- how much ground the piece wants."""
    ps = _pieces(pieces)
    if not ps:
        return (0.0, 0.0, 0.0, 0.0)
    xs = [p.dx for p in ps]
    ys = [p.dy for p in ps]
    return (min(xs), max(xs), min(ys), max(ys))


def relief_cm(pieces) -> float:
    """Spread of source ground heights under the piece. Near zero means the
    compound was built on a levelled plane and the target needs one too."""
    ps = _pieces(pieces)
    if not ps:
        return 0.0
    zs = [p.z for p in ps]
    return max(zs) - min(zs)


def headings(pieces) -> Dict[float, int]:
    """Roll histogram. A hand-turned compound shows two or three values."""
    out: Dict[float, int] = {}
    for p in _pieces(pieces):
        out[p.roll] = out.get(p.roll, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def alignment(pieces, link_m: float = 6.0,
              only: Optional[Iterable[int]] = None) -> Tuple[float, float, int]:
    """How tightly ``roll + bearing-to-nearest-neighbour`` clusters, mod 180.

    Returns ``(concentration, mean_deg, n)`` over records whose nearest other
    record is within ``link_m``, restricted to the CRCs in ``only`` when given.
    The invariant belongs to LINKED pieces -- fences, wall modules -- whose
    heading follows the line to the neighbour; over a whole compound (tents,
    trees, clutter) it is diluted to noise, so pass the fence CRCs. A copied
    rail scores what its source scores. Concentration is the circular
    resultant length on the doubled angle, so 1 is perfect and 0 is uniform.

    Blind spot: a turn with the wrong sign shifts the mean by twice the angle,
    so at 90 or 180 degrees it shows nothing (a fence has no front). The sign
    itself is measured from the corpus, not from this check.
    """
    ps = _pieces(pieces)
    if only is not None:
        keep = set(only)
        ps = [p for p in ps if p.crc in keep]
    vals = []
    for i, a in enumerate(ps):
        best = None
        for j, b in enumerate(ps):
            if i == j:
                continue
            d = math.hypot(b.dx - a.dx, b.dy - a.dy)
            if d <= link_m and (best is None or d < best[0]):
                best = (d, b)
        if best is None:
            continue
        b = best[1]
        br = math.degrees(math.atan2(b.dy - a.dy, b.dx - a.dx))
        vals.append(math.radians(2.0 * ((a.roll + br) % 180.0)))
    if not vals:
        return (0.0, 0.0, 0)
    sx = sum(math.cos(v) for v in vals) / len(vals)
    sy = sum(math.sin(v) for v in vals) / len(vals)
    return (math.hypot(sx, sy), (math.degrees(math.atan2(sy, sx)) / 2.0) % 180.0, len(vals))


# --- as a script: print a table to paste into a spec, or save a pattern ------

def _catalog_names() -> Dict[int, str]:
    cat = pathlib.Path(__file__).resolve().parents[3] / "reference" / "catalog" / "objects.json"
    if not cat.exists():
        return {}
    try:
        objs = json.loads(cat.read_text(encoding="utf-8"))["objects"]
    except (OSError, ValueError, KeyError):
        return {}
    return {int(c): (e.get("property_name") or "") for c, e in objs.items()}


def _linked_crcs(sp: SetPiece) -> Optional[List[int]]:
    """The fence CRCs of a pattern, by name, for :func:`alignment`."""
    crcs = sorted({p.crc for p in sp.pieces if "fence" in p.name.lower()})
    return crcs or None


def describe(sp: SetPiece) -> str:
    x0, x1, y0, y1 = sp.extent_m()
    conc, mu, n = alignment(sp.pieces, only=_linked_crcs(sp))
    return ("%d records within %.0f m of (%.0f, %.0f) in %s; pivot %s at (%.2f, %.2f) m; "
            "turned %g deg\n"
            "spans x %+.1f..%+.1f  y %+.1f..%+.1f m; source relief %.0f cm; headings %s\n"
            "roll+bearing concentration over linked pieces %.2f (mean %.0f, n=%d)"
            % (len(sp.pieces), sp.radius_m, sp.source_point_m[0], sp.source_point_m[1],
               sp.source_map, sp.pivot, sp.pivot_m[0], sp.pivot_m[1], sp.rotation_deg,
               x0, x1, y0, y1, sp.relief_cm(),
               " ".join("%g x%d" % kv for kv in sp.headings().items()), conc, mu, n))


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        description="dump every areadata record around a point as a set-piece, "
                    "about its centroid; optionally turn it and save it as a pattern")
    ap.add_argument("map_dir")
    ap.add_argument("x_m", type=float)
    ap.add_argument("y_m", type=float)
    ap.add_argument("radius_m", type=float)
    ap.add_argument("--name", default="")
    ap.add_argument("--pivot", choices=("centroid", "centre"), default="centroid")
    ap.add_argument("--rotate", type=float, default=0.0,
                    help="turn the block by this many degrees of roll before printing")
    ap.add_argument("--save", help="write the pattern as JSON here")
    ap.add_argument("--notes", default="")
    a = ap.parse_args(argv)
    sp = extract(a.map_dir, (a.x_m, a.y_m), a.radius_m, name=a.name, pivot=a.pivot,
                 names=_catalog_names())
    if a.rotate:
        sp = sp.rotated(a.rotate)
    sp.notes = a.notes
    for line in describe(sp).splitlines():
        print("# " + line)
    print("SETPIECE = [")
    print("    # (dx m, dy m, roll, bias, crc) about the pivot -- two decimals is 1 cm;")
    print("    # a pasted table can land a panel a centimetre off, the JSON does not")
    for p in sp.pieces:
        print("    (%7.2f, %7.2f, %5g, %5g, %10d),  # %s"
              % (p.dx, p.dy, p.roll, p.height_bias, p.crc, p.name))
    print("]")
    if a.save:
        print("# saved", sp.save(a.save))
    return 0


if __name__ == "__main__":       # pragma: no cover
    raise SystemExit(main())

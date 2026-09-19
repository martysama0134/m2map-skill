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


#: One character per tile in `Ground.rows`: an index into `Ground.palette`.
_GROUND_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"
#: ...and the tile that is left to the target map.
_GROUND_SKIP = "-"


def _norm_tex(path: str) -> str:
    """A texture path as a key: textureset files write `d:\\ymir work\\...`,
    mapspecs write `d:/ymir work/...`, and case is whatever the artist typed."""
    return str(path).replace("\\", "/").strip().lower()


@dataclass(frozen=True)
class Ground:
    """The paint under a compound: a 1 m tile grid about the pivot.

    Keyed by texture PATH, not by index -- a `tile.raw` byte only means
    something next to the textureset it was painted with, and the target map has
    its own. ``rows[j][i]`` is a digit into ``palette`` or ``-`` for "leave this
    tile to the target"; tile ``(i, j)`` covers ``origin_m + (i, j)`` to
    ``+ (i + 1, j + 1)`` in the pattern's y-down metres.

    The three c1 encampments are why this exists. Each stands on a solid
    `field 01` core with a `field 04` halo 4-8 m wide and a spur toward the
    road; a disc of road dirt under the stamped copy was only an approximation
    of that, and the halo is what stops the patch reading as a decal.
    """

    origin_m: Tuple[float, float]
    palette: List[str]
    rows: List[str]

    def cells(self) -> List[Tuple[float, float, str]]:
        """``(dx, dy, texture path)`` of every painted tile's centre."""
        out = []
        for j, row in enumerate(self.rows):
            for i, ch in enumerate(row):
                if ch != _GROUND_SKIP:
                    out.append((self.origin_m[0] + i + 0.5, self.origin_m[1] + j + 0.5,
                                self.palette[_GROUND_DIGITS.index(ch)]))
        return out

    def rotated(self, deg: float) -> "Ground":
        """Turned with the block: same sign as :func:`rotate`, nearest tile."""
        if not self.rows or not (deg % 360.0):
            return self
        t = math.radians(deg)
        c, sn = math.cos(t), math.sin(t)
        w, h = len(self.rows[0]), len(self.rows)
        ox, oy = self.origin_m
        corners = [(ox + i, oy + j) for i in (0, w) for j in (0, h)]
        turned = [(x * c + y * sn, -x * sn + y * c) for x, y in corners]
        nx0 = math.floor(min(x for x, _ in turned))
        ny0 = math.floor(min(y for _, y in turned))
        nw = int(math.ceil(max(x for x, _ in turned))) - nx0
        nh = int(math.ceil(max(y for _, y in turned))) - ny0
        rows = []
        for j in range(nh):
            out = []
            for i in range(nw):
                x, y = nx0 + i + 0.5, ny0 + j + 0.5
                sx, sy = x * c - y * sn, x * sn + y * c        # back into the source
                si, sj = int(math.floor(sx - ox)), int(math.floor(sy - oy))
                out.append(self.rows[sj][si] if 0 <= si < w and 0 <= sj < h
                           else _GROUND_SKIP)
            rows.append("".join(out))
        return Ground(origin_m=(float(nx0), float(ny0)), palette=list(self.palette), rows=rows)

    def to_dict(self) -> Dict:
        return {"origin_m": [round(self.origin_m[0], 4), round(self.origin_m[1], 4)],
                "size": [len(self.rows[0]) if self.rows else 0, len(self.rows)],
                "palette": list(self.palette), "rows": list(self.rows)}

    @classmethod
    def from_dict(cls, d: Dict) -> "Ground":
        return cls(origin_m=(float(d["origin_m"][0]), float(d["origin_m"][1])),
                   palette=[_norm_tex(t) for t in d["palette"]],
                   rows=[str(r) for r in d["rows"]])


@dataclass(frozen=True)
class Relief:
    """The landform under a pattern: heights on the 2 m vertex grid about the
    pivot, in cm above the source's own base level.

    For a pattern whose record is nothing without its terrain. The three
    volcanoes of ``metin2_map_battleroyale`` are ONE record each -- a smoke
    effect at roll 0, bias 0, standing on the crater floor -- and everything
    that reads as a volcano is the cone under it: 55-60 m of relief inside a
    40-50 m radius, a rim 7-13 m over the crater, 100% blocked out to 30-40 m.

    ``rows[j][i]`` is at ``origin_m + (i, j) * cell_m`` in the pattern's
    UNTURNED frame; :meth:`SetPiece.rotated` only accumulates the angle and the
    terrain stage samples through it, so a turned cone is not resampled twice.
    ``base`` is the 25th percentile of the ring between ``radius_m - feather_m``
    and ``radius_m`` -- a low quantile, because a cone's ring is half foot and
    half the next ridge, and the foot is the level it stands on.
    """

    origin_m: Tuple[float, float]
    rows: List[List[int]]
    radius_m: float
    feather_m: float = 16.0
    cell_m: float = 2.0

    def to_dict(self) -> Dict:
        return {"origin_m": [round(self.origin_m[0], 4), round(self.origin_m[1], 4)],
                "size": [len(self.rows[0]) if self.rows else 0, len(self.rows)],
                "cell_m": self.cell_m, "radius_m": self.radius_m, "feather_m": self.feather_m,
                # one string per row: `indent=1` would put every vertex on its own line
                "rows": [" ".join("%d" % v for v in r) for r in self.rows]}

    @classmethod
    def from_dict(cls, d: Dict) -> "Relief":
        return cls(origin_m=(float(d["origin_m"][0]), float(d["origin_m"][1])),
                   rows=[[int(v) for v in (r.split() if isinstance(r, str) else r)]
                         for r in d["rows"]],
                   radius_m=float(d["radius_m"]), feather_m=float(d.get("feather_m", 16.0)),
                   cell_m=float(d.get("cell_m", 2.0)))


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
    #: the paint under it, if it was read -- see :func:`with_ground`
    ground: Optional[Ground] = None
    #: the water surface the source stood at, world cm -- set for SHORE patterns
    #: (rafts, piers, fish huts), which are fitted to the water and not to the
    #: ground. With it, `stamp(water_cm=...)` hangs every piece at the same
    #: height over the target's water that it had over the source's.
    water_cm: Optional[float] = None
    #: the landform under it, if it was read -- see :func:`with_relief`
    relief: Optional[Relief] = None

    # --- geometry ---------------------------------------------------------
    def rotated(self, deg: float) -> "SetPiece":
        """The same block turned by ``deg`` about its pivot, in the sense of
        ``roll`` (see module docstring for the measured sign)."""
        return replace(self, pieces=rotate(self.pieces, deg),
                       rotation_deg=(self.rotation_deg + deg) % 360.0,
                       ground=self.ground.rotated(deg) if self.ground else None)

    def stamp(self, anchor: Tuple[float, float], label: Optional[str] = None,
              tier: str = "filler", water_cm: Optional[float] = None) -> List[ObjectTier]:
        if water_cm is not None and self.water_cm is None:
            raise ValueError("pattern %s has no water_cm to be fitted from" % self.name)
        return stamp(self.pieces, anchor, label=label or self.name, tier=tier,
                     rise_cm=(None if water_cm is None
                              else float(water_cm) - float(self.water_cm)))

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
        d = {
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
        if self.ground is not None:
            d["ground"] = self.ground.to_dict()
        if self.water_cm is not None:
            d["water_cm"] = float(self.water_cm)
        if self.relief is not None:
            d["relief"] = self.relief.to_dict()
        return d

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
                   notes=d.get("notes", ""),
                   ground=Ground.from_dict(d["ground"]) if d.get("ground") else None,
                   water_cm=(float(d["water_cm"]) if d.get("water_cm") is not None else None),
                   relief=Relief.from_dict(d["relief"]) if d.get("relief") else None)

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


def _dropper(names: Dict[int, str], exclude: Sequence[str]):
    """``crc -> bool``: is this record named out by ``exclude``?"""
    drop = [str(e).lower() for e in exclude]

    def dropped(crc: int) -> bool:
        label = names.get(crc, "").lower()
        return any(e == str(crc) or (label and e in label) for e in drop)
    return dropped


def extract(map_dir, centre_m: Tuple[float, float], radius_m: float,
            name: str = "", pivot: str = "centroid",
            names: Optional[Dict[int, str]] = None,
            exclude: Sequence[str] = ()) -> SetPiece:
    """Every record within ``radius_m`` of ``centre_m`` on ``map_dir``, as a
    :class:`SetPiece` about its pivot.

    ``centre_m`` is in metres of the map-local frame the editor's status bar
    shows -- ``(333, 307)`` for the desert camp. ``pivot`` is ``"centroid"``
    (the mean of the record positions -- the block's own centre, which is what
    to turn it about) or ``"centre"`` (the point asked for). Records come back
    sorted by distance from the pivot so the table is stable across runs.

    ``exclude`` drops records before the centroid is taken: each entry is a CRC
    in decimal, or a case-insensitive substring of the catalog name. A disc
    cannot always take one compound and nothing of the next -- the b1 town
    square at 60 m clips four corners and the gate of the walled estate beside
    it, and half a wall is worse than none.
    """
    map_dir = pathlib.Path(map_dir)
    cx, cy = float(centre_m[0]) * 100.0, float(centre_m[1]) * 100.0
    r_cm = float(radius_m) * 100.0
    names = names or {}
    dropped = _dropper(names, exclude)
    hits = []
    for f in _sector_files(map_dir):
        for rec in ad.AreaData.load(f).records:
            x, y = rec.x, rec.terrain_y          # areadata stores Y negated
            if math.hypot(x - cx, y - cy) <= r_cm and not dropped(int(rec.crc)):
                hits.append((x, y, rec))
    return _build(hits, map_dir.name, name, pivot, names,
                  centre_m=(float(centre_m[0]), float(centre_m[1])),
                  radius_m=float(radius_m))


def from_areadata(path, source_map: str = "", name: str = "",
                  pivot: str = "centroid",
                  names: Optional[Dict[int, str]] = None,
                  exclude: Sequence[str] = ()) -> SetPiece:
    """Every record of one ``areadata.txt`` -- a selection copied out of the
    editor, or a scratch map holding only the group -- as a :class:`SetPiece`.

    A hand-picked group is its own definition and a radius cannot reproduce it:
    the bounding box of the c1 east encampment also holds two stray fence panels
    and a tree its author left out. So there is no query point. The pivot is the
    centroid, ``source_point_m`` repeats it and ``radius_m`` is only a
    description -- the reach of the farthest record, rounded up.

    ``source_map`` names where the group stands (the coordinates are kept as
    ``pivot_m``, so the source can be rendered from the same camera).
    ``pivot="centre"`` is not meaningful here and is refused.
    """
    if pivot != "centroid":
        raise ValueError("a pasted group has no query point; pivot must be 'centroid'")
    names = names or {}
    dropped = _dropper(names, exclude)
    hits = []
    for rec in ad.AreaData.load(path).records:
        if dropped(int(rec.crc)):
            continue
        hits.append((rec.x, rec.terrain_y, rec))          # areadata stores Y negated
    if not hits:
        raise ValueError("no records in %s" % path)
    return _build(hits, source_map, name or pathlib.Path(path).stem, "centroid", names)


def verify_against(areadata_path, map_dir, names: Optional[Dict[int, str]] = None) -> Dict:
    """Check a pasted selection against the map it is said to come from.

    Every pasted record should exist on the map -- same position to the
    centimetre, same CRC, roll and bias. One that does not is a typo or the
    wrong map (``missing_from_map``). Records the map holds inside the paste's
    bounding box that the paste does NOT are reported too (``left_out``): they
    are what the author chose to leave out, and worth a look before saving --
    on the c1 east camp they were two stray fence panels and a tree.
    """
    names = names or {}
    pasted = list(ad.AreaData.load(areadata_path).records)
    if not pasted:
        raise ValueError("no records in %s" % areadata_path)
    x0, x1 = min(r.x for r in pasted) - 1.0, max(r.x for r in pasted) + 1.0
    y0, y1 = min(r.terrain_y for r in pasted) - 1.0, max(r.terrain_y for r in pasted) + 1.0
    on_map = [r for f in _sector_files(pathlib.Path(map_dir))
              for r in ad.AreaData.load(f).records
              if x0 <= r.x <= x1 and y0 <= r.terrain_y <= y1]

    def key(r):
        return (round(r.x), round(r.terrain_y), int(r.crc), float(r.roll) % 360.0,
                float(r.height_bias))

    def row(r):
        return {"x_m": round(r.x / 100.0, 2), "y_m": round(r.terrain_y / 100.0, 2),
                "crc": int(r.crc), "name": names.get(int(r.crc), ""),
                "roll": float(r.roll) % 360.0, "bias": float(r.height_bias)}

    have = {}
    for r in on_map:
        have.setdefault(key(r), []).append(r)
    missing = []
    for r in pasted:
        bucket = have.get(key(r))
        if bucket:
            bucket.pop()
        else:
            missing.append(row(r))
    left_out = [row(r) for bucket in have.values() for r in bucket]
    return {"pasted": len(pasted), "in_bbox": len(on_map), "missing_from_map": missing,
            "left_out": left_out, "exact": not missing and not left_out}


WE_OBJECTS_MAGIC = "WE_OBJECTS_V1"


def parse_we_objects(path) -> List[Tuple[float, float, int, float, float]]:
    """``(x_cm, y_cm, crc, roll, bias)`` per record of a WorldEditorRemix
    clipboard paste (``WE_OBJECTS_V1``, a count, then one line per object:
    ``x y z crc yaw pitch roll bias ...``).

    Unlike ``areadata.txt`` text the paste has **no absolute position**: ``x`` and
    ``y`` are offsets from the selection's own bounding box, and ``y`` grows
    **north** -- it is the stored (negated) ``areadata`` Y minus its minimum, so
    the record at ``y = 0`` is the southernmost. Measured on five pastes from
    ``metin2_map_battleroyale``: every record found with the sign flipped, none
    without. ``z`` is a small relative figure and is not used.
    """
    lines = pathlib.Path(path).read_text(encoding="utf-8").split("\n")
    if not lines or lines[0].strip() != WE_OBJECTS_MAGIC:
        raise ValueError("%s is not a %s paste" % (path, WE_OBJECTS_MAGIC))
    out = []
    for ln in lines[2:]:
        t = ln.split()
        if len(t) >= 8:
            out.append((float(t[0]), float(t[1]), int(t[3]), float(t[6]) % 360.0, float(t[7])))
    if not out:
        raise ValueError("no records in %s" % path)
    return out


def locate_we_objects(path, map_dir, tol_cm: float = 3.0) -> List[Dict]:
    """Every place on ``map_dir`` where a ``WE_OBJECTS_V1`` paste stands.

    The paste carries offsets only, so the group is found by its rarest CRC:
    each map record of that CRC is tried as the anchor and the rest of the paste
    is looked up around it -- position within ``tol_cm``, same CRC, roll and
    bias. Returns one dict per candidate, best first: ``records`` (the matched
    map records, paste order, ``None`` where nothing matched), ``matched``,
    ``left_out`` (map records inside the same box the paste does not hold).
    """
    pasted = parse_we_objects(path)
    on_map = [r for f in _sector_files(pathlib.Path(map_dir))
              for r in ad.AreaData.load(f).records]
    freq: Dict[int, int] = {}
    for r in on_map:
        freq[int(r.crc)] = freq.get(int(r.crc), 0) + 1
    a = min(pasted, key=lambda p: freq.get(p[2], 0) or 10 ** 9)
    sites = []
    for cand in on_map:
        if int(cand.crc) != a[2]:
            continue
        ox, oy = cand.x - a[0], cand.terrain_y + a[1]      # paste y grows north
        pool = list(on_map)
        got = []
        for px, py, crc, roll, bias in pasted:
            hit = next((r for r in pool if int(r.crc) == crc
                        and abs(r.x - (ox + px)) <= tol_cm
                        and abs(r.terrain_y - (oy - py)) <= tol_cm
                        and float(r.roll) % 360.0 == roll
                        and float(r.height_bias) == bias), None)
            if hit is not None:
                pool.remove(hit)
            got.append(hit)
        found = [r for r in got if r is not None]
        if not found:
            continue
        x0, x1 = min(r.x for r in found) - 1.0, max(r.x for r in found) + 1.0
        y0, y1 = min(r.terrain_y for r in found) - 1.0, max(r.terrain_y for r in found) + 1.0
        left = [r for r in pool if x0 <= r.x <= x1 and y0 <= r.terrain_y <= y1]
        sites.append({"records": got, "matched": len(found), "pasted": len(pasted),
                      "left_out": left})
    sites.sort(key=lambda s: -s["matched"])
    return sites


def from_we_objects(path, map_dir, name: str = "",
                    names: Optional[Dict[int, str]] = None,
                    exclude: Sequence[str] = ()) -> SetPiece:
    """A ``WE_OBJECTS_V1`` paste as a :class:`SetPiece`, built from the MAP's
    records once the paste has been found on it -- so the pattern has a
    ``pivot_m`` to render from and a ground to read, which the paste alone
    cannot give. Refuses a paste that is not wholly on the map.
    """
    map_dir = pathlib.Path(map_dir)
    sites = locate_we_objects(path, map_dir)
    if not sites or sites[0]["matched"] != sites[0]["pasted"]:
        raise ValueError("%s: %d of %d pasted records found on %s"
                         % (path, sites[0]["matched"] if sites else 0,
                            len(parse_we_objects(path)), map_dir.name))
    names = names or {}
    dropped = _dropper(names, exclude)
    hits = [(r.x, r.terrain_y, r) for r in sites[0]["records"] if not dropped(int(r.crc))]
    return _build(hits, map_dir.name, name or pathlib.Path(path).stem, "centroid", names)


def _find_textureset(map_dir: pathlib.Path, ref: str) -> Optional[pathlib.Path]:
    """Where ``setting.txt``'s ``TextureSet`` reference actually is.

    The engine resolves it against the data directory, so look beside the map,
    then up the tree the way a data dir is laid out (``<data>/maps/<map>`` next
    to ``<data>/textureset``), then in the configured client pack.
    """
    rel = pathlib.PureWindowsPath(ref)
    roots = [map_dir, map_dir.parent, map_dir.parent.parent]
    for root in roots:
        for cand in (root.joinpath(*rel.parts), root / "textureset" / rel.name):
            if cand.is_file():
                return cand
            if cand.parent.is_dir():                       # case-insensitive match
                for f in cand.parent.iterdir():
                    if f.name.lower() == cand.name.lower():
                        return f
    try:
        from ..config import paths
        base = paths().texturesets
        for f in base.iterdir():
            if f.name.lower() == rel.name.lower():
                return f
    except Exception:                                      # not configured / not mounted
        pass
    return None


def with_ground(sp: SetPiece, map_dir, keep: Sequence[str] = (), margin_m: float = 8.0,
                textureset=None, within_m: Optional[float] = None) -> SetPiece:
    """``sp`` with the source map's paint under it, as a :class:`Ground`.

    Reads ``tile.raw`` over the pattern's extent plus ``margin_m`` and resolves
    every index through the map's own textureset. ``keep`` is a list of
    case-insensitive substrings of the texture path; only matching tiles are
    kept, the rest are left to the target map. Without it the whole window is
    copied, grass and all, and the window's square edge shows wherever the
    target's ground differs -- so name the FEATURE: ``keep=["field"]`` takes a
    camp's dirt core and halo and leaves the meadow round it alone.

    ``within_m`` keeps only tiles inside that radius of the pivot -- for a
    landform, whose square window otherwise clips the lava of the next cone.
    """
    from ..codec import setting as setting_codec
    from ..codec import textureset as ts_codec

    map_dir = pathlib.Path(map_dir)
    if sp.rotation_deg:
        raise ValueError("read the ground before turning the pattern")
    if textureset is None:
        ref = setting_codec.Setting.load(map_dir / "setting.txt").texture_set
        textureset = _find_textureset(map_dir, str(ref))
        if textureset is None:
            raise FileNotFoundError("textureset %r of %s not found; pass textureset="
                                    % (ref, map_dir.name))
    slots = ts_codec.TextureSet.load(textureset).slots
    path_of = {i: _norm_tex(t.filename) for i, t in enumerate(slots) if t is not None}

    x0, x1, y0, y1 = sp.extent_m()
    px, py = sp.pivot_m
    X0, X1 = int(math.floor(px + x0 - margin_m)), int(math.ceil(px + x1 + margin_m))
    Y0, Y1 = int(math.floor(py + y0 - margin_m)), int(math.ceil(py + y1 + margin_m))
    want = [k.lower() for k in keep]
    sectors: Dict[Tuple[int, int], bytes] = {}
    palette: List[str] = []
    rows = []
    for ty in range(Y0, Y1):
        out = []
        for tx in range(X0, X1):
            key = (tx // 256, ty // 256)
            if key not in sectors:
                f = map_dir / ("%03d%03d" % key) / "tile.raw"
                sectors[key] = f.read_bytes() if tx >= 0 and ty >= 0 and f.is_file() else b""
            raw = sectors[key]
            tex = path_of.get(raw[(ty % 256 + 1) * 258 + (tx % 256 + 1)]) if raw else None
            if within_m is not None and math.hypot(tx + 0.5 - px, ty + 0.5 - py) > within_m:
                tex = None
            if tex is None or (want and not any(k in tex for k in want)):
                out.append(_GROUND_SKIP)
                continue
            if tex not in palette:
                if len(palette) >= len(_GROUND_DIGITS):
                    raise ValueError("more than %d textures under one pattern" % len(_GROUND_DIGITS))
                palette.append(tex)
            out.append(_GROUND_DIGITS[palette.index(tex)])
        rows.append("".join(out))
    return replace(sp, ground=Ground(origin_m=(X0 - px, Y0 - py), palette=palette, rows=rows))


def with_relief(sp: SetPiece, map_dir, radius_m: float, feather_m: float = 16.0) -> SetPiece:
    """``sp`` with the source map's landform under it, as a :class:`Relief`.

    Reads ``height.raw`` on the vertex grid over a square of ``radius_m`` about
    the pivot and stores it relative to the base level (see :class:`Relief`).
    Save the ground with ``--ground-margin`` equal to the radius, so the paint
    on the mountain -- a volcano's lava head -- comes with it.
    """
    import numpy as np
    from ..codec import height as height_codec

    map_dir = pathlib.Path(map_dir)
    if sp.rotation_deg:
        raise ValueError("read the relief before turning the pattern")
    px, py = sp.pivot_m
    i0, i1 = int(math.floor((px - radius_m) / 2.0)), int(math.ceil((px + radius_m) / 2.0))
    j0, j1 = int(math.floor((py - radius_m) / 2.0)), int(math.ceil((py + radius_m) / 2.0))
    sectors: Dict[Tuple[int, int], Optional[object]] = {}

    def grid(key):
        if key not in sectors:
            f = map_dir / ("%03d%03d" % key) / "height.raw"
            sectors[key] = (height_codec.read_height(f).world_z()
                            if min(key) >= 0 and f.is_file() else None)
        return sectors[key]

    z = np.zeros((j1 - j0 + 1, i1 - i0 + 1))
    for j in range(j0, j1 + 1):
        for i in range(i0, i1 + 1):
            # vertex 128 of one sector is vertex 0 of the next; on the map's far
            # edge only the first exists
            for key in ((i // 128, j // 128), ((i - 1) // 128, j // 128),
                        (i // 128, (j - 1) // 128), ((i - 1) // 128, (j - 1) // 128)):
                g = grid(key)
                li, lj = i - key[0] * 128, j - key[1] * 128
                if g is not None and 0 <= li <= 128 and 0 <= lj <= 128:
                    z[j - j0, i - i0] = g[lj, li]
                    break
            else:
                raise ValueError("relief window leaves %s at vertex (%d, %d)" % (map_dir.name, i, j))
    yy, xx = np.mgrid[j0:j1 + 1, i0:i1 + 1]
    r = np.hypot(xx * 2.0 - px, yy * 2.0 - py)
    ring = (r >= radius_m - feather_m) & (r <= radius_m)
    base = float(np.percentile(z[ring], 25))
    rows = [[int(round(v - base)) for v in row] for row in z]
    return replace(sp, relief=Relief(origin_m=(i0 * 2.0 - px, j0 * 2.0 - py), rows=rows,
                                     radius_m=float(radius_m), feather_m=float(feather_m)))


def _build(hits, source_map: str, name: str, pivot: str, names: Dict[int, str],
           centre_m: Optional[Tuple[float, float]] = None,
           radius_m: Optional[float] = None) -> SetPiece:
    """``hits`` -- ``(x_cm, terrain_y_cm, record)`` -- about their pivot."""
    if pivot == "centroid" and hits:
        px = sum(h[0] for h in hits) / len(hits)
        py = sum(h[1] for h in hits) / len(hits)
    elif pivot in ("centroid", "centre", "center") and centre_m is not None:
        px, py = centre_m[0] * 100.0, centre_m[1] * 100.0
    else:
        raise ValueError("pivot must be 'centroid' or 'centre', got %r" % pivot)
    pieces = [Piece(dx=(x - px) / 100.0, dy=(y - py) / 100.0,
                    roll=float(rec.roll) % 360.0, height_bias=float(rec.height_bias),
                    crc=int(rec.crc), z=float(rec.z), name=names.get(int(rec.crc), ""))
              for x, y, rec in hits]
    pieces.sort(key=lambda p: (math.hypot(p.dx, p.dy), p.crc))
    if centre_m is None:
        centre_m = (px / 100.0, py / 100.0)
    if radius_m is None:
        radius_m = float(math.ceil(max(math.hypot(p.dx, p.dy) for p in pieces)))
    return SetPiece(name=name or "%s_%d_%d" % (source_map, round(centre_m[0]), round(centre_m[1])),
                    pieces=pieces, source_map=source_map,
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
          label: str = "set-piece", tier: str = "filler",
          rise_cm: Optional[float] = None) -> List[ObjectTier]:
    """Authored tiers that reproduce ``pieces`` with the pivot on ``anchor``
    (tile metres).

    ``rise_cm`` switches from "the bias it was shipped with, over whatever ground
    is there" to "the HEIGHT it was shipped at, moved by this much" -- a shore
    pattern passes target water minus source water, so each deck keeps its
    clearance over the surface. Such tiers carry `absolute_z` and no footprint:
    a pier is walked on.

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
        key = (p.crc, p.height_bias if rise_cm is None
               else round(p.z + p.height_bias + rise_cm, 2))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append((ax + p.dx, ay + p.dy, p.roll))
        if p.name:
            nm[p.crc] = p.name
    tiers = []
    for crc, bias in order:
        t = ObjectTier(crc=crc, name="%s %s" % (label, nm.get(crc) or crc),
                       tier=tier, density=0.0, spacing_cm=0.0, max_slope=90.0,
                       road_clearance_cm=0.0,
                       positions=list(groups[(crc, bias)]),
                       height_bias=(bias, bias) if rise_cm is None else (0.0, 0.0))
        if rise_cm is not None:
            t.absolute_z = float(bias)          # the key holds the absolute height here
            t.footprint = False
        tiers.append(t)
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
    ``pad_radius_m`` or, by default, the pattern's extent plus 4 m (a pad is
    exempt from the plaza band; a town is wider than any disc). A turned block stays inside it because it turns about the
    same point.
    """
    from dataclasses import replace as _replace
    from .spec import (GroundStampSpec, PlazaSpec, ReliefStampSpec, SpecError,
                       resolve_pattern)

    if not getattr(spec, "setpieces", None):
        return spec
    objects = list(spec.objects)
    plazas = list(spec.plazas)
    grounds = list(spec.ground_stamps)
    reliefs = list(spec.relief_stamps)
    for sps in spec.setpieces:
        path = resolve_pattern(sps.pattern)
        if path is None:
            raise SpecError("set-piece pattern %r not found" % sps.pattern)
        sp = load(path)
        if sps.rotate_deg:
            sp = sp.rotated(sps.rotate_deg)
        objects += sp.stamp(tuple(sps.anchor), label=sps.label or sp.name, tier=sps.tier,
                            water_cm=sps.water_cm)
        r = sps.pad_radius_m
        if r is None and sps.water_cm is not None:
            r = 0.0                       # a pad would flatten the shore it stands on
        if r is None and sp.relief is not None:
            r = 0.0                       # ...or the mountain it came with
        if r is None:
            x0, x1, y0, y1 = sp.extent_m()
            r = max(4.0, max(abs(x0), abs(x1), abs(y0), abs(y1)) + 4.0)
        if r > 0:
            plazas.append(PlazaSpec(centre=tuple(sps.anchor), radius_m=float(r),
                                    tile_index=0, safezone=False))
        if sps.ground and sp.ground is not None:
            grounds.append(GroundStampSpec(anchor=tuple(sps.anchor),
                                           origin_m=tuple(sp.ground.origin_m),
                                           palette=list(sp.ground.palette),
                                           rows=list(sp.ground.rows),
                                           label=sps.label or sp.name))
        if sp.relief is not None:
            reliefs.append(ReliefStampSpec(anchor=tuple(sps.anchor),
                                           origin_m=tuple(sp.relief.origin_m),
                                           rows=[list(x) for x in sp.relief.rows],
                                           radius_m=sp.relief.radius_m,
                                           feather_m=sp.relief.feather_m,
                                           cell_m=sp.relief.cell_m,
                                           rotate_deg=sp.rotation_deg,
                                           label=sps.label or sp.name))
    return _replace(spec, objects=objects, plazas=plazas, setpieces=[],
                    ground_stamps=grounds, relief_stamps=reliefs)


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
    ap.add_argument("map_dir", nargs="?")
    ap.add_argument("x_m", type=float, nargs="?")
    ap.add_argument("y_m", type=float, nargs="?")
    ap.add_argument("radius_m", type=float, nargs="?")
    ap.add_argument("--from-areadata", metavar="FILE",
                    help="take every record of this areadata.txt -- a selection copied "
                         "out of the editor -- instead of a map, a point and a radius")
    ap.add_argument("--verify-against", metavar="MAP_DIR",
                    help="with --from-areadata: check every pasted record exists on this "
                         "map, and list what the map holds in the same box that the paste "
                         "does not; exits 1 if a pasted record is not on the map")
    ap.add_argument("--from-we-objects", metavar="FILE",
                    help="take a WorldEditorRemix clipboard paste (WE_OBJECTS_V1). It holds "
                         "offsets only, so give --locate-on: the group is found on that map "
                         "and the pattern is built from the map's own records")
    ap.add_argument("--locate-on", metavar="MAP_DIR",
                    help="with --from-we-objects: the map the selection was copied from")
    ap.add_argument("--source-map", default="",
                    help="with --from-areadata: the map the group stands on")
    ap.add_argument("--name", default="")
    ap.add_argument("--pivot", choices=("centroid", "centre"), default="centroid")
    ap.add_argument("--rotate", type=float, default=0.0,
                    help="turn the block by this many degrees of roll before printing")
    ap.add_argument("--exclude", action="append", default=[], metavar="NAME|CRC",
                    help="drop records whose catalog name contains this, or whose "
                         "CRC is this; repeatable")
    ap.add_argument("--ground-from", metavar="MAP_DIR",
                    help="also save the paint under the group, read from this map "
                         "(default with MAP_DIR X Y R: that map, if --ground-keep is given)")
    ap.add_argument("--ground-keep", action="append", default=[], metavar="SUBSTR",
                    help="keep only tiles whose texture path contains this (repeatable); "
                         "name the feature, e.g. 'field' for a camp's dirt")
    ap.add_argument("--ground-margin", type=float, default=8.0, metavar="M")
    ap.add_argument("--relief-radius", type=float, default=None, metavar="M",
                    help="also save the LANDFORM: the source heights within this radius "
                         "of the pivot, relative to the level of the ring at its edge -- "
                         "for a record that is nothing without its mountain (a volcano). "
                         "Read from --ground-from / --locate-on / MAP_DIR")
    ap.add_argument("--water-cm", type=float, default=None,
                    help="the water surface the group stands at, world cm -- for a SHORE "
                         "pattern (rafts, piers), which is then stamped relative to the "
                         "target's water instead of its ground")
    ap.add_argument("--save", help="write the pattern as JSON here")
    ap.add_argument("--notes", default="")
    a = ap.parse_args(argv)
    if a.from_areadata and a.verify_against:
        rep = verify_against(a.from_areadata, a.verify_against, names=_catalog_names())
        print("# verify: %d pasted, %d on the map inside the same box%s"
              % (rep["pasted"], rep["in_bbox"], " -- exact match" if rep["exact"] else ""))
        for r in rep["left_out"]:
            print("#   left out by the author: %(name)s %(crc)d at (%(x_m).1f, %(y_m).1f) roll %(roll)g" % r)
        for r in rep["missing_from_map"]:
            print("#   NOT ON THE MAP: %(name)s %(crc)d at (%(x_m).1f, %(y_m).1f) roll %(roll)g" % r)
        if rep["missing_from_map"]:
            return 1
    if a.from_we_objects:
        if not a.locate_on:
            ap.error("--from-we-objects needs --locate-on MAP_DIR")
        names = _catalog_names()
        sites = locate_we_objects(a.from_we_objects, a.locate_on)
        for s in sites:
            recs = [r for r in s["records"] if r is not None]
            print("# located: %d of %d at (%.1f, %.1f) m%s"
                  % (s["matched"], s["pasted"],
                     sum(r.x for r in recs) / len(recs) / 100.0,
                     sum(r.terrain_y for r in recs) / len(recs) / 100.0,
                     " -- exact match" if s["matched"] == s["pasted"] and not s["left_out"] else ""))
        if not sites or sites[0]["matched"] != sites[0]["pasted"]:
            print("#   NOT ON THE MAP as pasted")
            return 1
        for r in sites[0]["left_out"]:
            print("#   left out by the author: %s %d at (%.1f, %.1f) roll %g"
                  % (names.get(int(r.crc), ""), int(r.crc), r.x / 100.0, r.terrain_y / 100.0,
                     float(r.roll) % 360.0))
        sp = from_we_objects(a.from_we_objects, a.locate_on, name=a.name, names=names,
                             exclude=a.exclude)
        a.ground_from = a.ground_from or (a.locate_on if a.ground_keep else None)
    elif a.from_areadata:
        sp = from_areadata(a.from_areadata, source_map=a.source_map, name=a.name,
                           pivot=a.pivot, names=_catalog_names(), exclude=a.exclude)
    elif None in (a.map_dir, a.x_m, a.y_m, a.radius_m):
        ap.error("give MAP_DIR X_M Y_M RADIUS_M, or --from-areadata FILE")
    else:
        sp = extract(a.map_dir, (a.x_m, a.y_m), a.radius_m, name=a.name, pivot=a.pivot,
                     names=_catalog_names(), exclude=a.exclude)
    ground_map = a.ground_from or (a.map_dir if a.ground_keep and not a.from_areadata else None)
    if ground_map:
        sp = with_ground(sp, ground_map, keep=a.ground_keep, margin_m=a.ground_margin,
                         within_m=(a.relief_radius - 8.0) if a.relief_radius else None)
    if a.relief_radius:
        src = a.ground_from or a.locate_on or a.map_dir
        if not src:
            ap.error("--relief-radius needs a map: --ground-from, --locate-on or MAP_DIR")
        sp = with_relief(sp, src, a.relief_radius)
    if a.rotate:
        sp = sp.rotated(a.rotate)
    sp.water_cm = a.water_cm
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
    if sp.ground is not None:
        print("# ground: %d tiles of %s" % (len(sp.ground.cells()),
                                          ", ".join(t.rsplit("/", 1)[-1] for t in sp.ground.palette)))
    if sp.relief is not None:
        flat = [v for row in sp.relief.rows for v in row]
        print("# relief: %d x %d vertices, %+d .. %+d cm about the base, radius %g m"
              % (len(sp.relief.rows[0]), len(sp.relief.rows), min(flat), max(flat),
                 sp.relief.radius_m))
    if a.save:
        print("# saved", sp.save(a.save))
    return 0


if __name__ == "__main__":       # pragma: no cover
    raise SystemExit(main())

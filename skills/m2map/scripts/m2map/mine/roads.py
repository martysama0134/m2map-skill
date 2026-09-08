"""Road / path grammar miner.

Ymir's terrain art has **no** texture called road, path or trail: the whole
``d:/ymir work/terrainmaps`` vocabulary is field / grass / stone / tile / sand
/ beach / snow / valcano / cliff / river / lava / ice / rock.  Roads are
painted *with* the bare-earth ("field 0N.dds") and paved ("tile0N.dds")
families over whatever the map's base layer is, so a path-role texture can
only be identified by **shape**, with the name as a weak prior.

Pipeline (all on the stitched 1-tile = 1 m grid from :mod:`tile_stats`)
----------------------------------------------------------------------
1. **De-dither.** Ymir splats blend two textures by stippling single tiles of
   one into the other, so a raw index mask is a solid core plus a noisy
   fringe.  ``open(3x3)`` deletes the fringe, ``close(3x3)`` refills pinholes,
   then components under ``MIN_CORE_COMPONENT`` tiles go.  The retained
   fraction (``solid_retention``) is itself a strong signal: palette slots
   used *only* as dither noise retain <5 % of their tiles.
2. **Medial axis.** Zhang-Suen thinning of the core (spurs under
   ``SPUR_PRUNE_M`` pruned, redundant diagonal links dropped so the node
   degrees are topological).  Corridor width is measured by walking the
   perpendicular and counting core tiles -- exact; the distance-transform
   estimate ``2*D - 1`` is kept alongside as ``*_dt_*`` but reads one metre
   low on even widths.
3. **Classify.** An index is path-role when its core survives de-dithering,
   its median corridor width is inside ``PATH_WIDTH_RANGE`` and its medial
   axis is long relative to its area (``aspect = L^2 / area``).
4. **Measure.** Branch decomposition of the skeleton graph gives centrelines;
   from those come width, tortuosity, turning rate, junction degree/angles,
   and plaza blobs.  Edge treatment comes from ring histograms outward from
   the core; terrain and attr relations from the stitched ``height.raw``
   slope grid and ``attr.atr`` flag grid.

CLI
---
``python -m m2map.mine.roads [--maps <CORPUS>] [--out roads.json]``
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import pathlib
import sys

import numpy as np

try:
    import cv2
except ImportError:                                    # pragma: no cover
    cv2 = None

from ..codec.attr import (ATTR_BANPK, ATTR_BLOCK, ATTR_OBJECT, ATTR_WATER,
                          AttrMap)
from ..codec.height import HeightMap, slope_degrees
from ..codec.tile import TILE_SCALE
from .tile_stats import (DEFAULT_MAPS_DIR, DEFAULT_PACK_DIR, SECTOR_TILES,
                         MapTiles, load_archetypes, load_map, texture_role)

__all__ = [
    "MIN_CORE_COMPONENT", "PATH_WIDTH_RANGE", "PATH_ROLE_PRIOR",
    "MIN_RIBBON_FRACTION", "SPUR_PRUNE_M",
    "thin", "denoise_core", "skeleton_graph", "rdp", "polyline_metrics",
    "transect_widths", "smooth_polyline",
    "index_shape_stats", "classify_path_indices", "road_network", "prune_spurs",
    "edge_profile", "terrain_relation", "attr_relation", "map_roads",
    "road_verdict", "texture_vocabulary", "main",
]

# --- tuning constants, each justified by a measurement in roads.json --------
#: cores smaller than this are dither residue, not geometry (tiles = m^2)
MIN_CORE_COMPONENT = 30
#: minimum tiles of raw coverage before an index is worth thinning
MIN_INDEX_AREA = 400
#: a corridor wider than this is a region, not a road (tiles = metres)
PATH_WIDTH_RANGE = (2.0, 16.0)
#: medial-axis length^2 / core area; a square blob scores ~1, a corridor L/w
MIN_PATH_ASPECT = 10.0
#: share of the de-dithered core that must lie within 3 m of its own edge.
#: Measured separation on the empire capitals (see roads.json
#: ``index_shape_stats``): road textures 0.67-0.88, terrain patches 0.14-0.54.
MIN_RIBBON_FRACTION = 0.60
#: branches shorter than this that dead-end are thinning spurs, not roads
SPUR_PRUNE_M = 10
#: an index covering more than this share of the painted map is the ground
MAX_PATH_COVERAGE = 0.40
#: de-dithered core must keep at least this share of the raw index
MIN_SOLID_RETENTION = 0.25
#: name families that can plausibly carry a road (weak prior, not a filter)
PATH_ROLE_PRIOR = ("dirt", "paved", "sand", "rock")
#: branches shorter than this are skeleton hair, not road
MIN_BRANCH_LEN = 6
#: how far outward the edge-treatment rings are sampled (tiles)
EDGE_RINGS = 14
#: control band for terrain / attr comparisons (tiles from the core)
CONTROL_BAND = (6, 24)

_K3 = np.ones((3, 3), np.uint8)


# --------------------------------------------------------------------------
# morphology / skeleton primitives
# --------------------------------------------------------------------------
def thin(mask):
    """Zhang-Suen thinning -> 1-tile-wide 8-connected medial axis.

    Vectorised over the mask's bounding box; converges in ~max-half-width
    iterations.
    """
    img = np.asarray(mask, np.uint8)
    ys, xs = np.nonzero(img)
    if len(ys) == 0:
        return np.zeros(img.shape, bool)
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()) + 1, int(xs.min()), int(xs.max()) + 1
    sub = np.pad(img[y0:y1, x0:x1], 1)
    while True:
        removed = 0
        for step in (0, 1):
            P = np.pad(sub, 1)
            p2, p3, p4 = P[0:-2, 1:-1], P[0:-2, 2:], P[1:-1, 2:]
            p5, p6, p7 = P[2:, 2:], P[2:, 1:-1], P[2:, 0:-2]
            p8, p9 = P[1:-1, 0:-2], P[0:-2, 0:-2]
            B = (p2.astype(np.int16) + p3 + p4 + p5 + p6 + p7 + p8 + p9)
            seq = (p2, p3, p4, p5, p6, p7, p8, p9, p2)
            A = np.zeros(sub.shape, np.int16)
            for k in range(8):
                A += ((seq[k] == 0) & (seq[k + 1] == 1))
            if step == 0:
                cond = ((p2 * p4 * p6) == 0) & ((p4 * p6 * p8) == 0)
            else:
                cond = ((p2 * p4 * p8) == 0) & ((p2 * p6 * p8) == 0)
            m = (sub == 1) & (B >= 2) & (B <= 6) & (A == 1) & cond
            n = int(m.sum())
            if n:
                sub[m] = 0
                removed += n
        if removed == 0:
            break
    out = np.zeros(img.shape, bool)
    out[y0:y1, x0:x1] = sub[1:-1, 1:-1].astype(bool)
    return out


def denoise_core(mask, min_component=MIN_CORE_COMPONENT):
    """Strip the splat dither fringe: open(3x3) -> close(3x3) -> drop crumbs."""
    m = np.asarray(mask, np.uint8)
    c = cv2.morphologyEx(m, cv2.MORPH_OPEN, _K3)
    c = cv2.morphologyEx(c, cv2.MORPH_CLOSE, _K3)
    n, lab, st, _ = cv2.connectedComponentsWithStats(c, connectivity=8)
    keep = np.zeros(n, bool)
    if n > 1:
        keep[1:] = st[1:, cv2.CC_STAT_AREA] >= min_component
    return keep[lab]


def distance_transform(mask):
    """L2 distance to the nearest background tile (padded, so edges are real)."""
    return cv2.distanceTransform(
        np.pad(np.asarray(mask, np.uint8), 1), cv2.DIST_L2, 5)[1:-1, 1:-1]


_N8 = ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1))


def skeleton_graph(skel, min_branch=MIN_BRANCH_LEN):
    """Decompose an 8-connected skeleton into nodes and branch polylines.

    Returns ``(nodes, branches)`` where ``nodes`` maps ``(x, y)`` -> degree for
    every endpoint (deg 1) and junction (deg >= 3), and each branch is a dict
    with ``points`` (list of ``(x, y)``), ``ends`` and ``closed``.
    """
    pts = set(zip(*np.nonzero(skel)[::-1]))            # (x, y)
    nb = {}
    for (x, y) in pts:
        n = [(x + dx, y + dy) for dx, dy in _N8 if (x + dx, y + dy) in pts]
        # Drop redundant diagonal links.  A Zhang-Suen skeleton is 8-thin but
        # not 8-*simple*: on a diagonal staircase a plain 8-neighbour count
        # reports degree 3 for ordinary line pixels, which manufactured 3,630
        # phantom junctions on metin2_map_a1 alone.  A diagonal neighbour that
        # is itself 4-adjacent to one of this pixel's 4-neighbours carries no
        # topology, so it is removed and the remaining count is the real degree.
        orth = [q for q in n if abs(q[0] - x) + abs(q[1] - y) == 1]
        n = [q for q in n
             if abs(q[0] - x) + abs(q[1] - y) == 1
             or not any(abs(q[0] - r[0]) + abs(q[1] - r[1]) == 1 for r in orth)]
        nb[(x, y)] = n
    nodes = {p: len(n) for p, n in nb.items() if len(n) != 2}
    branches = []
    seen_edge = set()

    def walk(start, first):
        path = [start, first]
        seen_edge.add((start, first))
        seen_edge.add((first, start))
        cur, prev = first, start
        while cur not in nodes:
            nxt = [q for q in nb[cur] if q != prev]
            if not nxt:
                break
            # prefer 4-neighbours so diagonal shortcuts don't zigzag
            nxt.sort(key=lambda q: (abs(q[0] - cur[0]) + abs(q[1] - cur[1])))
            q = nxt[0]
            if (cur, q) in seen_edge:
                break
            seen_edge.add((cur, q))
            seen_edge.add((q, cur))
            path.append(q)
            prev, cur = cur, q
        return path

    for p in nodes:
        for q in nb[p]:
            if (p, q) in seen_edge:
                continue
            path = walk(p, q)
            if len(path) >= 2:
                branches.append(path)
    # isolated cycles carry no node -- seed one arbitrarily
    for p in pts:
        if p in nodes:
            continue
        if any((p, q) in seen_edge for q in nb[p]):
            continue
        if not nb[p]:
            continue
        path = walk(p, nb[p][0])
        if len(path) >= 2:
            branches.append(path)
    out = []
    for path in branches:
        if len(path) < min_branch:
            continue
        out.append({"points": path,
                    "ends": (path[0], path[-1]),
                    "closed": path[0] == path[-1]})
    return nodes, out


def prune_spurs(skel, min_len=SPUR_PRUNE_M, rounds=4):
    """Delete dead-end twigs shorter than ``min_len``.

    Thinning any non-convex blob sprouts short hairs off the medial axis; left
    in, they dominate the node-degree histogram (metin2_map_a1 reported 9,302
    "junctions" before pruning, 244 after) and inflate the junction density by
    two orders of magnitude.  Only branches with a degree-1 end are cut, so
    real T/Y/X topology survives.
    """
    sk = np.asarray(skel, bool).copy()
    for _ in range(rounds):
        nodes, branches = skeleton_graph(sk, min_branch=0)
        drop = []
        for b in branches:
            a, z = b["ends"]
            if b["closed"]:
                continue
            deg_a, deg_z = nodes.get(a, 2), nodes.get(z, 2)
            if 1 in (deg_a, deg_z) and arc_length(b["points"]) < min_len:
                keep_ends = {p for p, d in ((a, deg_a), (z, deg_z)) if d >= 3}
                drop += [p for p in b["points"] if p not in keep_ends]
        if not drop:
            break
        for (x, y) in drop:
            sk[y, x] = False
    return sk


def arc_length(points):
    a = np.asarray(points, float)
    if len(a) < 2:
        return 0.0
    d = np.diff(a, axis=0)
    return float(np.hypot(d[:, 0], d[:, 1]).sum())


def rdp(points, eps=1.5):
    """Ramer-Douglas-Peucker simplification (iterative, no recursion limit)."""
    pts = np.asarray(points, float)
    if len(pts) < 3:
        return [tuple(p) for p in pts]
    keep = np.zeros(len(pts), bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        a, b = pts[i], pts[j]
        ab = b - a
        L = math.hypot(*ab)
        seg = pts[i + 1:j] - a
        if L < 1e-9:
            d = np.hypot(seg[:, 0], seg[:, 1])
        else:
            d = np.abs(seg[:, 0] * ab[1] - seg[:, 1] * ab[0]) / L
        k = int(np.argmax(d))
        if d[k] > eps:
            keep[i + 1 + k] = True
            stack.append((i, i + 1 + k))
            stack.append((i + 1 + k, j))
    return [tuple(p) for p in pts[keep]]


def resample(points, step=4.0):
    """Uniform arc-length resample; needed before any angle measurement."""
    a = np.asarray(points, float)
    if len(a) < 2:
        return a
    d = np.hypot(*np.diff(a, axis=0).T)
    s = np.concatenate([[0.0], np.cumsum(d)])
    if s[-1] < step:
        return np.array([a[0], a[-1]])
    t = np.arange(0.0, s[-1] + 1e-9, step)
    return np.stack([np.interp(t, s, a[:, 0]), np.interp(t, s, a[:, 1])], 1)


def smooth_polyline(points, sigma=3.0):
    """Gaussian blur along arc length.

    A tile-quantised centreline staircases by +/-1 m, which alone reads as
    ~14 deg of turning per 4 m step.  Blurring with sigma = 3 m removes the
    quantisation without touching arcs of the radius roads actually use
    (tens of metres).
    """
    a = np.asarray(points, float)
    if len(a) < 5:
        return a
    r = int(max(2, round(3 * sigma)))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    pad = np.concatenate([np.repeat(a[:1], r, 0), a, np.repeat(a[-1:], r, 0)])
    return np.stack([np.convolve(pad[:, i], k, "valid") for i in (0, 1)], 1)


def polyline_metrics(points, step=4.0, straight_tol=1.0, straight_min=20.0):
    """Shape of one centreline.

    ``tortuosity`` = arc length / end-to-end distance (1.0 = dead straight).
    ``turn_deg_per_10m`` = total |heading change| per 10 m of arc, measured on a
    sigma=3 m smoothed, 4 m resampled copy so tile staircasing cannot inflate
    it.  ``radius_of_curvature_m`` is the equivalent circular-arc radius.
    ``straight_fraction`` = share of arc length covered by maximal runs whose
    deviation from their own chord stays under ``straight_tol`` tiles over at
    least ``straight_min`` tiles.
    """
    L = arc_length(points)
    a = np.asarray(points, float)
    chord = float(np.hypot(*(a[-1] - a[0]))) if len(a) > 1 else 0.0
    r = resample(smooth_polyline(points), step)
    turn = 0.0
    angles = []
    if len(r) >= 3:
        v = np.diff(r, axis=0)
        h = np.arctan2(v[:, 1], v[:, 0])
        dh = np.diff(h)
        dh = (dh + np.pi) % (2 * np.pi) - np.pi
        angles = np.degrees(np.abs(dh))
        turn = float(angles.sum())
    # longest straight runs
    straight = 0.0
    i = 0
    n = len(r)
    while i < n - 1:
        j = i + 1
        best = i + 1
        while j < n:
            seg = r[i:j + 1]
            ab = seg[-1] - seg[0]
            Ls = math.hypot(*ab)
            if Ls < 1e-9:
                j += 1
                continue
            d = np.abs((seg[:, 0] - seg[0, 0]) * ab[1] -
                       (seg[:, 1] - seg[0, 1]) * ab[0]) / Ls
            if d.max() > straight_tol:
                break
            best = j
            j += 1
        run = arc_length(r[i:best + 1])
        if run >= straight_min:
            straight += run
            i = best
        else:
            i += 1
    return {
        "length_m": round(L, 2),
        "chord_m": round(chord, 2),
        "tortuosity": round(L / chord, 4) if chord > 1e-6 else None,
        "total_turn_deg": round(turn, 2),
        "turn_deg_per_10m": round(10.0 * turn / L, 3) if L > 0 else 0.0,
        "max_turn_deg_per_step": round(float(np.max(angles)), 2) if len(angles) else 0.0,
        "radius_of_curvature_m": (round(L / math.radians(turn), 2)
                                  if turn > 1e-6 and L > 0 else None),
        "straight_fraction": round(straight / L, 4) if L > 0 else 0.0,
    }


# --------------------------------------------------------------------------
# per-index shape statistics + path classification
# --------------------------------------------------------------------------
def index_shape_stats(mt: MapTiles, index):
    raw = (mt.grid == index) & mt.valid
    area = int(raw.sum())
    fn = mt.slot_name(index)
    rec = {"index": index, "texture": fn,
           "role": texture_role(fn) if fn else "unresolved",
           "raw_tiles": area,
           "coverage": area / int(mt.valid.sum()) if mt.valid.any() else 0.0}
    if area < MIN_INDEX_AREA:
        rec.update(core_tiles=0, solid_retention=0.0, skeleton_m=0,
                   width_median_m=None, aspect=0.0, verdict="too_small")
        return rec
    core = denoise_core(raw)
    ct = int(core.sum())
    rec["core_tiles"] = ct
    rec["solid_retention"] = round(ct / area, 4)
    if ct < MIN_CORE_COMPONENT * 4:
        rec.update(skeleton_m=0, width_median_m=None, aspect=0.0,
                   verdict="dither_only")
        return rec
    dt = distance_transform(core)
    sk = thin(core)
    L = int(sk.sum())
    if L == 0:
        # Zhang-Suen deletes both sub-fields of a 2x2 block simultaneously, so
        # a core made only of tiny squares thins to nothing.
        rec.update(skeleton_m=0, width_median_m=None, aspect=0.0,
                   verdict="no_medial_axis")
        return rec
    w = 2.0 * dt[sk] - 1.0
    rec.update({
        "skeleton_m": L,
        "width_median_m": round(float(np.median(w)), 2),
        "width_p25_m": round(float(np.quantile(w, 0.25)), 2),
        "width_p75_m": round(float(np.quantile(w, 0.75)), 2),
        "width_p95_m": round(float(np.quantile(w, 0.95)), 2),
        "width_iqr_over_median": round(
            float((np.quantile(w, 0.75) - np.quantile(w, 0.25)) /
                  max(np.median(w), 1e-6)), 3),
        "aspect": round(L * L / ct, 1),
        # share of the solid core lying within 3 m of its own edge, i.e. the
        # part that fits inside a <=7 m ribbon.  This is the measurement that
        # separates a road from a terrain patch: in metin2_map_a1 the road
        # texture (field 01) scores 0.67 and field 04 0.88, while the blobby
        # stone01 patches score 0.54 and beach sand 01 scores 0.14.
        "ribbon_fraction": round(float((dt[core] <= 3.0).mean()), 4),
        "ribbon_fraction_4m": round(float((dt[core] <= 4.0).mean()), 4),
        "core_area_per_skeleton_m": round(ct / max(L, 1), 3),
        "components": int(cv2.connectedComponentsWithStats(
            core.astype(np.uint8), connectivity=8)[0] - 1),
    })
    return rec


def classify_path_indices(mt: MapTiles, stats=None):
    """Which palette slots carry roads, by measured shape + name prior."""
    stats = stats if stats is not None else [
        index_shape_stats(mt, i) for i in mt.used_indices()]
    lo, hi = PATH_WIDTH_RANGE
    base = max(stats, key=lambda s: s["raw_tiles"])["index"] if stats else None
    for s in stats:
        if s.get("verdict"):
            s["is_path"] = False
            continue
        reasons = []
        if s["index"] == base:
            reasons.append("is the base layer")
        if s["coverage"] > MAX_PATH_COVERAGE:
            reasons.append("coverage %.2f > %.2f" % (s["coverage"], MAX_PATH_COVERAGE))
        if s["solid_retention"] < MIN_SOLID_RETENTION:
            reasons.append("solid_retention %.2f < %.2f"
                           % (s["solid_retention"], MIN_SOLID_RETENTION))
        if not (lo <= s["width_median_m"] <= hi):
            reasons.append("median width %.1f outside %s"
                           % (s["width_median_m"], list(PATH_WIDTH_RANGE)))
        if s["aspect"] < MIN_PATH_ASPECT:
            reasons.append("aspect %.0f < %.0f" % (s["aspect"], MIN_PATH_ASPECT))
        if s["ribbon_fraction"] < MIN_RIBBON_FRACTION:
            reasons.append("ribbon_fraction %.2f < %.2f"
                           % (s["ribbon_fraction"], MIN_RIBBON_FRACTION))
        if s["role"] not in PATH_ROLE_PRIOR:
            reasons.append("art family %r is never a road surface" % s["role"])
        s["is_path"] = not reasons
        s["rejected_because"] = reasons
        s["name_prior"] = s["role"] in PATH_ROLE_PRIOR
    return stats


# --------------------------------------------------------------------------
# network measurement
# --------------------------------------------------------------------------
def _direction_at(points, node, span=8.0):
    """Unit direction leaving ``node`` along ``points`` (degrees, y-down)."""
    pts = points if points[0] == node else points[::-1]
    a = np.asarray(pts, float)
    d = np.hypot(*np.diff(a, axis=0).T)
    s = np.concatenate([[0.0], np.cumsum(d)])
    k = int(np.searchsorted(s, min(span, s[-1])))
    k = max(1, min(k, len(a) - 1))
    v = a[k] - a[0]
    return math.degrees(math.atan2(v[1], v[0])) % 360.0


def _classify_junction(angles):
    """T / Y / X / star from the directions of the incident branches."""
    n = len(angles)
    if n < 3:
        return "endpoint" if n <= 1 else "through"
    a = sorted(angles)
    gaps = [(a[(i + 1) % n] - a[i]) % 360.0 for i in range(n)]
    if n == 3:
        # T: one pair is near-collinear (gap ~180); Y: gaps all near 120
        if max(gaps) > 150.0:
            return "T"
        return "Y"
    if n == 4:
        if max(gaps) < 120.0 and min(gaps) > 60.0:
            return "X"
        return "X_skew"
    return "star%d" % n


def transect_widths(core, points, step=5, max_half=80, dt=None):
    """Exact corridor width in metres, measured across the centreline.

    ``2*distanceTransform - 1`` is quantised: a W-metre ribbon reads W when W
    is odd but W-1 when it is even (verified on synthetic ribbons W=2..12),
    which is why the naive corpus histogram piles up on 3/5/7/9.  Walking the
    chord and counting the distinct core tiles it crosses has no such bias.

    The chord is taken as the **minimum** over five directions spanning
    +/-20 deg around the estimated normal, because a tile-quantised tangent can
    be several degrees off and a near-tangential chord reports a road as
    hundreds of metres wide.  The tangent itself comes from a smoothed copy of
    the centreline over a +/-4-sample baseline.
    """
    a = np.asarray(points, float)
    if len(a) < 10:
        return []
    sm = smooth_polyline(points, sigma=2.0)
    H, W = core.shape
    rots = [math.radians(d) for d in (-20, -10, 0, 10, 20)]
    out = []
    for k in range(4, len(a) - 4, step):
        t = sm[k + 4] - sm[k - 4]
        L = math.hypot(*t)
        if L < 1e-6:
            continue
        t /= L
        cx, cy = a[k]
        # the inscribed radius bounds the search: a chord through a point can
        # not be much longer than 4x it without leaving the corridor, and
        # letting the walk run to max_half everywhere is what makes this the
        # slow step of the whole miner.
        limit = max_half if dt is None else min(
            max_half, max(6.0, 4.0 * float(dt[int(cy), int(cx)])))
        best = None
        for r in rots:
            nx = -t[1] * math.cos(r) - t[0] * math.sin(r)
            ny = t[0] * math.cos(r) - t[1] * math.sin(r)
            w = 1
            ok = True
            for sgn in (1, -1):
                seen = {(int(cx), int(cy))}
                d = 0.25
                while d <= limit:
                    x, y = int(round(cx + nx * sgn * d)), int(round(cy + ny * sgn * d))
                    if not (0 <= x < W and 0 <= y < H):
                        ok = False
                        break
                    if (x, y) not in seen:
                        if not core[y, x]:
                            break
                        seen.add((x, y))
                        w += 1
                    d += 0.25
                else:
                    ok = False                 # ran past the search limit
                if not ok:
                    break
            if ok and (best is None or w < best):
                best = w
        if best is not None:
            out.append(best)
    return out


def road_network(mt: MapTiles, path_indices):
    """Core mask, medial axis, branch geometry and junction topology."""
    raw = np.isin(mt.grid, list(path_indices)) & mt.valid
    core = denoise_core(raw)
    dt = distance_transform(core)
    sk_raw = thin(core)
    sk = prune_spurs(sk_raw)
    nodes, branches = skeleton_graph(sk)

    seg = []
    for b in branches:
        pts = b["points"]
        w = np.array([2.0 * dt[y, x] - 1.0 for (x, y) in pts])
        met = polyline_metrics(pts)
        tw = transect_widths(core, pts, dt=dt)
        seg.append({
            "transect_widths_m": tw,
            "width_transect_median_m": float(np.median(tw)) if tw else None,
            "points": pts,
            "length_m": met["length_m"],
            "metrics": met,
            "width_median_m": float(np.median(w)),
            "width_p10_m": float(np.quantile(w, 0.10)),
            "width_p90_m": float(np.quantile(w, 0.90)),
            "width_cv": float(np.std(w) / max(np.mean(w), 1e-6)),
            "closed": b["closed"],
            "ends": b["ends"],
        })

    wid = np.array([s["width_median_m"] for s in seg]) if seg else np.array([0.0])
    lens = np.array([s["length_m"] for s in seg]) if seg else np.array([1.0])
    med_w = float(np.median(np.repeat(wid, np.maximum(lens.astype(int), 1)))) if seg else 0.0

    # --- junction classification ------------------------------------------
    # A medial axis never produces a 4-way node: thinning splits a crossroads
    # into two 3-way nodes a road-width apart (that is why metin2_map_a1 first
    # reported 148 T/Y nodes and zero X).  Junction nodes closer together than
    # ``merge_r`` are therefore clustered and the cluster's *external* arms are
    # what gets classified.
    merge_r = max(6.0, 1.5 * med_w)
    jnodes = sorted({e for s in seg for e in set(s["ends"])
                     if nodes.get(e, 0) >= 3})
    par = {p: p for p in jnodes}

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    for i, p in enumerate(jnodes):
        for q in jnodes[i + 1:]:
            if q[0] - p[0] > merge_r:
                break
            if math.hypot(q[0] - p[0], q[1] - p[1]) <= merge_r:
                ra, rb = find(p), find(q)
                if ra != rb:
                    par[ra] = rb
    clusters = collections.defaultdict(set)
    for p in jnodes:
        clusters[find(p)].add(p)

    jtypes = collections.Counter()
    jrecords = []
    for members in clusters.values():
        arms = []
        for s in seg:
            a, z = s["ends"]
            ina, inz = a in members, z in members
            if ina == inz:
                continue                    # internal connector or unrelated
            arms.append((s, a if ina else z))
        if len(arms) < 3:
            continue
        angles = [_direction_at(s["points"], node) for s, node in arms]
        kind = _classify_junction(angles)
        jtypes[kind] += 1
        cx = int(round(sum(p[0] for p in members) / len(members)))
        cy = int(round(sum(p[1] for p in members) / len(members)))
        jrecords.append({"tile": [cx, cy], "degree": len(arms), "kind": kind,
                         "merged_nodes": len(members),
                         "angles_deg": [round(a, 1) for a in angles],
                         "arm_widths_m": [round(s["width_median_m"], 1)
                                          for s, _ in arms]})

    # plazas: blobs whose inscribed radius far exceeds the road half-width
    plaza_thr = max(2.0 * med_w, med_w + 6.0)
    plaza_mask = core & (dt * 2.0 - 1.0 >= plaza_thr)
    plazas = []
    if plaza_mask.any():
        n, lab, st, cen = cv2.connectedComponentsWithStats(
            plaza_mask.astype(np.uint8), connectivity=8)
        for k in range(1, n):
            a = int(st[k, cv2.CC_STAT_AREA])
            if a < 40:
                continue
            plazas.append({
                "tile": [int(round(cen[k][0])), int(round(cen[k][1]))],
                "area_m2": a,
                "bbox_m": [int(st[k, cv2.CC_STAT_WIDTH]), int(st[k, cv2.CC_STAT_HEIGHT])],
                "max_inscribed_width_m": round(
                    float(2 * dt[lab == k].max() - 1), 1),
            })
        plazas.sort(key=lambda p: -p["area_m2"])
    # graph invariants over the pruned skeleton, restricted to accepted
    # segments: V = distinct segment ends, E = segments, C = components
    ends = {}
    for si, s in enumerate(seg):
        for e in set(s["ends"]):
            ends.setdefault(e, []).append(si)
    parent = list(range(len(seg)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for e, sids in ends.items():
        for b in sids[1:]:
            ra, rb = find(sids[0]), find(b)
            if ra != rb:
                parent[ra] = rb
    comps = len({find(i) for i in range(len(seg))}) if seg else 0
    cycles = len(seg) - len(ends) + comps
    return {"raw": raw, "core": core, "dt": dt, "skel": sk, "skel_raw": sk_raw,
            "nodes": nodes, "segments": seg, "junction_types": jtypes,
            "junctions": jrecords, "median_width_m": med_w,
            "plaza_threshold_m": plaza_thr, "plazas": plazas,
            "junction_merge_radius_m": merge_r,
            "graph": {"vertices": len(ends), "edges": len(seg),
                      "components": comps, "cycles": cycles}}


def edge_profile(mt: MapTiles, net, path_indices, rings=EDGE_RINGS):
    """What sits beside a road: dither fringe, transition texture, or nothing.

    Ring ``r`` is the set of tiles at chessboard distance ``r`` outside the
    de-dithered core.  ``path_share`` there is the leftover splat stipple of
    the road texture, so the ring where it decays below 10 % is the measured
    blend-band width.
    """
    core = net["core"]
    out = ~core & mt.valid
    dout = cv2.distanceTransform(np.pad((~core).astype(np.uint8), 1),
                                 cv2.DIST_C, 3)[1:-1, 1:-1]
    pidx = set(path_indices)
    far = out & (dout >= rings) & (dout < rings + 20)
    far_hist = collections.Counter(mt.grid[far].tolist()) if far.any() else collections.Counter()
    far_tot = sum(far_hist.values()) or 1
    prof = []
    band = None
    for r in range(1, rings + 1):
        ring = out & (dout == r)
        tot = int(ring.sum())
        if tot == 0:
            prof.append({"ring_m": r, "tiles": 0})
            continue
        hist = collections.Counter(mt.grid[ring].tolist())
        pshare = sum(v for k, v in hist.items() if k in pidx) / tot
        top = [{"index": int(k), "texture": mt.slot_name(int(k)),
                "share": round(v / tot, 4),
                "enrichment": round((v / tot) / max(far_hist.get(k, 0) / far_tot, 1e-6), 2)}
               for k, v in hist.most_common(3)]
        prof.append({"ring_m": r, "tiles": tot,
                     "path_share": round(pshare, 4), "top": top})
        if band is None and pshare < 0.10:
            band = r - 1
    # transition textures: enriched at r<=3 vs the far field
    near = out & (dout >= 1) & (dout <= 3)
    near_hist = collections.Counter(mt.grid[near].tolist()) if near.any() else collections.Counter()
    near_tot = sum(near_hist.values()) or 1
    trans = []
    for k, v in near_hist.most_common(6):
        if k in pidx or v < 50:
            continue
        e = (v / near_tot) / max(far_hist.get(k, 0) / far_tot, 1e-6)
        trans.append({"index": int(k), "texture": mt.slot_name(int(k)),
                      "near_share": round(v / near_tot, 4),
                      "far_share": round(far_hist.get(k, 0) / far_tot, 4),
                      "enrichment": round(e, 2)})
    trans.sort(key=lambda t: -t["enrichment"])
    return {
        "rings": prof,
        "blend_band_m": band if band is not None else rings,
        "ring1_path_share": prof[0].get("path_share") if prof else None,
        "hard_edge": bool(prof and (prof[0].get("path_share") or 0) < 0.15),
        "transition_candidates": trans[:4],
        "far_field_top": [{"index": int(k), "texture": mt.slot_name(int(k)),
                           "share": round(v / far_tot, 4)}
                          for k, v in far_hist.most_common(3)],
    }


# --------------------------------------------------------------------------
# stitched height / attr layers
# --------------------------------------------------------------------------
def stitch_slope(mt: MapTiles):
    """(rows*128, cols*128) per-cell slope in degrees; NaN where absent.

    One terrain cell = 2 tiles, so cell ``(cx, cy)`` covers tiles
    ``(2cx..2cx+1, 2cy..2cy+1)``.
    """
    rows, cols = mt.sector_shape
    hs = mt.setting.height_scale if mt.setting else 0.5
    slope = np.full((rows * 128, cols * 128), np.nan, np.float32)
    height = np.full((rows * 128, cols * 128), np.nan, np.float32)
    for sec in mt.sectors:
        sx, sy = sec
        f = mt.path / ("%03d%03d" % (sx, sy)) / "height.raw"
        if not f.exists():
            continue
        hm = HeightMap.from_bytes(f.read_bytes())
        v = hm.vertices
        slope[sy * 128:(sy + 1) * 128, sx * 128:(sx + 1) * 128] = \
            slope_degrees(v, hs)
        height[sy * 128:(sy + 1) * 128, sx * 128:(sx + 1) * 128] = \
            v[:-1, :-1].astype(np.float32) * hs
    return slope, height


def stitch_attr(mt: MapTiles):
    """(rows*256, cols*256) attribute bytes -- 1 attr cell = 1 tile."""
    rows, cols = mt.sector_shape
    a = np.zeros((rows * SECTOR_TILES, cols * SECTOR_TILES), np.uint8)
    ok = np.zeros(a.shape, bool)
    for sx, sy in mt.sectors:
        f = mt.path / ("%03d%03d" % (sx, sy)) / "attr.atr"
        if not f.exists():
            continue
        try:
            am = AttrMap.from_bytes(f.read_bytes())
        except ValueError:
            continue
        a[sy * 256:(sy + 1) * 256, sx * 256:(sx + 1) * 256] = am.cells
        ok[sy * 256:(sy + 1) * 256, sx * 256:(sx + 1) * 256] = True
    return a, ok


def _cell_mask(tile_mask):
    """256-tile grid -> 128-cell grid; a cell is road if >=2 of its 4 tiles are."""
    h, w = tile_mask.shape
    m = tile_mask[:h // 2 * 2, :w // 2 * 2].reshape(h // 2, 2, w // 2, 2)
    return m.sum(axis=(1, 3)) >= 2


def terrain_relation(mt: MapTiles, net, band=CONTROL_BAND, samples=4000):
    """Slope / roughness inside the corridor vs a control ring, plus the mean
    perpendicular cross-section of the corridor."""
    slope, height = stitch_slope(mt)
    if np.isnan(slope).all():
        return {"reason": "no height.raw"}
    core = net["core"]
    dout = cv2.distanceTransform(np.pad((~core).astype(np.uint8), 1),
                                 cv2.DIST_C, 3)[1:-1, 1:-1]
    inside = _cell_mask(core)
    ctrl = _cell_mask((dout >= band[0]) & (dout <= band[1]) & mt.valid)
    sl = slope[:inside.shape[0], :inside.shape[1]]
    ok = ~np.isnan(sl)

    def st(m):
        v = sl[m & ok]
        if v.size == 0:
            return None
        return {"n_cells": int(v.size),
                "slope_mean_deg": round(float(v.mean()), 3),
                "slope_median_deg": round(float(np.median(v)), 3),
                "slope_p90_deg": round(float(np.quantile(v, 0.9)), 3),
                "steep_gt10deg_fraction": round(float((v > 10).mean()), 4)}

    a, b = st(inside), st(ctrl)
    # Perpendicular cross-section.  Branch traversal direction is arbitrary, so
    # the raw signed profile has no meaning; every transect is folded about the
    # centreline (``symmetric_dz``) to answer "is the corridor a cut/fill?",
    # and the unfolded left-right difference is kept as a magnitude
    # (``cross_slope``) to answer "do roads run along hillsides?".
    prof = None
    segs = [s for s in net["segments"] if s["length_m"] >= 40]
    if segs and not np.isnan(height).all():
        H, W = height.shape
        offs = np.arange(0, 15)
        acc = np.zeros(len(offs))
        cnt = np.zeros(len(offs))
        cross = []
        step = max(1, (sum(len(s["points"]) for s in segs) // samples) or 1)
        for s in segs:
            p = np.asarray(s["points"], float)
            for k in range(2, len(p) - 2, step):
                t = p[k + 2] - p[k - 2]
                nrm = np.array([-t[1], t[0]])
                L = math.hypot(*nrm)
                if L < 1e-6:
                    continue
                nrm /= L
                cx0, cy0 = p[k] / 2.0        # tile -> cell

                def sample(o):
                    cx = int(round(cx0 + nrm[0] * o / 2.0))
                    cy = int(round(cy0 + nrm[1] * o / 2.0))
                    if not (0 <= cx < W and 0 <= cy < H):
                        return None
                    z = height[cy, cx]
                    return None if np.isnan(z) else float(z)

                z0 = sample(0)
                if z0 is None:
                    continue
                for oi, o in enumerate(offs):
                    zp, zm = sample(int(o)), sample(-int(o))
                    both = [z for z in (zp, zm) if z is not None]
                    if not both:
                        continue
                    acc[oi] += sum(z - z0 for z in both) / len(both)
                    cnt[oi] += 1
                za, zb = sample(8), sample(-8)
                if za is not None and zb is not None:
                    cross.append(abs(za - zb))
        good = cnt > 20
        if good.any():
            prof = {
                "offset_m": [int(o) for o in offs[good]],
                "symmetric_mean_dz_cm": [round(float(v), 2)
                                         for v in (acc[good] / cnt[good])],
                "samples": int(cnt.max()),
                "cross_slope_dz_over_16m_cm": (
                    {"median": round(float(np.median(cross)), 1),
                     "p90": round(float(np.quantile(cross, 0.9)), 1),
                     "n": len(cross)} if cross else None),
                "reading": "positive symmetric_mean_dz means the ground rises "
                           "away from the centreline -- the corridor sits in a "
                           "cut; ~0 means the road is painted on unmodified "
                           "terrain",
            }
    return {
        "inside_corridor": a,
        "control_band_m": list(band),
        "control": b,
        "slope_ratio_inside_over_control": (
            round(a["slope_mean_deg"] / b["slope_mean_deg"], 4)
            if a and b and b["slope_mean_deg"] > 1e-6 else None),
        "slope_median_ratio_inside_over_control": (
            round(a["slope_median_deg"] / b["slope_median_deg"], 4)
            if a and b and b["slope_median_deg"] > 1e-6 else None),
        "steep_fraction_ratio_inside_over_control": (
            round(a["steep_gt10deg_fraction"] / b["steep_gt10deg_fraction"], 4)
            if a and b and b["steep_gt10deg_fraction"] > 1e-6 else None),
        "cross_section": prof,
    }


def attr_relation(mt: MapTiles, net, band=CONTROL_BAND):
    """Do roads clear the block flag?  1 attr cell == 1 tile, so this is exact."""
    a, ok = stitch_attr(mt)
    if not ok.any():
        return {"reason": "no attr.atr"}
    core = net["core"]
    h = min(core.shape[0], a.shape[0])
    w = min(core.shape[1], a.shape[1])
    core = core[:h, :w]
    ok = ok[:h, :w] & mt.valid[:h, :w]
    a = a[:h, :w]
    dout = cv2.distanceTransform(np.pad((~core).astype(np.uint8), 1),
                                 cv2.DIST_C, 3)[1:-1, 1:-1]
    ctrl = (dout >= band[0]) & (dout <= band[1]) & ok
    flags = (("block", ATTR_BLOCK), ("water", ATTR_WATER),
             ("banpk", ATTR_BANPK), ("object", ATTR_OBJECT))

    def rates(m):
        n = int(m.sum())
        if n == 0:
            return None
        return dict({"n_tiles": n},
                    **{k: round(float(((a[m] & v) != 0).mean()), 5)
                       for k, v in flags})
    ins, con = rates(core & ok), rates(ctrl)
    rel = None
    if ins and con and con["block"] > 1e-6:
        rel = round(ins["block"] / con["block"], 4)
    return {"inside_corridor": ins, "control": con,
            "block_rate_ratio_inside_over_control": rel,
            "map_block_rate": round(float(((a[ok] & ATTR_BLOCK) != 0).mean()), 5)}


# --------------------------------------------------------------------------
def _weighted_quantiles(vals, weights, qs):
    v = np.asarray(vals, float)
    w = np.asarray(weights, float)
    o = np.argsort(v)
    v, w = v[o], w[o]
    c = np.cumsum(w)
    if c[-1] <= 0:
        return [None] * len(qs)
    c = (c - 0.5 * w) / c[-1]
    return [round(float(np.interp(q, c, v)), 3) for q in qs]


def map_roads(mt: MapTiles, archetype=None, n_centrelines=8):
    stats = classify_path_indices(mt)
    path = [s["index"] for s in stats if s.get("is_path")]
    rec = {
        "map": mt.name,
        "archetype": archetype,
        "textureset": mt.setting.texture_set if mt.setting else None,
        "base_position_cm": list(mt.base_position),
        "grid_tiles": [int(mt.grid.shape[1]), int(mt.grid.shape[0])],
        "index_shape_stats": stats,
        "path_indices": [{"index": s["index"], "texture": s["texture"],
                          "role": s["role"], "name_prior": s.get("name_prior"),
                          "width_median_m": s.get("width_median_m"),
                          "coverage": round(s["coverage"], 5)}
                         for s in stats if s.get("is_path")],
    }
    if not path:
        rec["has_roads"] = False
        return rec
    net = road_network(mt, path)
    segs = [s for s in net["segments"] if s["length_m"] > 0]
    if not segs:
        rec["has_roads"] = False
        return rec
    rec["has_roads"] = True
    lens = np.array([s["length_m"] for s in segs])
    wids = np.array([s["width_median_m"] for s in segs])
    tort = np.array([s["metrics"]["tortuosity"] or 1.0 for s in segs])
    turn = np.array([s["metrics"]["turn_deg_per_10m"] for s in segs])
    strf = np.array([s["metrics"]["straight_fraction"] for s in segs])
    rad = np.array([s["metrics"]["radius_of_curvature_m"] for s in segs
                    if s["length_m"] >= 30 and s["metrics"]["radius_of_curvature_m"]])
    long_m = lens >= 30
    rec["network"] = {
        "core_tiles": int(net["core"].sum()),
        "core_fraction_of_map": round(float(net["core"].sum() / mt.valid.sum()), 5),
        "raw_path_tiles": int(net["raw"].sum()),
        "core_over_raw": round(float(net["core"].sum() / max(net["raw"].sum(), 1)), 4),
        "skeleton_length_m": int(net["skel"].sum()),
        "segments": len(segs),
        "segments_over_30m": int(long_m.sum()),
        "total_centreline_m": round(float(lens.sum()), 1),
        "road_density_m_per_km2": round(
            float(lens.sum()) / (mt.valid.sum() / 1e6), 1) if mt.valid.any() else None,
    }
    tw_all = [w for s in segs for w in s["transect_widths_m"]]
    tw_arr = np.array(tw_all) if tw_all else np.array([0.0])
    rec["width"] = {
        "unit": "metres (== tiles == half-cells); 1 cell = 2 m",
        "estimator": "perpendicular transect across the de-dithered core "
                     "(exact); the *_dt_* fields use 2*distanceTransform-1, "
                     "which reads one metre low on even widths",
        "transect_samples": len(tw_all),
        "transect_p10_p25_p50_p75_p90_m": [
            round(float(np.quantile(tw_arr, q)), 2)
            for q in (0.10, 0.25, 0.50, 0.75, 0.90)],
        "transect_median_m": round(float(np.median(tw_arr)), 2),
        "transect_mean_m": round(float(tw_arr.mean()), 2),
        "transect_median_cells": round(float(np.median(tw_arr)) / 2.0, 2),
        "transect_median_cm": round(float(np.median(tw_arr)) * TILE_SCALE, 1),
        "transect_histogram_m": {str(int(k)): int(v) for k, v in
                                 sorted(collections.Counter(tw_all).items())},
        "length_weighted_p10_p25_p50_p75_p90": _weighted_quantiles(
            wids, lens, [0.10, 0.25, 0.50, 0.75, 0.90]),
        "median_dt_m": round(float(np.median(wids)), 2),
        "within_segment_cv_median": round(float(np.median(
            [s["width_cv"] for s in segs])), 4),
        "histogram_dt_m": dict(collections.Counter(
            int(round(w)) for w in np.repeat(wids, np.maximum(lens.astype(int), 1)))),
    }
    rec["curvature"] = {
        "tortuosity_median": round(float(np.median(tort[long_m])) if long_m.any()
                                   else float(np.median(tort)), 4),
        "tortuosity_p90": round(float(np.quantile(tort[long_m], 0.9)) if long_m.any()
                                else float(np.quantile(tort, 0.9)), 4),
        "turn_deg_per_10m_median": round(float(np.median(turn[long_m])) if long_m.any()
                                         else float(np.median(turn)), 3),
        "turn_deg_per_10m_p90": round(float(np.quantile(turn[long_m], 0.9)) if long_m.any()
                                      else float(np.quantile(turn, 0.9)), 3),
        "straight_fraction_median": round(float(np.median(strf[long_m])) if long_m.any()
                                          else float(np.median(strf)), 4),
        "radius_of_curvature_m": round(float(np.median(rad)), 2) if len(rad) else None,
        "note": "centrelines are smoothed (Gaussian, sigma = 3 m) then "
                "resampled every 4 m before any heading is taken, so tile "
                "staircasing does not register as curvature; straight = "
                "deviation under 1 m from its own chord over >= 20 m; "
                "radius_of_curvature_m = arc length / total turn in radians; "
                "all figures use segments >= 30 m only",
    }
    # degree over the *accepted* segment graph, not the raw skeleton: a raw
    # medial axis is mostly thinning hair (see prune_spurs).
    endc = collections.Counter()
    for s in segs:
        for e in set(s["ends"]):
            endc[e] += 1
    deg = collections.Counter(endc.values())
    njunc = sum(v for k, v in deg.items() if k >= 3)
    rec["topology"] = {
        "junction_types": dict(net["junction_types"]),
        "junction_merge_radius_m": round(net["junction_merge_radius_m"], 2),
        "junction_arm_count_histogram": {
            str(k): v for k, v in sorted(collections.Counter(
                j["degree"] for j in net["junctions"]).items())},
        "junctions_merged": sum(1 for j in net["junctions"]
                                if j["merged_nodes"] > 1),
        "node_degree_histogram": {str(k): v for k, v in sorted(deg.items())},
        "raw_skeleton_node_degrees": {
            str(k): v for k, v in sorted(collections.Counter(
                net["nodes"].values()).items())},
        "endpoints": deg.get(1, 0),
        "junctions_total": len(net["junctions"]),
        "junctions_per_km_of_road": round(
            len(net["junctions"]) / (lens.sum() / 1000.0), 2) if lens.sum() else None,
        "segment_end_degree_3plus": njunc,
        "graph": net["graph"],
        "loop_count_euler": net["graph"]["cycles"],
        "loops_per_km_of_road": round(
            net["graph"]["cycles"] / (lens.sum() / 1000.0), 3) if lens.sum() else None,
        "plaza_threshold_m": round(net["plaza_threshold_m"], 2),
        "plazas": net["plazas"][:12],
        "plaza_count": len(net["plazas"]),
        "junction_samples": sorted(net["junctions"],
                                   key=lambda j: -j["degree"])[:12],
    }
    core_by_index = collections.Counter(mt.grid[net["core"]].tolist())
    core_tot = sum(core_by_index.values()) or 1
    rec["road_texture_ranking"] = [
        {"index": int(i), "texture": mt.slot_name(int(i)),
         "role": mt.slot_role(int(i)),
         "core_tiles": int(n), "share_of_road_surface": round(n / core_tot, 4)}
        for i, n in core_by_index.most_common() if i in set(path)]
    rec["edge_treatment"] = edge_profile(mt, net, path)
    rec["terrain_relation"] = terrain_relation(mt, net)
    rec["attr_relation"] = attr_relation(mt, net)

    # centrelines, longest first
    picks = sorted(segs, key=lambda s: -s["length_m"])[:n_centrelines]
    bx, by = mt.base_position
    lines = []
    for s in picks:
        simp = rdp(s["points"], eps=1.5)
        lines.append({
            "length_m": s["length_m"],
            "tortuosity": s["metrics"]["tortuosity"],
            "turn_deg_per_10m": s["metrics"]["turn_deg_per_10m"],
            "straight_fraction": s["metrics"]["straight_fraction"],
            "width_median_m": (round(s["width_transect_median_m"], 2)
                               if s["width_transect_median_m"] else
                               round(s["width_median_m"], 2)),
            "width_dt_median_m": round(s["width_median_m"], 2),
            "width_dt_p10_p90_m": [round(s["width_p10_m"], 2),
                                   round(s["width_p90_m"], 2)],
            "closed_loop": s["closed"],
            "vertices_tile": [[int(round(x)), int(round(y))] for x, y in simp],
            "vertices_world_cm": [[int(bx + x * TILE_SCALE), int(by + y * TILE_SCALE)]
                                  for x, y in simp],
            "rdp_epsilon_m": 1.5,
        })
    rec["centrelines"] = lines
    rec["road_verdict"] = road_verdict(rec)
    return rec


# --------------------------------------------------------------------------
def _json_default(o):
    """numpy scalars leak in through Counter keys and cv2 stats."""
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError("%r is not JSON serialisable" % (type(o).__name__,))


def _num(vals):
    a = np.asarray([v for v in vals if v is not None], float)
    a = a[~np.isnan(a)]
    if a.size == 0:
        return None
    return {"n": int(a.size), "mean": round(float(a.mean()), 4),
            "median": round(float(np.median(a)), 4),
            "p10": round(float(np.quantile(a, 0.1)), 4),
            "p90": round(float(np.quantile(a, 0.9)), 4)}


def aggregate(recs, key, confirmed_only=True):
    """Group per-map road records for per-archetype statistics.

    ``has_roads`` alone is not enough. The miner classifies each map's ribbons
    into road / terrain_ribbon / ambiguous, and the corpus splits 37 / 29 / 7 --
    so grouping on ``has_roads`` pooled the width, tortuosity, curvature and
    junction statistics of 36 maps whose ribbons this very module decided were
    NOT roads (snow fields, desert flats and similar large soft-edged regions).

    ``confirmed_only`` keeps only verdict == "road". Pass False to reproduce the
    older, wider grouping.
    """
    groups = collections.defaultdict(list)
    skipped = collections.Counter()
    for r in recs:
        if not r.get("has_roads"):
            continue
        verdict = (r.get("road_verdict") or {}).get("verdict")
        if confirmed_only and verdict != "road":
            skipped[verdict or "unknown"] += 1
            continue
        groups[r.get(key) or "unclassified"].append(r)
    if skipped:
        # Never let a coverage cap pass silently as "we measured everything".
        print("  aggregate(%s): excluded %d non-road maps (%s)"
              % (key, sum(skipped.values()),
                 ", ".join("%s=%d" % kv for kv in sorted(skipped.items()))))
    out = {}
    for name, rs in sorted(groups.items()):
        jt = collections.Counter()
        wh = collections.Counter()
        roles = collections.Counter()
        for r in rs:
            jt.update(r["topology"]["junction_types"])
            for k, v in r["width"]["transect_histogram_m"].items():
                wh[int(k)] += v
            for p in r["path_indices"]:
                roles[p["role"]] += 1
        tot = sum(wh.values()) or 1
        out[name] = {
            "maps": sorted(r["map"] for r in rs),
            "map_count": len(rs),
            "total_centreline_m": round(sum(r["network"]["total_centreline_m"] for r in rs), 1),
            "road_core_fraction": _num([r["network"]["core_fraction_of_map"] for r in rs]),
            "road_density_m_per_km2": _num([r["network"]["road_density_m_per_km2"] for r in rs]),
            "width_median_m": _num([r["width"]["transect_median_m"] for r in rs]),
            "width_median_dt_m": _num([r["width"]["median_dt_m"] for r in rs]),
            "width_histogram_m": {str(k): round(v / tot, 5)
                                  for k, v in sorted(wh.items()) if k <= 40},
            "tortuosity_median": _num([r["curvature"]["tortuosity_median"] for r in rs]),
            "turn_deg_per_10m_median": _num([r["curvature"]["turn_deg_per_10m_median"] for r in rs]),
            "straight_fraction_median": _num([r["curvature"]["straight_fraction_median"] for r in rs]),
            "junctions_per_km": _num([r["topology"]["junctions_per_km_of_road"] for r in rs]),
            "junction_type_share": {k: round(v / max(sum(jt.values()), 1), 4)
                                    for k, v in jt.most_common()},
            "radius_of_curvature_m": _num([r["curvature"]["radius_of_curvature_m"]
                                           for r in rs]),
            "loops_per_km": _num([r["topology"]["loops_per_km_of_road"] for r in rs]),
            "plaza_count_total": sum(r["topology"]["plaza_count"] for r in rs),
            "blend_band_m": _num([r["edge_treatment"]["blend_band_m"] for r in rs]),
            "ring1_path_share": _num([r["edge_treatment"]["ring1_path_share"] for r in rs]),
            "slope_ratio_inside_over_control": _num(
                [r["terrain_relation"].get("slope_ratio_inside_over_control") for r in rs]),
            "block_rate_ratio_inside_over_control": _num(
                [r["attr_relation"].get("block_rate_ratio_inside_over_control") for r in rs]),
            "path_texture_role_counts": dict(roles),
            "road_verdict_counts": dict(collections.Counter(
                r.get("road_verdict", {}).get("verdict") for r in rs)),
        }
    return out


#: A corridor is only a *road* if the map was edited for it.  Shape alone
#: also matches ribbon-shaped terrain (the rock bands of map_n_snowm_01 pass
#: every geometric test), so the two independent layers decide: a road runs on
#: ground flattened relative to its surroundings and with the block flag
#: cleared.  Thresholds picked from the corpus bimodality -- see
#: ``by_archetype``: field_empire/field_valley/guild_village/arena_pvp sit at
#: slope 0.16-0.27 and block 0.02-0.24, while snow_field/desert/ice_valley/
#: event_instance sit at slope 0.91-1.85 and block 0.89-1.04.
ROAD_VERDICT_SLOPE_MAX = 0.60
ROAD_VERDICT_BLOCK_MAX = 0.60


def road_verdict(rec):
    """Is the detected corridor network a designed road, or ribbon terrain?

    Pure function of values already measured into ``rec``; returns a dict with
    ``verdict`` in {"road", "terrain_ribbon", "ambiguous", "undetermined"}.
    """
    if not rec.get("has_roads"):
        return {"verdict": "no_corridors"}
    sl = rec.get("terrain_relation", {}).get("slope_ratio_inside_over_control")
    bl = rec.get("attr_relation", {}).get("block_rate_ratio_inside_over_control")
    if sl is None and bl is None:
        return {"verdict": "undetermined", "slope_ratio": sl, "block_ratio": bl}
    flat = sl is not None and sl < ROAD_VERDICT_SLOPE_MAX
    clear = bl is not None and bl < ROAD_VERDICT_BLOCK_MAX
    if flat and clear:
        v = "road"
    elif not flat and not clear:
        v = "terrain_ribbon"
    else:
        v = "ambiguous"
    return {"verdict": v, "slope_ratio": sl, "block_ratio": bl,
            "flattened": flat, "block_cleared": clear,
            "thresholds": [ROAD_VERDICT_SLOPE_MAX, ROAD_VERDICT_BLOCK_MAX]}


def texture_vocabulary(pack_dir):
    """Every distinct .dds referenced by the shipped TextureSets, by role.

    This is the evidence for "Ymir has no road texture": across all 100 sets
    in ``<pack>/textureset/textureset`` not one filename contains road, path,
    trail, track or street.
    """
    from ..codec.textureset import TextureSet
    root = pathlib.Path(pack_dir) / "textureset" / "textureset"
    names = collections.Counter()
    if root.is_dir():
        for f in sorted(root.glob("*.txt")):
            try:
                ts = TextureSet.load(f)
            except (OSError, ValueError):
                continue
            for e in ts.slots:
                if e is not None and e.filename:
                    names[e.filename.replace("\\", "/").lower()] += 1
    by_role = collections.defaultdict(list)
    for n in sorted(names):
        by_role[texture_role(n)].append(n)
    return {
        "textureset_files_scanned": len(list(root.glob("*.txt"))) if root.is_dir() else 0,
        "distinct_textures": len(names),
        "role_counts": {k: len(v) for k, v in sorted(
            by_role.items(), key=lambda kv: -len(kv[1]))},
        "road_like_names": [n for n in names
                            if any(w in n for w in ("road", "path", "trail",
                                                    "track", "street"))],
        "textures_by_role": {k: v for k, v in sorted(by_role.items())},
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--maps", default=str(DEFAULT_MAPS_DIR))
    ap.add_argument("--pack", default=str(DEFAULT_PACK_DIR))
    ap.add_argument("--taxonomy", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--only", default=None)
    ap.add_argument("--annotate", default=None,
                    help="re-derive the fields that are pure functions of "
                         "already-measured values (road_verdict and the "
                         "roll-ups over it) in an existing roads.json, "
                         "in place, without re-reading the corpus")
    args = ap.parse_args(argv)

    if args.annotate:
        path = pathlib.Path(args.annotate)
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        recs = list(doc["maps"].values())
        for r in recs:
            r["road_verdict"] = road_verdict(r)
        with_roads = [r for r in recs if r.get("has_roads")]
        doc["by_archetype"] = aggregate(recs, "archetype")
        doc["corpus"]["road_verdict_counts"] = dict(collections.Counter(
            r["road_verdict"]["verdict"] for r in with_roads))
        doc["corpus"]["confirmed_road_maps"] = sorted(
            r["map"] for r in with_roads
            if r["road_verdict"]["verdict"] == "road")
        doc["method"]["road_verdict"] = (
            "shape alone also matches ribbon-shaped terrain, so a network "
            "counts as a road only when it is measurably flattened "
            "(slope_ratio < %.2f) AND has the block flag cleared "
            "(block_rate_ratio < %.2f) relative to a %s m control band"
            % (ROAD_VERDICT_SLOPE_MAX, ROAD_VERDICT_BLOCK_MAX,
               list(CONTROL_BAND)))
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, default=_json_default)
        print("annotated %s (%d maps)" % (path, len(recs)), file=sys.stderr)
        return doc

    here = pathlib.Path(__file__).resolve()
    catalog = here.parents[3] / "reference" / "catalog"
    arche = load_archetypes(args.taxonomy or (catalog / "map-taxonomy.json"))
    out_path = pathlib.Path(args.out or (catalog / "roads.json"))

    recs = []
    for d in sorted(pathlib.Path(args.maps).iterdir()):
        if not d.is_dir() or (args.only and args.only not in d.name):
            continue
        mt = load_map(d, pathlib.Path(args.pack))
        if mt is None:
            continue
        r = map_roads(mt, arche.get(d.name))
        recs.append(r)
        print("  %-42s roads=%-5s paths=%s len=%s" % (
            d.name, r.get("has_roads"),
            [p["index"] for p in r["path_indices"]],
            r.get("network", {}).get("total_centreline_m")), file=sys.stderr)

    with_roads = [r for r in recs if r.get("has_roads")]
    all_lines = []
    for r in with_roads:
        for c in r["centrelines"]:
            all_lines.append((c["length_m"], r["map"], r["archetype"], c))
    all_lines.sort(key=lambda t: -t[0])

    doc = {
        "schema_version": 1,
        "generated_from": {
            "maps_dir": args.maps, "pack_dir": args.pack,
            "maps_analysed": len(recs), "maps_with_roads": len(with_roads),
            "spec": "reference/mapformat/tile-raw.md, height-raw.md, attr-atr.md",
        },
        "method": {
            "grid": "stitched tile.raw, 1 tile = 100 world units = 1 m = 1 half-cell",
            "dedither": "open(3x3) then close(3x3), then drop components < %d tiles"
                        % MIN_CORE_COMPONENT,
            "centreline": "Zhang-Suen thinning; width = 2*distanceTransform(L2) - 1",
            "path_rule": ("index is path-role when its art family is one of "
                          "%s AND it is not the base layer AND coverage <= "
                          "%.2f AND solid_retention >= %.2f AND median corridor "
                          "width in %s m AND aspect (L^2/area) >= %.0f AND "
                          "ribbon_fraction >= %.2f"
                          % (list(PATH_ROLE_PRIOR), MAX_PATH_COVERAGE,
                             MIN_SOLID_RETENTION, list(PATH_WIDTH_RANGE),
                             MIN_PATH_ASPECT, MIN_RIBBON_FRACTION)),
            "spur_pruning": ("dead-end branches under %d m are removed from the "
                             "medial axis before any topology is counted"
                             % SPUR_PRUNE_M),
            "constants": {
                "MIN_CORE_COMPONENT": MIN_CORE_COMPONENT,
                "MIN_INDEX_AREA": MIN_INDEX_AREA,
                "PATH_WIDTH_RANGE": list(PATH_WIDTH_RANGE),
                "MIN_PATH_ASPECT": MIN_PATH_ASPECT,
                "MIN_RIBBON_FRACTION": MIN_RIBBON_FRACTION,
                "SPUR_PRUNE_M": SPUR_PRUNE_M,
                "MAX_PATH_COVERAGE": MAX_PATH_COVERAGE,
                "MIN_SOLID_RETENTION": MIN_SOLID_RETENTION,
                "MIN_BRANCH_LEN": MIN_BRANCH_LEN,
                "CONTROL_BAND": list(CONTROL_BAND),
            },
        },
        "coordinates": {
            "tile_to_world_cm": "x_cm = BasePosition.x + tile_x * 100, "
                                "y_cm = BasePosition.y + tile_y * 100; tile "
                                "(0,0) is the NW corner of sector 000000, X "
                                "grows east and Y grows south",
            "caveat": "areadata.txt stores object Y negated (see "
                      "reference/mapformat/areadata-txt.md); the world_cm "
                      "values here are NOT negated -- negate Y before writing "
                      "a centreline vertex into an areadata record",
            "sector_of_tile": "sector folder = printf('%03d%03d', tile_x//256, "
                              "tile_y//256)",
        },
        "texture_role_vocabulary": texture_vocabulary(pathlib.Path(args.pack)),
        "corpus": None,
        "by_archetype": aggregate(recs, "archetype"),
        "longest_centrelines": [
            dict(c, map=m, archetype=a) for _, m, a, c in all_lines[:24]],
        "maps": {r["map"]: r for r in recs},
    }
    if with_roads:
        wh = collections.Counter()
        jt = collections.Counter()
        for r in with_roads:
            for k, v in r["width"]["transect_histogram_m"].items():
                wh[int(k)] += v
            jt.update(r["topology"]["junction_types"])
        tot = sum(wh.values()) or 1
        doc["corpus"] = {
            "maps_with_roads": len(with_roads),
            "total_centreline_m": round(sum(r["network"]["total_centreline_m"]
                                            for r in with_roads), 1),
            "width_histogram_m": {str(k): round(v / tot, 5) for k, v in sorted(wh.items())},
            "width_median_m": _num([r["width"]["transect_median_m"] for r in with_roads]),
            "width_median_dt_m": _num([r["width"]["median_dt_m"] for r in with_roads]),
            "tortuosity_median": _num([r["curvature"]["tortuosity_median"] for r in with_roads]),
            "turn_deg_per_10m_median": _num([r["curvature"]["turn_deg_per_10m_median"]
                                             for r in with_roads]),
            "radius_of_curvature_m": _num([r["curvature"]["radius_of_curvature_m"]
                                           for r in with_roads]),
            "junctions_per_km": _num([r["topology"]["junctions_per_km_of_road"]
                                      for r in with_roads]),
            "loops_per_km": _num([r["topology"]["loops_per_km_of_road"]
                                  for r in with_roads]),
            "straight_fraction_median": _num([r["curvature"]["straight_fraction_median"]
                                              for r in with_roads]),
            "junction_type_share": {k: round(v / max(sum(jt.values()), 1), 4)
                                    for k, v in jt.most_common()},
            "junctions_per_km": _num([r["topology"]["junctions_per_km_of_road"]
                                      for r in with_roads]),
            "blend_band_m": _num([r["edge_treatment"]["blend_band_m"] for r in with_roads]),
            "ring1_path_share": _num([r["edge_treatment"]["ring1_path_share"]
                                      for r in with_roads]),
            "slope_ratio_inside_over_control": _num(
                [r["terrain_relation"].get("slope_ratio_inside_over_control")
                 for r in with_roads]),
            "block_rate_ratio_inside_over_control": _num(
                [r["attr_relation"].get("block_rate_ratio_inside_over_control")
                 for r in with_roads]),
            "road_verdict_counts": dict(collections.Counter(
                r.get("road_verdict", {}).get("verdict") for r in with_roads)),
            "confirmed_road_maps": sorted(
                r["map"] for r in with_roads
                if r.get("road_verdict", {}).get("verdict") == "road"),
        }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, default=_json_default)
    print("wrote %s (%d maps, %d with roads)" % (out_path, len(recs), len(with_roads)),
          file=sys.stderr)
    return doc


if __name__ == "__main__":
    main()

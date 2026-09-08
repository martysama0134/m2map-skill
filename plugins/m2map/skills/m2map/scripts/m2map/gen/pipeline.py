"""The staged pipeline driver.

Stages are re-entrant: each declares what it consumes and produces, and
:func:`run` can start from any of them given the earlier artifacts. That is what
lets ``improve`` re-run 2..8 for touched sectors while terrain sculpted by hand
in WorldEditor survives, and ``reskin`` re-run only texture, objects, attr and
finish.

Order (revised against the mining -- see the design doc):

    0 resolve   1 spec   2 layout   3 terrain   4 water
    5 texture   6 objects   7 attr   8 finish

``water`` precedes ``texture`` because texture needs the rasterised wet mask, and
``attr`` follows ``objects`` because footprints are one of its inputs.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from ..codec import areadata as ad
from . import attribute, finish, layout, objects, terrain, texture, water
from .spec import MapSpec

STAGES = ("layout", "terrain", "water", "texture", "objects", "attr", "finish")


@dataclass
class Build:
    """Everything the pipeline has produced so far."""

    spec: MapSpec
    layout: Optional[layout.Layout] = None
    height_cm: Optional[np.ndarray] = None
    slope_deg: Optional[np.ndarray] = None
    water_cells: Optional[np.ndarray] = None
    water_heights: List[float] = field(default_factory=list)
    wet: Optional[np.ndarray] = None
    submerged: Optional[np.ndarray] = None
    tiles: Optional[np.ndarray] = None
    records: List[ad.ObjectRecord] = field(default_factory=list)
    footprints: List[Tuple[float, float, float]] = field(default_factory=list)
    attr_cells: Optional[np.ndarray] = None
    server_attr: object = None
    log: List[str] = field(default_factory=list)

    def note(self, msg: str) -> None:
        self.log.append(msg)


def _note_road_gradient(b: "Build") -> None:
    """Report how much flatter the corridor is than the ground beside it.

    The corpus figure is `slope_ratio_inside_over_control`, measured against a
    [6, 24] m control band: median **0.21** over the 37 confirmed road maps,
    p25 0.13, p75 0.38, worst 0.56.

    This is reported rather than asserted because the generator can only get
    part of the way there. Levelling the corridor is implemented; **choosing a
    gentle route is not**. Ymir's roads follow ground that was already easy, so
    the corpus figure is route selection and earthworks combined, while the
    generator levels whatever line the spec names. The desert reference spec
    measures 0.58 -- level with the corpus's worst confirmed road -- and a spec
    whose waypoints cut straight over a massif will measure worse. If this line
    reads above about 0.5, move the waypoints before touching the generator.
    """
    if b.layout is None or b.slope_deg is None or not b.layout.corridors:
        return
    core = np.zeros(b.layout.shape, bool)
    for c in b.layout.corridors:
        core |= c.core
    d = b.layout.road_distance
    ctrl = (d >= 6.0) & (d <= 24.0)
    if core.sum() < 50 or ctrl.sum() < 50:
        return
    h, w = b.slope_deg.shape
    ys, xs = np.mgrid[:core.shape[0], :core.shape[1]]
    sl = b.slope_deg[np.clip(ys // 2, 0, h - 1), np.clip(xs // 2, 0, w - 1)]
    inside, control = float(sl[core].mean()), float(sl[ctrl].mean())
    if control <= 1e-6:
        return
    ratio = inside / control
    b.note("road: slope %.1f deg vs %.1f deg beside it, ratio %.2f "
           "(corpus median 0.21, worst confirmed road 0.56)%s"
           % (inside, control, ratio,
              "  <-- route crosses steep ground" if ratio > 0.5 else ""))


def run(spec: MapSpec, bbox_lookup: Optional[Callable] = None,
        stages: Tuple[str, ...] = STAGES, build: Optional[Build] = None,
        progress: Optional[Callable[[str], None]] = None) -> Build:
    """Run the requested stages, in order, on a fresh or existing build."""
    spec.require_valid()
    b = build or Build(spec=spec)

    def step(name: str) -> bool:
        if name not in stages:
            return False
        if progress:
            progress(name)
        return True

    if step("layout"):
        b.layout = layout.build(spec)
        b.note("layout: %d corridor(s), %d water feature(s), %d region(s)"
               % (len(b.layout.corridors), len(b.layout.water_masks),
                  len(b.layout.regions)))

    if step("terrain"):
        flat = b.layout.flatten_mask_cells() if b.layout else None
        carve = b.layout.carve_cm if b.layout else None
        gap = b.layout.ridge_gap if b.layout else None
        pads = b.layout.pad_masks_cells() if b.layout else None
        b.height_cm = terrain.build(spec, flatten_mask=flat,
                                    carve_cm=carve, ridge_gap=gap, pads=pads,
                                    scarp_cm=(b.layout.scarp_cm
                                              if b.layout else None),
                                    benches=(b.layout.benches
                                             if b.layout else None))
        b.slope_deg = terrain.slope_degrees(b.height_cm)
        # Report the PLAYABLE interior, not the whole grid. The border ridge is
        # a 40 deg wall by design, and including it pushed the reported slope
        # p50 from 4.1 to 16.0 and the flat fraction from 37% to 6% -- numbers
        # that look like a broken generator when compared against the
        # archetype's targets, which describe ground the player stands on.
        inner = b.height_cm
        if spec.border_ridge_cm > 0:
            m = int(max(4, spec.border_ridge_width_m / 2.0)) + 2
            if min(inner.shape) > 2 * m + 8:
                inner = inner[m:-m, m:-m]
        _note_road_gradient(b)
        s = terrain.stats(inner)
        scope = "interior" if inner is not b.height_cm else "map"
        b.note("terrain (%s): slope p50 %.1f / p95 %.1f deg, flat %.0f%%"
               % (scope, s["walkable_slope_deg"]["p50"],
                  s["walkable_slope_deg"]["p95"], s["flat_fraction_2deg"] * 100))
        if scope == "interior":
            w = terrain.stats(b.height_cm)
            b.note("  border ridge: +%.0f cm over %.0f m; whole-map slope p50 "
                   "%.1f deg (the wall, by design)"
                   % (spec.border_ridge_cm, spec.border_ridge_width_m,
                      w["walkable_slope_deg"]["p50"]))

    if step("water"):
        cells, heights, wet, sub = water.build(spec, b.layout, b.height_cm)
        b.water_cells, b.water_heights, b.wet, b.submerged = cells, heights, wet, sub
        b.note("water: %d layer(s), %.1f%% submerged"
               % (len(heights), 100.0 * sub.mean() if sub is not None else 0.0))

    if step("texture"):
        b.tiles = texture.build(spec, b.layout, b.height_cm, b.slope_deg,
                                b.wet if b.wet is not None else
                                np.zeros(b.layout.shape, bool))
        st = texture.stipple_stats(b.tiles)
        b.note("texture: %d slots used, run-length median %.1f, base share %.2f"
               % (st["used_slots"], st["run_length_median"], st["base_share"]))

    if step("objects"):
        b.records, b.footprints, shortfalls = objects.build(
            spec, b.layout, b.height_cm, b.slope_deg, b.tiles,
            submerged=b.submerged, wet=b.wet, bbox_lookup=bbox_lookup)
        os_ = objects.stats(b.records)
        b.note("objects: %d placed, %d distinct CRCs, roll-snap %.0f%%"
               % (os_.get("count", 0), os_.get("distinct_crcs", 0),
                  100 * os_.get("roll_snap_15_share", 0)))
        for name, want, got, why in shortfalls:
            b.note("  ! %s: %s" % (name, why))

    if step("attr"):
        b.attr_cells = attribute.build(spec, b.layout, b.slope_deg,
                                       b.submerged, b.footprints)
        b.server_attr = attribute.build_server_attr(spec, b.attr_cells)
        cov = attribute.coverage(b.attr_cells)
        b.note("attr: block %.0f%%, water %.0f%%, safezone %.0f%%"
               % (100 * cov["block"], 100 * cov["water"], 100 * cov["safezone"]))

    return b


def assemble(b: Build) -> Dict:
    """Turn whole-map grids into per-sector codec objects, ready to write."""
    spec = b.spec
    shade = finish.bake_shadow(b.height_cm)
    by_sector = objects.split_by_sector(b.records, spec)

    sectors: Dict[Tuple[int, int], Dict] = {}
    for cx, cy in spec.sectors():
        recs = by_sector.get((cx, cy), [])
        area = ad.AreaData(records=list(recs))
        area.declared_count = len(recs)
        amb = ad.AreaAmbienceData(records=[])
        amb.declared_count = 0
        sectors[(cx, cy)] = {
            "height": terrain.to_sector_raw(b.height_cm, cx, cy),
            "tile": texture.to_sector_raw(b.tiles, cx, cy),
            "attr": attribute.to_sector(b.attr_cells, cx, cy),
            "water": water.to_sector(b.water_cells, b.water_heights, cx, cy),
            "shadow": finish.sector_shadow(shade, cx, cy),
            "minimap": finish.sector_minimap(b.tiles, shade, spec.textures, cx, cy),
            "areadata": area,
            "ambience": amb,
        }
    return {"sectors": sectors, "server_attr": b.server_attr}


def write(b: Build, out_dir, textureset_dir=None, spec_copy: bool = True) -> List[str]:
    """Write the map, its textureset and its mapspec to disk."""
    layers = assemble(b)
    written = finish.write_map(out_dir, b.spec, layers, b.spec.textures)

    out = pathlib.Path(out_dir)
    ts = texture.build_textureset(b.spec)
    ts_name = "%s.txt" % (b.spec.textureset_name or b.spec.name)
    ts_dir = pathlib.Path(textureset_dir) if textureset_dir else out / "textureset"
    ts_dir.mkdir(parents=True, exist_ok=True)
    (ts_dir / ts_name).write_bytes(ts.to_bytes())
    written.append(str((ts_dir / ts_name).relative_to(out))
                   if textureset_dir is None else str(ts_dir / ts_name))

    if spec_copy:
        b.spec.dump(out / "mapspec.yaml")
        written.append("mapspec.yaml")
    return written

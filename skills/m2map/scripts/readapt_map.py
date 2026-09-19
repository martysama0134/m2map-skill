#!/usr/bin/env python3
"""Readapt a merged map: level the source maps, weld the joins, cut a pass
through each double wall and run a road along it.

    python readapt_map.py <merged map> --out <new folder>
    python readapt_map.py <merged map> --out <new folder> --no-level --floor 12
    python readapt_map.py <merged map> --out <new folder> --render
    python readapt_map.py <merged map> --out <existing result> --render-only --at 767,1280

Never edits in place: the merged map is copied to --out and only the files that
changed are rewritten there. The report is printed and kept as
``<out>/_readapt.json``; before/after pictures land in ``<out>/_preview/``.

--render loads BOTH maps in WorldEditorRemix and shoots every pass before and
after with one camera: ``_preview/we_<spot>_{before,after}.png`` and one contact
sheet, ``we_sheet.png``. Look at the sheet -- that is the point of it.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from m2map.edit import readapt, we_shots


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("map")
    ap.add_argument("--out", required=True)
    ap.add_argument("--overwrite", action="store_true", help="replace --out if it exists")
    ap.add_argument("--no-level", action="store_true",
                    help="keep every source map at its own datum (the pass climbs instead)")
    ap.add_argument("--floor", type=float, default=16.0, help="pass floor width, m")
    ap.add_argument("--road", type=float, default=7.0, help="road core width, m")
    ap.add_argument("--road-slot", action="append", default=[], metavar="BLOCK:SLOT",
                    help="force the road texture slot for one source map")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--render", action="store_true",
                    help="shoot every pass in WorldEditorRemix, before and after")
    ap.add_argument("--render-only", action="store_true",
                    help="--out is an existing result: shoot it, change nothing")
    ap.add_argument("--at", action="append", default=[], metavar="X,Y",
                    help="one more spot to shoot, in tile metres (repeatable)")
    a = ap.parse_args(argv)

    if a.render_only:
        report = json.loads((pathlib.Path(a.out) / "_readapt.json").read_text("ascii"))
        return _render(a, report)

    opt = readapt.Options(level=not a.no_level, floor_m=a.floor, road_m=a.road, seed=a.seed,
                          road_slots={int(b): int(s) for b, s in
                                      (v.split(":") for v in a.road_slot)})
    report = readapt.readapt(a.map, a.out, opt, overwrite=a.overwrite)
    print(json.dumps(report, indent=1))
    bad = report.get("problems") or [b for b, ok in report.get("joined", {}).items() if not ok]
    if a.render and _render(a, report):
        return 1
    return 1 if bad else 0


def _render(a, report) -> int:
    spots = we_shots.link_spots(report)
    for i, v in enumerate(a.at):
        x, y = (float(t) for t in v.split(","))
        spots["at%d" % i] = (x, y)
    try:
        shots = we_shots.pairs(a.map, a.out, spots, pathlib.Path(a.out) / "_preview")
    except we_shots.RenderUnavailable as e:
        print("NOT RENDERED -- tell the user the map was not checked in the editor:", e,
              file=sys.stderr)
        return 1
    print(json.dumps({"rendered": shots,
                      "sheet": str(pathlib.Path(a.out) / "_preview" / "we_sheet.png")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

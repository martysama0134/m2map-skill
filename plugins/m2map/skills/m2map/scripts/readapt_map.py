#!/usr/bin/env python3
"""Readapt a merged map: level the source maps, weld the joins, cut a pass
through each double wall and run a road along it.

    python readapt_map.py <merged map> --out <new folder>
    python readapt_map.py <merged map> --out <new folder> --no-level --floor 12

Never edits in place: the merged map is copied to --out and only the files that
changed are rewritten there. The report is printed and kept as
``<out>/_readapt.json``; before/after pictures land in ``<out>/_preview/``.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from m2map.edit import readapt


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
    a = ap.parse_args(argv)

    opt = readapt.Options(level=not a.no_level, floor_m=a.floor, road_m=a.road, seed=a.seed,
                          road_slots={int(b): int(s) for b, s in
                                      (v.split(":") for v in a.road_slot)})
    report = readapt.readapt(a.map, a.out, opt, overwrite=a.overwrite)
    print(json.dumps(report, indent=1))
    bad = report.get("problems") or [b for b, ok in report.get("joined", {}).items() if not ok]
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())

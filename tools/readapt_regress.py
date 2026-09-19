#!/usr/bin/env python3
"""Run readapt on every merged test map and say what moved.

    python tools/readapt_regress.py            # compare with the baseline
    python tools/readapt_regress.py --accept   # the new numbers ARE the baseline

The merged maps live outside the repo (``merge_tests`` in ``m2map.paths.json``:
the folder holding ``map_merge_test_*``). Each is readapted into a temp folder
and reduced to the numbers a change to ``edit/readapt.py`` is able to move --
blocks, datum shifts, every pass, the read-backs -- and compared with
``tests/baselines/readapt.json``.

This exists because "maps 01 and 02 are unchanged" was once written into a
commit message before it was checked. Run it before saying so.

Exit 0: nothing moved. Exit 1: something did -- read the lines, and if the
change is the one you meant, ``--accept``. Exit 2: no maps found.
"""
import argparse
import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "m2map" / "scripts"))

from m2map import config                                          # noqa: E402
from m2map.edit import readapt                                    # noqa: E402

BASELINE = ROOT / "tests" / "baselines" / "readapt.json"


def summary(report: dict) -> dict:
    return {
        "blocks": {b: len(s) for b, s in report.get("blocks", {}).items()},
        "void_blocks": report.get("void_blocks", []),
        "level_cm": report.get("level_cm", {}),
        "links": [{k: lk[k] for k in ("blocks", "from_tile", "to_tile", "length_m",
                                      "wall_m", "mouths_cm", "grade_pct", "road_joined_m", "water_m")
                                if k in lk}
                  for lk in report.get("links", [])],
        "skipped_links": [lk["blocks"] for lk in report.get("skipped_links", [])],
        "problems": report.get("problems", []),
        "joined": report.get("joined", {}),
        "tear_after_cm": report.get("tear_after_cm"),
        "blank_tiles_added": report.get("blank_tiles_added"),
        "join_slot_cm": report.get("join_slot_cm"),
        "objects": {k: (round(v) if isinstance(v, float) else v)
                    for k, v in report.get("objects", {}).items()},
        "server_attr": report.get("server_attr"),
        "files_written": len(report.get("written", [])),
    }


def diff(old, new, at="") -> list:
    if isinstance(old, dict) and isinstance(new, dict):
        out = []
        for k in sorted(set(old) | set(new), key=str):
            out += diff(old.get(k), new.get(k), "%s.%s" % (at, k) if at else str(k))
        return out
    if isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        out = []
        for i, (a, b) in enumerate(zip(old, new)):
            out += diff(a, b, "%s[%d]" % (at, i))
        return out
    return [] if old == new else ["  %s: %s -> %s" % (at, json.dumps(old), json.dumps(new))]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--maps", default=None, help="folder holding map_merge_test_* "
                                                 "(default: merge_tests in m2map.paths.json)")
    ap.add_argument("--accept", action="store_true", help="write the new numbers as the baseline")
    a = ap.parse_args(argv)

    where = pathlib.Path(a.maps) if a.maps else config.paths().merge_tests
    maps = sorted(p for p in (where.iterdir() if where and where.is_dir() else [])
                  if p.is_dir() and p.name.startswith("map_merge_test_")
                  and not p.name.endswith("_readapt") and (p / "setting.txt").is_file())
    if not maps:
        print("no map_merge_test_* under %s: pass --maps or set merge_tests" % where,
              file=sys.stderr)
        return 2

    base = json.loads(BASELINE.read_text("ascii")) if BASELINE.is_file() else {}
    got, moved = {}, 0
    for mp in maps:
        with tempfile.TemporaryDirectory() as tmp:
            got[mp.name] = summary(readapt.readapt(mp, pathlib.Path(tmp) / "out"))
        # json round trip: int keys become the strings the baseline holds
        got[mp.name] = json.loads(json.dumps(got[mp.name]))
        lines = diff(base.get(mp.name), got[mp.name]) if mp.name in base else ["  (no baseline)"]
        moved += bool(lines)
        print("%-24s %s" % (mp.name, "MOVED" if lines else "same"))
        print("\n".join(lines), end="\n" if lines else "")

    if a.accept:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps({**base, **got}, indent=1, sort_keys=True) + "\n", "ascii",
                            newline="\n")
        print("baseline written: %s" % BASELINE.relative_to(ROOT))
        return 0
    return 1 if moved else 0


if __name__ == "__main__":
    raise SystemExit(main())

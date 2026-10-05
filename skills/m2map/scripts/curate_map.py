#!/usr/bin/env python3
"""Curate somebody's map: fix what the quality rules flag, where the user says.

    python curate_map.py <map> --list
    python curate_map.py <map> --fix attr,rock,road,border,water [--sectors 000001,001001] --render

--list runs the quality pass (M2MAP-QA-001..004) and the water rules
(M2MAP-WTR-005 staircase shore, WTR-004 water half flagged, ATR-002 stray water
bits) and prints which fix answers
which finding, as JSON -- the menu `modes/curate.md` asks the user from. --fix
copies the map beside itself (`<map>_backup_<time>`, unless --no-backup), applies
the chosen fixes inside the chosen sectors only, and audits again. --render
shoots every changed spot in WorldEditorRemix on the backup and on the result
(`<map>/_curate/we_sheet.png`).
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from m2map.audit import quality, rules
from m2map.config import paths
from m2map.edit import curate, we_shots

#: which fix answers which finding
FIX_FOR = {"M2MAP-QA-001": "rock", "M2MAP-QA-002": "attr",
           "M2MAP-QA-003": "road", "M2MAP-QA-004": "border",
           "M2MAP-WTR-005": "water", "M2MAP-WTR-004": "water", "M2MAP-ATR-002": "water"}


def textureset_dir(map_dir, given=None):
    """The first folder holding the map's TextureSet: the one given, the map's own
    `textureset/` (what build_map writes), the client pack's, the editor's data
    root (where `we_shots` stages them)."""
    from m2map.codec.setting import Setting
    if given:
        return given
    P = paths()
    name = pathlib.Path(str(Setting.load(pathlib.Path(map_dir) / "setting.txt").texture_set)
                        .replace("\\", "/")).name.lower()
    cands = [pathlib.Path(map_dir) / "textureset"]
    for key, sub in (("client_pack", ("textureset", "textureset")), ("worldeditor_data", ("textureset",))):
        root = getattr(P, key, None)
        if root:
            cands.append(pathlib.Path(root).joinpath(*sub))
    for c in cands:
        if c.is_dir() and any(p.name.lower() == name for p in c.iterdir()):
            return str(c)
    return None


def flagged(map_dir, tsdir):
    out = []
    for f in quality.quality(rules.resolve(map_dir), tsdir):
        out.append({"rule": f.rule, "severity": f.severity, "fix": FIX_FOR.get(f.rule),
                    "where": f.where, "symptom": f.symptom, "detail": f.detail})
    # the water rules map-wide: a plane runs across sector borders
    out += curate.water_findings(curate.load(map_dir, tsdir))
    # the edge test counts a mostly-blocked band as a wall: with no attr at all,
    # every rim reads open. Ask about the border only once the attr is back
    if any(f["rule"] == "M2MAP-QA-002" for f in out):
        for f in out:
            if f["rule"] == "M2MAP-QA-004":
                f["after"] = "attr"
                f["note"] = "may be the missing attr alone: fix attr, then --list again"
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("map")
    ap.add_argument("--list", action="store_true", help="only report what is flagged")
    ap.add_argument("--fix", default="", help="comma list of: " + ", ".join(curate.FIXES))
    ap.add_argument("--sectors", default="", help="comma list of XXXYYY; default the whole map")
    ap.add_argument("--textureset-dir", default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-backup", action="store_true")
    ap.add_argument("--render", action="store_true",
                    help="before/after shots of every changed spot in WorldEditorRemix")
    a = ap.parse_args(argv)

    tsdir = textureset_dir(a.map, a.textureset_dir)
    before = flagged(a.map, tsdir)
    if a.list or not a.fix:
        print(json.dumps({"map": a.map, "flagged": before}, indent=1))
        return 0

    fixes = [f.strip() for f in a.fix.split(",") if f.strip()]
    sectors = [s.strip() for s in a.sectors.split(",") if s.strip()] or None
    report = curate.curate(a.map, fixes, sectors, tsdir, make_backup=not a.no_backup, seed=a.seed)
    report["flagged_before"] = sorted({f["rule"] for f in before})
    report["flagged_after"] = sorted({f["rule"] for f in flagged(a.map, tsdir)})
    print(json.dumps(report, indent=1))

    if a.render:
        if "backup" not in report:
            print("NOT RENDERED -- there is no backup to compare with (--no-backup)", file=sys.stderr)
            return 1
        out = pathlib.Path(a.map) / "_curate"
        spots = {k: tuple(v) for k, v in report["spots"].items()}
        if not spots:
            print("nothing visible to render: the fixes only changed attr", file=sys.stderr)
            return 0
        try:
            we_shots.pairs(report["backup"], a.map, spots, out)
        except we_shots.RenderUnavailable as e:
            print("NOT RENDERED -- tell the user the map was not checked in the editor:", e,
                  file=sys.stderr)
            return 1
        print("sheet:", out / "we_sheet.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

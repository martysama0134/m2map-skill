#!/usr/bin/env python3
"""Audit a map for the faults that make it break in game.

    python audit_map.py d:/maps/metin2_map_foo

Read-only. Reports symptom-first: what the player would see, then the cause.
Severity is honest -- `info` findings are things shipped Ymir maps do too, and
are not defects.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from m2map.audit import rules
from m2map.config import paths


def property_crcs():
    cat = (pathlib.Path(__file__).resolve().parents[1]
           / "reference" / "catalog" / "objects.json")
    if not cat.exists():
        return None
    data = json.loads(cat.read_text(encoding="utf-8"))
    objs = data.get("objects")
    if isinstance(objs, dict):
        return {int(k) for k in objs}
    return {int(o["crc"]) for o in objs} if objs else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("map_dir")
    ap.add_argument("--corpus", default=None, help="for resolving ParentMapName")
    ap.add_argument("--textureset-dir", default=None)
    ap.add_argument("--severity", default="info",
                    choices=rules.SEVERITIES, help="minimum severity to report")
    ns = ap.parse_args(argv)

    P = paths()
    corpus = ns.corpus or (str(P.corpus) if P.corpus else None)
    tsdir = ns.textureset_dir or (str(P.texturesets) if P.client_pack else None)

    findings = rules.audit(ns.map_dir, corpus_root=corpus,
                           property_crcs=property_crcs(), textureset_dir=tsdir)
    cutoff = rules.SEVERITIES.index(ns.severity)
    shown = [f for f in findings if rules.SEVERITIES.index(f.severity) <= cutoff]

    counts = rules.summarise(findings)
    print("%s: blocker=%d major=%d minor=%d info=%d"
          % (ns.map_dir, counts["blocker"], counts["major"],
             counts["minor"], counts["info"]))
    for f in shown:
        print("\n%s" % f)
        if f.fix:
            print("         fix: %s" % f.fix)
    return 1 if counts["blocker"] else 0


if __name__ == "__main__":
    sys.exit(main())

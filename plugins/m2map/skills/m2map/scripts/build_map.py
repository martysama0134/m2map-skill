#!/usr/bin/env python3
"""Build a map from a mapspec.

    python build_map.py spec.yaml --out <maps>/metin2_map_foo [--preview]

The spec is the contract: everything the generator does comes from it, so a map
is reproducible from (spec, seed) and an edit is a spec diff. See
`m2map/gen/spec.py` for the schema.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from m2map.config import paths
from m2map.gen import pipeline
from m2map.gen.spec import MapSpec, SpecError


def bbox_lookup_from_catalog():
    """crc -> (sx, sy, sz) cm from the mined model catalog, if present."""
    cat = (pathlib.Path(__file__).resolve().parents[1]
           / "reference" / "catalog" / "models.json")
    if not cat.exists():
        return None
    data = json.loads(cat.read_text(encoding="utf-8"))
    models = data.get("models") or {}
    table = {}
    for entry in (models.values() if isinstance(models, dict) else models):
        if not isinstance(entry, dict):
            continue
        size = entry.get("size_xyz")
        crc = entry.get("crc")
        if crc is not None and size:
            try:
                table[int(crc)] = tuple(float(v) for v in size)
            except (TypeError, ValueError):
                continue
    return table.get if table else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", help="mapspec .yaml/.json")
    ap.add_argument("--out", default=None,
                    help="map output dir (default: <output_dir>/<name> from config)")
    ap.add_argument("--textureset-dir", default=None,
                    help="where to write the textureset (default: <map>/textureset)")
    ap.add_argument("--preview", action="store_true", help="render 2D layer PNGs")
    ap.add_argument("--preview-dir", default=None)
    ap.add_argument("--stages", default=None,
                    help="comma-separated subset, e.g. texture,objects,attr")
    ap.add_argument("--audit", action="store_true", help="audit the result")
    ns = ap.parse_args(argv)

    try:
        spec = MapSpec.load(ns.spec)
    except SpecError as exc:
        print("spec error:\n%s" % exc, file=sys.stderr)
        return 2

    problems = spec.validate()
    if problems:
        print("mapspec is not buildable:", file=sys.stderr)
        for p in problems:
            print("  - %s" % p, file=sys.stderr)
        return 2

    out = pathlib.Path(ns.out) if ns.out else None
    if out is None:
        base = paths().output_dir
        if base is None:
            print("no --out and no output_dir configured", file=sys.stderr)
            return 2
        out = base / spec.name

    stages = tuple(s.strip() for s in ns.stages.split(",")) if ns.stages else pipeline.STAGES
    b = pipeline.run(spec, bbox_lookup=bbox_lookup_from_catalog(), stages=stages,
                     progress=lambda s: print("  %s..." % s, file=sys.stderr))
    for line in b.log:
        print("  " + line)

    written = pipeline.write(b, out, textureset_dir=ns.textureset_dir)
    print("\nwrote %d files to %s" % (len(written), out))

    if ns.preview:
        from m2map.preview import layers
        pdir = pathlib.Path(ns.preview_dir) if ns.preview_dir else out / "_preview"
        pngs = layers.render_all(b, pdir)
        print("previews: %s" % ", ".join(sorted(pngs)))
        print("  -> %s" % pdir)
        print("  LOOK AT THESE before shipping the map. A map that parses is not")
        print("  a map that plays, and the statistics can read fine while the")
        print("  picture is obviously wrong.")

    if ns.audit:
        from m2map.audit import rules
        findings = rules.audit(out, textureset_dir=ns.textureset_dir or out / "textureset")
        print("\naudit: %s" % rules.summarise(findings))
        for f in findings:
            print("  %s" % f)
    return 0


if __name__ == "__main__":
    sys.exit(main())

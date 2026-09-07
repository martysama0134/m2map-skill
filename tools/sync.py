#!/usr/bin/env python3
"""Sync the m2map skill from its single source of truth to every agent's native format.

Source of truth
---------------
    skills/m2map/           the skill itself
    agents/                 dispatchable subagent definitions
    rules/m2map-activate.md the auto-activation rule body

Generated (never edit by hand; this script overwrites them)
-----------------------------------------------------------
    plugins/m2map/skills/m2map/     Codex plugin skill subtree
    plugins/m2map/agents/           Codex plugin agent subtree
    .agents/plugins/marketplace.json  Codex plugin discovery descriptor
    .cursor/rules/m2map.mdc         Cursor  (alwaysApply frontmatter)
    .windsurf/rules/m2map.md        Windsurf (always_on frontmatter)
    .clinerules/m2map.md            Cline    (bare copy)
    .github/copilot-instructions.md Copilot  (bare copy)

Usage
-----
    python tools/sync.py             # write the generated files
    python tools/sync.py --check     # exit 1 if anything is out of date (CI gate)

Runs on stock Python 3.9+ with no third-party dependencies, so it works
identically in GitHub Actions and on a Windows box with no rsync.
"""

from __future__ import annotations

import argparse
import filecmp
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SKILL_SRC = ROOT / "skills" / "m2map"
AGENTS_SRC = ROOT / "agents"
RULES_SRC = ROOT / "rules" / "m2map-activate.md"

CODEX_ROOT = ROOT / "plugins" / "m2map"
CODEX_SKILL = CODEX_ROOT / "skills" / "m2map"
CODEX_AGENTS = CODEX_ROOT / "agents"

# Never copied into the generated trees.
IGNORE = shutil.ignore_patterns(
    "__pycache__", "*.pyc", "*.pyo", ".pytest_cache",
    ".cache", "patches", "sheets", "*.npy",
)

CURSOR_FRONTMATTER = """\
---
description: "m2map - Metin2 map generator. Activate when the user creates, modifies, audits, merges or reskins Metin2 maps, or works with map file formats (height.raw, tile.raw, attr.atr, water.wtr, areadata.txt, textureset, msenv, server_attr)."
alwaysApply: true
---

"""

WINDSURF_FRONTMATTER = """\
---
trigger: always_on
---

"""

CODEX_MARKETPLACE = {
    "name": "m2map-local",
    "plugins": [
        {
            "name": "m2map",
            "source": {"source": "local", "path": "./plugins/m2map"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Coding",
        }
    ],
}


class Sync:
    """Collects writes so --check can report drift without touching the tree."""

    def __init__(self, check_only: bool) -> None:
        self.check_only = check_only
        self.stale: list[str] = []

    def _rel(self, path: Path) -> str:
        return path.relative_to(ROOT).as_posix()

    def write_text(self, dest: Path, content: str) -> None:
        current = dest.read_text(encoding="utf-8") if dest.exists() else None
        if current == content:
            return
        self.stale.append(self._rel(dest))
        if self.check_only:
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        # newline="\n" so Windows checkouts do not emit CRLF into generated files
        # that .gitattributes has already declared to be LF.
        dest.write_text(content, encoding="utf-8", newline="\n")

    def mirror_tree(self, src: Path, dest: Path) -> None:
        """Make dest an exact copy of src (deleting anything extra)."""
        if not src.exists():
            raise SystemExit(f"source tree missing: {self._rel(src)}")

        if self._trees_equal(src, dest):
            return

        self.stale.append(self._rel(dest) + "/")
        if self.check_only:
            return
        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest, ignore=IGNORE)

    def _trees_equal(self, src: Path, dest: Path) -> bool:
        if not dest.exists():
            return False
        ignored = set(IGNORE(str(src), [p.name for p in src.iterdir()]))
        cmp = filecmp.dircmp(src, dest, ignore=list(ignored))
        return self._dircmp_equal(cmp)

    def _dircmp_equal(self, cmp: filecmp.dircmp) -> bool:
        if cmp.left_only or cmp.right_only or cmp.funny_files:
            return False
        # shallow=False: compare contents, not just size+mtime. A stat-only
        # match would let an edited-but-same-size file pass as synced.
        _, mismatch, errors = filecmp.cmpfiles(
            cmp.left, cmp.right, cmp.common_files, shallow=False
        )
        if mismatch or errors:
            return False
        return all(self._dircmp_equal(sub) for sub in cmp.subdirs.values())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="store_true",
        help="report drift and exit 1 instead of writing (CI gate)",
    )
    args = ap.parse_args()

    if not RULES_SRC.exists():
        raise SystemExit(f"missing rule source: {RULES_SRC.relative_to(ROOT).as_posix()}")
    body = RULES_SRC.read_text(encoding="utf-8")

    s = Sync(args.check)

    # Codex plugin subtree
    s.mirror_tree(SKILL_SRC, CODEX_SKILL)
    s.mirror_tree(AGENTS_SRC, CODEX_AGENTS)
    s.write_text(
        ROOT / ".agents" / "plugins" / "marketplace.json",
        json.dumps(CODEX_MARKETPLACE, indent=2) + "\n",
    )

    # Per-tool activation rules, all derived from the one body
    s.write_text(ROOT / ".clinerules" / "m2map.md", body)
    s.write_text(ROOT / ".github" / "copilot-instructions.md", body)
    s.write_text(ROOT / ".cursor" / "rules" / "m2map.mdc", CURSOR_FRONTMATTER + body)
    s.write_text(ROOT / ".windsurf" / "rules" / "m2map.md", WINDSURF_FRONTMATTER + body)

    if not s.stale:
        print("sync: up to date")
        return 0

    if args.check:
        print("sync: OUT OF DATE -- run `python tools/sync.py`:")
        for path in s.stale:
            print(f"  {path}")
        return 1

    print("sync: updated")
    for path in s.stale:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

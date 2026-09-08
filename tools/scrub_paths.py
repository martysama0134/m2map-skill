#!/usr/bin/env python3
"""Keep host filesystem paths out of committed files.

This repo is published. An absolute path like ``C:/Users/<someone>/Documents/git/...``
baked into a reference doc or a mined catalog leaks the author's machine layout
and is wrong for every other user. Generated artifacts refer to host locations
by placeholder instead -- ``<CLIENT_PACK>``, ``<CORPUS>``, ``<WORLDEDITOR>`` --
resolved per machine from ``m2map.paths.json`` (gitignored).

    python tools/scrub_paths.py            # rewrite host paths to placeholders
    python tools/scrub_paths.py --check    # exit 1 if any tracked file leaks

What is deliberately NOT scrubbed
---------------------------------
``d:/ymir work/...`` strings inside Metin2 data are literal *client* asset
references -- textureset texture entries, ``buildingfile``/``treefile`` property
keys, ``.msenv`` cloud textures. The game engine resolves them against its own
pack. They are part of the file format, they appear verbatim in every shipped
map, and rewriting them would corrupt the data. ``ymir_work`` is therefore
excluded from the placeholder map in ``m2map.config``.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "skills" / "m2map" / "scripts"))

from m2map.config import paths  # noqa: E402

TEXT_SUFFIXES = {
    ".md", ".json", ".py", ".txt", ".yml", ".yaml", ".sh", ".cfg",
    ".ini", ".toml", ".js", ".mdc",
}

# Files allowed to contain literal host paths: the gitignored local config, its
# template, this scrubber and the config loader (both of which document the
# problem in their docstrings), and the scrubber's own test suite -- whose
# fixtures MUST stay raw. Scrubbing the tests turns
#   assert scrub("C:/Users/alice/x") == "<HOME>/x"
# into the vacuous
#   assert scrub("<HOME>/x") == "<HOME>/x"
# which passes while testing nothing. Learned the hard way.
ALLOWLIST = {
    "CLAUDE.local.md",
    "m2map.paths.json",
    "m2map.paths.example.json",
    "tools/scrub_paths.py",
    "skills/m2map/scripts/m2map/config.py",
    "tests/test_scrub_paths.py",
}

# Trees that tools/sync.py regenerates wholesale from the source of truth.
# Scrubbing them is wrong twice over: the edit is discarded on the next sync,
# and until then it makes the copy differ from its (allowlisted) source, so
# `sync.py --check` fails permanently. Clean the source; the mirror follows.
GENERATED_PREFIXES = (
    "plugins/m2map/",
    ".cursor/",
    ".windsurf/",
    ".clinerules/",
    ".agents/",
    ".github/copilot-instructions.md",
)

# In-game asset references. These are part of the Metin2 file format -- the
# engine resolves them against its own pack -- and they appear verbatim in every
# shipped map. They are masked out before substitution and restored afterwards,
# so no host-path rule can reach inside one. Without this, a corpus configured
# as "D:/" rewrites d:/ymir work/... to <CORPUS>/ymir work/..., and a model path
# containing a /home/ or /Users/ component gets a <HOME> spliced into its middle.
IN_GAME_RE = re.compile(r"[A-Za-z]:[\\/]{1,2}ymir[ _]work[\\/][^\"'\s<>|]*",
                        re.IGNORECASE)

# Catch-all for any user home dir we did not enumerate, on all three platforms.
#
# Anchored: the lookbehind stops it matching a /home/ or /Users/ component in
# the MIDDLE of a longer path. The username class excludes only characters that
# cannot appear in a path component, so names with spaces ("Alice Smith") are
# consumed whole instead of leaving a "<HOME> Smith" remnant.
HOME_RE = re.compile(
    r"(?<![A-Za-z0-9._\-])"
    r"(?:[A-Za-z]:)?[/\\]{1,2}(?:Users|home)[/\\]{1,2}"
    r"[^\\/:*?\"<>|\r\n]+?(?=[/\\]|$)",
    re.IGNORECASE,
)

#: Source files must never be silently rewritten -- see scrub_text().
SOURCE_SUFFIXES = {".py"}


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return [REPO_ROOT / p for p in out.split("\0") if p]


def candidate_files(only_tracked: bool) -> list[Path]:
    if only_tracked:
        files = tracked_files()
    else:
        files = [
            p for p in REPO_ROOT.rglob("*")
            if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts
        ]
    return [p for p in files if p.suffix.lower() in TEXT_SUFFIXES]


def build_patterns(placeholder_map: dict[str, str] | None = None) -> list[tuple[re.Pattern, str]]:
    """Regexes matching each configured host root, separator-agnostic.

    ``placeholder_map`` (host path -> token) defaults to this machine's config.
    Tests MUST pass synthetic maps: a suite that only ever exercises the local
    config proves nothing about anyone else's, which is how the ``D:/``-as-corpus
    and username-with-spaces breakages went unnoticed.

    Each is anchored on both ends at a path-component boundary: a root must not
    match starting mid-component, and must be followed by a separator or the end
    of the path. Without the leading anchor a configured root that is a prefix of
    another string matches inside it; without the trailing one, a root like
    ``D:/map`` would match ``D:/maps``.
    """
    if placeholder_map is None:
        placeholder_map = paths().placeholder_map()
    patterns = []
    for host, token in placeholder_map.items():
        norm = host.replace("\\", "/")
        parts = [p for p in re.split(r"[/\\]+", norm) if p]
        if not parts:
            continue
        body = r"[/\\]{1,2}".join(re.escape(part) for part in parts)
        # A POSIX absolute root ("/srv/maps") must keep its leading separator,
        # or it both leaves a stray "/" in the output and matches the same names
        # appearing as a RELATIVE path ("vendor/srv/maps").
        if norm.startswith("/"):
            body = r"[/\\]" + body
        # Both ends anchored at a path-component boundary. "/" and "\" are in the
        # lookbehind class so a root cannot match part-way along a longer path.
        rx = re.compile(r"(?<![A-Za-z0-9._\-/\\])" + body + r"(?![A-Za-z0-9._\-])",
                        re.IGNORECASE)
        patterns.append((rx, token))
    return patterns


def scrub_text(text: str, patterns: list[tuple[re.Pattern, str]]) -> str:
    """Replace host paths with placeholders, leaving in-game refs untouched.

    In-game asset references are masked out first with a sentinel that contains
    no path characters, so no host rule can match inside one, then restored.
    """
    shelf: list[str] = []

    def stash(m: re.Match) -> str:
        shelf.append(m.group(0))
        return "\x00INGAME%d\x00" % (len(shelf) - 1)

    text = IN_GAME_RE.sub(stash, text)

    for rx, token in patterns:
        text = rx.sub(token, text)
    text = HOME_RE.sub("<HOME>", text)

    for i, original in enumerate(shelf):
        text = text.replace("\x00INGAME%d\x00" % i, original)
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="report leaks and exit 1 instead of rewriting")
    ap.add_argument("--all", action="store_true",
                    help="scan every file, not only git-tracked ones "
                         "(use before staging freshly generated artifacts)")
    args = ap.parse_args()

    patterns = build_patterns()
    if not patterns:
        print("scrub: no paths configured; nothing to scrub", file=sys.stderr)

    hits: list[tuple[str, int]] = []
    changed: list[str] = []
    source_hits: list[tuple[str, int]] = []

    for path in candidate_files(only_tracked=not args.all):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in ALLOWLIST or rel.startswith(GENERATED_PREFIXES):
            continue
        try:
            original = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        scrubbed = scrub_text(original, patterns)
        if scrubbed == original:
            continue

        leaked = sum(
            1 for line in original.splitlines()
            if scrub_text(line, patterns) != line
        )

        # NEVER rewrite source. A host path in a .py file means the module
        # hardcoded a location instead of resolving it through m2map.config;
        # substituting a placeholder produces a literal "<CORPUS>" string that
        # no longer resolves at runtime, converting a visible wrong default into
        # an invisible broken one. This is exactly how all five miners and both
        # codec test modules were silently broken. Report, do not patch.
        if path.suffix.lower() in SOURCE_SUFFIXES:
            source_hits.append((rel, leaked))
            continue

        if args.check:
            hits.append((rel, leaked))
        else:
            path.write_text(scrubbed, encoding="utf-8", newline="\n")
            changed.append(f"{rel} ({leaked} lines)")

    if source_hits:
        print("scrub: HOST PATHS IN PYTHON SOURCE -- fix these by hand:")
        for rel, n in source_hits:
            print(f"  {rel}  ({n} lines)")
        print("\n  Resolve the location through m2map.config instead of hardcoding it:")
        print("      from m2map.config import paths")
        print("      DEFAULT_MAPS = paths().corpus")
        print("  Do NOT substitute a placeholder here -- '<CORPUS>' is not a path,")
        print("  and baking it into source turns a wrong default into a broken one.")

    if args.check:
        if not hits and not source_hits:
            print("scrub: clean -- no host paths in tracked files")
            return 0
        if hits:
            print("scrub: HOST PATHS LEAKED into tracked files:")
            for rel, n in hits:
                print(f"  {rel}  ({n} lines)")
            print("\nRun `python tools/scrub_paths.py --all` to fix.")
        return 1

    if not changed:
        print("scrub: clean -- nothing to rewrite")
        return 1 if source_hits else 0
    print("scrub: rewrote host paths to placeholders")
    for line in changed:
        print(f"  {line}")
    return 1 if source_hits else 0


if __name__ == "__main__":
    sys.exit(main())

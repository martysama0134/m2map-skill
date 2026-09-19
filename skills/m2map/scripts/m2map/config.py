"""Machine-path resolution for m2map.

Every host filesystem location the skill touches is configured, never hardcoded.
The repo is published; a committed absolute path would leak the author's machine
layout and be wrong for everyone else.

Config search order (first hit wins):

1. ``$M2MAP_PATHS`` -- explicit path to a JSON config
2. ``m2map.paths.json`` at the repo root
3. ``m2map.paths.example.json`` at the repo root (placeholders; usable only for
   the keys you have actually filled in)

Individual keys can always be overridden by environment variable, which is what
CI and one-off runs should use::

    M2MAP_CORPUS=D:/maps  M2MAP_CLIENT_PACK=D:/pack  python -m m2map.mine...

Not to be confused with in-game paths
-------------------------------------
Strings like ``d:/ymir work/zone/foo.gr2`` that appear *inside* Metin2 data
files -- textureset texture entries, ``buildingfile``/``treefile`` property
keys, ``.msenv`` cloud textures -- are literal client asset references. The
engine resolves them against its own pack. They are part of the file format and
must be read and written verbatim. ``ymir_work`` here is the separate question
of where those assets happen to be extracted for tools that read models
directly.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, fields
from functools import lru_cache
from pathlib import Path

# skills/m2map/scripts/m2map/config.py -> repo root is five levels up
REPO_ROOT = Path(__file__).resolve().parents[4]

CONFIG_NAME = "m2map.paths.json"
EXAMPLE_NAME = "m2map.paths.example.json"


class ConfigError(RuntimeError):
    """Raised when a required path is unset or does not exist."""


@dataclass(frozen=True)
class Paths:
    """Resolved host locations. Values may be None when not configured."""

    corpus: Path | None = None
    client_pack: Path | None = None
    ymir_work: Path | None = None
    worldeditor: Path | None = None
    #: The editor BINARY, and the data root it must be started from (the folder
    #: holding pack/ and ymir work/). ``worldeditor`` above is the source repo.
    worldeditor_exe: Path | None = None
    worldeditor_data: Path | None = None
    mapforge: Path | None = None
    opengranny: Path | None = None
    pygr2: Path | None = None
    output_dir: Path | None = None
    #: Folder holding the merged test maps (map_merge_test_*) that
    #: tools/readapt_regress.py runs.
    merge_tests: Path | None = None

    # --- derived locations under the client pack -------------------------

    @property
    def property_db(self) -> Path:
        return self.require("client_pack") / "property" / "property"

    @property
    def texturesets(self) -> Path:
        return self.require("client_pack") / "textureset" / "textureset"

    @property
    def environments(self) -> Path:
        return self.require("client_pack") / "yw_etc" / "ymir work" / "environment"

    @property
    def terrainmaps(self) -> Path:
        return self.require("ymir_work") / "terrainmaps"

    @property
    def zone(self) -> Path:
        return self.require("ymir_work") / "zone"

    @property
    def tree(self) -> Path:
        return self.require("ymir_work") / "tree"

    # --- access ----------------------------------------------------------

    def require(self, key: str) -> Path:
        """Return a configured path, or explain precisely how to set it."""
        value = getattr(self, key, None)
        if value is None:
            raise ConfigError(
                f"path '{key}' is not configured.\n"
                f"  Set it in {REPO_ROOT / CONFIG_NAME}\n"
                f"  (copy {EXAMPLE_NAME} if it does not exist yet),\n"
                f"  or export M2MAP_{key.upper()}=<path>."
            )
        if not value.exists():
            raise ConfigError(
                f"path '{key}' is configured as {value} but does not exist.\n"
                f"  Fix it in {REPO_ROOT / CONFIG_NAME} or export M2MAP_{key.upper()}."
            )
        return value

    def placeholder_map(self) -> dict[str, str]:
        """Host path -> placeholder token, for scrubbing generated artifacts.

        Longest paths first so nested locations substitute before their parents.
        """
        pairs = [
            (self.client_pack, "<CLIENT_PACK>"),
            (self.worldeditor_exe, "<WORLDEDITOR_EXE>"),
            (self.worldeditor, "<WORLDEDITOR>"),
            (self.mapforge, "<MAPFORGE>"),
            (self.opengranny, "<OPENGRANNY>"),
            (self.pygr2, "<PYGR2>"),
            (self.corpus, "<CORPUS>"),
            (REPO_ROOT, "<REPO>"),
        ]
        out = {str(p): token for p, token in pairs if p is not None}
        return dict(sorted(out.items(), key=lambda kv: len(kv[0]), reverse=True))


def _load_raw() -> dict:
    explicit = os.environ.get("M2MAP_PATHS")
    candidates = [Path(explicit)] if explicit else []
    candidates += [REPO_ROOT / CONFIG_NAME, REPO_ROOT / EXAMPLE_NAME]

    for path in candidates:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            # Drop the doc block the example file carries.
            return {k: v for k, v in data.items() if not k.startswith("$")}
    return {}


@lru_cache(maxsize=1)
def paths() -> Paths:
    raw = _load_raw()
    kwargs = {}
    for f in fields(Paths):
        # Env var wins over the file, so a single run can be redirected.
        value = os.environ.get(f"M2MAP_{f.name.upper()}") or raw.get(f.name)
        if value in (None, "", "null"):
            kwargs[f.name] = None
            continue
        p = Path(str(value).replace("\\", "/"))
        # Reject the example file's untouched placeholders rather than
        # failing later with a confusing "no such directory".
        kwargs[f.name] = None if "path/to" in p.as_posix() else p
    return Paths(**kwargs)

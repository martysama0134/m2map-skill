"""The scrubber must abstract HOST paths without touching IN-GAME asset paths.

This distinction is the whole point and it is easy to get wrong in a way that
silently corrupts data:

- ``C:/Users/<someone>/Documents/M2Clients/.../pack`` is where the client
  happens to live on one machine. It must never be committed.
- ``d:/ymir work/zone/foo.gr2`` inside a textureset entry or a property file's
  ``buildingfile`` key is a *client asset reference*. The engine resolves it
  against its own pack. It appears verbatim in every shipped map. Rewriting it
  corrupts the file.

Both start with a drive letter and look like paths. Only one may be rewritten.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "skills" / "m2map" / "scripts"))

from tools.scrub_paths import build_patterns, scrub_text  # noqa: E402
from m2map.config import paths  # noqa: E402


@pytest.fixture(scope="module")
def patterns():
    return build_patterns()


def scrub(text, patterns):
    return scrub_text(text, patterns)


# --- in-game asset paths must survive byte-for-byte -----------------------

IN_GAME = [
    'd:/ymir work/zone/12temple/12t_12statue_01.gr2',
    'd:/ymir work/tree/b1_baobab_rt.spt',
    'd:/ymir work/environment/clouds_zone01.tga',
    'd:/ymir work/terrainmaps/b/field/field 01.dds',
    'd:\\ymir work\\terrainmaps\\b\\grass\\grass 01.dds',
    'D:/YMIR WORK/ZONE/N/OBJ/SNOW.M/GENERAL_OBJ_BELL.GR2',
]


@pytest.mark.parametrize("asset", IN_GAME)
def test_in_game_paths_are_untouched(asset, patterns):
    """A client asset reference is part of the file format, not a host path."""
    assert scrub(asset, patterns) == asset


def test_realistic_textureset_line_survives(patterns):
    line = '    "d:\\ymir work\\terrainmaps\\b\\field\\field 01.dds"'
    assert scrub(line, patterns) == line


def test_realistic_property_body_survives(patterns):
    body = (
        'buildingfile\t\t"d:/ymir work/zone/12temple/12t_12statue_01.gr2"\n'
        'propertyname\t\t"12T_12statue_01"\n'
        'propertytype\t\t"Building"\n'
    )
    assert scrub(body, patterns) == body


# --- host paths must be abstracted ----------------------------------------

def test_configured_roots_become_placeholders(patterns):
    p = paths()
    for host, token in p.placeholder_map().items():
        assert scrub(host, patterns) == token, f"{host} did not become {token}"


def test_separator_variants_all_match(patterns):
    p = paths()
    if p.client_pack is None:
        pytest.skip("client_pack not configured")
    posix = p.client_pack.as_posix()
    variants = [posix, posix.replace("/", "\\"), posix.replace("/", "\\\\")]
    for v in variants:
        assert "<CLIENT_PACK>" in scrub(v, patterns), f"missed separator form: {v}"


def test_subpaths_keep_their_tail(patterns):
    p = paths()
    if p.client_pack is None:
        pytest.skip("client_pack not configured")
    text = f"{p.client_pack.as_posix()}/property/property/a/tree.prt"
    out = scrub(text, patterns)
    assert out == "<CLIENT_PACK>/property/property/a/tree.prt"


# --- the catch-all: any user home, not just this machine's ----------------

@pytest.mark.parametrize("path", [
    "C:/Users/alice/Documents/thing",
    "C:\\Users\\bob\\Desktop",
    "/home/carol/maps",
    "/Users/dave/src",
])
def test_foreign_home_dirs_are_caught(path, patterns):
    out = scrub(path, patterns)
    assert "<HOME>" in out or "<" in out, f"leaked: {out}"
    for name in ("alice", "bob", "carol", "dave"):
        assert name not in out


def test_username_never_survives(patterns):
    p = paths()
    if p.client_pack is None:
        pytest.skip("client_pack not configured")
    parts = p.client_pack.as_posix().split("/")
    if len(parts) < 3 or parts[1].lower() != "users":
        pytest.skip("client_pack is not under a user home on this machine")
    username = parts[2]
    text = f"see {p.client_pack.as_posix()}/textureset for details"
    assert username not in scrub(text, patterns)


# --- mixed content, the real-world case -----------------------------------

def test_mixed_document(patterns):
    p = paths()
    if p.client_pack is None or p.corpus is None:
        pytest.skip("paths not configured")
    doc = (
        f"Parsed 100 texturesets from {p.client_pack.as_posix()}/textureset/textureset\n"
        f"Sampled {p.corpus.as_posix()}/metin2_map_a1/000000/areadata.txt\n"
        'Slot 1 -> "d:/ymir work/terrainmaps/b/field/field 01.dds"\n'
    )
    out = scrub(doc, patterns)
    assert "<CLIENT_PACK>/textureset/textureset" in out
    assert "<CORPUS>/metin2_map_a1/000000/areadata.txt" in out
    assert '"d:/ymir work/terrainmaps/b/field/field 01.dds"' in out

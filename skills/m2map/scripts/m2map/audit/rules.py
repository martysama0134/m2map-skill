"""Map validation -- symptom-first, with the detection rule spelled out.

Every check here answers "what will the player see", because that is where a
report is entered from. The companion prose is ``reference/failure-atlas.md``;
the machine-readable rule list is ``reference/catalog/audit-rules.json``.

Ordering is by severity, and severity means what it says:

``blocker``  the map does not load, or is unplayable (no collision anywhere,
             every cell impassable, sector silently dropped)
``major``    a visible, reproducible fault (invisible objects, walk-through
             walls, error texture)
``minor``    wrong but survivable (stale server_attr, unused palette slot)
``info``     worth knowing, and NOT a defect -- the corpus does this too

That last tier matters. 46% of adjacent sector pairs in shipped Ymir maps
disagree on their tile skirt, and 452 of 1343 sectors carry water below the
terrain. A checker that flags those as errors reports 142 broken official maps
and teaches the user to ignore it.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from ..codec import areadata as ad
from ..codec import attr as attr_codec
from ..codec import height as height_codec
from ..codec import server_attr as sa_codec
from ..codec import setting as setting_codec
from ..codec import textureset as ts_codec
from ..codec import tile as tile_codec
from ..codec import water as water_codec

SEVERITIES = ("blocker", "major", "minor", "info")

#: Exact sizes the loaders assume. They memcpy blindly, so a wrong size is
#: silent corruption rather than a load error.
FIXED_SIZES = {
    "height.raw": height_codec.FILE_SIZE,
    "tile.raw": tile_codec.FILE_SIZE,
    "attr.atr": attr_codec.FILE_SIZE,
}


@dataclass
class Finding:
    rule: str
    severity: str
    where: str
    symptom: str
    detail: str
    fix: str = ""

    def __str__(self) -> str:
        return "%-8s %-16s %s\n         %s" % (
            self.severity.upper(), self.rule, self.where, self.detail)


@dataclass
class MapView:
    """A resolved map on disk. Stage 0 -- see :func:`resolve`."""

    root: pathlib.Path
    setting: Optional[setting_codec.Setting] = None
    terrain_root: Optional[pathlib.Path] = None
    parent_name: str = ""
    sectors: List[str] = field(default_factory=list)
    is_proxy: bool = False


def resolve(map_dir, corpus_root=None) -> MapView:
    """Stage 0: work out whether this map owns terrain, and where it lives.

    26 of 142 corpus maps have NO sector folders -- they carry a
    ``ParentMapName`` and reuse the parent's terrain. Three
    (``metin2_guild_village_01/02/03``) have no ``setting.txt`` at all, only
    ``mapproperty.txt``. Any tool that assumes a map owns terrain reports
    blockers on shipped, working maps.
    """
    root = pathlib.Path(map_dir)
    view = MapView(root=root, terrain_root=root)

    setting_path = root / "setting.txt"
    if setting_path.exists():
        try:
            view.setting = setting_codec.Setting.load(setting_path)
        except Exception:                                  # noqa: BLE001
            view.setting = None

    prop = root / "mapproperty.txt"
    if prop.exists():
        try:
            mp = setting_codec.MapProperty.load(prop)
            view.parent_name = (getattr(mp, "parent_map_name", "") or
                                (mp.extras.get("parentmapname", [""])[0]
                                 if getattr(mp, "extras", None) else ""))
        except Exception:                                  # noqa: BLE001
            pass

    view.sectors = sorted(p.name for p in root.iterdir()
                          if p.is_dir() and len(p.name) == 6 and p.name.isdigit())

    if not view.sectors and view.parent_name:
        view.is_proxy = True
        if corpus_root:
            cand = pathlib.Path(corpus_root) / view.parent_name
            if cand.is_dir():
                view.terrain_root = cand
    return view


def _sector_xy(name: str) -> Tuple[int, int]:
    return int(name[:3]), int(name[3:])


def audit(map_dir, corpus_root=None, property_crcs: Optional[Iterable[int]] = None,
          textureset_dir=None) -> List[Finding]:
    """Run every check. Returns findings sorted worst-first."""
    view = resolve(map_dir, corpus_root)
    out: List[Finding] = []
    root = view.root
    crcs = set(property_crcs) if property_crcs is not None else None

    # --- map-level ------------------------------------------------------
    if view.setting is None:
        if view.is_proxy or view.parent_name:
            out.append(Finding(
                "M2MAP-SET-004", "info", str(root),
                "map reuses another map's terrain",
                "No setting.txt; ParentMapName=%r. This is legal -- three "
                "shipped maps do exactly this." % view.parent_name,
                "Nothing to fix."))
        else:
            out.append(Finding(
                "M2MAP-SET-001", "blocker", str(root / "setting.txt"),
                "map does not load at all",
                "setting.txt is missing and no ParentMapName was declared.",
                "Write setting.txt with all six required keys."))
            return out

    if view.is_proxy:
        out.append(Finding(
            "M2MAP-SET-005", "info", str(root),
            "proxy map -- terrain comes from the parent",
            "Zero sector folders, ParentMapName=%r. Sector-scope rules were run "
            "against %s." % (view.parent_name, view.terrain_root),
            "Nothing to fix."))

    s = view.setting
    if s is not None:
        declared = s.map_size
        for name in view.sectors:
            cx, cy = _sector_xy(name)
            if cx >= declared[0] or cy >= declared[1]:
                out.append(Finding(
                    "M2MAP-SET-002", "minor", str(root / name),
                    "sector exists but is never loaded",
                    "Sector (%d,%d) lies outside MapSize %dx%d. The client only "
                    "iterates the declared rectangle, so this is dead data."
                    % (cx, cy, declared[0], declared[1]),
                    "Extend MapSize, or delete the folder."))

        for i, v in enumerate(s.base_position):
            if v % 25600:
                out.append(Finding(
                    "M2MAP-SET-003", "minor", str(root / "setting.txt"),
                    "map origin is not sector-aligned",
                    "BasePosition[%d]=%d is not a multiple of 25600. Four "
                    "shipped maps do this too, so the client tolerates it, but "
                    "atlas and regen maths assume alignment." % (i, v),
                    "Round to a multiple of 25600 if you can still move the map."))

    # --- textureset -----------------------------------------------------
    ts = None
    if s is not None and s.texture_set:
        ts_name = pathlib.PurePath(s.texture_set.replace("\\", "/")).name
        for cand in ([pathlib.Path(textureset_dir) / ts_name] if textureset_dir else []) + \
                    [root / "textureset" / ts_name, root / ts_name]:
            if cand.exists():
                try:
                    ts = ts_codec.TextureSet.load(cand)
                except Exception as exc:                    # noqa: BLE001
                    out.append(Finding(
                        "M2MAP-TS-002", "major", str(cand),
                        "terrain renders as the error texture",
                        "TextureSet failed to parse: %s" % exc, "Fix the file."))
                break
        else:
            out.append(Finding(
                "M2MAP-TS-001", "major", str(root / "setting.txt"),
                "all terrain renders as the error texture",
                "TextureSet %r was not found. A map is not self-contained: "
                "tile.raw stores INDICES into this palette." % s.texture_set,
                "Ship the textureset alongside the map."))

    # --- per sector -----------------------------------------------------
    terrain_root = view.terrain_root or root
    sector_names = view.sectors or sorted(
        p.name for p in terrain_root.iterdir()
        if p.is_dir() and len(p.name) == 6 and p.name.isdigit())

    if not sector_names and not view.is_proxy:
        out.append(Finding(
            "M2MAP-SEC-001", "blocker", str(root),
            "empty map",
            "No sector folders and no ParentMapName.",
            "Generate terrain, or declare a ParentMapName."))

    for name in sector_names:
        sec = terrain_root / name
        rel = "%s/%s" % (terrain_root.name, name)

        if not (sec / "areaproperty.txt").exists():
            out.append(Finding(
                "M2MAP-SEC-002", "blocker", rel,
                "sector silently disappears",
                "areaproperty.txt is missing. It DEFINES the sector -- without "
                "it the sector is not loaded even though every binary layer is "
                "present.", "Write areaproperty.txt."))

        for fname, want in FIXED_SIZES.items():
            f = sec / fname
            if not f.exists():
                if fname == "attr.atr":
                    out.append(Finding(
                        "M2MAP-ATR-001", "blocker", "%s/%s" % (rel, fname),
                        "player walks through the world here",
                        "attr.atr missing -- the sector has no collision.",
                        "Generate attr.atr."))
                continue
            got = f.stat().st_size
            if got != want:
                out.append(Finding(
                    "M2MAP-BIN-001", "blocker", "%s/%s" % (rel, fname),
                    "terrain is corrupt or shifted",
                    "%s is %d bytes, expected %d. The loaders memcpy blindly, "
                    "so a wrong size corrupts the grid without an error."
                    % (fname, got, want),
                    "Regenerate the file at the exact size."))

        # tile indices vs palette
        tf = sec / "tile.raw"
        if tf.exists() and ts is not None:
            try:
                tm = tile_codec.read_tile(tf)
                used = set(int(v) for v in tm.used_indices())
                over = sorted(v for v in used if v > ts.declared_count)
                if over:
                    out.append(Finding(
                        "M2MAP-TIL-001", "major", "%s/tile.raw" % rel,
                        "patches of error texture on the ground",
                        "Tile indices %s exceed TextureCount %d."
                        % (over[:8], ts.declared_count),
                        "Add the missing textures, or repaint those tiles."))
            except Exception:                                # noqa: BLE001
                pass

        # objects
        af = sec / "areadata.txt"
        if af.exists():
            try:
                area = ad.AreaData.load(af)
            except Exception as exc:                         # noqa: BLE001
                out.append(Finding(
                    "M2MAP-ARD-001", "major", "%s/areadata.txt" % rel,
                    "objects missing from the sector",
                    "areadata.txt failed to parse: %s" % exc, "Fix the file."))
            else:
                for p in area.problems():
                    out.append(Finding(
                        "M2MAP-ARD-002", "minor", "%s/areadata.txt" % rel,
                        "some objects never appear", p,
                        "Make ObjectCount match the blocks."))
                if crcs is not None:
                    missing = sorted({r.crc for r in area.records} - crcs)
                    if missing:
                        out.append(Finding(
                            "M2MAP-ARD-004", "major", "%s/areadata.txt" % rel,
                            "objects are invisible in game",
                            "%d CRC(s) are not in the property DB: %s. An "
                            "unregistered CRC is dropped at load with no error, "
                            "no log and no placeholder."
                            % (len(missing), missing[:6]),
                            "Ship the property files, or repoint the records."))
                pos = [r for r in area.records if r.y > 0]
                if pos:
                    out.append(Finding(
                        "M2MAP-ARD-005", "major", "%s/areadata.txt" % rel,
                        "objects sit outside the map, or mirrored",
                        "%d record(s) have positive Y. areadata stores Y "
                        "NEGATED; every shipped file is negative." % len(pos),
                        "Negate Y on those records."))

        # water vs attr -- height aware, or it fires on a third of the corpus
        wf, at_f, hf = sec / "water.wtr", sec / "attr.atr", sec / "height.raw"
        if wf.exists() and at_f.exists() and hf.exists():
            try:
                wm = water_codec.read_water(wf)
                am = attr_codec.read_attr(at_f)
                hm = height_codec.read_height(hf)
                sub = _submerged_mask(wm, hm)
                if sub is not None and sub.any():
                    flag = (am.cells & attr_codec.ATTR_WATER).astype(bool)
                    sub_t = np.repeat(np.repeat(sub, 2, axis=0), 2, axis=1)[:256, :256]
                    unflagged = int((sub_t & ~flag).sum())
                    if unflagged > sub_t.sum() * 0.02:
                        out.append(Finding(
                            "M2MAP-WTR-001", "major", "%s/attr.atr" % rel,
                            "player runs across open water",
                            "%d cells are submerged (water surface above "
                            "terrain) but carry no ATTR_WATER."
                            % unflagged,
                            "OR 0x02 into those cells. Do not mask attr.atr."))
            except Exception:                                # noqa: BLE001
                pass

        # The plane's own edge showing as a 2 m staircase. Measured as the
        # share of the plane's outer boundary standing over ground BELOW its
        # surface: every such cell is a grid edge the player can see, because
        # nothing hides it. Corpus: metin2_map_c1 0.3%, b1 0.4%,
        # n_desert_01 1.2%, a1 2.5% -- planes run far past the shore and the
        # terrain draws the waterline over them. The one map that measures high
        # is metin2_map_eastplain_01 at 23.4%, which is flooded rather than
        # shored, so the threshold sits above it and this stays quiet on the
        # corpus.
        #
        # Cells on the sector's own rim are skipped: the plane usually continues
        # into the neighbouring sector, and counting them would report a seam as
        # a shoreline.
        if wf.exists() and hf.exists():
            try:
                wm = water_codec.read_water(wf)
                hm = height_codec.read_height(hf)
                terrain = hm.raw[:128, :128].astype(float)
                surf = np.full((128, 128), np.nan)
                for i, raw in enumerate(wm.heights):
                    surf[wm.cells == i] = float(raw)
                plane = np.isfinite(surf)
                if plane.sum() >= 200:
                    b = np.zeros_like(plane)
                    b[:-1, :] |= plane[:-1, :] & ~plane[1:, :]
                    b[1:, :] |= plane[1:, :] & ~plane[:-1, :]
                    b[:, :-1] |= plane[:, :-1] & ~plane[:, 1:]
                    b[:, 1:] |= plane[:, 1:] & ~plane[:, :-1]
                    b[0, :] = b[-1, :] = b[:, 0] = b[:, -1] = False
                    n_b = int(b.sum())
                    exposed = int((b & (surf > terrain)).sum())
                    # A FLOODED sector has no shoreline to get wrong: the plane
                    # covers everything and its boundary is bound to stand over
                    # water. metin2_map_battleroyale and metin2_map_trent02
                    # measure 100% exposed for exactly that reason, and
                    # metin2_map_eastplain_01 92% submerged. The rule is about a
                    # shore, so it needs one to exist.
                    submerged_share = float((plane & (surf > terrain)).sum()) /                         max(1, int(plane.sum()))
                    if n_b >= 40 and submerged_share < 0.80 and                             exposed > n_b * 0.30:
                        out.append(Finding(
                            "M2MAP-WTR-005", "info", "%s/water.wtr" % rel,
                            "the shoreline is a staircase",
                            "%d of %d cells on the water plane's outer boundary "
                            "(%.0f%%) stand over ground below the surface, so "
                            "the plane's own 2 m cell edge is what the player "
                            "sees. The corpus runs 0.3-2.5%%: its planes reach "
                            "well past the shore and the terrain that rises "
                            "through them draws the waterline instead."
                            % (exposed, n_b, 100.0 * exposed / n_b),
                            "Widen the plane past the basin -- "
                            "gen/water.py PLANE_OVERRUN is 1.2x the radius -- "
                            "rather than clipping it to the water. INFO, not a "
                            "defect: an interior pool set in a carved floor "
                            "trips this legitimately, and 5 shipped maps do "
                            "(devilscatacomb, milgyo, 12zi_stage, "
                            "eastplain_01/03). On an outdoor shore it is real."))
            except Exception:                                # noqa: BLE001
                pass

        # water planes far below every cell they cover: invisible in game, and
        # the classic symptom of writing centimetres into a raw-unit field.
        if wf.exists() and hf.exists():
            try:
                wm = water_codec.read_water(wf)
                surfaces = list(wm.world_heights())
                if surfaces:
                    hm = height_codec.read_height(hf)
                    terrain = hm.raw[1:129, 1:129].astype(float) * 0.5
                    lo, hi = float(terrain.min()), float(terrain.max())
                    for i, s in enumerate(surfaces):
                        if not (wm.cells == i).any():
                            continue
                        if float(s) < lo - 5000:
                            out.append(Finding(
                                "M2MAP-WTR-002", "major", "%s/water.wtr" % rel,
                                "water is invisible in game",
                                "Layer %d sits at %.0f cm, below every terrain "
                                "cell it covers (%.0f..%.0f). A plane under the "
                                "ground never renders. Classic cause: heights "
                                "written in centimetres into a field the format "
                                "defines in RAW units (worldZ = value * "
                                "HeightScale), which halves them."
                                % (i, s, lo, hi),
                                "Divide world cm by HeightScale when writing."))
                            break
            except Exception:                                # noqa: BLE001
                pass

    # --- server_attr ----------------------------------------------------
    saf = root / "server_attr"
    if saf.exists():
        try:
            sa = sa_codec.read_server_attr(saf)
            ok, bad = sa.verify()
            if bad:
                out.append(Finding(
                    "M2MAP-SRV-001", "blocker", "server_attr",
                    "server has no collision in part of the map",
                    "%d LZO block(s) do not decompress to 65536 bytes. Build "
                    "ignores the failure and boots anyway." % len(bad),
                    "Regenerate server_attr."))
            mx = max(int(sa.block(x, y).max())
                     for y in range(sa.height) for x in range(sa.width))
            if mx > 0x07:
                out.append(Finding(
                    "M2MAP-ATR-004", "blocker", "server_attr",
                    "every cell of the map is impassable on the server",
                    "server_attr carries values above 0x07 (max %d). The server "
                    "blocks on ATTR_BLOCK|ATTR_OBJECT (0x01|0x80) and Ymir "
                    "paints bit 7 on WALKABLE mountain, so an unmasked copy "
                    "blocks the whole map." % mx,
                    "Regenerate with attr masked to & 0x07."))
        except Exception as exc:                             # noqa: BLE001
            out.append(Finding(
                "M2MAP-SRV-003", "major", "server_attr",
                "server collision may be wrong",
                "server_attr failed to parse: %s" % exc, "Regenerate it."))
    elif not view.is_proxy:
        out.append(Finding(
            "M2MAP-SRV-002", "info", str(root),
            "no server collision file",
            "server_attr is absent. Expected in a client-only extraction; fatal "
            "in a map you are about to deploy.",
            "Generate it before deploying."))

    order = {s: i for i, s in enumerate(SEVERITIES)}
    out.sort(key=lambda f: (order.get(f.severity, 9), f.rule, f.where))
    return out


def _submerged_mask(wm, hm) -> Optional[np.ndarray]:
    """Water cells whose surface is above the terrain -- the only real water."""
    try:
        cells = wm.cells
        heights = list(wm.world_heights) if hasattr(wm, "world_heights") else list(wm.heights)
    except Exception:                                        # noqa: BLE001
        return None
    if not heights:
        return None
    raw = hm.raw[1:130, 1:130] if hm.raw.shape[0] >= 130 else hm.raw
    terrain = raw[:128, :128].astype(float) * 0.5
    out = np.zeros((128, 128), bool)
    for i, surf in enumerate(heights):
        m = cells == i
        if m.any():
            out |= m & (float(surf) > terrain)
    return out


def summarise(findings: Sequence[Finding]) -> Dict[str, int]:
    counts = {s: 0 for s in SEVERITIES}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    return counts

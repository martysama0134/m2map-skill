"""``.msenv`` codec -- the per-map environment preset.

Hierarchical ``Group Name { ... }`` / ``List Name { ... }`` script parsed by
``CTextFileLoader``.  Reader ``Environment_Load`` (GameLib/MapUtil.cpp:76-232),
defaults ``Environment_Init`` (MapUtil.cpp:4-74), writer
``CMapManagerAccessor::SaveEnvironmentScript``
(WorldEditor/DataCtrl/MapManagerEnvironment.cpp:350-486).

Notes from the source that matter:

* ``ScriptType`` is written but **never validated**.  Vanilla files carry the
  historical typo ``EnvrionmentData``; all 104 files under
  ``pack/yw_etc/ymir work/environment`` do.  :meth:`Environment.render_canonical`
  preserves it by default (WorldEditorRemix fixed the spelling, which is why
  its own output differs from every shipped file).
* ``List Gradient`` is only accepted when ``len(tokens) % 8 == 0`` **and**
  ``len(tokens)/8 == GradientLevelUpper + GradientLevelLower``
  (MapUtil.cpp:181-184).  A mismatch silently leaves the sky dome ungraded.
* ``List CloudColor`` is 8 floats = two RGBA rows (first/second colour).
* ``Fog.IsDensity`` is read into ``bDensityFog`` but never written back.
* ``Group Wind`` (``Enable``/``Strength``/``Random``) is a WorldEditorRemix
  extension; no vanilla file has it.
* Duplicate keys inside a group resolve first-wins (``std::map::insert``,
  TextFileLoader.cpp:39).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from .textfile import GroupDoc, GroupNode, atof, atoi, encode, parse_groups, quote

__all__ = ["Color", "DirLight", "SkyBox", "Environment",
           "ENV_KEY_INVENTORY", "SCRIPT_TYPE_TYPO"]

CRLF = "\r\n"

#: What every shipped file says -- yes, the typo is in the data.
SCRIPT_TYPE_TYPO = "EnvrionmentData"

#: Full key inventory, group -> keys.  ``+`` marks a nested Group,
#: ``*`` marks a List.
ENV_KEY_INVENTORY = {
    "": ["ScriptType", "ScriptVersion", "Reserved"],
    "DirectionalLight": ["Direction", "+Background", "+Character"],
    "DirectionalLight/Background": ["Enable", "Diffuse", "Ambient"],
    "DirectionalLight/Character": ["Enable", "Diffuse", "Ambient"],
    "Material": ["Diffuse", "Ambient", "Emissive"],
    "Fog": ["Enable", "IsDensity", "NearDistance", "FarDistance", "Color"],
    "Filter": ["Enable", "Color", "AlphaSrc", "AlphaDest"],
    "SkyBox": ["bTextureRenderMode", "Scale", "GradientLevelUpper",
               "GradientLevelLower", "FrontFaceFileName", "BackFaceFileName",
               "LeftFaceFileName", "RightFaceFileName", "TopFaceFileName",
               "BottomFaceFileName", "CloudScale", "CloudHeight",
               "CloudTextureScale", "CloudSpeed", "CloudTextureFileName",
               "*CloudColor", "*Gradient"],
    "LensFlare": ["Enable", "BrightnessColor", "MaxBrightness",
                  "MainFlareEnable", "MainFlareTextureFileName",
                  "MainFlareSize"],
    "Wind": ["Enable", "Strength", "Random"],   # WorldEditorRemix extension
}

SKYBOX_FACES = ("Front", "Back", "Left", "Right", "Top", "Bottom")


def _c(r=0.0, g=0.0, b=0.0, a=1.0):
    return [r, g, b, a]


def _fl(vals: Sequence[float]) -> str:
    return " ".join("%f" % v for v in vals)


@dataclass
class DirLight:
    enable: int = 0
    diffuse: List[float] = field(default_factory=lambda: _c(1, 1, 1, 1))
    ambient: List[float] = field(default_factory=lambda: _c(.5, .5, .5, 1))


@dataclass
class SkyBox:
    b_texture_render_mode: int = 0
    scale: List[float] = field(default_factory=lambda: [3500.0, 3500.0, 3500.0])
    gradient_level_upper: int = 0
    gradient_level_lower: int = 0
    faces: List[str] = field(default_factory=lambda: [""] * 6)
    has_faces: bool = False
    cloud_scale: List[float] = field(default_factory=lambda: [200000.0, 200000.0])
    cloud_height: float = 30000.0
    cloud_texture_scale: List[float] = field(default_factory=lambda: [4.0, 4.0])
    cloud_speed: List[float] = field(default_factory=lambda: [0.001, 0.001])
    cloud_texture_file_name: str = ""
    #: 8 floats: first RGBA then second RGBA.
    cloud_color: List[float] = field(default_factory=lambda: [0.0] * 8)
    #: One 8-float entry per gradient stop (first RGBA + second RGBA).
    gradient: List[List[float]] = field(default_factory=list)
    has_gradient_list: bool = False
    #: True when the list length matched upper+lower, i.e. the engine used it.
    gradient_accepted: bool = True


@dataclass
class Environment:
    """A parsed ``.msenv``.  Field defaults are ``Environment_Init``'s."""

    script_type: str = SCRIPT_TYPE_TYPO
    script_version: float = 1.0
    reserved: Optional[int] = None

    direction: List[float] = field(default_factory=lambda: [0.5, 0.5, -0.5])
    background: DirLight = field(default_factory=DirLight)
    character: DirLight = field(default_factory=DirLight)

    material_diffuse: List[float] = field(default_factory=lambda: _c(.8, .8, .8, 1))
    material_ambient: List[float] = field(default_factory=lambda: _c(.8, .8, .8, 1))
    material_emissive: List[float] = field(default_factory=lambda: _c(.8, .8, .8, 1))

    fog_enable: int = 0
    fog_is_density: Optional[int] = None
    fog_near_distance: float = 12800.0
    fog_far_distance: float = 17920.0
    fog_color: List[float] = field(default_factory=lambda: _c(.5, .5, .5, 1))

    filter_enable: int = 0
    filter_color: List[float] = field(default_factory=lambda: _c(.3, .1, .1, 0))
    filter_alpha_src: int = 2         # D3DBLEND_ONE
    filter_alpha_dest: int = 2

    skybox: SkyBox = field(default_factory=SkyBox)

    lensflare_enable: int = 0
    lensflare_brightness_color: List[float] = field(default_factory=lambda: _c(1, 1, 1, 1))
    lensflare_max_brightness: float = 1.0
    main_flare_enable: int = 0
    main_flare_texture_file_name: str = ""
    main_flare_size: float = 0.2

    #: WorldEditorRemix extension -- ``None`` when the group is absent.
    wind_enable: Optional[int] = None
    wind_strength: float = 0.0
    wind_random: float = 0.0

    doc: Optional[GroupDoc] = None

    # -- read --------------------------------------------------------------
    @classmethod
    def parse(cls, data) -> "Environment":
        doc = parse_groups(data)
        e = cls(doc=doc)
        root = doc.root
        e.script_type = root.get_str("scripttype", SCRIPT_TYPE_TYPO)
        v = root.get("scriptversion")
        if v:
            e.script_version = atof(v[0])
        r = root.get("reserved")
        if r:
            e.reserved = atoi(r[0])

        dl = root.child("directionallight")
        if dl:
            e.direction = dl.get_floats("direction", 3, e.direction)
            for name, tgt in (("background", "background"), ("character", "character")):
                node = dl.child(name)
                if node is None:
                    continue
                light = DirLight(enable=node.get_int("enable", 0),
                                 diffuse=node.get_floats("diffuse", 4, _c(1, 1, 1, 1)),
                                 ambient=node.get_floats("ambient", 4, _c(.5, .5, .5, 1)))
                setattr(e, tgt, light)

        mat = root.child("material")
        if mat:
            e.material_diffuse = mat.get_floats("diffuse", 4, e.material_diffuse)
            e.material_ambient = mat.get_floats("ambient", 4, e.material_ambient)
            e.material_emissive = mat.get_floats("emissive", 4, e.material_emissive)

        fog = root.child("fog")
        if fog:
            e.fog_enable = fog.get_int("enable", 0)
            if fog.get("isdensity") is not None:
                e.fog_is_density = fog.get_int("isdensity", 0)
            e.fog_near_distance = fog.get_float("neardistance", e.fog_near_distance)
            e.fog_far_distance = fog.get_float("fardistance", e.fog_far_distance)
            e.fog_color = fog.get_floats("color", 4, e.fog_color)

        flt = root.child("filter")
        if flt:
            e.filter_enable = flt.get_int("enable", 0)
            e.filter_color = flt.get_floats("color", 4, e.filter_color)
            e.filter_alpha_src = flt.get_int("alphasrc", e.filter_alpha_src) & 0xFF
            e.filter_alpha_dest = flt.get_int("alphadest", e.filter_alpha_dest) & 0xFF

        sb_node = root.child("skybox")
        if sb_node:
            e.skybox = cls._parse_skybox(sb_node)

        lf = root.child("lensflare")
        if lf:
            e.lensflare_enable = lf.get_int("enable", 0)
            e.lensflare_brightness_color = lf.get_floats(
                "brightnesscolor", 4, e.lensflare_brightness_color)
            e.lensflare_max_brightness = lf.get_float("maxbrightness", 1.0)
            e.main_flare_enable = lf.get_int("mainflareenable", 0)
            e.main_flare_texture_file_name = lf.get_str("mainflaretexturefilename", "")
            e.main_flare_size = lf.get_float("mainflaresize", 0.2)

        wind = root.child("wind")
        if wind:
            e.wind_enable = wind.get_int("enable", 0)
            e.wind_strength = wind.get_float("strength", 0.0)
            e.wind_random = wind.get_float("random", 0.0)
        return e

    @staticmethod
    def _parse_skybox(node: GroupNode) -> SkyBox:
        sb = SkyBox()
        sb.b_texture_render_mode = node.get_int("btexturerendermode", 0)
        sb.scale = node.get_floats("scale", 3, sb.scale)
        sb.gradient_level_upper = node.get_int("gradientlevelupper", 0) & 0xFF
        sb.gradient_level_lower = node.get_int("gradientlevellower", 0) & 0xFF
        for i, face in enumerate(SKYBOX_FACES):
            v = node.get(face.lower() + "facefilename")
            if v is not None:
                sb.has_faces = True
                sb.faces[i] = v[0] if v else ""
        sb.cloud_scale = node.get_floats("cloudscale", 2, sb.cloud_scale)
        sb.cloud_height = node.get_float("cloudheight", sb.cloud_height)
        sb.cloud_texture_scale = node.get_floats("cloudtexturescale", 2,
                                                 sb.cloud_texture_scale)
        sb.cloud_speed = node.get_floats("cloudspeed", 2, sb.cloud_speed)
        sb.cloud_texture_file_name = node.get_str("cloudtexturefilename", "")

        cc = node.get_list("cloudcolor")
        if cc is not None and len(cc) % 8 == 0 and cc:
            sb.cloud_color = [atof(x) for x in cc[:8]]

        grad = node.get_list("gradient")
        if grad is not None:
            sb.has_gradient_list = True
            want = sb.gradient_level_upper + sb.gradient_level_lower
            if len(grad) % 8 == 0 and len(grad) // 8 == want:
                sb.gradient = [[atof(x) for x in grad[i * 8:i * 8 + 8]]
                               for i in range(want)]
                sb.gradient_accepted = True
            else:
                # engine leaves SkyBoxGradientColorVector untouched (empty)
                sb.gradient = [[atof(x) for x in grad[i:i + 8]]
                               for i in range(0, len(grad) - 7, 8)]
                sb.gradient_accepted = False
        return sb

    @classmethod
    def load(cls, path) -> "Environment":
        with open(path, "rb") as fh:
            return cls.parse(fh.read())

    # -- checks ------------------------------------------------------------
    def problems(self) -> List[str]:
        out = []
        sb = self.skybox
        if sb.has_gradient_list and not sb.gradient_accepted:
            out.append("List Gradient has %d entries but GradientLevelUpper+Lower "
                       "is %d -- the engine discards the whole gradient"
                       % (len(sb.gradient),
                          sb.gradient_level_upper + sb.gradient_level_lower))
        if self.doc is not None and not self.doc.balanced:
            out.append("unbalanced braces")
        return out

    # -- write -------------------------------------------------------------
    def render(self) -> str:
        return self.doc.render() if self.doc is not None else self.render_canonical()

    def to_bytes(self) -> bytes:
        return encode(self.render())

    def save(self, path) -> None:
        with open(path, "wb") as fh:
            fh.write(self.to_bytes())

    def render_canonical(self, script_type: Optional[str] = None,
                         write_faces: Optional[bool] = None) -> str:
        """``SaveEnvironmentScript`` layout, indentation and all.

        ``PrintfTabs`` writes four spaces per level.  ``script_type`` defaults
        to the historical ``EnvrionmentData`` typo, which is what every shipped
        file carries and what a vanilla client round trip must preserve.
        """
        st = script_type if script_type is not None else self.script_type
        sb = self.skybox
        faces = sb.has_faces if write_faces is None else write_faces
        L: List[str] = []
        add = L.append

        add("ScriptType         %s" % st)
        add("ScriptVersion      %.4f" % self.script_version)
        add("")
        add("Group DirectionalLight")
        add("{")
        add("    Direction     %s" % _fl(self.direction))
        add("")
        for name, light in (("Background", self.background),
                            ("Character", self.character)):
            add("    Group %s" % name)
            add("    {")
            add("        Enable        %d" % light.enable)
            add("        Diffuse       %s" % _fl(light.diffuse))
            add("        Ambient       %s" % _fl(light.ambient))
            add("    }")
            if name == "Background":
                add("    ")
        add("}")
        add("Group Material")
        add("{")
        add("    Diffuse       %s" % _fl(self.material_diffuse))
        add("    Ambient       %s" % _fl(self.material_ambient))
        add("    Emissive      %s" % _fl(self.material_emissive))
        add("}")
        add("")
        if self.wind_enable is not None:
            add("Group Wind")
            add("{")
            add("    Enable    %d" % self.wind_enable)
            add("    Strength  %f" % self.wind_strength)
            add("    Random    %f" % self.wind_random)
            add("}")
            add("")
        add("Group Fog")
        add("{")
        add("    Enable        %d" % self.fog_enable)
        add("    NearDistance  %f" % self.fog_near_distance)
        add("    FarDistance   %f" % self.fog_far_distance)
        add("    Color         %s" % _fl(self.fog_color))
        add("}")
        add("")
        add("Group Filter")
        add("{")
        add("    Enable        %d" % self.filter_enable)
        add("    Color         %s" % _fl(self.filter_color))
        add("    AlphaSrc      %d" % self.filter_alpha_src)
        add("    AlphaDest     %d" % self.filter_alpha_dest)
        add("}")
        add("")
        add("Group SkyBox")
        add("{")
        if faces:
            add("    bTextureRenderMode    %d" % sb.b_texture_render_mode)
        add("    Scale                 %s" % _fl(sb.scale))
        add("    GradientLevelUpper    %d" % sb.gradient_level_upper)
        add("    GradientLevelLower    %d" % sb.gradient_level_lower)
        if faces:
            for i, face in enumerate(SKYBOX_FACES):
                add("    %sFaceFileName\t   %s" % (face, quote(sb.faces[i])))
        add("    ")
        add("    CloudScale            %s" % _fl(sb.cloud_scale))
        add("    CloudHeight           %f" % sb.cloud_height)
        add("    CloudTextureScale     %s" % _fl(sb.cloud_texture_scale))
        add("    CloudSpeed            %s" % _fl(sb.cloud_speed))
        add("    CloudTextureFileName  %s" % quote(sb.cloud_texture_file_name))
        add("    List CloudColor")
        add("    {")
        add("        %s" % _fl(sb.cloud_color[:4]))
        add("        %s" % _fl(sb.cloud_color[4:8]))
        add("    }")
        if sb.gradient:
            add("    List Gradient")
            add("    {")
            for k, entry in enumerate(sb.gradient):
                add("        %s" % _fl(entry[:4]))
                add("        %s" % _fl(entry[4:8]))
                if k < len(sb.gradient) - 1:
                    add("        ")
            add("    }")
        add("}")
        add("")
        add("Group LensFlare")
        add("{")
        add("    Enable                     %d" % self.lensflare_enable)
        add("    BrightnessColor            %s" % _fl(self.lensflare_brightness_color))
        add("    MaxBrightness              %f" % self.lensflare_max_brightness)
        add("    MainFlareEnable            %d" % self.main_flare_enable)
        add("    MainFlareTextureFileName   %s" % quote(self.main_flare_texture_file_name))
        add("    MainFlareSize              %f" % self.main_flare_size)
        add("}")
        add("")
        return "".join(l + CRLF for l in L)

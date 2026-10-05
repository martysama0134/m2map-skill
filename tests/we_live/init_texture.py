# Runs INSIDE WorldEditorRemix v61+ with --save. InitBaseTexture: every tile of the map becomes
# the init-brush texture -- in the view, and still after the save (fixme100).
import json, os
import WorldEditor as we
R = {}
we.GotoSector(1, 1)
we.SetInitTextureBrushVector([2])
r = we.InitBaseTexture()
probe = [we.GetTileValueAt(sx * 128 + 64, sy * 128 + 64) for sx in range(3) for sy in range(3)]
R["InitBaseTexture"] = [r == 1 and all(v == 2 for v in probe), "returned %r; window tiles %r" % (r, probe)]
open(os.path.join(os.path.dirname(__file__), "init_texture_result.json"), "w").write(json.dumps(R))

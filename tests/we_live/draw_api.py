# Runs INSIDE WorldEditorRemix v61+:  --map <copy of metin2_map_a1> --script draw_api.py --save
# Every draw binding, checked live; what it did is recorded so tests/test_we_live.py
# can read the SAVED files back with the skill's codecs.
import json, os
import WorldEditor as we

HERE = os.path.dirname(__file__)
R, DID = {}, {}


def check(name, fn):
    try:
        ok, detail = fn()
        R[name] = [bool(ok), str(detail)]
    except BaseException as e:
        R[name] = [False, "raised %s: %s" % (type(e).__name__, e)]


we.GotoSector(1, 1)          # window = sectors 0..2 x 0..2, edit sector (1, 1)


def height_pixel():
    gx, gy = 2 * 128 + 20, 1 * 128 + 30                     # sector (2, 1)
    h0 = we.GetHeightAt(gx, gy)
    nb0 = we.GetHeightAt(gx + 1, gy)
    we.DrawHeightPixel(gx, gy, h0 + 777)
    h1 = we.GetHeightAt(gx, gy)
    nb1 = we.GetHeightAt(gx + 1, gy)
    DID["height_pixel"] = [gx, gy, h0 + 777]
    return h1 == h0 + 777 and nb1 == nb0, "%d -> %d (want %d), neighbour %d -> %d" % (h0, h1, h0 + 777, nb0, nb1)
check("DrawHeightPixel", height_pixel)


def set_height():
    gx, gy = 1 * 128 + 60, 2 * 128 + 70                     # sector (1, 2)
    h0 = we.GetHeightAt(gx, gy)
    we.SetHeightAt(gx, gy, h0 + 555)
    h1 = we.GetHeightAt(gx, gy)
    DID["set_height"] = [gx, gy, h0 + 555]
    return h1 == h0 + 555, "%d -> %d (want %d)" % (h0, h1, h0 + 555)
check("SetHeightAt", set_height)


def height_region():
    x1, y1, x2, y2 = 0 * 128 + 50, 2 * 128 + 50, 0 * 128 + 53, 2 * 128 + 52   # sector (0, 2), 4x3
    h = 20000
    out0 = we.GetHeightAt(x2 + 1, y1)
    we.DrawHeightRegion(x2, y2, x1, y1, h)                  # inverted on purpose: it should swap
    inside = [we.GetHeightAt(x, y) for x in range(x1, x2 + 1) for y in range(y1, y2 + 1)]
    out1 = we.GetHeightAt(x2 + 1, y1)
    DID["height_region"] = [x1, y1, x2, y2, h]
    return all(v == h for v in inside) and out1 == out0, \
        "%d of %d at %d, outside %d -> %d" % (sum(v == h for v in inside), len(inside), h, out0, out1)
check("DrawHeightRegion", height_region)


def height_brush():
    gx, gy = 0 * 128 + 90, 0 * 128 + 90                     # sector (0, 0)
    h0 = we.GetHeightAt(gx, gy)
    we.DrawHeightBrush(gx, gy, we.BRUSH_SHAPE_CIRCLE, we.BRUSH_TYPE_UP, 3, 30)
    h1 = we.GetHeightAt(gx, gy)
    DID["height_brush"] = [gx, gy, h1]
    return h1 > h0, "%d -> %d" % (h0, h1)
check("DrawHeightBrush", height_brush)


def texture_brush():
    gx, gy = 2 * 128 + 64, 2 * 128 + 64                     # sector (2, 2)
    t0 = we.GetTileValueAt(gx, gy)
    far0 = we.GetTileValueAt(gx + 20, gy)
    tex = 1 if t0 != 1 else 2
    we.DrawTextureBrush(gx, gy, [tex], 2, 0, 0)
    t1 = we.GetTileValueAt(gx, gy)
    far1 = we.GetTileValueAt(gx + 20, gy)
    DID["texture_brush"] = [gx, gy, tex, t0]
    return t1 == tex and far1 == far0, "centre %d -> %d (want %d), 20 cells away %d -> %d" % (t0, t1, tex, far0, far1)
check("DrawTextureBrush", texture_brush)


def water_brush():
    gx, gy = 1 * 128 + 100, 0 * 128 + 100                   # sector (1, 0)
    wx, wy = gx * 200 + 100, gy * 200 + 100                 # world cm, positive y
    ground = we.GetHeightAt(gx, gy)
    level = ground + 400                                    # raw: 2 m over the ground
    w0 = we.GetWaterHeight(wx, wy)
    we.DrawWaterBrush(gx, gy, level, 2, 0)
    w1 = we.GetWaterHeight(wx, wy)
    far = we.GetWaterHeight(wx + 20 * 200, wy)
    DID["water_brush"] = [gx, gy, level, w0]
    # the brush takes RAW (height.raw units); GetWaterHeight answers world cm, as the engine's
    # CTerrain::GetWaterHeight does (raw / 2) -- the game's own unit for a water surface
    return w1 * 2 == level and far == -1, "centre %d -> %d cm (= %d raw, asked %d); 20 cells away %d" % (w0, w1, w1 * 2, level, far)
check("DrawWaterBrush", water_brush)


def attr_brush():
    gx, gy = 2 * 128 + 30, 0 * 128 + 30                     # sector (2, 0)
    x, y = gx * 200 + 50, gy * 200 + 50                     # world cm, positive y
    a0 = we.GetAttrAt(x, y)
    far0 = we.GetAttrAt(x + 3000, y)
    we.DrawAttrBrush(x, y, 4, 2, 0)                          # safezone bit, radius 2
    a1 = we.GetAttrAt(x, y)
    far1 = we.GetAttrAt(x + 3000, y)
    DID["attr_brush"] = [x, y, 4]
    ok_on = bool(a1 & 4) and far1 == far0
    # and erase it again on a second spot, to prove erase works, leaving the first painted
    x2 = x + 6000
    we.DrawAttrBrush(x2, y, 4, 2, 0)
    on2 = we.GetAttrAt(x2, y)
    we.DrawAttrBrush(x2, y, 4, 2, 1)
    off2 = we.GetAttrAt(x2, y)
    DID["attr_erase"] = [x2, y, 4]
    return ok_on and (on2 & 4) and not (off2 & 4), \
        "centre %d -> %d, 30 m away %d -> %d; erase spot on %d off %d" % (a0, a1, far0, far1, on2, off2)
check("DrawAttrBrush_and_erase", attr_brush)


def object_list_forms():
    a = we.GetObjectList(2, 1)
    b = we.GetObjectList([2, 1])
    c = we.GetObjectList((2, 1))
    e = we.GetObjectList()                                   # the edit sector: (1, 1) after GotoSector
    f = we.GetObjectList(1, 1)
    try:
        we.GetObjectList([2])
        bad = "no error"
    except TypeError as ex:
        bad = "TypeError"
    return (len(a) == len(b) == len(c) and len(e) == len(f) and bad == "TypeError"),         "(2,1) as two numbers %d / list %d / tuple %d; edit sector %d = (1,1) %d; [2] -> %s" % (len(a), len(b), len(c), len(e), len(f), bad)
check("GetObjectList_forms_and_edit_sector", object_list_forms)


def objects():
    lst = we.GetObjectList(1, 1)
    crcs = {}
    for o in lst:
        crcs[o[3]] = crcs.get(o[3], 0) + 1
    victim = max(crcs, key=lambda c: crcs[c])               # commonest CRC in sector (1, 1)
    n_before = crcs[victim]
    deleted = we.DeleteObjectsByCRCList([victim], 0)        # scope 0: the edit sector only
    after = [o for o in we.GetObjectList(1, 1) if o[3] == victim]
    other = [o for o in we.GetObjectList(0, 1) if o[3] == victim]
    DID["delete"] = [victim, n_before, deleted, len(other)]
    # insert a different CRC into sector (2, 1) at an exact spot
    ins_crc = [c for c in crcs if c != victim][0]
    x, y = 2 * 25600 + 12345.0, 1 * 25600 + 6789.0
    n0 = len(we.GetObjectList(2, 1))
    we.InsertObject(x, -y, 37.0, 0.0, 0.0, 123.0, 0, ins_crc)
    lst2 = we.GetObjectList(2, 1)
    hit = [o for o in lst2 if o[3] == ins_crc and abs(o[0] - x) < 1 and abs(abs(o[1]) - y) < 1]
    DID["insert"] = [ins_crc, x, y, 37.0, 123.0, hit[0] if hit else None, n0, len(lst2)]
    ok = deleted == n_before and not after and len(lst2) == n0 + 1 and bool(hit)
    return ok, "deleted %d of %d crc %d in (1,1) (left %d; sector (0,1) still has %d); inserted crc %d: %r" % (
        deleted, n_before, victim, len(after), len(other), ins_crc, hit[0] if hit else None)
check("DeleteObjectsByCRCList_and_InsertObject", objects)

open(os.path.join(HERE, "draw_api_result.json"), "w").write(json.dumps({"live": R, "did": DID}, indent=1))

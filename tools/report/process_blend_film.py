"""process_blend_film: the whole film of the storyboard, in Blender, every effect, by script alone.

    blender -b -P tools/report/process_blend_film.py -- still T OUT.png           one frame, at T seconds
    blender -b -P tools/report/process_blend_film.py -- stills OUTDIR T1,T2,... [SAMPLES]   several moments, one session
    blender -b -P tools/report/process_blend_film.py -- frames A B OUTDIR [SAMPLES]   frames A..B-1 as PNGs (skips those there)
    blender -b -P tools/report/process_blend_film.py -- blend OUT.blend           the scene, to open and look round in

Paul, 13 November: "now an animation in blender. can you do all the effects ... can we redo them all in
blender. Use all blender scripts. Is there a way to get the teleprompt scrolling in front of the camera."

THE SAME FILM, IN A PLACE. Nothing about what is said or when is decided here: the scenes, their lengths,
the cues, the camera's targets, which arrow is lit and where its token is at a given second are
process_film.py's and film.py's, imported. This script is only how that is built in three dimensions:

  the map      each territory a slab, each block risen out of its territory when the film first names it, each
               arrow a tube drawn on from its source to its destination;
  a step       the camera flies to the arrow; the source dips as the token sets out, the token travels with a
               trail, a ring opens where it crosses a border and it takes the next territory's colour, the
               destination swells as it lands and a yellow rectangle is drawn round it;
  the head-up  everything a viewer reads is IN FRONT OF THE CAMERA, parented to it one unit away: the step's
               words, the path down to the step, the small map of the whole, and the teleprompt, scrolling at
               the film's words a minute with the word being spoken lit. The camera moves; the words do not.
  the boards   the cold open (ten gains worth nothing; the same curve; signal and noise) and the closing shape
               stand upright as charts beside the map, and the camera travels along them and then to the map.

As in the drawn film every frame is a function of its time: `apply(t)` sets every object from t alone, so
frames render in any order and several Blenders can share the film (`frames A B`).
"""
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["still", "100", "/tmp/process-blend.png"]
sys.argv = sys.argv[:1]
sys.path.insert(0, HERE)
import process_film as pf  # noqa: E402
from film import clamp, smooth, out, back, seg, lerp, mix, appear, swell  # noqa: E402

K, SLAB, BLOCK = 0.01, 0.12, 0.42
INK, DIM, FAINT, BG, PANEL = pf.INK, pf.DIM, pf.FAINT, "#0a0b0d", "#101216"
YELLOW, RED = pf.LINE, pf.RED
HK = 1.2 / 1920            # a pixel of the drawn film, one unit in front of a 30 mm lens
FPS = pf.FPS


def P(x, y, z=0.0):
    return Vector(((x - 960) * K, (540 - y) * K, z))


def rgb(h):
    c = [int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    return [((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c] + [1.0]


# ---- materials: one that glows and takes no light (words, wires), one that stands in the light (bodies) --------

def glow(col, k=1.0):
    m = bpy.data.materials.new("glow")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    e, o = nt.nodes.new("ShaderNodeEmission"), nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(e.outputs[0], o.inputs[0])
    m["col"], m["k"] = col, k
    e.inputs[0].default_value, e.inputs[1].default_value = rgb(col), k
    return m


def set_glow(m, op=1.0, col=None, k=None):
    e = m.node_tree.nodes["Emission"]
    if col:
        e.inputs[0].default_value = rgb(col)
    e.inputs[1].default_value = (m["k"] if k is None else k) * op


def body(col, dark=0.8, shine=0.07):
    m = bpy.data.materials.new("body")
    m.use_nodes = True
    m["col"], m["dark"], m["shine"] = col, dark, shine
    set_body(m, 1.0)
    return m


def set_body(m, lit, col=None, hot=0.0):
    b = m.node_tree.nodes["Principled BSDF"]
    c = rgb(col or m["col"])
    d = m["dark"] * (1 - 0.22 * hot)
    b.inputs["Base Color"].default_value = [v * (1 - d) * lit + 0.004 for v in c[:3]] + [1.0]
    b.inputs["Roughness"].default_value = 0.45
    for k in ("Emission Color", "Emission"):
        if k in b.inputs:
            b.inputs[k].default_value = c
            break
    if "Emission Strength" in b.inputs:
        b.inputs["Emission Strength"].default_value = (m["shine"] + 0.22 * hot) * lit


FONTS = {}


def font(weight=400, serif=False):
    key = ("Georgia" if serif else "Arial") + (" Bold" if weight >= 600 else "")
    if key not in FONTS:
        try:
            FONTS[key] = bpy.data.fonts.load("/System/Library/Fonts/Supplemental/%s.ttf" % key)
        except RuntimeError:
            FONTS[key] = None
    return FONTS[key]


def link(o, parent=None):
    bpy.context.collection.objects.link(o)
    if parent:
        o.parent = parent
    return o


def text(s, size, m, loc, rot=(0, 0, 0), align="LEFT", weight=400, serif=False, parent=None, line=None):
    cu = bpy.data.curves.new("words", "FONT")
    cu.body, cu.size, cu.align_x = s, size, align
    f = font(weight, serif)
    if f:
        cu.font = f
    if line:
        cu.space_line = line
    cu.materials.append(m)
    o = link(bpy.data.objects.new("words", cu), parent)
    o.visible_shadow = False
    o.location, o.rotation_euler = loc, rot
    o["m"] = m.name
    return o


def show(o, on):
    o.hide_render = o.hide_viewport = not on


def say(o, s=None, op=1.0, col=None):
    """A line of words: what it says and how bright. Dark is gone."""
    show(o, op > 0.01 and (s is None or bool(s)))
    if op > 0.01:
        if s is not None and o.data.body != s:
            o.data.body = s
        set_glow(o.data.materials[0], op, col)


def written(s, p):
    return s if p >= 1 else s[:int(clamp(p) * (len(s) + 1))]


def cube(m, bevel=0.0, parent=None):
    me = bpy.data.meshes.new("box")
    v = [(x, y, z) for x in (-.5, .5) for y in (-.5, .5) for z in (-.5, .5)]
    me.from_pydata(v, [], [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
    me.materials.append(m)
    o = link(bpy.data.objects.new("box", me), parent)
    if bevel:
        mod = o.modifiers.new("bevel", "BEVEL")
        mod.width, mod.segments = bevel, 2
    return o


def place(o, lo, hi):
    """A box from one corner to the other."""
    o.location = [(a + b) / 2 for a, b in zip(lo, hi)]
    o.scale = [max(1e-4, abs(b - a)) for a, b in zip(lo, hi)]


def tube(pts, m, r=0.022, parent=None, cyclic=False):
    cu = bpy.data.curves.new("wire", "CURVE")
    cu.dimensions, cu.bevel_depth, cu.bevel_resolution = "3D", r, 4
    cu.bevel_factor_mapping_end = "SPLINE"
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for p_, q in zip(sp.points, pts):
        p_.co = (q[0], q[1], q[2], 1.0)
    sp.use_cyclic_u = cyclic
    cu.materials.append(m)
    o = link(bpy.data.objects.new("wire", cu), parent)
    o.visible_shadow = False
    return o


def ball(m, r, parent=None, torus=False):
    if torus:
        bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.035, major_segments=48, minor_segments=8)
    else:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=20, ring_count=10)
        bpy.ops.object.shade_smooth()
    o = bpy.context.object
    o.data.materials.append(m)
    o.visible_shadow = False
    if parent:
        o.parent = parent
    return o


def cone(m, r):
    bpy.ops.mesh.primitive_cone_add(radius1=r * 3.2, depth=r * 8, vertices=20)
    o = bpy.context.object
    o.data.materials.append(m)
    return o


# ---- the world, built once ----------------------------------------------------------------------------------

S = {}      # everything apply() moves, by name


def reg_col(n):
    return pf.REGIONS[pf.N[n][0]]["col"]


def build_map():
    grid = glow(INK, 0.03)
    for i in range(-40, 41):
        tube([P(i * 80 + 960, -2600), P(i * 80 + 960, 3700)], grid, r=0.0035)
        tube([P(-2300, i * 80 + 540), P(4200, i * 80 + 540)], grid, r=0.0035)
    bpy.ops.mesh.primitive_plane_add(size=600, location=(0, 0, -0.02))
    bpy.context.object.data.materials.append(body("#0e1013", 0.0, 0.0))
    S["reg"] = {}
    for k, r in pf.REGIONS.items():
        m = body(r["col"], 0.965, 0.01)
        o = cube(m, 0.05)
        a, b = P(r["x"], r["y"] + r["h"]), P(r["x"] + r["w"], r["y"])
        S["reg"][k] = dict(o=o, a=a, b=b, m=m,
                           small=text(r["name"], 0.2, glow(r["col"], 3.0), P(r["x"] + 22, r["y"] + 34, SLAB + 0.004), weight=700),
                           big=text(r["name"], 0.62 if k != "main" else 0.5, glow(r["col"], 3.0), P(r["x"] + r["w"] / 2, r["y"] + r["h"] / 2 + 14, SLAB + 0.004), align="CENTER", weight=700),
                           sub=text(r["sub"], 0.24, glow(INK, 1.6), P(r["x"] + r["w"] / 2, r["y"] + r["h"] / 2 + 56, SLAB + 0.004), align="CENTER"))
    lb = pf.LINE_BOX
    S["linebox"] = tube([P(lb["x"], lb["y"], SLAB + 0.012), P(lb["x"] + lb["w"], lb["y"], SLAB + 0.012), P(lb["x"] + lb["w"], lb["y"] + lb["h"], SLAB + 0.012),
                         P(lb["x"], lb["y"] + lb["h"], SLAB + 0.012)], glow(YELLOW, 2.0), r=0.008, cyclic=True)
    S["node"] = {}
    for n, (k, x, y, w, h, title, sub) in pf.N.items():
        col = pf.REGIONS[k]["col"]
        m = body(col, 0.80, 0.07)
        o = cube(m, 0.03)
        S["node"][n] = dict(o=o, m=m, x=x, y=y, w=w, h=h,
                            t1=text(title, 0.24, glow(INK, 2.4), P(x + 16, y + 38, SLAB + BLOCK + 0.004), weight=600),
                            t2=text(sub, 0.14, glow(col, 1.6), P(x + 16, y + 66, SLAB + BLOCK + 0.004)))
    S["arrow"] = {}
    z = SLAB + BLOCK * 0.55
    for s in pf.STEPS:
        col = reg_col(s["a"])
        m = glow(col, 3.0)
        pts = pf.path_of(s)
        cu = tube([P(q[0], q[1], z) for q in pts], m)
        hd = cone(m, 0.022)
        a, b = P(*pts[-2]), P(*pts[-1])
        ang = math.atan2(b.y - a.y, b.x - a.x)
        hd.location, hd.rotation_euler = (b.x - math.cos(ang) * 0.09, b.y - math.sin(ang) * 0.09, z), (0, math.pi / 2, ang)
        S["arrow"][s["id"]] = dict(o=cu, head=hd, m=m, col=col)
    # what moves: one token, its trail, its name, the two rings of a border crossed, the rectangle of a landing
    tm = glow(YELLOW, 5.0)
    S["tok"] = dict(o=ball(tm, 0.085), m=tm, trail=[], label=text("", 0.2, glow(INK, 3.0), (0, 0, 0), align="CENTER", weight=600), plate=cube(glow(BG, 1.0)))
    S["tok"]["plate"].visible_shadow = False
    for i in range(8):
        mm = glow(YELLOW, 3.0)
        S["tok"]["trail"].append((ball(mm, 0.07 - i * 0.006), mm))
    S["rip"] = []
    for _ in range(2):
        mm = glow(YELLOW, 4.0)
        S["rip"].append((ball(mm, 0, torus=True), mm))
    S["ind"] = tube([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 0)], glow(YELLOW, 4.0), r=0.016)
    # the whole: four thick arrows between the territories, each with its words lying beside it
    S["big"] = []
    for (a, b, col, words, off) in (((1290, 236), (1290, 376), pf.CPU, "what the game is now", -26), ((1440, 376), (1440, 236), pf.MAIN, "only what was proved better", 26),
                                    ((370, 236), (370, 376), pf.GPU, "the rules of the world", -26), ((520, 376), (520, 236), pf.MAIN, "only a net the game credits", 26)):
        m = glow(col, 4.0)
        cu = tube([P(a[0], a[1], 0.75), P(b[0], b[1], 0.75)], m, r=0.06)
        hd = cone(m, 0.06)
        d = 1 if b[1] > a[1] else -1
        hd.location, hd.rotation_euler = P(b[0], b[1] - d * 20, 0.75), (0, math.pi / 2, -d * math.pi / 2)
        tx = text(words, 0.25, glow(INK, 2.6), P(a[0] + off, 352, 0.78), align="LEFT" if off > 0 else "RIGHT", weight=600)
        S["big"].append(dict(o=cu, head=hd, m=m, t=tx))
    S["border"] = []
    for col, pts in ((pf.CPU, [(1000, 282), (1880, 282)]), (YELLOW, [(1000, 300), (1000, 770)]), (pf.MAIN, [(1000, 306), (1880, 306)]), (pf.GPU, [(40, 300), (920, 300)])):
        m = glow(col, 5.0)
        S["border"].append((tube([P(q[0], q[1], 0.5) for q in pts], m, r=0.05), m))
    bpy.ops.object.light_add(type="SUN", location=(0, 0, 30))
    sun = bpy.context.object
    sun.data.energy, sun.rotation_euler = 1.1, (math.radians(38), 0, math.radians(-28))
    bpy.ops.object.light_add(type="AREA", location=(9, -6, 10))
    bpy.context.object.data.energy, bpy.context.object.data.size = 350, 16


# ---- the head-up display: everything read, one unit in front of the lens ------------------------------------

def H(px, py, layer=0):
    return Vector(((px - 960) * HK, (540 - py) * HK, -1.0 + layer * 0.002))


def hud(s, px, py, size, col, k=1.0, weight=400, align="LEFT", layer=2, serif=False, line=None):
    return text(s, size * HK, glow(col, k), H(px, py, layer), align=align, weight=weight, serif=serif, parent=S["cam"], line=line)


def panel(x0, y0, x1, y1, col, layer=0, k=1.0):
    m = glow(col, k)
    o = cube(m, parent=S["cam"])
    a, b = H(x0, y1, layer), H(x1, y0, layer)
    place(o, (a.x, a.y, a.z - 0.0002), (b.x, b.y, a.z))
    o["m"] = m.name
    return o


def pshow(o, op):
    show(o, op > 0.5)


def build_hud():
    bpy.ops.object.camera_add()
    cam = S["cam"] = bpy.context.object
    cam.data.lens, cam.data.clip_start, cam.data.clip_end = 30, 0.05, 600
    bpy.context.scene.camera = cam
    h = S["hud"] = {}
    # the step's words
    h["low"] = panel(-10, 690, 1930, 1090, BG)
    h["lowline"] = panel(-10, 688, 1930, 692, pf.CPU, 1, 2.0)
    h["label"] = hud("", 60, 726, 17, pf.CPU, 2.4, 700)
    h["a"] = hud("", 60, 774, 40, INK, 2.6, 600)
    h["to"] = hud("→", 0, 774, 40, pf.CPU, 3.0, 700)
    h["b"] = hud("", 0, 774, 40, INK, 2.6, 600)
    h["rows"] = [(hud("", 60, 0, 13.5, pf.CPU, 2.4, 700), hud("", 214, 0, 22, INK, 2.2, line=29 / 22.0)) for _ in range(4)]
    # the path down to the step
    h["crumbbg"] = panel(28, 26, 760, 66, BG)
    h["crumb"] = [hud("", 44, 52, 16, DIM, 2.2, 600), hud("", 0, 52, 16, pf.CPU, 2.6, 700), hud("", 0, 52, 16, INK, 2.4, 600)]
    # the small map of the whole
    h["mini"] = dict(bg=panel(1568, 18, 1888, 206, BG), nodes={}, regs=[])
    k, ox, oy = 0.158, 1576, 26
    for r in pf.REGIONS.values():
        h["mini"]["regs"].append(panel(ox + r["x"] * k, oy + r["y"] * k, ox + (r["x"] + r["w"]) * k, oy + (r["y"] + r["h"]) * k, mix(BG, r["col"], 0.22), 1))
    for n, (rk, x, y, w, hh, _, _) in pf.N.items():
        h["mini"]["nodes"][n] = panel(ox + x * k, oy + y * k, ox + (x + w) * k, oy + (y + hh) * k, mix(BG, pf.REGIONS[rk]["col"], 0.55), 2)
    h["minit"] = hud("where this step is in the whole", 1576, 196, 13, DIM, 1.8)
    # THE TELEPROMPT, in front of the camera
    tp = pf.TP
    h["tp"] = panel(tp["x"], tp["y"], tp["x"] + tp["w"], tp["y"] + tp["h"], "#050607", 3)
    h["tpmask"] = panel(tp["x"], tp["y"], tp["x"] + tp["w"], tp["y"] + 40, "#050607", 5)
    h["tphead"] = hud("NARRATION  ·  %d WORDS A MINUTE" % pf.WPM, tp["x"] + 18, tp["y"] + 27, 12.5, DIM, 2.0, 700, layer=6)
    h["tpmark"] = panel(tp["x"] + 8, tp["y"] + 50 + 34 * 1.2 - 19, tp["x"] + 13, tp["y"] + 50 + 34 * 1.2 + 3, YELLOW, 6, 3.0)
    t = h["tptext"] = hud("", tp["x"] + 26, 0, 23.5, INK, 2.4, layer=4, line=34 / 23.5)
    t.data.materials.clear()
    for col, kk in ((INK, 2.3), (YELLOW, 3.4), (INK, 0.75)):       # to come, being spoken, spoken
        t.data.materials.append(glow(col, kk))
    # what the other scenes say on the glass
    # WORDS OVER A MOVING PICTURE STAND ON A PLATE (Paul, 13 November: "It needs to be in the background, so some
    # clear way to make words on the screen stand out"). Nothing read is ever laid straight over the fields.
    h["headbg"] = panel(28, 28, 980, 108, BG)
    h["credits"] = [hud("", 960, 590 + i * 44, 30 if i == 0 else 24, INK if i < 2 else DIM, 2.6, 700 if i == 0 else 400, "CENTER") for i in range(len(pf.STORY.get("credits", [])))]
    h["head"] = hud("", 60, 62, 22, INK, 2.4, 700)
    h["head2"] = hud("", 60, 92, 19, DIM, 2.0)
    h["band"] = panel(-10, 380, 1930, 790, BG)
    h["c1"] = hud("", 960, 520, 84, INK, 3.0, 700, "CENTER")
    h["c2"] = hud("", 960, 584, 34, INK, 2.4, 400, "CENTER")
    h["c3"] = hud("", 960, 646, 22, DIM, 2.0, 400, "CENTER")
    h["legend"] = [(hud("■", 60, 836 + i * 56, 22, c, 3.0), hud("", 92, 836 + i * 56, 28, INK, 2.4, 600), hud("", 420, 836 + i * 56, 28, DIM, 2.2))
                   for i, c in enumerate((pf.CPU, YELLOW, pf.MAIN, pf.GPU))]
    h["jpanel"] = panel(-10, 800, 1930, 1090, BG)
    h["jlabel"] = hud("", 60, 852, 18, pf.CPU, 2.4, 700)
    h["jwords"] = hud("", 60, 912, 36, INK, 2.6, 500, line=48 / 36.0)


# ---- the boards: charts standing beside the map --------------------------------------------------------------

K2 = 0.012
BOARD = {"hook1": -112.0, "hook2": -82.0, "hook3": -52.0, "pattern": 46.0}
BY = -6.0


def B(k, px, py, d=0.0):
    """A point of a board's drawing (the drawn film's own pixels) on the board: across, and up."""
    return Vector((BOARD[k] + (px - 960) * K2, BY - d, (1080 - py) * K2))


def btext(k, s, px, py, size, col, kk=2.4, weight=400, align="LEFT", serif=False, d=0.3):
    return text(s, size * K2, glow(col, kk), B(k, px, py, d), rot=(math.pi / 2, 0, 0), align=align, weight=weight, serif=serif)


def bbox_(k, m, x0, y0, x1, y1, depth=0.5, bevel=0.03):
    o = cube(m, bevel)
    a, b = B(k, x0, y1), B(k, x1, y0)
    place(o, (a.x, BY - depth / 2, a.z), (b.x, BY + depth / 2, b.z))
    return o


def build_boards():
    hk, b = pf.HOOK, S.setdefault("board", {})
    # one: ten gains stacked, and the ten measured together
    base, k, x0, bw, x1 = 860, 92.0, 300, 250, 1000
    h1 = b["hook1"] = dict(blocks=[], base=base, k=k, x0=x0, bw=bw, x1=x1)
    bbox_("hook1", body(DIM, 0.5, 0.2), 200, base, 1340, base + 6, 0.8, 0)
    y = base
    for i, (run, v) in enumerate(hk["claims"]):
        hgt = v * k
        y -= hgt
        m = body(pf.CPU, 0.55 + 0.1 * (i % 2), 0.12)
        h1["blocks"].append(dict(o=bbox_("hook1", m, x0, y + 2, x0 + bw, y + hgt - 2), z=B("hook1", 0, y + hgt / 2).z, v=v,
                                 t=btext("hook1", "+%.2f" % v, x0 + bw / 2, y + hgt / 2 + 9, 24, INK, 2.6, 400, "CENTER", True) if hgt > 28 else None,
                                 r=btext("hook1", run, x0 - 16, y + hgt / 2 + 6, 15, DIM, 2.0, 400, "RIGHT")))
    full = sum(v for _, v in hk["claims"]) * k
    h1.update(top=y, full=full, cap1=btext("hook1", "ten changes, each one tested", x0 + bw / 2, base + 44, 24, INK, 2.4, 400, "CENTER"),
              total=btext("hook1", "", x0 + bw + 40, y + 60, 76, pf.CPU, 3.0, 700, serif=True),
              sub=btext("hook1", "", x0 + bw + 44, y + 100, 24, DIM, 2.2),
              cap2=btext("hook1", "all ten, measured together", x1 + bw / 2, base + 44, 24, INK, 2.4, 400, "CENTER"),
              exp=btext("hook1", "", x1 + bw / 2, base - full - 22, 22, YELLOW, 2.8, 400, "CENTER"),
              ghost=[cube(glow(YELLOW, 2.6)) for _ in range(3)],
              bar=bbox_("hook1", glow(RED, 4.0), x1, base - 4 - hk["proof"][0] * k, x1 + bw, base + 1 - hk["proof"][0] * k, 0.6, 0),
              whisk=bbox_("hook1", glow(RED, 4.0), x1 + bw / 2 - 2, base - (hk["proof"][0] + 2 * hk["proof"][1]) * k, x1 + bw / 2 + 2, base - (hk["proof"][0] - 2 * hk["proof"][1]) * k, 0.62, 0),
              num=btext("hook1", "", x1 + bw / 2, base - 70, 64, RED, 3.4, 700, "CENTER", True),
              said=btext("hook1", "what %s games said" % format(hk["proof"][2], ","), x1 + bw / 2, base - 132, 22, DIM, 2.2, 400, "CENTER"))
    # two: every trial by its score, and the curve of no effect at all
    hist, n = hk["hist"], hk["trials"]
    hx0, hx1, hb, ht = 200, 1260, 800, 250
    w_ = (hx1 - hx0) / len(hist)
    sy = (hb - ht) / max(hist)
    h2 = b["hook2"] = dict(bars=[], x0=hx0, x1=hx1, base=hb, w=w_, sy=sy)
    bbox_("hook2", body(DIM, 0.5, 0.2), hx0 - 20, hb, hx1 + 20, hb + 6, 0.8, 0)
    for i, c in enumerate(hist):
        m = body(pf.GPU, 0.35, 0.25)
        h2["bars"].append(dict(o=cube(m, 0.02), m=m, c=c, i=i))
        if i % 2 == 0:
            btext("hook2", "%+d" % (i / 2 - 4) if i != 8 else "0", hx0 + i * w_, hb + 34, 20, DIM, 2.0, 400, "CENTER", True)
    btext("hook2", "+4", hx1, hb + 34, 20, DIM, 2.0, 400, "CENTER", True)
    btext("hook2", "its score, in units of its own error", (hx0 + hx1) / 2, hb + 76, 22, DIM, 2.0, 400, "CENTER")
    pts = [B("hook2", hx0 + (z_ + 4) / 8 * (hx1 - hx0), hb - n * 0.5 * math.exp(-z_ * z_ / 2) / math.sqrt(2 * math.pi) * sy, 0.45) for z_ in [-4 + j * 0.05 for j in range(161)]]
    h2.update(curve=tube(pts, glow(YELLOW, 4.0), r=0.035), none=btext("hook2", "", hx1 - 250, ht + 70, 26, YELLOW, 2.8),
              same=btext("hook2", "", (hx0 + hx1) / 2, ht - 44, 54, INK, 3.0, 700, "CENTER", True),
              kept=btext("hook2", "", (hx0 + 12 * w_ + hx1 - 60) / 2, hb - 186, 26, YELLOW, 3.0, 700, "CENTER"),
              again=btext("hook2", "", (hx0 + hx1) / 2, hb - 196, 30, YELLOW, 3.0, 700, "CENTER", d=0.9),
              dots=[ball(glow(YELLOW, 4.0), 0.075) for _ in range(54)])
    # three: the scale of the problem, to scale
    k3, x3 = 118.0, 200
    b["hook3"] = dict(k=k3, x=x3, m1=None,
                      bar1=cube(body(pf.GPU, 0.35, 0.3), 0.03), bar2=cube(glow(YELLOW, 2.2), 0.0),
                      t1=btext("hook3", "", x3, 228, 34, INK, 2.6), t2=btext("hook3", "", x3, 408, 34, YELLOW, 3.0),
                      s1=btext("hook3", "", x3, 660, 44, INK, 2.8, 400, serif=True), s2=btext("hook3", "", x3, 726, 44, INK, 2.8, 400, serif=True))
    # the last: one shape, at every border
    pw, gap, px0, py = 262, 34, 78, 230
    pt = b["pattern"] = dict(title=btext("pattern", "", 960, 150, 64, INK, 3.0, 700, "CENTER"), top=[], rows=[], last=[])
    for i, (name, sub) in enumerate(pf.PATTERN):
        x = px0 + i * (pw + gap)
        pt["top"].append(dict(o=bbox_("pattern", body(INK, 0.86, 0.05), x, py, x + pw, py + 120, 0.5), z=B("pattern", 0, py + 60).z,
                              t=btext("pattern", name, x + pw / 2, py + 52, 32, INK, 2.8, 700, "CENTER"),
                              s=btext("pattern", "\n".join(pf.wrap(sub, 17, pw - 24)), x + pw / 2, py + 82, 17, DIM, 2.0, 400, "CENTER"),
                              w=tube([B("pattern", x - gap + 4, py + 60, 0.2), B("pattern", x - 6, py + 60, 0.2)], glow(INK, 3.0), r=0.02) if i else None))
    for r, (name, col, cells) in enumerate(pf.PATTERN_ROWS):
        yy = 452 + r * 124
        row = dict(name=btext("pattern", name.upper(), px0, yy - 16, 20, col, 3.0, 700), cells=[])
        for i, c in enumerate(cells):
            x = px0 + i * (pw + gap)
            ls = pf.wrap(c, 21, pw - 20)
            row["cells"].append(dict(o=bbox_("pattern", body(col, 0.72, 0.1), x, yy, x + pw, yy + 78, 0.4), z=B("pattern", 0, yy + 39).z,
                                     t=btext("pattern", "\n".join(ls), x + pw / 2, yy + (46 if len(ls) == 1 else 34), 21, INK, 2.6, 400, "CENTER")))
        pt["rows"].append(row)
    for kk, l in enumerate(["A guess is cheap. A crossing is earned, on seeds the guess never saw.", "And every verdict goes back to where the guess was made."]):
        pt["last"].append((btext("pattern", "", 78, 880 + kk * 46, 33, INK, 2.8), l))


# ---- the battles: the recordings, reenacted behind the map ---------------------------------------------------
#
# Paul, 13 November: "taking the data and the generations of the recording showing the bots and their traces, in a
# multidimensional battle decision best of montage background, behind the blocks and animations ... 3d assets
# that run from the recording files. design it in the easy way, simply."
#
# The recording is docs/process/battles.json (tools/report/battles.py: crucible's own trace of four generations,
# 48 duels each from one start in one arena). Each generation has a field behind the map, oldest on the left.
# On it stand the arena's pillars, pillboxes, groves and walls; the champion's path in EVERY duel is drawn faint,
# all from the one start (the many ways the same moment went: blue where it won, red where it lost); and its
# best duels are played by two small tanks, one after another, three times the speed they were fought at, the
# path of the duel in hand drawn behind the champion as it goes, a shell a bright bead, a hit a flash.
AK, ARENA_Y, PLAY = 0.14, 10.9, 3.0
TANK = 4.5       # a tank is drawn this many times its size: at a field's scale a true one is a speck


def A(g, x, y, z=0.0):
    c = S["battle"]["half"]
    return Vector((g["cx"] + (x - c) * AK, ARENA_Y + (y - c) * AK, z))


def tank(col):
    bpy.ops.object.empty_add()
    e = bpy.context.object
    m = body(col, 0.25, 0.35)
    for lo, hi in (((-0.5, -0.36, 0), (0.5, 0.36, 0.3)), ((-0.22, -0.22, 0.3), (0.22, 0.22, 0.5)), ((0.1, -0.05, 0.36), (0.8, 0.05, 0.44))):
        o = cube(m, parent=e)
        place(o, [v * AK * TANK for v in lo], [v * AK * TANK for v in hi])
    return e


def build_battles():
    path = os.path.join(os.path.dirname(pf.STORY_PATH), "battles.json")
    if not os.path.exists(path):
        S["battle"] = None
        return
    import json
    d = json.load(open(path))
    gens = d["generations"]
    bt = S["battle"] = dict(half=d["arena"] / 2, dt=d["dt"], hp=d["hp"], pb_hp=d["pb_hp"], gens=[])
    size = d["arena"] * AK
    pitch = size + 0.7
    stone, wood, leaf = body("#8a8f98", 0.55, 0.05), body("#b08a5a", 0.5, 0.05), body("#4f8a4a", 0.45, 0.08)
    for gi, gd in enumerate(gens):
        g = dict(cx=(gi - (len(gens) - 1) / 2) * pitch, data=gd, pbs=[], trails=[])
        o = cube(body("#141a22", 0.0, 0.0))
        place(o, A(g, 0, 0, 0.0), A(g, d["arena"], d["arena"], 0.02))
        a, b = A(g, 0, 0, 0.03), A(g, d["arena"], d["arena"], 0.03)
        g["rim"] = glow(pf.GPU, 1.6)
        tube([a, (b.x, a.y, a.z), b, (a.x, b.y, a.z)], g["rim"], r=0.03, cyclic=True)
        g["name"] = text("generation %s" % format(gd["gen"], ","), 0.42, glow(INK, 2.4), (a.x, a.y - 0.55, 0.03), weight=700)
        text("%s  ·  won %d of %d, lost %d" % (gd["name"], gd["won"], d["duels"], gd["lost"]), 0.24, glow(pf.GPU, 2.2), (a.x, a.y - 0.92, 0.03))
        for x, y, r in d["pillars"]:
            bpy.ops.mesh.primitive_cylinder_add(radius=r * AK, depth=0.5, location=A(g, x, y, 0.25), vertices=20)
            bpy.context.object.data.materials.append(stone)
        for x, y, r in d["groves"]:
            bpy.ops.mesh.primitive_cone_add(radius1=r * AK, depth=0.55, location=A(g, x, y, 0.28), vertices=16)
            bpy.context.object.data.materials.append(leaf)
        for x0, y0, x1, y1 in d["walls"]:
            place(cube(wood), A(g, x0, y0, 0.0), A(g, x1, y1, 0.3))
        for x, y in d["boxes"]:
            m = body(YELLOW, 0.4, 0.3)
            bpy.ops.mesh.primitive_cylinder_add(radius=1.1 * AK, depth=1.0, location=A(g, x, y, 0.2), vertices=6)
            o = bpy.context.object
            o.data.materials.append(m)
            g["pbs"].append((o, m))
        # every duel's path from the one start: the fan of what the same moment became
        win, lose, draw = glow(pf.GPU, 0.45), glow(RED, 0.38), glow(INK, 0.07)
        outcome = {}
        for bd in gd["best"]:
            outcome[bd["duel"]] = bd["outcome"]
        order = sorted(range(len(gd["ghosts"])), key=lambda k: k)
        for k in order:
            pts = gd["ghosts"][k]
            if len(pts) > 1:
                # a duel's end tells how it went: the trace gives won, lost, drawn only for the best; the rest are drawn plain
                tube([A(g, x, y, 0.05) for x, y in pts], win if outcome.get(k) == 1 else lose if outcome.get(k) == -1 else draw, r=0.012)
        g["me"], g["foe"] = tank(pf.GPU), tank(pf.CPU)
        g["shell"] = [ball(glow(YELLOW, 6.0), 0.07), ball(glow(YELLOW, 6.0), 0.07)]
        g["flash"] = [(ball(m_, 1.0), m_) for m_ in (glow("#ffffff", 8.0), glow("#ffffff", 8.0))]
        for bd in gd["best"]:
            g["trails"].append(tube([A(g, r[0], r[1], 0.09) for r in bd["rec"][::3]] + [A(g, bd["rec"][-1][0], bd["rec"][-1][1], 0.09)], glow(pf.GPU, 3.2), r=0.028))
        g["spans"] = [len(bd["rec"]) * d["dt"] / PLAY + 2.0 for bd in gd["best"]]
        bt["gens"].append(g)


def battle_at(t, spot=None):
    """Every field at t. THE FIELDS FOLLOW THE SCRIPT: a step or a journey of the storyboard may name a
    generation ("field": "M0030"), and while it is told that generation's field is lit and the others stand back."""
    bt = S["battle"]
    if not bt:
        return
    for gi, g in enumerate(bt["gens"]):
        on = spot is None or g["data"]["name"] == spot
        set_glow(g["rim"], (3.2 if spot else 1.0) if on else 0.25, YELLOW if (spot and on) else pf.GPU)
        set_glow(g["name"].data.materials[0], 1.0 if on else 0.3, YELLOW if (spot and on) else INK)
        total = sum(g["spans"])
        u = (t + gi * 7.3) % total            # each field at its own place in its round, so they are never in step
        k = 0
        while u >= g["spans"][k]:
            u -= g["spans"][k]
            k += 1
        rec = g["data"]["best"][k]["rec"]
        f = min(len(rec) - 1.001, u * PLAY / bt["dt"])
        i = int(f)
        a, b, fr = rec[i], rec[i + 1], f - i
        for j, tr in enumerate(g["trails"]):
            show(tr, j == k)
        g["trails"][k].data.bevel_factor_end = max(0.002, (i + fr) / (len(rec) - 1))
        for o, off, hit in ((g["me"], 0, 19), (g["foe"], 7, 18)):
            alive = a[off + 3] > 0
            o.location = A(g, lerp(a[off], b[off], fr), lerp(a[off + 1], b[off + 1], fr), 0.03)
            dh = (b[off + 2] - a[off + 2] + math.pi) % (2 * math.pi) - math.pi
            o.rotation_euler = (0, 0, a[off + 2] + dh * fr)
            for c_ in o.children:
                show(c_, alive)
        for j, off in enumerate((0, 7)):
            sh = g["shell"][j]
            on = a[off + 6] > 0 and b[off + 6] > 0
            show(sh, on)
            if on:
                sh.location = A(g, lerp(a[off + 4], b[off + 4], fr), lerp(a[off + 5], b[off + 5], fr), 0.14)
        # a hit: a flash where the struck tank stood, for half a second of the duel
        for j, (ev, off) in enumerate(((18, 7), (19, 0))):
            fl, m = g["flash"][j]
            age = next((i - s_ + fr for s_ in range(i, max(-1, i - 6), -1) if int(rec[s_][ev]) == 1), None)
            show(fl, age is not None)
            if age is not None:
                kk = age / 6.0
                dead = rec[min(len(rec) - 1, i + 1)][off + 3] <= 0
                fl.location = A(g, rec[i][off], rec[i][off + 1], 0.2)
                fl.scale = [(0.12 + (0.9 if dead else 0.35) * out(kk))] * 3
                set_glow(m, 1 - kk, YELLOW if dead else "#ffffff")
        for (o, m), hp in zip(g["pbs"], a[14:18]):
            show(o, hp > 0)
            if hp > 0:
                o.scale = (1, 1, 0.25 + 0.75 * hp / bt["pb_hp"])


# ---- the camera: where it is and what it looks at, at t ----------------------------------------------------

def map_pose(t):
    cx, cy, z = pf.camera(t)
    aim = P(cx, cy)
    e = math.radians(lerp(84, 44, seg(z, pf.FAR, 1.0)))      # low enough that the fields behind the map are in the picture
    d = 17.5 / z
    return aim + Vector((0, -math.cos(e) * d, math.sin(e) * d)), aim


def board_pose(k):
    """In front of a board, square on, at the distance where a pixel of the drawn film is a pixel here: the
    charts were laid out to keep clear of the teleprompt's corner, and at this distance they still do."""
    d = pf.W * K2 / 1.2
    return Vector((BOARD[k], BY - d, 540 * K2 + 0.5)), Vector((BOARD[k], BY, 540 * K2))


def pose_of(sc, t):
    k = sc["kind"]
    if k in BOARD:
        return board_pose(k)
    if k == "end":
        return board_pose("pattern")
    return map_pose(t)


def pose(t):
    sc = pf.scene_at(t)
    i = pf.SCENES.index(sc)
    cur = pose_of(sc, t)
    if i and (sc["kind"] in BOARD or pf.SCENES[i - 1]["kind"] in BOARD) and sc["kind"] != "end":
        prev = pose_of(pf.SCENES[i - 1], sc["t0"] - 1e-3)
        p = smooth((t - sc["t0"]) / (3.2 if sc["kind"] in ("title", "pattern") else 2.2))
        # a journey between boards and map rises on the way, so the flight reads as a flight
        lift = Vector((0, 0, 9.0 * math.sin(math.pi * p))) if (prev[1] - cur[1]).length > 40 else Vector((0, 0, 0))
        return prev[0].lerp(cur[0], p) + lift, prev[1].lerp(cur[1], p)
    return cur


# ---- apply(t): every object, from the time alone ------------------------------------------------------------

def token_at(s, p, op, col, name):
    tk, pts, z = S["tok"], pf.path_of(s), SLAB + BLOCK * 0.55
    cr = pf.crossing(s)
    if cr:
        col = mix(col, reg_col(s["b"]), seg(p, cr[0], cr[1]))
    q, _, _ = pf.along(pts, p)
    show(tk["o"], op > 0.02)
    tk["o"].location = P(q[0], q[1], z)
    set_glow(tk["m"], op, col)
    for i, (o, m) in enumerate(tk["trail"]):
        pk = p - (i + 1) * 0.028
        show(o, op > 0.02 and pk > 0)
        if pk > 0:
            g, _, _ = pf.along(pts, pk)
            o.location = P(g[0], g[1], z)
            set_glow(m, op * (1 - (i + 1) / 9.0), col)
    lab = tk["label"]
    say(lab, name, op)
    cam = S["cam"]
    lab.location = P(q[0], q[1], z + 0.42)
    lab.rotation_euler = cam.rotation_euler
    pl = tk["plate"]
    show(pl, op > 0.3 and bool(name))
    back_ = cam.matrix_world.to_quaternion() @ Vector((0, 0, -1))        # a little behind the words, as the camera sees them
    up = cam.matrix_world.to_quaternion() @ Vector((0, 1, 0))
    pl.location = lab.location + back_ * 0.03 + up * 0.07
    pl.rotation_euler = cam.rotation_euler
    pl.scale = (len(name) * 0.118 + 0.3, 0.34, 0.004)
    L = pf.length(pts)
    for (o, m), at, c in zip(S["rip"], cr or (0, 0), (YELLOW, reg_col(s["b"]))):
        d = (p - at) * L
        on = bool(cr) and 0 <= d <= 170 and op > 0.02
        show(o, on)
        if on:
            g, _, _ = pf.along(pts, at)
            kk = d / 170.0
            o.location = P(g[0], g[1], z)
            o.scale = [0.1 + 0.62 * out(kk)] * 2 + [1.0]
            set_glow(m, op * (1 - kk), c)


def apply(t):
    sc = pf.scene_at(t)
    k, u, dur = sc["kind"], t - sc["t0"], sc["t1"] - sc["t0"]
    cur = pf.SI[sc["step"]] if k == "step" else None
    h, cam = S["hud"], S["cam"]
    pos, aim = pose(t)
    cam.location = pos
    cam.rotation_euler = (aim - pos).to_track_quat("-Z", "Y").to_euler()
    # the territories rise when the opening names them
    wh = pf.WH
    born_r = {"main": wh["t0"] + 0.2, "cpu": wh["t0"] + wh["cues"][0] - 0.4, "gpu": wh["t0"] + wh["cues"][2] - 0.4}
    big = 1 - seg(t, pf.FIRST_STEP - 1.4, pf.FIRST_STEP - 0.4)
    for rk, r in S["reg"].items():
        o = seg(t, born_r[rk], born_r[rk] + 1.2)
        show(r["o"], o > 0.001)
        place(r["o"], (r["a"].x, r["a"].y, 0), (r["b"].x, r["b"].y, max(1e-3, SLAB * back(o))))
        say(r["small"], None, o * (1 - big))
        say(r["big"], None, o * big)
        say(r["sub"], None, o * big)
    lo = seg(t, pf.STEP_T["c6"] + 1.6, pf.STEP_T["c6"] + 2.6)
    show(S["linebox"], lo > 0.02)
    set_glow(S["linebox"].data.materials[0], lo)
    # the blocks: risen when first named; the two of this step lit, the rest dim; a dip, a swell
    hot, scales, lit_arrow = {}, {}, None
    if cur:
        hot[cur["a"]] = 1 - 0.6 * seg(u, 4.6, 6.2)
        hot[cur["b"]] = seg(u, 5.0, 6.2)
        v = (u - pf.GO) % pf.CYCLE if u >= pf.GO else -9.0
        scales[cur["a"]] = 1 - 0.035 * swell(v + 0.25, 0.5) + 0.05 * swell(u - 0.5, 0.7)
        scales[cur["b"]] = 1 + 0.06 * swell(v - pf.TRAVEL + 0.15, 0.55)
    if k == "journey":
        i, a, c = pf.leg_at(sc, u)
        if i >= 0:
            s = pf.SI[sc["journey"]["legs"][i][0]]
            hot[s["a"]] = hot[s["b"]] = 1.0
            lit_arrow = (s, seg(u, a + 0.2, a + min(3.0, 0.7 * (c - a))), sc["journey"]["col"])
    dim = 0.30 if cur else 0.55 if k == "journey" else 0.5 if k == "act" else 1.0
    for n, d in S["node"].items():
        o = seg(t, pf.BORN[n], pf.BORN[n] + 0.7)
        show(d["o"], o > 0.001)
        if o <= 0.001:
            say(d["t1"], None, 0)
            say(d["t2"], None, 0)
            continue
        h_ = hot.get(n, 0.0)
        lit = dim + (1 - dim) * max(h_, 0.0 if (cur or k == "journey") else 1.0)
        sx = scales.get(n, 1.0)
        zt = SLAB + BLOCK * max(0.02, back(o))
        a, b = P(d["x"], d["y"] + d["h"]), P(d["x"] + d["w"], d["y"])
        cx, cy = (a.x + b.x) / 2, (a.y + b.y) / 2
        place(d["o"], (cx - (b.x - a.x) / 2 * sx, cy - (b.y - a.y) / 2 * sx, SLAB), (cx + (b.x - a.x) / 2 * sx, cy + (b.y - a.y) / 2 * sx, zt))
        set_body(d["m"], lit, hot=h_)
        for tx, zz in ((d["t1"], 38), (d["t2"], 66)):
            tx.location = P(d["x"] + 16, d["y"] + zz, zt + 0.004)
            say(tx, None, o * lit)
    # the arrows: walked ones stay, quiet; this one is drawn on
    for s in pf.STEPS:
        ar = S["arrow"][s["id"]]
        born = pf.STEP_T[s["id"]] + 1.6
        if s is cur:
            p = seg(u, 1.6, 3.0)
            show(ar["o"], p > 0.01)
            ar["o"].data.bevel_factor_end = max(0.001, p)
            show(ar["head"], p > 0.95)
            set_glow(ar["m"], 1.6, ar["col"])
        elif lit_arrow and lit_arrow[0] is s:
            show(ar["o"], True)
            show(ar["head"], True)
            ar["o"].data.bevel_factor_end = 1.0
            set_glow(ar["m"], 1.6, lit_arrow[2])
        else:
            on = t >= born
            show(ar["o"], on)
            show(ar["head"], on)
            ar["o"].data.bevel_factor_end = 1.0
            set_glow(ar["m"], 0.16 if (cur or k == "journey") else 0.4, ar["col"])
    # what moves
    ind = S["ind"]
    show(ind, False)
    if cur:
        col = reg_col(cur["a"])
        v = (u - pf.GO) % pf.CYCLE if u >= pf.GO else -1.0
        token_at(cur, seg(v, 0.0, pf.TRAVEL), appear(v, -0.2, pf.CYCLE - 0.6, 0.4) if v >= 0 else 0.0, col, cur["moves"])
        pd = seg(u, pf.GO + pf.TRAVEL - 0.2, pf.GO + pf.TRAVEL + 0.7)
        if pd > 0.01:
            d = S["node"][cur["b"]]
            a, b = P(d["x"] - 12, d["y"] + d["h"] + 12, SLAB + 0.02), P(d["x"] + d["w"] + 12, d["y"] - 12, SLAB + 0.02)
            for pt_, co in zip(ind.data.splines[0].points, ((a.x, a.y), (b.x, a.y), (b.x, b.y), (a.x, b.y), (a.x, a.y))):
                pt_.co = (co[0], co[1], a.z, 1.0)
            ind.data.bevel_factor_end = pd
            show(ind, True)
            set_glow(ind.data.materials[0], 1 - 0.55 * seg(u, pf.GO + pf.TRAVEL + 1.5, pf.GO + pf.TRAVEL + 3.0))
    elif lit_arrow:
        token_at(lit_arrow[0], lit_arrow[1], 1.0, lit_arrow[2], lit_arrow[0]["moves"])
    else:
        token_at(pf.STEPS[0], 0, 0.0, YELLOW, "")
    # the whole, and the borders
    c = sc["cues"]
    for i, bg in enumerate(S["big"]):
        on, p = False, 0.0
        if k == "whole":
            a = (c[0] + 2.2, c[1], c[2] + 2.2, c[3])[i]
            p, on = seg(u, a, a + 1.2), u >= a
        show(bg["o"], on and p > 0.01)
        show(bg["head"], on and p > 0.9)
        bg["o"].data.bevel_factor_end = max(0.001, p)
        say(bg["t"], None, appear(u, a + 0.7, dur, 0.5) if on else 0.0)
    for i, (o, m) in enumerate(S["border"]):
        on = k == "borders" and u >= c[i]
        show(o, on)
        if on:
            pulse = 0.5 + 0.5 * math.sin((u - c[i]) * 5) if u < c[i] + 5 else 0.0
            set_glow(m, appear(u, c[i], dur, 0.6) * (0.35 + 0.65 * pulse))
    hud_at(t, sc, k, u, dur, cur)
    battle_at(t, (cur or {}).get("field") if cur else (sc["journey"].get("field") if k == "journey" else None))
    if k in S["board"] or k == "end":
        board_at(k, u, dur, sc)
    else:
        i = pf.SCENES.index(sc)
        prev = pf.SCENES[i - 1] if i else None
        if prev and prev["kind"] in S["board"] and u < 4.0:      # the board just left, as it was left
            board_at(prev["kind"], prev["t1"] - prev["t0"], prev["t1"] - prev["t0"], prev)


def hud_at(t, sc, k, u, dur, cur):
    h = S["hud"]
    step = k == "step"
    op = seg(u, 0.5, 1.2) * (1 - seg(u, dur - 0.6, dur - 0.1)) if step else 0.0
    pshow(h["low"], 1 if step else 0)
    pshow(h["lowline"], 1 if step else 0)
    if step:
        s = cur
        col = reg_col(s["a"])
        set_glow(bpy.data.materials[h["lowline"]["m"]], 1.0, col)
        i = [x["id"] for x in pf.STEPS].index(s["id"]) + 1
        say(h["label"], "STEP %d OF %d  ·  %s" % (i, len(pf.STEPS), pf.ACTS[s["act"]][0]), op, col)
        a_, b_ = pf.N[s["a"]][5], pf.N[s["b"]][5]
        say(h["a"], written(a_, seg(u, 0.5, 1.5, out)), op)
        xa = 60 + len(a_) * 20.5 + 26
        h["to"].location = H(xa + 18 + 40 * seg(u, 1.6, 3.0), 774, 2)
        say(h["to"], None, op * seg(u, 1.6, 2.4), col)
        h["b"].location = H(xa + 128, 774, 2)
        say(h["b"], written(b_, seg(u, 2.4, 3.4, out)), op)
        rows = [("WHAT MOVES", s["what"], 2.8), ("WHY", s["why"], 5.0)]
        if s.get("rule"):
            rows.append(("THE RULE", s["rule"], 7.0))
        if s.get("border"):
            rows.append(("THE BORDER", s["border"], 7.0 if not s.get("rule") else 8.0))
        y = 690 + 126
        for j, (nm, bd) in enumerate(h["rows"]):
            if j >= len(rows):
                say(nm, "", 0)
                say(bd, "", 0)
                continue
            name, words, at = rows[j]
            o = op * seg(u, at, at + 0.7)
            dy = 16 * (1 - seg(u, at, at + 0.7, out))
            ls = pf.wrap(words, 22, 1070)
            nm.location, bd.location = H(60, y + dy, 2), H(214, y + 2 + dy, 2)
            say(nm, name, o, YELLOW if name == "THE BORDER" else col)
            say(bd, "\n".join(ls), o)
            y += 29 * len(ls) + 7
    else:
        for key in ("label", "a", "to", "b"):
            say(h[key], None, 0)
        for nm, bd in h["rows"]:
            say(nm, None, 0)
            say(bd, None, 0)
    # the path down, and the small map
    cop = seg(u, 0.4, 1.1) * (1 - seg(t, sc["t1"] - 0.5, sc["t1"])) if step else 0.0
    pshow(h["crumbbg"], cop)
    pshow(h["mini"]["bg"], cop)
    for o in h["mini"]["regs"]:
        pshow(o, cop)
    say(h["minit"], None, cop)
    for n, o in h["mini"]["nodes"].items():
        pshow(o, cop)
        if step:
            on = n in (cur["a"], cur["b"])
            set_glow(bpy.data.materials[o["m"]], 1.0, INK if on else mix(BG, reg_col(n), 0.55), 3.0 if on else 1.0)
    if step:
        parts = [("THE WHOLE", DIM), (pf.ACTS[cur["act"]][0], pf.ACTS[cur["act"]][2]), ("%s  →  %s" % (pf.N[cur["a"]][5], pf.N[cur["b"]][5]), INK)]
        x = 44
        for j, ((words, cc), o) in enumerate(zip(parts, h["crumb"])):
            o.location = H(x, 52, 2)
            say(o, ("›  " if j else "") + words, cop * seg(u, 0.5 + j * 0.35, 1.0 + j * 0.35, out), cc)
            x += (len(words) + (3 if j else 0)) * 10.6 + 20
    else:
        for o in h["crumb"]:
            say(o, None, 0)
    # the teleprompt: the narration's lines, the spoken word lit, climbing at the film's pace
    lines = sc.get("lines")
    if lines is None:
        lines, curl, n = [], [], 0
        for i, w in enumerate(sc["words"]):
            if n + len(w) + 1 > 36 and curl:
                lines.append(curl)
                curl, n = [], 0
            curl.append((i, w))
            n += len(w) + 1
        lines = sc["lines"] = lines + ([curl] if curl else [])
    tp, tx = pf.TP, h["tptext"]
    pos = clamp((u - pf.LEAD) * pf.WPM / 60.0, 0, len(sc["words"]) - 0.001)
    li = next(i for i, l in enumerate(lines) if l[-1][0] >= int(pos))
    frac = (pos - lines[li][0][0]) / len(lines[li])
    first, last = max(0, li - 1), min(len(lines), li + 6 - (1 if frac < 0.55 else 0))
    body_, fmt = "", []
    for l in lines[first:last]:
        for kx, w in l:
            body_ += w + " "
            fmt += [1 if kx == int(pos) else 2 if kx < pos else 0] * (len(w) + 1)
        body_ += "\n"
        fmt.append(0)
    if tx.data.body != body_:
        tx.data.body = body_
    for bf, mi in zip(tx.data.body_format, fmt):
        bf.material_index = mi
    tx.location = H(tp["x"] + 26, tp["y"] + 50 + 34 * 1.2 - (li - first + frac) * 34, 4)
    show(tx, True)
    # the other scenes' words on the glass
    names = {"whole": "THE WHOLE, IN ONE PICTURE", "borders": "THE BORDERS, AND WHAT IT TAKES TO CROSS EACH", "hook1": "ONE WEEK IN NOVEMBER",
             "hook2": "%s CHANGES, EACH PLACED BY HOW IT SCORED" % format(pf.HOOK["trials"], ","), "hook3": "SIGNAL, AND NOISE, TO SCALE"}
    hop = appear(u, 0.4, dur, 0.6)
    pshow(h["headbg"], 1 if (k == "journey" or k in names) and hop > 0.3 else 0)
    if k == "journey":
        j = sc["journey"]
        say(h["head"], j["title"].upper(), hop, j["col"])
        say(h["head2"], j["sub"], hop)
        i, a, c = pf.leg_at(sc, u)
        pshow(h["jpanel"], 1)
        if i >= 0:
            sid, words = j["legs"][i]
            o = appear(u, a, c + 0.2, 0.4) * hop
            say(h["jlabel"], "%d OF %d  ·  %s  to  %s" % (i + 1, len(j["legs"]), pf.N[pf.SI[sid]["a"]][5], pf.N[pf.SI[sid]["b"]][5]), o, j["col"])
            say(h["jwords"], "\n".join(pf.wrap(words, 36, 1230)), o)
        else:
            say(h["jlabel"], "", 0)
            say(h["jwords"], "The same arrows, with one real thing travelling over them.", appear(u, 0.5, sc["cues"][0], 0.4))
    else:
        say(h["head"], names.get(k, ""), hop if k in names else 0, INK if k in ("whole", "borders") else DIM)
        say(h["head2"], None, 0)
        pshow(h["jpanel"], 1 if k == "borders" else 0)
        say(h["jlabel"], None, 0)
        say(h["jwords"], None, 0)
    for i, (sq, nm, need) in enumerate(h["legend"]):
        rows = (("main to the fleet", "free: reading changes nothing"), ("the fleet to the line", "a gain that held on fresh seeds, and every gate"),
                ("the line to main", "a proof: the new game against the old, 9,600 games"), ("the cards to main", "the game's own reading of the net, twice"))
        o = appear(u, sc["cues"][i], dur, 0.6) if k == "borders" else 0.0
        say(sq, None, o)
        say(nm, rows[i][0], o)
        say(need, rows[i][1], o * seg(u, sc["cues"][i] + 0.8, sc["cues"][i] + 1.6) if k == "borders" else 0.0)
    # the cards: the title, an act, the close
    pshow(h["band"], 1 if k == "act" else 0)
    if k == "act":
        name, sub, col = pf.ACTS[sc["act"]]
        o = appear(u, 0.2, dur, 0.6)
        n = sum(1 for s in pf.STEPS if s["act"] == sc["act"])
        say(h["c1"], name, o, col)
        say(h["c2"], sub, o * seg(u, 0.8, 1.6), INK)
        say(h["c3"], "%d arrow%s, one at a time" % (n, "" if n == 1 else "s"), o * seg(u, 1.4, 2.2))
    elif k == "title":
        o = appear(u, 0.3, dur, 0.7)
        say(h["c1"], written(pf.STORY["title"], seg(u, 0.3, 1.8, out)), o, INK)
        say(h["c2"], pf.STORY["subtitle"], o * seg(u, 1.2, 2.2), DIM)
        say(h["c3"], pf.STORY["byline"], o * seg(u, 2.0, 3.0))
    elif k == "end":
        o = appear(u, 0.3, dur, 0.8)
        a = pf.LEAD + 9 * 60.0 / pf.WPM
        pshow(h["band"], 1)
        say(h["c1"], "", 0)
        h["c2"].location, h["c3"].location = H(960, 452, 2), H(960, 506, 2)
        say(h["c2"], pf.STORY["closing"][0], o, INK)
        say(h["c3"], pf.STORY["closing"][1], o * seg(u, a, a + 1.0), INK)
        for i, (tx, l) in enumerate(zip(h["credits"], pf.STORY.get("credits", []))):
            say(tx, l, o * seg(u, 6.0 + i * 0.5, 6.8 + i * 0.5))
    else:
        for key in ("c1", "c2", "c3"):
            say(h[key], None, 0)
    if k != "end":
        for tx in h["credits"]:
            say(tx, None, 0)
        h["c2"].location, h["c3"].location = H(960, 584, 2), H(960, 646, 2)


def board_at(k, u, dur, sc):
    c, hk = sc["cues"], pf.HOOK
    if k == "hook1":
        b = S["board"]["hook1"]
        each, total = (c[1] - c[0] - 0.8) / len(b["blocks"]), 0.0
        for i, d in enumerate(b["blocks"]):
            a = c[0] + i * each
            land = seg(u, a, a + 0.75, back)
            on = u >= a
            show(d["o"], on)
            d["o"].location.z = d["z"] + 260 * K2 * (1 - land)
            total += d["v"] * seg(u, a, a + 0.6)
            if d["t"]:
                say(d["t"], None, seg(u, a + 0.4, a + 0.9))
            say(d["r"], None, seg(u, a + 0.4, a + 0.9))
        say(b["cap1"], None, seg(u, c[0], c[0] + 1.0))
        say(b["total"], "+%.2f" % total, seg(u, c[0] + 0.3, c[0] + 1.0))
        say(b["sub"], written("points a seat, added together", seg(u, c[1], c[1] + 1.2)), 1.0)
        o2, fall = seg(u, c[2], c[2] + 0.8), seg(u, c[3], c[3] + 1.6)
        hh = b["full"] * (1 - fall)
        x1, bw, base = b["x1"], b["bw"], b["base"]
        for o, (xa, ya, xb, yb) in zip(b["ghost"], ((x1, base - hh, x1 + 5, base), (x1 + bw - 5, base - hh, x1 + bw, base), (x1, base - hh, x1 + bw, base - hh + 5))):
            show(o, o2 > 0.02 and fall < 0.98)
            p0, p1 = B("hook1", xa, yb), B("hook1", xb, ya)
            place(o, (p0.x, BY - 0.25, p0.z), (p1.x, BY + 0.25, max(p1.z, p0.z + 0.02)))
            set_glow(o.data.materials[0], o2 * (1 - 0.7 * fall))
        say(b["cap2"], None, o2)
        say(b["exp"], written("what we expected", seg(u, c[2] + 0.4, c[2] + 1.4)), 1 - fall)
        o3 = seg(u, c[3] + 1.0, c[3] + 1.8)
        show(b["bar"], o3 > 0.02)
        show(b["whisk"], o3 > 0.02)
        say(b["num"], written("%+.2f ± %.2f" % (hk["proof"][0], hk["proof"][1]), seg(u, c[3] + 1.0, c[3] + 2.0)), 1.0)
        say(b["said"], None, o3)
    elif k == "hook2":
        b = S["board"]["hook2"]
        win, home = seg(u, c[2], c[2] + 0.8), seg(u, c[3], c[3] + 2.2)
        for d in b["bars"]:
            i = d["i"]
            a = 3.4 + i * (c[0] - 4.6) / len(b["bars"])
            g = seg(u, a, a + 1.0, out)
            tail = i >= 12
            hh = max(0.5, d["c"] * b["sy"] * g * (1 - home if tail else 1))
            p0, p1 = B("hook2", b["x0"] + i * b["w"] + 3, b["base"]), B("hook2", b["x0"] + (i + 1) * b["w"] - 3, b["base"] - hh)
            place(d["o"], (p0.x, BY - 0.25, p0.z), (p1.x, BY + 0.25, p1.z))
            show(d["o"], g > 0.001)
            set_body(d["m"], 1.0, mix(pf.GPU, YELLOW, win) if tail else pf.GPU)
        p = seg(u, c[0], c[0] + 2.4)
        show(b["curve"], p > 0.005)
        b["curve"].data.bevel_factor_end = max(0.001, p)
        say(b["none"], written("if none of them did anything", seg(u, c[0] + 1.2, c[0] + 2.4)), 1.0)
        say(b["same"], written("the same curve", seg(u, c[1], c[1] + 1.0)), 1.0)
        say(b["kept"], written("the best: kept", win), 1 - home)
        say(b["again"], written("measured again", seg(u, c[3] + 1.4, c[3] + 2.4)), 1.0)
        for j, o in enumerate(b["dots"]):
            q = (j * 0.6180339887) % 1.0
            zs = 2.0 + 1.3 * q * q
            ze = math.sqrt(-2 * math.log(1 - 0.98 * ((j * 0.7548776662 + 0.31) % 1.0))) * math.cos(6.2831853 * ((j * 0.5698402909 + 0.17) % 1.0))
            z = lerp(zs, ze, seg(u, c[3] + 0.012 * j, c[3] + 1.9 + 0.012 * j))
            show(o, win > 0.05)
            o.location = B("hook2", b["x0"] + (z + 4) / 8 * (b["x1"] - b["x0"]), b["base"] - 24 - (j * 37 % 110), 0.5)
    elif k == "hook3":
        b = S["board"]["hook3"]
        g1, g2 = seg(u, 1.0, 3.0), seg(u, c[0] - 1.6, c[0] - 0.4)
        for o, y, g, v in ((b["bar1"], 250, g1, hk["swing"]), (b["bar2"], 430, g2, hk["gain"])):
            show(o, g > 0.002)
            p0, p1 = B("hook3", b["x"], y + 74), B("hook3", b["x"] + v * b["k"] * max(g, 0.002), y)
            place(o, (p0.x, BY - 0.3, p0.z), (p1.x, BY + 0.3, p1.z))
        say(b["t1"], written("the luck of a single game: %.1f points" % hk["swing"], seg(u, 1.2, 2.6)), 1.0)
        say(b["t2"], written("a real improvement to the game: %.2f points" % hk["gain"], g2), 1.0)
        say(b["s1"], written("This is the story of one machine that learns to play a game,", seg(u, c[1], c[1] + 2.4)), 1.0)
        say(b["s2"], written("and of the borders it built against its own luck.", seg(u, c[2], c[2] + 2.2)), 1.0)
    else:
        b = S["board"]["pattern"]
        if k == "end":
            u, c = 1e6, [0, 0, 0, 0, 0]
        say(b["title"], written("One shape, at every border", seg(u, 0.6, 2.0, out)), 1.0)
        each = (c[1] - c[0] - 1.0) / len(b["top"]) if k != "end" else 1
        for i, d in enumerate(b["top"]):
            o = seg(u, c[0] + i * each, c[0] + i * each + 0.8)
            show(d["o"], o > 0.01)
            d["o"].location.z = d["z"] - 0.6 * (1 - back(o))
            say(d["t"], None, o)
            say(d["s"], None, o)
            if d["w"]:
                show(d["w"], o > 0.5)
        for r, row in enumerate(b["rows"]):
            a = c[1 + r]
            say(row["name"], None, seg(u, a, a + 0.8))
            for i, d in enumerate(row["cells"]):
                o = seg(u, a + 0.3 + i * 0.28, a + 0.9 + i * 0.28)
                show(d["o"], o > 0.01)
                d["o"].location.z = d["z"] - 0.5 * (1 - back(o))
                say(d["t"], None, o)
        for kk, (tx, l) in enumerate(b["last"]):
            say(tx, written(l, seg(u, c[4] + kk * 1.6, c[4] + 1.6 + kk * 1.6)), 1.0)


# ---- the scene, and the frames -------------------------------------------------------------------------------

def park():
    b = S["board"]
    for o in b["hook1"]["ghost"] + [b["hook1"]["bar"], b["hook1"]["whisk"], b["hook2"]["curve"], b["hook3"]["bar1"], b["hook3"]["bar2"]] + b["hook2"]["dots"] \
            + [d["o"] for d in b["hook1"]["blocks"] + b["hook2"]["bars"] + b["pattern"]["top"]] + [d["w"] for d in b["pattern"]["top"] if d["w"]] \
            + [d["o"] for r in b["pattern"]["rows"] for d in r["cells"]]:
        show(o, False)
    for o in bpy.data.objects:
        if o.type == "FONT" and o.parent is None and o.location.y < BY + 1 and abs(o.location.x) > 30:
            pass


def scene(samples=24):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    w = bpy.data.worlds.new("dark")
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = rgb("#07080a")
    build_hud()
    build_map()
    build_boards()
    build_battles()
    park()
    for name in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            sc.render.engine = name
            break
        except TypeError:
            pass
    sc.render.resolution_x, sc.render.resolution_y, sc.render.fps = pf.W, pf.H, FPS
    sc.view_settings.view_transform = "Standard"
    sc.render.image_settings.file_format = "PNG"
    try:
        sc.eevee.taa_render_samples = samples
    except AttributeError:
        pass
    return sc


def shoot(t, out_png):
    apply(t)
    bpy.context.view_layer.update()
    bpy.context.scene.render.filepath = out_png
    bpy.ops.render.render(write_still=True)


def main():
    mode = ARGS[0]
    if mode == "still":
        scene()
        shoot(float(ARGS[1]), ARGS[2])
    elif mode == "frames":
        a, b, out_dir = int(ARGS[1]), int(ARGS[2]), ARGS[3]
        scene(int(ARGS[4]) if len(ARGS) > 4 else 24)
        os.makedirs(out_dir, exist_ok=True)
        # JPEG: eighteen thousand PNGs of this are thirty gigabytes
        bpy.context.scene.render.image_settings.file_format = "JPEG"
        bpy.context.scene.render.image_settings.quality = 93
        for i in range(a, min(b, int(pf.LENGTH * FPS))):
            f = os.path.join(out_dir, "f%05d.jpg" % i)
            if not os.path.exists(f):
                shoot(i / FPS, f)
    elif mode == "stills":        # several moments in one session: stills OUTDIR T1,T2,... [SAMPLES]
        scene(int(ARGS[3]) if len(ARGS) > 3 else 16)
        for t in [float(x) for x in ARGS[2].split(",")]:
            shoot(t, os.path.join(ARGS[1], "s%07.1f.png" % t))
    elif mode == "blend":
        scene()
        apply(float(ARGS[2]) if len(ARGS) > 2 else pf.STEP_T["c6"] + 6)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(ARGS[1]))
    print("process_blend_film: %s done" % " ".join(ARGS))


main()

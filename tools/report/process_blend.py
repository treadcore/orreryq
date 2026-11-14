"""process_blend: the storyboard's block diagram as a place, in Blender.

    blender -b -P tools/report/process_blend.py -- [still|film|blend] [STORYBOARD.json] [OUTDIR]

The same file the drawn film is made from (docs/process/storyboard.json) built in three dimensions: each
territory a slab, each block standing on its territory, each arrow a tube from its source to its destination
with a token on it, and the border between territories a gap the tubes bridge. `still` renders one picture
(OUTDIR/blender-still.png), `film` the opening move: the camera coming in from far above to the map, 8
seconds (OUTDIR/blender-open.mp4). Either saves the scene (OUTDIR/process.blend) to open and look round in.

Nothing here is placed by hand: every position is the storyboard's, a hundred of its units to one of
Blender's, its y turned to go away from the viewer. Run by Blender's own Python; it imports nothing else.
"""
import json
import math
import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "still"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STORY = json.load(open(argv[1] if len(argv) > 1 else os.path.join(ROOT, "docs", "process", "storyboard.json")))
OUT = argv[2] if len(argv) > 2 else os.path.join(ROOT, "docs", "process")
K = 0.01            # the storyboard's units to Blender's
SLAB, BLOCK = 0.12, 0.42
INK, YELLOW = "#ece9e1", "#f7d96f"


def P(x, y, z=0.0):
    """A storyboard point as a place: x across, y away from the viewer, the map centred on the origin."""
    return ((x - 960) * K, (540 - y) * K, z)


def rgb(h, a=1.0):
    c = [int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c) + (a,)


_MATS = {}


def mat(name, col, glow=0.0, rough=0.55, mix_dark=0.0):
    key = (name, col, glow, mix_dark)
    if key in _MATS:
        return _MATS[key]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    c = rgb(col)
    d = tuple(v * (1 - mix_dark) + 0.004 * mix_dark for v in c[:3]) + (1.0,)
    b.inputs["Base Color"].default_value = d
    b.inputs["Roughness"].default_value = rough
    for k in ("Emission Color", "Emission"):
        if k in b.inputs:
            b.inputs[k].default_value = c
            break
    if "Emission Strength" in b.inputs:
        b.inputs["Emission Strength"].default_value = glow
    _MATS[key] = m
    return m


def box(name, x, y, w, h, z0, z1, material, bevel=0.03):
    cx, cy, _ = P(x + w / 2, y + h / 2)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, (z0 + z1) / 2))
    o = bpy.context.object
    o.name = name
    o.scale = (w * K, h * K, z1 - z0)
    bpy.ops.object.transform_apply(scale=True)
    if bevel:
        mod = o.modifiers.new("bevel", "BEVEL")
        mod.width, mod.segments = bevel, 3
    o.data.materials.append(material)
    return o


def words(s, x, y, z, size, col, glow=1.6, align="LEFT"):
    px, py, _ = P(x, y)
    bpy.ops.object.text_add(location=(px, py, z))
    o = bpy.context.object
    o.data.body = s
    o.data.size = size
    o.data.align_x = align
    o.data.extrude = 0.004
    o.data.materials.append(mat("ink", col, glow))
    return o


def tube(pts, z, col, r=0.022, glow=3.0, dash=False):
    cu = bpy.data.curves.new("arrow", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth, cu.bevel_resolution = r, 6
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for p_, q in zip(sp.points, pts):
        p_.co = P(q[0], q[1], z) + (1.0,)
    o = bpy.data.objects.new("arrow", cu)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(mat("wire", col, glow * (0.45 if dash else 1.0)))
    # the head: a cone at the end, pointing the way the arrow goes
    a, b = P(*pts[-2]), P(*pts[-1])
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    bpy.ops.mesh.primitive_cone_add(radius1=r * 3.2, depth=r * 8, location=(b[0] - math.cos(ang) * r * 4, b[1] - math.sin(ang) * r * 4, z),
                                    rotation=(0, math.pi / 2, ang))
    bpy.context.object.data.materials.append(mat("wire", col, glow))
    return o


def rect_of(n):
    v = STORY["nodes"][n]
    return v["x"], v["y"], v["w"], v["h"]


def clip(n, toward):
    x, y, w, h = rect_of(n)
    cx, cy = x + w / 2, y + h / 2
    dx, dy = toward[0] - cx, toward[1] - cy
    k = min((w / 2) / abs(dx) if dx else 1e9, (h / 2) / abs(dy) if dy else 1e9)
    return cx + dx * k, cy + dy * k


def path_of(s):
    if s.get("pts"):
        return [tuple(q) for q in s["pts"]]
    ca = (rect_of(s["a"])[0] + rect_of(s["a"])[2] / 2, rect_of(s["a"])[1] + rect_of(s["a"])[3] / 2)
    cb = (rect_of(s["b"])[0] + rect_of(s["b"])[2] / 2, rect_of(s["b"])[1] + rect_of(s["b"])[3] / 2)
    return [clip(s["a"], cb), clip(s["b"], ca)]


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    w = bpy.data.worlds.new("dark")
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = rgb("#07080a")
    # the ground: a dark plane with the storyboard's faint plane of lines on it
    bpy.ops.mesh.primitive_plane_add(size=120, location=(0, 0, -0.01))
    bpy.context.object.data.materials.append(mat("ground", "#0e1013", 0.0, 0.9))
    for i in range(-30, 31):
        for pts in (((i * 80 + 960, -1500), (i * 80 + 960, 2600)), ((-1500, i * 80 + 540), (3400, i * 80 + 540))):
            tube(pts, 0.0, INK, r=0.0035, glow=0.02 if i % 6 else 0.07)
            bpy.data.objects.remove(bpy.context.object)       # a grid line has no head
    for k, r in STORY["regions"].items():
        box("territory " + k, r["x"], r["y"], r["w"], r["h"], 0, SLAB, mat("slab " + k, r["col"], 0.02, 0.6, 0.93), bevel=0.05)
        words(r["name"], r["x"] + 22, r["y"] + 34, SLAB + 0.002, 0.2, r["col"], 3.0)
    lb = STORY["line_box"]
    x0, y0, x1, y1 = lb["x"], lb["y"], lb["x"] + lb["w"], lb["y"] + lb["h"]
    tube([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], SLAB + 0.01, YELLOW, r=0.008, glow=2.0)
    bpy.data.objects.remove(bpy.context.object)
    for n, v in STORY["nodes"].items():
        col = STORY["regions"][v["region"]]["col"]
        box(n, v["x"], v["y"], v["w"], v["h"], SLAB, SLAB + BLOCK, mat("block " + v["region"], col, 0.07, 0.42, 0.80))
        words(v["title"], v["x"] + 16, v["y"] + 38, SLAB + BLOCK + 0.003, 0.24, INK, 2.4)
        words(v["sub"], v["x"] + 16, v["y"] + 66, SLAB + BLOCK + 0.003, 0.14, col, 1.6)
    for s in STORY["steps"]:
        col = STORY["regions"][STORY["nodes"][s["a"]]["region"]]["col"]
        pts = path_of(s)
        tube(pts, SLAB + BLOCK * 0.55, col, dash=bool(s.get("dash")))
        # what moves, part of the way along: a small bright sphere, yellow where the arrow crosses a border
        a, b = pts[0], pts[1] if len(pts) == 2 else pts[len(pts) // 2]
        m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        cross = STORY["nodes"][s["a"]]["region"] != STORY["nodes"][s["b"]]["region"]
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.06, location=P(m[0], m[1], SLAB + BLOCK * 0.55))
        bpy.ops.object.shade_smooth()
        bpy.context.object.data.materials.append(mat("token", YELLOW if cross else col, 4.5))
    # light: one soft key from the front left, and the things that glow
    bpy.ops.object.light_add(type="AREA", location=(-7, -9, 9))
    key = bpy.context.object
    key.data.energy, key.data.size = 1400, 9
    key.rotation_euler = (math.radians(48), 0, math.radians(-32))
    bpy.ops.object.light_add(type="AREA", location=(9, 6, 7))
    bpy.context.object.data.energy, bpy.context.object.data.size = 450, 12
    # the camera: far above, then down to the map from the front
    bpy.ops.object.empty_add(location=(0, -1.6, 0))
    aim = bpy.context.object
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    cam.data.lens = 30
    t = cam.constraints.new("TRACK_TO")
    t.target, t.track_axis, t.up_axis = aim, "TRACK_NEGATIVE_Z", "UP_Y"
    sc.camera = cam
    sc.render.fps = 24
    sc.frame_start, sc.frame_end = 1, 192
    for f, loc in ((1, (0, -3.0, 70)), (110, (0, -12.0, 22.0)), (192, (-0.8, -14.2, 10.2))):
        cam.location = loc
        cam.keyframe_insert("location", frame=f)
    for name in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            sc.render.engine = name
            break
        except TypeError:
            pass
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
    sc.view_settings.view_transform = "Standard"
    try:
        sc.eevee.taa_render_samples = 48
    except AttributeError:
        pass
    return sc


def main():
    sc = build()
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "process.blend"))
    if MODE == "still":
        sc.frame_set(192)
        sc.render.image_settings.file_format = "PNG"
        sc.render.filepath = os.path.join(OUT, "blender-still.png")
        bpy.ops.render.render(write_still=True)
    elif MODE == "film":
        sc.render.image_settings.file_format = "FFMPEG"
        sc.render.ffmpeg.format, sc.render.ffmpeg.codec = "MPEG4", "H264"
        sc.render.ffmpeg.constant_rate_factor = "HIGH"
        sc.render.filepath = os.path.join(OUT, "blender-open.mp4")
        bpy.ops.render.render(animation=True)
    print("process_blend: %s, %d blocks, %d arrows -> %s" % (MODE, len(STORY["nodes"]), len(STORY["steps"]), OUT))


main()

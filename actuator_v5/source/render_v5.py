"""Render the exported CAD tessellation in Blender Cycles (no geometry substitutions).

blender -b -P source/render_v5.py -- [--quick] [--views hero,section,...] [--out images]
Blender axes: X = actuator axis, Y = -model Y (service side away from the
default camera), Z = clevis pin axis (eyes lie flat).
"""
import bpy, json, math, sys
from pathlib import Path
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
QUICK = "--quick" in argv
VIEWS = argv[argv.index("--views") + 1].split(",") if "--views" in argv else None
root = Path(__file__).resolve().parent.parent
OUT = Path(argv[argv.index("--out") + 1]) if "--out" in argv else root / "images"
OUT.mkdir(parents=True, exist_ok=True)
data = json.loads((root / "source/scene_meshes.json").read_text())
P = json.loads((root / "parameters.json").read_text())
CENTRE = (P["rear_eye_z"] + P["front_eye_z_retracted"]) / 2 + P["stroke_mm"] / 4

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 24 if QUICK else 96
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 8
scene.render.resolution_x, scene.render.resolution_y = (960, 540) if QUICK else (1920, 1080)
scene.render.image_settings.file_format = "PNG"
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"


def linear(c):
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


MATS = {}


def material(kind, color):
    key = (kind, tuple(round(c, 3) for c in color))
    if key in MATS:
        return MATS[key]
    m = bpy.data.materials.new(f"{kind}_{len(MATS)}")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*linear(color), 1)
    preset = {"paint": (0.0, 0.34, 0.25), "plastic": (0.0, 0.46, 0.05), "chrome": (1.0, 0.11, 0.0),
              "rubber": (0.0, 0.72, 0.0), "steel": (1.0, 0.28, 0.0), "brass": (1.0, 0.26, 0.0),
              "tin": (1.0, 0.33, 0.0), "black": (0.0, 0.4, 0.0), "ceramic": (0.0, 0.55, 0.0),
              "blackmetal": (0.85, 0.38, 0.0), "wire": (0.0, 0.35, 0.1), "backdrop": (0.0, 0.62, 0.0)}[kind]
    b.inputs["Metallic"].default_value, b.inputs["Roughness"].default_value, coat = preset
    b.inputs["Coat Weight"].default_value = coat
    if kind not in ("backdrop", "wire", "rubber"):
        bev = nt.nodes.new("ShaderNodeBevel")
        bev.inputs["Radius"].default_value = 0.18 if kind in ("paint", "plastic", "chrome") else 0.05
        nt.links.new(bev.outputs["Normal"], b.inputs["Normal"])
    MATS[key] = m
    return m


root_obj = bpy.data.objects.new("actuator", None)
scene.collection.objects.link(root_obj)
objects = {}
for item in data:
    verts = [(v[2] - CENTRE, -v[1], v[0]) for v in item["vertices"]]
    mesh = bpy.data.meshes.new(item["name"])
    mesh.from_pydata(verts, [], [tuple(t) for t in item["triangles"]])
    mesh.validate()
    mesh.update()
    ob = bpy.data.objects.new(item["name"], mesh)
    scene.collection.objects.link(ob)
    ob.parent = root_obj
    kind, color = item["material"], item["color"]
    if item["name"].endswith("__half") and kind == "chrome":
        kind, color = "plastic", (0.70, 0.72, 0.74)      # cut faces read as the silver PETG they are
    ob.data.materials.append(material(kind, color))
    for poly in mesh.polygons:
        poly.use_smooth = True
    try:
        mesh.set_sharp_from_angle(angle=math.radians(32))
    except Exception:
        pass
    ob["moving"] = item["moving"]
    ob["kind"] = item["kind"]
    ob["rotating"] = item.get("rotating", False)
    objects[item["name"]] = ob

# Studio: bundled studio HDRI for reflections, flat warm grey seen by the camera.
world = bpy.data.worlds.new("studio")
scene.world = world
world.use_nodes = True
wn = world.node_tree
for n in list(wn.nodes):
    wn.nodes.remove(n)
env = wn.nodes.new("ShaderNodeTexEnvironment")
env.image = bpy.data.images.load(str(Path(bpy.utils.resource_path("LOCAL")) / "datafiles/studiolights/world/studio.exr"))
bg_env = wn.nodes.new("ShaderNodeBackground")
bg_env.inputs["Strength"].default_value = 0.55
bg_flat = wn.nodes.new("ShaderNodeBackground")
bg_flat.inputs["Color"].default_value = (*linear((0.93, 0.93, 0.92)), 1)
bg_flat.inputs["Strength"].default_value = 1.0
lp = wn.nodes.new("ShaderNodeLightPath")
mix = wn.nodes.new("ShaderNodeMixShader")
out = wn.nodes.new("ShaderNodeOutputWorld")
wn.links.new(env.outputs["Color"], bg_env.inputs["Color"])
wn.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
wn.links.new(bg_env.outputs["Background"], mix.inputs[1])
wn.links.new(bg_flat.outputs["Background"], mix.inputs[2])
wn.links.new(mix.outputs["Shader"], out.inputs["Surface"])

bpy.ops.mesh.primitive_plane_add(size=3000, location=(0, 0, -11.55))
ground = bpy.context.object
ground.data.materials.append(material("backdrop", (0.90, 0.90, 0.89)))
ground.is_shadow_catcher = False


def area_light(name, loc, energy, size, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy, ld.shape, ld.size, ld.color = energy, "DISK", size, color
    ob = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return ob


area_light("key", (-60, -160, 210), 260000, 170, (1.0, 0.97, 0.92))
area_light("fill", (170, -40, 90), 60000, 160, (0.92, 0.96, 1.0))
area_light("rim", (40, 210, 140), 140000, 120)

cam_data = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
cam_data.lens = 85
cam_data.clip_end = 10000


def aim(direction, target, distance, lens=85, roll=0.0, ground_z=-11.55):
    d = Vector(direction).normalized()
    cam.location = Vector(target) + d * distance
    q = (-d).to_track_quat("-Z", "Y")
    if roll:
        from mathutils import Quaternion
        q = Quaternion(-d, math.radians(roll)) @ q
    cam.rotation_euler = q.to_euler()
    cam_data.type = "PERSP"
    cam_data.lens = lens
    ground.location.z = ground_z


HALF = {n[:-6] for n in objects if n.endswith("__half")}


def pose(travel=None, hide=(), only=None, section=False, xray=(), offsets=None):
    travel = P["stroke_mm"] / 2 if travel is None else travel
    theta = -travel / P["screw_pitch_mm"] * 2 * math.pi
    for name, ob in objects.items():
        base = name[:-6] if name.endswith("__half") else name
        ob.location = (travel if ob["moving"] else 0, 0, 0)
        ob.rotation_euler = (theta if ob["rotating"] else 0, 0, 0)
        visible = True
        if name.endswith("__half"):
            visible = section
        elif section and base in HALF:
            visible = False
        if only is not None and not any(base.startswith(o) for o in only):
            visible = False
        if any(base.startswith(h) for h in hide):
            visible = False
        ob.hide_render = not visible
        if offsets:
            for key, off in offsets.items():
                if base.startswith(key):
                    ob.location = (ob.location[0] + off[0], ob.location[1] + off[1], ob.location[2] + off[2])
    ground.hide_render = False


def shot(name):
    scene.render.filepath = str(OUT / f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print("rendered", name)


L = P["eye_centres_open_mm"]
VIEWS_ALL = {
    "hero": lambda: (pose(), aim((-0.25, -0.85, 0.47), (-10, 0, -2), 600), shot("hero")),
    "service_side": lambda: (pose(), aim((-0.2, 0.85, 0.45), (-10, 0, -2), 600), shot("service_side")),
    "section": lambda: (pose(section=True, hide=("06_",)), aim((-0.06, -0.36, 0.93), (-7, 2, -3), 365), shot("section")),
    "wiring": lambda: (pose(hide=("06_",)), aim((-0.12, 0.88, 0.46), (-12, 6, -2), 300), shot("wiring")),
    "retracted": lambda: (pose(travel=0), aim((0, -0.93, 0.36), (-8, 0, -1), 640), shot("stroke_retracted")),
    "extended": lambda: (pose(travel=P["stroke_mm"]), aim((0, -0.93, 0.36), (-8, 0, -1), 640), shot("stroke_extended")),
    "core_part": lambda: (pose(travel=0, only=("motor_",)), aim((-0.30, -0.30, 0.90), (-CENTRE + 6, 0, 0), 190,
                                                                  roll=-52, ground_z=-6.05), shot("core_part")),
    "rod_end": lambda: (pose(travel=P["stroke_mm"]), aim((0.35, -0.75, 0.55), (52, 0, -1), 200), shot("detail_rod_end")),
    "cap_end": lambda: (pose(), aim((-0.55, -0.6, 0.55), (-48, 0, -1), 200), shot("detail_cap_end")),
}
for key in (VIEWS or VIEWS_ALL):
    VIEWS_ALL[key]()

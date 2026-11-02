"""Render the exported CAD tessellation in Blender Cycles (no geometry substitutions).

blender -b -P source/render_v6.py -- [--variant S|L|<name>] [--root DIR] [--quick] [--views hero,cutaway,...] [--out images]
--root reads DIR/source/scene_<v>.json.gz and DIR/parameters.json (build_v6.py --root) and writes
to DIR/images; it defaults to this package.
Blender axes: X = actuator axis (model z), Y = model x (board side away from the default
camera), Z = model y, the clevis-pin axis (eyes lie flat). A rotation, no mirroring.
"""
import bpy, gzip, json, math, sys
from pathlib import Path
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
QUICK = "--quick" in argv
VIEWS = argv[argv.index("--views") + 1].split(",") if "--views" in argv else None
VARIANT = argv[argv.index("--variant") + 1] if "--variant" in argv else "S"
root = Path(argv[argv.index("--root") + 1]).resolve() if "--root" in argv else Path(__file__).resolve().parent.parent
OUT = Path(argv[argv.index("--out") + 1]) if "--out" in argv else root / "images"
OUT.mkdir(parents=True, exist_ok=True)
with gzip.open(root / f"source/scene_{VARIANT}.json.gz", "rt") as f:
    data = json.load(f)
P = json.loads((root / "parameters.json").read_text())[VARIANT]
CENTRE = (P["rear_eye_z"] + P["eye_front_z"]) / 2 + P["stroke_mm"] / 4
GROUND = -7.4

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 16 if QUICK else 48
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 8
scene.render.resolution_x, scene.render.resolution_y = (800, 450) if QUICK else (1600, 900)
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
    preset = {"paint": (0.0, 0.34, 0.25), "plastic": (0.0, 0.46, 0.05), "silver": (0.75, 0.3, 0.1),
              "rubber": (0.0, 0.72, 0.0), "steel": (1.0, 0.28, 0.0), "brass": (1.0, 0.26, 0.0),
              "tin": (1.0, 0.3, 0.0), "black": (0.0, 0.4, 0.0), "ceramic": (0.0, 0.55, 0.0),
              "pcb": (0.0, 0.32, 0.45), "wire": (0.0, 0.35, 0.1), "backdrop": (0.0, 0.62, 0.0)}[kind]
    b.inputs["Metallic"].default_value, b.inputs["Roughness"].default_value, coat = preset
    b.inputs["Coat Weight"].default_value = coat
    if kind in ("paint", "plastic", "silver", "steel", "brass"):
        bev = nt.nodes.new("ShaderNodeBevel")
        bev.inputs["Radius"].default_value = 0.15 if kind in ("paint", "plastic", "silver") else 0.04
        nt.links.new(bev.outputs["Normal"], b.inputs["Normal"])
    MATS[key] = m
    return m


root_obj = bpy.data.objects.new("actuator", None)
scene.collection.objects.link(root_obj)
objects = {}
for item in data:
    verts = [(v[2] - CENTRE, v[0], v[1]) for v in item["vertices"]]
    mesh = bpy.data.meshes.new(item["name"])
    mesh.from_pydata(verts, [], [tuple(t) for t in item["triangles"]])
    mesh.validate()
    mesh.update()
    ob = bpy.data.objects.new(item["name"], mesh)
    scene.collection.objects.link(ob)
    ob.parent = root_obj
    kind, color = item["material"], item["color"]
    if item["kind"] in ("section", "cutaway") and kind == "silver":
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

bpy.ops.mesh.primitive_plane_add(size=3000, location=(0, 0, GROUND))
ground = bpy.context.object
ground.data.materials.append(material("backdrop", (0.90, 0.90, 0.89)))


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
cam_data.clip_end = 10000


def aim(direction, target, distance, lens=85, roll=0.0, ground_z=GROUND):
    d = Vector(direction).normalized()
    cam.location = Vector(target) + d * distance
    q = (-d).to_track_quat("-Z", "Y")
    if roll:
        from mathutils import Quaternion
        q = Quaternion(-d, math.radians(roll)) @ q
    cam.rotation_euler = q.to_euler()
    cam_data.lens = lens
    ground.location.z = ground_z


HIDE_IN_BOARD = ("motor_", "M3_brass_nut", "M2x10_rod_eye", "M1.6", "05_rod_eye")


def pose(travel=None, mode="exterior", only=None, hide=()):
    """mode: exterior | cutaway (pin-plane halves) | internal (housing hidden) | board (board side cut)."""
    travel = P["stroke_mm"] / 2 if travel is None else travel
    theta = -travel / P["mechanics"]["screw_pitch_mm"] * 2 * math.pi
    for name, ob in objects.items():
        ob.location = (travel if ob["moving"] else 0, 0, 0)
        ob.rotation_euler = (theta if ob["rotating"] else 0, 0, 0)
        kinematics = next(it for it in data if it["name"] == name).get("geartrain_rotation")
        if kinematics:
            from mathutils import Quaternion
            x, y, z = kinematics["axis_origin_mm"]
            pivot = Vector((z - CENTRE, x, y))
            ax, ay, az = kinematics["axis_direction"]
            rotation = Quaternion(Vector((az, ax, ay)), theta * kinematics["angle_per_output_rad"])
            ob.rotation_euler = rotation.to_euler()
            ob.location = pivot - rotation @ pivot
        k = ob["kind"]
        if k == "section":
            visible = mode == "cutaway"
        elif k == "cutaway":
            visible = mode == "board"
        elif k == "printed":
            visible = mode == "exterior" or (mode == "internal" and ob["moving"])
        elif k == "board":
            visible = mode != "exterior"
        elif k in ("tool", "xsection"):         # the assembly animation's screwdrivers and screw cut
            visible = False
        else:
            visible = True
        if mode == "board" and name.startswith(HIDE_IN_BOARD):
            visible = False
        if only is not None and not name.startswith(only):
            visible = False
        if name.startswith(hide):
            visible = False
        ob.hide_render = not visible


def shot(name):
    scene.render.filepath = str(OUT / f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print("rendered", name)


v = VARIANT
zb = (P["pcb_z"][0] + P["pcb_z"][1]) / 2 - CENTRE
far = 520 + (P["pin_centres_open"] - 160) * 8 / 3          # camera distance: 520 for V6-S, 760 for V6-L
VIEWS_ALL = {
    "hero": lambda: (pose(), aim((-0.25, -0.85, 0.47), (-6, 0, -1), far), shot(f"hero_{v}")),
    "cutaway": lambda: (pose(mode="cutaway"), aim((-0.06, -0.36, 0.93), (-4, 2, -3), far * 0.62), shot(f"cutaway_{v}")),
    "internal": lambda: (pose(mode="internal"), aim((-0.3, -0.8, 0.55), (-6, 2, 0), far * 0.62), shot(f"internals_{v}")),
    "board": lambda: (pose(travel=0, mode="board"), aim((0.0, -1.0, 0.2), (zb - 6, 6, 0), P["pcb_length"] * 3.7, lens=85),
                      shot(f"board_in_body_{v}")),
    "retracted": lambda: (pose(travel=0), aim((0, -0.93, 0.36), (-6, 0, -1), far * 1.06), shot(f"stroke_retracted_{v}")),
    "extended": lambda: (pose(travel=P["stroke_mm"]), aim((0, -0.93, 0.36), (-6, 0, -1), far * 1.06),
                         shot(f"stroke_extended_{v}")),
    "core_part": lambda: (pose(travel=0, only=("motor_",)), aim((-0.30, -0.30, 0.90), (-CENTRE - 10, 0, 0), 190,
                                                                 roll=-52, ground_z=-6.05), shot("core_part")),
    "rear_end": lambda: (pose(), aim((-0.82, 0.42, 0.40), (P["body_z"][0] - CENTRE - 6, 3, -1), 200),
                         shot(f"detail_rear_end_{v}")),
}
for key in (VIEWS or VIEWS_ALL):
    VIEWS_ALL[key]()

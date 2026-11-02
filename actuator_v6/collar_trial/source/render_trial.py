"""Render matching original/trial views and an exploded nut detail in Blender."""
from pathlib import Path
import sys
import gzip
import json

TRIAL = Path(__file__).resolve().parents[1]
BASE = TRIAL.parent
sys.argv = [__file__, "--", "--root", str(TRIAL), "--variant", "U60"]
# Reuse the released studio setup and CAD mesh importer, stopping before its shot loop.
setup = (BASE / "source" / "render_v6.py").read_text().split("\nv = VARIANT\n")[0]
exec(compile(setup, str(BASE / "source" / "render_v6.py"), "exec"), globals())

scene.cycles.samples = 24
scene.render.resolution_x, scene.render.resolution_y = 1600, 650
cam_data.type = "ORTHO"
cam_data.ortho_scale = 215
changed = {"01_body", "02_front_cap", "03_rear_cap", "06_cable_clamp"}
changed.update(f"M2x{length}_{end}_cap_{i}" for end, length in (("front", 8), ("rear", 10)) for i in (1, 2))
with gzip.open(BASE / "source" / "scene_U60.json.gz", "rt") as f:
    original = json.load(f)
for it in original:
    if it["name"] not in changed:
        continue
    mesh = bpy.data.meshes.new("original_" + it["name"])
    mesh.from_pydata([(v[2] - CENTRE, v[0], v[1]) for v in it["vertices"]], [], it["triangles"])
    mesh.update()
    ob = bpy.data.objects.new("original_" + it["name"], mesh)
    scene.collection.objects.link(ob)
    ob.parent = root_obj
    ob.data.materials.append(material(it["material"], it["color"]))
    for p in mesh.polygons:
        p.use_smooth = True
    mesh.set_sharp_from_angle(angle=math.radians(32))
    ob["moving"], ob["kind"] = False, "original"
    objects[ob.name] = ob


def exterior(stock=False):
    for name, ob in objects.items():
        ob.location = (30 if ob["moving"] else 0, 0, 0)
        ob.rotation_euler = (0, 0, 0)
        visible = ob["kind"] in ("printed", "hardware", "wire", "board")
        if name.startswith("original_"):
            visible = stock
        elif name in changed or name.startswith("M2_nut_"):
            visible = not stock
        ob.hide_render = not visible


for stock, label in ((True, "original"), (False, "trial")):
    exterior(stock)
    aim((-0.25, -0.85, 0.47), (-5, 1.7, -1), 600, ground_z=-7.4 if stock else -11.6)
    shot(label)

exterior()
aim((-0.40, 0.85, 0.44), (-5, 1.7, -1), 600, ground_z=-11.6)
shot("trial_fastener_side")

# The front band is an actual cropped solid. Nuts move sideways; the cap moves axially.
for name, ob in objects.items():
    ob.location = (0, 0, 0)
    ob.hide_render = True
    if name == "detail_front_band":
        ob.hide_render = False
    elif name == "02_front_cap":
        ob.hide_render = False
        ob.location.x = 18
    elif name.startswith("M2_nut_front_"):
        ob.hide_render = False
        ob.location.y = 9
    elif name.startswith("M2x8_front_cap_"):
        ob.hide_render = False
        ob.location.x = 24
cam_data.ortho_scale = 76
scene.render.resolution_x, scene.render.resolution_y = 1400, 1050
aim((0.65, 1, 0.8), (P["body_z"][1] - CENTRE + 5, 7, 0), 250, ground_z=-12)
shot("nut_detail")

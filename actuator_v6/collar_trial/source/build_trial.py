"""Build the U60 collar/nut trial without changing the released V6 geometry.

Run with the same CadQuery environment as actuator_v6/source/build_v6.py.
The scene reuses the released motor, PCB, wires and rod meshes verbatim.
"""
from pathlib import Path
import gzip
import itertools
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent
sys.path.insert(0, str(BASE / "source"))
import cadquery as cq
import trimesh
import layout as L
import design_v6 as D
from cad_utils import box, cylinder, hex_z, rr_box

V = "U60"
P = L.derived(V)
Z0, Z1 = P["body_z"]
SCREWS = ((8.0, 7.2), (8.0, -7.2))
# Reinforced body: 20.1 x 20.7; cap skirt: 22.5 x 23.1.
BAND = (-8.35, 11.75, 10.35, 2.3)
CAP = (-9.55, 12.95, 11.55, 3.5)
SKIRT_INNER = (-8.55, 11.95, 10.55, 2.5)
BAND_LENGTH = 8.0
TAPER_LENGTH = 5.0
NUT_AF, NUT_T = 4.0, 1.6
POCKET_AF, POCKET_T = 4.2, 1.9
SHOULDER = 2.4


def prism(spec, lo, hi):
    a, b, y, r = spec
    return rr_box(a, b, -y, y, lo, hi, r)


def wire(spec, z):
    a, b, y, r = spec
    return D.rr_wire(a, b, -y, y, r, z)


def volume(shape):
    return sum(s.Volume() for s in shape.solids().vals())


def intersection(a, b):
    return volume(a.intersect(b))


def mesh(shape):
    vertices, faces = shape.val().tessellate(0.025, 0.1)
    return dict(vertices=[[round(v.x, 5), round(v.y, 5), round(v.z, 5)] for v in vertices],
                triangles=[list(t) for t in faces])


def make_trial():
    original_screws = L.CAP_SCREWS
    original_outline = D.outline
    original_radius = L.BODY_R
    old_bounds = D.X0, D.X1, D.YH
    # Rebuild the original body with no obsolete pilot holes and flat mating ends.
    L.CAP_SCREWS = ()
    D.outline = lambda lo, hi, *args, **kwargs: original_outline(lo, hi)
    core = D.make_body(P)
    D.outline = original_outline
    body = core
    normal = (*L.BODY_X, L.BODY_Y, L.BODY_R)
    reference_envelope = prism(normal, Z0 - 1, Z1 + 1)
    for end, sign in ((Z0, 1), (Z1, -1)):
        lo, hi = sorted((end, end + sign * BAND_LENGTH))
        band = prism(BAND, lo, hi)
        w0 = wire(BAND, end + sign * BAND_LENGTH)
        w1 = wire(normal, end + sign * (BAND_LENGTH + TAPER_LENGTH))
        taper = cq.Workplane(obj=cq.Solid.makeLoft([w0, w1], True))
        body = body.union(band.union(taper).cut(reference_envelope))

    nuts, insertion_envelopes = {}, {}
    for label, end, sign in (("rear", Z0, 1), ("front", Z1, -1)):
        p0, p1 = sorted((end + sign * SHOULDER, end + sign * (SHOULDER + POCKET_T)))
        n0, n1 = sorted((end + sign * SHOULDER, end + sign * (SHOULDER + NUT_T)))
        for i, (x, y) in enumerate(SCREWS, 1):
            pocket = hex_z(POCKET_AF, p1 - p0, p0).translate((x, y, 0))
            entry = box(15 - x, POCKET_AF, p1 - p0, x=(15 + x) / 2, y=y, z=(p0 + p1) / 2)
            body = body.cut(pocket.union(entry))
            lo, hi = sorted((end - sign, end + sign * 7.5))
            body = body.cut(cylinder(1.1, hi - lo, lo).translate((x, y, 0)))
            nut = hex_z(NUT_AF, n1 - n0, n0).cut(cylinder(1.0, n1 - n0 + 0.2, n0 - 0.1))
            nuts[f"M2_nut_{label}_{i}"] = nut.translate((x, y, 0))
            # The solid outer hex is swept from the +X side before installing the cap.
            outer_nut = hex_z(NUT_AF, n1 - n0, n0).translate((x, y, 0))
            insertion_envelopes[f"{label}_{i}"] = [outer_nut.translate((dx, 0, 0)) for dx in (0, 1, 2, 3, 4, 5, 6)]

    # The released functions preserve the rod guide, spigot, clevis and cable clamp.
    L.CAP_SCREWS = SCREWS
    D.X0, D.X1, D.YH, L.BODY_R = CAP
    front = D.make_front_cap(P)
    rear = D.make_rear_cap(P)
    clamp = D.make_cable_clamp(P)
    for label, end, sign in (("rear", Z0, 1), ("front", Z1, -1)):
        lo, hi = sorted((end, end + sign * BAND_LENGTH))
        outer = prism(CAP, lo, hi)
        outer = outer.faces(">Z" if sign > 0 else "<Z").edges().chamfer(0.35)
        shell = outer.cut(prism(SKIRT_INNER, lo - 0.1, hi + 0.1))
        if label == "front":
            front = front.union(shell)
        else:
            rear = rear.union(shell)
    L.CAP_SCREWS = original_screws
    D.X0, D.X1, D.YH = old_bounds
    L.BODY_R = original_radius

    printed = {"01_body": body, "02_front_cap": front, "03_rear_cap": rear, "06_cable_clamp": clamp}
    bolts = {}
    for i, (x, y) in enumerate(SCREWS, 1):
        bolts[f"M2x8_front_cap_{i}"] = D.pan_m2(x, y, Z1 + L.FRONT_CAP_T - 2.5 + 1.6, 1, 8)
        bolts[f"M2x10_rear_cap_{i}"] = D.pan_m2(x, y, D.CLAMP_Z - L.CLAMP_T + 1.8 - 1.6, -1, 10)
    return core, printed, nuts, bolts, insertion_envelopes


def validate(core, parts, nuts, bolts, insertions):
    checks = {}
    all_shapes = parts | nuts | bolts
    for name, shape in all_shapes.items():
        checks[f"valid_{name}"] = bool(shape.val().isValid() and len(shape.solids().vals()) == 1)
    overlaps = []
    for (a, sa), (b, sb) in itertools.combinations(all_shapes.items(), 2):
        overlap = intersection(sa, sb)
        if overlap > 1e-5:
            overlaps.append(dict(a=a, b=b, volume_mm3=round(overlap, 6)))
    checks["no_new_assembly_intersections"] = not overlaps
    insert_max = max(intersection(parts["01_body"], s) for shapes in insertions.values() for s in shapes)
    checks["nuts_insert_from_side_with_caps_removed"] = insert_max < 1e-5
    # Slipping the skirts over the bands must work along their complete assembly path.
    cap_sweep = {}
    for name, sign in (("02_front_cap", 1), ("03_rear_cap", -1)):
        cap_sweep[name] = max(intersection(parts["01_body"], parts[name].translate((0, 0, sign * step)))
                              for step in (0, 0.5, 1, 2, 4, 6, 8, 12))
    checks["caps_slide_over_reinforced_bands"] = max(cap_sweep.values()) < 1e-5
    rod = D.make_rod(P)
    motion = []
    for travel in (0, 10, 20, 30, 40, 50, 60):
        posed = rod.translate((0, 0, travel))
        motion.append(dict(travel_mm=travel, overlap_mm3=max(intersection(posed, parts[n])
                      for n in ("01_body", "02_front_cap", "03_rear_cap"))))
    checks["rod_clears_at_seven_stroke_positions"] = max(r["overlap_mm3"] for r in motion) < 1e-5
    # The stock electronics and motor cavity remain unobstructed by the reinforcement.
    normal = (*L.BODY_X, L.BODY_Y, L.BODY_R)
    inside_original = parts["01_body"].intersect(prism(normal, Z0, Z1))
    added_inside = volume(inside_original.cut(core))
    checks["no_added_material_inside_original_body_envelope"] = added_inside < 1e-5
    report = dict(status="CAD trial; not load-tested or cleared against the excavator arm",
                  checks=checks, all_passed=all(checks.values()), overlaps=overlaps,
                  nut_insertion_max_overlap_mm3=insert_max, cap_sweep_overlap_mm3=cap_sweep,
                  stroke_checks=motion, added_material_inside_original_envelope_mm3=added_inside,
                  dimensions=dict(original_body_section_mm=[16.1, 14.7], collar_section_mm=[22.5, 23.1],
                                  reinforced_band_mm=[20.1, 20.7], collar_overlap_mm=BAND_LENGTH,
                                  taper_length_mm=TAPER_LENGTH, skirt_radial_clearance_mm=0.2,
                                  skirt_wall_mm=1.0, nut_af_mm=NUT_AF, nut_thickness_mm=NUT_T,
                                  pocket_af_mm=POCKET_AF, pocket_thickness_mm=POCKET_T,
                                  nut_bearing_shoulder_mm=SHOULDER, nut_to_pcb_slot_ligament_mm=1.0,
                                  screw_centres_xy_mm=SCREWS, stroke_mm=60, pin_centres_mm=[140, 200],
                                  front_screw_tip_beyond_nut_mm=0.5, rear_screw_tip_beyond_nut_mm=1.8))
    return report


def export(core, printed, nuts, bolts, report):
    for name in ("step", "stl", "images", "source"):
        (ROOT / name).mkdir(exist_ok=True, parents=True)
    for name, shape in printed.items():
        cq.exporters.export(shape, str(ROOT / "step" / f"{name}.step"))
        # Front cap prints with its external face down; rear cap clevis needs supports.
        oriented = shape.rotate((0, 0, 0), (1, 0, 0), 180) if name == "02_front_cap" else shape
        bb = oriented.val().BoundingBox()
        oriented = oriented.translate((-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))
        dest = ROOT / "stl" / f"{name}.stl"
        cq.exporters.export(oriented, str(dest), tolerance=0.025, angularTolerance=0.1)
        m = trimesh.load(dest, force="mesh")
        report["checks"][f"watertight_{name}"] = bool(m.is_watertight and m.is_volume)
    coupon = printed["01_body"].intersect(box(40, 40, 14, z=Z1 - 7))
    coupon = coupon.translate((0, 0, -(Z1 - 14)))
    cq.exporters.export(coupon, str(ROOT / "stl" / "07_front_band_fit_sample.stl"), tolerance=0.025, angularTolerance=0.1)
    report["checks"]["watertight_fit_sample"] = bool(trimesh.load(ROOT / "stl" / "07_front_band_fit_sample.stl").is_watertight)
    assembly = cq.Assembly(name="U60_collar_trial_housing")
    colors = {"01_body": (0.93, 0.42, 0.09), "06_cable_clamp": (0.30, 0.31, 0.33)}
    for name, shape in (printed | nuts | bolts).items():
        color = colors.get(name, (0.10, 0.105, 0.115) if name[0].isdigit() else (0.70, 0.72, 0.75))
        assembly.add(shape, name=name, color=cq.Color(*color))
    assembly.save(str(ROOT / "step" / "collar_housing_assembly.step"))
    with gzip.open(BASE / "source" / "scene_U60.json.gz", "rt") as f:
        stock_scene = json.load(f)
    scene = [it for it in stock_scene if it["kind"] in ("printed", "hardware", "board", "wire")
             and it["name"] not in (printed | bolts)]
    for name, shape in (printed | nuts | bolts).items():
        is_print = name in printed
        scene.append(dict(name=name, kind="printed" if is_print else "hardware", moving=False, rotating=False,
                          material="paint" if name == "01_body" else "plastic" if is_print else "steel",
                          color=colors.get(name, (0.10, 0.105, 0.115) if is_print else (0.70, 0.72, 0.75)), **mesh(shape)))
    # Detailed assembly views use real solids, not a decorative replacement shape.
    body_slice = printed["01_body"].intersect(box(50, 50, 17, z=Z1 - 8.5))
    scene.append(dict(name="detail_front_band", kind="detail", moving=False, rotating=False,
                      material="paint", color=colors["01_body"], **mesh(body_slice)))
    for name, shape in printed.items():
        section = shape.intersect(box(80, 40, 400, y=20))
        scene.append(dict(name=name + "__section", kind="section", moving=False, rotating=False,
                          material="paint" if name == "01_body" else "plastic", color=colors.get(name, (0.1, 0.105, 0.115)),
                          **mesh(section)))
    with gzip.open(ROOT / "source" / "scene_U60.json.gz", "wt") as f:
        json.dump(scene, f, separators=(",", ":"))
    (ROOT / "parameters.json").write_text(json.dumps({"U60": json.loads((BASE / "parameters.json").read_text())["U60"]}, indent=2) + "\n")
    report["all_passed"] = all(report["checks"].values())
    (ROOT / "validation.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    print("Building collar trial", flush=True)
    core, printed, nuts, bolts, insertions = make_trial()
    print("Checking assembly, nut insertion and stroke", flush=True)
    report = validate(core, printed, nuts, bolts, insertions)
    print("Exporting trial CAD and render meshes", flush=True)
    export(core, printed, nuts, bolts, report)
    print(json.dumps(report, indent=2), flush=True)
    if not report["all_passed"]:
        raise SystemExit("Trial verification failed")

"""Build V5: STEP/STL export, render meshes, parameters, wiring data and validation.

python source/build_v5.py [--screw-length 40] [--preview] [--out DIR]
--preview writes only the render meshes (fast iteration).
"""
from pathlib import Path
import argparse, itertools, json, time
import cadquery as cq
import numpy as np
from design_v5 import make_design, make_hall, make_harness

ROOT = Path(__file__).resolve().parent.parent

PRINTED_LOOK = {
    "01_barrel": ((0.99, 0.75, 0.04), "paint"),
    "04_pushrod": ((0.80, 0.82, 0.84), "chrome"),
    "07_TPU_cable_boot": ((0.05, 0.05, 0.055), "rubber"),
}
PRINT_SETTINGS = {
    "01_barrel": "PETG yellow, rear face down, 0.2 mm, 4 walls, 30% gyroid",
    "02_rear_cap": "PETG black, collar opening down, 0.16 mm, 4 walls, 40% gyroid",
    "03_head_collar": "PETG black, nose down, 0.16 mm, 4 walls",
    "04_pushrod": "PETG silver, carrier down, 0.16 mm, 100% infill",
    "05_rod_eye": "PETG black, socket opening down, 0.16 mm, 100% infill",
    "06_sensor_cover": "PETG black, flat inner face down, 0.12 mm",
    "07_TPU_cable_boot": "TPU 95A, taper end down",
}


def look(name):
    if name in PRINTED_LOOK:
        return PRINTED_LOOK[name]
    if name[:2].isdigit():
        return (0.11, 0.12, 0.13), "plastic"
    if name == "cable_jacket":
        return (0.035, 0.04, 0.045), "rubber"
    table = [("motor_can", (0.80, 0.81, 0.82), "steel"), ("motor_end_cap", (0.04, 0.04, 0.045), "black"),
             ("motor_rear_boss", (0.04, 0.04, 0.045), "black"), ("motor_terminal", (0.86, 0.86, 0.83), "tin"),
             ("motor_gearbox_frame", (0.86, 0.66, 0.30), "brass"), ("motor_front_bushing", (0.74, 0.56, 0.32), "brass"),
             ("motor_gear", (0.60, 0.62, 0.64), "steel"), ("motor_leadscrew", (0.74, 0.76, 0.78), "steel"),
             ("M3_nut", (0.84, 0.66, 0.32), "brass"), ("magnet", (0.76, 0.77, 0.79), "steel"),
             ("M2", (0.07, 0.07, 0.08), "blackmetal"), ("dowel", (0.70, 0.71, 0.73), "steel"), ("_pin", (0.86, 0.86, 0.83), "tin"),
             ("_end_", (0.86, 0.86, 0.83), "tin"), ("_C_100n", (0.62, 0.47, 0.30), "ceramic"),
             ("_R_4k7", (0.05, 0.05, 0.05), "black"), ("DRV5033", (0.05, 0.05, 0.06), "black")]
    for key, color, mat in table:
        if key in name:
            return color, mat
    return (0.6, 0.6, 0.6), "steel"


def mesh_data(shape, tol=0.03, ang=0.1):
    vs, fs = shape.val().tessellate(tol, ang)
    return dict(vertices=[[round(v.x, 4), round(v.y, 4), round(v.z, 4)] for v in vs], triangles=[list(f) for f in fs])


def section_halves(d):
    from cad_utils import box
    keep = box(100, 100, 400, x=-50, z=0)   # model x < 0; the cut face shows at the clevis-pin plane
    return {n + "__half": s.intersect(keep) for n, s in d["printed"].items() if not n.startswith("07_")}


def scene_items(d):
    items = []
    groups = [("printed", d["printed"]), ("section", section_halves(d)), ("hardware", d["hardware"]),
              ("wire", d["wires"]), ("soft", {"cable_jacket": d["jacket"]})]
    for kind, parts in groups:
        for name, shape in parts.items():
            if kind == "wire":
                m = d["wire_meta"][name]
                color, mat = m["color"], "wire"
                extra = dict(net=m["net"], wire_id=m["wire_id"], diameter_mm=m["od_mm"])
            else:
                base = name.replace("__half", "")
                color, mat = look(base)
                extra = {}
            k = "soft" if name.startswith("07_") else kind
            items.append(dict(name=name, kind=k, material=mat, color=[round(c, 4) for c in color],
                              moving=name.replace("__half", "") in d["moving"],
                              rotating=name == "motor_leadscrew_M3", **extra, **mesh_data(shape)))
    return items


def overlap(a, b):
    aa, bb = a.val().BoundingBox(), b.val().BoundingBox()
    for ax in "xyz":
        if getattr(aa, ax + "min") >= getattr(bb, ax + "max") - 1e-7 or getattr(bb, ax + "min") >= getattr(aa, ax + "max") - 1e-7:
            return 0.0
    return sum(s.Volume() for s in a.intersect(b).solids().vals())


def orient_for_print(name, shape):
    if name in ("02_rear_cap", "03_head_collar"):
        shape = shape.rotate((0, 0, 0), (1, 0, 0), 180)
    elif name.startswith("06_"):
        shape = shape.rotate((0, 0, 0), (1, 0, 0), -90)
    elif name.startswith("07_"):
        shape = shape.rotate((0, 0, 0), (1, 0, 0), 90)
    bb = shape.val().BoundingBox()
    return shape.translate((-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))


def fit_samples(d):
    from cad_utils import box
    p = d["params"]
    b, r, s = d["printed"]["01_barrel"], d["printed"]["04_pushrod"], d["printed"]["06_sensor_cover"]
    lip = p["lip_z"][0]
    return {"08_fit_motor_step_and_channel": b.intersect(box(60, 60, 20, z=4.0)),
            "09_fit_carrier": r.intersect(box(60, 60, 14, z=9.0)),
            "10_fit_front_lip": b.intersect(box(60, 60, 10, z=lip + 3.0)),
            "11_fit_cover_strip": s.intersect(box(60, 60, 20, z=4.0))}


def export(d, out):
    import trimesh
    report = {}
    for sub in ("step", "stl", "stl/soft", "stl/fit_samples"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    parts = dict(d["printed"])
    parts.update(fit_samples(d))
    for name, shape in parts.items():
        assert shape.val().isValid() and len(shape.solids().vals()) == 1, name
        step_file = out / "step" / f"{name}.step"
        cq.exporters.export(shape, str(step_file))
        solid = cq.importers.importStep(str(step_file)).solids().val()
        assert solid.isValid(), ("STEP round trip", name)
        oriented = orient_for_print(name, cq.Workplane(obj=solid.clean()))
        folder = "stl/soft" if "TPU" in name else ("stl/fit_samples" if "fit" in name else "stl")
        f = out / folder / f"{name}.stl"
        cq.exporters.export(oriented, str(f), tolerance=0.02, angularTolerance=0.1)
        mesh = trimesh.load_mesh(f)
        keep = mesh.nondegenerate_faces(height=1e-8)
        removed = len(keep) - int(np.count_nonzero(keep))
        if removed:
            mesh.update_faces(keep); mesh.remove_unreferenced_vertices(); mesh.export(f)
        report[name] = dict(watertight=bool(mesh.is_watertight), winding_consistent=bool(mesh.is_winding_consistent),
                            components=len(mesh.split(only_watertight=False)),
                            zero_height_facets_removed=removed, print_extent_mm=np.round(mesh.extents, 2).tolist(),
                            volume_mm3=round(shape.val().Volume(), 1), print_setup=PRINT_SETTINGS.get(name, "fit sample, as main part"))
    assy = cq.Assembly(name="V5_hydraulic_style_actuator")
    for name, shape in d["printed"].items():
        assy.add(shape, name=name, color=cq.Color(*look(name)[0]))
    for name, shape in d["hardware"].items():
        assy.add(shape, name=name, color=cq.Color(*look(name)[0]))
    for name, shape in d["wires"].items():
        assy.add(shape, name="wire_" + name, color=cq.Color(*d["wire_meta"][name]["color"]))
    assy.add(d["jacket"], name="cable_jacket", color=cq.Color(*look("cable_jacket")[0]))
    assy.export(str(out / "step" / "assembly_retracted.step"))
    return report


def validate(d):
    p, pr, hw, wires = d["params"], d["printed"], d["hardware"], d["wires"]
    moving = set(d["moving"])
    fixed_pr = {n: s for n, s in pr.items() if n not in moving}
    fixed_hw = {n: s for n, s in hw.items() if n not in moving}
    # Intentional contacts: thread engagement and the screw passing through its own nut.
    allowed = {("M3_nut", "motor_leadscrew_M3")}
    rep = {"units": "mm", "fixed_interferences": [], "wire_interferences": [], "wire_wire_interferences": [],
           "motion": [], "wire_terminal_contacts": []}
    for (an, a), (bn, b) in itertools.combinations(list(fixed_pr.items()) + [("cable_jacket", d["jacket"])], 2):
        v = overlap(a, b)
        if v > 0.002: rep["fixed_interferences"].append([an, bn, round(v, 4)])
    for pn, ps in fixed_pr.items():
        for hn, hs in fixed_hw.items():
            v = overlap(ps, hs)
            if v > 0.002: rep["fixed_interferences"].append([pn, hn, round(v, 4)])
    for hn, hs in fixed_hw.items():
        if hn.startswith("motor_"):
            continue
        for mn, ms in fixed_hw.items():
            if mn.startswith("motor_") and mn != "motor_leadscrew_M3":
                v = overlap(hs, ms)
                if v > 0.002: rep["fixed_interferences"].append([hn, mn, round(v, 4)])
    obstacles = dict(fixed_pr); obstacles["cable_jacket_wall"] = d["jacket"]; obstacles.update(fixed_hw)
    for wn, ws in wires.items():
        for on, os_ in obstacles.items():
            v = overlap(ws, os_)
            if v > 0.001: rep["wire_interferences"].append([wn, on, round(v, 4)])
    for (an, a), (bn, b) in itertools.combinations(wires.items(), 2):
        v = overlap(a, b)
        if v > 0.0005: rep["wire_wire_interferences"].append([an, bn, round(v, 4)])
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    def dist(a, b):
        x = BRepExtrema_DistShapeShape(a.val().wrapped, b.val().wrapped); x.Perform(); return x.Value()
    for wn, m in d["wire_meta"].items():
        sp = m["start_pin"]
        target = (f"motor_terminal_{sp['motor_terminal']}" if "motor_terminal" in sp
                  else f"Hall_{sp['sensor']}_pin{sp['pin']}_{ {1: 'VCC', 2: 'GND', 3: 'OUT'}[sp['pin']] }")
        g = dist(wires[wn], hw[target])
        rep["wire_terminal_contacts"].append(dict(wire=wn, wire_id=m["wire_id"], terminal=target, gap_mm=round(g, 6)))
    statics = dict(fixed_pr); statics.update(fixed_hw); statics.update(wires); statics["cable_jacket"] = d["jacket"]
    travels = [p["mechanical_stop_retract_mm"]] + list(np.linspace(0, p["stroke_mm"], 7)) + [p["mechanical_stop_extend_mm"]]
    for t in travels:
        hits = []
        for mn in moving:
            ms = (pr.get(mn) or hw.get(mn)).translate((0, 0, float(t)))
            for sn, ss in statics.items():
                if (mn, sn) in allowed:
                    continue
                v = overlap(ms, ss)
                if v > 0.002: hits.append([mn, sn, round(v, 4)])
        rep["motion"].append(dict(travel_mm=round(float(t), 2), interferences=hits))
    # Sensor calibration: each Hall slides +-3 mm in the channel; re-dressed wires must still clear.
    rep["sensor_reroutes"] = []
    for offs in [(-3, 0), (3, 0), (0, -3), (0, 3)]:
        ww, jj, _, _ = make_harness(p, offs)
        hh = {}
        for label, zc, o in zip(("retract", "extend"), p["sensor_centres_z"], offs):
            h, _, _, _ = make_hall(label, zc + o)
            hh.update(h)
        obst = dict(fixed_pr); obst.update({n: s for n, s in fixed_hw.items() if not n.startswith("Hall_")}); obst.update(hh)
        hits = [[wn, on] for wn, ws in ww.items() for on, os_ in obst.items() if overlap(ws, os_) > 0.001]
        hits += [[a, b] for (a, x), (b, y) in itertools.combinations(ww.items(), 2) if overlap(x, y) > 0.0005]
        rep["sensor_reroutes"].append(dict(offsets_mm=list(offs), interferences=hits))
    rep["all_checks_pass"] = (not rep["fixed_interferences"] and not rep["wire_interferences"]
                              and not rep["wire_wire_interferences"] and all(not m["interferences"] for m in rep["motion"])
                              and all(c["gap_mm"] < 1e-5 for c in rep["wire_terminal_contacts"])
                              and all(not r["interferences"] for r in rep["sensor_reroutes"]))
    return rep


def run():
    ap = argparse.ArgumentParser()
    ap.add_argument("--screw-length", type=float, default=40.0)
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--out", type=Path, default=ROOT)
    a = ap.parse_args()
    t0 = time.time()
    d = make_design(a.screw_length)
    out = a.out
    (out / "source").mkdir(parents=True, exist_ok=True)
    items = scene_items(d)
    (out / "source" / "scene_meshes.json").write_text(json.dumps(items, separators=(",", ":")))
    (out / "parameters.json").write_text(json.dumps(d["params"], indent=2))
    print("meshes", len(items), round(time.time() - t0, 1), "s")
    if a.preview:
        return
    parts = export(d, out)
    print("export", round(time.time() - t0, 1), "s")
    (out / "wiring_routes.json").write_text(json.dumps({"wires": d["wire_meta"], "hall_modules": d["hall_meta"]}, indent=2))
    rows = ["wire_id,model_name,net,insulation_od_mm,model_centerline_mm,model_min_bend_radius_mm,note"]
    for n, m in d["wire_meta"].items():
        rows.append(f"{m['wire_id']},{n},{m['net']},{m['od_mm']},{m['centerline_length_mm']},{m['min_bend_radius_mm']},"
                    "\"Model tail only (8 mm past the jacket). Add vehicle routing and calibration allowance.\"")
    (out / "wire_lengths.csv").write_text("\n".join(rows) + "\n")
    rep = validate(d)
    rep["parts"] = parts
    rep["all_meshes_pass"] = all(v["watertight"] and v["winding_consistent"] and v["components"] == 1 for v in parts.values())
    rep["all_checks_pass"] = rep["all_checks_pass"] and rep["all_meshes_pass"]
    (out / "validation.json").write_text(json.dumps(rep, indent=2))
    summary = {k: v for k, v in rep.items() if k not in ("parts", "motion", "wire_terminal_contacts", "sensor_reroutes")}
    print(json.dumps(summary, indent=1))
    print("motion hits:", [m for m in rep["motion"] if m["interferences"]])
    print("reroute hits:", [r for r in rep["sensor_reroutes"] if r["interferences"]])
    print("terminal gaps:", [(c["wire"], c["gap_mm"]) for c in rep["wire_terminal_contacts"]])
    print("total", round(time.time() - t0, 1), "s")
    assert rep["all_checks_pass"], "Resolve the reported problems."


if __name__ == "__main__":
    run()

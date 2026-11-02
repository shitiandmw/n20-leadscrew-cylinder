"""Build V6: STEP/STL export, viewer meshes, parameters and validation, for each screw length.

python source/build_v6.py [--variant S|U60|L|<name>|all] [--custom NAME=SCREW:STROKE ...] [--root DIR] [--preview]
    -> step/V6-<v>/  stl/V6-<v>/  stl/fit_samples/  parameters.json  validation.json
       wire_lengths_<v>.csv  source/scene_<v>.json.gz (viewer and render meshes)
"all" builds the lengths in layout.VARIANTS: S, U60 and L.
--custom adds another stock leadscrew length and nominal stroke in mm, e.g. --custom X80=80:65;
    "all" then means only the custom lengths.
--root writes the outputs into another package folder; the magnet model and the circuit
    simulation are still read from this one. Existing parameters.json entries keep extra keys.
--preview writes only the meshes, parameters and wire lengths (fast iteration).
--motor-only replaces motor meshes and assembly STEP files and reruns assembled
clearance checks, preserving all non-motor scene items and printable part files.
"""
from pathlib import Path
import argparse
import gzip
import itertools
import json
import math
import re
import time
import cadquery as cq
import numpy as np
import layout as L
import board as BD
from cad_utils import box, cylinder
import design_v6 as DS
import assembly as AS
from gear_spec import transmission
from design_v6 import make_design

HOME = Path(__file__).resolve().parent.parent       # this package: shared inputs
ROOT = HOME                                          # output package (--root, or set by an importing script)
PETG_DENSITY = 1.27            # g/cm3

PRINT_SETTINGS = {
    "01_body": "PETG, rear end down (flat face, chamfered motor-bay mouth), 5 mm brim, 0.2 mm layers, 3 walls, "
               "25 % gyroid, no supports. The motor wall bridges the motor bay; its countersinks, the carrier "
               "stop and the board rest are top surfaces.",
    "02_front_cap": "PETG, outer face down, 0.16 mm, 4 walls, 40 % gyroid, no supports.",
    "03_rear_cap": "PETG, flat front face down (clevis up), 0.16 mm, 4 walls, 60 % gyroid, no supports.",
    "04_rod": "PETG, carrier down, 0.16 mm, 100 % infill, 3 mm brim; slow the last 20 mm of the L rod.",
    "05_rod_eye": "PETG, socket opening down, 0.16 mm, 100 % infill, no supports.",
    "06_cable_clamp": "PETG, flat back down (groove up), 0.16 mm, 100 % infill, no supports.",
    "08_fit_body_wall": "As 01_body, rear end down. Checks the motor bay, the M1.6 countersinks, the board "
                        "groove and the key rib.",
    "09_fit_carrier": "As 04_rod. Checks the nut slot, the magnet pocket and the slide in 08 (one way round only).",
}
FLIP = ("02_", "03_")                        # printed upside down (model +Z on the bed)


# ---- looks (shared by the viewer and the Blender render) ------------------------------------
def hex_rgb(h):
    return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))


def look(name, meta=None):
    if name.startswith("PCB_"):
        k = meta["kind"]
        if k == "board":
            return (0.04, 0.26, 0.14), "pcb"
        if k == "copper":
            return ((0.80, 0.80, 0.77), "tin") if meta["layer"] == "top pads" else ((0.10, 0.40, 0.21), "pcb")
        if k == "part_leads":
            return (0.80, 0.80, 0.77), "tin"
        mat = "ceramic" if meta["package"] in ("0603", "1206") else "black"
        return hex_rgb(meta["colour"]), mat
    printed = {"01_body": ((0.93, 0.42, 0.09), "paint"), "04_rod": ((0.80, 0.82, 0.84), "silver"),
               "06_cable_clamp": ((0.30, 0.31, 0.33), "plastic"),
               "08_fit_body_wall": ((0.93, 0.42, 0.09), "paint"), "09_fit_carrier": ((0.80, 0.82, 0.84), "silver")}
    if name in printed:
        return printed[name]
    if name[:2].isdigit():
        return (0.10, 0.105, 0.115), "plastic"
    table = [("motor_can", (0.80, 0.81, 0.82), "steel"), ("motor_end_cap", (0.04, 0.04, 0.045), "black"),
             ("motor_rear_boss", (0.04, 0.04, 0.045), "black"), ("motor_terminal", (0.86, 0.86, 0.83), "tin"),
             ("motor_gearbox_frame", (0.86, 0.66, 0.30), "brass"), ("motor_front_bushing", (0.74, 0.56, 0.32), "brass"),
             ("motor_bushing", (0.74, 0.56, 0.32), "brass"),
             ("motor_gear", (0.60, 0.62, 0.64), "steel"), ("motor_leadscrew", (0.74, 0.76, 0.78), "steel"),
             ("brass_nut", (0.84, 0.66, 0.32), "brass"), ("magnet", (0.76, 0.77, 0.79), "steel"),
             ("M1.6", (0.72, 0.73, 0.75), "steel"), ("M2", (0.72, 0.73, 0.75), "steel"),
             ("cable_sleeve", (0.16, 0.16, 0.17), "wire"), ("tool_PH0_handle", (0.78, 0.12, 0.10), "plastic"),
             ("tool_PH1_handle", (0.93, 0.66, 0.10), "plastic"), ("tool_", (0.80, 0.81, 0.83), "steel")]
    for key, color, mat in table:
        if key in name:
            return color, mat
    return (0.6, 0.6, 0.6), "steel"


def one_shape(wp):
    objs = wp.vals()
    return objs[0] if len(objs) == 1 else cq.Compound.makeCompound(objs)


def mesh_data(wp, tol=0.03, ang=0.1):
    vs, fs = one_shape(wp).tessellate(tol, ang)
    return dict(vertices=[[round(v.x, 4), round(v.y, 4), round(v.z, 4)] for v in vs], triangles=[list(f) for f in fs])


def section_halves(d):
    keep = box(100, 100, 600, y=-50)          # keeps model y < 0; the cut face is the XZ plane
    return {n + "__half": s.intersect(keep) for n, s in d["printed"].items()}


CUT_X = L.PARTITION_X[1] + 0.05               # board view: body and partition cut away in front of the board


def screw_cut(d):
    """Assembly view of the motor screws: the body cut on the YZ plane through both screws, board side kept."""
    return {"01_body__xhalf": d["printed"]["01_body"].intersect(box(100, 100, 600, x=50))}


def board_cutaway(d):
    keep = box(100, 100, 600, x=CUT_X + 50)   # keeps model x > CUT_X: the board side, seen from the bore
    cuts = {n + "__cut": s.intersect(keep) for n, s in d["printed"].items() if not n.startswith("05_")}
    return {n: s for n, s in cuts.items() if s.solids().vals()}


def part_name(name):
    return re.sub(r"__(xhalf|half|cut)$", "", name)


def tools(d):
    """The assembly animation's screwdrivers, tip at the origin, blade along +Z (assembly.py)."""
    return {f"tool_{k}_{part}": shape for k in AS.DRIVERS
            for part, shape in AS.tool_parts(k, AS.blade_length(k, d["params"])).items()}


def scene_items(d):
    items = []
    rotors = transmission(d["params"]["screw_length_mm"])["parts"]
    groups = [("printed", d["printed"]), ("section", section_halves(d)), ("cutaway", board_cutaway(d)),
              ("xsection", screw_cut(d)), ("hardware", d["hardware"]),
              ("board", {n: s for n, (s, m) in d["board"].items()}), ("wire", d["wires"]), ("tool", tools(d))]
    for kind, parts in groups:
        for name, shape in parts.items():
            extra = {}
            if kind == "wire":
                m = d["wire_meta"][name]
                color, mat = m["color"], "wire"
                extra = dict(net=m["net"], wire_id=m["wire_id"], diameter_mm=m["od_mm"], start_pad=m["start_pad"],
                             end=m["end"], length_mm=m["centerline_length_mm"], paths=m["paths"])
                if "knot_u" in m:
                    extra["knot_u"] = m["knot_u"]
            elif kind == "board":
                meta = d["board"][name][1]
                color, mat = look(name, meta)
                extra = {k: v for k, v in meta.items() if k != "colour"}
                extra["board_kind"] = extra.pop("kind")
            else:
                color, mat = look(part_name(name))
                if name == "cable_sleeve":
                    extra = dict(path=d["sleeve_path"], diameter_mm=L.SLEEVE_OD)
                if kind == "tool":
                    k = name.split("_")[1]
                    extra = dict(tool=k, blade_d_mm=AS.DRIVERS[k]["blade_d"],
                                 blade_len_mm=round(AS.blade_length(k, d["params"]), 1))
            if name in rotors:
                extra["geartrain_rotation"] = rotors[name]
            tol, ang = ((0.01, 0.1) if kind == "board" else (0.04, 0.35) if name == "motor_leadscrew_M3"
                        else (0.06, 0.25) if kind == "tool" else (0.03, 0.1))
            items.append(dict(name=name, kind=kind, material=mat, color=[round(c, 4) for c in color],
                              moving=part_name(name) in d["moving"],
                              rotating=name in rotors, **extra, **mesh_data(shape, tol, ang)))
    return items


# ---- export ------------------------------------------------------------------------------------
def orient_for_print(name, shape):
    if name.startswith(FLIP):
        shape = shape.rotate((0, 0, 0), (1, 0, 0), 180)
    bb = shape.val().BoundingBox()
    return shape.translate((-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))


def fit_samples(d):
    b, r = d["printed"]["01_body"], d["printed"]["04_rod"]
    c0 = L.CARRIER_Z0
    return {"08_fit_body_wall": b.intersect(box(40, 40, 18, z=-1.0)),                    # z -10 .. 8
            "09_fit_carrier": r.intersect(box(40, 40, L.CARRIER_LEN + 1.5, z=c0 + (L.CARRIER_LEN + 1.5) / 2))}


def step_name(n):
    return n.replace("MOT+", "MOT_P").replace("MOT-", "MOT_N").replace("J_M+", "J_MP").replace("J_M-", "J_MN")


def write_part(name, shape, step_dir, stl_dir):
    import trimesh
    assert shape.val().isValid() and len(shape.solids().vals()) == 1, name
    step_file = step_dir / f"{name}.step"
    cq.exporters.export(shape, str(step_file))
    solid = cq.importers.importStep(str(step_file)).solids().val()
    assert solid.isValid(), ("STEP round trip", name)
    oriented = orient_for_print(name, cq.Workplane(obj=solid.clean()))
    f = stl_dir / f"{name}.stl"
    cq.exporters.export(oriented, str(f), tolerance=0.02, angularTolerance=0.1)
    mesh = trimesh.load_mesh(f)
    keep = mesh.nondegenerate_faces(height=1e-8)
    removed = len(keep) - int(np.count_nonzero(keep))
    if removed:
        mesh.update_faces(keep)
        mesh.remove_unreferenced_vertices()
        mesh.export(f)
    vol = shape.val().Volume()
    return dict(file=str(f.relative_to(ROOT)), watertight=bool(mesh.is_watertight),
                winding_consistent=bool(mesh.is_winding_consistent),
                components=len(mesh.split(only_watertight=False)), zero_height_facets_removed=removed,
                print_extent_mm=np.round(mesh.extents, 2).tolist(), volume_mm3=round(vol, 1),
                mass_solid_g=round(vol / 1000 * PETG_DENSITY, 2), print_setup=PRINT_SETTINGS[name])


def export(d, out, with_fit_samples):
    v = d["variant"]
    step_dir, stl_dir = out / "step" / f"V6-{v}", out / "stl" / f"V6-{v}"
    for p in (step_dir, stl_dir):
        p.mkdir(parents=True, exist_ok=True)
    report = {name: write_part(name, shape, step_dir, stl_dir) for name, shape in d["printed"].items()}
    if with_fit_samples:
        fd, fs = out / "step" / "fit_samples", out / "stl" / "fit_samples"
        fd.mkdir(parents=True, exist_ok=True)
        fs.mkdir(parents=True, exist_ok=True)
        for name, shape in fit_samples(d).items():
            report[name] = write_part(name, shape, fd, fs)
    export_assembly(d, step_dir)
    return report


def export_assembly(d, step_dir):
    v = d["variant"]
    assy = cq.Assembly(name=f"actuator_V6_{v}_retracted")
    for name, shape in itertools.chain(d["printed"].items(), d["hardware"].items()):
        assy.add(shape, name=step_name(name), color=cq.Color(*look(name)[0]))
    for name, (shape, meta) in d["board"].items():
        assy.add(shape, name=step_name(name), color=cq.Color(*look(name, meta)[0]))
    for name, shape in d["wires"].items():
        assy.add(shape, name=f"wire_{name}_{step_name(d['wire_meta'][name]['net'])}",
                 color=cq.Color(*d["wire_meta"][name]["color"]))
    assy.export(str(step_dir / f"assembly_V6-{v}_retracted.step"))


# ---- validation --------------------------------------------------------------------------------
# Intended overlaps: screw threads cut into their pilot holes, and the nut on the leadscrew.
INTENDED = [("01_body", "M2x8_front_cap_", "M2 thread in the 1.6 mm pilot (front cap screw)"),
            ("01_body", "M2x10_rear_cap_", "M2 thread in the 1.6 mm pilot (rear cap screw, through the clamp)"),
            ("03_rear_cap", "cable_sleeve", "sleeve squeezed 0.4 mm in the clamp groove, ridges bite in"),
            ("06_cable_clamp", "cable_sleeve", "sleeve squeezed 0.4 mm in the clamp groove, ridges bite in"),
            ("motor_gearbox_frame", "M1.6x4_countersunk_", "M1.6 thread in the gearbox's tapped hole (modelled 1.4)"),
            ("05_rod_eye", "M2x10_rod_eye", "M2 thread in the 1.7 mm pilot of the rod eye"),
            ("M3_brass_nut", "motor_leadscrew_M3", "nut on the leadscrew thread")]


def intended(a, b):
    for x, y, why in INTENDED:
        if (a.startswith(x) and b.startswith(y)) or (b.startswith(x) and a.startswith(y)):
            return why
    return None


def overlap(a, b):
    aa, bb = a.val().BoundingBox(), b.val().BoundingBox()
    for ax in "xyz":
        if getattr(aa, ax + "min") >= getattr(bb, ax + "max") - 1e-7 or getattr(bb, ax + "min") >= getattr(aa, ax + "max") - 1e-7:
            return 0.0
    return sum(s.Volume() for s in a.intersect(b).solids().vals())


def dist(a, b):
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    x = BRepExtrema_DistShapeShape(one_shape(a).wrapped, one_shape(b).wrapped)
    x.Perform()
    return x.Value()


def bbox_gap(a, b):
    aa, bb = one_shape(a).BoundingBox(), one_shape(b).BoundingBox()
    return math.sqrt(sum(max(0.0, getattr(aa, ax + "min") - getattr(bb, ax + "max"),
                             getattr(bb, ax + "min") - getattr(aa, ax + "max")) ** 2 for ax in "xyz"))


def tool_access(d):
    """Each screw in assembly order: its driver, swept in from outside along the screw axis, against the
    parts already fitted at that step. Reports any overlap, the nearest parts to the blade, and the
    shortest blade that keeps the handle clear of everything."""
    p = d["params"]
    shapes = dict(d["printed"])
    shapes.update(d["hardware"])
    shapes.update({n: s for n, (s, m) in d["board"].items()})
    shapes.update(d["wires"])
    fitted, out = set(), {}
    for step in AS.plan(p)["steps"]:
        for op in sorted(step["ops"], key=lambda o: o["t0"]):
            names = {n for e in op.get("items", []) + op.get("wires", []) + [op.get("item", "")]
                     for n in shapes if e and AS.matches(e, n)}
            if op["op"] == "sleeve":
                names.add("cable_sleeve")
            if op["op"] == "screw":
                t = AS.DRIVERS[op["tool"]]
                blade_len = AS.blade_length(op["tool"], p)
                env = AS.place(AS.access_envelope(op["tool"], blade_len), op["tip"], op["out"])
                blade = AS.place(AS.access_envelope(op["tool"], blade_len, reach=0.01), op["tip"], op["out"])
                handle = AS.place(cylinder(t["handle_d"] / 2, 400), op["tip"], op["out"])
                others = {n: shapes[n] for n in fitted if n != op["item"]}
                hits = [[n, round(v, 4)] for n, s in sorted(others.items()) if (v := overlap(env, s)) > 0.001]
                near = sorted((dist(blade, s), n) for n, s in others.items() if bbox_gap(blade, s) < 3.0)
                o = cq.Vector(*op["out"])
                reach = 0.0
                for n, s in others.items():
                    if overlap(handle, s) > 0:
                        bb = handle.intersect(s).val().BoundingBox()
                        far = max(cq.Vector(x, y, z).dot(o) for x in (bb.xmin, bb.xmax) for y in (bb.ymin, bb.ymax)
                                  for z in (bb.zmin, bb.zmax))
                        reach = max(reach, far - cq.Vector(*op["tip"]).dot(o))
                out[op["item"]] = dict(step=step["ref"], tool=op["tool"], blade_d_mm=t["blade_d"],
                                       blade_len_mm=round(blade_len, 1), min_blade_len_mm=round(reach, 1),
                                       hits=hits, nearest=[dict(part=n, mm=round(v, 3)) for v, n in near[:5] if v < 3.0])
            fitted |= names
    return out


def validate(d):
    p, pr, hw = d["params"], d["printed"], d["hardware"]
    board = {n: s for n, (s, m) in d["board"].items()}
    wires = d["wires"]
    moving = set(d["moving"])
    statics = {n: s for n, s in itertools.chain(pr.items(), hw.items()) if n not in moving}
    statics.update(board)
    movers = {n: s for n, s in itertools.chain(pr.items(), hw.items()) if n in moving}
    rep = {"units": "mm", "fixed_interferences": [], "intended_contacts": [], "moving_assembly_interferences": [],
           "wire_interferences": [], "wire_wire_interferences": [], "motion": [], "wire_end_contacts": []}

    def skip(a, b):                    # parts of the same bought assembly
        return (a.startswith("motor_") and b.startswith("motor_")) or (a.startswith("PCB_") and b.startswith("PCB_"))
    for (an, a), (bn, b) in itertools.combinations(statics.items(), 2):
        if skip(an, bn):
            continue
        v = overlap(a, b)
        if v <= 0.002:
            continue
        why = intended(an, bn)
        (rep["intended_contacts"].append([an, bn, round(v, 4), why]) if why
         else rep["fixed_interferences"].append([an, bn, round(v, 4)]))
    for (an, a), (bn, b) in itertools.combinations(movers.items(), 2):
        v = overlap(a, b)
        if v <= 0.002:
            continue
        why = intended(an, bn)
        (rep["intended_contacts"].append([an, bn, round(v, 4), why]) if why
         else rep["moving_assembly_interferences"].append([an, bn, round(v, 4)]))
    for wn, ws in wires.items():
        for on, os_ in itertools.chain(statics.items(), movers.items()):
            v = overlap(ws, os_)
            if v > 0.001:
                rep["wire_interferences"].append([wn, on, round(v, 4)])
    for (an, a), (bn, b) in itertools.combinations(wires.items(), 2):
        v = overlap(a, b)
        if v > 0.0005:
            rep["wire_wire_interferences"].append([an, bn, round(v, 4)])
    # wire ends: soldered to the board pad (fillet) and to the motor tab (side by side)
    for wn, m in d["wire_meta"].items():
        g_pad = dist(wires[wn], board[f"PCB_pads_{m['net']}"])
        rec = dict(wire=wn, net=m["net"], pad=m["start_pad"], pad_gap_mm=round(g_pad, 4))
        if "motor terminal" in m["end"]:
            t = "motor_terminal_" + m["end"].split("motor terminal ")[1][0]
            rec.update(terminal=t, terminal_gap_mm=round(dist(wires[wn], hw[t]), 6))
        else:
            # Out sideways through the clamp, then inside the sleeve to its far end and 3 mm beyond:
            # with no wire-sleeve overlap it can only have run in the sleeve's bore.
            wb, sb = wires[wn].val().BoundingBox(), hw["cable_sleeve"].val().BoundingBox()
            rec.update(leaves_through_clamp=bool(wb.xmax > L.BODY_X[1] + 2.0),
                       runs_in_sleeve=bool(overlap(wires[wn], hw["cable_sleeve"]) == 0.0 and wb.zmin < sb.zmin - 1.0),
                       knot_from_pad_mm=m["knot_from_pad_mm"])
        rep["wire_end_contacts"].append(rec)
    rep["board_rests_on_motor_wall_gap_mm"] = round(dist(board["PCB_board"], pr["01_body"]), 4)
    # Cable clamp: the sleeve is squeezed by both halves; the screws keep a full thread in the body.
    tip = min(hw[f"M2x10_rear_cap_{i}"].val().BoundingBox().zmax for i in (1, 2))
    squeeze = {n: v for a, b, v, why in rep["intended_contacts"] for n in (a, b)
               if "cable_sleeve" in (a, b) and n != "cable_sleeve"}
    rep["cable_clamp"] = dict(sleeve_od_mm=L.SLEEVE_OD, groove_height_mm=round(L.SLEEVE_OD - L.CLAMP_SQUEEZE, 2),
                              grip_length_mm=round(L.BODY_X[1] - 0.6 - DS.SLEEVE_X0, 2),
                              squeezed_by=sorted(squeeze), rear_screw_thread_in_body_mm=round(tip - L.BODY_REAR_Z, 2))
    # Carrier key: turned 180 degrees about the axis, the rod would hit the key rib.
    wrong = pr["04_rod"].rotate((0, 0, 0), (0, 0, 1), 180)
    rep["carrier_key_blocks_wrong_way_mm3"] = round(overlap(wrong, pr["01_body"]), 3)
    rep["board_front_end_to_cap_tongue_mm"] = round(dist(board["PCB_board"], pr["02_front_cap"]), 3)
    # The animation's screw table must match the modelled screws: head face, axis and direction
    # (0.05 mm: the bounds come from the viewer tessellation once the shapes are meshed).
    for n, sc in AS.screws(p).items():
        bb = hw[n].val().BoundingBox()
        lo, hi = (bb.xmin, bb.ymin, bb.zmin), (bb.xmax, bb.ymax, bb.zmax)
        k = [i for i in range(3) if sc["out"][i]][0]
        face = hi[k] if sc["out"][k] > 0 else lo[k]
        axis = [(lo[i] + hi[i]) / 2 for i in range(3) if i != k]
        assert abs(face - sc["tip"][k]) < 0.05 and all(abs(a - b) < 0.05 for a, b in
                                                         zip(axis, [sc["tip"][i] for i in range(3) if i != k])), n
    rep["tool_access"] = tool_access(d)
    everything = dict(statics)
    everything.update(wires)
    travels = [-L.OVERTRAVEL] + [float(t) for t in np.linspace(0, p["stroke_mm"], 7)] + [p["stroke_mm"] + L.OVERTRAVEL]
    for t in travels:
        hits, gaps = [], {}
        for mn, ms in movers.items():
            mt = ms.translate((0, 0, t))
            for sn, ss in everything.items():
                if intended(mn, sn):
                    continue
                v = overlap(mt, ss)
                if v > 0.002:
                    hits.append([mn, sn, round(v, 4)])
        rep["motion"].append(dict(travel_mm=round(t, 2), interferences=hits))
    # running clearance between the moving carrier/magnet and the board parts
    near = {n: s for n, s in board.items() if d["board"][n][1]["kind"] in ("part", "part_leads")}
    rep["carrier_to_board_parts_min_gap_mm"] = round(min(dist(movers[m], s) for m in ("04_rod", "magnet_D3x2_axial")
                                                         for s in near.values()), 3)
    # The partition must be solid over the entire circuit cavity, including behind the Halls.
    px0, px1 = L.PARTITION_X
    z0, z1 = L.WALL_Z[1], p["body_z"][1]
    wall = box(px1 - px0, 2 * L.OPEN_Y, z1 - z0, x=(px0 + px1) / 2, z=(z0 + z1) / 2)
    expected = wall.val().Volume()
    actual = sum(s.Volume() for s in pr["01_body"].intersect(wall).solids().vals())
    assert abs(actual - expected) < 1e-5, "partition has a hole or is thinner than specified"
    assert max(meta["height_mm"] for _, meta in d["board"].values() if meta.get("kind") == "part") <= L.PART_MAX_H
    # A conservative rectangular envelope covers every carrier position, continuously.
    travel_lo, travel_hi = -L.OVERTRAVEL, p["stroke_mm"] + L.OVERTRAVEL
    carrier_lo = L.CARRIER_Z0 + travel_lo
    carrier_hi = L.CARRIER_Z0 + L.CARRIER_LEN + travel_hi
    envelope = box(2 * L.CARRIER_X, 2 * L.CARRIER_Y, carrier_hi - carrier_lo,
                   z=(carrier_lo + carrier_hi) / 2)
    board_play = L.PCB_X_INNER - L.SLOT_X[0]
    component_gap = min(dist(wall, s) for s in near.values())
    rep["partition"] = dict(thickness_mm=L.PARTITION_T, z_mm=[z0, z1],
                            continuous=True, volume_mm3=round(actual, 3),
                            component_gap_mm=round(component_gap, 3),
                            component_gap_with_board_play_mm=round(component_gap - board_play, 3),
                            carrier_envelope_gap_mm=round(dist(envelope, wall), 3),
                            carrier_envelope_to_components_mm=round(min(dist(envelope, s) for s in near.values()), 3),
                            note="Nominal full-stroke envelope; the printed partition is a sliding guide, not a load-bearing PCB support. Print error and flex require physical checks.")
    assert component_gap - board_play >= 0.24, "component cavity has inadequate board-placement clearance"
    assert dist(envelope, wall) >= 0.149, "partition reduces the existing carrier guide clearance"
    rep["all_checks_pass"] = (not rep["fixed_interferences"] and not rep["moving_assembly_interferences"]
                              and not rep["wire_interferences"] and not rep["wire_wire_interferences"]
                              and all(not m["interferences"] for m in rep["motion"])
                              and all(c["pad_gap_mm"] <= 0.15 for c in rep["wire_end_contacts"])
                              and all(c.get("terminal_gap_mm", 0) < 1e-3 for c in rep["wire_end_contacts"])
                              and all(c.get("leaves_through_clamp", True) and c.get("runs_in_sleeve", True)
                                      for c in rep["wire_end_contacts"])
                              and len(rep["cable_clamp"]["squeezed_by"]) == 2
                              and rep["cable_clamp"]["rear_screw_thread_in_body_mm"] >= 5.0
                              and rep["carrier_key_blocks_wrong_way_mm3"] > 1.0
                              and rep["board_rests_on_motor_wall_gap_mm"] < 1e-4
                              and rep["carrier_to_board_parts_min_gap_mm"] >= 0.2
                              and all(not a["hits"] and a["min_blade_len_mm"] <= a["blade_len_mm"]
                                      for a in rep["tool_access"].values()))
    return rep


# ---- parameters ------------------------------------------------------------------------------
def mechanics(sim):
    """Hand estimates from the simulation's motor model (see the README for the assumptions)."""
    m = sim["assumptions"]["motor"]
    pitch, ratio = m["pitch"], m["ratio"]
    eta_gear, eta_screw, i0 = 0.55, 0.25, 0.04            # gearbox, M3 steel screw in brass, no-load current
    torque_out = lambda i: max(0.0, i - i0) * m["k"] * ratio * eta_gear
    thrust = lambda i: 2 * math.pi * torque_out(i) * eta_screw / (pitch / 1000)
    stall_a = sim["scenarios"]["jam_mid_stroke"]["measured"]["i_stall"]
    ptc = sim["assumptions"]["ptc"]
    return dict(screw_pitch_mm=pitch, gear_ratio_assumed=ratio, eta_gearbox_assumed=eta_gear,
                eta_leadscrew_assumed=eta_screw, self_locking=eta_screw < 0.5,
                speed_no_load_mm_s=round(150 * pitch / 60, 3),
                speed_simulated_mm_s=sim["scenarios"]["mid_speed"]["speed_mm_s"],
                thrust_at_fuse_hold_N=round(thrust(ptc["hold_A"]), 0),
                thrust_at_stall_N=round(thrust(stall_a), 0),
                note="Estimates. Stall thrust lasts only until F1 trips (about 1.6 s in the simulation).")


def buckling(d):
    """Euler load of the rod at full extension, pinned at the eye and at the front-cap guide."""
    e_petg = 1800.0                                         # N/mm2, printed PETG along the layers
    i_rod = math.pi / 64 * (L.ROD_D ** 4 - L.ROD_BORE ** 4)
    free = d["eye_front_z"] + d["stroke_mm"] - d["front_cap_z"][1]
    return dict(rod_free_length_extended_mm=round(free, 1),
                euler_pinned_pinned_N=round(math.pi ** 2 * e_petg * i_rod / free ** 2, 0), e_assumed_MPa=e_petg)


def parameters(d, trig, sim):
    p = dict(d["params"])
    p.update(stroke_mm=d["params"]["stroke_mm"], overtravel_mm=L.OVERTRAVEL,
             mechanical_stop_retract_mm=-L.OVERTRAVEL, mechanical_stop_extend_mm=p["stroke_mm"] + L.OVERTRAVEL,
             hall_operate_mm=trig["nominal_operate_offset_mm"]["typ"],
             hall_release_mm=trig["nominal_release_offset_mm"]["typ"], hall_lead_mm=L.HALL_LEAD,
             stop_spread_mm=[trig["stop_position_spread_mm"]["earliest"], trig["stop_position_spread_mm"]["latest"]],
             rod_d_mm=L.ROD_D, pin_d_mm=3.0, wire_od_mm=L.WIRE_OD, board_t_mm=L.PCB_T,
             supply="2 wires: A+ / B- extends, B+ / A- retracts; 6 V nominal, 7 V max",
             buckling=buckling(p), mechanics=mechanics(sim),
             geartrain=transmission(p["screw_length_mm"]))
    return p


def run():
    global ROOT
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="all", help="S, U60, L, a --custom name, or all (default)")
    ap.add_argument("--custom", action="append", default=[], metavar="NAME=SCREW:STROKE",
                    help="another stock leadscrew length and nominal stroke in mm, e.g. X80=80:65")
    ap.add_argument("--root", type=Path, default=HOME, help="package folder for the outputs")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--motor-only", action="store_true",
                    help="replace only motor scene items and STEP assemblies; validate the assembled actuator")
    a = ap.parse_args()
    if a.motor_only and a.preview:
        ap.error("--motor-only already updates both preview geometry and STEP assemblies")
    custom = []
    for c in a.custom:
        name, lengths = c.split("=")
        screw, stroke = (float(x) for x in lengths.split(":"))
        L.VARIANTS[name] = dict(screw_length=screw, stroke=stroke)
        custom.append(name)
    variants = (custom or list(L.VARIANTS)) if a.variant == "all" else [a.variant]
    assert set(variants) <= set(L.VARIANTS), f"unknown variant {a.variant}; add it with --custom NAME=SCREW:STROKE"
    ROOT = BD.ROOT = a.root.resolve()                # board.py keeps its route cache with the outputs
    (ROOT / "source").mkdir(parents=True, exist_ok=True)
    trig = json.loads((HOME / "magnet_trigger.json").read_text())
    sim = json.loads((HOME / "electronics" / "simulation" / "results.json").read_text())
    pfile, vfile = ROOT / "parameters.json", ROOT / "validation.json"
    allp = json.loads(pfile.read_text()) if pfile.exists() else {}
    allv = json.loads(vfile.read_text()) if vfile.exists() else {}
    for v in variants:
        t0 = time.time()
        d = make_design(v)
        items = scene_items(d)
        if a.motor_only:
            with gzip.open(ROOT / "source" / f"scene_{v}.json.gz", "rt") as f:
                previous = json.load(f)
            items = ([it for it in previous if not it["name"].startswith("motor_")]
                     + [it for it in items if it["name"].startswith("motor_")])
        with gzip.open(ROOT / "source" / f"scene_{v}.json.gz", "wt") as f:
            json.dump(items, f, separators=(",", ":"))
        allp[v] = {**allp.get(v, {}), **parameters(d, trig, sim)}     # keeps keys added by other builders
        rows = ["variant,wire_id,net,colour,insulation_od_mm,model_centerline_mm,cut_length_mm,from,to"]
        for n, m in d["wire_meta"].items():
            cable = "motor terminal" not in m["end"]
            cut = (f"{m['inside_to_clamp_mouth_mm'] + 8 + 5:.0f} + your lead (knot {m['knot_from_pad_mm']:.0f} mm from the pad)"
                   if cable else round(m["centerline_length_mm"] + 8, 0))          # 8 mm to strip and solder, 5 for the knot
            rows.append(f"{v},{m['wire_id']},{m['net']},{ {'W1': 'red', 'W2': 'black', 'W3': 'orange', 'W4': 'purple'}[n] },"
                        f"{m['od_mm']},{m['centerline_length_mm']},{cut},board pad {m['start_pad']},\"{m['end']}\"")
        if not a.motor_only:
            (ROOT / f"wire_lengths_{v}.csv").write_text("\n".join(rows) + "\n")
        print(v, "meshes", len(items), sum(len(i["triangles"]) for i in items), "triangles", round(time.time() - t0, 1), "s")
        if a.preview:
            continue
        if a.motor_only:
            export_assembly(d, ROOT / "step" / f"V6-{v}")
            parts = allv[v]["parts"]
        else:
            parts = export(d, ROOT, with_fit_samples=(v == "S"))
        print(v, "export", round(time.time() - t0, 1), "s")
        rep = validate(d)
        rep["parts"] = parts
        rep["all_meshes_pass"] = all(x["watertight"] and x["winding_consistent"] and x["components"] == 1
                                     for x in parts.values())
        rep["all_checks_pass"] = rep["all_checks_pass"] and rep["all_meshes_pass"]
        allv[v] = rep
        summary = {k: x for k, x in rep.items() if k not in ("parts", "motion", "wire_end_contacts", "intended_contacts")}
        print(json.dumps(summary, indent=1))
        print("motion hits:", [m for m in rep["motion"] if m["interferences"]])
        print("wire ends:", rep["wire_end_contacts"])
        print(v, "total", round(time.time() - t0, 1), "s")
    known = list(L.VARIANTS)
    in_order = lambda dct: {k: dct[k] for k in sorted(dct, key=lambda k: known.index(k) if k in known else len(known))}
    pfile.write_text(json.dumps(in_order(allp), indent=2))
    if not a.preview:
        allv = in_order(allv)
        vfile.write_text(json.dumps(allv, indent=2))
        if len(allv) > 1:
            first, *rest = allv
            same = {n: all(allv[v]["parts"][n]["volume_mm3"] == allv[first]["parts"][n]["volume_mm3"]
                           and allv[v]["parts"][n]["print_extent_mm"] == allv[first]["parts"][n]["print_extent_mm"]
                           for v in rest)
                    for n in ("02_front_cap", "03_rear_cap", "05_rod_eye", "06_cable_clamp")}
            print("shared parts identical in", " · ".join(allv), same)
            assert all(same.values())
        assert all(allv[v]["all_checks_pass"] for v in variants), "Resolve the reported problems."


if __name__ == "__main__":
    run()

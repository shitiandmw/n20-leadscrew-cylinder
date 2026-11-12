"""Assembly sequence: the order the parts go in, the screwdrivers that drive the screws, and the camera
for each step. One source for the tool-access check (build_v6.py validate) and the assembly animation in
3D_preview.html (build_viewer.py).

Units mm, model frame of layout.py. Every offset is measured from the part's assembled position at
travel 0. Ops, in step time (seconds):
  show   items appear in place                         move   items slide from `from` to `to`
  feed   the board slides in, its wires lead the way   wire   wires take a new path state
  knot   knots appear on the cable wires               sleeve the sleeve slides up the wires
  screw  a driver carries the screw in and turns it     drive  the leadscrew turns and moves the rod
         (the soldering iron presses each heat-set insert in the same way; iron and insert are round, so
          their turn does not show)
Items name scene parts; a name ending in "_" covers every part that starts with it.
"""
import math
import re
import cadquery as cq
import layout as L
import design_v6 as DS

# Cross-recess sizes after DIN 965 / DIN 7985: M1.6 takes PH0, M2 takes PH1; M1 micro screws take PH000.
# IRON is the soldering iron that presses the heat-set inserts (fine conical tip, round grip).
DRIVERS = {
    "PH0": dict(tip_d=1.8, blade_d=3.0, tip_len=2.5, handle_d=18.0, handle_len=80.0,
                note="PH0 screwdriver with a 3 mm round blade, e.g. Wera 350 PH 0 × 100 mm (item 05008706001)"),
    "PH1": dict(tip_d=2.5, blade_d=4.5, tip_len=3.5, handle_d=26.0, handle_len=95.0, blade_len=80.0,
                note="PH1 screwdriver, 4.5 mm blade, 80 mm"),
    "PH000": dict(tip_d=0.8, blade_d=2.5, tip_len=2.0, handle_d=13.0, handle_len=75.0, blade_len=40.0,
                  note="PH000 precision screwdriver, 2.5 mm blade, 40 mm"),
    "IRON": dict(tip_d=0.8, blade_d=4.0, tip_len=6.0, handle_d=12.0, handle_len=100.0, blade_len=45.0,
                 note="Soldering iron with a fine conical tip, about 240 °C for PETG"),
}
FERRULE = 8.0            # cone from the blade to the handle
SCREW_TIMES = (0.36, 0.80)   # approach until 36 % of the op, turn until 80 %, then the driver backs out


def blade_length(kind, d):
    """The PH0 reaches the motor screws through the bore from the body's front face, 13 mm to spare."""
    if kind == "PH0":
        return d["body_z"][1] - L.WALL_Z[1] + 13.0
    return DRIVERS[kind]["blade_len"]


def tool_parts(kind, blade_len):
    """Screwdriver with its tip at the origin and its blade along +Z: {"blade": ..., "handle": ...}."""
    t = DRIVERS[kind]
    rb = t["blade_d"] / 2
    blade = cq.Workplane(obj=cq.Solid.makeCone(t["tip_d"] / 2, rb, t["tip_len"]))
    blade = blade.union(cq.Workplane("XY").circle(rb).extrude(blade_len - t["tip_len"] + 1.0)
                        .translate((0, 0, t["tip_len"])))
    z0 = blade_len
    ferrule = cq.Workplane(obj=cq.Solid.makeCone(rb + 0.8, t["handle_d"] * 0.36, FERRULE, cq.Vector(0, 0, z0)))
    if kind == "IRON":                   # round grip
        grip = (cq.Workplane("XY").circle(t["handle_d"] / 2).extrude(t["handle_len"])
                .faces(">Z").edges().fillet(t["handle_d"] * 0.2).translate((0, 0, z0 + FERRULE)))
    else:                                # screwdriver: hexagonal grip
        grip = (cq.Workplane("XY").polygon(6, t["handle_d"]).extrude(t["handle_len"])
                .edges("|Z").fillet(t["handle_d"] * 0.13).faces(">Z").edges().fillet(t["handle_d"] * 0.12)
                .translate((0, 0, z0 + FERRULE)))
    return {"blade": blade, "handle": ferrule.union(grip)}


def access_envelope(kind, blade_len, reach=300.0):
    """What the driver sweeps on its way in: tip, blade, then the handle's full circle out to `reach`."""
    t = DRIVERS[kind]
    s = cq.Workplane(obj=cq.Solid.makeCone(t["tip_d"] / 2, t["blade_d"] / 2, t["tip_len"]))
    s = s.union(cq.Workplane("XY").circle(t["blade_d"] / 2).extrude(blade_len - t["tip_len"] + 0.01)
                .translate((0, 0, t["tip_len"])))
    return s.union(cq.Workplane("XY").circle(t["handle_d"] / 2).extrude(reach).translate((0, 0, blade_len)))


def place(shape, tip, out):
    """Move a +Z tool so that its tip sits at `tip` and its blade points along `out`."""
    o = cq.Vector(*out).normalized()
    z = cq.Vector(0, 0, 1)
    if (o - z).Length < 1e-9:
        s = shape
    elif (o + z).Length < 1e-9:
        s = shape.rotate((0, 0, 0), (1, 0, 0), 180)
    else:
        ax = z.cross(o)
        s = shape.rotate((0, 0, 0), ax.toTuple(), math.degrees(math.acos(max(-1, min(1, z.dot(o))))))
    return s.translate(tuple(tip))


def screws(d):
    """Each screw's head centre (where the driver tip sits), the direction out of the head, and how far
    it threads in; for the heat-set inserts, the centre of the outer end (where the iron's tip sits) and how
    far the iron presses them in. Mirrors design_v6.make_hardware; validate() checks the two agree."""
    out = {}
    for i, (x, y) in enumerate(L.MOTOR_SCREWS, start=1):
        out[f"M1.6x4_countersunk_{i}"] = dict(tool="PH0", tip=(x, y, L.WALL_Z[1]), out=(0, 0, 1),
                                               thread=round(L.WALL_Z[0] - (L.WALL_Z[1] - 4.0), 3), pitch=0.35)
    I, S = L.INSERT, L.CAP_SCREW
    press = round(I["length"] + I["recess"], 3)                         # how far the iron pushes each insert
    head_rear = DS.CLAMP_Z - L.CLAMP_T + S["pocket_depth"] - S["head_h"]   # outer face of a rear head
    head_front = d["front_cap_z"][1] - S["pocket_depth"] + S["head_h"]     # top face of a front head
    for i, (x, y) in enumerate(L.REAR_INSERTS, start=1):
        out[f"M1_insert_rear_{i}"] = dict(tool="IRON", tip=(x, y, L.BODY_REAR_Z + I["recess"]), out=(0, 0, -1),
                                          thread=press, pitch=press / 2)
        out[f"M1x8_rear_cap_{i}"] = dict(tool="PH000", tip=(x, y, head_rear), out=(0, 0, -1),
                                         thread=round(head_rear + S["head_h"] + S["length"] - L.BODY_REAR_Z, 3),
                                         pitch=0.25)
    for i, (x, y) in enumerate(L.FRONT_INSERTS, start=1):
        out[f"M1_insert_front_{i}"] = dict(tool="IRON", tip=(x, y, d["body_z"][1] - I["recess"]), out=(0, 0, 1),
                                           thread=press, pitch=press / 2)
        out[f"M1x8_front_cap_{i}"] = dict(tool="PH000", tip=(x, y, head_front), out=(0, 0, 1),
                                          thread=round(d["body_z"][1] - (head_front - S["head_h"] - S["length"]), 3),
                                          pitch=0.25)
    out["M2x10_rod_eye"] = dict(tool="PH1", tip=(round(4.6 + 1.6, 3), 0.0, d["rod_end_z"] - 4.5), out=(1, 0, 0),
                                thread=round(-(L.ROD_D / 2 + 0.05) - (4.6 - 10.0), 3), pitch=0.4)
    return out


def matches(entry, name):
    base = re.sub(r"__(xhalf|half|cut)$", "", name)
    return base == entry or (entry.endswith("_") and base.startswith(entry))


def plan(d, access=None):
    """The animation and the tool-access check, step by step. `access` (validation results) fills the
    clearance numbers into the captions."""
    zr, zf = d["body_z"]
    mid = (zr + zf) / 2
    sl = d["screw_length_mm"]
    sc = screws(d)
    ph0 = blade_length("PH0", d)
    motor_back = sl - zr + 12.0                          # motor starts with its leadscrew behind the body
    feed = zf - d["pcb_z"][0] + 18.0                     # board starts 18 mm in front of the body
    bench = zf + 22.0 - L.CARRIER_Z0                     # rod waits in front of the body for the nut and magnet
    nut_rear = L.CARRIER_Z0 + L.NUT_SLOT_DZ[0] + 0.05
    touch = round(sl - nut_rear, 3)                      # rod offset where the nut meets the screw tip
    rod = ["04_rod", "M4_brass_nut", L.MAGNET_NAME]
    sh = L.REAR_HOOK["shift"]                            # the rear cap goes on this far toward +X, then slides back
    hp = L.rear_hook_profile()
    hook = (hp["xi"] - 0.4, 0, hp["zr"] - 0.6)          # camera on the tooth and the notch
    eye = ["05_rod_eye", "M2x10_rod_eye"]

    def near(screw, part):
        a = (access or {}).get(screw) or {}
        return next((x["mm"] for x in a.get("nearest", []) if x["part"].startswith(part)), None)

    def screw(name, t0, t1):
        return dict(op="screw", item=name, t0=t0, t1=t1, approach=round(approach[name], 1), **sc[name])

    def cam(t, target, direction, span):
        return [t, [round(c, 2) for c in target], list(direction), round(span, 1)]

    # Looking onto a cut, the camera stays square to the axis so the body lies level, front to the right.
    top = (-0.25, 0.97, 0.0)             # onto the pin-plane cut (look "half")
    side = (-1.0, 0.3, 0.0)              # onto the screw-plane cut (look "xhalf"), from the side away from the board

    approach = {}
    for n, s in sc.items():                              # driver tip starts this far out of the part
        approach[n] = {"PH0": zf - L.WALL_Z[1] + 14.0}.get(s["tool"], 26.0)
    m16 = sc["M1.6x4_countersunk_1"]
    handle_end = (m16["tip"][2] + m16["thread"] + approach["M1.6x4_countersunk_1"] + ph0 + FERRULE
                  + DRIVERS["PH0"]["handle_len"])                # driver at the start of its way down
    wall, lead = near("M1.6x4_countersunk_1", "01_body"), near("M1.6x4_countersunk_1", "motor_leadscrew")
    gap_txt = (f" The 3 mm blade passes {wall:.2f} mm from the bore wall and {lead:.1f} mm from the leadscrew."
               if wall is not None and lead is not None else "")
    steps = [
        dict(id="body", ref="2", title="Printed body", look="solid", dur=3.0,
             text="01 body, printed standing on its front end. Everything goes into it in the order shown.",
             ops=[dict(op="show", items=["01_body"], t0=0.0)],
             cams=[cam(0.0, (1, 0, mid), (-0.55, 0.5, 0.42), zf - zr + 60)]),
        dict(id="inserts", ref="3", title="Heat-set inserts", look="solid", dur=17.5,
             text="Press the four M1 heat-set inserts (1.8 mm long, 2 mm across) into the holes in the end faces "
                  "with the soldering iron at about 240 °C, your PETG print temperature + 10 °C: two in the rear face, "
                  "two in the front face. Let each one sink in straight under light pressure until it sits 0.1 mm "
                  "below the face. The front ones have 0.7 mm of wall: go slowly there.",
             ops=[screw("M1_insert_rear_1", 0.5, 4.1), screw("M1_insert_rear_2", 4.4, 8.0),
                  screw("M1_insert_front_1", 9.0, 12.6), screw("M1_insert_front_2", 12.9, 16.5)],
             cams=[cam(1.0, (7, 0, zr - 10), (0.55, 0.45, -0.7), 64), cam(8.2, (7, 0, zr - 10), (0.55, 0.45, -0.7), 64),
                   cam(9.0, (7, 0, zf + 10), (0.55, 0.45, 0.7), 64), cam(16.5, (7, 0, zf + 10), (0.55, 0.45, 0.7), 64)]),
        dict(id="board", ref="4–5", title="Board and wires", look="ghost", dur=7.5,
             text="Thread the four wires into the board slot from the front, through the passage in the motor "
                  "wall and out at the rear. Slide the board in after them, parts facing the partition, until "
                  "it rests on the motor wall.",
             ops=[dict(op="feed", items=["PCB_"], wires=["W1", "W2", "W3", "W4"], **{"from": [0, 0, round(feed, 2)]},
                       t0=0.8, t1=6.8)],
             cams=[cam(1.0, (4, 0, mid + feed * 0.4), (-0.72, 0.5, 0.3), zf - zr + feed + 40)]),
        dict(id="motor", ref="6.1", title="Motor", look="half", dur=5.5,
             text=(f"Cut the M4 leadscrew to {d['screw_length_mm']:g} mm from the gearbox face (it is sold 100 mm long). "
                   if d["screw_length_mm"] < 100 else "The M4 leadscrew stays at its full 100 mm. ")
                  + "Push the N20 into the motor bay from the rear, gearbox first. The leadscrew passes through the "
                  "hole in the motor wall into the empty bore.",
             ops=[dict(op="move", items=["motor_"], **{"from": [0, 0, -round(motor_back, 2)]}, t0=0.6, t1=4.8)],
             cams=[cam(1.0, (0, 0, (zf - 26.5 - motor_back) / 2), top, zf + 26.5 + motor_back + 16)]),
        dict(id="motor_screws", ref="6.2", title="Motor screws, through the empty bore", look="xhalf", dur=12.0,
             text=f"Carry each M1.6 × 4 countersunk screw down the bore on a PH0 driver ({ph0:.0f} mm blade or "
                  f"longer, 3 mm thick or less) and drive it through the wall into the gearbox, beside the "
                  f"leadscrew. The rod is not in yet, so the bore is clear.{gap_txt}",
             ops=[screw("M1.6x4_countersunk_1", 0.7, 5.9), screw("M1.6x4_countersunk_2", 6.3, 11.5)],
             cams=[cam(1.0, (0, 0, (zr + handle_end) / 2), side, handle_end - zr + 16),
                   cam(2.1, (0, 0, (zr + handle_end) / 2), side, handle_end - zr + 16),
                   cam(3.0, (0, -2.5, 11), side, 56),
                   cam(10.7, (0, -2.5, 11), side, 56),
                   cam(11.9, (0, 0, mid + 8), side, zf - zr + 40)]),
        dict(id="motor_wires", ref="6.3", title="Motor wires", look="half", dur=4.5,
             text="Lead W3 (orange) and W4 (purple) around the back of the can and solder them to the motor "
                  "terminals.",
             ops=[dict(op="wire", wires=["W3", "W4"], to="final", t0=0.6, t1=3.6)],
             cams=[cam(1.0, (2, 0, -16), top, 60)]),
        dict(id="rear_cap", ref="7.1–7.2", title="Knots and rear cap", look="half", dur=9.5,
             text="Tie an overhand knot in W1 and W2, 31 mm from the board. Pass both wires through the slot in "
                  f"the rear cap. Set the cap on the rear face {sh:g} mm toward the board side, so that the end of "
                  "the motor-side wall goes into the pocket in the cap, then slide it back: its tooth drops into "
                  "the notch inside the wall and the screw holes line up. The knots stay inside: they cannot pass "
                  "the slot.",
             ops=[dict(op="wire", wires=["W1", "W2"], to="slot_fit", t0=0.5, t1=2.0),
                  dict(op="knot", wires=["W1", "W2"], t0=2.2),
                  dict(op="move", items=["03_rear_cap"], **{"from": [sh, 0, -40], "to": [sh, 0, 0]}, t0=3.0, t1=6.0),
                  dict(op="move", items=["03_rear_cap"], **{"from": [sh, 0, 0]}, t0=7.0, t1=8.6),
                  dict(op="wire", wires=["W1", "W2"], to="slot", t0=7.0, t1=8.6)],
             cams=[cam(1.0, (4, 0, -44), top, 84), cam(5.6, (4, 0, -40), top, 70),
                   cam(6.8, hook, top, 16), cam(9.2, hook, top, 16)]),
        dict(id="sleeve_clamp", ref="7.3–7.4", title="Sleeve and cable clamp", look="solid", dur=7.0,
             text="Lay both wires out sideways along the groove and slide the 3 mm sleeve over them up to the "
                  "slot. Lay the cable clamp in its pocket over the sleeve, ridges toward it.",
             ops=[dict(op="wire", wires=["W1", "W2"], to="final", t0=0.4, t1=2.0),
                  dict(op="sleeve", **{"from": 30.0}, t0=2.2, t1=4.6),
                  dict(op="move", items=["06_cable_clamp"], **{"from": [0, 0, -16]}, t0=4.9, t1=6.6)],
             cams=[cam(1.0, (7, 0, -38), (0.55, 0.45, -0.7), 64)]),
        dict(id="rear_screws", ref="7.5", title="Rear screws", look="solid", dur=11.0,
             text="Fit 2 × M1 × 8 with the PH000 driver through the clamp and the cap into the rear inserts. Tighten "
                  "until the clamp sits flat, and no further: the sleeve is squeezed by 0.4 mm and the cable cannot "
                  "pull out. The screws also keep the cap from sliding back toward the board side, which would free "
                  "its tooth.",
             ops=[screw("M1x8_rear_cap_1", 0.6, 5.4), screw("M1x8_rear_cap_2", 5.8, 10.6)],
             cams=[cam(1.0, (7, 0, -50), (0.62, 0.5, -0.6), 100)]),
        dict(id="magnet_nut", ref="8.1–8.2", title="Magnet and nut", look="solid", dur=6.0,
             text=f"Press the {L.magnet_label()} block magnet into the pocket in the side of the carrier, and slide "
                  "the thin brass M4 nut into the hex slot.",
             ops=[dict(op="move", items=rod[:1], **{"from": [0, 0, round(bench + 40, 2)], "to": [0, 0, round(bench, 2)]},
                       t0=0.2, t1=1.4),
                  dict(op="move", items=[L.MAGNET_NAME], **{"from": [16, 0, round(bench, 2)],
                                                                  "to": [0, 0, round(bench, 2)]}, t0=1.7, t1=3.2),
                  dict(op="move", items=["M4_brass_nut"], **{"from": [-18, 0, round(bench, 2)],
                                                             "to": [0, 0, round(bench, 2)]}, t0=3.6, t1=5.2)],
             cams=[cam(1.0, (0, 0, L.CARRIER_Z0 + bench + 6), (0.75, 0.55, 0.3), 48),     # magnet: board side
                   cam(3.3, (0, 0, L.CARRIER_Z0 + bench + 6), (0.75, 0.55, 0.3), 48),
                   cam(4.1, (0, 0, L.CARRIER_Z0 + bench + 6), (-0.75, 0.55, 0.3), 48)]),   # nut: the far side
        dict(id="rod", ref="8.3–8.4", title="Rod", look="half", dur=8.5,
             text="Slide the rod into the bore, magnet toward the board: the key rib in one corner only lets it in "
                  "that way. When the nut touches the leadscrew, apply B+ for a moment: the nut picks up the thread "
                  "and the carrier pulls itself in until U1 stops it at the retract end.",
             ops=[dict(op="move", items=rod, **{"from": [0, 0, round(bench, 2)], "to": [0, 0, touch]}, t0=0.5, t1=3.4),
                  dict(op="drive", items=rod, **{"from": touch, "to": 0.0}, t0=4.0, t1=8.0)],
             cams=[cam(1.0, (0, 0, (zr + zf + touch) / 2 + 10), top, zf - zr + touch + 50)]),
        dict(id="front_cap", ref="9.1", title="Front cap", look="half", dur=4.5,
             text="Slide the front cap over the rod. Its spigot enters the bore and its tongue holds the board's "
                  "front edge.",
             ops=[dict(op="move", items=["02_front_cap"], **{"from": [0, 0, 32]}, t0=0.5, t1=3.6)],
             cams=[cam(1.0, (2, 0, zf + 10), top, 90)]),
        dict(id="front_screws", ref="9.2", title="Front screws", look="solid", dur=11.0,
             text="Fix the front cap with 2 × M1 × 8 into the front inserts, PH000 driver, snug only.",
             ops=[screw("M1x8_front_cap_1", 0.6, 5.4), screw("M1x8_front_cap_2", 5.8, 10.6)],
             cams=[cam(1.0, (5, 0, zf + 22), (0.5, 0.5, 0.7), 124)]),
        dict(id="rod_eye", ref="9.3", title="Rod eye", look="solid", dur=8.0,
             text="Push the rod eye onto the rod, line up the cross holes and fit the M2 × 10 from the "
                  "counterbored side. It threads into the pilot on the far side.",
             ops=[dict(op="move", items=["05_rod_eye"], **{"from": [0, 0, 26]}, t0=0.4, t1=2.4),
                  screw("M2x10_rod_eye", 2.8, 7.6)],
             cams=[cam(1.0, (6, 0, d["rod_end_z"] - 4), (0.55, 0.45, 0.7), 70)]),
        dict(id="done", ref="10", title="Assembled", look="solid", dur=7.0,
             text="Done. Each end stop switches the motor off by itself, and reversing the polarity always drives "
                  "the rod back.",
             ops=[dict(op="drive", items=rod + eye, **{"from": 0.0, "to": d["stroke_mm"]}, t0=1.0, t1=3.6),
                  dict(op="drive", items=rod + eye, **{"from": d["stroke_mm"], "to": 0.0}, t0=4.0, t1=6.6)],
             cams=[cam(1.0, (0, 0, mid + d["stroke_mm"] / 2), (-0.6, 0.5, 0.55), d["pin_centres_open"] + 50),
                   cam(7.0, (0, 0, mid + d["stroke_mm"] / 2), (-0.32, 0.55, 0.77), d["pin_centres_open"] + 50)]),
    ]
    for s in steps:
        assert all(o["t1"] <= s["dur"] if "t1" in o else o["t0"] < s["dur"] for o in s["ops"]), s["id"]
    tools = {k: dict(blade_d=v["blade_d"], blade_len=round(blade_length(k, d), 1), note=v["note"])
             for k, v in DRIVERS.items()}
    return dict(steps=steps, tools=tools, screw_times=SCREW_TIMES, pitch=0.5)

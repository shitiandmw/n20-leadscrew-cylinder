"""V5: hydraulic-cylinder style housing around the unmodified N20 leadscrew motor.

Units mm. Z is the actuator axis (+Z toward the rod eye), X is the clevis pin
axis, -Y is the service side (sensor channel, cable port). Z=0 is the gearbox
front face of the motor. All Z positions below are for travel 0 (retracted,
Hall trigger point); moving parts are translated by the travel.

Load path: the gearbox front plate seats on a step inside the barrel (pull),
the rear cap backs the can (push). The leadscrew drives an M3 nut held in the
pushrod carrier; the carrier's asymmetric section keys it against rotation.
"""
import math
import cadquery as cq
from cad_utils import (cylinder, box, axial_x, hex_z, hex_x, ring, cy, cx_cone, rr_box)
from n20_screw_motor import n20_core_part, screw_envelope, CAN_REAR, TERMINAL_Y, TERMINAL_HOLE_Z
from wire_geometry import route, sweep, offset_yz_route, tangent, length, min_radius

BARREL_R = 10.5           # Ø21 barrel
CAP_R = 11.5              # Ø23 rear cap and head collar
ROD_R = 4.5               # Ø9 piston rod
EYE_R = 7.0               # Ø14 clevis eyes
EYE_T = 10.4              # eye thickness along the pin, same as V4
PIN_HOLE_R = 1.6          # Ø3.2 for Ø3 pins
POCKET = (5.175, 6.175)   # motor pocket half-size, motor is 10 x 12
CARRIER_BORE = (-4.65, 4.65, -5.65, 4.65)
CARRIER = (-4.5, 4.5, -5.5, 4.5)
CARRIER_LEN = 10.0
CARRIER_Z0 = 2.0          # carrier rear face at travel 0; touches the motor at -2
BARREL_Z0 = -23.0         # motor can protrudes 1 mm into the rear cap
CHANNEL = (-2.6, 2.6, -9.7, -6.95)
CHANNEL_FLOOR = -6.95
SENSOR_Y = CHANNEL_FLOOR - 0.81
LOWER_WIRE_Y = SENSOR_Y
UPPER_WIRE_Y = -9.05
STRIP_INNER_Y = -9.5
PORT_Z = -25.4
JACKET_START_Y = -10.0
REAR_EYE_Z = -35.0
OVERTRAVEL_RETRACT = 2.0
OVERTRAVEL_EXTEND = 3.0
MAGNET_DZ = 7.2           # magnet centre from the carrier rear face
HALL_LEAD = 3.8           # Hall sits this far outboard of the magnet end position; see magnet_trigger.py
NUT_DZ = (1.8, 4.4)       # nut slot from the carrier rear face


def parameters(screw_length=40.0, screw_pitch=0.5):
    nut_front = CARRIER_Z0 + NUT_DZ[1]
    usable = screw_length - 0.5 - nut_front - OVERTRAVEL_EXTEND
    stroke = 5 * math.floor(usable / 5 + 1e-9)
    assert stroke >= 10, "Leadscrew too short for this layout."
    lip = CARRIER_Z0 + stroke + OVERTRAVEL_EXTEND + CARRIER_LEN
    front = lip + 8.0
    socket = front + 6.0           # rod-eye socket rear face, retracted
    rod_end = socket + 8.0
    eye = socket + 14.0
    bore_end = rod_end - 10.0
    return dict(
        version="5.0", screw_length_mm=screw_length, screw_pitch_mm=screw_pitch, screw_thread="M3",
        stroke_mm=stroke, overtravel_retract_mm=OVERTRAVEL_RETRACT, overtravel_extend_mm=OVERTRAVEL_EXTEND,
        mechanical_stop_retract_mm=-OVERTRAVEL_RETRACT, mechanical_stop_extend_mm=stroke + OVERTRAVEL_EXTEND,
        rear_eye_z=REAR_EYE_Z, front_eye_z_retracted=eye,
        eye_centres_closed_mm=round(eye - REAR_EYE_Z, 2), eye_centres_open_mm=round(eye - REAR_EYE_Z + stroke, 2),
        barrel_od_mm=2 * BARREL_R, cap_od_mm=2 * CAP_R, rod_d_mm=2 * ROD_R, eye_od_mm=2 * EYE_R,
        eye_thickness_mm=EYE_T, eye_hole_mm=2 * PIN_HOLE_R,
        barrel_z=[BARREL_Z0, front], lip_z=[lip, front], carrier_z0=CARRIER_Z0, carrier_length_mm=CARRIER_LEN,
        rod_end_z_retracted=rod_end, rod_bore_end_z_retracted=bore_end,
        longest_screw_that_fits_mm=round(bore_end - 0.5 - CARRIER_Z0 + OVERTRAVEL_RETRACT, 1),
        magnet_end_positions_z=[CARRIER_Z0 + MAGNET_DZ, CARRIER_Z0 + MAGNET_DZ + stroke],
        sensor_centres_z=[CARRIER_Z0 + MAGNET_DZ - HALL_LEAD, CARRIER_Z0 + MAGNET_DZ + stroke + HALL_LEAD],
        sensor_axial_adjustment_mm=3,
        magnet_mm=[4, 2], magnet_axis="radial (Y)", sensor_model="DRV5033AJQLPG",
        hall_wires=6, motor_wires=2, total_exit_wires=8, sensor_wire_od_mm=0.4, motor_wire_od_mm=0.7,
        jacket_od_mm=4.0, jacket_id_mm=3.2,
        motor_dimension_chain_mm=dict(shaft_or_screw_from_front_face=screw_length, gearbox=9, can_incl_end_cap=15,
                                      rear_boss=1.2, terminals_beyond_can=2.5),
        wire_routing="Nominal dressed harness; trim after Hall calibration.",
        magnetic_verification=("Biot-Savart model of the magnet (magnet_trigger.py): typical switch-on about "
                               "3.9 mm before alignment, hence HALL_LEAD. Steel screw/nut not modelled; "
                               "no physical trigger test yet - calibrate on the bench."))


def lug(z_base, half_base, zc, r=EYE_R, thick=EYE_T):
    """Clevis lug: hull of a base segment (|y|<=half_base at z_base) and the eye circle."""
    s = 1 if z_base > zc else -1
    pts = {}
    for side in (1, -1):
        by, bz = side * half_base, z_base
        dy, dz = by, bz - zc
        L = math.hypot(dy, dz)
        th = math.atan2(dz, dy)
        a = th - side * s * math.acos(r / L)
        pts[side] = (r * math.cos(a), zc + r * math.sin(a))
    far = (0, zc - s * r)
    wp = (cq.Workplane("YZ").moveTo(-half_base, z_base).lineTo(half_base, z_base)
          .lineTo(*pts[1]).threePointArc(far, pts[-1]).close())
    solid = wp.extrude(thick).translate((-thick / 2, 0, 0))
    try:
        solid = solid.faces(">X or <X").edges().chamfer(0.5)
    except Exception:
        pass
    return solid


def pin_hole(zc):
    return (axial_x(PIN_HOLE_R, 20, -10, 0, zc)
            .union(cx_cone(PIN_HOLE_R + 0.4, PIN_HOLE_R, 0.4, -EYE_T / 2, 0, zc))
            .union(cx_cone(PIN_HOLE_R, PIN_HOLE_R + 0.4, 0.4, EYE_T / 2 - 0.4, 0, zc)))


def dovetail(y_in, half_in, y_out, half_out, z0, z1):
    q = (cq.Workplane("XY").polyline([(-half_in, y_in), (half_in, y_in), (half_out, y_out), (-half_out, y_out)])
         .close().extrude(z1 - z0))
    return q.translate((0, 0, z0))


def make_barrel(p):
    z1 = p["barrel_z"][1]
    lip = p["lip_z"][0]
    b = cylinder(BARREL_R, z1 - BARREL_Z0, BARREL_Z0).edges(">Z or <Z").chamfer(0.4)
    px, py = POCKET
    b = b.cut(rr_box(-px, px, -py, py, BARREL_Z0 - 1, 0, 0.8))
    x0, x1, y0, y1 = CARRIER_BORE
    b = b.cut(rr_box(x0, x1, y0, y1, -0.01, lip, 1.2))
    b = b.cut(cylinder(4.65, z1 - lip + 1, lip - 0.01))
    ch_end = z1 + 1.0
    cx0, cx1, cy0, cy1 = CHANNEL
    b = b.cut(box(cx1 - cx0, cy1 - cy0, ch_end - BARREL_Z0 + 1, y=(cy0 + cy1) / 2, z=(BARREL_Z0 - 1 + ch_end) / 2))
    b = b.cut(dovetail(-9.45, 3.35, -11.2, 2.55, BARREL_Z0 - 1, ch_end))
    for x in (-7.85, 7.85):
        b = b.cut(cylinder(0.85, 6.0, BARREL_Z0 - 0.1).translate((x, 0, 0)))
    return b


def make_cover_strip(p):
    # Slides in from the front through the head collar, after Hall calibration.
    z1 = p["barrel_z"][1] + 1.6
    strip = dovetail(STRIP_INNER_Y, 3.217, -11.2, 2.44, BARREL_Z0 + 1.0, z1)
    strip = strip.intersect(cylinder(BARREL_R, z1 - BARREL_Z0, BARREL_Z0))
    return strip.cut(box(8, 0.5, 0.8, y=-10.6, z=z1 - 1.6))   # nail groove for pulling it out


def make_rear_cap(p):
    body = cylinder(CAP_R, -17.0 - -30.5, -30.5)
    body = body.edges("<Z").fillet(1.5).edges(">Z").chamfer(0.6)
    boss = cy(4.0, 3.0, 0, -13.0, PORT_Z)
    boss = boss.faces("<Y").edges().chamfer(0.5)
    body = body.union(boss)
    body = body.union(lug(-30.0, 8.5, REAR_EYE_Z))
    px, py = POCKET
    cuts = [cylinder(10.6, 6.2, BARREL_Z0),                      # collar over the barrel
            rr_box(-px, px, -py, py, -24.2, BARREL_Z0 + 0.1, 0.8),  # motor seat; face at -24.2
            cylinder(4.6, 3.85, -28.0),                           # boss, terminals, solder joints
            box(5.2, 2.75, 3.2, y=(-9.7 - 6.95) / 2, z=-24.5),     # sensor wires from the channel
            box(2.6, 5.5, 2.8, y=-5.75, z=-26.4),                  # motor wires to the port
            cy(2.2, 4.1, 0, -11.0, PORT_Z),                       # jacket bore
            cy(2.7, 3.3, 0, -13.2, PORT_Z),                       # TPU boot spigot
            pin_hole(REAR_EYE_Z)]
    for x in (-7.85, 7.85):
        cuts.append(cylinder(2.0, 2.7, -30.7).translate((x, 0, 0)))
        cuts.append(cylinder(1.1, 5.1, -28.05).translate((x, 0, 0)))
    for c in cuts:
        body = body.cut(c)
    return body


def make_head_collar(p):
    z1 = p["barrel_z"][1]
    c = cylinder(CAP_R, 7.6, z1 - 6.0).edges("<Z").chamfer(0.5).edges(">Z").chamfer(1.0)
    nose = cylinder(EYE_R, 2.4, z1 + 1.6).edges(">Z").chamfer(0.5)
    c = c.union(nose)
    c = c.cut(cylinder(10.6, 6.1, z1 - 6.1)).cut(cylinder(4.9, 12, z1 - 3))
    c = c.cut(dovetail(-9.4, 3.35, -11.3, 2.55, z1 - 0.1, z1 + 1.7))   # cover-strip slot
    c = c.cut(ring(14.4, 13.3, 0.4, z1 + 2.6))
    c = c.cut(ring(23.4, 22.6, 0.4, z1 - 2.6))
    return c


def make_pushrod(p):
    S = p["stroke_mm"]
    z0 = CARRIER_Z0
    rod_end = p["rod_end_z_retracted"]
    x0, x1, y0, y1 = CARRIER
    carrier = rr_box(x0, x1, y0, y1, z0, z0 + CARRIER_LEN, 1.0).edges(">Z").chamfer(0.4)
    rod = cylinder(ROD_R, rod_end - (z0 + CARRIER_LEN) + 0.01, z0 + CARRIER_LEN - 0.01).edges(">Z").chamfer(0.5)
    r = carrier.union(rod)
    n0, n1 = z0 + NUT_DZ[0], z0 + NUT_DZ[1]
    cuts = [cylinder(2.7, 1.0, z0 - 0.01),                         # clears the gearbox bushing
            cylinder(1.8, n0 - z0, z0),                            # M3 clearance
            hex_z(5.7, n1 - n0, n0, 30),                           # M3 nut, inserted from +Y
            box(5.7, 5.0, n1 - n0, y=2.5, z=(n0 + n1) / 2),
            cy(2.05, 2.15, 0, y0 - 0.05, z0 + MAGNET_DZ),          # Ø4 x 2 magnet, faces the sensors
            cylinder(1.9, p["rod_bore_end_z_retracted"] - n1, n1),  # leadscrew clearance when retracted
            axial_x(1.1, 12, -6, 0, rod_end - 4.0)]                # rod-eye dowel pin
    for c in cuts:
        r = r.cut(c)
    return r


def make_rod_eye(p):
    zs = p["rod_end_z_retracted"] - 8.0
    ze = p["front_eye_z_retracted"]
    sock = cylinder(EYE_R, 9.5, zs).edges("<Z").chamfer(0.5)
    body = sock.union(lug(zs + 9.0, EYE_R, ze))
    slab = (cq.Workplane("XZ").polyline([(-7.5, zs - 1), (7.5, zs - 1), (7.5, zs + 8.4), (EYE_T / 2, zs + 10.2),
                                          (EYE_T / 2, ze + 9), (-EYE_T / 2, ze + 9), (-EYE_T / 2, zs + 10.2),
                                          (-7.5, zs + 8.4)]).close().extrude(10, both=True))
    body = body.intersect(slab)
    # Ø2 x 13.8 steel dowel, press fit in the neck, clearance in the rod; ends sit flush.
    body = body.cut(cylinder(4.6, 8.1, zs - 0.1)).cut(pin_hole(ze)).cut(axial_x(0.98, 20, -10, 0, zs + 4.0))
    return body


def make_boot():
    spigot = cy(2.65, 3.0, 0, -13.0, PORT_Z)
    hexa = hex_z(6.6, 2.0, 0, 0).rotate((0, 0, 0), (1, 0, 0), 90).translate((0, -13.0, PORT_Z))
    taper = (cq.Workplane(obj=cq.Solid.makeCone(2.7, 2.35, 1.6, cq.Vector(0, 0, 0)))
             .rotate((0, 0, 0), (1, 0, 0), 90).translate((0, -15.0, PORT_Z)))
    boot = spigot.union(hexa).union(taper)
    return boot.cut(cy(2.0, 8, 0, -17.0, PORT_Z))


def make_hall(label, zc):
    """DRV5033 LPG with its 4.7k pull-up (1206, pins 1-3) and 100 nF (0603, pins 1-2)."""
    hw, meta = {}, {}
    pins = {1: 1.27, 2: 0.0, 3: -1.27}     # branded face toward +Y, leads toward -Z
    hw[f"Hall_{label}_DRV5033"] = box(4.1, 1.62, 3.25, y=SENSOR_Y, z=zc)
    tip = zc - 1.625 - 4.0
    for pin, fn in ((1, "VCC"), (2, "GND"), (3, "OUT")):
        hw[f"Hall_{label}_pin{pin}_{fn}"] = box(0.43, 0.38, 4.0, x=pins[pin], y=SENSOR_Y, z=tip + 2.0)
    rz, czz = zc - 1.625 - 2.6, zc - 1.625 - 1.0
    ry, cyy = SENSOR_Y + 0.19 + 0.3, SENSOR_Y - 0.19 - 0.4
    hw[f"Hall_{label}_R_4k7"] = box(2.2, 0.6, 1.6, y=ry, z=rz)
    for side in (-1, 1):
        hw[f"Hall_{label}_R_4k7_end_{'L' if side < 0 else 'R'}"] = box(0.5, 0.6, 1.6, x=side * 1.35, y=ry, z=rz)
    hw[f"Hall_{label}_C_100n"] = box(0.9, 0.8, 0.8, x=0.635, y=cyy, z=czz)
    for side in (-1, 1):
        hw[f"Hall_{label}_C_100n_end_{'L' if side < 0 else 'R'}"] = box(0.35, 0.8, 0.8, x=0.635 + side * 0.625,
                                                                         y=cyy, z=czz)
    meta.update({f"Hall_{label}": dict(z_centre=zc, pins={1: "VCC", 2: "GND", 3: "OUT"},
                                       pin_x=pins, lead_tip_z=tip,
                                       pullup="4.7k 1206 across pins 1-3 (under the leads)",
                                       decoupling="100nF 0603 across pins 1-2 (over the leads)")})
    return hw, meta, pins, tip


def make_harness(p, sensor_offsets=(0.0, 0.0)):
    """8 wires + jacket. Returns wires, jacket, metadata."""
    zr, ze = [z + o for z, o in zip(p["sensor_centres_z"], sensor_offsets)]
    pins = {1: 1.27, 2: 0.0, 3: -1.27}
    tips = {"R": zr - 5.625, "E": ze - 5.625}
    cable = route([(0, JACKET_START_Y, PORT_Z), (0, -20.5, PORT_Z), (0, -20.5, PORT_Z - 32.0)], 4.0)
    jacket = sweep(cable, 4.0).cut(sweep(cable, 3.2))
    wires, meta = {}, {}
    upper_x = {1: 0.85, 2: 0.0, 3: -0.85}
    specs = [
        ("W1", "HR_VCC", "+5V (retract Hall)", (1, .12, .08), "R", 1),
        ("W2", "HR_GND", "GND (retract Hall)", (.07, .09, .1), "R", 2),
        ("W3", "HR_OUT", "ALLOW_RET", (.08, .65, .32), "R", 3),
        ("W4", "HE_VCC", "+5V (extend Hall)", (1, .12, .08), "E", 1),
        ("W5", "HE_GND", "GND (extend Hall)", (.07, .09, .1), "E", 2),
        ("W6", "HE_OUT", "ALLOW_EXT", (.12, .38, .94), "E", 3),
    ]
    for wid, name, net, color, which, pin in specs:
        x = pins[pin]
        if which == "R":
            pts = [(x, LOWER_WIRE_Y, tips["R"]), (x, LOWER_WIRE_Y, PORT_Z), (x, JACKET_START_Y, PORT_Z)]
            dx, dn = x, 0.0
        else:
            xu, zt = upper_x[pin], PORT_Z + 0.75
            pts = [(x, LOWER_WIRE_Y, tips["E"]), (x, LOWER_WIRE_Y, zr + 5.3), (x, UPPER_WIRE_Y, zr + 2.6),
                   (x, UPPER_WIRE_Y, -18.0), (xu, UPPER_WIRE_Y, -20.5), (xu, UPPER_WIRE_Y, zt),
                   (xu, JACKET_START_Y, zt)]
            dx, dn = xu, 0.75
        internal = route(pts, 1.2)
        wires[name], meta[name] = _finish(internal, cable, dx, dn, 0.4, wid, net, color,
                                          dict(sensor="retract" if which == "R" else "extend", pin=pin))
    m1 = [(0, -TERMINAL_Y - 0.15, TERMINAL_HOLE_Z), (0, -4.8, TERMINAL_HOLE_Z), (-0.55, -7.0, PORT_Z - 0.75),
          (-0.55, JACKET_START_Y, PORT_Z - 0.75)]
    m2 = [(0, TERMINAL_Y - 0.15 - 0.35, TERMINAL_HOLE_Z), (0, TERMINAL_Y - 0.5, -27.2), (0, -3.0, -27.2),
          (0.55, -7.0, PORT_Z - 0.75), (0.55, JACKET_START_Y, PORT_Z - 0.75)]
    for wid, name, net, color, pts, dx, term in (("W7", "M1", "MOTOR_A", (1, .42, .06), m1, -0.55, 1),
                                                 ("W8", "M2", "MOTOR_B", (.62, .2, .85), m2, 0.55, 2)):
        internal = route(pts, 1.0)
        wires[name], meta[name] = _finish(internal, cable, dx, -0.75, 0.7, wid, net, color,
                                          dict(motor_terminal=term))
    return wires, jacket, meta, cable


def _finish(internal, cable, dx, dn, od, wid, net, color, start):
    external = offset_yz_route(cable, dx, dn)
    end = external[-1][2] + tangent(external[-1], True) * 8.0
    segs = internal + external + [("line", external[-1][2], end)]
    meta = dict(wire_id=wid, net=net, color=color, od_mm=od, centerline_length_mm=round(length(segs), 2),
                min_bend_radius_mm=round(min_radius(segs), 3), start_pin=start,
                note="Nominal routing; trim after sensor calibration and keep a service loop.")
    return sweep(segs, od), meta


def make_design(screw_length=40.0, screw_pitch=0.5):
    p = parameters(screw_length, screw_pitch)
    printed = {
        "01_barrel": make_barrel(p),
        "02_rear_cap": make_rear_cap(p),
        "03_head_collar": make_head_collar(p),
        "04_pushrod": make_pushrod(p),
        "05_rod_eye": make_rod_eye(p),
        "06_sensor_cover": make_cover_strip(p),
        "07_TPU_cable_boot": make_boot(),
    }
    hw = n20_core_part(screw_length, screw_pitch)
    n0 = CARRIER_Z0 + NUT_DZ[0]
    hw["M3_nut"] = hex_z(5.5, 2.4, n0 + 0.1, 30).cut(cylinder(1.5, 2.6, n0))
    hw["magnet_4x2"] = cy(2.0, 2.0, 0, CARRIER[2], CARRIER_Z0 + MAGNET_DZ)
    zs = p["rod_end_z_retracted"] - 8.0 + 4.0
    hw["dowel_2x13.8_rod_eye"] = axial_x(0.98, 13.8, -6.9, 0, zs)
    for i, x in enumerate((-7.85, 7.85), start=1):
        # Shank shown at the M2 minor diameter where it self-taps into the barrel.
        screw = cylinder(1.0, 5.0, -28.0).union(cylinder(0.8, 5.0, -23.0))
        screw = screw.union(cylinder(1.9, 2.0, -30.0).cut(hex_z(1.5, 1.2, -30.1)))
        hw[f"M2x10_cap_screw_{i}"] = screw.translate((x, 0, 0))
    hall_meta = {}
    for label, zc in zip(("retract", "extend"), p["sensor_centres_z"]):
        h, m, _, _ = make_hall(label, zc)
        hw.update(h)
        hall_meta.update(m)
    wires, jacket, wire_meta, cable = make_harness(p)
    moving = ["04_pushrod", "05_rod_eye", "M3_nut", "magnet_4x2", "dowel_2x13.8_rod_eye"]
    return dict(params=p, printed=printed, hardware=hw, wires=wires, jacket=jacket, wire_meta=wire_meta,
                hall_meta=hall_meta, moving=moving, screw_envelope=screw_envelope(screw_length))

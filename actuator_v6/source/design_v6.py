"""V6: general-purpose two-wire actuator around the unmodified N20 leadscrew motor.

Units mm; frame and numbers from layout.py (Z = axis, Z = 0 gearbox front face, +X board
side, Y clevis-pin axis). All Z positions are for travel 0; moving parts are translated by
the travel.

Printed: 01 body, 02 front cap, 03 rear cap, 04 rod (carrier + rod, one part), 05 rod eye,
06 cable clamp.
Load path: the motor is screwed (2 x M1.6, countersunk) to the wall inside the body; its M4
leadscrew drives a thin brass M4 nut held in the carrier; each end cap has 2 x M1 screws into brass
heat-set inserts in the solid corners on the board side, the rear cap also hooks onto the end of the
motor-side wall (layout.REAR_HOOK) and the front cap has a third screw in the motor-side corner by the key rib,
so neither cap tips about its board side under load; the rod eye is held by one M2 cross screw.
Cable: the two cable wires leave through a slot in the rear cap (a knot inside stops them) and
run out sideways in a 3 mm sleeve, which the clamp plate grips under the two rear-cap screws.
"""
import math
import cadquery as cq
import layout as L
import board as BD
from cad_utils import cylinder, box, hex_z, rr_box, cone, cx_cone
from n20_screw_motor import n20_core_part, TERMINAL_Y, TERMINAL_HOLE_Z
from wire_geometry import route, sweep, length, min_radius, sample

X0, X1 = L.BODY_X
YH = L.BODY_Y


def outline(z0, z1, chamfer_front=0.0, chamfer_rear=0.0):
    s = rr_box(X0, X1, -YH, YH, z0, z1, L.BODY_R)
    if chamfer_front:
        s = s.faces(">Z").edges().chamfer(chamfer_front)
    if chamfer_rear:
        s = s.faces("<Z").edges().chamfer(chamfer_rear)
    return s


def lug_y(z_base, half_base, zc, r, thick):
    """Clevis lug in the XZ plane (pin along Y): hull of a base segment at z_base and the eye."""
    s = 1 if z_base > zc else -1
    pts = {}
    for side in (1, -1):
        bx, bz = side * half_base, z_base
        dx, dz = bx, bz - zc
        Ln = math.hypot(dx, dz)
        th = math.atan2(dz, dx)
        a = th - side * s * math.acos(r / Ln)
        pts[side] = (r * math.cos(a), zc + r * math.sin(a))
    far = (0, zc - s * r)
    wp = (cq.Workplane("XZ").moveTo(-half_base, z_base).lineTo(half_base, z_base)
          .lineTo(*pts[1]).threePointArc(far, pts[-1]).close())
    solid = wp.extrude(thick)
    bb = solid.val().BoundingBox()
    solid = solid.translate((0, -(bb.ymin + bb.ymax) / 2, 0))
    try:
        solid = solid.faces(">Y or <Y").edges().chamfer(0.4)
    except Exception:
        pass
    return solid


def pin_hole_y(zc, length=20):
    h = cylinder(L.PIN_HOLE / 2, length, -length / 2).rotate((0, 0, 0), (1, 0, 0), 90).translate((0, 0, zc))
    for y in (-L.EYE_T / 2, L.EYE_T / 2):
        c = cone(L.PIN_HOLE / 2 + 0.4, L.PIN_HOLE / 2, 0.4).rotate((0, 0, 0), (1, 0, 0), 90 if y > 0 else -90)
        h = h.union(c.translate((0, y, zc)))
    return h


def x_hole(radius, x0, x1, y, z):
    return cylinder(radius, x1 - x0).rotate((0, 0, 0), (0, 1, 0), 90).translate((x0, y, z))


def rr_wire(x0, x1, y0, y1, r, z):
    w = cq.Wire.makePolygon([cq.Vector(x0, y0, z), cq.Vector(x1, y0, z), cq.Vector(x1, y1, z),
                             cq.Vector(x0, y1, z)], close=True)
    return w.fillet2D(r, w.Vertices()) if r else w


def lead_in(x0, x1, y0, y1, r, z_face, depth, facing=-1):
    """45 degree chamfer cutter for a (rounded-)rectangle opening in a face at z_face. facing -1: the face
    looks -Z (material at z > z_face); +1: it looks +Z. On the bed it takes the first layer's squash."""
    e = depth + 0.01
    wide = rr_wire(x0 - e, x1 + e, y0 - e, y1 + e, r + e if r else 0, z_face + facing * 0.01)
    return cq.Workplane(obj=cq.Solid.makeLoft([wide, rr_wire(x0, x1, y0, y1, r, z_face - facing * depth)], True))


def xz_prism(pts, half_y, arc=None):
    """Prism along Y (|y| <= half_y) from a closed outline of (x, z) points. arc = (i, mid): the edge from
    point i to point i + 1 is a circular arc through mid."""
    w = cq.Workplane("XZ").moveTo(*pts[0])
    for i in range(1, len(pts)):
        w = w.threePointArc(arc[1], pts[i]) if arc and arc[0] == i - 1 else w.lineTo(*pts[i])
    return w.close().extrude(half_y, both=True)


FRONT_LEAD_IN = 0.3             # the body prints front end down: chamfers at the bore and board-slot mouths


def hook_wall_end():
    """The end of the motor-side wall behind the rear face, with the notch the cap's tooth hooks into
    (layout.REAR_HOOK). It reaches 1 mm into the body so that it fills the rear-face chamfer."""
    h, p = L.REAR_HOOK, L.rear_hook_profile()
    xi, xn, x0, zr, ze, zb = p["xi"], p["xn"], p["x0"], p["zr"], p["ze"], p["zb"]
    ci, r = h["inner_chamfer"], h["fillet"]
    pts = [(x0, zr + 1.0), (x0, ze), (xi - ci, ze), (xi, ze + ci), (xi, zb),       # outer face, end, flat head
           (xn, zb + h["notch"]), (xn, zr - r),                                     # 45 degree bevel, floor
           (xn + r, zr), (xi, zr), (xi, zr + 1.0)]                                  # fillet, rear face
    mid = (xn + r - r * math.sqrt(0.5), zr - r + r * math.sqrt(0.5))
    return xz_prism(pts, h["half_width"], arc=(6, mid))


def hook_pocket():
    """Cutter for the rear cap's pocket. What it leaves between the pocket and the bore is the tooth: a 45 degree
    bevel on the wall's bevel line, a flat tip with room under it, and a chamfer on the bed. The pocket's two ends
    get the same chamfer at the cap's face."""
    h, p = L.REAR_HOOK, L.rear_hook_profile()
    zr, bc = p["zr"], h["bed_chamfer"]
    pts = [(p["x0"] - 1.0, zr + 1.0), (p["x0"] - 1.0, p["zp"]), (p["xp"], p["zp"]),
           (p["xp"], p["zb"] - h["side_room"]), (p["xt"], p["zb"] + p["eng"]),          # pocket, tooth bevel
           (p["xt"], zr - bc), (p["xt"] + bc, zr), (p["xt"] + bc, zr + 1.0)]          # flat tip, bed chamfer
    pocket = xz_prism(pts, p["y_pocket"])
    yp = p["y_pocket"]
    ends = (cq.Workplane("YZ").polyline([(-yp, zr - bc), (yp, zr - bc), (yp + bc + 1.0, zr + 1.0),
                                         (-yp - bc - 1.0, zr + 1.0)]).close()
            .extrude(30.0).translate((-20.0, 0, 0)))
    mouth = xz_prism(pts, yp + bc + 1.0).intersect(box(30, 30, 1.0 + bc, z=zr + (1.0 - bc) / 2))
    return pocket.union(mouth.intersect(ends))


def key_cut(clear, z0, z1):
    """Cuts the (-X, -Y) corner of a part that slides past the bore's key rib, clear mm off the rib."""
    c = -L.BORE_X - L.BORE_Y + L.CARRIER_KEY + clear * math.sqrt(2)      # x + y < c is removed
    return (cq.Workplane("XY").polyline([(-20, -20), (-20, c + 20), (c + 20, -20)]).close()
            .extrude(z1 - z0).translate((0, 0, z0)))


def rib_mouth(z_face, depth):
    """The key rib's side of its face (x + y < c) near the body's front face, the face set back 45 degrees by
    `depth` at the front face: what the bore's lead-in leaves of the rib. The rib then reaches the front face,
    so the third front insert keeps its wall there, and its edge takes the first layer's squash like the bore's."""
    c0 = -L.BORE_X - L.BORE_Y + L.CARRIER_KEY
    tri = lambda c, z: cq.Wire.makePolygon([cq.Vector(-20, -20, z), cq.Vector(-20, c + 20, z),
                                            cq.Vector(c + 20, -20, z)], close=True)
    za, zb = z_face - depth - 0.01, z_face + 0.02
    ca, cb = c0 + 0.01 * math.sqrt(2), c0 - (depth + 0.02) * math.sqrt(2)
    return cq.Workplane(obj=cq.Solid.makeLoft([tri(ca, za), tri(cb, zb)], True))


# ---- printed parts -----------------------------------------------------------------------
def make_body(d, insert_holes=True):
    z0, z1 = d["body_z"]
    bx, by = L.BORE_X, L.BORE_Y
    b = outline(z0, z1, 0.4, 0.4)
    b = b.cut(rr_box(-bx, bx, -by, by, z0 - 1, L.WALL_Z[0], L.BORE_R))          # motor bay
    b = b.cut(rr_box(-bx, bx, -by, by, L.WALL_Z[1], z1 + 1, L.BORE_R))          # carrier bore
    w0, w1 = L.WALL_Z
    k = L.CARRIER_KEY                                                           # key rib, (-X, -Y)
    b = b.union(cq.Workplane("XY").polyline([(-bx - 0.3, -by - 0.3), (-bx - 0.3, -by + k + 0.3),
                                             (-bx + k + 0.3, -by - 0.3)]).close()
                .extrude(z1 - w1).translate((0, 0, w1)))
    b = b.cut(cylinder(L.WALL_HOLE_D / 2, w1 - w0 + 2, w0 - 1))                 # bushing + M4 screw
    for x, y in L.MOTOR_SCREWS:                                                 # M1.6 countersunk
        b = b.cut(cylinder(0.9, w1 - w0 + 2, w0 - 1).translate((x, y, 0)))
        b = b.cut(cone(0.9, 1.65, 0.751).translate((x, y, w1 - 0.75)))
    # PCB slot and component cavity; retain a continuous 1 mm wall toward the bore.
    sx0, sx1 = L.SLOT_X
    b = b.cut(box(sx1 - sx0, 2 * L.SLOT_Y, z1 - w1 + 1, x=(sx0 + sx1) / 2, z=(w1 + z1 + 1) / 2))
    px = L.PARTITION_X[1]
    b = b.cut(box(sx0 - px + 0.02, 2 * L.OPEN_Y, z1 - w1 + 1,
                  x=(px + sx0) / 2 + 0.01, z=(w1 + z1 + 1) / 2))
    # The front end is on the bed: lead-ins take the first layer's squash at the bore mouth (the carrier passes it
    # with 0.15 mm, the key rib with 0.2 mm) and at the board slot (0.05 mm). The partition is chamfered on its bore
    # side only, so it is 0.7 mm thick at the front face; the board ends 0.5 mm inside the body, behind the front
    # cap's tongue. The bore's lead-in follows the key rib's face, so the rib runs out to the front face.
    b = b.cut(lead_in(-bx, bx, -by, by, L.BORE_R, z1, FRONT_LEAD_IN, facing=+1)
              .cut(rib_mouth(z1, FRONT_LEAD_IN)))
    b = b.cut(lead_in(sx0, sx1, -L.SLOT_Y, L.SLOT_Y, 0, z1, FRONT_LEAD_IN, facing=+1))
    # wire channel beside the motor, and the wire passage through the wall
    b = b.cut(box(sx1 - bx + 0.02, 2 * L.OPEN_Y, w0 - z0 + 1, x=(bx + sx1) / 2, z=(z0 - 1 + w0) / 2))
    hx0, hx1, hy0, hy1 = L.WIRE_HOLE
    b = b.cut(box(hx1 - hx0 + 0.02, hy1 - hy0, w1 - w0 + 0.2, x=(hx0 + hx1) / 2 + 0.01, y=(hy0 + hy1) / 2,
                  z=(w0 + w1) / 2))
    b = b.union(hook_wall_end())                           # the rear cap hooks onto this (layout.REAR_HOOK)
    if insert_holes:                                       # heat-set insert holes in both end faces
        r, h = L.INSERT["hole"] / 2, L.INSERT["hole_depth"]
        for x, y in L.REAR_INSERTS:
            b = b.cut(cylinder(r, h + 0.5, z0 - 0.5).translate((x, y, 0)))
        for x, y in L.FRONT_INSERTS:
            b = b.cut(cylinder(r, h + 0.5, z1 - h).translate((x, y, 0)))
    return b


def make_front_cap(d):
    z0 = d["body_z"][1]
    z1 = z0 + L.FRONT_CAP_T
    c = outline(z0, z1, chamfer_front=0.4)
    spig = rr_box(-L.CARRIER_X + 0.05, L.CARRIER_X - 0.05, -L.CARRIER_Y + 0.05, L.CARRIER_Y - 0.05,
                  z0 - L.SPIGOT, z0 + 0.01, 0.6)
    c = c.union(spig.cut(key_cut(0.2, z0 - L.SPIGOT - 1, z0 + 0.01)))
    # tongue in the board groove: holds the board's front edge (0.1 mm play)
    tongue = z0 - d["pcb_z"][1] - 0.1
    assert tongue > 0, "PCB must leave space for the front-cap retaining tongue"
    c = c.union(box(L.PCB_T - 0.05, 2 * (L.SLOT_Y - 0.25), tongue + 0.01,
                    x=(L.PCB_X_INNER + L.PCB_X_OUTER) / 2, z=z0 - tongue / 2 + 0.005))
    c = c.cut(cylinder(L.ROD_GUIDE_D / 2, L.FRONT_CAP_T + L.SPIGOT + 1, z0 - L.SPIGOT - 0.5))
    c = c.cut(cone(L.ROD_GUIDE_D / 2, L.ROD_GUIDE_D / 2 + 0.5, 0.51).translate((0, 0, z1 - 0.5)))
    S = L.CAP_SCREW
    for x, y in L.FRONT_INSERTS:
        c = c.cut(cylinder(S["clear"] / 2, L.FRONT_CAP_T + 1, z0 - 0.5).translate((x, y, 0)))
        c = c.cut(cylinder(S["pocket_d"] / 2, S["pocket_depth"] + 0.01, z1 - S["pocket_depth"]).translate((x, y, 0)))
    return c


# Cable exit: the two cable wires come down the wire channel, pass the rear cap in a slot and turn
# out sideways (+X) inside the sleeve. The sleeve axis lies in the clamp face, the rear-cap pocket floor.
CLAMP_Z = L.BODY_REAR_Z - L.REAR_CAP_T + L.CLAMP_POCKET
LEAD_X = 5.3                    # the wires pass the rear cap here, 0.45 mm either side of y = 0
SLEEVE_X0 = 6.25                # inner end of the sleeve; it is gripped from here to the +X face
SLEEVE_BEND = (15.5, 4.0)       # outside: the sleeve turns from +X to -Z at this x, bend radius


def clamp_zone(x0, za, zb):
    return outline(za, zb).intersect(box(30, 30, zb - za, x=x0 + 15, z=(za + zb) / 2))


def sleeve_groove(side, x0):
    """Half of the clamp groove: side = +1 in the rear cap (material at z > CLAMP_Z), -1 in the clamp.
    Each half is 1.3 deep, so the 3.0 mm sleeve is squeezed by 0.4; the mouth flares for bending."""
    r = L.SLEEVE_OD / 2
    zc = CLAMP_Z - side * (r - (L.SLEEVE_OD - L.CLAMP_SQUEEZE) / 2)
    g = x_hole(r, x0, X1 + 1, 0, zc)
    return g.union(cx_cone(r, r + 0.6, 0.61, X1 - 0.6, 0, zc))


def ridges(side, xs):
    """0.3 mm ridges across the groove that bite into the sleeve."""
    r = L.SLEEVE_OD / 2
    zc = CLAMP_Z - side * (r - (L.SLEEVE_OD - L.CLAMP_SQUEEZE) / 2)
    half = box(30, 30, 10, z=CLAMP_Z + side * 5)
    out = None
    for x in xs:
        ring = x_hole(r + 0.01, x - 0.25, x + 0.25, 0, zc).cut(x_hole(r - 0.3, x - 1, x + 1, 0, zc)).intersect(half)
        out = ring if out is None else out.union(ring)
    return out


def make_rear_cap(d):
    z1 = L.BODY_REAR_Z
    z0 = z1 - L.REAR_CAP_T
    c = outline(z0, z1, chamfer_rear=0.4)
    c = c.union(lug_y(z0 + 0.6, 4.5, d["rear_eye_z"], L.EYE_OD / 2, L.EYE_T))
    c = c.cut(pin_hole_y(d["rear_eye_z"]))
    c = c.cut(clamp_zone(L.CLAMP_X0 - 0.1, z0 - 1, CLAMP_Z))                     # pocket for the clamp
    c = c.cut(sleeve_groove(+1, L.CLAMP_X0 - 0.1)).union(ridges(+1, (7.9,)))
    c = c.cut(box(1.4, 2.0, z1 - CLAMP_Z + 0.65, x=LEAD_X + 0.2, z=(z1 + CLAMP_Z) / 2 + 0.1))   # wire slot
    c = c.cut(hook_pocket())                          # takes the end of the motor-side wall; leaves the tooth
    for x, y in L.REAR_INSERTS:
        c = c.cut(cylinder(L.CAP_SCREW["clear"] / 2, L.REAR_CAP_T + 1, z0 - 0.5).translate((x, y, 0)))
    return c


def make_cable_clamp(d):
    """Clamp plate: sits in the rear-cap pocket; the two rear-cap screws pass through it and press it
    onto the sleeve. Counterbored so the heads stay inside the cap outline."""
    zb = CLAMP_Z - L.CLAMP_T
    j = clamp_zone(L.CLAMP_X0, zb, CLAMP_Z)
    j = j.faces("<Z").edges().chamfer(0.3)
    j = j.cut(sleeve_groove(-1, L.CLAMP_X0 - 0.1)).union(ridges(-1, (7.3, 8.5)))
    S = L.CAP_SCREW
    for x, y in L.REAR_INSERTS:
        j = j.cut(cylinder(S["clear"] / 2, L.CLAMP_T + 1, zb - 0.5).translate((x, y, 0)))
        j = j.cut(cylinder(S["pocket_d"] / 2, S["pocket_depth"] + 0.01, zb - 0.01).translate((x, y, 0)))
    return j


def sleeve_route(z_end):
    return route([(SLEEVE_X0, 0, CLAMP_Z), (SLEEVE_BEND[0], 0, CLAMP_Z), (SLEEVE_BEND[0], 0, z_end)], SLEEVE_BEND[1])


def make_rod(d):
    c0 = L.CARRIER_Z0
    c1 = c0 + L.CARRIER_LEN
    part = rr_box(-L.CARRIER_X, L.CARRIER_X, -L.CARRIER_Y, L.CARRIER_Y, c0, c1, 0.8)
    part = part.faces("<Z").edges().chamfer(0.3)
    part = part.cut(key_cut(0.2, c0 - 1, c1 + 1))                              # clears the bore's key rib
    rod = cylinder(L.ROD_D / 2, d["rod_end_z"] - c1 + 0.5, c1 - 0.5).faces(">Z").edges().chamfer(0.5)
    part = part.union(rod)
    part = part.cut(cylinder(L.ROD_BORE / 2, d["rod_bore_end_z"] - c0 + 1, c0 - 1))
    n0, n1 = c0 + L.NUT_SLOT_DZ[0], c0 + L.NUT_SLOT_DZ[1]
    af = L.NUT_AF + 0.15
    part = part.cut(hex_z(af, n1 - n0, n0))
    part = part.cut(box(L.CARRIER_X + 1, af, n1 - n0, x=-(L.CARRIER_X + 1) / 2, z=(n0 + n1) / 2))
    m = L.MAGNET
    mz = c0 + m["dz"]
    # block pocket, open to the +X face so the magnet slides in from the board side (press fit in Y)
    x0 = m["x"] - m["wx"] / 2
    part = part.cut(box(L.CARRIER_X + 0.5 - x0, m["wy"], m["l"] + 0.05, x=(x0 + L.CARRIER_X + 0.5) / 2, y=m["y"],
                        z=mz))
    # rod-eye cross screw: Ø1.7 through the solid rod, where the M2 × 10 cuts its own thread (about 7.9 mm, 20
    # turns). Until 2026-11-15 this was Ø2.2 clearance and the screw gripped the eye's 1.45 mm far wall (3½ turns).
    part = part.cut(x_hole(0.85, -5, 5, 0, d["rod_end_z"] - 4.5))
    return part


def make_rod_eye(d):
    re = d["rod_end_z"]
    s0 = re - 9.0
    e = cylinder(5.5, re + 1.5 - s0, s0).faces("<Z").edges().chamfer(0.5)
    e = e.union(lug_y(re + 1.0, 3.8, d["eye_front_z"], L.EYE_OD / 2, L.EYE_T))
    e = e.cut(cylinder(L.ROD_D / 2 + 0.05, 9.0 + 0.01, s0 - 0.01))
    e = e.cut(pin_hole_y(d["eye_front_z"]))
    zc = re - 4.5
    e = e.cut(x_hole(1.1, -6, 6, 0, zc))                                         # M2 clearance through both walls
    e = e.cut(x_hole(2.0, 4.6, 6.5, 0, zc))                                      # head counterbore
    return e


# ---- hardware -------------------------------------------------------------------------------
def countersunk_m16(x, y):
    w1 = L.WALL_Z[1]
    head = cone(0.8, 1.5, 0.7).translate((x, y, w1 - 0.7))
    shank = cylinder(0.8, 4.0 - 0.7, w1 - 4.0).translate((x, y, 0))
    return head.union(shank)


def pan_m1(x, y, z_head_top, direction):
    """M1 pan-head cap screw (layout.CAP_SCREW) along Z. direction=+1: head on top, its top face at
    z_head_top, shank going -Z; direction=-1: head below, its outer face at z_head_top, shank going +Z."""
    S = L.CAP_SCREW
    h, n = S["head_h"], S["length"]
    if direction > 0:
        head = cylinder(S["head_d"] / 2, h, z_head_top - h)
        shank = cylinder(S["d"] / 2, n, z_head_top - h - n)
    else:
        head = cylinder(S["head_d"] / 2, h, z_head_top)
        shank = cylinder(S["d"] / 2, n, z_head_top + h)
    return head.union(shank).translate((x, y, 0))


def heat_set_insert(x, y, z_outer, direction):
    """M1 brass heat-set insert (layout.INSERT), seated: its outer end face at z_outer, the insert below it
    (direction=+1, front face) or above it (direction=-1, rear face). Two knurl bands either side of a groove."""
    I = L.INSERT
    r, n = I["od"] / 2, I["length"]
    z0 = z_outer - n if direction > 0 else z_outer
    part = cylinder(r, n, z0).faces(">Z or <Z").edges().chamfer(0.12)
    groove = cylinder(r + 0.1, 0.3, z0 + n / 2 - 0.15).cut(cylinder(r - 0.12, 0.4, z0 + n / 2 - 0.2))
    part = part.cut(groove).cut(cylinder(I["bore"] / 2, n + 1, z0 - 0.5))
    return part.translate((x, y, 0))


def make_hardware(d):
    hw = n20_core_part(d["screw_length_mm"])
    c0 = L.CARRIER_Z0
    n0 = c0 + L.NUT_SLOT_DZ[0] + 0.05
    hw["M4_brass_nut"] = hex_z(L.NUT_AF, L.NUT_T, n0).cut(cylinder(1.62, L.NUT_T + 0.6, n0 - 0.3))   # D1 3.24
    m = L.MAGNET
    hw[L.MAGNET_NAME] = box(m["wx"] - 0.02, m["wy"] - 0.02, m["l"], x=m["x"], y=m["y"], z=c0 + m["dz"])
    for i, (x, y) in enumerate(L.MOTOR_SCREWS, start=1):
        hw[f"M1.6x4_countersunk_{i}"] = countersunk_m16(x, y)
    fz, S, I = d["front_cap_z"][1], L.CAP_SCREW, L.INSERT
    for i, (x, y) in enumerate(L.REAR_INSERTS, start=1):
        hw[f"M1_insert_rear_{i}"] = heat_set_insert(x, y, L.BODY_REAR_Z + I["recess"], -1)
        hw[f"M1x8_rear_cap_{i}"] = pan_m1(x, y, CLAMP_Z - L.CLAMP_T + S["pocket_depth"] - S["head_h"], -1)
    for i, (x, y) in enumerate(L.FRONT_INSERTS, start=1):
        hw[f"M1_insert_front_{i}"] = heat_set_insert(x, y, d["body_z"][1] - I["recess"], +1)
        hw[f"M1x8_front_cap_{i}"] = pan_m1(x, y, fz - S["pocket_depth"] + S["head_h"], +1)
    seg = sleeve_route(d["rear_eye_z"] - 12.0)
    hw["cable_sleeve"] = sweep(seg, L.SLEEVE_OD).cut(sweep(seg, L.SLEEVE_ID))
    zc = d["rod_end_z"] - 4.5
    eye_screw = (cylinder(1.9, 1.6).rotate((0, 0, 0), (0, 1, 0), 90).translate((4.6, 0, zc))
                 .union(cylinder(1.0, 10.0).rotate((0, 0, 0), (0, 1, 0), -90).translate((4.6, 0, zc))))
    hw["M2x10_rod_eye"] = eye_screw
    return hw


MOVING = {"04_rod", "05_rod_eye", "M4_brass_nut", L.MAGNET_NAME, "M2x10_rod_eye"}


# ---- board in 3D ----------------------------------------------------------------------------
def board_frame(u, v):
    return (u + L.PCB_Z0, v)            # (z, y)


def make_board(variant):
    """Board, copper and every part at its real position. Returns {name: (shape, meta)}.
    The 0.8 mm includes the copper: FR4 core 0.73 plus 0.035 of copper each side. Pads are separate
    from the masked tracks so the viewer can show them as tin."""
    from shapely.geometry import LineString, Point
    from shapely.ops import unary_union
    d = L.derived(variant)
    out = {}
    cu_t = 0.035
    xi, xo = L.PCB_X_INNER, L.PCB_X_OUTER
    z0, z1 = d["pcb_z"]
    out["PCB_board"] = (box(xo - xi - 2 * cu_t, L.PCB_W, z1 - z0, x=(xi + xo) / 2, z=(z0 + z1) / 2),
                        dict(kind="board", ref="PCB", note=f"V6-{variant} end-stop board, 2 layers, {L.PCB_T} mm"))
    tr, vias = BD.routes(variant)
    P = BD.pads(variant)

    def slab(geom, x0):
        solids = None
        for p in (geom.geoms if hasattr(geom, "geoms") else [geom]):
            if p.is_empty or p.area < 1e-4:
                continue
            p = p.simplify(0.004)
            pts = []
            for u, v in p.exterior.coords[:-1]:
                q = (v, u + L.PCB_Z0)
                if not pts or math.hypot(q[0] - pts[-1][0], q[1] - pts[-1][1]) > 1e-3:
                    pts.append(q)
            if len(pts) > 2 and math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) < 1e-3:
                pts.pop()
            wp = cq.Workplane("YZ").polyline(pts).close().extrude(cu_t).translate((x0, 0, 0))
            solids = wp if solids is None else solids.union(wp)
        return solids
    for net in BD.NETS:
        pad_geo = unary_union([p["poly"] for p in P.values() if p["net"] == net])
        vias_geo = [Point(at).buffer(BD.RULES["via_pad"] / 2, 16) for n, at in vias if n == net]
        top = unary_union([LineString(pts).buffer(w / 2) for n, l, w, pts in tr if n == net and l == "F.Cu"]
                          + vias_geo).difference(pad_geo)
        bot = unary_union([LineString(pts).buffer(w / 2) for n, l, w, pts in tr if n == net and l == "B.Cu"]
                          + vias_geo)
        for name, geom, x0, layer in ((f"PCB_pads_{net}", pad_geo, xi, "top pads"),
                                      (f"PCB_copper_top_{net}", top, xi, "top"),
                                      (f"PCB_copper_bottom_{net}", bot, xo - cu_t, "bottom")):
            sh = slab(geom, x0)
            if sh is not None:
                out[name] = (sh, dict(kind="copper", net=net, layer=layer))
    bodies = BD.bodies(variant)
    for ref, (kind, netmap, role) in BD.COMPONENTS.items():
        if kind == "WIRE":
            continue
        value, fpname, h, mpn, lcsc, colour = BD.PARTS[kind]
        meta = dict(kind="part", ref=ref, value=value, mpn=mpn, lcsc=lcsc, role=role, package=fpname,
                    nets=sorted(set(netmap.values())), colour=colour, height_mm=h,
                    pins={n: net for n, net in netmap.items()})
        u0, v0, u1, v1 = bodies[ref].bounds
        chip = fpname in ("0603", "R0603", "1206")
        lead_h = h if chip else 0.18
        if chip:                       # ceramic body between two tinned end terminations
            along_u = (u1 - u0) > (v1 - v0)
            t = 0.3 if fpname != "1206" else 0.5
            core = (u0 + t, v0, u1 - t, v1) if along_u else (u0, v0 + t, u1, v1 - t)
            ends = ([(u0, v0, u0 + t, v1), (u1 - t, v0, u1, v1)] if along_u
                    else [(u0, v0, u1, v0 + t), (u0, v1 - t, u1, v1)])
        else:                          # moulded body, leads from the body edge to the pad centres
            core = (u0, v0, u1, v1)
            ends = []
            for num in netmap:
                pu, pv = P[(ref, num)]["at"]
                w = 0.38 if fpname == "SOT-23" else 0.3
                if pu < u0:
                    ends.append((pu, pv - w / 2, u0 + 0.2, pv + w / 2))
                elif pu > u1:
                    ends.append((u1 - 0.2, pv - w / 2, pu, pv + w / 2))
                elif pv < v0:
                    ends.append((pu - w / 2, pv, pu + w / 2, v0 + 0.2))
                else:
                    ends.append((pu - w / 2, v1 - 0.2, pu + w / 2, pv))
        def blk(r, hh):
            a0, b0, a1, b1 = r
            return box(hh, b1 - b0, a1 - a0, x=xi - hh / 2, y=(b0 + b1) / 2, z=(a0 + a1) / 2 + L.PCB_Z0)
        body = blk(core, h) if chip else blk(core, h - 0.05).translate((-0.05, 0, 0))   # 0.05 standoff
        out[f"PCB_{ref}"] = (body, meta)
        leads = None
        for r in ends:
            b = blk(r, lead_h)
            leads = b if leads is None else leads.union(b)
        if leads is not None:
            out[f"PCB_{ref}__leads"] = (leads, dict(meta, kind="part_leads"))
    return out


# ---- wires ----------------------------------------------------------------------------------
WIRES = {  # id: (net, colour, start pad, end)
    "W1": ("A", (0.80, 0.10, 0.08), "J_A", "cable"),
    "W2": ("B", (0.06, 0.06, 0.07), "J_B", "cable"),
    "W3": ("MOT+", (0.85, 0.45, 0.05), "J_M+", ("motor", 2)),
    "W4": ("MOT-", (0.45, 0.20, 0.65), "J_M-", ("motor", 1)),
}


def open_route(points, radius, target):
    """Route that runs straight on past its last point until it is target mm long: a wire end that has
    not been laid yet."""
    pts = [tuple(q) for q in points]
    for _ in range(4):
        err = target - length(route(pts, radius))
        if abs(err) < 1e-4:
            break
        a, b = pts[-2], pts[-1]
        k = math.dist(a, b)
        pts[-1] = tuple(b[i] + (b[i] - a[i]) / k * err for i in range(3))
    return route(pts, radius)


def path_samples(states, step=0.25):
    """Each route state sampled at the same number of points (the viewer morphs between them)."""
    n = round(length(states["final"]) / step) + 1
    return {k: [c for q in sample(seg, n) for c in q] for k, seg in states.items()}


def make_wires(variant):
    P = BD.pads(variant)
    d = L.derived(variant)
    r = L.WIRE_OD / 2
    xs = L.SLOT_X[0] - r - 0.05                 # lies on the pad and clears the wall passage
    out, meta = {}, {}
    for wid, (net, colour, pad, end) in WIRES.items():
        u, v = P[(pad, "1")]["at"]
        z_pad = u + L.PCB_Z0 + 0.5
        y = v * 0.82 if abs(v) > 2 else v
        extra = {}
        if end == "cable":
            yl = 2.2 if v > 0 else -2.2
            ys = 0.45 if v > 0 else -0.45
            bx, bz = SLEEVE_BEND[0], d["rear_eye_z"] - 12.0
            inside = [(xs, v, z_pad), (xs, v, L.WALL_Z[1] + 1.0), (xs, y, L.WALL_Z[0] - 1.5),
                      (6.6, yl, -18.0), (6.6, yl, -25.4), (LEAD_X, ys, -27.2), (LEAD_X, ys, CLAMP_Z)]
            pts = inside + [(bx, ys, CLAMP_Z), (bx, ys, bz - 3.0)]   # in the sleeve, 3 mm out of its end
            seg = route(pts, [0.9] * 6 + [SLEEVE_BEND[1]])
            knot = route(inside[:5] + [(LEAD_X + 0.4, ys + (yl - ys) * 0.2, -26.8)], 0.9)
            extra = dict(inside_to_clamp_mouth_mm=round(length(route(inside + [(X1, ys, CLAMP_Z)], 0.9)), 1),
                         knot_from_pad_mm=round(length(knot), 0), knot_u=round(length(knot), 2))
            # while fitted: straight out of the rear of the body, then straight through the rear-cap slot; the cap
            # goes on REAR_HOOK["shift"] toward +X first (the tooth clears the wall end), and the wires go with it
            sh = L.REAR_HOOK["shift"]
            states = dict(final=seg, pre=open_route(inside[:5], 0.9, length(seg)),
                          slot_fit=open_route(inside[:5] + [(LEAD_X + sh, ys, -27.2), (LEAD_X + sh, ys, CLAMP_Z)],
                                              0.9, length(seg)),
                          slot=open_route(inside, 0.9, length(seg)))
        else:
            yt = TERMINAL_Y if end[1] == 2 else -TERMINAL_Y
            xin = 5.85
            ty = yt + (0.15 + r if yt > 0 else -0.15 - r)
            pts = [(xs, v, z_pad), (xs, v, -20.0), (xin, v, -24.6), (3.2, ty, TERMINAL_HOLE_Z),
                   (0.2, ty, TERMINAL_HOLE_Z)]                                  # along the tab
            seg = route(pts, 0.9)
            states = dict(final=seg, pre=open_route(pts[:2], 0.9, length(seg)))   # straight out of the rear
        out[wid] = sweep(seg, L.WIRE_OD)
        meta[wid] = dict(wire_id=wid, net=net, color=colour, od_mm=L.WIRE_OD, start_pad=pad,
                         end=("through the rear-cap slot (knot inside the body) and the cable clamp, "
                              "in the 3 mm sleeve, to the driver" if end == "cable"
                              else f"motor terminal {end[1]} ({'+' if end[1] == 2 else '-'})"),
                         centerline_length_mm=round(length(seg), 1),
                         min_bend_radius_mm=round(min_radius(seg) or 0, 2), paths=path_samples(states), **extra)
    return out, meta


def make_design(variant):
    d = L.derived(variant)
    printed = {"01_body": make_body(d), "02_front_cap": make_front_cap(d), "03_rear_cap": make_rear_cap(d),
               "04_rod": make_rod(d), "05_rod_eye": make_rod_eye(d), "06_cable_clamp": make_cable_clamp(d)}
    hardware = make_hardware(d)
    board = make_board(variant)
    wires, wire_meta = make_wires(variant)
    return dict(variant=variant, params=d, printed=printed, hardware=hardware, board=board, wires=wires,
                wire_meta=wire_meta, moving=MOVING,
                sleeve_path=path_samples(dict(final=sleeve_route(d["rear_eye_z"] - 12.0)))["final"])

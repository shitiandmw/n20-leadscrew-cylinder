"""Revision F track joint: straight X101 arms in plain receiving seats (left track, mm).

The original flat main-plate face remains Y=-34. Each X101 arm keeps its full
28 mm width to the plate and ends flat in a plain 1.5 mm deep rectangular seat.
Two M4 screws pass through the arm end on either side of its 9 mm centre web;
the heads and washers sit in side slots in the arm, the washers and nuts on the
far side are external. Plain bores retain the full remaining plate wall.
"""
import cadquery as cq
import tw_parts as tp

STATIONS = (-63.5, 63.5)
ARM_HALF = 14.0                    # X101 arm half-width, constant from the root bend into the seat
WIDTH = 2*ARM_HALF
PLATE_FACE_Y = -34.0
SEAT_DEPTH = 1.5
SEAT_SIDE_CLEARANCE = .15
FACE_Y = PLATE_FACE_Y + SEAT_DEPTH
WALL_Y = (PLATE_FACE_Y, -24.0)
ORIGINAL_WALL_Y = (-30.0, -24.0)
THICKENING_Y = (PLATE_FACE_Y, ORIGINAL_WALL_Y[0])
FACE_Z = (53.0, 74.0)              # arm end: underside on the seat ledge, deck at the plate
CLAMP_T = 10.5                     # arm-end stock between the head slots and the seat face
HEAD_FACE_Y = FACE_Y - CLAMP_T     # -43: washer face at the outboard end of each slot
CROWN_Z = 57.5                     # flat arm underside over the motor pod
CROWN_Y = -62.0                    # the foot curve starts at the crown of the arm's arched underside
FOOT = ((PLATE_FACE_Y, FACE_Z[0]), (PLATE_FACE_Y, 58.0), (-46.0, CROWN_Z), (CROWN_Y, CROWN_Z))  # cubic Bezier
WEB = 9.0                          # centre web between the two head slots
SLOT_Y = (-73.0, HEAD_FACE_Y)      # head slots, round inboard end
SLOT_Z = (62.75, 72.75)
SLOT_R = (SLOT_Z[1]-SLOT_Z[0])/2
ACCESS_LANE = 10.0                 # J909 relief beside each slot for sideways screw entry
BOLT_OFFSET = 9.5
BOLT_Z = (67.75,)
HOLE_R = 2.25
BOLT_L = 25.0
HEAD = dict(r=3.5, h=4.0)  # ISO 4762 M4; 3 mm hex key
WASHER = dict(ro=4.5, ri=2.2, t=.8)
NUT = dict(af=7.0, h=3.2)
REAR_WASHER_Y = (WALL_Y[1], WALL_Y[1]+WASHER['t'])
NUT_Y = (REAR_WASHER_Y[1], REAR_WASHER_Y[1]+NUT['h'])
DIAPHRAGM_X = (42.0, 52.0)
DIAPHRAGM_Z = (37.0, 55.0)
WINDOW_C = .5                      # J909 clearance round the arm


def bolt_centres():
    """Return station index, side index, X and Z for both screws of each arm."""
    return [(i, j, x+dx, BOLT_Z[0])
            for i, x in enumerate(STATIONS)
            for j, dx in enumerate((-BOLT_OFFSET, BOLT_OFFSET))]


def foot_points(n=60):
    """Samples of the foot curve, ordered from the plate face inboard."""
    (y0, z0), (y1, z1), (y2, z2), (y3, z3) = FOOT
    out = []
    for k in range(n+1):
        t = k/n
        a, b, c, d = (1-t)**3, 3*(1-t)**2*t, 3*(1-t)*t**2, t**3
        out.append((a*y0+b*y1+c*y2+d*y3, a*z0+b*z1+c*z2+d*z3))
    return out


def arm_under(y):
    """Arm underside height at track-frame Y over the joint region (Y >= CROWN_Y)."""
    if y >= PLATE_FACE_Y:
        return FACE_Z[0]
    pts = foot_points()
    for (ya, za), (yb, zb) in zip(pts, pts[1:]):
        if yb <= y <= ya:
            return min(CROWN_Z, za+(zb-za)*(y-ya)/(yb-ya) if ya != yb else min(za, zb))
    return CROWN_Z


def arm_window(x, c=WINDOW_C):
    """Open-top window following the arm's underside with clearance c."""
    p = (cq.Workplane('YZ').moveTo(-80.0, 90.0).lineTo(-29.0, 90.0)
         .lineTo(-29.0, FACE_Z[0]-c).lineTo(PLATE_FACE_Y, FACE_Z[0]-c)
         .bezier([(y, z-c) for y, z in FOOT[1:]], includeCurrent=True)
         .lineTo(-80.0, CROWN_Z-c).close())
    w = p.extrude(2*(ARM_HALF+c)).translate((x-ARM_HALF-c, 0, 0))
    return w.intersect(tp.box(x-ARM_HALF-c-1, x+ARM_HALF+c+1, -65.0, -29.0, 0, 90.0))


def access_lanes(x):
    """Space beside both slots, above the slot floor, for the screw and washer to slide in."""
    return tp.box(x-ARM_HALF-ACCESS_LANE, x+ARM_HALF+ACCESS_LANE, *SLOT_Y, SLOT_Z[0], 90.0)


def receiving_seats():
    """Plain open-top rectangular seats, side clearance, nominal lower bearing contact."""
    c = SEAT_SIDE_CLEARANCE
    return cq.Workplane(obj=cq.Compound.makeCompound([
        tp.one(tp.box(x-ARM_HALF-c, x+ARM_HALF+c, PLATE_FACE_Y-.01, FACE_Y, FACE_Z[0], 90))
        for x in STATIONS]))


def bolt_bores():
    return cq.Workplane(obj=cq.Compound.makeCompound([
        tp.one(tp.ycyl(HOLE_R, HEAD_FACE_Y-1, WALL_Y[1]+1, x, z))
        for _, _, x, z in bolt_centres()]))


def housing_clearance():
    """J909: arm windows plus the screw-entry lanes (these only reach the rear motor-pod shell)."""
    return cq.Workplane(obj=cq.Compound.makeCompound([
        tp.one(arm_window(x).union(access_lanes(x))) for x in STATIONS]))


def main_face_clearance():
    """J901: remove only cosmetic rim material ahead of the original plate face."""
    windows = cq.Workplane(obj=cq.Compound.makeCompound([tp.one(arm_window(x)) for x in STATIONS]))
    return windows.intersect(tp.box(-200, 200, -100, PLATE_FACE_Y, 0, 100))

"""J9 JGY-370 single track: CadQuery parts, hardware and assembly instances (mm).

One printed H-frame (two walls joined by a web) carries everything:
- the JGY-370 bolts to the inner wall; the printed sprocket bolts to a bought Pololu #1999 hub
  that is set-screwed onto the motor's D-shaft;
  a printed journal plug in a 6800ZZ in the outer wall supports the sprocket's outer side;
- five road rollers and two support rollers (one part, 2 x 624ZZ each) on M4 bolts
  through both walls;
- a U-yoke slides in grooves in both walls and carries the idler on a plain 8 mm pin;
  the R5 spring sits between the web and the yoke.
A one-piece housing (inboard skirt + closed motor pod) encloses the motor.
"""
import math, sys
from pathlib import Path
from functools import lru_cache
import cadquery as cq
from shapely.geometry import Point, box as rect
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                       # track_wheel_jgy370/J9
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'track_wheel/source'))
sys.path.insert(0, str(HERE))
import tw_parts as tp                    # primitives, R4 idler wheel, sprocket outline (tp.ex)
from j9_design import *

box, ycyl, yring, xcyl, xring, zcyl, xz_prism, one = tp.box, tp.ycyl, tp.yring, tp.xcyl, tp.xring, tp.zcyl, tp.xz_prism, tp.one
YELLOW, DARK, STEEL, RUBBER, BRASS, MOTOR_C, GEARBOX_C, SPRING_C, BLACK = (
    tp.YELLOW, tp.DARK, tp.STEEL, tp.RUBBER, tp.BRASS, tp.MOTOR, tp.GEARBOX, tp.SPRING_C, tp.BLACK)
FRAME_C, HOUSING_C, YOKE_C, HUB_C = (.55, .64, .64), (.91, .60, .07), (.62, .45, .78), (.80, .82, .86)

ROLLERS = [(x, ROAD_Z, f'road{j}') for j, x in enumerate(ROAD_X)] + [(x, CARRIER_Z, f'support{j}') for j, x in enumerate(CARRIER_X)]
HOUSING_SCREWS = [(-84.0, 69.0), (-15.0, 33.0), (85.0, 62.0), (85.0, 32.0)]   # first one clears the pod's drum
CAN_Y = GEARBOX_FACE_Y - 13.2
GB_X, GB_Z = (DRIVE_X - 14.5, DRIVE_X + 31.5), (AXLE_Z - 16, AXLE_Z + 16)
GB_Y = (GEARBOX_FACE_Y - 23, GEARBOX_FACE_Y)
CAN_X = (GB_X[1], DRIVE_X + 62.3)
TERM_X = (CAN_X[1], CAN_X[1] + 10)
# Motor pod of the one-piece housing J909: a drum concentric with the sprocket, a shoulder over the gearbox,
# a tube over the can and a round nose with the cable port. Its cavity slides straight over the motor (+Y).
POD_CLEAR, POD_WALL = 0.8, 2.5
POD_FACE_Y = -60.0                       # drum and shoulder face; the tube's crown is 1.5 mm lower
DRUM_R = 26.5
SHOULDER_X, SHOULDER_H = GB_X[1] + POD_CLEAR + POD_WALL, (GB_Z[1] - GB_Z[0])/2 + POD_CLEAR + POD_WALL
SHOULDER_RC, DRUM_RF, FACE_FILLET = POD_CLEAR + POD_WALL, 6.0, 3.0
TUBE_R = 12 + POD_CLEAR + POD_WALL       # around the can axis
NOSE_X = TERM_X[1] + POD_CLEAR           # centre of the hemispherical nose
TUBE_X0 = SHOULDER_X - 8.0               # the tube starts inside the shoulder
PORT = dict(r=2.75, boss_r=4.5, length=3.0)
RIM_Y = (SKIRT_Y[1], -WALL_OUT)          # rim on the inner wall that closes the gap behind the skirt
BOSS_COUNTERBORE = 2.0                   # gearbox screw bosses (Ø7 x 2) nest in the wall
ROLLER_BOSS = dict(r=2.8, h=0.7)         # wall bosses touching only the 624 inner rings
M4_HEAD = dict(r=3.5, h=4.0)             # ISO 4762 M4
M3_HEAD = dict(r=2.75, h=3.0)            # ISO 4762 M3
M3_BUTTON = dict(r=2.85, h=1.65)         # ISO 7380 M3
HUB_SCREW_CB_R = 3.1                     # counterbore for ISO 4762 M3 heads (dk max 5.68 knurled)
NYLOC_M4 = dict(af=7.0, h=5.0)           # DIN 985
INSERT_M3 = dict(r=2.0, length=5.7)      # hole Ø4.0 x 5.7 (heat-set)
INSERT_M4 = dict(r=2.8, length=8.1)      # hole Ø5.6 x 8.1 (heat-set)


def yhex(af, y0, y1, x, z):
    return cq.Workplane('XZ').center(x, z).polygon(6, af*2/math.sqrt(3)).extrude(y1 - y0).translate((0, y1, 0))


def mirror_y(s):
    return s.mirror('XZ')


# ================================================================ H-frame
def wall_profile():
    shapes = [rect(DRIVE_X, WALL_BODY_Z[0], IDLER_X, WALL_BODY_Z[1]),
              Point(DRIVE_X, AXLE_Z).buffer(DRIVE_LOBE_R, quad_segs=48),
              Point(IDLER_X, AXLE_Z).buffer(IDLER_LOBE_R, quad_segs=48)]
    for x in ROAD_X:
        shapes += [Point(x, ROAD_Z).buffer(ROAD_EAR_R, quad_segs=32), rect(x - ROAD_EAR_R, ROAD_Z, x + ROAD_EAR_R, WALL_BODY_Z[0] + 1)]
    for x in CARRIER_X:
        shapes += [Point(x, CARRIER_Z).buffer(CARRIER_EAR_R, quad_segs=32), rect(x - CARRIER_EAR_R, WALL_BODY_Z[1] - 1, x + CARRIER_EAR_R, CARRIER_Z)]
    return unary_union(shapes)


def wall(side):
    """side -1: inner (motor) wall, +1: outer wall."""
    y0, y1 = sorted([side*WALL_IN, side*WALL_OUT])
    w = xz_prism(wall_profile() if side > 0 else unary_union([wall_profile(), pod_silhouette()]), y0, y1)
    face = side*WALL_IN                                   # inner face (toward the track centre)
    for x, z, _ in ROLLERS:
        b0, b1 = sorted([face, face - side*ROLLER_BOSS['h']])
        w = w.union(ycyl(ROLLER_BOSS['r'], b0, b1, x, z))
    # Yoke groove (arms slide in it; its rear end is the recoil stop) and the pin-end track.
    g0, g1 = sorted([face - side*.01, side*(WALL_IN + ARM_T + GROOVE_CLEAR)])
    w = w.cut(box(GROOVE_X0, IDLER_X + 40, g0, g1, AXLE_Z - ARM_HALF_Z - GROOVE_CLEAR, AXLE_Z + ARM_HALF_Z + GROOVE_CLEAR))
    t0, t1 = sorted([side*(WALL_IN + 1), side*(WALL_IN + ARM_T + GROOVE_CLEAR + 1.0)])
    w = w.cut(box(IDLER_LIMITS[0] - 4.8, IDLER_X + 40, t0, t1, AXLE_Z - 4.3, AXLE_Z + 4.3))
    for x, z, _ in ROLLERS:
        w = w.cut(ycyl(2.2, y0 - 2, y1 + 2, x, z))
    if side < 0:
        o = -WALL_OUT
        w = w.cut(ycyl(4.0, y0 - 1, y1 + 1, DRIVE_X, AXLE_Z))                       # shaft clearance
        w = w.cut(ycyl(6.8, o - 1, o + 1.8, DRIVE_X, AXLE_Z))                        # Ø13.2 x 1.6 gearbox boss
        for x, z in MOTOR_HOLES:
            w = w.cut(ycyl(3.7, o - 1, o + BOSS_COUNTERBORE, x, z))                  # Ø7 x 2 screw bosses
            w = w.cut(ycyl(1.7, y0 - 1, y1 + 1, x, z))
            w = w.cut(ycyl(3.25, -WALL_IN - 1.0, -WALL_IN + 1, x, z))               # 1 mm spot face, M3 x 6
        for x, z in HOUSING_SCREWS:                                                 # standoffs carry the housing
            w = w.union(ycyl(4.0, RIM_Y[0], o + .01, x, z))
            w = w.cut(ycyl(INSERT_M3['r'], RIM_Y[0] - 1, RIM_Y[0] + INSERT_M3['length'], x, z))
        w = w.union(pod_rim())
        for x in CHASSIS_X:
            w = w.union(box(x - CHASSIS_HALF_X, x + CHASSIS_HALF_X, CHASSIS_Y[0], CHASSIS_Y[1] + .01, *CHASSIS_Z))
            w = w.cut(ycyl(INSERT_M4['r'], CHASSIS_Y[0] - 1, CHASSIS_Y[0] + INSERT_M4['length'], x, sum(CHASSIS_Z)/2))
    else:
        w = w.cut(ycyl(B6800['D']/2, B6800_Y[0], WALL_OUT + 1, DRIVE_X, AXLE_Z))      # 6800ZZ seat, 1 mm lip
        w = w.cut(ycyl(6.0, WALL_IN - 1, B6800_Y[0] + .01, DRIVE_X, AXLE_Z))
    return w


def h_frame():
    web = box(WEB_X[0], WEB_X[1], -WALL_IN - .01, WALL_IN + .01, *WEB_Z)
    web = web.union(xcyl(SPIGOT_R, WEB_X[1] - .01, WEB_X[1] + SPIGOT_L, 0, AXLE_Z))
    return wall(-1).union(wall(1)).union(web).clean()


# ================================================================ drive
def hub_screw_xz(degs=HUB_SCREW_DEG):
    return [(DRIVE_X + HUB['pcd_r']*math.cos(math.radians(a)), AXLE_Z + HUB['pcd_r']*math.sin(math.radians(a))) for a in degs]


def sprocket():
    """Printed sprocket. The bought hub's flange sits in a recess in its inner face and 3 x M3 x 25 from the outer
    face hold it; a small pad inside the hub bore meets the shaft end and sets the axial position."""
    s = xz_prism(tp.ex.sprocket_outline(), -BUSH_HALF_L, BUSH_HALF_L, DRIVE_X, AXLE_Z)
    s = s.union(ycyl(SPROCKET_HUB_R, SPROCKET_Y[0], -BUSH_HALF_L + .01, DRIVE_X, AXLE_Z))
    s = s.cut(ycyl(HUB_RECESS['r'], SPROCKET_Y[0] - 1, HUB_FACE_Y, DRIVE_X, AXLE_Z))
    s = s.union(ycyl(STOP_PAD['r'], STOP_PAD['y'][0], STOP_PAD['y'][1] + .01, DRIVE_X, AXLE_Z))
    s = s.cut(ycyl(1.7, SHAFT_TIP_Y - .1, SPROCKET_Y[1] + 1, DRIVE_X, AXLE_Z))
    s = s.cut(ycyl(SOCKET['r'], SPROCKET_Y[1] - SOCKET['depth'], SPROCKET_Y[1] + 1, DRIVE_X, AXLE_Z))
    for x, z in hub_screw_xz():
        s = s.cut(ycyl(1.7, HUB_FACE_Y - 1, SPROCKET_Y[1] + 1, x, z))
        s = s.cut(ycyl(HUB_SCREW_CB_R, SPROCKET_Y[1] - M3_HEAD['h'], SPROCKET_Y[1] + 1, x, z))   # heads flush
    return s.clean()


def pololu_hub(tap_r=1.5):
    """Pololu #1999 hub in its J9 pose. Tapped holes default to the M3 major diameter (threads not modelled,
    as for the motor); tap_r=HUB['tap_r'] reproduces the vendor STEP's Ø2.5 holes for the comparison check."""
    f0 = HUB_FACE_Y - HUB['flange_t']
    s = ycyl(HUB['flange_r'], f0, HUB_FACE_Y, DRIVE_X, AXLE_Z)
    s = s.union(ycyl(HUB['boss_r'], f0 - HUB['boss_h'], f0 + .01, DRIVE_X, AXLE_Z))
    s = s.cut(ycyl(HUB['bore_r'], f0 - HUB['boss_h'] - 1, HUB_FACE_Y + 1, DRIVE_X, AXLE_Z))
    for x, z in hub_screw_xz(range(0, 360, 60)):
        s = s.cut(ycyl(tap_r, f0 - 1, HUB_FACE_Y + 1, x, z))
    for depth, _ in HUB_SET_SCREWS:
        s = s.cut(zcyl(tap_r, AXLE_Z, AXLE_Z + HUB['flange_r'] + 1, DRIVE_X, HUB_FACE_Y - depth))
    return s.clean()


def hub_set_screw(depth, length):
    """M3 set screw from the hub's radial hole down onto the shaft's flat (which faces +Z)."""
    z0 = AXLE_Z + SHAFT_FLAT['across'] - 3.0
    return zcyl(1.5, z0, z0 + length, DRIVE_X, HUB_FACE_Y - depth)


def journal_plug():
    return yring(PLUG['r'], PLUG['bore'], *PLUG['y'], DRIVE_X, AXLE_Z)


def jgy370():
    """JGY-370 envelope (check_packaging.py dimensions) with the gearbox face on the inner wall."""
    f = GEARBOX_FACE_Y
    gb = box(*GB_X, *GB_Y, *GB_Z)
    for x, z in MOTOR_HOLES:
        gb = gb.union(ycyl(3.5, f - .01, f + BOSS_COUNTERBORE, x, z))
    gb = gb.union(ycyl(6.6, f - .01, f + 1.6, DRIVE_X, AXLE_Z))
    for x, z in MOTOR_HOLES:
        gb = gb.cut(ycyl(1.5, f - 6, f + BOSS_COUNTERBORE + 1, x, z))              # M3 tapped holes (threads not modelled)
    shaft = ycyl(3, f + 1.6, f + 15.6, DRIVE_X, AXLE_Z)
    shaft = shaft.cut(box(DRIVE_X - 4, DRIVE_X + 4, f + 3.6, f + 16, AXLE_Z + 2.5, AXLE_Z + 4))
    shaft = shaft.cut(ycyl(1.5, f + 5.5, f + 16, DRIVE_X, AXLE_Z))                    # M3 x 10 deep tapped end
    can = xcyl(12, *CAN_X, CAN_Y, AXLE_Z)
    terminals = xcyl(12, *TERM_X, CAN_Y, AXLE_Z)          # solder tabs sit inside the Ø24 end cap; 10 mm for the leads
    return dict(gearbox=gb, shaft=shaft, can=can, terminals=terminals)


# ================================================================ rollers, idler, yoke
def roller():
    r = yring(ROLLER_R, 3.0, -ROLLER_HALF_W, ROLLER_HALF_W)
    for s in (-1, 1):
        y0, y1 = sorted([s*FLANGE_IN, s*ROLLER_HALF_W])
        r = r.union(yring(FLANGE_R, 3.0, y0, y1))
        y0, y1 = sorted([s*(ROLLER_HALF_W - B624['B']), s*(ROLLER_HALF_W + 1)])
        r = r.cut(ycyl(B624['D']/2, y0, y1))
    return r.clean()


def idler_wheel():
    return tp.idler_wheel()                                 # J8/R5 07_idler_wheel, unchanged


def idler_spacer(side=1):
    y0, y1 = sorted([side*10.05, side*(WALL_IN - .05)])
    return yring(5.5, 4.1, y0, y1)


def u_yoke():
    x0, x1 = YOKE_BASE_X
    z0, z1 = AXLE_Z - ARM_HALF_Z, AXLE_Z + ARM_HALF_Z
    y_out = WALL_IN + ARM_T
    s = box(x0, x1, -y_out, y_out, AXLE_Z - 7.0, AXLE_Z + ARM_HALF_Z)
    for side in (-1, 1):
        y0, y1 = sorted([side*WALL_IN, side*y_out])
        s = s.union(box(x0, IDLER_X, y0, y1, z0, z1)).union(ycyl(ARM_HALF_Z, y0, y1, IDLER_X, AXLE_Z))
    s = s.union(xcyl(SPIGOT_R, x0 - SPIGOT_L, x0 + .01, 0, AXLE_Z))
    s = s.cut(ycyl(4.05, -y_out - 1, y_out + 1, IDLER_X, AXLE_Z))
    return s.clean()


# ================================================================ housing
def _xz_solid(wp, y0, y1):
    """Extrude a closed XZ-workplane sketch between y0 < y1."""
    return wp.close().extrude(y1 - y0).translate((0, y1, 0))


def _rear_body(o, y0, y1):
    """Drum (concentric with the sprocket) + gearbox shoulder, outline offset inward by o; exact arcs, G1 corners."""
    R, h, rc, rf, x1 = DRUM_R - o, SHOULDER_H - o, SHOULDER_RC - o, DRUM_RF + o, SHOULDER_X - o
    cx, cz = DRIVE_X, AXLE_Z
    fx = cx + math.sqrt((R + rf)**2 - (h + rf)**2)                   # concave fillet centre: (fx, cz +- (h + rf))
    k = R/(R + rf)
    t1 = (cx + (fx - cx)*k, cz + (h + rf)*k)                          # drum / fillet tangent point (upper)
    a1 = math.atan2(t1[1] - cz, t1[0] - cx)
    def on_drum(a): return (cx + R*math.cos(a), cz + R*math.sin(a))
    def on_fillet(sgn):
        u = ((t1[0] - fx), (t1[1] - cz - (h + rf)))
        m = (u[0]/rf + 0.0, u[1]/rf - 1.0); n = math.hypot(*m)        # bisector of the two fillet radii
        return (fx + rf*m[0]/n, cz + sgn*(h + rf + rf*m[1]/n))
    c45 = rc*(1 - math.sqrt(.5))
    wp = (cq.Workplane('XZ').moveTo(cx - R, cz)
          .threePointArc(on_drum((math.pi + a1)/2), t1)
          .threePointArc(on_fillet(1), (fx, cz + h))
          .lineTo(x1 - rc, cz + h)
          .threePointArc((x1 - c45, cz + h - c45), (x1, cz + h - rc))
          .lineTo(x1, cz - h + rc)
          .threePointArc((x1 - c45, cz - h + c45), (x1 - rc, cz - h))
          .lineTo(fx, cz - h)
          .threePointArc(on_fillet(-1), (t1[0], 2*cz - t1[1]))
          .threePointArc(on_drum(-(math.pi + a1)/2), (cx - R, cz)))
    return _xz_solid(wp, y0, y1)


def _u_tube(r, x0, x1, y_open):
    """U-section over the can: inboard half-round of radius r round the can axis, straight sides to y_open; along X."""
    z, c = AXLE_Z, r*math.sqrt(.5)
    wp = (cq.Workplane('YZ').moveTo(y_open, z + r).lineTo(CAN_Y, z + r)
          .threePointArc((CAN_Y - r, z), (CAN_Y, z - r)).lineTo(y_open, z - r).close())
    return wp.extrude(x1 - x0).translate((x0, 0, 0))


def _u_nose(r, y_open):
    """Rounded nose: a quarter sphere (inboard half, front half) plus a half-cylinder toward the wall.
    The sphere's poles point along X, so the cable port drills the only degenerate point away."""
    c = cq.Vector(NOSE_X, CAN_Y, AXLE_Z)
    q = cq.Workplane(obj=cq.Solid.makeSphere(r, c, cq.Vector(1, 0, 0), -90, 90, 360))
    q = q.intersect(box(NOSE_X, NOSE_X + r + 1, CAN_Y - r - 1, CAN_Y, AXLE_Z - r - 1, AXLE_Z + r + 1))
    h = ycyl(r, CAN_Y, y_open, NOSE_X, AXLE_Z).intersect(box(NOSE_X, NOSE_X + r + 1, CAN_Y - 1, y_open + 1, AXLE_Z - r - 1, AXLE_Z + r + 1))
    return q.union(h)


def _tube(o, y_open):
    """Tube over the can and the rounded nose; no undercut toward the wall (+Y), so the housing slides on."""
    r = TUBE_R - o
    return _u_tube(r, TUBE_X0 + o, NOSE_X, y_open).union(_u_nose(r, y_open))


def pod_outer(y_open):
    body = _rear_body(0, POD_FACE_Y, y_open).faces('<Y').edges().fillet(FACE_FILLET)
    return body.union(_tube(0, y_open))


def pod_cavity(y_open):
    return _rear_body(POD_WALL, POD_FACE_Y + POD_WALL, y_open).union(_tube(POD_WALL, y_open))


def pod_rim():
    """Frame-side rim between the inner wall and the skirt, continuing the pod's walls (no gap to see the motor)."""
    y0, y1 = RIM_Y
    slab = box(-300, 300, y0, y1, -100, 200)
    return pod_outer(y1 + 1).intersect(slab).cut(pod_cavity(y1 + 2))


def pod_silhouette():
    """Approximate XZ footprint of the pod (shapely); added to the inner wall outline so the rim sits on the wall."""
    return unary_union([Point(DRIVE_X, AXLE_Z).buffer(DRUM_R, quad_segs=48),
                        rect(DRIVE_X, AXLE_Z - SHOULDER_H, SHOULDER_X, AXLE_Z + SHOULDER_H),
                        rect(TUBE_X0, AXLE_Z - TUBE_R, NOSE_X, AXLE_Z + TUBE_R),
                        Point(NOSE_X, AXLE_Z).buffer(TUBE_R, quad_segs=48)])


def housing():
    outline = unary_union([rect(DRIVE_X, 13, IDLER_X, 77), Point(DRIVE_X, AXLE_Z).buffer(33.5, quad_segs=48),
                           Point(IDLER_X, AXLE_Z).buffer(33.5, quad_segs=48)])
    for x, z, _ in ROLLERS:
        outline = outline.difference(Point(x, z).buffer(4.0, quad_segs=24))         # bolt access, Ø8
    for x in CHASSIS_X:
        outline = outline.difference(rect(x - CHASSIS_HALF_X - .5, CHASSIS_Z[0] - .5, x + CHASSIS_HALF_X + .5, CHASSIS_Z[1] + .5))
    s = xz_prism(outline, *SKIRT_Y).union(pod_outer(SKIRT_Y[1]))
    # 1 mm base flange round the pod on the skirt face, and a raised band on the motor tube.
    flange = box(-300, 300, SKIRT_Y[0] - 1.0, SKIRT_Y[0] + .01, -100, 200)
    s = s.union(_rear_body(-1.0, SKIRT_Y[0] - 1.0, SKIRT_Y[0] + .01).union(_tube(-1.0, SKIRT_Y[0] + .01)).intersect(flange))
    s = s.union(_u_tube(TUBE_R + .6, TERM_X[0] - 1.5, TERM_X[0] + 1.5, SKIRT_Y[1]))
    # Final-drive cover details on the drum face: hub disc, centre boss and a ring of 8 hex bolt heads (cosmetic).
    f = POD_FACE_Y
    s = s.union(ycyl(13.0, f - 1.5, f + .01, DRIVE_X, AXLE_Z).faces('<Y').edges().chamfer(.6))
    s = s.union(ycyl(5.5, f - 2.5, f - 1.5 + .01, DRIVE_X, AXLE_Z).faces('<Y').edges().chamfer(.4))
    for k in range(8):
        a = math.radians(22.5 + 45*k)
        s = s.union(yhex(3.2, f - 1.0, f + .01, DRIVE_X + 19.5*math.cos(a), AXLE_Z + 19.5*math.sin(a)))
    # Cable port at the nose tip.
    tip = NOSE_X + TUBE_R
    s = s.union(xcyl(PORT['boss_r'], tip - 2.0, tip + PORT['length'], CAN_Y, AXLE_Z).faces('>X').edges().chamfer(.8))
    s = s.cut(pod_cavity(SKIRT_Y[1] + 1))
    s = s.cut(xcyl(PORT['r'], NOSE_X, tip + PORT['length'] + 1, CAN_Y, AXLE_Z))
    for x, z in HOUSING_SCREWS:
        s = s.cut(ycyl(1.7, SKIRT_Y[0] - 1, SKIRT_Y[1] + 1, x, z))
    return s.clean()


# ================================================================ track
def track_shoe():
    """R4 shoe and link plates; only the shoe plate and grousers are widened to SHOE_W."""
    h = SHOE_W/2
    shoe = box(-9.4, 9.4, -h, h, -6, -4)
    for x in tp.ex.GROUSER_CENTRES:
        shoe = shoe.union(box(x - 1, x + 1, -h, h, -7, -6))
    for y0, y1 in [(-21, -14), (14, 21)]:
        plate = box(-10, 10, y0, y1, -4, 4).union(ycyl(4, y0, y1, -10, 0))
        plate = plate.cut(ycyl(4.3, y0 - 1, y1 + 1, 10, 0)).cut(ycyl(1.6, y0 - 1, y1 + 1, -10, 0))
        shoe = shoe.union(plate)
    for y0, y1 in [(-13.7, -8.7), (8.7, 13.7)]:
        eye = ycyl(4, y0, y1, 10, 0).union(box(0, 10, y0, y1, -4, 0))
        shoe = shoe.union(eye.cut(ycyl(1.6, y0 - 1, y1 + 1, 10, 0)))
    return shoe.cut(zcyl(1.2, -8, -3, 0, -5)).cut(zcyl(1.2, -8, -3, 0, 5)).clean()


def link_poses(pins):
    n = len(pins)
    for i in range(n):
        a, b = pins[i], pins[(i + 1) % n]
        yield i, (a + b)/2, math.atan2(b[1] - a[1], b[0] - a[0])


# ================================================================ hardware
def bearing_rings(b, y0, y1, x, z):
    ri, ro = b['d']/2, b['D']/2
    split_i, split_o = ri + (ro - ri)*.3, ro - (ro - ri)*.3
    inner = yring(split_i, ri, y0, y1, x, z)
    outer = yring(ro, split_o, y0, y1, x, z)
    shield = yring(split_o - .01, split_i + .01, y0 + .3, y1 - .3, x, z)
    return inner, outer, shield


def screw_y(r, head, y_face, length, x, z, toward):
    """Socket/button screw along Y: head on y_face, shank running in direction toward (+1/-1)."""
    h0, h1 = sorted([y_face, y_face - toward*head['h']])
    s0, s1 = sorted([y_face, y_face + toward*length])
    return ycyl(head['r'], h0, h1, x, z).union(ycyl(r, s0, s1, x, z))


def spring_helix(x0, length):
    s = SPRING; ro, ri, wire = s['od']/2, s['id']/2, s['wire']
    coils = s['solid']/wire; n_active = coils - 2
    pitch = (length - 2*wire)/n_active; rmean = (ro + ri)/2
    path = cq.Wire.makeHelix(pitch, n_active*pitch, rmean)
    prof = cq.Wire.makeCircle(wire/2, cq.Vector(rmean, 0, 0), cq.Vector(0, 1, 0))
    coil = cq.Solid.sweep(cq.Face.makeFromWires(prof), path, True, True).translate(cq.Vector(0, 0, wire))
    end0 = cq.Workplane('XY').circle(ro).circle(ri).extrude(wire).val()
    end1 = end0.translate(cq.Vector(0, 0, length - wire))
    spring = cq.Workplane(obj=cq.Compound.makeCompound([coil, end0, end1]))
    return spring.rotate((0, 0, 0), (0, 1, 0), 90).translate((x0, 0, AXLE_Z))


PRINTED = {
    'J901_H_frame': (h_frame, FRAME_C, 1, 'PETG or PA12, 3 walls, 30 % infill; supports under the inner wall',
                     'Two 6 mm walls joined by an 18 mm web. Motor seat, 6800ZZ seat, 7 roller holes, yoke grooves, 3 chassis bosses; '
                     'motor rim and 4 housing standoffs on the inner wall.'),
    'J902_sprocket': (sprocket, DARK, 1, 'PETG or PA12, 5 walls, 50 % infill; outer disc face on the bed',
                      'Unchanged 12-tooth 20 mm pitch form. Ø25.8 recess for the Pololu hub flange, 3 x M3 counterbored holes; Ø10 socket for the journal plug.'),
    'J903_journal_plug': (journal_plug, DARK, 1, 'PETG or PA12, 100 % infill, standing on its end',
                          'Ø9.95 journal in the 6800ZZ. The M3 x 50 screw clamps it and the sprocket to the motor shaft.'),
    'J904_roller': (roller, DARK, 7, 'PETG, 4 walls, 40 % infill, on its side',
                    'Road and support roller: Ø22 tread, Ø26 guide flanges, 46 wide, two 624ZZ seats.'),
    'J906_idler_wheel': (idler_wheel, DARK, 1, 'As J8 07_idler_wheel',
                         'Unchanged J8/R5 07_idler_wheel: Ø70.5 centre drum, rails, guide flanges, two 608 seats.'),
    'J907_idler_spacer': (idler_spacer, STEEL, 2, 'PETG, 100 % infill',
                          'Ø11 x 13.9 tube between the yoke arm and the 608 inner ring; locates the idler.'),
    'J908_U_yoke': (u_yoke, YOKE_C, 1, 'PETG or PA12, 4 walls, 50 % infill, base on the bed',
                    'Arms slide in the wall grooves; carries the Ø8 idler pin; spring pilot on the back.'),
    'J909_housing': (housing, HOUSING_C, 1, 'PETG, 3 walls; skirt inner face on the bed, supports inside the motor pod',
                     'Inboard skirt and motor pod in one piece: drum on the sprocket axis, gearbox shoulder, motor tube, '
                     'nose with cable port. 4 x M3 x 8 into inserts in the frame standoffs.'),
    'J910_track_shoe_70': (track_shoe, RUBBER, 34, 'PETG or PA12, as the R4 shoe',
                           'R4 shoe and link plates; shoe plate and grousers widened to 70 mm.'),
}


@lru_cache(maxsize=1)
def parts():
    out = {}
    for n, (fn, color, qty, material, note) in PRINTED.items():
        out[n] = dict(shape=fn(), color=color, quantity=qty, material=material, note=note, kind='printed')
    return out


# ================================================================ assembly
def unit(prt=None, with_chain=True):
    """All solids of one track in the assembly pose.

    Groups: frame (fixed), drive (turns about the drive axis), roadN / supportN,
    idler_slide (yoke, pin, spacers, 608 inner rings), idler (wheel), spring, track.
    """
    prt = prt or parts()
    out = {}
    def add(n, s, color, group, kind='hardware', source=None):
        out[n] = dict(shape=s, color=color, group=group, kind=kind, source=source)

    add('J901_H_frame', prt['J901_H_frame']['shape'], FRAME_C, 'frame', 'printed', 'J901_H_frame')
    add('J909_housing', prt['J909_housing']['shape'], HOUSING_C, 'housing', 'printed', 'J909_housing')
    add('J902_sprocket', prt['J902_sprocket']['shape'], DARK, 'drive', 'printed', 'J902_sprocket')
    add('J903_journal_plug', prt['J903_journal_plug']['shape'], DARK, 'drive', 'printed', 'J903_journal_plug')
    for j, (x, z, g) in enumerate(ROLLERS):
        add(f'J904_roller_{g}', prt['J904_roller']['shape'].translate((x, 0, z)), DARK, g, 'printed', 'J904_roller')
    add('J906_idler_wheel', prt['J906_idler_wheel']['shape'].translate((IDLER_X, 0, AXLE_Z)), DARK, 'idler', 'printed', 'J906_idler_wheel')
    for k, side in enumerate((-1, 1)):
        add(f'J907_idler_spacer_{k}', idler_spacer(side).translate((IDLER_X, 0, AXLE_Z)), STEEL, 'idler_slide', 'printed', 'J907_idler_spacer')
    add('J908_U_yoke', prt['J908_U_yoke']['shape'], YOKE_C, 'idler_slide', 'printed', 'J908_U_yoke')

    m = jgy370()
    add('JGY370_gearbox', m['gearbox'], GEARBOX_C, 'frame')
    add('JGY370_motor_can', m['can'], MOTOR_C, 'frame')
    add('JGY370_terminal_space', m['terminals'], (.75, .55, .35), 'frame')
    add('JGY370_output_shaft', m['shaft'], STEEL, 'drive')
    for i, (x, z) in enumerate(MOTOR_HOLES):
        add(f'motor_screw_M3x6_{i}', screw_y(1.5, M3_HEAD, -WALL_IN - 1.0, 6.0, x, z, -1), BLACK, 'frame')
    add('sprocket_screw_M3x50', screw_y(1.5, M3_HEAD, PLUG['y'][1], 50.0, DRIVE_X, AXLE_Z, -1), BLACK, 'drive')
    add('Pololu_1999_hub', pololu_hub(), HUB_C, 'drive')
    for i, (x, z) in enumerate(hub_screw_xz()):
        add(f'hub_screw_M3x25_{i}', screw_y(1.5, M3_HEAD, SPROCKET_Y[1] - M3_HEAD['h'], 25.0, x, z, -1), BLACK, 'drive')
    for depth, length in HUB_SET_SCREWS:
        add(f'hub_set_screw_M3x{length:g}', hub_set_screw(depth, length), BLACK, 'drive')
    i6, o6, s6 = bearing_rings(B6800, *B6800_Y, DRIVE_X, AXLE_Z)
    add('6800ZZ_inner', i6, STEEL, 'drive'); add('6800ZZ_outer', o6, STEEL, 'frame'); add('6800ZZ_shield', s6, BLACK, 'frame')

    for x, z, g in ROLLERS:
        for k, s in enumerate((-1, 1)):
            y0, y1 = sorted([s*(ROLLER_HALF_W - B624['B']), s*ROLLER_HALF_W])
            bi, bo, bs = bearing_rings(B624, y0, y1, x, z)
            add(f'624ZZ_{g}_{k}_inner', bi, STEEL, 'frame'); add(f'624ZZ_{g}_{k}_outer', bo, STEEL, g); add(f'624ZZ_{g}_{k}_shield', bs, BLACK, g)
        add(f'bolt_M4x70_{g}', screw_y(2.0, M4_HEAD, -WALL_OUT, 70.0, x, z, 1), BLACK, 'frame')
        add(f'nyloc_M4_{g}', yhex(NYLOC_M4['af'], WALL_OUT, WALL_OUT + NYLOC_M4['h'], x, z).cut(ycyl(2.0, 0, 50, x, z)), STEEL, 'frame')

    add('idler_pin_8x55', ycyl(4.0, -IDLER_PIN['length']/2, IDLER_PIN['length']/2, IDLER_X, AXLE_Z), STEEL, 'idler_slide')
    for k, (y0, y1) in enumerate([(-10, -3), (3, 10)]):
        bi, bo, bs = bearing_rings(B608, y0, y1, IDLER_X, AXLE_Z)
        add(f'608ZZ_{k}_inner', bi, STEEL, 'idler_slide'); add(f'608ZZ_{k}_outer', bo, STEEL, 'idler'); add(f'608ZZ_{k}_shield', bs, BLACK, 'idler')
    add('recoil_spring', spring_helix(SPRING_X0, SPRING_SET), SPRING_C, 'spring')

    for i, (x, z) in enumerate(HOUSING_SCREWS):
        add(f'insert_M3_{i}', yring(INSERT_M3['r'], 1.5, RIM_Y[0], RIM_Y[0] + INSERT_M3['length'], x, z), BRASS, 'frame')
        add(f'housing_screw_M3x8_{i}', screw_y(1.5, M3_BUTTON, SKIRT_Y[0], 8.0, x, z, 1), BLACK, 'housing')
    for i, x in enumerate(CHASSIS_X):
        add(f'insert_M4_chassis_{i}', yring(INSERT_M4['r'], 2.0, CHASSIS_Y[0], CHASSIS_Y[0] + INSERT_M4['length'], x, sum(CHASSIS_Z)/2), BRASS, 'frame')

    if with_chain:
        for n, (s, color) in chain(prt).items():
            add(n, s, color, 'track', 'printed' if n.startswith('shoe_') else 'hardware', 'J910_track_shoe_70' if n.startswith('shoe_') else None)
    return out


def chain(prt, pins=None):
    pins = PINS if pins is None else pins
    shoe = prt['J910_track_shoe_70']['shape']
    out = {}
    for i, origin, a in link_poses(pins):
        out[f'shoe_{i:02}'] = (shoe.rotate((0, 0, 0), (0, 1, 0), -math.degrees(a)).translate((float(origin[0]), 0, float(origin[1]))), RUBBER)
    for i, (x, z) in enumerate(pins):
        x, z = float(x), float(z)
        out[f'track_bushing_{i:02}'] = (yring(BUSH_R, 1.55, -BUSH_HALF_L, BUSH_HALF_L, x, z), STEEL)
        out[f'track_pin_{i:02}'] = (ycyl(PIN_R, -PIN_HALF_L, PIN_HALF_L, x, z), STEEL)
        for k, dy in enumerate([-CLIP_Y, CLIP_Y]):
            out[f'pin_clip_{i:02}_{k}'] = (yring(3, 1.5, dy - .3, dy + .3, x, z), STEEL)
    return out

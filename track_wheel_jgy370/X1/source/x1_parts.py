"""X1 crawler chassis: two J9 tracks on a printed X-frame, with the turntable seat reserved (mm).

Vehicle frame: X forward, Y to the left, Z up; origin on the ground under the swing centre.
- The J9 module as built is the left track (its inboard side is -Y in its own frame), so it sits at Y = +TRACK_Y.
  The right track is its mirror image: mirrored J901 H-frame and J909 housing prints, every other part the same.
- The X-frame X101 follows the Cat 320 lower frame: a round carbody under the slewing ring, four legs in an X and a
  mounting rail along each track. Each rail bolts to the track's three J9 chassis bosses (M4 inserts).
- The turntable is not built. Its seat is sized for a THK RU66 cross-roller ring (catalogue A18-20/21): the outer
  ring bolts to the X-frame with 8 x M4 from above, and the inner ring (8 x M4 tapped, PCD 45) is left for the turntable.
"""
import math, sys
from pathlib import Path
from functools import lru_cache
import cadquery as cq
from shapely.geometry import Point, LineString, Polygon, box as rect
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                                   # track_wheel_jgy370/X1
sys.path.insert(0, str(ROOT.parent / 'J9/source'))
import j9_parts as P9                                # also puts track_wheel/source on the path
import j9_design as D9

tp = P9.tp
box, ycyl, xcyl, zcyl, yring, one = tp.box, tp.ycyl, tp.xcyl, tp.zcyl, tp.yring, tp.one
REPO = P9.REPO
XFRAME_C, COVER_C, BEARING_C, RESERVE_C = (.93, .66, .10), (.20, .23, .25), (.62, .65, .69), (.35, .62, .85)
STEEL, BRASS, BLACK = P9.STEEL, P9.BRASS, P9.BLACK

# ---------------------------------------------------------------- reference (Cat 320, 07H spec sheet p. 2 and p. 4)
SCALE = 15
CAT320 = dict(track_length=4450, length_to_centre_of_rollers=3650, track_gauge=2380, undercarriage_width_790_shoes=3170,
              shoe_width=790, ground_clearance=470, counterweight_clearance=1050, tail_swing_radius=2830,
              upperframe_width=2780, track_rollers_per_side=8, carrier_rollers_per_side=2)

# ---------------------------------------------------------------- layout
TRACK_Y = 170.0                    # track centre lines at Y = +-170: the 60 mm excavator's 340 mm stance
BOSS_FACE_Y = TRACK_Y + D9.CHASSIS_Y[0]              # 124: J9 boss faces (M4 inserts), seen from the vehicle centre
CHASSIS_Z = sum(D9.CHASSIS_Z)/2                      # 68
CHASSIS_SCREW_L = 12.0             # M4 x 12 through the 6 mm rail: 6 mm in the 8.1 mm insert, 2.1 short of the hole bottom

# X-frame X101
TOP_Z = 85.0                       # flat top = slewing-ring seat; the whole top prints on the bed
BOTTOM_Z = 34.0                    # carbody rim; the belly cover sits below it
COVER_Z = (31.0, 34.0)             # ground clearance 31 (Cat 320: 470 mm, 31.3 at 1:15)
BODY_R, BODY_WALL, PLATE_T = 60.0, 6.0, 6.0
LEG_W, LEG_END_X, LEG_FILLET = 32.0, 73.5, 15.0      # leg centre lines meet the rails' inner faces at X = +-73.5
RAIL_T = 6.0
RAIL_IN_Y = BOSS_FACE_Y - RAIL_T                     # 118
RAIL_X = (-93.0, 95.0)
RAIL_Z0, RAIL_Z0_POD, POD_STEP_X = 61.5, 67.5, -70.0  # rail bottom: over the bosses and motor tube / over the pod's shoulder and drum
UNDER = ((BODY_R, BOTTOM_Z), (100.0, 73.0))          # underside rises from the carbody rim to the legs (Cat-style sloped bottom plates)
RAIL_HOLE_R, ACCESS_R = 2.25, 4.0                    # M4 clearance; J9 tool access through the rail
ACCESS = [(x, D9.CARRIER_Z) for x in D9.CARRIER_X] + [(x, z) for x, z in P9.HOUSING_SCREWS if z > RAIL_Z0]
CABLE_HOLE = dict(x=0.0, z=46.0, r=5.0)              # motor leads enter the carbody here, midway between the legs
COVER_BOSS_R, COVER_BOSS_ANG = 51.0, (45, 135, 225, 315)

# Turntable seat: THK RU66 cross-roller ring, catalogue A18-20/21 (references/thk_ru66/)
RU66 = dict(d=35.0, D=95.0, dp=66.0, B=15.0, ds_max=59.0, Dh_min=74.0, C_kN=17.5, C0_kN=22.3, mass_kg=.62,
            inner_pcd=45.0, inner_holes='8 x M4 tapped through', outer_pcd=83.0,
            outer_holes='8 x 4.5 drilled through, 8 counterbore depth 4.4')
SEAT_Z = TOP_Z                     # outer ring bottom face
TURNTABLE_Z = SEAT_Z + RU66['B']   # 100: turntable mounting face (inner ring top)
RELIEF_R, RELIEF_DEPTH = 37.5, 2.5 # clears the inner ring (Dh min 74) and up to 2 mm of turntable screw tips
PASSAGE_R = 12.5                   # cable passage at the swing centre (the centre-joint position)
OUTER_ANG = [22.5 + 45*k for k in range(8)]
INNER_ANG = [45*k for k in range(8)]
INSERT_M4, INSERT_M3 = P9.INSERT_M4, P9.INSERT_M3    # hole r 2.8 x 8.1 / r 2.0 x 5.7
MOUNT_RING = (35.0, 48.0, TOP_Z - 10.0)              # thickened ring under the seat for the 8 inserts
TAIL_SWING_R = CAT320['tail_swing_radius']/SCALE     # 188.7: reserved swing circle (the R3 upper body uses 189)
RESERVE_R = 189.0
M4_HEAD, M3_CSK = P9.M4_HEAD, dict(r=3.15, h=1.65)   # ISO 4762 M4; ISO 10642 M3 countersunk (90 deg)


def polar(r, deg):
    a = math.radians(deg)
    return r*math.cos(a), r*math.sin(a)


def xy_prism(poly, z0, z1):
    """Prism along Z from a shapely polygon (with holes) in the XY plane."""
    def wire(coords):
        return cq.Wire.makePolygon([cq.Vector(x, y, z0) for x, y in list(coords)[:-1]], close=True)
    face = cq.Face.makeFromWires(wire(poly.exterior.coords), [wire(h.coords) for h in poly.interiors])
    return cq.Workplane(obj=cq.Solid.extrudeLinear(face, cq.Vector(0, 0, z1 - z0)))


def zring(ro, ri, z0, z1, x=0., y=0.):
    return zcyl(ro, z0, z1, x, y).cut(zcyl(ri, z0 - 1, z1 + 1, x, y))


def leg_ends():
    return [(sx*LEG_END_X, sy*RAIL_IN_Y) for sx in (1, -1) for sy in (1, -1)]


def plan_outline():
    """Carbody circle and four legs in an X, concave corners rounded, cut at the rails' inner faces."""
    shapes = [Point(0, 0).buffer(BODY_R, quad_segs=64)]
    for x, y in leg_ends():
        shapes.append(LineString([(0, 0), (1.2*x, 1.2*y)]).buffer(LEG_W/2, cap_style=2))
    u = unary_union(shapes).buffer(LEG_FILLET, quad_segs=16).buffer(-LEG_FILLET, quad_segs=16)
    return u.intersection(rect(-300, -RAIL_IN_Y - .5, 300, RAIL_IN_Y + .5))


def rail_profile():
    """Rail elevation (X, Z): stepped up over the J9 motor pod's shoulder and drum, corners rounded."""
    p = Polygon([(RAIL_X[0], RAIL_Z0_POD), (POD_STEP_X - 6, RAIL_Z0_POD), (POD_STEP_X, RAIL_Z0), (RAIL_X[1], RAIL_Z0),
                 (RAIL_X[1], TOP_Z), (RAIL_X[0], TOP_Z)])
    return p.buffer(-2.5, join_style=1).buffer(2.5, join_style=1)


def underside():
    """Solid of revolution: everything above the X-frame's underside surface."""
    (r0, z0), (r1, z1) = UNDER
    pts = [(0, z0), (r0, z0), (r1, z1), (400, z1), (400, TOP_Z + 5), (0, TOP_Z + 5)]
    return cq.Workplane('XZ').polyline(pts).close().revolve(360, (0, 0, 0), (0, 1, 0))


@lru_cache(None)
def x_frame():
    s = xy_prism(plan_outline(), BOTTOM_Z, TOP_Z).intersect(underside())
    for side in (1, -1):
        y0, y1 = sorted([side*RAIL_IN_Y, side*BOSS_FACE_Y])
        s = s.union(tp.xz_prism(rail_profile(), y0, y1))
    # Hollow carbody: 6 mm wall, 6 mm top plate, open below (closed by the belly cover).
    s = s.cut(zcyl(BODY_R - BODY_WALL, BOTTOM_Z - 1, TOP_Z - PLATE_T))
    s = s.union(zring(MOUNT_RING[1], MOUNT_RING[0], MOUNT_RING[2], TOP_Z - PLATE_T + .01))
    for a in COVER_BOSS_ANG:
        s = s.union(zcyl(5.0, BOTTOM_Z, BOTTOM_Z + 10, *polar(COVER_BOSS_R, a)))
    # Seat for the RU66 outer ring, relief over the inner ring, cable passage, inserts.
    s = s.cut(zcyl(RELIEF_R, TOP_Z - RELIEF_DEPTH, TOP_Z + 1))
    s = s.cut(zcyl(PASSAGE_R, MOUNT_RING[2] - 1, TOP_Z + 1))
    for a in OUTER_ANG:
        s = s.cut(zcyl(INSERT_M4['r'], TOP_Z - INSERT_M4['length'] - 1, TOP_Z + 1, *polar(RU66['outer_pcd']/2, a)))
    for a in COVER_BOSS_ANG:
        s = s.cut(zcyl(INSERT_M3['r'], BOTTOM_Z - 1, BOTTOM_Z + INSERT_M3['length'], *polar(COVER_BOSS_R, a)))
    for side in (1, -1):
        s = s.cut(ycyl(CABLE_HOLE['r'], *sorted([side*(BODY_R - BODY_WALL - 2), side*(BODY_R + 2)]), CABLE_HOLE['x'], CABLE_HOLE['z']))
        y0, y1 = sorted([side*(RAIL_IN_Y - 1), side*(BOSS_FACE_Y + 1)])
        for x in D9.CHASSIS_X:
            s = s.cut(ycyl(RAIL_HOLE_R, y0, y1, x, CHASSIS_Z))
        for x, z in ACCESS:
            s = s.cut(ycyl(ACCESS_R, y0, y1, x, z))
    return s.clean()


def belly_cover():
    """Round guard under the carbody (the Cat 320's centre guard), 4 x M3 countersunk into inserts."""
    s = zcyl(BODY_R, *COVER_Z)
    for a in COVER_BOSS_ANG:
        x, y = polar(COVER_BOSS_R, a)
        s = s.cut(zcyl(1.7, COVER_Z[0] - 1, COVER_Z[1] + 1, x, y))
        s = s.cut(csk_cone(x, y))
    return s.clean()


def ru66():
    """THK RU66, simplified to its two rings. Faces follow the catalogue's mounting limits: the outer ring is
    supported outside Dh min 74 (bottom face), the inner ring inside ds max 59 (top face)."""
    z0, z1, zm = SEAT_Z, TURNTABLE_Z, SEAT_Z + RU66['B']/2
    outer = zring(RU66['D']/2, RU66['Dh_min']/2 + .5, z0, zm + .01).union(zring(RU66['D']/2, RU66['ds_max']/2 + .5, zm, z1))
    inner = zring(RU66['Dh_min']/2 - .5, RU66['d']/2, z0, zm).union(zring(RU66['ds_max']/2 - .5, RU66['d']/2, zm - .01, z1))
    for a in OUTER_ANG:
        x, y = polar(RU66['outer_pcd']/2, a)
        outer = outer.cut(zcyl(2.25, z0 - 1, z1 + 1, x, y)).cut(zcyl(4.0, z1 - 4.4, z1 + 1, x, y))
    for a in INNER_ANG:
        inner = inner.cut(zcyl(1.65, z0 - 1, z1 + 1, *polar(RU66['inner_pcd']/2, a)))      # M4 tapped through (minor dia.)
    return outer.clean(), inner.clean()


def screw_z(r, head, z_face, length, x, y, toward):
    """Socket/countersunk screw along Z: head on z_face, shank running in direction toward (+1/-1)."""
    h0, h1 = sorted([z_face, z_face - toward*head['h']])
    s0, s1 = sorted([z_face, z_face + toward*length])
    return zcyl(head['r'], h0, h1, x, y).union(zcyl(r, s0, s1, x, y))


def mirror_y(s):
    return s.mirror('XZ')


def track(side, inst9):
    """One J9 module in the vehicle frame: side +1 = left (as built), -1 = right (mirror image)."""
    out = {}
    for n, d in inst9.items():
        s = d['shape'] if side > 0 else mirror_y(d['shape'])
        out[('L_' if side > 0 else 'R_') + n] = {**d, 'shape': s.translate((0, side*TRACK_Y, 0)), 'side': side, 'j9': n}
    return out


def chassis_parts():
    """Printed X1 parts (single solids, vehicle frame)."""
    return {'X101_X_frame': dict(shape=x_frame(), quantity=1, material='PETG or PA12, 4 walls, 30 % infill',
                                 note='Carbody under the slewing ring, four legs in an X and a rail along each track (3 x M4 into the J9 chassis bosses). '
                                      'Flat top = RU66 seat with 8 M4 inserts; Ø25 cable passage at the swing centre.'),
            'X102_belly_cover': dict(shape=belly_cover(), quantity=1, material='PETG, 3 walls',
                                     note='Round guard under the carbody, 4 x M3 x 8 countersunk into inserts.')}


def unit(inst9=None, with_reserve=True):
    """Every solid of the chassis in the vehicle frame. Groups: track_L/track_R (J9 groups kept in 'j9group'),
    xframe, cover, bearing (reserved turntable interface), reserve (turntable swing envelope)."""
    inst9 = inst9 or P9.unit(with_chain=True)
    out = {}
    for side in (1, -1):
        for n, d in track(side, inst9).items():
            out[n] = {**d, 'j9group': d['group'], 'group': ('L_' if side > 0 else 'R_') + d['group']}
    def add(n, s, color, group, kind='hardware', source=None):
        out[n] = dict(shape=s, color=color, group=group, kind=kind, source=source)
    prt = chassis_parts()
    add('X101_X_frame', prt['X101_X_frame']['shape'], XFRAME_C, 'xframe', 'printed', 'X101_X_frame')
    add('X102_belly_cover', prt['X102_belly_cover']['shape'], COVER_C, 'cover', 'printed', 'X102_belly_cover')
    for side in (1, -1):
        tag = 'L' if side > 0 else 'R'
        for i, x in enumerate(D9.CHASSIS_X):
            add(f'chassis_screw_M4x12_{tag}{i}', chassis_screw(side, x), BLACK, 'xframe')
    for i, a in enumerate(OUTER_ANG):
        x, y = polar(RU66['outer_pcd']/2, a)
        add(f'insert_M4_seat_{i}', zring(INSERT_M4['r'], 2.0, TOP_Z - INSERT_M4['length'], TOP_Z, x, y), BRASS, 'xframe')
        add(f'seat_screw_M4x16_{i}', screw_z(2.0, M4_HEAD, TURNTABLE_Z - 4.4, 16.0, x, y, -1), BLACK, 'bearing')
    for i, a in enumerate(COVER_BOSS_ANG):
        x, y = polar(COVER_BOSS_R, a)
        add(f'insert_M3_cover_{i}', zring(INSERT_M3['r'], 1.5, BOTTOM_Z, BOTTOM_Z + INSERT_M3['length'], x, y), BRASS, 'xframe')
        add(f'cover_screw_M3x8_{i}', csk_screw(x, y), BLACK, 'cover')
    outer, inner = ru66()
    add('RU66_outer_ring', outer, BEARING_C, 'bearing')
    add('RU66_inner_ring', inner, BEARING_C, 'bearing')
    if with_reserve:
        add('RESERVED_turntable_swing_envelope', zcyl(RESERVE_R, TURNTABLE_Z, TURNTABLE_Z + 60.0), RESERVE_C, 'reserve', 'envelope')
    return out


def chassis_screw(side, x):
    """M4 x 12 socket screw from the rail's inner face into a J9 boss insert (shank outboard)."""
    return P9.screw_y(2.0, M4_HEAD, side*RAIL_IN_Y, CHASSIS_SCREW_L, x, CHASSIS_Z, side)


def csk_screw(x, y):
    """ISO 10642 M3 x 8 from below, head flush with the cover's underside."""
    return csk_cone(x, y).union(zcyl(1.5, COVER_Z[0] + M3_CSK['h'] - .01, COVER_Z[0] + 8.0, x, y))


def csk_cone(x, y):
    return cq.Workplane(obj=cq.Solid.makeCone(M3_CSK['r'], M3_CSK['r'] - M3_CSK['h'], M3_CSK['h'],
                                              cq.Vector(x, y, COVER_Z[0]), cq.Vector(0, 0, 1)))


def cable_route(side):
    """Reserved Ø5 path for one motor's two leads: from the pod's nose port, forward, then inboard into the carbody."""
    port_x = P9.NOSE_X + P9.TUBE_R + P9.PORT['length']             # tip of the port boss
    y_port = side*(TRACK_Y + P9.CAN_Y)
    a = cq.Vector(port_x, y_port, D9.AXLE_Z); b = cq.Vector(CABLE_HOLE['x'], y_port, D9.AXLE_Z)
    c = cq.Vector(CABLE_HOLE['x'], side*(BODY_R - BODY_WALL - 4), CABLE_HOLE['z'])
    seg = lambda p, q: cq.Workplane(obj=cq.Solid.makeCylinder(2.5, (q - p).Length, p, (q - p).normalized()))
    ball = cq.Workplane(obj=cq.Solid.makeSphere(2.5, b, angleDegrees1=-90, angleDegrees2=90))
    return seg(a, b).union(ball).union(seg(b, c))

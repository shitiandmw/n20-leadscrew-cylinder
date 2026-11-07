"""X1 crawler chassis: two J9 tracks on a printed X-frame, with the turntable seat reserved (mm).

Vehicle frame: X forward, Y to the left, Z up; origin on the ground under the swing centre.
- The J9 module as built is the left track (its inboard side is -Y in its own frame), so it sits at Y = +TRACK_Y.
  The right track is its mirror image: mirrored J901 H-frame and J909 housing prints, every other part the same.
- The X-frame X101 follows the Cat 320 lower frame: a round carbody under the slewing ring and four straight arms
  in an X. Rev F: each arm keeps its 28 mm width to the track plate and ends flat in a plain 1.5 mm seat; the deck
  and the arched underside are single curves, and side slots take the two screw heads (j9_mounts.py).
- The seat is sized for a THK RU66 cross-roller ring (catalogue A18-20/21). The inner ring (8 x M4 tapped, PCD 45)
  carries the turntable (x1_turntable.py, concept R3).
- X101 rev B (turntable concept R3, 2026-11-03): the RU66 outer ring sits on 8 x M4 x 30 with Ø12 washers, conical
  spring washers and nuts under the mount ring (plain Ø4.5 holes instead of heat-set inserts); a collar under the top
  plate locates the bought 6-way slip ring (R2); 6 countersunk Ø3.4 holes at R 51 take the ring gear X103's screws from
  below, with scallops in the mount ring and wall so the Ø6.3 heads pass.
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
import j9_mounts as M

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
SEAT_Y = TRACK_Y + M.FACE_Y        # 137.5: arm end face, bottom of the J901 seat
PLATE_Y = TRACK_Y + M.PLATE_FACE_Y # 136: J901 main-plate face

# X-frame X101
TOP_Z = 85.0                       # bearing seat on the bed
BOTTOM_Z = 34.0                    # carbody rim; the belly cover sits below it
COVER_Z = (31.0, 34.0)             # ground clearance 31 (Cat 320: 470 mm, 31.3 at 1:15)
BODY_R, BODY_WALL, PLATE_T = 60.0, 6.0, 6.0
ARM_X, ARM_HALF, ARM_FILLET = M.STATIONS[1], M.ARM_HALF, 10.0
ARM_ROOT = ((5.0, 35.0), (40.0, 20.0))   # arm root on the carbody (first quadrant)
ARM_STRAIGHT_Y = 96.0              # full 28 mm width from here into the seat
PROFILE_Y0 = 48.0                  # side profile: full carbody height inside |Y| 48
CROWN_Y = TRACK_Y + M.CROWN_Y      # 108: top of the arched underside; the J9 foot curve follows
SLOT_Y = tuple(TRACK_Y + y for y in M.SLOT_Y)   # 97..127: head slots
CABLE_HOLE = dict(x=0.0, z=46.0, r=5.0)              # motor leads enter the carbody here, midway between the arms
CABLE_X, CABLE_TURN_Y = 34.0, (96.0, 66.0)        # leads run forward beside the front arm, clear of the inner screws' key swing
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
# X101 rev B: turntable interface of concept R3 (swing_concept/X1_swing_concept_R3.pdf, sheet 4)
SEAT_HOLE_R = 2.25                 # plain Ø4.5 through the seat and mount ring; nuts below
SEAT_STACK = dict(screw_L=30.0, washer=(6.0, 2.2, 1.0), disc=(4.5, 2.2, 1.3), nut=(7.0, 3.2))   # DIN 9021 Ø12, DIN 6796 M4, ISO 4032 M4
COLLAR = dict(r_in=11.2, r_out=22.0, z=(TOP_Z - PLATE_T - 5.0, TOP_Z - PLATE_T), insert_r=17.5, insert_ang=(0.0, 120.0, 240.0))
RG_HOLES = dict(r=51.0, ang=[60.0*k for k in range(6)], hole_r=1.7, scallop_r=3.6)                # ring gear X103 screws, from below


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


def arm_centres():
    return [(sx*ARM_X, sy*SEAT_Y) for sx in (1, -1) for sy in (1, -1)]


def plan_outline():
    """Carbody disc and four arms; each arm is 28 mm wide from Y 96 to the seat, concave root fillets."""
    shapes = [Point(0, 0).buffer(BODY_R, quad_segs=64)]
    (x0, y0), (x1, y1) = ARM_ROOT
    for sx in (1, -1):
        for sy in (1, -1):
            shapes.append(Polygon([(sx*x, sy*y) for x, y in
                                  ((x0, y0), (x1, y1),
                                   (ARM_X+ARM_HALF, ARM_STRAIGHT_Y), (ARM_X+ARM_HALF, SEAT_Y+1),
                                   (ARM_X-ARM_HALF, SEAT_Y+1), (ARM_X-ARM_HALF, ARM_STRAIGHT_Y))]))
    u = unary_union(shapes).buffer(ARM_FILLET, quad_segs=6).buffer(-ARM_FILLET, quad_segs=6).simplify(.05)
    return u.intersection(rect(-300, -SEAT_Y - .5, 300, SEAT_Y + .5))


def deck_bezier():
    """Arm deck: z = 85 - 11 u^3 from |Y| 48 (u=0) to the plate face (u=1), as an exact cubic Bezier."""
    y0, y1 = PROFILE_Y0, PLATE_Y
    d = (y1 - y0)/3
    return [(y0, TOP_Z), (y0 + d, TOP_Z), (y0 + 2*d, TOP_Z), (y1, M.FACE_Z[1])]


def arch_bezier():
    """Arched underside from the carbody rim to the crown: z = 34 + 23.5 (1 - (1-u)^2), a quadratic Bezier."""
    return [(PROFILE_Y0, BOTTOM_Z), ((PROFILE_Y0 + CROWN_Y)/2, M.CROWN_Z), (CROWN_Y, M.CROWN_Z)]


def foot_bezier():
    """The J9 foot curve (j9_mounts.FOOT) in vehicle |Y|, from the crown to the plate face."""
    return [(TRACK_Y + y, z) for y, z in M.FOOT[::-1]]


def arm_profile():
    """|Y|-symmetric side elevation of the arms, extruded along X; exact Bezier edges only."""
    deck, arch, foot = deck_bezier(), arch_bezier(), foot_bezier()
    zb, zt = M.FACE_Z
    neg = lambda pts: [(-y, z) for y, z in pts]
    w = (cq.Workplane('YZ').moveTo(-SEAT_Y, zb).lineTo(-SEAT_Y, zt).lineTo(-PLATE_Y, zt)
         .bezier(neg(deck[::-1])[1:], includeCurrent=True)
         .lineTo(PROFILE_Y0, TOP_Z)
         .bezier(deck[1:], includeCurrent=True)
         .lineTo(SEAT_Y, zt).lineTo(SEAT_Y, zb).lineTo(PLATE_Y, zb)
         .bezier(foot[::-1][1:], includeCurrent=True)
         .bezier(arch[::-1][1:], includeCurrent=True)
         .lineTo(-PROFILE_Y0, BOTTOM_Z)
         .bezier(neg(arch)[1:], includeCurrent=True)
         .bezier(neg(foot)[1:], includeCurrent=True)
         .close())
    return w.extrude(400).translate((-200, 0, 0))


def arm_z_under(y):
    """Underside height of the arm at vehicle |Y| (for checks and drawings)."""
    y = abs(y)
    if y <= PROFILE_Y0:
        return BOTTOM_Z
    if y <= CROWN_Y:
        u = (y - PROFILE_Y0)/(CROWN_Y - PROFILE_Y0)
        return BOTTOM_Z + (M.CROWN_Z - BOTTOM_Z)*(1 - (1 - u)**2)
    return M.arm_under(y - TRACK_Y)


def arm_z_top(y):
    y = abs(y)
    if y <= PROFILE_Y0:
        return TOP_Z
    if y >= PLATE_Y:
        return M.FACE_Z[1]
    return TOP_Z - (TOP_Z - M.FACE_Z[1])*((y - PROFILE_Y0)/(PLATE_Y - PROFILE_Y0))**3


def slot_tool():
    """Both head slots of every arm (round inboard end, open to the side) and the screw bores, fused."""
    tool = None
    for sx in (1, -1):
        for sy in (1, -1):
            cx = sx*ARM_X
            y0, y1 = sorted((sy*SLOT_Y[0], sy*SLOT_Y[1]))
            for side in (-1, 1):
                xa, xb = sorted((cx + side*M.WEB/2, cx + side*(ARM_HALF + 6)))
                cut = box(xa, xb, y0, y1, *M.SLOT_Z).union(xcyl(M.SLOT_R, xa, xb, sy*SLOT_Y[0], M.BOLT_Z[0]))
                ya, yb = sorted((sy*(SLOT_Y[1] - 5), sy*(SEAT_Y + 2)))
                cut = cut.union(ycyl(M.HOLE_R, ya, yb, cx + side*M.BOLT_OFFSET, M.BOLT_Z[0]))
                tool = cut if tool is None else tool.union(cut)
    return tool


@lru_cache(None)
def x_frame():
    arms = xy_prism(plan_outline(), BOTTOM_Z - 1, TOP_Z + 1).cut(zcyl(BODY_R - 1, BOTTOM_Z - 2, TOP_Z + 2))
    arms = arms.intersect(arm_profile())
    s = zcyl(BODY_R, BOTTOM_Z, TOP_Z).union(arms).cut(slot_tool())
    # Hollow carbody: 6 mm wall, 6 mm top plate, open below (closed by the belly cover).
    s = s.cut(zcyl(BODY_R - BODY_WALL, BOTTOM_Z - 1, TOP_Z - PLATE_T))
    s = s.union(zring(MOUNT_RING[1], MOUNT_RING[0], MOUNT_RING[2], TOP_Z - PLATE_T + .01))
    for a in COVER_BOSS_ANG:
        s = s.union(zcyl(5.0, BOTTOM_Z, BOTTOM_Z + 10, *polar(COVER_BOSS_R, a)))
    # Seat for the RU66 outer ring, relief over the inner ring, cable passage (rev B: plain holes, nuts below).
    s = s.cut(zcyl(RELIEF_R, TOP_Z - RELIEF_DEPTH, TOP_Z + 1))
    s = s.cut(zcyl(PASSAGE_R, MOUNT_RING[2] - 1, TOP_Z + 1))
    for a in OUTER_ANG:
        s = s.cut(zcyl(SEAT_HOLE_R, MOUNT_RING[2] - 1, TOP_Z + 1, *polar(RU66['outer_pcd']/2, a)))
    # Rev B: slip-ring collar under the top plate (R2): Ø22.4 bore for the ring's spigot, 3 M3 inserts from below.
    z0, z1 = COLLAR['z']
    s = s.union(zring(COLLAR['r_out'], COLLAR['r_in'], z0, z1 + .01))
    for a in COLLAR['insert_ang']:
        s = s.cut(zcyl(INSERT_M3['r'], z0 - 1, z0 + INSERT_M3['length'], *polar(COLLAR['insert_r'], a)))
    # Rev B: ring gear screws from below, countersunk in the plate's underside; scallops let the heads pass.
    for a in RG_HOLES['ang']:
        x, y = polar(RG_HOLES['r'], a)
        s = s.cut(zcyl(RG_HOLES['hole_r'], z1 - 1, TOP_Z + 1, x, y))
        s = s.cut(cq.Workplane(obj=cq.Solid.makeCone(M3_CSK['r'] + .05, 0, M3_CSK['r'] + .05, cq.Vector(x, y, z1 - .01), cq.Vector(0, 0, 1))))
        s = s.cut(zcyl(RG_HOLES['scallop_r'], BOTTOM_Z - 1, z1, x, y))      # 0.6 deep groove up the carbody wall, notch in the mount ring
    for a in COVER_BOSS_ANG:
        s = s.cut(zcyl(INSERT_M3['r'], BOTTOM_Z - 1, BOTTOM_Z + INSERT_M3['length'], *polar(COVER_BOSS_R, a)))
    for side in (1, -1):
        s = s.cut(ycyl(CABLE_HOLE['r'], *sorted([side*(BODY_R - BODY_WALL - 2), side*(BODY_R + 2)]), CABLE_HOLE['x'], CABLE_HOLE['z']))
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
        inner = inner.cut(zcyl(2.0, z0 - 1, z1 + 1, *polar(RU66['inner_pcd']/2, a)))       # M4 tapped through (drawn at the major dia., as in J9)
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
    return {'X101_X_frame': dict(shape=x_frame(), quantity=1, material='PETG or PA12; qualify print settings for intended load',
                                 note='Rev F: four T-ends with integral curved supports seated in shallow main-plate recesses; exposed through-bolts on both wings. '
                                      'Flat top = RU66 seat with 8 M4 through-bolts; Ø25 cable passage at the swing centre.'),
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
    out.update(mount_hardware())
    for i, a in enumerate(OUTER_ANG):
        x, y = polar(RU66['outer_pcd']/2, a)
        for n, sh in seat_stack(x, y).items():
            add(f'{n}_{i}', sh, BLACK if n.startswith(('seat_screw', 'seat_nut')) else STEEL, 'bearing')
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


def seat_stack(x, y):
    """RU66 outer ring to X101 (rev B): M4 x 30 socket screw from the ring's counterbore; under the mount ring a Ø12
    washer, a conical spring washer (drawn flat at its free height) and a nut."""
    st = SEAT_STACK; z = MOUNT_RING[2]
    wz = (z - st['washer'][2], z); dz = (wz[0] - st['disc'][2], wz[0]); nz = (dz[0] - st['nut'][1], dz[0])
    return {'seat_screw_M4x30': screw_z(2.0, M4_HEAD, TURNTABLE_Z - 4.4, st['screw_L'], x, y, -1),
            'seat_washer_12': zring(st['washer'][0], st['washer'][1], *wz, x, y),
            'seat_disc_spring': zring(st['disc'][0], st['disc'][1], *dz, x, y),
            'seat_nut_M4': tp.zhex(st['nut'][0], *nz, x, y).cut(zcyl(2.0, nz[0] - 1, nz[1] + 1, x, y))}


def mount_stack(x, z):
    """Plain through-bolt: head and washer in the arm's side slot, rear washer and nut inside the track."""
    w = M.WASHER
    face = M.HEAD_FACE_Y
    return dict(
        screw_M4x25=P9.screw_y(2, M.HEAD, face-w['t'], M.BOLT_L, x, z, 1),
        washer=yring(w['ro'], w['ri'], face-w['t'], face, x, z),
        rear_washer=yring(w['ro'], w['ri'], *M.REAR_WASHER_Y, x, z),
        nut_M4=P9.yhex(M.NUT['af'], *M.NUT_Y, x, z).cut(ycyl(2, M.NUT_Y[0]-1, M.NUT_Y[1]+1, x, z)))


def mount_hardware():
    out = {}
    for side in (1, -1):
        tag = 'L' if side > 0 else 'R'
        for i, j, x, z in M.bolt_centres():
            for n, shape in mount_stack(x, z).items():
                if side < 0:
                    shape = mirror_y(shape)
                out[f'mount_{n}_{tag}{i}{j}'] = dict(
                    shape=shape.translate((0, side*TRACK_Y, 0)),
                    color=BLACK if n.startswith(('screw', 'nut')) else STEEL,
                    group='xframe', kind='hardware', source=None)
    return out


def key_side(x):
    """+1 if the screw at local X x lies on the +X side of its arm's centre web."""
    station = min(M.STATIONS, key=lambda c: abs(x - c))
    return 1 if x > station else -1


def mount_key(x, z, angle=0.0):
    """Ordinary 3 mm L-key: 20 mm short leg on the screw axis, 80 mm handle out of the side slot.

    angle is the handle's elevation above horizontal (degrees), turning about the screw axis.
    The socket is not modelled in the simplified screw, so the short leg stops
    just before the head. The standard socket supplies the final insertion.
    """
    head_end = M.HEAD_FACE_Y - M.WASHER['t'] - M.HEAD['h']
    bend_y = head_end - 18.0
    handle = xcyl(1.75, x, x + key_side(x)*80.0, bend_y, z)
    if angle:
        handle = handle.rotate((x, bend_y, z), (x, bend_y + 1, z), -key_side(x)*angle)
    return ycyl(1.75, bend_y, head_end - .05, x, z).union(handle)


def csk_screw(x, y):
    """ISO 10642 M3 x 8 from below, head flush with the cover's underside."""
    return csk_cone(x, y).union(zcyl(1.5, COVER_Z[0] + M3_CSK['h'] - .01, COVER_Z[0] + 8.0, x, y))


def csk_cone(x, y):
    return cq.Workplane(obj=cq.Solid.makeCone(M3_CSK['r'], M3_CSK['r'] - M3_CSK['h'], M3_CSK['h'],
                                              cq.Vector(x, y, COVER_Z[0]), cq.Vector(0, 0, 1)))


def cable_route(side):
    """Reserved Ø5 path for one motor's two leads.

    From the pod's nose port it runs forward under the arms to X 34, beside the
    front arm, then inboard and into the carbody's side hole at X 0. This keeps
    it out of the inner joint screws' L-key swing, which sweeps the gap between
    the arms at vehicle Y 99-106.
    """
    port_x = P9.NOSE_X + P9.TUBE_R + P9.PORT['length']             # tip of the port boss
    y_port = side*(TRACK_Y + P9.CAN_Y)
    pts = [cq.Vector(port_x, y_port, D9.AXLE_Z), cq.Vector(CABLE_X, y_port, D9.AXLE_Z),
           cq.Vector(CABLE_X, side*CABLE_TURN_Y[0], D9.AXLE_Z),
           cq.Vector(CABLE_HOLE['x'], side*CABLE_TURN_Y[1], CABLE_HOLE['z']),
           cq.Vector(CABLE_HOLE['x'], side*(BODY_R - BODY_WALL - 4), CABLE_HOLE['z'])]
    s = None
    for p, q in zip(pts, pts[1:]):
        seg = cq.Workplane(obj=cq.Solid.makeCylinder(2.5, (q - p).Length, p, (q - p).normalized()))
        s = seg if s is None else s.union(seg)
    for corner in pts[1:-1]:
        s = s.union(cq.Workplane(obj=cq.Solid.makeSphere(2.5, corner)))
    return s

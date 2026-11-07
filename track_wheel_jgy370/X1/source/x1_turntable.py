"""X1 turntable, concept R3 issue 3, in CAD (mm, vehicle frame: X forward, Y left, Z up, origin on the ground under the
swing centre).

Every dimension comes from the R3 drawing script (swing_concept/source/draw_swing_concept_r3.py), so the drawings and
this model cannot drift apart. The chassis-side interface (X101 rev B) is in x1_parts.py.

Printed, upper (turns with the swing):
  T101 centre frame, T102 motor slide, T103 drag-pad plunger (x 2), T104 hub adapter, T105 pinion.
Printed, chassis side (fixed):
  X103 ring gear; T106 slip-ring rotor dog (TPU, R2's dog; it turns with the rotor).
Bought: JGY-370-1260 12 V 200:1 swing motor (the tracks' motor, J9 model), Pololu #1999 hub, 6-way 2 A slip ring,
  screws, nuts, washers, conical spring washers, heat-set inserts, two springs, felt. Existing: the ARM60 base and arm
  (excavator_arm_60mm STEP, as exported).
"""
import math, sys
from functools import lru_cache
import numpy as np
import cadquery as cq
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
import x1_parts as X

sys.path.insert(0, str(X.ROOT / 'swing_concept/source'))
import draw_swing_concept_r3 as R3                    # noqa: E402  R3 constants (imports R1 and R2 too)
R2, C = R3.R2, R3.C
tp, P9, D9 = X.tp, X.P9, X.D9
zcyl, zring, box, xy_prism, polar = X.zcyl, X.zring, X.box, X.xy_prism, X.polar
REPO = X.REPO

UPPER_C, SLIDE_C, RING_C, TPU_C = (.42, .62, .80), (.30, .48, .66), (.86, .45, .16), (.63, .25, .0)
SLIP_C, FELT_C, SPRING_C = (.12, .38, .55), (.49, .24, .60), (.60, .62, .64)
STEEL, BRASS, BLACK, HUB_C = X.STEEL, X.BRASS, X.BLACK, P9.HUB_C
ARM_C = (.42, .30, .52)

# ------------------------------------------------------------------ fixed numbers (from R3; see the drawings)
ALPHA = 20.0                                          # pressure angle
DX_SET = R3.PX_SET - R3.PX                            # -0.137: the slide with the mesh set to 0.1 mm backlash
PXS = R3.PX_SET                                       # pinion axis X
RATIO = R3.ZR/R3.ZP                                   # 4: pinion turns per turn of the upper, relative to it
CAN_Z = R3.GB_FACE + C.CAN_AX                         # 122.2: motor axis height
M3_HEAD, M4_HEAD, M3_BUTTON = P9.M3_HEAD, X.M4_HEAD, P9.M3_BUTTON
M6_HEAD = dict(r=5.0, h=6.0)                          # ISO 4762 M6
WASHER_M3 = dict(ro=3.5, ri=1.6, t=.5)                # ISO 7089 M3
INSERT_M3 = X.INSERT_M3
CSK = X.M3_CSK
BODY_SLEEVE_X = (-120.0, -45.0)                       # body halves B102/B103: M3 inserts in the rib tops at Y +-65


def prism(g, z0, z1):
    """Prism along Z from a shapely polygon or multipolygon."""
    parts = [xy_prism(q, z0, z1) for q in getattr(g, 'geoms', [g]) if not q.is_empty]
    s = parts[0]
    for q in parts[1:]:
        s = s.union(q)
    return s


# ------------------------------------------------------------------ involute gears
def _tooth_polar(z, m=R3.M, alpha=ALPHA, n_flank=12):
    """One tooth, centred on angle 0, as (radius, angle) from root to tip and back (standard tooth, no backlash:
    the backlash comes from the set centre distance)."""
    a = math.radians(alpha)
    r, rb, ra, rf = m*z/2, m*z/2*math.cos(a), m*z/2 + m, m*z/2 - 1.25*m
    inv = lambda x: math.tan(x) - x
    psi = math.pi/(2*z)
    half = lambda rho: psi + inv(a) - inv(math.acos(min(1.0, rb/rho)))
    r0 = max(rb, rf)
    flank = [(rho, half(rho)) for rho in np.linspace(r0, ra, n_flank)]
    if rf < rb:
        flank = [(rf, half(rb))] + flank
    tip = [(ra, t) for t in np.linspace(-half(ra), half(ra), 4)[1:-1]]
    return [(rho, -t) for rho, t in flank] + tip + [(rho, t) for rho, t in reversed(flank)], rf


def gear_outline(z, phase_deg=0.0, centre=(0.0, 0.0), n_root=5):
    """Whole gear outline (shapely polygon). Tooth k is centred on phase_deg + k*360/z."""
    tooth, rf = _tooth_polar(z)
    pts = []
    for k in range(z):
        c = math.radians(phase_deg) + 2*math.pi*k/z
        pts += [(rho, c + t) for rho, t in tooth]
        a0, a1 = c + tooth[-1][1], c + 2*math.pi/z + tooth[0][1]
        pts += [(rf, t) for t in np.linspace(a0, a1, n_root + 2)[1:-1]]
    return Polygon([(centre[0] + rho*math.cos(t), centre[1] + rho*math.sin(t)) for rho, t in pts])


def tooth_polygons(z, phase_deg=0.0, depth=.6):
    """Each tooth as its own convex polygon (local gear frame), reaching depth below the root circle."""
    tooth, rf = _tooth_polar(z)
    out = []
    for k in range(z):
        c = math.radians(phase_deg) + 2*math.pi*k/z
        p = [(rho*math.cos(c + t), rho*math.sin(c + t)) for rho, t in tooth]
        p += [((rf - depth)*math.cos(c + tooth[-1][1]), (rf - depth)*math.sin(c + tooth[-1][1])),
              ((rf - depth)*math.cos(c + tooth[0][1]), (rf - depth)*math.sin(c + tooth[0][1]))]
        out.append(p)
    return out


def gear_solid(z, phase_deg, centre, z0, z1, bore_r):
    """Gear as a solid: involute flanks as splines through the exact points, tip and root as arcs (the same tooth as
    gear_outline, with a few hundred faces instead of thousands)."""
    tooth, rf = _tooth_polar(z)
    cx, cy = centre
    P = lambda rho, t: cq.Vector(cx + rho*math.cos(t), cy + rho*math.sin(t), z0)
    n = (len(tooth) - 2)//2
    edges = []

    def flank(seg):
        tail = None
        if abs(seg[0][1] - seg[1][1]) < 1e-12:           # radial line below the base circle (small pinions)
            edges.append(cq.Edge.makeLine(P(*seg[0]), P(*seg[1]))); seg = seg[1:]
        if abs(seg[-1][1] - seg[-2][1]) < 1e-12:
            tail, seg = seg[-2:], seg[:-1]
        edges.append(cq.Edge.makeSpline([P(*q) for q in seg]))
        if tail:
            edges.append(cq.Edge.makeLine(P(*tail[0]), P(*tail[1])))
    for k in range(z):
        c = math.radians(phase_deg) + 2*math.pi*k/z
        pts = [(rho, c + t) for rho, t in tooth]
        right, left = pts[:n], pts[n + 2:]
        flank(right)
        edges.append(cq.Edge.makeThreePointArc(P(*right[-1]), P(right[-1][0], (right[-1][1] + left[0][1])/2), P(*left[0])))
        flank(left)
        a0, a1 = left[-1][1], c + 2*math.pi/z + tooth[0][1]
        edges.append(cq.Edge.makeThreePointArc(P(rf, a0), P(rf, (a0 + a1)/2), P(rf, a1)))
    face = cq.Face.makeFromWires(cq.Wire.assembleEdges(edges), [cq.Wire.makeCircle(bore_r, cq.Vector(cx, cy, z0), cq.Vector(0, 0, 1))])
    return cq.Workplane(obj=cq.Solid.extrudeLinear(face, cq.Vector(0, 0, z1 - z0)))


RING_PHASE, PINION_PHASE = 0.0, 180.0/R3.ZP           # a ring tooth at 180°; the pinion shows a gap to the ring there


# ------------------------------------------------------------------ chassis side
@lru_cache(None)
def ring_gear():
    """X103: m1.5 x 80 on the X-frame top, bore Ø95.2 on the RU66 outer ring; 6 M3 insert holes from below."""
    rg = R3.RG
    s = gear_solid(R3.ZR, RING_PHASE, (0, 0), *rg['z'], rg['bore_r'])
    for a in rg['screw_ang']:
        s = s.cut(zcyl(rg['insert']['r'], rg['z'][0] - 1, rg['z'][0] + rg['insert']['depth'], *polar(rg['screw_r'], a)))
    return s.clean()


def rotor_dog():
    """T106 (R2's TPU dog): pressed on the slip ring's Ø7.8 rotor, two lugs that the T104 prongs pick up.
    Drawn on the rotor's diameter; printed with a Ø7.5 bore for the press fit."""
    d, rz = R2.DOG, R2.ROTOR_Z
    s = zcyl(d['r_out'], d['z0'], d['z1'])
    for a in (90.0, 270.0):
        lug = box(0, d['lug_r'], -d['lug_w']/2, d['lug_w']/2, d['lug_z0'], d['z1'])
        s = s.union(lug.rotate((0, 0, 0), (0, 0, 1), a))
    s = s.cut(zcyl(R2.ROTOR_R, d['z0'] - 1, rz[1]))
    s = s.cut(zcyl(d['hole_d']/2, rz[1] - .01, d['z1'] + 1))
    return s.clean()


def slip_ring():
    """Bought 6-way 2 A flanged slip ring (seller's drawing): stator below, flange against the collar, rotor up."""
    g, n = R2.RING, 6
    body = zcyl(R2.BODY_R, R2.END_Z[n], R2.FACE_Z)
    fl = zcyl(R2.FLANGE_R, *R2.FL_Z)
    for a in R2.HOLE_ANG:
        fl = fl.cut(zcyl(g['hole_d']/2, R2.FL_Z[0] - 1, R2.FL_Z[1] + 1, *polar(R2.PCD_R, a)))
    stator = body.union(fl).clean()
    rotor = zcyl(R2.ROTOR_R, *R2.ROTOR_Z)
    return stator, rotor


@lru_cache(None)
def chassis_side():
    """Fixed parts and hardware added to the chassis by the turntable (vehicle frame)."""
    out = {}
    def add(n, s, color, kind='hardware', source=None, group='lower'):
        out[n] = dict(shape=s, color=color, group=group, kind=kind, source=source)
    rg = R3.RG
    add('X103_ring_gear', ring_gear(), RING_C, 'printed', 'X103_ring_gear')
    for i, a in enumerate(rg['screw_ang']):
        x, y = polar(rg['screw_r'], a)
        z0 = X.TOP_Z - X.PLATE_T
        head = cq.Workplane(obj=cq.Solid.makeCone(CSK['r'], CSK['r'] - CSK['h'], CSK['h'], cq.Vector(x, y, z0), cq.Vector(0, 0, 1)))
        add(f'ring_gear_screw_M3x12_{i}', head.union(zcyl(1.5, z0 + CSK['h'] - .01, z0 + R3.RG_SCREW['L'], x, y)), X.BLACK)
        add(f'ring_gear_insert_M3_{i}', zring(INSERT_M3['r'], 1.5, rg['z'][0], rg['z'][0] + INSERT_M3['length'], x, y), BRASS)
    stator, rotor = slip_ring()
    add('slip_ring_6way_stator', stator, SLIP_C)
    add('slip_ring_6way_rotor', rotor, SLIP_C, group='rotor')
    add('T106_rotor_dog_TPU', rotor_dog(), TPU_C, 'printed', 'T106_rotor_dog_TPU', group='rotor')
    for i, a in enumerate(X.COLLAR['insert_ang']):
        x, y = polar(X.COLLAR['insert_r'], a)
        z0 = X.COLLAR['z'][0]
        add(f'collar_insert_M3_{i}', zring(INSERT_M3['r'], 1.5, z0, z0 + INSERT_M3['length'], x, y), BRASS)
        wz = (R2.FL_Z[0] - WASHER_M3['t'], R2.FL_Z[0])
        add(f'slip_ring_washer_M3_{i}', zring(WASHER_M3['ro'], WASHER_M3['ri'], *wz, x, y), STEEL)
        add(f'slip_ring_screw_M3x8_{i}', X.screw_z(1.5, M3_HEAD, wz[0], R2.SCREW['L'], x, y, 1), BLACK)
    return out


# ------------------------------------------------------------------ upper: printed parts
@lru_cache(None)
def hub_adapter():
    """T104: Ø59 x 3 flange on the RU66 inner ring, Ø34.6 spigot in its bore, two prongs that drive the slip ring's dog."""
    t = R3.T104
    s = zring(t['r_out'], t['r_in'], *t['z']).union(zring(t['spigot_r'], t['r_in'], t['spigot_z0'], t['z'][0] + .01))
    pr = t['prong']
    for a in (0.0, 180.0):
        h = math.radians(pr['width_deg']/2)
        arc = [(pr['ro']*math.cos(math.radians(a) + u), pr['ro']*math.sin(math.radians(a) + u)) for u in np.linspace(-h, h, 24)]
        arc += [(pr['ri']*math.cos(math.radians(a) + u), pr['ri']*math.sin(math.radians(a) + u)) for u in np.linspace(h, -h, 24)]
        s = s.union(xy_prism(Polygon(arc), pr['z0'], t['spigot_z0'] + .01))
    for r, a in R3.TH_HUB:
        s = s.cut(zcyl(t['hole_r'], t['z'][0] - 1, t['z'][1] + 1, *polar(r, a)))
    return s.clean()


@lru_cache(None)
def centre_frame():
    """T101: base plate (Z 103-109) with the hub hole and the motor opening; ribs, bulkheads and hub well to Z 136;
    drag-pad housings to Z 124. Holes and pockets as on sheet 2."""
    bz, top = R3.BASE_Z, R3.TOPZ
    s = prism(R3.frame_base(), *bz)
    s = s.union(prism(R3.frame_walls(pads=False), bz[1] - .01, top))
    pad = R3.PAD
    for x, y in R3.PAD_XY:
        s = s.union(zcyl(pad['housing_r'], bz[1] - .01, pad['top'], x, y))
    # hub screws, slide-clamp inserts, drag-pad bores (lip at the bottom, the M6 insert hole is the bore itself)
    for r, a in R3.TH_HUB:
        s = s.cut(zcyl(2.25, bz[0] - 1, bz[1] + 1, *polar(r, a)))
    for x, y in R3.SLIDE['slots']:
        for sy in (1, -1):
            s = s.cut(zcyl(INSERT_M3['r'], bz[1] - INSERT_M3['length'], bz[1] + 1, x, sy*y))
    for x, y in R3.PAD_XY:
        s = s.cut(zcyl(pad['lip_r'], bz[0] - 1, pad['lip'][1] + .01, x, y))
        s = s.cut(zcyl(pad['bore_r'], pad['lip'][1], pad['top'] + 1, x, y))
    # ARM60 base bolts: Ø6.6 through the blocks, M6 nut pockets open inboard
    blk = R3.ARM_BLOCK
    for x, y in R3.ARM_BOLTS:
        sy = np.sign(y)
        s = s.cut(zcyl(3.3, bz[0] - 1, top + 1, x, y))
        y0, y1 = sorted([sy*(blk['y'][0] - 1), y + sy*5.9])
        s = s.cut(box(x - 5.1, x + 5.1, y0, y1, *blk['nut_z']))
    # push-screw lugs: M3 inserts along X, entered from the lug's front face
    lug = R3.LUG
    for sy in (1, -1):
        yc = sy*sum(lug['y'])/2
        s = s.cut(tp.xcyl(INSERT_M3['r'], lug['x'][1] - INSERT_M3['length'], lug['x'][1] + 1, yc, lug['screw_z']))
        s = s.cut(tp.xcyl(1.7, lug['x'][0] - 1, lug['x'][1], yc, lug['screw_z']))
    # rib tops: M3 inserts for the body halves' sleeve screws (x1_body.py), 2.5 deeper than the insert for the screw tip
    for x in BODY_SLEEVE_X:
        for sy in (1, -1):
            s = s.cut(zcyl(INSERT_M3['r'], top - INSERT_M3['length'] - 2.5, top + 1, x, sy*sum(R3.RIB_Y)/2))
    # rear bulkhead: window for the motor's lead end, two M4 holes for the counterweight
    rb = R3.REAR_BULK
    s = s.cut(tp.xcyl(R3.WINDOW_R, rb[0] - 1, rb[1] + 1, 0, CAN_Z))
    for sy in (1, -1):
        s = s.cut(tp.xcyl(2.25, rb[0] - 1, rb[1] + 1, sy*40.0, CAN_Z))
    return s.clean()


@lru_cache(None)
def motor_slide():
    """T102 in its set position: body in the opening, ears on the base plate, slots for the clamp screws;
    4 gearbox screws from below (ISO 7380 heads in counterbores), pockets for the gearbox's screw bosses."""
    sl, dx = R3.SLIDE, DX_SET
    x0, x1 = sl['x'][0] + dx, sl['x'][1] + dx
    s = box(x0, x1, -sl['y'], sl['y'], *sl['z'])
    for sy in (1, -1):
        y0, y1 = sorted([sy*(sl['ear_y'][0] - .5), sy*sl['ear_y'][1]])        # overlaps the body by 0.5 in Y, sits on the plate
        s = s.union(box(x0, x1, y0, y1, sl['ear_z'][0], sl['ear_z'][1]))
    s = s.cut(zcyl(sl['hole_r'], sl['z'][0] - 1, sl['z'][1] + 1, PXS, 0))
    for x, y in R3.SLIDE['slots']:
        for sy in (1, -1):
            slot = cq.Workplane('XY').slot2D(sl['slot_len'], 3.4).extrude(sl['ear_z'][1] - sl['ear_z'][0] + 2)
            s = s.cut(slot.translate((x + dx, sy*y, sl['ear_z'][0] - 1)))
    cb, bp = sl['cb'], sl['boss_pocket']
    for hx, hy in R3.MOTOR['holes']:
        hx += dx
        s = s.cut(zcyl(1.7, sl['z'][0] - 1, sl['z'][1] + 1, hx, hy))
        s = s.cut(zcyl(cb[0], sl['z'][0] - 1, sl['z'][0] + cb[1], hx, hy))
        s = s.cut(zcyl(bp[0], sl['z'][1] - bp[1], sl['z'][1] + 1, hx, hy))
    return s.clean()


def plunger(x, y):
    """T103: head Ø7.6 x 4 in the Ø8 bore, stem Ø6.4 through the Ø6.8 lip; felt glued on the stem's end."""
    p = R3.PAD
    return zcyl(p['head_r'], *p['head'], x, y).union(zcyl(p['stem_r'], p['felt'][1], p['head'][0] + .01, x, y)).clean()


@lru_cache(None)
def pinion_shape():
    """T105: m1.5 x 20, 10 wide, on the Pololu hub with 4 x M3 x 10 from below (heads in counterbores)."""
    z0, z1 = R3.PIN_Z
    s = gear_solid(R3.ZP, PINION_PHASE, (PXS, 0), z0, z1, 3.5)
    for a in PINION_SCREW_ANG:
        x, y = polar(HUB_PCD_R, a); x += PXS
        s = s.cut(zcyl(1.7, z0 - 1, z1 + 1, x, y)).cut(zcyl(3.1, z0 - 1, z0 + 3.2, x, y))
    return s.clean()


HUB_PCD_R = D9.HUB['pcd_r']                            # 9.525
HUB_HOLE_ANG = [60.0*k for k in range(6)]              # the hub's 6 tapped holes; its set screws point to -Y, between two holes
PINION_SCREW_ANG = [0.0, 60.0, 180.0, 240.0]           # 4 of them carry the pinion


# ------------------------------------------------------------------ upper: bought parts in the swing pose
def _place(s):
    """J9 motor frame -> swing pose: shaft (J9 +Y) points down, can (J9 +X) to the rear, gearbox face at Z 109.
    The rotation x -> -x, y -> -z, z -> -y is a half turn about the axis (0, 1, -1)."""
    p0 = (D9.DRIVE_X, D9.GEARBOX_FACE_Y, D9.AXLE_Z)
    return s.translate((-p0[0], -p0[1], -p0[2])).rotate((0, 0, 0), (0, 1, -1), 180).translate((PXS, 0, R3.GB_FACE))


def motor_parts():
    """JGY-370-1260 from J9's model, in the swing pose. The lead space replaces J9's 10 mm terminal envelope: Ø24 up to the
    rear bulkhead, then Ø18 through its Ø20 window."""
    m = P9.jgy370()
    can_end = PXS - C.CAN_END
    rb = R3.REAR_BULK
    lead = tp.xcyl(12.0, rb[1] + .3, can_end, 0, CAN_Z).union(tp.xcyl(9.0, can_end - 10.0, rb[1] + .31, 0, CAN_Z))
    return dict(gearbox=_place(m['gearbox']), can=_place(m['can']), shaft=_place(m['shaft']), leads=lead)


def pololu_hub():
    """Pololu #1999 on the motor shaft, flange face down on the pinion (Z 97), boss up."""
    h, (z0, z1, z2) = D9.HUB, R3.HUB_Z
    s = zcyl(h['flange_r'], z0, z1, PXS, 0).union(zcyl(h['boss_r'], z1 - .01, z2, PXS, 0))
    s = s.cut(zcyl(h['bore_r'], z0 - 1, z2 + 1, PXS, 0))
    for a in HUB_HOLE_ANG:
        x, y = polar(HUB_PCD_R, a)
        s = s.cut(zcyl(1.5, z0 - 1, z1 + 1, PXS + x, y))
    for depth, _ in D9.HUB_SET_SCREWS:
        s = s.cut(tp.ycyl(1.5, -h['flange_r'] - 1, 0, PXS, z0 + depth))
    return s.clean()


def hub_set_screws():
    """M3 cup-point set screws (ISO 4029: 45° chamfer to the Ø1.4 cup) on the shaft's flat, which faces -Y in this
    pose. The boss screw's cup lands 1.3 mm short of the flat's end (the hub sits 4.2 mm further up the shaft than on J9)."""
    out = []
    for depth, length in D9.HUB_SET_SCREWS:
        y0, z = -(D9.SHAFT_FLAT['across'] - 3.0), R3.HUB_Z[0] + depth
        body = tp.ycyl(1.5, y0 - length, y0 - .8, PXS, z)
        cone = cq.Workplane(obj=cq.Solid.makeCone(1.5, .7, .8, cq.Vector(PXS, y0 - .8, z), cq.Vector(0, 1, 0)))
        out.append(body.union(cone))
    return out


@lru_cache(None)
def upper_parts():
    """Every solid that turns with the upper, at swing 0 (pinion group: turns about the pinion axis as well)."""
    out = {}
    def add(n, s, color, kind='hardware', source=None, group='upper'):
        out[n] = dict(shape=s, color=color, group=group, kind=kind, source=source)
    add('T101_centre_frame', centre_frame(), UPPER_C, 'printed', 'T101_centre_frame')
    add('T104_hub_adapter', hub_adapter(), UPPER_C, 'printed', 'T104_hub_adapter')
    add('T102_motor_slide', motor_slide(), SLIDE_C, 'printed', 'T102_motor_slide')
    # hub joint: 8 x M4 x 20, DIN 6796 on a Ø12 DIN 9021, into the RU66 inner ring
    bz, st = R3.BASE_Z, X.SEAT_STACK
    for i, (r, a) in enumerate(R3.TH_HUB):
        x, y = polar(r, a)
        wz = (bz[1], bz[1] + st['washer'][2]); dz = (wz[1], wz[1] + st['disc'][2])
        add(f'hub_washer_12_{i}', zring(st['washer'][0], st['washer'][1], *wz, x, y), STEEL)
        add(f'hub_disc_spring_{i}', zring(st['disc'][0], st['disc'][1], *dz, x, y), STEEL)
        add(f'hub_screw_M4x20_{i}', X.screw_z(2.0, M4_HEAD, dz[1], R3.TOP_SCREW['L'], x, y, -1), BLACK)
    # motor on the slide
    mp = motor_parts()
    add('JGY370_gearbox', mp['gearbox'], P9.GEARBOX_C)
    add('JGY370_motor_can', mp['can'], P9.MOTOR_C)
    add('JGY370_lead_space', mp['leads'], (.75, .55, .35), kind='envelope')
    sl = R3.SLIDE
    for i, (hx, hy) in enumerate(R3.MOTOR['holes']):
        z0 = sl['z'][0] + sl['cb'][1]
        add(f'motor_screw_M3x8_button_{i}', X.screw_z(1.5, M3_BUTTON, z0, 8.0, hx + DX_SET, hy, 1), BLACK)
    # slide clamps: M3 x 12 + washer into inserts in the base plate
    for i, (x, y) in enumerate([(x, sy*y) for x, y in sl['slots'] for sy in (1, -1)]):
        add(f'slide_insert_M3_{i}', zring(INSERT_M3['r'], 1.5, bz[1] - INSERT_M3['length'], bz[1], x, y), BRASS)
        wz = (sl['ear_z'][1], sl['ear_z'][1] + WASHER_M3['t'])
        add(f'slide_washer_M3_{i}', zring(WASHER_M3['ro'], WASHER_M3['ri'], *wz, x, y), STEEL)          # on the inserts, through the slots
        add(f'slide_clamp_screw_M3x12_{i}', X.screw_z(1.5, M3_HEAD, wz[1], 12.0, x, y, -1), BLACK)
    # push screws behind the ears: M3 x 12 in inserts in the lugs, tips on the ears, lock nuts on the lugs' front faces
    lug = R3.LUG
    for i, sy in enumerate((1, -1)):
        yc, zc = sy*sum(lug['y'])/2, lug['screw_z']
        tip = sl['x'][0] + DX_SET
        add(f'lug_insert_M3_{i}', tp.xring(INSERT_M3['r'], 1.5, lug['x'][1] - INSERT_M3['length'], lug['x'][1], yc, zc), BRASS)
        add(f'push_screw_M3x12_{i}', tp.xcyl(1.5, tip - 12.0, tip, yc, zc).union(tp.xcyl(M3_HEAD['r'], tip - 12.0 - M3_HEAD['h'], tip - 12.0 + .01, yc, zc)), BLACK)
        add(f'push_nut_M3_{i}', tp.xhex(5.5, lug['x'][1], lug['x'][1] + 2.4, yc, zc).cut(tp.xcyl(1.5, lug['x'][1] - 1, lug['x'][1] + 3.4, yc, zc)), BLACK)
    # drag pads
    p = R3.PAD
    for i, (x, y) in enumerate(R3.PAD_XY):
        add(f'T103_drag_plunger_{i}', plunger(x, y), SLIDE_C, 'printed', 'T103_drag_plunger')
        add(f'drag_felt_{i}', zcyl(p['felt_r'], *p['felt'], x, y), FELT_C)
        sp = p['spring']                                  # Ø4.5: fitted through the insert's M6 thread after the insert
        add(f'drag_spring_{i}', zring(sp['od']/2, sp['od']/2 - sp['wire'], p['head'][1], p['screw_tip'], x, y), SPRING_C)
        add(f'drag_insert_M6_{i}', zring(p['insert']['r'], 3.0, p['top'] - p['insert']['length'], p['top'], x, y), BRASS)
        add(f'drag_set_screw_M6x8_{i}', zcyl(3.0, p['screw_tip'], p['top'], x, y), BLACK)
    # ARM60 base bolts: M6 x 40 from above, nuts in the pockets
    for i, (x, y) in enumerate(R3.ARM_BOLTS):
        zt = R3.TOPZ + R3.ARM_BASE['t']
        add(f'arm_bolt_M6x40_{i}', zcyl(3.0, zt - 40.0, zt + .01, x, y).union(zcyl(M6_HEAD['r'], zt, zt + M6_HEAD['h'], x, y)), BLACK)
        nz = R3.ARM_BLOCK['nut_z']
        nut = tp.zhex(10.0, nz[0] + .25, nz[0] + 5.25, x, y).rotate((x, y, 0), (x, y, 1), 30)   # flats on the pocket walls
        add(f'arm_nut_M6_{i}', nut.cut(zcyl(3.0, nz[0], nz[1], x, y)), BLACK)
    # pinion group: turns about the pinion axis
    add('T105_pinion', pinion_shape(), UPPER_C, 'printed', 'T105_pinion', group='pinion')
    add('Pololu_1999_hub', pololu_hub(), HUB_C, group='pinion')
    add('JGY370_output_shaft', mp['shaft'], STEEL, group='pinion')
    for i, s in enumerate(hub_set_screws()):
        add(f'hub_set_screw_{i}', s, BLACK, group='pinion')
    for i, a in enumerate(PINION_SCREW_ANG):
        x, y = polar(HUB_PCD_R, a)
        add(f'pinion_screw_M3x10_{i}', X.screw_z(1.5, M3_HEAD, R3.PIN_Z[0] + 3.2, 10.0, PXS + x, y, 1), BLACK, group='pinion')
    return out


@lru_cache(None)
def arm60():
    """The existing ARM60 (excavator_arm_60mm STEP, as exported: arm stretched forward), on the rib tops.
    Returns (base, rest): the fixed pivot base and every other solid as one compound."""
    step = REPO / 'excavator_arm_60mm/step'
    base = cq.importers.importStep(str(step / '01_fixed_pivot_base.step'))
    allp = cq.importers.importStep(str(step / 'excavator_arm_assembly.step')).solids().vals()
    bb = tp.one(base).BoundingBox()
    def is_base(s):
        b = s.BoundingBox()
        return abs(b.xmin - bb.xmin) < .01 and abs(b.xmax - bb.xmax) < .01 and abs(b.zmax - bb.zmax) < .01 and abs(s.Volume() - tp.one(base).Volume()) < 1
    rest = [s for s in allp if not is_base(s)]
    assert len(rest) == len(allp) - 1, 'ARM60 base not found in the assembly STEP'
    mv = (R3.ARM_X0, 0, R3.TOPZ)
    return base.translate(mv), cq.Workplane(obj=cq.Compound.makeCompound(rest)).translate(mv), len(rest)


def turntable(swing_deg=0.0, with_arm=True, slide_dx=0.0, upper_dz=0.0):
    """Every turntable solid in the vehicle frame, the upper turned by swing_deg (the pinion by RATIO x that,
    relative to the upper). slide_dx / upper_dz move the motor group / whole upper for assembly-path checks."""
    out = dict(chassis_side())
    up = dict(upper_parts())
    if with_arm:
        base, rest, _ = arm60()
        up['ARM60_fixed_pivot_base'] = dict(shape=base, color=ARM_C, group='arm', kind='existing', source='excavator_arm_60mm')
        up['ARM60_arm_and_actuators'] = dict(shape=rest, color=ARM_C, group='arm', kind='existing', source='excavator_arm_60mm')
    rot = RATIO*swing_deg
    for n, d in up.items():
        s = d['shape']
        if d['group'] == 'pinion':
            s = s.rotate((PXS, 0, 0), (PXS, 0, 1), rot)
        if slide_dx and (d['group'] == 'pinion' or n.startswith(('T102', 'JGY370', 'motor_screw'))):
            s = s.translate((slide_dx, 0, 0))
        if upper_dz:
            s = s.translate((0, 0, upper_dz))
        if swing_deg:
            s = s.rotate((0, 0, 0), (0, 0, 1), swing_deg)
        out[n] = {**d, 'shape': s}
    if swing_deg:                                      # the rotor dog follows the prongs (it lags inside its free play)
        for n in ('slip_ring_6way_rotor', 'T106_rotor_dog_TPU'):
            out[n] = {**out[n], 'shape': out[n]['shape'].rotate((0, 0, 0), (0, 0, 1), swing_deg)}
    return out


PRINTED = {   # name: (quantity, material, print orientation (axis, deg, note), note)
    'T101_centre_frame': (1, 'PETG, 4 walls, 30 % infill; solid within 10 mm of every bolt', ((1, 0, 0), 0, 'base plate down; no supports'),
                          'Upper frame: two 8 x 27 ribs carry the ARM60 base (4 x M6 into nut pockets) over the bearing; hub well, '
                          'motor opening, drag-pad housings, push-screw lugs, rear bulkhead with a Ø20 lead window and 2 M4 holes for the '
                          'counterweight; 4 M3 inserts in the rib tops for the body halves.'),
    'T102_motor_slide': (1, 'PETG, 100 % infill', ((1, 0, 0), 0, 'body down, ears up'),
                         'Carries the JGY-370 (4 x M3 x 8 button head from below); slides ±2 in the opening to set the mesh.'),
    'T103_drag_plunger': (2, 'PETG, 100 % infill', ((1, 0, 0), 180, 'head down'),
                          'Spring-loaded plunger; Ø8 x 3 felt glued on its end presses on the ring gear top.'),
    'T104_hub_adapter': (1, 'PETG, 100 % infill', ((1, 0, 0), 180, 'flange face down; spigot and prongs grow upwards'),
                         'Flange on the RU66 inner ring (clamped with T101 by 8 x M4 x 20); spigot in the bore; prongs drive the slip-ring dog.'),
    'T105_pinion': (1, 'PETG or PA12, 100 % infill', ((1, 0, 0), 0, 'flat'),
                    'm1.5 x 20, 10 wide; 4 x M3 x 10 into the Pololu hub.'),
    'X103_ring_gear': (1, 'PETG or PA12, 100 % infill', ((1, 0, 0), 180, 'top face (drag track) on the bed'),
                       'm1.5 x 80 on the X-frame top, centred on the RU66 outer ring (bore Ø95.2); 6 M3 inserts from below.'),
    'T106_rotor_dog_TPU': (1, 'TPU 95A', ((1, 0, 0), 180, 'top web down'),
                           "R2's dog: pressed on the slip ring's rotor (print the bore Ø7.5); two lugs for the T104 prongs."),
}


def printed_parts():
    shapes = {'T101_centre_frame': centre_frame(), 'T102_motor_slide': motor_slide(), 'T103_drag_plunger': plunger(0, 0),
              'T104_hub_adapter': hub_adapter(), 'T105_pinion': pinion_shape().translate((-PXS, 0, 0)),
              'X103_ring_gear': ring_gear(), 'T106_rotor_dog_TPU': rotor_dog()}
    return {n: dict(shape=shapes[n], quantity=q, material=mat, print=pr, note=note) for n, (q, mat, pr, note) in PRINTED.items()}

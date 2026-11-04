"""R12 concept: real excavator geometry (Cat 325 pins from US 6,518,519, Cat 320 outlines from the
manufacturer render, both normalised to Cat 320 at 1:15) with four identical V6-U60 drives.

Structural pins (O, E, H, side-link pivot J, both link lengths, bucket link pin Q) and the visible
cylinder ends (boom rod pin B, stick-cylinder base C on the boom top, bucket-cylinder base F on the
stick) follow the reference. Only what the 60 mm stroke forces is moved: the boom-cylinder base A
(hidden in the foot bracket) and the stick tail D (shortened). Each deviation is listed in DEVIATIONS.

Frames: world X forward / Z up at the boom-foot pin O; boom x along O->E; stick x along
E->H, +z outer face; bucket x along H->T, +z back of the bucket (mouth faces -z).
"""
import math
import functools
import numpy as np
from shapely.geometry import Point, Polygon, LineString, box
from shapely.ops import unary_union
from shapely import affinity
import reference_cat as rc
import bucket_ref as BREF

SCALE = 15.0
BOOM, STICK, TIP_R, BUCKET_W = rc.BOOM, rc.STICK, rc.TIP_R, 1200 / SCALE
TURNTABLE_Z, GROUND_Z, SWING_X = -55.0, -155.0, -30.0
ACT = dict(name='V6-U60', closed=140.0, stroke=60.0, open=200.0, eye_r=4.5, cap_s=6.0, body_end_s=122.5, body_half=8.05,
           body_board=9.75, body_back=6.35, body_half_y=7.35,
           rod_r=4.0, socket_r=5.5, socket_s=(4.0, 14.5), eye_t=6.0, boss_r=3.6, thrust_cont=51.0, thrust_stall=201.0, mass_barrel=0.051, barrel_cg_s=75.6, mass_rod=0.006,
           rod_cg_s=129.9)
RHO, T_WALL, PAYLOAD = 1.27e-6, 2.5, 0.150
PRINT_INFILL = 0.10                  # boxes print as 6 perimeters (2.5 mm) + 10 % gyroid infill
WIDTH = dict(boom=40.0, stick=32.0)

O = np.zeros(2)
E_B = np.array([BOOM, 0.0])
H_S = np.array([STICK, 0.0])
T_K = np.array([TIP_R, 0.0])
P = rc.REF_PINS

# --- choices (see concept sheet): ranges at 140 / 200 mm between pins
BOOM_RANGE_DEG = (-35.0, 50.0)
STICK_RANGE_DEG = (-35.0, -125.0)
STICK_TAIL = 43.0                                  # |E-D|; reference 50.3
STICK_TAIL_TURN = -17.0                            # deg, turned from the reference direction toward the stick
B_B = P['B_boom'].copy()                           # reference
J_S = P['J_stick'].copy()                          # reference
SIDE_LINK, H_LINK = rc.REF_LINKS['side_link'], rc.REF_LINKS['h_link']
EAR = float(P['Q_bucket'][1])
EAR_BETA = math.radians(90.0)                      # reference: Q perpendicular to the tip line, at the back
Q_K = EAR * np.array([math.cos(EAR_BETA), math.sin(EAR_BETA)])


def rot(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s], [s, c]])


def circ(p0, r0, p1, r1, side):
    d = float(np.linalg.norm(p1 - p0))
    if d > r0 + r1 or d < abs(r0 - r1) or d == 0:
        return None
    a = (r0 * r0 - r1 * r1 + d * d) / (2 * d)
    h = math.sqrt(max(r0 * r0 - a * a, 0.0))
    u = (p1 - p0) / d
    return p0 + a * u + side * h * np.array([-u[1], u[0]])


def disc(p, r):
    return Point(float(p[0]), float(p[1])).buffer(r, 64)


def place(g, origin, angle):
    return affinity.translate(affinity.rotate(g, math.degrees(angle), origin=(0, 0)), float(origin[0]), float(origin[1]))


def to_world(p, origin, angle):
    return np.asarray(origin, float) + rot(angle) @ np.asarray(p, float)


# --- derived cylinder pins
def _base_for(moving_at_lo, moving_at_hi, pick):
    c = [circ(moving_at_lo, ACT['closed'], moving_at_hi, ACT['open'], s) for s in (1, -1)]
    return pick([x for x in c if x is not None])


_lo, _hi = map(math.radians, BOOM_RANGE_DEG)
A_W = _base_for(rot(_lo) @ B_B, rot(_hi) @ B_B, lambda c: min(c, key=lambda p: p[1]))
_ad = math.atan2(P['D_stick'][1], P['D_stick'][0])
_ad += math.radians(STICK_TAIL_TURN)
D_S = STICK_TAIL * np.array([math.cos(_ad), math.sin(_ad)])
_slo, _shi = map(math.radians, STICK_RANGE_DEG)
C_B = _base_for(E_B + rot(_slo) @ D_S, E_B + rot(_shi) @ D_S, lambda c: min(c, key=lambda p: np.linalg.norm(p - P['C_boom'])))


BUCKET_MIN_TRANSMISSION = 30.0       # deg, at Q (H-link / ear) and at R (cylinder / side link)


def _acute(a, b):
    return math.degrees(math.acos(min(1.0, abs(float(a @ b) / (np.linalg.norm(a) * np.linalg.norm(b))))))


def bucket_sweep(F, n=31):
    """Bucket angles over the stroke and the worst transmission angles, or None if it locks."""
    g, mu = [], []
    for L in np.linspace(ACT['closed'], ACT['open'], n):
        R = circ(F, L, J_S, SIDE_LINK, +1)
        Q = None if R is None else circ(R, H_LINK, H_S, EAR, +1)
        if Q is None:
            return None
        g.append(math.atan2(*(Q - H_S)[::-1]) - EAR_BETA)
        mu.append(min(_acute(Q - R, Q - H_S), _acute(R - F, R - J_S)))
    g = np.unwrap(g)
    if np.any(np.diff(g) >= 0):
        return None
    return g, min(mu)


BUCKET_CYL_CLEARANCE = 1.5           # mm, drive body to the stick over the whole stroke


def bucket_cyl_clearance(F, sb=None):
    sb = sb if sb is not None else stick_base()
    worst = 1e9
    for L in np.linspace(ACT['closed'], ACT['open'], 13):
        R = circ(F, L, J_S, SIDE_LINK, +1)
        worst = min(worst, actuator_body(F, R).distance(sb))
    return worst


def _bucket_base():
    """Bucket-cylinder base above the stick outer face near the reference F: the widest bucket
    range with both transmission angles >= BUCKET_MIN_TRANSMISSION and the drive body clear of
    the stick by BUCKET_CYL_CLEARANCE."""
    cands = []
    for u in np.arange(-30.0, 40.0, 0.5):
        for v in np.arange(30.0, 64.0, 0.5):
            r = bucket_sweep(np.array([u, v]))
            if r is not None and r[1] >= BUCKET_MIN_TRANSMISSION:
                cands.append((math.degrees(r[0][0] - r[0][-1]), u, v))
    sb = stick_base()
    for rng, u, v in sorted(cands, reverse=True):
        if bucket_cyl_clearance(np.array([u, v]), sb) >= BUCKET_CYL_CLEARANCE:
            return np.array([u, v])
    raise RuntimeError('no bucket-cylinder base found')


F_S = np.array([12.0, 44.0])           # placeholder, replaced by the search below at import


# --- kinematics
def _angle(anchor, moving, length, target):
    a, b = np.linalg.norm(anchor), np.linalg.norm(moving)
    c = (a * a + b * b - length * length) / (2 * a * b)
    if not -1 <= c <= 1:
        raise ValueError('cylinder cannot reach')
    best = None
    for br in (1, -1):
        x = math.atan2(anchor[1], anchor[0]) - math.atan2(moving[1], moving[0]) + br * math.acos(c)
        x = (x - target + math.pi) % (2 * math.pi) - math.pi + target
        if best is None or abs(x - target) < abs(best - target):
            best = x
    return best


def solve(strokes):
    sb, ss, sk = strokes
    lb, ls, lk = (ACT['closed'] + s for s in strokes)
    th = _angle(A_W, B_B, lb, math.radians(BOOM_RANGE_DEG[0] + sb / 60 * (BOOM_RANGE_DEG[1] - BOOM_RANGE_DEG[0])))
    ph = _angle(C_B - E_B, D_S, ls, math.radians(STICK_RANGE_DEG[0] + ss / 60 * (STICK_RANGE_DEG[1] - STICK_RANGE_DEG[0])))
    R = circ(F_S, lk, J_S, SIDE_LINK, +1)
    Q = circ(R, H_LINK, H_S, EAR, +1)
    gm = math.atan2(*(Q - H_S)[::-1]) - EAR_BETA
    e = to_world(E_B, O, th)
    st = th + ph
    h = to_world(H_S, e, st)
    bk = st + gm
    p = dict(O=O.copy(), A=A_W.copy(), B=to_world(B_B, O, th), C=to_world(C_B, O, th), E=e, D=to_world(D_S, e, st),
             F=to_world(F_S, e, st), J=to_world(J_S, e, st), R=to_world(R, e, st), H=h, Q=to_world(Q, e, st),
             T=to_world(T_K, h, bk))
    sl = math.atan2(*(p['R'] - p['J'])[::-1])
    hl = math.atan2(*(p['Q'] - p['R'])[::-1])
    return dict(theta=th, phi=ph, gamma=gm, pins=p, R_s=R, Q_s=Q,
                poses=dict(boom=(O, th), stick=(e, st), bucket=(h, bk), side_link=(p['J'], sl), h_link=(p['R'], hl)))


# --- outlines from the trace, cleaned of pipes, hoses and bosses
def _chaikin(poly, n=3):
    xy = np.asarray(poly.exterior.coords)[:-1]
    for _ in range(n):
        nxt = np.roll(xy, -1, axis=0)
        xy = np.stack([0.75 * xy + 0.25 * nxt, 0.25 * xy + 0.75 * nxt], 1).reshape(-1, 2)
    return Polygon(xy)


def _clean(poly, r_open=2.5, r_close=4.0):
    """Remove pipes, hoses and pixel noise from a traced outline, then smooth it."""
    g = poly.buffer(-r_open, 32).buffer(r_open, 32)
    g = g.buffer(r_close, 32).buffer(-r_close, 32)
    if g.geom_type == 'MultiPolygon':
        g = max(g.geoms, key=lambda x: x.area)
    return _chaikin(g.simplify(1.2), 3).buffer(0)


def _fair(poly, xa, xb, sigma, step=1.0):
    """Fair a traced outline: upper and lower edge sampled every `step` mm between xa and xb,
    Gaussian-smoothed (sigma in mm). Removes handrails, decals and render noise; keeps the shape."""
    from scipy.ndimage import gaussian_filter1d
    xs = np.arange(xa, xb + step / 2, step)
    top, bot = [], []
    for x in xs:
        b = LineString([(x, -500), (x, 500)]).intersection(poly).bounds
        top.append(b[3])
        bot.append(b[1])
    top = gaussian_filter1d(np.array(top), sigma / step, mode='nearest')
    bot = gaussian_filter1d(np.array(bot), sigma / step, mode='nearest')
    return Polygon(list(zip(xs, top)) + list(zip(xs[::-1], bot[::-1])))


BOOM_FAIR_SIGMA, STICK_FAIR_SIGMA = 7.0, 10.0      # mm


_T = rc.load_traced()


@functools.lru_cache(maxsize=None)
def boom_profile():
    tr = _fair(_clean(Polygon(_T['boom'])), 0.0, BOOM - 22, BOOM_FAIR_SIGMA)   # nose rebuilt round E
    nose = unary_union([disc(E_B, 14.0), tr.intersection(box(BOOM - 40, -100, BOOM, 200))])
    foot = unary_union([disc(O, 14.0), tr.intersection(box(0.0, -100, 10.0, 200))]).convex_hull
    g = unary_union([tr, nose.convex_hull, foot]).buffer(1.5, 32).buffer(-1.5, 32)
    return g


@functools.lru_cache(maxsize=None)
def c_bracket():
    top = boom_profile()
    base = LineString([(C_B[0] - 16, 120), (C_B[0] - 16, -50)]).intersection(top)
    return unary_union([disc(C_B, 7.5), Polygon([(C_B[0] - 12, C_B[1]), (C_B[0] + 12, C_B[1]),
                                                (C_B[0] + 16, C_B[1] - 16), (C_B[0] - 16, C_B[1] - 16)])]).convex_hull


STICK_FACE = ((-2.0, 36.5), (80.0, 25.0))   # outer face line over the head, reference lug removed


@functools.lru_cache(maxsize=None)
def stick_base():
    """Traced stick without the reference tail and bucket-cylinder lug; tail rebuilt round D."""
    tr = _clean(Polygon(_T['stick']), 2.0, 3.0)
    (u0, v0), (u1, v1) = STICK_FACE
    tr = tr.difference(Polygon([(u0, v0), (u1, v1), (u1, 120), (u0, 120)]))
    tr = _fair(tr, -10.0, STICK - 10.0, STICK_FAIR_SIGMA)
    tail = unary_union([disc(D_S, 7.5), disc(np.zeros(2), 15.0), Point(-8.0, 34.0).buffer(2.0)]).convex_hull
    nose = unary_union([disc(H_S, 11.0), tr.intersection(box(STICK - 24, -60, STICK, 60))]).convex_hull
    g = unary_union([tr, tail, nose, disc(J_S, 7.0)])
    return g.buffer(1.5, 32).buffer(-1.5, 32)


@functools.lru_cache(maxsize=None)
def f_lug():
    (u0, v0), (u1, v1) = STICK_FACE
    foot = lambda u: v0 + (v1 - v0) * (u - u0) / (u1 - u0)
    return Polygon([F_S + np.array([-7.0, 0.0]), F_S + np.array([5.0, -4.0]), (F_S[0] + 6.0, foot(F_S[0] + 6.0) - 2.0),
                    (F_S[0] - 13.0, foot(F_S[0] - 13.0) - 2.0)]).union(disc(F_S, 7.0))


def stick_profile():
    return unary_union([stick_base(), f_lug()]), Polygon(_T['stick'])


# ------------------------------------------------------------------ bucket, Rev. D4
# A copy of a real bucket: Caterpillar US 8,201,350 B2, Example 1 (bucket_ref.py). Its tip radius
# (1570 mm) is R12's, so it is used at 1:15 with H on the patent's upper pin bore and T on its
# tooth tip.
#  * One wrapper plate runs from the cutting edge along the floor, round the heel (R1 985 over 30
#    deg, R2 370 over 130 deg) and back up as the support plate. The support plate ends beside H
#    at the top of the mouth.
#  * The mouth is open from the cutting edge to that front end, just behind the H-T line.
#  * Two side plates close the ends. Their front edge runs straight from the support-plate front end
#    to the floor.
#  * Hinge plates (ears) carry H and Q. A torque tube between them stiffens the support plate and
#    carries the Q pin across.
BUCKET_PLATE = 2.4                                   # mm, printed wrapper and side-plate thickness
BUCKET_WRAPPER = BREF.to_bucket(BREF.wrapper_E()[0])    # outer surface: support front -> heel -> cutting-edge tip
FLOOR_TIP_DIR = BREF.dir_to_bucket((-1.0, 0.0))      # along the floor, toward the cutting edge
EDGE_OUT = np.array([-FLOOR_TIP_DIR[1], FLOOR_TIP_DIR[0]])      # floor normal, toward the outside
EDGE_C0 = BUCKET_WRAPPER[-1].copy()                  # cutting-edge tip, on the floor's outer face
SUPPORT_FRONT = BUCKET_WRAPPER[0].copy()
SIDE_FRONT = BREF.to_bucket(BREF.side_front_corner_E(BUCKET_PLATE * BREF.SCALE))   # side-plate front edge on the floor
BUCKET_CURL_CLEARANCE = 2.0          # mm, bucket to the stick swept over the bucket travel
TORQUE_TUBE_CLEARANCE = 1.5          # mm, torque tube to the H-link tubes and the bucket-drive rod end
TORQUE_TUBE_HALF_W = 16.5            # between the ears
TOOTH_PITCH, TOOTH_HALF_W, TOOTH_STRAP, TOOTH_SOCKET_GAP = 16.0, 3.4, 1.6, 0.1
TOOTH_Y = tuple(TOOTH_PITCH * k for k in (-2, -1, 0, 1, 2))
SUPPORT_DIR = (BUCKET_WRAPPER[1] - SUPPORT_FRONT) / np.linalg.norm(BUCKET_WRAPPER[1] - SUPPORT_FRONT)
SUPPORT_OUT = np.array([-SUPPORT_DIR[1], SUPPORT_DIR[0]])        # support-plate normal, toward H and Q
assert SUPPORT_OUT @ (np.zeros(2) - SUPPORT_FRONT) > 0


def _bucket_frames(n=41):
    """Stick-frame -> bucket-frame transform at n bucket strokes, with R in the stick frame."""
    out = []
    for L in np.linspace(ACT['closed'], ACT['open'], n):
        R = circ(F_S, L, J_S, SIDE_LINK, +1)
        Q = circ(R, H_LINK, H_S, EAR, +1)
        gm = math.atan2(*(Q - H_S)[::-1]) - EAR_BETA
        out.append((R, lambda g, gm=gm: affinity.rotate(affinity.translate(g, -H_S[0], -H_S[1]), -math.degrees(gm), origin=(0, 0))))
    return out


@functools.lru_cache(maxsize=None)
def stick_sweep():
    """Stick outline swept over the bucket travel, in the bucket frame."""
    sb = stick_base()
    return unary_union([to_bk(sb) for _, to_bk in _bucket_frames()])


@functools.lru_cache(maxsize=None)
def r_end_sweep():
    """What swings round R inside |Y| 16.5 (the H-link tubes and the bucket-drive rod eye, socket
    and rod end), swept over the bucket travel, in the bucket frame."""
    g = []
    for R, to_bk in _bucket_frames():
        u = (R - F_S) / np.linalg.norm(R - F_S)
        f0, f1 = ACT['socket_s']
        rod = LineString([tuple(R - 30.0 * u), tuple(R - f0 * u)]).buffer(ACT['socket_r'], cap_style=2)
        g.append(to_bk(unary_union([disc(R, 5.0), disc(R, ACT['eye_r']), rod])))
    return unary_union(g)


def _largest_open(g, r=0.6):
    g = g.buffer(-r, 32).buffer(r, 32)
    return max(getattr(g, 'geoms', [g]), key=lambda x: x.area)


@functools.lru_cache(maxsize=None)
def bucket_shell():
    """Side-plate outline (the whole bucket in side view): wrapper outer surface, closed by the
    straight side-plate front edge. Clear of the stick swept over the bucket travel."""
    tip_in = EDGE_C0 - BUCKET_PLATE * EDGE_OUT
    g = Polygon([tuple(p) for p in BUCKET_WRAPPER] + [tuple(tip_in), tuple(SIDE_FRONT)]).buffer(0)
    g = g.difference(stick_sweep().buffer(BUCKET_CURL_CLEARANCE, 32))
    return _largest_open(g, 0.3)


@functools.lru_cache(maxsize=None)
def bucket_band():
    """The wrapper plate (floor, heel, back, support plate) as a 2.4 mm band inside the outline."""
    line = LineString([tuple(p) for p in BUCKET_WRAPPER])
    sh = bucket_shell()
    sides = [line.buffer(s * BUCKET_PLATE, single_sided=True, join_style=2) for s in (1, -1)]
    band = max(sides, key=lambda b: b.intersection(sh).area).intersection(sh)
    return _largest_open(band, 0.2)


@functools.lru_cache(maxsize=None)
def torque_tube():
    """Torque tube on the outside of the support plate between the ears (|Y| <= 16.5): the patent's
    inverted-U section, scaled into the space between H and Q. It carries the Q bore across the bucket,
    clear of the stick and of everything that swings round R."""
    sf, s, n = SUPPORT_FRONT, SUPPORT_DIR, SUPPORT_OUT
    sq = float((Q_K - sf) @ s)
    feet = [sf + 1.0 * s - 0.5 * n, sf + (sq + 2.5) * s - 0.5 * n]
    crown = [sf + 4.0 * s + 5.5 * n, sf + 10.0 * s + 7.0 * n]
    g = unary_union([Polygon([tuple(p) for p in feet[:1] + crown + feet[1:]]), disc(Q_K, 3.5),
                     unary_union([disc(c, 1.5) for c in crown]).convex_hull]).convex_hull
    g = g.difference(stick_sweep().buffer(BUCKET_CURL_CLEARANCE, 32)).difference(r_end_sweep().buffer(TORQUE_TUBE_CLEARANCE, 32))
    return _largest_open(g, 0.4)


def bucket_ears():
    """Hinge plates carrying H and Q, standing on the support plate (|Y| 16.5..20.5)."""
    sf, s, n = SUPPORT_FRONT, SUPPORT_DIR, SUPPORT_OUT
    sq = float((Q_K - sf) @ s)
    return unary_union([disc(np.zeros(2), 10.0), disc(Q_K, 7.0), disc(sf - 0.8 * n + 0.5 * s, 0.8),
                        disc(sf + (sq + 4.0) * s - 0.8 * n, 0.8)]).convex_hull


@functools.lru_cache(maxsize=None)
def cutting_edge():
    """Floor-plate end at the cutting edge: outer and inner face points (bucket frame)."""
    outer, inner = EDGE_C0, EDGE_C0 - BUCKET_PLATE * EDGE_OUT
    return dict(outer=outer, inner=inner, mid=0.5 * (outer + inner), half_plate=0.5 * BUCKET_PLATE)


# tooth + adapter side outline from US 8,201,350 FIG. 1 (tooth 34 on its adapter), at 1:15:
# (u forward along the floor from the cutting-edge tip, w outward from the floor's outer face), mm.
# The tip is T itself; the adapter straddles the cutting edge with straps 11 mm long.
TOOTH_UW = [(4.0, -3.4), (-1.0, -5.2), (-10.0, -4.2), (-11.0, -3.0), (-11.0, 1.7), (-9.0, 1.9), (4.0, 3.5)]


@functools.lru_cache(maxsize=None)
def tooth_outline():
    """Side outline of one tooth (tip + adapter): FIG. 1 shape, tip on T, with a socket that slides
    over the floor-plate edge (0.1 mm gap)."""
    a, v = FLOOR_TIP_DIR, EDGE_OUT
    env = Polygon([tuple(T_K)] + [tuple(EDGE_C0 + u * a + w * v) for u, w in TOOTH_UW])
    g = env.difference(bucket_band().buffer(TOOTH_SOCKET_GAP, join_style=2))
    return max(getattr(g, 'geoms', [g]), key=lambda x: x.area)


@functools.lru_cache(maxsize=None)
def bucket_parts():
    shell, band = bucket_shell(), bucket_band()
    return dict(shell=shell, band=band, ears=bucket_ears(), torque_tube=torque_tube(), teeth=tooth_outline(),
                inner=_largest_open(shell.difference(band), 0.2))


@functools.lru_cache(maxsize=None)
def bucket_profile():
    return unary_union([bucket_shell(), bucket_ears(), torque_tube()])


def link_parts():
    side = unary_union([disc((0, 0), 5.0), disc((SIDE_LINK, 0), 5.0)]).convex_hull
    hl = unary_union([disc((0, 0), 5.0), disc((H_LINK, 0), 5.0)]).convex_hull
    return dict(side=side, h=hl)


def actuator_body(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    u = (b - a) / np.linalg.norm(b - a)
    n = np.array([-u[1], u[0]]) * ACT['body_half']
    return Polygon([a + 6 * u + n, a + ACT['body_end_s'] * u + n, a + ACT['body_end_s'] * u - n, a + 6 * u - n])


# --- masses (PETG, 2.5 mm box walls, 2.4 mm bucket shell)
def _box_mass(profile, width, t=T_WALL):
    core = profile.buffer(-t)
    return RHO * (2 * profile.area * t + profile.exterior.length * (width - 2 * t) * t
                  + PRINT_INFILL * core.area * (width - 2 * t))


def mass_model():
    bp = boom_profile()
    sp, _ = stick_profile()
    m_boom = _box_mass(bp, WIDTH['boom']) * 0.93 + RHO * (2 * c_bracket().area * 5 + math.pi * (10 ** 2 - 3 ** 2) * 60)
    m_stick = _box_mass(sp, WIDTH['stick']) + RHO * math.pi * (10 ** 2 - 3 ** 2) * 64
    bkp = bucket_parts()
    comps = [(RHO * 2 * bkp['shell'].area * BUCKET_PLATE, bkp['shell']), (RHO * bkp['band'].area * (BUCKET_W - 2 * BUCKET_PLATE), bkp['band']),
             (RHO * 2 * bkp['ears'].area * 4.0, bkp['ears']), (_box_mass(bkp['torque_tube'], 2 * TORQUE_TUBE_HALF_W), bkp['torque_tube']),
             (RHO * 5 * bkp['teeth'].area * 2 * TOOTH_HALF_W, bkp['teeth'])]
    m_bucket = sum(m for m, _ in comps)
    c_bucket = sum(m * np.array(g.centroid.coords[0]) for m, g in comps) / m_bucket
    lk = link_parts()
    inner = bkp['inner']
    return dict(boom=(m_boom, np.array(bp.centroid.coords[0])), stick=(m_stick, np.array(sp.centroid.coords[0])),
                bucket=(m_bucket, c_bucket),
                payload=(PAYLOAD, np.array(inner.centroid.coords[0])),
                side_link=(RHO * lk['side'].area * 4, np.array([SIDE_LINK / 2, 0])),
                h_link=(RHO * (2 * lk['h'].area * 4 + 2 * math.pi * (5 ** 2 - 1.6 ** 2) * 17.8), np.array([H_LINK / 3, 0])))


def potential(strokes, payload=True):
    s = solve(strokes)
    po, Pn = s['poses'], s['pins']
    V, g = 0.0, 9.81
    for nm in ('boom', 'stick', 'bucket', 'side_link', 'h_link'):
        m, c = MASS[nm]
        V += (2 if nm == 'side_link' else 1) * m * g * to_world(c, *po[nm])[1]
    if payload:
        m, c = MASS['payload']
        V += m * g * to_world(c, *po['bucket'])[1]
    for a, b, k in (('A', 'B', 2), ('C', 'D', 1), ('F', 'R', 1)):
        u = (Pn[b] - Pn[a]) / np.linalg.norm(Pn[b] - Pn[a])
        V += k * g * (ACT['mass_barrel'] * (Pn[a] + ACT['barrel_cg_s'] * u)[1]
                      + ACT['mass_rod'] * (Pn[b] - (ACT['closed'] - ACT['rod_cg_s']) * u)[1])
    return V / 1000.0


def drive_forces(strokes, payload=True, h=0.05):
    out = []
    for i in range(3):
        p, m = list(strokes), list(strokes)
        p[i] = min(60.0, p[i] + h)
        m[i] = max(0.0, m[i] - h)
        out.append((potential(p, payload) - potential(m, payload)) / ((p[i] - m[i]) / 1000.0) / (2 if i == 0 else 1))
    return out


def moment_arms(strokes, h=0.02):
    res = []
    for i, key in enumerate(('theta', 'phi', 'gamma')):
        p, m = list(strokes), list(strokes)
        p[i] = min(60.0, p[i] + h)
        m[i] = max(0.0, m[i] - h)
        res.append(1.0 / abs((solve(p)[key] - solve(m)[key]) / (p[i] - m[i])))
    return res


def transmission(strokes):
    s = solve(strokes)
    Pn = s['pins']
    u = (Pn['Q'] - Pn['R']) / H_LINK
    v = (Pn['Q'] - Pn['H']) / EAR
    c = (Pn['R'] - Pn['F']) / np.linalg.norm(Pn['R'] - Pn['F'])
    w = (Pn['R'] - Pn['J']) / SIDE_LINK
    return (math.degrees(math.acos(min(1, abs(float(u @ v))))), math.degrees(math.acos(min(1, abs(float(c @ w))))))


def envelope(n=19, nk=25):
    lin = np.linspace(0, 60, n)
    tip = lambda a, b, k: solve((a, b, k))['pins']['T']
    faces = [np.array([[tip(a, b, k) for b in lin] for a in lin]) for k in np.linspace(0, 60, nk)]
    for e in (0.0, 60.0):
        faces.append(np.array([[tip(a, e, k) for k in lin] for a in lin]))
        faces.append(np.array([[tip(e, b, k) for k in lin] for b in lin]))
    quads = []
    for g in faces:
        for i in range(n - 1):
            for j in range(n - 1):
                q = Polygon([tuple(g[i, j]), tuple(g[i + 1, j]), tuple(g[i + 1, j + 1]), tuple(g[i, j + 1])]).buffer(0.01)
                if q.is_valid and q.area > 0:
                    quads.append(q)
    u = unary_union(quads)
    return unary_union([Polygon(x.exterior) for x in getattr(u, 'geoms', [u])])


def working_ranges(env):
    minx, miny, maxx, maxy = env.bounds
    ground = LineString([(-500, GROUND_Z), (1500, GROUND_Z)]).intersection(env)
    return dict(dig_depth=GROUND_Z - miny, reach_ground=ground.bounds[2] - SWING_X, reach_max=maxx - SWING_X,
                cut_height=maxy - GROUND_Z)


F_S = _bucket_base()
MASS = mass_model()

DEVIATIONS = dict(
    A=('boom-cylinder base', P['A_world'], A_W, 'hidden in the foot bracket; sets the -35..+50 deg range'),
    D=('stick tail (stick-cylinder rod pin)', P['D_stick'], D_S, f'tail {STICK_TAIL:.0f} mm instead of 50.3 for 60 mm stroke'),
    C=('stick-cylinder base on the boom top', P['C_boom'], C_B, '15 mm bracket on the top flange keeps the drive clear of the boom'),
    F=('bucket-cylinder base on the stick', P['F_stick'], F_S, 'moved so 140-200 mm spans the bucket range'),
)


# ------------------------------------------------------------------ lateral layout (|Y| bands, mirrored)
CAT_1_15 = dict(dig_depth=6730 / SCALE, reach_ground=9870 / SCALE, cut_height=9450 / SCALE, load_height=6480 / SCALE,
                min_load_height=2160 / SCALE)
Y = dict(
    boom=(0, 20.0), boom_nose=(0, 10.5), boom_b_pad=(20.0, 28.3), boom_b_boss=(28.3, 30.9), boom_cyl=34.0, boom_c_cheek=(8.0, 13.0),
    foot_plate=(20.5, 25.5), foot_outer_cheek=(42.5, 47.5), foot_flange=(0, 50.0),
    stick=(0, 16.0), stick_head_plate=(11.0, 16.0), stick_bridge=(0, 11.0), f_cheek=(8.0, 13.0),
    bucket=(0, 40.0), bucket_ear=(16.5, 20.5),
    side_link=(26.0, 30.0), h_link_plate=(21.0, 25.0), h_link_tube=(5.8, 20.9), h_link_boss=(3.1, 5.8), torque_tube=(0, 16.5),
)
BOOM_NOSE_R = 54.0        # boom narrows to |Y| <= 10.5 inside this radius around E
STICK_FORK_R = 52.0       # stick head plates (|Y| 11..16, an open fork round the boom nose) inside this radius
BOARD_SIDE = dict(boom=-1, stick=+1, bucket=+1)
# pin diameter and the |Y| band of the collar on each end (outside the outermost member)
PIN_ENDS = dict(O=(6, 25.8, 29.8), A=(3, 47.8, 50.8), B=(3, 37.3, 40.3), C=(3, 13.3, 16.3), E=(6, 16.3, 20.3),
                D=(3, 16.3, 19.3), F=(3, 13.3, 16.3), J=(3, 30.3, 33.3), R=(3, 30.3, 33.3), Q=(3, 25.3, 28.3),
                H=(6, 20.8, 24.8))
COLLAR_R = {6: 5.5, 3: 3.5}   # drive board (9.75 side) to the left (+1) / right (-1) of rear->rod


def joint_angles(strokes):
    s = solve(strokes)
    return math.degrees(s['theta']), math.degrees(s['phi']), math.degrees(s['gamma'])


@functools.lru_cache(maxsize=None)
def stick_regions():
    sb = stick_base()
    fork = disc(np.zeros(2), STICK_FORK_R)
    head = sb.intersection(fork)
    return dict(head=head, box=sb.difference(fork), bridge=head.intersection(box(D_S[0] + 9.0, 18.0, 80, 120)), j=disc(J_S, 7.0))




@functools.lru_cache(maxsize=None)
def foot_parts():
    flange_x1 = A_W[0] + 14.0
    plate = unary_union([unary_union([disc(O, 13.0), disc(A_W, 7.5)]).convex_hull,
                         Polygon([(-28, TURNTABLE_Z + 6), (-17, -9), (11, -9), (flange_x1, TURNTABLE_Z + 6)])])
    outer = unary_union([disc(A_W, 7.5), Polygon([(A_W[0] - 7, A_W[1] - 3), (A_W[0] + 7, A_W[1] - 3),
                                                    (A_W[0] + 9, TURNTABLE_Z + 6), (A_W[0] - 9, TURNTABLE_Z + 6)])])
    flange = box(-36, TURNTABLE_Z, flange_x1, TURNTABLE_Z + 6)
    return dict(plate=plate, outer=outer, flange=flange)


def actuator_shapes(a, b, board=+1):
    """Side-view envelope of one drive between rear pin a and rod pin b (world). The body section
    is 16.1 deep: 9.75 on the board side, 6.35 on the other; `board` = +1 puts the board on the
    left of a->b."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    L = float(np.linalg.norm(b - a))
    u = (b - a) / L
    n = np.array([-u[1], u[0]]) * board
    s0, s1 = ACT['cap_s'], ACT['body_end_s']
    body = Polygon([a + s0 * u + ACT['body_board'] * n, a + s1 * u + ACT['body_board'] * n,
                    a + s1 * u - ACT['body_back'] * n, a + s0 * u - ACT['body_back'] * n])
    rod = LineString([tuple(a + s1 * u), tuple(b)]).buffer(ACT['rod_r'] + 0.5, cap_style=2)
    f0, f1 = ACT['socket_s']
    socket = LineString([tuple(b - f1 * u), tuple(b - f0 * u)]).buffer(ACT['socket_r'], cap_style=2)
    return dict(body=unary_union([body, disc(a, ACT['eye_r'])]), rod=unary_union([rod, disc(b, ACT['eye_r'])]),
                socket=socket, outline=unary_union([rod, socket, disc(b, ACT['eye_r'])]))


def _band(lo, hi, side):
    return (lo, hi) if side > 0 else (-hi, -lo)


def parts_at(strokes, sol=None):
    """(name, body, polygon_world, (y_lo, y_hi)) for every item, both sides listed."""
    s = sol or solve(strokes)
    P, po = s['pins'], s['poses']
    out = []

    def add(name, body, g, frame, band):
        out.append((name, body, place(g, *po[frame]) if frame else g, band))
    bp = boom_profile()
    add('boom.main', 'boom', bp.difference(disc(E_B, BOOM_NOSE_R)), 'boom', (-20.0, 20.0))
    add('boom.nose', 'boom', bp.intersection(disc(E_B, BOOM_NOSE_R)), 'boom', (-10.5, 10.5))
    fp, sr, bk, lk = foot_parts(), stick_regions(), bucket_parts(), link_parts()
    for sg in (1, -1):
        add('boom.B_pad', 'boom', disc(B_B, 8.5), 'boom', _band(*Y['boom_b_pad'], sg))
        add('boom.B_boss', 'boom', disc(B_B, ACT['boss_r']), 'boom', _band(*Y['boom_b_boss'], sg))
        add('h_link.r_boss', 'h_link', disc(np.zeros(2), ACT['boss_r']), 'h_link', _band(*Y['h_link_boss'], sg))
        add('h_link.r_tube', 'h_link', disc(np.zeros(2), 5.0), 'h_link', _band(*Y['h_link_tube'], sg))
        add('boom.C_cheek', 'boom', c_bracket(), 'boom', _band(*Y['boom_c_cheek'], sg))
        add('foot.plate', 'base', fp['plate'], None, _band(*Y['foot_plate'], sg))
        add('foot.outer_cheek', 'base', fp['outer'], None, _band(*Y['foot_outer_cheek'], sg))
        add('stick.head_plate', 'stick', sr['head'], 'stick', _band(*Y['stick_head_plate'], sg))
        add('stick.F_cheek', 'stick', f_lug(), 'stick', _band(*Y['f_cheek'], sg))
        add('bucket.ear', 'bucket', bk['ears'], 'bucket', _band(*Y['bucket_ear'], sg))
        add('side_link', 'side_link' + str(sg), lk['side'], 'side_link', _band(*Y['side_link'], sg))
        add('h_link.plate', 'h_link', lk['h'], 'h_link', _band(*Y['h_link_plate'], sg))
    add('foot.flange', 'base', fp['flange'], None, (-50.0, 50.0))
    add('stick.box', 'stick', sr['box'], 'stick', (-16.0, 16.0))
    add('stick.head_bridge', 'stick', sr['bridge'], 'stick', (-11.0, 11.0))
    add('bucket.shell', 'bucket', unary_union([bk['shell'], bk['teeth']]), 'bucket', (-40.0, 40.0))
    add('bucket.torque_tube', 'bucket', bk['torque_tube'], 'bucket', (-TORQUE_TUBE_HALF_W, TORQUE_TUBE_HALF_W))
    for pin, (dpin, ylo, yhi) in PIN_ENDS.items():           # collars / retainers outside the outermost member
        for sg in (1, -1):
            out.append(('pin.' + pin, 'pin.' + pin, disc(P[pin], COLLAR_R[dpin]), _band(ylo, yhi, sg)))
    for nm, a, b, ys, side in [('cyl.boom', 'A', 'B', (Y['boom_cyl'], -Y['boom_cyl']), BOARD_SIDE['boom']),
                               ('cyl.stick', 'C', 'D', (0.0,), BOARD_SIDE['stick']),
                               ('cyl.bucket', 'F', 'R', (0.0,), BOARD_SIDE['bucket'])]:
        sh = actuator_shapes(P[a], P[b], side)
        for y in ys:
            out.append((nm + '.body', nm + str(y), sh['body'], (y - ACT['body_half_y'], y + ACT['body_half_y'])))
            out.append((nm + '.rod', nm + str(y), sh['rod'], (y - ACT['rod_r'], y + ACT['rod_r'])))
            out.append((nm + '.socket', nm + str(y), sh['socket'], (y - ACT['socket_r'], y + ACT['socket_r'])))
    return out


# Pin-joined pairs: contact is accepted only inside the 6.5 mm pin zone (eye and its supports).
_ALLOWED = {tuple(sorted(k)) for k in [
    ('boom.B_pad', 'cyl.boom.rod'), ('foot.plate', 'cyl.boom.body'), ('foot.outer_cheek', 'cyl.boom.body'),
    ('boom.C_cheek', 'cyl.stick.body'), ('stick.head_bridge', 'cyl.stick.rod'), ('stick.F_cheek', 'cyl.bucket.body'),
    ('stick.box', 'cyl.bucket.rod'), ('h_link.r_tube', 'cyl.bucket.rod'), ('boom.main', 'foot.plate'),
    ('side_link', 'stick.box'), ('h_link.plate', 'cyl.bucket.rod'), ('stick.head_plate', 'cyl.stick.rod'),
    ('boom.nose', 'stick.head_bridge'), ('cyl.boom.rod', 'pin.B'), ('boom.B_boss', 'cyl.boom.rod'),
    ('boom.B_boss', 'cyl.boom.socket'), ('h_link.r_boss', 'cyl.bucket.rod'), ('h_link.r_boss', 'cyl.bucket.socket')]}


def _pairs(strokes):
    s = solve(strokes)
    items = parts_at(strokes, s)
    pz = unary_union([disc(p, 6.5) for p in s['pins'].values()])
    for i in range(len(items)):
        n1, b1, g1, y1 = items[i]
        for j in range(i + 1, len(items)):
            n2, b2, g2, y2 = items[j]
            if b1 == b2 or g1.is_empty or g2.is_empty or min(y1[1], y2[1]) - max(y1[0], y2[0]) <= 0.05:
                continue
            key = tuple(sorted((n1, n2)))
            if key in _ALLOWED:          # bosses entirely inside a pin zone have nothing left to clash
                g1, g2 = g1.difference(pz), g2.difference(pz)
                if g1.is_empty or g2.is_empty:
                    continue
            yield key, g1.distance(g2)


def interference(strokes, clearance=1.0):
    """2.5D check: items clash when their |Y| bands overlap and their side-view outlines come closer
    than `clearance`; items of one rigid body are skipped; pin zones excluded for pin-joined pairs."""
    return [dict(a=k[0], b=k[1], gap=round(g, 2)) for k, g in _pairs(strokes) if g < clearance]


def min_gaps(strokes):
    res = {}
    for k, g in _pairs(strokes):
        res[k] = min(res.get(k, 1e9), g)
    return res


def tip_forces(strokes, thrust=ACT['thrust_cont']):
    arms = moment_arms(strokes)
    P_ = solve(strokes)['pins']
    return dict(bucket=thrust * arms[2] / TIP_R, stick=thrust * arms[1] / float(np.linalg.norm(P_['T'] - P_['E'])))


def dump_height():
    shell = unary_union([bucket_parts()['shell'], tooth_outline()])
    best, pose = -1e9, None
    for a in np.linspace(40, 60, 6):
        for b in np.linspace(0, 60, 13):
            s = solve((a, b, 0.0))
            low = place(shell, *s['poses']['bucket']).bounds[1]
            if low > best:
                best, pose = low, (a, b, 0.0)
    return best - GROUND_Z, pose

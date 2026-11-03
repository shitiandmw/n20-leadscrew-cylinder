"""X1 swing concept: animation of why wires through the swing centre wind up, and how the proposed slip ring stops it.

Part 1  The same upper turns three times: wires straight through the centre (left), wires through the SRC022A-6 slip ring (right).
Part 2  Inside the slip ring: one ring per wire on the rotor, one spring brush per ring in the housing.
Part 3  The other option: a limited swing with an end stop.
Summary card.

The sizes of X1, the RU66 and the slip ring come from draw_swing_concept.py, so the animation and the concept sheet agree.
The drawing is schematic: the chassis and turntable are see-through, the carbody is drawn taller than X1's to show the
leads, the track motors are drawn close in, the upper is simplified, and the slip ring's inside (rings, brushes) is
illustrative, not taken from the datasheet.

Usage, with the CAD Python as for the concept sheet:
  python animate_slip_ring.py                              # ../X1_slip_ring_animation.mp4 and ../X1_slip_ring_animation_check.json
  python animate_slip_ring.py --stills 3,12 --dir /tmp/x  # PNG stills at those times (seconds), no video
"""
import argparse, hashlib, json, math, multiprocessing, subprocess, sys, textwrap
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.colors import to_rgba
from matplotlib.patches import FancyBboxPatch, Circle, Wedge, Rectangle, Polygon as MPoly
import imageio_ffmpeg

HERE = Path(__file__).resolve().parent
OUT = HERE.parent                                     # track_wheel_jgy370/X1/swing_concept
sys.path.insert(0, str(HERE))
import draw_swing_concept as C                        # noqa: E402  concept-sheet sizes; imports X1/source/x1_parts.py
X = C.X

VIDEO = OUT / 'X1_slip_ring_animation.mp4'
CHECK = OUT / 'X1_slip_ring_animation_check.json'
W, H, FPS, DPI = 1280, 720, 25, 100

# ------------------------------------------------------------------ sizes (X1 Z values, mm)
TOP_Z, PLATE_Z0, PASS_R, BODY_R = X.TOP_Z, X.TOP_Z - X.PLATE_T, X.PASSAGE_R, X.BODY_R      # 85, 79, 12.5, 60
RU_RO, RU_Z = X.RU66['D']/2, (X.SEAT_Z, X.TURNTABLE_Z)                                      # 47.5, 85-100
DECK_Z = C.DECK_Z                                                                           # 101-107
SR, BOSS_Z, BOSS_R, FL_Z, BODY_Z, ROTOR_Z, TUBE = C.SR, C.BOSS_Z, C.BOSS_R, C.FL_Z, C.BODY_Z, C.ROTOR_Z, C.TUBE
# schematic only
FLOOR_Z = -2.0                  # carbody drawn taller than X1's (bottom Z 34) to show the leads to the track motors
DECK_R = 80.0                   # simplified turntable: the real upper is not designed yet
CLAMP_Z = (12.0, 22.0)          # cable clamp on the chassis: it holds the bottom end of the wires
MOTOR_Y, MOTOR_Z = 92.0, 10.0   # track motors drawn close in (on X1 they sit at the rear of the tracks)
BUNDLE_R = 4.5
PHI = np.radians([45, 135, 225, 315])     # strands in the bundle: 0 and 1 go to the left motor, 2 and 3 to the right
SLOT = math.radians(216)                  # driver-tube slot, on the side of the drivers' box (upper frame)
EXIT = [np.array([-16.0, -11.0 - 2.6*i, DECK_Z[1] + 0.9]) for i in range(4)]   # leads leave the drivers' box here
# slip ring inside (illustrative): six rings on the rotor, a brush for each in the housing
RING_Z = [52.5 + 2.75*k for k in range(6)]
RING_R, RING_H, CORE_R, WALL_IN = 6.4, 1.8, 4.4, 9.8

# ------------------------------------------------------------------ look
INK, GREY = '#1d2b2f', '#5f6f75'
XF, XF_EDGE = C.XF, '#b9770e'           # chassis (X-frame), as on the concept sheet
TT, TT_D, TT_EDGE = '#2e86c1', '#21618c', '#1b4f72'   # upper: everything that turns
SLIP, SLIP_L, SLIP_D, ROTOR = C.SLIP, C.SLIP_L, '#154360', '#5dade2'
BRG = C.BRG
GOLD = '#d4ac0d'
WIRES = ['#e03131', '#f59f00', '#2f9e44', '#7048e8']  # left motor: red + amber; right motor: green + violet
GOOD, BAD = '#1e8449', '#c0392b'
OUT_C = (0.11, 0.17, 0.18, 0.9)
NONE = (0.0, 0.0, 0.0, 0.0)
BG = '#fbfcfc'

PARTS = [dict(title='Part 1 of 3: the upper turns', dur=22.0),
         dict(title='Part 2 of 3: inside the slip ring', dur=18.0),
         dict(title='Part 3 of 3: the other option', dur=14.0),
         dict(title='Summary', dur=6.0)]
CAPTIONS = [
    [(0.0, 6.5, 'On the upper: the battery, receiver and motor drivers. On the chassis: the two track motors. '
                'Four wires join them through the swing centre.'),
     (6.5, 13.5, 'Left: the top end of the wires turns with the upper, but the chassis holds the bottom end. '
                 'So every turn of the upper adds one twist.'),
     (13.5, 22.0, 'Right: the slip ring cuts every wire in two. The top half turns with the upper and the bottom half '
                  'stays still, so neither half ever twists.')],
    [(0.0, 6.0, 'Inside, each wire from the upper is soldered to its own metal ring on the rotor. '
                'The tube on the turntable turns the rotor.'),
     (6.0, 12.0, 'Each wire to the motors is soldered to a spring brush in the housing. '
                 'The housing is screwed to the X-frame and never turns.'),
     (12.0, 18.0, 'The rings slide under the brushes. They always touch, so the current gets across at every angle, '
                  'for any number of turns.')],
    [(0.0, 7.0, 'Without a slip ring, an end stop can keep the upper within just under half a turn each way. '
                'The wires then twist half a turn at most.'),
     (7.0, 14.0, 'A loose loop of soft silicone wire takes that easily. The catch: the upper can never keep turning '
                 'one way; it has to swing back.')],
    []]


# ------------------------------------------------------------------ maths helpers
def unit(v):
    v = np.asarray(v, float)
    return v/np.linalg.norm(v)


def shade(c, k=1.0, alpha=None):
    r, g, b, a = to_rgba(c)
    if k <= 1:
        r, g, b = r*k, g*k, b*k
    else:
        t = min(k - 1, 1.0)
        r, g, b = r + (1 - r)*t, g + (1 - g)*t, b + (1 - b)*t
    return (r, g, b, a if alpha is None else alpha)


def rot(P, th):
    P = np.asarray(P, float)
    c, s = math.cos(th), math.sin(th)
    Q = P.copy()
    Q[..., 0] = c*P[..., 0] - s*P[..., 1]
    Q[..., 1] = s*P[..., 0] + c*P[..., 1]
    return Q


def arc(r, a0, a1, z, n, cx=0.0, cy=0.0):
    t = np.linspace(a0, a1, n)
    return np.stack([cx + r*np.cos(t), cy + r*np.sin(t), np.full(n, float(z))], -1)


def polar(r, a, z):
    return np.array([r*math.cos(a), r*math.sin(a), float(z)])


def bez(P0, P1, P2, P3, n=24):
    t = np.linspace(0, 1, n)[:, None]
    P0, P1, P2, P3 = (np.asarray(p, float) for p in (P0, P1, P2, P3))
    return (1 - t)**3*P0 + 3*(1 - t)**2*t*P1 + 3*(1 - t)*t**2*P2 + t**3*P3


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x*x*(3 - 2*x)


def move(t, t0, t1, a0, a1, ramp=0.7):
    """From a0 to a1 between t0 and t1: constant speed with eased start and stop."""
    if t <= t0:
        return a0
    if t >= t1:
        return a1
    T, tt = t1 - t0, t - t0
    r = min(ramp, T/2)
    v = (a1 - a0)/(T - r)
    if tt < r:
        return a0 + 0.5*v*tt*tt/r
    if tt > T - r:
        d = T - tt
        return a1 - 0.5*v*d*d/r
    return a0 + v*(tt - r/2)


# ------------------------------------------------------------------ a small painter's-algorithm renderer
class Cam:
    """Orthographic view from azimuth az and elevation el (degrees)."""
    def __init__(self, az, el):
        self.a, e = math.radians(az), math.radians(el)
        self.c = np.array([math.cos(e)*math.cos(self.a), math.cos(e)*math.sin(self.a), math.sin(e)])   # towards the viewer
        self.r = np.array([-math.sin(self.a), math.cos(self.a), 0.0])                                    # screen right
        self.u = np.cross(self.c, self.r)                                                                # screen up
        self.sin_el, self.cos_el = math.sin(e), math.cos(e)
        self.light = unit(0.5*self.c + np.array([0.0, 0.0, 0.8]) - 0.3*self.r)

    def xy(self, P):
        P = np.asarray(P, float)
        return np.stack([P @ self.r, P @ self.u], -1)

    def depth(self, P):
        return -(np.asarray(P, float) @ self.c)


class Scene:
    """Polygons sorted by (layer, depth), far first, drawn as one PolyCollection."""
    def __init__(self, cam, ppu):
        self.cam, self.ppu, self.items = cam, ppu, []

    def add(self, P, fc, ec=NONE, lw=0.0, layer=0, depth=None):
        P = np.asarray(P, float)
        d = float(self.cam.depth(P).mean()) if depth is None else float(depth)
        self.items.append((layer, d, self.cam.xy(P), to_rgba(fc) if isinstance(fc, str) else fc, ec, lw))

    def face(self, P, base, n, alpha=1.0, ec=None, lw=0.0, layer=0, k=None, depth=None):
        n = np.asarray(n, float)
        if float(n @ self.cam.c) <= 1e-6:
            return
        if k is None:
            k = 0.62 + 0.42*max(0.0, float(n @ self.cam.light))
        fc = shade(base, k, alpha)
        if ec is None:
            ec, lw = (fc, 0.4) if alpha >= 1 else (NONE, 0.0)
        self.add(P, fc, ec, lw, layer, depth)

    def line(self, P, color, w_px, outline=None, o_px=0.8, layer=0, colors=None, bias=0.0, ext=0.8):
        """A wire or an edge: one quad per segment, sorted with everything else."""
        P = np.asarray(P, float)
        S, D = self.cam.xy(P), self.cam.depth(P) + bias
        w, o = 0.5*w_px/self.ppu, o_px/self.ppu
        col = to_rgba(color) if isinstance(color, str) else color
        for k in range(len(P) - 1):
            s0, s1 = S[k], S[k + 1]
            t = s1 - s0
            L = math.hypot(t[0], t[1])
            if L < 1e-9:
                continue
            t = t/L
            nv = np.array([-t[1], t[0]])
            d = 0.5*(D[k] + D[k + 1])
            if outline is not None:
                h = w + o
                self.items.append((layer, d + 1e-3, np.array([s0 + nv*h, s1 + nv*h, s1 - nv*h, s0 - nv*h]), outline, NONE, 0.0))
            e = t*w*ext
            self.items.append((layer, d, np.array([s0 - e + nv*w, s1 + e + nv*w, s1 + e - nv*w, s0 - e - nv*w]),
                               col if colors is None else colors[k], NONE, 0.0))

    def dot(self, P, r_px, fc, ec=NONE, lw=0.0, layer=0, bias=-0.3, n=16):
        s, d, r = self.cam.xy(P), float(self.cam.depth(P)) + bias, r_px/self.ppu
        t = np.linspace(0, 2*np.pi, n, endpoint=False)
        self.items.append((layer, d, np.stack([s[0] + r*np.cos(t), s[1] + r*np.sin(t)], -1),
                           to_rgba(fc) if isinstance(fc, str) else fc, to_rgba(ec) if isinstance(ec, str) else ec, lw))

    def draw(self, ax):
        items = sorted(self.items, key=lambda it: (it[0], -it[1]))
        ax.add_collection(PolyCollection([it[2] for it in items], facecolors=[it[3] for it in items],
                                         edgecolors=[it[4] for it in items], linewidths=[it[5] for it in items],
                                         antialiaseds=True))


# ------------------------------------------------------------------ shapes
def outline(S, P, color=OUT_C, lw=0.9, layer=0, bias=-0.5):
    S.line(P, color, lw, layer=layer, bias=bias, ext=0.5)


def annulus(r, hole, z, cx=0.0, cy=0.0, n=72):
    outer = arc(r, 0, 2*np.pi, z, n, cx, cy)
    return outer[:-1] if not hole else np.vstack([outer, arc(hole, 2*np.pi, 0, z, n, cx, cy)])


def cyl(S, r, z0, z1, color, cx=0.0, cy=0.0, n=40, layer=0, top=True, edge=OUT_C, lw=0.8, top_k=1.12,
        stripe=None, stripe_color='white', stripe_px=2.2):
    """Opaque vertical cylinder. `stripe` (an angle) marks a turning part."""
    c, a = S.cam, np.linspace(0, 2*np.pi, n + 1)
    for k in range(n):
        am = 0.5*(a[k] + a[k + 1])
        nrm = np.array([math.cos(am), math.sin(am), 0.0])
        if nrm @ c.c <= 0:
            continue
        p0, p1 = (cx + r*math.cos(a[k]), cy + r*math.sin(a[k])), (cx + r*math.cos(a[k + 1]), cy + r*math.sin(a[k + 1]))
        S.face([(*p0, z0), (*p1, z0), (*p1, z1), (*p0, z1)], color, nrm, layer=layer)
    if top:
        S.face(arc(r, 0, 2*np.pi, z1, n + 1, cx, cy)[:-1], color, (0, 0, 1), layer=layer, k=top_k)
    if stripe is not None and math.cos(stripe - c.a) > 0.08:
        q = (cx + 1.01*r*math.cos(stripe), cy + 1.01*r*math.sin(stripe))
        S.line([(*q, z0 + 0.25*(z1 - z0)), (*q, z1 - 0.12*(z1 - z0))], stripe_color, stripe_px, layer=layer, bias=-0.4)
    if edge is not None:
        b = -(0.5*(z1 - z0)*c.sin_el + r*c.cos_el + 0.3)
        outline(S, arc(r, 0, 2*np.pi, z1, 2*n + 1, cx, cy), edge, lw, layer, b)
        outline(S, arc(r, c.a - np.pi/2, c.a + np.pi/2, z0, n + 1, cx, cy), edge, lw, layer, b)
        for s in (-1, 1):
            q = (cx + r*math.cos(c.a + s*np.pi/2), cy + r*math.sin(c.a + s*np.pi/2))
            outline(S, [(*q, z0), (*q, z1)], edge, lw, layer, b)


def ghost_cyl(S, r, z0, z1, color, a_front=0.13, a_back=0.07, edge=None, lw=0.9, layer=0, cx=0.0, cy=0.0,
              top=0.0, hole=0.0, n=64):
    """See-through vertical cylinder: back half, front half and top drawn as single translucent polygons."""
    c, a = S.cam, S.cam.a
    dc = float(c.depth([cx, cy, 0.5*(z0 + z1)]))
    if a_back:
        back = np.vstack([arc(r, a + np.pi/2, a + 1.5*np.pi, z0, n, cx, cy), arc(r, a + 1.5*np.pi, a + np.pi/2, z1, n, cx, cy)])
        S.add(back, shade(color, 1, a_back), layer=layer, depth=dc + 0.6*r)
    if a_front:
        front = np.vstack([arc(r, a - np.pi/2, a + np.pi/2, z0, n, cx, cy), arc(r, a + np.pi/2, a - np.pi/2, z1, n, cx, cy)])
        S.add(front, shade(color, 1, a_front), layer=layer, depth=dc - 0.6*r)
    if top:
        S.add(annulus(r, hole, z1, cx, cy), shade(color, 1.15, top), layer=layer, depth=float(c.depth([cx, cy, z1])))
    if edge is not None:
        outline(S, arc(r, 0, 2*np.pi, z1, 2*n, cx, cy), edge, lw, layer, -0.3)
        outline(S, arc(r, a - np.pi/2, a + np.pi/2, z0, n, cx, cy), edge, lw, layer, -0.3)
        for s in (-1, 1):
            q = (cx + r*math.cos(a + s*np.pi/2), cy + r*math.sin(a + s*np.pi/2))
            outline(S, [(*q, z0), (*q, z1)], edge, lw, layer, -0.3)
        if hole:
            outline(S, arc(hole, 0, 2*np.pi, z1, n, cx, cy), edge, 0.8*lw, layer, -0.3)


def box(S, x0, x1, y0, y1, z0, z1, color, th=0.0, layer=0, edge=OUT_C, lw=0.6, top_k=None):
    V = rot([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], th)
    for idx, n in (((0, 1, 2, 3), (0, 0, -1)), ((4, 5, 6, 7), (0, 0, 1)), ((0, 1, 5, 4), (0, -1, 0)),
                   ((1, 2, 6, 5), (1, 0, 0)), ((2, 3, 7, 6), (0, 1, 0)), ((3, 0, 4, 7), (-1, 0, 0))):
        S.face(V[list(idx)], color, rot(np.array(n, float), th), ec=edge, lw=lw, layer=layer,
               k=top_k if (top_k and n[2] == 1) else None)


def prism_z(S, poly, z0, z1, color, th=0.0, layer=0, edge=OUT_C, lw=0.6):
    """Counter-clockwise plan polygon extruded from z0 to z1."""
    poly = np.asarray(poly, float)
    for k in range(len(poly)):
        p, q = poly[k], poly[(k + 1) % len(poly)]
        nrm = unit([q[1] - p[1], p[0] - q[0], 0.0])
        S.face(rot([(*p, z0), (*q, z0), (*q, z1), (*p, z1)], th), color, rot(nrm, th), layer=layer)
    S.face(rot(np.column_stack([poly, np.full(len(poly), z1)]), th), color, (0, 0, 1), ec=edge, lw=lw, layer=layer, k=1.08)


def beam(S, A, B, w, h, color, th=0.0, layer=0, edge=OUT_C, lw=0.6):
    """A straight beam from A to B in an x-z plane: width w across (y), depth h."""
    A, B = np.asarray(A, float), np.asarray(B, float)
    d = unit(B - A)
    yv, nv = np.array([0.0, 1.0, 0.0]), np.array([-d[2], 0.0, d[0]])
    def cn(p, sy, sn):
        return p + sy*w/2*yv + sn*h/2*nv
    a00, a01, a10, a11 = cn(A, -1, -1), cn(A, -1, 1), cn(A, 1, -1), cn(A, 1, 1)
    b00, b01, b10, b11 = cn(B, -1, -1), cn(B, -1, 1), cn(B, 1, -1), cn(B, 1, 1)
    for P, n in (([a00, b00, b01, a01], -yv), ([a10, a11, b11, b10], yv), ([a00, a10, b10, b00], -nv),
                 ([a01, b01, b11, a11], nv), ([a00, a01, a11, a10], -d), ([b00, b10, b11, b01], d)):
        S.face(rot(P, th), color, rot(n, th), ec=edge, lw=lw, layer=layer)


def cyl_axis(S, p0, p1, r, color, n=28, layer=0, edge=OUT_C, lw=0.6):
    """Opaque cylinder along any axis (the track motors' cans)."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    ax_ = unit(p1 - p0)
    u = unit(np.cross(ax_, [0.0, 0.0, 1.0]))
    v = np.cross(ax_, u)
    a = np.linspace(0, 2*np.pi, n + 1)
    ring0 = p0 + r*np.cos(a)[:, None]*u + r*np.sin(a)[:, None]*v
    ring1 = p1 + r*np.cos(a)[:, None]*u + r*np.sin(a)[:, None]*v
    for k in range(n):
        am = 0.5*(a[k] + a[k + 1])
        S.face([ring0[k], ring0[k + 1], ring1[k + 1], ring1[k]], color, math.cos(am)*u + math.sin(am)*v, layer=layer)
    S.face(ring1[:-1], color, ax_, ec=edge, lw=lw, layer=layer, k=1.0)
    S.face(ring0[:-1], color, -ax_, ec=edge, lw=lw, layer=layer, k=1.0)


# ------------------------------------------------------------------ part 1 and 3 scene: X1's centre with the upper above
def ribbon(i, r=8.5, pitch=1.15):
    """Strand i in the driver tube's slot (upper frame, x-y)."""
    t = np.array([-math.sin(SLOT), math.cos(SLOT)])
    return r*np.array([math.cos(SLOT), math.sin(SLOT)]) + (i - 1.5)*pitch*t


def bundle_shades(S, P, color, r=BUNDLE_R):
    M = 0.5*(P[1:] + P[:-1])
    A = M.copy()
    A[:, :2] = 0
    f = np.clip((S.cam.depth(M) - S.cam.depth(A))/r, -1, 1)
    return [shade(color, 1.1 - 0.34*(x + 1)/2) for x in f]


def to_motor(i):
    side = 1 if i < 2 else -1
    x0, off = BUNDLE_R*math.cos(PHI[i]), (2.6 if i % 2 == 0 else -2.6)
    return bez((x0, side*8.0, 17.0), (x0, side*44.0, 17.0), (-70.0, side*(MOTOR_Y + off), MOTOR_Z),
               (-44.6, side*(MOTOR_Y + off), MOTOR_Z), 32)


def chassis(S, mode, th):
    ghost_cyl(S, BODY_R, FLOOR_Z, TOP_Z, XF, a_front=0.15, a_back=0.10, edge=XF_EDGE, top=0.20, hole=PASS_R)
    ghost_cyl(S, BODY_R, PLATE_Z0, TOP_Z, XF, a_front=0.16, a_back=0.0)                    # the top plate's rim
    S.add(annulus(BODY_R, 0, FLOOR_Z), shade(XF, 1, 0.08), depth=float(S.cam.depth([0, 0, FLOOR_Z])) + 2*BODY_R)
    ghost_cyl(S, RU_RO, RU_Z[0], RU_Z[1], BRG, a_front=0.10, a_back=0.05, edge=shade(BRG, 0.85, 0.8), lw=0.8)
    cyl(S, 3.0, FLOOR_Z, CLAMP_Z[0], '#7b8a8b', n=16, edge=None)                           # clamp post
    box(S, -8, 8, -8, 8, *CLAMP_Z, '#566573')                                               # cable clamp
    for side in (1, -1):                                                                    # track motors
        y = side*MOTOR_Y
        box(S, -12, 14, y - 12, y + 12, MOTOR_Z - 12, MOTOR_Z + 12, '#6c7a7b')
        cyl_axis(S, (-12, y, MOTOR_Z), (-44, y, MOTOR_Z), 11.5, '#b3bfc0')
    if mode == 'slip':
        for a in np.radians([0, 120, 240]):
            cyl(S, BOSS_R, *BOSS_Z, XF, cx=SR['pcd_r']*math.cos(a), cy=SR['pcd_r']*math.sin(a), n=16, edge=XF_EDGE, lw=0.6)
        cyl(S, SR['flange_r'], *FL_Z, SLIP_L, edge=SLIP, lw=0.8)
        cyl(S, SR['body_r'], *BODY_Z, SLIP, edge=SLIP_D, lw=0.8, top=False)
        cyl(S, SR['rotor_r'], *ROTOR_Z, ROTOR, n=20, edge=SLIP_D, lw=0.7, stripe=SLOT + th)
        ghost_cyl(S, TUBE['ro'], TUBE['z0'], DECK_Z[0], TT, a_front=0.22, a_back=0.12, edge=TT_EDGE, lw=0.8)
        for s in (-1, 1):                                                                   # the slot's edges
            q = SLOT + th + s*0.24
            S.line([polar(TUBE['ro'], q, TUBE['z0']), polar(TUBE['ro'], q, DECK_Z[0])], TT_EDGE, 1.6, bias=-0.2)


def wires(S, mode, th, w=3.0):
    if mode == 'direct':                                        # one piece from the upper to the clamp: it twists
        z = np.linspace(DECK_Z[1] + 0.6, CLAMP_Z[1], 170)
        f = np.clip((z - CLAMP_Z[1])/(DECK_Z[0] - CLAMP_Z[1]), 0, 1)
        for i in range(4):
            ang = PHI[i] + th*f
            P = np.stack([BUNDLE_R*np.cos(ang), BUNDLE_R*np.sin(ang), z], -1)
            S.line(P, WIRES[i], w, outline=OUT_C, colors=bundle_shades(S, P, WIRES[i]))
    else:
        tv = np.array([-math.sin(SLOT), math.cos(SLOT)])
        for i in range(4):                                      # top half: in the tube's slot, turning with the upper
            q = ribbon(i)
            top, low = np.array([*q, DECK_Z[1] + 0.6]), np.array([*q, 88.0])
            end = np.array([*(0.7*(i - 1.5)*tv), ROTOR_Z[1]])
            P = np.vstack([np.linspace(top, low, 10), bez(low, low - (0, 0, 4), end + (2.5*math.cos(SLOT), 2.5*math.sin(SLOT), 3), end, 16)[1:]])
            S.line(rot(P, th), WIRES[i], w, outline=OUT_C)
        for i in range(4):                                      # bottom half: never moves
            P = [polar(3.2, PHI[i], BODY_Z[0]), polar(3.2, PHI[i], BODY_Z[0] - 5), polar(BUNDLE_R, PHI[i], BODY_Z[0] - 12),
                 polar(BUNDLE_R, PHI[i], CLAMP_Z[1])]
            S.line(P, WIRES[i], w, outline=OUT_C)
    for i in range(4):                                          # clamp to the track motors: fixed in both cases
        S.line(to_motor(i), WIRES[i], w, outline=OUT_C)


def upper(S, mode, th, w=3.0):
    ghost_cyl(S, DECK_R, DECK_Z[0], DECK_Z[1], TT, a_front=0.36, a_back=0.20, edge=TT_EDGE, lw=1.0, layer=1, top=0.24)
    z1 = DECK_Z[1]
    beam(S, (18, -13, z1 + 3), (76, -13, 137), 14, 13, TT, th, layer=2)                     # boom (stub)
    box(S, 12, 46, 24, 56, z1, 139, '#d5d8dc', th, layer=2)                                  # cab
    for P, n in (([(46.3, 28, 122), (46.3, 52, 122), (46.3, 52, 135), (46.3, 28, 135)], (1, 0, 0)),
                 ([(16, 56.3, 122), (42, 56.3, 122), (42, 56.3, 135), (16, 56.3, 135)], (0, 1, 0))):
        S.face(rot(P, th), '#34495e', rot(np.array(n, float), th), ec=OUT_C, lw=0.5, layer=2, k=1.0)
    cw = np.vstack([arc(78, math.radians(150), math.radians(210), 0, 14)[:, :2], arc(56, math.radians(210), math.radians(150), 0, 14)[:, :2]])
    prism_z(S, cw, z1, 128, TT_D, th, layer=2)                                                # counterweight
    box(S, -44, -16, -36, -8, z1, 125, '#34495e', th, layer=2)                               # battery, receiver, drivers
    box(S, -42, -18, -34, -10, 125, 126.6, '#1e8449', th, layer=2)                           # driver board
    box(S, -37, -29, -28, -20, 126.6, 128.4, '#17202a', th, layer=2)
    for i in range(4):                                          # leads across the deck to the centre (or the slot)
        q = np.array([BUNDLE_R*math.cos(PHI[i]), BUNDLE_R*math.sin(PHI[i])]) if mode != 'slip' else ribbon(i)
        e, end = EXIT[i], np.array([*q, z1 + 0.6])
        u = unit(end[:2] - e[:2])
        S.line(rot(bez(e, e + (7, 0, -0.3), end - (3*u[0], 3*u[1], 0), end, 26), th), WIRES[i], w, outline=OUT_C, layer=2)


def scene_machine(cam, ppu, mode, th):
    S = Scene(cam, ppu)
    chassis(S, mode, th)
    wires(S, mode, th)
    upper(S, mode, th)
    return S


# ------------------------------------------------------------------ part 2 scene: the slip ring cut open
CAM2 = Cam(25, 22)
SLOT2 = math.radians(25 + 205)          # driver-tube slot at the start: back left
PLATE_R2 = 30.0                         # how much of the X-frame top plate is drawn around the passage


def scene_inside(th, t, ppu):
    S = Scene(CAM2, ppu)
    c, a = CAM2, CAM2.a
    back = np.linspace(a + np.pi/2, a + 1.5*np.pi, 33)            # the half behind the cut
    z0, z1 = BODY_Z
    zi = z0 + 1.2                                                 # inside floor
    # housing, cut open: inner wall of the back half, cut faces, floor, flange
    for k in range(len(back) - 1):
        am = 0.5*(back[k] + back[k + 1])
        P = [polar(WALL_IN, back[k], zi), polar(WALL_IN, back[k + 1], zi), polar(WALL_IN, back[k + 1], z1), polar(WALL_IN, back[k], z1)]
        S.face(P, SLIP, -np.array([math.cos(am), math.sin(am), 0.0]), k=0.78)
    S.add(np.vstack([arc(SR['body_r'], back[0], back[-1], zi, 33), arc(2.6, back[-1], back[0], zi, 33)]), shade(SLIP, 1.25))
    fl = (FL_Z[0], FL_Z[1])
    S.add(np.vstack([arc(SR['flange_r'], back[0], back[-1], fl[1], 49), arc(CORE_R + 0.2, back[-1], back[0], fl[1], 33)]), shade(SLIP_L, 1.0))
    outline(S, arc(SR['flange_r'], back[0], back[-1], fl[1], 49), SLIP_D, 0.9, bias=-0.3)
    for q in (back[0], back[-1]):                                  # cut faces: wall, floor, flange
        d = np.array([math.cos(q), math.sin(q)])
        for r0, r1, za, zb in ((WALL_IN, SR['body_r'], z0, z1), (2.6, SR['body_r'], z0, zi), (CORE_R + 0.2, SR['flange_r'], fl[0], fl[1])):
            P = [(*(r0*d), za), (*(r1*d), za), (*(r1*d), zb), (*(r0*d), zb)]
            S.add(P, shade(SLIP_L, 1.1), ec=SLIP_D, lw=0.7, depth=float(c.depth([0, 0, 0.5*(za + zb)])) - 0.1)
    # X-frame top plate (cut) and the two bosses behind the cut
    pb = np.linspace(a + np.pi/2, a + 1.5*np.pi, 41)
    S.add(np.vstack([arc(38, pb[0], pb[-1], TOP_Z, 41), arc(PASS_R, pb[-1], pb[0], TOP_Z, 41)]), shade(XF, 1.1, 0.30), depth=float(c.depth([0, 0, TOP_Z])) + 5)
    for q in (pb[0], pb[-1]):
        d = np.array([math.cos(q), math.sin(q)])
        S.add([(*(PASS_R*d), PLATE_Z0), (*(38*d), PLATE_Z0), (*(38*d), TOP_Z), (*(PASS_R*d), TOP_Z)], shade(XF, 1.0, 0.55), ec=XF_EDGE, lw=0.7)
    for q in np.radians([120, 240]):
        ghost_cyl(S, BOSS_R, *BOSS_Z, XF, a_front=0.30, a_back=0.2, edge=XF_EDGE, lw=0.7, cx=SR['pcd_r']*math.cos(q), cy=SR['pcd_r']*math.sin(q), n=24)
    # rotor: core with six rings inside the housing, shaft out of the top; all of it turns
    ghost_cyl(S, CORE_R, zi + 0.4, fl[0], ROTOR, a_front=0.28, a_back=0.18, edge=shade(SLIP, 1, 0.7), lw=0.7)
    for k, zc in enumerate(RING_Z):
        col = WIRES[k] if k < 4 else GOLD
        cyl(S, RING_R, zc - RING_H/2, zc + RING_H/2, col, n=48, edge=shade(col, 0.6), lw=0.6, stripe=th + k*0.9, stripe_color=shade(col, 0.45), stripe_px=2.0)
    cyl(S, SR['rotor_r'], fl[0], ROTOR_Z[1], ROTOR, n=28, edge=SLIP_D, lw=0.8, stripe=SLOT2 + th)
    # inside the rotor: each upper lead goes down to its own ring
    for k in range(4):
        q = th + k*np.pi/2
        P = [polar(2.0, q, fl[0]), polar(2.0, q, RING_Z[k]), polar(CORE_R, q, RING_Z[k])]
        S.line(P, WIRES[k], 2.4, outline=OUT_C, o_px=0.6)
    # brushes on the back-left wall, pressing on the front-left of each ring; leads down the wall and out of the bottom
    tip = a + math.radians(290)
    for k, zc in enumerate(RING_Z):
        root = a + math.radians(244 + 4*k)
        s = np.linspace(0, 1, 18)
        rr = (WALL_IN - 0.2)*(1 - s) + (RING_R + 0.08)*s + 0.5*np.sin(np.pi*s)
        qq = root + (tip - root)*s
        P = np.stack([rr*np.cos(qq), rr*np.sin(qq), np.full_like(s, zc)], -1)
        used = k < 4
        S.line(P, GOLD if used else '#a6acaf', 2.3, outline=OUT_C, o_px=0.6, bias=-0.2)
        if used:
            L = [polar(WALL_IN - 0.3, root, zc), polar(WALL_IN - 0.3, root, zi + 0.5), polar(2.2, root, zi + 0.5), polar(1.2, k*np.pi/2, z0 - 1.0),
                 polar(1.6, k*np.pi/2, z0 - 3.5), polar(1.6, k*np.pi/2, 34.0)]
            S.line(L, WIRES[k], 2.4, outline=OUT_C, o_px=0.6)
            glow = 0.55 + 0.35*math.sin(2*np.pi*(1.3*t + 0.25*k))
            S.dot(P[-1], 7.0, shade('#fff3b0', 1, 0.55*glow), bias=-0.6)
            S.dot(P[-1], 3.0, shade('#ffffff', 1, 0.95), bias=-0.7)
    # tube on the turntable with its slot; the rotor's leads ride in the slot and turn with it
    ghost_cyl(S, TUBE['ro'], TUBE['z0'], 99.0, TT, a_front=0.24, a_back=0.14, edge=TT_EDGE, lw=0.9)
    for s in (-1, 1):
        q = SLOT2 + th + s*0.24
        S.line([polar(TUBE['ro'], q, TUBE['z0']), polar(TUBE['ro'], q, 99.0)], TT_EDGE, 1.8, bias=-0.2)
    tv = np.array([-math.sin(SLOT2 + th), math.cos(SLOT2 + th)])
    rv = np.array([math.cos(SLOT2 + th), math.sin(SLOT2 + th)])
    for k in range(4):
        low = np.array([*(8.5*rv + (k - 1.5)*0.9*tv), 85.0])
        end = np.array([*((k - 1.5)*0.7*tv), ROTOR_Z[1]])
        P = np.vstack([bez(end, end + (0, 0, 2.5), low - (0, 0, 2.5), low, 16), np.linspace(low, low + (0, 0, 14), 8)[1:]])
        S.line(P, WIRES[k], 2.4, outline=OUT_C, o_px=0.6)
        # current: down one lead of each motor and back up the other
        sgn = -1 if k % 2 == 0 else 1
        for j in range(3):
            u = ((sgn*t*0.45 + j/3 + 0.13*k) % 1.0)
            S.dot(low + (0, 0, 1 + 12*u), 3.2, 'white', ec=WIRES[k], lw=1.4, bias=-0.5)
            S.dot(polar(1.6, k*np.pi/2, z0 - 4.0 - 11*u), 3.2, 'white', ec=WIRES[k], lw=1.4, bias=-0.5)
    return S


# ------------------------------------------------------------------ frame layout
CAM1, PPU1, Y0_1 = Cam(30, 15), 2.62, -24.0
PPU2, Y0_2 = 8.3, 30.5
RECT_L, RECT_R, RECT_2 = [0.0, 0.16, 0.5, 0.66], [0.5, 0.16, 0.5, 0.66], [0.0, 0.16, 1.0, 0.70]


def scene_axes(fig, rect, ppu, y0):
    ax = fig.add_axes(rect)
    ax.set_axis_off()
    w, h = rect[2]*W/ppu, rect[3]*H/ppu
    ax.set_xlim(-w/2, w/2)
    ax.set_ylim(y0, y0 + h)
    return ax


def label(ax, cam, P, text, xytext, color=INK, fs=10.5, ha='left', va='center', alpha=1.0, weight='normal'):
    ax.annotate(text, cam.xy(P), xytext, fontsize=fs, color=color, ha=ha, va=va, alpha=alpha, weight=weight, zorder=20,
                arrowprops=dict(arrowstyle='-', lw=0.8, color=color, alpha=alpha, shrinkA=2, shrinkB=1))


def turn_arrow(ax, cam, z=152.0, r=44.0, text='UPPER: turns'):
    P = arc(r, cam.a - math.radians(75), cam.a + math.radians(75), z, 40)
    s = cam.xy(P)
    ax.plot(s[:, 0], s[:, 1], color=TT, lw=2.4, solid_capstyle='round', zorder=21)
    t = unit(s[-1] - s[-3])
    nrm = np.array([-t[1], t[0]])
    tip = s[-1] + 4.5*t
    ax.add_patch(MPoly([tip, s[-1] - 1.0*t + 3.2*nrm, s[-1] - 1.0*t - 3.2*nrm], closed=True, fc=TT, ec=TT, zorder=21))
    ax.text(s[0, 0] - 4, s[0, 1] + 2, text, color=TT, fontsize=11, weight='bold', ha='right', va='bottom', zorder=21)


def header(fig, part):
    fig.patches.append(Rectangle((0, 0.936), 1, 0.064, transform=fig.transFigure, fc=INK, ec='none'))
    fig.text(0.014, 0.968, 'How a slip ring keeps the wires from winding up  ·  X1 swing concept', color='white',
             fontsize=16, weight='bold', va='center')
    fig.text(0.986, 0.968, PARTS[part]['title'], color='#c9d3d6', fontsize=13, va='center', ha='right')


def captions(fig, part, t):
    fig.patches.append(FancyBboxPatch((0.018, 0.016), 0.964, 0.118, boxstyle='round,pad=0.003,rounding_size=0.012',
                                      transform=fig.transFigure, fc='#edf2f3', ec='#c5cfd2', lw=1.0))
    for t0, t1, text in CAPTIONS[part]:
        al = smooth((t - t0)/0.35)*(1.0 if t1 >= PARTS[part]['dur'] else smooth((t1 - t)/0.35))
        if al > 0.01:
            fig.text(0.5, 0.075, '\n'.join(textwrap.wrap(text, 98)), ha='center', va='center', fontsize=15.5,
                     color=INK, alpha=al, linespacing=1.35)


def draw_part1(fig, t):
    th = move(t, 2.5, 17.5, 0.0, 3*2*np.pi)
    turns = th/(2*np.pi)
    fig.text(0.5, 0.905, f'The upper has turned {turns:.2f} times', ha='center', va='center', fontsize=15, color=TT, weight='bold')
    for mode, rect, title in (('direct', RECT_L, 'Wires straight through the centre'), ('slip', RECT_R, 'Wires through the slip ring')):
        ax = scene_axes(fig, rect, PPU1, Y0_1)
        scene_machine(CAM1, PPU1, mode, th).draw(ax)
        x = rect[0] + rect[2]/2
        fig.text(x, 0.866, title, ha='center', va='center', fontsize=15, weight='bold', color=INK)
        if mode == 'direct':
            col = BAD if turns > 0.04 else INK
            fig.text(x, 0.832, f'Twist in the wires: {turns:.2f} turns', ha='center', va='center', fontsize=13.5, color=col, weight='bold')
        else:
            fig.text(x, 0.832, 'Twist in the wires: none', ha='center', va='center', fontsize=13.5, color=GOOD, weight='bold')
        turn_arrow(ax, CAM1)
        ax.text(-118, -18, 'CHASSIS: does not turn', color=XF_EDGE, fontsize=11, weight='bold', ha='left', va='bottom')
        label(ax, CAM1, (-28, MOTOR_Y + 12, MOTOR_Z + 6), 'track motor', (66, -14), GREY, 10, ha='center')
        label(ax, CAM1, (-28, -MOTOR_Y - 12, MOTOR_Z + 6), 'track motor', (-66, -14), GREY, 10, ha='center')
        al = 1 - smooth((t - 2.6)/0.6)
        if al > 0.01:
            label(ax, CAM1, rot([-30, -22, 128.4], th), 'battery, receiver, drivers', (-112, 150), INK, 10.5, alpha=al)
        if mode == 'direct':
            if t > 6.5:
                al = smooth((t - 6.5)/0.5)
                p0, p1 = CAM1.xy((0, 0, CLAMP_Z[1] + 2)), CAM1.xy((0, 0, DECK_Z[0] - 14))
                xb = 20.0
                ax.plot([xb - 3, xb, xb, xb - 3], [p0[1], p0[1], p1[1], p1[1]], color=BAD, lw=1.6, alpha=al, zorder=20)
                ax.text(xb + 4, 0.5*(p0[1] + p1[1]), 'the twist\npiles up\nalong here', color=BAD, fontsize=10.5, va='center', ha='left', alpha=al, zorder=20)
            if turns > 1.9:
                al = smooth((turns - 1.9)/0.4)
                ax.text(0, 128 + 0*al, ' ', fontsize=1)
                fig.text(0.25, 0.20, 'After a few turns the wires pull tight and tear off', ha='center', va='center', fontsize=12.5,
                         color='white', weight='bold', alpha=al, bbox=dict(boxstyle='round,pad=0.4', fc=BAD, ec='none', alpha=0.92*al))
        else:
            label(ax, CAM1, (SR['body_r']*math.cos(CAM1.a + np.pi/2), SR['body_r']*math.sin(CAM1.a + np.pi/2), 58), 'slip ring', (50, 62), SLIP, 11, weight='bold')
            if t > 13.0:
                al = smooth((t - 13.0)/0.5)
                p0, p1 = CAM1.xy((0, 0, ROTOR_Z[1] + 2)), CAM1.xy((0, 0, DECK_Z[0] - 1))
                p2, p3 = CAM1.xy((0, 0, CLAMP_Z[1] + 2)), CAM1.xy((0, 0, BODY_Z[0] - 2))
                xb = 24.0
                for (q0, q1, col, txt) in ((p0, p1, TT, 'top half:\nturns with\nthe upper'), (p2, p3, XF_EDGE, 'bottom half:\nstays still')):
                    ax.plot([xb - 3, xb, xb, xb - 3], [q0[1], q0[1], q1[1], q1[1]], color=col, lw=1.6, alpha=al, zorder=20)
                    ax.text(xb + 4, 0.5*(q0[1] + q1[1]), txt, color=col, fontsize=10.5, va='center', ha='left', alpha=al, zorder=20, weight='bold')
    fig.lines.append(plt.Line2D([0.5, 0.5], [0.17, 0.885], transform=fig.transFigure, color='#d5dbdb', lw=1.2))
    fig.text(0.99, 0.142, 'Schematic: chassis and turntable see-through, carbody drawn taller, track motors drawn close in.',
             ha='right', va='bottom', fontsize=8.5, color=GREY)


def draw_part2(fig, t):
    th = move(t, 0.5, 17.5, 0.0, 3*2*np.pi)
    ax = scene_axes(fig, RECT_2, PPU2, Y0_2)
    scene_inside(th, t, PPU2).draw(ax)
    fig.text(0.5, 0.895, 'Inside the slip ring (housing and X-frame plate cut open)', ha='center', va='center', fontsize=15.5, weight='bold', color=INK)
    c, a = CAM2, CAM2.a
    left = a - np.pi/2
    def L(P, text, xy, col):
        label(ax, c, P, text, xy, col, 11.5, ha='right' if xy[0] < 0 else 'left', weight='bold')
    L(polar(TUBE['ro'], left, 93), 'tube on the turntable:\nits slot carries the leads round', (-30, 92.5), TT)
    L(polar(SR['rotor_r'], left, 77), 'rotor: turns with the upper', (-30, 82.5), TT)
    L(polar(RING_R, left, RING_Z[1]), 'rings: one for each wire', (-30, 64), TT)
    L(polar(RING_R, left, RING_Z[5]), '2 spare rings', (-30, 72), shade(GOLD, 0.75))
    L(polar(8.9, a + math.radians(282), RING_Z[0]), 'spring brushes press\non the rings', (-30, 48), shade(GOLD, 0.7))
    right = a + np.pi/2
    L(polar(30, right, 84.5), 'X-frame top plate', (34, 91), XF_EDGE)
    L(polar(18, right, FL_Z[1] - 0.5), 'housing: screwed to the X-frame,\nnever turns', (34, 75), SLIP_D)
    L(polar(9.0, a + math.radians(160), 85.0 + 9), 'leads from the drivers:\nturn with the upper', (34, 99), TT)
    L(polar(1.6, 0, 40.0), 'leads to the track motors:\nnever move', (34, 41), XF_EDGE)
    fig.text(0.99, 0.142, 'Inside drawn schematically. Outside sizes: SRC022A-6 datasheet (Ø22 × 19 body, Ø44 flange, 6 rings, 2 A each).',
             ha='right', va='bottom', fontsize=8.5, color=GREY)


def swing_limited(t):
    lim = math.radians(170)
    if t < 5.0:
        return move(t, 1.0, 4.0, 0.0, lim)
    if t < 11.0:
        return move(t, 5.0, 10.0, lim, -lim)
    return move(t, 11.0, 13.5, -lim, 0.0)


def draw_part3(fig, t):
    th = swing_limited(t)
    turns = th/(2*np.pi)
    ax = scene_axes(fig, RECT_L, PPU1, Y0_1)
    scene_machine(CAM1, PPU1, 'direct', th).draw(ax)
    turn_arrow(ax, CAM1, text='UPPER: swings')
    ax.text(-118, -18, 'CHASSIS: does not turn', color=XF_EDGE, fontsize=11, weight='bold', ha='left', va='bottom')
    fig.text(0.25, 0.866, 'Limited swing, no slip ring', ha='center', va='center', fontsize=15, weight='bold', color=INK)
    fig.text(0.25, 0.832, f'Twist in the wires: {turns:+.2f} turn', ha='center', va='center', fontsize=13.5, weight='bold',
             color='#ca6f1e' if abs(turns) > 0.02 else INK)
    # plan view: the upper's front direction, the allowed range and the end stop
    ax2 = fig.add_axes([0.56, 0.40, 0.38, 0.46])
    ax2.set_xlim(-1.5, 1.5)
    ax2.set_ylim(-1.32, 1.32)
    ax2.set_aspect('equal')
    ax2.set_axis_off()
    ax2.text(0, 1.30, 'Seen from above', ha='center', va='bottom', fontsize=12, color=GREY)
    ax2.add_patch(Circle((0, 0), 1.0, fc=shade(XF, 1, 0.22), ec=XF_EDGE, lw=1.4))
    q = np.radians(np.linspace(90 - 170, 90 + 170, 120))
    ax2.plot(1.13*np.cos(q), 1.13*np.sin(q), color=GOOD, lw=5, alpha=0.45, solid_capstyle='butt')
    hit = abs(abs(th) - math.radians(170)) < math.radians(1.5)
    ax2.add_patch(Wedge((0, 0), 1.24, 263, 277, width=0.24, fc=BAD, ec=shade(BAD, 0.7), lw=1.0, alpha=1.0 if hit else 0.75))
    ax2.text(0, -1.30, 'end stop on the chassis', ha='center', va='top', fontsize=11, color=BAD, weight='bold')
    ax2.add_patch(Circle((0, 0), 0.80, fc=shade(TT, 1, 0.20), ec=TT_EDGE, lw=1.4))
    fa = math.pi/2 + th
    ax2.annotate('', (0.98*math.cos(fa), 0.98*math.sin(fa)), (0, 0), arrowprops=dict(arrowstyle='-|>', lw=3, color=TT, mutation_scale=22))
    ax2.add_patch(Wedge((0, 0), 1.06, math.degrees(fa) - 6, math.degrees(fa) + 6, width=0.12, fc=INK, ec=INK))
    ax2.text(0, 1.17, 'front', ha='center', va='bottom', fontsize=10.5, color=GREY)
    ax2.text(1.33, 0.35, f'upper at\n{math.degrees(th):+.0f}°', ha='left', va='center', fontsize=12.5, color=TT, weight='bold')
    if hit:
        ax2.text(-1.33, -0.62, 'stop:\nswing back', ha='right', va='center', fontsize=12.5, color=BAD, weight='bold')
    rows = [(GOOD, 'Slip ring: turns without limit, like the Cat 320. Needs the bought ring and 3 small bosses.'),
            ('#ca6f1e', 'Limited swing: no extra part, but the upper stays within about ±170° and swings back.')]
    for k, (col, text) in enumerate(rows):
        y = 0.315 - 0.075*k
        fig.patches.append(Circle((0.548, y), 0.006, transform=fig.transFigure, fc=col, ec='none'))
        fig.text(0.56, y, '\n'.join(textwrap.wrap(text, 62)), ha='left', va='center', fontsize=12, color=INK, linespacing=1.3)
    fig.lines.append(plt.Line2D([0.5, 0.5], [0.17, 0.885], transform=fig.transFigure, color='#d5dbdb', lw=1.2))


def draw_summary(fig, t):
    fig.text(0.06, 0.84, 'In short', fontsize=26, weight='bold', color=INK, va='center')
    rows = [(BAD, 'Wires straight through the swing centre twist once for every turn of the upper, and soon tear off.'),
            (GOOD, 'A slip ring cuts each wire in two. The top half turns with the upper, the bottom half stays with the chassis, '
                   'and rings and brushes carry the current across at any angle.'),
            (SLIP, 'X1 proposal: SRC022A-6, 6 rings rated 2 A each. The two track motors use 4 (1.3 A each at stall); 2 are spare. '
                   'The housing is screwed under the X-frame top plate; a tube on the turntable turns the rotor.'),
            ('#ca6f1e', 'The other option: a limited swing of about ±170° with a loose loop of soft wire, and no slip ring.')]
    for k, (col, text) in enumerate(rows):
        y = 0.70 - 0.145*k
        fig.patches.append(Circle((0.075, y), 0.011, transform=fig.transFigure, fc=col, ec='none'))
        fig.text(0.10, y, '\n'.join(textwrap.wrap(text, 100)), ha='left', va='center', fontsize=16, color=INK, linespacing=1.35)
    fig.text(0.06, 0.12, 'Still your choice: slip ring or limited swing.', fontsize=15, color=GREY, style='italic', va='center')


def locate(tg):
    t0 = 0.0
    for k, p in enumerate(PARTS):
        if tg < t0 + p['dur'] or k == len(PARTS) - 1:
            return k, tg - t0
        t0 += p['dur']


def draw_frame(fig, tg):
    part, t = locate(tg)
    fig.clf()
    fig.patch.set_facecolor(BG)
    header(fig, part)
    (draw_part1, draw_part2, draw_part3, draw_summary)[part](fig, t)
    if CAPTIONS[part]:
        captions(fig, part, t)


_FIG = None


def frame_rgb(i):
    global _FIG
    if _FIG is None:
        _FIG = plt.figure(figsize=(W/DPI, H/DPI), dpi=DPI)
    draw_frame(_FIG, i/FPS)
    _FIG.canvas.draw()
    return np.asarray(_FIG.canvas.buffer_rgba())[..., :3].tobytes()


# ------------------------------------------------------------------ video and check
def encode(n_frames, workers):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    starts = np.cumsum([0.0] + [p['dur'] for p in PARTS])
    meta = ';FFMETADATA1\ntitle=X1 swing concept: how a slip ring keeps the wires from winding up\n'
    for k, p in enumerate(PARTS):
        meta += f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={int(starts[k]*1000)}\nEND={int(starts[k + 1]*1000)}\ntitle={p['title']}\n"
    chap = Path('/tmp/x1_slip_anim_chapters.ffmeta')
    chap.write_text(meta)
    pending = VIDEO.with_suffix('.pending.mp4')
    cmd = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
           '-r', str(FPS), '-i', '-', '-i', str(chap), '-map', '0:v:0', '-map_metadata', '1', '-map_chapters', '1',
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an', str(pending)]
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with multiprocessing.get_context('fork').Pool(workers) as pool:
        for i, buf in enumerate(pool.imap(frame_rgb, range(n_frames), chunksize=5)):
            enc.stdin.write(buf)
            if i % 250 == 0:
                print(f'frame {i}/{n_frames}', flush=True)
    enc.stdin.close()
    if enc.wait() != 0:
        raise SystemExit('ffmpeg failed')
    pending.replace(VIDEO)


def check(n_frames):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    dec = subprocess.run([ffmpeg, '-hide_banner', '-v', 'error', '-nostats', '-progress', 'pipe:1', '-i', str(VIDEO), '-map', '0:v:0',
                          '-f', 'null', '-'], check=True, capture_output=True, text=True)
    assert not dec.stderr.strip(), dec.stderr
    values = dict(line.split('=', 1) for line in dec.stdout.splitlines() if '=' in line)
    reader = imageio_ffmpeg.read_frames(str(VIDEO))
    info = next(reader)
    reader.close()
    chapters = subprocess.run([ffmpeg, '-hide_banner', '-v', 'error', '-i', str(VIDEO), '-f', 'ffmetadata', '-'],
                              check=True, capture_output=True, text=True).stdout
    result = dict(status='PASS', file=VIDEO.name, frames_decoded=int(values['frame']), frames_expected=n_frames,
                  duration_s=info['duration'], fps=info['fps'], size=list(info['size']), chapters=chapters.count('[CHAPTER]'),
                  bytes=VIDEO.stat().st_size, sha256=hashlib.sha256(VIDEO.read_bytes()).hexdigest(), decode_errors=[],
                  scope='Whole file decoded without errors; frame count, size, frame rate and chapters checked. '
                        'The pictures were reviewed by eye; the drawing is schematic.')
    ok = (result['frames_decoded'] == n_frames and result['size'] == [W, H] and abs(result['fps'] - FPS) < 0.01
          and result['chapters'] == len(PARTS))
    result['status'] = 'PASS' if ok else 'FAIL'
    CHECK.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    if not ok:
        raise SystemExit('video check failed')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stills', help='comma-separated times in seconds: write PNG stills instead of the video')
    ap.add_argument('--dir', default='/tmp/x1_slip_anim', help='folder for the stills')
    ap.add_argument('--workers', type=int, default=3)
    args = ap.parse_args()
    n = int(round(sum(p['dur'] for p in PARTS)*FPS))
    if args.stills:
        out = Path(args.dir)
        out.mkdir(parents=True, exist_ok=True)
        fig = plt.figure(figsize=(W/DPI, H/DPI), dpi=DPI)
        for s in args.stills.split(','):
            draw_frame(fig, float(s))
            fig.savefig(out / f'still_{float(s):05.1f}.png', dpi=DPI)
            print('wrote', out / f'still_{float(s):05.1f}.png')
        return
    encode(n, args.workers)
    check(n)


if __name__ == '__main__':
    main()

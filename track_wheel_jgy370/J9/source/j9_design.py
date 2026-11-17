"""J9 JGY-370 single track: layout, exact chain closure and derived positions (mm).

Frame: X along the track (sprocket at the rear, X -110), Y across (-Y = motor and
vehicle side), Z up, Z 0 = ground (grouser tips of the ground run).

J9 change after the concept review: the ground run is flat. Sprocket, idler and all
five road rollers sit on one line; only the two support rollers lift the track.
Chain, pins, bushings and sprocket tooth form are unchanged from Track R4/R5/J8.
"""
import math
import numpy as np
from scipy.optimize import brentq

# ---- chain and end wheels (unchanged R4/R5/J8 values) ----
PITCH, TEETH, LINKS = 20.0, 12, 34
PITCH_R = PITCH / (2 * math.sin(math.pi / TEETH))       # 38.637
APOTHEM = PITCH_R * math.cos(math.pi / TEETH)           # 37.321
SPROCKET_TIP_R = APOTHEM + 3.5                          # 40.821
SPROCKET_HALF_T = 8.5      # the sprocket stays 17 mm thick (unchanged R4/R5/J8 tooth form)
# Chain joint, J910 revision B (2026-11-14). The 2026-11-14 pre-print review found three faults in the inherited R4 link:
# the grooved pin floated 5.2 mm either way, so an E-clip could sit under a roller flange; the Ø8 ends cleared the next
# shoe plate by 0.045 mm; and the sprocket had 0.2 mm a side between the inner ears. Each joint is now an ISO 4762
# M3 x 60 partly threaded screw and a DIN 985 M3 nyloc nut (agreed with the user on 2026-11-14). Head and nut seat on
# low bosses on the outer plates, 2 mm outboard of the roller flanges, so the screw cannot slide. M3 x 50 is too short:
# the seats are 50 mm apart before the nut starts, and the smooth shank has to reach past the far inner ear.
BUSH_R, BUSH_BORE_R, BUSH_HALF_L = 3.0, 1.6, 9.0   # stock sleeve Ø6 x Ø3.2 x 18 (a 17 mm one also fits)
PIN_R = 1.5                                         # M3 shank; the link holes stay Ø3.2
LINK_PLATE_Y = (14.0, 21.0)                         # outer plates
LINK_EAR_Y = (9.2, 13.7)                            # inner ears 4.5 thick, 18.4 apart: 0.2 a side for the sleeve, 0.7 for the sprocket
LINK_RELIEF_R = 4.6                                 # about both pin axes: 0.6 mm to the next link's Ø8 ends
# Seat boss on the outer face of each outer plate: the lower part of the Ø8 plate end plus a web onto the shoe plate,
# cut off 0.8 mm above the pin axis so that the roller flanges (2.0 mm above the axis) pass 1.2 mm over it.
LINK_BOSS = dict(y=(21.0, 25.0), top=0.8, web_x=-5.0)
LINK_EAR_CHAMFER, LINK_RAIL_CHAMFER = 1.0, 0.8      # lead-ins for the sprocket teeth and for the roller / idler flanges
GROUSER_X = (-8.4, 0.0, 8.4)                        # outer grousers at the plate edges: the underside bridges 6.4 mm, no hanging strip
TRACK_SCREW = dict(length=60.0, head_r=2.75, head_k=3.0, thread=18.0)   # head outboard (+Y on the left track), tip at the shoe edge
TRACK_NUT = dict(af=5.5, m=4.0)
SCREW_SEAT_Y = LINK_BOSS['y'][1]                    # 25: head seat (+Y) and nut seat (-Y)
RAIL_FACE = 4.0            # link running face, inside the pin line
SHOE_OUT = 7.0             # grouser tips, outside the pin line
LINK_HALF_W = 21.0         # outer face of the outer link plates
IDLER_R, IDLER_RAIL_R = 35.24, 33.17

# ---- J9 layout ----
GROUND_PIN_Z = SHOE_OUT                        # 7: pin line of the flat ground run
AXLE_Z = GROUND_PIN_Z + APOTHEM                # 44.321 (concept: 46.321 with a 2 mm end rise)
TOP_Z = AXLE_Z + APOTHEM                       # pin line over the sprocket and idler tops
DRIVE_X = -110.0
TOP_LIFT = 3.5                                 # support rollers lift the top-run pin line
SHOE_W = 70.0
ROLLER_R, FLANGE_R, ROLLER_HALF_W, FLANGE_IN = 11.0, 13.0, 23.0, 21.6
ROAD_X = [-58.0, -29.0, 0.0, 29.0, 58.0]
ROAD_Z = GROUND_PIN_Z + RAIL_FACE + ROLLER_R   # 22: tangent to the ground run, flush with the end wheels
CARRIER_X = [-35.0, 35.0]

# ---- frame ----
WALL_IN, WALL_T = 24.0, 6.0                    # wall inner face |Y| and thickness
WALL_OUT = WALL_IN + WALL_T                    # 30
WALL_BODY_Z = (28.0, 74.0)
DRIVE_LOBE_R, IDLER_LOBE_R = 29.0, 26.0
ROAD_EAR_R, CARRIER_EAR_R = 8.5, 7.0
WEB_X, WEB_Z = (-66.0, 36.0), (37.0, 55.0)
SPIGOT_R, SPIGOT_L = 5.5, 4.0                  # spring pilots (spring ID 11.58)

# ---- tensioner (R5 spring kept) ----
INCH = 25.4
SPRING = dict(model='Associated/Lee Spring C-600-072-1500, music wire', od=.600*INCH, wire=.072*INCH,
              free=1.500*INCH, rate=35.89*4.4482216/INCH, max_load=26.48*4.4482216, solid=.670*INCH)
SPRING['id'] = SPRING['od'] - 2*SPRING['wire']
SPRING_SET = 25.8                              # fitted length, as R5/J8: 77 N preload
RECOIL = 4.2                                   # idler recoil to the mechanical stop
# J9 rev B: spring contained in an axial pocket in the main web. The yoke's rear
# piston preserves the original crossbar position and spring preload/travel.
SPRING_POCKET = dict(recess=8.0, bore_d=16.4, outer_d=21.2, piston_d=15.6,
                     rear_wall=2.0, yoke_gap_at_recoil=0.8)
YOKE_BASE_T, ARM_T, ARM_HALF_Z = 8.0, 3.0, 8.0
GROOVE_CLEAR = 0.2                             # yoke arms in the wall grooves, above and below
GROOVE_SIDE_CLEAR = 0.5                        # ... and sideways (0.2 until 2026-11-14): the inner wall's groove floor prints on support
PIN_TRACK_FLOOR = WALL_IN + ARM_T + 1.2        # 28.2: floor of the idler-pin tracks in the groove floors (unchanged)
IDLER_PIN = dict(d=8.0, length=55.0)           # ISO 2338 8 m6 x 55 steel pin

# ---- drive ----
GEARBOX_FACE_Y = -WALL_OUT                     # gearbox face flat on the inner wall
MOTOR_HOLES = [(DRIVE_X + x, AXLE_Z + z) for x in (-9.0, 24.0) for z in (-9.0, 9.0)]
SHAFT_TIP_Y = GEARBOX_FACE_Y + 15.6            # -14.4
SHAFT_FLAT = dict(across=5.5, length=12.0)     # D-flat 0.5 deep, running 12 mm back from the tip (JGY-370 drawing)
# Bought Ø32 / Ø6 aluminium flange coupling (the Pololu #1999 hub could not be bought, 2026-11-12). Sizes from the
# seller's drawing (../../references/flange_coupling_32/), each one confirmed on the part by the user: flange Ø32 x 4 with
# 6 x M3 tapped holes on Ø23, boss Ø14 x 10 (14 overall), Ø6 bore, one radial M3 set screw in the boss 5 mm from its
# end, halfway between two flange holes, flat flange face.
HUB = dict(flange_r=16.0, flange_t=4.0, boss_r=7.0, boss_h=10.0, bore_r=3.0, pcd_r=11.5)
HUB_FACE_Y = -WALL_IN + 1.0 + HUB['flange_t'] + HUB['boss_h']   # -9.0: flange face on the sprocket; boss end at -23.0, 1.0 from the wall
HUB_SCREW_DEG = (0, 120, 240)                  # 3 of the 6 holes carry the sprocket; the set screw points up (+Z), between the 60 and 120 deg holes
HUB_SCREW_L = 20.0                             # ISO 4762 M3 x 20 from the sprocket's outer face: 4 mm of thread, tip 1.5 mm past the flange
HUB_SET_SCREWS = ((HUB['flange_t'] + HUB['boss_h'] - 5.0, 4.0),)   # (depth from the flange face, M3 set screw length): one, 9.0 deep
HUB_RECESS = dict(r=16.2, depth=1.0)           # centres the Ø32 flange in the sprocket's inner face
SPROCKET_Y = (HUB_FACE_Y - HUB_RECESS['depth'], 8.5)   # recess rim, outer disc face (bed face when printed)
SPROCKET_HUB_R = 18.5                          # ring round the recess, 1.5 mm proud of the tooth disc
STOP_PAD = dict(r=2.7, y=(SHAFT_TIP_Y, HUB_FACE_Y))    # printed pad down the coupling bore to the shaft end (5.4 long)
SOCKET = dict(r=5.05, depth=5.0)               # journal plug seat in the sprocket's outer face
PLUG = dict(r=4.975, bore=1.7, y=(SPROCKET_Y[1] - SOCKET['depth'], WALL_OUT))
B6800 = dict(d=10.0, D=19.0, B=5.0)
B6800_Y = (WALL_OUT - B6800['B'], WALL_OUT)    # seat open to the outside, 1 mm lip behind
B624 = dict(d=4.0, D=13.0, B=5.0)
B608 = dict(d=8.0, D=22.0, B=7.0)

# ---- housing ----
SKIRT_Y = (-38.0, -35.5)
# Chassis mounting dimensions are in j9_mounts.py (two supported side plates).


# ================================================================ chain closure
def _polar(cx, cz, r, deg):
    t = math.radians(deg)
    return np.array([cx + r*math.cos(t), cz + r*math.sin(t)])


def sprocket_pins(phase=0.0):
    """Pins engaged on the sprocket, CCW from the top-front pin (75 deg) to the bottom-front pin (285 deg)."""
    return [_polar(DRIVE_X, AXLE_Z, PITCH_R, a + phase) for a in range(75, 286, 30)]


def idler_pins(xi, phi):
    """Eight pins on the idler pitch circle, CCW from the bottom-rear pin to the top-rear pin."""
    return [_polar(xi, AXLE_Z, PITCH_R, -105.0 + phi + 30*j) for j in range(8)]


def _bisect(f, lo, hi, n=None):
    """Root of f in [lo, hi] (Brent's method)."""
    return brentq(f, lo, hi, xtol=1e-12, rtol=1e-15, maxiter=200)


def _point_on(path, s):
    """Point at arc length s; beyond the end the last segment is extended."""
    segs = list(zip(path[:-1], path[1:]))
    for k, (a, b) in enumerate(segs):
        L = float(np.linalg.norm(b - a))
        if s <= L or k == len(segs) - 1: return a + (b - a)*s/L
        s -= L


def _length(path):
    return sum(float(np.linalg.norm(b - a)) for a, b in zip(path[:-1], path[1:]))


def _walk(path, n):
    """n chords of PITCH along a polyline from its first point. Returns pins and overshoot."""
    pins, s = [path[0]], 0.0
    for _ in range(n):
        p = pins[-1]
        s = _bisect(lambda t: float(np.linalg.norm(_point_on(path, t) - p)) - PITCH, s, s + PITCH + 2)
        pins.append(_point_on(path, s))
    return pins, s - _length(path)


def _idler_phase(xi):
    last_flat = np.array([DRIVE_X + 10 + 9*PITCH, GROUND_PIN_Z])     # ninth flat link ends at X 80
    return _bisect(lambda phi: float(np.linalg.norm(idler_pins(xi, phi)[0] - last_flat)) - PITCH, -8.0, 8.0)


def _top(xi, h):
    phi = _idler_phase(xi)
    start = idler_pins(xi, phi)[-1]
    path = [start, np.array([CARRIER_X[1], TOP_Z + h]), np.array([CARRIER_X[0], TOP_Z + h]), sprocket_pins()[0]]
    pins, over = _walk(path, 10)
    return phi, pins, over


def _idler_x(h):
    # over > 0: chain longer than the path -> the spring pushes the idler forward
    return _bisect(lambda xi: _top(xi, h)[2], 105.0, 115.0)


def loop(h):
    xi = _idler_x(h)
    phi, top, over = _top(xi, h)
    pins = sprocket_pins()                                               # 8 pins, 75..285 deg
    pins += [np.array([DRIVE_X + 10 + PITCH*k, GROUND_PIN_Z]) for k in range(1, 10)]
    pins += idler_pins(xi, phi)
    pins += top[1:-1]
    return xi, phi, np.array(pins)


def running_faces(pins):
    """Running-face segment of every link (offset RAIL_FACE toward the loop interior)."""
    out = []
    for i in range(len(pins)):
        a, b = pins[i], pins[(i + 1) % len(pins)]
        t = (b - a)/np.linalg.norm(b - a); n = np.array([-t[1], t[0]])   # CCW loop: left normal is inside
        out.append((a + n*RAIL_FACE, b + n*RAIL_FACE))
    return out


def seg_dist(p, a, b):
    ab = b - a; t = np.clip(np.dot(p - a, ab)/np.dot(ab, ab), 0, 1)
    return float(np.linalg.norm(p - (a + t*ab)))


def carrier_z(pins, x):
    faces = [f for f in running_faces(pins) if min(f[0][1], f[1][1]) > AXLE_Z + 20]
    return _bisect(lambda z: min(seg_dist(np.array([x, z]), a, b) for a, b in faces) - ROLLER_R, AXLE_Z, TOP_Z)


def solve():
    def lift_err(h):
        xi, phi, pins = loop(h)
        zc = min(carrier_z(pins, x) for x in CARRIER_X)
        return zc + ROLLER_R + RAIL_FACE - TOP_Z - TOP_LIFT
    h = _bisect(lift_err, 2.0, 6.0, n=60)
    xi, phi, pins = loop(h)
    zc = [carrier_z(pins, x) for x in CARRIER_X]
    return dict(h=h, idler_x=xi, idler_phase_deg=phi, pins=pins, carrier_z=min(zc), carrier_z_each=zc)


SOLUTION = solve()
PINS = SOLUTION['pins']
IDLER_X = SOLUTION['idler_x']
CARRIER_Z = SOLUTION['carrier_z']
IDLER_LIMITS = (IDLER_X - RECOIL, IDLER_X)

# ---- tensioner positions derived from the solved idler ----
SPRING_X0 = WEB_X[1] - SPRING_POCKET['recess']          # recessed spring seat
YOKE_BASE_X = (WEB_X[1] + SPRING_SET, WEB_X[1] + SPRING_SET + YOKE_BASE_T)
SPRING_GUIDE_X = (SPRING_X0 - SPRING_POCKET['rear_wall'],
                  YOKE_BASE_X[0] - RECOIL - SPRING_POCKET['yoke_gap_at_recoil'])
YOKE_ARM_END = IDLER_X + 8.0
GROOVE_X0 = YOKE_BASE_X[0] - RECOIL                    # recoil stop: arm ends meet the groove end
# Lock pin for fitting the chain (2026-11-14): with the yoke on its recoil stop, a Ø3.2 hole through the outer wall lines up
# with a blind hole in each end of the yoke crossbar. One of the M3 x 60 track screws dropped in holds the idler back.
LOCK_PIN = dict(r=1.6, x=GROOVE_X0 + YOKE_BASE_T/2, depth=8.0)


def check():
    p = PINS; n = len(p)
    L = [float(np.linalg.norm(p[(i+1) % n] - p[i])) for i in range(n)]
    ground = [q for q in p if abs(q[1] - GROUND_PIN_Z) < 1e-9]
    top = [q for q in p if q[1] > AXLE_Z + 20]
    return dict(links=n, link_error_mm=max(abs(x - PITCH) for x in L), path_apex_h=SOLUTION['h'],
                idler_x=IDLER_X, idler_phase_deg=SOLUTION['idler_phase_deg'], carrier_z=SOLUTION['carrier_z_each'],
                top_lift=CARRIER_Z + ROLLER_R + RAIL_FACE - TOP_Z, top_pin_max_z=max(q[1] for q in top),
                track_top_z=max(q[1] for q in top) + SHOE_OUT, ground_pins_x=[min(q[0] for q in ground), max(q[0] for q in ground)],
                lowest_pin_z=min(q[1] for q in p), spring_preload_N=(SPRING['free'] - SPRING_SET)*SPRING['rate'],
                spring_at_recoil_N=(SPRING['free'] - SPRING_SET + RECOIL)*SPRING['rate'], spring_solid=SPRING['solid'])


if __name__ == '__main__':
    import json
    print(json.dumps(check(), indent=1, default=float))

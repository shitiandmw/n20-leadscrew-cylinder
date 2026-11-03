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
BUSH_R, BUSH_HALF_L = 3.0, 8.5
PIN_R, PIN_HALF_L, CLIP_Y = 1.5, 28.0, 26.5
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
YOKE_BASE_T, ARM_T, ARM_HALF_Z = 8.0, 3.0, 8.0
GROOVE_CLEAR = 0.2
IDLER_PIN = dict(d=8.0, length=55.0)           # ISO 2338 8 m6 x 55 steel pin

# ---- drive ----
GEARBOX_FACE_Y = -WALL_OUT                     # gearbox face flat on the inner wall
MOTOR_HOLES = [(DRIVE_X + x, AXLE_Z + z) for x in (-9.0, 24.0) for z in (-9.0, 9.0)]
SHAFT_TIP_Y = GEARBOX_FACE_Y + 15.6            # -14.4
SHAFT_FLAT = dict(across=5.5, length=12.0)     # D-flat 0.5 deep, running 12 mm back from the tip (JGY-370 drawing)
# Bought Pololu #1999 universal aluminium hub (6 mm bore, 6 x M3), from its drawing (pololu.com/file/0J667)
# and STEP (pololu.com/file/0J1153). Two radial M3 set screws at the same angle: flange mid-plane and boss mid-height.
HUB = dict(flange_r=12.7, flange_t=5.0, boss_r=6.0, boss_h=4.2, bore_r=3.0, pcd_r=9.525, tap_r=1.25)
HUB_FACE_Y = -13.8                             # flange face on the sprocket; boss end at -23.0, 1.0 from the wall
HUB_SCREW_DEG = (0, 120, 240)                  # 3 of the 6 hub holes carry the sprocket; set screws point up (+Z)
HUB_SET_SCREWS = ((2.5, 8.0), (7.1, 3.0))      # (depth from the flange face, M3 set screw length) flange, boss
HUB_RECESS = dict(r=12.9, depth=1.0)           # centres the Ø25.4 flange in the sprocket's inner face
SPROCKET_Y = (HUB_FACE_Y - HUB_RECESS['depth'], 8.5)   # recess rim, outer disc face (bed face when printed)
SPROCKET_HUB_R = 15.0
STOP_PAD = dict(r=2.7, y=(SHAFT_TIP_Y, HUB_FACE_Y))    # printed pad inside the hub bore that meets the shaft end
SOCKET = dict(r=5.05, depth=5.0)               # journal plug seat in the sprocket's outer face
PLUG = dict(r=4.975, bore=1.7, y=(SPROCKET_Y[1] - SOCKET['depth'], WALL_OUT))
B6800 = dict(d=10.0, D=19.0, B=5.0)
B6800_Y = (WALL_OUT - B6800['B'], WALL_OUT)    # seat open to the outside, 1 mm lip behind
B624 = dict(d=4.0, D=13.0, B=5.0)
B608 = dict(d=8.0, D=22.0, B=7.0)

# ---- housing ----
SKIRT_Y = (-38.0, -35.5)
CHASSIS_X, CHASSIS_Z, CHASSIS_Y = [-60.0, 0.0, 60.0], (62.0, 74.0), (-46.0, -WALL_OUT)
CHASSIS_HALF_X = 6.0


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
SPRING_X0 = WEB_X[1]                                   # spring seat on the web front face
YOKE_BASE_X = (SPRING_X0 + SPRING_SET, SPRING_X0 + SPRING_SET + YOKE_BASE_T)
YOKE_ARM_END = IDLER_X + 8.0
GROOVE_X0 = YOKE_BASE_X[0] - RECOIL                    # recoil stop: arm ends meet the groove end


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

"""Which stroke suits the real lever arms? For each stock-able stroke s (closed s + 80, open 2 s + 80)
find the best base pin for the boom (real rod pin B, range -35..+50 deg, base above the turntable
deck) and for the stick with the real tail D. Used for the actuator table on sheet 2."""
import math
import numpy as np
import reference_cat as rc
import r12_design as d

P = rc.REF_PINS
BOOM_BASE_OK = lambda b: -30 <= b[0] <= 70 and -50 <= b[1] <= -8          # inside the foot bracket, above the deck
STICK_BASE_BAND = (1.0, 16.0)                                              # base 1..16 mm above the boom top


def _boom_top(x):
    from shapely.geometry import LineString
    return LineString([(x, -300), (x, 300)]).intersection(d.boom_profile()).bounds[3]


def best_base(rod_local, origin, base_ok, lo, hi, s, step=0.5):
    """Base pin giving full stroke s exactly over lo -> hi (deg), monotonic, with the largest minimum lever."""
    c, o = s + 80.0, 2 * s + 80.0
    p1 = origin + d.rot(math.radians(lo)) @ rod_local
    p2 = origin + d.rot(math.radians(hi)) @ rod_local
    sgn = 1 if hi > lo else -1
    angs = np.radians(np.arange(lo, hi + sgn * step, sgn * step))
    best = None
    for side in (1, -1):
        b = d.circ(p1, c, p2, o, side)
        if b is None or not base_ok(b):
            continue
        cs, sn = np.cos(angs), np.sin(angs)
        pts = origin + np.stack([cs * rod_local[0] - sn * rod_local[1], sn * rod_local[0] + cs * rod_local[1]], 1)
        L = np.linalg.norm(pts - b, axis=1)
        if np.any(np.diff(L) <= 0):
            continue
        lev = float(np.abs(np.gradient(L, angs)).min())
        if best is None or lev > best[0]:
            best = (round(lev, 1), [round(float(x), 1) for x in b])
    return best


def study(strokes=(40, 55, 60, 65, 70, 80, 85)):
    E = np.array([d.BOOM, 0.0])
    stick_ok = lambda b: (140 <= b[0] <= 300 and _boom_top(b[0]) + STICK_BASE_BAND[0] <= b[1]
                          <= _boom_top(b[0]) + STICK_BASE_BAND[1])
    rows = []
    for s in strokes:
        boom = best_base(P['B_boom'], np.zeros(2), BOOM_BASE_OK, -35, 50, s)
        stick = {span: best_base(P['D_stick'], E, stick_ok, -35, -35 - span, s) for span in (90, 95, 100)}
        st = max(((k, v) for k, v in stick.items() if v), key=lambda kv: kv[0], default=None)
        rows.append(dict(stroke=s, screw=s + 15, closed=s + 80, open=2 * s + 80,
                         euler_N=round(561 * (77.5 / (s + 17.5)) ** 2),
                         boom_lever=boom[0] if boom else None, boom_base=boom[1] if boom else None,
                         stick_real_tail_span=st[0] if st else None, stick_real_tail_lever=st[1][0] if st else None))
    return rows


if __name__ == '__main__':
    for r in study():
        print(r)

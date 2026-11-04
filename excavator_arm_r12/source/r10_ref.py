"""R10 reference (excavator_arm_dual/) for like-for-like comparison: 2D side outlines rebuilt from
its build_arm.py recipes, and static holding forces from its own kinematics and mass report."""
import importlib.util
import json
import math
import itertools
from pathlib import Path
import numpy as np
from shapely.geometry import Point, Polygon, LineString
from shapely.ops import unary_union
from shapely import affinity

ROOT = Path(__file__).resolve().parents[2] / 'excavator_arm_dual'
_spec = importlib.util.spec_from_file_location('r10_kinematics', ROOT / 'source' / 'kinematics.py')
K = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(K)
MASS = json.loads((ROOT / 'simulation' / 'mass_properties.json').read_text())['groups']


def _c(x, z, r):
    return Point(x, z).buffer(r, 48)


def _chain(points, radii):
    return unary_union([unary_union([_c(*points[i], radii[i]), _c(*points[i + 1], radii[i + 1])]).convex_hull
                        for i in range(len(points) - 1)]).buffer(0)


def _hull(pts, r):
    return unary_union([_c(*p, r) for p in pts]).convex_hull


def outlines():
    boom = _chain(K.BOOM_PROFILE_POINTS, K.BOOM_PROFILE_RADII).union(_c(0, 0, 11))
    bx, bz = K.BOOM_LIFT
    boom = boom.union(_chain([(bx + 19, bz + 28), (bx + 32, bz + 32)], [12, 12]))
    boom = boom.union(_chain([(bx, bz), (bx + 24, bz + 25)], [10, 15]))
    cx, cz = K.STICK_CYL
    boom = boom.union(Polygon([(cx - 12, cz - 26), (cx + 12, cz - 26), (cx + 12, cz - 18), (cx - 12, cz - 18)]))
    boom = boom.union(_hull([(cx, cz), (cx, cz - 22)], 7))
    stick = _chain([tuple(K.STICK_TAIL), (0, 0), (84, 0), (152, 0), (K.STICK, 0)], [12, 20, 16, 14, 14])
    fx, fz = K.BUCKET_CYL
    stick = stick.union(_hull([(fx, fz), (fx, fz - 18)], 7)).union(_hull([tuple(K.ROCKER_PIVOT), (K.ROCKER_PIVOT[0], 3)], 9))
    back = [(x * .8, z * .8) for x, z in [(-7, -22), (30, -24), (56, -42), (55, -73), (30, -96), (-28, -102), (-89, -77)]]
    bucket = LineString(back).buffer(2, cap_style=2, join_style=1).union(Polygon(back))
    horn = unary_union([_hull([(0, 0), tuple(K.HORN_POINT)], 11), Polygon([(-10, -5), (-10, -30), (44, -30), (43, -7), (10, 8)])])
    bucket = bucket.union(horn).difference(Polygon([(-100, -120), (-61.5, -120), (-61.5, -40), (-100, -40)]))
    tooth = Polygon([(-63, -60.8), (-63, -66.8), (float(K.TIP[0]), float(K.TIP[1])), (float(K.TIP[0]), float(K.TIP[1]) + .9)])
    bucket = bucket.union(tooth)
    tower = unary_union([Polygon([(-23, 10), (24, 10), (18, 88), (-18, 88), (-23, 76)]), _c(0, 88, 16)])
    base = unary_union([Polygon([(-44, 0), (88, 0), (88, 10), (-44, 10)]), tower])
    return dict(base=base, boom=boom, stick=stick, bucket=bucket)


def placed(strokes):
    st = K.solve(strokes)
    o = outlines()
    out = {'base': o['base']}
    for g in ('boom', 'stick', 'bucket'):
        x = affinity.rotate(o[g], math.degrees(st['angles'][g]), origin=(0, 0))
        out[g] = affinity.translate(x, *st['origins'][g])
    return st, out


def _world(local, origin, angle):
    c, s = math.cos(angle), math.sin(angle)
    return np.array(origin) + np.array([c * local[0] - s * local[1], s * local[0] + c * local[1]])


def potential(strokes, payload=0.150):
    st = K.solve(strokes)
    V = 0.0
    for g in ('boom', 'stick', 'bucket', 'rocker', 'coupler'):
        m = MASS[g]['mass_kg']
        c = np.array(MASS[g]['centre_m'])[[0, 2]] * 1000
        V += m * 9.81 * _world(c, st['origins'][g], st['angles'][g])[1]
    cb = np.array(MASS['bucket']['centre_m'])[[0, 2]] * 1000
    V += payload * 9.81 * _world(cb, st['origins']['bucket'], st['angles']['bucket'])[1]
    P = st['points']
    for a, b, k in (('A', 'B', 2), ('C', 'D', 1), ('F', 'R', 1)):
        u = (P[b] - P[a]) / np.linalg.norm(P[b] - P[a])
        V += k * 9.81 * (0.051 * (P[a] + 75.6 * u)[1] + 0.006 * (P[b] - 10.1 * u)[1])
    return V / 1000


def hold_forces(payload=0.150, grid=np.linspace(0, 60, 13)):
    worst = [0.0, 0.0, 0.0]
    for st in itertools.product(grid, repeat=3):
        for i in range(3):
            p, m = list(st), list(st)
            p[i] = min(60, p[i] + .05)
            m[i] = max(0, m[i] - .05)
            try:
                f = (potential(p, payload) - potential(m, payload)) / ((p[i] - m[i]) / 1000) / (2 if i == 0 else 1)
            except ValueError:
                continue
            worst[i] = max(worst[i], abs(f))
    return worst


R10_FACTS = dict(mass_boom=MASS['boom']['mass_kg'], mass_stick=MASS['stick']['mass_kg'], mass_bucket=MASS['bucket']['mass_kg'],
                 ranges='boom -20..69, stick -48.9..-143.9, bucket 131.1..12.9 (R4 table), 118 deg bucket travel',
                 boom_cyl_y=50.0, saddle_half_width=66.0, boom_width=48.0, wall=4.0)

if __name__ == '__main__':
    print({k: round(v, 3) if isinstance(v, float) else v for k, v in R10_FACTS.items()})
    print('R10 static hold per drive, 150 g:', [round(x, 1) for x in hold_forces()])
    print('R10 static hold per drive, unloaded:', [round(x, 1) for x in hold_forces(0.0)])

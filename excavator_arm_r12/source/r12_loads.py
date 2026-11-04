"""Static pin forces on the boom and its bending-moment envelope (hold case, 150 g payload).

Free bodies: (1) everything beyond the boom-stick pin E except the stick cylinder, (2) the boom.
Cylinders are two-force members; their own weight is lumped onto the body at each end.
Units: N, mm, N*mm.
"""
import math
import itertools
import numpy as np
from shapely.geometry import LineString, box as sbox
import r12_design as d

G = 9.81


def _w(m):
    return np.array([0.0, -m * G])


def _cross(r, f):
    return r[0] * f[1] - r[1] * f[0]


def boom_forces(strokes, payload=True):
    s = d.solve(strokes)
    P, po = s['pins'], s['poses']
    M = d.MASS
    # subsystem beyond E (stick, bucket, links, payload, bucket cylinder, half the stick cylinder)
    loads = []
    for nm in ('stick', 'bucket', 'h_link'):
        loads.append((d.to_world(M[nm][1], *po[nm]), _w(M[nm][0])))
    loads.append((d.to_world(M['side_link'][1], *po['side_link']), _w(2 * M['side_link'][0])))
    if payload:
        loads.append((d.to_world(M['payload'][1], *po['bucket']), _w(M['payload'][0])))
    m_act = d.ACT['mass_barrel'] + d.ACT['mass_rod']
    loads.append(((P['F'] + P['R']) / 2, _w(m_act)))
    loads.append((P['D'], _w(m_act / 2)))
    E = P['E']
    u = (P['D'] - P['C']) / np.linalg.norm(P['D'] - P['C'])
    mom = sum(_cross(p - E, f) for p, f in loads)
    f_s = -mom / _cross(P['D'] - E, u)                  # stick-cylinder push on the stick (+ = push)
    w_sub = sum(f for _, f in loads)
    f_E_boom = w_sub + f_s * u                          # force of the stick on the boom at E
    f_C_boom = -f_s * u + _w(m_act / 2)                 # stick cylinder on the boom at C (plus its half weight)
    v = (P['B'] - P['A']) / np.linalg.norm(P['B'] - P['A'])
    cg_b = d.to_world(M['boom'][1], *po['boom'])
    others = [(E, f_E_boom), (P['C'], f_C_boom), (cg_b, _w(M['boom'][0])), (P['B'], 2 * _w(m_act / 2))]
    mom_o = sum(_cross(p - P['O'], f) for p, f in others)
    f_b = -mom_o / _cross(P['B'] - P['O'], v)           # total boom-cylinder push (both drives)
    forces = dict(E=f_E_boom, C=f_C_boom, B=f_b * v + 2 * _w(m_act / 2), G=_w(M['boom'][0]))
    return s, forces, f_b, f_s


def moment_along_boom(strokes, xs, payload=True):
    """Bending moment about the local Y axis at boom-frame stations xs (cut normal to the chord).
    Uses the part of the boom beyond each cut; the boom weight is spread along the chord in
    proportion to the side-profile area."""
    s, F, f_b, f_s = boom_forces(strokes, payload)
    th = s['theta']
    R = d.rot(-th)
    prof = d.boom_profile()
    total_area = prof.area
    m_boom = d.MASS['boom'][0]
    loc = dict(E=d.E_B, C=d.C_B, B=d.B_B)
    out = []
    for x in xs:
        cut = np.array([x, 0.0])
        m = 0.0
        for k, p in loc.items():
            if p[0] > x:
                f_local = R @ F[k]
                m += _cross(p - cut, f_local)
        part = prof.intersection(sbox(x, -200, 500, 300))
        if not part.is_empty:
            c = np.array(part.centroid.coords[0])
            m += _cross(c - cut, R @ _w(m_boom * part.area / total_area))
        out.append(m)
    return np.array(out)


def section_depth(x, prof=None):
    prof = prof or d.boom_profile()
    seg = LineString([(x, -300), (x, 300)]).intersection(prof)
    return seg.bounds[3] - seg.bounds[1], seg.bounds[1], seg.bounds[3]


def box_modulus(b, h, t):
    i = (b * h ** 3 - (b - 2 * t) * (h - 2 * t) ** 3) / 12.0
    return i / (h / 2.0)


def envelope(xs, grid=(0, 15, 30, 45, 60)):
    env = np.zeros(len(xs))
    for st in itertools.product(grid, repeat=3):
        m = np.abs(moment_along_boom(st, xs))
        env = np.maximum(env, m)
    return env


def section_table(stations=(60.0, 150.0, 220.0, 290.0, 345.0)):
    xs = np.array(stations)
    env = envelope(xs)
    rows = []
    prof = d.boom_profile()
    for x, m in zip(xs, env):
        h, lo, hi = section_depth(x, prof)
        b = 21.0 if x > d.BOOM - d.BOOM_NOSE_R else 40.0
        z = box_modulus(b, h, d.T_WALL)
        rows.append(dict(x=float(x), depth=round(h, 1), width=b, M_Nmm=round(float(m), 0),
                         Z_mm3=round(z, 0), sigma_MPa=round(float(m) / z, 2)))
    return rows


if __name__ == '__main__':
    for r in section_table():
        print(r)

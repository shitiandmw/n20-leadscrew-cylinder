#!/usr/bin/env python3
"""Materials showcase for two J9 tracks (revision F): every part to print or buy, in 3D, with its dimensions and material.

Writes, from the same lists and files as the print kit (build_track_kit.py; no quantity, setting or spec is typed in again):
  ../parts_showcase.html         offline page (three.js, one file). Pick a part to turn it, see it on the print bed or as fitted,
                                 cut it open, read its dimensions on the model and in a table, and find it in the track
  ../parts_showcase_report.json  what was checked (see below)

The printed parts are shown from their STL files, the files you print. The bought parts are shown from the CAD scene; those models
are simplified (no threads, sockets, balls or seals). Every dimension drawn on a model is checked against that model's mesh before
the page is written: a diameter must be a circle of that radius on the mesh over the stated length, and a length must end on faces
of the mesh. Values come from the J9 design (j9_design.py, j9_parts.py, j9_mounts.py, X1 x1_parts.py) and the suppliers' data
named in each row. The report also records each print file against the CAD scene (same solid: bounding box, centroid and volume),
the right-hand files against the mirrored left ones (vertex for vertex), and the item list against the kit's.

Inputs: j9_scene.json.gz, ../../X1/source/x1_scene.json.gz, the STL files, build_track_kit.py, parts_showcase.html (template),
../../../actuator_v6/source/vendor (three.js r128 and OrbitControls).
Standard library only:  python3 track_wheel_jgy370/J9/source/build_parts_showcase.py
Then check the page in Chromium:  NODE_PATH=<playwright node_modules> node track_wheel_jgy370/J9/source/check_parts_showcase.cjs
"""
import array
import base64
import gzip
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_track_kit as K             # noqa: E402  the kit lists, STL facts and chain hardware

ROOT, REPO, X1 = K.ROOT, K.REPO, K.X1
TOL = 0.012                             # mm: a feature must be on the mesh within this
PRINT_ROT = {'J901': -90, 'J909': -90, 'J902': -90, 'J903': -90, 'J904': -90, 'J906': -90, 'J907': -90,
             'J908': 180, 'J910': 0, 'X101': 180}     # build_j9.PRINT and X1 check_revf_exports.py: rotation about X onto the bed
STEP_FILES = {'J901': {'left': 'track_wheel_jgy370/J9/step/J901_H_frame.step', 'right': 'track_wheel_jgy370/X1/step/J901_H_frame_right.step'},
              'J909': {'left': 'track_wheel_jgy370/J9/step/J909_housing.step', 'right': 'track_wheel_jgy370/X1/step/J909_housing_right.step'},
              'X101': {'chassis': 'track_wheel_jgy370/X1/step/X101_X_frame.step'}}
INCH, LBF = 25.4, 4.4482216
SPRING = dict(od=.600 * INCH, wire=.072 * INCH, free=1.500 * INCH, solid=.670 * INCH, rate=35.89 * LBF / INCH, max_load=26.48 * LBF,
              set=25.8, recoil=4.2)                   # j9_design.SPRING (Lee Spring C-600-072-1500 catalogue values)
PETG = K.PETG


def fmt(v, nd=2):
    s = f'{v:.{nd}f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --------------------------------------------------------------------------------------------- small linear algebra
def rot_x(deg):
    c, s = round(math.cos(math.radians(deg))), round(math.sin(math.radians(deg)))
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def mv(M, p):
    return [M[i][0] * p[0] + M[i][1] * p[1] + M[i][2] * p[2] for i in range(3)]


def tp(M):
    return [[M[j][i] for j in range(3)] for i in range(3)]


def m4(R=None, t=(0, 0, 0)):
    R = R or [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    return [[*R[0], t[0]], [*R[1], t[1]], [*R[2], t[2]], [0, 0, 0, 1]]


def mul4(A, B):
    return [[sum(A[i][k] * B[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def col(M):
    """Column-major 16 numbers, as THREE.Matrix4.fromArray wants."""
    return [round(M[r][c], 6) for c in range(4) for r in range(4)]


def rot_y(theta):
    """THREE's rotation about Y by theta."""
    c, s = math.cos(theta), math.sin(theta)
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


# --------------------------------------------------------------------------------------------- meshes
def load_stl(rel):
    """Binary STL as an indexed mesh (coincident vertices merged exactly)."""
    data = (REPO / rel).read_bytes()
    n = struct.unpack_from('<I', data, 80)[0]
    assert len(data) == 84 + 50 * n, rel
    index, V, T = {}, [], []
    for t in struct.iter_unpack('<12fH', data[84:]):
        tri = []
        for k in (3, 6, 9):
            key = t[k:k + 3]
            i = index.get(key)
            if i is None:
                i = index[key] = len(V)
                V.append(list(key))
            tri.append(i)
        T.append(tri)
    lo = [min(v[i] for v in V) for i in range(3)]
    hi = [max(v[i] for v in V) for i in range(3)]
    return dict(V=V, T=T, n=n, lo=lo, hi=hi, sha256=hashlib.sha256(data).hexdigest(), rel=rel)


def mesh_stats(V, T):
    lo = [min(v[i] for v in V) for i in range(3)]
    hi = [max(v[i] for v in V) for i in range(3)]
    vol, cen = 0.0, [0.0, 0.0, 0.0]
    for a, b, c in T:
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = V[a], V[b], V[c]
        d = (ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)) / 6
        vol += d
        cen = [cen[0] + d * (ax + bx + cx) / 4, cen[1] + d * (ay + by + cy) / 4, cen[2] + d * (az + bz + cz) / 4]
    return dict(lo=lo, hi=hi, volume=vol, centroid=[c / vol for c in cen] if abs(vol) > 1e-9 else [(a + b) / 2 for a, b in zip(lo, hi)])


def fit_print(stl, scene_mesh, deg):
    """Rigid transform track (or vehicle, or link) frame -> STL frame for one placed instance of a printed part: the export's
    rotation about X, then the translation that build_track_wheel.to_bed applies (centred in X and Y, on the bed). Checked: the
    two meshes (different tessellations of one solid) agree in bounding box, centroid and volume."""
    R = rot_x(deg)
    S = mesh_stats(scene_mesh['vertices'], scene_mesh['triangles'])
    P = mesh_stats(stl['V'], stl['T'])
    corners = [mv(R, [S['lo'][0] if i & 1 else S['hi'][0], S['lo'][1] if i & 2 else S['hi'][1], S['lo'][2] if i & 4 else S['hi'][2]]) for i in range(8)]
    lo = [min(c[i] for c in corners) for i in range(3)]
    hi = [max(c[i] for c in corners) for i in range(3)]
    t = [(P['lo'][0] + P['hi'][0]) / 2 - (lo[0] + hi[0]) / 2, (P['lo'][1] + P['hi'][1]) / 2 - (lo[1] + hi[1]) / 2, P['lo'][2] - lo[2]]
    bbox_err = max(max(abs(lo[i] + t[i] - P['lo'][i]), abs(hi[i] + t[i] - P['hi'][i])) for i in range(3))
    c = mv(R, S['centroid'])
    cen_err = math.dist([c[i] + t[i] for i in range(3)], P['centroid'])
    vol_ratio = P['volume'] / S['volume']
    ok = bbox_err < 0.06 and cen_err < 0.05 and abs(vol_ratio - 1) < 0.002
    assert ok, (stl['rel'], scene_mesh['name'], deg, bbox_err, cen_err, vol_ratio)
    return R, t, dict(rot_x_deg=deg, bbox_error_mm=round(bbox_err, 4), centroid_error_mm=round(cen_err, 4), volume_ratio=round(vol_ratio, 5))


class Plane:
    """Coplanar triangles of a mesh, by axis and coordinate, for the 'ends on a face' test."""
    def __init__(self, V, T):
        self.V, self.idx = V, [{}, {}, {}]
        for tri in T:
            for k in range(3):
                vals = [V[i][k] for i in tri]
                if max(vals) - min(vals) < 1e-4:
                    self.idx[k].setdefault(round(sum(vals) / 3, 2), []).append(tri)

    def on_face(self, p, k):
        i, j = [m for m in range(3) if m != k]
        for key in (round(p[k], 2) + d for d in (-.01, 0, .01)):
            for tri in self.idx[k].get(round(key, 2), []):
                (a, b, c) = (self.V[x] for x in tri)
                if abs(a[k] - p[k]) > TOL:
                    continue
                d = (b[j] - c[j]) * (a[i] - c[i]) + (c[i] - b[i]) * (a[j] - c[j])
                if abs(d) < 1e-12:
                    continue
                l1 = ((b[j] - c[j]) * (p[i] - c[i]) + (c[i] - b[i]) * (p[j] - c[j])) / d
                l2 = ((c[j] - a[j]) * (p[i] - c[i]) + (a[i] - c[i]) * (p[j] - c[j])) / d
                if l1 >= -1e-6 and l2 >= -1e-6 and 1 - l1 - l2 >= -1e-6:
                    return True
        return False


def circle_hits(V, c, k, r, span):
    i, j = [m for m in range(3) if m != k]
    return [v for v in V if span[0] - TOL <= v[k] <= span[1] + TOL and abs(math.hypot(v[i] - c[i], v[j] - c[j]) - r) < TOL]


def check_circle(V, a):
    """A circle of radius r about the axis through c, present over the whole span (vertices at both ends) and round it (no
    angular gap over 'gap' degrees); 'exact': the same circle does not go on within 3 mm beyond the span (a stated depth)."""
    k, c, r, span = a['k'], a['c'], a['r'], a['span']
    i, j = [m for m in range(3) if m != k]
    hits = circle_hits(V, c, k, r, span)
    assert len(hits) >= 6, f'no circle r {r} about {c} axis {k} over {span}'
    angs = sorted(math.degrees(math.atan2(v[j] - c[j], v[i] - c[i])) % 360 for v in hits)
    gaps = [b - x for x, b in zip(angs, angs[1:])] + [angs[0] + 360 - angs[-1]]
    assert max(gaps) <= a['gap'] + 1e-6, f'circle r {r} about {c}: gap {max(gaps):.1f} deg > {a["gap"]}'
    ys = [v[k] for v in hits]
    assert min(ys) <= span[0] + TOL and max(ys) >= span[1] - TOL, f'circle r {r} about {c} spans {min(ys):.3f}..{max(ys):.3f}, not {span}'
    if a.get('exact'):
        beyond = [v for v in circle_hits(V, c, k, r, (span[0] - 3, span[1] + 3)) if v[k] < span[0] - TOL or v[k] > span[1] + TOL]
        assert not beyond, f'circle r {r} about {c} goes on beyond {span}: {beyond[0][k]:.3f}'
    return dict(vertices=len(hits), max_gap_deg=round(max(gaps), 1), axial=[round(min(ys), 3), round(max(ys), 3)])


# --------------------------------------------------------------------------------------------- dimensions
# Anchors and dimensions are written in the part's own frame as placed in the CAD (track frame for the J9 module, vehicle frame
# for X1, the link frame for the chain), then moved into the frame the page draws the model in.
AX = dict(x=0, y=1, z=2)


def pl(p, axis):
    """A face perpendicular to axis through p (p must lie on a face of the mesh)."""
    return dict(t='pl', p=list(p), k=AX[axis])


def ci(c, axis, r, span, gap=60, exact=False):
    """A cylinder of radius r about axis through c, from span[0] to span[1] along that axis."""
    return dict(t='ci', c=list(c), k=AX[axis], r=r, span=list(span), gap=gap, exact=exact)


def cedge(circle, d):
    """The point of a checked circle (anchor ci) in direction d from its axis: for widths across a flat or a tangent."""
    return dict(t='ce', ci=circle, d=list(d))


def DIA(label, c, axis, r, span, text='Ø{v}', key=False, note='', grp='', gap=60, exact=False, rad=False, show=None):
    """Diameter (or radius, rad=True) of the cylinder r about axis through c over span. Drawn at 'show' along the axis
    (default: c's own coordinate)."""
    return dict(k='dia', label=label, a=ci(c, axis, r, span, gap, exact), text=text, key=key, note=note, grp=grp, rad=rad, show=show)


def LEN(label, a, b, off, text='{v}', key=False, note='', grp=''):
    """Distance between two anchors: two faces (along their axis), two circles (centre to centre) or a face and a circle edge."""
    return dict(k='len', label=label, a=a, b=b, off=list(off), text=text, key=key, note=note, grp=grp)


def PCD(label, c, axis, R, angles, hole_r, span, text, key=False, note='', grp=''):
    """Holes of radius hole_r on a circle of radius R (angles in degrees, from the first of the other two axes)."""
    return dict(k='pcd', label=label, c=list(c), axis=axis, R=R, angles=list(angles), hole_r=hole_r, span=list(span), text=text,
                key=key, note=note, grp=grp)


def SPEC(label, text, note='', grp=''):
    """A table row only (thread, rating, material data); not drawn."""
    return dict(k='spec', label=label, text=text, note=note, grp=grp)


def REFC(label, c, axis, r, text, note='', grp='', key=False):
    """A reference circle (not a surface, e.g. a pitch circle): drawn dashed, its value computed, not measured."""
    return dict(k='ref', label=label, c=list(c), axis=axis, r=r, text=text, note=note, grp=grp, key=key)


def holes_xz(cx, cz, R, angles):
    return [(cx + R * math.cos(math.radians(a)), cz + R * math.sin(math.radians(a))) for a in angles]


class Frame:
    """Moves anchors from the CAD frame into the drawing frame: p' = R p + t."""
    def __init__(self, R=None, t=(0, 0, 0)):
        self.R, self.t = R or [[1, 0, 0], [0, 1, 0], [0, 0, 1]], list(t)

    def p(self, p):
        q = mv(self.R, p)
        return [q[i] + self.t[i] for i in range(3)]

    def v(self, v):
        return mv(self.R, v)

    def k(self, k):
        u = [0, 0, 0]
        u[k] = 1
        w = mv(self.R, u)
        return max(range(3), key=lambda i: abs(w[i]))

    def span(self, c, k, span):
        q0, q1 = list(c), list(c)
        q0[k], q1[k] = span
        k2 = self.k(k)
        return sorted([self.p(q0)[k2], self.p(q1)[k2]])

    def anchor(self, a):
        if a['t'] == 'pl':
            return dict(t='pl', p=self.p(a['p']), k=self.k(a['k']))
        if a['t'] == 'ci':
            return dict(a, c=self.p(a['c']), k=self.k(a['k']), span=self.span(a['c'], a['k'], a['span']))
        return dict(t='ce', ci=self.anchor(a['ci']), d=self.v(a['d']))


def unit(k):
    u = [0.0, 0.0, 0.0]
    u[k] = 1.0
    return u


def resolve(dims, frame, mesh, item):
    """Check every dimension against the mesh (drawing frame) and turn it into drawing data. Returns (dims, checks)."""
    V = mesh['V']
    faces = Plane(V, mesh['T'])
    out, checks = [], []

    def anchor_point(a):
        if a['t'] == 'pl':
            assert faces.on_face(a['p'], a['k']), f'{item}: no face at {[round(x, 3) for x in a["p"]]} across axis {a["k"]}'
            return a['p'], dict(face=[round(x, 3) for x in a['p']], axis='xyz'[a['k']])
        if a['t'] == 'ci':
            return a['c'], dict(circle=check_circle(V, a), r=a['r'])
        c = a['ci']
        res = check_circle(V, c)
        d = a['d']
        return [c['c'][i] + c['r'] * d[i] for i in range(3)], dict(circle_edge=res, r=c['r'])

    for n, d in enumerate(dims, 1):
        row = dict(n=n, k=d['k'], label=d['label'], key=d.get('key', False), note=d.get('note', ''), grp=d.get('grp', ''))
        try:
            if d['k'] == 'dia':
                a = frame.anchor(d['a'])
                res = check_circle(V, a)
                v = a['r'] if d['rad'] else 2 * a['r']
                text = d['text'].replace('{v}', fmt(v))
                if d['rad']:
                    text = text.replace('Ø', 'R')
                c = list(a['c'])
                if d['show'] is not None:
                    q = list(d['a']['c'])
                    q[d['a']['k']] = d['show']
                    c = frame.p(q)
                row.update(text=text, value=v, c=[round(x, 4) for x in c], u=unit(a['k']), r=a['r'])
                checks.append(dict(item=item, n=n, label=d['label'], text=text, **res))
            elif d['k'] == 'len':
                A, ra = anchor_point(frame.anchor(d['a']))
                B, rb = anchor_point(frame.anchor(d['b']))
                ta, tb = d['a']['t'], d['b']['t']
                if 'pl' in (ta, tb):
                    k = frame.k((d['a'] if ta == 'pl' else d['b'])['k'])
                    v = abs(B[k] - A[k])
                    B2 = list(A)
                    B2[k] = B[k]
                    B = B2
                else:                                       # two circles: centre to centre, square to their (parallel) axes
                    k = frame.k(d['a']['ci']['k'] if ta == 'ce' else d['a']['k'])
                    B = list(B)
                    B[k] = A[k]
                    v = math.dist(A, B)
                text = d['text'].replace('{v}', fmt(v))
                row.update(text=text, value=v, A=[round(x, 4) for x in A], B=[round(x, 4) for x in B],
                           off=[round(x, 4) for x in frame.v(d['off'])])
                checks.append(dict(item=item, n=n, label=d['label'], text=text, a=ra, b=rb))
            elif d['k'] == 'pcd':
                k0 = AX[d['axis']]
                i0, j0 = [m for m in range(3) if m != k0]
                centres = []
                res = []
                for ang in d['angles']:
                    q = list(d['c'])
                    q[i0] += d['R'] * math.cos(math.radians(ang))
                    q[j0] += d['R'] * math.sin(math.radians(ang))
                    a = frame.anchor(ci(q, d['axis'], d['hole_r'], d['span']))
                    res.append(check_circle(V, a)['vertices'])
                    centres.append([round(x, 4) for x in a['c']])
                text = d['text'].replace('{v}', fmt(2 * d['R'])).replace('{h}', fmt(2 * d['hole_r'])).replace('{n}', str(len(d['angles'])))
                row.update(text=text, value=2 * d['R'], c=[round(x, 4) for x in frame.p(d['c'])], u=unit(frame.k(k0)), r=d['R'],
                           holes=centres, hole_r=d['hole_r'])
                checks.append(dict(item=item, n=n, label=d['label'], text=text, holes=len(centres), vertices_each=res))
            elif d['k'] == 'ref':
                k0 = AX[d['axis']]
                row.update(text=d['text'], value=2 * d['r'], c=[round(x, 4) for x in frame.p(d['c'])], u=unit(frame.k(k0)), r=d['r'], dashed=True)
                checks.append(dict(item=item, n=n, label=d['label'], text=d['text'], computed=True))
            else:
                row.update(text=d['text'])
        except AssertionError as e:
            raise SystemExit(f'{item} dimension {n} "{d["label"]}": {e}')
        out.append(row)
    return out, checks


# --------------------------------------------------------------------------------------------- the dimensions of each part
def printed_dims(cfg):
    """Feature dimensions of the printed parts, in the CAD frame of the instance named with each list."""
    DX, AZ = cfg['drive']
    IX = cfg['idler'][0]
    RX, RZ = cfg['rollers']['road0']
    WIN, WOUT, PLATE = 24.0, 30.0, -34.0                         # j9_design WALL_IN/WALL_OUT, j9_mounts PLATE_FACE_Y
    MOTOR_HOLES = [(DX + x, AZ + z) for x in (-9.0, 24.0) for z in (-9.0, 9.0)]
    HOUSING_SCREWS = [(-103.0, 71.0), (-15.0, 33.0), (85.0, 56.0), (85.0, 32.0)]
    yoke_x0 = 36.0 + 25.8                                       # WEB_X[1] + SPRING_SET: front of the yoke base
    sx, sz = HOUSING_SCREWS[1]
    can_y = -30.0 - 13.2                                        # CAN_Y
    nose_x = -110.0 + 62.3 + 10 + .8                            # NOSE_X
    tube_r = 12 + .8 + 2.5                                      # TUBE_R
    shoulder_x = -110.0 + 31.5 + .8 + 2.5                       # SHOULDER_X
    d = {}
    d['J901'] = ('J901_H_frame', [
        LEN('Between the walls (inner faces)', pl((20, -WIN, 60), 'y'), pl((20, WIN, 60), 'y'), (0, 0, 22), key=True, grp='Walls',
            note='The rollers, the idler and the sprocket run between the walls.'),
        LEN('Inner main plate', pl((-30, PLATE, 65), 'y'), pl((-30, -WIN, 65), 'y'), (0, 0, 16), key=True, grp='Walls',
            note='Revision F: 10 mm plate on the motor side (X101 joints and motor).'),
        LEN('Outer wall', pl((20, WIN, 65), 'y'), pl((20, WOUT, 65), 'y'), (0, 0, 16), grp='Walls'),
        DIA('6800ZZ seat', (DX, WOUT, AZ), 'y', 9.5, (25, 30), text='Ø{v} × 5 deep', key=True, exact=True, grp='Drive',
            note='Outer wall, open to the outside. The 6800ZZ (10 × 19 × 5) presses in onto the 1 mm lip and ends flush.'),
        DIA('Hole through the lip', (DX, 24.5, AZ), 'y', 6.0, (24, 25), grp='Drive'),
        DIA('Motor shaft hole', (DX, -26, AZ), 'y', 4.0, (-28.2, -24), grp='Drive'),
        DIA('Recess for the gearbox boss', (DX, -30, AZ), 'y', 6.8, (-30, -28.2), text='Ø{v} × 1.8', exact=True, grp='Drive',
            note='JGY-370 centre boss Ø13.2 × 1.6.'),
        DIA('Counterbores for the gearbox screw bosses (4)', (MOTOR_HOLES[0][0], -30, MOTOR_HOLES[0][1]), 'y', 3.7, (-30, -28), text='Ø{v} × 2',
            exact=True, grp='Drive', note='The gearbox has four Ø7 × 2 bosses round its M3 holes.'),
        DIA('Motor screw holes (4)', (MOTOR_HOLES[0][0], -26.5, MOTOR_HOLES[0][1]), 'y', 1.7, (-28, -25), grp='Drive'),
        DIA('Spot faces for the M3 × 6 heads (4)', (MOTOR_HOLES[0][0], -WIN, MOTOR_HOLES[0][1]), 'y', 3.25, (-25, -24), text='Ø{v} × 1', grp='Drive',
            note='On the inside of the H: the motor screws go in from between the walls.'),
        LEN('Motor hole pattern, along the track', ci((MOTOR_HOLES[0][0], -26.5, MOTOR_HOLES[0][1]), 'y', 1.7, (-28, -25)),
            ci((MOTOR_HOLES[2][0], -26.5, MOTOR_HOLES[2][1]), 'y', 1.7, (-28, -25)), (0, 0, -16), grp='Drive', key=True),
        LEN('Motor hole pattern, height', ci((MOTOR_HOLES[0][0], -26.5, MOTOR_HOLES[0][1]), 'y', 1.7, (-28, -25)),
            ci((MOTOR_HOLES[1][0], -26.5, MOTOR_HOLES[1][1]), 'y', 1.7, (-28, -25)), (-14, 0, 0), grp='Drive'),
        DIA('Roller axle holes (7)', (0, 27, 22), 'y', 2.2, (23.3, 30), key=True, grp='Rollers', note='M4 × 70 axles.'),
        DIA('Head recesses for the axle screws (7)', (0, PLATE, 22), 'y', 3.7, (-34, -30), text='Ø{v} × 4', exact=True, grp='Rollers'),
        DIA('Roller bosses on the inner faces', (0, 23.3, 22), 'y', 2.8, (23.3, 24), text='Ø{v} × 0.7', exact=True, grp='Rollers',
            note='They touch only the 624 inner rings, so each roller floats about 0.3 mm between the walls.'),
        LEN('Road roller pitch', ci((-29, 27, 22), 'y', 2.2, (23.3, 30)), ci((0, 27, 22), 'y', 2.2, (23.3, 30)), (0, 0, -14), key=True, grp='Rollers'),
        LEN('Support roller spacing', ci((-35, 27, cfg['rollers']['support0'][1]), 'y', 2.2, (23.3, 30)),
            ci((35, 27, cfg['rollers']['support1'][1]), 'y', 2.2, (23.3, 30)), (0, 0, 14), grp='Rollers'),
        DIA('Spring guide bore', (40, 0, AZ), 'x', 8.2, (28, 56.8), key=True, grp='Tensioner',
            note='The J908 piston (Ø15.6) slides in it; the spring sits on its floor.'),
        DIA('Spring guide outside', (54.4, 0, AZ), 'x', 10.6, (52, 56.8), grp='Tensioner'),
        DIA('Spring pilot', (30, 0, AZ), 'x', 5.5, (28, 32), text='Ø{v} × 4', exact=True, grp='Tensioner', note='Inside the spring (ID 11.58).'),
        LEN('Yoke groove depth (both walls)', pl((80, WIN, AZ + 12), 'y'), pl((80, 27.2, AZ + 6.5), 'y'), (0, 0, 2.7), grp='Tensioner',
            note='The 3 mm yoke arms slide in them.'),
        LEN('Yoke groove height', pl((80, 25.6, AZ - 8.2), 'z'), pl((80, 25.6, AZ + 8.2), 'z'), (10, 0, 0), grp='Tensioner'),
        DIA('Insert holes in the housing standoffs (4)', (sx, -35.5, sz), 'y', 2.0, (-35.5, -29.8), text='Ø{v} × 5.7 deep', key=True, exact=True,
            grp='Housing standoffs', note='Blind, for M3 heat-set inserts.'),
        DIA('Housing standoffs (4)', (sx, -34.75, sz), 'y', 4.0, (-35.5, -34), grp='Housing standoffs'),
        LEN('X101 joint seat width (2)', pl((63.5 - 14.15, -33.2, 65), 'x'), pl((63.5 + 14.15, -33.2, 65), 'x'), (0, 0, 14), key=True,
            grp='X101 joints', note='The 28 mm X101 arm end sits in it, 0.15 mm clear each side.'),
        LEN('X101 joint seat depth', pl((40, PLATE, 60), 'y'), pl((63.5, -32.5, 60), 'y'), (0, 0, 20), grp='X101 joints'),
        DIA('X101 joint bolt holes (4)', (63.5 - 9.5, -28, 67.75), 'y', 2.25, (-32.5, -24), key=True, grp='X101 joints',
            note='Plain holes: M4 × 25, washers both sides, nut inside the track.'),
        LEN('X101 joint bolt spacing', ci((63.5 - 9.5, -28, 67.75), 'y', 2.25, (-32.5, -24)), ci((63.5 + 9.5, -28, 67.75), 'y', 2.25, (-32.5, -24)),
            (0, 0, 12), grp='X101 joints'),
        SPEC('Axle positions', f'Sprocket axis X {fmt(DX)}, Z {fmt(AZ)}; road rollers X −58 to 58 at Z 22; support rollers X ±35 at Z {fmt(cfg["rollers"]["support0"][1])}',
             note='Track frame: X forward, Z up from the ground.', grp='Layout'),
    ])
    d['J909'] = ('J909_housing', [
        LEN('Skirt thickness', pl((12, -38, 20), 'y'), pl((12, -35.5, 20), 'y'), (0, 0, -12), key=True, grp='Skirt'),
        LEN('Skirt height (middle)', pl((12, -36.75, 13), 'z'), pl((12, -36.75, 77), 'z'), (-14, 0, 0), grp='Skirt'),
        DIA('Roller bolt access holes (7)', (0, -38, 22), 'y', 4.0, (-38, -35.5), key=True, grp='Skirt',
            note='Line up with the M4 × 70 heads, so the rollers can be serviced with the housing on.'),
        DIA('Screw holes (4)', (sx, -38, sz), 'y', 1.7, (-38, -35.5), key=True, grp='Skirt', note='M3 × 8 button heads into the J901 inserts.'),
        DIA('Final-drive drum', (DX, -48, AZ), 'y', 26.5, (-57, -39), key=True, gap=150, grp='Motor pod', note='On the sprocket axis.'),
        LEN('Pod depth from the skirt', pl((DX - 30, -35.5, AZ), 'y'), pl((DX, -60, AZ + 16), 'y'), (0, 0, -40), grp='Motor pod'),
        DIA('Tube over the motor can', (-41.5, can_y, AZ), 'x', tube_r, (-46.2, nose_x), gap=185, grp='Motor pod',
            note='2.5 mm wall, 0.8 mm clear of the Ø24 can. Further back the X101 arm window cuts its top away.'),
        DIA('Cable port', (-21.1, can_y, AZ), 'x', 2.75, (nose_x + math.sqrt((tube_r - 2.5) ** 2 - 2.75 ** 2), nose_x + tube_r + 3), key=True,
            grp='Motor pod',
            note='In the nose: the motor leads only, no plug.'),
    ])
    d['J902'] = ('J902_sprocket', [
        DIA('Tooth tips', (DX, 0, AZ), 'y', 40.8205, (-8.5, 8.5), key=True, gap=40, grp='Teeth'),
        REFC('Pitch circle (bushing centres)', (DX, 8.5, AZ), 'y', cfg['pitch_r'], text=f'Ø{fmt(2 * cfg["pitch_r"])}', grp='Teeth', key=True,
             note=f'12 teeth on a {fmt(cfg["pitch"])} mm pitch: {fmt(cfg["pitch"])} / sin 15°.'),
        LEN('Tooth disc thickness', pl((DX + 30, -8.5, AZ), 'y'), pl((DX + 30, 8.5, AZ), 'y'), (0, 0, 16), key=True, grp='Teeth',
            note='As long as the 17 mm bushings.'),
        DIA('Ring round the recess', (DX, -9.25, AZ), 'y', 18.5, (-10.0, -8.5), text='Ø{v} × 1.5', grp='Coupling side'),
        DIA('Recess for the coupling flange', (DX, -10.0, AZ), 'y', 16.2, (-10.0, -9.0), text='Ø{v} × 1 deep', key=True, exact=True,
            grp='Coupling side', note='Centres the Ø32 flange of the coupling.'),
        DIA('Stop pad for the shaft end', (DX, -14.4, AZ), 'y', 2.7, (-14.4, -9.0), text='Ø{v} × 5.4', exact=True, grp='Coupling side',
            note='Reaches down the coupling bore to the shaft end.'),
        PCD('Coupling screw holes', (DX, 0, AZ), 'y', 11.5, (0, 120, 240), 1.7, (-9.0, 5.5), text='3 × Ø{h} on Ø{v}', key=True, grp='Coupling side',
            note='Every other hole of the coupling; M3 × 20 from the outer face.'),
        DIA('Counterbores for the M3 heads (3)', (DX + 11.5, 8.5, AZ), 'y', 3.1, (5.5, 8.5), text='Ø{v} × 3 deep', exact=True, grp='Outer face',
            note='The heads end flush.'),
        DIA('Socket for the journal plug', (DX, 8.5, AZ), 'y', 5.05, (3.5, 8.5), text='Ø{v} × 5 deep', key=True, exact=True, grp='Outer face'),
        DIA('Centre bore', (DX, 0, AZ), 'y', 1.7, (-14.4, 3.5), grp='Outer face', note='For the M3 × 50 into the motor shaft.'),
    ])
    d['J903'] = ('J903_journal_plug', [
        DIA('Journal', (DX, 16.75, AZ), 'y', 4.975, (3.5, 30), key=True, grp='Plug', note='Runs in the 6800ZZ inner ring (Ø10).'),
        DIA('Bore', (DX, 30, AZ), 'y', 1.7, (3.5, 30), key=True, grp='Plug', note='M3 × 50 clearance.'),
        SPEC('Engagement', '5 mm in the sprocket socket; the rest passes the outer wall and the 6800ZZ', grp='Plug'),
    ])
    rc = lambda y: (RX, y, RZ)
    d['J904'] = ('J904_roller_road0', [
        DIA('Tread', rc(0), 'y', 11.0, (-21.6, 21.6), key=True, grp='Running surfaces', note='Rolls on the link rails.'),
        DIA('Guide flanges', rc(22.3), 'y', 13.0, (21.6, 23), text='Ø{v} × 1.4', key=True, exact=True, grp='Running surfaces'),
        DIA('624ZZ seats (both faces)', rc(23), 'y', 6.5, (18, 23), text='Ø{v} × 5 deep', key=True, exact=True, grp='Bearing seats',
            note='Press fit; each 624ZZ (4 × 13 × 5) ends flush with the face.'),
        DIA('Centre bore', rc(0), 'y', 4.0, (-18, 18), key=True, exact=True, grp='Bearing seats',
            note='The seat shoulders bear only on the outer rings (SKF 624-2Z: inner ring d1 6.95, Da max 11.2).'),
        LEN('Between the seats', pl((RX + 5, -18, RZ), 'y'), pl((RX + 5, 18, RZ), 'y'), (0, 0, -16), grp='Bearing seats'),
    ])
    ic = lambda y: (IX, y, AZ)
    d['J906'] = ('J906_idler_wheel', [
        DIA('Centre drum (bushings run on it)', ic(0), 'y', 35.237, (-7, 7), key=True, exact=True, grp='Running surfaces'),
        DIA('Rails (link running faces)', ic(18), 'y', 33.17, (15, 21.6), grp='Running surfaces'),
        DIA('Guide flanges', ic(22.3), 'y', 35.17, (21.6, 23), text='Ø{v} × 1.4', exact=True, grp='Running surfaces'),
        DIA('608ZZ seats (both sides)', ic(10.5), 'y', 11.1, (3, 10.5), text='Ø{v} × 7.5', key=True, exact=True, grp='Bearing seats',
            note='Press fit; each 608ZZ (8 × 22 × 7) stops against the central web.'),
        DIA('Slide-in bores (both faces)', ic(22.4), 'y', 11.3, (10.5, 22.4), text='Ø{v}, 0.6 × 45° chamfer', key=True, exact=True, grp='Bearing seats',
            note='The bearing slides in by hand, then presses the last 7.5 mm.'),
        LEN('Idler face to the web', pl((IX + 9, 3, AZ), 'y'), pl((IX + 20, 23, AZ), 'y'), (0, 0, 30), grp='Bearing seats',
            note='The 608ZZ outer faces end 13 mm below the idler faces.'),
        DIA('Web bore', ic(0), 'y', 6.2, (-3, 3), exact=True, grp='Bearing seats'),
    ])
    d['J907'] = ('J907_idler_spacer_1', [
        DIA('Outside', (IX, 17, AZ), 'y', 5.5, (10.05, 23.95), key=True, exact=True, grp='Spacer', note='Touches only the 608 inner ring.'),
        DIA('Bore', (IX, 23.95, AZ), 'y', 4.1, (10.05, 23.95), key=True, exact=True, grp='Spacer', note='On the Ø8 idler pin.'),
    ])
    d['J908'] = ('J908_U_yoke', [
        DIA('Idler pin holes', (IX, 27, AZ), 'y', 4.05, (24, 27), key=True, exact=True, grp='Arms', note='Ø8 × 55 steel pin.'),
        LEN('Arm thickness', pl((95, 24, AZ), 'y'), pl((95, 27, AZ), 'y'), (0, 0, 12), key=True, grp='Arms',
            note='Slides in the frame\'s 3.2 mm grooves.'),
        LEN('Arm height', pl((95, 25.5, AZ - 8), 'z'), pl((95, 25.5, AZ + 8), 'z'), (8, 0, 0), grp='Arms'),
        LEN('Between the arms', pl((95, -24, AZ), 'y'), pl((95, 24, AZ), 'y'), (0, 0, -12), grp='Arms', note='The idler and its two spacers.'),
        DIA('Piston', (57.8, 0, AZ), 'x', 7.8, (53.8, yoke_x0), text='Ø{v} × 8', key=True, exact=True, grp='Piston',
            note='Slides in the frame\'s Ø16.4 bore.'),
        DIA('Spring pilot', (51.8, 0, AZ), 'x', 5.5, (49.8, 53.8), text='Ø{v} × 4', key=True, exact=True, grp='Piston'),
    ])
    d['J910'] = ('link', [
        LEN('Pitch', ci((-10, 17.5, 0), 'y', 1.6, (14, 21)), ci((10, 11.2, 0), 'y', 1.6, (8.7, 13.7)), (0, 0, 9), key=True, grp='Joint'),
        DIA('Pin holes', (-10, 21, 0), 'y', 1.6, (14, 21), key=True, exact=True, grp='Joint',
            note='The Ø3 pin goes through; the Ø6 bushing cannot, so it goes in between the ears first.'),
        LEN('Over the outer plates', pl((0, -21, 2), 'y'), pl((0, 21, 2), 'y'), (0, 0, 10), grp='Joint'),
        LEN('Between the outer plates', pl((0, -14, 2), 'y'), pl((0, 14, 2), 'y'), (0, 0, 7), grp='Joint'),
        LEN('Over the inner ears', pl((10, -13.7, 2), 'y'), pl((10, 13.7, 2), 'y'), (0, 0, 7), grp='Joint',
            note='Fits between the next link\'s outer plates (28).'),
        LEN('Between the inner ears', pl((10, -8.7, 2), 'y'), pl((10, 8.7, 2), 'y'), (0, 0, 4), key=True, grp='Joint',
            note='The 17 mm bushing: 0.2 mm clear each side.'),
        DIA('Plate end hollow', (10, 21, 0), 'y', 4.3, (14, 21), text='R{v}', rad=True, gap=240, grp='Joint',
            note='The next link\'s rounded R4 plate end nests in it, so links go together only along the strip.'),
        LEN('Shoe plate', pl((3, 30, -6), 'z'), pl((3, 30, -4), 'z'), (0, 6, 0), grp='Shoe'),
        LEN('Grousers (3 per shoe)', pl((3, 30, -6), 'z'), pl((0, 30, -7), 'z'), (0, 6, 0), text='{v} high × 2 wide', grp='Shoe'),
        DIA('Holes in the shoe plate (2)', (0, 5, -4), 'z', 1.2, (-7, -4), grp='Shoe'),
    ])
    d['X101'] = ('X101_X_frame', [
        DIA('Carbody', (0, 0, 60), 'z', 60.0, (34, 85), key=True, gap=90, grp='Carbody'),
        DIA('Relief for the RU66 inner ring', (0, 0, 85), 'z', 37.5, (82.5, 85), text='Ø{v} × 2.5 deep', exact=True, grp='Slewing ring seat',
            note='Clears the RU66 inner ring (Dh min 74).'),
        PCD('RU66 outer-ring holes', (0, 0, 85), 'z', 41.5, [22.5 + 45 * k for k in range(8)], 2.25, (75, 85), text='8 × Ø{h} on Ø{v}', key=True,
            grp='Slewing ring seat', note='M4 × 30 from the ring\'s counterbores, nuts below.'),
        DIA('Cable passage', (0, 0, 82.5), 'z', 12.5, (79, 82.5), key=True, grp='Slewing ring seat',
            note='Through the top plate; the slip-ring collar below it has a Ø22.4 bore.'),
        LEN('Arm width (4 arms)', pl((63.5 - 14, 132, 65), 'x'), pl((63.5 + 14, 132, 65), 'x'), (0, 0, 16), key=True, grp='Arms',
            note='Into the 28.3 mm J901 seats.'),
    ])
    return d


def spring_dims():
    """The spring is drawn by the page from the catalogue values (free length, axis X, centred), so its dimensions are written
    here in that frame; the CAD's fitted spring is checked against the same values in main()."""
    s = SPRING
    ro, L = s['od'] / 2, s['free']
    f = lambda length: (s['free'] - length) * s['rate']
    rows = [
        dict(k='dia', label='Outside diameter', text=f'Ø{fmt(s["od"])}', value=s['od'], c=[0, 0, 0], u=[1, 0, 0], r=ro, key=True, grp='Spring',
             note='Slides in the Ø16.4 bore of the frame.'),
        dict(k='len', label='Length (shown: free)', text=fmt(L, 1), value=L, A=[-L / 2, 0, -ro], B=[L / 2, 0, -ro], off=[0, 0, -6], key=True,
             grp='Spring', spring_len=True),
        dict(k='spec', label='Wire', text=f'Ø{fmt(s["wire"])} music wire', grp='Spring'),
        dict(k='spec', label='Inside diameter', text=f'Ø{fmt(s["od"] - 2 * s["wire"])}', grp='Spring', note='Fits over the Ø11 pilots.'),
        dict(k='spec', label='Rate', text=f'{fmt(s["rate"])} N/mm', grp='Force'),
        dict(k='spec', label='Fitted (track tight)', text=f'{fmt(s["set"], 1)} long, {fmt(f(s["set"]), 0)} N', grp='Force'),
        dict(k='spec', label='Idler at its recoil stop', text=f'{fmt(s["set"] - s["recoil"], 1)} long, {fmt(f(s["set"] - s["recoil"]), 0)} N', grp='Force'),
        dict(k='spec', label='Solid length; maximum load', text=f'{fmt(s["solid"], 1)}; {fmt(s["max_load"], 1)} N (catalogue)', grp='Force'),
    ]
    for n, r in enumerate(rows, 1):
        r['n'] = n
        r.setdefault('note', '')
        r.setdefault('key', False)
    return rows


def bought_dims(cfg):
    """Feature dimensions of the bought parts, in the frame of the CAD instance named with each list (track frame; X1 joint parts
    in the vehicle frame; chain hardware in its own frame, axis Y)."""
    DX, AZ = cfg['drive']
    IX = cfg['idler'][0]
    RX, RZ = cfg['rollers']['road0']
    gx, gz = DX - 9.0, AZ - 9.0                                    # MOTOR_HOLES[0]
    hx, hz = -103.0, 71.0                                          # HOUSING_SCREWS[0]
    can_y = -43.2
    d = {}
    shaft = ci((DX, -20, AZ), 'y', 3.0, (-28.4, -14.4), gap=90)
    d['motor'] = ('JGY370', [
        LEN('Gearbox length', pl((DX - 14.5, -41.5, AZ + 10), 'x'), pl((DX + 31.5, -33, AZ + 14), 'x'), (0, -10, 22), key=True, grp='Gearbox'),
        LEN('Gearbox height', pl((DX - 3, -41.5, AZ - 16), 'z'), pl((DX - 3, -41.5, AZ + 16), 'z'), (-20, 0, 0), key=True, grp='Gearbox'),
        LEN('Gearbox depth', pl((DX + 10, -53, AZ), 'y'), pl((DX + 10, -30, AZ), 'y'), (0, 0, 22), grp='Gearbox'),
        DIA('Centre boss', (DX, -29.2, AZ), 'y', 6.6, (-30, -28.4), text='Ø{v} × 1.6', exact=True, grp='Gearbox'),
        DIA('Screw bosses (4)', (gx, -29, gz), 'y', 3.5, (-30, -28), text='Ø{v} × 2', exact=True, grp='Mounting'),
        LEN('Mounting holes, along the gearbox', ci((gx, -29, gz), 'y', 1.5, (-36, -28)), ci((DX + 24, -29, gz), 'y', 1.5, (-36, -28)),
            (0, 0, -14), key=True, grp='Mounting', text='{v} (4 × M3)'),
        LEN('Mounting holes, across', ci((gx, -29, gz), 'y', 1.5, (-36, -28)), ci((gx, -29, AZ + 9), 'y', 1.5, (-36, -28)), (-12, 0, 0),
            key=True, grp='Mounting'),
        DIA('Output shaft', (DX, -20, AZ), 'y', 3.0, (-28.4, -14.4), text='Ø{v}, D-flat', key=True, gap=90, grp='Shaft'),
        LEN('Shaft length from the gearbox face', pl((DX + 10, -30, AZ), 'y'), pl((DX, -14.4, AZ - 2.2), 'y'), (0, 0, -14), key=True, grp='Shaft'),
        LEN('Across the D-flat', pl((DX, -16, AZ + 2.5), 'z'), cedge(shaft, (0, 0, -1)), (0, 8, 0), grp='Shaft', text='{v}, 12 long'),
        DIA('Motor can', (DX + 47, can_y, AZ), 'x', 12.0, (-78.5, -47.7), key=True, grp='Motor'),
        LEN('Can length', pl((-78.5, -33, AZ + 14), 'x'), pl((-47.7, can_y, AZ + 6), 'x'), (0, 0, 16), grp='Motor'),
        SPEC('Tapped shaft end', 'M3 × 10 deep (vendor drawing)', grp='Shaft', note='The M3 × 50 through the plug and sprocket goes in here.'),
        SPEC('Leads', '10 mm behind the can is kept clear for the solder tabs and leads (pale in the model)', grp='Motor'),
        SPEC('Rating (vendor table)', '12 V, 200:1, 30 rpm no load; 6 kgf·cm rated at 0.2 A; 20 kgf·cm stall at 1.3 A', grp='Electrical'),
    ])
    d['hub'] = ('flange_coupling_32', [
        DIA('Flange', (DX, -11.0, AZ), 'y', 16.0, (-13.0, -9.0), text='Ø{v} × 4', key=True, exact=True, grp='Coupling'),
        DIA('Boss', (DX, -18.0, AZ), 'y', 7.0, (-23.0, -13.0), text='Ø{v} × 10', key=True, exact=True, grp='Coupling'),
        DIA('Bore', (DX, -23.0, AZ), 'y', 3.0, (-23.0, -9.0), key=True, exact=True, grp='Coupling', note='The D = 6 version.'),
        PCD('Tapped holes', (DX, -9.0, AZ), 'y', 11.5, range(0, 360, 60), 1.5, (-13.0, -9.0), text='6 × M3 on Ø{v}', key=True, grp='Coupling',
            note='Three carry the sprocket (M3 × 20).'),
        LEN('Overall length', pl((DX + 5.0, -23.0, AZ), 'y'), pl((DX + 12.0, -9.0, AZ + 6.1), 'y'), (0, 0, 21), grp='Coupling'),
        SPEC('Set screw', 'One radial M3 in the boss, 5 mm from its end, halfway between two flange holes', grp='Coupling'),
        SPEC('Source', 'Seller drawing in references/flange_coupling_32; every value checked on the part', grp='Coupling'),
    ])
    d['setscrew'] = ('hub_set_screws', [
        DIA('Thread', (DX, -18.0, AZ + 4.5), 'z', 1.5, (AZ + 2.5, AZ + 6.5), text='M3', key=True, exact=True, grp='Set screw'),
        LEN('Length (as modelled)', pl((DX, -18.0, AZ + 2.5), 'z'), pl((DX, -18.0, AZ + 6.5), 'z'), (0, -6, 0), key=True, grp='Set screw'),
        SPEC('Length', 'The seller gives none. The CAD assumes 4 mm; up to 4.5 mm stays below the boss surface.', grp='Set screw'),
        SPEC('Key', '1.5 mm hex', grp='Set screw'),
    ])

    def bearing(name, c, y0, y1, dd, D):
        x, z = c
        return (name, [
            DIA('Bore d', (x, y1, z), 'y', dd / 2, (y0, y1), key=True, exact=True, grp='Bearing'),
            DIA('Outside D', (x, y1, z), 'y', D / 2, (y0, y1), key=True, exact=True, grp='Bearing'),
            LEN('Width B', pl((x + D / 2 - .35, y0, z), 'y'), pl((x + D / 2 - .35, y1, z), 'y'), (0, 0, D / 2 + 4), key=True, grp='Bearing'),
            SPEC('Shields', 'ZZ: a metal shield on each side', grp='Bearing'),
        ])
    d['6800ZZ'] = bearing('6800ZZ', (DX, AZ), 25, 30, 10, 19)
    d['624ZZ'] = bearing('624ZZ_road0_0', (RX, RZ), -23, -18, 4, 13)
    d['608ZZ'] = bearing('608ZZ_0', (IX, AZ), -10, -3, 8, 22)
    d['pin8'] = ('idler_pin_8x55', [
        DIA('Diameter', (IX, 27.5, AZ), 'y', 4.0, (-27.5, 27.5), key=True, exact=True, grp='Pin'),
        LEN('Length', pl((IX + 2, -27.5, AZ), 'y'), pl((IX + 2, 27.5, AZ), 'y'), (0, 0, 10), key=True, grp='Pin',
            note='Its ends stand 0.5 mm proud of the yoke arms.'),
    ])

    def screw(name, c, y_head, y_face, y_end, head_r, head_h, r, thread, keysize, std):
        x, z = c
        s = 1 if y_end > y_face else -1
        return (name, [
            DIA('Head', (x, y_head, z), 'y', head_r, sorted([y_head, y_face]), text=f'Ø{{v}} × {fmt(head_h)}', key=True, exact=True, grp='Screw'),
            DIA('Thread', (x, (y_face + y_end) / 2, z), 'y', r, sorted([y_face, y_end]), text=thread, key=True, exact=True, grp='Screw'),
            LEN('Length under the head', pl((x + (r + head_r) / 2, y_face, z), 'y'), pl((x + r / 2, y_end, z), 'y'), (0, 0, -(head_r + 4)),
                key=True, grp='Screw'),
            SPEC('Standard and key', f'{std}; {keysize} hex key', grp='Screw'),
        ])
    d['M4x70'] = screw('bolt_M4x70_road0', (RX, RZ), -34, -30, 40, 3.5, 4, 2.0, 'M4', '3 mm', 'ISO 4762 socket head')
    d['M3x6'] = screw('motor_screw_M3x6_0', (gx, gz), -22, -25, -31, 2.75, 3, 1.5, 'M3', '2.5 mm', 'ISO 4762 socket head')
    d['M3x20'] = screw('hub_screw_M3x20_0', (DX + 11.5, AZ), 8.5, 5.5, -14.5, 2.75, 3, 1.5, 'M3', '2.5 mm', 'ISO 4762 socket head')
    d['M3x50'] = screw('sprocket_screw_M3x50', (DX, AZ), 33, 30, -20, 2.75, 3, 1.5, 'M3', '2.5 mm', 'ISO 4762 socket head')
    d['M3x8'] = screw('housing_screw_M3x8_0', (hx, hz), -39.65, -38, -30, 2.85, 1.65, 1.5, 'M3', '2 mm', 'ISO 7380 button head (domed; drawn flat)')
    d['nyloc'] = ('nyloc_M4_road0', [
        LEN('Across flats', pl((RX, 32.5, RZ - 3.5), 'z'), pl((RX, 32.5, RZ + 3.5), 'z'), (0, 0, 0), key=True, grp='Nut', text='{v} AF'),
        LEN('Height', pl((RX + 3, 30, RZ), 'y'), pl((RX + 3, 35, RZ), 'y'), (0, 0, 8), key=True, grp='Nut'),
        DIA('Thread', (RX, 35, RZ), 'y', 2.0, (30, 35), text='M4', exact=True, grp='Nut'),
        SPEC('Standard and tool', 'DIN 985 (nylon ring); 7 mm spanner. Snug only: the rollers must still spin.', grp='Nut'),
    ])
    d['insert'] = ('insert_M3_0', [
        DIA('Hole it goes in (as modelled)', (hx, -35.5, hz), 'y', 2.0, (-35.5, -29.8), text='Ø{v} × 5.7', key=True, exact=True, grp='Insert'),
        DIA('Thread', (hx, -29.8, hz), 'y', 1.5, (-35.5, -29.8), text='M3', exact=True, grp='Insert'),
        SPEC('Choose', 'An M3 heat-set insert made for a Ø4.0 hole, no longer than 5.7 mm', grp='Insert'),
    ])
    d['trackpin'] = ('pin', [
        DIA('Diameter', (0, 28, 0), 'y', 1.5, (-28, 28), key=True, exact=True, grp='Pin'),
        LEN('Length', pl((.7, -28, 0), 'y'), pl((.7, 28, 0), 'y'), (0, 0, 6), key=True, grp='Pin'),
        SPEC('E-clip grooves', '1.5 mm from each end (centres 26.5 each side of the middle, 53 apart), sized for DIN 6799 size 2.3 (groove Ø2.3); '
             'not modelled', grp='Pin'),
    ])
    d['bushing'] = ('bushing', [
        DIA('Outside', (0, 8.5, 0), 'y', 3.0, (-8.5, 8.5), key=True, exact=True, grp='Bushing', note='The sprocket teeth drive on it.'),
        DIA('Bore', (0, 8.5, 0), 'y', 1.55, (-8.5, 8.5), key=True, exact=True, grp='Bushing', note='Must slip freely on the Ø3 pin.'),
        LEN('Length', pl((2.3, -8.5, 0), 'y'), pl((2.3, 8.5, 0), 'y'), (0, 0, 7), key=True, grp='Bushing'),
    ])
    d['clip'] = ('clip', [
        DIA('Outside (as modelled)', (0, .3, 0), 'y', 3.0, (-.3, .3), key=True, exact=True, gap=70, grp='E-clip'),
        LEN('Thickness (as modelled)', pl((-2.3, -.3, 0), 'y'), pl((-2.3, .3, 0), 'y'), (0, 0, 5), key=True, grp='E-clip'),
        SPEC('Size', 'DIN 6799 size 2.3: for a Ø2.3 groove on Ø3-4 shafts', grp='E-clip'),
    ])
    d['dummy'] = ('dummy', [
        DIA('Diameter', (0, 12, 0), 'y', 1.5, (-12, 12), key=True, exact=True, grp='Dummy pin'),
        LEN('Length', pl((.7, -12, 0), 'y'), pl((.7, 12, 0), 'y'), (0, 0, 6), key=True, grp='Dummy pin',
            note='Shorter than the 27.4 mm over the inner ears, so the outer plates still pass over it.'),
    ])
    # X1 joint parts, vehicle frame (left track, joint L00: X -73, Z 67.75; j9_mounts + 170 in Y)
    jx, jz = -73.0, 67.75
    d['M4x25'] = screw('mount_screw_M4x25_L00', (jx, jz), 122.2, 126.2, 151.2, 3.5, 4, 2.0, 'M4', '3 mm (L-key, 20 mm short leg)', 'ISO 4762 socket head')
    d['washer4'] = ('mount_washer_L00', [
        DIA('Outside', (jx, 127, jz), 'y', 4.5, (126.2, 127), key=True, exact=True, grp='Washer'),
        DIA('Bore', (jx, 127, jz), 'y', 2.2, (126.2, 127), key=True, exact=True, grp='Washer'),
        LEN('Thickness', pl((jx + 3.3, 126.2, jz), 'y'), pl((jx + 3.3, 127, jz), 'y'), (0, 0, 7), key=True, grp='Washer'),
    ])
    d['nut4'] = ('mount_nut_M4_L00', [
        LEN('Across flats', pl((jx, 148.4, jz - 3.5), 'z'), pl((jx, 148.4, jz + 3.5), 'z'), (0, 0, 0), key=True, grp='Nut', text='{v} AF'),
        LEN('Height', pl((jx + 3, 146.8, jz), 'y'), pl((jx + 3, 150, jz), 'y'), (0, 0, 7), key=True, grp='Nut'),
        DIA('Thread', (jx, 150, jz), 'y', 2.0, (146.8, 150), text='M4', exact=True, grp='Nut'),
        SPEC('Standard and tool', 'ISO 4032; a compact 7 mm nut holder (within Ø11.2) inside the track', grp='Nut'),
    ])
    return d


# --------------------------------------------------------------------------------------------- materials (what each item is made of)
MAT_PRINT = {
    'PETG': 'PETG (polyester). The kit\'s mass figures use 1.27 g/cm³.',
    'PA12': 'PA12 (nylon 12) is the alternative the design names for this part.',
}
MATERIAL = {   # bought items: what they are made of, as specified by the design or the standard named in the kit list
    'motor': ('Bought assembly', 'Brushed 12 V DC motor (370 can) on a worm gearbox; metal housing. A worm gearbox is normally self-locking: the track cannot be turned by hand.'),
    'hub': ('Aluminium', 'Flange coupling with a 6 mm bore (seller drawing in references/flange_coupling_32); comes with one M3 set screw.'),
    'setscrew': ('Steel', 'Supplied with the coupling.'),
    '6800ZZ': ('Bearing steel', 'Deep-groove ball bearing; chrome steel rings and balls are standard. Stainless versions (S6800ZZ) have the same size.'),
    '624ZZ': ('Bearing steel', 'Deep-groove ball bearing; chrome steel rings and balls are standard. Stainless versions (S624ZZ) have the same size.'),
    '608ZZ': ('Bearing steel', 'Deep-groove ball bearing; chrome steel rings and balls are standard. Stainless versions (S608ZZ) have the same size.'),
    'pin8': ('Steel', 'ISO 2338 dowel pin 8 m6 × 55, or Ø8 steel shaft cut to 55 and deburred.'),
    'spring': ('Music wire', 'Lee Spring C-600-072-1500, music wire. A substitute must slide in the Ø16.4 bore and over the Ø11 pilot.'),
    'M4x70': ('Steel', 'No grade is specified: any ISO 4762 steel or stainless screw.'),
    'nyloc': ('Steel with a nylon ring', 'DIN 985 prevailing-torque nut.'),
    'M3x6': ('Steel', 'No grade is specified: any ISO 4762 steel or stainless screw.'),
    'M3x20': ('Steel', 'No grade is specified: any ISO 4762 steel or stainless screw.'),
    'M3x50': ('Steel', 'No grade is specified: any ISO 4762 steel or stainless screw.'),
    'M3x8': ('Steel', 'No grade is specified: any ISO 7380 steel or stainless button head.'),
    'insert': ('Brass', 'Heat-set (thermal) insert, pressed in with a soldering iron and an M3 insert tip.'),
    'trackpin': ('Silver steel', 'Ground Ø3 silver-steel rod, yield at least 400 MPa, cut to 56 and grooved at both ends. Not off the shelf.'),
    'bushing': ('Steel tube', 'Cut from Ø6 × Ø3.1 steel tube and deburred at both ends. Not off the shelf.'),
    'clip': ('Spring steel', 'DIN 6799 retaining washer (E-clip), usually phosphated or zinc plated. Buy spares: they jump.'),
    'M4x25': ('Steel', 'No grade is specified: any ISO 4762 steel or stainless screw.'),
    'washer4': ('Steel', 'Plain washer Ø9 / Ø4.4 × 0.8.'),
    'nut4': ('Steel', 'ISO 4032 hex nut.'),
    'dummy': ('Any rod', 'An offcut of the Ø3 pin rod (or any Ø2.5-3 rod), ends deburred.'),
}
OPEN_POINTS = {   # known open questions on the part as it is drawn now (not decided; see J9/README.md and the session notes)
    'insert': 'The blind hole is exactly as deep as the insert. Insert makers usually ask for about 1 mm more. Not decided: drill the holes to '
              '6.7 mm by hand, use M3 × 6 screws, or deepen the holes in the CAD.',
    'J901': 'The four insert holes are blind Ø4.0 × 5.7, the same as the insert length (see the M3 heat-set insert). Not decided.',
    'pin8': 'An m6 pin is a light press fit in the 608 inner rings, which cannot be backed up inside the yoke; a g6 or h6 rod slides in. '
            'Not decided.',
}


# --------------------------------------------------------------------------------------------- geometry library
class Library:
    def __init__(self):
        self.geos, self.keys = [], {}

    def add(self, key, V, T, kind):
        if key in self.keys:
            return self.keys[key]
        wide = len(V) >= 65536
        a = array.array('f', (c for v in V for c in v))
        b = array.array('I' if wide else 'H', (c for t in T for c in t))
        if sys.byteorder != 'little':
            a.byteswap()
            b.byteswap()
        self.geos.append(dict(key=key, kind=kind, wide=wide, nt=len(T), v=base64.b64encode(a.tobytes()).decode(),
                              t=base64.b64encode(b.tobytes()).decode()))
        self.keys[key] = len(self.geos) - 1
        return self.keys[key]


def centred(mesh):
    S = mesh_stats(mesh['vertices'], mesh['triangles'])
    c = [(a + b) / 2 for a, b in zip(S['lo'], S['hi'])]
    rel = [[v[0] - c[0], v[1] - c[1], v[2] - c[2]] for v in mesh['vertices']]
    sig = hashlib.sha256(json.dumps([[round(x, 3) for x in v] for v in rel] + mesh['triangles']).encode()).hexdigest()[:16]
    return c, rel, sig


# --------------------------------------------------------------------------------------------- main
def main(check_only=False):
    j9 = json.loads(gzip.decompress((HERE / 'j9_scene.json.gz').read_bytes()))
    x1 = json.loads(gzip.decompress((X1 / 'source/x1_scene.json.gz').read_bytes()))
    cfg = j9['config']
    assert 'revision F' in cfg['revision'], cfg['revision']
    assert x1['module'] == j9['unit'] and x1['j9'] == cfg, 'X1 scene does not hold the current J9 module: run X1 build_viewer.py first'
    track_y = x1['config']['track_y']
    report = dict(generator='track_wheel_jgy370/J9/source/build_parts_showcase.py', revision=cfg['revision'],
                  inputs_sha256={str(p.relative_to(REPO)): sha(p) for p in (HERE / 'j9_scene.json.gz', X1 / 'source/x1_scene.json.gz',
                                                                          HERE / 'build_track_kit.py', HERE / 'parts_showcase.html', Path(__file__))})
    lib = Library()
    revf = {e['stl_file']: e for e in json.loads((X1 / 'revf_part_exports.json').read_text())['exports']}

    # ---------------------------------------------------------------- printed parts: the STL files, placed against the CAD scene
    unit_by = {p['name']: p for p in j9['unit']}
    chassis_by = {p['name']: p for p in x1['chassis']}
    stl, stl_facts, fits = {}, {}, {}
    for it in K.PRINTED + K.OPTIONAL_PRINTED:
        for side, rel in it['files'].items():
            f = K.read_stl(REPO / rel)
            if rel in revf:
                assert revf[rel]['stl_sha256'] == f['sha256'], f'{rel} differs from revf_part_exports.json'
            stl_facts[rel] = dict(size_mm=[round(b - a, 1) for a, b in zip(f['lo'], f['hi'])], volume_cm3=round(f['volume_cm3'], 2),
                                  area_cm2=round(f['area_cm2'], 1), triangles=f['triangles'], sha256=f['sha256'],
                                  beds={f'{w}x{dd}': K.bed_fit(f['hull'], w, dd) for w, dd in K.BEDS})
    mirror = {}
    for it in K.PRINTED + K.OPTIONAL_PRINTED:
        files = it['files']
        main_rel = files.get('left') or files.get('both') or files.get('chassis')
        stl[it['id']] = load_stl(main_rel)
        if 'right' in files:
            # the right-hand file is the left one mirrored across Y in the print frame: same triangles, vertex for vertex
            L, R = stl[it['id']], load_stl(files['right'])
            tl = {frozenset((round(L['V'][i][0], 4), round(-L['V'][i][1], 4), round(L['V'][i][2], 4)) for i in t) for t in L['T']}
            tr = {frozenset((round(R['V'][i][0], 4), round(R['V'][i][1], 4), round(R['V'][i][2], 4)) for i in t) for t in R['T']}
            assert len(L['T']) == len(R['T']) and tl == tr, f'{files["right"]} is not the mirror of {main_rel}'
            mirror[it['id']] = dict(left=main_rel, right=files['right'], triangles=len(L['T']), same_triangles_mirrored=True,
                                    right_sha256=R['sha256'])
    report['right_files_mirror_left'] = mirror
    for k, m in stl.items():
        m['geo'] = lib.add('stl:' + k, m['V'], m['T'], 'printed')

    # each printed instance in the scenes: transform track/vehicle/link frame -> STL frame
    def scene_mesh(name):
        if name == 'link':
            return dict(j9['link'][0], name='link')
        return unit_by.get(name) or chassis_by[name]
    inst_fit = {}
    for p in j9['unit']:
        if p['kind'] == 'printed':
            k = K.kit_id(p['name'])
            inst_fit[p['name']] = fit_print(stl[k], p, PRINT_ROT[k])
    inst_fit['link'] = fit_print(stl['J910'], scene_mesh('link'), PRINT_ROT['J910'])
    inst_fit['X101_X_frame'] = fit_print(stl['X101'], chassis_by['X101_X_frame'], PRINT_ROT['X101'])
    report['print_files_against_cad'] = {n: f[2] for n, f in inst_fit.items()}

    # ---------------------------------------------------------------- bought parts: CAD meshes, one geometry per distinct shape
    def bought_geo(mesh):
        c, rel, sig = centred(mesh)
        return c, lib.add('cad:' + sig, rel, mesh['triangles'], 'bought')
    hw = K.hardware_meshes(j9['link'])
    hw_geo = {k: lib.add('hw:' + k, v['vertices'], v['triangles'], 'bought') for k, v in hw.items()}

    # ---------------------------------------------------------------- context scenes: the left track module, and X1
    def inst(g, color, M, item, kind, name, env=False):
        return dict(g=g, c=[round(x, 3) for x in color], m=col(M), item=item, kind=kind, name=name, piece=K.piece(name),
                    **({'env': True} if env else {}))
    module = []
    for p in j9['unit']:
        n = p['name']
        item = K.kit_id(n)
        if n == 'recoil_spring':
            continue                                        # drawn by the page from the catalogue values (spring below)
        if p['kind'] == 'printed':
            R, t, _ = inst_fit[n]
            Rt = tp(R)
            M = m4(Rt, [-x for x in mv(Rt, t)])
            module.append(inst(stl[item]['geo'], p['color'], M, item, 'printed', n))
        else:
            c, g = bought_geo(p)
            module.append(inst(g, p['color'], m4(None, c), item, 'bought', n, env=n == 'JGY370_terminal_space'))
    # the chain, as fitted (3D_preview.html placement): shoe j between pins j and j+1, pin, bushing and two E-clips at pin j
    P = cfg['pins']
    R0, t0, _ = inst_fit['link']
    shoe_from_stl = m4(tp(R0), [-x for x in mv(tp(R0), t0)])
    for j in range(len(P)):
        a, b = P[j], P[(j + 1) % len(P)]
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        M = mul4(m4(rot_y(-ang), ((a[0] + b[0]) / 2, 0, (a[1] + b[1]) / 2)), shoe_from_stl)
        module.append(inst(stl['J910']['geo'], j9['link'][0]['color'], M, 'J910', 'printed', f'shoe_{j:02}'))
        module.append(inst(hw_geo['pin'], hw['pin']['color'], m4(None, (a[0], 0, a[1])), 'trackpin', 'bought', f'track_pin_{j:02}'))
        module.append(inst(hw_geo['bushing'], hw['bushing']['color'], m4(None, (a[0], 0, a[1])), 'bushing', 'bought', f'track_bushing_{j:02}'))
        for s in (-1, 1):
            module.append(inst(hw_geo['clip'], hw['clip']['color'], m4(rot_y(-(ang - math.pi / 2)), (a[0], s * K.CLIP_Y, a[1])), 'clip', 'bought',
                               f'pin_clip_{j:02}_{(s + 1) // 2}'))
    sp = unit_by['recoil_spring']
    S = mesh_stats(sp['vertices'], sp['triangles'])
    spring_fit = dict(x0=round(S['lo'][0], 4), y=0.0, z=round((S['lo'][2] + S['hi'][2]) / 2, 4), length=round(S['hi'][0] - S['lo'][0], 4),
                      od=round(S['hi'][1] - S['lo'][1], 4))
    assert abs(spring_fit['length'] - SPRING['set']) < .01 and abs(spring_fit['od'] - SPRING['od']) < .01, spring_fit
    assert abs(spring_fit['z'] - cfg['drive'][1]) < .01
    module.append(dict(g=-1, spring=spring_fit['length'], c=[round(x, 3) for x in sp['color']],
                       m=col(m4(None, (spring_fit['x0'], spring_fit['y'], spring_fit['z']))), item='spring', kind='bought', name='recoil_spring',
                       piece='recoil_spring'))
    x1ctx = []
    for p in x1['chassis']:
        n = p['name']
        if n == 'X101_X_frame':
            R, t, _ = inst_fit[n]
            Rt = tp(R)
            x1ctx.append(inst(stl['X101']['geo'], p['color'], m4(Rt, [-x for x in mv(Rt, t)]), 'X101', 'printed', n))
        elif n.startswith('mount_'):
            c, g = bought_geo(p)
            x1ctx.append(inst(g, p['color'], m4(None, c), K.kit_id(n), 'bought', n))

    # ---------------------------------------------------------------- items
    PD, BD = printed_dims(cfg), bought_dims(cfg)
    steps = {s['id']: (i, s['title']) for i, s in enumerate(K.STEPS)}
    first = {}
    for p in j9['unit']:
        first.setdefault(K.kit_id(p['name']), K.STEPS[K.module_anim(p['name'])[0]['s']]['id'])
    first.update(J910='chain', trackpin='chain', bushing='chain', clip='chain', dummy='chain', M4x25='xframe', washer4='xframe', nut4='xframe',
                 X101='xframe')
    checks, items = [], []
    counts = {}
    for m in module:
        counts[m['item']] = counts.get(m['item'], 0) + 1
    pieces = {}
    for p in j9['unit']:
        pieces.setdefault(K.kit_id(p['name']), set()).add(K.piece(p['name']))
    per_track_cad = {k: len(v) for k, v in pieces.items()}
    per_track_cad.update(J910=len(P), trackpin=len(P), bushing=len(P), clip=2 * len(P))

    def step_of(k):
        s = first.get(k)
        return dict(n=steps[s][0], title=steps[s][1]) if s else None

    def printed_item(it, optional=False):
        k = it['id']
        files = it['files']
        rel = files.get('left') or files.get('both') or files.get('chassis')
        f = stl_facts[rel]
        ref = PD[k][0]
        R, t, _ = inst_fit[ref]
        frame = Frame(R, t)
        dims, ch = resolve(PD[k][1], frame, stl[k], k)
        checks.extend(ch)
        # the fitted pose: STL frame -> CAD frame, centred on the part
        Rt = tp(R)
        M = m4(Rt, [-x for x in mv(Rt, t)])
        lo, hi = stl[k]['lo'], stl[k]['hi']
        corners = [[lo[0] if i & 1 else hi[0], lo[1] if i & 2 else hi[1], lo[2] if i & 4 else hi[2]] for i in range(8)]
        cad = [mv(Rt, [c[0] - t[0], c[1] - t[1], c[2] - t[2]]) for c in corners]
        cc = [(min(c[i] for c in cad) + max(c[i] for c in cad)) / 2 for i in range(3)]
        M = mul4(m4(None, [-x for x in cc]), M)
        if optional:
            qty = dict(total=it['per_machine'], text=f'{it["per_machine"]} (only to test the chassis mounting)')
            per = None
        else:
            q = K.qty_files(it)
            total = sum(q.values())
            text = f'{total}' + (f' ({q["left"]} left + {q["right"]} right print)' if 'right' in q else f' ({it["per_track"]} per track)')
            qty = dict(total=total, text=text)
            per = it['per_track']
        walls, infill, assumed = it.get('est', (None, None, False))
        mass = dict(solid_g=round(f['volume_cm3'] * PETG, 1))
        if walls is not None:
            mass['estimate_g'] = round(K.estimate_cm3(f, walls, infill) * PETG, 1)
            mass['estimate_basis'] = (f'{walls} walls, {round(infill * 100)} % infill' + (' (assumed: the design gives no infill)' if assumed else '')
                                      if infill < 1 else '100 % infill')
        mats = [m for m in ('PETG', 'PA12') if m in it['settings']]
        files_out = [dict(label={'left': 'Left track', 'right': 'Right track (mirrored)', 'both': 'Both tracks', 'chassis': 'X1 chassis'}[s],
                          stl=r, step=STEP_FILES.get(k, {}).get(s) or r.replace('/stl/', '/step/').replace('.stl', '.step'),
                          sha256=stl_facts[r]['sha256'], copies=(K.qty_files(it)[s] if not optional else it['per_machine']), pkg=K.package_stl(it, s, r))
                     for s, r in files.items()]
        for fo in files_out:
            assert (REPO / fo['step']).exists(), fo['step']
        beds = {b: v for b, v in f['beds'].items()}
        return dict(id=k, type='print-opt' if optional else 'print', cat='Print: optional chassis test' if optional else 'Print: track parts',
                    name=it['name'], qty=qty, per_track=per, material=dict(name=' or '.join(mats) or 'PETG', notes=[MAT_PRINT[m] for m in mats]),
                    settings=it['settings'], orientation=it['orientation'], note=it['note'], files=files_out, mirror='right' in files,
                    size=f['size_mm'], volume_cm3=f['volume_cm3'], triangles=f['triangles'], mass=mass, beds=beds,
                    step=step_of(k), open=OPEN_POINTS.get(k), dims=dims,
                    model=dict(parts=[dict(g=stl[k]['geo'], c=[round(x, 3) for x in scene_mesh(ref)['color']], m=col(m4()))],
                               fit=col(M), bed=True, frame='stl', rot_x=PRINT_ROT[k]),
                    context='x1' if optional else 'module')

    def bought_item(it, cat, name_key, meshes, dims_key, qty, per, step_id=None, context='module', spring=False):
        k = it['id']
        model, dims = None, []
        if meshes:
            Ss = [mesh_stats(m['vertices'], m['triangles']) for m in meshes]
            lo = [min(s['lo'][i] for s in Ss) for i in range(3)]
            hi = [max(s['hi'][i] for s in Ss) for i in range(3)]
            c = [(a + b) / 2 for a, b in zip(lo, hi)]
            parts = []
            for m in meshes:
                mc, g = bought_geo(m) if m.get('_hw') is None else (m['_c'], m['_hw'])
                parts.append(dict(g=g, c=[round(x, 3) for x in m['color']], m=col(m4(None, [mc[i] - c[i] for i in range(3)])),
                                  **({'env': True} if m['name'] == 'JGY370_terminal_space' else {})))
            model = dict(parts=parts, frame='cad', size=[round(b - a, 2) for a, b in zip(lo, hi)])
            if dims_key in BD:
                V = [[v[i] for i in range(3)] for m in meshes for v in m['vertices']]
                T, off = [], 0
                for m in meshes:
                    T += [[a + off, b + off, cc + off] for a, b, cc in m['triangles']]
                    off += len(m['vertices'])
                dims, ch = resolve(BD[dims_key][1], Frame(None, [-x for x in c]), dict(V=[[v[0] - c[0], v[1] - c[1], v[2] - c[2]] for v in V], T=T), k)
                checks.extend(ch)
        if spring:
            model = dict(spring=dict(SPRING, id=SPRING['od'] - 2 * SPRING['wire']), frame='cad', size=[SPRING['free'], SPRING['od'], SPRING['od']])
            dims = spring_dims()
        mat = MATERIAL.get(k, ('', ''))
        return dict(id=k, type={'Track chain': 'chain', 'X1 joint': 'joint'}.get(cat, 'buy'), cat=f'Buy: {cat.lower()}' if cat not in ('X1 joint',)
                    else 'Buy: X101 joints (only on the chassis)', name=it['name'], qty=qty, per_track=per,
                    material=dict(name=mat[0], notes=[mat[1]] if mat[1] else []), spec=it.get('spec', ''), buy=it.get('buy', ''),
                    step=step_of(step_id or k), open=OPEN_POINTS.get(k), dims=dims, model=model, context=context if model else None)

    def scene_piece(names):
        return [unit_by[n] for n in names]

    piece_meshes = {
        'motor': scene_piece(['JGY370_gearbox', 'JGY370_motor_can', 'JGY370_terminal_space', 'JGY370_output_shaft']),
        'hub': scene_piece(['flange_coupling_32']),
        'setscrew': scene_piece(['hub_set_screw_M3x4']),
        '6800ZZ': scene_piece(['6800ZZ_inner', '6800ZZ_outer', '6800ZZ_shield']),
        '624ZZ': scene_piece(['624ZZ_road0_0_inner', '624ZZ_road0_0_outer', '624ZZ_road0_0_shield']),
        '608ZZ': scene_piece(['608ZZ_0_inner', '608ZZ_0_outer', '608ZZ_0_shield']),
        'pin8': scene_piece(['idler_pin_8x55']),
        'M4x70': scene_piece(['bolt_M4x70_road0']), 'nyloc': scene_piece(['nyloc_M4_road0']),
        'M3x6': scene_piece(['motor_screw_M3x6_0']), 'M3x20': scene_piece(['hub_screw_M3x20_0']),
        'M3x50': scene_piece(['sprocket_screw_M3x50']), 'M3x8': scene_piece(['housing_screw_M3x8_0']), 'insert': scene_piece(['insert_M3_0']),
        'M4x25': [chassis_by['mount_screw_M4x25_L00']], 'washer4': [chassis_by['mount_washer_L00']], 'nut4': [chassis_by['mount_nut_M4_L00']],
    }
    dims_key = {'motor': 'motor', 'hub': 'hub', 'setscrew': 'setscrew', '6800ZZ': '6800ZZ', '624ZZ': '624ZZ', '608ZZ': '608ZZ', 'pin8': 'pin8',
                'M4x70': 'M4x70', 'nyloc': 'nyloc', 'M3x6': 'M3x6', 'M3x20': 'M3x20', 'M3x50': 'M3x50', 'M3x8': 'M3x8', 'insert': 'insert',
                'M4x25': 'M4x25', 'washer4': 'washer4', 'nut4': 'nut4'}
    for it in K.PRINTED:
        items.append(printed_item(it))
    for it in K.OPTIONAL_PRINTED:
        items.append(printed_item(it, optional=True))
    for it in K.STANDARD:
        q = 2 * it['per_track']
        qty = dict(total=q, text=f'{q} ({it["per_track"]} per track)' + (f'; {it["buy"]}' if it.get('buy') else ''))
        items.append(bought_item(it, it['cat'], it['id'], piece_meshes.get(it['id']), dims_key.get(it['id']), qty, it['per_track'],
                                 spring=it['id'] == 'spring'))
    for it in K.CHAIN:
        q = 2 * it['per_track']
        hwk = dict(trackpin='pin', bushing='bushing', clip='clip')[it['id']]
        m = dict(hw[hwk], _hw=hw_geo[hwk], _c=[0, 0, 0])
        items.append(bought_item(it, 'Track chain', it['id'], [m], hwk, dict(total=q, text=f'{q} ({it["per_track"]} per track)'), it['per_track']))
    for it in K.JOINT:
        items.append(bought_item(it, 'X1 joint', it['id'], piece_meshes[it['id']], dims_key[it['id']],
                                 dict(total=it['per_machine'], text=f'{it["per_machine"]} per machine (both tracks)'), None, context='x1'))
    for i, it in enumerate(K.BENCH):
        items.append(dict(id=f'bench{i}', type='bench', cat='First powered test (not in the CAD)', name=it['name'], qty=dict(total=None, text=it['qty']),
                          spec=it['spec'], material=dict(name='', notes=[]), dims=[], model=None, context=None, step=dict(n=steps['test'][0], title=steps['test'][1])))
    for i, (tool, use) in enumerate(K.TOOLS):
        if tool.startswith('Dummy pin'):
            m = dict(hw['dummy'], _hw=hw_geo['dummy'], _c=[0, 0, 0])
            items.append(dict(bought_item(dict(id='dummy', name=tool, spec=use), 'Tools', 'dummy', [m], 'dummy', dict(total=1, text='1, made from an offcut'),
                                          None, step_id='chain', context=None), type='tool', cat='Tools and aids'))
        else:
            items.append(dict(id=f'tool{i}', type='tool', cat='Tools and aids', name=tool, qty=dict(total=None, text=''), spec=f'For {use}.',
                              material=dict(name='', notes=[]), dims=[], model=None, context=None, step=None))

    # the list against the kit: every kit row is here once, and the CAD scene holds the per-track quantities of each modelled item
    ids = [i['id'] for i in items]
    assert len(ids) == len(set(ids)), 'duplicate item'
    kit_ids = [i['id'] for i in K.PRINTED + K.OPTIONAL_PRINTED + K.STANDARD + K.CHAIN + K.JOINT]
    assert all(k in ids for k in kit_ids) and len(K.BENCH) == sum(i['type'] == 'bench' for i in items)
    for i in items:
        if i['id'] in per_track_cad and i.get('per_track') is not None:
            assert per_track_cad[i['id']] == i['per_track'], (i['id'], per_track_cad[i['id']], i['per_track'])
            i['cad_per_track'] = per_track_cad[i['id']]
    for i in items:
        if i.get('context') == 'module':
            n = len({m['piece'] for m in module if m['item'] == i['id']})
            assert n == i['per_track'], (i['id'], n, i['per_track'])
            i['track_pieces'] = n
    x1_counts = {}
    for m in x1ctx:
        x1_counts[m['item']] = x1_counts.get(m['item'], 0) + 1
    assert x1_counts == {'X101': 1, 'M4x25': 8, 'washer4': 16, 'nut4': 8}, x1_counts
    # every printed item draws its overall size as well; the sizes are the kit's
    for i in items:
        if i['type'].startswith('print'):
            rel = i['files'][0]['stl']
            assert i['size'] == stl_facts[rel]['size_mm']

    if check_only:
        print(len(items), 'items;', len(checks), 'dimensions checked on the meshes;', len(lib.geos), 'meshes,',
              sum(g['nt'] for g in lib.geos), 'triangles (nothing written)')
        return
    totals = K.totals()
    notes = K.print_notes(stl_facts)
    data = dict(items=items, geos=lib.geos, module=module, x1=dict(parts=x1ctx, track_y=track_y), spring_fit=spring_fit,
                totals=dict(totals, solid_petg_kg=notes['solid_petg_kg'], estimate_petg_kg=notes['estimate_petg_kg']),
                kit=dict(md='TRACK_KIT.md', animation='install_animation.html'), revision=cfg['revision'],
                cfg=dict(drive=cfg['drive'], idler=cfg['idler'], pitch=cfg['pitch']))
    vendor = REPO / 'actuator_v6/source/vendor'
    html = (HERE / 'parts_showcase.html').read_text()
    for k, v in {'__THREE__': (vendor / 'three.min.js').read_text(), '__ORBIT__': (vendor / 'OrbitControls.js').read_text(),
                 '__DATA__': json.dumps(data, separators=(',', ':'), ensure_ascii=False)}.items():
        assert html.count(k) == 1, k
        html = html.replace(k, v)
    (ROOT / 'parts_showcase.html').write_text(html)
    report.update(
        items=[dict(id=i['id'], type=i['type'], name=i['name'], qty=i['qty']['text'], model=bool(i.get('model')),
                    dimensions_drawn=sum(1 for d in i['dims'] if d['k'] != 'spec'), table_rows=len(i['dims']) + (1 if i['type'].startswith('print') else 0))
               for i in items],
        dimension_checks=checks, spring=dict(catalogue=SPRING, cad_fitted=spring_fit),
        context=dict(module_instances=len(module), module_items=counts, x1_instances=len(x1ctx), x1_items=x1_counts),
        geometry=dict(meshes=len(lib.geos), triangles=sum(g['nt'] for g in lib.geos)),
        outputs_sha256={'parts_showcase.html': sha(ROOT / 'parts_showcase.html')}, **{'pass': True})
    (ROOT / 'parts_showcase_report.json').write_text(json.dumps(report, indent=1, ensure_ascii=False) + '\n')
    print('parts_showcase.html', round(len(html.encode()) / 1e6, 2), 'MB;', len(items), 'items;', len(checks), 'dimensions checked on the meshes;',
          len(lib.geos), 'meshes')


if __name__ == '__main__':
    main(check_only='--check-only' in sys.argv[1:])

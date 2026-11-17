#!/usr/bin/env python3
"""Parts showcase for the V6 actuator (rev 6.2): every part to print or buy for the R12 arm's four V6-U60, in 3D, with its
dimensions and material, the four print plates, and where each part sits in the actuator.

Writes:
  ../parts_showcase.html          offline page (three.js r128 and OrbitControls from vendor/, one file). Pick a part to turn it,
                                  see it on the print bed or as fitted, cut it open, read its dimensions on the model and in a
                                  table, and find it in the actuator, whole or cut open
  ../parts_showcase_report.json   what was checked (see below)

The printed parts are shown from their STL files, the files you print; the print plates from the plate STL files of
build_print_plates.py. The bought parts are shown from the CAD scene of the assembled V6-U60 (scene_U60.json.gz, written by
build_viewer.py); those models are simplified (no thread, no knurl). Every dimension drawn on a model is checked against that
model's mesh before the page is written: a diameter must be a circle of that radius on the mesh over the stated length, and a
length must end on faces of the mesh. The values come from layout.py and the BOM. The report also records each print file
against the CAD scene (same solid: bounding box, centroid and volume), each fit sample against the CAD cut it comes from, the
quantities against the scene (per actuator), and every file's SHA-256.

Inputs: scene_U60.json.gz, ../stl/V6-U60/*.stl, ../stl/fit_samples/*.stl, ../validation.json (print setups), ../SHA256SUMS.txt,
../wire_lengths_U60.csv, ../print_plates/V6-U60_x4/plates.json, parts_showcase.html (template), vendor/ (three.js).
Standard library only:  python3 actuator_v6/source/build_parts_showcase.py [--check-only]
The page links its files by their paths in this folder, so a copy with the same layout (a print-kit zip) works as it is.
Then check the page in Chromium:  NODE_PATH=<playwright node_modules> node actuator_v6/source/check_parts_showcase.cjs
"""
import array
import base64
import csv
import gzip
import hashlib
import json
import math
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                       # actuator_v6
REPO = ROOT.parent
sys.path.insert(0, str(HERE))
import layout as L                       # noqa: E402  shared geometry (standard library only)
import build_print_plates as PP          # noqa: E402  the plates: settings, files, checks

VARIANT, COUNT = 'U60', 4                # the R12 arm's four drives (excavator_complete/BOM.md)
TOL = 0.012                              # mm: a feature must be on the mesh within this
PETG = 1.27                              # g/cm3, as build_v6.py
FLIP = ('01_', '02_', '03_', '08_', '10_', '11_')     # build_v6.FLIP: printed upside down (rotation 180 deg about X)
DISP = [[0, 0, 1], [0, -1, 0], [1, 0, 0]]             # CAD frame -> page frame: the axis across the screen, board side up
F32 = struct.Struct('<3f')                            # an STL vertex as stored


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
    """Rigid transform CAD (assembly) frame -> STL frame for a printed part: the export's rotation about X, then the
    translation that build_v6.orient_for_print applies (centred in X and Y, on the bed). Checked: the two meshes (different
    tessellations of one solid) agree in bounding box, centroid and volume."""
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
# Anchors and dimensions are written in the CAD frame of the assembled actuator (layout.py: Z the axis, +X the board side, travel
# 0), then moved into the frame the page draws the model in.
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




# --------------------------------------------------------------------------------------------- the parts
D = L.derived(VARIANT)
X0, X1, YH = L.BODY_X[0], L.BODY_X[1], L.BODY_Y
BX, BY = L.BORE_X, L.BORE_Y
ZR, ZF = D['body_z']                     # rear and front faces of the body
ZC = D['front_cap_z'][1]                 # front cap's outer face
ZE = ZR - L.REAR_HOOK['reach']           # end of the motor-side wall
C0, C1 = L.CARRIER_Z0, L.CARRIER_Z0 + L.CARRIER_LEN
RE = D['rod_end_z']
CLAMP_Z = ZR - L.REAR_CAP_T + L.CLAMP_POCKET
I, S = L.INSERT, L.CAP_SCREW

PRINTED = [   # id, name, the per-actuator count, what it is for
    ('01_body', 'Body', 1, 'The square tube: motor bay at the rear, the carrier bore in front, the board slot behind a 1 mm '
     'partition, and five M1 insert holes in its end faces (two at the rear, three at the front). The end of the motor-side '
     'wall reaches into the rear cap and hooks it.'),
    ('02_front_cap', 'Front cap', 1, 'Guides the rod (Ø8.3 hole), stops the carrier (spigot) and holds the board\'s front '
     'edge (tongue). Three M1 × 8 into the front inserts: two on the board side, one in the motor-side corner.'),
    ('03_rear_cap', 'Rear cap', 1, 'Carries the rear clevis eye. Hooks onto the end of the motor-side wall, and two M1 × 8 '
     'through the cable clamp hold it on the board side.'),
    ('04_rod', 'Rod and nut carrier', 1, 'One part: the carrier slides in the bore, holds the brass M4 nut and the magnet; the '
     'Ø8 rod runs out through the front cap.'),
    ('05_rod_eye', 'Rod eye', 1, 'The front clevis eye, on the end of the rod; one M2 × 10 cross screw.'),
    ('06_cable_clamp', 'Cable clamp', 1, 'Plate in the rear cap\'s pocket: grips the 3 mm sleeve over W1 and W2 under the two '
     'rear-cap screws.'),
]
FIT = [
    ('08_fit_body_wall', 'Fit sample 08: motor bay and bore', 'The body from 10 mm behind to 8 mm in front of the motor wall: '
     'the motor slides into the bay, the M1.6 screws sit flush, the board or a 0.8 mm card slides into the slot, and sample 09 '
     'slides through the bore one way round only.'),
    ('09_fit_carrier', 'Fit sample 09: carrier', 'The carrier with 1.5 mm of rod: the brass nut drops into the hex slot, the '
     'magnet presses into its pocket, and it slides in sample 08.'),
    ('10_fit_insert_rear', 'Fit sample 10: rear end', 'The last 5 mm of the rear end with the end of the motor-side wall: press '
     'the two rear inserts in, then try a rear cap on it (0.8 mm toward the board side, slide back: the tooth drops into the '
     'notch).'),
    ('11_fit_insert_front', 'Fit sample 11: front end', 'The last 5 mm of the front end: press the three front inserts in (0.7 '
     'and 0.8 mm of wall); the bore and board-slot lead-ins and the key rib.'),
]


def by_label(rows, label):
    """The one dimension row with this label (the fit samples reuse the body's rows by name, not by position)."""
    m = [d for d in rows if d['label'] == label]
    assert len(m) == 1, f'{len(m)} rows labelled {label!r}'
    return m[0]


def printed_dims():
    """Feature dimensions of the printed parts, in the CAD frame (travel 0). Values from layout.py."""
    zb = 40.0                                                                  # a section in the carrier bore
    rh = L.REAR_HOOK
    body = [
        LEN('Length, rear face to front face', pl((9.0, 0, ZR), 'z'), pl((9.0, 0, ZF), 'z'), (1.6, 0, 0), key=True, grp='Outside',
            note='The end of the motor-side wall stands a further 1.6 mm out of the rear face (row {hook_row}).'),
        LEN('Width, motor side to board side', pl((X0, 0, zb), 'x'), pl((X1, 0, zb), 'x'), (0, 0, 6), key=True, grp='Outside'),
        LEN('Height', pl((0, -YH, zb), 'y'), pl((0, YH, zb), 'y'), (0, 0, 6), key=True, grp='Outside'),
        LEN('Bore, across', pl((-BX, 0, zb + 15), 'x'), pl((BX, 0, zb + 15), 'x'), (0, 0, 0), key=True, grp='Bore',
            note=f'The carrier is 10.0 × 12.0: 0.15 mm a side. A {L.CARRIER_KEY:g} mm key rib in one corner admits it one '
                 'way round only.'),
        LEN('Bore, high', pl((0, -BY, zb + 15), 'y'), pl((0, BY, zb + 15), 'y'), (0, 0, 0), grp='Bore'),
        LEN('Motor wall', pl((-3.0, 2.5, L.WALL_Z[0]), 'z'), pl((-3.0, 2.5, L.WALL_Z[1]), 'z'), (0, 2.5, 0), grp='Motor wall',
            note='The N20 gearbox face sits on its rear side; the carrier\'s travel starts 3 mm in front of it.'),
        DIA('Hole for the gearbox bushing and the M4 screw', (0, 0, 1.0), 'z', L.WALL_HOLE_D / 2, L.WALL_Z, grp='Motor wall',
            note='0.4 mm all round the Ø4 bushing.'),
        DIA('Motor screw holes, M1.6 (two, 9 mm apart)', (0, 4.5, 0.6), 'z', 0.9, (0.0, 1.25), grp='Motor wall',
            note='Countersunk 45° on the bore side, for DIN 965 heads.'),
        LEN('Partition between the bore and the board', pl((BX, 0, zb), 'x'), pl((L.PARTITION_X[1], 0, zb), 'x'), (0, 0, 0),
            grp='Board slot', note='One continuous printed wall: check in the slicer that it prints solid.'),
        LEN('Board groove', pl((L.SLOT_X[0], 3.7, zb), 'x'), pl((L.SLOT_X[1], 3.7, zb), 'x'), (0, 0, 0), grp='Board slot',
            note='For the 0.8 mm board: 0.05 mm a side. In the middle it opens into the cavity for the board\'s parts.'),
        DIA('Insert holes, rear face (two)', (L.REAR_INSERTS[0][0], L.REAR_INSERTS[0][1], ZR + 1.5), 'z', I['hole'] / 2,
            (ZR, ZR + I['hole_depth']), grp='Insert holes', note='M1 × 1.8 × 2 heat-set inserts, 1.05 mm of PETG round the knurl.'),
        DIA('Insert holes, front face, board side (two)', (L.FRONT_INSERTS[0][0], L.FRONT_INSERTS[0][1], ZF - 1.5), 'z',
            I['hole'] / 2, (ZF - I['hole_depth'], ZF), grp='Insert holes',
            note='0.70 mm of PETG round the knurl: press them in slowly.'),
        DIA('Insert hole, front face, motor side', (L.FRONT_INSERTS[2][0], L.FRONT_INSERTS[2][1], ZF - 1.5), 'z',
            I['hole'] / 2, (ZF - I['hole_depth'], ZF), grp='Insert holes',
            note='In the corner thickened by the key rib: 0.78 mm of PETG round the knurl.'),
        LEN('End of the motor-side wall (hooks the rear cap)', pl((9.0, 0, ZR), 'z'), pl((-6.6, 0, ZE), 'z'), (0, 0, 0), key=True,
            grp='Rear-cap hook', note=f'Its notch is {rh["notch"]} mm deep at 45°; 1.8 mm of wall is left there.'),
    ]
    hook = by_label(body, 'End of the motor-side wall (hooks the rear cap)')
    body[0]['note'] = body[0]['note'].format(hook_row=body.index(hook) + 1)   # rows are numbered from 1 in list order
    g = L.ROD_GUIDE_D / 2
    front = [
        LEN('Thickness', pl((-6.5, 0, ZF), 'z'), pl((-6.5, 0, ZC), 'z'), (0, -9, 0), key=True, grp='Plate'),
        DIA('Rod guide', (0, 0, ZF + 2.5), 'z', g, (ZF - L.SPIGOT, ZC - 0.5), key=True, grp='Plate',
            note='0.15 mm a side on the Ø8 rod.'),
        DIA('Screw holes, M1 clearance (three)', (L.FRONT_INSERTS[0][0], L.FRONT_INSERTS[0][1], ZF + 2.5), 'z', S['clear'] / 2,
            (ZF, ZC - S['pocket_depth']), grp='Plate', note='Two on the board side, one in the corner on the motor side.'),
        DIA('Head pockets (three)', (L.FRONT_INSERTS[0][0], L.FRONT_INSERTS[0][1], ZC - 0.5), 'z', S['pocket_d'] / 2,
            (ZC - S['pocket_depth'], ZC), grp='Plate', note='The M1 heads sit 0.3 mm below the face.'),
        LEN('Spigot, into the bore', pl((-6.5, 0, ZF), 'z'), pl((-4.5, 0, ZF - L.SPIGOT), 'z'), (0, 0, 0), grp='Spigot',
            note='The carrier stops on it at the end of its overtravel.'),
        LEN('Spigot, across', pl((-L.CARRIER_X + 0.05, 0, ZF - 0.5), 'x'), pl((L.CARRIER_X - 0.05, 0, ZF - 0.5), 'x'), (0, 0, 0),
            grp='Spigot', note='0.2 mm a side in the bore.'),
        LEN('Tongue, into the board groove', pl((9.3, 0, ZF), 'z'), pl((8.1, 0, ZF - (ZF - D['pcb_z'][1] - 0.1)), 'z'), (0, 0, 0),
            grp='Tongue', note='Holds the board\'s front edge, 0.1 mm of play.'),
    ]
    ez = D['rear_eye_z']
    rear = [
        LEN('Plate thickness', pl((-6.5, 6.5, ZR), 'z'), pl((-6.5, 6.5, ZR - L.REAR_CAP_T), 'z'), (0, 0, 0), grp='Plate'),
        LEN('Pin eye: centre to the cap\'s front face', pl((-6.5, 6.5, ZR), 'z'), cedge(ci((0, 0, ez), 'y', L.PIN_HOLE / 2, (-2.6, 2.6)),
            (0, 0, 0)), (0, 0, 0), key=True, grp='Clevis'),
        DIA('Pin hole', (0, 0, ez), 'y', L.PIN_HOLE / 2, (-2.6, 2.6), key=True, grp='Clevis', note='For the Ø3 pin or shaft.'),
        LEN('Eye thickness', pl((-3.5, -L.EYE_T / 2, -35.0), 'y'), pl((-3.5, L.EYE_T / 2, -35.0), 'y'), (0, 0, 0), grp='Clevis'),
        DIA('Screw holes, M1 clearance (two)', (L.REAR_INSERTS[0][0], L.REAR_INSERTS[0][1], ZR - 1.5), 'z', S['clear'] / 2,
            (CLAMP_Z, ZR), grp='Screws', note='Through the cable clamp, which sits in the 1 mm pocket on this side.'),
    ]
    rod = [
        LEN('Length, carrier to rod end', pl((-3.5, 3.5, C0), 'z'), pl((0, 2.5, RE), 'z'), (0, 7, 0), key=True, grp='Outside'),
        DIA('Rod', (0, 0, 50.0), 'z', L.ROD_D / 2, (C1, RE - 0.5), key=True, grp='Outside'),
        LEN('Carrier, across', pl((-L.CARRIER_X, 3.0, C0 + 5.5), 'x'), pl((L.CARRIER_X, 3.0, C0 + 5.5), 'x'), (0, 0, 0), grp='Carrier'),
        LEN('Carrier, high', pl((0, -L.CARRIER_Y, C0 + 5.5), 'y'), pl((0, L.CARRIER_Y, C0 + 5.5), 'y'), (0, 0, 0), grp='Carrier'),
        LEN('Carrier, long', pl((-3.5, 3.5, C0), 'z'), pl((-4.5, 4.5, C1), 'z'), (0, 0, 0), grp='Carrier'),
        LEN('Nut slot, across the flats', pl((0, -(L.NUT_AF + 0.15) / 2, C0 + 3.0), 'y'), pl((0, (L.NUT_AF + 0.15) / 2, C0 + 3.0), 'y'),
            (0, 0, 0), grp='Nut and magnet', note='For the 7 mm thin brass M4 nut, which slides in from the motor side.'),
        LEN('Nut slot, thick', pl((-3.0, 0, C0 + L.NUT_SLOT_DZ[0]), 'z'), pl((-3.0, 0, C0 + L.NUT_SLOT_DZ[1]), 'z'), (0, 0, 0),
            grp='Nut and magnet', note='The nut is 2.2 mm: 0.1 mm of play.'),
        LEN('Magnet pocket, wide', pl((4.0, -1.5, C0 + 6.0), 'y'), pl((4.0, 1.5, C0 + 6.0), 'y'), (0, 0, 0), grp='Nut and magnet',
            note='The 3 × 2 × 2 mm magnet presses in from the board side, poles along the travel.'),
        DIA('Bore, clears the M4 leadscrew', (0, 0, 40.0), 'z', L.ROD_BORE / 2, (C0, D['rod_bore_end_z']), grp='Outside',
            note='0.4 mm all round the screw; it stops 10 mm short of the rod end.'),
        DIA('Cross hole: the M2 screw cuts its thread here', (0, 0, RE - 4.5), 'x', 0.85, (-L.ROD_D / 2, L.ROD_D / 2),
            grp='Outside', note='Straight through the solid rod: about 7.9 mm of thread for the M2 × 10.'),
    ]
    zc = RE - 4.5
    eye = [
        DIA('Socket for the rod', (0, 0, RE - 4.5), 'z', L.ROD_D / 2 + 0.05, (RE - 9.0, RE), key=True, grp='Socket',
            note='0.05 mm a side on the Ø8 rod.'),
        DIA('Outside', (0, 0, RE - 4.0), 'z', 5.5, (RE - 8.5, RE + 1.5), grp='Socket'),
        DIA('Pin hole', (0, 0, D['eye_front_z']), 'y', L.PIN_HOLE / 2, (-2.6, 2.6), key=True, grp='Clevis'),
        DIA('M2 clearance hole, head side', (4.3, 0, zc), 'x', 1.1, (3.96, 4.6), grp='Cross screw'),
        DIA('M2 clearance hole, far side', (-4.8, 0, zc), 'x', 1.1, (-5.5, -3.96), grp='Cross screw',
            note='The screw threads into the rod, not into this 1.45 mm wall.'),
    ]
    yc = 6.5
    clamp = [
        LEN('Thickness', pl((8.5, yc, CLAMP_Z - L.CLAMP_T), 'z'), pl((8.5, yc, CLAMP_Z), 'z'), (0, 0, 0), grp='Plate'),
        LEN('Width', pl((L.CLAMP_X0, 5.0, CLAMP_Z - 1.5), 'x'), pl((X1, 5.0, CLAMP_Z - 1.5), 'x'), (0, 0, 0), grp='Plate'),
        DIA('Screw holes (two)', (L.REAR_INSERTS[0][0], L.REAR_INSERTS[0][1], CLAMP_Z - 1.0), 'z', S['clear'] / 2,
            (CLAMP_Z - L.CLAMP_T + S['pocket_depth'], CLAMP_Z), grp='Plate'),
        DIA('Head pockets (two)', (L.REAR_INSERTS[0][0], L.REAR_INSERTS[0][1], CLAMP_Z - 2.5), 'z', S['pocket_d'] / 2,
            (CLAMP_Z - L.CLAMP_T, CLAMP_Z - L.CLAMP_T + S['pocket_depth']), grp='Plate'),
    ]
    fit08 = [
        LEN('Bore, across', pl((-BX, 0, 5.0), 'x'), pl((BX, 0, 5.0), 'x'), (0, 0, 0), key=True, grp='Bore',
            note='Sample 09 must slide through it one way round only.'),
        LEN('Bore, high', pl((0, -BY, 5.0), 'y'), pl((0, BY, 5.0), 'y'), (0, 0, 0), grp='Bore'),
        LEN('Motor bay, across', pl((-BX, 4.5, -5.0), 'x'), pl((BX, 4.5, -5.0), 'x'), (0, 0, 0), key=True, grp='Motor bay',
            note='The N20 gearbox (10 × 12) slides in without force.'),
        by_label(body, 'Motor wall'), by_label(body, 'Hole for the gearbox bushing and the M4 screw'),
        by_label(body, 'Motor screw holes, M1.6 (two, 9 mm apart)'),
    ]
    fit09 = [rod[2], rod[3], rod[5], rod[7]]
    fit10 = [by_label(body, 'Insert holes, rear face (two)'), hook]
    fit11 = [by_label(body, 'Insert holes, front face, board side (two)'), by_label(body, 'Insert hole, front face, motor side')]
    return {'01_body': body, '02_front_cap': front, '03_rear_cap': rear, '04_rod': rod, '05_rod_eye': eye,
            '06_cable_clamp': clamp, '08_fit_body_wall': fit08, '09_fit_carrier': fit09, '10_fit_insert_rear': fit10,
            '11_fit_insert_front': fit11}


# the fit samples are CAD cuts of the body and the rod (build_v6.fit_samples): the box each one keeps, in the CAD frame
FIT_CUT = {'08_fit_body_wall': ('01_body', (-10.0, 8.0)), '09_fit_carrier': ('04_rod', (C0, C0 + L.CARRIER_LEN + 1.5)),
           '10_fit_insert_rear': ('01_body', (ZR - 2.0, ZR + 5.0)), '11_fit_insert_front': ('01_body', (ZF - 5.0, ZF))}

BOUGHT = [   # id, name, per actuator, scene meshes (prefixes), material, specification
    ('motor', 'N20 gearmotor, 12 V 1:50, M4 leadscrew', 1, ('motor_',), ('Bought assembly',
     'Brushed 12 V N20 motor on a metal spur gearbox; steel M4 × 0.7 leadscrew straight from the gearbox.'),
     '12 V, 1:50, 800 rpm without load (0.08 A). The leadscrew is sold 100 mm long: cut it to 75 mm for V6-U60, measured from '
     'the gearbox face to the tip, and deburr the cut end. Otherwise used as bought. No seller drawing of this version was '
     'found: check the gearbox face (Ø4 bushing, M1.6 holes 9 mm apart) before printing.'),
    ('nut', 'Hex nut M4, thin, brass', 1, ('M4_brass_nut',), ('Brass', 'ISO 4035 thin nut.'),
     'ISO 4035, 7 mm across the flats × 2.2 mm. Slides into the carrier\'s hex slot.'),
    ('magnet', 'Magnet, N35 block 3 × 2 × 2 mm', 1, ('magnet_3x2x2_axial',), ('NdFeB, N35', 'Sintered neodymium magnet, '
     'nickel plated as usual.'), 'Magnetised through the 2 mm length, so its poles are two 3 × 2 mm faces. It presses into the '
     'carrier pocket with the poles along the travel; either pole may face forward.'),
    ('M1.6x4', 'Countersunk screw M1.6 × 4', 2, ('M1.6x4_countersunk_',), ('Steel or stainless', 'DIN 965, cross recess PH0.'),
     'Motor to the body\'s wall, driven through the bore with a long PH0 blade.'),
    ('insert', 'Heat-set insert M1, brass', 5, ('M1_insert_',), ('Brass', 'Heat-set (thermal) insert, pressed in with the '
     'soldering iron at about 240 °C.'), 'M1 × 0.25 thread, 1.8 mm long, 2.0 mm across the knurl (sold as M1 × 1.8 × 2). Two in '
     'the body\'s rear face, three in its front face.'),
    ('M1x8', 'Pan-head screw M1 × 8', 5, ('M1x8_',), ('Stainless, A2-70', 'Cross recess PH000.'),
     'Three through the front cap, two through the cable clamp and the rear cap, into the inserts. Each runs through its whole '
     'insert. Very little torque.'),
    ('M2x10', 'Pan-head screw M2 × 10', 1, ('M2x10_rod_eye',), ('Steel or stainless', 'Any ISO 7045 pan head.'),
     'Rod-eye cross screw: through clearance holes in both eye walls; it cuts its own thread in the 1.7 mm hole '
     'through the rod.'),
    ('pcba', 'End-stop board V6-U60 (assembled)', 1, ('PCB_',), ('FR4 board, assembled', 'Two layers, 0.8 mm, all 17 parts on '
     'the top side (rev 6.2).'), '76.4 × 8 mm. Gerbers, BOM and placement files for JLCPCB in electronics/pcb/V6-U60/. At 8 mm wide '
     'it must be ordered panelized with break-off rails. Order a spare or two.'),
    ('wires', 'Wire, 28 AWG PTFE, 0.8 mm', 4, ('W1', 'W2', 'W3', 'W4'), ('PTFE-insulated copper', '28 AWG, 0.8 mm outside.'),
     'W1 red (A), W2 black (B), W3 orange (motor +), W4 purple (motor −).'),
    ('sleeve', 'Sleeve, 3 mm outside × 2 mm bore', 1, ('cable_sleeve',), ('Silicone or PVC tube', 'The clamp grips 3.0 ± 0.3 mm.'),
     'Over W1 and W2 from the cable clamp to your driver.'),
]
BENCH = [
    ('pins', 'Clevis pins Ø3', 'Two per actuator, only to try one on the bench: in the R12 arm its own steel shafts go through '
     'the eyes, which are 6 mm thick.'),
    ('supply', '12 V supply with a reversing switch', 'A DPDT switch or any H-bridge motor driver; a current limit of about '
     '0.5 A helps on the first run (ASSEMBLY.md step 10).'),
]
TOOLS = [   # id, name, scene meshes, use
    ('iron', 'Soldering iron, fine conical tip', ('tool_IRON_',), 'The wires on the board and the motor, and the M1 inserts '
     '(about 240 °C).'),
    ('PH0', 'PH0 screwdriver, long thin blade', ('tool_PH0_',), 'The two M1.6 motor screws, through the bore: blade 3 mm or less, '
     'at least 90 mm long for V6-U60 (for example a Wera 350 PH 0 × 100 mm, 05008706001).'),
    ('PH000', 'PH000 precision screwdriver', ('tool_PH000_',), 'The four M1 cap screws.'),
    ('PH1', 'PH1 screwdriver', ('tool_PH1_',), 'The M2 rod-eye screw.'),
    ('pliers', 'Small pliers', None, 'Knots, wires, holding the nut.'),
    ('saw', 'Fine hacksaw or cut-off disc', None, 'Cutting the leadscrew to 75 mm; clamp the screw, not the gearbox.'),
    ('file', 'Small file and an M4 nut', None, 'A chamfer on the cut end of the leadscrew, then run the nut over it and off to '
     'clean up the first thread.'),
]


def bought_dims():
    """Feature dimensions of the bought parts, in the CAD frame (the scene meshes)."""
    n0 = L.CARRIER_Z0 + L.NUT_SLOT_DZ[0] + 0.05
    m = L.MAGNET
    mz = L.CARRIER_Z0 + m['dz']
    xi, yi = L.FRONT_INSERTS[0]
    zi = ZF - I['recess']
    zh = ZC - S['pocket_depth'] + S['head_h']
    return {
        'motor': [
            LEN('Gearbox to leadscrew tip (cut length)', pl((-4.0, 4.0, 0.0), 'z'), pl((0.0, 0.0, D['screw_length_mm']), 'z'),
                (0, 9, 0), key=True, note='Cut the 100 mm screw to this, from the gearbox face.'),
            LEN('Gearbox, across', pl((-5.0, 0, -0.4), 'x'), pl((5.0, 0, -0.4), 'x'), (0, 0, 0), key=True,
                note='Its front plate: the bay in the body is 10.3 × 12.3.'),
            LEN('Gearbox, high', pl((0, -6.0, -0.4), 'y'), pl((0, 6.0, -0.4), 'y'), (0, 0, 0)),
            SPEC('Leadscrew', 'M4 × 0.7, single start'),
            SPEC('Speed', '800 rpm without load at 12 V: 9.3 mm/s'),
        ],
        'nut': [
            LEN('Across the flats', pl((0, -L.NUT_AF / 2, n0 + 1.1), 'y'), pl((0, L.NUT_AF / 2, n0 + 1.1), 'y'), (0, 0, 0), key=True),
            LEN('Thick', pl((0, 3.0, n0), 'z'), pl((0, 3.0, n0 + L.NUT_T), 'z'), (0, 0, 0), key=True),
            SPEC('Thread', 'M4 × 0.7'),
        ],
        'magnet': [
            LEN('Wide (Y)', pl((m['x'], -m['wy'] / 2 + 0.01, mz), 'y'), pl((m['x'], m['wy'] / 2 - 0.01, mz), 'y'), (0, 0, 0),
                key=True, note='Modelled 0.02 mm under size: the pocket is a press fit.'),
            LEN('Long (along the travel, the pole axis)', pl((m['x'], 0, mz - m['l'] / 2), 'z'), pl((m['x'], 0, mz + m['l'] / 2), 'z'),
                (0, 0, 0), key=True),
            SPEC('Grade', 'N35, magnetised through the 2 mm length'),
        ],
        'M1.6x4': [
            DIA('Thread', (0, 4.5, 0.0), 'z', 0.8, (L.WALL_Z[1] - 4.0, L.WALL_Z[1] - 0.7), key=True),
            LEN('Length, head included', pl((0, 4.5, L.WALL_Z[1] - 4.0), 'z'), pl((0.6, 4.5, L.WALL_Z[1]), 'z'), (0, 2.5, 0), key=True),
        ],
        'insert': [
            DIA('Knurl', (xi, yi, zi - 0.4), 'z', I['od'] / 2, (zi - 0.75, zi - 0.12), key=True),
            LEN('Length', pl((xi + 0.6, yi, zi - I['length']), 'z'), pl((xi + 0.6, yi, zi), 'z'), (0, 2.5, 0), key=True),
            DIA('Bore (drawn plain; the thread is M1 × 0.25)', (xi, yi, zi - 0.9), 'z', I['bore'] / 2, (zi - 1.8, zi)),
        ],
        'M1x8': [
            DIA('Head', (xi, yi, zh - 0.35), 'z', S['head_d'] / 2, (zh - S['head_h'], zh), key=True),
            DIA('Thread', (xi, yi, zh - 3.0), 'z', S['d'] / 2, (zh - S['head_h'] - S['length'], zh - S['head_h']), key=True),
            LEN('Length under the head', pl((xi + 0.8, yi, zh - S['head_h']), 'z'), pl((xi, yi, zh - S['head_h'] - S['length']), 'z'),
                (0, 2.5, 0)),
        ],
        'M2x10': [
            DIA('Thread', (0, 0, RE - 4.5), 'x', 1.0, (-5.4, 4.6), key=True),
            DIA('Head', (5.4, 0, RE - 4.5), 'x', 1.9, (4.6, 6.2)),
        ],
        'pcba': [
            LEN('Length', pl((8.1, 0, L.PCB_Z0), 'z'), pl((8.1, 0, D['pcb_z'][1]), 'z'), (0, 0, 0), key=True),
            LEN('Wide', pl((8.1, -L.PCB_W / 2, 40.0), 'y'), pl((8.1, L.PCB_W / 2, 40.0), 'y'), (0, 0, 0), key=True),
            SPEC('Hall switches', 'U1 at the wire end (retract), U2 at the front end (extend)'),
        ],
        'sleeve': [
            DIA('Outside', (9.0, 0, CLAMP_Z), 'x', L.SLEEVE_OD / 2, (6.25, 11.5), key=True),
            DIA('Bore', (9.0, 0, CLAMP_Z), 'x', L.SLEEVE_ID / 2, (6.25, 11.5)),
        ],
    }


# --------------------------------------------------------------------------------------------- inputs
def slicer_note(est, e):
    """PrusaSlicer's report for one plate (slicer_estimate.json, through build_print_plates), as the page shows it."""
    text = (f"{e['filament_g']:.1f} g of PETG ({e['filament_m']:.1f} m of 1.75 mm filament, skirt and brims included), about "
            f"{PP.hours(e['time_normal_s'])}, in {est['slicer']} with a generic 0.4 mm nozzle at its default speeds; your "
            "printer's profile gives its own time.")
    for part, issues in PP.alerts(e):
        short, why = PP.SUPPORT_ALERT[part]
        text += f' Its support alert names {short} ({issues.lower()}): {why}'
    return dict(text=text, filament_g=e['filament_g'], time_s=e['time_normal_s'])


def released():
    """SHA-256 of every released file, from ../SHA256SUMS.txt (paths relative to actuator_v6)."""
    out = {}
    for line in (ROOT / 'SHA256SUMS.txt').read_text().splitlines():
        if line.strip():
            h, p = line.split(None, 1)
            out[p.strip().lstrip('*')] = h
    return out


def fit_cut(stl, parent_lo, parent_hi, zr, deg):
    """CAD frame -> STL frame for a fit sample, a CAD cut of a part between z = zr[0] and zr[1]: the same rotation about X and
    centring as the parts. Checked: the STL's size is the cut's size."""
    R = rot_x(deg)
    lo = [parent_lo[0], parent_lo[1], max(parent_lo[2], zr[0])]
    hi = [parent_hi[0], parent_hi[1], min(parent_hi[2], zr[1])]
    corners = [mv(R, [lo[0] if i & 1 else hi[0], lo[1] if i & 2 else hi[1], lo[2] if i & 4 else hi[2]]) for i in range(8)]
    a = [min(c[i] for c in corners) for i in range(3)]
    b = [max(c[i] for c in corners) for i in range(3)]
    t = [(stl['lo'][0] + stl['hi'][0]) / 2 - (a[0] + b[0]) / 2, (stl['lo'][1] + stl['hi'][1]) / 2 - (a[1] + b[1]) / 2, stl['lo'][2] - a[2]]
    err = max(max(abs(a[i] + t[i] - stl['lo'][i]), abs(b[i] + t[i] - stl['hi'][i])) for i in range(3))
    assert err < 0.06, (stl['rel'], err)
    return R, t, dict(rot_x_deg=deg, cut_z=list(zr), bbox_error_mm=round(err, 4))


def stl_to_display(R, t, centre=None):
    """4x4: STL frame -> CAD frame (inverse of p' = R p + t) -> page frame; optionally moved so that `centre` (page frame) is at 0."""
    Rt = tp(R)
    M = mul4(m4(DISP), m4(Rt, [-x for x in mv(Rt, t)]))
    return mul4(m4(None, [-x for x in centre]), M) if centre else M


SHOW = {'insert': 'M1_insert_front_1', 'M1x8': 'M1x8_front_cap_1', 'M1.6x4': 'M1.6x4_countersunk_1'}


def main(check_only=False):
    scene = json.loads(gzip.decompress((HERE / f'scene_{VARIANT}.json.gz').read_bytes()))
    by = {p['name']: p for p in scene}
    val = json.loads((ROOT / 'validation.json').read_text())
    setups = val[VARIANT]['parts']
    fit_setups = val['S']['parts']
    rel_sums = released()
    plate_dir = ROOT / f'print_plates/V6-{VARIANT}_x{COUNT}'
    plates_meta = json.loads((plate_dir / 'plates.json').read_text())
    assert plates_meta['variant'] == f'V6-{VARIANT}' and plates_meta['actuators'] == COUNT and plates_meta['pass']
    # what PrusaSlicer reported (slice_plates.py), used only for the plates whose 3MF is the file it sliced
    est_file = plate_dir / 'slicer_estimate.json'
    est = json.loads(est_file.read_text()) if est_file.exists() else None
    wires = list(csv.DictReader((ROOT / f'wire_lengths_{VARIANT}.csv').open()))
    report = dict(generator='actuator_v6/source/build_parts_showcase.py', variant=f'V6-{VARIANT}', actuators=COUNT,
                  inputs_sha256={str(p.relative_to(REPO)): sha(p) for p in [HERE / f'scene_{VARIANT}.json.gz', ROOT / 'validation.json',
                                 plate_dir / 'plates.json', HERE / 'parts_showcase.html', Path(__file__)] + ([est_file] if est else [])})
    lib = Library()
    checks, items = [], []
    PD, BD = printed_dims(), bought_dims()

    # ---------------------------------------------------------------- printed parts: the released STL files, placed against the CAD
    stl, fits = {}, {}
    for k, *_ in PRINTED + FIT:
        rel = f'stl/V6-{VARIANT}/{k}.stl' if not k.startswith(('08', '09', '10', '11')) else f'stl/fit_samples/{k}.stl'
        m = load_stl(f'actuator_v6/{rel}')
        assert rel_sums.get(rel) == m['sha256'], f'{rel} is not the released file (SHA256SUMS.txt)'
        m['file'] = rel
        stl[k] = m
        m['geo'] = lib.add('stl:' + k, m['V'], m['T'], 'printed')
    for k, *_ in PRINTED:
        fits[k] = fit_print(stl[k], dict(by[k], name=k), 180 if k.startswith(FLIP) else 0)
    for k, (parent, zr) in FIT_CUT.items():
        S0 = mesh_stats(by[parent]['vertices'], by[parent]['triangles'])
        fits[k] = fit_cut(stl[k], S0['lo'], S0['hi'], zr, 180 if k.startswith(FLIP) else 0)
    report['print_files_against_cad'] = {k: f[2] for k, f in fits.items()}

    plate_of = {}
    for p in plates_meta['plates']:
        for o in p['objects']:
            plate_of.setdefault(o['name'], []).append((p['n'], o['copies'], o['settings']))

    def printed_item(k, name, per, note, fit=False):
        R, t, _ = fits[k]
        m = stl[k]
        dims, ch = resolve(PD[k], Frame(R, t), m, k)
        checks.extend(ch)
        size = [round(b - a, 2) for a, b in zip(m['lo'], m['hi'])]
        vol = mesh_stats(m['V'], m['T'])['volume']
        # the fitted pose: STL -> CAD -> page frame, centred on the part
        corners = [[m['lo'][0] if i & 1 else m['hi'][0], m['lo'][1] if i & 2 else m['hi'][1], m['lo'][2] if i & 4 else m['hi'][2]]
                   for i in range(8)]
        M0 = stl_to_display(R, t)
        pts = [mv([row[:3] for row in M0[:3]], c) for c in corners]
        pts = [[p[i] + M0[i][3] for i in range(3)] for p in pts]
        cc = [(min(p[i] for p in pts) + max(p[i] for p in pts)) / 2 for i in range(3)]
        src = fit_setups if fit else setups
        setup = src[k]['print_setup']
        assert abs(src[k]['volume_mm3'] - vol) / vol < 0.003, (k, src[k]['volume_mm3'], vol)
        orient = re.match(r'(?:PETG, |As \w+, )?([^,.]+?(?: \([^)]*\))?)[,.]', setup).group(1)
        qty = dict(total=1, text='1, print it once before the parts') if fit else dict(total=per * COUNT, text=f'{per * COUNT} ({per} per actuator)')
        plates = [dict(n=n, copies=c, settings=s) for n, c, s in plate_of.get(k, [])]
        assert sum(p['copies'] for p in plates) == (1 if fit else per * COUNT) + (1 if k == '03_rear_cap' else 0), (k, plates)
        color = by[FIT_CUT[k][0] if fit else k]['color']
        files = [dict(label='STL, oriented for printing', path=f'actuator_v6/{m["file"]}',
                      sha256=m['sha256'])]
        step = f'step/{"fit_samples" if fit else "V6-" + VARIANT}/{k}.step'
        assert (ROOT / step).exists(), step
        files.append(dict(label='STEP', path=f'actuator_v6/{step}', sha256=sha(ROOT / step)))
        return dict(id=k, type='fit' if fit else 'print', cat='Print once first: fit samples' if fit else 'Print: four of each',
                    name=name, qty=qty, per=None if fit else per, note=note, settings=setup, orientation=orient[0].upper() + orient[1:],
                    plates=plates, material=dict(name='PETG', notes=['PETG, unfilled. Masses use 1.27 g/cm³.']), files=files,
                    size=size, volume_cm3=round(vol / 1000, 3), triangles=len(m['T']), mass=dict(solid_g=round(vol / 1000 * PETG, 2)),
                    dims=dims, model=dict(parts=[dict(g=m['geo'], c=[round(x, 3) for x in color], m=col(m4()))],
                                          fit=col(stl_to_display(R, t, cc)), bed=True),
                    context=not fit)

    for k, name, per, note in PRINTED:
        items.append(printed_item(k, name, per, note))
    for k, name, note in FIT:
        items.append(printed_item(k, name, 1, note, fit=True))

    # ---------------------------------------------------------------- bought parts and tools: CAD meshes from the scene
    def names(prefixes):
        return [p['name'] for p in scene if p['kind'] in ('hardware', 'board', 'wire', 'tool') and p['name'].startswith(prefixes)]

    geo_of = {}

    def cad_geo(n):
        if n not in geo_of:
            c, rel, sig = centred(by[n])
            geo_of[n] = (c, lib.add('cad:' + sig, rel, by[n]['triangles'], 'bought'))
        return geo_of[n]

    def model_of(meshes, dims_rows, key):
        """Part view of bought meshes in the page frame, centred on the item; dimensions checked on the same meshes."""
        Ss = [mesh_stats(by[n]['vertices'], by[n]['triangles']) for n in meshes]
        lo = [min(s['lo'][i] for s in Ss) for i in range(3)]
        hi = [max(s['hi'][i] for s in Ss) for i in range(3)]
        c = [(a + b) / 2 for a, b in zip(lo, hi)]
        cd = mv(DISP, c)
        parts = []
        for n in meshes:
            mc, g = cad_geo(n)
            parts.append(dict(g=g, c=[round(x, 3) for x in by[n]['color']], m=col(mul4(m4(None, [-x for x in cd]), mul4(m4(DISP), m4(None, mc))))))
        dims = []
        if dims_rows:
            V, T, off = [], [], 0
            for n in meshes:
                V += [[x - cc for x, cc in zip(mv(DISP, v), cd)] for v in by[n]['vertices']]
                T += [[a + off, b + off, e + off] for a, b, e in by[n]['triangles']]
                off += len(by[n]['vertices'])
            dims, ch = resolve(dims_rows, Frame(DISP, [-x for x in cd]), dict(V=V, T=T), key)
            checks.extend(ch)
        size = mv(DISP, [b - a for a, b in zip(lo, hi)])
        return dict(parts=parts, size=[round(abs(x), 2) for x in size]), dims

    for k, name, per, prefixes, mat, spec in BOUGHT:
        meshes = names(prefixes)
        shown = [SHOW[k]] if k in SHOW else meshes
        model, dims = model_of(shown, BD.get(k), k)
        if k == 'wires':
            dims = [SPEC(f'{w["wire_id"]} {w["colour"]} ({w["net"]})', (w['cut_length_mm'] + ' mm').replace(' mm mm', ' mm')
                         .replace('your lead (knot 31 mm from the pad) mm', 'your lead; knot 31 mm from the pad'),
                         note=w['from'] + (', ' if w['to'].startswith('through') else ' to ') + w['to']) for w in wires]
            dims = [dict(d, n=i + 1, key=False) for i, d in enumerate(dims)]
        total = per * COUNT
        qty = dict(total=total, text=f'{total} ({per} per actuator)' if k != 'sleeve' else f'{COUNT} lengths, one per actuator: '
                   'the lead to your driver')
        if k == 'pcba':
            qty['text'] += '; order a spare or two'
        if k == 'wires':
            qty['text'] = f'{total} pieces: W1 to W4 for each actuator'
        items.append(dict(id=k, type='buy', cat='Buy: four actuators', name=name, qty=qty, per=per, spec=spec,
                          material=dict(name=mat[0], notes=[mat[1]]), dims=dims, model=model, context=True, scene=meshes))
    for k, name, use in BENCH:
        items.append(dict(id=k, type='bench', cat='Bench test (not for the arm)', name=name, qty=dict(total=None, text=''),
                          spec=use, material=dict(name='', notes=[]), dims=[], model=None, context=False))
    for k, name, prefixes, use in TOOLS:
        model = model_of(names(prefixes), None, k)[0] if prefixes else None
        items.append(dict(id=k, type='tool', cat='Tools', name=name, qty=dict(total=1, text='1'), spec=use,
                          material=dict(name='', notes=[]), dims=[], model=model, context=False))

    # ---------------------------------------------------------------- the print plates
    for p in plates_meta['plates']:
        f3, fs = p['files']['3mf'], p['files']['stl']
        m = load_stl(f'actuator_v6/{fs}')
        assert m['sha256'] == p['sha256']['stl'] and sha(ROOT / f3) == p['sha256']['3mf'], f'{fs}: not the file plates.json lists'
        # the plate is drawn from the part files at the plate's translations (much smaller than the plate file); checked: the
        # plate file holds exactly the placed parts' triangles, vertex order kept, each vertex moved and rounded to float32 as
        # build_print_plates.py writes it
        want = sorted(tuple(tuple(m['V'][i]) for i in tr) for tr in m['T'])
        got, parts = [], []
        for ins in p['instances']:
            k, t = ins['part'], ins['translate_mm']
            W = [F32.unpack(F32.pack(*(v[j] + t[j] for j in range(3)))) for v in stl[k]['V']]
            got += [tuple(W[i] for i in tr) for tr in stl[k]['T']]
            parts.append(dict(g=stl[k]['geo'], c=[round(x, 3) for x in by[FIT_CUT[k][0] if k in FIT_CUT else k]['color']],
                              m=col(m4(None, t))))
        assert sorted(got) == want, f'{fs}: not the placed parts'
        objs = [dict(name=o['name'], copies=o['copies'], settings=o['settings']) for o in p['objects']]
        e = next((x for x in (est or {}).get('plates', []) if x['n'] == p['n'] and x['sha256_3mf'] == p['sha256']['3mf']), None)
        items.append(dict(id=f'plate{p["n"]}', type='plate', cat='Print plates, 180 × 180 bed', name=f'Plate {p["n"]}: {p["title"]}',
                          qty=dict(total=None, text='print once' if p.get('once') else 'one plate'), note=p['purpose'],
                          objects=objs, size=[round(b - a, 1) for a, b in zip(m['lo'], m['hi'])], triangles=len(m['T']),
                          material=dict(name='PETG', notes=[]), dims=[],
                          files=[dict(label='3MF for PrusaSlicer (settings per object, copies as instances)', path=f'actuator_v6/{f3}',
                                      sha256=p['sha256']['3mf']),
                                 dict(label='STL, the whole plate in one file', path=f'actuator_v6/{fs}',
                                      sha256=p['sha256']['stl'])],
                          mass=dict(solid_g=p.get('mass_solid_g')), slicer=slicer_note(est, e) if e else None,
                          model=dict(parts=parts, bed=True, plate=list(plates_meta['bed_mm'])),
                          context=False))

    # ---------------------------------------------------------------- the actuator: whole, and cut open on the pin plane
    item_of = {}
    for i in items:
        for n in i.get('scene', []):
            item_of[n] = i['id']

    def inst(g, color, M, item, kind, name):
        return dict(g=g, c=[round(x, 3) for x in color], m=col(M), item=item, kind=kind, piece=name)

    ctx = dict(whole=[], cut=[])
    for p in scene:
        n = p['name']
        if p['kind'] == 'printed':
            R, t, _ = fits[n]
            ctx['whole'].append(inst(stl[n]['geo'], p['color'], stl_to_display(R, t), n, 'printed', n))
            h = by[f'{n}__half']
            c, g = cad_geo(h['name'])
            ctx['cut'].append(inst(g, h['color'], mul4(m4(DISP), m4(None, c)), n, 'printed', n))
        elif n in item_of:
            c, g = cad_geo(n)
            k = item_of[n]
            piece = k if k in ('motor', 'pcba') else n      # the motor and the board are many meshes but one part each
            for view in ctx.values():
                view.append(inst(g, p['color'], mul4(m4(DISP), m4(None, c)), k, 'bought', piece))
    pieces = {}
    for m in ctx['whole']:
        pieces.setdefault(m['item'], set()).add(m['piece'])
    counts = {k: len(v) for k, v in pieces.items()}
    for i in items:
        if i.get('context'):
            assert counts.get(i['id']) == i['per'], (i['id'], counts.get(i['id']), i['per'])
            i['in_actuator'] = counts[i['id']]
    assert counts['wires'] == 4 and not [n for n in by if by[n]['kind'] in ('hardware', 'board', 'wire') and n not in item_of]

    ids = [i['id'] for i in items]
    assert len(ids) == len(set(ids)), 'duplicate item'
    totals = dict(actuators=COUNT, printed=sum(i['qty']['total'] for i in items if i['type'] == 'print'),
                  fit=sum(1 for i in items if i['type'] == 'fit'), bought_kinds=sum(1 for i in items if i['type'] == 'buy'),
                  plates=len(plates_meta['plates']),
                  solid_petg_g=round(sum(i['mass']['solid_g'] * i['qty']['total'] for i in items if i['type'] in ('print', 'fit')), 0))
    sliced = [i['slicer'] for i in items if i['type'] == 'plate']
    if all(sliced):                     # every plate sliced as it stands: the filament and time for the whole set
        totals['sliced'] = dict(filament_g=round(sum(x['filament_g'] for x in sliced), 2), time_s=sum(x['time_s'] for x in sliced),
                                slicer=est['slicer'])
    if check_only:
        print(len(items), 'items;', len(checks), 'dimensions checked on the meshes;', len(lib.geos), 'meshes,',
              sum(g['nt'] for g in lib.geos), 'triangles (nothing written)')
        return
    data = dict(items=items, geos=lib.geos, ctx=ctx, totals=totals, variant=f'V6-{VARIANT}', revision='rev 6.2',
                plates=dict(bed=plates_meta['bed_mm'], folder=f'print_plates/V6-{VARIANT}_x{COUNT}'))
    vendor = HERE / 'vendor'
    template = (HERE / 'parts_showcase.html').read_text()
    html = template
    for k, v in {'__THREE__': (vendor / 'three.min.js').read_text(), '__ORBIT__': (vendor / 'OrbitControls.js').read_text(),
                 '__DATA__': json.dumps(data, separators=(',', ':'), ensure_ascii=False)}.items():
        assert html.count(k) == 1, k
        html = html.replace(k, v)
    (ROOT / 'parts_showcase.html').write_text(html)
    report.update(
        items=[dict(id=i['id'], type=i['type'], name=i['name'], qty=i['qty']['text'], model=bool(i.get('model')),
                    dimensions_drawn=sum(1 for d in i['dims'] if d['k'] != 'spec'), table_rows=len(i['dims']))
               for i in items],
        dimension_checks=checks, context=dict(whole=len(ctx['whole']), cut=len(ctx['cut']), per_actuator=counts),
        geometry=dict(meshes=len(lib.geos), triangles=sum(g['nt'] for g in lib.geos)), totals=totals,
        outputs_sha256={'parts_showcase.html': sha(ROOT / 'parts_showcase.html')}, **{'pass': True})
    (ROOT / 'parts_showcase_report.json').write_text(json.dumps(report, indent=1, ensure_ascii=False) + '\n')
    print('parts_showcase.html', round((ROOT / 'parts_showcase.html').stat().st_size / 1e6, 2), 'MB;', len(items), 'items;',
          len(checks), 'dimensions checked on the meshes;', len(lib.geos), 'meshes')


if __name__ == '__main__':
    main(check_only='--check-only' in sys.argv[1:])

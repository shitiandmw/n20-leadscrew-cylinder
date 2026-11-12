"""R12 CAD: every printed part, the pin hardware and four V6-U60 drives, built from r12_design.py.

Writes
  ../step/<part>.step            each printed part, in its body frame
  ../step/r12_arm_assembly.step  the whole arm at the reference pose
  ../stl/<part>.stl              printed parts in print orientation
  ../cad/scene.json.gz           meshes per body frame (viewer, 3D clash check)
  ../cad/cad_report.json         validity, watertightness, volumes, print bounds
  ../simulation/mass_properties.json   mass, centre of mass and inertia of every moving body

Frames: world X forward, Y lateral, Z up, boom-foot pin O at the origin. Each link frame is the
r12_design.py frame (x, z in the arm plane), rotated about Y. Units mm, kg.

Structural parts are modelled as solid envelopes with true bores; they print with 6 perimeters
(2.5 mm) and 10 % gyroid infill, which reproduces the 2.5 mm-wall box of the drawings with internal
bracing. Masses use exactly that: envelope minus 90 % of the inner core.
"""
import os
import sys
import json
import gzip
import math
import time
from pathlib import Path
import numpy as np
import cadquery as cq
import trimesh
from shapely.geometry import Polygon, Point, LineString, box
from shapely.ops import unary_union
import r12_design as d
from poses_r12 import DRIVES, REF_POSE, body_poses

ROOT = d.rc.ROOT
REPO = ROOT.parent
RHO_PETG, RHO_STEEL = 1.27e-6, 7.85e-6          # kg/mm^3
WALL, INFILL = d.T_WALL, d.PRINT_INFILL
ACT_INTERNAL_KG = 0.035                           # N20 motor, M4 screw, board, wires per drive (assumed, as R10)
ACT_ROD_INSERTS_KG = 0.0012                       # brass nut + magnet in the rod carrier
FIT = 0.1                                         # bore = pin + FIT (running fit; press fits noted in ASSEMBLY.md)
COLORS = dict(yellow=(0.95, 0.74, 0.22), yellow2=(0.88, 0.64, 0.16), dark=(0.20, 0.23, 0.26), steel=(0.66, 0.70, 0.74),
              link=(0.38, 0.41, 0.45), orange=(0.93, 0.53, 0.25), spacer=(0.80, 0.83, 0.86), tooth=(0.47, 0.50, 0.53))
PIN_FRAME = dict(O='base', A='base', B='boom', C='boom', E='boom', D='stick', F='stick', J='stick', H='stick',
                 R='side_link', Q='bucket')


# ------------------------------------------------------------------ primitives
def pin_xy(name):
    return dict(O=d.O, A=d.A_W, B=d.B_B, C=d.C_B, E=d.E_B, D=d.D_S, F=d.F_S, J=d.J_S, H=d.H_S,
                R=np.array([d.SIDE_LINK, 0.0]), Q=d.Q_K)[name]


def _poly(g, tol=0.02):
    g = g.simplify(tol)
    if g.geom_type != 'Polygon':
        g = max(g.geoms, key=lambda x: x.area)
    return g


def plate(poly, y0, y1):
    """Prism of a side outline (x, z) between y0 and y1."""
    g = _poly(poly)
    pts = [(float(x), float(z)) for x, z in list(g.exterior.coords)[:-1]]
    s = cq.Workplane('XZ').polyline(pts).close().extrude(float(y1 - y0)).translate((0, float(y1), 0))
    for ring in g.interiors:
        hp = [(float(x), float(z)) for x, z in list(ring.coords)[:-1]]
        s = s.cut(cq.Workplane('XZ').polyline(hp).close().extrude(float(y1 - y0) + 2).translate((0, float(y1) + 1, 0)))
    return s


def ycyl(p, r, y0, y1):
    return cq.Workplane('XZ').center(float(p[0]), float(p[1])).circle(r).extrude(float(y1 - y0)).translate((0, float(y1), 0))


def tube(p, ro, ri, y0, y1):
    return ycyl(p, ro, y0, y1).cut(ycyl(p, ri, y0 - 1, y1 + 1))


def bore(s, pts, r):
    for p in pts:
        s = s.cut(ycyl(p, r, -120, 120))
    return s


def band(lo, hi, sg):
    return (lo, hi) if sg > 0 else (-hi, -lo)


def both(shape_fn, lo, hi):
    """Union of a +Y and a -Y copy."""
    return shape_fn(lo, hi).union(shape_fn(-hi, -lo))


def solid(s):
    vals = s.solids().vals()
    assert len(vals) == 1, f'{len(vals)} solids'
    return vals[0]


# ------------------------------------------------------------------ printed parts
def foot_bracket():
    fp = d.foot_parts()
    s = plate(fp['flange'], -50, 50)
    s = s.union(both(lambda a, b: plate(fp['plate'], a, b), 20.5, 25.5))
    s = s.union(both(lambda a, b: plate(fp['outer'], a, b), 42.5, 47.5))
    s = bore(s, [d.O], 3.0 + FIT / 2)
    s = bore(s, [d.A_W], 1.5 + FIT / 2)
    for x in (-28.0, 0.0):
        for y in (-35.0, 35.0):
            s = s.cut(cq.Workplane('XY').center(x, y).circle(2.25).extrude(20).translate((0, 0, d.TURNTABLE_Z - 5)))
    return s, []


def boom():
    bp = d.boom_profile()
    nd = d.disc(d.E_B, d.BOOM_NOSE_R)
    main, nose = bp.difference(nd), bp.intersection(nd)
    s = plate(main, -20, 20).union(plate(nose, -10.5, 10.5))
    s = s.union(both(lambda a, b: plate(d.c_bracket(), a, b), 8.0, 13.0))
    s = bore(s, [d.O, d.E_B], 3.0 + FIT)
    s = bore(s, [d.B_B, d.C_B], 1.5 + FIT)
    core = [(main.buffer(-WALL).difference(unary_union([d.disc(d.O, 8.0), d.disc(d.B_B, 5.0)])), 20 - WALL),
            (nose.buffer(-WALL).difference(d.disc(d.E_B, 8.0)), 10.5 - WALL)]
    return s, core


def stick():
    sr = d.stick_regions()
    s = plate(sr['box'], -16, 16)
    s = s.union(both(lambda a, b: plate(sr['head'], a, b), 11.0, 16.0))
    s = s.union(plate(sr['bridge'], -11, 11))
    s = s.union(both(lambda a, b: plate(d.f_lug(), a, b), 8.0, 13.0))
    s = bore(s, [np.zeros(2), d.H_S], 3.0 + FIT)
    s = bore(s, [d.D_S, d.F_S, d.J_S], 1.5 + FIT)
    core = [(sr['box'].buffer(-WALL).difference(unary_union([d.disc(d.J_S, 5.0), d.disc(d.H_S, 8.0)])), 16 - WALL)]
    return s, core


def side_link(sg):
    s = plate(d.link_parts()['side'], *band(26.0, 30.0, sg))
    return bore(s, [np.zeros(2), np.array([d.SIDE_LINK, 0.0])], 1.5 + FIT), []


def h_link(sg):
    # Ø10 tube at R, stepped to a Ø7.2 boss next to the drive eye: the V6 rod-eye socket (Ø11) starts
    # 4.0 mm behind the eye centre and must clear it at every H-link angle
    s = plate(d.link_parts()['h'], *band(21.0, 25.0, sg)).union(ycyl(np.zeros(2), 5.0, *band(d.Y['h_link_tube'][0], 21.0, sg)))
    s = s.union(ycyl(np.zeros(2), d.ACT['boss_r'], *band(*d.Y['h_link_boss'], sg)))
    return bore(s, [np.zeros(2), np.array([d.H_LINK, 0.0])], 1.5 + FIT), []


def bucket():
    """Rev. D4, the Caterpillar US 8,201,350 bucket at 1:15:
      * wrapper plate (floor, heel, support plate) across the inside width
      * two side plates
      * a torque tube between the ears that carries the Q bore
      * hinge plates (ears) at H and Q
    The mouth is open from the cutting edge to the support-plate front end."""
    bk = d.bucket_parts()
    s = plate(bk['band'], -37.6, 37.6)
    s = s.union(both(lambda a, b: plate(bk['shell'], a, b), 37.6, 40.0))
    s = s.union(plate(bk['torque_tube'], -d.TORQUE_TUBE_HALF_W, d.TORQUE_TUBE_HALF_W))
    s = s.union(both(lambda a, b: plate(bk['ears'], a, b), 16.5, 20.5))
    s = bore(s, [np.zeros(2)], 3.0 + FIT)
    s = bore(s, [d.Q_K], 1.5 + FIT)
    return s, []


def b_pad(sg):
    """Boss pad between the boom side wall and a boom-drive rod eye (bonded, located by the B pin).
    Ø17 pad, then a Ø7.2 boss that bears on the eye lug and clears the Ø11 rod-eye socket."""
    s = ycyl(d.B_B, 8.5, *band(*d.Y['boom_b_pad'], sg)).union(ycyl(d.B_B, d.ACT['boss_r'], *band(*d.Y['boom_b_boss'], sg)))
    return bore(s, [d.B_B], 1.5 + FIT), []


def tooth(yc):
    return plate(d.tooth_outline(), yc - d.TOOTH_HALF_W, yc + d.TOOTH_HALF_W), []


PRINTED = [
    # name, body, builder, colour, print orientation ('side' = lying on a side face, 'flat' = as modelled)
    ('B01_boom_foot_bracket', 'base', foot_bracket, 'dark', 'flat'),
    ('B02_boom', 'boom', boom, 'yellow', 'side'),
    ('B03_stick', 'stick', stick, 'yellow', 'side'),
    ('B04_side_link_L', 'side_link', lambda: side_link(+1), 'link', 'side'),
    ('B04_side_link_R', 'side_link', lambda: side_link(-1), 'link', 'side'),
    ('B05_h_link_L', 'h_link', lambda: h_link(+1), 'link', 'side'),
    ('B05_h_link_R', 'h_link', lambda: h_link(-1), 'link', 'side'),
    ('B06_bucket', 'bucket', bucket, 'yellow', 'side'),
    ('B08_B_pad_L', 'boom', lambda: b_pad(+1), 'yellow2', 'side'),
    ('B08_B_pad_R', 'boom', lambda: b_pad(-1), 'yellow2', 'side'),
] + [(f'B07_tooth_{i + 1}', 'bucket', (lambda yc=yc: tooth(yc)), 'tooth', 'side') for i, yc in enumerate(d.TOOTH_Y)]


# ------------------------------------------------------------------ hardware (pins, collars, spacers, washers)
# per pin: diameter, pin extent |Y| (or (lo, hi) for one-sided A pins), printed spacers (|Y| ranges),
# thrust washers (|Y| ranges); collars come from d.PIN_ENDS
HW = dict(
    O=dict(dia=6, y=30.0, spacers=[], washers=[(20.05, 20.45)]),
    A=dict(dia=3, y=None, spacers=[(25.6, 30.9), (37.1, 42.4)], washers=[]),
    B=dict(dia=3, y=41.0, spacers=[], washers=[]),               # the B08 boss runs up to the eye lug
    C=dict(dia=3, y=17.0, spacers=[(3.1, 7.9)], washers=[]),
    E=dict(dia=6, y=21.0, spacers=[], washers=[(10.55, 10.95)]),
    D=dict(dia=3, y=20.0, spacers=[(3.1, 10.9)], washers=[]),
    F=dict(dia=3, y=17.0, spacers=[(3.1, 7.9)], washers=[]),
    J=dict(dia=3, y=34.0, spacers=[(16.1, 25.9)], washers=[]),
    R=dict(dia=3, y=34.0, spacers=[(25.1, 25.9)], washers=[]),
    Q=dict(dia=3, y=29.0, spacers=[], washers=[]),
    H=dict(dia=6, y=25.0, spacers=[], washers=[(16.05, 16.45)]),
)


def hardware():
    out = []
    for pin, h in HW.items():
        p, dia, body = pin_xy(pin), h['dia'], PIN_FRAME[pin]
        r = dia / 2
        if pin == 'A':
            for sg in (1, -1):
                out.append((f'pin_A_{"L" if sg > 0 else "R"}_d3x30', body, ycyl(p, r, *band(20.5, 50.5, sg)), 'steel', 'steel'))
        else:
            out.append((f'pin_{pin}_d{dia}x{2 * h["y"]:.0f}', body, ycyl(p, r, -h['y'], h['y']), 'steel', 'steel'))
        _, lo, hi = d.PIN_ENDS[pin]
        for sg in (1, -1):
            side = 'L' if sg > 0 else 'R'
            out.append((f'collar_{pin}_{side}', body, tube(p, d.COLLAR_R[dia], r + 0.02, *band(lo, hi, sg)), 'steel', 'steel'))
            for k, (a, b) in enumerate(h['spacers']):
                out.append((f'spacer_{pin}{k + 1}_{side}', body, tube(p, 3.5 if dia == 3 else 5.5, r + FIT, *band(a, b, sg)),
                            'spacer', 'petg'))
            for k, (a, b) in enumerate(h['washers']):
                out.append((f'washer_{pin}_{side}', body, tube(p, 5.5, r + 0.05, *band(a, b, sg)), 'steel', 'steel'))
    # Q: the D4 torque tube (printed with B06) spans the ears and carries the pin; no separate spacer
    return out


# ------------------------------------------------------------------ V6-U60 drives
def v6_parts():
    sys.path.insert(0, str(REPO / 'actuator_v6' / 'source'))
    import layout as L
    import design_v6 as D
    dd = L.derived('U60')
    assert abs(dd['pin_centres_closed'] - d.ACT['closed']) < 1e-6 and abs(dd['pin_centres_open'] - d.ACT['open']) < 1e-6
    parts = dict(body=D.make_body(dd), front_cap=D.make_front_cap(dd), rear_cap=D.make_rear_cap(dd),
                 cable_clamp=D.make_cable_clamp(dd), rod=D.make_rod(dd), rod_eye=D.make_rod_eye(dd))
    return {k: (v if isinstance(v, cq.Workplane) else cq.Workplane(obj=v)) for k, v in parts.items()}, -dd['rear_eye_z']


def to_drive_frame(s, rear_offset, board):
    """V6 frame (travel along +Z, board on +X) -> drive frame (x along rear->rod pin, rear eye at the
    origin, z = in-plane left normal). board = +1 puts the board housing on the left of rear->rod."""
    if board > 0:
        s = s.rotate((0, 0, 0), (0, 0, 1), 180)
    return s.rotate((0, 0, 0), (0, 1, 0), 90).translate((rear_offset, 0, 0))


def drives():
    parts, rear = v6_parts()
    out = []
    for name, a, b, yc, board, _ in DRIVES:
        for pn, s in parts.items():
            body = f'{name}_rod' if pn in ('rod', 'rod_eye') else f'{name}_barrel'
            col = 'orange' if pn == 'body' else 'steel' if pn == 'rod' else 'dark'
            out.append((f'{name}_V6_{pn}', body, to_drive_frame(s, rear, board).translate((0, yc, 0)), col, 'petg'))
    return out


def place(s, pose):
    (ox, oz), ang = pose
    return s.rotate((0, 0, 0), (0, 1, 0), -math.degrees(ang)).translate((float(ox), 0, float(oz)))


# ------------------------------------------------------------------ mass properties
def _mesh(shape, tol=0.05, ang=0.2):
    v, f = shape.tessellate(tol, ang)
    return np.array([[p.x, p.y, p.z] for p in v]), np.array(f, dtype=np.int64)


def _props(tm):
    """volume, centroid, inertia about the centroid (unit density)."""
    return float(tm.volume), np.asarray(tm.center_mass, float), np.asarray(tm.moment_inertia, float)


def _pa(r):
    return float(r @ r) * np.eye(3) - np.outer(r, r)


def combine(items):
    """items: (mass, com, inertia about com). Returns the same for the union."""
    m = sum(i[0] for i in items)
    c = sum(i[0] * i[1] for i in items) / m
    I = sum(i[2] + i[0] * _pa(i[1] - c) for i in items)
    return m, c, I


def shell_props(shape, core):
    """Printed envelope with 6 perimeters and 15 % infill: mass, com, inertia (kg, mm, kg mm^2)."""
    v, f = _mesh(shape)
    tm = trimesh.Trimesh(v, f, process=True)
    Ve, ce, Ie = _props(tm)
    items = [(RHO_PETG * Ve, ce, RHO_PETG * Ie)]
    for g, half in core:
        if g.is_empty or half <= 0:
            continue
        for pg in getattr(g, 'geoms', [g]):
            if pg.area < 1:
                continue
            cs = plate(pg, -half, half)
            cv, cf = _mesh(solid(cs), 0.1, 0.3)
            ctm = trimesh.Trimesh(cv, cf, process=True)
            Vc, cc, Ic = _props(ctm)
            k = -(1 - INFILL) * RHO_PETG
            items.append((k * Vc, cc, k * Ic))
    return combine(items), Ve


# ------------------------------------------------------------------ build
def build(export=True):
    t0 = time.time()
    for sub in ('step', 'stl', 'cad', 'simulation'):
        (ROOT / sub).mkdir(exist_ok=True)
    items, report, body_mass, solids = [], [], {}, {}

    def account(body, props):
        body_mass.setdefault(body, []).append(props)

    for name, body, fn, col, orient in PRINTED:
        s, core = fn()
        sol = solid(s)
        assert sol.isValid(), name
        solids[name] = sol
        (m, c, I), Ve = shell_props(sol, core)
        account(body, (m, c, I))
        vtx, tri = _mesh(sol)
        items.append(dict(name=name, body=body, color=COLORS[col], kind='printed', v=vtx, t=tri))
        rep = dict(name=name, body=body, valid=True, volume_mm3=round(Ve, 1), mass_g=round(m * 1000, 1))
        if export:
            cq.exporters.export(cq.Workplane(obj=sol), str(ROOT / 'step' / f'{name}.step'))
            sp = cq.Workplane(obj=sol)
            if orient == 'side':
                sp = sp.rotate((0, 0, 0), (1, 0, 0), 90)
            bb = sp.val().BoundingBox()
            sp = sp.translate((-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))
            dest = ROOT / 'stl' / f'{name}.stl'
            cq.exporters.export(sp, str(dest), tolerance=0.03, angularTolerance=0.12)
            tm = trimesh.load_mesh(dest)
            rt = cq.importers.importStep(str(ROOT / 'step' / f'{name}.step'))
            rep.update(watertight=bool(tm.is_watertight), winding_consistent=bool(tm.is_winding_consistent),
                       single_shell=len(tm.split(only_watertight=False)) == 1, step_roundtrip_valid=bool(rt.val().isValid()),
                       print_bounds_mm=[round(float(x), 1) for x in tm.extents])
            assert rep['watertight'] and rep['single_shell'] and rep['step_roundtrip_valid'], rep
        report.append(rep)
        print(f'{name:28s} {rep["mass_g"]:7.1f} g  {time.time() - t0:6.1f} s', flush=True)
    hw = hardware() + drives()
    for name, body, s, col, mat in hw:
        sol = solid(s)
        vtx, tri = _mesh(sol)
        tm = trimesh.Trimesh(vtx, tri, process=True)
        V, c, I = _props(tm)
        rho = RHO_STEEL if mat == 'steel' else RHO_PETG
        account(body, (rho * V, c, rho * I))
        items.append(dict(name=name, body=body, color=COLORS[col], kind='hardware' if mat == 'steel' or 'spacer' in name
                          else 'drive', v=vtx, t=tri))
    # drive internals: motor, screw and board in the barrel; nut and magnet in the rod carrier
    for name, a, b, yc, *_ in DRIVES:
        account(f'{name}_barrel', (ACT_INTERNAL_KG, np.array([30.0, yc, 0.0]), ACT_INTERNAL_KG * np.diag([60.0, 400.0, 400.0])))
        account(f'{name}_rod', (ACT_ROD_INSERTS_KG, np.array([d.ACT['closed'] - 92.0, yc, 0.0]), np.zeros((3, 3)) + 1e-6 * np.eye(3)))
    mass = {}
    for body, lst in body_mass.items():
        m, c, I = combine(lst)
        mass[body] = dict(mass_kg=round(m, 6), com_mm=[round(float(x), 4) for x in c],
                          inertia_kg_mm2=[[round(float(x), 6) for x in row] for row in I])
    (ROOT / 'simulation' / 'mass_properties.json').write_text(json.dumps(dict(
        bodies=mass, frames='body frames as in r12_design.py; drives: x along rear->rod pin, rear eye at origin',
        assumptions=dict(petg_kg_m3=1270, steel_kg_m3=7850, perimeters_mm=WALL, infill=INFILL,
                         drive_internal_kg=ACT_INTERNAL_KG, rod_inserts_kg=ACT_ROD_INSERTS_KG,
                         note='printed structural parts: envelope minus 90 % of the core inside 2.5 mm walls; '
                              'V6 printed parts solid; internals assumed, not weighed')), indent=1))
    scene = [dict(name=i['name'], body=i['body'], color=i['color'], kind=i['kind'],
                  v=np.round(i['v'], 3).ravel().tolist(), t=i['t'].ravel().tolist()) for i in items]
    (ROOT / 'cad' / 'scene.json.gz').write_bytes(gzip.compress(json.dumps(scene, separators=(',', ':')).encode()))
    if export:
        _, poses = body_poses(REF_POSE)
        assy = cq.Assembly(name='R12_excavator_arm')
        shapes = {n: s for n, _, s, _, _ in hw}
        for name, body, fn, col, _ in PRINTED:
            assy.add(place(cq.Workplane(obj=solids[name]), poses[body]), name=name, color=cq.Color(*COLORS[col]))
        for name, body, s, col, _ in hw:
            assy.add(place(shapes[name], poses[body]), name=name, color=cq.Color(*COLORS[col]))
        dest = ROOT / 'step' / 'r12_arm_assembly.step'
        assy.export(str(dest))
        rt = cq.importers.importStep(str(dest))
        n_solids = len(rt.solids().vals())
    else:
        n_solids = None
    (ROOT / 'cad' / 'cad_report.json').write_text(json.dumps(dict(
        printed_parts=report, hardware_and_drive_parts=len(hw), assembly_solids=n_solids, reference_pose_strokes=REF_POSE,
        masses_kg={k: v['mass_kg'] for k, v in mass.items()}, build_seconds=round(time.time() - t0, 1)), indent=1))
    print('done', round(time.time() - t0, 1), 's', flush=True)
    return items, mass


if __name__ == '__main__':
    build(export='--no-export' not in sys.argv)

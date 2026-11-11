"""B01X: the R12 boom-foot bracket, fitted to the X1 turntable (T101).

R12's B01 stands on a 6 mm flange with 4 x M4 holes, drawn for a bare turntable face. On X1 that face is
occupied by the T101 centre frame, whose rib tops (Z 136) carry the arm on 4 x M6 bolts (the ARM60 base
pattern). B01X keeps everything of B01 above the flange top unchanged (foot plates, outer cheeks, the O and A
bores) and replaces the flange with a 10 mm base plate:
  - footprint of the ARM60 base (X -21..111, |Y| <= 82), so the body halves fit round it as checked in BODY.md;
  - 4 x Ø6.6 holes on the T101 pattern, so the existing M6 x 40 bolts and T101 nut pockets are reused;
  - 10 mm thick, as the ARM60 base: the bolt length and the M6 thread past the nut stay as checked.
O therefore sits 59 mm above the rib tops (B01: 55 above its turntable face), at vehicle (30, 0, 195).

Issue 3 (wiring): the plate carries the arm harness (harness.py). T101 has full-width bulkheads under the plate at
vehicle X -38..-30 and 30..38, so cables can only leave its underside through the gap behind the plate's rear edge. Each
side therefore has one 8 x 7 slot at vehicle X 0..8 (|Y| 36..43): the stick / bucket cable comes down into it from a Ø6
post behind it (Ø2.6 tie hole through the post top), and the boom drive's sleeve reaches it along a 5 x 7 trough cut into
the plate top: a 9 wide mouth at the drive's own |Y| 34 from x 47 back to x 20, where the sleeve lands and slides, then
easing outboard to the slot at |Y| 39.5. Cable-tie slot pairs across each trough and behind each slot hold the sleeves.

Frame: the R12 'base' body frame (O at the origin, X forward, Z up), as R12's own part STEP files.
Writes ../step/B01X_boom_foot_bracket.step, ../stl/B01X_boom_foot_bracket.stl (print orientation, plate down),
../cad/B01X_mesh.json.gz (viewer and checks) and ../cad/B01X_report.json.
Run with the R12 interpreter (CadQuery 2.8, trimesh), from this folder.
"""
import sys
import json
import math
import time
import numpy as np
import cadquery as cq
import trimesh
from shapely.geometry import box as sbox
from shapely.ops import unary_union
import common as K
import harness as H

sys.path.insert(0, str(K.R12 / 'source'))
import r12_design as d          # noqa: E402
import cad_r12 as C             # noqa: E402

NAME = 'B01X_boom_foot_bracket'
FILLET = 3.0                    # vertical plate corners
Z0, Z1 = -(K.O_Z - K.T101_TOP_Z), -(K.O_Z - K.T101_TOP_Z) + K.BASE_T     # -59, -49 in the O frame
X0, X1 = K.BASE_X[0] - K.O_X, K.BASE_X[1] - K.O_X                         # -51, 81
BOLTS_O = [(x - K.O_X, y) for x, y in K.BOLTS]


def extend_down(poly, z_top, z_new):
    """Carry a side outline's flat bottom edge (at z_top) 1 mm down into the base plate so the union is one solid."""
    xs = [x for x, z in poly.exterior.coords if abs(z - z_top) < 1e-6]
    assert len(xs) >= 2, 'outline has no flat bottom edge at the flange top'
    return unary_union([poly, sbox(min(xs), z_new, max(xs), z_top)])


def bracket():
    fp = d.foot_parts()
    top = d.TURNTABLE_Z + 6.0                        # B01 flange top, O - 49
    assert abs(top - Z1) < 1e-9, (top, Z1)
    plate = cq.Workplane('XY').box(X1 - X0, 2 * K.BASE_Y, K.BASE_T, centered=False).translate((X0, -K.BASE_Y, Z0))
    plate = plate.edges('|Z').fillet(FILLET)
    s = plate
    s = s.union(C.both(lambda a, b: C.plate(extend_down(fp['plate'], top, top - 1.0), a, b), *d.Y['foot_plate']))
    s = s.union(C.both(lambda a, b: C.plate(extend_down(fp['outer'], top, top - 1.0), a, b), *d.Y['foot_outer_cheek']))
    s = C.bore(s, [d.O], 3.0 + C.FIT / 2)            # as cad_r12.foot_bracket
    s = C.bore(s, [d.A_W], 1.5 + C.FIT / 2)
    for x, y in BOLTS_O:
        s = s.cut(cq.Workplane('XY').center(x, y).circle(K.BOLT_HOLE_R).extrude(K.BASE_T + 2).translate((0, 0, Z0 - 1)))
    s = cable_features(s)
    return C.solid(s)


def cable_features(s):
    """Issue 3: the two troughs on the plate top (a 9 mm mouth where the sleeve lands and slides, then 5 wide along the
    polyline to the slot), the two merged slots, their tie slots and the two loop posts (harness.py)."""
    T = H.TROUGH
    zf = Z1 - T['depth']
    path = T['path']
    for sy in (1, -1):
        for (xa, ya), (xb, yb) in zip(path[:-1], path[1:]):
            L = math.hypot(xb - xa, yb - ya)
            ang = math.degrees(math.atan2(sy * (yb - ya), xb - xa))
            w = T['mouth_w'] if xa >= T['mouth_to_x'] - 1e-6 and xb >= T['mouth_to_x'] - 1e-6 else T['w']
            seg = cq.Workplane('XY').center((xa + xb) / 2, sy * (ya + yb) / 2).slot2D(L + (w - T['w']), w, ang).extrude(T['depth'] + 2).translate((0, 0, zf))
            s = s.cut(seg)
        for tx in H.TROUGH_TIES_X:       # a tie pair across the trough at its local centreline
            for (xa, ya), (xb, yb) in zip(path[:-1], path[1:]):
                if min(xa, xb) - 1e-6 <= tx <= max(xa, xb) + 1e-6:
                    yc = ya + (yb - ya) * (tx - xa) / (xb - xa)
                    break
            w = T['mouth_w'] if tx >= T['mouth_to_x'] else T['w']
            for ty in (yc - (w / 2 + 2.0), yc + (w / 2 + 2.0)):
                s = s.cut(cq.Workplane('XY').rect(H.TIE_SLOT[0], H.TIE_SLOT[1]).extrude(K.BASE_T + 2).translate((tx, sy * ty, Z0 - 1)))
    for name, (x, y, Lx, Ly) in H.SLOTS.items():
        slot = cq.Workplane('XY').rect(Lx, Ly).extrude(K.BASE_T + 2).edges('|Z').fillet(2.0).translate((x, y, Z0 - 1))
        s = s.cut(slot)
        for dx in (-3.0, 3.0):      # a tie pair behind the slot, where both cables run down together
            s = s.cut(cq.Workplane('XY').rect(H.TIE_SLOT[1], H.TIE_SLOT[0]).extrude(K.BASE_T + 2).translate((x - 5.5 + dx, y, Z0 - 1)))
    P = H.POST
    for sy in (1, -1):
        post = cq.Workplane('XY').center(P['x'], sy * P['y']).circle(P['r']).extrude(P['top'] - Z1 + .01).translate((0, 0, Z1 - .01))
        base = cq.Workplane(obj=cq.Solid.makeCone(P['r_base'], P['r'], P['r_base'] - P['r'], cq.Vector(P['x'], sy * P['y'], Z1 - .01), cq.Vector(0, 0, 1)))
        s = s.union(post).union(base)
        hole = cq.Workplane('YZ').center(sy * P['y'], P['tie_z']).circle(1.3).extrude(2 * P['r'] + 2).translate((P['x'] - P['r'] - 1, 0, 0))
        s = s.cut(hole)
    return s


def core():
    """Infill region of the base plate: 2.5 mm skins all round, solid round the bolts (as R12's print rule).
    The 5 mm foot plates and cheeks are all perimeter, i.e. solid."""
    w = C.WALL
    c = cq.Workplane('XY').box(X1 - X0 - 2 * w, 2 * (K.BASE_Y - w), K.BASE_T - 2 * w, centered=False).translate((X0 + w, -K.BASE_Y + w, Z0 + w))
    for x, y in BOLTS_O:
        c = c.cut(cq.Workplane('XY').center(x, y).circle(K.BOLT_HOLE_R + w).extrude(K.BASE_T).translate((0, 0, Z0)))
    return C.solid(c)


def props(shape, tol=0.05):
    v, f = C._mesh(shape, tol)
    tm = trimesh.Trimesh(v, f, process=True)
    return C._props(tm)


def main():
    t0 = time.time()
    for sub in ('step', 'stl', 'cad'):
        (K.ROOT / sub).mkdir(exist_ok=True)
    sol = bracket()
    assert sol.isValid()
    Ve, ce, Ie = props(sol)
    Vc, cc, Ic = props(core())
    k = (1 - C.INFILL) * C.RHO_PETG
    m, c, I = C.combine([(C.RHO_PETG * Ve, ce, C.RHO_PETG * Ie), (-k * Vc, cc, -k * Ic)])
    # B01 for comparison (as built by cad_r12: solid)
    b01, _ = C.foot_bracket()
    Vb, _, _ = props(C.solid(b01))

    step = K.ROOT / 'step' / f'{NAME}.step'
    cq.exporters.export(cq.Workplane(obj=sol), str(step))
    bb = sol.BoundingBox()
    sp = cq.Workplane(obj=sol).translate((-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))
    stl = K.ROOT / 'stl' / f'{NAME}.stl'
    cq.exporters.export(sp, str(stl), tolerance=0.03, angularTolerance=0.12)
    tm = trimesh.load_mesh(stl)
    rt = cq.importers.importStep(str(step))
    v, f = C._mesh(sol)
    K.save_gz(K.ROOT / 'cad' / 'B01X_mesh.json.gz', dict(
        name=NAME, body='base', kind='printed', color=list(C.COLORS['dark']),
        v=np.round(v, 3).ravel().tolist(), t=np.asarray(f).ravel().tolist()))
    rep = dict(
        part=NAME, frame='R12 base body frame: O at the origin, X forward, Z up; vehicle = this + (%g, 0, %g)' % (K.O_X, K.O_Z),
        valid=bool(sol.isValid()), solids=1, watertight=bool(tm.is_watertight), winding_consistent=bool(tm.is_winding_consistent),
        single_shell=len(tm.split(only_watertight=False)) == 1, step_roundtrip_valid=bool(rt.val().isValid()),
        print_orientation='base plate on the bed (as B01: flange down); no supports except the O and A bores (bridged holes)',
        print_bounds_mm=[round(float(x), 1) for x in tm.extents],
        envelope_mm3=round(Ve, 1), infill_core_mm3=round(Vc, 1),
        mass_g=round(m * 1000, 1), com_mm_O_frame=[round(float(x), 2) for x in c],
        inertia_kg_mm2=[[round(float(x), 4) for x in row] for row in I],
        print_rule='PETG, 6 perimeters (2.5 mm) + 10 % gyroid infill, as every R12 print: envelope minus 90 % of the plate core',
        base_plate=dict(x_vehicle=list(K.BASE_X), y_abs=K.BASE_Y, z_vehicle=[K.T101_TOP_Z, K.T101_TOP_Z + K.BASE_T],
                        corner_fillet_mm=FILLET, bolt_holes=[dict(x=x, y=y, d=2 * K.BOLT_HOLE_R) for x, y in K.BOLTS]),
        unchanged_from_B01='foot plates |Y| 20.5-25.5 and outer cheeks |Y| 42.5-47.5 above Z O-49, the O bore Ø6.1 and the A bores Ø3.1 '
                           '(r12_design.foot_parts); A pins pressed in as ASSEMBLY.md',
        replaced='B01 flange 75.8 x 100 x 6 with 4 x Ø4.5 (M4) holes',
        cable_features=dict(issue=3, slots={k: dict(x_O=v[0], y=v[1], length_x=v[2], width_y=v[3], x_vehicle=v[0] + K.O_X) for k, v in H.SLOTS.items()},
                            troughs=dict(centreline_O=[list(p) for p in H.TROUGH['path']], width=H.TROUGH['w'], depth=H.TROUGH['depth'],
                                         mouth=dict(from_x_O=H.TROUGH['mouth_to_x'], width=H.TROUGH['mouth_w']), tie_pairs_x_O=list(H.TROUGH_TIES_X)),
                            tie_slots='%g x %g: two pairs across each trough, one pair behind each slot' % H.TIE_SLOT,
                            posts=dict(x_O=H.POST['x'], y=H.POST['y'], d=2 * H.POST['r'], top_z_O=H.POST['top'], top_z_vehicle=H.POST['top'] + K.O_Z, tie_hole_d=2.6, x_vehicle=H.POST['x'] + K.O_X)),
        b01_volume_mm3=round(Vb, 1),
        seconds=round(time.time() - t0, 1))
    assert rep['watertight'] and rep['single_shell'] and rep['step_roundtrip_valid'], rep
    (K.ROOT / 'cad' / 'B01X_report.json').write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: rep[k] for k in ('mass_g', 'print_bounds_mm', 'com_mm_O_frame', 'seconds')}))


if __name__ == '__main__':
    main()

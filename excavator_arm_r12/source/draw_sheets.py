"""R12 detailed design drawings (A3, 6 sheets) -> ../R12_design_drawings.pdf and ../images/sheet_N.png

Everything is generated from r12_design.py (geometry, outlines, pin stacks), design_check.json
(written by check_design.py) and r12_loads.py. The traced outlines are defined on the sheets by
offset tables (boom, stick) and a contour-point table (bucket).
"""
import sys
import json
import math
import itertools
from pathlib import Path
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from shapely.geometry import Point, Polygon, LineString, box
from shapely.ops import unary_union
import r12_design as d
import r12_loads as LD
from drawkit import Sheet as _Sheet, View, COL, INK, INK2, MUTED, FS, DASH, polys

ROOT = d.rc.ROOT
(ROOT / 'images').mkdir(exist_ok=True)
CHECK = json.loads((ROOT / 'design_check.json').read_text())
CLASH = json.loads((ROOT / 'cad' / 'clash_check.json').read_text())
DYN = json.loads((ROOT / 'simulation' / 'payload_150g_report.json').read_text())
_SYNC = json.loads((ROOT / 'simulation' / 'sync_bias_report.json').read_text())['poses']['boom']['mujoco_force_N']
SYNC_BOOM_MAX_N = max(_SYNC['boom_L'], _SYNC['boom_R'])           # boom pair with a 0.5 mm feedback-zero error
import r10_ref                    # R10 (excavator_arm_dual/) for the comparison on sheet 6

SERIES = ['#2a78d6', '#eb6834', '#1baf7a']          # boom, stick, bucket (validated categorical slots 1-3)
REFC = '#7d93a8'                                    # reference trace
NSHEETS = 6
REF_POSE = (40.0, 26.0, 30.0)
PIN_D = dict(O=6, E=6, H=6)
REV = 'Rev. D4'
STATUS = 'DETAILED DESIGN - MODELLED IN 3D (cad/, step/), 3D CLASH CHECK PASSED'
TRACE = d.rc.load_traced()


def Sheet(*a, **k):
    return _Sheet(*a, status=STATUS, rev=REV, **k)


def fmt(v, n=1):
    return f'{v:.{n}f}'


def offsets(prof, xs):
    """(x, z_top, z_bottom) where a vertical line at x cuts the outline."""
    out = []
    for x in xs:
        seg = LineString([(x, -500), (x, 500)]).intersection(prof)
        out.append((x, seg.bounds[3], seg.bounds[1]))
    return out


def offset_table(sh, x, y, rows, label, colw=10.6, first=17):
    data = [(label,) + tuple(f'{r[0]:.0f}' for r in rows),
            ('z top',) + tuple(f'{r[1]:.1f}' for r in rows),
            ('z bottom',) + tuple(f'{r[2]:.1f}' for r in rows)]
    return sh.table(x, y, [first] + [colw] * len(rows), data, rh=3.7, size=FS['xs'])


def station_marks(v, rows, lo_ext=3, hi_ext=3):
    for x, top, bot in rows:
        v.line([(x, bot - lo_ext), (x, top + hi_ext)], lw=0.25, color=MUTED, z=7)


# ------------------------------------------------------------------ assembled side view
def actuator_side(v, a, b, z, board=+1):
    """V6-U60 side view: body 17.3 deep (board housing on the `board` side, 9.75 from the axis; 7.55 on the
    other, the motor-side wall that hooks the rear cap)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    L = float(np.linalg.norm(b - a))
    u = (b - a) / L
    n = np.array([-u[1], u[0]]) * board

    def quad(s0, s1, hp, hm, fc, zz, lw=0.55):
        v.poly(Polygon([a + s0 * u + hp * n, a + s1 * u + hp * n, a + s1 * u - hm * n, a + s0 * u - hm * n]),
               fc=fc, lw=lw, z=zz)
    quad(122.5, L - 9.0, 4.0, 4.0, COL['rod'], z)
    quad(L - 11.0, L - 2.0, 4.5, 4.5, COL['rod'], z + 0.01)
    v.poly(Point(*b).buffer(4.5, 32), fc=COL['rod'], lw=0.55, z=z + 0.02)
    v.poly(Point(*a).buffer(4.5, 32), fc=COL['cap'], lw=0.55, z=z + 0.03)
    bk, bb = d.ACT['body_back'], d.ACT['body_board']
    quad(6.0, 10.0, bk, bk, COL['cap'], z + 0.04)
    quad(10.0, 116.5, bk, bk, COL['act'], z + 0.05)
    quad(14.0, 112.0, bb, -bk, '#d77c45', z + 0.06, lw=0.45)            # board housing
    quad(116.5, 122.5, bk, bk, COL['cap'], z + 0.07)


def arm_items(st):
    """(z_order = outer |Y|, geometry_world, fill) for the +Y half, drawn back to front."""
    s = d.solve(st)
    po = s['poses']
    pl = lambda g, f: d.place(g, *po[f])
    bp, fp, sr, bk, lk = d.boom_profile(), d.foot_parts(), d.stick_regions(), d.bucket_parts(), d.link_parts()
    it = [(13.0, pl(d.c_bracket(), 'boom'), COL['struct2']),
          (13.1, pl(d.f_lug(), 'stick'), COL['struct2']),
          (16.0, pl(d.stick_profile()[0], 'stick'), COL['struct']),
          (16.1, pl(d.disc(d.J_S, 7.0), 'stick'), COL['struct2']),
          (16.2, pl(d.disc(d.H_S, 11.0), 'stick'), COL['struct2']),
          (16.3, pl(sr['head'], 'stick'), COL['struct2']),
          (20.0, pl(bp, 'boom'), COL['struct']),
          (20.1, pl(d.disc(d.O, 10.0), 'boom'), COL['struct2']),
          (20.5, pl(bk['ears'], 'bucket'), COL['struct2']),
          (25.0, pl(lk['h'], 'h_link'), COL['link']),
          (25.5, fp['plate'], COL['base']),
          (29.8, pl(d.disc(d.B_B, 8.5), 'boom'), COL['struct2']),
          (30.0, pl(lk['side'], 'side_link'), '#8a9198'),
          (40.0, pl(bk['shell'], 'bucket'), COL['bucket']),
          (40.2, pl(bk['teeth'], 'bucket'), COL['steel']),
          (47.5, fp['outer'], COL['base']),
          (50.0, fp['flange'], COL['base'])]
    return s, it


def draw_arm(v, st, ghost=False, pins=True, labels=False, z0=0.0):
    s, items = arm_items(st)
    P = s['pins']
    acts = [(7.35, 'C', 'D', d.BOARD_SIDE['stick']), (7.36, 'F', 'R', d.BOARD_SIDE['bucket']),
            (41.35, 'A', 'B', d.BOARD_SIDE['boom'])]
    seq = sorted([(z, 'g', g, f, None) for z, g, f in items] + [(z, 'a', a, b, bs) for z, a, b, bs in acts],
                 key=lambda r: r[0])
    for z, kind, g, f, bs in seq:
        if ghost:
            if kind == 'g':
                v.poly(g, fc='none', ec=MUTED, lw=0.35, z=z0 + 1)
            else:
                v.line([P[g], P[f]], lw=0.35, color=MUTED, z=z0 + 1)
            continue
        if kind == 'g':
            v.poly(g, fc=f, lw=0.6, z=z0 + 2 + z / 10)
        else:
            actuator_side(v, P[g], P[f], z0 + 2 + z / 10, bs)
    if pins and not ghost:
        for k, p in P.items():
            if k == 'T':
                continue
            r = PIN_D.get(k, 3) / 2
            v.pin(p, r, collar=d.COLLAR_R[PIN_D.get(k, 3)], z=z0 + 9, cross=False, label=k if labels else None)
    return s


# ------------------------------------------------------------------ projections (prismatic parts)
def fillfor(name):
    if name.startswith('cyl'):
        return COL['act'] if 'body' in name else COL['rod']
    if name.startswith('pin'):
        return COL['steel']
    if name.startswith('foot'):
        return COL['base']
    if name.startswith(('side_link', 'h_link')):
        return COL['link']
    if name.startswith('bucket'):
        return COL['bucket'] if 'shell' in name else COL['struct2']
    if any(k in name for k in ('pad', 'cheek', 'bridge', 'head_plate', 'tube')):
        return COL['struct2']
    return COL['struct']


def silhouettes(st):
    out = []
    for name, body, g, (ylo, yhi) in d.parts_at(st):
        if not g.is_empty:
            x0, z0, x1, z1 = g.bounds
            out.append((name, (x0, x1), (z0, z1), (ylo, yhi)))
    return out


def front_view(v, st):
    for name, (x0, x1), (z0, z1), (y0, y1) in sorted(silhouettes(st), key=lambda r: r[1][1]):
        v.poly(box(y0, z0, y1, z1), fc=fillfor(name), lw=0.4, z=2 + x1 / 1000)


def plan_view(v, st):
    for name, (x0, x1), (z0, z1), (y0, y1) in sorted(silhouettes(st), key=lambda r: r[2][1]):
        v.poly(box(x0, y0, x1, y1), fc=fillfor(name), lw=0.4, z=2 + z1 / 1000)


# ------------------------------------------------------------------ sheet 1: general arrangement
def sheet1(pdf):
    sh = Sheet(1, NSHEETS, 'General arrangement', 'Side, front and plan view at the reference pose; key data',
               '1:2.5 (all views)')
    k = 0.4
    st = REF_POSE
    s = d.solve(st)
    P = s['pins']
    v = View(sh, 60, 172, k, label=f'SIDE VIEW  (reference pose, strokes {st[0]:.0f} / {st[1]:.0f} / {st[2]:.0f} mm)',
             label_xy=(16, 280))
    draw_arm(v, st, labels=True)
    v.line([(-105, d.GROUND_Z), (560, d.GROUND_Z)], lw=0.8, color=INK, z=1)
    for xx in np.arange(-99, 560, 9):
        v.line([(xx, d.GROUND_Z), (xx - 6, d.GROUND_Z - 6)], lw=0.3, color=INK2, z=1)
    v.line([(-105, d.TURNTABLE_Z), (14, d.TURNTABLE_Z)], lw=0.5, color=INK2, ls=DASH, z=1)
    v.text((-103, d.TURNTABLE_Z + 2.5), 'turntable face', size=FS['xs'], color=INK2)
    v.text((-103, d.GROUND_Z + 3), 'ground (X1 crawler)', size=FS['xs'], color=INK2)
    v.centerline((d.SWING_X, d.GROUND_Z - 4), (d.SWING_X, 60))
    v.text((d.SWING_X + 1.5, 52), 'swing centre', size=FS['xs'], color=INK2, rotation=90)
    v.dim(P['E'], P['H'], -14, mode='aligned', prefix='stick E-H ')
    v.dim(P['H'], P['T'], -14, mode='aligned', prefix='tip R ')
    v.dim((0, 0), (0, d.TURNTABLE_Z), -26, mode='v', fmt='{:.0f}')
    v.dim((0, 0), (0, d.GROUND_Z), -34, mode='v', fmt='{:.0f}')
    v.dim((d.SWING_X, d.GROUND_Z), (0, d.GROUND_Z), -7, mode='h', fmt='{:.0f}')
    po = s['poses']
    v.balloon(np.array([-20.0, -45.0]), 'B01', -12, 8)
    v.balloon(d.to_world((240, 60), *po['boom']), 'B02', 4, 14)
    v.balloon(d.to_world((110, -5), *po['stick']), 'B03', -16, -4)
    v.balloon(d.to_world((20, 0), *po['side_link']), 'B04', 16, 6)
    v.balloon(d.to_world((22, 0), *po['h_link']), 'B05', 16, -3)
    v.balloon(d.to_world((60, 45), *po['bucket']), 'B06', 18, -6)
    v.balloon(P['T'], 'B07', -16, 4)
    for lab, a, b, dx, dy in (('A1/A2', 'A', 'B', 12, -6), ('A3', 'C', 'D', -2, 12), ('A4', 'F', 'R', 14, 4)):
        v.balloon(P[a] + 0.45 * (P[b] - P[a]), lab, dx, dy, r=3.4)
    # front view (looking -X), aligned in Z
    fv = View(sh, 302, 172, k, label='FRONT VIEW  (looking -X)', label_xy=(282, 280))
    front_view(fv, st)
    fv.line([(-62, d.GROUND_Z), (62, d.GROUND_Z)], lw=0.8, z=1)
    fv.centerline((0, d.GROUND_Z - 3), (0, 205))
    fv.dim((-20, P['C'][1] + 22), (20, P['C'][1] + 22), 6, mode='h', text='boom 40')
    fv.dim((-d.Y['boom_cyl'], P['B'][1]), (d.Y['boom_cyl'], P['B'][1]), 14, mode='h', text='drives 68 c/c')
    fv.dim((-40, d.GROUND_Z), (40, d.GROUND_Z), -7, mode='h', text='bucket 80')
    fv.dim((-47.5, d.GROUND_Z), (47.5, d.GROUND_Z), -15, mode='h', text='foot cheeks 95')
    # plan view
    pv = View(sh, 60, 64, k, label='PLAN VIEW  (prismatic envelopes of every part)', label_xy=(16, 96))
    plan_view(pv, st)
    pv.centerline((-80, 0), (560, 0))
    pv.dim((P['O'][0], -50), (P['O'][0], 50), -22, mode='v', text='flange 100')
    # key data
    x0, y0 = 334, 283
    sh.heading(x0, y0, 'Key data')
    ck = CHECK
    jr, hf, hu = ck['joint_ranges_deg'], ck['hold_force_per_drive_N_150g'], ck['hold_force_per_drive_N_unloaded']
    wr, m = ck['working_ranges_mm'], ck['masses_kg']
    rows = [('Item', 'Value'),
            ('Reference', 'Cat 320 / 325, 1:15'),
            ('Boom O-E / stick E-H', f'{d.BOOM:.1f} / {d.STICK:.1f}'),
            ('Bucket tip radius / width', f'{d.TIP_R:.1f} / {d.BUCKET_W:.1f}'),
            ('Drives (all identical)', '4 x V6-U60'),
            ('Screw / stroke / pins', 'M3x0.5 75 / 60 / 140-200'),
            ('Boom chord range', f"{jr['boom'][0]:+.1f} .. {jr['boom'][1]:+.1f}"),
            ('Stick vs boom', f"{jr['stick'][0]:+.1f} .. {jr['stick'][1]:+.1f}"),
            ('Bucket vs stick', f"{jr['bucket'][0]:+.1f} .. {jr['bucket'][1]:+.1f}"),
            ('Hold force/drive, 150 g', f"{hf['boom']} / {hf['stick']} / {hf['bucket']} N"),
            ('Hold force/drive, empty', f"{hu['boom']} / {hu['stick']} / {hu['bucket']} N"),
            ('Continuous thrust (fuse)', f"{d.ACT['thrust_cont']:.0f} N per drive"),
            ('Digging depth', f"{wr['dig_depth']:.0f}"),
            ('Reach at ground', f"{wr['reach_ground']:.0f}"),
            ('Cutting height / dump', f"{wr['cut_height']:.0f} / {wr['dump_height']:.0f}"),
            ('Boom / stick / bucket mass', f"{m['boom']*1000:.0f} / {m['stick']*1000:.0f} / {m['bucket']*1000:.0f} g"),
            ('Interference sweep', f"{ck['status']}, {ck['poses_grid'] + ck['poses_fine']} poses")]
    yb = sh.table(x0, y0 - 3, [41, 38], rows, rh=4.1)
    sh.heading(x0, yb - 6, 'Parts')
    prow = [('No.', 'Part', 'Qty'), ('B01', 'Boom-foot bracket', '1 set'), ('B02', 'Boom, closed box', '1'),
            ('B03', 'Stick, head fork + box', '1'), ('B04', 'Side link', '2'), ('B05', 'H-link plate + R tube', '2'),
            ('B06', 'Bucket', '1'), ('B07', 'Replaceable tooth', '5'), ('A1-A4', 'V6-U60 drive', '4')]
    yb = sh.table(x0, yb - 9, [13, 46, 20], prow, rh=4.0, align=['left', 'left', 'right'])
    sh.notes(x0, yb - 3, ['Hold forces: worst static case over the',
                          'full stroke grid, gravity only (estimated',
                          'masses, PETG at the stated walls).',
                          'On the X1 crawler the boom-foot pin is',
                          '155 above ground. Positive angles turn',
                          '+X toward +Z.'], size=FS['xs'], gap=3.0)
    sh.save(pdf, ROOT / 'images' / 'sheet_1.png')


# ------------------------------------------------------------------ sheet 2: kinematics
def sheet2(pdf):
    sh = Sheet(2, NSHEETS, 'Kinematics and working range', 'Pins, joint ranges, forces, choice of stroke',
               '1:5 (range)')
    env = d.envelope(19, 25)
    k = 0.2
    v = View(sh, 66, 188, k, label='WORKING RANGE ON THE X1 CRAWLER  1:5', label_xy=(16, 280))
    v.poly(env, fc='#eaf1f8', ec=COL['ref'], lw=0.8, z=1)
    tr = unary_union([Point(d.SWING_X - 154.3 + 46.2, d.GROUND_Z + 46.2).buffer(46.2),
                      Point(d.SWING_X + 154.3 - 46.2, d.GROUND_Z + 46.2).buffer(46.2)]).convex_hull
    v.poly(tr, fc='none', ec=INK2, lw=0.5, ls=DASH, z=2)
    v.poly(box(d.SWING_X - 60, d.TURNTABLE_Z - 10, d.SWING_X + 60, d.TURNTABLE_Z), fc='none', ec=INK2, lw=0.5, ls=DASH, z=2)
    v.text((d.SWING_X - 120, d.GROUND_Z + 20), 'X1 crawler (reference)', size=FS['xs'], color=INK2)
    v.line([(-235, d.GROUND_Z), (700, d.GROUND_Z)], lw=0.8, z=3)
    v.centerline((d.SWING_X, -500), (d.SWING_X, 430))
    for st in [(0, 0, 0), (60, 0, 0), (0, 40, 45), (60, 60, 60)]:
        draw_arm(v, st, ghost=True, pins=False)
    draw_arm(v, REF_POSE, pins=False, z0=5)
    wr = CHECK['working_ranges_mm']
    lo = env.bounds
    v.dim((d.SWING_X, d.GROUND_Z), (d.SWING_X + wr['reach_ground'], d.GROUND_Z), -(d.GROUND_Z - lo[1]) * k - 6, mode='h',
          fmt='{:.0f}', prefix='reach at ground ')
    v.dim((lo[2] - 5, d.GROUND_Z), (lo[2] - 5, lo[1]), 14, mode='v', fmt='{:.0f}', prefix='depth ')
    v.dim((lo[2] + 10, d.GROUND_Z), (lo[2] + 10, lo[3]), 26, mode='v', fmt='{:.0f}', prefix='cutting height ')
    v.dim((-200, d.GROUND_Z), (-200, d.GROUND_Z + wr['dump_height']), 0, mode='v', fmt='{:.0f}', prefix='dump height ')
    v.line([(-200, d.GROUND_Z + wr['dump_height']), (150, d.GROUND_Z + wr['dump_height'])], lw=0.35, color=INK2, ls=DASH)
    # pin table
    x0, y0 = 250, 283
    sh.heading(x0, y0, 'Pin coordinates')
    ref = d.P
    rows = [('Pin', 'Frame', 'X', 'Z', 'Reference', 'Function'),
            ('O', 'world', '0.0', '0.0', '=', 'boom foot, Ø6'),
            ('A', 'world', fmt(d.A_W[0]), fmt(d.A_W[1]), f"{ref['A_world'][0]:.1f}, {ref['A_world'][1]:.1f}", 'boom drive base (x2, Y±34)'),
            ('B', 'boom', fmt(d.B_B[0]), fmt(d.B_B[1]), '=', 'boom drive rod, through-pin'),
            ('C', 'boom', fmt(d.C_B[0]), fmt(d.C_B[1]), f"{ref['C_boom'][0]:.1f}, {ref['C_boom'][1]:.1f}", 'stick drive base'),
            ('E', 'boom', f'{d.BOOM:.1f}', '0.0', '=', 'boom-stick, Ø6'),
            ('D', 'stick', fmt(d.D_S[0]), fmt(d.D_S[1]), f"{ref['D_stick'][0]:.1f}, {ref['D_stick'][1]:.1f}", 'stick drive rod'),
            ('F', 'stick', fmt(d.F_S[0]), fmt(d.F_S[1]), f"{ref['F_stick'][0]:.1f}, {ref['F_stick'][1]:.1f}", 'bucket drive base'),
            ('J', 'stick', fmt(d.J_S[0]), fmt(d.J_S[1]), '=', 'side-link pivot'),
            ('H', 'stick', f'{d.STICK:.1f}', '0.0', '=', 'stick-bucket, Ø6'),
            ('Q', 'bucket', fmt(d.Q_K[0]), fmt(d.Q_K[1]), '=', 'H-link to bucket ears'),
            ('T', 'bucket', f'{d.TIP_R:.1f}', '0.0', '=', 'tooth tip'),
            ('Links', '', f'J-R {d.SIDE_LINK:.1f}', f'R-Q {d.H_LINK:.1f}', '=', f'H-Q {d.EAR:.1f}')]
    yb = sh.table(x0, y0 - 3, [11, 13, 17, 17, 25, 80], rows, rh=4.0,
                  align=['left', 'left', 'right', 'right', 'right', 'left'])
    sh.notes(x0, yb - 2, ['Reference: Cat 325 pins (US 6,518,519, Table 1), each link scaled to Cat 320 at 1:15; "=" kept.',
                          'Frames: world X fwd / Z up at O; boom x along O->E; stick x along E->H, +z outer face;',
                          'bucket x along H->T, +z back of bucket. Ground Z -155, turntable face Z -55.'],
             size=FS['xs'], gap=3.0)
    yb -= 15
    sh.heading(x0, yb, 'Joints (drive stroke 0 -> 60 mm)')
    jr, ma = CHECK['joint_ranges_deg'], CHECK['min_moment_arm_mm']
    hf, hu = CHECK['hold_force_per_drive_N_150g'], CHECK['hold_force_per_drive_N_unloaded']
    rows = [('Joint', 'at 0', 'at 60', 'travel', 'min lever', 'hold 150 g', 'hold empty')]
    for j in ('boom', 'stick', 'bucket'):
        a0, a1 = jr[j]
        rows.append((j, f'{a0:+.1f}', f'{a1:+.1f}', f'{abs(a1 - a0):.1f}', f'{ma[j]:.1f}', f'{hf[j]} N', f'{hu[j]} N'))
    yb = sh.table(x0, yb - 3, [20, 18, 18, 18, 22, 33, 34], rows, rh=4.0)
    mt, tf = CHECK['min_transmission_deg'], CHECK['tip_force_at_rating']
    sh.notes(x0, yb - 2, [f"Bucket four-bar: minimum transmission angle {mt['Q']}° at Q, {mt['R']}° at R.",
                          f"At {d.ACT['thrust_cont']:.0f} N: tooth force from the bucket drive {tf['bucket_min']}-{tf['bucket_max']} N, from the stick "
                          f"drive {tf['stick_min']}-{tf['stick_max']} N.",
                          'Extension raises the boom, crowds the stick and curls the bucket.'], size=FS['xs'], gap=3.0)
    # charts
    grid = np.linspace(0, 60, 13)
    curves = [[], [], []]
    for i in range(3):
        for sv in grid:
            worst = 0
            for a, b in itertools.product(grid[::2], repeat=2):
                stx = [a, b]
                stx.insert(i, sv)
                worst = max(worst, abs(d.drive_forces(tuple(stx))[i]))
            curves[i].append(worst)
    ax = sh.chart(258, 116, 70, 50)
    names = ['boom (each of 2)', 'stick', 'bucket']
    for i in range(3):
        ax.plot(grid, curves[i], color=SERIES[i], lw=1.5, label=names[i])
        ax.text(61, curves[i][-1], names[i].split(' ')[0], fontsize=FS['xs'], color=INK, va='center')
    ax.axhline(d.ACT['thrust_cont'], color=INK2, lw=0.8, ls=(0, (4, 2)))
    ax.text(1, d.ACT['thrust_cont'] + 1.5, f"{d.ACT['thrust_cont']:.0f} N continuous thrust", fontsize=FS['xs'], color=INK2)
    ax.set_xlim(0, 60)
    ax.set_ylim(0, 60)
    ax.set_xlabel('stroke of that drive, mm', fontsize=FS['xs'], color=INK2)
    ax.set_title('Worst static holding force per drive, 150 g load (N)', fontsize=FS['s'], color=INK, loc='left')
    ax.legend(fontsize=FS['xs'], frameon=False, loc='upper center', bbox_to_anchor=(0.5, 0.8), ncol=3)
    arms = np.array([d.moment_arms((s_, s_, s_)) for s_ in grid])
    ax2 = sh.chart(342, 116, 62, 50)
    for i in range(3):
        ax2.plot(grid, arms[:, i], color=SERIES[i], lw=1.5, label=['boom', 'stick', 'bucket'][i])
        ax2.text(61, arms[-1, i], ['boom', 'stick', 'bucket'][i], fontsize=FS['xs'], color=INK, va='center')
    ax2.set_xlim(0, 60)
    ax2.set_ylim(0, 50)
    ax2.set_xlabel('stroke, mm', fontsize=FS['xs'], color=INK2)
    ax2.set_title('Effective lever on the joint (mm/rad)', fontsize=FS['s'], color=INK, loc='left')
    ax2.legend(fontsize=FS['xs'], frameon=False, loc='lower center', ncol=3)
    # stroke study + Cat comparison
    x1, y1 = 18, 70
    sh.heading(x1, y1, 'Why every drive stays at 60 mm stroke')
    rows = [('Stroke', 'Screw', 'Pins', 'Boom -35..+50°, real B', 'Stick, real tail', 'Verdict')]
    verdict = {40: 'too short', 55: 'weaker boom', 60: 'chosen (stock U60)', 65: 'no gain, custom screw',
               70: 'boom does not fit', 80: 'stick only', 85: 'boom does not fit (V6-L)'}
    for r in CHECK['stroke_study']:
        boom = (f"lever {r['boom_lever']}, A Z {r['boom_base'][1]:.0f}" if r['boom_lever'] else
                'cannot span 85°' if r['stroke'] < 55 else 'base A below the deck')
        stick = f"{r['stick_real_tail_span']}°, lever {r['stick_real_tail_lever']}" if r['stick_real_tail_span'] else '-'
        rows.append((f"{r['stroke']}", f"{r['screw']}", f"{r['closed']}-{r['open']}", boom, stick,
                     verdict.get(r['stroke'], '')))
    yb = sh.table(x1, y1 - 3, [12, 11, 16, 34, 27, 34], rows, rh=3.7, size=FS['xs'],
                  align=['right', 'right', 'right', 'left', 'left', 'left'])
    sh.notes(x1, yb - 2, ['The boom decides: with the real rod pin B, a stroke above 65 mm needs the base pin A below the',
                          'turntable deck (Z < -50). 60 mm gives the best boom lever and is the stock 75 mm screw. A longer',
                          'stroke would only let the stick keep the real 50 mm tail, i.e. a second drive model.'],
             size=FS['xs'], gap=3.0)
    x2 = 157
    sh.heading(x2, y1, 'Against Cat 320 at 1:15')
    c = CHECK['cat320_1_15_mm']
    rows = [('Range', 'R12', 'Cat 1:15', 'ratio'),
            ('Digging depth', f"{wr['dig_depth']:.0f}", f"{c['dig_depth']:.0f}", f"{wr['dig_depth'] / c['dig_depth'] * 100:.0f} %"),
            ('Reach at ground', f"{wr['reach_ground']:.0f}", f"{c['reach_ground']:.0f}",
             f"{wr['reach_ground'] / c['reach_ground'] * 100:.0f} %"),
            ('Cutting height', f"{wr['cut_height']:.0f}", f"{c['cut_height']:.0f}", f"{wr['cut_height'] / c['cut_height'] * 100:.0f} %"),
            ('Dump height (lowest point)', f"{wr['dump_height']:.0f}", f"{c['load_height']:.0f}**", '')]
    yb = sh.table(x2, y1 - 3, [38, 12, 16, 14], rows, rh=3.7, size=FS['xs'])
    sh.notes(x2, yb - 2, ['** Cat loading height is measured differently.',
                          f"Boom range {jr['boom'][0]:+.0f}..{jr['boom'][1]:+.0f}° and stick range 90°",
                          '(Cat: ~100-130°) cost the depth; the forces stay',
                          f"under {d.ACT['thrust_cont']:.0f} N with margin."], size=FS['xs'], gap=3.0)
    lim = CHECK['x1_track_limit']
    sh.notes(250, 100, [f"On the X1 crawler, slewed over a track (~90°), the boom must stay above stroke {lim['stroke']:.0f} mm "
                       f"({lim['boom_deg']:+.0f}°): soft limit or operator."], size=FS['xs'])
    sh.save(pdf, ROOT / 'images' / 'sheet_2.png')


# ------------------------------------------------------------------ sheet 3: boom and foot bracket
def box_section(v, c, b, h, t, hatch='////'):
    outer = box(c[0] - b / 2, c[1] - h / 2, c[0] + b / 2, c[1] + h / 2)
    inner = box(c[0] - b / 2 + t, c[1] - h / 2 + t, c[0] + b / 2 - t, c[1] + h / 2 - t)
    v.poly(outer.difference(inner), fc='white', ec=INK, lw=0.7, hatch=hatch, z=5)
    return outer


def trace_overlay(v, part):
    v.poly(Polygon(TRACE[part]), fc='none', ec=REFC, lw=0.45, ls=DASH, z=2.5)


def sheet3(pdf):
    sh = Sheet(3, NSHEETS, 'B02 boom and B01 boom-foot bracket', 'Closed box on the traced Cat 320 outline; '
               'boom drives on boss pads and one through-pin', '1:2 (views), 1:1 (sections)')
    bp = d.boom_profile()
    k = 0.5
    v = View(sh, 32, 216, k, label='B02 BOOM - SIDE (boom frame, chord O-E horizontal)', label_xy=(16, 280))
    trace_overlay(v, 'boom')
    v.poly(bp, fc=COL['struct'], lw=0.8, z=3)
    v.poly(d.c_bracket(), fc=COL['struct2'], lw=0.6, z=2)
    v.poly(d.disc(d.B_B, 8.5), fc=COL['struct2'], lw=0.6, z=4)
    v.poly(bp.buffer(-d.T_WALL, join_style=2), fc='none', ec=INK2, lw=0.35, ls=DASH, z=4)
    for p, r, lab in ((d.O, 3, 'O'), (d.E_B, 3, 'E'), (d.B_B, 1.5, 'B'), (d.C_B, 1.5, 'C')):
        v.pin(p, r, z=8, label=lab, lpos=(2.2, 2.2))
    v.centerline((-25, 0), (405, 0))
    rows = offsets(bp, list(range(0, 381, 20)))
    station_marks(v, rows)
    v.dim(d.O, d.E_B, -27, mode='h', fmt='{:.1f}')
    v.dim(d.O, d.B_B, -20, mode='h', fmt='{:.1f}')
    v.dim(d.B_B, (d.B_B[0], 0), -8, mode='v', fmt='{:.1f}')
    v.dim(d.C_B, d.E_B, 20, mode='h', fmt='{:.1f}')
    v.dim(d.C_B, (d.C_B[0], 0), 10, mode='v', fmt='{:.1f}')
    v.radius(d.O, 14, -100, 'R14 root', out=4)
    v.radius(d.E_B, 14, -40, 'R14 nose', out=4)
    v.circle(d.E_B, d.BOOM_NOSE_R, ec=INK2, lw=0.3)
    v.text(d.E_B + np.array([-100, -40]), f'nose 21 wide inside R{d.BOOM_NOSE_R:.0f} of E', size=FS['xs'], color=INK2)
    v.leader(d.C_B + np.array([8, -10]), 'C bracket: two 5 mm cheeks', 12, 6, size=FS['xs'])
    v.line([(205, -18), (205, 100)], lw=0.6, color='#a14b16', ls=DASH)
    v.text((207, 96), 'S: optional split', size=FS['xs'], color='#a14b16')
    for x, lab in ((155, 'A'), (290, 'B'), (360, 'C')):
        _, lo_, hi_ = LD.section_depth(x, bp)
        v.section_mark((x, lo_ - 7), (x, hi_ + 7), lab)
    v.text((30, -32), 'dashed blue: Cat 320 trace', size=FS['xs'], color=REFC)
    yb = offset_table(sh, 16, 181, rows, 'x')
    sh.text(16, yb - 3.5, 'Offsets in the boom frame (x along O-E, z up). Outline = fair curve through the offsets; '
            'ends R14 about O and E. Walls 2.5, tolerance ±0.3.', size=FS['xs'], color=INK2)
    # plan
    pv = View(sh, 32, 131, k, label='B02 BOOM - PLAN', label_xy=(16, 153))
    nose_x0, nose_x1 = d.BOOM - d.BOOM_NOSE_R - 16, d.BOOM - d.BOOM_NOSE_R
    plan = Polygon([(-14, -20), (nose_x0, -20), (nose_x1, -10.5), (394, -10.5), (394, 10.5), (nose_x1, 10.5),
                    (nose_x0, 20), (-14, 20)])
    pv.poly(plan, fc=COL['struct'], lw=0.8, z=3)
    cb = d.c_bracket().bounds
    for sg in (1, -1):
        pv.poly(box(d.B_B[0] - 8.5, min(sg * 20, sg * 29.8), d.B_B[0] + 8.5, max(sg * 20, sg * 29.8)),
                fc=COL['struct2'], lw=0.6, z=4)
        pv.poly(box(cb[0], min(sg * 8, sg * 13), cb[2], max(sg * 8, sg * 13)), fc=COL['struct2'], lw=0.6, z=5)
    pv.centerline((-25, 0), (405, 0))
    for x in (0, d.B_B[0], d.C_B[0], d.BOOM):
        pv.centerline((x, -36), (x, 36))
    pv.dim((0, -20), (0, 20), -10, mode='v', fmt='{:.0f}')
    pv.dim((d.BOOM, -10.5), (d.BOOM, 10.5), 14, mode='v', fmt='{:.0f}')
    pv.dim((d.B_B[0], -29.8), (d.B_B[0], 29.8), 12, mode='v', fmt='{:.1f}')
    pv.dim((cb[0], 13), (cb[2], 13), 5, mode='h', fmt='{:.0f}')
    pv.dim((nose_x0, 20), (nose_x1, 20), 6, mode='h', fmt='{:.0f}')
    # sections 1:1
    secs = [(155, 'A-A  through B'), (290, 'B-B  front leg'), (360, 'C-C  nose')]
    for (x, lab), px in zip(secs, (282, 342, 392)):
        h, lo_, hi_ = LD.section_depth(x, bp)
        b = 21.0 if x > d.BOOM - d.BOOM_NOSE_R else 40.0
        sv = View(sh, px, 238, 1.0, origin=(0, (lo_ + hi_) / 2), label=lab, label_xy=(px - (34 if x == 155 else 18), 282))
        box_section(sv, (0, (lo_ + hi_) / 2), b, h, d.T_WALL)
        sv.dim((-b / 2, hi_), (b / 2, hi_), 5, mode='h', fmt='{:.0f}')
        sv.dim((b / 2, lo_), (b / 2, hi_), 15 if x == 155 else 5, mode='v', fmt='{:.1f}')
        if x == 155:
            zc = d.B_B[1]
            sv.poly(box(-20, zc - 5, 20, zc + 5), fc='white', ec=INK, lw=0.5, hatch='\\\\\\\\', z=6)
            (p0, p1), (b0, b1), br = d.Y['boom_b_pad'], d.Y['boom_b_boss'], d.ACT['boss_r']
            for sg in (1, -1):
                sv.poly(box(min(sg * p0, sg * p1), zc - 8.5, max(sg * p0, sg * p1), zc + 8.5), fc='white', ec=INK,
                        lw=0.5, hatch='////', z=6)
                sv.poly(box(min(sg * b0, sg * b1), zc - br, max(sg * b0, sg * b1), zc + br), fc='white', ec=INK,
                        lw=0.5, hatch='////', z=6)
            sv.line([(-41, zc), (41, zc)], lw=1.4, color='#6f7780', z=7)
            sv.dim((-b1, zc - 8.5), (b1, zc - 8.5), -4, mode='h', text=f'bosses {2 * b1:.1f}')
            sv.text((-34, lo_ - 9), 'Ø10 cross tube + Ø3 x 82 pin;', size=FS['xs'])
            sv.text((-34, lo_ - 12.5), 'eyes and collars: sheet 6, B', size=FS['xs'])
        else:
            sv.text((-b / 2 - 4, lo_ - 8), f'walls {d.T_WALL}', size=FS['xs'])
            sv.text((-b / 2 - 4, lo_ - 11.5), f'Z = {LD.box_modulus(b, h, d.T_WALL):.0f} mm³', size=FS['xs'])
    # bending moment
    xs_ = np.linspace(2, 378, 60)
    env = LD.envelope(xs_)
    ax = sh.chart(262, 128, 140, 48)
    ax.fill_between(xs_, env / 1000, color=SERIES[0], alpha=0.18, lw=0)
    ax.plot(xs_, env / 1000, color=SERIES[0], lw=1.5)
    for x, lab in ((d.B_B[0], 'B'), (d.C_B[0], 'C'), (205, 'S')):
        ax.axvline(x, color=INK2, lw=0.6, ls=(0, (3, 2)))
        ax.text(x + 2, env.max() / 1000 * 1.02, lab, fontsize=FS['xs'], color=INK2)
    ax.set_xlim(0, 380)
    ax.set_ylim(0, env.max() / 1000 * 1.15)
    ax.set_xlabel('boom station x, mm', fontsize=FS['xs'], color=INK2)
    ax.set_title('Boom bending-moment envelope, hold with 150 g (N·m)', fontsize=FS['s'], color=INK, loc='left')
    rows = [('x', 'depth', 'M N·mm', 'σ MPa')] + [(f"{r['x']:.0f}", f"{r['depth']}", f"{r['M_Nmm']:.0f}",
                                                   f"{r['sigma_MPa']:.2f}") for r in CHECK['boom_sections']]
    sh.table(262, 114, [16, 16, 22, 18], rows, rh=3.7)
    sh.notes(338, 114, ['Bending stress is < 1 MPa in the hold case',
                        f"and a few MPa even at {d.ACT['thrust_stall']:.0f} N stall. Walls",
                        'are set by stiffness, handling and the pin',
                        'bosses; the bosses and the printed layer',
                        'bond are what need testing.'], size=FS['xs'], gap=3.0)
    # foot bracket
    fp = d.foot_parts()
    fv = View(sh, 48, 66, k, label='B01 BOOM-FOOT BRACKET - SIDE / FRONT', label_xy=(16, 108))
    fv.poly(fp['plate'], fc=COL['base'], lw=0.7, z=3)
    fv.poly(fp['outer'], fc='#7b838c', lw=0.7, z=4)
    fv.poly(fp['flange'], fc=COL['base'], lw=0.7, z=5)
    fv.pin(d.O, 3, z=8, label='O')
    fv.pin(d.A_W, 1.5, z=8, label='A', lpos=(2.4, -4.5))
    fv.dim((0, 0), (0, d.TURNTABLE_Z), -24, mode='v', fmt='{:.0f}')
    fv.dim(d.O, d.A_W, 14, mode='h', fmt='{:.1f}')
    fv.dim(d.A_W, (d.A_W[0], d.TURNTABLE_Z), 14, mode='v', fmt='{:.1f}')
    fv.dim((-36, d.TURNTABLE_Z), (fp['flange'].bounds[2], d.TURNTABLE_Z), -6, mode='h', fmt='{:.0f}')
    ff = View(sh, 128, 66, k)
    ff.poly(box(-50, d.TURNTABLE_Z, 50, d.TURNTABLE_Z + 6), fc=COL['base'], lw=0.7, z=3)
    for sg in (1, -1):
        ff.poly(box(min(sg * 20.5, sg * 25.5), d.TURNTABLE_Z + 6, max(sg * 20.5, sg * 25.5), 13), fc=COL['base'], lw=0.7, z=4)
        ff.poly(box(min(sg * 42.5, sg * 47.5), d.TURNTABLE_Z + 6, max(sg * 42.5, sg * 47.5), d.A_W[1] + 7.5), fc='#7b838c',
                lw=0.7, z=4)
        ff.poly(box(min(sg * 31, sg * 37), d.A_W[1] - 4.5, max(sg * 31, sg * 37), d.A_W[1] + 4.5), fc=COL['cap'], lw=0.5, z=5)
    ff.poly(box(-20, -14, 20, 14), fc=COL['struct'], lw=0.6, z=2)
    ff.line([(-30, 0), (30, 0)], lw=1.4, color='#6f7780', z=6)
    ff.centerline((0, d.TURNTABLE_Z - 4), (0, 18))
    ff.dim((-50, d.TURNTABLE_Z), (50, d.TURNTABLE_Z), -6, mode='h', fmt='{:.0f}')
    ff.dim((-25.5, 13), (25.5, 13), 5, mode='h', fmt='{:.0f}')
    ff.dim((-47.5, d.TURNTABLE_Z), (47.5, d.TURNTABLE_Z), -12, mode='h', fmt='{:.0f}')
    sh.heading(176, 108, 'Construction')
    sh.notes(176, 103, ['Printed in one piece lying on a side plate: 6 perimeters (2.5 mm',
                        'walls) + 10 % gyroid infill as the internal bracing. Needs a',
                        '410 mm bed; otherwise split at S (spigot + 4 x M3 x 45).',
                        'B08 pads (Ø17 + Ø7.2 boss) printed separately and bonded.',
                        'Outline: the Cat 320 boom (traced), knee and taper kept. The',
                        'reference lift-cylinder boss is replaced by the B pads.',
                        'B: Ø10 cross tube in the box; Ø17 pads + Ø7.2 bosses outside; one Ø3',
                        'hardened pin carries both drive eyes (Y ±34).',
                        'C: two 5 mm cheeks rise 16 mm from the top flange (|Y| 8-13).',
                        f'Nose: 21 wide inside R{d.BOOM_NOSE_R:.0f} of E, closed box between the stick',
                        'head plates. Split S at x 205 for <= 250 mm beds: 30 mm spigot',
                        '+ 4 x M3 through the side walls.',
                        'B01: two 5 mm plates carry O and the inner end of A; outer',
                        'cheeks close each A clevis; 6 mm flange, 4 x M4 into inserts.'], size=FS['xs'], gap=3.1)
    sh.save(pdf, ROOT / 'images' / 'sheet_3.png')


# ------------------------------------------------------------------ sheet 4: stick and links
def sheet4(pdf):
    sh = Sheet(4, NSHEETS, 'B03 stick, B04 side link, B05 H-link', 'Head fork carries D, E and F; '
               'side links and H-link plates outside the bucket ears', '1:1')
    sp = d.stick_profile()[0]
    sr = d.stick_regions()
    v = View(sh, 68, 216, 1.0, label='B03 STICK - SIDE (stick frame, E-H horizontal)', label_xy=(16, 280))
    trace_overlay(v, 'stick')
    v.poly(sp, fc=COL['struct'], lw=0.8, z=3)
    v.poly(sr['head'], fc=COL['struct2'], lw=0.5, z=3.5)
    v.poly(d.f_lug(), fc=COL['struct2'], lw=0.6, z=3.6)
    v.poly(sp.buffer(-d.T_WALL, join_style=2).difference(sr['head']).difference(d.f_lug()), fc='none', ec=INK2, lw=0.35,
           ls=DASH, z=4)
    v.poly(sr['bridge'], fc='none', ec=INK, lw=0.45, ls=DASH, z=4.2)
    v.poly(d.disc(d.J_S, 7.0), fc=COL['struct2'], lw=0.6, z=4)
    v.poly(d.disc(d.H_S, 11.0), fc=COL['struct2'], lw=0.6, z=4)
    for nm, p, r in (('E', np.zeros(2), 3), ('D', d.D_S, 1.5), ('F', d.F_S, 1.5), ('J', d.J_S, 1.5), ('H', d.H_S, 3)):
        v.pin(p, r, z=8, label=nm, lpos=(2.4, 2.4))
    v.centerline((-50, 0), (212, 0))
    rows = offsets(d.stick_base(), list(range(-40, 201, 20)))
    station_marks(v, rows)
    v.dim((0, 0), d.H_S, -24, mode='h', fmt='{:.2f}')
    v.dim(d.D_S, (0, 0), 30, mode='h', fmt='{:.1f}')
    v.dim(d.D_S, (d.D_S[0], 0), -8, mode='v', fmt='{:.1f}')
    v.dim(d.F_S, (0, 0), 14, mode='h', fmt='{:.1f}')
    v.dim((0, 0), d.F_S, 18, mode='v', fmt='{:.1f}')
    v.dim(d.J_S, d.H_S, -14, mode='h', fmt='{:.1f}')
    v.radius(d.H_S, 11, -30, 'nose boss')
    v.radius(np.zeros(2), 15, -120, 'R15')
    v.radius(d.D_S, 7.5, 160, 'R7.5')
    v.leader(np.array([20.0, 31.0]), 'bridge (dashed): head plates tied, |Y| < 11', 30, 22, size=FS['xs'])
    v.text((110, 30), 'dashed blue: Cat 320 trace', size=FS['xs'], color=REFC)
    v.section_mark((120, -19), (120, 24), 'K')
    yb = offset_table(sh, 16, 186, rows, 'u', colw=11.4)
    sh.text(16, yb - 3.5, 'Offsets in the stick frame (u along E-H, v to the outer face). Fair curve through the offsets; '
            'tail = hull of R15 at E, R7.5 at D; F lug (not in the table) and J, H bosses as drawn.', size=FS['xs'], color=INK2)
    sh.text(16, yb - 7.0, f'Pins (u, v): E (0, 0), D ({d.D_S[0]:.1f}, {d.D_S[1]:.1f}), F ({d.F_S[0]:.1f}, {d.F_S[1]:.1f}), '
            f'J ({d.J_S[0]:.1f}, {d.J_S[1]:.1f}), H ({d.H_S[0]:.2f}, 0). Ø6 at E and H, Ø3 elsewhere. '
            f'Darker: head fork, plates |Y| 11-16 inside R{d.STICK_FORK_R:.0f} of E.',
            size=FS['xs'], color=INK2)
    # plan
    pv = View(sh, 68, 138, 1.0, label='B03 STICK - PLAN', label_xy=(16, 160))
    x0, _, x1, _ = sp.bounds
    head_x1 = sr['head'].bounds[2]
    for sg in (1, -1):
        pv.poly(box(x0, min(sg * 11, sg * 16), head_x1, max(sg * 11, sg * 16)), fc=COL['struct2'], lw=0.7, z=3)
        fl = d.f_lug().bounds
        pv.poly(box(fl[0], min(sg * 8, sg * 13), fl[2], max(sg * 8, sg * 13)), fc=COL['struct2'], lw=0.6, z=4)
    pv.poly(box(d.STICK_FORK_R * 0.75, -16, x1, 16), fc=COL['struct'], lw=0.7, z=2)
    brb = sr['bridge'].bounds
    pv.poly(box(brb[0], -11, brb[2], 11), fc=COL['struct'], ec=INK, lw=0.5, hatch='....', z=2.5)
    pv.text((brb[0] + 26, 2), 'bridge |Y| < 11', size=FS['xs'], color=INK2)
    for x in (0, d.D_S[0], d.F_S[0], d.J_S[0], d.H_S[0]):
        pv.centerline((x, -20), (x, 20))
    pv.centerline((-50, 0), (212, 0))
    pv.dim((x1 - 12, -16), (x1 - 12, 16), 16, mode='v', fmt='{:.0f}')
    pv.dim((x0 + 4, 11), (x0 + 4, 16), -6, mode='v', text='5')
    pv.dim((x0 + 12, -11), (x0 + 12, 11), -12, mode='v', text='22 gap')
    # section D-D (box) and head section at E
    seg = LineString([(120, -100), (120, 100)]).intersection(sp)
    lo_, hi_ = seg.bounds[1], seg.bounds[3]
    sv = View(sh, 312, 252, 1.0, origin=(0, (lo_ + hi_) / 2), label='K-K  stick box', label_xy=(292, 280))
    box_section(sv, (0, (lo_ + hi_) / 2), 32, hi_ - lo_, d.T_WALL)
    sv.dim((-16, hi_), (16, hi_), 5, mode='h', fmt='{:.0f}')
    sv.dim((16, lo_), (16, hi_), 5, mode='v', fmt='{:.1f}')
    hv = View(sh, 376, 252, 1.0, label='E-E  head at E', label_xy=(352, 280))
    for sg in (1, -1):
        hv.poly(box(min(sg * 11, sg * 16), -15, max(sg * 11, sg * 16), 15), fc='white', ec=INK, hatch='////', lw=0.6, z=4)
        hv.poly(box(min(sg * 16.3, sg * 20.3), -5.5, max(sg * 16.3, sg * 20.3), 5.5), fc=COL['steel'], lw=0.5, z=5)
    hv.poly(box(-10.5, -14, 10.5, 14), fc='white', ec=INK, hatch='\\\\\\\\', lw=0.6, z=3)
    hv.poly(box(-21, -3, 21, 3), fc='#e9edf0', lw=0.5, z=6)
    hv.dim((-10.5, 15), (10.5, 15), 4, mode='h', text='nose 21')
    hv.dim((-16, -15), (16, -15), -5, mode='h', fmt='{:.0f}')
    hv.text((-22, -27), 'Boom nose between the head plates;', size=FS['xs'])
    hv.text((-22, -30.5), 'Ø6 x 42 pin, collars outside.', size=FS['xs'])
    # links
    lk = d.link_parts()
    lv = View(sh, 290, 176, 1.0, label='B04 SIDE LINK (x2)', label_xy=(282, 200))
    lv.poly(lk['side'], fc='#8a9198', lw=0.7, z=3)
    lv.pin((0, 0), 1.5, z=8, label='J')
    lv.pin((d.SIDE_LINK, 0), 1.5, z=8, label='R')
    lv.dim((0, 0), (d.SIDE_LINK, 0), 9, mode='h', fmt='{:.2f}')
    lv.text((-5, -11), '4 mm plate, R5 ends, |Y| 26-30 (outermost)', size=FS['xs'])
    hv2 = View(sh, 352, 176, 1.0, label='B05 H-LINK (x2)', label_xy=(346, 200))
    hv2.poly(lk['h'], fc=COL['link'], lw=0.7, z=3)
    hv2.poly(d.disc(np.zeros(2), 5.0), fc='#8a9198', lw=0.6, z=4)
    hv2.pin((0, 0), 1.5, z=8, label='R')
    hv2.pin((d.H_LINK, 0), 1.5, z=8, label='Q')
    hv2.dim((0, 0), (d.H_LINK, 0), 9, mode='h', fmt='{:.2f}')
    hv2.text((-5, -11), '4 mm plate |Y| 21-25 + Ø10 tube at R to |Y| 5.8,', size=FS['xs'])
    hv2.text((-5, -14.5), 'then Ø7.2 boss to |Y| 3.1 (clears the Ø11 eye socket)', size=FS['xs'])
    # transmission chart
    ks = np.linspace(0, 60, 31)
    tr = np.array([d.transmission((30, 30, kk)) for kk in ks])
    ax = sh.chart(290, 62, 70, 50)
    ax.plot(ks, tr[:, 0], color=SERIES[0], lw=1.5, label='at Q (H-link / ear)')
    ax.plot(ks, tr[:, 1], color=SERIES[1], lw=1.5, label='at R (drive / side link)')
    ax.axhline(d.BUCKET_MIN_TRANSMISSION, color=INK2, lw=0.8, ls=(0, (4, 2)))
    ax.text(1, d.BUCKET_MIN_TRANSMISSION + 1.5, f'{d.BUCKET_MIN_TRANSMISSION:.0f}° design minimum', fontsize=FS['xs'],
            color=INK2)
    ax.set_xlim(0, 60)
    ax.set_ylim(0, 95)
    ax.set_xlabel('bucket drive stroke, mm', fontsize=FS['xs'], color=INK2)
    ax.set_title('Bucket four-bar transmission angle (deg)', fontsize=FS['s'], color=INK, loc='left')
    ax.legend(fontsize=FS['xs'], frameon=False, loc='upper right')
    cp = {(a, b): g for a, b, g, _ in CHECK['closest_pairs']}
    sh.heading(16, 112, 'Stick construction')
    sh.notes(16, 107, ['Outline: the Cat 320 stick (traced). The reference tail is shortened to D (43 mm from E, see sheet 2)',
                       'and the reference bucket-cylinder lug is replaced by the F lug, set back for the 60 mm stroke.',
                       f'Head: two 5 mm plates (|Y| 11-16) inside R{d.STICK_FORK_R:.0f} of E form an open fork around the boom nose. They',
                       'carry E (Ø6) and the stick-drive rod pin D (Ø3); a bridge (|Y| < 11) ties them in front of D.',
                       'F lug: two 5 mm cheeks (|Y| 8-13) on the top face carry the bucket-drive base pin F.',
                       'Box: 32 wide, 2.5 walls, tapering to the nose boss at H (full width, ears outside it).',
                       'J boss Ø14 through the box; spacers to the side links. Prints in one piece on its side.',
                       '',
                       'Links: side links outermost (|Y| 26-30); H-link plates (|Y| 21-25) just outside the bucket',
                       'ears at Q. At R the drive eye sits between the H-link tubes (Ø7.2 boss next to the eye).',
                       f"Closest: H-link to H collar {cp.get(('h_link.plate', 'pin.H'), 0):.1f} mm, H-link tube to stick "
                       f"{cp.get(('h_link.r_tube', 'stick.box'), 0):.1f} mm."],
             size=FS['xs'], gap=3.1)
    sh.save(pdf, ROOT / 'images' / 'sheet_4.png')


# ------------------------------------------------------------------ sheet 5: bucket
def contour_points(g, tol=0.45, max_gap=14.0):
    c = np.asarray(g.simplify(tol).exterior.coords)[:-1]
    i0 = int(np.argmax(c[:, 0]))                          # start at the tip
    c = np.roll(c, -i0, axis=0)
    out = []
    for i in range(len(c)):
        a, b = c[i], c[(i + 1) % len(c)]
        out.append(a)
        n = int(np.linalg.norm(b - a) // max_gap)
        for j in range(1, n + 1):
            out.append(a + (b - a) * j / (n + 1))
    keep = [out[0]]
    for p in out[1:]:
        if np.linalg.norm(p - keep[-1]) >= 4.0:
            keep.append(p)
    return np.array(keep)


def _full_sand_boom_n():
    """Boom force per drive at the worst boom pose with a struck load of dry sand (2.5D statics)."""
    st = tuple(CHECK['worst_pose']['boom'])
    sand = d.bucket_parts()['inner'].area * (d.BUCKET_W - 4.8) / 1000.0 * 1.6 / 1000.0
    f150, f0 = d.drive_forces(st, True)[0], d.drive_forces(st, False)[0]
    return f0 + (f150 - f0) * sand / d.PAYLOAD


def sheet5(pdf):
    global FULL_SAND_BOOM_N
    FULL_SAND_BOOM_N = _full_sand_boom_n()
    sh = Sheet(5, NSHEETS, 'B06 bucket and B07 teeth', 'Rev. D4: Cat bucket of US 8,201,350 at 1:15 - open mouth, '
               'torque tube, five teeth', '1:1, detail 2:1')
    bk = d.bucket_parts()
    shell = bk['shell']
    v = View(sh, 62, 150, 1.0, label='B06 BUCKET - SIDE (bucket frame: H-T horizontal, mouth down)', label_xy=(16, 280))
    trace_overlay(v, 'bucket')
    v.poly(shell, fc=COL['bucket'], lw=0.85, z=3)
    v.poly(bk['inner'], fc='white', ec=INK2, lw=0.4, z=4)
    v.poly(bk['torque_tube'], fc=COL['struct2'], lw=0.6, z=5)
    v.poly(bk['ears'], fc=COL['struct2'], lw=0.7, z=5.5)
    v.poly(bk['torque_tube'], fc='none', ec=INK2, lw=0.45, ls=DASH, z=6.5)
    v.poly(bk['teeth'], fc=COL['steel'], lw=0.6, z=6)
    v.pin(np.zeros(2), 3, collar=5.5, z=8, label='H', lpos=(-6, 3))
    v.pin(d.Q_K, 1.5, collar=3.5, z=8, label='Q', lpos=(-6, 3))
    v.line([np.zeros(2), d.T_K], lw=0.35, color=INK2, ls=(0, (9, 2.2, 1.6, 2.2)))
    v.line([d.SUPPORT_FRONT, d.SIDE_FRONT], lw=0.35, color=INK2, ls=DASH)
    pts = contour_points(shell)
    for i, p in enumerate(pts):
        v.circle(p, 0.6, fc=INK, ec=INK, lw=0.2, z=9)
        nrm = p - np.array(shell.centroid.coords[0])
        nrm = nrm / np.linalg.norm(nrm)
        v.text(p + nrm * 3.2, str(i + 1), size=4.4, ha='center', va='center', color=INK2)
    v.dim(np.zeros(2), d.T_K, -26, mode='h', fmt='{:.2f}', prefix='tip R ')
    v.dim(np.zeros(2), d.Q_K, -16, mode='v', fmt='{:.1f}')
    ztop = shell.bounds[3]
    xtop = float(np.array(shell.exterior.coords)[np.argmax(np.array(shell.exterior.coords)[:, 1])][0])
    v.dim((xtop, 0), (xtop, ztop), 0, mode='v', fmt='{:.1f}')
    v.leader(np.array([60.3, 57.2]), 'heel R 65.7 over 30°,\nthen R 24.7 over 130°', -10, -26, size=FS['xs'], ha='left')
    v.leader(d.SUPPORT_FRONT + 26.0 * d.SUPPORT_DIR - 1.2 * d.SUPPORT_OUT, 'support plate, 20° to the floor', -20, 16,
             size=FS['xs'])
    v.leader(0.5 * (d.SUPPORT_FRONT + d.SIDE_FRONT) + np.array([0.0, 0.3]), 'mouth open from the cutting edge to the support plate',
             4, -24, size=FS['xs'])
    v.leader(np.array([-7.0, 22.0]), 'ears 4 mm, |Y| 16.5-20.5', -8, 14, size=FS['xs'])
    v.leader(np.array(bk['torque_tube'].centroid.coords[0]), 'torque tube (dashed, behind the ears), |Y| ≤ 16.5', 20, -40,
             size=FS['xs'])
    v.leader(np.array(d.T_K) + np.array([-4.0, 3.0]), 'B07 tooth + adapter on the floor-plate end', 4, -20, size=FS['xs'])
    v.text((30, -46), 'dashed blue: Cat 320 render trace (Rev. D1-D2 outline), for comparison', size=FS['xs'], color=REFC)
    # contour table
    rows = [('Pt', 'x', 'z')] + [(str(i + 1), f'{p[0]:.1f}', f'{p[1]:.1f}') for i, p in enumerate(pts)]
    half = (len(rows) + 1) // 2
    t1 = rows[:half]
    t2 = [rows[0]] + rows[half:]
    sh.heading(178, 283, 'Side plate contour')
    yb1 = sh.table(178, 279, [8, 12, 12], t1, rh=3.4, size=FS['xs'])
    yb1 = min(yb1, sh.table(212, 279, [8, 12, 12], t2, rh=3.4, size=FS['xs']))
    sh.notes(178, yb1 - 2, ['Bucket frame; fair arcs through the points',
                            '(US 8,201,350 Ex. 1 at 1:15). Front edge',
                            'straight from the support plate to the floor.',
                            f'Clear of the stick swept over the bucket',
                            f'travel by {d.BUCKET_CURL_CLEARANCE:.0f} mm.'], size=FS['xs'], gap=3.0)
    # view on the mouth (from -z), x aligned with the side view
    mv = View(sh, 62, 50, 1.0, rot=0, label='VIEW ON THE MOUTH (from below, -z)', label_xy=(16, 95))
    xs0, xs1 = shell.bounds[0], shell.bounds[2]
    mv.poly(box(xs0, -40, xs1, 40), fc=COL['bucket'], lw=0.8, z=2)
    mouth = box(float(d.SUPPORT_FRONT[0]), -37.6, float(d.SIDE_FRONT[0]), 37.6)
    mv.poly(mouth, fc='#fbf6e4', ec=INK2, lw=0.4, z=3)
    tt = bk['torque_tube'].bounds
    mv.poly(box(tt[0], -d.TORQUE_TUBE_HALF_W, tt[2], d.TORQUE_TUBE_HALF_W), fc=COL['struct2'], lw=0.5, z=4)
    eb = bk['ears'].bounds
    for sg in (1, -1):
        mv.poly(box(eb[0], min(sg * 16.5, sg * 20.5), eb[2], max(sg * 16.5, sg * 20.5)), fc=COL['struct2'], lw=0.6, z=4)
    tb = bk['teeth'].bounds
    for yc in d.TOOTH_Y:
        mv.poly(box(tb[0], yc - d.TOOTH_HALF_W, tb[2], yc + d.TOOTH_HALF_W), fc=COL['steel'], lw=0.5, z=6)
        mv.centerline((tb[0] - 4, yc), (110, yc))
    mv.centerline((-14, 0), (112, 0))
    mv.dim((xs1, -40), (xs1, 40), 22, mode='v', fmt='{:.0f}')
    mv.dim((eb[0], -16.5), (eb[0], 16.5), -5, mode='v', text='33 between ears')
    mv.dim((d.TIP_R, 16), (d.TIP_R, 32), 4, mode='v', text='16 pitch')
    mv.text((16, 30), 'mouth: open, 75.2 between the side plates', size=FS['xs'], color=INK2)
    mv.text((16, -33), 'side plates 2.4, wrapper 2.4', size=FS['xs'], color=INK2)
    # tooth detail 2:1
    tc = np.array(bk['teeth'].centroid.coords[0])
    tv = View(sh, 290, 150, 2.0, origin=tuple(tc), label='B07 TOOTH  2:1 (side, on the floor plate)', label_xy=(250, 186))
    tv.poly(bk['teeth'], fc=COL['steel'], lw=0.7, z=3)
    tb = bk['teeth'].bounds
    tv.dim((tb[0], tb[1]), (tb[2], tb[1]), -4, mode='h', fmt='{:.1f}')
    tv.dim((tb[2], tb[1]), (tb[2], tb[3]), 4, mode='v', fmt='{:.1f}')
    ce = d.cutting_edge()
    tv.poly(Polygon([ce['outer'], ce['inner'], ce['inner'] - 14 * d.FLOOR_TIP_DIR, ce['outer'] - 14 * d.FLOOR_TIP_DIR]),
            fc=COL['bucket'], ec=INK2, lw=0.4, z=2)
    tv.text((tb[0] - 2, tb[1] - 9.0), 'socket straddles the 2.4 mm floor plate', size=FS['xs'])
    tv.text((tb[0] - 2, tb[1] - 10.8), '(0.1 gap); CA glue. Shape: FIG. 1 tip + adapter', size=FS['xs'])
    # capacity table
    inner = bk['inner']
    wi = d.BUCKET_W - 2 * 2.4
    struck = inner.area * wi / 1000.0
    sand = struck * 1.6
    rows = [('Capacity (estimate)', 'value'), ('Struck (to the mouth plane)', f'{struck:.0f} cm³'),
            ('Same bucket at full size', f'{struck * d.SCALE ** 3 / 1e6:.2f} m³'),
            ('Struck load of dry sand (1.6 g/cm³)', f'{sand:.0f} g'),
            ('Rated example load', '150 g'), ('Estimated bucket mass', f"{CHECK['masses_kg']['bucket'] * 1000:.0f} g")]
    sh.table(320, 206, [62, 22], rows, rh=4.0)
    rep = d.BREF.report()
    sh.heading(254, 283, 'What the bucket is')
    sh.notes(254, 278, ['Rev. D4 copies a real bucket: Caterpillar US 8,201,350 B2,',
                        'Example 1. Its tip radius (1570 mm) is R12 at 1:15, so it is drawn',
                        'at 1:15 with H on its upper pin and T on its tooth tip.',
                        '- Wrapper: floor and cutting edge, heel R 985 over 30° and',
                        '  R 370 over 130°, then the support plate at 20° to the floor,',
                        '  back to its front end beside H (dims full size).',
                        '- Mouth open from the cutting edge to the support plate, just',
                        '  behind the H-T line. Side plates: straight front edge.',
                        '- Ears carry H and Q. A torque tube between them stiffens the',
                        '  support plate and carries the Q pin (no separate spacer).',
                        f"- Patent check: throat D {rep['throat']['D']} / D' {rep['throat']['D1']} mm "
                        f"(patent 940 / 920).",
                        '- Five teeth on adapters (FIG. 1 shape) to the tip T (R 104.67).',
                        '',
                        'Print: one part lying on a side plate, 6 perimeters + 10 % gyroid;',
                        'supports inside the cavity come out through the open mouth.',
                        'Teeth printed separately and glued on.',
                        f'At 150 g the bucket is about {150 / sand * 100:.0f} % full of dry sand. A struck load',
                        f'({sand:.0f} g) takes each boom drive to about {FULL_SAND_BOOM_N:.0f} N held (2.5D), '
                        + ('over' if FULL_SAND_BOOM_N > d.ACT['thrust_cont'] else 'just under'),
                        f"the {d.ACT['thrust_cont']:.0f} N rating: plan on the rated 150 g."], size=FS['xs'], gap=3.1)
    sh.save(pdf, ROOT / 'images' / 'sheet_5.png')


# ------------------------------------------------------------------ sheet 6: lateral layout, hardware, comparison
S, S2, G, ST, LKC = COL['struct'], COL['struct2'], COL['ghost'], COL['steel'], COL['link']
STACKS = [
    ('O', 6, [('boom root tube', -20, 20, S), ('foot plate', 20.5, 25.5, COL['base']), ('foot plate', -25.5, -20.5, COL['base']),
              ('collar', 25.8, 29.8, ST), ('collar', -29.8, -25.8, ST)], 60),
    ('A', 3, [('foot plate', 20.5, 25.5, COL['base']), ('spacer', 25.6, 30.9, G), ('drive eye', 31, 37, COL['cap']),
              ('spacer', 37.1, 42.4, G), ('outer cheek', 42.5, 47.5, '#7b838c'), ('collar', 47.8, 50.8, ST)], 30),
    ('B', 3, [('cross tube', -20, 20, S), ('pad', 20, 28.3, S2), ('pad', -28.3, -20, S2),
              ('boss', 28.3, 30.9, S2), ('boss', -30.9, -28.3, S2),
              ('eye', 31, 37, COL['rod']), ('eye', -37, -31, COL['rod']), ('collar', 37.3, 40.3, ST),
              ('collar', -40.3, -37.3, ST)], 82),
    ('C', 3, [('eye', -3, 3, COL['cap']), ('spacer', 3.1, 7.9, G), ('spacer', -7.9, -3.1, G), ('cheek', 8, 13, S2),
              ('cheek', -13, -8, S2), ('collar', 13.3, 16.3, ST), ('collar', -16.3, -13.3, ST)], 34),
    ('E', 6, [('boom nose', -10.5, 10.5, S), ('head plate', 11, 16, S2), ('head plate', -16, -11, S2),
              ('collar', 16.3, 20.3, ST), ('collar', -20.3, -16.3, ST)], 42),
    ('D', 3, [('eye', -3, 3, COL['rod']), ('spacer', 3.1, 10.9, G), ('spacer', -10.9, -3.1, G),
              ('head plate', 11, 16, S2), ('head plate', -16, -11, S2), ('collar', 16.3, 19.3, ST),
              ('collar', -19.3, -16.3, ST)], 40),
    ('F', 3, [('eye', -3, 3, COL['cap']), ('spacer', 3.1, 7.9, G), ('spacer', -7.9, -3.1, G), ('F cheek', 8, 13, S2),
              ('F cheek', -13, -8, S2), ('collar', 13.3, 16.3, ST), ('collar', -16.3, -13.3, ST)], 34),
    ('J', 3, [('stick boss', -16, 16, S), ('spacer', 16.1, 25.9, G), ('spacer', -25.9, -16.1, G),
              ('side link', 26, 30, '#8a9198'), ('side link', -30, -26, '#8a9198'), ('collar', 30.3, 33.3, ST),
              ('collar', -33.3, -30.3, ST)], 68),
    ('R', 3, [('drive eye', -3, 3, COL['rod']), ('boss', 3.1, 5.8, '#8a9198'), ('boss', -5.8, -3.1, '#8a9198'),
              ('H-link tube', 5.8, 20.9, '#8a9198'), ('H-link tube', -20.9, -5.8, '#8a9198'),
              ('H-link', 21, 25, LKC), ('H-link', -25, -21, LKC), ('spacer', 25.1, 25.9, G), ('spacer', -25.9, -25.1, G),
              ('side link', 26, 30, '#8a9198'), ('side link', -30, -26, '#8a9198'), ('collar', 30.3, 33.3, ST),
              ('collar', -33.3, -30.3, ST)], 68),
    ('Q', 3, [('torque tube', -16.5, 16.5, S2), ('ear', 16.5, 20.5, S2), ('ear', -20.5, -16.5, S2),
              ('H-link', 21, 25, LKC), ('H-link', -25, -21, LKC), ('collar', 25.3, 28.3, ST),
              ('collar', -28.3, -25.3, ST)], 58),
    ('H', 6, [('stick nose', -16, 16, S), ('ear', 16.5, 20.5, S2), ('ear', -20.5, -16.5, S2),
              ('collar', 20.8, 24.8, ST), ('collar', -24.8, -20.8, ST)], 50),
]


def sheet6(pdf):
    sh = Sheet(6, NSHEETS, 'Lateral layout, hardware, comparison', 'Pin stacks across Y, bought parts, '
               'print plan, R10 / R12, checks and open points', '1:1')
    sh.heading(16, 279, 'Pin stacks  1:1')
    y = 268
    v0 = 82
    for name, dpin, parts, plen in STACKS:
        v = View(sh, v0, y, 1.0)
        sh.text(18, y + 0.2, name, size=FS['n'], weight='bold')
        sh.text(18, y - 4.0, f'Ø{dpin} x {plen}', size=FS['xs'], color=INK2)
        hh = 3.2
        for lab, a, b, c in parts:
            v.poly(box(a, -hh, b, hh), fc=c, lw=0.4, z=3)
        lo = -plen / 2 if name != 'A' else 20.5
        hi = plen / 2 if name != 'A' else 20.5 + plen
        v.poly(box(lo, -dpin / 4 - 0.3, hi, dpin / 4 + 0.3), fc='#e9edf0', lw=0.4, z=4)
        labs = {}
        for lab, a, b, c in parts:
            if a >= 0 and lab not in labs:
                labs[lab] = (a + b) / 2
        for i, (lab, xm) in enumerate(sorted(labs.items(), key=lambda kv: kv[1])):
            v.text((xm, 3.7 + (i % 3) * 2.6), lab, size=4.2, ha='center', color=INK2)
        v.centerline((0, -5.5), (0, 5.5))
        y -= 18.6
    sh.notes(18, y + 6, ['Section along each pin axis, Y in mm, centre line = arm plane. A is the +Y side only (pin',
                         'pressed flush inside the foot plate). Grey bar = steel pin; light = printed spacers; collars',
                         'Ø11 x 4 (Ø6 pins) and Ø7 x 3 (Ø3 pins); 0.3 mm running clearance per joint. All collars are',
                         'in the clash model.'], size=FS['xs'], gap=3.0)
    # hardware
    x0 = 160
    sh.heading(x0, 283, 'Bought parts')
    rows = [('Item', 'Size', 'Qty', 'Where'),
            ('Pin, ground steel', 'Ø6 x 60', '1', 'O'), ('Pin', 'Ø6 x 42', '1', 'E'), ('Pin', 'Ø6 x 50', '1', 'H'),
            ('Pin, hardened', 'Ø3 x 30', '2', 'A (pressed in B01)'), ('Pin, hardened', 'Ø3 x 82', '1', 'B (through boom)'),
            ('Pin', 'Ø3 x 34', '2', 'C, F'), ('Pin', 'Ø3 x 40', '1', 'D'), ('Pin, hardened', 'Ø3 x 68', '2', 'J, R'),
            ('Pin', 'Ø3 x 58', '1', 'Q'),
            ('Shaft collar + set screw', 'Ø6 bore', '6', 'O, E, H'), ('Shaft collar + set screw', 'Ø3 bore', '16', 'A..Q'),
            ('Shim washer', 'Ø6/11 x 0.4', '6', 'O, E, H'), ('Screw + insert', 'M4 x 12', '4', 'B01 to turntable'),
            ('Screw (split option)', 'M3 x 45', '4', 'boom joint S'), ('Drive', 'V6-U60', '4', 'A1-A4')]
    yb = sh.table(x0, 280, [34, 18, 9, 36], rows, rh=3.7)
    sh.heading(x0, yb - 6, 'Print plan (PETG)')

    def bb(g, w):
        b = g.bounds
        return f'{b[2] - b[0]:.0f} x {b[3] - b[1]:.0f} x {w}'
    bk = d.bucket_parts()
    rows = [('Part', 'Pieces', 'Lies on', 'Outline'),
            ('B02 boom', '1', 'side plate', bb(unary_union([d.boom_profile(), d.c_bracket()]), 40)),
            ('  or split at S', '2', 'side plate', '219 + 189 long'),
            ('B03 stick', '1', 'side plate', bb(d.stick_profile()[0], 32)),
            ('B06 bucket', '1', 'side plate', bb(unary_union([bk['shell'], bk['ears'], bk['torque_tube']]), 80)),
            ('B01 bracket', '1', 'flange', '100 x 76 x 68'),
            ('B04 / B05 links', '2 + 2', 'side', f'{d.SIDE_LINK + 10:.0f} / {d.H_LINK + 10:.0f} long'),
            ('B07 teeth / B08 pads', '5 + 2', 'side / face', '{:.0f} x {:.0f} / Ø17'.format(*np.subtract(bk['teeth'].bounds[2:], bk['teeth'].bounds[:2]))),
            ('All: 6 perimeters (2.5 mm) + 10 % gyroid', '', '', '')]
    yb = sh.table(x0, yb - 9, [26, 26, 20, 25], rows, rh=3.7)
    # comparison
    x2 = 262
    sh.heading(x2, 283, 'R10 / R12')
    r10f, r10u = r10_ref.hold_forces(), r10_ref.hold_forces(0.0)
    hf, hu, m = CHECK['hold_force_per_drive_N_150g'], CHECK['hold_force_per_drive_N_unloaded'], CHECK['masses_kg']
    jr, wr = CHECK['joint_ranges_deg'], CHECK['working_ranges_mm']
    span = lambda j: f"{abs(j[1] - j[0]):.0f}"
    f10 = r10_ref.R10_FACTS
    rows = [('', 'R10', 'R12'),
            ('Geometry source', 'own', 'Cat pins + outlines'),
            ('Boom / stick / bucket mass, g', f"{f10['mass_boom'] * 1000:.0f}/{f10['mass_stick'] * 1000:.0f}/"
             f"{f10['mass_bucket'] * 1000:.0f}", f"{m['boom'] * 1000:.0f}/{m['stick'] * 1000:.0f}/{m['bucket'] * 1000:.0f}"),
            ('Hold per boom drive, 150 g / empty', f'{r10f[0]:.1f} / {r10u[0]:.1f}', f"{hf['boom']} / {hu['boom']}"),
            ('Hold, stick drive, 150 g', f'{r10f[1]:.1f}', f"{hf['stick']}"),
            ('Hold, bucket drive, 150 g', '-', f"{hf['bucket']}"),
            ('Boom / stick / bucket travel, °', '89 / 95 / 118', f"{span(jr['boom'])} / {span(jr['stick'])} / {span(jr['bucket'])}"),
            ('Depth / reach / cut height', '-', f"{wr['dig_depth']:.0f} / {wr['reach_ground']:.0f} / {wr['cut_height']:.0f}"),
            ('Boom drives', 'Y ±50, crossbar', 'Y ±34, 1 pin'),
            ('Bucket link', 'rocker + coupler', 'H-link outside ears'),
            ('Closest clash gap', '-', f"{CHECK['closest_pairs'][0][2]} mm")]
    yb = sh.table(x2, 280, [56, 38, 44], rows, rh=3.9, size=FS['xs'])
    sh.notes(x2, yb - 2, ['Same static method for both (R10: its kinematics + mass report);',
                          f"continuous rating {d.ACT['thrust_cont']:.0f} N per drive. R10 masses are CAD values, R12 estimates."],
             size=FS['xs'], gap=3.0)
    # deviations from the reference
    yb -= 12
    sh.heading(x2, yb, 'Where R12 leaves the reference')
    rows = [('Pin', 'Reference', 'R12', 'Why')]
    for kk, (nm, refp, newp, why) in d.DEVIATIONS.items():
        rows.append((kk, f'{refp[0]:.1f}, {refp[1]:.1f}', f'{newp[0]:.1f}, {newp[1]:.1f}', why.replace(' deg', '°')))
    yb = sh.table(x2, yb - 3, [8, 20, 20, 100], rows, rh=3.7, size=FS['xs'],
                  align=['left', 'right', 'right', 'left'])
    sh.notes(x2, yb - 2, ['Bucket: copy of the Cat bucket of US 8,201,350 (D4). Also rebuilt: F lug, stick tail.',
                          'All other pins, both link lengths and the outlines follow the reference.'],
             size=FS['xs'], gap=3.0)
    # checks
    yb -= 11
    sh.heading(x2, yb, 'Checks done / still open')
    cp = CHECK['closest_pairs']
    nice = lambda a: a.replace('cyl.', '').replace('.', ' ')
    sh.notes(x2, yb - 5, [f"Done: 2.5D sweep, {CHECK['poses_grid']} grid + {CHECK['poses_fine']} fine poses, >= 1.0 mm: "
                          f"{CHECK['status']}.",
                          f"  Closest: {nice(cp[0][0])} / {nice(cp[0][1])} {cp[0][2]} mm; {nice(cp[1][0])} / {nice(cp[1][1])} "
                          f"{cp[1][2]} mm;",
                          f"  {nice(cp[2][0])} / {nice(cp[2][1])} {cp[2][2]} mm. Drives with the real {d.ACT['body_board']:g} / {d.ACT['body_back']:g} body.",
                          'Done: hold forces, levers, four-bar angles, boom bending, stroke study.',
                          f"Done: 3D CAD (step/, stl/); exact mesh clash (FCL) over {CLASH['poses_grid'] + CLASH['poses_cycle']} poses: "
                          f"{CLASH['status']},",
                          f"  closest side-view gap {CLASH['closest_inplane'][0]['gap_mm']:.2f} mm. It found the Ø11 rod-eye socket",
                          '  (now cleared by the Ø7.2 bosses at B and R).',
                          f"Done: MuJoCo dig cycle, 150 g: peak boom {DYN['peak_force_N']['boom_L']:.0f} N each, stick "
                          f"{abs(DYN['peak_force_N']['stick']):.0f} N, bucket {DYN['peak_force_N']['bucket']:.0f} N.",
                          'Open: fits on the printer; cable routing (board housings as drawn on',
                          '  sheet 1); boom-pair synchronised control (0.5 mm sensor offset',
                          f"  loads one boom drive to {SYNC_BOOM_MAX_N:.0f} N); payload / strength tests. Over an",
                          f"  X1 track keep the boom above {CHECK['x1_track_limit']['stroke']:.0f} mm stroke."],
             size=FS['xs'], gap=3.0)
    kv = View(sh, 280, 76, 0.2, label='PIN KEY  1:5 (reference pose)', label_xy=(262, 122))
    draw_arm(kv, REF_POSE, pins=False)
    for nm, p in d.solve(REF_POSE)['pins'].items():
        if nm != 'T':
            kv.pin(p, 0.8, z=12, cross=False, label=nm, lpos=(1.0, 1.0))
    sh.save(pdf, ROOT / 'images' / 'sheet_6.png')


def main():
    out = ROOT / 'R12_design_drawings.pdf'
    with PdfPages(out) as pdf:
        sheet1(pdf)
        sheet2(pdf)
        sheet3(pdf)
        sheet4(pdf)
        sheet5(pdf)
        sheet6(pdf)
        info = pdf.infodict()
        info['Title'] = 'R12 excavator arm - design drawings (D1)'
        info['Subject'] = 'Six A3 sheets generated from source/r12_design.py'
    print('wrote', out)


if __name__ == '__main__':
    main()

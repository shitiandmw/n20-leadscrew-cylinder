"""R12 concept sheets (A3 x 2) -> ../R12_concept.pdf and ../images/concept_N.png

Sheet 1: the reference (Cat 320 render with traced outlines, Cat 325 patent pins) and what the
60 mm stroke allows with real lever arms.
Sheet 2: R10 (the previous arm) and R12 against the reference at the same joint angles; R12 layout,
deviations from the reference and numbers. Drawn from the current r12_design.py, so it shows the design
as detailed in R12_design_drawings.pdf.
"""
import sys
import json
import math
import itertools
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.optimize import brentq
from matplotlib.backends.backend_pdf import PdfPages
from shapely.geometry import Point, Polygon, LineString, box
from shapely.ops import unary_union
from shapely import affinity
import reference_cat as rc
import r12_design as d
from drawkit import Sheet, View, COL, INK, INK2, MUTED, FS, DASH, CENTER, polys

ROOT = rc.ROOT
import r10_ref                    # R10 (excavator_arm_dual/) for the comparison

STATUS = 'CONCEPT (APPROVED) - DETAILS IN R12_design_drawings.pdf'
NS = 2
REFCOL = '#c9ced3'
DESIGN_COL = dict(R10='#b0563a', R12='#2a78d6')

# common pose: R10 at strokes 30 / 30 / 30 (the pose of the earlier side-by-side comparison)
_st10 = r10_ref.K.solve([30, 30, 30])
_p10 = _st10['points']
POSE = (math.atan2(*(_p10['E'] - _p10['O'])[::-1]),
        math.atan2(*(_p10['H'] - _p10['E'])[::-1]) - math.atan2(*(_p10['E'] - _p10['O'])[::-1]),
        math.atan2(*(_p10['T'] - _p10['H'])[::-1]) - math.atan2(*(_p10['H'] - _p10['E'])[::-1]))


def strokes_for(mod, pose):
    """Strokes that put the R12 design module at the joint angles `pose`."""
    th, ph, gm = pose
    sb = brentq(lambda s: mod.solve((s, 30, 30))['theta'] - th, 0, 60)
    ss = brentq(lambda s: mod.solve((sb, s, 30))['phi'] - ph, 0, 60)
    sk = brentq(lambda s: mod.solve((sb, ss, s))['gamma'] - gm, 0, 60)
    return sb, ss, sk


def frames(pose, O=np.zeros(2)):
    th, ph, gm = pose
    E = O + d.rot(th) @ np.array([d.BOOM, 0.0])
    H = E + d.rot(th + ph) @ np.array([d.STICK, 0.0])
    return dict(boom=(O, th), stick=(E, th + ph), bucket=(H, th + ph + gm))


def reference_outlines(pose):
    t = rc.load_traced()
    f = frames(pose)
    return dict(boom=d.place(d._clean(Polygon(t['boom'])), *f['boom']),
                stick=d.place(Polygon(t['stick']), *f['stick']),
                bucket=d.place(Polygon(t['bucket']), *f['bucket']))


def r10_outlines():
    st, o = r10_ref.placed([30, 30, 30])
    shift = -st['points']['O']
    P = {k: v + shift for k, v in st['points'].items()}
    g = {k: affinity.translate(o[k], *shift) for k in ('boom', 'stick', 'bucket')}
    return g, P, [('A', 'B'), ('C', 'D'), ('F', 'R')]


def r12_outlines(pose):
    s = d.solve(strokes_for(d, pose))
    po, P = s['poses'], s['pins']
    sp, _ = d.stick_profile()
    g = dict(boom=d.place(unary_union([d.boom_profile(), d.c_bracket()]), *po['boom']),
             stick=d.place(sp, *po['stick']), bucket=d.place(d.bucket_profile(), *po['bucket']))
    return g, P, [('A', 'B'), ('C', 'D'), ('F', 'R')], s


def actuator_side(v, a, b, z):
    a, b = np.asarray(a, float), np.asarray(b, float)
    L = float(np.linalg.norm(b - a))
    u = (b - a) / L
    n = np.array([-u[1], u[0]])

    def rect(s0, s1, h, fc, zz):
        v.poly(Polygon([a + s0 * u + h * n, a + s1 * u + h * n, a + s1 * u - h * n, a + s0 * u - h * n]), fc=fc, lw=0.5, z=zz)
    rect(122.5, L - 9.0, 4.0, COL['rod'], z)
    rect(L - 11.0, L - 2.0, 4.5, COL['rod'], z + 0.01)
    v.poly(Point(*b).buffer(4.5, 32), fc=COL['rod'], lw=0.5, z=z + 0.02)
    v.poly(Point(*a).buffer(4.5, 32), fc=COL['cap'], lw=0.5, z=z + 0.03)
    rect(6.0, 10.0, 8.05, COL['cap'], z + 0.04)
    rect(10.0, 116.5, 8.05, COL['act'], z + 0.05)
    rect(116.5, 122.5, 8.05, COL['cap'], z + 0.06)


def draw_ref(v, pose, z=1):
    for g in reference_outlines(pose).values():
        v.poly(g, fc=REFCOL, ec='none', lw=0, z=z)


def draw_design(v, g, P, cyl, col, z=3, lw=0.9):
    for nm in ('boom', 'stick', 'bucket'):
        v.poly(g[nm], fc='none', ec=col, lw=lw, z=z)
    for a, b in cyl:
        v.line([P[a], P[b]], lw=1.6, color=col, z=z + 0.1)
    for k in ('O', 'E', 'H'):
        v.circle(P[k], 2.2, fc='white', ec=col, lw=0.6, z=z + 0.2)


def fmt2(p):
    return f'{p[0]:.1f}, {p[1]:.1f}'


# ------------------------------------------------------------------ sheet 1
def sheet1(pdf):
    sh = Sheet(1, NS, 'Reference geometry', 'Cat 320 outlines from the manufacturer render; Cat 325 pins from '
               'US 6,518,519', 'pins normalised per link', status=STATUS)
    # render with the trace
    im = np.asarray(Image.open(rc.REF / 'cat320_view_018.jpg').convert('RGB'))
    x0, x1, y0, y1 = 470, 1530, 170, 1035
    crop = im[y0:y1, x0:x1]
    W_, H_ = 172.0, 172.0 * (y1 - y0) / (x1 - x0)
    px0, py0 = 16, 275 - H_
    sh.ax.imshow(crop, extent=(px0, px0 + W_, py0, py0 + H_), zorder=2, interpolation='bilinear')
    k = W_ / (x1 - x0)
    tr = rc.load_traced()
    P = rc.RENDER_PX
    to_paper = lambda q: (px0 + (q[0] - x0) * k, py0 + H_ - (q[1] - y0) * k)
    for part, (a, b, L) in dict(boom=('O', 'E', rc.BOOM), stick=('E', 'Hs', rc.STICK), bucket=('Hb', 'T', rc.TIP_R)).items():
        loc = np.asarray(tr[part])
        pa, pb = np.array([P[a][0], -P[a][1]]), np.array([P[b][0], -P[b][1]])
        u = (pb - pa) / np.linalg.norm(pb - pa)
        n = np.array([-u[1], u[0]])
        s = np.linalg.norm(pb - pa) / L
        pix = pa + s * (loc[:, :1] * u + loc[:, 1:] * n)
        pp = np.array([to_paper((q[0], -q[1])) for q in pix])
        sh.ax.plot(pp[:, 0], pp[:, 1], color=dict(boom='#2a78d6', stick='#eb6834', bucket='#1baf7a')[part], lw=0.8, zorder=4)
    for nm in ('O', 'B', 'E', 'D', 'J', 'R', 'Hs', 'Hb', 'T'):
        q = to_paper(P[nm])
        sh.ax.plot(*q, marker='+', color='#d01c1c', ms=5, mew=0.8, zorder=5)
        sh.ax.text(q[0] + 1.2, q[1] + 1.0, nm, fontsize=FS['xs'], color='#d01c1c', weight='bold', zorder=5)
    sh.text(16, 278, 'CAT 320 SIDE RENDER (manufacturer image) WITH THE TRACED OUTLINES AND PINS', size=FS['n'] + 0.4, weight='bold')
    sh.notes(16, py0 - 2, [
        'Outlines: yellow-paint mask, cleaned, split into boom / stick / bucket and expressed in link frames',
        '(boom O-E = 380, stick E-H = 193.33, bucket hinge-tip = 104.67: Cat 320 at 1:15).',
        'Hs = stick-end pin (carries a quick coupler in this render); Hb = the bucket\'s own hinge under it.',
        'Slight perspective: the far side shifts toward the image centre (see the fanned teeth), so the trace',
        'is a proportion reference, not plate-edge data. Image (c) Caterpillar, used as reference only.'],
        size=FS['xs'], gap=3.0)
    # patent table image
    tab = np.asarray(Image.open(rc.REF / 'US6518519_fig4_table1.png').convert('L'))[530:2010, 380:1960]
    tw = 74.0
    th_ = tw * tab.shape[0] / tab.shape[1]
    sh.ax.imshow(tab, cmap='gray', extent=(16, 16 + tw, 40, 40 + th_), zorder=2, vmin=0, vmax=255)
    sh.ax.add_patch(__import__('matplotlib.patches', fromlist=['Rectangle']).Rectangle((16, 40), tw, th_, fill=False, lw=0.4, ec=MUTED, zorder=3))
    sh.notes(94, 40 + th_, ['US 6,518,519 B1 (Caterpillar, 2003),', 'FIG. 4, Table 1: mechanism', 'parameters of a Cat 325.',
                            '', 'Boom 6.15 m, stick 3.2 m.', 'Cat 320: 5.7 m and 2.9 m,', 'same proportions within 3 %.',
                            '', 'Each link is scaled to', 'its own Cat 320 length:', 'boom x 0.0618, stick x 0.0604.',
                            '', 'O-x is the turntable deck,', 'boom t / stick v / bucket q', 'point to the upper / outer',
                            '/ back side.'], size=FS['xs'], gap=3.0)
    # pin comparison table
    k10 = r10_ref.K
    rp = rc.REF_PINS
    trp = rc.load_traced()['meta']['render_pins_in_frames']
    a10 = np.array(k10.GROUND_CYL) - np.array(k10.ORIGIN)
    rows = [('Pin (frame)', 'Cat 325 patent', 'Cat 320 render', 'R10', 'R12'),
            ('A boom-cyl base (O)', fmt2(rp['A_world']), 'hidden', fmt2(a10), fmt2(d.A_W)),
            ('B boom-cyl rod (boom)', fmt2(rp['B_boom']), fmt2(trp['B_boom']), fmt2(k10.BOOM_LIFT), fmt2(d.B_B)),
            ('C stick-cyl base (boom)', fmt2(rp['C_boom']), 'hidden', fmt2(k10.STICK_CYL), fmt2(d.C_B)),
            ('D stick tail (stick)', fmt2(rp['D_stick']), fmt2(trp['D_stick']), fmt2(k10.STICK_TAIL), fmt2(d.D_S)),
            ('  tail length |ED|', f"{np.linalg.norm(rp['D_stick']):.1f}", f"{np.linalg.norm(trp['D_stick']):.1f}",
             f"{np.linalg.norm(k10.STICK_TAIL):.1f}", f"{np.linalg.norm(d.D_S):.1f}"),
            ('F bucket-cyl base (stick)', fmt2(rp['F_stick']), 'approx. 23, 37', fmt2(k10.BUCKET_CYL), fmt2(d.F_S)),
            ('J side-link pivot (stick)', fmt2(rp['J_stick']), fmt2(trp['J_stick']), fmt2(k10.ROCKER_PIVOT), fmt2(d.J_S)),
            ('side link / H-link', f"{rc.REF_LINKS['side_link']:.1f} / {rc.REF_LINKS['h_link']:.1f}", '40.1 / 38.2',
             f'{k10.ROCKER:.1f} / {k10.COUPLER:.1f}', f'{d.SIDE_LINK:.1f} / {d.H_LINK:.1f}'),
            ('Q link pin on bucket, angle', f"{rp['Q_bucket'][1]:.1f} at 90°", 'coupler', '-', f'{d.EAR:.1f} at 90°')]
    sh.heading(214, 280, 'Pins normalised to Cat 320 at 1:15 (mm)')
    yb = sh.table(214, 277, [46, 36, 36, 36, 36], rows, rh=4.2, align=['left'] + ['right'] * 4, size=FS['xs'] + 0.3)
    sh.notes(214, yb - 2, ['Patent and render agree within ~2 mm on B and J and on both link lengths, so the render outlines can be',
                          'used in the patent frames.'],
             size=FS['xs'], gap=3.0)
    # what the U60 allows with real levers
    sh.heading(214, yb - 16, 'Real lever arms with a 60 mm stroke')
    rows = [('Joint', 'pin distance needed', 'U60 140-200 covers', 'travel', 'real machine'),
            ('Boom (B, A as patent)', '119 at -50°, 216 at +70°', '-21.6 .. +44.5°', '66°', 'about 100-115°'),
            ('Stick (D, C as patent)', '128 at -20°, 230 at -160°', '-40 .. -107°', '67°', 'about 110-130°'),
            ('Bucket (F as patent)', '103 .. 176 over 195°', 'too long for F', '-', 'about 175°')]
    yb2 = sh.table(214, yb - 19, [40, 40, 34, 18, 34], rows, rh=4.2, align=['left'] + ['right'] * 4, size=FS['xs'] + 0.3)
    sh.notes(214, yb2 - 2, [
        'At this scale the real cylinders would need about 85-95 mm of stroke and close to about 115-120 mm;',
        'the U60 has 60 mm and closes to 140 mm. Two ways out: (1) keep every real lever and accept ~66° boom and',
        'stick travel (working range shrinks by about a third), or (2) keep the real outlines and visible pins and',
        'move only the hidden or minor pins (boom-cylinder base, stick tail, bucket-cylinder base) to buy the',
        'range back with slightly shorter levers. R12 takes (2); sheet 2 shows the result.'], size=FS['xs'], gap=3.0)
    sh.save(pdf, ROOT / 'images' / 'concept_1.png')


# ------------------------------------------------------------------ sheet 2
def sheet2(pdf, results):
    sh = Sheet(2, NS, 'R12 concept', 'Real outlines and pins; three cylinder pins moved for the U60', '1:5 (comparison), 1:3 (layout)', status=STATUS)
    pose = POSE
    g10, P10, c10 = r10_outlines()
    g12, P12, c12, s12 = r12_outlines(pose)
    k = 0.2
    titles = [('R10 (previous arm)', g10, P10, c10, 'R10'), ('R12', g12, P12, c12, 'R12')]
    for i, (t, g, P, c, key) in enumerate(titles):
        x0 = 30 + i * 132
        v = View(sh, x0, 210, k, label=f'{t} over the Cat reference', label_xy=(x0 - 14, 280))
        draw_ref(v, pose)
        draw_design(v, g, P, c, DESIGN_COL[key])
        v.line([(-60, d.TURNTABLE_Z), (60, d.TURNTABLE_Z)], lw=0.4, color=INK2, ls=DASH)
    sh.text(16, 186, f'Same joint angles for all: boom {math.degrees(pose[0]):+.0f}°, stick {math.degrees(pose[1]):+.0f}° '
            f'to the boom, bucket tip line {math.degrees(pose[2]):+.0f}° to the stick (R10 at strokes 30/30/30). '
            'Grey: Cat 320 outlines at 1:15. Lines: drive axes.', size=FS['xs'], color=INK2)
    # R12 layout
    v = View(sh, 70, 100, 0.3, label='R12 LAYOUT AT THE SAME POSE  1:3.33', label_xy=(16, 178))
    sp, _ = d.stick_profile()
    po = s12['poses']
    P = s12['pins']
    v.poly(d.place(d.bucket_profile(), *po['bucket']), fc=COL['bucket'], lw=0.6, z=4)
    v.poly(d.place(sp, *po['stick']), fc=COL['struct'], lw=0.6, z=3)
    v.poly(d.place(unary_union([d.boom_profile(), d.c_bracket()]), *po['boom']), fc=COL['struct'], lw=0.6, z=5)
    foot = unary_union([Polygon([(-36, d.TURNTABLE_Z), (d.A_W[0] + 12, d.TURNTABLE_Z), (d.A_W[0] + 9, d.A_W[1] + 4),
                                 (14, 2), (-12, 6)]), d.disc(d.A_W, 6.5), d.disc(np.zeros(2), 14.5)])
    v.poly(foot, fc=COL['base'], lw=0.6, z=2)
    lk = d.link_parts()
    v.poly(d.place(lk['side'], *po['side_link']), fc=COL['link'], lw=0.5, z=6.5)
    v.poly(d.place(lk['h'], *po['h_link']), fc=COL['link'], lw=0.5, z=6.6)
    actuator_side(v, P['A'], P['B'], 6)
    actuator_side(v, P['C'], P['D'], 7)
    actuator_side(v, P['F'], P['R'], 7.2)
    for nm, p in P.items():
        if nm == 'T':
            continue
        v.pin(p, 3.0 if nm in 'OEH' else 1.5, collar=None, z=9, cross=False, label=nm, lpos=(1.6, 1.4))
    v.line([(-90, d.TURNTABLE_Z), (60, d.TURNTABLE_Z)], lw=0.5, color=INK2, ls=DASH, z=1)
    v.text((-88, d.TURNTABLE_Z + 2), 'turntable face', size=FS['xs'], color=INK2)
    # deviations
    x2 = 214
    sh.heading(x2, 178, 'Where R12 leaves the reference, and why')
    rows = [('Pin', 'reference', 'R12', 'moved', 'reason')]
    for key, (name, ref, new, why) in d.DEVIATIONS.items():
        rows.append((f'{key} {name.split(" (")[0]}', fmt2(ref), fmt2(new), f'{np.linalg.norm(new - ref):.1f}', why))
    yb = sh.table(x2, 175, [40, 22, 22, 13, 102], rows, rh=4.2, align=['left', 'right', 'right', 'right', 'left'],
                  size=FS['xs'] + 0.3)
    sh.notes(x2, yb - 2, ['Unchanged from the reference: O, E, H, B (boom-cylinder rod), J (side-link pivot), both link',
                          'lengths, Q, and the boom / stick / bucket outlines (traced, cleaned of pipes and hoses).'],
             size=FS['xs'], gap=3.0)
    # numbers
    r = results
    rows = [('', 'R10', 'R12'),
            ('Boom / stick / bucket travel', '89 / 95 / 118°',
             ' / '.join(f'{abs(b - a):.0f}' for a, b in r['ranges']) + '°'),
            ('Hold per drive, 150 g (boom / stick / bucket)', '69.9 / 39.2 / - N',
             ' / '.join(f'{x:.1f}' for x in r['hold150']) + ' N'),
            ('Same, empty', '57.6 / 25.2 / - N',
             ' / '.join(f'{x:.1f}' for x in r['hold0']) + ' N'),
            ('Min. lever (boom / stick / bucket)', '-', ' / '.join(f'{x:.1f}' for x in r['lever']) + ' mm'),
            ('Dig depth / reach at ground / cut height', '-',
             f"{r['working']['dig_depth']:.0f} / {r['working']['reach_ground']:.0f} / {r['working']['cut_height']:.0f}"),
            ('Boom / stick / bucket mass (estimate)', '581 / 207 / 159 g',
             ' / '.join(f'{x:.0f}' for x in r['mass']) + ' g'),
            ('Closest side-view gap (concept check)', '-', f"{r['gap']:.1f} mm")]
    sh.heading(x2, yb - 12, 'Numbers (same static method for both)')
    yb = sh.table(x2, yb - 15, [72, 50, 76], rows, rh=4.2, align=['left', 'right', 'right'], size=FS['xs'] + 0.3)
    sh.notes(x2, yb - 2, ['Hold = worst static thrust per drive over the stroke grid, gravity only; rating 51 N continuous.',
                          'R10 masses are its CAD values; R12 masses are PETG estimates.',
                          'Working range on the X1 crawler (boom-foot pin 155 above ground).'], size=FS['xs'], gap=3.0)
    sh.heading(x2, yb - 15, 'Open at concept stage, closed in the detailed drawings')
    sh.notes(x2, yb - 20, ['- Lateral layout (pin stacks, link plates): drawing sheet 6, checked in 3D (cad/clash_check.json).',
                           '- Outlines redrawn as arcs and lines: drawing sheets 3-5.',
                           '- Bucket: Rev. D4 copies the Caterpillar bucket of US 8,201,350 (drawing sheet 5).'],
             size=FS['xs'], gap=3.0)
    sh.save(pdf, ROOT / 'images' / 'concept_2.png')


def evaluate():
    import check_concept
    g = np.linspace(0, 60, 7)
    hf, hu, lev = [0.0] * 3, [0.0] * 3, [1e9] * 3
    for st in itertools.product(g, repeat=3):
        f, f0, m = d.drive_forces(st), d.drive_forces(st, payload=False), d.moment_arms(st)
        hf = [max(a, abs(b)) for a, b in zip(hf, f)]
        hu = [max(a, abs(b)) for a, b in zip(hu, f0)]
        lev = [min(a, b) for a, b in zip(lev, m)]
    j0, j1 = d.solve((0, 0, 0)), d.solve((60, 60, 60))
    ranges = [(math.degrees(j0[k]), math.degrees(j1[k])) for k in ('theta', 'phi', 'gamma')]
    gaps = check_concept.check()
    res = dict(hold150=hf, hold0=hu, lever=lev, ranges=ranges,
               working=d.working_ranges(d.envelope(19, 25)),
               mass=[d.MASS[k][0] * 1000 for k in ('boom', 'stick', 'bucket')],
               gap=min(v[0] for v in gaps.values()), gaps={k: v for k, v in gaps.items()},
               pins=dict(A=d.A_W, B=d.B_B, C=d.C_B, D=d.D_S, F=d.F_S, J=d.J_S, Q=d.Q_K))
    out = {k: (v if not isinstance(v, (list, tuple, dict)) else v) for k, v in res.items()}
    (ROOT / 'concept_check.json').write_text(json.dumps(out, indent=1, default=lambda o: np.round(o, 2).tolist()))
    return res


def main():
    res = evaluate()
    out = ROOT / 'R12_concept.pdf'
    with PdfPages(out) as pdf:
        sheet1(pdf)
        sheet2(pdf, res)
        pdf.infodict()['Title'] = 'R12 excavator arm - concept (reference-based geometry)'
    print('wrote', out)


if __name__ == '__main__':
    main()

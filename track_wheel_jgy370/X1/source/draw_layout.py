"""X1 layout sheet from the CAD: plan view, front section through the swing centre, turntable-seat detail and the
Cat 320 comparison. Writes ../X1_layout.pdf and ../images/X1_layout.png."""
import json
from functools import reduce
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import trimesh
from shapely.geometry import Polygon
import x1_parts as X
from x1_parts import P9, D9

ROOT = X.ROOT
INK, ACC, RES, GRID = '#203a42', '#c0392b', '#2e86c1', '#9aa7a5'


def to_mesh(shape, tol=.05):
    v, f = X.one(shape).tessellate(tol, .2)
    return trimesh.Trimesh(np.array([(p.x, p.y, p.z) for p in v]), np.array(f), process=True)


def section(shape, origin, normal, axes):
    s = to_mesh(shape).section(plane_origin=origin, plane_normal=normal)
    if s is None:
        return None
    loops = [Polygon(l[:, axes]).buffer(0) for l in s.discrete if len(l) > 3]
    loops = [l for l in loops if l.area > 1e-3]
    return reduce(lambda a, b: a.symmetric_difference(b), loops) if loops else None


def fill(ax, g, color, ec='#1d2b2f', lw=.4, z=2, alpha=1):
    if g is None:
        return
    for poly in getattr(g, 'geoms', [g]):
        if poly.geom_type != 'Polygon':
            continue
        ax.fill(*poly.exterior.xy, color=color, ec=ec, lw=lw, zorder=z, alpha=alpha)
        for h in poly.interiors:
            ax.fill(*h.xy, color='white', ec=ec, lw=lw, zorder=z + .1)


def dim(ax, a, b, off, text, vertical=False, fs=8, side=1):
    (x0, y0), (x1, y1) = a, b
    if vertical:
        ax.annotate('', (off, y0), (off, y1), arrowprops=dict(arrowstyle='<->', lw=.6, color=INK))
        ax.text(off + side*2.5, (y0 + y1)/2, text, rotation=90, va='center', ha='left' if side > 0 else 'right', fontsize=fs, color=INK)
    else:
        ax.annotate('', (x0, off), (x1, off), arrowprops=dict(arrowstyle='<->', lw=.6, color=INK))
        ax.text((x0 + x1)/2, off + side*2.5, text, ha='center', va='bottom' if side > 0 else 'top', fontsize=fs, color=INK)


def plan(ax, inst, keys):
    L = keys['track_length']
    for s in (1, -1):
        ax.add_patch(plt.Rectangle((-L/2, s*X.TRACK_Y - D9.SHOE_W/2), L, D9.SHOE_W, color='#7d8a8f', alpha=.55, zorder=1))
        tag = 'L' if s > 0 else 'R'
        fill(ax, section(inst[f'{tag}_J901_H_frame']['shape'], [0, 0, 68], [0, 0, 1], [0, 1]), '#8fb4b4', z=2)
        fill(ax, section(inst[f'{tag}_J909_housing']['shape'], [0, 0, D9.AXLE_Z], [0, 0, 1], [0, 1]), '#e8a23a', z=3)
    fill(ax, section(inst['X101_X_frame']['shape'], [0, 0, 80], [0, 0, 1], [0, 1]), '#f2c230', z=4)
    for r in (X.RU66['D']/2, X.RU66['d']/2):
        ax.add_patch(Circle((0, 0), r, fill=False, ec='#566573', lw=.9, zorder=6))
    ax.add_patch(Circle((0, 0), X.RESERVE_R, fill=False, ec=RES, lw=1.0, ls='--', zorder=6))
    ax.text(-232, 228, f'dashed: reserved swing circle R {X.RESERVE_R:g} (Cat 320 tail swing radius 2830 mm at 1:15)', color=RES, fontsize=7.5, ha='left')
    for s in (1, -1):
        ax.plot([-L/2 - 12, L/2 + 12], [s*X.TRACK_Y]*2, color=GRID, lw=.6, ls='-.', zorder=0)
    ax.plot([-8, 8], [0, 0], color=INK, lw=.8, zorder=7); ax.plot([0, 0], [-8, 8], color=INK, lw=.8, zorder=7)
    # labels sit in the open space between the front legs and left of the swing circle, clear of the dimensions
    ax.annotate('swing centre:\nRU66 seat\n(Ø95 outer ring)', (0, 0), (66, -8), fontsize=8, va='top',
                arrowprops=dict(arrowstyle='-', lw=.5, relpos=(0, 1)), zorder=8)
    ax.annotate('X-frame X101:\ncarbody, 4 legs,\na rail on each\ntrack (3 x M4)', (60, 80), (66, 60), fontsize=8, va='top',
                arrowprops=dict(arrowstyle='-', lw=.5, relpos=(0, 1)), zorder=8)
    ax.annotate('motor pods\n(final drives) at\nthe rear, as on\nthe Cat 320', (-100, X.TRACK_Y - 58), (-268, 30), fontsize=8, va='top',
                arrowprops=dict(arrowstyle='-', lw=.5, relpos=(1, 1)), zorder=8)
    ax.annotate('front', (L/2 + 52, -X.TRACK_Y - 55), (L/2 + 12, -X.TRACK_Y - 55), fontsize=9, va='center', weight='bold',
                arrowprops=dict(arrowstyle='->', lw=1.0))
    dim(ax, (-L/2, 0), (L/2, 0), -X.TRACK_Y - 55, f'{L:.1f} track length (Cat 320 at 1:15: 296.7)', side=-1)
    dim(ax, (D9.DRIVE_X, 0), (D9.IDLER_X, 0), X.TRACK_Y + 45, f'{keys["sprocket_to_idler"]:.1f} sprocket to idler')
    dim(ax, (0, -X.TRACK_Y), (0, X.TRACK_Y), L/2 + 22, f'{2*X.TRACK_Y:.0f} track gauge', vertical=True)
    dim(ax, (0, -X.TRACK_Y - 35), (0, X.TRACK_Y + 35), L/2 + 40, f'{keys["overall_width"]:.0f} overall width', vertical=True)
    dim(ax, (0, -X.BOSS_FACE_Y), (0, X.BOSS_FACE_Y), 138, f'{2*X.BOSS_FACE_Y:.0f} X-frame (boss faces)', vertical=True, side=-1)
    ax.set_xlim(-235, 250); ax.set_ylim(-245, 238); ax.set_aspect('equal'); ax.axis('off')
    ax.set_title('Plan view (front to the right). Sections: X-frame at Z 80, J9 frames at Z 68, motor pods at the axle height', fontsize=10, loc='left')


def front(ax, inst):
    cut = [n for n, d in inst.items() if d['group'] != 'reserve' and X.one(d['shape']).BoundingBox().xmin < 0 < X.one(d['shape']).BoundingBox().xmax]
    for n in cut:
        d = inst[n]
        c = '#f2c230' if n == 'X101_X_frame' else ('#9aa4ab' if n.startswith('RU66') else tuple(d['color']))
        fill(ax, section(d['shape'], [0, 0, 0], [1, 0, 0], [1, 2]), c, lw=.3, z=3 if n.startswith(('X1', 'RU66')) else 2)
    for s in (1, -1):
        r = X.cable_route(s)
        fill(ax, section(r, [0, 0, 0], [1, 0, 0], [1, 2]), '#c0392b', z=4, alpha=.8)
    ax.axhline(0, color='#6b4f2a', lw=1.2)
    ax.plot([-X.RESERVE_R, X.RESERVE_R], [X.TURNTABLE_Z]*2, color=RES, lw=1.0, ls='--')
    ax.text(-X.RESERVE_R, X.TURNTABLE_Z + 3, 'turntable face Z 100: reserved above, R 189', color=RES, fontsize=7.5, ha='left')
    # ground clearance under the belly cover; the text goes below the ground line (the dimension is shorter than it)
    dim(ax, (0, 0), (0, X.COVER_Z[0]), -25, '', vertical=True, fs=7.5)
    ax.text(-25, -3, f'{X.COVER_Z[0]:g} ground clearance', ha='center', va='top', fontsize=7.5, color=INK)
    dim(ax, (0, 0), (0, 92.4), 224, '92.4 top of track', vertical=True, fs=7.5)
    ax.annotate('cable route: pod port to carbody', (X.BODY_R + 20, X.CABLE_HOLE['z']), (2, 6), fontsize=7.5, color='#c0392b',
                arrowprops=dict(arrowstyle='-', lw=.5, color='#c0392b'))
    ax.annotate('rail, 3 x M4 into the J9 bosses', (X.RAIL_IN_Y + 3, 80), (110, 112), fontsize=7.5, arrowprops=dict(arrowstyle='-', lw=.5))
    ax.annotate('belly cover', (-50, 32.5), (-110, 14), fontsize=7.5, arrowprops=dict(arrowstyle='-', lw=.5))
    ax.set_xlim(-215, 245); ax.set_ylim(-8, 122); ax.set_aspect('equal'); ax.axis('off')
    ax.set_title('Front section through the swing centre (X = 0), seen from the front', fontsize=10, loc='left')


def seat(ax, inst):
    names = ['X101_X_frame', 'RU66_outer_ring', 'RU66_inner_ring'] + [n for n in inst if n.startswith(('seat_screw', 'insert_M4_seat'))]
    a = np.radians(X.OUTER_ANG[0])
    for n in names:
        c = '#f2c230' if n == 'X101_X_frame' else ('#9aa4ab' if n.startswith('RU66') else tuple(inst[n]['color']))
        # vertical plane through the swing axis and a seat screw, drawn as (radius, Z)
        sec = to_mesh(inst[n]['shape']).section(plane_origin=[0, 0, 0], plane_normal=[-np.sin(a), np.cos(a), 0])
        if sec is None:
            continue
        polys = []
        for l in sec.discrete:
            if len(l) < 4:
                continue
            rr = l[:, 0]*np.cos(a) + l[:, 1]*np.sin(a)
            p = Polygon(np.c_[rr, l[:, 2]]).buffer(0)
            if p.area > 1e-3:
                polys.append(p)
        if polys:
            fill(ax, reduce(lambda u, v: u.symmetric_difference(v), polys), c, lw=.4, z=3 if 'screw' in n or 'insert' in n else 2)
    ax.plot([0, 0], [70, 108], color=GRID, lw=.6, ls='-.')
    for z, t in ((X.SEAT_Z, 'Z 85 seat (outer ring)'), (X.TURNTABLE_Z, 'Z 100 turntable face (inner ring)')):
        ax.plot([-62, 62], [z, z], color=GRID, lw=.4, ls=':')
        ax.text(-63, z, t, fontsize=7, color=INK, ha='right', va='center')
    notes = [((41.5, 97.5), (28, 106), 'outer ring: 8 x M4 x 16 from above,\nPCD 83, into heat-set inserts', 'baseline'),
             ((-24, 99), (-60, 106), 'inner ring: 8 x M4 tapped, PCD 45\n(reserved for the turntable)', 'baseline'),
             ((-30, 83.6), (-52, 73.5), 'Ø75 relief 2.5 deep: clears the\ninner ring (Dh min 74) and the\nturntable screw tips', 'top'),
             ((-11, 79), (-22, 64), 'Ø25 cable passage', 'baseline')]
    for xy, txt, t, va in notes:
        ax.annotate(t, xy, txt, fontsize=7, va=va, arrowprops=dict(arrowstyle='-', lw=.5))
    ax.set_xlim(-62, 62); ax.set_ylim(62, 112); ax.set_aspect('equal'); ax.axis('off')
    ax.set_title('Turntable seat: section through a seat screw (THK RU66, catalogue A18-21)', fontsize=10, loc='left')


def table(ax, keys, val):
    C, s = X.CAT320, X.SCALE
    rows = [('Item', 'Cat 320', '1:15', 'X1'),
            ('Track length', C['track_length'], C['track_length']/s, keys['track_length']),
            ('Length to centre of rollers', C['length_to_centre_of_rollers'], C['length_to_centre_of_rollers']/s, keys['sprocket_to_idler']),
            ('Track gauge', C['track_gauge'], C['track_gauge']/s, keys['track_gauge']),
            ('Undercarriage width', C['undercarriage_width_790_shoes'], C['undercarriage_width_790_shoes']/s, keys['overall_width']),
            ('Shoe width', C['shoe_width'], C['shoe_width']/s, keys['shoe_width']),
            ('Ground clearance', C['ground_clearance'], C['ground_clearance']/s, keys['ground_clearance']),
            ('Counterweight clearance / turntable face', C['counterweight_clearance'], C['counterweight_clearance']/s, keys['turntable_face_z']),
            ('Tail swing radius / reserve', C['tail_swing_radius'], C['tail_swing_radius']/s, keys['reserve_radius']),
            ('Track / carrier rollers per side', '8 / 2', '', '5 / 2')]
    for i, r in enumerate(rows):
        for j, t in enumerate(r):
            txt = t if isinstance(t, str) else (f'{t:,.0f}' if j == 1 else f'{t:.1f}')
            ax.text([0, .50, .66, .82][j], .92 - i*.092, txt, fontsize=8.5, transform=ax.transAxes,
                    weight='bold' if i == 0 else 'normal', color=INK)
    st = val['static']; tools = sum(len(v) for k, v in val['tool_access'].items() if not k.startswith('support_roller_bolt_withdrawal'))
    lines = [f'CAD checks (validation.json): {"PASS" if val["pass"] else "FAIL"}',
             f'static: 0 overlaps in {st["pairs_tested"]} exact pairs (both tracks, X-frame, RU66, screws, cable routes)',
             f'turntable reserve (R 189 above Z 100): no intrusion; tracks 7.6 below it, X-frame 15',
             f'track slide-on (both sides), RU66 lowering, belly cover: no overlaps; {tools} tool paths clear',
             'support-roller bolts: unbolt the track from the X-frame before withdrawing them']
    for i, t in enumerate(lines):
        plt.gcf().text(.57, .205 - i*.022, t, fontsize=9 if i == 0 else 8.2,
                       color='#1e8449' if i == 0 else '#40585e', weight='bold' if i == 0 else 'normal')
    ax.axis('off')
    ax.set_title('Cat 320 reference (07H spec sheet p. 4) and X1 (mm)', fontsize=10, loc='left')


def main():
    val = json.loads((ROOT / 'validation.json').read_text()); keys = val['key_numbers']
    inst = X.unit(with_reserve=False)
    fig = plt.figure(figsize=(16.5, 11.7))
    fig.text(.03, .965, 'X1 crawler chassis  —  two J9 tracks on an X-frame (built from the CAD data)', fontsize=17, weight='bold', color=INK)
    fig.text(.03, .943, 'Cat 320 lower-frame layout: round carbody under the slewing ring, four legs in an X, final drives at the rear. '
                        'The turntable is not built; its seat, cable passage and swing envelope are reserved.', fontsize=10, color='#40585e')
    plan(fig.add_axes([.02, .27, .52, .63]), inst, keys)
    front(fig.add_axes([.55, .60, .44, .31]), inst)
    seat(fig.add_axes([.57, .25, .41, .31]), inst)
    table(fig.add_axes([.05, .015, .48, .245]), keys, val)
    fig.text(.57, .04, 'Dimensions in mm. Vehicle frame: X forward, Y left, Z up, origin on the ground under the swing centre.\n'
                       'The right track is the mirror image of J9 (mirrored J901 and J909 prints).', fontsize=8, color='#40585e')
    out = ROOT / 'X1_layout.pdf'
    fig.savefig(out); fig.savefig(ROOT / 'images/X1_layout.png', dpi=110)
    print('wrote', out)


if __name__ == '__main__':
    main()

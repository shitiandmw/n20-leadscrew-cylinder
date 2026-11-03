"""J9 layout sheet from the CAD layout data: outboard side view, flat-ground detail, top-run detail."""
import math, sys, json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon as MPoly
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import j9_design as D
from j9_parts import wall_profile, ROLLERS, pod_outer, one
import trimesh
from shapely.geometry import LineString

ROOT = HERE.parent
INK, FRAME, CHAIN, ACC, OLD = '#203a42', '#9cc3c3', '#59656b', '#c0392b', '#c98a2b'


def chain_outline(ax, lw=1.0):
    p = np.vstack([D.PINS, D.PINS[:1]])
    ax.plot(p[:, 0], p[:, 1], '-', color=CHAIN, lw=lw, zorder=4)
    ax.plot(D.PINS[:, 0], D.PINS[:, 1], 'o', ms=2.6, color=INK, zorder=5)
    outer = LineString(p).buffer(D.SHOE_OUT, join_style=2, single_sided=False).exterior
    ax.plot(*outer.xy, '-', color='#b9c1c4', lw=.8, zorder=1)


def pod_outline(ax):
    """Outline of the housing's motor pod, cut from the CAD at Y -40 (where its sides are straight)."""
    v, f = one(pod_outer(D.SKIRT_Y[1])).tessellate(.05, .2)
    m = trimesh.Trimesh(np.array([(q.x, q.y, q.z) for q in v]), np.array(f))
    for l in m.section(plane_origin=[0, -40, 0], plane_normal=[0, 1, 0]).discrete:
        ax.plot(l[:, 0], l[:, 2], '--', color=OLD, lw=1.0, zorder=7)


def wheels(ax):
    for x, z, g in ROLLERS:
        ax.add_patch(Circle((x, z), D.FLANGE_R, fc='#d9dee0', ec=INK, lw=.6, zorder=3))
        ax.add_patch(Circle((x, z), D.ROLLER_R, fc='#808b90', ec=INK, lw=.6, zorder=3))
        ax.add_patch(Circle((x, z), 2, fc='k', zorder=3))
    ax.add_patch(Circle((D.DRIVE_X, D.AXLE_Z), D.SPROCKET_TIP_R, fc='#7d878c', ec=INK, lw=.6, zorder=2))
    ax.add_patch(Circle((D.DRIVE_X, D.AXLE_Z), D.PITCH_R, fill=False, ec='w', lw=.6, ls='--', zorder=2))
    ax.add_patch(Circle((D.IDLER_X, D.AXLE_Z), D.IDLER_R, fc='#7d878c', ec=INK, lw=.6, zorder=2))
    for c in ((D.DRIVE_X, D.AXLE_Z), (D.IDLER_X, D.AXLE_Z)):
        ax.add_patch(Circle(c, 4, fc='k', zorder=3))


def frame(ax):
    prof = wall_profile()
    ax.add_patch(MPoly(np.array(prof.exterior.coords), closed=True, fc=FRAME, ec=INK, lw=.7, alpha=.55, zorder=1.5))
    ax.add_patch(MPoly([(D.WEB_X[0], D.WEB_Z[0]), (D.WEB_X[1], D.WEB_Z[0]), (D.WEB_X[1], D.WEB_Z[1]), (D.WEB_X[0], D.WEB_Z[1])],
                       closed=True, fill=False, ec=INK, ls='--', lw=.6, zorder=2))
    s0, s1 = D.SPRING_X0, D.SPRING_X0 + D.SPRING_SET
    xs = np.linspace(s0, s1, 40); ax.plot(xs, D.AXLE_Z + 7*np.sin((xs - s0)/(s1 - s0)*2*math.pi*7), color='#666', lw=.6, zorder=2)
    y0, y1 = D.YOKE_BASE_X
    ax.add_patch(MPoly([(y0, D.AXLE_Z - 8), (D.YOKE_ARM_END, D.AXLE_Z - 8), (D.YOKE_ARM_END, D.AXLE_Z + 8), (y0, D.AXLE_Z + 8)],
                       closed=True, fill=False, ec='#8e44ad', ls='--', lw=.7, zorder=2))


def hdim(ax, x0, x1, z, text, off=0, fs=8):
    ax.annotate('', (x0, z), (x1, z), arrowprops=dict(arrowstyle='<->', lw=.6, color=INK))
    ax.text((x0 + x1)/2, z + 1.5 + off, text, ha='center', va='bottom', fontsize=fs, color=INK)


def vdim(ax, x, z0, z1, text, fs=8, side=1):
    ax.annotate('', (x, z0), (x, z1), arrowprops=dict(arrowstyle='<->', lw=.6, color=INK))
    ax.text(x + side*2, (z0 + z1)/2, text, ha='left' if side > 0 else 'right', va='center', fontsize=fs, color=INK, rotation=90)


def main():
    chk = D.check(); val = json.loads((ROOT / 'validation.json').read_text())
    fig = plt.figure(figsize=(16.5, 11.7))
    fig.text(.03, .965, 'JGY-370 single track  —  J9 layout (built from the CAD data)', fontsize=17, weight='bold', color=INK)
    fig.text(.03, .943, 'Change after the concept review: flat ground run. Sprocket, five road rollers and idler bear on one line; only the two support rollers lift the track.',
             fontsize=10, color='#40585e')
    fig.text(.03, .925, 'Side view from the inboard (motor) side with the housing and motor hidden; the housing\'s motor pod is dashed. All dimensions in mm.', fontsize=10, color='#40585e')

    ax = fig.add_axes([.03, .43, .94, .49]); ax.set_aspect('equal'); ax.axis('off')
    frame(ax); wheels(ax); chain_outline(ax); pod_outline(ax)
    ax.annotate('motor pod of the one-piece\nhousing (dashed): drum, gearbox\nshoulder, motor tube, cable port', (-62, D.AXLE_Z + 15.3), (-108, 100), fontsize=8, color=OLD,
                arrowprops=dict(arrowstyle='-', lw=.5, color=OLD))
    ax.plot([-170, 170], [0, 0], color='#6b4f2a', lw=1.4); ax.text(165, -4, 'ground', fontsize=8, ha='right', va='top', color='#6b4f2a')
    zl = D.GROUND_PIN_Z + D.RAIL_FACE
    ax.plot([D.DRIVE_X - 12, D.IDLER_X + 12], [zl, zl], color=ACC, lw=1.0, ls='-', zorder=6)
    ax.annotate('one straight running line: sprocket chord, 5 road rollers and idler (road rollers 0 mm below the end wheels)',
                (-75, zl), (-178, -30), fontsize=8.5, color=ACC, ha='left', arrowprops=dict(arrowstyle='-', lw=.6, color=ACC))
    zt = D.TOP_Z + D.TOP_LIFT
    ax.plot([D.CARRIER_X[0] - 14, D.CARRIER_X[1] + 14], [zt, zt], color='#1e8449', lw=1.0, zorder=6)
    ax.plot([D.DRIVE_X - 20, D.IDLER_X + 20], [D.TOP_Z, D.TOP_Z], color='#1e8449', lw=.7, ls=':', zorder=6)
    ax.text(0, zt + 9, 'top run lifted 3.5 mm over the end-wheel tops by the two support rollers', ha='center', fontsize=8.5, color='#1e8449')
    hdim(ax, D.DRIVE_X, D.IDLER_X, -19, f'{D.IDLER_X - D.DRIVE_X:.1f} sprocket to idler (idler free to recoil {D.RECOIL:.1f})')
    for a, b in zip(D.ROAD_X[:-1], D.ROAD_X[1:]):
        hdim(ax, a, b, -7, f'{b - a:.0f}', fs=7)
    vdim(ax, 152, 0, D.AXLE_Z, f'{D.AXLE_Z:.2f} axles', side=1)
    vdim(ax, 162, 0, chk['track_top_z'], f'{chk["track_top_z"]:.1f} top of track', side=1)
    vdim(ax, -158, 0, D.ROAD_Z, f'{D.ROAD_Z:.0f} road rollers', side=-1)
    vdim(ax, -168, 0, D.CARRIER_Z, f'{D.CARRIER_Z:.2f} support rollers', side=-1)
    ax.annotate('sprocket on a Pololu hub, JGY-370 D-shaft\n(12 V, 200:1 motor on the inboard wall)', (D.DRIVE_X - 30, D.AXLE_Z + 30), (-175, 112), fontsize=8, arrowprops=dict(arrowstyle='-', lw=.5))
    ax.annotate('idler on a U-yoke, R5 spring\n77 N fitted, recoil stop 4.2 mm', (D.IDLER_X + 20, D.AXLE_Z + 30), (120, 112), fontsize=8, arrowprops=dict(arrowstyle='-', lw=.5))
    ax.annotate('H-frame wall (web dashed)', (-40, 60), (-60, 112), fontsize=8, arrowprops=dict(arrowstyle='-', lw=.5))
    ax.set_xlim(-185, 185); ax.set_ylim(-34, 122)

    # Detail 1: flat ground at the sprocket end
    a1 = fig.add_axes([.03, .04, .31, .36]); a1.set_aspect('equal'); a1.axis('off')
    frame(a1); wheels(a1); chain_outline(a1, 1.4)
    a1.plot([-150, -40], [zl, zl], color=ACC, lw=1.1); a1.plot([-150, -40], [0, 0], color='#6b4f2a', lw=1.4)
    a1.plot([-150, -40], [D.GROUND_PIN_Z + 2 + D.RAIL_FACE]*2, color=OLD, lw=.9, ls='--')
    box = dict(fc='w', ec='none', alpha=.85, pad=1.5)
    a1.text(-126, 33, 'concept (removed): sprocket and idler 2 mm above the road rollers', fontsize=7.5, color=OLD, bbox=box)
    a1.annotate('', (-62, zl + 2), (-80, 32), arrowprops=dict(arrowstyle='->', lw=.6, color=OLD))
    a1.text(-126, 26.5, 'J9: sprocket chord, road rollers and ground run on one line', fontsize=7.5, color=ACC, bbox=box)
    a1.annotate('', (-100, zl), (-104, 25.5), arrowprops=dict(arrowstyle='->', lw=.6, color=ACC))
    a1.set_xlim(-128, -48); a1.set_ylim(-2, 36); a1.set_title('DETAIL A  —  sprocket end of the ground run', fontsize=10, loc='left', color=INK)

    # Detail 2: top run over the idler-side support roller
    a2 = fig.add_axes([.36, .04, .30, .36]); a2.set_aspect('equal'); a2.axis('off')
    frame(a2); wheels(a2); chain_outline(a2, 1.4)
    a2.plot([0, 125], [D.TOP_Z]*2, color='#1e8449', lw=.9, ls=':'); a2.plot([14, 50], [zt]*2, color='#1e8449', lw=1)
    a2.annotate('', (20, D.TOP_Z), (20, zt), arrowprops=dict(arrowstyle='<->', lw=.8, color='#1e8449'))
    a2.text(21.5, zt + 2.2, '3.5 mm lift of the pin line', fontsize=8, color='#1e8449', va='bottom', bbox=dict(fc='w', ec='none', alpha=.85, pad=1))
    a2.text(52, D.TOP_Z - 1.4, 'pin line over the end-wheel tops (dotted)', fontsize=7.5, color='#1e8449', va='top', bbox=dict(fc='w', ec='none', alpha=.85, pad=1))
    a2.set_xlim(12, 92); a2.set_ylim(56, 94); a2.set_title('DETAIL B  —  support roller lifting the top run', fontsize=10, loc='left', color=INK)

    # Change table and checks
    a3 = fig.add_axes([.68, .05, .31, .34]); a3.axis('off')
    rows = [('', 'concept', 'J9 CAD'),
            ('Road rollers below end wheels', '2.0', '0 (flat)'),
            ('Axle height', '46.32', f'{D.AXLE_Z:.2f}'),
            ('Idler centre X (34 links taut)', '109.80', f'{D.IDLER_X:.2f}'),
            ('Support-roller lift / centre Z', '3.5 / 72.14', f'3.5 / {D.CARRIER_Z:.2f}'),
            ('Top of track', '94.4', f'{chk["track_top_z"]:.1f}'),
            ('Sprocket outer support', 'boss in 6800ZZ', 'plug in 6800ZZ'),
            ('Idler axle', 'M8 bolt, wall slots', 'Ø8 pin in yoke'),
            ('Sprocket on the motor shaft', 'printed D-bore', 'Pololu #1999 hub'),
            ('JGY-370-1260 12 V ratio', 'open', '200:1, 30 rpm'),
            ('Motor enclosure', 'thin shroud', 'closed drive pod'),
            ('Spring preload / at recoil stop', '77 N', f'{chk["spring_preload_N"]:.0f} / {chk["spring_at_recoil_N"]:.0f} N')]
    for i, r in enumerate(rows):
        for j, t in enumerate(r):
            a3.text([0, .52, .76][j], 1 - i*.062, t, fontsize=8.6, weight='bold' if i == 0 else None, color=INK, transform=a3.transAxes)
    st = val['static']
    aa = val['assembly_and_access']
    n_tools = sum(len(aa[k]) for k in ('motor_screw_key_before_sprocket', 'housing_screw_driver', 'roller_bolt_through_skirt',
                                       'nyloc_socket', 'hub_set_screw_key')) + 1
    lines = [f'CAD checks (validation.json): {"PASS" if val["pass"] else "FAIL"}',
             f'34 links closed exactly (error {chk["link_error_mm"]:.0e} mm); static overlap: 0 of {st["pairs_tested"]} pairs',
             'drive rotation, idler recoil to the stop, 3 chain phases, sprocket fitting path,',
             f'plug, yoke and housing insertion, {n_tools} tool-access paths: no overlaps',
             f'min clearance track pins/clips to H-frame {val["clearances_mm"]["track pins and clips to H-frame"]:.1f} mm']
    for i, t in enumerate(lines):
        a3.text(0, .26 - i*.055, t, fontsize=8, color='#1e6b3a' if i == 0 else '#40585e', weight='bold' if i == 0 else None, transform=a3.transAxes)
    out = ROOT / 'J9_layout.pdf'
    fig.savefig(out); fig.savefig(ROOT / 'images/J9_layout.png', dpi=110)
    print('wrote', out)


if __name__ == '__main__':
    main()

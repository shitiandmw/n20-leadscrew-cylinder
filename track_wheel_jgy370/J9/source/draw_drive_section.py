"""Section through the J9 drive axis (plane X = DRIVE_X, seen from the front): JGY-370 shaft, Pololu #1999 hub
and its set screws, printed sprocket, journal plug, 6800ZZ and the H-frame walls. Writes ../images/J9_drive_section.png."""
from functools import reduce
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import trimesh
from shapely.geometry import Polygon
import j9_parts as P
import j9_design as D

ROOT = P.ROOT
PARTS = [('J901_H_frame', P.FRAME_C), ('JGY370_gearbox', P.GEARBOX_C), ('JGY370_output_shaft', P.STEEL),
         ('Pololu_1999_hub', P.HUB_C), ('hub_set_screw_M3x8', (.15, .15, .15)), ('hub_set_screw_M3x3', (.15, .15, .15)),
         ('J902_sprocket', (.42, .44, .46)), ('J903_journal_plug', (.30, .32, .34)), ('sprocket_screw_M3x50', (.15, .15, .15)),
         ('6800ZZ_inner', P.STEEL), ('6800ZZ_outer', P.STEEL), ('6800ZZ_shield', (.2, .2, .2)), ('J909_housing', P.HOUSING_C)]


def section(shape):
    v, f = P.one(shape).tessellate(.01, .1)
    m = trimesh.Trimesh(np.array([(p.x, p.y, p.z) for p in v]), np.array(f), process=True)
    s = m.section(plane_origin=[D.DRIVE_X, 0, 0], plane_normal=[1, 0, 0])
    if s is None:
        return None
    loops = [Polygon(l[:, 1:]) for l in s.discrete if len(l) > 3]
    loops = [l.buffer(0) for l in loops if l.area > 1e-4]
    return reduce(lambda a, b: a.symmetric_difference(b), loops) if loops else None


def main():
    inst = P.unit(with_chain=False)
    fig, ax = plt.subplots(figsize=(12.5, 8.4))
    for name, color in PARTS:
        g = section(inst[name]['shape'])
        if g is None:
            continue
        for poly in getattr(g, 'geoms', [g]):
            ax.fill(*poly.exterior.xy, color=color, ec='#1d2b2f', lw=.5)
            for hole in poly.interiors:
                ax.fill(*hole.xy, color='white', ec='#1d2b2f', lw=.5)
    z0 = D.AXLE_Z
    ax.axhline(z0, color='#7a8a8f', lw=.5, ls='-.')
    notes = [((-42, z0 - 8), (-100, z0 - 12), 'JGY-370 gearbox\n(12 V, 200:1)'),
             ((-27, z0 + 22), (-100, z0 + 20), 'inner wall\n+ motor rim'),
             ((-26, z0 + 1.5), (-100, z0 + 6), '6 mm D-shaft,\nflat up'),
             ((-60.5, z0 + 18), (-100, z0 + 38), 'housing J909: drum of\nthe motor pod, hub cap'),
             ((-37, z0 - 30), (-100, z0 - 34), 'housing skirt'),
             ((-16.3, z0 + 9), (-40, z0 + 46), '2 × M3 set screws on the flat'),
             ((2, z0 + 36), (4, z0 + 46), 'printed sprocket J902'),
             ((27.5, z0 + 7.5), (40, z0 + 24), '6800ZZ in the\nouter wall'),
             ((18, z0 - 3), (40, z0 - 20), 'journal plug J903\n+ M3 × 50'),
             ((-16.5, z0 - 10), (-62, z0 - 50), 'Pololu #1999 hub (Ø25.4 flange, Ø12 boss)'),
             ((-14.1, z0 - 2), (-8, z0 - 50), 'printed pad meets the shaft end')]
    for xy, txt_xy, t in notes:
        ax.annotate(t, xy, txt_xy, fontsize=8.5, color='#1d2b2f', arrowprops=dict(arrowstyle='-', lw=.5, color='#1d2b2f'))
    ax.set_xlim(-104, 58); ax.set_ylim(z0 - 53, z0 + 50); ax.set_aspect('equal')
    ax.set_xlabel('Y (mm): inboard  ←  →  outboard'); ax.set_ylabel('Z (mm)')
    ax.set_title('J9 drive: section through the sprocket axis (seen from the front)', fontsize=12, loc='left')
    fig.tight_layout()
    out = ROOT / 'images/J9_drive_section.png'
    fig.savefig(out, dpi=120)
    print('wrote', out)


if __name__ == '__main__':
    main()

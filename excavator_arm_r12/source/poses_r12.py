"""Body frames of the R12 arm for given drive strokes (shared by CAD, physics, viewer and checks)."""
import math
import numpy as np
import r12_design as d

REF_POSE = (40.0, 26.0, 30.0)
DRIVES = [  # name, rear pin, rod pin, Y centre, board side, body carrying the rear pin
    ('boom_L', 'A', 'B', d.Y['boom_cyl'], d.BOARD_SIDE['boom'], 'base'),
    ('boom_R', 'A', 'B', -d.Y['boom_cyl'], d.BOARD_SIDE['boom'], 'base'),
    ('stick', 'C', 'D', 0.0, d.BOARD_SIDE['stick'], 'boom'),
    ('bucket', 'F', 'R', 0.0, d.BOARD_SIDE['bucket'], 'stick'),
]
DRIVE_AXIS = dict(boom_L=0, boom_R=0, stick=1, bucket=2)        # which stroke of (boom, stick, bucket)
LINKS = ('base', 'boom', 'stick', 'bucket', 'side_link', 'h_link')
BODIES = LINKS + tuple(f'{n}_{p}' for n, *_ in DRIVES for p in ('barrel', 'rod'))


def body_poses(strokes):
    """(origin (x, z) mm, angle rad) of every body frame in the world."""
    s = d.solve(strokes)
    P, po = s['pins'], s['poses']
    out = dict(base=(np.zeros(2), 0.0), **{k: (np.asarray(v[0], float), float(v[1])) for k, v in po.items()})
    for name, a, b, *_ in DRIVES:
        u = P[b] - P[a]
        L = float(np.linalg.norm(u))
        ang = math.atan2(u[1], u[0])
        out[f'{name}_barrel'] = (P[a].copy(), ang)
        out[f'{name}_rod'] = (P[a] + (L - d.ACT['closed']) * u / L, ang)
    return s, out

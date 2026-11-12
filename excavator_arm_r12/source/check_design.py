"""Design-stage verification of R12: dense 2.5D clash sweep, holding forces, levers, four-bar angles,
working range, boom sections and the stroke study -> ../design_check.json"""
import json
import math
import time
import itertools
import multiprocessing as mp
import numpy as np
from shapely.geometry import box
from shapely.ops import unary_union
import r12_design as d
import r12_loads as LD
import stroke_study


def check_pose(st):
    st = tuple(float(x) for x in st)
    return st, d.interference(st), {'|'.join(k): v for k, v in d.min_gaps(st).items()}


def x1_track_limit():
    """Slewed over an X1 track (~90 deg), the boom and its drives must stay above the track top."""
    for sb in np.linspace(0, 60, 61):
        s = d.solve((sb, 30, 30))
        g = unary_union([d.place(d.boom_profile(), *s['poses']['boom']),
                         d.actuator_shapes(s['pins']['A'], s['pins']['B'], d.BOARD_SIDE['boom'])['body']])
        seg = g.intersection(box(105, -400, 175, 400))
        if seg.is_empty or seg.bounds[1] > 92.4 + d.GROUND_Z + 3:
            return dict(stroke=float(sb), boom_deg=round(math.degrees(s['theta']), 1))
    return None


def main():
    t0 = time.time()
    grid = [0, 10, 20, 30, 40, 50, 60]
    poses = list(itertools.product(grid, repeat=3))
    fine = []
    for i in range(3):
        for others in itertools.product([0, 60], [0, 60]):
            for s in np.linspace(0, 60, 61):
                st = list(others)
                st.insert(i, float(s))
                fine.append(tuple(st))
    d.parts_at((30, 30, 30))                 # warm the outline caches before forking
    with mp.get_context('fork').Pool() as pool:
        res = pool.map(check_pose, poses + fine, chunksize=8)
    hits, gaps = [], {}
    for st, h, g in res:
        hits += [dict(pose=list(st), **x) for x in h]
        for k, v in g.items():
            if v < gaps.get(k, (1e9,))[0]:
                gaps[k] = (v, st)
    g13 = np.linspace(0, 60, 13)
    forces, fpose, forces_unl = dict(boom=0, stick=0, bucket=0), {}, dict(boom=0, stick=0, bucket=0)
    for st in itertools.product(g13, repeat=3):
        for k, v in zip(forces, d.drive_forces(st)):
            if abs(v) > forces[k]:
                forces[k], fpose[k] = abs(v), [float(x) for x in st]
        for k, v in zip(forces_unl, d.drive_forces(st, payload=False)):
            forces_unl[k] = max(forces_unl[k], abs(v))
    env = d.envelope(19, 25)
    wr = d.working_ranges(env)
    dump, dump_pose = d.dump_height()
    wr['dump_height'] = dump
    arms = [d.moment_arms((s, s, s)) for s in g13]
    tr = [d.transmission((30, 30, s)) for s in np.linspace(0, 60, 31)]
    tips = [d.tip_forces((30, 30, s)) for s in g13]
    a0, a1 = d.joint_angles((0, 0, 0)), d.joint_angles((60, 60, 60))
    close = [(k.split('|')[0], k.split('|')[1], round(v[0], 2), list(v[1]))
             for k, v in sorted(gaps.items(), key=lambda kv: kv[1][0])][:16]
    rep = dict(
        status='PASS' if not hits else 'FAIL',
        scope='2.5D side-view sweep with lateral (Y) bands incl. pin collars; design stage, not a 3D CAD check',
        poses_grid=len(poses), poses_fine=len(fine), clearance_required_mm=1.0, hits=hits[:20], n_hits=len(hits),
        closest_pairs=close,
        joint_ranges_deg=dict(boom=[round(a0[0], 2), round(a1[0], 2)], stick=[round(a0[1], 2), round(a1[1], 2)],
                              bucket=[round(a0[2], 2), round(a1[2], 2)]),
        hold_force_per_drive_N_150g={k: round(v, 1) for k, v in forces.items()}, worst_pose=fpose,
        hold_force_per_drive_N_unloaded={k: round(v, 1) for k, v in forces_unl.items()},
        thrust_continuous_N=d.ACT['thrust_cont'],
        min_moment_arm_mm=dict(boom=round(min(a[0] for a in arms), 1), stick=round(min(a[1] for a in arms), 1),
                               bucket=round(min(a[2] for a in arms), 1)),
        min_transmission_deg=dict(Q=round(min(t[0] for t in tr), 1), R=round(min(t[1] for t in tr), 1)),
        tip_force_at_rating=dict(bucket_min=round(min(t['bucket'] for t in tips), 2), bucket_max=round(max(t['bucket'] for t in tips), 2),
                              stick_min=round(min(t['stick'] for t in tips), 2), stick_max=round(max(t['stick'] for t in tips), 2)),
        working_ranges_mm={k: round(float(v), 1) for k, v in wr.items()}, dump_pose=list(dump_pose),
        cat320_1_15_mm={k: round(v, 1) for k, v in d.CAT_1_15.items()},
        x1_track_limit=x1_track_limit(),
        boom_sections=LD.section_table(),
        stroke_study=stroke_study.study(),
        masses_kg={k: round(v[0], 4) for k, v in d.MASS.items()},
        pins=dict(A_world=d.A_W.round(2).tolist(), B_boom=d.B_B.round(2).tolist(), C_boom=d.C_B.round(2).tolist(),
                  D_stick=d.D_S.round(2).tolist(), F_stick=d.F_S.round(2).tolist(), J_stick=d.J_S.round(2).tolist(),
                  H_stick=d.H_S.round(2).tolist(), Q_bucket=[round(float(x), 2) for x in d.Q_K], T_bucket=d.T_K.tolist()),
        links=dict(side_link=round(d.SIDE_LINK, 2), h_link=round(d.H_LINK, 2), ear_HQ=round(d.EAR, 2)),
        seconds=round(time.time() - t0, 1))
    (d.rc.ROOT / 'design_check.json').write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k not in ('hits', 'stroke_study', 'boom_sections')}, indent=1)[:4000])
    print('hits', len(hits))


if __name__ == '__main__':
    main()

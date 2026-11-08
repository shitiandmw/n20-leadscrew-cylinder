"""Integration checks of the complete machine: what is new when R12 goes on the X1 upper.

Everything already validated inside one subsystem is not repeated (J9 and X1 joint checks, turntable, body, R12's own
clash check). Tested here, on the viewer meshes of the current CAD (chord error <= 0.05 mm for R12 and B01X, 0.1 mm
for the turntable and the X1 hardware, 0.15 mm for the body prints):
  1. interface   T101's rib-top height and M6 bolt axes, measured on the turntable meshes; B01X seated on the ribs
                 and under the bolt heads without overlap; B01X against the body and everything else at rest
  2. arm/upper   every R12 moving part against the upper (turntable, body, electronics, B01X) over R12's 5 x 5 x 5
                 stroke grid and its dig cycle (MuJoCo trace, 150 g) every 2 s
  3. demo        the demonstration sequence against the lower (tracks, chains, X-frame): dig at swing 0, swing to 90
                 holding the raise pose, dump at 90, swing back holding the dump pose, return to carry at 0
  4. envelope    the carry pose swung all round; the stroke grid at swings 0/45/90/135/180 (a map of which poses
                 reach the lower, not a pass/fail)
  5. reach       tooth reach, dig depth and dump height with O at Z 195 (R12 drawings: O at 155)
  6. balance     machine CG over the track footprint for the stroke grid and the cycle, swings 0-315, with and without
                 the 150 g payload
Writes ../integration_check.json. Run with the R12 interpreter (fcl, trimesh) from this folder.
"""
import sys
import json
import math
import time
import itertools
import multiprocessing as mp
import numpy as np
import fcl
import trimesh
import common as K
import machine as M

sys.path.insert(0, str(K.R12 / 'source'))
import r12_design as d                # noqa: E402
import motion_r12 as Mo               # noqa: E402
from poses_r12 import body_poses      # noqa: E402

NEAR = 5.0
PARTS, LINKS, CFG = M.load()
TRACE = K.load_gz(K.R12 / 'simulation/payload_150g_trace.json.gz')
SEG = {s['name']: (s['t0'], s['t1']) for s in Mo.SEGMENTS}
T_RAISE_END = SEG['raise -> dump'][0]           # the arm holds the raise pose (dwell) here: swing out
T_DUMP_END = SEG['dump -> carry'][0]            # holds the dump pose: swing back

# ------------------------------------------------------------------ collision objects
def bvh(v, t):
    m = fcl.BVHModel()
    m.beginModel(len(v), len(t))
    m.addSubModel(np.ascontiguousarray(v, float), np.ascontiguousarray(t, np.int64))
    m.endModel()
    return m


def sphere(v):
    c = 0.5 * (v.min(0) + v.max(0))
    return c, float(np.linalg.norm(v - c, axis=1).max())


OBJ = []        # dict(name, sys, set, body, obj, c, r)
for p in PARTS:
    v = p['v']
    if p['mover'] == 'track':
        R, t = M.track_frame(CFG, p['side'])
        v = v @ R.T + t
        name = f"{p['name']} ({'left' if p['side'] > 0 else 'right'} track)"
        st = 'lower'
    elif p['mover'] == 'ground':
        name, st = p['name'], 'lower'
    elif p['mover'] in ('upper', 'pinion'):
        name, st = p['name'], p['mover']
    else:
        name, st = p['name'], 'arm'
    c, r = sphere(v)
    OBJ.append(dict(name=name, sys=p['sys'], set=st, body=p.get('body'), new=p.get('new', False), r12=p['sys'] == 'arm',
                    obj=fcl.CollisionObject(bvh(v, p['t']), fcl.Transform()), c=c, r=r, zmin=float(v[:, 2].min())))
for side in (1, -1):                       # chains at phase 0, fixed to the lower for these checks
    Rt, tt = M.track_frame(CFG, side)
    shoes, pins = M.chain_transforms(CFG, 0.0)
    for j, ((Rs, ts), (Rp, tp)) in enumerate(zip(shoes, pins)):
        for L, (R, t) in ((LINKS[0], (Rs, ts)), (LINKS[1], (Rp, tp))):
            v = (L['v'] @ R.T + t) @ Rt.T + tt
            c, r = sphere(v)
            OBJ.append(dict(name=f"{L['name']} ({'left' if side > 0 else 'right'} track, link {j})", sys='track', set='lower',
                            body=None, new=False, r12=False, obj=fcl.CollisionObject(bvh(v, L['t']), fcl.Transform()),
                            c=c, r=r, zmin=float(v[:, 2].min())))
ARM = [i for i, o in enumerate(OBJ) if o['set'] == 'arm']
UPPER = [i for i, o in enumerate(OBJ) if o['set'] in ('upper', 'pinion') and not (o['r12'] and not o['new'])]
LOWER = [i for i, o in enumerate(OBJ) if o['set'] == 'lower']
B01X = next(i for i, o in enumerate(OBJ) if o['new'])


def place(pose_bodies, swing):
    """Set every transform for one machine state. pose_bodies: {body: ((x, z), a)} (R12 O frame)."""
    T = M.arm_transforms(pose_bodies, swing)
    Ru, tu = M.upper_transform(swing)
    Rp, tp = M.pinion_transform(CFG, swing)
    centres = {}
    for i, o in enumerate(OBJ):
        if o['set'] == 'arm':
            R, t = T[o['body']]
        elif o['set'] == 'upper':
            R, t = Ru, tu
        elif o['set'] == 'pinion':
            R, t = Rp, tp
        else:
            R, t = np.eye(3), np.zeros(3)
        o['obj'].setTransform(fcl.Transform(R, t))
        centres[i] = R @ o['c'] + t
    return centres


def test(pairs, centres, near=NEAR):
    hits, close = [], []
    for i, j in pairs:
        gap = np.linalg.norm(centres[i] - centres[j]) - OBJ[i]['r'] - OBJ[j]['r']
        if gap > near:
            continue
        res = fcl.CollisionResult()
        if fcl.collide(OBJ[i]['obj'], OBJ[j]['obj'], fcl.CollisionRequest(), res):
            hits.append((OBJ[i]['name'], OBJ[j]['name']))
            continue
        dr = fcl.DistanceResult()
        dist = fcl.distance(OBJ[i]['obj'], OBJ[j]['obj'], fcl.DistanceRequest(enable_nearest_points=True), dr)
        if dist < near:
            close.append((OBJ[i]['name'], OBJ[j]['name'], round(float(dist), 3)))
    return hits, close


def trace_pose(t):
    """R12 body poses from the MuJoCo trace at time t (linear between the 10 Hz frames, as the viewers)."""
    fr, hz = TRACE['frames'], TRACE['record_hz']
    x = min(max(t * hz, 0), len(fr) - 1.000001)
    i, f = int(x), x - int(x)
    a, b = fr[i]['pose'], fr[i + 1]['pose']
    p = [u + (w - u) * f for u, w in zip(a, b)]
    out = {'base': (np.zeros(2), 0.0)}
    for j, n in enumerate(TRACE['bodies']):
        out[n] = (np.array(p[3 * j:3 * j + 2]), p[3 * j + 2])
    tip = [u + (w - u) * f for u, w in zip(fr[i]['tip'], fr[i + 1]['tip'])]
    return out, tip


def grid_pose(st):
    s, P = body_poses(tuple(st))
    return {k: (np.asarray(v[0], float), float(v[1])) for k, v in P.items()}, [float(x) for x in s['pins']['T']]


# a job: (label, kind, key, swing, set)  kind 'grid' (key = strokes) or 'trace' (key = t)
def run(job):
    label, kind, key, swing, which = job
    pose, tip = grid_pose(key) if kind == 'grid' else trace_pose(key)
    cen = place(pose, swing)
    others = UPPER if which == 'upper' else LOWER
    pairs = [(i, j) for i in ARM for j in others]
    hits, close = test(pairs, cen)
    # lowest arm point (for the ground and the reach numbers)
    zmin = min(float((cen[i] - OBJ[i]['r'])[2]) for i in ARM)
    return dict(label=label, kind=kind, key=key if kind == 'trace' else list(key), swing=swing, which=which,
                hits=hits, close=close, tip_O=tip, zmin_sphere=zmin)


def summarise(results, n=8):
    hits, best = [], {}
    for r in results:
        hits += [dict(state=f"{r['label']} {r['key']} swing {r['swing']:g}", a=a, b=b) for a, b in r['hits']]
        for a, b, dist in r['close']:
            k = f'{a} | {b}'
            if dist < best.get(k, (1e9,))[0]:
                best[k] = (dist, f"{r['label']} {r['key']} swing {r['swing']:g}")
    top = [dict(pair=k, gap_mm=v[0], state=v[1]) for k, v in sorted(best.items(), key=lambda kv: kv[1][0])[:n]]
    return dict(states=len(results), penetrations=len(hits), hits=hits[:40], closest=top)


# ------------------------------------------------------------------ 1. interface
def interface():
    by = {o['name']: i for i, o in enumerate(OBJ)}
    t101 = next(p for p in PARTS if p['name'] == 'T101_centre_frame')
    v = t101['v']
    rib = v[(np.abs(np.abs(v[:, 1]) - 65.0) < 4.0)]
    top = float(rib[:, 2].max())
    bolts = []
    for k in range(4):
        b = next(p for p in PARTS if p['name'] == f'arm_bolt_M6x40_{k}')['v']
        bolts.append([round(float(b[:, 0].mean()), 3), round(float(b[:, 1].mean()), 3), round(float(b[:, 2].max()), 3)])
    want = sorted(K.BOLTS)
    got = sorted((b[0], b[1]) for b in bolts)
    axis_err = max(math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(want, got))
    head_under = min(b[2] for b in bolts) - 6.0           # ISO 4762 M6 head height 6
    plate = PARTS[[i for i, p in enumerate(PARTS) if p.get('new')][0]]['v']
    rep = dict(t101_rib_top_z=round(top, 3), expected_z=K.T101_TOP_Z, b01x_plate_bottom_z=round(float(plate[:, 2].min()), 3),
               b01x_plate_top_z=K.T101_TOP_Z + K.BASE_T, bolt_axes_measured=bolts, bolt_axes_expected=[list(b) for b in K.BOLTS],
               bolt_axis_error_mm=round(axis_err, 4), bolt_head_underside_z=round(head_under, 3))
    # seated contacts: B01X lifted 0.02 must clear T101 and the nuts; lowered 0.02 must clear the bolt heads and shanks
    place({'base': (np.zeros(2), 0.0), **grid_pose(Mo.WAYPOINTS[0][1])[0]}, 0.0)
    o = OBJ[B01X]['obj']
    res = {}
    for dz, names in ((+0.02, ['T101_centre_frame'] + [f'arm_nut_M6_{k}' for k in range(4)]),
                      (-0.02, [f'arm_bolt_M6x40_{k}' for k in range(4)])):
        o.setTransform(fcl.Transform(np.eye(3), np.array([0, 0, dz])))
        for nm in names:
            j = by[nm]
            r = fcl.CollisionResult()
            hit = fcl.collide(o, OBJ[j]['obj'], fcl.CollisionRequest(), r)
            dr = fcl.DistanceResult()
            dist = 0.0 if hit else fcl.distance(o, OBJ[j]['obj'], fcl.DistanceRequest(), dr)
            res[f'{nm} (B01X {dz:+.2f} Z)'] = dict(overlap=bool(hit), gap_mm=round(float(dist), 3))
    o.setTransform(fcl.Transform())
    rep['seated'] = res
    # B01X against everything else at rest (body prints, hardware, electronics, lower)
    cen = place({'base': (np.zeros(2), 0.0), **grid_pose(Mo.WAYPOINTS[0][1])[0]}, 0.0)
    skip = {by['T101_centre_frame']} | {by[f'arm_bolt_M6x40_{k}'] for k in range(4)} | {by[f'arm_nut_M6_{k}'] for k in range(4)}
    rest = [(B01X, j) for j, ob in enumerate(OBJ) if j != B01X and j not in skip and not ob['r12']]
    hits, close = test(rest, cen, near=8.0)
    rep['static_against_the_rest'] = dict(pairs=len(rest), penetrations=hits,
                                          closest=sorted(close, key=lambda c: c[2])[:8])
    ok = (abs(top - K.T101_TOP_Z) < 0.05 and abs(rep['b01x_plate_bottom_z'] - K.T101_TOP_Z) < 1e-3 and axis_err < 0.05
          and abs(head_under - (K.T101_TOP_Z + K.BASE_T)) < 0.05 and not any(v['overlap'] for v in res.values()) and not hits)
    rep['pass'] = bool(ok)
    return rep


# ------------------------------------------------------------------ 6. balance
def balance():
    mp_ = json.loads((K.X1 / 'simulation/turntable_mass_properties.json').read_text())
    r12m = json.loads((K.R12 / 'simulation/mass_properties.json').read_text())['bodies']
    cad = json.loads((K.R12 / 'cad/cad_report.json').read_text())
    b01x = json.loads((K.ROOT / 'cad/B01X_report.json').read_text())
    up, lo, pin = mp_['upper'], mp_['lower'], mp_['pinion']
    arm60 = {p['name']: p['mass_kg'] for p in mp_['parts'] if p['name'].startswith('ARM60')}
    tt = K.load_gz(K.X1 / 'source/turntable_scene.json.gz')
    m60, c60 = 0.0, np.zeros(3)
    for it in tt['items']:
        if it['name'] in arm60:
            tm = trimesh.Trimesh(np.asarray(it['vertices'], float), np.asarray(it['triangles'], np.int64), process=True)
            m60 += arm60[it['name']]
            c60 += arm60[it['name']] * np.asarray(tm.center_mass)
    c60 /= m60
    mu = up['mass_kg'] + pin['mass_kg']
    cu = (up['mass_kg'] * np.asarray(up['centre_m']) + pin['mass_kg'] * np.asarray(pin['centre_m'])) * 1000 / mu
    m_noarm = mu - m60
    c_noarm = (mu * cu - m60 * c60) / m_noarm
    # R12 base body: B01 (solid, cad_report mass) replaced by B01X (print rule)
    b01_mass = next(p['mass_g'] for p in cad['printed_parts'] if p['name'] == 'B01_boom_foot_bracket') / 1000
    r12s = K.load_gz(K.R12 / 'cad/scene.json.gz')
    b01_mesh = next(i for i in r12s if i['name'] == 'B01_boom_foot_bracket')
    c_b01 = np.asarray(trimesh.Trimesh(np.asarray(b01_mesh['v']).reshape(-1, 3), np.asarray(b01_mesh['t']).reshape(-1, 3)).center_mass)
    base = r12m['base']
    m_base = base['mass_kg'] - b01_mass + b01x['mass_g'] / 1000
    c_base = (base['mass_kg'] * np.asarray(base['com_mm']) - b01_mass * c_b01 + b01x['mass_g'] / 1000 * np.asarray(b01x['com_mm_O_frame'])) / m_base
    moving = {k: (v['mass_kg'], np.asarray(v['com_mm'])) for k, v in r12m.items() if k != 'base'}
    pay_m, pay_c = d.PAYLOAD, np.array([d.MASS['payload'][1][0], 0.0, d.MASS['payload'][1][1]])
    m_lo, c_lo = lo['mass_kg'], np.asarray(lo['centre_m']) * 1000
    pins = np.asarray(CFG['j9']['pins'])
    ground = pins[np.abs(pins[:, 1] - pins[:, 1].min()) < 0.5]
    fx = (float(ground[:, 0].min()), float(ground[:, 0].max()))
    fy = CFG['track_y'] + CFG['key']['shoe_width'] / 2

    def state(pose, swing, payload):
        T = M.arm_transforms(pose, 0.0)
        items = [(m_noarm, c_noarm), (m_base, c_base + K.O_VEH)]
        for b, (m, c) in moving.items():
            R, t = T[b]
            items.append((m, R @ c + t))
        if payload:
            R, t = T['bucket']
            items.append((pay_m, R @ pay_c + t))
        mu_ = sum(m for m, _ in items)
        cu_ = sum(m * c for m, c in items) / mu_
        cu_ = K.rot_z(swing) @ cu_
        mt = mu_ + m_lo
        ct = (mu_ * cu_ + m_lo * c_lo) / mt
        margin = min(ct[0] - fx[0], fx[1] - ct[0], ct[1] + fy, fy - ct[1])
        return mu_, cu_, mt, ct, margin

    rows = []
    grid = [0.0, 15.0, 30.0, 45.0, 60.0]
    for st in itertools.product(grid, repeat=3):
        pose = grid_pose(st)[0]
        for sw in range(0, 360, 45):
            for pay in (False, True):
                mu_, cu_, mt, ct, mg = state(pose, sw, pay)
                rows.append((mg, list(st), sw, pay, ct))
    cyc = []
    for t in np.arange(0, TRACE['frames'][-1]['t'], 2.0):
        pose = trace_pose(t)[0]
        sw = K.SWING_DUMP_DEG if T_RAISE_END <= t <= T_DUMP_END else 0.0
        cyc.append(state(pose, sw, True)[4])
    worst = min(rows, key=lambda r: r[0])
    ref = state(grid_pose(Mo.WAYPOINTS[0][1])[0], 0.0, False)
    by_pose = {n: [round(float(x), 1) for x in state(grid_pose(st)[0], 0.0, False)[1]] for n, st in Mo.WAYPOINTS[:-1]}
    # the shot was sized with the ARM60 stretched forward; the R12 counterpart is 'reach out, bucket open'
    shot = next(i for i in K.load_gz(K.X1 / 'source/body_scene.json.gz')['items'] if i['name'] == 'ballast_steel_shot')
    xs = float(trimesh.Trimesh(np.asarray(shot['vertices'], float), np.asarray(shot['triangles'], np.int64)).center_mass[0])
    mu_s, cu_s = state(grid_pose(Mo.WAYPOINTS[1][1])[0], 0.0, False)[:2]
    trim = dict(reference_pose='reach out, bucket open %s (R12 stretched, as the ARM60 was when the shot was sized)' % (list(Mo.WAYPOINTS[1][1]),),
                upper_cg_x_mm=round(float(cu_s[0]), 1), shot_centre_x_mm=round(xs, 1),
                shot_to_remove_kg=round(float(mu_s * cu_s[0] / xs), 3),
                note='Removing this much shot (uniformly, at the pocket centre) would put the upper CG back on the swing axis in that pose. '
                     'Not applied: the body is unchanged in this folder.')
    old_upper = dict(kg=round(mu, 3), cg_mm=[round(float(x), 1) for x in cu])
    return dict(
        method='Static: CG of the whole machine projected on the ground against the track footprint (ground-run pins X %.0f..%.0f, '
               'shoe outer edges |Y| %.0f). Positive margin = inside. Upper without the ARM60: the X1 turntable mass file minus the ARM60 '
               '(its masses there, centres from its meshes at uniform density). R12 bodies from R12 mass_properties.json with B01 '
               'replaced by B01X. Lower from the same file. No dynamics, slopes or digging forces.' % (fx[0], fx[1], fy),
        lower=dict(kg=round(m_lo, 3), cg_mm=[round(float(x), 1) for x in c_lo]),
        upper_with_arm60_as_in_X1=old_upper,
        arm60_removed=dict(kg=round(m60, 4), cg_mm=[round(float(x), 1) for x in c60]),
        r12_added=dict(kg=round(m_base + sum(m for m, _ in moving.values()), 4), base_body_with_B01X_kg=round(m_base, 4)),
        upper_with_r12_carry_pose=dict(kg=round(ref[0], 3), cg_mm=[round(float(x), 1) for x in ref[1]]),
        upper_cg_mm_by_waypoint=by_pose, shot_trim_estimate=trim,
        machine_carry_pose=dict(kg=round(ref[2], 3), cg_mm=[round(float(x), 1) for x in ref[3]], margin_mm=round(ref[4], 1)),
        footprint_mm=dict(x=[round(fx[0], 1), round(fx[1], 1)], y=[-fy, fy]),
        worst_static=dict(margin_mm=round(worst[0], 1), strokes=worst[1], swing_deg=worst[2], payload=worst[3],
                          cg_mm=[round(float(x), 1) for x in worst[4]]),
        states=len(rows), cycle_min_margin_mm=round(min(cyc), 1), all_inside=bool(worst[0] > 0),
        note='The body\'s shot pocket was sized to put the upper CG on the swing axis with the 1.64 kg ARM60 stretched forward. R12 with '
             'B01X is lighter, so the upper CG moves rearward (upper_cg_mm_by_waypoint, shot_trim_estimate). The machine stays inside its '
             'footprint in every case here.')


def main():
    t0 = time.time()
    rep = dict(method='FCL mesh-mesh collision and distance on the viewer meshes of the current CAD (see the module docstring)')
    rep['interface'] = interface()
    print('interface', rep['interface']['pass'], round(time.time() - t0, 1), 's', flush=True)
    grid = list(itertools.product([0.0, 15.0, 30.0, 45.0, 60.0], repeat=3))
    t_end = TRACE['frames'][-1]['t']
    jobs_upper = [('grid', 'grid', st, 0.0, 'upper') for st in grid]
    jobs_upper += [('cycle', 'trace', float(t), 0.0, 'upper') for t in np.arange(0, t_end, 2.0)]
    sw = K.SWING_DUMP_DEG
    demo = [('dig at 0', 'trace', float(t), 0.0, 'lower') for t in np.arange(0, T_RAISE_END + 1e-9, 1.0)]
    demo += [('swing out (raise pose)', 'trace', T_RAISE_END, float(a), 'lower') for a in np.arange(0, sw + 1e-9, 2.5)]
    demo += [('dump at %g' % sw, 'trace', float(t), sw, 'lower') for t in np.arange(T_RAISE_END, T_DUMP_END + 1e-9, 1.0)]
    demo += [('swing back (dump pose)', 'trace', T_DUMP_END, float(a), 'lower') for a in np.arange(sw, -1e-9, -2.5)]
    demo += [('return to carry at 0', 'trace', float(t), 0.0, 'lower') for t in np.arange(T_DUMP_END, t_end, 1.0)]
    allround = [('carry pose, full swing', 'trace', 0.0, float(a), 'lower') for a in range(0, 360, 5)]
    envelope = [('grid', 'grid', st, float(a), 'lower') for a in (0, 45, 90, 135, 180) for st in grid]
    with mp.get_context('fork').Pool(6) as pool:
        r_up = pool.map(run, jobs_upper, chunksize=4)
        print('arm/upper', round(time.time() - t0, 1), 's', flush=True)
        r_demo = pool.map(run, demo, chunksize=4)
        r_all = pool.map(run, allround, chunksize=2)
        print('demo', round(time.time() - t0, 1), 's', flush=True)
        r_env = pool.map(run, envelope, chunksize=4)
        print('envelope', round(time.time() - t0, 1), 's', flush=True)
    rep['arm_vs_upper'] = summarise(r_up)
    rep['demo_vs_lower'] = summarise(r_demo)
    rep['carry_pose_full_swing'] = summarise(r_all)
    env = {}
    for r in r_env:
        env.setdefault(r['swing'], []).append(r)
    rep['grid_envelope_vs_lower'] = {
        f'swing {a:g}': dict(poses=len(rs), poses_touching=sum(1 for r in rs if r['hits']),
                             touching=[dict(strokes=r['key'], parts=sorted({h[1].split(' (')[0] for h in r['hits']})[:4]) for r in rs if r['hits']][:30])
        for a, rs in sorted(env.items())}
    # 5. reach with the new O height
    tips = np.array([trace_pose(t)[1] for t in np.arange(0, t_end, 0.5)])
    gr = np.array([grid_pose(st)[1] for st in itertools.product(np.linspace(0, 60, 13), repeat=3)])
    ground_O = -K.O_Z
    rep['reach'] = dict(
        O_vehicle_mm=K.O_VEH.tolist(), O_above_R12_drawings_mm=K.O_Z - K.R12_DESIGN_O_Z,
        cycle_tooth_lowest_below_ground_mm=round(float(ground_O - tips[:, 1].min()), 1),
        cycle_tooth_reach_from_swing_axis_mm=round(float(tips[:, 0].max() + K.O_X), 1),
        grid_dig_depth_mm=round(float(ground_O - gr[:, 1].min()), 1),
        grid_reach_from_swing_axis_mm=round(float(gr[:, 0].max() + K.O_X), 1),
        grid_tooth_highest_above_ground_mm=round(float(gr[:, 1].max() - ground_O), 1),
        r12_drawings=dict(dig_depth_below_ground_mm=round(float(d.GROUND_Z - gr[:, 1].min()), 1), note='same strokes, ground at O - 155'),
        note='13 x 13 x 13 stroke grid, tooth tip T. Raising O by %g mm (B01X on the T101 ribs) takes the same from the dig depth and adds it to '
             'the dump height; reach is unchanged.' % (K.O_Z - K.R12_DESIGN_O_Z))
    rep['balance'] = balance()
    ok = (rep['interface']['pass'] and rep['arm_vs_upper']['penetrations'] == 0 and rep['demo_vs_lower']['penetrations'] == 0
          and rep['carry_pose_full_swing']['penetrations'] == 0 and rep['balance']['all_inside'])
    rep['status'] = 'PASS' if ok else 'FAIL'
    rep['seconds'] = round(time.time() - t0, 1)
    (K.ROOT / 'integration_check.json').write_text(json.dumps(rep, indent=1, default=float))
    print(rep['status'], rep['seconds'], 's')
    for k in ('arm_vs_upper', 'demo_vs_lower', 'carry_pose_full_swing'):
        print(k, rep[k]['states'], 'states', rep[k]['penetrations'], 'hits', rep[k]['closest'][:3], rep[k]['hits'][:3])
    print(json.dumps(rep['grid_envelope_vs_lower'])[:1500])
    print(json.dumps(rep['reach']))
    print(json.dumps(rep['balance'], default=float)[:2000])


if __name__ == '__main__':
    main()

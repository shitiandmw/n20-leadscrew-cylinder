"""Build the offline R12 viewer ../3D_preview.html: CAD meshes (cad/scene.json.gz), kinematic tables for
the manual mode and the two MuJoCo dig-cycle traces. Everything is inlined (three.js r128, no network).

Kinematics in the page: the boom angle depends only on the boom stroke, the stick pose in the boom
frame only on the stick stroke, and the bucket linkage in the stick frame only on the bucket stroke.
So three 1D tables (0.1 mm steps) composed in the browser reproduce r12_design.solve(); the build
checks that against poses_r12.body_poses() on a stroke grid before writing anything."""
import base64
import gzip
import itertools
import json
import math
import numpy as np
import r12_design as d
import motion_r12 as Mo
from poses_r12 import body_poses, DRIVES, BODIES

ROOT = d.rc.ROOT
REPO = ROOT.parent
SRC = ROOT / 'source'
STEP = 0.1
CHAIN = dict(boom=('base', 0, ['boom']), stick=('boom', 1, ['stick']), bucket=('stick', 2, ['bucket', 'side_link', 'h_link']))
PIN_BODY = dict(O='base', A='base', B='boom', C='boom', E='boom', D='stick', F='stick', J='stick', H='stick',
                R='h_link', Q='bucket', T='bucket')


def rel(parent, child):
    (po, pa), (co, ca) = parent, child
    c, s = math.cos(pa), math.sin(pa)
    dx = np.asarray(co, float) - np.asarray(po, float)
    return [c * dx[0] + s * dx[1], -s * dx[0] + c * dx[1], ca - pa]


def compose(p, r):
    c, s = math.cos(p[2]), math.sin(p[2])
    return [p[0] + c * r[0] - s * r[1], p[1] + s * r[0] + c * r[1], p[2] + r[2]]


def tables():
    ks = np.round(np.arange(0, 60 + 1e-9, STEP), 6)
    base = list(Mo.WAYPOINTS[0][1])
    out = {}
    for key, (parent, axis, kids) in CHAIN.items():
        rows = []
        for k in ks:
            st = list(base)
            st[axis] = float(k)
            _, P = body_poses(tuple(st))
            rows.append([v for kid in kids for v in rel(P[parent], P[kid])])
        a = np.array(rows)
        for j in range(2, a.shape[1], 3):
            a[:, j] = np.unwrap(a[:, j])
        out[key] = dict(parent=parent, bodies=kids, rows=np.round(a, 6).tolist())
    return out


def pin_locals():
    s, P = body_poses(Mo.WAYPOINTS[0][1])
    return {k: [round(v, 6) for v in rel(P[b], (s['pins'][k], 0.0))[:2]] for k, b in PIN_BODY.items()}


def js_like_poses(tab, pins, st):
    """Python twin of the page's compose step (used to verify the tables)."""
    def look(key, s):
        rows = tab[key]['rows']
        x = min(max(s / STEP, 0), len(rows) - 1.000001)
        i, f = int(x), x - int(x)
        return [a + (b - a) * f for a, b in zip(rows[i], rows[i + 1])]
    P = dict(base=[0.0, 0.0, 0.0])
    P['boom'] = compose(P['base'], look('boom', st[0]))
    P['stick'] = compose(P['boom'], look('stick', st[1]))
    r = look('bucket', st[2])
    for j, b in enumerate(tab['bucket']['bodies']):
        P[b] = compose(P['stick'], r[3 * j:3 * j + 3])
    W = {k: compose(P[PIN_BODY[k]], v + [0.0])[:2] for k, v in pins.items()}
    for name, a, b, *_ in DRIVES:
        u = np.subtract(W[b], W[a])
        L = float(np.hypot(*u))
        ang = math.atan2(u[1], u[0])
        P[f'{name}_barrel'] = [W[a][0], W[a][1], ang]
        P[f'{name}_rod'] = [W[a][0] + (L - d.ACT['closed']) * u[0] / L, W[a][1] + (L - d.ACT['closed']) * u[1] / L, ang]
    return P, W


def verify(tab, pins):
    worst_pose, worst_ang, worst_tip = 0.0, 0.0, 0.0
    grid = [0.0, 7.35, 15.0, 22.5, 33.33, 45.0, 52.05, 60.0]
    for st in itertools.product(grid, repeat=3):
        s, P = body_poses(st)
        J, W = js_like_poses(tab, pins, st)
        for b in BODIES:
            (o, a) = P[b]
            worst_pose = max(worst_pose, math.hypot(J[b][0] - o[0], J[b][1] - o[1]))
            worst_ang = max(worst_ang, abs((J[b][2] - a + math.pi) % (2 * math.pi) - math.pi))
        worst_tip = max(worst_tip, math.hypot(W['T'][0] - s['pins']['T'][0], W['T'][1] - s['pins']['T'][1]))
    rep = dict(poses=len(grid) ** 3, max_origin_error_mm=worst_pose, max_angle_error_rad=worst_ang, max_tip_error_mm=worst_tip)
    assert worst_pose < 0.01 and worst_tip < 0.01 and worst_ang < 1e-4, rep
    return rep


def pack_meshes():
    items = json.loads(gzip.decompress((ROOT / 'cad' / 'scene.json.gz').read_bytes()))
    out = []
    for it in items:
        v = np.asarray(it['v'], np.float32)
        t = np.asarray(it['t'], np.uint32)
        wide = len(v) // 3 >= 65536
        out.append(dict(name=it['name'], body=it['body'], color=it['color'], kind=it['kind'], wide=wide,
                        v=base64.b64encode(v.astype('<f4').tobytes()).decode(),
                        t=base64.b64encode(t.astype('<u4' if wide else '<u2').tobytes()).decode()))
    return out


def phases():
    out, t = [], 0.0
    for i, seg in enumerate(Mo.SEGMENTS):
        end = seg['t1'] if i < len(Mo.SEGMENTS) - 1 else Mo.DURATION
        a, b = seg['name'].split(' -> ')
        out.append(dict(id=i, title=b[0].upper() + b[1:], start=round(t, 3), end=round(end, 3), move=[round(seg['t0'], 3), round(seg['t1'], 3)]))
        t = end
    return out


def clash_summary():
    c = json.loads((ROOT / 'cad' / 'clash_check.json').read_text())
    assert c['status'] == 'PASS'
    return dict(penetrations=c['penetrations'], poses=c['poses_grid'] + c['poses_cycle'], parts=c['parts'],
                min_inplane=c['closest_inplane'][0]['gap_mm'])


def sync_note():
    r = json.loads((ROOT / 'simulation' / 'sync_bias_report.json').read_text())['poses']['boom']['mujoco_force_N']
    return (f"Boom pair needs synchronised feedback: a 0.5 mm sensor offset between the two boom drives at the worst "
            f"hold pose loads them {r['boom_L']:.0f} N / {r['boom_R']:.0f} N (clamped) instead of sharing the load.")


def main():
    tab, pins = tables(), pin_locals()
    ver = verify(tab, pins)
    sim = ROOT / 'simulation'
    reports = {k: json.loads((sim / f'{k}_report.json').read_text()) for k in ('payload_150g', 'unloaded')}
    traces = {k: base64.b64encode((sim / f'{k}_trace.json.gz').read_bytes()).decode() for k in reports}
    motion = json.loads((ROOT / 'motion.json').read_text())
    config = dict(
        step=STEP, tables=tab, pins=pins, closed=d.ACT['closed'], stroke=d.ACT['stroke'], ground_z=d.GROUND_Z,
        turntable_z=d.TURNTABLE_Z, swing_x=d.SWING_X, thrust_cont=d.ACT['thrust_cont'], thrust_stall=d.ACT['thrust_stall'],
        drives=[dict(name=n, a=a, b=b, y=float(y)) for n, a, b, y, *_ in DRIVES], duration=round(Mo.DURATION, 3),
        phases=phases(), waypoints=motion['waypoints'], default=list(Mo.WAYPOINTS[0][1]),
        reports={k: dict(peak_force_N=v['peak_force_N'], tracking_mm=v['max_stroke_tracking_error_mm'],
                         closure_mm=v['max_pin_closure_error_mm'], clamp_s=v['time_at_force_clamp_s'], passed=v['pass'])
                 for k, v in reports.items()},
        pin_body=PIN_BODY, clash=clash_summary(), sync_note=sync_note())
    html = (SRC / 'viewer_r12.html').read_text()
    subs = {'__THREE__': (REPO / 'actuator_v6/source/vendor/three.min.js').read_text(),
            '__ORBIT__': (REPO / 'actuator_v6/source/vendor/OrbitControls.js').read_text(),
            '__MESHES__': json.dumps(pack_meshes(), separators=(',', ':')),
            '__CONFIG__': json.dumps(config, separators=(',', ':')),
            '__TRACES__': json.dumps(traces, separators=(',', ':'))}
    for k, v in subs.items():
        assert html.count(k) == 1, k
        html = html.replace(k, v)
    (ROOT / '3D_preview.html').write_text(html)
    (SRC / 'viewer_tables_check.json').write_text(json.dumps(ver, indent=1))
    cases = []
    for st in itertools.product([0.0, 12.5, 30.0, 47.5, 60.0], repeat=3):
        sol, P = body_poses(st)
        cases.append(dict(strokes=list(st), poses={b: [float(P[b][0][0]), float(P[b][0][1]), float(P[b][1])] for b in BODIES},
                          tip=[float(x) for x in sol['pins']['T']]))
    (SRC / 'viewer_cases.json').write_text(json.dumps(cases))
    print('3D_preview.html', round(len(html) / 1e6, 2), 'MB', json.dumps(ver))


if __name__ == '__main__':
    main()

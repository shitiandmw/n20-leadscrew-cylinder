"""R12 work cycle: stroke waypoints -> smooth, speed-limited reference for the three drive axes.

The two boom drives share the boom reference. Each segment uses a quintic (minimum-jerk) blend; its
duration is set so the fastest axis peaks at PEAK_SPEED, below the drive's loaded speed. Writes
../motion.json (waypoints, segments, a 10 Hz reference and kinematic checks)."""
import json
import math
import numpy as np
import r12_design as d

PEAK_SPEED = 0.80          # mm/s planned peak stroke rate: planned for the earlier 6 V drive (1.25 mm/s without
                           # load) and kept; the 12 V drive runs 8.2 mm/s without load, 6.2 mm/s at the 150 g case
DWELL = 3.0                # s at each waypoint
WAYPOINTS = [              # name, (boom, stick, bucket) strokes in mm
    ('carry', (45.0, 38.0, 50.0)),
    ('reach out, bucket open', (32.0, 6.0, 8.0)),
    ('penetrate', (10.0, 12.0, 18.0)),
    ('crowd the stick', (8.0, 42.0, 30.0)),
    ('curl the bucket', (12.0, 46.0, 58.0)),
    ('raise', (52.0, 40.0, 60.0)),
    ('dump', (55.0, 22.0, 4.0)),
    ('carry', (45.0, 38.0, 50.0)),
]


def _segments():
    t, segs = 0.0, []
    for (n0, s0), (n1, s1) in zip(WAYPOINTS[:-1], WAYPOINTS[1:]):
        s0, s1 = np.array(s0), np.array(s1)
        T = max(1.875 * float(np.max(np.abs(s1 - s0))) / PEAK_SPEED, 4.0)
        segs.append(dict(name=f'{n0} -> {n1}', t0=t + DWELL, t1=t + DWELL + T, s0=s0, s1=s1))
        t += DWELL + T
    return segs, t + DWELL


SEGMENTS, DURATION = _segments()


def reference(t):
    """Stroke reference (boom, stick, bucket) and its rate at time t (mm, mm/s)."""
    s, v = np.array(WAYPOINTS[0][1]), np.zeros(3)
    for seg in SEGMENTS:
        if t < seg['t0']:
            return s, v
        T = seg['t1'] - seg['t0']
        if t <= seg['t1']:
            x = (t - seg['t0']) / T
            h = 10 * x ** 3 - 15 * x ** 4 + 6 * x ** 5
            dh = (30 * x ** 2 - 60 * x ** 3 + 30 * x ** 4) / T
            return seg['s0'] + h * (seg['s1'] - seg['s0']), dh * (seg['s1'] - seg['s0'])
        s = seg['s1']
    return s, v


def phase(t):
    for seg in SEGMENTS:
        if t < seg['t0']:
            return 'hold at ' + seg['name'].split(' -> ')[0]
        if t <= seg['t1']:
            return seg['name']
    return 'hold at ' + WAYPOINTS[-1][0]


def build():
    ts = np.arange(0.0, DURATION + 1e-9, 0.1)
    rows, tips, lows = [], [], []
    from shapely.ops import unary_union
    bucket_out = unary_union([d.bucket_parts()['shell'], d.bucket_parts()['teeth']])
    for t in ts:
        s, v = reference(t)
        sol = d.solve(tuple(s))
        T = sol['pins']['T']
        rows.append([round(float(t), 2)] + [round(float(x), 4) for x in s] + [round(float(x), 4) for x in v])
        tips.append(T)
    for name, st in WAYPOINTS:
        sol = d.solve(st)
        lows.append(d.place(bucket_out, *sol['poses']['bucket']).bounds[1])
    tips = np.array(tips)
    refs = np.array([r[1:4] for r in rows])
    rates = np.array([r[4:7] for r in rows])
    out = dict(
        description='R12 dig cycle on the X1 crawler (ground Z -155): strokes of the boom pair, stick and bucket drives',
        peak_speed_planned_mm_s=PEAK_SPEED, dwell_s=DWELL, duration_s=round(DURATION, 2),
        waypoints=[dict(name=n, strokes_mm=list(s), joint_angles_deg=[round(a, 2) for a in d.joint_angles(s)],
                        tip_mm=[round(float(x), 2) for x in d.solve(s)['pins']['T']], bucket_lowest_z_mm=round(float(z), 2))
                   for (n, s), z in zip(WAYPOINTS, lows)],
        segments=[dict(name=s['name'], t0=round(s['t0'], 2), t1=round(s['t1'], 2)) for s in SEGMENTS],
        checks=dict(stroke_min_mm=round(float(refs.min()), 3), stroke_max_mm=round(float(refs.max()), 3),
                    peak_rate_mm_s=round(float(np.abs(rates).max()), 3),
                    tip_lowest_z_mm=round(float(tips[:, 1].min()), 1), tip_depth_below_ground_mm=round(float(d.GROUND_Z - tips[:, 1].min()), 1),
                    tip_highest_z_mm=round(float(tips[:, 1].max()), 1), tip_reach_max_mm=round(float(tips[:, 0].max() - d.SWING_X), 1),
                    within_strokes=bool(refs.min() >= 0 and refs.max() <= 60)),
        columns=['t_s', 'boom_mm', 'stick_mm', 'bucket_mm', 'boom_rate', 'stick_rate', 'bucket_rate'],
        reference=rows)
    (d.rc.ROOT / 'motion.json').write_text(json.dumps(out, separators=(',', ':')))
    return out


if __name__ == '__main__':
    o = build()
    print(json.dumps({k: v for k, v in o.items() if k not in ('reference',)}, indent=1))

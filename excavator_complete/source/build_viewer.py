"""Pack the complete machine into the offline single-file demonstration ../3D_preview.html.

Data, all read from the subsystem folders (see machine.py):
  meshes      J9 track module (drawn twice, the right one mirrored), chain links, X-frame, RU66, turntable, body,
              electronics, B01X and R12 (per body frame)
  kinematics  R12's three 1D stroke tables (as excavator_arm_r12/source/build_viewer_r12.py, re-verified here)
  dynamics    the R12 MuJoCo dig cycle with 150 g (simulation/payload_150g_trace.json.gz), replayed for the arm
  timeline    the demonstration: travel, dig, swing to 90 deg, dump, swing back, carry, travel back. Travel and swing
              are kinematic (minimum-jerk at the J9 and swing-drive speeds); the arm is the MuJoCo trace at 20 x
  checks      ../integration_check.json and the subsystem reports
Run with the R12 interpreter from this folder.
"""
import sys
import json
import base64
import numpy as np
import common as K
import machine as M

sys.path.insert(0, str(K.R12 / 'source'))
import r12_design as d               # noqa: E402
import motion_r12 as Mo              # noqa: E402
import build_viewer_r12 as BV        # noqa: E402


def pack_mesh(v, t):
    v = np.asarray(v, np.float32).reshape(-1, 3)
    t = np.asarray(t).reshape(-1, 3)
    wide = len(v) >= 65536
    return dict(wide=wide, v=base64.b64encode(v.astype('<f4').tobytes()).decode(),
                t=base64.b64encode(t.astype('<u4' if wide else '<u2').tobytes()).decode())


# ------------------------------------------------------------------ assembly steps and exploded offsets
STEPS = [
    ('Tracks', 'Two J9 tracks, built on the bench: rollers on their axles, the JGY-370 motor and the J909 pod housing. '
               'The right track uses the mirrored J901 and J909 prints. Hold both at their final 340 mm spacing.'),
    ('X-frame', 'Lower the bare X101 frame vertically (80 mm approach) into the open-top seats in both track main plates. '
                'Four joints, each clamped by two M4 x 25 through plain holes with the washers and nuts outside. Then the rear '
                'sprockets and chains, and the belly cover below.'),
    ('Slewing ring', 'Slip ring into the frame collar from below (3 x M3), ring gear X103 onto the frame top (6 x M3 countersunk '
                     'from below), then the THK RU66 into the gear bore with 8 x M4 x 30, nuts below.'),
    ('Turntable', 'Hub adapter T104 and centre frame T101 on the RU66 inner ring (8 x M4 x 20). The swing motor goes in on the '
                  'T102 slide; the mesh is set with a paper strip, then the drag pads. Press the body\'s 4 M3 inserts into the rib tops now.'),
    ('Arm', 'B01X onto the T101 rib tops with the 4 existing M6 x 40 bolts (nuts in the T101 pockets). Then the R12 arm as its '
            'ASSEMBLY.md: boom on pin O, both boom drives on A and B, stick drive and stick, bucket drive, linkage and bucket.'),
    ('Counterweight', 'Counterweight B101, its steel shot poured in during a print pause, with 2 x M4 x 12 from inside T101.'),
    ('Left half', 'Left half B102 with the cab interior, operator, handrail and the main board rev A in its bay: lower it, slide '
                  'it 10 mm inward onto its hook under the base plate, 2 x M3 down the sleeves.'),
    ('Right half', 'Right half B103 with the tank, stairs and toolbox (main switch, fuse, charge jack): the same fixing.'),
    ('Battery hatch', 'Battery hatch B106 with the three 18650 cells hanging under it; 4 magnets hold it on the hood.'),
]


def step_and_vectors(p):
    """(assembly step, approach vector, exploded offset); vectors in the upper or vehicle frame, mm."""
    n, s = p['name'], p['sys']
    if s == 'track':
        return 0, [0, 0, 0], [0, 0, 0]                       # the track groups carry these (see the page)
    if s == 'xframe':
        if p.get('group') == 'cover' or n.startswith('cover_screw'):
            return 1, [0, 0, -60], [0, 0, -70]
        if n.startswith('mount_'):
            return 1, [0, 0, 80], [0, 0, 0]
        return 1, [0, 0, 80], [0, 0, 0]
    if s == 'slew':
        if n.startswith(('slip_ring', 'collar_insert', 'T106')):
            return 2, [0, 0, -70], [0, 0, -80]
        if n.startswith(('X103', 'ring_gear')):
            return 2, [0, 0, 60], [0, 0, 30]
        return 2, [0, 0, 90], [0, 0, 55]                     # RU66 and its seat hardware
    if s == 'turntable':
        if n.startswith(('arm_bolt', 'arm_nut')):
            return 4, [0, 0, 120], [0, 0, 0]
        return 3, [0, 0, 90], [0, 0, 0]
    if s == 'arm':
        return 4, [0, 0, 0], [0, 0, 0]                       # the arm mount group carries these
    part = p.get('part')
    if part == 'counterweight':
        return 5, [-110, 0, 0], [-110, 0, 40]
    if part == 'left':
        return 6, [0, 10, 70], [0, 120, 60]
    if part == 'right' or part == 'fixed':
        return 7, [0, -10, 70], [0, -120, 60]
    if part == 'hatch':
        return 8, [0, 0, 90], [0, 0, 190]
    raise ValueError(n)


# ------------------------------------------------------------------ demonstration timeline
def timeline(trace):
    seg = {s['name']: (s['t0'], s['t1']) for s in Mo.SEGMENTS}
    t_raise, t_dump = seg['raise -> dump'][0], seg['dump -> carry'][0]
    t_end = trace['frames'][-1]['t']
    rows, v, real = [], 0.0, 0.0

    def add(title, kind, rd, rate, caption, **kw):
        nonlocal v, real
        vd = rd / rate
        rows.append(dict(id=len(rows), title=title, kind=kind, v0=round(v, 4), vd=round(vd, 4), real0=round(real, 3), rd=round(rd, 3),
                         rate=rate, caption=caption, **kw))
        v += vd
        real += rd
    X, S = K.TRAVEL_MM, K.SWING_DUMP_DEG
    add('Travel forward', 'travel', K.TRAVEL_TIME_S, 1.0,
        'Both J9 tracks drive forward %.0f mm (JGY-370-1260, 30 rpm: 88-120 mm/s). Kinematic playback of the chain and sprocket; '
        'the ground run stays still on the ground.' % X, x=[0.0, X], sw=0.0, t=0.0)
    add('Dig', 'arm', t_raise, K.ARM_PLAYBACK,
        'The R12 dig cycle from its MuJoCo simulation (150 g in the bucket): reach out, penetrate, crowd the stick, curl the bucket, '
        'raise. Shown at %g x: the leadscrew drives move at most 0.8 mm/s. Soil forces are not modelled.' % K.ARM_PLAYBACK,
        x=X, sw=0.0, t=[0.0, t_raise])
    add('Swing to dump', 'swing', K.SWING_TIME_S, 1.0,
        'The upper turns %.0f deg to the left (cab side) on the RU66, driven by the JGY-370 pinion on the X103 ring gear (4:1). '
        'Minimum-jerk move, peak 42 deg/s (7.5 rpm no-load limit 45 deg/s); kinematic playback, the arm holds the raise pose.' % S,
        x=X, sw=[0.0, S], t=t_raise)
    add('Dump', 'arm', t_dump - t_raise, K.ARM_PLAYBACK,
        'Over the left track: the stick goes out and the bucket opens (MuJoCo trace, %g x).' % K.ARM_PLAYBACK, x=X, sw=S, t=[t_raise, t_dump])
    add('Swing back', 'swing', K.SWING_TIME_S, 1.0, 'Back to the front, holding the dump pose (kinematic).', x=X, sw=[S, 0.0], t=t_dump)
    add('Carry', 'arm', t_end - t_dump, K.ARM_PLAYBACK, 'The arm returns to the carry pose (MuJoCo trace, %g x).' % K.ARM_PLAYBACK,
        x=X, sw=0.0, t=[t_dump, t_end])
    add('Travel back', 'travel', K.TRAVEL_TIME_S, 1.0, 'The tracks reverse to the start (kinematic).', x=[X, 0.0], sw=0.0, t=t_end)
    # payload shown from the end of the curl until the bucket has opened in the dump
    t_curl = seg['curl the bucket -> raise'][0]
    t_open = next(f['t'] for f in trace['frames'] if f['t'] > t_raise and f['s'][3] < 30.0)
    return rows, dict(payload_from=t_curl, payload_to=t_open)


def checks_summary():
    ic = json.loads((K.ROOT / 'integration_check.json').read_text())
    sub = {}
    for key, path in [('J9 track', 'track_wheel_jgy370/J9/validation.json'),
                      ('X1 joints (rev F)', 'track_wheel_jgy370/X1/arc_seat_mount_validation.json'),
                      ('Turntable R3', 'track_wheel_jgy370/X1/turntable_validation.json'),
                      ('Body B1', 'track_wheel_jgy370/X1/body_validation.json'),
                      ('R12 arm', 'excavator_arm_r12/validation_summary.json')]:
        try:
            j = json.loads((K.REPO / path).read_text())
            st = j.get('status') or j.get('overall') or j.get('result')
            if st is None and 'pass' in j:
                st = 'PASS' if j['pass'] else 'FAIL'
        except FileNotFoundError:
            st = 'missing'
        sub[key] = dict(file=path, status=str(st))
    return ic, sub


def main():
    parts, links, cfg = M.load()
    tab, pins = BV.tables(), BV.pin_locals()
    ver = BV.verify(tab, pins)
    trace_path = K.R12 / 'simulation/payload_150g_trace.json.gz'
    trace = K.load_gz(trace_path)
    tl, pay = timeline(trace)
    ic, sub = checks_summary()

    j9 = K.load_gz(K.J9 / 'source/j9_scene.json.gz')
    module = [dict(name=p['name'], color=p['color'], kind=p['kind'], group=p['group'], **pack_mesh(p['vertices'], p['triangles']))
              for p in j9['unit']]
    link = [dict(name=l['name'], color=l['color'], **pack_mesh(l['vertices'], l['triangles'])) for l in j9['link']]
    out, counts = [], {}
    for p in parts:
        if p['mover'] == 'track':
            if p['side'] > 0:
                counts['track'] = counts.get('track', 0) + 2
            continue
        stp, app, exp = step_and_vectors(p)
        counts[p['sys']] = counts.get(p['sys'], 0) + 1
        out.append(dict(name=p['name'], sys=p['sys'], mover=p['mover'], color=p['color'], kind=p['kind'], step=stp, app=app, exp=exp,
                        group=p.get('group'), part=p.get('part'), new=p.get('new', False), **pack_mesh(p['v'], p['t'])))
    counts['track'] += 2 * 2 * len(cfg['j9']['pins'])       # shoes and pins
    sysinfo = {k: dict(label=v[0], folder=v[1], revision=v[2], meshes=counts.get(k, 0)) for k, v in M.SYS.items()}
    config = dict(
        j9=cfg['j9'], track_y=cfg['track_y'], key=cfg['key'], pinion_axis=cfg['pinion_axis'], ratio=cfg['ratio'],
        O=K.O_VEH.tolist(), O_design_z=K.R12_DESIGN_O_Z, step=BV.STEP, tables=tab, pins=pins, pin_body=BV.PIN_BODY, closed=d.ACT['closed'],
        drives=[dict(name=n, a=a, b=b, y=float(y)) for n, a, b, y, *_ in BV.DRIVES], default=list(Mo.WAYPOINTS[0][1]),
        waypoints=[dict(name=n, strokes=list(s)) for n, s in Mo.WAYPOINTS[:-1]], phases=BV.phases(), duration=round(Mo.DURATION, 3),
        payload=dict(com=[d.MASS['payload'][1][0], 0.0, d.MASS['payload'][1][1]], kg=d.PAYLOAD, **pay),
        thrust_cont=d.ACT['thrust_cont'])
    data = dict(cfg=config, module=module, link=link, parts=out, sys=sysinfo, steps=[dict(title=a, caption=b) for a, b in STEPS],
                timeline=tl, trace=base64.b64encode(trace_path.read_bytes()).decode(), checks=ic, subsystem_reports=sub)
    html = (K.HERE / 'viewer.html').read_text()
    for k, v in {'__THREE__': (K.VENDOR / 'three.min.js').read_text(), '__ORBIT__': (K.VENDOR / 'OrbitControls.js').read_text(),
                 '__DATA__': json.dumps(data, separators=(',', ':'))}.items():
        assert html.count(k) == 1, k
        html = html.replace(k, v)
    (K.ROOT / '3D_preview.html').write_text(html)
    (K.HERE / 'viewer_tables_check.json').write_text(json.dumps(ver, indent=1))
    print('3D_preview.html', round(len(html) / 1e6, 1), 'MB;', len(out), 'parts +', len(module), 'x 2 track parts;', 'timeline',
          round(tl[-1]['v0'] + tl[-1]['vd'], 1), 's shown,', round(tl[-1]['real0'] + tl[-1]['rd'], 1), 's real;', json.dumps(sub))


if __name__ == '__main__':
    main()

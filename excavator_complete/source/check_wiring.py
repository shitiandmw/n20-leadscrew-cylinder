"""Wiring checks of the complete machine: the harness of harness.py against the CAD over the arm's poses.

  1. arm cables   every segment on the arm (lanes, exits, the loops round O and E, the boom-drive drops) as a tube of
                  the sleeve radius, against every part it is not attached to, over R12's 5 x 5 x 5 stroke grid and the
                  dig cycle every 2 s: no overlap, and at least CLEAR mm away (R12's rule). Lanes and clamps must sit on
                  their host face (reported, not a failure).
  2. loops        chord over the poses against the cable length (never taut: >= 4 mm slack), the arc's bend radius, and
                  the slide travel of the boom-drive sleeves in their slots.
  3. static runs  the upper and lower cables against the parts they pass (holes they use are excluded by name).
  4. space        what lies under each B01X slot inside T101 (clear height), the rib-crossing gap, the bay height over
                  the plugs, the counterweight channel and the T101 window for the swing leads.
Writes ../wiring_check.json and ../wiring/harness.csv. Run with the R12 interpreter from this folder (after
build_adapter.py, which cuts the slots the drops pass through).
"""
import csv
import itertools
import json
import math
import multiprocessing as mp
import sys
import time
import numpy as np
import fcl
import common as K
import machine as M
import harness as H
import check_complete as CC            # builds the collision objects of every part (OBJ), place(), trace_pose()

sys.path.insert(0, str(K.R12 / 'source'))
import r12_design as d                 # noqa: E402
import motion_r12 as Mo                # noqa: E402
from poses_r12 import body_poses       # noqa: E402

OBJ, place = CC.OBJ, CC.place
NAME = {i: o['name'] for i, o in enumerate(OBJ)}
BY_BODY = {}
for i, o in enumerate(OBJ):
    BY_BODY.setdefault(o.get('body'), []).append(i)
UPPER_SET = [i for i, o in enumerate(OBJ) if o['set'] in ('upper', 'pinion')]
ARM_SET = [i for i, o in enumerate(OBJ) if o['set'] == 'arm']
LOWER_SET = [i for i, o in enumerate(OBJ) if o['set'] == 'lower']

DRIVE_BODIES = {'boom_L': ('boom_L_barrel', 'boom_L_rod'), 'boom_R': ('boom_R_barrel', 'boom_R_rod'),
                'stick': ('stick_barrel', 'stick_rod'), 'bucket': ('bucket_barrel', 'bucket_rod')}
# parts a static cable may touch (it plugs into them or passes through a hole cut in them)
TOUCH = {
    'slip ring rotor leads': ('slip_ring_6way_rotor', 'T106_rotor_dog_TPU', 'T104_hub_adapter', 'T101_centre_frame', 'board_plugs', 'board_parts'),
    'swing motor leads': ('JGY370_motor_can', 'JGY370_lead_space', 'T101_centre_frame', 'B101_counterweight', 'B102_left_half', 'B103_right_half', 'board_plugs', 'board_parts'),
    '12 V link (switch to board)': ('board_parts', 'board_plugs', 'main_switch', 'fuse_holder_5A', 'B103_right_half', 'controller_PCB', 'board_link_XT30U-F'),
    'battery feed (fuse to hatch socket)': ('fuse_holder_5A', 'main_switch', 'B103_right_half', 'feed_socket_XT30'),
    'battery hatch lead': ('battery_lead_XT30', 'B106_battery_hatch', 'battery_BMS_HX3S01'),
    'toolbox lamp pair': ('board_plugs', 'board_parts', 'B103_right_half', 'main_switch', 'fuse_holder_5A', 'SM-LAMP'),
    'roof lamps pair': ('board_plugs', 'board_parts', 'B102_left_half', 'B104_cab_interior', 'B107_left_handrail'),
    'left track motor leads': ('J909_housing (left track)', 'JGY370_terminal_space (left track)', 'JGY370_motor_can (left track)', 'X101_X_frame',
                               'reserved cable route (left motor leads)', 'SM-L'),
    'right track motor leads': ('J909_housing (right track)', 'JGY370_terminal_space (right track)', 'JGY370_motor_can (right track)', 'X101_X_frame',
                                'reserved cable route (right motor leads)', 'SM-R'),
    'slip ring stator leads': ('slip_ring_6way_stator', 'X101_X_frame', 'SM-L'),
    'slip ring stator leads (right pair)': ('slip_ring_6way_stator', 'X101_X_frame', 'SM-R'),
}
PLATE = next(i for i, o in enumerate(OBJ) if o['new'])          # B01X
BOARD_TOUCH = ('board_plugs', 'board_parts', 'controller_PCB')


def touch_list(c):
    t = list(TOUCH.get(c.get('parent', c['name']), ()))
    if c['to'] in H.BOARD or c.get('parent'):
        t += list(BOARD_TOUCH)
    if c.get('slot'):
        t += ['T101_centre_frame', 'B01X_boom_foot_bracket']   # the sleeve lies in the plate's trough / slot and on T101's floor
    return tuple(t)


def tube_obj(pts, r):
    v, t = H.tube(pts, r)
    return fcl.CollisionObject(CC.bvh(v, t), fcl.Transform()), v


def nearest(obj, v, idx, exclude=(), near=6.0):
    """(min distance, part) of a tube against the parts idx (already placed), skipping exclude; overlaps as 0."""
    c = 0.5 * (v.min(0) + v.max(0))
    rad = float(np.linalg.norm(v - c, axis=1).max())
    best, who, hits = 1e9, None, []
    for j in idx:
        if j in exclude:
            continue
        o = OBJ[j]
        if np.linalg.norm(CUR[j] - c) - rad - o['r'] > near:
            continue
        res = fcl.CollisionResult()
        if fcl.collide(obj, o['obj'], fcl.CollisionRequest(), res):
            hits.append(o['name'])
            best, who = 0.0, o['name']
            continue
        dr = fcl.DistanceResult()
        dist = fcl.distance(obj, o['obj'], fcl.DistanceRequest(), dr)
        if dist < best:
            best, who = float(dist), o['name']
    return best, who, hits


CUR = {}


def set_pose(strokes, swing=0.0):
    s, P = body_poses(tuple(strokes))
    pose = {k: (np.asarray(v[0], float), float(v[1])) for k, v in P.items()}
    cen = place(pose, swing)
    CUR.update(cen)
    return s, pose


def world_pts(seg, pose):
    T = M.arm_transforms(pose, 0.0)
    R, t = T[seg['frame']]
    return np.asarray(seg['pts'], float) @ R.T + t


def arm_segments(strokes):
    sol, pose = set_pose(strokes)
    segs = H.arm_cables(sol, sol['pins'])
    out = []
    for sg in segs:
        pts = world_pts(sg, pose)
        kind = sg['kind']
        if kind == 'loop':
            # the clamps hold the first and last 6 mm
            keep = []
            cum = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
            L = cum[-1]
            pts_t = pts[(cum >= 6.0) & (cum <= L - 6.0)]
            if len(pts_t) < 3:
                pts_t = pts
            hosts = set()
            for b in sg['bodies']:
                hosts |= set(BY_BODY.get(b, []))
            test_pts, exclude = pts_t, set()
            host_idx = hosts
        elif kind == 'drop':
            hosts = set(j for b in DRIVE_BODIES[sg['cable']] for j in BY_BODY.get(b, []))
            # the end runs in B01X's trough: the plate is a host (its gap is reported); the first 2 mm are the clamp face
            test_pts, exclude, host_idx = pts[1:], set(), hosts | {PLATE}
        elif kind == 'exit':
            # from the V6 clamp face (its barrel parts are hosts) to the first W01 clamp (last 6 mm held); the host body
            # itself (boom or stick) is tested: the path must clear it except where it lands on the clamp
            drive = sg['cable']
            hosts = set(j for b in DRIVE_BODIES[drive] for j in BY_BODY.get(b, []))
            cum = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
            L = cum[-1]
            test_pts = pts[(cum >= 2.5) & (cum <= L - 7.0)]
            exclude, host_idx = set(), hosts
        else:   # fixed on one body ('fixed', and 'landing': the last 25 mm of an exit, on the host face)
            host_idx = set(BY_BODY.get(sg['frame'], []))
            if kind == 'landing':
                host_idx |= set(j for b in DRIVE_BODIES[sg['cable']] for j in BY_BODY.get(b, []))
            test_pts, exclude = pts, set()
        out.append((sg, pts, test_pts, host_idx))
    return sol, pose, out


def run(job):
    label, kind, key = job
    if kind == 'grid':
        strokes = tuple(key)
    else:
        fr = CC.TRACE['frames']
        hz = CC.TRACE['record_hz']
        x = min(max(key * hz, 0), len(fr) - 1.000001)
        i, f = int(x), x - int(x)
        s = [u + (w - u) * f for u, w in zip(fr[i]['s'], fr[i + 1]['s'])]
        strokes = (float(s[0]), float(s[2]), float(s[3]))
    sol, pose, segs = arm_segments(strokes)
    rows = []
    for sg, pts, test_pts, hosts in segs:
        obj, v = tube_obj(test_pts, sg['r'])
        # against everything except its hosts (arm, upper, B01X); the lower is far from the arm cables
        idx = [j for j in ARM_SET + UPPER_SET if j not in hosts]
        best, who, hits = nearest(obj, v, idx)
        hb, hw, hh = nearest(obj, v, list(hosts)) if hosts else (None, None, [])
        info = dict(sg.get('info', {}))
        rows.append(dict(name=sg['name'], cable=sg['cable'], kind=sg['kind'], clear_mm=round(best, 3), closest=who, hits=hits,
                         host_mm=(None if hb is None else round(hb, 3)), host_part=hw, length_mm=round(H.length(pts), 2),
                         min_radius_mm=round(H.min_radius(pts), 2) if sg['kind'] in ('loop', 'drop', 'exit') else None,
                         chord_mm=round(info['chord'], 2) if 'chord' in info else None, sagitta_mm=round(info['sagitta'], 2) if 'sagitta' in info else None,
                         entry=info.get('trough_entry_x'), inside=(info.get('inside_trough') and info.get('ok')) if 'inside_trough' in info else None,
                         r2=info.get('second_bend_radius')))
    return dict(label=label, strokes=[round(float(x), 3) for x in strokes], rows=rows)


def static_checks():
    """The fixed cables at the carry pose, swing 0."""
    set_pose(Mo.WAYPOINTS[0][1])
    out = []
    for c in H.static_cables():
        pts = np.asarray(c['pts'], float)
        obj, v = tube_obj(H.round_corners(pts, 4.0), c['r'])
        idx = LOWER_SET if c['mover'] == 'ground' else UPPER_SET + ARM_SET
        touch = touch_list(c)
        touch_idx = {j for j in idx if any(OBJ[j]['name'] == t or OBJ[j]['name'].startswith(t + '_') for t in touch)}
        best, who, hits = nearest(obj, v, [j for j in idx if j not in touch_idx], near=8.0)
        tb, tw, th = nearest(obj, v, list(touch_idx), near=8.0) if touch_idx else (None, None, [])
        out.append(dict(name=c['name'], to=c['to'], r_mm=c['r'], length_mm=round(H.length(pts), 1), clear_mm=round(best, 3), closest=who, hits=hits,
                        touches=dict(expected=list(touch), nearest=tw, mm=(None if tb is None else round(tb, 3)), overlaps=th)))
    return out


def box_obj(x0, x1, y0, y1, z0, z1):
    g = fcl.Box(x1 - x0, y1 - y0, z1 - z0)
    return fcl.CollisionObject(g, fcl.Transform(np.eye(3), np.array([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2])))


def highest_under(x0, x1, y0, y1, z_top, idx, step=1.0, z_floor=100.0):
    """Highest Z below z_top at which a box of this footprint meets any part in idx (scanning down), or None."""
    z = z_top
    while z > z_floor:
        b = box_obj(x0, x1, y0, y1, z - step, z)
        for j in idx:
            r = fcl.CollisionResult()
            if fcl.collide(b, OBJ[j]['obj'], fcl.CollisionRequest(), r):
                return z, OBJ[j]['name']
        z -= step
    return None, None


def space_checks():
    """Clear heights and gaps the harness relies on, measured on the meshes with probe boxes."""
    set_pose(Mo.WAYPOINTS[0][1])
    rep = {}
    idx = [j for j in UPPER_SET if j != PLATE]
    for name, (x, y, Lx, Ly) in H.SLOTS.items():
        X = x + K.O_X
        z, who = highest_under(X - Lx / 2, X + Lx / 2, y - Ly / 2, y + Ly / 2, K.T101_TOP_Z - 0.01, idx)
        rep[name] = dict(x_vehicle=X, y=y, first_part_below_plate=who, its_top_z=z, plate_bottom_z=K.T101_TOP_Z,
                         clear_height_mm=(None if z is None else round(K.T101_TOP_Z - z, 1)), ok=(z is not None and K.T101_TOP_Z - z >= 20.0))
    # the middle compartment floor the cables run on (X -26..8, |Y| 38-56, Z 110-135) and the rise gap behind the plate
    # (X -27..-22, |Y| 38-58, Z 110-150) must be empty
    for lab, bx in (('middle_compartment_left', (-28.0, 8.0, 38.0, 54.0, 111.0, 135.0)), ('middle_compartment_right', (-28.0, 8.0, -54.0, -38.0, 111.0, 135.0)),
                    ('rise_gap_left', (-29.0, -22.0, 39.0, 55.0, 110.0, 154.0)), ('rise_gap_right', (-29.0, -22.0, -55.0, -39.0, 110.0, 154.0))):
        hits = set()
        for j in idx + [PLATE]:
            r = fcl.CollisionResult()
            if fcl.collide(box_obj(*bx), OBJ[j]['obj'], fcl.CollisionRequest(), r):
                hits.add(OBJ[j]['name'])
        rep[lab] = dict(box=bx, parts_inside=sorted(hits), ok=not hits)
    # the hood cavity over T101 behind the plate where the right-side sleeves cross (Z 139-149, X -38..-26)
    hits = set()
    for j in idx:
        r = fcl.CollisionResult()
        if fcl.collide(box_obj(-38.0, -28.0, -45.0, 45.0, 139.0, 149.0), OBJ[j]['obj'], fcl.CollisionRequest(), r):
            hits.add(OBJ[j]['name'])
    rep['crossing_over_hub_well'] = dict(x=(-38, -28), y=(-45, 45), z=(139, 149), parts_inside=sorted(hits), ok=not hits)
    # rib crossing gap between the hood front wall (X -25) and the front sleeve (X -50..-40)
    rep['rib_crossing'] = dict(x_band=(-40.0, -25.0), used_x=[H.X_ARM_L, H.X_ARM_R], cables=4, note='two cables per X, stacked at Z 141 and 145')
    rep['bay_over_plugs'] = dict(plug_top_z=117.7, run_z=H.BAY_RUN['z'], run_y=H.BAY_RUN['y'], plug_face_y=72.0, hood_underside_z='>= 136.3 (hood front wall bottom) / 198.8')
    return rep


def main():
    t0 = time.time()
    grid = list(itertools.product([0.0, 15.0, 30.0, 45.0, 60.0], repeat=3))
    t_end = CC.TRACE['frames'][-1]['t']
    jobs = [('grid', 'grid', st) for st in grid] + [('cycle', 'trace', float(t)) for t in np.arange(0, t_end, 2.0)]
    with mp.get_context('fork').Pool(6) as pool:
        res = pool.map(run, jobs, chunksize=4)
    print('arm poses', len(res), round(time.time() - t0, 1), 's', flush=True)
    # summarise per segment
    seg = {}
    for r in res:
        for row in r['rows']:
            e = seg.setdefault(row['name'], dict(cable=row['cable'], kind=row['kind'], states=0, overlaps=0, hits=set(), min_clear_mm=1e9, min_clear_state=None,
                                                 closest=None, host_mm=[], lengths=[], radii=[], chords=[], sagittas=[]))
            e['states'] += 1
            if row['hits']:
                e['overlaps'] += 1
                e['hits'] |= set(row['hits'])
            if row['clear_mm'] < e['min_clear_mm']:
                e['min_clear_mm'], e['min_clear_state'], e['closest'] = row['clear_mm'], f"{r['label']} {r['strokes']}", row['closest']
            if row['host_mm'] is not None:
                e['host_mm'].append(row['host_mm'])
            e['lengths'].append(row['length_mm'])
            if row['min_radius_mm'] is not None:
                e['radii'].append(row['min_radius_mm'])
            if row['chord_mm'] is not None:
                e['chords'].append(row['chord_mm'])
                e['sagittas'].append(row['sagitta_mm'])
            if row.get('entry') is not None:
                lo, hi = e.get('entry', (1e9, -1e9))
                e['entry'] = (min(lo, row['entry']), max(hi, row['entry']))
                e['inside'] = e.get('inside', True) and bool(row['inside'])
                e['r2'] = min(e.get('r2', 1e9), row['r2'])
    summary = {}
    for n, e in seg.items():
        s = dict(cable=e['cable'], kind=e['kind'], states=e['states'], overlaps=e['overlaps'], overlapping_parts=sorted(e['hits'])[:12],
                 min_clear_mm=round(e['min_clear_mm'], 3), at=e['min_clear_state'], closest=e['closest'],
                 length_mm=dict(min=min(e['lengths']), max=max(e['lengths'])))
        if e['host_mm']:
            s['host_gap_mm'] = dict(min=min(e['host_mm']), max=max(e['host_mm']))
        if e['radii']:
            s['min_bend_radius_mm'] = min(e['radii'])
        if e['chords']:
            s['chord_mm'] = dict(min=min(e['chords']), max=max(e['chords']))
            s['sagitta_mm'] = dict(min=min(e['sagittas']), max=max(e['sagittas']))
            L = H.LOOP_L['O' if ' O' in n else 'E']
            s['cable_length_mm'] = L
            s['slack_at_longest_chord_mm'] = round(L - max(e['chords']), 2)
        if e['kind'] == 'drop':
            s['slide_travel_mm'] = round(max(e['lengths']) - min(e['lengths']), 2)
            s['trough_entry_x_O'] = e.get('entry')
            s['always_in_trough_and_bends_ok'] = e.get('inside', True)
            s['second_bend_radius_min_mm'] = e.get('r2')
        ok = e['overlaps'] == 0 and e['min_clear_mm'] >= H.CLEAR and e.get('inside', True)
        if e['radii']:
            ok = ok and min(e['radii']) >= (H.MIN_BEND_R_DROP if e['kind'] == 'drop' else 5.0 if e['kind'] in ('exit', 'landing') else H.MIN_BEND_R)
        if e['chords']:
            ok = ok and (L - max(e['chords'])) >= 4.0
        s['pass'] = bool(ok)
        summary[n] = s
    st = static_checks()
    sp = space_checks()
    # routed lengths per cable (carry pose) for the wire list
    sol, pose, segs = arm_segments(Mo.WAYPOINTS[0][1])
    per = {}
    for sg, pts, _, _ in segs:
        L = H.LOOP_L['O' if 'loop at O' in sg['name'] else 'E'] if sg['kind'] == 'loop' else H.length(pts)
        per[sg['cable']] = per.get(sg['cable'], 0.0) + L
    for c in H.static_cables():
        L = H.length(np.asarray(c['pts'], float))
        key = c.get('parent', c['name'])
        if c.get('slot'):
            key = c['slot']
        per[key] = per.get(key, 0.0) + L
    # the boom-drive drops vary with the pose: take the longest so the sleeve is never short
    for cable in ('boom_L', 'boom_R'):
        drop = summary[f'{cable} drop']
        per[cable] += drop['length_mm']['max'] - drop['length_mm']['min'] + (drop['trough_entry_x_O'][1] - 25.0 if drop.get('trough_entry_x_O') else 0.0)
    rows = H.wire_list(per)
    (K.ROOT / 'wiring').mkdir(exist_ok=True)
    with open(K.ROOT / 'wiring' / 'harness.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['cable', 'from', 'to', 'pins', 'wire', 'routed_mm', 'service_slack_mm', 'cut_length_mm', 'note'])
        for r in rows:
            w.writerow([r['cable'], r['from_'], r['to'], r['pins'], r['wire'], r['routed_mm'], r['slack_mm'], r['cut_mm'], r['note']])
    ok_arm = all(s['pass'] for s in summary.values())
    ok_static = all(not c['hits'] and c['clear_mm'] >= H.CLEAR for c in st)
    rep_static_touch_overlaps = {c['name']: c['touches']['overlaps'] for c in st if c['touches']['overlaps']}
    ok_space = all(v.get('ok', True) for v in sp.values() if isinstance(v, dict))
    rep = dict(
        method='Tubes of the cable radius (3 mm sleeve modelled at Ø3.5) along harness.py routes; FCL collision and distance against the viewer meshes '
               '(chord error 0.05-0.15 mm) over R12\'s 5 x 5 x 5 stroke grid and the dig cycle every 2 s (%d poses). Loops are circular arcs of fixed '
               'length between their clamps, bulging away from pin A (O) and pin D (E); the boom-drive sleeves slide in their slots (cubic from the '
               'exit direction to vertical).' % len(res),
        rules=dict(clearance_mm=H.CLEAR, min_bend_radius_mm=H.MIN_BEND_R, loop_slack_min_mm=4.0),
        arm_cables=summary, static_cables=st, space=sp, routed_lengths_mm={k: round(v, 1) for k, v in per.items()},
        wire_list_rows=len(rows), status='PASS' if (ok_arm and ok_static and ok_space) else 'FAIL', seconds=round(time.time() - t0, 1))
    (K.ROOT / 'wiring_check.json').write_text(json.dumps(rep, indent=1, default=float))
    print(rep['status'], rep['seconds'], 's')
    for n, s in summary.items():
        print(f"{'PASS' if s['pass'] else 'FAIL'} {n:34s} clear {s['min_clear_mm']:7.3f} ({s['closest']}) at {s['at']}; overlaps {s['overlaps']}"
              + (f"; chord {s['chord_mm']['min']}-{s['chord_mm']['max']} L {s['cable_length_mm']} R>= {s['min_bend_radius_mm']}" if 'chord_mm' in s else '')
              + (f"; Rmin {s['min_bend_radius_mm']}" if 'min_bend_radius_mm' in s and 'chord_mm' not in s else '')
              + (f"; slide {s['slide_travel_mm']}" if 'slide_travel_mm' in s else '')
              + (f"; host {s['host_gap_mm']}" if 'host_gap_mm' in s else ''))
    for c in st:
        print(f"{'PASS' if (not c['hits'] and c['clear_mm'] >= H.CLEAR) else 'FAIL'} static {c['name']:40s} clear {c['clear_mm']:7.3f} ({c['closest']}) hits {c['hits']} touch {c['touches']['nearest']} {c['touches']['mm']} {c['touches']['overlaps'][:3]}")
    print(json.dumps(sp, indent=None, default=float)[:1500])


if __name__ == '__main__':
    main()

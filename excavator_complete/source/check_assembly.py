"""Assembly inspection of the complete machine: the fitting moves that only exist once the subsystems are combined,
swept against the CAD meshes with FCL.

  1. pin O         the Ø6 x 60 boom-foot pin pushed in from the left and from the right (its 120 mm swept cylinder), with
                   the body on: which side is open
  2. arm unit      B01X with the whole R12 arm, lowered vertically onto the T101 rib tops with the body halves already fitted
                   (and the reverse: lifted off for service), 2..120 mm above its seat
  3. M6 bolts      a 5 mm hex key (Ø6) on each of the four B01X bolts, straight up 120 mm, with the arm and the body on
  4. body halves   each half with its electronics slid 2/5/10 mm outboard then lifted 5/20/60 mm, hatch off, with the R12
                   arm (carry pose) and B01X in place (the body's own check did this against the ARM60)
  5. hatch         the battery hatch lifted 1..60 mm at every R12 dig-cycle waypoint
  6. plugs         the mated JST plugs on the board's inboard edge (top entry) against T101's rib, and their insertion path:
                   each plug lifted 2..30 mm straight up from its header, against the left half's own parts
Writes ../assembly_check.json. Run with the R12 interpreter from this folder.
"""
import json
import time
import numpy as np
import fcl
import common as K
import machine as M
import harness as H
import check_complete as CC

import motion_r12 as Mo                # noqa: E402
from poses_r12 import body_poses       # noqa: E402

OBJ, place = CC.OBJ, CC.place
NAMES = [o['name'] for o in OBJ]
IDX = {o['name']: i for i, o in enumerate(OBJ)}


def pose_of(strokes):
    s, P = body_poses(tuple(strokes))
    return {k: (np.asarray(v[0], float), float(v[1])) for k, v in P.items()}


def group(pred):
    return [i for i, o in enumerate(OBJ) if pred(o)]


def hits_between(moving, static, shift=np.zeros(3), near=3.0):
    """Names of static parts a moving set overlaps after translating the moving set by shift; also the smallest gap."""
    out, gap = set(), 1e9
    for i in moving:
        oi = OBJ[i]['obj']
        tr = oi.getTransform() if hasattr(oi, 'getTransform') else None
        R, t = oi.getRotation(), oi.getTranslation()
        oi.setTransform(fcl.Transform(R, t + shift))
        for j in static:
            res = fcl.CollisionResult()
            if fcl.collide(oi, OBJ[j]['obj'], fcl.CollisionRequest(), res):
                out.add((OBJ[i]['name'], OBJ[j]['name']))
                gap = 0.0
            elif gap > 0:
                dr = fcl.DistanceResult()
                d = fcl.distance(oi, OBJ[j]['obj'], fcl.DistanceRequest(), dr)
                gap = min(gap, float(d))
        oi.setTransform(fcl.Transform(R, t))
    return sorted(out), round(gap, 3)


def cylinder_obj(p0, p1, r):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = p1 - p0
    L = float(np.linalg.norm(d))
    z = d / L
    x = np.cross(z, [1, 0, 0]) if abs(z[0]) < 0.9 else np.cross(z, [0, 1, 0])
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    R = np.stack([x, y, z], axis=1)
    return fcl.CollisionObject(fcl.Cylinder(r, L), fcl.Transform(R, 0.5 * (p0 + p1)))


def probe(obj, idx, exclude=()):
    hits, gap = [], 1e9
    for j in idx:
        if OBJ[j]['name'] in exclude:
            continue
        res = fcl.CollisionResult()
        if fcl.collide(obj, OBJ[j]['obj'], fcl.CollisionRequest(), res):
            hits.append(OBJ[j]['name'])
            gap = 0.0
        elif gap > 0:
            dr = fcl.DistanceResult()
            gap = min(gap, float(fcl.distance(obj, OBJ[j]['obj'], fcl.DistanceRequest(), dr)))
    return sorted(set(hits)), round(gap, 3)


def main():
    t0 = time.time()
    rep = {}
    carry = pose_of(Mo.WAYPOINTS[0][1])
    place(carry, 0.0)
    upper_all = group(lambda o: o['set'] in ('upper', 'pinion'))
    arm_all = group(lambda o: o['set'] == 'arm')
    body_left = group(lambda o: o['name'].startswith(('B102', 'B104', 'B105', 'B107', 'controller_PCB', 'board_')) or o['name'] in ('ledge_magnet_0', 'ledge_magnet_2'))
    body_right = group(lambda o: o['name'].startswith(('B103', 'main_switch', 'fuse_holder', 'charge_jack', 'feed_socket')) or o['name'] in ('ledge_magnet_1', 'ledge_magnet_3'))
    hatch = group(lambda o: o['name'].startswith(('B106', 'cell_', 'holder_', 'battery_', 'hatch_magnet')))
    body_all = group(lambda o: o['sys'] in ('body', 'electronics'))
    turntable = group(lambda o: o['sys'] in ('turntable', 'slew') and o['set'] in ('upper', 'pinion'))
    plate = IDX['B01X_boom_foot_bracket']
    arm_unit = arm_all      # B01X + every R12 part (the base-body hardware is 'arm' too)

    # 1. pin O from each side (the pin's own parts and the boom/bracket bores are excluded)
    O = K.O_VEH
    excl = {'B02_boom', 'B01X_boom_foot_bracket', 'pin_O_d6x60', 'collar_O_L', 'collar_O_R', 'washer_O_L', 'washer_O_R'}
    res = {}
    for side, lab in ((1, 'from the left (cab side)'), (-1, 'from the right (tank side)')):
        cyl = cylinder_obj(O + [0, -side * 30.0, 0], O + [0, side * 92.0, 0], 3.0)
        hits, gap = probe(cyl, upper_all + arm_all, excl)
        res[lab] = dict(overlaps=hits, gap_mm=gap, clear=not hits)
    rep['pin_O_insertion'] = dict(pin='Ø6 x 60 at vehicle (30, 0, 195); the pin must be outside (|Y| 30..92) before it enters', results=res,
                                  verdict=('either side: the cab is open on the boom side, so the pin can be pushed in from the left too' if not res['from the left (cab side)']['overlaps'] else 'from the right (tank side) only, or before the left half is fitted') if not res['from the right (tank side)']['overlaps'] else 'see overlaps')

    # 2. the arm unit lowered onto T101 with the body on
    steps = {}
    for dz in (2.0, 5.0, 10.0, 30.0, 60.0, 120.0):
        hits, gap = hits_between(arm_unit, body_all + turntable, np.array([0, 0, dz]))
        steps[f'{dz:g} mm up'] = dict(overlaps=hits[:10], gap_mm=gap)
    rep['arm_unit_vertical_path'] = dict(moving='B01X with the complete R12 arm at the carry pose', against='body halves, hatch, electronics, turntable',
                                         steps=steps, clear=all(not v['overlaps'] for v in steps.values()))

    # 3. hex key on the four M6 bolts
    res = {}
    for k, (x, y) in enumerate(K.BOLTS):
        key = cylinder_obj([x, y, K.T101_TOP_Z + K.BASE_T + 6.0], [x, y, K.T101_TOP_Z + K.BASE_T + 126.0], 3.0)
        hits, gap = probe(key, upper_all + arm_all, {f'arm_bolt_M6x40_{k}'})
        res[f'bolt {k} at ({x:g}, {y:g})'] = dict(overlaps=hits, gap_mm=gap)
    rep['m6_key_access'] = dict(tool='5 mm hex key as a Ø6 x 120 straight path up from each bolt head, arm and body fitted', results=res,
                                clear=all(not v['overlaps'] for v in res.values()))

    # 4. body halves out and up with R12 in place (hatch off): the half's parts move, everything else stays
    screws = group(lambda o: o['name'].startswith('sleeve_screw_M3x12'))        # taken out before a half moves
    others = [i for i in upper_all + arm_all if i not in body_left + body_right + hatch + screws]
    half_res = {}
    for lab, parts, side in (('left half', body_left, 1), ('right half', body_right, -1)):
        steps = {}
        for dy in (2.0, 5.0, 10.0):      # lifted 0.2 so the sleeve floors do not rub the rib tops in the mesh test
            hits, gap = hits_between(parts, others, np.array([0, side * dy, 0.2]))
            steps[f'{dy:g} mm outboard'] = dict(overlaps=hits[:10], gap_mm=gap)
        for dz in (5.0, 20.0, 60.0):
            hits, gap = hits_between(parts, others, np.array([0, side * 10.0, dz]))
            steps[f'10 mm outboard, {dz:g} mm up'] = dict(overlaps=hits[:10], gap_mm=gap)
        half_res[lab] = dict(steps=steps, clear=all(not v['overlaps'] for v in steps.values()))
    rep['body_halves_removal'] = dict(note='as BODY.md paths, but against the R12 arm (carry pose), B01X and its posts', results=half_res,
                                      clear=all(v['clear'] for v in half_res.values()))

    # 5. hatch lift at every waypoint
    res = {}
    for name, st in Mo.WAYPOINTS[:-1]:
        place(pose_of(st), 0.0)
        worst = []
        for dz in (1.0, 10.0, 60.0):
            hits, gap = hits_between(hatch, [i for i in upper_all + arm_all if i not in hatch], np.array([0, 0, dz]))
            worst.append((dz, hits[:5], gap))
        res[name] = dict(steps=[dict(dz=w[0], overlaps=w[1], gap_mm=w[2]) for w in worst], clear=all(not w[1] for w in worst))
    rep['hatch_lift_vs_arm_poses'] = dict(results=res, clear=all(v['clear'] for v in res.values()))
    place(carry, 0.0)

    # 6. the plugs: top-entry headers since 2026-11-14 (B2B/B4B-XH-A, B3B-PH-K-S). The mated XHP / PHR housings stand on the
    #    board over the pin rows (Y 93.74 / 90.79) with their wires going up; against the T101 rib (outer face Y 69), and each
    #    plug's way on: lifted straight up from its header, against the left half's own parts (B102 with its hood, the cab
    #    parts). The half stands beside the machine for this, so T101 is not in that test.
    plugs = [i for i, o in enumerate(OBJ) if o['name'].startswith('board_plugs')]
    gap = min(probe(OBJ[i]['obj'], [IDX['T101_centre_frame']])[1] for i in plugs)
    half = [i for i in body_left if not OBJ[i]['name'].startswith(('board_plugs', 'board_parts', 'controller_PCB'))]
    path = []
    for dz in (2.0, 5.0, 14.0, 30.0):
        hits, g = hits_between(plugs, half, np.array([0, 0, dz]))
        path.append(dict(dz=dz, overlaps=hits[:5], gap_mm=g))
    rep['inboard_plugs'] = dict(rib_outer_face_y=69.0, gap_to_rib_mm=round(gap, 3), lift_path=path,
                                clear=gap >= 1.0 and all(not p['overlaps'] for p in path),
                                note='top-entry headers: each plug goes on straight down. The left half\'s hood covers the board (Z 199 over J102, Z 217 over the rest), so the '
                                     'plugs are mated with the half standing beside the machine (BODY.md slack), as before.')

    rep['status'] = 'PASS' if (not rep['pin_O_insertion']['results']['from the right (tank side)']['overlaps'] and rep['arm_unit_vertical_path']['clear']
                               and rep['m6_key_access']['clear'] and rep['body_halves_removal']['clear'] and rep['hatch_lift_vs_arm_poses']['clear']
                               and rep['inboard_plugs']['clear']) else 'FAIL'
    rep['seconds'] = round(time.time() - t0, 1)
    (K.ROOT / 'assembly_check.json').write_text(json.dumps(rep, indent=1, default=float))
    print(json.dumps({k: (v if k in ('status', 'seconds') else {kk: vv for kk, vv in v.items() if kk in ('clear', 'verdict', 'gap_mm')}) for k, v in rep.items()}, indent=1))
    print('pin O:', json.dumps(rep['pin_O_insertion']['results']))
    print('arm unit:', json.dumps(rep['arm_unit_vertical_path']['steps']))
    print('keys:', json.dumps(rep['m6_key_access']['results']))
    print('halves:', json.dumps(rep['body_halves_removal']['results'])[:1500])


if __name__ == '__main__':
    main()

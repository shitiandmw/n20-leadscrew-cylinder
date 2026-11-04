"""Exact-mesh 3D interference check of the R12 CAD (cad/scene.json.gz), using FCL.

Poses: the full 5 x 5 x 5 stroke grid (0, 15, 30, 45, 60 mm) plus the dig cycle every 2 s.
Every pair of parts on different bodies is tested for penetration. For pairs that come within
4 mm, the true minimum distance and its closest points are computed and classed as:
  drive   - inside one V6 drive (rod in its cap and body: sliding fit)
  pin     - closest points within 7 mm of a pin axis (running fits, eyes between cheeks)
  lateral - separation along Y (side faces running past each other, e.g. boom nose |Y| 10.5 / fork 11)
  inplane - everything else: the side-view clearance that the motion can close
Meshes are the CAD tessellation (chord error <= 0.05 mm). Writes ../cad/clash_check.json."""
import json
import gzip
import math
import time
import itertools
import multiprocessing as mp
import numpy as np
import fcl
import r12_design as d
import motion_r12 as Mo
from poses_r12 import body_poses

ROOT = d.rc.ROOT
NEAR = 4.0
PIN_ZONE = 7.0
SCENE = json.loads(gzip.decompress((ROOT / 'cad' / 'scene.json.gz').read_bytes()))
OBJS, NAMES, BODY, SPH = [], [], [], []
for it in SCENE:
    v = np.asarray(it['v'], float).reshape(-1, 3)
    t = np.asarray(it['t'], np.int64).reshape(-1, 3)
    m = fcl.BVHModel()
    m.beginModel(len(v), len(t))
    m.addSubModel(v, t)
    m.endModel()
    OBJS.append(fcl.CollisionObject(m, fcl.Transform()))
    NAMES.append(it['name'])
    BODY.append(it['body'])
    c = 0.5 * (v.min(0) + v.max(0))
    SPH.append((c, float(np.linalg.norm(v - c, axis=1).max())))
PAIRS = [(i, j) for i, j in itertools.combinations(range(len(OBJS)), 2) if BODY[i] != BODY[j]]
SAME = [(i, j) for i, j in itertools.combinations(range(len(OBJS)), 2) if BODY[i] == BODY[j]]


def same_body_overlaps():
    """Parts fixed to one body never move relative to each other: test them once for real overlap
    (penetration deeper than 0.01 mm; parts that only touch, like a pin in its fused bore, are fine)."""
    out = []
    for o in OBJS:
        o.setTransform(fcl.Transform())
    for i, j in SAME:
        ci, ri = SPH[i]
        cj, rj = SPH[j]
        if np.linalg.norm(ci - cj) > ri + rj:
            continue
        res = fcl.CollisionResult(); req = fcl.CollisionRequest(num_max_contacts=50, enable_contact=True)
        if fcl.collide(OBJS[i], OBJS[j], req, res):
            depth = max(c.penetration_depth for c in res.contacts)
            out.append(dict(a=NAMES[i], b=NAMES[j], body=BODY[i], max_depth_mm=round(float(depth), 3)))
    return out


def rot(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, -s], [0, 1, 0], [s, 0, c]])


def check_pose(st):
    sol, poses = body_poses(st)
    T = {}
    for k, ((ox, oz), a) in poses.items():
        T[k] = (rot(a), np.array([ox, 0.0, oz]))
    for o, b in zip(OBJS, BODY):
        R, t = T[b]
        o.setTransform(fcl.Transform(R, t))
    pins = np.array([sol['pins'][k] for k in 'OABCEDFJHRQ'])
    centres = [T[b][0] @ c + T[b][1] for (c, _), b in zip(SPH, BODY)]
    hits, near = [], []
    for i, j in PAIRS:
        gap = np.linalg.norm(centres[i] - centres[j]) - SPH[i][1] - SPH[j][1]
        if gap > NEAR:
            continue
        cres = fcl.CollisionResult()
        if fcl.collide(OBJS[i], OBJS[j], fcl.CollisionRequest(), cres):
            hits.append((NAMES[i], NAMES[j]))
            continue
        dres = fcl.DistanceResult()
        dist = fcl.distance(OBJS[i], OBJS[j], fcl.DistanceRequest(enable_nearest_points=True), dres)
        if dist < NEAR:
            p = 0.5 * (np.asarray(dres.nearest_points[0]) + np.asarray(dres.nearest_points[1]))
            dv = np.asarray(dres.nearest_points[1]) - np.asarray(dres.nearest_points[0])
            if NAMES[i].split('_V6_')[0] == NAMES[j].split('_V6_')[0] and '_V6_' in NAMES[i]:
                cls = 'drive'
            elif np.min(np.linalg.norm(pins - p[[0, 2]], axis=1)) < PIN_ZONE:
                cls = 'pin'
            elif dist > 1e-6 and abs(dv[1]) > 0.9 * np.linalg.norm(dv):
                cls = 'lateral'
            else:
                cls = 'inplane'
            near.append((NAMES[i], NAMES[j], round(float(dist), 3), cls))
    return tuple(st), hits, near


def main():
    t0 = time.time()
    grid = [0.0, 15.0, 30.0, 45.0, 60.0]
    poses = list(itertools.product(grid, repeat=3))
    cyc = [tuple(float(x) for x in Mo.reference(t)[0]) for t in np.arange(0, Mo.DURATION, 2.0)]
    with mp.get_context('fork').Pool() as pool:
        res = pool.map(check_pose, poses + cyc, chunksize=4)
    same = same_body_overlaps()
    hits, cls = [], dict(inplane={}, lateral={}, pin={}, drive={})
    for st, h, nr in res:
        hits += [dict(pose=list(st), a=a, b=b) for a, b in h]
        for a, b, dist, c in nr:
            key = f'{a} | {b}'
            if dist < cls[c].get(key, (1e9,))[0]:
                cls[c][key] = (dist, [round(x, 2) for x in st])
    top = lambda dct, n: [dict(pair=k, gap_mm=v[0], pose=v[1]) for k, v in sorted(dct.items(), key=lambda kv: kv[1][0])[:n]]
    same_bad = [x for x in same if x['max_depth_mm'] > 0.01]
    rep = dict(status='PASS' if not hits and not same_bad else 'FAIL',
               method='FCL mesh-mesh collision and distance on the CAD tessellation (chord <= 0.05 mm); all part pairs on different bodies',
               poses_grid=len(poses), poses_cycle=len(cyc), parts=len(OBJS), part_pairs=len(PAIRS),
               penetrations=len(hits), hits=hits[:30], same_body_pairs=len(SAME), same_body_overlaps=same_bad,
               same_body_contacts=[x for x in same if x['max_depth_mm'] <= 0.01][:40],
               closest_inplane=top(cls['inplane'], 15), closest_lateral=top(cls['lateral'], 10),
               closest_at_pins=top(cls['pin'], 10), closest_inside_drives=top(cls['drive'], 4),
               note='Pairs are classed by where their closest points are (see check_cad.py). A pair is listed once, '
                    'under the class of its overall closest points at its worst pose. The in-plane list therefore gives the '
                    'side-view clearances that remain when no lateral face or pin fit is closer.',
               seconds=round(time.time() - t0, 1))
    (ROOT / 'cad' / 'clash_check.json').write_text(json.dumps(rep, indent=1))
    print(rep['status'], 'penetrations', len(hits), 'parts', len(OBJS), 'pairs', len(PAIRS), rep['seconds'], 's')
    print('same-body overlaps', same_bad, 'touching', len(rep['same_body_contacts']))
    for c in ('closest_inplane', 'closest_lateral', 'closest_at_pins', 'closest_inside_drives'):
        for x in rep[c]:
            print(f"{c:22s} {x['gap_mm']:7.3f}  {x['pair']:45s} {x['pose']}")
    for h in hits[:15]:
        print('HIT', h)


if __name__ == '__main__':
    main()

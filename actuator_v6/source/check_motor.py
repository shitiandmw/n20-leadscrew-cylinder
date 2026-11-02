"""Check the replacement motor's solids, supports, keyed output and tooth mesh.

Run after build_v6.py --motor-only. Tooth checks use the actual delivered
V6 preview meshes, including their four-decimal coordinate quantization.
"""
import gzip
import itertools
import json
import math
from pathlib import Path

import cadquery as cq
import numpy as np
import trimesh
from shapely.affinity import rotate
from shapely.geometry import Polygon, GeometryCollection
from shapely.ops import unary_union

from gear_spec import CENTRES, STAGES, RATIOS, PART_BODIES
from n20_screw_motor import n20_core_part
from n20_geartrain import cylinder

ROOT = Path(__file__).resolve().parent.parent


def volume(shape):
    return max(0., sum(s.Volume() for s in shape.Solids()))


def overlap(a, b):
    aa, bb = a.BoundingBox(), b.BoundingBox()
    if any(getattr(aa, c+'min') >= getattr(bb, c+'max')-1e-8 or
           getattr(bb, c+'min') >= getattr(aa, c+'max')-1e-8 for c in 'xyz'):
        return 0.
    return volume(a.intersect(b))


def section(mesh, z):
    path = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    out = GeometryCollection()
    if path is not None:
        for line in path.discrete:
            polygon = Polygon(line[:, :2])
            out = out.symmetric_difference(polygon if polygon.is_valid else polygon.buffer(0))
    return out


def main():
    failures = []
    report = dict(scope='V6 motor replacement only', failures=failures)
    def check(ok, message):
        if not ok:
            failures.append(message)

    shapes = {n: wp.val() for n, wp in n20_core_part(40).items()}
    report['solids'] = {n: dict(valid=s.isValid(), count=len(s.Solids())) for n, s in shapes.items()}
    check(all(s['valid'] and s['count'] == 1 for s in report['solids'].values()), 'invalid motor solid')
    hits = []
    for (an, a), (bn, b) in itertools.combinations(shapes.items(), 2):
        v = overlap(a, b)
        if v > 1e-7:
            hits.append(dict(a=an, b=bn, volume_mm3=v))
    report['rest_pose'] = dict(pairs=math.comb(len(shapes), 2), collisions=hits, tolerance_mm3=1e-7)
    check(not hits, 'motor parts overlap at zero pose')
    a, b = shapes['motor_gear_4'], shapes['motor_leadscrew_M3']
    report['keyed_output'] = dict(gap_mm=a.distance(b), fused_solids=len(a.fuse(b).Solids()), overlap_mm3=overlap(a, b))
    check(report['keyed_output']['gap_mm'] < 1e-7 and report['keyed_output']['fused_solids'] == 1,
          'output wheel is not connected to the screw')
    print('Motor solids and zero-pose pairs checked', flush=True)

    # Rotation-invariant enclosing cylinders prove clearance to all fixed
    # supports at every angle, after checking containment of the actual CAD.
    layers = {
        'input': [(.5,-24.8,-6.75),(3.2,-21.8,-11),(.65,-9.35,-9.15),(.9,-7.85,-6.95)],
        'compound_a': [(.45,-9,0),(.59,-8.1,-7.95),(.59,-1.05,-.9),(2.52,-7.85,-6.95),(.9,-5.85,-4.95)],
        'compound_b': [(.45,-9,0),(.59,-8.1,-7.95),(.59,-1.05,-.9),(2.52,-5.85,-4.95),(.9,-3.85,-2.75)],
        'output': [(1.5,-4.83,40),(1.75,-4.83,-4.73),(1.9,-3.95,-2.65),(2.52,-3.85,-2.75)]}
    supports = {}
    for body, sections in layers.items():
        cells = [cylinder(r, z0, z1, CENTRES[body]).val() for r, z0, z1 in sections]
        env = cells[0].fuse(*cells[1:])
        outside = max(volume(s.cut(env)) for n, s in shapes.items() if PART_BODIES.get(n) == body)
        fixed = {n: s for n, s in shapes.items() if n not in PART_BODIES}
        hits = {n: v for n, s in fixed.items() if (v := overlap(env, s)) > 1e-7}
        supports[body] = dict(outside_envelope_mm3=outside, collisions=hits,
                              minimum_clearance_mm=min(env.distance(s) for s in fixed.values()))
        check(outside < 1e-7 and not hits, body + ' all-angle support clearance')
    report['continuous_support_clearance'] = supports
    print('Continuous support clearance checked', flush=True)

    report['variants'] = {}
    params = json.loads((ROOT/'parameters.json').read_text())
    reference_gears = None
    for variant, p in params.items():
        with gzip.open(ROOT/f'source/scene_{variant}.json.gz', 'rt') as f:
            items = {it['name']: it for it in json.load(f) if it['name'].startswith('motor_')}
        meshes = {n: trimesh.Trimesh(it['vertices'], it['triangles'], process=True) for n, it in items.items()}
        vertices = np.concatenate([m.vertices for m in meshes.values()])
        lo, hi = vertices.min(axis=0), vertices.max(axis=0)
        envelope_ok = bool(np.allclose(lo, [-5,-6,-26.5], atol=1e-4) and
                           np.allclose(hi, [5,6,p['screw_length_mm']], atol=1e-4))
        gears = {n: it for n, it in items.items() if n.startswith('motor_gear_')}
        identical = reference_gears is None or gears == reference_gears
        reference_gears = gears
        check(envelope_ok and identical and len(items) == 21, variant + ' envelope/gear geometry')
        check(all(m.is_watertight for m in meshes.values()), variant + ' non-watertight motor mesh')
        check({n for n, it in items.items() if it.get('geartrain_rotation')} == set(PART_BODIES),
              variant + ' missing rotor metadata')
        report['variants'][variant] = dict(parts=len(items), bounds_mm=[lo.tolist(), hi.tolist()],
                                          envelope_pass=envelope_ok, same_gears=identical,
                                          watertight=all(m.is_watertight for m in meshes.values()))
        if variant != 'S':
            continue
        contacts = []
        for stage in STAGES:
            driver, driven = stage['driver'], stage['driven']
            names = [next(n for n, b in PART_BODIES.items() if b == body) for body in (driver, driven)]
            z = (stage['zmin'] + stage['zmax'])/2
            pa, pb = [section(meshes[n], z) for n in names]
            max_area, max_gap = 0., 0.
            for theta in np.linspace(0, 2*math.pi/(18*abs(RATIOS[driver])), 2049):
                ga = rotate(pa, theta*RATIOS[driver], origin=CENTRES[driver], use_radians=True)
                gb = rotate(pb, theta*RATIOS[driven], origin=CENTRES[driven], use_radians=True)
                max_area = max(max_area, ga.intersection(gb).area)
                max_gap = max(max_gap, ga.distance(gb))
            # 0.0001 mm mesh rounding can introduce tiny flank overlaps.
            ok = max_area < 2e-6 and max_gap < .0003 and 18*RATIOS[driver]+54*RATIOS[driven] == 0
            check(ok, stage['id'] + ' delivered mesh contact')
            contacts.append(dict(stage=stage['id'], samples=2049, max_overlap_area_mm2=max_area,
                                 max_flank_gap_mm=max_gap, face_overlap_mm=stage['zmax']-stage['zmin'], pass_=ok))
            print('Tooth contacts', contacts[-1], flush=True)
        report['delivered_mesh_contacts'] = contacts
        levels = [-9,-8.2,-8.1,-7.95,-7.85,-6.95,-6.75,-5.85,-4.95,-4.83,-4.73,
                  -4.65,-4.15,-3.95,-3.85,-2.75,-2.65,-1.05,-.9,-.8,0]
        slices = []
        for z0, z1 in zip(levels, levels[1:]):
            z = (z0+z1)/2
            slices.append({body: unary_union([section(meshes[n], z) for n, b in PART_BODIES.items() if b == body])
                           for body in CENTRES})
        maximum, count = 0., 0
        for theta in np.linspace(0, 2*math.pi/54, 257):
            for polygons in slices:
                posed = {b: rotate(p, theta*RATIOS[b], origin=CENTRES[b], use_radians=True)
                         for b, p in polygons.items()}
                for a, b in itertools.combinations(posed.values(), 2):
                    if not a.is_empty and not b.is_empty:
                        maximum = max(maximum, a.intersection(b).area)
                        count += 1
        report['all_moving_pairs'] = dict(samples=257, axial_intervals=len(slices), pair_checks=count,
                                           max_overlap_area_mm2=maximum, tolerance_mm2=2e-6)
        check(maximum < 2e-6, 'moving motor bodies collide')
        print('All moving body pairs checked', count, maximum, flush=True)

    report['passed'] = not failures
    report['limitations'] = ['Illustrative 27:1 gearbox; commercial tooth counts are unknown.',
                            'Prescribed gear motion; no load, backlash reversal or manufacturing fit simulation.',
                            'The existing V6 pitch-ring thread is retained above Z=0.7 mm.']
    (ROOT/'motor_validation.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'], failures=failures)), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

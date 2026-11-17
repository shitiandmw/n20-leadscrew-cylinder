"""Revision F J9 track validation: a fresh full run on the delivered parts.

The trial orchestration is the validated block of build_j9.main(): static
assembly, drive rotation, idler travel and stop, spring at recoil, chain
phases, assembly paths and tool access. Here it runs on the delivered STEP
parts (not regenerated exports) and every candidate pair is computed fresh.
The spring envelope and the thickened main-plate clearances are checked
separately, and so is the chain joint (chain_joint_checks: neighbouring
links through the bend range, screw seats, head/nut/boss clearance to the
guide flanges with the chain hard over, tooth side clearance). Nominal CAD
only: no strength, print-tolerance, fatigue or powered test.
"""
import ast
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

import cadquery as cq

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent/'X1/source'))
import mount_checks as V
import build_j9 as B
import check_spring_guide as S
from refresh_revf import part as current_step_part

P, D, tp = V.P, V.D, V.tp
ROOT, REPO = P.ROOT, P.REPO


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def binding():
    sources = [Path(__file__), Path(V.__file__), Path(B.__file__), Path(S.__file__),
               P.HERE/'j9_parts.py', P.HERE/'j9_design.py', P.HERE/'j9_mounts.py',
               Path(tp.__file__), Path(V.checks.__file__), V.X.HERE/'x1_parts.py',
               V.X.HERE/'refresh_revf.py']
    return dict(source_sha256={str(p.relative_to(REPO)): sha(p) for p in sources},
                exported_step_sha256={str((ROOT/'step'/f'{n}.step').relative_to(REPO)):
                                       sha(ROOT/'step'/f'{n}.step') for n in P.PRINTED},
                exported_stl_sha256={str((ROOT/'stl'/f'{n}.stl').relative_to(REPO)):
                                      sha(ROOT/'stl'/f'{n}.stl') for n in P.PRINTED})


class Checkpoint:
    """Reuse completed cases only for identical source and exported part bytes."""
    def __init__(self, inputs):
        self.fingerprint = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
        task = hashlib.sha256(str(ROOT).encode()).hexdigest()[:12]
        self.path = Path(tempfile.gettempdir())/f'j9-revf-fresh-{task}-checkpoints.json'
        old = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.results = old.get('results', {}) if old.get('fingerprint') == self.fingerprint else {}
        self.reused = 0

    def run(self, key, fn):
        if key in self.results:
            self.reused += 1
            return self.results[key]
        self.results[key] = fn()
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(dict(fingerprint=self.fingerprint, results=self.results)))
        temporary.replace(self.path)
        return self.results[key]


def validation_block():
    """The build_j9.main() trial block, from fixed_names to rep['assembly_and_access']."""
    tree = ast.parse(Path(B.__file__).read_text())
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    start = end = None
    for i, node in enumerate(main.body):
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == 'fixed_names' for t in node.targets):
                start = i
            for target in node.targets:
                if (isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and
                        target.value.id == 'rep' and isinstance(target.slice, ast.Constant) and
                        target.slice.value == 'assembly_and_access'):
                    end = i
    if start is None or end is None:
        raise RuntimeError('Could not locate the build_j9 trial block')
    block = ast.Module(body=main.body[start:end+1], type_ignores=[])
    return block, hashlib.sha256(ast.dump(block, include_attributes=False).encode()).hexdigest()


class FullChecks:
    """Every candidate pair of every case is computed fresh with tw_checks."""
    def __init__(self, checkpoint):
        self.checkpoint = checkpoint
        self.case_rows = []

    def interference(self, inst, tol=.01, skip=None, margin=.05):
        case_id = len(self.case_rows)
        result = self.checkpoint.run(f'case_{case_id}', lambda: V.checks.interference(
            inst, tol=tol, skip=skip, margin=margin))
        result = dict(case_index=case_id, **result)
        self.case_rows.append(result)
        print(f'  case {case_id}: {result["pairs_tested"]} pairs; {len(result["hits"])} hits', flush=True)
        if result['hits']:
            print(json.dumps(result['hits']), flush=True)
        return result

    def against(self, fixed, moving):
        return self.interference({**fixed, **moving}, skip=lambda a, b: (a in moving) == (b in moving))


def load_current():
    prt = {}
    for name, (_, color, quantity, material, note) in P.PRINTED.items():
        shape = cq.Workplane(obj=current_step_part(ROOT/'step'/f'{name}.step'))
        if not P.one(shape).isValid() or len(P.one(shape).Solids()) != 1:
            raise RuntimeError(f'Current STEP is not one valid solid: {name}')
        prt[name] = dict(shape=shape, color=color, quantity=quantity, material=material, note=note)
    print('Build current purchased hardware and exact chain instances', flush=True)
    return prt, P.unit(prt)


def chain_joint_checks(prt, inst):
    """The chain joint, against the three faults the 2026-11-14 pre-print review found in the inherited link: a pin that
    could slide until its clip was under a roller flange, 0.045 mm between neighbouring links, and 0.2 mm of tooth side
    clearance. Checked on the delivered J910 and the joint hardware, with the chain pushed sideways as far as the guide
    flanges allow (0.6 mm of flange play plus 0.3 mm of roller float)."""
    import math
    shoe = prt['J910_track_shoe_70']['shape']
    half, side_play = D.PITCH/2, (D.FLANGE_IN - D.LINK_HALF_W) + .3
    wheels = {n: d['shape'] for n, d in inst.items() if n.startswith('J904_roller_') or n == 'J906_idler_wheel'}
    centres = {n: ((D.IDLER_X, D.AXLE_Z) if n == 'J906_idler_wheel' else next((x, z) for x, z, g in P.ROLLERS if n.endswith(g)))
               for n in wheels}
    reach = {n: (D.PITCH_R + 1 if n == 'J906_idler_wheel' else D.ROLLER_R + D.RAIL_FACE + 6) for n in wheels}
    near = lambda x, z: [n for n in wheels if math.hypot(x - centres[n][0], z - centres[n][1]) < reach[n]]

    # 1. Neighbouring links through the bend range (the top run needs about 3 degrees of back-bend).
    neighbours = []
    for ang in (-5.0, 0.0, 10.0, 20.0, 30.0):
        other = shoe.translate((D.PITCH, 0, 0)).rotate((half, 0, 0), (half, 1, 0), -ang)
        neighbours.append(dict(bend_deg=ang, mm=B.dist(shoe, other)))
    # 2. The screw cannot slide: the seat faces are where the head and the nut rest, on both sides.
    solid = P.one(shoe)
    probe = lambda y: bool(solid.isInside(cq.Vector(-half, y, -2.5)))
    seats = {('head' if s > 0 else 'nut') + '_seat_at_abs_y': D.SCREW_SEAT_Y if probe(s*(D.SCREW_SEAT_Y - .05)) and not probe(s*(D.SCREW_SEAT_Y + .05)) else None
             for s in (1, -1)}
    # ... and head, nut and seat bosses clear the roller and idler flanges with the chain hard over to either side.
    hardware, bosses = [], []
    boss = {s: shoe.intersect(tp.box(-15, -4, *sorted([s*(D.LINK_HALF_W + .02), s*(D.SCREW_SEAT_Y + 1)]), -3.9, 2)) for s in (-1, 1)}
    poses = list(P.link_poses(D.PINS))
    S = D.TRACK_SCREW
    pieces = dict(head=tp.ycyl(S['head_r'], D.SCREW_SEAT_Y, D.SCREW_SEAT_Y + S['head_k']), nut=P.track_nut(),
                  shank=tp.ycyl(D.PIN_R, D.SCREW_SEAT_Y - S['length'], D.SCREW_SEAT_Y))
    shanks = []
    for i, (x, z) in enumerate(D.PINS):
        x, z = float(x), float(z)
        for wheel in near(x, z):
            for kind, piece in pieces.items():
                for dy in (-side_play, 0.0, side_play):
                    row = dict(part=f'{kind} at pin {i:02}', wheel=wheel, chain_offset_mm=round(dy, 2),
                               mm=B.dist(piece.translate((x, dy, z)), wheels[wheel]))
                    (shanks if kind == 'shank' else hardware).append(row)
    for i, origin, a in poses:
        px, pz = (float(v) for v in D.PINS[i])           # the plate end (boss) of link i is at pin i
        for wheel in near(px, pz):
            for s in (-1, 1):
                placed = boss[s].rotate((0, 0, 0), (0, 1, 0), -math.degrees(a)).translate((float(origin[0]), 0, float(origin[1])))
                for dy in (-side_play, side_play):
                    bosses.append(dict(link=i, side='outboard' if s > 0 else 'inboard', wheel=wheel, chain_offset_mm=round(dy, 2),
                                       mm=B.dist(placed.translate((0, dy, 0)), wheels[wheel])))
    # 3. Sprocket teeth between the inner ears, with the chain at the limit of the flange play.
    engaged = [i for i, origin, a in poses if all(abs(math.hypot(float(D.PINS[k % len(D.PINS)][0]) - D.DRIVE_X, float(D.PINS[k % len(D.PINS)][1]) - D.AXLE_Z)
                                                      - D.PITCH_R) < 1e-6 for k in (i, i + 1))]
    sprocket = inst['J902_sprocket']['shape']
    teeth = []
    for i in engaged[1::2][:3]:
        for dy in (-(D.FLANGE_IN - D.LINK_HALF_W), D.FLANGE_IN - D.LINK_HALF_W):
            common = sprocket.intersect(inst[f'shoe_{i:02}']['shape'].translate((0, dy, 0)))
            teeth.append(dict(link=i, chain_offset_mm=round(dy, 2), overlap_mm3=round(sum(v.Volume() for v in common.solids().vals()), 4)))
    result = dict(
        neighbouring_links=neighbours, min_neighbour_mm=min(r['mm'] for r in neighbours),
        seats=seats, side_play_mm=round(side_play, 2),
        head_and_nut_to_guide_flanges=dict(cases=len(hardware), min_mm=min(r['mm'] for r in hardware),
                                           worst=min(hardware, key=lambda r: r['mm'])),
        screw_shank_under_guide_flanges=dict(cases=len(shanks), min_mm=min(r['mm'] for r in shanks), worst=min(shanks, key=lambda r: r['mm']),
                                             note='the Ø3 shank passes under the flanges as the Ø3 pin did'),
        seat_boss_to_guide_flanges=dict(cases=len(bosses), min_mm=min(r['mm'] for r in bosses), worst=min(bosses, key=lambda r: r['mm'])),
        sprocket_side_clearance_mm=round(D.LINK_EAR_Y[0] - D.SPROCKET_HALF_T, 3), sprocket_at_flange_play=teeth,
        limits=dict(min_neighbour_mm=.25, min_head_nut_to_flange_mm=.8, min_shank_to_flange_mm=.3, min_boss_to_flange_mm=.6,
                    min_sprocket_side_mm=.5))
    L = result['limits']
    result['pass'] = bool(result['min_neighbour_mm'] >= L['min_neighbour_mm'] and all(seats.values())
                          and result['head_and_nut_to_guide_flanges']['min_mm'] >= L['min_head_nut_to_flange_mm']
                          and result['screw_shank_under_guide_flanges']['min_mm'] >= L['min_shank_to_flange_mm']
                          and result['seat_boss_to_guide_flanges']['min_mm'] >= L['min_boss_to_flange_mm']
                          and result['sprocket_side_clearance_mm'] >= L['min_sprocket_side_mm']
                          and all(r['overlap_mm3'] == 0 for r in teeth))
    return result


def run():
    started = time.time()
    inputs = binding()
    checkpoint = Checkpoint(inputs)
    print(f'Checkpoint {checkpoint.path}; {len(checkpoint.results)} saved results', flush=True)
    prt, inst = load_current()
    if binding() != inputs:
        raise RuntimeError('Inputs changed while loading current J9')
    engine = FullChecks(checkpoint)
    block, block_sha = validation_block()
    namespace = dict(vars(B))
    namespace.update(inst=inst, prt=prt, rep={},
                     checks=SimpleNamespace(interference=engine.interference), against=engine.against)
    print('Run the build_j9 trial block with every pair computed fresh', flush=True)
    exec(compile(block, str(HERE/'build_j9.py')+' [trial block]', 'exec'), namespace)
    trials = namespace['rep']
    print('Full spring-envelope and insertion checks', flush=True)
    spring = checkpoint.run('full_spring_envelope',
                            lambda: S.check(prt['J901_H_frame']['shape'], prt['J908_U_yoke']['shape']))
    spring_path = ROOT/'spring_guide_validation.json'
    spring_path.write_text(json.dumps(spring, indent=2)+'\n')
    print('Thickened main-plate clearances', flush=True)
    added_plate = prt['J901_H_frame']['shape'].intersect(
        tp.box(-200, 200, min(P.mounts.THICKENING_Y), P.mounts.ORIGINAL_WALL_Y[0]-.0001, -100, 200))
    clearances = checkpoint.run('mounting_clearances', lambda: {
        'added_main_plate_to_housing': V.closest_disjoint(added_plate, {'J909_housing': inst['J909_housing']}),
        'added_main_plate_to_motor': V.closest_disjoint(added_plate, {n: inst[n] for n in
             ('JGY370_gearbox', 'JGY370_motor_can', 'JGY370_terminal_space')}),
        'added_main_plate_to_chain': V.closest_disjoint(added_plate, {n: d for n, d in inst.items()
                                                                    if d['group'] == 'track'}),
    })
    # The over-travel trial is expected to hit the H-frame/yoke stop. Every
    # other case must have no above-tolerance overlap.
    over = namespace['over']
    stop_ok = bool(over['hits']) and all({h['a'], h['b']} == {'J901_H_frame', 'J908_U_yoke'} for h in over['hits'])
    failures = [r for r in engine.case_rows if r['case_index'] != over['case_index'] and r['hits']]
    design = D.check()
    print('Drive coupling against the seller drawing', flush=True)
    hub = dict(seller_drawing_check=B.coupling_check(), set_screws=B.hub_set_screws())
    hub['pass'] = bool(hub['seller_drawing_check']['ok'] and all(s['on_flat'] for s in hub['set_screws']))
    print('Chain joint: neighbouring links, screw seats and guide flanges, tooth side clearance', flush=True)
    joint = checkpoint.run('chain_joint', lambda: chain_joint_checks(prt, inst))
    ok = (not failures and stop_ok and spring['pass'] and hub['pass'] and joint['pass'] and
          all(row['mm'] > .2 for row in clearances.values()) and design['link_error_mm'] < 1e-9)
    if binding() != inputs:
        raise RuntimeError('Inputs changed while the track check was running')
    report = dict(revision='J9 revision F straight-arm seats on the main plate',
                  validation_method='fresh full run of the build_j9 trial block on the delivered STEP parts',
                  **inputs, trial_block_ast_sha256=block_sha,
                  static=trials['static'], drive_rotation_no_chain=trials['drive_rotation_no_chain'],
                  idler_travel=trials['idler_travel'], spring_at_recoil=trials['spring_at_recoil'],
                  chain_phases_vs_fixed_parts=trials['chain_phases_vs_fixed_parts'],
                  assembly_and_access=trials['assembly_and_access'],
                  spring_guide=spring, spring_guide_report_sha256=sha(spring_path),
                  mounting_clearances_mm=clearances, drive_hub=hub, chain_joint=joint,
                  stop_test=over, stop_pass=stop_ok, case_count=len(engine.case_rows),
                  pairs_tested=sum(r['pairs_tested'] for r in engine.case_rows),
                  failure_cases=failures, overlap_tolerance_mm3=.01,
                  reused_checkpoint_cases=checkpoint.reused, design=design,
                  scope='Nominal CAD validation. Every candidate pair of every trial is computed fresh on the '
                        'delivered revision F parts. Full spring envelopes are checked at eleven positions. '
                        'Not a strength, print-tolerance, fatigue or powered test.',
                  elapsed_s=round(time.time()-started, 2))
    report['pass'] = bool(ok)
    (ROOT/'revf_track_validation.json').write_text(json.dumps(report, indent=1)+'\n')
    # validation.json is the established entry point for the current track.
    (ROOT/'validation.json').write_text(json.dumps(report, indent=1)+'\n')
    print(json.dumps(dict(passed=ok, cases=len(engine.case_rows), pairs=report['pairs_tested'],
                          stop=stop_ok, drive_hub=hub['pass'], chain_joint=joint['pass'],
                          failures=[r['case_index'] for r in failures],
                          clearances={k: v['mm'] for k, v in clearances.items()},
                          elapsed_s=report['elapsed_s']), indent=1), flush=True)
    if not ok:
        raise SystemExit(1)
    return report


if __name__ == '__main__':
    run()

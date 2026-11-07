"""Revision F J9 track validation: a fresh full run on the delivered parts.

The trial orchestration is the validated block of build_j9.main(): static
assembly, drive rotation, idler travel and stop, spring at recoil, chain
phases, assembly paths and tool access. Here it runs on the delivered STEP
parts (not regenerated exports) and every candidate pair is computed fresh.
The spring envelope and the thickened main-plate clearances are checked
separately. Nominal CAD only: no strength, print-tolerance, fatigue or
powered test.
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
    ok = (not failures and stop_ok and spring['pass'] and
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
                  mounting_clearances_mm=clearances,
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
                          stop=stop_ok, failures=[r['case_index'] for r in failures],
                          clearances={k: v['mm'] for k, v in clearances.items()},
                          elapsed_s=report['elapsed_s']), indent=1), flush=True)
    if not ok:
        raise SystemExit(1)
    return report


if __name__ == '__main__':
    run()

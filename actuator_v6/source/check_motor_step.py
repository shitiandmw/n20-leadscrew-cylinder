"""Read back a regenerated V6 assembly STEP and persist each completed check.

Use --variant S, U60 or L to check large assemblies in separate processes.
"""
import argparse
import json
from pathlib import Path

import cadquery as cq

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant', choices=['S', 'U60', 'L'], required=True)
    variant = parser.parse_args().variant
    path = ROOT / f'step/V6-{variant}/assembly_V6-{variant}_retracted.step'
    shape = cq.importers.importStep(str(path)).val()
    result = dict(valid=shape.isValid(), solids=len(shape.Solids()), bytes=path.stat().st_size)
    assert result['valid'] and result['solids'] > 21, result
    out = ROOT / 'motor_step_check.json'
    report = json.loads(out.read_text()) if out.exists() else dict(variants={})
    report['variants'][variant] = result
    report['passed'] = (set(report['variants']) == {'S', 'U60', 'L'} and
                        all(r['valid'] for r in report['variants'].values()))
    out.write_text(json.dumps(report, indent=2)+'\n')
    print(variant, result, flush=True)


if __name__ == '__main__':
    main()

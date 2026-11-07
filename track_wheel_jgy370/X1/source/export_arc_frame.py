"""Export revision F X101 as STEP and print-oriented STL.

An optional candidate receipt can reuse a native solid only when all its source
and BREP hashes match. Without it the current source constructs the solid.
Run check_revf_exports.py afterwards; it writes the export report.
"""
import argparse
import hashlib
import json
from pathlib import Path

import cadquery as cq

import x1_parts as X
import build_x1 as B


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def volume(shape):
    return sum(s.Volume() for s in shape.Solids())


def geometry_contract(shape):
    """Reject a valid but incomplete boolean result before manufacturing export.

    These independent bounds describe the approved F envelope. Deriving them
    from the generated solid or source constants could hide a dropped arm end.
    The joint checker separately verifies all four contact faces and seats.
    """
    expected = [-77.5, 77.5, -137.5, 137.5, 34.0, 85.0]
    box = shape.BoundingBox()
    measured = [box.xmin, box.xmax, box.ymin, box.ymax, box.zmin, box.zmax]
    tolerance = 1e-4
    error = max(abs(a-b) for a, b in zip(measured, expected))
    assert error <= tolerance, (
        'Revision F X101 envelope is incomplete or changed', measured, expected, error)
    return dict(expected_bounds_mm=expected, measured_bounds_mm=measured,
                bound_order=['xmin', 'xmax', 'ymin', 'ymax', 'zmin', 'zmax'],
                tolerance_mm=tolerance, max_error_mm=error, **{'pass': True})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-json', type=Path)
    args = parser.parse_args()
    source_files = [Path(__file__), Path(X.__file__), Path(X.M.__file__),
                    Path(X.P9.__file__), Path(X.D9.__file__), Path(X.tp.__file__),
                    Path(B.__file__), Path(B.export.__file__)]
    bindings = {str(p.relative_to(X.REPO)): sha(p) for p in source_files}
    if args.candidate_json:
        candidate = json.loads(args.candidate_json.read_text())
        assert all(sha(name) == value for name, value in candidate['source_sha256'].items())
        assert sha(candidate['brep']) == candidate['brep_sha256']
        shape = cq.Shape.importBrep(candidate['brep'])
    else:
        shape = X.one(X.x_frame())
    assert shape.isValid() and len(shape.Solids()) == 1
    contract = geometry_contract(shape)
    print('Export X101 STEP and printable STL', flush=True)
    step = X.ROOT/'step/X101_X_frame.step'
    stl = X.ROOT/'stl/X101_X_frame.stl'
    temporary_step = step.with_name('X101_X_frame.revf_tmp.step')
    temporary_stl = stl.with_name('X101_X_frame.revf_tmp.stl')
    cq.exporters.export(shape, str(temporary_step))
    roundtrip = cq.importers.importStep(str(temporary_step)).val()
    assert roundtrip.isValid() and len(roundtrip.Solids()) == 1
    roundtrip_contract = geometry_contract(roundtrip)
    assert abs(volume(roundtrip)-volume(shape)) < .01
    mesh = B.export.export_stl(B.export.to_bed(cq.Workplane(obj=shape), (1, 0, 0), 180), temporary_stl)
    assert all(sha(X.REPO/name) == value for name, value in bindings.items())
    temporary_step.replace(step)
    temporary_stl.replace(stl)
    row = dict(name='X101_X_frame', quantity=1, solids=1, valid=True,
               volume_mm3=volume(shape), step_roundtrip=True,
               stl_watertight=bool(mesh.is_watertight), stl_components=len(mesh.split()),
               print_bounds_mm=mesh.extents.tolist(),
               step_file=str(step.relative_to(X.REPO)), step_sha256=sha(step),
               stl_file=str(stl.relative_to(X.REPO)), stl_sha256=sha(stl))
    report = dict(revision='F', source_sha256=bindings, geometry_contract=contract,
                  step_roundtrip_contract=roundtrip_contract, exports=[row])
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()

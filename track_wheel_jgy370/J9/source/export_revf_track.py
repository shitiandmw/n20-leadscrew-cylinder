"""Export both revision F track frame/housing pairs and verify STEP/STL files.

Run X1/source/check_revf_exports.py afterwards; it writes the export report.

A source-bound candidate manifest may avoid repeating solid construction.
Every STEP is reimported and checked; the cache stores that imported shape.
The accepted seven other track parts are left byte-for-byte unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import cadquery as cq
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
import j9_parts as P
import build_track_wheel as E

sys.path.insert(0, str(P.ROOT.parent/'X1/source'))
from refresh_revf import signature, signature_matches


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_bindings():
    paths = [P.HERE/'j9_parts.py', P.HERE/'j9_mounts.py', P.HERE/'j9_design.py',
             Path(P.tp.__file__), Path(E.__file__), Path(__file__)]
    return {str(p.relative_to(P.REPO)): sha(p) for p in paths}


def roundtrip_geometry(source, imported):
    """Verify geometry while retaining numerical integration diagnostics.

    The default non-adaptive OCC mass integration can change slightly after
    STEP normalizes spline surfaces. In that case keep the original strict
    dimensional/volume/area tolerances, calculate those properties with
    adaptive integration, and require zero symmetric-difference solids to
    within 1e-6 cubic millimetres. Face counts are diagnostic, not geometry.
    """
    a, b = signature(source), signature(imported)
    result = dict(source_signature=a, imported_signature=b,
                  original_signature_match=signature_matches(a, b))
    if result['original_signature_match']:
        result.update(method='original strict signature', passed=True)
        return result
    print('  STEP normalization: compare adaptive properties and exact material differences', flush=True)
    properties = {}
    for label, shape in [('source', source), ('imported', imported)]:
        print(f'    {label}: adaptive volume properties', flush=True)
        vp, ap = GProp_GProps(), GProp_GProps()
        ve = BRepGProp.VolumeProperties_s(shape.wrapped, vp, 1e-10, True, False)
        print(f'    {label}: adaptive surface properties', flush=True)
        ae = BRepGProp.SurfaceProperties_s(shape.wrapped, ap, 1e-10, False)
        properties[label] = dict(volume_mm3=vp.Mass(), area_mm2=ap.Mass(),
                                 volume_integration_relative_error=ve,
                                 area_integration_relative_error=ae)
    differences = {}
    for label, x, y in [('removed_mm3', source, imported), ('added_mm3', imported, source)]:
        print(f'    Exact STEP normalization difference: {label}', flush=True)
        difference = x.cut(y)
        differences[label] = sum(s.Volume() for s in difference.Solids())
    accurate_a, accurate_b = properties['source'], properties['imported']
    volume_tolerance = max(1e-4, abs(accurate_a['volume_mm3'])*1e-8)
    area_tolerance = max(1e-4, abs(accurate_a['area_mm2'])*1e-8)
    bound_error = max(abs(x-y) for x, y in zip(a['bounds'], b['bounds']))
    passed = (source.isValid() and imported.isValid() and a['solids'] == b['solids'] == 1
              and bound_error < 1e-5
              and abs(accurate_a['volume_mm3']-accurate_b['volume_mm3']) <= volume_tolerance
              and abs(accurate_a['area_mm2']-accurate_b['area_mm2']) <= area_tolerance
              and all(v <= 1e-6 for v in differences.values()))
    result.update(method='adaptive OCC integration and exact symmetric difference',
                  adaptive_properties=properties, symmetric_difference=differences,
                  tolerance=dict(bounds_mm=1e-5, volume_mm3=volume_tolerance,
                                 area_mm2=area_tolerance, each_material_difference_mm3=1e-6),
                  max_bound_difference_mm=bound_error, passed=passed)
    assert passed, result
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidates', type=Path)
    args = parser.parse_args()
    bound = source_bindings()
    candidate = json.loads(args.candidates.read_text()) if args.candidates else None
    if candidate:
        assert all(sha(Path(name)) == value for name, value in candidate['sources'].items())
        source_rows = {r['name']: r for r in candidate['parts']}
        assert {'J901_H_frame', 'J909_housing'} <= source_rows.keys()
    rows = []
    for name, fn, destination, mirrored in [
            ('J901_H_frame', P.h_frame, P.ROOT, False),
            ('J909_housing', P.housing, P.ROOT, False),
            ('J901_H_frame_right', P.h_frame, P.ROOT.parent/'X1', True),
            ('J909_housing_right', P.housing, P.ROOT.parent/'X1', True)]:
        start = time.time()
        print('Export and verify', name, flush=True)
        if candidate:
            row = source_rows[name.removesuffix('_right')]
            assert sha(row['file']) == row['sha256']
            s = cq.Shape.importBrep(row['file'])
        else:
            s = P.one(fn())
        if mirrored:
            s = P.one(P.mirror_y(cq.Workplane(obj=s)))
        assert s.isValid() and len(s.Solids()) == 1
        step = destination/'step'/f'{name}.step'
        stl = destination/'stl'/f'{name}.stl'
        temp_step = step.with_name(name+'.revf_tmp.step')
        temp_stl = stl.with_name(name+'.revf_tmp.stl')
        cq.exporters.export(s, str(temp_step))
        rt = P.one(cq.importers.importStep(str(temp_step)))
        assert rt.isValid() and len(rt.Solids()) == 1
        equivalence = roundtrip_geometry(s, rt)
        angle = 90 if mirrored else -90
        mesh = E.export_stl(E.to_bed(cq.Workplane(obj=s), (1, 0, 0), angle), temp_stl)
        temp_step.replace(step)
        temp_stl.replace(stl)
        key = sha(step)
        cache = Path('/tmp/x1-part-cache')
        cache.mkdir(exist_ok=True)
        native = cache/(key+'.brep')
        rt.exportBrep(str(native))
        (cache/(key+'.json')).write_text(json.dumps(dict(step_sha256=key, brep_sha256=sha(native), signature=signature(rt))))
        result = dict(name=name, step_file=str(step.relative_to(P.REPO)), step_sha256=key,
                      stl_file=str(stl.relative_to(P.REPO)), stl_sha256=sha(stl),
                      step_roundtrip=True, step_roundtrip_evidence=equivalence,
                      solids=1, stl_watertight=bool(mesh.is_watertight),
                      stl_components=len(mesh.split()), print_bounds_mm=[round(v,3) for v in mesh.extents.tolist()],
                      volume_mm3=rt.Volume(), mirrored=mirrored,
                      print_orientation=f'Outer wall/skirt inner face on the bed; rotate X by {angle} degrees.',
                      source_sha256=bound, seconds=round(time.time()-start,2))
        rows.append(result)
        print(json.dumps(result), flush=True)
    assert source_bindings() == bound, 'Export source changed while running'
    print('Revision F track exports PASS', flush=True)


if __name__ == '__main__':
    main()

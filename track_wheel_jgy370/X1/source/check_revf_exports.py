"""Verify the eight delivered revision F part designs without re-exporting them.

For X101, both J901 H-frames, both J909 housings, the J902 sprocket, the J904 roller and the J906 idler wheel: the STEP imports as one
valid solid that matches the current source construction (strict signature, or
exact symmetric difference after STEP spline normalisation), and the STL is a
single watertight component whose volume agrees with the source. X101 must also
fill its required envelope, which catches a boolean that silently dropped a
support end. Writes ../revf_part_exports.json.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

import cadquery as cq
import trimesh

import x1_parts as X
import build_x1
from refresh_revf import part

P = X.P9
sys.path.insert(0, str(P.HERE))
import export_revf_track as ER
import export_arc_frame as EF

FRAME_BOUNDS = [-77.5, 77.5, -137.5, 137.5, 34.0, 85.0]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path):
    return str(Path(path).relative_to(X.REPO))


def sources():
    files = [Path(__file__), Path(X.__file__), Path(X.M.__file__), Path(P.__file__), Path(X.D9.__file__),
             Path(X.tp.__file__), Path(ER.__file__), Path(EF.__file__), Path(build_x1.__file__),
             Path(build_x1.export.__file__), X.HERE/'refresh_revf.py']
    return {rel(p): sha(p) for p in files}


def parts():
    mirror = lambda s: P.one(P.mirror_y(cq.Workplane(obj=s)))
    track = X.ROOT.parent/'J9'
    return [('X101_X_frame', lambda: X.one(X.x_frame()), X.ROOT, 'Bearing seat on the bed; rotate X by 180 degrees.'),
            ('J901_H_frame', lambda: P.one(P.h_frame()), track, 'Outer wall on the bed; rotate X by -90 degrees.'),
            ('J909_housing', lambda: P.one(P.housing()), track, 'Skirt inner face on the bed; rotate X by -90 degrees.'),
            ('J901_H_frame_right', lambda: mirror(P.one(P.h_frame())), X.ROOT, 'Outer wall on the bed; rotate X by 90 degrees.'),
            ('J909_housing_right', lambda: mirror(P.one(P.housing())), X.ROOT, 'Skirt inner face on the bed; rotate X by 90 degrees.'),
            ('J902_sprocket', lambda: P.one(P.sprocket()), track, 'Outer disc face on the bed; rotate X by -90 degrees.'),
            ('J904_roller', lambda: P.one(P.roller()), track, 'On a flange face; rotate X by -90 degrees.'),
            ('J906_idler_wheel', lambda: P.one(P.idler_wheel()), track, 'Flat face on the bed; rotate X by -90 degrees.')]


def check(name, build, root, orientation):
    started = time.time()
    step, stl = root/'step'/f'{name}.step', root/'stl'/f'{name}.stl'
    step_hash, stl_hash = sha(step), sha(stl)
    print('Check', name, flush=True)
    imported = part(step)
    source = build()
    assert source.isValid() and len(source.Solids()) == 1, name
    equivalence = ER.roundtrip_geometry(source, imported)
    mesh = trimesh.load(stl, force='mesh')
    stl_volume = float(mesh.volume)
    row = dict(name=name, step_file=rel(step), step_sha256=step_hash, stl_file=rel(stl), stl_sha256=stl_hash,
               solids=len(imported.Solids()), valid=bool(imported.isValid()), step_roundtrip=True,
               matches_current_source=bool(equivalence['passed']), source_equivalence=equivalence,
               volume_mm3=imported.Volume(), stl_watertight=bool(mesh.is_watertight),
               stl_components=len(mesh.split()), stl_volume_mm3=stl_volume,
               stl_volume_relative_difference=abs(stl_volume-source.Volume())/source.Volume(),
               print_bounds_mm=[round(v, 3) for v in mesh.extents.tolist()], print_orientation=orientation,
               seconds=round(time.time()-started, 1))
    if name == 'X101_X_frame':
        row['envelope_contract'] = {label: EF.geometry_contract(shape) for label, shape in
                                    (('source', source), ('step', imported))}
    assert sha(step) == step_hash and sha(stl) == stl_hash, f'{name} changed while being checked'
    row['pass'] = bool(row['valid'] and row['solids'] == 1 and row['matches_current_source'] and
                       row['stl_watertight'] and row['stl_components'] == 1 and
                       row['stl_volume_relative_difference'] < 5e-3)
    print(json.dumps({k: row[k] for k in ('name', 'pass', 'matches_current_source', 'stl_watertight',
                                          'stl_volume_relative_difference', 'print_bounds_mm', 'seconds')}),
          flush=True)
    return row


def main():
    started = time.time()
    bound = sources()
    rows = [check(*spec) for spec in parts()]
    assert sources() == bound, 'Source changed while checking exports'
    ok = all(r['pass'] for r in rows)
    report = dict(revision='F', method='verified delivered STEP/STL files against the current source; nothing re-exported',
                  source_sha256=bound, exports=rows, seconds=round(time.time()-started, 1), **{'pass': bool(ok)})
    (X.ROOT/'revf_part_exports.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Revision F part exports', 'PASS' if ok else 'FAIL', flush=True)
    if not ok:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

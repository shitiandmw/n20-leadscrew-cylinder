"""Measure revision F X101 arm cross-sections; geometry only.

Section areas, centroidal second moments and separate-axis I/c values are
measured from B-rep sections of the delivered STEP parts. This is not a
strength acceptance gate, stress analysis or payload qualification.
"""
import hashlib
import json
import time
from pathlib import Path

import cadquery as cq
from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt

import x1_parts as X
from refresh_revf import part

ROOT, REPO = X.ROOT, X.REPO
# Root bend at Y 96, head slots Y 97..127, plate face Y 136, arm end Y 137.5.
SAMPLES = (90., 96., 97.5, 100., 103., 106., 108., 110., 115., 120., 124., 126.99,
           127.5, 130., 132., 133., 134., 135., 135.99)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def section(shape, y):
    tool = BRepAlgoAPI_Section(shape.wrapped, gp_Pln(gp_Pnt(0,y,0), gp_Dir(0,1,0)), False)
    tool.Approximation(False)
    tool.Build()
    assert tool.IsDone()
    edges = [e for e in cq.Shape.cast(tool.Shape()).Edges() if e.Center().x > 0]
    wires = cq.Wire.combine(edges)
    # One outer boundary; beyond the head slots the two plain screw bores are holes.
    wires = sorted(wires, key=lambda w: -cq.Face.makeFromWires(w).Area())
    outer, holes = wires[0], wires[1:]
    assert len(holes) in (0, 2), (y, len(wires))
    face = cq.Face.makeFromWires(outer, holes)
    assert face.isValid() and face.Area() < cq.Face.makeFromWires(outer).Area()+1e-9
    return face


def metrics(face):
    props = GProp_GProps()
    error = BRepGProp.SurfaceProperties_s(face.wrapped, props, 1e-10, False)
    c, inertia, b = props.CentreOfMass(), props.MatrixOfInertia(), face.BoundingBox()
    ix, iz = inertia.Value(1,1), inertia.Value(3,3)
    return dict(area_mm2=props.Mass(), centroid_xz_mm=[c.X(),c.Z()],
                Ix_mm4=ix, Iz_mm4=iz, product_Ixz_mm4=inertia.Value(1,3),
                vertical_I_over_c_mm3=min(ix/(b.zmax-c.Z()), ix/(c.Z()-b.zmin)),
                lateral_I_over_c_mm3=min(iz/(b.xmax-c.X()), iz/(c.X()-b.xmin)),
                bounds_xz_mm=[b.xmin,b.xmax,b.zmin,b.zmax],
                numerical_integration_relative_error=error)


def main():
    start = time.time()
    current = ROOT/'step/X101_X_frame.step'
    sources = [Path(__file__), X.HERE/'refresh_revf.py', Path(X.__file__), Path(X.M.__file__)]
    bound = {str(p.relative_to(REPO)): sha(p) for p in sources+[current]}
    frame = part(current)
    rows = []
    fields = ('area_mm2', 'vertical_I_over_c_mm3', 'lateral_I_over_c_mm3')
    for y in SAMPLES:
        # Move 0.1 micrometres off topology seams; record the exact plane used.
        plane = y+.0001
        row = dict(nominal_Y_mm=y, section_plane_Y_mm=plane, **metrics(section(frame, plane)))
        rows.append(row)
        print(json.dumps(dict(Y_mm=y, **{k: row[k] for k in fields})), flush=True)
    minima = {}
    for label, selected in [('all_sampled_planes', rows),
                            ('straight_arm_planes_Y96_to_135p99', [r for r in rows if r['nominal_Y_mm'] >= 96])]:
        minima[label] = {}
        for field in fields:
            r = min(selected, key=lambda d: d[field])
            minima[label][field] = dict(minimum_sampled_value=r[field], nominal_Y_mm=r['nominal_Y_mm'])
    assert all(sha(REPO/p) == value for p, value in bound.items())
    report = dict(revision='F', geometry_calculation_pass=True, source_and_step_sha256=bound,
                  rows=rows, minima=minima,
                  method='Exact OpenCascade BRep section of the positive-X arm at each stated vehicle Y plane. '
                         'Adaptive surface integration gives area and centroidal inertia. '
                         'I/c uses the more distant extreme fibre for each coordinate axis.',
                  scope='Sampled geometric section properties, not a continuous minimum search or structural acceptance gate. '
                        'These separate-axis values do not model combined bending, shear, torsion, stress concentrations, '
                        'fastener preload, material anisotropy, print defects or fatigue. No payload rating is claimed.',
                  not_strength_validation=True, elapsed_s=round(time.time()-start, 2))
    (ROOT/'revf_leg_sections.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(minima, indent=2), flush=True)


if __name__ == '__main__':
    main()

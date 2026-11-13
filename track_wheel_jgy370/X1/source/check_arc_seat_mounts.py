"""Nominal geometry checks for revision F straight X101 arms seated in plain main-plate recesses.

Checks use the delivered STEP parts and the checked STEP assemblies. Every case,
including the central bearing-seat and belly-cover tool access, is computed
fresh on revision F geometry. No printed strength, bolt preload, torque,
fatigue or payload rating is established.
"""
import argparse
import gzip
import hashlib
import json
import math
import tempfile
import time
from pathlib import Path

import cadquery as cq
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.gp import gp_Vec

import x1_parts as X
import mount_checks as V
from refresh_revf import cached_assembly, components_from_assembly, part as step_part

P, D, M, tp = X.P9, X.D9, X.M, X.tp
ROOT, REPO = X.ROOT, P.REPO
PROOFS = [ROOT/'revf_part_exports.json', P.ROOT/'revf_track_validation.json',
          ROOT/'revf_refresh_validation.json']
SPEC = dict(stations=[-63.5, 63.5], wing_offsets=[-9.5, 9.5],
            plate_face_y=-34.0, face_y=-32.5, wall_back_y=-24.0,
            face_z=[53.0, 74.0], arm_width=28.0, centre_web=9.0,
            seat_depth=1.5, seat_side_clearance=.15,
            head_face_y=-43.0, clamp_y=[-43.0, -32.5], slot_y=[-73.0, -43.0], slot_z=[62.75, 72.75],
            bolt_z=67.75, bore_radius=2.25,
            screw_length=25.0, washer_t=.8, nut_y=[-23.2, -20.0],
            nut_af=7.0, remaining_plate_mm=8.5, nominal_screw_tip_y=-18.8)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path):
    return str(Path(path).relative_to(REPO))


def bindings(include_track_validation=True):
    import refresh_revf, x1_turntable, build_j9
    files = [Path(__file__), Path(X.__file__), Path(P.__file__), Path(D.__file__),
             Path(M.__file__), Path(V.__file__), Path(V.checks.__file__),
             Path(tp.__file__), Path(tp.ex.__file__),
             Path(refresh_revf.__file__),
             Path(x1_turntable.__file__), Path(build_j9.__file__),
             Path(x1_turntable.R3.__file__)]
    steps = [P.ROOT/'step'/f'{n}.step' for n in P.PRINTED]
    steps += [ROOT/'step'/f'{n}.step' for n in
              ('X101_X_frame', 'X102_belly_cover', 'J901_H_frame_right', 'J909_housing_right')]
    meshes = [p.parent.parent/'stl'/p.with_suffix('.stl').name for p in steps]
    assemblies = [P.ROOT/'step/JGY370_track_J9.step', ROOT/'step/X1_crawler_chassis.step',
                  P.HERE/'j9_scene.json.gz']
    upper = [ROOT/'step/X1_turntable_assembly.step', ROOT/'source/turntable_scene.json.gz']
    arm = [REPO/'excavator_arm_60mm/step'/name for name in
           ('01_fixed_pivot_base.step', 'excavator_arm_assembly.step')]
    return dict(source_sha256={rel(p): sha(p) for p in files},
                exported_step_sha256={rel(p): sha(p) for p in steps},
                exported_stl_sha256={rel(p): sha(p) for p in meshes},
                assembly_input_sha256={rel(p): sha(p) for p in assemblies},
                upper_assembly_input_sha256={rel(p): sha(p) for p in upper},
                arm_reference_input_sha256={rel(p): sha(p) for p in arm},
                reference_files_sha256={rel(p): sha(p) for p in PROOFS
                                        if include_track_validation or p.name != 'revf_track_validation.json'})


def verify_proofs(allow_pending_track=False):
    def verify_file(name, expected):
        path = Path(name)
        if not path.is_absolute():
            path = REPO/path
        assert path.is_file() and sha(path) == expected, f'Stale proof input: {name}'

    def verify_row(row):
        if not isinstance(row, dict):
            return
        verify_current_maps(row)
        for stem in ('step', 'stl'):
            if stem+'_file' in row and stem+'_sha256' in row:
                verify_file(row[stem+'_file'], row[stem+'_sha256'])
        if 'file' in row and 'sha256' in row:
            verify_file(row['file'], row['sha256'])
        if 'pass' in row:
            assert row['pass'] is True, 'Assembly/export row did not pass'

    def verify_current_maps(d):
        # Nested baseline mappings describe historical bytes; only these
        # declared current-input mappings are checked against the workspace.
        for field in ('source_sha256', 'exported_step_sha256',
                      'exported_stl_sha256', 'reference_files_sha256',
                      'assembly_input_sha256', 'upper_assembly_input_sha256',
                      'arm_reference_input_sha256', 'current_candidate_files_sha256', 'inputs'):
            mapping = d.get(field, {})
            if isinstance(mapping, dict):
                for name, expected in mapping.items():
                    if isinstance(expected, str) and len(expected) == 64:
                        verify_file(name, expected)

    reports = {}
    for path in PROOFS:
        if allow_pending_track and path.name == 'revf_track_validation.json':
            continue
        d = json.loads(path.read_text())
        # The export inventory can be a list of individually checked rows.
        if isinstance(d, dict):
            assert d.get('pass') is True, f'Proof has not passed: {path}'
            verify_current_maps(d)
            for field in ('exports', 'parts', 'assemblies', 'scenes', 'rows'):
                if isinstance(d.get(field), list):
                    for row in d[field]:
                        verify_row(row)
        else:
            assert isinstance(d, list) and d, path
            for row in d:
                verify_row(row)
        reports[path.name] = d
    exports = reports['revf_part_exports.json']['exports']
    assert {row['name'] for row in exports} == {
        'X101_X_frame', 'J901_H_frame', 'J909_housing', 'J901_H_frame_right', 'J909_housing_right',
        'J902_sprocket', 'J904_roller', 'J906_idler_wheel'}
    assert all(row['step_roundtrip'] and row['stl_watertight'] and row['matches_current_source'] and
               row['solids'] == 1 and row['stl_components'] == 1 for row in exports)
    if not allow_pending_track:
        track = reports['revf_track_validation.json']
        assert track['validation_method'].startswith('fresh'), 'Track validation must be a fresh full run'
        assert track['spring_guide_report_sha256'] == sha(P.ROOT/'spring_guide_validation.json')
    return reports


class Checkpoint:
    def __init__(self, inputs):
        # Proof reports are acceptance evidence, not numerical inputs. A
        # geometry-only preflight may reuse exact cases after the final J9
        # proof arrives, but only with identical source, CAD and scene bytes.
        numerical = {k: v for k, v in inputs.items() if k != 'reference_files_sha256'}
        self.fingerprint = hashlib.sha256(json.dumps(numerical, sort_keys=True).encode()).hexdigest()
        ident = hashlib.sha256(str(ROOT).encode()).hexdigest()[:12]
        self.path = Path(tempfile.gettempdir())/f'x1-revf-joint-{ident}-checkpoints.json'
        old = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.results = old.get('results', {}) if old.get('fingerprint') == self.fingerprint else {}
        self.reused = 0
        print(f'Checkpoint: {self.path}; {len(self.results)} completed cases', flush=True)

    def run(self, name, fn):
        if name not in self.results:
            result = fn()
            self.results[name] = result
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(dict(fingerprint=self.fingerprint, results=self.results)))
            temporary.replace(self.path)
            V._BOX_CACHE.clear()
            print(f'  {name}: checked', flush=True)
        else:
            self.reused += 1
            print(f'  {name}: reused identical inputs', flush=True)
        return self.results[name]


def load_current():
    """Use actual STEP bytes, with native caches checked against those bytes."""
    raw = components_from_assembly(cached_assembly(P.ROOT/'step/JGY370_track_J9.step'))
    scene = json.loads(gzip.decompress((P.HERE/'j9_scene.json.gz').read_bytes()))
    lookup = {d['name']: d for d in scene['unit']}
    track = {}
    for name, row in raw.items():
        d = lookup.get(name)
        if d is None:
            assert name.startswith(('shoe_', 'track_bushing_', 'track_pin_', 'pin_clip_')), name
            d = dict(group='track', color=[.5, .5, .5], kind='hardware', source=None)
        track[name] = {k: d[k] for k in ('group', 'color', 'kind', 'source')}
        track[name]['shape'] = cq.Workplane(obj=row['shape'])
    # The revised individual manufacturing parts, not independent mirrors or
    # source-only stand-ins, are used at the actual interfaces.
    for n in ('J901_H_frame', 'J909_housing'):
        track[n]['shape'] = cq.Workplane(obj=step_part(P.ROOT/'step'/f'{n}.step'))
    own = {n: dict(shape=cq.Workplane(obj=step_part(ROOT/'step'/f'{n}.step')))
           for n in ('X101_X_frame', 'X102_belly_cover')}
    original = X.chassis_parts
    try:
        X.chassis_parts = lambda: own
        inst = X.unit(track)
    finally:
        X.chassis_parts = original
    for n in ('J901_H_frame', 'J909_housing'):
        inst[f'R_{n}']['shape'] = cq.Workplane(obj=step_part(
            ROOT/'step'/f'{n}_right.step')).translate((0, -X.TRACK_Y, 0))
    return inst


def upper_parts():
    import x1_turntable as T
    raw = components_from_assembly(cached_assembly(ROOT/'step/X1_turntable_assembly.step'))
    scene = json.loads(gzip.decompress((ROOT/'source/turntable_scene.json.gz').read_bytes()))
    groups = {row['name']: row['group'] for row in scene['items']}
    pieces = {}
    for name, row in raw.items():
        if name == 'JGY370_lead_space':
            pieces[name] = dict(shape=cq.Workplane(obj=row['shape']), group='upper')
            continue
        if name not in groups:
            continue
        if name == 'ARM60_arm_and_actuators':
            for i, solid in enumerate(row['shape'].Solids()):
                pieces[f'ARM60_rest_solid_{i:03}'] = dict(shape=cq.Workplane(obj=solid), group='arm')
        else:
            pieces[name] = dict(shape=cq.Workplane(obj=row['shape']), group=groups[name])
    # The established turntable STEP includes the fixed ARM60 base but omits
    # the arm/actuator compound; its viewer includes that reference geometry.
    # Check the exact original arm STEP at the same placement and bind those
    # reference bytes explicitly in the report.
    if not any(n.startswith('ARM60_rest_') for n in pieces):
        _, arm, _ = T.arm60()
        for i, solid in enumerate(X.one(arm).Solids()):
            pieces[f'ARM60_rest_solid_{i:03}'] = dict(shape=cq.Workplane(obj=solid), group='arm')
    assert 'ARM60_fixed_pivot_base' in pieces and any(n.startswith('ARM60_rest_') for n in pieces)
    return pieces, T


def contract():
    assert list(M.STATIONS) == SPEC['stations']
    assert list(M.FACE_Z) == SPEC['face_z'] and [M.HEAD_FACE_Y, M.FACE_Y] == SPEC['clamp_y']
    assert M.FACE_Y == SPEC['face_y'] and M.WALL_Y[1] == SPEC['wall_back_y']
    assert M.PLATE_FACE_Y == SPEC['plate_face_y'] and M.HEAD_FACE_Y == SPEC['head_face_y']
    assert M.WIDTH == SPEC['arm_width'] and M.BOLT_OFFSET == 9.5 and M.WEB == SPEC['centre_web']
    assert list(M.SLOT_Y) == SPEC['slot_y'] and list(M.SLOT_Z) == SPEC['slot_z']
    assert M.CROWN_Z == 57.5 and M.CROWN_Y == -62.0 and X.SEAT_Y == 137.5 and X.PLATE_Y == 136.0
    assert M.SEAT_DEPTH == SPEC['seat_depth'] and M.SEAT_SIDE_CLEARANCE == SPEC['seat_side_clearance']
    assert list(M.BOLT_Z) == [SPEC['bolt_z']] and M.HOLE_R == SPEC['bore_radius']
    assert M.BOLT_L == 25.0 and M.WASHER['t'] == .8 and list(M.NUT_Y) == SPEC['nut_y']
    assert M.NUT['af'] == 7.0
    assert [(x, z) for _, _, x, z in M.bolt_centres()] == [
        (-73.0, 67.75), (-54.0, 67.75), (54.0, 67.75), (73.0, 67.75)]


def bearing_contract(station, penetration=.01):
    """Independent flat-seat contact, allowing the retained rear motor relief.

    The 28 mm arm end rests on the 1.5 mm seat ledge at Z53. At the rear the
    ledge crosses the existing radius-12.8 motor-clearance cylinder.
    Integrating its circular boundary over the .01 mm downward probe avoids
    confusing that finite probe with the infinitesimal contact area.
    """
    width = SPEC['arm_width']
    nominal = width*SPEC['seat_depth']
    if station > 0:
        return dict(expected_probe_area_mm2=nominal,
                    contact_limit_area_mm2=nominal, motor_relief_reduction_mm2=0.)
    radius, cy, cz = 12.8, -43.2, 44.32050807568877
    def primitive(u):
        return .5*(u*math.sqrt(radius**2-u*u)+radius**2*math.asin(u/radius))
    u1, u0 = 53.-cz, 53.-penetration-cz
    mean_y = cy+(primitive(u1)-primitive(u0))/penetration
    at_contact_y = cy+math.sqrt(radius**2-u1*u1)
    removed_probe = width*(mean_y-(-34.))
    removed_limit = width*(at_contact_y-(-34.))
    assert 0 < removed_limit < nominal
    return dict(expected_probe_area_mm2=nominal-removed_probe,
                contact_limit_area_mm2=nominal-removed_limit,
                motor_relief_reduction_mm2=removed_limit,
                retained_motor_clearance_circle=dict(radius_mm=radius, centre_y_mm=cy, centre_z_mm=cz),
                formula='42 - 28 * mean(cy + sqrt(R^2 - (z-cz)^2) + 34), z=52.99..53 mm')


def intersections(a, b):
    return V.against(a, b)


def closest_disjoint(shape, others):
    """Exact whole-shape OCC distance after a fresh solid overlap check.

    SetMultiThread precedes Perform; passing shapes to the constructor would
    start the expensive operation before the setting is applied. Component
    AABB distances provide conservative pruning, and exact point witnesses
    are retained for every tested nearest-distance operation.
    """
    overlap = intersections(others, {'distance_probe': dict(shape=shape, group='probe')})
    if overlap['hits']:
        return dict(mm=0., overlapping=True, hits=overlap['hits'])
    first = X.one(shape)
    queue = sorted((V.bbox_distance(first.BoundingBox(), V.bound(d)), n) for n, d in others.items())
    best, nearest, trials = math.inf, None, []
    for lower, name in queue:
        if lower > best+1e-7:
            break
        began = time.time()
        tool = BRepExtrema_DistShapeShape()
        tool.LoadS1(first.wrapped)
        tool.LoadS2(X.one(others[name]['shape']).wrapped)
        tool.SetMultiThread(True)
        tool.Perform()
        assert tool.IsDone() and tool.NbSolution() > 0, f'Distance failed: {name}'
        value = float(tool.Value())
        assert math.isfinite(value) and value >= 0
        a, b = tool.PointOnShape1(1), tool.PointOnShape2(1)
        pa, pb = [a.X(), a.Y(), a.Z()], [b.X(), b.Y(), b.Z()]
        assert abs(math.dist(pa, pb)-value) < 1e-5
        trials.append(dict(part=name, mm=value, aabb_lower_bound_mm=lower,
                           point_on_first_mm=pa, point_on_second_mm=pb,
                           seconds=round(time.time()-began, 3)))
        if value < best:
            best, nearest = value, name
    return dict(mm=round(best, 5), part=nearest, trials=trials,
                method='OCC BRepExtrema_DistShapeShape, SetMultiThread(True) before Perform; '
                       'fresh non-overlap check and conservative component AABB pruning')


def key_stroke_angles(x):
    """Handle out of the side slot: 30 degrees below to 30 degrees above horizontal."""
    return (-30., 30.)


def key_stroke_envelope(x, z):
    """Conservative continuous 60-degree stroke for the ordinary 3 mm L-key.

    A filled 80 mm XZ sector, offset outwards by 1.75 mm and extruded
    6.5 mm along Y, contains every handle pose over the 60-degree stroke
    out of the side slot and the 3 mm withdrawal needed for re-indexing.
    The short leg stays on the screw axis throughout that rotation.
    """
    head_end = M.HEAD_FACE_Y-M.WASHER['t']-M.HEAD['h']
    bend_y = head_end-18.0
    a, b = key_stroke_angles(x)
    sg = X.key_side(x)
    def point(angle):
        return sg*80*math.cos(math.radians(angle)), 80*math.sin(math.radians(angle))
    sector = (cq.Workplane('XZ', origin=(x, bend_y-1.5, z)).moveTo(0, 0)
              .lineTo(*point(a)).threePointArc(point((a+b)/2), point(b))
              .close().offset2D(1.75).extrude(3.25, both=True))
    return sector.union(tp.ycyl(1.75, bend_y-3.0, head_end-.05, x, z))


def nut_socket_envelope(x, z):
    """7 mm nut-holding socket and upright handle, before sprocket/chain fit.

    A 7.1 mm AF cavity clears the idealized nut while retaining the actual
    11.2 mm tool outside. The stem and handle are conservative solid envelopes.
    """
    shell = tp.ycyl(5.6, -23.15, -10., x, z)
    shell = shell.cut(P.yhex(7.1, -24., -15., x, z))
    shell = shell.cut(tp.ycyl(2.5, -24., -9., x, z))
    return shell.union(tp.ycyl(5.6, -10., 5., x, z)).union(
        tp.zcyl(5.6, z, z+60., x, 5.))


SCREW_WITHDRAWAL, SCREW_SIDE_OFFSET, SCREW_LIFT = 24.25, 10., 30.


def screw_entry_envelopes(x, z):
    """Complete sideways-entry and axial insertion envelopes for M4x25 with its washer.

    Withdrawn 24.25 mm, the screw lies in the arm's side slot with its tip
    .05 mm short of the slot end. It enters sideways from 10 mm outside its
    final axis (clear of the arm), having been lowered 30 mm there, then
    advances into the plain bores.
    """
    sg = X.key_side(x)
    xo = x+sg*SCREW_SIDE_OFFSET
    components = [(3.5, -47.8, -43.8), (4.5, -43.8, -43.), (2., -43.8, -18.8)]
    side, axial = [], []
    for radius, y0, y1 in components:
        dy0, dy1 = y0-SCREW_WITHDRAWAL, y1-SCREW_WITHDRAWAL
        xa, xb = sorted((x, xo))
        slide = tp.box(xa, xb, dy0, dy1, z-radius, z+radius).union(
            tp.ycyl(radius, dy0, dy1, x, z)).union(tp.ycyl(radius, dy0, dy1, xo, z))
        drop = tp.box(xo-radius, xo+radius, dy0, dy1, z, z+SCREW_LIFT).union(
            tp.ycyl(radius, dy0, dy1, xo, z+SCREW_LIFT))
        side.append(slide.union(drop))
        axial.append(tp.ycyl(radius, dy0, y1, x, z))
    def united(pieces):
        result=pieces[0]
        for piece in pieces[1:]:
            result=result.union(piece)
        result=result.clean()
        assert X.one(result).isValid() and len(X.one(result).Solids())==1
        return result
    return united(side), united(axial)


def socket_route_envelopes(x,z):
    """Continuous 80 mm approach from above, then 12 mm axial engagement."""
    shell = tp.ycyl(5.6,-23.15,2.,x,z).cut(P.yhex(7.1,-24.,-15.,x,z))
    shell = shell.cut(tp.ycyl(2.5,-24.,3.,x,z))
    withdrawal = shell.union(tp.ycyl(5.6,-10.,17.,x,z)).union(
        tp.box(x-5.6,x+5.6,-.6,22.6,z,z+60.)).clean()
    # At 12 mm withdrawal the socket is clear of the nut. Rectangular
    # envelopes conservatively contain every vertical insertion pose.
    drop = tp.box(x-5.6,x+5.6,-11.15,2.,z-5.6,z+85.6).union(
        tp.box(x-5.6,x+5.6,2.,17.,z-5.6,z+85.6)).union(
        tp.box(x-5.6,x+5.6,11.4,22.6,z,z+140.)).clean()
    return drop,withdrawal


def sprocket_route_envelopes():
    """Conservative continuous sweeps of the complete sprocket/hub assembly.

    Fresh containment proofs verify actual STEP components against the base
    envelopes. The radial capsule contains all -150..0 mm X translations at
    Y offset9.6. Three coaxial bands contain all 0..9.6 mm axial translations:
    the coupling boss, the coupling flange with the sprocket-screw tips past
    it, and the sprocket from its inboard ring face (sizes from j9_design, so
    they follow the hub). The D-profile shaft clearance stays empty below its
    fixed tip throughout positive-Y movement. Material above its flat includes
    the radial set-screw tip, which must not be excluded by a circular bore
    approximation.
    """
    x,z=D.DRIVE_X,D.AXLE_Z
    radius=D.SPROCKET_TIP_R+.01
    radial_seed=tp.ycyl(radius,-13.41,18.11,x,z)
    radial=tp.box(x-150.,x,-13.41,18.11,z-radius,z+radius).union(
        tp.ycyl(radius,-13.41,18.11,x-150.,z)).union(radial_seed).clean()
    flange_back=D.HUB_FACE_Y-D.HUB['flange_t']
    boss_end=flange_back-D.HUB['boss_h']
    screw_tip=D.SPROCKET_Y[1]-P.M3_HEAD['h']-D.HUB_SCREW_L
    def bands(ymax):
        shape=tp.ycyl(D.HUB['boss_r']+.1,boss_end-.01,ymax,x,z).union(
            tp.ycyl(D.HUB['flange_r']+.1,min(flange_back,screw_tip)-.01,ymax,x,z)).union(
            tp.ycyl(radius,D.SPROCKET_Y[0]-.01,ymax,x,z))
        flat_z=z+D.SHAFT_FLAT['across']-3.
        clearance=tp.ycyl(3.,-24.,D.SHAFT_TIP_Y,x,z).intersect(
            tp.box(x-4.,x+4.,-24.,D.SHAFT_TIP_Y,z-4.,flat_z))
        assert boss_end-.01 > D.SHAFT_TIP_Y-D.SHAFT_FLAT['length'] and boss_end-.01 > -24.
        return shape.cut(clearance).clean()
    return radial_seed,radial,bands(8.51),bands(18.11)


def vertical_frame_sweep(frame, fixed, lift=80.):
    """Exact continuous translation of STEP boundary faces through +Z.

    The installed solid plus these face prisms contains the entire translated
    solid: any newly occupied point enters through its moving boundary.
    Separating boxes discard only faces whose whole sweep misses every fixed
    component. Zero-volume side-face sweeps cannot introduce solid overlap.
    """
    shape = X.one(frame)
    fixed_boxes = {n: V.bound(d) for n, d in fixed.items()}
    members = {'installed_frame': dict(shape=frame, group='swept_frame')}
    skipped, zero, prisms = 0, 0, []
    for i, face in enumerate(shape.Faces()):
        b = face.BoundingBox()
        def near(c):
            return (b.xmin <= c.xmax+.05 and b.xmax >= c.xmin-.05 and
                    b.ymin <= c.ymax+.05 and b.ymax >= c.ymin-.05 and
                    b.zmin <= c.zmax+.05 and b.zmax+lift >= c.zmin-.05)
        if not any(near(c) for c in fixed_boxes.values()):
            skipped += 1
            continue
        operation = BRepPrimAPI_MakePrism(face.wrapped, gp_Vec(0, 0, lift), True, True)
        assert operation.IsDone(), ('Vertical face sweep failed', i)
        swept = cq.Shape.cast(operation.Shape())
        count = 0
        for j, solid in enumerate(swept.Solids()):
            volume = solid.Volume()
            if abs(volume) < 1e-7:
                continue
            if volume < 0:
                solid = cq.Shape.cast(solid.wrapped.Reversed())
            assert solid.isValid() and solid.Volume() > 0, ('Invalid face prism', i, j)
            name = f'frame_face_prism_{i}_{j}'
            members[name] = dict(shape=cq.Workplane(obj=solid), group='swept_frame')
            prisms.append(dict(face_index=i, prism_index=j, volume_mm3=solid.Volume()))
            count += 1
        zero += count == 0
    start_clearance = shape.BoundingBox().zmin+lift-max(b.zmax for b in fixed_boxes.values())
    assert start_clearance > 0, 'Vertical approach does not start fully above the prepared tracks'
    return members, dict(lift_mm=lift, boundary_face_count=len(shape.Faces()),
                         separating_box_rejections=skipped, zero_volume_face_sweeps=zero,
                         positive_volume_prisms=prisms,
                         start_horizontal_plane_clearance_mm=start_clearance,
                         negligible_prism_volume_mm3=1e-7,
                         method='Actual STEP boundary-face prisms plus the installed frame contain every '
                                'translation between 0 and 80 mm vertical lift. Each retained prism is '
                                'a valid solid with positive orientation; excluded faces have separating '
                                'swept boxes or negligible volume. No sampled-pose interpolation is assumed.')


def track_service_routes(every, prepared_tracks, upper, drop=80.):
    """Prove per-track downward withdrawal and subsequent outward departure.

    Relative frame/track motion is the inverse of the checked continuous
    vertical fitting sweep. Every other retained component must have a
    separating bounding box over the complete drop. After the drop, fixed
    X/Z separation or the outward Y half-space proves unlimited departure.
    The affected motor leads and all four joint fastener groups are removed.
    """
    assert not any(n == 'X101_X_frame' or n.startswith('mount_') for n in upper)
    routes = []
    for side, tag in ((1, 'L'), (-1, 'R')):
        moving = {n: d for n, d in prepared_tracks.items() if n.startswith(tag+'_')}
        boxes = [V.bound(d) for d in moving.values()]
        bounds = {axis+end: (min if end == 'min' else max)(getattr(b, axis+end) for b in boxes)
                  for axis in 'xyz' for end in ('min', 'max')}
        fixed = {n: d for n, d in every.items() if not n.startswith(tag+'_') and
                 not (n.startswith('mount_') and f'_{tag}' in n) and n != f'cable_route_{tag}'}
        fixed.update({f'upper_{n}': d for n, d in upper.items()})
        swept = {**bounds, 'zmin': bounds['zmin']-drop}
        lowered = {**bounds, 'zmin': bounds['zmin']-drop, 'zmax': bounds['zmax']-drop}
        vertical, lateral = [], []
        for name, data in fixed.items():
            b = V.bound(data)
            def gaps(m):
                return {axis: max(getattr(b, axis+'min')-m[axis+'max'],
                                  m[axis+'min']-getattr(b, axis+'max')) for axis in 'xyz'}
            if name != 'X101_X_frame':
                g = gaps(swept)
                axis = max(g, key=g.get)
                assert g[axis] > 1e-6, ('Service drop bounding proof inconclusive', tag, name, g)
                vertical.append(dict(fixed_component=name, separating_axis=axis, gap_mm=g[axis]))
            g = gaps(lowered)
            # Outward movement increases this Y gap monotonically. A gap on
            # the other Y side would not establish an unlimited route.
            g['y'] = (lowered['ymin']-b.ymax if side > 0 else b.ymin-lowered['ymax'])
            axis = max(g, key=g.get)
            assert g[axis] > 1e-6, ('Service departure bounding proof inconclusive', tag, name, g)
            lateral.append(dict(fixed_component=name, separating_axis=axis, gap_mm=g[axis]))
        routes.append(dict(side=tag, drop_mm=drop, prepared_component_count=len(moving),
                           prepared_component_names=sorted(moving), installed_bounds_mm=bounds,
                           lowered_bounds_mm=lowered,
                           preparation='Support the chassis and affected track; park the upper at 0 degrees. '
                                       'Remove the affected chain, rear sprocket/hub/journal, all four joint '
                                       'fastener groups, and disconnect and secure that motor cable.',
                           route='Lower the prepared affected track vertically 80 mm, then move it '
                                 'outward horizontally. Do not pull it sideways while seated.',
                           frame_withdrawal_proof='Exact inverse relative motion of continuous_vertical_fitting.',
                           remaining_parts_during_drop=vertical,
                           unlimited_outward_departure=lateral,
                           hits=[], pass_=True,
                           method='Conservative component AABB separating planes over the entire vertical '
                                  'drop, plus X/Z separation or a monotonic outward Y half-space for lateral '
                                  'departure. Full bound ARM60 reference at the parked pose is included.'))
    return routes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-checkpoints', action='store_true')
    parser.add_argument('--geometry-preflight', action='store_true',
                        help='Check and cache identical geometry while final J9 validation is pending; '
                             'does not publish arc_seat_mount_validation.json or any final PASS.')
    args = parser.parse_args()
    started = time.time()
    contract()
    proofs = verify_proofs(allow_pending_track=args.geometry_preflight)
    current_bindings = lambda: bindings(include_track_validation=not args.geometry_preflight)
    initial = current_bindings()
    checkpoint = Checkpoint(initial)
    if args.no_checkpoints:
        checkpoint.results.clear()
    run = checkpoint.run
    inst = load_current()
    assert current_bindings() == initial, 'Inputs changed during STEP loading'
    every = {n: d for n, d in inst.items() if d['group'] != 'reserve'}
    for side, tag in ((1, 'L'), (-1, 'R')):
        every[f'cable_route_{tag}'] = dict(shape=X.cable_route(side), group='cable')
    primary = {n: d for n, d in every.items() if n == 'X101_X_frame' or n.startswith('mount_')}
    others = {n: d for n, d in every.items() if n not in primary}
    xf = every['X101_X_frame']['shape']
    bb = X.one(xf).BoundingBox()
    assert all(abs(a-b) < 1e-4 for a,b in zip(
        (bb.xmin,bb.xmax,bb.ymin,bb.ymax,bb.zmin,bb.zmax),
        (-77.5,77.5,-137.5,137.5,34.,85.))), 'Frame lost an arm end or changed its required envelope'
    no_chain = {n: d for n, d in every.items() if d['group'] not in ('L_track', 'R_track')}
    print('Current X101 and all joint hardware versus complete tracks', flush=True)
    static = run('static', lambda: intersections(others, primary))
    internal = run('internal_joint', lambda: V.checks.interference(primary))
    critical = [static, internal]
    if static['hits'] or internal['hits']:
        print(json.dumps(dict(static=static['hits'], internal=internal['hits'])), flush=True)

    print('Arm end faces, seat ledges and plain-hole wall stock', flush=True)
    interfaces = []
    for side, tag in ((1, 'L'), (-1, 'R')):
        hframe = inst[f'{tag}_J901_H_frame']['shape']
        for i, station in enumerate(SPEC['stations']):
            def measure():
                crop = V.vehicle(tp.box(station-19, station+19, -44, -32.499,
                                        52.999, 74.001), side)
                end = xf.intersect(crop)
                axial = V.volume(end.translate((0, side*.01, 0)).intersect(hframe))/.01
                bearing = V.volume(end.translate((0, 0, -.01)).intersect(hframe))/.01
                floor = tp.box(station-14, station+14, -32.5, -24, 53, 74)
                for dx in (-9.5, 9.5):
                    floor = floor.cut(tp.ycyl(2.25, -33, -23, station+dx, 67.75))
                missing = V.volume(V.vehicle(floor, side).cut(hframe))
                support = bearing_contract(station)
                arm_points=[]
                for dx,local_y,z,expected,what in [
                        (0.,-55.,67.75,True,'centre web'),(-9.5,-55.,67.75,False,'head slot'),(9.5,-55.,67.75,False,'head slot'),
                        (-9.5,-55.,75.,True,'deck over slot'),(9.5,-55.,75.,True,'deck over slot'),
                        (-9.5,-55.,60.,True,'base under slot'),(9.5,-55.,60.,True,'base under slot'),
                        (-14.5,-55.,65.,False,'outside arm'),(14.5,-55.,65.,False,'outside arm'),
                        (-13.,-72.,60.,True,'arm at slot start'),(13.,-72.,60.,True,'arm at slot start'),
                        (-9.5,-74.5,67.75,False,'round slot end'),(9.5,-74.5,67.75,False,'round slot end'),
                        (-9.5,-76.5,63.,True,'beyond slot end'),(9.5,-76.5,63.,True,'beyond slot end'),
                        (-13.5,-40.,60.,True,'clamped end'),(13.5,-40.,60.,True,'clamped end'),
                        (-9.5,-38.,67.75,False,'plain bore'),(9.5,-38.,67.75,False,'plain bore'),
                        (-13.,-33.,53.5,True,'end in seat'),(13.,-33.,53.5,True,'end in seat'),
                        (-14.1,-33.,60.,False,'seat side gap'),(14.1,-33.,60.,False,'seat side gap')]:
                    point=(station+dx, side*(X.TRACK_Y+local_y), z)
                    inside=bool(X.one(xf).Solids()[0].isInside(point,1e-6))
                    arm_points.append(dict(point_mm=point,feature=what,expected_inside=expected,inside=inside))
                assert all(r['inside']==r['expected_inside'] for r in arm_points),arm_points
                return dict(side=tag, station_x_mm=station,
                            screw_x_mm=[station-9.5, station+9.5],
                            face_y_mm=side*(X.TRACK_Y-32.5), seat_depth_mm=1.5,
                            axial_contact_area_mm2=round(axial, 5),
                            expected_contact_area_mm2=28*21-2*math.pi*2.25**2,
                            nominal_lower_bearing_area_mm2=round(bearing, 5),
                            expected_lower_bearing_area_mm2=support['expected_probe_area_mm2'],
                            contact_limit_lower_bearing_area_mm2=support['contact_limit_area_mm2'],
                            retained_motor_relief_bearing_contract=support,
                            remaining_plate_mm=8.5, missing_plain_hole_wall_mm3=missing,
                            arm_material_probes=arm_points,
                            measurement='Actual STEP contact from a 0.01 mm axial/downward probe; '
                                        '8.5 mm full rectangular wall floor behind the arm end independently reconstructed with only two circular bores.')
            interfaces.append(run(f'interface_{tag}{i}', measure))

    assert all(abs(r['axial_contact_area_mm2']-r['expected_contact_area_mm2']) < .2 and
               abs(r['nominal_lower_bearing_area_mm2']-r['expected_lower_bearing_area_mm2']) < .2 and
               abs(r['missing_plain_hole_wall_mm3']) < 1e-4 for r in interfaces), interfaces

    print('Vertical frame lowering into both prepared tracks; lateral fitting is unsuitable', flush=True)
    removed_for_fitting = {n for n in every if n.startswith(('L_', 'R_')) and
                           (n.endswith(('J902_sprocket', 'flange_coupling_32', 'J903_journal_plug',
                                        'sprocket_screw_M3x50')) or
                            '_hub_screw_' in n or '_hub_set_screw_' in n)}
    fit_fixed = {n: d for n, d in no_chain.items() if n.startswith(('L_', 'R_')) and
                 n not in removed_for_fitting}
    assembly = []
    for lift in (80., 30., 10., 2., .3, 0.):
        def fitting():
            return dict(route='Bare X101 lowers vertically into both aligned track seats',
                        frame_lift_mm=lift,
                        **intersections(fit_fixed, {'moving_X101': dict(
                            shape=xf.translate((0, 0, lift)), group='frame_fitting')}))
        assembly.append(run(f'vertical_fit_{lift}', fitting))
    def continuous_fitting():
        members, evidence = vertical_frame_sweep(xf, fit_fixed)
        return dict(route='Complete continuous 80 mm vertical frame lowering',
                    stage='Rollers and axles, motor, housing and nominal idler fitted to both aligned tracks. '
                          'Rear sprockets/hubs/journals, chains, joint fasteners and upper assembly absent.',
                    sweep_evidence=evidence, **intersections(fit_fixed, members))
    assembly.append(run('continuous_vertical_fitting', continuous_fitting))
    critical.extend(assembly)
    rejected_lateral = []
    for side, tag in ((1, 'L'), (-1, 'R')):
        def lateral_diagnostic():
            moved = {n: {**d, 'shape': d['shape'].translate((0, side*10., 0))}
                     for n, d in fit_fixed.items() if n.startswith(tag+'_')}
            return dict(side=tag, lateral_gap_mm=10., accepted_route=False,
                        **intersections({'X101_X_frame': dict(shape=xf, group='frame')}, moved))
        diagnostic = run(f'rejected_lateral_fit_{tag}', lateral_diagnostic)
        hit_parts = {h[k] for h in diagnostic['hits'] for k in ('a', 'b')}
        assert {f'{tag}_JGY370_motor_can', f'{tag}_J909_housing'} <= hit_parts
        rejected_lateral.append(diagnostic)
    frame_bounds = X.one(xf).BoundingBox()
    cover_bounds = X.one(inst['X102_belly_cover']['shape']).BoundingBox()
    ring_bounds = X.one(inst['RU66_outer_ring']['shape']).BoundingBox()
    axial_assembly = dict(frame_min_z_mm=frame_bounds.zmin, frame_max_z_mm=frame_bounds.zmax,
                          cover_max_z_mm=cover_bounds.zmax, ring_min_z_mm=ring_bounds.zmin,
                          cover_lowering_clear=cover_bounds.zmax <= frame_bounds.zmin+1e-6,
                          bearing_lowering_clear=ring_bounds.zmin >= frame_bounds.zmax-1e-6,
                          method='Installed interfaces checked statically. Translation away from these '
                                 'separating horizontal planes cannot create a frame collision.')
    print('Central bearing-seat and belly-cover screw keys', flush=True)
    seat_z = X.TURNTABLE_Z - .4 + .05
    central_tools = dict(
        seat_screw_key=[run(f'seat_screw_key_{i}', lambda a=a: dict(angle_deg=a, **V.tool_check(
            every, X.zcyl(1.6, seat_z, seat_z+40, *X.polar(X.RU66['outer_pcd']/2, a)))))
            for i, a in enumerate(X.OUTER_ANG)],
        cover_screw_key=[run(f'cover_screw_key_{i}', lambda a=a: dict(angle_deg=a, **V.tool_check(
            every, X.zcyl(1.25, X.COVER_Z[0]-30, X.COVER_Z[0]-.05, *X.polar(X.COVER_BOSS_R, a)))))
            for i, a in enumerate(X.COVER_BOSS_ANG)])
    for rows in central_tools.values():
        critical.extend(rows)

    print('External fasteners, L-key strokes and socket holding before sprocket/chain', flush=True)
    screws, screw_sweeps, keys, key_strokes, nuts, nut_sweeps, nut_sockets, socket_sweeps = [], [], [], [], [], [], [], []
    for side, tag in ((1, 'L'), (-1, 'R')):
        # Roller wheels and their long axles are already installed. The rear
        # sprocket/hub and track chain are left off for nut/socket access.
        removed = {n for n in every if n.startswith(tag+'_') and
                   (n.endswith(('J902_sprocket', 'flange_coupling_32', 'J903_journal_plug', 'sprocket_screw_M3x50')) or
                    '_hub_screw_' in n or '_hub_set_screw_' in n)}
        nut_stage = {n: d for n, d in no_chain.items() if n not in removed}
        for i, j, x, z in M.bolt_centres():
            ident = f'{tag}{i}{j}'
            def fastener():
                stack = X.mount_stack(x, z)
                sn = next(n for n in stack if n.startswith('screw_'))
                front = stack['washer']
                fixed = {n: d for n, d in every.items() if n not in
                         (f'mount_{sn}_{ident}', f'mount_washer_{ident}')}
                bolt = stack[sn].union(front)
                sg = X.key_side(x)
                insertion = [dict(bolt=ident, withdrawal_mm=gap, side_offset_mm=off, lift_mm=lift,
                                  **V.tool_check(fixed, V.vehicle(bolt.translate((sg*off, -gap, lift)), side)))
                             for gap, off, lift in ((24.25, 10., 30.), (24.25, 10., 10.), (24.25, 10., 0.),
                                                    (24.25, 5., 0.), (24.25, 0., 0.), (15., 0., 0.),
                                                    (8., 0., 0.), (2., 0., 0.), (0., 0., 0.))]
                side_entry, advance = screw_entry_envelopes(x,z)
                continuous_entry = [dict(bolt=ident, stage=stage,
                                          **V.tool_check(fixed,V.vehicle(envelope,side)))
                                    for stage,envelope in (('30 mm drop beside the arm, then 10 mm sideways into the head slot, '
                                                            'tip .05 mm short of the slot end', side_entry),
                                                           ('24.25 mm axial insertion into plain bores',advance))]
                key = X.mount_key(x, z)
                paths = [dict(bolt=ident, withdrawal_mm=-dy, side_offset_mm=dx,
                              **V.tool_check(every, V.vehicle(key.translate((sg*dx, dy, 0)), side)))
                         for dy, dx in ((-3, 15), (-3, 6), (-3, 0), (-1.5, 0), (0, 0))]
                stroke = dict(bolt=ident, handle_angle_range_deg=list(key_stroke_angles(x)),
                              direction='Handle out of the side slot, 30 degrees below to 30 degrees above horizontal.',
                              withdrawal_range_mm=[0., 3.],
                              **V.tool_check(every, V.vehicle(key_stroke_envelope(x, z), side)))
                nut_fixed = {n: d for n, d in nut_stage.items() if n not in
                             (f'mount_nut_M4_{ident}', f'mount_rear_washer_{ident}')}
                pair = stack['nut_M4'].union(stack['rear_washer'])
                loading = [dict(bolt=ident, offset_toward_track_centre_mm=dy,
                                **V.tool_check(nut_fixed, V.vehicle(pair.translate((0, dy, 0)), side)))
                           for dy in (20., 12., 6., 2., 0.)]
                # The nut and washer slide axially over the threaded screw.
                sweep = tp.yring(4.5, 2.0, -24, 0, x, z)
                swept = dict(bolt=ident, travel_mm=20,
                             envelope='Complete radius-4.5 nut/washer sweep, central screw clearance retained.',
                             **V.tool_check(nut_fixed, V.vehicle(sweep, side)))
                socket = nut_socket_envelope(x, z)
                sockets = [dict(bolt=ident, withdrawal_mm=dy,
                                stage='Rollers, axles, motor, housing and nominal idler fitted; rear sprocket/hub, chain and upper absent.',
                                **V.tool_check(nut_stage, V.vehicle(socket.translate((0, dy, 0)), side)))
                           for dy in (0., 2., 6., 12.)]
                socket_continuous = [dict(bolt=ident,stage=label,
                                              **V.tool_check(nut_stage,V.vehicle(envelope,side)))
                                     for label,envelope in zip(('80 mm descent with socket withdrawn12mm',
                                                                'continuous0..12mm axial socket movement'),
                                                               socket_route_envelopes(x,z))]
                # Front key and back holding socket can coexist.
                coexist = V.volume(V.vehicle(socket, side).intersect(V.vehicle(key_stroke_envelope(x, z), side)))
                assert coexist < .01
                return dict(screws=insertion, screw_sweeps=continuous_entry, keys=paths, key_stroke=stroke,
                            nuts=loading, sweep=swept, sockets=sockets, socket_sweeps=socket_continuous,
                            simultaneous_tool_overlap_mm3=coexist)
            rows = run(f'fastener_{ident}', fastener)
            screws.extend(rows['screws']); screw_sweeps.extend(rows['screw_sweeps']); keys.extend(rows['keys']); nuts.extend(rows['nuts'])
            key_strokes.append(rows['key_stroke']); nut_sweeps.append(rows['sweep'])
            nut_sockets.extend(rows['sockets']); socket_sweeps.extend(rows['socket_sweeps'])
            failures = [r for r in rows['screws']+rows['screw_sweeps']+rows['keys']+rows['nuts']+rows['sockets']+rows['socket_sweeps']+
                        [rows['sweep'], rows['key_stroke']] if r['hits']]
            print(f'  {ident}: {len(failures)} insertion/access failures', flush=True)
            if failures:
                print(json.dumps(failures), flush=True)
    critical += screws+screw_sweeps+keys+key_strokes+nuts+nut_sweeps+nut_sockets+socket_sweeps

    print('Support-roller service on detached tracks', flush=True)
    detached = []
    for side, tag in ((1, 'L'), (-1, 'R')):
        fixed = {n: d for n, d in every.items() if n.startswith(tag+'_') or n.startswith((f'mount_nut_M4_{tag}', f'mount_rear_washer_{tag}'))}
        for x in D.CARRIER_X:
            for label, radius, length in (('driver', 1.75, 100.), ('bolt', 3.6, 70.)):
                def service():
                    tool = V.vehicle(tp.ycyl(radius, -34-length, -34.05, x, D.CARRIER_Z), side)
                    return dict(side=tag, roller_x_mm=x, tool=label, **V.tool_check(fixed, tool))
                detached.append(run(f'detached_{tag}_{x}_{label}', service))
    critical += detached

    print('Rear sprocket/hub installation after joint tightening', flush=True)
    wheel_installation, sprocket_sweeps, sprocket_containment = [], [], []
    for side, tag in ((1, 'L'), (-1, 'R')):
        # Track sprocket and idler enter from their respective open ends.
        spr = {n: d for n, d in every.items() if n.startswith(tag+'_') and
               (n.endswith(('J902_sprocket', 'flange_coupling_32')) or
                '_hub_screw_' in n or '_hub_set_screw_' in n)}
        omitted = set(spr) | {f'{tag}_J903_journal_plug', f'{tag}_sprocket_screw_M3x50'}
        stage = {n: d for n, d in no_chain.items() if n not in omitted}
        def continuous_sprocket():
            seed,radial,base,axial=sprocket_route_envelopes()
            radial_seed=V.vehicle(seed,side)
            base=V.vehicle(base,side)
            containment=[]
            for n,d in spr.items():
                first=d['shape'].translate((0,side*9.6,0))
                containment.append(dict(component=n,
                    radial_seed_outside_mm3=V.volume(first.cut(radial_seed)),
                    axial_base_outside_mm3=V.volume(d['shape'].cut(base))))
            assert all(r['radial_seed_outside_mm3']<1e-5 and r['axial_base_outside_mm3']<1e-5
                       for r in containment),containment
            checks=[dict(side=tag,stage=label,**intersections(stage,{
                'moving_sprocket_sweep':dict(shape=V.vehicle(envelope,side),group='assembly')}))
                for label,envelope in (('continuous rear entry X -150..0 at Y+9.6',radial),
                                       ('continuous axial seating Y+9.6..0',axial))]
            return dict(containment=containment,checks=checks,
                        explanation='Measured STEP containment in conservative cylinder bands/capsule. '
                                    'The radial sweep is separated from new fasteners by at least5.39mm in Y. '
                                    'The D-profile shaft clearance below its fixed tip remains empty under positive-Y translation; '
                                    'the envelope retains material above the flat to include the coupling set-screw tip.')
        swept=run(f'sprocket_sweeps_{tag}',continuous_sprocket)
        sprocket_sweeps.extend(swept['checks'])
        sprocket_containment.append(dict(side=tag, containment=swept['containment'],
                                         explanation=swept['explanation']))
        for gap in (150., 110., 80., 60., 40., 25., 12., 5., 0.):
            def sprocket_entry():
                moving = {n: {**d, 'shape': d['shape'].translate((-gap, side*9.6, 0))}
                          for n, d in spr.items()}
                return dict(side=tag, assembly='sprocket', longitudinal_offset_mm=-gap,
                            lateral_offset_mm=9.6, **intersections(stage, moving))
            wheel_installation.append(run(f'sprocket_entry_{tag}_{gap}', sprocket_entry))
        for gap in (9.6, 7., 4., 2., 0.):
            def sprocket_seating():
                moving = {n: {**d, 'shape': d['shape'].translate((0, side*gap, 0))}
                          for n, d in spr.items()}
                return dict(side=tag, assembly='sprocket', lateral_offset_mm=gap,
                            **intersections(stage, moving))
            wheel_installation.append(run(f'sprocket_seat_{tag}_{gap}', sprocket_seating))
        slide = {n: d for n, d in every.items() if d['group'] in (f'{tag}_idler', f'{tag}_idler_slide')}
        for gap in (60., 25., 8., 0.):
            def idler_entry():
                moving = {n: {**d, 'shape': d['shape'].translate((gap, 0, 0))} for n, d in slide.items()}
                return dict(side=tag, assembly='idler_yoke', longitudinal_offset_mm=gap,
                            **intersections({n:d for n,d in stage.items() if n not in slide and d['group'] != f'{tag}_spring'}, moving))
            wheel_installation.append(run(f'idler_entry_{tag}_{gap}', idler_entry))
    critical += wheel_installation+sprocket_sweeps

    print('New connection hardware through full idler recoil', flush=True)
    recoil_cases = []
    for side, tag in ((1, 'L'), (-1, 'R')):
        slide = {n: d for n, d in every.items() if d['group'] in (f'{tag}_idler', f'{tag}_idler_slide')}
        for k in range(13):
            recoil = D.RECOIL*k/12
            def posed_recoil():
                moving = {n: {**d, 'shape': d['shape'].translate((-recoil, 0, 0))} for n, d in slide.items()}
                return dict(side=tag, recoil_mm=recoil, **intersections(primary, moving))
            recoil_cases.append(run(f'recoil_{tag}_{k}', posed_recoil))
    critical += recoil_cases

    print('New connection through twelve chain phases per side', flush=True)
    from build_j9 import phase_pins
    shoe = cq.Workplane(obj=step_part(P.ROOT/'step/J910_track_shoe_70.step'))
    phases = []
    for k in range(12):
        if all(f'phase_{tag}_{k}' in checkpoint.results for tag in ('L', 'R')):
            phases.extend(checkpoint.results[f'phase_{tag}_{k}'] for tag in ('L', 'R'))
            continue
        chain = P.chain({'J910_track_shoe_70': dict(shape=shoe)}, phase_pins(k/12))
        for side, tag in ((1, 'L'), (-1, 'R')):
            def phase_case():
                moving = {f'{tag}_{n}': dict(shape=V.vehicle(shape, side), group='track')
                          for n, (shape, _) in chain.items()}
                return dict(side=tag, fraction_of_pitch=k/12, **intersections(primary, moving))
            phases.append(run(f'phase_{tag}_{k}', phase_case))
        print(f'  phase {k}/12: {sum(len(r["hits"]) for r in phases[-2:])} hits', flush=True)
    critical += phases

    print('Delivered upper assembly and bound ARM60 reference through twenty-four swing angles', flush=True)
    upper, T = upper_parts()
    service_routes = run('track_service_routes', lambda: track_service_routes(every, fit_fixed, upper))
    critical += service_routes
    service_upper_tools = []
    for side, tag in ((1, 'L'), (-1, 'R')):
        for i, j, x, z in M.bolt_centres():
            def service_tools():
                envelopes = list(zip(('socket_descent', 'socket_engagement'), socket_route_envelopes(x, z)))
                envelopes += list(zip(('screw_side_entry', 'screw_axial_entry'), screw_entry_envelopes(x, z)))
                return [dict(bolt=f'{tag}{i}{j}', upper_angle_deg=0., envelope=label,
                             **V.tool_check(upper, V.vehicle(shape, side))) for label, shape in envelopes]
            service_upper_tools += run(f'service_upper_tools_{tag}{i}{j}', service_tools)
    critical += service_upper_tools
    upper_changed = {**primary, **{n: d for n, d in every.items()
                                  if n.endswith(('J901_H_frame', 'J909_housing', 'insert_M3_0',
                                                 'insert_M3_2', 'housing_screw_M3x8_0', 'housing_screw_M3x8_2'))}}
    moving_groups = {'upper', 'pinion', 'rotor', 'arm'}
    swing = []
    for angle in range(0, 360, 15):
        def swing_case():
            posed = {}
            for n, d in upper.items():
                if angle and d['group'] not in moving_groups:
                    continue
                shape = d['shape']
                if d['group'] == 'pinion':
                    shape = shape.rotate((T.PXS, 0, 0), (T.PXS, 0, 1), T.RATIO*angle)
                if d['group'] in moving_groups:
                    shape = shape.rotate((0, 0, 0), (0, 0, 1), angle)
                posed[n] = {**d, 'shape': shape}
            return dict(angle_deg=angle, **intersections(upper_changed, posed))
        swing.append(run(f'swing_{angle}', swing_case))
        print(f'  swing {angle}: {len(swing[-1]["hits"])} hits', flush=True)
    critical += swing
    upper_key = []
    for side, tag in ((1, 'L'), (-1, 'R')):
        for i, j, x, z in M.bolt_centres():
            def upper_access():
                return dict(bolt=f'{tag}{i}{j}', upper_angle_deg=0,
                            handle_angle_range_deg=list(key_stroke_angles(x)),
                            **V.tool_check(upper, V.vehicle(key_stroke_envelope(x, z), side)))
            upper_key.append(run(f'upper_key_{tag}{i}{j}', upper_access))
    # These tool clearances are required for the documented parked-upper
    # service route, although initial fitting precedes upper installation.
    critical += upper_key

    print('Final nominal clearances and solid validity', flush=True)
    def clearance_case():
        result = dict(inner_ring=closest_disjoint(xf, {'RU66_inner_ring': inst['RU66_inner_ring']}),
                      cable_L=closest_disjoint(xf, {'cable': dict(shape=X.cable_route(1), group='cable')}),
                      cable_R=closest_disjoint(xf, {'cable': dict(shape=X.cable_route(-1), group='cable')}))
        for tag in ('L', 'R'):
            result[f'frame_to_{tag}_housing'] = closest_disjoint(xf, {f'{tag}_J909_housing': inst[f'{tag}_J909_housing']})
            motor = {n: d for n, d in every.items() if n.startswith(f'{tag}_JGY370_') and 'shaft' not in n}
            result[f'frame_to_{tag}_motor'] = closest_disjoint(xf, motor)
        for side, tag in ((1, 'L'), (-1, 'R')):
            hardware = V.compound([d['shape'] for n, d in every.items()
                                   if n.startswith('mount_') and f'_{tag}' in n])
            wheels = {n: d for n, d in every.items() if n.startswith(tag+'_') and
                      n.endswith(('J902_sprocket', 'J906_idler_wheel'))}
            wheels.update({n: d for n, d in every.items() if n.startswith(f'{tag}_J904_roller_')})
            result[f'hardware_to_{tag}_wheels'] = closest_disjoint(hardware, wheels)
            idler = every[f'{tag}_J906_idler_wheel']
            result[f'hardware_to_{tag}_recoiled_idler'] = closest_disjoint(
                hardware, {'idler_full_recoil': {**idler, 'shape': idler['shape'].translate((-D.RECOIL, 0, 0))}})
        return result
    clearances = run('clearances', clearance_case)
    solids = {n: dict(valid=bool(X.one(inst[n]['shape']).isValid()),
                      solids=len(X.one(inst[n]['shape']).Solids()), volume_mm3=V.volume(inst[n]['shape']))
              for n in ('X101_X_frame', 'L_J901_H_frame', 'R_J901_H_frame', 'L_J909_housing', 'R_J909_housing')}
    st = X.mount_stack(54, 67.75)
    bolt_box = X.one(st['screw_M4x25']).BoundingBox()
    nut_box = X.one(st['nut_M4']).BoundingBox()
    fastener_spec = dict(screw_entry='With its washer, lower the screw beside the arm, slide it sideways into the head slot '
                                     '(tip just short of the slot end), then advance into the plain bore.', count=8, screw='M4 x25 ISO4762', front_washer_mm=.8, rear_washer_mm=.8,
                         nut_engagement_mm=min(bolt_box.ymax, nut_box.ymax)-nut_box.ymin,
                         tip_y_mm=bolt_box.ymax, tip_projection_past_nut_mm=bolt_box.ymax-nut_box.ymax,
                         nut_loading='External nuts and washers. Fit and tighten with a 7 mm socket before '
                                     'installing the rear sprocket/hub and chain. Rollers and axles are already fitted. No nut/head recesses in the joint.',
                         tool='3 mm L-key, approximately 20 mm short leg and 80 mm handle. '
                              'Handle out of the side slot: swing from 30 degrees below to 30 degrees above horizontal, withdraw 3 mm and reset. '
                              'Hold the external nut with a 7 mm socket from inside the track, with rollers fitted and the rear sprocket/chain absent.',
                         socket_envelope='11.2 mm outer diameter and drive/handle/junction envelope, '
                                         '7.1 mm AF cavity and 60 mm upright holding handle. '
                                         'Verify actual chosen tool dimensions.')
    spring = dict(guide_bore_mm=D.SPRING_POCKET['bore_d'],
                  guide_outer_mm=D.SPRING_POCKET['outer_d'],
                  piston_mm=D.SPRING_POCKET['piston_d'], recess_mm=D.SPRING_POCKET['recess'],
                  fitted_length_mm=D.SPRING_SET, recoil_mm=D.RECOIL,
                  yoke_step_sha256=sha(P.ROOT/'step/J908_U_yoke.step'),
                  spring_guide_report=rel(P.ROOT/'spring_guide_validation.json'))
    spring['preserved'] = (spring['guide_bore_mm'] == 16.4 and spring['guide_outer_mm'] == 21.2 and
                           spring['piston_mm'] == 15.6 and spring['recess_mm'] == 8.0 and
                           spring['fitted_length_mm'] == 25.8 and spring['recoil_mm'] == 4.2 and
                           spring['yoke_step_sha256'] ==
                           '3ab7207adb42dc2eb1b08c4dc9a470fafd4a43527277ddad2c02f078ea9db60d')
    interface_ok = all(abs(r['axial_contact_area_mm2']-r['expected_contact_area_mm2']) < .2 and
                       abs(r['nominal_lower_bearing_area_mm2']-r['expected_lower_bearing_area_mm2']) < .2 and
                       abs(r['missing_plain_hole_wall_mm3']) < 1e-4 for r in interfaces)
    passed = all(not row['hits'] for row in critical) and interface_ok
    passed &= all(row['valid'] and row['solids'] == 1 for row in solids.values())
    passed &= axial_assembly['cover_lowering_clear'] and axial_assembly['bearing_lowering_clear']
    passed &= abs(fastener_spec['nut_engagement_mm']-3.2) < 1e-5
    passed &= abs(fastener_spec['tip_projection_past_nut_mm']-1.2) < 1e-5
    passed &= clearances['inner_ring']['mm'] > .5
    passed &= all(r['mm'] > .2 for k, r in clearances.items() if k != 'inner_ring')
    passed &= spring['preserved']
    verify_proofs(allow_pending_track=args.geometry_preflight)
    assert current_bindings() == initial, 'Validation inputs changed; rerun against frozen files'
    report = dict(revision='F', geometry_source='Current individual STEP interfaces and checked current STEP assemblies; '
                  'the original ARM60 STEP supplies the arm/actuators omitted from the delivered turntable STEP.',
                  **initial, central_tools=central_tools, interface_contract=SPEC,
                  interfaces=interfaces, static=static, internal_joint=internal,
                  track_fitting=assembly,
                  track_service_routes=service_routes,
                  track_service_tools_with_parked_upper=service_upper_tools,
                  rejected_lateral_track_fitting=dict(
                      accepted=False, diagnostics=rejected_lateral,
                      reason='Straight lateral fitting causes real motor-can and housing interference. '
                             'It is not an assembly route. The accepted vertical route is independently '
                             'checked over its entire continuous motion, with no collision waiver.'),
                  central_axial_assembly=axial_assembly,
                  fasteners=fastener_spec, screw_insertion=screws, continuous_screw_entry=screw_sweeps, L_key_access=keys,
                  L_key_continuous_strokes=key_strokes,
                  nut_insertion_before_sprocket_and_chain=nuts, nut_continuous_sweeps=nut_sweeps,
                  external_nut_socket_access=nut_sockets, continuous_socket_routes=socket_sweeps, detached_support_roller_service=detached,
                  sprocket_and_optional_idler_installation_after_joint_tightening=wheel_installation,
                  continuous_sprocket_routes=sprocket_sweeps,
                  sprocket_sweep_containment_proofs=sprocket_containment,
                  recoil=recoil_cases, track_phases=phases,
                  swing=swing, upper_component_count=len(upper),
                  arm_reference=dict(source=rel(REPO/'excavator_arm_60mm/step/excavator_arm_assembly.step'),
                                     placement_mm=[T.R3.ARM_X0, 0, T.R3.TOPZ],
                                     rest_solids=sum(n.startswith('ARM60_rest_') for n in upper),
                                     delivered_turntable_step_contains='Fixed ARM60 base only; arm/actuators are reference geometry.'),
                  upper_key_at_zero_deg=upper_key,
                  upper_key_clear_at_zero_deg=all(not r['hits'] for r in upper_key),
                  clearances_mm=clearances, solids=solids,
                  accepted_spring=spring,
                  overlap_tolerance_mm3=.01,
                  numerical_case_cache=dict(fingerprint=checkpoint.fingerprint,
                                            case_count=len(checkpoint.results), reused_cases=checkpoint.reused,
                                            binding='Exact source, exported CAD, assembly and scene bytes. '
                                                    'Acceptance proofs are independently verified before publication.'),
                  scope='Exact nominal solid interference at the listed poses, with a complete continuous '
                        'vertical frame-fitting sweep, continuous nut insertion '
                        'and conservative60-degree L-key strokes, complete screw/socket insertion envelopes and continuous sprocket assembly sweeps. '
                        'Track internals are covered by the fresh J9 validation; central tools are checked here. '
                        'No physical fit, strength, torque, preload retention, fatigue or payload rating is established.',
                  elapsed_s=round(time.time()-started, 2), **{'pass': bool(passed)})
    if args.geometry_preflight:
        report.pop('pass')
        report.update(status='GEOMETRY PREFLIGHT ONLY; FINAL VALIDATION PENDING',
                      geometry_cases_pass=bool(passed),
                      required_final_proof=rel(P.ROOT/'revf_track_validation.json'),
                      final_pass_published=False)
    path = ROOT/('arc_seat_mount_preflight.json' if args.geometry_preflight else 'arc_seat_mount_validation.json')
    path.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(geometry_cases_pass=bool(passed),
                          final_pass_published=bool(passed and not args.geometry_preflight),
                          interfaces=interfaces, fasteners=fastener_spec,
                          clearances=clearances, upper_key_clear_at_zero_deg=report['upper_key_clear_at_zero_deg'],
                          elapsed_s=report['elapsed_s']), indent=2), flush=True)
    if not passed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

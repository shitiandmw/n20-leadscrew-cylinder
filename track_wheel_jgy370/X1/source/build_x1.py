"""Export X1 (STEP, print-oriented STL, coloured chassis assembly) and run the geometry checks.

Run with the CAD interpreter from this folder:  python build_x1.py
Writes ../step, ../stl, ../validation.json and x1_scene.json.gz (viewer data).
"""
import json, gzip, time
import cadquery as cq
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
import x1_parts as X
from x1_parts import P9, D9, tp
import tw_checks as checks
import build_track_wheel as export

ROOT = X.ROOT
PETG_G_MM3, STEEL_G_MM3 = 1.27e-3, 7.85e-3
PRINT = {   # axis, angle, how the part lies on the bed
    'X101_X_frame': ((1, 0, 0), 180, 'upside down: the flat top (slewing-ring seat) on the bed; no supports'),
    'X102_belly_cover': ((1, 0, 0), 0, 'flat, countersinks up'),
    'J901_H_frame_right': ((1, 0, 0), 90, 'mirror of J9 J901: outer wall face on the bed; support under the inner wall overhangs'),
    'J909_housing_right': ((1, 0, 0), 90, 'mirror of J9 J909: skirt inner face on the bed; supports inside the motor pod only'),
}


def dist(a, b):
    d = BRepExtrema_DistShapeShape(X.one(a).wrapped, X.one(b).wrapped); d.Perform()
    return round(d.Value(), 3)


def compound(inst, names):
    return cq.Workplane(obj=cq.Compound.makeCompound([X.one(inst[n]['shape']) for n in names]))


def against(fixed, moving):
    return checks.interference({**fixed, **moving}, skip=lambda a, b: (a in moving) == (b in moving))


def moved(inst, names, dx=0., dy=0., dz=0.):
    return {n: {**inst[n], 'shape': inst[n]['shape'].translate((dx, dy, dz))} for n in names}


def tool(shape):
    return {'tool': dict(shape=shape, group='tool')}


def export_parts(prt):
    rows = []
    for n, d in prt.items():
        s = d['shape']
        assert X.one(s).isValid() and len(s.solids().vals()) == 1, n
        print('Export', n, flush=True)
        export.export_step(s, ROOT / 'step' / f'{n}.step')
        axis, deg, how = PRINT[n]
        tm = export.export_stl(export.to_bed(s, axis, deg), ROOT / 'stl' / f'{n}.stl')
        bed = tm.area_faces[(tm.face_normals[:, 2] < -.999) & (abs(tm.triangles_center[:, 2] - tm.bounds[0][2]) < 1e-3)].sum()
        vol = X.one(s).Volume()
        rows.append(dict(name=n, quantity=d['quantity'], material=d['material'], note=d['note'], print_orientation=how,
                         volume_mm3=round(vol, 1), solid_PETG_mass_g=round(vol*PETG_G_MM3, 1), bed_contact_mm2=round(bed),
                         print_bounds_mm=[round(v, 1) for v in tm.extents.tolist()], stl_watertight=True,
                         stl_components=len(tm.split()), step_roundtrip=True, solids=1))
    return rows


def printed_parts(prt9):
    prt = X.chassis_parts()
    for n9, n in (('J901_H_frame', 'J901_H_frame_right'), ('J909_housing', 'J909_housing_right')):
        d = prt9[n9]
        prt[n] = dict(shape=X.mirror_y(d['shape']), quantity=1, material=d['material'],
                      note=f'Mirror image of J9 {n9} for the right track. ' + d['note'])
    return prt


def save_assembly(inst, path, name):
    a = cq.Assembly(name=name)
    for n, d in inst.items():
        a.add(d['shape'], name=n, color=cq.Color(*d['color']))
    a.export(str(path))
    rt = cq.importers.importStep(str(path))
    assert X.one(rt).isValid()
    return len(rt.solids().vals())


def side_names(inst, side, groups=None):
    tag = 'L_' if side > 0 else 'R_'
    return [n for n, d in inst.items() if n.startswith(tag) and (groups is None or d['j9group'] in groups)]


def checks_all(inst):
    t0 = time.time()
    x1 = {n: d for n, d in inst.items() if not n.startswith(('L_', 'R_')) and d['group'] != 'reserve'}
    for side in (1, -1):
        x1[f'cable_route_{"L" if side > 0 else "R"}'] = dict(shape=X.cable_route(side), group='cable', color=(.1, .1, .1))
    tracks = {n: d for n, d in inst.items() if n.startswith(('L_', 'R_'))}
    out = {}
    print('Static interference', flush=True)
    # J9's own pairs were checked in J9 (the right track is its mirror); here every X1 part meets everything.
    out['static'] = checks.interference({**x1, **tracks}, skip=lambda a, b: a in tracks and b in tracks)
    print('Assembly paths', flush=True)
    # Tracks are offered up from the side before their three chassis screws go in.
    xfixed = {n: d for n, d in x1.items() if not n.startswith(('cable_route', 'chassis_screw'))}
    seq = {}
    for side in (1, -1):
        names = side_names(inst, side)
        seq[f'track_slide_on_{"L" if side > 0 else "R"}'] = [dict(dy=dy, **against(xfixed, moved(inst, names, 0, side*dy)))
                                                              for dy in (40, 20, 10, 4, 1)]
    ring = ['RU66_outer_ring', 'RU66_inner_ring']
    rest = {n: d for n, d in {**x1, **tracks}.items() if n not in ring and not n.startswith(('cable_route', 'seat_screw', 'cover_screw'))}
    seq['bearing_lowering'] = [dict(dz=dz, **against(rest, moved(inst, ring, 0, 0, dz))) for dz in (40, 15, 5, 1)]
    seq['cover_from_below'] = [dict(dz=dz, **against({n: d for n, d in rest.items() if n != 'X102_belly_cover'},
                                                     moved(inst, ['X102_belly_cover'], 0, 0, -dz))) for dz in (20, 5, 1)]
    print('Tool access', flush=True)
    every = {**x1, **tracks}
    nochain = {n: d for n, d in every.items() if d['group'] not in ('L_track', 'R_track')}
    t = {}
    head_r = X.M4_HEAD['h']
    for side in (1, -1):
        tag = 'L' if side > 0 else 'R'
        y_head = side*(X.RAIL_IN_Y - head_r)                     # top of the chassis screw heads
        t[f'chassis_screw_key_{tag}'] = [against(every, tool(ycyl_span(1.6, y_head - side*35, y_head - side*.05, x, X.CHASSIS_Z)))
                                         for x in D9.CHASSIS_X]
        t[f'chassis_screw_insertion_{tag}'] = [against({n: d for n, d in every.items() if not n.startswith('chassis_screw')},
                                                       tool(ycyl_span(3.6, y_head - side*X.CHASSIS_SCREW_L, y_head, x, X.CHASSIS_Z))) for x in D9.CHASSIS_X]
        # J9 paths, now with the X-frame in place (vehicle frame; module Y -> side*(TRACK_Y + y)).
        vy = lambda y: side*(X.TRACK_Y + y)
        y_hs = vy(P9.SKIRT_Y[0] - P9.M3_BUTTON['h'])             # top of the housing screw heads
        t[f'housing_screw_key_{tag}'] = [against(nochain, tool(ycyl_span(1.6, y_hs - side*40, y_hs - side*.05, x, z))) for x, z in P9.HOUSING_SCREWS]
        y_rb = vy(-D9.WALL_OUT - P9.M4_HEAD['h'])                # top of the roller bolt heads
        road = [(x, z) for x, z, g in P9.ROLLERS if g.startswith('road')]
        sup = [(x, z) for x, z, g in P9.ROLLERS if g.startswith('support')]
        t[f'road_roller_bolt_withdrawal_{tag}'] = [against(nochain, tool(ycyl_span(3.6, y_rb - side*70, y_rb - side*.05, x, z))) for x, z in road]
        t[f'support_roller_bolt_key_{tag}'] = [against(nochain, tool(ycyl_span(1.6, y_rb - side*40, y_rb - side*.05, x, z))) for x, z in sup]
        t[f'support_roller_bolt_withdrawal_{tag}'] = [against(nochain, tool(ycyl_span(3.6, y_rb - side*70, y_rb - side*.05, x, z))) for x, z in sup]
    y0 = X.TURNTABLE_Z - .4 + .05
    t['seat_screw_key'] = [against(every, tool(X.zcyl(1.6, y0, y0 + 40, *X.polar(X.RU66['outer_pcd']/2, a)))) for a in X.OUTER_ANG]
    t['cover_screw_key'] = [against(every, tool(X.zcyl(1.25, X.COVER_Z[0] - 30, X.COVER_Z[0] - .05, *X.polar(X.COVER_BOSS_R, a))))
                            for a in X.COVER_BOSS_ANG]
    out['assembly'] = seq; out['tools'] = t
    print('Turntable reserve', flush=True)
    env = {'RESERVED_turntable_swing_envelope': inst['RESERVED_turntable_swing_envelope']}
    out['turntable_reserve'] = checks.interference({**env, **every}, skip=lambda a, b: (a in env) == (b in env))
    out['seconds'] = round(time.time() - t0, 1)
    return out


def ycyl_span(r, y0, y1, x, z):
    return tp.ycyl(r, *sorted([y0, y1]), x, z)


def clearances(inst):
    print('Clearances', flush=True)
    xf = inst['X101_X_frame']['shape']; env = inst['RESERVED_turntable_swing_envelope']['shape']
    c = {}
    for side, tag in ((1, 'L'), (-1, 'R')):
        chain = side_names(inst, side, ('track',))
        c[f'X-frame to track {tag} motor pod and skirt (J909)'] = dist(xf, inst[f'{tag}_J909_housing']['shape'])
        c[f'X-frame to track {tag} motor (gearbox, can, terminal space)'] = dist(xf, compound(inst, [f'{tag}_{n}' for n in
                                                    ('JGY370_gearbox', 'JGY370_motor_can', 'JGY370_terminal_space')]))
        c[f'X-frame to track {tag} chain and shoes'] = dist(xf, compound(inst, chain))
        c[f'turntable reserve to track {tag} chain (top of track)'] = dist(env, compound(inst, chain))
    c['turntable reserve to X-frame'] = dist(env, xf)
    c['turntable reserve to RU66 bolt heads (8 x M4 in the counterbores)'] = dist(env, compound(inst, [n for n in inst if n.startswith('seat_screw')]))
    c['RU66 inner ring to X-frame (relief)'] = dist(inst['RU66_inner_ring']['shape'], xf)
    c['RU66 outer ring to X-frame (seat, contact by design)'] = dist(inst['RU66_outer_ring']['shape'], xf)
    zmin = min(X.one(inst[n]['shape']).BoundingBox().zmin for n in ('X101_X_frame', 'X102_belly_cover'))
    c['ground clearance under the carbody (Cat 320 at 1:15: 31.3)'] = round(zmin, 3)
    for side, tag in ((1, 'L'), (-1, 'R')):
        c[f'cable route {tag} to X-frame (Ø5 path through the Ø10 hole)'] = dist(X.cable_route(side), xf)
    return c


def key_numbers(inst):
    chain = [X.one(inst[n]['shape']).BoundingBox() for n in inst if n.startswith(('L_', 'R_')) and inst[n]['j9group'] == 'track']
    xs = [b.xmin for b in chain] + [b.xmax for b in chain]; ys = [b.ymin for b in chain] + [b.ymax for b in chain]
    zt = max(b.zmax for b in chain)
    return dict(track_gauge=2*X.TRACK_Y, overall_width=round(max(ys) - min(ys), 1), track_length=round(max(xs) - min(xs), 1),
                sprocket_to_idler=round(D9.IDLER_X - D9.DRIVE_X, 1), shoe_width=D9.SHOE_W, track_top=round(zt, 1),
                ground_clearance=X.COVER_Z[0], seat_z=X.SEAT_Z, turntable_face_z=X.TURNTABLE_Z, reserve_radius=X.RESERVE_R,
                x_frame_width=round(2*X.BOSS_FACE_Y, 1), x_frame_length=round(X.RAIL_X[1] - X.RAIL_X[0], 1))


def write_scene(inst, keys):
    print('Viewer scene', flush=True)
    j9 = json.loads(gzip.decompress((X.ROOT.parent / 'J9/source/j9_scene.json.gz').read_bytes()))
    own = {n: d for n, d in inst.items() if not n.startswith(('L_', 'R_'))}
    # The viewer shows the swing reserve as a thin disc at the turntable face, so it does not hide the chassis.
    own['RESERVED_turntable_swing_envelope'] = {**own['RESERVED_turntable_swing_envelope'],
                                                'shape': X.zcyl(X.RESERVE_R, X.TURNTABLE_Z, X.TURNTABLE_Z + 3.0)}
    items = export.scene_items(own)
    for side in (1, -1):
        items.append(dict(name=f'reserved cable route ({"left" if side > 0 else "right"} motor leads)', color=[.78, .28, .18],
                          group='cable', kind='envelope', source=None, **export.mesh(X.cable_route(side))))
    payload = dict(module=j9['unit'], link=j9['link'], j9=j9['config'], chassis=items,
                   config=dict(revision='X1', track_y=X.TRACK_Y, key=keys))
    (X.HERE / 'x1_scene.json.gz').write_bytes(gzip.compress(json.dumps(payload, separators=(',', ':')).encode()))


def main():
    t0 = time.time()
    (ROOT / 'step').mkdir(exist_ok=True); (ROOT / 'stl').mkdir(exist_ok=True)
    print('J9 parts and track unit', flush=True)
    prt9 = P9.parts()
    inst9 = P9.unit(prt9, with_chain=True)
    rows = export_parts(printed_parts(prt9))
    inst = X.unit(inst9)
    keys = key_numbers(inst)
    print('Assembly STEP', flush=True)
    solids = save_assembly({n: d for n, d in inst.items() if d['group'] != 'reserve'}, ROOT / 'step/X1_crawler_chassis.step', 'X1_crawler_chassis')
    rep = checks_all(inst)
    clear = clearances(inst)
    write_scene(inst, keys)
    runs = [rep['static'], rep['turntable_reserve']] + [r for v in rep['assembly'].values() for r in v]
    tool_runs = {k: v for k, v in rep['tools'].items() if not k.startswith('support_roller_bolt_withdrawal')}
    runs += [r for v in tool_runs.values() for r in v]
    blocked = {k: [len(r['hits']) for r in v] for k, v in rep['tools'].items() if k.startswith('support_roller_bolt_withdrawal')}
    ok = all(not r['hits'] for r in runs) and clear['RU66 inner ring to X-frame (relief)'] > .5
    val = dict(revision='X1', reference=dict(machine='Caterpillar 320 (07H) technical specifications, p. 2 and p. 4',
                                             file='excavator_arm_60mm/references/cat320_specifications.pdf', values_mm=X.CAT320, scale=X.SCALE),
               slewing_ring=dict(model='THK RU66 cross-roller ring', source='THK catalogue A18-20/21 (track_wheel_jgy370/X1/references/thk_ru66/)', **X.RU66),
               turntable_interface=dict(swing_centre=[0, 0], outer_ring_to_x_frame='8 x M4 x 16 ISO 4762 from above into heat-set inserts, PCD 83',
                                        inner_ring_reserved_for_turntable='8 x M4 tapped through, PCD 45; turntable flange within Ø59 (ds max)',
                                        seat_z=X.SEAT_Z, turntable_face_z=X.TURNTABLE_Z, cable_passage_d=2*X.PASSAGE_R,
                                        relief='Ø75 x 2.5 under the inner ring: turntable screw tips may protrude up to 2 mm below it',
                                        swing_envelope=f'R {X.RESERVE_R} above Z {X.TURNTABLE_Z} (Cat 320 tail swing radius 2830 mm at 1:15)'),
               key_numbers=keys, parts=rows, assembly_solids=solids,
               static=rep['static'], turntable_reserve=rep['turntable_reserve'], assembly_paths=rep['assembly'], tool_access=rep['tools'],
               known_service_limits=dict(support_roller_bolt_withdrawal_hits=blocked,
                                         note='The X-frame legs cross the inboard withdrawal path of the two support-roller bolts on each side. '
                                              'To change a support roller, unbolt that track from the X-frame (3 screws) first. Their heads stay reachable with a key.'),
               clearances_mm=clear, pass_=ok,
               scope='Nominal CAD with exact solid intersections: static fit, track slide-on, bearing and cover fitting, tool access and the '
                     'reserved turntable envelope. J9 internals as validated in J9 (the right track is its mirror). Not a load, print-tolerance or powered test.',
               elapsed_s=round(time.time() - t0, 1))
    val['pass'] = val.pop('pass_')
    (ROOT / 'validation.json').write_text(json.dumps(val, indent=1, ensure_ascii=False) + '\n')
    print(json.dumps(dict(passed=ok, keys=keys, clearances=clear, static_pairs=rep['static']['pairs_tested'],
                          static_hits=rep['static']['hits'][:5], reserve_hits=rep['turntable_reserve']['hits'][:5],
                          tool_hits={k: [len(r['hits']) for r in v] for k, v in rep['tools'].items()},
                          assembly_hits={k: [len(r['hits']) for r in v] for k, v in rep['assembly'].items()},
                          elapsed=round(time.time() - t0, 1)), indent=1))


if __name__ == '__main__':
    main()

"""Export J9 (STEP, print-oriented STL, coloured assembly) and run the geometry checks.

Run with the CAD interpreter from this folder:  python build_j9.py
Writes ../step, ../stl, ../validation.json and j9_scene.json.gz (viewer data).
"""
import json, gzip, math, time
import numpy as np
import cadquery as cq
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
import j9_parts as P
from j9_parts import tp
import j9_design as D
import tw_checks as checks
import build_track_wheel as export

ROOT = P.ROOT
PETG_G_MM3 = 1.27e-3
KGF_CM = .0980665                       # N m
VENDOR_HUB = ROOT.parent / 'references/pololu_1999/pololu-universal-aluminum-mounting-hub-for-6mm-shaft-m3-holes.step'
# Shop listing options (no-load rpm, rated kg cm) from the user's screenshot; matched to the ZENG WHCD 12 V tables.
LISTING = [(375, 1.2), (210, 1.7), (150, 1.2), (90, 2.0), (68, 2.8), (40, 4.5), (30, 6.0), (18, 12.0), (6, 25.0)]
CHOSEN = dict(listing='12V 电机 (motor only) + 每分钟/30转 6KG.CM', model='JGY-370-1260', voltage_V=12, ratio=200)
CAT320_TOP_KMH, SCALE = 5.7, 15         # Cat 320 spec sheet p. 2; the 60 mm excavator's 1:15 reference scale
OLD_BORE_L = 9.1                        # printed D-bore engagement of the 2026-11-02 sprocket (superseded)
PRINT = {   # axis, angle: how each part lies on the bed
    'J901_H_frame': ((1, 0, 0), -90, 'outer wall face on the bed; support under the inner wall overhangs'),
    'J902_sprocket': ((1, 0, 0), -90, 'outer disc face on the bed, hub up; no supports'),
    'J903_journal_plug': ((1, 0, 0), -90, 'standing on its end'),
    'J904_roller': ((1, 0, 0), -90, 'on a flange face; no supports'),
    'J906_idler_wheel': ((1, 0, 0), -90, 'as J8 07_idler_wheel'),
    'J907_idler_spacer': ((1, 0, 0), -90, 'standing on its end'),
    'J908_U_yoke': ((1, 0, 0), 180, 'upside down, flat top face on the bed'),
    'J909_housing': ((1, 0, 0), -90, 'skirt inner face on the bed; supports inside the motor pod only'),
    'J910_track_shoe_70': ((1, 0, 0), 0, 'grousers on the bed, as the R4 shoe'),
}


def dist(a, b):
    d = BRepExtrema_DistShapeShape(P.one(a).wrapped, P.one(b).wrapped); d.Perform()
    return round(d.Value(), 3)


def against(fixed, moving):
    return checks.interference({**fixed, **moving}, skip=lambda a, b: (a in moving) == (b in moving))


def moved(inst, names, dx=0., dy=0., dz=0.):
    return {n: {**inst[n], 'shape': inst[n]['shape'].translate((dx, dy, dz))} for n in names}


def export_parts(prt):
    rows = []
    for n, d in prt.items():
        s = d['shape']
        assert P.one(s).isValid() and len(s.solids().vals()) == 1, n
        print('Export', n, flush=True)
        export.export_step(s, ROOT / 'step' / f'{n}.step')
        axis, deg, how = PRINT[n]
        tm = export.export_stl(export.to_bed(s, axis, deg), ROOT / 'stl' / f'{n}.stl')
        vol = P.one(s).Volume()
        rows.append(dict(name=n, quantity=d['quantity'], material=d['material'], note=d['note'], print_orientation=how,
                         volume_mm3=round(vol, 1), solid_PETG_mass_g=round(vol*PETG_G_MM3, 1),
                         print_bounds_mm=[round(v, 1) for v in tm.extents.tolist()], stl_watertight=True,
                         stl_components=len(tm.split()), step_roundtrip=True, solids=1))
    return rows


def vendor_hub_check():
    """Place Pololu's own STEP in the J9 pose and compare it with the modelled hub (Ø2.5 tap holes, as the vendor)."""
    if not VENDOR_HUB.exists():
        return dict(skipped=f'vendor STEP not found at {VENDOR_HUB}', ok=True)
    v = cq.importers.importStep(str(VENDOR_HUB)).val()
    v = v.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), 30).rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), 90)
    v = v.translate(cq.Vector(D.DRIVE_X, D.HUB_FACE_Y - D.HUB['flange_t']/2, D.AXLE_Z))
    m = P.one(P.pololu_hub(D.HUB['tap_r']))
    bv, bm = v.BoundingBox(), m.BoundingBox()
    dev = max(abs(a - b) for a, b in zip((bv.xmin, bv.xmax, bv.ymin, bv.ymax, bv.zmin, bv.zmax),
                                         (bm.xmin, bm.xmax, bm.ymin, bm.ymax, bm.zmin, bm.zmax)))
    only_v, only_m = v.cut(m).Volume(), m.cut(v).Volume()
    return dict(file=str(VENDOR_HUB.relative_to(P.REPO)), vendor_volume_mm3=round(v.Volume(), 1), model_volume_mm3=round(m.Volume(), 1),
                bbox_max_deviation_mm=round(dev, 4), vendor_not_in_model_mm3=round(only_v, 2), model_not_in_vendor_mm3=round(only_m, 2),
                note='Model has sharp edges where the vendor STEP has chamfers, so only model-not-in-vendor volume is expected. '
                     'A misplaced hole or set screw would show up in both directions.',
                ok=dev < .02 and only_v < 1.0 and only_m < 30.0)


def drive_option(r):
    """Track speed, pull and old printed-D-bore pressure for one vendor table row at its 12 V rating."""
    mm_s = D.TEETH*D.PITCH/60; R = D.PITCH_R/1000; w = 2*math.sqrt(3**2 - 2.5**2)
    Tr, Ts = float(r['rated_kgf_cm'])*KGF_CM, float(r['stall_kgf_cm'])*KGF_CM
    p = lambda T: round(12*T*1e3/(OLD_BORE_L*w*w))
    return dict(model=r['model'], ratio=int(r['ratio']), no_load_rpm=float(r['no_load_rpm']), rated_rpm=float(r['rated_rpm']),
                track_mm_s_no_load=round(float(r['no_load_rpm'])*mm_s), track_mm_s_rated_load=round(float(r['rated_rpm'])*mm_s),
                rated_Nm=round(Tr, 3), stall_Nm=round(Ts, 3), rated_A=float(r['rated_A']), stall_A=float(r['stall_A']),
                track_pull_rated_N=round(Tr/R, 1), track_pull_stall_N=round(Ts/R, 1),
                old_printed_D_flat_MPa_rated=p(Tr), old_printed_D_flat_MPa_stall=p(Ts))


def save_assembly(inst, path, name):
    a = cq.Assembly(name=name)
    for n, d in inst.items():
        a.add(d['shape'], name=n, color=cq.Color(*d['color']))
    a.export(str(path))
    rt = cq.importers.importStep(str(path))
    assert P.one(rt).isValid()
    return len(rt.solids().vals())


def phase_pins(f):
    """Chain advanced by a fraction f of a pitch: pins stay on the wheel pitch circles on the wraps
    and on the straight runs elsewhere (a conveyor approximation used for clearance sampling)."""
    p = D.PINS; n = len(p); out = []
    centres = [np.array([D.DRIVE_X, D.AXLE_Z]), np.array([D.IDLER_X, D.AXLE_Z])]
    for k in range(n):
        a, b = p[k], p[(k + 1) % n]
        q = a + (b - a)*f
        for c in centres:
            if abs(np.linalg.norm(a - c) - D.PITCH_R) < 1e-6 and abs(np.linalg.norm(b - c) - D.PITCH_R) < 1e-6:
                ta, tb = math.atan2(*(a - c)[::-1]), math.atan2(*(b - c)[::-1])
                if tb < ta: tb += 2*math.pi
                t = ta + (tb - ta)*f; q = c + D.PITCH_R*np.array([math.cos(t), math.sin(t)])
        out.append(q)
    return np.array(out)


def write_scene(prt, inst):
    print('Viewer scene', flush=True)
    scene = export.scene_items({n: d for n, d in inst.items() if d['group'] != 'track'})
    for item in scene:
        if item['name'].startswith(('JGY370_', 'motor_screw')) and item['group'] == 'frame': item['group'] = 'motor'
    pinset = tp.yring(D.BUSH_R, 1.55, -D.BUSH_HALF_L, D.BUSH_HALF_L).union(tp.ycyl(D.PIN_R, -D.PIN_HALF_L, D.PIN_HALF_L))
    for dy in (-D.CLIP_Y, D.CLIP_Y):
        pinset = pinset.union(tp.yring(3, 1.5, dy - .3, dy + .3))
    link = [dict(name='J910_track_shoe_70', color=list(P.RUBBER), **export.mesh(prt['J910_track_shoe_70']['shape'])),
            dict(name='pin, bushing, 2 clips', color=list(P.STEEL), **export.mesh(pinset))]
    payload = dict(unit=scene, link=link, config=dict(revision='J9', pitch=D.PITCH, pitch_r=D.PITCH_R, drive=[D.DRIVE_X, D.AXLE_Z],
                   idler=[D.IDLER_X, D.AXLE_Z], pins=D.PINS.tolist(), recoil=D.RECOIL,
                   rollers={g: [x, z] for x, z, g in P.ROLLERS}, roller_r=D.ROLLER_R, rail_face=D.RAIL_FACE,
                   key=dict(track_top=round(D.check()['track_top_z'], 1), top_lift=D.TOP_LIFT, axle_z=round(D.AXLE_Z, 2),
                            centres=round(D.IDLER_X - D.DRIVE_X, 1), shoe=D.SHOE_W,
                            width=round(D.SHOE_W/2 - P.one(inst['J909_housing']['shape']).BoundingBox().ymin, 1))))
    (P.HERE / 'j9_scene.json.gz').write_bytes(gzip.compress(json.dumps(payload, separators=(',', ':')).encode()))


def main():
    t0 = time.time()
    (ROOT / 'step').mkdir(exist_ok=True); (ROOT / 'stl').mkdir(exist_ok=True)
    prt = P.parts()
    rows = export_parts(prt)
    inst = P.unit(prt)
    print('Assembly STEP', flush=True)
    solids = save_assembly(inst, ROOT / 'step' / 'JGY370_track_J9.step', 'JGY370_track_J9')
    rep = dict(revision='J9', design=D.check(), parts=rows, assembly_solids=solids)

    fixed_names = [n for n, d in inst.items() if d['group'] in ('frame', 'housing')]
    fixed = {n: inst[n] for n in fixed_names}
    nochain = {n: d for n, d in inst.items() if d['group'] != 'track'}

    print('Static interference', flush=True)
    rep['static'] = checks.interference(inst)

    print('Drive rotation', flush=True)
    drive = [n for n, d in inst.items() if d['group'] == 'drive']
    others = {n: d for n, d in nochain.items() if d['group'] != 'drive'}
    rot = []
    for a in range(0, 30, 5):
        posed = {n: {**inst[n], 'shape': inst[n]['shape'].rotate((D.DRIVE_X, 0, D.AXLE_Z), (D.DRIVE_X, 1, D.AXLE_Z), a)} for n in drive}
        rot.append(dict(angle_deg=a, **against(others, posed)))
    rep['drive_rotation_no_chain'] = rot

    print('Idler recoil travel', flush=True)
    slide = [n for n, d in inst.items() if d['group'] in ('idler', 'idler_slide')]
    rest = {n: d for n, d in nochain.items() if d['group'] not in ('idler', 'idler_slide', 'spring')}
    travel = []
    for dx in (-D.RECOIL/2, -D.RECOIL):
        travel.append(dict(idler_x=round(D.IDLER_X + dx, 3), **against(rest, moved(inst, slide, dx))))
    over = against(rest, moved(inst, slide, -D.RECOIL - .3))
    travel.append(dict(idler_x=round(D.IDLER_X - D.RECOIL - .3, 3), expect='stop: arms meet the groove ends', stop_hits=[h['b'] if h['a'] in slide else h['a'] for h in over['hits']]))
    rep['idler_travel'] = travel
    spring_recoil = P.spring_helix(D.SPRING_X0, D.SPRING_SET - D.RECOIL)
    rep['spring_at_recoil'] = against({n: d for n, d in rest.items()} | moved(inst, slide, -D.RECOIL),
                                      {'spring': dict(shape=spring_recoil, group='spring')})

    print('Chain phases', flush=True)
    phases = []
    for f in (.25, .5, .75):
        ch = {n: dict(shape=s, color=c, group='track') for n, (s, c) in P.chain(prt, phase_pins(f)).items()}
        res = against(fixed, ch)
        phases.append(dict(fraction_of_pitch=f, **res))
    rep['chain_phases_vs_fixed_parts'] = phases

    print('Assembly paths', flush=True)
    seq = {}
    # 1. Motor screws go in from inside the open H before the sprocket (L-key short arm along +Y).
    base = {n: d for n, d in nochain.items() if d['group'] in ('frame', 'housing')}
    seq['motor_screw_key_before_sprocket'] = [against(base, {'key': dict(shape=tp.ycyl(1.25, -22, 8, x, z), group='tool')}) for x, z in D.MOTOR_HOLES]
    # 2. Sprocket with its hub (bolted on at the bench) enters radially between the walls 9.6 mm outboard
    #    of its seat, then slides onto the shaft until its pad meets the shaft end.
    spr_names = ['J902_sprocket', 'Pololu_1999_hub'] + [n for n in inst if n.startswith(('hub_screw_', 'hub_set_screw_'))]
    spr = {n: inst[n] for n in spr_names}
    fixed_drive = {**base, 'JGY370_output_shaft': inst['JGY370_output_shaft']}
    radial = []
    for dx in (-150, -110, -80, -60, -40, -25, -12, -5, 0):
        radial.append(dict(dx=dx, **against(fixed_drive, moved(spr, spr_names, dx, 9.6))))
    axial = [dict(dy=dy, **against(fixed_drive, moved(spr, spr_names, 0, dy))) for dy in (9.6, 7, 4, 2, 0)]
    seq['sprocket_radial_entry'] = radial; seq['sprocket_slide_onto_shaft'] = axial
    # 3. Journal plug and M3 x 50 enter from outside through the 6800ZZ.
    plug_names = ['J903_journal_plug', 'sprocket_screw_M3x50']
    ref = {**base, **spr, **{n: inst[n] for n in ('JGY370_output_shaft', '6800ZZ_inner')}}
    seq['plug_insertion'] = [dict(dy=dy, **against(ref, moved(inst, plug_names, 0, dy))) for dy in (40, 20, 10, 3, 0)]
    # 4. Yoke, idler, pin and spacers slide in from the front along the grooves.
    seq['yoke_insertion'] = [dict(dx=dx, **against(rest, moved(inst, slide, dx))) for dx in (60, 40, 20, 8, 0)]
    # 5. Tool access with everything fitted.
    seq['housing_screw_driver'] = [against(nochain, {'key': dict(shape=tp.ycyl(1.6, -90, -39.7, x, z), group='tool')}) for x, z in P.HOUSING_SCREWS]
    seq['roller_bolt_through_skirt'] = [against(inst, {'bolt_path': dict(shape=tp.ycyl(3.6, -90, -34.05, x, z), group='tool')}) for x, z, _ in P.ROLLERS]
    seq['nyloc_socket'] = [against(inst, {'socket': dict(shape=tp.yring(5.6, 2.6, 35.05, 90, x, z), group='tool')}) for x, z, _ in P.ROLLERS]
    seq['plug_screw_key'] = against(inst, {'key': dict(shape=tp.ycyl(1.25, 33.05, 90, D.DRIVE_X, D.AXLE_Z), group='tool')})
    # 6. Hub set screws: 1.5 mm hex key (1.73 across corners) straight down between the walls, after the
    #    sprocket is on the shaft and before the plug, track and housing go on.
    stage = {n: d for n, d in nochain.items() if d['group'] != 'housing' and n not in plug_names}
    seq['hub_set_screw_key'] = [against(stage, {'key': dict(shape=tp.zcyl(.87, D.AXLE_Z + D.SHAFT_FLAT['across'] - 3 + l + .02, D.AXLE_Z + 80,
                                                                           D.DRIVE_X, D.HUB_FACE_Y - d), group='tool')}) for d, l in D.HUB_SET_SCREWS]
    # 7. Housing: slides on along +Y over the motor; the pod cavity has no undercut in that direction.
    #    The track is already on, but moving the housing outboard-to-inboard only increases its distance from the shoes.
    before = {n: d for n, d in nochain.items() if d['group'] != 'housing'}
    seq['housing_fitting'] = [dict(dy=dy, **against(before, moved(inst, ['J909_housing'], 0, -dy))) for dy in (40, 25, 15, 8, 4, 1.5)]
    rep['assembly_and_access'] = seq

    print('Clearances', flush=True)
    H = prt['J901_H_frame']['shape']
    clips = [d['shape'] for n, d in inst.items() if n.startswith('pin_clip_')]
    pins = [d['shape'] for n, d in inst.items() if n.startswith('track_pin_')]
    c = {}
    c['track pins and clips to H-frame'] = min(dist(H, s) for s in clips + pins)
    c['track shoes to housing'] = min(dist(prt['J909_housing']['shape'], inst[n]['shape']) for n in inst if n.startswith('shoe_'))
    c['road rollers to H-frame (walls 1.0 by design)'] = min(dist(H, inst[f'J904_roller_road{j}']['shape']) for j in range(5))
    c['road roller flanges to web underside'] = round(D.WEB_Z[0] - (D.ROAD_Z + D.FLANGE_R), 3)
    c['support roller flanges to web top'] = round(D.CARRIER_Z - D.FLANGE_R - D.WEB_Z[1], 3)
    c['support rollers to H-frame (walls)'] = min(dist(H, inst[f'J904_roller_support{j}']['shape']) for j in range(2))
    c['hub boss end to inner wall (1.0 by design)'] = dist(H, inst['Pololu_1999_hub']['shape'])
    c['sprocket to H-frame (tooth tips to the web end)'] = dist(H, inst['J902_sprocket']['shape'])
    c['hub and hub screw tips to motor screw heads'] = min(dist(inst[a]['shape'], inst[f'motor_screw_M3x6_{i}']['shape'])
                                                          for a in spr_names if not a.startswith('J902') for i in range(4))
    c['idler wheel to U-yoke'] = dist(inst['J906_idler_wheel']['shape'], inst['J908_U_yoke']['shape'])
    c['end road roller to sprocket'] = dist(inst['J904_roller_road0']['shape'], inst['J902_sprocket']['shape'])
    c['end road roller to idler at full recoil'] = dist(inst['J904_roller_road4']['shape'], inst['J906_idler_wheel']['shape'].translate((-D.RECOIL, 0, 0)))
    c['spring envelope to rollers'] = min(dist(tp.xring(D.SPRING['od']/2, D.SPRING['id']/2, D.SPRING_X0, D.SPRING_X0 + D.SPRING_SET, 0, D.AXLE_Z), inst[f'J904_roller_{g}']['shape']) for g in ('road2', 'road3', 'road4', 'support1'))
    c['U-yoke base to road roller'] = dist(inst['J908_U_yoke']['shape'], inst['J904_roller_road4']['shape'])
    motor = ('JGY370_gearbox', 'JGY370_motor_can', 'JGY370_terminal_space')
    c['housing pod to motor'] = min(dist(prt['J909_housing']['shape'], inst[n]['shape']) for n in motor)
    c['frame rim (behind the skirt) to motor'] = min(dist(P.pod_rim(), inst[n]['shape']) for n in motor)
    boss0 = tp.box(D.CHASSIS_X[0] - D.CHASSIS_HALF_X, D.CHASSIS_X[0] + D.CHASSIS_HALF_X, *D.CHASSIS_Y, *D.CHASSIS_Z)
    c['housing skirt cutouts to chassis bosses (0.5 by design)'] = dist(prt['J909_housing']['shape'], boss0)
    c['motor pod to rear chassis boss'] = dist(P.pod_outer(D.SKIRT_Y[1]), boss0)
    c['road roller tread to ground-run link faces'] = round(min(D.seg_dist(np.array([x, D.ROAD_Z]), a, b) for x in D.ROAD_X for a, b in D.running_faces(D.PINS)) - D.ROLLER_R, 4)
    c['support roller tread to top-run link faces'] = round(min(D.seg_dist(np.array([x, D.CARRIER_Z]), a, b) for x in D.CARRIER_X for a, b in D.running_faces(D.PINS)) - D.ROLLER_R, 4)
    c['sprocket bottom chord to ground line (pin line)'] = round(D.AXLE_Z - D.APOTHEM - D.GROUND_PIN_Z, 4)
    c['idler rail to ground-run link faces'] = round(D.APOTHEM - D.RAIL_FACE - D.IDLER_RAIL_R, 3)
    rep['clearances_mm'] = c

    print('Motor selection and drive hub', flush=True)
    rows_csv = (ROOT.parent / 'references/vendor_ratings.csv').read_text().strip().splitlines()
    vend = [dict(zip(rows_csv[0].split(','), l.split(','))) for l in rows_csv[1:]]
    def listed(rpm, kg):
        r = [v for v in vend if float(v['no_load_rpm']) == rpm and float(v['rated_kgf_cm']) == kg]
        return dict(listing=f'{rpm:g} rpm, {kg:g} kg cm', **(drive_option(r[0]) if r else dict(vendor_row=None)))
    options = [listed(*o) for o in LISTING]
    pick = drive_option(next(v for v in vend if v['model'] == CHOSEN['model'] and int(v['ratio']) == CHOSEN['ratio']))
    chk = D.check()
    rep['motor_selection'] = dict(
        chosen={**CHOSEN, **pick},
        basis=['12 V: the only voltage the vendor tables (ZENG WHCD JGY-370-1260/-1285) document; the 60 mm excavator has a regulated 12 V travel rail.',
               'Motor only: J9 bolts the gearbox face to the inner wall; the L-bracket and the one-way speed controller are not used.',
               f'Speed: Cat 320 top travel speed {CAT320_TOP_KMH} km/h is {CAT320_TOP_KMH/3.6e-3/SCALE:.0f} mm/s at 1:{SCALE}; '
               f'this option gives {pick["track_mm_s_rated_load"]}-{pick["track_mm_s_no_load"]} mm/s (rated load to no load).',
               f'Pull: the {pick["track_pull_stall_N"]} N stall pull is just inside the {chk["spring_at_recoil_N"]/2:.1f} N the spring idler '
               f'holds in reverse at its recoil stop; 340:1 and slower exceed it.',
               'Every useful ratio needs the metal hub: the old printed D-bore was over PETG yield already at the chosen rated torque.'],
        reverse_pull_before_idler_moves_N=round(chk['spring_preload_N']/2, 1),
        reverse_pull_at_recoil_stop_N=round(chk['spring_at_recoil_N']/2, 1),
        track_mm_s_per_rpm=round(D.TEETH*D.PITCH/60, 3), pitch_radius_mm=round(D.PITCH_R, 3),
        options=options,
        note='12 V vendor ratings. Pull = torque / sprocket pitch radius. A 12 V motor run from 2S (7.4 V) gives about 60 % of '
             'these speeds and stall values. No vehicle load rating is implied.')
    n = len(D.HUB_SCREW_DEG); rp = D.HUB['pcd_r']/1000
    boss_end = D.HUB_FACE_Y - D.HUB['flange_t'] - D.HUB['boss_h']
    screw_N = {k: round(pick[f'{k}_Nm']/(n*rp), 1) for k in ('rated', 'stall')}
    rep['drive_hub'] = dict(
        part='Pololu #1999 universal aluminium mounting hub for 6 mm shaft, M3 holes (sold in pairs with 4 set screws)',
        sources=['https://www.pololu.com/file/0J667/1999-6mm-m3-hub-dimensions.pdf',
                 'https://www.pololu.com/file/0J1153/pololu-universal-aluminum-mounting-hub-for-6mm-shaft-m3-holes.step'],
        vendor_step_check=vendor_hub_check(),
        shaft_engagement_mm=round(D.SHAFT_TIP_Y - boss_end, 2),
        boss_end_to_wall_face_mm=round(boss_end + D.WALL_IN, 2),
        set_screws=[dict(length_mm=l, centre_from_shaft_tip_mm=round(D.SHAFT_TIP_Y - (D.HUB_FACE_Y - d), 2),
                         on_flat=bool(D.SHAFT_TIP_Y - (D.HUB_FACE_Y - d) - 1.5 >= 0 and D.SHAFT_TIP_Y - (D.HUB_FACE_Y - d) + 1.5 <= D.SHAFT_FLAT['length']))
                    for d, l in D.HUB_SET_SCREWS],
        sprocket_screws=dict(count=n, size='ISO 4762 M3 x 25', pitch_circle_mm=round(2*D.HUB['pcd_r'], 2), thread_in_hub_mm=D.HUB['flange_t'],
                             force_per_screw_N=screw_N, printed_hole_bearing_MPa={k: round(v/(3*3), 1) for k, v in screw_N.items()},
                             note='Chosen motor at rated and stall torque. Bearing on the printed hole wall over the first 3 mm next to '
                                  'the hub; clamping friction ignored.'),
        old_printed_D_bore=dict(engagement_mm=OLD_BORE_L, flat_width_mm=round(2*math.sqrt(3**2 - 2.5**2), 2),
                                formula='p = 12 T / (L w^2): elastic, linear pressure over the loaded half of the flat',
                                rated_MPa=pick['old_printed_D_flat_MPa_rated'], stall_MPa=pick['old_printed_D_flat_MPa_stall'],
                                correction='The 2026-11-02 table used 6T/(L w^2), which understated the pressure by a factor of 2.'),
        open='Pololu publishes no torque rating for the set screws on a D flat. Mark them and check after the first runs.')

    runs = [rep['static'], rep['spring_at_recoil']] + rot + travel[:2] + phases + seq['motor_screw_key_before_sprocket'] + radial + axial + \
        seq['plug_insertion'] + seq['yoke_insertion'] + seq['housing_screw_driver'] + seq['roller_bolt_through_skirt'] + seq['nyloc_socket'] + \
        [seq['plug_screw_key']] + seq['hub_set_screw_key'] + seq['housing_fitting']
    stop_ok = bool(travel[2]['stop_hits']) and all('U_yoke' in h or 'H_frame' in h for h in travel[2]['stop_hits'])
    hub_ok = rep['drive_hub']['vendor_step_check']['ok'] and all(s['on_flat'] for s in rep['drive_hub']['set_screws'])
    rep['pass'] = all(not r['hits'] for r in runs) and stop_ok and hub_ok and D.check()['link_error_mm'] < 1e-9
    rep['scope'] = ('Nominal CAD with exact solid intersections; sampled drive rotation, idler recoil, chain phases (conveyor '
                    'approximation on the wraps), assembly paths and tool access. Not a load, fatigue, print-tolerance or powered test.')
    rep['elapsed_s'] = round(time.time() - t0, 1)
    (ROOT / 'validation.json').write_text(json.dumps(rep, indent=1, default=float) + '\n')

    def failures(v, path=''):
        if isinstance(v, dict):
            if v.get('hits'): print('FAIL', path, v['hits'][:6], flush=True)
            for k, w in v.items(): failures(w, path + '/' + k)
        if isinstance(v, list):
            for i, w in enumerate(v): failures(w, path + '/' + str(i))
    failures({k: v for k, v in rep.items() if k != 'idler_travel'} | {'idler_travel': travel[:2]})
    print(json.dumps(dict(passed=rep['pass'], stop=travel[2]['stop_hits'], clearances=c, static_pairs=rep['static']['pairs_tested'], elapsed=rep['elapsed_s']), indent=1, default=float), flush=True)

    write_scene(prt, inst)
    print('done', round(time.time() - t0, 1), 's', flush=True)


if __name__ == '__main__':
    import sys
    if '--scene-only' in sys.argv:
        prt = P.parts(); write_scene(prt, P.unit(prt))
    else:
        main()

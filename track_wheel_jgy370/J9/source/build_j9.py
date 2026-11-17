"""Export J9 (STEP, print-oriented STL, coloured assembly) and run the geometry checks.

Run with the CAD interpreter from this folder:  python build_j9.py
Writes ../step, ../stl, ../validation.json and j9_scene.json.gz (viewer data).
"""
import json, gzip, math, time, hashlib
from pathlib import Path
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
# Seller drawing of the Ø32 / Ø6 flange coupling; every value confirmed on the part by the user on 2026-11-12.
SELLER_HUB = dict(flange_d=32.0, flange_t=4.0, boss_d=14.0, overall=14.0, bore_d=6.0, holes=6, hole_circle_d=23.0,
                  set_screw_from_boss_end=5.0, drawing='track_wheel_jgy370/references/flange_coupling_32/seller_drawing.jpg')
# Shop listing options (no-load rpm, rated kg cm) from the user's screenshot; matched to the ZENG WHCD 12 V tables.
LISTING = [(375, 1.2), (210, 1.7), (150, 1.2), (90, 2.0), (68, 2.8), (40, 4.5), (30, 6.0), (18, 12.0), (6, 25.0)]
CHOSEN = dict(listing='12V 电机 (motor only) + 每分钟/30转 6KG.CM', model='JGY-370-1260', voltage_V=12, ratio=200)
CAT320_TOP_KMH, SCALE = 5.7, 15         # Cat 320 spec sheet p. 2; the 60 mm excavator's 1:15 reference scale
OLD_BORE_L = 9.1                        # printed D-bore engagement of the 2026-11-02 sprocket (superseded)
PRINT = {   # axis, angle: how each part lies on the bed
    'J901_H_frame': ((1, 0, 0), -90, 'outer wall face on the bed; support under the inner wall overhangs'),
    'J902_sprocket': ((1, 0, 0), -90, 'outer disc face on the bed, recess ring and pad up; no supports'),
    'J903_journal_plug': ((1, 0, 0), -90, 'standing on its end'),
    'J904_roller': ((1, 0, 0), -90, 'on a flange face; no supports'),
    'J906_idler_wheel': ((1, 0, 0), -90, 'as J8 07_idler_wheel'),
    'J907_idler_spacer': ((1, 0, 0), -90, 'standing on its end'),
    'J908_U_yoke': ((1, 0, 0), 180, 'upside down, flat top face on the bed; support rear piston as needed'),
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


def coupling_check():
    """Probe the modelled coupling (J9 pose) against the seller drawing's values: outline, flange thickness, boss, bore,
    six holes on the hole circle, and the set screw 5 mm from the boss end, halfway between two holes."""
    S = SELLER_HUB
    m = P.one(P.flange_coupling())
    bb = m.BoundingBox()
    face = D.HUB_FACE_Y; back = face - S['flange_t']; end = face - S['overall']; ys = end + S['set_screw_from_boss_end']

    def solid(r, deg, y):
        a = math.radians(deg)
        return m.isInside(cq.Vector(D.DRIVE_X + r*math.cos(a), y, D.AXLE_Z + r*math.sin(a)))
    e = .05
    probes = dict(
        outline=abs(bb.xlen - S['flange_d']) < 1e-3 and abs(bb.zlen - S['flange_d']) < 1e-3 and abs(bb.ylen - S['overall']) < 1e-3,
        flange=(solid(S['flange_d']/2 - e, 30, back + e) and solid(S['flange_d']/2 - e, 30, face - e)
                and not solid(S['flange_d']/2 - e, 30, back - e) and not solid(S['flange_d']/2 + e, 30, face - e)),
        boss=solid(S['boss_d']/2 - e, 30, end + e) and not solid(S['boss_d']/2 + e, 30, end + e),
        bore=(not solid(S['bore_d']/2 - e, 30, end + 1) and solid(S['bore_d']/2 + e, 30, end + 1)
              and not solid(S['bore_d']/2 - e, 30, face - 1)),
        holes=all(not solid(S['hole_circle_d']/2, a, back + 1) and solid(S['hole_circle_d']/2, a + 30, back + 1)
                  for a in range(0, 360, 360//S['holes'])),
        set_screw=(not solid(5.0, 90, ys) and solid(5.0, 90, ys + 2) and solid(5.0, 90, ys - 2) and solid(5.0, 270, ys)))
    return dict(drawing=S['drawing'], seller_values=S, model_bbox_mm=[round(v, 3) for v in (bb.xlen, bb.ylen, bb.zlen)],
                volume_mm3=round(m.Volume(), 1), aluminium_mass_g=round(m.Volume()*2.70e-3, 1), probes=probes,
                ok=all(probes.values()))


def hub_set_screws():
    """Each coupling set screw: length, centre from the shaft tip, and whether its whole Ø3 tip lands on the D flat."""
    rows = []
    for d, l in D.HUB_SET_SCREWS:
        c = D.SHAFT_TIP_Y - (D.HUB_FACE_Y - d)
        rows.append(dict(length_mm=l, centre_from_shaft_tip_mm=round(c, 2),
                         on_flat=bool(c - 1.5 >= 0 and c + 1.5 <= D.SHAFT_FLAT['length'])))
    return rows


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
    hw = P.chain_hardware()
    pinset = cq.Workplane(obj=cq.Compound.makeCompound([P.one(hw[k]) for k in ('screw', 'nut', 'sleeve')]))
    link = [dict(name='J910_track_shoe_70', color=list(P.RUBBER), **export.mesh(prt['J910_track_shoe_70']['shape'])),
            dict(name=P.LINK_HARDWARE_NAME, color=list(P.STEEL), **export.mesh(pinset))]
    payload = dict(unit=scene, link=link, config=dict(revision='J9', pitch=D.PITCH, pitch_r=D.PITCH_R, drive=[D.DRIVE_X, D.AXLE_Z],
                   idler=[D.IDLER_X, D.AXLE_Z], pins=D.PINS.tolist(), recoil=D.RECOIL,
                   rollers={g: [x, z] for x, z, g in P.ROLLERS}, roller_r=D.ROLLER_R, rail_face=D.RAIL_FACE,
                   key=dict(track_top=round(D.check()['track_top_z'], 1), top_lift=D.TOP_LIFT, axle_z=round(D.AXLE_Z, 2),
                            centres=round(D.IDLER_X - D.DRIVE_X, 1), shoe=D.SHOE_W,
                            width=round(D.SHOE_W/2 - P.one(inst['J909_housing']['shape']).BoundingBox().ymin, 1))))
    (P.HERE / 'j9_scene.json.gz').write_bytes(gzip.compress(json.dumps(payload, separators=(',', ':')).encode()))


def main():
    t0 = time.time()
    sources = [P.HERE / name for name in ('build_j9.py', 'j9_parts.py', 'j9_design.py',
                                          'j9_mounts.py', 'check_spring_guide.py')]
    sources += [Path(module.__file__) for module in (tp, checks, export)]
    source_hashes = {str(p.relative_to(P.REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    (ROOT / 'step').mkdir(exist_ok=True); (ROOT / 'stl').mkdir(exist_ok=True)
    prt = P.parts()
    rows = export_parts(prt)
    inst = P.unit(prt)
    print('Assembly STEP', flush=True)
    solids = save_assembly(inst, ROOT / 'step' / 'JGY370_track_J9.step', 'JGY370_track_J9')
    rep = dict(revision='J9 revision F mounting stations', design=D.check(), parts=rows, assembly_solids=solids)
    from check_spring_guide import check as check_spring_guide
    rep['spring_guide'] = check_spring_guide(prt['J901_H_frame']['shape'], prt['J908_U_yoke']['shape'])
    (ROOT / 'spring_guide_validation.json').write_text(json.dumps(rep['spring_guide'], indent=2) + '\n')

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
    spr_names = ['J902_sprocket', 'flange_coupling_32'] + [n for n in inst if n.startswith(('hub_screw_', 'hub_set_screw_'))]
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
    joint = [d['shape'] for n, d in inst.items() if n.startswith(('track_screw_', 'track_nut_'))]
    c = {}
    c['track screws and nuts to H-frame'] = min(dist(H, s) for s in joint)
    c['track shoes to housing'] = min(dist(prt['J909_housing']['shape'], inst[n]['shape']) for n in inst if n.startswith('shoe_'))
    c['road rollers to H-frame (including spring guide)'] = min(dist(H, inst[f'J904_roller_road{j}']['shape']) for j in range(5))
    c['road roller flanges to web underside'] = round(D.WEB_Z[0] - (D.ROAD_Z + D.FLANGE_R), 3)
    c['support roller flanges to web top'] = round(D.CARRIER_Z - D.FLANGE_R - D.WEB_Z[1], 3)
    c['support rollers to H-frame (walls)'] = min(dist(H, inst[f'J904_roller_support{j}']['shape']) for j in range(2))
    c['hub boss end to inner wall (1.0 by design)'] = dist(H, inst['flange_coupling_32']['shape'])
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
    pads = P.mounts.pads()
    c['housing cutouts to chassis mounting stations'] = dist(prt['J909_housing']['shape'], pads)
    c['motor gearbox to chassis mounting stations'] = dist(inst['JGY370_gearbox']['shape'], pads)
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
    tip = D.SPROCKET_Y[1] - P.M3_HEAD['h'] - D.HUB_SCREW_L
    back = D.HUB_FACE_Y - D.HUB['flange_t']
    rep['drive_hub'] = dict(
        part='Ø32 / Ø6 aluminium flange coupling: flange Ø32 x 4 with 6 x M3 tapped holes on Ø23, boss Ø14 x 10, one M3 set screw',
        sources=[SELLER_HUB['drawing'], 'Every value confirmed on the part by the user on 2026-11-12; the Pololu #1999 hub '
                                        'used before could not be bought.'],
        seller_drawing_check=coupling_check(),
        shaft_engagement_mm=round(D.SHAFT_TIP_Y - boss_end, 2),
        boss_end_to_wall_face_mm=round(boss_end + D.WALL_IN, 2),
        set_screws=hub_set_screws(),
        sprocket_screws=dict(count=n, size=f'ISO 4762 M3 x {D.HUB_SCREW_L:g}', pitch_circle_mm=round(2*D.HUB['pcd_r'], 2),
                             thread_in_hub_mm=round(D.HUB_FACE_Y - max(back, tip), 2), tip_past_flange_mm=round(back - tip, 2),
                             force_per_screw_N=screw_N, printed_hole_bearing_MPa={k: round(v/(3*3), 1) for k, v in screw_N.items()},
                             note='Chosen motor at rated and stall torque. Bearing on the printed hole wall over the first 3 mm next to '
                                  'the hub; clamping friction ignored.'),
        old_printed_D_bore=dict(engagement_mm=OLD_BORE_L, flat_width_mm=round(2*math.sqrt(3**2 - 2.5**2), 2),
                                formula='p = 12 T / (L w^2): elastic, linear pressure over the loaded half of the flat',
                                rated_MPa=pick['old_printed_D_flat_MPa_rated'], stall_MPa=pick['old_printed_D_flat_MPa_stall'],
                                correction='The 2026-11-02 table used 6T/(L w^2), which understated the pressure by a factor of 2.'),
        open='The coupling has one set screw on the D flat (the Pololu hub had two) and no torque rating. Mark it and check it '
             'after the first runs and after any stall.')

    runs = [rep['static'], rep['spring_at_recoil']] + rot + travel[:2] + phases + seq['motor_screw_key_before_sprocket'] + radial + axial + \
        seq['plug_insertion'] + seq['yoke_insertion'] + seq['housing_screw_driver'] + seq['roller_bolt_through_skirt'] + seq['nyloc_socket'] + \
        [seq['plug_screw_key']] + seq['hub_set_screw_key'] + seq['housing_fitting']
    stop_ok = bool(travel[2]['stop_hits']) and all('U_yoke' in h or 'H_frame' in h for h in travel[2]['stop_hits'])
    hub_ok = rep['drive_hub']['seller_drawing_check']['ok'] and all(s['on_flat'] for s in rep['drive_hub']['set_screws'])
    rep['pass'] = all(not r['hits'] for r in runs) and stop_ok and hub_ok and D.check()['link_error_mm'] < 1e-9 and rep['spring_guide']['pass']
    rep['scope'] = ('Nominal CAD with exact solid intersections; sampled drive rotation, idler recoil, chain phases (conveyor '
                    'approximation on the wraps), assembly paths and tool access. Not a load, fatigue, print-tolerance or powered test.')
    rep['elapsed_s'] = round(time.time() - t0, 1)
    assert all(hashlib.sha256((P.REPO / name).read_bytes()).hexdigest() == value
               for name, value in source_hashes.items()), 'CAD source changed during validation'
    rep['source_sha256'] = source_hashes
    rep['exported_step_sha256'] = {str(p.relative_to(P.REPO)): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted((ROOT / 'step').glob('*.step')) if p.stem in P.PRINTED}
    rep['exported_stl_sha256'] = {str(p.relative_to(P.REPO)): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sorted((ROOT / 'stl').glob('*.stl'))}
    rep['spring_guide_report_sha256'] = hashlib.sha256((ROOT / 'spring_guide_validation.json').read_bytes()).hexdigest()
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

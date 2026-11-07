"""Build and check the X1 turntable (concept R3 issue 3) on the X1 chassis (X101 rev B).

Run with the CAD interpreter from this folder:  python build_turntable.py
Writes:
  ../step/<part>.step, ../stl/<part>.stl      printed turntable parts (STL in print orientation)
  ../step/X1_turntable_assembly.step          turntable + X-frame centre (no tracks) + ARM60 base, at swing 0
                                              (tracks: X1_crawler_chassis.step; arm: excavator_arm_60mm/step)
  ../turntable_validation.json                fits, swing sweep, gear mesh, assembly paths, tool access, clearances
  ../simulation/turntable_mass_properties.json   rigid bodies for simulate_swing.py (SI units)
  turntable_scene.json.gz                     viewer meshes (build_viewer.py adds them to the X1 viewer)
"""
import json, gzip, math, sys, time, hashlib
from functools import lru_cache
from pathlib import Path
import numpy as np
import cadquery as cq
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
import x1_parts as X
import x1_turntable as T
from x1_parts import P9, D9, tp
import tw_checks as checks
import build_track_wheel as export

ROOT = X.ROOT
R3, R2 = T.R3, T.R2
SIM = ROOT / 'simulation'
DENS = dict(petg=1.27e-6, tpu=1.20e-6, steel=7.85e-6, brass=8.5e-6, alu=2.70e-6)   # kg/mm^3
MOTOR_KG = 0.17            # JGY-370-1260 gearmotor, assumed (no vendor figure); split over gearbox and can by volume
SLIP_KG = 0.030            # 6-way capsule slip ring with leads, assumed
ARM_KG = 1.6418            # ARM60 with actuators: excavator_60mm/validation.json loads.arm_mass_kg (CAD-derived)
RU66_KG = X.RU66['mass_kg']


def one(s):
    return tp.one(s)


def dist(a, b):
    d = BRepExtrema_DistShapeShape(one(a).wrapped, one(b).wrapped); d.Perform()
    return round(d.Value(), 3)


def compound(shapes):
    return cq.Workplane(obj=cq.Compound.makeCompound([one(s) for s in shapes]))


def against(fixed, moving):
    return checks.interference({**fixed, **moving}, skip=lambda a, b: (a in moving) == (b in moving))


def tool(shape):
    return {'tool': dict(shape=shape, group='tool')}


def consistency():
    """The chassis interface in x1_parts must match the R3 numbers the turntable is built from."""
    assert X.RG_HOLES['r'] == R3.RG['screw_r'] and X.RG_HOLES['ang'] == R3.RG['screw_ang']
    assert X.RG_HOLES['scallop_r'] == R3.RG['scallop_r']
    assert (X.COLLAR['r_in'], X.COLLAR['r_out']) == (R2.COLLAR['r_in'], R2.COLLAR['r_out'])
    assert X.COLLAR['z'] == (R2.COLLAR['z0'], R2.COLLAR['z1']) and X.COLLAR['insert_r'] == R2.PCD_R
    assert X.SEAT_STACK['screw_L'] == R3.BOT_SCREW['L']
    return True


# ------------------------------------------------------------------ exports
def export_parts():
    rows = []
    for n, d in T.printed_parts().items():
        s = d['shape']
        assert one(s).isValid() and len(s.solids().vals()) == 1, n
        print('Export', n, flush=True)
        export.export_step(s, ROOT / 'step' / f'{n}.step')
        axis, deg, how = d['print']
        tm = export.export_stl(export.to_bed(s, axis, deg), ROOT / 'stl' / f'{n}.stl')
        vol = one(s).Volume()
        dens = DENS['tpu'] if 'TPU' in n else DENS['petg']
        rows.append(dict(name=n, quantity=d['quantity'], material=d['material'], note=d['note'], print_orientation=how,
                         volume_mm3=round(vol, 1), solid_mass_g=round(vol*dens*1000, 1), print_bounds_mm=[round(v, 1) for v in tm.extents.tolist()],
                         stl_watertight=True, stl_components=len(tm.split()), step_roundtrip=True))
    return rows


def save_assembly(inst, path, name):
    a = cq.Assembly(name=name)
    for n, d in inst.items():
        a.add(d['shape'], name=n, color=cq.Color(*d['color']))
    a.export(str(path))
    rt = cq.importers.importStep(str(path))
    assert one(rt).isValid()
    return len(rt.solids().vals())


# ------------------------------------------------------------------ checks
def is_upper(d):
    return d['group'] in ('upper', 'pinion', 'arm')


def static_check(lower, tt):
    """Every turntable solid against everything; chassis pairs were checked in build_x1, track pairs in J9."""
    allp = {**lower, **tt}
    return checks.interference(allp, skip=lambda a, b: (a in lower and b in lower)
                               or (allp[a]['group'] == 'arm' and allp[b]['group'] == 'arm'))


def swing_sweep(lower, step=15, angles=None):
    """Upper (and the arm) at every swing angle against the chassis and the chassis-side turntable parts."""
    out = []
    for a in (angles if angles is not None else range(0, 360, step)):
        tt = T.turntable(a)
        up = {n: d for n, d in tt.items() if is_upper(d)}
        up['RU66_inner_ring'] = {**lower['RU66_inner_ring'], 'shape': lower['RU66_inner_ring']['shape'].rotate((0, 0, 0), (0, 0, 1), a)}
        fixed = {**{n: d for n, d in lower.items() if n != 'RU66_inner_ring'}, **{n: d for n, d in tt.items() if not is_upper(d)}}
        r = against(fixed, up)
        out.append(dict(swing_deg=a, pairs=r['pairs_tested'], hits=r['hits']))
        print(f'  swing {a:3d}: {len(r["hits"])} hits', flush=True)
    return out


def gear_mesh(lower_ring):
    """Pinion against the ring gear through one ring-tooth pitch (the mesh repeats every 4.5°): exact overlap and the
    smallest gap (half the normal backlash when the pinion is centred in its play)."""
    rows = []
    for a in np.linspace(0, 360/R3.ZR, 10):
        p = T.turntable(float(a), with_arm=False)['T105_pinion']['shape']
        common = one(p).intersect(one(lower_ring))
        v = sum(s.Volume() for s in common.Solids()) if common is not None else 0.
        rows.append(dict(swing_deg=round(float(a), 3), overlap_mm3=round(v, 4), min_gap_mm=dist(p, lower_ring)))
        print('  mesh', rows[-1], flush=True)
    return rows


def paths(lower, tt0):
    """Assembly paths in the R3 order (sheet 4). Each step lists the hits at decreasing distances from home."""
    seq = {}
    side = {n: d for n, d in tt0.items() if not is_upper(d)}
    chassis_noring = {n: d for n, d in lower.items() if not n.startswith(('RU66', 'seat_screw'))}
    ring = {'X103_ring_gear': tt0['X103_ring_gear']}
    seq['ring_gear_onto_seat'] = [dict(dz=dz, **against(chassis_noring, {n: {**d, 'shape': d['shape'].translate((0, 0, dz))} for n, d in ring.items()}))
                                  for dz in (30, 10, 3, 1)]
    ru = {n: d for n, d in lower.items() if n.startswith('RU66')}
    fix = {**{n: d for n, d in lower.items() if not n.startswith(('RU66', 'seat_screw'))}, **ring}
    seq['RU66_into_ring_gear_bore'] = [dict(dz=dz, **against(fix, {n: {**d, 'shape': d['shape'].translate((0, 0, dz))} for n, d in ru.items()}))
                                       for dz in (30, 10, 3, 1)]
    hub = ['T104_hub_adapter', 'T101_centre_frame']
    fixed = {**lower, **side}
    seq['T104_and_T101_lowered_onto_the_bearing'] = [dict(dz=dz, **against(fixed, {n: {**tt0[n], 'shape': tt0[n]['shape'].translate((0, 0, dz))} for n in hub}))
                                                    for dz in (40, 15, 5, 2, 1)]
    motor = [n for n, d in tt0.items() if d['group'] == 'pinion' or n.startswith(('T102', 'JGY370', 'motor_screw')) and 'lead_space' not in n]
    fixed2 = {**fixed, **{n: tt0[n] for n in tt0 if is_upper(tt0[n]) and n not in motor and tt0[n]['group'] != 'arm'
                          and not n.startswith(('slide_washer', 'slide_clamp', 'push_screw', 'push_nut', 'JGY370_lead_space'))}}
    rear = -(R3.SLIDE['travel'] + T.DX_SET)          # the opening's rear stop: 1.86 behind the set position (2 behind nominal)
    back = T.turntable(0, with_arm=False, slide_dx=rear)
    seq['motor_on_slide_lowered_into_opening_at_the_rear_stop'] = [dict(dz=dz, **against(fixed2, {n: {**back[n], 'shape': back[n]['shape'].translate((0, 0, dz))} for n in motor}))
                                                          for dz in (40, 15, 5, 2, 1, 0)]
    seq['slide_pushed_in_to_mesh'] = []
    for dx in (rear, -1.5, -1.0, -.5, -.1):
        moved = T.turntable(0, with_arm=False, slide_dx=dx)
        seq['slide_pushed_in_to_mesh'].append(dict(dx=dx, **against(fixed2, {n: moved[n] for n in motor})))
    pl = {f'T103_drag_plunger_{i}': tt0[f'T103_drag_plunger_{i}'] for i in range(len(R3.PAD_XY))}
    sp = {f'drag_spring_{i}': tt0[f'drag_spring_{i}'] for i in range(len(R3.PAD_XY))}
    t101 = {'T101_centre_frame': tt0['T101_centre_frame']}
    seq['plunger_dropped_in_from_the_top_before_the_insert'] = [
        dict(dz=dz, **against(t101, {n: {**d, 'shape': d['shape'].translate((0, 0, dz))} for n, d in pl.items()})) for dz in (30, 15, 5, 1)]
    with_ins = {**t101, **pl, **{n: tt0[n] for n in tt0 if n.startswith('drag_insert')}}
    seq['spring_dropped_through_the_M6_insert'] = [
        dict(dz=dz, **against(with_ins, {n: {**d, 'shape': d['shape'].translate((0, 0, dz))} for n, d in sp.items()})) for dz in (30, 15, 5, 1)]
    arm = {n: d for n, d in tt0.items() if d['group'] == 'arm'}
    fixed3 = {**fixed, **{n: d for n, d in tt0.items() if is_upper(d) and d['group'] != 'arm' and not n.startswith(('arm_bolt', 'arm_nut'))}}
    seq['ARM60_lowered_onto_the_ribs'] = [dict(dz=dz, **against(fixed3, {n: {**d, 'shape': d['shape'].translate((0, 0, dz))} for n, d in arm.items()}))
                                          for dz in (40, 15, 5, 1)]
    return seq


def tools(lower, tt0):
    """Keys and sockets on their real axes. Hex keys: M3 socket r 1.25, M4 socket and M6 set screw r 1.6, M6 socket r 2.6.
    A 7 mm socket for the M4 nuts: r 5.2."""
    every = {**lower, **tt0}
    noarm = {n: d for n, d in every.items() if d['group'] != 'arm'}
    t = {}
    st = X.SEAT_STACK
    bz = R3.BASE_Z
    head_top = bz[1] + st['washer'][2] + st['disc'][2] + X.M4_HEAD['h']
    hub_xy = [X.polar(r, a) for r, a in R3.TH_HUB]
    t['hub_screw_key_before_ARM60'] = [against(noarm, tool(X.zcyl(1.6, head_top + .05, head_top + 60, x, y))) for x, y in hub_xy]
    t['hub_screw_key_with_ARM60_fitted'] = [against(every, tool(X.zcyl(1.6, head_top + .05, head_top + 60, x, y))) for x, y in hub_xy]
    nut_bot = X.MOUNT_RING[2] - st['washer'][2] - st['disc'][2] - st['nut'][1]
    ru_xy = [X.polar(X.RU66['outer_pcd']/2, a) for a in X.OUTER_ANG]
    below = {n: d for n, d in every.items() if n != 'X102_belly_cover' and not n.startswith('cover_screw')}
    # 7 mm deep socket: hollow (hex 7 across flats), so the 3.9 mm of screw below the nut goes inside it
    t['RU66_nut_socket_from_below'] = [against(below, tool(X.zring(5.2, 3.5, X.BOTTOM_Z - 5, nut_bot - .05, x, y))) for x, y in ru_xy]
    rg_xy = [X.polar(R3.RG['screw_r'], a) for a in R3.RG['screw_ang']]
    z79 = X.TOP_Z - X.PLATE_T
    no_rg_screws = {n: d for n, d in below.items() if not n.startswith('ring_gear_screw')}
    t['ring_gear_screw_head_path_from_below'] = [against(no_rg_screws, tool(X.zcyl(X.M3_CSK['r'] + .05, X.BOTTOM_Z - 5, z79 - .05, x, y))) for x, y in rg_xy]
    t['ring_gear_screw_key_from_below'] = [against(below, tool(X.zcyl(1.25, X.BOTTOM_Z - 30, z79 - .05, x, y))) for x, y in rg_xy]
    col_xy = [X.polar(X.COLLAR['insert_r'], a) for a in X.COLLAR['insert_ang']]
    shead = R2.FL_Z[0] - T.WASHER_M3['t'] - T.M3_HEAD['h']
    t['slip_ring_screw_key_from_below'] = [against(below, tool(X.zcyl(1.25, X.BOTTOM_Z - 30, shead - .05, x, y))) for x, y in col_xy]
    sl = R3.SLIDE
    ctop = sl['ear_z'][1] + T.WASHER_M3['t'] + T.M3_HEAD['h']
    t['slide_clamp_key_from_above'] = [against(every, tool(X.zcyl(1.25, ctop + .05, ctop + 60, x, sy*y)))
                                       for x, y in sl['slots'] for sy in (1, -1)]
    p = R3.PAD
    t['drag_pad_set_screw_key_from_above'] = [against(every, tool(X.zcyl(1.6, p['top'] + .05, p['top'] + 60, x, y))) for x, y in R3.PAD_XY]   # from the screw's top face
    lug = R3.LUG
    hx = sl['x'][0] + T.DX_SET - 12.0 - T.M3_HEAD['h']
    t['push_screw_key_short_arm_15'] = [against(every, tool(tp.xcyl(1.25, hx - 15.0, hx - .05, sy*sum(lug['y'])/2, lug['screw_z']))) for sy in (1, -1)]
    zt = R3.TOPZ + R3.ARM_BASE['t'] + T.M6_HEAD['h']
    t['ARM60_bolt_key_from_above'] = [against(every, tool(X.zcyl(2.6, zt + .05, zt + 60, x, y))) for x, y in R3.ARM_BOLTS]
    return t


def clearances(lower, tt0):
    c = {}
    pin = tt0['T105_pinion']['shape']
    c['pinion to the X-frame (leg tops)'] = dist(pin, lower['X101_X_frame']['shape'])
    c['pinion to the ring gear (half the normal backlash)'] = dist(pin, tt0['X103_ring_gear']['shape'])
    c['T101 underside to the RU66 seat-screw heads'] = dist(tt0['T101_centre_frame']['shape'], compound([d['shape'] for n, d in lower.items() if n.startswith('seat_screw')]))
    c['T101 to the RU66 outer ring'] = dist(tt0['T101_centre_frame']['shape'], lower['RU66_outer_ring']['shape'])
    c['T104 to the RU66 outer ring'] = dist(tt0['T104_hub_adapter']['shape'], lower['RU66_outer_ring']['shape'])
    c['T104 prongs to the X-frame (relief floor)'] = dist(tt0['T104_hub_adapter']['shape'], lower['X101_X_frame']['shape'])
    c['T104 prongs to the rotor dog (free play, at swing 0)'] = dist(tt0['T104_hub_adapter']['shape'], tt0['T106_rotor_dog_TPU']['shape'])
    c['drag felt to the X-frame'] = min(dist(tt0[f'drag_felt_{i}']['shape'], lower['X101_X_frame']['shape']) for i in range(2))
    c['ring gear to the RU66 outer ring (bore, radial)'] = dist(tt0['X103_ring_gear']['shape'], lower['RU66_outer_ring']['shape'])
    c['hub flange to the motor slide'] = dist(tt0['Pololu_1999_hub']['shape'], tt0['T102_motor_slide']['shape'])
    c['hub boss to the gearbox'] = dist(tt0['Pololu_1999_hub']['shape'], tt0['JGY370_gearbox']['shape'])
    c['motor lead space to T101 (window)'] = dist(tt0['JGY370_lead_space']['shape'], tt0['T101_centre_frame']['shape'])
    c['slip-ring stator to the belly cover'] = dist(tt0['slip_ring_6way_stator']['shape'], lower['X102_belly_cover']['shape'])
    r_st, w_r = X.RU66['outer_pcd']/2, X.SEAT_STACK['washer'][0]          # the washers sit on the mount ring: radial gaps only
    c['RU66 Ø12 washers to the carbody wall (radial)'] = round(X.BODY_R - X.BODY_WALL - (r_st + w_r), 2)
    c['RU66 Ø12 washers to the slip-ring collar (radial)'] = round(r_st - w_r - X.COLLAR['r_out'], 2)
    arm = one(tt0['ARM60_arm_and_actuators']['shape'])
    ab = arm.BoundingBox()
    near = []
    for n, d in lower.items():                       # only track parts whose boxes come within 40 mm of the arm's box
        if n.startswith(('L_', 'R_')):
            b = one(d['shape']).BoundingBox()
            if b.xmax > ab.xmin - 40 and b.xmin < ab.xmax + 40 and b.ymax > ab.ymin - 40 and b.ymin < ab.ymax + 40 and b.zmax > ab.zmin - 40:
                near.append(d['shape'])
    c['ARM60 (stretched) to the tracks'] = dist(tt0['ARM60_arm_and_actuators']['shape'], compound(near)) if near else '> 40 (bounding boxes apart)'
    # rear of the upper inside the reserved tail-swing circle
    rmax = 0
    for n, d in tt0.items():
        if is_upper(d) and d['group'] != 'arm':
            b = one(d['shape']).BoundingBox()
            for x in (b.xmin, b.xmax):
                for y in (b.ymin, b.ymax):
                    if x < 0:
                        rmax = max(rmax, math.hypot(x, y))
    c['rear of the upper, largest radius (reserved tail swing R 189)'] = round(rmax, 1)
    return c


# ------------------------------------------------------------------ mass properties (for the simulation)
def material(n, d):
    if d.get('kind') == 'envelope' or n.startswith('RESERVED') or 'lead_space' in n or 'terminal_space' in n:
        return None
    if 'TPU' in n:
        return DENS['tpu']
    if d.get('kind') == 'printed' or n.startswith(('X10', 'T10', 'J90', 'shoe_')) or 'J9' in str(d.get('source')):
        return DENS['petg']
    if 'insert' in n:
        return DENS['brass']
    if 'Pololu' in n:
        return DENS['alu']
    if 'felt' in n:
        return .3e-6
    return DENS['steel']


def body_props(items):
    """items: list of (mass kg, centre mm, inertia about own centre kg mm^2) -> mass, centre (m), inertia about centre (kg m^2)."""
    m = sum(i[0] for i in items)
    c = sum(i[0]*np.asarray(i[1]) for i in items)/m
    I = np.zeros((3, 3))
    for mi, ci, Ii in items:
        d = np.asarray(ci) - c
        I += np.asarray(Ii) + mi*(d @ d*np.eye(3) - np.outer(d, d))
    return dict(mass_kg=m, centre_m=(c/1000).tolist(), inertia_kgm2=(I*1e-6).tolist())


def solid_item(s, density=None, mass=None):
    sol = one(s)
    v = sol.Volume()
    if mass is None:
        mass = v*density
    c = sol.Center()
    I = np.array(cq.Shape.matrixOfInertia(sol))*(mass/v)
    return mass, [c.x, c.y, c.z], I


def point_item(mass, centre, box_mm=(1, 1, 1)):
    a, b, c = box_mm
    I = mass/12*np.diag([b*b + c*c, a*a + c*c, a*a + b*b])
    return mass, list(centre), I


BODY_MASS = SIM / 'body_mass_properties.json'         # written by build_body.py (the body B1 CAD)


def placeholders():
    """Upper parts outside the turntable CAD. Once the body is built (build_body.py), its prints, ballast, electronics
    and fixings come from the body CAD. Before that: the 60 mm excavator's upper body, battery and electronics moved to
    X1's deck, and R3's 1.8 kg counterweight 160 mm behind the swing axis."""
    if BODY_MASS.exists():
        b = json.loads(BODY_MASS.read_text())
        items = [(r['mass_kg'], r['centre_mm'], np.array(r['inertia_kgmm2'])) for r in b['items']]
        return dict(items=items, kg=sum(i[0] for i in items), names=[r['name'] for r in b['items']],
                    source='simulation/body_mass_properties.json (build_body.py: body B1 CAD, shot sized for the CG on the swing axis)')
    data = json.loads((X.REPO / 'excavator_60mm/simulation/mass_properties.json').read_text())
    keep = {}
    dz = R3.TOPZ - 129.0               # 60 mm upper deck centre Z 129 -> X1 rib tops
    for r in data:
        if not r['upper'] or r['name'].startswith(('slew', '13_slew', '26_slew', '16_upper_deck', 'gear_standoff', '17_slew', 'steel_ballast', '18_counterweight', 'ballast')):
            continue
        keep[r['name']] = (r['mass_kg'], [r['centre_mm'][0], r['centre_mm'][1], r['centre_mm'][2] + dz])
    shells = [point_item(m, c, (40, 40, 40)) for m, c in keep.values()]
    cw = point_item(R3.CW['mass'], (R3.CW['x'], 0, R3.BASE_Z[0] + 20), (54, 150, 40))
    return dict(items=[cw] + shells, kg=R3.CW['mass'] + sum(m for m, _ in keep.values()), names=['R3 counterweight'] + sorted(keep),
                source='R3 counterweight (1.8 kg at X -160) and excavator_60mm/simulation/mass_properties.json (upper body, '
                       'battery, electronics), Z moved to X1 deck')


def mass_item(n, d, arm_v, motor_v):
    """(mass, centre, inertia) of one CAD solid, or None for envelopes."""
    if n.startswith('ARM60'):
        return solid_item(d['shape'], mass=ARM_KG*one(d['shape']).Volume()/arm_v)
    if n in ('JGY370_gearbox', 'JGY370_motor_can'):
        return solid_item(d['shape'], mass=MOTOR_KG*one(d['shape']).Volume()/motor_v)
    if n.endswith(('JGY370_gearbox', 'JGY370_motor_can')):          # track motors
        return solid_item(d['shape'], mass=MOTOR_KG/2)
    if n.startswith('RU66'):
        return solid_item(d['shape'], mass=RU66_KG/2)
    if n.startswith('slip_ring_6way'):
        return solid_item(d['shape'], mass=SLIP_KG*(.85 if 'stator' in n else .15))
    rho = material(n, d)
    return None if rho is None else solid_item(d['shape'], density=rho)


def arm_motor_volumes(tt0):
    return (sum(one(tt0[n]['shape']).Volume() for n in ('ARM60_fixed_pivot_base', 'ARM60_arm_and_actuators')),
            sum(one(tt0[n]['shape']).Volume() for n in ('JGY370_gearbox', 'JGY370_motor_can')))


def mass_properties(lower, tt0):
    upper, pinion, low, rows = [], [], [], []
    arm_v, motor_v = arm_motor_volumes(tt0)
    for n, d in {**lower, **tt0}.items():
        it = mass_item(n, d, arm_v, motor_v)
        if it is None:
            continue
        on_upper = is_upper(d) or n == 'RU66_inner_ring'                   # the inner ring turns with the upper
        (pinion if d['group'] == 'pinion' else upper if on_upper else low).append(it)
        rows.append(dict(name=n, body='pinion' if d['group'] == 'pinion' else 'upper' if on_upper else 'lower', mass_kg=round(it[0], 5)))
    ph = placeholders()
    up = body_props(upper + ph['items'])
    up_cad = body_props(upper)
    res = dict(units='kg, m, kg m^2 about the body centre; vehicle frame (X forward, Z up), swing 0',
               upper=up, upper_cad_only=up_cad, pinion=body_props(pinion), lower=body_props(low),
               upper_inertia_about_swing_axis_kgm2=up['inertia_kgm2'][2][2] + up['mass_kg']*(up['centre_m'][0]**2 + up['centre_m'][1]**2),
               pinion_inertia_about_its_axis_kgm2=None,
               assumptions=dict(densities_kg_mm3=DENS, motor_kg=MOTOR_KG, slip_ring_kg=SLIP_KG, arm_kg=ARM_KG,
                                arm_pose='excavator_arm_60mm STEP as exported (stretched forward, bucket 440 mm from the swing axis)',
                                rest_of_upper=dict(kg=ph['kg'], source=ph['source'], names=ph['names']),
                                printed='turntable parts: full modelled volume at PETG density (as the 60 mm excavator); '
                                        'body prints: see body_mass_properties.json'),
               parts=rows)
    p = res['pinion']
    res['pinion_inertia_about_its_axis_kgm2'] = p['inertia_kgm2'][2][2] + p['mass_kg']*((p['centre_m'][0] - T.PXS/1000)**2 + p['centre_m'][1]**2)
    return res


def tip_point(tt0):
    b = one(tt0['ARM60_arm_and_actuators']['shape']).BoundingBox()
    return [b.xmax, 0.0, b.zmin + 10]


# ------------------------------------------------------------------ viewer
def write_scene(tt0, sweep_ok):
    print('Viewer scene', flush=True)
    items = []
    for n, d in tt0.items():
        if n.startswith(('JGY370_lead_space',)):
            continue
        fine = n in ('T105_pinion', 'X103_ring_gear')
        m = export.mesh(d['shape'], .02, .1) if fine else export.mesh(d['shape'], .1, .2)
        items.append(dict(name=n, color=list(d['color']), group=d['group'], kind=d.get('kind', 'hardware'), source=d.get('source'), **m))
    payload = dict(items=items, pinion_axis=[T.PXS, 0.0], ratio=T.RATIO, sweep_ok=sweep_ok)
    (X.HERE / 'turntable_scene.json.gz').write_bytes(gzip.compress(json.dumps(payload, separators=(',', ':')).encode()))


_sources = [*X.HERE.glob('*.py'), *(X.ROOT.parent / 'J9/source').glob('*.py'), *(X.ROOT / 'swing_concept/source').glob('*.py')]
_fingerprint = hashlib.sha256(b''.join(p.read_bytes() for p in sorted(_sources))).hexdigest()[:16]
CACHE = Path('/tmp/sw-render') / ('tt_cache_' + _fingerprint)        # stage results, so each stage can run on its own (python build_turntable.py <stage>)
STAGES = ('export', 'static', 'mesh', 'paths', 'tools', 'clearances', 'mass', 'sweep', 'final')


def cached(name, fn):
    f = CACHE / f'{name}.json'
    if f.exists():
        return json.loads(f.read_text())
    t = time.time()
    r = fn()
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(r, ensure_ascii=False))
    print(f'  [{name}: {time.time() - t:.0f} s]', flush=True)
    return r


MODEL_CACHE = Path('/tmp/sw-render/model_cache')   # built models as BREP, keyed by their source files' contents


def stamp(*files):
    """Cache key from the source files' contents, so a changed model is rebuilt (file times change on every checkout)."""
    return hashlib.sha256(b''.join(Path(f).read_bytes() for f in files)).hexdigest()[:12]


def brep_cached(tag, build, root=MODEL_CACHE):
    """name -> item dict; the shapes kept as BREP files in root/<tag>/ (loading them takes seconds, building minutes)."""
    d = root / tag
    meta = d / 'meta.json'
    if meta.exists():
        m = json.loads(meta.read_text())
        return {n: {**info['data'], 'shape': cq.Workplane(obj=cq.Shape.importBrep(str(d / info['file'])))} for n, info in m.items()}
    items = build()
    d.mkdir(parents=True, exist_ok=True)
    m = {}
    for i, (n, it) in enumerate(items.items()):
        f = f'{i:04d}.brep'
        one(it['shape']).exportBrep(str(d / f))
        m[n] = dict(file=f, data={k: (list(v) if isinstance(v, tuple) else v) for k, v in it.items() if k != 'shape'})
    meta.write_text(json.dumps(m))
    return items


R3_SRC = ROOT / 'swing_concept/source/draw_swing_concept_r3.py'
J9_SRC = sorted((ROOT.parent / 'J9/source').glob('*.py'))       # j9_parts, j9_mounts (the revision F seats), tw_parts, ...
R_SRC = sorted((ROOT / 'swing_concept/source').glob('*.py'))     # R3 imports R1 and R2


def chassis_model():
    print('Chassis', flush=True)
    return brep_cached('lower_' + stamp(X.HERE / 'x1_parts.py', *J9_SRC),
                       lambda: {n: d for n, d in X.unit(P9.unit(P9.parts(), with_chain=True), with_reserve=False).items()})


def turntable_model():
    print('Turntable and ARM60', flush=True)
    return brep_cached('tt_' + stamp(X.HERE / 'x1_turntable.py', X.HERE / 'x1_parts.py', *R_SRC, *J9_SRC), lambda: T.turntable(0))


@lru_cache(None)
def models():
    return chassis_model(), turntable_model()


def run_stage(st, sweep_angles=None):
    lower = lambda: models()[0]
    tt0 = lambda: models()[1]
    if st == 'export':
        def f():
            rows = export_parts()
            keep = {n: d for n, d in {**lower(), **tt0()}.items() if not n.startswith(('L_', 'R_')) and n != 'ARM60_arm_and_actuators'}
            print('Assembly STEP', flush=True)
            return dict(rows=rows, solids=save_assembly(keep, ROOT / 'step/X1_turntable_assembly.step', 'X1_turntable_assembly'))
        return cached('export', f)
    if st == 'static':
        r = cached('static', lambda: static_check(lower(), tt0()))
        print('  static hits:', r['hits'], flush=True); return r
    if st == 'mesh':
        return cached('mesh', lambda: gear_mesh(tt0()['X103_ring_gear']['shape']))
    if st == 'paths':
        r = cached('paths', lambda: paths(lower(), tt0()))
        print('  path hits:', {k: [len(x['hits']) for x in v] for k, v in r.items()}, flush=True); return r
    if st == 'tools':
        r = cached('tools', lambda: tools(lower(), tt0()))
        print('  tool hits:', {k: [len(x['hits']) for x in v] for k, v in r.items()}, flush=True); return r
    if st == 'clearances':
        r = cached('clearances', lambda: clearances(lower(), tt0()))
        print('  clearances:', r, flush=True); return r
    if st == 'mass':
        def f():
            mp = mass_properties(lower(), tt0())
            mp['bucket_tip_mm'] = tip_point(tt0())
            SIM.mkdir(exist_ok=True)
            (SIM / 'turntable_mass_properties.json').write_text(json.dumps(mp, indent=1) + '\n')
            write_scene(tt0(), None)
            return dict(upper_kg=round(mp['upper']['mass_kg'], 3), upper_cad_kg=round(mp['upper_cad_only']['mass_kg'], 3),
                        lower_kg=round(mp['lower']['mass_kg'], 3),
                        upper_inertia_about_swing_axis_kgm2=round(mp['upper_inertia_about_swing_axis_kgm2'], 4))
        return cached('mass', f)
    if st == 'sweep':
        rows = []
        for a in (sweep_angles or range(0, 360, 15)):
            rows += cached(f'sweep_{a:03d}', lambda a=a: swing_sweep(lower(), angles=[a]))
        return rows
    if st == 'final':
        return final()
    raise SystemExit(f'unknown stage {st}; one of {STAGES}')


def final():
    t0 = time.time()
    ex, static, mesh, seq, tl, clr, ms = (run_stage(s) for s in ('export', 'static', 'mesh', 'paths', 'tools', 'clearances', 'mass'))
    sweep = run_stage('sweep')
    sweep_ok = all(not r['hits'] for r in sweep)
    known = {'hub_screw_key_with_ARM60_fitted'}        # expected: the ARM60 base covers the hub well (service note)
    path_runs = [r for v in seq.values() for r in v]
    tool_runs = [r for k, v in tl.items() if k not in known for r in v]
    mesh_ok = all(r['overlap_mm3'] == 0 and r['min_gap_mm'] > .01 for r in mesh)
    ok = (not static['hits'] and sweep_ok and mesh_ok and all(not r['hits'] for r in path_runs + tool_runs)
          and clr['rear of the upper, largest radius (reserved tail swing R 189)'] <= X.RESERVE_R)
    sc = X.HERE / 'turntable_scene.json.gz'               # record the sweep result in the viewer data
    data = json.loads(gzip.decompress(sc.read_bytes())); data['sweep_ok'] = sweep_ok
    sc.write_bytes(gzip.compress(json.dumps(data, separators=(',', ':')).encode()))
    val = dict(revision='X1 turntable, concept R3 issue 3 (CAD)', chassis='X101 revision F, straight arms (x1_parts.py)',
               drawings='swing_concept/X1_swing_concept_R3.pdf', parts=ex['rows'], assembly_solids=ex['solids'],
               static=static, gear_mesh=dict(backlash_set_mm=R3.BACKLASH, centre_distance_mm=round(-T.PXS, 3), rows=mesh, ok=mesh_ok),
               swing_sweep=dict(step_deg=15, ok=sweep_ok, rows=sweep), assembly_paths=seq, tool_access=tl,
               known_service_limits=dict(hub_screw_key_with_ARM60_fitted=[len(r['hits']) for r in tl['hub_screw_key_with_ARM60_fitted']],
                                         note='The ARM60 base covers the hub well. To re-tighten the 8 hub screws (after about 1 h and 10 h of '
                                              'running), take the ARM60 off first (4 x M6). The RU66 nuts are re-tightened from below with the belly cover off.'),
               clearances_mm=clr, mass_summary=ms,
               scope='Nominal CAD with exact solid intersections: static fit, swing sweep every 15°, gear mesh through one tooth pitch, '
                     'assembly paths in the R3 order, tool access and clearances. Not a print-tolerance, load or powered test '
                     '(see simulate_swing.py for the dynamics).')
    val['pass'] = ok
    (ROOT / 'turntable_validation.json').write_text(json.dumps(val, indent=1, ensure_ascii=False) + '\n')
    print(json.dumps(dict(passed=ok, static_hits=static['hits'][:8], mesh=[(r['swing_deg'], r['overlap_mm3'], r['min_gap_mm']) for r in mesh],
                          sweep_hits={r['swing_deg']: r['hits'][:3] for r in sweep if r['hits']},
                          path_hits={k: [len(r['hits']) for r in v] for k, v in seq.items()},
                          path_hit_detail={k: [r['hits'][:3] for r in v if r['hits']] for k, v in seq.items() if any(r['hits'] for r in v)},
                          tool_hits={k: [len(r['hits']) for r in v] for k, v in tl.items()},
                          tool_hit_detail={k: [r['hits'][:3] for r in v if r['hits']][:2] for k, v in tl.items() if any(r['hits'] for r in v)},
                          clearances=clr, mass=ms), indent=1, ensure_ascii=False))
    return ok


def main():
    """No argument: every stage (about 40 min). With a stage name: only that stage (cached in /tmp/sw-render/tt_cache;
    delete the cache after changing the CAD). 'sweep' takes optional angles: python build_turntable.py sweep 0 15 30."""
    consistency()
    (ROOT / 'step').mkdir(exist_ok=True); (ROOT / 'stl').mkdir(exist_ok=True); SIM.mkdir(exist_ok=True)
    args = sys.argv[1:]
    if not args:
        final()
    elif args[0] == 'sweep':
        run_stage('sweep', [int(a) for a in args[1:]] or None)
    else:
        for st in args:
            run_stage(st)


if __name__ == '__main__':
    main()

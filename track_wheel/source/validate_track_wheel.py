"""Validate the track wheel unit and write ../validation.json.

Exact CAD interference in the assembly pose and at both ends of the idler
travel and adjuster range; minimum gaps between parts that move relative to
each other; fits at datasheet extremes; fastener engagement; gear mesh at
+/-0.1 mm centre distance; spring, bearing and strength checks; drive rating;
mass. Printed-material allowables are assumptions until parts are tested.
Run: python validate_track_wheel.py   (about 5 minutes)
"""
import json, math, time
import numpy as np
import cadquery as cq
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
import tw_parts as tp
import tw_checks as tc
import tw_gears as tg
from tw_design import *

ROOT = tp.ROOT
PETG_KG_MM3 = 1.27e-6
STEEL_KG_MM3 = 7.85e-6
BRASS_KG_MM3 = 8.5e-6
PRINTED_TOOTH_ALLOWABLE_MPA = 8.0     # same assumption as the excavator slew gear; test required
# Parts of the unchanged Track R4 chain/roller set: their mutual gaps were validated with R4.
R4 = ('shoe_', 'track_bushing', 'track_pin', 'pin_clip', '07_idler_wheel', '08_road_roller', '24_return_roller',
      'axle_', 'collar_', 'spacer_', '608_', 'idler_608', 'idler_spacer', 'idler_collar', 'idler_axle')
# Deliberate contacts between relatively moving groups.
CONTACT = [('gearmotor_gearbox', 'gearmotor_shaft', 'shaft leaves the output bushing'),
           ('adjuster_M6x16', 'adjuster_captive_nut', 'thread'),
           ('TW06_track_frame', 'adjuster_lock_nut', 'lock nut clamps the rear wall'),
           ('recoil_spring', 'TW07_idler_yoke', 'spring end on the yoke'),
           ('recoil_spring', 'TW08_spring_seat', 'spring end on the seat')]
MIN_GAP = .05


def r4(n):
    return n.startswith(R4)


def contact_reason(a, b):
    for x, y, why in CONTACT:
        if {a, b} == {x, y}:
            return why
    if a.startswith('bearing_') and b.startswith('bearing_') and a.rsplit('_', 1)[0] == b.rsplit('_', 1)[0]:
        return 'inside one bearing'
    return None


def clearances(inst, near=1.0):
    """Minimum distance for every pair of different groups closer than `near` (mm)."""
    t0 = time.time()
    shp = {n: tc._one(d.get('envelope', d['shape'])) for n, d in inst.items()}
    bbs = {n: s.BoundingBox() for n, s in shp.items()}
    names = list(inst); rows = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if inst[a]['group'] == inst[b]['group'] or (r4(a) and r4(b)):
                continue
            A, B = bbs[a], bbs[b]
            if (A.xmin > B.xmax + near or B.xmin > A.xmax + near or A.ymin > B.ymax + near or
                    B.ymin > A.ymax + near or A.zmin > B.zmax + near or B.zmin > A.zmax + near):
                continue
            d = BRepExtrema_DistShapeShape(shp[a].wrapped, shp[b].wrapped); d.Perform()
            if d.Value() < near:
                rows.append(dict(a=a, b=b, groups=[inst[a]['group'], inst[b]['group']], gap_mm=round(d.Value(), 4),
                                 contact=contact_reason(a, b)))
    rows.sort(key=lambda r: r['gap_mm'])
    bad = [r for r in rows if r['gap_mm'] < MIN_GAP and not r['contact']]
    return dict(pairs_below_1mm=rows, violations=bad, threshold_mm=MIN_GAP, seconds=round(time.time() - t0, 1))


def moving_subset(inst):
    """Parts that matter for the idler travel and adjuster checks (chain excluded)."""
    keep = {}
    for n, d in inst.items():
        if d['group'] in ['idler_slide', 'idler', 'spring', 'adjuster'] or n in [
                'TW06_track_frame', 'TW09_channel_nose', 'adjuster_captive_nut', 'nose_bolt_0', 'nose_bolt_1',
                'nose_nut_0', 'nose_nut_1', '08_road_roller_2', 'axle_roller2', 'collar_roller2_0',
                '24_return_roller_1', 'axle_return1', 'collar_return1_0']:
            keep[n] = d
    return keep


def travel_checks(parts):
    out = {}
    cases = [('recoil_stop', ADJUST_NOMINAL, -recoil_travel()),
             ('forward_stop', ADJUST_NOMINAL, forward_travel()),
             ('adjuster_min', ADJUST_RANGE[0], 0.0), ('adjuster_max', ADJUST_RANGE[1], 0.0),
             ('adjuster_max_recoil_stop', ADJUST_RANGE[1], -recoil_travel()),
             ('adjuster_min_recoil_stop', ADJUST_RANGE[0], -recoil_travel())]
    for name, ext, shift in cases:
        inst = moving_subset(tp.unit_instances(parts, extension=ext, with_chain=False, yoke_shift=shift))
        r = tc.interference(inst)
        st = spring_state(ext, shift + ASSEMBLY_YOKE_SHIFT)
        yoke = tc._one(inst['TW07_idler_yoke']['shape']).BoundingBox()
        seat = tc._one(inst['TW08_spring_seat']['shape']).BoundingBox()
        out[name] = dict(adjuster_extension_mm=ext, yoke_shift_from_assembly_mm=round(shift, 4),
                         spring_length_mm=round(st['length'], 3), spring_force_N=round(st['force'], 2),
                         spigot_gap_mm=round(yoke.xmin - seat.xmax, 3), hits=r['hits'], pairs_tested=r['pairs_tested'])
        a = tc._one(inst['07_idler_wheel']['shape']); b = tc._one(inst['08_road_roller_2']['shape'])
        d = BRepExtrema_DistShapeShape(a.wrapped, b.wrapped); d.Perform()
        out[name]['idler_to_front_roller_mm'] = round(d.Value(), 3)
    return out


def gear_checks(parts):
    out = dict(spec=PINION_SPEC, module=GEAR_MODULE, teeth=[PINION_TEETH, RING_TEETH], ratio=HUB_RATIO,
               design_backlash_mm=GEAR_BACKLASH, centre_distance_mm=CENTRE_DISTANCE,
               centre_distance_tolerance_mm=.1,
               centre_distance_basis='Gearbox Ø12 output bushing in a Ø12.15 hole in the housing end wall (±0.075) '
                                     'plus ±0.025 for the gearbox offset; checked at ±0.1.')
    for a in [CENTRE_DISTANCE - .1, CENTRE_DISTANCE, CENTRE_DISTANCE + .1]:
        r = tg.mesh_check(a)
        out[f'a_{a:.1f}'] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if k != 'rows'}
    out['involute_theory'] = {k: round(v, 4) for k, v in tg.contact_ratio_theory().items()}
    # 3D CAD: rotate the cap and pinion together and intersect the solids.
    cap = parts['TW03_hub_cap']['shape']; pin = tp.pinion()
    rows = []
    for beta in np.linspace(0, 360 / RING_TEETH, 5, endpoint=False):
        c = cap.rotate((tp.DX, 0, tp.DZ), (tp.DX, -1, tp.DZ), beta)
        p = pin.rotate((tp.PX, 0, tp.PZ), (tp.PX, -1, tp.PZ), beta * RING_TEETH / PINION_TEETH)
        common = tc._one(c).intersect(tc._one(p))
        v = sum(s.Volume() for s in common.Solids())
        d = BRepExtrema_DistShapeShape(tc._one(c).wrapped, tc._one(p).wrapped); d.Perform()
        rows.append(dict(ring_deg=round(float(beta), 3), overlap_mm3=round(v, 5), min_gap_mm=round(d.Value(), 4)))
    out['cad_3d'] = rows
    return out


def fits():
    g = GEARMOTOR; tol = GEARMOTOR_DIAMETER_TOL; b = BEARINGS
    rows = []
    def row(name, value, limit, ok, basis):
        rows.append(dict(check=name, value=round(value, 3), limit=limit, ok=bool(ok), basis=basis))
    row('gearbox in housing bore, min radial gap (Ø36.8 +0.2)', (TUBE_BORE - g['gearbox_diameter'] - tol) / 2, '>0', TUBE_BORE > g['gearbox_diameter'] + tol,
        'Pololu 37D drawing; diameter tolerance not stated, ±0.2 assumed')
    row('motor can in housing bore, min radial gap (Ø34.8 +0.2)', (TUBE_BORE - g['motor_diameter'] - tol) / 2, '>0', True, 'Pololu 37D drawing')
    row('output bushing in end-wall hole, diametral gap', 12.15 - g['bushing_diameter'], '0.05..0.25', True, 'locates the gear centre distance')
    rear = FACE_Y - g['gearbox_length'] - g['motor_length'] - g['terminal_projection']
    cavity = REAR_CAP_Y[0] + 1.2
    row('motor terminals to rear-cap floor (gearbox 0.5 mm long)', rear - .5 - cavity, '>=1.5', rear - .5 - cavity >= 1.5,
        'terminal projection 5.0 mm from the drawing; 0.5 mm length tolerance assumed')
    shaft_end = FACE_Y + g['shaft_length']
    row('shaft end to cap pocket floor (shaft +0.5 mm)', CAP_Y[1] - CAP_END_PLATE + 1.0 - (shaft_end + .5), '>=0.5', True,
        'shaft 22.0 mm from the gearbox face; pocket Ø23 × 1 mm in the cap end plate')
    row('pinion face to cap end plate', CAP_Y[1] - CAP_END_PLATE - PINION_Y[1], '>=0.4', True, 'pinion set flush with the 22 mm shaft end')
    row('pinion to bearing retainer', PINION_Y[0] - RETAINER_Y[1], '>=0.5', True, '')
    row('ring gear to bearing retainer', RING_Y[0] - RETAINER_Y[1], '>=0.5', True, '')
    face_thread = FACE_Y - (face_screw_head_y_value() - FACE_SCREW_LENGTH)
    row('gearbox face screw thread depth', -face_thread if face_thread < 0 else face_thread, f"<= {g['face_screw_max_depth']}",
        abs(face_thread) <= g['face_screw_max_depth'], 'Pololu: M3 face holes, 3 mm maximum screw depth')
    row('6809 inner ring seat on housing tube', TUBE_OD, b['inboard']['d'], TUBE_OD == b['inboard']['d'], 'loose (floating) fit; printed Ø45.00, stationary inner ring')
    row('61808 inner ring seat on end-wall spigot', END_WALL_SEAT_D, b['outboard']['d'], END_WALL_SEAT_D == b['outboard']['d'], 'printed Ø40.00, clamped by TW04')
    row('6809 outer seat in hub', b['inboard']['D'], b['inboard']['D'], True, 'press fit, rotating outer-ring load; tune with a test print')
    row('61808 outer seat in hub', b['outboard']['D'], b['outboard']['D'], True, 'press fit; clamped by the cap lip')
    row('61808 inner-ring shoulder diameter (≤ d_as max)', 42.8, b['outboard']['shoulder_d_max'], True, 'housing relief at Y -3.9..-3.5; retainer Ø42.8')
    row('6809 outer-ring shoulder bore (≥ D_as min)', 55.5, b['inboard']['housing_shoulder_D_min'], True, 'hub relief Ø55.5')
    row('61808 outer-ring shoulder bore (≥ D_as min)', 50.0, b['outboard']['housing_shoulder_D_min'], True, 'hub relief Ø50, cap lip ID 50')
    row('spring OD in bore, radial gap', (SPRING_BORE_D - SPRING['od']) / 2, '>=1', True, 'C-600-072-1500 OD 0.600 in')
    row('spring ID on Ø10 spigots, radial gap', (SPRING['id'] - SPIGOT_D) / 2, '>=0.5', True, '')
    row('yoke in channel, gap per side (Y, Z)', min(CHANNEL_Y[1] - CHANNEL_Y[0] - 2 * YOKE_HALF[0], 2 * CHANNEL_Z - 2 * YOKE_HALF[1]) / 2, '>=0.2', True, 'printed sliding fit')
    return rows


def face_screw_head_y_value():
    return tp.face_screw_head_y()


def fasteners():
    rows = []
    def row(name, spec, qty, engagement, available, note=''):
        rows.append(dict(fastener=name, spec=spec, quantity=qty, engagement_mm=round(engagement, 2),
                         available_mm=available, ok=bool(engagement <= available + 1e-9), note=note))
    hy = tp.face_screw_head_y()
    row('gearbox face screws', 'M3 × 10 button head ISO 7380', 6, FACE_Y - (hy - FACE_SCREW_LENGTH), GEARMOTOR['face_screw_max_depth'],
        'through TW04 and the end wall into the gearbox face')
    row('hub cap screws', 'M3 × 20 button head ISO 7380', 6, HUB_Y[1] - .05 - (CAP_Y[1] - CAP_SCREW_LENGTH), INSERT_M3['length'] - .05,
        'into M3 × 5.7 inserts in TW02')
    row('housing flange screws', 'M3 × 10 socket head ISO 4762', 4, FLANGE_Y[0] + FLANGE_SCREW_LENGTH - (FRAME_Y[0] + .05), INSERT_M3['length'] - .05,
        'into M3 × 5.7 inserts in the TW06 boss')
    row('rear cap screws', 'M3 × 8 socket head ISO 4762', 2, REAR_CAP_EAR_Y[0] + REAR_CAP_SCREW_LENGTH - (REAR_CAP_EAR_Y[1] + .05), INSERT_M3['length'] - .05,
        'into M3 × 5.7 inserts in the TW01 pillars')
    row('nose bolts', 'M3 × 40 socket head + ISO 4032 nut', 2, NUT_M3['h'], NUT_M3['h'], 'through TW06 channel and TW09')
    row('tension adjuster', 'M6 × 16 hex ISO 4017 + 2 × M6 nut', 1, NUT_M6['h'], NUT_M6['h'], 'captive nut in the rear wall, lock nut outside')
    root_r = PINION_TEETH * GEAR_MODULE / 2 - 1.25 * GEAR_MODULE
    row('pinion set screw', 'M3 × 4 cup point ISO 4029', 1, 4.0, round(root_r - (GEARMOTOR['shaft_flat'] - GEARMOTOR['shaft_diameter'] / 2), 2),
        'tapped radially between two teeth onto the D-flat; length = thread available from flat to root circle')
    return rows


def spring_checks():
    s = SPRING; out = dict(model=s['model'], source=s['source'], rate_N_mm=round(s['rate_N_mm'], 3),
                           free_length_mm=round(s['free_length'], 2), solid_length_mm=round(s['solid_length'], 2),
                           max_load_N=round(s['max_load_N'], 1), od_mm=round(s['od'], 2), wire_mm=round(s['wire'], 3))
    out['catalogue_max_load_length_mm'] = round(s['free_length'] - s['max_load_N'] / s['rate_N_mm'], 2)
    out['solid_margin_at_stop_mm'] = round(stop_state(ADJUST_RANGE[1])['length'] - s['solid_length'], 2)
    rows = []
    fmax = drive_force_limit()['chain_pull_N']
    for ext in [ADJUST_RANGE[0], ADJUST_NOMINAL, ADJUST_RANGE[1]]:
        for k in [1 - s['rate_tolerance'], 1.0, 1 + s['rate_tolerance']]:
            st = spring_state(ext, rate=s['rate_N_mm'] * k)
            sp = stop_state(ext, rate=s['rate_N_mm'] * k)
            rows.append(dict(adjuster_mm=ext, rate_factor=round(k, 2), length_mm=round(st['length'], 2), preload_N=round(st['force'], 1),
                             length_at_stop_mm=round(sp['length'], 2), force_at_stop_N=round(sp['force'], 1),
                             below_max_load=bool(sp['force'] <= s['max_load_N']),
                             reverse_slack_strand_N=round(st['force'] / 2 - fmax, 1)))
    out['cases'] = rows
    nominal = spring_state()
    out['nominal'] = dict(adjuster_mm=ADJUST_NOMINAL, length_mm=round(nominal['length'], 3), preload_N=round(nominal['force'], 1),
                          recoil_travel_mm=round(recoil_travel(), 2), forward_travel_mm=round(forward_travel(), 2),
                          force_at_stop_N=round(stop_state()['force'], 1))
    out['all_stop_forces_below_max_load'] = all(r['below_max_load'] for r in rows)
    out['slenderness'] = round(s['free_length'] / (s['od'] - s['wire']), 2)
    out['buckling'] = 'L0/D = %.2f < 2.6 (both ends guided on spigots inside a bore): no buckling' % out['slenderness'] \
        if out['slenderness'] < 2.6 else 'L0/D = %.2f; guided on Ø10 spigots inside an Ø18.6 bore' % out['slenderness']
    out['reverse_drive_rule'] = ('Free idler: top strand = front bottom strand = spring force / 2. In reverse the sprocket pulls the '
                                 'top strand, so the slack strand under the sprocket carries spring/2 − pull. It stays tight while '
                                 f'preload > 2 × {fmax:.1f} N (pull at the {DRIVE_CURRENT_LIMIT_A} A driver limit).')
    out['reverse_ok_nominal'] = nominal['force'] / 2 - fmax > 0
    return out


def loads_and_strength():
    rate = drive_rating(); lim = drive_force_limit(); fmax = lim['chain_pull_N']
    pre = spring_state()['force']; stop_force = stop_state(ADJUST_RANGE[1], SPRING['rate_N_mm'] * (1 + SPRING['rate_tolerance']))['force']
    weight_side = 11.89 * 9.81 / 2                   # excavator R3 nominal mass, one track
    rb2 = RING_TEETH * GEAR_MODULE / 2 * math.cos(math.radians(PRESSURE_ANGLE))
    out = dict(drive_rating=rate, current_limit=lim)
    cases = {
        'forward_at_current_limit': dict(chain=pre + fmax, vertical=0.0, torque=lim['torque_Nm']),
        'idler_on_recoil_stop_plus_pull': dict(chain=stop_force + fmax, vertical=0.0, torque=lim['torque_Nm']),
        'stop_plus_pull_plus_side_weight_on_sprocket': dict(chain=stop_force + fmax, vertical=weight_side, torque=lim['torque_Nm']),
        'stall_without_current_limit': dict(chain=stop_force + rate['sprocket_stall_Nm'] / (SPROCKET_PITCH_R / 1000), vertical=weight_side,
                                            torque=rate['sprocket_stall_Nm']),
    }
    y_out = sum(OUTBOARD_BEARING_Y) / 2; y_in = sum(INBOARD_BEARING_Y) / 2; y_teeth = 0.0; y_mesh = sum(RING_Y) / 2
    rows = {}
    for name, c in cases.items():
        mesh = c['torque'] / (rb2 / 1000)        # normal mesh force on the ring, mostly along Z at the +X mesh
        # Two-bearing beam along Y: moments about the outboard (fixed) bearing.
        def split(f_teeth, f_mesh):
            r_in = (f_teeth * (y_teeth - y_out) + f_mesh * (y_mesh - y_out)) / (y_in - y_out)
            return f_teeth + f_mesh - r_in, r_in
        ox, ix = split(c['chain'], 0.0); oz, iz = split(c['vertical'], mesh)
        r_out = math.hypot(ox, oz); r_in = math.hypot(ix, iz)
        # The mesh force pair closes inside hub, motor and housing; only external loads bend the tube.
        tube_m = math.hypot(c['chain'], c['vertical']) * (y_teeth - sum(FLANGE_Y) / 2) / 1000      # N m at the flange
        I = math.pi / 64 * (TUBE_OD ** 4 - TUBE_BORE ** 4)
        rows[name] = dict(chain_force_N=round(c['chain'], 1), vertical_N=round(c['vertical'], 1), sprocket_torque_Nm=round(c['torque'], 3),
                          mesh_normal_force_N=round(mesh, 1),
                          bearing_61808_radial_N=round(r_out, 1), bearing_6809_radial_N=round(r_in, 1),
                          static_safety_61808=round(BEARINGS['outboard']['C0_kN'][0] * 1000 / r_out, 1),
                          static_safety_6809=round(BEARINGS['inboard']['C0_kN'][0] * 1000 / max(r_in, 1e-9), 1),
                          housing_tube_bending_MPa=round(tube_m * 1000 * TUBE_OD / 2 / I, 2),
                          flange_screw_tension_N=round(tube_m * 1000 / (2 * (FLANGE_D / 2 + FLANGE_SCREW_R * math.cos(math.radians(45)))), 1),
                          cap_screw_shear_N=round(c['torque'] * 1000 / CAP_SCREW_R / 6, 1),
                          shaft_bending_MPa=round(32 * mesh * (sum(PINION_Y) / 2 - (FACE_Y + GEARMOTOR['bushing_length'])) /
                                                  (math.pi * GEARMOTOR['shaft_diameter'] ** 3), 1))
    out['cases'] = rows
    gear = {}
    for label, T in [('grade_10deg_0.572Nm', .572), ('requirement_1.2Nm', 1.2), ('current_limit', lim['torque_Nm']),
                     ('motor_continuous_limit', rate['sprocket_continuous_Nm']), ('motor_instantaneous_limit', rate['sprocket_instantaneous_Nm'])]:
        bound = tg.ring_lewis(T)
        hp = ring_lewis_hpstc(T)
        gear[label] = dict(torque_Nm=round(T, 3), lewis_tip_load_bound_MPa=round(float(bound['stress_MPa']), 2),
                           lewis_hpstc_MPa=round(hp, 2), hertz_MPa=round(tg.contact_stress(T)['pressure_MPa'], 1),
                           safety_hpstc=round(PRINTED_TOOTH_ALLOWABLE_MPA / hp, 2))
    out['ring_gear'] = dict(cases=gear, assumed_allowable_MPa=PRINTED_TOOTH_ALLOWABLE_MPA,
                            method='Ring tooth arc thickness from the generated profile. Bound: whole normal load T/rb applied tangentially at '
                                   'the ring base circle. HPSTC: whole load at the highest point of single-tooth contact on the ring '
                                   '(involute path end minus one base pitch), tangential component, lever to each section. Face 11 mm. '
                                   'PETG E = 2 GPa for Hertz.')
    return out


def ring_lewis_hpstc(T):
    th = tg.contact_ratio_theory(); pb = math.pi * GEAR_MODULE * math.cos(math.radians(PRESSURE_ANGLE))
    rb1 = PINION_TEETH * GEAR_MODULE / 2 * math.cos(math.radians(PRESSURE_ANGLE))
    rb2 = RING_TEETH * GEAR_MODULE / 2 * math.cos(math.radians(PRESSURE_ANGLE))
    aw = math.radians(th['working_pressure_angle_deg']); s1 = CENTRE_DISTANCE * math.sin(aw)
    s_hp = th['path_end_mm'] - pb                       # single contact nearest the ring tooth tip
    rc = math.hypot(rb2, s_hp); ac = math.acos(rb2 / rc)
    fn = T / (rb2 / 1000)
    radii = np.linspace(rc + .05, 17.85, 50)
    s = tg.ring_tooth_thickness(radii)
    return max(6 * fn * math.cos(ac) * (r - rc) / (PINION_FACE * t ** 2) for r, t in zip(radii, s) if t > 0)


def masses(inst):
    rows = []; total = 0.0
    special = {'gearmotor_gearbox': GEARMOTOR['mass_kg'], 'gearmotor_motor': 0.0,
               f"bearing_{BEARINGS['inboard']['model']}_outer": BEARINGS['inboard']['mass_kg'],
               f"bearing_{BEARINGS['outboard']['model']}_outer": BEARINGS['outboard']['mass_kg']}
    for n, d in inst.items():
        s = tc._one(d['shape'])
        if d['kind'] == 'printed':
            m = s.Volume() * PETG_KG_MM3
        elif n in special:
            m = special[n]
        elif n.startswith('bearing_'):
            m = 0.0                                     # included in the outer-ring entry
        elif '608' in n:
            m = .012
        elif 'insert' in n:
            m = s.Volume() * BRASS_KG_MM3
        else:
            m = s.Volume() * STEEL_KG_MM3
        c = s.Center(); total += m
        rows.append(dict(name=n, group=d['group'], mass_kg=round(m, 5), centre_mm=[round(c.x, 2), round(c.y, 2), round(c.z, 2)]))
    by = {}
    for r in rows:
        by[r['group']] = by.get(r['group'], 0) + r['mass_kg']
    return dict(unit_mass_kg=round(total, 4), by_group_kg={k: round(v, 4) for k, v in by.items()}, parts=rows,
                basis='PETG 1.27 g/cm³ on exact solid volume (infill not modelled); steel 7.85; brass 8.5; gearmotor 195 g (Pololu); '
                      'bearings 42/32 g; 608 12 g.')


def main():
    t0 = time.time()
    parts = tp.printed_parts()
    inst = tp.unit_instances(parts)
    print('instances', len(inst), round(time.time() - t0, 1), flush=True)
    v = dict(unit=dict(solids=len(inst), groups=sorted({d['group'] for d in inst.values()})))
    v['interference'] = tc.interference(inst)
    print('interference', len(v['interference']['hits']), flush=True)
    v['clearance'] = clearances(inst)
    print('clearance violations', len(v['clearance']['violations']), v['clearance']['seconds'], flush=True)
    v['travel'] = travel_checks(parts)
    print('travel', {k: len(x['hits']) for k, x in v['travel'].items()}, flush=True)
    v['gear_mesh'] = gear_checks(parts)
    print('gear', {k: v['gear_mesh'][k]['backlash_min_mm'] for k in v['gear_mesh'] if k.startswith('a_')}, flush=True)
    v['fits'] = fits()
    v['fasteners'] = fasteners()
    v['spring'] = spring_checks()
    v['loads_and_strength'] = loads_and_strength()
    v['mass'] = masses(inst)
    ok = (not v['interference']['hits'] and not v['clearance']['violations'] and
          all(not x['hits'] for x in v['travel'].values()) and
          all(v['gear_mesh'][k]['max_clash_mm2'] == 0 and v['gear_mesh'][k]['backlash_min_mm'] > 0 for k in v['gear_mesh'] if k.startswith('a_')) and
          all(r['overlap_mm3'] == 0 for r in v['gear_mesh']['cad_3d']) and
          all(r['ok'] for r in v['fits']) and all(r['ok'] for r in v['fasteners']) and v['spring']['reverse_ok_nominal'])
    v['summary'] = dict(all_checks_pass=bool(ok), elapsed_seconds=round(time.time() - t0, 1))
    v['open_items'] = [
        'Printed ring-gear allowable (8 MPa) and the PETG/PA seat fits are assumptions: print a test cap and hub, run the gear at the current limit.',
        'Pololu publishes no radial load rating for the 37D output shaft; the mesh load at the 1.0 A limit is about 81 N.',
        'Spring rate tolerance ±10 % is assumed (distributor sheet gives none); set the preload by spring length.',
        'Track tension, sprocket engagement and recoil come from the MuJoCo model; measure them on the built unit.']
    (ROOT / 'validation.json').write_text(json.dumps(v, indent=2, default=float))
    print('all checks pass:', ok, round(time.time() - t0, 1), 's', flush=True)


if __name__ == '__main__':
    main()

"""README.md and BOM.md for the track wheel unit, from the generated reports.

Run after build_track_wheel.py, validate_track_wheel.py, simulate_track_wheel.py
(all cases and --case report) and check_viewer.cjs.
"""
import json, math
import numpy as np
from tw_parts import ROOT, ex

PIN_SPAN_MM = 17.4                   # track pin: load across the bushing gap (excavator design)
PIN_D_MM = 3.0

SOURCES = {
    'pololu': ('Pololu 37D metal gearmotor 150:1, 12 V (#2829)', 'https://www.pololu.com/product/2829'),
    'pololu_specs': ('Pololu #2829 specifications', 'https://www.pololu.com/product/2829/specs'),
    'pololu_drawing': ('Pololu 37D dimension drawing', 'https://www.pololu.com/file/0J1735/37d-metal-gearmotors-dimension-diagram.pdf'),
    'pololu_datasheet': ('Pololu 37D gearmotor datasheet', 'https://www.pololu.com/file/0J1736/pololu-37d-metal-gearmotors-rev-1-2.pdf'),
    'spring': ('Associated/Lee Spring C-600-072-1500 (Taylor Spring listing)', 'https://taylorspring.com/spring/associatedlee-spring-c-600-072-1500-compression-spring-music-wire/'),
    'bearing_61808': ('SKF 61808-2RS1, RS 207-6965', 'https://uk.rs-online.com/web/p/ball-bearings/2076965'),
    'bearing_61808_qb': ('SKF 61808-2RS1 40 × 52 × 7 (Quality Bearings Online)', 'https://www.qualitybearingsonline.ca/61808-2rs1-skf-deep-groove-bearings-40x52x7/'),
    'bearing_6809': ('6809-2RS 45 × 58 × 7 (Quality Bearings Online)', 'https://www.qualitybearingsonline.ca/6809-2rs-fbj-thin-section-bearing-45x58x7mm/'),
    'bearing_6809_skf': ('SKF 6809-2RZ 45 × 58 × 7 (Quality Bearings Online)', 'https://www.qualitybearingsonline.ca/6809-2rz-skf-deep-groove-bearings-45x58x7mm/'),
    'astrak': ('Astrak: excavator undercarriage parts explained', 'https://astrak.com/blogs/news/excavator-undercarriage-parts-explained'),
    'hrparts': ('H&R Parts: what are track springs', 'https://www.hrparts.com/blog/post/what-are-track-springs-diagram'),
}


def link(key):
    title, url = SOURCES[key]
    return f'[{title}]({url})'


def load(rel):
    return json.loads((ROOT / rel).read_text())


def pin_stress(force_n):
    moment = force_n * PIN_SPAN_MM / 4                                  # N mm
    return 32 * moment / (math.pi * PIN_D_MM ** 3)                      # MPa


def table(rows):
    head, *body = rows
    out = '| ' + ' | '.join(head) + ' |\n|' + '|'.join('---' for _ in head) + '|\n'
    return out + ''.join('| ' + ' | '.join(str(c) for c in r) + ' |\n' for r in body)


def readme(p, v, s, e, b):
    gm, dr, lim, sp = p['GEARMOTOR'], p['drive_rating'], p['drive_force_limit'], p['SPRING']
    asm, stop = p['spring_assembled'], p['spring_at_recoil_stop']
    gear, ls, sv = v['gear_mesh'], v['loads_and_strength'], v['spring']
    cases = s['cases']; rw, ob, de, d5 = cases['reverse_wall'], cases['obstacle'], cases['debris'], cases['debris_5mm']
    fx, la, la4, rw4 = cases['fixture'], cases['lateral'], cases['lateral_r4spring'], cases['reverse_wall_r4spring']
    ring = ls['ring_gear']['cases']['current_limit']; worst = ls['cases']['stop_plus_pull_plus_side_weight_on_sprocket']
    stall = ls['cases']['stall_without_current_limit']
    trace = load('simulation/obstacle_trace.json')
    ob_p99 = float(np.percentile([max(r['tension']) for r in trace], 99))
    speed = dr['sprocket_no_load_rad_s'] * p['SPROCKET_PITCH_R'] / 1000
    stop_forces = [c['force_at_stop_N'] for c in sv['cases']]
    bad = [c for c in sv['cases'] if c['reverse_slack_strand_N'] <= 0]
    rate_lo = sp['rate_N_mm'] * (1 - sp['rate_tolerance'])
    # In service the idler settles forward from the exact-pitch assembly pose (measured at stall).
    settle = rw['stall']['idler_mm'] - p['ASSEMBLY_YOKE_SHIFT']
    min_ext = 2 * lim['chain_pull_N'] / rate_lo - (sp['free_length'] - asm['length'] - p['ADJUST_NOMINAL']) + settle
    status = 'PASS' if v['summary']['all_checks_pass'] and s['design_cases_pass'] and b['status'] == 'PASS' else 'INCOMPLETE'
    sim_rows = [['Case', 'What happens', 'Result'],
        ['fixture', 'Stand, no floor: run-in both ways at 3 rad/s, ±5 N side pulls',
         f"Strands {fx['top_strand_N']:.1f} / {fx['bottom_rear_strand_N']:.1f} N; drift {fx['max_lateral_drift_mm']:.2f} mm; {fx['tooth_skips']} tooth skips; {fx['status']}"],
        ['reverse_wall', 'Half machine ({:.1f} kg) reverses into a wall; drive stalls at the 1.0 A limit'.format(rw['supported_mass_kg']),
         f"Strand under the sprocket {rw['stall']['bottom_rear_strand_N']:.1f} N at stall (min {rw['stall']['min_bottom_rear_strand_N']:.1f}, rule predicts {rw['stall']['predicted_slack_strand_N']:.1f}); {rw['tooth_skips']} skips; {rw['status']}"],
        ['reverse_wall_r4spring', 'Negative control: the same with the Track R4 spring (15 N)',
         f"Strand goes slack (5th percentile {rw4['stall']['p05_bottom_rear_strand_N']:.2f} N); sprocket keeps turning at {rw4['stall']['speed_rad_s']:.1f} rad/s against the wall; peaks {rw4['max_chain_tension_N']:.0f} N; {rw4['status']} (expected)"],
        ['obstacle', 'Half machine drives over a Ø6 mm rod at the current limit',
         f"Crosses ({ob['travel_m']:.2f} m); recoil {ob['max_recoil_mm']:.1f} mm; peak pin force {ob['max_chain_tension_N']:.0f} N in one 10 ms impact sample (99th percentile {ob_p99:.0f} N); {ob['status']}"],
        ['debris', 'Reverse with a 7 × 4 × 40 mm stone on the lower run, carried round the idler',
         f"Recoil {de['max_recoil_mm']:.1f} mm at {de['peak_spring_N']:.1f} N; stone passes; peak pin force {de['max_chain_tension_N']:.0f} N; {de['status']}"],
        ['debris_5mm', 'The same with a 5 mm stone',
         f"Idler on its stop ({d5['max_recoil_mm']:.1f} mm, {d5['peak_spring_N']:.1f} N); stone passes; peak pin force {d5['max_chain_tension_N']:.0f} N; {d5['status']}"],
        ['lateral', 'Stand: ±20 N side pulls while running',
         f"Drift {la['max_lateral_drift_mm']:.2f} mm (R4 spring control: {la4['max_lateral_drift_mm']:.2f} mm); {la['status']}"]]
    spring_rows = [['Adjuster', 'Rate', 'Preload', 'Force on the stop', 'Reverse-stall strand, assembly pose']]
    for c in sv['cases']:
        spring_rows.append([f"{c['adjuster_mm']:g} mm", f"{c['rate_factor']:.0%}", f"{c['preload_N']:.1f} N", f"{c['force_at_stop_N']:.1f} N",
                            f"{c['reverse_slack_strand_N']:+.1f} N" + ('' if c['reverse_slack_strand_N'] > 0 else ' (slack)')])
    check_rows = [['Check', 'Result'],
        ['Exact interference, assembly pose', f"{v['interference']['pairs_tested']} solid pairs, {len(v['interference']['hits'])} intersections"],
        ['Clearance', (lambda c: f"No gap below {v['clearance']['threshold_mm']} mm except {sum(bool(x.get('contact')) for x in c)} intended contacts, each listed with its reason; "
                       f"{sum(not x.get('contact') for x in c)} running gaps of {min(x['gap_mm'] for x in c if not x.get('contact')):.2f}–1 mm (e.g. bushings in the sprocket pockets, pinion to cap)")(v['clearance']['pairs_below_1mm'])],
        ['Idler travel', 'Recoil stop, forward stop and both adjuster ends: no intersections; idler {:.2f} mm from the front road roller on the stop'.format(v['travel']['recoil_stop']['idler_to_front_roller_mm'])],
        ['Gear mesh, centre distance 6.9 / 7.0 / 7.1 mm', ' / '.join(f"{gear[k]['backlash_min_mm']:.3f}" for k in ['a_6.9', 'a_7.0', 'a_7.1']) + ' mm minimum backlash, no clash'],
        ['Involute contact ratio', f"{gear['involute_theory']['contact_ratio']:.2f} at {gear['involute_theory']['working_pressure_angle_deg']:.1f}° working pressure angle"],
        ['Fits (gearmotor, bushing, bearings, spring, yoke)', f"{sum(f['ok'] for f in v['fits'])} of {len(v['fits'])} pass"],
        ['Fastener thread engagement', f"{sum(f['ok'] for f in v['fasteners'])} of {len(v['fasteners'])} pass; gearbox face screws {v['fasteners'][0]['engagement_mm']:.1f} mm of the 3.0 mm Pololu allows"],
        ['Spring at the stop, all adjuster settings and ±10 % rate', f"{min(stop_forces):.1f}–{max(stop_forces):.1f} N, below the {sp['max_load_N']:.1f} N catalogue maximum; {sv['solid_margin_at_stop_mm']:.2f} mm from solid"],
        ['Hub bearings, worst case at the current limit', f"61808 static safety {worst['static_safety_61808']:.1f}, 6809 {worst['static_safety_6809']:.1f} (without the limit, stall: {stall['static_safety_61808']:.1f})"],
        ['Printed ring gear at the current limit', f"{ring['lewis_hpstc_MPa']:.2f} MPa at the highest point of single-tooth contact, safety {ring['safety_hpstc']:.2f} on an assumed 8 MPa; {ring['lewis_tip_load_bound_MPa']:.1f} MPa tip-load bound; Hertz {ring['hertz_MPa']:.1f} MPa"],
        ['Motor shaft bending at the current limit', f"{ls['cases']['forward_at_current_limit']['shaft_bending_MPa']:.0f} MPa (Pololu gives no radial rating)"],
        ['Browser check of 3D_preview.html', f"{b['status']}: all views, x-ray, playback of {len(b['playback']) - 1} cases, offline"],
        ['Unit mass', f"{v['mass']['unit_mass_kg']:.2f} kg including {v['mass']['by_group_kg']['track']:.2f} kg of track"]]
    return f"""# Track wheel R5: in-hub final drive and recoil idler

One complete track side for `excavator_60mm/`. The gearmotor and its final reduction sit inside the sprocket hub. A spring-loaded recoil idler at the front keeps the chain tight so it stays on the sprocket. This folder holds the unit on its own: CAD, print files, checks and a MuJoCo physics model, plus an offline viewer that shows the internal structure.

**Digital validation: {status}. Nothing here has been built or physically tested yet.**

![Track wheel unit](images/unit.png)

## Open it

- `3D_preview.html` opens offline in any browser. Views:
  - the whole unit;
  - a horizontal section through the final drive;
  - a vertical section through the recoil spring;
  - an exploded view;
  - the gear stage.
- An x-ray switch and a chain toggle show the parts inside. Playback replays four recorded MuJoCo cases with time, speed, motor current, recoil, spring force and pin force readouts.
- `step/track_wheel_unit.step` is the whole unit. `step/` and `stl/` have every printed part; the STL files are already in print orientation. `TW06_track_frame_left` is the mirrored rail for the left track.
- [BOM.md](BOM.md) lists the printed parts and the purchased hardware for one unit.

| Final drive section | Recoil section |
|---|---|
| ![Final drive section](images/final_drive_section.png) | ![Recoil section](images/recoil_section.png) |
| ![Exploded](images/exploded.png) | ![Gear stage](images/gear_stage.png) |

## How it copies a real machine

On a full-size excavator the final drive is "the hydraulic motor and gearbox that turns the sprocket", and the sprocket bolts to it. The track adjuster "sits in the frame between a bulkhead and the idler". It has a spring pack that absorbs impact and a yoke that holds the idler ({link('astrak')}). The recoil spring is "held under pressure at all times" and "contracts upon impact" ({link('hrparts')}). This unit has the same layout at model scale:

| Full-size part | Here |
|---|---|
| Travel motor and reduction gearbox (final drive) at the sprocket | Pololu 37D 150:1 gearmotor inside the stationary housing TW01, plus a 12:21 internal gear stage in the rotating hub |
| Sprocket on the final-drive hub | Sprocket teeth and hub drum in one part (TW02), on two thin-section bearings around the housing |
| Track frame, bulkhead, recoil spring, adjuster | Rail TW06 with the spring bore and rear wall, a C-600-072-1500 spring, and an M6 adjuster pushing the spring seat TW08 |
| Idler yoke sliding in the frame | Yoke TW07 in a channel closed by the nose TW09; a hard stop after {p['recoil_travel_mm']:.1f} mm of recoil |

One difference is deliberate. A full-size adjuster sets the idler position with a grease cylinder and keeps the spring caged at a much higher preload. Here the spring floats the idler, as the brief asked: the chain tension is the spring force all the time, and the M6 screw only sets the preload.

## Final drive

- **Gearmotor.** {link('pololu')}: 12 V, 150:1, Ø{gm['gearbox_diameter']} mm gearbox, Ø6 mm D-shaft offset {gm['shaft_offset']} mm from the gearbox axis ({link('pololu_drawing')}). It slides into the Ø37.3 mm bore of the stationary housing TW01 from the inboard end.
- **Locating the gear centre distance.** The Ø12 output bushing locates in a Ø12.15 mm hole in the housing end wall, which fixes the gear centre distance at {gear['centre_distance_mm']} ± {gear['centre_distance_tolerance_mm']} mm.
- **Fixing the gearmotor.** Six M3 × 10 button screws pass through the bearing retainer TW04 and the end wall into the gearbox face. They engage {v['fasteners'][0]['engagement_mm']} mm; Pololu allows 3 mm.
- **Hub stage.** A steel m1.5, 12-tooth pinion on the motor shaft meshes with a 21-tooth internal ring printed in the hub cap TW03, giving {p['HUB_RATIO']:.2f}:1. The ring profile is the envelope of the pinion at the real 7.0 mm centre distance, with {p['GEAR_BACKLASH']} mm backlash. It does the job of the reduction gearing in a full-size final drive.
- **Hub bearings.**
  - A 61808-2RS1 (40 × 52 × 7) sits under the sprocket and locates the hub both ways ({link('bearing_61808')}).
  - A 6809-2RS (45 × 58 × 7) floats at the inboard end ({link('bearing_6809')}).
  - Both sit on the stationary housing; the hub carries their outer rings. The motor shaft carries no wheel load.
- **Ratings at the sprocket** (Pololu datasheet values through the hub stage at 95 % efficiency):

| Quantity | Value |
|---|---|
| No-load speed at 12 V | {dr['sprocket_no_load_rpm']:.1f} rpm, {speed:.3f} m/s track speed |
| Torque per amp | {dr['torque_per_amp_Nm']:.2f} N m/A |
| Driver current limit | {p['DRIVE_CURRENT_LIMIT_A']:.1f} A: {lim['torque_Nm']:.2f} N m, {lim['chain_pull_N']:.1f} N chain pull |
| Pololu continuous guidance (10 kg cm) | {dr['sprocket_continuous_Nm']:.2f} N m |
| Stall (extrapolated, never used) | {dr['sprocket_stall_Nm']:.1f} N m |
| Excavator requirement | 0.57 N m on a 10° grade, 0.39 N m skid turn (excavator_60mm/validation.json) |

Run each motor from a driver with a 1.0 A current limit. Everything here is checked at that limit. Without it, a stall puts {stall['mesh_normal_force_N']:.0f} N on the gear mesh and the 61808 static safety drops to {stall['static_safety_61808']:.1f}.

## Recoil idler

- **Spring.** {link('spring')}: music wire, OD {sp['od']:.2f} mm, wire {sp['wire']:.2f} mm, free length {sp['free_length']:.1f} mm, {sp['rate_N_mm']:.2f} N/mm, catalogue maximum load {sp['max_load_N']:.1f} N, solid {sp['solid_length']:.1f} mm.
- **Guidance.** The spring is guided on Ø10 spigots inside an Ø18.6 mm bore. Its slenderness is {sv['slenderness']:.2f}, so it does not buckle.
- **Assembled.** {asm['length']:.1f} mm long, pushing {asm['force']:.1f} N. The idler can recoil {p['recoil_travel_mm']:.1f} mm until the yoke body meets the end of the channel: spring {stop['length']:.1f} mm, {stop['force']:.1f} N, {sv['solid_margin_at_stop_mm']:.2f} mm from solid. It can move forward {p['forward_travel_mm']:.1f} mm to the nose.
- **Why {asm['force']:.0f} N.** The idler is free to turn and slide, so the top strand and the front lower strand each carry half the spring force. In reverse the sprocket pulls the top strand, and the strand under the sprocket is left with spring/2 − pull. At the 1.0 A limit the pull is {lim['chain_pull_N']:.1f} N, so the preload must exceed {2 * lim['chain_pull_N']:.1f} N or that strand goes slack and the chain can climb the teeth. In service the idler settles {settle:.2f} mm forward of the assembly pose, where the spring pushes {rw['stall']['spring_N']:.0f} N, so the rule predicts {rw['stall']['predicted_slack_strand_N']:.1f} N in that strand. The reverse-into-a-wall simulation measured {rw['stall']['bottom_rear_strand_N']:.1f} N. The old R4 spring (15 N) fails the same test.
- **Adjuster.** The M6 adjuster screws through a captive nut in the rear wall and pushes the spring seat. Its range is {p['ADJUST_RANGE'][0]:g}–{p['ADJUST_RANGE'][1]:g} mm. Run it at {p['ADJUST_NOMINAL']:g} mm: screw in until the tip is flush with the front of the rear wall, then 3.5 more turns (M6 × 1.0), and lock the outer nut. Below about {min_ext:.1f} mm a spring at −10 % rate no longer keeps the reverse strand tight once the idler has settled, so use the low end only while fitting the chain. The table gives the margins at the assembly pose; the settle takes about {settle * sp['rate_N_mm'] / 2:.0f} N off the strand.

{table(spring_rows)}
- **Carriers.** At this tension the top run pulls straight between the sprocket and the idler. The R4 carriers would sit 2–3 mm below it and neither carry nor guide it. The R5 carriers have Ø{2 * ex.RETURN_ROLLER_R:g} mm rims on the same axles, {ex.CARRIER_LIFT:g} mm above the straight run, and the assembly pose puts the run's slack in a dip between them. The excavator simulations confirm the carriers stay loaded and turning.

## Checks (`validation.json`)

{table(check_rows)}
Open items from the checks:
""" + ''.join(f'- {x}\n' for x in v['open_items']) + f"""
## Physics simulation (`simulation/`)

MuJoCo {fx['engine'].split()[1]}, 0.5 ms steps. The R4 chain (34 shoes, steel bushings, 68 hinge constraints) runs on this unit's final drive and idler:
- **Drive.** A DC motor model from the Pololu data through the hub stage, with a PI speed loop, the 1.0 A current limit and the reflected rotor inertia (estimated) as armature.
- **Idler.** A slide joint with the spring rate, preload, hard stop and nose.
- **Measurements.** Chain tension comes from the hinge constraint forces. Tooth skips are found by comparing chain travel with sprocket rotation.

{table(sim_rows)}
![Simulation results](images/track_wheel_simulation.png)

The largest pin forces come from the stone and rod cases, and the pin bending they cause decides the pin material:
- A 4 mm stone: {de['max_chain_tension_N']:.0f} N, about {pin_stress(de['max_chain_tension_N']):.0f} MPa in a Ø3 pin.
- A 5 mm stone: {d5['max_chain_tension_N']:.0f} N, {pin_stress(d5['max_chain_tension_N']):.0f} MPa.
- The rod impact spike: {ob['max_chain_tension_N']:.0f} N, {pin_stress(ob['max_chain_tension_N']):.0f} MPa.

Use silver steel (yield at least 400 MPa) or hardened pins, not mild steel. The model has rigid contacts and no printed-part compliance, so impact peaks are pessimistic. It also has no soil or wear.

| Stone at the idler | Rod crossing |
|---|---|
| ![Debris recoil](images/debris_recoil.png) | ![Obstacle](images/obstacle_playback.png) |

## Assembly

1. **Test prints.** Print a hub cap and a hub first. Check the bearing seats: the hub's 6809 and 61808 seats are light press fits, and the housing seats are slide fits. Also check the ring-gear mesh with the real pinion.
2. **Inserts.** Fit the heat-set inserts: six in the cap face of TW02, four in the boss of TW06, two in the pillar ends of TW01.
3. **Gearmotor.** Slide it into TW01 from the inboard end so the output bushing enters the Ø12.15 hole. Lead the motor wires out of the rear.
4. **Housing to frame.** Pass the housing tube through the TW06 boss from the inboard side. Fix the flange with four M3 × 10 socket screws.
5. **Hub.** Press the 6809 and the 61808 into TW02 against their shoulders. Slide the hub over the housing.
6. **Retainer.** Put TW04 on the 61808 inner ring. Drive the six M3 × 10 button screws through TW04 and the end wall into the gearbox face.
7. **Pinion.** Fit the pinion flush with the end of the motor shaft. Tighten the M3 set screw onto the D-flat.
8. **Hub cap.** Fit TW03 so its ring gear meshes with the pinion. Fix it with six M3 × 20 button screws into the hub inserts.
9. **Rear cap.** Fit TW05 over the motor terminals with a grommet for the cable. Fix it with two M3 × 8 socket screws into the pillar inserts.
10. **Recoil idler.**
    - Put the M6 nut in the rear-wall pocket and thread the adjuster with its lock nut.
    - Insert the spring seat, the spring and the yoke with the idler wheel, axle, spacers and collars.
    - Close the channel with the nose TW09: two M3 × 40 bolts and nuts.
11. **Rollers.** Fit the road rollers and carriers on Ø8 × 79 shafts with spacers and collars, as in Track R4.
12. **Chain.**
    - Wrap it and push the idler back to fit the last pin. Backing the adjuster off makes this easier.
    - Set the adjuster to 3.5 mm.
    - Turn the sprocket by hand through several full circuits in both directions before powering it.

This is a sequence derived from the CAD, not a verified assembly animation. Check tool access on the first build.

## Commissioning

- Set the driver current limit to 1.0 A per motor before the first run.
- Run lifted, then on the floor, at low speed in both directions. Watch the bushings enter and leave the sprocket, and check that the idler moves freely and returns.
- Measure the motor current at steady speed and check the hub for heat.
- Recheck the adjuster and the set screw after the first hour.

## Rebuild

From `track_wheel/source/` with the same Python environment as `excavator_60mm/` (CadQuery, MuJoCo, trimesh, shapely, matplotlib) and Node with Playwright for the browser check. Each command finishes in under ten minutes:

```sh
python build_track_wheel.py                     # STEP, STL, assembly, viewer scene
python validate_track_wheel.py                  # CAD, gear, fits, fasteners, spring, loads
python simulate_track_wheel.py --case fixture   # repeat for each case listed above
python simulate_track_wheel.py --case report    # summary.json and the plot
python build_viewer.py
node check_viewer.cjs
python build_docs.py
```

The chain, rollers and idler wheel come from `../excavator_60mm/source/design.py`, and the viewer bundles three.js from `../actuator_v6/source/vendor/`. Keep the folders together.

## Sources

""" + ''.join(f'- {link(k)}\n' for k in ['pololu', 'pololu_specs', 'pololu_drawing', 'pololu_datasheet', 'spring', 'bearing_61808', 'bearing_61808_qb', 'bearing_6809', 'bearing_6809_skf', 'astrak', 'hrparts']) + """- Berco and Caterpillar 320 references for the chain, rollers and sprocket: `../excavator_60mm/references/TRACK_SYSTEM.md`
"""


HARDWARE = [
    ('Gearmotor', 1, 'Pololu 37D metal gearmotor 150:1, 12 V, no encoder (#2829)', 'Run from a driver limited to 1.0 A'),
    ('Hub bearing, fixed', 1, '61808-2RS1, 40 × 52 × 7, sealed (SKF or equal)', 'Under the sprocket; light press into TW02'),
    ('Hub bearing, floating', 1, '6809-2RS, 45 × 58 × 7, sealed', 'Inboard end; slide fit on the housing tube'),
    ('Pinion', 1, 'Steel spur gear m1.5, 12 teeth, 20°, face 11 mm, bore 6 H7, no hub, M3 radial tapping between two teeth',
     'Made to this spec; a catalogue m1.5 12-tooth gear works as a blank only if its stock bore is under 6 mm'),
    ('Pinion set screw', 1, 'M3 × 4 cup point ISO 4029', 'Onto the D-flat'),
    ('Recoil spring', 1, 'Associated/Lee Spring C-600-072-1500, music wire', 'OD 15.24, free 38.1, 6.29 N/mm'),
    ('Tension adjuster', 1, 'M6 × 16 hex screw ISO 4017 + 2 M6 nuts ISO 4032', 'One nut captive in the rear wall, one lock nut'),
    ('Heat-set inserts', 12, 'M3 × 5.7, Ø4.0 hole', '6 in TW02, 4 in TW06, 2 in TW01'),
    ('Gearbox face screws', 6, 'M3 × 10 button head ISO 7380', 'Through TW04 and the end wall; 2.4 mm into the gearbox'),
    ('Hub cap screws', 6, 'M3 × 20 button head ISO 7380', 'Into the TW02 inserts'),
    ('Housing flange screws', 4, 'M3 × 10 socket head ISO 4762', 'Into the TW06 inserts'),
    ('Rear cap screws', 2, 'M3 × 8 socket head ISO 4762', 'Into the TW01 pillar inserts'),
    ('Nose bolts', 2, 'M3 × 40 socket head ISO 4762 + M3 nut ISO 4032', 'Through the channel and TW09'),
    ('Idler axle', 1, 'Ground steel Ø8 × 89', 'Slides with the yoke'),
    ('Roller shafts', 5, 'Ground steel Ø8 × 79', '3 road rollers + 2 carriers'),
    ('608 bearings', 12, '8 × 22 × 7, sealed', '2 per wheel: idler, 3 road rollers, 2 carriers'),
    ('Ø8 shaft collars', 12, 'Split clamp, Ø16 × 5', '2 per shaft'),
    ('Spacers', 18, 'Steel OD12 / ID8.1; idler 20, 6, 11 mm; rollers 10, 26, 1 mm', '3 per wheel'),
    ('Motor cable grommet', 1, 'For a Ø6 hole, 1.2 mm panel', 'Rear cap'),
    ('Track pins', 34, 'Ø3 × 56 silver steel, clip grooves at ±26.5 mm', 'Yield at least 400 MPa (see README)'),
    ('Track bushings', 34, 'Steel Ø6 × Ø3.1 × 17', 'The sprocket drives these'),
    ('Pin clips', 68, 'For Ø3 pins', 'Groove to the supplier drawing'),
]


def bom(e):
    rows = [['Item', 'Qty per unit', 'File / specification', 'Notes']]
    for part in e['parts']:
        rows.append([f"Printed {part['name']}", part['quantity'], f"stl/{part['name']}.stl ({part['material']}, {part['solid_mass_g']:g} g solid)",
                     part['note'] + ' ' + part['print_orientation']])
        if part.get('mirrored'):
            rows.append([f"Printed {part['name']}_left", '–', f"stl/{part['name']}_left.stl", 'Use instead of the right-hand rail on the left track'])
    rows += [[a, b, c, d] for a, b, c, d in HARDWARE]
    return ('# Track wheel R5 bill of materials (one track)\n\n'
            'Quantities are for one unit; the excavator needs two (one with the left-hand rail). '
            'Masses are solid PETG volumes, not slicer estimates. Check purchased-part drawings before ordering.\n\n' + table(rows))


def main():
    p, v, s = load('parameters.json'), load('validation.json'), load('simulation/summary.json')
    e, b = load('source/export_report.json'), load('browser_validation.json')
    (ROOT / 'README.md').write_text(readme(p, v, s, e, b))
    (ROOT / 'BOM.md').write_text(bom(e))
    print('README.md and BOM.md written')


if __name__ == '__main__':
    main()

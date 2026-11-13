"""The parts list of the complete X1 excavator, assembled from the subsystem BOMs (J9 x 2, X1, turntable, body, main board,
R12 with four V6-U60, B01X) and the harness (harness.py, W01). Writes ../BOM.md and ../BOM.csv.

Every line names the subsystem BOM it comes from, so a change there is found here. Quantities are for one machine.
"""
import csv
import json
import common as K
import harness as H

ROWS = []   # (group, part, qty, spec, source, note)


def add(group, part, qty, spec, source, note=''):
    ROWS.append(dict(group=group, part=part, qty=qty, spec=spec, source=source, note=note))


# ------------------------------------------------------------------ printed parts
P = 'Printed'
add(P, 'J901_H_frame', 1, 'PETG or PA12; outer wall face on the bed', 'J9/BOM.md', 'left track, revision F seats')
add(P, 'J901_H_frame_right', 1, 'mirrored print of J901', 'X1/BOM.md', 'right track')
add(P, 'J909_housing', 1, 'PETG, 3 walls; skirt inner face on the bed', 'J9/BOM.md', 'left track')
add(P, 'J909_housing_right', 1, 'mirrored print of J909', 'X1/BOM.md', 'right track')
add(P, 'J902_sprocket', 2, 'PETG or PA12, 5 walls, 50 %', 'J9/BOM.md', 'one per track')
add(P, 'J903_journal_plug', 2, 'PETG or PA12, 100 %', 'J9/BOM.md')
add(P, 'J904_roller', 14, 'PETG, 4 walls, 40 %', 'J9/BOM.md', '5 road + 2 support rollers per track')
add(P, 'J906_idler_wheel', 2, 'PETG, flat face on the bed (print as J8)', 'J9/BOM.md', 'both 608ZZ seats open to the faces')
add(P, 'J907_idler_spacer', 4, 'PETG, 100 %', 'J9/BOM.md')
add(P, 'J908_U_yoke', 2, 'PETG or PA12, 4 walls, 50 %', 'J9/BOM.md', 'with the spring piston')
add(P, 'J910_track_shoe_70', 68, 'PETG or PA12, grousers on the bed', 'J9/BOM.md', '34 per track')
add(P, 'X101_X_frame', 1, 'PETG or PA12; bearing seat on the bed; 155 x 275 x 51', 'X1/BOM.md', 'revision F')
add(P, 'X102_belly_cover', 1, 'PETG, 3 walls', 'X1/BOM.md')
add(P, 'T101_centre_frame', 1, 'PETG, 4 walls, 30 %; 252 x 148 x 33', 'X1/TURNTABLE.md')
add(P, 'T102_motor_slide', 1, 'PETG, 100 %', 'X1/TURNTABLE.md')
add(P, 'T103_drag_plunger', 2, 'PETG, 100 %', 'X1/TURNTABLE.md')
add(P, 'T104_hub_adapter', 1, 'PETG, 100 %', 'X1/TURNTABLE.md')
add(P, 'T105_pinion', 1, 'PETG or PA12, 100 %', 'X1/TURNTABLE.md', 'wears first: keep a spare')
add(P, 'X103_ring_gear', 1, 'PETG or PA12, 100 %', 'X1/TURNTABLE.md')
add(P, 'T106_rotor_dog_TPU', 1, 'TPU 95A', 'X1/TURNTABLE.md')
add(P, 'B101_counterweight', 1, 'PETG, 4 walls, 15 %; pause at 24.9 mm to pour the shot', 'X1/BODY.md')
add(P, 'B102_left_half', 1, 'PETG, 3 walls; on its left face. Rev B issue 2: harness notch in the inboard hood wall', 'X1/BODY.md')
add(P, 'B103_right_half', 1, 'PETG, 3 walls; tree supports under the rails and mirror. Rev B issue 2: harness notch', 'X1/BODY.md')
add(P, 'B104_cab_interior', 1, 'PETG (dark grey), 3 walls, 15 %', 'X1/BODY.md')
add(P, 'B105_operator', 1, 'PETG or PLA (orange); tree supports', 'X1/BODY.md')
add(P, 'B106_battery_hatch', 1, 'PETG, 3 walls; upside down', 'X1/BODY.md')
add(P, 'B107_left_handrail', 1, 'PETG (black), 100 %', 'X1/BODY.md')
add(P, 'B01X_boom_foot_bracket', 1, 'PETG, 6 perimeters + 10 % gyroid; plate down; 132 x 164 x 72; issue 3 with the cable troughs, slots and posts', 'excavator_complete (new)', 'replaces R12 B01')
add(P, 'B02_boom', 1, 'PETG, 6 perimeters + 10 %; on its side; needs a 410 mm bed or the split at S', 'R12/ASSEMBLY.md')
add(P, 'B03_stick', 1, 'PETG, 6 perimeters + 10 %; on its side', 'R12/ASSEMBLY.md')
add(P, 'B04_side_link', 2, 'PETG; L and R', 'R12/ASSEMBLY.md')
add(P, 'B05_H_link', 2, 'PETG; L and R', 'R12/ASSEMBLY.md')
add(P, 'B06_bucket', 1, 'PETG; supports inside the cavity', 'R12/ASSEMBLY.md', 'Cat bucket of US 8,201,350 at 1:15')
add(P, 'B07_tooth', 5, 'PETG; glued with CA', 'R12/ASSEMBLY.md')
add(P, 'B08_B_pad', 2, 'PETG; bonded to the boom on the B pin', 'R12/ASSEMBLY.md')
add(P, 'R12 pin spacers (A1, A2, C1, D1, F1, J1, R1, left and right)', 14, 'PETG tubes Ø7 on Ø3 pins', 'R12/ASSEMBLY.md pin stacks')
add(P, 'V6-U60 01_body', 4, 'PETG, front end down, 3 walls, 25 %; check the 1 mm partition prints solid', 'actuator_v6/BOM.md')
add(P, 'V6-U60 02_front_cap', 4, 'PETG, 4 walls, 40 %', 'actuator_v6/BOM.md')
add(P, 'V6-U60 03_rear_cap', 4, 'PETG, 4 walls, 60 %', 'actuator_v6/BOM.md')
add(P, 'V6-U60 04_rod', 4, 'PETG, 100 %', 'actuator_v6/BOM.md')
add(P, 'V6-U60 05_rod_eye', 4, 'PETG, 100 %', 'actuator_v6/BOM.md')
add(P, 'V6-U60 06_cable_clamp', 4, 'PETG, 100 %', 'actuator_v6/BOM.md')
add(P, 'V6 fit samples 08–11', 1, 'print once before the actuators; 10 and 11 try the M1 inserts, 10 also the rear-cap hook', 'actuator_v6/BOM.md')
n_clamps = len(H.clamps(None)) if False else 15
add(P, 'W01_cable_clamp', n_clamps + 3, 'PETG, 100 %; 8 x 7 x 5.5; glued with CA, the 3 mm sleeve snaps in', 'excavator_complete (new)', f'{n_clamps} fitted (6 boom left lane, 8 boom right lane, 1 stick) + 3 spare')

# ------------------------------------------------------------------ bought: motors, bearings, mechanical
B = 'Bought mechanical'
add(B, 'JGY-370-1260 12 V worm gear motor, 200:1, 30 rpm', 3, 'motor only, no bracket / speed controller', 'J9/BOM.md, X1/TURNTABLE.md', '2 tracks + swing')
add(B, 'Ø32 / Ø6 aluminium flange coupling (flange Ø32 x 4, 6 x M3 tapped on Ø23, boss Ø14 x 10)', 2, 'one M3 set screw supplied with each', 'J9/BOM.md', '2 sprockets; seller drawing in track_wheel_jgy370/references/flange_coupling_32')
add(B, 'Pololu #1999 universal mounting hub, 6 mm, M3', 1, 'sold in pairs: 1 pack. Could not be bought on 2026-11-12; a substitute must be no bigger: flange max Ø26 x 5.5, boss max Ø13, max 9.9 long, set screw in the flange', 'X1/TURNTABLE.md', 'swing pinion; set screws supplied')
add(B, 'THK RU66 cross-roller ring', 1, 'Ø35 bore, Ø95, 15 high (catalogue A18-20/21)', 'X1/BOM.md', 'see references/thk_ru66/SOURCE.md before substituting')
add(B, '6-way 2 A flanged slip ring', 1, 'Ø22 body, Ø44 flange, Ø7.8 rotor (seller drawing)', 'X1/TURNTABLE.md', 'rings 1-4 used')
add(B, 'N20 gearmotor 12 V 1:50 800 rpm with M4 x 0.7 leadscrew (100 mm stock)', 4, 'screw cut to 75 mm; otherwise unmodified', 'actuator_v6/BOM.md', 'V6-U60 drives')
add(B, 'V6-U60 end-stop board (PCBA, 76.4 x 8 mm)', 4, 'electronics/pcb/V6-U60; panelised with rails', 'actuator_v6/BOM.md', 'order a spare or two')
add(B, '6800ZZ bearing 10 x 19 x 5', 2, '', 'J9/BOM.md')
add(B, '624ZZ bearing 4 x 13 x 5', 28, '', 'J9/BOM.md')
add(B, '608ZZ bearing 8 x 22 x 7', 4, '', 'J9/BOM.md')
add(B, 'Ø8 x 55 steel pin (ISO 2338 8 m6)', 2, 'idler axles', 'J9/BOM.md')
add(B, 'Idler compression spring, Lee Spring C-600-072-1500', 2, '25.8 fitted, 77 N', 'J9/BOM.md')
add(B, 'Ø3 x 56 steel track pin', 68, '', 'J9/BOM.md')
add(B, 'Ø6 / Ø3.1 x 17 steel bushing', 68, '', 'J9/BOM.md')
add(B, 'Pin clip', 136, '', 'J9/BOM.md')
add(B, 'Ground steel pin Ø6 x 60', 1, 'pin O', 'R12 sheet 6')
add(B, 'Steel pin Ø6 x 42', 1, 'pin E', 'R12 sheet 6')
add(B, 'Steel pin Ø6 x 50', 1, 'pin H', 'R12 sheet 6')
add(B, 'Hardened pin Ø3 x 30', 2, 'pins A, pressed into B01X (2.9 mm bores)', 'R12 sheet 6')
add(B, 'Hardened pin Ø3 x 82', 1, 'pin B through the boom', 'R12 sheet 6')
add(B, 'Steel pin Ø3 x 34', 2, 'pins C, F', 'R12 sheet 6')
add(B, 'Steel pin Ø3 x 40', 1, 'pin D', 'R12 sheet 6')
add(B, 'Hardened pin Ø3 x 68', 2, 'pins J, R', 'R12 sheet 6')
add(B, 'Steel pin Ø3 x 58', 1, 'pin Q', 'R12 sheet 6')
add(B, 'Shaft collar Ø6 bore, Ø11 x 4, set screw', 6, 'O, E, H', 'R12 sheet 6')
add(B, 'Shaft collar Ø3 bore, Ø7 x 3, set screw', 16, 'A..Q', 'R12 sheet 6')
add(B, 'Shim washer Ø6 / Ø11 x 0.4 steel', 6, 'O, E, H', 'R12 sheet 6')
add(B, 'M4 thin hex nut, brass (ISO 4035), 7 AF x 2.2', 4, 'V6 rod carriers', 'actuator_v6/BOM.md')
add(B, 'NdFeB block magnet N35 3 x 2 x 2, magnetised through 2 mm', 4, 'V6 carriers', 'actuator_v6/BOM.md')
add(B, 'NdFeB disc magnet Ø6 x 2 (N42/N52)', 8, 'hatch and ledges', 'X1/BODY.md')
add(B, 'Steel shot (about 4.5 g/cm3), poured', '735 g', 'counterweight pocket, 286 g left / 449 g right', 'X1/BODY.md')
add(B, 'Felt Ø8 x 3', 2, 'drag pads', 'X1/TURNTABLE.md')
add(B, 'Spring Ø4.5 x 12, wire 0.5 (about 1.2 N/mm)', 2, 'drag pads', 'X1/TURNTABLE.md')
add(B, 'Keystone 1043 single 18650 holder (THM, PC pins)', 3, '77.05 x 20.65 x 14.86, Keystone drawing rev C; snaps into the hatch sled', 'CONNECTORS.md, X1/BODY.md')
add(B, 'Samsung INR18650-35E cell (or any 18650 up to 65.3 mm, flat or button top)', 3, '3S1P; unprotected is fine (BMS)', 'CONNECTORS.md, X1/BODY.md')
add(B, '3S 10 A Li-ion protection board HX-3S-01 (50 x 16)', 1, 'on the +Y sled wall with 1 mm VHB tape; charge through P+/P-', 'CONNECTORS.md')
add(B, 'Rocker switch KCD1-101 (SPST, 21.2 x 15.1 bezel, 19 x 13 cut-out)', 1, 'toolbox top', 'CONNECTORS.md')
add(B, 'Littelfuse MINI FHM in-line fuse holder 0FHM0001ZXJ + MINI blade fuse 5 A', 1, 'toolbox floor, VHB tape; 14 AWG leads spliced to 20 AWG', 'CONNECTORS.md')
add(B, '5.5 x 2.1 mm metal panel DC jack, M8 thread (DC-022B pattern)', 1, 'toolbox front, Ø8 hole, nut and lock washer outside; 12.6 V CC/CV charger', 'CONNECTORS.md')
add(B, 'VHB double-sided foam tape 1 mm', '0.1 m', 'BMS and fuse holder', 'CONNECTORS.md')
add(B, 'X1 main board rev B, 96 x 64, JLCPCB-assembled', 1, '132 parts; see main_board/BOM.md and fab/', 'X1/controller/main_board/BOM.md')
add(B, 'Thin CA glue / laminating epoxy', 1, 'shot lock, magnets, teeth, pads, clamps W01', 'X1/BODY.md, R12')

# ------------------------------------------------------------------ bought: screws, nuts, inserts
S = 'Screws, nuts, washers, inserts'
add(S, 'M1.6 x 4 countersunk, PH0 (DIN 965)', 8, 'V6 motor screws', 'actuator_v6/BOM.md')
add(S, 'M1 x 8 pan head, A2-70 stainless, PH000', 16, 'V6 front caps (8), V6 cable clamps (8)', 'actuator_v6/BOM.md')
add(S, 'M1 heat-set insert, 1.8 mm long x 2 mm knurl (M1 x 1.8 x 2)', 16, 'V6 bodies, both end faces', 'actuator_v6/BOM.md')
add(S, 'M2 x 10 pan head', 4, 'V6 rod eyes', 'actuator_v6/BOM.md')
add(S, 'M2.5 x 6 self-tapping', 4, 'main board to the bay bosses', 'X1/BODY.md')
add(S, 'M3 x 6 socket (ISO 4762)', 8, 'track motors to the inner walls', 'J9/BOM.md')
add(S, 'M3 x 8 button head (ISO 7380)', 12, 'track housings (8), swing motor (4)', 'J9/BOM.md, X1/TURNTABLE.md')
add(S, 'M3 x 8 socket (ISO 4762)', 3, 'slip ring to the collar', 'X1/TURNTABLE.md')
add(S, 'M3 x 8 countersunk (ISO 10642)', 4, 'belly cover', 'X1/BOM.md')
add(S, 'M3 x 10 socket', 4, 'pinion to the hub', 'X1/TURNTABLE.md')
add(S, 'M3 x 12 socket', 10, 'slide clamps (4), push screws (2), body halves (4)', 'X1/TURNTABLE.md, X1/BODY.md')
add(S, 'M3 x 12 countersunk (ISO 10642)', 6, 'ring gear from below', 'X1/TURNTABLE.md')
add(S, 'M3 x 20 socket', 6, 'sprockets to the couplings', 'J9/BOM.md')
add(S, 'M3 x 50 socket', 2, 'journal plugs', 'J9/BOM.md')
add(S, 'M3 nut', 2, 'push-screw locks', 'X1/TURNTABLE.md')
add(S, 'M3 washer (ISO 7089)', 7, 'slip ring (3), slide clamps (4)', 'X1/TURNTABLE.md')
add(S, 'M3 heat-set insert (hole Ø4.0 x 5.7)', 31, 'housings (8), belly cover (4), collar (3), ring gear (6), slide (4), lugs (2), rib tops (4)', 'J9, X1, TURNTABLE, BODY')
add(S, 'M4 x 12 socket', 2, 'counterweight', 'X1/BODY.md')
add(S, 'M4 x 20 socket', 8, 'hub joint', 'X1/TURNTABLE.md')
add(S, 'M4 x 25 socket, Ø7 x 4 head', 8, 'track joints, revision F', 'X1/BOM.md')
add(S, 'M4 x 30 socket', 8, 'RU66 to the X-frame', 'X1/BOM.md')
add(S, 'M4 x 70 socket', 14, 'roller axles', 'J9/BOM.md')
add(S, 'M4 nut (ISO 4032)', 16, 'RU66 seat (8), track joints (8)', 'X1/BOM.md')
add(S, 'M4 nyloc nut (DIN 985)', 14, 'roller axles', 'J9/BOM.md')
add(S, 'M4 washer Ø9 / Ø4.4 x 0.8', 16, 'track joints', 'X1/BOM.md')
add(S, 'DIN 6796 M4 conical spring washer', 16, 'RU66 seat (8), hub joint (8)', 'X1/BOM.md, X1/TURNTABLE.md')
add(S, 'DIN 9021 M4 washer Ø12', 16, 'RU66 seat (8), hub joint (8)', 'X1/BOM.md, X1/TURNTABLE.md')
add(S, 'M4 heat-set insert (hole Ø5.6 x 8.1)', 2, 'counterweight', 'X1/BODY.md')
add(S, 'M6 x 40 socket', 4, 'B01X to the T101 rib tops', 'X1/TURNTABLE.md')
add(S, 'M6 nut', 4, 'in the T101 pockets', 'X1/TURNTABLE.md')
add(S, 'M6 washer', 4, '', 'X1/TURNTABLE.md')
add(S, 'M6 x 8 set screw', 2, 'drag pads', 'X1/TURNTABLE.md')
add(S, 'M6 heat-set insert (Ø8 hole, 9 long)', 2, 'drag pads', 'X1/TURNTABLE.md')

# ------------------------------------------------------------------ harness
W = 'Harness and electrical'
add(W, 'JST XHP-2 housing + 2 x SXH-001T-P0.6 contacts', 5, 'boom L, boom R, stick, bucket, swing (mate the S2B-XH-A headers J103-J107)', 'CONNECTORS.md')
add(W, 'JST XHP-4 housing + 4 x SXH-001T-P0.6 contacts', 1, 'tracks via the slip ring (mates S4B-XH-A J102)', 'CONNECTORS.md')
add(W, 'JST PHR-3 housing + 3 x SPH-002T-P0.5S contacts', 1, 'lamps (mates S3B-PH-K-S J108)', 'CONNECTORS.md')
add(W, 'Amass XT30U-F cable female', 2, 'hatch lead end; 12 V link end onto the board\'s XT30PW-M', 'CONNECTORS.md')
add(W, 'Amass XT30U-M cable male', 1, 'feed socket hanging in the hood cavity (mates the hatch lead)', 'CONNECTORS.md')
add(W, 'JST SMR-02V-B receptacle housing + 2 x SYM-001T-P0.6 pin contacts', 3, 'two track joints in the carbody (stator side), toolbox lamp joint in the right bay (board side)', 'CONNECTORS.md')
add(W, 'JST SMP-02V-BC plug housing + 2 x SHF-001T-0.8BS socket contacts', 3, 'the motor-lead and lamp-lead sides of those joints', 'CONNECTORS.md')
add(W, 'Heat-shrink 1.2 mm', '0.2 m', 'over the V6 wires before the XH crimp (insulation Ø0.8 < 0.9 range)', 'CONNECTORS.md')
add(W, 'Silicone wire 26 AWG, red + black', '3 m', 'tracks, swing, lamps, roof-lamp feed', 'WIRING.md')
add(W, 'Silicone wire 20 AWG, red + black', '1 m', 'battery feed, 12 V link', 'WIRING.md')
add(W, 'Silicone wire 22 AWG', '0.2 m', 'charge jack', 'WIRING.md')
add(W, 'PTFE wire 28 AWG, 4 colours', '1.2 m', 'V6 internal and cable wires (W1-W4 x 4)', 'actuator_v6/BOM.md')
add(W, 'Silicone sleeve 3.0 mm OD x 2.0 mm bore', '2.2 m', 'V6 cables, cut lengths in harness.csv', 'WIRING.md')
add(W, 'Enamelled wire 0.2 mm', '0.6 m', 'roof lamps inside the cab', 'WIRING.md')
add(W, '3 mm white LED', 3, '2 roof lamps, 1 toolbox lamp', 'WIRING.md')
add(W, '100 R resistor, 1/4 W', 3, 'one per LED', 'WIRING.md')
add(W, '100 nF 50 V ceramic capacitor', 3, 'across each JGY-370 motor\'s tabs (brush noise)', 'WIRING.md')
add(W, 'Cable tie 2.5 x 100 mm', 16, 'B01X troughs (4), slots (2), posts (2), bay and hood slack (8)', 'WIRING.md')
add(W, 'Heat-shrink 2.4 and 4.8 mm', '0.5 m', 'joints and the slip-ring spare leads', 'WIRING.md')
add(W, 'Nut-holding tool, 7 mm, within Ø11.2', 1, 'track joint nuts', 'X1/ASSEMBLY.md', 'tool, not a part')
add(W, 'Hex L-keys 1.5, 2, 2.5 (90 mm long), 3 (20 mm short leg / 80 mm arm), 5 mm; PH0 driver with a 3 mm x 100 mm blade; PH1; PH000 precision driver', 1, 'see ASSEMBLY.md', 'subsystem guides', 'tools')


def main():
    groups = []
    for r in ROWS:
        if r['group'] not in groups:
            groups.append(r['group'])
    md = ['# Parts list of the complete X1 excavator', '',
          'One machine: two J9 tracks on the X1 revision F frame, the R3 turntable, body B1 rev B (issue 2), main board rev B, the R12 arm '
          'with four V6-U60 drives on B01X (issue 3), the harness of [WIRING.md](WIRING.md) and the connectors of [CONNECTORS.md](CONNECTORS.md). Generated by `source/build_bom.py`; '
          'the same rows are in [BOM.csv](BOM.csv). Each row names the subsystem BOM it is taken from; those BOMs stay authoritative '
          'for print settings and part sources.', '']
    counts = {}
    for g in groups:
        rows = [r for r in ROWS if r['group'] == g]
        n_lines = len(rows)
        n_pieces = sum(r['qty'] for r in rows if isinstance(r['qty'], int))
        counts[g] = (n_lines, n_pieces)
        md += [f'## {g}', '', f'{n_lines} lines' + (f', {n_pieces} pieces' if n_pieces else '') + '.', '',
               '| Part | Qty | Specification | From | Note |', '|---|---|---|---|---|']
        md += [f"| {r['part']} | {r['qty']} | {r['spec']} | {r['source']} | {r['note']} |" for r in rows]
        md.append('')
    printed = counts['Printed']
    md += ['## Counts', '', '| | Lines | Pieces |', '|---|---|---|']
    md += [f'| {g} | {c[0]} | {c[1] or "-"} |' for g, c in counts.items()]
    md += [f'| **All** | {sum(c[0] for c in counts.values())} | {sum(c[1] for c in counts.values())} |', '',
           f'The printed count includes the 68 track shoes and the {n_clamps + 3} W01 clamps. No custom-machined part anywhere in the machine.', '']
    (K.ROOT / 'BOM.md').write_text('\n'.join(md))
    with open(K.ROOT / 'BOM.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['group', 'part', 'qty', 'specification', 'from', 'note'])
        for r in ROWS:
            w.writerow([r['group'], r['part'], r['qty'], r['spec'], r['source'], r['note']])
    print(json.dumps(counts))


if __name__ == '__main__':
    main()

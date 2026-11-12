# Assembling the complete X1 excavator: order, inspection and what was changed to make it easier

This guide chains the subsystem guides into one order and records the inspection of the moves that only exist once the subsystems are combined. The subsystem guides stay authoritative for their own steps:
[J9/ASSEMBLY.md](../track_wheel_jgy370/J9/ASSEMBLY.md) (one track), [X1/ASSEMBLY.md](../track_wheel_jgy370/X1/ASSEMBLY.md) (chassis, revision F), [X1/TURNTABLE.md](../track_wheel_jgy370/X1/TURNTABLE.md) (slewing ring and turntable), [X1/BODY.md](../track_wheel_jgy370/X1/BODY.md) (body), [actuator_v6/ASSEMBLY.md](../actuator_v6/ASSEMBLY.md) (each V6-U60), [excavator_arm_r12/ASSEMBLY.md](../excavator_arm_r12/ASSEMBLY.md) (the arm), [WIRING.md](WIRING.md) (the harness) and the main board's [firmware README](../track_wheel_jgy370/X1/controller/firmware/README.md) (bring-up).

Nothing has been printed or assembled; every "checked" below is a nominal CAD check (`assembly_check.json`, `wiring_check.json`, `integration_check.json` and the subsystem reports), not a fit test.

## 1. What the inspection found

| Move | Checked how | Result |
|---|---|---|
| Pin O (Ø6 × 60) pushed in from either side with the body on | the pin's 120 mm swept cylinder against every part | clear from both sides (the cab is open on the boom side); 7 mm to the nearest part from the left |
| B01X with the whole arm lowered onto the T101 rib tops, body halves already fitted (and lifted off for service) | the arm unit translated 2–120 mm up | clear, 26 mm to the nearest body part at 2 mm up |
| 5 mm hex key on the four M6 × 40 bolts with the arm and the body on | Ø6 × 120 straight path up from each head | clear, 6 mm to the nearest part |
| Each body half slid 10 mm outboard and lifted 60 mm, hatch off, with the R12 arm and B01X in place | the half with its electronics against the rest (BODY.md did this against the ARM60) | clear, 0.3 mm as in BODY.md |
| Battery hatch lifted 1–60 mm at every dig-cycle pose | the hatch set against everything | clear |
| Mated JST plugs on the board's inboard edge against the T101 rib | gap between the mated housings (XHP-2/-4, PHR-3, 1.5 mm proud of the header faces, their wires to Y 79) and the rib | about 10 mm to the wires: a housing needs its 7.5 mm length plus the wire bend to go in, so it cannot be mated with the half on the machine, see 3.3 |
| Boom drives' V6 cable exits over the B01X plate | exit position over the boom travel | at full boom-down the sleeve exits 2.8 mm above the plate pointing straight down: the plate needed the troughs (3.1) |
| Cables leaving T101 behind the plate | probe boxes and the wiring tubes | T101's rear bulkhead and the hood wall left a 5 mm column: the body halves needed the notch (3.2) |
| R12's pin A order | reading the two guides against each other | step 1 pressed pins A before the drive eyes could be threaded on: fixed (3.4) |
| Right track motor polarity | X1 ASSEMBLY.md against the firmware channel table | "reverse electrically or in the controller" could be done twice: fixed (3.5) |

Everything else is inside one subsystem and keeps that subsystem's result: the J9 track build and the revision F joints (X1), the turntable, the body, R12's clash check and pin stacks, the V6 tool access.

## 2. The order (the installation sequence; the viewer's "Assembly order" mode animates the same 14 steps)

Tools for the whole machine: hex L-keys 1.5, 2, 2.5 (one at least 90 mm long for the body sleeves), 3 (20 mm short leg, 80 mm arm, for the track joints), 5; a 7 mm nut-holding tool within Ø11.2 (track joints) and a 7 mm deep socket (RU66 nuts); PH0 with a 3 mm × 100 mm blade and PH1 (V6); a 1.5 mm key (hub set screws); a soldering iron; CA glue; JST crimp tool (WC-110 for XH, WC-240 for PH, YC-160R for SM, or an Engineer PA-09 for all three); 1.2 and 2.4 mm heat-shrink; 1 mm VHB tape. Every connector's model number, mate, contacts and position is in [CONNECTORS.md](CONNECTORS.md); every bought part's place in [STANDARD_PARTS.md](STANDARD_PARTS.md).

1. **Tracks** (J9 ASSEMBLY.md 1–8, twice; the right track with the mirrored J901/J909). Fit the motor (Pololu 1999 hub), all rollers (two 624ZZ each) and axles, the idler (two 608ZZ) and the housing. Leave the rear sprocket, hub, plug and chain off. Solder 100 nF across each motor's tabs; lead the two 26 AWG leads out of the pod nose port and crimp a **JST SMP-02V-BC** (2 × SHF-001T-0.8BS) on their ends, + in position 1.
2. **Chassis** (X1 ASSEMBLY.md 1–3). Hold both tracks at 340 mm; lower the bare X101 80 mm into the seats; 8 × M4 × 25 with the external nuts. Then the sprockets, hubs, plugs and chains (J9 steps 4, 5, 7). Run each motor's leads forward beside the front arm into the carbody's side hole.
3. **Slewing ring, slip ring and the track joints** (TURNTABLE.md 1–3). Slip ring with the TPU dog into the collar; crimp a **JST SMR-02V-B** (2 × SYM-001T-P0.6 pins) on stator rings 1–2 and another on rings 3–4; ring gear; RU66 (nuts from below). Plug each track's SMP into its SMR beside the ring (left pair at (0, 30, 52), right pair at (0, −30, 52); the plug clicks in along Y), then the belly cover.
4. **Turntable** (TURNTABLE.md 4–8). T104 and T101 with the rotor leads fed up the Ø15 hole and out of the lead slot; drag pads; the swing motor on its slide; set the mesh with a paper strip and the drag at 1.9 N. Crimp the **XHP-4** (4 × SXH-001T-P0.6) on rotor rings 1–4 (rings 5–6 taped). **Press the body's 4 M3 inserts into the T101 rib tops now.**
5. **Actuators** (V6 ASSEMBLY.md). Four V6-U60 with cables to the lengths in harness.csv; each cable ends in a **JST XHP-2** (2 × SXH-001T-P0.6; slip 1.2 mm heat-shrink over the Ø0.8 PTFE wires before crimping; wire A red in position 1). Test each drive's direction on the bench.
6. **Arm unit on the bench** (R12 ASSEMBLY.md, corrected). Pins O and B into B01X and the boom; each boom drive's rear eye held between the foot plate and the cheek while its pin A is pressed in from outside; then the stick drive and stick, the bucket drive, linkage and bucket; the teeth glued. Glue the 15 W01 clamps on the boom and stick faces and snap the stick and bucket cables in; lay the boom-drive sleeves in the troughs; cables over the posts and down the slots; cable ties (WIRING.md 4).
7. **Arm unit onto T101.** Lower B01X with the arm onto the rib tops, feeding the four cables rearward on T101's floor and up at X −24.5 (where the hood notches will be). 4 × M6 × 40 from above, nuts in the T101 pockets. Checked: the unit's vertical path is clear even with the body on, and the bolts stay reachable from above.
8. **Counterweight** (BODY.md 2). Swing motor leads (with their XHP-2) into its channel, 2 × M4 × 12 from inside T101.
9. **Left half on the bench** (BODY.md 3). The main board rev B onto its 4 bosses (4 × M3), cab interior, operator, handrail, the two ledge magnets. Roof-lamp wires (0.2 mm enamelled, spliced to 26 AWG) through the Ø2 hole in the cab's rear wall; crimp the **PHR-3** (3 × SPH-002T-P0.5S) with the roof return in position 2 and the toolbox return in position 3, +5 V in position 1; the toolbox-lamp wires end in the lamp joint's **SMR-02V-B**.
10. **Plug the harness into the board** with the half standing beside the machine (the headers are side-entry, 15 mm from the T101 rib once the half is on): J102 XHP-4 (tracks), J103 (swing), J104 boom L, J105 boom R, J106 stick, J107 bucket (XHP-2 each), J108 PHR-3 (lamps): push each along +Y into its S2B/S4B-XH-A or S3B-PH-K-S header until the lock clicks, pin 1 at the marked end. The 12 V link's **XT30U-F** pushes onto the **XT30PW-M** at the front edge along −X. J109 stays empty. Coil the 150 mm slacks in the bay. Check every plug against WIRING.md 1.
11. **Left half onto T101** (BODY.md 4). Lower, slide 10 mm inward onto its hook, 2 × M3 × 12 down the sleeves. Its lap goes under the right half's skin; the four arm cables pass through the notches as it slides in.
12. **Right half on the bench.** Snap the **KCD1-101** rocker into the 19 × 13 cut-out in the toolbox top (terminals down, 20 AWG soldered to the 4.8 mm tabs). Put the **5.5 × 2.1 mm metal panel jack** (DC-022B pattern, M8) through the Ø8 hole in the toolbox front from inside, lock washer and nut outside; tip to the fuse side, sleeve to GND (22 AWG). Stick the **Littelfuse MINI FHM** holder (5 A MINI fuse) on the toolbox floor beside the Ø12 wire hole with VHB tape and splice its 14 AWG leads to the 20 AWG feed. The feed lead ends in the **XT30U-M** that will hang in the hood cavity; the lamp lead ends in the **SMP-02V-BC**; the two ledge magnets; the toolbox lamp LED.
13. **Right half onto T101** (BODY.md 4). With the half held beside the machine, plug the lamp lead's SMP-02V-BC into the SMR-02V-B of the cable from the board (the joint then lies in the right bay at X −12, Y −128, 10 mm outboard of the feed and the 12 V link) and the 12 V link into the switch lead; lay the slack over T101; lower, slide 10 mm inward, 2 × M3 × 12.
14. **Battery pack on the hatch** (BODY.md 6). Hatch B106 upside down on the bench: press the three **Keystone 1043** holders up between the sled walls against the two standoff ribs until the wall lips snap over their end walls (cell opening down; springs at alternating ends so the pack chains in series along X). Solder the two series links between the PC pins (20 AWG, about 20 mm), B−/B1/B2/B+ to the **HX-3S-01** BMS taped to the +Y wall, P−/P+ to the 150 mm lead with its **XT30U-F**.
15. **Cells.** Three Samsung INR18650-35E (or any 18650 up to 65.3 mm): − end onto the spring first, then press the + end down past the lips onto the plate contact. Check about 11 V (12.6 max) at the XT30U-F.
16. **Hatch lead and hatch.** Plug the hatch lead's XT30U-F down onto the feed's XT30U-M in the hood cavity, tuck the slack over T101, and set the hatch on its four magnet pairs (finger notch at the rear).
17. **Bring-up** (firmware README): `show`, `zero`, `drive` each channel at low duty, check every direction against WIRING.md 1, then pair the handle.

The viewer's "Assembly order" mode plays steps 1–16 as 14 animated steps (the two half-on-the-bench steps and the plug step are separate; tracks + chassis and the two turntable steps are merged as before): each step's parts move in along their fitting direction, the halves and the hatch are built beside the machine and go on as one, the camera flies to each step, and the labels name every connector and pack part by its model number.

## 3. Changes made in this round so that it assembles

1. **B01X issue 3** (`source/build_adapter.py`): two cable troughs in the plate top (a 9 mm mouth under each boom drive's exit, easing to the slot), one 8 × 7 slot per side at vehicle X 0..8, tie-slot pairs, and two Ø6 cable posts with tie holes. B01X stays a 188 g PETG print with its bolt pattern and foot geometry unchanged.
2. **Body B1 rev B, issue 2** (`X1/source/x1_body.py`): the inboard hood front wall's bottom edge raised to Z 156 over |Y| 38–56 on both halves. The body checks were re-run on it.
3. **Main board inboard plugs.** They can only be mated with the half beside the machine (3 mm to the rib). The order above does it that way; top-entry headers (DESIGN.md's listed alternatives) are recommended for a rev B board so plugs go in from above.
4. **R12 ASSEMBLY.md steps 1 and 3**: pins A are pressed in with the drive eyes and spacers in place, not before.
5. **X1 ASSEMBLY.md 4.2**: both track motors wired alike; the firmware inverts the right one.
6. **W01 cable clamp** (`source/build_clamps.py`): a glued snap clamp for the 3 mm sleeve, 0.24 g, no screws.
7. **Firmware S4** (CONTROL_CHECK.md 3): the stall cut-out now works at any speed.

## 4. Service

- **Arm off:** unplug its four cables at the board, free them at the rib crossings, take the 4 × M6 out from above, lift B01X with the arm and the cables. The body stays. (Also the way to the T101 hub screws, TURNTABLE.md.)
- **A half off:** BODY.md: hatch, 2 screws, slide out 10, lift; set it beside the machine on its slack, then unplug.
- **A track off:** X1 ASSEMBLY.md service: belly cover off, its SM plug apart, chain and sprocket off, the four joint screws, lower the track 80 mm, slide it out.
- **Cells:** the hatch, by hand.

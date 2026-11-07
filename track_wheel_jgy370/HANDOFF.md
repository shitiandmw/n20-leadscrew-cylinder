# Current status

**2026-11-07: the body B1 branch (`at/c12fe487`) is merged into revision F, and everything that depends on both was rebuilt and re-checked on the merged CAD.**
- `X1/body_validation.json` PASS (byte-identical to the body branch's: the body sits above Z 100.5, clear of the whole chassis at every swing angle).
- `X1/turntable_validation.json` PASS, now run on the revision F chassis; swing simulation re-run (MuJoCo 4.0, knock cases moved by up to 3 %).
- Joint check, both viewers (with the body views) and the delivery package re-run; see `X1/README.md` → Verification and rebuilding.

**2026-11-05: X1 revision F is the only chassis-to-track connection. Every check passes, run fresh on F.** See [X1 revision F](#x1-revision-f-curved-supports-seated-in-the-track-beams-2026-11-05) and `X1/REV_F_NOTES.md`.
- The superseded connection revisions C, D and E were deleted at the user's request ("we only need that approved F").
- The enclosed idler spring guide from revision C is kept unchanged.
- Nothing has been printed or assembled.

**2026-11-04 (body B1 rev B): the user's four review points on rev A are modelled.** The battery is on the centreline under a lift-off hatch, the cab has its glass cut out with a seat and an operator, and there are stairs and other Cat 320 details. The side CG is trimmed to 0.0 by a stepped shot pocket. Every body, turntable and browser check passes. See [X1 body B1 rev B](#x1-body-b1-rev-b-the-users-review-of-rev-a-2026-11-04) and `X1/BODY.md`.
- Nothing is committed: the user stages and commits.
- The shared handoff note (update_task_handoff, task a6e8dd4e) is kept up to date as well.

**2026-11-03 (body B1 in CAD): the three body prints agreed on concept sheet 5 are modelled, and every CAD check in `X1/body_validation.json` passes.**
- See [X1 body B1: CAD](#x1-body-b1-cad-3-prints-2026-11-03) and `X1/BODY.md`.
- T101 gained 4 M3 insert holes in its rib tops; its export, static fit, clearances and mass were re-run.
- The turntable's mass file and the swing simulation now use the real body instead of the placeholders. Every case moved by a few per cent, and the R3 conclusions stand.
- Nothing is committed: the user stages and commits.
- The shared handoff tools (get_task_handoff / update_task_handoff) were not available in this session; this file is the handoff.

**2026-11-03 (body concept B1, issue 2): the X1 upper body was sketched from the real Cat 320.** Decisions D1–D6 are made, and the user agreed to 3 prints. See [X1 body concept B1](#x1-body-concept-b1-traced-from-the-cat-320-2026-11-03-sketch-only).

**2026-11-03 (Round 14): the X1 turntable (concept R3, issue 3) is modelled in CAD, every CAD check passes, and the swing drive has been simulated in MuJoCo.**
- See [X1 turntable R3: CAD and swing simulation](#x1-turntable-r3-cad-and-swing-simulation-round-14-2026-11-03) and `X1/TURNTABLE.md`.
- The 6-way 2 A slip ring and the track motor as the swing motor are confirmed by the user.
- Main finding: the speed ramp is essential, and a full-speed swing into a rigid obstacle loads the printed pinion to about PETG's yield.
- Waiting on the user's review. Nothing is committed: the user stages and commits.

**2026-11-03: the X1 crawler chassis (two J9 tracks on a printed X-frame) is built and every geometry check passes.** See [X1](#x1-crawler-chassis-2026-11-03) below.

**2026-11-03: the J9 CAD is built and every geometry check passes.**

- **Motor:** chosen from the user's shop listing. It is the JGY-370-1260 12 V 200:1 (30 rpm), motor only.
- **Sprocket drive:** the sprocket now bolts to a bought Pololu #1999 hub on the D-shaft.
- **Motor enclosure:** the housing J909 now has a closed motor pod styled on the Cat 320's final drive (round drum on the sprocket axis, gearbox shoulder, motor tube, nose with a Ø5.5 cable port). See `J9/README.md → Motor enclosure`.
- **Files:** `track_wheel_jgy370/J9/`. The downloadable package is `output/jgy370_J9/` (gitignored).
- **Waiting on:** the user's feedback on X1 (and J9).
- **Not done yet:** nothing has been printed, assembled or run under power.

J8 still sits at the top level of `track_wheel_jgy370/`, unchanged. J9 is a separate subfolder. Do not flatten or archive J8 unless the user asks.

## User requirements (J9)

The user writes "jqy370" for this JGY-370 module.

1. **Round 1.** J8 has too many redundant structures. Keep only the core parts:
   - the gear motor
   - the one-piece motor/track housing
   - the sprocket on the motor
   - the H-shaped main frame
   - the spring idler
   - small support rollers above the H and small road rollers below it

   The small wheels were too large and too few. The track was too narrow and could tip over.
2. **Round 2.**
   - "H" means the cross-section: two walls joined by a web. The user confirmed this.
   - The user let me choose the shoe width and the wheel count.
   - The support rollers must lift the top run a little more.
   - The user asked for a drawing first, with no implementation yet.
3. **Round 3.** The user approved the concept drawing (`output/jgy370_J9_discussion/`) and said to begin implementation.
4. **Round 4** (during implementation): "the bottom support wheels also seem to protrude slightly. That's unnecessary — only the top needs it."
   - The 2 mm end-wheel rise inherited from J8 is removed. The ground run is now flat.
5. **Round 5 (2026-11-03).** The user sent the JGY-370 drawing, the ZENG WHCD 1260/1285 tables and a shop listing. They said "choose a suitable one". The choice and its reasons are in `J9/README.md → Motor choice`:
   - **Motor:** 12 V motor only, 30 rpm (6 kg·cm) = JGY-370-1260 200:1.
   - **Speed:** 88–120 mm/s, which covers the Cat 320's scale speed of 106 mm/s at 1:15.
   - **Pull:** 15 N rated and 51 N stall per track. The stall pull is just inside the 51.9 N the idler holds in reverse at its stop.
   - **Not used:** the L-bracket and the one-way speed controller.
6. **Round 6 (2026-11-03).** The user said the track left the motor exposed and asked for an enclosure that "has to look good".
   - They asked twice before ("This track motor doesn't seem to have an outer casing?" and "…you need to design an enclosure"); both times I wrongly sent no answer.
   - The housing is still one piece (round-1 requirement): skirt + closed motor pod. Done; see below.
7. **Round 7 (2026-11-03).** "Now, using a real excavator as a reference, complete a chassis with two crawler tracks and an X-shaped structure. Do not build the upper turntable, but reserve the mounting position for the turntable." Done as X1; see below.
8. **Round 8 (2026-11-03).** The user asked several questions:
   - How does the chassis turn the upper, and can a planetary gear set be used?
   - What do RC excavators usually use?
   - The control circuit is usually in the upper, right? How do we keep the wires from tangling when it turns?
   - They also asked: "can you draw a sketch first instead of modeling directly?"

   Answered with a concept sketch only (see [X1 swing drive and wiring concept](#x1-swing-drive-and-wiring-concept-2026-11-03-sketch-only)). Nothing is modelled. Waiting on their choices.
9. **Round 9 (2026-11-03), "feat: Turntable design".** The user sent R1's PDF and a seller's dimension drawing of a 6-way / 12-way 2 A flanged slip ring:
   "printing a slip ring myself is too complicated … use this slip ring to modify the design drawing. Please first help me design a new sketch."
   - R1 had already assumed a bought ring (SRC022A-6), not a printed one. The user's ring is the same family's standard type: its flange sits 5 mm back from the rotor end.
   - Answered with concept R2, a sketch only (see the section below). The user chose a slip ring over a limited swing. The swing-motor choice is still open.
10. **Rounds 10–11 (2026-11-03), discussion.** Could the turntable's gear connection and the parts above it sway, and can structure fix it? See the Round 10 section below.
11. **Round 12 (2026-11-03).** "I don't agree to adding metal parts; the machining cost is too high. Everything else is fine. Please redo the detailed design drawings for me."
    - Taken to mean no custom or machined metal: no aluminium hub plate, no metal backing ring, no metal sleeves, no pinion cartridge shaft.
    - Bought standard hardware stays: screws, nuts, washers, spring washers, heat-set inserts, small springs and felt, plus the parts already bought.
    - Answered with concept R3 (see its section below).
12. **Round 13 (2026-11-03).** "First design it according to the same motor model as the tracked version, and then I didn't understand the 6-channel or 12-channel issue: why does it need to be chosen?"
    - Swing motor: R3's motor was already J9's model (envelope, D-shaft, Pololu hub and 4 × M3 screw pattern come straight from `J9/source/j9_design.py` and `j9_parts.py`). The decision is now recorded in R3 issue 2, with the motor's swing figures.
    - Slip ring: explained, and the 6-way is now fixed in the drawings. Each ring passes one wire across the turning joint. Only the two track motors are in the lower, so 4 wires cross.

## What J9 is (CAD, done)

**Sources** (in `J9/source/`):
- `j9_design.py`: layout and the exact chain solver. It runs in about 0.6 s.
- `j9_parts.py`: CadQuery parts and the assembly.
- `build_j9.py`: STEP and STL export plus every check. It takes about 4 minutes in the foreground.
- `build_viewer.py`, `viewer.html` and `check_viewer.cjs`: the offline viewer, its screenshots and its browser test.
- `draw_layout.py`: builds `J9_layout.pdf`.
- `draw_drive_section.py`: builds `images/J9_drive_section.png`.

**Flat ground run:**
- The axles are at Z 44.32. Road rollers are at Z 22, tangent to the ground run and level with the sprocket's bottom chord.
- The idler is free (smooth wheel). The chain solve gives the idler at X 109.90, rotated 0.155 degrees.
- The support rollers are at X ±35 and Z 70.14, lifting the top run 3.5 mm. The top of the track is 92.4 mm.

**Parts:**
- 15 printed pieces of 9 designs, plus 34 shoes:
  - H-frame
  - sprocket
  - journal plug
  - 7 rollers (one design)
  - idler wheel (J8 shape)
  - 2 idler spacers
  - U-yoke
  - housing
- 56 bought pieces, including the Pololu hub, its 2 set screws and 3 × M3 × 25 added on 2026-11-03. There are no machined parts. The concept estimated 12 printed + 51 bought.

**Changes against the concept, found while building:**
1. **Sprocket outer support.** The sprocket's boss cannot go into the outer 6800ZZ when the H-frame is one piece. The sprocket now enters from the rear and slides onto the D-shaft. A printed journal plug then goes in from outside through the 6800ZZ, and an M3 × 50 screw clamps the plug and sprocket to the shaft end.
2. **Idler axle.** An M8 bolt through slots in the walls would clamp the walls and block recoil. It is now a plain Ø8 × 55 pin in the yoke arms. The pin ends run in 1 mm tracks in the groove floors. Two printed spacers locate the idler.
3. **Motor face.** The gearbox screw bosses (Ø7 × 2) and the central boss sit in counterbores in the inner wall. The four M3 × 6 screws go in from inside the H, before the sprocket. Thread engagement is 3 mm, as in J8.
4. **Drive hub (2026-11-03).**
   - The printed D-bore was replaced by a Pololu #1999 hub, sized from Pololu's drawing and STEP (`references/pololu_1999/`).
   - The hub flange sits in a Ø25.8 × 1 recess in the sprocket and is held by 3 × M3 × 25 from the sprocket's outer face.
   - Both set screws bear on the flat; they are tightened from above with a 1.5 mm key, before the track goes on.
   - A printed pad inside the hub bore meets the shaft end and sets the axial position. The boss stops 1.0 mm from the wall.
   - **Formula correction:** the old printed-bore table used 6T/(L·w²) and was 2× too low. The correct elastic peak is 12T/(L·w²). With the chosen motor that is 71 MPa at rated torque and 235 at stall, against a PETG yield of about 50.
5. **Motor pod (2026-11-03).**
   - `j9_parts.py`: `pod_outer`, `pod_cavity` (2.5 walls, 0.8 clearance to gearbox, can and the 10 mm terminal space), `pod_rim` (on J901, fills the skirt-to-wall gap round the pod), `housing()`.
   - The cavity is a U-section open toward +Y, so the housing slides straight on. `build_j9.py → housing_fitting` checks the path at 6 positions.
   - Cosmetic on the drum face: hub cap, centre boss and 8 printed hex heads. The tube has a band at the can's end cap; the nose has the cable port.
   - Fastening: 4 × M3 × 8 button heads (were M3 × 12) into inserts in 4 standoffs on the inner wall.
   - Print orientation is now skirt face on the bed (−90° about X).
   - Old-housing faults found and disclosed: it could not be fitted (the can tube wrapped past the can axis), and its print orientation put the shroud on the bed.
   - Module width is now 97.5 (hub cap to shoe edge, was 93.5). The pod reaches Y −62.5 over X −137.5 to −18.6 and Z 16.8 to 71.8; it clears the rear chassis boss by 2.4.
6. **Walls and housing.**
   - The walls are 6 mm thick everywhere; the concept's 8 mm front section was not needed.
   - Yoke grooves are 3.2 deep; the recoil stop is 4.2 mm, where the arms meet the groove ends.
   - The housing skirt sits at Y −35.5 to −38 and has Ø8 holes for roller-bolt access.

## Verification (`J9/validation.json`, PASS)

- **Chain:** 34 links with 2e-14 mm length error.
- **Static assembly:** 0 overlaps in 449 exact pairs, track included.
- **Motion:**
  - drive rotation through one tooth in 5° steps;
  - idler recoil 2.1 / 4.2 mm, with the hard stop confirmed;
  - spring clear at its recoil length;
  - chain at ¼, ½ and ¾ pitch against all fixed parts (conveyor approximation).
- **Assembly paths:** sprocket and hub entry and slide, plug insertion, yoke insertion, motor-screw key, housing fitting (6 positions).
- **Tool access:** 25 paths clear, including the 1.5 mm key onto both hub set screws.
- **Hub against Pololu's STEP:** 0.0001 mm bounding-box deviation. 0.03 mm³ of vendor material is missing from the model; 16 mm³ is extra, which is Pololu's edge chamfers.
- **Smallest clearances:**
  - pins and clips to the frame: 3.5 mm;
  - roller flanges to the web: 2.0 / 2.1 mm;
  - yoke to road roller: 2.1 mm;
  - hub boss to the wall: 1.0 mm;
  - sprocket tooth tips to the web end: 3.2 mm;
  - motor pod and frame rim to motor: 0.8 mm;
  - motor pod to the rear chassis boss: 2.4 mm.
- **Printed parts:** every one is a single valid solid; the STLs are watertight.
- **Viewer:** `J9/browser_validation.json` passes (no errors or network requests, views and run animation work).

## Open problems

1. **Hub set screws.**
   - Pololu publishes no torque rating for the set screws on a D-flat. The motor's stall torque is 1.96 N·m.
   - Mark the set screws and recheck them after the first runs.
   - Pololu gives no set-screw lengths. The CAD assumes 8 mm (flange) and 3 mm (boss).
2. **Motor hole depth.** 3 mm thread engagement in the gearbox holes is assumed and not confirmed.
3. **Print fits.** Bearing press fits, the Ø9.95 plug in the 6800ZZ and the Ø25.8 hub recess need test prints.
4. **Roller nuts.** The rollers float 0.3 mm between small wall bosses. Tighten the nyloc nuts only until snug.
5. **Chordal bobbing.** With a flat bottom, the sprocket's polygon effect reaches the ground (up to 1.3 mm per tooth on hard floors). Fix it only if it shows up in testing, for example by raising the sprocket alone by about 1.3 mm.
6. **Chassis.** Done as X1 revision F: straight X101 arms seated in 1.5 mm recesses in the main plate at X ±63.5, two M4 × 25 per joint (see the revision F section). The original three M4 bosses no longer exist.
7. **Reverse stall.** The stall pull of 50.8 N in reverse is almost the 51.9 N the idler holds at its stop. A driver current limit of about 1.0 A keeps the pull near 38 N.
8. **Heat in the closed pod.** No vents. About 0.4 W of winding loss at the rated 0.2 A; about 9 W in a held stall at a 1.0 A limit, so the driver should cut out on stall. Check the can temperature on the bench; vent slots under the tube are the fallback.
9. **Not checked.** Loads, wear, print tolerances and powered running. The vehicle mass is unspecified: do not ask again and do not invent a load rating.

## Next steps (in order)

1. Get the user's review of X1 (`output/jgy370_X1/`) and of J9, the motor and hub choice and the motor pod (`output/jgy370_J9/`).
2. Buy the parts: the JGY-370-1260 12 V 30 rpm motor only, and a Pololu #1999 hub pair (one pack covers both tracks).
3. Make test prints for the fits. Measure the gearbox hole depth. Bench-test the motor current and pull, and check the set screws.
4. Chassis: done as X1. Its next steps are listed under X1 below.
5. Promote J9 to the main revision (flatten it, archive J8) only when the user asks.

## Notes

- The shared handoff MCP tools (`get_task_handoff` / `update_task_handoff`) were not available in the 2026-11-02 or 2026-11-03 sessions, so this file is the fallback.
- No background jobs were started; every build ran in the foreground.
- CAD Python: `LD_LIBRARY_PATH=/tmp/v6-cad-libs/extracted/usr/lib/x86_64-linux-gnu OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/venv/bin/python`.
- Viewer test: `NODE_PATH=/tmp/j5-preview-tools/node_modules node check_viewer.cjs`.
- The concept drawing in `output/jgy370_J9_discussion/` still shows the 2 mm end rise and the M8/boss details. J9 CAD supersedes it.

## X1 crawler chassis (2026-11-03)

**What it is.** Two J9 tracks (left = J9 as built, right = mirror image) on a printed X-frame in the Cat 320 lower-frame layout. The turntable is not built; its mounting is reserved. Docs: `X1/README.md`, `X1/BOM.md`, `X1/ASSEMBLY.md`. Package: `output/jgy370_X1/` (gitignored).

**Decisions** (reasons in `X1/README.md → Decisions`):
- **Gauge 340 mm, not the scaled 159.** At 159 the two J9 motor pods would be 34 mm apart. 340 is the 60 mm excavator's stance.
- **Slewing ring: THK RU66 cross-roller ring**, sized from THK catalogue A18-20/21 (`X1/references/thk_ru66/`).
  - The outer ring bolts to the X-frame with 8 × M4 × 16 into inserts on PCD 83.
  - The inner ring is left for the turntable: 8 × M4 tapped through, PCD 45, flange within Ø59.
  - Seat at Z 85, turntable face at Z 100, Ø25 cable passage, swing envelope R 189 above Z 100.
- **Right track.** Only J901 and J909 need mirrored prints (`J901_H_frame_right`, `J909_housing_right`). The motor is turned 180° about its can axis and wired reversed.
- **Track to frame.** 3 × M4 × 12 per side. M4 × 14 was changed to M4 × 12 because it left only 0.1 mm to the bottom of the 8.1 mm insert hole.

**Sources** (`X1/source/`):
- `x1_parts.py`: X-frame, belly cover, RU66 model, assembly.
- `build_x1.py`: exports and checks, about 3.5 min.
- `build_viewer.py`, `viewer.html`, `check_viewer.cjs`: viewer build and test.
- `draw_layout.py`: the layout sheet.

They import J9's `j9_parts`/`j9_design` and read `J9/source/j9_scene.json.gz`. Changing J9 means rebuilding X1.

**Verification (`X1/validation.json`, PASS):**
- 594 assembly solids.
- Static: 0 overlaps in 126 pairs.
- Track slide-on, RU66 lowering and belly-cover paths: clear.
- Tool access: 46 paths clear. The 4 support-roller bolt withdrawals are blocked by the legs; this is documented as a service limit (take the track off first).
- Reserve: no intrusion.
- Clearances: X-frame to J909 1.5; reserve to track tops 7.6.
- Viewer check passes.

**Open (X1):**
- bed size (X101 is 188 × 248);
- the single-row 3 × M4 joint per side (check that the tracks don't rock);
- seat flatness and flush inserts;
- RU66 cost and equivalents;
- swing drive and slip ring: not included and belong to the turntable;
- no load rating.

The R3 upper body in `excavator_60mm` shares the 340 gauge and R 189 tail swing, but it was built for its own slew (two 6004 bearings + Ø20 spindle). On X1 it would need an adapter and a new swing drive.

## X1 swing drive and wiring concept (2026-11-03, sketch only)

**Status:** a two-sheet concept sketch was delivered. Nothing has been modelled, and X1's CAD is unchanged.

**Files:** `X1/swing_concept/` (tracked):
- `X1_swing_concept.pdf` and the two sheet PNGs;
- `source/draw_swing_concept.py`. It imports `X1/source/x1_parts.py` and writes into `X1/swing_concept/`. Run it with the CAD Python (about 7 s);
- `references/prosper_src022/`: slip-ring datasheet pages and `SOURCE.md`.

The sketch was first delivered only in `output/jgy370_X1_swing_discussion/`, which git ignores. When the user asked whether it had been saved, it was copied into `X1/swing_concept/`. The only change was the script's import path. The PDF regenerated there matched the delivered one: same text, and same pixels at 200 dpi on both pages. The `output/` copy remains as the download copy.

**Proposal (the user must confirm it before modelling):**
- **Swing drive (option A).** This is the full-size layout:
  - A printed ring gear is screwed to the carbody top: module 1.5, 80 teeth, pitch Ø120, Z 85–97, bore Ø98.
  - The swing motor sits on the turntable: a JGY-370-1260 200:1 (the track motor), shaft down.
  - A printed 20-tooth pinion on a Pololu #1999 hub sits at R 75, Z 87–97, 2 mm above the leg tops.
  - Output: 7.5 rpm with no load, and about 2.4 N·m rated torque at the swing. The Cat 320 is 11.25 rpm and 82 kN·m, which scales to 1.6 N·m at 1:15.
- **Wiring.** The battery, receiver and all drivers stay in the upper. Only the 4 track-motor wires cross the joint.
  - They go through an SRC022A-6 slip ring (Adafruit 736): 6 rings × 2 A, Ø22 × 19 body, Ø44 flange.
  - The slip ring is screwed under the X-frame top plate on 3 new bosses. The turntable turns its rotor through a loose slot in a Ø20 tube.
- **Alternatives shown:**
  - a planetary gearmotor instead of the worm. This is the real machine's choice, but it is back-drivable and needs a brake;
  - one big planetary set round the swing axis: not recommended, because it takes the centre that the cables need;
  - the motor on the chassis (the R3 layout);
  - a limited swing with a cable loop (R3 used ±150°);
  - a separate battery and receiver in the lower.
- **Sources checked:**
  - Cat 320 spec p. 2;
  - conequip.com "What is a Swing Drive?";
  - the LESU PC30 listing on oliverhobby.com (4-way electric + 1-way oil slip ring, 360°);
  - the Huina 1580 rotary-gearbox listing on havochobby.in;
  - the Prosper SRC022 datasheet.

**Decisions pending from the user:**
1. Worm or planetary swing motor.
2. Slip ring or limited swing.
3. 200:1 (7.5 rpm) or 150:1 (10 rpm).

**After approval, model these:**
- the ring gear and pinion prints;
- 6 M3 inserts in the carbody top;
- 3 slip-ring bosses under the top plate;
- the pinion's path (R 58–92, Z 87–100) added to the turntable reserve and to the checks;
- the swing motor's position on the future turntable.

## X1 swing concept R2: the bought slip ring (2026-11-03, sketch only)

**Status:** a two-sheet sketch was made. Nothing is modelled, and X1's CAD is unchanged. R1's files are kept unchanged for comparison.

**Files** (in `X1/swing_concept/`, not committed yet):
- `X1_swing_concept_R2.pdf`, plus `X1_swing_concept_R2_sheet1.png` and `_sheet2.png`;
- `X1_swing_concept_R2_checks.json`: 22 clearance checks computed from the sketch sizes, all passing;
- `source/draw_swing_concept_r2.py`: imports R1's `draw_swing_concept.py` for its helpers and swing-gear sizes. Run it with the CAD Python, in a few seconds. It exits non-zero if a check fails;
- `references/bought_slip_ring_2A/`: the seller's drawing (`seller_drawing_6_and_12_way.png`) and `SOURCE.md`, with the values read from it and what it doesn't give.

**The bought ring** (from the seller's drawing):
- Ø22 body, L 19 (6-way) or 26 (12-way).
- Ø44 × 2.4 flange, 5 mm back from the rotor end; 3 × Ø5.4 on Ø35.
- Ø7.8 × 9 rotor; 2 A per ring.
- Not on the drawing: voltage, speed, lead length and gauge, colour code.

**R2 proposal (changes only the slip ring and its mount; the swing drive is R1's):**
- **Collar (X101 change).** It replaces R1's 3 bosses. It hangs under the top plate: Ø44 × 5, Z 74–79, Ø22.4 bore.
  - The ring's Ø22 × 5 spigot (the body above the flange) locates in the bore.
  - 3 × M3 × 8 with ISO 7089 washers go in from below, into M3 inserts (Ø4.0 × 5.7) on Ø35. A washer is needed because the Ø5.5 head barely covers the Ø5.4 hole.
- **Positions.** The flange is at Z 71.6–74 and the rotor at Z 79–88. The stator end is at Z 60 (6-way) or Z 53 (12-way).
- **Rotor dog (new print, TPU 95A).**
  - Ø7.5 bore, a stretch fit on the rotor; Z 81–89, with a shoulder on the rotor end and a Ø5 hole for the leads.
  - Two lugs, Ø19 across.
- **Turntable hub (future part).**
  - Ø34.6 spigot in the RU66 bore (Z 95–100) and a Ø15 lead hole.
  - Two prongs, R 7.5–11, 50° wide, reaching down to Z 83.5. They push the lugs with about 103° of play, so the ring carries no load.
- **Wiring.**
  - 6-way: rings 1–4 carry left +/−, right +/−; 5–6 spare. The 12-way pairs rings.
  - The stator leads plug into the track-motor leads in the carbody with 2-pin plugs.
  - The rotor leads end in a JST-XH 4-pin plug at the drivers; it passes the Ø15 hole.
- **Recommendation:** the 6-way. The 12-way only for encoder track motors (10 circuits) or paired rings. Both fit the same collar.

**Decisions pending from the user:**
1. Approve R2's mount, or change it.
2. 6-way or 12-way.
3. Still open from R1: worm (JGY-370) or planetary swing motor, and 200:1 (7.5 rpm) or 150:1 (10 rpm).

**After approval, model these:**
- the collar and the 6 ring-gear M3 inserts on X101;
- the TPU dog;
- the ring gear and pinion;
- the turntable hub with its prongs.

Then add the pinion path and the prongs (R 7.5–11, down to Z 83.5) to the turntable reserve and to `build_x1.py`'s checks. Also update `X1/ASSEMBLY.md`: it still routes the motor leads up the Ø25 passage.

**Notes for the modeller:**
- The prong tips sit exactly at the 1.0 mm minimum above the relief floor.
- The collar sits on the plate area under the RU66 relief. When X101 prints upside down, that plate bridges over the Ø75 relief pocket. This is an existing X1 print question, not checked.
- The animation script `source/animate_slip_ring.py` still uses R1's geometry and was not regenerated.

**Environment used:**
- Fresh venv `/tmp/sw-venv`: CadQuery 2.7, matplotlib, shapely, scipy, PyMuPDF.
- `LD_LIBRARY_PATH=/tmp/sw-tools/root/usr/lib/x86_64-linux-gnu`, with libGL and X libraries extracted from Ubuntu debs.
- `/tmp/venv` from earlier sessions no longer exists.
- The shared `get_task_handoff` / `update_task_handoff` tools were not available. This section is the local fallback for task `a6e8dd4e-9ad7-4bb5-8bf5-3a34526d787e`.

## Round 10 discussion: will the upper sway at the swing joint? (2026-11-03, no files changed)

The user asked whether the turntable's gear connection and the parts above it could sway (not the tracks). The answer was discussion only, with rough estimates. Nothing has been modelled, and the R2 sketch is unchanged.

**Conclusion:** the RU66 bearing is not the problem. The risks are in the parts around it.

**Risks found, most noticeable first:**
1. **Side-to-side play in the swing drive.**
   - Sources: backlash in the JGY-370 worm gearbox (not specified; assumed 1–2°, divided by the 4:1 gears) and the printed gear mesh (0.2–0.4 mm at R 60).
   - Total: about 0.45–0.9° at the turntable, or roughly 4–8 mm at the bucket 0.5 m out. Measure the real gearbox.
   - The ring gear makes it worse. Its bore is Ø98 around the RU66's Ø95, so it is located only by 6 × M3 in clearance holes and can sit off-centre.
2. **A springy deck and hub.** The deck in the sketch is only a placeholder.
   - A 6 mm printed plate carried on the Ø59 inner-ring pad sags about 1.5 mm under the ~1.8 kg counterweight and bounces at about 13 Hz.
   - A ribbed box about 30 mm deep is about 60 times stiffer.
3. **Abrupt stops.** The worm cannot be back-driven, so the upper stops dead. The arm whips and the upper rattles inside the play.
4. **Bolts loosening as the plastic creeps.**
   - Both bearing joints clamp printed plastic: 8 × M4 at the top, 8 × M4 into inserts at the bottom.
   - Statically there is plenty of margin: the joint would open at about 36 N·m, against about 3 N·m from the 60 mm excavator's upper and arm. Creep will slowly lose that clamp.

**Fixes proposed (not yet in any sketch):**
- a Ø95.2 locating bore so the ring gear centres on the RU66 outer ring;
- a motor mount that can be adjusted or spring-loaded to set the gear backlash;
- a light friction drag pad;
- speed ramps on the swing motor in the driver;
- a box-section deck with a metal (or metal-sleeved) hub plate on the inner ring;
- metal compression sleeves or an aluminium ring under both bearing joints, re-tightened after running in;
- ask the seller for a low-clearance or preloaded RU66.

**Next:** waiting for the user to choose which fixes go into a sketch R3.

**Round 11 (follow-up): "Can this problem be solved through structural design?"** The answer was discussion only.

Mostly yes. Proposed structural concept for sketch R3 (not drawn yet):
- **Centre frame**, as on a real upper frame: two deep printed ribs about 35 mm tall run over the bearing hub from the boom foot to the counterweight. The boom and the counterweight balance each other through these ribs, and the deck plates carry only light parts.
- **Hub:** a metal plate, or a printed hub with metal sleeves, on the RU66 inner ring.
- **Bottom joint:** a backing ring with nuts under the X-frame top plate, instead of plain heat-set inserts.
- **Ring gear** centred on the RU66 outer ring with a Ø95.2 bore.
- **Pinion:** on a sliding mount with a set screw and a lock, optionally in a two-bearing cartridge so the gearbox shaft carries no side load.
- **Drag pad:** a spring-loaded felt pad pressing on the ring gear's top face: about 15 N at R 55, giving about 0.25 N·m (about 10% of the rated swing torque).

Not fully solvable by structure:
- the worm gearbox's own internal play: the drag pad stops the rattle, but a dead band remains when the upper reverses;
- the jolt when the swing stops: best fixed with a speed ramp in the motor driver.

The other structural option is an industrial-style worm slewing drive at the ring gear: a bigger change, not recommended now.

**Round 12:** the user rejected the metal parts (the hub plate, the sleeves, the backing ring and the cartridge shaft) because of machining cost. Everything else was approved and is drawn in R3.

## X1 revision F: straight arms seated in the track beams (2026-11-05/06)

**User requests (task "optimise the latest track and chassis design" and its follow-ups):**
1. Replace the three square X-frame-to-track mounts with arch-shaped clamps over the track main beam, and enclose the idler spring in a bore in the main beam. The spring guide was accepted; the arch clamp (revision C) was not.
2. Revisions D (broad bolted faces) and E (T-flanges on a flat plate) were also rejected as too complex or not stable.
3. The user sketched the final form in red over a section: each X-leg deepens into a curved support whose foot sits in a shallow recess in the track main plate. No recessed screw or nut pockets, because they weaken the plate. The sketch was confirmed and modelled as revision F.
4. "We only need that approved F; the rest can be cleaned up." C, D and E files are deleted. F's scripts and reports no longer depend on them.
5. After delivery the user found the leg ends "very strange" (narrow stems with T-blocks) and asked for a smoother, stronger, less geometric form that reads as one piece with the X-frame. Concepts were drawn first (`output/X1_straight_arm_concept.*`, earlier ones superseded); the user approved v4, "Agreed, let's start implementing the modeling".
6. v4 is now the product CAD, still called revision F: same principle (end in a 1.5 mm seat, plain holes, external nuts), same screw positions.

**Geometry:**
- Joints at X ±63.5. Each arm is 28 mm wide, straight from vehicle Y ±96 to its flat end at ±137.5 (Z 53–74).
- Deck: one cubic Bézier, Z 85 at |Y| 48 to Z 74 at the plate face. Underside: quadratic arch Z 34 → 57.5 (crown at |Y| 108), then the J9 foot curve (`j9_mounts.FOOT`) down to Z 53. All exact Bézier edges, so the booleans stay fast (X101 builds in about 40 s).
- Head slots each side of a 9 mm centre web, Y ±97 to ±127, Z 62.75–72.75, round inboard end; screws slide in sideways, the L-key handle comes out of the slot (±30° stroke).
- The seat is a plain 28.3 mm rectangle (0.15 mm side clearance), 1.5 mm deep, open top; 8.5 mm of plate remains behind it.
- J909: windows follow the arm with about 0.5 mm clearance (0.41 mm measured minimum); beside each slot a lane above Z 62.75 lets the washer pass over the rear motor-pod shell (0.9 mm deep there).
- Fasteners: 8 × M4 × 25 ISO 4762 through plain holes, with 16 washers and 8 external nuts.
- Fit the frame by lowering it vertically 80 mm into both prepared tracks; sliding the tracks on sideways clashes with the motor and housing.
- X101 prints at 155 × 275 × 51 mm.

**Verification (all fresh, nothing inherited):**
- `X1/arc_seat_mount_validation.json` (173 cases, about 51 min, straight-arm joint):
  - joint seating and contact, fasteners and tools;
  - continuous vertical fitting and service routes;
  - sprocket fitting, idler recoil and chain phases;
  - 24 upper swing angles;
  - RU66 seat-screw and belly-cover keys;
  - clearances. The smallest are 0.41 mm frame to housing, 0.59 mm joint hardware to the recoiled idler and 0.65 mm frame to motor.
  - contact per joint: 556.2 mm² end face; seat ledge 42.0 mm² front, 36.1 mm² rear (the motor relief interrupts it).
- `X1/revf_leg_sections.json`: weakest arm section 1612 / 1328 mm³ (vertical / lateral I/c) at the slot end, Y 127; the old T-end was 514 / 701.
- Motor leads: the reserved cable path now runs forward to X 34 beside the front arm, clear of the inner screws' key swing (it used to cross between the arms at X 0).
- `J9/validation.json`: a fresh full run of the `build_j9.py` trial block on the delivered parts (69 cases, 904 pairs), plus the spring envelope and main-plate seat clearances.
- `X1/revf_part_exports.json`: the five changed STEP/STL files match the current source. `X1/revf_refresh_validation.json`: the assemblies and viewer scenes hold the current parts.
- Rebuild order: `X1/README.md`, "Verification and rebuilding". Long checks resume from `/tmp` checkpoints keyed on exact input hashes.

**Open:** printed fit of the seats and plain holes, joint stiffness, preload retention, creep and strength. No load rating.

## X1 body B1 rev B: the user's review of rev A (2026-11-04)

**User request** (verbatim):
> "A few minor issues 1. The actual dimensions and weight of an 18650 are fairly large; placing it on the right may cause a slight shift in the center of gravity 2. The 18650 battery should be designed to be easy to install 3. The glass part of the cab can be cut out, and a simulated seat and simulated driver can be added 4. You could add some simulated stairs and the like to make the model look more realistic."

**What changed** (updated in place; rev A's sources were backed up only in `/tmp/sw-render/b2/`, as `x1_body_revA.py` and `build_body_revA.py`)
1. **Battery and CG.**
   - The cells are taken at the Samsung INR18650-35E datasheet maxima: Ø18.55 × 65.25, 50 g.
   - The pack moved from the right bay to a lift-off hatch B106 on the centreline. The hatch is the Cat's raised engine hood (rear view 027), X −144.7 to −73.9, |Y| < 54.7, seated on 6.5 × 4 ledges at Z 217.02.
   - Rev A's upper CG was Y +1.7 (the solid cab outweighed the right battery). Rev B untrimmed was +2.3.
   - **The fix:** the counterweight's shot pocket is split on the centreline with two floor heights (left Z 117.3, right 108.0). The mass stage solves the left and right shot masses so that both the X and Y moments are zero. The result is CG (0.0, 0.0). `final` checks |CG Y| < 1.0.
2. **Easy to install.**
   - 3 × Keystone 1043 single holders (77.05 × 20.65 × 14.86, DigiKey) are glued under the hatch, cells facing down. The BMS and the XT30 lead are on the hatch's end walls.
   - The hatch is held by 4 pairs of Ø6 × 2 magnets and has a finger notch. The lead is 150 mm long, so the hatch can be turned over without unplugging.
3. **Cab.**
   - B102's cab is a 2 mm shell, open on the boom side, with the door glass (split at Z 184–187), the rear side window, the windshield and the rear window cut out.
   - New prints:
     - B104, the cab interior: seat, consoles, joysticks, levers, pedals, monitor, and the right front pillar and sill.
     - B105, the operator in a hard hat.
     - B107, the left handrail and mirror, pegged into the front-left pillar.
4. **Details** (from renders 000/009/018/027):
   - stairs with a back panel, a stringer and tread grooves;
   - a grab rail;
   - the right mirror;
   - an anti-skid crosshatch on the tank;
   - a toolbox lamp, roof work lamps and a rear camera.

**Numbers**
- Prints:
  - B101 452.7, B102 336.0, B103 340.6, B104 46.0, B105 17.4, B106 36.7, B107 1.2 g.
  - The shot is 728 g (left 269, right 459); pause at 25.4 mm.
  - The body is 2.30 kg.
- Upper: 5.12 kg, CG (0.0, 0.0, 178.2), 0.154 kg·m². With the arm tucked (bound): X −42.6.
- Swing simulation re-run: upper 5.10 kg (the pinion is a separate body), 0.154 kg·m². Stop without the ramp 204 N on a pinion tooth (rev A 208 N), with the ramp 35 N; into a rock 258 N. The conclusions stand (TURNTABLE.md).

**Checks** (all pass)
- `X1/body_validation.json`:
  - static: 204 pairs;
  - sweep: decided by height, 8.1 mm clear;
  - paths: 27 positions (the hatch lift; each half off with the hatch off; the counterweight; B104 and B105 slid into the cab on the bench);
  - tools: 12 paths;
  - bed fit: all 7 prints;
  - STEP round-trips, and every STL is watertight with 1 shell (B101: 2, the sealed pocket);
  - lateral CG: 0.0 (limit 1.0).
- `X1/turntable_validation.json` was re-run (`build_turntable.py mass … final`).
- `X1/browser_validation.json`: 16 screenshots including the new Cab and operator and Body, right side views; the hatch lifts in the service pose; swing playback works; no errors and no network requests.
- A full `build_body.py` run takes about 60 min here. The right half's path stage is slowest (about 20 min): the crosshatched B103 against the ARM60.

**Problems met**
- **Chained `.union()` with `.clean()` left the operator solid invalid.** One `fuse(*shapes).clean()` (`fuse_all`) is valid.
- **The traced treads stack like a ladder.** Full-depth risers sealed 5 voids under the tread grooves (B103 STL with 6 shells), so they were replaced by a back panel and a stringer.
- **`half_of` doesn't match `B103_right_half_shell`.** `build_body.side_of` groups the mass rows for the side moments.
- **The first static run found two slivers**, both fixed:
  - B102's lap-side front ledge touched B103's slope inner face (0.52 mm³). The ledge now stops 1.3 mm short of the slope.
  - B104's box floor plate cut into the cab's sloping rear-lower wall (34 mm³). The plate now follows both sloping walls, 0.3 clear.
- **Coarse preview renders run out of memory** (exit 137) on this shared 8 GB machine. Tessellate to npz in one process, then render in another.
- **Labels changed after the final run.** Two clearance labels were renamed (B107 pegs; body top = the roof lamps), and B103's note now reads "back panel and a stringer". The same strings were patched in `body_validation.json`; the geometry is unchanged. Because `x1_body.py`'s stamp changed, the next `build_body.py` run rebuilds the body BREP.

**Open items:**
- magnet hold (not tested);
- whether the cells stay in the face-down holders when shaken;
- fragile rails, mirror and joysticks;
- B105 needs tree supports;
- all of rev A's open items.

**Next:** the user's review of rev B.

## X1 body B1: CAD, 3 prints (2026-11-03)

**User request:** "Agreed to split it into 3 pieces. Let's start modeling."

**Deliverables**
- `X1/BODY.md`: parts, the shot fill, bought parts, wiring, assembly, service, checks, balance, changes from the concept and open items.
- `X1/source/x1_body.py`: the CAD. It imports the concept script's traces and numbers.
- `X1/source/build_body.py`: cached stages `mass export static sweep paths tools clearances final`.
- `X1/step/B101_counterweight.step`, `B102_left_half.step`, `B103_right_half.step` and `X1_body_assembly.step`; `X1/stl/B10x_*.stl` in print orientation.
- `X1/body_validation.json` and `X1/simulation/body_mass_properties.json`.
- The viewer has a body toggle and three views: Body B1, Inside the body, Body off (service).

**The parts**

| Part | Print | Mass |
|---|---|---|
| B101 counterweight | Upright, turned 45°, 231.5 square. Pause at 22.0 mm to pour 777 g of steel shot into the sealed pocket. | 452 g |
| B102 left half | On its outer face, 236.7 × 151.4 × 160. Cab (solid with infill), louvred hood, controller bay, USB slot. | 521 g |
| B103 right half | On its outer face, 204.7 × 150.3 × 153.8. Tank, guardrail, treads, toolbox (switch, fuse, jack), exhaust, battery bay. | 336 g |

- **Fixing:** 2 × M3 × 12 per half, down sleeves into new rib-top inserts at X −120 and −45, plus a front hook. The counterweight takes 2 × M4 × 12 into inserts.
- **Balance:** the upper is 5.22 kg with its CG on the axis (arm stretched); with the arm tucked (bound), X −41.8. Its inertia is 0.159 kg·m².

**Checks (all pass)**
- Static: 158 pairs.
- Sweep: decided by height. The body's lowest point is Z 100.5; the chassis outside r 70 reaches only Z 92.4.
- Paths: 16 positions (each half slides out 10 and lifts 60 with the rest in place; the counterweight comes off backwards).
- Tools: 12 paths. Bed fit: all three. STEP and STL valid.

**Changes from the concept** (also in BODY.md)
- The front sleeve moved from X −60 to −45, onto flat hood.
- The counterweight's captive nuts became M4 inserts.
- The shot goes in during a print pause.
- The USB slot is in the skirt, not in a louvre.
- The cab, tank and counterweight are solid with infill.
- The tank is flush with the doors.
- The deck in front of the hood is a full plate.

**Problems met while building it**
- Forked worker processes deadlock inside OCC: the checks run serially.
- A full stage set takes about 40 min. Each stage is cached; the models are cached as BREP in `/tmp/sw-render/model_cache`, which `build_turntable.py` now shares.
- An inverted overlap sign left a 0.01 mm slit inside the right half's side wall. The STL overhang check found it; it is fixed.
- The viewer check stalled once the body was added. With the body in the scene, each software-WebGL frame takes 5 to 25 s. After the track animation, a screenshot timed out after 180 s, and in another run the browser closed during the swing playback. The machine has 8 GB of RAM, no swap, and other sessions running. `check_viewer.cjs` now takes every screenshot first and runs the two animation tests with the body prints toggled off. Its clicks skip Playwright's wait for two stable frames (they are still real mouse clicks), and the default timeout is 180 s. A full run takes about 7 to 13 min, depending on load.

**Open items:**
- Print-fit test pieces: the sleeve on a rib, the hook, the lap and the insert holes.
- The 0.5 mm side gap between the raised deck and the ARM60 base edge.
- The real electronics' sizes.
- The weight of the shot.
- The fragile guardrail and exhaust.

**Next:** the user's review of the body.

## X1 body concept B1: traced from the Cat 320 (2026-11-03, sketch only)

**User requests:**
- "Agree to start modelling the body parts; sketch it out first, and don't start modelling directly."
- "Use a real excavator to draw the body shape, then find space inside the shell for electronic components, batteries, etc."

**Deliverables** (in `X1/body_concept/`)
- `X1_body_concept_B1.pdf`, 4 sheets: the trace; the X1 shell; the inside; parts, balance, wiring, checks and decisions.
- Sheet PNGs and `X1_body_concept_B1_checks.json`.
- `README.md`.
- Source: `source/draw_body_concept.py`.

**Shape source**
- The Cat 320 spec sheet, page 4: side and rear views, orthographic, 19.1 mm/px. The scale is set by the tail swing radius (dimension 4).
- Caterpillar's right-side render (`cat320_view_018.jpg`, perspective): used only for the right-side features.
- The traced pixel points are in the script.
- Checked against Caterpillar's numbers, all within 1.8 %: cab top, counterweight clearance, track length, tail swing, upperframe width and handrail.

**Cat → X1 mapping**
- X is kept at 1:15.
- Heights above the deck are kept at 1:15, on the T101 rib tops (Z 136). Hood Z 219; cab roof Z 252.
- The Cat's 11.5 mm frame band is stretched to 31 mm (Z 105–136), to cover T101.
- The width goes from 185.3 to 308: 61.3 is inserted on each side of the centreline, because the ARM60 base is 164 wide. Each Cat part keeps its own width.
- The counterweight's front face is the T101 rear face (X −145). The Cat's seam is at −145 (render) and −149 (drawing).
- The tail stays at R 188.7 on the centreline. The corners reach R 225, outside X1's R 189 reserve. They clear every lower part by 12.6 mm in height. This is decision D4.

**Parts** (all fit a 256 bed)

| Part | Note |
|---|---|
| B101 counterweight shell | Upright, turned 45° on the bed. |
| B102 left side module | |
| B103 right side module | |
| B104 hood lid, left | Magnets. |
| B105 hood lid, right | Magnets. |
| B106 cab | |
| B107 tank block | |
| B108 toolbox | |
| B109 details | |

- Change needed to T101: 3 M3 inserts in each rib's outer face, for the side modules.
- The counterweight uses the two existing M4 holes.

**Inside**
- **Left bay** (behind the Cat's louvres): the controller board (ESP32, 3 × DRV8871, 2 × DRV8833, 6 V and 5 V bucks). All 7 motor cables end here.
- **Right bay**, low at the rear: the 3S1P 18650 pack and BMS.
- **Toolbox:** the switch, a 5 A fuse and the charge jack.
- **Counterweight:** about 0.85 kg of steel shot (189 cm³, filled to Z 130) and a lead channel from the Ø20 window.
- The T101 service area stays clear. The cross-over loom runs at X −26, behind the ARM60 base.

**Balance (estimates)**

| Quantity | Value |
|---|---|
| Upper mass | 5.13 kg |
| Upper CG, arm stretched | X 0 (the ballast is set for this) |
| Upper CG, arm tucked (bound) | X −42.5 |
| Whole machine CG | X −1.5 (arm stretched), −24.2 (arm tucked) |
| Track support | X −110 to +110 |
| Inertia about the swing axis | 0.156 kg·m² |

The R3 simulation used 0.152 kg·m². With the 0.32 kg·m² reflected rotor inertia, the stops see +1.0 %. The check now compares that total; plain upper inertia alone would fail it.

**Decisions for the user**
- **D1:** 3S direct, or 2S with a boost.
- **D2:** ESP32 with a gamepad, or an RC radio.
- **D3:** steel shot, or stick-on wheel weights.
- **D4:** the widened Cat tail (R 225 corners), or keep inside R 189.
- **D5:** a 31 mm skirt, or the Cat's 11.5 mm band.
- **D6:** detail level.

**Issue 2** (after the user's reply)

The user's reply:
- "3 batteries, you mean 18650?" Yes: 3 × 18650 in series (3S1P).
- ESP32 is fine.
- "I agree to the bulk copper configuration": read as the loose-shot option D3; copper shot would also fit.
- Everything else is fine.
- "It would be best if the body could be printed in one piece, without too many parts; if not possible, discuss the pros and cons."

What issue 2 adds:
- The decisions are recorded on sheet 4.
- Sheet 5 is new: "fewer parts".
  - **Why one piece doesn't fit:** the body is 308 × 281 × 147. On a 256 bed, a print spanning the full 308 width must be under 54 deep (laid diagonally), so only the counterweight can be one full-width print.
  - **Minimum:** 3 prints.
    - B101 counterweight, 436 g, upright, turned 45°.
    - B102 left half, 391 g: cab, left hood, louvred side. 237 × 154 × 147, printed on its outer side face.
    - B103 right half, 308 g: right hood, tank, steps, toolbox, exhaust. 205 × 154 × 127, printed on its side.
  - **Fixings:** each half has 2 × M3 screwed down sleeves in the hood top into new inserts in the T101 rib tops, plus a front hook under the T101 base-plate edge (slide in 10 mm). The magnets and lids go.
  - **From outside, no opening:** the switch and charge jack on the toolbox; the ESP32 USB through a louvre slot.
  - **Comparison table:** 9 prints vs 3 vs 1 print. One print needs a bed of about 285 × 312.
- Two new checks, so 21/21 pass: the 3 prints fit the 256 bed; the one piece does not.

**Next:**
1. Get the user's answer on the split. 3 prints is recommended.
2. CAD of the body in the chosen split, and the T101 inserts.
3. A swing sweep with the body.
4. The balance from the CAD.
5. A re-run of the R3 simulation.

**Notes**
- The first silhouette version unioned about 100k triangles with shapely and ran for more than 10 min. It now rasterises them at 0.25 mm and traces the outline with contourpy, in about 2.5 s per view. The areas agree within 1 %.
- The shared handoff tools and the workspace-service tools were again unavailable, so this file is the handoff.

## X1 turntable R3: CAD and swing simulation (Round 14, 2026-11-03)

**User request:** "the 6-channel one is fine; let's get the modelling and physics simulation done now". Replies and documents are in English. Nothing is committed by the agent; the user stages and commits (they staged part of this work mid-round, so files show as `MM`).

**Deliverables**
- `X1/TURNTABLE.md`: the turntable's parts, bought hardware, assembly order, service, verification, simulation results and rebuild commands.
- `X1/X1_turntable_simulation.pdf` (5 pages) and `X1/images/X1_swing_sim_p1..5.png`.
- `X1/3D_preview.html`: the X1 viewer with the turntable, a swing slider, simulated swing playback and the new views "Swing drive" and "Hub and slip ring".
- `X1/swing_concept/X1_swing_concept_R3.pdf`, now issue 3: it matches the CAD, with 43/43 R3 checks and 22/22 R2 checks passing.
- `X1/turntable_validation.json` (PASS), `X1/simulation/` (mass properties, MJCF model, report, traces).
- Step files: `X1/step/T101..T106, X103` and `X1_turntable_assembly.step` (no tracks or arm, to stay under 100 MB). STLs are in `X1/stl/`.

**CAD (`X1/source/x1_turntable.py`, checks in `build_turntable.py`)**
- **Printed parts:** T101 centre frame, T102 motor slide, T103 drag plunger (×2), T104 hub adapter, T105 pinion, T106 TPU rotor dog and X103 ring gear.
- **Also modelled:** the JGY-370 swing motor, the Pololu hub, all hardware, the slip ring and the ARM60.
- **Gears:** true involutes (B-spline flanks). The mesh is set to 0.1 mm backlash at a centre distance of 75.137.
- **X-frame X101 rev B** (`x1_parts.py`):
  - RU66 on 8 plain Ø4.5 holes, with M4 × 30, a Ø12 washer, DIN 6796 and a nut below;
  - the slip-ring collar;
  - 6 countersunk ring-gear holes with Ø7.2 scallops.
  - `build_x1.py` passes (158 static pairs, 610 solids); X101 is now 449 cm³.
- **Turntable checks, all passing:**
  - static fit: 305 pairs, no overlap;
  - gear mesh: 10 positions, gap 0.047 mm;
  - swing sweep: every 15°, no hits;
  - assembly paths: 36 positions, all clear;
  - tool access: 51 paths, all clear except the known service limit (the ARM60 must come off to re-tighten the 8 hub screws).
- **Staged build:** `build_turntable.py` can run stage by stage (`export static mesh paths tools clearances mass sweep final`). Stages cache to `/tmp/sw-render/tt_cache`; delete it after CAD changes. Each stage takes under 8 min, so it fits a foreground command. Background jobs were killed twice by session restarts.

**Design changes found by modelling** (in R3 issue 3 and the CAD)
- Ring-gear screw heads could not pass the mount ring: added scallops.
- The drag plunger could not pass an M4 insert: now an M6 insert with an Ø8 hole, a Ø7.6 head and an M6 × 8 set screw.
- The drag spring would have had to go in before the heat-set insert: it is now Ø4.5 × 12, wire 0.5, about 1.2 N/mm, dropped through the insert's thread. The drag is now about 0.19 N·m (was 0.24), still adjustable.
- The motor leads hit the rear bulkhead: the window is now Ø20.
- The push-screw lock nut hit the base plate: the screw is now at Z 113 and the ears are 6 thick.
- The gearbox's screw bosses needed pockets: the motor now sits on M3 × 8 button heads in counterbores.
- The hub's boss set screw lands 1.3 mm short of the end of the motor shaft's D-flat. It is modelled as a cup point; check this on the real shaft.

**Simulation (`simulate_swing.py`, CAD masses)**
- **Model:** upper 5.52 kg (2.80 from the CAD, a 1.8 kg counterweight, 0.92 kg of placeholders); inertia 0.152 kg·m²; lower 4.48 kg.
- **Stops and reversals:** without a ramp, 203–210 N on a pinion tooth (about 80 % of PETG's yield). With the 0.4 s ramp, 34–40 N.
- **Knocks and shake:** R3 wobbles 6.9 mm with 23 tooth impacts; without the pads, 8.8 mm and 37; R2-like, 9.9 mm and 29.
- **Slope:** the worm holds the upper on a 15° slope (0.2° of drift through the play).
- **Rigid obstacle at full speed:** 256 N, about 50 MPa, at yield; the current limit does not cap the impact. It does cap the held stall (78 against 139 N).
- **Recommendations:** ramps in the driver; slow swings near obstacles; spare pinions, or a stronger filament.

**Open items for the user**
1. Review `TURNTABLE.md`, the simulation PDF and R3 issue 3.
2. Measure the output play on a track motor (the simulation assumes 1.5°).
3. Decide the pinion material, or accept it as a spare part.
4. Next design work: the body (counterweight shell, side decks, cab, hood) and the electronics layout.

**Environment notes**
- CAD and MuJoCo: `/tmp/sw-venv`, with `LD_LIBRARY_PATH=/tmp/sw-tools/root/usr/lib/x86_64-linux-gnu`.
- Viewer check: `FONTCONFIG_FILE=~/.cache/arm-design-tools/fonts.conf LD_LIBRARY_PATH=~/.cache/arm-design-tools/syslibs/extracted/usr/lib/x86_64-linux-gnu NODE_PATH=/tmp/pw/node_modules node check_viewer.cjs`. It takes about 2.5 min with software WebGL (7 to 13 min since the body was added).
- This workspace has OCC 7.8, not the 7.9 that built X1 first. The re-exported STEPs of the unchanged parts (X102, J901/J909 right) differ only in their headers and tessellation; their volumes are identical.
- The shared handoff tools (get_task_handoff / update_task_handoff) and the workspace-service tools were not available, so this file is the handoff.

## X1 swing concept R3: against sway, no custom metal (2026-11-03, drawings only)

**Status (updated in Round 14):** R3 is now issue 3 and is modelled; see the Round 14 section above. The text below describes issues 1–2. Some details it gives were changed by the modelling: the drag spring and insert, the Ø20 window, the slide ears, the motor screws and the ring-gear scallops.

**Issue 2 (Round 13): decisions recorded, no geometry change.**
- **Swing motor = the track motor, JGY-370-1260 12 V 200:1 (30 rpm).** The machine uses three of the same motor. Sheet 3 has a data block; the numbers are in `estimates.swing_motor`:
  - turntable speed 7.5 rpm with no load and 5.5 rpm at rated load: a full turn takes 8–11 s;
  - torque 2.35 N·m rated at the turntable, against the 1.6 N·m that R1's sizing needs;
  - 7.8 N·m at stall, which puts 131 N and about 27 MPa on a pinion tooth (Lewis bending);
  - with a 0.6 A driver current limit: about 3.3 N·m and 11 MPa.
- **Slip ring = 6-way 2 A.**
  - Battery, receiver, all three drivers and the swing motor are in the upper, so only the two track motors' 4 leads cross the joint. That leaves 2 rings spare.
  - A track motor stalls at 1.3 A, and each ring is rated 2 A.
  - A 12-way would only be needed for encoders on the track motors (10 circuits), lights or sensors on the chassis, or doubled rings. Sheet 4 has the explanation and the ring allocation.
- **4 new checks**, so there are now 36 R3 checks, all passing:
  - rated swing torque against the sizing need: 1.47 times;
  - tooth-stress margin at stall: 22.8 MPa;
  - margin on the ring current: 0.7 A;
  - spare rings: 2.
- Check entries now have `value` and `unit` instead of `value_mm`.
- The no-load current (about 0.1 A) used for the current-limit estimate is inferred from J9's and R1's estimates; the vendor gives no figure.

**Files** in `X1/swing_concept/`:
- `X1_swing_concept_R3.pdf`, plus `_R3_sheet1.png` to `_sheet4.png`;
- `X1_swing_concept_R3_checks.json`: the estimates, 32 R3 checks and R2's 22 checks, all passing;
- `source/draw_swing_concept_r3.py`, which imports R1 and R2's scripts.

**Sheets:**
1. Section A–A and plan.
2. T101 centre frame (plan, side view, section B–B) and the T104 hub adapter.
3. Swing drive: detail D (pinion on the slide), section C–C, details E (drag pad) and F (ring gear).
4. X-frame from below, detail H (slip ring), assembly order and the bought-hardware list.

**Design (all new parts printed):**
- **T101 centre frame**, 252 × 148 × 33, PETG, printed base-down without supports.
  - Two 8 × 27 ribs at Y ±65 sit under the ARM60 base's 4 M6 bolts (nuts in arm blocks).
  - A hub well Ø60/68 and bulkheads 8 thick; the drag-pad housings merge into the rear hub bulkhead.
  - A motor opening 56 × 48.4, a rear bulkhead with a Ø16 window and the counterweight nuts, and a 10 mm lead slot.
- **T104 hub adapter**: a separate print so T101 needs no supports.
  - Flange Ø59 × 3 on the inner ring and a spigot Ø34.6 in the RU66 bore.
  - It carries R2's slip-ring prongs.
  - Clamped with T101 by 8 × M4 × 20.
- **X103 ring gear** (R1's m1.5 × 80):
  - Its bore is now Ø95.2 on the RU66 outer ring, so it is centred to about 0.1 mm.
  - Held by 6 × M3 × 12 countersunk from below into inserts.
  - Its top face is the drag track.
- **T102 motor slide**:
  - The JGY-370 sits on the slide: 4 × M3 × 6 from below.
  - The slide moves ±2 in the opening. The mesh is set with an 80 g/m² paper strip, then the slide is clamped with 4 × M3 in slots and backed by 2 push screws.
- **T103 drag pads** (×2, at R 53.5, 145°/215°):
  - Each is a printed plunger with Ø8 × 3 felt, pressed by a Ø6 × 12 spring (about 9 N) that an M4 set screw adjusts.
  - Together they give about 0.24 N·m.
- **Bolted joints in plastic**: Ø12 DIN 9021 washers and DIN 6796 spring washers. The RU66 outer ring is on M4 × 30 with nuts under the mount ring (was heat-set inserts).

**Estimates (hand calculations, not FEA):**
- T101 is about 37 × stiffer than a 6 mm deck plate:
  - sag at the counterweight 0.063 mm against 2.37 mm;
  - bounce 63 Hz against 10 Hz.
- Play at the turntable drops from 0.44–0.88° to 0.35–0.60° (3.0–5.2 mm at the bucket 0.5 m out, only on reversing). It assumes the JGY-370 has 1–2° of output play.
- Hub joint: about 400 N per screw and 4.1 MPa under the washers. It opens at about 36 N·m, against 2.9 N·m static.

**Changes to the built X-frame X101 (proposals):**
- R2's slip-ring collar;
- 8 plain Ø4.5 RU66 holes with nuts below, instead of inserts;
- 6 countersunk Ø3.4 holes for the ring gear.

**Waiting on the user:**
1. Review R3.
2. Measure the output play on one of the track motors (the swing uses the same JGY-370); it sets the play budget.
3. After that: the body parts (counterweight shell, side decks, cab, hood) and the electronics layout.
- Settled in Round 13: the swing motor is the track motor, and the slip ring is the 6-way.

**Environment:** the same as R2 (`/tmp/sw-venv` with `LD_LIBRARY_PATH`). The shared handoff tools were still not available, so this file is the local fallback.

## J8 record (unchanged)

The current JGY-370 design is revision J8. Its files have been moved directly into `track_wheel_jgy370/`; the nested revision folder is removed. Build, documentation, package and provenance paths have been updated. The design and existing media are unchanged. Relocation and refreshed-package checks pass; the task is complete.

## Latest user request and folder layout

The user requested moving the remaining revision up one level after deleting the older versions. The current layout is:

- `source/`: build, checking and media scripts; `source/support/` holds required inherited geometry/checking functions.
- `step/`, `stl/`, `images/`, `references/`, `simulation/`: current assets and inputs.
- `README.md`, `ASSEMBLY.md`, `BOM.md`, `3D_preview.html`, `J8_design_review.pdf`, `J8_operation.mp4`: current guides and deliverables.
- `../output/jgy370_J8/`: exported downloads and complete ZIP. Revision identifiers in filenames remain J8.

Earlier cleanup removed YVZD, J1-J7 release folders, obsolete exports and render caches (approximately 1.906 GB). Required geometry modules were retained as a small support library; their names preserve part lineage. The original `track_wheel/` R5 project and the other sibling dependencies must remain in place. The README contains current rebuild commands.

## User requirements and design constraints

- English only in replies and deliverables.
- Preserve overall track size, motor location/holes, chassis mounting points and the one-piece removable motor-to-idler housing.
- User prefers broad continuous side plates, with both ends of every small-wheel axle supported.
- Reference photo: `references/user_continuous_frame.png`. It establishes layout style; retained CAD determines dimensions.
- Overall bounds: min [-154.320508,-73,0], max [154.120006,28,91.141016] mm. Shoes 54 mm wide; nominal drive/idler centres 220 mm; 34 links at 20 mm pitch; 12 sprocket teeth.
- Motor axis X=-110 / Z46.320508 along Y; face Y=-46; motor can points +X. Mounting pattern 33 x 18 mm. Chassis pads X=-60/0/115, Y=-54, Z70.
- Vehicle mass was already asked during J6 and remains unspecified. Do not repeat the question or invent a load rating. Actual X-frame and left motor CAD remain unavailable.

## Current geometry and service

Main geometry: `source/j8_parts.py`; export/check: `source/build_j8.py`.

- J806 printed support frame; J815 inner and J816 outer continuous aluminum side plates. Plates are 4 mm thick, with inner faces 48 mm apart.
- Five J721 steel through-axles, three J722 steel cross ties and ten J723 end spacers. Bearing clamp stack: 4 + 7 + 26 + 7 + 4 = 48 mm. Inner axle engagement 4 mm; outer straight engagement 2.5 mm before countersink.
- Three lower rollers: 36 mm running / 40 mm flange diameter. Two upper rollers: 30 / 34 mm, at X +/-30, Z65.141016. Flange clearance is 1 mm per side. Other diameters need an axle-position and track-path check.
- Outer plate has a 12 mm drive-access hole and a 1 mm rear relief, leaving 3 mm locally. Minimum measured rotating-drive clearance is about 1.202 mm.
- Both plates have a 17.6 x 25.8 mm idler opening, clearing the moving collar from axle-centre X105.8 to X114.0. Drive bearings and sliding idler yoke remain independent; openings are not new bearing seats.
- Remove five M5 axle screws and three M4 tie screws to withdraw the outer plate. Open/remove the chain before wheel removal. For inboard axle removal, remove the housing and keep the axle-head flat upward.
- J711 housing remains one piece: 2.5 mm nominal walls, locally 1 mm over the motor; nominal motor-can clearance 0.8 mm.

## Verification and motion provenance

Completed design checks remain valid for the unchanged geometry:

- Valid single-solid changed STEP parts; connected/watertight printed meshes; full, isolated and paired STEP reimports pass.
- 151 changed-part and 358 paired-reference collision candidates clear; 24 drive angles and three idler positions including both stops clear.
- 19 housing-removal, 12 outer-plate-removal, 45 axle-removal and 30 wheel-removal samples clear; tool access and retained chassis installation checks pass.
- Fifteen sampled motion poses clear. Both actual J624 upper rollers are explicitly checked.
- Viewer: twelve views and controls pass; no page errors or network requests. PDF and media were visually inspected. Video is H.264, 1280 x 720, 25 fps, 676 frames / 27.04 seconds; every frame decodes.
- Previous cleanup rebuilt all 14 generated parts and compared them with saved STEP geometry, checked the 318-instance assembly/envelope and verified unchanged media hashes. See `cleanup_validation.json`.

Motion remains the saved J6 unloaded fixed-frame trace. It uses a generic +/-1.2 Nm servo targeting +/-20 rpm, not motor electrical behavior or a vehicle payload/traction model. No new dynamics simulation or physical footage is claimed. `source/reuse_motion.py` verifies trace and input hashes. `simulation/motion_provenance.json` preserves historical hashes and current input locations. Optional baseline reproduction scripts write separately under `simulation/recomputed_baseline/`.

Relocation checks completed:

- `flatten_validation.json`: 124 files promoted; 116 byte-identical, with only eight intentional documentation/path/provenance changes. Geometry function bodies are unchanged; imports, paths and Python/Node syntax pass.
- Viewer rebuild is byte-identical. Twelve browser views and forward/reverse playback pass, with no page errors or network requests. Models, images, PDF, video and trace are unchanged.
- Refreshed ZIP: 36,814,338 bytes; CRC and all 159 SHA256 entries pass. Fresh extraction has no nested revision directory and passes imports, playback provenance and a byte-identical viewer rebuild without workspace fallback.
- `../output/jgy370_J8/delivery_manifest.json` records package/extraction checks. Whitespace checks pass. Before-move inventory: `/tmp/jgy370_flatten_before.json`; browser result: `/tmp/jgy370_flatten_browser.json`.

## Downloads and next steps

Key downloads under `../output/jgy370_J8/` are `JGY370_J8_complete_EN.zip`, `JGY370_J8_track.step`, `JGY370_J8_side_frame.step`, `JGY370_J8_operation_EN.mp4` and `JGY370_J8_continuous_frame_EN.png`. Standalone PDF, viewer, axle section and proposed chassis are also available.

1. Respond to the user's next feedback. The folder move and refreshed ZIP are complete; no implementation or verification is pending.
2. Respond to subsequent design feedback. No geometry or video regeneration is required for this folder move.
3. Before fabrication, finish shaft/plate/bearing fits, match bearing stacks to cross ties, and validate preload, outer axle engagement, plate bearing stress, printed-frame creep and loaded endurance.
4. Confirm actual motor threads, fastener heads, wiring, thermal/print clearances and actual chassis/left-motor fit. No payload rating is established.

## Workspace and tools

Workspace: `/home/tower/Work/shitian/.worktrees/at/0f6b89f4`.
CAD interpreter: `LD_LIBRARY_PATH=/tmp/v6-cad-libs/extracted/usr/lib/x86_64-linux-gnu OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/venv/bin/python`.
Node: `NODE_PATH=/tmp/j5-preview-tools/node_modules`.

Earlier cleanup log: `/tmp/j8_cleanup_check.log`; prior media/build logs: `/tmp/j8_build.log`, `/tmp/j8_motion.log`, `/tmp/j8_video.log`. Relocation sessions completed: imports/viewer/hash check 90999, browser 17220, packaging 65246, extracted-package check 15029. No manual commit, persistent service or subagent was started. Shared handoff tools are unavailable; this local note is the fallback. Persistent commands must use workspace-service tools, and subagents require explicit authorization.

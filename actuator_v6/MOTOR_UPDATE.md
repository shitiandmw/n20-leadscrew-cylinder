# V6 motor gear replacement

The motor in V6-S, V6-U60 and V6-L now uses the meshed gearbox supplied in
`n20_geartrain (1).zip`. Open `3D_preview.html` and select **Motor gears** to
inspect it. **Extend** and **Retract** run this view at 0.02× playback speed;
leaving the view restores the previous playback speed. Drag to orbit.

## What changed

- Three involute gear meshes, each 18:54 teeth, module 0.09 mm and 20° pressure
  angle. The centre distance is 3.24 mm for each pair, with the archive's tooth
  phases retained.
- Four rigid rotors turn at −27, +9, −3 and +1 times the output speed about
  their own shafts. Both gears on each compound shaft turn together. The
  output wheel and screw share a keyed spindle and rotate together.
- The matching plates, bushings and hollow motor can provide space and support
  for the rotating parts. The motor still occupies the original 10 × 12 mm
  envelope, with its gearbox front face at Z=0 and terminals at Z=−26.5 mm.
- The offline viewer, three assembly STEP files and their scene meshes are
  updated. The external screw lengths remain 55 / 75 / 100 mm. Printed parts,
  circuit, wiring and all non-motor scene geometry are preserved.

The archive's 27:1 tooth counts are illustrative; they are not measured
commercial N20 internals. This update does not change the existing electrical
or load model. The existing V6 display thread above Z=0.7 mm remains a revolved
pitch-ring profile. The optional helical screw and unrelated archive content
are not imported. These metal gearbox internals are not printable replacement
parts or manufacturing drawings. Backlash reversal and load dynamics are not
simulated.

## Files and rebuilding

- `source/n20_geartrain.py` and `source/gear_spec.py`: gearbox geometry and
  phases adapted from the supplied archive.
- `source/n20_screw_motor.py`: V6 motor API, including its retained thread and
  the new keyed output connection.
- `source/build_v6.py --motor-only`: update the three assemblies and validate
  actuator fit while preserving the other scene items and printable files.
- `source/build_viewer.py`: regenerate the self-contained offline viewer.
- `source/check_motor.py`: CAD validity, all 210 motor part pairs at zero pose,
  keyed output connectivity, continuous support clearance, sampled tooth
  contact and moving-body clearance from the delivered preview meshes.
- `source/check_motor_viewer.cjs`: browser checks of shaft pivots, signed
  ratios, reversal, all three lengths and assembly-mode transitions.

With the dependencies described in `README.md`, run:

```sh
python source/build_v6.py --motor-only
python source/build_viewer.py
python source/check_motor.py
node source/check_motor_viewer.cjs
node source/assembly_video.cjs check
python source/check_motor_step.py --variant S
python source/check_motor_step.py --variant U60
python source/check_motor_step.py --variant L
```

`validation.json` records the rebuilt actuator checks. `motor_validation.json`
and `motor_viewer_check.json` record the focused motor checks;
`motor_step_check.json` records the assembly STEP read-back checks.

The motor CAD passes all 210 part-pair checks at the zero pose. Each of the
three tooth meshes passes 2,049 phase samples, and 13,878 moving-body pair
checks pass across the gearbox's axial feature intervals. The delivered
display mesh's largest measured flank gap is 0.000102 mm; its small rounding
overlaps remain below 0.00000016 mm². Continuous rotation envelopes clear all
fixed supports, with a minimum radial clearance of 0.015 mm in this model.
All three complete actuator builds pass their existing fit and motion checks.

The existing assembly video and older overview images predate this motor update; use the
updated interactive preview, STEP assemblies, `images/core_part.png` and `images/motor_gears.png`
for the replacement gear geometry.

# Cat 320 reference arm with V6 leadscrew actuators — revision 2

A **1:12 reference-based model of the Cat 320 reach-boom excavator arm**, mounted on a fixed base with no chassis. The boom is a bent hollow box section, the stick has a compact pivot fork, and the bucket opens toward the machine. Two outside cylinders lift the boom; one cylinder drives the stick and one drives the bucket four-bar.

The V6 actuator architecture is retained, with **separate leadscrew lengths** for the three functions. Matching barrels, rods, end-stop PCBs and internal geometry are regenerated. This replaces the earlier straight plate-link arm; do not mix its structural files with this revision.

Open `3D_preview.html` directly in a browser. It works offline. `step/excavator_arm_assembly.step` is the editable assembly in the reference working pose. The guide, dimension drawing and validation reports are included alongside it.

## Real-machine basis

The manufacturer's Cat 320 technical specifications give the following dimensions. The model preserves all four exactly at 1:12.

| Dimension | Cat 320 reference | This model |
|---|---:|---:|
| Reach boom pin centres | 5700 mm | 475.000 mm |
| R2.9 stick pin centres | 2900 mm | 241.667 mm |
| 1.19 m³ HD pin-on bucket width | 1200 mm | 100.000 mm |
| Bucket tip radius | 1570 mm | 130.833 mm |

Sources: [Finning's Cat 320 product page](https://www.finning.com/en_GB/products/new/equipment/excavators/medium-excavators/126532.html) and [Caterpillar technical specifications](https://s7d2.scene7.com/is/content/Caterpillar/CM20240927-d80d6-c6a9b), pages 4, 5 and 11. Copies and source notes are under `references/`. Manufacturer side views were used to establish the bent boom profile, short stick, twin lift cylinders, pivot arrangement and inward bucket opening.

**This is an adapted model, not factory CAD.** The four dimensions above are published values. Detailed section outlines, pin locations, clevis widths and ground bracket are engineering adaptations estimated from the imagery and fitted to the V6 actuators. The factory cylinder dimensions, complete working envelope and load ratings are not claimed for this model. The fixed base replaces only the original arm-support structure; no vehicle chassis, cab or turret is modeled.

## Resized actuators

| Function | Variant | Quantity | Screw length | Nominal stroke | Pin spacing, closed → open |
|---|---|---:|---:|---:|---:|
| Paired boom lift | V6-B | 2 | 100 mm | 85 mm | 165 → 250 mm |
| Stick crowd | V6-T | 1 | 120 mm | 105 mm | 185 → 290 mm |
| Bucket curl | V6-K | 1 | 75 mm | 60 mm | 140 → 200 mm |

Screw lengths are measured from the gearbox front face to the tip. The V6 relationship is **closed pin spacing = screw length + 65 mm**, and **stroke = screw length − 15 mm**. Keep the stock right-hand M3 × 0.5 thread, Ø8 rod, 16.10 × 14.70 housing section, 6 mm-thick eyes and Ø3.2 eye holes for Ø3 pins. Each end retains 3 mm of mechanical reserve beyond nominal travel. Do not command that reserve.

`actuators/` contains the three matched sets, their individual STEP/STL parts, assembled actuator STEP files, new board Gerbers/KiCad/BOM/placement files, parameters and verification. Print or order two B sets, one T and one K. Select or modify the motor's integrated screw to the specified length; the original 55 mm V6-S screw is not the correct part for these three new sizes. The motor body, gearbox mounting and anti-rotation carrier follow the original V6 design.

The original V6 files in sibling `actuator_v6/` remain unchanged and are source dependencies. Do not substitute an original V6-S PCB into a longer actuator. Its Hall positions and board length would be wrong.

## Coordinates and transmission

Global X points from the base toward the work area, Z is upward and all hinge axes are parallel to Y. Positive angles turn +X toward +Z. Boom coordinates originate at O, stick coordinates at E, and bucket coordinates at H.

| Point | Local frame | X | Z | Purpose |
|---|---|---:|---:|---|
| O | Ground | 0 | 110 | Boom hinge |
| A | Ground | 70 | 75 | Both boom actuator rear eyes |
| B | Boom | 190 | 75 | Both boom actuator rod eyes |
| E | Boom | 475 | 0 | Stick hinge |
| C | Boom | 263 | 116 | Stick actuator rear eye |
| D | Stick | −62 | 14 | Stick actuator rod eye |
| F | Stick | 35 | 36 | Bucket actuator rear eye |
| J | Stick | 192 | 16 | Rocker hinge |
| H | Stick | 241.667 | 0 | Bucket hinge |
| R | Rocker, origin J | 52 | 0 | Bucket rod eye and coupler pin |
| Q | Bucket | 32.889 | −11.971 | Coupler pin |
| T | Bucket | −104 | −79.381 | Cutting-tip reference |

Boom cylinders are at Y = −42 and +42; their pin-to-pin lengths are identical at every pose. The other cylinders are centred at Y = 0. The four-bar lengths are J–R = 52, R–Q = 65 and H–Q = 35 mm. The fixed J–H link is 52.180 mm. Assemble the illustrated branch; the other circle-intersection branch is not the intended digging mechanism.

**Electrical A+ / B− extends:** the boom rises, the stick moves inward and the bucket cutting lip curls upward toward the machine. Reverse polarity reverses these actions. Electrical terminal names A/B are separate from the mechanical point labels.

A right-hand M3 × 0.5 screw makes **2 revolutions per millimetre**. With the screw held axially and the nut prevented from turning, clockwise rotation **viewed from the rod end toward the motor** extends the rod. Local screw angle is −2π·stroke/0.5 with +Z toward the rod. Full nominal strokes require 170 / 210 / 120 revolutions for boom / stick / bucket. The original screw mesh uses pitch rings rather than a helical manufacturing thread; the viewer applies the correct rotation relationship and adds a rotation witness.

Nominal joint ranges are approximately 1.72–69.17° boom elevation, −39.26 to −150.80° stick relative to boom, and 131.11 to 12.86° bucket relative to stick. The bucket body's zero orientation has its mouth and teeth toward −X. The reference pose has boom 31°, stick −114° relative to boom and the cutting lip just above Z = 0.

Use three reversible 6 V control functions, with the two boom units coordinated as one mechanical axis. They must never be commanded to unequal lengths. Match their physical end stops before powered operation; the V6 has no external position-feedback output. The viewer's exact position sliders are geometric controls, not a supplied hardware position controller.

## Mounts, parts and assembly

The fixed plate is **165 × 164 × 12 mm**, X = −55 to +110, Y = ±82. Four Ø6.6 holes at (X,Y) = (−40,±65), (95,±65) accept M6 fixing bolts. The boom root is 110 mm above the mounting plane. The compact root support uses paired bearing cheeks and gussets; boom lift cylinders have their own lower clevises.

Main pivots O, E and H use **Ø6 steel shafts in Ø6.2 holes**. Cylinder and linkage pivots use **Ø3 shafts in Ø3.2 holes**. The boom box is 48 mm wide, the stick 32 mm wide, and the bucket 100 mm wide. Nominal box walls are 4 mm. The distal boom fork is open over its last 70 mm to clear the stick through its full range. Its bearing cheeks remain on either side of the stick.

There are eight structural STL files: fixed base, boom, stick, two rockers, two couplers and bucket. These are model meshes with valid closed solids. **The 509 mm-long monolithic boom needs a large printer or a separately engineered split/joint before manufacture**; do not mistake a watertight STL for a ready-to-load printed assembly. Individual structural STEP files preserve assembly coordinates. STLs are laid onto Z = 0 for slicing. The hollow boxes have trapped internal cavities; review the intended printing process and supports before fabrication.

| Shaft | Quantity | Location |
|---|---:|---|
| Ø6 × 82 | 1 | O |
| Ø6 × 60 | 2 | E,H |
| Ø3 × 36 | 6 | A-left/right, B-left/right, C,F |
| Ø3 × 42 | 1 | D |
| Ø3 × 58 | 1 | J |
| Ø3 × 70 | 2 | R,Q |

Use two collars per shaft: six Ø6-bore collars with nominal Ø11 × 4 envelopes and twenty Ø3-bore collars with nominal Ø7 × 3 envelopes. Set screws are omitted from the model. Collars have 0.3 mm running clearance to the outer faces. Confirm the actual bought collars fit those envelopes.

| Spacer, OD × ID × length | Quantity | Location |
|---|---:|---|
| 9 × 6.2 × 2.8 | 2 | O |
| 9 × 6.2 × 1.8 | 4 | E,H |
| 7 × 3.2 × 4.8 | 12 | Both sides of the six eyes at A-left/right, B-left/right, C,F |
| 7 × 3.2 × 6.8 | 2 | D |
| 7 × 3.2 × 1.8 | 2 | J |
| 7 × 3.2 × 14.8 | 2 | R, actuator eye to rockers |
| 7 × 3.2 × 0.8 | 4 | R,Q, rockers/horns to outer couplers |

1. Anchor the fixed base to a rigid surface using four M6 bolts and suitable washers/nuts. Keep the pivot shafts horizontal and parallel.
2. Fit the boom at O, the stick at E and the bucket at H with the listed spacers and collars.
3. Fit paired rockers on J in Y bands 18–24 and −24 to −18. Fit outer couplers at R and Q in bands 25–30 and −30 to −25. The bucket mouth must face the base in the reference pose.
4. Assemble and calibrate the four matching V6 actuators. Fit the B pair at A–B, T at C–D and K at F–R, using the eye spacers. Keep the two B strokes equal.
5. Route flexible two-core cables with service loops at the moving pivots. External cable loops are not routed or collision-checked by this model.
6. Jog unloaded at low speed, check all three motion directions and verify actual end-stop reversal. Calibrate the paired boom endpoints together before combined motion.

The working envelope includes positions below Z = 0, just as a real excavator digs below its support surface. The viewer shows the mounting plane and leaves the working area visible. On a solid-floor demonstration rig, restrict those positions or mount beside a clear recess/bench edge. Do not sweep the model through a solid floor.

## Validation and limitations

`validation.json` records reference dimensional ratios, 461 transmission samples, actuator/link closure, inward bucket orientation, upward lip motion during curl, and exact-solid interference checks at **134 combined configurations**: 125 nominal grid points, eight mechanical-reserve corners and the reference pose. It also samples the tooth envelope at 9,261 configurations. Sampling is not a proof of continuous collision freedom.

`actuators/validation.json` records fresh internal CAD and STL checks for B, T and K. `actuators/electronics/pcb/validation.json` records board design-rule checks and independent Gerber readback. All three regenerated boards have zero DRC errors and zero readback mismatch. Electronics topology and magnetic sensing assumptions are inherited from V6; this is not a new powered hardware or thermal test.

`source/export_report.json` records structural single-solid, watertight STL and STEP import checks. `browser_validation.json` records independent Python/JavaScript pin-position comparison, controls, offline rendering and mobile layout.

The published Cat dimensions do not transfer its forces or payload to this model. Motor gearbox axial capacity, long printed rods, joint deflection, print process, creep, real end stops, synchronized boom drive and external wiring require physical prototype testing. No payload rating is supplied.

## Rebuild

Keep `excavator_arm/` beside `actuator_v6/`. Use Python 3.11 and the packages in `source/requirements.txt`. CadQuery needs the appropriate system OpenGL libraries. Node/Playwright with Chromium is needed only for the viewer checks.

```sh
python excavator_arm/source/build_actuators.py
python excavator_arm/source/build_arm.py
python excavator_arm/source/validate_arm.py
python excavator_arm/source/build_viewer.py
python excavator_arm/source/build_guide.py
python excavator_arm/source/package_delivery.py
```

`source/kinematics.py` is the single dimensional reference and supplies the viewer configuration. Original V6 source files are imported read-only; board caches and generated files are redirected into `actuators/`. The package carries the bundled three.js MIT license and identifies manufacturer reference images separately.

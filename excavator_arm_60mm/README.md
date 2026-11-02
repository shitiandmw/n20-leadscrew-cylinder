# Cat 320 arm — separate 60 mm stroke edition, R4

A compact **1:15 Cat 320 reference arm** with four identical V6-U60 electric actuators, each with **60 mm nominal stroke**. The boom is a bent hollow box section, with twin outside lift cylinders, a shorter stick and an inward-opening bucket. It fixes to a ground plate; there is no chassis.

This is an additional version. The earlier `excavator_arm/` R2 model stays at 1:12 with 85/105/60 mm strokes. Do not mix structural parts between versions.

Open **`3D_preview.html`** in a browser for the offline interactive model. Use `step/excavator_arm_assembly.step` for the complete CAD assembly, `stl/` for eight structural meshes, the sibling `actuator_v6/` folder for the one common actuator, V6-U60, with its parts and board, and `build_guide.pdf` plus `dimension_sheet.pdf` for illustrated documentation.

## What changed

| Dimension | R2, 1:12 | New 60 mm edition, 1:15 |
|---|---:|---:|
| Boom, pin to pin | 475 mm | 380.000 mm |
| Stick, pin to pin | 241.667 mm | 193.333 mm |
| Bucket width | 100 mm | 80.000 mm |
| Bucket tip radius | 130.833 mm | 104.667 mm |
| Boom pivot above mounting plane | 110 mm | 88 mm |
| Ground plate | 165 × 164 × 12 mm | 132 × 164 × 10 mm |
| Actuator strokes, boom / stick / bucket | 85 / 105 / 60 mm | 60 / 60 / 60 mm |
| Leadscrews, boom / stick / bucket | 100 / 120 / 75 mm | 75 / 75 / 75 mm |
| Distinct actuator/board sets | 3 | 1 |

The four primary reference dimensions are **20% smaller**. Mounting pins were relocated to fit the fixed 140–200 mm actuator length. The boom lift brackets and stick tail fork were reshaped. Bucket shell, teeth and wear strips were reduced to match the new bucket dimensions.

Hardware does not scale uniformly: the V6 motor, Ø8 rod, housing section, Ø3/Ø6 shafts, 48 mm boom width, 32 mm stick width, lateral clevis spacing and 4 mm box walls remain full size. The bucket rocker/coupler/horn remain 52/65/35 mm to use the full 60 mm stroke without a linkage toggle. Its cylinder base sits just behind the main stick hinge, on the upper lug. These are documented adaptations, not factory CAD.

## R4 lift-mount reinforcement

The previous lift mounts projected from narrow bridges near the upper edge of the boom. Collision-free movement did not establish their printed strength. R4 changes the attachment geometry to give the cylinder loads a wider path into the boom:

- Upper pin B moves from (117.372, 87.808) to (150, 60) mm in boom coordinates: **32.628 mm forward and 27.808 mm lower**.
- Each clevis cheek is **8 mm thick instead of 5 mm**, with a 10 mm boss radius instead of 7 mm. The nominal radial material outside the Ø3.2 pin hole is 8.4 mm instead of 5.4 mm.
- Rounded, broad saddle feet merge into a **solid cross-web through the hollow boom**, joining both sides. The cross-web lies above/forward of the incoming rods and clears their motion.
- A **single Ø3 × 126 mm steel through-pin** carries both upper eyes. Retaining collars sit outside the saddles; there are no inaccessible inner collars against the boom walls. This is a shaft with collars, not a bolt to tighten across the moving eyes.
- Lower anchors A move from (55, 53) to (47.277, 55.771) mm in ground coordinates. This small shift preserves the **2–69° nominal boom range** with the same 60 mm stroke. The plate footprint and anchor-bolt pattern remain the same.

For an existing R3 build, use the **new boom and new fixed base together**, plus the longer B cross-pin and two fewer Ø3 collars. Stick, bucket, rocker/coupler geometry and U60 actuators retain their dimensions. See `images/lift_mount_comparison.png` for the detail comparison.

These are geometric improvements, **not a measured strength increase or a payload rating**. The supplied boom STL lies on its broad side, placing the main arm-plane load directions within the printed layers. Continuous perimeters around the pin bosses and saddle roots, local print density, layer adhesion, material and actual shaft fit still need prototype validation. Do not rely on sparse infill alone at the mounts. Do not clamp the paired eyes solid when fitting the collars.

## Common actuator

Build **four copies of V6-U60**: two for boom lift, one for stick crowd and one for bucket curl. Every copy has:

- 75 mm right-hand M3 × 0.5 leadscrew, measured from gearbox face to screw tip.
- 60 mm nominal stroke and 140–200 mm mounting-pin spacing.
- 3 mm mechanical reserve beyond each endpoint; reserve is not commanded travel.
- V6 16.10 × 14.70 mm housing section, Ø8 rod, 6 mm eye thickness and Ø3.2 eye holes.
- The same barrel, caps, rod, rod eye, internal parts and end-stop board.

Print/order four of each actuator part and four common boards. V6-U60 is one of the three standard lengths in the sibling `actuator_v6/` folder, next to V6-S and V6-L; only V6-U60 fits this arm. U60 uses the same axial dimensions as R2's bucket actuator.

- Parts: `actuator_v6/stl/V6-U60/` and `actuator_v6/step/V6-U60/`.
- Board: `actuator_v6/electronics/pcb/V6-U60/`, with `actuator_v6/electronics/pcb/actuator_v6_U60_gerbers.zip` ready to upload to the board maker. The Hall switches sit at both ends of the board.
- Guides: `actuator_v6/BOM.md` and `actuator_v6/ASSEMBLY.md` list V6-U60 beside the other lengths. `actuator_v6/3D_preview.html` shows it (V6-U60 button) with its schematic linked to the board and a drive simulation.
- Boom pair: measure each actuator's ends after assembly and use the two closest units for the boom.

## Motion and transmission

X points forward into the working area, Z points upward, and all hinges are parallel to Y. All coordinates are millimetres. Positive angles turn +X toward +Z.

| Joint | Nominal range, retracted → extended | Angular travel |
|---|---:|---:|
| Boom elevation | 2.00° → 69.00° | 67.00° |
| Stick relative to boom | -48.92° → -143.86° | 94.94° |
| Bucket relative to stick | 131.11° → 12.86° | 118.24° |

The boom and bucket retain approximately the R2 angular travel. The stick has 94.9° of travel versus about 111.5° in R2. Full working reach is smaller. Relocating the cylinder pins changes mechanical advantage; equal actuator thrust does not imply equal payload.

**Extension raises the boom, crowds the stick and curls the cutting lip upward toward the machine.** The bucket mouth faces the base in the reference pose. Default boom/stick angles are 31°/−114°; the cutting tip is 1.27 mm above the mounting plane.

Electrical A+ / B− extends, and reverse polarity retracts. Clockwise screw rotation **viewed from the rod end toward the motor** extends the non-rotating nut/rod. M3 × 0.5 means two revolutions per millimetre, or **120 revolutions for every full stroke**. The mesh has schematic pitch rings; the viewer applies the correct rotation relation with a visible witness.

Use three reversible 6 V control functions. The two boom actuators operate as one axis and **must stay equal in length**; matching voltage alone does not establish position synchronisation. Match actual endpoints and verify unloaded coordinated movement. Original V6 circuitry has no external position-feedback output, and the viewer is not a hardware position controller.

| Point | Local frame | X | Z | Function |
|---|---|---:|---:|---|
| O | Ground | 0.000 | 88.000 | Boom hinge |
| A | Ground | 47.277 | 55.771 | Both boom rear eyes |
| B | Boom | 150.000 | 60.000 | Both boom rod eyes |
| E | Boom | 380.000 | 0.000 | Stick hinge |
| C | Boom | 230.000 | 88.000 | Stick rear eye |
| D | Stick | -40.000 | 8.000 | Stick rod eye |
| F | Stick | -13.333 | 36.000 | Bucket rear eye |
| J | Stick | 143.667 | 16.000 | Rocker hinge |
| H | Stick | 193.333 | 0.000 | Bucket hinge |
| R | Rocker | 52.000 | 0.000 | Bucket rod eye and coupler |
| Q | Bucket | 32.889 | -11.971 | Coupler pin |
| T | Bucket | -83.200 | -63.505 | Cutting tip |

Boom cylinders sit at Y = ±42 mm; stick/bucket cylinders at Y = 0. Link lengths J–R / R–Q / H–Q = 52 / 65 / 35 mm. J–H = 52.180 mm. Assemble the illustrated circle-intersection branch.

## Mounts and assembly

The base spans X = −44 to +88 mm and Y = ±82 mm. Four Ø6.6 fixing holes at (X,Y) = (−32,±65), (76,±65) accept M6 bolts. Root pivot O is 88 mm above the mounting plane. Main pivots have Ø6.2 holes for Ø6 steel shafts; remaining pivots have Ø3.2 holes for Ø3 shafts.

The final 90 mm of the boom is an open fork around the stick and its actuator. The stick tail has an open centre extending to X = −10 mm to clear the incoming rod at full crowd. Main root bearing material remains intact.

| Shaft | Quantity | Location |
|---|---:|---|
| Ø6 × 82 mm | 1 | O |
| Ø6 × 60 mm | 2 | E, H |
| Ø3 × 36 mm | 4 | A-left/right, C, F |
| Ø3 × 126 mm | 1 | Shared B pin through both lift eyes and the boom |
| Ø3 × 42 mm | 1 | D |
| Ø3 × 58 mm | 1 | J |
| Ø3 × 70 mm | 2 | R, Q |

Use two collars per shaft: six Ø6-bore collars (nominal Ø11 × 4 mm envelope) and eighteen Ø3-bore collars (Ø7 × 3 mm). Collars have 0.3 mm running clearance to outer faces. Their actual set screws are not modeled.

| Spacer, OD × ID × length, mm | Quantity | Location |
|---|---:|---|
| 9 × 6.2 × 2.8 | 2 | O |
| 9 × 6.2 × 1.8 | 4 | E, H |
| 7 × 3.2 × 4.8 | 12 | Both sides of six eyes at A/B pairs, C, F |
| 7 × 3.2 × 6.8 | 2 | D |
| 7 × 3.2 × 1.8 | 2 | J |
| 7 × 3.2 × 14.8 | 2 | R eye to rockers |
| 7 × 3.2 × 0.8 | 4 | R, Q to outer links |

1. Anchor the base to a rigid surface using four M6 bolts. Keep shaft axes parallel.
2. Install boom O, stick E and bucket H with the specified shafts, spacers and collars.
3. Fit rockers at J in Y bands 18–24 and −24 to −18; outer links at R/Q in bands 25–30 and −30 to −25.
4. Install two U60 actuators at A–B using the common B cross-pin and outside collars; install one each at C–D and F–R. Keep both boom strokes equal.
5. Provide flexible external cable loops and collar running clearance.
6. Jog unloaded; verify direction, physical endpoint reversal and coordinated boom motion before combined movement.

## Verification and limits

- **134 combined configurations**, 1021 distinct exact-solid intersection checks; zero interference at the sampled poses. Includes 125 independent nominal grid combinations, eight reserve corners and the reference pose.
- **461 transmission samples**; pin closure error at most 9.95e-14 mm. Correct motion direction and minimum four-bar transmission angle 33.16° including reserve.
- Eight structural STLs are watertight, consistently wound and single-component; individual STEP and the 96-solid assembly round trips pass.
- The U60 actuator internal/mesh checks and board checks pass. Its PCB has zero DRC errors and zero independent Gerber readback mismatch.
- Browser checks compare 125 Python/JavaScript cases and actual rendered cylinder endpoints, including all four cylinders, controls, animation, mobile layout and offline operation.

Sampled tip envelope: X = 82.1…606.8 mm, Z = -195.4…524.7 mm. Below-plane positions represent digging. A solid-floor demonstrator needs restricted travel or a recess/bench edge. The sampled checks do not prove continuous collision freedom.

The monolithic boom STL measures **414.0 × 118.0 × 116.0 mm**; the stick measures **259.3 × 63.0 × 32.0 mm**. Both require review against the actual printer volume. The boom needs a large printer or an engineered split. Closed box cavities need process/support planning. No physical print, fit, powered-operation or load test has been performed. Gearbox thrust capacity, rod deflection, joint alignment, creep, real Hall switching points, boom synchronisation and external wiring still need physical validation. No payload rating is supplied.

## Manufacturer references and rebuild

The Cat 320 dimensions are boom 5700 mm, R2.9 stick 2900 mm, bucket width 1200 mm and tip radius 1570 mm, from Caterpillar specifications pages 4, 5 and 11. Full URLs and downloaded reference material are in `references/SOURCES.md`. Images/PDF remain © Caterpillar; this model is not manufacturer-approved CAD.

Keep `excavator_arm_60mm/` beside `actuator_v6/`. Use Python 3.11 and `source/requirements.txt`, CadQuery system libraries, plus Node/Playwright with Chromium for browser checks.

```sh
python excavator_arm_60mm/source/build_actuators.py
python excavator_arm_60mm/source/build_arm.py
python excavator_arm_60mm/source/validate_arm.py
python excavator_arm_60mm/source/build_viewer.py
node excavator_arm_60mm/source/check_viewer.cjs
python excavator_arm_60mm/source/build_readme.py
python excavator_arm_60mm/source/build_guide.py
python excavator_arm_60mm/source/package_delivery.py
```

`source/kinematics.py` is the dimensional authority. The actuator is the standard V6-U60: `build_actuators.py` builds it in `actuator_v6/` with the V6 scripts and checks its screw, stroke, closed length, CAD checks and board checks against `kinematics.py`. The arm's structural CAD stays inside this folder. `actuator_v6/README.md` lists the actuator's preview, schematic and render commands. The ZIP includes checksums, sources, the three.js MIT license, references and validation reports.

# Current status

Revision 2 is a Cat 320 reference-based arm at 1:12, fixed directly to a base with no chassis. The redesigned structures, four resized V6 actuators, matching PCBs, CAD exports, documentation and offline viewer are complete. Geometry, actuator, PCB and final browser verification pass. The delivery archive is `output/excavator_arm_cat320_r2.zip`, generated and CRC-verified by `source/package_delivery.py`.

## User requirements and corrections

- The user initially asked for an excavator arm based on the V6 short actuator, with correct dimensions, motion and transmission, and no vehicle chassis.
- The user rejected the first straight plate-link model, specifically its mounting plates and bucket orientation. That model is superseded; its earlier tests do not establish acceptance of the current task.
- The user then explicitly authorized changing leadscrew lengths to preserve real excavator proportions. This enabled different cylinder lengths rather than three identical V6-S units.
- Current geometry follows the Cat 320 bent box boom, shorter stick, twin outside boom cylinders and bucket opening toward the machine. The fixed base replaces the chassis arm supports.
- Four primary dimensions are exact at 1:12: boom 475 mm, stick 241.667 mm, bucket width 100 mm, tip radius 130.833 mm. Detailed section profiles, pin locations and fixed mounts are documented adaptations, not factory CAD.
- Boom cylinders: two V6-B, 100 mm screws, 85 mm stroke, 165–250 mm pin spacing. Stick: one V6-T, 120 mm screw, 105 mm stroke, 185–290 mm spacing. Bucket: one V6-K, 75 mm screw, 60 mm stroke, 140–200 mm spacing.
- Extension raises the boom, crowds the stick and curls the cutting lip upward. A+ / B− extends. The right-hand M3 × 0.5 screw rotates clockwise viewed from the rod end toward the motor to extend.

## Reference evidence

- Finning Cat 320 product page: https://www.finning.com/en_GB/products/new/equipment/excavators/medium-excavators/126532.html
- Manufacturer specifications: https://s7d2.scene7.com/is/content/Caterpillar/CM20240927-d80d6-c6a9b
- PDF pages 4 and 5 give the 5.7 m boom, R2.9 stick and 1570 mm bucket tip radius. Page 11 gives the 1.19 m³ HD bucket width as 1200 mm.
- Manufacturer side image `Caterpillar/320_NA_exterior_018` shows the arm unobstructed. Reference PDF, photographs, rendered pages and full URLs are in `references/`.

## Implementation and files

- `source/kinematics.py`: single dimensional reference, three independent axis equations, reference pose and viewer configuration.
- `source/build_arm.py`, `cad_common.py`: new hollow box structures, clevises, inward bucket, smooth shafts/spacers/collar envelopes and structural STEP/STL export.
- `source/build_actuators.py`: imports original V6 parametric source read-only, adds B/T/K variants, redirects all caches/outputs to `actuators/`, regenerates matching mechanical parts and PCBs.
- `source/validate_arm.py`: reference ratios, closure, direction, bucket-facing/curl checks, 134-pose exact-solid sampling and tooth envelope.
- `source/build_viewer.py`, `viewer_template.html`: self-contained three.js model, three different stroke maxima, coordinated boom pair, original internal geometry regenerated at each length, orthographic side view and embedded manufacturer reference.
- `source/check_viewer.cjs`: Playwright checks including actual rendered cylinder pin transforms against Python pin coordinates.
- `source/build_guide.py`: actual CAD silhouette drawing, side-by-side reference comparison and four-page A4 guide.
- `source/package_delivery.py`: `output/excavator_arm_cat320_r2.zip`, checksum manifest and archive CRC verification.
- Main assembly: `step/excavator_arm_assembly.step`, 95 exterior/mechanical solids. Full individual actuator assemblies including internals are under `actuators/step/V6-B`, `V6-T`, `V6-K`.
- Eight current structural STL/STEP parts remain. Superseded structural files and copied V6-S print parts were removed. The old ZIP is `output/excavator_arm_v1_superseded.zip`; do not deliver it as current.
- Original sibling `actuator_v6/` is unchanged. Repository base is `a68cacd`; task changes are uncommitted.

## Verification and limits

- Arm PASS: 134 combined poses, 997 distinct exact-solid intersections, zero overlap. Includes 125 nominal grid combinations, all eight ±3 mm reserve corners, and the reference pose.
- Transmission PASS: 461 samples; maximum pin closure error 1.42e-13 mm; correct derivative signs throughout reserve travel; minimum four-bar transmission angle 33.156°.
- Bucket faces toward the machine and its cutting lip rises throughout curl with the boom/stick in the reference pose.
- All eight structural STLs are watertight, single-component and consistently wound; individual STEP and 95-solid assembly round trips pass.
- Resized B/T/K actuator internal CAD and STL checks all pass. All three boards have zero DRC errors and zero independent Gerber readback mismatch.
- Browser PASS: 125 cases; Python/JavaScript pin discrepancy 5.98e-13 mm; actual rendered cylinder pin discrepancy 3.31e-13 mm. All four cylinders, endpoints, cameras, overlay, internals, animation, reference reset, offline operation and 390 px mobile layout pass with no page errors/network requests.
- Final browser rerun (session 32643) exited successfully after the perspective camera adjustment. The overview clearly shows the inward-opening bucket. All four guide pages were visually reviewed; no layout issues were found. `git diff --check` passes, and original `actuator_v6/` has no changes.
- The first R2 collision check found the stick touching the closed end of the boom at both angular limits. The distal fork opening was increased to 70 mm while retaining side bearing cheeks; targeted checks and the final full grid pass.
- The sampled tooth envelope spans X 73.3–786.8 mm and Z −246.2–715.6 mm. Below-Z=0 poses intentionally represent excavation; a solid-floor demonstrator must restrict them or provide a recess/bench edge.
- The monolithic boom is 509 mm long, requiring a large printer or an engineered split. Closed box cavities require print-process planning. This is not a physical fit/load validation, a continuous collision proof or a payload rating. Paired boom endpoints, external cable loops and actual collar set screws need physical checks.

## Delivery and future work

1. Deliver `output/excavator_arm_cat320_r2.zip` and `excavator_arm/3D_preview.html` with Agent Tower download directives. The archive includes CAD, meshes, regenerated actuators and boards, drawings, references, sources and validation reports.
2. If any files change, rerun `source/package_delivery.py` to refresh the checksums and verified archive; repeat relevant checks for geometry or motion changes.
3. For physical prototyping, plan the 509 mm boom manufacture, coordinate the two boom actuators and follow the guide to establish unloaded operation before load tests. Physical fit and load testing remain future work.

## Environment and handoff availability

Use `/tmp/venv/bin/python`. CadQuery needs `LD_LIBRARY_PATH=/tmp/v6-cad-libs/extracted/usr/lib/x86_64-linux-gnu`. Playwright is at `/tmp/v6-preview-tools/node_modules`; set `NODE_PATH` for browser checks. These are local environment conveniences; portable requirements are in `source/requirements.txt`.

No sub-agents or long-running workspace services were used. All commands are finite builds/tests. Agent Tower handoff MCP tools are unavailable; this local note is the fallback, not a claimed shared-note update. Task ID: `9fdc882d-ea1f-456e-abb7-d1579ed8c7bd`.

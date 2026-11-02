# Current status

R4 of the 60 mm stroke excavator arm is complete in `excavator_arm_60mm/`. The user identified weak projecting upper lift mounts in R3 and asked to move them forward for a better printed attachment. Geometry, CAD, browser preview, drawings, comparison image and the five-page guide have been updated. Final validation completed with exit code 0 and a PASS report. Delivery archive: `output/excavator_arm_cat320_60mm_r4.zip`, built and CRC-verified by `source/package_delivery.py`.

## Requirements and design decisions

- Arm only, fixed to the ground, with no chassis. Four identical V6-U60 actuators: 75 mm M3 × 0.5 screws, 60 mm nominal stroke, 140–200 mm pin spacing and 3 mm reserve at each end.
- Preserve the separate 1:12 R2 model. Current 1:15 reference dimensions remain boom 380 mm, stick 193.333 mm, bucket width 80 mm and tip radius 104.667 mm.
- Upper lift pin B moves from (117.372, 87.808) to (150, 60) mm in boom coordinates: 32.628 mm forward and 27.808 mm lower.
- Replace the narrow bridges with broad rounded saddles and a solid cross-web through the hollow boom, joining both sides. Cheeks increase from 5 to 8 mm, boss radius from 7 to 10 mm; Ø3.2 holes remain.
- Both upper eyes share one Ø3 × 126 mm steel cross-pin, retained by two outside collars. Separate inner collars would hit the boom walls; they were removed in the final design. The collar is a retainer, not a clamp that locks the moving eyes.
- Lower anchors move from (55,53) to (47.277,55.771) mm in ground coordinates. This preserves the 2–69° boom range with unchanged actuators. The base plate footprint and bolt holes remain the same.
- Existing R3 builders must replace the boom and base together and use the new B pin/two fewer Ø3 collars. The other six structural STLs match R3 byte-for-byte. Actuator and PCB files are unchanged.
- Broader load paths are a geometric improvement, not a measured strength increase or a payload rating. Physical print, fit and load tests remain unperformed.

## Important files

- `source/kinematics.py`: authoritative pins, dimensions and motion.
- `source/build_arm.py`: revised saddles, cross-web, lower clevises and single B cross-pin.
- `source/build_readme.py`: generates README including R4 changes, revised BOM and print limitations.
- `source/build_guide.py`: generates drawings/comparisons and five-page guide; page 5 documents the mount changes.
- `source/check_viewer.cjs`: browser checks and close-up view. The screenshot helper hides UI for the mount detail.
- `images/lift_mount_comparison.png`: before/after at the same pose and camera. `references/r3_mount_before.png` preserves the historical view.
- `step/excavator_arm_assembly.step`, `stl/`: revised model; assembly has 92 solids.
- `3D_preview.html`: offline standalone viewer, about 16.5 MB since its 2026-10-29 rebuild (see the last section).
- `source/package_delivery.py`: target `output/excavator_arm_cat320_60mm_r4.zip`; retains R3 ZIP.
- R3 delivered archive remains `output/excavator_arm_cat320_60mm_r3.zip`. Temporary R3 reference files are `/tmp/arm60_r3_before/`.

## Verification completed

- Final R4 report (clean exit, session 18232): PASS, 134 sampled configurations, 990 distinct exact-solid intersections, zero overlap; includes ±3 mm reserve corners.
- Transmission: 461 samples; closure error 9.95e-14 mm; correct direction and minimum four-bar transmission angle 33.156°.
- Eight structural STL/STEP checks pass; 92-solid assembly round trip passes. Boom STL now measures 414 × 118 × 116 mm.
- Browser PASS: 125 Python/JavaScript cases, pin discrepancy 2.56e-13 mm, actual cylinder-pin discrepancy 3.06e-13 mm. Four cylinders, equal boom lengths, 60 mm strokes, controls, internals, cameras, animation, offline and mobile checks pass.
- Existing U60 mechanical/PCB checks remain applicable: 282 R2/original V6/current actuator files match the start-of-turn baseline in `/tmp/arm_r4_unchanged_baseline.json`.
- Five PDF pages have text within page bounds. The new page 5 and mount comparison were visually reviewed. Source/document whitespace checks pass; generated STEP files contain exporter-produced trailing spaces.

## Delivery and future work

1. Deliver/open the R4 ZIP, offline preview and `images/lift_mount_comparison.png`. R3 remains in its previous ZIP and R2 remains in its separate folder.
2. For an existing build, use the revised boom and base together with the new shared cross-pin. Follow the updated BOM and guide; six retained structural STLs and all U60 parts remain compatible.
3. Establish physical fit, coordinated unloaded boom motion and print strength before load tests. No payload rating or measured strength multiplier is claimed.
4. After future geometry changes, rerun relevant validation and refresh the package/checksums. Final reports are authoritative; temporary diagnostic logs are not delivery artifacts.

## Environment and physical limits

Use `/tmp/venv/bin/python` and `LD_LIBRARY_PATH=/tmp/v6-cad-libs/extracted/usr/lib/x86_64-linux-gnu` for CadQuery. Playwright uses `NODE_PATH=/tmp/v6-preview-tools/node_modules`. Builds/tests are finite; no services or sub-agents were used. Shared handoff MCP tools are unavailable; this local note is the fallback. Task ID: `9fdc882d-ea1f-456e-abb7-d1579ed8c7bd`.

The monolithic 414 mm boom needs a large printer or an engineered split. The supplied boom STL lies on its broad side; continuous perimeters/local density and layer bonding matter at the mounts. Maintain equal boom actuator lengths; V6 has no external position feedback. Below-ground digging poses need a clear recess or restricted movement on a solid-floor demonstrator. External wiring and real collar set screws are outside the collision model.

## The actuator moved into actuator_v6 (2026-10-29, V6 session, task `f1790fb0`)

The user asked for the general custom-length actuator, V6-U60, to move into the V6 folder so that V6 shows three versions. The arm geometry is unchanged.

- **Where the actuator is now:** V6-U60 is a standard V6 length, registered in `actuator_v6/source/layout.py` between V6-S and V6-L.
  - Parts: `actuator_v6/stl/V6-U60/`, `step/V6-U60/`.
  - Board: `actuator_v6/electronics/pcb/V6-U60/` and `actuator_v6_U60_gerbers.zip`.
  - Renders: `actuator_v6/images/*_U60.png`.
  - Data: its entries in `parameters.json` and `validation.json`.
  - V6's `README.md`, `BOM.md`, `ASSEMBLY.md`, schematic and `3D_preview.html` all cover V6-S, V6-U60 and V6-L.
- **Removed:** `excavator_arm_60mm/actuators/`. Every file there was a duplicate of the new V6 files or a document merged into V6's.
  - V6's build reproduces the STL, part STEP, Gerber and BOM/CPL files and the validation report exactly.
  - The assembly STEP differs only in the order of its colour records, and the KiCad file only in its edit timestamps.
- **Arm scripts changed:**
  - `build_actuators.py` now runs V6's `pcb_export.py U60` and `build_v6.py --variant U60`, then checks screw, stroke, closed length, CAD checks and board checks against `kinematics.ACTUATORS`.
  - `build_viewer.py` reads `actuator_v6/source/scene_U60.json.gz`, and stops if it is missing instead of silently leaving out the actuator internals.
  - `package_delivery.py` checks `actuator_v6/validation.json` and `check_U60.json`, and requires `actuator_v6/step/V6-U60/04_rod.step` in the zip.
  - `build_readme.py`, and with it the README, points to `actuator_v6/`.
- **Not rebuilt:** the arm's own `3D_preview.html`. A rebuild would read the V6 scene, whose leadscrew mesh is coarser; nothing else the arm uses changed.
- **Regenerated:** `SHA256SUMS_ARM.txt` and `output/excavator_arm_cat320_60mm_r4.zip`.

## V6 enclosure revision reaches the arm (2026-10-29, V6 session, task `f1790fb0`)

The user asked for the V6 housing to be easier to print and install, and for the cable to be protected so it cannot easily come loose. V6-U60 changed with it; its pin lengths (140–200 mm) and stroke did not.

- **What changed on the actuator:**
  - **Cable clamp:** a new printed `06_cable_clamp` plate sits in a pocket of the rear cap. Its two screws, now M2 × 10, squeeze a 3 mm sleeve over the cable wires, which leave sideways on the board side.
  - **Body:** flat rear face, printed rear end down.
  - **Carrier key:** a key rib in the bore lets the rod in one way round only.
  - **Details:** `actuator_v6/README.md`, section "Enclosure revision".
- **Arm changes:**
  - `source/build_arm.py`, `load_actuators()`: now includes `06_cable_clamp`, so the clamp plates are in the collision model.
  - `source/build_guide.py`: one sentence in the verification list.
- **Re-run and passing:**
  - `validate_arm.py`: PASS, 134 configurations, 1021 exact-solid checks (the clamp plates add pairs), zero overlap.
  - `check_viewer.cjs`: PASS, 125 cases.
- **Regenerated:**
  - `build_arm.py`: assembly STEP and scene;
  - `build_viewer.py`: the preview. Its actuator internals now come from the V6 scene, whose leadscrew mesh is coarser, hence 16.5 MB instead of 26.4 MB;
  - `build_guide.py`: drawings, comparisons and the guide;
  - `build_readme.py`, then `package_delivery.py`.
- **Unchanged:** the eight structural STEP and STL files, byte for byte. The rebuild changed only their header timestamps, and those were restored from git.
- **Not touched:** the 1:12 R2 arm in `excavator_arm/`.
  - **Delivered files:** its zip and actuator files keep the previous enclosure.
  - **Rebuilding R2:** its scripts import the live V6 code, so a rebuild would adopt the new enclosure. Its `load_actuators()` would then need `06_cable_clamp` added, as here.

## V6 printed-parts view and assembly animation (2026-10-29, V6 session, task `f1790fb0`)

The user asked why the printed parts were not shown one by one in the V6 preview, and whether some screws inside the actuator can be installed at all. No actuator geometry changed.

- **What changed on the actuator:**
  - **Preview views:** `actuator_v6/3D_preview.html` gains a **Printed parts** view and an **Assembly ▶** animation of the build order, with the screwdrivers. `images/assembly_V6-S.mp4` is a recording of it.
  - **Assembly order:** `source/assembly.py` holds the order and the screw list.
  - **Tool access:** `build_v6.py` now checks that each driver reaches its screw without touching a part (`validation.json`, `tool_access`).
  - **Scenes:** `scene_*.json.gz` gain two item kinds, `tool` (the screwdrivers) and `xsection` (a cut body). The wires and the sleeve carry sampled `paths`.
- **Effect on the arm:** none now.
  - **Parts:** the printed parts, their STEP and STL files and V6-U60's dimensions are unchanged.
  - **On a rebuild:** `build_viewer.py` here copies only `hardware`, `board` and `wire` items from the V6 scene, so the new kinds stay out. The wires' extra `paths` would add about 240 kB to the preview.
- **Motor screws on V6-U60:** they need a PH0 with a blade 3 mm thick or less and at least 77 mm long; 90 mm is recommended. A Wera 350 PH 0 × 100 mm fits. V6-L has no suitable catalogue driver yet, but this arm does not use V6-L.
- **Repackaged:** `package_delivery.py` re-run, so the R4 zip carries the new actuator files.


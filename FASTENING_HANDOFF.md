# Actuator fastening revision

The user rejected the first enlarged collar trial as “way too ugly” and said there was no need to enlarge the actuator that much. A substantially smaller revision is complete in `actuator_v6/compact_trial/`. It retains M2 nuts but adds only local screw-corner pads, with no surrounding shell. All 24 CAD/export checks and six browser checks pass. The comparison and exploded renders were visually inspected. Updated downloadable files are available under the new `u60-compact-trial` names.

## User intent and corrections

- The task concerns the printed actuator’s front/rear end-cap fasteners and how to provide usable screw threads.
- The original recommendation to tap the printed holes was withdrawn after checking the very thin walls: approximately 0.60 mm to the exterior after M2 tapping, 0.65 mm to the front PCB slot, and 0.20 mm at the entrance chamfer.
- The user authorized a trial of enlarged mounts with concealed nuts, then rejected the large result. Appearance and minimal enlargement are important constraints.
- Do not revive the bulky full-perimeter collars as the preferred design. The first trial in `actuator_v6/collar_trial/` is retained only as a rejected reference.
- This is a candidate for review and fit prototyping. The released V6 and excavator assemblies have not been regenerated, and the user has not accepted the new appearance yet.
- Latest user feedback is positive interest (“This structure is quite interesting”), followed by questions about the black cover's thickness and whether 3D-printing precision is sufficient. This is a discussion turn; no further CAD change was requested.

## Current compact design

- Folder: `actuator_v6/compact_trial/`. Start with `README.md`; geometry and verification are in `source/build_trial.py`.
- U60 only. The original 16.1 × 14.7 mm central body, 60 mm stroke and 140–200 mm pin spacing remain.
- Maximum local end envelope: **17.4 × 18.1 mm**, versus the rejected collar’s 22.5 × 23.1 mm. This rectangle bounds two small pads; the whole end section is not enlarged to fill it.
- No added material on the motor side. At the PCB-side screw pads, projection is 1.3 mm sideways and 1.7 mm at the upper/lower corners.
- Body pads extend 6 mm axially and blend back over 4.5 mm. Front/rear cap plates retain their original 6/4 mm thicknesses. Two narrow 5 mm-long fingers per cap cover the nut insertion slots; nominal finger fit clearance is 0.15 mm.
- Four M2 hex nuts, 4.0 mm across flats × 1.6 mm thick; pockets 4.2 mm across flats × 1.9 mm deep. The nuts bear axially on 2.4 mm printed shoulders.
- Retains two M2 × 8 front screws and two M2 × 10 rear screws. Their new centres are (7.55, ±6.25) mm.
- Front nuts have 0.25 mm nominal clearance to the PCB edge. A small opening removes an otherwise unprintable 0.05 mm web between each front nut pocket and the PCB groove. The axial shoulder remains intact; real board/nut fit needs careful checking.
- Revised parts: body, front cap, rear cap and cable clamp. The rod-eye cross screw remains the original direct-to-plastic fastening.

## Cover thickness and printing discussion

- The narrow black nut-slot cover is integral with the end cap. Its flat wall is **1.0 mm** thick (`PAD_X[1] - TAB_INNER_X`), with a 5 mm axial projection. Rounded edges taper; across the nut opening the wall is approximately **0.867–1.0 mm**, calculated from the 1.2 mm corner radius. The front/rear cap plates themselves are 6/4 mm thick.
- Current nominal cover/body assembly clearance is 0.15 mm. A calibrated FDM printer can reproduce the feature, but that clearance is tight and does not guarantee an as-printed sliding fit. The thin cover is also vulnerable to bending at its root.
- Proposed practical FDM targets, not implemented: PETG, a 0.4 mm nozzle and 0.16–0.20 mm layers; about 0.25–0.30 mm clearance at the mating faces, tuned with the fit sample. Consider a 1.2 mm cover and a root fillet for handling robustness.
- A thicker cover cannot simply grow inward: the current nut-to-cover gap is only about 0.191 mm. Increasing the cover from 1.0 to 1.2 mm would require approximately 0.2 mm local outward growth or a checked pocket relocation. Preserve the user's minimal-enlargement requirement.
- The cover retains the nut laterally; the 2.4 mm printed shoulder takes the primary axial nut load. Existing CAD checks establish geometric fit, not printed accuracy or strength. Print the short front sample and cap before the full body.

## Files and verification

- `validation.json`: 24 passing checks, including valid single solids, watertight STLs, no new assembly overlaps, side insertion of nuts, cap-finger insertion, rod/nut clearance at seven stroke positions, PCB/nut clearance and preservation of the motor-side outline. No material is added inside the original body envelope.
- `step/compact_housing_assembly.step` contains the housing, nuts and cap screws, not the complete motor/electronics assembly. Individual revised STEP files and printable STLs are included.
- `stl/07_front_band_fit_sample.stl` is a short fit sample for the revised front end; its filename is inherited from the earlier trial.
- `images/comparison.png` compares the original and compact version from the fastener side at identical scale. `trial_motor_side.png` shows the opposite face; `nut_detail.png` shows exploded actual CAD.
- `3D_preview.html` offers original/revised switching, rotation, full stroke and a nut detail. All six browser checks passed in `browser_validation.json`; screenshots are in `images/viewer_desktop.png` and `viewer_mobile.png`.
- Downloads use new names: `output/u60-compact-trial-comparison.png`, `output/u60-compact-trial.html`, `output/u60-compact-trial.zip`. The ZIP includes original V6 dependencies and unchanged rod/eye STEP/STLs for rebuilding.
- Final package integrity passed: 61 entries, 14,007,625 bytes; both passing check reports and final HTML/images are included. ZIP SHA-256: `434795570d91da2d227d6777ded738d79a1ab2e281913754d90b94d41e7dc360`. Delivery metadata and checksums are in `output/u60-compact-trial-delivery.json` and `output/u60-compact-trial.sha256`.
- No physical fit, load, creep or pull-out testing has been performed. Enlarged corners have not been checked against the excavator’s brackets over the full motion range.
- Workspace: `/home/tower/Work/shitian/.worktrees/at/f0b996ed`; baseline HEAD for this revision: `1ab8c8e`. Logs: `/tmp/compact-trial-build.log`, `/tmp/compact-trial-render.log`, `/tmp/compact-trial-browser.log`.

## Next steps

1. Let the user assess the smaller revision; no further CAD changes are pending for this trial.
2. If the user requests further changes, preserve the slim outline and minimize local projection; do not add a surrounding collar shell again.
3. Before adoption, check the full excavator motion for bracket clearance. Print the front fit sample and cap, and test the actual nuts and board fit. The rear cap requires support in its supplied print orientation.
4. Test fastener strength and creep, then integrate accepted geometry into the required production variants and regenerate their assemblies and instructions.

## Rebuild environment

- CAD: `LD_LIBRARY_PATH=/tmp/v6-cad-libs/extracted/usr/lib/x86_64-linux-gnu /tmp/venv/bin/python actuator_v6/compact_trial/source/build_trial.py` (CadQuery 2.8).
- Renders: `LD_LIBRARY_PATH=/tmp/tools/gl:/tmp/tools/sysroot/usr/lib/x86_64-linux-gnu /tmp/tools/blender-4.2.23-linux-x64/blender -b -t 8 -P actuator_v6/compact_trial/source/render_trial.py`.
- Presentation/package: `/tmp/venv/bin/python actuator_v6/compact_trial/source/build_presentation.py`.
- Browser: `NODE_PATH=/tmp/j5-preview-tools/node_modules BROWSER_PATH=/home/tower/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome node actuator_v6/compact_trial/source/check_viewer.cjs`. Repackage afterward to include its report/screenshots.

## Tool constraints

- Shared `get_task_handoff` / `update_task_handoff` tools are unavailable. This file is the local fallback for task `8918e5e2-b064-4f01-8602-ef9769f5d97c`.
- Long-running services must use Agent Tower workspace service tools. Only finite CAD, render and browser commands have been used; no persistent server was started.

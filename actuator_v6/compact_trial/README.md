# U60 compact nut mounts — revised trial

This revision follows the user's rejection of the oversized collar trial. It keeps the original body and cap outline on the motor side and adds material only at the two screw corners on the PCB side. Small integral fingers on each cap cover the nut-entry slots. There is no surrounding cap skirt.

The earlier `collar_trial` is a rejected appearance proposal. This `compact_trial` is the current candidate; it has not been adopted in the released V6 or excavator assemblies.

## Size and fastening

| Feature | Original | Rejected collars | Compact revision |
|---|---:|---:|---:|
| Main body section | 16.1 × 14.7 mm | 16.1 × 14.7 mm | 16.1 × 14.7 mm |
| Maximum local end envelope | 16.1 × 14.7 mm | 22.5 × 23.1 mm | **17.4 × 18.1 mm** |
| Additional material on motor side | — | 3.2 mm | **0 mm** |
| Additional material on PCB side | — | 3.2 mm | **1.3 mm at screw pads** |
| Additional material above/below body | — | 4.2 mm each side | **1.7 mm at screw corners** |

The maximum envelope encloses two local pads; the whole body is not enlarged to that rectangle. Each body pad is 6 mm long, blending back over 4.5 mm. The front and rear cap plate thicknesses remain 6 and 4 mm. Their two narrow cover fingers extend 5 mm along the body, with 0.15 mm nominal assembly clearance.

- Four **M2 × 0.4 hex nuts, 4.0 mm across flats × 1.6 mm thick**.
- Two **M2 × 8** front screws and two **M2 × 10** rear screws, as in the original actuator.
- Screw centres: X = 7.55 mm; Y = ±6.25 mm.
- Nut pockets: 4.2 mm across flats × 1.9 mm deep, entered from the PCB side before installing the caps.
- Nuts bear against 2.4 mm printed shoulders; the plastic no longer supplies the end-cap screw threads.
- Stroke remains 60 mm; pin centres remain 140–200 mm.

The front nuts have **0.25 mm nominal clearance to the original PCB edge**. A narrow local opening connects each nut pocket to the PCB groove, removing an otherwise unprintable 0.05 mm web. The axial bearing shoulder remains intact. This close fit must be checked with real nuts and the actual board. The cover fingers retain the nuts sideways; they are not the primary axial load-bearing feature.

## Review and prototype

`images/comparison.png` shows the original and compact revision from the fastener side at the same scale. `trial_motor_side.png` shows the opposite side; `nut_detail.png` shows the actual front-end CAD exploded. Open `3D_preview.html` for rotation, original/revised switching, a stroke slider and the nut detail.

1. Print `stl/07_front_band_fit_sample.stl` and the revised front cap first, using the original PETG material. Check the purchased M2 nuts, cap fingers and a real PCB or a 0.8 × 8 mm board gauge.
2. Adjust print compensation if necessary. Suggested starting settings: 0.16–0.20 mm layers and at least four perimeters; inspect the nut-seat toolpaths and pocket bridges. Print fit and orientation have not been tested. The rear cap's clevis needs support in the supplied orientation.
3. Print the revised body, front cap, rear cap and cable clamp. Use the unchanged V6-U60 rod and rod eye supplied in the package's `actuator_v6/stl/V6-U60/` folder.
4. Install the motor, PCB and wiring following the original V6 sequence. Slide the four M2 nuts fully into their pockets before fitting the caps. Ensure the nuts clear the PCB and their threads align with the cap holes.
5. Fit the rear cap and cable clamp with two M2 × 10 screws. After fitting the rod, fit the front cap with two M2 × 8 screws, then attach the rod eye. The cap fingers conceal the side-entry openings.
6. Tighten gently by hand and verify free motion. There is no validated torque, working load or nut pull-out rating.

The rod-eye cross screw remains the original direct-to-plastic fastening. This revision concerns the four end-cap attachments.

## Files and verification

- `step/`: four revised part STEP files and `compact_housing_assembly.step` (housing, four nuts and four screws; motor and electronics are not included in that STEP).
- `stl/`: four revised printable parts and a short fit sample.
- `validation.json`: 24 passing checks covering valid solids, watertight exports, new-part intersections, nut insertion, cover-finger assembly, rod/nut clearance at seven stroke positions, PCB/nut clearance and preservation of the motor-side outline.
- `source/build_trial.py`: geometry, checks, STEP/STL and scene generation. It imports the original V6 source from the parent folder.
- `source/render_trial.py`: Blender renders of the exported geometry.
- `source/build_presentation.py`: offline viewer, comparison image and source/CAD ZIP.
- `source/check_viewer.cjs`: six passing browser checks for offline loading, original/revised switching, full stroke, nut detail, mobile layout and JavaScript errors; see `browser_validation.json`.

These are geometry checks. Physical fit, fastening strength, creep and clearance against the excavator brackets through the full motion range remain unverified. This candidate is provided for appearance review and fit prototyping.

## Rebuild

Use Python 3.11 with CadQuery 2.8, NumPy, trimesh and Pillow, plus Blender 4.2:

```sh
python actuator_v6/compact_trial/source/build_trial.py
blender -b -t 8 -P actuator_v6/compact_trial/source/render_trial.py
python actuator_v6/compact_trial/source/build_presentation.py
```

The ZIP includes the original V6 sources/scene, vendor JavaScript, rod/eye STEP/STLs and parameters used by these scripts. For browser verification, install Playwright and run `node actuator_v6/compact_trial/source/check_viewer.cjs`; `BROWSER_PATH` may select an installed Chromium binary. Re-run the presentation script afterward to include the latest report/screenshots in the package. The embedded three.js and OrbitControls license is in `THREE_LICENSE.txt`.

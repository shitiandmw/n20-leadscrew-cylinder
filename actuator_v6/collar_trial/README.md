# U60 collar and captive-nut trial

**Rejected appearance proposal.** The user found these collars too bulky. The current, smaller candidate is in [`../compact_trial/README.md`](../compact_trial/README.md).

This candidate replaces the four end-cap screws' plastic threads with concealed M2 hex nuts. It is a separate CAD and appearance trial of V6-U60. The released actuator and excavator assemblies have not been updated.

The orange body has reinforced bands at its ends and 5 mm tapered transitions back to the original section. Wider black caps overlap each band by 8 mm. The nuts slide into pockets from the PCB side; the cap skirts cover the openings. The nut bears against a 2.4 mm printed shoulder when the screw is tightened.

## Appearance and dimensions

- Original body section: **16.1 × 14.7 mm**.
- Reinforced body bands: **20.1 × 20.7 mm**.
- Maximum black collar section: **22.5 × 23.1 mm**. This is a visible increase of 6.4 mm in width and 8.4 mm in height, concentrated at the ends.
- Skirt wall: 1.0 mm before its edge chamfer; nominal sliding clearance: 0.2 mm per side.
- Stroke: 60 mm; pin spacing: 140–200 mm, as in the original U60.
- Nut pocket: 4.2 mm across flats, 1.9 mm deep, for an M2 nut measuring 4.0 mm across flats and 1.6 mm thick.
- The front pocket retains 1.0 mm to the PCB slot. The primary axial bearing shoulder is 2.4 mm thick. These dimensions do not establish a load rating.

`images/comparison.png` shows both designs with the same camera and scale. `images/nut_detail.png` shows the actual CAD solids exploded for assembly. `3D_preview.html` works offline and lets you rotate the original, trial and nut detail.

## Hardware and assembly

For one actuator, add **four M2 × 0.4 hex nuts, 4 mm across flats × 1.6 mm thick**. Check the purchased nuts against those dimensions. Retain two M2 × 8 front screws and two M2 × 10 rear screws. Their centres move from Y = ±5.75 to ±7.2 mm; X remains 8 mm.

1. Print `stl/07_front_band_fit_sample.stl` and the revised front cap first. Check the nut pocket and skirt fit using the actual printer and hardware.
2. Print the revised body, front cap, rear cap and cable clamp. PETG is the original material. Begin with 0.16–0.20 mm layers and at least four perimeters, inspecting the slicer's paths around the nut seats. The small pocket ceilings require bridging. The revised rear cap has a clevis below its plate in the supplied orientation and needs supports; these print orientations have not been physically tested.
3. Install the stock motor, electronics and wires following the released V6 assembly sequence. Its motor screws thread into the metal gearbox.
4. Slide each M2 nut into its side pocket. Seat it fully and hold it temporarily if necessary; the cap will retain it laterally. The pockets and nut threads must line up with the clearance holes.
5. Slide the rear cap over its band, route the cable and fit the revised cable clamp. Install the two M2 × 10 screws by hand. Screw tips extend about 1.8 mm beyond the nuts into clearance holes.
6. Fit the rod, then slide the front cap along the rod and over its band. Install the two M2 × 8 screws; their tips extend about 0.5 mm beyond the nuts. Fit the rod eye afterward.
7. Tighten gently and check free motion. There is no validated tightening torque or load rating for the printed nut seats.

The rod-eye cross screw remains the original direct-to-plastic M2 fastening. This trial changes the four end-cap attachments only.

## Files and checks

- `step/01_body.step`, `02_front_cap.step`, `03_rear_cap.step`, `06_cable_clamp.step`: the revised parts.
- `step/collar_housing_assembly.step`: those four parts, four nuts and four screws in their assembled positions. It is a housing assembly, not the complete motor/electronics assembly.
- `stl/`: four revised printable meshes and a short front-band fit sample. The unchanged rod and rod eye are included in the package at `actuator_v6/stl/V6-U60/`, with matching STEP files.
- `validation.json`: CAD validity, watertight exports, new-part interference checks, nut insertion and cap sliding checks, plus rod clearance at seven positions from 0 to 60 mm. No material is added inside the original body envelope, so the motor and PCB cavity shapes are preserved.
- `source/build_trial.py`: reproducible geometry and checks; imports the original V6 source in the parent folder.
- `source/render_trial.py`: Blender renders of the exported CAD.
- `source/build_presentation.py`: offline preview, comparison sheet and download package.

The CAD checks do not establish strength, creep resistance, printed fit or nut pull-out strength. The enlarged collars have **not** been checked for clearance against the excavator's brackets through its motion range. Establish those before adopting this candidate in the arm.

All 22 checks in `validation.json` passed. The offline preview also passed six browser checks covering load, design switching, full stroke, nut detail, mobile layout and JavaScript errors; see `browser_validation.json`. The comparison and exploded renders were visually inspected.

## Rebuild

Use the repository's CadQuery 2.8 / Python 3.11 environment, with NumPy, trimesh and Pillow. Run these from the repository or extracted package root:

```sh
python actuator_v6/collar_trial/source/build_trial.py
blender -b -t 8 -P actuator_v6/collar_trial/source/render_trial.py
python actuator_v6/collar_trial/source/build_presentation.py
```

The package includes the original V6 source/scene dependencies used by these scripts. Blender 4.2 supplies the studio environment. The offline viewer embeds the existing MIT-licensed three.js and OrbitControls; its license is included in `THREE_LICENSE.txt`.

For optional browser verification, install Playwright and run `node actuator_v6/collar_trial/source/check_viewer.cjs`; `BROWSER_PATH` can select an existing Chromium binary. Run `build_presentation.py` again after verification to include the latest browser report and screenshots in the ZIP.

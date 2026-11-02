# JGY-370 track module — J8 continuous side frames

J8 follows the user's latest reference photo: a broad continuous side plate with wheel mounting points along its edge. The outer side now uses this full-length frame layout. The inner metal cheek has the same broad web and matching small-wheel axle positions, with the necessary drive clearance on the motor side.

The plates retain J7's double-sided support for all three lower and both upper rollers. Two 4 mm 6061-T6 aluminum plates and three steel cross ties surround the wheels; five 8 mm steel through-axles locate in both sides. The inner faces remain 48 mm apart, with 1 mm beside each small-wheel flange. The outer plate removes as one complete piece after its eight flush screws.

The outer plate includes a 12 mm drive-access opening and a 17.6 mm high, 25.8 mm long idler opening. The idler opening clears the existing collar over axle-centre positions X105.8 to X114.0; it does not fix the moving tensioner in one position. The drive retains its independent bearings and the idler retains its sliding yoke. The frame's current axle holes accommodate the retained 30 mm upper and 36 mm lower rollers. Other diameters require checking hole positions and the track path.

The outer plate is locally relieved by 1 mm behind the drive end to clear the rotating cap screw heads. It remains 3 mm thick there and 4 mm elsewhere. The one-piece motor-to-idler protective housing is retained separately. The reference photo sets the layout style; existing CAD sets all dimensions and mounting datums.

## Preserved package

- Single-unit bounds: min [-154.320508, -73, 0], max [154.120006, 28, 91.141016] mm; approximately 308.44 x 101 x 91.14 mm.
- 54 mm shoes; 220 mm nominal drive/idler centres; 34 links at 20 mm pitch; 12 sprocket teeth.
- Motor axis X=-110 / Z=46.320508 along Y. Gearbox face Y=-46; motor can points +X. Motor face hole pattern 33 x 18 mm.
- Chassis pads X=-60/0/115, Y=-54, Z70 mm. Docking beam and proposed X connector unchanged.
- Three lower rollers: 36 mm running / 40 mm flange diameter. Two upper rollers: 30 / 34 mm at X +/-30, Z65.141016 mm. These moving parts and axes are unchanged from J6.

## Bracket details

| Feature | Nominal geometry |
|---|---|
| Inner cheek J815 | Y=-28 to -24 mm, 4 mm aluminum |
| Outer cheek J816 | Y=24 to 28 mm, 4 mm aluminum |
| Axle seats | 8.05 mm nominal bores; finish matched to actual shafts |
| Straight axle engagement | Inner plate 4 mm; outer plate 2.5 mm before countersink |
| Through-axle J721 | C45 steel, 8 mm journal, integral rear head, M5 front thread |
| Wheel clamp stack | 4 + 7 + 26 + 7 + 4 = 48 mm between cheeks |
| Cross ties J722 | Three steel OD8 x 48 mm, M4 blind threads both ends |
| Outer fasteners | Five M5 x 12 and three M4 x 10 countersunk screws |
| Inner tie fasteners | Three M4 x 25 low-head screws with 1 mm washers |

The axle heads have an upward flat and a rear 4 mm hex counterhold. The flat clears the retained motor and docking beam during inboard axle removal. The frame has matching access pockets. The outer axle ends stop 1.5 mm short of the plate face, allowing the screw heads to seat in the plate countersinks. Thread helices, drill points and commercial fastener details are simplified; select actual screws within the modeled envelopes.

Machine the cheeks as a matched pair. Finish journal/plate/bearing fits and spacer lengths with the selected bearings. The 48 mm tie length and five bearing stacks must agree without bending the cheeks or preloading the bearings. The 2.5 mm outer axle engagement, screw preload, aluminum bearing stress and printed frame creep require physical load validation. Vehicle mass remains unspecified; no payload rating is assigned.

## Folder guide

The current design lives directly in `track_wheel_jgy370/`.

- `source/`: build, checking and media scripts; `source/support/` contains required inherited geometry functions.
- `step/` and `stl/`: current CAD assemblies, individual parts and printable meshes.
- `images/`: diagrams and rendered views.
- `references/`: motor drawings/ratings, frame reference and retained design inputs.
- `simulation/`: saved motion trace and provenance.
- `../output/jgy370_J8/`: downloadable files and complete ZIP.
- `HANDOFF.md`: workspace progress and continuation notes.

## Files

- `images/J8_continuous_frame_review.png`: reference comparison and continuous side-frame illustration; axle section is in the PDF.
- `step/J8_continuous_side_frame_assembly.step`: isolated assembled bracket for direct inspection.
- `step/JGY370_track_J8.step`: complete right track.
- `step/J8_docked_chassis_PROPOSAL.step`: paired reference; actual X-frame and left motor installation remain unverified.
- `step/`: individual machined/printed components. `stl/`: printed parts only; aluminum cheeks and steel axles are not supplied as print parts.
- `3D_preview.html`: offline English viewer, opening on the side-frame assembly; separate inner/outer side, exploded and top views included.
- `J8_design_review.pdf`, `J8_operation.mp4`: illustrated design review and assembly/motion demonstration.
- `ASSEMBLY.md`, `BOM.md`: installation sequence and changed parts.
- Validation JSON files: nominal geometry, sampled removal paths, motion clearances, browser behavior and media decode results.

## Motion and verification scope

J8 reuses the J6 unloaded fixed-frame motion trace because all moving parts and axes are unchanged. `simulation/motion_provenance.json` records source hashes. J8's new stationary bracket is checked against 15 sampled poses. The new video renders J8 geometry; it does not represent a new dynamics calculation.

The trace uses a generic torque servo limited to +/-1.2 Nm, targeting +/-20 rpm. Nominal chain speed at 20 rpm is 80 mm/s. Both upper rollers turn through contact; the unloaded middle lower roller can remain stationary. This is not physical footage, a motor electrical model or a vehicle load/traction test. Passive roller support changes do not increase speed.

## Rebuild

J8 is the only retained JGY release. Its inherited geometry and checking functions are in `source/support/`; the J1-J7 release folders are no longer needed. The support filenames retain their part lineage. Motor drawings, ratings, retained dimensions and external design references are in `references/`.

Keep the included sibling dependency folders (`track_wheel/`, `excavator_60mm/`, `excavator_arm_60mm/` and `actuator_v6/`) in place. Python needs CadQuery, NumPy, Shapely, trimesh, matplotlib, Pillow, PyMuPDF and imageio-ffmpeg. Node needs Playwright and Chromium. No persistent server is needed.

`reuse_motion.py` verifies the saved playback and its input hashes; it no longer copies files from an earlier release. The optional original motion generator is documented in `source/support/README.md`. It is not part of the normal media rebuild.

```sh
python3 track_wheel_jgy370/source/export_plate_layout.py
python3 track_wheel_jgy370/source/build_j8.py
python3 track_wheel_jgy370/source/reuse_motion.py
python3 track_wheel_jgy370/source/check_motion_geometry.py
python3 track_wheel_jgy370/source/build_viewer.py
node track_wheel_jgy370/source/check_viewer.cjs
node track_wheel_jgy370/source/export_video.cjs --preview
node track_wheel_jgy370/source/export_video.cjs
python3 track_wheel_jgy370/source/draw_review.py
python3 track_wheel_jgy370/source/verify_media.py
python3 track_wheel_jgy370/source/package_j8.py
```

Workspace CAD interpreter: `/tmp/venv/bin/python`, with `LD_LIBRARY_PATH=/tmp/v6-cad-libs/extracted/usr/lib/x86_64-linux-gnu`. Node: `NODE_PATH=/tmp/j5-preview-tools/node_modules`.

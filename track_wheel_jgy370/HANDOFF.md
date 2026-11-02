# Current status

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

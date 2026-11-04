# R12 excavator arm: CAD and motion simulation

R12 is built on **real excavator geometry**: Cat 325 pin positions from a Caterpillar patent and Cat 320 outlines traced from the manufacturer's render, both scaled to a Cat 320 at 1:15. All four drives are the same model, **V6-U60** (60 mm stroke, stock M3 × 0.5 screw 75 mm long, 140–200 mm between pins).

**Status:** the approved drawing set is now modelled in 3D (CAD in CadQuery) and simulated (MuJoCo), at drawing revision **D4**. D4 replaces the bucket with a 1:15 copy of a real Caterpillar bucket (see *The bucket, Rev. D4*).
- The exact 3D clash check found one real interference that the drawing-stage check could not see. It is fixed; see *What the 3D model changed*.
- Nothing has been printed yet.

## Open these first

- **`3D_preview.html`**: an offline 3D viewer. Open it in any browser; it needs no network.
  - It shows the CAD of every part.
  - It replays the dig cycle from the MuJoCo trace, with or without 150 g of payload, with live drive forces, a force chart and phase selection.
  - Manual mode has three stroke sliders.
  - There are views, an X-ray toggle and pin labels.
- **`images/motion_simulation_r12.mp4`**: a 32 s video of the 150 g dig cycle (643 s simulated, shown at 20×, 1280 × 720, with one chapter per phase).
- **`images/dig_cycle_r12.png`**: strokes and drive forces over the cycle.
- **`ASSEMBLY.md`**: print settings, pins, pin stacks, fits, drive orientation and assembly order.

## Files

- `step/`: one STEP file per printed part, in its body frame, and `r12_arm_assembly.step` (93 solids at the reference pose)
- `stl/`: the printed parts in print orientation
- `R12_design_drawings.pdf` (Rev. D4): six A3 sheets, also exported as `images/sheet_1.png` … `sheet_6.png`. They are updated to the CAD: stepped bosses, one-piece prints, hardware counts, checks and the Caterpillar bucket (sheet 5).
- `references/`: the Caterpillar sources, now including `US8201350_fig1.png`, the bucket patent figure D4 is copied from
- `images/bucket_rev_d4_before_after.png`: D3 and D4 in the 3D viewer at the same poses, and the D4 outline on the patent figure
- `cad/`
  - `scene.json.gz`: meshes per body
  - `cad_report.json`: validity, watertightness and STEP round trip per part
  - `clash_check.json`: the exact 3D interference check
- `motion.json`: the dig-cycle waypoints and the 10 Hz stroke reference
- `simulation/`
  - `arm_r12.xml`: the MuJoCo model
  - `mass_properties.json`: from the CAD
  - `*_report.json` and `*_trace.json.gz`: the results
- `validation_summary.json`: every check in one place. It is written by `source/summarize_r12.py`, along with `browser_validation.json` and `video_validation.json`.
- `design_check.json`: the drawing-stage 2.5D check, rerun with the final geometry
- `source/`: see *Rebuild*

## The model

| Body | Mass (CAD, incl. pins/collars on it) | Printed part |
|---|---|---|
| Boom-foot bracket | 117 g | B01, 93.5 g |
| Boom | 312 g | B02, 283.8 g, + 2 × B08 pad, 2.4 g |
| Stick | 191 g | B03, 161.2 g |
| Bucket | 85 g | B06, 74.9 g, + 5 × B07 tooth, 1.2 g |
| Side links / H-links | 10 g / 7.5 g | B04, B05 |
| Each V6-U60 | 51 g barrel + 7.6 g rod | (V6 parts from `actuator_v6`) |

- **Printed parts:** PETG, 6 perimeters (2.5 mm) + 10 % gyroid. Masses count exactly that: the solid envelope minus 90 % of its core. The 15 printed parts weigh about 637 g in total.
- **Validity:** every part is a valid, watertight single solid and survives a STEP export/import round trip.
- **The drives** are the real V6 solids from `actuator_v6/source/design_v6.py` (U60 layout), with the 9.75 mm board side oriented as on the drawings.

## Checks

| Check | Result |
|---|---|
| 3D clash, FCL mesh–mesh | **PASS** over 447 poses: the 5×5×5 stroke grid plus the dig cycle every 2 s. 93 parts and 3771 moving pairs give 0 penetrations. No overlaps between parts fixed to the same body. |
| Closest side-view gaps | Stick-drive rod eye to stick head bridge: **1.10 mm** at full crowd. Boom drive body to foot bracket: 1.32 mm. Bucket-drive rod eye to stick: 2.11 mm. Side faces run past each other at 0.5 mm by design. Running fits at the pins are 0.05–0.1 mm. |
| 2.5D drawing check, rerun | PASS, 1075 poses, ≥ 1.0 mm. Its closest pair (1.1 mm) is the same one the 3D check found. |
| Viewer kinematics vs Python | 125 poses, ≤ 0.0003 mm |
| Viewer replay vs MuJoCo trace | Body poses identical, to 0 error, at the sampled frames |

## Dig cycle and dynamics

Each segment of the cycle is a minimum-jerk move. Its duration is set so the fastest drive peaks at 0.8 mm/s, below the 1.25 mm/s no-load speed. Each waypoint has a 3 s dwell.

| # | Phase | Boom / stick / bucket stroke, mm |
|---|---|---|
| 0 | Carry | 45 / 38 / 50 |
| 1 | Reach out, bucket open | 32 / 6 / 8 |
| 2 | Penetrate | 10 / 12 / 18 |
| 3 | Crowd the stick | 8 / 42 / 30 |
| 4 | Curl the bucket | 12 / 46 / 58 |
| 5 | Raise | 52 / 40 / 60 |
| 6 | Dump | 55 / 22 / 4 |
| 7 | Carry | 45 / 38 / 50 |

The whole cycle takes **643 s**. The tooth reaches 279 mm below the ground (the X1 crawler stands on Z −155) and 654 mm ahead of the slew axis.

### The MuJoCo model

- **Bodies and loops:** rigid bodies with the CAD mass and inertia. The two closed loops (boom pair, bucket four-bar) are pin-to-pin equality constraints.
- **Drives:** each drive is a slide with a DC-motor force law: 201 N stall, 1.25 mm/s no load, linear in between.
- **Reflected rotor inertia:** 3216 kg equivalent, from an assumed 20 ms mechanical time constant.
- **Force clamp:** 51 N, the continuous rating, used as a fuse.
- **Control:** PI position control on each stroke.
- **Solver:** 1 ms step, implicitfast. The payload is 150 g in the bucket.

| Scenario | Peak boom (each) | Peak stick | Peak bucket | Tracking | Pin closure | At clamp |
|---|---|---|---|---|---|---|
| 150 g payload | **38.3 N** | 16.9 N | 14.0 N | ≤ 0.063 mm | ≤ 0.019 mm | 0 s |
| Empty | 27.5 N | 9.1 N | 4.7 N | ≤ 0.049 mm | ≤ 0.014 mm | 0 s |

Cross-checks:
- **Static holds** at the three worst poses agree with the virtual-work statics within 0.02 N:
  - boom 39.5 N each at 60 / 15 / 35
  - stick 27.6 N at 0 / 60 / 45
  - bucket 16.6 N at 40 / 55 / 60
- **Halving the time step** changes no peak force (0.00 N over the first 160 s).

## What the 3D model changed

1. **The rod-eye socket.**
   - The V6 rod eye has an Ø11 socket around the rod, starting 4 mm behind the eye centre, as well as the 6 mm lug. The 2.5D model only carried the Ø8 rod.
   - At B the boss pads, and at R the Ø10 H-link tubes, ran into that socket.
   - Both now step down to an **Ø7.2 boss** next to the eye. The redundant B spacer is gone, because the boss now bears on the eye.
   - The socket is now in the 2.5D model too.
2. **Teeth.** The tooth socket is cut from the actual floor plate with 0.1 mm clearance. In D3 a straight socket had cut 0.17 mm into the curved plate.
3. **Shim washers.** 0.4 mm steel shims sit at O, E and H, between members that run face to face.
4. **One-piece prints.** The boom, stick and bucket print in one piece with 6 perimeters + 10 % gyroid, instead of channel + cover. The drawings were updated to match.
5. **Q spacer tube (D4).** It is gone: the bucket's torque tube now spans the ears and carries the Q pin.

## The bucket, Rev. D4: a copy of a real Caterpillar bucket

You asked for the shape of an actual bucket. D4 replaces the bucket with the one in **Caterpillar patent US 8,201,350 B2, "Machine bucket"** (Example 1 and FIG. 1).
- That bucket has a tip radius of 1,570 mm, which is exactly R12's tip radius at 1:15.
- So it is copied at 1:15 with nothing stretched: its upper pin is our H and its tooth tip is our T.
- Sources:
  - https://patentimages.storage.googleapis.com/20/c1/2f/6b72806a7cb504/US8201350.pdf
  - `references/US8201350_fig1.png`
  - `source/bucket_ref.py`

**What is copied:**
- **Wrapper.** One plate runs from the cutting edge along the floor and round the heel: R 985 mm over 30°, then R 370 mm over 130°.
- **Support plate.** It runs back at 20° to the floor, to its front end beside H.
- **Placement.** The patent's heel radius (1246 mm at 10.34°) and its support plate place all of this relative to the pin.
- **Patent check.** Measured on our model, the throat dimensions are D 941 / D′ 928 mm. The patent gives 940 / 920.
- **Mouth.** It is fully open, from the cutting edge to the support-plate front end. It lies just behind the hinge–tooth line, the line you drew in red.
  - The D1–D3 buckets had a lip bar and a closed top plate that stuck out on the other side of that line.
  - D3 made the back shallower but kept them, which is why it still did not look like a bucket.
  - `images/bucket_rev_d4_before_after.png` shows D3 and D4 side by side, and the D4 outline on the patent figure.
- **Side plates.** Straight front edge from the support plate down to the cutting edge, as on the real bucket.
- **Hinge.**
  - H and Q sit on two 4 mm hinge plates (the ears).
  - Between the ears, a torque tube stiffens the support plate and carries the Q pin, so the separate Q spacer tube is gone.
  - Our Q is 8.4 mm (full size 126 mm) closer to the tip than the patent's link pin, because R12 keeps the Cat 325 linkage. That is the only adaptation.
- **Teeth.** Five tip-and-adapter teeth in the FIG. 1 shape. They reach 20.6 mm ahead of the cutting edge to T, and their straps clamp the floor plate.

**Unchanged:** the tip radius, H, Q, T and the whole linkage. Joint ranges, digging depth, reach and dump height are therefore the same.

**What it costs:**
- **Size.** The back reaches 74 mm from the hinge–tooth line, as a real bucket of this tip radius does. D3's back stopped at 30 mm, with its lip bar 17 mm out on the other side.
  - Struck capacity is **247 cm³** (0.83 m³ at full size, a normal Cat 320 bucket). That holds about 395 g of dry sand, so the rated 150 g fills it to about 38 %.
- **Mass.** B06 is 74.9 g (D3: 65.1 g) and each tooth 1.2 g, so the drive forces rise slightly (tables above).
- **A full struck load of sand** would take each boom drive to about 56 N held (2.5D estimate), above the 51 N rating. Plan on 150 g, or a half-full bucket of sand.

## Findings that need a decision

1. **Boom-pair synchronisation is required.**
   - At the worst hold pose a 0.5 mm offset between the two boom position sensors loads the drives to 51 N (clamped) and 28 N instead of 39.5 N each.
   - Control both boom drives from one shared target, with closed-loop correction on each drive (`ASSEMBLY.md`).
2. **Margin.**
   - The boom pair is the limit: the cycle peak is 38.3 N and the worst static hold is 39.5 N, about 23 % below the 51 N rating.
   - The stick and bucket drives have large margins.
   - Soil forces are not modelled. At 51 N the tooth force is 3.6–15.3 N from the bucket drive and 7.3–14.6 N from the stick drive, so digging firm soil is not realistic; loose sand is.
3. **Speed.** One cycle takes almost 11 minutes. The N20 screw drives are slow (1.25 mm/s with no load), and the cycle peaks at 0.8 mm/s to keep a speed margin under load. A cycle at full speed would take about 7 minutes.
4. **Printer bed.** The boom is 408 mm long. Below a 410 mm bed, split it at S (sheet 3).
5. **Still open from the drawings:**
   - the X1 track limit: keep the boom above 4 mm of stroke when slewed over a track
   - cable routing
   - testing pin and collar fits on the actual printer

## Rebuild

The steps need Python 3.11 with numpy, scipy, shapely, matplotlib, pillow, contourpy, cadquery, trimesh, python-fcl, mujoco and imageio-ffmpeg. The browser steps need Node with Playwright and its headless Chromium.

On this machine:
- The venv is `~/.cache/arm-design-tools/venv`.
- CadQuery and Chromium need user-space libraries: `LD_LIBRARY_PATH=~/.cache/arm-design-tools/syslibs/extracted/usr/lib/x86_64-linux-gnu`.
- Chromium needs a font config: `FONTCONFIG_FILE=~/.cache/arm-design-tools/fonts.conf`.

From `source/`, in order:

```
python check_design.py         # 2.5D sweep -> design_check.json          (~2 min, 8 cores)
python draw_sheets.py          # drawings                                  (~1 min)
python cad_r12.py              # STEP / STL / scene / mass properties      (~1 min)
python check_cad.py            # exact 3D clash -> cad/clash_check.json    (~1 min)
python motion_r12.py           # dig cycle -> motion.json
python physics_r12.py all      # MuJoCo scenarios -> simulation/           (~10 min)
python plot_cycle_r12.py       # images/dig_cycle_r12.png
python build_viewer_r12.py     # 3D_preview.html
node render_r12.cjs review     # browser check -> browser_validation.json
node render_r12.cjs frames /tmp/r12-frames 0 771   # video frames (split into chunks to run in parallel)
python encode_r12.py           # images/motion_simulation_r12.mp4 -> video_validation.json
python summarize_r12.py        # validation_summary.json
```

`r12_design.py` is still the single source of truth. It takes the bucket geometry from `bucket_ref.py` (the patent numbers and FIG. 1 points). `poses_r12.py` turns strokes into body frames for the CAD, the physics, the viewer and the checks.

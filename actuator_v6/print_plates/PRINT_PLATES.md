# Print plates: four V6-U60

The printed parts of four V6-U60 drives, laid out on four plates for a 180 × 180 mm bed (Prusa MINI, Bambu Lab A1 mini, or anything larger). The files are in `V6-U60_x4/`, and `../parts_showcase.html` shows each plate and part in 3D.

Print plate 1 first and check its fits (`ASSEMBLY.md` step 1) before printing the rest. PETG, 1.75 mm; no supports on any plate.

| Plate | What | Pieces | Height | PETG | Time |
|---|---|---:|---:|---:|---:|
| 1 | Fit test (print this first) | 5 | 18 mm | 7.0 g | 1 h 19 min |
| 2 | Bodies, 4 off | 4 | 108.1 mm | 61.2 g | 10 h 59 min |
| 3 | Rods, rod eyes and cable clamps, 4 each | 12 | 92 mm | 24.0 g | 5 h 49 min |
| 4 | Front and rear caps, 4 each | 8 | 14.5 mm | 12.6 g | 2 h 10 min |
| | All plates | 29 | | 105 g | 20 h 16 min |

Filament and times are the estimates of PrusaSlicer 2.9.2 (`V6-U60_x4/slicer_estimate.json`, written by `source/slice_plates.py`), skirt and brims included, with a generic 0.4 mm nozzle at its default speeds: your printer's profile gives its own times.

## The files

- `plate<N>_<name>.3mf`, for PrusaSlicer: every part is an object with its own settings (layer height, walls, infill, brim, and the body's 0.12 mm layers for its last 2 mm as a height range); copies are instances of it. Open it, pick your printer and filament, and slice.
- Bambu Studio, OrcaSlicer and Cura load the same 3MF with every part in place, but not the settings: set the settings of each part by hand, as listed below.
- `plate<N>_<name>.stl`: the whole plate as one mesh, with one setting for everything on it. Enough for plate 2; on the other plates the parts differ, so prefer the 3MF.
- `plates.json`: what is on each plate, where and with which settings, and the checks that were run.

## Plate 1: Fit test (print this first)

`plate1_fit_test.3mf` (and `.stl`): 5 pieces, 71.9 × 39.4 mm on the bed, brims included; 18 mm tall.

The four fit samples and one rear cap: check the motor bay, the carrier in the bore, the nut and magnet seats, the board slot, the M1 insert holes and the rear-cap hook before printing the real parts (ASSEMBLY.md step 1).

| Part | Copies | Settings |
|---|---:|---|
| Fit sample 08: motor bay and bore (`08_fit_body_wall`) | 1 | 0.2 mm layers, 3 walls, 25 % gyroid, no brim; the last 2 mm at 0.12 mm layers, no supports |
| Fit sample 10: rear end (`10_fit_insert_rear`) | 1 | 0.2 mm layers, 3 walls, 25 % gyroid, no brim; the last 2 mm at 0.12 mm layers, no supports |
| Fit sample 11: front end (`11_fit_insert_front`) | 1 | 0.2 mm layers, 3 walls, 25 % gyroid, no brim; the last 2 mm at 0.12 mm layers, no supports |
| Fit sample 09: carrier (`09_fit_carrier`) | 1 | 0.16 mm layers, 100 % infill, no brim, no supports |
| Rear cap (`03_rear_cap`) | 1 | 0.16 mm layers, 4 walls, 60 % gyroid, no brim, no supports |

The rear cap is for the hook test on sample 10; afterwards it is a spare.

PrusaSlicer 2.9.2: 7.0 g, about 1 h 19 min. Its support alert names fit sample 08 (floating bridge anchors, loose extrusions): the same bridge as in the body, the motor wall over the bore, here 6 mm up. Checking it is what the sample is for: the M1.6 screws must sit flush with the wall (ASSEMBLY.md step 1). No supports.

## Plate 2: Bodies, 4 off

`plate2_bodies_x4.3mf` (and `.stl`): 4 pieces, 64.6 × 59.4 mm on the bed, brims included; 108.1 mm tall.

The barrels: tall parts with the 1 mm partition, printed front end down.

| Part | Copies | Settings |
|---|---:|---|
| Body (`01_body`) | 4 | 0.2 mm layers, 3 walls, 25 % gyroid, 5 mm brim; the last 2 mm at 0.12 mm layers, no supports |

PrusaSlicer 2.9.2: 61.2 g, about 10 h 59 min. Its support alert names the body (floating bridge anchors): the motor wall bridges the carrier bore 77 mm up, and the two motor-screw countersinks open into its underside, so some bridge lines end in mid-air. Print without supports all the same: they would be trapped in the bore. Fit sample 08 shows how this bridge prints.

## Plate 3: Rods, rod eyes and cable clamps, 4 each

`plate3_rods_eyes_clamps_x4.3mf` (and `.stl`): 12 pieces, 94 × 63.7 mm on the bed, brims included; 92 mm tall.

The solid (100 % infill) parts at 0.16 mm.

| Part | Copies | Settings |
|---|---:|---|
| Rod and nut carrier (`04_rod`) | 4 | 0.16 mm layers, 100 % infill, 3 mm brim, no supports |
| Rod eye (`05_rod_eye`) | 4 | 0.16 mm layers, 100 % infill, no brim, no supports |
| Cable clamp (`06_cable_clamp`) | 4 | 0.16 mm layers, 100 % infill, no brim, no supports |

`BOM.md` asks to slow the last 20 mm of the U60 rods, so that their thin tops can cool. With four rods on the plate each of those layers already takes about four times as long; slow down if you print a rod on its own.

PrusaSlicer 2.9.2: 24.0 g, about 5 h 49 min. Its support alert names the cable clamp (loose extrusions): its two screw-head counterbores face the bed, so the ring around each screw hole is printed over the counterbore. A little sag there does no harm: the screw head presses it flat. No supports.

## Plate 4: Front and rear caps, 4 each

`plate4_caps_x4.3mf` (and `.stl`): 8 pieces, 99.2 × 39.4 mm on the bed, brims included; 14.5 mm tall.

The end caps at 0.16 mm and 4 walls.

| Part | Copies | Settings |
|---|---:|---|
| Front cap (`02_front_cap`) | 4 | 0.16 mm layers, 4 walls, 40 % gyroid, no brim, no supports |
| Rear cap (`03_rear_cap`) | 4 | 0.16 mm layers, 4 walls, 60 % gyroid, no brim, no supports |

PrusaSlicer 2.9.2: 12.6 g, about 2 h 10 min.

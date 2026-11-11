# R12 assembly and printing notes

These notes go with the CAD in `step/` and `stl/`. All sizes are in mm. Y is across the arm, and + is the left side when you look forward along the arm.

## Printed parts (PETG)

All printed parts use 6 perimeters (2.5 mm), 10 % gyroid infill and 0.2 mm layers. The STL files are already in print orientation.

| Part | Qty | Mass g | Print size | Orientation, notes |
|---|---|---|---|---|
| B01 boom-foot bracket | 1 | 93.5 | 76 × 100 × 68 | flange down. Pins A press into it (below). |
| B02 boom | 1 | 283.8 | 408 × 108 × 40 | on its side. **Needs a bed of at least 410 mm.** On a smaller bed, split it at S (x 205) with a spigot and 4 × M3 (drawing sheet 3). |
| B03 stick | 1 | 161.2 | 245 × 69 × 32 | on its side |
| B04 side link | 2 (L, R) | 2.4 | 51 × 10 × 4 | flat |
| B05 H-link | 2 (L, R) | 3.8 | 49 × 10 × 22 | plate down, R tube up |
| B06 bucket | 1 | 74.9 | 100 × 84 × 80 | on one side plate. Rev. D4: the Caterpillar bucket of US 8,201,350 at 1:15, with an open mouth. The upper side plate spans the cavity, so put supports inside; they come out through the mouth. The torque tube between the ears prints with it. |
| B07 tooth | 5 | 1.2 | 23 × 25 × 7 | on its side. Tip and adapter in one piece (patent FIG. 1 shape). The socket slides over the floor-plate edge; glue it with CA. |
| B08 B pad | 2 (L, R) | 2.4 | Ø17 × 10.9 | big face down. Bond it to the boom side wall, centred on pin B. |

Total printed: about 637 g.

## Pins and hardware

| Pin | Pin size | Retention | Stack across Y, outward from Y 0 |
|---|---|---|---|
| O boom foot | Ø6 × 60 | 2 × collar Ø11 × 4 | boom root ±20 · 0.4 shim washer Ø6/11 · foot plate 20.5–25.5 · collar 25.8–29.8 |
| A boom-drive base | 2 × Ø3 × 30 | collar Ø7 × 3 outboard | foot plate 20.5–25.5 · spacer 25.6–30.9 · **drive eye 31–37** · spacer 37.1–42.4 · outer cheek 42.5–47.5 · collar 47.8–50.8 |
| B boom-drive rod | Ø3 × 82 (one through-pin) | 2 × collar Ø7 × 3 | cross tube ±20 · B08 pad 20–28.3 · B08 boss Ø7.2 28.3–30.9 · **drive eye 31–37** · collar 37.3–40.3 |
| C stick-drive base | Ø3 × 34 | 2 × collar | **drive eye ±3** · spacer 3.1–7.9 · C cheek 8–13 · collar 13.3–16.3 |
| E boom–stick | Ø6 × 42 | 2 × collar Ø11 × 4 | boom nose ±10.5 · 0.4 shim washer · stick head plate 11–16 · collar 16.3–20.3 |
| D stick-drive rod | Ø3 × 40 | 2 × collar | **drive eye ±3** · spacer 3.1–10.9 · head plate 11–16 · collar 16.3–19.3 |
| F bucket-drive base | Ø3 × 34 | 2 × collar | **drive eye ±3** · spacer 3.1–7.9 · F cheek 8–13 · collar 13.3–16.3 |
| J side-link pivot | Ø3 × 68 | 2 × collar | stick boss ±16 · spacer 16.1–25.9 · side link 26–30 · collar 30.3–33.3 |
| R linkage / bucket-drive rod | Ø3 × 68 | 2 × collar | **drive eye ±3** · H-link boss Ø7.2 3.1–5.8 · H-link tube Ø10 5.8–21 · H-link plate 21–25 · spacer 25.1–25.9 · side link 26–30 · collar 30.3–33.3 |
| Q H-link / bucket | Ø3 × 58 | 2 × collar | B06 torque tube ±16.5 (printed with the bucket) · bucket ear 16.5–20.5 · H-link plate 21–25 · collar 25.3–28.3 |
| H stick / bucket | Ø6 × 50 | 2 × collar Ø11 × 4 | stick nose ±16 · 0.4 shim washer · bucket ear 16.5–20.5 · collar 20.8–24.8 |

- **Pins:** hardened dowels or ground silver steel.
- **Collars:** shaft collars with a set screw, Ø7 × 3 for the Ø3 pins and Ø11 × 4 for the Ø6 pins. An e-clip in a turned groove also works if it stays inside the same envelope.
- **Spacers:** printed PETG tubes, Ø7 on Ø3 pins.
- **Shim washers:** steel, 0.4 mm thick, 6 × 11.

### Fits

- **Printed bores** are modelled at pin + 0.1 mm, which is a running fit. Print them at that size, then ream with the pin's drill size (3.0 / 6.0) until the pin turns freely without play.
- **Pins A** must not rotate in the bracket. Drill those two bores 2.9 mm and press the pins in from outside.
- **The B08 pads** are glued to the boom with the B pin in place, so they line up with the bore.
- **The V6 eye lugs** are 6 mm wide. Every joint leaves 0.1 to 0.3 mm of side play.

### Why the B pad and the R tube are stepped

The V6-U60 rod eye is more than a 6 mm lug. Behind the lug there is an Ø11 socket around the rod, starting 4.0 mm behind the eye centre.

At B, a full-diameter pad would run into that socket, and so would a full Ø10 H-link tube at R. Both therefore step down to an Ø7.2 boss where they face the eye. The boss clears the socket by 0.4 mm at every angle.

The exact 3D check (`cad/clash_check.json`) found this. The side-view drawing check could not see it.

## Drives

There are four identical V6-U60 drives: 60 mm stroke, 140 to 200 mm between pins, stock M3 × 0.5 screw 75 mm long.

| Drive | Rear pin → rod pin | Y centre | Board housing, side view |
|---|---|---|---|
| Boom L | A → B | +34 | right of the line A→B |
| Boom R | A → B | −34 | right of the line A→B |
| Stick | C → D | 0 | left of the line C→D |
| Bucket | F → R | 0 | left of the line F→R |

The board housing is the 9.75 mm side of the 16.1 mm deep body (6.35 mm on the other side). These board sides are the ones checked for clearance. If a housing is flipped, run `check_cad.py` again.

**The boom pair must be synchronised in closed loop.** Both boom drives push on one rigid boom. A 0.5 mm difference between their position sensors at the worst holding pose loads one drive to 51 N and the other to 28 N, where they should share about 39.5 N each (`simulation/sync_bias_report.json`). Use one shared position target and correct each drive's error separately, or average their sensors and add a cross-coupling term. Do not drive the two boom drives open-loop from one PWM signal.

## Assembly order

1. Dry-fit pins A in B01 (B01X on the X1 machine, `excavator_complete/`): they go in last, in step 3, because once a pin is through the outer cheek and the foot plate the drive eye between them can no longer be threaded on.
2. Bond the B08 pads to B02, using the B pin as a jig. Let the glue cure.
3. Fit the boom to the bracket on pin O, with the shim washers. Then each boom drive: hold its rear eye, with a spacer on each side, between the foot plate and the outer cheek, and press pin A in from outside through the cheek, the outer spacer, the eye, the inner spacer and the foot plate; then the collar. Rod eyes on the B pin.
4. Fit the stick drive to the boom at C. Join the stick to the boom at E, with shims, and the stick-drive rod to the stick at D.
5. Fit the bucket drive at F. Assemble the linkage at J and R: side links, H-links, the R spacers, and the bucket-drive rod eye between the H-link bosses. Then fit Q through the bucket ears and the torque tube, and H.
6. Glue the five teeth.
7. Before switching on: move each joint through its range by hand, with the drive rods disconnected at their rod pins. Watch the stick-drive rod near the stick head bridge at full crowd: 1.1 mm is the smallest side-view gap.

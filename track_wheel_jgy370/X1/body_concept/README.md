# X1 body, concept B1 (sketch, not CAD)

The upper body is traced from the real Caterpillar 320, fitted to X1. The battery, electronics and ballast are packed inside it.

**Now modelled (rev B):** the three prints agreed on sheet 5 are in CAD, with their checks, plus four small prints added after the user's review of rev A: the cab interior, the operator, the battery hatch and the left handrail with its mirror. The battery has moved from the right bay to a hatch on the hood centreline. See [../BODY.md](../BODY.md), which also lists what changed from this sketch. This sketch stays as issue 2; it is not redrawn.

`X1_body_concept_B1.pdf` (issue 2) has 5 sheets. Each sheet is also a PNG, and the computed numbers are in `X1_body_concept_B1_checks.json`.

1. **The real machine, traced.** Sources:
   - Cat 320 spec sheet, page 4: the dimension drawing, which is orthographic, at 19.1 mm/px.
   - Caterpillar's right-side render, which is in perspective.

   The trace is checked against Caterpillar's own numbers: cab top, counterweight clearance, track length, tail swing, upperframe width and handrail. All agree within 1.8 %.
2. **The X1 shell** in four views over the existing machine, compared with the Cat at 1:15.
3. **Inside the shell:** the battery, the controller board, the switch gear, the ballast, the cable routes and service access.
4. **Parts and checks:** the issue-1 print split, masses and balance, wiring diagram, 21 checks (all pass) and the decisions.
5. **Fewer parts:** what a 256 printer allows. Three prints is the minimum, against the issue-1 nine prints and one print on a larger printer, with pros and cons.

## Decided (issue 2)

| Decision | Choice |
|---|---|
| D1 battery | 3 × 18650 Li-ion in series (3S1P) with a 3S BMS, straight onto the 12 V motors (12.6 V full, 9.0 V empty). |
| D2 control | ESP32 with a Bluetooth gamepad. |
| D3 ballast | Loose shot poured into the counterweight and sealed with epoxy. The user wrote "bulk copper". This is read as the loose-shot option; copper shot would also fit. |
| D4 tail | The Cat outline widened (corners R 225). |
| D5 skirt | 31 mm over the T101 sides. |
| D6 detail | As drawn. |

## Decided: the print split (3 prints, now modelled)

The user would have liked the body in one piece. On a 256 × 256 × 256 printer that is impossible: the body is 308 × 281 × 147, and a print spanning the full 308 width must be under 54 deep even laid diagonally. Only the counterweight is.

The proposal is 3 prints (sheet 5):
- **B101 counterweight** (436 g), printed upright and turned 45°.
- **B102 left half** (391 g): cab, left hood half and the louvred side, printed on its outer side face.
- **B103 right half** (308 g): right hood half, tank, steps, toolbox and exhaust, printed on its outer side face.

How the 3 prints fit together:
- **Fixings:** each half has 2 × M3 screwed down sleeves in its hood top into new inserts in the T101 rib tops, plus a front hook under the T101 base-plate edge.
- **Controls:** the switch and charge jack sit on the toolbox's outside.
- **ESP32:** its USB is reached through a louvre slot.
- **Seam:** on the hood centreline, as a lap joint.

One print would need a bed of about 285 × 312.

## How the Cat becomes X1

- **Lengths:** at 1:15, as traced. X1's tracks and the ARM60 are already 1:15 in length.
- **Heights above the deck:** at 1:15, measured from the T101 rib tops (Z 136).
  - Hood: Z 219. Cab roof: Z 252.
  - The Cat's 11.5 mm frame band is stretched to 31 mm. It covers the T101 sides down to Z 105.
- **Width:** 185.3 becomes 308.
  - The ARM60 base is 164 wide, so 61.3 is inserted on each side of the centreline.
  - Every Cat part keeps its own width: the cab, tank, toolbox and the counterweight's rounded ends.

## Layout

| Where | What |
|---|---|
| Left bay (the Cat's louvred cooling side) | Controller board: ESP32, 3 × DRV8871, 2 × DRV8833, 6 V and 5 V bucks. |
| Right bay, low at the rear | 3S1P 18650 pack with a 3S BMS. |
| Toolbox | Main switch, 5 A fuse, charge jack. |
| Counterweight | About 0.85 kg of bought steel shot (189 cm³, sealed with epoxy) and a lead channel from the T101 Ø20 window. |
| Tank block and cab | Empty. |

- The T101 service area (slide clamps, push screws, drag-pad set screws) stays clear.
- The hood lids come off by hand: 4 magnets each (issue 1; the 3-print split has no lids).

## Estimated balance

| Quantity | Value |
|---|---|
| Upper mass | 5.13 kg |
| Upper CG with the arm stretched | on the swing axis (the ballast is sized for this) |
| Upper CG with the arm tucked (bound) | X −42.5 |
| Inertia about the swing axis | 0.156 kg·m² |

The R3 swing simulation used 0.152 kg·m². Counting the motor's reflected 0.32 kg·m², the inertia the stops act against is 1.0 % higher than simulated.

## Rebuild

From `body_concept/source/`:

```
LD_LIBRARY_PATH=/tmp/sw-tools/root/usr/lib/x86_64-linux-gnu /tmp/sw-venv/bin/python draw_body_concept.py
```

- It takes about 2 min. The silhouettes of the existing machine are cached in `/tmp/sw-render/b1_silhouettes.pkl`.
- It reads:
  - the X1 scene files in `../../source/`;
  - `../../simulation/turntable_mass_properties.json` and `turntable_swing_report.json`;
  - the R3 constants, imported from `../../swing_concept/source/draw_swing_concept_r3.py`;
  - the Caterpillar images in `excavator_arm_60mm/references/`.

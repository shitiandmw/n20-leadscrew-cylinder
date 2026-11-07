# Bought slip ring, 6-way 2 A (and 12-way 2 A): source of the sizes in concept R2

- **Source:** the seller's dimension drawing, sent by the user on 2026-11-03 (titles "6路2A 尺寸图" and "12路2A 尺寸图"). The seller and part number were not given.
- **File:** `seller_drawing_6_and_12_way.png`, 2410 × 2608 px. SHA-256: `7baf35543fbdf9903d991b76b4316e0610d6c1071b120be08842ea14eeb72bd9`.
- It is a flanged capsule slip ring of the same family as the SRC022 series in `../prosper_src022/`. It matches the **standard type (SRC022)**, not the A type that concept R1 assumed: the flange sits 5 mm back from the rotor end, not at the rotor end.

## Values read from the drawing (mm)

| Item | 6-way 2 A | 12-way 2 A |
|---|---|---|
| Stator body | Ø22, L = 19 | Ø22, L = 26 |
| Flange | Ø44 × 2.4. Its rotor-side face is 5 from the rotor end of the body; its far face is 7.4 from it | same |
| Flange holes | 3 × Ø5.4, equally spaced on Ø35 | same |
| Rotor | Ø7.8 × 9, out of the rotor end of the body | same |
| Rotor leads | leave the end of the rotor | same |
| Stator leads | leave the far end of the body | same |
| Rated current | 2 A per ring (from the title) | same |

L runs from the rotor end of the body to the stator end. The body below the flange is therefore 19 − 7.4 = 11.6 (6-way) or 26 − 7.4 = 18.6 (12-way).

## Not given on the drawing: check with the seller before buying

- rated voltage, maximum speed and lead length (the SRC022 datasheet gives 240 V, 300 rpm and 250 mm leads for its own parts);
- lead gauge and colour code;
- which end the leads are numbered from.

## How concept R2 uses it

- **Fixed half (stator) on the chassis.** The Ø22 × 5 part of the body above the flange is a ready-made spigot. It locates in a Ø22.4 bore in a new collar under the X-frame's top plate, so the ring is centred on the swing axis even though the Ø5.4 holes are loose on M3 screws.
- **Rotor turned by the turntable** through a loose dog and fork, so the ring carries no load.
- The mount takes either length; only the body below the flange is longer on the 12-way.

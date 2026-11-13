# Ø32 / Ø6 aluminium flange coupling (J9 sprocket hub)

The J9 sprockets used the Pololu #1999 hub until 2026-11-12. It could not be bought, so the user found this flange coupling instead.

`seller_drawing.jpg` is the seller's dimension drawing, supplied by the user. The listing covers bores D = 4, 5, 6 and 8 mm; J9 uses D = 6.

The user checked every value below on the real part on 2026-11-12, on a confirmation sheet made for the purpose:

| Item | Value |
|---|---|
| Overall length | 14 mm |
| Flange | Ø32 × 4 mm, flat face |
| Boss | Ø14 × 10 mm |
| Bore | Ø6 |
| Flange holes | 6 × M3, tapped, on a Ø23 circle, 60° apart |
| Set screw | one radial M3 in the boss, centre 5 mm from the boss end, halfway between two flange holes |
| Material | aluminium (about 11 g) |

How J9 uses it:
- **Pose.** The flange sits in a Ø32.4 × 1 recess in the sprocket's inner face. Every other hole, at 0°, 120° and 240°, takes an ISO 4762 M3 × 20 screw from the sprocket's outer face.
- **Set screw.** It points up onto the motor shaft's D-flat. The boss end stands 1.0 mm off the inner wall.
- **Not given by the seller.** There is no set-screw length and no torque rating. The CAD assumes M3 × 4; anything up to 4.5 mm long stays below the boss surface. Check the set screw after the first runs.

`J9/source/build_j9.py` checks the modelled coupling against these values (`validation.json → drive_hub.seller_drawing_check`).

# Cab reference and upper-body packaging

The cab uses the same Caterpillar 320 reference and nominal 1:15 scale as arm60. The primary source is the manufacturer’s [320 technical specifications](https://s7d2.scene7.com/is/content/Caterpillar/CM20240927-d80d6-c6a9b), page 4; an offline copy is included at `../../excavator_arm_60mm/references/cat320_specifications.pdf`.

## What the source establishes

Published dimensions include a 5,700 mm boom, 2,960 mm ground-to-cab-roof height, 2,780 mm upperframe width, 2,830 mm tail radius and 3,650 mm roller-centre length. The boom is 380 mm in arm60, confirming the nominal 1:15 reference.

The document does **not** give standalone cab length, width or height. Those are estimated from its side/rear illustrations. On a 2× rendering of page 4, the side roller-centre span is approximately 239 pixels for 3,650 mm. The cab spans approximately 118 pixels in length and 115 pixels in height. The rear illustration has approximately 181 pixels for the 2,780 mm upperframe and 66 pixels for the cab width. Illustration strokes and perspective limit precision; these are not factory manufacturing dimensions.

| Cab envelope | Drawing estimate at 1:15 | R1 | R2 |
|---|---:|---:|---:|
| Length | about 120 mm | 110 mm | 120 mm |
| Width | about 68 mm | 40 mm | 70 mm |
| Height, including roof | about 117 mm | 108 mm | 118 mm |

The R1 table entries describe its main enclosure; the original 10 mm mounting feet and roof overhang are excluded. Its complete mounted cab envelope was 116 × 46 × 118 mm. The 75% increase compares cab body widths (40 to 70 mm), not roof overhangs.

R2 adds a sloped windscreen, removable 0.8 mm PET glazing, a seat and two side consoles. Its 70 mm width follows the drawing estimate with a small construction allowance; it is 75% wider than R1. Interior details are model design choices, not copied factory controls.

R3 keeps this cab unchanged and moves it to the Cat 320 position: front left, beside the boom foot, 23 mm further forward than R2, with the windscreen at X98.

## Chassis adaptations remain explicit

The complete machine is not an exact uniformly scaled Cat 320. The original arm mount, actuator motor sections, purchased bearings and steel shafts do not scale down. The track gauge and upperframe remain wider than the 1:15 manufacturer dimensions to accommodate this hardware.

R2 lowers the upper deck and original arm mounting plane from Z182 to Z134 mm. The 40 mm slew-bearing separation is retained; its tube and motor now recess through the chassis. The cab roof is Z252 mm, versus approximately 197 mm for a strictly 1:15 real-machine roof height. The retained mechanical interfaces explain this remaining height difference.

The structural clearance from the Z80 bridge top to the Z124 deck underside is 44 mm, reduced from 92 mm. A removable rotating skirt begins at Z92, leaving 12 mm visibly exposed above the bridge. It clears the tracks and encloses the bearing, motor and gears without carrying their loads. It has a clearance notch for the mechanical stop tab.

The reduced deck height introduces a bucket/track collision for unrestricted low-boom sideways slew. The preview allows the full 0–60 mm boom stroke at every angle within ±150°; the operator manages track clearance. The retained CAD reference samples use boom stroke ≥15 mm or slew within ±20°, and do not establish clearance throughout the full independent travel range. The unrestricted failing test remains in the simulation folder.

## R3 upper-body layout

R3 follows the arrangement shown in the page 4 drawings and Cat 320 product images. The cab is at the front left, and a stepped toolbox and a tank housing fill the front right. The engine hood spans the rear half, and the counterweight's rear face is an arc about the swing centre. That arc uses the published 2,830 mm tail swing radius: 188.7 mm at 1:15, rounded to 189 mm. The measured maximum radius over every rotating upper-body part is 189.0 mm.

The deck is 308 mm wide, against about 185 mm for a strict 1:15 upperframe, for the same hardware reasons as the track gauge. The hood and counterweight tops are at Z206, 72 mm above the deck; the cab roof remains at Z252.

The two-cell battery now sits in a datasheet-sized cradle under a removable hood hatch, beside its BMS and converters. See `ASSEMBLY.md` for the cell envelopes and fit results. Its electrical arrangement is 2S1P, with 12 V and 6 V regulated rails; two cells must not be described as a direct 12 V source.

# X1 bill of materials (crawler chassis)

X1 is two J9 track modules plus the X-frame, the belly cover and the slewing ring. The right track is a mirror image of J9: it uses the mirrored H-frame and housing prints listed here, and the same prints as the left track for everything else.

## Printed: 32 pieces, plus 68 track shoes

| Part | Qty | Material and orientation | Notes |
|---|---|---|---|
| X101_X_frame | 1 | PETG or PA12; bearing seat on the bed. Qualify wall count, infill and layer orientation for the intended load. | Revision F: round carbody and four straight 28 mm arms. Each flat arm end seats in a plain 1.5 mm main-plate recess, with one horizontal M4 screw in each side slot. Retains the RU66 seat, slip-ring collar, ring-gear holes, belly-cover inserts and cable passages. Print bounds are 155 × 275 × 51 mm; export checks are in revf_part_exports.json. Inverted printing needs support beneath the arm decks and the head-slot roofs; check the slicer and keep the arm end faces and washer faces clean. |
| X102_belly_cover | 1 | PETG, 3 walls. Flat, countersinks up. | Ø120 × 3 guard under the carbody, 4 countersunk M3 holes. |
| J901_H_frame_right | 1 | As J9 J901, mirrored: outer wall face on the bed; supports under the inner wall. | Revision F inner main plate with plain rectangular arm seats, plain mounting holes and retained mechanism recesses; accepted enclosed spring guide. |
| J909_housing_right | 1 | As J9 J909, mirrored: skirt inner face on the bed; supports inside the motor pod. | Revision F openings that follow the X101 arms with 0.5 mm clearance, plus a shallow screw-entry lane in the pod shell beside each rear arm; all four cover attachment axes are retained from E. |
| J901_H_frame | 1 | As J9. | Left track. |
| J909_housing | 1 | As J9. | Left track. |
| J902_sprocket | 2 | As J9. | One per track. The same print works on both sides. |
| J903_journal_plug | 2 | As J9. | |
| J904_roller | 14 | As J9. | 5 road and 2 support rollers per track. |
| J906_idler_wheel | 2 | As J9. | |
| J907_idler_spacer | 4 | As J9. | |
| J908_U_yoke | 2 | As revised J9. | Sliding piston on the rear face guides the spring end inside the main-beam bore. |
| J910_track_shoe_70 | 68 | As J9. | 34 per track. |

Materials and settings for the J9 parts are in [J9's BOM](../J9/BOM.md).

## Bought for X1: 73 pieces

| Item | Qty | Use |
|---|---|---|
| THK RU66 cross-roller ring: Ø35 bore, Ø95 outside, 15 high (catalogue A18-20/21) | 1 | Slewing ring. The outer ring bolts to the X-frame; the inner ring is left for the turntable. It can be bought together with the turntable. See `references/thk_ru66/SOURCE.md` before buying an equivalent from another maker. |
| M4 × 30 socket head screw (ISO 4762) | 8 | Outer ring to the X-frame, from above through the ring's Ø8 counterbores, the seat and the retained mount-ring interface on X101 revision F. |
| M4 nut (ISO 4032) | 8 | Under the mount ring, reached from below with a 7 mm socket (belly cover off). |
| DIN 6796 M4 conical spring washer | 8 | Under each nut, intended to add compliance; preload retention as the plastic creeps still needs testing. |
| DIN 9021 M4 washer (Ø12) | 8 | Between the spring washer and the mount ring: spreads the load on the print. |
| M4 × 25 socket-head screw (ISO 4762), Ø7 × 4 head | 8 | One horizontal screw in each side slot of the arm; two per joint. Slides in sideways; use a 3 mm L-key with its handle out of the slot. |
| M4 nut (ISO 4032), 7 mm across flats × 3.2 mm thick | 8 | External to the J901 main plate, behind a washer. Hold with a compact 7 mm nut-holding tool while tightening with rear sprocket and chain removed; rollers and their axles are already fitted. |
| M4 washer, Ø9 outside / Ø4.4 bore × 0.8 mm | 16 | One under each mounting screw head and each external nut. |
| M3 × 8 countersunk screw (ISO 10642) | 4 | Belly cover, from below: 5 mm in the insert. |
| M3 heat-set insert (hole Ø4.0 × 5.7, as J9) | 4 | Cover bosses inside the carbody. |

## Bought for the two tracks: 106 pieces

These are two revised J9 sets of 53 pieces each; see [J9's BOM](../J9/BOM.md).
- **Motors:** two JGY-370-1260 12 V 200:1 motors.
- **Hubs:** one Pololu #1999 pack, which holds two hubs.
- **No chassis-boss inserts:** the three M4 inserts per track were removed. The eight joint nuts are counted in X1 above.

## Track hardware (two J9 tracks)

| Item | Qty |
|---|---|
| Ø3 × 56 steel track pin | 68 |
| Ø6 / Ø3.1 × 17 steel bushing | 68 |
| Pin clip | 136 |

## Not counted


- **Motor lead wire.** Each motor's leads run about 180 mm from the pod's port to the turntable face. Add slack, plus whatever run the turntable needs.
- **Turntable and swing drive.** Listed separately in [TURNTABLE.md](TURNTABLE.md) (7 prints, 8 printed pieces, and their bought hardware).
- **Body B1 rev B.** Listed separately in [BODY.md](BODY.md):
  - 7 prints: B101 counterweight, the B102 and B103 halves, B104 cab interior, B105 operator, B106 battery hatch and B107 left handrail.
  - The steel shot.
  - The battery (3 × 18650 in Keystone 1043 holders) and the electronics.
  - 8 magnets (Ø6 × 2).
  - 4 M3 and 2 M4 screws with their inserts.

## Counts

| | X1 parts | Two J9 tracks | Chassis |
|---|---|---|---|
| Printed pieces (without the shoes) | 2 (X101, X102) | 30 (the right track's J901 and J909 are the mirrored prints) | 32 |
| Track shoes | — | 68 | 68 |
| Bought pieces (without the track hardware) | 73 (including RU66 and joint hardware) | 106 | 179 |
| Custom-machined parts | 0 | 0 | 0 |

# X1 bill of materials (crawler chassis)

X1 is two J9 track modules plus the X-frame, the belly cover and the slewing ring. The right track is a mirror image of J9: it uses the mirrored H-frame and housing prints listed here, and the same prints as the left track for everything else.

## Printed: 32 pieces, plus 68 track shoes

| Part | Qty | Material and orientation | Notes |
|---|---|---|---|
| X101_X_frame | 1 | PETG or PA12, 4 walls, 30 % infill. Upside down: the flat top (the bearing seat) on the bed; no supports. | Carbody, four legs and two rails in one piece. 8 M4 seat inserts, 4 M3 cover inserts, Ø25 cable passage, two Ø10 cable holes, Ø8 access holes in the rails. Print bounds 188 × 248, 51 high. 444 cm³ (564 g if printed solid in PETG). |
| X102_belly_cover | 1 | PETG, 3 walls. Flat, countersinks up. | Ø120 × 3 guard under the carbody, 4 countersunk M3 holes. |
| J901_H_frame_right | 1 | As J9 J901, mirrored: outer wall face on the bed; supports under the inner wall. | H-frame for the right track. Print bounds 275 × 64, 76 high. |
| J909_housing_right | 1 | As J9 J909, mirrored: skirt inner face on the bed; supports inside the motor pod only. | Housing and motor pod for the right track. Print bounds 287 × 67, 27 high. |
| J901_H_frame | 1 | As J9. | Left track. |
| J909_housing | 1 | As J9. | Left track. |
| J902_sprocket | 2 | As J9. | One per track. The same print works on both sides. |
| J903_journal_plug | 2 | As J9. | |
| J904_roller | 14 | As J9. | 5 road and 2 support rollers per track. |
| J906_idler_wheel | 2 | As J9. | |
| J907_idler_spacer | 4 | As J9. | |
| J908_U_yoke | 2 | As J9. | |
| J910_track_shoe_70 | 68 | As J9. | 34 per track. |

Materials and settings for the J9 parts are in [J9's BOM](../J9/BOM.md).

## Bought for X1: 31 pieces

| Item | Qty | Use |
|---|---|---|
| THK RU66 cross-roller ring: Ø35 bore, Ø95 outside, 15 high (catalogue A18-20/21) | 1 | Slewing ring. The outer ring bolts to the X-frame; the inner ring is left for the turntable. It can be bought together with the turntable. See `references/thk_ru66/SOURCE.md` before buying an equivalent from another maker. |
| M4 × 16 socket head screw (ISO 4762) | 8 | Outer ring to the X-frame, from above through the ring's Ø8 counterbores: 5.6 mm in the insert. |
| M4 heat-set insert (hole Ø5.6 × 8.1, as J9) | 8 | Bearing seat, pressed in from the top face. Flush with the seat or just below it. |
| M4 × 12 socket head screw (ISO 4762) | 6 | Rails to the J9 chassis-boss inserts, 3 per track, fitted from the inboard side: 6 mm in the insert. |
| M3 × 8 countersunk screw (ISO 10642) | 4 | Belly cover, from below: 5 mm in the insert. |
| M3 heat-set insert (hole Ø4.0 × 5.7, as J9) | 4 | Cover bosses inside the carbody. |

## Bought for the two tracks: 112 pieces

These are two J9 sets of 56 pieces each; see [J9's BOM](../J9/BOM.md).
- **Motors:** two JGY-370-1260 12 V 200:1 motors.
- **Hubs:** one Pololu #1999 pack, which holds two hubs.
- **Chassis-boss inserts:** each set includes the three M4 inserts that take the rail screws.

## Track hardware (two J9 tracks)

| Item | Qty |
|---|---|
| Ø3 × 56 steel track pin | 68 |
| Ø6 / Ø3.1 × 17 steel bushing | 68 |
| Pin clip | 136 |

## Not counted

- **Motor lead wire.** Each motor's leads run about 180 mm from the pod's port to the turntable face. Add slack, plus whatever run the turntable needs.
- **Turntable and swing drive.** Not part of X1.

## Counts

| | X1 parts | Two J9 tracks | Chassis |
|---|---|---|---|
| Printed pieces (without the shoes) | 2 (X101, X102) | 30 (the right track's J901 and J909 are the mirrored prints) | 32 |
| Track shoes | — | 68 | 68 |
| Bought pieces (without the track hardware) | 31 (including the RU66) | 112 | 143 |
| Custom-machined parts | 0 | 0 | 0 |

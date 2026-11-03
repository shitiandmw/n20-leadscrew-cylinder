# J9 bill of materials (one track module)

The mirrored module for the other side uses the same parts, assembled as a mirror image. The H-frame and the housing then need mirrored prints.

## Printed: 15 pieces, plus 34 track shoes

| Part | Qty | Material and orientation | Notes |
|---|---|---|---|
| J901_H_frame | 1 | PETG or PA12, 3 walls, 30 % infill. Outer wall face on the bed; supports under the inner wall. | Two 6 mm walls and an 18 mm web. Motor seat, 6800ZZ seat, 7 roller holes, yoke grooves, 3 chassis bosses. On the inner wall: the motor rim that closes the gap behind the housing skirt, and 4 housing standoffs. Print bounds 275 × 76 × 64. |
| J902_sprocket | 1 | PETG or PA12, 5 walls, 50 % infill. Outer disc face on the bed, no supports. | Unchanged 12-tooth, 20 mm pitch form. Ø25.8 × 1 recess for the hub flange, 3 counterbored M3 holes on a Ø19.05 circle, stop pad for the shaft end, Ø10.1 socket for the plug. |
| J903_journal_plug | 1 | PETG or PA12, 100 % infill, standing on its end. | Ø9.95 × 26.5 journal in the 6800ZZ, with an M3 clearance bore. |
| J904_roller | 7 | PETG, 4 walls, 40 % infill, on a flange face. | Road (5) and support (2) roller: Ø22 tread, Ø26 flanges, 46 wide, two Ø13 bearing seats. |
| J906_idler_wheel | 1 | As J8 07_idler_wheel. | Unchanged J8/R5 idler, two 608 seats. |
| J907_idler_spacer | 2 | PETG, 100 % infill. | Ø11 / Ø8.2 × 13.9 tube. It touches only the 608 inner ring. |
| J908_U_yoke | 1 | PETG or PA12, 4 walls, 50 % infill, upside down on its flat top. | Arms slide in the wall grooves; Ø8.1 pin holes; spring pilot on the back. |
| J909_housing | 1 | PETG, 3 walls. Skirt inner face on the bed; supports inside the motor pod only. | Inboard skirt and closed motor pod in one piece: drum on the sprocket axis, gearbox shoulder, motor tube, nose with a Ø5.5 cable port. Ø8 roller-bolt access holes. Print bounds 287 × 67 × 27. |
| J910_track_shoe_70 | 34 | PETG or PA12, grousers on the bed (as R4). | R4 shoe and link plates, with the shoe plate widened to 70 mm. |

## Bought: 56 pieces

| Item | Qty | Use |
|---|---|---|
| JGY-370-1260 12 V worm gear motor, 200:1. Shop options: "12V 电机" (motor only, no bracket or speed controller) and "每分钟/30转 6KG.CM". | 1 | Drive. Gearbox face on the inner wall. 30 rpm no load; 6 kgf·cm rated at 0.2 A; 20 kgf·cm stall at 1.3 A (vendor table). |
| Pololu #1999 universal aluminium mounting hub, 6 mm shaft, M3 holes (sold in pairs: one pack does both tracks) | 1 | Sprocket hub on the motor's D-shaft. Sized from Pololu's drawing and STEP (`track_wheel_jgy370/references/pololu_1999/`). |
| M3 set screws, supplied with the hub | 2 | Both bear on the D-flat. The CAD assumes 8 mm in the flange and 3 mm in the boss, because Pololu gives no lengths. Anything up to 10 mm (flange) or 3.5 mm (boss) stays below the surface. |
| 6800ZZ bearing, 10 × 19 × 5 | 1 | Outer support of the sprocket (journal plug). |
| 624ZZ bearing, 4 × 13 × 5 | 14 | Two per roller. |
| 608ZZ bearing, 8 × 22 × 7 | 2 | Idler (as J8). |
| Ø8 × 55 steel pin (ISO 2338 8 m6 × 55, or Ø8 shaft cut to 55) | 1 | Idler axle in the yoke. |
| M4 × 70 socket head screw (ISO 4762) | 7 | Roller axles, fitted from the inboard side. |
| M4 nyloc nut (DIN 985) | 7 | Roller axles, outboard side. Tighten until snug only. |
| M3 × 6 socket head screw (ISO 4762) | 4 | Motor to inner wall, from inside the H (3 mm engagement). |
| M3 × 50 socket head screw (ISO 4762) | 1 | Journal plug and sprocket onto the motor shaft's tapped end. |
| M3 × 25 socket head screw (ISO 4762) | 3 | Sprocket to the hub, from the sprocket's outer face. 5 mm thread in the hub. |
| M3 × 8 button head screw (ISO 7380) | 4 | Housing to the standoffs on the inner wall: 5.5 mm in the insert. |
| M3 heat-set insert (hole Ø4.0 × 5.7) | 4 | Tops of the housing standoffs on the inner wall. |
| M4 heat-set insert (hole Ø5.6 × 8.1) | 3 | Chassis bosses. |
| Compression spring, Associated/Lee Spring C-600-072-1500 (R5 part) | 1 | Idler tension: 25.8 fitted, 77 N. |

## Track hardware (unchanged R4/J8 chain)

| Item | Qty |
|---|---|
| Ø3 × 56 steel track pin | 34 |
| Ø6 / Ø3.1 × 17 steel bushing | 34 |
| Pin clip | 68 |

## Counts

| | J9 CAD | J9 concept | J8 |
|---|---|---|---|
| Printed pieces (without the track) | 15 | 12 | — |
| Bought pieces (without the track) | 56 | 51 | — |
| Total without the track | 71 | 63 | 148 (25 custom machined) |
| Custom-machined parts | 0 | 0 | 25 |

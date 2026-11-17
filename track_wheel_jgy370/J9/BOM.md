# J9 bill of materials (one track module)

The mirrored module for the other side uses the same parts, assembled as a mirror image. The H-frame and the housing then need mirrored prints.

## Printed: 15 pieces, plus 34 track shoes

| Part | Qty | Material and orientation | Notes |
|---|---|---|---|
| J901_H_frame | 1 | PETG or PA12. Qualify wall count, infill and layer orientation for the intended load; no structural print recipe is validated. Outer wall face on the bed; supports under the whole inner wall, standing on the part itself (not "build plate only"). | Revision F: inner main plate with 10 mm base thickness, 1.5 mm deep curved-support receiving seats and plain mounting holes; outer wall remains 6 mm. Mechanism recesses retain the motor seat, 7 roller axes and yoke grooves. Retains the 6800ZZ seat, main web, recessed Ø16.4 spring guide with Ø21.2 exterior, motor rim and four cover standoffs. The support seats include lower receiving shoulders; no separate projecting chassis pads or recessed mounting-nut pockets. Use the current STL bounds. 2026-11-14: Ø6.2 roller bosses, 0.5 mm of side room in the yoke grooves, Ø4.0 × 7 insert bores, and a Ø3.2 lock-pin hole through the outer wall at the yoke's recoil-stop position (ASSEMBLY.md 7). |
| J902_sprocket | 1 | PETG or PA12, 5 walls, 50 % infill. Outer disc face on the bed, no supports. | Unchanged 12-tooth, 20 mm pitch form. Ø37 × 1.5 ring with a Ø32.4 × 1 recess for the coupling flange, 3 counterbored M3 holes on a Ø23 circle, Ø5.4 × 5.4 stop pad down the coupling bore to the shaft end, Ø10.1 socket for the plug. |
| J903_journal_plug | 1 | PETG or PA12, 100 % infill, standing on its end. | Ø9.95 × 26.5 journal in the 6800ZZ, with an M3 clearance bore. |
| J904_roller | 7 | PETG, 4 walls, 40 % infill, on a flange face; no supports (the top flange is a 2 mm overhanging ring: trim any sag). | Road (5) and support (2) roller: Ø22 tread, Ø26 flanges, 46 wide, two Ø13 bearing seats. Ø8 centre bore, so each seat's shoulder bears only on the 624 outer ring (Ø6 until 2026-11-11). |
| J906_idler_wheel | 1 | PETG; no validated recipe (4 walls, 40 % as the roller is a reasonable start). Flat face on the bed; supports everywhere: three overhanging rings and the web under the upper bearing seat. | J8/R5 idler outline. Both 608 seats open to the faces: a Ø22.6 slide-in bore with a 0.6 mm chamfer, then the Ø22.2 × 7.5 press seat against the central web. (The inherited wheel had both seats sealed behind Ø16.4 necks.) |
| J907_idler_spacer | 2 | PETG, 100 % infill. | Ø11 / Ø8.2 × 13.9 tube. It touches only the 608 inner ring. |
| J908_U_yoke | 1 | PETG or PA12, 4 walls, 50 % infill, upside down on its flat top; support the rear piston as needed. | Arms slide in the wall grooves; Ø8.1 pin holes; rear Ø15.6 × 8 piston and spring pilot enter the revised J901 guide bore. A Ø3.2 × 8 lock-pin hole in each end of the crossbar, so the same print fits both tracks (2026-11-14). |
| J909_housing | 1 | PETG, 3 walls. Skirt inner face on the bed; supports inside the motor pod only. | Inboard skirt and closed motor pod in one piece: drum on the sprocket axis, gearbox shoulder, motor tube, nose with a Ø5.5 cable port. Ø8 roller-bolt access holes, curved-support clearance openings and retained cover attachment axes. Current print bounds are in the revision F export report. |
| J910_track_shoe_70 | 34 | PETG or PA12, 4 walls, 40 % infill, grousers on the bed, no supports. | Revision B (2026-11-14) of the R4 link on a 70 mm shoe plate. Seat bosses outside both outer plates carry the screw head and the nut, 50 mm apart. R4.6 reliefs round both joint axes keep 0.6 mm between neighbouring links. Inner ears 4.5 mm thick, 18.4 mm apart: 0.2 mm a side for the sleeve, 0.7 mm a side for the sprocket. Lead-in chamfers for the sprocket teeth and the roller flanges; outer grousers at the plate edges. A shoe printed from a file older than 2026-11-14 is the earlier one: do not mix them. |

## Bought: 52 pieces

| Item | Qty | Use |
|---|---|---|
| JGY-370-1260 12 V worm gear motor, 200:1. Shop options: "12V 电机" (motor only, no bracket or speed controller) and "每分钟/30转 6KG.CM". | 1 | Drive. Gearbox face on the inner wall. 30 rpm no load; 6 kgf·cm rated at 0.2 A; 20 kgf·cm stall at 1.3 A (vendor table). |
| Ø32 / Ø6 aluminium flange coupling: flange Ø32 × 4 with 6 × M3 tapped holes on a Ø23 circle, boss Ø14 × 10, bore 6 mm | 1 | Sprocket hub on the motor's D-shaft, replacing the Pololu #1999 hub, which could not be bought (2026-11-12). Sized from the seller's drawing, with every value checked on the part (`track_wheel_jgy370/references/flange_coupling_32/`). |
| M3 set screw, supplied with the coupling | 1 | In the boss, 5 mm from its end, halfway between two flange holes; bears on the D-flat. The seller gives no length: the CAD assumes 4 mm, and anything up to 4.5 mm stays below the boss surface. |
| 6800ZZ bearing, 10 × 19 × 5 | 1 | Outer support of the sprocket (journal plug). |
| 624ZZ bearing, 4 × 13 × 5 | 14 | Two per roller. |
| 608ZZ bearing, 8 × 22 × 7 | 2 | Idler (as J8). |
| Ø8 × 55 ground steel rod, tolerance h6 or g6 (cut linear shaft) | 1 | Idler axle in the yoke. Not an ISO 2338 m6 dowel pin: that is a press fit in the 608 bores, which cannot be backed up inside the yoke. |
| M4 × 70 socket head screw (ISO 4762), partly threaded | 7 | Roller axles, fitted from the inboard side. With the standard 20 mm of thread the bearings sit on plain shank. |
| M4 nyloc nut (DIN 985) | 7 | Roller axles, outboard side. Tighten until snug only. |
| M3 × 6 socket head screw (ISO 4762) | 4 | Motor to inner wall, from inside the H (3 mm engagement). |
| M3 × 50 socket head screw (ISO 4762) | 1 | Journal plug and sprocket onto the motor shaft's tapped end. |
| M3 × 20 socket head screw (ISO 4762) | 3 | Sprocket to the coupling, from the sprocket's outer face: 4 mm of thread in the flange, tip 1.5 mm past it. |
| M3 × 8 button head screw (ISO 7380) | 4 | Housing to the standoffs on the inner wall: 5.5 mm in the insert. |
| M3 heat-set insert, outside Ø4.5–4.6, up to 5.7 long (hole Ø4.0 × 7) | 4 | Tops of the housing standoffs on the inner wall. The bores are 1.3 mm deeper than the insert. |
| Compression spring, Associated/Lee Spring C-600-072-1500 (R5 part), or equal: wire 1.8, outside Ø15, free length 38–40, 9–10 coils | 1 | Idler tension: 25.8 fitted, 77 N. An equal spring must slide in the Ø16.4 bore (outside Ø15.6 at most) and over the Ø11 pilot (inside Ø11.3 at least), with a solid height under 19 mm. |

## Track hardware (J910 revision B, 2026-11-14)

| Item | Qty | Use |
|---|---|---|
| M3 × 60 socket head screw (ISO 4762), partly threaded: 18 mm of thread | 34 | One per joint, head outboard. The sleeve and the inner ears turn on smooth shank. M3 × 50 is too short: the two seats are 50 mm apart before the nut starts. Buy a few spares; one serves as the lock pin when the chain is closed. |
| Steel sleeve Ø6 / Ø3.2 × 18 | 34 | Between the inner ears of every joint; the sprocket teeth drive on it. A stock spacer size; 17 mm long also fits. |
| M3 nyloc nut (DIN 985) | 34 | Inboard, on the seat boss. Run it down until it touches the seat, then back it off 1/6 turn: it must not clamp the joint. |

The earlier chain (Ø3 × 56 grooved pins, Ø6 / Ø3.1 × 17 bushings and two E-clips per joint) is superseded. Its pins could slide 5.2 mm either way, which put an E-clip under a roller flange.

## Counts

| | J9 CAD | J9 concept | J8 |
|---|---|---|---|
| Printed pieces (without the track) | 15 | 12 | — |
| Bought pieces (without the track) | 52 | 51 | — |
| Total without the track | 67 | 63 | 148 (25 custom machined) |
| Custom-machined parts | 0 | 0 | 25 |

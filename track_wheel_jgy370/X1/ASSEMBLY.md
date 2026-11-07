# X1 revision F assembly

Use the matching revision F X101, both J901 track frames and both J909 housings. The accepted J908 spring-piston yoke remains in use. Earlier mounting-joint instructions are obsolete.

## 1. Prepare the track modules

1. Clean the two shallow receiving seats and four plain mounting holes in each track main plate. **Fit the road and support rollers and their axle bolts before mounting the tracks to X101. Leave the rear sprocket and chain off** so the external mounting nuts remain accessible to a socket.
2. Prepare the left track following [J9's assembly guide](../J9/ASSEMBLY.md). Prepare the right track with the mirrored J901 and J909 supplied in X1; its other printed parts are shared with J9. Turn the right motor 180° about its can axis to align the shaft and mounting holes.
3. Fit the motor, road and support rollers with their axle bolts, and housing using J9’s sequence. The front idler/tensioner may also be installed. Confirm free spring-piston motion through 4.2 mm recoil. Reserve the rear sprocket/hub and chain for installation after tightening the chassis joints.
4. Route each motor's leads through the housing port, allowing approximately 180 mm to the turntable face plus service slack.

## 2. Prepare the X-frame

1. Remove support material from under the four arm decks and from the eight head slots. Deburr the arm end faces, their lower edges, the washer faces at the slot ends and the plain screw holes. Each arm end must enter its shallow receiving seat without being held off by print ridges or housing edges.
2. Fit the four M3 heat-set inserts for the belly cover. If fitting the turntable, also fit the three M3 inserts in the slip-ring collar. The eight RU66 mounting holes are plain through-holes.
3. Check the RU66 seat for flatness. Keep X101 bare for fitting: install the slewing bearing, upper drive and belly cover after the track joints are seated and tightened.

## 3. Seat and bolt the arm ends

1. Secure both track modules upright and parallel at their final height, final drives at the rear, on 340 mm centres. Their motor, housing, road/support rollers and long axle bolts must already be fitted; the front idlers may remain fitted. Leave both rear sprockets/hubs, journal plugs, chains and all chassis-joint fasteners off. Independently support the bare X101 frame 80 mm above its final position and align all four arm ends over the open-top receiving seats.
2. Lower X101 vertically into both tracks together, maintaining their final spacing and alignment. The checked approach is a continuous 80 mm downward stroke. Do not push either track sideways into X101: that route clashes with the motor can and housing. Confirm the arm undersides meet the seat ledges and the end faces sit evenly on the seat floors. Do not force a misaligned or warped print with screw pressure. Run each motor's leads forward from the port, under the arms, to about X 34 beside the front arm, then inboard into the carbody's Ø10 side hole, with sufficient slack for seating. Do not take them straight across the gap between the arms: the inner joint screws' L-key swings through there.
3. At every joint fit **two M4 × 25 ISO 4762 socket screws**, one in each side slot of the arm. With its head washer already fitted, lower each screw beside the arm, slide it sideways into the slot with its tip toward the track, align it with the plain hole, then push it through. At the rear arms the outer screw slides over the motor pod in the shallow lane provided in the housing. Use a **Ø9/Ø4.4 × 0.8 mm washer beneath each screw head and each nut**. Fit external **M4 nuts, AF7 × 3.2 mm**. The chassis uses eight screws, sixteen washers and eight nuts; none is recessed or captive in a printed pocket.
4. Select a **compact 7 mm nut-holding tool**. Its complete body, shaft, drive junction and handle must fit within the checked **Ø11.2 mm maximum envelope**; an additional larger ratchet head is outside this check. Keep the rear sprocket and chain off for access. Road/support rollers and the front idler may remain fitted.
5. Start all screws by hand and hold each nut from the track interior. Turn the screw with a **3 mm L-key with a 20 mm short leg and 80 mm arm**: the short leg goes into the head along the screw axis and the long arm comes out of the side slot. Swing it from 30° below to 30° above horizontal, withdraw the key 3 mm, reset and reinsert. Confirm the actual key bend and complete nut-holding tool fit the nominal routes in `arc_seat_mount_validation.json`.
6. Tighten the paired screws gradually so the contact faces remain seated. Check that every washer lies flat and no nut or head cuts into the print. Do not use screw force to straighten a warped arm.
7. The nominal stack has the screw face at local Y−43.8, the nut at Y−23.2 to −20 and the screw tip at Y−18.8: full 3.2 mm geometric nut overlap and 1.2 mm nominal tip projection. Chamfers, thread runout and tolerances are not modelled; verify actual engagement and wheel clearance. Do not substitute longer screws without checking the track interior.
8. Fit the rear sprocket/hub, journal plug and chain using J9's sequence. Complete the front tensioner if it was not fitted earlier. Recheck alignment, fastener seating, full spring recoil and both chains through a complete hand-turned circuit. No wheel may rub a nut, washer or screw tip.

No tightening torque or payload has been qualified for these printed joints. Establish appropriate limits with physical tests and avoid crushing the main plate or the arm end.

## 4. Wiring

1. Route the four motor leads through the Ø25 centre passage, clear of fasteners and rotating parts. Retain service slack.
2. Reverse the right motor electrically or in the controller so both tracks drive forward together.
3. Leave X102 off until the slewing-bearing nuts and upper-drive hardware have been installed through the open underside.

## 5. Slewing bearing and upper drive

The ring gear goes on before the RU66. Follow [TURNTABLE.md](TURNTABLE.md) for the retained R3 sequence.

The RU66 outer ring uses eight M4 × 30 socket screws from above, with a Ø12 washer, conical spring washer and M4 nut below the X101 mounting ring. Reach the nuts from the open underside before fitting the belly cover. Tighten evenly while checking free rotation.

The turntable attaches to the inner ring's eight M4 tapped holes on PCD45. Its support flange stays within Ø59, and the retained Ø75 seat relief clears the existing turntable geometry.

After the bearing and upper drive are fitted, check the motor leads and all underside fasteners. Then fit X102 from below with four **M3 × 8 countersunk screws**.

## 6. Body B1 (after the turntable)

The full order is in [BODY.md](BODY.md#assembly-order-each-step-checked-in-cad). In short:
1. **T101 inserts.** Press 4 M3 inserts into the T101 rib tops (X −120 and −45, Y ±65), before the ARM60 goes on.
2. **Counterweight.** Fit B101, with its shot already printed in, using 2 × M4 × 12 from inside T101 through the rear bulkhead. The swing motor's leads go into its channel.
3. **Halves on the bench.**
   - Wire each half: the controller board in the left bay; the switch, fuse and charge jack in the right.
   - Glue the 4 ledge magnets into the halves (see BODY.md for the polarity).
   - Left half only: slide the cab interior B104, with the operator B105 on its seat peg, in from the open boom side and drop it onto the 2 floor pegs. Press the handrail and mirror, B107, into the 2 holes on the cab's front-left pillar.
4. **Halves on.** Fit each half 10 mm outboard of its place, slide it in (the hook goes under the T101 base plate), and fit 2 × M3 × 12 down its sleeves. Right half first: the left half's lap goes under it.
5. **Battery hatch, B106, last.**
   - Put the 3 cells into the holders under the hatch.
   - Plug its XT30 lead.
   - Lower the hatch into the opening on the hood top, where the magnets hold it.

## Service

- **Detach a track:** park the upper at 0° with the arm in the original reference pose, then independently support the chassis/upper and the affected track. Remove the belly cover for access. Disconnect and secure the affected motor wiring so it cannot restrain removal. Remove that track's chain, rear sprocket/hub and journal plug, then all four joint screws, both sets of washers and nuts. Lower only that prepared track **at least 80 mm vertically relative to the supported chassis**, maintaining its alignment until the support ends are clear; then slide it outward. Do not start with a sideways pull: the motor and housing clash with X101 along that route. The other track and parked upper may remain fitted.
- **Mounting nuts:** the nuts are external and turn freely unless held with a tool. Remove the chain for access. The rear outer nut also requires removing the rear sprocket. Road/support rollers and the front idler can remain fitted.
- **Housing, motor and support rollers:** detach the track before service. Follow J9's sequence rather than removing structural material for tool access.
- **Road rollers, idler and drive:** follow J9's retained service instructions and the current clearance report.
- **Slewing bearing:** remove the upper assembly and belly cover, then reach the outer-ring nuts from below.
- **Body:** see [BODY.md → Service](BODY.md#service): the battery hatch lifts off by hand, each half comes off with 2 screws, then the counterweight.

Nominal assembly, tool and motion checks are recorded in `arc_seat_mount_validation.json` (chassis and track joints), `turntable_validation.json` and `body_validation.json`. They do not establish real-tool ergonomics, printed fit or strength.

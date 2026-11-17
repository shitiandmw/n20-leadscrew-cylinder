# J9 assembly

Build the track on a bench with the H-frame lying on its outer wall. The retained drive and spring assembly sequence comes from the earlier J9 checks; revision F mounting geometry is checked separately in [X1/arc_seat_mount_validation.json](../X1/arc_seat_mount_validation.json).

For X1, install the motor and all road/support rollers with their axles first (steps 2–3). Fit the housing from step 8 while detached. The front tensioner/idler may also be fitted. **Pause before the rear sprocket and chain:** hold both tracks at their final spacing and lower bare X101 vertically into the seats, then tighten the joints using step 9 and X1/ASSEMBLY.md, then install the rear sprocket/hub, journal plug and chain. This preserves roller-axle access and leaves room to hold the external mounting nuts.

## 1. Prepare the prints

1. **Heat-set inserts.**
   - Four M3 inserts into the tops of the four housing standoffs on the inner wall (housing screws). The bores are 7 mm deep: press each insert in until it is flush with the standoff top, no deeper.
   - Clean the shallow chassis-support seats and plain mounting holes. Prepare four M4 nuts (AF7 × 3.2 mm) and eight Ø9/Ø4.4 × 0.8 mm washers per track for the X1 connection. The nuts remain external and must be held with a socket; no chassis heat-set inserts or captive nut pockets are fitted.
   - Clear the Ø3.2 lock-pin hole in the outer wall (in the yoke groove, 4 mm ahead of the groove's rear end) and the two Ø3.2 × 8 holes in the ends of the J908 crossbar with a 3.2 mm drill, by hand.
2. **6800ZZ.** Press it into the outer-wall seat from the outside until it sits on the 1 mm lip. Its face ends flush with the wall.
3. **Rollers.** Press two 624ZZ into each of the seven rollers, flush with the roller faces.
4. **Idler.** Fit a 608 from each face of the idler wheel.
   - Each bearing slides in by hand through the Ø22.6 bore.
   - Press the last 7.5 mm with a Ø20–21 mm tube or socket on the outer ring, not on the shield, until the bearing stops against the central web, 13 mm below the face.
   - The web's underside prints as a bridge: trim any sag before fitting the bearing on the bed side.
5. **Sprocket and coupling.**
   1. Put the flange coupling's flange into the Ø32.4 recess in the sprocket's inner face, boss outward. The sprocket's centre pad goes into the coupling bore.
   2. Line up every other coupling hole with the sprocket's three counterbores.
   3. Fit three **M3 × 20** from the sprocket's outer face into the coupling's threads. Their heads end flush.
   4. Start the coupling's set screw. Leave it backed out clear of the bore.

## 2. Motor (before the sprocket)

1. Seat the JGY-370 in the motor recess on the outer side of the thickened inner main plate. The recess retains the original gearbox face at local Y−30. Its four screw bosses and central boss enter the retained counterbores, and the shaft passes through the wall.
2. Working inside the open H, from the rear, drive four **M3 × 6** socket screws into the gearbox with a 2.5 mm L-key.
   - The CAD check reserves a straight 30 mm path for the key's short arm.
   - The screws cannot be reached once the sprocket is in.
   - Check the real hole depth first. 3 mm engagement is assumed.

## 3. Rollers

1. Put each roller between the walls: road rollers from below, support rollers from above.
2. Push an **M4 × 70** in from the inboard side, seating its head in the retained recess, then through the inner wall, both bearings and the outer wall. The recess keeps the original bolt position despite the thicker main plate.
3. Fit a **nyloc nut** outboard and turn it until it is just snug.
   - The rollers float about 0.3 mm between small wall bosses that touch only the bearing inner rings.
   - Do not clamp the walls together.

## 4. Sprocket

1. Hold the sprocket and coupling between the walls about **10 mm outboard** of their final position, so the coupling clears the shaft tip.
2. Bring them in from the **rear** of the frame.
3. Turn the sprocket so the coupling's set screw faces the shaft's D-flat, with the flat on top (as in the CAD pose). The worm gearbox does not turn by hand: if the flat is not on top, run the motor briefly until it is.
4. Slide it inboard onto the shaft until the sprocket's centre pad meets the shaft end. The coupling boss then stands 1 mm clear of the wall.
5. With a **1.5 mm hex key** straight down between the walls, 6 mm from the wall face, tighten the set screw firmly onto the flat.
   - The CAD check reserves this vertical path.
   - It closes once the track is on.
6. Use medium (blue) thread-locker on the set screw, and mark it with a paint line so any slip shows. It cannot be reached once the chain is on.

## 5. Journal plug

1. From outside, push the **J903 plug** through the 6800ZZ into the socket in the sprocket's outer face.
2. Insert the **M3 × 50** through the plug and the sprocket into the motor shaft's tapped end (engagement about 5.6 mm).
3. Tighten moderately: it clamps printed parts.

## 6. Tensioner

1. Clean the Ø16.4 main-web guide bore and dry-fit the revised J908's Ø15.6 piston. It must slide freely through the full 4.2 mm recoil stroke. Use the revised frame and piston yoke together.
   - Insert the spring from the front into the guide hole, onto the pilot at the recessed floor (X28). The spring is retained around its outside by the guide wall.
2. Make up the idler sub-assembly away from the frame:
   1. Place the idler (with its 608s) between the U-yoke arms, with one **J907 spacer** on each side.
   2. Push the **Ø8 × 55 rod** through arm, spacer, bearings, spacer and arm. It must slide into the 608 bores by hand (h6 or g6 rod). The rod ends stand 0.5 mm proud of the arms.
3. Slide the yoke arms into the wall grooves **from the front**.
   - The pin ends run in the deeper tracks in the groove floors.
   - Push until the spring sits on the yoke pilot and the piston enters the guide hole. The guide mouth remains 0.8 mm clear of the crossbar at the recoil stop.
4. Without the track, the spring pushes the yoke forward to about 12 mm ahead of its running position. The arms stay in the grooves.

## 7. Track

The chain goes on in one piece. Step 9 of [install_animation.html](install_animation.html) shows each move, and [TRACK_KIT.md](TRACK_KIT.md) lists them.

Each joint is an **M3 × 60 partly threaded screw** (head outboard), a **Ø6 × Ø3.2 × 18 sleeve** between the inner ears, and an **M3 nyloc nut** inboard. Head and nut sit on the seat bosses of the same link, so the screw cannot slide sideways. The nut is not tightened: the joint must stay free.

1. Join the 34 links into one straight strip on the bench, grousers down. For each joint:
   - Lay the next link down just ahead of the strip and push it back until its outer plates straddle the inner ears of the last link. The rounded plate ends turn in the hollowed ones, so a link only goes on along the strip.
   - Drop a **sleeve** in between those inner ears from above. At Ø6 it cannot pass the Ø3.2 holes, so it always goes in before its screw.
   - Push an **M3 × 60 screw** in from the outboard side: boss, plate, ear, sleeve, ear, plate, boss. Its head stops on the outboard seat.
   - Run a **nyloc nut** on from the inboard side with a 5.5 mm nut driver until it touches its seat, then back it off 1/6 turn (one flat). The link must swing under its own weight.
2. Leave the last joint open. Drop its sleeve between the free inner ears at the far end of the strip. Push a **Ø3 × 24 dummy pin** (any smooth Ø2.5–3 rod) through ears and sleeve until it sits inside both ears. On the top run those ears open downward, out of reach, and the dummy pin keeps the sleeve in.
3. Lay the strip under the lifted track and set the track on it. Wrap the rear end round the sprocket and forward over the support rollers.
4. Push the idler back to its **recoil stop** (4.2 mm travel; the yoke meets the groove ends). The Ø3.2 hole in the outer wall now lines up with the hole in the end of the yoke crossbar: push a spare **M3 × 60 screw** in from outboard, about 11 mm deep. It holds the idler back, so both hands are free.
5. Wrap the front end round the idler and over the top. Hold it in a low arch so that it lands a few millimetres short of the rear end. Press the arch flat: the front end slides along the run until its ears are between the rear end's outer plates.
6. Push the last screw in from outboard; it pushes the dummy pin out on the inboard side. Fit the last nut the same way as the others.
7. Pull the lock screw out. The spring moves the idler forward and sets the tension at about 77 N.

Check, by hand before power: every joint swings freely, no screw head or nut touches a roller flange or the idler flange, and the track turns a full round without a tight spot.

## 8. Housing

1. Thread the two motor leads through the cable port in the housing's nose, from the outside in. The port is Ø5.5: it takes two wires, not a plug.
2. Solder the leads to the motor terminals.
3. With the module detached from X1, slide the housing toward the inner wall along local Y and over the motor, pulling the slack out through the port.
   - The skirt openings expose the shallow main-plate receiving seats and clear the two X1 arms.
   - The pod's open side meets the rim on the inner wall, so the motor is closed in.
4. Fasten it with four **M3 × 8** button heads into the standoff inserts.

## 9. Chassis

Use the revision F X101, J901 and J909 together. Each track receives the flat ends of two straight X101 arms in 1.5 mm deep seats at X ±63.5. Four horizontal M4 × 25 screws per track, one in each side slot of every arm, clamp the parts through plain holes. Put a washer beneath every head and external nut. Follow [X1's assembly guide](../X1/ASSEMBLY.md): fit the road/support rollers and their axle bolts, motor and housing first. Secure both tracks at their final spacing and lower bare X101 vertically 80 mm into the open-top seats. Do not fit the tracks sideways into the frame: that route clashes with the motor and housing. Leave the rear sprocket/hub, journal plug, chain and joint fasteners off until the frame is seated; then install and tighten the joint fasteners. Slide each screw sideways into its slot and push it through; a compact 7 mm nut-holding tool holds each nut while a short-leg 3 mm L-key, handle out of the slot, turns the screw. Fit the rear sprocket/hub and chain afterward.

Other chassis adapters must match these current mating faces and the spring/motor envelopes. Earlier saddle, projecting-pad and flat-face joint patterns are obsolete.

## Service

- **X1 mounting joints:** follow X1/ASSEMBLY.md. Park the upper at 0° with the arm in its original reference pose, independently support the chassis/upper and affected track, remove the belly cover for access, and disconnect/secure the affected motor wiring. Remove the affected chain, rear sprocket/hub and journal plug for access to the external nuts, then all four joint screws, both sets of washers and nuts. Lower the prepared track **at least 80 mm vertically relative to the chassis before sliding it outward**. Road/support rollers and the front idler can remain fitted, as can the other track and parked upper. An immediate sideways pull clashes with the motor and housing.

- **Roller bolts on the detached module:** reachable and removable through the Ø8 housing-skirt holes, with nyloc nuts outboard. When fitted to X1, detach the module before servicing the support rollers; its deeper X-legs block their straight tool and withdrawal routes.
- **Motor:** detach the module from X1 first, then remove the four housing screws and slide the housing away from the inner wall along local Y. The leads stay threaded through the port.
- **Plug screw:** reachable from the outboard side with the track on.
- **Taking the track off:** push the idler back to its recoil stop and fit the lock screw (step 7.4). Take the nut and the screw out of any joint on the top run, then pull the lock screw.
- **Removing the idler:** take the track off, then the yoke, idler and spring slide out of the front of the frame.
- **Removing the sprocket:**
  1. Take the track off.
  2. Remove the plug screw and the plug.
  3. Loosen the coupling's set screw from above.
  4. Slide the sprocket and coupling outboard about 10 mm, then out to the rear.
- **Coupling set screw:** recheck it after the first runs and after any stall.

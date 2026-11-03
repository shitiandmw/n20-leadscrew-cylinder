# J9 assembly

Every step below was checked in CAD (`validation.json → assembly_and_access`). Work on a bench with the H-frame lying on its outer wall.

## 1. Prepare the prints

1. **Heat-set inserts.**
   - Four M3 inserts into the tops of the four housing standoffs on the inner wall (housing screws).
   - Three M4 inserts into the ends of the chassis bosses.
2. **6800ZZ.** Press it into the outer-wall seat from the outside until it sits on the 1 mm lip. Its face ends flush with the wall.
3. **Rollers.** Press two 624ZZ into each of the seven rollers, flush with the roller faces.
4. **Idler.** Press two 608 into the idler wheel (as J8).
5. **Sprocket and hub.**
   1. Put the Pololu hub's flange into the recess in the sprocket's inner face, boss outward.
   2. Line up every other hub hole with the sprocket's three counterbores.
   3. Fit three **M3 × 25** from the sprocket's outer face into the hub's threads. Their heads end flush.
   4. Start both set screws in the hub: the long one in the flange, the short one in the boss. Leave them backed out clear of the bore.

## 2. Motor (before the sprocket)

1. Set the JGY-370 against the outer face of the inner wall. Its four screw bosses and the central boss drop into the counterbores, and the shaft passes through the wall.
2. Working inside the open H, from the rear, drive four **M3 × 6** socket screws into the gearbox with a 2.5 mm L-key.
   - The CAD check reserves a straight 30 mm path for the key's short arm.
   - The screws cannot be reached once the sprocket is in.
   - Check the real hole depth first. 3 mm engagement is assumed.

## 3. Rollers

1. Put each roller between the walls: road rollers from below, support rollers from above.
2. Push an **M4 × 70** in from the inboard side, through the inner wall, both bearings and the outer wall.
3. Fit a **nyloc nut** outboard and turn it until it is just snug.
   - The rollers float about 0.3 mm between small wall bosses that touch only the bearing inner rings.
   - Do not clamp the walls together.

## 4. Sprocket

1. Hold the sprocket and hub between the walls about **10 mm outboard** of their final position, so the hub clears the shaft tip.
2. Bring them in from the **rear** of the frame.
3. Turn the sprocket so the hub's set screws face the shaft's D-flat (flat on top in the CAD pose).
4. Slide it inboard onto the shaft until the sprocket's centre pad meets the shaft end. The hub boss then stands 1 mm clear of the wall.
5. With a **1.5 mm hex key** straight down between the walls, tighten both set screws firmly onto the flat.
   - The CAD check reserves this vertical path.
   - It closes once the track is on.
6. Mark the set screws with a paint line so any slip shows.

## 5. Journal plug

1. From outside, push the **J903 plug** through the 6800ZZ into the socket in the sprocket's outer face.
2. Insert the **M3 × 50** through the plug and the sprocket into the motor shaft's tapped end (engagement about 5.6 mm).
3. Tighten moderately: it clamps printed parts.

## 6. Tensioner

1. Put the spring on the pilot at the front of the web.
2. Make up the idler sub-assembly away from the frame:
   1. Place the idler (with its 608s) between the U-yoke arms, with one **J907 spacer** on each side.
   2. Push the **Ø8 × 55 pin** through arm, spacer, bearings, spacer and arm. The pin ends stand 0.5 mm proud of the arms.
3. Slide the yoke arms into the wall grooves **from the front**.
   - The pin ends run in the deeper tracks in the groove floors.
   - Push until the spring sits on the yoke pilot.
4. Without the track, the spring pushes the yoke forward to about 12 mm ahead of its running position. The arms stay in the grooves.

## 7. Track

1. Assemble the 34 links as for R4/J8: pins, bushings, clips.
2. Wrap the chain around the sprocket, the rollers and the idler.
3. Push the idler back toward its **recoil stop** (4.2 mm travel; the yoke meets the groove ends) to gain slack.
4. Join the last pin, fit its clips, and release. The spring sets the tension at about 77 N.

## 8. Housing

1. Thread the two motor leads through the cable port in the housing's nose, from the outside in. The port is Ø5.5: it takes two wires, not a plug.
2. Solder the leads to the motor terminals.
3. Lower the housing straight down over the motor, pulling the slack out through the port.
   - The chassis bosses pass through the skirt.
   - The pod's open side meets the rim on the inner wall, so the motor is closed in.
4. Fasten it with four **M3 × 8** button heads into the standoff inserts.

## 9. Chassis

Fasten the module with three M4 screws into the boss inserts: X −60, 0 and 60; Z 68; boss faces at Y −46.
- **On the X1 chassis:** three M4 × 12 go through the X-frame rail from the inboard side. See [X1's assembly guide](../X1/ASSEMBLY.md).
- **On any other chassis:** the adapter must match the bosses and have a cut-out for the motor pod, which stands out to Y −62.5.

## Service

- **Roller bolts:** reachable and removable through the Ø8 holes in the housing skirt. The nyloc nuts are on the open outboard side.
- **Motor:** remove the four housing screws and lift the housing off; the leads stay threaded through the port.
- **Plug screw:** reachable from the outboard side with the track on.
- **Removing the idler:** take the track off, then the yoke, idler and spring slide out of the front of the frame.
- **Removing the sprocket:**
  1. Take the track off.
  2. Remove the plug screw and the plug.
  3. Loosen both hub set screws from above.
  4. Slide the sprocket and hub outboard about 10 mm, then out to the rear.
- **Hub set screws:** recheck them after the first runs and after any stall.

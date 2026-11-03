# X1 assembly

Every step below was checked in CAD (`validation.json → assembly_paths` and `tool_access`).

## 1. Build the two tracks

1. **Left track.** Build it exactly as [J9's assembly guide](../J9/ASSEMBLY.md) describes, with J9's `J901_H_frame` and `J909_housing`.
2. **Right track.** Build it the same way, as a mirror image, with `J901_H_frame_right` and `J909_housing_right`.
   - Use the same motor, turned 180° about the axis of its can. The four gearbox screw holes are symmetric about the axle height, so they line up with the mirrored seat.
   - Every other part is the same print as on the left track.
3. **Motor leads.** On both tracks, thread the leads out through the pod's nose port (J9 step 8). Leave each lead about 180 mm long beyond the port, plus slack, so it can reach the turntable face.

## 2. Prepare the X-frame

1. **M4 inserts.** Press eight M4 heat-set inserts into the seat from the top face. They must end flush with the seat or just below it; a proud insert would tilt the ring.
2. **M3 inserts.** Press four M3 heat-set inserts into the cover bosses inside the carbody, from below.
3. **Seat check.** Lay a straight edge across the seat and check that it is flat.

## 3. Fit the tracks

1. Hold the track beside the frame, with its motor pod at the rear. Feed its motor leads into the carbody through the Ø10 hole in the carbody wall.
2. Slide the track straight in sideways until its three chassis bosses meet the rail.
3. From inside the rail, fit three **M4 × 12** socket screws into the boss inserts with a 3 mm hex key. The CAD check reserves 35 mm in front of each screw head for the key.
4. Repeat for the other track.

## 4. Wiring

1. Inside the carbody, take all four leads up through the Ø25 passage at the swing centre.
2. The right motor is turned over, so it must run the opposite way to the left one for the same direction of travel. Swap its leads, or set it as reversed in the motor driver.
3. The J9 open items on current limiting and pod heat still apply ([J9 README](../J9/README.md#open-items-check-before-relying-on-them), items 6 and 7).

## 5. Belly cover

Fit `X102_belly_cover` from below with four **M3 × 8** countersunk screws (2 mm hex key).

## 6. Slewing ring (when the turntable is built)

1. Lower the RU66 onto the seat with the outer ring's counterbores facing up.
2. Fit eight **M4 × 16** socket screws through the outer ring into the seat inserts (3 mm hex key). Tighten them evenly, working across the circle.
3. The turntable then bolts to the inner ring: 8 × M4 on a Ø45 circle, tapped through the ring.
   - Its flange must stay within Ø59.
   - Its screw tips may go at most 2 mm below the ring.

## Service

See [README → Service](README.md#service). In short: the track screws and the J9 housing screws are reachable with everything assembled. To pull the support-roller bolts or take the housing off, first take that track off the chassis.

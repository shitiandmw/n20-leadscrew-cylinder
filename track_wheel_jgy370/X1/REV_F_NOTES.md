# Revision F — straight arms seated in the track main beam

Each X101 arm runs straight at its full 28 mm width from the root bend into the track main plate, where its flat end sits in a plain 1.5 mm deep rectangular seat. The deck and the arched underside are each one smooth curve. Two screws, one on each side of the arm's 9 mm centre web, clamp the joint through plain holes; their heads and washers sit in side slots under the closed deck. There are no T-blocks, stems or shelves. Mounting screw-head counterbores and rear nut pockets are absent. The accepted enclosed spring guide and J908 yoke are retained.

## Interface

| Feature | Revision F nominal geometry |
|---|---|
| Station centres | X −63.5 and +63.5 on each track |
| Arm | 28 mm wide, straight from vehicle Y ±96 to the seat; ends flat at vehicle Y ±137.5 |
| Arm deck | One cubic curve from Z85 at the carbody (vehicle Y ±48) down to Z74 at the plate face |
| Arm underside | One arch from the carbody rim (Z34) up to its crown (Z57.5 at vehicle Y ±108) over the motor pod, then the foot curve down to Z53 at the plate face |
| Arm end in the seat | 28 × 21 mm, Z53–74 |
| Head slots | Both sides of a 9 mm centre web; vehicle Y ±97 to ±127, Z62.75–72.75, round inboard end, open to the side |
| Clamped stock | 10.5 mm between the washer face (local Y−43) and the seat face |
| Receiving seat | Plain rectangle, 28.3 mm wide (0.15 mm side clearance), Z53 up, open at the top; 1.5 mm deep from the local Y−34 main-plate face to Y−32.5 |
| Mating plane | Vehicle Y ±137.5; left track local Y−32.5 |
| Main plate | Original inner surface remains at local Y−24; 8.5 mm remains behind the recessed contact face |
| Housing window | Follows the arm outline with about 0.5 mm clearance (0.41 mm measured minimum), open at the top; a 0.9 mm deep lane in the rear pod shell beside each slot lets the screw and washer slide in |
| Bolt axes | Front X54 and X73; mirrored rear axes; Z67.75 |
| Screws | Eight M4 × 25 ISO 4762; Ø7 × 4 mm heads; 3 mm key |
| Washers | Sixteen Ø9 / Ø4.4 × 0.8 mm; one beneath every head and nut |
| Nuts | Eight external M4, AF7 × 3.2 mm, at local Y−23.2 to −20 |
| Screw tip | Local Y−18.8; 1.2 mm nominal projection past the nut |
| Housing attachment axes | Retained from E: (X,Z) = (−103,71), (−15,33), (85,56), (85,32) |
| Accepted spring | Ø16.4 bore, Ø21.2 outside, Ø15.6 piston, 8 mm recessed seat |
| Spring setting | 25.8 mm fitted length and 4.2 mm recoil |

The arm end bears on the seat floor over 28 × 21 mm less the two holes, 556.2 mm² per joint. Its underside rests on the 1.5 mm seat ledge at Z53. At the rear joints the retained motor-can relief interrupts part of that ledge: about 36.1 mm² of nominal ledge contact per rear joint versus 42 mm² per front joint. The recess is part of the structural main plate. The cosmetic housing is relieved around the arm and carries no chassis load. Mechanism recesses retain the motor, roller and yoke positions. These areas describe the seating geometry, not a load rating; the current joint report gives the measured contact.

## Assembly implications

Use matching revision F X101, both J901 frames and both J909 housings. Fit the road and support rollers with their axles, the motor and housing first. Keep both tracks aligned at their final spacing and lower the bare X101 frame vertically through the checked 80 mm approach into their open-top seats. Sideways track fitting clashes with the motor can and housing. Leave the rear sprocket/hub, journal plug, chain and joint fasteners off until the frame is seated; fit and tighten the joint fasteners next. Slide each screw, with its washer, sideways into its head slot and push it through. Hold the nut with a compact 7 mm nut-holding tool and turn the screw with a 3 mm L-key whose handle comes out of the side slot. The complete nut-holding tool, including its body, shaft, drive junction and handle, must fit within the checked Ø11.2 mm envelope. Install the rear sprocket and chain afterward. Both washers and the nut sit outside the printed material; there are no captive mounting nuts.

Support the chassis independently while fitting or removing a track. For removal, park the upper at 0° with the arm in its original reference pose, support the affected track, disconnect/secure its wiring and remove its chain, rear sprocket/hub, journal plug and all joint hardware. Lower that prepared track at least 80 mm before sliding it outward; the other track and parked upper may remain fitted. The complete access and removal sequence is in ASSEMBLY.md. Seat the arm ends in their recesses without forcing the printed parts. Tighten the paired screws gradually and verify actual thread engagement, washer seating, wheel clearance and full spring recoil before operation. Follow ASSEMBLY.md for the complete order and tool route.

## Evidence and limits

`arc_seat_mount_validation.json` records the nominal joint checks and source/export hashes. `../J9/validation.json` is a fresh full run of every track trial on the delivered parts. `revf_part_exports.json` confirms the changed STEP/STL files match the current source and records their print bounds. `revf_refresh_validation.json` confirms the assemblies and viewer scenes hold the current parts. Browser reports bind the offline viewers and screenshots to their current inputs. All of these are computed on revision F itself; nothing is inherited from earlier designs.

`revf_leg_sections.json` measures the arm cross-section at 19 planes, from the root bend through the head slots to the seat. Through the slots the section is a closed deck, a 9 mm web and a full-width base. These are geometric section properties, not a strength validation or load rating.

Nominal fit and seating area do not establish printed stiffness, bolt preload retention, creep, fatigue life, tightening torque or payload capacity.

Open **Track connections** and **X-frame only** in the offline viewer. `X1_arc_mount_detail.pdf` shows sections of the delivered CAD. Rebuild steps are in README.md, "Verification and rebuilding".

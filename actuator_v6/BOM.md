# V6 bill of materials

Quantities are for one actuator. Reference designators match `electronics/schematic.pdf` and the board files; part names match the STEP files. The three lengths share every part except the body, the rod, the board and the length the motor's leadscrew is cut to.

The 60 mm excavator arm uses four V6-U60, so multiply the V6-U60 quantities by four and order a spare board or two.

## Printed parts

PETG, unfilled. Masses are for solid parts; the print settings below use less material.

| File | Qty | V6-S | V6-U60 | V6-L | Print setup |
|---|---:|---:|---:|---:|---|
| `01_body` | 1 | 12.2 g | 15.0 g | 18.5 g | Front end down (the bore and board-slot mouths are chamfered for the first layer), 5 mm brim, 0.2 mm layers, 3 walls, 25 % gyroid, no supports. The motor wall bridges the carrier bore, so the motor seat is a top surface; the M1.6 countersinks (45° cones) and the board rest are on the bridge's underside. The end of the motor-side wall stands 1.6 mm above the rear face; 0.12 mm layers for the last 2 mm print the 45° bevel of its notch in 5 layers instead of 3. Check in the slicer that the 1 mm partition prints solid. |
| `02_front_cap` | 1 | 1.6 g | same | same | Outer face down, 0.16 mm, 4 walls, 40 % gyroid |
| `03_rear_cap` | 1 | 1.7 g | same | same | Flat front face down (clevis up), 0.16 mm, 4 walls, 60 % gyroid. The pocket for the end of the body's wall is bridged; the tooth's tip and the pocket's ends have 0.2 mm chamfers for the first layer. |
| `04_rod` (rod and nut carrier) | 1 | 3.8 g | 4.7 g | 5.7 g | Carrier down, 0.16 mm, 100 % infill, 3 mm brim. Slow the last 20 mm of the taller U60 and L rods. |
| `05_rod_eye` | 1 | 1.1 g | same | same | Socket opening down, 0.16 mm, 100 % infill |
| `06_cable_clamp` | 1 | 0.2 g | same | same | Flat back down (groove up), 0.16 mm, 100 % infill |
| `fit_samples/08_fit_body_wall` | 1 | 2.7 g | – | – | Test print, front end down: motor bay, countersinks, wall, partition, board slot, key rib |
| `fit_samples/09_fit_carrier` | 1 | 1.2 g | – | – | Test print: carrier, nut slot, magnet pocket; slides in sample 08 one way round only |
| `fit_samples/10_fit_insert_rear` | 1 | 0.7 g | – | – | Test print, front end down: the last 5 mm of the rear end with its two insert holes and the end of the motor-side wall. Try the rear cap on it: set it on 0.8 mm toward the board side and slide it back; the tooth must drop into the notch. |
| `fit_samples/11_fit_insert_front` | 1 | 0.7 g | – | – | Test print, front end down: the last 5 mm of the front end with its two insert holes (0.7 mm walls) and the bore and slot lead-ins |

STL files are in `stl/V6-S/`, `stl/V6-U60/` and `stl/V6-L/`, already oriented for printing; the fit samples serve every length. Matching STEP files are in `step/`.

## Bought mechanical parts

| Ref | Part | Qty | Specification |
|---|---|---:|---|
| M1 | N20 gearmotor with integrated leadscrew | 1 | **12 V, 1:50, 800 rpm** without load (0.08 A). M4 × 0.7 leadscrew straight from the gearbox, sold 100 mm long: cut it to **55 mm for V6-S or 75 mm for V6-U60**, measured from the gearbox face to the tip, and deburr the cut end; V6-L uses it uncut. Otherwise unmodified. No seller drawing of this version was found: check the gearbox face (Ø4 bushing, M1.6 holes 9 mm apart) before printing. |
| | Hex nut M4, thin, brass | 1 | ISO 4035, 7 mm across flats × 2.2 mm. Slides into the carrier's hex slot. |
| | Magnet | 1 | NdFeB **N35 block, 3 × 2 × 2 mm, magnetised through 2 mm**, so its poles are two 3 × 2 mm faces. It presses into the carrier pocket with the poles facing along the travel; either pole may face forward. |
| | Countersunk screw M1.6 × 4 | 2 | DIN 965, cross recess (PH0). Motor to the body wall. |
| | Heat-set insert M1, brass | 4 | M1 × 0.25 thread, **1.8 mm long, 2.0 mm across the knurl** (sold as M1 × 1.8 × 2). Pressed with a soldering iron into the Ø1.7 mm holes in the body's end faces, two at each end. |
| | Pan-head screw M1 × 8 | 4 | A2-70 stainless, cross recess PH000. Two through the front cap, two through the cable clamp and the rear cap, into the inserts. Each runs through its whole insert. |
| | Pan-head screw M2 × 10 | 1 | Rod eye cross screw (clearance on one side, 1.7 mm pilot on the other). |
| | Clevis pins Ø3 mm | 2 | Length to suit your brackets; both eyes are 6 mm thick. The 60 mm arm uses its own steel shafts instead. |
| W1–W4 | Wire, 28 AWG PTFE, 0.8 mm OD | 4 | W1 red (A), W2 black (B), W3 orange (motor +), W4 purple (motor −). Cut lengths are in `wire_lengths_<version>.csv`; they are the same for every length. W1 and W2: 52 mm plus your lead to the driver; their knot sits 31 mm from the pad. |
| | Sleeve, silicone or PVC tube, 3 mm OD × 2 mm bore | your lead length | Over W1 and W2 from the cable clamp to the driver. The clamp grips 3.0 ± 0.3 mm. |

The M1 heads sit in Ø2.6 mm pockets in the front cap and the clamp plate, 0.3 mm below the face and inside the outline.

## End-stop board (PCBA)

- **Board:** 2 layers, FR4, 0.8 mm thick, all parts on the top side.
- **Size:** 56.4 × 8 mm for V6-S, 76.4 × 8 mm for V6-U60, 101.4 × 8 mm for V6-L (rev 6.2).
- **Hall switches:** both are on every board, U1 at the wire end and U2 at the front end.
- **Files:** in `electronics/pcb/V6-S/`, `V6-U60/` and `V6-L/`: Gerbers and drill file, `*_BOM_JLCPCB.csv`, `*_CPL_JLCPCB.csv`, and a KiCad board file.
- **Upload:** `electronics/pcb/actuator_v6_S_gerbers.zip`, `actuator_v6_U60_gerbers.zip` and `actuator_v6_L_gerbers.zip` hold the Gerbers and drill file, ready to upload to the board maker.

| Ref | Qty | Value | Package | Manufacturer part | LCSC |
|---|---:|---|---|---|---|
| U1, U2 | 2 | Hall switch, omnipolar, open drain | SOT-23 | TI DRV5033AJQDBZR | C85151 |
| Q1, Q2 | 2 | N-MOSFET 60 V, ±16 V gate | SOT-23 | Infineon IRLML0060TRPBF | C67274 |
| D1, D2 | 2 | 1N4148WS | SOD-323 | JSCJ 1N4148WS | C2128 |
| D4, D5 | 2 | Schottky B5819WS | SOD-323 | JSCJ B5819WS | C22624 |
| D3 | 1 | TVS SMF15CA, bidirectional, 15 V stand-off | SOD-123F | MDD SMF15CA | C123803 |
| F1 | 1 | PPTC 0.35 A hold, 0.75 A trip, 16 V | 1206 | Bourns MF-NSMF035X-2 | C208468 |
| C1, C2 | 2 | 1 µF 50 V X5R | 0603 | Samsung CL10A105KB8NNNC | C15849 |
| C3 | 1 | 100 nF 50 V X7R | 0603 | Yageo CC0603KRX7R9BB104 | C14663 |
| R1, R2 | 2 | 1 MΩ 1 % | 0603 | UNI-ROYAL 0603WAF1004T5E | C22935 |
| R3, R4 | 2 | 220 Ω 1 % | 0603 | UNI-ROYAL 0603WAF2200T5E | C22962 |

17 parts, 10 part numbers. D4 and D5 are optional. Without them the MOSFET body diodes carry the reverse current, and the rod runs about 4 % slower (simulated).

### Ordering and cost

- **Panelize the board.** At 8 mm wide it is narrower than assembly lines usually accept, so order it panelized with break-off rails. Either use the manufacturer's panel service or add rails yourself.
- **Check part availability before ordering.** The DRV5033AJQDBZR had low stock at LCSC when this was designed. At JLCPCB, some of the ten parts may be "extended" parts, each with a one-time setup fee, so check before ordering.
- **Check the part rotations.** Confirm them in the manufacturer's placement preview, especially U1, U2, Q1, Q2 and the diodes.
- **Unit cost.** For small runs, the per-board fees (setup, stencil and extended-part fees) cost more than the parts, which are low-cost commodity items. Panelizing several boards per order spreads these fees.

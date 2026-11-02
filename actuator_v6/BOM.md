# V6 bill of materials

Quantities are for one actuator. Reference designators match `electronics/schematic.pdf` and the board files; part names match the STEP files. The three lengths share every part except the body, the rod, the leadscrew motor and the board.

The 60 mm excavator arm uses four V6-U60, so multiply the V6-U60 quantities by four and order a spare board or two.

## Printed parts

PETG, unfilled. Masses are for solid parts; the print settings below use less material.

| File | Qty | V6-S | V6-U60 | V6-L | Print setup |
|---|---:|---:|---:|---:|---|
| `01_body` | 1 | 10.2 g | 12.6 g | 15.5 g | Rear end down (flat face), 5 mm brim, 0.2 mm layers, 3 walls, 25 % gyroid, no supports. The motor wall bridges the motor bay, so its countersinks, the carrier stop and the board rest are top surfaces. Check in the slicer that the 1 mm partition prints solid. |
| `02_front_cap` | 1 | 1.3 g | same | same | Outer face down, 0.16 mm, 4 walls, 40 % gyroid |
| `03_rear_cap` | 1 | 1.6 g | same | same | Flat front face down (clevis up), 0.16 mm, 4 walls, 60 % gyroid |
| `04_rod` (rod and nut carrier) | 1 | 4.4 g | 5.3 g | 6.5 g | Carrier down, 0.16 mm, 100 % infill, 3 mm brim. Slow the last 20 mm of the taller U60 and L rods. |
| `05_rod_eye` | 1 | 1.1 g | same | same | Socket opening down, 0.16 mm, 100 % infill |
| `06_cable_clamp` | 1 | 0.2 g | same | same | Flat back down (groove up), 0.16 mm, 100 % infill |
| `fit_samples/08_fit_body_wall` | 1 | 2.3 g | – | – | Test print, rear end down: motor bay, countersinks, wall, partition, board slot, key rib |
| `fit_samples/09_fit_carrier` | 1 | 1.3 g | – | – | Test print: carrier, nut slot, magnet pocket; slides in sample 08 one way round only |

STL files are in `stl/V6-S/`, `stl/V6-U60/` and `stl/V6-L/`, already oriented for printing; the fit samples serve every length. Matching STEP files are in `step/`.

## Bought mechanical parts

| Ref | Part | Qty | Specification |
|---|---|---:|---|
| M1 | N20 gearmotor with integrated leadscrew | 1 | 6 V, 150 rpm. M3 × 0.5 leadscrew straight from the gearbox, **55 mm for V6-S, 75 mm for V6-U60 or 100 mm for V6-L**, measured from the gearbox face to the tip. Used unmodified. |
| | Hex nut M3, brass | 1 | 5.5 mm across flats × 2.4 mm. Slides into the carrier's hex slot. |
| | Magnet | 1 | NdFeB **N35, Ø3 × 2 mm, magnetised axially** (through the 2 mm). Press fit; either pole may face forward. |
| | Countersunk screw M1.6 × 4 | 2 | DIN 965, cross recess (PH0). Motor to the body wall. |
| | Pan-head screw M2 × 8 | 2 | ISO 7045 or similar. Front cap; cuts its own thread in the 1.6 mm pilot holes. |
| | Pan-head screw M2 × 10 | 2 | Through the cable clamp and the rear cap into the same pilot holes at the rear end (5.8 mm of thread). |
| | Pan-head screw M2 × 10 | 1 | Rod eye cross screw (clearance on one side, 1.7 mm pilot on the other). |
| | Clevis pins Ø3 mm | 2 | Length to suit your brackets; both eyes are 6 mm thick. The 60 mm arm uses its own steel shafts instead. |
| W1–W4 | Wire, 28 AWG PTFE, 0.8 mm OD | 4 | W1 red (A), W2 black (B), W3 orange (motor +), W4 purple (motor −). Cut lengths are in `wire_lengths_<version>.csv`; they are the same for every length. W1 and W2: 52 mm plus your lead to the driver; their knot sits 31 mm from the pad. |
| | Sleeve, silicone or PVC tube, 3 mm OD × 2 mm bore | your lead length | Over W1 and W2 from the cable clamp to the driver. The clamp grips 3.0 ± 0.3 mm. |

The M2 pan heads stand about 0.3 mm proud of the body's side faces at the corners, where the 4 mm counterbores break through the edge of the front cap and the clamp plate. This is cosmetic.

## End-stop board (PCBA)

- **Board:** 2 layers, FR4, 0.8 mm thick, all parts on the top side.
- **Size:** 56.6 × 8 mm for V6-S, 76.6 × 8 mm for V6-U60, 101.6 × 8 mm for V6-L.
- **Hall switches:** both are on every board, U1 at the wire end and U2 at the front end.
- **Files:** in `electronics/pcb/V6-S/`, `V6-U60/` and `V6-L/`: Gerbers and drill file, `*_BOM_JLCPCB.csv`, `*_CPL_JLCPCB.csv`, and a KiCad board file.
- **Upload:** `electronics/pcb/actuator_v6_S_gerbers.zip`, `actuator_v6_U60_gerbers.zip` and `actuator_v6_L_gerbers.zip` hold the Gerbers and drill file, ready to upload to the board maker.

| Ref | Qty | Value | Package | Manufacturer part | LCSC |
|---|---:|---|---|---|---|
| U1, U2 | 2 | Hall switch, omnipolar, open drain | SOT-23 | TI DRV5033AJQDBZR | C85151 |
| Q1, Q2 | 2 | N-MOSFET 30 V | SOT-23 | AOS AO3400A | C20917 |
| D1, D2 | 2 | 1N4148WS | SOD-323 | JSCJ 1N4148WS | C2128 |
| D4, D5 | 2 | Schottky B5819WS | SOD-323 | JSCJ B5819WS | C22624 |
| D3 | 1 | TVS SMF7.0CA, bidirectional | SOD-123F | MDD SMF7.0CA | C123795 |
| F1 | 1 | PPTC 0.12 A hold | 1206 | Bourns MF-NSMF012-2 | C163517 |
| C1, C2 | 2 | 1 µF 50 V X5R | 0603 | Samsung CL10A105KB8NNNC | C15849 |
| C3 | 1 | 100 nF 50 V X7R | 0603 | Yageo CC0603KRX7R9BB104 | C14663 |
| R1, R2 | 2 | 1 MΩ 1 % | 0603 | UNI-ROYAL 0603WAF1004T5E | C22935 |

15 parts, 9 part numbers. D4 and D5 are optional. Without them the MOSFET body diodes carry the reverse current, and the rod runs about 10 % slower (simulated).

### Ordering and cost

- **Panelize the board.** At 8 mm wide it is narrower than assembly lines usually accept, so order it panelized with break-off rails. Either use the manufacturer's panel service or add rails yourself.
- **Check part availability before ordering.** The DRV5033AJQDBZR had low stock at LCSC when this was designed. At JLCPCB, some of the nine parts may be "extended" parts, each with a one-time setup fee, so check before ordering.
- **Check the part rotations.** Confirm them in the manufacturer's placement preview, especially U1, U2, Q1, Q2 and the diodes.
- **Unit cost.** For small runs, the per-board fees (setup, stencil and extended-part fees) cost more than the parts, which are low-cost commodity items. Panelizing several boards per order spreads these fees.

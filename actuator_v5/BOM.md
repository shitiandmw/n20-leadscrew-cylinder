# V5 bill of materials

Reference designators match `electronics/schematic.pdf`; part names match the STEP files.

## Actuator: printed parts

| STL | Qty | Material |
|---|---:|---|
| `01_barrel` | 1 | PETG, yellow |
| `02_rear_cap` | 1 | PETG, black |
| `03_head_collar` | 1 | PETG, black |
| `04_pushrod` (rod + nut carrier) | 1 | PETG, silver, 100 % infill |
| `05_rod_eye` | 1 | PETG, black, 100 % infill |
| `06_sensor_cover` | 1 | PETG, black |
| `07_TPU_cable_boot` | 1 | TPU 95A |
| `fit_samples/08–11` | 1 each | Test prints only, not part of the actuator |

## Actuator: bought parts

| Ref | Part | Qty | Specification |
|---|---|---:|---|
| M1 | N20 gearmotor with integrated leadscrew | 1 | Your part, unchanged: 10 × 12 mm, 9 mm gearbox, 15 mm can, Ø5 × 1.2 boss, M3 × 0.5 leadscrew straight from the gearbox. 40 mm screw assumed: measure yours and rebuild. 6 V winding assumed for the electronics. |
| | Hex nut M3, brass | 1 | DIN 934, 5.5 AF × 2.4 mm. Brass runs smoother on the steel screw than a steel nut does. |
| | Magnet | 1 | NdFeB **N35**, Ø4 × 2 mm, axially magnetised (through the 2 mm). Not N42, see `README.md`. |
| | Dowel pin | 1 | Ø2 mm steel, 13.8 mm long (a Ø2 × 14 pin with a filed end, or cut Ø2 silver steel). Press fit in the rod eye. |
| | Cap screw M2 × 10 | 2 | ISO 4762. Cuts its own thread in the barrel's Ø1.7 mm pilot holes. Holds the rear cap. |
| | Clevis pins | 2 | Ø3 mm steel, length to suit your brackets (eyes are 10.4 mm thick) |
| U1, U2 | Hall switch | 2 | TI **DRV5033AJQLPG** (TO-92 LPG, omnipolar, open drain). Not a PCB module, which will not fit the channel. |
| R1, R2 | Resistor 4.7 kΩ | 2 | 1206, 1 %. Soldered on the Hall leads (VCC to OUT). |
| C1, C2 | Capacitor 100 nF | 2 | 0603, X7R, ≥ 16 V. Soldered on the Hall leads (VCC to GND). |
| W1–W6 | Sensor wire | 6 | Modelled at OD 0.4 mm, e.g. AWG 32 thin-wall PTFE. Colours: red, black, green, red, black, blue. |
| W7, W8 | Motor wire | 2 | Modelled at OD 0.7 mm, e.g. AWG 28 PTFE. Colours: orange, purple. |
| | Cable jacket | 1 | Silicone tube or braided sleeve, ID 3.2 / OD 4.0 mm, length to the controller |
| | Consumables | | Heat-shrink 1–1.5 mm, 5-minute epoxy (magnet), neutral-cure silicone (sensors, cover strip), plastic glue for the head collar |

Wire lengths inside the actuator are in `wire_lengths.csv`. Add the run to the controller plus about 20 mm of calibration slack.

## Controller board (on the frame, not inside the actuator)

Example for a 6 V motor and 5 V logic; full circuit on sheet 2.

| Ref | Part | Qty | Specification |
|---|---|---:|---|
| U3 | SN74HC08N | 1 | Quad 2-input AND, DIP-14, 5 V. Two gates used. |
| U4 | DRV8833 carrier | 1 | Pololu #2130 (VIN 2.7–10.8 V; never 12 V) |
| R11 | Current-sense resistor | 1 | 0.25 Ω, 1206, ≥ 0.5 W, on U4's AISEN pads after cutting the GND break point. About 0.8 A chopping limit. |
| U5 | ACS712ELCTR-05B module | 1 | 5 A version only (185 mV/A), 5 V |
| U6 | Arduino Nano | 1 | ATmega328P, 5 V. Sketch in `electronics/actuator_protection/`. |
| R3, R4 | Resistor 47 kΩ | 2 | ALLOW_RET / ALLOW_EXT pull-downs |
| R5–R8 | Resistor 10 kΩ | 4 | Gate command inputs and DRV8833 AIN1/AIN2 pull-downs |
| R9 | Resistor 1 kΩ | 1 | ACS712 output series resistor |
| R10 | Resistor 100 kΩ | 1 | A0 pull-down (detects a missing sensor) |
| C3, C5, C7 | Capacitor 100 nF | 3 | Ceramic, ≥ 16 V. C3 at U3 pin 14, C5 at U4 VIN, C7 across the motor leads. |
| C4 | Capacitor 100 µF | 1 | Electrolytic, ≥ 16 V, at U4 VIN |
| C6 | Capacitor 1 µF | 1 | Ceramic, A0 filter |
| D1 | SMBJ8.0CA | 1 | Bidirectional TVS across the motor leads (6 V motor) |
| F1 | Fuse | 1 | 1 A slow-blow or PTC; size to your wiring |
| SW1–SW3 | Push button | 3 | Extend, retract, reset (to GND) |
| J1 | Terminal block | 1 | 8-way; pin n = wire Wn |
| J2, J3 | Terminal block | 2 | 2-way: motor supply 6 V, logic supply 5 V |

Some modules already carry decoupling or protection parts; check your board before doubling up. Current thresholds are commissioning values to be measured on the real motor. This list does not imply a rated force or life.

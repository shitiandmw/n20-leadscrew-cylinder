# V5 wiring, end stops and motor protection

The circuit is drawn in **`schematic.pdf`** (A3). Sheet 1 is inside the actuator, sheet 2 the controller board. PNG/SVG copies and the netlist (`netlist.csv`) are in this folder. Everything below matches those sheets; `source/build_schematic.py` checks the drawing against the netlist and the sketch's pin constants.

The reference design uses a **6 V motor supply and 5 V logic**. Your motor drawing gives no voltage, speed or current, so check them. The DRV8833 works from 2.7 to 10.8 V: do not connect it to 12 V.

## Eight-wire tail

Each Hall sensor has its own three wires, plus two motor wires, so eight leave the rear-cap port. The two +5 V and two GND wires are joined only at J1 on the controller; there are no splices inside the actuator.

| Wire | Colour | Actuator end | J1 pin | Controller net |
|---|---|---|---:|---|
| W1 | red | U1 (retract end) pin 1 VCC | 1 | +5V |
| W2 | black | U1 pin 2 GND | 2 | GND |
| W3 | green | U1 pin 3 OUT | 3 | ALLOW_RET → U3 pin 5, Nano D6, R3 47 kΩ to GND |
| W4 | red | U2 (extend end) pin 1 VCC | 4 | +5V |
| W5 | black | U2 pin 2 GND | 5 | GND |
| W6 | blue | U2 pin 3 OUT | 6 | ALLOW_EXT → U3 pin 2, Nano D5, R4 47 kΩ to GND |
| W7 | orange | M1 **(+)** terminal | 7 | MOTOR_A → U5 IP−; U5 IP+ ← U4 AOUT1 |
| W8 | purple | M1 **(−)** terminal | 8 | MOTOR_B ← U4 AOUT2 |

W7/W8 change polarity with direction, so neither is a ground. Fit the motor with its (+) terminal toward the cable port. The (+)/(−) marks are those on your drawing.

Modelled insulation: 0.4 mm for sensor wires and 0.7 mm for motor wires, in a 4.0 / 3.2 mm jacket. AWG does not fix insulation thickness, so measure what you buy. `wire_lengths.csv` gives each wire's modelled length inside the actuator (solder joint to 8 mm past the jacket entry).

## Hall end stops

- **U1, U2:** TI DRV5033AJQLPG. Omnipolar, open-drain output, LOW while a magnet of either pole is close. LPG pinout: 1 VCC, 2 GND, 3 OUT. Check against the datasheet drawing, not the 3D picture.
- **At the sensor:** a 4.7 kΩ pull-up (R1/R2, VCC to OUT) and 100 nF (C1/C2, VCC to GND), both soldered on the leads and sleeved.
- **At the controller:** a 47 kΩ pull-down on each OUT (R3/R4). A healthy, untriggered line sits at 5 V × 47 / 51.7 ≈ 4.55 V. A broken OUT or VCC wire leaves the pull-down alone, so the line reads LOW and that direction is blocked.
- **Placement:**
  - Both sensors sit in the channel on the barrel's −Y side, branded face toward the rod, leads to the rear.
  - The magnet (N35, Ø4 × 2, axis radial) is glued into the carrier facing the channel.
  - U1 is at z 5.4 mm and U2 at z 43.0 mm (z = 0 is the gearbox front face). Each can slide ±3 mm.
- **Switching points (model):**
  - From `magnet_trigger.json`, the output goes LOW about 3.9 mm before the magnet centre reaches the sensor centre and back HIGH about 4.3 mm after it.
  - The sensors therefore sit 3.8 mm outboard of the end positions, at magnet z 9.2 and 39.2. The steel screw and nut are not modelled.
  - The datasheet thresholds (AJ option) are BOP 3–12 mT (typ 6.9) and BRP 1–5 mT (typ 3.5).

## Hardware direction gates (U3, SN74HC08)

| U3 pin | Connection |
|---|---|
| 14 / 7 | +5V / GND, 100 nF (C3) at pin 14 |
| 1 | EXT_CMD from Nano D9, 10 kΩ (R5) to GND |
| 2 | ALLOW_EXT (W6) |
| 3 | AIN1 of U4, 10 kΩ (R7) to GND |
| 4 | RET_CMD from Nano D10, 10 kΩ (R6) to GND |
| 5 | ALLOW_RET (W3) |
| 6 | AIN2 of U4, 10 kΩ (R8) to GND |
| 9, 10, 12, 13 | GND (unused gates) |
| 8, 11 | open |

AIN1 = EXT_CMD · ALLOW_EXT and AIN2 = RET_CMD · ALLOW_RET. At the extend end ALLOW_EXT is LOW, so an extend command cannot reach the driver, while retract still works; the same holds at the other end. This does not depend on the firmware, only on +5 V for the sensors and U3. The pull-downs keep every input LOW while the Nano resets, so the motor stays off.

Not detected: an open GND wire (W2/W5, the sensor then floats HIGH through its pull-up), a signal shorted to +5 V, or a lost magnet. The current limit and the firmware's 30 s run timeout are the backup.

## Motor driver and current protection

- **Motor path:** U4 AOUT1 → U5 (ACS712-05B) IP+ → IP− → W7 → motor → W8 → U4 AOUT2. D1 (SMBJ8.0CA) and C7 (100 nF) sit across MOTOR_A/MOTOR_B at J1.
- **U4 (Pololu #2130):**
  - VIN with C4 100 µF + C5 100 nF, fed through F1.
  - SLP (nSLEEP) is pulled high on the carrier, and the firmware drives it from D8.
  - FLT (nFAULT) is open drain; D7 uses INPUT_PULLUP.
  - Channel B is unused.
- **Hardware current limit:**
  - The carrier ties AISEN to GND by default. Cut the break point on the back and solder R11 (0.25 Ω, 1206, ≥ 0.5 W) on the pads.
  - It chops at about 0.2 V / 0.25 Ω = 0.8 A (0.64–0.96 A over the threshold tolerance).
- **Firmware:** `actuator_protection/actuator_protection.ino` with `protection_logic.h`.
  - It zeroes U5 at power-up and reads A0 through R9 1 kΩ / C6 1 µF / R10 100 kΩ.
  - It latches a fault at 550 mA for 150 ms (after 100 ms of start-up blanking), after a 30 s run or on a driver/sensor fault.
  - Reset needs a released direction plus a fresh press of the reset button.
  - These are commissioning start values: if your motor stalls below 550 mA, lower the threshold.

| Nano pin | Use |
|---|---|
| D2 / D3 / D4 | SW1 extend / SW2 retract / SW3 reset, to GND, INPUT_PULLUP |
| D5 / D6 | ALLOW_EXT / ALLOW_RET, plain INPUT, **no** internal pull-up |
| D7 | U4 FLT (nFAULT), INPUT_PULLUP |
| D8 | U4 SLP (nSLEEP) |
| D9 / D10 | EXT_CMD / RET_CMD (PWM) into U3 pins 1 / 4 |
| A0 | I_SENSE from U5 |
| D13 | on-board LED: fault |
| 5V / GND | +5V logic rail, common ground |

Never feed VM into the Nano 5V pin.

## Commissioning

Follow the calibration list in `README.md`:

1. Check the direction first.
2. Measure W3/W6 levels.
3. Calibrate each end with the sensors sliding in the channel.
4. Check the power-cycle and broken-wire behaviour.
5. Then set the current threshold against the real motor and load.

Neither the code nor the animation replaces a powered bench test.

## Checks run on this package

- `python check_direction_gates.py`: all 16 gate input states, independent end blocking, reverse exit and the broken-OUT-wire model. Writes `direction_gate_validation.json`.
- `protection_logic_test.cpp`: compiled with asserts enabled (`c++ -std=c++17 -UNDEBUG protection_logic_test.cpp`) and passed: inrush, sustained overload, spikes, latching, reset, reversal, timeout, faults and timer wrap.
- The sketch compiles against an Arduino API stub. It has not been built with the Arduino core or flashed.
- `source/build_schematic.py`:
  - schematic connectivity equals the netlist (29 nets, 107 pins);
  - every junction has a dot and there are no dangling wire ends;
  - the sketch's pin constants sit on the right nets.

## Sources

- TI DRV5033 datasheet: pinout, LPG package, open-drain output, BOP/BRP. <https://www.ti.com/lit/ds/symlink/drv5033.pdf>
- TI SN74HC08 datasheet. <https://www.ti.com/lit/ds/symlink/sn74hc08.pdf>
- Pololu DRV8833 carrier #2130: pin labels, SLP pulled high, FLT floating, AISEN/BISEN tied to GND until the break point is cut. <https://www.pololu.com/product/2130>
- TI DRV8833 datasheet: current chopping threshold. <https://www.ti.com/lit/ds/symlink/drv8833.pdf>
- Allegro ACS712 datasheet: -05B sensitivity 185 mV/A. <https://www.allegromicro.com/-/media/files/datasheets/acs712-datasheet.ashx>

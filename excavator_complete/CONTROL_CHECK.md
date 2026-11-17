# Control circuit check: main board rev A, its firmware and the machine wiring

**Scope.** The X1 main board (`track_wheel_jgy370/X1/controller/main_board`), its firmware (`controller/firmware`) and the way the complete machine's wiring (WIRING.md) connects to them, checked on 2026-11-07 against the datasheets, the spec C1 and the subsystem designs. Nothing has run on hardware.

**Result.** The board design holds up: every rule and calculation re-runs clean, the schematic matches the datasheet pin for pin, and the datasheet confirms the current-sensing assumption the firmware depends on. One firmware protection rule did not work as the spec intended and is fixed (S4). Three design points are flagged for a rev B board; none blocks ordering rev A.

**Update 2026-11-10: main board rev B.** The arm's V6-U60 actuators now use the 12 V N20 1:50 motor with an M4 leadscrew. Rev B therefore:
- moves their four DRV8876s from the 6 V buck to VBAT;
- removes the buck (U111 and its parts) and the 6 V sense (R131, R132, C131 on GPIO7).

The firmware changed with it:
- the S4 stall cut-out now covers the actuators, using a 13 Ω stall estimate;
- the boom thresholds are rescaled to the new motor's current.

The battery budget is 4.45 A with the actuators at their own PTC's 0.35 A hold, and 5.04 A briefly with every channel at its limit (main_board/DESIGN.md). Item 1 of section 5, the headers, was resolved on 2026-11-14 with top-entry headers. Items 2 and 3 are still open: rev B does not change the 3.3 V supply, and its fuse margin is in item 3. The tables below are the rev A record.

## 1. What was re-run

| Check | Command | Result |
|---|---|---|
| Netlist rules (every net joins 2 pins, one use per GPIO, ADC1 only, enables off strap/glitch pins, straps low, driver mode pins, voltage ratings) | `main_board/source/netlist.py` | 7 of 7 pass |
| Electrical checks against the datasheet limits (ITRIP, IPROPI, VM, logic levels, PWM, bucks, LDO, sense ranges, battery budget, FET loss, clamps, PTCs, height) | `check_design.py` | 60 of 60 pass; the regenerated `X1_main_board_A_design_checks.json` differs from the committed file in one label only |
| Pin map and BOM generators | `pinmap.py`, `bom.py` | regenerate the committed files unchanged |
| Firmware host tests (packets, mapping, ramps, arming, link loss, E-stop, stall, battery, nFAULT, boom pair, wrap, telemetry, bench, parsers), gcc 14 with the address and UB sanitizers | `firmware/test/run_tests.sh` (Docker) | PASS, before and after the S4 change |

KiCad's ERC/DRC were not re-run (no KiCad here); the committed `*_schematic_checks.json` and `*_pcb_checks.json` are from 2026-11-05/06 and the netlist has not changed since.

## 2. Datasheet facts verified (TI DRV8876 SLVSDS7B, Espressif ESP32-S3 v2.2, ESP32-S3-WROOM-1 v1.8)

The PDFs were read directly (text extracted with PyMuPDF), not from memory.

| Point | Datasheet | Design |
|---|---|---|
| HTSSOP (PWP) pins: 1 EN/IN1, 2 PH/IN2, 3 nSLEEP, 4 nFAULT, 5 VREF, 6 IPROPI, 7 IMODE, 8 OUT1, 9 PGND, 10 OUT2, 11 VM, 12 VCP, 13 CPH, 14 CPL, 15 GND, 16 PMODE, pad GND | DRV8876 p. 3 | `netlist.py` DRV8876 cells: identical |
| A_IPROPI = 1000 µA/A; ITRIP × A_IPROPI = V_VREF / R_IPROPI | p. 6, p. 13 eq. 3 | `calcs.py`: 2.4k → 1.034 A, 4.12k → 0.602 A, 4.99k → 0.497 A |
| **IPROPI reflects the current through the low-side FETs, and in the brake / slow-decay state it is "proportional to the current in one of the low-side MOSFETs"** | p. 12, 7.3.3.1 | With EN = 0 braking (PH/EN mode, slow decay) the motor current recirculates through one low-side FET at every instant, so the 100 µs RC + 20 ms software filter of IPROPI follows the motor current at any duty. The firmware's stall, boom-balance and end-stop thresholds rely on this; it holds. |
| IMODE = GND: fixed off-time (25 µs) current chopping with automatic retry; PMODE = low: PH/EN | p. 13 table 6, p. 10 table 2 | both pins to GND on all seven drivers |
| V_VREF 0–3.6 V; I_IPROPI max 3 mA; A_ERR ±7.5 mA below 0.15 A, ±5 % to 0.5 A; UVLO rising max 4.6 V; t_WAKE 1 ms; VIH 1.5 V | p. 4–6 | VREF 2.48 V; worst IPROPI 1.03 mA; the 0.12 A actuator reading carries ±6 %; the 6 V rail is above UVLO; nFAULT is blanked 5 ms after nSLEEP |
| GPIO46 is I/O/T (not input-only as on the ESP32-S2); GPIO45 and GPIO46 have internal weak pull-downs at reset; strapping pins are GPIO0, 3, 45, 46 | ESP32-S3 p. 17, p. 22, p. 32 | lamps on 45/46 with the board's 100k pull-downs are safe; GPIO3 is a current input (JTAG strap ignored with the default eFuse) |
| ADC2 cannot be used while Wi-Fi is active; ADC1_CH0–9 = GPIO1–10 | p. 24, p. 59 | all nine analog inputs are on ADC1 |
| WROOM-1 note b: IO35–37 are tied to the Octal PSRAM only on R8/R16V modules | WROOM-1 p. 12 | the N8 (no PSRAM) frees them for the track drivers' EN/PH |

## 3. Finding fixed: the stall cut-out (S4) only worked near full speed

- **Rule as written (spec S4, firmware before this check):** a 12 V channel at 90 % or more of its board limit for 2 s is switched off.
- **Why it did not work:** the DRV8876 only reaches its limit when the motor asks for it. A stalled JGY-370 draws duty × V_bat / R_motor with no back-EMF; with R ≈ 9.2 Ω (12 V / 1.3 A stall, vendor table) that is 0.85 A at the default 65 % speed, under 90 % of the 1.03 A limit. Below about 72 % duty the rule could never trip, while the stalled motor dissipated several watts inside the closed J9 pod (J9 open item 8 is exactly this risk).
- **Fix (`control_logic.cpp`, `Config::motor_ohm`, `Config::stall_min_a`):** the threshold is now 90 % of the stalled current at the present duty, min(limit, duty × V_bat / R), and the rule is not judged while that estimate is under 0.4 A (twice the rated 0.2 A, where a loaded running motor comes too close). At full duty nothing changes. New host tests cover 65 % duty (0.85 A cut, 0.30 A not) and 25 % duty (not judged). Measure R on the bench and set `motor_ohm`.

## 4. Wiring points settled for the harness (WIRING.md)

- **Actuators:** XH pin 1 (OUT1) = V6 wire A (red), pin 2 (OUT2) = wire B (black). PH = 1 drives OUT1 high, A positive extends: boom up, stick in (crowd), bucket curl, the app's positive axes. No `flip` should be needed.
- **Tracks:** both motors wired the same way (motor + to pins 1 and 3). The firmware inverts channel 2 for the mirrored right motor; the old X1 note "reverse the right motor electrically or in the controller" is now "in the controller" only (fixed in X1/ASSEMBLY.md).
- **Swing:** the sense of rotation for PH = 1 depends on the motor and gear train and is set on the bench with `flip 3` if needed.
- **Slip ring:** rings 1–4 carry 1 A at 20 kHz PWM; a 100 nF capacitor across each JGY-370's tabs is added to the harness for brush noise near the ESP-NOW radio.
- **Battery current path:** 20 AWG silicone for the feed and the 12 V link (4.3 A worst case); 26 AWG elsewhere.

## 5. Flagged for a rev B board (not blocking)

1. **Side-entry inboard headers sit 3 mm from the T101 rib.** *Adopted 2026-11-14: rev B now has the top-entry headers below on the same pads (main_board/DESIGN.md); the harness comes straight down onto the plugs (WIRING.md 2.2).* A mated XH plug with its lead bend reaches 12 mm out of the board edge, toward the rib, and the harness drops its wires into the 3 mm gap and turns them back into the plugs (1.1 mm to the rib in WIRING.md's check, whose rule is 1.0 mm). DESIGN.md lists top-entry alternatives (B2B-XH-A C158012, B4B-XH-A C144395, B3B-PH-K-S C131339, B4B-PH-K-S C131334); KiCad's footprints give them the same pads. With them the plugs go on from above and the cables drop straight onto them (XH plug tops at Z 121.4; the hood over the headers is at Z 199–217). They do not let the plugs go on with the left half in place: its hood covers the board, so plugging stays a job with the half beside the machine (BODY.md's 150 mm slack). *Corrected 2026-11-14:* this item said before that top entry allowed plugging with the half in place, under a hood at Z 136.3. That figure is the bottom edge of the hood's front wall, not the hood over the headers.
2. **3.3 V LDO heat.** 600 mA from 4.6 V with 184 °C/W: fine at the assumed 0.15 A average, but a long Wi-Fi burst at 0.5 A would be 0.65 W. Bench item, as DESIGN.md says; a 3.3 V buck is the rev B fallback.
3. **Fuse margin.** 4.33 A worst case against a 5 A fuse; the later 4G stick takes it to 5.5 A (spec P4). Review with that phase. Rev B, with the actuators on VBAT: 4.45 A with the actuators at their PTC's 0.35 A hold, 5.04 A for the moment every channel is at its limit, about 6.1 A with the 4G stick (spec P4, issue 5).

## 6. Not verified here

Radio range from inside the body, IPROPI accuracy at 0.12 A, motor directions, the DRV8876 thermal figure in the closed bay, and everything the firmware README lists as hardware-only.

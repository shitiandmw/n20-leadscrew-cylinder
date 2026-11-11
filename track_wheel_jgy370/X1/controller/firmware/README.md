# X1 main board firmware (machine side)

Firmware for the X1 main control board, rev A: an ESP32-S3-WROOM-1-N8 and seven DRV8876 drivers in PH/EN mode. It follows [../SPEC.md](../SPEC.md) (spec C1): the channel table in section 2, the control mapping in section 4, safety S1–S6, the radio link L1–L3, the handle's packet contents (H1) and the firmware points F1, F2 and F4. The board facts come from [../main_board/DESIGN.md](../main_board/DESIGN.md) and [../main_board/PINMAP.md](../main_board/PINMAP.md).

**Status:** the host tests pass and the sketch compiles for the ESP32-S3. Nothing has run on hardware yet.

## Files

| Path | What it is |
|---|---|
| `common/x1_link.h` | The link packets, shared with the future handle firmware. **Master copy.** |
| `x1_main/x1_main.ino` | The sketch: the hardware layer only (MCPWM, PH pins, nSLEEP, nFAULT, ADC, LEDC, LED, ESP-NOW, NVS, USB console) |
| `x1_main/src/control_logic.h`, `.cpp` | The logic core, plain C++17 with no Arduino headers: channel table, input mapping, ramps, boom pair, S1–S6, telemetry |
| `x1_main/src/x1_main_pins.h` | Copy of `main_board/x1_main_pins.h`, written by `main_board/source/pinmap.py`. Do not edit. |
| `x1_main/src/x1_link.h` | Copy of `common/x1_link.h`, written by `sync_headers.sh`. Do not edit. |
| `sync_headers.sh` | Copies `common/x1_link.h` into each sketch |
| `test/control_logic_test.cpp` | Host tests (SPEC F4) |
| `test/run_tests.sh` | Checks the header copies, then builds and runs the tests |

### Why the headers are copied

The Arduino build copies the sketch folder to a build directory, so an `#include` that points outside the sketch breaks. So each header lives inside the sketch too:
- **Pin map:** `pinmap.py` (run from `main_board/source/`) writes `main_board/x1_main_pins.h` and an identical `x1_main/src/x1_main_pins.h`.
- **Link packets:** the master is `common/x1_link.h`. After editing it, run `./sync_headers.sh`. The handle sketch, when it exists, gets its own copy the same way (add it to the script's list).

`test/run_tests.sh` fails if either copy differs from its source.

## Build and flash

You need the Arduino IDE 2 or `arduino-cli`, with the **esp32 core 3.x** by Espressif (compiled here with 3.3.12, which is ESP-IDF 5.5). The board manager URL is `https://espressif.github.io/arduino-esp32/package_esp32_index.json`.

Board settings (IDE: Tools menu):
- Board: **ESP32S3 Dev Module**
- USB CDC On Boot: **Enabled** (the sketch stops with an error otherwise, because the console is on the native USB)
- USB Mode: Hardware CDC and JTAG
- Flash Size: 8MB; Partition Scheme: 8M with spiffs; PSRAM: Disabled

With `arduino-cli`, from this folder:

```sh
FQBN=esp32:esp32:esp32s3:CDCOnBoot=cdc,USBMode=hwcdc,FlashSize=8M,PartitionScheme=default_8MB,PSRAM=disabled
arduino-cli core install esp32:esp32@3.3.12 --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli compile --fqbn "$FQBN" x1_main
arduino-cli upload --fqbn "$FQBN" -p /dev/ttyACM0 x1_main
arduino-cli monitor -p /dev/ttyACM0
```

If the port does not appear, hold BOOT, press and release RESET, release BOOT, and upload again.

## Tests

```sh
./test/run_tests.sh
```

It checks the two header copies, then builds `control_logic_test.cpp` with `control_logic.cpp` (C++17, `-Wall -Wextra -Wpedantic -Werror`, address and undefined-behaviour sanitizers) and runs it. It uses `g++` (or `$CXX`) if there is one, otherwise Docker with `gcc:14`. The binary goes to `/tmp/x1fw-test`.

The tests cover: CRC and packet checks; the channel table against the pin header; the mapping signs against the app (every keyboard binding and a grid of pad positions through the app's own formula); ramps, reversal and speed scaling; the dead band; both track buttons and the pivot turn; power-up arming; link loss; sequence numbers; EMERGENCY STOP and RESUME; the stall cut-out; low battery; nFAULT; boom balancing, imbalance fault, end stops and re-sync; `millis()` wrap; telemetry, lamps, horn and travel alarm; the bench drive; and the console parsers.

## How the machine behaves

### Inputs and mapping (SPEC 4)

The handle sends calibrated stick positions, -1000..1000, with x positive to the right and y positive when pushed forward. The machine applies the app's 12 % dead band (a component under 12 % is zero; anything else passes unchanged, as in `main.js`), then the ISO mapping with the app's signs:

| Handle input | App label | App axis | Channel |
|---|---|---|---|
| left stick forward / back | STICK OUT / STICK IN | stick −1 / +1 | 6 stick |
| left stick left / right | L / R | slew −1 / +1 | 3 swing |
| right stick forward / back | LOWER / RAISE | boom −1 / +1 | 4 + 5 boom |
| right stick left / right | CURL / OPEN | bucket +1 / −1 | 7 bucket |
| LEFT TRACK ↑ / ↓ | | leftTrack +1 / −1 | 1 left track |
| RIGHT TRACK ↑ / ↓ | | rightTrack +1 / −1 | 2 right track |

- Each channel's duty is the axis times the movement speed (20–100 %). Both buttons of one track pressed give 0, so that track stops.
- In the app, a positive boom, stick or bucket axis lengthens that cylinder. The firmware drives PH = 1 for a positive duty. Whether "OUT1 high" really extends each actuator or turns each motor the right way depends on the wiring. Check it on the bench and fix it with `flip` if needed.
- The right track's PH is inverted, because that motor is mounted mirrored. So forward on both tracks gives PH 1 on the left and PH 0 on the right.

### Ramps (SPEC 2)

The ramp times are for a full-scale change: 0.3 s for the tracks, 0.4 s for the swing, 0.1 s for the actuators. A reversal ramps through zero. EN is 20 kHz MCPWM; EN = 0 brakes.

### Boom pair (SPEC 4)

- Both sides get the same command.
- **Balancing.** The side drawing more current has its duty trimmed down at 5 % per second, up to 15 %. Differences within 10 mA count as matched. The trims reset when the boom reverses. Currents are not judged for the first 0.3 s of a move, or below 15 % duty.
- **End stops.** If one side reads under 25 mA (its end stop has opened), its trim is dropped and the other side keeps being driven. If the other side does not stop within 10 s, that is a boom fault.
- **Imbalance fault.** If the difference stays over 40 mA for 3 s, the boom stops and the fault is reported. The other channels keep working. RESUME clears it.
- **Re-sync button.** A press drives both sides towards the retract end stops (boom down) at the movement speed, until both read zero current. It stops early on a second press, on any boom input, on a link loss, or after 120 s (reported). Imbalance is not judged while it runs. A press also clears a boom fault, because re-syncing is the remedy.

All these values are starting points from the spec, in `Config` in `control_logic.h`, to be tuned on the bench.

### Safety

| Rule | What the firmware does | What clears it |
|---|---|---|
| S1 link loss | No valid packet for 350 ms: the swing ramps down over its 0.4 s, every other channel stops at once | A valid packet, then all inputs centred |
| S2 EMERGENCY STOP | Latched when the handle's ESTOP bit is set. It stops everything, and the swing ramps as in S1. The latch survives a link loss. | A fresh RESUME press, with ESTOP released and all inputs centred |
| S3 power-up | The drivers stay asleep (nSLEEP low) until a valid packet arrives with all inputs centred | — |
| S4 stall | A 12 V channel (tracks, swing) at 90 % or more of the current a stalled motor would draw at its present duty, for 2 s, is switched off. That current is duty × battery voltage / 9.2 Ω (the JGY-370-1260's 12 V / 1.3 A stall figure), capped at the board limit (1.034 A or 0.602 A, from the pin header). Below a stalled current of 0.4 A (about 30 % duty at 12 V) the rule is not applied. | Its input returns to centre |
| S5 battery | A 2 s first-order filter on VBAT. Below 10.5 V: warning (cleared above 10.7 V). Below 9.6 V: motors stop. | The filtered battery voltage back above 10.5 V |
| S6 nFAULT | Low for 4 ms or more stops everything; it is reported. The line is ignored for 5 ms after nSLEEP rises. | RESUME with the line high |

"All inputs centred" means: sticks inside the dead band, no track button and no re-sync button. Every stop leaves the machine disarmed. It re-arms only on a packet with all inputs centred. The drivers sleep while the machine is disarmed and nothing is moving.

### Outputs

- **Lamps.** They follow the handle's LAMP1 and LAMP2 bits (the wanted states). They keep their last state through a link loss.
- **Buzzer.** In order of priority:
  - horn: on while held (link up only);
  - travel alarm: 0.4 s on, 0.4 s off while a track moves;
  - fault (driver, boom, re-sync timeout, stall, battery low): 0.1 s beep each second;
  - battery warning: 0.1 s beep every 5 s.
- **Status LED.**
  - pairing: fast blink;
  - E-stop or a fault: double flash;
  - armed or bench drive: on;
  - handle linked but not armed: 0.5 s blink;
  - no handle: short flash every 2 s.

### Telemetry (10 Hz)

Telemetry carries: state bits (armed, link, E-stop, pairing, re-sync, bench), fault bits, filtered battery, the 6 V rail, the RSSI of the last control packet, control packets per second, and per channel the signed duty, current and flags (stall cut, boom cut, PH level, at end stop). See `x1_link.h`.

## Radio and pairing (SPEC 6)

- ESP-NOW on a fixed Wi-Fi channel (default 1; console `wifi`). The station does not connect to any network.
- Traffic is encrypted. A fixed project PMK (`x1link::PMK`) wraps a 16-byte link key (LMK) that the machine makes at random when it pairs. The handle's MAC and the key are stored in NVS. Only control packets from that MAC are passed to the logic.
- **Pairing.** Type `pair` on the console, or, within 10 s of power-up, hold BOOT for 2 s. Do not hold BOOT through a reset: GPIO0 is a strap pin, and the chip would start its ROM downloader. The machine then listens for 60 s, disarmed:
  1. The handle broadcasts a `PairRequest`.
  2. The machine answers with a `PairAccept` (a new key and the channel).
  3. The handle replies with a `PairConfirm` (a check of the key).

  The machine then stores the pair. If the window times out, the old pair is kept. The key crosses the air in clear once, during the window. Pair away from other people's radios, or set the key by hand with `peer`.
- **What is not covered.** ESP-NOW may also hand over unencrypted frames that carry a forged source MAC. The machine checks only the MAC and the CRC; the packets carry no authentication code of their own. This is not verified on hardware.

## Console (USB, 115200)

| Command | What it does |
|---|---|
| `help` | the list |
| `show` | state, faults, handle inputs, radio counters, boom trims, and per channel the duty, PH, current, offset and flags; the machine MAC and the paired handle |
| `log <ms>` / `log off` | one status line every `<ms>` |
| `zero` | measures the current offsets (drivers awake, all bridges braked, so no current flows) and saves them. Only while disarmed. |
| `wifi [1-13]` | shows or sets the radio channel (saved) |
| `pair` | pairing mode for 60 s |
| `peer [<mac> <key>]` | shows the paired handle, or sets it by hand (`aa:bb:cc:dd:ee:ff` and 32 hex digits) |
| `unpair` | forgets the paired handle |
| `drive <1-7> <-100..100> [ms]` | bench drive of one channel, default 1000 ms, max 10 s. Refused while a handle is linked, the E-stop or a driver fault is latched, the battery is low, or pairing is on. Ramps and S4–S6 still apply. Channels 4 and 5 both drive the boom pair, so the boom does not twist. |
| `stop` | stops a bench drive |
| `clear` | clears the boom, re-sync and driver faults. Only without a handle link; never the E-stop. |
| `flip <1-7>` | inverts one channel's direction (saved), for a motor wired the other way round |
| `reboot` | restarts |

The NVS namespace is `x1main`. Its keys are `peer`, `lmk`, `chan`, `ioff` (offsets in 0.1 mV) and `flip`.

## Interpretations of the spec

- **S4 follows the duty.** The spec says "90 % of its limit"; the driver only reaches its limit when duty × Vbat / R exceeds it, so at the default 65 % speed a stalled track motor draws about 0.85 A, under 90 % of 1.03 A, and a fixed threshold would never trip. The firmware therefore compares the current with 90 % of the stalled current at the present duty, and does not judge below a stalled current of 0.4 A (twice the rated 0.2 A), where a loaded running motor comes too close to it. `Config::motor_ohm` (9.2 Ω) is the vendor stall figure; measure it on the bench.
- **Ramp time = full scale.** "0.3 s" is the time from 0 to 100 % duty, so a track at 65 % speed gets there in about 0.2 s.
- **Dead band.** It is applied as the app does it: no rescaling, so the output jumps from 0 to 12 %. The ramp smooths that jump. The machine applies the band even if the handle already has.
- **S5 filter.** "2 s filtered" is a first-order filter with a 2 s time constant. A step from 12 V to 9 V warns after about 1.4 s and stops after about 3.2 s. The stop holds until the filtered voltage is back above 10.5 V. That needs a charged pack, not just a resting one; without that hold, the stop would cycle as the voltage recovered.
- **What RESUME clears.** It clears the E-stop latch, and also the latched boom, re-sync and driver faults. It is the one "acknowledge" button on the handle.
- **Re-arming.** Every stop (S1, S2, S5, S6, pairing) leaves the machine disarmed until the inputs are centred, as at power-up (S3).
- **Re-sync speed.** The re-sync runs at the movement speed setting.
- **The boom's thresholds** (10 mA match band, 25 mA end-stop level, 0.3 s blank, 15 % minimum duty, 10 s and 120 s timeouts) are mine; the spec gives only 15 %, 40 mA and 3 s.
- **The bench drive and `flip`** are extra. Without a handle (parked), the console is the only way to run a motor on the bench.

## Verified and not verified

Verified here:
- `test/run_tests.sh` passes (gcc 14 in Docker, with the sanitizers).
- `pinmap.py` rewrites `main_board/PINMAP.md` and `x1_main_pins.h` unchanged, and its sketch copy is identical.
- The sketch compiles with `arduino-cli` 1.5.1 and esp32 core 3.3.12, for the FQBN above, with `--warnings all` and no warnings: 912,296 bytes of flash (27 % of the 3 MB app partition) and 48,456 bytes of static RAM.

Not verified (nothing has run on hardware):
- MCPWM output at 20 kHz on the EN pins, and the forced levels at 0 % and 100 %.
- ADC readings, calibration, offsets and IPROPI accuracy at about 0.1 A (SPEC open item 1).
- Whether the averaged IPROPI reading at part duty matches the motor current. The stall, balance and end-stop thresholds assume it does.
- Motor and actuator directions.
- ESP-NOW encryption, pairing, range, RSSI, and the behaviour with forged unencrypted frames.
- NVS storage, the BOOT pairing press, the buzzer and lamp PWM, and the console over USB CDC.
- Timing of the 2 ms control loop alongside the radio.
- The handle side of the pairing protocol: the handle does not exist yet.

# n20-leadscrew-cylinder

**A 3D-printable linear actuator for a model excavator that looks like a hydraulic cylinder.** It is driven by a standard N20 gearmotor with an integrated M3 leadscrew, used exactly as bought.

![n20-leadscrew-cylinder: yellow barrel, graphite end caps, chrome-look rod and clevis eyes](actuator_v5/images/hero.png)

The motor's own leadscrew drives a brass nut inside the rod. Two Hall-effect end stops hide in a covered channel along the barrel. A small controller blocks each direction in hardware once that end is reached.

The geometry, STL/STEP files, wire routes, schematic and a self-contained 3D preview are all generated from parametric Python (CadQuery).

> **Status:** the design is complete and checked in CAD, but it has not been printed or powered yet. See [Status](#status).

## Features

- **Unmodified N20 leadscrew motor.** There is no coupler, bearing or separate screw. The brass M3 nut in the rod's carrier rides directly on the motor's screw. The gearbox seats on a step in the barrel and the rear cap backs the motor can.
- **Hydraulic-cylinder look:**
  - a round Ø21 mm yellow barrel;
  - Ø23 mm graphite end caps, with a wiper lip at the rod end;
  - a Ø9 mm chrome-look rod;
  - Ø14 mm clevis eyes for Ø3 mm pins;
  - a hose-style cable port with a TPU boot.
- **Hidden end stops.** Two DRV5033AJ Hall sensors sit in a dovetail channel under a flush cover strip, along with their resistors, capacitors and wiring. Each sensor slides ±3 mm for calibration.
- **Hardware direction gating.** A 74HC08 blocks motion toward an end as soon as that end's sensor trips, regardless of the firmware. The Arduino adds a current trip (ACS712), a 30 s run timeout and latching faults.
- **Parametric.** Change the leadscrew length and the stroke, barrel, rod, sensor positions, cover strip and wire routes all follow.
- **Self-checking outputs.**
  - The CAD build checks for interference over the full stroke, checks that every wire lands on its terminal, and checks that every STL is watertight.
  - The schematic generator rebuilds the connections from the drawing itself. It compares them with the netlist and with the firmware's pin constants.

## Specifications

Default build, for a 40 mm leadscrew:

| | |
|---|---|
| Stroke | 30 mm, plus 2 / 3 mm mechanical over-travel at retract / extend |
| Pin centres | 108 mm retracted → 138 mm extended |
| Barrel | Ø21 × 76 mm, end caps Ø23 mm |
| Rod | Ø9 mm |
| Clevis eyes | Ø14 mm, 10.4 mm thick, Ø3.2 mm holes |
| Motor | N20 gearmotor (10 × 12 mm body) with integrated M3 × 0.5 leadscrew |
| End stops | 2 × TI DRV5033AJQLPG and an N35 Ø4 × 2 mm magnet |
| Electronics | 6 V motor supply, 5 V logic: DRV8833, ACS712-05B, SN74HC08, Arduino Nano |

A longer screw gives a longer stroke. For example, a 60 mm screw gives 50 mm of stroke and 128 → 178 mm pin centres. See the [full table](actuator_v5/README.md#rebuild).

## A look inside

<p align="center">
  <img src="actuator_v5/images/section.png" width="49%" alt="Section through the actuator">
  <img src="actuator_v5/images/wiring.png" width="49%" alt="Sensor channel with the cover strip removed">
</p>

The left image is a section on the pin plane, showing the motor, leadscrew, brass nut in the rod's carrier, and magnet. The right image shows the sensor channel with the cover strip removed.

For an interactive view, download [`actuator_v5/3D_preview.html`](actuator_v5/3D_preview.html) and open it in any browser. It is a single 7 MB file that works offline; GitHub can't run it in the page. The preview includes:

- exterior, section, wiring and core-part views;
- a stroke slider;
- a live demo of the end stops and the overcurrent trip.

## Electronics

| Sheet 1: inside the actuator | Sheet 2: controller board |
|---|---|
| [![Schematic sheet 1](actuator_v5/electronics/schematic_sheet1.png)](actuator_v5/electronics/schematic_sheet1.svg) | [![Schematic sheet 2](actuator_v5/electronics/schematic_sheet2.png)](actuator_v5/electronics/schematic_sheet2.svg) |

- Full schematic: [`schematic.pdf`](actuator_v5/electronics/schematic.pdf) (A3).
- Harness, pin tables and commissioning: [`wiring.md`](actuator_v5/electronics/wiring.md).
- Firmware: [`actuator_protection.ino`](actuator_v5/electronics/actuator_protection/actuator_protection.ino).

## Repository layout

```
actuator_v5/
├── README.md           build guide: print settings, assembly order, calibration, rebuild
├── BOM.md              everything to buy, with reference designators
├── 3D_preview.html     offline interactive 3D viewer
├── stl/                printable parts (PETG); soft/ = TPU boot; fit_samples/ = test slices
├── step/               single parts plus the full assembly with wiring
├── electronics/        schematic, netlist, wiring.md, Arduino sketch, logic tests
├── images/             renders and analysis plots
├── references/         motor drawing and photo the design is based on
├── parameters.json     key dimensions of the current build
├── validation.json     geometric check report
└── source/             generators (CadQuery, schemdraw, Blender, three.js viewer)
```

## Building one

1. **Measure your leadscrew** from the gearbox front face to the tip. If it is not 40 mm, rebuild with `--screw-length` (see below).
2. **Print** the parts in `actuator_v5/stl/` in PETG and the boot in `stl/soft/` in TPU 95A. Print the four fit samples first.
3. **Buy** the parts in [`BOM.md`](actuator_v5/BOM.md).
4. **Assemble, wire and calibrate** by following the [build guide](actuator_v5/README.md#assembly-order). Check the motor direction first. Then set each Hall sensor so that it stops the motor just before the mechanical stop.

## Rebuilding from source

Tested with Python 3.11 and the packages in [`requirements.txt`](actuator_v5/source/requirements.txt) (CadQuery 2.8, trimesh, schemdraw, matplotlib, ReportLab, PyMuPDF). The renders need Blender 4.2.

```sh
cd actuator_v5
pip install -r source/requirements.txt
python source/build_v5.py --screw-length 40         # STEP/STL, meshes, validation (about 3 minutes)
python source/magnet_trigger.py                     # magnet model and Hall placement
python source/build_schematic.py                    # schematic, plus connectivity and firmware checks
python source/build_viewer.py                       # 3D_preview.html
blender -b -P source/render_v5.py -- --out images   # optional renders
```

`build_v5.py` stops with an error if any geometric check fails.

The logic tests need no hardware (run them from `actuator_v5/` too):

```sh
python electronics/check_direction_gates.py         # 74HC08 gates: all 16 input states
c++ -std=c++17 -UNDEBUG electronics/protection_logic_test.cpp -o /tmp/protection_test && /tmp/protection_test
```

## Status

Checked:

- **CAD** (results in [`validation.json`](actuator_v5/validation.json)):
  - no interference between parts, hardware and wires anywhere in the stroke;
  - all eight wires land on their terminals;
  - wire routes still clear with each sensor moved ±3 mm;
  - every STL is watertight.
- **Electronics:**
  - the schematic's connections match the netlist and the firmware's pin map;
  - the 74HC08 truth table passes;
  - the protection-logic unit test passes;
  - the Arduino sketch compiles against a stub of the Arduino API.

Not verified yet:

- printing and fit;
- the real motor's ratings, the gearbox's axial load capacity and PETG creep under load;
- magnetic switching on real parts (the magnet model ignores the steel screw and nut);
- the firmware running on a board.

The current trip (550 mA for 150 ms) is a starting value. Set it against the real motor during commissioning.

To do:

- the remaining renders (stroke positions and close-ups);
- an illustrated assembly guide PDF.

## License

No license has been chosen yet. The bundled three.js is MIT-licensed (see [`THREE_LICENSE.txt`](actuator_v5/source/vendor/THREE_LICENSE.txt)).

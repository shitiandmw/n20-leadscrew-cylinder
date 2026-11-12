"""Generate the X1 main board KiCad 9 schematic from netlist.py.

Writes kicad/X1_main.kicad_sch (root) and one sub-sheet per netlist sheet, the project symbol
library (X1_main.kicad_sym), the project file and the symbol library table. The circuits are drawn
with wires; net labels carry only the signals that leave a block or a sheet. check_kicad.py then
has KiCad run ERC and export the netlist, and compares it with netlist.py pin by pin.

Layout coordinates below are in grid units of 2.54 mm.

    python build_schematic.py
"""
import json
import sys
from pathlib import Path

import calcs as CA
import kicad_sch as K
import netlist as NL
import sexp
from kicad_sch import G
from sexp import Sym as S

HERE = Path(__file__).resolve().parent
BOARD = HERE.parent
KDIR = BOARD / "kicad"
ROOT_UUID = K.uid("root")
NETS = K.NETLIST
GP = {net: g for g, net in NL.GPIO_MISC.items()}
ADC_LIST = ", ".join(str(g) for g in sorted(ch["adc"] for ch in NL.CHANNELS))


def P(x, y):
    return (x * G, y * G)


def net(ref, num):
    return NETS.parts[ref]["pins"][num]


def two_pin_rot(ref, top_num):
    """Rotation that puts pin top_num of a two-pin part at the top (vertical)."""
    info = NL.kind_info(NETS.parts[ref]["kind"])
    pins = K.symbol_pins(K.LIB.get(info["symbol"]))
    other = next(n for n in pins if n != top_num)
    for r in (0, 90, 180, 270):
        a = K.to_sheet(*pins[top_num][0][:2], r)
        b = K.to_sheet(*pins[other][0][:2], r)
        if abs(a[0] - b[0]) < 0.01 and a[1] < b[1]:
            return r
    raise ValueError(ref)


def horiz_rot(ref, left_num):
    info = NL.kind_info(NETS.parts[ref]["kind"])
    pins = K.symbol_pins(K.LIB.get(info["symbol"]))
    other = next(n for n in pins if n != left_num)
    for r in (0, 90, 180, 270):
        a = K.to_sheet(*pins[left_num][0][:2], r)
        b = K.to_sheet(*pins[other][0][:2], r)
        if abs(a[1] - b[1]) < 0.01 and a[0] < b[0]:
            return r
    raise ValueError(ref)


def pin_on(ref, netname):
    return next(n for n, v in NETS.parts[ref]["pins"].items() if v == netname)


def vert(sh, ref, x, ytop, top_net, side="r"):
    """Vertical two-pin part with the pin on top_net at grid (x, ytop); returns (top, bottom) points."""
    top = pin_on(ref, top_net)
    bot = next(n for n in NETS.parts[ref]["pins"] if n != top)
    pins = sh.place(ref, x * G, (ytop + 1.5) * G, two_pin_rot(ref, top), side=side)
    assert abs(pins[top][1] - ytop * G) < 1e-3, (ref, pins)
    return pins[top], pins[bot], bot


def shunt(sh, ref, x, yrail, top_net, side="r", gap=1):
    """Two-pin part hanging from a rail at yrail; the lower pin to GND or to its own label."""
    top, bottom, bnum = vert(sh, ref, x, yrail + gap, top_net, side)
    sh.w(top, P(x, yrail))
    if net(ref, bnum) == "GND":
        sh.gnd(bottom)
    return top, bottom


def horiz(sh, ref, x, y, left_net, side="a"):
    """Horizontal two-pin part centred at grid (x, y), pin on left_net at the left."""
    left = pin_on(ref, left_net)
    right = next(n for n in NETS.parts[ref]["pins"] if n != left)
    pins = sh.place(ref, x * G, y * G, horiz_rot(ref, left), side=side)
    return pins[left], pins[right]


# ---- power sheet ------------------------------------------------------------------------------
def power_sheet(page):
    sh = K.Sheet("power", NL.SHEETS["power"], page, ROOT_UUID)
    sh.text("Power input, protection and rails", 15, 12, size=2.5, bold=True)

    # Input: XT30 -> P-FET (reverse polarity) -> VBAT bus, TVS, bulk, battery sense
    X, Y = 8, 16
    sh.text("12 V link from the toolbox (battery, BMS, 5 A fuse, main switch). Q101 conducts only with the right "
            "polarity; D101 limits its gate-source voltage; D102 clamps transients (24.4 V at 24.6 A).",
            X * G, (Y - 5) * G)
    j = sh.place("J101", X * G, Y * G, mirror=True, side="l")
    q = sh.place("Q101", (X + 12) * G, (Y + 1) * G, rot=90, side="a")
    sh.w(j["1"], q["5"])
    sh.lab(P(X + 5, Y), "VBAT_IN")
    sh.w(j["2"], P(X + 4, Y + 1), P(X + 4, Y + 3))
    sh.gnd(P(X + 4, Y + 3))
    sh.w(q["4"], P(X + 12, Y + 4))
    rt, rb, _ = vert(sh, "R101", X + 12, Y + 4, "Q101_G", side="l")
    sh.gnd(rb)
    dt, db, _ = vert(sh, "D101", X + 17, Y + 1, "VBAT", side="r")
    sh.w(dt, P(X + 17, Y))
    sh.w(db, P(X + 17, Y + 4), P(X + 12, Y + 4))
    sh.w(q["1"], P(X + 50, Y))                 # VBAT bus
    sh.pwr(P(X + 21, Y), "VBAT")
    shunt(sh, "D102", X + 24, Y, "VBAT")
    shunt(sh, "C101", X + 30, Y, "VBAT")
    shunt(sh, "C102", X + 36, Y, "VBAT")
    t, b = shunt(sh, "R102", X + 42, Y, "VBAT")
    rt, rb, _ = vert(sh, "R103", X + 42, Y + 6, "VBAT_SNS")
    sh.w(b, rt)
    sh.gnd(rb)
    sh.w(P(X + 42, Y + 5), P(X + 46, Y + 5))
    ct, cb, _ = vert(sh, "C103", X + 46, Y + 6, "VBAT_SNS")
    sh.w(P(X + 46, Y + 5), ct)
    sh.gnd(cb)
    sh.lab(P(X + 46, Y + 5), "VBAT_SNS", (1, 0), stub=3 * G)
    sh.place("TP101", (X + 50) * G, Y * G, side="r")
    tp = sh.place("TP102", (X + 7) * G, (Y + 3) * G, side="r")
    sh.gnd(tp["1"])
    k = CA.divider("R102", "R103")
    sh.text(f"VBAT_SNS = VBAT x {k:.4f}\n12.6 V -> {12.6 * k:.2f} V, 9.6 V -> {9.6 * k:.2f} V\n"
            "(ADC1, 0-2.9 V at 12 dB)", (X + 54) * G, (Y + 4) * G)

    # TPS54302 buck (revision A had a second one, U111, for the 6 V actuators; they now run from VBAT)
    base, bx, by = 120, 8, 42
    start, stop = CA.buck_uvlo(base)
    sh.text(f"5 V for logic, lamps, buzzer and expansion: TPS54302, 3 A, 400 kHz. "
            f"Vout = 0.596 V x (1 + R{base + 1}/R{base + 2}) = {CA.buck_vout(base):.3f} V. "
            f"Enable divider R{base + 3}/R{base + 4}: on at {start:.2f} V, off at {stop:.2f} V.",
            bx * G, (by - 5) * G)
    buck(sh, base, "+5V", bx, by)

    # 3.3 V LDO, diode-OR input
    X, Y = 8, 76
    sh.text("3.3 V: AP2112K-3.3 fed from 5 V or from USB VBUS through Schottky diodes (flashing without the "
            "battery; nothing back-feeds the 5 V buck).", X * G, (Y - 6) * G)
    sh.pwr(P(X, Y), "+5V", (-1, 0))
    a, kk = horiz(sh, "D141", X + 3, Y, "+5V", side="a")
    sh.w(P(X, Y), a)
    sh.pwr(P(X, Y + 4), "VBUS", (-1, 0))
    a2, k2 = horiz(sh, "D142", X + 3, Y + 4, "VBUS", side="b")
    sh.w(P(X, Y + 4), a2)
    sh.w(k2, P(X + 6, Y + 4), P(X + 6, Y))
    sh.w(kk, P(X + 18, Y))                  # LDO_IN
    sh.lab(P(X + 7, Y), "LDO_IN")
    shunt(sh, "C141", X + 11, Y, "LDO_IN")
    u = sh.place("U141", (X + 21) * G, (Y + 1) * G, side="ib")
    sh.w(P(X + 18, Y), u["1"])
    sh.w(u["3"], P(X + 16, Y + 1), P(X + 16, Y))
    sh.gnd(u["2"])
    sh.w(u["5"], P(X + 38, Y))              # +3V3
    shunt(sh, "C142", X + 28, Y, "+3V3")
    sh.place("TP141", (X + 33) * G, Y * G, side="r")
    sh.pwr(P(X + 38, Y), "+3V3")

    # VREF
    X, Y = 96, 44
    sh.text(f"VREF = 3.3 V x 10k / 13.3k = {CA.vref():.3f} V, shared by the seven drivers (sets ITRIP).",
            X * G, (Y - 6) * G)
    sh.pwr(P(X, Y - 1), "+3V3")
    t, b, _ = vert(sh, "R151", X, Y - 1, "+3V3")
    t2, b2, _ = vert(sh, "R152", X, Y + 4, "VREF")
    sh.w(b, t2)
    sh.gnd(b2)
    sh.w(P(X, Y + 3), P(X + 6, Y + 3))
    ct, cb, _ = vert(sh, "C151", X + 6, Y + 4, "VREF")
    sh.w(P(X + 6, Y + 3), ct)
    sh.gnd(cb)
    sh.place("TP151", (X + 10) * G, (Y + 3) * G, side="r")
    sh.w(P(X + 6, Y + 3), P(X + 10, Y + 3))
    sh.lab(P(X + 10, Y + 3), "VREF", (1, 0), stub=3 * G)

    X, Y = 96, 66
    sh.text("VBAT bulk at the four actuator drivers (12 V N20 actuators, revision B).", X * G, (Y - 6) * G)
    sh.pwr(P(X, Y - 1), "VBAT")
    sh.w(P(X, Y - 1), P(X + 2, Y - 1))
    shunt(sh, "C130", X + 2, Y - 1, "VBAT")

    # Power flags: these nets are fed by connectors or inductors (passive pins)
    X, Y = 98, 88
    sh.text("ERC power flags (nets fed through connectors, FETs or inductors)", X * G, (Y - 5) * G)
    flags = ["GND", "VBAT", "+5V", "VBUS"]
    for i, n in enumerate(flags):
        p = P(X + i * 5, Y)
        sh.flag(p)
        sh.pwr(P(X + i * 5, Y + 2), n) if n != "GND" else sh.gnd(P(X + i * 5, Y + 2))
        sh.w(p, P(X + i * 5, Y + 2))
    xl = X + len(flags) * 5
    p = P(xl, Y)
    sh.flag(p)
    sh.w(p, P(xl, Y + 2))
    sh.lab(P(xl, Y + 2), "LDO_IN", (0, 1))
    return sh


def buck(sh, b, out, X, Y):
    """TPS54302 cell: VBAT rail at Y, IC, boot cap, inductor, output rail, feedback divider."""
    sh.pwr(P(X, Y), "VBAT")
    sh.w(P(X, Y), P(X + 25, Y))
    for i, r in enumerate((f"C{b + 1}", f"C{b + 2}", f"C{b + 3}")):
        shunt(sh, r, X + 2 + 6 * i, Y, "VBAT")
    en = f"EN_{b}"
    t, bt = shunt(sh, f"R{b + 3}", X + 20, Y, "VBAT", side="r")
    t2, b2, _ = vert(sh, f"R{b + 4}", X + 20, Y + 7, en, side="r")
    sh.w(bt, t2)
    sh.gnd(b2)
    u = sh.place(f"U{b + 1}", (X + 29) * G, (Y + 5) * G, side="ib")
    # VIN (X+25, Y+4), EN (X+25, Y+6), GND (X+29, Y+8), BOOT (X+33, Y+4), SW (X+33, Y+5), FB (X+33, Y+6)
    sh.w(u["3"], P(X + 25, Y))
    sh.w(P(X + 20, Y + 6), u["5"])
    sh.gnd(u["1"])
    # boot capacitor: from BOOT up and over to the switch node
    ct, cb, _ = vert(sh, f"C{b + 4}", X + 35, Y - 1, f"SW_{b}", side="l")
    sh.w(u["6"], P(X + 35, Y + 4), cb)
    sh.w(ct, P(X + 35, Y - 2), P(X + 38, Y - 2), P(X + 38, Y + 5))
    sh.w(u["2"], P(X + 38, Y + 5))
    a, k = horiz(sh, f"L{b + 1}", X + 41, Y + 5, f"SW_{b}", side="a")
    sh.w(P(X + 38, Y + 5), a)
    sh.w(k, P(X + 74, Y + 5))                # output rail
    shunt(sh, f"C{b + 5}", X + 46, Y + 5, out)
    shunt(sh, f"C{b + 6}", X + 52, Y + 5, out)
    fb = f"FB_{b}"
    t, bt = shunt(sh, f"R{b + 1}", X + 58, Y + 5, out, side="r")
    t2, b2, _ = vert(sh, f"R{b + 2}", X + 58, Y + 12, fb, side="r")
    sh.w(bt, t2)
    sh.gnd(b2)
    t3, b3 = shunt(sh, f"C{b + 7}", X + 63, Y + 5, out)
    sh.w(b3, P(X + 63, Y + 11), P(X + 58, Y + 11))
    sh.lab(P(X + 58, Y + 11), fb, (-1, 0), stub=2 * G)
    sh.lab(u["4"], fb, (1, 0), stub=2 * G)
    sh.place(f"TP{b + 1}", (X + 69) * G, (Y + 5) * G, side="r")
    sh.pwr(P(X + 74, Y + 5), out)


# ---- MCU sheet --------------------------------------------------------------------------------
def mcu_sheet(page):
    sh = K.Sheet("mcu", NL.SHEETS["mcu"], page, ROOT_UUID)
    sh.text("ESP32-S3-WROOM-1-N8 (no PSRAM, so GPIO35-37 are free), native USB, indicators", 15, 12, size=2.5,
            bold=True)
    sh.text("Straps: GPIO0 pulled up (hold BOOT at reset for download mode). GPIO45/46 held low by the lamp gate "
            "pull-downs (VDD_SPI 3.3 V, SPI boot).\nGPIO3 (JTAG strap) is ignored with the default eFuse. "
            f"Analog inputs on ADC1 only: GPIO{ADC_LIST} driver currents, GPIO{GP['VBAT_SNS']} battery.\n"
            "Enables and nSLEEP avoid GPIO18/19 (high glitch at power-up) and GPIO0/39/43/44 (pulled up at reset).",
            15, 20)
    X, Y = 62, 50                         # module centre
    u = sh.place("U201", X * G, Y * G, side="ib")
    # 3V3 pin (X, Y-11) up to the +3V3 symbol, decoupling on a short rail to the right
    sh.w(u["2"], P(X, Y - 21))
    sh.pwr(P(X, Y - 21), "+3V3")
    sh.w(P(X, Y - 19), P(X + 12, Y - 19))
    shunt(sh, "C202", X + 4, Y - 19, "+3V3")
    shunt(sh, "C201", X + 12, Y - 19, "+3V3")
    sh.gnd(u["1"])
    # EN (pin at X-6, Y-9): RC delay and RESET button, up and to the left
    sh.w(u["3"], P(X - 9, Y - 9), P(X - 9, Y - 15), P(X - 20, Y - 15))
    sh.pwr(P(X - 26, Y - 19), "+3V3")
    t, b, _ = vert(sh, "R201", X - 26, Y - 19, "+3V3", side="l")
    sh.w(b, P(X - 26, Y - 15), P(X - 20, Y - 15))
    t, b, _ = vert(sh, "C203", X - 22, Y - 14, "ESP_EN", side="r")
    sh.w(P(X - 22, Y - 15), t)
    sh.gnd(b)
    sh.place("SW201", (X - 31) * G, (Y - 15) * G, rot=180, side="a")
    sh.w(P(X - 29, Y - 15), P(X - 26, Y - 15))
    sh.w(P(X - 33, Y - 15), P(X - 34, Y - 15), P(X - 34, Y - 13))
    sh.gnd(P(X - 34, Y - 13))
    sh.text("RESET", (X - 33) * G, (Y - 20) * G)
    # BOOT (GPIO0, pin at X-6, Y-7): pull-up and button
    sh.w(u["27"], P(X - 29, Y - 7))
    sh.pwr(P(X - 17, Y - 12), "+3V3")
    t, b, _ = vert(sh, "R202", X - 17, Y - 12, "+3V3", side="r")
    sh.w(b, P(X - 17, Y - 7))
    sh.place("SW202", (X - 31) * G, (Y - 7) * G, rot=180, side="b")
    sh.w(P(X - 33, Y - 7), P(X - 34, Y - 7), P(X - 34, Y - 5))
    sh.gnd(P(X - 34, Y - 5))
    sh.text("BOOT", (X - 33) * G, (Y - 11) * G)
    # every other module pin: stub and label
    for num in u:
        if num in ("1", "2", "3", "27", "40", "41"):
            continue
        sh.term("U201", num, stub=3 * G)

    # USB-C, ESD and VBUS
    X, Y = 118, 46
    sh.text("USB-C device (flashing, logs): 5.1k on CC1 and CC2; both D+/D- pairs joined; USBLC6 ESD array.",
            (X - 10) * G, (Y - 16) * G)
    j = sh.place("J201", X * G, Y * G, side="ib")
    # right side at X+6: VBUS (Y-6), CC1 (Y-4), CC2 (Y-3), D- A7 (Y-1), D- B7 (Y), D+ A6 (Y+1), D+ B6 (Y+2),
    # SBU1 (Y+5), SBU2 (Y+6); GND (X, Y+9), shield (X-3, Y+9)
    sh.w(j["A4"], P(X + 10, Y - 6), P(X + 10, Y - 10), P(X + 20, Y - 10))
    sh.pwr(P(X + 20, Y - 10), "VBUS")
    shunt(sh, "C204", X + 15, Y - 10, "VBUS")
    sh.w(j["A5"], P(X + 32, Y - 4))
    t, b, _ = vert(sh, "R203", X + 32, Y - 4, "CC1", side="r")
    sh.gnd(b)
    sh.w(j["B5"], P(X + 27, Y - 3))
    t, b, _ = vert(sh, "R204", X + 27, Y - 3, "CC2", side="r")
    sh.gnd(b)
    sh.w(j["A7"], P(X + 12, Y - 1), P(X + 12, Y))
    sh.w(j["B7"], P(X + 16, Y))
    sh.w(j["A6"], P(X + 13, Y + 1), P(X + 13, Y + 2))
    sh.w(j["B6"], P(X + 16, Y + 2))
    sh.lab(P(X + 16, Y), "USB_DN", (1, 0))
    sh.lab(P(X + 16, Y + 2), "USB_DP", (1, 0))
    sh.nc(j["A8"])
    sh.nc(j["B8"])
    sh.w(j["S1"], P(X - 3, Y + 10), P(X, Y + 10))
    sh.w(j["A1"], P(X, Y + 10))
    sh.gnd(P(X, Y + 10))
    # ESD array: I/O1 pins 1/6, I/O2 pins 3/4, VBUS 5, GND 2
    e = sh.place("U202", (X + 26) * G, (Y + 12) * G, side="icr")
    sh.lab(e["1"], "USB_DP", (-1, 0), stub=2 * G)
    sh.lab(e["3"], "USB_DN", (-1, 0), stub=2 * G)
    sh.lab(e["6"], "USB_DP", (1, 0), stub=2 * G)
    sh.lab(e["4"], "USB_DN", (1, 0), stub=2 * G)
    sh.w(e["5"], P(X + 26, Y + 9))
    sh.pwr(P(X + 26, Y + 9), "VBUS")
    sh.gnd(e["2"])

    # Indicators and pull resistors
    X, Y = 84, 84
    sh.text(f"Status LED (GPIO{GP['LED_STAT']}), power LED, shared driver fault pull-up, sleep pull-down, UART0 test pads.",
            (X - 2) * G, (Y - 5) * G)
    sh.lab(P(X, Y - 1), "LED_STAT", (0, -1))
    t, b, _ = vert(sh, "R205", X, Y - 1, "LED_STAT")
    t2, b2, _ = vert(sh, "D201", X, Y + 4, "LED_STAT_A")
    sh.w(b, t2)
    sh.gnd(b2)
    sh.pwr(P(X + 8, Y - 1), "+3V3")
    t, b, _ = vert(sh, "R206", X + 8, Y - 1, "+3V3")
    t2, b2, _ = vert(sh, "D202", X + 8, Y + 4, "LED_PWR_A")
    sh.w(b, t2)
    sh.gnd(b2)
    sh.pwr(P(X + 16, Y - 1), "+3V3")
    t, b, _ = vert(sh, "R207", X + 16, Y - 1, "+3V3")
    sh.lab(b, "NFAULT", (0, 1), stub=1 * G)
    sh.lab(P(X + 24, Y - 1), "NSLEEP", (0, -1))
    t, b, _ = vert(sh, "R208", X + 24, Y - 1, "NSLEEP")
    sh.gnd(b)
    for i, (tp, n) in enumerate((("TP201", "TXD0"), ("TP202", "RXD0"), ("TP203", "NFAULT"), ("TP204", "NSLEEP"))):
        x = X + 32 + i * 6
        p = sh.place(tp, x * G, (Y + 2) * G, side="r")
        sh.lab(p["1"], n, (0, 1), stub=1 * G)
    return sh


# ---- drivers sheet ------------------------------------------------------------------------------
def drivers_sheet(page):
    sh = K.Sheet("drivers", NL.SHEETS["drivers"], page, ROOT_UUID)
    sh.text("Seven DRV8876 H-bridges: PH/EN mode (PMODE = GND), IMODE = GND (fixed off-time 25 us, auto-retry)",
            15, 12, size=2.5, bold=True)
    sh.text(f"ITRIP = VREF / (R_IPROPI x 1000 uA/A), VREF {CA.vref():.3f} V: tracks 2.4k -> "
            f"{CA.itrip(CA.channel('TL')):.3f} A, swing 4.12k -> {CA.itrip(CA.channel('SW')):.3f} A, actuators "
            f"4.99k -> {CA.itrip(CA.channel('BL')):.3f} A. At the limit IPROPI equals VREF, inside the ADC range.\n"
            "The 1k / 100n filter after IPROPI (100 us) smooths the PWM for the ADC without slowing the "
            "driver's own regulation. EN = PWM (0 = brake), PH = direction (1: OUT1 high).", 15, 20)
    for i, ch in enumerate(NL.CHANNELS):
        col, row = i % 3, i // 3
        driver(sh, ch, 300 + 10 * (i + 1), 18 + col * 44, 32 + row * 33)
    return sh


def driver(sh, ch, b, X, Y):
    """One DRV8876 cell; IC centre at grid (X, Y)."""
    k, vm = ch["key"], ch["vm"]
    sh.text(f"{ch['name']}: {vm}, limit {CA.itrip(ch):.2f} A", (X - 13) * G, (Y - 16) * G, size=1.7, bold=True)
    u = sh.place(f"U{b}", X * G, Y * G, side="ib")
    # left: EN (X-6,Y-2) PH (Y-1) nSLEEP (Y) VREF (Y+1) PMODE (Y+3) IMODE (Y+4)
    for num in ("1", "2", "3", "5"):
        sh.term(f"U{b}", num, stub=2 * G)
    sh.w(u["16"], P(X - 8, Y + 3), P(X - 8, Y + 6))
    sh.w(u["7"], P(X - 8, Y + 4))
    sh.gnd(P(X - 8, Y + 6))
    sh.gnd(u["15"])
    # top: CPL (X-4, Y-6), CPH (X-2), VCP (X+2), VM (X+4)
    sh.w(u["11"], P(X + 4, Y - 7), P(X + 8, Y - 7), P(X + 8, Y - 11))
    sh.w(P(X + 2, Y - 11), P(X + 19, Y - 11))
    sh.pwr(P(X + 8, Y - 11), vm)
    t, bt, _ = vert(sh, f"C{b + 3}", X + 2, Y - 10, vm, side="r")
    sh.w(t, P(X + 2, Y - 11))
    sh.w(u["12"], bt)
    shunt(sh, f"C{b + 1}", X + 13, Y - 11, vm)
    shunt(sh, f"C{b + 2}", X + 19, Y - 11, vm)
    t, bt, _ = vert(sh, f"C{b + 4}", X - 7, Y - 11, f"CPH_{k}", side="l")
    sh.w(u["13"], P(X - 2, Y - 12), P(X - 7, Y - 12), t)
    sh.w(u["14"], P(X - 4, Y - 7), P(X - 7, Y - 7), bt)
    # right: OUT1 (X+6, Y-2), OUT2 (Y-1), nFAULT (Y+1), IPROPI (Y+3)
    for num in ("8", "10", "4"):
        sh.term(f"U{b}", num, stub=2 * G)
    sh.w(u["6"], P(X + 9, Y + 3))
    t, bt, _ = vert(sh, f"R{b + 1}", X + 9, Y + 4, f"IPROPI_{k}", side="r")
    sh.w(P(X + 9, Y + 3), t)
    sh.gnd(bt)
    a, kk = horiz(sh, f"R{b + 2}", X + 14, Y + 3, f"IPROPI_{k}", side="b")
    sh.w(P(X + 9, Y + 3), a)
    sh.w(kk, P(X + 19, Y + 3))
    t, bt, _ = vert(sh, f"C{b + 5}", X + 19, Y + 4, f"ISNS_{k}", side="r")
    sh.w(P(X + 19, Y + 3), t)
    sh.gnd(bt)
    sh.lab(P(X + 19, Y + 3), f"ISNS_{k}", (1, 0), stub=2 * G)


# ---- IO sheet -----------------------------------------------------------------------------------
def io_sheet(page):
    sh = K.Sheet("io", NL.SHEETS["io"], page, ROOT_UUID)
    sh.text("Connectors, lamps, buzzer and expansion", 15, 12, size=2.5, bold=True)
    sh.text("Motor connectors (JST-XH, side entry), OUT1/OUT2 of each driver. The tracks share one 4-way plug "
            "from the slip ring (1-2 left, 3-4 right).", 15, 20)
    for i, r in enumerate(["J102", "J103", "J104", "J105", "J106", "J107"]):
        j = sh.place(r, (14 + i * 24) * G, 20 * G, mirror=True, side="l")
        for num in j:
            sh.term(r, num, stub=2 * G)

    # Lamps
    X, Y = 10, 48
    sh.text("Lamps: common 5 V through F401; each return is switched on the low side (PWM).\n"
            "The 100k gate pull-downs keep the lamps off at reset and hold the GPIO45/46 straps low.",
            X * G, (Y - 13) * G)
    j = sh.place("J108", X * G, Y * G, mirror=True, side="l")
    # pins 1 (X+2, Y-1), 2 (X+2, Y), 3 (X+2, Y+1)
    sh.pwr(P(X + 8, Y - 7), "+5V")
    t, bt, _ = vert(sh, "F401", X + 8, Y - 7, "+5V", side="r")
    sh.w(bt, P(X + 8, Y - 1), j["1"])
    sh.lab(P(X + 8, Y - 1), "+5V_LAMP", (1, 0), stub=2 * G)
    for i, (q, rg, rp, sig) in enumerate((("Q401", "R401", "R411", "LAMP1_PWM"), ("Q402", "R402", "R412", "LAMP2_PWM"))):
        qx, qy = X + 20 + i * 24, Y + 7
        qp = sh.place(q, qx * G, qy * G, side="r")
        # G (qx-2, qy), D (qx+1, qy-2), S (qx+1, qy+2)
        if i == 0:
            sh.w(j["2"], P(X + 4, Y), P(X + 4, Y + 3), P(qx + 1, Y + 3), qp["3"])
        else:
            sh.w(j["3"], P(X + 5, Y + 1), P(qx + 1, Y + 1), qp["3"])
        sh.gnd(qp["2"])
        a, kk = horiz(sh, rg, qx - 7, qy, sig, side="a")
        sh.w(kk, qp["1"])
        t, bt, _ = vert(sh, rp, qx - 4, qy + 1, f"LAMP{i + 1}_G", side="r")
        sh.w(P(qx - 4, qy), t)
        sh.gnd(bt)
        sh.lab(a, sig, (-1, 0), stub=2 * G)

    # Buzzer
    X, Y = 80, 48
    sh.text(f"Buzzer: 5 V passive magnetic (32 ohm, 2.7 kHz), GPIO{GP['BUZ_PWM']} PWM at resonance.\n"
            "R420 is a 0 ohm link (fit a resistor to lower the volume); D401 clamps the coil.",
            X * G, (Y - 13) * G)
    sh.pwr(P(X + 8, Y - 6), "+5V")
    t, bt, _ = vert(sh, "R420", X + 8, Y - 6, "+5V", side="r")
    sh.w(bt, P(X + 8, Y + 1))
    bz = sh.place("LS401", (X + 7) * G, (Y + 2) * G, mirror=True, side="l")
    # LS401 + at (X+8, Y+1), - at (X+8, Y+3)
    sh.w(P(X + 8, Y + 1), P(X + 14, Y + 1))
    dt, db, _ = vert(sh, "D401", X + 14, Y + 1, "BUZ_A", side="r")
    sh.w(bz["2"], P(X + 8, Y + 6), P(X + 14, Y + 6), db)
    qp = sh.place("Q403", (X + 7) * G, (Y + 10) * G, side="r")
    # G (X+5, Y+10), D (X+8, Y+8), S (X+8, Y+12)
    sh.w(qp["3"], P(X + 8, Y + 6))
    sh.gnd(qp["2"])
    a, kk = horiz(sh, "R403", X - 2, Y + 10, "BUZ_PWM", side="a")
    sh.w(kk, qp["1"])
    t, bt, _ = vert(sh, "R413", X + 2, Y + 11, "BUZ_G", side="l")
    sh.w(P(X + 2, Y + 10), t)
    sh.gnd(bt)
    sh.lab(a, "BUZ_PWM", (-1, 0), stub=2 * G)

    # Expansion
    X, Y = 12, 86
    sh.text("Expansion (a later serial link, e.g. a 4G stick): 5 V up to 2 A through F402, 3.3 V UART.\n"
            "R422 limits the current if a 5 V device drives RX.", (X - 2) * G, (Y - 13) * G)
    j = sh.place("J109", X * G, Y * G, mirror=True, side="l")
    # pins 1 (X+2, Y-1), 2 (Y), 3 (Y+1), 4 (Y+2)
    sh.pwr(P(X + 8, Y - 7), "+5V")
    t, bt, _ = vert(sh, "F402", X + 8, Y - 7, "+5V", side="r")
    sh.w(bt, P(X + 8, Y - 1), j["1"])
    sh.w(P(X + 8, Y - 1), P(X + 24, Y - 1))
    t, bt2, _ = vert(sh, "C401", X + 24, Y, "+5V_EXP", side="r")
    sh.w(P(X + 24, Y - 1), t)
    sh.gnd(bt2)
    sh.lab(P(X + 15, Y - 1), "+5V_EXP", (1, 0))
    sh.w(j["2"], P(X + 3, Y))
    sh.pwr(P(X + 3, Y), "GND", (1, 0))
    a, kk = horiz(sh, "R421", X + 9, Y + 1, "EXP_TX_C", side="b")
    sh.w(j["3"], a)
    sh.lab(kk, "EXP_TX", (1, 0), stub=2 * G)
    a, kk = horiz(sh, "R422", X + 9, Y + 5, "EXP_RX_C", side="b")
    sh.w(j["4"], P(X + 5, Y + 2), P(X + 5, Y + 5), a)
    sh.lab(kk, "EXP_RX", (1, 0), stub=2 * G)

    sh.text("Mounting: 4 x M2.5 holes on the bay bosses (x1_body.py BOARD).", 62 * G, 74 * G)
    for i, h in enumerate(["H1", "H2", "H3", "H4"]):
        sh.place(h, (64 + i * 7) * G, 80 * G, side="b")
    return sh


# ---- root and files ----------------------------------------------------------------------------
def root_sheet(sheets):
    items = [[S("text"), "X1 main board: ESP32-S3 controller, seven DRV8876 H-bridges, 5 V / 3.3 V rails",
              [S("exclude_from_sim"), S("no")], [S("at"), 20, 25, 0],
              [S("effects"), K.font(2.5, True), [S("justify"), S("left"), S("top")]], [S("uuid"), K.uid("root", "t")]],
             [S("text"), "Requirements: ../SPEC.md (spec C1). Design notes, calculations and sources: DESIGN.md.\n"
                         "Every sheet is generated by source/build_schematic.py from source/netlist.py.",
              [S("exclude_from_sim"), S("no")], [S("at"), 20, 33, 0],
              [S("effects"), K.font(), [S("justify"), S("left"), S("top")]], [S("uuid"), K.uid("root", "t2")]]]
    for i, sh in enumerate(sheets.values()):
        x, y = 25 + (i % 2) * 130, 50 + (i // 2) * 55
        items.append([S("sheet"), [S("at"), x, y], [S("size"), 100, 35], [S("exclude_from_sim"), S("no")],
                      [S("in_bom"), S("yes")], [S("on_board"), S("yes")], [S("dnp"), S("no")],
                      [S("fields_autoplaced"), S("yes")], [S("stroke"), [S("width"), 0.1524], [S("type"), S("solid")]],
                      [S("fill"), [S("color"), 0, 0, 0, 0.0]], [S("uuid"), sh.block_uuid],
                      K.prop("Sheetname", sh.title, (x, y - 0.7, 0), justify=["left", "bottom"]),
                      K.prop("Sheetfile", f"{K.PROJECT}_{sh.key}.kicad_sch", (x, y + 35.6, 0), justify=["left", "top"]),
                      [S("instances"), [S("project"), K.PROJECT, [S("path"), f"/{ROOT_UUID}", [S("page"), str(sh.page)]]]]])
    tb = [S("title_block"), [S("title"), f"{NL.TITLE}, revision {NL.REV}"], [S("date"), K.DATE], [S("rev"), NL.REV],
          [S("company"), "X1 crawler excavator"],
          [S("comment"), 1, "Generated by source/build_schematic.py from source/netlist.py; do not edit by hand"]]
    return [S("kicad_sch"), [S("version"), 20250114], [S("generator"), "eeschema"], [S("generator_version"), "9.0"],
            [S("uuid"), ROOT_UUID], [S("paper"), "A4"], tb, [S("lib_symbols")]] + items + [
        [S("sheet_instances"), [S("path"), "/", [S("page"), "1"]]], [S("embedded_fonts"), S("no")]]


def main():
    KDIR.mkdir(parents=True, exist_ok=True)
    syms = K.init()
    builders = dict(power=power_sheet, mcu=mcu_sheet, drivers=drivers_sheet, io=io_sheet)
    sheets = {}
    for i, key in enumerate(NL.SHEETS):
        sh = builders[key](i + 2)
        sh.finish()
        sheets[key] = sh
    placed = [r for sh in sheets.values() for r in sh.placed]
    missing = sorted(set(NETS.parts) - set(placed))
    dup = sorted({r for r in placed if placed.count(r) > 1})
    wrong_sheet = sorted(r for sh in sheets.values() for r in sh.placed if NETS.parts[r]["sheet"] != sh.key)
    if missing or dup or wrong_sheet:
        sys.exit(f"not placed: {missing}; placed twice: {dup}; on the wrong sheet: {wrong_sheet}")
    for key, sh in sheets.items():
        (KDIR / f"{K.PROJECT}_{key}.kicad_sch").write_text(sexp.dump(sh.sexpr()) + "\n")
    (KDIR / f"{K.PROJECT}.kicad_sch").write_text(sexp.dump(root_sheet(sheets)) + "\n")
    lib = [S("kicad_symbol_lib"), [S("version"), 20241209], [S("generator"), "x1_build_schematic"],
           [S("generator_version"), "9.0"]] + list(syms.values())
    (KDIR / f"{K.PROJECT}.kicad_sym").write_text(sexp.dump(lib) + "\n")
    # the project file also holds the board's rules and net classes (written by build_pcb.py): keep them
    pro_path = KDIR / f"{K.PROJECT}.kicad_pro"
    pro = json.loads(pro_path.read_text()) if pro_path.exists() else {}
    pro.setdefault("meta", {"filename": f"{K.PROJECT}.kicad_pro", "version": 3})
    pro["sheets"] = [[ROOT_UUID, "Root"]] + [[sh.block_uuid, sh.title] for sh in sheets.values()]
    pro.setdefault("text_variables", {})
    pro_path.write_text(json.dumps(pro, indent=2) + "\n")
    (KDIR / "sym-lib-table").write_text(
        '(sym_lib_table\n  (version 7)\n  (lib (name "X1_main")(type "KiCad")(uri "${KIPRJMOD}/X1_main.kicad_sym")'
        '(options "")(descr "X1 main board project symbols"))\n)\n')
    print(f"wrote {len(sheets) + 1} schematic files, {len(placed)} parts placed")


if __name__ == "__main__":
    main()

"""X1 main board, revision B: parts, pins and nets (the single source of truth).

Everything downstream reads this module: the KiCad schematic generator, the design checks, the BOM,
the PCB and the firmware pin map. Pin numbers are the footprint pad numbers, which match the KiCad
library symbols used for each part (checked by build_schematic.py against the libraries).

Datasheet facts used here are quoted in DESIGN.md with their source and page.

    python netlist.py   -> prints a summary and runs the netlist rules (exit 1 on any failure)
"""
from collections import OrderedDict, defaultdict
import sys

REV = "B"                # B: the arm actuators are 12 V N20 motors on VBAT; the 6 V buck is gone
TITLE = "X1 main board"

# ---- part kinds ------------------------------------------------------------------------------
# kind -> value, KiCad symbol, KiCad footprint, MPN, LCSC, height (mm), rating
# Footprints are confirmed against the KiCad 9 libraries by build_schematic.py; LCSC numbers
# against LCSC/JLCPCB pages (PARTS_SOURCES.md). "rating" is used by the voltage-rating rule.
KINDS = {
    # --- ICs and modules
    "ESP32": dict(value="ESP32-S3-WROOM-1-N8", symbol="RF_Module:ESP32-S3-WROOM-1",
                  footprint="X1_main:ESP32-S3-WROOM-1_X1", mpn="Espressif ESP32-S3-WROOM-1-N8",
                  lcsc="C2913198", height=3.1, rating=3.6),
    "DRV8876": dict(value="DRV8876PWPR", symbol="X1_main:DRV8876PWP",
                    footprint="Package_SO:HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm_Mask2.46x2.31mm_ThermalVias",
                    mpn="TI DRV8876PWPR", lcsc="C575551", height=1.2, rating=37.0),
    "TPS54302": dict(value="TPS54302DDCR", symbol="Regulator_Switching:TPS54302",
                     footprint="Package_TO_SOT_SMD:SOT-23-6", mpn="TI TPS54302DDCR", lcsc="C311983",
                     height=1.1, rating=28.0),
    "AP2112": dict(value="AP2112K-3.3", symbol="Regulator_Linear:AP2112K-3.3",
                   footprint="Package_TO_SOT_SMD:SOT-23-5", mpn="Diodes AP2112K-3.3TRG1", lcsc="C51118",
                   height=1.45, rating=6.0),
    "USBLC6": dict(value="USBLC6-2SC6", symbol="Power_Protection:USBLC6-2SC6",
                   footprint="Package_TO_SOT_SMD:SOT-23-6", mpn="ST USBLC6-2SC6", lcsc="C7519",
                   height=1.45, rating=6.0),
    # --- discrete semiconductors
    "AO4407A": dict(value="AO4407A", symbol="X1_main:AO4407A", footprint="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
                    mpn="AOS AO4407A", lcsc="C16072", height=1.75, rating=30.0),
    "AO3400A": dict(value="AO3400A", symbol="Transistor_FET:AO3400A", footprint="Package_TO_SOT_SMD:SOT-23",
                    mpn="AOS AO3400A", lcsc="C20917", height=1.25, rating=30.0),
    "SMBJ15A": dict(value="SMBJ15A", symbol="X1_main:SMBJ15A", footprint="Diode_SMD:D_SMB",
                    mpn="Littelfuse SMBJ15A (unidirectional)", lcsc="C83846", height=2.3, rating=15.0),
    "BZT52C12": dict(value="BZT52C12", symbol="Device:D_Zener", footprint="Diode_SMD:D_SOD-123",
                     mpn="JSCJ BZT52C12", lcsc="C43491", height=1.35, rating=12.0),
    "B5819W": dict(value="B5819W", symbol="Device:D_Schottky", footprint="Diode_SMD:D_SOD-123",
                   mpn="JSCJ B5819W SL", lcsc="C8598", height=1.35, rating=40.0),
    "LED_G": dict(value="green", symbol="Device:LED", footprint="LED_SMD:LED_0805_2012Metric",
                  mpn="Hubei KENTO KT-0805G", lcsc="C2297", height=0.8, rating=5.0),
    "LED_R": dict(value="red", symbol="Device:LED", footprint="LED_SMD:LED_0603_1608Metric",
                  mpn="Hubei KENTO KT-0603R", lcsc="C2286", height=0.8, rating=5.0),
    # --- passives (rating = volts for capacitors)
    "L10U": dict(value="10µH", symbol="Device:L", footprint="Inductor_SMD:L_Bourns_SRP6060FA",
                 mpn="Bourns SRP6060FA-100M", lcsc="C2046759", height=6.0, rating=None),
    "CP220": dict(value="220µ 35V", symbol="Device:C_Polarized", footprint="Capacitor_SMD:CP_Elec_8x10.5",
                  mpn="Nichicon UCD1V221MNL1GS", lcsc="C136294", height=10.5, rating=35.0),
    "C22U": dict(value="22µ 25V", symbol="Device:C", footprint="Capacitor_SMD:C_1206_3216Metric",
                 mpn="Samsung CL31A226KAHNNNE", lcsc="C12891", height=1.6, rating=25.0),
    "C10U": dict(value="10µ 25V", symbol="Device:C", footprint="Capacitor_SMD:C_0805_2012Metric",
                 mpn="Samsung CL21A106KAYNNNE", lcsc="C15850", height=1.25, rating=25.0),
    "C1U": dict(value="1µ 50V", symbol="Device:C", footprint="Capacitor_SMD:C_0603_1608Metric",
                mpn="Samsung CL10A105KB8NNNC", lcsc="C15849", height=0.9, rating=50.0),
    "C100N": dict(value="100n 50V", symbol="Device:C", footprint="Capacitor_SMD:C_0603_1608Metric",
                  mpn="Yageo CC0603KRX7R9BB104", lcsc="C14663", height=0.9, rating=50.0),
    "C22N": dict(value="22n 50V", symbol="Device:C", footprint="Capacitor_SMD:C_0603_1608Metric",
                 mpn="Samsung CL10B223KB8NNNC", lcsc="C21122", height=0.9, rating=50.0),
    "C68P": dict(value="68p C0G", symbol="Device:C", footprint="Capacitor_SMD:C_0603_1608Metric",
                 mpn="Samsung CL10C680JB8NNNC", lcsc="C28262", height=0.9, rating=50.0),
    "PTC2A": dict(value="2A PTC", symbol="Device:Polyfuse", footprint="Fuse:Fuse_1812_4532Metric",
                  mpn="BHFUSE BSMD1812-200-16V", lcsc="C883156", height=1.0, rating=16.0),
    "PTC05A": dict(value="0.5A PTC", symbol="Device:Polyfuse", footprint="Fuse:Fuse_1206_3216Metric",
                   mpn="BHFUSE BSMD1206-050-16V", lcsc="C883124", height=1.0, rating=16.0),
    "BUZ": dict(value="5V 2.7kHz", symbol="Device:Buzzer", footprint="X1_main:Buzzer_XHXDZ_8530",
                mpn="XHXDZ SMD8530-32Ω (5 V passive, 32 Ω)", lcsc="C49246949", height=3.0, rating=6.0),
    "SW": dict(value="SW_Push", symbol="Switch:SW_Push", footprint="Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A",
               mpn="XKB TS-1187A-B-A-B", lcsc="C318884", height=1.5, rating=12.0),
    # --- connectors
    "XT30": dict(value="XT30PW-M", symbol="Connector_Generic:Conn_01x02",
                 footprint="Connector_AMASS:AMASS_XT30PW-M_1x02_P2.50mm_Horizontal", mpn="Amass XT30PW-M30.G.Y",
                 lcsc="C431092", height=5.2, rating=30.0),
    "XH2": dict(value="XH 2p", symbol="Connector_Generic:Conn_01x02",
                footprint="Connector_JST:JST_XH_S2B-XH-A_1x02_P2.50mm_Horizontal", mpn="JST S2B-XH-A(LF)(SN)",
                lcsc="C157931", height=6.1, rating=250.0),
    "XH4": dict(value="XH 4p", symbol="Connector_Generic:Conn_01x04",
                footprint="Connector_JST:JST_XH_S4B-XH-A_1x04_P2.50mm_Horizontal", mpn="JST S4B-XH-A(LF)(SN)",
                lcsc="C157925", height=6.1, rating=250.0),
    "PH3": dict(value="PH 3p", symbol="Connector_Generic:Conn_01x03",
                footprint="Connector_JST:JST_PH_S3B-PH-K_1x03_P2.00mm_Horizontal", mpn="JST S3B-PH-K-S(LF)(SN)",
                lcsc="C157929", height=4.8, rating=100.0),
    "PH4": dict(value="PH 4p", symbol="Connector_Generic:Conn_01x04",
                footprint="Connector_JST:JST_PH_S4B-PH-K_1x04_P2.00mm_Horizontal", mpn="JST S4B-PH-K-S(LF)(SN)",
                lcsc="C157926", height=4.8, rating=100.0),
    "USBC": dict(value="USB-C", symbol="Connector:USB_C_Receptacle_USB2.0_16P",
                 footprint="Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", mpn="Korean Hroparts TYPE-C-31-M-12",
                 lcsc="C165948", height=3.26, rating=20.0),
    "TP": dict(value="TP", symbol="Connector:TestPoint", footprint="TestPoint:TestPoint_Pad_D1.5mm",
               mpn="test pad (copper only)", lcsc=None, height=0.0, rating=None),
    "HOLE": dict(value="M2.5", symbol="Mechanical:MountingHole", footprint="MountingHole:MountingHole_2.7mm_M2.5",
                 mpn="mounting hole", lcsc=None, height=0.0, rating=None),
}


def _r(ohms):
    """Resistor kind for a value in ohms (0603, 1 %)."""
    return ("R", ohms)


R_LCSC = {  # 0603 1 % UNI-ROYAL 0603WAF resistors (PARTS_SOURCES.md); all Basic except where noted
    0: "C21189", 100: "C22775", 1e3: "C21190", 2.4e3: "C22940", 3.3e3: "C22978", 4.12e3: "C23041",
    4.99e3: "C23046", 5.1e3: "C23186", 10e3: "C25804", 11e3: "C25950", 13.3e3: "C25952", 22e3: "C31850",
    100e3: "C25803",
}
R_NOT_BASIC = {4.12e3: "Extended", 11e3: "Preferred Extended", 13.3e3: "Extended"}


def r_value_text(ohms):
    """Compact schematic value: 0R, 100R, 4.99k, 100k."""
    if ohms == 0:
        return "0R"
    if ohms >= 1e6:
        return f"{ohms / 1e6:g}M"
    if ohms >= 1e3:
        return f"{ohms / 1e3:g}k"
    return f"{ohms:g}R"


def kind_info(kind):
    if isinstance(kind, tuple) and kind[0] == "R":
        ohms = kind[1]
        return dict(value=r_value_text(ohms), symbol="Device:R", footprint="Resistor_SMD:R_0603_1608Metric",
                    mpn=f"UNI-ROYAL 0603WAF, {r_value_text(ohms)} 1 %", lcsc=R_LCSC.get(ohms, "TBD"), height=0.5,
                    rating=75.0, ohms=ohms)
    return KINDS[kind]


# ---- ESP32-S3-WROOM-1 module pads (datasheet v1.8, Table 3-1) ----------------------------------
WROOM_PAD = {  # GPIO -> module pad
    4: 4, 5: 5, 6: 6, 7: 7, 15: 8, 16: 9, 17: 10, 18: 11, 8: 12, 19: 13, 20: 14, 3: 15, 46: 16, 9: 17,
    10: 18, 11: 19, 12: 20, 13: 21, 14: 22, 21: 23, 47: 24, 48: 25, 45: 26, 0: 27, 35: 28, 36: 29,
    37: 30, 38: 31, 39: 32, 40: 33, 41: 34, 42: 35, 44: 36, 43: 37, 2: 38, 1: 39,
}
ADC1_GPIO = set(range(1, 11))            # ADC1_CH0..CH9; ADC2 is shared with Wi-Fi, not used
STRAP_GPIO = {0, 3, 45, 46}
RESET_PULLUP_GPIO = {0, 39, 43, 44}      # weak pull-up at reset (GPIO39 = MTCK, default eFuse)
HIGH_GLITCH_GPIO = {18, 19}              # high-level glitch at power-up (chip datasheet Table 2-2)

# ---- motor channels -------------------------------------------------------------------------
# key, name, supply, IPROPI resistor, connector ref and pins (OUT1, OUT2), EN gpio, PH gpio, ADC gpio
CHANNELS = [   # GPIOs chosen by where the module pad faces the channel's driver (DESIGN.md, PCB layout)
    dict(key="TL", name="Track left", vm="VBAT", r_ipropi=2.4e3, conn=("J102", 1, 2), en=35, ph=36, adc=1),
    dict(key="TR", name="Track right", vm="VBAT", r_ipropi=2.4e3, conn=("J102", 3, 4), en=37, ph=38, adc=2),
    dict(key="SW", name="Swing", vm="VBAT", r_ipropi=4.12e3, conn=("J103", 1, 2), en=15, ph=16, adc=5),
    dict(key="BL", name="Boom left", vm="VBAT", r_ipropi=4.99e3, conn=("J104", 1, 2), en=21, ph=47, adc=10),
    dict(key="BR", name="Boom right", vm="VBAT", r_ipropi=4.99e3, conn=("J105", 1, 2), en=13, ph=14, adc=9),
    dict(key="ST", name="Stick", vm="VBAT", r_ipropi=4.99e3, conn=("J106", 1, 2), en=11, ph=12, adc=3),
    dict(key="BK", name="Bucket", vm="VBAT", r_ipropi=4.99e3, conn=("J107", 1, 2), en=17, ph=18, adc=6),
]
LIMIT_TARGET_A = dict(TL=1.0, TR=1.0, SW=0.6, BL=0.5, BR=0.5, ST=0.5, BK=0.5)   # SPEC.md M2

# Other signals on the module (GPIO -> net)
GPIO_MISC = OrderedDict([
    (8, "VBAT_SNS"), (4, "BUZ_PWM"), (48, "NSLEEP"), (39, "NFAULT"), (40, "LED_STAT"),
    (41, "EXP_TX"), (42, "EXP_RX"), (45, "LAMP1_PWM"), (46, "LAMP2_PWM"), (0, "BOOT"),
    (19, "USB_DN"), (20, "USB_DP"), (43, "TXD0"), (44, "RXD0"),
])

# Net voltage ceilings (V) for the rating rule: normal maximum, and transient (TVS clamp) maximum.
NET_VMAX = {"VBAT_IN": 12.6, "VBAT": 12.6, "+5V": 5.2, "+5V_EXP": 5.2, "+5V_LAMP": 5.2,
            "VBUS": 5.25, "+3V3": 3.4, "LDO_IN": 5.25, "VREF": 2.6}
VBAT_TRANSIENT = 24.4   # SMBJ15A clamping voltage at Ipp (PARTS_SOURCES.md)

SHEETS = OrderedDict([
    ("power", "Power input and rails"),
    ("mcu", "ESP32-S3, USB and indicators"),
    ("drivers", "Motor drivers"),
    ("io", "Connectors, lamps, buzzer and expansion"),
])


class Netlist:
    def __init__(self):
        self.parts = OrderedDict()   # ref -> dict(kind, pins{pad: net}, role, sheet, dnp)

    def add(self, ref, kind, pins, role, sheet, dnp=False):
        assert ref not in self.parts, ref
        assert sheet in SHEETS, sheet
        self.parts[ref] = dict(kind=kind, pins={str(k): v for k, v in pins.items()}, role=role, sheet=sheet,
                               dnp=dnp)

    def nets(self):
        out = defaultdict(list)
        for ref, p in self.parts.items():
            for pad, net in p["pins"].items():
                if net is not None:
                    out[net].append((ref, pad))
        return dict(out)

    def info(self, ref):
        return kind_info(self.parts[ref]["kind"])


def build():
    n = Netlist()
    R = _r

    # ---------------- sheet 1: power -----------------------------------------------------------
    s = "power"
    n.add("J101", "XT30", {1: "VBAT_IN", 2: "GND"}, "12 V link from the toolbox (battery, fuse, switch)", s)
    # Reverse-polarity P-FET: drain to the input, source to the protected bus, gate pulled to GND.
    n.add("Q101", "AO4407A", {1: "VBAT", 2: "VBAT", 3: "VBAT", 4: "Q101_G", 5: "VBAT_IN", 6: "VBAT_IN",
                              7: "VBAT_IN", 8: "VBAT_IN"}, "reverse-polarity protection", s)
    n.add("R101", R(100e3), {1: "Q101_G", 2: "GND"}, "Q101 gate pull-down", s)
    n.add("D101", "BZT52C12", {1: "VBAT", 2: "Q101_G"}, "Q101 gate-source clamp, 12 V", s)
    n.add("D102", "SMBJ15A", {1: "VBAT", 2: "GND"}, "transient clamp on the 12 V bus", s)
    n.add("C101", "CP220", {1: "VBAT", 2: "GND"}, "bulk, motor bus", s)
    n.add("C102", "C10U", {1: "VBAT", 2: "GND"}, "bus decoupling", s)
    n.add("R102", R(100e3), {1: "VBAT", 2: "VBAT_SNS"}, "battery sense, upper", s)
    n.add("R103", R(22e3), {1: "VBAT_SNS", 2: "GND"}, "battery sense, lower", s)
    n.add("C103", "C100N", {1: "VBAT_SNS", 2: "GND"}, "battery sense filter", s)
    n.add("TP101", "TP", {1: "VBAT"}, "test: VBAT", s)
    n.add("TP102", "TP", {1: "GND"}, "test: GND", s)

    # TPS54302 buck: 5 V for logic, lamps and expansion. (Revision A had a second one, U111, for 6 V
    # actuators; the arm's V6 actuators now use the 12 V N20 motor and run from VBAT like the tracks.)
    for base, out, rbot, label in ((120, "+5V", 13.3e3, "5 V"),):
        u, sw, fb, en, bst = f"U{base + 1}", f"SW_{base}", f"FB_{base}", f"EN_{base}", f"BST_{base}"
        n.add(u, "TPS54302", {1: "GND", 2: sw, 3: "VBAT", 4: fb, 5: en, 6: bst}, f"{label} 3 A buck", s)
        n.add(f"C{base + 1}", "C10U", {1: "VBAT", 2: "GND"}, f"{label} buck input", s)
        n.add(f"C{base + 2}", "C10U", {1: "VBAT", 2: "GND"}, f"{label} buck input", s)
        n.add(f"C{base + 3}", "C100N", {1: "VBAT", 2: "GND"}, f"{label} buck input, HF", s)
        n.add(f"C{base + 4}", "C100N", {1: bst, 2: sw}, f"{label} bootstrap", s)
        n.add(f"L{base + 1}", "L10U", {1: sw, 2: out}, f"{label} inductor", s)
        n.add(f"C{base + 5}", "C22U", {1: out, 2: "GND"}, f"{label} output", s)
        n.add(f"C{base + 6}", "C22U", {1: out, 2: "GND"}, f"{label} output", s)
        n.add(f"R{base + 1}", R(100e3), {1: out, 2: fb}, f"{label} feedback, upper", s)
        n.add(f"R{base + 2}", R(rbot), {1: fb, 2: "GND"}, f"{label} feedback, lower", s)
        n.add(f"C{base + 7}", "C68P", {1: out, 2: fb}, f"{label} feed-forward", s)
        n.add(f"R{base + 3}", R(100e3), {1: "VBAT", 2: en}, f"{label} enable / UVLO, upper", s)
        n.add(f"R{base + 4}", R(22e3), {1: en, 2: "GND"}, f"{label} enable / UVLO, lower", s)
        n.add(f"TP{base + 1}", "TP", {1: out}, f"test: {out}", s)
    n.add("C130", "C22U", {1: "VBAT", 2: "GND"}, "VBAT bulk at the four actuator drivers", s)

    # 3.3 V: LDO fed from 5 V or from USB VBUS through Schottky diodes (flashing with no battery,
    # and no back-feed into the synchronous buck).
    n.add("D141", "B5819W", {1: "LDO_IN", 2: "+5V"}, "5 V into the LDO", s)
    n.add("D142", "B5819W", {1: "LDO_IN", 2: "VBUS"}, "USB VBUS into the LDO", s)
    n.add("C141", "C10U", {1: "LDO_IN", 2: "GND"}, "LDO input", s)
    n.add("U141", "AP2112", {1: "LDO_IN", 2: "GND", 3: "LDO_IN", 4: None, 5: "+3V3"}, "3.3 V LDO, 600 mA", s)
    n.add("C142", "C10U", {1: "+3V3", 2: "GND"}, "LDO output", s)
    n.add("TP141", "TP", {1: "+3V3"}, "test: +3V3", s)
    # Shared current-limit reference for all seven drivers.
    n.add("R151", R(3.3e3), {1: "+3V3", 2: "VREF"}, "VREF divider, upper", s)
    n.add("R152", R(10e3), {1: "VREF", 2: "GND"}, "VREF divider, lower", s)
    n.add("C151", "C100N", {1: "VREF", 2: "GND"}, "VREF filter", s)
    n.add("TP151", "TP", {1: "VREF"}, "test: VREF", s)

    # ---------------- sheet 2: MCU ---------------------------------------------------------------
    s = "mcu"
    pins = {1: "GND", 2: "+3V3", 3: "ESP_EN", 40: "GND", 41: "GND"}
    for ch in CHANNELS:
        pins[WROOM_PAD[ch["en"]]] = f"EN_{ch['key']}"
        pins[WROOM_PAD[ch["ph"]]] = f"PH_{ch['key']}"
        pins[WROOM_PAD[ch["adc"]]] = f"ISNS_{ch['key']}"
    for gpio, net in GPIO_MISC.items():
        pins[WROOM_PAD[gpio]] = net
    used = set(pins)
    for gpio, pad in WROOM_PAD.items():
        if pad not in used:
            pins[pad] = None   # unused GPIO, left open (no-connect flag in the schematic)
    n.add("U201", "ESP32", pins, "controller, ESP-NOW link", s)
    n.add("C201", "C22U", {1: "+3V3", 2: "GND"}, "module supply bulk (Espressif ref. 22 µF)", s)
    n.add("C202", "C100N", {1: "+3V3", 2: "GND"}, "module supply decoupling", s)
    n.add("R201", R(10e3), {1: "+3V3", 2: "ESP_EN"}, "EN pull-up (RC delay with C203)", s)
    n.add("C203", "C1U", {1: "ESP_EN", 2: "GND"}, "EN delay, 10 kΩ × 1 µF", s)
    n.add("SW201", "SW", {1: "ESP_EN", 2: "GND"}, "RESET", s)
    n.add("R202", R(10e3), {1: "+3V3", 2: "BOOT"}, "GPIO0 pull-up", s)
    n.add("SW202", "SW", {1: "BOOT", 2: "GND"}, "BOOT (held at reset: download mode)", s)
    # USB-C, device only: 5.1 k pull-downs on CC, both D+/D- pairs joined, ESD array.
    n.add("J201", "USBC", {"A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "A4": "VBUS", "A9": "VBUS",
                           "B4": "VBUS", "B9": "VBUS", "A5": "CC1", "B5": "CC2", "A6": "USB_DP", "B6": "USB_DP",
                           "A7": "USB_DN", "B7": "USB_DN", "A8": None, "B8": None, "S1": "GND"},
          "USB-C: flashing and logs (native USB)", s)
    n.add("R203", R(5.1e3), {1: "CC1", 2: "GND"}, "CC1 sink pull-down", s)
    n.add("R204", R(5.1e3), {1: "CC2", 2: "GND"}, "CC2 sink pull-down", s)
    n.add("U202", "USBLC6", {1: "USB_DP", 2: "GND", 3: "USB_DN", 4: "USB_DN", 5: "VBUS", 6: "USB_DP"},
          "USB ESD protection", s)
    n.add("C204", "C1U", {1: "VBUS", 2: "GND"}, "VBUS decoupling", s)
    n.add("R205", R(1e3), {1: "LED_STAT", 2: "LED_STAT_A"}, "status LED resistor", s)
    n.add("D201", "LED_G", {1: "GND", 2: "LED_STAT_A"}, "status LED (link, arm state)", s)
    n.add("R206", R(1e3), {1: "+3V3", 2: "LED_PWR_A"}, "power LED resistor", s)
    n.add("D202", "LED_R", {1: "GND", 2: "LED_PWR_A"}, "3.3 V power LED", s)
    n.add("R207", R(10e3), {1: "+3V3", 2: "NFAULT"}, "shared driver fault line pull-up", s)
    n.add("R208", R(100e3), {1: "NSLEEP", 2: "GND"}, "drivers asleep until firmware arms", s)
    n.add("TP201", "TP", {1: "TXD0"}, "test: UART0 TX (boot log)", s)
    n.add("TP202", "TP", {1: "RXD0"}, "test: UART0 RX", s)
    n.add("TP203", "TP", {1: "NFAULT"}, "test: nFAULT", s)
    n.add("TP204", "TP", {1: "NSLEEP"}, "test: nSLEEP", s)

    # ---------------- sheet 3: motor drivers (one cell per channel) ------------------------------
    s = "drivers"
    for i, ch in enumerate(CHANNELS, start=1):
        k, vm, b = ch["key"], ch["vm"], 300 + 10 * i
        n.add(f"U{b}", "DRV8876", {1: f"EN_{k}", 2: f"PH_{k}", 3: "NSLEEP", 4: "NFAULT", 5: "VREF",
                                   6: f"IPROPI_{k}", 7: "GND", 8: f"OUT1_{k}", 9: "GND", 10: f"OUT2_{k}",
                                   11: vm, 12: f"VCP_{k}", 13: f"CPH_{k}", 14: f"CPL_{k}", 15: "GND",
                                   16: "GND", 17: "GND"},
              f"{ch['name']} H-bridge (PH/EN, IMODE = GND: fixed off-time, auto-retry)", s)
        n.add(f"C{b + 1}", "C100N", {1: vm, 2: "GND"}, f"{ch['name']}: VM decoupling", s)
        n.add(f"C{b + 2}", "C10U", {1: vm, 2: "GND"}, f"{ch['name']}: VM local bulk", s)
        n.add(f"C{b + 3}", "C100N", {1: f"VCP_{k}", 2: vm}, f"{ch['name']}: charge pump VCP", s)
        n.add(f"C{b + 4}", "C22N", {1: f"CPH_{k}", 2: f"CPL_{k}"}, f"{ch['name']}: charge pump flying cap", s)
        n.add(f"R{b + 1}", R(ch["r_ipropi"]), {1: f"IPROPI_{k}", 2: "GND"},
              f"{ch['name']}: IPROPI, sets the {LIMIT_TARGET_A[k]} A limit", s)
        n.add(f"R{b + 2}", R(1e3), {1: f"IPROPI_{k}", 2: f"ISNS_{k}"}, f"{ch['name']}: ADC filter", s)
        n.add(f"C{b + 5}", "C100N", {1: f"ISNS_{k}", 2: "GND"}, f"{ch['name']}: ADC filter, 100 µs", s)

    # ---------------- sheet 4: connectors and outputs ---------------------------------------------
    s = "io"
    n.add("J102", "XH4", {1: "OUT1_TL", 2: "OUT2_TL", 3: "OUT1_TR", 4: "OUT2_TR"},
          "tracks, from the slip ring (1-2 left, 3-4 right)", s)
    n.add("J103", "XH2", {1: "OUT1_SW", 2: "OUT2_SW"}, "swing motor", s)
    n.add("J104", "XH2", {1: "OUT1_BL", 2: "OUT2_BL"}, "boom cylinder, left", s)
    n.add("J105", "XH2", {1: "OUT1_BR", 2: "OUT2_BR"}, "boom cylinder, right", s)
    n.add("J106", "XH2", {1: "OUT1_ST", 2: "OUT2_ST"}, "stick cylinder", s)
    n.add("J107", "XH2", {1: "OUT1_BK", 2: "OUT2_BK"}, "bucket cylinder", s)
    # Lamps: common 5 V through a PTC, each return switched on the low side.
    n.add("F401", "PTC05A", {1: "+5V", 2: "+5V_LAMP"}, "lamp supply protection", s)
    n.add("J108", "PH3", {1: "+5V_LAMP", 2: "LAMP1_K", 3: "LAMP2_K"}, "lamps: 5 V, lamp 1 return, lamp 2 return", s)
    for i, (sig, ret) in enumerate((("LAMP1_PWM", "LAMP1_K"), ("LAMP2_PWM", "LAMP2_K")), start=1):
        q, g = f"Q40{i}", f"LAMP{i}_G"
        n.add(q, "AO3400A", {1: g, 2: "GND", 3: ret}, f"lamp {i} low-side switch", s)
        n.add(f"R40{i}", R(100), {1: sig, 2: g}, f"lamp {i} gate resistor", s)
        n.add(f"R41{i}", R(100e3), {1: g, 2: "GND"}, f"lamp {i} gate pull-down (holds GPIO4{4 + i} strap low)", s)
    # Buzzer: low-side switch with a flyback diode; series resistor sized in DESIGN.md.
    n.add("Q403", "AO3400A", {1: "BUZ_G", 2: "GND", 3: "BUZ_K"}, "buzzer low-side switch", s)
    n.add("R403", R(100), {1: "BUZ_PWM", 2: "BUZ_G"}, "buzzer gate resistor", s)
    n.add("R413", R(100e3), {1: "BUZ_G", 2: "GND"}, "buzzer gate pull-down", s)
    n.add("LS401", "BUZ", {1: "BUZ_A", 2: "BUZ_K"}, "travel alarm and warnings", s)
    n.add("R420", R(0), {1: "+5V", 2: "BUZ_A"}, "buzzer series link (0 Ω; a resistor here lowers the volume)", s)
    n.add("D401", "B5819W", {1: "BUZ_A", 2: "BUZ_K"}, "buzzer flyback", s)
    # Expansion: later serial link (4G stick); 5 V up to 2 A.
    n.add("F402", "PTC2A", {1: "+5V", 2: "+5V_EXP"}, "expansion supply protection, 2 A", s)
    n.add("J109", "PH4", {1: "+5V_EXP", 2: "GND", 3: "EXP_TX_C", 4: "EXP_RX_C"},
          "expansion: 5 V, GND, TX, RX (3.3 V UART)", s)
    n.add("R421", R(100), {1: "EXP_TX", 2: "EXP_TX_C"}, "expansion TX series resistor", s)
    n.add("R422", R(1e3), {1: "EXP_RX_C", 2: "EXP_RX"}, "expansion RX series resistor (limits a 5 V source)", s)
    n.add("C401", "C10U", {1: "+5V_EXP", 2: "GND"}, "expansion supply decoupling", s)
    for i, (x, y) in enumerate(((-132, 144), (-44, 144), (-44, 88), (-132, 88)), start=1):
        n.add(f"H{i}", "HOLE", {}, f"mounting hole on boss ({x}, {y})", s)
    return n


# ---- netlist rules --------------------------------------------------------------------------
def rules(n):
    """ERC-like checks on the netlist itself. Returns a list of (name, ok, detail)."""
    out = []
    nets = n.nets()
    single = [k for k, v in nets.items() if len(v) < 2 and not any(n.parts[r]["kind"] == "TP" for r, _ in v)]
    out.append(("every net joins at least two pins", not single, single or "ok"))

    # GPIO plan
    gpio_use = {}
    for ch in CHANNELS:
        for role in ("en", "ph", "adc"):
            gpio_use.setdefault(ch[role], []).append(f"{ch['key']}.{role}")
    for g, net in GPIO_MISC.items():
        gpio_use.setdefault(g, []).append(net)
    dup = {g: u for g, u in gpio_use.items() if len(u) > 1}
    out.append(("each GPIO has one use", not dup, dup or f"{len(gpio_use)} GPIO used of 36"))
    gpio_of = {net: g for g, net in GPIO_MISC.items()}
    analog = sorted([ch["adc"] for ch in CHANNELS] + [gpio_of["VBAT_SNS"]])
    out.append(("analog inputs on ADC1 only (ADC2 is shared with Wi-Fi)", set(analog) <= ADC1_GPIO,
                "GPIO " + ", ".join(map(str, analog))))
    enables = [ch["en"] for ch in CHANNELS] + [gpio_of["NSLEEP"]]
    bad = [g for g in enables if g in RESET_PULLUP_GPIO | HIGH_GLITCH_GPIO | STRAP_GPIO]
    out.append(("PWM enables and nSLEEP avoid pins that pull up or glitch high at reset", not bad, bad or "ok"))
    # strap pins: GPIO45 and GPIO46 must read 0 at reset (VDD_SPI 3.3 V; SPI boot / download mode)
    pulled_low = all(any(set(n.parts[r]["pins"].values()) >= {f"LAMP{i}_G", "GND"} for r in n.parts
                         if n.parts[r]["kind"] == ("R", 100e3)) for i in (1, 2))
    out.append(("GPIO45/46 straps held low through the lamp gate pull-downs", pulled_low, "100 kΩ to GND"))

    # Driver configuration pins
    cfg = []
    for ref, p in n.parts.items():
        if p["kind"] == "DRV8876":
            pins = p["pins"]
            cfg.append(pins["16"] == "GND" and pins["7"] == "GND" and pins["17"] == "GND" and pins["5"] == "VREF")
    out.append(("DRV8876: PMODE = GND (PH/EN), IMODE = GND (fixed off-time, auto-retry), pad to GND",
                all(cfg) and len(cfg) == 7, f"{sum(cfg)} of 7"))

    # Voltage rating of every capacitor, diode and connector against its nets
    worst = []
    for ref, p in n.parts.items():
        info = n.info(ref)
        rating = info.get("rating")
        if rating is None or p["kind"] == "TP":
            continue
        vmax = 0.0
        for net in p["pins"].values():
            v = NET_VMAX.get(net, 0.0)
            if net in ("VBAT", "VBAT_IN"):
                v = VBAT_TRANSIENT if p["kind"] not in ("SMBJ15A", "BZT52C12") else 0.0
            vmax = max(vmax, v)
        if ref.startswith("C") and rating < vmax:
            worst.append((ref, rating, vmax))
        if p["kind"] in ("DRV8876", "TPS54302", "AO4407A", "AO3400A", "B5819W") and rating < vmax:
            worst.append((ref, rating, vmax))
    out.append(("voltage ratings cover the 12 V bus transient (SMBJ15A clamp 24.4 V)", not worst, worst or "ok"))
    return out


def summary(n):
    nets = n.nets()
    kinds = defaultdict(int)
    for p in n.parts.values():
        kinds[str(p["kind"])] += 1
    return dict(parts=len(n.parts), nets=len(nets), kinds=dict(kinds))


if __name__ == "__main__":
    nl = build()
    print(summary(nl))
    ok = True
    for name, good, detail in rules(nl):
        ok &= bool(good)
        print(("PASS " if good else "FAIL ") + name + ": " + str(detail))
    sys.exit(0 if ok else 1)

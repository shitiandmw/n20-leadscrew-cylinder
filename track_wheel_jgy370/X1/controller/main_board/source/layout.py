"""PCB floor plan of the X1 main board: board outline, part positions, copper zones and rules.

Board frame (mm): u runs from the rear edge (u = 0, machine X -136) to the front edge (u = 96, X -40);
v runs from the outboard edge (v = 0, machine Y 148) to the inboard edge (v = 64, Y 84). Seen from
above, this is the machine's top view with outboard at the top, and also KiCad's frame (y down).
KiCad coordinates are (ORIGIN + u, ORIGIN + v).

Floor plan (see DESIGN.md "PCB layout"):
- outboard edge: ESP32-S3 module at the front corner, antenna at the edge, 15 mm from its side edge
  to the USB-C shell and 14 mm to the front boss screw (SPEC C3); USB-C at machine X -98; the 5 V
  buck and the bulk capacitor at the rear corner, with the RESET button beside the USB-C;
- under the module: only tracks (its bottom pads fan out straight down to the drivers);
- front edge: XT30, with the reverse-polarity FET and TVS behind it;
- inboard edge: tracks XH-4, boom L, boom R, stick, bucket, swing (XH-2), lamps PH-3, expansion PH-4, all top entry;
  each H-bridge sits directly behind its connector;
- rear end of the driver row: the LEDs and the shared nFAULT/nSLEEP pull resistors and test pads;
- rear-inboard corner: buzzer, lamp switches, expansion supply; BOOT button on the rear-edge strip.

    python layout.py   -> prints the placement check (overlaps of courtyard boxes, board fit)
"""
import math

import netlist as NL

W, H = 96.0, 64.0                       # board size
ORIGIN = (100.0, 60.0)                  # KiCad position of the board's (u, v) = (0, 0) corner
X0, Y0 = -136.0, 148.0                  # machine X at u = 0, machine Y at v = 0 (x1_body.py BOARD)
HOLES = {"H1": (4.0, 4.0), "H2": (92.0, 4.0), "H3": (92.0, 60.0), "H4": (4.0, 60.0)}
USB_U = -98.0 - X0                      # SPEC C3: USB-C on the outboard edge at machine X -98
USB_OVERHANG = 0.5                      # receptacle face beyond the board edge
# Pin rows (v of pin 1) of the inboard connectors. Rev B first had side-entry headers with their courtyards flush with
# the inboard edge (9.74 XH / 6.79 PH deep). The top-entry headers fitted since 2026-11-14 have the same pads and keep
# these pin rows, so the copper did not change; their housings stand 6.3 (XH) and 4.0 (PH) mm in from the edge.
XH_PIN_V = H - 9.74                     # 54.26
PH_PIN_V = H - 6.79                     # 57.21
MODULE_U = 66.5                         # module centre; antenna keep-out +/-22 clears the USB and boss H2
DRV_ROW_V = 41.9                        # driver centre line
CELL_PITCH = 9.0


def machine(u, v):
    """Board (u, v) -> machine (X, Y)."""
    return X0 + u, Y0 - v


# ---- part placement -------------------------------------------------------------------------
PLACE = {}          # ref -> (u, v, rotation in degrees, KiCad convention: counter-clockwise on screen)
# Straps: locked wide tracks under each supply pour, laid before routing. The router (Freerouting 2.1)
# treats a copper pour as passable and would cut it; a strap is an obstacle and already joins the
# pour's pads. The pours themselves are added after routing, over their straps.
STRAPS = []         # (net, width, [(u, v), ...])


def strap(net, width, *pts):
    STRAPS.append((net, width, [(round(u, 3), round(v, 3)) for u, v in pts]))


NET = NL.build()


def put(ref, u, v, rot=0):
    assert ref in NET.parts, ref
    PLACE[ref] = (round(u, 3), round(v, 3), rot % 360)


def driver_cell(b, cu, cv):
    """One DRV8876 channel. U rotated 270: logic pins face the module (outboard), VM and the charge
    pump face the connector (inboard). OUT1 leaves at the outboard-left corner, OUT2 at the inboard
    side; the cell sits 1.5 mm right of its connector's centre so the two outputs do not cross."""
    put(f"U{b}", cu, cv, 270)
    put(f"C{b + 4}", cu + 1.35, cv + 4.75, 0)        # CPH-CPL flying cap, under pins 13/14
    put(f"C{b + 3}", cu - 0.6, cv + 6.4, 180)        # VCP-VM, under pins 11/12
    put(f"C{b + 1}", cu + 2.45, cv + 6.4, 180)       # VM 100 nF
    put(f"C{b + 2}", cu + 2.7, cv + 8.4, 180)        # VM 10 uF
    put(f"R{b + 1}", cu - 1.85, cv - 4.8, 180)       # IPROPI to GND, above pin 6
    put(f"R{b + 2}", cu - 1.85, cv - 6.4, 180)       # IPROPI to ISNS
    put(f"C{b + 5}", cu - 1.85, cv - 8.0, 0)         # ISNS filter


def buck_cell(b, cu, cv):
    """TPS54302 buck, IC at (cu, cv): inductor to the left of the SW pin, input caps under the VIN
    pin, bootstrap cap over the IC, feedback and enable dividers on the right. Returns the copper
    pours of the switch node and the output, and the output stitching-via sites."""
    put(f"U{b + 1}", cu, cv, 0)
    put(f"C{b + 4}", cu, cv - 2.55, 180)             # BOOT (pin 6, right) to SW (pin 2, left)
    put(f"L{b + 1}", cu - 6.2, cv, 180)              # pad 1 (SW) next to the IC, pad 2 (output) at cu - 8.22
    put(f"C{b + 3}", cu - 0.5, cv + 2.6, 0)          # VIN 100 nF: pad 1 under the VIN pin
    put(f"C{b + 1}", cu - 0.3, cv + 4.45, 0)         # VIN 10 uF
    put(f"C{b + 2}", cu - 0.3, cv + 6.6, 0)          # VIN 10 uF
    put(f"C{b + 5}", cu - 8.2, cv + 5.95, 270)       # output 22 uF, pad 1 (output) toward the inductor
    put(f"C{b + 6}", cu - 5.4, cv + 5.95, 270)
    put(f"R{b + 3}", cu + 3.0, cv - 1.2, 90)         # EN divider, upper (VBAT)
    put(f"R{b + 4}", cu + 4.6, cv - 1.2, 90)         # EN divider, lower
    put(f"R{b + 1}", cu + 3.0, cv + 2.4, 90)         # FB divider, upper (output)
    put(f"C{b + 7}", cu + 4.6, cv + 2.4, 90)         # feed-forward
    put(f"R{b + 2}", cu + 3.0, cv + 5.6, 90)         # FB divider, lower
    put(f"TP{b + 1}", cu + 5.6, cv + 7.4, 0)
    out = "+5V"
    sw = [(cu - 4.95, cv - 0.45), (cu - 1.7, cv - 0.45), (cu - 1.7, cv + 0.45), (cu - 4.95, cv + 0.45)]
    vout = [(cu - 9.6, cv + 2.2), (cu - 4.4, cv + 2.2), (cu - 4.4, cv + 5.3), (cu - 9.6, cv + 5.3)]
    strap(f"SW_{b}", 0.9, (cu - 4.18, cv), (cu - 1.6, cv))                         # IC SW pin to inductor
    strap(out, 1.2, (cu - 8.2, cv + 2.4), (cu - 8.2, cv + 4.48), (cu - 5.4, cv + 4.48))  # inductor to output caps
    return [(f"SW_{b}", "F.Cu", 6, sw), (out, "F.Cu", 6, vout)], []         # 5 V leaves by traces


def place_all():
    PLACE.clear()
    STRAPS.clear()
    pours, vias = [], []
    for ref, (u, v) in HOLES.items():
        put(ref, u, v)
    # ---- outboard edge
    put("U201", MODULE_U, 12.75, 0)                                    # module top flush with the edge
    put("J201", USB_U, 3.65 - USB_OVERHANG, 180)                       # receptacle face 0.5 mm proud
    # USB 2.0 on USB-C: each data line has a pad in both rows (D+ on A6 and B6, D- on A7 and B7), so the
    # plug works either way up. The pads interleave (B6 A7 A6 B7), so one link must pass outside the row:
    # D+ above it, D- below it. Strapped before routing; the router once left A7 unjoined, boxed in
    # between its own D+ link and the VBUS track.
    pv = 3.65 - USB_OVERHANG + 4.04                                     # pad row (HRO TYPE-C-31-M-12)
    top, bot = pv - 0.725 - 0.245, pv + 0.725 + 0.245                  # pads 1.45 long; 0.17 mm clear
    strap("USB_DP", 0.15, (USB_U - 0.75, pv), (USB_U - 0.75, top), (USB_U + 0.25, top), (USB_U + 0.25, pv))
    strap("USB_DN", 0.15, (USB_U - 0.25, pv), (USB_U - 0.25, bot), (USB_U + 0.75, bot), (USB_U + 0.75, pv))
    # ---- front edge: XT30 (rot 270: mating face toward +u; pins at the rear of the housing)
    put("J101", W - 13.64, 17.0, 270)
    # ---- inboard edge, front to rear; top entry, on the pin rows of rev B's side-entry headers
    xh_v, ph_v = XH_PIN_V, PH_PIN_V
    put("J102", 78.3, xh_v)                                            # tracks XH-4: pins 78.3 .. 85.8
    for i, ref in enumerate(("J104", "J105", "J106", "J107", "J103")):  # BL, BR, ST, BK, SW
        put(ref, 69.3 - 9.0 * i, xh_v)
    put("J108", 23.3, ph_v)                                            # lamps PH-3
    put("J109", 11.8, ph_v)                                            # expansion PH-4
    # ---- H-bridges: one cell per channel, 1.5 mm right of its connector centre
    conn_centre = {"BL": 69.3 + 1.25, "BR": 60.3 + 1.25, "ST": 51.3 + 1.25, "BK": 42.3 + 1.25,
                   "SW": 33.3 + 1.25, "TL": 78.3 + 1.25, "TR": 78.3 + 1.25 + 9.0}
    for i, ch in enumerate(NL.CHANNELS, start=1):
        driver_cell(300 + 10 * i, conn_centre[ch["key"]] + 1.5, DRV_ROW_V)
    # ---- power input, behind the XT30 (pins at u 82.36: VBAT_IN v 17.0, GND v 12.0)
    put("Q101", 83.0, 26.0, 90)          # drain pins 5-8 toward the XT30, source and gate inboard
    put("D102", 90.0, 26.0, 90)          # TVS: pad 1 (VBAT, cathode) inboard
    put("D101", 94.3, 26.0, 90)          # gate clamp: pad 1 (VBAT) inboard
    put("R101", 87.0, 31.0, 0)           # gate pull-down
    put("C102", 91.0, 31.0, 0)
    put("TP101", 94.6, 31.2)
    put("TP102", 94.6, 34.8)
    pours.append(("VBAT", "F.Cu", 6, [(80.4, 27.6), (95.6, 27.6), (95.6, 29.6), (92.6, 29.6), (92.6, 32.6),
                                      (80.4, 32.6)]))
    vias += [("VBAT", 81.3 + 1.2 * i, 31.2) for i in range(3)] + [("VBAT", 81.9 + 1.2 * i, 32.3) for i in range(2)]
    strap("VBAT_IN", 3.6, (82.9, 17.0), (82.9, 22.6))      # XT30 pin 1 to the drains
    strap("VBAT", 1.4, (81.09, 28.6), (83.64, 28.6))                               # sources ...
    strap("VBAT", 2.0, (82.5, 28.6), (82.5, 32.3))                                 # ... down to the vias
    strap("VBAT", 0.8, (81.3, 31.2), (83.7, 31.2))
    strap("VBAT", 0.8, (81.9, 32.3), (83.1, 32.3))
    # ---- the 5 V buck at the rear-outboard corner (revision A had the 6 V buck below it, at v = 18)
    p, vv = buck_cell(120, 19.0, 5.0)
    pours += p
    vias += vv
    put("C101", 30.6, 18.8, 0)           # VBAT bulk, beside the buck's input
    put("C130", 46.0, 31.2, 0)           # VBAT bulk at the actuator drivers (revision A: the 6 V bus)
    # battery sense, VREF
    put("R102", 51.5, 23.0, 0)
    put("R103", 51.5, 24.6, 0)
    put("C103", 54.6, 23.8, 90)
    put("R151", 40.0, 30.0, 0)
    put("R152", 40.0, 31.6, 0)
    put("C151", 42.6, 30.8, 90)
    put("TP151", 36.6, 30.8)
    # 3.3 V: diode-OR and LDO between the USB and the module
    put("D142", 41.0, 16.0, 180)         # VBUS -> LDO_IN (cathode, pad 1, toward the LDO)
    put("D141", 41.0, 18.6, 180)         # +5V -> LDO_IN
    put("U141", 47.0, 16.0, 0)
    put("C141", 47.0, 19.2, 0)
    put("C142", 51.0, 16.0, 0)
    put("TP141", 54.3, 16.0)
    # module support
    put("C201", 54.9, 9.0, 90)           # 22 uF at the 3V3 pin
    put("C202", 52.6, 8.0, 90)
    put("R201", 50.8, 10.6, 0)           # EN pull-up
    put("C203", 50.8, 12.3, 0)           # EN delay
    put("R202", 78.0, 22.3, 90)          # BOOT pull-up, at module pad 27
    # buttons out of the module's fan-out (recovery only; reached with the bay open)
    put("SW201", 28.8, 3.3, 0)           # RESET, in the free corner beside the USB-C
    put("SW202", 4.4, 12.0, 0)           # BOOT, on the free strip along the rear edge
    # USB-C support (receptacle pads face inboard at v ~7.2)
    put("U202", 38.0, 12.0, 0)
    put("R204", 34.4, 11.6, 90)          # CC2 (pad B5 at u 36.25)
    put("R203", 41.6, 11.6, 90)          # CC1 (pad A5 at u 39.25)
    put("C204", 43.2, 11.6, 90)
    # indicators and the shared driver lines' pull resistors and test pads: at the rear end of the driver
    # row, so the band under the module's bottom pads carries only their tracks
    put("R207", 27.2, 34.0, 0)           # nFAULT pull-up
    put("R208", 27.2, 35.6, 0)           # nSLEEP pull-down
    put("R205", 27.2, 37.4, 0)
    put("D201", 30.5, 37.4, 180)         # status LED (green), anode toward R205
    put("R206", 27.2, 39.5, 0)
    put("D202", 30.5, 39.5, 180)         # power LED (red)
    put("TP201", 78.2, 10.2)             # TXD0 (module pad 37)
    put("TP202", 78.2, 13.0)             # RXD0 (module pad 36)
    put("TP203", 24.0, 34.6)             # nFAULT
    put("TP204", 24.0, 37.6)             # nSLEEP
    # ---- rear-inboard: buzzer, lamps, expansion
    put("LS401", 13.5, 42.0, 0)
    put("D401", 20.3, 42.0, 90)          # buzzer flyback: pad 1 (BUZ_A) toward LS401 pad 1
    put("R420", 20.3, 46.9, 90)          # 0R series link from +5V
    put("Q403", 20.6, 36.6, 0)           # buzzer switch: drain (BUZ_K)
    put("R403", 16.4, 34.4, 0)
    put("R413", 16.4, 36.0, 0)
    put("F401", 21.6, 51.0, 90)          # lamp PTC, by J108 pin 1
    put("Q401", 24.6, 49.6, 270)         # drain (pin 3) toward the connector
    put("Q402", 28.4, 49.6, 270)
    put("R401", 23.4, 45.4, 90)
    put("R411", 25.0, 45.4, 90)
    put("R402", 27.2, 45.4, 90)
    put("R412", 28.8, 45.4, 90)
    put("F402", 11.6, 51.5, 0)           # expansion PTC, by J109 pin 1
    put("C401", 15.7, 51.4, 90)
    put("R421", 17.6, 51.4, 90)
    put("R422", 19.2, 51.4, 90)
    missing = set(NET.parts) - set(PLACE)
    assert not missing, f"not placed: {sorted(missing)}"
    return PLACE, pours, vias


# ---- design rules (JLCPCB 4-layer standard process, jlcpcb.com/capabilities/pcb-capabilities) ----------
# Vias 0.45/0.2: the pad must be 0.1 mm (0.15 preferred) larger than the hole, and a 0.2 hole with a pad
# of 0.45 or more is not charged extra. Plated component holes need a 0.15 mm ring (checked in check_pcb.py).
RULES = dict(clearance=0.15, track_min=0.15, via_d=0.45, via_drill=0.2, via_min_d=0.45, drill_min=0.2,
             min_annular=0.1, hole_clearance=0.25, hole_to_hole=0.25, edge_clearance=0.4, silk_clearance=0.0)
PTH_MIN_RING = 0.15
# net classes: name -> (track width, clearance, nets)
NETCLASSES = {
    "Default": (0.15, 0.15, None),
    # motor outputs: 0.4 mm matches the DRV8876 pin; 1.0 A on 1 oz outer copper rises about 10 C
    "Motor": (0.4, 0.15, ["OUT1_*", "OUT2_*"]),
    # supply branches; the trunks are planes and pours
    "Supply": (0.4, 0.15, ["VBAT", "+3V3", "LDO_IN", "VBUS", "+5V_LAMP", "SW_1*", "BST_1*"]),
    "Supply5": (0.8, 0.2, ["+5V", "+5V_EXP"]),
    "Input": (1.5, 0.2, ["VBAT_IN"]),
}

# ---- copper zones (u, v polygons). Inner 1 is a solid ground plane; inner 2 is VBAT, which feeds all
# seven H-bridges and the 5 V buck. (Revision A split inner 2 for a +6V area under the module.)
VBAT_AREA = [(0.0, 0.0), (W, 0.0), (W, H), (0.0, H)]
PLANES = [
    # (net, layer, priority, polygon)
    ("GND", "In1.Cu", 0, [(0, 0), (W, 0), (W, H), (0, H)]),
    ("VBAT", "In2.Cu", 0, VBAT_AREA),
    # input pour: XT30 pin 1 to the FET drains
    ("VBAT_IN", "F.Cu", 5, [(80.4, 14.6), (85.6, 14.6), (85.6, 24.4), (80.4, 24.4)]),
]
PLANE_CLEARANCE = 0.3
FANOUT_WIDTH = {"GND": 0.3, "VBAT": 0.4}   # plane nets, fanned out to their planes (pcb_make.py)
# GND is hidden from the router: its ~120 fan-out vias would block both signal layers. Its pads are joined
# after routing, by the ground pours and a fan-out among the routed tracks.
ROUTER_HIDDEN = ["GND"]
# Ground pads that the routes boxed in on the routing of 2026-11-05, so the fan-out after routing found
# no room for their via. These get theirs before routing; the router sees the via and its stub as
# keep-outs (pcb_make.hide_nets).
EARLY_FANOUT = ["R101.2", "C315.2", "U202.2", "R208.2", "R341.2"]
# Pads joined to their pours solid, not by thermal spokes: the USB-C shell tabs (all four are "S1"), where
# the routes leave room for only one of the two spokes KiCad asks for.
SOLID_PADS = ["J201.S1"]
# Reference texts moved off their footprint's default spot, where they overlapped a neighbour's silk, a
# pad or another reference: offset (du, dv) in mm from the part's position, and the text angle. Each is
# the nearest spot clear of silk, pads and the other references (found by a search on the board,
# 2026-11-06; DRC then reports no silk overlap and no silk over copper).
REF_AT = {
    "J201": (0.0, 5.99, 0), "U202": (0.0, 3.41, 90), "F401": (0.0, 3.0, 0),
    "U121": (0.0, -3.92, 0), "L121": (-4.17, 0.0, 90), "J102": (0.0, -3.53, 0),
}
HOLE_KEEPOUT_R = 3.2                  # no tracks or vias under the M2.5 screw heads (outer layers)


def courtyard_box(ref):
    """Approximate courtyard (u0, v0, u1, v1) from the footprint courtyards measured in KiCad 9."""
    kind = NET.parts[ref]["kind"]
    fp = NL.kind_info(kind)["footprint"].split(":")[1]
    box = COURTYARDS.get(fp)
    if box is None:
        return None
    x0, y0, x1, y1 = box
    u, v, rot = PLACE[ref]
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    out = []
    for x, y in pts:
        r = math.radians(rot)
        out.append((u + x * math.cos(r) + y * math.sin(r), v - x * math.sin(r) + y * math.cos(r)))
    us, vs = [p[0] for p in out], [p[1] for p in out]
    return min(us), min(vs), max(us), max(vs)


COURTYARDS = {  # footprint -> (x0, y0, x1, y1), from pcbnew: the box of footprint.GetCourtyard(F_CrtYd)
    "ESP32-S3-WROOM-1_X1": (-9.795, -13.045, 9.795, 13.495),
    "JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical": (-2.995, -2.895, 5.495, 3.945),
    "JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical": (-2.995, -2.895, 10.495, 3.945),
    "JST_PH_B3B-PH-K_1x03_P2.00mm_Vertical": (-2.495, -2.245, 6.495, 3.345),
    "JST_PH_B4B-PH-K_1x04_P2.00mm_Vertical": (-2.495, -2.245, 8.495, 3.345),
    "AMASS_XT30PW-M_1x02_P2.50mm_Horizontal": (-9.7, -13.64, 4.7, 2.29),
    "USB_C_Receptacle_HRO_TYPE-C-31-M-12": (-5.37, -5.32, 5.37, 4.2),
    "HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm_Mask2.46x2.31mm_ThermalVias": (-3.94, -2.79, 3.94, 2.79),
    "L_Bourns_SRP6060FA": (-3.5, -3.6, 3.5, 3.6),
    "CP_Elec_8x10.5": (-6.2, -4.54, 6.2, 4.54),
    "SOIC-8_3.9x4.9mm_P1.27mm": (-3.75, -2.75, 3.75, 2.75),
    "D_SMB": (-3.69, -2.29, 3.69, 2.29),
    "SW_Push_1P1T_XKB_TS-1187A": (-3.79, -2.85, 3.79, 2.85),
    "Fuse_1812_4532Metric": (-3.0, -2.0, 3.0, 2.0),
    "SOT-23-6": (-2.1, -1.75, 2.1, 1.75),
    "SOT-23-5": (-2.1, -1.75, 2.1, 1.75),
    "SOT-23": (-1.98, -1.75, 1.98, 1.75),
    "D_SOD-123": (-2.4, -1.2, 2.4, 1.2),
    "R_0603_1608Metric": (-1.52, -0.78, 1.52, 0.78),
    "C_0603_1608Metric": (-1.48, -0.73, 1.48, 0.73),
    "C_0805_2012Metric": (-1.75, -1.02, 1.75, 1.02),
    "C_1206_3216Metric": (-2.35, -1.2, 2.35, 1.2),
    "Fuse_1206_3216Metric": (-2.33, -1.18, 2.33, 1.18),
    "LED_0805_2012Metric": (-1.73, -0.99, 1.73, 0.99),
    "LED_0603_1608Metric": (-1.52, -0.78, 1.52, 0.78),
    "TestPoint_Pad_D1.5mm": (-1.3, -1.3, 1.29, 1.3),
    "MountingHole_2.7mm_M2.5": (-2.99, -3.0, 2.99, 3.0),
    "Buzzer_XHXDZ_8530": (-4.685, -4.685, 4.685, 4.685),
}


def check():
    place_all()
    boxes = {r: courtyard_box(r) for r in PLACE}
    bad = []
    refs = sorted(boxes)
    for i, a in enumerate(refs):
        A = boxes[a]
        for b in refs[i + 1:]:
            B = boxes[b]
            if A[0] < B[2] - 1e-3 and B[0] < A[2] - 1e-3 and A[1] < B[3] - 1e-3 and B[1] < A[3] - 1e-3:
                bad.append((a, b, round(min(A[2], B[2]) - max(A[0], B[0]), 2), round(min(A[3], B[3]) - max(A[1], B[1]), 2)))
    outside = [r for r, (u0, v0, u1, v1) in boxes.items()
               if r not in ("U201", "J201", "J101") and (u0 < -0.01 or v0 < -0.01 or u1 > W + 0.01 or v1 > H + 0.01)]
    return bad, outside, boxes


if __name__ == "__main__":
    bad, outside, _ = check()
    for b in bad:
        print("overlap", *b)
    print("outside", outside)
    print(f"{len(PLACE)} parts placed, {len(bad)} courtyard-box overlaps")

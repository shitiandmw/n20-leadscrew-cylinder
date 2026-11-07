"""Builds controller/X1_controller_guide.html, the illustrated guide to the X1 main board for
non-engineers: what the board does, the power flow, the motor drivers, a simulator of the firmware's
rules, the safety rules, the program and the installation.

The page is one offline HTML file (images embedded). Its numbers come from the sources, not from
memory:
  - firmware/x1_main/src (control_logic.h, x1_link.h, x1_main_pins.h) and x1_main.ino: timings,
    thresholds, ramps, current limits; the simulator gets them as FACTS;
  - main_board/source/netlist.py: which driver feeds which socket, the socket roles;
  - main_board/X1_main_board_A_parts.json: part boxes for the board tour's highlights;
  - main_board/source/build_pcb.py CONN_LABELS: the socket names printed on the board.
The prose in guide_template.html quotes some of those numbers; check_prose() fails the build when a
source changes and the text no longer matches.

Run: python3 build_guide.py   (standard library only)
"""
import ast
import base64
import html
import json
import pathlib
import re
import struct
import sys

HERE = pathlib.Path(__file__).resolve().parent
CTRL = HERE.parent
MB = CTRL / "main_board"
FW = CTRL / "firmware" / "x1_main"
OUT = CTRL / "X1_controller_guide.html"

sys.path.insert(0, str(MB / "source"))
import netlist as NL  # noqa: E402

# ---------------------------------------------------------------------------------------------
# Firmware facts


def read(p):
    return pathlib.Path(p).read_text(encoding="utf-8")


def num(text, pattern, what):
    m = re.search(pattern, text)
    assert m, f"{what}: pattern {pattern!r} not found"
    return float(m.group(1))


def firmware_facts():
    h = read(FW / "src" / "control_logic.h")
    link = read(FW / "src" / "x1_link.h")
    pins = read(FW / "src" / "x1_main_pins.h")
    ino = read(FW / "x1_main.ino")
    f = {}
    f["packet_ms"] = num(link, r"CONTROL_PERIOD_MS = (\d+);", "packet period")
    f["telemetry_ms"] = num(link, r"TELEMETRY_PERIOD_MS = (\d+);", "telemetry period")
    f["link_timeout_ms"] = num(link, r"LINK_TIMEOUT_MS = (\d+);", "link timeout")
    m = re.search(r"SPEED_MIN = (\d+), SPEED_MAX = (\d+), SPEED_STEP = (\d+), SPEED_DEFAULT = (\d+);", link)
    f["speed_min"], f["speed_max"], f["speed_step"], f["speed_default"] = map(int, m.groups())
    f["axis_full"] = num(link, r"AXIS_FULL = (\d+);", "axis full scale")
    f["loop_ms"] = num(ino, r"CONTROL_PERIOD_MS = (\d+);", "control loop period")
    f["pwm_hz"] = num(ino, r"PWM_FREQ_HZ = (\d+);", "PWM frequency")
    f["pair_window_ms"] = num(ino, r"PAIR_WINDOW_MS = (\d+);", "pairing window")
    f["boot_pair_window_ms"] = num(ino, r"BOOT_PAIR_WINDOW_MS = (\d+);", "BOOT pairing window")
    f["boot_hold_ms"] = num(ino, r"BOOT_HOLD_MS = (\d+);", "BOOT hold")
    for key, name in [("dead_band", "dead_band"), ("stall_fraction", "stall_fraction"), ("stall_ms", "stall_ms"),
                      ("vbat_tau_ms", "vbat_tau_ms"), ("warn_v", "vbat_warn_v"), ("warn_clear_v", "vbat_warn_clear_v"),
                      ("stop_v", "vbat_stop_v"), ("stop_clear_v", "vbat_stop_clear_v"),
                      ("boom_trim_max", "boom_trim_max"), ("boom_imbalance_mA", "boom_imbalance_mA"),
                      ("boom_imbalance_ms", "boom_imbalance_ms"), ("boom_end_timeout_ms", "boom_end_timeout_ms"),
                      ("bench_max_ms", "bench_max_ms")]:
        f[key] = num(h, rf"\b{name} = ([\d.]+)f?[;,]", name)
    # channels: names and limits from the generated pin map, ramps and the 12 V flag from CHANNEL[]
    limits = re.findall(r'\{"([^"]+)", \d+, \d+, \d+, [\d.]+f, ([\d.]+)f\}', pins)
    makes = re.findall(r"detail::make\((\w+), (\d+), (true|false), (true|false)\)", h)
    assert len(limits) == 7 and len(makes) == 7, (limits, makes)
    poles = {"TRACK_L": ("back", "forward"), "TRACK_R": ("back", "forward"), "SWING": ("left", "right"),
             "BOOM_L": ("lower", "raise"), "BOOM_R": ("lower", "raise"), "STICK": ("out", "in"),
             "BUCKET": ("open", "curl")}
    f["channels"] = [dict(name=name, limit_a=float(lim), ramp_ms=int(ramp), vbat=vb == "true",
                          neg=poles[key][0], pos=poles[key][1])
                     for (name, lim), (key, ramp, _inv, vb) in zip(limits, makes)]
    return f


def check_prose(t, f):
    """Numbers the template's text states, against the sources."""
    ch = {c["name"]: c for c in f["channels"]}
    pct = lambda v: f"{round(v * 100)} %"  # noqa: E731
    expect = [
        f"{round(1000 / f['packet_ms'])} times a second",              # overview
        f"{round(1000 / f['telemetry_ms'])} times a second",
        f"<b>{f['loop_ms']:g} ms</b>", f"every <b>{f['packet_ms']:g} ms</b>", f"every <b>{f['telemetry_ms']:g} ms</b>",
        f"{f['pwm_hz']:,.0f} times a second".replace(",", " "),        # "20 000 times a second"
        f"less than {pct(f['dead_band'])} from centre",
        f"0.{ch['Track left']['ramp_ms'] // 100} s for the tracks", f"0.{ch['Swing']['ramp_ms'] // 100} s for the swing",
        f"0.{ch['Stick']['ramp_ms'] // 100} s for the arm",
        f"<b>{ch['Track left']['limit_a']:.2f} A</b> for the tracks", f"<b>{ch['Swing']['limit_a']:.1f} A</b> for the swing",
        f"<b>{ch['Stick']['limit_a']:.1f} A</b> for the arm",
        f"for <b>{f['stall_ms'] / 1000:g} seconds</b>", f"at {pct(f['stall_fraction'])} of its current limit for {f['stall_ms'] / 1000:g} s",
        f"Below {f['warn_v']:g} V: warning beeps", f"Below {f['stop_v']:g} V: motors stop",
        f"back above {f['stop_clear_v']:g} V", f"averaged over about {f['vbat_tau_ms'] / 1000:g} s",
        f"No valid command for {f['link_timeout_ms'] / 1000:g} s", f"radio lost for {f['link_timeout_ms'] / 1000:g} s",
        f"slows down over {ch['Swing']['ramp_ms'] / 1000:g} s",
        f"(up to {pct(f['boom_trim_max'])})", f"over {f['boom_imbalance_mA']:g} mA apart) for {f['boom_imbalance_ms'] / 1000:g} s",
        f"follow within {f['boom_end_timeout_ms'] / 1000:g} s",
        f"{f['speed_min']}–{f['speed_max']} % (steps of {f['speed_step']}, starts at {f['speed_default']} %)",
        f"−{f['axis_full']:g}…+{f['axis_full']:g}",
        f"Within {f['boot_pair_window_ms'] / 1000:g} s of switching on, hold <b>BOOT</b> for {f['boot_hold_ms'] / 1000:g} s",
        f"for up to {f['pair_window_ms'] / 1000:g} s", f"pairing mode, {f['pair_window_ms'] / 1000:g} s",
        f'min="{f["speed_min"]}" max="{f["speed_max"]}" step="{f["speed_step"]}" value="{f["speed_default"]}"',
    ]
    missing = [e for e in expect if e not in t]
    assert not missing, "guide text no longer matches the firmware: " + "; ".join(missing)


# ---------------------------------------------------------------------------------------------
# Board facts

def conn_labels():
    src = read(MB / "source" / "build_pcb.py")
    m = re.search(r"^CONN_LABELS = (\{.*?^\})", src, re.S | re.M)
    return ast.literal_eval(re.sub(r"#[^\n]*", "", m.group(1)))


def board_parts():
    d = json.loads(read(MB / "X1_main_board_A_parts.json"))
    # machine coordinates to the layout frame: u = X + 136 (rear edge forward), v = 148 - Y (outboard inward)
    return {p["ref"]: (p["x"][0] + 136, p["x"][1] + 136, 148 - p["y"][1], 148 - p["y"][0]) for p in d["parts"]}


def png_size(p):
    with open(p, "rb") as fh:
        head = fh.read(24)
    assert head[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", head[16:24])


def data_uri(p):
    mime = {".png": "image/png", ".jpg": "image/jpeg"}[p.suffix]
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


# check_pcb.py renders the board at 14.07 px/mm, centred in a 1992 x 1376 image; the bottom view is
# seen from below, so u is mirrored.
RW, RH, PX, CX, CY = 1992, 1376, 14.07, 996.0, 688.0


def px(u, v, side):
    x = CX + (u - 48) * PX if side == "top" else CX - (u - 48) * PX
    return x, CY + (v - 32) * PX


def rect(box, side, pad=0.6):
    u0, u1, v0, v1 = box
    xa, y0 = px(u0 - pad, v0 - pad, side)
    xb, y1 = px(u1 + pad, v1 + pad, side)
    return dict(x=round(min(xa, xb), 1), y=round(y0, 1), w=round(abs(xb - xa), 1), h=round(y1 - y0, 1))


def union(parts, refs):
    bs = [parts[r] for r in refs]
    return (min(b[0] for b in bs), max(b[1] for b in bs), min(b[2] for b in bs), max(b[3] for b in bs))


def group(parts, n):
    """Every part numbered n0..n9 (a circuit block, by the netlist's numbering)."""
    return [r for r in parts if re.fullmatch(rf"[A-Z]+{n}\d", r)]


def tour(parts, f, labels):
    ch = {c["name"]: c for c in f["channels"]}
    chan = {c["key"]: c for c in NL.CHANNELS}
    nl = NL.build()
    # driver of each channel: the DRV8876 whose OUT1 is that channel's OUT1 net
    drv = {}
    for ref, p in nl.parts.items():
        if p["kind"] == "DRV8876":
            key = p["pins"]["8"].split("_")[1]
            drv[key] = ref
    short = dict(TL="TRACK\nL", TR="TRACK\nR", SW="SWING", BL="BOOM\nL", BR="BOOM\nR", ST="STICK", BK="BUCKET")
    cells = sorted(chan, key=lambda k: parts[drv[k]][0])
    sockets = sorted({chan[k]["conn"][0] for k in chan}, key=lambda r: parts[r][0])

    Z = []

    def zone(title, text, groups, tht=False, glabels=None):
        Z.append(dict(title=title, text=text, groups=groups, tht=tht, glabels=glabels or [None] * len(groups)))

    zone("Power socket and its guards",
         "The yellow XT30 socket takes the battery's 9–12.6 V through the 12 V link from the toolbox. "
         "Q101 is a wrong-way guard: if the plug were ever wired backwards it stays closed and nothing is harmed. "
         "D102 swallows the voltage spikes that motors make.",
         [["J101", "Q101", "D101", "D102", "R101", "C102"]], tht=True)
    zone("Energy buffer",
         "The round can (C101, 220 µF) is a small reservoir. It covers the sudden gulps of current when motors start, "
         "so the voltage on the board stays steady.",
         [["C101"]])
    zone("6 V converter",
         "Turns the battery voltage into 6 V for the four arm actuators (boom left and right, stick, bucket). "
         "The grey square is its coil; together with chip U111 it works like an electrical gearbox. Up to 3 A.",
         [group(parts, 11)])
    zone("5 V converter",
         "The same circuit set to 5 V. It feeds the lamps, the buzzer, the expansion port and the 3.3 V regulator. Up to 3 A.",
         [group(parts, 12)])
    zone("3.3 V regulator",
         "Makes the clean, steady 3.3 V the brain needs (U141). Two small diodes let it take power from the 5 V converter "
         "or from a USB cable, whichever is there: that is how the program can be loaded with no battery.",
         [group(parts, 14)])
    zone("The brain: ESP32-S3",
         "A small computer with a built-in radio. It runs the control program, talks to the hand controller and decides "
         "what every motor does. The zig-zag at the board's edge is its antenna, kept clear of copper so the radio reaches out.",
         [["U201", "C201", "C202", "R201", "C203"]])
    zone("USB-C socket",
         "For loading the program and for the text console (section 8). U202 next to it protects the brain from static "
         "shocks. With the body closed, it is reached through a slot in the left side.",
         [["J201", "U202", "R203", "R204", "C204"]], tht=True)
    zone("Two buttons",
         "RESET (SW201, next to the USB socket) restarts the program. BOOT (SW202, at the corner): hold it for 2 s just after "
         "switching on to pair a hand controller. Held while pressing RESET, it puts the chip into loading mode instead.",
         [["SW201"], ["SW202"]], glabels=["RESET", "BOOT"])
    zone("Two lights",
         "Red: the brain has power. Green: what the program is doing: a short flash every 2 s (no hand controller), slow blink "
         "(controller found, waiting for centred sticks), steady (armed), double flash (stopped or a fault), fast blink (pairing).",
         [["D201", "D202", "R205", "R206"]])
    zone("Seven motor drivers",
         "One identical driver cell per motor: a DRV8876 chip with its capacitors and the resistor that sets its current "
         "limit (section 4). The three on the right run at battery voltage (tracks, swing); the four on the left at 6 V (the arm). "
         "The small resistors above them make the shared reference for the current limits and measure the battery and the 6 V rail.",
         [group(parts, int(drv[k][1:3])) for k in cells], glabels=[short[k] for k in cells])
    zone("Motor sockets",
         "The motor plugs go in along this edge, which faces the middle of the machine. Each socket's name is printed under it "
         "on the underside. The 4-pin one takes both track motors (pins 1-2 left, 3-4 right), as they come from the slip ring.",
         [[r] for r in sockets], tht=True, glabels=[labels[r][0].replace(" ", "\n") for r in sockets])
    zone("Lamps and expansion port",
         "LAMPS: two lamp outputs at 5 V (roof work lamps, toolbox lamp), switched by Q401 and Q402 and protected by a "
         "self-resetting fuse. EXP: 5 V up to 2 A plus a serial link, kept for a later 4G module.",
         [["J108", "F401", "Q401", "Q402"], ["J109", "F402", "C401"]], tht=True, glabels=["LAMPS", "EXP"])
    zone("Buzzer",
         "The horn button, a travel alarm that beeps while the tracks move, and warning beeps (low battery, faults). "
         "Q403 switches it; R420 can be swapped for a resistor to make it quieter.",
         [["LS401", "Q403", "D401", "R403", "R413"]])

    out = []
    for z in Z:
        e = dict(title=html.escape(z["title"]), text=html.escape(z["text"]))
        for side in ("top", "bottom"):
            if side == "bottom" and not z["tht"]:
                e[side], e[side + "_labels"] = [], []
                continue
            # from below only the plugs' solder joints show: the underside highlights the sockets alone
            groups = z["groups"] if side == "top" else [[r for r in g if r.startswith("J")] for g in z["groups"]]
            boxes = [union(parts, g) for g in groups]
            e[side] = [rect(b, side) for b in boxes]
            e[side + "_labels"] = []
            if side == "top":
                for b, t in zip(boxes, z["glabels"]):
                    if t:
                        x, y = px((b[0] + b[1]) / 2, (b[2] + b[3]) / 2, side)
                        e[side + "_labels"].append(dict(x=round(x, 1), y=round(y + 9, 1), t=t))
            allb = union(parts, [r for g in groups for r in g])
            mx, my = px((allb[0] + allb[1]) / 2, (allb[2] + allb[3]) / 2, side)
            if len(boxes) > 1 and z["glabels"][0]:          # labelled groups: marker above them
                mx, my = px((allb[0] + allb[1]) / 2, allb[2] - 2.6, side)
            e[side + "_marker"] = dict(x=round(mx, 1), y=round(my, 1))
        out.append(e)
    for side in ("top", "bottom"):                     # the numbered markers must not overlap
        ms = [(i, e[side + "_marker"]) for i, e in enumerate(out) if e[side]]
        for a in range(len(ms)):
            for b in range(a + 1, len(ms)):
                (i, p), (j, q) = ms[a], ms[b]
                d = ((p["x"] - q["x"]) ** 2 + (p["y"] - q["y"]) ** 2) ** 0.5
                assert d > 64, f"{side}: markers {i + 1} and {j + 1} overlap ({d:.0f} px)"
    return out, drv


# ---------------------------------------------------------------------------------------------
# Generated SVG pieces

def overview_motors(f):
    ch = f["channels"]
    rows = [(c["name"], "12 V" if c["vbat"] else "6 V", "#2a9d5c") for c in ch]
    rows += [("2 lamp outputs", "5 V", "#d4a500"), ("Buzzer", "5 V", "#d4a500")]
    s = ['<text x="700" y="42" font-size="15" font-weight="700" fill="#2a9d5c">Motors and outputs</text>']
    for i, (name, volts, col) in enumerate(rows):
        y = 70 + i * 38
        y0 = 112 + i * 19
        s.append(f'<path class="flow" d="M622,{y0} C 660,{y0} 660,{y} 698,{y}" stroke="{col}" stroke-width="3"/>')
        if col == "#2a9d5c":
            s.append(f'<g transform="translate(716,{y})"><circle r="13" fill="#e8f0ea" stroke="{col}" stroke-width="3"/>'
                     f'<rect x="-2" y="-10" width="4" height="20" rx="2" fill="{col}">'
                     f'<animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="{1.2 + 0.15 * i:.2f}s" repeatCount="indefinite"/></rect></g>')
        else:
            s.append(f'<circle cx="716" cy="{y}" r="11" fill="#ffe66d" stroke="{col}" stroke-width="3"/>')
        s.append(f'<text x="738" y="{y + 5}" font-size="14.5" fill="#1d2a35">{html.escape(name)} '
                 f'<tspan fill="#5b6b78" font-size="12.5">({volts})</tspan></text>')
    return "\n  ".join(s)


def wrap(text, n):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > n:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    return lines + [cur]


def wiring_svg(parts, labels, drv):
    """Top view of the board with each socket's destination."""
    nl = NL.build()
    S, X0, Y0 = 6.5, 188, 24
    X = lambda u: X0 + u * S          # noqa: E731
    Y = lambda v: Y0 + v * S          # noqa: E731
    o = [f'<svg viewBox="0 0 1000 700" width="100%" role="img" aria-label="Where each plug goes">',
         f'<rect x="{X(0)}" y="{Y(0)}" width="{96 * S}" height="{64 * S}" rx="6" fill="#2f5d3a" stroke="#1e3b25" stroke-width="3"/>']
    for u, v in [(4, 4), (92, 4), (92, 60), (4, 60)]:
        o.append(f'<circle cx="{X(u)}" cy="{Y(v)}" r="9" fill="#cfd8de" stroke="#1e3b25" stroke-width="2"/>')

    def box(ref, fill, stroke="none", rx=2):
        u0, u1, v0, v1 = parts[ref]
        return (f'<rect x="{X(max(u0, 0)):.1f}" y="{Y(max(v0, 0)):.1f}" width="{(min(u1, 96) - max(u0, 0)) * S:.1f}" '
                f'height="{(min(v1, 64) - max(v0, 0)) * S:.1f}" rx="{rx}" fill="{fill}" stroke="{stroke}"/>')
    o.append(box("U201", "#3d4a54"))
    o.append(f'<text x="{X(66.5)}" y="{Y(14)}" text-anchor="middle" font-size="13" font-weight="700" fill="#fff">brain</text>')
    o.append(box("J201", "#cfd8de"))
    o.append(f'<text x="{X(38)}" y="{Y(-1.5)}" text-anchor="middle" font-size="13" font-weight="700" fill="#33424d">USB-C (outer side of the machine)</text>')
    o.append(box("J101", "#f2d21b", "#a38b00"))
    o.append(f'<text x="{X(88)}" y="{Y(15) + 5}" text-anchor="middle" font-size="12" font-weight="700" fill="#3a2a00">XT30</text>')
    o.append(f'<text x="{X(96) + 12}" y="{Y(12)}" font-size="13" font-weight="700" fill="#e4572e">← 12 V link</text>'
             f'<text x="{X(96) + 12}" y="{Y(12) + 17}" font-size="12" fill="#5b6b78">from the toolbox</text>'
             f'<text x="{X(96) + 12}" y="{Y(12) + 33}" font-size="12" fill="#5b6b78">(front of the machine)</text>')
    for r in drv.values():
        o.append(box(r, "#1c1c1c"))
    for r in ("L111", "L121"):
        o.append(box(r, "#5d6670"))
    o.append(box("C101", "#e8ecef", rx=20))
    o.append(box("LS401", "#1c1c1c", rx=6))
    o.append(f'<text x="{X(48)}" y="{Y(30) + 5}" text-anchor="middle" font-size="13" fill="#d7eadb">seen from above, parts side up</text>')

    # destinations, in socket order along the inboard edge
    socks = sorted(labels, key=lambda r: parts[r][0])
    role = {r: nl.parts[r]["role"] for r in socks}
    dest = {
        "J102": ("TRACKS", "Both track motors: pins 1-2 left, 3-4 right. From the slip ring in the turntable's hub.", "#e4572e"),
        "J103": ("SWING", "Swing motor. Its wires come through the counterweight's channel and over the rear wall.", "#e4572e"),
        "J104": ("BOOM L", "Boom cylinder, left", "#f08c2e"),
        "J105": ("BOOM R", "Boom cylinder, right", "#f08c2e"),
        "J106": ("STICK", "Stick cylinder", "#f08c2e"),
        "J107": ("BUCKET", "Bucket cylinder", "#f08c2e"),
        "J108": ("LAMPS", "Lamps: +5 V, lamp 1 (roof work lamps), lamp 2 (toolbox lamp)", "#2f6fde"),
        "J109": ("EXP", "Expansion: 5 V, GND, TX, RX. Free, for a later 4G module.", "#2f6fde"),
    }
    assert set(dest) == set(socks), (set(dest), socks)
    for r in socks:                                   # the names printed on the board must match
        assert dest[r][0] == labels[r][0], (r, dest[r][0], labels[r])
    slot_w = 1000 / len(socks)
    for i, r in enumerate(socks):
        u0, u1, v0, v1 = parts[r]
        name, text, col = dest[r]
        o.append(box(r, "#f4f4f0", "#9aa7b1"))
        cx = X((u0 + u1) / 2)
        sx = slot_w * (i + 0.5)
        o.append(f'<path class="flow slow" d="M{cx:.1f},{Y(64):.1f} C {cx:.1f},{Y(64) + 60:.1f} {sx:.1f},{Y(64) + 40:.1f} {sx:.1f},{Y(64) + 92:.1f}" stroke="{col}" stroke-width="4"/>')
        y = Y(64) + 112
        o.append(f'<text x="{sx:.1f}" y="{y:.1f}" text-anchor="middle" font-size="14" font-weight="800" fill="{col}">{name}</text>')
        for k, line in enumerate(wrap(text, 17)):
            o.append(f'<text x="{sx:.1f}" y="{y + 18 + 15 * k:.1f}" text-anchor="middle" font-size="12" fill="#33424d">{html.escape(line)}</text>')
        assert role[r]  # every socket has a netlist role
    o.append('<g font-size="12.5"><text x="20" y="60" font-weight="700">Wire colours</text>'
             '<rect x="20" y="72" width="12" height="12" fill="#e4572e"/><text x="38" y="83">12 V motors</text>'
             '<rect x="20" y="92" width="12" height="12" fill="#f08c2e"/><text x="38" y="103">6 V actuators</text>'
             '<rect x="20" y="112" width="12" height="12" fill="#2f6fde"/><text x="38" y="123">5 V outputs</text></g>')
    o.append("</svg>")
    return "\n".join(o)


# ---------------------------------------------------------------------------------------------

def main():
    t = read(HERE / "guide_template.html")
    f = firmware_facts()
    check_prose(t, f)
    parts = board_parts()
    labels = conn_labels()
    top, bottom = MB / "X1_main_board_A_top.png", MB / "X1_main_board_A_bottom.png"
    assert png_size(top) == (RW, RH) and png_size(bottom) == (RW, RH), "render size changed: update PX/CX/CY"
    zones, drv = tour(parts, f, labels)
    x0, y0 = px(-3, -4.5, "top")                        # crop: the board and the markers above it
    x1, y1 = px(99, 67, "top")
    img = CTRL / "images"
    sub = {
        "%%TOUR_VIEWBOX%%": f"{x0:.0f} {y0:.0f} {x1 - x0:.0f} {y1 - y0:.0f}",
        "%%RW%%": str(RW), "%%RH%%": str(RH),
        "%%IMG_TOP%%": data_uri(top), "%%IMG_BOTTOM%%": data_uri(bottom),
        "%%IMG_INSIDE%%": data_uri(img / "guide_inside_body.jpg"),
        "%%IMG_BAY%%": data_uri(img / "guide_board_in_bay.jpg"),
        "%%IMG_SLOT%%": data_uri(img / "guide_usb_slot.jpg"),
        "%%OVERVIEW_MOTORS%%": overview_motors(f),
        "%%WIRING_SVG%%": wiring_svg(parts, labels, drv),
        "%%TOUR_JSON%%": json.dumps(zones, ensure_ascii=False),
        "%%FACTS_JSON%%": json.dumps(f, ensure_ascii=False),
        "%%RENDER_JSON%%": json.dumps(dict(w=RW, h=RH, px_per_mm=PX)),
    }
    for k, v in sub.items():
        assert k in t, k
        t = t.replace(k, v)
    left = re.findall(r"%%[A-Z_]+%%", t)
    assert not left, left
    OUT.write_text(t, encoding="utf-8")
    print(f"{OUT.relative_to(CTRL.parent)}: {OUT.stat().st_size / 1e6:.2f} MB, {len(zones)} tour stops")


if __name__ == "__main__":
    main()

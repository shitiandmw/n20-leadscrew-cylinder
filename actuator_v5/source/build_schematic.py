"""Circuit schematic of the V5 actuator, drawn from one netlist and checked against it.

python source/build_schematic.py
    -> electronics/schematic.pdf (A3, 2 sheets), schematic_sheet1/2.svg + .png, netlist.csv
Sheet 1 is everything inside the cylinder, sheet 2 the controller board. After drawing,
the script rebuilds the connectivity of the drawn wires (end points, T-junctions,
power symbols and net flags) and stops if it differs from NETLIST.
"""
from collections import Counter, defaultdict
from pathlib import Path
import csv
import json
import re
import matplotlib
matplotlib.use("Agg")
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle
import schemdraw
import schemdraw.elements as elm
import schemdraw.logic as logic

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "electronics"
W, H = 42.0, 29.7                       # A3 landscape, 1 drawing unit = 1 cm
INK, MUTED, NET, FRAME = "#1d2a30", "#5f6f75", "#1f5f8b", "#8d989c"
IC_FILL, TAG_FILL, BLOCK = "#f5f7f8", "#eaf2f8", "#b9c3c7"
WIRE = {"red": "#d7261e", "black": "#222222", "green": "#1a9a4b", "blue": "#2457c5",
        "orange": "#f07c12", "purple": "#8e3bc9"}
DATE, REV = "2026-10-27", "A"

# wire, colour, actuator end, controller net; J1 pin number = wire number
HARNESS = [("W1", "red", "U1 pin 1  VCC", "+5V"), ("W2", "black", "U1 pin 2  GND", "GND"),
           ("W3", "green", "U1 pin 3  OUT", "ALLOW_RET"), ("W4", "red", "U2 pin 1  VCC", "+5V"),
           ("W5", "black", "U2 pin 2  GND", "GND"), ("W6", "blue", "U2 pin 3  OUT", "ALLOW_EXT"),
           ("W7", "orange", "M1 (+)", "MOTOR_A"), ("W8", "purple", "M1 (−)", "MOTOR_B")]

NETLIST = {
    1: {"W1": {"U1.1", "C1.1", "R1.1"}, "W2": {"U1.2", "C1.2"}, "W3": {"U1.3", "R1.2"},
        "W4": {"U2.1", "C2.1", "R2.1"}, "W5": {"U2.2", "C2.2"}, "W6": {"U2.3", "R2.2"},
        "W7": {"M1.+"}, "W8": {"M1.-"}},
    2: {"+5V": {"J1.1", "J1.4", "J3.1", "U3.14", "C3.1", "U5.VCC", "U6.5V"},
        "GND": {"J1.2", "J1.5", "J2.2", "J3.2", "U3.7", "U3.9", "U3.10", "U3.12", "U3.13", "C3.2",
                "R3.2", "R4.2", "R5.2", "R6.2", "R7.2", "R8.2", "R10.2", "R11.2", "C4.2", "C5.2", "C6.2",
                "U4.GND", "U5.GND", "U6.GND", "SW1.2", "SW2.2", "SW3.2"},
        "VM_IN": {"J2.1", "F1.1"},
        "VM": {"F1.2", "U4.VIN", "C4.1", "C5.1"},
        "ALLOW_RET": {"J1.3", "R3.1", "U3.5", "U6.D6"},
        "ALLOW_EXT": {"J1.6", "R4.1", "U3.2", "U6.D5"},
        "EXT_CMD": {"U6.D9", "R5.1", "U3.1"},
        "RET_CMD": {"U6.D10", "R6.1", "U3.4"},
        "AIN1": {"U3.3", "R7.1", "U4.AIN1"},
        "AIN2": {"U3.6", "R8.1", "U4.AIN2"},
        "nSLEEP": {"U6.D8", "U4.SLP"},
        "nFAULT": {"U6.D7", "U4.FLT"},
        "AISEN": {"U4.AISEN", "R11.1"},
        "AOUT1": {"U4.AOUT1", "U5.IP+"},
        "MOTOR_A": {"U5.IP-", "J1.7", "D1.1", "C7.1"},
        "MOTOR_B": {"U4.AOUT2", "J1.8", "D1.2", "C7.2"},
        "ACS_OUT": {"U5.OUT", "R9.1"},
        "I_SENSE": {"R9.2", "C6.1", "R10.1", "U6.A0"},
        "BTN_EXT": {"U6.D2", "SW1.1"},
        "BTN_RET": {"U6.D3", "SW2.1"},
        "BTN_RST": {"U6.D4", "SW3.1"}},
}
NO_CONNECT = {1: set(), 2: {"U3.8", "U3.11", "U6.D13"}}   # D13 drives the Nano's own LED


def key(p):
    return (round(p[0], 3), round(p[1], 3))


def on_segment(q, a, b):
    """q strictly inside the axis-aligned or diagonal segment a-b."""
    if q in (a, b):
        return False
    cross = (b[0] - a[0]) * (q[1] - a[1]) - (b[1] - a[1]) * (q[0] - a[0])
    if abs(cross) > 1e-6:
        return False
    return min(a[0], b[0]) - 1e-6 <= q[0] <= max(a[0], b[0]) + 1e-6 and \
        min(a[1], b[1]) - 1e-6 <= q[1] <= max(a[1], b[1]) + 1e-6


class Sheet:
    def __init__(self, number, title):
        self.number, self.title = number, title
        self.d = schemdraw.Drawing(show=False)
        self.d.config(unit=1.5, inches_per_unit=1 / 2.54, fontsize=7, lw=1.0, color=INK, margin=0)
        self.d.add(elm.Line().endpoints((0, 0), (W, H)).color("white").linewidth(0))   # page extent
        self.texts, self.rects = [], []
        self.wires, self.pins, self.names, self.dots = [], {}, [], []
        self.report = None

    # ---- drawing primitives -------------------------------------------------
    def line(self, a, b, color=INK, lw=1.0, ls="-"):
        self.d.add(elm.Line().endpoints(a, b).color(color).linewidth(lw).linestyle(ls))

    def text(self, p, s, size=7.0, color=INK, ha="left", va="center", weight="normal", style="normal"):
        self.texts.append((p, s, size, color, ha, va, weight, style))

    def rect(self, x0, y0, x1, y1, edge=INK, fill="none", lw=0.9, ls="-", z=1.0):
        self.rects.append((x0, y0, x1, y1, edge, fill, lw, ls, z))

    def block(self, x0, y0, x1, y1, title):
        self.rect(x0, y0, x1, y1, edge=BLOCK, lw=0.8, ls=(0, (4, 3)), z=0.5)
        self.text((x0 + 0.25, y1 - 0.32), title, 6.8, MUTED, weight="bold")

    # ---- connectivity-carrying elements ---------------------------------------
    def wire(self, *pts, color=INK, lw=1.0):
        for a, b in zip(pts, pts[1:]):
            self.line(a, b, color, lw)
            self.wires.append((key(a), key(b)))

    def dot(self, p):
        self.d.add(elm.Dot(radius=0.075).at(p))
        self.dots.append(key(p))

    def part(self, kind, ref, a, b, value, side="right", pins=("1", "2"), gap=0.42):
        shape = {"R": elm.Resistor, "C": elm.Capacitor, "CP": lambda: elm.Capacitor(polar=True),
                 "D": elm.DiodeTVS, "F": elm.Fuse, "SW": elm.Button, "M": elm.Motor}[kind]()
        self.d.add(shape.endpoints(a, b))
        self.pins[f"{ref}.{pins[0]}"], self.pins[f"{ref}.{pins[1]}"] = key(a), key(b)
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        label = f"{ref}\n{value}" if value else ref
        if abs(a[0] - b[0]) < 1e-6:     # vertical part
            self.text((mx + gap if side == "right" else mx - gap, my), label,
                      ha="left" if side == "right" else "right")
        else:
            self.text((mx, my + gap if side == "top" else my - gap), label.replace("\n", "  "), ha="center",
                      va="bottom" if side == "top" else "top")

    def power(self, p, net):
        self.d.add(elm.Vdd().at(p))
        self.text((p[0], p[1] + 0.5), net, 7, ha="center", va="bottom", weight="bold")
        self.names.append((key(p), net))

    def ground(self, p):
        self.d.add(elm.Ground().at(p))
        self.names.append((key(p), "GND"))

    def flag(self, p, net, toward="right", text=None, color=NET):
        """Net flag; the point sits on the wire end, the body points away from it."""
        text = text or net
        width = max(0.9, 0.42 + 0.155 * len(text))
        tag = elm.Tag(width=width, height=0.46).at(p).color(color).fill(TAG_FILL)
        self.d.add(tag.right() if toward == "right" else tag.left())
        cx = p[0] + (width / 2 + 0.06) * (1 if toward == "right" else -1)
        self.text((cx, p[1]), text, 6.6, color, ha="center")
        self.names.append((key(p), net))
        return width

    def noconnect(self, ref_pin, p):
        self.d.add(elm.NoConnect().at(p))

    def ic(self, ref, box, pins, lead=0.6, name_size=6.4):
        """Box with pins (key, side, position[, name]); returns the outer lead end of every pin."""
        x0, y0, x1, y1 = box
        self.rect(x0, y0, x1, y1, fill=IC_FILL, lw=1.1, z=1.0)
        ends = {}
        for k, side, pos, *name in pins:
            name = name[0] if name else k
            a, b = {"L": ((x0, pos), (x0 - lead, pos)), "R": ((x1, pos), (x1 + lead, pos)),
                    "T": ((pos, y1), (pos, y1 + lead)), "B": ((pos, y0), (pos, y0 - lead))}[side]
            self.line(a, b)
            ends[k] = b
            self.pins[f"{ref}.{k}"] = key(b)
            if side == "L":
                self.text((x0 + 0.12, pos), name, name_size)
            elif side == "R":
                self.text((x1 - 0.12, pos), name, name_size, ha="right")
            elif side == "T":
                self.text((pos, y1 - 0.12), name, name_size, ha="center", va="top")
            else:
                self.text((pos, y0 + 0.12), name, name_size, ha="center", va="bottom")
        return ends

    def pin_numbers(self, ends, numbers, box):
        x0, y0, x1, y1 = box
        for k, num in numbers.items():
            x, y = ends[k]
            if x < x0:
                self.text((x0 - 0.08, y + 0.04), num, 5.8, MUTED, ha="right", va="bottom")
            elif x > x1:
                self.text((x1 + 0.08, y + 0.04), num, 5.8, MUTED, va="bottom")
            elif y > y1:
                self.text((x + 0.07, y1 + 0.08), num, 5.8, MUTED, va="bottom")
            else:
                self.text((x + 0.07, y0 - 0.08), num, 5.8, MUTED, va="top")

    def gate(self, ref, unit, at, numbers):
        g = self.d.add(logic.And(inputs=2).right().scale(1.4).at(at).anchor("in1"))
        ends = {}
        for anchor, num in zip(("in1", "in2", "out"), numbers):
            p = g.absanchors[anchor]
            ends[anchor] = (p[0], p[1])
            self.pins[f"{ref}.{num}"] = key(p)
            dx = -0.22 if anchor == "out" else -0.1
            self.text((p[0] + dx, p[1] + 0.04), str(num), 5.8, MUTED, ha="right", va="bottom")
        self.text((at[0] + 1.0, at[1] + 0.45), ref + unit, 7, weight="bold", ha="center", va="bottom")
        return ends

    # ---- connectivity check --------------------------------------------------
    def check(self, expected, no_connect):
        parent = {}

        def find(a):
            parent.setdefault(a, a)
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        def union(a, b):
            parent[find(a)] = find(b)

        for a, b in self.wires:
            union(a, b)
        pin_pts = Counter(self.pins.values())
        name_pts = Counter(p for p, _ in self.names)
        wire_ends = Counter(p for seg in self.wires for p in seg)
        attach = set(pin_pts) | set(name_pts) | set(wire_ends) | set(self.dots)
        degree = Counter()
        for q in attach:
            degree[q] += wire_ends[q] + pin_pts[q] + name_pts[q]
            for a, b in self.wires:
                if on_segment(q, a, b):
                    union(q, a)
                    degree[q] += 2
        errors = []
        junctions = {q for q, n in degree.items() if n >= 3}
        for q in junctions - set(self.dots):
            errors.append(f"junction without dot at {q}")
        for q in set(self.dots) - junctions:
            errors.append(f"dot that is not a junction at {q}")
        for q, n in wire_ends.items():
            if degree[q] == 1:
                errors.append(f"dangling wire end at {q}")
        by_name = defaultdict(list)
        for p, n in self.names:
            by_name[n].append(p)
        for pts in by_name.values():
            for p in pts[1:]:
                union(p, pts[0])
        groups = defaultdict(lambda: {"pins": set(), "names": set()})
        for ref, p in self.pins.items():
            groups[find(p)]["pins"].add(ref)
        for p, n in self.names:
            groups[find(p)]["names"].add(n)
        drawn = {}
        for g in groups.values():
            if len(g["names"]) > 1:
                errors.append(f"short between {sorted(g['names'])}")
            if not g["pins"]:
                errors.append(f"label {sorted(g['names'])} with no pin")
                continue
            drawn[frozenset(g["pins"])] = g["names"]
        matched = set()
        for net, pins in expected.items():
            missing = pins - set(self.pins)
            if missing:
                errors.append(f"{net}: pins not drawn {sorted(missing)}")
            hit = drawn.get(frozenset(pins))
            if hit is None:
                found = [sorted(p) for p in drawn if p & pins]
                errors.append(f"{net}: expected {sorted(pins)}, drawn {found}")
            elif hit and hit != {net}:
                errors.append(f"{net}: drawn with label {sorted(hit)}")
            else:
                matched.add(frozenset(pins))
        for pins, names in drawn.items():
            if pins in matched:
                continue
            if len(pins) == 1 and not names and next(iter(pins)) in no_connect:
                continue
            errors.append(f"unexpected net {sorted(pins)} {sorted(names)}")
        if errors:
            raise SystemExit(f"sheet {self.number} connectivity check failed:\n  " + "\n  ".join(errors))
        self.report = dict(nets=len(expected), pins=len(self.pins), junctions=len(junctions))
        return self.report

    # ---- page furniture and output -------------------------------------------
    def frame(self, heading, intro):
        self.rect(0.5, 0.5, W - 0.5, H - 0.5, edge=FRAME, lw=1.3)
        self.rect(1.0, 1.0, W - 1.0, H - 1.0, edge=FRAME, lw=0.7)
        for i in range(8):
            x = 1.0 + 5.0 * i
            if i:
                self.line((x, 0.5), (x, 1.0), FRAME, 0.7)
                self.line((x, H - 1.0), (x, H - 0.5), FRAME, 0.7)
            for y in (0.75, H - 0.75):
                self.text((x + 2.5, y), str(i + 1), 6, MUTED, ha="center")
        rows = "ABCDEF"
        step = (H - 2.0) / len(rows)
        for i, r in enumerate(rows):
            y = H - 1.0 - step * i
            if i:
                self.line((0.5, y), (1.0, y), FRAME, 0.7)
                self.line((W - 1.0, y), (W - 0.5, y), FRAME, 0.7)
            for x in (0.75, W - 0.75):
                self.text((x, y - step / 2), r, 6, MUTED, ha="center")
        self.text((1.6, 28.05), heading, 12.5, weight="bold")
        self.text((1.6, 27.4), intro, 7.4, MUTED)
        # title block
        x0, x1 = 28.0, W - 1.0
        self.rect(x0, 1.0, x1, 5.4, edge=FRAME, fill="white", lw=1.0, z=1.5)
        for y in (4.2, 3.3, 2.2):
            self.line((x0, y), (x1, y), FRAME, 0.7)
        self.text((x0 + 0.3, 4.8), self.title, 11.5, weight="bold")
        self.text((x0 + 0.3, 3.75), "Excavator arm actuator V5  ·  N20 gearmotor with integrated M3 leadscrew",
                  7.2, MUTED)
        cells = [("SHEET", f"{self.number} of 2"), ("REVISION", REV), ("DATE", DATE), ("FORMAT", "A3 landscape")]
        cw = (x1 - x0) / len(cells)
        for i, (cap, val) in enumerate(cells):
            cx = x0 + cw * i
            if i:
                self.line((cx, 2.2), (cx, 3.3), FRAME, 0.7)
            self.text((cx + 0.2, 3.08), cap, 5.4, MUTED)
            self.text((cx + 0.2, 2.6), val, 8.2)

    def render(self):
        fig = self.d.draw(show=False).getfig()
        ax = fig.axes[0]
        fig.set_size_inches(W / 2.54, H / 2.54)
        ax.set_position([0, 0, 1, 1])
        ax.set_xlim(0, W)
        ax.set_ylim(0, H)
        fig.set_facecolor("white")
        for x0, y0, x1, y1, edge, fill, lw, ls, z in self.rects:
            ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, edgecolor=edge, facecolor=fill, lw=lw, ls=ls, zorder=z))
        for (x, y), s, size, color, ha, va, weight, style in self.texts:
            ax.text(x, y, s, fontsize=size, color=color, ha=ha, va=va, fontweight=weight, fontstyle=style,
                    linespacing=1.18, zorder=6, clip_on=False)
        if self.report:
            r = self.report
            ax.text(28.3, 1.75, f"Generated by source/build_schematic.py. Connectivity re-derived from the drawing "
                                f"and checked\nagainst the netlist: {r['nets']} nets, {r['pins']} pins, "
                                f"{r['junctions']} junctions, no differences.",
                    fontsize=5.6, color=MUTED, va="center", linespacing=1.25, zorder=6)
        return fig


# ---------------------------------------------------------------------------------------------
def harness_end(s, p, wid, colour, dest):
    x, y = p
    s.wire(p, (x + 1.5, y), color=WIRE[colour], lw=3.2)
    w = s.flag((x + 1.5, y), wid, "right", color=INK)
    s.text((x + 1.5 + w + 0.3, y), dest, 6.8)


def hall_sensor(s, ref, r, c, yc, title, wires):
    xcap, xic, xr, xh = 3.0, 6.6, 10.4, 13.4
    yv, yg = yc + 2.4, yc - 2.4
    box = (xic - 1.6, yc - 1.2, xic + 1.6, yc + 1.2)
    p = s.ic(ref, box, [("1", "T", xic, "VCC"), ("2", "B", xic, "GND"), ("3", "R", yc, "OUT")])
    s.pin_numbers(p, {"1": "1", "2": "2", "3": "3"}, box)
    s.text((xic, yc + 0.2), "DRV5033AJ", 7, ha="center")
    s.text((xic, yc - 0.25), "TO-92 (LPG)", 5.8, MUTED, ha="center")
    s.text((box[0], box[3] + 0.12), ref, 8.5, weight="bold", va="bottom")
    s.wire(p["1"], (xic, yv))
    s.wire(p["2"], (xic, yg))
    s.wire((xcap, yv), (xh, yv))
    s.wire((xcap, yg), (xh, yg))
    s.wire(p["3"], (xh, yc))
    for q in ((xic, yv), (xic, yg), (xr, yv), (xr, yc)):
        s.dot(q)
    s.part("C", c, (xcap, yv), (xcap, yg), "100 nF\n0603")
    s.part("R", r, (xr, yv), (xr, yc), "4.7 kΩ\n1206")
    for y, (wid, colour, dest) in zip((yv, yc, yg), wires):
        harness_end(s, (xh, y), wid, colour, dest)
    s.block(1.6, yg - 0.8, 24.4, yv + 1.5, title)


def sheet1(params, lengths, magnet):
    s = Sheet(1, "Inside the actuator")
    s.frame("INSIDE THE ACTUATOR",
            "Both Hall end-stop sensors and the N20 motor. Eight wires leave through the rear-cap port and land on J1 "
            "of the controller (sheet 2); J1 pin number = wire number.")
    hall_sensor(s, "U1", "R1", "C1", 22.1, "U1 · RETRACT-END HALL SENSOR (MOTOR END OF THE BARREL)",
                [("W1", "red", "+5V  →  J1-1"), ("W3", "green", "ALLOW_RET  →  J1-3"), ("W2", "black", "GND  →  J1-2")])
    hall_sensor(s, "U2", "R2", "C2", 14.2, "U2 · EXTEND-END HALL SENSOR (HEAD END OF THE BARREL)",
                [("W4", "red", "+5V  →  J1-4"), ("W6", "blue", "ALLOW_EXT  →  J1-6"), ("W5", "black", "GND  →  J1-5")])
    # motor: (+) terminal toward the cable port = W7
    xm, yp, yn, xh = 6.6, 9.3, 6.5, 13.4
    s.part("M", "M1", (xm, yp), (xm, yn), None, pins=("+", "-"))
    s.texts.pop()                                   # custom label below
    s.text((xm + 0.3, yp - 0.55), "+", 9, weight="bold", ha="left")
    s.text((xm + 0.3, yn + 0.55), "−", 9, weight="bold", ha="left")
    s.text((xm - 0.8, (yp + yn) / 2), f"M1\nN20 gearmotor\nM3 × {params.get('screw_length_mm', 40):.0f} leadscrew", 7, ha="right")
    s.wire((xm, yp), (xh, yp))
    s.wire((xm, yn), (xh, yn))
    harness_end(s, (xh, yp), "W7", "orange", "MOTOR_A  →  J1-7")
    harness_end(s, (xh, yn), "W8", "purple", "MOTOR_B  →  J1-8")
    s.text((8.2, (yp + yn) / 2), "fit the motor with its (+) terminal toward the cable port;\n"
                                 "W7/W8 swap polarity with direction, neither is a ground", 6.4, MUTED)
    s.block(1.6, 5.7, 24.4, 10.5, "M1 · MOTOR (THE UNCHANGED CORE PART)")

    # harness table
    s.block(24.9, 18.9, 40.4, 26.0, "HARNESS · 8-WIRE TAIL IN Ø4.0 / 3.2 MM JACKET")
    cols = [25.2, 26.2, 28.3, 31.3, 32.6, 35.6, 37.2]
    heads = ["Wire", "Colour", "Actuator end", "J1 pin", "Controller net", "Ins. Ø", "Inside, mm"]
    yh = 25.05
    for x, h in zip(cols, heads):
        s.text((x, yh), h, 6.2, MUTED, weight="bold")
    s.line((25.1, yh - 0.3), (40.1, yh - 0.3), BLOCK, 0.6)
    for i, (wid, colour, end, net) in enumerate(HARNESS):
        y = yh - 0.75 - 0.62 * i
        od = params.get("motor_wire_od_mm", 0.7) if wid in ("W7", "W8") else params.get("sensor_wire_od_mm", 0.4)
        s.line((cols[1], y), (cols[1] + 0.45, y), WIRE[colour], 3.2)
        yb = y - 0.08
        s.text((cols[0], yb), wid, 6.8, weight="bold", va="baseline")
        for x, v, c in ((cols[1] + 0.6, colour, INK), (cols[2], end, INK), (cols[3], f"J1-{wid[1]}", INK),
                        (cols[4], net, NET), (cols[5], f"{od:.1f} mm", INK),
                        (cols[6], f"{lengths[wid]:.0f}" if wid in lengths else "–", INK)):
            s.text((x, yb), v, 6.6, c, va="baseline")
    s.text((25.2, 19.35), "“Inside” = modelled route from the solder joint to 8 mm past the jacket entry; add the run "
                          "to the controller\nand calibration slack. Modelled OD: sensor 0.4 mm (AWG 32 thin-wall PTFE), motor 0.7 mm "
                          "(AWG 28 PTFE); measure before buying the jacket.", 5.6, MUTED, va="center")

    # where the sensors sit
    s.block(24.9, 11.0, 40.4, 18.2, "WHERE THE SENSORS SIT · BARREL Z IN MM, 0 = GEARBOX FRONT FACE")
    zx = lambda z: 25.7 + (z + 31.0) * 0.163
    bz0, bz1 = params.get("barrel_z", [-23.0, 53.0])
    m0, m1 = params.get("magnet_end_positions_z", [9.2, 39.2])
    h0, h1 = params.get("sensor_centres_z", [5.4, 43.0])
    stroke = params.get("stroke_mm", 30)
    yb0, yb1 = 14.5, 15.9
    s.rect(zx(-30.5), yb0 - 0.1, zx(bz0), yb1 + 0.1, edge=INK, fill="#3a4044", lw=0.6)
    s.rect(zx(bz0), yb0, zx(bz1), yb1, edge=INK, fill="#f6dc6a", lw=0.8)
    s.rect(zx(-26.5), yb0 + 0.25, zx(0), yb1 - 0.25, edge=INK, fill="#c9cfd2", lw=0.6, z=1.2)
    s.text(((zx(-26.5) + zx(0)) / 2, (yb0 + yb1) / 2), "motor", 6, ha="center")
    s.line((zx(0), (yb0 + yb1) / 2), (zx(params.get("screw_length_mm", 40)), (yb0 + yb1) / 2), "#6d7579", 1.6)
    for z, solid in ((m0, True), (m1, False)):
        s.rect(zx(z) - 0.17, yb0 + 0.05, zx(z) + 0.17, yb0 + 0.38, edge="#b02a1f",
               fill="#d7261e" if solid else "white", lw=0.8, z=1.4)
    for z in (m0, m1):
        s.line((zx(z), yb0 + 0.38), (zx(z), yb1 + 0.55), "#b02a1f", 0.6, ls=":")
    s.line((zx(m0), yb1 + 0.45), (zx(m1), yb1 + 0.45), "#b02a1f", 0.8)
    s.text(((zx(m0) + zx(m1)) / 2, yb1 + 0.55), f"magnet travel z {m0:.1f} → {m1:.1f} (stroke {stroke})", 6,
           "#b02a1f", ha="center", va="bottom")
    for z, ref in ((h0, "U1"), (h1, "U2")):
        s.rect(zx(z) - 0.2, yb0 - 0.55, zx(z) + 0.2, yb0 - 0.15, edge=INK, fill=INK, lw=0.6, z=1.4)
        s.text((zx(z), yb0 - 0.7), f"{ref}  z {z:.1f}", 6.4, weight="bold", ha="center", va="top")
    s.text((zx(-30.5), yb1 + 0.25), "rear cap · cable port", 5.8, MUTED, va="bottom")
    s.text((zx(bz1), yb1 + 0.25), "head", 5.8, MUTED, ha="right", va="bottom")
    s.text((zx(-10), 17.0), "extend  →", 7, MUTED, ha="center")
    s.text((25.2, 12.15), f"Each Hall sits {params.get('sensor_centres_z', [0, 0])[1] - m1:.1f} mm outboard of the "
                          f"magnet end position because the output switches about {magnet['operate']:.1f} mm\nbefore "
                          f"the magnet centre arrives and releases {magnet['release']:.1f} mm after it (typ., magnet "
                          "model). The sensors slide ±3 mm in the channel for calibration.", 5.8, MUTED)

    # sensor and magnet facts
    s.block(24.9, 5.7, 40.4, 10.5, "HALL SENSOR AND MAGNET")
    facts = [("U1, U2", "TI DRV5033AJQLPG, omnipolar, open-drain output, 2.5–38 V supply (used at 5 V)."),
             ("Thresholds", "operate BOP 3–12 mT (typ 6.9), release BRP 1–5 mT (typ 3.5). Output LOW = magnet present."),
             ("Magnet", "N35, Ø4 × 2 mm, magnetised through the 2 mm, axis radial toward the channel, glued in the carrier."),
             ("Model", f"about {magnet['peak']:.0f} mT at the sensor; reverse lobe {magnet['lobe']:.1f} mT stays under "
                       "BOP min, so no early trigger."),
             ("Do not", "use N42 or stronger: its reverse lobe can reach BOP min and switch the sensor twice.")]
    for i, (k, v) in enumerate(facts):
        y = 9.6 - 0.72 * i
        s.text((25.2, y), k, 6.4, weight="bold")
        s.text((27.0, y), v, 6.4)

    notes = ["NOTES",
             "1. Open-drain outputs: R1/R2 pull OUT up to +5 V at the sensor. The 47 kΩ pull-downs on the controller (R3/R4, "
             "sheet 2) make a broken signal\n    or supply wire read LOW, which blocks that direction.",
             "2. R1/R2 (1206) and C1/C2 (0603) are soldered straight onto the Hall leads. Sleeve every joint with heat-shrink "
             "before the sensor goes into the channel.",
             "3. No splices inside the cylinder: each Hall has its own +5 V and GND wire, joined only at J1 on the controller.",
             "4. Pin numbers are those of the LPG package in the TI datasheet (1 VCC, 2 GND, 3 OUT). Check them on the part, "
             "not on the 3D picture."]
    for i, n in enumerate(notes):
        s.text((1.7, 4.95 - 0.62 * i - (0.18 if i > 1 else 0)), n, 7 if i == 0 else 6.5,
               INK if i == 0 else MUTED, weight="bold" if i == 0 else "normal", va="top" if i else "center")
    s.check(NETLIST[1], NO_CONNECT[1])
    return s


def sheet2():
    s = Sheet(2, "Controller board")
    s.frame("CONTROLLER BOARD",
            "6 V motor supply, 5 V logic. U3 blocks a direction in hardware whenever its Hall output is LOW; the "
            "firmware adds current limit, timeout and fault latching.")
    top = 26.7
    s.block(1.6, 15.0, 10.0, top, "HARNESS FROM THE ACTUATOR")
    s.block(10.4, 15.0, 21.7, top, "DIRECTION GATES · U3 SN74HC08")
    s.block(22.1, 15.0, 40.4, top, "H-BRIDGE AND MOTOR CURRENT SENSE")
    s.block(1.6, 5.8, 10.0, 14.6, "POWER IN")
    s.block(10.4, 5.8, 18.6, 14.6, "U3 SUPPLY AND SPARE GATES")
    s.block(19.0, 5.8, 31.0, 14.6, "MICROCONTROLLER")
    s.block(31.4, 5.8, 40.4, 14.6, "DIRECTION LOGIC")

    # J1 harness connector
    ys = [24.8 - 1.2 * i for i in range(8)]
    box = (2.4, ys[-1] - 0.5, 4.6, ys[0] + 0.5)
    j1 = s.ic("J1", box, [(str(i + 1), "R", y, h[0]) for i, (y, h) in enumerate(zip(ys, HARNESS))])
    s.pin_numbers(j1, {str(i + 1): str(i + 1) for i in range(8)}, box)
    for y, h in zip(ys, HARNESS):
        s.line((2.6, y), (3.1, y), WIRE[h[1]], 3.0)
    s.text((box[0], box[3] + 0.12), "J1", 8.5, weight="bold", va="bottom")
    s.text((box[0] + 0.6, box[3] + 0.12), "8-way terminal", 6.2, MUTED, va="bottom")
    for n, net in ((1, "+5V"), (4, "+5V")):
        s.wire(j1[str(n)], (5.8, ys[n - 1]))
        s.power((5.8, ys[n - 1]), net)
    for n in (2, 5):
        s.wire(j1[str(n)], (5.8, ys[n - 1]))
        s.ground((5.8, ys[n - 1]))
    for n, net in ((3, "ALLOW_RET"), (6, "ALLOW_EXT")):
        s.wire(j1[str(n)], (6.6, ys[n - 1]))
        s.flag((6.6, ys[n - 1]), net)
    y7, y8 = ys[6], ys[7]
    s.wire(j1["7"], (8.0, y7))
    s.wire(j1["8"], (8.0, y8))
    s.flag((8.0, y7), "MOTOR_A")
    s.flag((8.0, y8), "MOTOR_B")
    for q in ((5.9, y7), (5.9, y8), (7.1, y7), (7.1, y8)):
        s.dot(q)
    s.part("D", "D1", (5.9, y7), (5.9, y8), None)
    s.texts.pop()
    s.part("C", "C7", (7.1, y7), (7.1, y8), None)
    s.texts.pop()
    s.text((5.9, y8 - 0.35), "D1\nSMBJ8.0CA", 6.4, ha="center", va="top")
    s.text((7.45, y8 - 0.35), "C7\n100 nF", 6.4, ha="center", va="top")

    # direction gates
    xg, xb, xa, x5, x4 = 18.8, 13.2, 16.8, 13.9, 17.6
    for unit, y1, nums, cmd, allow, rc, ra in (("A", 23.6, (1, 2, 3), "EXT_CMD", "ALLOW_EXT", "R5", "R4"),
                                               ("B", 19.2, (4, 5, 6), "RET_CMD", "ALLOW_RET", "R6", "R3")):
        y2 = y1 - 0.7
        g = s.gate("U3", unit, (xg, y1), nums)
        s.flag((xb, y1), cmd, "left", text=f"{cmd} · D{9 if unit == 'A' else 10}")
        s.wire((xb, y1), g["in1"])
        s.dot((x5, y1))
        s.part("R", rc, (x5, y1), (x5, y1 - 1.8), "10 kΩ", side="left")
        s.ground((x5, y1 - 1.8))
        s.flag((xa, y2), allow, "left")
        s.wire((xa, y2), g["in2"])
        s.dot((x4, y2))
        s.part("R", ra, (x4, y2), (x4, y2 - 1.8), "47 kΩ")
        s.ground((x4, y2 - 1.8))
        if unit == "A":
            out_a = g["out"]
        else:
            out_b = g["out"]

    # H-bridge
    box = (27.4, 19.2, 30.8, 24.0)
    u4 = s.ic("U4", box, [("AIN1", "L", out_a[1]), ("AIN2", "L", 22.25), ("SLP", "L", 21.0), ("FLT", "L", 20.0),
                          ("VIN", "T", 29.1), ("GND", "B", 28.2), ("AISEN", "B", 30.0),
                          ("AOUT1", "R", 23.1), ("AOUT2", "R", 20.6)])
    s.text((29.1, 22.0), "DRV8833", 7.4, ha="center")
    s.text((29.1, 21.55), "Pololu #2130", 5.8, MUTED, ha="center")
    s.text((box[0], box[3] + 0.12), "U4", 8.5, weight="bold", va="bottom")
    s.wire(out_a, u4["AIN1"])
    s.dot((22.6, out_a[1]))
    s.part("R", "R7", (22.6, out_a[1]), (22.6, out_a[1] - 1.75), "10 kΩ")
    s.ground((22.6, out_a[1] - 1.75))
    xr = 24.1
    s.wire(out_b, (xr, out_b[1]), (xr, 22.25), u4["AIN2"])
    s.dot((22.6, out_b[1]))
    s.part("R", "R8", (22.6, out_b[1]), (22.6, out_b[1] - 1.75), "10 kΩ")
    s.ground((22.6, out_b[1] - 1.75))
    s.flag(u4["SLP"], "nSLEEP", "left", text="nSLEEP · D8")
    s.flag(u4["FLT"], "nFAULT", "left", text="nFAULT · D7")
    yvm = 25.7
    s.wire(u4["VIN"], (29.1, yvm), (33.4, yvm))
    s.power((33.4, yvm), "VM")
    s.dot((31.2, yvm))
    s.dot((32.4, yvm))
    s.part("CP", "C4", (31.2, yvm), (31.2, 24.4), None)
    s.texts.pop()
    s.part("C", "C5", (32.4, yvm), (32.4, 24.4), None)
    s.texts.pop()
    s.ground((31.2, 24.4))
    s.ground((32.4, 24.4))
    s.text((30.85, 24.95), "C4\n100 µF\n16 V", 6.2, ha="right")
    s.text((32.75, 24.95), "C5\n100 nF", 6.2)
    s.ground(u4["GND"])
    s.part("R", "R11", u4["AISEN"], (30.0, 16.8), "0.25 Ω\n≥0.5 W, 1206")
    s.ground((30.0, 16.8))

    # ACS712 in series with motor lead A
    box = (33.6, 22.0, 36.6, 24.2)
    u5 = s.ic("U5", box, [("IP+", "L", 23.1), ("IP-", "R", 23.1, "IP−"), ("VCC", "T", 35.1),
                          ("GND", "B", 34.5), ("OUT", "B", 35.7)])
    s.text((35.1, 23.3), "ACS712", 7.2, ha="center")
    s.text((35.1, 22.9), "-05B · 5 A", 5.8, MUTED, ha="center")
    s.text((box[0], box[3] + 0.12), "U5", 8.5, weight="bold", va="bottom")
    s.wire(u4["AOUT1"], u5["IP+"])
    s.power(u5["VCC"], "+5V")
    s.ground(u5["GND"])
    s.wire(u5["IP-"], (37.8, 23.1))
    s.flag((37.8, 23.1), "MOTOR_A")
    s.part("R", "R9", u5["OUT"], (35.7, 19.6), "1 kΩ")
    s.wire((35.7, 19.6), (38.4, 19.6))
    s.flag((38.4, 19.6), "I_SENSE")
    s.dot((36.6, 19.6))
    s.dot((37.6, 19.6))
    s.part("C", "C6", (36.6, 19.6), (36.6, 18.0), "1 µF", side="left")
    s.part("R", "R10", (37.6, 19.6), (37.6, 18.0), "100 kΩ")
    s.ground((36.6, 18.0))
    s.ground((37.6, 18.0))
    s.wire(u4["AOUT2"], (32.8, 20.6), (32.8, 16.2), (37.8, 16.2))
    s.flag((37.8, 16.2), "MOTOR_B")

    # power entry
    box = (2.4, 12.0, 4.0, 13.6)
    j2 = s.ic("J2", box, [("1", "R", 13.2, "+"), ("2", "R", 12.4, "−")])
    s.pin_numbers(j2, {"1": "1", "2": "2"}, box)
    s.text((box[0], box[3] + 0.12), "J2", 8.5, weight="bold", va="bottom")
    s.text((box[0] + 0.6, box[3] + 0.12), "motor supply 6 V", 6.2, MUTED, va="bottom")
    s.wire(j2["1"], (5.0, 13.2))
    s.part("F", "F1", (5.0, 13.2), (6.8, 13.2), "1 A slow", side="top")
    s.wire((6.8, 13.2), (8.4, 13.2))
    s.power((8.4, 13.2), "VM")
    s.wire(j2["2"], (5.4, 12.4))
    s.ground((5.4, 12.4))
    box = (2.4, 9.0, 4.0, 10.6)
    j3 = s.ic("J3", box, [("1", "R", 10.2, "+"), ("2", "R", 9.4, "−")])
    s.pin_numbers(j3, {"1": "1", "2": "2"}, box)
    s.text((box[0], box[3] + 0.12), "J3", 8.5, weight="bold", va="bottom")
    s.text((box[0] + 0.6, box[3] + 0.12), "logic supply 5 V, regulated", 6.2, MUTED, va="bottom")
    s.wire(j3["1"], (8.4, 10.2))
    s.power((8.4, 10.2), "+5V")
    s.wire(j3["2"], (5.4, 9.4))
    s.ground((5.4, 9.4))
    s.text((1.9, 7.9), "VM: 6 V for the example motor; the DRV8833\nworks from 2.7 to 10.8 V, so never 12 V.\n"
                       "+5V also feeds the Nano 5V pin, U3, U5 and\nboth Hall sensors. All grounds are common.",
           6.2, MUTED)

    # U3 supply and spare gates
    box = (11.2, 9.4, 12.6, 11.8)
    u3 = s.ic("U3", box, [("14", "T", 11.9, "VCC"), ("7", "B", 11.9, "GND")])
    s.pin_numbers(u3, {"14": "14", "7": "7"}, box)
    s.text((11.9, 10.6), "U3", 7, ha="center", weight="bold")
    s.wire(u3["14"], (11.9, 13.4))
    s.power((11.9, 13.4), "+5V")
    s.dot((11.9, 12.9))
    s.wire((11.9, 12.9), (13.4, 12.9))
    s.part("C", "C3", (13.4, 12.9), (13.4, 11.0), "100 nF")
    s.ground((13.4, 11.0))
    s.ground(u3["7"])
    for unit, y1, nums in (("C", 12.9, (9, 10, 8)), ("D", 9.9, (12, 13, 11))):
        g = s.gate("U3", unit, (15.6, y1), nums)
        s.wire(g["in1"], (15.0, y1), (15.0, y1 - 0.7))
        s.wire((15.0, y1 - 0.7), g["in2"])
        s.wire((15.0, y1 - 0.7), (15.0, y1 - 1.2))
        s.dot((15.0, y1 - 0.7))
        s.ground((15.0, y1 - 1.2))
        s.noconnect(f"U3.{nums[2]}", g["out"])
    s.text((10.7, 6.5), "Unused inputs tied to GND, outputs 8 and 11 open.\nC3 sits next to pin 14.", 6.2, MUTED)

    # microcontroller
    box = (24.6, 7.2, 27.8, 13.0)
    right = [("D5", 12.5, "ALLOW_EXT"), ("D6", 11.8, "ALLOW_RET"), ("D7", 11.1, "nFAULT"), ("D8", 10.4, "nSLEEP"),
             ("D9", 9.7, "EXT_CMD"), ("D10", 9.0, "RET_CMD"), ("A0", 8.3, "I_SENSE"), ("D13", 7.6, None)]
    left = [("D2", 12.3, "SW1", "EXTEND"), ("D3", 11.0, "SW2", "RETRACT"), ("D4", 9.7, "SW3", "RESET")]
    u6 = s.ic("U6", box, [(k, "R", y) for k, y, _ in right] + [(k, "L", y) for k, y, *_ in left] +
              [("5V", "T", 26.2), ("GND", "B", 26.2)])
    s.text((26.2, 10.4), "Arduino\nNano", 7.4, ha="center")
    s.text((26.2, 9.6), "ATmega328P, 5 V", 5.8, MUTED, ha="center")
    s.text((box[0], box[3] + 0.12), "U6", 8.5, weight="bold", va="bottom")
    for k, y, net in right:
        if net:
            s.flag(u6[k], net)
    s.text((u6["D13"][0] + 0.15, 7.6), "LED L: fault", 6.0, MUTED)
    s.power(u6["5V"], "+5V")
    s.ground(u6["GND"])
    xbus = 21.0
    for k, y, ref, name in left:
        s.part("SW", ref, (22.4, y), u6[k], None, pins=("2", "1"))
        s.texts.pop()
        s.text((23.2, y + 0.62), f"{ref}  {name}", 6.2, ha="center", va="bottom")
        s.wire((22.4, y), (xbus, y))
    s.wire((xbus, left[0][1]), (xbus, 8.9))
    for k, y, *_ in left[1:]:
        s.dot((xbus, y))
    s.ground((xbus, 8.9))
    s.text((19.3, 7.55), "D2–D4: INPUT_PULLUP, button to GND\nD5/D6: INPUT, no pull-up (see note 4)\n"
                         "D7: INPUT_PULLUP · D9/D10: PWM", 6.0, MUTED)

    # truth table
    cols = [31.7, 34.5, 36.05, 37.65, 38.85]
    heads = ["Situation", "ALLOW_RET", "ALLOW_EXT", "Extend", "Retract"]
    rows = [("between the ends", "H", "H", "yes", "yes"),
            ("at the retract end (U1)", "L", "H", "yes", "blocked"),
            ("at the extend end (U2)", "H", "L", "blocked", "yes"),
            ("W3 or W1 open", "L", "H", "yes", "blocked"),
            ("W6 or W4 open", "H", "L", "blocked", "yes"),
            ("both LOW (sensor fault)", "L", "L", "blocked", "blocked")]
    yt = 13.75
    for x, h in zip(cols, heads):
        s.text((x, yt), h, 6.0, MUTED, weight="bold")
    s.line((31.6, yt - 0.3), (40.2, yt - 0.3), BLOCK, 0.6)
    for i, row in enumerate(rows):
        y = yt - 0.75 - 0.6 * i
        for j, (x, v) in enumerate(zip(cols, row)):
            s.text((x, y - 0.08), v, 6.4, "#b02a1f" if v == "blocked" else INK, va="baseline")
    s.text((31.7, 9.15), "AIN1 = EXT_CMD · ALLOW_EXT\nAIN2 = RET_CMD · ALLOW_RET", 7, NET, weight="bold")
    s.text((31.7, 7.6), "Not detected: an open GND wire (W2/W5), a signal\nshorted to +5 V or a lost magnet. "
                        "The current limit\nand the 30 s run timeout are the backup.", 6.0, MUTED)

    notes = ["NOTES",
             "1. Never feed VM into the Nano 5V pin. If the Nano is on USB, J3 may stay connected (the Nano's USB diode "
             "blocks back-feed).",
             "2. Current limit: cut the AISEN-to-GND break point on the back of the Pololu #2130 and solder R11 on its 1206 "
             "pads → chopping at about\n    0.2 V / 0.25 Ω = 0.8 A (0.64–0.96 A). Channel B is unused. SLP is pulled high "
             "on the carrier; FLT is open-drain (D7 uses INPUT_PULLUP).",
             "3. U5 must be the ACS712-05B (185 mV/A). The firmware zeroes it at power-up and trips at 550 mA for 150 ms. "
             "These are start values: measure the motor.",
             "4. R5–R8 hold the gate inputs and AIN1/AIN2 LOW while the Nano resets, so the motor cannot start by itself. "
             "Keep D5/D6 plain INPUT: an\n    internal pull-up would make a broken W3/W6 read HIGH.",
             "5. First power-up at low voltage, rod disconnected: EXT_CMD must extend. If it retracts, swap W7 and W8 at J1."]
    y = 4.95
    for i, n in enumerate(notes):
        s.text((1.7, y), n, 7 if i == 0 else 6.3, INK if i == 0 else MUTED,
               weight="bold" if i == 0 else "normal", va="top")
        y -= 0.42 + 0.3 * n.count("\n") + (0.08 if i == 0 else 0)
    s.check(NETLIST[2], NO_CONNECT[2])
    return s


FIRMWARE_NETS = {"EXTEND_BUTTON": "BTN_EXT", "RETRACT_BUTTON": "BTN_RET", "RESET_BUTTON": "BTN_RST",
                 "DRIVER_FAULT": "nFAULT", "DRIVER_SLEEP": "nSLEEP", "IN1": "EXT_CMD", "IN2": "RET_CMD",
                 "CURRENT": "I_SENSE", "ALLOW_EXTEND": "ALLOW_EXT", "ALLOW_RETRACT": "ALLOW_RET"}


def check_firmware_pins():
    """The pin constants in the Arduino sketch must land on the nets drawn at the Nano (U6)."""
    sketch = (OUT / "actuator_protection" / "actuator_protection.ino").read_text()
    pins = dict(re.findall(r"\b([A-Z_0-9]+)\s*=\s*(A?\d+)\b", " ".join(
        line for line in sketch.splitlines() if line.startswith("constexpr uint8_t"))))
    for const, net in FIRMWARE_NETS.items():
        pin = pins[const] if pins[const].startswith("A") else "D" + pins[const]
        assert f"U6.{pin}" in NETLIST[2][net], f"firmware {const}={pins[const]} is not on net {net}"
    assert pins["FAULT_LED"] == "13" and "U6.D13" in NO_CONNECT[2]
    return len(FIRMWARE_NETS) + 1


def load_inputs():
    params, lengths = {}, {}
    magnet = dict(operate=3.85, release=4.25, peak=98.0, lobe=-2.45)
    if (ROOT / "parameters.json").exists():
        params = json.loads((ROOT / "parameters.json").read_text())
    if (ROOT / "wire_lengths.csv").exists():
        with open(ROOT / "wire_lengths.csv") as f:
            lengths = {r["wire_id"]: float(r["model_centerline_mm"]) for r in csv.DictReader(f)}
    if (ROOT / "magnet_trigger.json").exists():
        nominal = next(iter(json.loads((ROOT / "magnet_trigger.json").read_text())["cases"].values()))
        magnet = dict(operate=nominal["operate_offset_mm"]["typ"], release=nominal["release_offset_mm"]["typ"],
                      peak=nominal["peak_mT"], lobe=nominal["reverse_lobe_peak_mT"])
    return params, lengths, magnet


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sheets = [sheet1(*load_inputs()), sheet2()]
    with PdfPages(OUT / "schematic.pdf", metadata={"Title": "Excavator arm actuator V5 - schematic",
                                                    "Subject": "Sheet 1 inside the actuator, sheet 2 controller"}) as pdf:
        for s in sheets:
            fig = s.render()
            fig.savefig(OUT / f"schematic_sheet{s.number}.svg", facecolor="white")
            fig.savefig(OUT / f"schematic_sheet{s.number}.png", dpi=150, facecolor="white")
            pdf.savefig(fig, facecolor="white")
    with open(OUT / "netlist.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sheet", "net", "pins"])
        for sheet, nets in NETLIST.items():
            for net, pins in nets.items():
                w.writerow([sheet, net, " ".join(sorted(pins))])
            for pin in sorted(NO_CONNECT[sheet]):
                w.writerow([sheet, "(no connection)", pin])
    for s in sheets:
        print(f"sheet {s.number}: {s.report}")
    print(f"firmware pin constants match the netlist: {check_firmware_pins()} pins")


if __name__ == "__main__":
    main()

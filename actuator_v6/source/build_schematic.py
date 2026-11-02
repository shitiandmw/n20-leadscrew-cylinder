"""Schematic of the V6 end-stop board, drawn from board.py's netlist and checked against it.

python source/build_schematic.py [--root DIR]
    -> electronics/schematic.pdf, .svg, .png (A4 landscape), electronics/netlist.csv,
       source/schematic_links.json (hit areas and net segments for the 3D preview)
The title block lists the board lengths in DIR/parameters.json (build_v6.py); DIR defaults to
this package (V6-S and V6-L). The circuit is the same for every length.
After drawing, the script rebuilds the connectivity of the drawn wires (end points, T-junctions
and net flags) and stops if it differs from the netlist in board.py plus the motor.
"""
from collections import Counter, defaultdict
from pathlib import Path
import argparse
import csv
import json
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "actuator-v6"          # stable ids: the SVG only changes with the drawing
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle
import schemdraw
import schemdraw.elements as elm
import board as BD
from pcb_export import REV

ROOT = Path(__file__).resolve().parent.parent       # package folder (--root)
OUT = ROOT / "electronics"
VARIANTS = {}                                        # name -> parameters, from ROOT/parameters.json
W, H = 29.7, 21.0                       # A4 landscape, 1 drawing unit = 1 cm
INK, MUTED, NET, FRAME = "#1d2a30", "#5f6f75", "#1f5f8b", "#8d989c"
IC_FILL, TAG_FILL, BLOCK = "#f5f7f8", "#eaf2f8", "#b9c3c7"
WIRE = {"W1": ("#d7261e", "red"), "W2": ("#222222", "black"), "W3": ("#f07c12", "orange"),
        "W4": ("#8e3bc9", "purple")}
DATE = "2026-10-28"


def expected_netlist():
    nets = defaultdict(set)
    for ref, (kind, netmap, role) in BD.COMPONENTS.items():
        for pad, net in netmap.items():
            nets[net].add(f"{ref}.{pad}")
    nets["MOT+"].add("M1.+")
    nets["MOT-"].add("M1.-")
    return dict(nets)


def key(p):
    return (round(p[0], 3), round(p[1], 3))


def on_segment(q, a, b):
    """q strictly inside the segment a-b."""
    if q in (a, b):
        return False
    cross = (b[0] - a[0]) * (q[1] - a[1]) - (b[1] - a[1]) * (q[0] - a[0])
    if abs(cross) > 1e-6:
        return False
    return min(a[0], b[0]) - 1e-6 <= q[0] <= max(a[0], b[0]) + 1e-6 and \
        min(a[1], b[1]) - 1e-6 <= q[1] <= max(a[1], b[1]) + 1e-6


class Sheet:
    def __init__(self, title):
        self.title = title
        self.d = schemdraw.Drawing(show=False)
        self.d.config(unit=1.5, inches_per_unit=1 / 2.54, fontsize=7, lw=1.0, color=INK, margin=0)
        self.d.add(elm.Line().endpoints((0, 0), (W, H)).color("white").linewidth(0))   # page extent
        self.texts, self.rects = [], []
        self.wires, self.pins, self.names, self.dots = [], {}, [], []
        self.hits = {}                  # ref -> (x0, y0, x1, y1), for the 3D preview
        self.wire_nets = []
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

    def hit(self, ref, box, pad=0.15):
        x0, y0, x1, y1 = box
        old = self.hits.get(ref)
        box = (x0 - pad, y0 - pad, x1 + pad, y1 + pad)
        if old:
            box = (min(old[0], box[0]), min(old[1], box[1]), max(old[2], box[2]), max(old[3], box[3]))
        self.hits[ref] = tuple(round(v, 3) for v in box)

    def hit_element(self, ref, e, pad=0.15):
        b = e.get_bbox(transform=True)
        self.hit(ref, (b.xmin, b.ymin, b.xmax, b.ymax), pad)

    # ---- connectivity-carrying elements ---------------------------------------
    def wire(self, *pts, color=INK, lw=1.0):
        for a, b in zip(pts, pts[1:]):
            self.line(a, b, color, lw)
            self.wires.append((key(a), key(b)))

    def dot(self, p):
        self.d.add(elm.Dot(radius=0.07).at(p))
        self.dots.append(key(p))

    def part(self, kind, ref, a, b, value, side="right", pins=("1", "2"), gap=0.4):
        shape = {"R": elm.ResistorIEC, "C": elm.Capacitor, "D": elm.Diode, "DS": elm.Schottky,
                 "TVS": elm.DiodeTVS, "PTC": elm.Thermistor, "M": elm.Motor}[kind]()
        e = self.d.add(shape.endpoints(a, b))
        self.pins[f"{ref}.{pins[0]}"], self.pins[f"{ref}.{pins[1]}"] = key(a), key(b)
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        label = f"{ref}\n{value}" if value else ref
        if abs(a[0] - b[0]) < 1e-6:     # vertical part
            self.text((mx + gap if side == "right" else mx - gap, my), label,
                      ha="left" if side == "right" else "right")
            n = max(len(s) for s in label.split("\n"))
            x0 = mx + gap if side == "right" else mx - gap - 0.13 * n
            self.hit(ref, (x0, my - 0.3, x0 + 0.13 * n, my + 0.3), 0.05)
        else:
            self.text((mx, my + gap if side == "top" else my - gap), label.replace("\n", "  "), ha="center",
                      va="bottom" if side == "top" else "top")
        self.hit_element(ref, e)
        return e

    def flag(self, p, net, toward="right", text=None, color=NET):
        """Net flag; the point sits on the wire end, the body points away from it."""
        text = text or net
        width = max(0.8, 0.42 + 0.15 * len(text))
        tag = elm.Tag(width=width, height=0.42).at(p).color(color).fill(TAG_FILL)
        self.d.add(tag.right() if toward == "right" else tag.left())
        cx = p[0] + (width / 2 + 0.06) * (1 if toward == "right" else -1)
        self.text((cx, p[1]), text, 6.6, color, ha="center")
        self.names.append((key(p), net))
        return width

    def port(self, p, net, label, sub):
        """Off-board connection (the user's driver): an open terminal that names the net."""
        self.d.add(elm.Dot(radius=0.11, open=True).at(p))
        self.names.append((key(p), net))
        self.text((p[0] - 0.25, p[1] + 0.03), label, 9.5, INK, ha="right", weight="bold")
        self.text((p[0] - 0.25, p[1] - 0.42), sub, 5.6, MUTED, ha="right")

    def pad(self, ref, p, label, above=True):
        """Wire pad on the board edge: a square with the cable or motor lead soldered on."""
        x, y = p
        self.rect(x - 0.17, y - 0.17, x + 0.17, y + 0.17, edge="#8a6d1d", fill="#e8c96a", lw=0.8, z=3)
        self.pins[f"{ref}.1"] = key(p)
        self.text((x, y + (0.3 if above else -0.3)), label, 6.0, MUTED, ha="center", va="bottom" if above else "top")
        self.hit(ref, (x - 0.25, y - 0.25, x + 0.25, y + 0.25), 0.05)

    def ic(self, ref, box, pins, lead=0.4, name_size=6.2):
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
                self.text((pos, y1 - 0.1), name, name_size, ha="center", va="top")
            else:
                self.text((pos, y0 + 0.1), name, name_size, ha="center", va="bottom")
        self.hit(ref, (x0 - lead, y0 - lead, x1 + lead, y1 + lead), 0.05)
        return ends

    def pin_numbers(self, ends, numbers, box):
        x0, y0, x1, y1 = box
        for k, num in numbers.items():
            x, y = ends[k]
            if x < x0:
                self.text((x0 - 0.08, y + 0.04), num, 5.6, MUTED, ha="right", va="bottom")
            elif x > x1:
                self.text((x1 + 0.08, y + 0.04), num, 5.6, MUTED, va="bottom")
            elif y > y1:
                self.text((x + 0.07, y1 + 0.06), num, 5.6, MUTED, va="bottom")
            else:
                self.text((x + 0.07, y0 - 0.06), num, 5.6, MUTED, va="top")

    # ---- connectivity check --------------------------------------------------
    def check(self, expected):
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
        drawn, root_of = {}, {}
        for root, g in groups.items():
            if len(g["names"]) > 1:
                errors.append(f"short between {sorted(g['names'])}")
            if not g["pins"]:
                errors.append(f"label {sorted(g['names'])} with no pin")
                continue
            drawn[frozenset(g["pins"])] = g["names"]
            root_of[frozenset(g["pins"])] = root
        matched, net_of_root = set(), {}
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
                net_of_root[root_of[frozenset(pins)]] = net
        for pins, names in drawn.items():
            if pins not in matched:
                errors.append(f"unexpected net {sorted(pins)} {sorted(names)}")
        if errors:
            raise SystemExit("schematic connectivity check failed:\n  " + "\n  ".join(errors))
        self.wire_nets = [(a, b, net_of_root[find(a)]) for a, b in self.wires]
        self.report = dict(nets=len(expected), pins=len(self.pins), junctions=len(junctions))
        return self.report

    # ---- page furniture and output -------------------------------------------
    def frame(self, heading, intro):
        self.rect(0.5, 0.5, W - 0.5, H - 0.5, edge=FRAME, lw=1.3)
        self.rect(1.0, 1.0, W - 1.0, H - 1.0, edge=FRAME, lw=0.7)
        cols, rows = 6, "ABCD"
        cw, rh = (W - 2.0) / cols, (H - 2.0) / len(rows)
        for i in range(cols):
            x = 1.0 + cw * i
            if i:
                self.line((x, 0.5), (x, 1.0), FRAME, 0.7)
                self.line((x, H - 1.0), (x, H - 0.5), FRAME, 0.7)
            for y in (0.75, H - 0.75):
                self.text((x + cw / 2, y), str(i + 1), 6, MUTED, ha="center")
        for i, r in enumerate(rows):
            y = H - 1.0 - rh * i
            if i:
                self.line((0.5, y), (1.0, y), FRAME, 0.7)
                self.line((W - 1.0, y), (W - 0.5, y), FRAME, 0.7)
            for x in (0.75, W - 0.75):
                self.text((x, y - rh / 2), r, 6, MUTED, ha="center")
        self.text((1.6, 19.45), heading, 12.5, weight="bold")
        self.text((1.6, 18.95), intro, 7.0, MUTED)
        x0, x1 = 19.6, W - 1.0
        self.rect(x0, 1.0, x1, 4.4, edge=FRAME, fill="white", lw=1.0, z=1.5)
        for y in (3.3, 2.5, 1.6):
            self.line((x0, y), (x1, y), FRAME, 0.7)
        self.text((x0 + 0.3, 3.9), self.title, 10.5, weight="bold")
        self.text((x0 + 0.3, 3.5), "Two-wire actuator V6  ·  N20 6 V 150 rpm gearmotor with M3 leadscrew",
                  6.0, MUTED)
        self.text((x0 + 0.3, 3.05), "Board: 2 layers, 0.8 mm FR4, 8 mm wide, all parts on one side.", 6.0)
        lengths = [f"{p['pcb_length']:g} mm (V6-{v})" for v, p in VARIANTS.items()]
        lengths = " or ".join([", ".join(lengths[:-1]), lengths[-1]] if len(lengths) > 1 else lengths)
        self.text((x0 + 0.3, 2.72), f"Length {lengths}.", 6.0)
        cells = [("SHEET", "1 of 1"), ("REVISION", REV), ("DATE", DATE), ("V6 BOARDS", " · ".join(VARIANTS))]
        cw = (x1 - x0) / len(cells)
        for i, (cap, val) in enumerate(cells):
            cx = x0 + cw * i
            if i:
                self.line((cx, 1.6), (cx, 2.5), FRAME, 0.7)
            self.text((cx + 0.2, 2.32), cap, 5.2, MUTED)
            self.text((cx + 0.2, 1.88), val, 7.6)

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
            me = Path(__file__).resolve()                     # named relative to the package, else the repository
            me = me.relative_to(ROOT) if me.is_relative_to(ROOT) else me.relative_to(me.parents[2])
            ax.text(19.9, 1.3, f"Drawn by {me.as_posix()}; connectivity re-derived from the drawing\n"
                               f"and checked against board.py: {r['nets']} nets, {r['pins']} pins, "
                               f"{r['junctions']} junctions, no differences.",
                    fontsize=5.0, color=MUTED, va="center", linespacing=1.2, zorder=6)
        return fig


# ---------------------------------------------------------------------------------------------
X_C, X_PIN, BOX_X, X_S, X_G, X_D, X_DK, X_DA = 5.2, 7.0, (6.4, 9.2), 9.6, 10.35, 11.1, 11.5, 13.1
VALUES = {k: v[0] for k, v in BD.PARTS.items()}


def stop_cell(s, sign, y0, refs, feed_net, end_name):
    """One end stop. sign=+1 draws it above its rail (U1 on lead A), -1 below (U2 on lead B):
    Hall switch, gate pull-up, hold capacitor, feed diode from the other lead, and the MOSFET in
    the lead with its Schottky bypass."""
    u, q, r, c, dfeed, dpar = refs
    y_cell, y_out, y_vcc = y0 + sign * 1.9, y0 + sign * 3.85, y0 + sign * 5.8
    lo, hi = sorted((y0 + sign * 2.9, y0 + sign * 4.8))
    box = (BOX_X[0], lo, BOX_X[1], hi)
    vcc_side, gnd_side = ("T", "B") if sign > 0 else ("B", "T")
    p = s.ic(u, box, [("1", vcc_side, X_PIN, "VCC"), ("3", gnd_side, X_PIN, "GND"), ("2", "R", y_out, "OUT")])
    s.pin_numbers(p, {"1": "1", "2": "2", "3": "3"}, box)
    s.text(((box[0] + box[2]) / 2 + 0.35, y_out + 0.2), "DRV5033AJ", 6.8, ha="center")
    s.text(((box[0] + box[2]) / 2 + 0.35, y_out - 0.22), "Hall switch", 5.8, MUTED, ha="center")
    s.text((box[0], (hi if sign > 0 else lo) + (0.1 if sign > 0 else -0.1)), u, 8.5, weight="bold",
           va="bottom" if sign > 0 else "top")
    s.wire(p["1"], (X_PIN, y_vcc))
    s.wire(p["3"], (X_PIN, y_cell))
    s.wire((X_C, y_cell), (X_PIN, y_cell))
    s.wire((X_C, y_cell), (X_C, y0))
    s.wire((X_C, y_vcc), (X_PIN, y_vcc), (X_G, y_vcc), (X_DK, y_vcc))
    s.wire(p["2"], (X_G, y_out))
    for pt in ((X_C, y_cell), (X_C, y0), (X_PIN, y_vcc), (X_G, y_vcc), (X_G, y_out)):
        s.dot(pt)
    s.part("C", c, (X_C, y_vcc), (X_C, y_cell), VALUES["C1U"].replace(" X5R", ""), side="left")
    s.part("R", r, (X_G, y_vcc), (X_G, y_out), VALUES["R1M"].replace(" 1 %", ""))
    s.part("D", dfeed, (X_DA, y_vcc), (X_DK, y_vcc), VALUES["D_SIG"], pins=("2", "1"), side="top")
    s.flag((X_DA, y_vcc), feed_net, "right")
    # MOSFET in the lead: drain on the motor side, source on the cable side, gate toward the cell
    fet = elm.NFet(bulk=True).theta(90).flip() if sign > 0 else elm.NFet(bulk=True).theta(-90)
    e = s.d.add(fet.at((X_D, y0)))
    gate = tuple(e.absanchors["gate"])
    s.pins[f"{q}.1"], s.pins[f"{q}.2"], s.pins[f"{q}.3"] = key(gate), key((X_S, y0)), key((X_D, y0))
    s.hit_element(q, e)
    s.wire((X_G, y_out), gate)
    s.text((X_D + 0.3, y0 + sign * 1.3), f"{q}  AO3400A", 7.0, va="center")
    s.text((X_D + 0.3, y0 + sign * 0.92), "N-MOSFET", 5.6, MUTED, va="center")
    yp = y0 - sign * 1.1                                          # Schottky across the MOSFET
    s.wire((X_S, y0), (X_S, yp))
    s.part("DS", dpar, (X_S, yp), (X_D, yp), VALUES["D_SCH"], pins=("2", "1"), side="bottom" if sign > 0 else "top")
    s.wire((X_D, yp), (X_D, y0))
    s.dot((X_S, y0))
    s.dot((X_D, y0))
    # net names and the one-line story of the cell
    vname = "VCC_RET" if sign > 0 else "VCC_EXT"
    gname = "G_RET" if sign > 0 else "G_EXT"
    s.text((8.4, y_vcc + 0.12 * sign), vname, 5.8, NET, ha="center", va="bottom" if sign > 0 else "top")
    s.text((X_G + 0.15, (y_out + y0 + sign * 1.37) / 2 + sign * 0.35), gname, 5.8, NET)
    s.text((X_C + 0.35, y_cell + sign * 0.14), "A" if sign > 0 else "B", 5.8, NET, va="bottom" if sign > 0 else "top")
    ys = (y0 + y_cell) / 2
    s.text((X_C + 0.35, ys + 0.2), f"{u} sits at the {end_name} end.", 6.2, MUTED)
    s.text((X_C + 0.35, ys - 0.2), f"Magnet there: OUT low, {q} off.", 6.2, MUTED)


def draw():
    s = Sheet("End-stop board · schematic")
    s.frame("V6 end-stop board", "Two wires in. Polarity sets the direction; a Hall switch at each end cuts that "
            "direction off, and reversing always works. No microcontroller.")
    yA, yB = 11.8, 7.8
    s.block(2.9, 1.2, 19.3, 18.5, "END-STOP BOARD  ·  inside the actuator")
    # cable side: the user's driver
    s.port((1.6, yA), "A", "A", "red")
    s.port((1.6, yB), "B", "B", "black")
    s.wire((1.6, yA), (3.4, yA), color=WIRE["W1"][0], lw=3.0)
    s.wire((1.6, yB), (3.4, yB), color=WIRE["W2"][0], lw=3.0)
    s.text((2.5, yA + 0.16), "W1", 5.6, MUTED, ha="center", va="bottom")
    s.text((2.5, yB - 0.16), "W2", 5.6, MUTED, ha="center", va="top")
    s.hit("W1", (1.6, yA - 0.1, 3.3, yA + 0.1), 0.12)
    s.hit("W2", (1.6, yB - 0.1, 3.3, yB + 0.1), 0.12)
    s.pad("J_A", (3.4, yA), "J_A")
    s.pad("J_B", (3.4, yB), "J_B", above=False)
    # main rails
    s.wire((3.4, yA), (X_C, yA), (X_S, yA))
    s.wire((3.4, yB), (X_C, yB), (X_S, yB))
    s.dot((3.4, yA))
    s.dot((3.4, yB))
    s.text((7.4, yA + 0.12), "A", 5.8, NET, ha="center", va="bottom")
    s.text((7.4, yB - 0.12), "B", 5.8, NET, ha="center", va="top")
    stop_cell(s, +1, yA, ("U1", "Q1", "R1", "C1", "D1", "D4"), "B", "retract")
    stop_cell(s, -1, yB, ("U2", "Q2", "R2", "C2", "D2", "D5"), "A", "extend")
    xf0, xf1, xc3, xd3, xj, xm = 12.9, 14.9, 15.7, 17.0, 18.9, 21.7
    s.wire((X_D, yA), (xf0, yA))
    s.text(((X_D + xf0) / 2, yA - 0.12), "A_SW", 5.8, NET, ha="center", va="top")
    s.part("PTC", "F1", (xf0, yA), (xf1, yA), "0.12 A PPTC", side="top", gap=0.55)
    s.wire((xf1, yA), (xc3, yA), (xd3, yA), (xj, yA))
    s.wire((X_D, yB), (xc3, yB), (xd3, yB), (xj, yB))
    for pt in ((xc3, yA), (xd3, yA), (xc3, yB), (xd3, yB), (xj, yA), (xj, yB)):
        s.dot(pt)
    s.part("C", "C3", (xc3, yA), (xc3, yB), "100 nF", side="left")
    s.part("TVS", "D3", (xd3, yA), (xd3, yB), "SMF7.0CA\n±7 V TVS")
    s.text(((xd3 + xj) / 2, yA + 0.12), "MOT+", 5.8, NET, ha="center", va="bottom")
    s.text((13.3, yB + 0.12), "MOT−", 5.8, NET, ha="center", va="bottom")
    s.pad("J_M+", (xj, yA), "J_M+")
    s.pad("J_M-", (xj, yB), "J_M−", above=False)
    # motor side
    s.wire((xj, yA), (xm, yA), color=WIRE["W3"][0], lw=3.0)
    s.wire((xj, yB), (xm, yB), color=WIRE["W4"][0], lw=3.0)
    s.text(((xj + xm) / 2 + 0.2, yA + 0.16), "W3 orange", 5.6, MUTED, ha="center", va="bottom")
    s.text(((xj + xm) / 2 + 0.2, yB - 0.16), "W4 purple", 5.6, MUTED, ha="center", va="top")
    s.hit("W3", (xj + 0.2, yA - 0.1, xm, yA + 0.1), 0.12)
    s.hit("W4", (xj + 0.2, yB - 0.1, xm, yB + 0.1), 0.12)
    s.part("M", "M1", (xm, yA), (xm, yB), "N20 6 V", side="left", pins=("+", "-"), gap=0.8)
    s.text((xm + 0.25, yA - 0.35), "+", 7.5, MUTED)
    s.text((xm + 0.25, yB + 0.35), "−", 7.5, MUTED)
    notes(s)
    return s


NOTES = [
    ("HOW IT WORKS", True),
    ("A positive, B negative: the rod extends.", False),
    ("Current: A → D4 → F1 → M1 → Q2 → B.", False),
    ("At the extend end U2 sees the magnet, pulls", False),
    ("Q2's gate low, and the motor stops.", False),
    ("", False),
    ("B positive, A negative: the rod retracts.", False),
    ("Current: B → D5 → M1 → F1 → Q1 → A.", False),
    ("U1 stops it at the retract end the same way.", False),
    ("", False),
    ("At an end, the opposite polarity still runs:", False),
    ("D4 / D5 (and the MOSFET body diodes) carry", False),
    ("the current around the switch that is off.", False),
    ("", False),
    ("Each Hall switch is fed from the other wire", False),
    ("through D1 / D2, so it only runs while its own", False),
    ("direction is driven. C1 / C2 hold its supply.", False),
    ("", False),
    ("PROTECTION", True),
    ("F1: resettable fuse, 0.12 A hold. A jammed rod", False),
    ("trips it in about 1.6 s (simulated); it resets", False),
    ("when the power is removed for a few seconds.", False),
    ("D3 clamps the motor's switch-off spike; C3", False),
    ("suppresses brush noise.", False),
    ("", False),
    ("DRIVE", True),
    ("Any H-bridge or reversing (DPDT) switch.", False),
    ("6 V nominal, 7 V maximum (D3). PWM up to", False),
    ("20 kHz simulated. Stopped at an end, the", False),
    ("board draws about 2.2 mA (the Hall switch).", False),
]


def notes(s):
    y = 18.2
    for line, bold in NOTES:
        if bold:
            s.text((23.0, y), line, 7.0, INK, weight="bold")
        elif line:
            s.text((23.0, y), line, 6.5, INK)
        y -= 0.42 if line else 0.22


def main():
    global ROOT, OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=ROOT, help="package folder with parameters.json")
    ROOT = ap.parse_args().root.resolve()
    OUT = ROOT / "electronics"
    VARIANTS.update(json.loads((ROOT / "parameters.json").read_text()))
    OUT.mkdir(parents=True, exist_ok=True)
    (ROOT / "source").mkdir(exist_ok=True)
    s = draw()
    expected = expected_netlist()
    s.check(expected)
    fig = s.render()
    fig.savefig(OUT / "schematic.svg", facecolor="white", metadata={"Date": None})
    fig.savefig(OUT / "schematic.png", dpi=200, facecolor="white")
    with PdfPages(OUT / "schematic.pdf", metadata={"Title": "Actuator V6 - end-stop board schematic",
                                                    "Subject": "Two-wire end-stop board, "
                                                               + ", ".join(f"V6-{v}" for v in VARIANTS)}) as pdf:
        pdf.savefig(fig, facecolor="white")
    with open(OUT / "netlist.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["net", "pins (ref.pad)", "note"])
        for net in BD.NETS:
            note = "M1 via wire W3 (orange)" if net == "MOT+" else "M1 via wire W4 (purple)" if net == "MOT-" else \
                "cable wire W1 (red)" if net == "A" else "cable wire W2 (black)" if net == "B" else ""
            w.writerow([net, " ".join(sorted(expected[net])), note])
    links = dict(page_cm=[W, H], parts=s.hits,
                 nets=[dict(net=n, a=list(a), b=list(b)) for a, b, n in s.wire_nets],
                 wires={k: dict(color=c, name=n) for k, (c, n) in WIRE.items()})
    (ROOT / "source" / "schematic_links.json").write_text(json.dumps(links, indent=1))
    print(s.report, len(s.hits), "hit areas,", len(s.wire_nets), "net segments")


if __name__ == "__main__":
    main()

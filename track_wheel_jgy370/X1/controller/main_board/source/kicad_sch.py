"""KiCad 9 schematic writer: symbol libraries, a wired drawing API and file output.

Coordinates are sheet millimetres with y down, on the 1.27 mm grid. Library symbols are read from
the KiCad 9 symbol libraries (KICAD_SYMBOL_DIR) and embedded flattened, as KiCad does.

Drawing model: place() a netlist part, then connect its pins with w() (orthogonal wires), pwr()
(power symbols), lab() (net labels) or term() (a stub and a label/power symbol named from the
netlist). finish() splits wires where something lands on them, adds junction dots, and refuses a
sheet with any pin left unattached. Whether the drawing carries the right nets is checked by KiCad
itself (check_kicad.py compares KiCad's netlist export with netlist.py).
"""
import copy
import math
import os
import uuid
from collections import defaultdict
from pathlib import Path

import netlist as NL
import sexp
from sexp import Sym as S

SYMDIR = Path(os.environ.get("KICAD_SYMBOL_DIR", "/tmp/kicad-lib/symbols"))
PROJECT = "X1_main"
NS = uuid.UUID("6f1c3a52-6a3e-4c55-9a41-1d2a3b4c5d6e")
DATE = "2026-11-05"
G = 2.54
POWER_SYMBOL = {"GND": "power:GND", "+3V3": "power:+3V3", "+5V": "power:+5V", "+6V": "power:+6V",
                "VBUS": "power:VBUS", "VBAT": "X1_main:VBAT"}


def uid(*key):
    return str(uuid.uuid5(NS, "/".join(str(k) for k in key)))


def r4(v):
    return round(v + 0.0, 4) + 0.0


def pt(x, y):
    return (r4(x), r4(y))


def font(size=1.27, bold=False):
    f = [S("font"), [S("size"), size, size]]
    if bold:
        f.append([S("bold"), S("yes")])
    return f


def prop(name, value, at=(0, 0, 0), hide=False, justify=None, size=1.27):
    eff = [S("effects"), font(size)]
    if justify:
        eff.append([S("justify")] + [S(j) for j in justify])
    if hide:
        eff.append([S("hide"), S("yes")])
    return [S("property"), name, value, [S("at")] + [r4(a) for a in at], eff]


# ---- libraries ------------------------------------------------------------------------------
class Library:
    def __init__(self):
        self.files, self.project = {}, {}

    def _lib(self, lib):
        if lib not in self.files:
            tree = sexp.parse((SYMDIR / f"{lib}.kicad_sym").read_text())[0]
            self.files[lib] = {s[1]: s for s in sexp.find_all(tree, "symbol")}
        return self.files[lib]

    def flat(self, lib, name):
        syms = self.project if lib == PROJECT else self._lib(lib)
        s = syms[name]
        ext = sexp.find(s, "extends")
        if not ext:
            return copy.deepcopy(s)
        return rename(merge(self.flat(lib, ext[1]), s), name)

    def get(self, lib_id):
        lib, name = lib_id.split(":", 1)
        s = self.flat(lib, name)
        s[1] = lib_id
        return s


def merge(parent, child):
    """Child properties over the parent's body (KiCad 'extends'), keeping the parent's name so that
    rename() carries the unit sub-symbols (Parent_0_1 ...) over to the child."""
    out = [S("symbol"), parent[1]]
    props = {p[1]: p for p in sexp.find_all(child, "property")}
    attrs, plist, subs = [], [], []
    for item in parent[2:]:
        h = sexp.head(item)
        if h == "property":
            plist.append(copy.deepcopy(props.pop(item[1], item)))
        elif h == "symbol":
            subs.append(copy.deepcopy(item))
        elif h not in ("extends", "embedded_fonts"):
            attrs.append(copy.deepcopy(item))
    return out + attrs + plist + list(props.values()) + subs + [[S("embedded_fonts"), S("no")]]


def rename(sym, name):
    old = sym[1]
    sym[1] = name
    for sub in sexp.find_all(sym, "symbol"):
        if sub[1].startswith(old + "_"):
            sub[1] = name + sub[1][len(old):]
    return sym


def set_props(sym, **kv):
    for p in sexp.find_all(sym, "property"):
        if p[1] in kv:
            p[2] = kv.pop(p[1])
    for k, v in kv.items():
        idx = max(i for i, it in enumerate(sym) if sexp.head(it) == "property") + 1
        sym.insert(idx, prop(k, v, hide=True))
    return sym


def lib_pin(kind, x, y, angle, name, number, length=2.54, hide=False):
    p = [S("pin"), S(kind), S("line"), [S("at"), x, y, angle], [S("length"), length]]
    if hide:
        p.append([S("hide"), S("yes")])
    return p + [[S("name"), name, [S("effects"), font()]], [S("number"), number, [S("effects"), font()]]]


def drv8876_symbol():
    """TI DRV8876 (PWP, HTSSOP-16 with PowerPAD), pins from SLVSDS7B section 5."""
    left = [("1", "EN/IN1", "input", 5.08), ("2", "PH/IN2", "input", 2.54), ("3", "nSLEEP", "input", 0.0),
            ("5", "VREF", "input", -2.54), ("16", "PMODE", "input", -7.62), ("7", "IMODE", "input", -10.16)]
    right = [("8", "OUT1", "output", 5.08), ("10", "OUT2", "output", 2.54), ("4", "nFAULT", "open_collector", -2.54),
             ("6", "IPROPI", "output", -7.62)]
    top = [("14", "CPL", "passive", -10.16), ("13", "CPH", "passive", -5.08), ("12", "VCP", "passive", 5.08),
           ("11", "VM", "power_in", 10.16)]
    pins = [lib_pin(t, -15.24, y, 0, nm, no) for no, nm, t, y in left]
    pins += [lib_pin(t, 15.24, y, 180, nm, no) for no, nm, t, y in right]
    pins += [lib_pin(t, x, 15.24, 270, nm, no) for no, nm, t, x in top]
    pins += [lib_pin("power_in", 0, -15.24, 90, "GND", "15"),
             lib_pin("passive", 0, -15.24, 90, "PGND", "9", hide=True),
             lib_pin("passive", 0, -15.24, 90, "PAD", "17", hide=True)]
    body = [S("rectangle"), [S("start"), -12.7, 12.7], [S("end"), 12.7, -12.7],
            [S("stroke"), [S("width"), 0.254], [S("type"), S("default")]], [S("fill"), [S("type"), S("background")]]]
    return [S("symbol"), "DRV8876PWP", [S("pin_names"), [S("offset"), 0.762]], [S("exclude_from_sim"), S("no")],
            [S("in_bom"), S("yes")], [S("on_board"), S("yes")],
            prop("Reference", "U", (-12.7, 13.97, 0), justify=["left"]),
            prop("Value", "DRV8876PWP", (12.7, 13.97, 0), justify=["right"]),
            prop("Footprint", NL.KINDS["DRV8876"]["footprint"], hide=True),
            prop("Datasheet", "https://www.ti.com/lit/ds/symlink/drv8876.pdf", hide=True),
            prop("Description", "3.5 A brushed DC H-bridge with current sense and regulation, 4.5-37 V", hide=True),
            [S("symbol"), "DRV8876PWP_0_1", body], [S("symbol"), "DRV8876PWP_1_1"] + pins,
            [S("embedded_fonts"), S("no")]]


def project_symbols(lib):
    """Project library: the DRV8876, and renamed copies of library symbols with the right pinout."""
    syms = {"DRV8876PWP": drv8876_symbol()}
    ao = rename(lib.flat("Transistor_FET", "IRF7404"), "AO4407A")
    syms["AO4407A"] = set_props(ao, Value="AO4407A", Footprint=NL.KINDS["AO4407A"]["footprint"],
                                Datasheet="https://www.aosmd.com/res/datasheets/AO4407A.pdf",
                                Description="-30 V P-channel MOSFET, SO-8 (pins as IRF7404: S 1-3, G 4, D 5-8)")
    tvs = rename(lib.flat("Diode", "SM6T6V8A"), "SMBJ15A")
    syms["SMBJ15A"] = set_props(tvs, Value="SMBJ15A", Datasheet="",
                                Description="600 W unidirectional TVS, 15 V stand-off, SMB (pin 1 cathode)")
    vb = rename(lib.flat("power", "+BATT"), "VBAT")
    set_props(vb, Value="VBAT", Description="Power symbol: the protected 12 V battery bus")
    for p in sexp.walk(vb, "pin"):
        sexp.find(p, "name")[1] = "VBAT"
    syms["VBAT"] = vb
    lib.project = syms
    return syms


def symbol_pins(sym):
    """number -> list of (x, y, angle, type, name), library coordinates (y up), units 0 and 1."""
    out = {}
    for sub in sexp.find_all(sym, "symbol"):
        if int(sub[1].rsplit("_", 2)[-2]) not in (0, 1):
            continue
        for p in sexp.find_all(sub, "pin"):
            at = sexp.find(p, "at")
            out.setdefault(sexp.find(p, "number")[1], []).append(
                (float(at[1]), float(at[2]), float(at[3]), str(p[1]), sexp.find(p, "name")[1]))
    return out


def symbol_bbox(sym):
    """Extent of the symbol graphics (library coordinates), without pins."""
    xs, ys = [], []
    for sub in sexp.find_all(sym, "symbol"):
        for r in sexp.walk(sub, "rectangle"):
            for k in ("start", "end"):
                v = sexp.find(r, k)
                xs.append(float(v[1]))
                ys.append(float(v[2]))
        for pl in sexp.walk(sub, "pts"):
            for xy in sexp.find_all(pl, "xy"):
                xs.append(float(xy[1]))
                ys.append(float(xy[2]))
        for c in sexp.walk(sub, "circle"):
            cc, rr = sexp.find(c, "center"), float(sexp.find(c, "radius")[1])
            xs += [float(cc[1]) - rr, float(cc[1]) + rr]
            ys += [float(cc[2]) - rr, float(cc[2]) + rr]
    if not xs:
        return (-1.27, -1.27, 1.27, 1.27)
    return (min(xs), min(ys), max(xs), max(ys))


def to_sheet(px, py, rot, mirror=False):
    if mirror:
        px = -px
    a = math.radians(rot)
    return px * math.cos(a) - py * math.sin(a), -(px * math.sin(a) + py * math.cos(a))


def outward(pin_angle, rot, mirror=False):
    a = math.radians(pin_angle + 180)
    x, y = to_sheet(math.cos(a), math.sin(a), rot, mirror)
    return round(x), round(y)


LIB = Library()
NETLIST = NL.build()
GLOBAL_NETS = {}


def init():
    syms = project_symbols(LIB)
    sheets_of = defaultdict(set)
    for p in NETLIST.parts.values():
        for net in p["pins"].values():
            if net:
                sheets_of[net].add(p["sheet"])
    GLOBAL_NETS.update({n: len(s) > 1 for n, s in sheets_of.items()})
    return syms


# ---- sheet ----------------------------------------------------------------------------------
class Sheet:
    def __init__(self, key, title, page, root_uuid, paper="A3"):
        self.key, self.title, self.page, self.paper, self.root = key, title, page, paper, root_uuid
        self.items, self.segs, self.lib_ids = [], [], set()
        self.attach = defaultdict(int)     # point -> labels / power pins / no-connects attached
        self.pin_at = defaultdict(list)    # point -> [(ref, pin)]
        self.pins = {}                     # (ref, pin) -> point
        self.placed = []
        self.n = 0
        self.pn = 0
        self.uuid = uid("sheetfile", key)
        self.block_uuid = uid("sheetblock", key)

    def _id(self, *k):
        self.n += 1
        return uid(self.key, self.n, *k)

    # --- primitives
    def w(self, *pts):
        pts = [pt(*p) for p in pts]
        for a, b in zip(pts, pts[1:]):
            if a == b:
                continue
            assert a[0] == b[0] or a[1] == b[1], f"{self.key}: wire not orthogonal {a} {b}"
            self.segs.append((a, b))
        return pts[-1]

    def text(self, s, x, y, size=1.27, bold=False):
        self.items.append([S("text"), s, [S("exclude_from_sim"), S("no")], [S("at"), r4(x), r4(y), 0],
                           [S("effects"), font(size, bold), [S("justify"), S("left"), S("top")]],
                           [S("uuid"), self._id("text")]])

    def nc(self, p):
        p = pt(*p)
        self.attach[p] += 1
        self.items.append([S("no_connect"), [S("at"), p[0], p[1]], [S("uuid"), self._id("nc")]])

    def lab(self, p, net, d=(1, 0), stub=0.0):
        """Net label at p (after an optional stub in direction d); global if the net spans sheets."""
        p = pt(*p)
        if stub:
            p = self.w(p, (p[0] + d[0] * stub, p[1] + d[1] * stub))
        angle = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[tuple(d)]
        just = "left" if angle in (0, 90) else "right"
        self.attach[p] += 1
        if GLOBAL_NETS.get(net, False):
            self.items.append([S("global_label"), net, [S("shape"), S("bidirectional")], [S("at"), p[0], p[1], angle],
                               [S("fields_autoplaced"), S("yes")], [S("effects"), font(), [S("justify"), S(just)]],
                               [S("uuid"), self._id("gl", net)],
                               prop("Intersheetrefs", "${INTERSHEET_REFS}", (p[0], p[1], angle), hide=True,
                                    justify=[just])])
        else:
            self.items.append([S("label"), net, [S("at"), p[0], p[1], angle], [S("fields_autoplaced"), S("yes")],
                               [S("effects"), font(), [S("justify"), S(just), S("bottom")]],
                               [S("uuid"), self._id("lb", net)]])
        return p

    def pwr(self, p, net, d=None):
        """Power symbol at p: GND points down, rails point up, unless d says otherwise."""
        p = pt(*p)
        lib_id = "power:PWR_FLAG" if net == "PWR_FLAG" else POWER_SYMBOL[net]
        natural = (0, 1) if net == "GND" else (0, -1)
        d = tuple(d) if d else natural
        rot = next(r for r in (0, 90, 180, 270)
                   if tuple(round(v) for v in to_sheet(natural[0], -natural[1], r)) == d)
        flag = lib_id == "power:PWR_FLAG"
        self.pn += 1
        ref = f"#{'FLG' if flag else 'PWR'}{self.page}{self.pn:03d}"
        if net == "GND":
            vat = (p[0], p[1] + 4.2, 0)
        elif d == (0, -1):
            vat = (p[0], p[1] - (5.0 if flag else 3.6), 0)
        else:
            vat = (p[0] + d[0] * 4.5, p[1] + d[1] * 4.5, 90 if d[0] else 0)
        self.attach[p] += 1
        self._symbol(lib_id, ref, p, rot, False, ["1"],
                     [prop("Reference", ref, (p[0], p[1], 0), hide=True),
                      prop("Value", "PWR_FLAG" if flag else net, vat)], bom=False)
        return p

    def flag(self, p):
        return self.pwr(p, "PWR_FLAG")

    def gnd(self, p, drop=0.0):
        p = pt(*p)
        if drop:
            p = self.w(p, (p[0], p[1] + drop))
        return self.pwr(p, "GND")

    # --- parts
    def place(self, ref, x, y, rot=0, mirror=False, side="r", fields=None):
        """Place a netlist part; returns {pin number: connection point}."""
        part = NETLIST.parts[ref]
        info = NL.kind_info(part["kind"])
        sym = LIB.get(info["symbol"])
        pins = symbol_pins(sym)
        for num in pins:
            if num not in part["pins"]:
                raise KeyError(f"{ref}: symbol pin {num} has no net in netlist.py")
        for num in part["pins"]:
            if num not in pins:
                raise KeyError(f"{ref}: netlist pad {num} is not a pin of {info['symbol']}")
        o = pt(x, y)
        out = {}
        for num, lst in pins.items():
            px, py, pa, ptype, _ = lst[0]
            dx, dy = to_sheet(px, py, rot, mirror)
            p = pt(o[0] + dx, o[1] + dy)
            out[num] = p
            self.pins[(ref, num)] = p
            if part["pins"][num] is None and ptype == "no_connect":
                self.attach[p] += 1
            self.pin_at[p].append((ref, num))
        self.placed.append(ref)
        bx0, by0, bx1, by1 = symbol_bbox(sym)
        c = [to_sheet(a, b, rot, mirror) for a, b in ((bx0, by0), (bx1, by1), (bx0, by1), (bx1, by0))]
        box = (o[0] + min(a for a, _ in c), o[1] + min(b for _, b in c),
               o[0] + max(a for a, _ in c), o[1] + max(b for _, b in c))
        flds = fields or self._fields(ref, info["value"], o, box, rot, side, mirror)
        extra = {"MPN": info["mpn"], "Role": part["role"]}
        if info.get("lcsc"):
            extra["LCSC"] = info["lcsc"]
        self._symbol(info["symbol"], ref, o, rot, mirror, list(pins), flds, footprint=info["footprint"], extra=extra,
                     dnp=part["dnp"], bom=part["kind"] != "HOLE", board=True)   # holes: on the board, not in the BOM
        return out

    @staticmethod
    def _fields(ref, value, o, box, rot, side, mirror=False):
        """Reference and value text beside the body. KiCad turns field text with the symbol and keeps
        it readable by flipping the justification at 90 and 180 degrees (and horizontally when the
        symbol is mirrored), so that is undone here."""
        fa = 90 if rot in (90, 270) else 0
        flip_v = rot in (90, 180)
        flip_h = flip_v != bool(mirror)

        def j(h, v):
            if flip_h:
                h = {"left": "right", "right": "left"}.get(h, h)
            if flip_v:
                v = {"top": "bottom", "bottom": "top"}.get(v, v)
            return [x for x in (h, v) if x]

        x0, y0, x1, y1 = box
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if side == "r":
            return [prop("Reference", ref, (x1 + 0.8, cy - 1.1, fa), justify=j("left", None)),
                    prop("Value", value, (x1 + 0.8, cy + 1.1, fa), justify=j("left", None))]
        if side == "l":
            return [prop("Reference", ref, (x0 - 0.8, cy - 1.1, fa), justify=j("right", None)),
                    prop("Value", value, (x0 - 0.8, cy + 1.1, fa), justify=j("right", None))]
        if side == "a":
            return [prop("Reference", ref, (cx, y0 - 2.9, fa), justify=j(None, "bottom")),
                    prop("Value", value, (cx, y0 - 0.7, fa), justify=j(None, "bottom"))]
        if side == "b":
            return [prop("Reference", ref, (cx, y1 + 0.7, fa), justify=j(None, "top")),
                    prop("Value", value, (cx, y1 + 2.9, fa), justify=j(None, "top"))]
        if side == "ic":       # above the top-left corner and below the bottom-left corner
            return [prop("Reference", ref, (x0, y0 - 0.8, 0), justify=j("left", "bottom")),
                    prop("Value", value, (x0, y1 + 0.8, 0), justify=j("left", "top"))]
        if side == "icr":      # both to the right of the top-right corner
            return [prop("Reference", ref, (x1 + 1.0, y0 - 2.9, 0), justify=j("left", "bottom")),
                    prop("Value", value, (x1 + 1.0, y0 - 0.7, 0), justify=j("left", "bottom"))]
        if side == "ib":       # under the body, right of the centre (clear of a bottom GND pin)
            return [prop("Reference", ref, (cx + 1.0, y1 + 0.8, 0), justify=j("left", "top")),
                    prop("Value", value, (cx + 1.0, y1 + 2.9, 0), justify=j("left", "top"))]
        raise ValueError(side)

    def term(self, ref, num, d=None, stub=2 * G):
        """End a pin in its netlist net: power symbol or label, after a stub along d (default: outward)."""
        p = self.pins[(ref, num)]
        net = NETLIST.parts[ref]["pins"][num]
        if d is None:
            d = self._outward(ref, num)
        if net is None:
            self.nc(p)
            return p
        e = self.w(p, (p[0] + d[0] * stub, p[1] + d[1] * stub)) if stub else p
        if net in POWER_SYMBOL:
            return self.pwr(e, net, d if net != "GND" or d == (0, 1) else d)
        return self.lab(e, net, d)

    def _outward(self, ref, num):
        for it in self.items[::-1]:
            if sexp.head(it) == "symbol" and any(sexp.head(x) == "uuid" and x[1] == uid(self.key, "sym", ref)
                                                  for x in it):
                at = sexp.find(it, "at")
                mirror = sexp.find(it, "mirror") is not None
                info = NL.kind_info(NETLIST.parts[ref]["kind"])
                pa = symbol_pins(LIB.get(info["symbol"]))[num][0][2]
                return outward(pa, float(at[3]), mirror)
        raise KeyError(ref)

    def _symbol(self, lib_id, ref, p, rot, mirror, pins, fields, footprint="", bom=True, extra=None, dnp=False,
                board=None):
        self.lib_ids.add(lib_id)
        s = [S("symbol"), [S("lib_id"), lib_id], [S("at"), p[0], p[1], rot]]
        if mirror:
            s.append([S("mirror"), S("y")])
        s += [[S("unit"), 1], [S("exclude_from_sim"), S("no")], [S("in_bom"), S("yes" if bom else "no")],
              [S("on_board"), S("yes" if (bom if board is None else board) else "no")], [S("dnp"), S("yes" if dnp else "no")],
              [S("uuid"), uid(self.key, "sym", ref)]]
        s += fields
        s.append(prop("Footprint", footprint, (p[0], p[1], 0), hide=True))
        s.append(prop("Datasheet", "~", (p[0], p[1], 0), hide=True))
        for k, v in (extra or {}).items():
            s.append(prop(k, v, (p[0], p[1], 0), hide=True))
        for num in pins:
            s.append([S("pin"), num, [S("uuid"), uid(self.key, "pin", ref, num)]])
        s.append([S("instances"), [S("project"), PROJECT, [S("path"), f"/{self.root}/{self.block_uuid}",
                                                           [S("reference"), ref], [S("unit"), 1]]]])
        self.items.append(s)
        if not bom:            # power symbols: their pin is the attachment point
            self.pin_at[p].append((ref, "1"))

    # --- finish
    def finish(self):
        """Split wires at T-points, add junction dots, and check that every pin is attached."""
        cps = set(self.attach) | set(self.pin_at)
        for a, b in self.segs:
            cps.add(a)
            cps.add(b)
        segs = []
        for a, b in self.segs:
            inner = sorted((p for p in cps if _inside(p, a, b)), key=lambda p: abs(p[0] - a[0]) + abs(p[1] - a[1]))
            chain = [a] + inner + [b]
            segs += list(zip(chain, chain[1:]))
        ends = defaultdict(int)
        for a, b in segs:
            ends[a] += 1
            ends[b] += 1
            self.items.append([S("wire"), [S("pts"), [S("xy"), a[0], a[1]], [S("xy"), b[0], b[1]]],
                               [S("stroke"), [S("width"), 0], [S("type"), S("default")]], [S("uuid"), self._id("w")]])
        real_pins = {p: [x for x in v if not x[0].startswith("#")] for p, v in self.pin_at.items()}
        for p in sorted(set(ends) | set(real_pins)):
            if ends[p] + len(real_pins.get(p, [])) >= 3:
                self.items.append([S("junction"), [S("at"), p[0], p[1]], [S("diameter"), 0],
                                   [S("color"), 0, 0, 0, 0], [S("uuid"), self._id("j")]])
        loose = []
        for (ref, num), p in self.pins.items():
            if ends[p] or self.attach[p] or len(self.pin_at[p]) > 1:
                continue
            loose.append((ref, num))
        if loose:
            raise ValueError(f"sheet {self.key}: unattached pins {loose}")
        dangling = [p for p, n in ends.items() if n == 1 and not self.attach[p] and not self.pin_at[p]]
        if dangling:
            raise ValueError(f"sheet {self.key}: wire ends attached to nothing at {dangling[:8]}")

    def sexpr(self):
        tb = [S("title_block"), [S("title"), f"{NL.TITLE}: {self.title}"], [S("date"), DATE], [S("rev"), NL.REV],
              [S("company"), "X1 crawler excavator"],
              [S("comment"), 1, "Generated by source/build_schematic.py from source/netlist.py; do not edit by hand"]]
        return [S("kicad_sch"), [S("version"), 20250114], [S("generator"), "eeschema"],
                [S("generator_version"), "9.0"], [S("uuid"), self.uuid], [S("paper"), self.paper], tb,
                [S("lib_symbols")] + [LIB.get(x) for x in sorted(self.lib_ids)]] + self.items + [
            [S("embedded_fonts"), S("no")]]


def _inside(p, a, b):
    if a[0] == b[0] == p[0]:
        lo, hi = sorted((a[1], b[1]))
        return lo < p[1] < hi
    if a[1] == b[1] == p[1]:
        lo, hi = sorted((a[0], b[0]))
        return lo < p[0] < hi
    return False

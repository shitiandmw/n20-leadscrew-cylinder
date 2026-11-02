"""Manufacturing files for the end-stop board, written from board.py.

    python source/pcb_export.py [S U60 L]   -> electronics/pcb/V6-<v>/  (Gerbers, drill, BOM, CPL, KiCad board)
                                               electronics/pcb/actuator_v6_<v>_gerbers.zip (for upload)
    python source/pcb_export.py --zip-only DIR/electronics/pcb/V6-<v> ...   (only the upload zip)

Gerber frame: X = u (0 = rear edge), Y = v + 4 (board lower edge at Y = 0), top view.
Every layer is read back with pygerber (an independent parser) and compared pixel by pixel
with the intended geometry; the report goes to check_<v>.json.
"""
from pathlib import Path
import csv
import io
import json
import math
import sys
import zipfile
import numpy as np
from shapely.geometry import Point, LineString, Polygon, box as sbox
from shapely.affinity import scale as sscale, translate as stranslate
from shapely.ops import unary_union
import board as B
import layout as LY

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "electronics" / "pcb"
YOFF = LY.PCB_W / 2
REV = "6.1"                  # partition revision: new Hall positions and board length
MASK_EXP = 0.05
ZIP_DATE = (2026, 10, 28, 0, 0, 0)       # fixed, so the upload zip only changes with its files


# ---- silkscreen ---------------------------------------------------------------------------
def text_polys(s, u, v, h, mirror=False, anchor="center"):
    from matplotlib.textpath import TextPath
    from matplotlib.font_manager import FontProperties
    tp = TextPath((0, 0), s, size=h / 0.72, prop=FontProperties(family="DejaVu Sans", weight="bold"))
    polys = [Polygon(p) for p in tp.to_polygons() if len(p) >= 3]
    # TextPath gives outer contours and holes as separate polygons: even-odd fill
    shape = None
    for p in polys:
        p = p.buffer(0)
        shape = p if shape is None else shape.symmetric_difference(p)
    x0, y0, x1, y1 = shape.bounds
    dx = {"center": -(x0 + x1) / 2, "left": -x0, "right": -x1}[anchor]
    shape = stranslate(shape, dx + u, -(y0 + y1) / 2 + v)
    if mirror:
        shape = sscale(shape, -1, 1, origin=(u, v))
    return shape


def silkscreen(variant):
    d = LY.derived(variant)
    P = B.pads(variant)
    pl = B.placement(variant)
    top, bot = [], []
    # wire labels, just in front of the wire pads
    for ref, lab in (("J_A", "A"), ("J_M+", "M+"), ("J_M-", "M-"), ("J_B", "B")):
        u, v = P[(ref, "1")]["at"]
        if ref in ("J_A", "J_B"):
            top.append(text_polys(lab, u, v + (1.05 if v > 0 else -1.05), 0.6))
    # polarity marks: cathode bar beside pad 1 of the polarised diodes
    for ref in ("D1", "D2", "D4", "D5"):
        u, v = P[(ref, "1")]["at"]
        u2, v2 = P[(ref, "2")]["at"]
        du, dv = (u - u2), (v - v2)
        n = math.hypot(du, dv)
        cu, cv = u + du / n * 0.55, v + dv / n * 0.55
        if abs(du) > abs(dv):
            top.append(sbox(cu - 0.08, cv - 0.45, cu + 0.08, cv + 0.45))
        else:
            top.append(sbox(cu - 0.45, cv - 0.08, cu + 0.45, cv + 0.08))
    # SOT-23 needs no pin-1 mark: its 2 + 1 pad pattern only fits one way round
    mid = (d["hall_z"][0] + d["hall_z"][1]) / 2 - LY.PCB_Z0
    top.append(text_polys(f"V6-{variant}  A+ EXTEND  B+ RETRACT", mid, 1.35, 0.85))
    bot.append(text_polys(f"ACTUATOR V6-{variant} END-STOP BOARD  REV {REV}", mid, 1.2, 0.9, mirror=True))
    bot.append(text_polys("JLCJLCJLCJLC", mid, -1.3, 0.8, mirror=True))
    return unary_union(top), unary_union(bot)


def mask_openings(variant):
    return unary_union([p["poly"].buffer(MASK_EXP, join_style=2) for p in B.pads(variant).values()])


def silk_check(variant):
    top, bot = silkscreen(variant)
    errs = []
    opening = mask_openings(variant)
    if top.distance(opening) < 0.1:
        errs.append(f"top silkscreen within 0.1 mm of a pad opening ({top.distance(opening):.3f})")
    outline = B.board_outline(variant).buffer(-0.15)
    for name, g in (("top", top), ("bottom", bot)):
        if not outline.contains(g):
            errs.append(f"{name} silkscreen too close to the board edge")
    return errs


# ---- Gerber writer --------------------------------------------------------------------------
def fracture(poly):
    """Split a polygon along vertical lines through its holes until no piece has a hole."""
    from shapely.ops import split
    todo, done = [poly], []
    while todo:
        p = todo.pop()
        if p.is_empty:
            continue
        if not p.interiors:
            done.append(p)
            continue
        c = Polygon(p.interiors[0]).representative_point()
        cut = LineString([(c.x, p.bounds[1] - 1), (c.x, p.bounds[3] + 1)])
        todo += [g for g in split(p, cut).geoms if g.area > 1e-9]
    return done


class Gerber:
    def __init__(self, function, polarity="Positive"):
        self.head = ["%TF.GenerationSoftware,actuator_v6,pcb_export.py," + REV + "*%",
                     f"%TF.FileFunction,{function}*%", f"%TF.FilePolarity,{polarity}*%",
                     "%FSLAX46Y46*%", "%MOMM*%", "%LPD*%", "G01*"]
        self.aps = {}
        self.body = []
        self.cur = None

    @staticmethod
    def c(x):
        return f"{int(round(x * 1e6))}"

    def ap(self, kind, *dims):
        key = (kind,) + tuple(round(d, 4) for d in dims)
        if key not in self.aps:
            self.aps[key] = 10 + len(self.aps)
        code = self.aps[key]
        if self.cur != code:
            self.body.append(f"D{code}*")
            self.cur = code

    def flash_rect(self, u, v, w, h):
        self.ap("R", w, h)
        self.body.append(f"X{self.c(u)}Y{self.c(v + YOFF)}D03*")

    def flash_circle(self, u, v, d):
        self.ap("C", d)
        self.body.append(f"X{self.c(u)}Y{self.c(v + YOFF)}D03*")

    def line(self, pts, w):
        self.ap("C", w)
        u, v = pts[0]
        self.body.append(f"X{self.c(u)}Y{self.c(v + YOFF)}D02*")
        for u, v in pts[1:]:
            self.body.append(f"X{self.c(u)}Y{self.c(v + YOFF)}D01*")

    def region(self, poly, clear=False):
        if clear:
            self.body.append("%LPC*%")
        ring = list(poly.coords) if hasattr(poly, "coords") else list(poly.exterior.coords)
        self.body.append("G36*")
        u, v = ring[0]
        self.body.append(f"X{self.c(u)}Y{self.c(v + YOFF)}D02*")
        for u, v in ring[1:]:
            self.body.append(f"X{self.c(u)}Y{self.c(v + YOFF)}D01*")
        self.body.append("G37*")
        if clear:
            self.body.append("%LPD*%")

    def shape(self, geom):
        """Filled areas as dark regions only: polygons with holes are cut into hole-free pieces
        (no clear polarity, which some CAM viewers render badly)."""
        for p in (geom.geoms if hasattr(geom, "geoms") else [geom]):
            for piece in fracture(p):
                self.region(piece.exterior)

    def text(self):
        apdefs = []
        for key, code in sorted(self.aps.items(), key=lambda kv: kv[1]):
            if key[0] == "C":
                apdefs.append(f"%ADD{code}C,{key[1]:.4f}*%")
            else:
                apdefs.append(f"%ADD{code}R,{key[1]:.4f}X{key[2]:.4f}*%")
        return "\n".join(self.head + apdefs + self.body + ["M02*"]) + "\n"


def pad_size(variant, ref):
    kind = B.COMPONENTS[ref][0]
    fp = B.FP["WIRE"] if kind == "WIRE" else B.FP[B.PARTS[kind][1]]
    w, h = fp["pad"]
    rot = B.placement(variant)[ref][2]
    return (h, w) if round(rot) % 180 == 90 else (w, h)


def write_gerbers(variant, outdir):
    P = B.pads(variant)
    tr, vias = B.routes(variant)
    files = {}
    for layer, ext, func in (("F.Cu", "GTL", "Copper,L1,Top"), ("B.Cu", "GBL", "Copper,L2,Bot")):
        g = Gerber(func)
        if layer == "F.Cu":
            for (ref, num), p in sorted(P.items()):
                g.flash_rect(*p["at"], *pad_size(variant, ref))
        for net, ly, w, pts in tr:
            if ly == layer:
                g.line(pts, w)
        for net, at in vias:
            g.flash_circle(*at, B.RULES["via_pad"])
        files[ext] = g.text()
    g = Gerber("Soldermask,Top", "Negative")
    for (ref, num), p in sorted(P.items()):
        w, h = pad_size(variant, ref)
        g.flash_rect(*p["at"], w + 2 * MASK_EXP, h + 2 * MASK_EXP)
    files["GTS"] = g.text()
    files["GBS"] = Gerber("Soldermask,Bot", "Negative").text()          # bottom fully covered
    g = Gerber("Paste,Top")
    for (ref, num), p in sorted(P.items()):
        if not ref.startswith("J_"):                                   # wires are hand-soldered
            g.flash_rect(*p["at"], *pad_size(variant, ref))
    files["GTP"] = g.text()
    top, bot = silkscreen(variant)
    for ext, func, geo in (("GTO", "Legend,Top", top), ("GBO", "Legend,Bot", bot)):
        g = Gerber(func)
        g.shape(geo)
        files[ext] = g.text()
    g = Gerber("Profile,NP")
    x0, y0, x1, y1 = B.board_outline(variant).bounds
    g.line([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], 0.05)
    files["GKO"] = g.text()
    lines = ["M48", "; DRILL file actuator_v6 pcb_export.py", "FMAT,2", "METRIC",
             "; #@! TA.AperFunction,Plated,PTH,ViaDrill", f"T1C{B.RULES['via_drill']:.3f}", "%", "G90", "G05", "T1"]
    lines += [f"X{at[0]:.3f}Y{at[1] + YOFF:.3f}" for _, at in sorted(vias, key=lambda x: x[1])]
    lines += ["M30"]
    files["DRL"] = "\n".join(lines) + "\n"
    name = f"actuator_v6_{variant}"
    for ext, txt in files.items():
        (outdir / f"{name}.{ext}").write_text(txt)
    return {ext: outdir / f"{name}.{ext}" for ext in files}


# ---- BOM and placement ----------------------------------------------------------------------
def write_bom_cpl(variant, outdir):
    pl = B.placement(variant)
    groups = {}
    for ref, (kind, _, role) in B.COMPONENTS.items():
        if kind == "WIRE":
            continue
        value, fpname, h, mpn, lcsc, _ = B.PARTS[kind]
        groups.setdefault((value, B.FP[fpname]["kicad"], mpn, lcsc), []).append(ref)
    with open(outdir / f"actuator_v6_{variant}_BOM_JLCPCB.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #", "Manufacturer part", "Quantity"])
        for (value, fp, mpn, lcsc), refs in sorted(groups.items(), key=lambda kv: kv[1][0]):
            w.writerow([value, ",".join(sorted(refs)), fp.split(":")[1], lcsc, mpn, len(refs)])
    with open(outdir / f"actuator_v6_{variant}_CPL_JLCPCB.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for ref in sorted(pl):
            if ref.startswith("J_"):
                continue
            u, v, rot = pl[ref]
            w.writerow([ref, f"{u:.3f}mm", f"{v + YOFF:.3f}mm", "Top", f"{rot % 360:.0f}"])
    return groups


# ---- KiCad board ----------------------------------------------------------------------------
def uid(seed):
    import uuid
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "actuator_v6/" + seed))


def write_kicad(variant, outdir, ox=100.0, oy=100.0):
    from kiutils.board import Board
    from kiutils.footprint import Footprint, Pad
    from kiutils.items.common import Position, Net, Effects, Font
    from kiutils.items.brditems import Segment, Via
    from kiutils.items.gritems import GrLine, GrText
    from kiutils.items.fpitems import FpRect
    b = Board.create_new()
    b.generator = "actuator_v6_pcb_export"
    b.general.thickness = LY.PCB_T
    nets = {"": 0}
    b.nets = [Net(number=0, name="")]
    for i, n in enumerate(B.NETS, start=1):
        nets[n] = i
        b.nets.append(Net(number=i, name=n))
    X = lambda u: round(ox + u, 4)
    Y = lambda v: round(oy - v, 4)
    pl = B.placement(variant)
    for ref, (kind, netmap, role) in B.COMPONENTS.items():
        u, v, rot = pl[ref]
        if kind == "WIRE":
            fp = B.FP["WIRE"]
            value = role
        else:
            value, fpname, *_ = B.PARTS[kind]
            fp = B.FP[fpname]
        f = Footprint.create_new(fp["kicad"], value, type="smd", reference=ref)
        f.tstamp = uid(f"fp{variant}{ref}")
        f.layer = "F.Cu"
        f.position = Position(X=X(u), Y=Y(v), angle=rot or None)
        for item in f.graphicItems:
            if hasattr(item, "type") and item.type in ("reference", "value"):
                item.layer = "F.Fab"
                item.effects = Effects(font=Font(height=0.5, width=0.5, thickness=0.08))
        for num, (x, y) in fp["pads"].items():
            f.pads.append(Pad(number=num, type="smd", shape="rect", position=Position(X=x, Y=y, angle=rot or None),
                              size=Position(X=fp["pad"][0], Y=fp["pad"][1]),
                              layers=["F.Cu", "F.Mask"] + ([] if kind == "WIRE" else ["F.Paste"]),
                              net=Net(number=nets[netmap[num]], name=netmap[num])))
        if fp.get("body"):
            bw, bh = fp["body"]
            f.graphicItems.append(FpRect(start=Position(X=-bw / 2, Y=-bh / 2), end=Position(X=bw / 2, Y=bh / 2),
                                         layer="F.Fab", width=0.08))
        cy = B.courtyard(variant, ref) if kind != "WIRE" else None
        if cy is not None:
            x0, y0, x1, y1 = cy.bounds
            # courtyard in footprint frame (axis-aligned, so swap for 90/270)
            hw, hh = (x1 - x0) / 2, (y1 - y0) / 2
            if round(rot) % 180 == 90:
                hw, hh = hh, hw
            f.graphicItems.append(FpRect(start=Position(X=-hw, Y=-hh), end=Position(X=hw, Y=hh),
                                         layer="F.CrtYd", width=0.05))
        b.footprints.append(f)
    tr, vias = B.routes(variant)
    for net, layer, w, pts in tr:
        for (u0, v0), (u1, v1) in zip(pts[:-1], pts[1:]):
            b.traceItems.append(Segment(start=Position(X=X(u0), Y=Y(v0)), end=Position(X=X(u1), Y=Y(v1)),
                                        width=w, layer=layer, net=nets[net],
                                        tstamp=uid(f"seg{variant}{net}{layer}{u0}{v0}{u1}{v1}")))
    for net, (u, v) in vias:
        b.traceItems.append(Via(position=Position(X=X(u), Y=Y(v)), size=B.RULES["via_pad"],
                                drill=B.RULES["via_drill"], layers=["F.Cu", "B.Cu"], net=nets[net],
                                tstamp=uid(f"via{variant}{net}{u}{v}")))
    x0, y0, x1, y1 = B.board_outline(variant).bounds
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    for (u0, v0), (u1, v1) in zip(corners[:-1], corners[1:]):
        b.graphicItems.append(GrLine(start=Position(X=X(u0), Y=Y(v0)), end=Position(X=X(u1), Y=Y(v1)),
                                     layer="Edge.Cuts", width=0.05))
    d = LY.derived(variant)
    mid = (d["hall_z"][0] + d["hall_z"][1]) / 2 - LY.PCB_Z0
    b.graphicItems.append(GrText(text=f"V6-{variant}  A+ EXTEND  B+ RETRACT", position=Position(X=X(mid), Y=Y(1.35)),
                                 layer="F.SilkS", effects=Effects(font=Font(height=0.85, width=0.85, thickness=0.15))))
    b.graphicItems.append(GrText(text=f"ACTUATOR V6-{variant} END-STOP BOARD  REV {REV}",
                                 position=Position(X=X(mid), Y=Y(1.2)), layer="B.SilkS",
                                 effects=Effects(font=Font(height=0.9, width=0.9, thickness=0.15))))
    path = outdir / f"actuator_v6_{variant}.kicad_pcb"
    b.to_file(str(path))
    # round trip: parse it back and compare counts
    back = Board.from_file(str(path))
    assert abs(back.general.thickness - LY.PCB_T) < 1e-9, "KiCad thickness must match the printed PCB slot"
    assert len(back.footprints) == len(B.COMPONENTS)
    assert sum(1 for t in back.traceItems if isinstance(t, Via)) == len(vias)
    pro = outdir / f"actuator_v6_{variant}.kicad_pro"
    pro.write_text(json.dumps({"meta": {"filename": pro.name, "version": 1},
                               "board": {"design_settings": {"rules": {"min_clearance": B.RULES["clearance"],
                                                                        "min_track_width": B.RULES["track_min"],
                                                                        "min_via_diameter": B.RULES["via_pad"],
                                                                        "min_through_hole_diameter": B.RULES["via_drill"],
                                                                        "min_copper_edge_clearance": B.RULES["edge"]}}},
                               "net_settings": {"classes": [{"name": "Default", "clearance": B.RULES["clearance"],
                                                             "track_width": 0.25, "via_diameter": B.RULES["via_pad"],
                                                             "via_drill": B.RULES["via_drill"]}]}}, indent=2))
    return path


# ---- independent read-back --------------------------------------------------------------------
def intended(variant):
    P = B.pads(variant)
    tr, vias = B.routes(variant)
    via = [Point(at).buffer(B.RULES["via_pad"] / 2, 48) for _, at in vias]
    lay = {}
    lay["GTL"] = unary_union([p["poly"] for p in P.values()] + via +
                             [LineString(pts).buffer(w / 2) for n, l, w, pts in tr if l == "F.Cu"])
    lay["GBL"] = unary_union(via + [LineString(pts).buffer(w / 2) for n, l, w, pts in tr if l == "B.Cu"])
    lay["GTS"] = mask_openings(variant)
    lay["GTP"] = unary_union([p["poly"] for (r, _), p in P.items() if not r.startswith("J_")])
    lay["GTO"], lay["GBO"] = silkscreen(variant)
    return lay


def readback(variant, files, dpmm=40):
    from pygerber.gerberx3.api.v2 import GerberFile
    from PIL import Image
    from matplotlib.path import Path as MPath
    want = intended(variant)
    report = {}
    for ext, geom in want.items():
        pf = GerberFile.from_file(files[ext]).parse()
        info = pf.get_info()
        buf = io.BytesIO()
        pf.render_raster(buf, dpmm=dpmm, image_format=__import__("pygerber.gerberx3.api.v2", fromlist=["x"]).ImageFormatEnum.PNG)
        img = np.asarray(Image.open(io.BytesIO(buf.getvalue())).convert("L"), float)
        got = img > img.max() * 0.5 if img.max() > 0 else img > 0
        h, w = got.shape
        x0, y0 = float(info.min_x_mm), float(info.min_y_mm)
        xs = x0 + (np.arange(w) + 0.5) / dpmm
        ys = float(info.max_y_mm) - (np.arange(h) + 0.5) / dpmm
        XX, YY = np.meshgrid(xs, ys)
        pts = np.stack([XX.ravel(), YY.ravel() - YOFF], 1)
        mask = np.zeros(len(pts), bool)
        for p in (geom.geoms if hasattr(geom, "geoms") else [geom]):
            inside = MPath(np.asarray(p.exterior.coords)).contains_points(pts)
            for hole in p.interiors:
                inside &= ~MPath(np.asarray(hole.coords)).contains_points(pts)
            mask |= inside
        mask = mask.reshape(h, w)
        # compare away from edges: one-pixel boundary disagreement is rasterisation, not error
        from scipy.ndimage import binary_erosion
        diff = got ^ mask
        core = diff & binary_erosion(diff, iterations=1)
        frac = float(core.sum()) / max(1, int(mask.sum()))
        report[ext] = dict(pixels=int(mask.sum()), mismatch_fraction=round(frac, 5),
                           extent_mm=[round(float(info.min_x_mm), 3), round(float(info.min_y_mm), 3),
                                      round(float(info.max_x_mm), 3), round(float(info.max_y_mm), 3)])
    return report


def render_layers(variant, files, path, dpmm=40):
    """Board picture made from the Gerbers themselves (pygerber), top and bottom."""
    from pygerber.gerberx3.api.v2 import GerberFile, ImageFormatEnum
    from PIL import Image
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    L = B.board_outline(variant).bounds[2]

    def layer(ext):
        pf = GerberFile.from_file(files[ext]).parse()
        info = pf.get_info()
        buf = io.BytesIO()
        pf.render_raster(buf, dpmm=dpmm, image_format=ImageFormatEnum.PNG)
        img = np.asarray(Image.open(io.BytesIO(buf.getvalue())).convert("L"), float)
        full = np.zeros((int(round(LY.PCB_W * dpmm)), int(round(L * dpmm))), bool)
        r0 = int(round((LY.PCB_W - float(info.max_y_mm)) * dpmm))
        c0 = int(round(float(info.min_x_mm) * dpmm))
        m = img > img.max() * 0.5
        hh, ww = min(m.shape[0], full.shape[0] - r0), min(m.shape[1], full.shape[1] - c0)
        full[r0:r0 + hh, c0:c0 + ww] = m[:hh, :ww]
        return full

    fig, axs = plt.subplots(2, 1, figsize=(max(8, L / 4.5), 3.6), dpi=220)
    for ax, side in zip(axs, ("top", "bottom")):
        rgb = np.zeros(layer("GTL").shape + (3,))
        rgb[:] = (0.11, 0.37, 0.23)
        if side == "top":
            cu, mask, silk = layer("GTL"), layer("GTS"), layer("GTO")
            rgb[cu] = (0.20, 0.52, 0.33)
            rgb[cu & mask] = (0.85, 0.68, 0.30)
            rgb[silk & ~mask] = (0.95, 0.95, 0.95)
        else:
            cu, silk = layer("GBL"), layer("GBO")
            rgb[cu] = (0.20, 0.52, 0.33)
            rgb[silk] = (0.95, 0.95, 0.95)
            rgb = rgb[:, ::-1]
        ax.imshow(rgb, extent=(0, L, -LY.PCB_W / 2, LY.PCB_W / 2), interpolation="nearest")
        ax.set_title(f"V6-{variant} board from its Gerbers, {side} side" +
                     (" (mirrored: as seen from below)" if side == "bottom" else ""), fontsize=6)
        ax.tick_params(labelsize=4)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def zip_gerbers(folder):
    """Gerbers and drill file of one board folder (.../V6-<v>) in one zip next to it, for upload."""
    variant = folder.name.removeprefix("V6-")
    target = folder.parent / f"actuator_v6_{variant}_gerbers.zip"
    files = sorted(f for f in folder.glob(f"actuator_v6_{variant}.*") if not f.suffix.startswith(".kicad"))
    assert len(files) == 9, files                      # 8 Gerber layers and the drill file
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            info = zipfile.ZipInfo(f.name, date_time=ZIP_DATE)
            info.compress_type, info.external_attr = zipfile.ZIP_DEFLATED, 0o600 << 16
            z.writestr(info, f.read_bytes())
    return target


def main(variants):
    allrep = {}
    for variant in variants:
        out = OUT / f"V6-{variant}"
        out.mkdir(parents=True, exist_ok=True)
        errs, notes = B.drc(variant)
        errs += silk_check(variant)
        files = write_gerbers(variant, out)
        zip_gerbers(out)
        groups = write_bom_cpl(variant, out)
        kpath = write_kicad(variant, out)
        rb = readback(variant, files)
        worst = max(r["mismatch_fraction"] for r in rb.values())
        render_layers(variant, files, ROOT / "images" / f"board_{variant}.png")
        B.render(variant, out / f"board_{variant}_layout.png")
        d = LY.derived(variant)
        rep = dict(variant=variant, board_mm=[d["pcb_length"], LY.PCB_W], thickness_mm=LY.PCB_T,
                   layers=2, parts=sum(len(r) for r in groups.values()), part_numbers=len(groups),
                   drc_errors=errs, drc_notes=notes, rules=B.RULES, gerber_readback=rb,
                   readback_worst_mismatch=worst, kicad=kpath.name,
                   hall_u_mm=[d["hall_z"][0] - LY.PCB_Z0, d["hall_z"][1] - LY.PCB_Z0])
        (out / f"check_{variant}.json").write_text(json.dumps(rep, indent=2))
        allrep[variant] = rep
        print(variant, "DRC errors:", len(errs), "| read-back worst mismatch:", worst, "|", notes[0])
        for e in errs:
            print("   ", e)
        assert not errs and worst < 0.002, "board check failed"
    return allrep


if __name__ == "__main__":
    if sys.argv[1:2] == ["--zip-only"]:
        for folder in sys.argv[2:]:
            print(zip_gerbers(Path(folder).resolve()))
    else:
        main(sys.argv[1:] or list(LY.VARIANTS))

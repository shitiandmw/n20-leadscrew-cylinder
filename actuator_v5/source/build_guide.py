"""Illustrated assembly guide with the schematic appended.

python source/build_guide.py  -> assembly_guide.pdf (A4 landscape pages + the two A3 schematic sheets)
Uses the DejaVu fonts that ship with matplotlib, so it builds on any OS.
"""
from pathlib import Path
import json
import tempfile
import matplotlib
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image as RLImage, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

ROOT = Path(__file__).resolve().parent.parent
FONTS = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
pdfmetrics.registerFont(TTFont("DejaVu", str(FONTS / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(FONTS / "DejaVuSans-Bold.ttf")))
INK, MUTED, ACCENT = colors.HexColor("#1d2a30"), colors.HexColor("#5f6f75"), colors.HexColor("#b8650f")
PAGE = landscape(A4)
W = PAGE[0] - 30 * mm

H1 = ParagraphStyle("h1", fontName="DejaVu-Bold", fontSize=19, leading=23, textColor=INK, spaceAfter=4)
H2 = ParagraphStyle("h2", fontName="DejaVu-Bold", fontSize=12.5, leading=16, textColor=INK, spaceBefore=4, spaceAfter=4)
BODY = ParagraphStyle("body", fontName="DejaVu", fontSize=8.8, leading=12.4, textColor=INK, spaceAfter=3)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=7.6, leading=10.2, textColor=MUTED)
EYEBROW = ParagraphStyle("eyebrow", parent=BODY, fontName="DejaVu-Bold", fontSize=8, textColor=ACCENT, spaceAfter=2)


def picture(name, width, tmp, max_height=None):
    """Downscaled JPEG copy so the PDF stays small; fits inside width x max_height."""
    src = ROOT / "images" / name
    im = Image.open(src).convert("RGB")
    im.thumbnail((1600, 1600))
    out = Path(tmp) / (src.stem + ".jpg")
    im.save(out, quality=86)
    height = width * im.height / im.width
    if max_height and height > max_height:
        width, height = max_height * im.width / im.height, max_height
    return RLImage(str(out), width=width, height=height)


def table(rows, widths, header=True):
    t = Table([[Paragraph(str(c), BODY) for c in r] for r in rows], colWidths=widths)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#d5dbdd")),
             ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f3"))]
    t.setStyle(TableStyle(style))
    return t


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("DejaVu", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(15 * mm, 8 * mm, "Excavator arm actuator V5 · assembly and wiring guide")
    canvas.drawRightString(PAGE[0] - 15 * mm, 8 * mm, f"page {doc.page}")
    canvas.restoreState()


def two_up(left, right, gap=6 * mm):
    """Two columns; each side is a flowable or a list of flowables."""
    t = Table([[left if isinstance(left, list) else [left], right if isinstance(right, list) else [right]]],
              colWidths=[W / 2] * 2)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), gap / 2)]))
    return t


def build(tmp):
    p = json.loads((ROOT / "parameters.json").read_text())
    v = json.loads((ROOT / "validation.json").read_text())
    L, stroke = p["screw_length_mm"], p["stroke_mm"]
    half = (W - 6 * mm) / 2
    s = []

    # 1 overview
    s += [Paragraph("PRINTABLE LINEAR ACTUATOR · V5", EYEBROW),
          Paragraph("A leadscrew cylinder that looks hydraulic", H1),
          Paragraph(f"Built around your N20 gearmotor with integrated M3 leadscrew, used as supplied. Stroke {stroke} mm with "
                    f"the assumed {L:.0f} mm screw; pin centres {p['eye_centres_closed_mm']:.0f} → "
                    f"{p['eye_centres_open_mm']:.0f} mm; Ø{p['barrel_od_mm']:.0f} barrel, Ø{p['cap_od_mm']:.0f} caps, "
                    f"Ø{p['rod_d_mm']:.0f} rod, Ø{p['eye_od_mm']:.0f} clevis eyes with Ø{p['eye_hole_mm']} holes "
                    f"({p['eye_thickness_mm']} mm thick, as on V4). <b>Measure your screw before printing</b> and rebuild "
                    "with <font face='DejaVu-Bold'>--screw-length</font>; everything along the axis follows it.", BODY),
          picture("hero.png", W * 0.62, tmp),
          table([["Your point", "What V5 does"],
                 ["1. The rod looks too ugly", "Round yellow barrel, graphite end caps with wiper lip and design groove, "
                  "chrome-look rod, clevis eyes, hose-style cable port with TPU boot. Sensors and wiring hidden under a "
                  "flush cover strip. 25 mm shorter than V4 for the same stroke."],
                 ["2. The core part has an extra section", "Removed both: the 1.2 mm rear cap that V4 added behind the "
                  "15 mm can (the 15 already includes the end cap), and the 41 mm drive train of D-shaft, coupler, "
                  "624 bearing, washers and lock nuts. The brass nut now runs directly on the motor's own leadscrew."],
                 ["3. Wiring has no circuit schematic", "Two-sheet A3 schematic (appended at the end of this guide) with "
                  "designators, values, pin numbers and nets. Its connectivity is checked automatically against the "
                  "netlist and the firmware's pin constants."]],
                [55 * mm, W - 55 * mm]),
          PageBreak()]

    # 2 core part
    s += [Paragraph("The core part, unchanged", H1),
          Paragraph("Side elevations are projections of the CAD meshes at the same scale, aligned at the gearbox front face. "
                    "V5 follows your drawing exactly: Ø4 × 0.7 bushing, 9 mm gearbox, 15 mm can including the black end cap, "
                    "Ø5 × 1.2 boss, terminal blades 1.5 × 0.3 mm, 7.3 mm apart, reaching 2.5 mm beyond the can.", BODY),
          picture("core_part_check.png", W, tmp, max_height=148 * mm),
          Paragraph("Load path: the gearbox front face sits on a step in the barrel (pulling loads); the rear cap backs the can "
                    "and takes pushing loads through two M2 × 10 screws. The rectangular pocket stops the motor turning and "
                    "the flat-sided carrier stops the rod turning.", SMALL),
          PageBreak()]

    # 3 looks and stroke
    s += [Paragraph("Outside", H1),
          two_up(picture("service_side.png", half, tmp, 70 * mm), picture("detail_cap_end.png", half, tmp, 70 * mm)),
          Paragraph("Service side (−Y): the black strip covers the sensor channel. Rear: hose-style port with TPU boot, two M2 × 10 "
                    "cap screws, Ø3.2 clevis eye.", SMALL),
          two_up(picture("stroke_retracted.png", half, tmp, 70 * mm), picture("stroke_extended.png", half, tmp, 70 * mm)),
          Paragraph(f"Retracted (pin centres {p['eye_centres_closed_mm']:.0f} mm) and extended "
                    f"({p['eye_centres_open_mm']:.0f} mm). Mechanical stops sit {p['overtravel_retract_mm']} mm and "
                    f"{p['overtravel_extend_mm']} mm beyond the switched end positions.", SMALL),
          PageBreak()]

    # 4 inside
    s += [Paragraph("Inside", H1),
          two_up(picture("section.png", half, tmp, 70 * mm), picture("core_part.png", half, tmp, 70 * mm)),
          Paragraph("Left: section on the pin plane. Motor seated on the barrel step, M3 leadscrew straight from the "
                    "gearbox, brass nut in the carrier, magnet on the channel side, rod eye pinned with a Ø2 dowel. "
                    "Right: the core part on its own, as in your drawing.", SMALL),
          two_up(picture("wiring.png", half, tmp, 70 * mm), picture("detail_rod_end.png", half, tmp, 70 * mm)),
          Paragraph("Left: cover strip removed. Each Hall sensor carries its 4.7 kΩ pull-up and 100 nF capacitor on its leads; "
                    "six sensor wires run rearward in the channel, the two motor wires leave the terminals through the "
                    "rear cap. Right: head collar with wiper lip, rod eye and dowel.", SMALL),
          PageBreak()]

    # 5 assembly
    steps = [
        ("Head collar", "Glue 03 onto the barrel front with its strip slot over the channel (−Y)."),
        ("Pushrod", "Press the M3 brass nut into the carrier's side slot. Glue the Ø4 × 2 N35 magnet into the hole on "
                    "the channel side. Let the epoxy cure."),
        ("Rod in", "Slide the pushrod into the barrel from the rear, rod first, through the head collar."),
        ("Rod eye", "Press 05 onto the rod and drive the Ø2 × 13.8 dowel through the neck; both ends flush."),
        ("Motor wires", "Solder W7 orange to the motor's (+) and W8 purple to (−); sleeve both."),
        ("Motor in", "Turn the motor so the leadscrew threads into the nut, push it in until the gearbox sits on the step, "
                     "(+) terminal toward the cable port."),
        ("Hall modules", "Solder R/C onto the Hall leads and the three wires per sensor (schematic sheet 1). With the strip "
                         "off the channel is open: lay U1 (z 5.4) and U2 (z 43.0) in from below, branded face to the rod, "
                         "leads to the rear; tape them; run the wires rearward into the rear cap."),
        ("Cable", "Feed all eight wires through the rear-cap port, the TPU boot and the Ø4/3.2 jacket."),
        ("Rear cap", "Fit 02 and the two M2 × 10 screws (they cut their thread in Ø1.7 pilots; do not overtighten)."),
        ("Calibrate", "See the next page."),
        ("Cover strip", "Slide 06 in from the front through the head-collar slot; dab of neutral-cure silicone."),
    ]
    prints = [["STL", "Material and setup"]] + [[k, v_] for k, v_ in (
        ("01_barrel", "PETG yellow, rear face down, 0.2 mm, 4 walls, 30 % gyroid"),
        ("02_rear_cap", "PETG black, collar opening down, 0.16 mm, 4 walls, 40 % gyroid"),
        ("03_head_collar", "PETG black, nose down, 0.16 mm, 4 walls"),
        ("04_pushrod", "PETG silver, carrier down, 0.16 mm, 100 % infill"),
        ("05_rod_eye", "PETG black, socket opening down, 0.16 mm, 100 % infill"),
        ("06_sensor_cover", "PETG black, flat inner face down, 0.12 mm"),
        ("07_TPU_cable_boot", "TPU 95A, taper end down"))]
    s += [Paragraph("Assembly", H1),
          two_up([table([["#", "Step", ""]] + [[str(i), a, b] for i, (a, b) in enumerate(steps, 1)],
                        [9 * mm, 24 * mm, half - 35 * mm])],
                 [Paragraph("Print settings", H2), table(prints, [37 * mm, half - 39 * mm]), Spacer(1, 4 * mm),
                  Paragraph("0.4 mm nozzle, mm units, 100 % scale. Print the four fit samples first (motor step and "
                            "channel, carrier, front lip, cover strip). Not yet sliced or printed.", SMALL)]),
          PageBreak()]

    # 6 calibration and checks
    reroutes = all(not r["interferences"] for r in v["sensor_reroutes"])
    motion = ", ".join(f"{m['travel_mm']:g}" for m in v["motion"])
    s += [Paragraph("End stops: calibration", H1),
          two_up([
              Paragraph("1. <b>Direction first.</b> Strip off, logic on J3, motor at about 3 V on J2. Mid-stroke, tap EXTEND: "
                        "the rod must move out. If it moves in, swap W7/W8 at J1 before anything else, or the gates guard "
                        "the wrong end. The screw is self-locking, so only the motor moves the rod.", BODY),
              Paragraph("2. W3 and W6 against GND: about 4.5 V away from the ends, near 0 V at their own end.", BODY),
              Paragraph("3. Jog to each end. The Hall should cut the motor just before the mechanical stop (2 mm overtravel "
                        "at retract, 3 mm at extend). Slide the sensor ±3 mm in the channel to adjust.", BODY),
              Paragraph("4. At each end the blocked direction stays blocked after a power cycle; the other direction drives "
                        "out. Unplug W3, then W6: that direction must be blocked.", BODY),
              Paragraph("5. Fix the sensors with silicone, dress the wires, slide in the strip. Then set the current trip "
                        "against the real motor and load.", BODY),
              Paragraph("Use an N35 magnet. With N42 the reverse lobe of the field can reach the sensor's minimum operate "
                        "threshold and switch it twice.", SMALL)],
              [picture("magnet_trigger.png", half, tmp, 75 * mm),
               Paragraph("Magnet model (Biot–Savart, steel parts ignored): the DRV5033AJ switches LOW about 3.9 mm before "
                         "alignment and releases about 4.3 mm after, so each sensor sits 3.8 mm outboard of its end "
                         "position.", SMALL)]),
          Paragraph("What was checked", H2),
          Paragraph(f"CAD: no interference between fixed parts, hardware, Hall modules and wires; moving parts clear at "
                    f"{motion} mm; all eight wires start on their terminals (gap 0); sensor re-routes at ±3 mm "
                    f"{'clear' if reroutes else 'NOT clear'}; every STL watertight, single solid, after a STEP round trip. "
                    "Electronics: schematic connectivity equals the netlist and the firmware pin constants; 74HC08 gate "
                    "truth table; protection-logic unit test compiled with asserts and passed. Not verified: printing and "
                    "fit, motor ratings, axial load capacity, magnetic switching on real parts, firmware on a board.", SMALL)]

    doc = SimpleDocTemplate(str(tmp / "guide.pdf"), pagesize=PAGE, leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=12 * mm, bottomMargin=14 * mm, title="Excavator arm actuator V5 - guide",
                            author="build_guide.py")
    doc.build(s, onFirstPage=footer, onLaterPages=footer)
    return tmp / "guide.pdf"


def main():
    import pymupdf
    with tempfile.TemporaryDirectory() as t:
        guide = pymupdf.open(build(Path(t)))
        guide.insert_pdf(pymupdf.open(ROOT / "electronics" / "schematic.pdf"))
        guide.set_metadata({"title": "Excavator arm actuator V5 - assembly and wiring guide",
                            "subject": "Assembly, calibration and schematic"})
        out = ROOT / "assembly_guide.pdf"
        guide.save(out, deflate=True, garbage=3)
        print(out, guide.page_count, "pages")


if __name__ == "__main__":
    main()

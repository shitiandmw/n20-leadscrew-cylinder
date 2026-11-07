"""3D models (STEP) for parts that KiCad 9's 3D library lacks, for the board STEP and renders.

Each is built from its land pattern's fabrication outline (the KiCad footprint, drawn from the
maker's drawing named in the footprint) and the part height in netlist.py. Board surface at z = 0,
origin at the footprint origin. KiCad models have +y up the page, footprints +y down it, so a
footprint's (x, y) is (x, -y) here. Needs CadQuery (run with a Python that has it):

    python models_3d.py   -> ../kicad/3d/*.step

- Buzzer_XHXDZ_8530: XHXDZ SMD8530 (LCSC C49246949), 8.5 x 8.5 x 3.0 mm, round sound port, corner terminals.
- USB_C_Receptacle_HRO_TYPE-C-31-M-12: shell 8.94 x 7.30 mm, 3.26 mm high, mating face at +y.
- SW_Push_1P1T_XKB_TS-1187A: 5.1 x 5.1 mm body, 1.5 mm high with its round actuator.
- AMASS_XT30PW-M_1x02_P2.50mm_Horizontal: 9.9 x 9.0 mm housing, 5.2 mm high, mounting ears with pegs,
  contacts bent down to the two pads at the rear.
"""
from pathlib import Path

import cadquery as cq

import footprints as FP
import netlist as NL

OUT = Path(__file__).resolve().parent.parent / "kicad" / "3d"
BLACK, METAL, NYLON = cq.Color(0.08, 0.08, 0.08), cq.Color(0.82, 0.82, 0.78), cq.Color(0.95, 0.85, 0.15)


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def buzzer():
    b, h, p, s = FP.BUZ["body"], FP.BUZ["height"], FP.BUZ["pitch"] / 2, FP.BUZ["pad"]
    body = box(-b / 2, b / 2, -b / 2, b / 2, 0.1, h).edges("|Z").fillet(0.3).faces(">Z").workplane().hole(2.0, 0.6)
    pads = None
    for x in (-p, p):
        for y in (-p, p):
            t = box(x - s / 2, x + s / 2, y - s / 2, y + s / 2, 0, 0.12)
            pads = t if pads is None else pads.union(t)
    return [("body", body, BLACK), ("terminals", pads, METAL)]


def usb_c():
    h = NL.KINDS["USBC"]["height"]
    shell = (cq.Workplane("XZ").center(0, h / 2).slot2D(8.94, h).extrude(-7.30).translate((0, -3.65, 0)))
    mouth = cq.Workplane("XZ").center(0, h / 2).slot2D(8.34, h - 0.6).extrude(-6.0).translate((0, -2.35, 0))
    return [("shell", shell.cut(mouth), METAL), ("tongue", box(-3.3, 3.3, -2.0, 3.0, h / 2 - 0.35, h / 2 + 0.35), BLACK)]


def tact():
    h = NL.KINDS["SW"]["height"]
    body = box(-2.55, 2.55, -2.55, 2.55, 0, h - 0.3).edges("|Z").chamfer(0.6)
    knob = cq.Workplane("XY").circle(1.0).extrude(0.3).translate((0, 0, h - 0.3))
    legs = None
    for x in (-2.9, 2.9):
        for y in (-1.88, 1.88):
            t = box(x - 0.35, x + 0.35, y - 0.3, y + 0.3, 0, 0.15)
            legs = t if legs is None else legs.union(t)
    return [("body", body, BLACK), ("actuator", knob, BLACK), ("legs", legs, METAL)]


def xt30():
    # The housing lies on the footprint's -y side (its courtyard, toward the mating face), so +y here.
    h = NL.KINDS["XT30"]["height"]
    body = box(-7.45, 2.45, 4.1, 13.1, 0, h).edges("|Y").fillet(0.8)
    ears = None
    for cx in (-8.0, 3.0):                       # ears carry the 1.4 mm pegs (footprint holes at y -10)
        e = cq.Workplane("XY").circle(1.0).extrude(1.2).translate((cx, 10.0, 0)).union(
            box(min(cx, -7.45 if cx < 0 else 2.45), max(cx, -7.45 if cx < 0 else 2.45), 9.0, 11.0, 0, 1.2))
        ears = e if ears is None else ears.union(e)
    pins = None
    for x in (0.0, -5.0):                        # pads 1 and 2: contacts leave the rear and bend down
        t = box(x - 0.8, x + 0.8, -0.6, 4.1, h / 2 - 0.4, h / 2 + 0.4).union(box(x - 0.8, x + 0.8, -0.6, 0.4, -1.6, h / 2))
        pins = t if pins is None else pins.union(t)
    return [("housing", body.union(ears), NYLON), ("contacts", pins, cq.Color(0.85, 0.65, 0.2))]


MODELS = {"Buzzer_XHXDZ_8530": buzzer, "USB_C_Receptacle_HRO_TYPE-C-31-M-12": usb_c,
          "SW_Push_1P1T_XKB_TS-1187A": tact, "AMASS_XT30PW-M_1x02_P2.50mm_Horizontal": xt30}


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in MODELS.items():
        asm = cq.Assembly(name=name)
        for part, shape, colour in fn():
            asm.add(shape, name=part, color=colour)
        asm.save(str(OUT / f"{name}.step"), exportType="STEP")
        print("wrote", OUT / f"{name}.step")

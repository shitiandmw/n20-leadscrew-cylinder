"""The main board rev A as KiCad exported it (controller/main_board/X1_main_board_A.step: the PCB and every part's 3D
model, KiCad's own library models for the JST headers and the passives, the project's models for the XT30PW-M, USB-C,
buzzer and tact switches), read once and split into colour groups for the body CAD and the viewers.

STEP frame: PCB outline 0..96 x 0..64, board bottom z = 0, top z = 1.51 (KiCad's 1.6 nominal), parts on top. The
machine frame puts the board at x1_body.BOARD: machine = STEP + (-136, 84, 110).

groups() -> {group: (compound shape, colour, refs)} in the STEP frame; the group of a part follows its footprint:
  pcb          the PCB (KiCad's green)
  jst          S2B/S4B-XH-A and S3B/S4B-PH-K-S headers (natural PA, white)
  xt30         XT30PW-M housing (yellow) and xt30_pins (gold)
  usb          USB-C shell (steel) ; usb_tongue (black) goes with 'ics'
  module       ESP32-S3-WROOM-1 (shield can, steel)
  ics          SOT/SOIC/HTSSOP packages, the electrolytic can, the inductors, buzzer, tact switches (black)
  passives     chip resistors, capacitors, diodes, fuses, LEDs (light grey)
"""
from functools import lru_cache
from pathlib import Path
import cadquery as cq
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.TDF import TDF_LabelSequence, TDF_Label
from OCP.TDataStd import TDataStd_Name
from OCP.TopLoc import TopLoc_Location
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopoDS import TopoDS

HERE = Path(__file__).resolve().parent
STEP = HERE.parent / 'controller' / 'main_board' / 'X1_main_board_A.step'
OFFSET = (-136.0, 84.0, 110.0)           # STEP -> machine (x1_body.BOARD)

COLOURS = dict(pcb=(.10, .36, .22), jst=(.93, .92, .86), xt30=(.93, .72, .10), xt30_pins=(.85, .66, .22), usb=(.80, .81, .80),
               module=(.78, .79, .78), ics=(.12, .12, .13), passives=(.62, .62, .58))


def _group_of(path):
    tag = '/'.join(path)
    if 'X1_main_PCB' in tag:
        return 'pcb'
    if 'JST_' in tag:
        return 'jst'
    if 'XT30' in tag:
        return 'xt30_pins' if path[-1] == 'contacts' else 'xt30'
    if 'USB_C' in tag:
        return 'usb' if path[-1] == 'shell' else 'ics'
    if 'ESP32' in tag:
        return 'module'
    if any(k in tag for k in ('R_0', 'C_0', 'C_1', 'D_S', 'LED_', 'Fuse_')):
        return 'passives'
    return 'ics'


@lru_cache(None)
def groups():
    doc = TDocStd_Document(TCollection_ExtendedString('board'))
    rdr = STEPCAFControl_Reader()
    rdr.SetNameMode(True)
    assert rdr.ReadFile(str(STEP)) == 1, STEP
    rdr.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())

    def name(lab):
        n = TDataStd_Name()
        return n.Get().ToExtString() if lab.FindAttribute(TDataStd_Name.GetID_s(), n) else '?'

    solids = {}      # group -> [TopoDS_Solid]
    refs = {}        # group -> set of refs

    def walk(lab, loc, path):
        nm = name(lab)
        if st.IsReference_s(lab):
            ref = TDF_Label()
            st.GetReferredShape_s(lab, ref)
            walk(ref, loc.Multiplied(st.GetLocation_s(lab)), path + [nm])
            return
        kids = TDF_LabelSequence()
        st.GetComponents_s(lab, kids)
        if kids.Length() == 0:
            g = _group_of(path + [nm])
            sh = st.GetShape_s(lab).Moved(loc)
            ex = TopExp_Explorer(sh, TopAbs_SOLID)
            while ex.More():
                solids.setdefault(g, []).append(TopoDS.Solid_s(ex.Current()))
                ex.Next()
            ref = next((p for p in path if len(p) <= 5 and p[:1] in 'JUCRLDFQS' and p[1:].isdigit()), None)
            if ref:
                refs.setdefault(g, set()).add(ref)
            return
        for i in range(1, kids.Length() + 1):
            walk(kids.Value(i), loc, path + [nm])

    roots = TDF_LabelSequence()
    st.GetFreeShapes(roots)
    for i in range(1, roots.Length() + 1):
        walk(roots.Value(i), TopLoc_Location(), [])
    out = {}
    for g, lst in solids.items():
        comp = cq.Compound.makeCompound([cq.Solid(s) for s in lst])
        out[g] = (cq.Workplane(obj=comp), COLOURS[g], sorted(refs.get(g, ())))
    return out


def machine_groups():
    """groups() moved into the machine frame."""
    return {g: (s.translate(OFFSET), c, r) for g, (s, c, r) in groups().items()}


if __name__ == '__main__':
    for g, (s, c, r) in machine_groups().items():
        bb = s.val().BoundingBox()
        print(f'{g:10s} {len(s.val().Solids()):3d} solids  x {bb.xmin:7.2f}..{bb.xmax:7.2f}  y {bb.ymin:7.2f}..{bb.ymax:7.2f}  '
              f'z {bb.zmin:7.2f}..{bb.zmax:7.2f}  refs {len(r)}: {" ".join(r[:12])}{" ..." if len(r) > 12 else ""}')

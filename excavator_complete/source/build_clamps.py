"""W01: the printed cable clamp of the arm harness (harness.py). A small PETG block glued to a flat face of the boom or the
stick (CA); the 3 mm sleeve snaps into it from the top.

  base 8 (along the cable) x 7 x 1.2, saddle to 5.5 high, Ø3.2 bore with its centre 1.75 above the base (the cable centre
  sits TUBE_R off the face), a 2.4 mm snap slot on top with a 0.3 mm lead-in. 100 % infill, printed on its base.

Writes ../step/W01_cable_clamp.step, ../stl/W01_cable_clamp.stl, ../cad/W01_mesh.json.gz and ../cad/W01_report.json.
Run with the R12 interpreter from this folder.
"""
import json
import numpy as np
import cadquery as cq
import trimesh
import common as K
import harness as H

NAME = 'W01_cable_clamp'
L, W, BASE_T, HIGH = 8.0, 7.0, 1.2, 5.5
BORE_R, SLOT_W = 1.6, 2.4


def clamp():
    s = cq.Workplane('XY').box(L, W, HIGH, centered=(True, True, False))
    s = s.edges('|X').edges('>Z').fillet(1.2)
    bore = cq.Workplane('YZ').center(0, H.TUBE_R).circle(BORE_R).extrude(L + 2).translate((-L / 2 - 1, 0, 0))
    slot = cq.Workplane('XY').box(L + 2, SLOT_W, HIGH, centered=(True, True, False)).translate((0, 0, H.TUBE_R))
    s = s.cut(bore).cut(slot)
    lead = cq.Workplane('XY').box(L + 2, SLOT_W + 0.6, 0.3, centered=(True, True, False)).translate((0, 0, HIGH - 0.3))
    return s.cut(lead)


def main():
    for sub in ('step', 'stl', 'cad'):
        (K.ROOT / sub).mkdir(exist_ok=True)
    s = clamp()
    sol = s.val()
    assert sol.isValid()
    cq.exporters.export(s, str(K.ROOT / 'step' / f'{NAME}.step'))
    cq.exporters.export(s, str(K.ROOT / 'stl' / f'{NAME}.stl'), tolerance=0.02, angularTolerance=0.1)
    tm = trimesh.load_mesh(K.ROOT / 'stl' / f'{NAME}.stl')
    v, f = np.asarray(tm.vertices), np.asarray(tm.faces)
    K.save_gz(K.ROOT / 'cad' / 'W01_mesh.json.gz', dict(name=NAME, kind='printed', color=[0.20, 0.23, 0.26],
                                                       v=np.round(v, 3).ravel().tolist(), t=f.ravel().tolist()))
    rep = dict(part=NAME, valid=True, watertight=bool(tm.is_watertight), volume_mm3=round(float(tm.volume), 2),
               mass_g=round(float(tm.volume) * 1.27e-3, 2), size_mm=[L, W, HIGH], bore_d=2 * BORE_R, snap_slot_w=SLOT_W,
               cable_centre_above_face_mm=H.TUBE_R, print='PETG, 100 % infill, base down, no supports',
               fixing='CA glue on the base; the sleeve snaps in from the top',
               frame='x along the cable, z out of the glued face (the base is at z 0)')
    (K.ROOT / 'cad' / 'W01_report.json').write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep))


if __name__ == '__main__':
    main()

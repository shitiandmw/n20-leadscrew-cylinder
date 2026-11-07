"""Exact CAD checks for the recessed spring pocket and piston, independent of rendering.

The spring's full annular envelope (not merely sampled coils) must clear the
frame and moving yoke at eleven positions over the operating stroke.
"""
import json
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
import j9_parts as P
import j9_design as D


def volume(s):
    return sum(v.Volume() for v in s.vals())


def distance(a, b):
    tool = BRepExtrema_DistShapeShape(P.one(a).wrapped, P.one(b).wrapped)
    tool.Perform()
    return round(tool.Value(), 5)


def check(frame=None, yoke=None):
    frame = frame if frame is not None else P.h_frame()
    yoke = yoke if yoke is not None else P.u_yoke()
    rows = []
    for i in range(11):
        recoil = D.RECOIL*i/10
        moving = yoke.translate((-recoil, 0, 0))
        spring = P.xring(D.SPRING['od']/2, D.SPRING['id']/2,
                         D.SPRING_X0, D.SPRING_X0 + D.SPRING_SET - recoil, 0, D.AXLE_Z)
        rows.append(dict(recoil_mm=round(recoil, 3),
                         spring_frame_overlap_mm3=volume(spring.intersect(frame)),
                         spring_yoke_overlap_mm3=volume(spring.intersect(moving)),
                         yoke_frame_overlap_mm3=volume(moving.intersect(frame)),
                         spring_length_mm=round(D.SPRING_SET - recoil, 3)))
    guide = P.xring(D.SPRING_POCKET['outer_d']/2, D.SPRING_POCKET['bore_d']/2,
                    D.SPRING_X0, D.SPRING_GUIDE_X[1], 0, D.AXLE_Z)
    rollers = {g: P.roller().translate((x, 0, z)) for x, z, g in P.ROLLERS}
    free = P.xring(D.SPRING['od']/2, D.SPRING['id']/2,
                   D.SPRING_X0, D.SPRING_X0 + D.SPRING['free'], 0, D.AXLE_Z)
    insertion = [dict(offset_mm=dx, overlap_mm3=volume(free.translate((dx, 0, 0)).intersect(frame)))
                 for dx in (40, 20, 8, 1, 0)]
    report = dict(revision='J9 recessed spring guide',
                  dimensions_mm=dict(**D.SPRING_POCKET, seat_x=D.SPRING_X0, guide_x=list(D.SPRING_GUIDE_X),
                                     spring_radial_clearance=(D.SPRING_POCKET['bore_d'] - D.SPRING['od'])/2,
                                     piston_radial_clearance=(D.SPRING_POCKET['bore_d'] - D.SPRING_POCKET['piston_d'])/2,
                                     guide_wall=(D.SPRING_POCKET['outer_d'] - D.SPRING_POCKET['bore_d'])/2,
                                     spring_end_inside_guide_at_extension=D.SPRING_GUIDE_X[1] - D.SPRING_X0 - D.SPRING_SET,
                                     spring_above_solid_at_recoil=D.SPRING_SET - D.RECOIL - D.SPRING['solid']),
                  frame_one_valid_solid=P.one(frame).isValid() and len(frame.solids().vals()) == 1,
                  yoke_one_valid_solid=P.one(yoke).isValid() and len(yoke.solids().vals()) == 1,
                  travel=rows, free_spring_insertion=insertion,
                  guide_to_rollers_mm={n: distance(guide, r) for n, r in rollers.items()},
                  scope='Nominal exact CAD clearance and full spring-envelope checks. No structural, wear or physical print verification.')
    report['pass'] = (report['frame_one_valid_solid'] and report['yoke_one_valid_solid'] and
                      all(r[k] < 1e-6 for r in rows for k in ('spring_frame_overlap_mm3', 'spring_yoke_overlap_mm3', 'yoke_frame_overlap_mm3')) and
                      all(r['overlap_mm3'] < 1e-6 for r in insertion) and
                      min(report['guide_to_rollers_mm'].values()) > .5 and
                      report['dimensions_mm']['spring_end_inside_guide_at_extension'] > 0)
    return report


if __name__ == '__main__':
    result = check()
    (P.ROOT / 'spring_guide_validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    assert result['pass'], 'Spring pocket CAD checks failed'

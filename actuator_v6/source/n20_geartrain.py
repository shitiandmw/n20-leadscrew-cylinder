"""Parametric illustrative N20 metal internals. Not production fabrication CAD.

Gearbox geometry from n20_geartrain (1).zip, used by n20_screw_motor. All parts are already
at their zero-output pose. The phase/ratio contract lives in gear_spec.py.
"""
import math
import cadquery as cq
from functools import lru_cache
from gear_spec import CENTRES, STAGES, phases, involute_points, transmission


def cylinder(r, z0, z1, xy=(0,0)):
    return cq.Workplane('XY').circle(r).extrude(z1-z0).translate((*xy,z0))


def box(dx,dy,z0,z1,xy=(0,0)):
    return cq.Workplane('XY').box(dx,dy,z1-z0,centered=(True,True,False)).translate((*xy,z0))


def ring(ro,ri,z0,z1,xy=(0,0)):
    return cq.Workplane('XY').circle(ro).circle(ri).extrude(z1-z0).translate((*xy,z0))


def double_d(d,flat,z0,z1):
    return cylinder(d/2,z0,z1).intersect(box(flat,d+1,z0,z1))


def gear(teeth, body, z0, z1):
    x,y=CENTRES[body]
    return (cq.Workplane('XY').polyline(involute_points(teeth)).close().extrude(z1-z0)
            .rotate((0,0,0),(0,0,1),math.degrees(phases()[body])).translate((x,y,z0)))


def d_section(z0,z1):
    # Nominal keyed seat: zero material overlap, shared D faces transmit torque.
    return cylinder(1.5,z0,z1).cut(box(4,5,z0-.01,z1+.01,(3.2,0)))


def output_spindle():
    """Verified keyed shaft below Z=.7, for independently supplied threads."""
    shaft=cylinder(1.5,-4.83,.7)
    shaft=shaft.cut(box(4,5,-3.95,-2.65,(3.2,0)))
    return shaft.union(cylinder(1.75,-4.83,-4.73))


@lru_cache(maxsize=1)
def gearbox_parts():
    """Archive internals, excluding the independently supplied V6 thread."""
    hw={}
    # Preserve original outside; provide the rotor's real internal free volume.
    can=double_d(12,10,-23.,-9.).cut(double_d(11.4,9.4,-23.01,-8.99))
    for x in (-5.,5.):
        for y in (-2.,2.): can=can.cut(cylinder(.22,-19.5,-13.5,(x,y)))
    hw['motor_can']=can
    hw['motor_end_cap']=double_d(12,10,-24.,-23.).cut(cylinder(.85,-24.1,-22.9))
    hw['motor_rear_boss']=ring(2.5,.85,-25.2,-24.)
    for i,y in enumerate((-3.65,3.65),1):
        tab=box(1.5,.3,-26.5,-24.,(0,y))
        hole=cylinder(.3,-.5,.5).rotate((0,0,0),(1,0,0),90).translate((0,y,-25.7))
        hw[f'motor_terminal_{i}']=tab.cut(hole)

    plate_specs=[('rear',-9.,-8.2),('middle',-4.65,-4.15),('front',-.8,0.)]
    frame=None
    for label,z0,z1 in plate_specs:
        p=box(10,12,z0,z1).edges('|Z').fillet(.6)
        for body in ('compound_a','compound_b'):
            p=p.cut(cylinder(.70,z0-.1,z1+.1,CENTRES[body]))
            hw[f'motor_bushing_{body}_{label}']=ring(.70,.465,z0,z1,CENTRES[body])
        ro={'rear':.85,'middle':1.8,'front':2.0}[label]
        p=p.cut(cylinder(ro,z0-.1,z1+.1))
        if label=='rear': hw['motor_bushing_input_front']=ring(.85,.515,z0,z1)
        elif label=='middle': hw['motor_bushing_output_rear']=ring(1.8,1.525,z0,z1)
        else:
            for y in (-4.5,4.5): p=p.cut(cylinder(.7,-2.1,.1,(0,y)))
        frame=p if frame is None else frame.union(p)
    # Internal post location is intentionally different from unknown internals.
    for x in (-3.7,3.7): frame=frame.union(cylinder(.95,-9.,0.,(x,-4.4)))
    hw['motor_gearbox_frame']=frame.clean()
    hw['motor_front_bushing']=ring(2.,1.525,-.8,.7)
    hw['motor_bushing_input_rear']=ring(.85,.515,-24.9,-23.4)

    # Input pinion, rotor shaft and simplified rotor envelope are one solid.
    rotor=cylinder(.5,-24.8,-6.75).union(cylinder(3.2,-21.8,-11.0))
    rotor=rotor.union(cylinder(.65,-9.35,-9.15))
    hw['motor_gear_1']=rotor.union(gear(18,'input',-7.85,-6.95)).clean()
    for number,body,large,small in [(2,'compound_a',STAGES[0],STAGES[1]),
                                   (3,'compound_b',STAGES[1],STAGES[2])]:
        xy=CENTRES[body]
        s=cylinder(.45,-9.,0.,xy)
        # Integral shoulders provide axial capture with .1 mm face clearance.
        for z0,z1 in [(-8.1,-7.95),(-1.05,-.9)]: s=s.union(cylinder(.59,z0,z1,xy))
        s=s.union(gear(54,body,large['zmin'],large['zmax']))
        s=s.union(gear(18,body,small['zmin'],small['zmax']))
        hw[f'motor_gear_{number}']=s.clean()
    out=gear(54,'output',-3.85,-2.75).union(cylinder(1.9,-3.95,-2.65))
    hw['motor_gear_4']=out.cut(d_section(-4.0,-2.6)).clean()
    return hw


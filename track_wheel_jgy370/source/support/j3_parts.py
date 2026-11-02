"""J3: detachable chassis docking beams and vented motor enclosure.

Independent geometry informed by the public ProfessorBoots excavator previews.
All dimensions mm. The X bridge is a proposed interface, not supplied user CAD.
"""
import sys
from pathlib import Path
from support_paths import ROOT, REPO
import j2_parts as j2
import cadquery as cq
from shapely.geometry import Point, LineString
p=j2.p
DX,DZ=j2.DX,j2.DZ
DOCK_X=[-35.,90.]

def frame():
    s=j2.frame()
    # Two drain openings in the low wall, below the gearbox and away from bosses.
    for x in [-108.,-96.]:
        s=s.cut(p.box(x-3,x+3,-64,-58,17,23))
    return s.clean()

def lid():
    s=j2.lid()
    # Rounded 22 x 2.5 ventilation slots in front of the can; no claimed IP rating.
    for z in [37.5,43.5,49.5,55.5]:
        slot=LineString([(-76,z),(-56.5,z)]).buffer(1.25,resolution=12)
        s=s.cut(p.xz_prism(slot,-74,-71))
    return s.clean()

def beam():
    s=p.box(-73,128,-64,-44,70,78)
    # Two local outboard scallops clear the retained upper-roller collars.
    for x in p.ex.RETURN_ROLLERS:
        s=s.cut(p.ycyl(8.6,-47.6,-43,x,p.RETURN_Z))
    for x in j2.MOUNT_X:s=s.cut(p.zcyl(2.7,69,79,x,-54))
    for x in DOCK_X:
        s=s.cut(p.box(x-13,x+13,-63,-45,76,79))
        s=s.cut(p.zcyl(2,69,79,x,-54)) # M4 tapped hole, simplified major diameter
    return s.clean()

def xy_prism(poly,z0,z1):
    wire=cq.Wire.makePolygon([cq.Vector(x,y,z0) for x,y in list(poly.exterior.coords)[:-1]],close=True)
    holes=[cq.Wire.makePolygon([cq.Vector(x,y,z0) for x,y in list(r.coords)[:-1]],close=True) for r in poly.interiors]
    return cq.Workplane(obj=cq.Solid.extrudeLinear(cq.Face.makeFromWires(wire,holes),cq.Vector(0,0,z1-z0)))

def xbridge(lift_sweep=0):
    # No slew mounting holes specified: central Ø66 opening is only a space reserve.
    poly=Point(15,0).buffer(47,resolution=48)
    for x in DOCK_X:
        for y in [-116,116]:
            poly=poly.union(LineString([(15,0),(x,y)]).buffer(11,resolution=12))
    poly=poly.difference(Point(15,0).buffer(33,resolution=48))
    s=xy_prism(poly,78,82+lift_sweep)
    for x in DOCK_X:
        for y in [-116,116]:
            s=s.union(p.box(x-12.75,x+12.75,y-8.75,y+8.75,76.2,78.2+lift_sweep))
            s=s.cut(p.zcyl(2.25,75,83+lift_sweep,x,y))
    return s.clean()

def docking_hardware():
    out={}
    def add(n,shape,color=p.STEEL):
        out[n]=dict(shape=shape,color=color,kind='hardware',group='dock',source=None)
    for i,x in enumerate(j2.MOUNT_X):
        add(f'J3_beam_M5x16_{i}',p.zcyl(2.5,63,79,x,-54).union(p.zcyl(4.25,79,84,x,-54)).cut(p.zhex(4,81,85,x,-54)))
        add(f'J3_beam_washer_{i}',p.zcyl(5,78,79,x,-54).cut(p.zcyl(2.65,77,80,x,-54)))
    return out

def bridge_hardware():
    out={}
    for x in DOCK_X:
        for y in [-116,116]:
            screw=p.zcyl(2,71,83,x,y).union(p.zcyl(3.5,83,87,x,y)).cut(p.zhex(3,84,88,x,y))
            washer=p.zcyl(4.5,82,83,x,y).cut(p.zcyl(2.15,81,84,x,y))
            for suffix,s in [('M4x12',screw),('washer',washer)]:
                out[f'J3_bridge_{x:g}_{y:g}_{suffix}']=dict(shape=s,color=p.STEEL,kind='hardware',group='bridge',source=None)
    return out

def parts():
    out={n:d for n,d in j2.parts().items() if n not in ['J206_integrated_track_frame','J211_contoured_motor_lid']}
    def add(n,shape,material,kind,note,color):
        out[n]=dict(shape=shape,material=material,kind=kind,note=note,color=color,quantity=1)
    add('J306_drained_track_frame',frame(),'PETG or PA','printed','J2 integrated rail/enclosure with two 6 x 6 drain openings.',j2.FRAME_COLOR)
    add('J311_vented_protective_lid',lid(),'1 mm stainless steel','sheet','Four 22 x 2.5 rounded slots. Retains four independent lid screws.',j2.COVER_COLOR)
    add('J313_chassis_docking_beam',beam(),'6061-T6 aluminum','machined','201 x 20 x 8, mounts to all three original pads. Two locating pockets and M4 tapped holes.',(.52,.59,.62))
    return out

def unit(new):
    # j2.unit starts from J1, so use the finalized J2 assembly then replace rail/lid.
    base=j2.unit(j2.parts())
    for n in ['J206_integrated_track_frame','J211_contoured_motor_lid']:base.pop(n)
    for n,d in new.items():
        base[n]={**d,'group':'drive' if n in ['J03_hex_drive_cap','J10_torque_spindle'] else 'frame','source':n}
    base.update(docking_hardware())
    return base

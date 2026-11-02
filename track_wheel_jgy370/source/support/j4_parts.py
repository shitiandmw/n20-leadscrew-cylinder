"""J4: a single removable printed protective shell; all public media in English.

Nominal geometry, mm. The structural rail remains independent for motor service.
"""
import sys
from pathlib import Path
from support_paths import ROOT, REPO
import j3_parts as j3
import cadquery as cq
from shapely.geometry import LineString
j2=j3.j2
p=j3.p
DX,DZ=j3.DX,j3.DZ
COVER_HOLES=[(-136.5,DZ-7),(-136.5,DZ+7),(-39.,30.),(-48.,65.3)]

def frame():
    s=cq.importers.importStep(str(REPO/'track_wheel/step/TW06_track_frame.step'))
    for x in j2.MOUNT_X:
        s=s.union(p.box(x-6,x+6,-60,-47,64,70))
        s=s.cut(p.zcyl(2.7,59,71,x,-54)).cut(p.zcyl(3.4,64,71,x,-54))
    for x,z in j2.j1.MOTOR_HOLES:
        if x>DX:s=s.cut(p.ycyl(3.2,-43,-29,x,z))
    # Mounting columns are integral to the fixed rail, hidden inside the cover.
    for x,z in COVER_HOLES:
        s=s.union(p.ycyl(3.5,-69,-34.5,x,z))
        s=s.cut(p.ycyl(2,-69.1,-63,x,z))
        s=s.cut(p.ycyl(1.7,-63.1,-61.5,x,z))
    return s.clean()

def motor_plate():
    s=j2.face_plate()
    # Clearance notches for the two rear cover columns; all mounting datums kept.
    for x,z in COVER_HOLES[:2]:
        s=s.cut(p.ycyl(3.75,-46,-41,x,z)).cut(p.box(-147,x,-46,-41,z-3.75,z+3.75))
    return s.clean()

def cover():
    outer=j2.profile();inner=outer.buffer(-2.5)
    s=p.xz_prism(outer,-73,-42.3).cut(p.xz_prism(inner,-70.5,-41.8))
    # Preserve the 0.8 mm motor-can clearance without widening the module.
    # 2.5 mm front skin elsewhere; minimum 1.0 mm over the can crown.
    can_relief=p.xcyl(12.8,DX+30.5,DX+63.3,-59.2,DZ)
    s=s.cut(can_relief)
    # Open-backed clearances slide off the fixed original chassis pad and collars.
    s=s.cut(p.box(-75.3,-44.7,-60.3,-41,63.7,71))
    s=s.cut(p.ycyl(31.3,-44.3,-41,DX,DZ))
    for x,z in [(x,29) for x in p.ex.ROAD_ROLLERS]+[(x,p.RETURN_Z) for x in p.ex.RETURN_ROLLERS]:
        s=s.cut(p.ycyl(4.6,-54.3,-41,x,z)).cut(p.ycyl(8.7,-47.8,-41,x,z))
    # The wire outlet is open to the back so wires can stay connected on removal.
    s=s.cut(p.box(-39,-30,-67.3,-41,38.7,53.3))
    for x in [-108.,-96.]:s=s.cut(p.box(x-3,x+3,-64,-58,17,23))
    for z in [37.5,43.5,49.5,55.5]:
        s=s.cut(p.xz_prism(LineString([(-76,z),(-56.5,z)]).buffer(1.25,resolution=12),-74,-69.5))
    for x,z in COVER_HOLES:
        # Solid 4 mm local screw pads seat directly on the fixed columns.
        s=s.union(p.ycyl(4,-73,-69,x,z))
        s=s.cut(p.ycyl(3.75,-69,-41,x,z))
        s=s.cut(p.ycyl(1.7,-74,-68.9,x,z)).cut(j2.j1.cone(3,1.7,-73,-71.7,x,z))
    return s.clean()

def parts():
    out={n:d for n,d in j3.parts().items() if n not in ['J306_drained_track_frame','J311_vented_protective_lid','J202_motor_mount_plate']}
    def add(n,shape,material,kind,note,color):
        out[n]=dict(shape=shape,material=material,kind=kind,note=note,color=color,quantity=1)
    add('J402_motor_mount_plate',motor_plate(),'6061-T6 aluminum','machined','Original motor/carrier holes retained; two clearance notches for fixed cover columns.',p.STEEL)
    add('J406_serviceable_track_frame',frame(),'PETG or PA','printed','Structural rail with four integral hidden cover columns and original chassis interfaces.',j2.FRAME_COLOR)
    add('J411_one_piece_protective_shell',cover(),'PA12 preferred; PETG fit prototype','printed','One solid: front, top, bottom and end walls. Nominal 2.5 mm wall; locally 1.0 mm over the can crown.',j2.COVER_COLOR)
    return out

def unit(new):
    base=j3.unit(j3.parts())
    base={n:d for n,d in base.items() if n not in ['J306_drained_track_frame','J311_vented_protective_lid','J202_motor_mount_plate'] and not n.startswith(('J2_lid_M3x8','J2_lid_insert'))}
    for n,d in new.items():base[n]={**d,'group':'drive' if n in ['J03_hex_drive_cap','J10_torque_spindle'] else 'frame','source':n}
    for i,(x,z) in enumerate(COVER_HOLES):
        base[f'J4_cover_M3x10_{i}']=dict(shape=j2.j1.csk_screw(x,z,-73,10),group='frame',kind='hardware',color=p.BLACK,source=None)
        base[f'J4_cover_insert_{i}']=dict(shape=p.yring(2,1.5,-68.8,-63.1,x,z),group='frame',kind='hardware',color=p.BRASS,source=None)
    return base

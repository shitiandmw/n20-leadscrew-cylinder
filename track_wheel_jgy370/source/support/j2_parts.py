"""J2: integrated drive enclosure and chassis attachment operated from above.

Uses the J1 motor location and torque path. X-frame is a marked dimensional
reference because no actual X-frame CAD was supplied/found.
"""
import sys, math
from pathlib import Path
from support_paths import ROOT, REPO
import cadquery as cq
from shapely.geometry import Point, Polygon, box as polygon_box
from shapely.ops import unary_union

import structure as j1
p=j1.p
DX,DZ=p.DX,p.DZ
GUARD_HOLES=[p.polar(29,145),p.polar(29,215),(-44.,30.),(-48.,65.3)]
MOUNT_X=[-60.,0.,115.]
MOUNT_Y=-54.
FRAME_COLOR=(.115,.15,.17)
COVER_COLOR=(.16,.205,.23)


def profile():
    # Avoid a faceted polygon coincident with the original analytic R33 boss.
    disc=Point(DX,DZ).buffer(33.15,resolution=48)
    front=Polygon([(DX,26),(-43,26),(-33,31),(-33,57),(-47,69.3),(DX,69.3)])
    return unary_union([disc,front]).intersection(polygon_box(-150,18,0,69.3))


def face_plate():
    s=j1.mount_plate()
    for x,z in j1.FRAME_HOLES:
        s=s.cut(j1.cone(3,1.7,-44,-42.7,x,z))
    return s.clean()


def enclosure():
    outer=profile();inner=outer.buffer(-2.5)
    shell=p.xz_prism(outer,-72,-41.9).cut(p.xz_prism(inner,-73,-41.8))
    for x,z in GUARD_HOLES:
        shell=shell.union(p.ycyl(3.5,-72,-62.5,x,z))
    # The motor face plate is a separate machined component, clear of the shell.
    plate_clear=p.ycyl(31.25,-44.25,-41.8,DX,DZ)
    shell=shell.cut(plate_clear)
    # Retained roller hardware passes through dedicated clearances in the enclosure.
    for x,z in [(x,29) for x in p.ex.ROAD_ROLLERS]+[(x,p.RETURN_Z) for x in p.ex.RETURN_ROLLERS]:
        shell=shell.cut(p.ycyl(4.4,-54,-41.8,x,z))
        shell=shell.cut(p.ycyl(8.6,-47.6,-41.8,x,z))
    # A cable outlet at the forward end; not a sealed enclosure.
    shell=shell.cut(p.box(-39,-30,-67,-56,39,53))
    # Four original carrier bolts remain accessible from inboard after lid removal.
    for x,z in j1.FRAME_HOLES:
        shell=shell.cut(p.ycyl(3.2,-73,-41.8,x,z))
    for x,z in GUARD_HOLES:
        shell=shell.cut(p.ycyl(2,-73,-65.5,x,z))
        shell=shell.cut(p.ycyl(1.7,-65.6,-64.4,x,z))
        shell=shell.cut(j1.cone(3,1.7,-73,-71.7,x,z))
    return shell.clean()


def frame():
    s=cq.importers.importStep(str(REPO/'track_wheel/step/TW06_track_frame.step'))
    # All former side-mounted posts are gone. The cradle joins the original rail.
    s=s.union(enclosure())
    # Fill the old front nut slot and provide the same insert detail at all pads.
    for x in MOUNT_X:
        s=s.union(p.box(x-6,x+6,-60,-47,64,70))
        s=s.cut(p.zcyl(2.7,59,71,x,MOUNT_Y))
        s=s.cut(p.zcyl(3.4,64,71,x,MOUNT_Y))
    for x,z in j1.MOTOR_HOLES:
        if x>DX:s=s.cut(p.ycyl(3.2,-43,-29,x,z))
    return s.clean()


def lid():
    s=p.xz_prism(profile().buffer(-.15),-73,-72)
    for x,z in GUARD_HOLES:
        s=s.cut(p.ycyl(1.7,-74,-71,x,z)).cut(j1.cone(3,1.7,-73,-71.7,x,z))
    return s.clean()


def parts():
    # Keep J1's completed independent bearing support and direct-drive components.
    old=j1.parts()
    new={n:d for n,d in old.items() if n not in ['J02_motor_mount_plate','J06_track_frame','J11_motor_protective_plate'] and not n.startswith('J12_')}
    def add(n,s,material,kind,note,color=FRAME_COLOR):
        new[n]=dict(shape=s,color=color,material=material,kind=kind,note=note,quantity=1)
    add('J202_motor_mount_plate',face_plate(),'6061-T6 aluminum','machined','Same motor and rail hole centres; all four frame screws now countersunk.',p.STEEL)
    add('J206_integrated_track_frame',frame(),'PETG or PA','printed','Rail and contoured drive enclosure in one part; three M5 inserts for top-operated chassis bolts.')
    add('J211_contoured_motor_lid',lid(),'1 mm stainless steel','sheet','Flat contoured lid seats directly on enclosure; four flush M3 screws; no projecting posts.',COVER_COLOR)
    return new


def unit(new=None):
    new=parts() if new is None else new
    old=j1.parts();inst=j1.assembly(old)
    remove=['J02_motor_mount_plate','J06_track_frame','J11_motor_protective_plate','J12_guard_post_',
            'J_guard_csk_','J_guard_frame_insert_','J_carrier_csk_']
    inst={n:d for n,d in inst.items() if not any(n.startswith(prefix) for prefix in remove)}
    for n,d in new.items():
        inst[n]={**d, 'group':'drive' if n in ['J03_hex_drive_cap','J10_torque_spindle'] else 'frame','source':n}
    def hw(n,s,color=p.BLACK):
        inst[n]=dict(shape=s,color=color,group='frame',kind='hardware',source=None)
    for i,(x,z) in enumerate(j1.FRAME_HOLES):
        hw('J2_carrier_M3x6_'+str(i),j1.csk_screw(x,z,-44,6))
    for i,(x,z) in enumerate(GUARD_HOLES):
        hw('J2_lid_M3x8_'+str(i),j1.csk_screw(x,z,-73,8))
        hw('J2_lid_insert_'+str(i),p.yring(2,1.5,-71.3,-65.6,x,z),p.BRASS)
    for i,x in enumerate(MOUNT_X):
        insert=p.zcyl(3.4,64.1,69.9,x,MOUNT_Y).cut(p.zcyl(2.5,63,71,x,MOUNT_Y))
        hw('J2_chassis_M5_insert_'+str(i),insert,p.BRASS)
    # Distinguish metal from printed rail without the former blue bolt-on cover.
    inst['TW02_sprocket_hub']['color']=FRAME_COLOR
    return inst


def chassis_hardware():
    """Review fixture: a 10 mm chassis foot and M5x18 + 1 mm washer.

    These are not claimed to be the user's actual X-frame interfaces.
    """
    out={}
    for i,x in enumerate(MOUNT_X):
        foot=p.box(x-12,x+12,-66,-42,70,80).cut(p.zcyl(2.7,69,81,x,MOUNT_Y))
        washer=p.zcyl(5,80,81,x,MOUNT_Y).cut(p.zcyl(2.65,79,82,x,MOUNT_Y))
        screw=p.zcyl(2.5,63,81,x,MOUNT_Y).union(p.zcyl(4.25,81,86,x,MOUNT_Y))
        socket=p.zhex(4,83,87,x,MOUNT_Y)
        screw=screw.cut(socket)
        for suffix,shape in [('foot',foot),('washer',washer),('bolt',screw)]:
            out[f'chassis_fixture_{i}_{suffix}']=dict(shape=shape,color=(.36,.58,.61) if suffix=='foot' else p.STEEL,kind='hardware',group='chassis_fixture',source=None)
    return out


def xframe_reference():
    """Explicitly an interface demonstrator: four arms at original end mounts.

    No X-frame CAD exists in the checked workspace. The central mounting holes,
    section and dimensions are illustrative, not a production chassis design.
    """
    body=Point(0,0).buffer(47,resolution=40)
    for x in [-60,115]:
        for y in [-116,116]:
            # Polygon swept around a line between centre and retained attachment point.
            from shapely.geometry import LineString
            body=body.union(LineString([(0,0),(x,y)]).buffer(12,resolution=8))
    body=body.difference(Point(0,0).buffer(33,resolution=40))
    wire=cq.Wire.makePolygon([cq.Vector(x,y,70) for x,y in list(body.exterior.coords)[:-1]],close=True)
    holes=[cq.Wire.makePolygon([cq.Vector(x,y,70) for x,y in list(r.coords)[:-1]],close=True) for r in body.interiors]
    face=cq.Face.makeFromWires(wire,holes)
    s=cq.Workplane(obj=cq.Solid.extrudeLinear(face,cq.Vector(0,0,10)))
    for x in [-60,115]:
        for y in [-116,116]:s=s.cut(p.zcyl(2.7,69,81,x,y))
    return s.clean()

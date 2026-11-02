"""JGY-370 structural revision J1, mm, using unchanged R5 running gear.

Nominal prototype CAD. Purchased motor holes/threads require inspection.
The metal spindle has a D socket and an axially floating hex drive into cap.
"""
import sys, math
from pathlib import Path
from support_paths import ROOT, REPO
import cadquery as cq

sys.path.insert(0, str(REPO / 'track_wheel/source'))
import tw_parts as p
from check_packaging import motor_shapes

DX, DZ = p.DX, p.DZ
box, ycyl, yring, zcyl = p.box, p.ycyl, p.yring, p.zcyl
MOTOR_HOLES = [(DX+x, DZ+z) for x in (-9,24) for z in (-9,9)]
FRAME_HOLES = [p.polar(27,a) for a in p.FLANGE_SCREWS]
GUARD_HOLES = [(DX-27/math.sqrt(2), DZ+z*27/math.sqrt(2)) for z in (-1,1)] + [(-18.5,DZ+z*27/math.sqrt(2)) for z in (-1,1)]
RETAINER_HOLES = [p.polar(15,a) for a in (0,90,180,270)]
BODY_HOLES = [p.polar(19.25,a) for a in (0,90,180,270)]


def yhex(af, y0, y1):
    return cq.Workplane('XZ').center(DX,DZ).polygon(6,af*2/math.sqrt(3)).extrude(y1-y0).translate((0,y1,0))


def cone(r0,r1,y0,y1,x,z):
    return cq.Workplane(obj=cq.Solid.makeCone(r0,r1,y1-y0,cq.Vector(x,y0,z),cq.Vector(0,1,0)))


def carrier():
    # Open rear bore: accessible to turning/boring before bolting on face plate.
    s = yring(22.5,16,-42,-3.5,DX,DZ)
    s = s.union(ycyl(20,-3.5,3.4,DX,DZ))
    s = s.cut(yring(23,21.4,-3.9,-3.4,DX,DZ))
    s = s.cut(ycyl(6.5,-4,4,DX,DZ))
    for x,z in MOTOR_HOLES:
        # Straight driver approach through the end wall for the two inner holes.
        if x < DX:
            s = s.cut(ycyl(3.2,-4,4,x,z))
    for x,z in BODY_HOLES:
        s = s.cut(ycyl(1.5,-43,-34,x,z))
    for x,z in RETAINER_HOLES:
        s = s.cut(ycyl(1.5,-3,4,x,z))  # M3 tap representation; blind 6.4 mm
    return s.clean()


def mount_plate():
    # Retains motor face pattern and the four original rail bolt centres.
    s=ycyl(31,-44,-42,DX,DZ).cut(box(DX-40,DX+40,-45,-41,69.3,90))
    # Pilot recess locates the supplied Ø13.2 motor boss (0.2 diametral clearance).
    s=s.union(ycyl(9,-45.8,-44,DX,DZ)).cut(ycyl(6.7,-47,-41,DX,DZ))
    for x,z in MOTOR_HOLES:s=s.cut(ycyl(1.7,-45,-41,x,z))
    for x,z in FRAME_HOLES+BODY_HOLES:
        s=s.cut(ycyl(1.7,-45,-41,x,z))
        if (x,z) in BODY_HOLES or x>DX:s=s.cut(cone(3,1.7,-44,-42.7,x,z))
    return s.clean()


def retainer():
    s = yring(21.4,6.5,3.5,6.5,DX,DZ)
    for x,z in RETAINER_HOLES:
        s=s.cut(ycyl(1.7,3,7,x,z))
    return s.clean()


def cap():
    # Original outside and six mounting screws; internal ring gear removed.
    s = yring(25.95,25,3.5,7,DX,DZ).union(yring(32.8,25,7,19,DX,DZ))
    s = s.union(ycyl(32.8,19,22,DX,DZ))
    s = s.union(ycyl(18,10,19.01,DX,DZ))
    for a in range(0,360,60):
        web=box(17,25.1,10,19,-2,2).rotate((0,0,0),(0,-1,0),a).translate((DX,0,DZ))
        s=s.union(web)
    s=s.cut(yhex(24.2,9,19))  # Hex drive has 1 mm axial end clearance.
    s=s.cut(ycyl(3.5,18.9,23,DX,DZ))  # access to the shaft retaining screw
    for a in p.insert_angles():
        x,z=p.polar(p.CAP_SCREW_R,a)
        s=s.cut(ycyl(1.7,6,23,x,z))
    return s.clean()


def spindle():
    s=ycyl(6,-41.5,12.01,DX,DZ).union(yhex(24,12,18))
    # Blind D socket: shoulder seats on shaft tip at -30.4, not on the hub.
    socket=ycyl(3.02,-42,-30.4,DX,DZ).cut(box(DX-4,DX+4,-43,-29,DZ+2.52,DZ+4))
    s=s.cut(socket).cut(ycyl(1.7,-30.41,19,DX,DZ))
    return s.clean()


def frame():
    s=cq.importers.importStep(str(REPO/'track_wheel/step/TW06_track_frame.step'))
    # The rail, chassis bolts and carrier bolt centres remain unchanged.
    for x,z in MOTOR_HOLES:
        if x>DX:s=s.cut(ycyl(3.2,-43,-29,x,z))
    for x,z in GUARD_HOLES[2:]:
        s=s.cut(ycyl(2,-43,-36,x,z))
    return s.clean()


def guard():
    # 1 mm formed sheet; ideal bend corners. Shop applies R1 bend allowance.
    s=box(-135,-13,-73,-72,22,69.3)
    s=s.union(box(-135,-13,-72.01,-55,22,23))
    s=s.union(box(-135,-13,-72.01,-61,68.3,69.3))
    for x,z in GUARD_HOLES:
        s=s.cut(ycyl(1.7,-74,-71,x,z)).cut(cone(3,1.7,-73,-71.7,x,z))
    return s.clean()


def post(x,z,front=False):
    end=-42 if front else -44
    s=yring(2.5,1.55,-72,-66,x,z).union(ycyl(2.5,-66,end,x,z))
    s=s.union(ycyl(1.5,end,-38,x,z))
    # Continues the plate countersink into the backing post.
    s=s.cut(cone(3,1.7,-73,-71.7,x,z))
    return s.clean()


def csk_screw(x,z,face,length):
    return cone(2.85,1.5,face,face+1.35,x,z).union(ycyl(1.5,face+1.35,face+length,x,z))


def parts():
    out={}
    def add(n,s,c,material,kind,note):
        out[n]=dict(shape=s,color=c,material=material,kind=kind,note=note,quantity=1)
    add('J01_bearing_carrier_motor_mount',carrier(),p.STEEL,'6061-T6 aluminum','machined','Open-backed bearing carrier; finish seats; four M3 rear and four M3 retainer taps.')
    add('J02_motor_mount_plate',mount_plate(),p.STEEL,'6061-T6 aluminum','machined','2 mm plate with 1.8 mm raised pilot ring; motor and original carrier mounting holes retained.')
    add('J03_hex_drive_cap',cap(),p.YELLOW,'tough PETG or PA','printed','Original six screws; AF24.2 socket. Print closed outer face down.')
    add('J04_bearing_retainer',retainer(),p.STEEL,'6061-T6 aluminum','machined','Four independent M3x8 screws; do not preload bearing seals.')
    add('J06_track_frame',frame(),p.DARK,'PETG','printed','R5 rail with motor driver access and two added guard insert holes. Outboard face down.')
    add('J10_torque_spindle',spindle(),p.STEEL,'C45 steel','machined','D6.04 socket, AF24 drive, M3 axial through hole. Not a printed part.')
    add('J11_motor_protective_plate',guard(),(.35,.53,.63),'1 mm stainless steel','sheet','Folded removable guard. Nominal formed model; shop develops bends with R1 inner radius.')
    for i,(x,z) in enumerate(GUARD_HOLES):
        add('J12_guard_post_'+str(i),post(x,z,i>=2),p.STEEL,'steel','machined','D5 post; female M3x6 at guard; male M3, carrier posts L28+6, front posts L30+4.')
    return out


def assembly(new=None):
    new=parts() if new is None else new
    # Load the unchanged printed solids, then use the proven R5 hardware placement.
    oldparts={}
    for path in (REPO/'track_wheel/step').glob('*.step'):
        if path.stem in ['track_wheel_unit','TW06_track_frame_left']:continue
        oldparts[path.stem]=dict(shape=cq.importers.importStep(str(path)),color=p.YELLOW if path.stem in ['TW03_hub_cap','TW07_idler_yoke'] else p.DARK)
    inst=p.unit_instances(oldparts)
    obsolete=['TW01_motor_housing','TW03_hub_cap','TW04_bearing_retainer','TW05_motor_rear_cap','TW06_track_frame',
              'gearmotor_','hub_pinion','pinion_set_screw','face_screw_','flange_screw_','rear_cap_screw_','pillar_insert_']
    inst={n:d for n,d in inst.items() if not any(n==s or n.startswith(s) for s in obsolete)}
    for n,d in new.items():
        inst[n]={**d,'group':'drive' if n in ['J03_hex_drive_cap','J10_torque_spindle'] else 'frame','source':n}
    motor=motor_shapes()
    gb=motor['JGY_gearbox_envelope']
    for x,z in MOTOR_HOLES:gb=gb.cut(ycyl(1.5,-49,-43,x,z))
    motor['JGY_gearbox_envelope']=gb
    motor['JGY_output_shaft']=motor['JGY_output_shaft'].cut(ycyl(1.5,-40.4,-29,DX,DZ))
    for n,s in motor.items():
        if n.startswith('reserved'):continue
        inst[n]=dict(shape=s,color=p.ORANGE if 'gearbox' in n else p.STEEL,group='drive' if 'shaft' in n else 'frame',kind='hardware',source=None)
    def hw(n,s,grp='frame',color=p.BLACK):
        inst[n]=dict(shape=s,color=color,group=grp,kind='hardware',source=None)
    for i,(x,z) in enumerate(MOTOR_HOLES):
        hw('J_motor_M3x5_'+str(i),p.screw(1.5,2.85,1.65,-42,5,x,z))
    for i,(x,z) in enumerate(FRAME_HOLES):
        if x>DX:hw('J_carrier_csk_M3x6_'+str(i),csk_screw(x,z,-44,6))
    for i,(x,z) in enumerate(BODY_HOLES):
        hw('J_body_csk_M3x8_'+str(i),csk_screw(x,z,-44,8))
    for i,(x,z) in enumerate(RETAINER_HOLES):
        hw('J_retainer_M3x8_'+str(i),p.screw(1.5,2.85,1.65,6.5,8,x,z))
    for i,(x,z) in enumerate(GUARD_HOLES):
        hw('J_guard_csk_M3x6_'+str(i),csk_screw(x,z,-73,6))
        if i>=2:hw('J_guard_frame_insert_'+str(i),yring(2,1.5,-41.95,-36.3,x,z),color=p.BRASS)
    hw('J_shaft_retaining_M3x55',p.screw(1.5,2.85,1.65,18,55,DX,DZ),'drive')
    return inst

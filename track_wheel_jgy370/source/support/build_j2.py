"""Retained interface checks and STEP assembly exporter used by J8."""
import json, gzip, shutil, time
import cadquery as cq
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
import j2_parts as s
import tw_checks as checks
import build_track_wheel as export
from build_structure import distance

ROOT,REPO,p=s.ROOT,s.REPO,s.p


def exact_bounds(inst):
    boxes=[]
    for d in inst.values():
        b=Bnd_Box();BRepBndLib.AddOptimal_s(p.one(d['shape']).wrapped,b,False,False);boxes.append(b.Get())
    return [[min(b[i] for b in boxes) for i in range(3)],[max(b[i+3] for b in boxes) for i in range(3)]]


def check(inst):
    fixtures=s.chassis_hardware()
    context={**inst,**fixtures}
    changed=lambda n:n.startswith('J2') or n.startswith('chassis_fixture')
    report=checks.interference(context,skip=lambda a,b:not(changed(a) or changed(b)))
    report['bounds_mm']=exact_bounds(inst)
    old=json.loads((s.ROOT/'references/retained_dimensions.json').read_text())['original_unit_bounds_mm']
    report['within_original_envelope']=all(report['bounds_mm'][0][i]>=old[0][i]-.002 and report['bounds_mm'][1][i]<=old[1][i]+.002 for i in range(3))
    # The actual known rectangular bridge is an additional conservative local reference.
    bridge=cq.importers.importStep(str(REPO/'excavator_60mm/step/01_chassis_bridge.step')).translate((0,-p.ex.TRACK_Y,0))
    bridge_test=checks.interference({**inst,'known_bridge':dict(shape=bridge,group='chassis')},skip=lambda a,b:'known_bridge' not in (a,b))
    report['known_bridge_clearance']=bridge_test
    wire=s.j1.motor_shapes()['reserved_terminal_and_wire_space']
    report['wire_keepout']=checks.interference({'wire':dict(shape=wire,group='reserve'),**inst},skip=lambda a,b:'wire' not in (a,b))
    # Eight-millimetre bit/shaft envelope above each installed M5 socket head.
    tools=[]
    for i,x in enumerate(s.MOUNT_X):
        driver=p.zcyl(4,86,136,x,s.MOUNT_Y)
        run=checks.interference({**context,'driver':dict(shape=driver,group='tool')},skip=lambda a,b:'driver' not in (a,b))
        tools.append(dict(x_mm=x,**run))
    report['chassis_driver_access_8mm']=tools
    # A solid swept volume proves the 10 mm foot can descend vertically to Z70.
    descent=[]
    for i,x in enumerate(s.MOUNT_X):
        swept=p.box(x-12,x+12,-66,-42,70,120).cut(p.zcyl(2.7,69,121,x,s.MOUNT_Y))
        run=checks.interference({**inst,'foot_sweep':dict(shape=swept,group='installation')},skip=lambda a,b:'foot_sweep' not in (a,b))
        descent.append(dict(x_mm=x,**run))
    report['chassis_foot_vertical_sweep']=descent
    # The spindle/cap are unchanged. Test them against the changed enclosing rail.
    rotation=[]
    rotating={n:d for n,d in inst.items() if d['group']=='drive'}
    fixed={n:d for n,d in inst.items() if n.startswith('J2') and d['group']=='frame'}
    for a in [0,15,30,45,60,90,120,150,180,210,240,270,300,330]:
        pose={n:{**d,'shape':d['shape'].rotate((s.DX,0,s.DZ),(s.DX,1,s.DZ),a)} for n,d in rotating.items()}
        run=checks.interference({**fixed,**pose},skip=lambda x,y:(x in rotating)==(y in rotating))
        rotation.append(dict(angle_deg=a,**run))
    report['drive_rotation_samples']=rotation
    # Include the installed chassis screws: J1 did not model these.
    recoil=[]
    # Use the actual stop datums. Rounded -4 mm overshoots the retained rear
    # stop by about 0.0005 mm because the exact-pitch chain offset is not -0.2.
    stop_shifts=[p.YOKE_STOP_X-(p.YOKE_X[0]+p.ex.IDLER_ASSEMBLY_OFFSET),
                 p.NOSE_BLOCK_X[0]-(p.YOKE_X[1]+p.ex.IDLER_ASSEMBLY_OFFSET)]
    for shift in stop_shifts:
        moving={n:{**d,'shape':d['shape'].translate((shift,0,0))} for n,d in inst.items() if d['group'] in ['idler','idler_slide']}
        fixed={n:d for n,d in context.items() if n.startswith('J2') or n.startswith('chassis_fixture')}
        run=checks.interference({**fixed,**moving},skip=lambda a,b:(a in moving)==(b in moving))
        recoil.append(dict(shift_mm=shift,**run))
    report['idler_travel_with_chassis_fasteners']=recoil
    removal=[]
    fixed={n:d for n,d in inst.items() if n!='J211_contoured_motor_lid' and not n.startswith('J2_lid_M3x8')}
    for shift in [.5,4,15]:
        lid=inst['J211_contoured_motor_lid']['shape'].translate((0,-shift,0))
        run=checks.interference({**fixed,'lid_removed':dict(shape=lid,group='service')},skip=lambda a,b:'lid_removed' not in (a,b))
        removal.append(dict(outward_shift_mm=shift,**run))
    report['lid_removal']=removal
    no_motor_cover={n:d for n,d in inst.items() if n!='J211_contoured_motor_lid' and not n.startswith('J2_lid_M3x8')}
    carrier_access=[]
    for i,(x,z) in enumerate(s.j1.FRAME_HOLES):
        tool=p.ycyl(2,-92,-44,x,z)
        run=checks.interference({**no_motor_cover,'driver':dict(shape=tool,group='tool')},skip=lambda a,b:'driver' not in (a,b))
        carrier_access.append(dict(hole=i,**run))
    report['carrier_bolt_access_4mm']=carrier_access
    report['clearances_mm']={
        'can_to_lid':distance(inst['JGY_can_envelope']['shape'],inst['J211_contoured_motor_lid']['shape']),
        'motor_to_enclosing_frame':distance(inst['JGY_gearbox_envelope']['shape'],inst['J206_integrated_track_frame']['shape']),
        'rear_chassis_bolt_to_can':distance(fixtures['chassis_fixture_0_bolt']['shape'],inst['JGY_can_envelope']['shape']),
        'front_chassis_bolt_to_yoke':distance(fixtures['chassis_fixture_2_bolt']['shape'],inst['TW07_idler_yoke']['shape'])}
    report['interfaces']=dict(motor_face_y_mm=-46,motor_hole_pattern_mm=[33,18],shaft_axis_xz_mm=[s.DX,s.DZ],
        chassis_pad_centres_xyz_mm=[[x,-54,70] for x in s.MOUNT_X],chassis_insert='M5, modeled OD6.8 x L5.8; supplier hole spec must be confirmed',
        example_foot_thickness_mm=10,example_washer_mm=1,example_bolt_length_mm=18,maximum_bolt_projection_below_foot_mm=7,
        actual_X_frame_CAD_available=False,original_track_dimensions_preserved=True)
    all_runs=[report,bridge_test,report['wire_keepout']]+tools+descent+rotation+recoil+removal+carrier_access
    report['pass']=report['within_original_envelope'] and all(not r['hits'] for r in all_runs)
    report['scope']='Nominal geometry and installation access on retained pads. X-frame drawing is a marked reference, not verified against an actual user chassis. No structural or powered tests.'
    return report


def save_assembly(inst,path,name):
    a=cq.Assembly(name=name)
    for n,d in inst.items():a.add(d['shape'],name=n,color=cq.Color(*d['color']))
    a.export(str(path));rt=cq.importers.importStep(str(path));assert p.one(rt).isValid()
    return len(rt.solids().vals())

"""Rebuild printable parts, purchased-hardware envelopes and complete STEP.

Every printable part is a single BREP solid. Hardware is shown separately.
Track links use pin engagement, interleaved eyes and steel pins. Dimensions mm.
"""
import json, math, gzip, sys, time
import cadquery as cq
import numpy as np
import trimesh
from design import *
from cad_common import one, mesh, move, actmove
from build_arm import structures, hardware, load_actuators, placed_parts, actuator_instances
from upper_body import upper_printed, upper_hardware, UPPER_PARTS
sys.path.insert(0,str(REPO/'track_wheel/source'))
import tw_parts as tw                      # Track wheel R5: in-hub final drive and recoil idler
from build_track_wheel import PRINT as TW_PRINT

YELLOW=(.91,.60,.07); DARK=(.13,.17,.20); STEEL=(.63,.69,.73)
RUBBER=(.19,.21,.22); GLASS=(.22,.41,.47); RED=(.68,.14,.09)

def box(x0,x1,y0,y1,z0,z1):
    return cq.Workplane('XY').box(x1-x0,y1-y0,z1-z0).translate(((x0+x1)/2,(y0+y1)/2,(z0+z1)/2))

def cyl(r,z0,z1,x=0,y=0):
    return cq.Workplane('XY').center(x,y).circle(r).extrude(z1-z0).translate((0,0,z0))

def ycyl(r,y0,y1,x=0,z=0):
    return cq.Workplane('XZ').center(x,z).circle(r).extrude(y1-y0).translate((0,y1,0))

def xcyl(r,x0,x1,y=0,z=0):
    return cq.Workplane('YZ').center(y,z).circle(r).extrude(x1-x0).translate((x0,0,0))

def xz_prism(points,y0,y1):
    return cq.Workplane('XZ').polyline(points).close().extrude(y1-y0).translate((0,y1,0))

def drill_z(s,xy,r,z0=-20,z1=400):
    for x,y in xy:s=s.cut(cyl(r,z0,z1,x,y))
    return s

def ring(r,ri,z0,z1,x=0,y=0):return cyl(r,z0,z1,x,y).cut(cyl(ri,z0-1,z1+1,x,y))

def yring(r,ri,y0,y1,x=0,z=0):return ycyl(r,y0,y1,x,z).cut(ycyl(ri,y0-1,y1+1,x,z))

def bolt_circle(r,n,phase=0):
    return [(r*math.cos(phase+2*math.pi*i/n),r*math.sin(phase+2*math.pi*i/n)) for i in range(n)]

def countersink(s,points,hole_radius,head_radius,top):
    depth=head_radius-hole_radius
    for x,y in points:s=s.cut(cq.Solid.makeCone(hole_radius,head_radius,depth,cq.Vector(x,y,top-depth),cq.Vector(0,0,1)))
    return s

def nut_pockets(s,points,across_flats,bottom,depth):
    for x,y in points:s=s.cut(cq.Workplane('XY').center(x,y).polygon(6,across_flats*2/math.sqrt(3)).extrude(depth+.01).translate((0,0,bottom-.01)))
    return s

def gear(teeth,module,width,z0,bore):
    """20 degree full-depth involute, .18 mm tooth-thickness backlash per gear.

    Root follows a short radial relief, not an unmanufacturable sharp involute
    below the base circle. Both gears have >=20 teeth: no standard undercut.
    """
    rp=module*teeth/2;rb=rp*math.cos(math.radians(20));ra=rp+module;rf=rp-1.25*module
    inv=lambda r: math.sqrt(max(0,(r/rb)**2-1))-math.acos(min(1,rb/r))
    half=math.pi/(2*teeth)-.18/(2*rp);ip=inv(rp)
    points=[]
    for k in range(teeth):
        mid=2*math.pi*k/teeth
        flank=[]
        radii=sorted(set([rf]+list(np.linspace(max(rb,rf),ra,9))))
        for r in radii:
            angle=mid-half-ip+(inv(r) if r>=rb else 0)
            flank.append((r*math.cos(angle),r*math.sin(angle)))
        points+=flank
        for r in reversed(radii):
            angle=mid+half+ip-(inv(r) if r>=rb else 0)
            points.append((r*math.cos(angle),r*math.sin(angle)))
    s=cq.Workplane('XY').polyline(points).close().extrude(width).translate((0,0,z0))
    return s.cut(cyl(bore,z0-1,z0+width+1))


def printable_parts():
    p={}
    def add(n,s,color=DARK,quantity=1,material='PETG',note=''):
        p[n]=dict(shape=s.clean(),color=color,kind='printed',quantity=quantity,material=material,note=note)
    # Central bolted bridge. All rails mount through matching M5 holes.
    chassis=box(-145,145,-110-FRAME_SHIFT,110+FRAME_SHIFT,70,80)
    chassis=chassis.cut(box(-75,75,-65,65,69,75))
    chassis=chassis.cut(cyl(33,69,81))
    for x in RETURN_ROLLERS:
        for sign in [-1,1]:
            cut=ycyl(8.5,105+FRAME_SHIFT,113+FRAME_SHIFT,x,RETURN_Z)
            chassis=chassis.cut(cut if sign==1 else cut.mirror('XZ'))
    # M5 bolts into the track-wheel frame flanges (TW06).
    chassis=drill_z(chassis,[(x,y) for x in tw.FLANGE_X for y in [-100-FRAME_SHIFT,100+FRAME_SHIFT]],2.7)
    chassis=drill_z(chassis,bolt_circle(42,4,math.pi/4),2.7)
    # The slew motor now passes through the bridge, supported by a top flange.
    chassis=chassis.cut(box(65.7,108.7,-21.5,21.5,69,81))
    chassis=drill_z(chassis,[(87.2+dx,dy) for dx in [-29,29] for dy in [-19,19]],2.2)
    stops=bolt_circle(120,1,math.radians(15))+bolt_circle(120,1,math.radians(-15))
    chassis=drill_z(chassis,stops,2.7)
    add('01_chassis_bridge',chassis)
    # Track wheel R5 (track_wheel/): in-hub gearmotor final drive, recoil idler and frame.
    for n,fn,color,qty,note in tw.PRINTED:
        add(n,fn(),color,quantity=2,material='PETG or PA (tough)' if n=='TW03_hub_cap' else 'PETG',
            note=note+(' Right-hand; the left rail is the mirror image (TW06_track_frame_left).' if n=='TW06_track_frame' else ''))
    # Track shoe: complementary eyes leave the steel sleeve exposed to the sprocket.
    # Three transverse grousers, as on the Cat 320 reference. Recess the spaces
    # between ribs so the existing ground datum and arm clearance stay valid.
    shoe=box(-9.4,9.4,-SHOE_WIDTH/2,SHOE_WIDTH/2,-6,-4)
    for x in GROUSER_CENTRES:shoe=shoe.union(box(x-1,x+1,-SHOE_WIDTH/2,SHOE_WIDTH/2,-7,-6))
    for y0,y1 in [(-21,-14),(14,21)]:
        railshoe=box(-10,10,y0,y1,-4,4).union(ycyl(4,y0,y1,-10,0))
        railshoe=railshoe.cut(ycyl(4.3,y0-1,y1+1,10,0))
        railshoe=railshoe.cut(ycyl(1.6,y0-1,y1+1,-10,0))
        shoe=shoe.union(railshoe)
    for y0,y1 in [(-13.7,-8.7),(8.7,13.7)]:
        eye=ycyl(4,y0,y1,10,0).union(box(0,10,y0,y1,-4,0))
        shoe=shoe.union(eye.cut(ycyl(1.6,y0-1,y1+1,10,0)))
    # Two tread screws accept optional replaceable TPU traction strips.
    shoe=drill_z(shoe,[(0,-5),(0,5)],1.2,-8,-3)
    add('05_track_shoe',shoe,quantity=68,note='Triple grouser, 1 mm relief; Ø3 steel pin, 3.2 mm running bores; never print the pins.')
    idler=yring(IDLER_GUIDE_R,11.1,-7,7)
    idler=idler.union(yring(14,6.2,-10,10))
    # Twin running rims support the link rails and outer flanges guide their
    # sides. The central disc clears the steel sleeves around the wrap.
    idler=idler.union(yring(28,8.2,-20,20))
    for y0,y1 in [(-20,-15),(15,20)]:idler=idler.union(yring(IDLER_RAIL_R,8.2,y0,y1))
    for sign in [-1,1]:
        y0,y1=sorted([sign*20,sign*GUIDE_OUTER_Y]);idler=idler.union(yring(IDLER_RAIL_R,8.2,y0,y1))
        y0,y1=sorted([sign*GUIDE_INNER_Y,sign*GUIDE_OUTER_Y]);idler=idler.union(yring(IDLER_RAIL_R+GUIDE_HEIGHT,8.2,y0,y1))
    idler=idler.cut(ycyl(11.1,-11,-3)).cut(ycyl(11.1,3,11))
    add('07_idler_wheel',idler,quantity=2,note='Twin rail rims, outer guide flanges and bushing clearance; two 608 bearings; non-driven 8 mm steel axle.')
    roller=yring(13,6.2,-20,20)
    for y0,y1 in [(-20,-15),(15,20)]:roller=roller.union(yring(18,8.2,y0,y1))
    for sign in [-1,1]:
        y0,y1=sorted([sign*20,sign*GUIDE_OUTER_Y]);roller=roller.union(yring(18,11.1,y0,y1))
        y0,y1=sorted([sign*GUIDE_INNER_Y,sign*GUIDE_OUTER_Y]);roller=roller.union(yring(18+GUIDE_HEIGHT,11.1,y0,y1))
    roller=roller.cut(ycyl(11.1,-24,-12.9)).cut(ycyl(11.1,12.9,24))
    add('08_road_roller',roller,quantity=6,note='Two 608 bearings; twin running surfaces and outer guide flanges, 0.6 mm lateral clearance per side.')
    # Slew housing shoulders support outer races, separate steel spacers support inner races.
    housing=ring(32,19.5,80,150)
    # Keep the load-bearing flange on the bridge while recessing the bearing tube.
    housing=housing.union(ring(52,19.5,128,136))
    housing=housing.cut(cyl(21.1,79,104)).cut(cyl(21.1,132,151))
    housing=drill_z(housing,bolt_circle(42,4,math.pi/4),2.7)
    housing=drill_z(housing,bolt_circle(27,4,math.pi/4),1.7)
    add('10_slew_bearing_housing',housing,note='2 x 6004 bearings, 40 mm centre separation; ream seats after coupon.')
    cap=ring(32,15,150,154)
    cap=drill_z(cap,bolt_circle(27,4,math.pi/4),1.7)
    add('11_slew_top_cap',cap)
    bottom=ring(32,15,76,80)
    bottom=drill_z(bottom,bolt_circle(27,4,math.pi/4),1.7)
    add('12_slew_bottom_cap',bottom)
    # 96:20 external spur gears, positive hub fasteners. Pinion uses metal clamp hub.
    large=gear(96,1.5,10,154,38)
    large=drill_z(large,bolt_circle(56,6),2.2)
    large=nut_pockets(large,bolt_circle(56,6),7.2,154,5.2)
    add('13_slew_ring_gear',large,YELLOW)
    small=gear(20,1.5,10,154,4.2)
    small=drill_z(small,bolt_circle(9,3),1.7)
    add('14_slew_pinion',small,YELLOW,note='Three M3 bolts to 4 mm steel clamp hub; 87.2 mm shaft spacing.')
    mount=box(66.2,108.2,-21,21,80,145).cut(cyl(12.7,79,146,87.2,0))
    mount=mount.cut(box(65,110,-22,0,90,146))
    mount=mount.union(box(53.2,121.2,-25,25,128,134).cut(box(66.2,108.2,-21,21,127,135)))
    mount=drill_z(mount,[(87.2+dx,dy) for dx in [-29,29] for dy in [-19,19]],2.2)
    for z in [102,132]:
        for x in [69.2,105.2]:mount=mount.cut(ycyl(2.2,-22,22,x,z))
    add('15_slew_motor_mount',mount,note='Body saddle plus steel straps, slots permit .2 mm mesh adjustment.')
    # Actual mechanical stop at the rear, in its own Z band above both gears.
    tab=box(-130,-110,-5,5,165,172)
    tab=drill_z(tab,[(-125,0),(-115,0)],2.2)
    add('17_slew_stop_tab',tab)
    # Physical fit coupons for the purchased bearings, track pin and one 18650 cell.
    coupon=box(0,140,0,50,0,10)
    coupon=drill_z(coupon,[(15,25)],11.1)
    coupon=drill_z(coupon,[(55,25)],21.1)
    coupon=drill_z(coupon,[(90,15)],4.1)
    coupon=drill_z(coupon,[(90,32)],1.6)
    coupon=drill_z(coupon,[(122,25)],GROOVE_R)
    add('22_fit_coupon',coupon,note='608 / 6004 / 8 mm axle / 3 mm pin / Ø19.7 18650 cradle groove. Print first; tune hole compensation.')
    return_roller=tw.return_roller()
    add('24_return_roller',return_roller,quantity=4,note=f'Track R5 carrier: Ø{2*RETURN_ROLLER_R:g} rims {CARRIER_LIFT:g} mm above the straight top run so it keeps carrying the sprung track; outer flanges with 0.6 mm side clearance; two 608 bearings.')
    skirt=ring(131.5,127.5,140,172)
    for x,y in SKIRT_MOUNTS:skirt=skirt.union(cyl(5,160,172,x,y))
    skirt=drill_z(skirt,SKIRT_MOUNTS,1.7,159,173)
    skirt=nut_pockets(skirt,SKIRT_MOUNTS,5.7,160,3.0)
    skirt=skirt.cut(box(-132,-109,-6,6,164.5,173))
    add('26_slew_skirt',skirt,YELLOW,note='Removable rotating cover, bottom Z92, 12 mm above bridge; M3 captive nuts. Does not carry slew loads.')
    # Existing track geometry stays at its established datum; recess only the slew/upper body.
    for n in ['10_slew_bearing_housing','11_slew_top_cap','12_slew_bottom_cap','13_slew_ring_gear','14_slew_pinion',
              '15_slew_motor_mount','17_slew_stop_tab','26_slew_skirt']:
        p[n]['shape']=p[n]['shape'].translate((0,0,-SLEW_DROP))
    # R3 upper body is built directly in final coordinates.
    for n,d in upper_printed().items():p[n]=d
    return p


TW_FROM_R4=('07_idler_wheel','08_road_roller','24_return_roller','idler_608','axle_roller','axle_return',
            'collar_roller','collar_return','spacer_roller','spacer_return','608_roller','608_return')
TW_GROUPS=dict(frame='chassis',adjuster='chassis',drive='drive',pinion='drive_pinion',idler_slide='idler_slide',spring='idler_spring')


def vehicle_instances(parts):
    """Global Z up. Groups identify real rigid bodies for preview and validation."""
    out={}
    tw_unit=tw.unit_instances(parts,with_chain=False)
    def add(n,s,g='chassis',color=DARK,kind='hardware',source=None,final=False):
        if not final and kind!='printed' and (g in ['upper','slew_pinion'] or n.startswith('slew_')):
            s=s.translate((0,0,-SLEW_DROP))
        out[n]=dict(shape=s,group=g,color=color,kind=kind,source=source)
    def part(n,g='chassis',suffix='',transform=None):
        d=parts[n];s=d['shape'] if transform is None else transform(d['shape'])
        add(n+suffix,s,g,d['color'],'printed',n)
    for n in ['01_chassis_bridge','10_slew_bearing_housing','11_slew_top_cap','12_slew_bottom_cap','15_slew_motor_mount']:part(n)
    for n in ['13_slew_ring_gear','17_slew_stop_tab','26_slew_skirt']+[n for n in parts if n in UPPER_PARTS]:part(n,'upper')
    part('28_operator_console','upper','_inboard',lambda s:s.translate((0,-50*CAB_SIDE,0)))
    part('14_slew_pinion','slew_pinion',transform=lambda s:s.rotate((0,0,0),(0,0,1),9).translate((87.2,0,0)))
    for side,sgn in [('R',1),('L',-1)]:
        mirror=lambda s:s if sgn==1 else s.mirror('XZ')
        frame=lambda s:mirror(s.translate((0,FRAME_SHIFT,0)))
        outer=lambda s:mirror(s.translate((0,TRACK_SHIFT,0)))
        # Track wheel R5 unit: frame, final drive, pinion, idler slide, recoil spring.
        for n,d in tw_unit.items():
            if n.startswith(TW_FROM_R4):continue
            shape=d.get('envelope',d['shape']).translate((0,TRACK_Y,0))
            name=('recoil_spring_envelope' if n=='recoil_spring' else n)+'_'+side
            add(name,mirror(shape),TW_GROUPS[d['group']]+('_'+side if TW_GROUPS[d['group']]!='chassis' else ''),
                d['color'],'printed' if d['kind']=='printed' else 'hardware',d['source'])
        def wheel(s,x,z):return s.translate((x,sgn*TRACK_Y,z))
        part('07_idler_wheel','idler_'+side,'_'+side,lambda s:wheel(s,110,AXLE_Z))
        for j,x in enumerate(ROAD_ROLLERS):part('08_road_roller','roller_'+side+str(j),'_'+side+str(j),lambda s,x=x:wheel(s,x,29))
        for j,x in enumerate(RETURN_ROLLERS):part('24_return_roller','return_'+side+str(j),'_'+side+str(j),lambda s,x=x:wheel(s,x,RETURN_Z))
        for i,origin,a in track_poses():
            s=move(parts['05_track_shoe']['shape'],origin,a).translate((0,sgn*TRACK_Y,0))
            add('shoe_'+side+f'{i:02}',s,'track_'+side,RUBBER,'printed','05_track_shoe')
        for i,(x,z) in enumerate(track_pins()):
            add('track_bushing_'+side+f'{i:02}',yring(BUSH_R,1.55,sgn*TRACK_Y-BUSH_LENGTH/2,sgn*TRACK_Y+BUSH_LENGTH/2,x,z),'track_'+side,STEEL)
            add('track_pin_'+side+f'{i:02}',ycyl(1.5,sgn*TRACK_Y-PIN_LENGTH/2,sgn*TRACK_Y+PIN_LENGTH/2,x,z),'track_'+side,STEEL)
            for k,dy in enumerate([-PIN_CLIP_Y,PIN_CLIP_Y]):add('pin_clip_'+side+f'{i:02}_{k}',yring(3,1.5,sgn*TRACK_Y+dy-.3,sgn*TRACK_Y+dy+.3,x,z),'track_'+side,STEEL)
        for j,(x,z) in enumerate([(110,AXLE_Z)]+[(v,29) for v in ROAD_ROLLERS]+[(v,RETURN_Z) for v in RETURN_ROLLERS]):
            wheelgroup='idler_'+side if j==0 else 'roller_'+side+str(j-1) if j<4 else 'return_'+side+str(j-4)
            bands=[(-10,-3),(3,10)] if j==0 else [(-20,-13),(13,20)]
            for k,(a,b) in enumerate(bands):add('wheel_608_'+side+str(j)+str(k),yring(11,4,sgn*TRACK_Y+a,sgn*TRACK_Y+b,x,z),wheelgroup,STEEL)
            if j==0:continue                     # the idler axle set belongs to the track-wheel yoke
            add('free_axle_'+side+str(j),mirror(ycyl(4,101+FRAME_SHIFT,176+TRACK_SHIFT,x,z)),color=STEEL)
            for k,(a,b) in enumerate([(101+FRAME_SHIFT,106+FRAME_SHIFT) if j==0 else (107+FRAME_SHIFT,112+FRAME_SHIFT),(171+TRACK_SHIFT,176+TRACK_SHIFT)]):
                add('axle_collar_'+side+str(j)+str(k),mirror(yring(8,4.05,a,b,x,z)),color=STEEL)
            for k,(a,b) in enumerate([(124+FRAME_SHIFT,140+TRACK_SHIFT),(147+TRACK_SHIFT,153+TRACK_SHIFT),(160+TRACK_SHIFT,171+TRACK_SHIFT)] if j==0 else [(124+FRAME_SHIFT,130+TRACK_SHIFT),(137+TRACK_SHIFT,163+TRACK_SHIFT),(170+TRACK_SHIFT,171+TRACK_SHIFT)]):
                add('axle_spacer_'+side+str(j)+str(k),mirror(yring(6,4.05,a,b,x,z)),color=STEEL)
    for j,z in enumerate([92,132]):add('slew_6004_'+str(j),ring(21,10,z,z+12),color=STEEL)
    add('slew_outer_spacer_bottom',ring(21,17.5,80,92),color=STEEL)
    add('slew_outer_spacer_top',ring(21,17.5,144,150),color=STEEL)
    add('slew_spindle',cyl(10,82,172),'upper',STEEL)
    add('slew_inner_spacer',ring(13,10.05,104,132),'upper',STEEL)
    add('slew_top_spacer',ring(14,10.05,144,162),'upper',STEEL)
    add('slew_lower_collar',ring(15,10.05,82,92),'upper',STEEL)
    flange=ring(35,10.05,162,172)
    flange=drill_z(flange,bolt_circle(25,4,math.pi/4),2.1) # M5 tapped metal flange; minor diameter shown.
    flange=drill_z(flange,[(-10,25)],4)
    add('slew_clamp_flange',flange,'upper',STEEL)
    for j,(x,y) in enumerate(bolt_circle(56,6)):add('gear_standoff_'+str(j),ring(5,2.2,164,172,x,y),'upper',STEEL)
    add('slew_motor',cyl(12.5,94,145,87.2,0),color=STEEL)
    add('slew_motor_shaft',cyl(2,145,164,87.2,0),'slew_pinion',STEEL)
    pinion_hub=ring(12,2.05,147,154,87.2,0)
    pinion_hub=drill_z(pinion_hub,[(x+87.2,y) for x,y in bolt_circle(9,3,math.radians(9))],1.25)
    add('slew_pinion_clamp_hub',pinion_hub,'slew_pinion',STEEL)
    for j,a in enumerate([-15,15]):
        x,y=bolt_circle(120,1,math.radians(a))[0]
        add('slew_stop_post_'+str(j),cyl(4,128,172,x,y),color=STEEL)
    # R3 upper-body hardware and glazing are defined in final coordinates.
    for n,(shape,color,kind) in upper_hardware().items():add(n,shape,'upper',color,kind,final=True)
    # Exact-pitch assembly with raised end wheels needs 0.2005 mm idler take-up.
    for side in ['L','R']:
        for n,d in out.items():
            # Track-wheel parts arrive in the assembly pose already.
            moving=(n=='07_idler_wheel_'+side or n.startswith('wheel_608_'+side+'0'))
            if moving:d['shape']=d['shape'].translate((IDLER_ASSEMBLY_OFFSET,0,0))
    return out


def full_arm(strokes=None):
    parts=structures();parts.update(hardware());acts=load_actuators()
    placed=placed_parts(parts,acts,strokes)
    return {n:dict(shape=s.translate(tuple(ARM_OFFSET)),group='arm',color=parts[n]['color'] if n in parts else STEEL,kind=parts[n]['kind'] if n in parts else 'actuator') for n,s in placed.items()}


def track_link_components(parts):
    """One rigid link assembly in its local frame; its front hinge owns the pin."""
    steel=7.85e-6
    items=[(parts['05_track_shoe']['shape'],PETG_KG_MM3),
        (ycyl(1.5,-PIN_LENGTH/2,PIN_LENGTH/2,10,0),steel),
        (yring(BUSH_R,1.55,-BUSH_LENGTH/2,BUSH_LENGTH/2,10,0),steel)]
    for y in [-PIN_CLIP_Y,PIN_CLIP_Y]:items.append((yring(3,1.5,y-.3,y+.3,10,0),steel))
    return items


def track_link_shape(parts):
    return cq.Workplane(obj=cq.Compound.makeCompound([one(s) for s,_ in track_link_components(parts)]))


def export_track_inertias(parts,instances):
    """CAD-derived rigid-body masses, centres and tensors in kg, m and kg m².

    608 bearings use their declared 12 g procurement mass and the hub bearings
    their catalogue mass; the whole bearing ring rotates in this approximation.
    The reflected gearmotor inertia is added in simulate_track.py.
    """
    def combine(items):
        masses=[];centres=[];tensors=[]
        for shape,density in items:
            solid=one(shape);m=solid.Volume()*density;c=solid.Center()
            masses.append(m);centres.append(np.array([c.x,c.y,c.z]))
            tensors.append(np.array(cq.Shape.matrixOfInertia(solid))*density)
        total=sum(masses);centre=sum(m*c for m,c in zip(masses,centres))/total
        tensor=np.zeros((3,3))
        for m,c,inertia in zip(masses,centres,tensors):
            d=c-centre;tensor+=inertia+m*(np.dot(d,d)*np.eye(3)-np.outer(d,d))
        tensor*=1e-6
        return dict(mass_kg=total,centre_m=(centre*.001).tolist(),
            fullinertia_kg_m2=[float(tensor[i,j]) for i,j in [(0,0),(1,1),(2,2),(0,1),(0,2),(1,2)]])
    result={'shoe':combine(track_link_components(parts))}
    groups=[('drive','drive_R',(-110,TRACK_Y,AXLE_Z)),('idler','idler_R',(110+IDLER_ASSEMBLY_OFFSET,TRACK_Y,AXLE_Z)),
            ('idler_slide','idler_slide_R',(110+IDLER_ASSEMBLY_OFFSET,TRACK_Y,AXLE_Z))]
    groups += [('roller'+str(i),'roller_R'+str(i),(x,TRACK_Y,29)) for i,x in enumerate(ROAD_ROLLERS)]
    groups += [('roller'+str(i+3),'return_R'+str(i),(x,TRACK_Y,RETURN_Z)) for i,x in enumerate(RETURN_ROLLERS)]
    for name,group,origin in groups:
        items=[]
        for n,d in instances.items():
            if d['group']!=group:continue
            shape=d['shape'].translate(tuple(-v for v in origin))
            density=(PETG_KG_MM3 if d['kind']=='printed' else .012/one(shape).Volume() if '608' in n else
                     tw.BEARINGS['inboard']['mass_kg']/one(shape).Volume() if n.startswith('bearing_6809-2RS_outer') else
                     tw.BEARINGS['outboard']['mass_kg']/one(shape).Volume() if n.startswith('bearing_61808-2RS1_outer') else
                     8.5e-6 if 'insert' in n else 7.85e-6)
            items.append((shape,density))
        result[name]=combine(items)
    (ROOT/'source/track_mass_properties.json').write_text(json.dumps(result,indent=2)+'\n')


def export_all():
    start=time.time();p=printable_parts();report=[]
    for n,d in p.items():
        s=d['shape'];assert one(s).isValid() and len(s.solids().vals())==1,(n,len(s.solids().vals()))
        print('Export',n,flush=True)
        cq.exporters.export(s,str(ROOT/'step'/f'{n}.step'))
        printable=s
        if n in ['07_idler_wheel','08_road_roller','24_return_roller']:
            printable=s.rotate((0,0,0),(1,0,0),90)
        if n in TW_PRINT and TW_PRINT[n][1]:printable=s.rotate((0,0,0),TW_PRINT[n][0],TW_PRINT[n][1])
        if n in ['01_chassis_bridge'] or d.get('orient')=='flip':printable=s.rotate((0,0,0),(1,0,0),180)
        b=one(printable).BoundingBox();printable=printable.translate((-(b.xmin+b.xmax)/2,-(b.ymin+b.ymax)/2,-b.zmin))
        target=ROOT/'stl'/f'{n}.stl';cq.exporters.export(printable,str(target),tolerance=.035,angularTolerance=.12)
        tm=trimesh.load_mesh(target);tm.update_faces(tm.nondegenerate_faces(height=1e-8));tm.remove_unreferenced_vertices();tm.export(target)
        assert tm.is_watertight and tm.is_winding_consistent and len(tm.split())==1,n
        rt=cq.importers.importStep(str(ROOT/'step'/f'{n}.step'));assert one(rt).isValid() and len(rt.solids().vals())==1,n
        row=dict(name=n,quantity=d['quantity'],material=d['material'],note=d['note'],volume_mm3=one(s).Volume(),bounds_mm=tm.extents.tolist(),watertight=True,step_roundtrip=True)
        if n=='TW06_track_frame':
            mirror_cad=s.mirror('XZ').rotate((0,0,0),(1,0,0),90)
            mb=one(mirror_cad).BoundingBox();mirror_cad=mirror_cad.translate((-(mb.xmin+mb.xmax)/2,-(mb.ymin+mb.ymax)/2,-mb.zmin))
            mirror_path=ROOT/'stl'/f'{n}_left.stl';cq.exporters.export(mirror_cad,str(mirror_path),tolerance=.035,angularTolerance=.12)
            mirrored=trimesh.load_mesh(mirror_path)
            mirrored.update_faces(mirrored.nondegenerate_faces(height=1e-8));mirrored.remove_unreferenced_vertices();mirrored.export(mirror_path)
            assert mirrored.is_watertight and mirrored.is_winding_consistent and len(mirrored.split())==1
            cq.exporters.export(s.mirror('XZ'),str(ROOT/'step'/f'{n}_left.step'))
            mirror_rt=cq.importers.importStep(str(ROOT/'step'/f'{n}_left.step'));assert one(mirror_rt).isValid() and len(mirror_rt.solids().vals())==1
            row['mirrored_stl']=f'{n}_left.stl'
        report.append(row)
    instances=vehicle_instances(p);export_track_inertias(p,instances);items=[]
    from export_glazing import export_glazing
    export_glazing(instances)
    for n,d in instances.items():
        assert one(d['shape']).isValid(),n
        items.append(dict(name=n,**{k:v for k,v in d.items() if k!='shape'},**mesh(d['shape'])))
    (ROOT/'source/vehicle_scene.json.gz').write_bytes(gzip.compress(json.dumps(items,separators=(',',':')).encode()))
    # Reuse checked arm60 local meshes to retain all articulation in the viewer.
    assy=cq.Assembly(name='Tracked_excavator_arm60_R3')
    for n,d in {**instances,**{'arm_'+n:v for n,v in full_arm().items()}}.items():assy.add(d['shape'],name=n,color=cq.Color(*d['color']))
    assy.export(str(ROOT/'step/excavator_complete.step'))
    rt=cq.importers.importStep(str(ROOT/'step/excavator_complete.step'));assert one(rt).isValid()
    (ROOT/'parameters.json').write_text(json.dumps(config(),indent=2))
    (ROOT/'source/export_report.json').write_text(json.dumps(dict(parts=report,assembly_solids=len(rt.solids().vals()),elapsed_seconds=time.time()-start),indent=2))
    print('Complete assembly',len(rt.solids().vals()),'solids;',round(time.time()-start,1),'s',flush=True)

if __name__=='__main__':export_all()

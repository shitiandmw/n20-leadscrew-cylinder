"""CAD clearances, gear mesh, actual CAD mass properties and quasistatic loads.

The collision reference envelope is a sampled CAD subset, not a motion limit.
The preview allows full independent travel; operators manage track clearance.
Motor/printed-material capabilities are requirements until measured on hardware.
"""
import argparse,hashlib,itertools,json,math,time
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from build_vehicle import *
from check_intersections import intersections


def in_collision_reference_envelope(strokes,slew_deg):
    """Retain the original CAD sample region for comparable clearance results."""
    return strokes[0]>=15 or abs(slew_deg)<=20


def hardware_mass(n,s):
    if n.startswith('gearmotor_gearbox_'):return tw.GEARMOTOR['mass_kg']      # whole Pololu 37D gearmotor
    if n.startswith(('gearmotor_motor_','bearing_6809-2RS_inner','bearing_6809-2RS_seals','bearing_61808-2RS1_inner','bearing_61808-2RS1_seals')):return 0.
    if n.startswith('bearing_6809-2RS_outer'):return tw.BEARINGS['inboard']['mass_kg']
    if n.startswith('bearing_61808-2RS1_outer'):return tw.BEARINGS['outboard']['mass_kg']
    if 'insert' in n:return one(s).Volume()*8.5e-6
    if n.startswith('recoil_spring_envelope'):
        S=tw.SPRING;return math.pi*(S['wire']/2)**2*math.pi*(S['od']-S['wire'])*S['coils']*7.85e-6
    if n=='slew_motor':return .090
    if n.startswith('battery_18650_'):return .048
    if n in ['battery_end_pad','battery_top_pad','battery_separator']:return .001
    if n=='ballast_rubber_pad':return .002
    if n.startswith('nickel_strip_'):return one(s).Volume()*8.9e-6
    if n.startswith('electronics_support_'):return .001
    if n.startswith('electronics_'):return {'electronics_BMS':.012,'electronics_6V_buckboost':.025,'electronics_12V_boost':.035}[n]
    if n.startswith('cab_glazing_'):return one(s).Volume()*1.38e-6
    if '6004' in n:return .070
    if '608' in n:return .012
    return one(s).Volume()*7.85e-6


def mass_model(parts,vehicle):
    data=[]
    for n,d in vehicle.items():
        m=one(d['shape']).Volume()*PETG_KG_MM3 if d['kind']=='printed' else hardware_mass(n,d['shape'])
        c=one(d['shape']).Center();data.append(dict(name=n,mass_kg=m,centre_mm=[c.x,c.y,c.z],upper=d['group']=='upper'))
    arm_parts=structures();arm_parts.update(hardware());acts=load_actuators();am=[]
    for n,d in arm_parts.items():
        s=one(d['shape']);c=s.Center()
        am.append(dict(name=n,mass_kg=s.Volume()*(PETG_KG_MM3 if d['kind']=='printed' else 7.85e-6),centre_mm=np.array([c.x,c.y,c.z]),group=d['group']))
    for label,role,i,a,b,cy in actuator_instances():
        for n,s in acts[role].items():
            c=one(s).Center();am.append(dict(name=label+'_'+n,mass_kg=one(s).Volume()*PETG_KG_MM3,centre_mm=np.array([c.x,c.y,c.z]),group='act',index=i,a=a,b=b,y=cy,moving=n.startswith(('04','05'))))
        am.append(dict(name=label+'_motor_and_internal_hardware',mass_kg=.035,centre_mm=np.array([0.,0.,-10.]),group='act',index=i,a=a,b=b,y=cy,moving=False))
    return data,am,arm_parts,acts


def arm_centres(am,strokes):
    st=arm.solve(strokes);points=[]
    for d in am:
        c=d['centre_mm'].copy()
        if d['group']=='act':
            a,b=st['points'][d['a']],st['points'][d['b']];ang=math.atan2(*(b-a)[::-1])
            c[2]+=37.5+(strokes[d['index']] if d['moving'] else 0)
            # Local +Z is the actuator axis, +X the in-plane transverse axis.
            c[[0,2]]=a+np.array([c[2]*math.cos(ang)+c[0]*math.sin(ang),c[2]*math.sin(ang)-c[0]*math.cos(ang)])
            c[1]+=d['y']
        else:
            c[[0,2]]=st['origins'][d['group']]+arm.rot(st['angles'][d['group']])@c[[0,2]]
        points.append(c+ARM_OFFSET)
    return np.array(points)


def mass_and_loads(data,am):
    base=[d for d in data if not d['upper']];upper=[d for d in data if d['upper']]
    mb=sum(d['mass_kg'] for d in base);mu=sum(d['mass_kg'] for d in upper);ma=sum(d['mass_kg'] for d in am)
    bm=sum(d['mass_kg']*np.array(d['centre_mm']) for d in base);um=sum(d['mass_kg']*np.array(d['centre_mm']) for d in upper)
    masses=np.array([d['mass_kg'] for d in am]);cases=[];worst=None;maxmoment=0;maxcgz=0
    # 9^3 independent strokes, 13 slew angles, payload study and adverse 5° slope.
    for st in itertools.product(np.linspace(0,60,9),repeat=3):
        centres=arm_centres(am,st);s=arm.solve(st);tip=np.array([s['points']['T'][0],0,s['points']['T'][1]])+ARM_OFFSET
        # Raised arm/heavier print sensitivity: 20% arm mass, 10% less base mass.
        for payload in [0,.15]:
            total=.9*mb+mu+1.2*ma+payload
            moving=um+1.2*(centres*masses[:,None]).sum(axis=0)+payload*tip
            for yaw in np.radians(np.linspace(-150,150,13)):
                r=np.array([[math.cos(yaw),-math.sin(yaw)],[math.sin(yaw),math.cos(yaw)]])
                mm=moving.copy();mm[:2]=r@mm[:2];cg=(.9*bm+mm)/total
                # Gravity line on a 5° slope in the least favourable direction.
                margins=np.array([GROUND_HALF_LENGTH-abs(cg[0]),TRACK_Y+SHOE_WIDTH/2-abs(cg[1])])-cg[2]*math.tan(math.radians(5))
                margin=float(margins.min());maxcgz=max(maxcgz,cg[2])
                moment=float(np.linalg.norm(moving[:2])*.001*9.81);maxmoment=max(maxmoment,moment)
                if worst is None or margin<worst['margin_mm']:
                    worst=dict(margin_mm=margin,strokes_mm=list(st),slew_deg=math.degrees(yaw),payload_kg=payload,cg_mm=cg.tolist(),tooth_height_mm=tip[2])
        cases.append((st,centres,tip))
    # Static actuator thrust by virtual work, including each linkage mass.
    forces=np.zeros(3);maxpose=[None]*3
    for st,_,tip in cases:
        for j in range(3):
            plus=list(st);minus=list(st);plus[j]+=.001;minus[j]-=.001
            def potential(q):
                z=arm_centres(am,q)[:,2]*.001
                tipz=(arm.solve(q)['points']['T'][1]+ARM_OFFSET[2])*.001
                return 9.81*(np.dot(masses*1.2,z)+.15*tipz)
            force=abs((potential(plus)-potential(minus))/.000002)/(2 if j==0 else 1)
            if force>forces[j]:forces[j]=force;maxpose[j]=list(st)
    nominal=mb+mu+ma+.15
    r=PITCH_R*.001;mu_ground=.30;crr=.04;slope=math.radians(10)
    force_grade=nominal*9.81*(math.sin(slope)+crr*math.cos(slope))
    torque_grade=force_grade*r/2/.85
    # Coulomb lateral scrub on a uniformly loaded rectangular ground patch.
    torque_turn=(.45*nominal*9.81*(2*GROUND_HALF_LENGTH*.001)/(4*(2*TRACK_Y*.001))+crr*nominal*9.81/2)*r/.85
    traction_margin=mu_ground*nominal*9.81*math.cos(slope)/force_grade
    radial=maxmoment/.04
    # Net 20 mm shaft section, bore-free; slow operation so quasi-static bending.
    shaft_mpa=32*maxmoment/(math.pi*.020**3)/1e6
    ring_torque=.35*(96/20)*.75
    gear_stress=(ring_torque/.072)/(10*1.5*.32)
    # Sprocket pull at the 1.0 A driver limit (track_wheel/): torque already includes the hub-stage loss.
    drive_force=tw.drive_force_limit()['chain_pull_N']
    # Tight strand with the idler on its recoil stop (half the stop force) plus the pull;
    # one pin takes the whole load across a 17.4 mm gap.
    pin_force=drive_force+tw.stop_state(tw.ADJUST_RANGE[1])['force']/2
    pin_moment=pin_force*.0174/4
    pin_stress=32*pin_moment/(math.pi*.003**3)/1e6
    return dict(nominal_mass_kg=mb+mu+ma,base_mass_kg=mb,upper_without_arm_kg=mu,arm_mass_kg=ma,
        nominal_payload_study_kg=.15,stability_configurations=729*13*2,
        support_half_extents_mm=[GROUND_HALF_LENGTH,TRACK_Y+SHOE_WIDTH/2],uncertainty=dict(arm_mass_factor=1.2,base_mass_factor=.9,slope_deg=5),
        worst_stability=worst,max_overturning_moment_Nm=maxmoment,
        slew_bearing_couple_reaction_N=radial,slew_spindle_bending_MPa=shaft_mpa,
        static_actuator_thrust_N_per_cylinder=forces.tolist(),actuator_force_worst_strokes_mm=maxpose,
        actuator_selection_thrust_N_with_2x_margin=(2*forces).tolist(),
        drive=dict(mass_including_payload_kg=nominal,grade_deg=10,friction_coefficient=.3,rolling_coefficient=crr,
            grade_torque_Nm_each=torque_grade,skid_turn_torque_Nm_each=torque_turn,
            required_continuous_motor_torque_Nm=1.2,traction_margin=traction_margin,
            torque_at_current_limit_Nm=tw.drive_force_limit()['torque_Nm'],
            gearmotor_continuous_rating_Nm=tw.drive_rating()['sprocket_continuous_Nm'],
            no_load_speed_m_s=r*tw.drive_rating()['sprocket_no_load_rad_s'],torque_limit_tractive_force_N=drive_force),
        slew=dict(available_output_torque_Nm=ring_torque,output_rpm=10*20/96,
            conservative_Lewis_tooth_stress_MPa=gear_stress,assumed_printed_tooth_allowable_MPa=8),
        track_pin=dict(worst_force_with_pretension_N=pin_force,bending_MPa=pin_stress,assumed_steel_yield_MPa=400,material='silver steel'),
        assumptions='PETG at 1.27 g/cm³ on exact solid volume; steel 7.85; PET glazing 1.38. Drive gearmotors 195 g each (Pololu 37D 150:1, in the sprocket hubs), slew motor 90 g, hub bearings 42/32 g, two 18650 cells 48 g each (Panasonic NCR18650B maximum 48.5 g) plus pads and nickel strip, BMS/converters 72 g, bearings 12/70 g, U60 internals 35 g each. '+f'{BALLAST_KG:.3f}'+' kg steel ballast plate inside the counterweight. Mass, friction, gearbox thrust and printed strength must be measured. No soil digging load or dynamic arm load included in actuator thrust.')


def check_motion(parts,vehicle,arm_parts,acts):
    upper={n:d for n,d in vehicle.items() if d['group']=='upper'}
    fixed={n:d for n,d in vehicle.items() if d['group'] not in ['upper','slew_pinion']}
    # Compare to broad-phase fused compounds, then exact BREP where boxes overlap.
    def compound(items):return cq.Workplane(obj=cq.Compound.makeCompound([one(d['shape']) for d in items.values()]))
    up=compound(upper);fix=compound(fixed)
    collisions=[];checks=0;maxoverlap=0
    cache={};bounds_cache={}
    obstacle_bounds={n:one(d['shape']).BoundingBox() for n,d in {**upper,**fixed}.items()}
    def exact(shape,n,obstacle,e,key):
        nonlocal checks,maxoverlap
        bound_key=(n,*key)
        if bound_key not in bounds_cache:bounds_cache[bound_key]=one(shape).BoundingBox()
        a,b=bounds_cache[bound_key],obstacle_bounds[obstacle]
        if any(getattr(a,k+'max')<=getattr(b,k+'min')+1e-5 or getattr(b,k+'max')<=getattr(a,k+'min')+1e-5 for k in 'xyz'):return 0
        cache_key=(n,obstacle,*key)
        if cache_key not in cache:
            cache[cache_key]=sum(v.Volume() for v in shape.intersect(e['shape']).solids().vals());checks+=1
        vol=cache[cache_key];maxoverlap=max(maxoverlap,vol);return vol
    # Cross-system clearance; original intra-arm validation is retained separately.
    for i,st in enumerate(itertools.product([0,15,30,45,60],repeat=3)):
        ap=placed_parts(arm_parts,acts,st)
        for n,s in ap.items():
            shape=s.translate(tuple(ARM_OFFSET));bb=one(shape).BoundingBox()
            # The same rigid pose recurs for many independent actuator combinations.
            key=tuple(round(getattr(bb,a+b),6) for a in 'xyz' for b in ['min','max'])
            for obstacle,e in upper.items():
                vol=exact(shape,n,obstacle,e,key)
                if vol>.05:collisions.append(dict(part=n,obstacle=obstacle,strokes=st,volume_mm3=vol))
            if bb.zmin<DECK_Z-10:
                for yaw in [-150,-120,-90,-60,-20,0,20,60,90,120,150]:
                    if not in_collision_reference_envelope(st,yaw):continue
                    rotated=shape.rotate((0,0,0),(0,0,1),yaw)
                    for obstacle,e in fixed.items():
                        vol=exact(rotated,n,obstacle,e,(*key,yaw))
                        if vol>.05:collisions.append(dict(part=n,obstacle=obstacle,strokes=st,slew=yaw,volume_mm3=vol))
        if i%25==0:print('Arm/chassis pose',i,'checks',checks,'hits',len(collisions),flush=True)
    # Upper body sweeps through all allowed yaw; pinion has the inverse gear ratio.
    for yaw in np.linspace(-150,150,61):
        for n,d in upper.items():
            moving=d['shape'].rotate((0,0,0),(0,0,1),float(yaw))
            for obstacle,e in fixed.items():
                vol=exact(moving,n,obstacle,e,(float(yaw),))
                if vol>.05:collisions.append(dict(part=n,obstacle=obstacle,slew=float(yaw),volume_mm3=vol))
    # Full repeat cycle, one large-gear tooth. Includes minimum backlash geometry.
    big=parts['13_slew_ring_gear']['shape'];small=parts['14_slew_pinion']['shape'];gear_vol=[]
    for a in np.linspace(0,360/96,61):
        large=big.rotate((0,0,0),(0,0,1),float(a))
        little=small.rotate((0,0,0),(0,0,1),9-float(a)*96/20).translate((87.2,0,0))
        v=sum(s.Volume() for s in large.intersect(little).solids().vals());gear_vol.append(v)
    # Guide travel is checked without the chain: the extreme positions are for
    # assembly/tolerance take-up, not a command to stretch the closed track.
    idler_hits=[]
    for side in ['R','L']:
        # The track-wheel yoke, axle set and idler wheel slide together; the spring is checked in track_wheel/.
        moving={n:d for n,d in vehicle.items() if n=='07_idler_wheel_'+side or n.startswith('wheel_608_'+side+'0') or d['group']=='idler_slide_'+side}
        obstacles={n:d for n,d in fixed.items() if n not in moving and not n.startswith(('shoe_','track_pin_','track_bushing_','pin_clip_','recoil_spring_envelope_'))}
        for dx in [tw.YOKE_STOP_X-tw.YOKE_X[0],0,tw.FORWARD_TRAVEL]:
            for n,d in moving.items():
                s=d['shape'].translate((dx-IDLER_ASSEMBLY_OFFSET,0,0))
                for obstacle,e in obstacles.items():
                    vol=exact(s,'idler_move_'+n,obstacle,e,(dx,))
                    if vol>.05:idler_hits.append(dict(part=n,obstacle=obstacle,offset=dx,volume_mm3=vol))
    # Verify that physical stops act outside the working range in both directions.
    tab=parts['17_slew_stop_tab']['shape'];posts={n:d for n,d in fixed.items() if n.startswith('slew_stop_post')};stop_angles=[]
    for sign in [-1,1]:
        for angle in np.arange(150,171,.25):
            if any(sum(s.Volume() for s in tab.rotate((0,0,0),(0,0,1),sign*float(angle)).intersect(d['shape']).solids().vals())>.01 for d in posts.values()):
                stop_angles.append(sign*float(angle));break
    # Retain reference-region samples and the known collision outside that region.
    boundary_hits=[];boundary_checks=0
    for boom in [0,7.5,14.9,15.0,15.1]:
        print('Collision reference boundary boom',boom,flush=True)
        for stick in [45,52.5,60]:
            for curl in [0,7.5,15,30,45,60]:
                st=[boom,stick,curl]
                shape=placed_parts(arm_parts,acts,st)['06_inward_digging_bucket'].translate(tuple(ARM_OFFSET))
                for yaw in ([-20,-10,0,10,20] if boom<15 else [-150,-120,-90,-60,-20,0,20,60,90,120,150]):
                    rotated=shape.rotate((0,0,0),(0,0,1),yaw);boundary_checks+=1
                    for obstacle,e in fixed.items():
                        vol=exact(rotated,'guard_bucket',obstacle,e,(*st,yaw))
                        if vol>.05:boundary_hits.append(dict(strokes=st,slew=yaw,obstacle=obstacle,volume_mm3=vol))
    negative=placed_parts(arm_parts,acts,[0,60,0])['06_inward_digging_bucket'].translate(tuple(ARM_OFFSET)).rotate((0,0,0),(0,0,1),120)
    negative_volume=sum(exact(negative,'guard_negative',n,d,(120,)) for n,d in fixed.items())
    reference=dict(boom_threshold_mm=15,low_boom_slew_deg=20,boundary_configurations=boundary_checks,
        boundary_collisions=boundary_hits,negative_control_collision_mm3=negative_volume,
        negative_control_outside_reference_envelope=not in_collision_reference_envelope([0,60,0],120),negative_control_strokes_mm=[0,60,0],negative_control_slew_deg=120,
        description='CAD reference samples use boom stroke >=15 mm or slew within ±20°. This is not an operating restriction. The preview permits full 0–60 mm stroke and ±150° slew independently; operators manage track clearance.')
    return dict(arm_grid_configurations=125,arm_chassis_slew_angles=11,upper_slew_samples=61,
        exact_cross_system_intersections=checks,maximum_intersection_mm3=maxoverlap,
        collisions=collisions,gear_mesh_samples=61,maximum_gear_intersection_mm3=max(gear_vol),
        idler_guide_collisions=idler_hits,mechanical_stop_contact_deg=stop_angles,collision_reference_envelope=reference)


def stage(name,compute):
    """Cache an expensive check against the exported CAD scene.

    The full check is too long for one ten-minute run; --stage assembly and
    --stage motion can be run first. A rebuilt scene invalidates the cache.
    """
    path=ROOT/f'simulation/validation_stage_{name}.json'
    scene=hashlib.sha256((ROOT/'source/vehicle_scene.json.gz').read_bytes()).hexdigest()
    if path.exists():
        cached=json.loads(path.read_text())
        if cached['scene_sha256']==scene:
            print('Using cached',name,'check',flush=True);return cached['result']
    t0=time.time();result=compute()
    path.write_text(json.dumps(dict(scene_sha256=scene,seconds=round(time.time()-t0,1),result=result),indent=2))
    return json.loads(path.read_text())['result']


def check(only=None):
    start=time.time();p=printable_parts();v=vehicle_instances(p)
    hits,n=stage('assembly',lambda:intersections(v))
    if only=='assembly':return True
    data,am,ap,acts=mass_model(p,v)
    if only=='motion':
        stage('motion',lambda:check_motion(p,v,ap,acts));return True
    print('Mass and load sweep',flush=True);loads=mass_and_loads(data,am)
    print(json.dumps(loads,indent=2),flush=True)
    motion=stage('motion',lambda:check_motion(p,v,ap,acts))
    pins=track_pins();pitch_errors=np.linalg.norm(np.roll(pins,-1,axis=0)-pins,axis=1)-PITCH
    # Adjacent shoe articulation outside the reference pose, around a common pin.
    shoe=p['05_track_shoe']['shape'];art=[]
    for a in np.linspace(-32,8,41):
        other=shoe.translate((-20,0,0)).rotate((-10,0,0),(-10,1,0),-float(a))
        art.append(sum(s.Volume() for s in shoe.intersect(other).solids().vals()))
    upper=[one(d['shape']).BoundingBox() for d in v.values() if d['group']=='upper']
    top_min=min(b.ymin for b in upper);top_max=max(b.ymax for b in upper)
    proportions=dict(track_shoe_width_mm=SHOE_WIDTH,track_centres_mm=2*TRACK_Y,
        track_outer_width_mm=2*TRACK_Y+SHOE_WIDTH,aligned_platform_width_mm=top_max-top_min,
        aligned_outboard_margin_mm=[TRACK_Y+SHOE_WIDTH/2+top_min,TRACK_Y+SHOE_WIDTH/2-top_max],
        side_guide_clearance_mm=GUIDE_CLEARANCE,bushing_diameter_mm=2*BUSH_R,
        end_wheel_rise_mm=END_WHEEL_RISE,idler_assembly_offset_mm=IDLER_ASSEMBLY_OFFSET,
        sprocket_tooth_tip_clearance_mm=APOTHEM+4-SPROCKET_TIP_R)
    failures=[]
    if min(proportions['aligned_outboard_margin_mm'])<35:failures.append('tracks insufficiently wider than aligned platform')
    if hits:failures.append('assembly interference')
    if motion['collisions']:failures.append('arm or slew interference')
    reference=motion['collision_reference_envelope']
    if reference['boundary_collisions'] or not reference['negative_control_outside_reference_envelope'] or reference['negative_control_collision_mm3']<=.05:failures.append('lowered-body collision reference checks')
    if motion['idler_guide_collisions']:failures.append('idler guide travel interference')
    if len(motion['mechanical_stop_contact_deg'])!=2 or any(not 150<abs(x)<165 for x in motion['mechanical_stop_contact_deg']):failures.append('mechanical slew stop range')
    if motion['maximum_gear_intersection_mm3']>.05:failures.append('gear interference')
    if max(art)>.05:failures.append('track articulation interference')
    if loads['worst_stability']['margin_mm']<20:failures.append('stability margin below 20 mm')
    if max(loads['drive']['grade_torque_Nm_each'],loads['drive']['skid_turn_torque_Nm_each'])>loads['drive']['torque_at_current_limit_Nm']:failures.append('drive torque insufficient')
    if loads['drive']['traction_margin']<1.2:failures.append('traction margin insufficient')
    result=dict(status='PASS' if not failures else 'FAIL',failures=failures,
        assembly=dict(exact_intersections=n,collisions=hits),motion=motion,loads=loads,
        undercarriage=proportions,track=dict(links=len(pins),max_pitch_error_mm=float(abs(pitch_errors).max()),
            articulation_samples=41,articulation_range_deg=[-32,8],max_articulation_intersection_mm3=max(art),
            chordal_speed_variation_fraction=1-math.cos(math.pi/12),
            required_polygonal_take_up_mm=math.sqrt(240**2-400*math.sin(math.radians(15))**2)-20*math.cos(math.radians(15))-220),
        elapsed_seconds=time.time()-start,
        scope='Sampled exact CAD intersections within the collision reference envelope and quasi-static mechanics, not FEA, continuous collision proof or physical certification. This PASS applies to that sampled subset, not the full independent motion range. Low-boom sideways poses can collide with tracks; operators manage clearance. The preview does not enforce the reference envelope.')
    (ROOT/'validation.json').write_text(json.dumps(result,indent=2))
    (ROOT/'simulation/assembly_intersections.json').write_text(json.dumps(dict(intersections=hits,booleans=n),indent=2))
    (ROOT/'simulation/mass_properties.json').write_text(json.dumps(data,indent=2))
    print('VALIDATION',result['status'],failures,flush=True)
    return not failures

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['assembly','motion'])
    raise SystemExit(0 if check(parser.parse_args().stage) else 1)

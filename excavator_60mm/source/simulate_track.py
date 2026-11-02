"""Closed pin chain on the Track R5 wheel units. All model units are SI.

The drive is a speed servo clipped at the torque the R5 gearmotor gives at its
1.0 A driver limit, with the reflected rotor inertia as joint armature. The
idler slide uses the R5 recoil spring, preload and hard stop (track_wheel/).

MuJoCo's Newton constraint solver maintains the closed hinge loop. Steel bushings
contact the actual convex-decomposed sprocket; no belt motion is prescribed.
"""
import argparse,json,math,time
import numpy as np
import trimesh
import mujoco
from shapely.ops import triangulate,unary_union
from design import *
import tw_design as tw

SLIDE=tw.slide_spring()
DRIVE_LIMIT_NM=tw.drive_force_limit()['torque_Nm']
# Side pull on the free chain, as in the track_wheel/ lateral test. At the R5
# tension a 5 N pull no longer takes up the 0.6 mm guide clearance.
LATERAL_N=20.
# The R5 spring holds the return run taut above the carriers; their 2 mm guide
# flanges must still overlap its rails by at least 1 mm.
CARRIER_TOP_Z=RETURN_Z+RETURN_ROLLER_R
RAIL_BELOW_PIN=RAIL_FACE
MAX_CARRIER_LIFT_MM=GUIDE_HEIGHT-1.


def carrier_lift(sample):
    """Height (mm) of the return run's rail faces above each carrier top."""
    pins=[]
    for p,(w,x,y,z) in zip(sample['points'],sample['quaternions']):
        axis=np.array([1-2*(y*y+z*z),2*(x*y+w*z),2*(x*z-w*y)]);o=np.array(p)*1000
        pins += [o+10*axis,o-10*axis]
    pins=np.array(pins);top=pins[pins[:,2]>CARRIER_TOP_Z+RAIL_BELOW_PIN-3]
    lift=[]
    for xc in RETURN_ROLLERS:
        a=top[top[:,0]<=xc];b=top[top[:,0]>xc];a=a[np.argmax(a[:,0])];b=b[np.argmin(b[:,0])]
        lift.append(float(a[2]+(b[2]-a[2])*(xc-a[0])/(b[0]-a[0])-RAIL_BELOW_PIN-CARRIER_TOP_Z))
    return lift

def shoe_rail_meshes():
    """Convex pieces of the CAD running rail, including its pin-entry scallop.

    A shortened box misses the rail beside the scallop. A carrier roller then
    sinks into CAD material even when the simplified contact model passes.
    The rear bearing bore is omitted: hinge constraints replace pin/bore contact.
    """
    from shapely.geometry import box,Point
    profile=box(-10,-4,10,4).union(Point(-10,0).buffer(4,quad_segs=12))
    profile=profile.difference(Point(10,0).buffer(4.3,quad_segs=12))
    pieces=[t for t in triangulate(profile) if profile.covers(t)]
    assert unary_union(pieces).symmetric_difference(profile).area<1e-6
    changed=True
    while changed:
        changed=False
        for i in range(len(pieces)):
            for j in range(i):
                u=pieces[i].union(pieces[j])
                if u.geom_type=='Polygon' and abs(u.convex_hull.area-u.area)<1e-7:
                    pieces[j]=u.convex_hull;pieces.pop(i);changed=True;break
            if changed:break
    dest=ROOT/'simulation/shoe_contact_meshes_si';dest.mkdir(exist_ok=True);files=[]
    for side,(y0,y1) in enumerate([(-21,-14),(14,21)]):
        for i,p in enumerate(pieces):
            xz=np.asarray(p.exterior.coords)[:-1];n=len(xz)
            vertices=np.array([[x,y,z] for y in [y0,y1] for x,z in xz])*.001
            faces=[]
            for k in range(1,n-1):faces.extend([[0,k+1,k],[n,n+k,n+k+1]])
            for k in range(n):j=(k+1)%n;faces.extend([[k,j,n+j],[k,n+j,n+k]])
            f=dest/f'{side}_{i:02}.obj';trimesh.Trimesh(vertices=vertices,faces=faces,process=False).export(f);files.append(f)
    for old in set(dest.glob('*.obj'))-set(files):old.unlink()
    return files


def contact_meshes():
    profile=sprocket_outline(24,4)
    pieces=[t for t in triangulate(profile) if profile.covers(t)]
    assert unary_union(pieces).symmetric_difference(profile).area<1e-6
    changed=True
    while changed:
        changed=False
        for i in range(len(pieces)):
            for j in range(i):
                u=pieces[i].union(pieces[j])
                if u.geom_type=='Polygon' and abs(u.convex_hull.area-u.area)<1e-7:
                    pieces[j]=u.convex_hull;pieces.pop(i);changed=True;break
            if changed:break
    dest=ROOT/'simulation/contact_meshes_si';dest.mkdir(exist_ok=True);files=[]
    for i,p in enumerate(pieces):
        xz=np.asarray(p.exterior.coords)[:-1];n=len(xz)
        vertices=np.array([[x,y,z] for y in [-7,7] for x,z in xz])*.001
        faces=[]
        for k in range(1,n-1):faces.extend([[0,k+1,k],[n,n+k,n+k+1]])
        for k in range(n):j=(k+1)%n;faces.extend([[k,j,n+j],[k,n+j,n+k]])
        f=dest/f'{i:03}.obj';trimesh.Trimesh(vertices=vertices,faces=faces,process=False).export(f);files.append(f)
    for old in set(dest.glob('*.obj'))-set(files):old.unlink()
    return files


def make_model(ground=False):
    inertias=json.loads((ROOT/'source/track_mass_properties.json').read_text())
    def inertial(name):
        d=inertias[name];pos=' '.join(map(str,d['centre_m']));tensor=' '.join(map(str,d['fullinertia_kg_m2']))
        return f'<inertial pos="{pos}" mass="{d["mass_kg"]}" fullinertia="{tensor}"/>'
    files=contact_meshes();assets='\n'.join(f'<mesh name="tooth{i}" file="contact_meshes_si/{p.name}"/>' for i,p in enumerate(files))
    rails=shoe_rail_meshes()
    assets+='\n'+'\n'.join(f'<mesh name="rail{i}" file="shoe_contact_meshes_si/{p.name}"/>' for i,p in enumerate(rails))
    wheel_geoms='\n'.join(f'<geom type="mesh" mesh="tooth{i}" contype="2" conaffinity="5"/>' for i in range(len(files)))
    bodies=[f'''<body name="drive" pos="-.110 0 {AXLE_Z*.001}">
<joint name="drive" type="hinge" axis="0 1 0" damping=".0001" armature="{tw.reflected_inertia():.6g}"/>
{inertial('drive')}{wheel_geoms}
<geom name="hub_drum" type="cylinder" fromto="0 {tw.HUB_Y[0]*.001} 0 0 -.007 0" size="{tw.HUB_OD/2000}" contype="2" conaffinity="5"/>
<geom name="hub_cap" type="cylinder" fromto="0 .007 0 0 {tw.CAP_Y[1]*.001} 0" size="{tw.HUB_OD/2000}" contype="2" conaffinity="5"/></body>
<body name="slider" pos=".110 0 {AXLE_Z*.001}">
<joint name="slide" type="slide" axis="1 0 0" limited="true" range="{SLIDE['range'][0]:.6g} {SLIDE['range'][1]:.6g}" stiffness="{SLIDE['k']:.6g}"
 springref="{SLIDE['springref']:.6g}" damping="5" frictionloss=".5" solreflimit=".001 1" solimplimit=".99 .999 .0001"/>
{inertial('idler_slide')}
<body name="idler"><joint name="idler_spin" type="hinge" axis="0 1 0" damping=".0001"/>
{inertial('idler')}
<geom type="cylinder" fromto="0 -.007 0 0 .007 0" size="{IDLER_GUIDE_R*.001}" contype="2" conaffinity="5"/>
<geom type="cylinder" fromto="0 -.020 0 0 -.015 0" size="{IDLER_RAIL_R*.001}" contype="2" conaffinity="5"/>
<geom type="cylinder" fromto="0 .015 0 0 .020 0" size="{IDLER_RAIL_R*.001}" contype="2" conaffinity="5"/>
<geom type="cylinder" fromto="0 -.015 0 0 .015 0" size=".028" contype="2" conaffinity="5"/>
<geom name="idler_guide_left" type="cylinder" fromto="0 {-GUIDE_OUTER_Y*.001} 0 0 {-GUIDE_INNER_Y*.001} 0" size="{(IDLER_RAIL_R+GUIDE_HEIGHT)*.001}" contype="2" conaffinity="5"/>
<geom name="idler_guide_right" type="cylinder" fromto="0 {GUIDE_INNER_Y*.001} 0 0 {GUIDE_OUTER_Y*.001} 0" size="{(IDLER_RAIL_R+GUIDE_HEIGHT)*.001}" contype="2" conaffinity="5"/>
</body></body>''']
    for i,(x,z,r) in enumerate([(x,29,18) for x in ROAD_ROLLERS]+[(x,RETURN_Z,RETURN_ROLLER_R) for x in RETURN_ROLLERS]):
        bodies.append(f'''<body name="roller{i}" pos="{x*.001} 0 {z*.001}"><joint name="roller_spin{i}" type="hinge" axis="0 1 0" damping=".00002"/>
{inertial('roller'+str(i))}
<geom type="cylinder" fromto="0 -.020 0 0 .020 0" size=".013" contype="2" conaffinity="5"/>
<geom type="cylinder" fromto="0 {-GUIDE_INNER_Y*.001} 0 0 -.015 0" size="{r*.001}" contype="2" conaffinity="5"/>
<geom type="cylinder" fromto="0 .015 0 0 {GUIDE_INNER_Y*.001} 0" size="{r*.001}" contype="2" conaffinity="5"/>
<geom name="roller{i}_guide_left" type="cylinder" fromto="0 {-GUIDE_OUTER_Y*.001} 0 0 {-GUIDE_INNER_Y*.001} 0" size="{(r+GUIDE_HEIGHT)*.001}" contype="2" conaffinity="5"/>
<geom name="roller{i}_guide_right" type="cylinder" fromto="0 {GUIDE_INNER_Y*.001} 0 0 {GUIDE_OUTER_Y*.001} 0" size="{(r+GUIDE_HEIGHT)*.001}" contype="2" conaffinity="5"/></body>''')
    # Loaded test: a half-machine carriage can translate freely in X and Z.
    # Its pitch/roll/yaw are guided. Motion in X comes only from shoe/floor contact.
    mass=(json.loads((ROOT/'validation.json').read_text())['loads']['nominal_mass_kg']+.15)/2
    frame_mass=mass-(sum(d['mass_kg'] for name,d in inertias.items() if name!='shoe')+inertias['shoe']['mass_kg']*TRACK_LINKS)
    frame_joints=(f'<joint name="travel" type="slide" axis="1 0 0"/>'
                  f'<joint name="heave" type="slide" axis="0 0 1"/>'
                  f'<inertial pos="0 0 .08" mass="{frame_mass}" diaginertia=".03 .03 .03"/>') if ground else ''
    bodies=['<body name="frame">'+frame_joints+''.join(bodies)+'</body>']
    if ground:bodies.insert(0,'<geom name="floor" type="plane" size="2 1 .1" contype="8" conaffinity="1" friction=".6 .005 .0001"/>')
    equalities=[]
    for i,origin,a in track_poses():
        geoms=[f'<geom type="box" pos="0 0 -.005" size=".0094 {SHOE_WIDTH*.0005} .001"/>']
        geoms += [f'<geom type="mesh" mesh="rail{i}"/>' for i in range(len(rails))]
        for x in GROUSER_CENTRES:
            geoms.append(f'<geom type="box" pos="{x*.001} 0 -.0065" size=".001 {SHOE_WIDTH*.0005} .0005"/>')
        for x,y,length in [(10,-11.2,5),(10,11.2,5)]:
            geoms.append(f'<geom type="cylinder" fromto="{x*.001} {(y-length/2)*.001} 0 {x*.001} {(y+length/2)*.001} 0" size=".004"/>')
        geoms.append(f'<geom type="cylinder" fromto=".01 {-PIN_LENGTH*.0005} 0 .01 {PIN_LENGTH*.0005} 0" size=".0015" contype="4" conaffinity="2"/>')
        geoms.append(f'<geom type="cylinder" fromto=".01 {-BUSH_LENGTH*.0005} 0 .01 {BUSH_LENGTH*.0005} 0" size="{BUSH_R*.001}" contype="4" conaffinity="2"/>')
        sites=[]
        for end,x in [('front',.01),('rear',-.01)]:
            for sign in [-1,1]:sites.append(f'<site name="{end}{i}_{sign}" pos="{x} {sign*.018} 0" size=".0002"/>')
        bodies.append(f'<body name="shoe{i}" pos="{origin[0]*.001} 0 {origin[1]*.001}" quat="{math.cos(a/2)} 0 {-math.sin(a/2)} 0"><freejoint/>{inertial("shoe")}\n'+ '\n'.join(geoms+sites)+'</body>')
        for sign in [-1,1]:equalities.append(f'<connect site1="rear{i}_{sign}" site2="front{(i+1)%TRACK_LINKS}_{sign}" solref=".001 1" solimp=".9999 .99999 .0001"/>')
    xml=f'''<mujoco model="arm60_track_fixture"><compiler angle="radian" autolimits="true"/>
<option timestep=".0005" gravity="0 0 -9.81" integrator="implicitfast" solver="Newton" iterations="100" tolerance="1e-10" cone="elliptic" jacobian="sparse"/>
<default><geom contype="1" conaffinity="11" friction=".2 .001 .00001" condim="3" margin=".00002" solref=".002 1" solimp=".99 .999 .0001"/><joint armature=".00000001"/></default>
<asset>{assets}</asset><worldbody>{''.join(bodies)}</worldbody><equality>{''.join(equalities)}</equality>
<actuator><velocity name="drive_motor" joint="drive" kv="2" forcelimited="true" forcerange="{-DRIVE_LIMIT_NM:.6g} {DRIVE_LIMIT_NM:.6g}"/></actuator></mujoco>'''
    path=ROOT/('simulation/track_ground.xml' if ground else 'simulation/track_fixture.xml');path.write_text(xml)
    model=mujoco.MjModel.from_xml_path(str(path));data=mujoco.MjData(model)
    assert model.neq==2*TRACK_LINKS
    # Sprocket tooth meshes; the R5 hub drum and cap are the two extra cylinders.
    hub_geoms={model.geom('hub_drum').id,model.geom('hub_cap').id}
    drive_geoms=np.array([g for g in np.flatnonzero(model.geom_bodyid==model.body('drive').id) if g not in hub_geoms])
    assert model.nmesh==len(files)+len(rails) and len(files)==len(drive_geoms), 'Contact geometry was truncated'
    assert np.all(model.geom_type[drive_geoms]==mujoco.mjtGeom.mjGEOM_MESH)
    assert set(model.geom_dataid[drive_geoms])==set(range(len(files)))
    assert np.all(model.geom_contype[drive_geoms]==2) and np.all(model.geom_conaffinity[drive_geoms]==5)
    drive_id=model.joint('drive').qposadr[0];drive_v=model.joint('drive').dofadr[0];slide=model.joint('slide').qposadr[0]
    data.qpos[slide]=IDLER_ASSEMBLY_OFFSET*.001
    return model,data,len(files),drive_id,drive_v,slide


def command(t):
    """Enough travel for every link to circulate in both directions, then brake."""
    if t<15:return 1.6*min(1,max(0,t-.5)/2)
    if t<17:return 1.6-1.6*(t-15)
    if t<31:return -1.6
    return -1.6*max(0,1-(t-31)/2)


def run(ground=False):
    start=time.time();m,d,nmesh,drive,drivev,slide=make_model(ground);dt=m.opt.timestep
    shoe_ids=[m.body('shoe'+str(i)).id for i in range(TRACK_LINKS)]
    sitepairs=[(m.site(f'rear{i}_{s}').id,m.site(f'front{(i+1)%TRACK_LINKS}_{s}').id)
               for i in range(TRACK_LINKS) for s in [-1,1]]
    wheel_joints=['drive','idler_spin']+['roller_spin'+str(i) for i in range(5)]
    wheel_q=[m.joint(n).qposadr[0] for n in wheel_joints]
    frame=m.body('frame').id
    floor=m.geom('floor').id if ground else -1
    travel=m.joint('travel').dofadr[0] if ground else -1
    mass=float(m.body_mass.sum())
    trace=[];error=lateral=0.;contacts=0;ground_observations=0;ground_force=[]
    wheel_bodies=[m.body(n).id for n in ['drive','idler']+['roller'+str(i) for i in range(5)]]
    guide_ids={side:{i for i in range(m.ngeom) if (m.geom(i).name or '').endswith('_guide_'+side)} for side in ['left','right']}
    guide_contacts={side:0 for side in guide_ids};guide_wheels={}
    contact_force=np.zeros(6)
    mujoco.mj_forward(m,d)
    initial=max(np.linalg.norm(d.site_xpos[a]-d.site_xpos[b]) for a,b in sitepairs)
    assert initial<1e-9,initial
    steps=68000
    for k in range(steps+1):
        if k%40==0:
            # mj_forward makes positions consistent with qpos at this timestamp;
            # mj_step's cached Cartesian positions otherwise lag one time step.
            mujoco.mj_forward(m,d)
            points=d.xpos[shoe_ids]-d.xpos[frame]
            e=max(np.linalg.norm(d.site_xpos[a]-d.site_xpos[b]) for a,b in sitepairs)
            error=max(error,e);lateral=max(lateral,float(abs(points[:,1]).max()));contacts+=d.ncon
            normal=0.;wheel_support=np.zeros(7);guide_force=np.zeros(2)
            for c in range(d.ncon):
                contact=d.contact[c];g1,g2=contact.geom1,contact.geom2
                mujoco.mj_contactForce(m,d,c,contact_force)
                force=contact.frame.reshape(3,3).T@contact_force[:3]
                if ground and floor in [g1,g2]:normal+=contact_force[0];ground_observations+=1
                for j,body in enumerate(wheel_bodies):
                    if m.geom_bodyid[g1]==body:wheel_support[j]-=force[2]
                    if m.geom_bodyid[g2]==body:wheel_support[j]+=force[2]
                for j,side in enumerate(['left','right']):
                    if g1 in guide_ids[side] or g2 in guide_ids[side]:
                        guide_force[j]+=abs(force[1]);guide_contacts[side]+=1
                        wheel=m.body(m.geom_bodyid[g1 if g1 in guide_ids[side] else g2]).name+'_'+side
                        guide_wheels[wheel]=guide_wheels.get(wheel,0)+1
            if ground:ground_force.append(normal)
            trace.append(dict(t=float(d.time),angle=float(d.qpos[drive]),speed=float(d.qvel[drivev]),
                target=command(d.time),torque=float(d.actuator_force[0]),points=points.tolist(),
                quaternions=d.xquat[shoe_ids].tolist(),wheels=d.qpos[wheel_q].tolist(),
                wheel_vertical_support_N=wheel_support.tolist(),guide_force_N=guide_force.tolist(),
                frame=d.xpos[frame].tolist(),travel_speed=float(d.qvel[travel]) if ground else 0.,
                ground_normal_N=normal,hinge_error_mm=e*1000,idler_mm=float(d.qpos[slide]*1000)))
        if k==steps:break
        d.ctrl[0]=command(d.time)
        # Test guidance mechanically, with an external transverse load on the
        # free chain. No Y constraint or position prescription holds the belt.
        if not ground:
            side_load=LATERAL_N if 5<d.time<8 else -LATERAL_N if 24<d.time<27 else 0.
            d.xfrc_applied[shoe_ids,1]=side_load/TRACK_LINKS
        if ground:d.qfrc_applied[travel]=-.04*mass*9.81*math.tanh(d.qvel[travel]/.005)
        mujoco.mj_step(m,d)
        if k%10000==0:print('ground' if ground else 'fixture',k,'angle',round(d.qpos[drive],3),flush=True)
    forward=[v for v in trace if 11<v['t']<14]
    reverse=[v for v in trace if 27<v['t']<30]
    speed=float(np.mean([v['speed'] for v in forward]));back=float(np.mean([v['speed'] for v in reverse]))
    xyz=np.array([v['points'] for v in trace])
    phase=np.unwrap(np.arctan2(xyz[:,:,2]-AXLE_Z*.001,xyz[:,:,0]),axis=0)
    turning=np.argmin(abs(np.array([v['t'] for v in trace])-16))
    forward_laps=(phase[0]-phase[turning])/(2*math.pi)
    reverse_laps=(phase[-1]-phase[turning])/(2*math.pi)
    marker_path=float(np.linalg.norm(np.diff(xyz[:,6],axis=0),axis=1).sum())
    rotation=sum(abs(b['angle']-a['angle']) for a,b in zip(trace,trace[1:]));expected=rotation*PITCH*TEETH/(2*math.pi)*.001
    positions=[v['idler_mm'] for v in trace]
    checks={
        'all_links_complete_forward_circuit':bool(min(forward_laps)>1),
        'all_links_complete_reverse_circuit':bool(min(reverse_laps)>1),
        'forward_speed':abs(speed-1.6)<.12,
        'reverse_speed':abs(back+1.6)<.12,
        'controlled_stop':abs(trace[-1]['speed'])<.02,
        'hinge_closure':error<.0002,
        'lateral_guidance':lateral<.001,
        'idler_limits':min(positions)>SLIDE['range'][0]*1000-.1 and max(positions)<SLIDE['range'][1]*1000+.1,
        'pitch_travel':.9<marker_path/expected<1.1,
        'contacts':contacts>0,
        'solver_stable':all(w.number==0 for w in d.warning) and bool(np.isfinite(d.qpos).all()),
        'torque_limit':max(abs(v['torque']) for v in trace)<=DRIVE_LIMIT_NM+1e-6,
    }
    steady=forward+reverse
    supports=np.mean([v['wheel_vertical_support_N'] for v in steady],axis=0)
    def spins(rows):
        return (np.array(rows[-1]['wheels'])-rows[0]['wheels'])/(rows[-1]['t']-rows[0]['t'])
    forward_spins=spins(forward);reverse_spins=spins(reverse)
    wheel_checks=dict(mean_vertical_support_N=supports.tolist(),forward_rad_s=forward_spins.tolist(),
        reverse_rad_s=reverse_spins.tolist(),order=['drive','idler','road0','road1','road2','carrier0','carrier1'])
    # Every free wheel the chain bears on must turn: the idler always, the three
    # road rollers under load, and any roller the taut R5 runs touch on the stand.
    contact_wheels=sorted({1,2,3,4} if ground else {1}|{i for i in range(2,7) if abs(supports[i])>.05})
    wheel_checks['rotation_required']= [wheel_checks['order'][i] for i in contact_wheels]
    settled=[v for v in trace if v['t']>1]
    lift=np.array([carrier_lift(v) for v in settled])
    wheel_checks['carrier_lift_mm']=dict(minimum=lift.min(axis=0).tolist(),maximum=lift.max(axis=0).tolist(),
        mean=lift.mean(axis=0).tolist(),allowed=MAX_CARRIER_LIFT_MM)
    checks['carriers_bracket_return_run']=bool(lift.max()<MAX_CARRIER_LIFT_MM)
    checks['contacting_free_wheels_rotate_forward']=bool(min(forward_spins[contact_wheels])>.2)
    checks['contacting_free_wheels_rotate_reverse']=bool(max(reverse_spins[contact_wheels])<-.2)
    if not ground:
        checks['both_guide_flanks_engage']=all(n>0 for n in guide_contacts.values())
        checks['lateral_load_retained']=lateral<.001
    else:
        checks['each_road_roller_carries_load']=all(
            min(np.mean([v['wheel_vertical_support_N'][2:5] for v in rows],axis=0))>.1*mass*9.81
            for rows in [forward,reverse])
        checks['road_rollers_carry_primary_load']=bool(sum(supports[2:5])>.7*mass*9.81)
    loaded={}
    if ground:
        vf=float(np.mean([v['travel_speed'] for v in forward]));vr=float(np.mean([v['travel_speed'] for v in reverse]))
        pitch_speed=1.6*PITCH*TEETH/(2*math.pi)*.001
        normal=float(np.mean([v['ground_normal_N'] for v in forward+reverse]))
        checks.update(ground_contacts=ground_observations>0,
            forward_traction=abs(vf-pitch_speed)<.006,
            reverse_traction=abs(vr+pitch_speed)<.006,
            ground_support=abs(normal-mass*9.81)<mass*9.81*.12,
            chassis_stop=abs(trace[-1]['travel_speed'])<.002)
        loaded=dict(total_supported_mass_kg=mass,forward_speed_m_s=vf,reverse_speed_m_s=vr,
            pitch_speed_m_s=pitch_speed,mean_ground_normal_N=normal,weight_N=mass*9.81,
            ground_contact_observations=ground_observations,final_speed_m_s=trace[-1]['travel_speed'],
            max_travel_m=max(v['frame'][0] for v in trace),
            final_position_m=trace[-1]['frame'],rolling_resistance_coefficient=.04)
    checks={name:bool(passed) for name,passed in checks.items()}
    report=dict(status='PASS' if all(checks.values()) else 'FAIL',engine='MuJoCo '+mujoco.__version__+' Newton',
        wheel_checks=wheel_checks,guide_contacts=guide_contacts,guide_contacts_by_wheel=guide_wheels,lateral_test_force_N=0 if ground else LATERAL_N,
        time_step_s=float(dt),steps=steps,links=TRACK_LINKS,hinge_constraints=2*TRACK_LINKS,
        drive_angle_rad=trace[-1]['angle'],target_speed_rad_s=1.6,final_speed_rad_s=trace[-1]['speed'],
        max_hinge_error_mm=error*1000,max_lateral_drift_mm=lateral*1000,
        marker_excursion_mm=float(np.linalg.norm(xyz[:,6]-xyz[0,6],axis=1).max()*1000),
        contact_observations=contacts,contact_convex_pieces=nmesh,contact_geometry_verified=True,
        torque_limit_Nm=DRIVE_LIMIT_NM,idler_travel_mm=[min(positions),max(positions)],
        idler_travel_limits_mm=[SLIDE['range'][0]*1000,SLIDE['range'][1]*1000],
        idler_spring=tw.SPRING['model'],idler_spring_N_per_mm=tw.SPRING['rate_N_mm'],idler_preload_N=tw.spring_state()['force'],
        drive_armature_kg_m2=tw.reflected_inertia(),initial_hinge_error_mm=initial*1000,
        elapsed_seconds=time.time()-start,forward_mean_speed_rad_s=speed,reverse_mean_speed_rad_s=back,
        peak_angle_rad=max(v['angle'] for v in trace),total_rotation_rad=rotation,
        marker_path_mm=marker_path*1000,expected_pitch_travel_mm=expected*1000,chain_travel_ratio=marker_path/expected,
        minimum_forward_circuits=float(min(forward_laps)),minimum_reverse_circuits=float(min(reverse_laps)),
        peak_applied_torque_Nm=max(abs(v['torque']) for v in trace),checks=checks,loaded=loaded,
        scope=('Half-machine mass on a planar carriage free in X/Z, rigid floor and actual shoe contact; pitch/roll/yaw guided. '
            if ground else 'Gravity-loaded fixed single-track test stand; no floor. ')+
            'R5 track wheel: speed servo clipped at the 1.0 A driver torque with the reflected rotor inertia, steel-bushing sprocket on the hub drum, '
            'recoil idler on the C-600-072-1500 spring with its preload and hard stop, rollers with outer guide flanges, 34 free shoes and 68 hinge point constraints. '
            'Simplified rigid shoe contacts and ideal bearings; rail/frame collisions, soil, wear, printed elasticity and motor heating are not modeled.')
    stem='track_ground' if ground else 'track'
    (ROOT/f'simulation/{stem}_dynamics.json').write_text(json.dumps(report,indent=2)+'\n')
    (ROOT/f'simulation/{stem}_trace.json').write_text(json.dumps(trace,separators=(',',':')))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained');ts=[v['t'] for v in trace]
    axes[0,0].plot(ts,[v['speed'] for v in trace],label='Actual');axes[0,0].plot(ts,[v['target'] for v in trace],'--',label='Command')
    axes[0,0].set(xlabel='Time (s)',ylabel='Sprocket speed (rad/s)',title='Full circuits, reversal and stop');axes[0,0].legend()
    marker=xyz[:,6]*1000
    axes[0,1].plot(marker[:,0],marker[:,2],lw=1);axes[0,1].scatter(*marker[0,[0,2]],label='Start',s=30)
    axes[0,1].set(xlabel='X relative to chassis (mm)',ylabel='Z (mm)',title='One shoe travels the whole loop');axes[0,1].set_aspect('equal')
    axes[1,0].plot(ts,[v['idler_mm'] for v in trace]);axes[1,0].set(xlabel='Time (s)',ylabel='Idler displacement (mm)',title=f"Recoil idler: {SLIDE['range'][0]*1000:.1f} to +{SLIDE['range'][1]*1000:.1f} mm travel")
    if ground:
        axes[1,1].plot(ts,[v['travel_speed'] for v in trace],label='Ground-driven carriage')
        axes[1,1].plot(ts,[v['speed']*PITCH*TEETH/(2*math.pi)*.001 for v in trace],'--',label='Pitch prediction')
        axes[1,1].set(xlabel='Time (s)',ylabel='Travel speed (m/s)',title='Ground contact, load and braking');axes[1,1].legend()
    else:
        axes[1,1].plot(ts,[v['hinge_error_mm'] for v in trace]);axes[1,1].set(xlabel='Time (s)',ylabel='Hinge closure error (mm)',title='Numerical constraint accuracy')
    for a in axes.flat:a.grid(alpha=.2)
    fig.savefig(ROOT/f'images/{stem}_dynamics.png',dpi=160);plt.close(fig)
    print(json.dumps(report,indent=2),flush=True);return report['status']=='PASS'

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--ground',action='store_true');args=parser.parse_args()
    raise SystemExit(0 if run(args.ground) else 1)

"""Forward dynamics of the complete arm, with limited linear drives and gravity.
Playback records actual integrated joint states. It never assigns joint positions
while stepping. Example motor capacity and unmeasured materials are not ratings.
"""
import argparse,gzip,hashlib,itertools,json,math,time
from pathlib import Path
import numpy as np
import mujoco
from scipy.interpolate import RegularGridInterpolator, CubicHermiteSpline
from physics_model import *


def potential(strokes,payload=0.,mass_factor=1.):
    props=json.loads((SIM/'mass_properties.json').read_text())['groups'] if not hasattr(potential,'props') else potential.props
    potential.props=props;s=solve(strokes);energy=0.
    for group,p in props.items():
        if group=='base':continue
        c=np.array(p['centre_m'])*1000
        if group.endswith(('_cylinder','_rod')):
            drive=DRIVE_BY_NAME[group.rsplit('_',1)[0]];i=drive['axis'];a,b=drive['a'],drive['b']
            if group.endswith('_rod'):c[2]+=strokes[i]
            direction=s['points'][b]-s['points'][a];angle=math.atan2(direction[1],direction[0])
            height=s['points'][a][1]-math.cos(angle)*c[0]+math.sin(angle)*c[2]
        else:height=s['origins'][group][1]+(rot(s['angles'][group])@c[[0,2]])[1]
        energy+=9.81*p['mass_kg']*mass_factor*height*.001
    if payload:
        height=s['origins']['bucket'][1]+(rot(s['angles']['bucket'])@np.array([-25.,-50.]))[1]
        energy+=9.81*payload*height*.001
    return energy


def holding_force(strokes,payload=0.,mass_factor=1.):
    result=[];step=.001
    for i in range(3):
        a=list(strokes);b=list(strokes);a[i]+=step;b[i]-=step
        result.append((potential(a,payload,mass_factor)-potential(b,payload,mass_factor))/(2*step*.001))
    return np.array(result)


def interpolator(payload):
    grid=np.linspace(0,60,9)
    values=np.array([holding_force(st,payload) for st in itertools.product(grid,repeat=3)]).reshape(9,9,9,3)
    return RegularGridInterpolator((grid,grid,grid),values,bounds_error=False,fill_value=None)


TIME_SCALE=20.0  # 54 s presentation corresponds to 1080 simulated seconds.

def trajectory(kind='cycle'):
    motion=json.loads((ROOT/'motion.json').read_text())
    start=np.array(motion['frames'][0]['strokes'])
    if kind=='hold':return [(0.,start),(10.,start)]
    return [(f['t']*TIME_SCALE,np.array(f['strokes'])) for f in motion['frames']]


def reference_at(t,knots):
    if getattr(reference_at,'knots',None) is not knots:
        times=np.array([row[0] for row in knots]);positions=np.array([row[1] for row in knots])*.001
        reference_at.spline=CubicHermiteSpline(times,positions,np.gradient(positions,times,axis=0))
        reference_at.knots=knots
    return reference_at.spline(t),reference_at.spline(t,1)


DRIVE_AXES=np.array([d['axis'] for d in DRIVES])
AXIS_COUNTS=np.bincount(DRIVE_AXES,minlength=3)


def axis_strokes(actual):
    return np.array([actual[DRIVE_AXES==i].mean() for i in range(3)])


def frame(model,data,target,forces):
    drive_strokes=np.array([float(data.qpos[model.joint(d['name']+'_slide').qposadr[0]]*1000) for d in DRIVES])
    def q(name):return float(data.qpos[model.joint(name).qposadr[0]])
    theta,phi,gamma,alpha,delta=[q(n) for n in ['boom_angle','stick_angle','bucket_angle','rocker_angle','coupler_angle']]
    angles=dict(base=0.,boom=theta,stick=theta+phi,bucket=theta+phi+gamma,rocker=theta+phi+alpha,coupler=theta+phi+alpha+delta)
    origins={'base':[0.,0.]}
    for name in ['boom','stick','bucket','rocker','coupler']:
        pos=data.xpos[model.body(name).id]*1000;origins[name]=[float(pos[0]),float(pos[2])]
    actuators=[]
    for drive in DRIVES:
        name=drive['name'];pos=data.xpos[model.body(name+'_cylinder').id]*1000
        zaxis=data.xmat[model.body(name+'_cylinder').id].reshape(3,3)[:,2]
        actuators.append(dict(name=name,origin=pos.tolist(),angle=math.atan2(zaxis[2],zaxis[0])))
    return dict(time=round(float(data.time),6),strokes=axis_strokes(drive_strokes).round(5).tolist(),drive_strokes=drive_strokes.round(6).tolist(),target_strokes=(target*1000).round(4).tolist(),target_drive_strokes=(target[DRIVE_AXES]*1000).round(4).tolist(),force_N=np.array(forces).round(4).tolist(),angles=angles,origins=origins,actuators=actuators,tip_mm=(data.site_xpos[model.site('tooth_tip').id]*1000).round(4).tolist())


def run_case(name,payload=0.,force_limit=100.,kind='cycle',timestep=.002,duration=None,record=True,powered=True,gravity=True,sensor_bias_mm=0.):
    begun=time.time();xml=model_xml(payload,force_limit,timestep);(SIM/(name+'.xml')).write_text(xml)
    model=mujoco.MjModel.from_xml_string(xml)
    if not gravity:model.opt.gravity[:]=0
    if not powered:model.actuator_gainprm[:]=0;model.actuator_biasprm[:]=0
    data=mujoco.MjData(model);knots=trajectory(kind);set_initial_pose(model,data,knots[0][1])
    duration=knots[-1][0] if duration is None else duration
    ids=np.array([model.joint(d['name']+'_slide').qposadr[0] for d in DRIVES]);dofs=np.array([model.joint(d['name']+'_slide').dofadr[0] for d in DRIVES]);actids=np.array([model.actuator(d['name']+'_drive').id for d in DRIVES])
    gravity_force=interpolator(payload) if powered and gravity else None
    bias=np.array([0.,sensor_bias_mm*.001,0.,0.])
    peakforce=np.zeros(4);peakerr=np.zeros(4);peakvel=np.zeros(4);saturated=np.zeros(4);ff=np.zeros(3)
    minstroke=np.full(4,np.inf);maxstroke=-minstroke;peakclosure=0.;minz=np.inf;maxz=-np.inf;frames=[]
    peak_net_moment=peak_net_torsion=peak_force_difference=peak_stroke_difference=0.
    steps=round(duration/timestep);stride=max(1,round(.1/timestep));last_report=0.
    for step in range(steps+1):
        target,desired_velocity=reference_at(data.time,knots);target4=target[DRIVE_AXES]
        actual=data.qpos[ids];velocity=data.qvel[dofs]
        if powered:
            if gravity_force is not None and step%max(1,round(.02/timestep))==0:ff=np.asarray(gravity_force(np.clip(axis_strokes(actual)*1000,0,60))).reshape(3)
            # Each motor has its own feedback and force-speed law. There is no
            # doubled-force surrogate and no imposed equality between the slides.
            feed=ff[DRIVE_AXES]/AXIS_COUNTS[DRIVE_AXES]
            raw=(feed+80000*(target4-(actual+bias))+(force_limit/NO_LOAD_SPEED)*desired_velocity[DRIVE_AXES])/force_limit
            command=np.clip(raw,-1,1);saturated+=(np.abs(raw)>1)*timestep
        else:command=np.zeros(4)
        data.ctrl[actids]=command;mujoco.mj_forward(model,data);force=data.actuator_force[actids].copy()
        moment=np.zeros(3)
        for j in [0,1]:
            zaxis=data.xmat[model.body(DRIVES[j]['name']+'_cylinder').id].reshape(3,3)[:,2]
            moment+=np.cross([0,DRIVES[j]['y']*.001,0],force[j]*zaxis)
        boom_x=data.xmat[model.body('boom').id].reshape(3,3)[:,0]
        peak_net_moment=max(peak_net_moment,float(np.linalg.norm(moment)));peak_net_torsion=max(peak_net_torsion,abs(float(moment@boom_x)))
        peak_force_difference=max(peak_force_difference,abs(float(force[0]-force[1])))
        peak_stroke_difference=max(peak_stroke_difference,abs(float(actual[0]-actual[1]))*1000)
        peakforce=np.maximum(peakforce,np.abs(force));peakerr=np.maximum(peakerr,np.abs(target4-actual)*1000);peakvel=np.maximum(peakvel,np.abs(velocity)*1000)
        minstroke=np.minimum(minstroke,actual*1000);maxstroke=np.maximum(maxstroke,actual*1000)
        for a,b in [(d['name']+'_eye',d['name']+'_target') for d in DRIVES]+[('Q_coupler','Q_bucket')]:
            peakclosure=max(peakclosure,float(np.linalg.norm(data.site_xpos[model.site(a).id]-data.site_xpos[model.site(b).id])*1000))
        tipz=data.site_xpos[model.site('tooth_tip').id,2]*1000;minz=min(minz,tipz);maxz=max(maxz,tipz)
        if record and (step%stride==0 or step==steps):frames.append(frame(model,data,target,force))
        if step==steps:break
        mujoco.mj_step(model,data)
        if not np.all(np.isfinite(data.qpos)):raise RuntimeError('Non-finite state')
        if time.time()-last_report>25:
            print(name,'simulated',round(data.time,1),'/',duration,'wall',round(time.time()-begun,1),flush=True);last_report=time.time()
    report=dict(name=name,revision=10,payload_kg=payload,drive_names=[d['name'] for d in DRIVES],force_limit_N_per_drive=force_limit,no_load_speed_mm_s=NO_LOAD_SPEED*1000,timestep_s=timestep,duration_s=duration,powered=powered,gravity=gravity,boom1_sensor_bias_mm=sensor_bias_mm,peak_motor_force_N=peakforce.tolist(),maximum_tracking_error_mm=peakerr.tolist(),final_tracking_error_mm=(np.abs(target4-data.qpos[ids])*1000).tolist(),peak_slide_speed_mm_s=peakvel.tolist(),minimum_strokes_mm=minstroke.tolist(),maximum_strokes_mm=maxstroke.tolist(),maximum_pin_closure_error_mm=peakclosure,tooth_z_range_mm=[float(minz),float(maxz)],seconds_at_force_or_speed_limit=saturated.tolist(),peak_boom_force_difference_N=peak_force_difference,peak_boom_stroke_difference_mm=peak_stroke_difference,peak_net_eccentric_motor_moment_Nm=peak_net_moment,peak_projected_boom_torsion_Nm=peak_net_torsion,side_load_scope='Net moment of the two simulated motor forces at lateral offsets; not FEA stress or elastic twist',motion_sha256=hashlib.sha256((ROOT/'motion.json').read_bytes()).hexdigest(),presentation_time_scale=TIME_SCALE,final_drive_strokes_mm=(data.qpos[ids]*1000).tolist(),final_tip_mm=(data.site_xpos[model.site('tooth_tip').id]*1000).tolist(),wall_seconds=round(time.time()-begun,2),warnings={n:int(data.warning[i].number) for i,n in enumerate(['INERTIA','CONTACTFULL','CNSTRFULL','VGEOMFULL','BADQPOS','BADQVEL','BADQACC','BADCTRL'])})
    (SIM/(name+'_report.json')).write_text(json.dumps(report,indent=2)+'\n')
    if record:(SIM/(name+'_trace.json.gz')).write_bytes(gzip.compress(json.dumps(dict(scenario=report,frames=frames),separators=(',',':')).encode()))
    print(json.dumps(report,indent=2),flush=True);return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('case',choices=['hold','unloaded','payload','weak','gravity','zero_gravity','convergence','sync_bias']);case=parser.parse_args().case
    if case=='unloaded':run_case('unloaded')
    elif case=='payload':run_case('payload_150g',payload=.15)
    elif case=='hold':run_case('hold',payload=.15,kind='hold',duration=3.)
    elif case=='weak':run_case('underpowered_20N',payload=.15,force_limit=20.,kind='hold',duration=10.)
    elif case=='gravity':run_case('gravity_unpowered',powered=False,duration=4.,timestep=.001)
    elif case=='zero_gravity':run_case('zero_gravity',powered=False,gravity=False,duration=4.,timestep=.001,record=False)
    elif case=='convergence':run_case('gravity_unpowered_half_step',powered=False,duration=4.,timestep=.0005,record=False)
    elif case=='sync_bias':run_case('sync_bias_0p5mm',payload=.15,kind='hold',duration=5.,sensor_bias_mm=.5)


if __name__=='__main__':main()


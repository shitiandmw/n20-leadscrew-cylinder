"""Validate R10 rigid-body dynamics separately from load-capacity success."""
import gzip, hashlib, itertools, json
import numpy as np
import mujoco
from simulate_arm import holding_force, TIME_SCALE
from physics_model import *


def check():
    names=['hold','unloaded','payload_150g','underpowered_20N','gravity_unpowered','zero_gravity','gravity_unpowered_half_step','sync_bias_0p5mm']
    reports={n:json.loads((SIM/(n+'_report.json')).read_text()) for n in names}
    checks=[]
    def require(ok,label):
        assert ok,label
        checks.append(label)
    digest=hashlib.sha256((ROOT/'motion.json').read_bytes()).hexdigest()
    for name,r in reports.items():
        require(r['motion_sha256']==digest,name+': current target motion')
        require(not any(r['warnings'].values()),name+': no numerical warnings')
        require(r['maximum_pin_closure_error_mm']<.1,name+': pin closure below 0.1 mm')
        require(max(r['peak_motor_force_N'])<=r['force_limit_N_per_drive']+1e-6,name+': bounded force')
    require(max(reports['hold']['maximum_tracking_error_mm'])<.01,'Loaded initial pose holds')
    require(max(reports['unloaded']['maximum_tracking_error_mm'])<1,'Unloaded motion tracks within 1 mm stroke')
    require(max(reports['payload_150g']['maximum_tracking_error_mm'])<1,'150 g cycle tracks within 1 mm on all four drives')
    require(reports['payload_150g']['peak_boom_stroke_difference_mm']<.01,'Nominal paired boom strokes remain aligned')
    require(reports['payload_150g']['peak_boom_force_difference_N']<.1,'Symmetric nominal drives share force')
    require(reports['payload_150g']['peak_net_eccentric_motor_moment_Nm']<.01,'Nominal opposed lateral motor moments cancel')
    require(reports['sync_bias_0p5mm']['peak_boom_force_difference_N']>20,'0.5 mm feedback bias produces unequal opposing motor loads')
    require(reports['underpowered_20N']['maximum_tracking_error_mm'][0]>20,'20 N cannot hold initial loaded arm')
    require(max(reports['zero_gravity']['peak_slide_speed_mm_s'])<1e-7,'No gravity and no drive leaves pose stationary')
    require(reports['gravity_unpowered']['final_tip_mm'][2]<0,'Unpowered backdrivable arm falls under gravity')
    convergence=float(np.linalg.norm(np.array(reports['gravity_unpowered']['final_tip_mm'])-reports['gravity_unpowered_half_step']['final_tip_mm']))
    require(convergence<.15,'Gravity endpoint converges within 0.15 mm at half timestep')
    max_tip=max_force=max_side=0.
    for payload in [0.,.15]:
        model=mujoco.MjModel.from_xml_string(model_xml(payload));data=mujoco.MjData(model)
        for strokes in itertools.product([1.,30.,59.],repeat=3):
            s=set_initial_pose(model,data,strokes)
            max_tip=max(max_tip,float(np.linalg.norm(data.site_xpos[model.site('tooth_tip').id][[0,2]]*1000-s['points']['T'])))
            for drive in DRIVES:
                max_side=max(max_side,abs(data.site_xpos[model.site(drive['name']+'_target').id,1]*1000-drive['y']),abs(data.xpos[model.body(drive['name']+'_cylinder').id,1]*1000-drive['y']))
            bias=data.qfrc_bias.copy();numerical=[]
            for axis in range(3):
                a=list(strokes);b=list(strokes);a[axis]-=.001;b[axis]+=.001
                set_initial_pose(model,data,a);qa=data.qpos.copy();set_initial_pose(model,data,b);qb=data.qpos.copy()
                derivative=np.zeros(model.nv);mujoco.mj_differentiatePos(model,derivative,.000002,qa,qb);numerical.append(float(bias@derivative))
            max_force=max(max_force,float(np.max(np.abs(np.array(numerical)-holding_force(strokes,payload)))))
    require(max_tip<1e-5,'54 CAD / MuJoCo configurations agree')
    require(max_side<1e-8,'Four independent drives are placed at their specified Y planes')
    require(max_force<.01,'Independent virtual-work forces match MuJoCo generalized gravity')
    motion=json.loads((ROOT/'motion.json').read_text());target=np.array([f['tip'] for f in motion['frames']]);times=np.array([f['t'] for f in motion['frames']])
    path={};loads={}
    for name,payload in [('unloaded',0.),('payload_150g',.15)]:
        rows=json.loads(gzip.decompress((SIM/(name+'_trace.json.gz')).read_bytes()))['frames']
        actual=np.array([f['tip_mm'] for f in rows])[:,[0,2]];t=np.array([f['time']/TIME_SCALE for f in rows]);planned=np.column_stack([np.interp(t,times,target[:,i]) for i in range(2)])
        cut=(t>=11)&(t<=18);lift=(t>=23)&(t<=33);dump=(t>=33)&(t<=40)
        path[name]=dict(max_tip_deviation_mm=float(np.max(np.linalg.norm(actual-planned,axis=1))),cut_max_height_error_mm=float(np.max(np.abs(actual[cut,1]+240))),dump_min_tip_z_mm=float(actual[dump,1].min()),lift_max_absolute_bucket_angle_error_deg=float(max(abs(np.degrees(rows[i]['angles']['bucket'])+30) for i in np.flatnonzero(lift))))
        f=np.array([holding_force(row['strokes'],payload) for row in motion['frames']])
        loads[name]=dict(payload_kg=payload,max_absolute_axis_gravity_thrust_N=np.max(np.abs(f),axis=0).tolist(),equal_share_per_drive_N=(np.max(np.abs(f),axis=0)[[0,0,1,2]]/np.array([2,2,1,1])).tolist())
    require(path['unloaded']['max_tip_deviation_mm']<5,'Unloaded actual tip follows target within 5 mm')
    require(path['unloaded']['dump_min_tip_z_mm']>140,'Unloaded actual dumping remains above mounting plane')
    require(path['payload_150g']['max_tip_deviation_mm']<5,'Loaded actual tip follows target within 5 mm')
    require(path['payload_150g']['dump_min_tip_z_mm']>140,'Loaded actual dumping remains above mounting plane')
    require(max(loads['payload_150g']['equal_share_per_drive_N'])<100,'Loaded quasistatic equal-share demands stay below each 100 N assumption')
    report=dict(status='PASS',meaning='Numerical and behavioral validation passes; this is not a payload or strength qualification',revision=10,checks=checks,unloaded_cycle_status='TRACKS',loaded_150g_at_100N_each_status='TRACKS',forward_pose_cases=54,max_tip_pose_discrepancy_mm=max_tip,max_side_pin_position_error_mm=max_side,max_gravity_discrepancy_N=max_force,gravity_half_step_endpoint_difference_mm=convergence,actual_path=path,gravity_loads_on_path=loads,motion_sha256=digest,source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('physics_model.py'),Path(__file__).with_name('simulate_arm.py'),Path(__file__).with_name('kinematics.py')]},scope='Fixed-base 3D rigid-body inertias and four independently integrated drives. Two symmetric boom slides close separately onto the same rigid boom. Ideal hinge axes, assumed force-speed law and ideal stroke feedback. No soil, chassis stability or elastic twist/stress. Unpowered tests assume backdrivable slides.')
    (SIM/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':check()

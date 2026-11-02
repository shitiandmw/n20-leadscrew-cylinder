"""Fresh J6 constrained-chain motion demo; not a JGY electrical/load test.

Retains the chain and recoil spring, updates upper roller radii and centres. Recomputes
direct-drive CAD inertia. A generic torque-limited servo commands +/-20 rpm.
No Pololu motor, current, gear ratio or rotor inertia model is used.
"""
import sys,json,time,math
from pathlib import Path
from support_paths import ROOT as J8_ROOT, REPO
ROOT=J8_ROOT/'simulation/recomputed_baseline'
sys.path.insert(0,str(REPO/'track_wheel/source'))
import simulate_track_wheel as sim
import j6_parts as s
j1=s.j2.j1
import numpy as np
import mujoco

def main():
    sim.SIM=ROOT/'simulation';sim.SIM.mkdir(parents=True,exist_ok=True)
    mp=json.loads((REPO/'track_wheel/simulation/mass_properties.json').read_text())
    inst=s.unit(s.parts())
    def density(n,d):
        if n=='J10_torque_spindle':return 7.85e-6
        return sim.density(n,d,d['shape'])
    items=[(d['shape'].translate((-j1.DX,0,-j1.DZ)),density(n,d)) for n,d in inst.items() if d['group']=='drive']
    mp['drive']=sim.combine(items)
    for x,z,g in s.AXES:
        mp[g]=sim.combine([(d['shape'].translate((-x,0,-z)),density(n,d)) for n,d in inst.items() if d['group']==g])
    sim.ex.RETURN_ROLLER_R=s.RETURN_R
    sim.ex.RETURN_Z=s.RETURN_Z
    sim.tp.RETURN_Z=s.RETURN_Z
    (sim.SIM/'mass_properties.json').write_text(json.dumps(mp,indent=2)+'\n')
    sim.motor_constants=lambda:dict(reflected_inertia_kg_m2=0.0)
    m,d=sim.make_model(ground=False)
    probe=sim.Probe(m,d)
    omega=20*2*math.pi/60
    curve=[(0,0),(.5,0),(1.5,omega),(6,omega),(7,-omega),(12,-omega),(13,0),(13.5,0)]
    integral=0.;trace=[];rows=[];start=time.time();max_gap=0.
    for k in range(round(13.5/sim.DT)+1):
        speed=float(d.qvel[probe.drive_v]);target=sim.ramp(d.time,curve)
        error=target-speed;raw=.9*error+3*integral
        if abs(raw)<1.2:integral+=error*sim.DT
        torque=float(np.clip(raw,-1.2,1.2));d.ctrl[0]=torque
        if k%40==0:
            mujoco.mj_forward(m,d)
            gap=max(np.linalg.norm(d.site_xpos[m.site(f'rear{i}_{side}').id]-d.site_xpos[m.site(f'front{(i+1)%34}_{side}').id])*1000 for i in range(34) for side in [-1,1])
            max_gap=max(max_gap,gap)
            row=dict(t=round(float(d.time),4),speed_rad_s=speed,target_rad_s=target,torque_Nm=torque,
                     drive=float(d.qpos[probe.drive_q]),idler_mm=float(d.qpos[probe.slide_q])*1000,
                     chain_travel_mm=probe.chain_travel(),joint_error_mm=gap)
            rows.append(row)
            rel=d.xpos[probe.shoes]-d.xpos[probe.frame]
            trace.append(dict(t=row['t'],drive=row['drive'],idler_mm=row['idler_mm'],speed_rpm=speed*60/(2*math.pi),
                              torque_Nm=torque,wheels=[float(d.qpos[m.joint(j).qposadr[0]]) for j in ['idler_spin']+[f'roller_spin{i}' for i in range(5)]],
                              shoes=np.round(rel*1000,4).tolist(),quats=np.round(d.xquat[probe.shoes],6).tolist()))
        if k%4000==0:print(f'Demo {d.time:.1f}s, {speed*60/(2*math.pi):.2f} rpm, {torque:.3f} Nm',flush=True)
        if k<round(13.5/sim.DT):mujoco.mj_step(m,d)
    def mean_rpm(a,b):return float(np.mean([r['speed_rad_s']*60/(2*math.pi) for r in rows if a<=r['t']<=b]))
    travel=np.array([r['chain_travel_mm'] for r in rows]);angle=np.array([r['drive'] for r in rows]);travel-=travel[0];angle-=angle[0]
    sign=1 if np.dot(travel,angle)>0 else -1
    slip=travel-sign*sim.R_EFF*angle
    report=dict(scope='Unloaded fixed-frame digital chain motion; generic +/-1.2 Nm servo, NOT measured JGY motor performance or whole-vehicle dynamics.',
        selected_speed_assumption='20 rpm is a demonstration target; motor voltage and ratio remain unselected.',upper_roller_running_diameter_mm=30,upper_roller_axis_z_mm=s.RETURN_Z,fresh_J6_simulation=True,
        dt_s=sim.DT,duration_s=float(d.time),frames=len(trace),forward_rpm=mean_rpm(2,5.5),reverse_rpm=mean_rpm(8,11.5),
        max_abs_torque_Nm=max(abs(r['torque_Nm']) for r in rows),max_joint_error_mm=max_gap,
        phase_error_mm=[float(slip.min()),float(slip.max())],idler_absolute_range_mm=[min(r['idler_mm'] for r in rows),max(r['idler_mm'] for r in rows)],
        solver_warnings=int(sum(w.number for w in d.warning)),finite=bool(np.isfinite(d.qpos).all()),drive_inertia_from_J1_direct_drive_CAD=mp['drive'],
        rotor_inertia='Not modeled; no verified motor rotor/gear inertia supplied.',elapsed_s=round(time.time()-start,1))
    report['playback_checks_pass']=report['finite'] and report['solver_warnings']==0 and max_gap<.3 and max(abs(slip))<10 and abs(report['forward_rpm']-20)<1 and abs(report['reverse_rpm']+20)<1
    (sim.SIM/'demo_trace.json').write_text(json.dumps(trace,separators=(',',':')))
    (sim.SIM/'demo_report.json').write_text(json.dumps(report,indent=2)+'\n')
    (sim.SIM/'demo_samples.json').write_text(json.dumps(rows,separators=(',',':')))
    print(json.dumps(report,indent=2),flush=True)
    assert report['playback_checks_pass']

if __name__=='__main__':main()

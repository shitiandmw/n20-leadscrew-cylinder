"""Reduced-order traction and slew dynamics, separate from pin-chain physics.

Explicit Coulomb traction/scrub and rolling losses. No claim to model soil or
track deformation. SI units. Control laws are a simulation reference, not flashed
firmware; real current/position sensing and limits are specified in the guide.
"""
import json,math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from design import *
# Sprocket torque at the 1.0 A driver current limit (track_wheel/, includes the hub-stage loss).
DRIVE_LIMIT_NM=tw.drive_force_limit()['torque_Nm']


def travel_case(mass,left,right,slope=0,power_loss=False):
    dt=.001;length=GROUND_HALF_LENGTH*.002;width=TRACK_Y*.002;radius=PITCH_R*.001
    inertia=mass*(length**2+width**2)/12+.12
    v=w=x=y=yaw=0.;rows=[];energy=0.;max_torque=0
    grade=math.radians(slope);normal=mass*9.81*math.cos(grade)
    for k in range(5000):
        t=k*dt;desired=np.array([left,right]) if t<3 else np.zeros(2)
        sides=np.array([v-w*width/2,v+w*width/2])
        limit=min(DRIVE_LIMIT_NM/radius,.30*normal/2)
        forces=np.clip(5000*(desired-sides),-limit,limit)
        if power_loss and t>=3:forces[:]=0
        rolling=.04*normal/2*np.tanh(sides/.005)
        scrub=.45*normal*length/4*math.tanh(w/.02)
        acc=(sum(forces-rolling)-mass*9.81*math.sin(grade))/mass
        alpha=((forces[1]-forces[0]-rolling[1]+rolling[0])*width/2-scrub)/inertia
        v+=acc*dt;w+=alpha*dt;yaw+=w*dt;x+=v*math.cos(yaw)*dt;y+=v*math.sin(yaw)*dt
        energy+=float(np.dot(forces,sides))*dt
        max_torque=max(max_torque,float(np.max(abs(forces)))*radius)
        if k%10==0:rows.append([t,x,y,yaw,v,w,forces[0],forces[1]])
    return np.array(rows),dict(final_speed_m_s=v,final_yaw_rate_rad_s=w,position_m=[x,y],yaw_rad=yaw,
        max_motor_torque_Nm=max_torque,motor_work_J=energy)


def slew_case(torque,overturn):
    # Conservative equivalent inertia; flat-floor operating case. The 5° slope
    # term is separately reported as a holding-torque requirement.
    dt=.002;inertia=.50;angle=omega=0.;rows=[];peak=0
    for k in range(42000):
        t=k*dt;target=math.radians(150 if t<30 else -150 if t<80 else 0)
        error=target-angle
        desired=np.clip(2*error,-math.radians(6),math.radians(6)) if t<80 else 0
        drive=np.clip(8*(desired-omega),-torque,torque)
        friction=.12*math.tanh(omega/.005)
        omega+=(drive-friction)/inertia*dt;angle+=omega*dt
        peak=max(peak,abs(angle))
        if k%25==0:rows.append([t,math.degrees(angle),math.degrees(omega),drive])
    return np.array(rows),dict(peak_angle_deg=math.degrees(peak),final_speed_deg_s=math.degrees(omega),
        commanded_speed_limit_deg_s=6,model_inertia_kg_m2=inertia,
        assumed_breakaway_friction_Nm=.12,available_torque_Nm=torque,
        holding_torque_on_5deg_slope_Nm=.12+overturn*math.sin(math.radians(5)))


def run():
    validation=json.loads((ROOT/'validation.json').read_text());loads=validation['loads'];m=loads['drive']['mass_including_payload_kg']
    reports={};traces={};failures=[]
    for name,left,right,slope,powerloss in [('forward',.08,.08,0,False),('reverse',-.08,-.08,0,False),
        ('pivot',-.05,.05,0,False),('grade_10deg',.08,.08,10,False),('power_loss_on_grade',.08,.08,10,True)]:
        trace,r=travel_case(m,left,right,slope,powerloss);traces[name]=trace;reports[name]=r
        run=trace[(trace[:,0]>2)&(trace[:,0]<2.9)]
        r['steady_speed_m_s']=float(run[:,4].mean());r['steady_yaw_rad_s']=float(run[:,5].mean())
        r['stop_distance_after_3s_m']=float(np.linalg.norm(trace[-1,1:3]-trace[300,1:3]))
        if not powerloss and abs(r['final_speed_m_s'])>.005:failures.append(name+' failed stop')
        if name=='pivot' and r['steady_yaw_rad_s']<.25:failures.append('pivot insufficient yaw')
        if name in ['forward','reverse','grade_10deg'] and abs(r['steady_speed_m_s']-left)>.01:failures.append(name+' speed error')
        if powerloss and r['final_speed_m_s']>=0:failures.append('power-loss negative control did not roll back')
        if r['max_motor_torque_Nm']>DRIVE_LIMIT_NM+1e-8:failures.append('drive torque exceeded the current limit')
    slew,sreport=slew_case(loads['slew']['available_output_torque_Nm'],loads['max_overturning_moment_Nm'])
    if sreport['peak_angle_deg']>150.1 or abs(sreport['final_speed_deg_s'])>.1:failures.append('slew limit/stop')
    # Conservative hub load: the whole half-machine weight on the sprocket, the idler on its
    # recoil stop (both strands at half the stop force) and the limited drive pull. The sprocket
    # sits over the 61808, so it carries all of it; the hub-gear mesh force adds on the same bearing.
    stop=tw.stop_state(tw.ADJUST_RANGE[1],tw.SPRING['rate_N_mm']*(1+tw.SPRING['rate_tolerance']))['force']
    pull=tw.drive_force_limit()['chain_pull_N'];mesh=DRIVE_LIMIT_NM/(tw.RING_TEETH*tw.GEAR_MODULE/2*math.cos(math.radians(tw.PRESSURE_ANGLE))*.001)
    radial=math.hypot(stop+pull,m*9.81/2+mesh*(1+13.1/23))
    c0=tw.BEARINGS['outboard']['C0_kN'][0]*1000
    bearing_report=dict(conservative_sprocket_radial_load_N=radial,idler_stop_force_N=stop,drive_pull_N=pull,mesh_force_N=mesh,
        bearing='61808-2RS1 (fixed) under the sprocket; 6809-2RS floating',static_rating_C0_N=c0,static_safety=c0/radial,
        housing_tube_bending_MPa=math.hypot(stop+pull,m*9.81/2)*45/(math.pi/64*(45**4-37.3**4))*22.5,
        scope='Quasi-static upper bound for the in-hub final drive (track_wheel/validation.json has the full load cases). Whole half-machine weight on the sprocket, idler on its recoil stop at +10 % spring rate, drive at the 1.0 A limit, mesh force carried by the same bearing.')
    if bearing_report['static_safety']<4 or bearing_report['housing_tube_bending_MPa']>10:failures.append('hub bearing or housing static margin')
    fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
    for name in ['forward','reverse','grade_10deg','power_loss_on_grade']:
        a=traces[name];axes[0,0].plot(a[:,0],a[:,4],label=name.replace('_',' '))
    axes[0,0].set(xlabel='Time (s)',ylabel='Forward speed (m/s)',title='Traction, braking and power-loss control');axes[0,0].legend(fontsize=8)
    a=traces['pivot'];axes[0,1].plot(a[:,0],np.degrees(a[:,3]));axes[0,1].set(xlabel='Time (s)',ylabel='Heading (degrees)',title='Opposed track commands')
    axes[1,0].plot(slew[:,0],slew[:,1]);axes[1,0].axhline(150,color='grey',ls='--');axes[1,0].axhline(-150,color='grey',ls='--');axes[1,0].set(xlabel='Time (s)',ylabel='Slew (degrees)',title='Working limits and controlled stop')
    axes[1,1].plot(slew[:,0],slew[:,3]);axes[1,1].set(xlabel='Time (s)',ylabel='Output torque (N m)',title='Slew torque demand')
    for ax in axes.flat:ax.grid(alpha=.2)
    fig.savefig(ROOT/'images/vehicle_dynamics.png',dpi=160);plt.close(fig)
    result=dict(status='PASS' if not failures else 'FAIL',failures=failures,travel=reports,slew=sreport,hub_bearings=bearing_report,
        scope='Reduced rigid-body differential traction with force/current saturation, Coulomb scrub and rolling loss. Flat floor is the operating assumption; grade cases test the model and reveal power-off rollback. Slew assumes a raised boom clear of the tracks, ideal gears and 0.50 kg m² equivalent inertia. Motor performance assumes a maintained regulated 12 V rail within the commissioned power budget. Not full terrain contact, motor thermal analysis or firmware validation.')
    (ROOT/'simulation/vehicle_dynamics.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2));return not failures

if __name__=='__main__':raise SystemExit(0 if run() else 1)

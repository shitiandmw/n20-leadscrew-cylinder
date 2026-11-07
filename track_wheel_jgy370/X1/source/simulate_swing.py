"""MuJoCo simulation of the X1 swing drive (turntable concept R3 issue 3). SI units.

Model
  * The whole machine stands on the ground: the lower (X1 chassis with both J9 tracks, CAD mass) is a free body on two
    track footprints with friction. The upper (T101 frame, motor, ARM60 stretched forward, and the body B1 with its
    steel-shot counterweight, battery and electronics, from build_body.py) turns on the RU66 (hinge) and can tilt on the hub joint
    (two hinges with the joint's estimated stiffness). Masses and inertias: ../simulation/turntable_mass_properties.json
    written by build_turntable.py.
  * Gear mesh X103/T105 (m1.5, 80:20): force along the line of action from the mesh error e = rb_p*phi - rb_R*theta,
    with a dead band of the normal backlash and the printed teeth's stiffness (PETG estimate).
  * JGY-370-1260 200:1 (the tracks' motor): straight torque-speed line through the vendor's no-load and stall points,
    driver current limit, short brake at zero command, rotor inertia; worm stage friction that makes it self-locking
    (forward efficiency from the stall data), output play as a dead band with the gearbox's torsional stiffness.
  * Drag pads: Coulomb friction on the swing hinge (MuJoCo frictionloss), plus the RU66's own friction.
Every number that is an assumption, not a datum, is listed in PARAMS['assumptions'] and in the report.

Cases (python simulate_swing.py [--case NAME]):
  start_stop_step / start_stop_ramp   90°-class swing at full command, stopped abruptly or with a 0.4 s ramp
  reverse_step / reverse_ramp         full speed one way, then the other
  knock_R3 / knock_R2_like / knock_no_pads   motor holding; a 10 N knock and a 4 Hz +-3 N shake at the bucket
  slope_hold                          on a 15° side slope, arm downhill-sideways, motor off: does the upper hold?
  stall_limit / stall_no_limit        bucket against a stiff obstacle at full command, 0.6 A driver limit / none
"""
import argparse, json, math, sys, time
from pathlib import Path
import numpy as np
import mujoco

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SIM = ROOT / 'simulation'
sys.path.insert(0, str(ROOT / 'swing_concept/source'))

DEG = math.pi/180

# ------------------------------------------------------------------ parameters
def params():
    import os
    mp = json.loads(Path(os.environ.get('SWING_MASS', SIM / 'turntable_mass_properties.json')).read_text())
    r3 = json.loads((ROOT / 'swing_concept/X1_swing_concept_R3_checks.json').read_text())     # drag-pad setting
    m, zr, zp, alpha = 1.5e-3, 80, 20, 20*DEG
    V, i_stall, i0, rpm0 = 12.0, 1.3, 0.1, 30.0
    N = 200.0
    R = V/i_stall
    w0 = rpm0*N*2*math.pi/60                          # motor no-load speed, rad/s
    Ke = (V - i0*R)/w0
    t_stall_out = 20*9.81/100                         # 20 kgf·cm
    eta_f = t_stall_out/(N*Ke*(i_stall - i0))         # worm + spur stages, forward
    p = dict(
        gear=dict(m=m, zr=zr, zp=zp, alpha=alpha, rb_R=m*zr/2*math.cos(alpha), rb_P=m*zp/2*math.cos(alpha),
                  r_P=m*zp/2, face=10e-3, lewis_Y=.32),
        mesh=dict(backlash_t=0.1e-3, k=1.3e6, zeta=.1),
        motor=dict(V=V, N=N, R=R, Ke=Ke, Kt=Ke, i0=i0, i_stall=i_stall, i_limit=0.6, J=5e-7, eta_f=eta_f,
                   f_worm=1/eta_f - 1, w0=w0),
        gearbox=dict(play_deg=1.5, k=200.0, zeta=.05),
        swing=dict(drag_Nm=r3['estimates']['drag']['torque_Nm'], bearing_Nm=0.02, damping=0.002),
        tilt=dict(k=4.4e4, zeta=.03),
        ground=dict(mu=.6, footprint=(0.24, 0.07), track_y=0.17),
        bucket_tip=[v/1000 for v in mp['bucket_tip_mm']],
        mass=mp,
        dt=5e-5,
        assumptions={
            'mesh stiffness 1.3e6 N/m': 'steel spur-gear mesh stiffness ~14 N/(um·mm) x 10 mm face, scaled by E_PETG/E_steel = 2/210',
            'mesh damping ratio 0.1, gearbox damping ratio 0.05, tilt damping ratio 0.03': 'typical structural values',
            'JGY-370 output play 1.5° (cases also at 1° and 2°)': 'vendor gives none; R3 assumed 1-2°',
            'gearbox torsional stiffness 200 N·m/rad at the output': 'Ø6 steel shaft and metal gear stages; estimate',
            'motor rotor inertia 5e-7 kg·m²': 'RS-370 class rotor, estimate (x200² = 0.02 kg·m² at the output)',
            'no-load current 0.1 A': 'inferred (J9/R1 current-limit estimates); torque taken as linear in current',
            'worm friction factor 1/eta_f - 1': f'from the stall point: eta_f = {eta_f:.3f} forward, so the stage is self-locking',
            'hub-joint tilt stiffness 4.4e4 N·m/rad': '8 x M4 at r 22.5 clamping 9 mm of PETG under Ø12 washers (E 2 GPa); bearing and frame taken rigid',
            f"drag {r3['estimates']['drag']['torque_Nm']:.2f} N·m, RU66 friction 0.02 N·m": 'R3 drag-pad setting (2 pads, Ø4.5 springs at ~7 N, felt μ 0.25 guessed); RU66 value is a guess for a lightly loaded cross-roller ring',
            'ground friction 0.6, footprints 240 x 70 mm per track': 'printed grousers on firm ground',
            'arm pose': 'ARM60 stretched forward (largest inertia), fixed; no payload',
        })
    return p


# ------------------------------------------------------------------ MJCF
def fullinertia(I):
    I = np.asarray(I)
    return f'{I[0,0]:.8g} {I[1,1]:.8g} {I[2,2]:.8g} {I[0,1]:.8g} {I[0,2]:.8g} {I[1,2]:.8g}'


def mjcf(p):
    up, low, pin = p['mass']['upper'], p['mass']['lower'], p['mass']['pinion']
    zb = 0.100                                         # bearing plane (turntable face)
    px = -0.075 - p['mesh']['backlash_t']/(2*math.tan(p['gear']['alpha']))
    cu = np.array(up['centre_m']) - [0, 0, zb]
    cp = np.array(pin['centre_m']) - [px, 0, zb]
    L, W = p['ground']['footprint']; ty = p['ground']['track_y']
    It = np.array(up['inertia_kgm2']); m_up = up['mass_kg']
    ktilt, z = p['tilt']['k'], p['tilt']['zeta']
    Itilt = It[0, 0] + m_up*(cu[1]**2 + cu[2]**2)
    ctilt = 2*z*math.sqrt(ktilt*Itilt)
    sw = p['swing']
    return f"""<mujoco model="X1_swing">
  <option timestep="{p['dt']}" integrator="implicitfast" gravity="0 0 -9.81"/>
  <worldbody>
    <geom name="ground" type="plane" size="2 2 .1" friction="{p['ground']['mu']} .005 .0001" solref=".004 1"/>
    <body name="lower" pos="0 0 0">
      <freejoint name="lower_free"/>
      <inertial pos="{' '.join(f'{v:.6g}' for v in low['centre_m'])}" mass="{low['mass_kg']:.6g}" fullinertia="{fullinertia(low['inertia_kgm2'])}"/>
      <geom name="track_L" type="box" pos="0 {ty} .005" size="{L/2} {W/2} .005" friction="{p['ground']['mu']} .005 .0001" solref=".004 1" mass="0"/>
      <geom name="track_R" type="box" pos="0 {-ty} .005" size="{L/2} {W/2} .005" friction="{p['ground']['mu']} .005 .0001" solref=".004 1" mass="0"/>
      <body name="hub" pos="0 0 {zb}">
        <joint name="roll" type="hinge" axis="1 0 0" stiffness="{ktilt}" damping="{ctilt:.6g}"/>
        <joint name="pitch" type="hinge" axis="0 1 0" stiffness="{ktilt}" damping="{ctilt:.6g}"/>
        <inertial pos="0 0 0" mass="0.001" diaginertia="1e-7 1e-7 1e-7"/>
        <body name="upper" pos="0 0 0">
          <joint name="swing" type="hinge" axis="0 0 1" frictionloss="{sw['drag_Nm'] + sw['bearing_Nm']}" damping="{sw['damping']}"/>
          <inertial pos="{' '.join(f'{v:.6g}' for v in cu)}" mass="{m_up:.6g}" fullinertia="{fullinertia(up['inertia_kgm2'])}"/>
          <site name="bucket" pos="{p['bucket_tip'][0]:.5f} 0 {p['bucket_tip'][2] - zb:.5f}"/>
          <body name="pinion" pos="{px:.6f} 0 0">
            <joint name="pinion" type="hinge" axis="0 0 1"/>
            <inertial pos="{cp[0]:.6g} {cp[1]:.6g} {cp[2]:.6g}" mass="{pin['mass_kg']:.6g}" diaginertia="{p['mass']['pinion_inertia_about_its_axis_kgm2']*0.6:.6g} {p['mass']['pinion_inertia_about_its_axis_kgm2']*0.6:.6g} {p['mass']['pinion_inertia_about_its_axis_kgm2']:.6g}"/>
          </body>
        </body>
      </body>
    </body>
  </worldbody>
</mujoco>
"""


# ------------------------------------------------------------------ drive models
class Drive:
    def __init__(self, p, i_limit=None, play_deg=None, backlash_t=None, drag=None):
        self.p = p
        mo = p['motor']
        self.i_limit = mo['i_limit'] if i_limit is None else i_limit
        self.play = (p['gearbox']['play_deg'] if play_deg is None else play_deg)*DEG
        bt = p['mesh']['backlash_t'] if backlash_t is None else backlash_t
        self.b = bt*math.cos(p['gear']['alpha'])/2        # half the normal backlash
        self.wm = 0.0; self.thm = 0.0                     # motor rotor speed and angle
        self.i = 0.0; self.F = 0.0; self.Tg = 0.0
        g = p['gear']
        Ip = p['mass']['pinion_inertia_about_its_axis_kgm2']
        mred = Ip/g['rb_P']**2
        self.cm = 2*p['mesh']['zeta']*math.sqrt(p['mesh']['k']*mred)
        self.cg = 2*p['gearbox']['zeta']*math.sqrt(p['gearbox']['k']*Ip)

    @staticmethod
    def deadband(x, h):
        return x - h if x > h else (x + h if x < -h else 0.0)

    def forces(self, th, thd, ph, phd):
        """Mesh force along the line of action (N) and gearbox torque on the pinion (N·m)."""
        g, me, gb = self.p['gear'], self.p['mesh'], self.p['gearbox']
        e = g['rb_P']*ph - g['rb_R']*th
        ed = g['rb_P']*phd - g['rb_R']*thd
        d = self.deadband(e, self.b)
        F = 0.0
        if d:
            F = me['k']*d + self.cm*ed
            F = max(F, 0.0) if d > 0 else min(F, 0.0)
        N = self.p['motor']['N']
        phs, phsd = self.thm/N, self.wm/N
        eps = phs - ph
        dg = self.deadband(eps, self.play/2)
        T = 0.0
        if dg:
            T = gb['k']*dg + self.cg*(phsd - phd)
            T = max(T, 0.0) if dg > 0 else min(T, 0.0)
        self.F, self.Tg = F, T
        return F, T

    def motor_step(self, u, dt):
        mo = self.p['motor']
        v = max(-1.0, min(1.0, u))*mo['V']
        i = (v - mo['Ke']*self.wm)/mo['R']
        i = max(-self.i_limit, min(self.i_limit, i))
        self.i = i
        Tm = mo['Kt']*i
        Ts = self.Tg/mo['N']                             # load torque at the worm, ideal
        Fw = mo['f_worm']*abs(Ts) + mo['Kt']*mo['i0']    # worm friction capacity (load-proportional) + no-load loss
        net = Tm - Ts
        if abs(self.wm) < 1e-6:
            if abs(net) <= Fw:
                self.wm = 0.0
                return
            acc = (net - Fw*math.copysign(1, net))/mo['J']
        else:
            acc = (net - Fw*math.copysign(1, self.wm))/mo['J']
        w = self.wm + acc*dt
        if self.wm and w*self.wm < 0:                    # friction cannot reverse the rotor: it sticks
            w = 0.0
        self.wm = w
        self.thm += w*dt


# ------------------------------------------------------------------ cases
def ramp_cmd(t, segs):
    """segs: list of (t_start, t_end, u_from, u_to); outside them the last value holds."""
    u = 0.0
    for t0, t1, a, b in segs:
        if t >= t1:
            u = b
        elif t >= t0:
            u = a + (b - a)*(t - t0)/(t1 - t0) if t1 > t0 else b
    return u


CASES = {
    'start_stop_step': dict(T=3.0, cmd=[(0.3, 0.3, 0, 1), (2.3, 2.3, 1, 0)], note='full command for 2 s, then zero (driver short brake), no ramps'),
    'start_stop_ramp': dict(T=3.0, cmd=[(0.3, 0.7, 0, 1), (2.3, 2.7, 1, 0)], note='the same with 0.4 s ramps (R3 driver setting)'),
    'reverse_step': dict(T=3.2, cmd=[(0.3, 0.3, 0, 1), (1.6, 1.6, 1, -1), (2.9, 2.9, -1, 0)], note='full speed one way, then full the other way'),
    'reverse_ramp': dict(T=3.6, cmd=[(0.3, 0.7, 0, 1), (1.6, 2.4, 1, -1), (2.9, 3.3, -1, 0)], note='the same with ramps (0.4 s per full command)'),
    'knock_R3': dict(T=3.0, knock=True, note='motor holding (zero command); 10 N for 20 ms at the bucket, then a ±3 N 4 Hz shake for 2 s; R3: 0.1 mm backlash, drag pads'),
    'knock_no_pads': dict(T=3.0, knock=True, drag=0.0, note='the same without the drag pads'),
    'knock_R2_like': dict(T=3.0, knock=True, drag=0.0, backlash=0.3e-3, note='R2-like: 0.3 mm printed backlash, no drag pads'),
    'knock_R3_play2deg': dict(T=3.0, knock=True, play=2.0, note='R3 with 2° gearbox play (upper end of the assumption)'),
    'slope_hold': dict(T=3.0, slope=15.0, note='15° side slope, arm pointing forward along the slope contour (gravity tries to swing it downhill), motor off'),
    'stall_limit': dict(T=2.0, cmd=[(0.3, 0.3, 0, 1)], wall=True, note='bucket swings into a rock (fixed in the world, 20 N/mm) after 5°, full command held; 0.6 A driver limit'),
    'stall_no_limit': dict(T=2.0, cmd=[(0.3, 0.3, 0, 1)], wall=True, ilim=10.0, note='the same without a current limit (motor stall current 1.3 A)'),
}


def run(name, p, rate=500):
    c = CASES[name]
    model = mujoco.MjModel.from_xml_string(mjcf(p))
    if 'drag' in c:
        model.dof_frictionloss[model.joint('swing').dofadr[0]] = c['drag'] + p['swing']['bearing_Nm']
    if c.get('slope'):
        s = c['slope']*DEG
        model.opt.gravity[:] = [0, -9.81*math.sin(s), -9.81*math.cos(s)]
    data = mujoco.MjData(model)
    dr = Drive(p, i_limit=c.get('ilim'), play_deg=c.get('play'), backlash_t=c.get('backlash'))
    js, jp = model.joint('swing'), model.joint('pinion')
    qs, qp, vs, vp = js.qposadr[0], jp.qposadr[0], js.dofadr[0], jp.dofadr[0]
    ratio = p['gear']['zr']/p['gear']['zp']
    if c.get('swing0'):
        a = c['swing0']*DEG
        data.qpos[qs] = a; data.qpos[qp] = a*ratio; dr.thm = a*ratio*p['motor']['N']
    mujoco.mj_forward(model, data)
    bucket = model.site('bucket').id; up = model.body('upper').id; low = model.body('lower').id
    dt = model.opt.timestep
    rt = p['bucket_tip']; r_tip = math.hypot(rt[0], rt[1])
    th_wall = None
    settle = 0.3                                       # the machine settles on the ground first (motor off)
    nstep = int((c['T'] + settle)/dt); every = int(1/(rate*dt))
    rec = {k: [] for k in ('t', 'u', 'swing_deg', 'bucket_mm', 'F_N', 'Tg_Nm', 'i_A', 'motor_rpm', 'roll_deg', 'pitch_deg', 'lower_xy_mm', 'lower_yaw_deg', 'ext_N')}
    x0 = None
    for k in range(nstep):
        t = k*dt - settle
        th, thd, ph, phd = data.qpos[qs], data.qvel[vs], data.qpos[qp], data.qvel[vp]
        F, Tg = dr.forces(th, thd, ph, phd)
        u = ramp_cmd(t, c['cmd']) if ('cmd' in c and t >= 0) else 0.0
        dr.motor_step(u, dt)
        data.qfrc_applied[:] = 0
        data.xfrc_applied[:] = 0
        g = p['gear']
        data.qfrc_applied[vs] += F*g['rb_R']
        data.qfrc_applied[vp] += -F*g['rb_P'] + Tg
        ext = 0.0
        if c.get('knock') and t >= 0:
            if 0.2 <= t < 0.22:
                ext = 10.0
            elif 0.6 <= t < 2.6:
                ext = 3.0*math.sin(2*math.pi*4*(t - 0.6))
        wall_f = None
        if c.get('wall') and t >= 0:
            pb = data.site_xpos[bucket]
            if th_wall is None:                          # a rock fixed in the world, 5° of swing ahead of the bucket
                R0 = data.xmat[up].reshape(3, 3)
                d0 = R0 @ np.array([-rt[1], rt[0], 0.0])/r_tip
                th_wall = (pb.copy(), d0, r_tip*5*DEG); pen_prev = 0.0
            p0, d0, s0 = th_wall
            pen = float((pb - p0) @ d0) - s0
            if pen > 0:
                f = 2.0e4*pen + 50.0*(pen - pen_prev)/dt
                if f > 0:
                    wall_f = -f*d0; ext = -f
            pen_prev = pen
        if wall_f is not None:
            mujoco.mj_applyFT(model, data, wall_f, np.zeros(3), data.site_xpos[bucket].copy(), up, data.qfrc_applied)
        elif ext:
            pos = data.site_xpos[bucket].copy()
            R = data.xmat[up].reshape(3, 3)
            tang = R @ np.array([-rt[1], rt[0], 0.0])/r_tip     # tangential (positive swing) direction at the bucket
            mujoco.mj_applyFT(model, data, ext*tang, np.zeros(3), pos, up, data.qfrc_applied)
        mujoco.mj_step(model, data)
        if t >= 0 and k % every == 0:
            if x0 is None:
                x0 = data.xpos[low].copy(); th0 = data.qpos[qs]
            q = data.xquat[low]
            yaw = math.atan2(2*(q[0]*q[3] + q[1]*q[2]), 1 - 2*(q[2]**2 + q[3]**2))
            rec['t'].append(round(t, 4)); rec['u'].append(u)
            rec['swing_deg'].append(data.qpos[qs]/DEG)
            rec['bucket_mm'].append((data.qpos[qs] - th0)*r_tip*1000)
            rec['F_N'].append(F); rec['Tg_Nm'].append(Tg); rec['i_A'].append(dr.i)
            rec['motor_rpm'].append(dr.wm*60/(2*math.pi)); rec['ext_N'].append(ext)
            rec['roll_deg'].append(data.qpos[model.joint('roll').qposadr[0]]/DEG)
            rec['pitch_deg'].append(data.qpos[model.joint('pitch').qposadr[0]]/DEG)
            rec['lower_xy_mm'].append(float(np.hypot(*(data.xpos[low][:2] - x0[:2]))*1000)); rec['lower_yaw_deg'].append(yaw/DEG)
    return rec, metrics(name, c, rec, p, dr, r_tip)


def metrics(name, c, rec, p, dr, r_tip):
    t = np.array(rec['t']); F = np.abs(np.array(rec['F_N'])); b = np.array(rec['bucket_mm'])
    g = p['gear']
    Fmax = float(F.max())
    lewis = Fmax*math.cos(g['alpha'])/(g['face']*g['m']*g['lewis_Y'])/1e6
    out = dict(case=name, note=c['note'], peak_tooth_force_N=round(Fmax, 1), peak_tooth_stress_MPa_lewis=round(lewis, 1),
               peak_gearbox_torque_Nm=round(float(np.abs(rec['Tg_Nm']).max()), 3), peak_current_A=round(float(np.abs(rec['i_A']).max()), 3),
               peak_tilt_deg=round(float(max(np.abs(rec['roll_deg']).max(), np.abs(rec['pitch_deg']).max())), 4),
               lower_slide_mm=round(float(max(rec['lower_xy_mm'])), 2), lower_yaw_deg=round(float(np.abs(rec['lower_yaw_deg']).max()), 3),
               swing_total_deg=round(float(rec['swing_deg'][-1] - rec['swing_deg'][0]), 2))
    # contact changes in the mesh: each entry into contact after a free flight is an impact
    inc = (F > 1.0).astype(int)
    out['mesh_impacts'] = int(((inc[1:] - inc[:-1]) == 1).sum())
    cmd = c.get('cmd')
    if cmd and name.startswith('start_stop'):
        t_stop = cmd[-1][1]
        after = t >= t_stop
        bs = b[after]
        out['bucket_travel_after_stop_mm'] = round(float(bs.max() - bs[0]), 2)
        final = bs[-1]
        osc = np.abs(bs - final)
        tt = t[after]
        out['bucket_overshoot_mm'] = round(float(bs.max() - final), 2)
        idx = np.where(osc > 0.5)[0]
        out['settle_time_s_to_0.5mm'] = round(float(tt[idx[-1]] - tt[0]) if len(idx) else 0.0, 3)
        out['peak_tooth_force_at_stop_N'] = round(float(F[after].max()), 1)
        out['swing_speed_rpm_steady'] = round(float(np.gradient(rec['swing_deg'], t)[(t > cmd[0][1] + .5) & (t < cmd[-1][0])].mean())/6, 2)
    if name.startswith('reverse'):
        t_rev0, t_rev1 = cmd[1][0], cmd[1][1]
        win = (t >= t_rev0) & (t <= t_rev1 + .6)
        free = (F[win] <= 1.0)
        out['no_contact_time_during_reversal_s'] = round(float(free.sum()*(t[1] - t[0])), 3)
        out['peak_tooth_force_at_reversal_N'] = round(float(F[win].max()), 1)
    if c.get('knock'):
        s = (t >= .6) & (t <= 2.6)
        out['bucket_wobble_pp_mm_during_shake'] = round(float(b[s].max() - b[s].min()), 2)
        out['bucket_shift_after_knock_mm'] = round(float(b[(t > .3) & (t < .6)].mean() - b[t < .2].mean()), 2)
        out['mesh_impacts_during_shake'] = int(((inc[1:][s[1:]] - inc[:-1][s[1:]]) == 1).sum())
    if c.get('slope'):
        out['upper_drift_deg'] = round(float(rec['swing_deg'][-1] - rec['swing_deg'][0]), 3)
        out['bucket_drift_mm'] = round(float(b[-1] - b[0]), 2)
        out['holds'] = bool(abs(out['upper_drift_deg']) < 1.0)
    if c.get('wall'):
        out['static_tooth_force_at_stall_N'] = round(float(F[t > t[-1] - .3].mean()), 1)
        out['static_stress_at_stall_MPa_lewis'] = round(out['static_tooth_force_at_stall_N']*math.cos(g['alpha'])/(g['face']*g['m']*g['lewis_Y'])/1e6, 1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--case', default='all')
    a = ap.parse_args()
    p = params()
    names = list(CASES) if a.case == 'all' else [a.case]
    SIM.mkdir(exist_ok=True)
    (SIM / 'turntable_swing_model.xml').write_text(mjcf(p))
    results, traces = {}, {}
    for n in names:
        t0 = time.time()
        rec, m = run(n, p)
        m['wall_s'] = round(time.time() - t0, 1)
        results[n] = m; traces[n] = {k: [round(float(v), 5) for v in vals] for k, vals in rec.items()}
        print(json.dumps(m), flush=True)
    mo = p['motor']
    pub = dict(gear={k: v for k, v in p['gear'].items()}, mesh=p['mesh'], gearbox=p['gearbox'], swing=p['swing'], tilt=p['tilt'], ground=p['ground'],
               motor={k: round(v, 6) for k, v in mo.items()}, dt=p['dt'], bucket_tip_m=p['bucket_tip'],
               upper_mass_kg=p['mass']['upper']['mass_kg'], upper_inertia_about_swing_axis_kgm2=p['mass']['upper_inertia_about_swing_axis_kgm2'],
               lower_mass_kg=p['mass']['lower']['mass_kg'], reflected_rotor_inertia_at_turntable_kgm2=mo['J']*(mo['N']*4)**2,
               assumptions=p['assumptions'])
    rep = SIM / 'turntable_swing_report.json'
    old = json.loads(rep.read_text())['cases'] if rep.exists() and a.case != 'all' else {}
    rep.write_text(json.dumps(dict(model='MuJoCo ' + mujoco.__version__, parameters=pub, cases={**old, **results}), indent=1, ensure_ascii=False) + '\n')
    tr = SIM / 'turntable_swing_traces.json'
    oldt = json.loads(tr.read_text()) if tr.exists() and a.case != 'all' else {}
    tr.write_text(json.dumps({**oldt, **traces}, separators=(',', ':')))


if __name__ == '__main__':
    main()

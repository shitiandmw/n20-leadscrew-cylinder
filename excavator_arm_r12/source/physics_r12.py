"""R12 rigid-body dynamics in MuJoCo with four independent V6-U60 drives.

Model
  - Fixed base. Boom, stick, bucket, side links (one body, both plates), H-link (both plates) and,
    for every drive, a barrel on a hinge at its rear pin and a rod on a slide. Masses, centres of
    mass and inertias come from the CAD (../simulation/mass_properties.json).
  - Loops are closed by site-to-site pin constraints: each rod eye to its pin (B left and right, D,
    R) and the H-link to the bucket at Q.
  - Each drive is a DC-motor line along its slide: F = F_stall (u - v / v_no-load), u in [-1, 1].
    The 12 V N20 1:50 on an M4 x 0.7 leadscrew (actuator_v6 rev 6.2) at the X1's 11.1 V nominal,
    through the V6 board's Schottky and 1.7 ohm, as in excavator_app/shared/drives.js: F_stall 158 N
    at zero speed, v_no-load 8.17 mm/s, clamped at the 55 N continuous (fuse hold) rating. The
    rotor inertia reflected through the gearbox and the 0.7 mm lead is a slide armature of
    tau * F_stall / v_no-load (tau = 20 ms assumed), about 390 kg: without it the 7 g rod against
    the motor's back-EMF line is numerically unstable.
  - Each drive has its own stroke feedback: u = v_ref / v0 + Kp e + Ki integral(e). The boom pair
    gets one shared reference and two separate controllers.

Scenarios (python physics_r12.py <name> | all)
  payload_150g   dig cycle with 150 g in the bucket
  unloaded       the same cycle, empty
  hold           static hold at each drive's worst pose (design_check.json), 150 g, compared with
                 an independent virtual-work calculation using the same CAD masses
  sync_bias      boom pair at its worst pose with a 0.5 mm feedback-zero error on one drive
  half_step      first 160 s of the loaded cycle at half the timestep (convergence)

Writes ../simulation/<scenario>_report.json, <scenario>_trace.json.gz, arm_r12.xml, validation.json
"""
import sys
import json
import gzip
import math
import time
import numpy as np
import mujoco
import r12_design as d
import motion_r12 as M
from poses_r12 import DRIVES, DRIVE_AXIS, BODIES, body_poses

ROOT = d.rc.ROOT
SIM = ROOT / 'simulation'
MASS = json.loads((SIM / 'mass_properties.json').read_text())['bodies']
MM = 1e-3
F_STALL, V0, F_FUSE = 158.0, 8.17e-3, d.ACT['thrust_cont']   # N, m/s, N
MOTOR_TAU = 0.020                                    # s, assumed N20 mechanical time constant
SLIDE_ARMATURE = MOTOR_TAU * F_STALL / V0            # kg: rotor inertia reflected through gearbox and 0.7 mm lead
KP, KI = 2.0 / MM, 1.0 / MM                          # u per m, u per m s
DT = 1e-3
G = 9.81
PAYLOAD_KG = d.PAYLOAD
PAYLOAD_COM = np.asarray(d.MASS['payload'][1], float)


def _v(x):
    return ' '.join(f'{float(a):.9g}' for a in x)


def inertial(body):
    m = MASS[body]
    c = np.array(m['com_mm']) * MM
    I = np.array(m['inertia_kg_mm2']) * 1e-6
    I = 0.5 * (I + I.T) + 1e-12 * np.eye(3)
    return (f'<inertial pos="{_v(c)}" mass="{m["mass_kg"]:.9g}" '
            f'fullinertia="{_v([I[0, 0], I[1, 1], I[2, 2], I[0, 1], I[0, 2], I[1, 2]])}"/>')


def xz(p, y=0.0):
    return np.array([p[0] * MM, y * MM, p[1] * MM])


def drive_xml(name, pos_mm, yc):
    rod_eye = xz((d.ACT['closed'], 0.0), yc)
    return (f'<body name="{name}_barrel" pos="{_v(xz(pos_mm))}">{inertial(name + "_barrel")}'
            f'<joint name="{name}_barrel_hinge" type="hinge" axis="0 -1 0"/>'
            f'<body name="{name}_rod">{inertial(name + "_rod")}'
            f'<joint name="{name}_slide" type="slide" axis="1 0 0" range="-0.002 0.063" limited="true" armature="{SLIDE_ARMATURE:.6g}"/>'
            f'<site name="{name}_eye" pos="{_v(rod_eye)}" size="0.002"/></body></body>')


def model_xml(payload=True, timestep=DT):
    pay = (f'<body name="payload" pos="{_v(xz(PAYLOAD_COM))}"><inertial pos="0 0 0" mass="{PAYLOAD_KG}" '
           f'diaginertia="1e-5 1e-5 1e-5"/></body>') if payload else ''
    bucket = (f'<body name="bucket" pos="{_v(xz(d.H_S))}">{inertial("bucket")}'
              f'<joint name="bucket_hinge" type="hinge" axis="0 -1 0"/>'
              f'<site name="Q_bucket" pos="{_v(xz(d.Q_K))}" size="0.002"/>'
              f'<site name="tip" pos="{_v(xz(d.T_K))}" size="0.002"/>{pay}</body>')
    side = (f'<body name="side_link" pos="{_v(xz(d.J_S))}">{inertial("side_link")}'
            f'<joint name="side_link_hinge" type="hinge" axis="0 -1 0"/>'
            f'<site name="R_side" pos="{_v(xz((d.SIDE_LINK, 0.0)))}" size="0.002"/>'
            f'<body name="h_link" pos="{_v(xz((d.SIDE_LINK, 0.0)))}">{inertial("h_link")}'
            f'<joint name="h_link_hinge" type="hinge" axis="0 -1 0"/>'
            f'<site name="Q_hlink" pos="{_v(xz((d.H_LINK, 0.0)))}" size="0.002"/></body></body>')
    stick = (f'<body name="stick" pos="{_v(xz(d.E_B))}">{inertial("stick")}'
             f'<joint name="stick_hinge" type="hinge" axis="0 -1 0"/>'
             f'<site name="D_stick" pos="{_v(xz(d.D_S))}" size="0.002"/>'
             f'{bucket}{side}{drive_xml("bucket", d.F_S, 0.0)}</body>')
    boom = (f'<body name="boom" pos="0 0 0">{inertial("boom")}'
            f'<joint name="boom_hinge" type="hinge" axis="0 -1 0"/>'
            f'<site name="B_boom_L" pos="{_v(xz(d.B_B, d.Y["boom_cyl"]))}" size="0.002"/>'
            f'<site name="B_boom_R" pos="{_v(xz(d.B_B, -d.Y["boom_cyl"]))}" size="0.002"/>'
            f'{stick}{drive_xml("stick", d.C_B, 0.0)}</body>')
    world = boom + drive_xml('boom_L', d.A_W, d.Y['boom_cyl']) + drive_xml('boom_R', d.A_W, -d.Y['boom_cyl'])
    eq = ''.join(f'<connect site1="{a}" site2="{b}" solref="0.002 1" solimp="0.99 0.999 0.0001"/>' for a, b in
                 [('boom_L_eye', 'B_boom_L'), ('boom_R_eye', 'B_boom_R'), ('stick_eye', 'D_stick'),
                  ('bucket_eye', 'R_side'), ('Q_hlink', 'Q_bucket')])
    motors = ''.join(f'<general name="{n}_drive" joint="{n}_slide" gaintype="fixed" gainprm="{F_STALL}" biastype="affine" '
                     f'biasprm="0 0 {-F_STALL / V0}" ctrllimited="true" ctrlrange="-1 1" forcelimited="true" '
                     f'forcerange="{-F_FUSE} {F_FUSE}"/>' for n, *_ in DRIVES)
    return (f'<mujoco model="R12_excavator_arm"><compiler angle="radian" autolimits="true"/>'
            f'<option timestep="{timestep}" gravity="0 0 {-G}" integrator="implicitfast" solver="Newton" iterations="100" '
            f'tolerance="1e-10"/><default><joint armature="1e-6" damping="1e-5"/></default>'
            f'<worldbody>{world}</worldbody><equality>{eq}</equality><actuator>{motors}</actuator></mujoco>')


def initial_qpos(m, strokes):
    s, poses = body_poses(strokes)
    ang = {k: v[1] for k, v in poses.items()}
    q = dict(boom_hinge=ang['boom'], stick_hinge=ang['stick'] - ang['boom'], bucket_hinge=ang['bucket'] - ang['stick'],
             side_link_hinge=ang['side_link'] - ang['stick'], h_link_hinge=ang['h_link'] - ang['side_link'])
    parent = dict(base=0.0, boom=ang['boom'], stick=ang['stick'])
    for n, a, b, yc, board, pb in DRIVES:
        q[f'{n}_barrel_hinge'] = ang[f'{n}_barrel'] - parent[pb]
        L = float(np.linalg.norm(s['pins'][b] - s['pins'][a]))
        q[f'{n}_slide'] = (L - d.ACT['closed']) * MM
    out = np.zeros(m.nq)
    for j, v in q.items():
        out[m.joint(j).qposadr[0]] = v
    return out


class Arm:
    def __init__(self, payload=True, timestep=DT, bias=None):
        self.xml = model_xml(payload, timestep)
        self.m = mujoco.MjModel.from_xml_string(self.xml)
        self.d = mujoco.MjData(self.m)
        self.slides = [self.m.joint(f'{n}_slide').qposadr[0] for n, *_ in DRIVES]
        self.slide_dofs = [self.m.joint(f'{n}_slide').dofadr[0] for n, *_ in DRIVES]
        self.bias = np.zeros(4) if bias is None else np.asarray(bias, float)
        self.integ = np.zeros(4)
        self.body_ids = {b: self.m.body(b).id for b in BODIES if b != 'base'}

    def reset(self, strokes):
        mujoco.mj_resetData(self.m, self.d)
        self.d.qpos[:] = initial_qpos(self.m, strokes)
        mujoco.mj_forward(self.m, self.d)
        self.integ[:] = 0

    def strokes(self):
        return np.array([self.d.qpos[i] for i in self.slides]) / MM

    def control(self, ref, rate):
        s = self.strokes() + self.bias                    # what each drive's feedback reads
        r = np.array([ref[DRIVE_AXIS[n]] for n, *_ in DRIVES])
        v = np.array([rate[DRIVE_AXIS[n]] for n, *_ in DRIVES])
        e = (r - s) * MM
        u = v * MM / V0 + KP * e + KI * self.integ
        sat = np.abs(u) >= 1.0
        self.integ += np.where(sat & (np.sign(u) == np.sign(e)), 0.0, e) * self.m.opt.timestep
        self.d.ctrl[:] = np.clip(u, -1, 1)
        return r, e / MM

    def forces(self):
        return np.array(self.d.actuator_force)

    def closure_error_mm(self):
        err = 0.0
        for a, b in [('boom_L_eye', 'B_boom_L'), ('boom_R_eye', 'B_boom_R'), ('stick_eye', 'D_stick'),
                     ('bucket_eye', 'R_side'), ('Q_hlink', 'Q_bucket')]:
            pa, pb = self.d.site(a).xpos, self.d.site(b).xpos
            err = max(err, float(np.linalg.norm((pa - pb)[[0, 2]])) / MM)
        return err

    def pose_record(self):
        out = []
        for b, i in self.body_ids.items():
            p = self.d.xpos[i]
            R = self.d.xmat[i].reshape(3, 3)
            out += [round(float(p[0] / MM), 3), round(float(p[2] / MM), 3), round(math.atan2(R[2, 0], R[0, 0]), 6)]
        return out

    def tip(self):
        p = self.d.site('tip').xpos
        return np.array([p[0], p[2]]) / MM

    def tip_expected(self):
        return d.solve(tuple(self.strokes()[[0, 2, 3]]))['pins']['T']


# ------------------------------------------------------------------ independent static check
def static_forces(strokes, payload=True, h=0.05):
    """Drive forces from virtual work with the CAD masses (no MuJoCo): F_i = dV / ds_i. Boom value is
    per drive (two share it)."""
    def V(st):
        _, poses = body_poses(st)
        e = 0.0
        for b, mp in MASS.items():
            if b == 'base':
                continue
            (ox, oz), a = poses[b]
            c = np.array(mp['com_mm'])
            e += mp['mass_kg'] * G * (oz + math.sin(a) * c[0] + math.cos(a) * c[2])
        if payload:
            (ox, oz), a = poses['bucket']
            e += PAYLOAD_KG * G * (oz + math.sin(a) * PAYLOAD_COM[0] + math.cos(a) * PAYLOAD_COM[1])
        return e * MM
    out = []
    for i in range(3):
        p, m = list(strokes), list(strokes)
        p[i] = min(60.0, p[i] + h)
        m[i] = max(0.0, m[i] - h)
        out.append((V(p) - V(m)) / ((p[i] - m[i]) * MM) / (2 if i == 0 else 1))
    return out


# ------------------------------------------------------------------ runs
def run_cycle(name, payload=True, timestep=DT, t_end=None, bias=None, record_hz=10):
    arm = Arm(payload, timestep, bias)
    t_end = M.DURATION if t_end is None else t_end
    s0, _ = M.reference(0.0)
    arm.reset(tuple(s0))
    n = int(round(t_end / timestep))
    every = max(1, int(round(1.0 / record_hz / timestep)))
    rec, peak, worst_e, worst_c, worst_tip, sat_steps = [], np.zeros(4), 0.0, 0.0, 0.0, 0
    fmax_pos, fmax_neg = np.zeros(4), np.zeros(4)
    t0 = time.time()
    for k in range(n + 1):
        t = k * timestep
        ref, rate = M.reference(t)
        r, e = arm.control(ref, rate)
        if k:
            mujoco.mj_step(arm.m, arm.d)
        f = arm.forces()
        if t > 1.0:                                  # after the initial settling second
            peak = np.maximum(peak, np.abs(f))
            fmax_pos, fmax_neg = np.maximum(fmax_pos, f), np.minimum(fmax_neg, f)
            worst_e = max(worst_e, float(np.max(np.abs(arm.strokes() - r))))
            sat_steps += int(np.any(np.abs(f) >= F_FUSE - 1e-6))
        if k % every == 0:
            c = arm.closure_error_mm()
            worst_c = max(worst_c, c)
            tp = arm.tip()
            worst_tip = max(worst_tip, float(np.linalg.norm(tp - arm.tip_expected())))
            rec.append(dict(t=round(t, 3), s=np.round(arm.strokes(), 4).tolist(), r=np.round(r, 4).tolist(),
                            f=np.round(f, 3).tolist(), u=np.round(arm.d.ctrl, 4).tolist(), tip=np.round(tp, 2).tolist(),
                            pose=arm.pose_record(), c=round(c, 5)))
    names = [n for n, *_ in DRIVES]
    rep = dict(scenario=name, payload_kg=PAYLOAD_KG if payload else 0.0, timestep_s=timestep, simulated_s=round(t_end, 2),
               wall_s=round(time.time() - t0, 1), drive_model=dict(F_stall_N=F_STALL, v_no_load_mm_s=V0 / MM, slide_armature_kg=round(SLIDE_ARMATURE, 1),
                                                                  force_clamp_N=F_FUSE, Kp_per_mm=KP * MM, Ki_per_mm_s=KI * MM),
               feedback_bias_mm=dict(zip(names, (arm.bias if bias is not None else np.zeros(4)).tolist())),
               peak_force_N=dict(zip(names, np.round(peak, 2).tolist())),
               max_push_N=dict(zip(names, np.round(fmax_pos, 2).tolist())),
               max_pull_N=dict(zip(names, np.round(fmax_neg, 2).tolist())),
               time_at_force_clamp_s=round(sat_steps * timestep, 3),
               max_stroke_tracking_error_mm=round(worst_e, 4), max_pin_closure_error_mm=round(worst_c, 5),
               max_tip_vs_kinematics_mm=round(worst_tip, 4),
               final_strokes_mm=np.round(arm.strokes(), 3).tolist())
    rep['pass'] = bool(rep['time_at_force_clamp_s'] == 0 and worst_e < 0.5 and worst_c < 0.05 and worst_tip < 0.5)
    trace = dict(scenario=name, drives=names, bodies=list(arm.body_ids), record_hz=record_hz, frames=rec)
    return rep, trace


def run_hold(name='hold', bias=None, poses=None, t_hold=20.0):
    """Hold static poses; mean drive force over the last 5 s vs the virtual-work estimate."""
    chk = json.loads((ROOT / 'design_check.json').read_text())
    poses = poses or {k: tuple(v) for k, v in chk['worst_pose'].items()}
    out, traces = {}, []
    for label, st in poses.items():
        arm = Arm(True, DT, bias)
        arm.reset(st)
        n = int(t_hold / DT)
        acc, cnt = np.zeros(4), 0
        for k in range(n):
            arm.control(np.array(st), np.zeros(3))
            mujoco.mj_step(arm.m, arm.d)
            if k * DT > t_hold - 5:
                acc += arm.forces()
                cnt += 1
        f = acc / cnt
        vw = static_forces(st)
        names = [n for n, *_ in DRIVES]
        out[label] = dict(strokes_mm=list(st), mujoco_force_N=dict(zip(names, np.round(f, 2).tolist())),
                          virtual_work_N=dict(boom_each=round(vw[0], 2), stick=round(vw[1], 2), bucket=round(vw[2], 2)),
                          boom_pair_sum_N=round(float(f[0] + f[1]), 2),
                          stroke_error_mm=np.round(arm.strokes() - np.array([st[0], st[0], st[1], st[2]]), 4).tolist(),
                          residual_boom_moment_Nm=round(float(f[0] - f[1]) * d.Y['boom_cyl'] * MM, 4))
    return dict(scenario=name, payload_kg=PAYLOAD_KG, feedback_bias_mm=None if bias is None else list(bias), poses=out)


def main(which):
    SIM.mkdir(exist_ok=True)
    (SIM / 'arm_r12.xml').write_text(model_xml(True))
    todo = ['payload_150g', 'unloaded', 'hold', 'sync_bias', 'half_step'] if which == 'all' else [which]
    for sc in todo:
        t0 = time.time()
        if sc == 'payload_150g':
            rep, tr = run_cycle(sc, True)
        elif sc == 'unloaded':
            rep, tr = run_cycle(sc, False)
        elif sc == 'half_step':
            rep, tr = run_cycle(sc, True, DT / 2, t_end=160.0)
            base, _ = run_cycle('payload_160s', True, DT, t_end=160.0)
            rep['compare_full_step'] = dict(peak_force_N=base['peak_force_N'],
                                            max_peak_difference_N=round(max(abs(rep['peak_force_N'][k] - base['peak_force_N'][k])
                                                                            for k in rep['peak_force_N']), 4))
            tr = None
        elif sc == 'hold':
            rep, tr = run_hold(), None
        elif sc == 'sync_bias':
            chk = json.loads((ROOT / 'design_check.json').read_text())
            rep = run_hold('sync_bias_0p5mm', bias=[0.5, 0, 0, 0], poses={'boom': tuple(chk['worst_pose']['boom'])})
            tr = None
        (SIM / f'{sc}_report.json').write_text(json.dumps(rep, indent=1))
        if tr:
            (SIM / f'{sc}_trace.json.gz').write_bytes(gzip.compress(json.dumps(tr, separators=(',', ':')).encode()))
        print(sc, f'{time.time() - t0:.1f} s', json.dumps({k: v for k, v in rep.items() if k not in ('poses',)})[:900], flush=True)
        if sc in ('hold', 'sync_bias'):
            print(json.dumps(rep['poses'], indent=1))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'all')

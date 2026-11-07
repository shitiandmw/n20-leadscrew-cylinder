"""X1 turntable swing simulation report: ../X1_turntable_simulation.pdf (+ page PNGs in ../images).

Reads ../simulation/turntable_swing_report.json and _traces.json (simulate_swing.py) and ../turntable_validation.json
(build_turntable.py). One y-axis per chart; series colours follow the case, never the rank.
"""
import json, textwrap
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SIM = ROOT / 'simulation'
PDF = ROOT / 'X1_turntable_simulation.pdf'
BODY = json.loads((ROOT / 'simulation/body_mass_properties.json').read_text())
FIG = (16.5, 11.7)
INK, INK2, MUTED, GRID = '#0b0b0b', '#52514e', '#8a8984', '#e4e3df'
S1, S2, S3 = '#2a78d6', '#eb6834', '#1baf7a'          # categorical slots 1-3 (validated all-pairs)
REF = '#c0392b'
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': MUTED, 'axes.labelcolor': INK2, 'xtick.color': INK2, 'ytick.color': INK2,
                     'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': .6,
                     'axes.titleweight': 'bold', 'axes.titlesize': 10.5, 'axes.titlelocation': 'left', 'legend.frameon': False})


def wrap(s, n):
    return '\n'.join(textwrap.fill(p, n) for p in s.split('\n'))


def header(fig, n, title, sub):
    fig.text(.03, .965, f'X1 turntable swing simulation  —  page {n}: {title}', fontsize=16, weight='bold', color=INK)
    fig.text(.03, .943, sub, fontsize=9.4, color=INK2)


def line(ax, tr, key, color, label, scale=1.0, end_label=True):
    y = [v*scale for v in tr[key]]
    ax.plot(tr['t'], y, color=color, lw=1.6, label=label)
    if end_label:
        ax.annotate(label, (tr['t'][-1], y[-1]), xytext=(4, 0), textcoords='offset points', color=INK2, fontsize=8, va='center')


def table(fig, x, y, rows, widths, fs=8.2, dy=.0165):
    for i, r in enumerate(rows):
        xx = x
        for c, w in zip(r, widths):
            fig.text(xx, y, str(c), fontsize=fs, color=INK if i == 0 else INK2, weight='bold' if i == 0 else 'normal', va='top')
            xx += w
        y -= dy
    return y


def page1(pdf, rep, val):
    fig = plt.figure(figsize=FIG)
    P, C = rep['parameters'], rep['cases']
    header(fig, 1, 'model and results', f"{rep['model']}. Whole machine on the ground; X1 CAD masses (build_turntable.py); "
           'the turntable as drawn in concept R3 issue 3. Estimates for design decisions, not a test.')
    mo = P['motor']
    model = [
        ('Bodies', f"lower {P['lower_mass_kg']:.2f} kg (X1 chassis, both J9 tracks) free on two 240 x 70 mm track footprints, μ {P['ground']['mu']}; "
                   f"upper {P['upper_mass_kg']:.2f} kg on the RU66 (I {P['upper_inertia_about_swing_axis_kgm2']:.3f} kg·m² about the swing axis), "
                   'tilting on the hub joint; pinion on its own hinge.'),
        ('Upper', 'T101, T104, T102, motor, hardware and the ARM60 stretched forward from CAD; the body B1 from its CAD (build_body.py): '
                  f"3 PETG prints, {BODY['shot']['kg']:.2f} kg of steel shot (the upper's CG on the swing axis), battery, electronics, fixings."),
        ('Gear mesh', f"m1.5, 80 : 20; force along the line of action with a dead band of the 0.1 mm set backlash; "
                      f"PETG tooth stiffness {P['mesh']['k']/1e6:.1f} N/µm (estimate)."),
        ('Swing motor', f"JGY-370-1260 12 V 200:1, the tracks' motor: no-load 30 rpm, stall 1.96 N·m at {mo['i_stall']} A; "
                        f"forward efficiency {mo['eta_f']:.2f} from the stall point, so the worm is self-locking; driver limit {mo['i_limit']} A, "
                        f"short brake at zero command; gearbox play {P['gearbox']['play_deg']}°, {P['gearbox']['k']:.0f} N·m/rad."),
        ('Friction', f"drag pads {P['swing']['drag_Nm']:.2f} N·m + RU66 {P['swing']['bearing_Nm']} N·m on the swing hinge (Coulomb)."),
        ('Reflected', f"the motor rotor through 800 : 1 adds {P['reflected_rotor_inertia_at_turntable_kgm2']:.2f} kg·m² at the turntable."),
    ]
    y = .905
    fig.text(.03, y, 'Model', fontsize=11.5, weight='bold', color=INK, va='top'); y -= .026
    for k, v in model:
        fig.text(.03, y, k, fontsize=8.6, weight='bold', color=INK, va='top')
        t = wrap(v, 108)
        fig.text(.105, y, t, fontsize=8.6, color=INK2, va='top', linespacing=1.3)
        y -= .0155*(t.count('\n') + 1) + .006
    y -= .012
    fig.text(.03, y, 'Results', fontsize=11.5, weight='bold', color=INK, va='top'); y -= .026
    rows = [('Case', 'Peak tooth force', 'Lewis stress', 'Peak current', 'What it shows')]
    def what(n, c):
        if n.startswith('start_stop'):
            return f"bucket runs on {c['bucket_travel_after_stop_mm']} mm after the stop; settles in {c['settle_time_s_to_0.5mm']} s; {c['swing_speed_rpm_steady']} rpm"
        if n.startswith('reverse'):
            return f"no tooth contact for {c['no_contact_time_during_reversal_s']} s while reversing"
        if n.startswith('knock'):
            return f"bucket wobble {c['bucket_wobble_pp_mm_during_shake']} mm p-p; {c['mesh_impacts_during_shake']} tooth impacts in the shake"
        if n == 'slope_hold':
            return f"upper drifts {c['upper_drift_deg']}° ({c['bucket_drift_mm']} mm at the bucket): {'holds' if c['holds'] else 'does NOT hold'}"
        if n.startswith('stall'):
            return f"held against the rock: {c['static_tooth_force_at_stall_N']} N, {c['static_stress_at_stall_MPa_lewis']} MPa"
        return ''
    for n, c in C.items():
        rows.append((n.replace('_', ' '), f"{c['peak_tooth_force_N']:.0f} N", f"{c['peak_tooth_stress_MPa_lewis']:.0f} MPa",
                     f"{c['peak_current_A']:.2f} A", what(n, c)))
    y = table(fig, .03, y, rows, (.13, .085, .07, .07, .5))
    sl0 = C['stall_limit']
    fig.text(.03, y - .004, wrap('Lewis bending on the 20-tooth pinion, 10 wide (form factor 0.32). Printed PETG yields at about 50 MPa '
                                 f"(255 N on a tooth). R3's hand estimate for a held stall at 0.6 A was about 11 MPa (55 N); the simulation gives "
                                 f"{sl0['static_tooth_force_at_stall_N']:.0f} N ({sl0['static_stress_at_stall_MPa_lewis']:.0f} MPa) once the impact has died away.", 150),
             fontsize=7.8, color=MUTED, va='top')
    # conclusions
    cs = C
    st, sr = cs['start_stop_step'], cs['start_stop_ramp']
    kr, kn, k2 = cs['knock_R3'], cs['knock_no_pads'], cs['knock_R2_like']
    sl, snl = cs['stall_limit'], cs['stall_no_limit']
    concl = [
        ('1', f"The speed ramp is essential. Stopping dead from full speed puts {st['peak_tooth_force_N']:.0f} N on a pinion tooth "
              f"({st['peak_tooth_stress_MPa_lewis']:.0f} MPa, {st['peak_tooth_stress_MPa_lewis']/50:.0%} of PETG's yield), because the self-locking worm stops the motor side at once and "
              f"the upper's inertia runs into the teeth; the bucket swings on {st['bucket_travel_after_stop_mm']} mm. With the 0.4 s ramp: "
              f"{sr['peak_tooth_force_N']:.0f} N and {sr['bucket_travel_after_stop_mm']} mm."),
        ('2', f"Reversing at full command is as hard on the teeth ({cs['reverse_step']['peak_tooth_force_N']:.0f} N); ramped through zero, "
              f"{cs['reverse_ramp']['peak_tooth_force_N']:.0f} N."),
        ('3', f"Held still and shaken at the bucket, R3 wobbles {kr['bucket_wobble_pp_mm_during_shake']} mm p-p with "
              f"{kr['mesh_impacts_during_shake']} tooth impacts; without the drag pads {kn['bucket_wobble_pp_mm_during_shake']} mm and "
              f"{kn['mesh_impacts_during_shake']}; R2-like backlash and no pads {k2['bucket_wobble_pp_mm_during_shake']} mm and {k2['mesh_impacts_during_shake']}. "
              f"The pads stop rattle from small disturbances; a shake larger than their {P['swing']['drag_Nm']:.2f} N·m still moves the upper through the play."),
        ('4', f"The worm holds the upper on a 15° side slope with the motor off: it moves {cs['slope_hold']['upper_drift_deg']:.2f}° "
              f"({cs['slope_hold']['bucket_drift_mm']} mm at the bucket) while gravity takes up the play, then stops."),
        ('5', f"Swinging into a rock at full speed is the worst case: the impact peak ({sl['peak_tooth_force_N']:.0f} N, "
              f"{sl['peak_tooth_stress_MPa_lewis']:.0f} MPa, {sl['peak_tooth_stress_MPa_lewis']/50:.0%} of PETG's yield) comes from the upper's inertia, "
              f"not the motor, so the 0.6 A limit does not cap it. The limit does cap the held stall ({sl['static_tooth_force_at_stall_N']:.0f} N, against "
              f"{snl['static_tooth_force_at_stall_N']:.0f} N without it). Keep the limit, swing slowly near obstacles, and treat the pinion as the "
              "part that fails first: print spares, or a stronger filament (PC, nylon-CF) if it breaks."),
        ('6', f"The machine does not slide or rock measurably in any case (largest upper tilt "
              f"{max(c['peak_tilt_deg'] for c in C.values()):.3f}°, lower slide {max(c['lower_slide_mm'] for c in C.values()):.1f} mm)."),
    ]
    y -= .05
    fig.text(.03, y, 'What this means for the design', fontsize=11.5, weight='bold', color=INK, va='top'); y -= .026
    for k, v in concl:
        t = wrap(v, 150)
        fig.text(.03, y, k, fontsize=8.6, weight='bold', color=INK, va='top')
        fig.text(.045, y, t, fontsize=8.6, color=INK2, va='top', linespacing=1.3)
        y -= .0155*(t.count('\n') + 1) + .007
    if val:
        fig.text(.03, .02, f"CAD checks (turntable_validation.json): {'PASS' if val['pass'] else 'FAIL'} — static fit, swing sweep every 15°, "
                           'gear mesh, assembly paths and tool access. Assumptions: simulation/turntable_swing_report.json → parameters.assumptions.',
                 fontsize=7.8, color=MUTED)
    pdf.savefig(fig); fig.savefig(ROOT / 'images/X1_swing_sim_p1.png', dpi=90); plt.close(fig)


def three(fig, top, cases, keys, titles, units, colors, labels, scales=None, refs=None, xlim=None):
    axs = []
    for i, (k, t, u) in enumerate(zip(keys, titles, units)):
        ax = fig.add_axes([.06 + i*.315, top, .27, .3])
        for c, col, lab in zip(cases, colors, labels):
            line(ax, TR[c], k, col, lab, (scales or {}).get(k, 1.0), end_label=False)
        if refs and k in refs:
            v, lab = refs[k]
            ax.axhline(v, color=REF, lw=1, ls='--'); ax.annotate(lab, (ax.get_xlim()[0], v), xytext=(4, 3), textcoords='offset points', color=REF, fontsize=7.8)
        ax.set_title(t); ax.set_xlabel('time, s'); ax.set_ylabel(u)
        if xlim:
            ax.set_xlim(*xlim)
        axs.append(ax)
    axs[0].legend(loc='upper left', bbox_to_anchor=(0, -.17), ncol=len(cases), fontsize=8, frameon=False)   # below the plot, off the data
    return axs


def page_cases(pdf, n, title, sub, groups):
    fig = plt.figure(figsize=FIG)
    header(fig, n, title, sub)
    for spec in groups:
        three(fig, **spec)
    pdf.savefig(fig); fig.savefig(ROOT / f'images/X1_swing_sim_p{n}.png', dpi=90); plt.close(fig)


def main():
    global TR
    rep = json.loads((SIM / 'turntable_swing_report.json').read_text())
    TR = json.loads((SIM / 'turntable_swing_traces.json').read_text())
    vp = ROOT / 'turntable_validation.json'
    val = json.loads(vp.read_text()) if vp.exists() else None
    (ROOT / 'images').mkdir(exist_ok=True)
    yieldF = 50e6*.01*.0015*.32/0.9397
    keys = ('bucket_mm', 'F_N', 'i_A')
    tt = ('Bucket position along its swing path', 'Pinion tooth force (line of action)', 'Swing motor current')
    un = ('mm from the start', 'N', 'A')
    with PdfPages(PDF) as pdf:
        page1(pdf, rep, val)
        page_cases(pdf, 2, 'starting and stopping', 'Full command for 2 s, then zero. Orange: no ramps. Blue: 0.4 s ramps, the R3 driver setting. '
                   'The red line is the tooth force at which a PETG pinion tooth yields (Lewis).', [
            dict(top=.53, cases=['start_stop_step', 'start_stop_ramp'], keys=keys, titles=tt, units=un, colors=[S2, S1], labels=['no ramp', '0.4 s ramps'],
                 refs={'F_N': (yieldF, 'PETG yield, about 255 N')}),
            dict(top=.1, cases=['start_stop_step', 'start_stop_ramp'], keys=keys, titles=[t + ' (the stop)' for t in tt], units=un, colors=[S2, S1],
                 labels=['no ramp', '0.4 s ramps'], refs={'F_N': (yieldF, 'PETG yield, about 255 N')}, xlim=(2.2, 3.0))])
        page_cases(pdf, 3, 'reversing', 'Full command one way, then the other. Orange: straight through. Blue: ramped through zero (0.4 s per full command). '
                   'While the drive reverses, the upper floats in the backlash; then the teeth pick it up.', [
            dict(top=.53, cases=['reverse_step', 'reverse_ramp'], keys=keys, titles=tt, units=un, colors=[S2, S1], labels=['straight', 'ramped'],
                 refs={'F_N': (yieldF, 'PETG yield, about 255 N')}),
            dict(top=.1, cases=['reverse_step', 'reverse_ramp'], keys=('swing_deg', 'Tg_Nm', 'motor_rpm'),
                 titles=('Swing angle', 'Gearbox output torque on the pinion', 'Motor speed'), units=('deg', 'N·m', 'rpm (motor shaft)'),
                 colors=[S2, S1], labels=['straight', 'ramped'])])
        page_cases(pdf, 4, 'holding still: knocks and shaking at the bucket', 'Motor holding (zero command). At 0.2 s a 10 N knock for 20 ms; from 0.6 s a ±3 N, 4 Hz shake '
                   'for 2 s, both sideways at the bucket. Blue: R3 (0.1 mm backlash, drag pads). Orange: R3 without the pads. Aqua: R2-like (0.3 mm, no pads).', [
            dict(top=.53, cases=['knock_R3', 'knock_no_pads', 'knock_R2_like'], keys=('bucket_mm', 'F_N', 'ext_N'),
                 titles=('Bucket position along its swing path', 'Pinion tooth force', 'Force applied at the bucket'), units=('mm', 'N', 'N'),
                 colors=[S1, S2, S3], labels=['R3', 'R3 without pads', 'R2-like']),
            dict(top=.1, cases=['knock_R3', 'knock_no_pads', 'knock_R2_like'], keys=('bucket_mm', 'F_N', 'Tg_Nm'),
                 titles=('Bucket position (1.0-1.6 s)', 'Pinion tooth force (1.0-1.6 s)', 'Gearbox torque (1.0-1.6 s)'), units=('mm', 'N', 'N·m'),
                 colors=[S1, S2, S3], labels=['R3', 'R3 without pads', 'R2-like'], xlim=(1.0, 1.6))])
        page_cases(pdf, 5, 'swinging into a rock, and holding on a slope', 'Top: the bucket meets a rock fixed in the world (20 N/mm) after 5° at full command, '
                   'which is then held. Blue: 0.6 A driver limit (R3). Orange: no limit. Bottom: 15° side slope, motor off.', [
            dict(top=.53, cases=['stall_limit', 'stall_no_limit'], keys=keys, titles=tt, units=un, colors=[S1, S2], labels=['0.6 A limit', 'no limit'],
                 refs={'F_N': (yieldF, 'PETG yield, about 255 N')}),
            dict(top=.1, cases=['slope_hold'], keys=('swing_deg', 'F_N', 'pitch_deg'),
                 titles=('Swing angle on the slope', 'Pinion tooth force', 'Upper tilt on the hub joint (pitch)'), units=('deg', 'N', 'deg'),
                 colors=[S1], labels=['15° side slope'])])
    print('wrote', PDF)


TR = {}
if __name__ == '__main__':
    main()

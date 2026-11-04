"""Static figure of the 150 g dig cycle from the MuJoCo trace: strokes (top) and drive forces (bottom),
same colour per drive, phases marked. Writes ../images/dig_cycle_r12.png."""
import gzip
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import r12_design as d
from build_viewer_r12 import phases

ROOT = d.rc.ROOT
INK, INK2, MUTED, GRID = '#17232b', '#52514e', '#8a949b', '#e6e9ea'
COL = dict(boom='#2a78d6', stick='#eb6834', bucket='#1baf7a')


def main():
    tr = json.loads(gzip.decompress((ROOT / 'simulation' / 'payload_150g_trace.json.gz').read_bytes()))
    t = np.array([f['t'] for f in tr['frames']])
    s = np.array([f['s'] for f in tr['frames']])
    f = np.array([f['f'] for f in tr['frames']])
    boom_f = np.where(np.abs(f[:, 0]) >= np.abs(f[:, 1]), f[:, 0], f[:, 1])
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.edgecolor': '#c4cacd', 'axes.labelcolor': INK2,
                         'xtick.color': INK2, 'ytick.color': INK2})
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 6.2), sharex=True, gridspec_kw=dict(height_ratios=[1, 1.25], hspace=0.12))
    ph = phases()
    for ax in (a1, a2):
        for i, p in enumerate(ph):
            if i % 2 == 0:
                ax.axvspan(p['start'], p['end'], color='#f4f5f2', zorder=0, lw=0)
        ax.grid(axis='y', color=GRID, lw=0.8)
        ax.spines[['top', 'right']].set_visible(False)
        ax.set_xlim(0, t[-1] + 75)
    for i, p in enumerate(ph):
        a1.text((p['start'] + p['end']) / 2, 63.5, str(i + 1), ha='center', va='bottom', fontsize=8.5, color=INK2, weight='bold')
    series = [('boom', s[:, 0], boom_f, 'Boom (each of 2)'), ('stick', s[:, 2], f[:, 2], 'Stick'), ('bucket', s[:, 3], f[:, 3], 'Bucket')]
    for k, sv, fv, name in series:
        a1.plot(t, sv, color=COL[k], lw=2, label=name, solid_capstyle='round')
        a2.plot(t, fv, color=COL[k], lw=2, label=name, solid_capstyle='round')
    ends = sorted([(sv[-1], name) for k, sv, fv, name in series])
    y = -1e9
    for v, name in ends:
        y = max(v, y + 5)
        a1.text(t[-1] + 6, y, name, va='center', fontsize=8.5, color=INK)
    pk = [(fv[np.argmax(np.abs(fv))], name) for k, sv, fv, name in series]
    for v, name in pk:
        i = int(np.argmax(np.abs([x for x in series if x[3] == name][0][2])))
        a2.annotate(f'{name.split(" ")[0]} peak {v:.1f} N', (t[i], v), xytext=(0, 9 if v > 0 else -13), textcoords='offset points',
                    ha='center', fontsize=8, color=INK)
    a1.set_ylim(-2, 62)
    a1.set_ylabel('stroke (mm)')
    for v in (d.ACT['thrust_cont'], -d.ACT['thrust_cont']):
        a2.hlines(v, 0, t[-1], color=MUTED, lw=1.2, ls=(0, (4, 3)))
    a2.hlines(0, 0, t[-1], color='#c4cacd', lw=1)
    a2.text(t[-1] + 6, d.ACT['thrust_cont'], '51 N rating', va='center', fontsize=8.5, color=INK2)
    a2.text(t[-1] + 6, -d.ACT['thrust_cont'], '−51 N', va='center', fontsize=8.5, color=INK2)
    a2.set_ylim(-58, 58)
    a2.set_ylabel('drive force (N), + = push')
    a2.set_xlabel('time (s)')
    rep = json.loads((ROOT / 'simulation' / 'payload_150g_report.json').read_text())
    fig.suptitle('R12 dig cycle with 150 g in the bucket: MuJoCo rigid-body simulation (four V6-U60 drives, 1 ms step)',
                 x=0.06, ha='left', fontsize=11, color=INK, y=0.985)
    fig.text(0.06, 0.935, f"Peak per drive: boom {rep['peak_force_N']['boom_L']:.1f} N (each of two), stick {rep['peak_force_N']['stick']:.1f} N, "
             f"bucket {rep['peak_force_N']['bucket']:.1f} N · tracking ≤ {rep['max_stroke_tracking_error_mm']:.3f} mm · "
             f"pin closure ≤ {rep['max_pin_closure_error_mm']:.3f} mm · no soil forces", fontsize=8.5, color=INK2)
    fig.text(0.06, 0.905, 'Phases (each starts with a 3 s dwell): ' + ' · '.join(f"{i + 1} {p['title'].lower()}" for i, p in enumerate(ph)),
             fontsize=8.5, color=INK2)
    fig.subplots_adjust(left=0.06, right=0.9, top=0.86, bottom=0.08)
    out = ROOT / 'images' / 'dig_cycle_r12.png'
    fig.savefig(out, dpi=150)
    print('wrote', out)


if __name__ == '__main__':
    main()

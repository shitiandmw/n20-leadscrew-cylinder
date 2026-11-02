"""Transient simulation of the V6 two-wire end-stop board (ngspice).

python source/simulate_circuit.py  -> electronics/simulation/results.json + *.png

The board has no microcontroller. Each end has a Hall switch that turns off one
MOSFET in one motor lead. The MOSFET's body diode, and the Schottky beside it, still
conduct the other way, so the motor can always reverse out of that end. F1 (PTC) is in
series with the motor. The external driver is a generic H-bridge, because the part is
meant to work with any DC motor driver.

Motor and PTC values are assumptions for an N20 6 V 150 rpm gearmotor (listed in
results.json). The Hall switch is behavioural: open-drain output, released (high
impedance) for its 50 µs power-on time, operate/release points from the magnet model.
"""
from pathlib import Path
import json
import math
import re
import shutil
import subprocess
import tempfile
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "electronics" / "simulation"
NGSPICE = shutil.which("ngspice") or str(Path.home() / ".local/envs/spice/bin/ngspice")

MOTOR = dict(VS=6.0, Rm=13.0, Lm=0.3e-3, k=0.0037, J=3e-9, Tf=1.3e-4, Tload=3.0e-4, ratio=100, pitch=0.5)
# F1 = Bourns MF-NSMF012-2: hold 0.12 A, trip 0.29 A, 1.35-8.5 ohm, <= 0.2 s to trip at 1 A.
# Thermal model fitted to the slow corner (it switches only at the trip current), the worst case
# for protection: Rth puts the switch point at 0.29 A, Cth gives 0.2 s at 1 A.
PTC_R0, PTC_TSW, PTC_IHOLD, PTC_ITRIP = 2.0, 115.0, 0.12, 0.29
PTC = dict(R0=PTC_R0, Rth=round((PTC_TSW - 25) / (PTC_ITRIP ** 2 * PTC_R0), 1),
           Cth=round(0.2 * 1.0 ** 2 * PTC_R0 / (PTC_TSW - 25), 5), Tsw=PTC_TSW, dT=2.5, K=2e4)
ENDS = dict(XTR=0.0, XTE=45.0, XSR=-2.0, XSE=48.0, hyst=0.4)

MODELS = """
.model nfet NMOS (LEVEL=1 VTO=1.05 KP=8.8 LAMBDA=0.01 RD=0.004 RS=0.004 IS=1e-18)
.model dbody D (IS=3.7e-13 N=1 RS=0.05 CJO=100p TT=10n)
.model dsch D (IS=5e-7 N=1.05 RS=0.12 CJO=50p)
.model dsig D (IS=2.52n RS=0.568 N=1.752 CJO=4p M=0.4 TT=20n BV=75)
.model dtvs D (IS=1e-12 N=1 RS=0.3 BV=10.0 IBV=1m CJO=200p)
.model ddrv D (IS=1e-12 RS=0.03 N=1.2 CJO=200p)
.model sdrv SW (VT=0.5 VH=0.05 RON=0.25 ROFF=1e7)
.model swhall SW (VT=0.5 VH=0.05 RON=40 ROFF=1e10)
"""


def board(schottky=True):
    """The actuator board: Q1/Q2, D1/D2, C1/C2, R1/R2, U1/U2 (behavioural), F1, C3, D3."""
    p = PTC
    rptc = f"({p['R0']}+{p['R0'] * p['K']}/(1+exp(-(V(tptc)-{p['Tsw']})/{p['dT']})))"
    s = f"""
* ---- Q1 in lead A (source = pad A): gates retract (B positive) ----
MQ1 n1 g1 pa pa nfet
DQ1 pa n1 dbody
CQ1gs g1 pa 600p
CQ1gd g1 n1 70p
* ---- Q2 in lead B (source = pad B): gates extend (A positive) ----
MQ2 mb g2 pb pb nfet
DQ2 pb mb dbody
CQ2gs g2 pb 600p
CQ2gd g2 mb 70p
{'DS4 pa n1 dsch' if schottky else '* no D4'}
{'DS5 pb mb dsch' if schottky else '* no D5'}
* ---- F1 PTC between Q1 and motor (+); thermal node tptc in degC ----
BF1 n1 ma I = V(n1,ma)/{rptc}
BHEAT 0 tptc I = V(n1,ma)*V(n1,ma)/{rptc}
CTH tptc 0 {p['Cth']}
RTH tptc tamb {p['Rth']}
VTAMB tamb 0 25
* ---- C3 + D3 (bidirectional TVS) across the motor ----
C3 ma mb 100n
DT1 ma nt dtvs
DT2 mb nt dtvs
* ---- U2 extend-end Hall: VCC from pad A via D2, GND = pad B, OUT pulls G2 ----
D2 pa ve dsig
C2 ve pb 1u
R2 ve g2 1meg
RI2 ve pb 2k
BPG2 pg2 pb V = 0.5*(1+tanh((V(ve,pb)-2.4)/0.2))
RPG2 pg2 pgd2 72k
CPG2 pgd2 pb 1n
BCT2 ct2 0 V = 0.5*(1+tanh((V(pgd2,pb)-0.5)/0.05))*V(mag2)
SO2 g2 pb ct2 0 swhall
* ---- U1 retract-end Hall: VCC from pad B via D1, GND = pad A, OUT pulls G1 ----
D1 pb vr dsig
C1 vr pa 1u
R1 vr g1 1meg
RI1 vr pa 2k
BPG1 pg1 pa V = 0.5*(1+tanh((V(vr,pa)-2.4)/0.2))
RPG1 pg1 pgd1 72k
CPG1 pgd1 pa 1n
BCT1 ct1 0 V = 0.5*(1+tanh((V(pgd1,pa)-0.5)/0.05))*V(mag1)
SO1 g1 pa ct1 0 swhall
"""
    return s


def motor(jam=False):
    m, e = MOTOR, ENDS
    mmps = m["pitch"] / (2 * math.pi * m["ratio"])          # mm of travel per motor radian
    tjam = 5e-3 if jam else 0.0
    return f"""
* ---- N20 motor: electrical ----
VIM ma mai 0
RM mai ma2 {m['Rm']}
LM ma2 ma3 {m['Lm']}
BEMF ma3 mb V = {m['k']}*V(w)
* ---- mechanics: node w = motor speed [rad/s], node x = rod position [mm] ----
CJ w 0 {m['J']}
BTQ 0 w I = {m['k']}*I(VIM)
BLD w 0 I = ({m['Tf']}+{m['Tload']})*tanh(V(w)/5) + 1e-3*(0.5*(1+tanh((V(x)-{e['XSE']})/0.01))*0.5*(V(w)+sqrt(V(w)*V(w)+1)) + 0.5*(1+tanh(({e['XSR']}-V(x))/0.01))*0.5*(V(w)-sqrt(V(w)*V(w)+1))) + {tjam}*tanh(V(w)/1)
CX x 0 1
BXV 0 x I = {mmps:.6e}*V(w)
* ---- magnet at each Hall: operate at the end position, release {e['hyst']} mm back ----
VONE one 0 1
SM2 one mag2 x 0 swm2
RM2 mag2 0 1k
.model swm2 SW (VT={e['XTE'] - e['hyst'] / 2} VH={e['hyst'] / 2} RON=1 ROFF=1e9)
BNX nx 0 V = -V(x)
SM1 one mag1 nx 0 swm1
RM1 mag1 0 1k
.model swm1 SW (VT={-e['XTR'] - e['hyst'] / 2} VH={e['hyst'] / 2} RON=1 ROFF=1e9)
"""


def driver(windows, pwm=None, brake=1):
    """Generic H-bridge. windows = [(t0, t1, '+A'|'+B'), ...]; pwm = (freq, duty) or None for DC."""
    def pwl(direction):
        pts = [(0.0, 0.0)]
        for t0, t1, d in windows:
            if d == direction:
                pts += [(t0, 0.0), (t0 + 2e-6, 1.0), (t1, 1.0), (t1 + 2e-6, 0.0)]
        pts.sort()
        return " ".join(f"{t:.7g} {v:g}" for t, v in pts)
    if pwm:
        f, duty = pwm
        per, ton, dt = 1 / f, duty / f, 0.5e-6
        pp = f"PULSE(0 1 0 200n 200n {ton - 200e-9:.7g} {per:.7g})"
        qq = f"PULSE(0 1 {ton + dt:.7g} 200n 200n {per - ton - 2 * dt - 400e-9:.7g} {per:.7g})"
    else:
        pp, qq = "DC 1", "DC 0"
    b = brake
    return f"""
* ---- supply and generic H-bridge (the user's driver) ----
VS vs0 0 DC {MOTOR['VS']}
RSRC vs0 vs 0.05
CB vs 0 100u
VWA wa 0 PWL({pwl('+A')})
VWB wb 0 PWL({pwl('+B')})
VP p 0 {pp}
VQ q 0 {qq}
BCAH cah 0 V = V(wa)*V(p)
BCAL cal 0 V = V(wa)*V(q)*{b} + V(wb)*({b}+(1-{b})*V(p))
BCBH cbh 0 V = V(wb)*V(p)
BCBL cbl 0 V = V(wb)*V(q)*{b} + V(wa)*({b}+(1-{b})*V(p))
BAH vs da I = V(vs,da)*(4*V(cah)+1e-6)
BAL da 0 I = V(da)*(4*V(cal)+1e-6)
DAH da vs ddrv
DAL 0 da ddrv
CDA da 0 200p
BBH vs db I = V(vs,db)*(4*V(cbh)+1e-6)
BBL db 0 I = V(db)*(4*V(cbl)+1e-6)
DBH db vs ddrv
DBL 0 db ddrv
CDB db 0 200p
* ---- 2-wire cable ----
RCA da da1 0.1
LCA da1 pa 0.3u
RLA da1 pa 10
RCB db db1 0.1
LCB db1 pb 0.3u
RLB db1 pb 10
"""


SCENARIOS = {
    "dc_extend_end": dict(
        title="DC, extend into the end, hold, then reverse", x0=ENDS["XTE"] - 0.25,
        windows=[(0.002, 0.45, "+A"), (0.46, 0.80, "+B")], tstop=0.80, tmax=2e-6, t_rev=0.46, end="E"),
    "dc_retract_end": dict(
        title="DC, retract into the end, hold, then reverse", x0=ENDS["XTR"] + 0.25,
        windows=[(0.002, 0.45, "+B"), (0.46, 0.80, "+A")], tstop=0.80, tmax=2e-6, t_rev=0.46, end="R"),
    "pwm20k_brake": dict(
        title="20 kHz PWM 50 %, slow decay (brake), extend into the end, then reverse",
        x0=ENDS["XTE"] - 0.03, pwm=(20e3, 0.5), brake=1,
        windows=[(0.002, 0.22, "+A"), (0.225, 0.375, "+B")], tstop=0.375, tmax=0.4e-6, t_rev=0.225, end="E"),
    "pwm1k_coast": dict(
        title="1 kHz PWM 50 %, fast decay (coast), extend into the end, then reverse",
        x0=ENDS["XTE"] - 0.03, pwm=(1e3, 0.5), brake=0,
        windows=[(0.002, 0.25, "+A"), (0.255, 0.45, "+B")], tstop=0.45, tmax=2e-6, t_rev=0.255, end="E"),
    "pwm100_coast": dict(
        title="100 Hz PWM 30 %, fast decay (coast), extend into the end, then reverse",
        x0=ENDS["XTE"] - 0.015, pwm=(100, 0.3), brake=0,
        windows=[(0.002, 0.30, "+A"), (0.31, 0.60, "+B")], tstop=0.60, tmax=2e-6, t_rev=0.31, end="E"),
    "powerup_at_end": dict(
        title="Already at the extend end: apply extend (blocked), then retract",
        x0=ENDS["XTE"] + 0.5, windows=[(0.001, 0.10, "+A"), (0.11, 0.30, "+B")],
        tstop=0.30, tmax=0.5e-6, t_rev=0.11, end="E"),
    "mid_speed": dict(
        title="Mid-stroke extend, with D4/D5", x0=20.0, windows=[(0.002, 0.40, "+A")], tstop=0.40, tmax=5e-6),
    "mid_speed_no_schottky": dict(
        title="Mid-stroke extend, D4/D5 not fitted", x0=20.0, windows=[(0.002, 0.40, "+A")], tstop=0.40,
        tmax=5e-6, schottky=False),
    "jam_mid_stroke": dict(
        title="Rod jammed mid-stroke, extend held on: F1 trips", x0=20.0, windows=[(0.002, 12.0, "+A")],
        tstop=12.0, tmax=2e-4, jam=True),
}


def netlist(name, sc, outfile):
    lines = [f"* V6 end-stop board: {sc['title']}", MODELS,
             driver(sc["windows"], sc.get("pwm"), sc.get("brake", 1)), board(sc.get("schottky", True)),
             motor(sc.get("jam", False)),
             f".ic V(x)={sc['x0']} V(w)=0 V(tptc)=25 V(ve)=0 V(vr)=0 V(pgd1)=0 V(pgd2)=0",
             ".control", "set noaskquit", "option numdgt=7 reltol=1e-3 abstol=1e-10 vntol=1e-5 itl4=60 method=gear rshunt=1e12"]
    tstop, tmax = sc["tstop"], sc["tmax"]
    step = 20e-6 if tstop <= 1.0 else 1e-3          # output grid; tmax is the solver's step limit
    lines.append(f"tran {step:.3g} {tstop:.6g} 0 {tmax:.3g} uic")
    lines += ["let vds1 = v(n1)-v(pa)", "let vds2 = v(mb)-v(pb)", "let vgs1 = v(g1)-v(pa)",
              "let vgs2 = v(g2)-v(pb)", "let vcc1 = v(vr)-v(pa)", "let vcc2 = v(ve)-v(pb)", "let vm = v(ma)-v(mb)",
              "let ibat = -i(vs)",
              "meas tran vds_max MAX vds2", "meas tran vds1_max MAX vds1", "meas tran vcc_max MAX vcc2",
              "meas tran vm_max MAX vm", "meas tran vm_min MIN vm", "meas tran x_final FIND v(x) AT=" + f"{tstop - 1e-4:.6g}",
              "meas tran tptc_max MAX v(tptc)"]
    if "t_rev" in sc:
        tr = sc["t_rev"]
        mag = "mag2" if sc["end"] == "E" else "mag1"
        lines += [f"meas tran t_trip WHEN v({mag})=0.5 RISE=1",
                  f"meas tran x_at_rev FIND v(x) AT={tr - 0.001:.6g}",
                  f"meas tran i_blocked MAX i(vim) FROM={tr - 0.05:.6g} TO={tr - 0.001:.6g}",
                  f"meas tran i_blocked_min MIN i(vim) FROM={tr - 0.05:.6g} TO={tr - 0.001:.6g}",
                  f"meas tran ibat_blocked AVG ibat FROM={tr - 0.05:.6g} TO={tr - 0.001:.6g}",
                  f"meas tran i_blocked_avg AVG i(vim) FROM={tr - 0.05:.6g} TO={tr - 0.001:.6g}",
                  f"meas tran x_min_after FIND v(x) AT={tstop - 1e-4:.6g}"]
    if name.startswith("mid_speed"):
        lines += ["meas tran x_a FIND v(x) AT=0.2", "meas tran x_b FIND v(x) AT=0.4",
                  "meas tran i_avg AVG i(vim) FROM=0.2 TO=0.4", "meas tran vm_avg AVG vm FROM=0.2 TO=0.4"]
    if sc.get("jam"):
        lines += ["meas tran t_ptc_trip WHEN i(vim)=0.1 FALL=1 TD=0.05", "meas tran i_stall MAX i(vim) FROM=0.05 TO=0.5",
                  f"meas tran i_after FIND i(vim) AT={tstop - 1e-3:.6g}"]
    lines += ["linearize", "set wr_singlescale", "set wr_vecnames",
              f"wrdata {outfile} v(x) i(vim) vm vds2 vds1 vgs2 vgs1 vcc2 vcc1 v(tptc) v(mag2) v(mag1)",
              ".endc", ".end"]
    return "\n".join(lines) + "\n"


def run_one(name, sc, work):
    data = work / f"{name}.txt"
    cir = work / f"{name}.cir"
    cir.write_text(netlist(name, sc, data))
    res = subprocess.run([NGSPICE, "-b", str(cir)], capture_output=True, text=True, timeout=3600)
    meas = {}
    for line in res.stdout.splitlines():
        mm = re.match(r"^\s*([a-z_0-9]+)\s*=\s*([-+0-9.eE]+)", line)
        if mm:
            meas[mm.group(1)] = float(mm.group(2))
    if not data.exists():
        raise SystemExit(f"{name}: ngspice failed\n{res.stdout[-3000:]}\n{res.stderr[-3000:]}")
    raw = np.loadtxt(data, skiprows=1)
    return meas, raw


def decimate(raw, n=4000):
    if len(raw) <= n:
        return raw
    # keep a uniform time grid by interpolation (ngspice output is on its own time steps)
    t = np.linspace(raw[0, 0], raw[-1, 0], n)
    return np.column_stack([t] + [np.interp(t, raw[:, 0], raw[:, i]) for i in range(1, raw.shape[1])])


def evaluate(name, sc, m, raw):
    out = dict(title=sc["title"])
    keep = {k: round(v, 6) for k, v in m.items()}
    out["measured"] = keep
    checks = {}
    checks["vds_max_below_25V"] = m.get("vds_max", 0) < 25 and m.get("vds1_max", 0) < 25
    checks["hall_vcc_below_36V"] = m.get("vcc_max", 0) < 36
    if "t_rev" in sc:
        end = sc["end"]
        target = ENDS["XTE"] if end == "E" else ENDS["XTR"]
        over = (m["x_at_rev"] - target) if end == "E" else (target - m["x_at_rev"])
        if name != "powerup_at_end":
            out["stop_overshoot_mm"] = round(over, 4)
        checks["stops_within_0.05mm_of_trip"] = over < 0.05 if name != "powerup_at_end" else True
        moved_back = (m["x_min_after"] < m["x_at_rev"] - 0.01) if end == "E" else (m["x_min_after"] > m["x_at_rev"] + 0.01)
        checks["reverses_out_of_end"] = bool(moved_back)
        # While blocked the average motor current must be ~0 and any peak must stay below the
        # no-load current (35 mA), i.e. far below what overcomes friction; the rod must not creep.
        peak = max(abs(m["i_blocked"]), abs(m["i_blocked_min"]))
        out["blocked_peak_current_mA"] = round(peak * 1e3, 2)
        checks["no_motor_current_while_blocked"] = abs(m["i_blocked_avg"]) < 2e-3 and peak < 30e-3
        if "t_trip" in m:
            t, x = raw[:, 0], raw[:, 1]
            creep = float(np.interp(sc["t_rev"] - 0.001, t, x) - np.interp(m["t_trip"] + 0.005, t, x))
            out["creep_while_blocked_um"] = round(creep * 1e3, 3)
            checks["no_creep_while_blocked"] = abs(creep) < 1e-3
        out["supply_current_while_blocked_mA"] = round(m["ibat_blocked"] * 1e3, 3)
        if name == "powerup_at_end":
            out["creep_while_blocked_um"] = round((m["x_at_rev"] - sc["x0"]) * 1e3, 3)
            checks["no_motion_when_powered_at_end"] = abs(m["x_at_rev"] - sc["x0"]) < 1e-3
    if name.startswith("mid_speed"):
        out["speed_mm_s"] = round((m["x_b"] - m["x_a"]) / 0.2, 4)
        out["motor_current_mA"] = round(m["i_avg"] * 1e3, 1)
        out["motor_voltage_V"] = round(m["vm_avg"], 3)
    if sc.get("jam"):
        out["stall_current_mA"] = round(m["i_stall"] * 1e3, 1)
        out["ptc_trip_time_s"] = round(m.get("t_ptc_trip", float("nan")), 2)
        out["current_after_trip_mA"] = round(m["i_after"] * 1e3, 2)
        checks["ptc_trips_within_10s"] = 0 < m.get("t_ptc_trip", 1e9) < 10
        checks["current_after_trip_below_30mA"] = abs(m["i_after"]) < 0.03
    out["checks"] = checks
    out["pass"] = all(checks.values())
    return out


def plot(name, sc, raw, ax_title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    d = decimate(raw)
    t = d[:, 0]
    cols = dict(x=1, i=2, vm=3, vds2=4, vds1=5, vgs2=6, vgs1=7, vcc2=8, vcc1=9, tptc=10, mag2=11, mag1=12)
    fig, axs = plt.subplots(3, 1, figsize=(8.6, 6.4), dpi=150, sharex=True)
    tu, ts = (1.0, "s")
    axs[0].plot(t * tu, d[:, cols["x"]], color="#1f5f8b", lw=1.4)
    axs[0].set_ylabel("rod position [mm]")
    for z, lab in ((ENDS["XTE"], "extend end (U2 operates)"), (ENDS["XTR"], "retract end (U1 operates)")):
        if d[:, cols["x"]].min() - 1 < z < d[:, cols["x"]].max() + 1:
            axs[0].axhline(z, color="#b5651d", lw=0.8, ls="--")
            axs[0].text(t[-1] * tu, z, lab, ha="right", va="bottom", fontsize=7, color="#b5651d")
    axs[1].plot(t * tu, d[:, cols["i"]] * 1e3, color="#c8471d", lw=1.0)
    axs[1].set_ylabel("motor current [mA]")
    axs[2].plot(t * tu, d[:, cols["vgs2"]], color="#2fa35a", lw=1.0, label="Q2 gate (extend allowed)")
    axs[2].plot(t * tu, d[:, cols["vgs1"]], color="#8e3bc9", lw=1.0, label="Q1 gate (retract allowed)")
    axs[2].plot(t * tu, d[:, cols["vm"]], color="#222", lw=0.6, alpha=0.6, label="motor voltage")
    if sc.get("jam"):
        ax2 = axs[2].twinx()
        ax2.plot(t * tu, d[:, cols["tptc"]], color="#d9534f", lw=1.2, label="F1 temperature")
        ax2.set_ylabel("F1 temperature [°C]", color="#d9534f")
    axs[2].set_ylabel("volts")
    axs[2].legend(fontsize=7, loc="lower left", frameon=False)
    axs[2].set_xlabel(f"time [{ts}]")
    for a in axs:
        a.grid(alpha=0.25)
    axs[0].set_title(ax_title, fontsize=9.5)
    fig.tight_layout()
    fig.savefig(OUT / f"{name}.png")
    plt.close(fig)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated scenario names (debugging; results.json is not written)")
    args = ap.parse_args()
    if args.only:
        OUT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            for name in args.only.split(","):
                m, raw = run_one(name, SCENARIOS[name], Path(tmp))
                r = evaluate(name, SCENARIOS[name], m, raw)
                plot(name, SCENARIOS[name], raw, SCENARIOS[name]["title"])
                print(name, json.dumps(r, indent=1))
        return
    OUT.mkdir(parents=True, exist_ok=True)
    results = dict(assumptions=dict(
        motor=dict(MOTOR, note="N20 6 V 150 rpm, 1:100 assumed: 13 ohm winding (stall about 0.46 A), "
                               "k = 3.7 mV/(rad/s); load 0.3 mN·m at the motor (about 0.08 A extra)."),
        ptc=dict(PTC, part="Bourns MF-NSMF012-2 (1206)", hold_A=PTC_IHOLD, trip_A=PTC_ITRIP,
                 note="Slow corner: switches only at the 0.29 A trip current; Cth from 0.2 s at 1 A. Real parts "
                      "trip somewhere between 0.12 and 0.29 A, and sooner when warm."),
        ends_mm=ENDS, hall="DRV5033-like: open drain, 50 µs power-on (output released), 2.7 mA supply"),
        scenarios={})
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for name, sc in SCENARIOS.items():
            m, raw = run_one(name, sc, work)
            r = evaluate(name, sc, m, raw)
            results["scenarios"][name] = r
            plot(name, sc, raw, sc["title"])
            print(f"{name:24s} {'PASS' if r['pass'] else 'FAIL'}  " +
                  json.dumps({k: v for k, v in r.items() if k not in ('title', 'measured', 'checks')}))
            if not r["pass"]:
                print("   failed:", [k for k, v in r["checks"].items() if not v])
    a, b = results["scenarios"]["mid_speed"], results["scenarios"]["mid_speed_no_schottky"]
    results["schottky_speed_gain_percent"] = round((a["speed_mm_s"] / b["speed_mm_s"] - 1) * 100, 1)
    results["all_pass"] = all(s["pass"] for s in results["scenarios"].values())
    (OUT / "results.json").write_text(json.dumps(results, indent=2))
    print("all pass:", results["all_pass"], " schottky speed gain %:", results["schottky_speed_gain_percent"])
    assert results["all_pass"], "circuit simulation failed"


if __name__ == "__main__":
    main()

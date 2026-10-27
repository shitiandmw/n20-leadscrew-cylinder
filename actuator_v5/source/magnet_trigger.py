"""Estimate where each DRV5033AJ switches as the magnet passes it.

The Ø4 x 2 mm axially magnetised magnet sits in the carrier with its axis along
-Y (radial). Its field is computed from the equivalent surface current on the
cylinder side (Biot-Savart, numerically). The Hall element sits behind the
barrel wall and the sensor's branded face. Only the component along the
magnet axis (normal to the branded face) is sensed. The model ignores the steel
leadscrew and nut, so it is a calibration starting point, not a guarantee.

python source/magnet_trigger.py  -> magnet_trigger.json + images/magnet_trigger.png
"""
from pathlib import Path
import json
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MU0 = 4e-7 * np.pi


def field_y(u_mm, gap_mm, br=1.2, radius=2.0, length=2.0, n_loops=160, n_seg=240):
    """B along the magnet axis [mT] at axial offset u, gap measured from the magnet face."""
    k = br / MU0                                      # surface current density, A/m
    ys = (np.arange(n_loops) + 0.5) / n_loops * length  # loop heights from the far face
    dl_len = length / n_loops * 1e-3
    phi = (np.arange(n_seg) + 0.5) / n_seg * 2 * np.pi
    p = np.stack([radius * np.cos(phi), np.zeros_like(phi), radius * np.sin(phi)], 1) * 1e-3
    dl = np.stack([-np.sin(phi), np.zeros_like(phi), np.cos(phi)], 1) * (2 * np.pi * radius / n_seg) * 1e-3
    out = []
    for u in np.atleast_1d(u_mm):
        target = np.array([0.0, (length + gap_mm), u]) * 1e-3
        b = np.zeros(3)
        for y in ys:
            src = p + np.array([0, y * 1e-3, 0])
            r = target - src
            rn = np.linalg.norm(r, axis=1)[:, None]
            b += (MU0 / (4 * np.pi)) * k * dl_len * np.sum(np.cross(dl, r) / rn ** 3, axis=0)
        out.append(b[1] * 1e3)
    out = np.array(out)
    return out * np.sign(out[np.argmin(np.abs(np.atleast_1d(u_mm)))])


def operate_offset(u, b, level):
    """Approaching from far away: the largest offset where |B| reaches BOP."""
    idx = np.where(np.abs(b) >= level)[0]
    return None if len(idx) == 0 else round(float(np.max(u[idx])), 2)


def release_offset(u, b, level):
    """Moving away from alignment: the first offset where |B| falls below BRP."""
    idx = np.where(np.abs(b) < level)[0]
    return None if len(idx) == 0 else round(float(u[idx[0]]), 2)


def run():
    p = json.loads((ROOT / "parameters.json").read_text())
    wall = 1.3 + 0.15            # barrel wall under the channel + carrier clearance
    cases = {"nominal (N35, element 0.75 mm deep)": (1.2, wall + 0.75),
             "weak (N35 low, element 1.0 mm deep)": (1.15, wall + 1.0),
             "strong (N42, element 0.5 mm deep)": (1.32, wall + 0.5)}
    u = np.linspace(0, 9, 181)
    bop = {"min": 3.0, "typ": 6.9, "max": 12.0}
    brp = {"min": 1.0, "typ": 3.5, "max": 5.0}
    res = {}
    curves = {}
    for name, (br, gap) in cases.items():
        b = field_y(u, gap, br)
        curves[name] = b
        res[name] = dict(br_T=br, magnet_face_to_element_mm=round(gap, 2), peak_mT=round(float(b[0]), 1),
                         reverse_lobe_peak_mT=round(float(b.min()), 2),
                         operate_offset_mm={k: operate_offset(u, b, v) for k, v in bop.items()},
                         release_offset_mm={k: release_offset(u, b, v) for k, v in brp.items()})
    nominal = res["nominal (N35, element 0.75 mm deep)"]
    summary = dict(
        thresholds_mT=dict(BOP=bop, BRP=brp, source="TI DRV5033 datasheet, AJ option"),
        cases=res,
        design_hall_lead_mm=p["sensor_centres_z"][1] - p["magnet_end_positions_z"][1],
        note=("Offsets are the distance between magnet centre and Hall centre along the actuator axis at which "
              "the output switches. Operate = output goes low (direction blocked). Mount each Hall this far "
              "outboard of the wanted end position, then calibrate. Reverse lobe stays below BOP min in all "
              "cases, so no false trigger before the main lobe. Steel screw/nut not modelled."))
    (ROOT / "magnet_trigger.json").write_text(json.dumps(summary, indent=2))
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8.6, 4.2), dpi=160)
        styles = {"nominal": ("#1f5f8b", "-"), "weak": ("#7a8a93", "--"), "strong": ("#b5651d", "--")}
        for name, b in curves.items():
            c, ls = styles[name.split()[0]]
            full_u = np.concatenate([-u[::-1], u[1:]])
            full_b = np.concatenate([b[::-1], b[1:]])
            ax.plot(full_u, full_b, ls, color=c, lw=1.8 if c == "#1f5f8b" else 1.2, label=name)
        ax.axhspan(bop["min"], bop["max"], color="#d9534f", alpha=0.10, lw=0)
        ax.axhspan(brp["min"], brp["max"], color="#5cb85c", alpha=0.10, lw=0)
        ax.axhline(bop["typ"], color="#d9534f", lw=0.8)
        ax.axhline(brp["typ"], color="#5cb85c", lw=0.8)
        ax.text(8.9, bop["typ"] + 0.6, "operate BOP 3–12 mT (typ 6.9)", ha="right", fontsize=8, color="#a33")
        ax.text(8.9, brp["min"] + 0.2, "release BRP 1–5 mT (typ 3.5)", ha="right", fontsize=8, color="#3a7a3a")
        ax.set_ylim(-6, 60)
        ax.set_xlim(-9, 9)
        ax.set_xlabel("magnet centre − Hall centre along the actuator axis [mm]")
        ax.set_ylabel("field normal to Hall face [mT]")
        ax.set_title("Ø4×2 mm magnet passing a DRV5033AJ (model, steel parts ignored)", fontsize=10)
        ax.grid(alpha=0.25)
        ax.legend(fontsize=7.5, loc="upper left", frameon=False)
        lead = summary["design_hall_lead_mm"]
        ax.axvline(lead, color="#333", lw=0.8, ls=":")
        ax.axvline(-lead, color="#333", lw=0.8, ls=":")
        ax.text(lead + 0.15, 45, f"Hall placed {lead:.1f} mm\noutboard of end position", fontsize=7.5)
        fig.tight_layout()
        (ROOT / "images").mkdir(exist_ok=True)
        fig.savefig(ROOT / "images" / "magnet_trigger.png")
    except ImportError:
        pass
    print(json.dumps({k: (v["peak_mT"], v["reverse_lobe_peak_mT"], v["operate_offset_mm"], v["release_offset_mm"])
                      for k, v in res.items()}, indent=1))


if __name__ == "__main__":
    run()

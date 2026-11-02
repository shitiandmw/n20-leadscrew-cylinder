"""Where each DRV5033AJ switches as the carrier magnet passes it (V6 board-mounted Halls).

The Ø3 x 2 mm magnet is magnetised along the travel (Z). The Hall switches sense through
the 1 mm PETG partition, 2.2 mm from the magnet face to the element, normal to the board (X). With
an axial magnet that component has one lobe on each side of the magnet and nothing in
front of it, so an approaching magnet always trips the Hall on the leading flank of the
first lobe; no weak side lobe can trip it early. (A radial magnet at this gap has a strong
opposite-polarity side lobe; the omnipolar DRV5033 would trip on it up to 6 mm early.)

The steel leadscrew and the motor are not modelled, so the first prototype should confirm
the end positions. The hard stops leave room for the whole modelled spread.

python source/magnet_trigger.py  -> magnet_trigger.json + images/magnet_trigger.png
"""
from pathlib import Path
import itertools
import json
import numpy as np
import layout as L
from magnet_field import magnet_field

ROOT = Path(__file__).resolve().parent.parent
BOP = {"min": 3.0, "typ": 6.9, "max": 12.0}          # DRV5033AJ, -40..125 °C
BRP = {"min": 1.0, "typ": 3.5, "max": 5.0}
BR = {"N35 low": 1.17, "nominal": 1.20, "N42 high": 1.32}
GAP = {"near": -0.35, "nominal": 0.0, "far": 0.35}   # carrier play, board in slot, element height
Y_OFF = {"centred": 0.0, "offset": 0.3}
U = np.linspace(-15, 15, 1201)                       # include low-threshold release of the larger magnet


def bx(br, gap_shift=0.0, y_off=0.0):
    m = L.MAGNET
    pts = np.stack([np.full_like(U, L.HALL_X + gap_shift), np.full_like(U, y_off), -U], 1)
    return magnet_field(pts, (m["x"], m["y"], 0.0), (0, 0, 1), br, ("cyl", m["d"], m["l"]),
                        n_loops=32, n_seg=96)[:, 0]


def operate_offset(b, level):
    """Magnet approaching from far away (U < 0): offset where |Bx| first reaches the level."""
    half = U <= 0
    idx = np.where(np.abs(b[half]) >= level)[0]
    return None if len(idx) == 0 else float(-U[half][idx[0]])


def release_offset(b, level):
    """Backing away from the stop: offset where |Bx| first falls below the level."""
    half = U <= 0
    uu, bb = U[half][::-1], b[half][::-1]
    start = np.argmax(np.abs(bb))
    idx = np.where(np.abs(bb[start:]) < level)[0]
    return None if len(idx) == 0 else float(-uu[start + idx[0]])


def run():
    nominal = bx(BR["nominal"])
    typ_offset = operate_offset(nominal, BOP["typ"])
    corners = []
    for (bk, br), (gk, gs), (yk, yo), (lk, lv) in itertools.product(BR.items(), GAP.items(), Y_OFF.items(),
                                                                       BOP.items()):
        off = operate_offset(bx(br, gs, yo), lv)
        corners.append(dict(br=bk, gap=gk, y=yk, bop=lk, operate_offset_mm=off))
    offs = [c["operate_offset_mm"] for c in corners]
    assert all(off is not None for off in offs), "magnet fails to trigger a Hall switch in at least one tolerance corner"
    # Stop position relative to the nominal end position: + = stops later (further into the end).
    early = round(max(offs) - L.HALL_LEAD, 2)
    late = round(L.HALL_LEAD - min(offs), 2)
    margin_to_hard_stop = round(L.OVERTRAVEL - late, 2)
    res = dict(
        magnet=dict(L.MAGNET, br_T=BR),
        hall_element_x_mm=L.HALL_X, magnet_face_to_element_mm=round(L.HALL_X - (L.MAGNET["x"] + L.MAGNET["d"] / 2), 2),
        thresholds_mT=dict(BOP=BOP, BRP=BRP, source="TI DRV5033 datasheet SLIS151, AJ option, -40..125 °C"),
        peak_field_mT=round(float(np.max(np.abs(nominal))), 1),
        nominal_operate_offset_mm={k: operate_offset(nominal, v) for k, v in BOP.items()},
        nominal_release_offset_mm={k: release_offset(nominal, v) for k, v in BRP.items()},
        hall_lead_used_mm=L.HALL_LEAD,
        stop_position_spread_mm=dict(earliest=-early, latest=late,
                                     note="relative to the nominal end position, all corners: BOP 3-12 mT, "
                                          "N35-N42, gap ±0.35 mm, carrier 0.3 mm off-centre in Y"),
        overtravel_mm=L.OVERTRAVEL, margin_latest_stop_to_hard_stop_mm=margin_to_hard_stop,
        corners_evaluated=len(corners),
        partition_thickness_mm=L.PARTITION_T,
        partition_material="Unfilled, non-magnetic PETG; permeability approximated as air",
        note=("Offsets are magnet centre to Hall centre along the axis. U1 sits HALL_LEAD behind the magnet's "
              "retract end position, U2 HALL_LEAD in front of its extend end position. The same unit repeats "
              "its stop point; the spread is unit-to-unit. Steel leadscrew and motor not modelled."))
    assert abs(typ_offset - L.HALL_LEAD) <= 0.1, f"HALL_LEAD {L.HALL_LEAD} vs model {typ_offset}"
    assert margin_to_hard_stop >= 0.5, "latest stop comes too close to the hard stop"
    (ROOT / "magnet_trigger.json").write_text(json.dumps(res, indent=2))
    plot(nominal, res)
    print(json.dumps({k: res[k] for k in ("peak_field_mT", "nominal_operate_offset_mm", "nominal_release_offset_mm",
                                          "stop_position_spread_mm", "margin_latest_stop_to_hard_stop_mm")}, indent=1))
    return res


def plot(nominal, res):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8.6, 4.2), dpi=160)
    for (name, br, gs), colour, ls in ((("nominal", BR["nominal"], 0.0), "#1f5f8b", "-"),
                                       (("weak: N35 low, gap +0.35 mm", BR["N35 low"], 0.35), "#7a8a93", "--"),
                                       (("strong: N42 high, gap −0.35 mm", BR["N42 high"], -0.35), "#b5651d", "--")):
        b = nominal if name == "nominal" else bx(br, gs)
        ax.plot(U, np.abs(b), ls, color=colour, lw=1.8 if name == "nominal" else 1.2, label=name)
    ax.axhspan(BOP["min"], BOP["max"], color="#d9534f", alpha=0.10, lw=0)
    ax.axhline(BOP["typ"], color="#d9534f", lw=0.8)
    ax.text(-9.8, BOP["max"] + 1.0, "operate BOP 3–12 mT (typ 6.9)", fontsize=8, color="#a33")
    lead = L.HALL_LEAD
    for s in (-1, 1):
        ax.axvline(s * lead, color="#333", lw=0.8, ls=":")
    ax.text(-lead + 0.15, 45, f"stop: magnet {lead:.1f} mm\nbefore the Hall", fontsize=7.5)
    sp = res["stop_position_spread_mm"]
    ax.axvspan(-lead - (-sp["earliest"]), -lead + sp["latest"], color="#1f5f8b", alpha=0.08, lw=0)
    ax.set_xlim(-15, 15)
    ax.set_ylim(0, 60)
    ax.set_xlabel("magnet centre − Hall centre along the actuator axis [mm]")
    ax.set_ylabel("|field normal to the board| [mT]")
    ax.set_title(f"Ø{L.MAGNET['d']:g}×{L.MAGNET['l']:g} mm axial magnet through {L.PARTITION_T:g} mm PETG (model; steel ignored)",
                 fontsize=9.5)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=7.5, loc="upper right", frameon=False)
    fig.tight_layout()
    (ROOT / "images").mkdir(exist_ok=True)
    fig.savefig(ROOT / "images" / "magnet_trigger.png")
    plt.close(fig)


if __name__ == "__main__":
    run()

"""Explanatory drawing: how the rear cap carried a push and a pull before it was hooked onto the motor-side wall
(images/rear_cap_pull.png; the hook since 11 November 2026: draw_rear_cap_hook.py).

The two rear-cap screws sit on the board side (+X) only; the rear pin pulls on the centre line.
Pushing presses the cap flat onto the body. Pulling tips the cap about the body's +X edge like a
lever, so the screws carry several times the pull. Dimensions come from layout.py; the side views
are schematic sections (the screw is drawn in the same plane as the pin), and the tilt in the pull
view is exaggerated.

    python source/draw_rear_cap_load.py
"""
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle

import layout as L

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "images", "rear_cap_pull.png")

BODY, CAP, CLAMP, MOTOR = "#f39c4a", "#3a3a3a", "#5a5a5a", "#c8ccd2"
BRASS, STEEL, PIN, RED, BLUE, GREEN = "#c9a04a", "#8f9aa5", "#202020", "#c0392b", "#1f5fa8", "#2e7d32"

X0, X1 = -6.35, L.BODY_X[1]             # board side is +X; the motor-side wall was 1.2 mm before the hook
YH = L.BODY_Y                           # 7.35
BX, BY = L.BORE_X, L.BORE_Y             # motor bay half sizes 5.15, 6.15
ZR = L.BODY_REAR_Z                      # rear face of the body
CAP_T = L.REAR_CAP_T
XS, YS = L.REAR_INSERTS[0]              # screw / insert position (7.45, 5.30)
EDGE = X1 - 0.4                         # contact edge: the body's rear edge is chamfered 0.4 mm
CLAMP_Z = ZR - CAP_T + L.CLAMP_POCKET   # clamp face (pocket floor in the rear cap)
EYE_Z = ZR - CAP_T - 4.5 - 1.5          # rear pin centre (layout.derived: rear_eye_z)
EYE_R = L.EYE_OD / 2
PIN_R = 3.0 / 2
S, I = L.CAP_SCREW, L.INSERT
Z_HEAD_TOP = CLAMP_Z - L.CLAMP_T + S["pocket_depth"] - S["head_h"]
Z_TIP = Z_HEAD_TOP + S["head_h"] + S["length"]
Z_BREAK = ZR + 14.0                     # the side views show the last 14 mm of the body


def rot(points, pivot, ang):
    c, s = math.cos(ang), math.sin(ang)
    pz, px = pivot
    return [(pz + (z - pz) * c - (x - px) * s, px + (z - pz) * s + (x - px) * c) for z, x in points]


def rect(z0, z1, x0, x1):
    return [(z0, x0), (z1, x0), (z1, x1), (z0, x1)]


def lug_outline(n=40):
    """Clevis lug: from the cap's outer face to a half-round end around the pin (side view)."""
    zb = ZR - CAP_T
    pts = [(zb, -EYE_R), (EYE_Z, -EYE_R)]
    for k in range(n + 1):
        a = -math.pi / 2 - math.pi * k / n
        pts.append((EYE_Z + EYE_R * math.cos(a), EYE_R * math.sin(a)))
    pts += [(EYE_Z, EYE_R), (zb, EYE_R)]
    return pts


def arrow(ax, p0, p1, color, lw=2.2, ms=16, **kw):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=ms, lw=lw, color=color,
                                 shrinkA=0, shrinkB=0, zorder=9, **kw))


def body_side(ax):
    """Body end in section: thin -X wall, motor bay with the motor, thick +X side with the insert."""
    ax.add_patch(Polygon(rect(ZR, Z_BREAK, X0, -BX), color=BODY, zorder=2))
    ax.add_patch(Polygon(rect(ZR, Z_BREAK, BX, X1), color=BODY, zorder=2))
    ax.add_patch(Polygon(rect(ZR + 2.5, Z_BREAK, -BX + 0.15, BX - 0.15), color=MOTOR, zorder=1))
    ax.text(ZR + 8.0, 0.0, "motor", ha="center", va="center", fontsize=10, color="#555", zorder=3)
    hz0, hz1 = ZR, ZR + I["hole_depth"]
    ax.add_patch(Polygon(rect(hz0, hz1, XS - I["hole"] / 2, XS + I["hole"] / 2), color="white", zorder=3))
    iz0 = ZR + I["recess"]
    ax.add_patch(Polygon(rect(iz0, iz0 + I["length"], XS - I["od"] / 2, XS + I["od"] / 2), color=BRASS, zorder=4))
    # break line
    zz = [Z_BREAK + (0.35 if k % 2 else -0.35) for k in range(12)]
    xx = [X0 - 0.3 + (X1 - X0 + 0.6) * k / 11 for k in range(12)]
    ax.plot(zz, xx, color="white", lw=5, zorder=5)
    ax.plot(zz, xx, color="#888", lw=1, zorder=6)


def cap_parts(tilt=0.0):
    """Rear cap, lug, clamp and screw head as polygons, tipped by `tilt` about the +X contact edge."""
    pivot = (ZR, EDGE)
    cap = rect(ZR - CAP_T, ZR, X0, X1)
    clamp = rect(CLAMP_Z - L.CLAMP_T, CLAMP_Z, L.CLAMP_X0, X1)
    head = rect(Z_HEAD_TOP, Z_HEAD_TOP + S["head_h"], XS - S["head_d"] / 2, XS + S["head_d"] / 2)
    parts = {"cap": cap, "lug": lug_outline(), "clamp": clamp, "head": head}
    out = {k: rot(v, pivot, tilt) for k, v in parts.items()}
    out["pin"] = rot([(EYE_Z, 0.0)], pivot, tilt)[0]
    out["head_mid"] = rot([(Z_HEAD_TOP + S["head_h"], XS)], pivot, tilt)[0]
    return out


def draw_cap(ax, tilt=0.0):
    p = cap_parts(tilt)
    ax.add_patch(Polygon(p["lug"], color=CAP, zorder=4))
    ax.add_patch(Polygon(p["cap"], color=CAP, zorder=4))
    ax.add_patch(Polygon(p["clamp"], color=CLAMP, zorder=4))
    ax.add_patch(Circle(p["pin"], PIN_R, color="#e6e6e6", zorder=5))
    ax.add_patch(Circle(p["pin"], PIN_R * 0.82, color=PIN, zorder=6))
    # screw: head moves with the cap, the tip stays in the insert
    hz, hx = p["head_mid"]
    ax.plot([hz, Z_TIP], [hx, XS], color=STEEL, lw=3.2, solid_capstyle="butt", zorder=7)
    ax.add_patch(Polygon(p["head"], color=STEEL, zorder=7))
    return p


def frame(ax, title):
    ax.set_title(title, fontsize=13, fontweight="bold", loc="left", pad=10)
    ax.set_aspect("equal")
    ax.axis("off")


def end_view(ax):
    frame(ax, "1  Rear end with the cap off, seen from behind")
    ax.add_patch(FancyBboxPatch((-YH + L.BODY_R, X0 + L.BODY_R), 2 * YH - 2 * L.BODY_R, X1 - X0 - 2 * L.BODY_R,
                                boxstyle=f"round,pad={L.BODY_R}", color=BODY, zorder=1))
    ax.add_patch(FancyBboxPatch((-BY + L.BORE_R, -BX + L.BORE_R), 2 * BY - 2 * L.BORE_R, 2 * BX - 2 * L.BORE_R,
                                boxstyle=f"round,pad={L.BORE_R}", color=MOTOR, zorder=2))
    ax.text(0, -1.4, "motor", ha="center", va="center", fontsize=12, color="#555", zorder=3)
    ax.add_patch(Rectangle((-L.OPEN_Y, BX), 2 * L.OPEN_Y, L.SLOT_X[1] - BX, color="white", zorder=2))
    ax.text(0, (BX + L.SLOT_X[1]) / 2, "wires", ha="center", va="center", fontsize=10, color="#888", zorder=3)
    for y in (-YS, YS):
        ax.add_patch(Circle((y, XS), I["od"] / 2, color=BRASS, zorder=3))
        ax.add_patch(Circle((y, XS), S["d"] / 2, color=STEEL, zorder=4))
    ax.plot([-YH - 2.5, YH + 2.5], [0, 0], color=PIN, lw=1.6, ls=(0, (6, 3)), zorder=5)
    ax.text(YH + 3.0, 0, "the pin pulls here,\nin the middle", ha="left", va="center", fontsize=12)
    ax.annotate("the 2 screws: only here,\non the board side", xy=(YS + 1.0, XS + 0.5), xytext=(YH + 3.0, X1 + 2.6),
                fontsize=12, color=BLUE, ha="left", va="center",
                arrowprops=dict(arrowstyle="-|>", color=BLUE, lw=1.5))
    ax.annotate("this side is a 1.2 mm wall:\nno room for a screw", xy=(2.0, X0 + 0.6), xytext=(YH + 3.0, X0 - 2.4),
                fontsize=12, color=RED, ha="left", va="center",
                arrowprops=dict(arrowstyle="-|>", color=RED, lw=1.5))
    ax.text(-YH, X1 + 0.8, "board side", fontsize=11, color="#555", ha="left", va="bottom")
    ax.set_xlim(-YH - 3, YH + 21)
    ax.set_ylim(X0 - 6, X1 + 5.5)


def side_limits(ax, right=1.5):
    ax.set_xlim(EYE_Z - EYE_R - 10.5, Z_BREAK + right)
    ax.set_ylim(X0 - 6.0, X1 + 6.0)


def push_view(ax):
    frame(ax, "2  Pushing: no problem")
    body_side(ax)
    p = draw_cap(ax)
    pz, px = p["pin"]
    arrow(ax, (pz - 9.5, px), (pz - PIN_R - 0.3, px), BLUE, lw=3, ms=22)
    ax.text(pz - 9.7, px + 1.0, "push", color=BLUE, fontsize=13, ha="left", va="bottom", fontweight="bold")
    for x in (-5.8, -3.0, 0.0, 3.0, 6.3, 8.9):
        arrow(ax, (ZR + 1.9, x), (ZR + 0.25, x), GREEN, lw=1.5, ms=11)
    ax.text(ZR + 0.3, X0 - 1.0, "the cap is pressed flat onto the body:\nthe whole end face pushes back",
            color=GREEN, fontsize=12, ha="left", va="top")
    ax.text(Z_HEAD_TOP - 0.5, X1 + 1.2, "screws: no load", color="#555", fontsize=12, ha="center", va="bottom",
            fontweight="bold")
    side_limits(ax, right=10.0)


def pull_view(ax):
    frame(ax, "3  Pulling: the cap tips over its edge")
    body_side(ax)
    tilt = math.radians(-7.0)                       # exaggerated
    p = draw_cap(ax, tilt)
    pz, px = p["pin"]
    arrow(ax, (pz - PIN_R - 0.3, px), (pz - 9.5, px), RED, lw=3, ms=22)
    ax.text(pz - 9.5, px + 1.0, "pull", color=RED, fontsize=13, ha="left", va="bottom", fontweight="bold")
    gap_z = rot([(ZR, X0)], (ZR, EDGE), tilt)[0][0]
    ax.annotate("a gap opens here:\nnothing holds this side", xy=((gap_z + ZR) / 2, X0 + 0.5), xytext=(ZR + 2.5, X0 - 3.2),
                fontsize=12, color=RED, ha="left", va="center",
                arrowprops=dict(arrowstyle="-|>", color=RED, lw=1.5))
    ax.add_patch(Circle((ZR, EDGE), 0.5, color=GREEN, zorder=10))
    ax.annotate("the cap pivots on\nthe body's edge here", xy=(ZR - 0.3, EDGE + 0.4), xytext=(ZR - 15.0, X1 + 3.3),
                fontsize=12, color=GREEN, ha="left", va="center",
                arrowprops=dict(arrowstyle="-|>", color=GREEN, lw=1.5))
    ax.annotate("the screws are\npulled very hard", xy=(ZR + 2.2, XS), xytext=(Z_BREAK + 2.0, XS + 1.5),
                fontsize=12, color=BLUE, ha="left", va="center",
                arrowprops=dict(arrowstyle="-|>", color=BLUE, lw=1.5))
    side_limits(ax, right=10.0)


def lever_view(ax, k):
    frame(ax, "4  Why so hard: it is a lever")
    zc, t = 0.0, 1.6                                # the cap as a bar; the body's end face at z = 0
    gap = 0.9
    # body block touching the bar only at the top edge
    ax.add_patch(Polygon([(zc, X0), (zc + 9.0, X0), (zc + 9.0, X1), (zc, X1)], color=BODY, zorder=1))
    bar = rot(rect(zc - t, zc, X0, X1), (zc, EDGE), -math.atan(gap / (EDGE - X0)))
    ax.add_patch(Polygon(bar, color=CAP, zorder=3))
    ax.add_patch(Circle((zc, EDGE), 0.45, color=GREEN, zorder=6))
    ax.plot([zc - t / 2 - 0.2, zc + 2.6], [XS, XS], color=STEEL, lw=3.2, zorder=4)
    # forces on the cap
    arrow(ax, (zc - t - 0.4, 0.0), (zc - t - 6.0, 0.0), RED, lw=3, ms=20)
    ax.text(zc - t - 5.8, 0.5, "pull F", color=RED, fontsize=13, ha="left", va="bottom", fontweight="bold")
    arrow(ax, (zc + 3.0, XS - 1.3), (zc + 6.8, XS - 1.3), BLUE, lw=2.4, ms=18)
    ax.text(zc + 9.6, XS - 1.3, f"screws hold\n{k:.1f} F  ({k / 2:.1f} F each)", color=BLUE, fontsize=12,
            ha="left", va="center", fontweight="bold")
    arrow(ax, (zc - 0.6, EDGE + 1.0), (zc - 5.2, EDGE + 1.0), GREEN, lw=2.0, ms=15)
    ax.text(zc - 5.4, EDGE + 1.0, f"edge pushes back {k - 1:.1f} F", color=GREEN, fontsize=12, ha="right", va="center")
    # lever arms, measured from the pivot
    zd = zc - t - 9.5
    for xa, txt in ((0.0, f"pull: {EDGE:.2f} mm\nfrom the pivot"), (XS, f"screws: {EDGE - XS:.1f} mm\nfrom the pivot")):
        ax.plot([zd - 0.5, zc - t - 0.2], [xa, xa], color="#999", lw=0.8, ls=":", zorder=2)
    ax.plot([zd - 0.5, zc + 0.2], [EDGE, EDGE], color="#999", lw=0.8, ls=":", zorder=2)
    ax.annotate("", xy=(zd, 0.0), xytext=(zd, EDGE), arrowprops=dict(arrowstyle="<->", color="#333", lw=1.2))
    ax.text(zd - 0.6, EDGE / 2 - 0.6, f"{EDGE:.2f} mm", fontsize=12, ha="right", va="center", color="#333")
    ax.annotate("", xy=(zd + 3.4, XS), xytext=(zd + 3.4, EDGE), arrowprops=dict(arrowstyle="<->", color="#333", lw=1.2))
    ax.text(zd + 3.9, (XS + EDGE) / 2, f"{EDGE - XS:.1f} mm", fontsize=12, ha="left", va="center", color="#333")
    ax.text(zd - 6.5, X0 - 2.2,
            f"Turning about the edge:  F × {EDGE:.2f} mm  =  screws × {EDGE - XS:.1f} mm\n"
            f"so the screws together hold {EDGE:.2f} / {EDGE - XS:.1f} = {k:.1f} × the pull.\n"
            f"Like a bottle opener: a pull on the long arm becomes a big force on the short arm.",
            fontsize=12, ha="left", va="top", color="#222")
    ax.set_xlim(zd - 7.0, zc + 27.0)
    ax.set_ylim(X0 - 8.5, X1 + 4.0)


def main():
    k_screws = EDGE / (EDGE - XS)                  # total screw force / pull, contact at the edge
    fig, axes = plt.subplots(2, 2, figsize=(16.5, 12.0))
    end_view(axes[0, 0])
    push_view(axes[0, 1])
    pull_view(axes[1, 0])
    lever_view(axes[1, 1], k_screws)
    fig.text(0.012, 0.012,
             "V6 rear cap with M1 screws in heat-set inserts, before it was hooked onto the motor-side wall "
             "(images/rear_cap_hook.png). Views 2 and 3 are simplified side sections (the screw is "
             "drawn in the plane of the pin); the tilt in view 3 is exaggerated.\nThe numbers hold for the real, tiny "
             f"tilt. If the edge contact spreads inward from the edge, the screws carry even more (about {2 * 3.44:.1f} F "
             "together).", fontsize=10.5, color="#444", va="bottom")
    fig.subplots_adjust(left=0.01, right=0.995, top=0.95, bottom=0.07, wspace=0.03, hspace=0.12)
    fig.savefig(OUT, dpi=100)
    print("wrote", OUT, "screw factor", round(k_screws, 2))


if __name__ == "__main__":
    main()

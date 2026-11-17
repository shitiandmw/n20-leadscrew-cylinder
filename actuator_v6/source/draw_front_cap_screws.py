"""Design figure, 14 November 2026: the V6 front cap's third screw, on the motor side. Built as drawn in the
proposal of 13 November (then output/front_cap_proposal.png); the 2.5 mm key rib now also runs out to the front face.

The front cap's first two M1 screws sit on the board side (+X) only, like the rear cap's. The front cap is loaded only when
the carrier runs past the front Hall stop into the cap's spigot; it then tips about the body's +X edge like a lever,
and each screw carries about 1.9x the push. The rear cap's answer, a hook on the end of the motor-side wall
(draw_rear_cap_hook.py), does not carry over: the front cap is threaded onto the rod, and its spigot and its board
tongue sit inside the body with 0.075-0.2 mm of play, so it can only go on straight; and the body prints front end
down, so nothing may stand out of its front face. The key rib in the bore's (-X, -Y) corner makes that corner the
one thick spot on the motor side: a third insert and screw fit there (layout.FRONT_INSERTS[2]).

The end views are sections of the CAD body (design_v6.make_body): before, with the 2.0 mm rib and the two board-side
inserts, and now, with the 2.5 mm rib (layout.CARRIER_KEY) and the third insert. The side views are schematic
sections through the middle, with the screw drawn in that plane. Screw loads: rigid cap on the body's front face,
the screws as equal springs (no preload), the push in the middle.

    python source/draw_front_cap_screws.py        (writes images/front_cap_screws.png)
"""
import math
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec, GridSpecFromSubplotSpec
from matplotlib.patches import Circle, PathPatch, Polygon
from matplotlib.path import Path
import cadquery as cq
from shapely.geometry import Point, Polygon as SPoly
from shapely.ops import unary_union

import layout as L
import design_v6 as D
from draw_rear_cap_load import BODY, CAP, BRASS, STEEL, RED, BLUE, GREEN, rect, rot, arrow

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "images", "front_cap_screws.png")

VARIANT = "U60"
DV = L.derived(VARIANT)
ZF = DV["body_z"][1]                    # body front face (79.0)
CAP_T = L.FRONT_CAP_T
ZC = ZF + CAP_T                         # cap outer face
ZS = DV["carrier_front_max_z"]          # carrier front face at the hard stop = spigot end (78.0)
X0, X1 = L.BODY_X
YH = L.BODY_Y
BX, BY = L.BORE_X, L.BORE_Y
S, I = L.CAP_SCREW, L.INSERT
XS, YS = L.FRONT_INSERTS[0]             # (6.85, 5.65)
EDGE = X1 - 0.4                         # the body's front edge is chamfered 0.4 mm
F_JAM = 85.0                            # N: a jam at the X1 board's 0.5 A limit (README)
F_RATED = 55.0                          # N: continuous rating (the fuse's hold current)
PULL_OUT = (100.0, 150.0)               # N: estimated pull-out of an M1 insert from PETG (README, not tested)
YIELD = 207.0                           # N: A2-70 M1 screw
KEY_OLD, KEY_NEW = 2.0, L.CARRIER_KEY   # key rib before and now, mm
TWO = L.FRONT_INSERTS[:2]               # the board-side front inserts; the third is FRONT_INSERTS[2]
POCKET_NEW = L.CAP_SCREW["pocket_d"]     # head pocket of the new screw: the same 2.6 mm as the others
CARRIER = "#a9c4de"
PCB = "#2e6b3a"
Z_BREAK = ZF - 12.0
LD = dict(fontsize=11.5)


# ---- CAD sections ------------------------------------------------------------------------------
def body_section(z, key=KEY_NEW, holes=True, inserts=None):
    """shapely section of the CAD body at height z (mm), with the key rib `key` mm and the front inserts `inserts`
    (default: layout's)."""
    old = L.CARRIER_KEY, L.FRONT_INSERTS
    L.CARRIER_KEY = key
    if inserts is not None:
        L.FRONT_INSERTS = inserts
    try:
        body = D.make_body(DV, insert_holes=holes)
    finally:
        L.CARRIER_KEY, L.FRONT_INSERTS = old
    sec = body.copyWorkplane(cq.Workplane("XY", origin=(0, 0, z))).section()
    polys = []
    for f in sec.faces().vals():
        ring = lambda w: [(p.x, p.y) for p in w.positions([k / 720 for k in range(720)])]
        polys.append(SPoly(ring(f.outerWire()), [ring(w) for w in f.innerWires()]))
    return unary_union(polys)


def inscribed(P, x, y):
    p = Point(x, y)
    if not P.contains(p):
        return 0.0
    return min([P.exterior.distance(p)] + [h.distance(p) for h in P.interiors])


def best_corner(P):
    """Largest circle in the (-X, -Y) corner: coarse grid, then a fine one."""
    best = (0.0, (-6.0, -5.8))
    for span, n in ((2.4, 48), (0.12, 24)):
        cx, cy = best[1]
        for i in range(n + 1):
            for j in range(n + 1):
                x, y = cx - span / 2 + span * i / n, cy - span / 2 + span * j / n
                r = inscribed(P, x, y)
                if r > best[0]:
                    best = (r, (x, y))
    return best


# ---- statics -----------------------------------------------------------------------------------
def screw_loads(screws, face, f=1.0, load=(0.0, 0.0)):
    """Rigid cap on the body's front face, screws as equal springs. The lift is w = a + b x + c y >= 0 on the face;
    minimise the spring energy minus the work of the push f at `load` (active-set enumeration over the face's hull
    corners). Returns the screw forces and the contact forces (with their points)."""
    hull = np.array(face.convex_hull.exterior.coords[:-1])
    U = np.array([[1.0, x, y] for x, y in screws])
    M = U.T @ U
    rhs = np.array([f, f * load[0], f * load[1]])
    cands = [()] + [(j,) for j in range(len(hull))] + [(i, j) for i in range(len(hull)) for j in range(i + 1, len(hull))]
    best = None
    for J in cands:
        V = np.array([[1.0, hull[j, 0], hull[j, 1]] for j in J]).reshape(len(J), 3)
        A = np.block([[M, -V.T], [V, np.zeros((len(J), len(J)))]])
        b = np.concatenate([rhs, np.zeros(len(J))])
        try:
            sol = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            continue
        p, lam = sol[:3], sol[3:]
        if np.any(lam < -1e-9) or np.any(hull @ p[1:] + p[0] < -1e-9):
            continue
        energy = 0.5 * p @ M @ p - rhs @ p
        if best is None or energy < best[0] - 1e-12:
            best = (energy, U @ p, [(lam[k], tuple(hull[j])) for k, j in enumerate(J)])
    return best[1], best[2]


# ---- drawing helpers ----------------------------------------------------------------------------
def frame(ax, title, size=13):
    ax.set_title(title, fontsize=size, fontweight="bold", loc="left", pad=8)
    ax.set_aspect("equal")
    ax.axis("off")


def note(ax, text, xy, xytext, color, ha="left", size=11.5, va="center"):
    ax.annotate(text, xy=xy, xytext=xytext, fontsize=size, color=color, ha=ha, va=va, zorder=20,
                arrowprops=dict(arrowstyle="-|>", color=color, lw=1.3))


def shapely_patch(P, **kw):
    """matplotlib patch of a shapely (multi)polygon, with holes; coordinates as (-y, x): seen from the front."""
    geoms = list(P.geoms) if hasattr(P, "geoms") else [P]
    verts, codes = [], []
    for g in geoms:
        for ring in [g.exterior] + list(g.interiors):
            pts = [(-y, x) for x, y in ring.coords]
            verts += pts
            codes += [Path.MOVETO] + [Path.LINETO] * (len(pts) - 2) + [Path.CLOSEPOLY]
    return PathPatch(Path(verts, codes), **kw)


def break_line(ax, z, x0, x1):
    zz = [z + (0.3 if k % 2 else -0.3) for k in range(14)]
    xx = [x0 - 0.3 + (x1 - x0 + 0.6) * k / 13 for k in range(14)]
    ax.plot(zz, xx, color="white", lw=5, zorder=8)
    ax.plot(zz, xx, color="#888", lw=1, zorder=9)


def body_front(ax, board=False, screw_plane=True):
    """The body's last 12 mm in section (z across, x up): motor-side wall, bore, board side."""
    ax.add_patch(Polygon([(Z_BREAK, X0), (ZF - 0.4, X0), (ZF, X0 + 0.4), (ZF, -BX - 0.3), (ZF - 0.3, -BX),
                          (Z_BREAK, -BX)], color=BODY, zorder=2))
    if screw_plane:                     # board side as in the plane of the screws: a solid corner with the insert
        ax.add_patch(Polygon([(Z_BREAK, BX), (ZF - 0.3, BX), (ZF, BX + 0.3), (ZF, X1 - 0.4), (ZF - 0.4, X1),
                              (Z_BREAK, X1)], color=BODY, zorder=2))
        ax.add_patch(Polygon(rect(ZF - I["hole_depth"], ZF + 0.01, XS - I["hole"] / 2, XS + I["hole"] / 2),
                             color="white", zorder=3))
        z_out = ZF - I["recess"]
        ax.add_patch(Polygon(rect(z_out - I["length"], z_out, XS - I["od"] / 2, XS + I["od"] / 2), color=BRASS,
                             zorder=4))
    else:                               # board side in the middle: partition, part cavity, board groove, outer wall
        px1, (sx0, sx1) = L.PARTITION_X[1], L.SLOT_X
        ax.add_patch(Polygon([(Z_BREAK, BX), (ZF - 0.3, BX), (ZF, BX + 0.3), (ZF, px1), (Z_BREAK, px1)],
                             color=BODY, zorder=2))
        ax.add_patch(Polygon([(Z_BREAK, sx1), (ZF, sx1 + 0.3), (ZF, X1 - 0.4), (ZF - 0.4, X1), (Z_BREAK, X1)],
                             color=BODY, zorder=2))
        ax.add_patch(Polygon([(Z_BREAK, px1), (ZF, px1), (ZF, sx0 - 0.3), (ZF - 0.3, sx0), (Z_BREAK, sx0)],
                             color=BODY, zorder=2))
        ax.add_patch(Polygon(rect(Z_BREAK, ZF - 0.3, sx0, sx1), color="white", zorder=2))
        if board:
            ax.add_patch(Polygon(rect(Z_BREAK, DV["pcb_z"][1], L.PCB_X_INNER, L.PCB_X_OUTER), color=PCB, zorder=3))
    break_line(ax, Z_BREAK, X0, X1)


def carrier_and_rod(ax, z_front, right):
    c0 = z_front - L.CARRIER_LEN
    ax.add_patch(Polygon(rect(c0, z_front, -L.CARRIER_X, L.CARRIER_X), color=CARRIER, zorder=3))
    ax.add_patch(Polygon(rect(z_front - 0.01, right, -L.ROD_D / 2, L.ROD_D / 2), color=CARRIER, zorder=3))
    ax.add_patch(Polygon(rect(c0 - 0.01, right, -L.ROD_BORE / 2, L.ROD_BORE / 2), color="white", zorder=3.5))
    n0 = c0 + L.NUT_SLOT_DZ[0]
    ax.add_patch(Polygon(rect(n0, n0 + L.NUT_T, -L.NUT_AF / 2, L.NUT_AF / 2), color=BRASS, zorder=4))
    tip = DV["screw_length_mm"]
    ax.add_patch(Polygon(rect(Z_BREAK, min(tip, right), -2.0, 2.0), color=STEEL, zorder=4.5))


def cap_polys(tilt=0.0, tongue=False):
    """Front cap in the middle section, tipped by `tilt` about the body's +X front edge."""
    g = L.ROD_GUIDE_D / 2
    lo = [(ZF, X0), (ZC - 0.4, X0), (ZC, X0 + 0.4), (ZC, -g - 0.5), (ZC - 0.5, -g), (ZF - L.SPIGOT, -g),
          (ZF - L.SPIGOT, -L.CARRIER_X + 0.05), (ZF, -L.CARRIER_X + 0.05)]
    hi = [(ZF, L.CARRIER_X - 0.05), (ZF - L.SPIGOT, L.CARRIER_X - 0.05), (ZF - L.SPIGOT, g), (ZC - 0.5, g),
          (ZC, g + 0.5), (ZC, X1 - 0.4), (ZC - 0.4, X1), (ZF, X1)]
    out = {"lo": lo, "hi": hi}
    if tongue:
        t = ZF - DV["pcb_z"][1] - 0.1
        xm = (L.PCB_X_INNER + L.PCB_X_OUTER) / 2
        out["tongue"] = rect(ZF - t, ZF + 0.01, xm - (L.PCB_T - 0.05) / 2, xm + (L.PCB_T - 0.05) / 2)
    out["pocket"] = rect(ZC - S["pocket_depth"], ZC + 0.01, XS - S["pocket_d"] / 2, XS + S["pocket_d"] / 2)
    out["head"] = rect(ZC - S["pocket_depth"], ZC - S["pocket_depth"] + S["head_h"], XS - S["head_d"] / 2,
                       XS + S["head_d"] / 2)
    pivot = (ZF, EDGE)
    return {k: rot(v, pivot, tilt) for k, v in out.items()}


def draw_cap(ax, tilt=0.0, tongue=False, screw=True):
    p = cap_polys(tilt, tongue)
    for k in ("lo", "hi") + (("tongue",) if tongue else ()):
        ax.add_patch(Polygon(p[k], color=CAP, zorder=5))
    if screw:
        ax.add_patch(Polygon(p["pocket"], color="white", zorder=5.5))
        tip = ZC - S["pocket_depth"] - S["length"]            # the tip stays in the insert; the shank stretches
        head_mid = rot([(ZC - S["pocket_depth"], XS)], (ZF, EDGE), tilt)[0]
        ax.plot([head_mid[0], tip], [head_mid[1], XS], color=STEEL, lw=3.4, solid_capstyle="butt", zorder=7)
        ax.add_patch(Polygon(p["head"], color=STEEL, zorder=7))
    return p


# ---- panels ------------------------------------------------------------------------------------
def text_panel(ax, today, new, r_now):
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.text(0.0, 1.0, "Front cap: why it can't hook on like the rear cap, and its third screw",
            fontsize=14, fontweight="bold", ha="left", va="top")
    t_max, n_max = max(today) * F_JAM, max(new) * F_JAM
    blocks = [
        ("When the front cap is loaded",
         f"Only if the carrier runs past the front Hall stop into the cap's spigot, for example if U2 does not "
         f"switch.\nAt the X1 board's 0.5 A limit that push is about {F_JAM:.0f} N, for up to 2 s."),
        ("Before (view 2)",
         f"Both screws were on the board side, so the cap tipped over the body's board-side edge. Each screw then "
         f"carried\n{max(today):.2f}× the push: {t_max:.0f} N at {F_JAM:.0f} N, above the inserts' estimated "
         f"{PULL_OUT[0]:.0f}–{PULL_OUT[1]:.0f} N pull-out.\nThe rear cap had the same lever before its hook."),
        ("Why the rear cap's hook does not carry over (view 3)",
         "The rear cap goes on 0.8 mm to one side and slides back to hook on. The front cap is threaded onto the "
         "rod,\nand its spigot and its board tongue sit in the body with 0.075–0.20 mm of play: it can only go "
         "straight on.\nThe body also prints front end down, so no wall end may stand out of its front face. "
         "A hook here would need\na 2 mm spigot (cap 5 mm), a board 1.5 mm longer (new PCB files), no tongue, a "
         "spigot cut open on the\nboard side, and the cap pushed 0.6 mm sideways against the bent rod while "
         "fitting it."),
        ("Now (views 4 to 6)",
         "A third M1 insert and screw on the motor side, in the corner of the bore's key rib: the only thick "
         "spot there.\n"
         f"The rib grew from {KEY_OLD:.1f} to {KEY_NEW:.1f} mm, which gives the insert {NEW_R - I['od'] / 2:.2f} mm "
         f"of PETG round its knurl (at {KEY_OLD:.1f} mm: {r_now - I['od'] / 2:.2f}).\nThe push now sits between "
         f"the screws: the most loaded one carries {max(new):.2f}×, {n_max:.0f} N at {F_JAM:.0f} N."),
    ]
    y = 0.915
    for head, body in blocks:
        ax.text(0.0, y, head, fontsize=12.2, fontweight="bold", ha="left", va="top", color="#222")
        ax.text(0.015, y - 0.05, body, fontsize=11.4, ha="left", va="top", color="#222", linespacing=1.3)
        y -= 0.05 + 0.041 * (body.count("\n") + 1) + 0.04
    ax.text(0.0, y,
            "Nothing else changed: the outline, pins and lengths; both parts print as before. The rib now runs out "
            "to the\nfront face, with a 0.3 mm lead-in of its own. One more insert (step 3) and one more M1 × 8 "
            "(step 9) per actuator.",
            fontsize=11.6, ha="left", va="top", color=BLUE, linespacing=1.3, fontweight="bold")


def today_view(ax, k_each):
    frame(ax, "2  Before, at the front hard stop: the cap tips over its board-side edge")
    right = ZC + 5.5
    body_front(ax)
    carrier_and_rod(ax, ZS, right)
    tilt = math.radians(5.0)                       # exaggerated
    p = draw_cap(ax, tilt)
    for x in (-4.55, 4.55):
        a = rot([(ZS - 3.2, x), (ZS - 0.15, x)], (ZF, EDGE), tilt)
        arrow(ax, (ZS - 3.2, x), a[1], RED, lw=2.6, ms=18)
    ax.text(ZS - 3.4, -1.0, "carrier pushes\nthe spigot: F", color=RED, fontsize=12, ha="right", va="center",
            fontweight="bold")
    ax.add_patch(Circle((ZF, EDGE), 0.42, color=GREEN, zorder=12))
    note(ax, "the cap pivots on\nthe body's edge", (ZF + 0.2, EDGE + 0.35), (ZF - 9.0, X1 + 3.2), GREEN)
    gz = rot([(ZF, X0)], (ZF, EDGE), tilt)[0][0]
    note(ax, "a gap opens: nothing\nholds this side", ((ZF + gz) / 2, X0 + 0.3), (ZF - 9.5, X0 - 3.0), RED)
    note(ax, f"each screw: {k_each:.2f} F\n= {k_each * F_JAM:.0f} N at {F_JAM:.0f} N", (ZF - 1.2, XS),
         (right + 0.8, XS + 1.2), BLUE)
    ax.text(Z_BREAK + 0.6, -BX + 1.0, "bore", fontsize=10, color="#777", ha="left", va="bottom")
    ax.set_xlim(Z_BREAK - 1.5, right + 13.0)
    ax.set_ylim(X0 - 5.5, X1 + 5.5)


def dim(ax, z, x0, x1, text, color, side=1, size=10.5):
    ax.annotate("", xy=(z, x0), xytext=(z, x1), arrowprops=dict(arrowstyle="<->", color=color, lw=1.0,
                                                                shrinkA=0, shrinkB=0), zorder=15)
    ax.text(z + side * 0.35, (x0 + x1) / 2, text, fontsize=size, color=color, ha="left" if side > 0 else "right",
            va="center", zorder=15)


def why_view(ax):
    frame(ax, "3  Why the rear cap's hook does not fit here (section through the middle)")
    right = ZC + 3.0
    body_front(ax, board=True, screw_plane=False)
    ax.add_patch(Polygon(rect(Z_BREAK, right, -L.ROD_D / 2, L.ROD_D / 2), color=CARRIER, zorder=3))
    ax.add_patch(Polygon(rect(Z_BREAK - 0.01, right, -L.ROD_BORE / 2, L.ROD_BORE / 2), color="white", zorder=3.5))
    ax.add_patch(Polygon(rect(Z_BREAK, DV["screw_length_mm"], -2.0, 2.0), color=STEEL, zorder=4.5))
    draw_cap(ax, 0.0, tongue=True, screw=False)
    g = L.ROD_GUIDE_D / 2
    c_rod = g - L.ROD_D / 2
    c_spig = BX - (L.CARRIER_X - 0.05)
    c_tongue = (L.SLOT_X[1] - L.SLOT_X[0] - (L.PCB_T - 0.05)) / 2
    tx = right + 2.0
    note(ax, f"tongue in the board groove: {c_tongue:.3f} mm a side\n(it holds the board's front edge)",
         (ZF - 0.25, L.PCB_X_OUTER - 0.05), (tx, X1 + 1.6), "#333", size=11)
    note(ax, f"rod in its Ø{L.ROD_GUIDE_D:.1f} guide: {c_rod:.2f} mm a side", (ZF + 3.0, g - 0.05),
         (tx, 2.6), "#333", size=11)
    note(ax, f"spigot in the bore: {c_spig:.2f} mm a side", (ZF - 0.5, -BX + 0.1), (tx, X0 + 0.4), "#333",
         size=11)
    note(ax, "board", (ZF - 5.0, (L.PCB_X_INNER + L.PCB_X_OUTER) / 2), (ZF - 9.0, X1 + 2.6), PCB, size=11)
    note(ax, "rod", (Z_BREAK + 3.0, -3.3), (Z_BREAK + 1.0, X0 - 2.2), "#4a6f96", size=11)
    note(ax, "leadscrew", (Z_BREAK + 6.0, -1.0), (Z_BREAK + 5.0, X0 - 2.2), "#555", size=11)
    # the rear cap's fitting move, crossed out
    za, xa = tx + 1.0, -3.6
    arrow(ax, (za, xa - 1.3), (za, xa + 1.6), RED, lw=2.2, ms=16)
    ax.plot([za - 0.9, za + 0.9], [xa - 0.6, xa + 1.0], color=RED, lw=2.4, zorder=12)
    ax.plot([za - 0.9, za + 0.9], [xa + 1.0, xa - 0.6], color=RED, lw=2.4, zorder=12)
    ax.text(za + 1.5, xa + 0.2, "the rear cap goes on 0.8 mm to\nthe board side and slides back:\n"
            "no room for that here", fontsize=11, color=RED, ha="left", va="center")
    ax.set_xlim(Z_BREAK - 1.0, right + 20.0)
    ax.set_ylim(X0 - 4.0, X1 + 4.0)


def end_view(ax, sec_now, sec_new, c_new, r_new):
    frame(ax, "4  Body's front end, seen from the front (CAD section 1.5 mm in)")
    ax.add_patch(shapely_patch(sec_new, color=BODY, zorder=2, lw=0))
    # where the rib grows: the extra strip, outlined
    grown = sec_new.difference(sec_now.buffer(0.001))
    if not grown.is_empty:
        ax.add_patch(shapely_patch(grown, fc="#ffd27f", ec="#b06a00", lw=0.8, zorder=2.5))
    for (x, y), new in ((TWO[0], False), (TWO[1], False), (c_new, True)):
        ax.add_patch(Circle((-y, x), I["od"] / 2, color=BRASS if not new else "#e0b450", zorder=4))
        ax.add_patch(Circle((-y, x), S["d"] / 2, color=STEEL, zorder=5))
        if new:
            ax.add_patch(Circle((-y, x), I["od"] / 2 + 0.08, fill=False, ec=GREEN, lw=2.2, zorder=6))
    xs = [TWO[0], TWO[1], c_new]
    tri = [(-y, x) for x, y in xs] + [(-xs[0][1], xs[0][0])]
    ax.plot(*zip(*tri), color=BLUE, lw=1.1, ls=(0, (5, 3)), zorder=7)
    ax.plot(0, 0, marker="o", ms=11, mfc="white", mec=RED, mew=2.2, zorder=8)
    ax.plot(0, 0, marker="x", ms=8, mec=RED, mew=2.2, zorder=9)
    note(ax, "the carrier pushes\nhere, in the middle", (0.4, 0.4), (YH + 2.5, -1.4), RED)
    note(ax, "the two screws before:\nboard side only", (-L.FRONT_INSERTS[0][1] + 0.9, XS + 0.6), (YH + 2.5, X1 + 2.2),
         BLUE)
    note(ax, f"new: third insert in the\nkey-rib corner, where a\nØ{2 * r_new:.2f} mm circle fits",
         (-c_new[1] - 1.0, c_new[0] - 0.4), (YH + 2.5, X0 - 2.6), GREEN)
    note(ax, f"key rib {KEY_OLD:.1f} → {KEY_NEW:.1f} mm\n(the rod fits one way round)", (4.6, -3.9),
         (-YH - 2.0, X0 - 3.6), "#8a5200", ha="right")
    note(ax, "board groove", (-2.0, (L.SLOT_X[0] + L.SLOT_X[1]) / 2), (-YH - 2.0, X1 + 2.4), PCB, ha="right")
    ax.text(0.0, X1 + 0.6, "board side (+X)", fontsize=10.5, color="#555", ha="center", va="bottom")
    ax.text(0.0, X0 - 0.6, "motor side (−X)", fontsize=10.5, color="#555", ha="center", va="top")
    ax.set_xlim(-YH - 10.5, YH + 12.5)
    ax.set_ylim(X0 - 6.5, X1 + 4.5)


def corner_view(ax, sec_new, c_new, r_new, r_front):
    frame(ax, "5  The new insert, close up (same view)")
    ax.add_patch(shapely_patch(sec_new, color=BODY, zorder=2, lw=0))
    x, y = c_new
    ax.add_patch(Circle((-y, x), I["hole"] / 2, color="white", zorder=3))
    ax.add_patch(Circle((-y, x), I["od"] / 2, color="#e0b450", zorder=4, alpha=0.9))
    ax.add_patch(Circle((-y, x), I["bore"] / 2, color="white", zorder=5))
    ax.add_patch(Circle((-y, x), r_new, fill=False, ec=GREEN, lw=1.2, ls=(0, (3, 2)), zorder=6))
    ax.add_patch(Circle((-y, x), POCKET_NEW / 2, fill=False, ec=CAP, lw=1.4, ls=(0, (5, 3)), zorder=6))
    # outline of the cap and its 0.4 mm edge chamfer
    t = np.linspace(0, math.pi / 2, 30)
    rc = L.BODY_R
    cxo, cyo = X0 + rc, -YH + rc
    for off, ls, lab in ((0.0, "-", None), (0.4, ":", None)):
        r = rc - off
        ax.plot(-(cyo - r * np.sin(t)), cxo - r * np.cos(t), color=CAP, lw=1.0, ls=ls, zorder=7)
        ax.plot([-(cyo - r), -(cyo - r) - 0.0], [cxo, cxo + 4.0], color=CAP, lw=1.0, ls=ls, zorder=7)
        ax.plot([-cyo, -cyo - 4.0], [cxo - r, cxo - r], color=CAP, lw=1.0, ls=ls, zorder=7)
    knurl = r_new - I["od"] / 2
    rim = min(x - X0, y + YH) - POCKET_NEW / 2        # the cap's own sides (it has no rib)
    note(ax, f"{knurl:.2f} mm of PETG round the knurl\n(the board-side front inserts: {r_front - I['od'] / 2:.2f},"
         f"\nthe rear ones: 1.05)", (-y + 0.2, x + r_new - 0.05), (-y - 3.4, x + 3.0), GREEN, ha="right", size=11)
    note(ax, f"head pocket in the cap: Ø{POCKET_NEW:.1f},\n{rim:.2f} mm from its sides, outside\n"
         f"the 0.4 mm edge chamfer (dotted)", (-y - POCKET_NEW / 2 * 0.7, x - POCKET_NEW / 2 * 0.7),
         (-y - 3.4, x - 3.2), CAP, ha="right", size=11)
    ax.text(-y + 2.6, x + 1.9, "key rib", fontsize=10.5, color="#8a5200", ha="center", rotation=-45)
    ax.text(-y + 3.6, x + 3.3, "bore", fontsize=10.5, color="#777", ha="center")
    ax.set_xlim(-y - 9.0, -y + 4.6)
    ax.set_ylim(x - 4.6, x + 4.6)


def loads_view(ax, today, new):
    ax.set_title(f"6  Screw loads at a jam ({F_JAM:.0f} N push)", fontsize=13, fontweight="bold", loc="left",
                 pad=8)
    labels = ["before\n+X, +Y", "before\n+X, −Y", "now\n+X, +Y", "now\n+X, −Y", "now\nkey-rib\ncorner"]
    vals = [today[0], today[1], new[0], new[1], new[2]]
    cols = [RED, RED, BLUE, BLUE, GREEN]
    xs = np.arange(len(vals))
    ax.axhspan(*PULL_OUT, color="#f2c6c0", alpha=0.6, zorder=0)
    ax.text(len(vals) - 0.45, sum(PULL_OUT) / 2, "insert pull-out,\nestimated", fontsize=10, color="#9b3020",
            ha="right", va="center")
    ax.axhline(YIELD, color="#555", lw=1.0, ls="--", zorder=1)
    ax.text(len(vals) - 0.45, YIELD + 4, "M1 screw yields", fontsize=10, color="#555", ha="right", va="bottom")
    ax.bar(xs, [v * F_JAM for v in vals], color=cols, width=0.62, zorder=2)
    for x, v in zip(xs, vals):
        ax.text(x, v * F_JAM + 4, f"{v * F_JAM:.0f} N\n{v:.2f} F", ha="center", va="bottom", fontsize=10.5)
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel("N per screw", fontsize=11)
    ax.set_ylim(0, 245)
    ax.set_xlim(-0.6, len(vals) - 0.4)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.text(-0.5, 236, f"At the {F_RATED:.0f} N rating: before {max(today) * F_RATED:.0f} N, now "
            f"{max(new) * F_RATED:.0f} N per screw at most.", fontsize=10.5, color="#333", va="top")


def main():
    global NEW_R
    sec_now = body_section(ZF - 1.5, KEY_OLD, inserts=TWO)
    sec_new = body_section(ZF - 1.5, KEY_NEW)
    plain_new = body_section(ZF - 1.5, KEY_NEW, holes=False)
    c_new = L.FRONT_INSERTS[2]
    r_new = inscribed(plain_new, *c_new)
    r_best, c_best = best_corner(plain_new)
    assert r_best - r_new < 0.01, "the third insert is not at the corner's thickest spot"
    r_now, c_now = best_corner(body_section(ZF - 1.5, KEY_OLD, holes=False, inserts=TWO))
    r_front = inscribed(body_section(ZF - 1.5, KEY_OLD, holes=False, inserts=TWO), *TWO[0])
    NEW_R = r_new
    face = body_section(ZF - 0.02, KEY_NEW)
    two = list(TWO)
    today, cont_today = screw_loads(two, face)
    new, cont_new = screw_loads(two + [c_new], face)

    fig = plt.figure(figsize=(19.0, 17.5))
    gs = GridSpec(3, 2, figure=fig, height_ratios=[1.0, 0.82, 0.95], width_ratios=[1.0, 1.0], left=0.012,
                  right=0.99, top=0.98, bottom=0.075, hspace=0.12, wspace=0.05)
    text_panel(fig.add_subplot(gs[0, 0]), today, new, r_now)
    today_view(fig.add_subplot(gs[0, 1]), max(today))
    why_view(fig.add_subplot(gs[1, 0]))
    end_view(fig.add_subplot(gs[1, 1]), sec_now, sec_new, c_new, r_new)
    corner_view(fig.add_subplot(gs[2, 0]), sec_new, c_new, r_new, r_front)
    g6 = GridSpecFromSubplotSpec(1, 2, subplot_spec=gs[2, 1], width_ratios=[0.1, 1.0], wspace=0.0)
    loads_view(fig.add_subplot(g6[1]), today, new)
    fig.text(0.012, 0.012,
             f"V6-{VARIANT} front end, mm. Views 2 and 3: schematic sections through the middle; in view 2 the screw "
             "is drawn in that plane and the tilt is exaggerated.\nViews 4 and 5: sections of the CAD body "
             "(design_v6.make_body) 1.5 mm behind its front face, with the key rib at 2.5 mm; the strip it grew is outlined. "
             "Loads: rigid cap resting on the body's\nfront face, screws as equal springs, the push in the middle. "
             "Real contact spreads inward from the edge, which makes the figure before worse, not better.", fontsize=10.3, color="#444", va="bottom", linespacing=1.3)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    fig.savefig(OUT, dpi=100)
    print("wrote", OUT)
    print(f"corner with the {KEY_OLD} rib: r {r_now:.3f} at ({c_now[0]:.3f}, {c_now[1]:.3f}); rib {KEY_NEW}: insert "
          f"r {r_new:.3f} at ({c_new[0]:.3f}, {c_new[1]:.3f}), largest r {r_best:.3f} at ({c_best[0]:.3f}, "
          f"{c_best[1]:.3f}); +X front insert r {r_front:.3f}")
    print("today per screw (x F):", np.round(today, 3), "contacts", [(round(l, 3), tuple(np.round(p, 2)))
                                                                   for l, p in cont_today])
    print("new per screw (x F):", np.round(new, 3), "contacts", [(round(l, 3), tuple(np.round(p, 2)))
                                                               for l, p in cont_new])


NEW_R = 0.0

if __name__ == "__main__":
    main()

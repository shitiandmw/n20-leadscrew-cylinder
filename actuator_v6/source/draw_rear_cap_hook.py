"""The rear cap's hook on the end of the motor-side wall (images/rear_cap_hook.png), as built.

The rear cap's two screws sit on the board side only, so a pull on the rear pin used to tip the cap about its +X edge
(draw_rear_cap_load.py). Since 11 November 2026 the motor-side (-X) wall is 2.4 mm thick and its end reaches into a
pocket in the rear cap; a 45 degree tooth on the cap sits in a notch cut into the inside of that wall end (the
user's structure). The cap goes on 0.8 mm toward the board side, slides back so the tooth enters the notch, and the
two screws stop it sliding out. The profile is blunt so that it prints true: the user found the first, pointed
version (0.6 mm triangles, drawn for comparison) too sharp. All dimensions come from layout.REAR_HOOK; build_v6.py
checks the same profile on the CAD solids (validation.json, rear_hook).

The stress figures are a beam estimate of tension plus bending in the wall where the notch leaves it thinnest: the
tooth pulls on the inner edge of the wall, off its centre, and the bevel also pushes the wall outward. Section through
the middle (y = 0); the screw on the board side is drawn in the same plane, as in draw_rear_cap_load.py.

    python source/draw_rear_cap_hook.py
"""
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec, GridSpecFromSubplotSpec
from matplotlib.patches import Circle, Polygon, Rectangle

import layout as L
from draw_rear_cap_load import (BODY, CAP, CLAMP, MOTOR, BRASS, STEEL, PIN, RED, BLUE, GREEN, ZR, CAP_T, XS, I, S,
                                CLAMP_Z, EYE_Z, EYE_R, PIN_R, Z_HEAD_TOP, Z_TIP, rect, lug_outline, arrow)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "images", "rear_cap_hook.png")
WOOD = "#7a4a1a"

X1 = L.BODY_X[1]
X0_BEFORE = -6.35                    # the motor-side wall was 1.2 mm before the hook
XI = -L.BORE_X                       # -5.15: inner face of that wall. The motor goes in from the rear, so nothing
BX = L.BORE_X                        # may stick into the bay there: the notch is cut into the wall
YH = L.BODY_Y
ZB = ZR - CAP_T                      # the cap's outer face
Z_BREAK = ZR + 14.0
H = L.REAR_HOOK
PUSH = H["shift"]                    # the cap goes on this far toward the board side, then is pushed back
F_PULL = 85.0                        # N: a jam while pulling at the X1 board's 0.5 A limit (README)
MU = 0.3                             # PETG on PETG
W_HOOK = 2 * H["half_width"]          # 10.9 mm: the flat part of the wall, where the notch runs
PETG_Z = 30.0                        # MPa, printed PETG pulled across its layers (roughly)
LAYER_CAP, LAYER_BODY = 0.16, 0.2    # PRINT_SETTINGS: both parts print with their layers across z


class Joint:
    """End of the motor-side wall and the cap's tooth, 45 degree bevel.

    wall: wall thickness; d: notch depth; c: room under the tooth's tip; f: flat floor of the notch (z); hd: flat
    end of the wall before the bevel (z); cl: room between that end and the cap; r: radius in the notch's inside
    corner; ch: chamfer on the tooth's tip corner (it is on the bed); co, ci: chamfers on the wall's end (outer, inner);
    gap: room between the end of the wall and the pocket floor, which prints as a bridge in the cap."""

    def __init__(self, wall, d, c=0.0, f=0.0, hd=0.0, cl=0.0, r=0.0, ch=0.0, co=0.2, ci=0.0, gap=0.1):
        self.wall, self.d, self.c, self.f, self.hd, self.cl, self.r, self.ch = wall, d, c, f, hd, cl, r, ch
        self.co, self.ci, self.gap = co, ci, gap
        self.x0 = XI - wall
        self.xn = XI - d                         # notch floor
        self.eng = d - c                         # how far the tooth reaches into the wall
        self.xt = XI - self.eng                  # tooth tip
        self.zb = ZR - d - f                     # top of the bevel, on the inner face
        self.lip = hd + d + f                    # how far the end of the wall reaches into the cap
        self.ze = ZR - self.lip
        self.left = wall - d                     # wall left at the notch

    def wall_poly(self):
        pts = ([(self.ze, self.x0 + self.co), (self.ze + self.co, self.x0)] if self.co else [(self.ze, self.x0)])
        pts += [(Z_BREAK, self.x0), (Z_BREAK, XI),
               (ZR, XI), (ZR, self.xn + self.r)]
        if self.r:
            cz, cx = ZR - self.r, self.xn + self.r
            pts += [(cz + self.r * math.cos(t), cx + self.r * math.sin(t))
                    for t in (-math.pi / 2 * k / 8 for k in range(1, 8))]
        pts += [(ZR - self.r, self.xn), (self.zb + self.d, self.xn), (self.zb, XI), (self.ze + self.ci, XI),
                (self.ze, XI - self.ci)]
        return pts

    def cap_poly(self):
        zp, xp = self.ze - self.gap, XI + self.cl
        return [(ZB, self.x0 + 0.4), (ZB + 0.4, self.x0), (zp, self.x0), (zp, xp), (self.zb - self.cl, xp),
                (self.zb + self.eng, self.xt), (ZR - self.ch, self.xt), (ZR, self.xt + self.ch),
                (ZR, X1), (ZB + 0.4, X1), (ZB, X1 - 0.4)]

    def stress(self):
        """Hook force, sideways push of the bevel, and tension + bending where the wall is thinnest (MPa)."""
        a = math.radians(45.0)
        zm, xm = self.zb + self.eng / 2, XI - self.eng / 2        # middle of the contact on the bevel
        h = F_PULL * XS / (XS - xm)                               # the hook and the two screws share the pull
        side = h * (math.cos(a) - MU * math.sin(a)) / (math.sin(a) + MU * math.cos(a))
        xc = (self.x0 + self.xn) / 2
        m = (xm - xc) * h + (ZR - self.r - zm) * side
        return h, side, h / (W_HOOK * self.left) + 6 * m / (W_HOOK * self.left ** 2)


BLUNT = Joint(-L.BODY_X[0] - L.BORE_X, H["notch"], c=H["tip_room"], f=H["floor"], hd=H["head"], cl=H["side_room"],
              r=H["fillet"], ch=H["bed_chamfer"], co=0.0, ci=H["inner_chamfer"], gap=H["end_room"])   # as built
POINTED = Joint(BLUNT.wall, BLUNT.d)                                # the first version, not used
assert abs(BLUNT.lip - H["reach"]) < 1e-9 and abs(BLUNT.ze - L.rear_hook_profile()["ze"]) < 1e-9


def shifted(pts, dx):
    return [(z, x + dx) for z, x in pts]


def break_line(ax, z, x0, x1):
    zz = [z + (0.35 if k % 2 else -0.35) for k in range(12)]
    xx = [x0 - 0.3 + (x1 - x0 + 0.6) * k / 11 for k in range(12)]
    ax.plot(zz, xx, color="white", lw=5, zorder=5)
    ax.plot(zz, xx, color="#888", lw=1, zorder=6)


def layer_lines(ax, patch, z_from, z_to, pitch, color):
    """Faint print layers (planes of constant z) clipped to one part."""
    k = 1
    while True:
        z = z_from - k * pitch if z_to < z_from else z_from + k * pitch
        if (z_to < z_from and z < z_to) or (z_to > z_from and z > z_to):
            break
        ln, = ax.plot([z, z], [-20, 20], color=color, lw=0.6, alpha=0.45, zorder=patch.get_zorder() + 0.5)
        ln.set_clip_path(patch)
        k += 1


def draw_body(ax, j, plus_side=True, before=True, layers=False):
    wall = Polygon(j.wall_poly(), color=BODY, zorder=2)
    ax.add_patch(wall)
    if layers:
        layer_lines(ax, wall, ZR + 3.0, j.ze - 0.01, LAYER_BODY, "#9a5a14")
    if before:
        ax.plot([ZR + 0.4, Z_BREAK], [X0_BEFORE, X0_BEFORE], color=WOOD, lw=1.2, ls=(0, (4, 3)), zorder=3)
    # motor: can, end cap, rear boss; a terminal (it sits 3.65 mm off this section) drawn pale
    ax.add_patch(Polygon(rect(-23.0, Z_BREAK, -5.0, 5.0), color=MOTOR, zorder=1))
    ax.add_patch(Polygon(rect(-24.0, -23.0, -5.0, 5.0), color="#aeb3ba", zorder=1))
    ax.add_patch(Polygon(rect(-25.2, -24.0, -2.5, 2.5), color="#aeb3ba", zorder=1))
    ax.add_patch(Polygon(rect(-26.5, -24.0, -0.75, 0.75), color="#d9dce0", zorder=1))
    if plus_side:
        ax.add_patch(Polygon(rect(ZR, Z_BREAK, BX, X1), color=BODY, zorder=2))
        ax.add_patch(Polygon(rect(ZR, ZR + I["hole_depth"], XS - I["hole"] / 2, XS + I["hole"] / 2), color="white",
                             zorder=3))
        iz0 = ZR + I["recess"]
        ax.add_patch(Polygon(rect(iz0, iz0 + I["length"], XS - I["od"] / 2, XS + I["od"] / 2), color=BRASS, zorder=4))
        break_line(ax, Z_BREAK, j.x0, X1)


def draw_cap(ax, j, dx=0.0, screws=True, layers=False):
    ax.add_patch(Polygon(shifted(lug_outline(), dx), color=CAP, zorder=4))
    cap = Polygon(shifted(j.cap_poly(), dx), color=CAP, zorder=4)
    ax.add_patch(cap)
    if layers:
        layer_lines(ax, cap, ZR, ZB - 1.0, LAYER_CAP, "#9aa0a8")
    if screws:
        ax.add_patch(Polygon(shifted(rect(CLAMP_Z - L.CLAMP_T, CLAMP_Z, L.CLAMP_X0, X1), dx), color=CLAMP, zorder=4))
        ax.add_patch(Circle((EYE_Z, dx), PIN_R, color="#e6e6e6", zorder=5))
        ax.add_patch(Circle((EYE_Z, dx), PIN_R * 0.82, color=PIN, zorder=6))
        ax.plot([Z_HEAD_TOP + S["head_h"], Z_TIP], [XS + dx, XS + dx], color=STEEL, lw=3.2, solid_capstyle="butt",
                zorder=7)
        head = rect(Z_HEAD_TOP, Z_HEAD_TOP + S["head_h"], XS - S["head_d"] / 2, XS + S["head_d"] / 2)
        ax.add_patch(Polygon(shifted(head, dx), color=STEEL, zorder=7))


def frame(ax, title, size=13):
    ax.set_title(title, fontsize=size, fontweight="bold", loc="left", pad=8)
    ax.set_aspect("equal")
    ax.axis("off")


def note(ax, text, xy, xytext, color, ha="left", size=11.5):
    ax.annotate(text, xy=xy, xytext=xytext, fontsize=size, color=color, ha=ha, va="center", zorder=12,
                arrowprops=dict(arrowstyle="-|>", color=color, lw=1.3))


def marker(ax, n, xy, color=BLUE):
    ax.text(*xy, str(n), ha="center", va="center", fontsize=9.5, color="white", fontweight="bold", zorder=14,
            bbox=dict(boxstyle="circle,pad=0.22", fc=color, ec="white", lw=0.8))


def pin(ax, n, at, target, color=BLUE):
    ax.plot([at[0], target[0]], [at[1], target[1]], color=color, lw=1.3, zorder=13)
    ax.plot(*target, "o", ms=3.5, color=color, zorder=13)
    marker(ax, n, at, color)


def left_mark(ax, j, z):
    """Red bar across the wall where the notch leaves it thinnest."""
    ax.plot([z, z], [j.x0, j.xn], color=RED, lw=3.0, solid_capstyle="butt", zorder=11)


def text_panel(ax):
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.text(0.0, 1.0, "Rear cap hooked onto the motor-side wall", fontsize=13.5, fontweight="bold",
            ha="left", va="top")
    h, side, sig = BLUNT.stress()
    sig0 = POINTED.stress()[2]
    k = h / F_PULL
    ax.text(0.01, 0.80,
            f"The end of the {BLUNT.wall:.1f} mm motor-side wall reaches {BLUNT.lip:.1f} mm into a "
            f"{BLUNT.lip + BLUNT.gap:.1f} mm pocket in the rear cap,\nand a 45° tooth on the cap sits in a notch "
            f"inside it. The cap goes on {PUSH:g} mm toward the board\nside, slides back, and the two screws stop it "
            "sliding out. Blunt profile (detail at right): the two\nbevels are the only faces that touch.",
            fontsize=12, ha="left", va="top", color="#222")
    ax.text(0.01, 0.36,
            f"Loads at the X1 board's limit, F = {F_PULL:.0f} N: the bevel holds about {k:.2f} F, each screw about "
            f"{(1 - k) / 2:.2f} F\n({(1 - k) / 2 * F_PULL:.0f} N; before the hook 210–290 N). Wall at the notch, 1.8 mm left: "
            f"about {sig:.0f} MPa (pointed {sig0:.0f}: the blunt\ntooth bears a little further out on the wall). "
            f"Printed PETG holds roughly {PETG_Z:.0f} MPa across its layers.",
            fontsize=12, ha="left", va="top", color="#222")


def main_view(ax):
    ax.set_aspect("equal")
    ax.axis("off")
    j = BLUNT
    draw_body(ax, j)
    draw_cap(ax, j)
    ax.text(ZR + 9.0, 0.0, "motor", ha="center", va="center", fontsize=11, color="#555", zorder=3)
    ax.add_patch(Circle((ZR - 0.8, XI - 1.1), 2.4, fill=False, ec=BLUE, lw=1.6, ls=(0, (4, 2)), zorder=11))
    note(ax, "end of the wall, 1.6 mm into a pocket in the cap,\nwith the bevelled notch (detail at right)",
         (ZR - 1.0, XI - 3.4), (ZR + 3.2, j.x0 - 3.2), BLUE)
    note(ax, "this wall 1.2 mm thicker (2.4 mm);\ndashed line = the outside before", (ZR + 7.0, j.x0 + 0.1),
         (EYE_Z - 9.0, j.x0 - 5.3), WOOD)
    ax.text(Z_HEAD_TOP - 0.5, X1 + 1.0, "2 screws, as before", color="#555", fontsize=11, ha="center", va="bottom")
    arrow(ax, (EYE_Z - PIN_R - 0.3, 0.0), (EYE_Z - 8.0, 0.0), RED, lw=3, ms=20)
    ax.text(EYE_Z - 8.0, 0.8, "pull F", color=RED, fontsize=13, ha="left", va="bottom", fontweight="bold")
    ax.set_xlim(EYE_Z - 9.5, Z_BREAK + 6.0)
    ax.set_ylim(j.x0 - 6.8, X1 + 2.6)


ZOOM = ((ZR - 2.55, ZR + 1.25), (BLUNT.x0 - 0.3, XI + 1.25))


def zoom(ax, window=ZOOM):
    ax.set_xlim(*window[0])
    ax.set_ylim(*window[1])
    ax.set_anchor("W")


def labels(ax, j, dx=0.0):
    ax.text(ZR - 1.9, XI + 0.75 + dx, "cap", color="white", fontsize=10.5, ha="center", va="center", zorder=9,
            clip_on=True)
    ax.text(ZR + 0.75, (j.x0 + j.xn) / 2, "wall", color="#5a3210", fontsize=10.5, ha="center", va="center",
            zorder=9, clip_on=True)


def side_text(ax, text, color="#222"):
    ax.axis("off")
    ax.text(0.0, 0.5, text, transform=ax.transAxes, fontsize=11.2, color=color, ha="left", va="center",
            linespacing=1.35)


def before_view(ax, tx):
    j = POINTED
    frame(ax, "Not used: pointed (0.6 mm triangles)", 12)
    draw_body(ax, j, plus_side=False, before=False, layers=True)
    draw_cap(ax, j, screws=False, layers=True)
    labels(ax, j)
    pin(ax, 1, (ZR - 0.18, XI - 0.18), (ZR - 0.04, j.xn + 0.06), RED)        # in the tooth
    pin(ax, 2, (ZR + 0.42, j.xn - 0.3), (ZR + 0.02, j.xn - 0.02), RED)       # in the wall
    pin(ax, 3, (j.ze - 0.42, XI - 0.45), (j.ze + 0.03, XI - 0.03), RED)      # knife edge on the end of the wall
    zoom(ax)
    side_text(tx, "1  Tip of the tooth: it sits on the bed, and\n    the first layer squashes it outward.\n"
                  "2  Bottom of the V: the printer can't make a\n    sharp inside V, it fills it in.\n"
                  "    1 and 2 meet before the bevels do: the cap\n    stops short and the screw holes miss.\n"
                  "3  Knife edge at the end of the wall: prints\n    ragged and chips off.\n\n"
                  "Faint lines: print layers (cap 0.16 mm,\nbody 0.2 mm). The bevels are only 3–4 layers.")


def after_view(ax, tx):
    j = BLUNT
    frame(ax, "As built: flat tips, rounded corner, room", 12)
    draw_body(ax, j, plus_side=False, before=False, layers=True)
    draw_cap(ax, j, screws=False, layers=True)
    labels(ax, j)
    ax.plot([j.zb, j.zb + j.eng], [XI, j.xt], color=GREEN, lw=4.5, solid_capstyle="butt", zorder=10)
    left_mark(ax, j, ZR - j.r - 0.02)
    pin(ax, 1, (ZR - 0.55, XI - 0.05), (ZR - 0.38, (j.xt + j.xn) / 2))          # room under the flat tip
    pin(ax, 2, (ZR + 0.45, j.xn - 0.35), (ZR - 0.06, j.xn + 0.06))           # rounded inside corner
    marker(ax, 3, (j.zb + 0.25, j.xt - 0.02), GREEN)
    pin(ax, 4, (j.ze + 0.25, XI - 0.6), (j.ze + 0.35, XI - 0.02))            # flat end of the wall
    pin(ax, 5, (j.ze - 0.45, XI + 0.5), (j.ze - j.gap / 2, XI + j.cl / 2))     # room beside and behind it
    zoom(ax)
    side_text(tx, f"1  Flat tip, {j.c:.2f} mm above the notch floor,\n    corner chamfered {j.ch:.1f}: room for "
                  "the first\n    layer, which is printed on the bed.\n"
                  f"2  Rounded inside corner (r {j.r:.1f}): the printer\n    can make it, and the wall is less "
                  "likely\n    to crack there.\n"
                  f"3  The bevels touch only here (green):\n    {j.eng:.2f} mm deep, 45°. Pushing the cap back\n"
                  "    (step 2) still draws it tight.\n"
                  f"4  Flat end on the wall, {j.hd:.1f} mm: no knife edge.\n"
                  f"5  {j.cl:.2f} mm beside the end of the wall, {j.gap:.1f} mm\n    behind it: the bevel is the "
                  "only face\n    that touches inside the pocket.\n"
                  f"Red: {j.left:.1f} mm of wall left at the notch.")


STEP_WIN = ((ZR - 2.55, ZR + 1.0), (BLUNT.x0 - 0.3, XI + 1.6))


def step_view(ax, n):
    j = BLUNT
    dx = PUSH if n == 1 else 0.0
    title = (f"1  On {PUSH:g} mm toward the board side" if n == 1 else
             f"2  Pushed back {PUSH:g} mm, then 2 screws")
    frame(ax, title, 11)
    draw_body(ax, j, plus_side=False, before=False)
    draw_cap(ax, j, dx=dx, screws=False)
    ax.text(ZR - 1.9, XI + 1.1 + dx * 0.4, "cap", color="white", fontsize=10.5, ha="center", va="center",
            zorder=9, clip_on=True)
    ax.text(ZR + 0.5, (j.x0 + j.xn) / 2, "wall", color="#5a3210", fontsize=10.5, ha="center", va="center",
            zorder=9, clip_on=True)
    if n == 1:
        arrow(ax, (ZR - 2.45, j.x0 + 0.2), (ZR - 1.75, j.x0 + 0.2), RED, lw=2.0, ms=12)
    else:
        arrow(ax, (ZR - 2.25, j.x0 + 1.6), (ZR - 2.25, j.x0 + 0.6), RED, lw=2.0, ms=12)
    zoom(ax, STEP_WIN)


def print_view(ax):
    """How the two parts print: the cap flat face down as before; the body on its front end (schematic)."""
    frame(ax, "How they print", 12)
    j = BLUNT
    # cap: face ZR on the bed; u = x, v = height above the bed
    cap = [(x, ZR - z) for z, x in j.cap_poly()]
    lug = [(x, ZR - z) for z, x in lug_outline()]
    bed_y = -0.6
    ax.add_patch(Rectangle((j.x0 - 1.0, bed_y), X1 - j.x0 + 2.0, 0.6, facecolor="#e8e8e8", edgecolor="#999",
                           hatch="////", lw=0.6, zorder=1))
    ax.add_patch(Polygon(lug, color=CAP, zorder=4))
    ax.add_patch(Polygon(cap, color=CAP, zorder=4))
    ax.text((j.x0 + X1) / 2, -1.5, "rear cap: flat face down, as before;\nthe pocket for the end of the wall\n"
            "is bridged, so no support", fontsize=11, ha="center", va="top", color="#222")
    ax.add_patch(Circle((j.x0 + 1.4, 0.9), 1.9, fill=False, ec=BLUE, lw=1.4, ls=(0, (3, 2)), zorder=6))
    # body: front end on the bed; front end, motor wall and rear end, with two breaks (not to scale in z)
    ox = 30.0
    ax.add_patch(Rectangle((ox + j.x0 - 1.0, bed_y), X1 - j.x0 + 2.0, 0.6, facecolor="#e8e8e8", edgecolor="#999",
                           hatch="////", lw=0.6, zorder=1))
    top = 15.0

    def slab(v0, v1, x0, x1):
        ax.add_patch(Polygon([(ox + x0, v0), (ox + x1, v0), (ox + x1, v1), (ox + x0, v1)], color=BODY, zorder=2))

    slab(0.0, top, j.x0, -BX)
    slab(0.0, top, BX, X1)
    slab(7.0, 9.0, -BX, BX)                                    # motor wall: a bridge either way
    lip = [(ox + x, top + (ZR - min(z, ZR))) for z, x in j.wall_poly()]
    ax.add_patch(Polygon(lip, color=BODY, zorder=2))
    for v in (4.0, 12.0):
        zz = [ox + j.x0 - 0.5 + (X1 - j.x0 + 1.0) * k / 11 for k in range(12)]
        vv = [v + (0.3 if k % 2 else -0.3) for k in range(12)]
        ax.plot(zz, vv, color="white", lw=6, zorder=3)
        ax.plot(zz, vv, color="#888", lw=1, zorder=4)
    ax.text(ox, 2.0, "rod bore", fontsize=9.5, color="#666", ha="center", va="center")
    ax.text(ox, 13.6, "motor bay", fontsize=9.5, color="#666", ha="center", va="center")
    ax.text(ox + (j.x0 + X1) / 2, -1.5, "body: front end down (before the hook: rear end down)", fontsize=11, ha="center",
            va="top", color="#222")
    note(ax, f"rear end on top: the end of the\nwall sticks up {j.lip:.1f} mm; its bevel\nprints as a 45° overhang",
         (ox + j.x0 + 0.8, top + 1.0), (ox + X1 + 2.5, 14.4), "#222", size=10.5)
    note(ax, "motor wall: still a bridge, but\nthe motor seat is now its top\nface; the screw countersinks\n"
             "and the board rest come out\non its underside", (ox + 3.0, 8.0), (ox + X1 + 2.5, 6.4), "#222",
         size=10.5)
    ax.set_xlim(j.x0 - 3.0, ox + X1 + 19.5)
    ax.set_ylim(-5.2, top + j.lip + 0.8)
    ax.set_anchor("W")


def main():
    fig = plt.figure(figsize=(18.0, 14.0))
    gs = GridSpec(1, 2, figure=fig, width_ratios=[1.12, 1.0], left=0.012, right=0.995, top=0.975, bottom=0.065,
                  wspace=0.04)
    gl = GridSpecFromSubplotSpec(3, 1, subplot_spec=gs[0], height_ratios=[0.5, 1.5, 0.9], hspace=0.06)
    gr = GridSpecFromSubplotSpec(3, 1, subplot_spec=gs[1], height_ratios=[1.0, 1.0, 0.72], hspace=0.2)
    text_panel(fig.add_subplot(gl[0]))
    main_view(fig.add_subplot(gl[1]))
    print_view(fig.add_subplot(gl[2]))
    g0 = GridSpecFromSubplotSpec(1, 2, subplot_spec=gr[0], width_ratios=[1.0, 1.0], wspace=0.03)
    before_view(fig.add_subplot(g0[0]), fig.add_subplot(g0[1]))
    g1 = GridSpecFromSubplotSpec(1, 2, subplot_spec=gr[1], width_ratios=[1.0, 1.0], wspace=0.03)
    after_view(fig.add_subplot(g1[0]), fig.add_subplot(g1[1]))
    gs3 = GridSpecFromSubplotSpec(1, 2, subplot_spec=gr[2], wspace=0.06)
    step_view(fig.add_subplot(gs3[0]), 1)
    step_view(fig.add_subplot(gs3[1]), 2)
    fig.text(0.012, 0.012,
             "Section through the middle, mm; the screw is drawn in this plane. Dimensions from source/layout.py "
             "(REAR_HOOK); the CAD solids are checked in validation.json (rear_hook). The end of the wall and the "
             f"notch run along\nthe flat part of the wall ({W_HOOK:.1f} mm); the pocket in the cap is closed at both "
             "ends. Stress: tension plus bending in the wall at the notch, beam estimate, friction 0.3.",
             fontsize=10.5, color="#444", va="bottom")
    fig.savefig(OUT, dpi=100)
    print("wrote", OUT)
    for name, j in (("pointed", POINTED), ("blunt", BLUNT)):
        h, side, sig = j.stress()
        print(f"{name}: hook {h:.1f} N ({h / F_PULL:.2f} F), side {side:.1f} N, left {j.left:.1f} mm, "
              f"{sig:.1f} MPa, lip {j.lip:.2f}, tooth tip {j.xt:.2f}")


if __name__ == "__main__":
    main()

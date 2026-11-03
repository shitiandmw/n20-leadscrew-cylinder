"""X1 swing drive and wiring through the swing joint: concept sketch for review, not CAD.

Sheet 1: arrangement (section on the centreline, plan view, slip-ring detail).
Sheet 2: options, sizing, what full-size and RC excavators do, and the decisions needed before modelling.

X1 parts (X-frame, RU66, tracks) come from the X1 source. The new parts are proposals, sized from:
- the JGY-370 envelope and the Pololu #1999 hub in the J9 model;
- the Prosper SRC022 series datasheet for the SRC022A-6 slip ring (sold as Adafruit 736), in ../references/prosper_src022/.
"""
import math, sys, textwrap
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly, Circle, Rectangle, FancyBboxPatch, FancyArrowPatch, Wedge
from matplotlib.backends.backend_pdf import PdfPages
from shapely.geometry import LineString

HERE = Path(__file__).resolve().parent
OUT = HERE.parent                                     # track_wheel_jgy370/X1/swing_concept
sys.path.insert(0, str(OUT.parent / 'source'))        # X1/source
import x1_parts as X                                  # noqa: E402
from x1_parts import P9, D9                           # noqa: E402

INK, GREY, LIGHT = '#1d2b2f', '#5f6f75', '#9aa7ab'
XF, XF_L = '#f2c230', '#f9e3a0'                       # X-frame as built
BRG, BRG_L = '#7f8c8d', '#d5dbdb'                     # RU66
NEW, NEW_L = '#d35400', '#f8c9a0'                     # proposed printed parts
BUY, BUY_L = '#34495e', '#aeb6bf'                     # bought parts
SLIP, SLIP_L = '#1f618d', '#aed6f1'                   # slip ring
TT = '#2471a3'                                        # turntable (future)
RED, BLUE, GREEN = '#c0392b', '#2874a6', '#1e8449'    # track-motor leads, slip-ring fixed leads, rotor leads

# --- proposed swing gearing (concept): ring gear fixed on the carbody top, pinion on the turntable
MOD, Z_RING, Z_PIN = 1.5, 80, 20
R_RING, R_PIN = MOD*Z_RING/2, MOD*Z_PIN/2             # pitch radii 60 / 15
CD = R_RING + R_PIN                                   # 75: pinion axis from the swing axis
RING_TIP, RING_ROOT, RING_BORE = R_RING + MOD, R_RING - 1.25*MOD, 49.0
PIN_TIP, PIN_ROOT = R_PIN + MOD, R_PIN - 1.25*MOD
GEAR_Z, PIN_Z = (85.0, 97.0), (87.0, 97.0)            # pinion 2 mm above the leg tops (Z 85)
DECK_Z = (101.0, 107.0)                               # turntable deck: 1 mm above the RU66 outer ring
RATIO = Z_RING/Z_PIN
HUB = D9.HUB                                          # Pololu #1999, as on the J9 sprocket
SHAFT_LEN = D9.SHAFT_TIP_Y - D9.GEARBOX_FACE_Y        # 15.6 beyond the gearbox face
# JGY-370 envelope from the J9 model; here the shaft points down and the can points to the rear
GB_FRONT, GB_REAR = D9.DRIVE_X - P9.GB_X[0], P9.GB_X[1] - D9.DRIVE_X       # 14.5 / 31.5 from the shaft
CAN_END = P9.CAN_X[1] - D9.DRIVE_X                    # 62.3
GB_DEPTH = P9.GB_Y[1] - P9.GB_Y[0]                    # 23
GB_HALF = (P9.GB_Z[1] - P9.GB_Z[0])/2                 # 16
CAN_R = P9.TUBE_R - P9.POD_CLEAR - P9.POD_WALL        # 12
CAN_AX = D9.GEARBOX_FACE_Y - P9.CAN_Y                 # 13.2 above the face
PX = -CD                                              # pinion at the rear, on the centreline
# --- slip ring SRC022A-6 (Prosper SRC022 datasheet, type A): stator body, flange at the rotor end, rotor
SR = dict(body_r=11.0, body_l=19.0, flange_r=22.0, flange_t=2.4, hole_r=2.75, pcd_r=17.5, rotor_r=3.9, rotor_l=9.0)
BOSS_Z, BOSS_R = (71.0, 79.0), 4.5                    # three new bosses under the top plate (M3 inserts from below)
FL_Z = (BOSS_Z[0] - SR['flange_t'], BOSS_Z[0])        # 68.6-71
BODY_Z = (FL_Z[0] - SR['body_l'], FL_Z[0])            # 49.6-68.6
ROTOR_Z = (BOSS_Z[0], BOSS_Z[0] + SR['rotor_l'])      # 71-80
TUBE = dict(ro=10.0, ri=7.0, z0=ROTOR_Z[1] + 1.0)     # turntable driver tube in the passage (R 12.5)

PLATE_Z = X.TOP_Z - X.PLATE_T                         # 79
RELIEF_Z = X.TOP_Z - X.RELIEF_DEPTH                   # 82.5


# ------------------------------------------------------------------ helpers
def patch(ax, pts, fc='none', ec=INK, lw=.6, hatch=None, ls='-', z=3, alpha=1.0):
    ax.add_patch(MPoly(pts, closed=True, fc=fc, ec=ec, lw=lw, hatch=hatch, ls=ls, zorder=z, alpha=alpha))


def box(ax, x0, z0, x1, z1, **k):
    patch(ax, [(x0, z0), (x1, z0), (x1, z1), (x0, z1)], **k)


def both(ax, r0, r1, z0, z1, **k):
    """A ring cut through its axis: the same rectangle on each side."""
    box(ax, r0, z0, r1, z1, **k)
    box(ax, -r1, z0, -r0, z1, **k)


def note(ax, xy, txt, text, fs=7.2, color=INK, ha='left', va='center', relpos=None):
    props = dict(arrowstyle='-', lw=.5, color=color, shrinkA=1, shrinkB=0)
    if relpos:
        props['relpos'] = relpos
    ax.annotate(text, xy, txt, fontsize=fs, color=color, ha=ha, va=va, arrowprops=props, zorder=12)


def dim_v(ax, x, z0, z1, text, side=1, fs=7, color=INK):
    ax.annotate('', (x, z0), (x, z1), arrowprops=dict(arrowstyle='<->', lw=.55, color=color, shrinkA=0, shrinkB=0), zorder=11)
    ax.text(x + side*1.8, (z0 + z1)/2, text, rotation=90, va='center', ha='left' if side > 0 else 'right', fontsize=fs, color=color, zorder=12)


def dim_h(ax, x0, x1, z, text, side=1, fs=7, color=INK):
    ax.annotate('', (x0, z), (x1, z), arrowprops=dict(arrowstyle='<->', lw=.55, color=color, shrinkA=0, shrinkB=0), zorder=11)
    ax.text((x0 + x1)/2, z + side*1.5, text, ha='center', va='bottom' if side > 0 else 'top', fontsize=fs, color=color, zorder=12)


def under_z(r):
    (r0, z0), (r1, z1) = X.UNDER
    return z0 if r <= r0 else (z1 if r >= r1 else z0 + (r - r0)/(r1 - r0)*(z1 - z0))


def frame_side_silhouette():
    """Side projection of the X-frame half behind the cut (Y > 0): top Z 85, bottom along the sloped underside."""
    outline, bottom = X.plan_outline(), []
    for x in np.linspace(-96, 96, 385):
        g = outline.intersection(LineString([(x, 0), (x, 130)]))
        if not g.is_empty:
            bottom.append((x, under_z(math.hypot(x, g.bounds[1]))))
    return bottom + [(bottom[-1][0], X.TOP_Z), (bottom[0][0], X.TOP_Z)]


def stadium(x0, x1, z0, z1, n=40):
    r, zc = (z1 - z0)/2, (z0 + z1)/2
    right = [(x1 - r + r*math.cos(t), zc + r*math.sin(t)) for t in np.linspace(-math.pi/2, math.pi/2, n)]
    left = [(x0 + r + r*math.cos(t), zc + r*math.sin(t)) for t in np.linspace(math.pi/2, 1.5*math.pi, n)]
    return right + left


def gear_outline(cx, cy, n, r_tip, r_root, phase=0.0):
    """Plan outline of a spur gear, simplified to trapezoid teeth (sketch only)."""
    pts = []
    for k in range(n):
        a = phase + 2*math.pi*k/n
        for da, r in ((-.30, r_root), (-.16, r_tip), (.16, r_tip), (.30, r_root)):
            t = a + da*2*math.pi/n
            pts.append((cx + r*math.cos(t), cy + r*math.sin(t)))
    return pts


def ru66_section(ax, rollers=True):
    hb = dict(fc=BRG_L, ec=BRG, hatch='\\\\\\\\', lw=.6, z=4)
    zm = X.SEAT_Z + X.RU66['B']/2
    both(ax, X.RU66['Dh_min']/2 + .5, X.RU66['D']/2, X.SEAT_Z, zm, **hb)
    both(ax, X.RU66['ds_max']/2 + .5, X.RU66['D']/2, zm, X.TURNTABLE_Z, **hb)
    both(ax, X.RU66['d']/2, X.RU66['Dh_min']/2 - .5, X.SEAT_Z, zm, **hb)
    both(ax, X.RU66['d']/2, X.RU66['ds_max']/2 - .5, zm, X.TURNTABLE_Z, **hb)
    if rollers:
        for s in (1, -1):
            c = (s*X.RU66['dp']/2, zm)
            patch(ax, [(c[0] + 2.6, c[1]), (c[0], c[1] + 2.6), (c[0] - 2.6, c[1]), (c[0], c[1] - 2.6)], fc='white', ec=BRG, lw=.6, z=5)


def carbody_section(ax, bosses=True):
    hx = dict(fc=XF_L, ec='#b9770e', hatch='////', lw=.6, z=3)
    both(ax, X.BODY_R - X.BODY_WALL, X.BODY_R, X.BOTTOM_Z, PLATE_Z, **hx)             # wall
    both(ax, X.RELIEF_R, X.BODY_R, PLATE_Z, X.TOP_Z, **hx)                             # top plate outside the relief
    both(ax, X.PASSAGE_R, X.RELIEF_R, PLATE_Z, RELIEF_Z, **hx)                         # thinner plate under the relief
    both(ax, X.MOUNT_RING[0], X.MOUNT_RING[1], X.MOUNT_RING[2], PLATE_Z, **hx)          # ring under the seat inserts
    if bosses:   # proposed X-frame change: three bosses for the slip-ring flange, one in the cut, one behind it
        box(ax, SR['pcd_r'] - BOSS_R, BOSS_Z[0], SR['pcd_r'] + BOSS_R, BOSS_Z[1], fc=XF_L, ec=NEW, hatch='////', lw=.9, z=3)
        bx = SR['pcd_r']*math.cos(math.radians(120))
        box(ax, bx - BOSS_R, BOSS_Z[0], bx + BOSS_R, BOSS_Z[1], fc='none', ec=NEW, lw=.7, ls='--', z=3)


def slip_ring(ax, wires=True, screws=True):
    box(ax, -SR['flange_r'], FL_Z[0], SR['flange_r'], FL_Z[1], fc=SLIP_L, ec=SLIP, lw=.8, z=6)
    box(ax, -SR['body_r'], BODY_Z[0], SR['body_r'], BODY_Z[1], fc=SLIP_L, ec=SLIP, lw=.8, z=6)
    for zz in np.linspace(BODY_Z[0] + 3, BODY_Z[1] - 3, 5):
        ax.plot([-SR['body_r'] + 1, SR['body_r'] - 1], [zz, zz], color=SLIP, lw=.5, zorder=7)
    box(ax, -SR['rotor_r'], ROTOR_Z[0], SR['rotor_r'], ROTOR_Z[1], fc='#5dade2', ec=SLIP, lw=.8, z=6)
    if screws:   # M3 through the flange into the boss inserts: one in the cut
        x = SR['pcd_r']
        box(ax, x - 2.75, FL_Z[0] - 2.6, x + 2.75, FL_Z[0], fc=BUY, ec=BUY, lw=.5, z=7)     # head under the flange
        box(ax, x - 1.5, FL_Z[0], x + 1.5, FL_Z[0] + 8.0, fc=BUY_L, ec=BUY, lw=.5, z=7)
        box(ax, x - 2.0, BOSS_Z[1] - 5.7, x + 2.0, BOSS_Z[1], fc='none', ec='#b7950b', lw=.6, ls='--', z=7)  # insert
    if wires:
        ax.plot([0, 0], [ROTOR_Z[1], 101], color=GREEN, lw=1.6, zorder=8)                # rotor leads, up
        for dx in (-3, 3):
            ax.plot([dx, dx*3, dx*6], [BODY_Z[0], BODY_Z[0] - 4, BODY_Z[0] - 8], color=BLUE, lw=1.3, zorder=8)


def driver_tube(ax):
    """Turntable part (future): a tube down the passage whose slot turns the slip-ring rotor's lead bundle."""
    for s in (1, -1):
        box(ax, s*TUBE['ri'], TUBE['z0'], s*TUBE['ro'], DECK_Z[0], fc='#d6eaf8', ec=TT, lw=.7, ls='--', z=5)


# ------------------------------------------------------------------ sheet 1
def section_view(ax):
    ax.set_title('SECTION A–A on the centreline, seen from the right-hand side (front to the right)', fontsize=10.5, loc='left', weight='bold')
    # behind the cut: the left track and the left half of the X-frame (legs and rail)
    L = 308.6
    patch(ax, stadium(-L/2, L/2, 0, 92.4), fc='#eef0f1', ec=LIGHT, lw=.6, ls='--', z=0)
    ax.text(100, 14, 'left track\n(behind the cut)', fontsize=6.8, color=GREY, ha='center')
    patch(ax, frame_side_silhouette(), fc='#fbf1cf', ec='#d4ac0d', lw=.5, ls='--', z=1)
    patch(ax, list(X.rail_profile().exterior.coords), fc='#fbf1cf', ec='#d4ac0d', lw=.5, ls='--', z=1)
    ax.text(66, 66, 'leg and rail\n(behind)', fontsize=6.5, color='#9a7d0a', ha='left')
    ax.plot([-178, 150], [0, 0], color='#6b4f2a', lw=1.2, zorder=0)
    # the cut: X-frame carbody, belly cover, RU66 and one seat screw (dashed: it is not in this plane)
    carbody_section(ax)
    box(ax, -X.BODY_R, X.COVER_Z[0], X.BODY_R, X.COVER_Z[1], fc='#808b96', ec=INK, lw=.5, z=3)
    ru66_section(ax)
    x = X.RU66['outer_pcd']/2
    box(ax, x - 3.5, X.TURNTABLE_Z - 4.4, x + 3.5, X.TURNTABLE_Z - .4, fc='none', ec=BUY, lw=.5, ls='--', z=6)
    box(ax, x - 2, X.TURNTABLE_Z - 4.4 - 16, x + 2, X.TURNTABLE_Z - 4.4, fc='none', ec=BUY, lw=.5, ls='--', z=6)
    # NEW: ring gear on the carbody top (one screw shown dashed), pinion on the turntable
    hn = dict(fc=NEW_L, ec=NEW, hatch='xxx', lw=.8, z=5)
    both(ax, RING_BORE, RING_TIP, *GEAR_Z, **hn)
    for s in (1, -1):
        ax.plot([s*RING_ROOT]*2, GEAR_Z, color=NEW, lw=.5, zorder=6)
    xs = X.BODY_R - 6.5
    box(ax, xs - 1.5, X.TOP_Z - 4, xs + 1.5, GEAR_Z[1], fc='none', ec=BUY, lw=.5, ls='--', z=7)
    box(ax, PX - PIN_TIP, PIN_Z[0], PX + PIN_TIP, PIN_Z[1], **hn)
    for s in (1, -1):
        ax.plot([PX + s*PIN_ROOT]*2, PIN_Z, color=NEW, lw=.5, zorder=6)
    # bought: Pololu hub, shaft, JGY-370 swing motor (shaft down, can to the rear)
    hb = dict(fc=BUY_L, ec=BUY, lw=.7, z=6)
    box(ax, PX - HUB['flange_r'], PIN_Z[1], PX + HUB['flange_r'], PIN_Z[1] + HUB['flange_t'], **hb)
    box(ax, PX - HUB['boss_r'], PIN_Z[1] + HUB['flange_t'], PX + HUB['boss_r'], PIN_Z[1] + HUB['flange_t'] + HUB['boss_h'], **hb)
    box(ax, PX - 3, DECK_Z[1] - SHAFT_LEN, PX + 3, DECK_Z[1], fc='#566573', ec=INK, lw=.5, z=7)
    for dx in (-HUB['pcd_r'], HUB['pcd_r']):
        box(ax, PX + dx - 1.5, PIN_Z[0], PX + dx + 1.5, PIN_Z[1] + 4.5, fc='none', ec=INK, lw=.5, ls='--', z=7)
    box(ax, PX - GB_REAR, DECK_Z[1], PX + GB_FRONT, DECK_Z[1] + GB_DEPTH, fc='#d4ac6e', ec='#7e5109', lw=.8, z=6)
    zc = DECK_Z[1] + CAN_AX
    box(ax, PX - CAN_END, zc - CAN_R, PX - GB_REAR, zc + CAN_R, fc='#bfc9ca', ec=INK, lw=.8, z=6)
    ax.text(PX - (GB_REAR - GB_FRONT)/2, DECK_Z[1] + GB_DEPTH/2, 'JGY-370\ngearbox', fontsize=6.3, ha='center', va='center', color='#7e5109', zorder=8)
    ax.text(PX - (CAN_END + GB_REAR)/2, zc, 'motor', fontsize=6.3, ha='center', va='center', color=INK, zorder=8)
    for dx in (9.0, -24.0):                                                             # 2 of the 4 motor screws
        box(ax, PX + dx - 1.5, DECK_Z[0], PX + dx + 1.5, DECK_Z[1] + 3, fc='none', ec=INK, lw=.5, ls='--', z=7)
    # FUTURE: turntable deck with a spigot on the inner ring and the driver tube
    dk = dict(fc='#eaf2f8', ec=TT, lw=.8, ls='--', z=2, alpha=.9)
    box(ax, -178, DECK_Z[0], PX - 14, DECK_Z[1], **dk)
    box(ax, PX + 14, DECK_Z[0], -TUBE['ro'], DECK_Z[1], **dk)
    box(ax, TUBE['ro'], DECK_Z[0], 150, DECK_Z[1], **dk)
    for s in (1, -1):
        box(ax, s*TUBE['ro'], X.TURNTABLE_Z, s*(X.RU66['ds_max']/2), DECK_Z[0], fc='#eaf2f8', ec=TT, lw=.8, ls='--', z=2)
    driver_tube(ax)
    ax.text(-56, 110, 'turntable deck (future)', fontsize=6.8, color=TT)
    ax.add_patch(FancyBboxPatch((66, 116), 64, 24, boxstyle='round,pad=1.2', fc='#e9f7ef', ec=GREEN, lw=.9, zorder=6))
    ax.text(98, 128, 'battery, receiver\nand motor drivers\n(all in the upper)', fontsize=6.8, ha='center', va='center', color=GREEN, zorder=7)
    # slip ring and wiring
    slip_ring(ax)
    ax.plot([0, 0, 64.8], [101, 112, 126], color=GREEN, lw=1.6, zorder=8)
    ax.text(-3, 118, 'rotor leads', fontsize=6.5, color=GREEN, ha='right')
    ax.plot([PX - CAN_END, PX - CAN_END - 6, PX - CAN_END - 6, 60, 64.8], [zc, zc, 150, 150, 136], color=INK, lw=1.1, zorder=8)
    ax.text(-40, 152.5, 'swing motor leads (they stay in the upper)', fontsize=6.5, color=INK)
    for s in (1, -1):                                                                    # track-motor leads from the side holes
        ax.add_patch(Circle((s*4, X.CABLE_HOLE['z']), X.CABLE_HOLE['r'], fill=False, ec=RED, lw=.6, ls='--', zorder=7))
        ax.plot([s*18, s*24, s*9], [BODY_Z[0] - 8, X.CABLE_HOLE['z'] - 6, X.CABLE_HOLE['z'] - 1], color=RED, lw=1.3, zorder=8)
        box(ax, s*18 - 3, BODY_Z[0] - 10.5, s*18 + 3, BODY_Z[0] - 5.5, fc='white', ec=INK, lw=.6, z=9)        # connector
    # dimensions and centre lines
    dim_v(ax, -172, 0, X.TOP_Z, 'Z 85: seat and leg tops', side=-1)
    dim_v(ax, -97, PIN_Z[0], PIN_Z[1], '10', side=-1, fs=6.5)
    dim_h(ax, PX, 0, 205, f'{CD:g}: pinion axis from the swing axis')
    ax.plot([PX, PX], [DECK_Z[1] + GB_DEPTH + 2, 204], color=LIGHT, lw=.5, ls='-.', zorder=1)
    ax.plot([0, 0], [-6, 207], color=LIGHT, lw=.6, ls='-.', zorder=1)
    dim_v(ax, 136, 0, X.TURNTABLE_Z, 'Z 100: turntable face', side=1)
    # labels: upper parts above, lower parts below the ground line
    note(ax, (-100, 127), (-196, 197), 'swing motor ON THE TURNTABLE:\nJGY-370-1260 200:1, the same motor\nas the tracks; shaft down through\nthe deck, 4 × M3 into the gearbox',
         va='top', relpos=(.4, 0))
    note(ax, (-8, 93), (-26, 182), 'driver tube (part of the turntable)\nturns the slip-ring rotor', color=TT, ha='right', relpos=(1, .5))
    note(ax, (40, 97), (14, 184), 'RU66 (X1): outer ring bolted to the X-frame,\ninner ring turns with the turntable', relpos=(.2, 0))
    note(ax, (-82, 87.5), (-196, -9), 'NEW pinion: printed, 20 teeth,\n10 wide, on a Pololu #1999 hub\n(as the J9 sprocket); 2 mm\nabove the leg tops', color=NEW, va='top', relpos=(.6, 1))
    note(ax, (-56, 86), (-122, -9), 'NEW ring gear on the X-frame:\nprinted, module 1.5, 80 teeth,\npitch Ø120, 12 high;\n6 × M3 into the carbody top', color=NEW, va='top', relpos=(.6, 1))
    note(ax, (-11, 58), (-46, -9), 'slip ring SRC022A-6 (detail C):\nfixed half on 3 new bosses\nunder the top plate;\n6 rings × 2 A', color=SLIP, va='top', relpos=(.6, 1))
    note(ax, (22, 40), (32, -9), "track-motor leads (red) come in\nthrough the Ø10 side holes and\njoin the slip ring's fixed leads,\nbehind the belly cover", color=RED, va='top', relpos=(.2, 1))
    ax.set_xlim(-198, 152); ax.set_ylim(-46, 216); ax.set_aspect('equal'); ax.axis('off')


def plan_view(ax):
    ax.set_title('PLAN VIEW, turntable removed (front to the right)', fontsize=10.5, loc='left', weight='bold')
    L = 308.6
    for s in (1, -1):
        ax.add_patch(Rectangle((-L/2, s*X.TRACK_Y - 35), L, 70, fc='#d5d8dc', ec=LIGHT, lw=.6, zorder=0))
        ax.add_patch(Rectangle((X.RAIL_X[0], min(s*X.RAIL_IN_Y, s*X.BOSS_FACE_Y)), X.RAIL_X[1] - X.RAIL_X[0], X.RAIL_T,
                               fc=XF, ec='#b9770e', lw=.5, zorder=2))
        # X1 cable route: open to view between the legs, hidden under the carbody top inside it
        ax.plot([-18.6, 0, 0], [s*126.8, s*126.8, s*X.BODY_R], color=RED, lw=1.1, zorder=6)
        ax.plot([0, 0], [s*X.BODY_R, s*50], color=RED, lw=1.0, ls=(0, (2, 1.5)), zorder=6)
    ax.text(0, 170, 'left track', fontsize=7, color=GREY, ha='center', va='center')
    ax.text(0, -170, 'right track', fontsize=7, color=GREY, ha='center', va='center')
    patch(ax, list(X.plan_outline().exterior.coords), fc=XF, ec='#b9770e', lw=.6, z=1)
    ax.add_patch(Circle((0, 0), X.RESERVE_R, fill=False, ec=TT, lw=.8, ls='--', zorder=3))
    ax.text(-128, -152, 'swing circle R 189', fontsize=6.8, color=TT, rotation=40)
    patch(ax, gear_outline(0, 0, Z_RING, RING_TIP, RING_ROOT), fc=NEW_L, ec=NEW, lw=.5, z=4)
    ax.add_patch(Circle((0, 0), RING_BORE, fc=XF, ec=NEW, lw=.5, zorder=4))
    ax.add_patch(Circle((0, 0), X.RU66['D']/2, fc=BRG_L, ec=BRG, lw=.6, zorder=5))
    ax.add_patch(Circle((0, 0), X.RU66['d']/2, fc='white', ec=BRG, lw=.6, zorder=5))
    ax.add_patch(Circle((0, 0), CD, fill=False, ec=NEW, lw=.7, ls=(0, (4, 3)), zorder=4))
    patch(ax, gear_outline(PX, 0, Z_PIN, PIN_TIP, PIN_ROOT, phase=math.pi/Z_PIN), fc=NEW, ec='#873600', lw=.5, z=7)
    ax.add_patch(Rectangle((PX - GB_REAR, -GB_HALF), GB_REAR + GB_FRONT, 2*GB_HALF, fill=False, ec='#7e5109', lw=.7, ls='--', zorder=8))
    ax.add_patch(Rectangle((PX - CAN_END, -CAN_R), CAN_END - GB_REAR, 2*CAN_R, fill=False, ec=INK, lw=.7, ls='--', zorder=8))
    ax.add_patch(Circle((0, 0), SR['flange_r'], fill=False, ec=SLIP, lw=.7, ls='--', zorder=6))
    ax.add_patch(Circle((0, 0), SR['body_r'], fc=SLIP_L, ec=SLIP, lw=.6, zorder=6))
    for a in (0, 120, 240):
        ax.add_patch(Circle(X.polar(SR['pcd_r'], a), BOSS_R, fill=False, ec=NEW, lw=.6, zorder=6))
    for s in (1, -1):   # section line A-A; the arrows give the viewing direction (from the right-hand side)
        ax.annotate('', (s*200, 24), (s*200, 0), arrowprops=dict(arrowstyle='-|>', lw=1.0, color=INK))
        ax.text(s*200 + s*9, 4, 'A', fontsize=10, weight='bold', ha='center')
    ax.plot([-200, 200], [0, 0], color=INK, lw=.7, ls='-.', zorder=9)
    note(ax, (PX - 10, 9), (-214, 104), 'swing motor and\npinion, on the\nturntable at the\nrear; the pinion\nwalks round the\nring gear', color=NEW, va='top', fs=6.8, relpos=(.8, 0))
    note(ax, (CD*math.cos(math.radians(-50)), CD*math.sin(math.radians(-50))), (98, -46),
         'pinion path R 75:\npasses 2 mm over the legs', color=NEW, fs=6.8, relpos=(0, .5))
    note(ax, (RING_TIP*math.cos(math.radians(40)), RING_TIP*math.sin(math.radians(40))), (80, 92),
         'ring gear Ø123\naround the RU66 (Ø95)', color=NEW, fs=6.8, relpos=(0, .5))
    note(ax, (8, 6), (100, 46), 'slip ring Ø22, on 3 new\nbosses under the top plate', color=SLIP, fs=6.8, relpos=(0, .5))
    note(ax, (0, 60), (22, 140), 'X1 cable routes:\npod nose port → Ø10 hole', color=RED, fs=6.8, va='center', relpos=(0, .5))
    ax.annotate('front', (218, -186), (175, -186), fontsize=9, weight='bold', va='center', arrowprops=dict(arrowstyle='->', lw=1))
    ax.set_xlim(-216, 222); ax.set_ylim(-212, 212); ax.set_aspect('equal'); ax.axis('off')


def slip_detail(ax):
    ax.set_title('DETAIL C: slip ring at the swing centre (twice the scale of A–A)', fontsize=10.5, loc='left', weight='bold')
    carbody_section(ax)
    ru66_section(ax, rollers=False)
    driver_tube(ax)
    slip_ring(ax)
    for s in (1, -1):
        ax.plot([s*8, s*14], [BODY_Z[0] - 8, BODY_Z[0] - 11], color=BLUE, lw=1.3, zorder=8)
    dim_h(ax, -SR['body_r'], SR['body_r'], 52, 'Ø22', side=1, fs=6.8)
    dim_v(ax, -14, BODY_Z[0], FL_Z[0], '19', side=-1, fs=6.8)
    dim_v(ax, -6, ROTOR_Z[0], ROTOR_Z[1], '9', side=-1, fs=6.5)
    note(ax, (-20, FL_Z[0]), (-44, 60), 'flange Ø44 × 2.4,\n3 × Ø5.5 on Ø35', color=SLIP, fs=6.8, relpos=(1, .5))
    note(ax, (SR['pcd_r'] + BOSS_R, 74), (27, 68), 'NEW boss\n(X-frame change):\nM3 insert from below', color=NEW, fs=6.8, relpos=(0, .5))
    note(ax, (SR['rotor_r'], 77), (27, 54), "rotor Ø7.8, turned by\nthe turntable's tube\nthrough a loose slot:\nno load on the ring", color=SLIP, fs=6.8, relpos=(0, .5))
    note(ax, (-TUBE['ro'], 97), (-44, 106.5), 'driver tube Ø20 (turntable)', color=TT, fs=6.8, relpos=(1, .5))
    note(ax, (-12.5, 81), (-44, 102), 'Ø25 passage (X1)', fs=6.8, relpos=(1, .5))
    note(ax, (11, 45), (16, 42), 'fixed leads (blue)\nto the track motors', color=BLUE, fs=6.8, relpos=(0, .5))
    note(ax, (0, 103), (8, 106.5), 'rotor leads (green)', color=GREEN, fs=6.8, relpos=(0, .5))
    ax.set_xlim(-45, 45); ax.set_ylim(36, 109); ax.set_aspect('equal'); ax.axis('off')


def sheet1(pdf):
    fig = plt.figure(figsize=(16.5, 11.7))
    fig.text(.02, .968, 'X1 turntable drive and wiring  —  concept for review', fontsize=17, weight='bold', color=INK)
    fig.text(.02, .947, 'Concept sketch, not CAD. All dimensions in mm. Sheet 1 of 2: arrangement. X-frame, RU66 and tracks are X1 as built; '
                        'orange = new printed parts, blue dashed = the future turntable. Both are proposals.', fontsize=10, color='#40585e')
    section_view(fig.add_axes([.01, .355, .60, .545]))
    plan_view(fig.add_axes([.615, .42, .38, .50]))
    slip_detail(fig.add_axes([.015, .03, .33, .30]))
    blocks = [
        ('How it turns', [
            ('1', 'The ring gear is screwed to the X-frame and never moves, like the toothed race of a real swing bearing,\n'
                  'which is fixed to the undercarriage.'),
            ('2', 'The swing motor rides on the turntable. Its pinion walks round the ring gear and carries the whole upper\n'
                  'with it. This is the full-size layout: on the Cat 320 the swing motor and its planetary reducer sit on the upper.'),
            ('3', 'The RU66 carries the weight and the tipping loads of the upper. The gears only turn it.')]),
        ('Where the wires go', [
            ('4', 'Battery, receiver and every motor driver stay in the upper body, as the engine, pump and valves do on the\n'
                  'real machine. The battery also adds counterweight. The swing motor is up there too, so its wires never cross.'),
            ('5', 'Only the two track motors are below the joint: 4 wires. They cross it through a slip ring at the swing centre,\n'
                  'so the upper can turn any number of times without twisting a wire.'),
            ('6', "The slip ring's fixed half is screwed under the X-frame top plate. The turntable turns its rotor through a loose\n"
                  'slot, so the slip ring carries no load. Its joints to the track-motor leads sit inside the carbody, behind the belly cover.')]),
        ('Changes to X1 that this needs', [
            ('•', '6 M3 inserts in the carbody top for the ring gear, and 3 bosses with M3 inserts under the top plate for the slip ring.'),
            ('•', "The pinion's path (R 58 to 92, Z 87 to 100) joins the turntable reserve. Nothing on the chassis is in it now.")]),
    ]
    y, lh = .342, .0128
    for head, items in blocks:
        fig.text(.375, y, head, fontsize=10.5, weight='bold', color=INK, va='top'); y -= .026
        for tag, text in items:
            fig.text(.375, y, tag, fontsize=8.6, weight='bold', color=INK, va='top')
            fig.text(.39, y, text, fontsize=8.6, color='#2c3e50', va='top', linespacing=1.3)
            y -= lh*(text.count('\n') + 1) + .007
        y -= .004
    fig.text(.02, .008, 'Sources: Cat 320 (07H) specifications p. 2; THK catalogue A18-20/21 (RU66); Prosper SRC022 series datasheet '
                        '(SRC022A-6 = Adafruit 736); J9 model (JGY-370 envelope, Pololu #1999 hub). Sheet 2: options, sizing and decisions.',
             fontsize=7.6, color=GREY)
    pdf.savefig(fig); fig.savefig(OUT / 'X1_swing_concept_sheet1.png', dpi=110)
    plt.close(fig)


# ------------------------------------------------------------------ sheet 2 icons
def icon_pinion(ax, motor_on='turntable'):
    ring_c = NEW if motor_on == 'turntable' else TT
    patch(ax, gear_outline(0, 0, 40, 1.0, .92), fc=NEW_L if motor_on == 'turntable' else '#d6eaf8', ec=ring_c, lw=.5)
    ax.add_patch(Circle((0, 0), .62, fc=BRG_L, ec=BRG, lw=.6))
    patch(ax, gear_outline(-1.22, 0, 12, .30, .24), fc=NEW, ec='#873600', lw=.5, z=5)
    ax.add_patch(Rectangle((-2.05, -.22), .62, .44, fc=XF if motor_on == 'chassis' else '#d4ac6e', ec=INK, lw=.6, zorder=6))
    ax.text(-1.74, -.42, 'motor', fontsize=6.5, ha='center', va='top', color=INK)
    ax.text(0, 0, 'fixed' if motor_on == 'turntable' else 'turns', fontsize=6.5, ha='center', va='center', color=GREY)
    ax.add_patch(FancyArrowPatch((.95, -.85), (.95, .85), connectionstyle='arc3,rad=.55', arrowstyle='->', mutation_scale=10, lw=1, color=TT))
    ax.set_xlim(-2.2, 1.6); ax.set_ylim(-1.2, 1.2); ax.set_aspect('equal'); ax.axis('off')


def icon_planetary(ax):
    patch(ax, gear_outline(0, 0, 44, 1.10, 1.02), fc=NEW_L, ec=NEW, lw=.5)
    ax.add_patch(Circle((0, 0), .98, fc='white', ec=NEW, lw=.4))
    for a in (90, 210, 330):
        c = (.62*math.cos(math.radians(a)), .62*math.sin(math.radians(a)))
        patch(ax, gear_outline(*c, 12, .36, .30), fc='#f5b041', ec='#873600', lw=.5, z=4)
    patch(ax, gear_outline(0, 0, 12, .28, .22), fc=NEW, ec='#873600', lw=.5, z=5)
    ax.plot([-.45, .45], [-.45, .45], color=RED, lw=2.2, zorder=6); ax.plot([-.45, .45], [.45, -.45], color=RED, lw=2.2, zorder=6)
    ax.text(0, -1.3, 'the centre is taken', fontsize=6.5, color=RED, ha='center', va='top')
    ax.set_xlim(-1.9, 1.9); ax.set_ylim(-1.7, 1.25); ax.set_aspect('equal'); ax.axis('off')


def icon_slip(ax):
    ax.add_patch(Rectangle((-.5, -.9), 1.0, 1.4, fc=SLIP_L, ec=SLIP, lw=.8))
    ax.add_patch(Rectangle((-1.0, .5), 2.0, .14, fc=SLIP_L, ec=SLIP, lw=.8))
    ax.add_patch(Rectangle((-.18, .64), .36, .45, fc='#5dade2', ec=SLIP, lw=.8))
    for yy in np.linspace(-.7, .3, 5):
        ax.plot([-.45, .45], [yy, yy], color=SLIP, lw=.5)
    for dx in (-.08, .08):
        ax.plot([dx, dx*4], [1.09, 1.5], color=GREEN, lw=1.1)
        ax.plot([dx*2, dx*6], [-.9, -1.3], color=BLUE, lw=1.1)
    ax.add_patch(FancyArrowPatch((-.6, 1.3), (.6, 1.3), connectionstyle='arc3,rad=-.4', arrowstyle='->', mutation_scale=9, lw=1, color=TT))
    ax.text(1.1, 1.0, 'turns', fontsize=6.5, color=TT, va='center')
    ax.text(1.1, -.3, 'fixed', fontsize=6.5, color=GREY, va='center')
    ax.set_xlim(-1.9, 1.9); ax.set_ylim(-1.45, 1.65); ax.set_aspect('equal'); ax.axis('off')


def icon_loop(ax):
    t = np.linspace(0, 3.2*math.pi, 200)
    r = .25 + .23*t/(3.2*math.pi)*3
    ax.plot(r*np.cos(t), r*np.sin(t), color=RED, lw=1.2)
    ax.add_patch(Wedge((0, 0), 1.25, 80, 100, width=.25, fc=INK, ec=INK))
    ax.add_patch(FancyArrowPatch((-1.0, -.95), (1.0, -.95), connectionstyle='arc3,rad=.5', arrowstyle='<->', mutation_scale=9, lw=1, color=TT))
    ax.text(0, -1.55, '± 180° to the end stop', fontsize=6.5, color=TT, ha='center', va='top')
    ax.set_xlim(-1.9, 1.9); ax.set_ylim(-1.9, 1.35); ax.set_aspect('equal'); ax.axis('off')


def icon_two_batteries(ax):
    for yy, lab in ((.55, 'upper'), (-.75, 'lower')):
        ax.add_patch(Rectangle((-.6, yy - .22), 1.2, .44, fc='#e9f7ef', ec=GREEN, lw=.8))
        ax.add_patch(Rectangle((.6, yy - .1), .1, .2, fc=GREEN, ec=GREEN))
        ax.text(-.75, yy, lab, fontsize=6.5, ha='right', va='center', color=INK)
    for k in range(3):
        ax.add_patch(Wedge((1.35, -.1), .2 + .17*k, 120, 240, width=.04, fc=TT, ec=TT))
    ax.plot([-1.8, 1.7], [-.1, -.1], color=LIGHT, lw=.8, ls='--')
    ax.text(1.7, -.25, 'joint', fontsize=6, color=GREY, ha='right', va='top')
    ax.set_xlim(-1.9, 1.9); ax.set_ylim(-1.25, 1.1); ax.set_aspect('equal'); ax.axis('off')


def wrap(text, width):
    out = []
    for para in text.split('\n'):
        out.append(textwrap.fill(para, width, subsequent_indent='  ' if para.startswith('• ') else ''))
    return '\n'.join(out)


def card(fig, x, y, w, h, title, badge, badge_color, body, icon, wrap_at=54):
    fig.patches.append(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=.004', transform=fig.transFigure,
                                      fc='#fbfcfc', ec='#ccd1d1', lw=.8, zorder=-10))
    fig.text(x + .008, y + h - .012, title, fontsize=9.8, weight='bold', color=INK, va='top')
    fig.text(x + w - .006, y + h - .012, badge, fontsize=8.4, weight='bold', color=badge_color, ha='right', va='top')
    a = fig.add_axes([x + .004, y + .012, .09, h - .05])
    a.set_zorder(5); a.patch.set_alpha(0)
    icon(a)
    yy = y + h - .043
    for t in body:
        t = wrap(t, wrap_at)
        fig.text(x + .1, yy, t, fontsize=8.1, color='#2c3e50', va='top', linespacing=1.28)
        yy -= .01232*(t.count('\n') + 1) + .0055


def table(fig, x, y, cols, rows, widths, fs=7.9, dy=.0182):
    for j, c in enumerate(cols):
        fig.text(x + sum(widths[:j]), y, c, fontsize=fs, weight='bold', color=INK)
    for i, r in enumerate(rows):
        hi = len(r) > len(cols)
        for j, c in enumerate(r[:len(cols)]):
            fig.text(x + sum(widths[:j]), y - (i + 1)*dy, c, fontsize=fs, color=NEW if hi else '#2c3e50', weight='bold' if hi else 'normal')
    return y - (len(rows) + 1)*dy


def sheet2(pdf):
    fig = plt.figure(figsize=(16.5, 11.7))
    fig.text(.02, .968, 'X1 turntable drive and wiring  —  options, sizing and decisions', fontsize=17, weight='bold', color=INK)
    fig.text(.02, .947, 'Concept sketch, not CAD. Sheet 2 of 2. Proposals are marked; nothing here is modelled yet.', fontsize=10, color='#40585e')
    cw, ch, gap = .32, .19, .012
    rows_y = [.905 - ch - k*(ch + gap) for k in range(3)]
    fig.text(.02, .918, '1  How the upper is turned', fontsize=12.5, weight='bold', color=INK)
    card(fig, .02, rows_y[0], cw, ch, 'A. Pinion on a fixed ring gear, motor on the upper', 'proposed', GREEN, [
        'The full-size layout (sheet 1). The motor can be either:',
        '• JGY-370 worm gearmotor (proposed): self-locking, so the upper holds on a slope with no brake. '
        'Same part as the tracks. Shocks go into the teeth, so limit the current.',
        "• Planetary gearmotor: the real machine's choice. Efficient and back-drivable, which is kind to the teeth, "
        'but it needs a brake or a holding current, or the upper drifts on a slope.'], icon_pinion)
    card(fig, .02, rows_y[1], cw, ch, 'B. One big planetary set round the swing axis', 'not recommended', RED, [
        'Sun gear on a motor at the centre, ring gear fixed to the X-frame, planet carrier = turntable. '
        'It works in principle, but:',
        '• the sun gear and its motor sit exactly where the slip ring and the cables must pass;',
        '• dozens of printed teeth must run true at Ø120 and more.'], icon_planetary)
    card(fig, .02, rows_y[2], cw, ch, 'C. Motor on the chassis, ring gear on the upper', 'possible', GREY, [
        "The 60 mm excavator's R3 layout: its slew motor sits on the lower bridge.",
        '• Works, and keeps the turntable simple.',
        "• But the swing motor's wires, and any limit-switch or angle-sensor wires, must also cross the joint: "
        '6 or more circuits instead of 4.'], lambda a: icon_pinion(a, 'chassis'))

    x2 = .355
    fig.text(x2, .918, '2  Keeping the wires from tangling', fontsize=12.5, weight='bold', color=INK)
    card(fig, x2, rows_y[0], cw, ch, '1. Slip ring at the swing centre', 'proposed', GREEN, [
        'Unlimited turning. Sliding contacts carry each wire across the joint. '
        'Needed: 4 circuits for the two track motors, plus 2 spare.',
        '• SRC022A-6 (Adafruit 736): 6 rings, 2 A each, 240 V, up to 300 rpm, Ø22 × 19 body. '
        'The track motors stall at 1.3 A.',
        '• Hobby RC excavators do this. The LESU PC30 turntable has a 4-way electric and 1-way oil slip ring '
        'and turns 360° without limit.'], icon_slip)
    card(fig, x2, rows_y[1], cw, ch, '2. Limited swing with a cable loop', 'fallback', GREY, [
        'No slip ring: a loose loop of soft silicone wire round the centre, and end stops at about ±180°.',
        '• Cheapest, and no sliding contacts.',
        '• The upper cannot keep turning one way, so end stops or limit switches must stop it. '
        'The 60 mm excavator R3 used ±150° with no slip ring.'], icon_loop)
    card(fig, x2, rows_y[2], cw, ch, '3. Own battery and receiver in the lower', 'possible', GREY, [
        'The lower half gets its own battery, receiver and track drivers.',
        '• No wires cross the joint at all.',
        "• Two batteries to charge and two receivers to set up, and the battery's weight no longer "
        'counts as counterweight.'], icon_two_batteries)

    x3 = .69
    fig.text(x3, .918, '3  Sizing (concept numbers)', fontsize=12.5, weight='bold', color=INK)
    y = table(fig, x3, .89, ['', 'Cat 320', '1:15, same density', 'Proposal A'], [
        ('Swing speed', '11.25 rpm', '—', '7.5 rpm, no load'),
        ('Swing torque', '82 kN·m max', '1.6 N·m', '2.4 N·m rated'),
    ], [.07, .066, .09, .08])
    fig.text(x3, y + .004, wrap('Torque scales with size⁴ at the same density: 82,000 / 15⁴ ≈ 1.6 N·m. '
                                'Proposal A: JGY-370-1260 200:1 and gears 80 : 20 = 4 : 1.', 84), fontsize=7.3, color=GREY, va='top')
    y = table(fig, x3, y - .036, ['JGY-370-1260, 12 V', 'Swing, no load', 'Swing torque, rated', ''], [
        ('68 rpm, 87:1', '17 rpm', '1.1 N·m', 'too weak'),
        ('40 rpm, 150:1', '10 rpm', '1.8 N·m', 'nearest the Cat 320'),
        ('30 rpm, 200:1', '7.5 rpm', '2.4 N·m', 'same as the tracks', '*'),
        ('18 rpm, 340:1', '4.5 rpm', '4.7 N·m', 'slow, hard on teeth'),
    ], [.077, .062, .082, .07])
    fig.text(x3, y + .004, wrap('Rated torques × 4, before gear losses. At stall the 200:1 motor gives 7.8 N·m at the swing; '
                                'a 0.6 A current limit keeps it near 3.3 N·m, about 11 MPa in the printed teeth.', 84),
             fontsize=7.3, color=GREY, va='top')
    fig.text(x3, y - .05, '4  What full-size and RC excavators do', fontsize=12.5, weight='bold', color=INK)
    facts = [
        'Full size: a hydraulic swing motor with a planetary reduction gearbox is bolted to the upper frame. '
        'Its pinion meshes with the gear of the slewing ring, which is fixed to the undercarriage.',
        'A centre swivel joint on the swing axis carries the oil down to the travel motors, so the upper can turn freely.',
        'Hobby 1/14 models copy this in miniature. The LESU PC30 has a slewing support with a 1-way oil and a 4-way '
        'electric slip ring (360° without limit), and a brushless swing motor through a 603:1 reduction. The Huina 1580 '
        'has its own rotary gearbox between the slewing motor and the lower chassis.',
        'So a planetary gear set fits best as the reducer inside the swing gearmotor, as on the real machine (option A).',
    ]
    yy = y - .078
    for t in facts:
        t = wrap('• ' + t, 82)
        fig.text(x3, yy, t, fontsize=7.9, color='#2c3e50', va='top', linespacing=1.28)
        yy -= .0120*(t.count('\n') + 1) + .007

    yb = rows_y[2] - .03
    fig.text(.02, yb, 'Key point on the wiring', fontsize=12.5, weight='bold', color=INK)
    fig.text(.02, yb - .03, 'Yes: the control circuit belongs in the upper. Keep the battery, receiver and every\n'
                            'motor driver there. Then only the two track motors are below the joint, and just\n'
                            '4 wires have to cross it. A slip ring with 6 rings passes them, with 2 to spare,\n'
                            'and the upper can turn without limit. Without a slip ring, the swing must be limited.',
             fontsize=9.2, color='#2c3e50', va='top', linespacing=1.35)
    fig.text(x2, yb, '5  Decisions before I model it', fontsize=12.5, weight='bold', color=INK)
    asks = [
        ('Swing motor', 'JGY-370 worm, the track motor (proposed), or a planetary gearmotor?'),
        ('Wires', 'Slip ring for unlimited turning (proposed), or limited swing with a cable loop?'),
        ('Swing speed', "7.5 rpm (200:1, proposed) or 10 rpm (150:1)? The Cat 320 swings at 11.25 rpm."),
        ('Then I model', "the ring gear and pinion prints, the X-frame inserts and slip-ring bosses, the swing motor's\n"
                         "place on the future turntable, and add the pinion's path to the reserve and to the checks."),
    ]
    yy = yb - .03
    for k, v in asks:
        fig.text(x2, yy, k, fontsize=8.8, weight='bold', color=INK, va='top')
        fig.text(x2 + .075, yy, v, fontsize=8.8, color='#2c3e50', va='top', linespacing=1.3)
        yy -= .0138*(v.count('\n') + 1) + .009
    fig.text(.02, .012, wrap('Sources: Cat 320 (07H) specifications p. 2 (swing speed and torque); conequip.com "What is a Swing Drive?" '
                             '(planetary gearbox, pinion, slewing ring on the undercarriage); oliverhobby.com LESU PC30 listing; '
                             'havochobby.in Huina 1580 rotary gearbox listing; Prosper SRC022 series datasheet; '
                             'excavator_60mm README (R3: ±150°, no slip ring).', 210), fontsize=7.3, color=GREY)
    pdf.savefig(fig); fig.savefig(OUT / 'X1_swing_concept_sheet2.png', dpi=110)
    plt.close(fig)


def main():
    with PdfPages(OUT / 'X1_swing_concept.pdf') as pdf:
        sheet1(pdf)
        sheet2(pdf)
    print('wrote', OUT / 'X1_swing_concept.pdf')


if __name__ == '__main__':
    main()

"""X1 swing drive and wiring, concept R2: the bought 6-way 2 A slip ring. Concept sketch for review, not CAD.

R2 changes only the slip ring and its mount; the swing drive (ring gear, pinion, JGY-370 on the turntable) is R1's.
- The ring is the user's bought part (seller's drawing in ../references/bought_slip_ring_2A/): Ø22 body, Ø44 x 2.4 flange
  5 mm back from the rotor end, 3 x Ø5.4 on Ø35, Ø7.8 x 9 rotor; L 19 (6-way) or 26 (12-way).
- R1 assumed the SRC022A-6 (flange at the rotor end) on three bosses, and turned its rotor by the lead bundle in a slot.
- R2: the Ø22 x 5 part of the body above the flange is a spigot. It centres the ring in a Ø22.4 bore in a new collar
  under the X-frame's top plate; 3 x M3 x 8 with washers from below. A TPU dog on the rotor is pushed round by two prongs
  under the future turntable's hub, with play, so the ring carries no load.

Sheet 1: arrangement (section A-A, plan view, R1 -> R2 at the swing centre, notes).
Sheet 2: the slip-ring mount in detail, the bought part, wiring, assembly and the numbers this script checks.

Usage, with the CAD Python as for R1 (x1_parts imports CadQuery):
  python draw_swing_concept_r2.py      # ../X1_swing_concept_R2.pdf, two sheet PNGs, ../X1_swing_concept_R2_checks.json
"""
import json, math, sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle, FancyBboxPatch, FancyArrowPatch, Wedge, Arc
from matplotlib.backends.backend_pdf import PdfPages

HERE = Path(__file__).resolve().parent
OUT = HERE.parent                                     # track_wheel_jgy370/X1/swing_concept
sys.path.insert(0, str(HERE))
import draw_swing_concept as C                        # noqa: E402  R1: helpers, colours, swing gearing; imports x1_parts
X = C.X
from draw_swing_concept import (INK, GREY, LIGHT, XF, XF_L, BRG, BRG_L, NEW, NEW_L, BUY, BUY_L, SLIP, SLIP_L, TT,  # noqa: E402
                                RED, BLUE, GREEN, patch, box, both, note, dim_v, dim_h, wrap)

PDF = OUT / 'X1_swing_concept_R2.pdf'
PNG = [OUT / 'X1_swing_concept_R2_sheet1.png', OUT / 'X1_swing_concept_R2_sheet2.png']
CHECKS = OUT / 'X1_swing_concept_R2_checks.json'
TPU, TPU_L = '#a04000', '#f5cba7'                     # rotor dog, printed in TPU

# ------------------------------------------------------------------ the bought ring (seller's drawing)
RING = dict(body_d=22.0, flange_d=44.0, flange_t=2.4, flange_back=5.0, hole_d=5.4, pcd=35.0,
            rotor_d=7.8, rotor_l=9.0, L={6: 19.0, 12: 26.0}, amps=2.0)
R1_RING = dict(name='SRC022A-6', flange_back=0.0, hole_d=5.5, L={6: 19.0, 12: 28.0})   # what R1 assumed (A type)
BODY_R, FLANGE_R, ROTOR_R, PCD_R = RING['body_d']/2, RING['flange_d']/2, RING['rotor_d']/2, RING['pcd']/2
HOLE_ANG = (0.0, 120.0, 240.0)                        # one flange screw in the section plane (front, +X)

# ------------------------------------------------------------------ X1 as built
TOP_Z, PLATE_Z0 = X.TOP_Z, X.TOP_Z - X.PLATE_T        # 85, 79
RELIEF_Z = X.TOP_Z - X.RELIEF_DEPTH                   # 82.5: floor of the seat relief, under the RU66 inner ring
PASS_R = X.PASSAGE_R                                  # 12.5
RU_BORE_R = X.RU66['d']/2                             # 17.5
INSERT = X.INSERT_M3                                  # M3 heat-set insert hole: r 2.0 x 5.7 (X1 / J9 standard)

# ------------------------------------------------------------------ R2 mount (X-frame change): collar under the top plate
COLLAR = dict(r_in=11.2, r_out=FLANGE_R, z0=PLATE_Z0 - 5.0, z1=PLATE_Z0)     # Ø22.4 bore, Ø44, 5 high: Z 74-79
FACE_Z = COLLAR['z1']                                 # rotor end of the body (top of the spigot) = plate underside: 79
FL_Z = (COLLAR['z0'] - RING['flange_t'], COLLAR['z0'])                      # flange 71.6-74, against the collar
END_Z = {n: FACE_Z - L for n, L in RING['L'].items()} # stator end: 60 (6-way), 53 (12-way)
ROTOR_Z = (FACE_Z, FACE_Z + RING['rotor_l'])          # 79-88
INS_Z = (COLLAR['z0'], COLLAR['z0'] + INSERT['length'])                    # insert hole 74-79.7
SCREW = dict(d=3.0, head_d=5.5, head_h=3.0, L=8.0)    # ISO 4762 M3 x 8
WASHER = dict(d_out=7.0, t=0.5)                       # ISO 7089 M3: needed, the Ø5.5 head barely covers the Ø5.4 hole
SCREW_HEAD_Z = FL_Z[0] - WASHER['t']                  # 71.1: under the head
SCREW_TIP_Z = SCREW_HEAD_Z + SCREW['L']               # 79.1

# ------------------------------------------------------------------ rotor dog (new print, TPU) and the turntable's hub (future)
DOG = dict(bore_d=7.5, r_out=6.5, z0=ROTOR_Z[1] - 7.0, z1=ROTOR_Z[1] + 1.0, hole_d=5.0,       # Z 81-89; shoulder on the rotor end
           lug_w=4.0, lug_r=9.5, lug_z0=ROTOR_Z[1] - 4.0)                                    # two lugs, Ø19 across, Z 84-89
DECK_Z = C.DECK_Z                                     # 101-107, as R1: 1 mm over the RU66 outer ring
HUB = dict(hole_r=7.5, spigot_r=17.3, spigot_z0=95.0)                                        # Ø15 lead hole; Ø34.6 spigot in the RU66 bore
PRONG = dict(ri=HUB['hole_r'], ro=11.0, width_deg=50.0, z0=RELIEF_Z + 1.0, z1=HUB['spigot_z0'])   # two prongs, Z 83.5-95
JST_XH4 = (12.4, 5.75)                                # JST XHP-4 housing, the rotor-lead plug at the drivers


def free_play_deg():
    """How far the upper can turn before a prong picks up a lug (prongs and lugs both 180 deg apart)."""
    r = (PRONG['ri'] + DOG['lug_r'])/2                # mid-engagement radius
    lug = 2*math.degrees(math.asin(DOG['lug_w']/2/r))
    return 180.0 - PRONG['width_deg'] - lug


def checks():
    c = []

    def add(name, value, need, note_=''):
        c.append(dict(check=name, value_mm=round(value, 2), required=need, ok=bool(eval(f'{value} {need}')), note=note_))
    add('collar bore to spigot, radial', COLLAR['r_in'] - BODY_R, '>= 0.15', 'locating clearance; tune the bore on a test ring')
    add('insert hole to collar bore, wall', PCD_R - INSERT['r'] - COLLAR['r_in'], '>= 2')
    add('insert hole to collar rim, wall', COLLAR['r_out'] - PCD_R - INSERT['r'], '>= 2')
    add('insert hole top to the relief floor (skin)', RELIEF_Z - INS_Z[1], '>= 2')
    add('screw thread in the insert', SCREW_TIP_Z - INS_Z[0], '>= 4.5')
    add('screw tip to the insert-hole bottom', INS_Z[1] - SCREW_TIP_Z, '>= 0.3')
    add('washer to the stator body, radial', PCD_R - WASHER['d_out']/2 - BODY_R, '>= 2')
    add('collar to the seat-insert ring under the plate, radial', X.MOUNT_RING[0] - COLLAR['r_out'], '>= 5')
    add('6-way stator end above the belly cover', END_Z[6] - X.COVER_Z[1], '>= 15', 'room to bend the stator leads')
    add('12-way stator end above the belly cover', END_Z[12] - X.COVER_Z[1], '>= 15', 'room to bend the stator leads')
    add('dog above the stator face', DOG['z0'] - FACE_Z, '>= 1.5', 'the dog turns, the face does not')
    add('dog hub to the prongs, radial', PRONG['ri'] - DOG['r_out'], '>= 0.8', 'misalignment room: no side load on the rotor')
    add('lug / prong overlap, radial', DOG['lug_r'] - PRONG['ri'], '>= 1.5')
    add('lug / prong overlap, height', DOG['z1'] - max(DOG['lug_z0'], PRONG['z0']), '>= 4')
    add('prong tips above the relief floor', PRONG['z0'] - RELIEF_Z, '>= 1')
    add('prongs to the RU66 bore, radial', RU_BORE_R - PRONG['ro'], '>= 3')
    add('lugs inside the Ø25 passage, radial', PASS_R - DOG['lug_r'], '>= 2', 'the dog passes the passage and the collar bore')
    add('lugs pass the collar bore (fit the dog first)', COLLAR['r_in'] - DOG['lug_r'], '>= 1')
    add('dog top to the hub, height', HUB['spigot_z0'] - DOG['z1'], '>= 3', 'no axial load on the rotor')
    add('hub spigot in the RU66 bore, radial', RU_BORE_R - HUB['spigot_r'], '>= 0.15', 'centres the turntable')
    add('JST-XH 4 plug through the Ø15 lead hole, diagonal margin', 2*HUB['hole_r'] - math.hypot(*JST_XH4), '>= 1')
    add('free play of the rotor drive (degrees)', free_play_deg(), '<= 120', 'the rotor may lag; its leads twist < 1/3 turn')
    return c


# ------------------------------------------------------------------ drawing pieces (section XZ through the swing axis)
def collar(ax, lw=.9):
    hx = dict(fc=XF_L, ec=NEW, hatch='////', lw=lw, z=3)
    both(ax, COLLAR['r_in'], COLLAR['r_out'], COLLAR['z0'], COLLAR['z1'], **hx)
    x = PCD_R                                         # insert in the cut (front); the other two are out of the plane
    box(ax, x - INSERT['r'], INS_Z[0], x + INSERT['r'], INS_Z[1], fc='#f7dc6f', ec='#b7950b', lw=.6, z=4)


def ring(ax, n=6, ghost12=True, leads=True, screw=True, lw=.8):
    """The bought ring, rotor up: flange against the collar, spigot in its bore. Not sectioned (bought part)."""
    box(ax, -FLANGE_R, FL_Z[0], FLANGE_R, FL_Z[1], fc=SLIP_L, ec=SLIP, lw=lw, z=6)
    box(ax, -BODY_R, END_Z[n], BODY_R, FACE_Z, fc=SLIP_L, ec=SLIP, lw=lw, z=6)
    for zz in np.linspace(END_Z[n] + 2.5, FL_Z[0] - 2.0, 3):
        ax.plot([-BODY_R + 1, BODY_R - 1], [zz, zz], color=SLIP, lw=.45, zorder=7)
    if ghost12 and n == 6:
        box(ax, -BODY_R, END_Z[12], BODY_R, END_Z[6], fc='none', ec=SLIP, lw=.7, ls=(0, (3, 2)), z=6)
    box(ax, -ROTOR_R, ROTOR_Z[0], ROTOR_R, ROTOR_Z[1], fc='#5dade2', ec=SLIP, lw=lw, z=6)
    if screw:
        x = PCD_R
        box(ax, x - WASHER['d_out']/2, SCREW_HEAD_Z, x + WASHER['d_out']/2, FL_Z[0], fc='#d5d8dc', ec=BUY, lw=.5, z=7)
        box(ax, x - SCREW['head_d']/2, SCREW_HEAD_Z - SCREW['head_h'], x + SCREW['head_d']/2, SCREW_HEAD_Z, fc=BUY, ec=BUY, lw=.5, z=7)
        box(ax, x - SCREW['d']/2, SCREW_HEAD_Z, x + SCREW['d']/2, SCREW_TIP_Z, fc=BUY_L, ec=BUY, lw=.5, z=8)
    if leads:
        z = END_Z[n]
        for dx in (-3, 3):
            ax.plot([dx, dx*2.6, dx*5.5], [z, z - 3.5, z - 6.5], color=BLUE, lw=1.3, zorder=8)


def dog(ax, lw=.7):
    """TPU dog on the rotor, aligned section: the left half is cut through a lug, the right half between the lugs."""
    hd = dict(fc=TPU_L, ec=TPU, hatch='....', lw=lw, z=7)
    rb = DOG['bore_d']/2 + .15                        # drawn on the Ø7.8 rotor (stretched)
    both(ax, rb, DOG['r_out'], DOG['z0'], ROTOR_Z[1], **hd)
    both(ax, DOG['hole_d']/2, DOG['r_out'], ROTOR_Z[1], DOG['z1'], **hd)
    box(ax, -DOG['lug_r'], DOG['lug_z0'], -DOG['r_out'], DOG['z1'], **hd)


def hub(ax, lw=.8, deck_x=(-178, 150), motor_gap=None):
    """Future turntable around the swing centre: deck, pad on the inner ring, spigot in the bore, one prong in the cut (right)."""
    dk = dict(fc='#eaf2f8', ec=TT, lw=lw, ls='--', z=2, alpha=.95)
    hr = HUB['hole_r']
    segs = [(deck_x[0], -hr), (hr, deck_x[1])]
    if motor_gap:
        segs = [(deck_x[0], motor_gap[0]), (motor_gap[1], -hr), (hr, deck_x[1])]
    for a, b in segs:
        if b > a:
            box(ax, a, DECK_Z[0], b, DECK_Z[1], **dk)
    for s in (1, -1):
        box(ax, s*hr, X.TURNTABLE_Z, s*(X.RU66['ds_max']/2), DECK_Z[0], **dk)          # pad: stands on the inner ring only
        box(ax, s*hr, HUB['spigot_z0'], s*HUB['spigot_r'], X.TURNTABLE_Z, **dk)          # spigot in the RU66 bore
    box(ax, PRONG['ri'], PRONG['z0'], PRONG['ro'], PRONG['z1'], fc='#d6eaf8', ec=TT, lw=lw, ls='--', z=5)   # prong, in the cut


def rotor_leads(ax, z_top=112.0, lw=1.6):
    ax.plot([0, 0], [ROTOR_Z[1], z_top], color=GREEN, lw=lw, zorder=9)


# ------------------------------------------------------------------ sheet 1
def section_view(ax):
    ax.set_title('SECTION A–A on the centreline, seen from the right-hand side (front to the right)', fontsize=10.5, loc='left', weight='bold')
    L = 308.6
    patch(ax, C.stadium(-L/2, L/2, 0, 92.4), fc='#eef0f1', ec=LIGHT, lw=.6, ls='--', z=0)
    ax.text(100, 14, 'left track\n(behind the cut)', fontsize=6.8, color=GREY, ha='center')
    patch(ax, C.frame_side_silhouette(), fc='#fbf1cf', ec='#d4ac0d', lw=.5, ls='--', z=1)
    patch(ax, list(X.rail_profile().exterior.coords), fc='#fbf1cf', ec='#d4ac0d', lw=.5, ls='--', z=1)
    ax.text(66, 66, 'leg and rail\n(behind)', fontsize=6.5, color='#9a7d0a', ha='left')
    ax.plot([-178, 150], [0, 0], color='#6b4f2a', lw=1.2, zorder=0)
    C.carbody_section(ax, bosses=False)
    collar(ax, lw=.7)
    box(ax, -X.BODY_R, X.COVER_Z[0], X.BODY_R, X.COVER_Z[1], fc='#808b96', ec=INK, lw=.5, z=3)
    C.ru66_section(ax)
    x = X.RU66['outer_pcd']/2
    box(ax, x - 3.5, X.TURNTABLE_Z - 4.4, x + 3.5, X.TURNTABLE_Z - .4, fc='none', ec=BUY, lw=.5, ls='--', z=6)
    box(ax, x - 2, X.TURNTABLE_Z - 4.4 - 16, x + 2, X.TURNTABLE_Z - 4.4, fc='none', ec=BUY, lw=.5, ls='--', z=6)
    # swing drive: R1 unchanged
    hn = dict(fc=NEW_L, ec=NEW, hatch='xxx', lw=.8, z=5)
    both(ax, C.RING_BORE, C.RING_TIP, *C.GEAR_Z, **hn)
    for s in (1, -1):
        ax.plot([s*C.RING_ROOT]*2, C.GEAR_Z, color=NEW, lw=.5, zorder=6)
    xs = X.BODY_R - 6.5
    box(ax, xs - 1.5, TOP_Z - 4, xs + 1.5, C.GEAR_Z[1], fc='none', ec=BUY, lw=.5, ls='--', z=7)
    PX = C.PX
    box(ax, PX - C.PIN_TIP, C.PIN_Z[0], PX + C.PIN_TIP, C.PIN_Z[1], **hn)
    for s in (1, -1):
        ax.plot([PX + s*C.PIN_ROOT]*2, C.PIN_Z, color=NEW, lw=.5, zorder=6)
    hb = dict(fc=BUY_L, ec=BUY, lw=.7, z=6)
    H = C.HUB
    box(ax, PX - H['flange_r'], C.PIN_Z[1], PX + H['flange_r'], C.PIN_Z[1] + H['flange_t'], **hb)
    box(ax, PX - H['boss_r'], C.PIN_Z[1] + H['flange_t'], PX + H['boss_r'], C.PIN_Z[1] + H['flange_t'] + H['boss_h'], **hb)
    box(ax, PX - 3, DECK_Z[1] - C.SHAFT_LEN, PX + 3, DECK_Z[1], fc='#566573', ec=INK, lw=.5, z=7)
    for dx in (-H['pcd_r'], H['pcd_r']):
        box(ax, PX + dx - 1.5, C.PIN_Z[0], PX + dx + 1.5, C.PIN_Z[1] + 4.5, fc='none', ec=INK, lw=.5, ls='--', z=7)
    box(ax, PX - C.GB_REAR, DECK_Z[1], PX + C.GB_FRONT, DECK_Z[1] + C.GB_DEPTH, fc='#d4ac6e', ec='#7e5109', lw=.8, z=6)
    zc = DECK_Z[1] + C.CAN_AX
    box(ax, PX - C.CAN_END, zc - C.CAN_R, PX - C.GB_REAR, zc + C.CAN_R, fc='#bfc9ca', ec=INK, lw=.8, z=6)
    ax.text(PX - (C.GB_REAR - C.GB_FRONT)/2, DECK_Z[1] + C.GB_DEPTH/2, 'JGY-370\ngearbox', fontsize=6.3, ha='center', va='center', color='#7e5109', zorder=8)
    ax.text(PX - (C.CAN_END + C.GB_REAR)/2, zc, 'motor', fontsize=6.3, ha='center', va='center', color=INK, zorder=8)
    for dx in (9.0, -24.0):
        box(ax, PX + dx - 1.5, DECK_Z[0], PX + dx + 1.5, DECK_Z[1] + 3, fc='none', ec=INK, lw=.5, ls='--', z=7)
    # future turntable with the R2 hub; R2 slip ring, dog
    hub(ax, motor_gap=(PX - 14, PX + 14))
    ax.text(-56, 110, 'turntable deck (future)', fontsize=6.8, color=TT)
    ax.add_patch(FancyBboxPatch((66, 116), 64, 24, boxstyle='round,pad=1.2', fc='#e9f7ef', ec=GREEN, lw=.9, zorder=6))
    ax.text(98, 128, 'battery, receiver\nand motor drivers\n(all in the upper)', fontsize=6.8, ha='center', va='center', color=GREEN, zorder=7)
    ring(ax, screw=True, lw=.7)
    dog(ax, lw=.5)
    rotor_leads(ax, z_top=112)
    ax.plot([0, 0, 64.8], [112, 112, 126], color=GREEN, lw=1.6, zorder=8)
    ax.text(-3, 118, 'rotor leads', fontsize=6.5, color=GREEN, ha='right')
    ax.plot([PX - C.CAN_END, PX - C.CAN_END - 6, PX - C.CAN_END - 6, 60, 64.8], [zc, zc, 150, 150, 136], color=INK, lw=1.1, zorder=8)
    ax.text(-40, 152.5, 'swing motor leads (they stay in the upper)', fontsize=6.5, color=INK)
    zl = END_Z[6] - 6.5
    for s in (1, -1):                                 # stator leads to the 2-pin plugs, track-motor leads from the side holes
        ax.add_patch(Circle((s*4, X.CABLE_HOLE['z']), X.CABLE_HOLE['r'], fill=False, ec=RED, lw=.6, ls='--', zorder=7))
        ax.plot([s*16.5, s*8.5], [zl - 2.5, X.CABLE_HOLE['z'] + 1.5], color=RED, lw=1.3, zorder=8)
        box(ax, s*16.5 - 3, zl - 2.5, s*16.5 + 3, zl + 2.5, fc='white', ec=INK, lw=.6, z=9)
    C.dim_v(ax, -172, 0, TOP_Z, 'Z 85: seat and leg tops', side=-1)
    C.dim_v(ax, -97, C.PIN_Z[0], C.PIN_Z[1], '10', side=-1, fs=6.5)
    C.dim_h(ax, PX, 0, 205, f'{C.CD:g}: pinion axis from the swing axis')
    ax.plot([PX, PX], [DECK_Z[1] + C.GB_DEPTH + 2, 204], color=LIGHT, lw=.5, ls='-.', zorder=1)
    ax.plot([0, 0], [-6, 207], color=LIGHT, lw=.6, ls='-.', zorder=1)
    C.dim_v(ax, 136, 0, X.TURNTABLE_Z, 'Z 100: turntable face', side=1)
    note(ax, (-100, 127), (-196, 197), 'swing motor ON THE TURNTABLE (as R1):\nJGY-370-1260 200:1, the same motor\nas the tracks; shaft down through\nthe deck, 4 × M3 into the gearbox',
         va='top', relpos=(.4, 0))
    note(ax, (-12, 98), (-24, 184), "R2 turntable hub (future): Ø15 lead hole;\ntwo prongs turn the rotor's TPU dog", color=TT, ha='right', relpos=(1, .5))
    note(ax, (40, 97), (14, 184), 'RU66 (X1): outer ring bolted to the X-frame,\ninner ring turns with the turntable', relpos=(.2, 0))
    note(ax, (-82, 87.5), (-196, -9), 'pinion (as R1): printed, 20 teeth,\n10 wide, on a Pololu #1999 hub;\n2 mm above the leg tops', color=NEW, va='top', relpos=(.6, 1))
    note(ax, (-56, 86), (-122, -9), 'ring gear (as R1): printed,\nmodule 1.5, 80 teeth,\npitch Ø120, 12 high;\n6 × M3 into the carbody top', color=NEW, va='top', relpos=(.6, 1))
    note(ax, (-11, 66), (-52, -9), 'R2 slip ring, BOUGHT: 6-way 2 A\n(12-way: longer body, dashed).\nIts Ø22 spigot sits in a NEW\ncollar under the top plate;\n3 × M3 from below (sheet 2)', color=SLIP, va='top', relpos=(.6, 1))
    note(ax, (22, 42), (30, -9), "track-motor leads (red) come in\nthrough the Ø10 side holes and\nplug into the slip ring's stator\nleads, behind the belly cover", color=RED, va='top', relpos=(.2, 1))
    ax.set_xlim(-198, 152); ax.set_ylim(-46, 216); ax.set_aspect('equal'); ax.axis('off')


def plan_view(ax):
    ax.set_title('PLAN VIEW, turntable removed (front to the right)', fontsize=10.5, loc='left', weight='bold')
    L = 308.6
    for s in (1, -1):
        ax.add_patch(Rectangle((-L/2, s*X.TRACK_Y - 35), L, 70, fc='#d5d8dc', ec=LIGHT, lw=.6, zorder=0))
        ax.add_patch(Rectangle((X.RAIL_X[0], min(s*X.RAIL_IN_Y, s*X.BOSS_FACE_Y)), X.RAIL_X[1] - X.RAIL_X[0], X.RAIL_T,
                               fc=XF, ec='#b9770e', lw=.5, zorder=2))
        ax.plot([-18.6, 0, 0], [s*126.8, s*126.8, s*X.BODY_R], color=RED, lw=1.1, zorder=6)
        ax.plot([0, 0], [s*X.BODY_R, s*30], color=RED, lw=1.0, ls=(0, (2, 1.5)), zorder=6)
    ax.text(0, 170, 'left track', fontsize=7, color=GREY, ha='center', va='center')
    ax.text(0, -170, 'right track', fontsize=7, color=GREY, ha='center', va='center')
    patch(ax, list(X.plan_outline().exterior.coords), fc=XF, ec='#b9770e', lw=.6, z=1)
    ax.add_patch(Circle((0, 0), X.RESERVE_R, fill=False, ec=TT, lw=.8, ls='--', zorder=3))
    ax.text(-128, -152, 'swing circle R 189', fontsize=6.8, color=TT, rotation=40)
    patch(ax, C.gear_outline(0, 0, C.Z_RING, C.RING_TIP, C.RING_ROOT), fc=NEW_L, ec=NEW, lw=.5, z=4)
    ax.add_patch(Circle((0, 0), C.RING_BORE, fc=XF, ec=NEW, lw=.5, zorder=4))
    ax.add_patch(Circle((0, 0), X.RU66['D']/2, fc=BRG_L, ec=BRG, lw=.6, zorder=5))
    ax.add_patch(Circle((0, 0), RU_BORE_R, fc=XF_L, ec=BRG, lw=.6, zorder=5))           # relief floor seen through the bore
    ax.add_patch(Circle((0, 0), PASS_R, fc='white', ec='#b9770e', lw=.5, zorder=5))
    ax.add_patch(Circle((0, 0), C.CD, fill=False, ec=NEW, lw=.7, ls=(0, (4, 3)), zorder=4))
    patch(ax, C.gear_outline(C.PX, 0, C.Z_PIN, C.PIN_TIP, C.PIN_ROOT, phase=math.pi/C.Z_PIN), fc=NEW, ec='#873600', lw=.5, z=7)
    ax.add_patch(Rectangle((C.PX - C.GB_REAR, -C.GB_HALF), C.GB_REAR + C.GB_FRONT, 2*C.GB_HALF, fill=False, ec='#7e5109', lw=.7, ls='--', zorder=8))
    ax.add_patch(Rectangle((C.PX - C.CAN_END, -C.CAN_R), C.CAN_END - C.GB_REAR, 2*C.CAN_R, fill=False, ec=INK, lw=.7, ls='--', zorder=8))
    # R2: under the plate (hidden, dashed) the collar = flange outline and its 3 screws; seen through the passage: spigot face, dog
    ax.add_patch(Circle((0, 0), FLANGE_R, fill=False, ec=SLIP, lw=.7, ls='--', zorder=6))
    for a in HOLE_ANG:
        ax.add_patch(Circle(X.polar(PCD_R, a), WASHER['d_out']/2, fill=False, ec=BUY, lw=.5, ls='--', zorder=6))
    ax.add_patch(Circle((0, 0), BODY_R, fc=SLIP_L, ec=SLIP, lw=.5, zorder=6))
    plan_dog(ax, lugs_deg=90, lw=.4)
    for s in (1, -1):
        ax.annotate('', (s*200, 24), (s*200, 0), arrowprops=dict(arrowstyle='-|>', lw=1.0, color=INK))
        ax.text(s*200 + s*9, 4, 'A', fontsize=10, weight='bold', ha='center')
    ax.plot([-200, 200], [0, 0], color=INK, lw=.7, ls='-.', zorder=9)
    note(ax, (C.PX - 10, 9), (-214, 104), 'swing motor and\npinion, on the\nturntable at the\nrear (as R1)', color=NEW, va='top', fs=6.8, relpos=(.8, 0))
    note(ax, (C.CD*math.cos(math.radians(-50)), C.CD*math.sin(math.radians(-50))), (98, -46),
         'pinion path R 75:\npasses 2 mm over the legs', color=NEW, fs=6.8, relpos=(0, .5))
    note(ax, (C.RING_TIP*math.cos(math.radians(40)), C.RING_TIP*math.sin(math.radians(40))), (80, 92),
         'ring gear Ø123\naround the RU66 (Ø95)', color=NEW, fs=6.8, relpos=(0, .5))
    note(ax, (FLANGE_R*math.cos(math.radians(-35)), FLANGE_R*math.sin(math.radians(-35))), (100, 40),
         'R2: slip-ring flange Ø44 and collar,\nhidden under the top plate;\n3 × M3 on Ø35, from below', color=SLIP, fs=6.8, relpos=(0, .5))
    note(ax, (2, 8), (24, 140), 'X1 cable routes:\npod nose port → Ø10 hole', color=RED, fs=6.8, va='center', relpos=(0, .5))
    ax.annotate('front', (218, -186), (175, -186), fontsize=9, weight='bold', va='center', arrowprops=dict(arrowstyle='->', lw=1))
    ax.set_xlim(-216, 222); ax.set_ylim(-212, 212); ax.set_aspect('equal'); ax.axis('off')


def plan_dog(ax, lugs_deg=90, lw=.6, prongs_deg=None):
    """Dog seen from above: hub, two lugs; optionally the two prongs (cut at the dog's height)."""
    hd = dict(fc=TPU_L, ec=TPU, lw=lw)
    for a in (lugs_deg, lugs_deg + 180):
        t = math.radians(a)
        u, v = np.array([math.cos(t), math.sin(t)]), np.array([-math.sin(t), math.cos(t)])
        w = DOG['lug_w']/2
        pts = [tuple(u*r + v*s) for r, s in ((DOG['r_out'] - 1, -w), (DOG['lug_r'], -w), (DOG['lug_r'], w), (DOG['r_out'] - 1, w))]
        patch(ax, pts, fc=TPU_L, ec=TPU, lw=lw, z=8)
    ax.add_patch(Circle((0, 0), DOG['r_out'], zorder=8, **hd))
    ax.add_patch(Circle((0, 0), DOG['hole_d']/2, fc='#5dade2', ec=SLIP, lw=lw, zorder=9))
    ax.add_patch(Circle((0, 0), 1.6, fc=GREEN, ec=GREEN, lw=lw, zorder=10))
    if prongs_deg is not None:
        for a in (prongs_deg, prongs_deg + 180):
            ax.add_patch(Wedge((0, 0), PRONG['ro'], a - PRONG['width_deg']/2, a + PRONG['width_deg']/2, width=PRONG['ro'] - PRONG['ri'],
                               fc='#d6eaf8', ec=TT, lw=.8, hatch='////', zorder=7))


def r1_vs_r2(ax_l, ax_r):
    """Sheet 1, bottom left: R1 and R2 at the swing centre, same scale."""
    ax_l.set_title('R1 (superseded): SRC022A-6', fontsize=9.2, loc='left', weight='bold', color=GREY)
    C.carbody_section(ax_l)
    C.ru66_section(ax_l, rollers=False)
    C.driver_tube(ax_l)
    C.slip_ring(ax_l, screws=False)
    ax_l.text(0, 41, 'flange at the rotor end;\nrotor turned by its own\nleads in a slot of the tube', fontsize=6.8, ha='center', va='top', color=GREY)
    ax_r.set_title('R2: bought ring in a collar', fontsize=9.2, loc='left', weight='bold')
    C.carbody_section(ax_r, bosses=False)
    collar(ax_r)
    C.ru66_section(ax_r, rollers=False)
    hub(ax_r, deck_x=(-40, 40))
    ring(ax_r, leads=True)
    dog(ax_r)
    rotor_leads(ax_r, z_top=108)
    ax_r.text(0, 41, 'flange 5 back from the rotor end;\nØ22 spigot centres it; TPU dog\nand prongs turn the rotor', fontsize=6.8, ha='center', va='top', color=INK)
    for a in (ax_l, ax_r):
        a.set_xlim(-31, 31); a.set_ylim(32, 110); a.set_aspect('equal'); a.axis('off')


def text_blocks(fig, x, y, blocks, fs=8.5, lh=.0126, tab=.015, head_fs=10.5):
    for head, items in blocks:
        fig.text(x, y, head, fontsize=head_fs, weight='bold', color=INK, va='top'); y -= .024
        for tag, text in items:
            fig.text(x, y, tag, fontsize=fs, weight='bold', color=INK, va='top')
            fig.text(x + tab, y, text, fontsize=fs, color='#2c3e50', va='top', linespacing=1.3)
            y -= lh*(text.count('\n') + 1) + .006
        y -= .006
    return y


def sheet1(pdf):
    fig = plt.figure(figsize=(16.5, 11.7))
    fig.text(.02, .968, 'X1 turntable drive and wiring  —  concept R2: the bought slip ring', fontsize=17, weight='bold', color=INK)
    fig.text(.02, .947, 'Concept sketch, not CAD. All dimensions in mm. Sheet 1 of 2: arrangement. X-frame, RU66 and tracks are X1 as built; '
                        'orange = new printed parts, blue dashed = the future turntable. R2 changes only the slip ring and its mount.',
             fontsize=10, color='#40585e')
    section_view(fig.add_axes([.01, .355, .60, .545]))
    plan_view(fig.add_axes([.615, .42, .38, .50]))
    r1_vs_r2(fig.add_axes([.012, .03, .165, .30]), fig.add_axes([.185, .03, .165, .30]))
    blocks = [
        ('What changed from R1', [
            ('1', 'The slip ring is your bought 6-way 2 A ring. Its body (Ø22), flange (Ø44) and rotor (Ø7.8) match the SRC022A-6 that R1\n'
                  'assumed, but its flange sits 5 mm back from the rotor end, so a Ø22 × 5 spigot stands above the flange.'),
            ('2', "The spigot centres the ring in a Ø22.4 bore in a new collar under the top plate (it replaces R1's three bosses).\n"
                  'The Ø5.4 flange holes are loose on M3, so the spigot does the locating; the screws only clamp.'),
            ('3', "A TPU dog pushed onto the rotor is turned by two prongs under the turntable's hub, with play. The ring carries no\n"
                  'load, and the drive no longer goes through the rotor leads, as it did in R1.'),
            ('4', 'The 12-way ring fits the same collar. Only its body is longer: 26 instead of 19.')]),
        ('Where the wires go (as R1)', [
            ('•', 'Battery, receiver and all the drivers stay in the upper. Only the two track motors are below the joint: 4 wires.'),
            ('•', "The stator leads stay in the carbody and plug into the track-motor leads behind the belly cover. The rotor leads\n"
                  'go up through the hub to the drivers, so the upper can turn any number of times.')]),
        ('Changes to X1 that this needs', [
            ('•', 'Under the top plate: the slip-ring collar (Ø44 × 5, Ø22.4 bore, 3 M3 inserts). On the carbody top: 6 M3 inserts\n'
                  'for the ring gear, as in R1.'),
            ('•', "The pinion's path (R1) and the hub's prongs (R 7.5 to 11, down to Z 83.5) join the turntable reserve.")]),
    ]
    text_blocks(fig, .372, .342, blocks)
    fig.text(.02, .008, "Sources: the seller's drawing of the 6-way / 12-way 2 A slip ring (references/bought_slip_ring_2A); THK catalogue A18-20/21 (RU66); "
                        'J9 model (JGY-370 envelope, Pololu #1999 hub); concept R1 (X1_swing_concept.pdf) for the swing drive. Sheet 2: the slip-ring mount in detail.',
             fontsize=7.6, color=GREY)
    pdf.savefig(fig); fig.savefig(PNG[0], dpi=110)
    plt.close(fig)


# ------------------------------------------------------------------ sheet 2
A_A = dict(rect=(.01, .355, .60, .545), xlim=(-198, 152), ylim=(-46, 216))      # section A-A on sheet 1, for the scale ratios
FIG = (16.5, 11.7)


def scale(rect, xlim, ylim):
    """Inches of paper per mm for an equal-aspect axes."""
    return min(rect[2]*FIG[0]/(xlim[1] - xlim[0]), rect[3]*FIG[1]/(ylim[1] - ylim[0]))


def clip_to(ax, x0, x1, z0, z1):
    """Clip everything drawn so far to a detail boundary, and draw the boundary."""
    r = Rectangle((x0, z0), x1 - x0, z1 - z0, transform=ax.transData, fc='none', ec='none')
    for a in ax.patches + ax.lines:
        a.set_clip_path(r)
    ax.add_patch(Rectangle((x0, z0), x1 - x0, z1 - z0, fc='none', ec=LIGHT, lw=.6, ls=(0, (6, 3)), zorder=0))


DET = dict(rect=(.005, .31, .585, .605), xlim=(-74, 80), ylim=(18, 137), clip=(-37, 37, 40, 116))


def detail_c(ax):
    ax.set_title('DETAIL C: the slip ring at the swing centre, on the centreline (front to the right)', fontsize=10.5, loc='left', weight='bold')
    C.carbody_section(ax, bosses=False)
    collar(ax)
    C.ru66_section(ax, rollers=False)
    hub(ax, deck_x=(-50, 50))
    ring(ax)
    dog(ax)
    rotor_leads(ax, z_top=116)
    for s in (1, -1):
        ax.plot([s*16.5, s*24], [END_Z[6] - 6.5, END_Z[6] - 13], color=BLUE, lw=1.3, zorder=8)
    ax.plot([0, 0], [40, 116], color=LIGHT, lw=.6, ls='-.', zorder=1)
    clip_to(ax, *DET['clip'])
    ax.text(-1.0, 115.2, 'swing axis', fontsize=6.3, color=GREY, ha='right', va='top')
    x_r = DET['clip'][1]
    for z, t in ((DECK_Z[1], 'Z 107 deck top'), (X.TURNTABLE_Z, 'Z 100 turntable face'), (HUB['spigot_z0'], 'Z 95 hub'),
                 (DOG['z1'], 'Z 89 dog top'), (TOP_Z, 'Z 85 seat'), (FACE_Z, 'Z 79 rotor end of the body'),
                 (COLLAR['z0'], 'Z 74 collar = flange'), (END_Z[6], 'Z 60 6-way end'), (END_Z[12], 'Z 53 12-way end')):
        ax.plot([x_r, x_r + 2], [z, z], color=GREY, lw=.6, zorder=11)
        ax.text(x_r + 2.6, z, t, fontsize=6.4, color=GREY, va='center', zorder=11)
    k = dict(fs=7.0)
    # above
    note(ax, (0.3, 111), (-6, 132), 'rotor leads (green): up to the\ndrivers in the upper', color=GREEN, ha='right', relpos=(1, .5), **k)
    note(ax, (-HUB['hole_r'] + .3, DECK_Z[1] - 1.5), (-20, 124), 'Ø15 lead hole in the hub', color=TT, ha='right', relpos=(1, .5), **k)
    note(ax, (HUB['spigot_r'] - 2, 97.5), (8, 128.5), 'hub spigot Ø34.6 in the RU66 bore:\ncentres the turntable (future part)',
         color=TT, relpos=(0, .5), **k)
    note(ax, (PRONG['ro'], 89), (8, 121.5), 'prong of the hub, cut on the right of the axis:\npushes a lug of the dog round',
         color=TT, relpos=(0, .5), **k)
    # left
    xl = DET['clip'][0] - 1.5
    note(ax, (-DOG['lug_r'] + .5, 87), (xl, 99), 'NEW rotor dog, TPU 95A,\ncut through a lug on the left:\nØ7.5 bore, a stretch fit on the\nØ7.8 rotor, no glue; its shoulder\nsits on the rotor end; lugs Ø19',
         color=TPU, ha='right', relpos=(1, .5), **k)
    note(ax, (-ROTOR_R, 82), (xl, 84.5), 'rotor Ø7.8 × 9 (turns);\nits leads leave the end',
         color=SLIP, ha='right', relpos=(1, .5), **k)
    note(ax, (-COLLAR['r_out'] + 3, 76.5), (xl, 72), 'NEW collar under the top plate\n(X-frame change, printed with it):\nØ44 × 5, Ø22.4 bore takes the\nring\'s Ø22 × 5 spigot',
         color=NEW, ha='right', relpos=(1, .5), **k)
    note(ax, (-FLANGE_R + 4, FL_Z[0] + .3), (xl, 58), 'flange Ø44 × 2.4 clamped\nagainst the collar',
         color=SLIP, ha='right', relpos=(1, .5), **k)
    # right
    xr = DET['clip'][1] + 18
    note(ax, (PCD_R + INSERT['r'] - .3, INS_Z[1] - 1.5), (xr, 86), 'M3 heat-set insert,\nØ4.0 × 5.7 (X1 standard);\n2.8 of plastic left above it',
         color='#9a7d0a', relpos=(0, .5), **k)
    note(ax, (PCD_R + WASHER['d_out']/2, SCREW_HEAD_Z - 1.4), (xr, 66), 'M3 × 8 socket screw and\nM3 washer, from below;\n3 on Ø35 (1 in the cut).\nThe washer is needed: the\nhead (Ø5.5) barely covers\nthe Ø5.4 hole',
         color=BUY, relpos=(0, .5), **k)
    # below
    note(ax, (-BODY_R + 2, END_Z[6] + 4), (-36, 33), 'BOUGHT slip ring, 6-way 2 A, stator\n(fixed). Dashed: the 12-way body',
         color=SLIP, ha='right', va='top', relpos=(.8, 1), **k)
    note(ax, (24, END_Z[6] - 13), (30, 33), 'stator leads (blue) to two\n2-pin plugs: see view E',
         color=BLUE, va='top', relpos=(.1, 1), **k)
    ax.set_xlim(*DET['xlim']); ax.set_ylim(*DET['ylim']); ax.set_aspect('equal'); ax.axis('off')


def view_d(ax):
    ax.set_title('SECTION D: at Z 86, looking down', fontsize=9.5, loc='left', weight='bold')
    ax.add_patch(Circle((0, 0), X.RU66['ds_max']/2, fc=BRG_L, ec=BRG, lw=.6, hatch='\\\\\\\\', zorder=1))
    ax.add_patch(Circle((0, 0), RU_BORE_R, fc=XF_L, ec=BRG, lw=.6, zorder=2))
    ax.add_patch(Circle((0, 0), PASS_R, fc='white', ec='#b9770e', lw=.5, ls='--', zorder=2))
    ax.add_patch(Circle((0, 0), BODY_R, fc=SLIP_L, ec=SLIP, lw=.5, zorder=3))
    plan_dog(ax, lugs_deg=90, lw=.6, prongs_deg=0)
    for a0 in (40, 220):
        ax.add_patch(FancyArrowPatch(X.polar(14.0, a0), X.polar(14.0, a0 + 40), connectionstyle='arc3,rad=.25', arrowstyle='->',
                                     mutation_scale=9, lw=1, color=TT, zorder=9))
    k = dict(fs=6.8)
    note(ax, X.polar(PRONG['ro'] - .5, -12), (33, -14), 'prong (turntable),\ncut at Z 86', color=TT, relpos=(0, .5), **k)
    note(ax, X.polar(DOG['lug_r'] - .8, 95), (-61, 27), 'lug of the TPU dog', color=TPU, relpos=(1, .5), **k)
    note(ax, X.polar(15.0, 205), (-61, -21), 'relief floor, seen\nthrough the RU66 bore', color=GREY, relpos=(1, .5), **k)
    note(ax, X.polar(25.0, 45), (33, 25), 'RU66 inner ring', color=GREY, relpos=(0, .5), **k)
    ax.text(0, -34, f'Play: the upper turns up to {free_play_deg():.0f}° before a prong picks up\na lug. That is harmless: the rotor '
                    'leads twist less than 1/3 turn\nand never wind up. No side or end load reaches the rotor.',
            fontsize=6.8, ha='center', va='top', color=INK)
    ax.set_xlim(-62, 62); ax.set_ylim(-50, 33); ax.set_aspect('equal'); ax.axis('off')


def view_e(ax):
    ax.set_title('VIEW E: from below, belly cover off', fontsize=9.5, loc='left', weight='bold')
    ax.add_patch(Circle((0, 0), X.BODY_R, fc='#fbf1cf', ec='#b9770e', lw=.6, zorder=0))
    ax.add_patch(Circle((0, 0), X.BODY_R - X.BODY_WALL, fc='#fdfaf0', ec='#b9770e', lw=.6, zorder=1))
    for a in X.COVER_BOSS_ANG:
        ax.add_patch(Circle(X.polar(X.COVER_BOSS_R, a), 5.0, fc=XF_L, ec='#b9770e', lw=.5, zorder=2))
    ax.add_patch(Circle((0, 0), FLANGE_R, fc=SLIP_L, ec=SLIP, lw=.7, zorder=3))
    for a in HOLE_ANG:
        c = X.polar(PCD_R, -a)                         # seen from below: Y is mirrored
        ax.add_patch(Circle(c, WASHER['d_out']/2, fc='#d5d8dc', ec=BUY, lw=.5, zorder=4))
        ax.add_patch(Circle(c, SCREW['head_d']/2, fc=BUY, ec=BUY, lw=.5, zorder=5))
    ax.add_patch(Circle((0, 0), BODY_R, fc='#85c1e9', ec=SLIP, lw=.7, zorder=4))
    for s, lab in ((-1, 'left'), (1, 'right')):         # seen from below the left track (+Y) is at the bottom
        y_hole = s*(X.BODY_R - X.BODY_WALL/2)
        ax.add_patch(Rectangle((-X.CABLE_HOLE['r'], y_hole - X.BODY_WALL/2), 2*X.CABLE_HOLE['r'], X.BODY_WALL, fc='white', ec=RED, lw=.7, zorder=3))
        ax.plot([-4, -14, -26, -26], [s*5, s*16, s*28, s*33], color=BLUE, lw=1.2, zorder=6)
        box(ax, -30, s*36 - 3, -22, s*36 + 3, fc='white', ec=INK, lw=.6, z=7)
        ax.plot([-22, -8, 0, 0], [s*36, s*39, s*44, y_hole], color=RED, lw=1.2, zorder=6)
        ax.text(8, s*66, f'Ø10 hole: {lab} track motor', fontsize=6.4, color=RED, ha='left', va='center')
    k = dict(fs=6.6)
    note(ax, (-30, -36), (-66, -46), '2-pin plugs\n(e.g. JST-XH 2)', relpos=(1, .5), ha='right', **k)
    note(ax, X.polar(PCD_R + 2.5, -120), (-66, 24), '3 × M3 × 8 + washer,\nreached with the\nbelly cover off', color=BUY, relpos=(1, .5), ha='right', **k)
    note(ax, (BODY_R*.7, -BODY_R*.7), (66, -30), 'stator end of\nthe slip ring', color=SLIP, relpos=(0, .5), **k)
    ax.annotate('front', (86, 22), (68, 22), fontsize=7.5, weight='bold', va='center', arrowprops=dict(arrowstyle='->', lw=.9))
    ax.set_xlim(-88, 88); ax.set_ylim(-70, 70); ax.set_aspect('equal'); ax.axis('off')


def bought_part(ax):
    ax.set_title("THE BOUGHT PART: the seller's drawing, redrawn rotor up", fontsize=10.5, loc='left', weight='bold')

    def side(x0, L, label, sub, dims=False):
        face, fz = 0.0, -RING['flange_back']           # rotor end of the body; flange top
        box(ax, x0 - BODY_R, face - L, x0 + BODY_R, face, fc=SLIP_L, ec=SLIP, lw=.8, z=3)
        box(ax, x0 - FLANGE_R, fz - RING['flange_t'], x0 + FLANGE_R, fz, fc=SLIP_L, ec=SLIP, lw=.8, z=4)
        box(ax, x0 - ROTOR_R, face, x0 + ROTOR_R, face + RING['rotor_l'], fc='#5dade2', ec=SLIP, lw=.8, z=4)
        for dx in (-1.5, 0, 1.5):
            ax.plot([x0 + dx, x0 + dx*1.5], [face + RING['rotor_l'], face + RING['rotor_l'] + 5], color=GREEN, lw=.9, zorder=5)
            ax.plot([x0 + dx*3, x0 + dx*5], [face - L, face - L - 5], color=BLUE, lw=.9, zorder=5)
        ax.text(x0, 26, label, fontsize=8.4, weight='bold', ha='center', va='bottom', color=INK)
        ax.text(x0, 24.5, sub, fontsize=7.0, ha='center', va='top', color=GREY)
        ax.text(x0 + BODY_R + 5.5, face + RING['rotor_l'] + 1.5, 'rotor', fontsize=6.4, color=SLIP, va='center')
        ax.text(x0 + BODY_R + 5.5 + (11 if dims else 3), face - L/2 - 3, 'stator', fontsize=6.4, color=SLIP, va='center')
        if dims:
            dim_v(ax, x0 + BODY_R + 4, face - L, face, f'L {L:g}', side=1, fs=7)
            dim_v(ax, x0 - FLANGE_R - 3, fz, face, '5', side=-1, fs=7)
            dim_v(ax, x0 - FLANGE_R - 3, fz - RING['flange_t'], fz, '', side=-1, fs=7)
            ax.text(x0 - FLANGE_R - 5.2, fz - RING['flange_t'] - .4, '2.4', fontsize=7, ha='right', va='top')
            dim_v(ax, x0 - ROTOR_R - 3, face, face + RING['rotor_l'], '9', side=-1, fs=7)
            dim_h(ax, x0 - ROTOR_R, x0 + ROTOR_R, face + RING['rotor_l'] + 6.5, 'Ø7.8', side=1, fs=7)
            dim_h(ax, x0 - BODY_R, x0 + BODY_R, face - L - 8, 'Ø22', side=-1, fs=7)
            zd = face + 3.0
            for sx in (-1, 1):
                ax.plot([x0 + sx*FLANGE_R]*2, [fz + .3, zd + 1.0], color=INK, lw=.4, zorder=11)
            ax.annotate('', (x0 - FLANGE_R, zd), (x0 + FLANGE_R, zd), arrowprops=dict(arrowstyle='<->', lw=.55, color=INK, shrinkA=0, shrinkB=0), zorder=11)
            ax.text(x0 + 13, zd + 1.2, 'Ø44', fontsize=7, ha='center', va='bottom', zorder=12)

    side(-58, RING['L'][6], '6-way 2 A', 'recommended', dims=True)
    side(18, RING['L'][12], '12-way 2 A', 'the same, but L 26')
    cx, cz = 92, -6
    ax.add_patch(Circle((cx, cz), FLANGE_R, fc=SLIP_L, ec=SLIP, lw=.8, zorder=3))
    ax.add_patch(Circle((cx, cz), PCD_R, fill=False, ec=SLIP, lw=.5, ls='-.', zorder=4))
    for a in HOLE_ANG:
        ax.add_patch(Circle((cx + PCD_R*math.cos(math.radians(a + 90)), cz + PCD_R*math.sin(math.radians(a + 90))), RING['hole_d']/2,
                            fc='white', ec=SLIP, lw=.6, zorder=5))
    ax.add_patch(Circle((cx, cz), BODY_R, fill=False, ec=SLIP, lw=.6, zorder=4))
    ax.add_patch(Circle((cx, cz), ROTOR_R, fc='#5dade2', ec=SLIP, lw=.6, zorder=5))
    ax.text(cx, 26, 'flange, from the rotor end', fontsize=8.4, weight='bold', ha='center', va='bottom')
    ax.text(cx, 24.5, '3 × Ø5.4 equally spaced on Ø35', fontsize=7.0, ha='center', va='top', color=GREY)
    note(ax, (cx + PCD_R*math.cos(math.radians(-30)), cz + PCD_R*math.sin(math.radians(-30))), (cx + 18, cz - 27), 'Ø35', fs=7, color=SLIP, relpos=(0, .5))
    ax.text(-95, -43, 'Green: rotor leads; blue: stator leads.   R1 had assumed the SRC022A-6: flange at the rotor end, 3 × Ø5.5, 12-way L 28.',
            fontsize=6.8, color=GREY, va='bottom')
    ax.set_xlim(-96, 120); ax.set_ylim(-46, 33); ax.set_aspect('equal'); ax.axis('off')


def sheet2(pdf, results):
    fig = plt.figure(figsize=FIG)
    s_aa = scale(**A_A)
    s_c = scale(DET['rect'], DET['xlim'], DET['ylim'])
    fig.text(.02, .968, 'X1 turntable drive and wiring  —  concept R2, sheet 2: the slip-ring mount', fontsize=17, weight='bold', color=INK)
    fig.text(.02, .947, f'Concept sketch, not CAD. All dimensions in mm. Detail C is {s_c/s_aa:.1f} × the scale of section A–A. '
                        'Nothing here is modelled yet; the clearances listed are computed from these sizes.', fontsize=10, color='#40585e')
    detail_c(fig.add_axes(DET['rect']))
    view_d(fig.add_axes([.005, .015, .2, .285]))
    view_e(fig.add_axes([.205, .015, .215, .285]))
    bought_part(fig.add_axes([.60, .69, .395, .235]))

    # clearances, bottom middle
    xm = .435
    fig.text(xm, .29, 'Clearances checked here', fontsize=10.5, weight='bold', color=INK, va='top')
    y = .262
    pick = ['collar bore to spigot, radial', 'insert hole top to the relief floor (skin)', 'screw thread in the insert',
            'dog above the stator face', 'dog hub to the prongs, radial', 'lug / prong overlap, height',
            'prong tips above the relief floor', 'prongs to the RU66 bore, radial', 'dog top to the hub, height',
            'hub spigot in the RU66 bore, radial', 'JST-XH 4 plug through the Ø15 lead hole, diagonal margin',
            '12-way stator end above the belly cover']
    for r in results:
        if r['check'] in pick:
            fig.text(xm, y, r['check'].replace(', diagonal margin', ''), fontsize=7.4, color='#2c3e50', va='top')
            fig.text(xm + .157, y, f"{r['value_mm']:g}", fontsize=7.4, color=GREEN if r['ok'] else RED, va='top', ha='right', weight='bold')
            y -= .0128
    npass = sum(r['ok'] for r in results)
    fig.text(xm, y - .004, wrap(f'{npass} of {len(results)} checks pass. All are listed, with what each one needs, in '
                                'X1_swing_concept_R2_checks.json.', 44), fontsize=7.2, color=GREY, va='top', linespacing=1.25)

    xa, xb = .605, .80
    kw = dict(fs=8.0, lh=.0122, tab=.016)
    y = text_blocks(fig, xa, .675, [
        ('6 or 12 rings?  6 recommended', [
            ('6', 'Enough: 4 rings for the two track\nmotors (each stalls at 1.3 A; a ring\ntakes 2 A), and 2 spare. The\n'
                  'shorter body ends at Z 60.'),
            ('12', 'Only if the track motors get Hall\nencoders (2 × 6 wires, + and − shared:\n10 circuits), or to run each motor\n'
                   'lead through two rings in parallel.\nThe body ends at Z 53, still 19 above\nthe belly cover.')]),
    ], **kw)
    rows = [('Ring', '6-way', '12-way'), ('1', 'left motor +', '1 + 2'), ('2', 'left motor −', '3 + 4'),
            ('3', 'right motor +', '5 + 6'), ('4', 'right motor −', '7 + 8'), ('5, 6', 'spare', '9 to 12 spare')]
    fig.text(xa, y, 'Ring allocation', fontsize=10.5, weight='bold', color=INK, va='top'); y -= .024
    for i, r in enumerate(rows):
        for c, w in zip(r, (0, .035, .11)):
            fig.text(xa + w, y, c, fontsize=8.0, color=INK if i == 0 else '#2c3e50', weight='bold' if i == 0 else 'normal', va='top')
        y -= .0148
    fig.text(xa, y - .002, wrap("The leads' colours are the seller's. Before wiring, buzz each rotor lead through to its "
                                'stator lead with a meter, and label both ends.', 44), fontsize=7.4, color=GREY, va='top', linespacing=1.25)

    y2 = text_blocks(fig, xb, .675, [
        ('Assembly order', [
            ('1', 'Push the TPU dog onto the rotor until\nits shoulder sits on the rotor end.'),
            ('2', 'Belly cover off. Thread the rotor leads\nup through the collar and the Ø25\npassage, then push the spigot into the\n'
                  'collar. The lugs (Ø19) pass its bore.'),
            ('3', 'Three M3 × 8 socket screws with\nwashers, from below.'),
            ('4', 'Plug the stator leads into the track-\nmotor leads; refit the belly cover. Fit\nthe RU66 (X1 as built).'),
            ('5', 'Feed the rotor leads up through the\nhub hole and lower the turntable. If a\nprong lands on a lug, turn the rotor by\n'
                  'hand and it drops. 8 × M4 into the\ninner ring.')]),
        ('Service', [
            ('•', 'Belly cover off: unplug the two track\nplugs, take out the three M3, and the\nring comes out downwards.'),
            ('•', 'The rotor leads end in one JST-XH\n4-pin plug at the drivers. It passes\nthe Ø15 hub hole, so the upper lifts\n'
                  'off once it is unplugged.')]),
    ], **kw)

    yb = min(y - .05, y2) - .004
    fig.text(xa, yb, 'Still to decide before I model it', fontsize=10.5, weight='bold', color=INK, va='top')
    asks = [('Slip ring', '6-way (recommended) or 12-way? Both fit the same collar.'),
            ('Swing motor', 'From R1, still open: the JGY-370 worm, i.e. the track motor\n(proposed), or a planetary gearmotor? '
                            '7.5 rpm (200:1) or 10 rpm (150:1)?'),
            ('Then I model', 'the collar and the 6 ring-gear inserts on X101, the TPU dog,\nthe ring gear and pinion, the turntable hub '
                             'with its prongs,\nand add the pinion path and prongs to the reserve and checks.')]
    yy = yb - .024
    for k_, v in asks:
        fig.text(xa, yy, k_, fontsize=8.0, weight='bold', color=INK, va='top')
        fig.text(xa + .07, yy, v, fontsize=8.0, color='#2c3e50', va='top', linespacing=1.3)
        yy -= .0122*(v.count('\n') + 1) + .006
    fig.text(.02, .004, "Sources: the seller's drawing of the 6-way / 12-way 2 A slip ring (references/bought_slip_ring_2A); Prosper SRC022 series "
                        'datasheet (R1 comparison); THK RU66 catalogue; JST XH housing XHP-4; ISO 4762 / ISO 7089 M3.',
             fontsize=7.3, color=GREY)
    pdf.savefig(fig); fig.savefig(PNG[1], dpi=110)
    plt.close(fig)


def main():
    results = checks()
    CHECKS.write_text(json.dumps(dict(
        concept='X1 swing concept R2: bought 6-way / 12-way 2 A slip ring', source=Path(__file__).name,
        ring=RING, collar=COLLAR, flange_z=FL_Z, stator_end_z=END_Z, rotor_z=ROTOR_Z, dog=DOG, hub=HUB, prong=PRONG,
        free_play_deg=round(free_play_deg(), 1), checks=results, all_ok=all(r['ok'] for r in results)), indent=1))
    with PdfPages(PDF) as pdf:
        sheet1(pdf)
        sheet2(pdf, results)
    bad = [r for r in results if not r['ok']]
    print('wrote', PDF, '|', len(results) - len(bad), 'of', len(results), 'checks pass')
    for r in bad:
        print('  FAIL', r)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())

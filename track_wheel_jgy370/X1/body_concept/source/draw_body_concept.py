"""X1 body, concept B1: the Caterpillar 320's upper body traced from Caterpillar's own drawing and render, fitted to
X1, with the battery, electronics and ballast packed inside. A sketch for review, not CAD.

Sheet 1  the reference: the Cat 320 dimension drawing (side and rear, orthographic) and the right-side render, traced.
Sheet 2  the X1 shell in four views over the existing machine; each number compared with the Cat at 1:15.
Sheet 3  inside the shell: battery, driver board, switch and charge port, ballast, cable routes, service access.
Sheet 4  print split, masses and balance, wiring diagram, checks, decisions.
Sheet 5  fewer parts: what a 256 printer allows (3 prints at least), and the pros and cons against 9 parts and one piece.

Sources (excavator_arm_60mm/references/SOURCES.md):
  cat320_spec_page_4.png  Cat 320 specifications, page 4: dimension drawing (side and rear views) and table
  cat320_view_018.jpg     Cat 320 product render, right side
X1 data: x1_scene.json.gz and turntable_scene.json.gz (the CAD as exported), simulation/turntable_mass_properties.json,
and the T101 / ARM60 seat numbers from swing_concept/source/draw_swing_concept_r3.py (imported, so they cannot drift).
Run:  LD_LIBRARY_PATH=/tmp/sw-tools/root/usr/lib/x86_64-linux-gnu /tmp/sw-venv/bin/python draw_body_concept.py
"""
import gzip, json, math, pickle, sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly, Circle
from matplotlib.lines import Line2D
from matplotlib.backends.backend_pdf import PdfPages
from PIL import Image, ImageDraw
import shapely
from shapely.geometry import Polygon, Point, LineString, box as sbox
from shapely import affinity

HERE = Path(__file__).resolve().parent
OUT = HERE.parent                                      # X1/body_concept
X1 = OUT.parent
REF = X1.parent.parent / 'excavator_arm_60mm/references'
sys.path.insert(0, str(X1 / 'swing_concept/source'))
import draw_swing_concept_r3 as R3                     # noqa: E402  T101, ARM60 seat, counterweight interface
X = R3.X

PDF = OUT / 'X1_body_concept_B1.pdf'
PNG = [OUT / f'X1_body_concept_B1_sheet{k}.png' for k in (1, 2, 3, 4, 5)]
CHECKS = OUT / 'X1_body_concept_B1_checks.json'
CACHE = Path('/tmp/sw-render/b1_silhouettes.pkl')
ISSUE = 'X1 body, concept B1 issue 2: sketch for review, not CAD'
FIG = (16.5, 11.7)

INK, GREY, LIGHT = '#1d2b2f', '#5f6f75', '#9aa7ab'
BODY, BODY_L, BODY_D = '#d35400', '#fde3cc', '#f6c49a'   # new body prints (orange: proposals, as in R1-R3)
TRACE = '#e0007a'                                        # trace lines over Caterpillar's images
UP, UP_L = '#1a5276', '#d4e6f1'                          # existing turntable prints
ARMC, ARM_L = '#6c3483', '#efe4f4'                       # existing ARM60
TRK, TRK_L = '#566573', '#dfe3e5'                        # tracks and chassis
GLASS = '#b9d3dc'
STEEL, STEEL_L = '#4d5656', '#aab7b8'
ELEC = dict(battery=('#1e8449', '#c8ebd3'), carrier=('#1f618d', '#cfe3f3'), power=('#7d3c98', '#e8daef'))
WIRE = dict(power='#c0392b', track='#2874a6', swing='#1e8449', arm='#8e44ad', charge='#d68910')

# ------------------------------------------------------------------ Caterpillar's numbers (spec page 4)
SPEC = dict(X.CAT320, cab_top=2960, handrail=2950)      # mm, full size
S15 = X.SCALE                                           # 15

# ------------------------------------------------------------------ traces, in image pixels
# Spec drawing: one scale for both views, 19.1 mm/px = tail swing 2830 over the 148 px of dimension 4 (swing axis at
# x 703, arrow at x 851). Ground line y 395. Rear view centreline x 192.75 (body edges x 120.8 and 264.7).
K = 19.1/S15                                            # mm at 1:15 per pixel
AXIS_X, GROUND_Y, REAR_CL = 703.0, 395.0, 192.75
SIDE_PX = dict(                                         # left side (cab side), front to the left
    band=[(632, 331), (846, 331), (849, 333), (849.5, 338), (847, 340), (632, 340)],
    cab=[(631.7, 331), (634.5, 300), (638, 262), (639.5, 242.5), (642, 240), (727.5, 240), (729.5, 242.5),
         (729.5, 281.7), (706, 331)],
    hood=[(706, 331), (729.5, 281.7), (746.7, 281.7), (760.8, 265.8), (843.3, 265.8), (847, 268.5), (848.5, 275),
          (848.5, 331)],
    glass1=[(642, 327), (642, 252), (645, 250), (690, 250), (690, 327)],
    glass2=[(694, 327), (694, 246), (717, 246), (719, 260), (719, 283), (703, 327)],
    exhaust=[(795.8, 265.8), (795.8, 255.8), (803.3, 255.8), (803.3, 265.8)],
    seams=[[(768, 268), (768, 331)], [(820.8, 268), (820.8, 331)]],
    louvres=[(774, 815, 269, 273), (774, 815, 280, 286), (774, 815, 292, 298), (774, 815, 305, 311),
             (784, 815, 315, 323)],
    track=[(586, 395), (822, 395)])
REAR_PX = dict(                                         # rear view: the machine's left (cab) on the viewer's left
    cw=(120.8, 266.7, 264.7, 340.0, 3.5),
    cab=[(121, 266.7), (121, 243), (124, 240), (171, 240), (174.2, 243), (174.2, 266.7)],
    glass=[(130, 266.7), (130, 250), (167, 250), (167, 266.7)],
    rail=[(231.7, 266.7), (231.7, 244), (235, 241.7), (252, 241.7), (256.7, 245), (256.7, 266.7)],
    exhaust=[(240.8, 266.7), (240.8, 255.8), (246.7, 255.8), (246.7, 266.7)],
    lamps=[(124.2, 144.2, 326, 331.5), (242.5, 261.7, 326, 331.5)])
# Right-side render (perspective, 1600 x 1200): X from the near track, 4450 mm over x 159-904, swing axis at the track
# centre x 531.5; Z by two points, the upper-frame bottom (y 870 = 70.0) and the hood top (y 640 = the drawing's 164.5).
PH = dict(axis=531.5, kx=5.97/S15, y0=870.0, y1=640.0)
PHOTO_PX = dict(
    cw=[(116, 873), (116, 660), (122, 648), (135, 641), (167, 640), (167, 873)],
    door=[(167, 640), (340, 640), (340, 848), (167, 848)],
    front_door=[(340, 640), (347.7, 648), (391, 702), (450, 836), (450, 848), (340, 848)],
    tank=[(373, 848), (373, 641), (455, 641), (455, 675), (500, 675), (500, 848)],
    toolbox=[(577, 848), (577, 776), (581, 772), (673, 772), (677, 776), (677, 848)],
    band=[(167, 848), (677, 848), (677, 873), (167, 873)],
    treads=[(470, 527, 743, 750), (469, 525, 774, 782), (455, 532, 841, 848)],
    exhaust=[(236, 640), (236, 614), (258, 614), (258, 640)],
    rail=[(373, 700), (373, 567), (422, 567), (448, 840)],
    track=[(159, 1065), (904, 1065)])


def side_mm(p):                                         # drawing, side view -> (X, Z) at 1:15
    return ((AXIS_X - p[0])*K, (GROUND_Y - p[1])*K)


def rear_mm(p):                                         # drawing, rear view -> (Y, Z) at 1:15, Y + = machine left
    return ((REAR_CL - p[0])*K, (GROUND_Y - p[1])*K)


HOOD_TOP_CAT = side_mm((0, 265.8))[1]                   # 164.5


def photo_mm(p):                                        # right-side render -> (X, Z) at 1:15
    kz = (HOOD_TOP_CAT - 70.0)/(PH['y0'] - PH['y1'])
    return ((p[0] - PH['axis'])*PH['kx'], 70.0 + (PH['y0'] - p[1])*kz)


def rrect(x0, y0, x1, y1, r, n=6):
    pts = []
    for cx, cy, a0 in ((x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180), (x1 - r, y0 + r, 270)):
        pts += [(cx + r*math.cos(math.radians(a)), cy + r*math.sin(math.radians(a))) for a in np.linspace(a0, a0 + 90, n)]
    return pts


# ------------------------------------------------------------------ the Cat at 1:15, measured on the traces
def cat_numbers():
    s, r, p = side_mm, rear_mm, photo_mm
    c = dict(
        deck=s((0, 331))[1], bottom=s((0, 340))[1], hood_top=HOOD_TOP_CAT, cab_top=s((0, 240))[1], step=s((0, 281.7))[1],
        cab_x=(s((729.5, 0))[0], s((631.7, 0))[0]), cab_low_rear=s((706, 0))[0], slope=(s((760.8, 0))[0], s((746.7, 0))[0]),
        rear_end=s((848.5, 0))[0], hood_rear=s((843.3, 0))[0], cw_seam_left=s((820.8, 0))[0], door_seam_left=s((768, 0))[0],
        exhaust_x=(s((803.3, 0))[0], s((795.8, 0))[0]), exhaust_top=s((0, 255.8))[1],
        track_length=(822 - 586)*K,
        half_width=r((120.8, 0))[0], rear_top=r((0, 266.7))[1], cab_y=(r((174.2, 0))[0], r((121, 0))[0]),
        exhaust_y=(r((246.7, 0))[0], r((240.8, 0))[0]), rail_y=(r((256.7, 0))[0], r((231.7, 0))[0]),
        rail_top_rear=r((0, 241.7))[1],
        cw_side_end=p((116, 0))[0], cw_seam_right=p((167, 0))[0], door_seam_right=p((340, 0))[0],
        tank_x=(p((373, 0))[0], p((455, 0))[0], p((500, 0))[0]), tank_top=p((0, 641))[1], tank_step=p((0, 675))[1],
        steps_x=(p((450, 0))[0], p((577, 0))[0]), toolbox_x=(p((577, 0))[0], p((677, 0))[0]), toolbox_top=p((0, 772))[1],
        rail_top=p((0, 567))[1], rail_x=(p((373, 0))[0], p((422, 0))[0]),
        front_door=[p(q) for q in ((340, 640), (347.7, 648), (391, 702), (450, 836))])
    c['tail'] = SPEC['tail_swing_radius']/S15
    c['spec_half_width'] = SPEC['upperframe_width']/2/S15
    c['cw_corner_x'] = -math.sqrt(c['tail']**2 - c['spec_half_width']**2)
    c['tank_inner_y'] = -30.0          # estimate from the front render (cat320_view_009.jpg, perspective): +-5
    return c


CAT = cat_numbers()

# ------------------------------------------------------------------ Cat -> X1
# X stays at 1:15 (the X1 tracks and the ARM60 are 1:15 in length). Heights above the deck stay at 1:15 over the
# T101 rib tops (Z 136, where the ARM60 sits). The Cat's 11.5 deep frame band below the deck stretches to cover the
# 31 mm of T101 above the swing envelope (Z 105-136). The width grows from 185.3 to 308: the ARM60 base is 164 wide,
# so the same DY is inserted on each side of the centreline and every Cat part keeps its own width.
W = 154.0                                              # X1 half width: ARM60 base 82 + 3 + the Cat cab's 68 + 1
DY = W - CAT['spec_half_width']                        # 61.3
Z_DECK, Z_BOT = R3.TOPZ, 105.0
CWF = R3.REAR_BULK[0]                                  # -145: counterweight front = T101 rear face (Cat seam -145 / -149)
TAIL = CAT['tail']                                     # 188.7


def zmap(z):
    if z >= CAT['deck']:
        return z + Z_DECK - CAT['deck']
    return Z_BOT + (z - CAT['bottom'])*(Z_DECK - Z_BOT)/(CAT['deck'] - CAT['bottom'])


def ymap(y):
    return y + math.copysign(DY, y)


def xz(pts):
    return [(x, zmap(z)) for x, z in pts]


B = dict(hood_top=zmap(CAT['hood_top']), cab_top=zmap(CAT['cab_top']), step=zmap(CAT['step']),
         tank_top=zmap(CAT['tank_top']), tank_step=zmap(CAT['tank_step']), toolbox_top=zmap(CAT['toolbox_top']),
         exhaust_top=zmap(CAT['exhaust_top']), rail_top=zmap(CAT['rail_top']),
         cab_x=CAT['cab_x'], cab_y=(ymap(CAT['cab_y'][0]), W), inner=77.0, wall=2.0,
         left_front=92.0, right_front=60.0, tank_y=(ymap(CAT['tank_inner_y']), -W))
ARM_X = (R3.ARM_X0 + R3.ARM_BASE['x'][0], R3.ARM_X0 + R3.ARM_BASE['x'][1])   # -21, 111
ARM_Y = R3.ARM_BASE['y']                                                     # 82
BED = 256.0


def cw_plan(n=28):
    """Counterweight plan: the Cat's tail arc (R 188.7 about the swing axis) split on the centreline, the halves moved out
    by DY, a straight middle between them; sides forward to the T101 rear face."""
    a0 = math.atan2(CAT['spec_half_width'], CAT['cw_corner_x'])
    left = [(TAIL*math.cos(t), DY + TAIL*math.sin(t)) for t in np.linspace(a0, math.pi, n)]
    right = [(x, -y) for x, y in reversed(left)]
    return [(CWF, W)] + left + right + [(CWF, -W)]


def cw_side(r_top=8.0, r_bot=3.0):
    """Counterweight seen from the side (both sides): X -188.7 to -145, Z 105 to the hood top, rear corners rounded."""
    zt = B['hood_top']
    pts = [(CWF, Z_BOT), (CWF, zt)]
    pts += [(-TAIL + r_top + r_top*math.cos(t), zt - r_top + r_top*math.sin(t)) for t in np.linspace(math.pi/2, math.pi, 8)]
    pts += [(-TAIL + r_bot + r_bot*math.cos(t), Z_BOT + r_bot + r_bot*math.sin(t)) for t in np.linspace(math.pi, 1.5*math.pi, 5)]
    return pts


PLAN = dict(
    cw=cw_plan(),
    left_module=[(CWF, B['inner']), (B['left_front'], B['inner']), (B['left_front'], W), (CWF, W)],
    right_module=[(CWF, -B['inner']), (B['right_front'], -B['inner']), (B['right_front'], -W), (CWF, -W)],
    lid_left=[(CWF, 0), (CWF, W - 2.5), (B['cab_x'][0] - 1.3, W - 2.5), (B['cab_x'][0] - 1.3, ARM_Y + 2), (ARM_X[0] - 2, ARM_Y + 2),
              (ARM_X[0] - 2, 0)],
    lid_right=[(CWF, 0), (ARM_X[0] - 2, 0), (ARM_X[0] - 2, B['tank_y'][0] + 2), (CAT['tank_x'][0] - 2, B['tank_y'][0] + 2),
               (CAT['tank_x'][0] - 2, -W + 2.5), (CWF, -W + 2.5)],
    cab=[(B['cab_x'][0], B['cab_y'][0]), (B['cab_x'][1], B['cab_y'][0]), (B['cab_x'][1], W), (B['cab_x'][0], W)],
    tank=[(CAT['tank_x'][0], B['tank_y'][0]), (CAT['tank_x'][2], B['tank_y'][0]), (CAT['tank_x'][2], -W + 2.5),
          (CAT['tank_x'][0], -W + 2.5)],
    toolbox=[(CAT['toolbox_x'][0], B['tank_y'][0]), (CAT['toolbox_x'][1], B['tank_y'][0]), (CAT['toolbox_x'][1], -W),
             (CAT['toolbox_x'][0], -W)],
    steps=[(CAT['steps_x'][0], -120.0), (CAT['steps_x'][1], -120.0), (CAT['steps_x'][1], -W), (CAT['steps_x'][0], -W)])
EXHAUST = ((sum(CAT['exhaust_x'])/2, ymap(sum(CAT['exhaust_y'])/2)), (CAT['exhaust_x'][1] - CAT['exhaust_x'][0])/2)
RAIL_Y = (ymap(CAT['rail_y'][0]), ymap(CAT['rail_y'][1]))

# ------------------------------------------------------------------ what goes inside (envelopes: x0, x1, y0, y1, z0, z1)
WALL_IN = dict(left=(CWF + 2.5, B['left_front'] - 2.5, B['inner'] + 2.5, W - 2.5),
               right=(CWF + 2.5, B['right_front'] - 2.5, -W + 2.5, -B['inner'] - 2.5))
FLOOR_TOP = Z_BOT + 2.5
ITEMS = dict(
    battery=dict(env=(-139.0, -81.0, -149.0, -81.0, FLOOR_TOP + 1, FLOOR_TOP + 27), kg=.165, color='battery',
                 label='battery: 3S1P 18650 pack (3 cells\nside by side) + 3S BMS, 58 × 68 × 26'),
    carrier=dict(env=(-136.0, -40.0, 84.0, 148.0, FLOOR_TOP + 2.5, FLOOR_TOP + 26.5), kg=.075, color='carrier',
                 label='controller board 96 × 64 on standoffs:\nESP32, 3 × DRV8871, 2 × DRV8833,\n6 V and 5 V bucks'),
    switch=dict(env=(24.0, 45.0, -112.0, -97.0, Z_DECK + 4, Z_DECK + 26), kg=.008, color='power',
                label='main switch'),
    fuse=dict(env=(24.0, 45.0, -128.0, -116.0, Z_DECK + 4, Z_DECK + 22), kg=.006, color='power', label='5 A fuse'),
    jack=dict(env=(30.0, 50.0, -148.0, -134.0, Z_DECK + 6, Z_DECK + 20), kg=.006, color='power',
              label='charge jack'))
WIRING_KG, FIXINGS_KG = .05, .03
SHOT_DENSITY = 4.5e-3                                    # g/mm3: steel shot, poured (random packing, about 57 %)
PETG = 1.27e-3                                           # g/mm3
BOSS_FACTOR = 1.15                                       # bosses, ribs and lips over the plain walls


# ------------------------------------------------------------------ drawing helpers
def patch(ax, pts, fc='none', ec=INK, lw=.6, hatch=None, ls='-', z=3, alpha=1.0, closed=True):
    ax.add_patch(MPoly(pts, closed=closed, fc=fc, ec=ec, lw=lw, hatch=hatch, ls=ls, zorder=z, alpha=alpha))


def box(ax, x0, y0, x1, y1, **k):
    patch(ax, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], **k)


def line(ax, pts, color=INK, lw=.6, ls='-', z=4, **k):
    a = np.asarray(pts, float)
    ax.plot(a[:, 0], a[:, 1], color=color, lw=lw, ls=ls, zorder=z, solid_capstyle='round', **k)


def shape(ax, g, fc, ec, lw=.6, z=2, ls='-', alpha=1.0, hatch=None):
    for p in getattr(g, 'geoms', [g]):
        if p.is_empty or p.geom_type != 'Polygon':
            continue
        patch(ax, list(p.exterior.coords), fc=fc, ec=ec, lw=lw, z=z, ls=ls, alpha=alpha, hatch=hatch)
        for h in p.interiors:
            patch(ax, list(h.coords), fc='white', ec=ec, lw=lw*.7, z=z + .01, ls=ls, alpha=alpha)


def note(ax, xy, txt, text, fs=6.8, color=INK, ha='left', va='center', relpos=None, boxed=False):
    props = dict(arrowstyle='-', lw=.5, color=color, shrinkA=1, shrinkB=0)
    if relpos:
        props['relpos'] = relpos
    bb = dict(boxstyle='round,pad=0.18', fc='white', ec='none', alpha=.85) if boxed else None
    ax.annotate(text, xy, txt, fontsize=fs, color=color, ha=ha, va=va, arrowprops=props, zorder=20, bbox=bb)


def dim_h(ax, x0, x1, y, text, side=1, fs=6.6, color=INK, off=1.5):
    ax.annotate('', (x0, y), (x1, y), arrowprops=dict(arrowstyle='<->', lw=.5, color=color, shrinkA=0, shrinkB=0), zorder=15,
                annotation_clip=False)
    ax.text((x0 + x1)/2, y + side*off, text, ha='center', va='bottom' if side > 0 else 'top', fontsize=fs, color=color, zorder=16)


def dim_v(ax, x, y0, y1, text, side=1, fs=6.6, color=INK, off=1.8):
    ax.annotate('', (x, y0), (x, y1), arrowprops=dict(arrowstyle='<->', lw=.5, color=color, shrinkA=0, shrinkB=0), zorder=15,
                annotation_clip=False)
    ax.text(x + side*off, (y0 + y1)/2, text, rotation=90, va='center', ha='left' if side > 0 else 'right', fontsize=fs,
            color=color, zorder=16)


def fit(ax, cx, cy, mm_per_in, flip_x=False):
    """Equal-scale view: the same paper scale on every view that uses the same mm_per_in."""
    fig = ax.figure
    bb = ax.get_position()
    w, h = bb.width*fig.get_figwidth()*mm_per_in, bb.height*fig.get_figheight()*mm_per_in
    ax.set_xlim((cx + w/2, cx - w/2) if flip_x else (cx - w/2, cx + w/2))
    ax.set_ylim(cy - h/2, cy + h/2)
    ax.set_aspect('equal', adjustable='box')
    ax.axis('off')


def title(ax, text, sub=None):
    ax.set_title(text, fontsize=10.2, loc='left', weight='bold', color=INK, pad=3)
    if sub:
        ax.text(0, .995, sub, transform=ax.transAxes, fontsize=7.2, color=GREY, va='top', ha='left')


def header(fig, sheet, title_, sub):
    fig.text(.02, .968, f'X1 body  —  concept B1, sheet {sheet} of 5: {title_}', fontsize=17, weight='bold', color=INK)
    fig.text(.02, .947, sub, fontsize=9.4, color='#40585e')
    fig.text(.985, .006, ISSUE, fontsize=7.6, color=GREY, ha='right')


def text_blocks(fig, x, y, blocks, fs=8.0, lh=.0122, tab=.013, head_fs=10.0):
    for head, items in blocks:
        fig.text(x, y, head, fontsize=head_fs, weight='bold', color=INK, va='top'); y -= .021
        for tag, text in items:
            fig.text(x, y, tag, fontsize=fs, weight='bold', color=INK, va='top')
            fig.text(x + tab, y, text, fontsize=fs, color='#2c3e50', va='top', linespacing=1.3)
            y -= lh*(text.count('\n') + 1) + .005
        y -= .006
    return y


def table(fig, x, y, widths, rows, fs=7.3, lh=.0128, head_color=INK, colors=None, bold_rows=()):
    """Rows of strings (the first is the header); returns the y below the table."""
    fig.add_artist(Line2D([x, x + sum(widths)], [y + .004, y + .004], lw=.7, color=INK, transform=fig.transFigure))
    for i, row in enumerate(rows):
        n = max(str(c).count('\n') + 1 for c in row)
        cx = x
        for j, c in enumerate(row):
            col = (colors[i][j] if colors and colors[i] and colors[i][j] else ('#2c3e50' if i else head_color))
            fig.text(cx + .003, y, str(c), fontsize=fs, va='top', color=col, linespacing=1.22,
                     weight='bold' if (i == 0 or i in bold_rows) else 'normal')
            cx += widths[j]
        y -= lh*n + .0045
        fig.add_artist(Line2D([x, x + sum(widths)], [y + .0028, y + .0028], lw=.7 if i == 0 else .35,
                              color=INK if i == 0 else '#c5cdd0', transform=fig.transFigure))
    return y


# ------------------------------------------------------------------ the existing machine: silhouettes from the CAD
def _proj(V, T, view):
    a, b = dict(xz=(0, 2), xy=(0, 1), yz=(1, 2))[view]
    P = V[T][:, :, [a, b]]
    ar = .5*np.abs((P[:, 1, 0] - P[:, 0, 0])*(P[:, 2, 1] - P[:, 0, 1]) - (P[:, 2, 0] - P[:, 0, 0])*(P[:, 1, 1] - P[:, 0, 1]))
    return P[ar > 1e-3]


def _union(parts, res=.25):
    """Outline of many projected triangles: fill them on a 0.25 mm raster, trace the edge, back to polygons."""
    from contourpy import contour_generator, FillType
    P = np.concatenate(parts)
    lo = P.reshape(-1, 2).min(0) - 2.0
    hi = P.reshape(-1, 2).max(0) + 2.0
    n = np.ceil((hi - lo)/res).astype(int) + 1
    img = Image.new('L', (int(n[0]), int(n[1])), 0)
    d = ImageDraw.Draw(img)
    for t in (P - lo)/res:
        d.polygon([(t[0, 0], t[0, 1]), (t[1, 0], t[1, 1]), (t[2, 0], t[2, 1])], fill=255, outline=255)
    z = (np.asarray(img) > 127).astype(np.float32)
    polys, offs = contour_generator(z=z, fill_type=FillType.OuterOffset).filled(.5, 2.0)
    out = []
    for pts, of in zip(polys, offs):
        rings = [lo + pts[of[k]:of[k + 1]]*res for k in range(len(of) - 1)]
        if len(rings[0]) >= 4:
            out.append(Polygon(rings[0], [r for r in rings[1:] if len(r) >= 4]).buffer(0))
    return shapely.union_all(out).simplify(.15)


def mesh_vc(V, T):
    """Volume and centroid of a closed triangle mesh (divergence theorem)."""
    v0, v1, v2 = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    d = np.einsum('ij,ij->i', v0, np.cross(v1, v2))
    return d.sum()/6, ((v0 + v1 + v2)*d[:, None]).sum(0)/(4*d.sum())


def scene():
    srcs = [X1 / 'source/x1_scene.json.gz', X1 / 'source/turntable_scene.json.gz']
    key = [p.stat().st_mtime for p in srcs] + [4]
    if CACHE.exists():
        d = pickle.loads(CACHE.read_bytes())
        if d.get('key') == key:
            return d
    s, t = (json.load(gzip.open(p)) for p in srcs)
    ty = s['config']['track_y']
    def arr(it, dy=0.0, mirror=False):
        V = np.asarray(it['vertices'], float).copy()
        V[:, 1] += dy
        if mirror:
            V[:, 1] *= -1
        return V, np.asarray(it['triangles'], int)
    groups = {'tracks': [], 'chassis': [], 'turntable': [], 'arm_base': [], 'arm': []}
    for it in s['module']:
        groups['tracks'] += [arr(it, ty), arr(it, ty, True)]
    for it in s['chassis']:
        if it['name'].startswith(('X101', 'X102', 'RU66')):
            groups['chassis'].append(arr(it))
    vc = {}
    for it in t['items']:
        n = it['name']
        if n.startswith('X103'):
            groups['chassis'].append(arr(it))
        elif n.startswith(('T101', 'T102', 'T104', 'JGY370_gearbox', 'JGY370_motor_can')):
            groups['turntable'].append(arr(it))
        elif n == 'ARM60_fixed_pivot_base':
            groups['arm_base'].append(arr(it)); vc['arm_base'] = mesh_vc(*arr(it))
        elif n == 'ARM60_arm_and_actuators':
            groups['arm'].append(arr(it)); vc['arm'] = mesh_vc(*arr(it))
    # highest lower part where the body can pass over it (r > 70: the body is outside |Y| 77 and behind X -145)
    def zmax_out(V):
        m = np.hypot(V[:, 0], V[:, 1]) > 70.0
        return float(V[m, 2].max()) if m.any() else -1e9
    lows = [arr(i, ty) for i in s['module']] + [arr(i) for i in s['chassis'] if not i['name'].startswith(('RESERVED', 'reserved'))]
    lows += [arr(i) for i in t['items'] if i['group'] in ('lower', 'rotor')]
    lower_zmax = max([zmax_out(V) for V, _ in lows] + [s['config']['key']['track_top']])
    sil = {}
    for g, meshes in groups.items():
        for view in ('xz', 'xy', 'yz'):
            if g == 'tracks' and view == 'xz':
                meshes_v = meshes[::2]
            else:
                meshes_v = meshes
            sil[(g, view)] = _union([_proj(V, T, view) for V, T in meshes_v])
    # the shoe belt: pin loop + shoe depth (J910: 7 below the pin line), 70 wide
    pins = np.asarray(s['j9']['pins'], float)
    loop = Polygon(pins).convex_hull.buffer(7.0)
    sil[('belt', 'xz')] = loop
    x0, z0, x1, z1 = loop.bounds
    sil[('belt', 'xy')] = shapely.union_all([sbox(x0, ty - 35, x1, ty + 35), sbox(x0, -ty - 35, x1, -ty + 35)])
    sil[('belt', 'yz')] = shapely.union_all([sbox(ty - 35, z0, ty + 35, z1), sbox(-ty - 35, z0, -ty + 35, z1)])
    d = dict(key=key, sil=sil, vc=vc, lower_zmax=lower_zmax, track_top=s['config']['key']['track_top'],
             sprocket_to_idler=s['config']['key']['sprocket_to_idler'], drive_x=s['j9']['drive'][0], idler_x=s['j9']['idler'][0],
             track_y=ty, shoe=s['config']['key']['shoe_width'], track_length=s['config']['key']['track_length'])
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_bytes(pickle.dumps(d))
    return d


def context(ax, sc, view, arm=True, turntable=False, alpha=1.0):
    S = sc['sil']
    shape(ax, S[('belt', view)], TRK_L, TRK, lw=.5, z=1)
    shape(ax, S[('tracks', view)], '#eceff0', TRK, lw=.4, z=1.2)
    shape(ax, S[('chassis', view)], '#f6efcf', '#b7950b', lw=.4, z=1.1)
    if turntable:
        shape(ax, S[('turntable', view)], 'none', UP, lw=.5, z=6, ls='--')
    shape(ax, S[('arm_base', view)], ARM_L, ARMC, lw=.6, z=1.5, ls='--')
    if arm:
        shape(ax, S[('arm', view)], ARM_L, ARMC, lw=.45, z=1.4, alpha=alpha)


# ------------------------------------------------------------------ numbers
def shell_parts():
    """Printed body parts: plain-wall area (mm2), wall (mm), centre (x, y, z), size for the bed (x, y, z), note."""
    cw = Polygon(PLAN['cw'])
    H = B['hood_top'] - Z_BOT
    cab_l, cab_w, cab_h = B['cab_x'][1] - B['cab_x'][0], W - B['cab_y'][0], B['cab_top'] - Z_DECK
    lm_l, rm_l = B['left_front'] - CWF, B['right_front'] - CWF
    mw, sk = W - B['inner'], Z_DECK - Z_BOT
    up_h = B['hood_top'] - Z_DECK
    tank_l, tank_w, tank_h = CAT['tank_x'][2] - CAT['tank_x'][0], B['tank_y'][0] - (-W + 2.5), B['tank_top'] - Z_DECK
    tb_l, tb_w, tb_h = CAT['toolbox_x'][1] - CAT['toolbox_x'][0], B['tank_y'][0] + W, B['toolbox_top'] - Z_DECK
    lid_l = Polygon(PLAN['lid_left'])
    lid_r = Polygon(PLAN['lid_right'])
    fd = CAT['front_door']
    front_door_area = .5*(fd[0][1] - CAT['deck'] + 0)*(fd[-1][0] - fd[0][0])
    P = {
        'B101 counterweight shell': dict(area=2*cw.area + cw.length*H, wall=3.0,
                                         c=(cw.centroid.x, 0, (Z_BOT + B['hood_top'])/2), size=None, poly=cw, h=H,
                                         note='closed box; ballast pocket and lead channel inside'),
        'B102 left side module': dict(area=lm_l*mw + 2*lm_l*sk + 2*mw*sk + (B['cab_x'][0] - CWF)*up_h
                                      + .5*(CAT['cab_low_rear'] - CAT['cab_x'][0])*(B['step'] - Z_DECK) + cab_l*mw, wall=2.0,
                                      c=((CWF + B['left_front'])/2, (B['inner'] + W)/2, 140.0),
                                      size=(lm_l, mw, H), note='floor, skirt, side wall with the louvres, cab deck'),
        'B103 right side module': dict(area=rm_l*mw + 2*rm_l*sk + 2*mw*sk + (CAT['door_seam_right'] - CWF)*up_h
                                       + front_door_area + (B['right_front'] - CAT['tank_x'][0])*mw, wall=2.0,
                                       c=((CWF + B['right_front'])/2, -(B['inner'] + W)/2, 135.0),
                                       size=(rm_l, mw, H), note='floor, skirt, engine and pump doors, steps'),
        'B104 hood lid, left': dict(area=1.3*lid_l.area, wall=2.0, c=(lid_l.centroid.x, lid_l.centroid.y, B['hood_top'] - 6),
                                    size=(lid_l.bounds[2] - lid_l.bounds[0], lid_l.bounds[3] - lid_l.bounds[1], B['hood_top'] - B['step'] + 3),
                                    note='hood top, slope and step; 4 magnets'),
        'B105 hood lid, right': dict(area=1.3*lid_r.area, wall=2.0, c=(lid_r.centroid.x, lid_r.centroid.y, B['hood_top'] - 6),
                                     size=(lid_r.bounds[2] - lid_r.bounds[0], lid_r.bounds[3] - lid_r.bounds[1], B['hood_top'] - B['step'] + 3),
                                     note='hood top with the exhaust; 4 magnets'),
        'B106 cab': dict(area=2*(cab_l + cab_w)*cab_h + cab_l*cab_w, wall=2.0, c=(sum(B['cab_x'])/2, (B['cab_y'][0] + W)/2, Z_DECK + cab_h/2),
                         size=(cab_l, cab_w, cab_h), note='window recesses; 4 x M3 into the module deck'),
        'B107 tank block': dict(area=2*(tank_l + tank_w)*tank_h + tank_l*tank_w, wall=2.0,
                                c=(sum(CAT['tank_x'][::2])/2, (B['tank_y'][0] - W)/2, Z_DECK + tank_h/2),
                                size=(tank_l, tank_w, tank_h), note='spare space (receiver or speaker later)'),
        'B108 toolbox lid and box': dict(area=2*(tb_l + tb_w)*tb_h + tb_l*tb_w, wall=2.0,
                                         c=(sum(CAT['toolbox_x'])/2, (B['tank_y'][0] - W)/2, Z_DECK + tb_h/2),
                                         size=(tb_l, tb_w, tb_h), note='switch, fuse, charge jack under the lid'),
        'B109 details': dict(area=6000.0, wall=1.6, c=(-80.0, -100.0, 225.0), size=(60, 10, 60),
                             note='exhaust stack, 2 handrails, mirrors (optional)'),
    }
    for n, p in P.items():
        p['kg'] = p['area']*p['wall']*PETG*BOSS_FACTOR/1000
    return P


def bed_fit(p):
    """Smallest square bed side the part needs: footprint as it prints, straight or turned on the bed."""
    if p['size'] is None:                              # the counterweight prints upright on its bottom face
        g = p['poly']
        best = min((max(affinity.rotate(g, a, origin='centroid').bounds[2] - affinity.rotate(g, a, origin='centroid').bounds[0],
                        affinity.rotate(g, a, origin='centroid').bounds[3] - affinity.rotate(g, a, origin='centroid').bounds[1]), a)
                   for a in range(0, 91, 1))
        return dict(side=best[0], angle=best[1], height=p['h'], how=f'upright, turned {best[1]}° on the bed')
    a, b, c = sorted(p['size'], reverse=True)
    if a <= BED:
        return dict(side=a, angle=0, height=c, how='flat, straight')
    side = (a + b)/math.sqrt(2)
    return dict(side=side, angle=45, height=c, how='flat, turned 45°')


def ballast_pocket():
    """Inside of the counterweight below the lead channel: plan inset 3, minus the channel (Y +-12 to X -163) and the two
    M4 nut bosses at Y +-40 (12 x 12)."""
    g = Polygon(PLAN['cw']).buffer(-3.0, join_style=2)
    g = g.difference(sbox(CWF - 20, -12, CWF + 1, 12))
    for s in (1, -1):
        g = g.difference(sbox(CWF - 12, s*40 - 6, CWF + 1, s*40 + 6))
    return g


def polar_moment(g, step=1.0):
    x0, y0, x1, y1 = g.bounds
    xs, ys = np.meshgrid(np.arange(x0 + step/2, x1, step), np.arange(y0 + step/2, y1, step))
    pts = shapely.points(xs.ravel(), ys.ravel())
    inside = shapely.contains(g, pts)
    px, py = xs.ravel()[inside], ys.ravel()[inside]
    return float(((px**2 + py**2)*step*step).sum()), float(inside.sum()*step*step), float(px.mean()), float(py.mean())


def estimates(sc):
    mp = json.loads((X1 / 'simulation/turntable_mass_properties.json').read_text())
    SIM = json.loads((X1 / 'simulation/turntable_swing_report.json').read_text())
    cad = mp['upper_cad_only']
    m_cad, c_cad = cad['mass_kg'], np.array(cad['centre_m'])*1000
    I_cad_axis = cad['inertia_kgm2'][2][2] + m_cad*((c_cad[0]/1000)**2 + (c_cad[1]/1000)**2)
    arm_kg = mp['assumptions']['arm_kg']
    vb, cb = sc['vc']['arm_base']; va, ca = sc['vc']['arm']
    m_base, m_arm = arm_kg*vb/(vb + va), arm_kg*va/(vb + va)
    m_t101 = m_cad - arm_kg
    c_t101 = (m_cad*c_cad - m_base*cb - m_arm*ca)/m_t101
    rows = [dict(name='T101 group (turntable upper, CAD)', kg=m_t101, c=c_t101, group='existing'),
            dict(name='ARM60 base (CAD)', kg=m_base, c=cb, group='existing'),
            dict(name='ARM60 arm, stretched (CAD)', kg=m_arm, c=ca, group='existing')]
    P = shell_parts()
    I_body = 0.0
    for n, p in P.items():
        rows.append(dict(name=n, kg=p['kg'], c=np.array(p['c'], float), group='shell'))
        sx, sy = (p['size'][0], p['size'][1]) if p['size'] else (TAIL + CWF, 2*W)
        I_body += p['kg']*((p['c'][0]**2 + p['c'][1]**2) + (sx**2 + sy**2)/12)*1e-6
    for n, it in ITEMS.items():
        e = it['env']
        c = np.array([(e[0] + e[1])/2, (e[2] + e[3])/2, (e[4] + e[5])/2])
        rows.append(dict(name={'battery': 'battery pack + BMS', 'carrier': 'controller board (ESP32 + drivers)',
                               'switch': 'main switch', 'fuse': 'fuse and holder', 'jack': 'charge jack'}[n],
                         kg=it['kg'], c=c, group='electronics'))
        I_body += it['kg']*(c[0]**2 + c[1]**2)*1e-6
    rows.append(dict(name='wiring', kg=WIRING_KG, c=np.array([-60.0, 20.0, 140.0]), group='electronics'))
    rows.append(dict(name='screws, inserts, magnets', kg=FIXINGS_KG, c=np.array([-40.0, 0.0, 150.0]), group='shell'))
    I_body += (WIRING_KG*(60**2 + 20**2) + FIXINGS_KG*40**2)*1e-6
    # ballast: steel shot in the counterweight pocket, sized for the upper's CG on the swing axis with the arm stretched
    pocket = ballast_pocket()
    J, A, px, py = polar_moment(pocket)
    mx = sum(r['kg']*r['c'][0] for r in rows)
    m_shot = -mx/px
    vol = m_shot*1000/SHOT_DENSITY
    h = vol/A
    shot = dict(name='ballast: steel shot', kg=m_shot, c=np.array([px, py, FLOOR_TOP + 3 + h/2]), group='ballast')
    rows.append(shot)
    I_body += m_shot*J/A*1e-6
    m_up = sum(r['kg'] for r in rows)
    c_up = sum(r['kg']*r['c'] for r in rows)/m_up
    I_up = I_cad_axis + I_body                            # CAD part (arm stretched) about the axis + the body
    # tucked-arm bound: every moving arm part at the ARM60 base centre (a tucked arm stays ahead of its foot pin)
    c_tucked = c_up + m_arm*(cb - ca)/m_up
    low = mp['lower']
    m_low, c_low = low['mass_kg'], np.array(low['centre_m'])*1000
    def machine(cu):
        return (m_up*cu + m_low*c_low)/(m_up + m_low)
    sup = (sc['drive_x'], sc['idler_x'])
    est = dict(rows=rows, pocket=pocket, pocket_area=A, shot_kg=m_shot, shot_cm3=vol/1000, shot_h=h,
               fill_z=FLOOR_TOP + 3 + h, m_up=m_up, c_up=c_up, I_up=I_up, c_tucked=c_tucked,
               machine_stretched=machine(c_up), machine_tucked=machine(c_tucked), m_low=m_low, support=sup,
               sim=dict(m=mp['upper']['mass_kg'], I=mp['upper_inertia_about_swing_axis_kgm2'], cx=mp['upper']['centre_m'][0]*1000,
                        I_rotor=SIM['parameters']['reflected_rotor_inertia_at_turntable_kgm2'],
                        stop_N=SIM['cases']['start_stop_step']['peak_tooth_force_N']),
               shells_kg=sum(r['kg'] for r in rows if r['group'] == 'shell'),
               elec_kg=sum(r['kg'] for r in rows if r['group'] == 'electronics'), parts=P, I_cad_axis=I_cad_axis,
               m_arm=m_arm, c_arm=ca, m_base=m_base, c_base=cb)
    return est


# ------------------------------------------------------------------ X1 shell views
def left_view(ax, sc, est=None, labels=True):
    """From the machine's left (+Y): front to the left, as Caterpillar draws it."""
    context(ax, sc, 'xz')
    ho = dict(fc=BODY_L, ec=BODY, lw=.9, z=5)
    patch(ax, cw_side(), **ho)
    box(ax, CWF, Z_BOT, B['left_front'], Z_DECK, **ho)
    hood = [(CAT['cab_low_rear'], Z_DECK), (CAT['cab_x'][0], B['step']), (CAT['slope'][1], B['step']), (CAT['slope'][0], B['hood_top']),
            (CWF, B['hood_top']), (CWF, Z_DECK)]
    patch(ax, hood, **ho)
    patch(ax, xz([side_mm(p) for p in SIDE_PX['cab']]), fc='#fbeee2', ec=BODY, lw=.9, z=5.2)
    for g in ('glass1', 'glass2'):
        patch(ax, xz([side_mm(p) for p in SIDE_PX[g]]), fc=GLASS, ec=BODY, lw=.5, z=5.4)
    for x0, x1, y0, y1 in SIDE_PX['louvres']:
        (a, za), (b, zb) = side_mm((x0, y0)), side_mm((x1, y1))
        box(ax, a, zmap(za), b, zmap(zb), fc=BODY_D, ec=BODY, lw=.4, z=5.3)
    ex = xz([side_mm(p) for p in SIDE_PX['exhaust']])
    patch(ax, ex, fc='#7f8c8d', ec=INK, lw=.5, z=4.5)
    line(ax, [(CAT['door_seam_left'], Z_DECK), (CAT['door_seam_left'], B['hood_top'] - 2)], color=BODY, lw=.45, z=5.5)
    line(ax, [(CWF, Z_BOT), (CWF, B['hood_top'])], color=BODY, lw=.7, z=5.6)
    if labels:
        dim_v(ax, -TAIL - 12, 0, B['hood_top'], f"{B['hood_top']:.0f}", side=-1)
        dim_v(ax, -TAIL - 24, 0, B['cab_top'], f"{B['cab_top']:.0f}", side=-1)
        dim_h(ax, -TAIL, CWF, Z_BOT - 9, f'{TAIL + CWF:.1f}', side=-1)
        dim_h(ax, CAT['cab_x'][0], CAT['cab_x'][1], B['cab_top'] + 4, f"cab {CAT['cab_x'][1] - CAT['cab_x'][0]:.0f}", side=1)
        dim_h(ax, CWF, 0, Z_BOT - 9, f'{-CWF:.0f}', side=-1)
        ax.plot([0, 0], [-5, 262], color=LIGHT, lw=.6, ls='-.', zorder=0.5)
        ax.text(0, 263, 'swing axis', fontsize=6.3, color=GREY, ha='center', va='bottom')


def right_view(ax, sc, labels=True):
    """From the machine's right (-Y): front to the right."""
    context(ax, sc, 'xz')
    ho = dict(fc=BODY_L, ec=BODY, lw=.9, z=5)
    cab = xz([side_mm(p) for p in SIDE_PX['cab']])
    patch(ax, cab, fc='#f4f4f4', ec=GREY, lw=.6, z=3.5)                               # far side, behind
    patch(ax, [(x, z) for x, z in xz([side_mm(p) for p in SIDE_PX['exhaust']])], fc='#7f8c8d', ec=INK, lw=.5, z=3.6)
    tank = [(CAT['tank_x'][0], Z_DECK), (CAT['tank_x'][0], B['tank_top']), (CAT['tank_x'][1], B['tank_top']),
            (CAT['tank_x'][1], B['tank_step']), (CAT['tank_x'][2], B['tank_step']), (CAT['tank_x'][2], Z_DECK)]
    patch(ax, tank, fc='#fbeee2', ec=BODY, lw=.8, z=4.5)
    patch(ax, cw_side(), **ho)
    box(ax, CWF, Z_BOT, B['right_front'], Z_DECK, **ho)
    box(ax, CWF, Z_DECK, CAT['door_seam_right'], B['hood_top'], **ho)
    fd = xz(CAT['front_door'])
    patch(ax, [(CAT['door_seam_right'], Z_DECK)] + fd + [(fd[-1][0], Z_DECK)], **ho)
    tb = [(CAT['toolbox_x'][0], Z_DECK), (CAT['toolbox_x'][0], B['toolbox_top'] - 3), (CAT['toolbox_x'][0] + 3, B['toolbox_top']),
          (CAT['toolbox_x'][1] - 3, B['toolbox_top']), (CAT['toolbox_x'][1], B['toolbox_top'] - 3), (CAT['toolbox_x'][1], Z_DECK)]
    patch(ax, tb, **ho)
    for x0, x1, y0, y1 in PHOTO_PX['treads']:
        (a, za), (b, zb) = photo_mm((x0, y0)), photo_mm((x1, y1))
        box(ax, a, zmap(za), b, zmap(zb), fc=BODY_D, ec=BODY, lw=.4, z=5.3)
    r = xz([photo_mm(p) for p in PHOTO_PX['rail']])
    line(ax, r, color=INK, lw=1.1, z=5.5)
    line(ax, [(CWF, Z_BOT), (CWF, B['hood_top'])], color=BODY, lw=.7, z=5.6)
    if labels:
        ax.plot([0, 0], [-5, 262], color=LIGHT, lw=.6, ls='-.', zorder=0.5)
        dim_v(ax, CAT['toolbox_x'][1] + 8, Z_DECK, B['toolbox_top'], f"{B['toolbox_top'] - Z_DECK:.0f}", side=1)
        dim_h(ax, CAT['tank_x'][0], CAT['tank_x'][2], B['tank_top'] + 5, f"tank {CAT['tank_x'][2] - CAT['tank_x'][0]:.0f}", side=1)
        dim_h(ax, CAT['toolbox_x'][0], CAT['toolbox_x'][1], Z_BOT - 9, f"{CAT['toolbox_x'][1] - CAT['toolbox_x'][0]:.0f}", side=-1)
        dim_v(ax, -TAIL - 10, Z_BOT, Z_DECK, f'{Z_DECK - Z_BOT:.0f}', side=-1)
        dim_v(ax, -TAIL - 10, Z_DECK, B['hood_top'], f"{B['hood_top'] - Z_DECK:.0f}", side=-1)


def plan_body(ax, sc, lids=True, arm=True, labels=False):
    context(ax, sc, 'xy', arm=arm)
    ho = dict(fc=BODY_L, ec=BODY, lw=.9, z=5)
    patch(ax, PLAN['cw'], **ho)
    patch(ax, PLAN['left_module'], **ho)
    patch(ax, PLAN['right_module'], **ho)
    if lids:
        patch(ax, PLAN['lid_left'], fc='#fbe2cc', ec=BODY, lw=.8, z=5.5)
        patch(ax, PLAN['lid_right'], fc='#fbe2cc', ec=BODY, lw=.8, z=5.5)
        for x in (CAT['slope'][0], CAT['slope'][1]):
            line(ax, [(x, B['tank_y'][0] + 2), (x, W - 2.5)], color=BODY, lw=.45, z=5.6)
        line(ax, [(CWF, 0), (ARM_X[0] - 2, 0)], color=BODY, lw=.45, ls=(0, (4, 2)), z=5.6)
        ax.add_patch(Circle(EXHAUST[0], EXHAUST[1], fc='#7f8c8d', ec=INK, lw=.5, zorder=6))
    patch(ax, PLAN['cab'], fc='#fbeee2', ec=BODY, lw=.9, z=5.7)
    patch(ax, PLAN['tank'], fc='#fbeee2', ec=BODY, lw=.8, z=5.7)
    patch(ax, PLAN['toolbox'], fc='#fbeee2', ec=BODY, lw=.8, z=5.7)
    patch(ax, PLAN['steps'], fc=BODY_D, ec=BODY, lw=.5, z=5.6)
    line(ax, [(CAT['rail_x'][0], RAIL_Y[0]), (CAT['rail_x'][0], RAIL_Y[1])], color=INK, lw=1.0, z=6)
    line(ax, [(CAT['rail_x'][1], RAIL_Y[0]), (CAT['rail_x'][1], RAIL_Y[1])], color=INK, lw=1.0, z=6)


def rear_view(ax, sc):
    """From behind: the machine's left (cab) on the viewer's left, so the plot's x is -Y."""
    S = sc['sil']
    def flip(g):
        return affinity.scale(g, -1, 1, origin=(0, 0))
    shape(ax, flip(S[('belt', 'yz')]), TRK_L, TRK, lw=.5, z=1)
    shape(ax, flip(S[('tracks', 'yz')]), '#eceff0', TRK, lw=.4, z=1.2)
    shape(ax, flip(S[('chassis', 'yz')]), '#f6efcf', '#b7950b', lw=.4, z=1.1)
    shape(ax, flip(S[('arm', 'yz')]), ARM_L, ARMC, lw=.45, z=1.4)
    shape(ax, flip(S[('arm_base', 'yz')]), ARM_L, ARMC, lw=.6, z=1.5, ls='--')
    ho = dict(fc=BODY_L, ec=BODY, lw=.9, z=5)
    patch(ax, [(-y, z) for y, z in rrect(-W, Z_BOT, W, B['hood_top'], 4.5)], **ho)
    cab = [(B['cab_y'][0], B['hood_top']), (B['cab_y'][0], B['cab_top'] - 4), (B['cab_y'][0] + 4, B['cab_top']), (W - 4, B['cab_top']),
           (W, B['cab_top'] - 4), (W, B['hood_top'])]
    patch(ax, [(-y, z) for y, z in cab], fc='#fbeee2', ec=BODY, lw=.9, z=4.8)
    g = [(ymap(rear_mm(p)[0]), zmap(rear_mm(p)[1])) for p in REAR_PX['glass']]
    patch(ax, [(-y, z) for y, z in g], fc=GLASS, ec=BODY, lw=.5, z=4.9)
    ex = [(ymap(rear_mm(p)[0]), zmap(rear_mm(p)[1])) for p in REAR_PX['exhaust']]
    patch(ax, [(-y, z) for y, z in ex], fc='#7f8c8d', ec=INK, lw=.5, z=4.7)
    rl = [(ymap(rear_mm(p)[0]), zmap(rear_mm(p)[1])) for p in REAR_PX['rail']]
    line(ax, [(-y, z) for y, z in rl], color=INK, lw=1.0, z=4.7)
    for x0, x1, y0, y1 in REAR_PX['lamps']:
        (a, za), (b, zb) = rear_mm((x0, y0)), rear_mm((x1, y1))
        box(ax, -ymap(a), zmap(za), -ymap(b), zmap(zb), fc='#e74c3c', ec='#922b21', lw=.4, z=5.5)


# ------------------------------------------------------------------ sheet 1: the reference
def crop(path, box_):
    im = Image.open(path).convert('RGB')
    return np.asarray(im.crop(box_)), box_


def show_img(ax, path, box_):
    a, (x0, y0, x1, y1) = crop(path, box_)
    ax.imshow(a, extent=(x0, x1, y1, y0), interpolation='lanczos', zorder=0)
    ax.set_xlim(x0, x1); ax.set_ylim(y1, y0); ax.set_aspect('equal'); ax.axis('off')


def trace_poly(ax, pts, lw=1.1, closed=True, color=TRACE, ls='-'):
    p = list(pts) + ([pts[0]] if closed else [])
    line(ax, p, color=color, lw=lw, z=10, ls=ls)


def sheet1(pdf, est, chk):
    fig = plt.figure(figsize=FIG)
    header(fig, 1, 'the real machine, traced', 'Cat 320 (Caterpillar spec sheet page 4 drawing; Caterpillar product render). '
           'Magenta = traced outline. All numbers in mm at 1:15 unless marked "full size". Sources: '
           'excavator_arm_60mm/references/SOURCES.md.')
    # A: drawing, side view
    ax = fig.add_axes([.012, .50, .45, .415])
    show_img(ax, REF / 'cat320_spec_page_4.png', (578, 228, 870, 402))
    title(ax, 'A  Spec drawing, left side (orthographic): 19.1 mm/px')
    for n in ('band', 'cab', 'hood', 'glass1', 'glass2', 'exhaust'):
        trace_poly(ax, SIDE_PX[n], lw=1.2 if n in ('band', 'cab', 'hood') else .7)
    for s in SIDE_PX['seams']:
        trace_poly(ax, s, lw=.7, closed=False)
    for x0, x1, y0, y1 in SIDE_PX['louvres']:
        trace_poly(ax, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], lw=.5)
    ax.plot([AXIS_X]*2, [232, 400], color='#0b6fd6', lw=.7, ls='-.', zorder=11)
    ax.plot([580, 868], [GROUND_Y]*2, color='#0b6fd6', lw=.7, ls='-.', zorder=11)
    ax.text(AXIS_X + 1.5, 233, 'swing axis', fontsize=6.4, color='#0b6fd6', va='top')
    ax.text(582, GROUND_Y - 1, 'ground', fontsize=6.4, color='#0b6fd6', va='bottom')
    c = CAT
    k = dict(fs=6.6, color=TRACE, boxed=True)
    note(ax, (680, 240), (582, 234), f"cab top {c['cab_top']:.1f}  (spec 2960 → {SPEC['cab_top']/S15:.1f})", relpos=(1, .5), **k)
    note(ax, (775, 265.8), (752, 257), f"hood top {c['hood_top']:.1f}", ha='right', relpos=(1, .5), **k)
    note(ax, (760, 331), (745, 356), f"deck {c['deck']:.1f}", ha='right', relpos=(1, .5), **k)
    note(ax, (840, 340), (866, 362), f"upper-frame bottom {c['bottom']:.1f}\n(spec 1050 → {SPEC['counterweight_clearance']/S15:.1f})",
         ha='right', relpos=(1, .5), **k)
    note(ax, (848.5, 290), (867, 237), f"rear end {c['rear_end']:.1f}\n(tail swing 2830 → {c['tail']:.1f})", ha='right', relpos=(1, .5), **k)
    note(ax, (729.5, 262), (752, 320), f"cab rear X {c['cab_x'][0]:.1f}", relpos=(0, .5), **k)
    note(ax, (632, 331), (586, 318), f"cab front X {c['cab_x'][1]:.1f}", relpos=(0, .5), **k)
    note(ax, (820.8, 300), (830, 322), f"seam X {c['cw_seam_left']:.1f}", ha='center', relpos=(.5, 1), **k)
    note(ax, (800, 283), (780, 307), 'louvres', ha='center', relpos=(.5, 1), **k)
    note(ax, (700, 394), (640, 384), f"track {c['track_length']:.1f} (spec 4450 → {SPEC['track_length']/S15:.1f})",
         ha='right', relpos=(1, .5), **k)
    # B: drawing, rear view
    ax = fig.add_axes([.47, .50, .175, .415])
    show_img(ax, REF / 'cat320_spec_page_4.png', (100, 228, 286, 402))
    title(ax, 'B  Spec drawing, rear')
    x0, y0, x1, y1, r = REAR_PX['cw']
    trace_poly(ax, rrect(x0, y0, x1, y1, r), lw=1.2)
    for n in ('cab', 'glass', 'rail', 'exhaust'):
        trace_poly(ax, REAR_PX[n], lw=1.1 if n == 'cab' else .7, closed=n != 'rail')
    for x0, x1, y0, y1 in REAR_PX['lamps']:
        trace_poly(ax, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], lw=.5)
    ax.plot([REAR_CL]*2, [232, 400], color='#0b6fd6', lw=.7, ls='-.', zorder=11)
    note(ax, (121, 320), (104, 362), f"width {2*c['half_width']:.1f}\n(spec 2780 → {2*c['spec_half_width']:.1f})", relpos=(0, .5), **k)
    note(ax, (150, 241), (104, 236), f"cab {c['cab_y'][1] - c['cab_y'][0]:.1f} wide, inner side\n{c['cab_y'][0]:.1f} left of centre",
         relpos=(0, .5), **k)
    note(ax, (250, 241.7), (283, 233), f"handrail {c['rail_top_rear']:.1f}", ha='right', relpos=(1, .5), **k)
    # C: render, right side
    ax = fig.add_axes([.655, .50, .34, .415])
    show_img(ax, REF / 'cat320_view_018.jpg', (95, 540, 705, 890))
    title(ax, 'C  Render, right side (perspective): 5.97 mm/px on the near side')
    for n in ('cw', 'door', 'front_door', 'tank', 'toolbox', 'band', 'exhaust'):
        trace_poly(ax, PHOTO_PX[n], lw=1.1 if n in ('cw', 'door', 'front_door', 'toolbox', 'band') else .8,
                   ls='--' if n == 'tank' else '-')
    trace_poly(ax, PHOTO_PX['rail'], lw=.8, closed=False)
    for x0, x1, y0, y1 in PHOTO_PX['treads']:
        trace_poly(ax, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], lw=.6)
    ax.plot([PH['axis']]*2, [545, 885], color='#0b6fd6', lw=.7, ls='-.', zorder=11)
    note(ax, (116, 760), (100, 556), f"counterweight side end X {c['cw_side_end']:.1f}\n(plan from the spec: "
         f"{c['cw_corner_x']:.1f})", relpos=(0, .5), **k)
    note(ax, (240, 640), (180, 596), f"hood top {c['hood_top']:.1f} (set from A)", relpos=(0, .5), **k)
    note(ax, (400, 567), (430, 556), f"handrail top {c['rail_top']:.1f}\n(spec 2950 → {SPEC['handrail']/S15:.1f})", relpos=(0, .5), **k)
    note(ax, (440, 655), (560, 612), f"tank, inboard:\nX {c['tank_x'][0]:.1f} to {c['tank_x'][2]:.1f}\ntop {c['tank_top']:.1f}",
         relpos=(0, .5), **k)
    note(ax, (640, 772), (585, 715), f"toolbox X {c['toolbox_x'][0]:.1f}\nto {c['toolbox_x'][1]:.1f}, top {c['toolbox_top']:.1f}",
         relpos=(0, .5), **k)
    note(ax, (340, 800), (250, 858), f"door seam X {c['door_seam_right']:.1f}", ha='right', relpos=(1, .5), **k)
    # D: the mapping, Cat plan at 1:15 next to X1, one scale
    hw = c['spec_half_width']
    a0 = math.atan2(hw, c['cw_corner_x'])
    arc = [(TAIL*math.cos(t), TAIL*math.sin(t)) for t in np.linspace(a0, 2*math.pi - a0, 40)]
    cat_outline = [(c['cab_x'][1], hw)] + arc + [(c['toolbox_x'][1], -hw), (c['toolbox_x'][1], c['tank_inner_y']),
                                                 (c['cab_x'][1], c['tank_inner_y'])]
    fig.text(.012, .445, 'D  Plan: the Cat at 1:15, and X1 B1 widened in the middle', fontsize=10.2, weight='bold', color=INK)
    fig.text(.012, .428, f"Same scale. Lengths and every part's own width kept; {DY:.1f} inserted each side of the\n"
             f"centreline (hatched) because the ARM60 base is {2*ARM_Y:.0f} wide.", fontsize=7.2, color=GREY, va='top')
    for i, (lab, x1) in enumerate((('Cat 320 at 1:15 (from A-C)', False), ('X1 B1', True))):
        ax = fig.add_axes([.012 + i*.185, .04, .18, .375])
        ax.text(-195, 172, lab, fontsize=8, weight='bold', color=BODY if x1 else GREY)
        if x1:
            for n in ('cw', 'left_module', 'right_module', 'lid_left', 'lid_right'):
                patch(ax, PLAN[n], fc=BODY_L, ec=BODY, lw=.7, z=2)
            for n in ('cab', 'tank', 'toolbox'):
                patch(ax, PLAN[n], fc='#fbe2cc', ec=BODY, lw=.7, z=2.2)
            box(ax, -TAIL, -DY, ARM_X[0], DY, fc='none', ec=BODY, lw=0, hatch='////', z=2.5, alpha=.6)
            box(ax, ARM_X[0], -ARM_Y, ARM_X[1], ARM_Y, fc=ARM_L, ec=ARMC, lw=.7, ls='--', z=2.1)
            ax.text(45, 0, f'ARM60\nbase\n{2*ARM_Y:.0f}', fontsize=6.2, color=ARMC, ha='center', va='center', zorder=3)
            ax.text(28, 120, 'cab', fontsize=6.3, color=BODY, ha='center', zorder=4)
            ax.text(-38, -122, 'tank', fontsize=6.0, color=BODY, ha='center', zorder=4, rotation=90)
            ax.text(38, -122, 'tool-\nbox', fontsize=6.0, color=BODY, ha='center', va='center', zorder=4)
            for sgn in (1, -1):
                ax.annotate('', (-100, sgn*W), (-100, sgn*hw), arrowprops=dict(arrowstyle='->', lw=.8, color=BODY), zorder=6)
            ax.text(-104, 122, f'+{DY:.1f}', fontsize=6.6, color=BODY, ha='right', va='center', zorder=6)
            ax.text(-104, -122, f'−{DY:.1f}', fontsize=6.6, color=BODY, ha='right', va='center', zorder=6)
            dim_v(ax, 118, -W, W, f'{2*W:.0f}', side=1, fs=6.4)
        else:
            patch(ax, cat_outline, fc='#e5e8e8', ec=GREY, lw=.8, z=2)
            for poly in ([(c['cab_x'][0], c['cab_y'][0]), (c['cab_x'][1], c['cab_y'][0]), (c['cab_x'][1], hw), (c['cab_x'][0], hw)],
                         [(c['tank_x'][0], c['tank_inner_y']), (c['tank_x'][2], c['tank_inner_y']), (c['tank_x'][2], -hw), (c['tank_x'][0], -hw)],
                         [(c['toolbox_x'][0], c['tank_inner_y']), (c['toolbox_x'][1], c['tank_inner_y']), (c['toolbox_x'][1], -hw),
                          (c['toolbox_x'][0], -hw)]):
                patch(ax, poly, fc='#d5dbdb', ec=GREY, lw=.7, z=2.2)
            line(ax, [(CWF, -hw), (CWF, hw)], color=GREY, lw=.5, z=2.3)
            ax.text(28, 58, 'cab', fontsize=6.3, color=GREY, ha='center', zorder=4)
            ax.text(-38, -62, 'tank', fontsize=6.0, color=GREY, ha='center', zorder=4, rotation=90)
            ax.text(38, -62, 'tool-\nbox', fontsize=6.0, color=GREY, ha='center', va='center', zorder=4)
            ax.text(20, 0, 'boom\nfoot', fontsize=6.0, color=GREY, ha='center', va='center', zorder=4)
            ax.text(-160, 0, 'counter-\nweight', fontsize=6.0, color=GREY, ha='center', va='center', zorder=4)
            dim_v(ax, 105, -hw, hw, f'{2*hw:.1f}', side=1, fs=6.4)
        ax.add_patch(Circle((0, 0), TAIL, fc='none', ec=GREY, lw=.5, ls=':', zorder=1))
        ax.plot([-200, 130], [0, 0], color=LIGHT, lw=.5, ls='-.', zorder=0.5)
        ax.annotate('front', (128, -170), (95, -170), fontsize=6.3, color=GREY, va='center',
                    arrowprops=dict(arrowstyle='->', lw=.6, color=GREY))
        ax.set_xlim(-200, 140); ax.set_ylim(-178, 178); ax.set_aspect('equal'); ax.axis('off')
    # E: the trace checks
    rows = [('Check on the trace', 'traced', 'Caterpillar', 'error')]
    for r in chk['trace']:
        rows.append((r['what'], f"{r['traced']:.1f}", f"{r['spec']:.1f}", f"{100*r['error']:+.1f} %"))
    y = table(fig, .39, .425, [.17, .045, .055, .04], rows, fs=7.2)
    fig.text(.39, .445, 'E  Scales checked against Caterpillar\'s own numbers', fontsize=10.2, weight='bold', color=INK)
    text_blocks(fig, .39, y - .01, [
        ('How the trace was taken', [
            ('•', 'Drawing (A, B): orthographic, one scale, 19.1 mm/px from the tail swing radius (dimension 4).\n'
                  'Heights from the drawing\'s ground line. Read to ±1 px = ±1.3 mm at 1:15.'),
            ('•', 'Render (C): perspective. Lengths on the near side from the near track (4450 mm = 745 px);\n'
                  'heights set by two points from A. Used only for the right-side features that A cannot show.'),
            ('•', f"Not shown by either: the inner edge of the tank and toolbox ({c['tank_inner_y']:.0f}, estimated from the\n"
                  'front render cat320_view_009.jpg, ±5). It only sets the gap to the ARM60 base (sheet 2).')])], fs=7.4, lh=.0118)
    text_blocks(fig, .71, .425, [
        ('Cat → X1, the three rules', [
            ('1', 'Lengths (X) at 1:15 as traced. X1 already is 1:15 in length: track 4450 → 296.7,\n'
                  'the ARM60 reach, the T101 rear face at the counterweight seam (−145).'),
            ('2', f"Heights over the deck at 1:15, on the T101 rib tops (Z {Z_DECK:.0f}, the ARM60 seat):\n"
                  f"hood {B['hood_top']:.0f}, cab roof {B['cab_top']:.0f}. Below the deck the Cat's 11.5 band\n"
                  f"stretches to {Z_DECK - Z_BOT:.0f} to cover T101, down to Z {Z_BOT:.0f} (swing envelope Z {X.TURNTABLE_Z:.0f})."),
            ('3', f"Width: the Cat's {2*c['spec_half_width']:.1f} grows to {2*W:.0f}. The ARM60 base is {2*ARM_Y:.0f} wide where\n"
                  f"the Cat's boom foot sits, so {DY:.1f} is inserted each side of the centreline\n"
                  'and every part keeps its own Cat width: cab, tank, toolbox, and the\n'
                  'counterweight\'s rounded ends.')])],
        fs=7.4, lh=.0118)
    pdf.savefig(fig); fig.savefig(PNG[0], dpi=110); plt.close(fig)


# ------------------------------------------------------------------ sheet 2: the X1 shell
def sheet2(pdf, sc, est, chk):
    fig = plt.figure(figsize=FIG)
    header(fig, 2, 'the X1 shell, traced from the Cat 320', 'Orange = new body prints (B101-B109). Grey = X1 tracks and chassis, '
           'purple = ARM60 (dashed: its base), all from the CAD as exported, arm stretched. Side views at one scale, plan and rear at another.')
    S, S2 = 51.0, 92.0
    ax = fig.add_axes([.005, .49, .495, .425])
    left_view(ax, sc)
    fit(ax, -30, 133, S, flip_x=True)
    title(ax, 'LEFT SIDE (cab side, front to the left, as Caterpillar draws it)')
    k = dict(fs=6.6)
    note(ax, (-110, 190), (-150, 245), 'louvres: the Cat\'s cooling side.\nHere: vents for the driver board', color=BODY, relpos=(0, .5), **k)
    note(ax, (-160, 150), (-215, 175), 'B101 counterweight\n(steel shot inside)', color=BODY, ha='right', relpos=(1, .5), **k)
    note(ax, (40, 230), (120, 255), 'B106 cab', color=BODY, ha='right', relpos=(1, .5), **k)
    note(ax, (60, 120), (175, 115), f'B102 side module: skirt\nZ {Z_BOT:.0f}–{Z_DECK:.0f} over the T101 sides', color=BODY,
         relpos=(0, .5), **k)
    note(ax, (-100, B['hood_top']), (-90, 262), 'B104 hood lid', color=BODY, relpos=(0, .5), **k)
    ax = fig.add_axes([.50, .49, .495, .425])
    right_view(ax, sc)
    fit(ax, -30, 133, S)
    title(ax, 'RIGHT SIDE (front to the right)')
    note(ax, (-110, 180), (-160, 245), 'B103 side module: engine door\n(battery behind it)', color=BODY, relpos=(0, .5), **k)
    note(ax, (-40, 214), (-10, 262), 'B107 tank block', color=BODY, relpos=(0, .5), **k)
    note(ax, (38, 160), (70, 200), 'B108 toolbox: switch,\nfuse, charge jack', color=BODY, relpos=(0, .5), **k)
    note(ax, (-6, 160), (25, 225), 'steps and handrail', color=INK, relpos=(0, .5), **k)
    # plan
    ax = fig.add_axes([.005, .035, .37, .425])
    plan_body(ax, sc)
    fit(ax, -40, 0, S2)
    title(ax, 'PLAN (front to the right)')
    dim_v(ax, B['left_front'] + 14, -W, W, f'{2*W:.0f}', side=1)
    dim_h(ax, -TAIL, B['left_front'], W + 14, f"{TAIL + B['left_front']:.0f}", side=1)
    ax.add_patch(Circle((0, 0), X.RESERVE_R, fc='none', ec=GREY, lw=.5, ls=':', zorder=7))
    rc = math.hypot(CAT['cw_corner_x'], W)
    ax.add_patch(Circle((0, 0), rc, fc='none', ec=BODY, lw=.5, ls=':', zorder=7))
    ax.text(-rc*.68, -rc*.73, f'R {rc:.0f}: corners', fontsize=6.3, color=BODY, rotation=43, ha='center', zorder=8)
    ax.text(-X.RESERVE_R*.62, -X.RESERVE_R*.6, f'R {X.RESERVE_R:.0f} reserve', fontsize=6.3, color=GREY, rotation=43,
            ha='center', zorder=8)
    note(ax, (-120, 40), (-150, 205), 'B104 / B105 hood lids,\nsplit on the centreline', color=BODY, relpos=(0, .5), fs=6.5)
    note(ax, (20, 130), (40, 205), 'B106 cab', color=BODY, relpos=(0, .5), fs=6.5)
    note(ax, (-40, -120), (-50, -205), 'B107 tank', color=BODY, relpos=(0, .5), fs=6.5)
    note(ax, (40, -120), (45, -205), 'B108 toolbox', color=BODY, relpos=(0, .5), fs=6.5)
    # rear
    ax = fig.add_axes([.375, .035, .29, .425])
    rear_view(ax, sc)
    fit(ax, 0, 118, S2)
    title(ax, 'REAR (cab on the left)')
    dim_h(ax, -W, W, Z_BOT - 10, f'{2*W:.0f}', side=-1)
    dim_v(ax, -W - 14, Z_BOT, B['hood_top'], f"{B['hood_top'] - Z_BOT:.0f}", side=-1)
    dim_v(ax, W + 14, 0, Z_BOT, f'{Z_BOT:.0f}', side=1)
    dim_v(ax, W + 28, 0, sc['track_top'], f"{sc['track_top']:.1f} track top", side=1)
    # comparison table
    c = CAT
    rows = [('', 'Cat 320\n(full size)', 'Cat at\n1:15', 'X1 B1', 'why X1 differs'),
            ('upper-frame width', '2780', f"{2*c['spec_half_width']:.1f}", f'{2*W:.0f}', 'ARM60 base 164 wide;\nsheet 1, D'),
            ('tail radius (centre)', '2830', f"{c['tail']:.1f}", f'{TAIL:.1f}', '—'),
            ('tail radius (corners)', '—', f"{c['tail']:.1f}", f'{rc:.0f}', 'widening; decision D4'),
            ('frame bottom', '1050', f"{c['bottom']:.1f}", f'{Z_BOT:.0f}', f"X1 tracks {sc['track_top']:.1f} high"),
            ('deck (frame top)', 'traced', f"{c['deck']:.1f}", f'{Z_DECK:.0f}', 'T101 rib tops'),
            ('frame band depth', 'traced', f"{c['deck'] - c['bottom']:.1f}", f'{Z_DECK - Z_BOT:.0f}', 'covers T101; D5'),
            ('hood over the deck', 'traced', f"{c['hood_top'] - c['deck']:.1f}", f"{B['hood_top'] - Z_DECK:.1f}", '—'),
            ('cab roof over deck', '2960 roof', f"{c['cab_top'] - c['deck']:.1f}", f"{B['cab_top'] - Z_DECK:.1f}", '—'),
            ('cab length × width', 'traced', f"{c['cab_x'][1] - c['cab_x'][0]:.1f} × {c['cab_y'][1] - c['cab_y'][0]:.1f}",
             f"{B['cab_x'][1] - B['cab_x'][0]:.1f} × {W - B['cab_y'][0]:.1f}", 'outer side flush'),
            ('counterweight depth', 'traced', f"{c['tail'] + CWF:.1f}", f'{TAIL + CWF:.1f}', '—'),
            ('hood, cw seam to slope', 'traced', f"{c['slope'][0] - CWF:.1f}", f"{CAT['slope'][0] - CWF:.1f}", '—'),
            ('toolbox L × H', 'traced', f"{c['toolbox_x'][1] - c['toolbox_x'][0]:.1f} × {c['toolbox_top'] - c['deck']:.1f}",
             f"{c['toolbox_x'][1] - c['toolbox_x'][0]:.1f} × {B['toolbox_top'] - Z_DECK:.1f}", '—'),
            ('track length', '4450', f"{SPEC['track_length']/S15:.1f}", f"{sc['track_length']:.1f}", 'J9 (existing)'),
            ('track gauge', '2380', f"{SPEC['track_gauge']/S15:.1f}", f"{2*sc['track_y']:.0f}", 'X1 (existing)')]
    fig.text(.675, .445, 'Cat 320 against X1 B1', fontsize=10.2, weight='bold', color=INK)
    y = table(fig, .675, .425, [.088, .052, .056, .053, .075], rows, fs=6.9, lh=.0116)
    fig.text(.675, y - .006, 'Track figures: X1 rolling gear, unchanged. Its gauge is 2.1 × the Cat\'s at 1:15, so the\n'
             'upper is narrower than the tracks, as on the Cat.', fontsize=6.8, color=GREY, va='top', linespacing=1.3)
    pdf.savefig(fig); fig.savefig(PNG[1], dpi=110); plt.close(fig)


# ------------------------------------------------------------------ sheet 3: inside
def item_plan(ax, n, lw=.8, z=8, text=None, fs=6.3):
    e = ITEMS[n]['env']; ec, fc = ELEC[ITEMS[n]['color']]
    box(ax, e[0], e[2], e[1], e[3], fc=fc, ec=ec, lw=lw, z=z)
    if text:
        ax.text((e[0] + e[1])/2, (e[2] + e[3])/2, text, fontsize=fs, color=ec, ha='center', va='center', zorder=z + .1)


def item_side(ax, n, sign=1, lw=.8, z=8, text=None, fs=6.0):
    e = ITEMS[n]['env']; ec, fc = ELEC[ITEMS[n]['color']]
    box(ax, e[0], e[4], e[1], e[5], fc=fc, ec=ec, lw=lw, z=z)
    if text:
        ax.text((e[0] + e[1])/2, (e[4] + e[5])/2, text, fontsize=fs, color=ec, ha='center', va='center', zorder=z + .1)


def routes():
    """Cable routes in plan (x, y) and their heights; one list of points per cable."""
    ly = (ITEMS['carrier']['env'][2] + 8)
    return {
        'power': [(-110.0, -110.0), (-60.0, -118.0), (24.0, -118.0), (20.0, -100.0), (-26.0, -86.0), (-26.0, 72.0),
                  (-38.0, 82.0), (-46.0, ly)],
        'charge': [(40.0, -141.0), (0.0, -144.0), (-80.0, -144.0), (-100.0, -140.0)],
        'track': [(-8.0, 0.0), (-40.0, 0.0), (-41.0, 40.0), (-44.0, 66.0), (-54.0, ly)],
        'swing': [(-137.3, 0.0), (-150.0, 0.0), (-152.0, 6.0), (-140.0, 14.0), (-140.0, 60.0), (-128.0, ly)],
        'arm': [(-21.0, 30.0), (-23.5, 30.0), (-23.5, 70.0), (-37.0, 79.0), (-42.0, ly + 8)]}


def sheet3(pdf, sc, est, chk):
    fig = plt.figure(figsize=FIG)
    header(fig, 3, 'inside the shell', 'Battery low at the rear right, the controller board on the left (the Cat\'s cooling side, '
           'behind the louvres), switch and charge jack in the toolbox, steel shot in the counterweight. The T101 service area '
           'stays clear.')
    S = 54.0
    # plan, lids off
    ax = fig.add_axes([.005, .385, .56, .535])
    context(ax, sc, 'xy', arm=False)
    R3.draw_shape(ax, R3.frame_base(), fc='#e8f1f8', ec=UP, lw=.5, z=2)
    R3.draw_shape(ax, R3.frame_walls(), fc='#a9cce3', ec=UP, lw=.5, z=3, hole_fc='#e8f1f8')
    sz = Polygon([(R3.REAR_BULK[1], -R3.RIB_Y[0]), (-R3.HUB_BULK[1], -R3.RIB_Y[0]), (-R3.HUB_BULK[1], R3.RIB_Y[0]),
                  (R3.REAR_BULK[1], R3.RIB_Y[0])])
    shape(ax, sz, 'none', '#b03a2e', lw=.8, z=6.5, ls='--', hatch='////')
    for x, y in R3.SLIDE['slots']:
        for s in (1, -1):
            ax.add_patch(Circle((x, s*y), 2.6, fc='#f7dc6f', ec='#9a7d0a', lw=.5, zorder=7))
    for x, y in R3.PAD_XY:
        ax.add_patch(Circle((x, y), 3.0, fc='#f7dc6f', ec='#9a7d0a', lw=.5, zorder=7))
    for s in (1, -1):
        ax.add_patch(Circle((R3.LUG['x'][0] - 3, s*30), 2.4, fc='#f7dc6f', ec='#9a7d0a', lw=.5, zorder=7))
    ho = dict(fc='none', ec=BODY, lw=.9, z=5)
    pocket = est['pocket']
    patch(ax, PLAN['cw'], fc=BODY_L, ec=BODY, lw=.9, z=4)
    shape(ax, pocket, STEEL_L, STEEL, lw=.5, z=4.5, hatch='....')
    box(ax, CWF - 20, -12, CWF, 12, fc='white', ec=BODY, lw=.6, z=4.6)
    for s in (1, -1):
        box(ax, CWF - 12, s*40 - 6, CWF, s*40 + 6, fc=BODY_D, ec=BODY, lw=.5, z=4.6)
        ax.add_patch(Circle((CWF - 4, s*40), 2.2, fc='white', ec=INK, lw=.5, zorder=4.7))
    for n in ('left_module', 'right_module'):
        patch(ax, PLAN[n], fc='#fff7ef', ec=BODY, lw=.9, z=3.5)
    for n in ('cab', 'tank', 'toolbox'):
        patch(ax, PLAN[n], **ho)
    for n, t in (('battery', 'BATTERY\n3S1P 18650\n+ BMS'), ('carrier', 'CONTROLLER BOARD\nESP32 · 3 × DRV8871 · 2 × DRV8833\n6 V and 5 V bucks')):
        item_plan(ax, n, text=t, fs=6.3)
    for n in ('switch', 'fuse', 'jack'):
        item_plan(ax, n, lw=.6)
    # T101 change: inserts for the side modules
    for x in (-120.0, -60.0, 40.0):
        for s in (1, -1):
            box(ax, x - 4, s*R3.RIB_Y[1], x + 4, s*B['inner'], fc='#fdebd0', ec=BODY, lw=.5, z=6)
    rt = routes()
    for n, pts in rt.items():
        line(ax, pts, color=WIRE[n], lw=1.6, z=9, ls='--' if n == 'charge' else '-')
    fit(ax, -62, 0, 58.0)
    title(ax, 'PLAN, hood lids and cab roof off (front to the right)')
    k = dict(fs=6.5)
    xl, xr = -326.0, 118.0
    note(ax, (-90, -40), (xl, -128), 'T101 service area, keep clear:\nslide clamps, push screws and\ndrag-pad set screws are keyed\n'
         'from above (R3). Nothing is fixed\nover it; cables cross at the ends.', color='#b03a2e', relpos=(1, .5), **k)
    note(ax, (-160, 0), (xl, 30), f"lead channel from the Ø{2*R3.WINDOW_R:.0f}\nwindow (swing motor)", color=WIRE['swing'],
         relpos=(1, .5), **k)
    note(ax, (-178, -45), (xl, -40), f"steel shot {est['shot_kg']:.2f} kg,\nfill to Z {est['fill_z']:.0f}", color=STEEL,
         relpos=(1, .5), **k)
    note(ax, (CWF - 6, 40), (xl, 92), '2 × M4 into captive nuts,\nexisting T101 holes', color=BODY, relpos=(1, .5), **k)
    note(ax, (40, 72), (xr, 62), '3 × M3 per side into new\ninserts in the T101 rib\nouter faces (T101 change)', color=BODY,
         relpos=(0, .5), **k)
    note(ax, (45, -112), (xr, -112), 'toolbox: switch, fuse,\ncharge jack', color=ELEC['power'][0], relpos=(0, .5), **k)
    note(ax, (-20, -140), (xr, -150), 'tank: spare', color=BODY, relpos=(0, .5), **k)
    note(ax, (60, 120), (xr, 125), 'cab: empty\n(lights later)', color=BODY, relpos=(0, .5), **k)
    note(ax, (-26, -40), (xr, -40), 'cross-over at X −26: 12 V\nfeed and arm leads, over\nthe rib tops at Z 137–145',
         color=WIRE['power'], relpos=(0, .5), **k)
    # legend of the routes
    lx, ly0 = .012, .905
    for i, (n, t) in enumerate((('power', '12 V: battery → fuse → switch → board'), ('charge', 'charge: jack → BMS'),
                                ('track', 'track motors: slip ring → T101 lead slot'), ('swing', 'swing motor: Ø20 window → channel'),
                                ('arm', 'ARM60: 8 leads down the base rear face'))):
        y = ly0 - i*.015
        fig.add_artist(Line2D([lx, lx + .02], [y, y], lw=1.8, color=WIRE[n], ls='--' if n == 'charge' else '-',
                              transform=fig.transFigure))
        fig.text(lx + .024, y, t, fontsize=6.8, va='center', color=INK)
    # A-A: left bay, Y +113, seen from the left
    ya, yb = 113.0, -113.0
    ax = fig.add_axes([.57, .655, .425, .265])
    section_side(ax, sc, est, ya)
    fit(ax, -40, 165, 62.0, flip_x=True)
    title(ax, f'A–A  through the left bay, Y +{ya:.0f}, seen from the left')
    ax = fig.add_axes([.57, .385, .425, .265])
    section_side(ax, sc, est, yb)
    fit(ax, -40, 165, 62.0)
    title(ax, f'B–B  through the right bay, Y {yb:.0f}, seen from the right')
    # C-C centre
    ax = fig.add_axes([.005, .035, .36, .32])
    section_centre(ax, sc, est)
    fit(ax, -95, 150, 47.0)
    title(ax, 'C–C  centreline, from the right: lead channel')
    # D-D counterweight
    ax = fig.add_axes([.365, .035, .245, .32])
    section_cw(ax, sc, est)
    fit(ax, 0, 150, 80.0)
    title(ax, 'D–D  counterweight at X −170, from behind')
    text_blocks(fig, .62, .345, [
        ('Service (no tool needed for the lids)', [
            ('1', 'Lift the hood lids (4 magnets each): T101 service area, both bays, the board.'),
            ('2', 'Battery: lift out of the right bay; one plug at the BMS. Charge without opening:\n'
                  'toolbox lid → jack (12.6 V Li-ion charger, bought).'),
            ('3', 'Counterweight: 2 × M4 from inside T101 (lids off); it slides back off its ledges.'),
            ('4', 'Hub screws: ARM60 off first, unchanged from R3.')]),
        ('Why here', [
            ('•', 'Battery: heaviest item, low and at the rear (helps the balance), on the right to\n'
                  'offset the cab on the left. Clear of the T101 ribs, so it never covers a screw.'),
            ('•', 'Board on the left, behind the Cat\'s louvres: all 7 motor cables end there, the\n'
                  'louvres are its vents. The slip ring, swing and arm leads all arrive on that side.'),
            ('•', 'Ballast in the counterweight\'s lower part: the shot sets the balance after the\n'
                  'prints are weighed (sheet 4), sealed in with epoxy.')])], fs=7.3, lh=.0116)
    pdf.savefig(fig); fig.savefig(PNG[2], dpi=110); plt.close(fig)


def cw_y_extent(y):
    """Rear end of the counterweight at a given Y (plan outline)."""
    g = Polygon(PLAN['cw']).intersection(LineString([(-300, y), (0, y)]))
    return g.bounds[0]


def section_side(ax, sc, est, y):
    """Vertical cut along X at the given Y through a side bay."""
    sgn = 1 if y > 0 else -1
    belt = sc['sil'][('belt', 'xz')]
    shape(ax, belt, TRK_L, TRK, lw=.4, z=1)
    shape(ax, sc['sil'][('tracks', 'xz')], '#eceff0', TRK, lw=.35, z=1.1)
    hs = dict(fc=BODY_L, ec=BODY, lw=.8, z=5, hatch='////')
    xr = cw_y_extent(y)
    zt = B['hood_top']
    # counterweight cut: walls 3, pocket with shot
    box(ax, xr, Z_BOT, CWF, Z_BOT + 3, **hs); box(ax, xr, zt - 3, CWF, zt, **hs)
    box(ax, xr, Z_BOT, xr + 3, zt, **hs); box(ax, CWF - 3, Z_BOT, CWF, zt, **hs)
    box(ax, xr + 3, Z_BOT + 3, CWF - 3, est['fill_z'], fc=STEEL_L, ec=STEEL, lw=.5, z=4.5, hatch='....')
    # module: floor, end walls; the side skin is behind the cut (dashed)
    front = B['left_front'] if sgn > 0 else B['right_front']
    box(ax, CWF, Z_BOT, front, Z_BOT + 2.5, **hs)
    box(ax, CWF, Z_BOT, CWF + 2.5, Z_DECK, **hs)
    box(ax, front - 2.5, Z_BOT, front, Z_DECK, **hs)
    lid = [(CWF, zt), (CAT['slope'][0], zt), (CAT['slope'][1], B['step'])]
    if sgn > 0:
        lid += [(B['cab_x'][0] - 1.3, B['step'])]
        ln = LineString(lid).buffer(1.25, cap_style=2, join_style=2)
        shape(ax, ln, BODY_L, BODY, lw=.8, z=5.5, hatch='////')
        cab = xz([side_mm(p) for p in SIDE_PX['cab']])
        cabg = Polygon(cab)
        shape(ax, cabg.difference(cabg.buffer(-2.0)), BODY_L, BODY, lw=.8, z=5.5, hatch='////')
        box(ax, B['cab_x'][0], Z_DECK - 2.5, B['left_front'], Z_DECK, **hs)
        dash = [(CAT['cab_low_rear'], Z_DECK), (CAT['cab_x'][0], B['step'])]
        line(ax, dash, color=BODY, lw=.5, ls='--', z=5)
        for x0, x1, y0, y1 in SIDE_PX['louvres']:
            (a, za), (b, zb) = side_mm((x0, y0)), side_mm((x1, y1))
            box(ax, a, zmap(za), b, zmap(zb), fc='none', ec=BODY, lw=.4, ls='--', z=4)
        item_side(ax, 'carrier', text='controller board', fs=6.2)
        e = ITEMS['carrier']['env']
        for x in (e[0] + 5, e[1] - 5):
            box(ax, x - 1.5, Z_BOT + 2.5, x + 1.5, e[4], fc='#d5dbdb', ec=GREY, lw=.4, z=7)
        note(ax, (-100, 175), (-175, 240), 'louvres behind the cut:\nvents for the board', color=BODY, relpos=(1, .5), ha='right', fs=6.3)
        note(ax, (30, 200), (60, 240), 'B106 cab, empty', color=BODY, relpos=(0, .5), fs=6.3)
    else:
        lid = [(CWF, zt), (CAT['tank_x'][0] - 2, zt)]
        ln = LineString(lid).buffer(1.25, cap_style=2, join_style=2)
        shape(ax, ln, BODY_L, BODY, lw=.8, z=5.5, hatch='////')
        tank = Polygon([(CAT['tank_x'][0], Z_DECK), (CAT['tank_x'][0], B['tank_top']), (CAT['tank_x'][1], B['tank_top']),
                        (CAT['tank_x'][1], B['tank_step']), (CAT['tank_x'][2], B['tank_step']), (CAT['tank_x'][2], Z_DECK)])
        shape(ax, tank.difference(tank.buffer(-2.0)), BODY_L, BODY, lw=.8, z=5.5, hatch='////')
        tb = Polygon([(CAT['toolbox_x'][0], Z_DECK), (CAT['toolbox_x'][0], B['toolbox_top']), (CAT['toolbox_x'][1], B['toolbox_top']),
                      (CAT['toolbox_x'][1], Z_DECK)])
        shape(ax, tb.difference(tb.buffer(-2.0)), BODY_L, BODY, lw=.8, z=5.5, hatch='////')
        box(ax, CAT['tank_x'][0], Z_DECK - 2.5, front, Z_DECK, **hs)
        fd = xz(CAT['front_door'])
        line(ax, [(CWF, zt), (CAT['door_seam_right'], zt)] + fd, color=BODY, lw=.5, ls='--', z=4)
        item_side(ax, 'battery', text='battery', fs=6.2)
        for n in ('switch', 'jack'):
            item_side(ax, n, lw=.6)
        note(ax, (35, 150), (70, 215), 'toolbox: switch, fuse,\ncharge jack under the lid', color=ELEC['power'][0], relpos=(0, .5), fs=6.3)
        note(ax, (-40, 190), (-20, 240), 'B107 tank: spare', color=BODY, relpos=(0, .5), fs=6.3)
        note(ax, (-110, 122), (-130, 70), 'battery out upwards\n(right lid off)', color=ELEC['battery'][0], relpos=(.5, 1), ha='center', fs=6.3)
    line(ax, [(B['cab_x'][0] if sgn > 0 else CAT['tank_x'][0], Z_DECK), (CWF, Z_DECK)], color=BODY, lw=.4, ls=':', z=4)
    note(ax, (-165, (Z_BOT + est['fill_z'])/2), (-200, 85), 'steel shot', color=STEEL, relpos=(.5, 1), ha='center', fs=6.3)
    dim_v(ax, front + (8 if sgn > 0 else 8), Z_BOT + 2.5, Z_DECK, f'{Z_DECK - Z_BOT - 2.5:.0f}', side=1, fs=6.2)


def section_centre(ax, sc, est):
    shape(ax, sc['sil'][('chassis', 'xz')], '#f6efcf', '#b7950b', lw=.4, z=1.1)
    R3.frame_cut_xz(ax, lw=.6)
    R3.motor_side(ax, lw=.6, labels=False)
    R3.slide_cut(ax, lw=.6)
    box(ax, ARM_X[0], Z_DECK, ARM_X[1], 240.0, fc=ARM_L, ec=ARMC, lw=.6, ls='--', z=2)
    hs = dict(fc=BODY_L, ec=BODY, lw=.8, z=5, hatch='////')
    zt = B['hood_top']
    box(ax, -TAIL, Z_BOT, CWF, Z_BOT + 3, **hs); box(ax, -TAIL, zt - 3, CWF, zt, **hs)
    box(ax, -TAIL, Z_BOT, -TAIL + 3, zt, **hs)
    wz = R3.MOTOR['can_z']
    box(ax, CWF - 3, Z_BOT, CWF, wz - R3.WINDOW_R, **hs)
    box(ax, CWF - 3, wz + R3.WINDOW_R, CWF, Z_DECK + 1, **hs)
    box(ax, CWF - 3, Z_DECK + 16, CWF, zt, **hs)
    # channel: rear wall of the channel and its floor, lead path
    box(ax, CWF - 23, Z_BOT + 3, CWF - 20, Z_DECK + 16, **hs)
    box(ax, -TAIL + 3, Z_BOT + 3, CWF - 23, est['fill_z'], fc=STEEL_L, ec=STEEL, lw=.5, z=4.5, hatch='....')
    lead = [(R3.MOTOR['can_x'][0] - R3.MOTOR['term'], wz), (CWF - 10, wz), (CWF - 10, Z_DECK + 8), (CWF + 6, Z_DECK + 8),
            (CWF + 6, Z_DECK + 14)]
    line(ax, lead, color=WIRE['swing'], lw=1.6, z=9)
    lid = LineString([(CWF, zt), (CAT['slope'][0], zt), (CAT['slope'][1], B['step']), (ARM_X[0] - 2, B['step'])]).buffer(1.25, cap_style=2, join_style=2)
    shape(ax, lid, BODY_L, BODY, lw=.8, z=5.5, hatch='////')
    ax.add_patch(Circle((-26.0, Z_DECK + 5), 2.2, fc=WIRE['power'], ec='white', lw=.4, zorder=9))
    ax.add_patch(Circle((-26.0, Z_DECK + 10), 2.2, fc=WIRE['arm'], ec='white', lw=.4, zorder=9))
    k = dict(fs=6.3)
    note(ax, (CWF - 10, 140), (-232, 196), 'lead channel 24 × 20,\nsealed from the shot', color=WIRE['swing'], relpos=(0, .5), **k)
    note(ax, (CWF - 1.5, wz), (-120, 85), f"T101 rear bulkhead,\nØ{2*R3.WINDOW_R:.0f} window (R3)", color=UP, relpos=(0, .5), **k)
    note(ax, (-26, Z_DECK + 10), (5, 185), 'cross-over at X −26:\n12 V feed + arm leads', color=WIRE['power'], relpos=(0, .5), **k)
    note(ax, (-175, (Z_BOT + est['fill_z'])/2), (-232, 82), 'steel shot', color=STEEL, relpos=(0, .5), **k)
    note(ax, (-60, B['hood_top'] - 6), (-60, 235), 'hood lid', color=BODY, ha='center', relpos=(.5, 0), **k)
    ax.text(40, 190, 'ARM60 base', fontsize=6.3, color=ARMC, ha='center')
    ax.plot([0, 0], [70, 250], color=LIGHT, lw=.5, ls='-.', zorder=0.5)


def section_cw(ax, sc, est):
    S = sc['sil']
    def flip(g):
        return affinity.scale(g, -1, 1, origin=(0, 0))
    shape(ax, flip(S[('belt', 'yz')]), TRK_L, TRK, lw=.4, z=1)
    hs = dict(fc=BODY_L, ec=BODY, lw=.8, z=5, hatch='////')
    zt = B['hood_top']
    x = -170.0
    g = Polygon(PLAN['cw']).intersection(LineString([(x, -300), (x, 300)]))
    y0, y1 = g.bounds[1], g.bounds[3]
    outer = Polygon([(-y, z) for y, z in rrect(y0, Z_BOT, y1, zt, 4.5)])
    inner = outer.buffer(-3.0, join_style=2)
    shape(ax, outer.difference(inner), BODY_L, BODY, lw=.8, z=5, hatch='////')
    pk = est['pocket'].intersection(LineString([(x, -300), (x, 300)]))
    shape(ax, sbox(-pk.bounds[3], Z_BOT + 3, -pk.bounds[1], est['fill_z']), STEEL_L, STEEL, lw=.5, z=5.5, hatch='....')
    box(ax, -12, Z_BOT + 3, 12, est['fill_z'], fc='white', ec=BODY, lw=.5, z=5.6)
    ax.text(0, est['fill_z'] + 3, 'lead channel\n(behind the cut)', fontsize=5.8, color=WIRE['swing'], ha='center', va='bottom', zorder=6)
    dim_v(ax, -y1 - 12, Z_BOT + 3, est['fill_z'], f"{est['fill_z'] - Z_BOT - 3:.0f}", side=-1, fs=6.2)
    dim_h(ax, -y1, -y0, Z_BOT - 10, f'{y1 - y0:.0f}', side=-1, fs=6.2)
    note(ax, (0, est['fill_z'] + 25), (0, 240), f"{est['shot_cm3']:.0f} cm³ of shot = {est['shot_kg']:.2f} kg\n"
         f"(poured, {SHOT_DENSITY*1000:.1f} g/cm³), epoxy on top", color=STEEL, ha='center', relpos=(.5, 0), fs=6.3)


# ------------------------------------------------------------------ sheet 4: parts, balance, wiring, checks, decisions
def sheet4(pdf, sc, est, chk):
    fig = plt.figure(figsize=FIG)
    header(fig, 4, 'parts, balance, wiring, checks', 'Masses: printed walls at PETG 1.27 g/cm³ (+15 % for bosses and ribs), '
           'electronics from typical module weights; CAD masses from simulation/turntable_mass_properties.json. Estimates.')
    rows = [('part', 'size on the bed', 'how it prints', 'est. g', 'what it is')]
    for n, p in est['parts'].items():
        f = p['bed']
        rows.append((n, f"{f['side']:.0f} sq × {f['height']:.0f}", f['how'], f"{p['kg']*1000:.0f}", p['note']))
    fig.text(.015, .925, 'Printed parts, issue-1 split: 9 parts, all fit a 256 bed (sheet 5 proposes 3)', fontsize=10.2, weight='bold', color=INK)
    y = table(fig, .015, .905, [.135, .075, .095, .035, .175], rows, fs=7.0, lh=.0118)
    bought = [('Bought (no custom metal parts)', ''),
              ('3 × 18650 Li-ion cell, 3S BMS (10 A), nickel strip', 'battery'),
              ('ESP32 DevKit, 3 × DRV8871 board, 2 × DRV8833 board', 'controller board'),
              ('buck 12 → 6 V 3 A, buck 12 → 5 V 1 A, perfboard', 'controller board'),
              ('rocker switch, mini blade fuse 5 A + holder, DC jack', 'toolbox'),
              (f"steel shot 2–3 mm, about {est['shot_kg']:.1f} kg; 2-part epoxy", 'counterweight'),
              ('16 × magnet Ø6 × 3; M3 inserts and screws (about 20)', 'lids, fixing'),
              ('2 × M4 × 12 + nuts (into the existing T101 holes)', 'counterweight')]
    y = table(fig, .015, y - .012, [.31, .2], bought, fs=7.0, lh=.0118)
    # balance
    rows = [('mass item', 'kg', 'X', 'Y', 'Z')]
    for r in est['rows']:
        rows.append((r['name'], f"{r['kg']:.3f}", f"{r['c'][0]:.0f}", f"{r['c'][1]:.0f}", f"{r['c'][2]:.0f}"))
    cu = est['c_up']
    rows.append(('UPPER, arm stretched', f"{est['m_up']:.2f}", f"{cu[0]:+.1f}", f"{cu[1]:+.1f}", f"{cu[2]:.0f}"))
    rows.append(('UPPER, arm tucked (bound)', '', f"{est['c_tucked'][0]:+.1f}", f"{est['c_tucked'][1]:+.1f}", ''))
    fig.text(.545, .925, 'Masses and balance (vehicle frame, mm)', fontsize=10.2, weight='bold', color=INK)
    y2 = table(fig, .545, .905, [.17, .04, .035, .035, .035], rows, fs=6.9, lh=.0108, bold_rows=(len(rows) - 2, len(rows) - 1))
    sim = est['sim']
    text_blocks(fig, .545, y2 - .008, [('', [
        ('•', "Ballast set for the upper's CG on the swing axis with the arm stretched (as R3). In the build: weigh\n"
              'nothing, balance instead: the upper on a rod under X 0, arm stretched, pour shot until it levels.'),
        ('•', f"Upper {est['m_up']:.2f} kg, {est['I_up']:.3f} kg·m² about the swing axis; the R3 simulation used {sim['m']:.2f} kg,\n"
              f"{sim['I']:.3f} kg·m² (60 mm placeholders). With the motor's reflected {sim['I_rotor']:.2f} kg·m² the stops see\n"
              f"{100*((est['I_up'] + sim['I_rotor'])/(sim['I'] + sim['I_rotor']) - 1):+.1f} % inertia: the unramped stop's {sim['stop_N']:.0f} N "
              'moves by about that. Re-run with the body CAD.'),
        ('•', f"Whole machine CG X: {est['machine_stretched'][0]:+.0f} (arm stretched), {est['machine_tucked'][0]:+.0f} (tucked bound); "
              f"the tracks\ncarry it from X {est['support'][0]:.0f} to {est['support'][1]:+.0f} (sprocket to idler).")])],
        fs=7.1, lh=.0113)
    # wiring diagram
    ax = fig.add_axes([.015, .03, .40, .40])
    wiring(ax)
    # checks
    rows = [('check', 'value', 'limit', '')]
    for c in chk['checks']:
        rows.append((c['what'], c['value'], c['limit'], 'pass' if c['ok'] else 'FAIL'))
    cols = [None] + [[None, None, None, '#1e8449' if c['ok'] else '#c0392b'] for c in chk['checks']]
    fig.text(.43, .385, f"Checks: {sum(c['ok'] for c in chk['checks'])}/{len(chk['checks'])} pass", fontsize=10.2, weight='bold', color=INK)
    table(fig, .43, .365, [.165, .06, .052, .025], rows, fs=6.6, lh=.0104, colors=cols)
    text_blocks(fig, .745, .385, [
        ('Decided (issue 2)', [
            ('D1', 'Battery: 3 × 18650 Li-ion in series (3S1P) with a\n'
                   '3S BMS, straight onto the 12 V motors: 12.6 V full,\n11.1 V nominal, 9.0 V empty.'),
            ('D2', 'Control: ESP32 with a Bluetooth gamepad.'),
            ('D3', 'Ballast: loose shot poured into the counterweight\nand sealed with epoxy.'),
            ('D4', f'Tail: the Cat outline widened (corners R {math.hypot(CAT["cw_corner_x"], W):.0f}).'),
            ('D5', f'Skirt: {Z_DECK - Z_BOT:.0f} deep over the T101 sides.'),
            ('D6', 'Detail: louvres, steps, handrail, exhaust, lamps,\nwindow recesses.')]),
        ('Open', [
            ('•', 'How many prints: the user prefers one piece. A 256\nprinter needs at least 3 (sheet 5).')]),
        ('Then', [
            ('•', 'CAD of the body and the T101 inserts, a swing\nsweep with the body, the balance from the CAD,\n'
                  'and the R3 simulation re-run.')])], fs=7.0, lh=.0112, tab=.022)
    pdf.savefig(fig); fig.savefig(PNG[3], dpi=110); plt.close(fig)


def wiring(ax):
    ax.set_xlim(0, 100); ax.set_ylim(0, 62); ax.axis('off')
    ax.set_title('Wiring (12 V bus from the 3S pack)', fontsize=10.2, loc='left', weight='bold', color=INK, pad=3)
    def blk(x, y, w, h, t, key, fs=6.4):
        ec, fc = ELEC[key] if key in ELEC else (key, '#f4f6f6')
        box(ax, x, y, x + w, y + h, fc=fc, ec=ec, lw=.8, z=3)
        ax.text(x + w/2, y + h/2, t, fontsize=fs, ha='center', va='center', color=ec, zorder=4, linespacing=1.2)
    def arrow(p, q, c, lw=1.4):
        ax.annotate('', q, p, arrowprops=dict(arrowstyle='->', lw=lw, color=c, shrinkA=0, shrinkB=0), zorder=5)
    blk(0, 40, 15, 14, '3S1P 18650\n+ 3S BMS\n9.0–12.6 V', 'battery')
    blk(0, 18, 15, 10, 'DC jack\n(12.6 V\ncharger)', 'power')
    blk(20, 44, 11, 7, 'fuse 5 A', 'power')
    blk(35, 44, 11, 7, 'switch', 'power')
    arrow((7.5, 28), (7.5, 40), WIRE['charge'])
    arrow((15, 47.5), (20, 47.5), WIRE['power']); arrow((31, 47.5), (35, 47.5), WIRE['power'])
    box(ax, 50, 2, 100, 60, fc='#f3f8fc', ec=ELEC['carrier'][0], lw=.8, ls='--', z=1)
    ax.text(51, 58.5, 'controller board (left bay)', fontsize=6.6, color=ELEC['carrier'][0], va='top', zorder=2)
    ax.plot([46, 53], [47.5, 47.5], color=WIRE['power'], lw=1.4, zorder=4)
    ax.plot([53, 53], [8, 52], color=WIRE['power'], lw=1.4, zorder=4)
    ax.text(52.2, 30, '12 V', fontsize=6.3, color=WIRE['power'], rotation=90, ha='right', va='center')
    blk(56, 46, 15, 8, '3 × DRV8871\nlimit 0.6 A', 'carrier')
    blk(56, 32, 15, 8, 'buck 6 V 3 A', 'carrier')
    blk(56, 20, 15, 8, '2 × DRV8833', 'carrier')
    blk(56, 6, 15, 8, 'buck 5 V →\nESP32', 'carrier')
    for y in (50, 36, 10):
        arrow((53, y), (56, y), WIRE['power'], lw=1.0)
    arrow((63.5, 32), (63.5, 28), WIRE['power'], lw=1.0)
    blk(79, 50, 20, 7, 'L + R track motors\n(via the slip ring)', WIRE['track'], fs=6.0)
    blk(79, 41, 20, 6, 'swing motor', WIRE['swing'], fs=6.0)
    blk(79, 19, 20, 9, '4 × V6-U60 N20\n(ARM60)', WIRE['arm'], fs=6.0)
    blk(79, 5, 20, 9, 'ESP32: PWM to all\n7 bridges; gamepad', ELEC['carrier'][0], fs=6.0)
    arrow((71, 51.5), (79, 53.5), WIRE['track'], lw=1.0); arrow((71, 49), (79, 44), WIRE['swing'], lw=1.0)
    arrow((71, 24), (79, 23.5), WIRE['arm'], lw=1.0); arrow((71, 10), (79, 9.5), ELEC['carrier'][0], lw=1.0)
    ax.text(0, 9, 'Peak at the 0.6 A limits: 3 × 0.6 + N20s about 0.65 (at 12 V)\n+ ESP32 0.15 = about 2.6 A: 5 A fuse, '
            '2 A per slip-ring way.', fontsize=6.4, color=GREY, va='center', linespacing=1.3)


# ------------------------------------------------------------------ sheet 5: fewer parts
SPLIT_C = {'B101 counterweight': ('#7e5109', '#f5deb3'), 'B102 left half': (BODY, BODY_L), 'B103 right half': ('#1f618d', '#d6eaf8'),
           'one piece (for comparison)': ('#c0392b', '#fadbd8')}


def side_profile(side):
    """XZ outline of one body half (as in the side views of sheet 2), for its print footprint on its outer face."""
    band = sbox(CWF, Z_BOT, B['left_front'] if side > 0 else B['right_front'], Z_DECK)
    if side > 0:
        hood = Polygon([(CAT['cab_low_rear'], Z_DECK), (CAT['cab_x'][0], B['step']), (CAT['slope'][1], B['step']),
                        (CAT['slope'][0], B['hood_top']), (CWF, B['hood_top']), (CWF, Z_DECK)])
        cab = Polygon(xz([side_mm(p) for p in SIDE_PX['cab']]))
        return shapely.union_all([band, hood, cab])
    door = sbox(CWF, Z_DECK, CAT['door_seam_right'], B['hood_top'])
    fd = xz(CAT['front_door'])
    front = Polygon([(CAT['door_seam_right'], Z_DECK)] + fd + [(fd[-1][0], Z_DECK)])
    tank = Polygon([(CAT['tank_x'][0], Z_DECK), (CAT['tank_x'][0], B['tank_top']), (CAT['tank_x'][1], B['tank_top']),
                    (CAT['tank_x'][1], B['tank_step']), (CAT['tank_x'][2], B['tank_step']), (CAT['tank_x'][2], Z_DECK)])
    tb = sbox(CAT['toolbox_x'][0], Z_DECK, CAT['toolbox_x'][1], B['toolbox_top'])
    ex = sbox(CAT['exhaust_x'][0], B['hood_top'] - 1, CAT['exhaust_x'][1], B['exhaust_top'])
    hood_r = sbox(CWF, Z_DECK, CAT['tank_x'][0], B['hood_top'])
    return shapely.union_all([band, door, front, tank, tb, ex, hood_r])


def min_square(g):
    """Smallest square that holds the footprint, turned on the bed in 1° steps: (side, angle)."""
    best = (1e9, 0)
    for a in range(0, 91):
        r = affinity.rotate(g, a, origin='centroid')
        x0, y0, x1, y1 = r.bounds
        best = min(best, (max(x1 - x0, y1 - y0), a))
    return best


def split_parts(est):
    P = est['parts']
    cw = Polygon(PLAN['cw'])
    left = shapely.union_all([Polygon(PLAN['left_module']), Polygon(PLAN['lid_left']), Polygon(PLAN['cab'])])
    right = shapely.union_all([Polygon(PLAN['right_module']), Polygon(PLAN['lid_right']), Polygon(PLAN['tank']), Polygon(PLAN['toolbox'])])
    def kg(names):
        return sum(P[n]['kg'] for n in names)
    out = {
        'B101 counterweight': dict(plan=cw, z=(Z_BOT, B['hood_top']), kg=kg(['B101 counterweight shell']),
                                   what='as issue 1: shot pocket, lead channel, lamps', orient='upright'),
        'B102 left half': dict(plan=left, z=(Z_BOT, B['cab_top']), kg=kg(['B102 left side module', 'B104 hood lid, left', 'B106 cab']),
                               what='skirt, side with the louvres, left hood half, cab', orient='side', profile=side_profile(1)),
        'B103 right half': dict(plan=right, z=(Z_BOT, B['exhaust_top']),
                                kg=kg(['B103 right side module', 'B105 hood lid, right', 'B107 tank block', 'B108 toolbox lid and box',
                                       'B109 details']),
                                what='skirt, doors, right hood half, tank, steps, toolbox, exhaust', orient='side', profile=side_profile(-1))}
    allp = shapely.union_all([cw, left, right])
    out['one piece (for comparison)'] = dict(plan=allp, z=(Z_BOT, B['cab_top']), kg=sum(v['kg'] for v in out.values()),
                                             what='everything above in one print', orient='upright')
    for n, v in out.items():
        x0, y0, x1, y1 = v['plan'].bounds
        v['size'] = (x1 - x0, y1 - y0, v['z'][1] - v['z'][0])
        if v['orient'] == 'side':
            side, ang = min_square(v['profile'])
            v['fit'] = dict(side=side, angle=ang, height=v['size'][1], fits=side <= BED and v['size'][1] <= BED,
                            how=f"on its outer side face{', turned %d°' % ang if ang else ''}")
        else:
            side, ang = min_square(v['plan'])
            v['fit'] = dict(side=side, angle=ang, height=v['size'][2], fits=side <= BED and v['size'][2] <= BED,
                            how=f"upright{', turned %d°' % ang if ang else ''}")
    return out


def sheet5(pdf, sc, est, chk):
    sp = split_parts(est)
    fig = plt.figure(figsize=FIG)
    a, b, h = sp['one piece (for comparison)']['size']
    header(fig, 5, 'fewer parts: what a 256 printer allows', f'The body is {b:.0f} wide, {a:.0f} long, {h:.0f} tall. On a 256 bed '
           f'a print spanning the full {b:.0f} width must be under {math.sqrt(2)*BED - b:.0f} deep (laid diagonally): only the '
           'counterweight is. So at least 3 prints.')
    # plan of the 3-part split
    ax = fig.add_axes([.005, .43, .45, .49])
    context(ax, sc, 'xy', arm=False)
    for n in ('B101 counterweight', 'B102 left half', 'B103 right half'):
        ec, fc = SPLIT_C[n]
        shape(ax, sp[n]['plan'], fc, ec, lw=1.0, z=5)
    for n in ('cab', 'tank', 'toolbox'):
        patch(ax, PLAN[n], fc='none', ec=GREY, lw=.5, ls='--', z=5.5)
    line(ax, [(CWF, 0), (ARM_X[0] - 2, 0)], color=INK, lw=1.2, z=6)
    k = dict(fs=6.6)
    for s_ in (1, -1):
        for x in (-120.0, -60.0):
            ax.add_patch(Circle((x, s_*65), 3.2, fc='white', ec=INK, lw=.8, zorder=7))
            ax.plot([x - 2, x + 2], [s_*65, s_*65], color=INK, lw=.7, zorder=7.1)
        box(ax, 54, s_*64 - 3, 66, s_*77, fc='#fdebd0', ec=INK, lw=.6, z=6.5)
        ax.add_patch(Circle((CWF - 4, s_*40), 2.6, fc='#f5deb3', ec='#7e5109', lw=.7, zorder=7))
    note(ax, (-60, 65), (-150, 205), '2 × M3 per half, screwed down sleeves in the hood\ntop into new inserts in the T101 rib tops',
         relpos=(.5, 0), ha='center', **k)
    note(ax, (60, 70), (95, 200), 'front hook under the T101\nbase-plate edge (slide in 10)', relpos=(0, .5), **k)
    note(ax, (CWF - 4, -40), (-285, -150), '2 × M4,\nas issue 1', color='#7e5109', relpos=(.5, 1), ha='center', **k)
    note(ax, (-90, 0), (-150, -205), 'seam on the hood centreline\n(lap joint)', relpos=(.5, 1), ha='center', **k)
    for n, (x, y) in (('B101 counterweight', (-170, 0)), ('B102 left half', (-90, 115)), ('B103 right half', (-90, -115))):
        ax.text(x, y, n.replace(' ', '\n', 1), fontsize=7.4, weight='bold', color=SPLIT_C[n][0], ha='center', va='center', zorder=8,
                rotation=90 if n.startswith('B101') else 0)
    box(ax, ARM_X[0], -ARM_Y, ARM_X[1], ARM_Y, fc=ARM_L, ec=ARMC, lw=.7, ls='--', z=4)
    ax.text(45, 0, 'ARM60 base\n(stays)', fontsize=6.5, color=ARMC, ha='center', va='center', zorder=4.5)
    fit(ax, -45, 0, 82.0)
    title(ax, 'PROPOSED: 3 PRINTS (plan, front to the right)')
    # each print on the bed
    ax = fig.add_axes([.47, .58, .52, .33])
    title(ax, f'EACH PRINT ON A {BED:.0f} × {BED:.0f} BED (top view of the bed)')
    gap = 30.0
    for i, n in enumerate(('B101 counterweight', 'B102 left half', 'B103 right half', 'one piece (for comparison)')):
        v = sp[n]
        ox = i*(BED + gap)
        box(ax, ox, 0, ox + BED, BED, fc='#f8f9f9', ec=GREY, lw=.8, z=1)
        g = v['profile'] if v['orient'] == 'side' else v['plan']
        g = affinity.rotate(g, v['fit']['angle'], origin='centroid')
        c = g.centroid
        x0, y0, x1, y1 = g.bounds
        g = affinity.translate(g, ox + BED/2 - (x0 + x1)/2, BED/2 - (y0 + y1)/2)
        ec, fc = SPLIT_C[n]
        shape(ax, g, fc, ec, lw=.9, z=3, alpha=.9)
        ok = v['fit']['fits']
        ax.text(ox + BED/2, -14, n, fontsize=7.6, weight='bold', color=ec, ha='center', va='top')
        sz = v['size']
        ax.text(ox + BED/2, -30, f"{sz[0]:.0f} × {sz[1]:.0f} × {sz[2]:.0f}, about {v['kg']*1000:.0f} g\n{v['fit']['how']}\n"
                + (f"needs {v['fit']['side']:.0f} of bed, {v['fit']['height']:.0f} tall: fits" if ok else
                   f"needs at least {sz[0]:.0f} × {sz[1]:.0f}: does not fit"),
                fontsize=6.8, color=INK if ok else '#c0392b', ha='center', va='top', linespacing=1.3)
    ax.set_xlim(-10, 4*BED + 3*gap + 10); ax.set_ylim(-95, BED + 10); ax.set_aspect('equal'); ax.axis('off')
    # pros and cons
    L, R1 = sp['B102 left half'], sp['B103 right half']
    rows = [('', 'Issue 1: 9 prints', 'Proposed: 3 prints', '1 print (larger printer)'),
            ('fits your 256 × 256 × 256 printer', 'yes', 'yes', f'no: needs about {a + 4:.0f} × {b + 4:.0f} of bed'),
            ('largest prints', f"counterweight {sp['B101 counterweight']['kg']*1000:.0f} g; the\nothers 170 g or less",
             f"counterweight {sp['B101 counterweight']['kg']*1000:.0f} g; halves\n{L['kg']*1000:.0f} g and {R1['kg']*1000:.0f} g",
             f"{sp['one piece (for comparison)']['kg']*1000:.0f} g in one print"),
            ('supports', 'few: lids and boxes print flat', 'inside the cab and under the inner\nskirt (halves print on their outer side)',
             'under the whole hood and cab roof'),
            ('seams you see', 'hood lids, cab, tank, toolbox,\ncounterweight', 'hood centreline (lap joint) and the\ncounterweight seam the Cat also has',
             'counterweight seam only, if the\ncounterweight stays separate'),
            ('fixings', '16 magnets, about 20 M3, 2 M4', '4 M3, 2 front hooks, 2 M4', '2 M4 and 2–4 M3'),
            ('reach the T101 adjustments', 'lift 2 lids by hand', '2 screws, slide 10 mm, lift (per half)', 'lift the whole shell'),
            ('reach the battery', 'lift the right lid', 'lift the right half, unplug 1 plug', 'lift the whole shell'),
            ('charge, switch, ESP32 USB', 'under the toolbox lid', 'from outside: switch and jack on the\ntoolbox, USB through a louvre slot',
             'from outside, as for 3 prints'),
            ('if a print fails or breaks', 'reprint a small part', 'reprint one half (about 0.3–0.4 kg)', 'reprint everything (about 1.1 kg)'),
            ('stiffness, rattles', 'many joints', 'three joints, each half one stiff shell', 'stiffest')]
    cols = [None] + [[None, None, '#1e8449' if i in (1, 4, 5, 8, 10) else None, '#c0392b' if i == 1 else None] for i in range(1, len(rows))]
    fig.text(.015, .395, 'Pros and cons', fontsize=10.2, weight='bold', color=INK)
    table(fig, .015, .375, [.135, .145, .19, .16], rows, fs=7.0, lh=.0115, colors=cols)
    text_blocks(fig, .67, .395, [
        ('Recommendation', [
            ('•', '3 prints on your 256 printer. They keep almost all of the\n'
                  'one-piece benefit: two shells instead of nine parts, no lids,\n'
                  'nothing to rattle, and charging still needs no opening.'),
            ('•', f'If you can use a printer with a bed of at least about {a + 4:.0f} × {b + 4:.0f},\n'
                  'the whole body can be one print. It costs reach and\n'
                  'reprint size, see the table.')]),
        ('What changes from issue 1', [
            ('•', 'The cab, tank, toolbox, lids and details merge into the two\nhalves; the magnets go.'),
            ('•', 'Switch on the toolbox top, charge jack in its front face; the\n'
                  'fuse moves inside (rarely needed). ESP32 USB-C through a\n'
                  'louvre slot; WiFi updates later.'),
            ('•', 'Battery and board stay where they are; the cables between\n'
                  'the halves get one 12 V plug and 150 mm of slack.'),
            ('•', 'T101 change: 2 M3 inserts in each rib top (instead of 3 in\n'
                  'each rib side).')])], fs=7.2, lh=.0116)
    pdf.savefig(fig); fig.savefig(PNG[4], dpi=110); plt.close(fig)


# ------------------------------------------------------------------ checks
def run_checks(sc, est):
    c, out, tr = CAT, [], []
    def tcheck(what, traced, spec):
        tr.append(dict(what=what, traced=traced, spec=spec, error=traced/spec - 1))
    tcheck('cab top (drawing A)', c['cab_top'], SPEC['cab_top']/S15)
    tcheck('upper-frame bottom (drawing A)', c['bottom'], SPEC['counterweight_clearance']/S15)
    tcheck('track length (drawing A)', c['track_length'], SPEC['track_length']/S15)
    tcheck('rear end (drawing A)', -c['rear_end'], c['tail'])
    tcheck('upper-frame width (drawing B)', 2*c['half_width'], 2*c['spec_half_width'])
    tcheck('counterweight side end (render C)', -c['cw_side_end'], -c['cw_corner_x'])
    tcheck('handrail top (render C)', c['rail_top'], SPEC['handrail']/S15)
    def add(what, value, limit, ok):
        out.append(dict(what=what, value=value, limit=limit, ok=bool(ok)))
    worst = max(abs(t['error']) for t in tr)
    add('trace against Caterpillar\'s numbers', f'{100*worst:.1f} %', '≤ 2.5 %', worst <= .025)
    for n, p in est['parts'].items():
        p['bed'] = bed_fit(p)
    side = max(p['bed']['side'] for p in est['parts'].values())
    add('largest part on the bed', f'{side:.0f}', f'≤ {BED:.0f}', side <= BED)
    add('cab to the ARM60 base (Y)', f"{B['cab_y'][0] - ARM_Y:.1f}", '≥ 2', B['cab_y'][0] - ARM_Y >= 2)
    add('tank and toolbox to the base', f"{-B['tank_y'][0] - ARM_Y:.1f}", '≥ 2', -B['tank_y'][0] - ARM_Y >= 2)
    lid_gap = ARM_X[0] - max(Polygon(PLAN['lid_left']).bounds[2], Polygon(PLAN['lid_right']).bounds[2])
    add('hood lids to the base (X)', f'{lid_gap:.1f}', '≥ 2', lid_gap >= 2)
    add('module walls to T101 (Y)', f"{B['inner'] - 74.0:.1f}", '≥ 2', B['inner'] - 74.0 >= 2)
    gap = Z_BOT - sc['lower_zmax']
    add('body bottom over every lower part', f'{gap:.1f}', '≥ 10', gap >= 10)
    add('body bottom over the swing envelope', f'{Z_BOT - X.TURNTABLE_Z:.1f}', '≥ 3', Z_BOT - X.TURNTABLE_Z >= 3)
    sz = sbox(R3.REAR_BULK[1], -R3.RIB_Y[1], -R3.HUB_BULK[1], R3.RIB_Y[1])
    clash = [n for n, it in ITEMS.items() if sz.intersects(sbox(it['env'][0], it['env'][2], it['env'][1], it['env'][3]))]
    add('electronics over the T101 service area', str(len(clash)), '0', not clash)
    # every item inside its bay or box with clearance
    def inside(env, room, gap=1.5):
        return (env[0] >= room[0] + gap and env[1] <= room[1] - gap and env[2] >= room[2] + gap and env[3] <= room[3] - gap)
    tb = (CAT['toolbox_x'][0] + 2, CAT['toolbox_x'][1] - 2, -W + 2, B['tank_y'][0] - 2)
    ok_items = [inside(ITEMS['battery']['env'], WALL_IN['right']), inside(ITEMS['carrier']['env'], WALL_IN['left']),
                all(inside(ITEMS[n]['env'], tb, .5) for n in ('switch', 'fuse', 'jack'))]
    add('battery, board, switch gear in their bays', f'{sum(ok_items)}/3', '3/3', all(ok_items))
    hb = ITEMS['battery']['env'][5]; hc = ITEMS['carrier']['env'][5]
    add('battery and board below the deck line', f'{max(hb, hc):.1f}', f'≤ {Z_DECK:.0f}', max(hb, hc) <= Z_DECK)
    add('shot fill height in the pocket', f"{est['fill_z']:.0f}", f'≤ {Z_DECK:.0f}', est['fill_z'] <= Z_DECK)
    add('upper CG X, arm stretched', f"{est['c_up'][0]:+.1f}", '0 ± 2', abs(est['c_up'][0]) <= 2)
    add('upper CG Y (sideways)', f"{est['c_up'][1]:+.1f}", '± 5', abs(est['c_up'][1]) <= 5)
    sup = est['support']
    m1 = min(est['machine_stretched'][0] - sup[0], sup[1] - est['machine_stretched'][0])
    m2 = min(est['machine_tucked'][0] - sup[0], sup[1] - est['machine_tucked'][0])
    add('machine CG inside the tracks (margin)', f'{min(m1, m2):.0f}', '≥ 50', min(m1, m2) >= 50)
    add('upper mass vs R3 simulation', f"{est['m_up']:.2f}", f"≤ {est['sim']['m']:.2f}", est['m_up'] <= est['sim']['m'])
    rot = est['sim']['I_rotor']
    ratio = (est['I_up'] + rot)/(est['sim']['I'] + rot) - 1
    add('swing inertia + rotor vs R3 simulation', f'{100*ratio:+.1f} %', '≤ +5 %', ratio <= .05)
    sp = split_parts(est)
    three = [v for n, v in sp.items() if n != 'one piece (for comparison)']
    add('3-part split: every print fits the 256 bed', f"{sum(v['fit']['fits'] for v in three)}/3", '3/3', all(v['fit']['fits'] for v in three))
    one = sp['one piece (for comparison)']
    add('one piece on the 256 bed (expected: no)', 'no' if not one['fit']['fits'] else 'yes', 'no', not one['fit']['fits'])
    i_peak = 3*R3.JGY['i_limit'] + .65 + .15
    add('peak current vs the fuse', f'{i_peak:.1f} A', '≤ 5 A', i_peak <= 5)
    add('track motor current per slip-ring way', f"{R3.JGY['i_limit']:.1f} A", f"≤ {R3.SLIPRING['amp']:.0f} A",
        R3.JGY['i_limit'] <= R3.SLIPRING['amp'])
    return dict(trace=tr, checks=out)


def main():
    sc = scene()
    est = estimates(sc)
    est['pocket_cg_x'] = polar_moment(est['pocket'])[2]
    chk = run_checks(sc, est)
    with PdfPages(PDF) as pdf:
        sheet1(pdf, est, chk)
        sheet2(pdf, sc, est, chk)
        sheet3(pdf, sc, est, chk)
        sheet4(pdf, sc, est, chk)
        sheet5(pdf, sc, est, chk)
    res = dict(
        revision='X1 body, concept B1 issue 2', status='sketch for review, not CAD',
        decided=dict(D1='3 x 18650 Li-ion in series (3S1P), 3S BMS, straight to the 12 V motors', D2='ESP32 with a Bluetooth gamepad',
                     D3='loose shot in the counterweight, sealed with epoxy', D4='Cat tail widened (corners R 225)',
                     D5='31 mm skirt over the T101 sides', D6='details as drawn'),
        split={n: dict(kg=round(v['kg'], 3), size=[round(a, 1) for a in v['size']], fits_256=v['fit']['fits'], how=v['fit']['how'],
                       side=round(v['fit']['side'], 1), height=round(v['fit']['height'], 1)) for n, v in split_parts(est).items()},
        sources=dict(drawing='excavator_arm_60mm/references/cat320_spec_page_4.png',
                     render='excavator_arm_60mm/references/cat320_view_018.jpg', list='excavator_arm_60mm/references/SOURCES.md'),
        scales=dict(drawing_mm_per_px=19.1, render_mm_per_px=5.97, x1_scale=S15),
        cat_at_1_15={k: (round(v, 2) if isinstance(v, float) else v) for k, v in CAT.items() if not isinstance(v, list)},
        mapping=dict(dy_each_side=round(DY, 2), half_width=W, z_deck=Z_DECK, z_bottom=Z_BOT, cat_deck=round(CAT['deck'], 2)),
        x1_body={k: (round(v, 2) if isinstance(v, float) else v) for k, v in B.items()},
        parts={n: dict(kg=round(p['kg'], 3), bed=dict(side=round(p['bed']['side'], 1), height=round(p['bed']['height'], 1),
                                                     how=p['bed']['how']), note=p['note']) for n, p in est['parts'].items()},
        items={n: dict(envelope=it['env'], kg=it['kg']) for n, it in ITEMS.items()},
        balance=dict(upper_kg=round(est['m_up'], 3), upper_cg_mm=[round(v, 1) for v in est['c_up']],
                     upper_cg_tucked_bound_mm=[round(v, 1) for v in est['c_tucked']],
                     upper_inertia_kgm2=round(est['I_up'], 4), shot_kg=round(est['shot_kg'], 3), shot_cm3=round(est['shot_cm3'], 1),
                     fill_z=round(est['fill_z'], 1), shells_kg=round(est['shells_kg'], 3), electronics_kg=round(est['elec_kg'], 3),
                     machine_cg_stretched_mm=[round(v, 1) for v in est['machine_stretched']],
                     machine_cg_tucked_bound_mm=[round(v, 1) for v in est['machine_tucked']],
                     r3_simulation=dict(upper_kg=round(est['sim']['m'], 3), inertia_kgm2=round(est['sim']['I'], 4))),
        trace=[dict(what=t['what'], traced=round(t['traced'], 2), caterpillar=round(t['spec'], 2), error_pct=round(100*t['error'], 2))
               for t in chk['trace']],
        checks=chk['checks'], all_pass=all(c['ok'] for c in chk['checks']),
        outputs=[p.name for p in [PDF] + PNG])
    CHECKS.write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(f"{sum(c['ok'] for c in chk['checks'])}/{len(chk['checks'])} checks pass")
    for c in chk['checks']:
        print(('  ok   ' if c['ok'] else '  FAIL ') + f"{c['what']}: {c['value']} ({c['limit']})")
    for t in chk['trace']:
        print(f"  trace {t['what']}: {t['traced']:.2f} vs {t['spec']:.2f} ({100*t['error']:+.1f} %)")
    print(f"upper {est['m_up']:.3f} kg CG {np.round(est['c_up'], 1)} I {est['I_up']:.4f}; shot {est['shot_kg']:.3f} kg "
          f"{est['shot_cm3']:.0f} cm3 fill Z {est['fill_z']:.1f}; tucked {np.round(est['c_tucked'], 1)}")


if __name__ == '__main__':
    main()

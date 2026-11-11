"""X1 body B1 in CAD: the Caterpillar 320's upper body as three prints (mm, vehicle frame: X forward, Y left, Z up).

Every outline comes from concept B1 issue 2 (body_concept/source/draw_body_concept.py, imported, so the drawing and this
model cannot drift apart): the Cat 320 traced from Caterpillar's spec drawing and right-side render, X kept at 1:15,
heights at 1:15 over the T101 rib tops, 61.3 inserted each side of the centreline (sheet 1 and 2 of the concept).

Rev B (user review of rev A): the battery moves to the swing centreline, in a lift-off hatch; the cab glass is cut out
and the cab gets a seat and an operator; stairs, grab rail, mirrors, lamps, camera and anti-skid tops are added, each
traced from Caterpillar's own 320 renders (excavator_arm_60mm/references: views 000 left, 009 front, 018 right, 027 rear).

Printed (3 structural parts, the agreed split of concept sheet 5, plus 4 small ones):
  B101 counterweight    upright on the bed; steel-shot pocket filled during a print pause; 2 x M4 into inserts,
                        through the T101 rear bulkhead; lead channel from the T101 window; rear lamps; rear camera.
  B102 left half        cab as an open-glass shell, left hood half (louvres), left skirt and bay (controller board).
  B103 right half       right hood half, doors, tank, stairs, guardrail, grab rail, right mirror, toolbox (switch,
                        fuse, charge jack, lamp), exhaust, right skirt and bay.
  B104 cab interior     seat, joystick consoles, travel levers, monitor, right front pillar; 2 pegs in the cab floor.
  B105 operator         seated, hands on the joysticks; a peg into the seat.
  B106 battery hatch    the Cat's raised engine hood on the hood top; carries the 3 x 18650 holders and the BMS;
                        4 magnets onto 4 in the halves' hatch ledges. Lift it off by hand to change the cells.
  B107 left handrail    grab handle on the cab's front-left pillar with the left mirror; 2 pegs into the cab wall.
Each half: 2 x M3 x 12 down sleeves in its hood top into inserts in the T101 rib tops, and a front hook under the
T101 base-plate edge. Remove: hatch off, 2 screws, slide outward 10, lift. The halves meet on the hood centreline
with a lap. Solid-looking blocks (tank, counterweight) are modelled solid and printed with sparse infill, so their
inner faces print without supports; everything else is 2 mm shell.
"""
import math, sys
from functools import lru_cache
import numpy as np
import cadquery as cq
from shapely.geometry import Polygon, LineString, Point, box as sbox
from shapely.ops import unary_union
import x1_parts as X
import x1_turntable as T
import stdparts as SP                                  # bought parts drawn from their makers' drawings
import board_step as BS                                # the main board as KiCad exported it (STEP)

sys.path.insert(0, str(X.ROOT / 'body_concept/source'))
import draw_body_concept as K                          # noqa: E402  concept B1 numbers (Cat 320 traces, Cat -> X1)

R3, tp = T.R3, X.tp
box, zcyl, zring, xy_prism = X.box, X.zcyl, X.zring, X.xy_prism
xz_prism = tp.xz_prism

BODY_C, CW_C = (.90, .56, .04), (.74, .44, .04)        # Cat yellow (reads right in the viewer and in STEP viewers); counterweight darker
SHOT_C, CELL_C, BMS_C, PCB_C = (.45, .47, .50), (.13, .50, .28), (.20, .30, .25), (.10, .36, .22)
MOD_C, ESP_C, SW_C = (.75, .10, .12), (.15, .15, .17), (.08, .08, .09)
CABIN_C, OPER_C, TRIM_C, HOLD_C, MAG_C = (.20, .21, .23), (.95, .45, .10), (.07, .07, .08), (.12, .12, .13), (.55, .57, .60)
STEEL, BRASS, BLACK = X.STEEL, X.BRASS, X.BLACK

# ------------------------------------------------------------------ numbers (concept B1, sheet 2)
B, CAT, W = K.B, K.CAT, K.W                            # W 154: half width
TOP, STEP, CAB_TOP = B['hood_top'], B['step'], B['cab_top']          # 219.0, 198.8, 251.9
Z_BOT, Z_DECK = K.Z_BOT, K.Z_DECK                      # 105 (skirt bottom), 136 (T101 rib tops)
S0, S1 = CAT['slope']                                  # hood slope: X -73.6 at the top, -55.6 at the step
CWF = K.CWF                                            # -145: counterweight front face = T101 rear face
GAP = .3                                               # running gap between separate parts
XR = CWF + GAP                                         # rear faces of the halves
T_W, T_F = 2.0, 2.5                                    # shell wall, bay floor
FLOOR_TOP = Z_BOT + T_F                                # 107.5
Z_OVER = Z_DECK + GAP                                  # 136.3: lower edges of the hood over T101
Z_UNDER = Z_DECK - 1.0                                 # 135.0: deck under the ARM60 base edge (1 clear of it)
HOOD_FRONT = K.ARM_X[0] - 2.0                          # -23: hood front face, 2 behind the ARM60 base
CAB_Y = B['cab_y'][0]                                  # 84.95: cab inner face (ARM60 base edge at 82)
TANK_Y = B['tank_y'][0]                                # -91.3: tank and toolbox inner face
INNER = B['inner']                                     # 77: inner edge of the bay floors (T101 base plate at 69)
LEFT_FRONT, RIGHT_FRONT = B['left_front'], B['right_front']           # 92, 60
TANK_X = CAT['tank_x']                                 # -63.1, -30.4 (step), -12.5
TB_X = CAT['toolbox_x']                                # 18.1, 57.9
SEAM = .2                                              # visible seam on the centreline (right half stops at Y -0.2)
LAP = 6.0                                              # lap under the right half's skin
SLEEVE_X = T.BODY_SLEEVE_X                             # (-120, -45): on flat hood (top 219 and step 198.8)
SLEEVE_Y = sum(R3.RIB_Y)/2                             # 65: over the T101 ribs
SLEEVE_R, BORE_R, SLEEVE_FLOOR = 5.0, 3.2, 6.0
HOOK_X = (44.0, 56.0)
HOOK_Z = (100.5, R3.BASE_Z[0] - GAP)                   # tongue under the base plate (Z 103), above the swing envelope (Z 100)
HOOK_IN = R3.FR['y'] - 5.0                             # 64: 5 under the base-plate edge (Y 69)
SLIDE_OUT = 10.0
NOTCH = 14.0                                           # cable notch in the rear walls, |Y| < 14, Z to 154 (lead channel exit)
CW_CHANNEL = dict(x=(-165.0, CWF), y=12.0, z=(110.0, 152.0))
CW_BOLT_Y, CW_BOLT_Z = 40.0, T.CAN_Z                   # the T101 rear-bulkhead holes
CW_TOP_R, CW_BOT_CH = 8.0, 2.5                         # counterweight: rounded rear top edge, 45° chamfer at the bed
POCKET_FLOOR = Z_BOT + 3.0
SHOT_DENSITY = K.SHOT_DENSITY*1e-3                     # kg/cm3 -> 4.5e-6 kg/mm3 (poured steel shot)
INFILL = .15                                           # sparse infill of the solid blocks (gyroid)
SKIN = dict(B101=1.6, B102=1.2, B103=1.2, B104=1.2, B105=1.2, B106=1.2, B107=1.2)   # perimeters: 4 (B101) or 3 x 0.4
INSERT_M3, INSERT_M4 = X.INSERT_M3, X.INSERT_M4
M3_HEAD, M4_HEAD = T.M3_HEAD, X.M4_HEAD

# electronics (concept sheet 3); positions refined for the CAD
BOARD = dict(x=(-136.0, -40.0), y=(84.0, 148.0), z=(110.0, 111.6))
# main board rev A (controller/main_board): USB-C receptacle on the board's outboard edge, centred 1.6 above the board
# top (spec C1 B4: the slot moves down from Z 123.3, where a devkit on headers had it); plug overmolds to 14.4 x 8.4
USB = dict(x=-98.0, z=113.2, slot=(15.0, 9.0), r=3.0)
MAIN_BOARD_PARTS = X.ROOT / 'controller' / 'main_board' / 'X1_main_board_A_parts.json'   # written by check_pcb.py
PLUG_DEPTH = dict(XH=12.0, PH=10.0)    # mated JST plug and lead bend beyond a side-entry header's face (check envelope)
HEADER_FACE_Y = BOARD['y'][0] + 0.54   # 84.54: mating faces of the side-entry headers (KiCad's JST models, board_step.py)
BOARD_TOP_Z = BOARD['z'][0] + 1.51     # 111.51: the board top in the KiCad STEP
SWITCH = dict(c=(34.5, -104.5), cut=(19.0, 13.0), bezel=(21.2, 15.1), depth=18.9)   # KCD1-101 (Finglai drawing)
JACK = dict(y=-141.0, z=150.0, hole_r=4.1)             # 5.5 x 2.1 metal panel jack, M8 thread, 8 mm hole (DC-022B pattern)
FUSE_HOLDER = dict(x=30.0, y=-130.0, z0=138.0)         # Littelfuse MINI FHM in-line holder in the toolbox, leads along Y
FEED_SOCKET = (-100.0, -42.0, 166.0)                   # the mated XT30 pair of the battery feed, hanging in the hood cavity
BMS = dict(x=-110.0, z=205.0)                          # HX-3S-01 (50 x 16) taped to the +Y sled wall's outer face

# battery hatch B106 (rev B): the flat hood top between the rear face and the slope, on the centreline
HATCH_HY = 55.0                                        # opening half width (the sleeve bores are at |Y| 65)
Z_LEDGE = TOP - T_W                                    # 217.02: the hatch seats at the underside of the hood skin
HATCH_T = 3.0                                          # plate 217.0-220.0: 1 mm proud, as the Cat's raised engine hood (view 027)
LEDGE_W, LEDGE_T = 6.5, 4.0
MAGNET = dict(r=3.0, h=2.0, pocket_r=3.1, pocket_h=2.1,                 # Ø6 x 2 N52 discs, glued, 4 pairs
              xy=tuple((x, s*(HATCH_HY - LEDGE_W/2)) for x in (-137.0, -81.0) for s in (1, -1)))
SLED = dict(x=(-141.8, -78.2), y_in=38.9, t=1.6, z0=192.5, rib_y=20.0, standoff=4.0)
HOLDER = dict(l=77.05, w=20.65, h=14.86, pitch=21.0, xc=(-131.0, -110.0, -89.0), kg=.009)   # Keystone 1043 (drawing rev C; 8.8 g TME)
SNAP_LIP = dict(len=12.0, depth=1.0, h=0.8)             # the holders snap into the sled: lips under their end walls
CELL = dict(r=18.55/2, l=65.25, kg=.050)                # Samsung INR18650-35E datasheet maxima (Ø18.55, 65.25, 50 g)

# cab (rev B): glass openings traced in the drawing (glass1/2), the front render (windshield) and the rear view
DOOR_BAR = (184.2, 187.2)                              # door glass split at 57 % of the cab height (view 000)
WINDSHIELD = dict(y1=W - 5.0, z=(152.0, 244.0))        # open to the boom side: B104 carries the right front pillar
REAR_GLASS_Z0 = STEP + 4.2                             # the rear view hides the glass bottom behind the hood: taken 4 above the step
LAMP_Y = (146.0, 138.0)                                # 2 work lamps on the cab roof's front-left corner (views 000, 009)
CI_Y = (CAB_Y + GAP + .05, W - T_W - GAP)              # cab interior B104 between the open side and the left wall
SEAT_Y = sum(CI_Y)/2
CI_PEG_X = (8.0, 62.0)
HANDLE = dict(x=80.5, y=157.5, z=(158.0, 230.0), pegs=(165.0, 215.0), a=2.6)   # B107 on the front-left pillar (view 009)


def hood_top_at(x):
    if x <= S0:
        return TOP
    if x >= S1:
        return STEP
    return TOP + (STEP - TOP)*(x - S0)/(S1 - S0)


def band(P, t, open_bottom=False):
    """Wall band t thick inside the outline of XZ profile P; open_bottom: no wall along its bottom edge."""
    Q = P
    if open_bottom:
        x0, z0, x1, _ = P.bounds
        Q = P.union(sbox(x0, z0 - 10, x1, z0))
    return P.difference(Q.buffer(-t, join_style=2))


def yz_prism(poly, x0, x1):
    """Prism along X from a shapely polygon drawn in the YZ plane."""
    def wire(coords):
        return cq.Wire.makePolygon([cq.Vector(x0, py, pz) for py, pz in list(coords)[:-1]], close=True)
    face = cq.Face.makeFromWires(wire(poly.exterior.coords), [wire(h.coords) for h in poly.interiors])
    return cq.Workplane(obj=cq.Solid.extrudeLinear(face, cq.Vector(x1 - x0, 0, 0)))


def rod(p0, p1, r):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = p1 - p0
    return cq.Workplane(obj=cq.Solid.makeCylinder(r, float(np.linalg.norm(d)), cq.Vector(*p0), cq.Vector(*d)))


def ball(p, r):
    return cq.Workplane(obj=cq.Solid.makeSphere(r, cq.Vector(*p), angleDegrees1=-90, angleDegrees2=90))


def frustum(r0, z0, r1, z1):
    """Loft between two XY rectangles (x0, x1, y0, y1) at z0 and z1."""
    def wire(r, z):
        x0, x1, y0, y1 = r
        return cq.Wire.makePolygon([cq.Vector(x0, y0, z), cq.Vector(x1, y0, z), cq.Vector(x1, y1, z), cq.Vector(x0, y1, z)], close=True)
    return cq.Workplane(obj=cq.Solid.makeLoft([wire(r0, z0), wire(r1, z1)], True))


def rbox(x0, x1, y0, y1, z0, z1, r):
    return box(x0, x1, y0, y1, z0, z1).edges().fillet(r)


def polys(g):
    """The polygons of a shapely result (Polygon or MultiPolygon), slivers dropped."""
    return [p for p in getattr(g, 'geoms', [g]) if p.geom_type == 'Polygon' and p.area > .05]


def crosshatch(region, pitch=5.0, w=.8, avoid=(), avoid_r=3.0):
    """Anti-skid crosshatch (grooves at ±45°) inside a shapely region, kept clear of the posts in avoid."""
    x0, y0, x1, y1 = region.bounds
    L = (x1 - x0) + (y1 - y0)
    lines = []
    for k in np.arange(-L, L, pitch):
        lines += [LineString([(x0 + k, y0), (x0 + k + L, y0 + L)]), LineString([(x0 + k, y1), (x0 + k + L, y1 - L)])]
    g = unary_union([q.buffer(w/2, cap_style=2) for q in lines]).intersection(region)
    for p in avoid:
        g = g.difference(Point(p).buffer(avoid_r, 24))
    return polys(g)


def union_all(shapes):
    s = shapes[0]
    for q in shapes[1:]:
        s = s.union(q)
    return s


def fuse_all(shapes):
    """One fuse of every shape, then clean: chained unions cleaned at each step leave the operator figure invalid."""
    vals = [tp.one(q) for q in shapes]
    return cq.Workplane(obj=vals[0].fuse(*vals[1:]).clean())


def cut_all(s, shapes):
    """One cut with every tool fused first (a compound of overlapping tools would cut their overlaps twice)."""
    if not shapes:
        return s
    tools = [tp.one(q) for q in shapes]
    tool = tools[0].fuse(*tools[1:]) if len(tools) > 1 else tools[0]
    return s.cut(cq.Workplane(obj=tool))


def groove(line_pts, y_face, side, w=.8, depth=.6):
    """Seam groove along a polyline (XZ) in the outer face at y_face (side +1: face looks to +Y)."""
    g = LineString(line_pts).buffer(w/2, cap_style=2, join_style=2)
    y0, y1 = sorted([y_face - side*depth, y_face + side*1.0])
    return xz_prism(g, y0, y1)


def ring_groove(poly_pts, y_face, side, w=.8, depth=.6):
    g = Polygon(poly_pts).exterior.buffer(w/2, join_style=2)
    y0, y1 = sorted([y_face - side*depth, y_face + side*1.0])
    return xz_prism(g, y0, y1)


# ------------------------------------------------------------------ profiles (XZ)
def hood_in():
    """Inboard hood over T101 (both halves): flat top, the slope, the step, front face 2 behind the ARM60 base."""
    return Polygon([(XR, Z_OVER), (XR, TOP), (S0, TOP), (S1, STEP), (HOOD_FRONT, STEP), (HOOD_FRONT, Z_OVER)])


CAB = Polygon(K.xz([K.side_mm(p) for p in K.SIDE_PX['cab']]))


def left_outer():
    hood = Polygon([(CAT['cab_low_rear'], Z_DECK), (B['cab_x'][0], STEP), (S1, STEP), (S0, TOP), (XR, TOP), (XR, Z_DECK)])
    return hood.union(CAB).union(sbox(XR, Z_BOT, LEFT_FRONT, Z_DECK))


TANK = Polygon([(TANK_X[0], Z_DECK), (TANK_X[0], B['tank_top']), (TANK_X[1], B['tank_top']), (TANK_X[1], B['tank_step']),
                (TANK_X[2], B['tank_step']), (TANK_X[2], Z_DECK)])
TOOLBOX = Polygon([(TB_X[0], Z_DECK - .01), (TB_X[0], B['toolbox_top'] - 3), (TB_X[0] + 3, B['toolbox_top']),
                   (TB_X[1] - 3, B['toolbox_top']), (TB_X[1], B['toolbox_top'] - 3), (TB_X[1], Z_DECK - .01)])


def right_outer():
    return (sbox(XR, Z_DECK, TANK_X[0] + .01, TOP).union(TANK).union(sbox(XR, Z_BOT, RIGHT_FRONT, Z_DECK)).union(TOOLBOX))


# ------------------------------------------------------------------ shared features
def sleeve(x, side):
    """M3 sleeve over a rib: teardrop section (45° flanks toward the outer side, which prints down), a web out to the
    outer wall, a 6 mm floor on the rib top with a Ø3.4 hole, a Ø6.4 bore from the hood top for the head and the key."""
    y, zt = side*SLEEVE_Y, hood_top_at(x)
    r, k = SLEEVE_R, SLEEVE_R/math.sqrt(2)
    tear = Point(x, y).buffer(r, 48).union(Polygon([(x - k, y + side*k), (x, y + side*r*math.sqrt(2)), (x + k, y + side*k)]))
    s = xy_prism(tear, Z_DECK, zt - .5)
    yw = sorted([y + side*3.0, side*(W - T_W + .01)])
    s = s.union(box(x - T_W/2, x + T_W/2, yw[0], yw[1], Z_OVER, zt - .5))
    return s


def sleeve_cuts(x, side):
    y, zt = side*SLEEVE_Y, hood_top_at(x)
    return [zcyl(BORE_R, Z_DECK + SLEEVE_FLOOR, zt + 1, x, y), zcyl(1.7, Z_DECK - 1, Z_DECK + SLEEVE_FLOOR + .1, x, y)]


def hook(side):
    """Front hook: a tongue 5 under the T101 base-plate edge, hung from the bay floor's inner edge. Its outer face is
    45° so it grows out of the floor when the half prints on its side."""
    yz = [(HOOK_IN, HOOK_Z[0]), (HOOK_IN, HOOK_Z[1]), (INNER - 3, HOOK_Z[1]), (INNER - 3, FLOOR_TOP), (INNER + 3, FLOOR_TOP),
          (INNER + 3, Z_BOT), (INNER + 3 - (Z_BOT - HOOK_Z[0]), HOOK_Z[0])]
    return yz_prism(Polygon([(side*y, z) for y, z in yz]), *HOOK_X)


def bay_inner_strip(side, front):
    """The bay between the floor's inner edge (|Y| 77) and the cab or tank face: rear and front walls, the hood front
    wall carried down to the deck, and the deck in front of the hood from the outer wall in (it prints standing on the
    bed; Z 135.7 under the ARM60 base edge, |Y| < 82.5, then up to the deck line under the cab, tank and steps)."""
    yo = CAB_Y if side > 0 else TANK_Y
    y = sorted([side*INNER, yo])
    yd = sorted([side*(K.ARM_Y + .5), side*(W - T_W + .01)])
    ya = sorted([side*INNER, side*(K.ARM_Y + .51)])
    out = [box(XR, XR + T_W, *y, Z_BOT, Z_OVER + 1), box(front - T_W, front, *y, Z_BOT, Z_UNDER),
           box(HOOD_FRONT - T_W, front, *ya, Z_UNDER - T_W, Z_UNDER), box(HOOD_FRONT - T_W, front, *yd, Z_UNDER - T_W, Z_DECK)]
    yf = sorted([side*(R3.RIB_Y[1] + 1), yo])
    out.append(box(HOOD_FRONT - T_W, HOOD_FRONT, *yf, Z_UNDER - T_W, Z_OVER + 1))
    return out


HARNESS_NOTCH = dict(y=(38.0, 56.0), z_top=156.0)       # rev B issue 2: the arm harness rises through the hood's inboard front wall here


def common_cuts(side):
    """Cable notches: in the rear wall (and the lap) where the counterweight's lead channel comes out, and in the inboard
    hood's front wall where the four arm cables rise out of T101 behind the B01X plate (excavator_complete/WIRING.md).
    T101's rear bulkhead (X -38..-30) and the plate's rear edge (X -21) leave the wall (X -25..-23) in a 9 mm gap, so the
    cables need the wall's bottom edge raised to Z 156 over |Y| 38-56; nothing else of the half is there."""
    y = (-LAP - 1, NOTCH) if side > 0 else (-NOTCH, 0.0)
    hy = sorted([side * HARNESS_NOTCH['y'][0], side * HARNESS_NOTCH['y'][1]])
    return [box(XR - 1, XR + T_W + 2.5, *y, Z_OVER - 1, 154.0),
            box(HOOD_FRONT - T_W - 1, HOOD_FRONT + 1, *hy, Z_OVER - 1, HARNESS_NOTCH['z_top'])]


def hatch_frame(side):
    """(adds, cuts) for one half's share of the battery-hatch seat: the opening in the flat hood top (rear face to the
    slope), a 6.5 x 4 ledge along its side and front under the skin (the rear wall top is the rear ledge), magnet
    pockets in the side ledge, and the lap rings cleared where the battery sled hangs. Under the seam the left half's
    front ledge stops 1.3 short of the slope, which belongs to the right half there (0.4 clear of its inner face)."""
    hy, zl, zb = HATCH_HY, Z_LEDGE, Z_LEDGE - LEDGE_T
    ys = lambda a, b: sorted([side*a, side*b])
    adds = [box(XR + T_W - .01, S0 + 1.0, *ys(hy - LEDGE_W, hy + 3.0), zb, zl)]
    if side > 0:
        adds += [box(S0 - 4.0, S0 + 1.0, 0.0, hy + 3.0, zb, zl), box(S0 - 4.0, S0 - 1.3, -LAP, .01, zb, zl)]
        opening = box(XR - 1, S0, -LAP - 1, hy, zl, TOP + 1)
    else:
        adds += [box(S0 - 4.0, S0 + 1.0, -(hy + 3.0), -LAP - GAP, zb, zl)]
        opening = box(XR - 1, S0, -hy, 1.0, zl, TOP + 1)
    inner = hy - LEDGE_W
    cuts = [opening, box(XR + T_W, S0 - 4.0, -inner, inner, 188.0, TOP + 1)]
    cuts += [zcyl(MAGNET['pocket_r'], zl - MAGNET['pocket_h'], zl + 1, x, y) for x, y in MAGNET['xy'] if y*side > 0]
    return adds, cuts


def roof_lamps():
    """(adds, cuts): two work lamps on the cab roof's front-left corner, facing forward (views 000 and 009)."""
    zc = CAB_TOP + 3.2
    adds, cuts = [], []
    for y in LAMP_Y:
        adds += [box(72.0, 76.0, y - 1.2, y + 1.2, CAB_TOP - .01, CAB_TOP + 1.8), tp.xcyl(2.4, 71.5, 77.0, y, zc)]
        cuts.append(tp.xcyl(1.8, 76.6, 78.0, y, zc))
    return adds, cuts


# ------------------------------------------------------------------ B102 left half
def cab_inner():
    """The cab's inside in XZ, 0.3 clear of B102's 2 mm walls."""
    return CAB.buffer(-(T_W + GAP), join_style=2)


@lru_cache(None)
def left_half():
    A, P = hood_in(), left_outer()
    s = [xz_prism(P, W - T_W, W),                                         # outer wall
         xz_prism(band(P, T_W), CAB_Y, W - T_W + .01),                   # rear wall, hood skin, cab roof and front, bay floor
         xz_prism(band(CAB, T_W), CAB_Y, W - T_W + .01),                 # cab shell: roof, front, rear, slant and floor
         xz_prism(band(A, T_W, open_bottom=True), 0.0, CAB_Y + .01),     # inboard hood: skin, front and rear walls
         box(XR, LEFT_FRONT, INNER, W - .01, Z_BOT, FLOOR_TOP)]          # bay floor 2.5
    s += bay_inner_strip(1, LEFT_FRONT)
    def ring(t0, t1):
        return band(hood_in(), t1, open_bottom=True).difference(band(hood_in(), t0, open_bottom=True))
    s.append(xz_prism(ring(T_W + .15, T_W + 1.65), -LAP, LAP))          # lap under the right half's skin
    s.append(xz_prism(ring(T_W - .2, T_W + 1.65), 1.0, LAP))            # joined to the left skin on its own side
    s += [sleeve(x, 1) for x in SLEEVE_X] + [hook(1)]
    bx, by = BOARD['x'], BOARD['y']
    s += [zcyl(3.0, Z_BOT + 1, BOARD['z'][0], x, y) for x in (bx[0] + 4, bx[1] - 4) for y in (by[0] + 4, by[1] - 4)]
    s += [zcyl(1.45, Z_DECK + T_W - .01, Z_DECK + T_W + 1.0, x, SEAT_Y) for x in CI_PEG_X]   # pegs for B104
    hf_add, hf_cut = hatch_frame(1)
    la, lc = roof_lamps()
    s += hf_add + la
    body = union_all(s)
    cuts = common_cuts(1) + [c for x in SLEEVE_X for c in sleeve_cuts(x, 1)] + hf_cut + lc
    cuts += [tp.ycyl(1.1, W - T_W - 1, W + 1, HANDLE['x'], z) for z in HANDLE['pegs']]      # B107's pegs
    cuts += [zcyl(1.1, Z_BOT - 1, BOARD['z'][0] + .1, x, y) for x in (bx[0] + 4, bx[1] - 4) for y in (by[0] + 4, by[1] - 4)]
    # louvres: the Cat's cooling side, as vertical slits through the side wall (they vent the hood)
    for x0, x1, z0, z1 in K.SIDE_PX['louvres']:
        (a, za), (b, zb) = K.side_mm((x0, z0)), K.side_mm((x1, z1))
        za, zb = sorted([K.zmap(za), K.zmap(zb)])
        lo, hi = sorted([a, b])
        for xs in np.arange(lo + 1.8, hi - 2.6, 3.2):
            cuts.append(box(xs, xs + 1.4, W - T_W - .5, W + 1, za, zb))
    u = sbox(USB['x'] - USB['slot'][0]/2, USB['z'] - USB['slot'][1]/2, USB['x'] + USB['slot'][0]/2,
             USB['z'] + USB['slot'][1]/2).buffer(-USB['r']).buffer(USB['r'], 16)
    cuts.append(xz_prism(u, W - T_W - .5, W + 1))
    # seams and windows, 0.8 wide x 0.6 deep
    cuts.append(groove([(XR + 3, Z_DECK), (LEFT_FRONT - 3, Z_DECK)], W, 1))
    cuts.append(groove([(CAT['door_seam_left'], Z_DECK), (CAT['door_seam_left'], TOP - 2)], W, 1))
    (ga, za), (gb, zb) = (CAT['cab_low_rear'], Z_DECK), (B['cab_x'][0], STEP)
    k = 1.5/math.hypot(gb - ga, zb - za)                                 # stop short of the cab/step corner (no edge contact)
    cuts.append(groove([(ga, za), (gb - k*(gb - ga), zb - k*(zb - za))], W, 1))
    # glass cut out (rev B): door (upper and lower, split by the bar), rear side window, windshield, rear window
    wy = (W - T_W - .5, W + 1)
    g1 = Polygon(K.xz([K.side_mm(p) for p in K.SIDE_PX['glass1']]))
    for lo, hi in ((Z_DECK, DOOR_BAR[0]), (DOOR_BAR[1], CAB_TOP)):
        cuts += [xz_prism(p, *wy) for p in polys(g1.intersection(sbox(-100, lo, 200, hi)))]
    cuts.append(xz_prism(Polygon(K.xz([K.side_mm(p) for p in K.SIDE_PX['glass2']])), *wy))
    cuts.append(yz_prism(sbox(CAB_Y - 1, WINDSHIELD['z'][0], WINDSHIELD['y1'], WINDSHIELD['z'][1]), 60.0, 95.0))
    rg = [(K.ymap(K.rear_mm(p)[0]), K.zmap(K.rear_mm(p)[1])) for p in K.REAR_PX['glass']]
    ry0, ry1 = min(p[0] for p in rg), max(p[0] for p in rg)
    rz1 = max(p[1] for p in rg)
    cuts.append(yz_prism(sbox(ry0, REAR_GLASS_Z0, ry1, rz1), B['cab_x'][0] - 1, B['cab_x'][0] + T_W + 1))
    return cut_all(body, cuts).clean()


# ------------------------------------------------------------------ B103 right half
@lru_cache(None)
def tank_block():
    return xz_prism(TANK, -W, TANK_Y)


def tread_boxes():
    """(x_front, z_bottom, z_top) of the three traced treads (render 018): two on the tank front, one on the deck."""
    (t1, t2, t3) = [(K.photo_mm((x0, 0))[0], K.photo_mm((x1, 0))[0], K.zmap(K.photo_mm((0, y1))[1]), K.zmap(K.photo_mm((0, y0))[1]))
                    for x0, x1, y0, y1 in K.PHOTO_PX['treads']]
    return [(t1[1], t1[2], t1[3]), (t2[1], t2[2], t2[3]), (t3[1], Z_DECK - .5, Z_DECK + 1.2)]


TREAD_Y = (-W, -120.0)


def treads():
    return [box(TANK_X[2] - .5, xf, *TREAD_Y, z0, z1) for xf, z0, z1 in tread_boxes()]


def stair_frame():
    """Rev B: the stair housing as on the Cat (renders 009 and 018): a back panel against the tank front behind the
    treads, and a stringer along their inboard ends. The traced treads stack like a ladder (same depth), so they stay open;
    anti-skid grooves are cut in their exposed tops (stair_cuts)."""
    (x1, _, t1), _, (_, b3, _) = tread_boxes()
    x0 = TANK_X[2] - .5
    return [box(x0, STAIR_BACK, -W + .01, TREAD_Y[1], b3, t1),
            box(x0, x1, TREAD_Y[1] - .5, TREAD_Y[1] + STAIR_STRINGER, b3, t1)]


STAIR_BACK, STAIR_STRINGER = TANK_X[2] + 3.5, 2.0


def stair_cuts():
    out = []
    for xf, _, zt in tread_boxes():
        for xg in np.linspace(STAIR_BACK + 1.5, xf - 1.5, 3):
            out.append(box(xg - .4, xg + .4, -W + 2.0, TREAD_Y[1] - 1.5, zt - .5, zt + 1))
    return out


GRAB = dict(x=3.0, y=(-131.0, -97.0), top=228.0, r=1.5)     # the grab rail beside the stairs (front render 009, side 018)


def grab_rail():
    x, (ya, yb), zt, r = GRAB['x'], GRAB['y'], GRAB['top'], GRAB['r']
    z0 = Z_DECK - .5
    return [rod((x, ya, z0), (x, ya, zt), r), rod((x, yb, z0), (x, yb, zt), r), rod((x, ya, zt), (x, yb, zt), r),
            ball((x, ya, zt), 1.2*r), ball((x, yb, zt), 1.2*r)]


MIRROR_R = dict(pole=(-57.0, -122.0), top=247.0, elbow=(-136.0, 241.5), head=(-145.0, -133.0, 229.5, 241.5))   # rear view 027


def right_mirror():
    """The right mirror on its pole at the guardrail's rear (renders 018 and 027): pole, arm out and down, mirror."""
    (px, py), zt = MIRROR_R['pole'], MIRROR_R['top']
    ey, ez = MIRROR_R['elbow']
    y0, y1, z0, z1 = MIRROR_R['head']
    return [rod((px, py, B['tank_top'] - .5), (px, py, zt), 1.5), ball((px, py, zt), 1.8),
            rod((px, py, zt), (px, ey, ez), 1.2), ball((px, ey, ez), 1.5), box(px - 1.5, px + 1.5, y0, y1, z0, z1)]


TB_LAMP = dict(y=-100.0, z=143.0, r=3.0)                     # lamp low on the toolbox front, inboard side (render 009)


def tank_antiskid():
    """Crosshatch on the tank top and its front step (render 018 shows textured walkways), clear of the posts."""
    feet = [(TANK_X[0] + 1.5, y) for y in K.RAIL_Y] + [(-40.7, y) for y in K.RAIL_Y] + [MIRROR_R['pole']]
    top = crosshatch(sbox(TANK_X[0] + 3.0, -W + 3.5, TANK_X[1] - 3.0, TANK_Y - 4.0), avoid=feet)
    step = crosshatch(sbox(TANK_X[1] + 1.0, -W + 3.5, TANK_X[2] - 1.5, TANK_Y - 4.0))
    zt, zs = B['tank_top'], B['tank_step']
    return [xy_prism(p, zt - .4, zt + 1) for p in top] + [xy_prism(p, zs - .4, zs + 1) for p in step]


def handrail(r=1.5):
    """Guardrail on the tank top: traced in the render (rear post X -63.1, top 249, front leg toward the steps) and the
    rear view (rails at Y -110.9 and -142.8)."""
    xr, xf, zt = TANK_X[0] + r, CAT['rail_x'][1], B['rail_top']
    rail = K.xz([K.photo_mm(p) for p in K.PHOTO_PX['rail']])
    (fx0, fz0), (fx1, fz1) = rail[2], rail[3]
    zb = B['tank_top'] - 1.0
    xb = fx0 + (fx1 - fx0)*(zt - zb)/(fz0 - fz1)
    ys = K.RAIL_Y
    s = []
    for y in ys:
        s += [rod((xr, y, zb), (xr, y, zt), r), rod((xr, y, zt), (xf, y, zt), r), rod((xf, y, zt), (xb, y, zb), r),
              ball((xr, y, zt), 1.2*r), ball((xf, y, zt), 1.2*r)]
    for x in (xr, xf):
        s.append(rod((x, ys[0], zt), (x, ys[1], zt), r))
    return s


@lru_cache(None)
def right_half():
    A, P = hood_in(), right_outer()
    s = [xz_prism(P, -W, -W + T_W),
         xz_prism(band(P, T_W), TANK_Y, -W + T_W - .01),                 # into the outer wall
         tank_block(),
         xz_prism(TOOLBOX, TANK_Y - T_W, TANK_Y + .01).cut(box(TB_X[0] - 1, TB_X[1] + 1, TANK_Y - 3, TANK_Y + 1, Z_BOT, Z_DECK)),
         xz_prism(band(A, T_W, open_bottom=True), TANK_Y - .01, -SEAM),
         box(XR, RIGHT_FRONT, -W + .01, -INNER, Z_BOT, FLOOR_TOP)]
    s += bay_inner_strip(-1, RIGHT_FRONT)
    s += treads() + stair_frame() + handrail() + grab_rail() + right_mirror()
    s.append(tp.xcyl(TB_LAMP['r'], TB_X[1] - .01, TB_X[1] + 1.5, TB_LAMP['y'], TB_LAMP['z']))
    ex, er = K.EXHAUST
    s.append(zcyl(er, TOP - 1, B['exhaust_top'], *ex))
    s += [sleeve(x, -1) for x in SLEEVE_X] + [hook(-1)]
    hf_add, hf_cut = hatch_frame(-1)
    s += hf_add
    body = union_all(s)
    cuts = common_cuts(-1) + [c for x in SLEEVE_X for c in sleeve_cuts(x, -1)] + hf_cut + stair_cuts() + tank_antiskid()
    cuts.append(tp.xcyl(TB_LAMP['r'] - .8, TB_X[1] + 1.1, TB_X[1] + 2.0, TB_LAMP['y'], TB_LAMP['z']))
    cuts.append(zcyl(er - 1.6, B['exhaust_top'] - 6, B['exhaust_top'] + 1, *ex))
    sx, sy = SWITCH['c']
    cuts.append(box(sx - SWITCH['cut'][0]/2, sx + SWITCH['cut'][0]/2, sy - SWITCH['cut'][1]/2, sy + SWITCH['cut'][1]/2,
                    B['toolbox_top'] - 4, B['toolbox_top'] + 1))
    cuts.append(tp.xcyl(JACK['hole_r'], TB_X[1] - 3, TB_X[1] + 1, JACK['y'], JACK['z']))
    cuts.append(zcyl(6.0, Z_UNDER - T_W - 1, Z_DECK + 1, sum(TB_X)/2, -122.0))              # wires up into the toolbox
    fd = K.xz(CAT['front_door'])
    cuts.append(groove([(XR + 3, Z_DECK), (RIGHT_FRONT - 3, Z_DECK)], -W, -1))
    cuts.append(groove([(CAT['door_seam_right'], Z_DECK), (CAT['door_seam_right'], TOP - 2)], -W, -1))
    cuts.append(groove(fd[1:] + [(fd[-1][0], Z_DECK)], -W, -1))
    cuts.append(groove([(TB_X[0] + 1, B['toolbox_top'] - 5), (TB_X[1] - 1, B['toolbox_top'] - 5)], -W, -1))
    return cut_all(body, cuts).clean()


# ------------------------------------------------------------------ B101 counterweight
def cw_plan(d=0.0, n=28):
    """Concept cw_plan (the Cat's tail arc R 188.7 split on the centreline, the halves moved out by DY) moved in by d on
    the sides and the rear; the front face X -145 stays."""
    R, yw = K.TAIL - d, W - d
    a0 = math.pi - math.asin((yw - K.DY)/R)
    left = [(R*math.cos(t), K.DY + R*math.sin(t)) for t in np.linspace(a0, math.pi, n)]
    right = [(x, -y) for x, y in reversed(left)]
    return [(CWF, yw)] + left + right + [(CWF, -yw)]


def pocket_poly():
    """Shot pocket: the plan 3 in from every face, less the lead channel (3 walls) and the two M4 insert bosses."""
    g = Polygon(cw_plan()).buffer(-3.0, join_style=2)
    ch = CW_CHANNEL
    g = g.difference(sbox(ch['x'][0] - 3, -ch['y'] - 3, CWF + 1, ch['y'] + 3))
    for s in (1, -1):
        g = g.difference(sbox(CWF - 14, s*CW_BOLT_Y - 7.5, CWF + 1, s*CW_BOLT_Y + 7.5))
    return g


@lru_cache(None)
def cw_outer():
    secs = [(Z_BOT, CW_BOT_CH), (Z_BOT + CW_BOT_CH, 0.0), (TOP - CW_TOP_R, 0.0)]
    secs += [(TOP - CW_TOP_R + CW_TOP_R*math.sin(math.radians(a)), CW_TOP_R*(1 - math.cos(math.radians(a)))) for a in range(15, 91, 15)]
    wires = [cq.Wire.makePolygon([cq.Vector(x, y, z) for x, y in cw_plan(d)], close=True) for z, d in secs]
    return cq.Workplane(obj=cq.Solid.makeLoft(wires, True))


CAMERA = dict(x=-K.TAIL, y=5.0, z=(200.0, 206.5), out=2.0)   # rear-view camera, top centre of the rear face (view 027)


def pocket_sides():
    """The shot pocket split on the centreline: (left, right) lists of polygons. Rev B gives each side its own floor
    height, so the shot trims the lateral balance as well as the fore-aft one (build_body.py mass solves both)."""
    g = pocket_poly()
    return polys(g.intersection(sbox(-400, 0, 0, 400))), polys(g.intersection(sbox(-400, -400, 0, 0)))


def shot_prisms(fill_z, floors):
    return [xy_prism(p, f, fill_z) for side, f in zip(pocket_sides(), floors) for p in side]


@lru_cache(None)
def counterweight(fill_z, floors=(POCKET_FLOOR, POCKET_FLOOR)):
    c = CAMERA
    x0, (z0, z1) = c['x'], c['z']
    cam = xz_prism(Polygon([(x0 + .5, z0), (x0 + .5, z1), (x0 - c['out'], z1), (x0 - c['out'], z0 + c['out'] + .5)]), -c['y'], c['y'])
    s = cw_outer().union(cam)                                           # 45° underside: prints without support
    cuts = shot_prisms(fill_z, floors)
    cuts += [tp.xcyl(.8, x0 - c['out'] - 1, x0 - c['out'] + .6, y, z1 - 2.0) for y in (-2.2, 2.2)]
    ch = CW_CHANNEL
    cuts.append(box(*ch['x'], -ch['y'], ch['y'], *ch['z']))
    cuts += [tp.xcyl(INSERT_M4['r'], CWF - INSERT_M4['length'] - 2, CWF + 1, s_*CW_BOLT_Y, CW_BOLT_Z) for s_ in (1, -1)]
    plan = Polygon(cw_plan())
    for x0, x1, y0, y1 in K.REAR_PX['lamps']:
        (ya, za), (yb, zb) = K.rear_mm((x0, y0)), K.rear_mm((x1, y1))
        ya, yb = sorted([K.ymap(ya), K.ymap(yb)]); za, zb = sorted([K.zmap(za), K.zmap(zb)])
        lamp = xy_prism(plan, za, zb).cut(xy_prism(plan.buffer(-.8, join_style=2), za - 1, zb + 1))
        cuts.append(lamp.intersect(box(-200, CWF - 8, ya, yb, za, zb)))
    return cut_all(s, cuts).clean()


def shot(fill_z, floors=(POCKET_FLOOR, POCKET_FLOOR)):
    return union_all(shot_prisms(fill_z, floors))


# ------------------------------------------------------------------ B104 cab interior, B105 operator (rev B)
@lru_cache(None)
def cab_interior():
    """Seat, joystick consoles, travel levers and pedals, monitor, and the cab's right front pillar and sill (B102's cab
    is open on the boom side so that it prints without supports). It slides in from the boom side, 2.1 up, and drops
    onto 2 pegs in the cab floor. Printed upright on its floor plate."""
    CI, (y0, y1), yc = cab_inner(), CI_Y, SEAT_Y
    zf = Z_DECK + T_W                                                    # 138: top of B102's cab floor
    za, zb = zf + .4, zf + 1.2                                           # floor plate (mat): its ends follow the cab's
    (a0, _, a1, _), (b0, _, b1, _) = (CI.intersection(sbox(-60, z - .01, 120, z + .01)).bounds for z in (za, zb))
    xe = lambda a, b_, z: a + (b_ - a)*(z - za)/(zb - za)               # sloping rear-lower and front walls, 0.3 clear
    plate = Polygon([(xe(a0, b0, zf), zf), (xe(a1, b1, zf), zf), (b1, zb), (b0, zb)])
    s = [xz_prism(plate, y0, y1)]
    ring = CI.difference(CI.buffer(-4.0, join_style=2))
    frame = ring.intersection(sbox(55.0, 0, 120, 245.0)).union(ring.intersection(sbox(-60, 0, 120, zf + GAP + 4.0)))
    s += [xz_prism(p, y0, y0 + 3.0) for p in polys(frame)]              # right front pillar and sill
    zp = zf + 1.19
    s += [box(18.0, 44.0, yc - 12.5, yc + 12.5, zp, 157.0),            # seat pedestal, 45° flare, cushion, backrest, headrest
          frustum((18.0, 44.0, yc - 12.5, yc + 12.5), 157.0 - .01, (15.0, 47.0, yc - 16.0, yc + 16.0), 160.5),
          box(15.0, 47.0, yc - 16.0, yc + 16.0, 160.49, 164.5),
          xz_prism(Polygon([(15.0, 164.4), (21.0, 164.4), (16.5, 206.0), (10.5, 206.0)]), yc - 15.0, yc + 15.0),
          box(10.0, 15.5, yc - 8.5, yc + 8.5, 205.5, 219.0)]
    for sg in (1, -1):                                                   # consoles with armrests and joysticks
        y = yc + sg*24.0
        s += [box(22.0, 56.0, y - 6.0, y + 6.0, zp, 160.0), box(24.0, 47.0, y - 5.5, y + 5.5, 159.99, 163.0),
              rod((51.0, y, 159.9), (51.0, y, 171.0), 1.2), ball((51.0, y, 173.0), 2.6)]
    s.append(box(68.0, 80.0, yc - 14.5, yc + 14.5, zp, 143.0))         # pedal block and the two travel levers
    for dy in (-1.5, 1.5):
        s += [rod((75.0, yc + dy, 142.9), (70.0, yc + dy, 162.0), .9), ball((70.0, yc + dy, 162.0), 1.7)]
    s += [rod((56.0, yc - 24.0, 159.9), (60.0, yc - 24.0, 178.0), 1.2), box(59.0, 62.0, yc - 29.0, yc - 15.0, 177.0, 189.0)]
    cuts = [zcyl(1.65, zf - .1, zf + 1.3, x, yc) for x in CI_PEG_X] + [zcyl(1.6, 160.9, 165.0, 30.0, yc)]
    return cut_all(union_all(s), cuts).clean()


@lru_cache(None)
def operator():
    """A seated operator at 1:15 (1.75 m), hard hat, hands on the joysticks, feet on the pedals; a peg into the seat."""
    yc, zs = SEAT_Y, 164.5
    s = [rbox(22.0, 42.0, yc - 11.5, yc + 11.5, zs, 174.0, 3.0)]        # pelvis on the cushion
    for sg in (1, -1):
        yl = yc + sg*8.0
        s += [rod((36.0, yl, zs + 5.0), (58.5, yl, zs + 5.0), 5.0), ball((59.0, yl, zs + 5.0), 5.5),      # thigh, knee
              rod((59.0, yl, zs + 4.0), (71.0, yl, 147.5), 4.0), box(66.0, 80.0, yl - 4.0, yl + 4.0, 143.0, 148.0)]
        sh, el, ha = (26.0, yc + sg*14.0, 200.5), (37.0, yc + sg*18.0, 181.0), (45.5, yc + sg*24.0, 176.5)
        s += [ball(sh, 4.2), rod(sh, el, 3.4), ball(el, 3.8), rod(el, ha, 3.0), ball(ha, 3.3)]   # joints 1.1 r: no tangent unions
    s.append(frustum((24.0, 40.0, yc - 12.5, yc + 12.5), 172.0, (19.0, 33.0, yc - 14.0, yc + 14.0), 203.0))   # torso
    s += [rod((26.0, yc, 202.0), (26.5, yc, 210.5), 3.5), ball((27.0, yc, 216.0), 7.5)]                    # neck, head
    s.append(ball((27.0, yc, 217.0), 8.2).intersect(box(10, 45, yc - 10, yc + 10, 215.8, 230)))            # hard hat
    s.append(rod((30.0, yc, 161.3), (30.0, yc, zs + .5), 1.4))                                             # peg
    return fuse_all(s)


# ------------------------------------------------------------------ B106 battery hatch, B107 left handrail (rev B)
@lru_cache(None)
def hatch():
    """The Cat's raised engine hood (rear view 027), 1 mm proud of the hood top, as a lift-off hatch carrying the battery:
    2 side walls and 2 standoff ribs under the plate; the 3 Keystone 1043 holders press up between the walls against the
    ribs and snap behind lips on the walls, cells facing down; the BMS is taped to a wall. Lift it off (4 magnet pairs),
    turn it over, change the cells. Printed upside down."""
    hy, zl = HATCH_HY - GAP, Z_LEDGE
    s = [box(XR, S0 - GAP, -hy, hy, zl, zl + HATCH_T).edges('>Z').chamfer(.6)]
    x0, x1 = SLED['x']
    hx0, hx1 = HOLDER['xc'][0] - HOLDER['w']/2, HOLDER['xc'][-1] + HOLDER['w']/2
    z_lip = zl - SLED['standoff'] - HOLDER['h']                      # 198.16: the holders' open edge (inverted)
    for sg in (1, -1):
        s.append(box(x0, x1, *sorted([sg*SLED['y_in'], sg*(SLED['y_in'] + SLED['t'])]), SLED['z0'], zl + .01))
        s.append(box(hx0, hx1, sg*SLED['rib_y'] - 1.5, sg*SLED['rib_y'] + 1.5, zl - SLED['standoff'], zl + .01))
        for xc in HOLDER['xc']:                                             # snap lips: 12 long, 1.0 in, 0.8 thick, chamfered lead-in
            y_in = sg*(SLED['y_in'] - SNAP_LIP['depth'])
            lip = box(xc - SNAP_LIP['len']/2, xc + SNAP_LIP['len']/2, *sorted([y_in, sg*(SLED['y_in'] + .01)]), z_lip - SNAP_LIP['h'], z_lip)
            s.append(lip.edges('<Z').edges('>Y' if sg < 0 else '<Y').chamfer(SNAP_LIP['h'] - .1))
    cuts = [zcyl(MAGNET['pocket_r'], zl - .01, zl + MAGNET['pocket_h'], x, y) for x, y in MAGNET['xy']]
    cuts.append(box(XR - 1, XR + 6.0, -9.0, 9.0, zl + 1.5, zl + HATCH_T + 1))                # finger notch at the rear edge
    return cut_all(union_all(s), cuts).clean()


@lru_cache(None)
def handle_mirror():
    """Grab handle on the cab's front-left pillar with the left mirror on top of it (front view 009, rear view 027).
    It stands off the cab side, so it is a separate small print; 2 pegs into Ø2.2 holes in the cab wall."""
    x, y, (z0, z1), a = HANDLE['x'], HANDLE['y'], HANDLE['z'], HANDLE['a']/2
    s = [box(x - a, x + a, y - a, y + a, z0, z1)]
    s += [tp.ycyl(1.0, W - T_W + .3, y - a + .01, x, z) for z in HANDLE['pegs']]
    s += [box(x - a, x + a, y - a, 161.01, z1 - 3.0, z1), box(x - 1.5, x + 1.5, 161.0, 169.0, 213.0, z1)]
    return union_all(s).clean()


# ------------------------------------------------------------------ bought parts
def board_kg():
    return dict(pcb=.022, ics=.010, passives=.003, module=.003, jst=.003, usb=.001, xt30=.002, xt30_pins=.0005)


def main_board():
    """The main board rev A as KiCad exported it (board_step.py: the PCB and every part's 3D model, in colour groups)
    and the mated harness plugs of its inboard side-entry headers (stdparts: JST XHP-2 / XHP-4 / PHR-3 drawn from the
    JST catalogue), each with 4 mm of its wires. J109 (expansion) stays empty. The interference checks use the parts'
    courtyard boxes (X1_main_board_A_parts.json) and the old 12 / 10 mm plug envelopes, not the detailed solids."""
    import json
    d = json.loads(MAIN_BOARD_PARTS.read_text())
    assert d['board'] == dict(x=list(BOARD['x']), y=list(BOARD['y']), z=list(BOARD['z'])), 'main board outline moved'
    court = {p['ref']: box(*p['x'], *p['y'], *p['z']) for p in d['parts']}
    e = {}
    for g, (s, c, refs) in BS.machine_groups().items():
        name = 'controller_PCB' if g == 'pcb' else ('board_parts' if g == 'ics' else f'board_parts_{g}')
        env = box(*BOARD['x'], *BOARD['y'], *BOARD['z']) if g == 'pcb' else _union([court[r] for r in refs if r in court])
        e[name] = (s, PCB_C if g == 'pcb' else c, board_kg()[g], env)
    plugs, env, wires = [], [], {}
    for p in d['parts']:
        kind = p['value'][:2] if p['value'].startswith(('XH ', 'PH ')) else None      # JST XH / PH headers
        if kind and abs(p['y'][0] - BOARD['y'][0]) < 0.5 and p['ref'] != 'J109':     # side-entry, face on the inboard edge
            n = int(p['value'].split()[1][0])
            xc = sum(p['x']) / 2
            parts = SP.xh_housing(n, wire_len=4.0) if kind == 'XH' else SP.ph_housing(n, wire_len=4.0)
            for nm, s, c in SP.place(parts, (xc, HEADER_FACE_Y, BOARD_TOP_Z)):
                (plugs if nm == 'housing' else wires.setdefault(c, [])).append(s)
            env.append(box(*p['x'], BOARD['y'][0] - PLUG_DEPTH[kind], BOARD['y'][0], *p['z']))
    e['board_plugs'] = (_union(plugs), SP.NYLON_WHITE, .002 * len(plugs), _union(env))
    cname = {SP.RED: 'red', SP.BLACK_WIRE: 'black', (.9, .5, .1): 'orange', (.5, .2, .6): 'purple'}
    for c, lst in wires.items():
        e[f'board_plugs_wires_{cname[c]}'] = (_union(lst), c, 0.0, _union(env))
    return e


def _union(shapes):
    out = shapes[0]
    for s in shapes[1:]:
        out = out.union(s)
    return out


def electronics():
    """Bought electronics: the battery pack on the hatch (3 x Keystone 1043 holders with INR18650-35E cells, the HX-3S-01
    BMS, the XT30U-F hatch lead mated to the XT30U-M feed socket), the main board with its mated plugs in the left bay,
    and the KCD1-101 switch, the MINI FHM fuse holder and the 5.5 x 2.1 panel jack in the toolbox. Every bought shape
    comes from stdparts.py (the makers' drawings) or the board's STEP. name -> (shape, colour, kg[, check envelope])."""
    e = {}
    zt = Z_LEDGE - SLED['standoff']                      # the holders' base (they hang inverted) against the standoff ribs
    zc = zt - SP.K1043['base'] - SP.K1043['cell_d'] / 2 - .15
    for i, xc in enumerate(HOLDER['xc']):
        flip = [((1, 0, 0), 180)] + ([((0, 0, 1), 180)] if i % 2 else [])   # open side down; every other one turned round (series)
        for n, s, c in SP.place(SP.keystone_1043(), (xc, 0.0, zt), rot=flip):
            e[f'holder_1043_{i}' + ('' if n == 'cradle' else '_' + n)] = (s, c, HOLDER['kg'] if n == 'cradle' else 0.0)
        cell = SP.place(SP.cell_18650(), (0.0, SP.K1043['cell_y'], 0.0))            # against the holder's + dimple
        for n, s, c in SP.place(cell, (xc, 0.0, zc), rot=flip):                       # turned with its holder
            e[f'cell_18650_{i}' + ('' if n == 'wrap' else '_' + n)] = (s, c, CELL['kg'] if n == 'wrap' else 0.0)
    yo = SLED['y_in'] + SLED['t']
    for n, s, c in SP.place(SP.bms_hx3s01(), (BMS['x'], yo, BMS['z']), rot=[((1, 0, 0), -90)]):
        e['battery_BMS_HX3S01' + ('' if n == 'pcb' else '_' + n)] = (s, c, .004 if n == 'pcb' else 0.0)
    # the feed pair: the hatch lead's XT30U-F (nose down) in the feed's XT30U-M (mouth up), hanging in the hood cavity
    for n, s, c in SP.place(SP.xt30u_f(wire_len=4.0), FEED_SOCKET, rot=[((0, 1, 0), -90)]):
        e['battery_lead_XT30' + ('' if n == 'housing' else '_' + n)] = (s, c, .003 if n == 'housing' else 0.0)
    for n, s, c in SP.place(SP.xt30u_m(wire_len=4.0), FEED_SOCKET, rot=[((0, 1, 0), -90)]):
        e['feed_socket_XT30' + ('' if n == 'housing' else '_' + n)] = (s, c, .003 if n == 'housing' else 0.0)
    e.update(main_board())
    sx, sy = SWITCH['c']
    for n, s, c in SP.place(SP.kcd1_101(), (sx, sy, B['toolbox_top'])):
        e['main_switch' + ('' if n == 'bezel' else '_' + n)] = (s, c, .006 if n == 'bezel' else 0.0)
    for n, s, c in SP.place(SP.dc_jack_5521(T_W), (TB_X[1], JACK['y'], JACK['z'])):
        e['charge_jack' + ('' if n == 'barrel' else '_' + n)] = (s, c, .006 if n == 'barrel' else 0.0)
    f = FUSE_HOLDER
    for n, s, c in SP.place(SP.fuse_holder_mini(lead_len=3.0), (f['x'], f['y'], f['z0'])):
        e['fuse_holder_5A' + ('' if n == 'body' else '_' + n)] = (s, c, .012 if n == 'body' else 0.0)
    return e


def hardware():
    """Screws and inserts. name -> (shape, colour, material)."""
    h = {}
    for i, (x, sy) in enumerate([(x, sy) for sy in (1, -1) for x in SLEEVE_X]):
        y = sy*SLEEVE_Y
        h[f'rib_insert_M3_{i}'] = (zring(INSERT_M3['r'], 1.5, Z_DECK - INSERT_M3['length'], Z_DECK, x, y), BRASS, 'brass')
        h[f'sleeve_screw_M3x12_{i}'] = (X.screw_z(1.5, M3_HEAD, Z_DECK + SLEEVE_FLOOR, 12.0, x, y, -1), BLACK, 'steel')
    rb = R3.REAR_BULK
    for i, sy in enumerate((1, -1)):
        y = sy*CW_BOLT_Y
        h[f'cw_insert_M4_{i}'] = (tp.xring(INSERT_M4['r'], 2.0, CWF - INSERT_M4['length'], CWF, y, CW_BOLT_Z), BRASS, 'brass')
        h[f'cw_screw_M4x12_{i}'] = (tp.xcyl(2.0, rb[1] - 12.0, rb[1], y, CW_BOLT_Z)
                                    .union(tp.xcyl(M4_HEAD['r'], rb[1], rb[1] + M4_HEAD['h'], y, CW_BOLT_Z)), BLACK, 'steel')
    for i, (x, y) in enumerate(MAGNET['xy']):                   # NdFeB 7.5 g/cm3, taken as steel
        h[f'hatch_magnet_{i}'] = (zcyl(MAGNET['r'], Z_LEDGE, Z_LEDGE + MAGNET['h'], x, y), MAG_C, 'steel')
        h[f'ledge_magnet_{i}'] = (zcyl(MAGNET['r'], Z_LEDGE - MAGNET['h'], Z_LEDGE, x, y), MAG_C, 'steel')
    return h


PRINTED = {   # name: (material and settings, print orientation (axis, deg, note), note)
    'B101_counterweight': ('PETG, 4 perimeters, 15 % gyroid; pause at the pocket rim and pour the shot',
                           ((0, 0, 1), 45, 'upright on its bottom face, turned 45° on the bed'),
                           'Cat 320 counterweight. Steel-shot pocket (filled in a print pause), lead channel from the T101 '
                           'window up to the hood, 2 x M4 inserts in the front face, rear lamp recesses, rear-view camera.'),
    'B102_left_half': ('PETG, 3 perimeters, 15 % gyroid (2 mm walls print solid)',
                       ((1, 0, 0), -90, 'on its outer (left) side face'),
                       'Cab as an open-glass shell (door, rear side, windshield and rear window cut through; open on the '
                       'boom side), 2 roof lamps, left hood half with the louvres, left skirt and bay (controller board on 4 '
                       'bosses); hatch seat with 2 magnets; 2 sleeves and a front hook; lap under the right half; USB slot.'),
    'B103_right_half': ('PETG, 3 perimeters, 15 % gyroid (the tank is solid with infill); tree supports under the '
                        'guardrail, grab rail and mirror',
                        ((1, 0, 0), 90, 'on its outer (right) side face'),
                        'Right hood half, doors, tank with anti-skid tops, stairs (3 grooved treads on a back panel and a stringer), guardrail, grab '
                        'rail, right mirror, toolbox (switch, fuse, charge jack, lamp), exhaust, right skirt and bay; hatch '
                        'seat with 2 magnets; 2 sleeves and a front hook.'),
    'B104_cab_interior': ('PETG (dark grey), 3 perimeters, 15 % gyroid', ((0, 0, 1), 0, 'upright on its floor plate'),
                          'Seat, 2 joystick consoles, travel levers and pedals, monitor, right front pillar and sill. '
                          'Drops onto 2 pegs in the cab floor (a drop of glue if loose).'),
    'B105_operator': ('PETG or PLA (orange), 3 perimeters, 15 % gyroid; tree supports under the thighs, arms and chin',
                      ((0, 0, 1), 0, 'upright on its feet'), 'Seated operator in a hard hat; a peg into the seat.'),
    'B106_battery_hatch': ('PETG, 3 perimeters, 15 % gyroid', ((1, 0, 0), 180, 'upside down: the hatch top on the bed'),
                           "The Cat's raised engine hood, as a lift-off hatch carrying the battery: 3 Keystone 1043 holders "
                           'snapped between the sled walls against 2 standoff ribs (cells facing down), the HX-3S-01 BMS taped '
                           'to the +Y wall, the XT30U-F lead, 4 magnets.'),
    'B107_left_handrail': ('PETG (black), 100 % infill', ((0, 1, 0), 90, 'flat on its side'),
                           "Grab handle on the cab's front-left pillar with the left mirror; 2 pegs into the cab wall."),
}
PRINT_COLOURS = dict(B101_counterweight=CW_C, B102_left_half=BODY_C, B103_right_half=BODY_C, B104_cab_interior=CABIN_C,
                     B105_operator=OPER_C, B106_battery_hatch=BODY_C, B107_left_handrail=TRIM_C)
PRINT_SHAPES = dict(B102_left_half=left_half, B103_right_half=right_half, B104_cab_interior=cab_interior,
                    B105_operator=operator, B106_battery_hatch=hatch, B107_left_handrail=handle_mirror)


def body_parts(fill_z, swing_deg=0.0, floors=(POCKET_FLOOR, POCKET_FLOOR)):
    """Every body solid in the vehicle frame at swing 0 (or turned with the upper). group 'body'."""
    out = {}
    def add(n, s, color, kind, kg=None, mat=None, part=None, envelope=None):
        if swing_deg:
            s = s.rotate((0, 0, 0), (0, 0, 1), swing_deg)
            envelope = None if envelope is None else envelope.rotate((0, 0, 0), (0, 0, 1), swing_deg)
        out[n] = dict(shape=s, color=color, group='body', kind=kind, source=part or n, kg=kg, material=mat)
        if envelope is not None:
            out[n]['envelope'] = envelope                 # what the interference checks use instead of the detailed shape
    add('B101_counterweight', counterweight(fill_z, floors), CW_C, 'printed')
    for n, f in PRINT_SHAPES.items():
        add(n, f(), PRINT_COLOURS[n], 'printed')
    add('ballast_steel_shot', shot(fill_z, floors), SHOT_C, 'ballast')
    for n, v in electronics().items():
        add(n, v[0], v[1], 'electronics', kg=v[2], envelope=v[3] if len(v) > 3 else None)
    for n, (s, c, m) in hardware().items():
        add(n, s, c, 'hardware', mat=m)
    return out


def half_of(n):
    """What a part travels with when the body comes apart: 'hatch' (off first), 'left' or 'right' (a half), or None."""
    if n.startswith(('cell_', 'holder_', 'battery_', 'hatch_magnet')) or n == 'B106_battery_hatch':
        return 'hatch'
    if n.startswith('ledge_magnet'):
        return 'left' if MAGNET['xy'][int(n.split('_')[-1])][1] > 0 else 'right'
    if n.startswith(('main_switch', 'fuse', 'charge_jack', 'feed_socket')) or n == 'B103_right_half':
        return 'right'
    if n.startswith(('controller', 'board_', 'B102', 'B104', 'B105', 'B107')):
        return 'left'
    return None

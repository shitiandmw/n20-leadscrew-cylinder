"""X1 turntable, concept R3: the anti-sway structure. Detailed design drawings; issue 3 matches the CAD in ../../source/x1_turntable.py.

R3 adds what the user approved after the sway discussion (2026-11-03), with NO custom metal parts (no machined plates, rings
or sleeves); only bought standard hardware (screws, nuts, washers, heat-set inserts, two small springs) and printed parts:
- T101 centre frame: two deep ribs from the arm base to the counterweight, over the bearing, as on a real upper frame.
- T104 hub adapter: the R2 hub (spigot, prongs, lead hole) as its own small print under T101.
- X103 ring gear centred on the RU66 outer ring (bore Ø95.2), fixed from below so its top face is a clean drag track.
- T102 motor slide: the pinion's mesh is set with a paper strip, then clamped and backed by two push screws.
- T103 drag pads (x 2): spring-loaded felt on the ring gear's top face; ~0.2 N·m keeps the upper from rattling in the play.
- Bolted joints in plastic: Ø12 washers + conical spring washers; the RU66 outer ring on nuts under the X-frame instead of
  heat-set inserts.
The slip ring and its mount are R2's, unchanged. The swing gearing (m1.5, 80:20, JGY-370 200:1) is R1's.

Sheets: 1 arrangement, 2 T101 centre frame and T104 hub, 3 swing drive (slide, mesh, ring gear, drag pad),
4 chassis-side changes, slip ring, assembly order and hardware.

Usage, with the CAD Python as for R1/R2 (x1_parts imports CadQuery):
  python draw_swing_concept_r3.py    # ../X1_swing_concept_R3.pdf, sheet PNGs, ../X1_swing_concept_R3_checks.json
"""
import json, math, sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle, FancyBboxPatch, FancyArrowPatch, Wedge, Polygon as MPoly
from matplotlib.backends.backend_pdf import PdfPages
from shapely.geometry import Point, Polygon, box as sbox
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
sys.path.insert(0, str(HERE))
import draw_swing_concept as C                        # noqa: E402  R1 helpers and swing gearing
import draw_swing_concept_r2 as R2                    # noqa: E402  R2 slip ring, collar, dog, checks
X = C.X
from draw_swing_concept import (INK, GREY, LIGHT, XF, XF_L, BRG, BRG_L, NEW, NEW_L, BUY, BUY_L, SLIP, SLIP_L,  # noqa: E402
                                RED, BLUE, GREEN, patch, box, both, note, dim_v, dim_h, wrap)

PDF = OUT / 'X1_swing_concept_R3.pdf'
PNG = [OUT / f'X1_swing_concept_R3_sheet{k}.png' for k in (1, 2, 3, 4)]
CHECKS = OUT / 'X1_swing_concept_R3_checks.json'
FIG = (16.5, 11.7)
UP, UP_L, UP2_L = '#1a5276', '#d4e6f1', '#a9cce3'   # turntable (upper) prints; the slide in a darker fill
ARMC = '#6c3483'                                     # existing ARM60 part, dashed
TPU, TPU_L = R2.TPU, R2.TPU_L
XFE = '#b9770e'

# ------------------------------------------------------------------ fixed by X1 and R1/R2
TOP_Z, PLATE_Z0, RELIEF_Z = X.TOP_Z, X.TOP_Z - X.PLATE_T, X.TOP_Z - X.RELIEF_DEPTH      # 85, 79, 82.5
TT_Z = X.TURNTABLE_Z                                                                       # 100
RU_D, RU_BORE = X.RU66['D'], X.RU66['d']                                                   # 95, 35
RU_OUT_PCD, RU_IN_PCD = X.RU66['outer_pcd'], X.RU66['inner_pcd']                           # 83, 45
MR_R0, MR_R1, MR_Z0 = X.MOUNT_RING                                                         # 35, 48, 75
PCD_R = R2.PCD_R
HUB = C.HUB                                          # Pololu #1999: flange Ø25.4 x 5, boss Ø12 x 4.2
M, ZR, ZP = C.MOD, C.Z_RING, C.Z_PIN                 # 1.5, 80, 20
CD = C.CD                                            # 75
RING_TIP, RING_ROOT, PIN_TIP, PIN_ROOT = C.RING_TIP, C.RING_ROOT, C.PIN_TIP, C.PIN_ROOT
PIN_Z = C.PIN_Z                                      # 87-97: 2 mm over the leg tops
LEG_ANG = math.degrees(math.atan2(X.TRACK_Y + X.M.HEAD_FACE_Y, X.ARM_X))                   # 63.4: direction of the arm ends (unused)

# ------------------------------------------------------------------ X103 ring gear (chassis), R3: centred on the RU66
RG = dict(bore_r=RU_D/2 + .1, z=(TOP_Z, 97.0), screw_r=51.0, screw_ang=[60*k for k in range(6)],
          insert=dict(r=2.0, depth=7.0), track=(49.5, 57.5), scallop_r=3.6)   # scallops in the mount ring and wall: the Ø6.3 heads pass
RG_SCREW = dict(head_r=3.15, head_h=1.7, L=12.0)    # ISO 10642 M3 x 12 countersunk, from below

# ------------------------------------------------------------------ T104 hub adapter and T101 centre frame (upper)
T104 = dict(r_in=R2.HUB['hole_r'], r_out=X.RU66['ds_max']/2, z=(TT_Z, 103.0), spigot_r=R2.HUB['spigot_r'],
            spigot_z0=R2.HUB['spigot_z0'], prong=R2.PRONG, holes=8, hole_r=2.25)
BASE_Z = (103.0, 109.0)                               # T101 base plate: 3 mm over the RU66 outer ring
TOPZ = 136.0                                          # rib tops = arm mounting plane
FR = dict(x=(-145.0, 107.0), y=69.0, corner=8.0)      # 252 long: fits a 256 bed
RIB_Y = (61.0, 69.0)
WELL = (30.0, 34.0)                                   # hub well: key access to the 8 hub screws
HUB_BULK = (30.0, 38.0)                               # bulkheads at X +-(30..38), 8 thick; the pad housings merge into the rear one
LEAD_SLOT = 5.0                                       # half-width of the lead slot through the rear hub bulkhead
REAR_BULK, FRONT_BULK = (-145.0, -141.0), (101.0, 107.0)
WINDOW_R = 10.0                                       # Ø20 window in the rear bulkhead: the motor's solder tabs and leads
ARM_X0 = 23.0                                         # ARM60 base origin (its root pivot O) from the swing axis
ARM_BASE = dict(x=(-44.0, 88.0), y=82.0, t=10.0, pivot_z=88.0, bolts=[(-32.0, 65.0), (76.0, 65.0)], cyl=(47.28, 55.77))
ARM_BOLTS = [(ARM_X0 + bx, s*by) for bx, by in ARM_BASE['bolts'] for s in (1, -1)]
ARM_BLOCK = dict(dx=7.0, y=(56.0, 74.0), nut_z=(111.0, 116.5))   # 14 x 18 blocks round the M6 bolts, nut pocket inboard
TH_HUB = [(RU_IN_PCD/2, a) for a in X.INNER_ANG]      # 8 x M4 hub screws on Ø45

# ------------------------------------------------------------------ JGY-370 swing motor on the T102 slide
GB_FACE = 109.0                                       # gearbox face on the slide body, flush with the base-plate top
SHAFT_TIP = GB_FACE - C.SHAFT_LEN                     # 93.4
HUB_Z = (PIN_Z[1], PIN_Z[1] + HUB['flange_t'], PIN_Z[1] + HUB['flange_t'] + HUB['boss_h'])   # 97 / 102 / 106.2
GB_BOSS = 1.6                                         # Ø13.2 x 1.6 boss round the shaft
PX = -CD
BACKLASH = 0.1                                        # set with the paper strip
PX_SET = PX - BACKLASH/(2*math.tan(math.radians(20)))  # -75.137: pinion axis with the mesh set
MOTOR = dict(gb_x=(PX - C.GB_REAR, PX + C.GB_FRONT), gb_y=C.GB_HALF, gb_z=(GB_FACE, GB_FACE + C.GB_DEPTH),
             can_x=(PX - C.CAN_END, PX - C.GB_REAR), can_r=C.CAN_R, can_z=GB_FACE + C.CAN_AX, term=10.0,
             holes=[(PX + 9.0, s*9.0) for s in (1, -1)] + [(PX - 24.0, s*9.0) for s in (1, -1)])
SLIDE = dict(x=(-108.0, -56.0), y=24.0, z=BASE_Z, ear_y=(24.0, 36.0), ear_z=(BASE_Z[1], BASE_Z[1] + 6.0),
             travel=2.0, slots=[(-100.0, 30.0), (-64.0, 30.0)], slot_len=3.4 + 4.0, hole_r=7.0,
             cb=(3.1, 1.8), boss_pocket=(3.7, 2.1))            # ISO 7380 heads from below; pockets for the gearbox's Ø7 x 2 screw bosses
OPENING = dict(x=(SLIDE['x'][0] - SLIDE['travel'], SLIDE['x'][1] + SLIDE['travel']), y=SLIDE['y'] + .2)
LUG = dict(x=(-120.0, -114.0), y=(25.0, 35.0), z=(BASE_Z[1], BASE_Z[1] + 8.0), screw_z=BASE_Z[1] + 4.0)   # M3 lock nut clears the plate

# ------------------------------------------------------------------ T103 drag pads (x 2)
PAD = dict(r=53.5, ang=(145.0, 215.0), housing_r=7.0, bore_r=4.0, lip=(103.0, 104.0), lip_r=3.4, top=124.0, head_r=3.8,
           insert=dict(r=4.0, length=9.0), set_screw='M6 x 8',   # M6 insert hole Ø8 = the bore: the Ø7.6 head passes it
           felt=(RG['z'][1], RG['z'][1] + 3.0), felt_r=4.0, stem_r=3.2, head=(106.0, 110.0), screw_tip=116.0,
           spring=dict(od=4.5, free=12.0, rate=1.2, wire=.5, solid=5.0), mu=.25)   # Ø4.5: drops through the M6 insert's thread
PAD_XY = [X.polar(PAD['r'], a) for a in PAD['ang']]

# ------------------------------------------------------------------ hardware stacks on the two bearing joints
WASH12 = dict(d=12.0, t=1.0)                          # DIN 9021 M4
DISC = dict(d=9.0, h=1.3)                             # DIN 6796 M4 conical spring washer
TOP_SCREW = dict(L=20.0)                              # M4 x 20 through T101 + T104 into the inner ring
BOT_SCREW = dict(L=30.0, head_z=TT_Z - 4.4)           # M4 x 30 from the RU66 counterbore, nut under the mount ring
NUT_M4 = 3.2
PRELOAD_N = 400.0                                     # target per M4 in plastic (about 0.3 N·m)
E_PETG = 2000.0                                       # MPa, printed PETG (assumed)
CW = dict(mass=1.8, x=-160.0)                         # counterweight (60 mm excavator: ballast 1.53 + shell 0.30 kg)
# Swing motor: the user's decision (2026-11-03) is the same motor as the J9 tracks; data from J9/README.md (Motor choice).
# The envelope, D-shaft, Pololu hub and 4 x M3 gearbox screws above are J9's model. No-load current ~0.1 A is inferred from
# J9's and R1's current-limit estimates (torque taken as linear in current); the vendor gives no figure.
JGY = dict(model='JGY-370-1260 12 V 200:1 (30 rpm)', rpm=(30.0, 22.0), t_rated_kgfcm=6.0, t_stall_kgfcm=20.0,
           i_rated=0.2, i_stall=1.3, i_noload=0.1, i_limit=0.6)
SWING_NEED_NM = 1.6                                   # R1 sizing: Cat 320 82 kN·m scaled by 1/15^4
LEWIS_Y, PETG_YIELD = 0.32, 50.0                      # Lewis form factor, 20 teeth; printed PETG yield, MPa (assumed)
SLIPRING = dict(ways=6, amp=2.0, wires=4)                 # only the two track motors' leads cross the joint
ISSUE = 'Issue 3, 2026-11-03: modelled in CAD (x1_turntable.py); fixes from the CAD checks. Issue 2: track motor, 6-way slip ring'


def frame_walls(pads=True):
    """T101 in plan: everything that stands above the base plate (pads=False: without the drag-pad housings,
    which stand only to Z 124)."""
    w = [sbox(FR['x'][0], s*RIB_Y[0], FR['x'][1], s*RIB_Y[1]) for s in (1, -1)]
    w += [sbox(FR['x'][0], -RIB_Y[0], REAR_BULK[1], RIB_Y[0]), sbox(FRONT_BULK[0], -RIB_Y[0], FRONT_BULK[1], RIB_Y[0])]
    w += [sbox(HUB_BULK[0], -RIB_Y[0], HUB_BULK[1], RIB_Y[0])]
    for s in (1, -1):
        w += [sbox(-HUB_BULK[1], s*LEAD_SLOT, -HUB_BULK[0], s*RIB_Y[0])]
    w += [Point(0, 0).buffer(WELL[1], 64).difference(Point(0, 0).buffer(WELL[0], 64))]
    for x, y in ARM_BOLTS:
        w += [sbox(x - ARM_BLOCK['dx'], np.sign(y)*ARM_BLOCK['y'][0], x + ARM_BLOCK['dx'], np.sign(y)*ARM_BLOCK['y'][1])]
    if pads:
        w += [Point(x, y).buffer(PAD['housing_r'], 48) for x, y in PAD_XY]
    for s in (1, -1):
        w += [sbox(LUG['x'][0], s*LUG['y'][0], LUG['x'][1], s*LUG['y'][1])]
    u = unary_union([g.buffer(0) for g in w])
    slot = sbox(-WELL[1] - 1, -LEAD_SLOT, -WELL[0] + 1, LEAD_SLOT)
    return u.difference(slot).difference(Point(0, 0).buffer(WELL[0], 64))


def frame_base():
    b = sbox(FR['x'][0], -FR['y'], FR['x'][1], FR['y']).buffer(-FR['corner']).buffer(FR['corner'], 16)
    b = unary_union([b] + [sbox(x - ARM_BLOCK['dx'], np.sign(y)*ARM_BLOCK['y'][0], x + ARM_BLOCK['dx'], np.sign(y)*ARM_BLOCK['y'][1])
                           for x, y in ARM_BOLTS])
    b = b.difference(Point(0, 0).buffer(T104['r_in'], 48))
    return b.difference(sbox(OPENING['x'][0], -OPENING['y'], OPENING['x'][1], OPENING['y']))


def draw_shape(ax, g, fc, ec, lw=.6, z=3, hatch=None, ls='-', alpha=1.0, hole_fc='white'):
    geoms = sorted(getattr(g, 'geoms', [g]), key=lambda p: -p.area)
    for i, p in enumerate(geoms):
        if p.is_empty:
            continue
        zz = z + .05*i
        patch(ax, list(p.exterior.coords), fc=fc, ec=ec, lw=lw, z=zz, hatch=hatch, ls=ls, alpha=alpha)
        for h in p.interiors:
            patch(ax, list(h.coords), fc=hole_fc, ec=ec, lw=lw, z=zz + .01, ls=ls)


# ------------------------------------------------------------------ numbers: stiffness, joints, drag, play
def section_I(rects):
    a = sum(w*h for w, h, zc in rects)
    zbar = sum(w*h*zc for w, h, zc in rects)/a
    return sum(w*h**3/12 + w*h*(zc - zbar)**2 for w, h, zc in rects), zbar


def estimates():
    strip = FR['y'] - OPENING['y']
    t101 = [(2*strip, BASE_Z[1] - BASE_Z[0], sum(BASE_Z)/2), (2*(RIB_Y[1] - RIB_Y[0]), TOPZ - BASE_Z[1], (TOPZ + BASE_Z[1])/2)]
    i_t101, _ = section_I(t101)
    i_plate, _ = section_I([(2*FR['y'], 6.0, 3.0)])
    L = abs(CW['x']) - WELL[1]
    P = CW['mass']*9.81

    def cant(i):
        k = 3*E_PETG*i/L**3                           # N/mm
        return P/k, math.sqrt(k*1000/CW['mass'])/(2*math.pi)
    d_plate, f_plate = cant(i_plate)
    d_t101, f_t101 = cant(i_t101)
    a12 = math.pi/4*(WASH12['d']**2 - 4.5**2)
    m_open_top = 4*(RU_IN_PCD/2/1000)*PRELOAD_N
    m_open_bot = 4*(RU_OUT_PCD/2/1000)*PRELOAD_N
    seat = math.pi/4*(RU_D**2 - X.RU66['Dh_min']**2)
    f_pad = PAD['spring']['rate']*(PAD['spring']['free'] - (PAD['screw_tip'] - PAD['head'][1]))
    drag = 2*f_pad*PAD['mu']*PAD['r']/1000
    gb = (1.0, 2.0)                                   # JGY-370 output play, deg: assumed, measure it
    ratio = ZR/ZP
    mesh_before, mesh_after = (0.2, 0.4), (0.1, 0.1)
    def turn(mesh, g):
        return math.degrees(mesh/(M*ZR/2)) + g/ratio
    play_before = (turn(mesh_before[0], gb[0]), turn(mesh_before[1], gb[1]))
    play_after = (turn(mesh_after[0], gb[0]), turn(mesh_after[1], gb[1]))
    at = lambda deg: 500*math.tan(math.radians(deg))
    g = 9.81/100                                      # kgf·cm -> N·m
    t_rated, t_stall = JGY['t_rated_kgfcm']*g, JGY['t_stall_kgfcm']*g
    t_limit = t_stall*(JGY['i_limit'] - JGY['i_noload'])/(JGY['i_stall'] - JGY['i_noload'])
    r_pin = M*ZP/2/1000
    lewis = lambda t: t/r_pin/((PIN_Z[1] - PIN_Z[0])*M*LEWIS_Y)
    swing = dict(motor=JGY['model'], same_as_tracks=True, ratio=ratio,
                 turntable_rpm_noload=JGY['rpm'][0]/ratio, turntable_rpm_rated=JGY['rpm'][1]/ratio,
                 seconds_per_turn=[60/(JGY['rpm'][0]/ratio), 60/(JGY['rpm'][1]/ratio)],
                 motor_torque_Nm=dict(rated=t_rated, stall=t_stall, at_limit=t_limit), current_limit_A=JGY['i_limit'],
                 turntable_torque_Nm=dict(rated=t_rated*ratio, stall=t_stall*ratio, at_limit=t_limit*ratio, needed=SWING_NEED_NM),
                 tooth_force_N=dict(stall=t_stall/r_pin, at_limit=t_limit/r_pin),
                 tooth_stress_MPa=dict(stall=lewis(t_stall), at_limit=lewis(t_limit), petg_yield=PETG_YIELD),
                 note='torques before gear losses; Lewis bending on the 20-tooth pinion, 10 wide')
    slip = dict(ways=SLIPRING['ways'], wires_crossing=SLIPRING['wires'], spare=SLIPRING['ways'] - SLIPRING['wires'], amp_per_ring=SLIPRING['amp'],
                max_amp_per_wire=JGY['i_stall'], note='battery, receiver, all drivers and the swing motor ride in the upper')
    return dict(
        swing_motor=swing, slip_ring=slip,
        stiffness=dict(E_MPa=E_PETG, counterweight_kg=CW['mass'], lever_mm=L, I_plate_mm4=i_plate, I_T101_mm4=i_t101,
                       ratio=i_t101/i_plate, sag_plate_mm=d_plate, sag_T101_mm=d_t101, f_plate_Hz=f_plate, f_T101_Hz=f_t101,
                       note='cantilever from the hub well to the counterweight; T101 cut through the motor opening (weakest)'),
        top_joint=dict(screws='8 x M4 x 20 + DIN 6796 + DIN 9021 (Ø12)', preload_N=PRELOAD_N, pressure_MPa=PRELOAD_N/a12,
                       opening_moment_Nm=m_open_top, static_moment_Nm=2.93,
                       note='static moment: upper + arm of the 60 mm excavator (its validation.json)'),
        bottom_joint=dict(screws='8 x M4 x 30, nut + DIN 6796 + DIN 9021 under the mount ring', preload_N=PRELOAD_N,
                          pressure_washer_MPa=PRELOAD_N/a12, pressure_seat_MPa=8*PRELOAD_N/seat, opening_moment_Nm=m_open_bot),
        drag=dict(force_per_pad_N=f_pad, pads=2, mu_assumed=PAD['mu'], radius_mm=PAD['r'], torque_Nm=drag,
                  share_of_rated_swing_torque=drag/(t_rated*ratio), rated_swing_torque_Nm=t_rated*ratio, pull_at_100mm_N=drag/.1),
        play=dict(gearbox_deg_assumed=gb, ratio=ratio, mesh_mm_before=mesh_before, mesh_mm_after=mesh_after,
                  turntable_deg_before=play_before, turntable_deg_after=play_after,
                  at_500mm_before=[at(v) for v in play_before], at_500mm_after=[at(v) for v in play_after]))


def checks():
    c = []

    def add(name, value, need, note_='', unit='mm'):
        c.append(dict(check=name, value=round(value, 2), unit=unit, required=need, ok=bool(eval(f'{value} {need}')), note=note_))
    add('pinion above the leg tops', PIN_Z[0] - TOP_Z, '>= 1.5')
    add('hub flange below the slide body', BASE_Z[0] - HUB_Z[1], '>= 0.8')
    add('hub boss below the gearbox boss', GB_FACE - GB_BOSS - HUB_Z[2], '>= 0.5')
    add('shaft engagement in the hub (shaft tip below the hub)', HUB_Z[0] - SHAFT_TIP, '>= 0', 'the whole hub bore is on the shaft')
    add('T101 above the RU66 outer ring', BASE_Z[0] - TT_Z, '>= 2')
    add('T101 above the ring gear', BASE_Z[0] - RG['z'][1], '>= 4')
    add('ring gear bore to the RU66 outer ring, radial', RG['bore_r'] - RU_D/2, '<= 0.15', 'centring fit')
    add('drag track inside the ring-gear band, inner', RG['track'][0] - RG['bore_r'], '>= 1')
    add('drag track inside the ring-gear band, outer', RING_ROOT - RG['track'][1], '>= 0.5')
    add('felt pad inside the track', min(PAD['r'] - PAD['felt_r'] - RG['track'][0], RG['track'][1] - PAD['r'] - PAD['felt_r']), '>= 0')
    add('pad housing merges into the rear hub bulkhead (overlap)', (PAD_XY[0][0] + PAD['housing_r']) + HUB_BULK[1], '>= 1')
    add('pad housing to the slide ears at full travel', (PAD_XY[0][0] - PAD['housing_r']) - (SLIDE['x'][1] + SLIDE['travel']), '>= 2')
    add('motor can to the rear bulkhead at full travel', (MOTOR['can_x'][0] - SLIDE['travel']) - REAR_BULK[1], '>= 1.5')
    add('push-screw lugs to the slide ears, nearest', SLIDE['x'][0] - SLIDE['travel'] - LUG['x'][1], '>= 1')
    add('gearbox to the rib inner faces', RIB_Y[0] - MOTOR['gb_y'], '>= 20')
    add('motor can top below the rib tops', TOPZ - (MOTOR['can_z'] + MOTOR['can_r']), '>= 1')
    add('hub washers to the well wall', WELL[0] - (RU_IN_PCD/2 + WASH12['d']/2), '>= 1')
    tip = BASE_Z[1] + DISC['h'] + WASH12['t'] - TOP_SCREW['L']
    add('hub screws: thread in the inner ring', TT_Z - tip, '>= 6')
    add('hub screws: tip above the X-frame relief limit (Z 83)', tip - 83.0, '>= 1')
    add('bottom joint: Ø12 washer inside the mount ring, inner', RU_OUT_PCD/2 - WASH12['d']/2 - MR_R0, '>= 0.5')
    add('bottom joint: Ø12 washer inside the mount ring, outer', MR_R1 - RU_OUT_PCD/2 - WASH12['d']/2, '>= 0.5')
    stack = MR_Z0 - WASH12['t'] - DISC['h'] - NUT_M4
    add('bottom joint: screw past the nut', stack - (BOT_SCREW['head_z'] - BOT_SCREW['L']), '>= 1')
    add('ring-gear screw: thread in the gear', PLATE_Z0 + RG_SCREW['L'] - RG['z'][0], '>= 4.5')
    add('ring-gear screw: key gap between mount ring and wall', X.BODY_R - X.BODY_WALL - MR_R1, '>= 5')
    add('ring-gear insert hole inside the gear band', RG['screw_r'] - RG['insert']['r'] - RG['bore_r'], '>= 1')
    add('arm bolts: M6 x 40 past the nut', (TOPZ + ARM_BASE['t'] - 40.0) - ARM_BLOCK['nut_z'][0], '<= -1', 'negative = below the nut')
    add('drag-pad travel before the plunger lands on the lip', PAD['head'][0] - PAD['lip'][1], '>= 1.5')
    add('plunger head through the M6 insert hole (fitted from above)', PAD['insert']['r'] - PAD['head_r'], '>= 0.15', 'radial')
    add('drag spring above its solid length when set', PAD['screw_tip'] - PAD['head'][1] - PAD['spring']['solid'], '>= 0.5', 'Ø4.5 × 12, wire 0.5, ~8 coils')
    add('drag spring through the M6 insert thread (minor Ø4.92)', (4.917 - PAD['spring']['od'])/2, '>= 0.1', 'fitted after the insert', unit='mm')
    add('plunger hanging on the lip clear of the insert while it is pressed', PAD['top'] - PAD['insert']['length'] - (PAD['lip'][1] + PAD['head'][1] - PAD['head'][0]), '>= 3')
    add('push-screw M3 lock nut above the base plate', LUG['screw_z'] - 6.35/2 - BASE_Z[1], '>= 0.5', 'nut across corners 6.35')
    add('ring-gear screw head through the scallop', RG['scallop_r'] - RG_SCREW['head_r'], '>= 0.3', 'radial')
    add('motor lead bundle (Ø18) through the rear window', WINDOW_R - 9.0, '>= 0.5', 'radial')
    add('T101 length on a 256 bed', 256 - (FR['x'][1] - FR['x'][0]), '>= 3')
    add('T101 width on a 256 bed', 256 - 2*ARM_BLOCK['y'][1], '>= 3')
    e = estimates()
    add('T101 stiffer than a 6 mm plate', e['stiffness']['ratio'], '>= 20', unit='ratio')
    add('hub joint opening moment over the static moment', e['top_joint']['opening_moment_Nm']/e['top_joint']['static_moment_Nm'], '>= 5', unit='ratio')
    add('drag torque', e['drag']['torque_Nm'], '<= 0.4', unit='N·m')
    sw, sl = e['swing_motor'], e['slip_ring']
    add('swing torque, rated, over the R1 sizing need', sw['turntable_torque_Nm']['rated']/SWING_NEED_NM, '>= 1.2', 'track motor, 4:1 gears', unit='ratio')
    add('pinion tooth stress at motor stall, margin to PETG yield', PETG_YIELD - sw['tooth_stress_MPa']['stall'], '>= 10',
        'Lewis bending; no current limit', unit='MPa')
    add('slip ring: current per ring at track-motor stall, margin to 2 A', SLIPRING['amp'] - JGY['i_stall'], '>= 0.5', unit='A')
    add('slip ring: spare rings after the 4 track-motor leads', sl['spare'], '>= 1', unit='rings')
    return c, e


# ------------------------------------------------------------------ drawing pieces, section XZ (Y = 0) unless stated
def ring_gear_cut(ax, lw=.8):
    hn = dict(fc=NEW_L, ec=NEW, hatch='xxx', lw=lw, z=5)
    both(ax, RG['bore_r'], RING_TIP, *RG['z'], **hn)
    for s in (1, -1):
        ax.plot([s*RING_ROOT]*2, RG['z'], color=NEW, lw=.5, zorder=6)


def ring_gear_screws(ax, sides=(1, -1)):
    for s in sides:
        x = s*RG['screw_r']
        patch(ax, [(x - RG_SCREW['head_r'], PLATE_Z0), (x + RG_SCREW['head_r'], PLATE_Z0), (x + 1.5, PLATE_Z0 + RG_SCREW['head_h']),
                   (x - 1.5, PLATE_Z0 + RG_SCREW['head_h'])], fc=BUY, ec=BUY, lw=.4, z=8)
        box(ax, x - 1.5, PLATE_Z0, x + 1.5, PLATE_Z0 + RG_SCREW['L'], fc=BUY_L, ec=BUY, lw=.4, z=7)
        box(ax, x - RG['insert']['r'], TOP_Z, x + RG['insert']['r'], TOP_Z + 5.7, fc='none', ec='#b7950b', lw=.6, ls='--', z=8)


def bottom_joint(ax, x, solid=False, lw=.5):
    """RU66 outer-ring screw with nut, disc and Ø12 washer under the mount ring (dashed when out of the plane)."""
    ls = '-' if solid else '--'
    fc = (lambda c: c) if solid else (lambda c: 'none')
    hz = BOT_SCREW['head_z']
    box(ax, x - 3.5, hz, x + 3.5, hz + 4.0, fc=fc(BUY), ec=BUY, lw=lw, ls=ls, z=8)
    box(ax, x - 2, hz - BOT_SCREW['L'], x + 2, hz, fc=fc(BUY_L), ec=BUY, lw=lw, ls=ls, z=7)
    z = MR_Z0
    box(ax, x - WASH12['d']/2, z - WASH12['t'], x + WASH12['d']/2, z, fc=fc('#d5d8dc'), ec=BUY, lw=lw, ls=ls, z=8)
    z -= WASH12['t']
    patch(ax, [(x - DISC['d']/2, z), (x + DISC['d']/2, z), (x + 2.6, z - DISC['h']), (x - 2.6, z - DISC['h'])],
          fc=fc('#aab7b8'), ec=BUY, lw=lw, ls=ls, z=8)
    z -= DISC['h']
    box(ax, x - 3.5, z - NUT_M4, x + 3.5, z, fc=fc('#566573'), ec=BUY, lw=lw, ls=ls, z=8)


def hub_screw(ax, x, lw=.5):
    """M4 x 20 hub screw with disc and Ø12 washer, through T101 and T104 into the RU66 inner ring (in the plane)."""
    z = BASE_Z[1]
    box(ax, x - WASH12['d']/2, z, x + WASH12['d']/2, z + WASH12['t'], fc='#d5d8dc', ec=BUY, lw=lw, z=9)
    z += WASH12['t']
    patch(ax, [(x - DISC['d']/2, z), (x + DISC['d']/2, z), (x + 2.6, z + DISC['h']), (x - 2.6, z + DISC['h'])], fc='#aab7b8', ec=BUY, lw=lw, z=9)
    z += DISC['h']
    box(ax, x - 3.5, z, x + 3.5, z + 4.0, fc=BUY, ec=BUY, lw=lw, z=9)
    box(ax, x - 2, z - TOP_SCREW['L'], x + 2, z, fc=BUY_L, ec=BUY, lw=lw, z=8)


def t104_cut(ax, prongs=(1, -1), lw=.7):
    hu = dict(fc=UP_L, ec=UP, hatch='////', lw=lw, z=5)
    both(ax, T104['r_in'], T104['r_out'], *T104['z'], **hu)
    both(ax, T104['r_in'], T104['spigot_r'], T104['spigot_z0'], T104['z'][0], **hu)
    for s in prongs:
        box(ax, s*T104['prong']['ri'], T104['prong']['z0'], s*T104['prong']['ro'], T104['prong']['z1'], **hu)


def dog_cut(ax, lw=.6):
    """R2's TPU dog cut between its lugs (lugs at +-Y)."""
    hd = dict(fc=TPU_L, ec=TPU, hatch='....', lw=lw, z=7)
    rb = R2.DOG['bore_d']/2 + .15
    both(ax, rb, R2.DOG['r_out'], R2.DOG['z0'], R2.ROTOR_Z[1], **hd)
    both(ax, R2.DOG['hole_d']/2, R2.DOG['r_out'], R2.ROTOR_Z[1], R2.DOG['z1'], **hd)


def motor_side(ax, lw=.8, labels=True):
    """JGY-370 seen from the side (not cut), pinion axis at X = -75; hub and pinion cut."""
    gx, gz = MOTOR['gb_x'], MOTOR['gb_z']
    box(ax, gx[0], gz[0], gx[1], gz[1], fc='#d4ac6e', ec='#7e5109', lw=lw, z=6)
    zc = MOTOR['can_z']
    box(ax, MOTOR['can_x'][0], zc - MOTOR['can_r'], MOTOR['can_x'][1], zc + MOTOR['can_r'], fc='#bfc9ca', ec=INK, lw=lw, z=6)
    box(ax, MOTOR['can_x'][0] - MOTOR['term'], zc - 3, MOTOR['can_x'][0], zc + 3, fc='#e5e8e8', ec=INK, lw=.5, z=6)
    box(ax, PX - 6.6, GB_FACE - GB_BOSS, PX + 6.6, GB_FACE, fc='#d4ac6e', ec='#7e5109', lw=.5, z=6)
    if labels:
        ax.text(sum(gx)/2, sum(gz)/2, 'JGY-370\ngearbox', fontsize=6.0, ha='center', va='center', color='#7e5109', zorder=8)
        ax.text(sum(MOTOR['can_x'])/2, zc, 'motor', fontsize=6.0, ha='center', va='center', color=INK, zorder=8)
    box(ax, PX - 3, SHAFT_TIP, PX + 3, GB_FACE, fc='#566573', ec=INK, lw=.5, z=7)
    hb = dict(fc=BUY_L, ec=BUY, lw=.7, z=6)
    box(ax, PX - HUB['flange_r'], HUB_Z[0], PX + HUB['flange_r'], HUB_Z[1], **hb)
    box(ax, PX - HUB['boss_r'], HUB_Z[1], PX + HUB['boss_r'], HUB_Z[2], **hb)
    hu = dict(fc=UP_L, ec=UP, hatch='xxx', lw=.8, z=5)
    box(ax, PX - PIN_TIP, PIN_Z[0], PX - 3.5, PIN_Z[1], **hu)
    box(ax, PX + 3.5, PIN_Z[0], PX + PIN_TIP, PIN_Z[1], **hu)
    for s in (1, -1):
        ax.plot([PX + s*PIN_ROOT]*2, PIN_Z, color=UP, lw=.5, zorder=6)
        x = PX + s*HUB['pcd_r']
        box(ax, x - 1.5, PIN_Z[0], x + 1.5, HUB_Z[1], fc='none', ec=INK, lw=.45, ls='--', z=8)


def slide_cut(ax, lw=.7):
    """T102 body in the XZ plane at Y = 0 (cut), with the shaft hole; gearbox screws dashed."""
    hs = dict(fc=UP2_L, ec=UP, hatch='\\\\\\\\', lw=lw, z=5)
    box(ax, SLIDE['x'][0], SLIDE['z'][0], PX - SLIDE['hole_r'], SLIDE['z'][1], **hs)
    box(ax, PX + SLIDE['hole_r'], SLIDE['z'][0], SLIDE['x'][1], SLIDE['z'][1], **hs)
    for hx in sorted({h[0] for h in MOTOR['holes']}):
        z0 = SLIDE['z'][0] + SLIDE['cb'][1]
        box(ax, hx - 1.5, z0, hx + 1.5, z0 + 8.0, fc='none', ec=INK, lw=.45, ls='--', z=8)
        box(ax, hx - SLIDE['cb'][0], SLIDE['z'][0], hx + SLIDE['cb'][0], z0, fc='none', ec=INK, lw=.45, ls='--', z=8)
        box(ax, hx - SLIDE['boss_pocket'][0], GB_FACE - SLIDE['boss_pocket'][1], hx + SLIDE['boss_pocket'][0], GB_FACE,
            fc='none', ec=INK, lw=.45, ls=':', z=8)


def frame_cut_xz(ax, lw=.7, behind=True):
    """T101 cut at Y = 0: base plate (with the hub hole and the motor opening), bulkheads; ribs and blocks behind."""
    hu = dict(fc=UP_L, ec=UP, hatch='////', lw=lw, z=4)
    segs = [(FR['x'][0], OPENING['x'][0]), (OPENING['x'][1], -T104['r_in']), (T104['r_in'], FR['x'][1])]
    for a, b in segs:
        box(ax, a, BASE_Z[0], b, BASE_Z[1], **hu)
    wz = MOTOR['can_z']
    box(ax, REAR_BULK[0], BASE_Z[1], REAR_BULK[1], wz - 8, **hu)
    box(ax, REAR_BULK[0], wz + 8, REAR_BULK[1], TOPZ, **hu)
    box(ax, WELL[0], BASE_Z[1], HUB_BULK[1], TOPZ, **hu)
    box(ax, FRONT_BULK[0], BASE_Z[1], FRONT_BULK[1], TOPZ, **hu)
    if behind:
        patch(ax, [(FR['x'][0], BASE_Z[1]), (FR['x'][1], BASE_Z[1]), (FR['x'][1], TOPZ), (FR['x'][0], TOPZ)],
              fc='#eaf2f8', ec=UP, lw=.5, ls='--', z=1)
        for x, y in ARM_BOLTS[::2]:
            box(ax, x - ARM_BLOCK['dx'], BASE_Z[1], x + ARM_BLOCK['dx'], TOPZ, fc='none', ec=UP, lw=.45, ls='--', z=2)
        box(ax, -HUB_BULK[1], BASE_Z[1], -HUB_BULK[0], TOPZ, fc='#eaf2f8', ec=UP, lw=.45, ls='--', z=2)
        x0, x1 = PAD_XY[0][0] - PAD['housing_r'], PAD_XY[0][0] + PAD['housing_r']
        box(ax, x0, BASE_Z[1], x1, PAD['top'], fc='#eaf2f8', ec=UP, lw=.5, ls='--', z=3)
        box(ax, PAD_XY[0][0] - PAD['felt_r'], PAD['felt'][0], PAD_XY[0][0] + PAD['felt_r'], BASE_Z[0], fc='#f5eef8', ec=UP, lw=.5, ls='--', z=3)
        box(ax, LUG['x'][0], LUG['z'][0], LUG['x'][1], LUG['z'][1], fc='#eaf2f8', ec=UP, lw=.45, ls='--', z=3)
        box(ax, SLIDE['x'][0], SLIDE['ear_z'][0], SLIDE['x'][1], SLIDE['ear_z'][1], fc='none', ec=UP, lw=.45, ls='--', z=3)


def arm_base_xz(ax, lw=.8):
    x0, x1 = ARM_X0 + ARM_BASE['x'][0], ARM_X0 + ARM_BASE['x'][1]
    box(ax, x0, TOPZ, x1, TOPZ + ARM_BASE['t'], fc='#f4ecf7', ec=ARMC, lw=lw, ls='--', z=2)
    o = (ARM_X0, TOPZ + ARM_BASE['pivot_z'])
    patch(ax, [(ARM_X0 - 20, TOPZ + ARM_BASE['t']), (ARM_X0 + 20, TOPZ + ARM_BASE['t']), (ARM_X0 + 10, o[1]), (ARM_X0 - 10, o[1])],
          fc='#f4ecf7', ec=ARMC, lw=lw, ls='--', z=2)
    ax.add_patch(Circle(o, 10, fc='#f4ecf7', ec=ARMC, lw=lw, ls='--', zorder=2))
    ax.add_patch(Circle(o, 3, fc='white', ec=ARMC, lw=lw, zorder=3))
    a = (ARM_X0 + ARM_BASE['cyl'][0], TOPZ + ARM_BASE['cyl'][1])
    patch(ax, [(a[0] - 15, TOPZ + ARM_BASE['t']), (a[0] + 15, TOPZ + ARM_BASE['t']), (a[0] + 6, a[1]), (a[0] - 6, a[1])],
          fc='#f4ecf7', ec=ARMC, lw=lw, ls='--', z=2)
    ax.add_patch(Circle(a, 2, fc='white', ec=ARMC, lw=lw, zorder=3))
    for x, y in ARM_BOLTS[::2]:
        box(ax, x - 3, BASE_Z[1] + 2, x + 3, TOPZ + ARM_BASE['t'] + 4, fc='none', ec=BUY, lw=.5, ls='--', z=3)
    return o, a


# ------------------------------------------------------------------ sheet 1: arrangement
def section_aa(ax):
    ax.set_title('SECTION A–A on the centreline, seen from the right-hand side (front to the right)', fontsize=10.5, loc='left', weight='bold')
    L = 308.6
    patch(ax, C.stadium(-L/2, L/2, 0, 92.4), fc='#eef0f1', ec=LIGHT, lw=.6, ls='--', z=0)
    patch(ax, C.frame_side_silhouette(), fc='#fbf1cf', ec='#d4ac0d', lw=.5, ls='--', z=1)
    ax.plot([-200, 150], [0, 0], color='#6b4f2a', lw=1.2, zorder=0)
    C.carbody_section(ax, bosses=False)
    R2.collar(ax, lw=.7)
    box(ax, -X.BODY_R, X.COVER_Z[0], X.BODY_R, X.COVER_Z[1], fc='#808b96', ec=INK, lw=.5, z=3)
    C.ru66_section(ax)
    bottom_joint(ax, RU_OUT_PCD/2)
    ring_gear_cut(ax)
    ring_gear_screws(ax)
    R2.ring(ax, screw=True, lw=.7)
    dog_cut(ax)
    t104_cut(ax)
    frame_cut_xz(ax)
    slide_cut(ax)
    motor_side(ax)
    o, a = arm_base_xz(ax)
    # counterweight (body part, next step)
    patch(ax, [(FR['x'][0], BASE_Z[0]), (-X.RESERVE_R + 6, BASE_Z[0]), (-X.RESERVE_R, BASE_Z[0] + 8), (-X.RESERVE_R, 180),
               (-X.RESERVE_R + 10, 190), (FR['x'][0], 190)], fc='#f2f3f4', ec=GREY, lw=.7, ls='--', z=1)
    ax.text(-167, 160, 'counter-\nweight\n(body part,\nnext step)', fontsize=6.0, color=GREY, ha='center', va='center')
    ax.plot([0, 0, -15, -15, -30], [R2.ROTOR_Z[1], 114, 114, 114, 114], color=GREEN, lw=1.4, zorder=9)
    ax.annotate('', (-60, 114), (-30, 114), arrowprops=dict(arrowstyle='->', color=GREEN, lw=1.2), zorder=9)
    # dimensions
    dim_v(ax, -194, 0, TOP_Z, 'Z 85', side=-1, fs=6.6)
    dim_v(ax, 140, 0, TT_Z, 'Z 100: turntable face', side=1, fs=6.6)
    dim_v(ax, 128, BASE_Z[0], TOPZ, '33', side=1, fs=6.6)
    dim_h(ax, PX, 0, 252, '75: pinion axis', fs=6.6)
    dim_h(ax, 0, ARM_X0, o[1] + 14, f'{ARM_X0:g}', fs=6.6)
    ax.plot([0, 0], [-6, 258], color=LIGHT, lw=.6, ls='-.', zorder=1)
    ax.plot([PX, PX], [GB_FACE + C.GB_DEPTH + 2, 251], color=LIGHT, lw=.5, ls='-.', zorder=1)
    ax.plot([ARM_X0, ARM_X0], [o[1] + 4, o[1] + 16], color=LIGHT, lw=.5, ls='-.', zorder=1)
    # labels: upper parts above, chassis parts below
    k = dict(fs=6.7)
    note(ax, o, (52, 250), 'boom foot pin O (ARM60, existing):\nZ 224, 23 ahead of the swing axis', color=ARMC, relpos=(0, .5), **k)
    note(ax, (80, TOPZ + 6), (66, 224), 'ARM60 fixed pivot base (existing):\n4 × M6 × 40 into nuts in the ribs', color=ARMC, relpos=(0, .5), **k)
    note(ax, (88, 124), (90, 196), 'T101 centre frame (NEW):\ntwo ribs 8 × 27 on a 6 mm\nbase plate; bulkheads; well', color=UP, relpos=(0, .5), **k)
    note(ax, (-118, 112), (-196, 240), 'T102 motor slide (NEW): the JGY-370 sits\non it; slotted, set with a paper strip,\nthen clamped and backed by 2 push screws',
         color=UP, va='top', relpos=(.5, 0), **k)
    note(ax, (-43.8, 118), (-100, 206), 'T103 drag pad (×2, behind the cut):\nspring-loaded felt on the ring gear', color=UP, va='top', relpos=(.6, 0), **k)
    note(ax, (24, 101.5), (-14, 192), 'T104 hub adapter (NEW): spigot\nin the RU66 bore, slip-ring prongs', color=UP, ha='right', va='top', relpos=(1, .5), **k)
    note(ax, (-12, 114), (-56, 172), 'slip-ring rotor leads, out\nthrough the rear lead slot', color=GREEN, ha='right', va='top', relpos=(1, .3), **k)
    note(ax, (-86, 92), (-196, -10), 'T105 pinion (as R1): 20 teeth,\nm1.5, 10 wide, on the Pololu hub;\n2 mm over the leg tops', color=UP, va='top', relpos=(.6, 1), **k)
    note(ax, (-55, 90), (-122, -10), 'X103 ring gear: now centred on\nthe RU66 (bore Ø95.2), screwed\nfrom below; top = drag track', color=NEW, va='top', relpos=(.6, 1), **k)
    note(ax, (RU_OUT_PCD/2, 71), (-46, -10), 'RU66 on nuts under the mount ring\n(was heat-set inserts): M4 × 30,\nØ12 washer + spring washer', color=BUY, va='top', relpos=(.6, 1), **k)
    note(ax, (11, 66), (40, -10), 'slip ring and collar (R2,\nunchanged, sheet 4)', color=SLIP, va='top', relpos=(.2, 1), **k)
    ax.set_xlim(-200, 152); ax.set_ylim(-42, 262); ax.set_aspect('equal'); ax.axis('off')


def plan_r3(ax, big=False):
    """Turntable from above (swing 0): T101 walls over the base plate, motor, slide, pads, arm base and body outlines."""
    if not big:
        ax.set_title('PLAN VIEW of the turntable (front to the right)', fontsize=10.5, loc='left', weight='bold')
        ax.add_patch(Circle((0, 0), X.RESERVE_R, fill=False, ec=UP, lw=.7, ls='--', zorder=1))
        ax.text(-125, -150, 'swing circle R 189', fontsize=6.6, color=UP, rotation=40)
        for s in (1, -1):                              # side decks and counterweight: outlines only
            patch(ax, [(FR['x'][0] + 10, s*FR['y']), (FR['x'][1] - 5, s*FR['y']), (FR['x'][1] - 5, s*154), (FR['x'][0] + 10, s*154)],
                  fc='#f8f9f9', ec=GREY, lw=.6, ls='--', z=0)
        t = np.linspace(math.radians(140.4), math.radians(219.6), 60)
        cw = [(FR['x'][0], -120)] + [(X.RESERVE_R*math.cos(a), X.RESERVE_R*math.sin(a)) for a in t[::-1]] + [(FR['x'][0], 120)]
        cw = [(FR['x'][0], 120)] + [(X.RESERVE_R*math.cos(a), X.RESERVE_R*math.sin(a)) for a in t] + [(FR['x'][0], -120)]
        patch(ax, cw, fc='#f2f3f4', ec=GREY, lw=.6, ls='--', z=0)
        ax.text(-165, 0, 'counter-\nweight', fontsize=6.3, color=GREY, ha='center', va='center', rotation=90)
        for s in (1, -1):
            ax.text(-20, s*143, 'side deck: battery, receiver, drivers (body part, next step)', fontsize=6.0, color=GREY, ha='center', va='center')
    # under the frame, dashed: ring gear, RU66, pinion
    ax.add_patch(Circle((0, 0), RING_TIP, fill=False, ec=NEW, lw=.8, ls=(0, (4, 2.5)), zorder=5.5))
    ax.add_patch(Circle((PX, 0), PIN_TIP, fill=False, ec=UP, lw=.6, ls='--', zorder=6))
    draw_shape(ax, frame_base(), fc='#cfe2f3', ec=UP, lw=.6, z=2)
    draw_shape(ax, frame_walls(), fc='#7fb3d5', ec=UP, lw=.6, z=3, hole_fc='#cfe2f3')
    # slide and motor
    sx = SLIDE['x']
    patch(ax, [(sx[0], -SLIDE['ear_y'][1]), (sx[1], -SLIDE['ear_y'][1]), (sx[1], SLIDE['ear_y'][1]), (sx[0], SLIDE['ear_y'][1])],
          fc=UP2_L, ec=UP, lw=.6, z=4)
    for x, y in SLIDE['slots']:
        for s in (1, -1):
            ax.add_patch(FancyBboxPatch((x - SLIDE['slot_len']/2 + 1.7, s*y - 1.7), SLIDE['slot_len'] - 3.4, 3.4, boxstyle='round,pad=0,rounding_size=1.7',
                                        fc='white', ec=UP, lw=.5, zorder=5))
            ax.add_patch(Circle((x, s*y), 1.5, fc=BUY, ec=BUY, zorder=6))
    gx = MOTOR['gb_x']
    box(ax, gx[0], -MOTOR['gb_y'], gx[1], MOTOR['gb_y'], fc='#d4ac6e', ec='#7e5109', lw=.7, z=6)
    box(ax, MOTOR['can_x'][0], -MOTOR['can_r'], MOTOR['can_x'][1], MOTOR['can_r'], fc='#bfc9ca', ec=INK, lw=.7, z=6)
    box(ax, MOTOR['can_x'][0] - MOTOR['term'], -3, MOTOR['can_x'][0], 3, fc='#e5e8e8', ec=INK, lw=.5, z=6)
    for s in (1, -1):                                  # push screws
        box(ax, LUG['x'][0] - 3, s*30 - 1.5, SLIDE['x'][0] - 1.5, s*30 + 1.5, fc=BUY_L, ec=BUY, lw=.4, z=6)
    for x, y in PAD_XY:
        ax.add_patch(Circle((x, y), PAD['bore_r'] - 1.2, fc=BUY, ec=BUY, zorder=6))
    for r, a in TH_HUB:
        x, y = X.polar(r, a)
        ax.add_patch(Circle((x, y), WASH12['d']/2, fc='#d5d8dc', ec=BUY, lw=.4, zorder=4))
        ax.add_patch(Circle((x, y), 2.0, fc=BUY, ec=BUY, zorder=5))
    for x, y in ARM_BOLTS:
        ax.add_patch(Circle((x, y), 3.3, fc='white', ec=ARMC, lw=.6, zorder=6))
    x0, x1 = ARM_X0 + ARM_BASE['x'][0], ARM_X0 + ARM_BASE['x'][1]
    patch(ax, [(x0, -ARM_BASE['y']), (x1, -ARM_BASE['y']), (x1, ARM_BASE['y']), (x0, ARM_BASE['y'])], fc='none', ec=ARMC, lw=.9, ls='--', z=7)
    ax.add_patch(Circle((0, 0), T104['r_in'], fc='white', ec=UP, lw=.5, zorder=5))
    ax.add_patch(Circle((0, 0), 1.8, fc=GREEN, ec=GREEN, zorder=6))


def plan_view(ax):
    plan_r3(ax)
    for s in (1, -1):
        ax.annotate('', (s*178, 18), (s*178, 0), arrowprops=dict(arrowstyle='-|>', lw=1.0, color=INK))
        ax.text(s*178 + s*8, 4, 'A', fontsize=9, weight='bold', ha='center')
    ax.plot([-182, 182], [0, 0], color=INK, lw=.6, ls='-.', zorder=9)
    k = dict(fs=6.6)
    note(ax, (ARM_X0 + 70, ARM_BASE['y']), (40, 122), 'ARM60 base (existing, dashed):\n4 M6 bolts on the ribs', color=ARMC, relpos=(0, .5), **k)
    note(ax, (60, -RIB_Y[1]), (40, -100), 'T101 ribs at Y ±65', color=UP, relpos=(0, .5), **k)
    note(ax, (-95, 14), (-135, 122), 'T102 slide and motor', color=UP, relpos=(.3, 0), va='bottom', **k)
    note(ax, PAD_XY[0], (-135, 98), 'T103 drag pads (2)', color=UP, relpos=(.5, 0), va='bottom', **k)
    note(ax, X.polar(22.5, 45), (-40, 122), 'hub well: 8 × M4 on Ø45', color=BUY, relpos=(.6, 0), va='bottom', **k)
    note(ax, (-118, -30), (-135, -100), 'push screws (2)', color=BUY, relpos=(.3, 1), va='top', **k)
    note(ax, X.polar(RING_TIP, -55), (40, -122), 'ring gear Ø123 below (dashed)', color=NEW, relpos=(.2, 1), va='top', **k)
    ax.annotate('front', (222, -184), (182, -184), fontsize=8.5, weight='bold', va='center', arrowprops=dict(arrowstyle='->', lw=1))
    ax.set_xlim(-214, 224); ax.set_ylim(-200, 200); ax.set_aspect('equal'); ax.axis('off')


def text_blocks(fig, x, y, blocks, fs=8.2, lh=.0124, tab=.014, head_fs=10.3):
    for head, items in blocks:
        fig.text(x, y, head, fontsize=head_fs, weight='bold', color=INK, va='top'); y -= .023
        for tag, text in items:
            fig.text(x, y, tag, fontsize=fs, weight='bold', color=INK, va='top')
            fig.text(x + tab, y, text, fontsize=fs, color='#2c3e50', va='top', linespacing=1.3)
            y -= lh*(text.count('\n') + 1) + .0055
        y -= .006
    return y


def header(fig, sheet, title, sub):
    fig.text(.02, .968, f'X1 turntable  —  concept R3, sheet {sheet} of 4: {title}', fontsize=17, weight='bold', color=INK)
    fig.text(.02, .947, sub, fontsize=9.6, color='#40585e')
    fig.text(.985, .006, ISSUE, fontsize=7.6, color=GREY, ha='right')


def sheet1(pdf, est):
    fig = plt.figure(figsize=FIG)
    header(fig, 1, 'arrangement against sway', 'CAD: X1_turntable_assembly.step. All dimensions in mm. Blue = new turntable prints, '
           'orange = new chassis-side prints, purple dashed = the existing ARM60 base, grey dashed = body parts still to design. '
           'No custom metal parts.')
    section_aa(fig.add_axes([.005, .30, .60, .62]))
    plan_view(fig.add_axes([.60, .40, .40, .53]))
    s, p, d = est['stiffness'], est['play'], est['drag']
    blocks_l = [
        ('What R3 does against sway', [
            ('1', f"Stiff upper: the T101 centre frame carries the arm base and the counterweight on two 27 mm ribs over the bearing,\n"
                  f"like a real excavator's upper frame. About {s['ratio']:.0f} × stiffer than a 6 mm deck plate (sheet 2)."),
            ('2', 'Less gear play: the ring gear is centred on the bearing (Ø95.2 bore), and the motor slide sets the pinion mesh to\n'
                  f"about 0.1 mm. Play at the turntable drops from {p['turntable_deg_before'][0]:.2f}–{p['turntable_deg_before'][1]:.2f}° "
                  f"to {p['turntable_deg_after'][0]:.2f}–{p['turntable_deg_after'][1]:.2f}° (sheet 3)."),
            ('3', f"No rattle: two felt drag pads ({d['torque_Nm']:.2f} N·m, about {100*d['share_of_rated_swing_torque']:.0f}% of the rated "
                  'swing torque) hold the upper against one side of\nthe play that is left, so knocks and arm moves cannot shake it.'),
            ('4', 'Joints that stay tight in plastic: Ø12 washers spread the clamp, spring washers follow the plastic as it creeps, and\n'
                  'the RU66 now sits on nuts under the X-frame instead of heat-set inserts.')]),
    ]
    blocks_r = [
        ('Still not structural (approved)', [
            ('•', 'Swing stops: set a 0.3–0.5 s speed ramp in the swing motor driver.'),
            ('•', "Measure the output play on one of the track motors: the swing motor is the same JGY-370."),
            ('•', 'Re-tighten both bearing joints after about 1 h and 10 h of running.')]),
        ('Decided (issue 2)', [
            ('•', f"Swing motor: the tracks' {JGY['model']}, a third of the same motor (sheet 3)."),
            ('•', f"Slip ring: {SLIPRING['ways']}-way 2 A. Only the two track motors' 4 leads cross the joint; 2 rings spare (sheet 4).")]),
        ('No custom metal parts', [
            ('•', 'Every new part is printed. The rest is bought standard hardware:\nscrews, nuts, washers, heat-set inserts, 2 small springs, felt.'),
            ('•', 'The full list is on sheet 4.')]),
    ]
    text_blocks(fig, .015, .27, blocks_l)
    text_blocks(fig, .62, .37, blocks_r)
    fig.text(.02, .006, 'Sources: X1 CAD (x1_parts.py); THK RU66 catalogue; ARM60 base (excavator_arm_60mm/source/build_arm.py: plate 132 × 164 × 10, '
                        '4 × M6 at X −32/76, Y ±65); JGY-370 and Pololu #1999 from the J9 model; concepts R1 and R2.', fontsize=7.4, color=GREY)
    pdf.savefig(fig); fig.savefig(PNG[0], dpi=110); plt.close(fig)


# ------------------------------------------------------------------ sheet 2: T101 and T104
def t101_plan(ax):
    ax.set_title('T101 CENTRE FRAME, plan (front to the right)', fontsize=10.5, loc='left', weight='bold')
    draw_shape(ax, frame_base(), fc='#cfe2f3', ec=UP, lw=.7, z=2)
    draw_shape(ax, frame_walls(), fc='#7fb3d5', ec=UP, lw=.7, z=3, hole_fc='#cfe2f3')
    for x, y in ARM_BOLTS:
        ax.add_patch(Circle((x, y), 3.3, fc='white', ec=UP, lw=.6, zorder=5))
        nx = x
        patch(ax, [(nx - 5.1, np.sign(y)*ARM_BLOCK['y'][0]), (nx + 5.1, np.sign(y)*ARM_BLOCK['y'][0]), (nx + 5.1, y), (nx - 5.1, y)],
              fc='none', ec=UP, lw=.5, ls='--', z=5)
    for r, a in TH_HUB:
        ax.add_patch(Circle(X.polar(r, a), 2.25, fc='white', ec=UP, lw=.5, zorder=5))
    for x, y in SLIDE['slots']:
        for s in (1, -1):
            ax.add_patch(Circle((x, s*y), 2.0, fc='#f7dc6f', ec='#b7950b', lw=.5, zorder=5))
    for x, y in PAD_XY:
        ax.add_patch(Circle((x, y), PAD['bore_r'], fc='white', ec=UP, lw=.5, zorder=5))
    for s in (1, -1):
        ax.add_patch(Circle((-142, s*30), 1.8, fc='#f7dc6f', ec='#b7950b', lw=.5, zorder=5))
        box(ax, LUG['x'][0], s*30 - 2.0, LUG['x'][1], s*30 + 2.0, fc='#f7dc6f', ec='#b7950b', lw=.5, z=5)
    # dimensions
    y0 = -95
    dim_h(ax, FR['x'][0], FR['x'][1], y0 - 10, '252 (fits a 256 bed)', side=-1, fs=7)
    dim_h(ax, FR['x'][0], 0, y0, '145', side=-1, fs=6.8)
    dim_h(ax, 0, FR['x'][1], y0, '107', side=-1, fs=6.8)
    dim_v(ax, 128, -FR['y'], FR['y'], '138 (148 over the arm blocks)', side=1, fs=6.8)
    dim_v(ax, 116, -65, 65, '130: rib and arm-bolt centres', side=1, fs=6.8)
    for x in (ARM_BOLTS[0][0], ARM_BOLTS[2][0]):
        ax.plot([x, x], [80, 92], color=LIGHT, lw=.5, ls='-.')
    dim_h(ax, ARM_BOLTS[0][0], ARM_BOLTS[2][0], 88, f"108: arm bolts at X {ARM_BOLTS[0][0]:g} and {ARM_BOLTS[2][0]:g}", fs=6.8)
    dim_h(ax, OPENING['x'][0], OPENING['x'][1], 50, f"{OPENING['x'][1] - OPENING['x'][0]:g}", fs=6.5)
    dim_v(ax, -60, -OPENING['y'], OPENING['y'], f"{2*OPENING['y']:.1f}", side=1, fs=6.5)
    ax.plot([-156, 136], [0, 0], color=LIGHT, lw=.5, ls='-.', zorder=1)
    ax.plot([0, 0], [-108, 100], color=LIGHT, lw=.5, ls='-.', zorder=1)
    for s, lab in ((1, 'B'), (-1, 'B')):
        ax.annotate('', (-2, s*96), (0, s*96), arrowprops=dict(arrowstyle='-|>', lw=1, color=INK))
    ax.text(-6, 98, 'B', fontsize=9, weight='bold'); ax.text(-6, -102, 'B', fontsize=9, weight='bold')
    k = dict(fs=6.7)
    note(ax, (0, WELL[1]), (-60, 82), 'hub well Ø60 / Ø68, 27 deep: hex-key\naccess to the 8 hub screws on Ø45', color=UP, ha='right', relpos=(1, .5), **k)
    note(ax, (-34, 0), (-252, 86), 'lead slot 10 wide: slip-ring\nleads out to the electronics', color=GREEN, relpos=(1, .5), **k)
    note(ax, (-82, 24), (-252, 62), 'motor opening 56 × 48.4:\nT102 slide body sits in it', color=UP, relpos=(1, .5), **k)
    note(ax, (-100, 30), (-252, 38), '4 × M3 inserts for\nthe slide clamps', color='#9a7d0a', relpos=(1, .5), **k)
    note(ax, (-117, -30), (-252, -24), 'push-screw lugs with\nM3 inserts (along X)', color='#9a7d0a', relpos=(1, .5), **k)
    note(ax, PAD_XY[1], (-252, -50), 'T103 pad housings Ø14,\nbore Ø8, M6 insert on top', color=UP, relpos=(1, .5), **k)
    note(ax, (-143, -40), (-252, -80), 'rear bulkhead: Ø20 window for\nthe motor end; 2 M4 nuts for\nthe counterweight', color=UP, relpos=(1, .5), **k)
    note(ax, (ARM_BOLTS[2][0], -60), (40, -78), 'arm blocks 14 × 18: Ø6.6 hole, M6 nut\npocket open inboard (dashed)', color=UP, relpos=(0, .5), **k)
    ax.set_xlim(-254, 150); ax.set_ylim(-118, 104); ax.set_aspect('equal'); ax.axis('off')


def t101_side(ax):
    ax.set_title('T101 side view, outer face of the right rib (front to the right)', fontsize=10.5, loc='left', weight='bold')
    hu = dict(fc='#eaf2f8', ec=UP, lw=.8, z=2)
    box(ax, FR['x'][0], BASE_Z[0], FR['x'][1], BASE_Z[1], **hu)
    box(ax, FR['x'][0], BASE_Z[1], FR['x'][1], TOPZ, fc='#7fb3d5', ec=UP, lw=.8, z=2)
    for x, y in ARM_BOLTS[::2]:
        box(ax, x - ARM_BLOCK['dx'], BASE_Z[0], x + ARM_BLOCK['dx'], TOPZ, fc='#5499c7', ec=UP, lw=.8, z=3)
        box(ax, x - 3.3, BASE_Z[0] + 2, x + 3.3, TOPZ, fc='none', ec=UP, lw=.5, ls='--', z=4)
        box(ax, x - 5.1, ARM_BLOCK['nut_z'][0], x + 5.1, ARM_BLOCK['nut_z'][1], fc='none', ec=UP, lw=.5, ls='--', z=4)
    t104_cut(ax, prongs=(1, -1), lw=.7)
    for zz, dz, t in ((TOPZ, 0, 'Z 136: arm mounting plane'), (BASE_Z[1], 0, 'Z 109'), (BASE_Z[0], 1.8, 'Z 103'), (TT_Z, -1.2, 'Z 100'),
                      (T104['spigot_z0'], -2.4, 'Z 95'), (T104['prong']['z0'], 0, 'Z 83.5')):
        ax.plot([FR['x'][1] + 2, FR['x'][1] + 4, FR['x'][1] + 6], [zz, zz, zz + dz], color=GREY, lw=.6)
        ax.text(FR['x'][1] + 7, zz + dz, t, fontsize=6.5, color=GREY, va='center')
    k = dict(fs=6.7)
    note(ax, (-9, 128), (10, 156), 'arm blocks: M6 × 40 down from the ARM60\nbase into a nut in the inboard pocket', color=UP, relpos=(0, .5), **k)
    note(ax, (-120, 128), (-140, 156), 'rib 8 thick, 27 high', color=UP, relpos=(.2, .5), **k)
    note(ax, (12, 92), (40, 78), 'T104 below (separate print)', color=UP, relpos=(0, .5), **k)
    ax.set_xlim(-150, 150); ax.set_ylim(70, 164); ax.set_aspect('equal'); ax.axis('off')


def section_bb(ax):
    ax.set_title("SECTION B–B at X 0, seen from the front (machine's left on the right)", fontsize=10.5, loc='left', weight='bold')
    C.carbody_section(ax, bosses=False)
    R2.collar(ax, lw=.7)
    C.ru66_section(ax, rollers=True)
    ring_gear_cut(ax)
    R2.ring(ax, screw=False, lw=.7, leads=False)
    hd = dict(fc=TPU_L, ec=TPU, hatch='....', lw=.6, z=7)
    rb = R2.DOG['bore_d']/2 + .15
    both(ax, rb, R2.DOG['r_out'], R2.DOG['z0'], R2.ROTOR_Z[1], **hd)
    both(ax, R2.DOG['hole_d']/2, R2.DOG['r_out'], R2.ROTOR_Z[1], R2.DOG['z1'], **hd)
    both(ax, R2.DOG['r_out'], R2.DOG['lug_r'], R2.DOG['lug_z0'], R2.DOG['z1'], **hd)
    t104_cut(ax, prongs=())
    hu = dict(fc=UP_L, ec=UP, hatch='////', lw=.7, z=4)
    both(ax, T104['r_in'], FR['y'], *BASE_Z, **hu)
    both(ax, *WELL, BASE_Z[1], TOPZ, **hu)
    both(ax, *RIB_Y, BASE_Z[1], TOPZ, **hu)
    for s in (1, -1):
        hub_screw(ax, s*RU_IN_PCD/2)
        patch(ax, [(s*FR['y'], BASE_Z[1]), (s*104, BASE_Z[1]), (s*104, BASE_Z[1] + 6), (s*FR['y'], BASE_Z[1] + 6)], fc='#f8f9f9', ec=GREY, lw=.6, ls='--', z=1)
    box(ax, -ARM_BASE['y'], TOPZ, ARM_BASE['y'], TOPZ + ARM_BASE['t'], fc='#f4ecf7', ec=ARMC, lw=.8, ls='--', z=2)
    ax.plot([0, 0], [R2.ROTOR_Z[1], 132], color=GREEN, lw=1.3, zorder=9)
    k = dict(fs=6.7)
    note(ax, (RU_IN_PCD/2 + 3.5, BASE_Z[1] + 4), (8, 168), '8 × M4 × 20 into the RU66 inner ring, each\nwith a DIN 6796 spring washer on a Ø12\nDIN 9021 washer',
         color=BUY, relpos=(0, .5), **k)
    note(ax, (-32, 125), (-44, 160), 'hub well', color=UP, ha='right', relpos=(1, .5), **k)
    note(ax, (-65, 128), (-74, 152), 'ribs', color=UP, ha='right', relpos=(1, .5), **k)
    note(ax, (-60, TOPZ + 10), (-64, 172), 'ARM60 base (existing)', color=ARMC, ha='right', relpos=(1, .5), **k)
    ax.text(-102, BASE_Z[1] + 9, 'side deck', fontsize=6.7, color=GREY)
    note(ax, (-25, 101.5), (-62, 74), 'T104 flange 3 mm, clamped\nwith T101 on the inner ring', color=UP, ha='right', relpos=(1, .5), **k)
    note(ax, (9, 87), (62, 72), 'R2 dog lugs (TPU),\nin this cut', color=TPU, relpos=(0, .5), **k)
    ax.set_xlim(-104, 104); ax.set_ylim(62, 180); ax.set_aspect('equal'); ax.axis('off')


def t104_view(ax):
    ax.set_title('T104 HUB ADAPTER, from below', fontsize=10.0, loc='left', weight='bold')
    ax.add_patch(Circle((0, 0), T104['r_out'], fc=UP_L, ec=UP, lw=.8, zorder=1))
    ax.add_patch(Circle((0, 0), T104['spigot_r'], fc='#a9cce3', ec=UP, lw=.7, zorder=2))
    for a in (0, 180):
        ax.add_patch(Wedge((0, 0), T104['prong']['ro'], a - T104['prong']['width_deg']/2, a + T104['prong']['width_deg']/2,
                           width=T104['prong']['ro'] - T104['prong']['ri'], fc='#5499c7', ec=UP, lw=.7, zorder=3))
    ax.add_patch(Circle((0, 0), T104['r_in'], fc='white', ec=UP, lw=.7, zorder=4))
    for r, a in TH_HUB:
        ax.add_patch(Circle(X.polar(r, a), T104['hole_r'], fc='white', ec=UP, lw=.6, zorder=4))
    k = dict(fs=6.6)
    note(ax, (T104['r_out']*.7, -T104['r_out']*.7), (34, -40), 'flange Ø59 × 3: touches\nonly the inner ring (ds max)', color=UP, relpos=(0, .5), **k)
    note(ax, (T104['spigot_r']*.7, T104['spigot_r']*.7), (34, 40), 'spigot Ø34.6 × 5 in\nthe RU66 bore', color=UP, relpos=(0, .5), **k)
    note(ax, (9, 0), (34, 12), 'prongs R 7.5–11, 50°,\n11.5 long (R2)', color=UP, relpos=(0, .5), **k)
    note(ax, X.polar(22.5, 135), (-34, 40), '8 × Ø4.5 on Ø45', color=UP, ha='right', relpos=(1, .5), **k)
    note(ax, (-5, -5), (-34, -40), 'Ø15 lead hole', color=UP, ha='right', relpos=(1, .5), **k)
    ax.set_xlim(-76, 92); ax.set_ylim(-52, 52); ax.set_aspect('equal'); ax.axis('off')


def sheet2(pdf, est):
    fig = plt.figure(figsize=FIG)
    header(fig, 2, 'T101 centre frame and T104 hub adapter', 'Printed PETG. Concept dimensions in mm; Z is height above the ground, '
           'X forward and Y to the left of the swing axis, with the turntable at 0°.')
    t101_plan(fig.add_axes([.005, .50, .56, .41]))
    t101_side(fig.add_axes([.005, .27, .56, .22]))
    section_bb(fig.add_axes([.555, .52, .44, .41]))
    t104_view(fig.add_axes([.60, .27, .26, .23]))
    s, j = est['stiffness'], est['top_joint']
    rows = [('', '6 mm deck plate', 'T101'),
            ('Bending stiffness I (mm⁴)', f"{s['I_plate_mm4']:,.0f}", f"{s['I_T101_mm4']:,.0f}"),
            ('Sag at the counterweight', f"{s['sag_plate_mm']:.2f} mm", f"{s['sag_T101_mm']:.3f} mm"),
            ('Bounce frequency', f"{s['f_plate_Hz']:.0f} Hz", f"{s['f_T101_Hz']:.0f} Hz")]
    x0, y = .02, .245
    fig.text(x0, y, 'How stiff (estimate)', fontsize=10.3, weight='bold', color=INK, va='top'); y -= .024
    for i, r in enumerate(rows):
        for c, w in zip(r, (0, .14, .215)):
            fig.text(x0 + w, y, c, fontsize=8.0, color=INK if i == 0 else '#2c3e50', weight='bold' if i == 0 else 'normal', va='top')
        y -= .0145
    fig.text(x0, y - .002, wrap(f"{CW['mass']} kg counterweight {s['lever_mm']:.0f} mm behind the hub well; E = {E_PETG/1000:.1f} GPa; "
                                'T101 cut through the motor opening, its weakest place. The ARM60 base closes the front of the channel into '
                                'a box; the rear bulkhead and counterweight close the rear.', 62), fontsize=7.3, color=GREY, va='top', linespacing=1.25)
    text_blocks(fig, .30, .245, [
        ('Hub joint (top of the bearing)', [
            ('•', f"8 × M4 × 20 through T101 (6) and T104 (3) into the RU66 inner ring: {TT_Z - (BASE_Z[1] + DISC['h'] + WASH12['t'] - TOP_SCREW['L']):.1f} of thread."),
            ('•', f"Tighten to about 0.3 N·m: about {PRELOAD_N:.0f} N each. Under the Ø12 washers that is {j['pressure_MPa']:.1f} MPa on the plastic."),
            ('•', f"The joint opens only above about {j['opening_moment_Nm']:.0f} N·m; the 60 mm excavator's upper and arm give {j['static_moment_Nm']:.1f} N·m.")]),
        ('Printing', [
            ('•', 'T101: base plate down, no supports; 252 × 148 × 33. Solid within 10 mm of every bolt; elsewhere 4 walls, 30% infill.\n'
                  'Teardrop the Ø20 window and the horizontal nut pockets.'),
            ('•', 'T104: flange face down, so the spigot and prongs grow upwards. Solid.')]),
    ], fs=8.0, lh=.0122, tab=.012)
    fig.text(.88, .45, wrap('T104 is a separate print because the spigot and prongs hang below T101: printed in one piece, T101 '
                            'would need supports under its whole base plate.', 30), fontsize=7.4, color=GREY, va='top', linespacing=1.25)
    fig.text(.02, .006, 'Stiffness and joint numbers are hand estimates (beam theory, rigid bolts), not FEA; printed PETG properties vary.',
             fontsize=7.4, color=GREY)
    pdf.savefig(fig); fig.savefig(PNG[1], dpi=110); plt.close(fig)


# ------------------------------------------------------------------ sheet 3: swing drive
def detail_d(ax):
    ax.set_title('DETAIL D: the pinion on the T102 slide, on the centreline (front to the right)', fontsize=10.5, loc='left', weight='bold')
    hx = dict(fc=XF_L, ec=XFE, hatch='////', lw=.6, z=3)
    box(ax, -150, PLATE_Z0, -X.BODY_R, TOP_Z, fc='#fbf1cf', ec='#d4ac0d', lw=.5, ls='--', z=1)
    box(ax, -X.BODY_R, PLATE_Z0, -RU_D/2 + .01, TOP_Z, **hx)
    ax.text(-140, 80.5, 'leg top Z 85 (where the legs cross the pinion path)', fontsize=6.3, color='#9a7d0a', va='bottom')
    C.ru66_section(ax, rollers=False)
    ring_gear_cut(ax)
    ring_gear_screws(ax, sides=(-1,))
    frame_cut_xz(ax, behind=True)
    slide_cut(ax)
    motor_side(ax)
    box(ax, LUG['x'][0] - 3, LUG['screw_z'] - 1.5, SLIDE['x'][0], LUG['screw_z'] + 1.5, fc='none', ec=BUY, lw=.6, ls='--', z=9)
    R2.clip_to(ax, -150, -24, 56, 146)
    zt = MOTOR['gb_z'][1] + 4
    for s in (1, -1):
        ax.annotate('', (PX + s*14, zt), (PX + s*1, zt), arrowprops=dict(arrowstyle='->', lw=.9, color=UP), zorder=10)
    ax.text(PX, zt + 1.2, 'slide with motor: ±2', fontsize=6.4, color=UP, ha='center', va='bottom', zorder=10)
    for zz, t in ((GB_FACE, 'Z 109 gearbox face'), (HUB_Z[1], 'Z 102 hub flange'), (PIN_Z[1], 'Z 97 ring-gear top'), (PIN_Z[0], 'Z 87'), (TOP_Z, 'Z 85')):
        ax.plot([-24, -21], [zz, zz], color=GREY, lw=.6, zorder=11)
        ax.text(-20.5, zz, t, fontsize=6.3, color=GREY, va='center', zorder=11)
    k = dict(fs=6.7)
    note(ax, (-118, LUG['screw_z']), (-150, 150), 'push screw M3 × 12 (behind the cut), in\nan insert in a lug; backs the slide outward',
         color=BUY, relpos=(.3, 0), va='bottom', **k)
    note(ax, (-90, 106), (-150, 70), 'T102 slide body, 6 thick, flush with\nthe base plate; 4 gearbox screws\nM3 × 8 button head (ISO 7380) from\nbelow in counterbores; pockets on\ntop for the gearbox screw bosses',
         color=UP, relpos=(.5, 1), va='top', **k)
    note(ax, (-80, 92), (-100, 58), 'T105 pinion, on the Pololu\nhub (4 × M3, heads flush)', color=UP, relpos=(.5, 1), va='top', **k)
    note(ax, (-55, 90), (-60, 58), 'X103 ring gear', color=NEW, relpos=(.5, 1), va='top', **k)
    note(ax, (-43.8, 118), (-60, 152), 'T103 drag pad (behind the cut)', color=UP, relpos=(.5, 0), va='bottom', **k)
    ax.set_xlim(-152, 2); ax.set_ylim(54, 158); ax.set_aspect('equal'); ax.axis('off')


def section_cc(ax):
    ax.set_title("SECTION C–C through the pinion axis (X −75), seen from the rear", fontsize=10.5, loc='left', weight='bold')
    hu = dict(fc=UP_L, ec=UP, hatch='////', lw=.7, z=4)
    both(ax, OPENING['y'], FR['y'], *BASE_Z, **hu)
    both(ax, *RIB_Y, BASE_Z[1], TOPZ, **hu)
    hs = dict(fc=UP2_L, ec=UP, hatch='\\\\\\\\', lw=.7, z=5)
    both(ax, SLIDE['hole_r'], SLIDE['y'], *SLIDE['z'], **hs)
    both(ax, *SLIDE['ear_y'], *SLIDE['ear_z'], **hs)
    for s in (1, -1):
        x = s*SLIDE['slots'][0][1]
        box(ax, x - 2.75, SLIDE['ear_z'][1], x + 2.75, SLIDE['ear_z'][1] + 3, fc='none', ec=BUY, lw=.5, ls='--', z=8)
        box(ax, x - 1.5, BASE_Z[0], x + 1.5, SLIDE['ear_z'][1], fc='none', ec=BUY, lw=.5, ls='--', z=8)
        box(ax, x - 2.0, BASE_Z[0], x + 2.0, BASE_Z[1], fc='none', ec='#b7950b', lw=.5, ls='--', z=8)
    box(ax, -MOTOR['gb_y'], MOTOR['gb_z'][0], MOTOR['gb_y'], MOTOR['gb_z'][1], fc='#d4ac6e', ec='#7e5109', lw=.8, z=6)
    ax.add_patch(Circle((0, MOTOR['can_z']), MOTOR['can_r'], fill=False, ec=INK, lw=.6, ls='--', zorder=7))
    box(ax, -3, SHAFT_TIP, 3, GB_FACE, fc='#566573', ec=INK, lw=.5, z=7)
    box(ax, -HUB['flange_r'], HUB_Z[0], HUB['flange_r'], HUB_Z[1], fc=BUY_L, ec=BUY, lw=.7, z=6)
    box(ax, -HUB['boss_r'], HUB_Z[1], HUB['boss_r'], HUB_Z[2], fc=BUY_L, ec=BUY, lw=.7, z=6)
    hp = dict(fc=UP_L, ec=UP, hatch='xxx', lw=.8, z=5)
    both(ax, 3.5, PIN_TIP, *PIN_Z, **hp)
    ax.plot([-80, 80], [TOP_Z, TOP_Z], color='#d4ac0d', lw=.6, ls='--')
    ax.text(78, TOP_Z - .6, 'leg-top level Z 85', fontsize=6.3, color='#9a7d0a', ha='right', va='top')
    k = dict(fs=6.7)
    note(ax, (30, SLIDE['ear_z'][1] - 1), (73, 127), 'ears 12 wide, 6 thick, on the\nbase plate: slots 7.4 × 3.4\nalong X; M3 × 12 + washer\ninto inserts in the base plate',
         color=UP, relpos=(0, .5), **k)
    note(ax, (20, 106), (73, 98), 'slide body guided by the\nopening sides (0.2 per side)', color=UP, relpos=(0, .5), **k)
    note(ax, (-65, 125), (-86, 140), 'rib', color=UP, ha='right', relpos=(1, .5), **k)
    ax.set_xlim(-90, 112); ax.set_ylim(80, 148); ax.set_aspect('equal'); ax.axis('off')


def detail_e(ax):
    ax.set_title('DETAIL E: T103 drag pad, section', fontsize=10.5, loc='left', weight='bold')
    hu = dict(fc=UP_L, ec=UP, hatch='////', lw=.7, z=3)
    r0, r1 = PAD['bore_r'], PAD['housing_r']
    both(ax, r0, 15, *BASE_Z, **hu)
    both(ax, r0, r1, BASE_Z[1], PAD['top'], **hu)
    both(ax, PAD['lip_r'], r0 + .01, *PAD['lip'], **hu)
    zi = PAD['top'] - PAD['insert']['length']
    both(ax, 3.0, PAD['insert']['r'], zi, PAD['top'], fc='#f7dc6f', ec='#b7950b', lw=.5, z=4)
    box(ax, -3.0, PAD['screw_tip'], 3.0, PAD['screw_tip'] + 8, fc=BUY_L, ec=BUY, lw=.6, z=5)
    hp = dict(fc=UP2_L, ec=UP, hatch='\\\\\\\\', lw=.7, z=5)
    box(ax, -PAD['head_r'], PAD['head'][0], PAD['head_r'], PAD['head'][1], **hp)
    box(ax, -PAD['stem_r'], PAD['felt'][1], PAD['stem_r'], PAD['head'][0], **hp)
    box(ax, -PAD['felt_r'], PAD['felt'][0], PAD['felt_r'], PAD['felt'][1], fc='#f5eef8', ec='#7d3c98', lw=.7, hatch='ooo', z=6)
    z = np.linspace(PAD['head'][1], PAD['screw_tip'], 13)
    rs = PAD['spring']['od']/2 - PAD['spring']['wire']/2
    ax.plot([(-rs if i % 2 else rs) for i in range(len(z))], z, color=INK, lw=.9, zorder=6)
    box(ax, -15, RG['z'][0] + 4, 15, RG['z'][1], fc=NEW_L, ec=NEW, hatch='xxx', lw=.7, z=2)
    k = dict(fs=6.6)
    note(ax, (2, PAD['top'] - 3), (17, 130), 'M6 × 8 set screw in\nan M6 insert (Ø8 hole)', color=BUY, relpos=(0, .5), **k)
    note(ax, (rs, 115), (17, 121.5), f"spring Ø{PAD['spring']['od']:g} × {PAD['spring']['free']:g},\n~{PAD['spring']['rate']:g} N/mm: ~{PAD['spring']['rate']*(PAD['spring']['free'] - PAD['screw_tip'] + PAD['head'][1]):.0f} N",
         color=INK, relpos=(0, .5), **k)
    note(ax, (r0 - .5, 106.5), (17, 112.5), 'plunger T103, head\nØ7.6 × 4: drops in\nthrough the insert hole', color=UP, relpos=(0, .5), **k)
    note(ax, (PAD['lip_r'], 103.5), (17, 104.5), 'lip Ø6.8 keeps\nthe plunger', color=UP, relpos=(0, .5), **k)
    note(ax, (PAD['felt_r'], 98.5), (17, 98.5), 'felt Ø8 × 3, glued', color='#7d3c98', relpos=(0, .5), **k)
    note(ax, (-12, 92), (-17, 86.5), 'X103 drag track', color=NEW, ha='right', relpos=(1, .5), **k)
    note(ax, (-12, 106), (-17, 117), 'T101 base\nplate and\nhousing Ø14', color=UP, ha='right', relpos=(1, .5), **k)
    ax.set_xlim(-34, 40); ax.set_ylim(84, 134); ax.set_aspect('equal'); ax.axis('off')


def detail_f(ax):
    ax.set_title('DETAIL F: X103 ring gear, radial section', fontsize=10.5, loc='left', weight='bold')
    hx = dict(fc=XF_L, ec=XFE, hatch='////', lw=.6, z=3)
    box(ax, 40, PLATE_Z0, 64, TOP_Z, **hx)
    box(ax, X.BODY_R - X.BODY_WALL, 70, X.BODY_R, PLATE_Z0, **hx)
    box(ax, 40, MR_Z0, MR_R1, PLATE_Z0, **hx)
    hb = dict(fc=BRG_L, ec=BRG, hatch='\\\\\\\\', lw=.6, z=4)
    box(ax, 40, TOP_Z, RU_D/2, TT_Z, **hb)
    hn = dict(fc=NEW_L, ec=NEW, hatch='xxx', lw=.8, z=5)
    box(ax, RG['bore_r'], RG['z'][0], RING_TIP, RG['z'][1], **hn)
    ax.plot([RING_ROOT]*2, RG['z'], color=NEW, lw=.5, zorder=6)
    ring_gear_screws(ax, sides=(1,))
    box(ax, RG['track'][0], RG['z'][1], RG['track'][1], RG['z'][1] + .6, fc='#f5eef8', ec='#7d3c98', lw=.5, z=6)
    k = dict(fs=6.6)
    note(ax, (RU_D/2, 92), (26, 104), 'bore Ø95.2 on the RU66\nouter ring Ø95: centred\nto 0.1 mm', color=NEW, ha='right', relpos=(1, .5), **k)
    note(ax, (53.5, 97.6), (60, 106), 'drag track R 49.5–57.5:\nno screw heads in it', color='#7d3c98', relpos=(0, .5), **k)
    note(ax, (51, 80), (70, 76), 'M3 × 12 countersunk from\nbelow, into an M3 insert;\nkey between mount ring\nand wall (gap 6)', color=BUY, relpos=(0, .5), **k)
    note(ax, (RING_TIP - 1, 91), (70, 92), 'teeth m1.5, 80, tip Ø123', color=NEW, relpos=(0, .5), **k)
    ax.set_xlim(8, 100); ax.set_ylim(66, 112); ax.set_aspect('equal'); ax.axis('off')


def sheet3(pdf, est):
    fig = plt.figure(figsize=FIG)
    header(fig, 3, 'swing drive: pinion slide, ring gear and drag pads', f"Swing motor: the tracks' {JGY['model']}. Gears m1.5, 80 : 20 "
           '(R1). R3 changes how the parts are located, so the mesh can be set and stays set.')
    detail_d(fig.add_axes([.005, .44, .52, .465]))
    section_cc(fig.add_axes([.53, .64, .46, .29]))
    detail_f(fig.add_axes([.53, .37, .24, .26]))
    detail_e(fig.add_axes([.775, .355, .22, .29]))
    p, d = est['play'], est['drag']
    text_blocks(fig, .02, .41, [
        ('Setting the mesh (once, then after the first hours)', [
            ('1', 'Fit the motor on T102 on the bench: 4 × M3 × 8 button head from below. Fit the hub and the pinion.'),
            ('2', 'Slide back. Lower the slide into the opening; the pinion slides down into the ring gear.'),
            ('3', 'Put a strip of 80 g/m² paper (about 0.1 mm) between the teeth. Push the slide in until it\n'
                  'pinches, and tighten the 4 clamp screws.'),
            ('4', 'Turn the push screws in until they touch the ears; lock each with an M3 nut. Pull out\n'
                  'the paper, turn the upper by hand through a full turn: no tight spot.')]),
    ], fs=8.0, lh=.0122, tab=.012)
    rows = [('', 'R2', 'R3'),
            ('Ring-gear position', '±0.3 (6 screws only)', '±0.1 (bore on the RU66)'),
            ('Mesh play', f"{p['mesh_mm_before'][0]}–{p['mesh_mm_before'][1]} mm, as printed", f"~{p['mesh_mm_after'][0]} mm, set"),
            ('Gearbox play ÷ 4', f"{p['gearbox_deg_assumed'][0]/4:.2f}–{p['gearbox_deg_assumed'][1]/4:.2f}°", 'same: measure it'),
            ('At the turntable', f"{p['turntable_deg_before'][0]:.2f}–{p['turntable_deg_before'][1]:.2f}°", f"{p['turntable_deg_after'][0]:.2f}–{p['turntable_deg_after'][1]:.2f}°"),
            ('At the bucket, 0.5 m', f"{p['at_500mm_before'][0]:.1f}–{p['at_500mm_before'][1]:.1f} mm", f"{p['at_500mm_after'][0]:.1f}–{p['at_500mm_after'][1]:.1f} mm, only on reversing"),
            ('Rattle inside the play', 'free', f"held by {d['torque_Nm']:.2f} N·m of drag")]
    x0, y = .40, .41
    fig.text(x0, y, 'Play budget (estimate)', fontsize=10.3, weight='bold', color=INK, va='top'); y -= .024
    for i, r in enumerate(rows):
        for c, w in zip(r, (0, .10, .205)):
            fig.text(x0 + w, y, c, fontsize=7.9, color=INK if i == 0 else '#2c3e50', weight='bold' if i == 0 else 'normal', va='top')
        y -= .0142
    fig.text(x0, y - .002, wrap('JGY-370 output play 1–2° is an assumption (the vendor gives none). The gearbox play is the part '
                                'structure cannot remove; the drag pads stop it rattling.', 80), fontsize=7.2, color=GREY, va='top', linespacing=1.25)
    text_blocks(fig, .725, .33, [
        ('Drag pads', [
            ('•', f"2 pads × {d['force_per_pad_N']:.0f} N × μ {d['mu_assumed']} × R {d['radius_mm']:g} = {d['torque_Nm']:.2f} N·m,\n"
                  f"about {100*d['share_of_rated_swing_torque']:.0f}% of the {d['rated_swing_torque_Nm']:.2f} N·m rated swing torque."),
            ('•', f"μ is a guess: set the drag by pulling the upper round with\na spring scale at 100 mm from the axis: {d['pull_at_100mm_N']:.1f} N."),
            ('•', 'Too much drag only costs torque; too little lets it rattle.')]),
        ('Speed ramps (driver setting)', [
            ('•', 'Ramp the swing motor up and down over 0.3–0.5 s, so\nthe self-locking worm does not stop the upper dead.')]),
    ], fs=7.9, lh=.0122, tab=.012)
    sw = est['swing_motor']
    tt, mt = sw['turntable_torque_Nm'], sw['motor_torque_Nm']
    x0, y = .02, .27
    fig.text(x0, y, "Swing motor: the same as the tracks", fontsize=10.3, weight='bold', color=INK, va='top'); y -= .024
    rows = [('', 'At the motor shaft', f"At the turntable (× {sw['ratio']:g})"),
            ('Speed, no load / rated', f"{JGY['rpm'][0]:g} / {JGY['rpm'][1]:g} rpm",
             f"{sw['turntable_rpm_noload']:.1f} / {sw['turntable_rpm_rated']:.1f} rpm: a turn in {sw['seconds_per_turn'][0]:.0f}–{sw['seconds_per_turn'][1]:.0f} s"),
            ('Torque, rated', f"{JGY['t_rated_kgfcm']:g} kgf·cm = {mt['rated']:.2f} N·m", f"{tt['rated']:.2f} N·m (R1 sizing needs about {tt['needed']:g})"),
            ('Torque, stall', f"{JGY['t_stall_kgfcm']:g} kgf·cm = {mt['stall']:.2f} N·m",
             f"{tt['stall']:.1f} N·m: {sw['tooth_force_N']['stall']:.0f} N on a tooth, {sw['tooth_stress_MPa']['stall']:.0f} MPa"),
            (f"Driver limit {JGY['i_limit']:g} A", f"{mt['at_limit']:.2f} N·m",
             f"{tt['at_limit']:.1f} N·m: {sw['tooth_stress_MPa']['at_limit']:.0f} MPa in the teeth"),
            ('Current', f"{JGY['i_rated']:g} A rated, {JGY['i_stall']:g} A stall", 'own wires stay in the upper')]
    for i, r in enumerate(rows):
        for c, w in zip(r, (0, .105, .215)):
            fig.text(x0 + w, y, c, fontsize=7.8, color=INK if i == 0 else '#2c3e50', weight='bold' if i == 0 else 'normal', va='top')
        y -= .0142
    fig.text(x0, y - .002, wrap(f"Data: J9 motor choice (vendor table). Torques before gear losses; tooth stress by Lewis on the 10-wide pinion, "
                                f"PETG yields at about {PETG_YIELD:.0f} MPa. The {JGY['i_limit']:g} A limit assumes torque linear in current.", 92),
             fontsize=7.2, color=GREY, va='top', linespacing=1.25)
    text_blocks(fig, .40, .235, [
        ('Why the track motor suits the swing', [
            ('•', 'One part for all three drives: same Pololu hub, same M3 gearbox mounting, same\nmotor driver and settings, one spare motor covers everything.'),
            ('•', 'Its worm gearbox cannot be turned from the output, so the upper holds still on a slope\nwith the motor off. That is why it needs the speed ramp (right).'),
            ('•', 'Its output play is the largest item in the play budget: measure it on a track motor.')]),
    ], fs=7.9, lh=.0122, tab=.012)
    fig.text(.02, .006, 'Detail D: one push screw and one drag pad are behind the cut and drawn dashed. Section C–C: clamp screws are '
                        'off the cut and drawn dashed.', fontsize=7.4, color=GREY)
    pdf.savefig(fig); fig.savefig(PNG[2], dpi=110); plt.close(fig)


# ------------------------------------------------------------------ sheet 4: chassis side, slip ring, assembly, hardware
def view_below(ax):
    ax.set_title('VIEW G: X-frame from below, belly cover off (front to the right)', fontsize=10.5, loc='left', weight='bold')
    ax.add_patch(Circle((0, 0), X.BODY_R, fc='#fbf1cf', ec=XFE, lw=.6, zorder=0))
    ax.add_patch(Circle((0, 0), X.BODY_R - X.BODY_WALL, fc='#fdfaf0', ec=XFE, lw=.6, zorder=1))
    ax.add_patch(Wedge((0, 0), MR_R1, 0, 360, width=MR_R1 - MR_R0, fc=XF_L, ec=XFE, lw=.6, zorder=2))
    for a in X.OUTER_ANG:
        x, y = X.polar(RU_OUT_PCD/2, -a)
        ax.add_patch(Circle((x, y), WASH12['d']/2, fc='#d5d8dc', ec=BUY, lw=.5, zorder=3))
        hexa = [(x + 4.04*math.cos(math.radians(60*k + 30)), y + 4.04*math.sin(math.radians(60*k + 30))) for k in range(6)]
        patch(ax, hexa, fc='#566573', ec=INK, lw=.4, z=4)
    for a in RG['screw_ang']:
        x, y = X.polar(RG['screw_r'], -a)
        ax.add_patch(Circle((x, y), RG_SCREW['head_r'], fc=BUY, ec=INK, lw=.4, zorder=3))
    ax.add_patch(Circle((0, 0), R2.FLANGE_R, fc=SLIP_L, ec=SLIP, lw=.6, zorder=3))
    for a in R2.HOLE_ANG:
        c = X.polar(PCD_R, -a)
        ax.add_patch(Circle(c, R2.WASHER['d_out']/2, fc='#d5d8dc', ec=BUY, lw=.4, zorder=4))
        ax.add_patch(Circle(c, R2.SCREW['head_d']/2, fc=BUY, ec=BUY, lw=.4, zorder=5))
    ax.add_patch(Circle((0, 0), R2.BODY_R, fc='#85c1e9', ec=SLIP, lw=.6, zorder=4))
    for s in (1, -1):
        y_hole = s*(X.BODY_R - X.BODY_WALL/2)
        box(ax, -X.CABLE_HOLE['r'], y_hole - 3, X.CABLE_HOLE['r'], y_hole + 3, fc='white', ec=RED, lw=.6, z=3)
    k = dict(fs=6.6)
    note(ax, X.polar(RU_OUT_PCD/2, -22.5), (68, -30), '8 × M4 nut on a spring washer\nand a Ø12 washer (RU66 joint)', color=BUY, relpos=(0, .5), **k)
    note(ax, X.polar(RG['screw_r'], -60), (68, -54), '6 × M3 countersunk\n(ring gear X103)', color=BUY, relpos=(0, .5), **k)
    note(ax, X.polar(PCD_R, -120), (-68, -50), 'slip ring (R2):\n3 × M3 + washer', color=SLIP, ha='right', relpos=(1, .5), **k)
    note(ax, (-MR_R0 - 2, 10), (-68, 30), 'mount ring\nR 35–48', color=XFE, ha='right', relpos=(1, .5), **k)
    ax.set_xlim(-100, 112); ax.set_ylim(-66, 66); ax.set_aspect('equal'); ax.axis('off')


def slip_detail(ax):
    ax.set_title('DETAIL H: slip ring at the swing centre (R2 mount, R3 hub)', fontsize=10.5, loc='left', weight='bold')
    C.carbody_section(ax, bosses=False)
    R2.collar(ax)
    C.ru66_section(ax, rollers=False)
    R2.ring(ax)
    R2.dog(ax)
    t104_cut(ax, prongs=(1,))
    hu = dict(fc=UP_L, ec=UP, hatch='////', lw=.7, z=4)
    both(ax, T104['r_in'], 40, *BASE_Z, **hu)
    both(ax, *WELL, BASE_Z[1], 116, **hu)
    R2.rotor_leads(ax, z_top=116)
    k = dict(fs=6.6)
    note(ax, (-9, 86), (-63, 104), 'TPU dog on the rotor;\nlug cut on the left', color=TPU, ha='right', relpos=(1, .5), **k)
    note(ax, (10.5, 90), (63, 100), 'T104 prong,\ncut on the right', color=UP, relpos=(0, .5), **k)
    note(ax, (-18, 77), (-63, 72), 'collar Ø44 × 5, Ø22.4 bore\n(X-frame change)', color=NEW, ha='right', relpos=(1, .5), **k)
    note(ax, (11, 62), (63, 60), 'bought slip ring,\n6-way 2 A', color=SLIP, relpos=(0, .5), **k)
    note(ax, (17, 72), (63, 80), '3 × M3 × 8\n+ washer', color=BUY, relpos=(0, .5), **k)
    ax.set_xlim(-104, 100); ax.set_ylim(46, 118); ax.set_aspect('equal'); ax.axis('off')


HARDWARE = [
    ('Joint / part', 'Bought standard hardware', 'Qty'),
    ('RU66 to X-frame', 'M4 × 30 socket; M4 nut; DIN 6796 M4; DIN 9021 M4 (Ø12)', '8 each'),
    ('T101 + T104 to RU66', 'M4 × 20 socket; DIN 6796 M4; DIN 9021 M4 (Ø12)', '8 each'),
    ('X103 ring gear', 'M3 × 12 countersunk (ISO 10642); M3 heat-set insert', '6 each'),
    ('T102 slide clamps', 'M3 × 12 socket; M3 washer; M3 heat-set insert', '4 each'),
    ('T102 push screws', 'M3 × 12 socket; M3 nut (lock); M3 heat-set insert', '2 each'),
    ('JGY-370 on T102', 'M3 × 8 button head ISO 7380 (check the gearbox thread depth)', '4'),
    ('T105 pinion', 'Pololu #1999 hub; M3 × 10 socket, heads in counterbores', '1; 4'),
    ('T103 drag pads', 'spring Ø4.5 × 12, wire 0.5 (~1.2 N/mm); M6 × 8 set screw; M6 insert, Ø8 × 9; felt Ø8 × 3', '2 each'),
    ('ARM60 base', 'M6 × 40 socket; M6 nut; M6 washer', '4 each'),
    ('Counterweight', 'M4 × 12 socket; M4 nut', '2 each'),
    ('Slip ring (R2)', 'M3 × 8 socket; M3 washer; M3 heat-set insert', '3 each'),
]


def sheet4(pdf, results, est):
    fig = plt.figure(figsize=FIG)
    header(fig, 4, 'chassis side, slip ring, assembly and hardware', 'The X1 X-frame changes are modelled as X101 rev B. '
           'The slip ring and its collar are R2\'s, unchanged.')
    view_below(fig.add_axes([.005, .57, .44, .35]))
    slip_detail(fig.add_axes([.42, .57, .34, .35]))
    text_blocks(fig, .765, .91, [
        ('Changes to X101 (X-frame)', [
            ('1', 'Slip-ring collar under the top plate (R2).'),
            ('2', 'RU66: 8 plain Ø4.5 holes through the seat and\nmount ring; nuts below, instead of 8 M4 inserts.'),
            ('3', 'Ring gear: 6 Ø3.4 holes with countersinks\nfrom below at R 51; Ø7.2 scallops in the mount\nring and wall pass the heads.'),
            ('4', 'Reserve: pinion path R 58–92, Z 87–100; drag-\npad path R 49.5–57.5, Z 97–103; T104 inside\nthe RU66 bore down to Z 83.5.')]),
        ('New prints', [
            ('', 'X103 ring gear · T101 centre frame · T102 motor\nslide · T103 plunger × 2 · T104 hub adapter ·\nT105 pinion · TPU rotor dog (R2)')]),
    ], fs=7.8, lh=.0118, tab=.012)
    text_blocks(fig, .02, .545, [
        ('Assembly order', [
            ('1', 'X-frame upside down: slip ring into its collar with the dog on (R2). Leads through the passage.'),
            ('2', 'Ring gear X103 onto the seat area round the RU66 position; 6 × M3 countersunk from below.'),
            ('3', 'RU66 into the ring gear\'s bore onto the seat; 8 × M4 × 30 from above, nuts and washers below.\n'
                  'Tighten crosswise to about 0.3 N·m. Belly cover on after wiring (R2).'),
            ('4', 'T104 onto the inner ring (spigot in the bore, prongs past the dog\'s lugs), T101 on top. Feed the\n'
                  'rotor leads up the lead hole and out of the rear slot. 8 × M4 × 20 with washers, crosswise.'),
            ('5', 'Plungers into the empty insert holes, then the M6 inserts, the springs (through\n'
                  'the inserts) and the set screws, loose. Motor on T102 (sheet 3), slide in, set the mesh.'),
            ('6', 'Set the drag with a spring scale. Then the ARM60 base (4 × M6 × 40), counterweight, side decks.'),
            ('7', 'After about 1 h and 10 h of running: re-tighten both bearing joints and check the mesh.')]),
    ], fs=8.0, lh=.0122, tab=.012)
    y = text_blocks(fig, .02, .345, [
        ('Slip ring: why 6-way is enough', [
            ('•', 'Each ring ("way") is one separate wire through the turning joint. The number needed is the number of wires\n'
                  'that must cross between the chassis (lower) and the turntable (upper).'),
            ('•', 'Battery, receiver, all three motor drivers and the swing motor ride in the upper. Only the two track motors are\n'
                  'in the lower, so 4 wires cross: + and − for each.'),
            ('•', f"Current: a track motor draws {JGY['i_rated']:g} A running and {JGY['i_stall']:g} A at stall; each ring is rated {SLIPRING['amp']:g} A, "
                  'so one ring per wire is enough.'),
            ('•', '12-way only if more wires must cross later: encoders on the track motors (10 circuits in all), lights or\n'
                  'sensors on the chassis, or two rings in parallel per motor wire. Both sizes fit the same collar.')]),
    ], fs=8.0, lh=.0122, tab=.012)
    alloc = [('Ring', '1', '2', '3', '4', '5, 6'), ('Wire', 'left track +', 'left track −', 'right track +', 'right track −', 'spare')]
    for i, r in enumerate(alloc):
        for j, c in enumerate(r):
            fig.text(.032 + (0, .04, .11, .18, .255, .33)[j], y - .004 - i*.0145, c, fontsize=7.8,
                     color=INK if i == 0 or j == 0 else '#2c3e50', weight='bold' if i == 0 or j == 0 else 'normal', va='top')
    x0, y = .53, .545
    fig.text(x0, y, 'Bought standard hardware (no machined parts)', fontsize=10.3, weight='bold', color=INK, va='top'); y -= .024
    for i, r in enumerate(HARDWARE):
        for c, w in zip(r, (0, .105, .405)):
            fig.text(x0 + w, y, c, fontsize=7.5, color=INK if i == 0 else '#2c3e50', weight='bold' if i == 0 else 'normal', va='top')
        y -= .0132
    fig.text(x0, y - .002, f"Also bought: THK RU66, slip ring 6-way 2 A, ballast weights, and a third {JGY['model']}, as on the tracks.",
             fontsize=7.4, color=GREY, va='top')
    y -= .03
    fig.text(x0, y, 'Checks computed by this script', fontsize=10.3, weight='bold', color=INK, va='top'); y -= .022
    npass = sum(r['ok'] for r in results)
    r2 = R2.checks()
    fig.text(x0, y, wrap(f"{npass} of {len(results)} R3 checks and {sum(r['ok'] for r in r2)} of {len(r2)} R2 slip-ring checks pass. "
                         'Smallest (mm): ' + ', '.join(f"{r['check']} {r['value']:g}" for r in sorted(
                             [r for r in results if r['unit'] == 'mm' and r['required'].startswith('>=')],
                             key=lambda r: r['value'])[:4]) + '. All are in X1_swing_concept_R3_checks.json.', 98),
             fontsize=7.6, color='#2c3e50', va='top', linespacing=1.3)
    fig.text(.02, .006, 'Open: body parts (counterweight shell, side decks, cab and hood) and the electronics layout come next; '
                        'printed fits and the real JGY-370 play need test prints and a bench check.', fontsize=7.4, color=GREY)
    pdf.savefig(fig); fig.savefig(PNG[3], dpi=110); plt.close(fig)


def main():
    results, est = checks()
    r2 = R2.checks()
    CHECKS.write_text(json.dumps(dict(concept='X1 turntable concept R3: anti-sway structure, no custom metal parts', issue=ISSUE,
                                      source=Path(__file__).name, estimates=est, checks=results, r2_slip_ring_checks=r2,
                                      all_ok=all(r['ok'] for r in results + r2)), indent=1, default=float))
    with PdfPages(PDF) as pdf:
        sheet1(pdf, est)
        sheet2(pdf, est)
        sheet3(pdf, est)
        sheet4(pdf, results, est)
    bad = [r for r in results + r2 if not r['ok']]
    print('wrote', PDF, '|', len(results) - len([b for b in bad if b in results]), 'of', len(results), 'R3 checks;',
          len(r2) - len([b for b in bad if b in r2]), 'of', len(r2), 'R2 checks')
    for r in bad:
        print('  FAIL', r)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())

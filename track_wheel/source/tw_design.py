"""Track wheel unit: in-hub gearmotor final drive and spring-tensioned idler.

Unit frame, millimetres: X along the track (front +X), Y across it (track
centre Y=0, outboard +Y), Z up from the ground. In the excavator this is the
right-hand track shifted by TRACK_Y=170; the left track is its mirror image.
The rail plate keeps its existing position at Y -42..-30.

Purchased parts are interfaces taken from the cited documents. Where two
sources disagree, both extremes are carried and checked.
"""
import math

# ------------------------------------------------------------------ gearmotor
# Pololu 37D metal gearmotor, 150:1, 12 V, no encoder, item #2829.
# Drawing: "37D mm Metal Gearmotors (without encoder)", 10 Jan 2020,
# https://www.pololu.com/file/0J1735/37d-metal-gearmotors-dimension-diagram.pdf
# Ratings: datasheet rev 1.2 (Jan 2020) and https://www.pololu.com/product/2829/specs
GEARMOTOR = dict(
    model='Pololu 37D metal gearmotor 150:1, 12 V (#2829)',
    drawing='https://www.pololu.com/file/0J1735/37d-metal-gearmotors-dimension-diagram.pdf',
    specs='https://www.pololu.com/product/2829/specs',
    gearbox_diameter=36.8, gearbox_length=26.5,      # L for 100:1, 131:1, 150:1
    motor_diameter=34.8, motor_length=30.7,
    rear_boss_diameter=7.8, rear_boss_length=1.6, terminal_projection=5.0,
    shaft_diameter=6.0, shaft_flat=5.4, shaft_length=22.0,   # from gearbox face
    bushing_diameter=12.0, bushing_length=6.0,
    shaft_offset=7.0,                                 # output axis to gearbox axis
    face_screws=6, face_screw_circle=31.0, face_screw_max_depth=3.0,
    mass_kg=.195, ratio=150.0,
    no_load_rpm=67.0, no_load_A=.20, stall_kgcm=49.0, stall_A=5.5,   # extrapolated stall
    max_eff_rpm=58.0, max_eff_kgcm=6.5, max_eff_A=.72, max_eff=.44,
    continuous_limit_kgcm=10.0, instantaneous_limit_kgcm=25.0, voltage=12.0)
# Diameters are not toleranced on the drawing. Fit checks use +/-0.2 mm.
GEARMOTOR_DIAMETER_TOL = .2
KGCM = .0980665                                       # N m per kg cm

# ------------------------------------------------------------------ bearings
BEARINGS = dict(
    inboard=dict(model='6809-2RS', d=45., D=58., B=7., C_kN=[5.35, 6.63], C0_kN=[4.3, 6.1], mass_kg=.042,
                 shoulder_d_max=47.5, housing_shoulder_D_min=55.5, role='floating; carries radial load only',
                 source='Distributor listings for 6809-2RS / SKF 6809-2RZ / NTN 6809; lowest rating used'),
    outboard=dict(model='61808-2RS1', d=40., D=52., B=7., C_kN=[4.94, 4.94], C0_kN=[3.45, 3.45], mass_kg=.032,
                  shoulder_d_max=42.8, housing_shoulder_D_min=50.0, role='fixed; locates the hub both ways',
                  source='SKF 61808-2RS1 distributor listings (RS 207-6965, Exact Industrial Supply)'))

# ------------------------------------------------------------------ hub reduction
# Steel pinion on the eccentric gearbox shaft drives an internal ring gear
# moulded into the hub cap: a single-planet star stage, like the hub
# reduction inside a full-size final drive. The ring is generated as the
# envelope of the pinion at the actual 7.0 mm centre distance.
GEAR_MODULE = 1.5
PINION_TEETH = 12
RING_TEETH = 21
PRESSURE_ANGLE = 20.0
CENTRE_DISTANCE = GEARMOTOR['shaft_offset']
HUB_RATIO = RING_TEETH / PINION_TEETH
HUB_STAGE_EFFICIENCY = .95
PINION_FACE = 11.0
GEAR_BACKLASH = .22            # circumferential at a=7.0; still >0 at a=7.1 (play falls as a grows)
RING_BODY_R = 20.5
PINION_SPEC = ('Steel spur gear, module 1.5, 12 teeth, 20 deg, ISO 53 profile, face 11 mm, '
               'bore 6 H7 with M3 set screw on the motor D-flat. No hub (full face on the shaft).')

def drive_rating():
    """Sprocket-side ratings from the motor datasheet and the hub ratio."""
    m = GEARMOTOR; k = HUB_RATIO * HUB_STAGE_EFFICIENCY
    stall = m['stall_kgcm'] * KGCM * k
    w0 = m['no_load_rpm'] * 2 * math.pi / 60 / HUB_RATIO
    return dict(sprocket_no_load_rad_s=w0, sprocket_no_load_rpm=w0 * 60 / (2 * math.pi),
                sprocket_stall_Nm=stall,
                sprocket_continuous_Nm=m['continuous_limit_kgcm'] * KGCM * k,
                sprocket_instantaneous_Nm=m['instantaneous_limit_kgcm'] * KGCM * k,
                torque_per_amp_Nm=stall / (m['stall_A'] - m['no_load_A']),
                continuous_current_A=m['no_load_A'] + (m['stall_A'] - m['no_load_A']) * m['continuous_limit_kgcm'] / m['stall_kgcm'],
                instantaneous_current_A=m['no_load_A'] + (m['stall_A'] - m['no_load_A']) * m['instantaneous_limit_kgcm'] / m['stall_kgcm'])

# ------------------------------------------------------------------ final drive layout
DRIVE_X = -110.0
FRAME_Y = (-42.0, -30.0)       # rail plate, unchanged from track R4
FACE_Y = -3.5                   # gearbox face; gearbox fully inside the hub
PINION_ANGLE = 0.0              # eccentric shaft points along +X (front)
SCREW_PHASES = [30, 90, 150, 210, 270, 330]   # gearbox face holes from the shaft direction
TUBE_BORE = 37.3                # gearbox 36.8 + 0.5
TUBE_OD = 45.0                  # 6809 seat
TUBE_INBOARD_Y = -62.0
END_WALL = (FACE_Y, FACE_Y + 6.9)               # integral wall, 61808 seat; 0.1 short so the retainer clamps the inner ring
END_WALL_SEAT_D = 40.0
FLANGE_Y = (-48.0, -42.0)       # housing flange on the inboard face of the rail
FLANGE_D = 62.0
FLANGE_SCREW_R = 27.0
FLANGE_SCREWS = [45, 135, 225, 315]
BRIDGE_UNDERSIDE_Z = 70.0       # excavator chassis bridge plate above the rail flanges
FLANGE_FLAT_Z = 69.3            # housing flange is flattened 0.7 mm below the bridge
REAR_CAP_SCREWS = [0, 180]
REAR_CAP_SCREW_R = 26.5
REAR_PILLAR_R = (22.6, 30.0)    # housing pillars carrying the rear-cap inserts (radial extent)
REAR_PILLAR_HALF = 4.0
REAR_CAP_EAR_Y = (-70.0, -67.0) # cap ears at its closed end: they print flat on the bed
BOSS_D = 66.0                   # rail boss around the final drive
INBOARD_BEARING_Y = (-26.5, -19.5)
OUTBOARD_BEARING_Y = (-3.5, 3.5)
HUB_Y = (-29.5, 7.0)
HUB_OD = 65.6                   # 0.5 mm below the link running faces (66.64)
HUB_RIB_BORE = 46.0
HUB_INSERT_R = 29.8
RETAINER_Y = (3.5, 6.5)
RETAINER_D = 42.8
CAP_Y = (3.5, 22.0)
CAP_END_PLATE = 3.0
CAP_LIP = (50.0, 51.9)          # inner/outer diameter of the outer-ring clamp spigot
CAP_SCREW_R = HUB_INSERT_R
RING_Y = (7.2, 19.0)
PINION_Y = (7.5, 18.5)          # flush with the 22 mm shaft end at Y 18.5
REAR_CAP_Y = (-70.0, -62.0)

# Screws (ISO 7380 button head, ISO 4762 cap, ISO 4017 hex, ISO 4032 nuts) and
# M3 x 5.7 brass heat-set inserts (4.0 mm hole).
BUTTON_M3 = dict(head_d=5.7, head_h=1.65)
CAP_M3 = dict(head_d=5.5, head_h=3.0)
HEX_M6 = dict(af=10.0, head_h=4.0)
NUT_M6 = dict(af=10.0, h=5.2)
NUT_M3 = dict(af=5.5, h=2.4)
INSERT_M3 = dict(hole_d=4.0, length=5.7, od=4.6)
FACE_SCREW_LENGTH = 10.0        # M3 x 10 button head: 2.4 mm into the gearbox face
CAP_SCREW_LENGTH = 20.0
FLANGE_SCREW_LENGTH = 10.0       # 4 mm into the 5.7 mm rail insert, clear of its blind end
REAR_CAP_SCREW_LENGTH = 8.0      # 5 mm into the 5.7 mm pillar insert

# ------------------------------------------------------------------ recoil spring idler
# Associated/Lee Spring C-600-072-1500 (Ajax C600-072-1500), music wire:
# OD 0.600 in, wire 0.072 in, free length 1.500 in, rate 35.89 lbf/in,
# max load 26.48 lbf, solid height 0.670 in. Distributor data sheet:
# https://taylorspring.com/spring/associatedlee-spring-c-600-072-1500-compression-spring-music-wire/
LBF = 4.448222
INCH = 25.4
SPRING = dict(model='Associated/Lee Spring C-600-072-1500, music wire',
              source='https://taylorspring.com/spring/associatedlee-spring-c-600-072-1500-compression-spring-music-wire/',
              od=.600 * INCH, wire=.072 * INCH, free_length=1.500 * INCH,
              rate_N_mm=35.89 * LBF / INCH, max_load_N=26.48 * LBF, solid_length=.670 * INCH,
              rate_tolerance=.10)
SPRING['id'] = SPRING['od'] - 2 * SPRING['wire']
SPRING['coils'] = SPRING['solid_length'] / SPRING['wire']   # closed ends
IDLER_X = 110.0
SPRING_AXIS = (-44.0, None)    # Y; Z equals the axle height
CHANNEL_Y = (-54.0, -34.0)      # yoke channel interior
CHANNEL_Z = 15.5                # half height of the yoke channel
WALL = 4.0
REAR_WALL_X = (60.5, 66.5)      # carries the captive M6 nut of the adjuster
SPRING_BORE_D = 18.6
ASSEMBLY_YOKE_SHIFT = -.2005    # exact-pitch chain pose (excavator design.IDLER_ASSEMBLY_OFFSET)
# Hard recoil stop: the yoke body meets the rear end of the channel. 4.0 mm of
# recoil from the assembly pose leaves 1.3 mm between the idler and the front
# road roller (measured on the CAD), whatever the adjuster setting.
YOKE_STOP_X = 95.8
SPRING_BORE_X = (66.5, YOKE_STOP_X)
YOKE_X = (100.0, 124.0)         # nominal; axle at X110
YOKE_HALF = (9.7, 15.2)         # half width (Y) and half height (Z)
NOSE_X = (102.0, 118.0)
NOSE_HALF_Z = 7.9
SLOT_HALF_Z = 8.2
SPIGOT_D = 10.0
YOKE_SPIGOT = 9.0               # spring guides; they stay apart even at the stop with the adjuster at 3 mm
SEAT_SPIGOT = 9.0
SEAT_BLOCK = 4.0
SEAT_D = 18.2
ADJUST_RANGE = (0.0, 4.0)       # adjuster extension past the rear wall (M6 x 16 head stays 0.8 mm clear of the lock nut)
ADJUST_NOMINAL = 3.5             # assembled: 25.8 mm spring length, 77.3 N
FORWARD_TRAVEL = 4.0            # nominal yoke to the channel nose (slack take-up)
NOSE_BLOCK_X = (128.0, 140.0)
IDLER_AXLE_Y = (-63.0, 26.0)
# Reverse drive: a free idler sees both strands at the tight-side tension, so the
# slack strand under the sprocket keeps tension only while preload > 2 x drive pull.
PRELOAD_TARGET_N = 77.0
DRIVE_CURRENT_LIMIT_A = 1.0     # motor driver limit: 1.2 N m at the sprocket (the drive requirement)

def drive_force_limit():
    """Chain pull (N) at the motor driver current limit."""
    r = drive_rating()
    torque = (DRIVE_CURRENT_LIMIT_A - GEARMOTOR['no_load_A']) * r['torque_per_amp_Nm']
    return dict(torque_Nm=torque, chain_pull_N=torque / (SPROCKET_PITCH_R / 1000))

SPROCKET_PITCH_R = 20.0 / (2 * math.sin(math.pi / 12))   # 20 mm pitch, 12 teeth (excavator design.py)

def spring_state(extension=ADJUST_NOMINAL, yoke_shift=ASSEMBLY_YOKE_SHIFT, rate=None):
    """Spring length and force; yoke_shift from the nominal yoke (default: assembly pose)."""
    rate = SPRING['rate_N_mm'] if rate is None else rate
    seat_front = REAR_WALL_X[1] + extension + SEAT_BLOCK
    length = YOKE_X[0] + yoke_shift - seat_front
    return dict(length=length, force=max(0., (SPRING['free_length'] - length) * rate))

def recoil_travel():
    """Idler recoil from the assembly pose to the hard stop (mm)."""
    return YOKE_X[0] + ASSEMBLY_YOKE_SHIFT - YOKE_STOP_X

def forward_travel():
    """Idler travel from the assembly pose to the channel nose (mm)."""
    return YOKE_X[0] + FORWARD_TRAVEL - (YOKE_X[0] + ASSEMBLY_YOKE_SHIFT)

def stop_state(extension=ADJUST_NOMINAL, rate=None):
    """Spring at the recoil stop."""
    return spring_state(extension, YOKE_STOP_X - YOKE_X[0], rate)


def slide_spring(extension=ADJUST_NOMINAL):
    """Idler slide joint for the MuJoCo models (SI), measured from the nominal yoke pose."""
    return dict(k=SPRING['rate_N_mm'] * 1000,
                springref=(SPRING['free_length'] - spring_state(extension, 0.0)['length']) / 1000,
                range=((YOKE_STOP_X - YOKE_X[0]) / 1000, FORWARD_TRAVEL / 1000))


ROTOR_INERTIA = 1.5e-6          # kg m², estimate for a 37D rotor; Pololu publishes none

def reflected_inertia():
    """Rotor inertia seen at the sprocket through both stages (kg m²)."""
    return ROTOR_INERTIA * (GEARMOTOR['ratio'] * HUB_RATIO) ** 2

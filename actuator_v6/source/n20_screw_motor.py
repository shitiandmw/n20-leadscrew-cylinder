"""N20 gear motor with integrated M4 leadscrew: the bought core part, not modified.

The drive is the 12 V N20 gearmotor, 1:50, 800 rpm without load (the seller's table, row
"1:50, 12 V"), with an M4 x 0.7 leadscrew 100 mm long straight from the gearbox. V6-S and
V6-U60 use it cut to 55 and 75 mm; V6-L uses the full 100 mm.

Dimension chain from the user's N20 drawing (Z=0 at the gearbox front face). The motor body is
the same for every N20 winding and ratio; only the screw differs from the M3 version:
  front bushing  Ø4 x 0.7          z    0 ..  0.7
  gearbox        10 x 12 x 9        z   -9 ..  0     three plates, two pillars
  can            Ø12/10 flats x 15  z  -24 .. -9     includes the ~1 mm black end cap
  rear boss      Ø5 x 1.2           z -25.2 .. -24
  terminals      1.5 x 0.3, 2.5 out z -26.5 .. -24   7.3 apart

No drawing of the M4 version was available. Its photos (the user's seller and Veishida's
"threaded shaft N20 motor") show the standard gearbox face with the thread starting just in front
of the bushing, so the model keeps the Ø4 x 0.7 bushing and the Ø3 output journal inside it and
starts the M4 thread at Z = 0.8: the M4 shoulder runs 0.1 mm clear of the bushing face, the same
face clearance as the gearbox's own shoulders. Measure the real motor before printing: the
body's wall hole is Ø4.8 (layout.WALL_HOLE_D).
"""
from cad_utils import cylinder, box, revolve_profile
from n20_geartrain import gearbox_parts, output_spindle

GEARBOX_FRONT = 0.0
GEARBOX_REAR = -9.0
CAN_REAR = -24.0
BOSS_REAR = -25.2
TERMINAL_TIP = -26.5
TERMINAL_Y = 3.65
TERMINAL_HOLE_Z = -25.7
PLATE_T = 0.8
PLATES_Z = (-9.0, -4.65, -0.8)          # archive rear, middle, front plate rear faces
PILLARS_XY = ((-3.7, -4.4), (3.7, -4.4))
M16_HOLES_XY = ((0, 4.5), (0, -4.5))     # 2 x M1.6 tapped holes in the front face

# The leadscrew: ISO metric coarse M4 (pitch 0.7, minor diameter d3 = 3.141 mm).
SCREW = dict(name="M4 x 0.7", major=4.0, minor=3.14, pitch=0.7, stock_length=100.0)
BUSHING_FRONT = 0.7                     # front face of the Ø4 x 0.7 bushing
JOURNAL_R = 1.5                         # the Ø3 output journal inside the bushing
THREAD_START = BUSHING_FRONT + 0.1      # M4 shoulder, 0.1 mm clear of the bushing face


def screw_profile(length, pitch=SCREW["pitch"], major=SCREW["major"], minor=SCREW["minor"], start=THREAD_START):
    """Visual thread: a revolved saw-tooth. Pitch rings, not a helix."""
    r1, r0 = major / 2, minor / 2
    pts = [(0, -PLATE_T), (r1, -PLATE_T), (r1, start)]
    z = start
    while z + pitch <= length - 0.5 + 1e-9:
        pts += [(r0, z + pitch * 0.5), (r1, z + pitch)]
        z += pitch
    pts += [(r1, length - 0.4), (r1 - 0.4, length), (0, length)]
    return revolve_profile(pts)


def n20_core_part(screw_length=75.0, pitch=SCREW["pitch"]):
    """Meshed archive gearbox with the V6 visual M4 thread from THREAD_START.

    Keep the archive's keyed output spindle and thrust shoulder so the last
    wheel drives the screw. The external thread is V6's pitch rings; only
    the motor internals come from the archive, not the actuator's screw interface.
    """
    if pitch != SCREW["pitch"] or not 2 < screw_length <= SCREW["stock_length"]:
        raise ValueError("V6 requires the M4 x 0.7 screw, cut to between 2 and 100 mm")
    hw = dict(gearbox_parts())
    w = SCREW["major"] + 1
    thread = screw_profile(screw_length, pitch).intersect(
        box(w, w, screw_length - THREAD_START, z=(screw_length + THREAD_START) / 2))
    neck = cylinder(JOURNAL_R, THREAD_START - BUSHING_FRONT, BUSHING_FRONT)   # journal up to the shoulder
    hw["motor_leadscrew_M4"] = output_spindle().union(neck).union(thread)
    return hw


def screw_envelope(screw_length):
    return cylinder(SCREW["major"] / 2, screw_length + PLATE_T, -PLATE_T)

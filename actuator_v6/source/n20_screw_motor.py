"""N20 gear motor with integrated M3 leadscrew: the user's core part, not modified.

Dimension chain from the user's drawing (Z=0 at the gearbox front face):
  front bushing  Ø4 x 0.7          z    0 ..  0.7
  gearbox        10 x 12 x 9        z   -9 ..  0     three plates, two pillars
  can            Ø12/10 flats x 15  z  -24 .. -9     includes the ~1 mm black end cap
  rear boss      Ø5 x 1.2           z -25.2 .. -24
  terminals      1.5 x 0.3, 2.5 out z -26.5 .. -24   7.3 apart
V4 modelled the 1.2 mm as a separate full-section cap *and* added a 1.2 mm boss,
so its motor was 1.2 mm too long. Here the end cap is inside the 15 mm can.

The leadscrew follows the user's photo: it leaves the gearbox directly, no
coupler. The photo shows about 78 thread crests; with the Ø3 shaft of the
drawing that is M3 x 0.5, about 40 mm long. Measure the real screw and pass
its length to the build if it differs.
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


def screw_profile(length, pitch=0.5, major=3.0, minor=2.4, start=0.7):
    """Visual thread: a revolved saw-tooth. Pitch rings, not a helix."""
    r1, r0 = major / 2, minor / 2
    pts = [(0, -PLATE_T), (r1, -PLATE_T), (r1, start)]
    z = start
    while z + pitch <= length - 0.5 + 1e-9:
        pts += [(r0, z + pitch * 0.5), (r1, z + pitch)]
        z += pitch
    pts += [(r1, length - 0.4), (r1 - 0.4, length), (0, length)]
    return revolve_profile(pts)


def n20_core_part(screw_length=40.0, pitch=0.5):
    """Meshed archive gearbox with the existing V6 visual thread above Z=0.7.

    Keep the archive's keyed output spindle and thrust shoulder so the last
    wheel drives the screw. The external M3 thread remains V6's pitch rings;
    only the motor internals are replaced, not the actuator's screw interface.
    """
    if pitch != 0.5 or screw_length < 2:
        raise ValueError("V6 requires an M3 x 0.5 screw longer than 2 mm")
    hw = dict(gearbox_parts())
    thread = screw_profile(screw_length, pitch).intersect(
        box(5, 5, screw_length - 0.7, z=(screw_length + 0.7) / 2))
    hw["motor_leadscrew_M3"] = output_spindle().union(thread)
    return hw


def screw_envelope(screw_length):
    return cylinder(1.5, screw_length + PLATE_T, -PLATE_T)

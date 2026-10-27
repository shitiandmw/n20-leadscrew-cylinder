"""N20 gear motor with integrated M3 leadscrew: the user's core part, not modified.

Dimension chain from the user's drawing (Z=0 at the gearbox front face):
  front bushing  Ø4 x 0.7          z    0 ..  0.7
  gearbox        10 x 12 x 9        z   -9 ..  0     three 0.8 plates, two pillars
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
import math
import cadquery as cq
from cad_utils import cylinder, box, double_d, ring, revolve_profile

GEARBOX_FRONT = 0.0
GEARBOX_REAR = -9.0
CAN_REAR = -24.0
BOSS_REAR = -25.2
TERMINAL_TIP = -26.5
TERMINAL_Y = 3.65
TERMINAL_HOLE_Z = -25.7
PLATE_T = 0.8
PLATES_Z = (-9.0, -5.85, -0.8)          # rear, middle, front plate (rear faces)
PILLARS_XY = ((-2.7, 3.9), (2.7, -3.9))  # diagonal, as in the front view
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


def plate(z0):
    p = cq.Workplane("XY").rect(10, 12).extrude(PLATE_T).edges("|Z").fillet(0.6).translate((0, 0, z0))
    return p.cut(cylinder(2.1, PLATE_T + 0.2, z0 - 0.1))


def gear(x, y, radius, width, z0, teeth=14):
    g = cylinder(radius, width, z0).translate((x, y, 0))
    for i in range(teeth):
        a = 2 * math.pi * i / teeth
        g = g.union(box(0.5, 0.45, width, x=x + radius, y=y, z=z0 + width / 2)
                    .rotate((x, y, 0), (x, y, 1), math.degrees(a)))
    return g


def n20_core_part(screw_length=40.0, pitch=0.5):
    hw = {}
    can = double_d(12, 10, 15 - 1.0, CAN_REAR + 1.0)
    # Two pressed slots on each flat side, as in the drawing and photo.
    for x in (-5, 5):
        for y in (-2.0, 2.0):
            slot = cylinder(0.3, 6.0, -19.5).translate((x, y, 0))
            can = can.cut(slot)
    hw["motor_can"] = can
    hw["motor_end_cap"] = double_d(12, 10, 1.0, CAN_REAR)
    hw["motor_rear_boss"] = cylinder(2.5, 1.2, BOSS_REAR)
    for i, y in enumerate((-TERMINAL_Y, TERMINAL_Y), start=1):
        tab = box(1.5, 0.3, 2.5, y=y, z=CAN_REAR - 1.25)
        tab = tab.cut(cylinder(0.3, 1, -0.5).rotate((0, 0, 0), (1, 0, 0), 90).translate((0, y, TERMINAL_HOLE_Z)))
        hw[f"motor_terminal_{i}"] = tab
    frame = plate(PLATES_Z[0]).union(plate(PLATES_Z[1])).union(plate(PLATES_Z[2]))
    for x, y in PILLARS_XY:
        frame = frame.union(cylinder(1.2, -PLATES_Z[0] - PLATE_T, PLATES_Z[0] + PLATE_T).translate((x, y, 0)))
    for x, y in M16_HOLES_XY:
        frame = frame.cut(cylinder(0.7, 2.1, -2.1).translate((x, y, 0)))
    hw["motor_gearbox_frame"] = frame
    hw["motor_front_bushing"] = ring(4, 3.05, 0.7 + PLATE_T, -PLATE_T)
    for i, (x, y, r, w, z0) in enumerate([(0, 0, 1.2, 1.6, -7.9), (-1.2, 1.0, 1.6, 0.8, -7.6),
                                         (1.2, -1.0, 1.6, 0.8, -4.6), (0, 0, 3.0, 1.2, -2.3)], start=1):
        hw[f"motor_gear_{i}"] = gear(x, y, r, w, z0)
    hw["motor_leadscrew_M3"] = screw_profile(screw_length, pitch)
    return hw


def screw_envelope(screw_length):
    return cylinder(1.5, screw_length + PLATE_T, -PLATE_T)

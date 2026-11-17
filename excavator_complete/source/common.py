"""Shared constants for the complete-machine demonstration (mm, kg; vehicle frame: X forward, Y left, Z up,
origin on the ground under the swing centre, as in track_wheel_jgy370/X1).

The machine is assembled from the current revision of every subsystem, read from its own folder:
  lower   track_wheel_jgy370/X1  revision F X-frame, belly cover, THK RU66 seat     (x1_scene.json.gz)
          track_wheel_jgy370/J9  two J9 tracks (right = mirrored J901/J909 prints) (x1_scene.json.gz 'module')
  upper   track_wheel_jgy370/X1  R3 turntable (T101-T106, X103, swing motor)       (turntable_scene.json.gz)
          track_wheel_jgy370/X1  body B1 rev B with the main board rev B            (body_scene.json.gz)
                                 (its STEP, with the top-entry headers and their mated plugs, since 2026-11-14)
  arm     excavator_arm_r12      R12 Rev. D4 (Cat 320 geometry, 4 x V6-U60)         (cad/scene.json.gz)
The only new part is B01X, the R12 boom-foot bracket with the base plate that bolts to T101 (build_adapter.py).
"""
from pathlib import Path
import json
import gzip
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parent
X1 = REPO / 'track_wheel_jgy370/X1'
J9 = REPO / 'track_wheel_jgy370/J9'
R12 = REPO / 'excavator_arm_r12'
VENDOR = REPO / 'actuator_v6/source/vendor'

# ------------------------------------------------------------------ T101 arm interface (X1/swing_concept/source/draw_swing_concept_r3.py)
# These are the R3 numbers the ARM60 base used. check_complete.py re-measures them on the turntable meshes.
T101_TOP_Z = 136.0                        # rib tops = arm mounting plane (R3 TOPZ)
ARM60_X0 = 23.0                           # ARM60 base origin from the swing axis (R3 ARM_X0)
BASE_X = (ARM60_X0 - 44.0, ARM60_X0 + 88.0)   # ARM60 base plate footprint, kept for B01X: X -21 .. 111
BASE_Y = 82.0                             # |Y| <= 82 (the body halves stand 0.5 mm outside it)
BASE_T = 10.0                             # plate thickness: keeps the M6 x 40 bolts and T101's nut pockets
BOLTS = [(ARM60_X0 + bx, s * 65.0) for bx in (-32.0, 76.0) for s in (1, -1)]   # (-9, +-65), (99, +-65)
BOLT_HOLE_R = 3.3                         # Ø6.6 clearance, as the ARM60 base

# ------------------------------------------------------------------ where R12 sits
# R12's own frame has the boom-foot pin O at the origin, the swing axis 30 mm behind it (SWING_X = -30) and
# its foot flange (6 mm) on a turntable face 55 mm below O. B01X keeps every part of B01 above the flange top
# (O - 49) and replaces the flange with the 10 mm base plate on the rib tops, so O sits 59 mm above them.
R12_SWING_X = -30.0
O_X = -R12_SWING_X                        # 30: O ahead of the swing axis, as R12 was laid out
O_Z = T101_TOP_Z + BASE_T + 49.0          # 195
O_VEH = np.array([O_X, 0.0, O_Z])
R12_DESIGN_O_Z = 155.0                    # R12 drawings: O 155 above the ground (GROUND_Z = -155)

# ------------------------------------------------------------------ demonstration choices
SWING_DUMP_DEG = 90.0                     # dump to the left (cab side, the operator can see the spot)
SWING_TIME_S = 4.0                        # 90 deg in 4 s, minimum-jerk: peak 42 deg/s < 45 deg/s (7.5 rpm no load)
TRAVEL_MM = 250.0                         # forward and back
TRAVEL_TIME_S = 4.0                       # minimum-jerk: peak 117 mm/s; J9 runs 88-120 mm/s
ARM_PLAYBACK = 20.0                       # the arm is slow (0.8 mm/s drive peak): shown at 20 x real time


def load_gz(p):
    return json.loads(gzip.decompress(Path(p).read_bytes()))


def save_gz(p, obj):
    Path(p).write_bytes(gzip.compress(json.dumps(obj, separators=(',', ':')).encode()))


def rot_y(a):
    """R12 body frames: a planar pose angle a (x towards z) is a rotation of -a about +Y."""
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0.0, -s], [0.0, 1.0, 0.0], [s, 0.0, c]])


def rot_z(deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def min_jerk(u):
    u = min(max(u, 0.0), 1.0)
    return u ** 3 * (10 - 15 * u + 6 * u * u)

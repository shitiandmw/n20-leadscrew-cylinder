"""Reference bucket: Caterpillar US 8,201,350 B2 "Machine bucket" (2012), Example 1 and FIG. 1.

Example 1 has a tip radius of 1,570 mm. That is the Cat 320/325 tip radius R12 already uses
(104.67 mm at 1:15), so the bucket is copied at the same scale as the rest of the arm.

What comes from where:
  * Example 1 numbers (column 5):
      - tip radius 1570 and tip forward angle 35 deg
      - lower wrapper arc R1 985 over 30 deg, upper arc R2 370 over 130 deg
      - floor length A 354
      - heel radius R_H 1246 at heel radius angle 10.34 deg
    The heel radius and angle place the centre of the lower arc. That fixes the floor 1241.8 below
    the pin and the floor angle at 2.16 deg (the patent says about 2).
  * FIG. 1, read from ../references/US8201350_fig1.png:
      - a 300 dpi scan, turned so the floor is horizontal
      - pin 26 at pixel (1566, 701), 1.102 mm per pixel, scaled by the tip radius
      - the tooth tip lands within 2 mm of the numbers
    The figure gives:
      - the support-plate front end, laid at the 20 deg hinge-support-plate angle
      - the cutting-edge tip
      - the side-plate front edge
      - the torque tube (used only to measure the throat length L)
  * Check: the patent's throat dimensions come out as L' 1177 / D' 928 / D 941 against the stated
    1189 / 920 / 940 (report()).

Patent frame E (full-scale mm):
  * origin at the upper pin bore, which is R12 pin H
  * x along the floor toward the heel
  * y up (line 62, perpendicular to the floor, points down)
The R12 bucket frame has x from H to the tooth tip T and z toward the back of the bucket.
`to_bucket` maps E to the bucket frame at 1:15."""
import math
import numpy as np

SCALE = 15.0
# --- Example 1 (column 5, lines 1-20)
R_T = 1570.0            # tip radius: upper pin bore -> tooth tip
THETA_T = 35.0          # tip forward angle: tip line vs line 62
FLOOR_A = 354.0         # floor length (straight lower portion 44 of the wrapper)
R1, TH1 = 985.0, 30.0   # lower wrapper radius and its central angle
R2, TH2 = 370.0, 130.0  # upper wrapper radius and its central angle
HINGE_PLATE_ANGLE = 20.0  # cutting-edge top vs support-plate bottom (= upper vs lower straight wrapper portions)
R_H, THETA_H = 1246.0, 10.34   # heel radius and heel radius angle
PATENT_THROAT = dict(L=1326.0, D=940.0, L1=1189.0, D1=920.0)
# --- FIG. 1 (E frame, mm)
SUPPORT_FRONT = np.array([37.5, -246.8])     # support plate front end: top of the mouth, beside the pin
SUPPORT_REAR_X = 428.7                       # support plate meets the wrapper (points 41, 88)
SIDE_EDGE_PT = np.array([-530.0, -1145.0])   # a point on the side-plate front edge above the cutting edge
EDGE_TIP_X = -591.0                          # cutting-edge tip (on the floor line)
TORQUE_TUBE = np.array([[68.3, -230.3], [87.1, -131.1], [125.6, -92.6], [169.7, -81.5], [224.8, -98.1],
                        [268.9, -142.2], [335.0, -241.3], [390.1, -329.5]])
PIN_LINK_PATENT = np.array([419.9, -140.0])  # lower pin bore 28 (the link pin), for comparison only

_th = math.radians(THETA_T)
X_HAT = np.array([-math.sin(_th), -math.cos(_th)])     # bucket x (H -> T) in E
Z_HAT = np.array([math.cos(_th), -math.sin(_th)])      # bucket z (toward the back of the bucket) in E
TIP_E = R_T * X_HAT

_c1 = (R_H - R1) * np.array([math.sin(math.radians(THETA_H)), -math.cos(math.radians(THETA_H))])
H_FLOOR = R1 - _c1[1]                                     # pin -> floor line (outer surface), 1241.8
THETA_F = math.degrees(math.atan2(_c1[0], H_FLOOR))       # 2.16


def to_bucket(p):
    p = np.atleast_2d(np.asarray(p, float))
    out = np.c_[p @ X_HAT, p @ Z_HAT] / SCALE
    return out[0] if out.shape[0] == 1 else out


def dir_to_bucket(v):
    v = np.asarray(v, float)
    return np.array([v @ X_HAT, v @ Z_HAT])


def wrapper_E(n_arc=64):
    """Outer surface of the support plate and the wrapper, from the support-plate front end to the
    cutting-edge tip (E frame, mm), and the named points of the patent."""
    c1 = _c1
    a1 = np.radians(np.linspace(-90.0, -90.0 + TH1, max(8, n_arc // 4)))
    lower = c1 + R1 * np.c_[np.cos(a1), np.sin(a1)]                 # 94 -> 102
    p102 = lower[-1]
    c2 = p102 - R2 * np.array([math.cos(a1[-1]), math.sin(a1[-1])])
    a2 = np.radians(np.linspace(-90.0 + TH1, -90.0 + TH1 + TH2, n_arc))
    upper = c2 + R2 * np.c_[np.cos(a2), np.sin(a2)]                 # 102 -> 96
    p96 = upper[-1]
    slope = math.tan(math.radians(HINGE_PLATE_ANGLE))
    p41 = np.array([SUPPORT_REAR_X, SUPPORT_FRONT[1] - (SUPPORT_REAR_X - SUPPORT_FRONT[0]) * slope])
    p94, p47 = lower[0], np.array([lower[0][0] - FLOOR_A, -H_FLOOR])
    tip = np.array([EDGE_TIP_X, -H_FLOOR])
    path = np.vstack([[SUPPORT_FRONT, p41], upper[::-1], lower[::-1][1:], [p47, tip]])
    return path, dict(c1=c1, c2=c2, p94=p94, p102=p102, p96=p96, p41=p41, p47=p47, edge_tip=tip)


def side_front_corner_E(plate_t):
    """Where the straight side-plate front edge (support front end -> SIDE_EDGE_PT) meets the inner
    face of the floor plate (plate thickness plate_t, full-scale mm)."""
    d = SIDE_EDGE_PT - SUPPORT_FRONT
    t = (-H_FLOOR + plate_t - SUPPORT_FRONT[1]) / d[1]
    return SUPPORT_FRONT + t * d


def _throat(p_end, path):
    tip = np.array([EDGE_TIP_X, -H_FLOOR])
    L = float(np.linalg.norm(p_end - tip))
    u = (p_end - tip) / L
    n = np.array([-u[1], u[0]])
    r = path - tip
    m = ((r @ u) > 0) & ((r @ u) < L)
    return L, float(np.max(np.abs(r @ n)[m]))


def report():
    path, pts = wrapper_E(400)
    tip = pts['edge_tip']
    tt = TORQUE_TUBE[int(np.argmax([math.atan2(*(p - tip)[::-1]) for p in TORQUE_TUBE]))]
    L, D = _throat(tt, path)
    L1, D1 = _throat(SUPPORT_FRONT, path)
    return dict(floor_below_pin_mm=round(float(H_FLOOR), 1), floor_angle_deg=round(THETA_F, 2),
                throat=dict(L=round(L), D=round(D), L1=round(L1), D1=round(D1)), patent_throat=PATENT_THROAT,
                tooth_tip_below_floor_mm=round(float(-H_FLOOR - TIP_E[1]), 1))


if __name__ == '__main__':
    print(report())
    print(to_bucket(np.array([[0, 0], TIP_E, PIN_LINK_PATENT, SUPPORT_FRONT])))

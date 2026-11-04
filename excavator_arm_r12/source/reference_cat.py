"""Real excavator geometry used as the R12 reference.

Two independent sources:

1. Pins: US patent 6,518,519 (Caterpillar, 2003), FIG. 4 / Table 1, "Mechanism parameters for
   Model 325 excavator" (references/US6518519_fig4_table1.png, figure in US6518519_fig3.png).
   Cat 325: boom 6.15 m, stick 3.2 m. Cat 320 (our 1:15 target): boom 5.7 m, stick 2.9 m, so each
   link is normalised to its own length here (boom -> 380 mm, stick -> 193.33 mm).
2. Outlines: the Cat 320 manufacturer side render (references/cat320_view_018.jpg, opposite the
   cab). Its pins agree with the patent to within ~2 mm at our scale (see trace check), so the
   traced outlines are expressed in the same normalised link frames.

Frames (same as the patent): world x forward / z up with the boom-foot pin O at the origin;
boom s along O->E, t to the upper side; stick u along E->H, v to the outer side (away from the
machine, where both cylinders sit); bucket p along H->T, q counter-clockwise from p.
"""
import json
import math
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / 'references'

BOOM, STICK, TIP_R = 380.0, 193.333, 104.667          # Cat 320 at 1:15
KB, KS = BOOM / 6.15, STICK / 3.2                       # mm per metre of the Cat 325 table

PATENT_M = dict(a12=6.15, a23=3.2, xA=0.767, yA=-0.669, xO=0.165, yO=0.0, sB=2.505, tB=1.1, sD=3.518, tD=1.217,
                sJ=3.343, tJ=0.7, uE=-0.8325, vE=0.343, uF=0.485, vF=0.708, uG=2.72, vG=0.035, uK=0.861, vK=0.322,
                pI=0.0, qI=0.485, LGH=0.685, LHI=0.64, boom_mass_kg=2040, stick_mass_kg=946)

# Reference pins in R12 names (patent names in brackets), mm at our scale
REF_PINS = dict(
    A_world=(np.array([PATENT_M['xA'] - PATENT_M['xO'], PATENT_M['yA']]) * KB),   # boom cylinder base [A]
    B_boom=np.array([PATENT_M['sB'], PATENT_M['tB']]) * KB,                        # boom cylinder rod [B]
    C_boom=np.array([PATENT_M['sD'], PATENT_M['tD']]) * KB,                        # stick cylinder base [D]
    G_boom=np.array([PATENT_M['sJ'], PATENT_M['tJ']]) * KB,                        # boom centre of mass [J]
    D_stick=np.array([PATENT_M['uE'], PATENT_M['vE']]) * KS,                       # stick cylinder rod, tail [E]
    F_stick=np.array([PATENT_M['uF'], PATENT_M['vF']]) * KS,                       # bucket cylinder base [F]
    J_stick=np.array([PATENT_M['uG'], PATENT_M['vG']]) * KS,                       # side-link pivot [G]
    G_stick=np.array([PATENT_M['uK'], PATENT_M['vK']]) * KS,                       # stick centre of mass [K]
    Q_bucket=np.array([PATENT_M['pI'], PATENT_M['qI']]) * KS,                      # H-link to bucket [I]
)
REF_LINKS = dict(side_link=PATENT_M['LGH'] * KS, h_link=PATENT_M['LHI'] * KS)  # [G-H], [H-I]

# Pixel positions read from the render (image y down), near-side bosses
RENDER_PX = dict(O=(570.0, 748.0), B=(787.0, 455.0), E=(1289.5, 354.5), D=(1300.0, 244.0), J=(1350.8, 708.0),
                 R=(1437.0, 709.5), Hs=(1355.8, 775.8), Hb=(1365.0, 807.0), T=(1238.0, 997.0))
# Hs: stick-end pin (holds the quick coupler in the render); Hb: the bucket's own hinge pin under the
# coupler; T: near-side tooth tip. |Hb-T| scales to 105.9 mm against the 104.67 mm Cat tip radius.


def _rot(a):
    return np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])


def px_to_frame(pts, p0, p1, length):
    """Image pixels -> link frame: origin p0, x toward p1, |p0p1| scaled to `length`, z up."""
    pts = np.asarray(pts, float).copy()
    pts[:, 1] *= -1
    a, b = np.array([p0[0], -p0[1]]), np.array([p1[0], -p1[1]])
    u = (b - a) / np.linalg.norm(b - a)
    n = np.array([-u[1], u[0]])
    k = length / np.linalg.norm(b - a)
    d = pts - a
    return np.stack([d @ u, d @ n], 1) * k


def load_traced():
    p = REF / 'cat320_traced.json'
    return json.loads(p.read_text()) if p.exists() else None

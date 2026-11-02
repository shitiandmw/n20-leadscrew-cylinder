"""CadQuery geometry for the track wheel unit (one track, unit frame, mm).

Final drive: a Pololu 37D gearmotor sits coaxially inside the sprocket hub, in
a stationary housing bolted to the rail. Its eccentric output shaft drives an
internal ring gear in the rotating hub cap (1.75:1 hub reduction). The hub turns
on a fixed 61808 bearing under the sprocket and a floating 6809 bearing near the
rail, so track tension never loads the motor shaft.

Front idler: the idler axle is carried by a yoke sliding in a closed box
channel. A preloaded recoil spring behind the yoke pushes it forward; an M6
adjuster at the rear wall sets the preload. Spigots on the yoke and spring seat
meet before the spring reaches its catalogue maximum load (recoil stop).

The chain, shoes, rollers and idler wheel are the unchanged Track R4 parts.
Their geometry moved here from excavator_60mm/source/build_vehicle.py.
"""
import math, sys
from pathlib import Path
import cadquery as cq
import numpy as np
from shapely.geometry import Polygon
from shapely.affinity import rotate as srotate

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(REPO / 'excavator_60mm/source'))
import design as ex                                  # chain, sprocket and wheel constants
from tw_design import *
from tw_gears import pinion_profile, ring_profile

AXLE_Z = ex.AXLE_Z
assert abs(ex.IDLER_ASSEMBLY_OFFSET - ASSEMBLY_YOKE_SHIFT) < 1e-4
APOTHEM = ex.APOTHEM
DX, DZ = DRIVE_X, AXLE_Z
PX = DRIVE_X + CENTRE_DISTANCE * math.cos(math.radians(PINION_ANGLE))
PZ = AXLE_Z + CENTRE_DISTANCE * math.sin(math.radians(PINION_ANGLE))
RETURN_Z = ex.RETURN_Z

YELLOW = (.91, .60, .07); DARK = (.13, .17, .20); STEEL = (.63, .69, .73)
RUBBER = (.19, .21, .22); BRASS = (.78, .62, .28); MOTOR = (.30, .32, .34)
GEARBOX = (.70, .72, .74); SPRING_C = (.55, .58, .60); BLACK = (.07, .08, .09)
ORANGE = (.86, .38, .10)


# ---------------------------------------------------------------- primitives
def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane('XY').box(x1 - x0, y1 - y0, z1 - z0).translate(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))

def ycyl(r, y0, y1, x=0., z=0.):
    return cq.Workplane('XZ').center(x, z).circle(r).extrude(y1 - y0).translate((0, y1, 0))

def xcyl(r, x0, x1, y=0., z=0.):
    return cq.Workplane('YZ').center(y, z).circle(r).extrude(x1 - x0).translate((x0, 0, 0))

def zcyl(r, z0, z1, x=0., y=0.):
    return cq.Workplane('XY').center(x, y).circle(r).extrude(z1 - z0).translate((0, 0, z0))

def yring(ro, ri, y0, y1, x=0., z=0.):
    return ycyl(ro, y0, y1, x, z).cut(ycyl(ri, y0 - 1, y1 + 1, x, z))

def xring(ro, ri, x0, x1, y=0., z=0.):
    return xcyl(ro, x0, x1, y, z).cut(xcyl(ri, x0 - 1, x1 + 1, y, z))

def xhex(af, x0, x1, y, z):
    return cq.Workplane('YZ').center(y, z).polygon(6, af * 2 / math.sqrt(3)).extrude(x1 - x0).translate((x0, 0, 0))

def zhex(af, z0, z1, x, y):
    return cq.Workplane('XY').center(x, y).polygon(6, af * 2 / math.sqrt(3)).extrude(z1 - z0).translate((0, 0, z0))

def xz_prism(poly, y0, y1, x=0., z=0.):
    """Prism along Y from a shapely polygon (with holes) drawn in the XZ plane."""
    def wire(coords):
        return cq.Wire.makePolygon([cq.Vector(px + x, y0, pz + z) for px, pz in list(coords)[:-1]], close=True)
    face = cq.Face.makeFromWires(wire(poly.exterior.coords), [wire(h.coords) for h in poly.interiors])
    return cq.Workplane(obj=cq.Solid.extrudeLinear(face, cq.Vector(0, y1 - y0, 0)))

def polar(r, deg, x=DX, z=DZ):
    a = math.radians(deg)
    return x + r * math.cos(a), z + r * math.sin(a)

def one(s):
    vals = s.vals()
    return vals[0] if len(vals) == 1 else cq.Compound.makeCompound(vals)


def tooth_angles():
    """Angles (deg, XZ plane) of the sprocket tooth crests, from the outline."""
    poly = ex.sprocket_outline()
    pts = np.asarray(poly.exterior.coords)
    ang = np.degrees(np.arctan2(pts[:, 1], pts[:, 0])) % 360; rad = np.hypot(pts[:, 0], pts[:, 1])
    crest = []
    for k in range(ex.TEETH):
        # Pocket centres are where the radius is smallest; crests lie half a pitch away.
        sel = (ang >= k * 30) & (ang < (k + 1) * 30)
        crest.append(float(ang[sel][np.argmin(rad[sel])]))
    pockets = sorted(crest)
    return sorted(((p + 15) % 360) for p in pockets)


# ---------------------------------------------------------------- final drive
def motor_housing():
    """TW01. Stationary tube carrying the gearmotor; rail flange inboard."""
    s = yring(TUBE_OD / 2, TUBE_BORE / 2, TUBE_INBOARD_Y, FACE_Y, DX, DZ)
    s = s.union(ycyl(END_WALL_SEAT_D / 2, END_WALL[0], END_WALL[1], DX, DZ))
    flange = yring(FLANGE_D / 2, TUBE_BORE / 2, FLANGE_Y[0], FLANGE_Y[1], DX, DZ)
    # Flat top: the excavator's chassis bridge plate passes 0.7 mm above it.
    flange = flange.cut(box(DX - 40, DX + 40, FLANGE_Y[0] - 1, FLANGE_Y[1] + 1, FLANGE_FLAT_Z, FLANGE_FLAT_Z + 20))
    s = s.union(flange)
    # The Ø12 output bushing locates the shaft: close fit fixes the gear centre distance.
    s = s.cut(ycyl(12.15 / 2, END_WALL[0] - 1, END_WALL[1] + 1, PX, PZ))
    for a in SCREW_PHASES:
        x, z = polar(GEARMOTOR['face_screw_circle'] / 2, PINION_ANGLE + a)
        s = s.cut(ycyl(1.7, END_WALL[0] - 1, END_WALL[1] + 1, x, z))
    # The 61808 inner-ring shoulder stops at the catalogue d_as max (clear of the seals).
    s = s.cut(yring(TUBE_OD / 2 + 1, BEARINGS['outboard']['shoulder_d_max'] / 2, END_WALL[0] - .4, END_WALL[0] + .1, DX, DZ))
    for a in FLANGE_SCREWS:
        x, z = polar(FLANGE_SCREW_R, a)
        s = s.cut(ycyl(1.7, FLANGE_Y[0] - 1, FLANGE_Y[1] + 1, x, z))
    # Two pillars from the flange to the rear-cap ears, with M3 heat-set inserts in their ends.
    y_end = REAR_CAP_EAR_Y[1]
    for a in REAR_CAP_SCREWS:
        r0, r1 = REAR_PILLAR_R
        # Merged with the tube wall along the tube; clear of the rear cap beyond the tube end.
        pillar = box(TUBE_OD / 2 - 1, r1, TUBE_INBOARD_Y, FLANGE_Y[0] + .01, -REAR_PILLAR_HALF, REAR_PILLAR_HALF)
        pillar = pillar.union(box(r0, r1, y_end, TUBE_INBOARD_Y + .01, -REAR_PILLAR_HALF, REAR_PILLAR_HALF))
        pillar = pillar.rotate((0, 0, 0), (0, -1, 0), a).translate((DX, 0, DZ))
        s = s.union(pillar)
        x, z = polar(REAR_CAP_SCREW_R, a)
        s = s.cut(ycyl(INSERT_M3['hole_d'] / 2, y_end - 1, y_end + 7.0, x, z))
    return s


def sprocket_hub():
    """TW02. Sprocket teeth and hub drum in one rotating printed part."""
    teeth = xz_prism(ex.sprocket_outline(), -7.0, 7.0, DX, DZ)
    s = teeth.union(ycyl(HUB_OD / 2, HUB_Y[0], -7.0, DX, DZ))
    s = s.cut(ycyl(BEARINGS['inboard']['D'] / 2, HUB_Y[0] - 1, INBOARD_BEARING_Y[1], DX, DZ))
    s = s.cut(ycyl(HUB_RIB_BORE / 2, INBOARD_BEARING_Y[1] - .5, OUTBOARD_BEARING_Y[0] + .5, DX, DZ))
    s = s.cut(ycyl(BEARINGS['outboard']['D'] / 2, OUTBOARD_BEARING_Y[0], HUB_Y[1] + 1, DX, DZ))
    # Shoulders touch only the outer rings.
    s = s.cut(ycyl(BEARINGS['inboard']['housing_shoulder_D_min'] / 2, INBOARD_BEARING_Y[1] - .1, INBOARD_BEARING_Y[1] + .4, DX, DZ))
    s = s.cut(ycyl(BEARINGS['outboard']['housing_shoulder_D_min'] / 2, OUTBOARD_BEARING_Y[0] - .4, OUTBOARD_BEARING_Y[0] + .1, DX, DZ))
    for a in insert_angles():
        x, z = polar(HUB_INSERT_R, a)
        s = s.cut(ycyl(INSERT_M3['hole_d'] / 2, HUB_Y[1] - 7.3, HUB_Y[1] + 1, x, z))
    return s


def insert_angles():
    crests = tooth_angles()
    return crests[::2]


def hub_cap():
    """TW03. Rotating cap with the internal ring gear; clamps the 61808 outer ring."""
    y_wall = CAP_Y[1] - CAP_END_PLATE
    s = yring(CAP_LIP[1] / 2, CAP_LIP[0] / 2, CAP_Y[0], HUB_Y[1], DX, DZ)
    s = s.union(yring(HUB_OD / 2, CAP_LIP[0] / 2, HUB_Y[1], y_wall, DX, DZ))
    s = s.union(ycyl(HUB_OD / 2, y_wall, CAP_Y[1], DX, DZ))
    s = s.union(xz_prism(ring_profile(), RING_Y[0], y_wall + .01, DX, DZ))
    # Pocket over the shaft end and pinion face: room for +1.5 mm of shaft length.
    s = s.cut(ycyl(11.5, y_wall - .01, y_wall + 1.0, DX, DZ))
    for k in range(6):            # webs between the ring gear and the outer wall
        a = math.radians(insert_angles()[k] + 30)
        web = cq.Workplane('XY').box(CAP_LIP[0] / 2 - RING_BODY_R + .8, y_wall - RING_Y[0], 3.0).translate(
            ((RING_BODY_R - .4 + CAP_LIP[0] / 2 + .4) / 2, (RING_Y[0] + y_wall) / 2, 0))
        web = web.rotate((0, 0, 0), (0, -1, 0), math.degrees(a)).translate((DX, 0, DZ))
        s = s.union(web)
    for a in insert_angles():
        x, z = polar(CAP_SCREW_R, a)
        s = s.cut(ycyl(1.7, HUB_Y[1] - 1, CAP_Y[1] + 1, x, z))
    # Fill and drain plugs of a full-size final-drive cover, recessed so the face prints flat.
    for a in [90, 270]:
        x, z = polar(22.0, a)
        s = s.cut(yring(3.2, 2.5, CAP_Y[1] - .5, CAP_Y[1] + 1, x, z))
        s = s.cut(cq.Workplane('XZ').center(x, z).polygon(6, 2.5 * 2 / math.sqrt(3)).extrude(1.8).translate((0, CAP_Y[1] + 1, 0)))
    return s


def bearing_retainer():
    """TW04. Stationary disc clamping the 61808 inner ring; held by the six gearbox screws."""
    s = ycyl(RETAINER_D / 2, RETAINER_Y[0], RETAINER_Y[1], DX, DZ)
    s = s.cut(ycyl(3.5, RETAINER_Y[0] - 1, RETAINER_Y[1] + 1, PX, PZ))
    for a in SCREW_PHASES:
        x, z = polar(GEARMOTOR['face_screw_circle'] / 2, PINION_ANGLE + a)
        s = s.cut(ycyl(1.7, RETAINER_Y[0] - 1, RETAINER_Y[1] + 1, x, z))
        s = s.cut(ycyl(3.1, face_screw_head_y(), RETAINER_Y[1] + 1, x, z))
    return s


def face_screw_head_y():
    """Bearing face of the button heads: 2.4 mm of thread in the gearbox face."""
    return FACE_Y - (GEARMOTOR['face_screw_max_depth'] - .6) + FACE_SCREW_LENGTH


def rear_cap():
    """TW05. Dust cap over the motor terminals with a grommet hole and two screw lugs."""
    y0, y1 = REAR_CAP_Y
    s = ycyl(TUBE_OD / 2, y0, y1, DX, DZ).cut(ycyl(TUBE_BORE / 2, y0 + 1.2, y1 + 1, DX, DZ))
    s = s.cut(ycyl(3.0, y0 - 1, y0 + 2, DX, DZ - 10))
    e0, e1 = REAR_CAP_EAR_Y
    for a in REAR_CAP_SCREWS:
        ear = box(TUBE_OD / 2 - 1, REAR_PILLAR_R[1], e0, e1, -REAR_PILLAR_HALF, REAR_PILLAR_HALF)
        s = s.union(ear.rotate((0, 0, 0), (0, -1, 0), a).translate((DX, 0, DZ)))
        x, z = polar(REAR_CAP_SCREW_R, a)
        s = s.cut(ycyl(1.7, e0 - 1, e1 + 1, x, z))
    return s


# ---------------------------------------------------------------- frame and idler
CH_Z0, CH_Z1 = AXLE_Z - CHANNEL_Z, AXLE_Z + CHANNEL_Z
SPY = SPRING_AXIS[0]
NOSE_BOLTS = [(134.0, SPY - 4.0), (134.0, SPY + 4.0)]
FLANGE_X = [-60.0, 0.0, 115.0]
BRIDGE_BOLT_Y = -54.0


def track_frame():
    """TW06. Rail plate with the final-drive boss and the recoil channel (right track)."""
    s = box(-140, 145, FRAME_Y[0], FRAME_Y[1], 24, 70)
    for x in FLANGE_X:
        s = s.union(box(x - 15, x + 15, -60, FRAME_Y[1], 64, 70))
    # Final-drive boss; the housing tube passes through it.
    s = s.union(ycyl(BOSS_D / 2, FRAME_Y[0], FRAME_Y[1], DX, DZ))
    s = s.cut(ycyl(TUBE_OD / 2 + .2, FRAME_Y[0] - 1, FRAME_Y[1] + 1, DX, DZ))
    for a in FLANGE_SCREWS:
        x, z = polar(FLANGE_SCREW_R, a)
        s = s.cut(ycyl(INSERT_M3['hole_d'] / 2, FRAME_Y[0] - 1, FRAME_Y[0] + 6.0, x, z))
    # Recoil spring housing and yoke channel.
    s = s.union(xcyl(SPRING_BORE_D / 2 + 2.0, REAR_WALL_X[0], SPRING_BORE_X[1], SPY, AXLE_Z))
    s = s.union(box(SPRING_BORE_X[1], 140, CHANNEL_Y[0] - WALL, CHANNEL_Y[1] + WALL, CH_Z0 - WALL, CH_Z1 + WALL))
    s = s.cut(xcyl(SPRING_BORE_D / 2, SPRING_BORE_X[0], SPRING_BORE_X[1] + .5, SPY, AXLE_Z))
    s = s.cut(box(SPRING_BORE_X[1], 141, CHANNEL_Y[0], CHANNEL_Y[1], CH_Z0, CH_Z1))
    s = s.cut(xcyl(3.2, REAR_WALL_X[0] - 1, REAR_WALL_X[1], SPY, AXLE_Z))
    s = s.cut(xhex(NUT_M6['af'] + .15, REAR_WALL_X[1] - NUT_M6['h'] - .1, REAR_WALL_X[1] + .1, SPY, AXLE_Z))
    s = s.cut(box(44.0, REAR_WALL_X[0] + .01, FRAME_Y[0] - .1, -37.6, AXLE_Z - 7.0, AXLE_Z + 7.0))
    lo, hi = NOSE_X[0] - (YOKE_X[0] - YOKE_STOP_X) - .3, NOSE_X[1] + FORWARD_TRAVEL + .3
    for y0, y1 in [(CHANNEL_Y[0] - WALL - .1, CHANNEL_Y[0] + .1), (CHANNEL_Y[1] - .1, CHANNEL_Y[1] + WALL + .1)]:
        s = s.cut(box(lo, hi, y0, y1, AXLE_Z - SLOT_HALF_Z, AXLE_Z + SLOT_HALF_Z))
    for x, y in NOSE_BOLTS:
        s = s.cut(zcyl(1.7, CH_Z0 - WALL - 1, CH_Z1 + WALL + 1, x, y))
        # Nut pocket opens through the rail plate bottom (Z 24) where the plate runs under the channel.
        s = s.cut(zhex(NUT_M3['af'] + .15, 23.9, CH_Z0 - WALL + NUT_M3['h'], x, y))
        s = s.cut(zcyl(3.1, CH_Z1 + WALL - .01, 71, x, y))       # head clearance in the rail top
    # Bridge bolts: M5. Front one uses a side-loaded nut in the channel roof.
    for x in FLANGE_X:
        s = s.cut(zcyl(2.7, 63, 71, x, BRIDGE_BOLT_Y))
    s = s.cut(box(115 - 4.7, 115 + 4.7, -61, BRIDGE_BOLT_Y + 4.7, 64.4, 68.6))
    # Roller axles through the rail plate.
    for x in ex.ROAD_ROLLERS:
        s = s.cut(ycyl(4.1, FRAME_Y[0] - 1, FRAME_Y[1] + 1, x, 29))
    for x in ex.RETURN_ROLLERS:
        s = s.cut(ycyl(4.1, FRAME_Y[0] - 1, FRAME_Y[1] + 1, x, RETURN_Z))
    return s


def idler_yoke():
    """TW07. Carries the idler axle; slides in the channel, pushed by the spring."""
    x0, x1 = YOKE_X
    s = box(x0, x1, SPY - YOKE_HALF[0], SPY + YOKE_HALF[0], AXLE_Z - YOKE_HALF[1], AXLE_Z + YOKE_HALF[1])
    s = s.union(box(NOSE_X[0], NOSE_X[1], CHANNEL_Y[0] - WALL, SPY - YOKE_HALF[0] + .01, AXLE_Z - NOSE_HALF_Z, AXLE_Z + NOSE_HALF_Z))
    s = s.union(box(NOSE_X[0], NOSE_X[1], SPY + YOKE_HALF[0] - .01, FRAME_Y[1], AXLE_Z - NOSE_HALF_Z, AXLE_Z + NOSE_HALF_Z))
    s = s.union(xcyl(SPIGOT_D / 2, x0 - YOKE_SPIGOT, x0 + .01, SPY, AXLE_Z))
    s = s.cut(ycyl(4.05, CHANNEL_Y[0] - WALL - 1, FRAME_Y[1] + 1, IDLER_X, AXLE_Z))
    return s


def spring_seat(extension=ADJUST_NOMINAL):
    """TW08. Sliding spring seat pushed by the M6 adjuster."""
    x0 = REAR_WALL_X[1] + extension
    s = xcyl(SEAT_D / 2, x0, x0 + SEAT_BLOCK, SPY, AXLE_Z)
    s = s.union(xcyl(SPIGOT_D / 2, x0 + SEAT_BLOCK - .01, x0 + SEAT_BLOCK + SEAT_SPIGOT, SPY, AXLE_Z))
    return s


def channel_nose():
    """TW09. Front stop block: limits forward travel; two M3 through bolts."""
    x0, x1 = NOSE_BLOCK_X
    s = box(x0, x1, CHANNEL_Y[0] + .2, CHANNEL_Y[1] - .2, CH_Z0 + .2, CH_Z1 - .2)
    for x, y in NOSE_BOLTS:
        s = s.cut(zcyl(1.7, CH_Z0 - 1, CH_Z1 + 1, x, y))
    return s


# ---------------------------------------------------------------- unchanged Track R4 parts
def track_shoe():
    shoe = box(-9.4, 9.4, -ex.SHOE_WIDTH / 2, ex.SHOE_WIDTH / 2, -6, -4)
    for x in ex.GROUSER_CENTRES:
        shoe = shoe.union(box(x - 1, x + 1, -ex.SHOE_WIDTH / 2, ex.SHOE_WIDTH / 2, -7, -6))
    for y0, y1 in [(-21, -14), (14, 21)]:
        railshoe = box(-10, 10, y0, y1, -4, 4).union(ycyl(4, y0, y1, -10, 0))
        railshoe = railshoe.cut(ycyl(4.3, y0 - 1, y1 + 1, 10, 0))
        railshoe = railshoe.cut(ycyl(1.6, y0 - 1, y1 + 1, -10, 0))
        shoe = shoe.union(railshoe)
    for y0, y1 in [(-13.7, -8.7), (8.7, 13.7)]:
        eye = ycyl(4, y0, y1, 10, 0).union(box(0, 10, y0, y1, -4, 0))
        shoe = shoe.union(eye.cut(ycyl(1.6, y0 - 1, y1 + 1, 10, 0)))
    return shoe.cut(zcyl(1.2, -8, -3, 0, -5)).cut(zcyl(1.2, -8, -3, 0, 5))


def idler_wheel():
    G = ex
    idler = yring(G.IDLER_GUIDE_R, 11.1, -7, 7)
    idler = idler.union(yring(14, 6.2, -10, 10))
    idler = idler.union(yring(28, 8.2, -20, 20))
    for y0, y1 in [(-20, -15), (15, 20)]:
        idler = idler.union(yring(G.IDLER_RAIL_R, 8.2, y0, y1))
    for sign in [-1, 1]:
        y0, y1 = sorted([sign * 20, sign * G.GUIDE_OUTER_Y]); idler = idler.union(yring(G.IDLER_RAIL_R, 8.2, y0, y1))
        y0, y1 = sorted([sign * G.GUIDE_INNER_Y, sign * G.GUIDE_OUTER_Y]); idler = idler.union(yring(G.IDLER_RAIL_R + G.GUIDE_HEIGHT, 8.2, y0, y1))
    return idler.cut(ycyl(11.1, -11, -3)).cut(ycyl(11.1, 3, 11))


def road_roller():
    G = ex
    roller = yring(13, 6.2, -20, 20)
    for y0, y1 in [(-20, -15), (15, 20)]:
        roller = roller.union(yring(18, 8.2, y0, y1))
    for sign in [-1, 1]:
        y0, y1 = sorted([sign * 20, sign * G.GUIDE_OUTER_Y]); roller = roller.union(yring(18, 11.1, y0, y1))
        y0, y1 = sorted([sign * G.GUIDE_INNER_Y, sign * G.GUIDE_OUTER_Y]); roller = roller.union(yring(18 + G.GUIDE_HEIGHT, 11.1, y0, y1))
    return roller.cut(ycyl(11.1, -24, -12.9)).cut(ycyl(11.1, 12.9, 24))


def return_roller():
    """Carrier roller: R4 layout with R5 rims (ex.RETURN_ROLLER_R) that keep carrying the sprung top run."""
    G = ex; R = G.RETURN_ROLLER_R
    r = yring(13, 6.2, -20, 20)
    for y0, y1 in [(-20, -15), (15, 20)]:
        r = r.union(yring(R, 6.2, y0, y1))
    for sign in [-1, 1]:
        y0, y1 = sorted([sign * 20, sign * G.GUIDE_OUTER_Y]); r = r.union(yring(R, 11.1, y0, y1))
        y0, y1 = sorted([sign * G.GUIDE_INNER_Y, sign * G.GUIDE_OUTER_Y]); r = r.union(yring(R + G.GUIDE_HEIGHT, 11.1, y0, y1))
    return r.cut(ycyl(11.1, -24, -13)).cut(ycyl(11.1, 13, 24))


PRINTED = [
    ('TW01_motor_housing', motor_housing, YELLOW, 1, 'Stationary gearmotor housing. Ø37.3 bore, Ø45 6809 seat, Ø40 61808 seat on the end wall, Ø12.15 bushing locator. 2 M3 heat-set inserts in the rear pillars.'),
    ('TW02_sprocket_hub', sprocket_hub, DARK, 1, 'Rotating 12-tooth bushing sprocket and hub drum; 6809 and 61808 outer-ring seats; 6 M3 × 5.7 heat-set inserts for the cap.'),
    ('TW03_hub_cap', hub_cap, YELLOW, 1, 'Rotating cap with the 21-tooth internal ring gear (m1.5, generated at 7.0 mm). Print in tough PETG or PA, solid infill around the teeth.'),
    ('TW04_bearing_retainer', bearing_retainer, DARK, 1, 'Clamps the 61808 inner ring; held by the six M3 × 10 gearbox face screws.'),
    ('TW05_motor_rear_cap', rear_cap, DARK, 1, 'Dust cap over the motor terminals; grommet hole; two M3 × 8 into the housing pillar inserts.'),
    ('TW06_track_frame', track_frame, DARK, 1, 'Right-hand rail. Mirror for the left (TW06_track_frame_left). Final-drive boss with 4 heat-set inserts; recoil channel; M6 captive nut.'),
    ('TW07_idler_yoke', idler_yoke, YELLOW, 1, 'Sliding idler yoke; Ø8 axle bore; spring spigot.'),
    ('TW08_spring_seat', spring_seat, DARK, 1, 'Sliding spring seat pushed by the M6 adjuster; spigot is the recoil stop.'),
    ('TW09_channel_nose', channel_nose, DARK, 1, 'Front stop of the yoke channel; two M3 × 40 through bolts with captive nuts.'),
]
TRACK_R4 = [('05_track_shoe', track_shoe, RUBBER, 34), ('07_idler_wheel', idler_wheel, DARK, 1),
            ('08_road_roller', road_roller, DARK, 3), ('24_return_roller', return_roller, DARK, 2)]


def printed_parts():
    out = {}
    for name, fn, color, qty, note in PRINTED:
        out[name] = dict(shape=fn().clean(), color=color, quantity=qty, note=note, material='PETG')
    out['TW03_hub_cap']['material'] = 'PETG or PA (tough)'
    for name, fn, color, qty in TRACK_R4:
        out[name] = dict(shape=fn().clean(), color=color, quantity=qty, note='Unchanged Track R4 part', material='PETG')
    out['24_return_roller']['note'] = (f'Track R5 carrier: Ø{2 * ex.RETURN_ROLLER_R:g} rims (R4: Ø28) stand {ex.CARRIER_LIFT:g} mm above '
                                       'the straight top run, so they keep carrying the sprung track. Two 608 bearings.')
    return out


# ---------------------------------------------------------------- purchased hardware
def gearmotor():
    """Pololu 37D 150:1 envelope from the drawing, in the unit frame."""
    g = GEARMOTOR; f = FACE_Y
    gb = ycyl(g['gearbox_diameter'] / 2, f - g['gearbox_length'], f, DX, DZ)
    for a in SCREW_PHASES:                       # tapped face holes, 3 mm deep
        x, z = polar(g['face_screw_circle'] / 2, PINION_ANGLE + a)
        gb = gb.cut(ycyl(1.5, f - g['face_screw_max_depth'], f + 1, x, z))
    can = ycyl(g['motor_diameter'] / 2, f - g['gearbox_length'] - g['motor_length'], f - g['gearbox_length'], DX, DZ)
    rear = f - g['gearbox_length'] - g['motor_length']
    boss = ycyl(g['rear_boss_diameter'] / 2, rear - g['rear_boss_length'], rear + .01, DX, DZ)
    bush = ycyl(g['bushing_diameter'] / 2, f - .01, f + g['bushing_length'], PX, PZ)
    terminals = [box(DX + sx * 11.25 - 1.45, DX + sx * 11.25 + 1.45, rear - g['terminal_projection'], rear + .01, DZ - .25, DZ + .25)
                 for sx in [-1, 1]]
    stator = gb.union(bush)
    body = can.union(boss)
    for t in terminals:
        body = body.union(t)
    return dict(gearbox=stator, motor=body)


FLAT_ANGLE = 105.0   # D-flat normal (XZ plane, deg from +X): faces a pinion tooth space


def _flat_halfspace(y0, y1, depth):
    """Region beyond the D-flat, built on +Z then turned to FLAT_ANGLE about the shaft axis."""
    cut = box(PX - 4, PX + 4, y0, y1, PZ + depth, PZ + 4)
    return cut.translate((-PX, 0, -PZ)).rotate((0, 0, 0), (0, -1, 0), FLAT_ANGLE - 90).translate((PX, 0, PZ))


def motor_shaft():
    g = GEARMOTOR
    flat = g['shaft_flat'] - g['shaft_diameter'] / 2
    s = ycyl(g['shaft_diameter'] / 2, FACE_Y + g['bushing_length'], FACE_Y + g['shaft_length'], PX, PZ)
    return s.cut(_flat_halfspace(FACE_Y, FACE_Y + g['shaft_length'] + 1, flat))


def pinion():
    g = GEARMOTOR; y0, y1 = PINION_Y
    flat = g['shaft_flat'] - g['shaft_diameter'] / 2
    s = xz_prism(pinion_profile(), y0, y1, PX, PZ)
    bore = ycyl(g['shaft_diameter'] / 2, y0 - 1, y1 + 1, PX, PZ).cut(_flat_halfspace(y0 - 2, y1 + 2, flat))
    s = s.cut(bore)
    return s.cut(set_screw(hole=True))


def set_screw(hole=False):
    """M3 x 4 set screw through the pinion body between two teeth, onto the flat."""
    g = GEARMOTOR; flat = g['shaft_flat'] - g['shaft_diameter'] / 2
    ym = sum(PINION_Y) / 2
    s = zcyl(1.5, PZ + flat - (.01 if hole else 0), PZ + (12 if hole else flat + 4.0), PX, ym)
    return s.translate((-PX, 0, -PZ)).rotate((0, 0, 0), (0, -1, 0), FLAT_ANGLE - 90).translate((PX, 0, PZ))


def bearing(kind, y0, y1, x=DX, z=DZ):
    b = BEARINGS[kind]; ri, ro = b['d'] / 2, b['D'] / 2
    inner_o = b['shoulder_d_max'] / 2; outer_i = b['housing_shoulder_D_min'] / 2 - .3
    inner = yring(inner_o, ri, y0, y1, x, z)
    outer = yring(ro, outer_i, y0, y1, x, z)
    seals = yring(outer_i - .01, inner_o + .01, y0 + .35, y1 - .35, x, z)
    return inner, outer, seals


def screw(r, head_r, head_h, y_head, length, x, z, outward=True, hexhead=False):
    """Screw along Y. Head bearing face at y_head; outward=True: head toward +Y."""
    d = 1 if outward else -1
    if hexhead:
        head = cq.Workplane('XZ').center(x, z).polygon(6, head_r * 2).extrude(head_h)
        head = head.translate((0, y_head + (head_h if outward else 0), 0))
    else:
        y0, y1 = sorted([y_head, y_head + d * head_h])
        head = ycyl(head_r, y0, y1, x, z)
    y0, y1 = sorted([y_head, y_head - d * length])
    return head.union(ycyl(r, y0, y1 + (0 if outward else 0), x, z))


def recoil_spring(length, x0, helix=True):
    """Spring along +X starting at x0. helix=False returns the solid envelope."""
    s = SPRING; ro = s['od'] / 2; ri = s['id'] / 2
    if not helix:
        return xring(ro, ri, x0, x0 + length, SPY, AXLE_Z)
    n_active = s['coils'] - 2; wire = s['wire']
    pitch = (length - 2 * wire) / n_active if n_active > 0 else wire
    rmean = (ro + ri) / 2
    path = cq.Wire.makeHelix(pitch, n_active * pitch, rmean)
    prof = cq.Wire.makeCircle(wire / 2, cq.Vector(rmean, 0, 0), cq.Vector(0, 1, 0))
    coil = cq.Solid.sweep(cq.Face.makeFromWires(prof), path, True, True).translate(cq.Vector(0, 0, wire))
    # Closed, ground end coils as flat rings. Kept as separate solids: fusing them to
    # the swept coil gives a shape that fails the STEP round trip.
    end0 = cq.Workplane('XY').circle(ro).circle(ri).extrude(wire).val()
    end1 = end0.translate(cq.Vector(0, 0, length - wire))
    spring = cq.Workplane(obj=cq.Compound.makeCompound([coil, end0, end1]))
    # Local +Z becomes +X.
    return spring.rotate((0, 0, 0), (0, 1, 0), 90).translate((x0, SPY, AXLE_Z))


def hardware(extension=ADJUST_NOMINAL):
    """Purchased parts in the unit frame: name -> (shape, color, group)."""
    h = {}
    gm = gearmotor()
    h['gearmotor_gearbox'] = (gm['gearbox'], GEARBOX, 'frame')
    h['gearmotor_motor'] = (gm['motor'], MOTOR, 'frame')
    h['gearmotor_shaft'] = (motor_shaft(), STEEL, 'pinion')
    h['hub_pinion'] = (pinion(), STEEL, 'pinion')
    # Set screw M3 x 4 between two teeth, onto the D-flat (radial, +Z).
    h['pinion_set_screw'] = (set_screw(), BLACK, 'pinion')
    for kind, (y0, y1) in [('inboard', INBOARD_BEARING_Y), ('outboard', OUTBOARD_BEARING_Y)]:
        inner, outer, seals = bearing(kind, y0, y1)
        h[f'bearing_{BEARINGS[kind]["model"]}_inner'] = (inner, STEEL, 'frame')
        h[f'bearing_{BEARINGS[kind]["model"]}_outer'] = (outer, STEEL, 'drive')
        h[f'bearing_{BEARINGS[kind]["model"]}_seals'] = (seals, BLACK, 'frame')
    hy = face_screw_head_y()
    for i, a in enumerate(SCREW_PHASES):
        x, z = polar(GEARMOTOR['face_screw_circle'] / 2, PINION_ANGLE + a)
        h[f'face_screw_{i}'] = (screw(1.5, BUTTON_M3['head_d'] / 2, BUTTON_M3['head_h'], hy, FACE_SCREW_LENGTH, x, z), BLACK, 'frame')
    for i, a in enumerate(insert_angles()):
        x, z = polar(CAP_SCREW_R, a)
        head = CAP_Y[1]
        h[f'cap_screw_{i}'] = (screw(1.5, BUTTON_M3['head_d'] / 2, BUTTON_M3['head_h'], head, CAP_SCREW_LENGTH, x, z), BLACK, 'drive')
        h[f'cap_insert_{i}'] = (yring(INSERT_M3['hole_d'] / 2, 1.5, HUB_Y[1] - INSERT_M3['length'], HUB_Y[1] - .05, x, z), BRASS, 'drive')
    for i, a in enumerate(FLANGE_SCREWS):
        x, z = polar(FLANGE_SCREW_R, a)
        h[f'flange_screw_{i}'] = (screw(1.5, CAP_M3['head_d'] / 2, CAP_M3['head_h'], FLANGE_Y[0], FLANGE_SCREW_LENGTH, x, z, outward=False), BLACK, 'frame')
        h[f'frame_insert_{i}'] = (yring(INSERT_M3['hole_d'] / 2, 1.5, FRAME_Y[0] + .05, FRAME_Y[0] + INSERT_M3['length'], x, z), BRASS, 'frame')
    for i, a in enumerate(REAR_CAP_SCREWS):
        x, z = polar(REAR_CAP_SCREW_R, a)
        h[f'rear_cap_screw_{i}'] = (screw(1.5, CAP_M3['head_d'] / 2, CAP_M3['head_h'], REAR_CAP_EAR_Y[0], REAR_CAP_SCREW_LENGTH, x, z, outward=False), BLACK, 'frame')
        h[f'pillar_insert_{i}'] = (yring(INSERT_M3['hole_d'] / 2, 1.5, REAR_CAP_EAR_Y[1] + .05, REAR_CAP_EAR_Y[1] + INSERT_M3['length'], x, z), BRASS, 'frame')
    # Recoil spring, adjuster, nuts.
    st = spring_state(extension, 0.0)
    seat_front = REAR_WALL_X[1] + extension + SEAT_BLOCK
    h['recoil_spring'] = (recoil_spring(st['length'], seat_front), SPRING_C, 'spring')
    tip = REAR_WALL_X[1] + extension
    head_face = tip - 16.0
    adj = xcyl(3.0, head_face, tip, SPY, AXLE_Z).union(xhex(HEX_M6['af'], head_face - HEX_M6['head_h'], head_face, SPY, AXLE_Z))
    h['adjuster_M6x16'] = (adj, STEEL, 'adjuster')
    h['adjuster_lock_nut'] = (xhex(NUT_M6['af'], REAR_WALL_X[0] - NUT_M6['h'], REAR_WALL_X[0], SPY, AXLE_Z).cut(
        xcyl(3.0, REAR_WALL_X[0] - 7, REAR_WALL_X[0] + 1, SPY, AXLE_Z)), STEEL, 'adjuster')
    h['adjuster_captive_nut'] = (xhex(NUT_M6['af'], REAR_WALL_X[1] - NUT_M6['h'], REAR_WALL_X[1], SPY, AXLE_Z).cut(
        xcyl(3.0, REAR_WALL_X[1] - 7, REAR_WALL_X[1] + 1, SPY, AXLE_Z)), STEEL, 'frame')
    for i, (x, y) in enumerate(NOSE_BOLTS):
        bolt = zcyl(1.5, CH_Z0 - WALL - 1.0, CH_Z1 + WALL + .01, x, y).union(zcyl(CAP_M3['head_d'] / 2, CH_Z1 + WALL, CH_Z1 + WALL + CAP_M3['head_h'], x, y))
        h[f'nose_bolt_{i}'] = (bolt, BLACK, 'frame')
        h[f'nose_nut_{i}'] = (zhex(NUT_M3['af'], CH_Z0 - WALL, CH_Z0 - WALL + NUT_M3['h'], x, y).cut(zcyl(1.5, 0, 100, x, y)), STEEL, 'frame')
    # Idler axle set: shaft, inboard collar, spacers, outer collar, bearings.
    ix = IDLER_X
    h['idler_axle'] = (ycyl(4, IDLER_AXLE_Y[0], IDLER_AXLE_Y[1], ix, AXLE_Z), STEEL, 'idler_slide')
    h['idler_collar_inboard'] = (yring(8, 4.05, IDLER_AXLE_Y[0], CHANNEL_Y[0] - WALL, ix, AXLE_Z), STEEL, 'idler_slide')
    for k, (a, b) in enumerate([(FRAME_Y[1], -10), (-3, 3), (10, 21)]):
        h[f'idler_spacer_{k}'] = (yring(6, 4.05, a, b, ix, AXLE_Z), STEEL, 'idler_slide')
    h['idler_collar_outboard'] = (yring(8, 4.05, 21, 26, ix, AXLE_Z), STEEL, 'idler_slide')
    for k, (a, b) in enumerate([(-10, -3), (3, 10)]):
        h[f'idler_608_{k}'] = (yring(11, 4, a, b, ix, AXLE_Z), STEEL, 'idler')
    # Road and return roller axles: the Track R4 Ø8 × 79 shaft and stack.
    for j, (x, z) in enumerate([(v, 29) for v in ex.ROAD_ROLLERS] + [(v, RETURN_Z) for v in ex.RETURN_ROLLERS]):
        grp = f'roller{j}' if j < 3 else f'return{j - 3}'
        h[f'axle_{grp}'] = (ycyl(4, -53, 26, x, z), STEEL, 'frame')
        for k, (a, b) in enumerate([(-47, -42), (21, 26)]):
            h[f'collar_{grp}_{k}'] = (yring(8, 4.05, a, b, x, z), STEEL, 'frame')
        for k, (a, b) in enumerate([(-30, -20), (-13, 13), (20, 21)]):
            h[f'spacer_{grp}_{k}'] = (yring(6, 4.05, a, b, x, z), STEEL, 'frame')
        for k, (a, b) in enumerate([(-20, -13), (13, 20)]):
            h[f'608_{grp}_{k}'] = (yring(11, 4, a, b, x, z), STEEL, grp)
    return h


def chain(parts):
    """34 links in the exact-pitch assembly pose: shoes, pins, sleeves, clips."""
    out = {}
    for i, origin, a in ex.track_poses():
        out[f'shoe_{i:02}'] = (parts['05_track_shoe']['shape'].rotate((0, 0, 0), (0, 1, 0), -math.degrees(a)).translate((float(origin[0]), 0, float(origin[1]))), RUBBER)
    for i, (x, z) in enumerate(ex.track_pins()):
        out[f'track_bushing_{i:02}'] = (yring(ex.BUSH_R, 1.55, -ex.BUSH_LENGTH / 2, ex.BUSH_LENGTH / 2, x, z), STEEL)
        out[f'track_pin_{i:02}'] = (ycyl(1.5, -ex.PIN_LENGTH / 2, ex.PIN_LENGTH / 2, x, z), STEEL)
        for k, dy in enumerate([-ex.PIN_CLIP_Y, ex.PIN_CLIP_Y]):
            out[f'pin_clip_{i:02}_{k}'] = (yring(3, 1.5, dy - .3, dy + .3, x, z), STEEL)
    return out


def unit_instances(parts=None, extension=ADJUST_NOMINAL, with_chain=True, yoke_shift=0.0):
    """All solids of one track unit, assembly pose, unit frame.

    Groups: frame (stationary), drive (hub, turns about the drive axis), pinion
    (turns about the shaft axis), idler_slide (yoke and axle), idler (wheel),
    spring, adjuster, rollerN / returnN, track. yoke_shift moves the idler
    slide from the assembly pose (negative = recoil); the chain is only valid at 0.
    """
    parts = printed_parts() if parts is None else parts
    out = {}
    def add(n, s, color, group, kind, source=None):
        out[n] = dict(shape=s, color=color, group=group, kind=kind, source=source)
    for n in ['TW01_motor_housing', 'TW04_bearing_retainer', 'TW05_motor_rear_cap', 'TW06_track_frame', 'TW09_channel_nose']:
        add(n, parts[n]['shape'], parts[n]['color'], 'frame', 'printed', n)
    for n in ['TW02_sprocket_hub', 'TW03_hub_cap']:
        add(n, parts[n]['shape'], parts[n]['color'], 'drive', 'printed', n)
    add('TW07_idler_yoke', parts['TW07_idler_yoke']['shape'], parts['TW07_idler_yoke']['color'], 'idler_slide', 'printed', 'TW07_idler_yoke')
    seat = spring_seat(extension) if extension != ADJUST_NOMINAL else parts['TW08_spring_seat']['shape']
    add('TW08_spring_seat', seat, parts['TW08_spring_seat']['color'], 'adjuster', 'printed', 'TW08_spring_seat')
    add('07_idler_wheel', parts['07_idler_wheel']['shape'].translate((IDLER_X, 0, AXLE_Z)), DARK, 'idler', 'printed', '07_idler_wheel')
    for j, x in enumerate(ex.ROAD_ROLLERS):
        add(f'08_road_roller_{j}', parts['08_road_roller']['shape'].translate((x, 0, 29)), DARK, f'roller{j}', 'printed', '08_road_roller')
    for j, x in enumerate(ex.RETURN_ROLLERS):
        add(f'24_return_roller_{j}', parts['24_return_roller']['shape'].translate((x, 0, RETURN_Z)), DARK, f'return{j}', 'printed', '24_return_roller')
    for n, (s, color, group) in hardware(extension).items():
        add(n, s, color, group, 'hardware')
    if with_chain:
        for n, (s, color) in chain(parts).items():
            add(n, s, color, 'track', 'printed' if n.startswith('shoe_') else 'hardware', '05_track_shoe' if n.startswith('shoe_') else None)
    # Exact-pitch assembly pose: the idler sits 0.2005 mm behind nominal.
    off = ex.IDLER_ASSEMBLY_OFFSET + yoke_shift
    for n, d in out.items():
        if d['group'] in ['idler_slide', 'idler']:
            d['shape'] = d['shape'].translate((off, 0, 0))
    st = spring_state(extension, off)
    seat_front = REAR_WALL_X[1] + extension + SEAT_BLOCK
    out['recoil_spring']['shape'] = recoil_spring(st['length'], seat_front)
    out['recoil_spring']['envelope'] = recoil_spring(st['length'], seat_front, helix=False)
    return out

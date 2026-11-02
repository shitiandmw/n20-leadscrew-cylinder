"""V6 shared geometry: one source of numbers for the magnet model, the PCB and the CAD.

Units mm. Z is the actuator axis (+Z toward the rod eye), Z = 0 is the gearbox front face.
+X is the board side: the PCB stands in a slot on +X with its parts facing the bore.
Y is the clevis-pin axis. All Z values are for travel 0 (retracted end, U1 just tripped).

The body is one printed square tube, about 15 x 15 mm, printed rear end down:
  - rectangular bore 10.3 x 12.3 for the motor (behind the wall) and the carrier (in front),
    with a corner rib that lets the carrier in only one way round;
  - an integral 2 mm wall at Z = 0..2 that the motor is screwed to (2 x M1.6, countersunk);
  - the board slot on +X, separated from the bore by an integral 1 mm PETG partition;
  - solid +X corners that take the 2 x M2 screws of each end cap.
"""
import math

# ---- bore and body section -------------------------------------------------------------
BORE_X = 5.15                 # half width, motor gearbox is 10 wide
BORE_Y = 6.15                 # half height, gearbox is 12 high
BORE_R = 0.7                  # corner radius (gearbox plates have 0.6 mm fillets)
BODY_X = (-6.35, 9.75)        # outer, X; +1.15 mm on the PCB side for the partition
BODY_Y = 7.35                 # outer half height
BODY_R = 1.5                  # outer corner radius
WALL_Z = (0.0, 2.0)           # motor wall
MOTOR_SCREWS = ((0.0, 4.5), (0.0, -4.5))   # M1.6 holes in the gearbox front face
CAP_SCREWS = ((8.00, 5.75), (8.00, -5.75)) # M2 pilot holes, both end caps
CAP_SCREW_PILOT = 1.6
CAP_SCREW_CLEAR = 2.2

# ---- board slot ------------------------------------------------------------------------
PCB_T = 0.8
PCB_W = 8.0
PARTITION_T = 1.0             # continuous printed barrier over the full PCB length
PARTITION_X = (BORE_X, BORE_X + PARTITION_T)
PART_MAX_H = 1.25             # AO3400A package, the tallest component in board.py
PARTITION_COMPONENT_GAP = 0.30
PCB_X_INNER = PARTITION_X[1] + PARTITION_COMPONENT_GAP + PART_MAX_H
PCB_X_OUTER = PCB_X_INNER + PCB_T
SLOT_X = (PCB_X_INNER - 0.05, PCB_X_OUTER + 0.05)  # 0.05 mm board play each way
SLOT_Y = 4.10                 # groove half height (board 4.0)
OPEN_Y = 3.25                 # half height of component cavity behind the partition
PART_BAND_Y = 3.0             # parts must stay within |y| <= this on the board
PCB_Z0 = WALL_Z[1]            # board rear edge rests on the wall: same datum as the motor
WIRE_HOLE = (PARTITION_X[1], SLOT_X[0], -3.0, 3.0)  # passage stays on the PCB side
                                              # still rests on the wall behind the groove

# ---- carrier, nut, magnet --------------------------------------------------------------
CARRIER_X = 5.0               # half width (0.15 clearance per side)
CARRIER_Y = 6.0
CARRIER_LEN = 10.0
OVERTRAVEL = 3.0              # allows the increased magnetic switching spread through the partition
CARRIER_Z0 = WALL_Z[1] + OVERTRAVEL  # carrier rear face at travel 0
NUT_SLOT_DZ = (1.8, 4.3)      # from the carrier rear face; M3 brass nut 5.5 AF x 2.4
NUT_AF = 5.5
MAGNET = dict(d=3.0, l=2.0, axis="Z (along the travel)", grade="N35", x=3.3, y=0.0, dz=6.0)
#   magnet centre x: its +X side sits 0.2 mm inside the carrier face (x = 4.8)
HALL_ELEMENT_DEPTH = 0.70     # DRV5033 DBZ: element 0.7 +/- 0.05 mm above the package bottom
HALL_X = PCB_X_INNER - HALL_ELEMENT_DEPTH
HALL_LEAD = 5.3               # Hall centre sits this far outboard of the magnet's end position
                              # (typical switch point; magnet_trigger.py checks it)

# ---- rod and caps ----------------------------------------------------------------------
ROD_D = 8.0
ROD_BORE = 3.9                # clears the M3 leadscrew
ROD_GUIDE_D = 8.3             # hole in the front cap
FRONT_CAP_T = 6.0
SPIGOT = 1.0                  # front-cap spigot inside the bore; the carrier stops on it
REAR_CAP_T = 4.0              # the body's rear face is flat: it prints rear end down
EYE_OD = 9.0
EYE_T = 6.0
PIN_HOLE = 3.2                # for 3 mm clevis pins
BODY_REAR_Z = -27.5           # 1 mm behind the motor terminal tips
WIRE_OD = 0.8                 # 28 AWG PTFE: two motor leads and the two cable wires

# ---- rear cable clamp and carrier key ------------------------------------------------------
SLEEVE_OD, SLEEVE_ID = 3.0, 2.0   # protective sleeve over the two cable wires (silicone or PVC tube)
CLAMP_X0 = 5.4                # cable clamp plate from here to the +X face, beside the clevis
CLAMP_T = 3.0                 # clamp plate thickness; it sits CLAMP_POCKET deep in the rear cap
CLAMP_POCKET = 1.0             # leaves 1.7 mm of cap over the groove
CLAMP_SQUEEZE = 0.4           # the 3.0 mm sleeve is held in a 2.6 mm high groove, plus ridges
CLAMP_SCREW_L = 10.0          # the two rear-cap screws pass through the clamp plate: M2 x 10
CARRIER_KEY = 2.0             # corner rib in the bore (-X, -Y): the rod only fits magnet-to-board

VARIANTS = {                  # in order of screw length
    "S": dict(screw_length=55.0, stroke=40.0),
    "U60": dict(screw_length=75.0, stroke=60.0),       # the 60 mm excavator arm's common actuator (four per arm)
    "L": dict(screw_length=100.0, stroke=85.0),
}


def derived(variant):
    v = VARIANTS[variant]
    stroke, screw = v["stroke"], v["screw_length"]
    magnet_z0 = CARRIER_Z0 + MAGNET["dz"]
    nut_front = CARRIER_Z0 + NUT_SLOT_DZ[1]
    carrier_front_max = CARRIER_Z0 + CARRIER_LEN + stroke + OVERTRAVEL   # hard stop at the front
    body_front = carrier_front_max + SPIGOT
    hall_z = (magnet_z0 - HALL_LEAD, magnet_z0 + stroke + HALL_LEAD)
    pcb_z1 = hall_z[1] + 2.3                                   # board ends 0.5 mm inside the body
    rod_end = body_front + FRONT_CAP_T + 3.0 + 9.0       # 3 mm clear of the cap, 9 mm eye socket
    eye_front_z = rod_end + 5.5
    rear_eye_z = BODY_REAR_Z - REAR_CAP_T - 4.5 - 1.5
    d = dict(
        variant=variant, screw_length_mm=screw, stroke_mm=stroke,
        nut_front_z=nut_front, nut_margin_on_screw_mm=round(screw - 0.5 - (nut_front + stroke + OVERTRAVEL), 2),
        magnet_end_z=(magnet_z0, magnet_z0 + stroke), hall_z=hall_z,
        pcb_z=(PCB_Z0, pcb_z1), pcb_length=round(pcb_z1 - PCB_Z0, 2),
        body_z=(BODY_REAR_Z, body_front), front_cap_z=(body_front, body_front + FRONT_CAP_T),
        carrier_front_max_z=carrier_front_max,
        rod_end_z=rod_end, rod_bore_end_z=rod_end - 9.0 - 1.0,
        eye_front_z=eye_front_z, rear_eye_z=rear_eye_z,
        pin_centres_closed=round(eye_front_z - rear_eye_z, 2),
        pin_centres_open=round(eye_front_z - rear_eye_z + stroke, 2),
        body_section=(round(BODY_X[1] - BODY_X[0], 2), round(2 * BODY_Y, 2)),
        partition_thickness_mm=PARTITION_T, partition_x_mm=PARTITION_X,
        partition_z_mm=(WALL_Z[1], body_front),
        partition_component_gap_mm=PARTITION_COMPONENT_GAP,
        carrier_partition_gap_mm=round(PARTITION_X[0] - CARRIER_X, 3),
        magnet_diameter_mm=MAGNET["d"], magnet_length_mm=MAGNET["l"],
    )
    assert d["nut_margin_on_screw_mm"] >= 2.0, "leadscrew too short for this stroke"
    assert d["rod_bore_end_z"] >= screw + 0.5, "rod bore does not clear the screw tip"
    return d


if __name__ == "__main__":
    import json
    for k in VARIANTS:
        print(json.dumps(derived(k), indent=1))

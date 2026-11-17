"""V6 shared geometry: one source of numbers for the magnet model, the PCB and the CAD.

Units mm. Z is the actuator axis (+Z toward the rod eye), Z = 0 is the gearbox front face.
+X is the board side: the PCB stands in a slot on +X with its parts facing the bore.
Y is the clevis-pin axis. All Z values are for travel 0 (retracted end, U1 just tripped).

The body is one printed square tube, 17.3 x 14.7 mm, printed front end down:
  - rectangular bore 10.3 x 12.3 for the motor (behind the wall) and the carrier (in front),
    with a corner rib that lets the carrier in only one way round;
  - a 2.4 mm wall on the motor side (-X) whose end reaches into the rear cap and hooks it (REAR_HOOK);
  - an integral 2 mm wall at Z = 0..2 that the motor is screwed to (2 x M1.6, countersunk), with a
    Ø4.8 hole for the gearbox bushing and the M4 leadscrew;
  - the board slot on +X, separated from the bore by an integral 1 mm PETG partition;
  - solid +X corners with two M1 heat-set inserts at each end face for the end-cap screws, each
    insert placed where its corner is thickest (rear and front positions differ), and a third front
    insert on the motor side, in the corner thickened by the key rib.
"""
import math

# ---- bore and body section -------------------------------------------------------------
BORE_X = 5.15                 # half width, motor gearbox is 10 wide
BORE_Y = 6.15                 # half height, gearbox is 12 high
BORE_R = 0.7                  # corner radius (gearbox plates have 0.6 mm fillets)
BODY_X = (-7.55, 9.75)        # outer, X; +1.15 mm on the PCB side for the partition; -X wall 2.4 for the rear hook
BODY_Y = 7.35                 # outer half height
BODY_R = 1.5                  # outer corner radius
WALL_Z = (0.0, 2.0)           # motor wall
WALL_HOLE_D = 4.8             # the Ø4 bushing and the M4 thread pass the wall with 0.4 mm all round
MOTOR_SCREWS = ((0.0, 4.5), (0.0, -4.5))   # M1.6 holes in the gearbox front face
# End caps: M1 x 8 pan-head screws into brass heat-set inserts pressed into the body's end faces, two in the rear
# face and three in the front face. The PETG round a 2.0 mm knurl, measured on the body section (2026-11-11):
#   rear end, behind the motor wall: no board groove there, only the wire channel (|y| <= OPEN_Y), so the
#     corner is 4.1 mm tall; at (7.45, +-5.30) the knurl has 1.05 mm all round (the section's largest circle);
#   front end: the board groove (|y| <= SLOT_Y) runs out to the front face; the largest circle is at
#     (6.85, +-5.65), 0.70 mm round the knurl, between the groove's inner corner, the side face and the bore;
#   front end, motor side (2026-11-14): the bore's key rib (CARRIER_KEY) makes its (-X, -Y) corner the one thick
#     spot on the motor side. At (-5.76, -5.56) the knurl has 0.78 mm all round: 1.79 mm from both side faces and
#     from the rib's face, the section's largest circle with the rib at 2.5 mm. The rear cap hooks onto the
#     motor-side wall (REAR_HOOK), but the front cap is threaded onto the rod and can only go on straight; with
#     both its screws on +X, a push on its spigot tipped it about the body's +X edge and each screw carried about
#     1.9x the push. The third screw puts the push inside the screws' triangle: 0.52x at most
#     (images/front_cap_screws.png).
# Insert makers ask for at least 1.5x, ideally 2x, the knurl diameter: front 1.70x and 1.78x, rear 2.05x.
REAR_INSERTS = ((7.45, 5.30), (7.45, -5.30))
FRONT_INSERTS = ((6.85, 5.65), (6.85, -5.65), (-5.76, -5.56))
INSERT = dict(name="M1 x 1.8 x 2", thread="M1 x 0.25", od=2.0, length=1.8, bore=0.8,
              hole=1.7, hole_depth=3.5, recess=0.1)
#   bought as "M1 x 1.8 x 2" (thread x length x knurl diameter), pressed in with a soldering iron until its
#   outer end is 0.1 mm below the face; the 1.7 mm hole runs on 1.6 mm deeper for the screw tip and the melt.
CAP_SCREW = dict(d=1.0, length=8.0, head_d=2.0, head_h=0.7, clear=1.2, pocket_d=2.6, pocket_depth=1.0)
#   M1 x 8 pan head, A2-70 stainless, PH000 cross recess. The heads sit in 2.6 x 1.0 mm pockets in the front
#   cap and the cable clamp, 0.3 mm below the face; each screw then reaches 3.0 mm into the body: through
#   the whole insert and 1.1 mm beyond it, 0.5 mm short of the hole bottom.

# Rear-cap hook (2026-11-11). The cap's screws sit on +X only, so a pull on the rear pin would tip the cap about
# its +X edge (images/rear_cap_pull.png). The end of the motor-side (-X) wall therefore reaches into a pocket in
# the rear cap, and a 45 degree tooth on the cap sits in a notch cut into the inside of that wall end. The cap goes
# on SHIFT toward +X, slides back so the tooth enters the notch, and the two screws stop it sliding out again.
# Nothing may stand in the motor bay: the motor goes in from the rear. The profile is blunt so that it prints
# true (images/rear_cap_hook.png): the bevels touch only on their middle, everything else has room. Section in x
# (from the bay's -X face, x = -BORE_X) and z (from the rear face, BODY_REAR_Z):
REAR_HOOK = dict(
    half_width=BORE_Y - BORE_R,   # 5.45: the wall end and the notch run along the flat part of the bay face
    reach=1.6,                    # the wall end stands this far behind the rear face, into the cap
    notch=0.6,                    # notch depth into the 2.4 mm wall: 1.8 mm is left
    head=0.6,                     # flat inner face at the wall end, before the bevel
    floor=0.4,                    # from the bevel's lower end to the rear face, fillet included
    fillet=0.2,                   # inside corner of the notch
    inner_chamfer=0.2,            # wall end's inner corner: it sits in the pocket's inside corner
    tip_room=0.15,                # under the tooth's flat tip, so the bevels touch on 0.45 mm only
    side_room=0.15,               # between the wall end and the pocket's inner face
    end_room=0.3,                 # behind the wall end: the pocket floor prints as a bridge and may sag
    y_room=0.1,                   # at each end of the pocket
    bed_chamfer=0.2,              # tooth tip and pocket ends on the cap's face: first-layer squash (face down)
    shift=0.8,                    # fitting: on this far toward +X, then slid back
)


def rear_hook_profile():
    """Corner points of the hook section, x and z in the model frame: the wall end, the notch and the tooth."""
    h = REAR_HOOK
    xi, zr = -BORE_X, BODY_REAR_Z
    zb = zr - h["notch"] - h["floor"]                 # top of the bevel on the inner face
    eng = h["notch"] - h["tip_room"]                  # how far the tooth reaches into the wall
    return dict(xi=xi, x0=BODY_X[0], xn=xi - h["notch"], xt=xi - eng, xp=xi + h["side_room"], eng=eng,
                zr=zr, zb=zb, ze=zr - h["reach"], zp=zr - h["reach"] - h["end_room"],
                y_wall=h["half_width"], y_pocket=h["half_width"] + h["y_room"])

# ---- board slot ------------------------------------------------------------------------
PCB_T = 0.8
PCB_W = 8.0
PARTITION_T = 1.0             # continuous printed barrier over the full PCB length
PARTITION_X = (BORE_X, BORE_X + PARTITION_T)
PART_MAX_H = 1.25             # allowance for the tallest component (IRLML0060 and DRV5033 SOT-23: 1.12 max)
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
NUT_SLOT_DZ = (1.8, 4.1)      # from the carrier rear face; M4 thin brass nut (ISO 4035) 7 AF x 2.2, 0.1 mm play
NUT_AF = 7.0
NUT_T = 2.2
# N35 block 3 (Y) x 2 (X) x 2 (Z) mm, magnetised through a 2 mm face, along the travel. The M4 screw (r 2.0)
# leaves no room for the earlier Ø3 x 2 cylinder (x 1.8..4.8); the block sits at x 2.8..4.8, 0.4 mm of PETG
# from the Ø4.8 bore and 0.8 mm from the thread crests, and switches the Halls within the same spread
# (magnet_trigger.py; 2026-11-10 study: Ø3 x 2 cylinder 3.65..7.45 mm, this block 3.65..7.07 mm).
MAGNET = dict(shape="box", wy=3.0, wx=2.0, l=2.0, axis="Z (along the travel)", grade="N35", x=3.8, y=0.0, dz=6.0)
#   magnet centre x: its +X side sits 0.2 mm inside the carrier face (x = 4.8)
MAGNET_NAME = "magnet_3x2x2_axial"


def magnet_label():
    m = MAGNET
    return f"{m['wy']:g} × {m['wx']:g} × {m['l']:g} mm"


def magnet_field_shape():
    """magnet_field.py shape for an axis along Z: its first transverse vector is +Y, its second -X."""
    return ("box", MAGNET["wy"], MAGNET["wx"], MAGNET["l"])
HALL_ELEMENT_DEPTH = 0.70     # DRV5033 DBZ: element 0.7 +/- 0.05 mm above the package bottom
HALL_X = PCB_X_INNER - HALL_ELEMENT_DEPTH
HALL_LEAD = 5.1               # Hall centre sits this far outboard of the magnet's end position: the block
                              # magnet's typical switch point (5.08 mm; magnet_trigger.py checks it)

# ---- rod and caps ----------------------------------------------------------------------
ROD_D = 8.0
ROD_BORE = 4.8                # clears the M4 leadscrew: 0.4 mm all round
ROD_GUIDE_D = 8.3             # hole in the front cap
FRONT_CAP_T = 6.0
SPIGOT = 1.0                  # front-cap spigot inside the bore; the carrier stops on it
REAR_CAP_T = 4.0
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
CARRIER_KEY = 2.5             # corner rib in the bore (-X, -Y): the rod only fits magnet-to-board. 2.0 until
                              # 2026-11-14; 2.5 gives the third front insert its 0.78 mm (FRONT_INSERTS)

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
        magnet_size_mm=[MAGNET["wy"], MAGNET["wx"], MAGNET["l"]], magnet_length_mm=MAGNET["l"],
    )
    assert d["nut_margin_on_screw_mm"] >= 2.0, "leadscrew too short for this stroke"
    assert d["rod_bore_end_z"] >= screw + 0.5, "rod bore does not clear the screw tip"
    return d


if __name__ == "__main__":
    import json
    for k in VARIANTS:
        print(json.dumps(derived(k), indent=1))

"""The wiring harness of the complete X1 excavator: every cable, where it runs and what it plugs into.

Frames: vehicle (X forward, Y left, Z up, origin on the ground under the swing centre) at swing 0 for everything
fixed to the upper or the lower; R12 body frames ('base' = O frame, 'boom', 'stick') for the cables on the arm, which
move with it (common.O_VEH puts O at vehicle (30, 0, 195)).

What is modelled
  * static runs: polylines fixed to the upper (board, slip ring, swing motor, battery, lamps) or to the lower (track
    motor leads to the slip-ring stator);
  * arm runs: polylines fixed to one arm body (the boom-top side lanes, the stick side lane) between printed W01
    clamps, plus the four V6 cable exits (the sleeve leaves the rear-cap clamp sideways on the board side);
  * loops: a fixed length of cable between a clamp on one body and a clamp on the next (round pin O and pin E),
    taken as the circular arc of that length through the two clamps, bulging away from the part it must avoid;
  * drops: the boom-drive sleeves from their moving exits down through the B01X slots (the cable slides in the slot),
    taken as a cubic between the exit (its exit direction) and the slot (vertical).
check_wiring.py tests these against the machine over the poses; build_viewer.py draws them (the loops and drops
are rebuilt in the page from the same anchors and lengths).
"""
import math
import sys
import numpy as np
import common as K

sys.path.insert(0, str(K.R12 / 'source'))
import r12_design as d                                   # noqa: E402
from poses_r12 import DRIVES                            # noqa: E402
from shapely.geometry import LineString                  # noqa: E402

SLEEVE_OD = 3.0            # V6 cable: two 28 AWG PTFE wires in a 3 mm silicone sleeve (actuator_v6 BOM)
TUBE_R = 1.75              # modelled radius of a sleeve (0.25 margin)
LEAD_R = 1.3               # modelled radius of a 2-wire 26 AWG silicone lead pair (track, swing, lamp 2)
BUNDLE_R = 2.2             # slip-ring rotor leads (6 x 0.75 mm leads)
POWER_R = 2.0              # 2 x 20 AWG silicone (battery, 12 V link)
THIN_R = 0.5               # 2 x 0.2 mm enamelled wire (roof lamps)
MIN_BEND_R = 9.0           # 3 x OD for the 3 mm sleeve; the loops and drops are checked against it
CLEAR = 1.0                # required clearance to parts the cable is not attached to, as R12's rule
SLACK = 6.0                # a loop is this much longer than its longest chord

# ------------------------------------------------------------------ B01X cable features (O frame; see build_adapter.py)
# T101 has two full-width bulkheads under the plate (X -38..-30 and 30..38 vehicle; probe map in check_wiring.py), so a
# cable can only leave the plate's underside through the 9 mm gap between the plate's rear edge (X -21) and the rear
# bulkhead. Every arm cable therefore goes down through one slot per side at vehicle X 0..8, in the middle compartment:
#   * the stick and bucket cables come down from the loop posts behind the slots;
#   * the boom-drive sleeves land in a trough cut into the plate top under their exits and run rearward in it to the slot.
PLATE_TOP = -49.0                  # O frame (vehicle 146)
SLOTS = {                          # name: (x centre, y centre, length along X, width along Y): one per side
    'S3': (-26.0, 39.5, 8.0, 7.0),    # left: stick cable (from the post) and the boom L sleeve (from the trough)
    'S4': (-26.0, -39.5, 8.0, 7.0),   # right: bucket cable and the boom R sleeve
}
# The trough's centreline (O frame, |Y|): the sleeve lands and slides at the drive's own Y (34) in a 9 mm wide mouth, then the
# trough eases outboard to the slot (Y 39.5) over 42 mm so the sleeve is not bent sideways where it moves.
TROUGH = dict(path=[(47.0, 34.0), (20.0, 34.0), (0.0, 37.5), (-22.0, 39.5)], mouth_to_x=20.0, mouth_w=9.0, w=5.0, depth=7.0, y_land=34.0)
TROUGH_Z = PLATE_TOP - TROUGH['depth'] + TUBE_R                                        # cable centre in the trough: -54.25
TROUGH_TIES_X = (8.0, 30.0)        # cable-tie slot pairs across the trough (one in the mouth, one behind the slide)
POST = dict(x=-34.0, y=39.5, r=3.0, top=-26.0, r_base=5.0, tie_z=-30.0)   # cable posts: Ø6 from the plate top to z -26, Ø2.6 tie hole
TIE_SLOT = (3.5, 1.6)
SLOT_T = SLOTS['S3'][3]

# ------------------------------------------------------------------ connectors on the main board (vehicle, swing 0)
# From main_board/X1_main_board_A_parts.json and the board STEP (x1_body.main_board): the inboard JST headers face -Y with
# their mating faces at Y 84.54; the mated housings (XHP-2/-4, PHR-3) stand 1.5 proud, to Y 83.04, and 4 mm of their
# wires are drawn with them (stdparts.py), so a cable tube ends at Y 79.0. The XT30PW-M is on the front edge (X -40) and
# mates from +X; the XT30U-F of the 12 V link is drawn by build_connectors.py at its mouth.
PLUG_Z = dict(XH=114.65, PH=114.0, XT30=114.2)
PLUG_WIRE_END_Y = 79.0
HEADER_FACE_Y = 84.54
BOARD = {
    'J101': dict(kind='XT30', pins=('VBAT_IN', 'GND'), end=(-25.0, 133.5, 114.2), tangent=(-1, 0, 0),
                 note='12 V in from the toolbox (battery, BMS, 5 A fuse, main switch)'),
    'J102': dict(kind='XH4', pins=('OUT1_TL', 'OUT2_TL', 'OUT1_TR', 'OUT2_TR'), x=-53.95, note='tracks, from the slip ring'),
    'J103': dict(kind='XH2', pins=('OUT1_SW', 'OUT2_SW'), x=-101.45, note='swing motor'),
    'J104': dict(kind='XH2', pins=('OUT1_BL', 'OUT2_BL'), x=-65.45, note='boom drive, left'),
    'J105': dict(kind='XH2', pins=('OUT1_BR', 'OUT2_BR'), x=-74.45, note='boom drive, right'),
    'J106': dict(kind='XH2', pins=('OUT1_ST', 'OUT2_ST'), x=-83.45, note='stick drive'),
    'J107': dict(kind='XH2', pins=('OUT1_BK', 'OUT2_BK'), x=-92.45, note='bucket drive'),
    'J108': dict(kind='PH3', pins=('+5V_LAMP', 'LAMP1_K', 'LAMP2_K'), x=-110.7, note='lamps: roof pair, toolbox'),
    'J109': dict(kind='PH4', pins=('+5V_EXP', 'GND', 'EXP_TX', 'EXP_RX'), x=-121.2, note='expansion (not fitted)'),
}
for _k, _c in BOARD.items():
    if 'x' in _c:
        z = PLUG_Z['XH' if _c['kind'].startswith('XH') else 'PH']
        _c['end'] = (_c['x'], PLUG_WIRE_END_Y, z)
        _c['tangent'] = (0, 1, 0)
        # the last 25 mm are the bare wires out of the sleeve: they drop from the bay run (above the plugs) into the gap
        # between the T101 rib (Y 69) and the plug wires (Y 79), then turn into the plug
        _c['approach'] = [(_c['x'], 76.0, 122.0), (_c['x'], 70.5, 118.5), (_c['x'], 70.5, z), _c['end']]

# ------------------------------------------------------------------ body features (vehicle, swing 0)
RIB_TOP_Z = 136.0
LEFT_RIB_Y, RIGHT_RIB_Y = 65.0, -65.0        # T101 rib centres (Y 61..69); the body sleeves sit on them at X -120 and -45
BAY_RUN = dict(y=76.0, z=122.0)               # cables run along the left bay above the mated plugs (tops Z 117.7, ends Y 72); the T101 rib is at Y 61-69
WIRE_R = 0.45                                 # a bare 28 AWG wire (the plug tails: the two wires lie side by side along X, one wire deep in Y)
TOOLBOX_HOLE = (38.0, -122.0)                 # Ø12 in the deck (x1_body.py), Z 132-137
LAMP2 = (58.5, -100.0, 143.0)                 # toolbox lamp (B103 front face)
SM_LAMP = (-12.0, -128.0, 117.0)              # the lamp cable's JST SM joint, in the right bay under the deck, axis X (board side at -X); 10 mm outboard of the feed and the 12 V link
ROOF_LAMPS = [(75.0, 146.0, 255.1), (75.0, 138.0, 255.1)]
SWITCH, FUSE, JACK = (34.5, -104.5, 146.0), (30.0, -109.0, 142.5), (41.0, -141.0, 150.0)   # KCD1-101 terminals, MINI FHM lead end, jack lugs
HATCH_LEAD_END = (-110.0, -42.8, 199.0)       # where the BMS lead leaves the hatch (B106)
FEED_SOCKET = (-100.0, -42.0, 166.0)          # the mated XT30 pair of the feed (x1_body.FEED_SOCKET): male mouth plane, axis Z
FEED_PLUG_F_END = (FEED_SOCKET[0], FEED_SOCKET[1], FEED_SOCKET[2] + 12.4 + 4.0)   # the XT30U-F's wire stubs (hatch lead) end here
FEED_PLUG_M_END = (FEED_SOCKET[0], FEED_SOCKET[1], FEED_SOCKET[2] - 13.7 - 4.0)   # the XT30U-M's wire stubs (feed) end here
WINDOW = (-143.0, 0.0, 122.2)                 # T101 rear bulkhead Ø20 window (swing motor leads)
CW_CHANNEL = dict(x=-155.0, z=(122.0, 148.0)) # counterweight lead channel, |Y| < 12
NOTCH = (-143.5, 0.0, 150.0)                  # cable notch over the rear bulkhead in the halves' rear walls, |Y| < 14, Z to 154
SLIP_SLOT = (-33.0, 0.0, 124.0)               # T101 lead slot through the rear hub-well wall (x -35..-29, |Y| < 5)
ROTOR_TOP = (0.0, 0.0, 88.0)

# rib crossings (X positions between the hood front wall at X -25 and the front body sleeve at X -50..-40; the slip
# ring, link and lamp 2 cross further back, between the two sleeves)
X_ARM_L, X_ARM_R = -36.0, -32.0
X_SLIP, X_LINK, X_LAMP2, X_SWING, X_FEED = -62.0, -58.0, -56.0, -131.0, -100.0


def cross_rib(x, side=1, z_top=141.0):
    """Points of a cable going over a T101 rib top (Y 61-69, Z 136) from the hood cavity into a bay (side +1 left):
    level over the rib, 5 mm past its outer face, then down to the bay run."""
    return [(x, side * 52.0, z_top), (x, side * 60.0, z_top), (x, side * 74.0, z_top), (x, side * 77.0, 124.0)]


RISE_X = -24.5                     # the cables rise out of T101 here, in the gap between the plate's rear edge (-21) and the rear bulkhead (-30), and
                                   # up through the notch cut in the hood's inboard front wall (X -25..-23, |Y| 38-56, Z 136.3-156; x1_body.py common_cuts)
NOTCH_Y = (38.0, 56.0)
NOTCH_Z_TOP = 156.0


def under_plate(side, y_in, y_run, x_cross, z_cross, conn):
    """Vehicle points of an arm cable from the slot top (vehicle X 4, plate top Z 146) down into T101's middle compartment,
    rearward on its floor, up through the rise gap, (right side: across over the hub well), over the left rib at x_cross
    into the bay and to conn. y_in: where it enters the slot; y_run: its lane in the gap (cables side by side)."""
    X = SLOTS['S3'][0] + K.O_X
    pts = [(X, side * y_in, K.T101_TOP_Z + K.BASE_T), (X - 2.0, side * y_in, 128.0), (-8.0, side * y_run, 114.0),
           (RISE_X, side * y_run, 118.0), (RISE_X, side * y_run, 143.0), (-29.0, side * y_run, 149.0), (x_cross - 2.0, side * y_run, z_cross + 4.0)]
    if side < 0:
        pts += [(x_cross, -36.0, z_cross + 2.0), (x_cross, 0.0, z_cross + 3.0), (x_cross, 36.0, z_cross + 2.0)]
    pts += cross_rib(x_cross, 1, z_cross)
    c = BOARD[conn]
    pts += [(c['x'] + 4.0, BAY_RUN['y'], BAY_RUN['z'])] + c['approach']
    return pts


# ------------------------------------------------------------------ static cables (fixed to the upper or lower)
def static_cables():
    out = []
    # slip ring rotor leads: up the T104 hole and the hub well, out of the T101 lead slot, over the rib to J102
    pts = [ROTOR_TOP, (0, 0, 118.0), (-20.0, 0.0, 122.0), SLIP_SLOT, (-40.0, 0.0, 130.0), (-46.0, 12.0, 140.0),
           (X_SLIP, 44.0, 142.0)] + cross_rib(X_SLIP, 1, 141.0) + [(BOARD['J102']['x'] - 4.0, BAY_RUN['y'], BAY_RUN['z'])] + BOARD['J102']['approach']
    out.append(dict(name='slip ring rotor leads', mover='upper', r=BUNDLE_R, pts=pts, to='J102',
                    wire='6 leads of the bought ring (4 used: rings 1-2 left track, 3-4 right track)', kind='lead'))
    # swing motor: can end -> window -> counterweight channel -> over the bulkhead through the notch -> rib -> J103
    pts = [(-137.4, 0.0, 122.2), WINDOW, (CW_CHANNEL['x'], 0.0, CW_CHANNEL['z'][0]), (CW_CHANNEL['x'], 0.0, CW_CHANNEL['z'][1]),
           NOTCH, (-138.0, 0.0, 150.0), (-134.0, 30.0, 147.0)] + cross_rib(X_SWING, 1, 142.0) + \
          [(BOARD['J103']['x'] - 4.0, BAY_RUN['y'], BAY_RUN['z'])] + BOARD['J103']['approach']
    out.append(dict(name='swing motor leads', mover='upper', r=LEAD_R, pts=pts, to='J103', wire='2 x 26 AWG silicone', kind='lead'))
    # 12 V link: J101 (front edge, mates from +X) -> up and over the left rib -> across the hood -> right rib -> right bay
    # -> toolbox (switch). 150 mm of slack is coiled in the right bay (BODY.md).
    pts = [BOARD['J101']['end'], (-14.0, 133.5, 116.0), (-14.0, 128.0, 124.0), (-22.0, 95.0, 126.0), (-40.0, 80.0, 128.0),
           (X_LINK, 72.0, 134.0)] + cross_rib(X_LINK, 1, 143.0)[::-1][1:] + [(X_LINK, 0.0, 146.0)] + cross_rib(X_LINK, -1, 143.0) + \
          [(X_LINK, -100.0, 118.0), (10.0, -116.0, 116.0), (TOOLBOX_HOLE[0], TOOLBOX_HOLE[1], 118.0),
           (TOOLBOX_HOLE[0], TOOLBOX_HOLE[1], 140.0), SWITCH]
    out.append(dict(name='12 V link (switch to board)', mover='upper', r=POWER_R, pts=pts, to='J101', wire='2 x 20 AWG silicone, XT30 pair', kind='power'))
    # battery feed: toolbox (fuse) -> right bay -> over the right rib between the sleeves -> socket near the hatch
    pts = [FUSE, (TOOLBOX_HOLE[0], TOOLBOX_HOLE[1], 140.0), (TOOLBOX_HOLE[0], TOOLBOX_HOLE[1], 118.0), (0.0, -118.0, 116.0),
           (-60.0, -100.0, 118.0), (X_FEED, -82.0, 124.0)] + cross_rib(X_FEED, -1, 142.0)[::-1][1:] + [(X_FEED, -44.0, 142.0), FEED_PLUG_M_END]
    out.append(dict(name='battery feed (fuse to hatch socket)', mover='upper', r=POWER_R, pts=pts, to='XT30 socket', wire='2 x 20 AWG silicone', kind='power'))
    out.append(dict(name='battery hatch lead', mover='upper', r=POWER_R, pts=[HATCH_LEAD_END, (-104.0, -42.3, 192.0), FEED_PLUG_F_END],
                    to='XT30 plug', wire='the hatch BMS lead, 150 mm (BODY.md)', kind='power'))
    # lamp 2 (toolbox): J108 -> bay -> rib -> across -> right rib -> right bay -> toolbox -> lamp
    pts = [LAMP2, (50.0, -104.0, 143.0), (TOOLBOX_HOLE[0], TOOLBOX_HOLE[1] + 2, 140.0), (TOOLBOX_HOLE[0], TOOLBOX_HOLE[1] + 2, 118.0),
           (10.0, -118.0, 117.0), (SM_LAMP[0] + 14.0, SM_LAMP[1], SM_LAMP[2]), SM_LAMP, (SM_LAMP[0] - 22.0, SM_LAMP[1], SM_LAMP[2]),
           (-48.0, -112.0, 118.0), (X_LAMP2, -100.0, 118.0)] + cross_rib(X_LAMP2, -1, 141.0)[::-1] + [(X_LAMP2, 0.0, 144.0)] + \
          cross_rib(X_LAMP2, 1, 141.0)[1:] + [(BOARD['J108']['x'] + 4.0, BAY_RUN['y'], BAY_RUN['z'])] + BOARD['J108']['approach']
    out.append(dict(name='toolbox lamp pair', mover='upper', r=LEAD_R, pts=pts, to='J108', pins='1, 3', wire='2 x 26 AWG silicone; JST SM 2-pin inline in the right bay', kind='lead'))
    # lamp 1 (roof pair): J108 -> forward along the bay -> cab rear-left corner -> inside the cab shell to the roof
    pts = [ROOF_LAMPS[1], (74.0, 142.0, 251.0), ROOF_LAMPS[0], (74.0, 146.0, 251.0), (72.0, 150.6, 248.5), (-3.0, 150.6, 248.5),
           (-3.0, 150.6, 150.0), (-8.0, 150.0, 142.0), (-14.0, 140.0, 138.0), (-40.0, 90.0, 124.0),
           (BOARD['J108']['x'] + 4.0, BAY_RUN['y'], BAY_RUN['z'])] + BOARD['J108']['approach']
    out.append(dict(name='roof lamps pair', mover='upper', r=THIN_R, pts=pts, to='J108', pins='1, 2', wire='2 x 0.2 mm enamelled wire, in the cab roof corner', kind='lead'))
    # lower: track motor leads from each pod nose port forward beside the front arm, into the carbody side hole, to the
    # inline plug that meets the slip-ring stator leads (X1/source/x1_parts.py cable_route)
    for side, lab in ((1, 'left'), (-1, 'right')):
        y_port = side * 127.0
        pts = [(-34.0, y_port, 44.3), (34.0, y_port, 44.3), (34.0, side * 96.0, 44.3), (0.0, side * 66.0, 46.0), (0.0, side * 50.0, 46.0),
               (0.0, side * 30.0, 52.0)]
        out.append(dict(name=f'{lab} track motor leads', mover='ground', r=LEAD_R, pts=pts, to='JST SM 2-pin in the carbody',
                        wire='2 x 26 AWG silicone, 100 nF across the motor', kind='lead'))
    pts = [(0.0, 0.0, 60.0), (0.0, 0.0, 54.0), (0.0, 30.0, 52.0)]
    out.append(dict(name='slip ring stator leads', mover='ground', r=BUNDLE_R, pts=pts, to='2 x JST SM 2-pin', wire='6 leads of the bought ring', kind='lead'))
    pts = [(0.0, 0.0, 60.0), (0.0, 0.0, 54.0), (0.0, -30.0, 52.0)]
    out.append(dict(name='slip ring stator leads (right pair)', mover='ground', r=BUNDLE_R, pts=pts, to='JST SM 2-pin', wire='rings 3-4', kind='lead'))
    # the boom-drive sleeves in their troughs (from the rearmost point a drop can reach to the slot), then every arm cable
    # from its slot down into T101's middle compartment, rearward, up through the rise gap (the right pair crosses over
    # the hub well), over the left rib and into the bay
    for side, cable, conn, x_cross, z_cross, y_run in ((1, 'boom_L', 'J104', X_ARM_L, 142.0, 43.0), (-1, 'boom_R', 'J105', X_ARM_R, 142.0, 43.0)):
        path = TROUGH['path']
        pts = [(25.0 + K.O_X, side * path[0][1], TROUGH_Z + K.O_Z)] + [(x + K.O_X, side * y, TROUGH_Z + K.O_Z) for x, y in path[1:]]
        pts += under_plate(side, path[-1][1], y_run, x_cross, z_cross, conn)[1:]
        pts[len(path):len(path)] = [(SLOTS['S3'][0] + 1.0 + K.O_X, side * (path[-1][1] + 0.5), K.T101_TOP_Z + K.BASE_T - 6.0)]
        out.append(dict(name=f'{conn} cable in the trough and under the plate', mover='upper', r=TUBE_R, pts=pts, to=conn,
                        wire='V6 cable (3 mm sleeve)', kind='sleeve', slot=cable))
    for side, cable, conn, x_cross, z_cross, y_run in ((1, 'stick', 'J106', X_ARM_L, 146.5, 50.0), (-1, 'bucket', 'J107', X_ARM_R, 146.5, 50.0)):
        pts = under_plate(side, POST['y'] + 1.0, y_run, x_cross, z_cross, conn)
        out.append(dict(name=f'{conn} cable under the plate', mover='upper', r=TUBE_R, pts=pts, to=conn,
                        wire='V6 cable (3 mm sleeve)', kind='sleeve', slot=cable))
    # board-bound cables: the last 25 mm into each plug are bare wires (WIRE_R); split them off as 'plug tail' entries
    split = []
    for c in out:
        if c['to'] in BOARD and c['mover'] == 'upper' and c['to'] != 'J101':
            ap = BOARD[c['to']]['approach']
            k = c['pts'].index(ap[0]) if ap[0] in c['pts'] else None
            if k is not None:
                head, tail = c['pts'][:k + 1], c['pts'][k:]
                split.append(dict(c, name=c['name'] + ' (plug tail)', pts=tail, r=WIRE_R, kind='tail', parent=c['name']))
                c['pts'] = head
    out += split
    return out


# ------------------------------------------------------------------ arm cables
def boom_top(x):
    """z of the boom's top edge at boom-frame x (the traced Cat 320 profile)."""
    g = LineString([(x, -500), (x, 500)]).intersection(d.boom_profile())
    return float(g.bounds[3])


def stick_top(x):
    g = LineString([(x, -500), (x, 500)]).intersection(d.stick_base())
    return float(g.bounds[3])


LANE_DROP = 8.0                      # cable centre this far below the boom's top edge, on the side face
BOOM_Y = d.WIDTH['boom'] / 2 + TUBE_R        # 21.75: on the side face |Y| 20
STICK_Y = d.WIDTH['stick'] / 2 + TUBE_R      # 17.75: on the stick side face |Y| 16
LANE_X = dict(stick=[215.0, 180.0, 140.0, 95.0, 55.0, 28.0],           # boom left lane: first clamp behind the C bracket (219)
              bucket=[324.0, 285.0, 240.0, 195.0, 150.0, 100.0, 55.0, 28.0])   # boom right lane: from R 56 of E to the root
STICK_ANCHOR = (27.0, 28.0)          # bucket cable's clamp on the stick's right side face (x, z), R 39 from E
LOOP_L = dict(O=92.0, E=110.0)       # cable lengths of the two loops (set from the chord ranges in check_wiring.py)
# exit paths: straight out of the V6 clamp for a, a corner, a via point p2 and the landing point on the host face (frame of the
# host body), rounded with R; tuned in check_wiring.py's search so the free part clears everything by >= 1 mm
EXIT_STICK = dict(a=12.0, p2=(236.0, 9.0, 107.0), land=(227.0, 22.3, 96.0), R=7.5)
EXIT_BUCKET = dict(a=9.0, p2=(19.0, -8.0, 70.0), land=(27.5, -21.0, 54.0), R=6.0)


def lane(name):
    """Boom side-lane clamp points (boom frame) for the stick cable (left) or the bucket cable (right)."""
    s = 1 if name == 'stick' else -1
    return [np.array([x, s * BOOM_Y, boom_top(x) - LANE_DROP]) for x in LANE_X[name]]


def exit_geometry(pins, name):
    """V6 sleeve exit of one drive in the O-frame side view: (clamp face point, outward direction, axis direction).
    The clamp face is 7 mm ahead of the rear pin, 9.8 off-axis on the board side; the sleeve leaves it outward."""
    nm, a, b, yc, board, host = next(dr for dr in DRIVES if dr[0] == name)
    u = pins[b] - pins[a]
    u = u / np.linalg.norm(u)
    n = np.array([-u[1], u[0]])
    out = board * n
    face = pins[a] + 7.0 * u + 9.8 * out
    return face, out, u, yc, host


def post_top(side):
    return np.array([POST['x'], side * POST['y'], POST['top']])


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def arc_fixed_length(p0, p1, L, bulge_dir, n=24):
    """Circular arc of length L from p0 to p1 (L > chord), in the plane of the chord and bulge_dir, bulging that way."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    c = float(np.linalg.norm(p1 - p0))
    if L <= c + 1e-6:
        return np.linspace(p0, p1, n), dict(chord=c, radius=float('inf'), sagitta=0.0, taut=True)
    ratio = c / L
    lo, hi = 1e-6, math.pi - 1e-6            # half angle: sin(a)/a = c/L
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if math.sin(mid) / mid > ratio:
            lo = mid
        else:
            hi = mid
    a = 0.5 * (lo + hi)
    R = L / (2 * a)
    e = unit(p1 - p0)
    b = np.asarray(bulge_dir, float)
    b = b - (b @ e) * e
    b = unit(b)
    m = 0.5 * (p0 + p1)
    centre = m - b * (R * math.cos(a))
    t = np.linspace(-a, a, n)
    pts = np.array([centre + R * (math.cos(ti) * b + math.sin(ti) * e) for ti in t])
    return pts, dict(chord=c, radius=R, sagitta=R * (1 - math.cos(a)), taut=False)


def hermite(p0, t0, p1, t1, scale=None, n=24):
    """Cubic Hermite from p0 (unit tangent t0) to p1 (unit tangent t1); tangent magnitudes = scale x chord."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    c = float(np.linalg.norm(p1 - p0))
    k = (scale if scale is not None else 1.0) * max(c, 1e-6)
    m0, m1 = unit(t0) * k, unit(t1) * k
    s = np.linspace(0, 1, n)[:, None]
    h00, h10, h01, h11 = 2 * s ** 3 - 3 * s ** 2 + 1, s ** 3 - 2 * s ** 2 + s, -2 * s ** 3 + 3 * s ** 2, s ** 3 - s ** 2
    return h00 * p0 + h10 * m0 + h01 * p1 + h11 * m1


def catmull_rom(points, n_per=10):
    """Centripetal Catmull-Rom spline through the points (smooth, no overshoot between close points)."""
    P = [np.asarray(p, float) for p in points]
    if len(P) < 3:
        return np.array(P)
    P = [P[0] + (P[0] - P[1])] + P + [P[-1] + (P[-1] - P[-2])]
    out = [P[1]]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        def tj(ti, pi, pj):
            return ti + math.sqrt(max(np.linalg.norm(pj - pi), 1e-9))
        t0 = 0.0
        t1, t2, t3 = tj(t0, p0, p1), None, None
        t2 = tj(t1, p1, p2)
        t3 = tj(t2, p2, p3)
        for k in range(1, n_per + 1):
            t = t1 + (t2 - t1) * k / n_per
            A1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
            A2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
            A3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
            B1 = (t2 - t) / (t2 - t0) * A1 + (t - t0) / (t2 - t0) * A2
            B2 = (t3 - t) / (t3 - t1) * A2 + (t - t1) / (t3 - t1) * A3
            out.append((t2 - t) / (t2 - t1) * B1 + (t - t1) / (t2 - t1) * B2)
    return np.array(out)


MIN_BEND_R_DROP = 7.5             # the second bend of a boom-drive sleeve at full boom-down (8 mm of height into the trough)


def arc_pts(p, a0, turn, R, n):
    """Points of a circular arc in the XZ plane starting at p heading a0, turning by `turn` on radius R."""
    side = -1.0 if turn < 0 else 1.0
    cx = p[0] + R * math.cos(a0 + side * math.pi / 2)
    cz = p[2] + R * math.sin(a0 + side * math.pi / 2)
    return [np.array([cx + R * math.cos(a0 + turn * k / n - side * math.pi / 2), p[1], cz + R * math.sin(a0 + turn * k / n - side * math.pi / 2)])
            for k in range(1, n + 1)]


def drop_path(p0, t0, y_trough, R=MIN_BEND_R, n=12):
    """A boom-drive sleeve from its exit p0 (direction t0, O frame): turns on R to vertical, drops, then turns rearward
    (-X) on the largest radius the height allows and runs on in the trough (cable centre TROUGH_Z). The sleeve slides in
    the trough as the boom moves. Returns (points, info)."""
    x0, y, z0 = p0
    a0 = math.atan2(t0[2], t0[0])
    turn = (-math.pi / 2 - a0 + math.pi) % (2 * math.pi) - math.pi
    pts = [np.array([x0, y, z0])]
    if abs(turn) > math.radians(3.0):        # a smaller turn is taken as straight (the sleeve is already vertical)
        pts += arc_pts(pts[-1], a0, turn, R, n)
    p = pts[-1]
    h = float(p[2] - TROUGH_Z)                                      # height left for the second bend
    R2 = min(R, h)
    ok = R2 >= MIN_BEND_R_DROP
    if h > R2 + 1e-6:
        pts.append(np.array([p[0], p[1], TROUGH_Z + R2]))
    p = pts[-1]
    pts += arc_pts(p, -math.pi / 2, -math.pi / 2, R2, n)            # down -> rearward (-X): a clockwise quarter turn
    # the sleeve eases outboard to the trough's centreline over the whole drop (a smooth-step in Y along the arc length)
    pts = np.array(pts)
    cum = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    u = cum / max(cum[-1], 1e-9)
    pts[:, 1] = y + (y_trough - y) * (3 * u ** 2 - 2 * u ** 3)
    pts = [q for q in pts]
    end = pts[-1]
    info = dict(second_bend_radius=round(R2, 2), trough_entry_x=round(float(end[0]), 2), turn_deg=round(math.degrees(turn), 1),
                arc1_end_above_plate_mm=round(float(pts[n][2] - PLATE_TOP), 2) if abs(turn) > math.radians(3.0) else round(z0 - PLATE_TOP, 2),
                inside_trough=bool(TROUGH['mouth_to_x'] + 1 <= end[0] <= TROUGH['path'][0][0] - TUBE_R), ok=bool(ok))
    return np.array(pts), info


def length(pts):
    pts = np.asarray(pts, float)
    return float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())


def min_radius(pts):
    """Smallest radius of curvature of a sampled curve (three-point circles)."""
    pts = np.asarray(pts, float)
    best = float('inf')
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        ab, bc, ca = np.linalg.norm(b - a), np.linalg.norm(c - b), np.linalg.norm(a - c)
        if ab < 0.25 or bc < 0.25:           # sub-sample noise, not a bend
            continue
        area2 = np.linalg.norm(np.cross(b - a, c - a))
        if area2 < 1e-9:
            continue
        best = min(best, ab * bc * ca / (2 * area2))
    return best


def round_corners(pts, r=6.0, n=6):
    """Polyline with its interior corners replaced by arcs of radius r (clipped to the shorter neighbour)."""
    pts = [np.asarray(p, float) for p in pts]
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        u0, u1 = unit(a - b), unit(c - b)
        cosang = float(np.clip(u0 @ u1, -1, 1))
        ang = math.acos(cosang)
        if ang > math.pi - 1e-3 or ang < 1e-3:
            out.append(b)
            continue
        half = (math.pi - ang) / 2
        tdist = min(r / math.tan(ang / 2), 0.45 * np.linalg.norm(a - b), 0.45 * np.linalg.norm(c - b))
        rr = tdist * math.tan(ang / 2)
        p_in, p_out = b + u0 * tdist, b + u1 * tdist
        bis = unit(u0 + u1)
        centre = b + bis * (rr / math.sin(ang / 2))
        v0, v1 = p_in - centre, p_out - centre
        for k in range(n + 1):
            s = k / n
            # slerp between v0 and v1
            w = unit(v0 * (1 - s) + v1 * s) * rr
            out.append(centre + w)
    out.append(pts[-1])
    return np.array(out)


def tube(pts, r, n=10):
    """Tube mesh (vertices, triangles) around a polyline, with closed ends."""
    pts = np.asarray(pts, float)
    keep = [0] + [i for i in range(1, len(pts)) if np.linalg.norm(pts[i] - pts[i - 1]) > 1e-6]
    pts = pts[keep]
    tang = np.gradient(pts, axis=0)
    tang = np.array([unit(t) for t in tang])
    # parallel transport frame
    ref = np.array([0, 0, 1.0]) if abs(tang[0] @ [0, 0, 1]) < 0.9 else np.array([1.0, 0, 0])
    nrm = unit(np.cross(tang[0], ref))
    V = []
    for i, (p, t) in enumerate(zip(pts, tang)):
        if i:
            nrm = nrm - (nrm @ t) * t
            nrm = unit(nrm)
        bin_ = np.cross(t, nrm)
        for k in range(n):
            a = 2 * math.pi * k / n
            V.append(p + r * (math.cos(a) * nrm + math.sin(a) * bin_))
    V = np.array(V)
    T = []
    m = len(pts)
    for i in range(m - 1):
        for k in range(n):
            a, b = i * n + k, i * n + (k + 1) % n
            c, dd = a + n, b + n
            T += [[a, b, c], [b, dd, c]]
    V = np.vstack([V, pts[0], pts[-1]])
    s, e = len(V) - 2, len(V) - 1
    for k in range(n):
        T.append([s, (k + 1) % n, k])
        T.append([e, (m - 1) * n + k, (m - 1) * n + (k + 1) % n])
    return V, np.array(T, np.int64)


# ------------------------------------------------------------------ the arm harness at one pose
def arm_cables(sol, pins):
    """Cables on the arm for one R12 solution (r12_design.solve): list of dict(name, cable, part, pts (3D, in the frame
    'frame'), r, kind) with kind 'fixed' (on one body), 'loop' (fixed length between two bodies), 'drop' (slides
    through a slot), 'exit' (from the V6 clamp face to the first W01 clamp). Frames: body names; 'base' = O frame."""
    po = sol['poses']
    th = po['boom'][1]
    e_pt, st_ang = po['stick']
    out = []

    def w_boom(p):     # boom frame -> O frame (3D)
        p = np.asarray(p, float)
        c, s = math.cos(th), math.sin(th)
        return np.array([p[0] * c - p[2] * s, p[1], p[0] * s + p[2] * c])

    def w_stick(p):
        p = np.asarray(p, float)
        c, s = math.cos(st_ang), math.sin(st_ang)
        return np.array([e_pt[0] + p[0] * c - p[2] * s, p[1], e_pt[1] + p[0] * s + p[2] * c])

    # --- stick drive cable: exit (boom frame, moves with the stick) -> clamp 1 on the left lane -> lane -> O loop -> post -> slot S3
    face, outd, u, yc, host = exit_geometry(pins, 'stick')
    # into the boom frame
    c, s = math.cos(th), math.sin(th)
    rot = np.array([[c, s], [-s, c]])                       # world -> boom (2D)
    fb, ob, ub = rot @ (face - np.zeros(2)), rot @ outd, rot @ u
    face3 = np.array([fb[0], yc, fb[1]])
    stub = face3 + 2.0 * np.array([ob[0], 0.0, ob[1]])     # the sleeve leaves the clamp face straight, then bends on R >= 9
    L_st = lane('stick')
    o3 = np.array([ob[0], 0.0, ob[1]])
    land = np.array(EXIT_STICK['land'])
    free = round_corners([face3, face3 + EXIT_STICK['a'] * o3, np.array(EXIT_STICK['p2']), land], EXIT_STICK['R'])
    out.append(dict(name='stick exit', cable='stick', frame='boom', pts=free, r=TUBE_R, kind='exit'))
    out.append(dict(name='stick exit landing', cable='stick', frame='boom', pts=round_corners([land, L_st[0] + np.array([12.0, 0.3, 2.0]), L_st[0]], EXIT_STICK['R']),
                    r=TUBE_R, kind='landing'))
    out.append(dict(name='stick lane (boom left side)', cable='stick', frame='boom', pts=round_corners(L_st, 10.0), r=TUBE_R, kind='fixed'))
    # O loop, left: from the last lane clamp (boom) to the post top (base), bulging away from pin A
    pO0, pO1 = w_boom(L_st[-1]), post_top(1)
    mid = 0.5 * (pO0 + pO1)
    away = mid - np.array([d.A_W[0], 0.0, d.A_W[1]])
    arcO, infoO = arc_fixed_length(pO0, pO1, LOOP_L['O'], away)
    out.append(dict(name='stick loop at O', cable='stick', frame='base', pts=arcO, r=TUBE_R, kind='loop', info=infoO, bodies=('boom', 'base')))
    out.append(dict(name='stick post to slot S3', cable='stick', frame='base',
                    pts=round_corners([post_top(1), np.array([POST['x'] + 1.0, POST['y'] + 1.0, -40.0]), np.array([SLOTS['S3'][0] - 1.0, POST['y'] + 1.0, PLATE_TOP])], 5.0),
                    r=TUBE_R, kind='fixed'))

    # --- bucket drive cable: exit (stick frame) -> over the stick's right edge -> stick clamp -> E loop -> boom right lane -> O loop -> post -> S4
    face, outd, u, yc, host = exit_geometry(pins, 'bucket')
    c2, s2 = math.cos(st_ang), math.sin(st_ang)
    rot2 = np.array([[c2, s2], [-s2, c2]])
    fs, os_ = rot2 @ (face - e_pt), rot2 @ outd
    face3 = np.array([fs[0], yc, fs[1]])
    stub = face3 + 2.0 * np.array([os_[0], 0.0, os_[1]])
    anc = np.array([STICK_ANCHOR[0], -STICK_Y, STICK_ANCHOR[1]])
    o3 = np.array([os_[0], 0.0, os_[1]])
    land = np.array(EXIT_BUCKET['land'])
    free = round_corners([face3, face3 + EXIT_BUCKET['a'] * o3, np.array(EXIT_BUCKET['p2']), land], EXIT_BUCKET['R'])
    out.append(dict(name='bucket exit', cable='bucket', frame='stick', pts=free, r=TUBE_R, kind='exit'))
    out.append(dict(name='bucket exit landing', cable='bucket', frame='stick', pts=round_corners([land, anc + np.array([0.5, -0.6, 12.0]), anc], EXIT_BUCKET['R']),
                    r=TUBE_R, kind='landing'))
    L_bk = lane('bucket')
    pE0, pE1 = w_stick(anc), w_boom(L_bk[0])
    D = w_stick(np.array([d.D_S[0], 0.0, d.D_S[1]]))
    mid = 0.5 * (pE0 + pE1)
    arcE, infoE = arc_fixed_length(pE0, pE1, LOOP_L['E'], mid - D)
    out.append(dict(name='bucket loop at E', cable='bucket', frame='base', pts=arcE, r=TUBE_R, kind='loop', info=infoE, bodies=('stick', 'boom')))
    out.append(dict(name='bucket lane (boom right side)', cable='bucket', frame='boom', pts=round_corners(L_bk, 10.0), r=TUBE_R, kind='fixed'))
    pO0, pO1 = w_boom(L_bk[-1]), post_top(-1)
    mid = 0.5 * (pO0 + pO1)
    away = mid - np.array([d.A_W[0], 0.0, d.A_W[1]])
    arcO2, infoO2 = arc_fixed_length(pO0, pO1, LOOP_L['O'], away)
    out.append(dict(name='bucket loop at O', cable='bucket', frame='base', pts=arcO2, r=TUBE_R, kind='loop', info=infoO2, bodies=('boom', 'base')))
    out.append(dict(name='bucket post to slot S4', cable='bucket', frame='base',
                    pts=round_corners([post_top(-1), np.array([POST['x'] + 1.0, -POST['y'] - 1.0, -40.0]), np.array([SLOTS['S4'][0] - 1.0, -POST['y'] - 1.0, PLATE_TOP])], 5.0),
                    r=TUBE_R, kind='fixed'))

    # --- boom drives: exit (base frame, the barrel pivots on A) -> down through S1 / S2
    for name, slot, side_y in (('boom_L', 'S3', 1), ('boom_R', 'S4', -1)):
        face, outd, u, yc, host = exit_geometry(pins, name)
        p0 = np.array([face[0], yc, face[1]])
        t0 = np.array([outd[0], 0.0, outd[1]])
        # the sleeve turns to vertical, drops into the trough and turns rearward in it; it slides in the trough as the boom
        # moves (tied where the trough meets the slot, 30 mm further on)
        pts, info = drop_path(p0, t0, side_y * TROUGH['y_land'])
        out.append(dict(name=f'{name} drop', cable=name, frame='base', pts=pts, r=TUBE_R, kind='drop', slot=slot, info=info))
    return out


def clamps(sol):
    """W01 clamp frames: list of dict(frame, p (cable centre), t (cable direction), nrm (surface normal, out of the face))."""
    out = []
    for nm, y_sign in (('stick', 1), ('bucket', -1)):
        pts = lane(nm)
        for i, p in enumerate(pts):
            q = pts[min(i + 1, len(pts) - 1)] if i + 1 < len(pts) else pts[i - 1]
            t = unit(q - p) if i + 1 < len(pts) else unit(p - q)
            out.append(dict(frame='boom', p=p, t=t, nrm=np.array([0.0, y_sign, 0.0]), cable=nm))
    anc = np.array([STICK_ANCHOR[0], -STICK_Y, STICK_ANCHOR[1]])
    out.append(dict(frame='stick', p=anc, t=np.array([1.0, 0.0, 0.0]), nrm=np.array([0.0, -1.0, 0.0]), cable='bucket'))
    return out


# ------------------------------------------------------------------ wire list
def wire_list(lengths_mm):
    """Rows for harness.csv: cable, from, to, pins, wire, nominal routed length, service slack, cut length."""
    rows = []
    def add(cable, frm, to, pins, wire, routed, slack, note=''):
        rows.append(dict(cable=cable, from_=frm, to=to, pins=pins, wire=wire, routed_mm=round(routed), slack_mm=slack,
                         cut_mm=int(math.ceil((routed + slack) / 10.0) * 10), note=note))
    V6 = 'V6 cable: 2 x 28 AWG PTFE in a 3 mm silicone sleeve (W1 red = A, W2 black = B)'
    add('boom drive L', 'V6 boom L rear cap', 'J104 (XH 2-pin)', '1 OUT1 = A red (extend), 2 OUT2 = B black', V6, lengths_mm['boom_L'], 150,
        'lands in the left trough on the B01X plate, slides in it (up to 20 mm) as the boom moves; tied at the two tie-slot pairs; down slot S3')
    add('boom drive R', 'V6 boom R rear cap', 'J105 (XH 2-pin)', '1 OUT1 = A red, 2 OUT2 = B black', V6, lengths_mm['boom_R'], 150, 'right trough, slot S4')
    add('stick drive', 'V6 stick rear cap', 'J106 (XH 2-pin)', '1 OUT1 = A red (extend = crowd), 2 OUT2 = B black', V6, lengths_mm['stick'], 150,
        'W01 clamps on the boom left side; %g mm loop round O to the left post; slot S3' % LOOP_L['O'])
    add('bucket drive', 'V6 bucket rear cap', 'J107 (XH 2-pin)', '1 OUT1 = A red (extend = curl), 2 OUT2 = B black', V6, lengths_mm['bucket'], 150,
        'W01 clamp on the stick right side; %g mm loop round E; W01 clamps on the boom right side; %g mm loop round O; slot S4' % (LOOP_L['E'], LOOP_L['O']))
    add('swing motor', 'JGY-370 swing motor tabs', 'J103 (XH 2-pin)', '1 OUT1 = motor +, 2 OUT2 = motor -', '2 x 26 AWG silicone + 100 nF 50 V across the tabs',
        lengths_mm['swing motor leads'], 100, 'through the T101 rear window and the counterweight channel; direction set on the bench (flip 3 if needed)')
    add('slip ring rotor', 'slip ring rotor (6 leads)', 'J102 (XH 4-pin)', '1 ring 1 = L motor +, 2 ring 2 = L motor -, 3 ring 3 = R motor +, 4 ring 4 = R motor -; rings 5-6 spare, taped',
        'the ring\'s own leads (~0.75 mm); extend with 26 AWG if shorter than the cut length', lengths_mm['slip ring rotor leads'], 100, 'up the T104 hole, out of the T101 lead slot')
    for lab in ('left', 'right'):
        add(f'{lab} track motor', f'{lab} JGY-370 tabs (pod)', 'JST SM 2-pin in the carbody', 'motor + / motor - (the right motor is NOT reversed in the wiring: the firmware inverts channel 2)',
            '2 x 26 AWG silicone + 100 nF 50 V across the tabs', lengths_mm[f'{lab} track motor leads'], 60, 'X1 ASSEMBLY.md 3.2: forward beside the front arm, into the carbody side hole')
    add('slip ring stator', 'slip ring stator (6 leads)', '2 x JST SM 2-pin in the carbody', 'rings 1-2 -> left plug, 3-4 -> right plug', 'the ring\'s own leads',
        lengths_mm['slip ring stator leads'] + 40, 40, '')
    add('12 V link', 'main switch (toolbox)', 'J101 (XT30PW-M, front edge)', '+ / -', '2 x 20 AWG silicone, XT30 plug', lengths_mm['12 V link (switch to board)'], 150,
        'the slack lets the left half stand beside the machine (BODY.md)')
    add('battery feed', '5 A fuse (toolbox)', 'XT30 socket near the hatch', '+ / -', '2 x 20 AWG silicone, XT30 socket', lengths_mm['battery feed (fuse to hatch socket)'], 60,
        'the hatch lead (150 mm, BODY.md) plugs into it')
    add('charge jack', '5.5 x 2.1 panel jack', 'fuse / GND (toolbox)', 'tip + to the fuse (battery side of the switch), sleeve -', '2 x 22 AWG', 60, 20, 'inside the toolbox')
    add('toolbox lamp', 'J108 (PH 3-pin) pins 1, 3', 'toolbox lamp LED (B103)', '+5V_LAMP -> 100 R -> LED anode; cathode -> LAMP2_K', '2 x 26 AWG silicone; JST SM 2-pin inline in the right bay',
        lengths_mm['toolbox lamp pair'], 150, 'the inline plug lets the right half come off')
    add('roof lamps', 'J108 (PH 3-pin) pins 1, 2', '2 x roof LED (B102 cab roof)', '+5V_LAMP -> 2 x (100 R + LED) in parallel; cathodes -> LAMP1_K',
        '2 x 0.2 mm enamelled wire in the cab roof corner; 26 AWG from the cab to the board', lengths_mm['roof lamps pair'], 60,
        'through a Ø2 hole drilled in the cab\'s rear wall at (-6, 150, 142)')
    return rows

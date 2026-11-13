"""Pack the complete machine into the offline single-file demonstration ../3D_preview.html.

Data, all read from the subsystem folders (see machine.py):
  meshes      J9 track module (drawn twice, the right one mirrored), chain links, X-frame, RU66, turntable, body,
              electronics, B01X and R12 (per body frame)
  kinematics  R12's three 1D stroke tables (as excavator_arm_r12/source/build_viewer_r12.py, re-verified here)
  dynamics    the R12 MuJoCo dig cycle with 150 g (simulation/payload_150g_trace.json.gz), replayed for the arm
  timeline    the demonstration: travel, dig, swing to 90 deg, dump, swing back, carry, travel back. Travel and swing
              are kinematic (minimum-jerk at the J9 and swing-drive speeds); the arm is the MuJoCo trace at 20 x
  checks      ../integration_check.json and the subsystem reports
  wiring      harness.py: the fixed cables as tubes (static on the upper / lower, lanes on the boom and stick, W01 clamps) and the
              anchors, lengths and exit rules of the moving ones (loops at O and E, the V6 exits, the boom-drive drops), which the
              page rebuilds every frame with the same geometry rules
Run with the R12 interpreter from this folder.
"""
import sys
import json
import base64
import numpy as np
import common as K
import machine as M
import harness as H
import connectors as Cn

sys.path.insert(0, str(K.R12 / 'source'))
import r12_design as d               # noqa: E402
import motion_r12 as Mo              # noqa: E402
import build_viewer_r12 as BV        # noqa: E402


def pack_mesh(v, t):
    v = np.asarray(v, np.float32).reshape(-1, 3)
    t = np.asarray(t).reshape(-1, 3)
    wide = len(v) >= 65536
    return dict(wide=wide, v=base64.b64encode(v.astype('<f4').tobytes()).decode(),
                t=base64.b64encode(t.astype('<u4' if wide else '<u2').tobytes()).decode())


# ------------------------------------------------------------------ assembly steps and exploded offsets
# ------------------------------------------------------------------ the installation sequence (ASSEMBLY.md section 2)
# id (used by connectors.py and the wiring tables), title, caption, camera (position, target), see-through body
def _st(id_, title, caption, cam, xray=False, grp=None):
    """grp: the sub-assembly the step works on; the page offsets the camera by that group's bench position while it is not yet fitted."""
    return dict(id=id_, title=title, caption=caption, cam=dict(pos=cam[0], target=cam[1]), xray=xray, grp=grp)


STEPS = [
    _st('tracks', 'Tracks', 'Two J9 tracks, built on the bench: rollers on their axles (two 624ZZ bearings each), the sprocket on a Ø32 flange coupling on the JGY-370 motor shaft, the '
        'idler on two 608ZZ, the J909 pod housing. The right track uses the mirrored J901 and J909 prints. Solder 100 nF across each motor and lead its two '
        '26 AWG wires out of the pod nose. Hold both at their final 340 mm spacing.', ([1080, 860, 620], [170, 60, 130])),
    _st('xframe', 'X-frame', 'Lower the bare X101 frame vertically (80 mm approach) into the open-top seats in both track main plates. Four joints, each clamped by '
        'two M4 x 25 through plain holes with the washers and nuts outside. Then the rear sprockets and chains, and the belly cover below.', ([760, -700, 520], [0, 0, 60])),
    _st('slewing', 'Slewing ring, slip ring and the track joints', 'Slip ring into the frame collar from below (3 x M3), ring gear X103 onto the frame top (6 x M3 '
        'countersunk from below), then the THK RU66 into the gear bore with 8 x M4 x 30, nuts below. Each track\'s motor leads meet the slip ring\'s stator leads in '
        'a JST SM 2-pin joint beside the ring: SMR-02V-B (pins, on the stator leads) and SMP-02V-BC (sockets, on the motor leads); the plug clicks in along Y.',
        ([330, -250, 330], [0, 0, 70])),
    _st('turntable', 'Turntable', 'Hub adapter T104 and centre frame T101 on the RU66 inner ring (8 x M4 x 20), the rotor leads fed up the T104 hole and out of the T101 '
        'lead slot. The swing motor goes in on the T102 slide; the mesh is set with a paper strip, then the drag pads. Press the body\'s 4 M3 inserts into the rib tops now.',
        ([520, -520, 440], [-20, 0, 120])),
    _st('arm', 'Arm unit with its harness', 'B01X, the boom and both boom drives are built as one unit on the bench (pins A are pressed with the drive eyes in place); '
        'the stick and bucket drives, stick, linkage and bucket follow R12\'s ASSEMBLY.md. The four V6 cables (3 mm sleeves, each ending in a JST XHP-2 housing with two '
        'SXH-001T-P0.6 contacts) are laid in the W01 clamps, the B01X troughs and slots and tied (WIRING.md), then the unit goes down onto the T101 rib tops with the 4 M6 x 40 '
        'bolts, the cables fed into T101 and up through the hood-wall notches.', ([470, -470, 430], [50, 0, 160])),
    _st('counterweight', 'Counterweight', 'Counterweight B101, its steel shot poured in during a print pause, with 2 x M4 x 12 from inside T101; the swing motor leads '
        'run up its channel.', ([-720, -520, 420], [-120, 0, 150])),
    _st('left_parts', 'Left half on the bench', 'B102 with the main board rev B on its 4 bosses (the KiCad model: ESP32-S3-WROOM-1, 7 x DRV8876, the JST S2B/S4B-XH-A and '
        'S3B/S4B-PH-K-S side-entry headers on the inboard edge, the Amass XT30PW-M on the front edge, the USB-C through the slot), the cab interior B104, operator B105, '
        'handrail B107, the two ledge magnets, the roof-lamp wires through the Ø2 hole in the cab\'s rear wall; the toolbox-lamp cable from J108 ends in the lamp joint\'s SMR-02V-B.', ([-260, 560, 440], [-90, 110, 150]), grp='left'),
    _st('plugs', 'Plug the harness into the board', 'With the half standing beside the machine: the six XHP-2 (J103 swing, J104 boom L, J105 boom R, J106 stick, J107 bucket), '
        'the XHP-4 of the slip ring (J102) and the PHR-3 of the lamps (J108) push into their side-entry headers along +Y until the lock clicks (pin 1 at the marked end); the '
        '12 V link\'s Amass XT30U-F pushes onto the XT30PW-M on the front edge along -X. J109 (S4B-PH-K-S, expansion) stays empty. Coil the 150 mm slacks in the bay.',
        ([-30, 20, 250], [-85, 86, 116]), xray=True, grp='left'),
    _st('left', 'Left half onto T101', 'Lower it, slide it 10 mm inward onto its hook under the base plate, 2 x M3 x 12 down the sleeves into the rib inserts. Its lap goes '
        'under the right half\'s skin; the four arm cables pass through the notches as it slides in.', ([-320, 720, 520], [-60, 60, 150])),
    _st('right_parts', 'Right half on the bench: toolbox', 'B103 with the KCD1-101 rocker switch snapped into the 19 x 13 cut-out in the toolbox top, the 5.5 x 2.1 metal '
        'panel jack (DC-022B pattern) through the Ø8 hole in the toolbox front with its lock washer and M8 nut outside, the Littelfuse MINI FHM in-line fuse holder (5 A MINI '
        'fuse) on VHB tape on the toolbox floor, the toolbox lamp, the two ledge magnets; the feed lead with its XT30U-M and the lamp lead with its SMP-02V-BC hanging ready.',
        ([330, -430, 340], [40, -125, 150]), xray=True, grp='right'),
    _st('right', 'Right half onto T101', 'With the half held beside the machine: plug the lamp lead\'s SMP-02V-BC into the SMR-02V-B of the cable from the board (the joint then '
        'lies in the right bay, outboard of the feed and the 12 V link), plug the 12 V link into the switch lead, lay the slack over T101; then the same fixing as the left: lower, slide 10 mm inward, 2 x M3 x 12.',
        ([-320, -720, 520], [-60, -60, 150])),
    _st('pack', 'Battery pack on the hatch', 'Hatch B106 upside down on the bench: press the three Keystone 1043 holders up between the sled walls against the two standoff ribs '
        'until the wall lips snap over their end walls (cell opening down, springs alternating ends for the series chain). Solder the two 20 AWG series links between the PC '
        'pins, B-/B1/B2/B+ to the HX-3S-01 BMS taped to the +Y wall, P-/P+ to the 150 mm lead with its XT30U-F.', ([-60, -230, 350], [-110, 0, 200]), xray=True, grp='hatch'),
    _st('cells', 'Cells', 'Three Samsung INR18650-35E: the - end onto the spring first, then press the + end down past the lips onto the plate contact. Check 12.6 V max, '
        'about 11 V, at the XT30U-F before closing.', ([-60, -230, 350], [-110, 0, 200]), xray=True, grp='hatch'),
    _st('hatch', 'Hatch lead and hatch', 'Plug the hatch lead\'s XT30U-F down onto the feed\'s XT30U-M hanging in the hood cavity, tuck the slack over T101, and set the hatch '
        'on its four magnet pairs with the finger notch at the rear. Then the bring-up of the firmware README: show, zero, each drive at low duty, directions against WIRING.md.',
        ([-360, -320, 540], [-100, 0, 230]), xray=True),
]
SID = {st['id']: i for i, st in enumerate(STEPS)}
# sub-assemblies that are built on the bench and move as one: their parts keep this offset until the group's step
GROUPS = dict(left=dict(step=SID['left'], app=[0, 10, 70], exp=[0, 120, 60]), right=dict(step=SID['right'], app=[0, -10, 70], exp=[0, -120, 60]),
              hatch=dict(step=SID['hatch'], app=[0, 0, 90], exp=[0, 0, 190]))
Z0 = [0, 0, 0]


# ------------------------------------------------------------------ assembly steps and exploded offsets


def step_and_vectors(p):
    """(assembly step index, approach vector, exploded offset, group); vectors in the upper or vehicle frame, mm. The approach is
    the part's own fitting motion within its step; a group (left half, right half, hatch) adds the sub-assembly's motion at the group's step."""
    n, s = p['name'], p['sys']
    LX, RX, HX = GROUPS['left']['exp'], GROUPS['right']['exp'], GROUPS['hatch']['exp']
    if s == 'track':
        return SID['tracks'], Z0, Z0, None                   # the track groups carry these (see the page)
    if s == 'xframe':
        if p.get('group') == 'cover' or n.startswith('cover_screw'):
            return SID['xframe'], [0, 0, -60], [0, 0, -70], None
        return SID['xframe'], [0, 0, 80], Z0, None
    if s == 'slew':
        if n.startswith(('slip_ring', 'collar_insert', 'T106')):
            return SID['slewing'], [0, 0, -70], [0, 0, -80], None
        if n.startswith(('X103', 'ring_gear')):
            return SID['slewing'], [0, 0, 60], [0, 0, 30], None
        return SID['slewing'], [0, 0, 90], [0, 0, 55], None   # RU66 and its seat hardware
    if s == 'turntable':
        if n.startswith(('arm_bolt', 'arm_nut')):
            return SID['arm'], [0, 0, 120], Z0, None
        return SID['turntable'], [0, 0, 90], Z0, None
    if s == 'arm':
        return SID['arm'], Z0, Z0, None                      # the arm mount group carries these
    if s == 'wiring':
        if p['kind'] == 'connector':
            return connector_step(p)
        return SID[p['step']], Z0, Z0, p.get('grp')
    # body and electronics, by name
    if n.startswith('cell_'):
        return SID['cells'], [0, 0, -30], HX, 'hatch'
    if n.startswith('holder_'):
        return SID['pack'], [0, 0, -25], HX, 'hatch'
    if n.startswith('battery_BMS'):
        return SID['pack'], [0, 15, 0], HX, 'hatch'
    if n.startswith('battery_lead_XT30'):
        return SID['hatch'], [0, 0, 18], HX, 'hatch'
    if n.startswith('hatch_magnet'):
        return SID['pack'], [0, 0, -8], HX, 'hatch'
    if n == 'B106_battery_hatch':
        return SID['pack'], Z0, HX, 'hatch'
    if n.startswith(('controller_PCB', 'board_parts')):
        return SID['left_parts'], [0, 0, 30], LX, 'left'
    if n.startswith('board_plugs'):
        return SID['plugs'], [0, -14, 0], LX, 'left'
    if n.startswith(('B104', 'B105', 'B107')):
        return SID['left_parts'], [0, 0, 40], LX, 'left'
    if n == 'B102_left_half':
        return SID['left_parts'], Z0, LX, 'left'
    if n.startswith('ledge_magnet'):
        left = int(n.split('_')[-1]) in (0, 2)
        return (SID['left_parts'], [0, 0, -8], LX, 'left') if left else (SID['right_parts'], [0, 0, -8], RX, 'right')
    if n.startswith('sleeve_screw'):
        left = int(n.split('_')[-1]) < 2
        return (SID['left'], [0, 0, 40], LX, None) if left else (SID['right'], [0, 0, 40], RX, None)
    if n.startswith('rib_insert'):
        return SID['turntable'], [0, 0, 30], Z0, None
    if n.startswith(('main_switch', 'fuse_holder')):
        return SID['right_parts'], [0, 0, 20], RX, 'right'
    if n.startswith('charge_jack'):
        return SID['right_parts'], [-16, 0, 0], RX, 'right'
    if n.startswith('feed_socket'):
        return SID['right_parts'], [0, 0, -10], RX, 'right'
    if n == 'B103_right_half':
        return SID['right_parts'], Z0, RX, 'right'
    part = p.get('part')
    if part == 'counterweight':
        return SID['counterweight'], [-110, 0, 0], [-110, 0, 40], None
    if part == 'left':
        return SID['left_parts'], Z0, LX, 'left'
    if part in ('right', 'fixed'):
        return SID['right_parts'], Z0, RX, 'right'
    if part == 'hatch':
        return SID['pack'], Z0, HX, 'hatch'
    raise ValueError(n)


def connector_step(p):
    """The free connectors of build_connectors.py: the moving side approaches along the joint's mating direction."""
    j = next(x for x in Cn.JOINTS if x['id'] == p['joint'])
    free = ('SMP' in p['name']) or ('XT30U-F' in p['name'])
    app = [-(d * j['travel']) for d in j['mate_dir']] if free else Z0
    if j['id'] == 'J101':
        return SID['plugs'], app, GROUPS['left']['exp'], 'left'
    if j['id'] == 'SM-LAMP':
        return (SID['right'], app, Z0, None) if free else (SID['left_parts'], Z0, GROUPS['left']['exp'], 'left')
    return SID['slewing'], app, Z0, None


def labels():
    """Floating labels of the installation steps: every connector joint and the battery-pack parts, with their model numbers."""
    out = []
    for j in Cn.JOINTS:
        if not j['step'] or j['qty'] == 0:
            continue
        grp = 'left' if j['id'] in ('J101', 'J102', 'J103', 'J104', 'J105', 'J106', 'J107', 'J108') else 'right' if j['id'] in ('SW', 'JACK', 'FUSE') else None
        out.append(dict(step=SID[j['step']], text=f"{j['id']}: {j['fixed']} \u2190 {j['free']}", sub=j['circuit'], pos=list(j['pos']), grp=grp, joint=j['id']))
    sys.path.insert(0, str(K.X1 / 'source'))
    import x1_body as Bd                                       # noqa: E402  positions of the pack parts
    zt = Bd.Z_LEDGE - Bd.SLED['standoff']
    for i, xc in enumerate(Bd.HOLDER['xc']):
        out.append(dict(step=SID['pack'], text='Keystone 1043 holder %d' % (i + 1), sub='snaps between the sled walls', pos=[xc, 0.0, zt - 8.0], grp='hatch', joint='HOLDER'))
        out.append(dict(step=SID['cells'], text='Samsung INR18650-35E', sub='cell %d, + end %s' % (i + 1, '-Y' if i % 2 else '+Y'), pos=[xc, 0.0, zt - 20.0], grp='hatch', joint='CELL'))
    out.append(dict(step=SID['pack'], text='HX-3S-01 3S BMS', sub='on the +Y sled wall, VHB tape', pos=[Bd.BMS['x'], Bd.SLED['y_in'] + 3.0, Bd.BMS['z']], grp='hatch', joint='BMS'))
    return out


def stdparts_markers():
    f = K.ROOT / 'cad' / 'standard_parts.json.gz'
    return K.load_gz(f) if f.exists() else []


# ------------------------------------------------------------------ demonstration timeline
def timeline(trace):
    seg = {s['name']: (s['t0'], s['t1']) for s in Mo.SEGMENTS}
    t_raise, t_dump = seg['raise -> dump'][0], seg['dump -> carry'][0]
    t_end = trace['frames'][-1]['t']
    rows, v, real = [], 0.0, 0.0

    def add(title, kind, rd, rate, caption, **kw):
        nonlocal v, real
        vd = rd / rate
        rows.append(dict(id=len(rows), title=title, kind=kind, v0=round(v, 4), vd=round(vd, 4), real0=round(real, 3), rd=round(rd, 3),
                         rate=rate, caption=caption, **kw))
        v += vd
        real += rd
    X, S = K.TRAVEL_MM, K.SWING_DUMP_DEG
    add('Travel forward', 'travel', K.TRAVEL_TIME_S, 1.0,
        'Both J9 tracks drive forward %.0f mm (JGY-370-1260, 30 rpm: 88-120 mm/s). Kinematic playback of the chain and sprocket; '
        'the ground run stays still on the ground.' % X, x=[0.0, X], sw=0.0, t=0.0)
    add('Dig', 'arm', t_raise, K.ARM_PLAYBACK,
        'The R12 dig cycle from its MuJoCo simulation (150 g in the bucket): reach out, penetrate, crowd the stick, curl the bucket, '
        'raise. Shown at %g x: the leadscrew drives move at most 0.8 mm/s. Soil forces are not modelled.' % K.ARM_PLAYBACK,
        x=X, sw=0.0, t=[0.0, t_raise])
    add('Swing to dump', 'swing', K.SWING_TIME_S, 1.0,
        'The upper turns %.0f deg to the left (cab side) on the RU66, driven by the JGY-370 pinion on the X103 ring gear (4:1). '
        'Minimum-jerk move, peak 42 deg/s (7.5 rpm no-load limit 45 deg/s); kinematic playback, the arm holds the raise pose.' % S,
        x=X, sw=[0.0, S], t=t_raise)
    add('Dump', 'arm', t_dump - t_raise, K.ARM_PLAYBACK,
        'Over the left track: the stick goes out and the bucket opens (MuJoCo trace, %g x).' % K.ARM_PLAYBACK, x=X, sw=S, t=[t_raise, t_dump])
    add('Swing back', 'swing', K.SWING_TIME_S, 1.0, 'Back to the front, holding the dump pose (kinematic).', x=X, sw=[S, 0.0], t=t_dump)
    add('Carry', 'arm', t_end - t_dump, K.ARM_PLAYBACK, 'The arm returns to the carry pose (MuJoCo trace, %g x).' % K.ARM_PLAYBACK,
        x=X, sw=0.0, t=[t_dump, t_end])
    add('Travel back', 'travel', K.TRAVEL_TIME_S, 1.0, 'The tracks reverse to the start (kinematic).', x=[X, 0.0], sw=0.0, t=t_end)
    # payload shown from the end of the curl until the bucket has opened in the dump
    t_curl = seg['curl the bucket -> raise'][0]
    t_open = next(f['t'] for f in trace['frames'] if f['t'] > t_raise and f['s'][3] < 30.0)
    return rows, dict(payload_from=t_curl, payload_to=t_open)


def checks_summary():
    ic = json.loads((K.ROOT / 'integration_check.json').read_text())
    sub = {}
    for key, path in [('J9 track', 'track_wheel_jgy370/J9/validation.json'),
                      ('X1 joints (rev F)', 'track_wheel_jgy370/X1/arc_seat_mount_validation.json'),
                      ('Turntable R3', 'track_wheel_jgy370/X1/turntable_validation.json'),
                      ('Body B1', 'track_wheel_jgy370/X1/body_validation.json'),
                      ('R12 arm', 'excavator_arm_r12/validation_summary.json')]:
        try:
            j = json.loads((K.REPO / path).read_text())
            st = j.get('status') or j.get('overall') or j.get('result')
            if st is None and 'pass' in j:
                st = 'PASS' if j['pass'] else 'FAIL'
        except FileNotFoundError:
            st = 'missing'
        sub[key] = dict(file=path, status=str(st))
    return ic, sub


WIRE_COL = dict(sleeve=(0.78, 0.12, 0.10), lead=(0.16, 0.16, 0.18), bundle=(0.16, 0.16, 0.18), power=(0.95, 0.55, 0.10), lamp=(0.20, 0.60, 0.25))
WSTEP = {'slip ring rotor leads': ('turntable', None), 'swing motor leads': ('counterweight', None), '12 V link (switch to board)': ('right', None),
         'battery feed (fuse to hatch socket)': ('right', None), 'battery hatch lead': ('pack', 'hatch'), 'toolbox lamp pair': ('right', None),
         'roof lamps pair': ('left_parts', 'left'), 'left track motor leads': ('tracks', None), 'right track motor leads': ('tracks', None),
         'slip ring stator leads': ('slewing', None), 'slip ring stator leads (right pair)': ('slewing', None)}   # step id, sub-assembly group


def wire_colour(c):
    n = c['name']
    if 'lamp' in n:
        return WIRE_COL['lamp']
    if c.get('kind') == 'sleeve' or c.get('slot') or 'under the plate' in n or 'trough' in n:
        return WIRE_COL['sleeve']
    if c.get('kind') == 'power':
        return WIRE_COL['power']
    return WIRE_COL['lead']


def wiring_meshes():
    """Fixed cable tubes and W01 clamps for the page, plus the data the page needs to draw the moving cables."""
    import r12_design as d
    import motion_r12 as Mo
    out = []
    for c in H.static_cables():
        pts = H.round_corners(np.asarray(c['pts'], float), 4.0)
        v, t = H.tube(pts, c['r'])
        step, grp = WSTEP.get(c.get('parent', c['name']), ('arm', None))
        if c.get('kind') == 'tail':
            step, grp = 'plugs', 'left'                        # the bare wires into the board plugs go in with the plugs
        out.append(dict(name=c['name'] + (' to ' + c['to'] if c['to'] not in c['name'] else ''), sys='wiring', mover=c['mover'], color=list(wire_colour(c)),
                        kind='cable', step=step, grp=grp, app=[0, 0, 0], exp=[0, 0, 0], group=None, part=None, new=True, **pack_mesh(v, t)))
    sol = d.solve(tuple(Mo.WAYPOINTS[0][1]))
    segs = H.arm_cables(sol, sol['pins'])
    for sg in segs:
        if sg['kind'] not in ('fixed', 'landing'):
            continue
        v, t = H.tube(np.asarray(sg['pts'], float), sg['r'])
        mover = 'arm:' + sg['frame'] if sg['frame'] in ('boom', 'stick') else 'armbase'
        out.append(dict(name=sg['name'] + ' (' + sg['cable'].replace('_', ' ') + ' drive cable)', sys='wiring', mover=mover, color=list(WIRE_COL['sleeve']),
                        kind='cable', step='arm', app=[0, 0, 0], exp=[0, 0, 0], group=None, part=None, new=True, **pack_mesh(v, t)))
    w01 = K.load_gz(K.ROOT / 'cad' / 'W01_mesh.json.gz')
    wv, wt = np.asarray(w01['v'], float).reshape(-1, 3), np.asarray(w01['t']).reshape(-1, 3)
    for i, cl in enumerate(H.clamps(sol)):
        x, z = H.unit(cl['t']), H.unit(cl['nrm'])
        y = np.cross(z, x)
        R = np.stack([x, y, z], axis=1)
        v = wv @ R.T + (np.asarray(cl['p'], float) - z * H.TUBE_R)
        out.append(dict(name=f"W01 cable clamp {i + 1} ({cl['cable']} cable, {cl['frame']})", sys='wiring', mover='arm:' + cl['frame'], color=list(w01['color']),
                        kind='printed', step='arm', app=[0, 0, 0], exp=[0, 0, 0], group=None, part=None, new=True, **pack_mesh(v, wt)))
    # the moving cables: anchors in body frames, lengths and rules (harness.py); the page's geometry twins these
    L_st, L_bk = H.lane('stick'), H.lane('bucket')
    anc = [H.STICK_ANCHOR[0], -H.STICK_Y, H.STICK_ANCHOR[1]]
    A = [float(d.A_W[0]), 0.0, float(d.A_W[1])]
    D = [float(d.D_S[0]), 0.0, float(d.D_S[1])]
    dyn = dict(
        tube_r=H.TUBE_R, plate_top=H.PLATE_TOP, trough_z=H.TROUGH_Z, min_bend_r=H.MIN_BEND_R,
        loops=[dict(name='stick drive cable, loop at O', cable='stick', a=dict(frame='boom', p=L_st[-1].tolist()), b=dict(frame='base', p=H.post_top(1).tolist()),
                    L=H.LOOP_L['O'], away=dict(frame='base', p=A)),
               dict(name='bucket drive cable, loop at E', cable='bucket', a=dict(frame='stick', p=anc), b=dict(frame='boom', p=L_bk[0].tolist()),
                    L=H.LOOP_L['E'], away=dict(frame='stick', p=D)),
               dict(name='bucket drive cable, loop at O', cable='bucket', a=dict(frame='boom', p=L_bk[-1].tolist()), b=dict(frame='base', p=H.post_top(-1).tolist()),
                    L=H.LOOP_L['O'], away=dict(frame='base', p=A))],
        exits=[dict(name='stick drive cable, exit', drive='stick', host='boom', a='C', b='D', yc=0.0, side=+1, stub=H.EXIT_STICK['a'],
                    p2=list(H.EXIT_STICK['p2']), land=list(H.EXIT_STICK['land']), R=H.EXIT_STICK['R']),
               dict(name='bucket drive cable, exit', drive='bucket', host='stick', a='F', b='R', yc=0.0, side=+1, stub=H.EXIT_BUCKET['a'],
                    p2=list(H.EXIT_BUCKET['p2']), land=list(H.EXIT_BUCKET['land']), R=H.EXIT_BUCKET['R'])],
        drops=[dict(name='boom L drive cable, drop into the trough', drive='boom_L', a='A', b='B', yc=float(d.Y['boom_cyl']), side=-1, trough_y=H.TROUGH['y_land']),
               dict(name='boom R drive cable, drop into the trough', drive='boom_R', a='A', b='B', yc=-float(d.Y['boom_cyl']), side=-1, trough_y=-H.TROUGH['y_land'])])
    # reference lengths of the moving cables at three poses, for the browser check
    ref = []
    for st in (tuple(Mo.WAYPOINTS[0][1]), (0.0, 0.0, 0.0), (60.0, 60.0, 60.0)):
        so = d.solve(st)
        lens = {}
        for sg in H.arm_cables(so, so['pins']):
            if sg['kind'] in ('loop', 'exit', 'drop'):
                lens[sg['name']] = round(H.length(sg['pts']), 3)
        ref.append(dict(strokes=list(st), lengths=lens))
    return out, dyn, ref


def main():
    parts, links, cfg = M.load()
    tab, pins = BV.tables(), BV.pin_locals()
    ver = BV.verify(tab, pins)
    trace_path = K.R12 / 'simulation/payload_150g_trace.json.gz'
    trace = K.load_gz(trace_path)
    tl, pay = timeline(trace)
    ic, sub = checks_summary()

    j9 = K.load_gz(K.J9 / 'source/j9_scene.json.gz')
    module = [dict(name=p['name'], color=p['color'], kind=p['kind'], group=p['group'], **pack_mesh(p['vertices'], p['triangles']))
              for p in j9['unit']]
    link = [dict(name=l['name'], color=l['color'], **pack_mesh(l['vertices'], l['triangles'])) for l in j9['link']]
    out, counts = [], {}
    for p in parts:
        if p['mover'] == 'track':
            if p['side'] > 0:
                counts['track'] = counts.get('track', 0) + 2
            continue
        stp, app, exp, grp = step_and_vectors(p)
        counts[p['sys']] = counts.get(p['sys'], 0) + 1
        out.append(dict(name=p['name'], sys=p['sys'], mover=p['mover'], color=p['color'], kind=p['kind'], step=stp, app=app, exp=exp, grp=grp,
                        group=p.get('group'), part=p.get('part'), new=p.get('new', False), joint=p.get('joint'), **pack_mesh(p['v'], p['t'])))
    wm, dyn, wref = wiring_meshes()
    for w in wm:                                               # step ids -> indices
        w['step'] = SID[w['step']]
    out += wm
    counts['wiring'] = len(wm) + len(dyn['loops']) + len(dyn['exits']) + len(dyn['drops'])
    counts['track'] += 2 * 2 * len(cfg['j9']['pins'])       # shoes and pins
    sysinfo = {k: dict(label=v[0], folder=v[1], revision=v[2], meshes=counts.get(k, 0)) for k, v in M.SYS.items()}
    config = dict(
        j9=cfg['j9'], track_y=cfg['track_y'], key=cfg['key'], pinion_axis=cfg['pinion_axis'], ratio=cfg['ratio'],
        O=K.O_VEH.tolist(), O_design_z=K.R12_DESIGN_O_Z, step=BV.STEP, tables=tab, pins=pins, pin_body=BV.PIN_BODY, closed=d.ACT['closed'],
        drives=[dict(name=n, a=a, b=b, y=float(y)) for n, a, b, y, *_ in BV.DRIVES], default=list(Mo.WAYPOINTS[0][1]),
        waypoints=[dict(name=n, strokes=list(s)) for n, s in Mo.WAYPOINTS[:-1]], phases=BV.phases(), duration=round(Mo.DURATION, 3),
        payload=dict(com=[d.MASS['payload'][1][0], 0.0, d.MASS['payload'][1][1]], kg=d.PAYLOAD, **pay),
        thrust_cont=d.ACT['thrust_cont'])
    wc = json.loads((K.ROOT / 'wiring_check.json').read_text()) if (K.ROOT / 'wiring_check.json').exists() else None
    ac = json.loads((K.ROOT / 'assembly_check.json').read_text()) if (K.ROOT / 'assembly_check.json').exists() else None
    data = dict(cfg=config, module=module, link=link, parts=out, sys=sysinfo, steps=STEPS, groups=GROUPS, labels=labels(), stdparts=stdparts_markers(),
                catalogue=dict(types=Cn.type_rows(), joints=[dict(j, pos=list(j['pos']), mate_dir=list(j['mate_dir'])) for j in Cn.JOINTS], pack=Cn.PACK),
                timeline=tl, trace=base64.b64encode(trace_path.read_bytes()).decode(), checks=ic, subsystem_reports=sub,
                wiring=dyn, wiring_ref=wref, wiring_check=(None if wc is None else dict(status=wc['status'], rules=wc['rules'],
                    cables={k: dict(min_clear_mm=v['min_clear_mm'], states=v['states'], chord=v.get('chord_mm'), L=v.get('cable_length_mm')) for k, v in wc['arm_cables'].items()},
                    static_min_clear_mm=min(c['clear_mm'] for c in wc['static_cables']))),
                assembly_check=(None if ac is None else dict(status=ac['status'], pin_O=ac['pin_O_insertion']['verdict'], arm_unit=ac['arm_unit_vertical_path']['clear'],
                                                             keys=ac['m6_key_access']['clear'], halves=ac['body_halves_removal']['clear'], hatch=ac['hatch_lift_vs_arm_poses']['clear'])))
    html = (K.HERE / 'viewer.html').read_text()
    for k, v in {'__THREE__': (K.VENDOR / 'three.min.js').read_text(), '__ORBIT__': (K.VENDOR / 'OrbitControls.js').read_text(),
                 '__DATA__': json.dumps(data, separators=(',', ':'))}.items():
        assert html.count(k) == 1, k
        html = html.replace(k, v)
    (K.ROOT / '3D_preview.html').write_text(html)
    (K.HERE / 'viewer_tables_check.json').write_text(json.dumps(ver, indent=1))
    print('3D_preview.html', round(len(html) / 1e6, 1), 'MB;', len(out), 'parts +', len(module), 'x 2 track parts;', 'timeline',
          round(tl[-1]['v0'] + tl[-1]['vd'], 1), 's shown,', round(tl[-1]['real0'] + tl[-1]['rd'], 1), 's real;', json.dumps(sub))


if __name__ == '__main__':
    main()

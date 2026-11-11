"""The complete machine as one list of meshes, each with the rule that moves it (vehicle frame, mm).

Movers
  ground      fixed to the lower: X-frame, belly cover, RU66, ring gear, slip-ring stator, cable envelopes
  track       a J9 module part on the left (+1) or right (-1) track; right = mirror image (J901/J909 mirrored prints)
  chain       track shoes and pins, placed from the J9 chain solution (phase in links)
  upper       turns with the swing: T101-T105, swing motor, body B1, electronics, B01X and R12's fixed pin hardware
  pinion      turns with the upper and RATIO x the swing about its own axis
  arm:<body>  an R12 body frame, placed by the drive strokes, then by the mount (O at O_VEH) and the swing

Sources are read from the subsystem folders at run time; nothing is copied, so a rebuild there flows through here.
"""
import math
import numpy as np
import common as K

SYS = dict(   # key: (label, source folder, revision)
    track=('Crawler tracks J9 (x 2)', 'track_wheel_jgy370/J9', 'J9 with the revision F seats and enclosed spring guide'),
    xframe=('X-frame and belly cover', 'track_wheel_jgy370/X1', 'X1 revision F (straight arms in the track seats)'),
    slew=('Slewing ring, ring gear and slip ring', 'track_wheel_jgy370/X1', 'THK RU66, X103 m1.5 x 80, 6-way 2 A slip ring (R3/R2)'),
    turntable=('Turntable and swing drive', 'track_wheel_jgy370/X1', 'R3 issue 3: T101-T106, JGY-370 swing motor'),
    body=('Upper body', 'track_wheel_jgy370/X1', 'B1 rev B (Cat 320 trace): B101-B107, steel shot'),
    electronics=('Battery and main board', 'track_wheel_jgy370/X1/controller', 'main board rev A (ESP32-S3, 7 x DRV8876), 3S 18650 pack'),
    arm=('Excavator arm', 'excavator_arm_r12', 'R12 Rev. D4 (Cat 325 pins, Cat bucket US 8,201,350), 4 x V6-U60; B01X mount (new)'),
    wiring=('Wiring harness and connectors', 'excavator_complete', 'harness.py (new): 4 drive cables with loops at O and E, slip ring, swing, battery, lamps; W01 clamps; connectors.py models'),
)


def _arr(v, t):
    v = np.asarray(v, np.float64).reshape(-1, 3)
    t = np.asarray(t, np.int64).reshape(-1, 3)
    return v, t


def load():
    x1 = K.load_gz(K.X1 / 'source/x1_scene.json.gz')
    j9 = K.load_gz(K.J9 / 'source/j9_scene.json.gz')          # the latest track module (as X1/source/build_viewer.py)
    tt = K.load_gz(K.X1 / 'source/turntable_scene.json.gz')
    bd = K.load_gz(K.X1 / 'source/body_scene.json.gz')
    r12 = K.load_gz(K.R12 / 'cad/scene.json.gz')
    b01x = K.load_gz(K.ROOT / 'cad/B01X_mesh.json.gz')
    parts = []

    def add(name, sys_, mover, v, t, color, kind, **kw):
        v, t = _arr(v, t)
        parts.append(dict(name=name, sys=sys_, mover=mover, v=v, t=t, color=[float(c) for c in color], kind=kind, **kw))

    for c in x1['chassis']:
        g = c['group']
        if g == 'reserve':                                    # the RU66 seat carries the turntable now
            continue
        add(c['name'], 'slew' if g == 'bearing' else 'xframe', 'ground', c['vertices'], c['triangles'], c['color'], c['kind'], group=g)
    for side in (1, -1):
        for p in j9['unit']:
            add(p['name'], 'track', 'track', p['vertices'], p['triangles'], p['color'], p['kind'], side=side, j9group=p['group'])
    links = [dict(name=l['name'], v=_arr(l['vertices'], l['triangles'])[0], t=_arr(l['vertices'], l['triangles'])[1],
                  color=l['color']) for l in j9['link']]
    for p in tt['items']:
        g = p['group']
        if g == 'arm':                                        # the ARM60 is replaced by R12
            continue
        mover = dict(lower='ground', rotor='upper', upper='upper', pinion='pinion')[g]
        sys_ = 'slew' if g in ('lower', 'rotor') else 'turntable'
        add(p['name'], sys_, mover, p['vertices'], p['triangles'], p['color'], p['kind'], group=g)
    for p in bd['items']:
        sys_ = 'electronics' if p['kind'] == 'electronics' else 'body'
        add(p['name'], sys_, 'upper', p['vertices'], p['triangles'], p['color'], p['kind'], part=p['part'])
    # R12: B01 is replaced by B01X; the rest of the base body (pins O and A, collars, spacers, shims) is unchanged
    for p in r12:
        if p['name'] == 'B01_boom_foot_bracket':
            continue
        b = p['body']
        add(p['name'], 'arm', 'upper' if b == 'base' else 'arm:' + b, p['v'], p['t'], p['color'], p['kind'], body=b)
    add(b01x['name'], 'arm', 'upper', b01x['v'], b01x['t'], b01x['color'], 'printed', body='base', new=True)
    conn = K.ROOT / 'cad/connectors_mesh.json.gz'            # build_connectors.py: the mated free connectors (12 V link XT30U-F, SM pairs)
    if conn.exists():
        for p in K.load_gz(conn)['parts']:
            add(p['name'], 'wiring', p['mover'], p['v'], p['t'], p['color'], 'connector', joint=p['joint'], new=True)
    # R12 base-body meshes are in the O frame: move them into the vehicle frame once
    for p in parts:
        if p.get('body') == 'base':
            p['v'] = p['v'] + K.O_VEH
    cfg = dict(j9=j9['config'], key=x1['config']['key'], track_y=x1['config']['track_y'], revision=x1['config']['revision'],
               pinion_axis=tt['pinion_axis'], ratio=tt['ratio'], body_slide_out=bd['slide_out'])
    return parts, links, cfg


# ------------------------------------------------------------------ transforms (rotation R, translation t: x' = R x + t)
def chain_transforms(cfg, phase):
    """Shoe and pin transforms in the track frame (X1 viewer setPhase twin): link j sits between pins j+k and j+k+1."""
    V = cfg['j9']
    P, R = np.asarray(V['pins'], float), V['pitch_r']
    N, C = len(P), [np.asarray(V['drive']), np.asarray(V['idler'])]
    k, f = int(math.floor(phase)) % N, phase - math.floor(phase)

    def on(p, c):
        return abs(math.hypot(p[0] - c[0], p[1] - c[1]) - R) < 1e-4

    def interp(a, b):
        for c in C:
            if on(a, c) and on(b, c):
                ta, tb = math.atan2(a[1] - c[1], a[0] - c[0]), math.atan2(b[1] - c[1], b[0] - c[0])
                if tb < ta:
                    tb += 2 * math.pi
                t = ta + (tb - ta) * f
                return np.array([c[0] + R * math.cos(t), c[1] + R * math.sin(t)])
        return a + (b - a) * f
    q = [interp(P[(j + k) % N], P[(j + k + 1) % N]) for j in range(N)]
    shoes, pins = [], []
    for j in range(N):
        a, b = q[j], q[(j + 1) % N]
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        shoes.append((K.rot_y(ang), np.array([(a[0] + b[0]) / 2, 0.0, (a[1] + b[1]) / 2])))
        pins.append((np.eye(3), np.array([a[0], 0.0, a[1]])))
    return shoes, pins


def track_frame(cfg, side):
    """Track-local -> vehicle: the left module as exported at +track_y; the right one mirrored in Y."""
    return np.diag([1.0, float(side), 1.0]), np.array([0.0, side * cfg['track_y'], 0.0])


def arm_transforms(body_poses, swing_deg=0.0):
    """body_poses: {body: ((x, z), angle)} in the R12 O frame -> {body: (R, t)} in the vehicle frame."""
    Rs = K.rot_z(swing_deg)
    out = {}
    for b, ((ox, oz), a) in body_poses.items():
        R = K.rot_y(a)
        t = np.array([ox, 0.0, oz]) + K.O_VEH
        out[b] = (Rs @ R, Rs @ t)
    return out


def upper_transform(swing_deg):
    return K.rot_z(swing_deg), np.zeros(3)


def pinion_transform(cfg, swing_deg):
    px, py = cfg['pinion_axis']
    Rp = K.rot_z(cfg['ratio'] * swing_deg)
    c = np.array([px, py, 0.0])
    Rs = K.rot_z(swing_deg)
    return Rs @ Rp, Rs @ (c - Rp @ c)

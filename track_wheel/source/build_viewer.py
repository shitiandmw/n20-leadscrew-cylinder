"""Offline viewer for the track wheel unit: ../3D_preview.html.

Packs the CAD scene (track_wheel_scene.json.gz), one chain link in its own
frame, and the MuJoCo traces into a single HTML file with three.js inlined.
Run after build_track_wheel.py and simulate_track_wheel.py.
"""
import array, base64, gzip, json, math, sys
import tw_parts as tp
from tw_design import *

ROOT = tp.ROOT
VENDOR = tp.REPO / 'actuator_v6/source/vendor'
PLAYBACK = ['fixture', 'reverse_wall', 'debris', 'obstacle']


def pack(vertices, triangles):
    wide = len(vertices) >= 65536
    out = {'wide': wide}
    for src, key, t in [(vertices, 'v', 'f'), (triangles, 't', 'I' if wide else 'H')]:
        a = array.array(t, (v for row in src for v in row))
        if sys.byteorder != 'little':
            a.byteswap()
        out[key] = base64.b64encode(a.tobytes()).decode()
    return out


def link_mesh():
    """Shoe, bushing, pin and clips in the shoe frame (pin at x = +10), as one mesh."""
    ex = tp.ex; parts = []
    shoe = tp.track_shoe()
    bits = [shoe, tp.yring(ex.BUSH_R, 1.55, -ex.BUSH_LENGTH / 2, ex.BUSH_LENGTH / 2, 10, 0),
            tp.ycyl(1.5, -ex.PIN_LENGTH / 2, ex.PIN_LENGTH / 2, 10, 0)]
    bits += [tp.yring(3, 1.5, dy - .3, dy + .3, 10, 0) for dy in [-ex.PIN_CLIP_Y, ex.PIN_CLIP_Y]]
    out = []
    for i, b in enumerate(bits):
        v, f = tp.one(b).tessellate(.08, .15)
        out.append(dict(color=list(tp.RUBBER if i == 0 else tp.STEEL),
                        **pack([[round(p.x, 4), round(p.y, 4), round(p.z, 4)] for p in v], [list(t) for t in f])))
    return out


def traces():
    out = {}
    for name in PLAYBACK:
        p = ROOT / 'simulation' / f'{name}_trace.json'
        rep = json.loads((ROOT / 'simulation' / f'{name}.json').read_text())['report']
        tr = json.loads(p.read_text())
        rows = []
        for s in tr:
            stone = s.get('stone') or [float('nan')] * 3
            row = [s['t'], s['drive'], s['idler_mm'], *s['frame'], *s['wheels'], s['current_A'], max(s['tension']), *stone]
            for pos, q in zip(s['shoes'], s['quats']):
                row.extend(pos); row.extend(q)
            rows.extend(row)
        stride = 17 + 7 * tp.ex.TRACK_LINKS
        assert len(rows) == stride * len(tr)
        a = array.array('f', rows)
        if sys.byteorder != 'little':
            a.byteswap()
        cfg = __import__('simulate_track_wheel').CASES[name]
        out[name] = dict(frames=base64.b64encode(a.tobytes()).decode(), count=len(tr), stride=stride,
                         ground=cfg['ground'], note=cfg['note'], status=rep['status'], bump=cfg.get('bump'),
                         stone=cfg.get('stone'), wall=cfg.get('wall'),
                         spring=dict(k=rep['spring_rate_N_mm'], springref_mm=__import__('simulate_track_wheel').SPRINGS['R5']['springref'] * 1000))
    return out


def config():
    ex = tp.ex
    seat_front = REAR_WALL_X[1] + ADJUST_NOMINAL + SEAT_BLOCK
    return dict(drive=[DRIVE_X, tp.AXLE_Z], pinion=[tp.PX, tp.PZ], idler=[IDLER_X + ex.IDLER_ASSEMBLY_OFFSET, tp.AXLE_Z],
                assembly_offset=ex.IDLER_ASSEMBLY_OFFSET, ratio=RING_TEETH / PINION_TEETH,
                rollers=[[x, 29] for x in ex.ROAD_ROLLERS] + [[x, tp.RETURN_Z] for x in ex.RETURN_ROLLERS],
                spring=dict(seat_front=seat_front, length=spring_state()['length'], y=SPRING_AXIS[0], z=tp.AXLE_Z),
                spy=SPRING_AXIS[0], gear_y=sum(RING_Y) / 2, recoil_stop=recoil_travel(),
                poses=[dict(o=[float(o[0]), float(o[1])], a=float(a)) for _, o, a in ex.track_poses()],
                preload=spring_state()['force'], rate=SPRING['rate_N_mm'])


def build():
    items = json.loads(gzip.decompress((ROOT / 'source/track_wheel_scene.json.gz').read_bytes()))
    meshes = []
    for p in items:
        out = {k: v for k, v in p.items() if k not in ['vertices', 'triangles']}
        out.update(pack(p['vertices'], p['triangles'])); meshes.append(out)
    html = (ROOT / 'source/viewer_template.html').read_text()
    data = dict(config=config(), meshes=meshes, link=link_mesh(), traces=traces(),
                validation=json.loads((ROOT / 'validation.json').read_text())['summary'])
    for token, value in {'__THREE__': (VENDOR / 'three.min.js').read_text(), '__ORBIT__': (VENDOR / 'OrbitControls.js').read_text(),
                         '__DATA__': json.dumps(data, separators=(',', ':'))}.items():
        assert html.count(token) == 1, token
        html = html.replace(token, value)
    (ROOT / '3D_preview.html').write_text(html)
    print('Offline viewer', round(len(html) / 1e6, 1), 'MB')


if __name__ == '__main__':
    build()

"""Pack x1_scene.json.gz (+ turntable_scene.json.gz, body_scene.json.gz) into the offline single-file viewer ../3D_preview.html."""
import sys, json, gzip, array, base64
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[1]                  # repository root


def pack(items):
    out = []
    for s in items:
        d = {k: v for k, v in s.items() if k not in ('vertices', 'triangles')}
        d['wide'] = len(s['vertices']) >= 65536
        for src, key, t in [('vertices', 'v', 'f'), ('triangles', 't', 'I' if d['wide'] else 'H')]:
            a = array.array(t, (v for row in s[src] for v in row))
            if sys.byteorder != 'little': a.byteswap()
            d[key] = base64.b64encode(a.tobytes()).decode()
        out.append(d)
    return out


def main():
    data = json.loads(gzip.decompress((HERE / 'x1_scene.json.gz').read_bytes()))
    # J9 and X1 exports may run separately. Always embed the latest generated
    # track module so the spring guide and mounting stations match the chassis.
    track = json.loads(gzip.decompress((ROOT.parent / 'J9/source/j9_scene.json.gz').read_bytes()))
    latest = dict(module=track['unit'], link=track['link'], j9=track['config'])
    if any(data[k] != v for k, v in latest.items()):
        data.update(latest)
        (HERE / 'x1_scene.json.gz').write_bytes(gzip.compress(json.dumps(data, separators=(',', ':')).encode()))
    for k in ('module', 'link', 'chassis'):
        data[k] = pack(data[k])
    tt = HERE / 'turntable_scene.json.gz'                 # build_turntable.py
    if tt.exists():
        t = json.loads(gzip.decompress(tt.read_bytes()))
        data['turntable'] = dict(items=pack(t['items']), pinion_axis=t['pinion_axis'], ratio=t['ratio'])
        # the RU66 seat now carries the turntable: drop the old 'reserved' disc from the chassis list
        data['chassis'] = [c for c in data['chassis'] if c['group'] != 'reserve']
    bd = HERE / 'body_scene.json.gz'                      # build_body.py
    if bd.exists():
        b = json.loads(gzip.decompress(bd.read_bytes()))
        data['body'] = dict(items=pack(b['items']), slide_out=b['slide_out'], sweep_ok=b.get('sweep_ok'))
    tr = ROOT / 'simulation/turntable_swing_traces.json'  # simulate_swing.py
    if tr.exists():
        traces = json.loads(tr.read_text())
        rep = json.loads((ROOT / 'simulation/turntable_swing_report.json').read_text())['cases']
        sw = {}
        for case in ('start_stop_ramp', 'start_stop_step', 'reverse_ramp'):
            if case in traces:
                tt_, deg = traces[case]['t'], traces[case]['swing_deg']
                step = max(1, int(round(.02/(tt_[1] - tt_[0]))))         # 50 Hz is plenty for playback
                sw[case] = dict(t=tt_[::step], deg=[round(d - deg[0], 3) for d in deg[::step]], note=rep[case]['note'],
                                peak_tooth_force_N=rep[case]['peak_tooth_force_N'])
        data['swing'] = sw
    vendor = REPO / 'actuator_v6/source/vendor'
    html = (HERE / 'viewer.html').read_text()
    for k, v in {'__THREE__': (vendor / 'three.min.js').read_text(), '__ORBIT__': (vendor / 'OrbitControls.js').read_text(),
                 '__DATA__': json.dumps(data, separators=(',', ':'))}.items():
        assert html.count(k) == 1, k
        html = html.replace(k, v)
    (ROOT / '3D_preview.html').write_text(html)
    print('X1 viewer', round(len(html)/1e6, 1), 'MB')


if __name__ == '__main__':
    main()

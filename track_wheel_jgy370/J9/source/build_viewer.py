"""Pack j9_scene.json.gz into the offline single-file viewer ../3D_preview.html."""
import sys, json, gzip, array, base64
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[1]


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
    data = json.loads(gzip.decompress((HERE / 'j9_scene.json.gz').read_bytes()))
    data['unit'] = pack(data['unit']); data['link'] = pack(data['link'])
    vendor = REPO / 'actuator_v6/source/vendor'
    html = (HERE / 'viewer.html').read_text()
    for k, v in {'__THREE__': (vendor / 'three.min.js').read_text(), '__ORBIT__': (vendor / 'OrbitControls.js').read_text(),
                 '__DATA__': json.dumps(data, separators=(',', ':'))}.items():
        assert html.count(k) == 1, k
        html = html.replace(k, v)
    (ROOT / '3D_preview.html').write_text(html)
    print('J9 viewer', round(len(html)/1e6, 1), 'MB')


if __name__ == '__main__':
    main()

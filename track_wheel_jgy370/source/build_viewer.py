import sys,json,gzip,array,base64
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parent

def pack(items):
    out=[]
    for s in items:
        d={k:v for k,v in s.items() if k not in ['vertices','triangles']};d['wide']=len(s['vertices'])>=65536
        for src,key,t in [('vertices','v','f'),('triangles','t','I' if d['wide'] else 'H')]:
            a=array.array(t,(v for row in s[src] for v in row))
            if sys.byteorder!='little':a.byteswap()
            d[key]=base64.b64encode(a.tobytes()).decode()
        out.append(d)
    return out

def main():
    data=json.loads(gzip.decompress((ROOT/'source/j8_scene.json.gz').read_bytes()))
    for k in ['unit','bridge']:data[k]=pack(data[k])
    # J8 has a direct coupling. Do not expose the archived R5 pinion configuration.
    data['config'].pop('pinion',None);data['config']['ratio']=1
    data['trace']=json.loads((ROOT/'simulation/demo_trace.json').read_text())
    data['report']=json.loads((ROOT/'simulation/demo_report.json').read_text())
    assert data['report']['playback_checks_pass']
    vendor=REPO/'actuator_v6/source/vendor';html=(ROOT/'source/viewer.html').read_text()
    for k,v in {'__THREE__':(vendor/'three.min.js').read_text(),'__ORBIT__':(vendor/'OrbitControls.js').read_text(),'__DATA__':json.dumps(data,separators=(',',':'))}.items():
        assert html.count(k)==1;html=html.replace(k,v)
    (ROOT/'3D_preview.html').write_text(html)
    print('J8 offline motion viewer:',round(len(html)/1e6,1),'MB')

if __name__=='__main__':main()

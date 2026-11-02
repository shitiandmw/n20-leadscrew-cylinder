"""Offline assembly viewer; retains the original arm60 kinematic implementation."""
import json,gzip,array,base64,re,hashlib
from design import *

def track_playback():
    report=json.loads((ROOT/'simulation/track_ground_dynamics.json').read_text())
    assert report['status']=='PASS', 'Loaded track simulation must pass before publishing playback'
    trace_bytes=(ROOT/'simulation/track_ground_trace.json').read_bytes()
    trace=json.loads(trace_bytes)
    rows=[]
    for sample in trace:
        row=[sample['t'],*(1000*x for x in sample['frame']),sample['idler_mm'],
             sample['speed'],sample['torque'],sample['target'],sample['ground_normal_N'],*sample['wheels']]
        for point,q in zip(sample['points'],sample['quaternions']):
            row.extend(1000*x for x in point);row.extend(q)
        assert len(row)==16+7*TRACK_LINKS
        rows.extend(row)
    a=array.array('f',rows)
    if sys.byteorder!='little':a.byteswap()
    return dict(frames=base64.b64encode(a.tobytes()).decode(),count=len(trace),stride=16+7*TRACK_LINKS,
                source_trace_sha256=hashlib.sha256(trace_bytes).hexdigest(),
                dt=trace[1]['t']-trace[0]['t'],duration=trace[-1]['t'],
                supported_mass_kg=report['loaded']['total_supported_mass_kg'],
                initial_poses=[dict(origin=o.tolist(),angle=a) for _,o,a in track_poses()])

def build():
    items=json.loads(gzip.decompress((ROOT/'source/vehicle_scene.json.gz').read_bytes()))
    arm_items=json.loads(gzip.decompress((REPO/'excavator_arm_60mm/source/scene.json.gz').read_bytes()))
    for p in arm_items:p['arm']=True
    packed=[]
    for p in items+arm_items:
        out={k:v for k,v in p.items() if k not in ['vertices','triangles']}
        wide=len(p['vertices'])>=65536
        for src,key,t in [('vertices','v','f'),('triangles','t','I' if wide else 'H')]:
            a=array.array(t,(v for row in p[src] for v in row))
            if sys.byteorder!='little':a.byteswap()
            out[key]=base64.b64encode(a.tobytes()).decode()
        out['wide']=wide;packed.append(out)
    original=(REPO/'excavator_arm_60mm/source/viewer_template.html').read_text()
    solver=original[original.index('const add='):original.index('const axisNames=')]
    html=(ROOT/'source/viewer_template.html').read_text()
    replacements={'__THREE__':(REPO/'actuator_v6/source/vendor/three.min.js').read_text(),
        '__ORBIT__':(REPO/'actuator_v6/source/vendor/OrbitControls.js').read_text(),
        '__DATA__':json.dumps(dict(config=config(),meshes=packed,track=track_playback()),separators=(',',':')),
        '__TRACK__':(ROOT/'source/track_playback.js').read_text(),
        '__SOLVER__':solver}
    for token,value in replacements.items():
        assert html.count(token)==1,token
        html=html.replace(token,value)
    (ROOT/'3D_preview.html').write_text(html)
    cases=[]
    import itertools
    for st in itertools.product([0,15,30,45,60],repeat=3):
        cases.append(dict(strokes=st,points={k:v.tolist() for k,v in arm.solve(st)['points'].items()}))
    (ROOT/'source/kinematic_cases.json').write_text(json.dumps(cases))
    print('Offline viewer',round(len(html)/1e6,1),'MB')

if __name__=='__main__':build()

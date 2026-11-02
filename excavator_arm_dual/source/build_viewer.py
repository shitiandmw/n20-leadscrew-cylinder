from pathlib import Path
import json,gzip,base64,array,sys
from kinematics import config,ACTUATORS,solve,STROKES
import itertools
import numpy as np
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent
items=json.loads(gzip.decompress((ROOT/'source/scene.json.gz').read_bytes()))
packed=[]
for p in items:
    n={k:v for k,v in p.items() if k not in ['vertices','triangles']};wide=len(p['vertices'])>=65536
    for src,key,t in [('vertices','v','f'),('triangles','t','I' if wide else 'H')]:
        a=array.array(t,(v for row in p[src] for v in row))
        if sys.byteorder!='little':a.byteswap()
        n[key]=base64.b64encode(a.tobytes()).decode()
    n['wide']=wide;packed.append(n)
s=(ROOT/'source/viewer_template.html').read_text()
traces={name:base64.b64encode((ROOT/'simulation'/(name+'_trace.json.gz')).read_bytes()).decode() for name in ['unloaded','payload_150g']}
replay=(ROOT/'source/physics_replay.js').read_text().replace('__PHYSICS__',json.dumps(traces,separators=(',',':')))
s=s.replace('__REPLAY__',replay)
for a,b in {'__REFERENCE__':'data:image/png;base64,'+base64.b64encode((ROOT/'references/user_structure.png').read_bytes()).decode(),'__DATA__':json.dumps({'meshes':packed,'config':config()},separators=(',',':')),'__THREE__':(REPO/'actuator_v6/source/vendor/three.min.js').read_text(),'__ORBIT__':(REPO/'actuator_v6/source/vendor/OrbitControls.js').read_text()}.items():assert s.count(a)==1;s=s.replace(a,b)
review=(ROOT/'source/motion_ui.js').read_text().replace('__MOTION_DATA__',(ROOT/'motion.json').read_text())
s=s.replace('</body>','<script>'+review+'</script></body>').replace('<html lang="en">','<html lang="zh-CN">').replace('Excavator arm R7 · Single lift / replaceable teeth','R10 双推杆回旋镖形大臂 / 运动仿真')
(ROOT/'3D_preview.html').write_text(s);print('Offline preview:',round(len(s)/1e6,2),'MB')

cases=[dict(strokes=[float(x) for x in st],points={k:v.tolist() for k,v in solve(st)['points'].items()}) for st in itertools.product(*[np.linspace(0,v,5) for v in STROKES])]
(ROOT/'source/kinematic_cases.json').write_text(json.dumps(cases))

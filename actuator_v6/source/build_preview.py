"""Build the standalone offline partition preview from exported CAD meshes."""
from pathlib import Path
import array,base64,gzip,hashlib,json,sys

source=Path(__file__).resolve().parent.parent
output=source / '3D_preview.html'
def packed(items):
    result=[]
    for item in items:
        meta={k:v for k,v in item.items() if k not in ('vertices','triangles')}
        wide=len(item['vertices'])>=65536
        for field,dest,kind in [('vertices','v','f'),('triangles','t','I' if wide else 'H')]:
            values=array.array(kind,(x for row in item[field] for x in row))
            if sys.byteorder!='little': values.byteswap()
            meta[dest]=base64.b64encode(values.tobytes()).decode()
        meta['wide']=wide
        result.append(meta)
    return result
evidence=['source/scene_S.json.gz','source/scene_L.json.gz','parameters.json','validation.json','magnet_trigger.json','electronics/pcb/V6-S/check_S.json','electronics/pcb/V6-L/check_L.json','electronics/simulation/results.json']
data={'params':json.loads((source/'parameters.json').read_text()),
      'scenes':{v:packed(json.loads(gzip.decompress((source/f'source/scene_{v}.json.gz').read_bytes()))) for v in 'SL'},
      'hashes':{p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in evidence}}
template=(source / 'source/preview_template.html').read_text()
for key,value in {'__DATA__':json.dumps(data,separators=(',',':')),'__THREE__':(source/'source/vendor/three.min.js').read_text(),'__ORBIT__':(source/'source/vendor/OrbitControls.js').read_text()}.items():
    assert template.count(key)==1,key
    template=template.replace(key,value)
output.parent.mkdir(exist_ok=True)
output.write_text(template)
print(f'Created {output.name}: {output.stat().st_size/1e6:.2f} MB; 92 CAD meshes per variant')

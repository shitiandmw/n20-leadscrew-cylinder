"""Generate matching V6 bodies, rods, boards and internals for the new screw lengths.
Imports the original parametric source read-only; all outputs/caches are redirected.
"""
from pathlib import Path
import sys,json,gzip,time
from kinematics import ACTUATORS
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'actuators';REPO=ROOT.parent
sys.path.insert(0,str(REPO/'actuator_v6/source'))
import layout as L,board as BD,design_v6 as D,build_v6 as B,pcb_export as PCB
for p in [OUT/'source',OUT/'images',OUT/'electronics/pcb']:p.mkdir(parents=True,exist_ok=True)
BD.ROOT=OUT;B.ROOT=OUT;PCB.ROOT=OUT;PCB.OUT=OUT/'electronics/pcb'
for v in ACTUATORS.values():L.VARIANTS[v['variant']]={'screw_length':v['screw'],'stroke':v['stroke']}

def run():
    params={};validation={};pcb={}
    for name,v in ACTUATORS.items():
        variant=v['variant'];start=time.time();print('Build custom actuator',name,v,flush=True)
        pcb.update(PCB.main([variant]))
        d=D.make_design(variant);params[variant]=dict(d['params'],role=name,quantity=v['quantity'],screw_pitch_mm=.5)
        items=B.scene_items(d)
        (OUT/'source'/f'scene_{variant}.json.gz').write_bytes(gzip.compress(json.dumps(items,separators=(',',':')).encode()))
        parts=B.export(d,OUT,with_fit_samples=False)
        report=B.validate(d);report['parts']=parts
        report['all_meshes_pass']=all(p['watertight'] and p['winding_consistent'] and p['components']==1 for p in parts.values())
        report['all_checks_pass'] &= report['all_meshes_pass']
        assert report['all_checks_pass'],name
        validation[variant]=report
        (OUT/'parameters.json').write_text(json.dumps(params,indent=2));(OUT/'validation.json').write_text(json.dumps(validation,indent=2))
        print('PASS actuator',name,round(time.time()-start,1),'seconds',flush=True)
    (OUT/'electronics/pcb/validation.json').write_text(json.dumps(pcb,indent=2))

if __name__=='__main__':run()

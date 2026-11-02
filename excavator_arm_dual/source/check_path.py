"""Check unchanged R7 exact solids at endpoints and midpoints of the new path."""
from pathlib import Path
import sys,json,gzip,itertools,hashlib,time
REPO=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'excavator_arm_dual/source'))
from build_arm import *

def main():
    began=time.time();scene=json.loads(gzip.decompress((REPO/'excavator_arm_dual/source/scene.json.gz').read_bytes()))
    parts={m['name']:dict(shape=cq.importers.importStep(str(REPO/'excavator_arm_dual/step'/(m['name']+'.step'))),group=m['group'],kind=m['kind']) for m in scene if m['kind']=='printed'}
    hw=hardware();parts.update(hw);acts=load_actuators();group={n:p['group'] for n,p in parts.items()}
    for label,role,idx,a,b,cy in actuator_instances():
        for n in acts[role]:group[label+'_V6_'+n]='act_'+label
    data=json.loads((OUT/'motion.json').read_text());times=sorted(set(t for p in data['phases'] for t in [p['start'],(p['start']+p['end'])/2,p['end']]))
    poses=[];seen=set()
    for t in times:
        f=data['frames'][min(len(data['frames'])-1,round(t*48))];key=tuple(round(s,9) for s in f['strokes'])
        if key not in seen:poses.append((t,f['strokes']));seen.add(key)
    maximum=0.;checks=0;fail=[];cache={}
    for t,strokes in poses:
        posed=placed_parts(parts,acts,strokes);boxes={n:one(s).BoundingBox() for n,s in posed.items()}
        for n,m in itertools.combinations(posed,2):
            same=group[n]==group[m]
            if same and (group[n].startswith('act_') or (n in hw and m in hw)):continue
            bn,bm=boxes[n],boxes[m]
            if any(getattr(bn,a+'max')<=getattr(bm,a+'min')+1e-6 or getattr(bm,a+'max')<=getattr(bn,a+'min')+1e-6 for a in 'xyz'):continue
            if same and (n,m) in cache:volume=cache[n,m]
            else:
                volume=sum(s.Volume() for s in posed[n].intersect(posed[m]).solids().vals());checks+=1
                if same:cache[n,m]=volume
            maximum=max(maximum,volume)
            if volume>.02:fail.append(dict(time=t,parts=[n,m],volume_mm3=volume))
        print('pose',t,'checks',checks,'overlaps',len(fail),flush=True)
    result=dict(status='PASS' if not fail else 'FAIL',sampled_poses=len(poses),sample_times_seconds=[p[0] for p in poses],exact_intersections=checks,maximum_overlap_mm3=maximum,failures=fail,motion_sha256=hashlib.sha256((OUT/'motion.json').read_bytes()).hexdigest(),geometry='R10 paired-drive STEP solids, R10 hardware and U60 exteriors',scope='Sampled endpoint/midpoint clearance, not continuous proof; no soil, chassis or force qualification.',elapsed_s=time.time()-began)
    (OUT/'path_validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));assert not fail
if __name__=='__main__':main()

"""Reference proportions, actuator/link closure, scoop direction and sampled CAD checks.
The earth-working envelope may extend below the mounting plane, as on the reference.
"""
import itertools,json,math,time
import numpy as np
from shapely.geometry import MultiPoint
from build_arm import *


def check():
    start=time.time();fail=[];closure=0.;derivatives={k:[] for k in ORDER};levers={k:[] for k in ORDER};mus=[]
    for u in np.linspace(0,1,461):
        strokes=-3+u*(STROKES+6);s=solve(strokes);p=s['points'];tr=transmission(strokes)
        for i,(key,a,b) in enumerate([('boom','A','B'),('stick','C','D'),('bucket','F','R')]):
            closure=max(closure,abs(np.linalg.norm(p[b]-p[a])-CLOSED[i]-strokes[i]));derivatives[key].append(tr[key]['degrees_per_mm']);levers[key].append(tr[key]['effective_moment_arm_mm'])
        for a,b,l in [('O','E',BOOM),('E','H',STICK),('J','R',ROCKER),('R','Q',COUPLER),('H','Q',HORN),('H','T',TIP_RADIUS)]:closure=max(closure,abs(np.linalg.norm(p[b]-p[a])-l))
        mus.append(tr['four_bar_transmission_angle_deg'])
    assert closure<1e-8
    assert min(derivatives['boom'])>0 and max(derivatives['stick'])<0 and max(derivatives['bucket'])<0
    assert abs(BOOM/STICK-5700/2900)<1e-12 and abs(np.linalg.norm(TIP)-1570/12)<1e-9
    reference=solve();p=reference['points'];assert p['T'][0]<p['H'][0],'Neutral teeth must face toward machine'
    # With boom/stick at the reference pose, extension must lift the cutting lip during curl.
    curl=[solve([*default_strokes()[:2],x])['points']['T'][1] for x in np.linspace(0,STROKES[2],121)]
    assert np.min(np.diff(curl))>0,'Bucket cylinder extension should curl cutting lip upward'
    parts=structures();hw=hardware();acts=load_actuators();allparts={**parts,**hw}
    names=list(allparts)+[label+'_V6_'+n for label,role,i,a,b,cy in actuator_instances() for n in acts[role]]
    group={n:p['group'] for n,p in allparts.items()};ameta={}
    for label,role,i,a,b,cy in actuator_instances():
        for n in acts[role]:group[label+'_V6_'+n]='act_'+label;ameta[label+'_V6_'+n]=(i,n.startswith(('04','05')))
    nominal=list(itertools.product(*[np.linspace(0,v,5) for v in STROKES]));guard=list(itertools.product(*[[-3,v+3] for v in STROKES]))
    poses=nominal+guard+[default_strokes()];cache={};collisions=[];booleans=cached=0;max_v=0
    for i,strokes in enumerate(poses):
        st=solve(strokes);placed=placed_parts(allparts,acts,strokes);transforms={g:(np.array([o[0],0,o[1]]),st['angles'][g]) for g,o in st['origins'].items()}
        for label,role,idx,a,b,cy in actuator_instances():
            u=st['points'][b]-st['points'][a];transforms['act_'+label]=(np.array([st['points'][a][0],cy,st['points'][a][1]]),math.atan2(u[1],u[0]))
        boxes={n:one(s).BoundingBox() for n,s in placed.items()}
        for ni,n in enumerate(names):
            for m in names[ni+1:]:
                gn,gm=group[n],group[m]
                if n in hw and m in hw and gn==gm:continue
                if gn==gm and gn.startswith('act_'):continue
                bn,bm=boxes[n],boxes[m]
                if any(getattr(bn,a+'max')<=getattr(bm,a+'min')+1e-6 or getattr(bm,a+'max')<=getattr(bn,a+'min')+1e-6 for a in 'xyz'):continue
                on,an=transforms[gn];om,aa=transforms[gm];offset=om-on;rr=rot(-an)@offset[[0,2]]
                travel=tuple(strokes[ameta[x][0]] if x in ameta and ameta[x][1] else 0 for x in [n,m])
                key=(n,m,*np.round(rr,5),round(offset[1],5),round(aa-an,5),*travel)
                if key in cache:volume=cache[key];cached+=1
                else:
                    volume=sum(s.Volume() for s in placed[n].intersect(placed[m]).solids().vals());cache[key]=volume;booleans+=1
                max_v=max(max_v,volume)
                if volume>.02:collisions.append(dict(parts=[n,m],strokes_mm=[float(x) for x in strokes],volume_mm3=round(volume,5)))
        if i%10==0:print('pose',i,'/',len(poses),'boolean pairs',booleans,'collisions',len(collisions),flush=True)
    if collisions:fail.append('solid interference')
    # Tooth envelope over the same independent control cube, sampled more densely.
    xyz=[]
    for strokes in itertools.product(*[np.linspace(0,v,21) for v in STROKES]):xyz.append(solve(strokes)['points']['T'])
    xyz=np.array(xyz)
    rep=dict(status='PASS' if not fail else 'FAIL',revision=2,reference='Cat 320 Reach boom/R2.9B1 stick, 1:12',failures=fail,units='mm',
      nominal_strokes_mm=STROKES.tolist(),actuator_closed_mm=CLOSED.tolist(),closure_samples=461,max_pin_closure_error_mm=closure,
      nominal_angles_deg={k:[math.degrees(solve(v)[a]) for v in [np.zeros(3),STROKES]] for k,a in [('boom','theta'),('stick_relative_to_boom','phi'),('bucket_relative_to_stick','gamma')]},
      guard_transmission_degrees_per_mm={k:[min(v),max(v)] for k,v in derivatives.items()},guard_effective_moment_arm_mm={k:[min(v),max(v)] for k,v in levers.items()},
      four_bar_guard_transmission_angle_deg=[min(mus),max(mus)],bucket_faces_machine_in_reference_pose=True,bucket_lip_rises_during_reference_curl=True,
      factory_dimensions_mm={'boom':5700,'stick':2900,'bucket_width':1200,'bucket_tip_radius':1570},model_scale=12,
      solid_collision_poses=len(poses),exact_boolean_pairs=booleans,cached_pairs=cached,maximum_intersection_mm3=max_v,collision_volume_tolerance_mm3=.02,collisions=collisions,
      tooth_envelope_samples=len(xyz),tooth_x_range_mm=[float(xyz[:,0].min()),float(xyz[:,0].max())],tooth_z_range_mm=[float(xyz[:,1].min()),float(xyz[:,1].max())],below_mounting_plane_samples=int((xyz[:,1]<0).sum()),
      scope='134 sampled configurations: 5^3 nominal combinations, eight reserve corners and the reference pose. External structures, pin/spacer/collar envelopes and regenerated V6 exteriors. Below-Z=0 poses represent the reference excavator digging below its mounting plane; solid-floor operation requires restricting those poses or a clear recess. This is not a continuous collision proof or a payload/physical-fit test.',elapsed_seconds=round(time.time()-start,1))
    (ROOT/'validation.json').write_text(json.dumps(rep,indent=2));print(json.dumps({k:v for k,v in rep.items() if k!='collisions'},indent=2));print('First collisions',collisions[:25]);return not fail

if __name__=='__main__':
    import sys
    sys.exit(0 if check() else 1)

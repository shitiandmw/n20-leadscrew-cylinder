"""Check actual J8 solids at sampled reused J6 motion poses and roller service steps."""
import json,math,time
import numpy as np
import cadquery as cq
import j8_parts as s
import tw_checks as checks

def pose(shape,xyz,q):
    w,x,y,z=np.asarray(q)/np.linalg.norm(q)
    length=math.sqrt(x*x+y*y+z*z)
    angle=math.degrees(2*math.atan2(length,w))
    rotated=shape.rotate((0,0,0),(x/length,y/length,z/length),angle) if length>1e-12 else shape
    return rotated.translate(tuple(xyz))

def main():
    start=time.time();new=s.parts();inst=s.unit(new);trace=json.loads((s.ROOT/'simulation/demo_trace.json').read_text())
    p=s.p;G=p.ex
    bits=[p.one(p.track_shoe()),p.one(p.yring(G.BUSH_R,1.55,-G.BUSH_LENGTH/2,G.BUSH_LENGTH/2,10,0)),p.one(p.ycyl(1.5,-G.PIN_LENGTH/2,G.PIN_LENGTH/2,10,0))]
    bits += [p.one(p.yring(3,1.5,y-.3,y+.3,10,0)) for y in [-G.PIN_CLIP_Y,G.PIN_CLIP_Y]]
    link=cq.Workplane(obj=cq.Compound.makeCompound(bits))
    fixed={n:d for n,d in inst.items() if n.startswith(('J7','J8')) and d['group'] not in ['track','drive']}
    checks_motion=[]
    for t in [0,1.5,2,2.5,3,4,5,6,7,8,9,10,11.5,12.5,13.5]:
        r=min(trace,key=lambda a:abs(a['t']-t));moving={}
        for i,(xyz,q) in enumerate(zip(r['shoes'],r['quats'])):moving[f'link_{i}']=dict(shape=pose(link,xyz,q),group='track')
        a=checks.interference({**fixed,**moving},skip=lambda a,b:((a in moving)==(b in moving)))
        wheels={n:{**d,'shape':d['shape'].rotate((x,0,z),(x,1,z),r['wheels'][4+i]*180/math.pi)} for i,(x,z,g) in enumerate(s.AXES[3:]) for n,d in inst.items() if n==f'J624_compact_return_roller_{i}'}
        assert len(wheels)==2, 'Both actual upper rollers must be checked'
        b=checks.interference({**wheels,**moving},tol=.5,skip=lambda a,b:((a in moving)==(b in moving)))
        checks_motion.append(dict(t=r['t'],stationary_clearance=a,upper_roller_contact=b))
        print('Motion geometry',r['t'],'s',len(a['hits']),len(b['hits']),'hits',flush=True)
    service=[]
    for x,z,g in s.AXES:
        # Chain opened and removed; front retention undone before sliding wheel off.
        wheel={n:d for n,d in inst.items() if d['group']==g or n.startswith(f'spacer_{g}_') or n.startswith(f'J7_end_spacer_{g}_')}
        fixed_service={n:d for n,d in inst.items() if d['group'] not in ['track','outer_plate','outer_fasteners'] and n not in wheel and n!='J711_one_piece_track_housing' and not n.startswith('J7_cover_M3x10')}
        samples=[]
        for y in [0,1,5,15,35,65]:
            moving={n:{**d,'shape':d['shape'].translate((0,y,0))} for n,d in wheel.items()}
            samples.append(dict(withdrawal_mm=y,**checks.interference({**fixed_service,**moving},skip=lambda a,b:((a in moving)==(b in moving)))))
        service.append(dict(wheel=g,samples=samples))
    ok=all(not r[k]['hits'] for r in checks_motion for k in ['stationary_clearance','upper_roller_contact']) and all(not a['hits'] for r in service for a in r['samples'])
    report=dict(pass_=ok,motion_samples=checks_motion,roller_service=service,elapsed_s=round(time.time()-start,1),
        scope='15 sampled poses from the unchanged J6 moving-geometry trace. Stationary interference limit 0.01 mm3; moving roller/chain contact overlap allowance 0.5 mm3. Six wheel withdrawal positions with chain, housing, outer plate and eight outer screws removed. Not a continuous sweep or load/strength proof.')
    report['pass']=report.pop('pass_');(s.ROOT/'motion_geometry_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'pass':ok,'elapsed_s':report['elapsed_s']},indent=2));assert ok

if __name__=='__main__':main()

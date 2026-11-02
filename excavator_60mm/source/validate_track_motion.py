"""Check actual CAD shoe articulation and wheel clearances at simulated poses.

This samples a tooth period in both directions. A small contact-volume allowance
covers the soft contact solver and the lower-resolution sprocket contact mesh;
it is not a continuous collision proof.
"""
import argparse,json,math,time,hashlib
import numpy as np
from build_vehicle import printable_parts,one,track_link_shape
from design import ROOT,AXLE_Z,APOTHEM,CENTRES,ROAD_ROLLERS,RETURN_ROLLERS,RETURN_Z,TRACK_LINKS
import tw_design as tw


def run(case):
    start=time.time();parts=printable_parts();shoe=track_link_shape(parts)
    failures=[];maximum={};checks=0;floor_penetration=0.
    for name in [case]:
        trace_bytes=(ROOT/f'simulation/{name}_trace.json').read_bytes()
        trace=json.loads(trace_bytes)
        # Allow for speed droop under ground load when covering a 30-degree tooth period.
        span=.36 if name=='track_ground' else .34
        for index in [round(t/.02) for t in np.r_[np.linspace(5,5+span,9),np.linspace(24,24+span,9)]]:
            sample=trace[index];placed=[]
            for p,q in zip(sample['points'],sample['quaternions']):
                axis=np.asarray(q[1:]);length=np.linalg.norm(axis)
                oriented=shoe if length<1e-12 else shoe.rotate((0,0,0),tuple(axis/length),math.degrees(2*math.atan2(length,q[0])))
                placed.append(oriented.translate(tuple(1000*np.array(p))))
            # Track R5: sprocket hub and hub cap turn together about the drive axis (unit frame).
            hub=lambda n:parts[n]['shape'].rotate((tw.DRIVE_X,0,AXLE_Z),(tw.DRIVE_X,1,AXLE_Z),math.degrees(sample['angle']))
            wheels=[('sprocket',hub('TW02_sprocket_hub')),('hub_cap',hub('TW03_hub_cap')),
                ('idler',parts['07_idler_wheel']['shape'].translate((CENTRES/2+sample['idler_mm'],0,AXLE_Z)))]
            wheels += [('road'+str(i),parts['08_road_roller']['shape'].translate((x,0,29))) for i,x in enumerate(ROAD_ROLLERS)]
            wheels += [('return'+str(i),parts['24_return_roller']['shape'].translate((x,0,RETURN_Z))) for i,x in enumerate(RETURN_ROLLERS)]
            bounds={n:one(s).BoundingBox() for n,s in wheels}
            for i,s in enumerate(placed):
                candidates=[('adjacent',placed[(i+1)%TRACK_LINKS])]+wheels
                a=one(s).BoundingBox()
                if name=='track_ground':
                    depth=max(0.,-a.zmin-1000*sample['frame'][2])
                    floor_penetration=max(floor_penetration,depth)
                    if depth>.1:failures.append(dict(case=name,time=sample['t'],shoe=i,other='floor',penetration_mm=depth))
                for n,other in candidates:
                    b=one(other).BoundingBox() if n=='adjacent' else bounds[n]
                    if any(getattr(a,k+'max')<=getattr(b,k+'min') or getattr(b,k+'max')<=getattr(a,k+'min') for k in 'xyz'):continue
                    volume=sum(v.Volume() for v in s.intersect(other).solids().vals());checks+=1
                    maximum[n]=max(maximum.get(n,0),volume)
                    if volume>.5:failures.append(dict(case=name,time=sample['t'],shoe=i,other=n,overlap_mm3=volume))
            print(name,round(sample['t'],2),'checks',checks,'failures',len(failures),flush=True)
    result=dict(status='PASS' if not failures else 'FAIL',sampled_poses=18,exact_intersections=checks,
        trace_sha256=hashlib.sha256(trace_bytes).hexdigest(),
        maximum_overlap_mm3=maximum,contact_volume_tolerance_mm3=.5,
        max_floor_penetration_mm=floor_penetration,floor_contact_tolerance_mm=.1,
        failures=failures,elapsed_seconds=time.time()-start,
        scope='Actual CAD shoes, steel bushings, pins and clips against adjacent links, the R5 sprocket hub and hub cap, idler and rollers at 18 poses per test across forward/reverse tooth periods. Wheel bearing holes retained. No rail/frame sweep or continuous collision proof. 0.5 mm3 contact-volume tolerance covers numerical soft contact and sprocket mesh approximation.')
    (ROOT/f'simulation/{case}_cad_motion.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2));return not failures

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case',choices=['track','track_ground','all'],default='all')
    args=parser.parse_args();cases=['track','track_ground'] if args.case=='all' else [args.case]
    results=[run(case) for case in cases]
    raise SystemExit(0 if all(results) else 1)

"""Diagnostic full assembly BREP intersection sweep, excluding no part pairs."""
from build_vehicle import *

def intersections(items):
    boxes={n:one(d['shape']).BoundingBox() for n,d in items.items()};hits=[];count=0
    for i,(n,d) in enumerate(items.items()):
        for m,e in list(items.items())[i+1:]:
            a,b=boxes[n],boxes[m]
            if any(getattr(a,k+'max')<=getattr(b,k+'min')+1e-5 or getattr(b,k+'max')<=getattr(a,k+'min')+1e-5 for k in 'xyz'):continue
            v=sum(s.Volume() for s in d['shape'].intersect(e['shape']).solids().vals());count+=1
            if v>.05:
                hits.append([n,m,round(v,3)]);print(hits[-1],flush=True)
    return hits,count

if __name__=='__main__':
    p=printable_parts();items=vehicle_instances(p)
    hits,count=intersections(items)
    (ROOT/'simulation/assembly_intersections.json').write_text(json.dumps(dict(intersections=hits,booleans=count),indent=2))
    print('TOTAL',len(hits),'/',count,flush=True)

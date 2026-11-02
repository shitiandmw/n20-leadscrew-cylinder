"""Measure the requested deeper middle and tapered ends independently of mesh rendering."""
from pathlib import Path
import hashlib,json
import numpy as np
from shapely.geometry import Point,LineString
from shapely.ops import unary_union
from kinematics import *

ROOT=Path(__file__).resolve().parents[1]
def profile(points,radii):
    circles=[Point(p).buffer(r,quad_segs=32) for p,r in zip(points,radii)]
    return unary_union([unary_union([a,b]).convex_hull for a,b in zip(circles,circles[1:])]).buffer(0)

def height(poly,x):
    b=poly.intersection(LineString([(x,-300),(x,300)])).bounds
    return b[3]-b[1]

def main():
    old=profile([(0,0),(72,54.4),(136,76),(184,68),(380,0)],[18,20,24,20,16])
    new=profile(BOOM_PROFILE_POINTS,BOOM_PROFILE_RADII)
    stations=[0,75,142,205,300,380]
    table=[dict(x_mm=x,r9_vertical_section_mm=height(old,x),r10_vertical_section_mm=height(new,x)) for x in stations]
    assert new.is_valid and new.geom_type=='Polygon'
    assert height(new,142)>1.4*height(old,142)
    assert height(new,142)>height(new,75)>height(new,0)
    assert height(new,142)>height(new,205)>height(new,300)>height(new,380)
    assert ACTUATORS['boom']['quantity']==2 and ACTUATORS['boom']['y']==[-50.,50.]
    assert sum(a['quantity'] for a in ACTUATORS.values())==4
    report=dict(status='PASS',revision=10,stations=table,boom_half_width_mm=24,nominal_wall_mm=4,paired_boom_y_mm=ACTUATORS['boom']['y'],actuator_count=4,reference='User photograph establishes topology and silhouette; no measured CAT 390D dimensions claimed',scope='Vertical side-profile depth measured in boom-local X/Z, excluding added clevises; not wall-thickness or strength verification',source_sha256=hashlib.sha256(Path(__file__).with_name('kinematics.py').read_bytes()).hexdigest())
    (ROOT/'shape_revision.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()

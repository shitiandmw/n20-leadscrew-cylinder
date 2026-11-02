"""J8: continuous opposing side plates based on the user's side-frame photo.

The five roller axles retain double-sided support. Broad uninterrupted webs
replace the narrow J7 bracket outline. Drive and idler retain their own bearings.
"""
import sys
from pathlib import Path
from functools import lru_cache
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent
sys.path.insert(0,str(ROOT/'source/support'))
import j7_parts as j7
from shapely.geometry import Point,LineString,box as rect
from shapely.ops import unary_union
j7.parts=lru_cache(maxsize=1)(j7.parts)
j6,j5,j4,j3,j2,p=j7.j6,j7.j5,j7.j4,j7.j3,j7.j2,j7.p
DX,DZ=j7.DX,j7.DZ
AXES,TIES,COVER_HOLES=j7.AXES,j7.TIES,j7.COVER_HOLES
RETURN_R,RETURN_Z=j7.RETURN_R,j7.RETURN_Z
INNER_Y,OUTER_Y=j7.INNER_Y,j7.OUTER_Y
# Idler axle centres at the retained rear/forward mechanical stops.
IDLER_LIMITS=(p.IDLER_X+p.YOKE_STOP_X-p.YOKE_X[0],p.IDLER_X+p.NOSE_BLOCK_X[0]-p.YOKE_X[1])

def side_profile():
    # Front end stays inside the return envelope at maximum idler recoil.
    end=IDLER_LIMITS[0]
    shapes=[rect(DX,24,end,75.2),Point(DX,DZ).buffer(31,resolution=48),Point(end,DZ).buffer(31,resolution=48)]
    # Lower mounting lobes blend directly into the continuous side wall.
    for x,z,g in AXES:shapes.append(Point(x,z).buffer(10,resolution=32))
    return unary_union(shapes)

def idler_opening():
    # Clearance for the retained moving collar, not a new fixed idler bearing.
    return LineString([(x,DZ) for x in IDLER_LIMITS]).buffer(8.8,resolution=48)

def inner_profile():
    return side_profile().difference(Point(DX,DZ).buffer(33.8,resolution=64)).difference(idler_opening())

def frame():
    q=j5.frame().union(p.xz_prism(inner_profile(),-30,-28))
    for x,z,g in AXES:
        q=q.union(p.ycyl(9.8,-42,-28,x,z))
        pocket=p.ycyl(6.2,-43,-27.8,x,z).intersect(p.box(x-7,x+7,-44,-27,z-7,z+4.5))
        q=q.cut(pocket)
    for x,z in TIES:
        q=q.cut(p.ycyl(2.15,-46,-27,x,z)).cut(p.ycyl(4.8,-43.2,-41.9,x,z)).cut(p.ycyl(3.8,-46,-42.9,x,z))
    return q.clean()

def plate(outer=False):
    a,b=OUTER_Y if outer else INNER_Y
    profile=side_profile().difference(idler_opening()) if outer else inner_profile()
    q=p.xz_prism(profile,a,b)
    if outer:
        # Original drive screw heads reach Y23.65. A 1 mm rear relief gives
        # 1.35 mm nominal clearance without moving the outer face beyond Y28.
        q=q.cut(p.ycyl(33.8,23,25,DX,DZ))
        q=q.cut(p.ycyl(6,23,29,DX,DZ))
    for x,z,g in AXES:
        q=q.cut(p.ycyl(4.025,a-1,b+1,x,z))
        if outer:q=q.cut(j2.j1.cone(2.5,5,25.5,28,x,z))
    for x,z in TIES:
        q=q.cut(p.ycyl(2.15,a-1,b+1,x,z))
        if outer:q=q.cut(j2.j1.cone(2,4,26,28,x,z))
    return q.clean()

def parts():
    out={n:d for n,d in j7.parts().items() if n not in ['J706_bracket_support_frame','J715_inner_bracket_plate','J716_outer_bracket_plate']}
    out['J806_continuous_support_frame']=dict(shape=frame(),kind='printed',material='PA12 preferred',quantity=1,
        note='Full continuous inner-cheek seat; motor/chassis interfaces and axle-head service pockets retained.',color=(.55,.64,.64))
    out['J815_inner_continuous_side_plate']=dict(shape=plate(),kind='machined',material='6061-T6 aluminum, 4 mm plate',quantity=1,
        note='Continuous structural web; five matched roller axle bores; drive clearance and idler travel opening.',color=(.55,.64,.67))
    out['J816_outer_continuous_side_plate']=dict(shape=plate(True),kind='machined',material='6061-T6 aluminum, 4 mm plate; 3 mm locally over drive',quantity=1,
        note='Full-length removable structural side plate; broad web; drive access hole and free idler travel opening. Flush original J7 fasteners.',color=(.55,.64,.67))
    return out

def unit(new):
    inst=j7.unit(j7.parts())
    for old,n,g in [('J706_bracket_support_frame','J806_continuous_support_frame','frame'),('J715_inner_bracket_plate','J815_inner_continuous_side_plate','inner_plate'),('J716_outer_bracket_plate','J816_outer_continuous_side_plate','outer_plate')]:
        inst.pop(old);inst[n]={**new[n],'group':g,'source':n}
    return inst

def bracket_items(inst):return j7.bracket_items(inst)

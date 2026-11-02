"""J7: two structural cheek plates supporting both ends of all five roller axles.

All dimensions in mm. Two 4 mm aluminium plates and three steel cross ties
form a detachable roller bracket. The one-piece outer protection stays separate.
"""
import sys
from functools import lru_cache
from pathlib import Path
from support_paths import ROOT, REPO
import j6_parts as j6
import cadquery as cq
from shapely.geometry import Point,LineString,box as rect
from shapely.ops import unary_union
j5,j4,j3,j2,p=j6.j5,j6.j4,j6.j3,j6.j2,j6.p
# Reuse immutable baseline parts within each build/check process.
j5.parts=lru_cache(maxsize=1)(j5.parts)
j6.parts=lru_cache(maxsize=1)(j6.parts)
DX,DZ=j6.DX,j6.DZ
AXES=j6.AXES;RETURN_R=j6.RETURN_R;RETURN_Z=j6.RETURN_Z
TIES=[(-63.,61.5),(0.,55.5),(63.,61.5)]
INNER_Y=(-28.,-24.);OUTER_Y=(24.,28.)
COVER_HOLES=j6.COVER_HOLES

def bracket_profile():
    shapes=[rect(-63,43,63,56)]
    for x,z,g in AXES:
        shapes += [Point(x,z).buffer(10,resolution=32),rect(x-6,min(z,49),x+6,max(z,49))]
    for x,z in TIES:
        shapes += [Point(x,z).buffer(6,resolution=32),rect(x-6,49,x+6,z)]
    return unary_union(shapes)

def frame():
    s=j5.frame()
    # The metal inner plate seats on a continuous plane at Y=-28.
    s=s.union(p.xz_prism(bracket_profile(),-30,-28))
    for x,z,g in AXES:
        # Keep the true cylinder inside the polygonal seat outline to avoid
        # tangent sliver faces at their common surface.
        s=s.union(p.ycyl(9.8,-42,-28,x,z))
        # Access pocket; the axle is located in the metal plates, not this bore.
        pocket=p.ycyl(6.2,-43,-27.8,x,z).intersect(p.box(x-7,x+7,-44,-27,z-7,z+4.5))
        s=s.cut(pocket)
    for x,z in TIES:
        s=s.cut(p.ycyl(2.15,-46,-27,x,z))
        s=s.cut(p.ycyl(4.8,-43.2,-41.9,x,z)).cut(p.ycyl(3.8,-46,-42.9,x,z))
    return s.clean()

def plate(outer=False):
    a,b=OUTER_Y if outer else INNER_Y
    s=p.xz_prism(bracket_profile(),a,b)
    for x,z,g in AXES:
        s=s.cut(p.ycyl(4.025,a-1,b+1,x,z))
        if outer:s=s.cut(j2.j1.cone(2.5,5,25.5,28,x,z))
    for x,z in TIES:
        s=s.cut(p.ycyl(2.15,a-1,b+1,x,z))
        if outer:s=s.cut(j2.j1.cone(2,4,26,28,x,z))
    return s.clean()

def axle():
    s=p.ycyl(4,-28,26.5).union(p.ycyl(6,-30.5,-28))
    # Flat faces upward: it keys the head and clears the retained motor/beam
    # during inboard axle withdrawal.
    s=s.cut(p.box(-7,7,-31,-27.99,4.3,7))
    # M5 blind thread plus a matching countersink mouth; screw head is flush at Y28.
    s=s.cut(p.ycyl(2.5,14,27)).cut(j2.j1.cone(2.5,5,25.5,28,0,0))
    # Rear 4 mm hex counterhold, reached through the frame access pocket.
    socket=cq.Workplane('XZ').polygon(6,8/(3**.5)).extrude(1.5).translate((0,-29,0))
    return s.cut(socket).clean()

def tie():
    return p.ycyl(4,-24,24).cut(p.ycyl(2,-25,-14)).cut(p.ycyl(2,14,25)).clean()

def csk(x,z,r,top,length):
    # 90 degree countersunk fastener; length includes its head.
    return p.ycyl(r,top-length,top-r,x,z).union(j2.j1.cone(r,2*r,top-r,top,x,z)).cut(
        cq.Workplane('XZ').center(x,z).polygon(6,(3 if r==2.5 else 2.5)*2/(3**.5)).extrude(1.5).translate((0,top+.01,0)))

def housing():
    s=j6.housing()
    for x,z in TIES:
        s=s.cut(p.ycyl(4.9,-43.3,-41,x,z)).cut(p.ycyl(3.9,-46,-41,x,z))
    return s.clean()

def parts():
    out={n:d for n,d in j6.parts().items() if n not in ['J606_continuous_boss_frame','J611_one_piece_track_housing','J621_stepped_roller_axle']}
    def add(n,shape,kind,material,qty,note,color):out[n]=dict(shape=shape,kind=kind,material=material,quantity=qty,note=note,color=color)
    add('J706_bracket_support_frame',frame(),'printed','PA12 preferred',1,'Continuous seat for metal inner cheek; five axle-head access pockets; three bracket mounting holes.',(.55,.64,.64))
    add('J711_one_piece_track_housing',housing(),'printed','PA12 preferred',1,'One continuous motor-to-idler protective housing; retained seven-screw service interface.',(.75,.79,.77))
    add('J715_inner_bracket_plate',plate(),'machined','6061-T6 aluminium, 4 mm plate',1,'Inner structural cheek, Y=-28 to -24. Five 8.05 mm axle holes. Machine/ream as a matched pair.',(.56,.65,.68))
    add('J716_outer_bracket_plate',plate(True),'machined','6061-T6 aluminium, 4 mm plate',1,'Outer removable structural cheek, Y=24 to 28. Five axle seats and flush M5 retention; three tie screws.',(.23,.43,.48))
    add('J721_supported_roller_axle',axle(),'machined','C45 steel, ground 8 mm journal',5,'Through axle supported by both metal cheeks. Integral rear head and M5 blind-thread/countersink at front.',p.STEEL)
    add('J722_bracket_cross_tie',tie(),'machined','Steel, OD8 x 48 mm',3,'Metal spacing tie with M4 blind threads at both ends; separates plate inner faces by 48 mm.',p.STEEL)
    add('J723_roller_end_spacer',p.yring(6,4.05,0,4),'machined','Steel, OD12 / ID8.1 x 4 mm',10,'One at each end of each wheel; transfers axial clamp through bearing inner rings.',p.STEEL)
    return out

def unit(new):
    base=j6.unit(j6.parts())
    remove=['J606_continuous_boss_frame','J611_one_piece_track_housing']
    base={n:d for n,d in base.items() if n not in remove and not n.startswith(('J6_axle_','J6_rear_','J6_front_','J6_cover_'))}
    for n,d in new.items():
        if n in ['J624_compact_return_roller','J721_supported_roller_axle','J722_bracket_cross_tie','J723_roller_end_spacer']:continue
        group='outer_plate' if n=='J716_outer_bracket_plate' else 'inner_plate' if n=='J715_inner_bracket_plate' else 'drive' if n in ['J03_hex_drive_cap','J10_torque_spindle'] else 'frame'
        base[n]={**d,'group':group,'source':n}
    def hw(n,shape,group='frame',color=p.STEEL,source=None):base[n]=dict(shape=shape,group=group,kind='hardware',color=color,source=source)
    for x,z,g in AXES:
        base.pop(f'spacer_{g}_2')
        hw(f'J7_through_axle_{g}',new['J721_supported_roller_axle']['shape'].translate((x,0,z)),'axles',source='J721_supported_roller_axle')
        for i,a in enumerate([-24.,20.]):hw(f'J7_end_spacer_{g}_{i}',new['J723_roller_end_spacer']['shape'].translate((x,a,z)),'axles',source='J723_roller_end_spacer')
        hw(f'J7_outer_axle_M5x12_{g}',csk(x,z,2.5,28,12),'outer_fasteners',p.BLACK)
    for i,(x,z) in enumerate(TIES):
        hw(f'J7_cross_tie_{i}',new['J722_bracket_cross_tie']['shape'].translate((x,0,z)),'ties',source='J722_bracket_cross_tie')
        hw(f'J7_inner_tie_M4x25_{i}',j6.socket_screw(x,z,-43,25,False),'frame',p.BLACK)
        hw(f'J7_inner_tie_washer_{i}',p.yring(4.5,2.15,-43,-42,x,z))
        hw(f'J7_outer_tie_M4x10_{i}',csk(x,z,2,28,10),'outer_fasteners',p.BLACK)
    for i,(x,z) in enumerate(COVER_HOLES):
        hw(f'J7_cover_M3x10_{i}',j2.j1.csk_screw(x,z,-73,10),'frame',p.BLACK)
        hw(f'J7_cover_insert_{i}',p.yring(2,1.5,-68.8,-63.1,x,z),'frame',p.BRASS)
    return base

def bracket_items(inst):
    return {n:d for n,d in inst.items() if d['group'] in ['inner_plate','outer_plate','outer_fasteners','axles','ties','roller0','roller1','roller2','return0','return1'] or n.startswith('spacer_') and not n.startswith('spacer_idler')}

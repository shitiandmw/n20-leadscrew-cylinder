"""J6: continuous reinforced rail and compact positively retained roller axles.

Millimetres. The exterior protection stays one removable body. Wheel loads go
through the reinforced rail, not the thin protective skin. Prototype geometry.
"""
import sys
from pathlib import Path
from support_paths import ROOT, REPO
import j5_parts as j5
import cadquery as cq
from shapely.geometry import LineString
j4,j3,j2,p=j5.j4,j5.j3,j5.j2,j5.p
DX,DZ=j5.DX,j5.DZ
RETURN_R=15.
RETURN_Z=p.RETURN_Z+(p.ex.RETURN_ROLLER_R-RETURN_R)
AXES=[(x,29.,f'roller{i}') for i,x in enumerate(p.ex.ROAD_ROLLERS)]+[(x,RETURN_Z,f'return{i}') for i,x in enumerate(p.ex.RETURN_ROLLERS)]
BOSS_R=10.5
ROOT_BORE_R=6.025
COVER_HOLES=j5.COVER_HOLES
FRAME_COLOR=(.64,.70,.70)
SHELL_COLOR=(.75,.79,.77)

def frame():
    s=j5.frame()
    # Fill former upper axle holes before moving their centres.
    for x in p.ex.RETURN_ROLLERS:
        s=s.union(p.ycyl(4.2,-42,-30,x,p.RETURN_Z))
    # A continuous web replaces five long exposed inboard spacer stacks.
    s=s.union(p.box(-63,63,-30,-25,25,69.3))
    for x,z,g in AXES:
        s=s.union(p.ycyl(BOSS_R,-42,-21,x,z))
        s=s.cut(p.ycyl(ROOT_BORE_R,-43,-20,x,z))
    return s.clean()

def return_roller():
    G=p.ex;R=RETURN_R
    s=p.yring(13,6.2,-20,20)
    for a,b in [(-20,-15),(15,20)]:s=s.union(p.yring(R,6.2,a,b))
    for sign in [-1,1]:
        a,b=sorted([sign*20,sign*G.GUIDE_OUTER_Y]);s=s.union(p.yring(R,11.1,a,b))
        a,b=sorted([sign*G.GUIDE_INNER_Y,sign*G.GUIDE_OUTER_Y]);s=s.union(p.yring(R+G.GUIDE_HEIGHT,11.1,a,b))
    return s.cut(p.ycyl(11.1,-24,-13)).cut(p.ycyl(11.1,13,24)).clean()

def axle():
    # Rear M4 screw clamps the printed root between a broad washer and the
    # integral shoulder. Front M4 screw clamps only the metal inner-ring stack.
    # Root is recessed 0.2 mm at the rear; journal end is recessed 0.2 mm at front.
    s=p.ycyl(6,-41.8,-21).union(p.ycyl(8,-21,-20.5))
    s=s.union(p.ycyl(6,-20.5,-20)).union(p.ycyl(4,-20,20.8))
    s=s.cut(p.ycyl(2,-42,-34)).cut(p.ycyl(2,13,21))
    return s.clean()

def socket_screw(x,z,face,length,outward):
    s=p.screw(2,3.5,2.5,face,length,x,z,outward=outward)
    # Nominal low-head M4 socket, major-diameter shank and simplified threads.
    a,b=(face+1,face+3) if outward else (face-3,face-1)
    cut=cq.Workplane('XZ').center(x,z).polygon(6,3*2/(3**.5)).extrude(b-a).translate((0,b,0))
    return s.cut(cut)

def housing():
    outer=j5.profile();inner=outer.buffer(-2.5)
    s=p.xz_prism(outer,-73,-42.3).cut(p.xz_prism(inner,-70.5,-41.8))
    s=s.cut(p.xcyl(12.8,DX+30.5,DX+63.3,-59.2,DZ))
    for x in j2.MOUNT_X:s=s.cut(p.box(x-15.3,x+15.3,-60.3,-41,63.7,71))
    s=s.cut(p.box(130.7,137.3,-51.3,-41,65.3,71))
    s=s.cut(p.box(132,136,-50,-41,23,27.3))
    s=s.cut(p.ycyl(31.3,-44.3,-41,DX,DZ))
    for x,z,g in AXES:
        s=s.cut(p.ycyl(3.9,-46,-41,x,z)).cut(p.ycyl(9.3,-43.2,-41,x,z))
    s=s.cut(p.box(-23,-15,-64,-41,60,71))
    for x in [-108.,-96.,5.,80.,136.]:s=s.cut(p.box(x-3,x+3,-66,-60,17,29))
    for z in [37.5,43.5,49.5,55.5]:
        s=s.cut(p.xz_prism(LineString([(-76,z),(-56.5,z)]).buffer(1.25,resolution=12),-74,-69.5))
    for x,z in COVER_HOLES:
        s=s.union(p.ycyl(4,-73,-69,x,z)).cut(p.ycyl(3.75,-69,-41,x,z))
        s=s.cut(p.ycyl(1.7,-74,-68.9,x,z)).cut(j2.j1.cone(3,1.7,-73,-71.7,x,z))
    return s.clean()

def parts():
    out={n:d for n,d in j5.parts().items() if n not in ['J506_internal_support_rail','J511_one_piece_track_housing']}
    out['J606_continuous_boss_frame']=dict(shape=frame(),material='PA12 preferred; finish axle bores',kind='printed',color=FRAME_COLOR,quantity=1,
        note='Continuous web and five integral 21 mm deep axle bosses. Diameter 12.05 nominal root bores; finish to selected fit.')
    out['J611_one_piece_track_housing']=dict(shape=housing(),material='PA12 preferred',kind='printed',color=SHELL_COLOR,quantity=1,
        note='One motor-to-idler exterior housing. Seven removable screws. Revised small axle-head reliefs.')
    out['J624_compact_return_roller']=dict(shape=return_roller(),material='PA12 or tough PETG',kind='printed',color=p.DARK,quantity=2,
        note='30 mm running diameter; 34 mm guide flanges; two 608 bearings. Axis raised by 1.5 mm.')
    out['J621_stepped_roller_axle']=dict(shape=axle(),material='C45 steel; finish bearing journals',kind='machined',color=p.STEEL,quantity=5,
        note='12 mm root, 8 mm journal, relieved integral shoulder; M4 blind threads at both ends. Thread geometry simplified.')
    return out

def unit(new):
    base=j5.unit(j5.parts())
    removed=['J506_internal_support_rail','J511_one_piece_track_housing']
    base={n:d for n,d in base.items() if n not in removed and not n.startswith('J5_cover_')}
    # Shared wheel/axle definitions are not extra origin instances.
    for n,d in new.items():
        if n in ['J624_compact_return_roller','J621_stepped_roller_axle']:continue
        base[n]={**d,'group':'drive' if n in ['J03_hex_drive_cap','J10_torque_spindle'] else 'frame','source':n}
    def hw(n,shape,color=p.STEEL):base[n]=dict(shape=shape,color=color,kind='hardware',group='frame',source=None)
    for x,z,g in AXES:
        for n in [f'axle_{g}',f'collar_{g}_0',f'collar_{g}_1',f'spacer_{g}_0']:base.pop(n)
        hw(f'J6_axle_{g}',new['J621_stepped_roller_axle']['shape'].translate((x,0,z)))
        hw(f'J6_rear_washer_{g}',p.yring(9,2.15,-43,-42,x,z))
        hw(f'J6_rear_M4x8_{g}',socket_screw(x,z,-43,8,False),p.BLACK)
        hw(f'J6_front_washer_{g}',p.yring(6,2.15,21,22,x,z))
        hw(f'J6_front_M4x8_{g}',socket_screw(x,z,22,8,True),p.BLACK)
        if g.startswith('return'):
            i=int(g[-1]);base.pop(f'24_return_roller_{i}')
            base[f'J624_compact_return_roller_{i}']={**new['J624_compact_return_roller'],'shape':new['J624_compact_return_roller']['shape'].translate((x,0,z)),'source':'J624_compact_return_roller','group':g}
            for n,d in base.items():
                if n.startswith((f'608_{g}_',f'spacer_{g}_')):d['shape']=d['shape'].translate((0,0,RETURN_Z-p.RETURN_Z))
    for i,(x,z) in enumerate(COVER_HOLES):
        hw(f'J6_cover_M3x10_{i}',j2.j1.csk_screw(x,z,-73,10),p.BLACK)
        hw(f'J6_cover_insert_{i}',p.yring(2,1.5,-68.8,-63.1,x,z),p.BRASS)
    return base

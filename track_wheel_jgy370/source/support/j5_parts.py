"""J5: a full-length, one-piece outer track housing, millimetres.

The motor shroud and right-hand guard walls are one printed body. The internal
bearing rail and moving tensioner remain independent of the removable housing.
"""
import sys
from pathlib import Path
from support_paths import ROOT, REPO
import j4_parts as j4
import cadquery as cq
from shapely.geometry import Polygon,LineString
j3,j2,p=j4.j3,j4.j2,j4.p
DX,DZ=j4.DX,j4.DZ
COVER_HOLES=j4.COVER_HOLES+[(5.,46.),(144.1,37.),(144.1,56.)]

def profile():
    extension=Polygon([(-110,24),(142.2,24),(149.5,31.3),(149.5,60),
                       (140.2,69.3),(-110,69.3)])
    return j2.profile().union(extension)

def frame():
    s=j4.frame()
    for x,z in COVER_HOLES[4:]:
        s=s.union(p.ycyl(3.5,-69,-34.5,x,z))
        s=s.cut(p.ycyl(2,-69.1,-63,x,z)).cut(p.ycyl(1.7,-63.1,-61.5,x,z))
    return s.clean()

def housing():
    outer=profile();inner=outer.buffer(-2.5)
    s=p.xz_prism(outer,-73,-42.3).cut(p.xz_prism(inner,-70.5,-41.8))
    s=s.cut(p.xcyl(12.8,DX+30.5,DX+63.3,-59.2,DZ))
    # Back-open scallops preserve the three existing chassis pads and collars.
    for x in j2.MOUNT_X:
        s=s.cut(p.box(x-15.3,x+15.3,-60.3,-41,63.7,71))
    # A back-open roof notch clears both retained tensioner-stop screw heads.
    s=s.cut(p.box(130.7,137.3,-51.3,-41,65.3,71))
    # The inner stop screw also projects 1 mm below the original channel floor.
    s=s.cut(p.box(132,136,-50,-41,23,27.3))
    s=s.cut(p.ycyl(31.3,-44.3,-41,DX,DZ))
    for x,z in [(x,29) for x in p.ex.ROAD_ROLLERS]+[(x,p.RETURN_Z) for x in p.ex.RETURN_ROLLERS]:
        s=s.cut(p.ycyl(4.6,-54.3,-41,x,z)).cut(p.ycyl(8.7,-47.8,-41,x,z))
    # The cable route exits the open back; no separate right-hand end panel.
    s=s.cut(p.box(-23,-15,-64,-41,60,71))
    for x in [-108.,-96.,5.,80.,136.]:
        s=s.cut(p.box(x-3,x+3,-66,-60,17,29))
    for z in [37.5,43.5,49.5,55.5]:
        s=s.cut(p.xz_prism(LineString([(-76,z),(-56.5,z)]).buffer(1.25,resolution=12),-74,-69.5))
    for x,z in COVER_HOLES:
        s=s.union(p.ycyl(4,-73,-69,x,z))
        s=s.cut(p.ycyl(3.75,-69,-41,x,z))
        s=s.cut(p.ycyl(1.7,-74,-68.9,x,z)).cut(j2.j1.cone(3,1.7,-73,-71.7,x,z))
    return s.clean()

def parts():
    out={n:d for n,d in j4.parts().items() if n not in ['J406_serviceable_track_frame','J411_one_piece_protective_shell']}
    out['J506_internal_support_rail']=dict(shape=frame(),material='PA12 preferred',kind='printed',
        note='Original rail and chassis pads; seven integral hidden housing supports.',color=j2.FRAME_COLOR,quantity=1)
    out['J511_one_piece_track_housing']=dict(shape=housing(),material='PA12 preferred; PETG fit prototype',kind='printed',
        note='One continuous motor-to-idler outer housing, including all right-hand guard walls. 2.5 mm nominal wall; local 1 mm can relief.',color=j2.COVER_COLOR,quantity=1)
    return out

def unit(new):
    base=j4.unit(new)
    base={n:d for n,d in base.items() if n not in ['J406_serviceable_track_frame','J411_one_piece_protective_shell'] and not n.startswith('J4_cover_')}
    for n,d in new.items():base[n]={**d,'group':'drive' if n in ['J03_hex_drive_cap','J10_torque_spindle'] else 'frame','source':n}
    for i,(x,z) in enumerate(COVER_HOLES):
        base[f'J5_cover_M3x10_{i}']=dict(shape=j2.j1.csk_screw(x,z,-73,10),group='frame',kind='hardware',color=p.BLACK,source=None)
        base[f'J5_cover_insert_{i}']=dict(shape=p.yring(2,1.5,-68.8,-63.1,x,z),group='frame',kind='hardware',color=p.BRASS,source=None)
    return base

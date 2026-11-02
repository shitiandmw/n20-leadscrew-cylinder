"""Cat 320 reference-based arm: shaped closed boxes, compact fixed pivot base,
paired external boom cylinders, central stick and bucket cylinders, inward scoop.
"""
from cad_common import *
from kinematics import *


def shape_chain(points,radii):
    return unary_union([unary_union([circle(*points[i],radii[i]),circle(*points[i+1],radii[i+1])]).convex_hull for i in range(len(points)-1)]).buffer(0)


def box_beam(profile,half_width,wall=4):
    return plate(profile,-half_width,half_width).cut(plate(profile.buffer(-wall),-half_width+wall,half_width-wall))


def structures():
    parts={}
    def add(n,s,g,color=YELLOW):parts[n]=dict(shape=s.clean(),group=g,color=color,kind='printed')
    base=box2(-55,110,0,12,-82,82)
    tower=unary_union([Polygon([(-28,12),(30,12),(18,110),(-18,110),(-28,98)]),circle(0,110,16)])
    for a,b in [(-35,-27),(27,35)]:base=base.union(holes(plate(tower,a,b),[(0,110)],3.1))
    base=base.union(box2(-26,-16,12,85,-27,27))
    base=base.union(box2(-20,24,12,24,-27,27))
    for cy in [-42,42]:
        lug=unary_union([Polygon([(55,12),(85,12),(81,65),(59,65)]),hull([(70,62),(70,75)],8)])
        for a,b in [(cy-13,cy-8),(cy+8,cy+13)]:base=base.union(holes(plate(lug,a,b),[GROUND_CYL],1.6))
        base=base.union(box2(55,85,12,22,cy-13,cy+13))
    for x in [-40,95]:
        for y in [-65,65]:base=base.cut(cq.Workplane('XY').center(x,y).circle(3.3).extrude(15))
    add('01_fixed_pivot_base',base,'base',DARK)
    profile=shape_chain([(0,0),(90,68),(170,95),(230,85),(BOOM,0)],[18,23,28,22,16])
    boom=box_beam(profile,24,4)
    # Root bearing tube and open distal fork, rather than full-height mounting plates.
    boom=boom.union(ycyl(0,0,11,-24,24))
    boom=boom.cut(box2(BOOM-70,BOOM+30,-60,60,-18,18))
    for a,b in [(-24,-18),(18,24)]:boom=boom.union(plate(hull([(BOOM-55,16),(BOOM,0)],16),a,b))
    boom=holes(boom,[(0,0),(BOOM,0)],3.1)
    # Two rod clevises outside the boom, connected above the incoming cylinder axes.
    bx,bz=BOOM_LIFT
    for cy in [-42,42]:
        a,b=sorted([24*np.sign(cy),cy+13*np.sign(cy)])
        boom=boom.union(box2(bx-11,bx+11,bz+11,bz+21,a,b))
        for y0,y1 in [(cy-13,cy-8),(cy+8,cy+13)]:boom=boom.union(holes(plate(hull([(bx,bz),(bx,bz+16)],7),y0,y1),[BOOM_LIFT],1.6))
    boom=holes(boom,[BOOM_LIFT],1.6)
    cx,cz=STICK_CYL
    boom=boom.union(box2(cx-12,cx+12,cz-26,cz-18,-24,24))
    for a,b in [(-13,-8),(8,13)]:boom=boom.union(holes(plate(hull([(cx,cz),(cx,cz-22)],7),a,b),[STICK_CYL],1.6))
    add('02_bent_box_boom',boom,'boom')
    sp=shape_chain([tuple(STICK_TAIL),(0,0),(105,0),(190,0),(STICK,0)],[12,20,17,14,14])
    stick=box_beam(sp,16,4)
    stick=stick.cut(box2(-100,-20,-80,80,-10,10))
    for a,b in [(-16,-10),(10,16)]:stick=stick.union(plate(hull([tuple(STICK_TAIL),(-21,4)],12),a,b))
    for x in [0,STICK]:stick=stick.union(ycyl(x,0,10,-16,16))
    stick=holes(stick,[(0,0),(STICK,0)],3.1)
    stick=holes(stick,[STICK_TAIL],1.6)
    fx,fz=BUCKET_CYL
    stick=stick.union(box2(fx-11,fx+11,fz-22,fz-14,-16,16))
    for a,b in [(-13,-8),(8,13)]:stick=stick.union(holes(plate(hull([(fx,fz),(fx,fz-18)],7),a,b),[BUCKET_CYL],1.6))
    # Small paired rocker bosses on the front face of the stick.
    jx,jz=ROCKER_PIVOT
    for a,b in [(-16,-10),(10,16)]:stick=stick.union(plate(hull([(jx,jz),(jx,3)],9),a,b))
    stick=holes(stick,[ROCKER_PIVOT],1.6)
    add('03_box_stick',stick,'stick')
    for side,a,b in [('left',18,24),('right',-24,-18)]:
        rocker=holes(plate(hull([(0,0),(ROCKER,0)],7),a,b),[(0,0),(ROCKER,0)],1.6)
        add('04_rocker_'+side,rocker,'rocker',YELLOW)
    for side,a,b in [('left',25,30),('right',-30,-25)]:
        s=holes(plate(hull([(0,0),(COUPLER,0)],6.5),a,b),[(0,0),(COUPLER,0)],1.6)
        add('05_bucket_link_'+side,s,'coupler',DARK)
    # Mouth and teeth face -X in the bucket's neutral frame (toward the excavator).
    back=[(-7,-22),(30,-24),(56,-42),(55,-73),(30,-96),(-28,-102),(-89,-77)]
    wall=LineString(back).buffer(2,cap_style=2,join_style=1)
    bucket=plate(wall,-BUCKET_WIDTH/2,BUCKET_WIDTH/2)
    for a,b in [(-50,-46.5),(46.5,50)]:bucket=bucket.union(plate(Polygon(back),a,b))
    horn=unary_union([hull([(0,0),tuple(HORN_POINT)],11),Polygon([(-10,-5),(-10,-30),(44,-30),(43,-7),(10,8)])]).buffer(0)
    for a,b in [(-24,-18),(18,24)]:bucket=bucket.union(holes(holes(plate(horn,a,b),[(0,0)],3.1),[HORN_POINT],1.6))
    tooth=[(-83,-78),(-90,-72),tuple(TIP),(-96,-79),(-88,-78)]
    for y in [-40,-20,0,20,40]:bucket=bucket.union(plate(tooth,y-3.5,y+3.5))
    # Three external wear strips follow the lower rear shell.
    wear=LineString([(54,-47),(53,-72),(29,-94),(-27,-100),(-73,-83)]).buffer(2.5,cap_style=2,join_style=1)
    for y in [-30,0,30]:bucket=bucket.union(plate(wear,y-3,y+3))
    add('06_inward_digging_bucket',bucket,'bucket',YELLOW)
    return parts


def hardware():
    out={}
    def add(n,s,g):out[n]=dict(shape=s,group=g,color=STEEL,kind='hardware')
    def pin(n,g,p,d,outer,cy=0):
        thick=4 if d==6 else 3;half=outer+thick+2
        add('pin_'+n,ycyl(*p,d/2,cy-half,cy+half),g)
        for sig in [-1,1]:
            a,b=sorted([cy+sig*(outer+.3),cy+sig*(outer+.3+thick)])
            add('collar_'+n+str(sig),ycyl(*p,5.5 if d==6 else 3.5,a,b).cut(ycyl(*p,d/2+.05,a-.1,b+.1)),g)
    def spacers(n,g,p,a,b,d=3,cy=0):
        for sig in [-1,1]:
            y0,y1=sorted([cy+sig*a,cy+sig*b]);add('spacer_'+n+str(sig),ycyl(*p,4.5 if d==6 else 3.5,y0,y1).cut(ycyl(*p,d/2+.1,y0-.1,y1+.1)),g)
    pin('O','base',(0,110),6,35);spacers('O','base',(0,110),24.1,26.9,6)
    pin('E','boom',(BOOM,0),6,24);spacers('E','boom',(BOOM,0),16.1,17.9,6)
    pin('H','stick',(STICK,0),6,24);spacers('H','stick',(STICK,0),16.1,17.9,6)
    for side,cy in [('L',-42),('R',42)]:
        for label,g,p in [('A','base',GROUND_CYL),('B','boom',BOOM_LIFT)]:
            pin(label+side,g,p,3,13,cy);spacers(label+side,g,p,3.1,7.9,3,cy)
    for n,g,p,outer,inside in [('C','boom',STICK_CYL,13,8),('D','stick',STICK_TAIL,16,10),('F','stick',BUCKET_CYL,13,8)]:
        pin(n,g,p,3,outer);spacers(n,g,p,3.1,inside-.1)
    pin('J','stick',ROCKER_PIVOT,3,24);spacers('J','stick',ROCKER_PIVOT,16.1,17.9)
    pin('R','rocker',(ROCKER,0),3,30);spacers('R_eye','rocker',(ROCKER,0),3.1,17.9);spacers('R_link','rocker',(ROCKER,0),24.1,24.9)
    pin('Q','bucket',HORN_POINT,3,30);spacers('Q_link','bucket',HORN_POINT,24.1,24.9)
    return out


def load_actuators():
    result={}
    import sys
    sys.path.insert(0,str(REPO/'actuator_v6/source'))
    import layout as L,design_v6 as D
    for role,v in ACTUATORS.items():
        L.VARIANTS[v['variant']]={'screw_length':v['screw'],'stroke':v['stroke']};d=L.derived(v['variant'])
        result[role]={'01_body':D.make_body(d),'02_front_cap':D.make_front_cap(d),'03_rear_cap':D.make_rear_cap(d),'04_rod':D.make_rod(d),'05_rod_eye':D.make_rod_eye(d)}
    return result


def actuator_instances():
    for index,(role,a,b) in enumerate([('boom','A','B'),('stick','C','D'),('bucket','F','R')]):
        for side,cy in enumerate(ACTUATORS[role]['y']):yield f'{role}{side}',role,index,a,b,cy


def placed_parts(parts,acts,strokes=None):
    st=solve(strokes);out={}
    for n,p in parts.items():out[n]=move(p['shape'],st['origins'][p['group']],st['angles'][p['group']])
    for label,role,i,a,b,cy in actuator_instances():
        for n,s in acts[role].items():out[label+'_V6_'+n]=actmove(s,st['points'][a],st['points'][b],st['strokes'][i],n.startswith(('04','05'))).translate((0,cy,0))
    return out


def export_all():
    start=time.time();parts=structures();parts.update(hardware());acts=load_actuators();items=[];report=[]
    for folder in ['step','stl','source','images']:(ROOT/folder).mkdir(exist_ok=True)
    for n,p in parts.items():
        s=p['shape'];assert one(s).isValid(),n
        items.append(dict(name=n,group=p['group'],color=p['color'],kind=p['kind'],**mesh(s)))
        if p['kind']!='printed':continue
        print('Export',n,flush=True);assert len(s.solids().vals())==1,(n,len(s.solids().vals()))
        cq.exporters.export(s,str(ROOT/'step'/f'{n}.step'))
        sp=s if p['group']=='base' else s.rotate((0,0,0),(1,0,0),90)
        bb=one(sp).BoundingBox();sp=sp.translate((-(bb.xmin+bb.xmax)/2,-(bb.ymin+bb.ymax)/2,-bb.zmin))
        dest=ROOT/'stl'/f'{n}.stl';cq.exporters.export(sp,str(dest),tolerance=.03,angularTolerance=.12)
        tm=trimesh.load_mesh(dest);tm.update_faces(tm.nondegenerate_faces(height=1e-8));tm.remove_unreferenced_vertices();tm.export(dest)
        assert tm.is_watertight and tm.is_winding_consistent and len(tm.split())==1,n
        rt=cq.importers.importStep(str(ROOT/'step'/f'{n}.step'));assert one(rt).isValid()
        report.append(dict(name=n,watertight=True,single_solid=True,step_roundtrip_valid=True,volume_mm3=round(one(s).Volume(),2),print_bounds_mm=tm.extents.round(2).tolist()))
    for label,role,i,a,b,cy in actuator_instances():
        for n,s in acts[role].items():items.append(dict(name=label+'_V6_'+n,group='act_'+label,role=role,axis_index=i,a=a,b=b,y=cy,color=ORANGE if n=='01_body' else STEEL if n=='04_rod' else DARK,kind='actuator',moving=n.startswith(('04','05')),**mesh(s)))
    (ROOT/'source/scene.json.gz').write_bytes(gzip.compress(json.dumps(items,separators=(',',':')).encode()))
    (ROOT/'parameters.json').write_text(json.dumps(config(),indent=2))
    assy=cq.Assembly(name='Cat320_reference_V6_fixed_arm');col={p['name']:p['color'] for p in items}
    for n,s in placed_parts(parts,acts).items():assy.add(s,name=n,color=cq.Color(*col[n]))
    dest=ROOT/'step/excavator_arm_assembly.step';assy.export(str(dest));rt=cq.importers.importStep(str(dest));assert one(rt).isValid()
    (ROOT/'source/export_report.json').write_text(json.dumps(dict(parts=report,assembly_solids=len(rt.solids().vals()),build_seconds=round(time.time()-start,1)),indent=2))
    print('DONE',round(time.time()-start,1),'seconds',flush=True)

if __name__=='__main__':export_all()

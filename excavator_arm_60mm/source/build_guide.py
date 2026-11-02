"""CAD drawings and illustrated guide, including the R4 lift-mount revision."""
from pathlib import Path
import gzip,json,math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as Patch,Circle
from shapely.geometry import Polygon
from shapely.ops import unary_union
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from PIL import Image,ImageDraw,ImageFont
from kinematics import *
ROOT=Path(__file__).resolve().parents[1]


def projection(item,st):
    v=np.array(item['vertices'])[:,[0,2]];g=item['group']
    if g.startswith('act_'):
        role=item['role'];idx=ORDER.index(role);a,b=[('A','B'),('C','D'),('F','R')][idx];p,q=st['points'][a],st['points'][b];u=(q-p)/np.linalg.norm(q-p);n=np.array([u[1],-u[0]])
        z=v[:,1]+37.5+(st['strokes'][idx] if item.get('moving') else 0);v=v[:,0,None]*n+z[:,None]*u+p
    else:v=v@rot(st['angles'][g]).T+st['origins'][g]
    polys=[]
    for f in item['triangles']:
        pts=v[f];area=abs(np.cross(pts[1]-pts[0],pts[2]-pts[0]))/2
        if area>1e-7:polys.append(Polygon(pts))
    return unary_union(polys).buffer(0)


def drawing():
    st=solve();p=st['points'];items=json.loads(gzip.decompress((ROOT/'source/scene.json.gz').read_bytes()))
    fig,ax=plt.subplots(figsize=(16.54,11.69),dpi=150);fig.patch.set_facecolor('#fbfcf9');ax.set_facecolor('#fbfcf9')
    ax.axhline(0,color='#96a7a3',lw=.8,ls='--');ax.text(580,4,'Mounting plane Z = 0',fontsize=8,ha='right',color='#687d7d')
    for item in items:
        if item['kind']=='hardware' or item['group']=='act_boom1':continue
        poly=projection(item,st)
        color='#dfa526' if item['kind']=='printed' and item['group']!='base' else '#344c58' if item['group']=='base' else '#c87330' if '01_body' in item['name'] else '#8c9ca4'
        for shape in poly.geoms if hasattr(poly,'geoms') else [poly]:
            ax.add_patch(Patch(np.array(shape.exterior.coords),fc=color,ec='#354f59',lw=.45,zorder=2))
            for hole in shape.interiors:ax.add_patch(Patch(np.array(hole.coords),fc='#fbfcf9',ec='#354f59',lw=.3,zorder=3))
    offsets={'O':(-20,-12),'A':(12,-12),'B':(-18,8),'C':(-9,17),'D':(8,12),'E':(-22,-8),'F':(12,8),'J':(-23,0),'R':(10,9),'H':(-23,-7),'Q':(10,-7),'T':(-18,-14)}
    for key,pt in p.items():
        ax.add_patch(Circle(pt,2.5,fc='white',ec='#233e49',lw=1,zorder=7));ax.annotate(key,pt,xytext=offsets[key],textcoords='offset points',fontsize=11,fontweight='bold',color='#203b45',zorder=8)
    def dim(a,b,offset,label):
        v=b-a;u=v/np.linalg.norm(v);n=np.array([-u[1],u[0]]);aa=a+n*offset;bb=b+n*offset
        ax.plot([a[0],aa[0]],[a[1],aa[1]],color='#71818b',lw=.6);ax.plot([b[0],bb[0]],[b[1],bb[1]],color='#71818b',lw=.6)
        ax.annotate('',aa,bb,arrowprops=dict(arrowstyle='<->',color='#314753',lw=.8));center=(aa+bb)/2+n*5
        angle=math.degrees(math.atan2(v[1],v[0]));angle=angle+180 if angle<-90 else angle
        ax.text(*center,label,fontsize=10,rotation=angle,ha='center',va='bottom',color='#314753',bbox=dict(fc='#fbfcf9',ec='none',pad=1))
    dim(p['O'],p['E'],132,'380.000  (5700 / 15)');dim(p['E'],p['H'],-63,'193.333  (2900 / 15)');dim(np.array([0.,0]),p['O'],47,'88');dim(p['H'],p['T'],-32,'R104.667  (1570 / 15)')
    ax.set_aspect('equal');ax.set_xlim(-100,525);ax.set_ylim(-55,450);ax.axis('off')
    fig.text(.05,.95,'CAT 320 REFERENCE / V6 ARM / 1:15',fontsize=22,weight='bold',color='#20333e')
    fig.text(.05,.92,'DIMENSION SHEET  |  Actual CAD silhouette  |  Fixed base; no chassis  |  All dimensions in mm',fontsize=10,color='#62727a')
    fig.text(.05,.054,'Factory dimensions retained: boom 5700, stick 2900, bucket width 1200, tip radius 1570. Model bucket width: 80 mm.\nMounts, sections and cylinder pin placements are adapted geometry. J–R = 52; R–Q = 65; H–Q = 35. Not a cutting template.',fontsize=10,color='#435963')
    fig.savefig(ROOT/'images/dimension_sheet.png',dpi=160);fig.savefig(ROOT/'dimension_sheet.pdf');plt.close(fig)


def comparison():
    a=Image.open(ROOT/'references/cat320_view_018.jpg').convert('RGB');b=Image.open(ROOT/'images/side_view.png').convert('RGB')
    result=Image.new('RGB',(1800,900),'#f5f7f4');d=ImageDraw.Draw(result)
    font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';title=ImageFont.truetype(font,27);small=ImageFont.truetype(font,18)
    for i,(im,label) in enumerate([(a,'Cat 320 manufacturer reference'),(b,'1:15 V6 model — arm and fixed mount')]):
        im.thumbnail((860,735));result.paste(im,(20+900*i+(860-im.width)//2,95+(735-im.height)//2));d.text((30+900*i,30),label,font=title,fill='#20333e')
    d.text((30,850),'Reference image © Caterpillar. Boom / stick / bucket width / tip radius follow the published 1:15 dimensions.',font=small,fill='#526770')
    result.save(ROOT/'images/reference_comparison.png')


def version_comparison():
    """Compare actual CAD silhouettes at identical mm-per-pixel scales."""
    import importlib.util
    cache=ROOT/'references/r2_comparison_outline.json'
    def outlines(folder,st):
        result=[]
        items=json.loads(gzip.decompress((folder/'source/scene.json.gz').read_bytes()))
        for item in items:
            if item['kind']=='hardware' or item['group']=='act_boom1':continue
            shape=projection(item,st)
            color='#dfa526' if item['kind']=='printed' and item['group']!='base' else '#344c58' if item['group']=='base' else '#c87330' if '01_body' in item['name'] else '#8c9ca4'
            for poly in shape.geoms if hasattr(shape,'geoms') else [shape]:
                result.append(dict(exterior=list(poly.exterior.coords),holes=[list(h.coords) for h in poly.interiors],color=color))
        return result
    if not cache.exists():
        old=ROOT.parent/'excavator_arm'
        spec=importlib.util.spec_from_file_location('r2_reference_kinematics',old/'source/kinematics.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        cache.write_text(json.dumps(dict(source='R2 exported CAD silhouette at its reference pose; mm',polygons=outlines(old,mod.solve()))))
    old=json.loads(cache.read_text())['polygons'];new=outlines(ROOT,solve())
    fig,axes=plt.subplots(1,2,figsize=(14,7),dpi=160)
    fig.patch.set_facecolor('#f5f7f4')
    for ax,data,title,subtitle in zip(axes,[old,new],['R2 / 1:12','60 mm edition / 1:15'],['475 mm boom / 241.7 mm stick / 100 mm bucket','380 mm boom / 193.3 mm stick / 80 mm bucket']):
        ax.set_facecolor('#f5f7f4')
        for poly in data:
            ax.add_patch(Patch(poly['exterior'],fc=poly['color'],ec='#354f59',lw=.45))
            for hole in poly['holes']:ax.add_patch(Patch(hole,fc='#f5f7f4',ec='#354f59',lw=.3))
        ax.axhline(0,lw=.7,color='#a6b2ae');ax.set_xlim(-80,550);ax.set_ylim(-20,470);ax.set_aspect('equal');ax.axis('off')
        ax.set_title(title+'\n'+subtitle,fontsize=13,color='#20333e',pad=16)
        ax.plot([-45,55],[425,425],color='#20333e',lw=2);ax.text(5,435,'100 mm',ha='center',fontsize=9,color='#435963')
    fig.suptitle('Cat 320 proportions. One common actuator size.',fontsize=19,weight='bold',color='#20333e',y=.97)
    fig.text(.06,.065,'R2 strokes: 85 / 105 / 60 mm; four units in three sizes.',fontsize=11,color='#435963')
    fig.text(.53,.065,'New strokes: 60 / 60 / 60 mm; four identical U60 units.',fontsize=11,color='#435963')
    fig.text(.06,.025,'Same drawing scale and joint pose. Main reference dimensions are 20% smaller; pin hardware and linkage are adapted.',fontsize=10,color='#435963')
    fig.subplots_adjust(left=.035,right=.985,bottom=.11,top=.79,wspace=.08)
    fig.savefig(ROOT/'images/version_comparison.png');plt.close(fig)


def mount_comparison():
    before=Image.open(ROOT/'references/r3_mount_before.png').convert('RGB')
    after=Image.open(ROOT/'images/lift_mount_detail.png').convert('RGB')
    result=Image.new('RGB',(1800,1000),'#f5f7f4');d=ImageDraw.Draw(result)
    font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';title=ImageFont.truetype(font,29);small=ImageFont.truetype(font,21)
    for i,(im,label) in enumerate([(before,'R3 / narrow projecting supports'),(after,'R4 / broad saddles and cross-web')]):
        im.thumbnail((870,790));result.paste(im,(15+900*i+(870-im.width)//2,85+(790-im.height)//2));d.text((30+900*i,28),label,font=title,fill='#20333e')
    d.text((30,888),'5 mm cheeks / 7 mm boss radius',font=small,fill='#526770')
    d.text((930,888),'8 mm cheeks / 10 mm boss radius',font=small,fill='#526770')
    d.text((30,934),'Pins move 32.6 mm forward and 27.8 mm lower in boom coordinates. Both views use the same camera and pose.',font=small,fill='#526770')
    d.text((30,968),'60 mm stroke and 2–69° boom range retained. Geometry and motion checked; printed strength not load-tested.',font=small,fill='#526770')
    result.save(ROOT/'images/lift_mount_comparison.png')


def guide():
    val=json.loads((ROOT/'validation.json').read_text());exp=json.loads((ROOT/'source/export_report.json').read_text());assert val['status']=='PASS'
    c=canvas.Canvas(str(ROOT/'build_guide.pdf'),pagesize=(595.28,841.89));ink='#20333e';sub='#60717a'
    def text(x,y,s,size=10,bold=False,color=ink):c.setFillColor(HexColor(color));c.setFont('Helvetica-Bold' if bold else 'Helvetica',size);c.drawString(x,y,s)
    def header(page,title,subtitle):
        text(38,806,'CAT 320 REFERENCE / V6 ARM / 60 MM EDITION / REVISION 04',9,True,sub);text(38,770,title,23,True);text(38,748,subtitle,10,color=sub);c.setStrokeColor(HexColor('#d8e0e2'));c.line(38,731,557,731);text(38,24,'Adapted CAD model  |  Units: mm  |  Full dimensions and BOM: README.md',8,color=sub);text(540,24,str(page),9)
    def table(y,rows,widths):
        for i,row in enumerate(rows):
            if i==0:c.setFillColor(HexColor('#eaf0ee'));c.rect(38,y-20,sum(widths),24,fill=1,stroke=0)
            x=38
            for s,w in zip(row,widths):text(x+7,y-12,str(s),9,i==0);x+=w
            c.setStrokeColor(HexColor('#dce2e3'));c.line(38,y-21,38+sum(widths),y-21);y-=24
        return y
    def lines(y,ls,size=10,step=16):
        for s in ls:text(38,y,s,size,color=sub);y-=step
    header(1,'One stroke. A smaller arm.','Bent box boom. Compact pivots. Inward bucket. Four identical 60 mm actuators.')
    c.drawImage(ImageReader(str(ROOT/'images/version_comparison.png')),27,400,width=541,height=300,preserveAspectRatio=True,anchor='c')
    table(379,[['Published Cat 320 dimension','Reference','Model at 1:15'],['Reach boom pin centres','5700','380.000'],['R2.9 stick pin centres','2900','193.333'],['1.19 m3 HD bucket width','1200','80.000'],['Bucket tip radius','1570','104.667']],[269,120,130])
    text(38,228,'Confirmed dimensions and adapted geometry',12,True)
    lines(205,['The four dimensions above come from Caterpillar technical specifications,','pages 4, 5 and 11. Side photographs establish the shape and mechanism.','Section outlines, detailed pin locations and the ground support are adapted','to the V6 actuators; this is not factory CAD or a scaled factory load rating.'])
    lines(109,['References: Finning Cat 320 product page; Caterpillar specifications and','360-degree side image. Full URLs and downloaded references are included','under references/. Manufacturer images remain copyright Caterpillar.'],9,15);c.showPage()
    header(2,'Geometry & correct bucket action','Side silhouette is generated from the exported CAD meshes.')
    c.drawImage(ImageReader(str(ROOT/'images/dimension_sheet.png')),18,337,width=559,height=395,preserveAspectRatio=True,anchor='c')
    table(331,[['Key interface','Model dimensions'],['Main pivots O, E, H','diameter 6 shaft / diameter 6.2 hole'],['Actuator and linkage pivots','diameter 3 shaft / diameter 3.2 hole'],['Four-bar J-R / R-Q / H-Q','52 / 65 / 35'],['Boom / stick box width','48 / 32'],['Base plate / root height','132 x 164 x 10 / 88']],[260,259])
    text(38,163,'Extension must produce these actions',12,True)
    lines(141,['Boom rises. Stick crowds inward. Bucket cutting lip curls up toward the base.','Both boom cylinders share one angle and must remain equal in length.','The bucket mouth faces the machine in the reference pose. Its tip lies','approximately 1.3 mm above the mounting plane in that pose.'],9,15);c.showPage()
    header(3,'Actuators sized to the arm','One 75 mm screw and one 60 mm stroke actuator design serves all positions.')
    table(704,[['Function','Qty','Screw','Stroke','Closed-open'],['Boom, V6-U60','2','75','60','140-200'],['Stick, V6-U60','1','75','60','140-200'],['Bucket, V6-U60','1','75','60','140-200']],[165,45,80,80,149])
    lines(583,['Screw length is measured from gearbox front face to tip.','V6 closed pin spacing = screw length + 65; stroke = screw length - 15.','Each end retains 3 mm of mechanical reserve beyond nominal travel.','The original 55 mm V6-S screw and its PCB do not fit this 60 mm version.'])
    text(38,494,'Matching regenerated components',12,True)
    lines(472,['Build four copies of the same barrel, caps, rod and rod eye.','New end-stop boards, Gerbers, KiCad, BOM and placement files are included.','The common actuator CAD/STL checks pass; its board has zero design-','rule errors and zero independent Gerber readback mismatch.'])
    text(38,380,'Rotation and electrical direction',12,True)
    lines(358,['M3 x 0.5 right-hand screw: 2 revolutions per mm.','Clockwise extends, viewed from the rod end toward the motor.','Nominal full strokes need 120 revolutions on every actuator.','Electrical A+ / B- extends; reverse polarity retracts. Nominal supply is 6 V.','There is no external position feedback from the original V6 circuitry.'])
    text(38,242,'Paired boom control',12,True)
    lines(220,['Use three reversible control functions; coordinate both boom cylinders together.','They represent one mechanical axis. Do not command unequal lengths.','Match both physical end stops before operation. The viewer sliders specify','exact geometry; they are not a supplied hardware position controller.'])
    lines(111,['The original electronics topology and magnetic assumptions are inherited.','The resized mechanical and PCB layouts were checked; powered operation,','motor thrust capacity, temperature and real switch positions remain untested.'],9,15);c.showPage()
    header(4,'Assembly & verification','Use the matching sets and check the physical fits before loaded operation.')
    lines(704,['1. Anchor the fixed base using four M6 bolts through its diameter 6.6 holes.','2. Install boom O, stick E and bucket H with steel shafts and spacers.','3. Fit the paired rockers on J and outer links on R/Q on the illustrated branch.','4. Fit U60 cylinders at A-B (two), C-D and F-R. Keep boom strokes equal.','5. Fit collars with running endplay; add flexible external cable loops.','6. Jog unloaded and verify polarity, physical endpoints and paired reversal.'],10,18)
    text(38,571,'Measured checks on this revision',12,True)
    lines(549,[f"{val['solid_collision_poses']} sampled CAD poses; {val['exact_boolean_pairs']} distinct solid intersections checked.",'No external solid interference at the sampled poses, including reserve corners.',f"{val['closure_samples']} transmission samples; maximum pin error below 0.000001 mm.",f"Minimum four-bar transmission angle: {val['four_bar_guard_transmission_angle_deg'][0]:.2f} degrees including reserve.",f"{len(exp['parts'])} structural STL files: watertight and single-component; STEP imports pass.",'The V6-U60 actuators, with their cable clamps, pass their own CAD and board checks.'],10,17)
    text(38,423,'Working envelope',12,True)
    lines(401,[f"The sampled cutting tip spans X {val['tooth_x_range_mm'][0]:.1f} to {val['tooth_x_range_mm'][1]:.1f} mm and",f"Z {val['tooth_z_range_mm'][0]:.1f} to {val['tooth_z_range_mm'][1]:.1f} mm relative to the mounting plane.",'Below-plane poses represent excavation. A solid-floor rig must restrict these','poses or provide a clear recess/bench edge. Sampled checks do not prove','collision freedom at every continuous position.'],9,15)
    text(38,298,'Manufacturing and load limits',12,True)
    lines(276,['The boom STL is 414 mm long; it needs a large printer or an engineered split.','Closed hollow boxes require process-specific support and cavity planning.','A watertight model is not a validated load-bearing printed assembly.','Actual collar set screws, external wires and floor material are outside the','collision model. Printing, alignment, rod deflection, PETG creep, gearbox','thrust capacity and real end-stop accuracy need physical prototype tests.','No payload rating is supplied. See README.md for the shaft/spacer BOM.'],9,16)
    c.showPage()
    header(5,'Lift mounts integrated into the boom','R4: broader load paths at the two upper lift-cylinder connections.')
    c.drawImage(ImageReader(str(ROOT/'images/lift_mount_comparison.png')),27,409,width=541,height=300,preserveAspectRatio=True,anchor='c')
    table(395,[['Feature','Previous R3','Revised R4'],['Upper pin B, boom X / Z','117.372 / 87.808','150 / 60'],['Clevis cheek thickness','5','8'],['Boss radius / hole diameter','7 / 3.2','10 / 3.2'],['Upper lift pin arrangement','Two short pins','One diameter 3 x 126'],['Lower A, ground X / Z','55 / 53','47.277 / 55.771']],[229,145,145])
    text(38,218,'Attachment and assembly changes',12,True)
    lines(196,['Broad rounded saddle feet join a solid web across both boom walls.','Both upper eyes share a steel cross-pin, retained by two outside collars.','Use the revised boom and fixed base together; keep the eye joints free.','The 60 mm actuators, 2-69 degree boom range and main arm sizes remain.'],9,15)
    text(38,117,'Print strength still needs physical validation',12,True)
    lines(95,['Print on the broad side as oriented in the STL. Use continuous perimeters','and suitable local density around the bosses and saddle roots. Layer bonding,','material, print settings and pin fit determine actual strength. No load rating','or measured strength multiplier is claimed.'],9,14)
    c.save();print('Created CAD drawings, mount comparison and five-page guide')

if __name__=='__main__':drawing();comparison();version_comparison();mount_comparison();guide()

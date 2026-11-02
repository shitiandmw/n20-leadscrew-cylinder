"""English J8 review: actual CAD views plus a dimensioned axle section."""
import json,math
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle,Polygon,Circle
from matplotlib.backends.backend_pdf import PdfPages
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
INK='#203d47';MUTED='#57727c';INNER='#617c93';OUTER='#437786';GOLD='#c7923c';STEEL='#acbbc4'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})

def page(title,subtitle,number):
    f=plt.figure(figsize=(14,9.5),facecolor='#fbfcfb')
    f.text(.045,.94,title,fontsize=24,fontweight='bold',color=INK)
    f.text(.045,.902,subtitle,fontsize=10.5,color=MUTED)
    f.text(.045,.025,'JGY-370 / J8  |  Nominal CAD prototype  |  Dimensions in mm',fontsize=8,color=MUTED)
    f.text(.94,.025,str(number),fontsize=9,color=MUTED)
    return f

def pic(f,rect,name,crop=(80,170,1210,900)):
    im=Image.open(ROOT/'images'/name)
    if crop:im=im.crop(crop)
    ax=f.add_axes(rect);ax.imshow(im);ax.axis('off');return ax

def block(f,x,y,title,body,size=10):
    f.text(x,y,title,fontsize=size+2,fontweight='bold',color=INK,va='top')
    f.text(x,y-.035,body,fontsize=size,color=MUTED,va='top',linespacing=1.6)

def section(ax):
    ax.set_aspect('equal');ax.set_xlim(-49,48);ax.set_ylim(-35,35);ax.axis('off')
    def rect(a,b,lo,hi,c,edge=INK):ax.add_patch(Rectangle((a,lo),b-a,hi-lo,fc=c,ec=edge,lw=.65))
    # Local cheek section, cropped above the lower axle. Both support seats exist.
    for a,b,c in [(-28,-24,INNER),(24,28,OUTER)]:
        rect(a,b,-10,21,c);rect(a-.01,b+.01,-4.025,4.025,'white','white')
        ax.plot([a-.5,a+1,b-1,b+.5],[21,20,22,21],lw=.8,color=INK)
    for sign in [-1,1]:
        ax.add_patch(Polygon([(26.5,sign*4.025),(28,sign*5),(28,sign*4.025)],fc='white',ec='none'))
    # Road roller at X=0: hub, running bands and guide flanges.
    for sign in [-1,1]:
        def ring(a,b,ri,ro,c):rect(a,b,min(sign*ri,sign*ro),max(sign*ri,sign*ro),c)
        ring(-13,13,6.2,13,'#59676a')
        for a,b in [(-20,-13),(13,20)]:ring(a,b,11.1,13,'#59676a')
        for a,b in [(-20,-15),(15,20)]:ring(a,b,13,18,'#59676a')
        for a,b in [(-23,-20),(20,23)]:ring(a,b,11.1,18,'#59676a')
        for a,b in [(-23,-21.6),(21.6,23)]:ring(a,b,18,20,'#59676a')
        for a,b in [(-20,-13),(13,20)]:ring(a,b,4,11,GOLD)
        for a,b in [(-24,-20),(-13,13),(20,24)]:ring(a,b,4.05,6,STEEL)
    # Axle and inboard integral head. Front cone and retention simplified.
    rect(-30.5,-28,-6,4.3,STEEL);rect(-28,26.5,-4,4,STEEL)
    rect(14,26.6,-2.5,2.5,'white','white')
    ax.add_patch(Polygon([(25.5,-2.5),(26.5,-3.5),(26.5,3.5),(25.5,2.5)],fc='white',ec='none'))
    rect(16,25.5,-2.5,2.5,'#374a51')
    ax.add_patch(Polygon([(25.5,-2.5),(28,-5),(28,5),(25.5,2.5)],fc='#374a51',ec=INK,lw=.6))
    ax.axhline(0,color=MUTED,ls='--',lw=.5)
    def label(text,xy,at,ha='center'):
        ax.annotate(text,xy=xy,xytext=at,ha=ha,fontsize=8.5,color=INK,arrowprops=dict(arrowstyle='-',color=MUTED,lw=.65))
    label('Inner structural plate\n4 mm aluminum',(-26,15),(-38,28))
    label('Outer structural plate\n4 mm aluminum',(26,15),(37,28))
    label('2 x 608 bearings',(16,9),(0,29))
    label('Integral axle head\nFlat upward',(-30,-3),(-39,-22))
    label('M5 x 12 screw\nFlush at Y28',(28,0),(37,-22))
    label('8 mm steel through-axle',(0,-3),(0,-23))
    for x in [-24,24]:ax.plot([x,x],[-10,-31],color=MUTED,lw=.6)
    ax.annotate('',xy=(-24,-30),xytext=(24,-30),arrowprops=dict(arrowstyle='<->',color=MUTED,lw=.8))
    ax.text(0,-29,'48 mm between plate faces',ha='center',va='bottom',fontsize=8,color=INK)

def layout(ax,inner=False):
    d=json.loads((ROOT/'plate_layout.json').read_text());p=d['inner' if inner else 'outer']
    ax.set_aspect('equal');ax.set_xlim(150,-150);ax.set_ylim(-1,96);ax.axis('off')
    ax.add_patch(Polygon(p['outline'],fc=INNER if inner else OUTER,ec=INK,lw=.8))
    for h in p['holes']:ax.add_patch(Polygon(h,fc='white',ec=INK,lw=.65))
    for x,z,g in d['axes']:
        ax.add_patch(Circle((x,z),4.025 if inner else 5,fc='white',ec=INK,lw=.65))
        ax.add_patch(Circle((x,z),18 if g.startswith('roller') else 15,fill=False,ec=GOLD,lw=.9,ls='--'))
    for x,z in d['ties']:ax.add_patch(Circle((x,z),2.15 if inner else 4,fc='white',ec=INK,lw=.6))
    if not inner:ax.add_patch(Circle(d['drive'],6,fc='white',ec=INK,lw=.6))
    ax.text(0,91,'30 mm upper rollers',ha='center',fontsize=8,color=INK)
    for x in [-30,30]:ax.annotate('',xy=(x,81),xytext=(x*.3,87),arrowprops=dict(arrowstyle='-',color=MUTED,lw=.6))
    ax.text(0,0,'36 mm lower rollers',ha='center',fontsize=8,color=INK)
    for x in [-52,0,52]:ax.annotate('',xy=(x,10),xytext=(x*.2,5),arrowprops=dict(arrowstyle='-',color=MUTED,lw=.6))

def main():
    v=json.loads((ROOT/'validation.json').read_text());g=json.loads((ROOT/'motion_geometry_validation.json').read_text())
    assert v['pass'] and g['pass']
    with PdfPages(ROOT/'J8_design_review.pdf') as pdf:
        f=page('J8 / Continuous side frames on both sides','Your reference layout, adapted to the retained motor, track dimensions and five roller positions.',1)
        im=Image.open(ROOT/'references/user_continuous_frame.png');ax=f.add_axes([.045,.69,.44,.17]);ax.imshow(im);ax.axis('off')
        f.text(.05,.665,'Your reference: a broad continuous web with wheel mounting points.',fontsize=9,color=MUTED)
        ax=f.add_axes([.53,.67,.43,.22]);layout(ax)
        f.text(.55,.645,'J816 outer side plate / actual CAD profile. Dashed lines show roller diameters.',fontsize=8,color=MUTED)
        pic(f,[.025,.17,.61,.44],'exploded.png')
        block(f,.67,.57,'One continuous outer side','The full-length web joins the wheel mounts.\nFive axle holes match the inner side.\nThree cross ties connect the two plates.\nThe complete outer plate removes for service.',10)
        block(f,.67,.37,'Keep the end mechanisms free','Drive access: 12 mm opening.\nIdler opening follows the original travel.\nDrive bearings and sliding yoke retained.\nMotor-side plate has the necessary drive clearance.',10)
        block(f,.67,.22,'Same overall package','308.44 x 101 x 91.14 mm.\nOriginal motor and chassis mounting points.\nOne-piece protective housing retained.',10)
        f.text(.05,.075,'Both sides support the small-wheel axles. Current holes fit the retained 30 / 36 mm rollers; new sizes need a fresh track-clearance check.',fontsize=9,color=MUTED)
        f.savefig(ROOT/'images/J8_continuous_frame_review.png',dpi=180);pdf.savefig(f);plt.close(f)

        f=page('Continuous plates with matched axle positions','The removable cheek closes the support structure. It must be fitted for operation.',2)
        pic(f,[.03,.52,.47,.34],'bracket.png')
        pic(f,[.51,.52,.46,.34],'top.png')
        block(f,.06,.49,'Inner cheek / J815','4 mm seat: Y=-28 to -24.\nAxle head bears against the metal cheek.\nFrame access pocket clears the rear head.',10)
        block(f,.54,.49,'Outer cheek / J816','2.5 mm straight shaft engagement: Y24 to 26.5.\nThe remaining plate depth contains the countersink.\nScrew head finishes flush at Y28.',10)
        ax=f.add_axes([.065,.10,.40,.25]);section(ax)
        block(f,.54,.29,'Check fits before loaded use','Machine the plates as a matched pair.\nMatch five bearing stacks to the 48 mm cross ties.\nVerify free rotation and 1 mm flange clearance per side.\nFinish journals, blind threads and fastener seats.\nNo payload rating is established.',10)
        f.savefig(ROOT/'images/J8_axle_section.png',dpi=180);pdf.savefig(f);plt.close(f)

        f=page('Service access and operation','New J8 CAD, with the unchanged J6 unloaded motion trace replayed in the video.',3)
        pic(f,[.03,.49,.51,.37],'unit.png')
        block(f,.57,.82,'Nominal geometry checks',f"{v['static_current_parts']['pairs_tested']} changed-part collision pairs clear.\nOriginal overall bounds retained.\n12 outer-plate withdrawal positions checked.\n45 inboard axle-removal samples clear.\n30 wheel-removal samples clear.\n15 sampled motion poses clear.",10)
        block(f,.06,.43,'Service sequence','1. Remove housing for rear fastener access.\n2. Remove eight outer screws, then the outer plate.\n3. Open/remove chain before withdrawing wheels.\n4. Withdraw a bare axle inboard, head flat upward.\n5. Refit both plates and check free rotation.',10)
        block(f,.57,.43,'Video provenance','J8 geometry; reused J6 motion, not a new simulation.\nGeneric servo target: +/-20 rpm.\nNominal chain speed: 80 mm/s.\nUnloaded fixed frame; not physical footage.\nNo motor electrical or vehicle load model.',10)
        f.text(.06,.12,'Both continuous plates carry the small-wheel axle loads. The one-piece PA12 housing remains separate, with 2.5 mm nominal walls and a local 1 mm motor skin.',fontsize=9,color=INK)
        f.text(.06,.075,'Actual X-frame / left motor fit, screw preload, plate bearing stress, printed-frame creep and loaded endurance remain unverified.',fontsize=9,color=MUTED)
        pdf.savefig(f);plt.close(f)
    print('J8 three-page review and bracket/axle images generated.')
if __name__=='__main__':main()

"""Generate BOM, summary, drawings and readable PDF reports from actual results."""
import csv,json,math,html
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle,Circle,Polygon
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Image,Table,TableStyle,PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4,landscape
from design import *

HARDWARE=[
 ('Steel track pins',68,'Ø3 × 56 silver steel (yield ≥ 400 MPa); clip grooves at ±26.5 from centre','A stone jammed at the idler peaks one pin at about 157 N (257 MPa bending) in the track_wheel/ simulation; mild steel is not enough'),
 ('Steel track bushings',68,'Ø6 OD × Ø3.1 ID × 17','Captured replaceable sleeves; deburr and check free fit on Ø3 pins'),
 ('Track pin retaining clips',136,'For Ø3 shaft; nominal Ø6 envelope','Supplier groove dimensions govern'),
 ('608 bearings',24,'8 × 22 × 7, sealed','4 idler + 12 road + 8 return; rated static capacity at least 1000 N'),
 ('Hub bearings 61808-2RS1',2,'40 × 52 × 7, sealed (SKF 61808-2RS1 or equal)','Fixed bearing under each sprocket; C0 3.45 kN'),
 ('Hub bearings 6809-2RS',2,'45 × 58 × 7, sealed','Floating bearing at the inboard end of each hub; C0 ≥ 4.3 kN'),
 ('Hub pinions',2,'Steel spur gear m1.5, 12 T, 20°, face 11, bore 6 H7 + M3 set screw','On the 37D D-shaft, flush with the shaft end; see track_wheel/BOM.md'),
 ('Track tension springs',2,'Associated/Lee C-600-072-1500 music wire: OD 15.24, wire 1.83, free 38.1, 6.29 N/mm','Assembled 25.8 mm (77 N); recoil stop at 21.8 mm (102 N); catalogue max 117.8 N'),
 ('Tension adjusters',2,'M6 × 16 hex ISO 4017 + 2 M6 nuts ISO 4032','One nut captive in the rear wall, one lock nut; 0–4 mm adjustment'),
 ('Track-wheel screws and inserts',2,'Per side: 12 M3 × 5.7 heat-set inserts; 6 M3 × 10 + 6 M3 × 20 button head; 4 M3 × 10 + 2 M3 × 8 socket head; 2 M3 × 40 + nuts; M3 × 4 set screw','Kit per track wheel; track_wheel/BOM.md lists each position'),
 ('Motor cable grommets',2,'For a Ø6 hole, 1.2 mm panel','Rear cap of each final drive'),
 ('6004 bearings',2,'20 × 42 × 12, sealed','Slew pair; choose reputable rated bearings'),
 ('Free wheel shafts',10,'Ground steel Ø8 × 79','Road and return rollers'),
 ('Idler axles',2,'Ground steel Ø8 × 89','Through the idler yoke and wheel; slide with the yoke'),
 ('Ø8 shaft collars',24,'Split clamp, Ø16 × 5 envelope','20 roller retainers + 4 idler-axle retainers'),
 ('Drive gearmotors',2,'Pololu 37D metal gearmotor 150:1, 12 V, no encoder (#2829)','Inside the sprocket hubs; run from a current-limited driver set to 1.0 A (1.2 N m at the sprocket)'),
 ('Slew gearmotor',1,'12 V, 10 rpm, >=0.35 N m continuous; Ø25 × 51 body; Ø4 shaft','Verify shaft interface and body length; saddle-clamped'),
 ('Slew motor straps',2,'Formed steel strap, matching 25 mm body','M4 fasteners through mount at Z=54/84'),
 ('Slew pinion clamp hub',1,'Ø4 bore, Ø24 × 7; 3 × M3 tapped on Ø18','Metal; match/machine interface'),
 ('Slew spindle',1,'Ground steel Ø20 × 90','Z=34 to 124'),
 ('Slew lower collar',1,'Ø20 bore, OD30 × 10','Split clamp'),
 ('Slew deck clamp flange',1,'Ø20 bore, OD70 × 10; 4 × M5 tapped on Ø50 at 45°','Metal split clamp; cable hole Ø8 at (-10,25)'),
 ('Slew inner spacer',1,'Steel OD26 / ID20.1 × 28','Faces parallel; shim final stack'),
 ('Slew top spacer',1,'Steel OD28 / ID20.1 × 18','Contacts upper inner race only'),
 ('Slew outer spacers',2,'Steel OD42 / ID35: one ×12, one ×6','Contacts outer races only'),
 ('Gear stand-offs',6,'Metal OD10 / ID4.4 × 8','Ø112 pitch circle'),
 ('Mechanical stop posts',2,'Steel Ø8 × 44 with M5 mounting ends','Centres radius120, azimuth ±15°'),
 ('Ballast plate',1,f'Steel {BALLAST_BOX[1]-BALLAST_BOX[0]:.0f} × {2*BALLAST_BOX[2]:.0f} × {BALLAST_BOX[3]:.0f}, about {BALLAST_KG:.2f} kg','Inside the counterweight, clamped by its ribs through a 1 mm rubber pad; do not substitute printed plastic'),
 ('Ballast rubber pad',1,f'1 mm rubber strip, {BALLAST_BOX[1]-BALLAST_BOX[0]-4:.0f} × 16 mm','Between the ballast plate and the counterweight pressing rib'),
 ('18650 cells',2,f'Flat-top, unprotected; datasheet envelope Ø{CELL_DIAMETER_RANGE[0]:.1f}–{CELL_DIAMETER_RANGE[1]:.1f} × {CELL_LENGTH_RANGE[0]:.1f}–{CELL_LENGTH_RANGE[1]:.1f}; >=15 A continuous each','Matched pair, e.g. Samsung INR18650-25R or LG INR18650HG2. Panasonic NCR18650B fits but is not a 15 A cell. Button-top or protected cells (67–70 mm) do not fit'),
 ('Welded 2S1P pack build',1,f'{NICKEL_STRIP:g} mm pure nickel strip (one series link, two terminal tabs), {CELL_SEPARATOR:g} mm separator, {END_INSULATION_RANGE[0]:g}–{END_INSULATION_RANGE[1]:g} mm end insulators, {PACK_WRAP_RANGE[0]:g}–{PACK_WRAP_RANGE[1]:g} mm PVC wrap','Spot-welded, never soldered to the cans. Finished pack at most 38.2 × 19.1 × 67.6 mm with leads leaving the -Y end'),
 ('Closed-cell foam pads',3,f"Two Ø17 × {END_PAD['free_mm']:g} mm end pads at the +Y end; one {TOP_PAD['free_mm']:g} mm top pad, 31 × 16 mm",f"End pads never below {END_PAD['minimum_compressed_mm']:g} mm, top pad never below {TOP_PAD['minimum_compressed_mm']:g} mm across the datasheet range"),
 ('2S balancing/protection BMS',1,'>=10 A continuous; envelope 30 × 29 × 6 mm','Verify actual supplier dimensions; use insulating adapter plate'),
 ('12 V boost converter',1,'>=30 W continuous; envelope 60 × 32 × 21 mm','Verify cooling at 6.2 V input; shared output budget 36 W'),
 ('6 V buck-boost converter',1,'>=18 W continuous; envelope 37 × 32 × 16 mm','Maintains 6 V near pack cutoff; shared output budget 36 W'),
 ('Pack fuse / master stop / connector',1,'10 A fuse; suitable 8 A wiring/connector; accessible stop','External 8.4 V charger for the removable 2S pack'),
 ('Insulating module adapters and spacers',3,'Match purchased board holes to the two M3 holes per board in the equipment tray','Ø5 × 3 mm insulating standoffs shown; maximum module envelopes; choose actual hardware before printing'),
 ('0.8 mm PET glazing',4,'Cut from glazing/*.svg or cab_glazing_*.step','Inside-face adhesive strips; SVG templates are 1:1'),
 ('Roller inner spacers',10,'Steel OD12 / ID8.1 × 26','Road and return rollers'),
 ('Roller inboard spacers',10,'Steel OD12 / ID8.1 × 10','Rail to road/return roller'),
 ('Idler inner spacers',2,'Steel OD12 / ID8.1 × 6','Between idler bearing inner races'),
 ('1 mm washers',10,'Steel OD12 / ID8.1 × 1','Road and return outboard'),
 ('Idler inboard spacers',2,'Steel OD12 / ID8.1 × 20','Rail to wheel'),
 ('Idler outboard spacers',2,'Steel OD12 / ID8.1 × 11','Wheel to retaining collar'),
 ('Frame and housing fasteners',10,'M5 × 25, washers, locking nuts','6 rail/bridge + 4 slew housing; verify stack before ordering'),
 ('Arm mounting fasteners',4,'M6 × 25, washers, M6 nyloc nuts in underside deck pockets','Existing arm60 hole pattern'),
 ('Bearing cap tie fasteners',4,'M3 × 85, washers, locking nuts','Through both slew caps; do not thread plastic'),
 ('Deck flange fasteners',4,'M5 × 20 countersunk, into tapped metal flange','Heads flush with deck; thread-lock metal threads'),
 ('Ring gear fasteners',6,'M4 × 30 countersunk, M4 nyloc nuts in gear pockets','Heads flush with deck; 10 mm gear + 8 mm spacer + 10 mm deck'),
 ('Pinion fasteners',3,'M3 × 16 with 1 mm washers into tapped hub','About 5 mm thread engagement; keep heads below Z=124'),
 ('Slew motor mount bolts',4,'M4 × 25, washers, locking nuts','Mount feet to bridge'),
 ('Slew motor strap bolts',4,'M4 × 50, washers, locking nuts','Verify actual strap thickness'),
 ('Counterweight bolts',4,'M4 × 80 countersunk, M4 nuts in deck pockets','Through the counterweight bolt tubes; heads flush with the top'),
 ('Engine hood bolts',4,'M3 × 80 countersunk, M3 nuts in deck pockets','Through the hood bolt tubes'),
 ('Tank housing bolts',2,'M3 × 80 countersunk, M3 nuts in deck pockets','Through the housing bolt tubes'),
 ('Toolbox bolts',2,'M3 × 45 countersunk, M3 nuts in deck pockets','Through the toolbox bolt tubes'),
 ('Equipment tray screws',4,'M3 × 45 countersunk, M3 nuts in deck pockets','Through the four tray legs'),
 ('Exhaust stack screw',1,'M3 × 8 and M3 nut','From inside the hood top into the nut in the stack base; fit before the hood'),
 ('Hood hatch screws',4,'M3 × 12 countersunk, M3 nuts','Nuts captured in the four hood bosses'),
 ('Battery retainer screws',2,'M3 × 20, M3 nuts','Nuts slide into side slots in the cradle posts'),
 ('Cell cradle screws',2,'M3 × 8, M3 nuts','Cradle tabs to the tray; nuts in tray underside pockets'),
 ('Cab tie rods',4,'M3 threaded rod cut to 130, washer and nut on the roof','Through roof, corner posts and deck into the deck nuts; lower ends at Z125, above the Z124 deck underside'),
 ('Slew skirt bolts',6,'M3 × 25 countersunk, thin M3 nuts','Six bosses at radius130 and 30° phase'),
 ('Seat bolts',4,'M3 × 35, M3 nuts in deck pockets','Seat through cab floor and deck; tips end flush with the deck underside'),
 ('Console bolts',2,'M3 × 45 socket head in a 3 mm counterbore, M3 nuts in deck pockets','One per console; decorative controls'),
 ('Stop tab bolts',2,'M4 × 25 countersunk, washers, locking nuts','Tab to upper deck'),
 ('Arm60 assembly hardware',1,'Use existing arm60 shaft/spacer/collar BOM','No scaling or substitutions; includes Ø3 × 126 shared lift pin'),
 ('V6-U60 actuators',4,'75 mm M3 screw; 60 mm stroke; 140–200 mm pin spacing','Build from actuator_v6 BOM, PCB and assembly guide'),
 ('Control and electrical set',1,'Current-limited H-bridges, 6 V regulator, fuse/stop, slew feedback/NC limits, boom feedback, flexible harness','Requirements in ASSEMBLY.md; not supplied as commissioned electronics'),
]

def pdf(path,blocks):
    styles=getSampleStyleSheet();styles['BodyText'].fontSize=9;styles['BodyText'].leading=13
    styles['BodyText'].spaceAfter=8
    styles['Heading2'].keepWithNext=True
    story=[]
    for kind,value in blocks:
        if kind=='image':
            from PIL import Image as PILImage
            w,h=PILImage.open(value).size;story.append(Image(str(value),width=480,height=480*h/w));story.append(Spacer(1,10))
        elif kind=='page':story.append(PageBreak())
        elif kind=='table':
            cells=[[Paragraph(html.escape(str(cell)),styles['BodyText']) for cell in row] for row in value]
            widths=[225,275] if len(value[0])==2 else [145,115,240]
            table=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT')
            table.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8eeeb')),
                ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f5f7f6')]),
                ('VALIGN',(0,0),(-1,-1),'TOP'),
                ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
                ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
            ]))
            story.extend([table,Spacer(1,10)])
        else:
            style=styles['Title' if kind=='title' else 'Heading2' if kind=='heading' else 'BodyText']
            story.append(Paragraph(html.escape(str(value)),style))
    def footer(c,d):
        c.setFont('Helvetica',8);c.setFillColor(colors.grey);c.drawString(42,24,'ARM60 tracked excavator R3 / Track R4 | digital prototype | dimensions in mm');c.drawRightString(A4[0]-42,24,str(d.page))
    SimpleDocTemplate(str(path),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=40,bottomMargin=42).build(story,onFirstPage=footer,onLaterPages=footer)

def drawing():
    from shapely.geometry import box as rect
    from upper_body import deck_plan,hood_plan,cab_point,HATCH,EXHAUST
    body,cabc,cell='#b8830a','#455a64','#3d7a46'
    fig,axes=plt.subplots(1,2,figsize=(11.7,8.3),gridspec_kw={'width_ratios':[1.4,1]})
    fig.subplots_adjust(left=.07,right=.97,bottom=.17,top=.85,wspace=.30)
    fig.suptitle('ARM60 tracked excavator R3 — dimensional interfaces',fontsize=17,y=.95)
    fig.text(.07,.07,'All dimensions in mm. Kinematic reference only; use the supplied STEP files for manufacturing.\nPrinter-bed splitting is deferred. Purchased shafts, bearings and hubs must match their interface drawings.',fontsize=10,linespacing=1.6)
    ax=axes[0]
    for x in [-CENTRES/2,CENTRES/2+IDLER_ASSEMBLY_OFFSET]:ax.add_patch(Circle((x,AXLE_Z),PITCH_R,fill=False,color=cabc))
    pins=track_pins();ax.plot(*np.vstack([pins,pins[0]]).T,color=cabc,lw=.8)
    for x in ROAD_ROLLERS:ax.add_patch(Circle((x,29),18,fill=False,color=cabc))
    for x in RETURN_ROLLERS:ax.add_patch(Circle((x,RETURN_Z),RETURN_ROLLER_R,fill=False,color=cabc))
    for r in [(-145,70,290,10),(-32,32,64,74),(1,134,132,10)]:ax.add_patch(Rectangle(r[:2],*r[2:],fill=False,color=body))
    # R3 upper body in side projection; the front-right housings are shaded.
    t0,t1=TANK_HOUSING[:2];b0,b1=TOOLBOX[:2]
    ax.add_patch(Rectangle((t0,DECK_Z),t1-t0,HOOD_TOP_Z-DECK_Z,color=body,alpha=.18,lw=0))
    ax.add_patch(Polygon([(b0,DECK_Z),(b1,DECK_Z),(b1,TOOLBOX_STEP_Z),(b1-14,TOOLBOX_STEP_Z),(b1-14,TOOLBOX_TOP_Z),(b0,TOOLBOX_TOP_Z)],color=body,alpha=.18,lw=0))
    ax.add_patch(Polygon([(-TAIL_RADIUS,DECK_RIM_Z),(DECK_NOSE_X-8,DECK_RIM_Z),(DECK_NOSE_X-8,DECK_Z-10),(DECK_NOSE_X,DECK_Z-10),(DECK_NOSE_X,DECK_Z),(-TAIL_RADIUS,DECK_Z)],fill=False,color=body))
    cw=COUNTERWEIGHT_FRONT_X
    ax.add_patch(Polygon([(-TAIL_RADIUS,DECK_Z),(cw,DECK_Z),(cw,HOOD_TOP_Z),(-TAIL_RADIUS+6,HOOD_TOP_Z),(-TAIL_RADIUS,HOOD_TOP_Z-6)],fill=False,color=body))
    ax.plot([cw,HOOD_FRONT_X,HOOD_FRONT_X,HOOD_NOSE_X,HOOD_NOSE_X],[HOOD_TOP_Z,HOOD_TOP_Z,HOOD_NOSE_TOP_Z,HOOD_NOSE_TOP_Z,DECK_Z],color=body)
    hx0,hx1=HATCH['panel'][:2];ax.add_patch(Rectangle((hx0,HOOD_TOP_Z),hx1-hx0,2.4,color=body))
    ax.add_patch(Rectangle((EXHAUST[0]-3.8,HOOD_TOP_Z),7.6,18,color='#202c35'))
    d=CELL_NOMINAL[0];zc=GROOVE_Z-math.sqrt((GROOVE_R-d/2)**2-((GROOVE_PITCH-d-CELL_SEPARATOR)/2)**2)
    for sign in [-1,1]:ax.add_patch(Circle((CRADLE_X+sign*(d+CELL_SEPARATOR)/2,zc),d/2,color=cell))
    ax.add_patch(Rectangle((TRAY[0],TRAY_TOP_Z-4),TRAY[1]-TRAY[0],4,fill=False,color=cabc,lw=.8))
    ax.text(-150,170,'Counter-\nweight',fontsize=8,ha='center',va='center')
    ax.text(CRADLE_X,148,'2 × 18650',fontsize=8,ha='center',color=cell)
    ax.text((b0+b1)/2-8,160,'Toolbox',fontsize=7,ha='center',color='#6f5115')
    ax.text(14,182,'Tank',fontsize=7,ha='center',color='#6f5115')
    cx=[x+CAB_SHIFT_X for x in [-45,75,75,68,58,-37,-45,-45]]
    ax.plot(cx,[134,134,154,245,248,248,238,134],color=cabc)
    ax.add_patch(Rectangle((-45+CAB_SHIFT_X,248),120,4,fill=False,color=cabc))
    ax.annotate('',xy=(-215,DECK_Z),xytext=(-215,CAB_ROOF_Z),arrowprops={'arrowstyle':'<->','lw':.8})
    ax.text(-227,193,'118 cab',rotation=90,fontsize=8,ha='center',va='center')
    ax.annotate('',xy=(HOOD_FRONT_X,265),xytext=(HOOD_FRONT_X+120,265),arrowprops={'arrowstyle':'<->','lw':.8})
    ax.text(HOOD_FRONT_X+60,278,'120 cab',fontsize=8,ha='center')
    st=arm.solve()['points'];points=np.array([st[k]+ARM_OFFSET[[0,2]] for k in ['O','E','H','T']]);ax.plot(points[:,0],points[:,1],'o-',color=body,lw=3)
    for key,p in zip(['O','E','H','T'],points):ax.annotate(key,p,xytext=(5,5),textcoords='offset points')
    ax.annotate('',xy=(-110,-15),xytext=(110,-15),arrowprops={'arrowstyle':'<->'});ax.text(0,-28,'220 wheel centres',ha='center')
    ax.annotate(f'{HOOD_TOP_Z:g} hood / counterweight top',xy=(-130,HOOD_TOP_Z),xytext=(-235,310),fontsize=8,arrowprops={'arrowstyle':'->','lw':.7})
    ax.annotate('134 arm mounting plane',xy=(0,134),xytext=(150,170),fontsize=8,arrowprops={'arrowstyle':'->','lw':.7});ax.axhline(0,color='#333',lw=.7);ax.set_title('Side layout — reference pose',fontsize=11);ax.set_aspect('equal');ax.set_xlim(-250,530);ax.set_ylim(-45,520);ax.set(xlabel='X / forward, mm',ylabel='Z / height, mm');ax.grid(alpha=.15)
    ax=axes[1]
    ax.add_patch(Polygon(np.asarray(deck_plan().exterior.coords),fill=False,color=body))
    ax.add_patch(Circle((0,0),TAIL_RADIUS,fill=False,color=body,ls=':'))
    ax.annotate(f'R{TAIL_RADIUS:g} tail swing',xy=(-TAIL_RADIUS*math.sqrt(.5),-TAIL_RADIUS*math.sqrt(.5)),xytext=(-228,-222),fontsize=8,arrowprops={'arrowstyle':'->','lw':.7})
    ax.add_patch(Polygon(np.asarray(hood_plan().union(rect(-40,-HOOD_NOSE_HALF_WIDTH,HOOD_NOSE_X,HOOD_NOSE_HALF_WIDTH)).exterior.coords),fill=False,color=body,lw=.8))
    ax.plot([COUNTERWEIGHT_FRONT_X]*2,[-DECK_HALF_WIDTH,DECK_HALF_WIDTH],color=body,lw=.8)
    x0,x1,y0,y1=HATCH['opening'];ax.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,fill=False,color=body,ls='--',lw=.8))
    for sign in [-1,1]:ax.add_patch(Rectangle((CRADLE_X+sign*(d+CELL_SEPARATOR)/2-d/2,-CELL_NOMINAL[1]/2),d,CELL_NOMINAL[1],color=cell))
    for name,(a,b,c,e),_ in BOARDS:ax.add_patch(Rectangle((a,c),b-a,e-c,fill=False,color=cell,lw=.7))
    (cx0,cy0),(cx1,cy1)=cab_point(-45,-154),cab_point(75,-84);cx0,cx1=sorted([cx0,cx1]);cy0,cy1=sorted([cy0,cy1])
    ax.add_patch(Rectangle((cx0,cy0),cx1-cx0,cy1-cy0,fill=False,color=cabc));ax.text((cx0+cx1)/2,(cy0+cy1)/2,'Cab',fontsize=8,ha='center',va='center')
    ax.annotate('',xy=(165,cy0),xytext=(165,cy1),arrowprops={'arrowstyle':'<->','lw':.8})
    ax.text(177,(cy0+cy1)/2,'70 cab',rotation=90,fontsize=8,ha='center',va='center')
    for (a,b,c,e),label in [(TANK_HOUSING,'Tank'),(TOOLBOX,'Tool-\nbox')]:
        ax.add_patch(Rectangle((a,c),b-a,e-c,fill=False,color=body));ax.text((a+b)/2,(c+e)/2,label,fontsize=7,ha='center',va='center')
    ax.text(-150,0,'Counterweight',rotation=90,fontsize=7,ha='center',va='center')
    ax.text((x0+x1)/2,y1-12,'Hatch',fontsize=7,ha='center')
    for y in [-TRACK_Y,TRACK_Y]:ax.add_patch(Rectangle((-154,y-SHOE_WIDTH/2),308,SHOE_WIDTH,fill=False,color=cabc,lw=.8))
    ax.add_patch(Circle((0,0),52,fill=False,color=cabc));ax.add_patch(Circle((0,0),73.5,fill=False,color=body))
    ax.add_patch(Circle((87.2,0),16.5,fill=False,color=body))
    for x in [13,121]:
        for y in [-65,65]:ax.add_patch(Circle((x,y),3.3,color='#202c35'))
    ax.plot([0,87.2],[0,0],'k--',lw=.8);ax.text(43.6,8,'87.2 gear axes',ha='center',fontsize=7)
    ax.annotate('',xy=(-205,-TRACK_Y),xytext=(-205,TRACK_Y),arrowprops={'arrowstyle':'<->'});ax.text(-216,0,f'{2*TRACK_Y:g} track centres',rotation=90,ha='center',va='center')
    ax.text(0,218,f'{2*TRACK_Y+SHOE_WIDTH:g} overall shoe width / {2*DECK_HALF_WIDTH:g} upper platform',ha='center',fontsize=8)
    ax.annotate('M6 arm holes X=13 / 121, Y=±65',xy=(13,-65),xytext=(-60,-218),fontsize=8,arrowprops={'arrowstyle':'->','lw':.7})
    ax.set_title('Top layout — zero slew',fontsize=11);ax.set_aspect('equal');ax.set_xlim(-232,195);ax.set_ylim(-228,235);ax.set(xlabel='X / forward, mm',ylabel='Y / lateral (+ = machine left), mm');ax.grid(alpha=.15)
    fig.savefig(ROOT/'dimension_sheet.pdf');fig.savefig(ROOT/'images/dimension_sheet.png',dpi=160);plt.close(fig)

def track_drawing():
    """Reference diagram from the same parameters as the CAD, in millimetres."""
    fig=plt.figure(figsize=(11.7,8.3),layout='constrained')
    fig.get_layout_engine().set(rect=(0,0,1,.93))  # keep the axes below the title
    grid=fig.add_gridspec(2,2,height_ratios=[.65,1.5])
    ax=fig.add_subplot(grid[0,:])
    for y in [-TRACK_Y,TRACK_Y]:
        ax.add_patch(Rectangle((y-SHOE_WIDTH/2,0),SHOE_WIDTH,42,facecolor='#52616b'))
    outer=TRACK_Y+SHOE_WIDTH/2;margin=outer-DECK_HALF_WIDTH
    ax.add_patch(Rectangle((-DECK_HALF_WIDTH,55),2*DECK_HALF_WIDTH,16,facecolor='#d4a12b'))
    ax.text(0,63,f'{2*DECK_HALF_WIDTH:g} mm R3 upper platform',ha='center',va='center',fontsize=10)
    ax.annotate('',xy=(-outer,-12),xytext=(outer,-12),arrowprops={'arrowstyle':'<->'})
    ax.text(0,-27,f'{2*outer:g} mm overall shoes / {2*TRACK_Y:g} mm track centres',ha='center')
    for sign in [-1,1]:ax.text(sign*(outer+DECK_HALF_WIDTH)/2,82,f'{margin:g} mm',ha='center')
    ax.text(0,24,'Width comparison at zero slew',ha='center',fontsize=10)
    ax.set(xlim=(-225,225),ylim=(-40,95));ax.set_aspect('equal');ax.axis('off')
    ax=fig.add_subplot(grid[1,0])
    profile=np.asarray(sprocket_outline().exterior.coords)
    ax.add_patch(Polygon(profile,facecolor='#d4a12b',edgecolor='#6f5115',lw=.8))
    # Track R5 hub in the sprocket plane: 61808 bearing on the stationary end wall,
    # gearbox face screws, and the pinion/ring pitch circles of the hub stage.
    b=tw.BEARINGS['outboard']
    ax.add_patch(Circle((0,0),b['D']/2,facecolor='#bec8ce',edgecolor='#34454e',lw=.6))
    ax.add_patch(Circle((0,0),b['d']/2,facecolor='#52616b',edgecolor='#34454e',lw=.6))
    for a in tw.SCREW_PHASES:
        r=tw.GEARMOTOR['face_screw_circle']/2;ax.add_patch(Circle((r*math.cos(math.radians(a)),r*math.sin(math.radians(a))),2.85,color='#1d2428'))
    for (x,radius) in [(0,tw.GEAR_MODULE*tw.RING_TEETH/2),(tw.CENTRE_DISTANCE,tw.GEAR_MODULE*tw.PINION_TEETH/2)]:
        ax.add_patch(Circle((x,0),radius,fill=False,ls='--',lw=.9,color='white'))
    ax.add_patch(Circle((tw.CENTRE_DISTANCE,0),3,color='#e8e8e8'))
    for _,origin,a in track_poses():
        c,s=math.cos(a),math.sin(a)
        transform=lambda p:np.asarray(p)@np.array([[c,s],[-s,c]])+origin-np.array([-CENTRES/2,AXLE_Z])
        pad=transform([[-9.4,-6],[9.4,-6],[9.4,-4],[-9.4,-4]])
        if pad[:,0].min()<52:ax.add_patch(Polygon(pad,facecolor='#52616b'))
        pin=transform([10,0])
        if pin[0]<48:
            ax.add_patch(Circle(pin,BUSH_R,facecolor='#bec8ce',edgecolor='#34454e',lw=.6))
            ax.add_patch(Circle(pin,1.5,color='white'))
    ax.text(0,-63,'20 mm pitch · 12 teeth · Ø6 steel sleeves on Ø3 pins\n61808 hub bearing on the stationary end wall\nPinion z12 on the motor shaft (7 mm offset), ring z21 in the cap',ha='center',va='top',fontsize=9.5)
    ax.set(xlim=(-53,53),ylim=(-87,56));ax.set_aspect('equal');ax.axis('off')
    ax.set_title('Sprocket hub: bushing drive and hub gear stage',fontsize=12)
    ax=fig.add_subplot(grid[1,1])
    def block(y0,y1,z0,z1,color):
        ax.add_patch(Rectangle((y0,z0),y1-y0,z1-z0,facecolor=color,edgecolor='white',lw=.5))
    block(-SHOE_WIDTH/2,SHOE_WIDTH/2,1,3,'#52616b')
    block(-SHOE_WIDTH/2,SHOE_WIDTH/2,0,1,'#52616b')
    for sign in [-1,1]:
        y0,y1=sorted([sign*14,sign*21]);block(y0,y1,3,11,'#52616b')
        y0,y1=sorted([sign*15,sign*GUIDE_INNER_Y]);block(y0,y1,11,47,'#d4a12b')
        y0,y1=sorted([sign*GUIDE_INNER_Y,sign*GUIDE_OUTER_Y]);block(y0,y1,9,49,'#a87918')
    block(-15,15,16,42,'#d4a12b')
    ax.axhline(29,color='#5b636a',lw=.8,ls='--')
    ax.annotate('0.6 mm per side',xy=(21.3,10),xytext=(0,-10),ha='center',fontsize=10,
                arrowprops={'arrowstyle':'->','lw':.8,'connectionstyle':'angle,angleA=0,angleB=-80,rad=8'})
    ax.annotate('Outer flanges\n2 mm projection',xy=(-22.3,9),xytext=(-32,55),ha='left',fontsize=10,
                arrowprops={'arrowstyle':'->','lw':.8})
    ax.text(0,32,'Free roller',ha='center',fontsize=10)
    ax.text(0,-22,'Running rims bear on both link rails\nClearance permits free chain articulation\nSchematic section; bearings omitted',ha='center',va='top',fontsize=9)
    ax.set(xlim=(-35,35),ylim=(-43,62));ax.set_aspect('equal');ax.axis('off')
    ax.set_title('Road roller / shoe cross-section',fontsize=12)
    fig.suptitle('Track R5 — in-hub final drive, side guidance and wider stance',fontsize=17,y=.965)
    fig.savefig(ROOT/'images/track_interfaces.png',dpi=160)
    fig.savefig(ROOT/'track_interfaces.pdf');plt.close(fig)


def build():
    export=json.loads((ROOT/'source/export_report.json').read_text());v=json.loads((ROOT/'validation.json').read_text())
    track_cad=[json.loads((ROOT/f'simulation/{name}_cad_motion.json').read_text()) for name in ['track','track_ground']]
    gr=json.loads((ROOT/'simulation/track_ground_dynamics.json').read_text())
    tr=json.loads((ROOT/'simulation/track_dynamics.json').read_text());dy=json.loads((ROOT/'simulation/vehicle_dynamics.json').read_text());br=json.loads((ROOT/'browser_validation.json').read_text());pk=json.loads((ROOT/'simulation/packaging.json').read_text())
    loads=v['loads'];rows=[]
    wheel=REPO/'track_wheel';wv=json.loads((wheel/'validation.json').read_text());ws=json.loads((wheel/'simulation/summary.json').read_text())
    wc=ws['cases'];dr=loads['drive'];rating=tw.drive_rating();carrier=gr['wheel_checks']['mean_vertical_support_N'][5:]
    for p in export['parts']:
        if p.get('mirrored_stl'):
            rows.append(('Printed '+p['name'],1,'stl/'+p['name']+'.stl',p['note']))
            rows.append(('Printed '+p['name']+'_left',1,'stl/'+p['mirrored_stl'],'Already mirrored'))
        else:rows.append(('Printed '+p['name'],p['quantity'],'stl/'+p['name']+'.stl',p['note']))
    rows+=HARDWARE
    with (ROOT/'BOM.csv').open('w',newline='') as f:
        writer=csv.writer(f,lineterminator="\n");writer.writerow(['Item','Quantity','Specification or file','Notes']);writer.writerows(rows)
    (ROOT/'BOM.md').write_text('# Tracked arm60 bill of materials\n\nThe travel gearmotors, hub bearings and recoil springs are catalogue parts sized from cited datasheets (see ../track_wheel/README.md and BOM.md). The slew motor and its clamp hub are still procurement interfaces, not verified catalogue part numbers. Inspect the supplier drawing before ordering. Fastener lengths include a starting allowance; confirm washer, head and nut stacks during trial assembly.\n\n| Item | Qty | Specification / file | Notes |\n|---|---:|---|---|\n'+''.join('| '+' | '.join(str(x) for x in row)+' |\n' for row in rows))
    inherited=json.loads((ROOT/'simulation/inherited_arm/validation.json').read_text())
    all_pass=all(r['status']=='PASS' for r in [v,tr,gr,dy,br,pk,inherited,*track_cad]) and wv['summary']['all_checks_pass'] and ws['design_cases_pass']
    cf,bs,lay=pk['cell_fit'],pk['battery_service'],pk['layout']
    fasteners=sum(f.get('count',1) for f in pk['fasteners']);margin=TRACK_Y+SHOE_WIDTH/2-DECK_HALF_WIDTH
    rng=lambda key,unit=' mm':'–'.join(f'{x:.2f}' for x in cf[key])+unit
    summary=f'''# Complete tracked excavator — arm60 R3 / Track R5

A complete mechanical vehicle built around the unchanged R4 arm60 and four V6-U60 actuators. Each track has its gearmotor and final reduction inside the sprocket hub and a spring-loaded recoil idler at the front (Track R5, [`../track_wheel/`](../track_wheel/README.md)), with pinned steel track joints and road and carrier rollers. A recessed, bearing-supported geared slew carries the upper body. The R3 upper body follows the Cat 320 layout: cab front-left, tank housing and stepped toolbox front-right, an engine hood with a battery hatch, and a curved counterweight on the {TAIL_RADIUS:g} mm tail-swing radius. Two 18650 cells sit in a cradle sized from manufacturer datasheets.

**Digital validation: {'PASS' if all_pass else 'INCOMPLETE — inspect reports'}. Physical prototype testing has not been performed.** CAD clearance passes apply to the documented reference samples; full independent boom/slew travel includes known bucket/track collisions managed by the operator. The 0.15 kg bucket load used in calculations is a study case, not a payload rating. Motor torque/thrust, printing tolerances, layer strength, harness clearance and coordinated boom control require hardware verification before loaded operation.

![Complete excavator](images/overview.png)

## Open and build

- Open `3D_preview.html` directly in a browser; it works offline. Arm and slew controls, a battery-bay view with the hood hatch removed and a mechanism view are included. The preview permits full 0–60 mm boom stroke at every angle within ±150°, with independent controls. Track controls replay the loaded contact simulation, with pause, time scrub, playback speed and a highlighted shoe. Shoes, pins, bushings, sprocket hubs with their pinions, rollers, the sprung idler yokes and springs, and ground travel move together.
- Import `step/excavator_complete.step` for the full assembly. `step/` also contains every new printed part; `stl/` contains their print orientations, including the mirrored left track frame (`TW06_track_frame_left`).
- The track wheel unit has its own folder, [`../track_wheel/`](../track_wheel/README.md): section, exploded and x-ray views and physics playback in `../track_wheel/3D_preview.html`, plus its own checks and simulations.
- Build the retained arm from `../excavator_arm_60mm/` and four actuators from `../actuator_v6/stl/V6-U60/`. The delivery ZIP preserves these relative paths and includes the actuator boards and guides.
- Read [assembly and commissioning](ASSEMBLY.md), [BOM](BOM.md), `build_guide.pdf`, `dimension_sheet.pdf` and `simulation_report.pdf` before making parts. Printer-bed splitting is deferred as requested.

## Track R5: in-hub final drive and recoil idler

![Track wheel unit](../track_wheel/images/unit.png)

Each track side is the unit in [`../track_wheel/`](../track_wheel/README.md), which has its own CAD, checks, simulations and viewer.

- **Final drive.** A Pololu 37D 150:1 gearmotor sits in a stationary housing bolted to the track frame. A steel 12-tooth pinion on its offset shaft drives a 21-tooth internal ring in the rotating hub cap ({tw.HUB_RATIO:.2f}:1). The sprocket hub turns on a 61808 and a 6809 thin-section bearing around the housing, as a full-size final drive turns its sprocket. No drive shaft, coupling or motor strap crosses the chassis any more.
- **Drive rating.** At the 1.0 A driver current limit each sprocket gives {dr['torque_at_current_limit_Nm']:.2f} N m ({dr['torque_limit_tractive_force_N']:.1f} N chain pull). The excavator needs {dr['grade_torque_Nm_each']:.2f} N m per track on a 10° grade and {dr['skid_turn_torque_Nm_each']:.2f} N m to skid-turn. No-load speed is {rating['sprocket_no_load_rpm']:.1f} rpm, {dr['no_load_speed_m_s']:.3f} m/s.
- **Recoil idler.** The idler yoke slides in a channel in the track frame. A C-600-072-1500 spring pushes it forward with {tw.spring_state()['force']:.0f} N, and an M6 adjuster sets the preload. When a stone or a bar jams in the track the idler can recoil {tw.recoil_travel():.1f} mm to a hard stop. The preload keeps the strand under the sprocket tight when reversing at the current limit: {wc['reverse_wall']['stall']['bottom_rear_strand_N']:.1f} N in the reverse-into-a-wall simulation. With the R4 spring (15 N) it went slack and the sprocket kept turning.
- **Carriers.** The spring pulls the top run straight, so the R5 carriers have Ø{2*RETURN_ROLLER_R:g} mm rims {CARRIER_LIFT:g} mm above that line, at X = ±{abs(RETURN_ROLLERS[0]):g}. In the loaded simulation they carry {-carrier[0]:.2f} / {-carrier[1]:.2f} N and roll with the run. At the R4 size the run lifted up to 2.8 mm off them.

| Final drive section | Recoil section |
|---|---|
| ![Final drive section](../track_wheel/images/final_drive_section.png) | ![Recoil section](../track_wheel/images/recoil_section.png) |

### Chain, rollers and stance (from Track R4)

The chain follows Berco pin-and-bushing architecture: rounded sprocket pockets engage replaceable Ø6 steel sleeves on Ø3 pins. Lower and carrier rollers have outer guide flanges with 0.6 mm clearance per side; the idler supports the two rails and guides both sides. The sprocket and idler are raised 2 mm relative to the central ground run so the three lower rollers carry the main chassis load. Exact 20 mm link pitch is retained with sloping transition links on the ground run, a dip in the top run between the carriers and 0.201 mm initial idler retraction. Painted witness marks make passive wheel motion visible.

The 54 mm shoes sit on 340 mm centres: {2*TRACK_Y+SHOE_WIDTH:g} mm overall versus the {2*DECK_HALF_WIDTH:g} mm R3 upper platform, leaving {margin:g} mm beyond each side. The bridge, track frames, axles and spacers have been widened together. See [Berco and Cat 320 references and model adaptations](references/TRACK_SYSTEM.md). The loaded simulation supports {gr['loaded']['total_supported_mass_kg']:.3f} kg on one track and drives the carriage through shoe/floor contact. The browser replays this straight-travel result on both sides; it includes forward/reverse full chain circuits and braking.

![Sprocket, roller guidance and width comparison](images/track_interfaces.png)

## R3 upper body

![R2 and R3 upper body from the same cameras](images/r2_r3_comparison.png)

R2 left most of the deck empty: a rectangular service box behind the cab, no tail shape, and a battery cassette with a loose 71 × 46 mm cavity that had never been checked against real cells. R3 rebuilds everything above the slew deck from the Cat 320 layout:

- **Deck:** {2*DECK_HALF_WIDTH:g} mm wide, with a rear arc on the {TAIL_RADIUS:g} mm tail-swing radius (Cat 320: 2,830 mm at 1:15), a boom-foot nose and a 12 mm perimeter rim that reads as the upper-frame side members.
- **Cab:** the R2 cab ({CAB_SIZE[0]:g} × {CAB_SIZE[1]:g} × {CAB_SIZE[2]:g} mm), moved forward to the machine's {lay['cab_side']} as on the Cat 320.
- **Front right:** a tank housing with a filler cap, and a toolbox with an access step and tread grooves.
- **Engine hood:** full width behind the cab, with side louvres, a valve-cover nose, an exhaust stack and a removable battery hatch.
- **Counterweight:** a curved shell that clamps the {BALLAST_BOX[1]-BALLAST_BOX[0]:.0f} × {2*BALLAST_BOX[2]:.0f} × {BALLAST_BOX[3]:.0f} mm steel ballast plate (about {BALLAST_KG:.2f} kg) through a rubber pad.
- **Fasteners:** every shell bolts down with standard M3/M4 screws into nuts held in hex pockets under the deck. The packaging check confirms that all {fasteners} upper-body screws fully engage their nuts and that no tip reaches below the deck underside.

The deck is still 48 mm lower than R1, and the removable skirt still encloses the slew mechanism, ending {pk['visible_bridge_to_skirt_gap_mm']:g} mm above the bridge. The boom/slew interlock remains removed: operators can lower the boom through its full stroke at any slew angle and manage bucket/track clearance during digging.

## 18650 battery bay

![Battery bay with the hood hatch removed](images/battery_bay.png)

The cradle is sized from published datasheets: [Samsung INR18650-25R](https://www.akkuman.de/shop/mediafiles/PDF/18650%20Lithium/samsung%20inr18650-25r%2036v%202550mah%208c%2020a.pdf) (Samsung SDI, Mar. 2013), [LG INR18650HG2](https://files.batteryjunction.com/frontend/files/lg-hg2-18650.pdf) (BCY-PS-HG2-Rev0) and [Panasonic NCR18650B](https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/196/Panasonic-NCR18650B-datasheet.pdf). These links are retailer and forum copies of the manufacturer documents. It accepts flat-top, unprotected cells from Ø{CELL_DIAMETER_RANGE[0]:.1f} to {CELL_DIAMETER_RANGE[1]:.1f} mm and {CELL_LENGTH_RANGE[0]:.1f} to {CELL_LENGTH_RANGE[1]:.1f} mm long. The cells are built as a welded 2S1P pack with {NICKEL_STRIP:g} mm nickel strip, a {CELL_SEPARATOR:g} mm separator, end insulators and PVC wrap. The finished pack measures {rng('pack_width_range_mm')} wide, {rng('pack_height_range_mm')} high and {rng('pack_length_range_mm')} long.

- Two Ø{2*GROOVE_R:g} mm grooves on a {GROOVE_PITCH:g} mm pitch locate the cells. The {CRADLE_INNER_LENGTH:g} mm between the end walls leaves room for {END_PAD['free_mm']:g} mm foam end pads.
- A retainer bar presses a {TOP_PAD['free_mm']:g} mm foam pad onto the pack with two M3 × 20 screws.
- Across the whole datasheet range, the minimum radial clearance is {cf['minimum_radial_clearance_mm']:.2f} mm. The end pads compress to {rng('end_pad_compressed_range_mm')} and the top pad to {rng('top_pad_compressed_range_mm')}. The largest and smallest packs have zero CAD intersection with the cradle.
- **Service:** remove the four M3 × 12 hatch screws and the two retainer screws, then lift the pack straight out. The BMS and both converters stay on the tray. The CAD check lifts the pack from 0 to 80 mm: {bs['exact_intersections']} exact intersections, {len(bs['collisions'])} collisions and {bs['pack_to_opening_margin_mm']:.1f} mm margin to the hatch opening.
- `22_fit_coupon` includes a Ø{2*GROOVE_R:g} mm groove gauge. Print it first and check a real cell in it.

Button-top or protected cells, about 67–70 mm long, do not fit this cradle.

## Mechanical specification

| Feature | Design |
|---|---|
| Tracks | 34 shoes per side, 20 mm pitch, 54 mm triple-grouser pad width, Ø3 × 56 pins, Ø6 × Ø3.1 × 17 steel sleeves |
| Wheels | 12-tooth bushing-drive sprockets; 220 mm nominal centres, 219.799 mm in the assembly pose |
| Ground support | End-wheel axes Z46.321; 2 mm end rise; central road rollers at Z29; conservative contact half-length 79.30 mm |
| Support | 3 flanged road rollers + 2 flanged Ø{2*RETURN_ROLLER_R:g} carriers per track; recoil idler on a C-600-072-1500 spring, {tw.spring_state()['force']:.0f} N preload, {tw.recoil_travel():.1f} mm recoil to a hard stop, 0–4 mm adjuster |
| Track centres | 340 mm; 394 mm overall shoe width, 396 mm pin envelope |
| Drive | Pololu 37D 150:1 gearmotor inside each sprocket hub with a 12:21 internal gear stage; 61808 + 6809 hub bearings; {dr['torque_at_current_limit_Nm']:.2f} N m at the 1.0 A limit, {rating['sprocket_no_load_rpm']:.1f} rpm no-load |
| Slew | Module 1.5, 96:20 involute gears; two 6004 bearings 40 mm apart; Ø20 steel spindle |
| Slew control | ±150° independent of boom stroke; 6°/s commissioning limit; no slip ring |
| Arm mount | Original base shifted to (45,0,134) mm; four M6 bolts at X=13/121, Y=±65 |
| Upper body | Cat 320 layout, {2*DECK_HALF_WIDTH:g} mm wide; {TAIL_RADIUS:g} mm tail-swing radius (measured {lay['measured_max_radius_mm']:.1f} mm) |
| Cab | 120 × 70 × 118 mm, based on the Cat 320 drawing at 1:15; front-left at X{HOOD_FRONT_X:g} to {HOOD_FRONT_X+CAB_SIZE[0]:g}; seat, consoles and glazing |
| Body height | Deck Z134, lowered 48 mm; hood and counterweight Z{HOOD_TOP_Z:g}, cab roof Z{CAB_ROOF_Z:g}; skirt leaves 12 mm above the bridge |
| Battery | Two flat-top 18650 cells (datasheet Ø{CELL_DIAMETER_RANGE[0]:.1f}–{CELL_DIAMETER_RANGE[1]:.1f} × {CELL_LENGTH_RANGE[0]:.1f}–{CELL_LENGTH_RANGE[1]:.1f} mm), welded 2S1P pack in a fitted cradle under the hood hatch; regulated 12 V and 6 V rails |
| Ballast | Steel {BALLAST_BOX[1]-BALLAST_BOX[0]:.0f} × {2*BALLAST_BOX[2]:.0f} × {BALLAST_BOX[3]:.0f} mm plate inside the counterweight, about {BALLAST_KG:.2f} kg |
| Calculated mass | {loads['nominal_mass_kg']:.2f} kg using full modeled PETG/steel volumes and declared hardware masses |

The sprockets have rounded bushing pockets with swept entry/exit relief, six open web windows and 0.5 mm nominal tooth-tip clearance to the shoe web. Public manufacturer images establish the architecture; the tooth profile is calculated for this model’s pitch and bushing diameter. Bearing spacers contact inner or outer races deliberately. The hub bearings carry the sprocket loads, so the motor shaft carries only the gear mesh force.

## Verification

- {len(export['parts'])} new printed designs, plus two mirrored variants: watertight, consistently wound, single-solid STL/STEP checks. Complete assembly: {export['assembly_solids']} CAD solids.
- {v['assembly']['exact_intersections']} exact assembly intersections and {v['motion']['exact_cross_system_intersections']} distinct cross-system checks: {len(v['assembly']['collisions'])+len(v['motion']['collisions'])} collisions inside the CAD reference envelope above the 0.05 mm³ tolerance. Arm controls sampled on a 5×5×5 grid; cross-system samples use boom ≥15 mm or slew within ±20°, drawn from 11 slew angles; upper body checked at 61 angles.
- Gear mesh: 61 samples over a full tooth repeat; peak overlap {v['motion']['maximum_gear_intersection_mm3']:.3g} mm³. Track articulation: 41 samples from 32° wrap to 8° back-bend.
- Powered track fixture: {tr['steps']} MuJoCo steps at {tr['time_step_s']*1000:g} ms, 34 links and 34 hinges enforced by 68 point constraints. Maximum hinge error {tr['max_hinge_error_mm']:.6f} mm. All {tr['contact_convex_pieces']} sprocket contact pieces are verified as present in the model. Every shoe completes at least {tr['minimum_forward_circuits']:.2f} forward and {tr['minimum_reverse_circuits']:.2f} reverse circuits.
- Loaded track/floor contact: {gr['steps']} steps, {gr['loaded']['total_supported_mass_kg']:.3f} kg supported, forward/reverse travel {gr['loaded']['forward_speed_m_s']:.4f}/{gr['loaded']['reverse_speed_m_s']:.4f} m/s. Mean floor reaction {gr['loaded']['mean_ground_normal_N']:.2f} N against {gr['loaded']['weight_N']:.2f} N weight; final speed {gr['loaded']['final_speed_m_s']:.6f} m/s.
- Roller function under load: mean upward road-roller reactions {', '.join(f'{x:.2f}' for x in gr['wheel_checks']['mean_vertical_support_N'][2:5])} N. The road rollers carry {100*sum(gr['wheel_checks']['mean_vertical_support_N'][2:5])/gr['loaded']['weight_N']:.1f}% of the supported weight. Both carriers support the return run, and all six passive wheels rotate in both directions.
- Side guidance: ±{tr['lateral_test_force_N']:g} N on the free chain, {tr['max_lateral_drift_mm']:.3f} mm maximum lateral motion, with both guide flanks engaged. Suspended road rollers are unloaded; their spin requirement is checked in the floor-contact test.
- Actual CAD at simulated track poses: {sum(r['sampled_poses'] for r in track_cad)} forward/reverse samples, {sum(r['exact_intersections'] for r in track_cad)} exact intersections, no overlap above the 0.5 mm³ contact allowance. The shoe rail contact meshes include the hinge-entry scallop; this catches carrier-roller interference hidden by the former short-box approximation.
- Upper body and battery bay: {pk['status']}. Measured tail radius {lay['measured_max_radius_mm']:.1f} mm; all {fasteners} upper-body screws engage their full nut height; cell fit checked across the datasheet range; pack lift-out {bs['exact_intersections']} exact intersections, {len(bs['collisions'])} collisions. Battery budget: 36 W regulated output requires at most {pk['power']['maximum_calculated_pack_current_A']:.2f} A at 6.2 V and assumed 85% efficiency; actual converter/cell performance needs measurement.
- CAD reference boundary: {v['motion']['collision_reference_envelope']['boundary_configurations']} additional configurations; a known collision outside that region is retained as a negative control. These samples do not limit the controls.
- Stability: {loads['stability_configurations']:,} sampled combinations including 0/0.15 kg bucket load, +20% arm mass, -10% base mass and an adverse 5° slope. Minimum calculated gravity-line margin {loads['worst_stability']['margin_mm']:.1f} mm inside the support rectangle. These are quasi-static assumptions, not a slope or payload rating.
- Required static actuator thrust with the study load: {', '.join(f'{x:.1f}' for x in loads['static_actuator_thrust_N_per_cylinder'])} N per boom/stick/bucket cylinder. Procurement targets with a 2× margin: {', '.join(f'{x:.1f}' for x in loads['actuator_selection_thrust_N_with_2x_margin'])} N. Real gearbox axial capacity remains unverified.
- Reduced vehicle dynamics check forward/reverse travel, a skid turn, braking, grade traction, power-loss rollback and slew limits. The power-loss case deliberately demonstrates that powered holding is not a parking brake.
- Track wheel unit ([`../track_wheel/`](../track_wheel/README.md)): {wv['interference']['pairs_tested']} exact solid pairs with {len(wv['interference']['hits'])} intersections. Gear mesh clash-free at 6.9–7.1 mm centre distance. All {len(wv['fits'])} fits and {len(wv['fasteners'])} fastener engagements pass. Spring on its stop at {min(c['force_at_stop_N'] for c in wv['spring']['cases']):.0f}–{max(c['force_at_stop_N'] for c in wv['spring']['cases']):.0f} N, below its {wv['spring']['max_load_N']:.1f} N rating. MuJoCo cases with the motor model:
  - reverse stall at the current limit;
  - a Ø6 rod crossing;
  - a 4 mm stone carried round the idler: {wc['debris']['max_recoil_mm']:.1f} mm recoil;
  - a 5 mm stone: idler on its stop;
  - ±20 N side pulls.
  All pass with no tooth skips. The R4-spring negative control fails as expected.
- Retained arm60 validation (unchanged arm): 134 poses, 990 exact intersections, zero interference; report in `simulation/inherited_arm/validation.json`.
- Browser: {br['arm_and_slew_cases']} arm/slew cases match Python and actual rendered cylinder endpoints; offline, mobile, controls and gear direction checks pass. Track playback checks {br['track_motion']['sampled_times']} times, including interpolated poses, and verifies rendered pin closure, wheel phase, carriage take-up, travel, pause and reset.

The collision checks are sampled, not a continuous proof. The contact simulation uses ideal hinge constraints and simplified shoe geometry; chassis rail collisions are omitted. The fixed fixture has no floor; the loaded case includes a rigid floor and guides chassis pitch/roll/yaw; it does not model soil, wear, motor heating or printed elasticity. No FEA or physical strength certification is claimed. Fastener threads, flexible cables and tool access need physical trial assembly. A fully lowered, tucked-in arm can hit a track during sideways slew; avoiding that collision is an operating responsibility. The original failing unrestricted case is preserved in `simulation/unrestricted_lowered_body.json`. Some arm poses extend below a solid floor and require a recess or restricted travel. Full hardware commissioning also requires slew feedback/independent direction limits and measured boom synchronisation, as explained in the assembly guide.

## Reproduce

Use Python 3.11, the pinned packages in `source/requirements.txt`, CadQuery's system libraries and Node/Playwright with Chromium. All commands are finite; no web server is needed.

```sh
(cd ../track_wheel/source && python build_track_wheel.py && python validate_track_wheel.py)
(cd ../track_wheel/source && for c in fixture reverse_wall reverse_wall_r4spring obstacle debris debris_5mm lateral lateral_r4spring report; do python simulate_track_wheel.py --case $c; done)
(cd ../track_wheel/source && python build_viewer.py && node check_viewer.cjs && python build_docs.py)
python source/build_vehicle.py
python source/validate_vehicle.py --stage assembly
python source/validate_vehicle.py --stage motion
python source/validate_vehicle.py
python source/validate_inherited_arm.py
python source/validate_packaging.py
python source/simulate_track.py
python source/simulate_track.py --ground
python source/validate_track_motion.py
python source/simulate_vehicle.py
python source/build_viewer.py
cd source && npm install && npx playwright install chromium && cd ..
node source/check_viewer.cjs
python source/build_docs.py
python source/package_delivery.py
```

Run from this folder, or use the script paths from the repository root. Each command finishes in under ten minutes; the vehicle validation is split into cached stages for that reason. Keep the sibling track_wheel, arm60 and V6 folders. `source/design.py` and `source/build_vehicle.py` are the new dimensional authority; arm dimensions remain in the original `kinematics.py`. The simulation reports contain units, force assumptions and scope. `SHA256SUMS.txt` records delivery-file checksums. Bundled three.js is MIT-licensed; the model has no newly assigned license.
'''
    (ROOT/'README.md').write_text(summary)
    drawing();track_drawing()
    blocks=[('title','Tracked arm60 — simulation report'),('text','Digital prototype R3 with Track R5 (in-hub final drive, recoil idler; details in track_wheel/README.md). These results describe the supplied CAD and explicit numerical models. They do not establish a tested physical payload or certify printed strength.'),('image',ROOT/'images/overview.png'),('heading','CAD and motion'),('text',f"Assembly intersections: {v['assembly']['exact_intersections']}; cross-system intersections: {v['motion']['exact_cross_system_intersections']}. Collisions above tolerance: {len(v['assembly']['collisions'])+len(v['motion']['collisions'])}. Gear cycle: 61 samples, maximum overlap {v['motion']['maximum_gear_intersection_mm3']:.4g} mm³. Track pitch closure error {v['track']['max_pitch_error_mm']:.3g} mm."),('text',v['scope']),('page',''),('heading','Track R4 mechanical changes'),('image',ROOT/'images/track_interfaces.png'),('text','Adapted from Berco sprocket, track-chain, roller and idler references. Rounded tooth pockets drive replaceable steel bushings; outer guide flanges retain lateral running clearance. '+f'The {2*TRACK_Y+SHOE_WIDTH:g} mm shoe envelope extends {margin:g} mm beyond each side of the {2*DECK_HALF_WIDTH:g} mm R3 upper platform. '+'See references/TRACK_SYSTEM.md for original manufacturer URLs and images.'),('page',''),('heading','Driven track contact simulation')]
    blocks.append(('table',[
        ['Track contact test','Result'],
        ['Engine / status',tr['engine']+' / '+tr['status']],
        ['Duration / integration',f"{tr['steps']*tr['time_step_s']:g} s / {tr['steps']:,} steps at {tr['time_step_s']*1000:g} ms"],
        ['Links / hinge point constraints',f"{tr['links']} / {tr['hinge_constraints']}"],
        ['Forward / reverse mean speed',f"{tr['forward_mean_speed_rad_s']:.4f} / {tr['reverse_mean_speed_rad_s']:.4f} rad/s (command ±{tr['target_speed_rad_s']:g})"],
        ['Forward rotation / total rotation',f"{tr['peak_angle_rad']:.3f} / {tr['total_rotation_rad']:.3f} rad"],
        ['Speed after controlled stop',f"{tr['final_speed_rad_s']:.6f} rad/s"],
        ['Peak applied torque / limit',f"{tr['peak_applied_torque_Nm']:.3f} / {tr['torque_limit_Nm']:.2f} N m"],
        ['Shoe path / ideal pitch travel',f"{tr['marker_path_mm']:.1f} / {tr['expected_pitch_travel_mm']:.1f} mm; ratio {tr['chain_travel_ratio']:.3f}"],
        ['Maximum hinge / lateral error',f"{tr['max_hinge_error_mm']:.6f} / {tr['max_lateral_drift_mm']:.6f} mm"],
        ['Idler displacement',f"{tr['idler_travel_mm'][0]:.3f} to {tr['idler_travel_mm'][1]:.3f} mm (recoil stop {tr['idler_travel_limits_mm'][0]:.1f}, nose +{tr['idler_travel_limits_mm'][1]:.1f})"],
        ['Recoil spring / preload',f"{tr['idler_spring']}, {tr['idler_spring_N_per_mm']:.2f} N/mm, {tr['idler_preload_N']:.1f} N"],
        ['Carrier support / largest lift of the run',f"{-tr['wheel_checks']['mean_vertical_support_N'][5]:.2f} / {-tr['wheel_checks']['mean_vertical_support_N'][6]:.2f} N; {max(tr['wheel_checks']['carrier_lift_mm']['maximum']):.2f} mm (limit {tr['wheel_checks']['carrier_lift_mm']['allowed']:.1f})"],
        ['Sprocket contact pieces present',str(tr['contact_convex_pieces'])],
        ['Alternating side load / maximum lateral movement',f"±{tr['lateral_test_force_N']:g} N / {tr['max_lateral_drift_mm']:.3f} mm"],
        ['Left / right guide-contact observations',f"{tr['guide_contacts']['left']} / {tr['guide_contacts']['right']}"],
        ['Minimum complete circuits, forward / reverse',f"{tr['minimum_forward_circuits']:.2f} / {tr['minimum_reverse_circuits']:.2f}"],
    ]))
    blocks.append(('text',tr['scope']))
    if (ROOT/'images/track_dynamics.png').exists():blocks.append(('image',ROOT/'images/track_dynamics.png'))
    blocks += [('page',''),('heading','Loaded floor-contact simulation'),('text',gr['scope']),('text',f"Actual CAD checked at {sum(r['sampled_poses'] for r in track_cad)} recorded track poses: {sum(r['exact_intersections'] for r in track_cad)} exact intersections, no overlap above 0.5 mm3. This allowance covers soft contact and polygonal mesh approximation; these are sampled checks."),('table',[
        ['Loaded track test','Result'],['Status',gr['status']],
        ['Supported mass / weight',f"{gr['loaded']['total_supported_mass_kg']:.3f} kg / {gr['loaded']['weight_N']:.2f} N"],
        ['Mean floor reaction',f"{gr['loaded']['mean_ground_normal_N']:.2f} N"],
        ['Road roller share of supported weight',f"{100*sum(gr['wheel_checks']['mean_vertical_support_N'][2:5])/gr['loaded']['weight_N']:.1f}%"],
        ['Road roller upward reactions (rear / centre / front)',', '.join(f'{x:.2f}' for x in gr['wheel_checks']['mean_vertical_support_N'][2:5])+' N'],
        ['Carrier downward reactions (rear / front)',', '.join(f'{-x:.3f}' for x in gr['wheel_checks']['mean_vertical_support_N'][5:])+' N'],
        ['Passive wheel forward angular speeds',', '.join(f'{x:.2f}' for x in gr['wheel_checks']['forward_rad_s'][1:])+' rad/s'],
        ['Passive wheel reverse angular speeds',', '.join(f'{x:.2f}' for x in gr['wheel_checks']['reverse_rad_s'][1:])+' rad/s'],
        ['Forward / reverse travel',f"{gr['loaded']['forward_speed_m_s']:.4f} / {gr['loaded']['reverse_speed_m_s']:.4f} m/s"],
        ['Pitch prediction at commanded speed',f"{gr['loaded']['pitch_speed_m_s']:.4f} m/s"],
        ['Final travel speed',f"{gr['loaded']['final_speed_m_s']:.6f} m/s"],
        ['Minimum complete circuits, forward / reverse',f"{gr['minimum_forward_circuits']:.2f} / {gr['minimum_reverse_circuits']:.2f}"],
        ['Maximum hinge error',f"{gr['max_hinge_error_mm']:.6f} mm"],
    ]),('image',ROOT/'images/track_ground_dynamics.png'),('text','Track references: Berco drive sprockets, rollers, track chains and idlers; Caterpillar 320 technical specifications, pages 2, 3, 4 and 20. See references/TRACK_SYSTEM.md for source dimensions, model adaptations and simulation scope. The offline viewer interpolates the recorded rigid-body poses; it does not run a live terrain solver.')]
    blocks += [('page',''),('heading','Stability and load requirements'),('text',loads['assumptions']),('text',f"Mass {loads['nominal_mass_kg']:.3f} kg. Minimum calculated support margin {loads['worst_stability']['margin_mm']:.2f} mm over {loads['stability_configurations']} configurations. Worst case: strokes {loads['worst_stability']['strokes_mm']}, slew {loads['worst_stability']['slew_deg']:.0f}°, 0.15 kg load."),('text',f"Slew overturning moment {loads['max_overturning_moment_Nm']:.2f} N m; bearing-couple reaction {loads['slew_bearing_couple_reaction_N']:.1f} N; steel spindle bending estimate {loads['slew_spindle_bending_MPa']:.2f} MPa."),('text',f"Per-cylinder static thrust, boom/stick/bucket: {', '.join(format(x, '.1f') for x in loads['static_actuator_thrust_N_per_cylinder'])} N. Select and bench-test against twice these values. These calculations omit soil reaction and dynamic arm loads."),('text',f"Grade torque per drive {loads['drive']['grade_torque_Nm_each']:.3f} N m; skid-turn torque {loads['drive']['skid_turn_torque_Nm_each']:.3f} N m. Required continuous motor rating 1.2 N m. The assumed friction coefficient is 0.30."),('text',f"Simplified Lewis gear stress {loads['slew']['conservative_Lewis_tooth_stress_MPa']:.2f} MPa against an assumed printed allowable of 8 MPa; pin bending {loads['track_pin']['bending_MPa']:.1f} MPa against assumed steel yield 200 MPa. These are analytic estimates, not FEA or material coupon results."),('page',''),('heading','Vehicle and slew dynamics'),('image',ROOT/'images/vehicle_dynamics.png'),('text',dy['scope']),('text',f"Drive shaft/bearing upper bound: outer bearing reaction {dy['drive_bearings']['outer_bearing_reaction_N']:.1f} N; steel shaft bending {dy['drive_bearings']['drive_shaft_bending_MPa']:.1f} MPa. Specify 608 static capacity at least 1000 N and steel yield at least 200 MPa; both retain at least a 2x calculated static margin."),('text','Power loss on a grade produces rollback in the negative control. Commission on a level surface with chocks; do not infer a fail-safe parking brake from a gearmotor.'),('heading','Required physical validation'),('text','Bearing and pin fits; motor continuous torque/current/thermal behavior; gearbox axial thrust capacity; paired boom synchronisation; cable loop and direction-limit commissioning; print layer adhesion, deflection, creep and endurance. Record these before a general print or payload release.')]
    blocks += [('page',''),('heading','Upper body, battery bay and independent motion'),('image',ROOT/'images/battery_bay.png'),
        ('text',f"R3 upper body in the Cat 320 layout: cab envelope {pk['cab_envelope_mm']} mm at the machine's {lay['cab_side']} front; measured tail radius {lay['measured_max_radius_mm']:.2f} mm against {TAIL_RADIUS:g} mm (2,830 mm at 1:15). Deck lowered {pk['lowered_deck_mm']:g} mm; exposed bridge/skirt gap {pk['visible_bridge_to_skirt_gap_mm']:g} mm. Cab estimates use the Cat 320 page 4 drawing, not factory cab dimensions."),
        ('table',[['Battery bay check','Result'],
            ['Cell envelope (Samsung 25R, LG HG2, Panasonic NCR18650B datasheets)',f'Ø{CELL_DIAMETER_RANGE[0]:.1f}–{CELL_DIAMETER_RANGE[1]:.1f} × {CELL_LENGTH_RANGE[0]:.1f}–{CELL_LENGTH_RANGE[1]:.1f} mm, flat-top, unprotected'],
            ['Welded 2S1P pack width / height / length',f"{rng('pack_width_range_mm','')} / {rng('pack_height_range_mm','')} / {rng('pack_length_range_mm')}"],
            ['Cradle grooves',f'Ø{2*GROOVE_R:g} mm at {GROOVE_PITCH:g} mm pitch, {CRADLE_INNER_LENGTH:g} mm between end walls'],
            ['Minimum radial clearance',f"{cf['minimum_radial_clearance_mm']:.2f} mm"],
            ['End pad compressed (free 4 mm)',rng('end_pad_compressed_range_mm')],
            ['Top pad compressed (free 3 mm)',rng('top_pad_compressed_range_mm')],
            ['CAD intersection, largest / smallest pack',' / '.join(f"{c['cradle_intersection_mm3']:g}" for c in cf['cad_extremes'])+' mm³'],
            ['Pack lift-out 0–80 mm',f"{bs['exact_intersections']} exact intersections, {len(bs['collisions'])} collisions"],
            ['Pack to hatch-opening margin',f"{bs['pack_to_opening_margin_mm']:.1f} mm"],
            ['Upper-body screws checked',f"{fasteners}; all engage the full nut; no tip below the Z124 deck underside"]]),
        ('text',cf['scope']),
        ('text',f"2S power budget: 36 W shared output, 6.2 V cutoff, 85% assumed efficiency: {pk['power']['maximum_calculated_pack_current_A']:.2f} A maximum. Required cells >=15 A, BMS >=10 A, pack controller limit 8 A. Thermal performance, current limits and runtime require hardware measurement."),
        ('text',v['motion']['collision_reference_envelope']['description']),('text',f"Reference boundary tested at {v['motion']['collision_reference_envelope']['boundary_configurations']} configurations. The negative control outside this region has {v['motion']['collision_reference_envelope']['negative_control_collision_mm3']:.1f} mm³ collision. The preview permits that pose; operators manage track clearance.")]
    pdf(ROOT/'simulation_report.pdf',blocks)
    guide=[('title','Tracked arm60 — build guide'),('image',ROOT/'images/overview.png'),('page',''),('heading','Track R5 interfaces'),('image',ROOT/'images/track_interfaces.png'),
        ('page',''),('heading','Track wheel unit: final drive and recoil idler'),('text','Full unit documentation, BOM and assembly sequence: track_wheel/README.md and track_wheel/BOM.md.'),
        ('image',REPO/'track_wheel/images/final_drive_section.png'),('image',REPO/'track_wheel/images/recoil_section.png')]
    for para in (ROOT/'ASSEMBLY.md').read_text().split('\n\n'):
        if para.startswith('# '):continue
        if para.startswith('## '):
            if para=='## Commissioning sequence':guide.append(('page',''))
            guide.append(('heading',para[3:]))
        elif para.startswith('|'):
            guide.append(('table',[[x.strip() for x in row.strip('|').split('|')] for row in para.splitlines() if not row.startswith('|---')]))
        elif para.startswith('1. '):
            for line in para.splitlines():guide.append(('text',line))
        else:guide.append(('text',para))
    pdf(ROOT/'build_guide.pdf',guide)
    print('Generated BOM, README, dimension sheet, build guide and simulation report')

if __name__=='__main__':build()

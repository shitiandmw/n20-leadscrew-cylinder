"""R3 upper body: Cat 320 layout around the unchanged arm60 base.

Final (lowered) coordinates in mm: X forward, +Y machine left, Z up.
The cab sits front-left as on the Cat 320. A tank housing and stepped toolbox
fill the front right, the engine hood spans the width behind them, and a curved
counterweight sets the 189 mm tail radius. The two 18650 cells sit in a fitted
cradle under a removable hood hatch.
"""
import math
import cadquery as cq
import numpy as np
from shapely.geometry import Point, box as rect
from design import *

YELLOW=(.91,.60,.07); DARK=(.13,.17,.20); STEEL=(.63,.69,.73)
GLASS=(.22,.41,.47); RED=(.68,.14,.09); CELL=(.25,.48,.28); BOARD=(.15,.37,.29)
NICKEL=(.74,.76,.72); FOAM=(.20,.22,.24); BLACK=(.07,.08,.09)
WALL=2.4
UPPER_PARTS=['16_upper_deck','18_counterweight','19_engine_hood','20_cab_frame','21_cab_roof','23_equipment_tray',
    '25_battery_retainer','27_operator_seat','28_operator_console','29_hood_hatch','30_tank_housing',
    '31_toolbox_step','32_exhaust_stack','33_cell_cradle']


def box(x0,x1,y0,y1,z0,z1):
    return cq.Workplane('XY').box(x1-x0,y1-y0,z1-z0).translate(((x0+x1)/2,(y0+y1)/2,(z0+z1)/2))

def cyl(r,z0,z1,x=0,y=0):
    return cq.Workplane('XY').center(x,y).circle(r).extrude(z1-z0).translate((0,0,z0))

def ycyl(r,y0,y1,x=0,z=0):
    return cq.Workplane('XZ').center(x,z).circle(r).extrude(y1-y0).translate((0,y1,0))

def prism(poly,z0,z1):
    return cq.Workplane('XY').polyline(list(poly.exterior.coords)[:-1]).close().extrude(z1-z0).translate((0,0,z0))

def holes(s,points,r,z0=100,z1=260):
    for x,y in points:s=s.cut(cyl(r,z0,z1,x,y))
    return s

def nut_pockets(s,points,across_flats,bottom,depth):
    for x,y in points:s=s.cut(cq.Workplane('XY').center(x,y).polygon(6,across_flats*2/math.sqrt(3)).extrude(depth+.01).translate((0,0,bottom-.01)))
    return s

def countersink(s,points,hole_radius,head_radius,top):
    depth=head_radius-hole_radius
    for x,y in points:s=s.cut(cq.Solid.makeCone(hole_radius,head_radius,depth,cq.Vector(x,y,top-depth),cq.Vector(0,0,1)))
    return s

def groove_x(s,x0,x1,y,z0,z1,depth):
    """Shallow panel/tread groove cut into a face normal to Y (side walls)."""
    return s.cut(box(x0,x1,y-depth,y+depth,z0,z1))


# ---------------------------------------------------------------- plan view
def deck_plan():
    """Rectangular front, straight sides, rear arc on the tail radius.

    The nose carries the arm60 base plate (X1-133). The plan contains the
    rotating skirt circle (R131.5) everywhere, so the skirt stays hidden.
    """
    body=rect(-TAIL_RADIUS-1,-DECK_HALF_WIDTH,DECK_FRONT_X,DECK_HALF_WIDTH)
    body=body.intersection(Point(0,0).buffer(TAIL_RADIUS,quad_segs=48))
    plan=body.union(rect(DECK_FRONT_X-20,-DECK_NOSE_HALF_WIDTH,DECK_NOSE_X,DECK_NOSE_HALF_WIDTH))
    plan=plan.buffer(-6,quad_segs=6).buffer(6,quad_segs=6)
    return plan.buffer(6,quad_segs=6).buffer(-6,quad_segs=6)

def counterweight_solid(inset,z0,z1,chamfer):
    """Circular segment between the hood joint and the tail-radius arc."""
    r=TAIL_RADIUS-inset;xf=COUNTERWEIGHT_FRONT_X-inset;y=math.sqrt(r*r-xf*xf)
    s=cq.Workplane('XY').moveTo(xf,-y).lineTo(xf,y).threePointArc((-r,0),(xf,-y)).close()
    # Sharp front corners meet the hood side panels; a 45° top chamfer prints face-down.
    return s.extrude(z1-z0).translate((0,0,z0)).edges('>Z').chamfer(chamfer)

def hood_plan():
    main=rect(COUNTERWEIGHT_FRONT_X+.3,-DECK_HALF_WIDTH,HOOD_FRONT_X,DECK_HALF_WIDTH)
    return main.intersection(deck_plan())


# ------------------------------------------------------------- fasteners
# Screw heads seat on the top of each listed stack; nuts sit in hex pockets
# under the deck (or in the named boss), pulled up against the pocket roof.
# validate_packaging.py checks that every tip ends inside its nut pocket and
# that nothing protrudes below the deck where it could reach the slew stops.
M3_NUT=(5.7,2.4); M4_NUT=(7.2,3.2)
DECK_POCKET={'M3':5.0,'M4':6.0}
COUNTERWEIGHT_BOLTS=[(-145.,95.),(-145.,-95.),(-122.,125.),(-122.,-125.)]
HOOD_BOLTS=[(-104.,140.),(-104.,-140.),(-30.,140.),(-30.,-140.)]
TANK_BOLTS=[(-14.,-100.),(42.,-140.)]
TOOLBOX_BOLTS=[(58.,-142.),(76.,-96.)]
TRAY_LEGS=[(-100.,96.),(-100.,-96.),(-31.,96.),(-31.,-96.)]
HATCH=dict(opening=(-101.,-35.,-89.,89.),panel=(-108.,-28.,-96.,96.))
HATCH_SCREWS=[(-104.5,92.5),(-104.5,-92.5),(-31.5,92.5),(-31.5,-92.5)]
EXHAUST=(-62.,-124.)

def cab_point(x,y):
    """R2 cab coordinates (right side, 23 mm further back) to the R3 placement."""
    return (x+CAB_SHIFT_X,-CAB_SIDE*y)

def cab_place(s):
    s=s.translate((CAB_SHIFT_X,0,-SLEW_DROP))
    return s.mirror('XZ') if CAB_SIDE>0 else s

CAB_TIES=[cab_point(x,y) for x,y in [(-40,-149),(59,-149),(-40,-89),(59,-89)]]
SEAT_BOLTS=[cab_point(x,y) for x in [-10,10] for y in [-136,-106]]
CONSOLE_BOLTS=[cab_point(25,-144),cab_point(25,-94)]

def fastener_table():
    """Every fastener that ends in a deck nut pocket (lengths are standard sizes)."""
    rows=[]
    def add(name,points,size,head_z,length,kind):
        for p in points:rows.append(dict(name=name,xy=p,size=size,head_seat_z=head_z,length=length,kind=kind))
    add('Counterweight bolt',COUNTERWEIGHT_BOLTS,'M4',HOOD_TOP_Z,80,'countersunk')
    add('Engine hood bolt',HOOD_BOLTS,'M3',HOOD_TOP_Z,80,'countersunk')
    add('Tank housing bolt',TANK_BOLTS,'M3',HOOD_TOP_Z,80,'countersunk')
    add('Toolbox bolt',TOOLBOX_BOLTS,'M3',TOOLBOX_TOP_Z,45,'countersunk')
    add('Equipment tray leg screw',TRAY_LEGS,'M3',TRAY_TOP_Z,45,'countersunk')
    # Threaded rod: lower end placed inside the pocket, nut on the roof.
    add('Cab tie rod',CAB_TIES,'M3',CAB_ROOF_Z+3,130,'M3 threaded rod, nut and washer on the roof')
    add('Seat bolt',SEAT_BOLTS,'M3',SEAT_BASE_TOP_Z,35,'socket head')
    add('Console bolt',CONSOLE_BOLTS,'M3',CONSOLE_TOP_Z,45,'socket head in a 3 mm counterbore')
    return rows


# ------------------------------------------------------------- 18650 pack
def cell_fit(d,length,wrap,end_insulation):
    """Rest position of one wrapped cell of diameter d in its cradle groove."""
    rw=d/2+wrap;e=(GROOVE_PITCH-(d+CELL_SEPARATOR))/2
    drop=math.sqrt(max((GROOVE_R-rw)**2-e*e,0))
    pack_length=length+2*NICKEL_STRIP+2*end_insulation
    return dict(radial_clearance_mm=GROOVE_R-e-rw,centre_drop_mm=drop,pack_top_z=GROOVE_Z-drop+rw,
                pack_width_mm=2*d+CELL_SEPARATOR+2*wrap,pack_height_mm=d+2*wrap,pack_length_mm=pack_length,
                end_pad_compressed_mm=CRADLE_INNER_LENGTH-pack_length,
                top_pad_compressed_mm=RETAINER_BOTTOM_Z-(GROOVE_Z-drop+rw))


# ------------------------------------------------------------ printed parts
def upper_printed():
    p={}
    def add(n,s,color=YELLOW,quantity=1,material='PETG',note='',orient='upright'):
        p[n]=dict(shape=s.clean(),color=color,kind='printed',quantity=quantity,material=material,note=note,orient=orient)
    plan=deck_plan()
    deck=prism(plan,DECK_Z-10,DECK_Z)
    # A 12 mm perimeter rim reads as the deep upper-frame side members. It is
    # left off the boom-foot nose, where the bucket passes in low poses.
    rim=plan.difference(plan.buffer(-3,join_style=2)).difference(rect(DECK_NOSE_X-8,-DECK_NOSE_HALF_WIDTH-1,300,DECK_NOSE_HALF_WIDTH+1))
    for g in getattr(rim,'geoms',[rim]):deck=deck.union(prism(g,DECK_RIM_Z,DECK_Z-10+.01))
    arm=[(45+x,y) for x in [-32,76] for y in [-65,65]]
    deck=holes(deck,arm,3.3);deck=nut_pockets(deck,arm,10.2,DECK_Z-10,6.2)
    deck=holes(deck,bolt_circle(25,4,math.pi/4),2.7);deck=countersink(deck,bolt_circle(25,4,math.pi/4),2.7,5.2,DECK_Z)
    deck=holes(deck,bolt_circle(56,6),2.2);deck=countersink(deck,bolt_circle(56,6),2.2,4.2,DECK_Z)
    deck=holes(deck,SKIRT_MOUNTS,1.7);deck=countersink(deck,SKIRT_MOUNTS,1.7,3.4,DECK_Z)
    deck=holes(deck,[(-125,0),(-115,0)],2.2);deck=countersink(deck,[(-125,0),(-115,0)],2.2,4.2,DECK_Z)
    deck=deck.cut(cyl(10.2,DECK_Z-11,DECK_Z+1))
    # Harness pass-through near the slew axis, under the hood nose.
    deck=holes(deck,[CABLE_PASS],4)
    for row in fastener_table():
        r,(af,_)=(2.2,M4_NUT) if row['size']=='M4' else (1.7,M3_NUT)
        deck=holes(deck,[row['xy']],r);deck=nut_pockets(deck,[row['xy']],af,DECK_Z-10,DECK_POCKET[row['size']])
    add('16_upper_deck',deck,note='R3 Cat 320 plan: 189 mm tail arc, boom-foot nose, perimeter rim; all shells bolt into captive nuts.',orient='flip')

    # Counterweight: chamfered (printable) curved shell over the steel plate.
    cw=counterweight_solid(0,DECK_Z,HOOD_TOP_Z,6).cut(counterweight_solid(3,DECK_Z-1,HOOD_TOP_Z-3,3))
    bx0,bx1,by,bt=BALLAST_BOX
    for sign in [-1,1]:
        y0,y1=sorted([sign*(by+.5),sign*(by+2.5)])
        cw=cw.union(box(bx0-2.5,COUNTERWEIGHT_FRONT_X-1,y0,y1,DECK_Z,HOOD_TOP_Z-1))
    cw=cw.union(box(bx0-2.5,bx0-.5,-by-2.5,by+2.5,DECK_Z,HOOD_TOP_Z-1))
    # Central rib presses the plate through a 1 mm rubber pad.
    cw=cw.union(box(bx0-1,COUNTERWEIGHT_FRONT_X-1,-1,1,DECK_Z+bt+1,HOOD_TOP_Z-1))
    for x,y in COUNTERWEIGHT_BOLTS:cw=cw.union(cyl(4.6,DECK_Z,HOOD_TOP_Z-1,x,y))
    cw=cw.intersect(counterweight_solid(0,DECK_Z,HOOD_TOP_Z,6))
    cw=holes(cw,COUNTERWEIGHT_BOLTS,2.2);cw=countersink(cw,COUNTERWEIGHT_BOLTS,2.2,4.2,HOOD_TOP_Z)
    band=cyl(TAIL_RADIUS+1,152,154).cut(cyl(TAIL_RADIUS-.8,151,155)).cut(box(COUNTERWEIGHT_FRONT_X-12,0,-200,200,150,156))
    cw=cw.cut(band)  # styling groove around the tail
    add('18_counterweight',cw,note='Curved 189 mm tail-radius shell; clamps the steel ballast plate with internal ribs; four M4 × 80 into deck nuts.',orient='flip')

    # Engine hood: one shell behind the cab and tank housing, lower valve-cover nose.
    hp=hood_plan();nose=rect(-40,-HOOD_NOSE_HALF_WIDTH,HOOD_NOSE_X,HOOD_NOSE_HALF_WIDTH)
    outer=prism(hp,DECK_Z,HOOD_TOP_Z).union(prism(nose,DECK_Z,HOOD_NOSE_TOP_Z))
    outer=outer.edges('|Z').edges('>X').fillet(4)
    inner_main=hp.buffer(-WALL,join_style=2).union(rect(COUNTERWEIGHT_FRONT_X-5,-DECK_HALF_WIDTH+WALL,COUNTERWEIGHT_FRONT_X+5,DECK_HALF_WIDTH-WALL))
    inner=prism(inner_main,DECK_Z-1,HOOD_TOP_Z-WALL).union(prism(nose.buffer(-WALL,join_style=2),DECK_Z-1,HOOD_NOSE_TOP_Z-WALL))
    hood=outer.cut(inner)
    x0,x1,y0,y1=HATCH['opening'];hood=hood.cut(box(x0,x1,y0,y1,HOOD_TOP_Z-WALL-1,HOOD_TOP_Z+1))
    for x,y in HATCH_SCREWS:hood=hood.union(cyl(4,HOOD_TOP_Z-WALL-7.6,HOOD_TOP_Z-WALL+.01,x,y))
    hood=holes(hood,HATCH_SCREWS,1.7);hood=nut_pockets(hood,HATCH_SCREWS,M3_NUT[0],HOOD_TOP_Z-WALL-7.6,3.0)
    for x,y in HOOD_BOLTS:hood=hood.union(cyl(4,DECK_Z,HOOD_TOP_Z-.01,x,y))
    hood=holes(hood,HOOD_BOLTS,1.7);hood=countersink(hood,HOOD_BOLTS,1.7,3.4,HOOD_TOP_Z)
    hood=holes(hood,[EXHAUST],1.7)
    # Cat 320-style side grilles: four recessed louvres on each engine door.
    for side in [-1,1]:
        for z in [166,174,182,190]:hood=groove_x(hood,-96,-40,side*DECK_HALF_WIDTH,z,z+3.5,1.2)
        for a,b,z0,z1 in [(-100,-99,146,198),(-37,-36,146,198),(-100,-36,146,147),(-100,-36,197,198)]:
            hood=groove_x(hood,a,b,side*DECK_HALF_WIDTH,z0,z1,.6)
    for x in [-19,-13,-7]:hood=hood.cut(box(x,x+2.5,-60,60,HOOD_NOSE_TOP_Z-.8,HOOD_NOSE_TOP_Z+1))
    add('19_engine_hood',hood,note='Hood shell with service opening, side louvres and valve-cover nose; four M3 × 80 countersunk into deck nuts.',orient='flip')

    # Removable top panel, raised 2.4 mm like a real engine hood.
    x0,x1,y0,y1=HATCH['panel']
    hatch=box(x0,x1,y0,y1,HOOD_TOP_Z,HOOD_TOP_Z+WALL).edges('|Z').fillet(4)
    for y in np.arange(-84,-38,6):hatch=hatch.cut(box(-96,-60,y,y+2.6,HOOD_TOP_Z+WALL-.9,HOOD_TOP_Z+WALL+1))
    hatch=holes(hatch,HATCH_SCREWS,1.7);hatch=countersink(hatch,HATCH_SCREWS,1.7,3.4,HOOD_TOP_Z+WALL)
    add('29_hood_hatch',hatch,note='Battery service hatch; four M3 × 12 countersunk into nuts captured in the hood bosses.')

    # Right-front tank housing (hydraulic/fuel tank position on the Cat 320).
    tx0,tx1,ty0,ty1=TANK_HOUSING
    tank=box(tx0,tx1,ty0,ty1,DECK_Z,HOOD_TOP_Z).edges('|Z and >X').fillet(5)
    tank=tank.cut(box(tx0-1,tx1-WALL,ty0+WALL,ty1-WALL,DECK_Z-1,HOOD_TOP_Z-WALL))
    for x,y in TANK_BOLTS:tank=tank.union(cyl(4,DECK_Z,HOOD_TOP_Z-.01,x,y))
    tank=holes(tank,TANK_BOLTS,1.7);tank=countersink(tank,TANK_BOLTS,1.7,3.4,HOOD_TOP_Z)
    for a,b,za,zb in [(tx0+8,tx0+9,142,198),(tx1-10,tx1-9,142,198)]:tank=groove_x(tank,a,b,ty0,za,zb,.6)
    tank=groove_x(tank,tx0+8,tx1-9,ty0,142,143,.6);tank=groove_x(tank,tx0+8,tx1-9,ty0,197,198,.6)
    ring=cyl(6,HOOD_TOP_Z-.6,HOOD_TOP_Z+1,14,-121).cut(cyl(5,HOOD_TOP_Z-1,HOOD_TOP_Z+2,14,-121))
    tank=tank.cut(ring)
    add('30_tank_housing',tank,note='Front-right tank housing; reserved controller bay inside; two M3 × 80 countersunk.',orient='flip')

    # Stepped toolbox in front of the tank housing.
    bx0,bx1,by0,by1=TOOLBOX
    step=box(bx1-14,bx1+1,by0-1,by0+26,TOOLBOX_STEP_Z,TOOLBOX_TOP_Z+1)
    tb=box(bx0,bx1,by0,by1,DECK_Z,TOOLBOX_TOP_Z).edges('|Z and >X').fillet(8).cut(step)
    inner=box(bx0-1,bx1-WALL,by0+WALL,by1-WALL,DECK_Z-1,TOOLBOX_TOP_Z-WALL)
    inner=inner.cut(box(bx1-14-WALL,bx1+1,by0-1,by0+26+WALL,TOOLBOX_STEP_Z-WALL,TOOLBOX_TOP_Z+1))
    tb=tb.cut(inner)
    for x in [60,67,74,81]:tb=tb.cut(box(x,x+1.8,by0+4,by1-4,TOOLBOX_TOP_Z-.8,TOOLBOX_TOP_Z+1))
    for x in [bx1-11,bx1-6]:tb=tb.cut(box(x,x+1.8,by0+4,by0+22,TOOLBOX_STEP_Z-.8,TOOLBOX_STEP_Z+1))
    for x in TOOLBOX_BOLTS:tb=tb.union(cyl(4,DECK_Z,TOOLBOX_TOP_Z-.01,*x))
    tb=holes(tb,TOOLBOX_BOLTS,1.7);tb=countersink(tb,TOOLBOX_BOLTS,1.7,3.4,TOOLBOX_TOP_Z)
    tb=groove_x(tb,bx0+6,bx0+7,by0,141,165,.6);tb=groove_x(tb,bx1-22,bx1-21,by0,141,165,.6)
    tb=groove_x(tb,bx0+6,bx1-21,by0,141,142,.6);tb=groove_x(tb,bx0+6,bx1-21,by0,164,165,.6)
    add('31_toolbox_step',tb,note='Front-right toolbox with access step and tread grooves; two M3 × 45 countersunk.',orient='flip')

    # Exhaust stack: separate upright print, M3 screw from inside the hood top.
    ex,ey=EXHAUST
    stack=cyl(6,HOOD_TOP_Z,HOOD_TOP_Z+2,ex,ey).union(cyl(3.8,HOOD_TOP_Z,HOOD_TOP_Z+18,ex,ey))
    stack=stack.cut(cq.Workplane('XY').box(20,20,10).rotate((0,0,0),(1,0,0),30).translate((ex,ey,HOOD_TOP_Z+22)))
    stack=stack.cut(cyl(2.4,HOOD_TOP_Z+7,HOOD_TOP_Z+30,ex,ey))
    stack=holes(stack,[EXHAUST],1.7,HOOD_TOP_Z-1,HOOD_TOP_Z+7.01)
    stack=nut_pockets(stack,[EXHAUST],M3_NUT[0],HOOD_TOP_Z,2.6)
    add('32_exhaust_stack',stack,BLACK,note='Decorative stack; fit before the hood with an M3 × 8 from inside.')

    # Equipment tray: plate on four legs, printed upside down.
    x0,x1,y0,y1=TRAY
    tray=box(x0,x1,y0,y1,TRAY_TOP_Z-4,TRAY_TOP_Z).edges('|Z').fillet(4)
    for x,y in TRAY_LEGS:tray=tray.union(cyl(4.2,DECK_Z,TRAY_TOP_Z-3.99,x,y))
    tray=holes(tray,TRAY_LEGS,1.7);tray=countersink(tray,TRAY_LEGS,1.7,3.4,TRAY_TOP_Z)
    tray=holes(tray,CRADLE_SCREWS,1.7);tray=nut_pockets(tray,CRADLE_SCREWS,M3_NUT[0],TRAY_TOP_Z-4,2.6)
    for _,(bx0,bx1,by0,by1),_ in BOARDS:tray=holes(tray,[(bx0+4,by0+4),(bx1-4,by1-4)],1.7)
    tray=tray.cut(box(x1-20,x1-8,-6,6,TRAY_TOP_Z-5,TRAY_TOP_Z+1))  # harness slot towards the nose
    add('23_equipment_tray',tray,DARK,note='Fixed tray for the cell cradle, BMS and converters; legs bolt to the deck with four M3 × 45.',orient='flip')

    # Cell cradle: two grooves sized from 18650 datasheet envelopes.
    xc=CRADLE_X;half=CRADLE_INNER_LENGTH/2
    cradle=box(xc-21.5,xc+21.5,-half-3,half+3,TRAY_TOP_Z,GROOVE_Z)
    cradle=cradle.union(box(xc-21.5,xc+21.5,-half-3,-half,TRAY_TOP_Z,GROOVE_Z+GROOVE_R+1))
    cradle=cradle.union(box(xc-21.5,xc+21.5,half,half+3,TRAY_TOP_Z,GROOVE_Z+GROOVE_R+1))
    for x in [xc-GROOVE_PITCH/2,xc+GROOVE_PITCH/2]:cradle=cradle.cut(ycyl(GROOVE_R,-half,half,x,GROOVE_Z))
    cradle=cradle.cut(box(xc-6,xc+6,-half-4,-half+.01,GROOVE_Z-2,GROOVE_Z+GROOVE_R+2))  # pack leads
    # End reliefs: the welded strips bridge the ridge between the two grooves.
    for sign in [-1,1]:
        y0,y1=sorted([sign*(half-4),sign*half]);cradle=cradle.cut(box(xc-14,xc+14,y0,y1,GROOVE_Z-6.5,GROOVE_Z+1))
    for y in [-half-6.5,half+6.5]:cradle=cradle.union(box(xc-7,xc+7,y-3.5,y+3.5,TRAY_TOP_Z,TRAY_TOP_Z+3))
    for x,y in RETAINER_SCREWS:cradle=cradle.union(cyl(4.5,TRAY_TOP_Z,RETAINER_BOTTOM_Z,x,y))
    cradle=holes(cradle,CRADLE_SCREWS+RETAINER_SCREWS,1.7,TRAY_TOP_Z-1,RETAINER_BOTTOM_Z+1)
    for x,y in RETAINER_SCREWS:  # side-entry nut slots open away from the cells
        out=1 if x>xc else -1;a,b=sorted([x-out*3,x+out*10])
        cradle=cradle.cut(box(a,b,y-3,y+3,RETAINER_NUT_Z,RETAINER_NUT_Z+2.6))
    add('33_cell_cradle',cradle,DARK,note='Two Ø19.7 grooves at 19.3 mm pitch, 69 mm between end walls; fits datasheet 18650 cells Ø18.0-18.6 × 64.7-65.3 as a welded 2S1P pack.')

    retainer=box(xc-29.5,xc+29.5,-8,8,RETAINER_BOTTOM_Z,RETAINER_BOTTOM_Z+3).edges('|Z').fillet(3)
    retainer=holes(retainer,RETAINER_SCREWS,1.7,RETAINER_BOTTOM_Z-1,RETAINER_BOTTOM_Z+4)
    add('25_battery_retainer',retainer,DARK,note='Clamp bar over a 3 mm closed-cell foam pad; two M3 × 20 into side-loaded nuts.')

    for n,d in cab_printed().items():p[n]=d
    return p


def cab_printed():
    """R2 cab geometry, placed by cab_place(): moved forward 23 mm, on the left."""
    p={}
    def add(n,s,color=YELLOW,quantity=1,note=''):
        p[n]=dict(shape=cab_place(s).clean(),color=color,kind='printed',quantity=quantity,material='PETG',note=note,orient='upright')
    from shapely.geometry import Polygon
    def xz_prism(points,y0,y1):
        return cq.Workplane('XZ').polyline(points).close().extrude(y1-y0).translate((0,y1,0))
    def drill(s,xy,r,z0=-20,z1=400):
        for x,y in xy:s=s.cut(cyl(r,z0,z1,x,y))
        return s
    mounts=[(-40,-149),(59,-149),(-40,-89),(59,-89)]
    outer=[(-45,182),(75,182),(75,202),(68,293),(58,296),(-37,296),(-45,286)]
    inner=[(-41,186),(71,186),(71,202),(64,293),(58,297),(-33,297),(-41,286)]
    cab=xz_prism(outer,-154,-84).cut(xz_prism(inner,-150,-88))
    window=[(-34,215),(53,215),(51,284),(-30,284)]
    for a,b in [(-155,-149),(-89,-83)]:cab=cab.cut(xz_prism(window,a,b))
    for a,b in [(-46,-39),(57,76)]:cab=cab.cut(box(a,b,-145,-93,220,283))
    for x,y in mounts:cab=cab.union(cyl(3.5,182,296,x,y))
    cab=drill(cab,mounts,1.7)
    cab=drill(cab,[(x,y) for x in [-10,10] for y in [-136,-106]],1.7,181,187)
    cab=drill(cab,[(25,-144),(25,-94)],1.7,181,187)
    add('20_cab_frame',cab,note='120 x 70 x 118 mm cab; Cat 320 drawing proportions, now front-left beside the boom foot.')
    roof=box(-45,75,-154,-84,296,300)
    add('21_cab_roof',drill(roof,mounts,1.7))
    seat=box(-18,18,-140,-98,186,207).union(box(-25,-14,-140,-98,202,246))
    add('27_operator_seat',drill(seat,[(x,y) for x in [-10,10] for y in [-136,-106]],1.7),DARK,note='Scale interior; M3 through bolts into deck nuts.')
    console=box(18,52,-148,-140,186,221).union(cyl(2,221,233,35,-144)).union(cyl(3.5,233,237,35,-144))
    console=drill(console,[(25,-144)],1.7,185,222).cut(cyl(3.1,218,222,25,-144))
    add('28_operator_console',console,DARK,quantity=2,note='Second console sits 50 mm inboard; decorative joystick.')
    return p


def cab_extras():
    """Second console and glazing, already in final coordinates."""
    out={}
    def xz_prism(points,y0,y1):
        return cq.Workplane('XZ').polyline(points).close().extrude(y1-y0).translate((0,y1,0))
    side_glass=[(-35,214),(54,214),(52,285),(-31,285)]
    for i,(a,b) in enumerate([(-150,-149.2),(-88.8,-88)]):out['cab_glazing_side_'+str(i)]=cab_place(xz_prism(side_glass,a,b))
    out['cab_glazing_rear']=cab_place(box(-41,-40.2,-145,-93,219,284))
    front=lambda z:75-(z-202)*7/91
    pane=[(front(219)-4.8,219),(front(219)-4,219),(front(284)-4,284),(front(284)-4.8,284)]
    out['cab_glazing_front']=cab_place(xz_prism(pane,-146,-92))
    return out


# ------------------------------------------------------------- hardware
def upper_hardware():
    """Purchased parts above the deck, final coordinates: name -> (shape, colour, kind)."""
    out={}
    bx0,bx1,by,bt=BALLAST_BOX
    out['steel_ballast']=(box(bx0,bx1,-by,by,DECK_Z,DECK_Z+bt),STEEL,'hardware')
    out['ballast_rubber_pad']=(box(bx0+2,bx1-2,-8,8,DECK_Z+bt,DECK_Z+bt+1),FOAM,'hardware')
    d,length=CELL_NOMINAL;r=d/2;xc=CRADLE_X
    zc=GROOVE_Z-math.sqrt((GROOVE_R-r)**2-((GROOVE_PITCH-(d+CELL_SEPARATOR))/2)**2)+.05
    xs=[xc-(d+CELL_SEPARATOR)/2,xc+(d+CELL_SEPARATOR)/2]
    for i,x in enumerate(xs):
        # Alternate orientation: series pack, positive caps at opposite ends.
        sign=1 if i==0 else -1
        body=ycyl(r,-length/2+(.5 if sign<0 else 0),length/2-(.5 if sign>0 else 0),x,zc)
        cap=ycyl(3.5,sign*(length/2-.5),sign*length/2,x,zc) if sign>0 else ycyl(3.5,-length/2,-length/2+.5,x,zc)
        out['battery_18650_'+str(i)]=(body.union(cap),CELL,'hardware')
    for end in [-1,1]:
        y0,y1=sorted([end*length/2,end*(length/2+NICKEL_STRIP)])
        if end>0:
            out['nickel_strip_series']=(box(xs[0]-4,xs[1]+4,y0,y1,zc-4,zc+4),NICKEL,'hardware')
        else:
            for i,x in enumerate(xs):out['nickel_strip_terminal_'+str(i)]=(box(x-4,x+4,y0,y1,zc-4,zc+4),NICKEL,'hardware')
    half=CRADLE_INNER_LENGTH/2
    end_pad=ycyl(8.5,length/2+NICKEL_STRIP,half,xs[0],zc).union(ycyl(8.5,length/2+NICKEL_STRIP,half,xs[1],zc))
    out['battery_end_pad']=(end_pad,FOAM,'hardware')
    top=zc+r
    out['battery_top_pad']=(box(xs[0]-6,xs[1]+6,-8,8,top,RETAINER_BOTTOM_Z),FOAM,'hardware')
    out['battery_separator']=(box(xc-CELL_SEPARATOR/2+.05,xc+CELL_SEPARATOR/2-.05,-length/2+1,length/2-1,zc-1.2,zc+6),RED,'hardware')
    for name,(x0,x1,y0,y1),h in BOARDS:
        out['electronics_'+name]=(box(x0,x1,y0,y1,TRAY_TOP_Z+3,TRAY_TOP_Z+3+h),BOARD,'hardware')
        for j,(x,y) in enumerate([(x0+4,y0+4),(x1-4,y1-4)]):
            out['electronics_support_'+name+str(j)]=(cyl(2.5,TRAY_TOP_Z,TRAY_TOP_Z+3,x,y).cut(cyl(1.6,TRAY_TOP_Z-1,TRAY_TOP_Z+4,x,y)),DARK,'insulator')
    for n,s in cab_extras().items():out[n]=(s,GLASS,'glazing')
    return out


def bolt_circle(r,n,phase=0):
    return [(r*math.cos(phase+2*math.pi*i/n),r*math.sin(phase+2*math.pi*i/n)) for i in range(n)]

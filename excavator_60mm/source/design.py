"""Tracked arm60 vehicle. CAD dimensions in mm, analysis in SI where labelled.

Original arm60 is imported, never rescaled. Purchased hardware dimensions are
interface requirements, not a claim that every similarly named motor fits.
"""
from pathlib import Path
import sys, math
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(REPO / 'excavator_arm_60mm/source'))
import kinematics as arm
sys.path.insert(0, str(REPO / 'track_wheel/source'))
import tw_design as tw                      # Track wheel R5 constants (no CAD imports)

PITCH = 20.0
TEETH = 12
PITCH_R = PITCH / (2 * math.sin(math.pi / TEETH))
APOTHEM = PITCH_R * math.cos(math.pi / TEETH)
END_WHEEL_RISE = 2.0
AXLE_Z = APOTHEM + 7.0 + END_WHEEL_RISE
CENTRES = 220.0
# Two sloping links per straight run preserve exact pitch with the raised ends.
TRANSITION_DX = math.sqrt(PITCH**2-END_WHEEL_RISE**2)
IDLER_ASSEMBLY_OFFSET = 2*(TRANSITION_DX-PITCH)
GROUND_HALF_LENGTH = CENTRES/2-1.5*PITCH-.6+IDLER_ASSEMBLY_OFFSET/2
TRACK_Y = 170.0
TRACK_SHIFT = TRACK_Y - 150.0
FRAME_SHIFT = 16.0
SHOE_WIDTH = 54.0
PIN_LENGTH = 56.0
PIN_CLIP_Y = 26.5
BUSH_R = 3.0
BUSH_LENGTH = 17.0
GUIDE_CLEARANCE = .6
GUIDE_INNER_Y = 21.0 + GUIDE_CLEARANCE
GUIDE_OUTER_Y = 23.0
GUIDE_HEIGHT = 2.0
SPROCKET_TIP_R = APOTHEM + 3.5
IDLER_GUIDE_R = PITCH_R - BUSH_R - .4
TRACK_LINKS = 34
ROAD_ROLLERS = [-52., 0., 52.]
# Track R5 carriers. The R5 recoil spring holds the top run straight between the
# end chords, so the carriers stand CARRIER_LIFT above that line to keep carrying
# it. Larger rims on the R4 axle height; moved in from x = +-35 to clear the
# road-roller flanges.
RETURN_ROLLERS = [-30., 30.]
RAIL_FACE = 4.0                     # link running faces from the pin line
CARRIER_LIFT = .5
RETURN_Z = 2*APOTHEM-11
RETURN_ROLLER_R = AXLE_Z+APOTHEM+CARRIER_LIFT-RAIL_FACE-RETURN_Z   # 16.5 (R4: 14)
IDLER_RAIL_R = APOTHEM - 4.15
GROUSER_CENTRES = [-6., 0., 6.]
SLEW_DROP = 48.0
DECK_Z = 182.0-SLEW_DROP
ARM_OFFSET = np.array([45.0, 0.0, DECK_Z])
CAB_SIZE = [120.,70.,118.]
SKIRT_MOUNTS = [(130*math.cos(a),130*math.sin(a)) for a in np.radians([30,90,150,210,270,330])]
SLEW_LIMIT = 150.0
PETG_KG_MM3 = 1.27e-6
STEEL_KG_MM3 = 7.85e-6

# R3 upper body, final coordinates. Cat 320 layout: cab front-left, tank
# housing and toolbox front-right, engine hood behind, curved counterweight.
DECK_HALF_WIDTH = 154.0
TAIL_RADIUS = 189.0            # Cat 320 tail swing radius 2,830 mm at 1:15
DECK_FRONT_X = 104.0
DECK_NOSE_X = 138.0            # boom-foot nose under the arm60 base (X1-133)
DECK_NOSE_HALF_WIDTH = 86.0
DECK_RIM_Z = 112.0
COUNTERWEIGHT_FRONT_X = -math.sqrt(TAIL_RADIUS**2-DECK_HALF_WIDTH**2)
CAB_SHIFT_X = 23.0             # R2 cab moved forward: windscreen at X98
CAB_SIDE = 1                   # +1 = machine left as on the Cat 320. The tank housing,
                               # toolbox and exhaust are fixed on the right: -1 is not a supported layout.
HOOD_FRONT_X = -45.0+CAB_SHIFT_X
HOOD_TOP_Z = 206.0
HOOD_NOSE_X = -2.0
HOOD_NOSE_HALF_WIDTH = 80.0
HOOD_NOSE_TOP_Z = 182.0
TANK_HOUSING = (HOOD_FRONT_X+.3, 50.0, -DECK_HALF_WIDTH, -88.0)
TOOLBOX = (50.3, DECK_FRONT_X, -DECK_HALF_WIDTH, -88.0)
TOOLBOX_TOP_Z = 171.0
TOOLBOX_STEP_Z = 152.0
CABLE_PASS = (-10.0, 25.0)
CAB_ROOF_Z = 300.0-SLEW_DROP
SEAT_BASE_TOP_Z = 207.0-SLEW_DROP
CONSOLE_TOP_Z = 218.0-SLEW_DROP  # 3 mm counterbore in the console top

# Two 18650 cells as a welded 2S1P side-by-side pack. Datasheet envelopes:
CELL_DATASHEETS = [
    dict(model='Samsung INR18650-25R', source='Samsung SDI specification, Mar. 2013',
         diameter_mm=[18.26,18.40], length_mm=[64.70,65.00], max_mass_g=45.0),
    dict(model='LG INR18650HG2', source='LG Chem product specification BCY-PS-HG2-Rev0, 2014-10-13',
         diameter_mm=[18.0,18.5], length_mm=[64.8,65.2], max_mass_g=47.0),
    dict(model='Panasonic NCR18650B', source='Panasonic NCR18650B data sheet, 2012 (maxima only)',
         diameter_mm=[None,18.5], length_mm=[None,65.3], max_mass_g=48.5)]
CELL_DIAMETER_RANGE = (18.0, 18.6)   # 0.1 mm above the largest datasheet maximum
CELL_LENGTH_RANGE = (64.7, 65.3)     # flat-top, unprotected cells
CELL_NOMINAL = (18.3, 65.0)          # modelled cell
CELL_SEPARATOR = 0.5                 # insulating sheet between the two cans
NICKEL_STRIP = 0.15                  # pure nickel, one layer at each end
PACK_WRAP_RANGE = (0.12, 0.25)       # PVC heat-shrink wall
END_INSULATION_RANGE = (0.3, 1.0)    # fish-paper ring / end board per end
GROOVE_R = 9.85
GROOVE_PITCH = 19.3
CRADLE_X = -68.0
CRADLE_INNER_LENGTH = 69.0
END_PAD = dict(free_mm=4.0, minimum_compressed_mm=1.2)
TOP_PAD = dict(free_mm=3.0, minimum_compressed_mm=1.0)
TRAY = (-105.0, -26.0, -100.0, 100.0)
TRAY_TOP_Z = 170.0
GROOVE_Z = TRAY_TOP_Z+1.5+GROOVE_R
RETAINER_BOTTOM_Z = GROOVE_Z+10.6
RETAINER_NUT_Z = GROOVE_Z-4.0
RETAINER_SCREWS = [(CRADLE_X-25.5,0.0),(CRADLE_X+25.5,0.0)]
CRADLE_SCREWS = [(CRADLE_X,-(CRADLE_INNER_LENGTH/2+6.5)),(CRADLE_X,CRADLE_INNER_LENGTH/2+6.5)]
BOARDS = [('BMS',(-60.,-31.,-78.,-48.),6),('6V_buckboost',(-100.,-63.,-78.,-46.),16),('12V_boost',(-100.,-40.,46.,78.),21)]
# Steel ballast plate inside the counterweight: rear X, front X, half width, thickness.
BALLAST_BOX = (-167.1, COUNTERWEIGHT_FRONT_X-3.5, 75.0, 24.0)
BALLAST_KG = (BALLAST_BOX[1]-BALLAST_BOX[0])*2*BALLAST_BOX[2]*BALLAST_BOX[3]*STEEL_KG_MM3

def sprocket_outline(outer_segments=48,pin_segments=12):
    """Bushing sprocket including the entry/exit sweep of a rigid 20 mm link.

    At the top horizontal chord the preceding pin is (-p/2, apothem).
    A departing pin follows c + Rot(t)*(p,0) in the sprocket frame, 0..30°.
    This is a curved flank relief; a narrow radial slot alone still binds.
    Mirror the sweep for reverse drive. Buffer adds the 3 mm steel sleeve
    radius plus 0.3 mm running clearance. Tooth tips clear the shoe web.
    """
    from shapely.geometry import Point,LineString
    from shapely.affinity import rotate,scale
    profile=Point(0,0).buffer(SPROCKET_TIP_R,quad_segs=outer_segments)
    points=[(-PITCH/2+PITCH*math.cos(t),APOTHEM+PITCH*math.sin(t)) for t in np.linspace(0,math.pi/6,7)]
    sweep=rotate(LineString(points).buffer(BUSH_R+.3,quad_segs=pin_segments),-75,origin=(0,0))
    relief=sweep.union(scale(sweep,xfact=1,yfact=-1,origin=(0,0)))
    for a in range(15,360,30):profile=profile.difference(rotate(relief,a,origin=(0,0)))
    return profile


def top_run_pins(x0,x1):
    """Pins of the top run strictly between the end-chord pins at x0 and x1.

    The run lies on the carriers, CARRIER_LIFT above the end chords. The slack
    needed to close 34 exact pitches is a dip at mid-span, between the carriers;
    the R5 spring pulls it out in service.
    """
    a,lift=APOTHEM,CARRIER_LIFT;n=round((x1-x0)/PITCH)
    end=math.sqrt(PITCH**2-lift**2)
    dip_dx=(x1-x0-2*end-(n-4)*PITCH)/2;dip=math.sqrt(PITCH**2-dip_dx**2)
    z=[a+lift]*(n-1);z[n//2-1]=a+lift-dip
    x=[x0]
    for k in range(n-1):x.append(x[-1]+math.sqrt(PITCH**2-((z[k]-(a if k==0 else z[k-1]))**2)))
    assert abs(x[-1]+end-x1)<1e-9
    pins=list(zip(x[1:],z))
    for xc in RETURN_ROLLERS:   # each carrier sits under a level link
        k=max(i for i,(px,_) in enumerate(pins) if px<=xc)
        assert z[k]==z[k+1]==a+lift,xc
    return pins


def track_pins():
    """Exact closed pin polygon with end shoes raised above the ground run.

    Keep a full horizontal chord over each end wheel. On the ground run the next
    link slopes down to the central run; the idler retracts slightly to close
    all 34 pitches. The top run rests on the carriers (top_run_pins). Road
    running levels stay fixed. This is only the assembly pose.
    """
    a, c = APOTHEM, CENTRES / 2
    right=c+IDLER_ASSEMBLY_OFFSET
    inner=np.arange(-c+PITCH/2+TRANSITION_DX,right-PITCH/2-TRANSITION_DX+.01,PITCH)
    p=[(-c-PITCH/2,a),(-c+PITCH/2,a)]
    p += top_run_pins(-c+PITCH/2,right-PITCH/2)
    p += [(right-PITCH/2,a),(right+PITCH/2,a)]
    p += [(right+PITCH_R*math.cos(math.radians(t)),
           PITCH_R*math.sin(math.radians(t))) for t in [45,15,-15,-45,-75]]
    p += [(right-PITCH/2,-a)]
    p += [(x,-a-END_WHEEL_RISE) for x in inner[::-1]]
    p += [(-c+PITCH/2,-a),(-c-PITCH/2,-a)]
    p += [(-c+PITCH_R*math.cos(math.radians(t)),
           PITCH_R*math.sin(math.radians(t))) for t in [225,195,165,135]]
    return np.array(p) + [0, AXLE_Z]


def track_poses():
    p = track_pins()
    for i, a in enumerate(p):
        b = p[(i+1) % len(p)]
        # Local shoe underside (-Z) must point away from the loop.
        yield i, (a+b)/2, math.atan2(a[1]-b[1], a[0]-b[0])


def config():
    return dict(revision=3, units='mm', track_pitch=PITCH, sprocket_teeth=TEETH,
                pitch_radius=PITCH_R, wheel_centres=CENTRES, axle_z=AXLE_Z,
                end_wheel_rise_mm=END_WHEEL_RISE,idler_assembly_offset_mm=IDLER_ASSEMBLY_OFFSET,
                return_roller_z_mm=RETURN_Z,return_roller_r_mm=RETURN_ROLLER_R,carrier_lift_mm=CARRIER_LIFT,ground_support_half_length_mm=GROUND_HALF_LENGTH,
                track_centres=2*TRACK_Y, track_links_per_side=TRACK_LINKS,
                track_pin_diameter=3, track_pin_length=PIN_LENGTH,track_pin_clip_y_mm=PIN_CLIP_Y,
                shoe_width=SHOE_WIDTH, idler_travel_mm=[-tw.recoil_travel(),tw.forward_travel()],
                idler_tension_adjustment_mm=list(tw.ADJUST_RANGE), track_revision=5, grouser_centres_mm=GROUSER_CENTRES,
                track_bushing_od_mm=2*BUSH_R,track_bushing_id_mm=3.1,track_bushing_length_mm=BUSH_LENGTH,
                track_outer_width_mm=2*TRACK_Y+SHOE_WIDTH,frame_lateral_shift_mm=FRAME_SHIFT,
                guide_clearance_per_side_mm=GUIDE_CLEARANCE,guide_flange_height_mm=GUIDE_HEIGHT,
                guide_inner_y_mm=GUIDE_INNER_Y,guide_outer_y_mm=GUIDE_OUTER_Y,
                sprocket_tip_radius_mm=SPROCKET_TIP_R,idler_guide_radius_mm=IDLER_GUIDE_R,
                grouser_height_mm=1, grouser_width_mm=2,
                idler_rail_radius_mm=IDLER_RAIL_R,
                road_roller_x_mm=ROAD_ROLLERS, return_roller_x_mm=RETURN_ROLLERS,
                track_reference='Berco sprockets, rollers, track chains and idlers; Cat 320 technical specifications pages 2, 3, 4 and 20; references/TRACK_SYSTEM.md',
                arm_offset=ARM_OFFSET.tolist(), arm=arm.config(),
                cab_size_mm=CAB_SIZE, cab_reference='Cat 320 specifications page 4, drawing estimate at 1:15',
                deck_top_mm=DECK_Z, skirt_bottom_mm=92, slew_lowered_mm=SLEW_DROP,
                upper_body=dict(revision=3,layout='Cat 320: cab front-left, tank housing and stepped toolbox front-right, engine hood, curved counterweight',
                    cab_side='left' if CAB_SIDE>0 else 'right',cab_x_mm=[HOOD_FRONT_X,HOOD_FRONT_X+CAB_SIZE[0]],
                    tail_swing_radius_mm=TAIL_RADIUS,deck_half_width_mm=DECK_HALF_WIDTH,deck_front_x_mm=DECK_FRONT_X,
                    deck_nose_mm=[DECK_NOSE_X,DECK_NOSE_HALF_WIDTH],deck_rim_bottom_z_mm=DECK_RIM_Z,
                    counterweight_front_x_mm=COUNTERWEIGHT_FRONT_X,hood_top_z_mm=HOOD_TOP_Z,
                    hood_nose_top_z_mm=HOOD_NOSE_TOP_Z,toolbox_top_z_mm=TOOLBOX_TOP_Z,
                    reference='Cat 320 technical specifications page 4: 2,830 mm tail swing radius; product images for component layout'),
                battery=dict(cells=2,type='18650',arrangement='2S1P welded side-by-side pack',nominal_voltage=7.2,full_voltage=8.4,
                    operational_voltage_range=[6.2,8.4],cell_diameter_range_mm=list(CELL_DIAMETER_RANGE),
                    cell_length_range_mm=list(CELL_LENGTH_RANGE),cell_datasheets=CELL_DATASHEETS,
                    cradle_groove_diameter_mm=2*GROOVE_R,cradle_groove_pitch_mm=GROOVE_PITCH,
                    cradle_inner_length_mm=CRADLE_INNER_LENGTH,
                    mounting='Fitted cradle on the equipment tray inside the engine hood, under the removable hatch',
                    regulated_rails_V=[12,6],combined_output_budget_W=36,
                    minimum_cell_continuous_A=15,minimum_BMS_continuous_A=10),
                ballast_plate_mm=[BALLAST_BOX[1]-BALLAST_BOX[0],2*BALLAST_BOX[2],BALLAST_BOX[3]],
                slew_soft_limit_deg=SLEW_LIMIT, slew_gear_teeth=[96,20],
                slew_module=1.5, slew_pressure_angle_deg=20,
                slew_centre_distance=87.2, slew_bearing='2 x 6004, 20 x 42 x 12',
                slew_bearing_separation=40, drive_bearing='Per side: 61808-2RS1 (40 x 52 x 7, fixed) + 6809-2RS (45 x 58 x 7, floating) in the sprocket hub',
                ballast_kg=BALLAST_KG, drive_motor=dict(voltage=12,rpm=round(tw.drive_rating()['sprocket_no_load_rpm'],1),
                required_continuous_torque_Nm=1.2,model=tw.GEARMOTOR['model']+' inside the sprocket hub, 1.75:1 internal ring stage',
                current_limit_A=tw.DRIVE_CURRENT_LIMIT_A,sprocket_torque_at_limit_Nm=round(tw.drive_force_limit()['torque_Nm'],3),
                body_diameter=tw.GEARMOTOR['gearbox_diameter']),
                track_wheel=dict(revision='R5',folder='track_wheel/',spring=tw.SPRING['model'],spring_rate_N_mm=tw.SPRING['rate_N_mm'],
                    assembled_spring_length_mm=tw.spring_state()['length'],preload_N=tw.spring_state()['force'],
                    spring_seat_x_mm=tw.REAR_WALL_X[1]+tw.ADJUST_NOMINAL+tw.SEAT_BLOCK,recoil_travel_mm=tw.recoil_travel(),
                    forward_travel_mm=tw.forward_travel(),hub_ratio=tw.HUB_RATIO,
                    pinion_x_mm=tw.DRIVE_X+tw.CENTRE_DISTANCE*math.cos(math.radians(tw.PINION_ANGLE)),
                    pinion_z_mm=AXLE_Z+tw.CENTRE_DISTANCE*math.sin(math.radians(tw.PINION_ANGLE)),
                    spring_length_nominal_mm=tw.spring_state(tw.ADJUST_NOMINAL,0.0)['length'],yoke_rear_x_mm=tw.YOKE_X[0],
                    hub_cap_face_y_mm=tw.CAP_Y[1]),
                slew_motor=dict(voltage=12,rpm=10,required_continuous_torque_Nm=.35,
                shaft='4 mm D',body_diameter=25),
                normal_drive_speed_limit_m_s=.10, nominal_floor_slope_deg=0)

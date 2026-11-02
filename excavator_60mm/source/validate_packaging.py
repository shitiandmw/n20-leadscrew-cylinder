"""R3 cab placement, 18650 cradle fit, fastener stacks, battery service and 2S power budget.

The cell fit uses manufacturer datasheet envelopes plus stated pack build-up
assumptions. CAD checks are sampled; electrical results are a power budget,
not a switching-converter, cell thermal, charger or hardware validation.
"""
import itertools,json,math
import numpy as np
from build_vehicle import *
from upper_body import cell_fit,fastener_table,M3_NUT,M4_NUT,DECK_POCKET,HATCH,HATCH_SCREWS

PACK=['battery_18650_0','battery_18650_1','nickel_strip_series','nickel_strip_terminal_0','nickel_strip_terminal_1','battery_end_pad','battery_separator']


def cell_fit_report(cradle):
    """Analytic fit over the datasheet range, then exact CAD at the extremes."""
    cases=[];fail=[]
    for d,length,wrap,ends in itertools.product(CELL_DIAMETER_RANGE,CELL_LENGTH_RANGE,PACK_WRAP_RANGE,END_INSULATION_RANGE):
        f=cell_fit(d,length,wrap,ends);f.update(cell_diameter_mm=d,cell_length_mm=length,wrap_mm=wrap,end_insulation_mm=ends)
        cases.append(f)
    radial=min(c['radial_clearance_mm'] for c in cases)
    end=[c['end_pad_compressed_mm'] for c in cases];top=[c['top_pad_compressed_mm'] for c in cases]
    if radial<.1:fail.append('cell groove clearance below 0.1 mm')
    if min(end)<END_PAD['minimum_compressed_mm'] or max(end)>END_PAD['free_mm']:fail.append('end pad cannot hold every datasheet pack length')
    if min(top)<TOP_PAD['minimum_compressed_mm'] or max(top)>TOP_PAD['free_mm']:fail.append('top pad cannot hold every datasheet pack height')
    # Exact CAD: largest and smallest wrapped cells at their analytic rest position.
    cad=[]
    for d,wrap in [(CELL_DIAMETER_RANGE[1],PACK_WRAP_RANGE[1]),(CELL_DIAMETER_RANGE[0],PACK_WRAP_RANGE[0])]:
        f=cell_fit(d,CELL_LENGTH_RANGE[1],wrap,END_INSULATION_RANGE[1]);rw=d/2+wrap
        z=GROOVE_Z-f['centre_drop_mm'];length=f['pack_length_mm']
        volume=0
        for sign in [-1,1]:
            x=CRADLE_X+sign*(d+CELL_SEPARATOR)/2
            test=ycyl(rw-.002,-length/2,length/2,x,z)
            volume+=sum(s.Volume() for s in cradle.intersect(test).solids().vals())
        cad.append(dict(cell_diameter_mm=d,wrap_mm=wrap,pack_length_mm=length,cradle_intersection_mm3=volume))
        if volume>.01:fail.append(f'CAD pack Ø{d} intersects the cradle')
    nominal=dict(diameter_mm=CELL_NOMINAL[0],length_mm=CELL_NOMINAL[1])
    for sheet in CELL_DATASHEETS:
        lo,hi=sheet['diameter_mm'];a,b=sheet['length_mm']
        if (lo is not None and lo<CELL_DIAMETER_RANGE[0]) or hi>CELL_DIAMETER_RANGE[1] or (a is not None and a<CELL_LENGTH_RANGE[0]) or b>CELL_LENGTH_RANGE[1]:
            fail.append('design range does not cover '+sheet['model'])
    return dict(datasheets=CELL_DATASHEETS,design_range=dict(diameter_mm=list(CELL_DIAMETER_RANGE),length_mm=list(CELL_LENGTH_RANGE)),
        pack_build_up=dict(arrangement='two cells side by side, opposite polarity, welded series strip',
            separator_mm=CELL_SEPARATOR,nickel_strip_mm=NICKEL_STRIP,wrap_wall_mm=list(PACK_WRAP_RANGE),end_insulation_per_end_mm=list(END_INSULATION_RANGE)),
        cradle=dict(groove_diameter_mm=2*GROOVE_R,groove_pitch_mm=GROOVE_PITCH,inner_length_mm=CRADLE_INNER_LENGTH,
            groove_centre_z_mm=GROOVE_Z,retainer_underside_z_mm=RETAINER_BOTTOM_Z,end_pad=END_PAD,top_pad=TOP_PAD),
        cases=len(cases),minimum_radial_clearance_mm=radial,
        pack_width_range_mm=[min(c['pack_width_mm'] for c in cases),max(c['pack_width_mm'] for c in cases)],
        pack_length_range_mm=[min(c['pack_length_mm'] for c in cases),max(c['pack_length_mm'] for c in cases)],
        pack_height_range_mm=[min(c['pack_height_mm'] for c in cases),max(c['pack_height_mm'] for c in cases)],
        end_pad_compressed_range_mm=[min(end),max(end)],top_pad_compressed_range_mm=[min(top),max(top)],
        cad_extremes=cad,modelled_cell=nominal,failures=fail,
        scope='Flat-top unprotected 18650 cells only. Button-top or protected cells (about 67-70 mm) do not fit this cradle.')


def fastener_report():
    """Each screw must engage its whole nut and stay above the deck underside."""
    rows=[];fail=[]
    underside=DECK_Z-10
    for f in fastener_table():
        thickness=(M4_NUT if f['size']=='M4' else M3_NUT)[1];top=underside+DECK_POCKET[f['size']]
        tip=f['head_seat_z']-f['length'];engaged=top-max(tip,top-thickness)
        ok=tip>=underside-1e-6 and engaged>=thickness-1e-6
        rows.append(dict(f,tip_z_mm=tip,nut_z_mm=[top-thickness,top],engaged_mm=engaged,ok=ok))
        if not ok:fail.append(f"{f['name']} at {f['xy']}")
    # Short screws into nuts captured in printed bosses.
    extra=[('Hood hatch screw','M3',12,HOOD_TOP_Z+2.4,HOOD_TOP_Z-2.4-7.6,3.0,len(HATCH_SCREWS)),
           ('Battery retainer screw','M3',20,RETAINER_BOTTOM_Z+3,RETAINER_NUT_Z,2.6,2),
           ('Cell cradle screw','M3',8,TRAY_TOP_Z+3,TRAY_TOP_Z-4,2.6,2)]
    for name,size,length,head,pocket_bottom,pocket,count in extra:
        top=pocket_bottom+pocket;tip=head-length;engaged=top-max(tip,top-M3_NUT[1])
        ok=engaged>=M3_NUT[1]-1e-6
        rows.append(dict(name=name,size=size,length=length,head_seat_z=head,count=count,tip_z_mm=tip,nut_z_mm=[top-M3_NUT[1],top],engaged_mm=engaged,ok=ok))
        if not ok:fail.append(name)
    return rows,fail


def run():
    parts=printable_parts();vehicle=vehicle_instances(parts);fail=[]
    cab=cq.Compound.makeCompound([one(parts[n]['shape']) for n in ['20_cab_frame','21_cab_roof']]).BoundingBox()
    dimensions=[cab.xlen,cab.ylen,cab.zlen]
    if not np.allclose(dimensions,CAB_SIZE,atol=1e-5):fail.append('cab envelope')
    if (cab.ymin>0)!=(CAB_SIDE>0):fail.append('cab is not on the configured side')
    cells={n:d for n,d in vehicle.items() if n.startswith('battery_18650_')}
    if len(cells)!=2:fail.append('cell count')
    fit=cell_fit_report(parts['33_cell_cradle']['shape']);fail+=fit['failures']
    fasteners,fastener_fail=fastener_report();fail+=fastener_fail
    # Service: hatch, retainer and top pad off; lift the welded pack straight out.
    removed=PACK+['29_hood_hatch','25_battery_retainer','battery_top_pad']
    fixed={n:d for n,d in vehicle.items() if d['group']=='upper' and n not in removed}
    fixed.update({'arm_'+n:d for n,d in full_arm().items()})
    bounds={n:one(d['shape']).BoundingBox() for n,d in fixed.items()}
    collisions=[];checks=0;lifts=[0,1,5,10,20,40,80]
    for lift in lifts:
        for n in PACK:
            shape=vehicle[n]['shape'].translate((0,0,lift));a=one(shape).BoundingBox()
            for other,d in fixed.items():
                b=bounds[other]
                if any(getattr(a,k+'max')<=getattr(b,k+'min')+1e-5 or getattr(b,k+'max')<=getattr(a,k+'min')+1e-5 for k in 'xyz'):continue
                vol=sum(s.Volume() for s in shape.intersect(d['shape']).solids().vals());checks+=1
                if vol>.05:collisions.append(dict(part=n,obstacle=other,lift_mm=lift,volume_mm3=vol))
    if collisions:fail.append('battery pack removal interference')
    pack=cq.Compound.makeCompound([one(vehicle[n]['shape']) for n in PACK]).BoundingBox()
    x0,x1,y0,y1=HATCH['opening']
    hatch_margin=min(pack.xmin-x0,x1-pack.xmax,pack.ymin-y0,y1-pack.ymax)
    if hatch_margin<2:fail.append('hatch opening too small for the pack')
    # Voltage sag is bounded by a controller cutoff; BMS undervoltage is the backup.
    voltage=np.linspace(6.2,8.4,23);efficiency=.85;budget=36.
    current=budget/efficiency/voltage
    if max(current)>8 or max(current)>10 or max(current)>15:fail.append('2S current budget')
    power=dict(arrangement='2S1P',cells=2,nominal_V=7.2,full_V=8.4,controller_cutoff_V=6.2,
        rails_V=[12,6],combined_output_budget_W=budget,assumed_min_converter_efficiency=efficiency,
        maximum_calculated_pack_current_A=float(max(current)),pack_controller_limit_A=8,
        minimum_BMS_continuous_A=10,minimum_cell_continuous_A=15,main_fuse_A=10,
        boost_12V_max_output_W=30,buckboost_6V_max_output_W=18,
        voltage_samples=23,simultaneous_rail_limits_require_combined_budget=True,
        nominal_capacity_assumption_Ah=3,estimated_minutes_at_36W=7.2*3*.8*efficiency/budget*60,
        charging='Lift the pack out; use a matching 8.4 V CC/CV 2S balance/protection-compatible charger.',
        scope='Analytic budget with assumed 85% efficiency and 80% usable nominal energy. Actual cell sag, converter cooling, motor current and runtime need measurement. Motor torque assumptions only hold while regulated rails and measured current limits support them.')
    # Tail swing from tessellated surfaces of every rotating upper-body part.
    tail=max(math.hypot(v.x,v.y) for d in vehicle.values() if d['group']=='upper' for v in one(d['shape']).tessellate(.05,.1)[0])
    if tail>TAIL_RADIUS+.05:fail.append('upper body exceeds the tail swing radius')
    result=dict(status='PASS' if not fail else 'FAIL',failures=fail,
        layout=dict(cab_side='left' if CAB_SIDE>0 else 'right',cab_box_mm=[[cab.xmin,cab.xmax],[cab.ymin,cab.ymax],[cab.zmin,cab.zmax]],
            tail_swing_radius_mm=TAIL_RADIUS,measured_max_radius_mm=tail,hood_top_z_mm=HOOD_TOP_Z,
            reference='Cat 320 technical specifications page 4: 2,830 mm tail swing radius = 188.7 mm at 1:15'),
        cab_envelope_mm=dimensions,
        cab_drawing_estimate_mm=[118*3650/239/15,66*2780/181/15,115*3650/239/15],
        cab_roof_z_mm=cab.zmax,deck_top_z_mm=DECK_Z,lowered_deck_mm=SLEW_DROP,
        visible_bridge_to_skirt_gap_mm=round(min(v.Z for v in one(parts['26_slew_skirt']['shape']).Vertices())-80,3),
        cell_fit=fit,fasteners=fasteners,
        battery_service=dict(lifts_mm=lifts,exact_intersections=checks,collisions=collisions,
            hatch_opening_mm=list(HATCH['opening']),pack_to_opening_margin_mm=hatch_margin,
            procedure='Switch off and unplug the pack; remove the four hatch screws and the two retainer screws, then lift the welded pack straight out of the cradle. The tray, BMS and converters stay in place.'),
        power=power,scope='CAD envelope, fit and removal checks plus an analytic battery power budget; no physical fit or electrical commissioning claimed.')
    (ROOT/'simulation/packaging.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in ['fasteners','cell_fit']},indent=2))
    print('cell fit',json.dumps({k:v for k,v in fit.items() if k not in ['datasheets','cases']},indent=1))
    print('fasteners failing',fastener_fail)
    return not fail

if __name__=='__main__':raise SystemExit(0 if run() else 1)

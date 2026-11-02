"""Export J8 and check the two-sided roller bracket and retained interfaces."""
import json,gzip,time,shutil,importlib.util
import j8_parts as s
import build_j2 as prior
import build_track_wheel as export
import tw_checks as checks
from build_structure import distance
ROOT=s.ROOT

def against(fixed,moving):
    return checks.interference({**fixed,**moving},skip=lambda a,b:(a in moving)==(b in moving))

def main():
    start=time.time();new=s.parts();inst=s.unit(new);rows=[]
    for n,d in new.items():
        print('Export',n,flush=True)
        assert s.p.one(d['shape']).isValid(),n
        export.export_step(d['shape'],ROOT/'step'/f'{n}.step')
        row={k:v for k,v in d.items() if k not in ['shape','color']};row.update(name=n,step_roundtrip=True,valid=True)
        row['solid_count']=len(d['shape'].solids().vals());assert row['solid_count']==1
        if d['kind']=='printed':
            angle=90 if n in ['J711_one_piece_track_housing','J624_compact_return_roller'] else -90
            mesh=export.export_stl(export.to_bed(d['shape'],(1,0,0),angle),ROOT/'stl'/f'{n}.stl')
            row.update(stl_watertight=True,connected_components=len(mesh.split()),print_bounds_mm=mesh.extents.tolist())
        rows.append(row)
    for name in ['TW02_sprocket_hub','TW07_idler_yoke','TW08_spring_seat','TW09_channel_nose','05_track_shoe','07_idler_wheel','08_road_roller']:
        for fmt in ['step','stl']:shutil.copy2(s.REPO/'track_wheel'/fmt/f'{name}.{fmt}',ROOT/fmt/f'{name}.{fmt}')
    solids=prior.save_assembly(inst,ROOT/'step/JGY370_track_J8.step','JGY370_track_J8')
    bracket=s.bracket_items(inst)
    bracket_solids=prior.save_assembly(bracket,ROOT/'step/J8_continuous_side_frame_assembly.step','J8_continuous_side_frame_assembly')
    bridge=s.j3.xbridge();export.export_step(bridge,ROOT/'step/J314_X_bridge_PROPOSAL.step')
    pair={}
    for n,d in inst.items():
        pair['right_'+n]={**d,'shape':d['shape'].translate((0,170,0))}
        pair['left_REFERENCE_'+n]={**d,'shape':d['shape'].mirror('XZ').translate((0,-170,0))}
    pair['J314_X_bridge_PROPOSAL']=dict(shape=bridge,color=(.28,.48,.51),group='bridge',kind='machined',source=None)
    pair.update(s.j3.bridge_hardware())
    prior.save_assembly(pair,ROOT/'step/J8_docked_chassis_PROPOSAL.step','J8_chassis_PROPOSAL')
    print('Geometry and service checks',flush=True)
    aliases={'J806_continuous_support_frame':'J206_integrated_track_frame','J711_one_piece_track_housing':'J211_contoured_motor_lid','J402_motor_mount_plate':'J202_motor_mount_plate'}
    legacy={aliases.get(n,n.replace('J7_cover_M3x10','J2_lid_M3x8').replace('J7_cover_insert','J2_lid_insert')):d for n,d in inst.items() if n!='J313_chassis_docking_beam' and not n.startswith('J3_beam_')}
    rep=prior.check(legacy);rep['legacy_alias_note']='Interface regression uses J2 keys with actual J8 shapes.'
    rep['static_current_parts']=checks.interference(inst,skip=lambda a,b:not(a.startswith('J8') or b.startswith('J8')))
    fixed={n:d for n,d in inst.items() if n!='J711_one_piece_track_housing' and not n.startswith('J7_cover_M3x10')}
    fixed['wire_reserve']=dict(shape=s.j2.j1.motor_shapes()['reserved_terminal_and_wire_space'],group='wire')
    removal=[]
    for shift in [0,.1,.25,.5,1,2,3,4,5,7.5,10,12.5,15,20,25,30,35,40,45]:
        removal.append(dict(shift_mm=shift,**against(fixed,{'cover':{**inst['J711_one_piece_track_housing'],'shape':new['J711_one_piece_track_housing']['shape'].translate((0,-shift,0))}})))
    rep['cover_removal_samples']=removal
    tools=[]
    for x,z in s.COVER_HOLES:
        tools.append(dict(x=x,z=z,**against(inst,{'tool':dict(shape=s.p.ycyl(2,-115,-73,x,z),group='tool')})))
    rep['cover_screw_tool_access']=tools
    service={n:d for n,d in fixed.items() if n!='wire_reserve'}
    axle_access=[]
    for x,z,g in s.AXES:
        for side,lo,hi,r in [('rear_hex',-95,-30.5,2.4),('front_M5',28,75,1.8)]:
            axle_access.append(dict(wheel=g,side=side,**against(service,{'tool':dict(shape=s.p.ycyl(r,lo,hi,x,z),group='tool')})))
    rep['roller_retention_tool_approach']=axle_access
    tie_access=[]
    for x,z in s.TIES:
        for side,lo,hi in [('rear',-95,-45.5),('front',28,75)]:
            tie_access.append(dict(x=x,side=side,**against(service,{'tool':dict(shape=s.p.ycyl(1.5,lo,hi,x,z),group='tool')})))
    rep['cross_tie_tool_approach']=tie_access
    # All five axle screws and three tie screws are removed first.
    plate_fixed={n:d for n,d in inst.items() if d['group'] not in ['outer_plate','outer_fasteners']}
    plate_removal=[]
    for shift in [0,.1,.5,1,2,3,4,6,10,20,40,65]:
        plate_removal.append(dict(shift_mm=shift,**against(plate_fixed,{'plate':{**new['J816_outer_continuous_side_plate'],'group':'service','shape':new['J816_outer_continuous_side_plate']['shape'].translate((0,shift,0))}})))
    rep['outer_plate_removal']=plate_removal
    # Remove chain, outer plate, both end spacers and the selected wheel first.
    axle_removal=[]
    for x,z,g in s.AXES:
        axle_name=f'J7_through_axle_{g}'
        retained={n:d for n,d in service.items() if d['group'] not in ['track','outer_plate','outer_fasteners',g] and n!=axle_name and not n.startswith((f'spacer_{g}_',f'J7_end_spacer_{g}_'))}
        samples=[]
        for shift in [0,1,5,12,20,30,45,60,85]:
            samples.append(dict(shift_mm=shift,**against(retained,{axle_name:{**inst[axle_name],'shape':inst[axle_name]['shape'].translate((0,-shift,0))}})))
        axle_removal.append(dict(wheel=g,samples=samples))
    rep['inboard_axle_removal']=axle_removal
    changed=lambda n:any(t in n for t in ['J8','J313','J3_beam','J314','J3_bridge'])
    rep['docked_chassis_static']=checks.interference(pair,skip=lambda a,b:not(changed(a) or changed(b)))
    fixed_pair={n:d for n,d in pair.items() if not n.startswith(('J314','J3_bridge_'))}
    rep['chassis_insertion']=against(fixed_pair,{'bridge_sweep':dict(shape=s.j3.xbridge(lift_sweep=40),group='tool')})
    moving_drive={n:d for n,d in inst.items() if d['group']=='drive'}
    changed_fixed={n:d for n,d in inst.items() if n.startswith('J8')}
    rotations=[]
    for angle in range(0,360,15):
        posed={n:{**d,'shape':d['shape'].rotate((s.DX,0,s.DZ),(s.DX,1,s.DZ),angle)} for n,d in moving_drive.items()}
        rotations.append(dict(angle_deg=angle,**against(changed_fixed,posed)))
    rep['drive_against_continuous_plates']=rotations
    travel=[]
    for cx in [s.IDLER_LIMITS[0],s.p.IDLER_X+s.p.ex.IDLER_ASSEMBLY_OFFSET,s.IDLER_LIMITS[1]]:
        shift=cx-(s.p.IDLER_X+s.p.ex.IDLER_ASSEMBLY_OFFSET)
        moving={n:{**d,'shape':d['shape'].translate((shift,0,0))} for n,d in inst.items() if d['group'] in ['idler','idler_slide']}
        travel.append(dict(axis_x_mm=cx,**against(changed_fixed,moving)))
    rep['idler_against_continuous_plates']=travel
    rep['outer_plate_drive_clearance_mm']=min(distance(d['shape'],new['J816_outer_continuous_side_plate']['shape']) for d in moving_drive.values())
    rep['full_bounds_mm']=prior.exact_bounds(inst)
    reference=json.loads((ROOT/'references/retained_dimensions.json').read_text())['full_bounds_mm']
    rep['overall_envelope_unchanged']=all(abs(rep['full_bounds_mm'][j][i]-reference[j][i])<.002 for j in range(2) for i in range(3))
    side_clear=[]
    for x,z,g in s.AXES:
        wheel=next(d for n,d in inst.items() if d['group']==g and d['kind']=='printed')
        side_clear.append(dict(wheel=g,inner_mm=distance(wheel['shape'],new['J815_inner_continuous_side_plate']['shape']),outer_mm=distance(wheel['shape'],new['J816_outer_continuous_side_plate']['shape'])))
    rep['bracket']=dict(side_plate_style='Continuous broad web based on user reference photo',idler_travel_centres_x_mm=list(s.IDLER_LIMITS),idler_opening_height_mm=17.6,drive_access_diameter_mm=12,outer_drive_relief_mm=1,outer_drive_local_thickness_mm=3,plate_thickness_mm=4,plate_inner_faces_y_mm=[-24,24],plate_gap_mm=48,cross_ties=3,
        axle_diameter_mm=8,nominal_plate_bore_mm=8.05,inner_support_interval_y_mm=[-28,-24],outer_support_interval_y_mm=[24,26.5],
        inner_support_length_mm=4,outer_support_length_mm=2.5,clamp_stack_mm=[4,7,26,7,4],clamp_stack_closes=sum([4,7,26,7,4])==48,
        roller_side_clearances=side_clear,axle_end_recess_mm=1.5,axle_screw='M5 x 12 countersunk',axle_thread_engagement_mm=9.5,
        front_tie_screw='M4 x 10 countersunk',rear_tie_screw='M4 x 25 low head + 1 mm washer',tie_thread_engagement_mm=6,
        support_note='Both ends locate in metal cheeks; outer 4 mm plate has 2.5 mm straight shaft engagement before the countersink.')
    rep['cover']=dict(solids=len(new['J711_one_piece_track_housing']['shape'].solids().vals()),nominal_wall_mm=2.5,minimum_wall_over_can_mm=1.,can_clearance_mm=distance(inst['JGY_can_envelope']['shape'],new['J711_one_piece_track_housing']['shape']),fasteners='7 x M3x10',fixed_frame_independent=True)
    rep.update(parts=rows,assembly_solids=solids,bracket_assembly_solids=bracket_solids,elapsed_s=round(time.time()-start,1))
    runs=[rep['static_current_parts'],rep['docked_chassis_static'],rep['chassis_insertion']]+rotations+travel+removal+tools+axle_access+tie_access+plate_removal+[a for r in axle_removal for a in r['samples']]
    rep['pass']=rep['pass'] and rep['overall_envelope_unchanged'] and rep['bracket']['clamp_stack_closes'] and all(min(r['inner_mm'],r['outer_mm'])>=.999 for r in side_clear) and all(not r['hits'] for r in runs)
    rep['scope']='Valid nominal CAD and sampled service checks. Not continuous sweep, load capacity, screw preload or actual X-frame fit validation.'
    (ROOT/'validation.json').write_text(json.dumps(rep,indent=2)+'\n')
    def failures(value,path=''):
        if isinstance(value,dict):
            if value.get('hits'):print('FAIL',path,value['hits'],flush=True)
            for k,v in value.items():failures(v,path+'/'+k)
        if isinstance(value,list):
            for i,v in enumerate(value):failures(v,path+'/'+str(i))
    failures(rep)
    print(json.dumps({k:rep[k] for k in ['pass','static_current_parts','overall_envelope_unchanged','elapsed_s']},indent=2),flush=True)
    assert rep['pass']
    spec=importlib.util.spec_from_file_location('base_viewer',s.REPO/'track_wheel/source/build_viewer.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
    config=v.config();config['rollers']=[[x,z] for x,z,g in s.AXES]
    payload=dict(unit=export.scene_items(inst),bridge=export.scene_items({n:d for n,d in pair.items() if n.startswith(('J314','J3_bridge_'))}),link=v.link_mesh(),config=config,bracket_names=list(bracket))
    (ROOT/'source/j8_scene.json.gz').write_bytes(gzip.compress(json.dumps(payload,separators=(',',':')).encode()))

if __name__=='__main__':main()

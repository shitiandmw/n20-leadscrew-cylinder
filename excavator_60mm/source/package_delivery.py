"""Build a self-contained, checksummed delivery only from passing reports."""
import hashlib,json,zipfile
from design import ROOT,REPO,config,track_poses


def package():
    for relative in ['validation.json','browser_validation.json','simulation/track_dynamics.json','simulation/track_ground_dynamics.json','simulation/track_cad_motion.json','simulation/track_ground_cad_motion.json','simulation/vehicle_dynamics.json','simulation/inherited_arm/validation.json','simulation/packaging.json']:
        report=json.loads((ROOT/relative).read_text())
        assert report['status']=='PASS',f'{relative}: {report.get("failures",report["status"])}'
    assert json.loads((ROOT/'parameters.json').read_text())==config(), 'Exported parameters are stale'
    # Track wheel R5 unit (track_wheel/): CAD checks, MuJoCo design cases and its own viewer.
    wheel=REPO/'track_wheel'
    assert json.loads((wheel/'validation.json').read_text())['summary']['all_checks_pass'], 'track_wheel/validation.json'
    assert json.loads((wheel/'simulation/summary.json').read_text())['design_cases_pass'], 'track_wheel/simulation/summary.json'
    assert json.loads((wheel/'browser_validation.json').read_text())['status']=='PASS', 'track_wheel/browser_validation.json'
    for part in json.loads((wheel/'source/export_report.json').read_text())['parts']:
        assert part['watertight'] and part['step_roundtrip'] and (wheel/'stl'/(part['name']+'.stl')).is_file(), part['name']
    for case in ['track','track_ground']:
        trace_bytes=(ROOT/f'simulation/{case}_trace.json').read_bytes()
        first=json.loads(trace_bytes)[0]
        assert len(first['points'])==config()['track_links_per_side']
        cad=json.loads((ROOT/f'simulation/{case}_cad_motion.json').read_text())
        assert cad['trace_sha256']==hashlib.sha256(trace_bytes).hexdigest(), 'CAD-tested trace has changed: '+case
        for (_,origin,_),actual in zip(track_poses(),first['points']):
            assert max(abs(actual[i]*1000-origin[j]) for i,j in [(0,0),(2,1)])<1e-8, 'Track trace uses a different assembly pose'
    loaded=json.loads((ROOT/'simulation/track_ground_dynamics.json').read_text())
    for check in ['road_rollers_carry_primary_load','each_road_roller_carries_load','carriers_bracket_return_run',
                  'contacting_free_wheels_rotate_forward','contacting_free_wheels_rotate_reverse']:
        assert loaded['checks'].get(check) is True,check
    browser=json.loads((ROOT/'browser_validation.json').read_text())
    assert browser['track_revision']==config()['track_revision']
    for key,path in [('track_trace_sha256','simulation/track_ground_trace.json'),('preview_sha256','3D_preview.html')]:
        assert browser[key]==hashlib.sha256((ROOT/path).read_bytes()).hexdigest(), 'Browser-tested file has changed: '+path
    actuator=json.loads((REPO/'actuator_v6/validation.json').read_text())['U60']
    assert actuator['all_checks_pass'] and actuator['all_meshes_pass'], 'Inherited U60 validation failed'
    board=json.loads((REPO/'actuator_v6/electronics/pcb/V6-U60/check_U60.json').read_text())
    assert not board['drc_errors'] and board['readback_worst_mismatch']==0, 'Inherited U60 board checks failed'
    exported=json.loads((ROOT/'source/export_report.json').read_text())
    for part in exported['parts']:
        assert part['watertight'] and part['step_roundtrip'], part['name']
        for suffix in ['stl','step']:
            assert (ROOT/suffix/(part['name']+'.'+suffix)).is_file(), part['name']
        if part.get('mirrored_stl'):
            assert (ROOT/'stl'/part['mirrored_stl']).is_file(), part['name']
    required=['README.md','ASSEMBLY.md','BOM.csv','BOM.md','build_guide.pdf','simulation_report.pdf','dimension_sheet.pdf',
        '3D_preview.html','step/excavator_complete.step','images/overview.png','images/track_dynamics.png',
        'images/battery_bay.png','images/r2_r3_comparison.png','references/TRACK_SYSTEM.md','images/track_ground_dynamics.png','references/CAB_PROPORTIONS.md','references/berco_sprockets.png','references/berco_rollers.png','source/track_mass_properties.json','track_interfaces.pdf','images/track_interfaces.png','glazing/cab_glazing_front.svg']
    for name in required:assert (ROOT/name).is_file(),name
    folders=[ROOT,REPO/'track_wheel',REPO/'excavator_arm_60mm',REPO/'actuator_v6']
    files=sorted(p for folder in folders for p in folder.rglob('*') if p.is_file() and not {'__pycache__','node_modules','.venv','.git'}.intersection(p.parts)
        and p.suffix not in ['.pyc','.log'] and p!=ROOT/'SHA256SUMS.txt')
    manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(REPO).as_posix()+'\n' for p in files)
    (ROOT/'SHA256SUMS.txt').write_text(manifest)
    target=REPO/'output/excavator_arm60_tracked_r3_track_r5.zip';target.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        z.writestr('START_HERE.txt','Open excavator_60mm/3D_preview.html for the offline model and loaded track-motion playback. The R3 upper body follows the Cat 320 layout (cab front-left, tank housing and toolbox front-right, engine hood, curved 189 mm tail-radius counterweight) with a datasheet-sized two-18650 bay under the hood hatch. Track R5 puts the drive gearmotor inside the sprocket hub (Pololu 37D 150:1 plus a 12:21 internal gear stage on two thin-section bearings) and holds the track with a spring-loaded recoil idler (C-600-072-1500, 77 N preload, 4 mm recoil to a hard stop). The unit has its own folder: open track_wheel/3D_preview.html for sections, exploded and x-ray views and simulation playback; track_wheel/README.md explains it. R4 features remain: Berco-referenced bushing-drive sprockets, outer roller/idler guide flanges and a 394 mm stance around the 308 mm platform. Read excavator_60mm/references/TRACK_SYSTEM.md for the real-machine reference and model adaptations.\nRead excavator_60mm/README.md, ASSEMBLY.md and simulation_report.pdf.\nPrintable vehicle parts are in excavator_60mm/stl (track wheel parts TW01-TW09 also in track_wheel/stl). Retained arm parts are in excavator_arm_60mm/stl; build four V6-U60 actuators from actuator_v6/stl/V6-U60.\nThe complete STEP assembly is excavator_60mm/step/excavator_complete.step.\nThe preview permits full 0-60 mm boom stroke at every angle within +/-150 degrees. Track clearance is operator-controlled. CAD clearance results cover the documented reference samples, not every independent control combination. Read ASSEMBLY.md for operation and the 2S battery power budget.\nKeep these folders together for rebuilding. This is a digitally tested prototype, not a physical payload or print certification.\nSHA256SUMS.txt paths are relative to this archive root.\n')
        for p in files+[ROOT/'SHA256SUMS.txt']:z.write(p,p.relative_to(REPO).as_posix())
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None,'ZIP CRC failed'
        for line in manifest.splitlines():
            digest,name=line.split('  ',1)
            assert hashlib.sha256(z.read(name)).hexdigest()==digest,name
    report=dict(archive=target.relative_to(REPO).as_posix(),files=len(files)+2,bytes=target.stat().st_size,
        sha256=hashlib.sha256(target.read_bytes()).hexdigest(),crc_and_manifest_verified=True)
    (REPO/'output/excavator_arm60_delivery.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':package()

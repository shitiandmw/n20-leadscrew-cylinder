"""Package J8 CAD, English review/media, source and required rebuild inputs."""
from pathlib import Path
import json,hashlib,shutil,zipfile,re
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent;OUT=REPO/'output/jgy370_J8'

def main():
    for name in ['validation.json','motion_geometry_validation.json','browser_validation.json','video_validation.json','media_validation.json','simulation/upper_roller_checks.json']:
        assert json.loads((ROOT/name).read_text())['pass'],name
    assert json.loads((ROOT/'simulation/demo_report.json').read_text())['playback_checks_pass']
    OUT.mkdir(parents=True,exist_ok=True)
    copies={ROOT/'J8_operation.mp4':'JGY370_J8_operation_EN.mp4',ROOT/'J8_design_review.pdf':'JGY370_J8_design_review_EN.pdf',
        ROOT/'images/J8_continuous_frame_review.png':'JGY370_J8_continuous_frame_EN.png',ROOT/'images/J8_axle_section.png':'JGY370_J8_axle_section_EN.png',
        ROOT/'3D_preview.html':'JGY370_J8_interactive_EN.html',ROOT/'step/JGY370_track_J8.step':'JGY370_J8_track.step',
        ROOT/'step/J8_continuous_side_frame_assembly.step':'JGY370_J8_side_frame.step',
        ROOT/'step/J8_docked_chassis_PROPOSAL.step':'JGY370_J8_chassis_PROPOSAL.step'}
    for name in ['J806_continuous_support_frame','J711_one_piece_track_housing','J624_compact_return_roller']:
        for fmt in ['step','stl']:copies[ROOT/fmt/f'{name}.{fmt}']=f'{name}.{fmt}'
    for name in ['J815_inner_continuous_side_plate','J816_outer_continuous_side_plate','J721_supported_roller_axle','J722_bracket_cross_tie','J723_roller_end_spacer']:
        copies[ROOT/'step'/f'{name}.step']=f'{name}.step'
    for p,n in copies.items():shutil.copy2(p,OUT/n)
    files=[p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='HANDOFF.md' and not p.name.startswith(('decoded_','review_page_','initial_geometry_check','PRIOR_HANDOFF_ARCHIVE'))]
    files += [p for p in (REPO/'track_wheel/step').glob('*.step') if p.name!='track_wheel_unit.step']
    files += list((REPO/'track_wheel/stl').glob('*.stl'))
    files += [REPO/'track_wheel/source'/n for n in ['tw_parts.py','tw_design.py','tw_gears.py','tw_checks.py','build_track_wheel.py','build_viewer.py','simulate_track_wheel.py']]
    files += [REPO/'track_wheel/simulation/mass_properties.json',REPO/'track_wheel/BOM.md']
    files += [REPO/'excavator_60mm/source/design.py',REPO/'excavator_arm_60mm/source/kinematics.py',REPO/'excavator_60mm/step/01_chassis_bridge.step',REPO/'excavator_60mm/validation.json']
    files += list((REPO/'actuator_v6/source/vendor').glob('*'))
    files=sorted(set(files));assert all(p.is_file() for p in files)
    for p in files:
        if p.suffix in ['.py','.cjs','.js','.md','.html','.json']:
            assert not re.search(r'[\u3400-\u9fff]',p.read_text()),f'Non-English text: {p}'
    manifest={str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    intro="""# JGY-370 J8 — continuous opposing side frames

Start in track_wheel_jgy370/:
- images/J8_continuous_frame_review.png compares the new side plate to your reference.
- J8_design_review.pdf contains views, mounting details and verification scope.
- step/J8_continuous_side_frame_assembly.step isolates the side plates and five rollers.
- step/JGY370_track_J8.step is the complete right-hand track.
- J8_operation.mp4 shows assembly, outer-side removal and unloaded digital motion.
- 3D_preview.html opens on the side-frame assembly and works offline.
- Read README.md, ASSEMBLY.md and BOM.md before fabrication.

J8 uses broad continuous side plates, following the user's reference frame layout.
Both sides support all five small-wheel axles. The outer side removes as one
piece. The inner motor side has its required drive clearance. Drive bearings
and the sliding idler yoke remain independent; the idler slot preserves travel.
Track size, motor and chassis mounting positions and the one-piece protective
housing are retained. The 4 mm outer plate is locally 3 mm over the drive end.

The current axle pattern fits 30 mm upper and 36 mm lower rollers. Other wheel
sizes require checking axle positions and the track path. Nominal CAD and
sampled service/motion checks pass; physical fits, preload, frame creep,
plate stresses and loaded endurance remain unverified. No load rating is set.

The new video renders J8 geometry using the unchanged J6 unloaded trace;
this is not a new dynamics run, physical footage or an electrical/load test.
Actual X-chassis and left motor installation remain unverified.

Other directories contain rebuild dependencies and unchanged-drive references.
track_wheel_jgy370/source/support contains the retained geometry and checking library. Module
names keep their original part lineage; no earlier JGY release folders are needed.
The unchanged J6 playback and its provenance are in track_wheel_jgy370/simulation.
SHA256.json records all packaged file hashes.
"""
    dest=OUT/'JGY370_J8_complete_EN.zip'
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,'JGY370_J8/'+str(p.relative_to(REPO)))
        z.writestr('JGY370_J8/START_HERE.md',intro)
        z.writestr('JGY370_J8/SHA256.json',json.dumps(manifest,indent=2)+'\n')
    with zipfile.ZipFile(dest) as z:
        assert z.testzip() is None
        for rel,h in manifest.items():assert hashlib.sha256(z.read('JGY370_J8/'+rel)).hexdigest()==h
    report=dict(pass_=True,archive=dest.name,bytes=dest.stat().st_size,zip_crc_pass=True,sha256_entries_verified=len(manifest),english_text_scan_pass=True,
        downloads=[dict(file=n,bytes=(OUT/n).stat().st_size,sha256=hashlib.sha256((OUT/n).read_bytes()).hexdigest()) for n in copies.values()])
    report['pass']=report.pop('pass_');(OUT/'delivery_manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['pass','archive','bytes','sha256_entries_verified']},indent=2))

if __name__=='__main__':main()

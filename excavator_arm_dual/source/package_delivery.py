"""Bind R10 CAD, dynamics, browser and media evidence into a checked archive."""
from pathlib import Path
import hashlib,json,re,zipfile

ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    names=['validation.json','motion_validation.json','path_validation.json','simulation/validation.json','browser_validation.json','video_validation.json']
    reports={name:json.loads((ROOT/name).read_text()) for name in names}
    assert all(r['status']=='PASS' for r in reports.values())
    assert reports['simulation/validation.json']['loaded_150g_at_100N_each_status']=='TRACKS'
    assert reports['simulation/validation.json']['unloaded_cycle_status']=='TRACKS'
    motion_hash=sha(ROOT/'motion.json');html_hash=sha(ROOT/'3D_preview.html')
    for name in ['path_validation.json','simulation/validation.json','video_validation.json']:assert reports[name]['motion_sha256']==motion_hash
    for name in ['browser_validation.json','video_validation.json']:assert reports[name]['html_sha256']==html_hash
    for report in ['motion_validation.json','simulation/validation.json']:
        for name,digest in reports[report]['source_sha256'].items():assert sha(ROOT/'source'/name)==digest
    assert reports['video_validation.json']['sha256']==sha(ROOT/'images/motion_simulation_r10.mp4')
    shape=json.loads((ROOT/'shape_revision.json').read_text());assert shape['status']=='PASS' and shape['source_sha256']==sha(ROOT/'source/kinematics.py')
    export=json.loads((ROOT/'source/export_report.json').read_text())
    assert export['assembly_solids']==114 and len(export['parts'])==13
    assert all(r['watertight'] and r['single_solid'] and r['step_roundtrip_valid'] for r in export['parts'])
    required=['README.md','ASSEMBLY.md','HANDOFF.md','images/structure_reference.png','images/simulation_results.png','step/excavator_arm_assembly.step','images/boom_shape_comparison.png','shape_revision.json']
    assert all((ROOT/name).is_file() for name in required)
    files={p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.name!='delivery_manifest.json'}
    v6=REPO/'actuator_v6'
    files.update((v6/'source').glob('*.py'))
    for folder in ['source/vendor','stl/V6-U60','electronics']:
        files.update(p for p in (v6/folder).rglob('*') if p.is_file())
    for name in ['ASSEMBLY.md','BOM.md','wire_lengths_U60.csv']:
        p=v6/name;files.add(p)
        if p.suffix=='.md':
            for link in re.findall(r'\]\(([^)]+)\)',p.read_text()):
                if '://' not in link:
                    image=p.parent/link;assert image.is_file(),image;files.add(image)
    files=sorted(files)
    manifest=ROOT/'delivery_manifest.json'
    manifest.write_text(json.dumps(dict(revision=10,scope='Dual independent boom drives with deeper boomerang section; 150 g tracks at assumed 100 N each; ideal feedback, no structural or soil qualification',files={str(p.relative_to(REPO)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in files}),ensure_ascii=False,indent=2)+'\n')
    files.append(manifest);out=REPO/'output';out.mkdir(exist_ok=True);target=out/'excavator_arm_dual_boomerang_r10.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for p in files:archive.write(p,str(p.relative_to(REPO)))
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist())=={str(p.relative_to(REPO)) for p in files}
        for p in files:assert hashlib.sha256(archive.read(str(p.relative_to(REPO)))).hexdigest()==sha(p)
    digest=sha(target);target.with_suffix('.zip.sha256').write_text(f'{digest}  {target.name}\n')
    result=dict(status='PASS',revision=10,file=str(target.relative_to(REPO)),bytes=target.stat().st_size,files=len(files),sha256=digest,checks=['Current validation/media hashes agree','All ZIP CRCs valid','Every archived file hash rechecked'],unloaded_motion='TRACKS',loaded_150g_at_100N_each='TRACKS')
    (out/'excavator_arm_r10_delivery.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()

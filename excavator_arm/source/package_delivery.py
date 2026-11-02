"""Portable R2 download: model, regenerated actuators and read-only V6 source package."""
from pathlib import Path
import hashlib,zipfile,json
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent;OUT=REPO/'output';OUT.mkdir(exist_ok=True)
assert json.loads((ROOT/'validation.json').read_text())['status']=='PASS'
assert json.loads((ROOT/'browser_validation.json').read_text())['status']=='PASS'
assert all(v['all_checks_pass'] for v in json.loads((ROOT/'actuators/validation.json').read_text()).values())
assert all(not v['drc_errors'] and v['readback_worst_mismatch']<.002 for v in json.loads((ROOT/'actuators/electronics/pcb/validation.json').read_text()).values())
files=[]
for folder in [ROOT,REPO/'actuator_v6']:
    files.extend(p for p in sorted(folder.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.name!='SHA256SUMS_ARM.txt')
manifest=''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(REPO).as_posix()}\n' for p in files)
(ROOT/'SHA256SUMS_ARM.txt').write_text(manifest)
intro='''# Cat 320 reference arm / V6 / revision 2

Open `excavator_arm/3D_preview.html` for the offline interactive model.

- Main assembly: `excavator_arm/step/excavator_arm_assembly.step` (mm).
- Structural model STEP/STL: `excavator_arm/step/` and `stl/` (eight new structural parts).
- Matching actuators: `excavator_arm/actuators/` (B x2, T x1, K x1; mechanical CAD, STL, boards and checks).
- Dimension drawing: `excavator_arm/dimension_sheet.pdf`.
- Illustrated guide: `excavator_arm/build_guide.pdf`.
- Reference comparison: `excavator_arm/images/reference_comparison.png`.
- Full dimensions, BOM, assembly and limits: `excavator_arm/README.md`.
- Verification: `excavator_arm/validation.json`, `browser_validation.json`, and actuator validation reports.

The arm follows Cat 320 reach-boom proportions at 1:12: 475 mm boom, 241.667 mm stick, 100 mm bucket width, 130.833 mm bucket tip radius. Detailed mounts and sections are adapted, not factory CAD. It has a bent box boom, paired lift cylinders and an inward-opening bucket on a fixed base. There is no chassis.

Leadscrews are 100 mm for both boom cylinders, 120 mm for the stick and 75 mm for the bucket. All matching actuator parts and boards are regenerated. The original 55 mm short actuator is not the right length for this revision.

Keep both folders beside each other for rebuilds. `actuator_v6/` is the unchanged original source/reference dependency. Do not substitute its original short PCB/parts into the new B/T/K designs.

This replaces the first plate-link arm. The 509 mm boom needs a large printer or an engineered split before manufacture. No physical print/load test has been performed. Below-mounting-plane digging positions need a clear working recess on a solid-floor demonstrator. External wires and collar set screws are outside the collision model.
'''
target=OUT/'excavator_arm_cat320_r2.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    z.writestr('START_HERE.md',intro)
    for p in files+[ROOT/'SHA256SUMS_ARM.txt']:z.write(p,p.relative_to(REPO).as_posix())
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
    for required in ['excavator_arm/step/excavator_arm_assembly.step','excavator_arm/actuators/step/V6-T/04_rod.step','excavator_arm/3D_preview.html']:assert required in z.namelist()
    print('Verified',len(z.namelist()),'entries;',round(target.stat().st_size/1e6,2),'MB:',target)

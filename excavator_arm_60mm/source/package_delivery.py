"""Portable 60 mm R4 download: model, regenerated actuators and read-only V6 source package."""
from pathlib import Path
import hashlib,zipfile,json
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent;OUT=REPO/'output';OUT.mkdir(exist_ok=True)
arm_report=json.loads((ROOT/'validation.json').read_text())
assert arm_report['status']=='PASS' and arm_report['revision']==4
browser_report=json.loads((ROOT/'browser_validation.json').read_text())
assert browser_report['status']=='PASS' and browser_report['revision']==4
assert json.loads((REPO/'actuator_v6/validation.json').read_text())['U60']['all_checks_pass']
board=json.loads((REPO/'actuator_v6/electronics/pcb/V6-U60/check_U60.json').read_text())
assert not board['drc_errors'] and board['readback_worst_mismatch']<.002
files=[]
for folder in [ROOT,REPO/'actuator_v6']:
    files.extend(p for p in sorted(folder.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.name!='SHA256SUMS_ARM.txt')
manifest=''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(REPO).as_posix()}\n' for p in files)
(ROOT/'SHA256SUMS_ARM.txt').write_text(manifest)
intro='''# Cat 320 reference arm / V6 / 60 mm edition / revision 4

Open `excavator_arm_60mm/3D_preview.html` for the offline interactive model.

- Main assembly: `excavator_arm_60mm/step/excavator_arm_assembly.step` (mm).
- Structural model STEP/STL: `excavator_arm_60mm/step/` and `stl/` (eight new structural parts).
- Matching actuators: four V6-U60 from `actuator_v6/`: STL in `actuator_v6/stl/V6-U60/`, STEP in `step/V6-U60/`, board files and upload zip in `electronics/pcb/`. `actuator_v6/README.md`, `BOM.md`, `ASSEMBLY.md` and `3D_preview.html` (V6-U60 button, schematic linked to the board) cover it.
- Dimension drawing: `excavator_arm_60mm/dimension_sheet.pdf`.
- Illustrated guide: `excavator_arm_60mm/build_guide.pdf`.
- Lift mount revision: `excavator_arm_60mm/images/lift_mount_comparison.png`.
- Comparison with R2: `excavator_arm_60mm/images/version_comparison.png`.
- Reference comparison: `excavator_arm_60mm/images/reference_comparison.png`.
- Full dimensions, BOM, assembly and limits: `excavator_arm_60mm/README.md`.
- Verification: `excavator_arm_60mm/validation.json` and `browser_validation.json`; for the actuator, `actuator_v6/validation.json` and `actuator_v6/electronics/pcb/V6-U60/check_U60.json`.

The arm follows Cat 320 reach-boom proportions at 1:15: 380 mm boom, 193.333 mm stick, 80 mm bucket width, 104.667 mm bucket tip radius. Detailed mounts and sections are adapted, not factory CAD. It has a bent box boom, paired lift cylinders and an inward-opening bucket on a fixed base. There is no chassis.

R4 moves both upper lift pins forward/down onto the boom body, adds 8 mm cheeks and a cross-web, and uses one 126 mm steel cross-pin with outside collars. Matching lower anchors preserve the 2-69 degree boom range. Replace the R3 boom and base together. Printed load capacity remains untested.

All four actuators use 75 mm leadscrews, 60 mm strokes and 140-200 mm pin spacing. Build four copies of the common U60 actuator and board. The original 55 mm short actuator is not the right length for this revision.

Keep both folders beside each other for rebuilds. `actuator_v6/` holds the actuator in three lengths, V6-S, V6-U60 and V6-L; this arm uses V6-U60 only. Do not substitute the V6-S or V6-L parts or boards.

This is a separate version; the 1:12 R2 remains available. The 414 mm boom needs a large printer or an engineered split before manufacture. No physical print/load test has been performed. Below-mounting-plane digging positions need a clear working recess on a solid-floor demonstrator. External wires and collar set screws are outside the collision model.
'''
target=OUT/'excavator_arm_cat320_60mm_r4.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    z.writestr('START_HERE.md',intro)
    for p in files+[ROOT/'SHA256SUMS_ARM.txt']:z.write(p,p.relative_to(REPO).as_posix())
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
    for required in ['excavator_arm_60mm/step/excavator_arm_assembly.step','actuator_v6/step/V6-U60/04_rod.step','excavator_arm_60mm/3D_preview.html']:assert required in z.namelist()
    print('Verified',len(z.namelist()),'entries;',round(target.stat().st_size/1e6,2),'MB:',target)

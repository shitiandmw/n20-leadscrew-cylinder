"""Package checked revision F STEP/STL files, offline viewers, reports and notes.

Every packaged file must be bound by a passing revision F report. Every payload
is listed in a SHA-256 manifest and read back from the ZIP.
"""
import ast
import hashlib
import json
from pathlib import Path
import re
import zipfile

import fitz
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle

X1 = Path(__file__).resolve().parents[1]
J9 = X1.parent / 'J9'
REPO = X1.parents[1]
OUT = REPO / 'output'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return digest(Path(path).read_bytes())


def verify_bound_files(mapping):
    for name, expected in mapping.items():
        path = Path(name)
        if not path.is_absolute():
            options = [REPO/path, X1/path, J9/path]
            matches = [p for p in options if p.is_file() and sha(p) == expected]
            assert matches, f'Validated file changed or is missing: {name}'
        else:
            assert path.is_file() and sha(path) == expected, name


def revision_f(value):
    return str(value).strip().upper() == 'F' or bool(re.search(r'\brev(?:ision)?\s*f\b', str(value), re.I))


def gate():
    paths = [X1/'arc_seat_mount_validation.json', X1/'revf_refresh_validation.json',
             X1/'revf_part_exports.json', X1/'arc_mount_drawing.json',
             X1/'browser_validation.json', J9/'browser_validation.json',
             J9/'validation.json', J9/'revf_track_validation.json', J9/'spring_guide_validation.json']
    reports = {p.name if p.parent == X1 else 'J9_'+p.name: json.loads(p.read_text()) for p in paths}
    assert all(d.get('pass') is True for d in reports.values()), 'A revision F check failed'
    joint = reports['arc_seat_mount_validation.json']
    track = reports['J9_revf_track_validation.json']
    for report in (joint, track):
        assert revision_f(report['revision']), 'Stale model validation report'
        assert report.get('source_sha256') and report.get('exported_step_sha256'), 'Unbound geometry check'
    assert track['validation_method'].startswith('fresh'), 'Track validation must be a fresh full run'
    assert sha(J9/'validation.json') == sha(J9/'revf_track_validation.json'), 'Track report copies differ'
    assert track['spring_guide_report_sha256'] == sha(J9/'spring_guide_validation.json')
    for report in reports.values():
        for field in ('source_sha256', 'exported_step_sha256', 'exported_stl_sha256',
                      'upper_assembly_input_sha256', 'arm_reference_input_sha256',
                      'assembly_input_sha256', 'reference_files_sha256'):
            if isinstance(report.get(field), dict):
                verify_bound_files(report[field])
    refresh = reports['revf_refresh_validation.json']
    assert refresh['revision'] == 'F'
    verify_bound_files(refresh['inputs'])
    for row in refresh['assemblies'] + refresh['scenes']:
        assert sha(REPO/row['file']) == row['sha256'], row['file']
    assert len(refresh['assemblies']) == 3
    drawing = reports['arc_mount_drawing.json']
    assert drawing['revision'] == 'F'
    verify_bound_files(drawing['inputs'])
    verify_bound_files(drawing['outputs'])
    exports = reports['revf_part_exports.json']
    assert exports['revision'] == 'F'
    rows = exports['exports']
    assert {r['name'] for r in rows} == {'X101_X_frame', 'J901_H_frame', 'J909_housing',
                                        'J901_H_frame_right', 'J909_housing_right',
                                        'J902_sprocket', 'J904_roller', 'J906_idler_wheel'}
    for row in rows:
        assert (row['pass'] and row['stl_watertight'] and row['stl_components'] == 1 and row['step_roundtrip']
                and row['solids'] == 1 and row['matches_current_source'])
        assert sha(REPO/row['step_file']) == row['step_sha256']
        assert sha(REPO/row['stl_file']) == row['stl_sha256']
    frame = next(r for r in rows if r['name'] == 'X101_X_frame')
    for contract in frame['envelope_contract'].values():
        assert contract['pass'] is True
        assert contract['expected_bounds_mm'] == [-77.5, 77.5, -137.5, 137.5, 34.0, 85.0]
        assert contract['max_error_mm'] <= contract['tolerance_mm'] <= 1e-4
    for root, key in ((X1, 'browser_validation.json'), (J9, 'J9_browser_validation.json')):
        report = reports[key]
        assert sha(root/'source/check_viewer.cjs') == report['checker_sha256']
        assert sha(root/'3D_preview.html') == report['html_sha256']
        scene = 'x1_scene.json.gz' if root == X1 else 'j9_scene.json.gz'
        assert sha(root/'source'/scene) == report['scene_sha256']
        assert not report['errors'] and not report['network']
        if root == X1:
            assert {'mounts','frame'} <= report.get('model_views',{}).keys()
            assert set(report['model_views']) == set(report['model_screenshot_sha256'])
        for view, expected in report.get('screenshot_sha256', {}).items():
            assert sha(root/report['views'][view]) == expected
        for view, expected in report.get('model_screenshot_sha256', {}).items():
            assert sha(root/report['model_views'][view]) == expected
    for p in (X1/'README.md', X1/'ASSEMBLY.md', X1/'BOM.md', J9/'README.md', J9/'ASSEMBLY.md'):
        assert '<<<<<<<' not in p.read_text()
    section_path = X1/'revf_leg_sections.json'
    sections = json.loads(section_path.read_text())
    assert sections['revision'] == 'F' and sections['geometry_calculation_pass'] is True
    assert sections['not_strength_validation'] is True
    verify_bound_files(sections['source_and_step_sha256'])
    reports[section_path.name] = sections
    assert (X1/'X1_arc_mount_detail.pdf').is_file()
    return reports, {str(p.relative_to(REPO)): sha(p) for p in [*paths, section_path]}


def build_review():
    OUT.mkdir(exist_ok=True)
    exports = json.loads((X1/'revf_part_exports.json').read_text())['exports']
    frame_row = next(r for r in exports if r['name'] == 'X101_X_frame')
    print_bounds = ' × '.join(f'{value:g}' for value in frame_row['print_bounds_mm'])
    sections = json.loads((X1/'revf_leg_sections.json').read_text())
    minima = sections['minima']['all_sampled_planes']
    section_note = ('Sampled arm sections give minimum section moduli of '
                    f'{minima["vertical_I_over_c_mm3"]["minimum_sampled_value"]:.0f} mm³ (vertical) and '
                    f'{minima["lateral_I_over_c_mm3"]["minimum_sampled_value"]:.0f} mm³ (lateral); ')
    styles = getSampleStyleSheet()
    body = styles['BodyText']
    body.leading = 14
    story = [Paragraph('X1 revision F', styles['Title']),
             Paragraph('Straight X101 arms seated in the track main beam', styles['Heading2']), Spacer(1, 8)]
    story += [Paragraph('The updated X101 frame has four straight 28 mm arms whose flat ends sit in plain 1.5 mm recesses '
                        'in the matching J901 track frames; the J909 housings follow the arms. Two screws, one each side of the '
                        'arm\'s centre web, clamp each joint through plain holes. '
                        'The accepted enclosed spring guide and travel are retained.', body), Spacer(1, 10)]
    for image_path, caption in [(X1/'images/X1_mounts_model.png', 'Front left connection.<br/><br/>Blue: X101 frame. Yellow: track beam and housing. Inspection colors distinguish the mating parts.<br/><br/>The arm end fits into the shallow beam seat. The screw heads sit in side slots under the closed deck; the rear washers and nuts sit outside the main plate.'),
                                (X1/'images/X1_frame_model.png', 'X101 with the tracks, upper assembly and hardware hidden.<br/><br/>Each arm keeps its width to the track; the deck and the arched underside are single curves. The track recess supports and locates the flat arm ends.'+f'<br/><br/>Print bounds: {print_bounds} mm.')]:
        with fitz.open(image_path) as source:
            w, h = source[0].rect.width, source[0].rect.height
        thumbnail = Image(str(image_path), width=300, height=300*h/w)
        panel = Table([[thumbnail, Paragraph(caption, body)]], colWidths=[340, 150])
        panel.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                                   ('LEFTPADDING', (0, 0), (-1, -1), 0),
                                   ('RIGHTPADDING', (0, 0), (-1, -1), 8)]))
        story += [panel, Spacer(1, 8)]
    story += [Paragraph('Use the matched revision F parts together. Open 3D_preview.html for interactive '
                        'inspection; STEP contains the coloured assemblies and individual parts; STL is '
                        'oriented for printing. The upper STEP includes the fixed ARM60 base; the moving arm in the viewer is a reference. Lower bare X101 vertically into both aligned tracks before fastening. For removal, lower the prepared track at least 80 mm before sliding it outward. Follow ASSEMBLY.md for preparation and support.', body), Spacer(1, 8),
              Paragraph('Nominal geometry, motion and access checks are recorded in arc_seat_mount_validation.json. '
                        + section_note +
                        'these are geometric values and do not validate printed strength. '
                        'No payload rating is assigned: printed fit, stiffness, creep and durability still '
                        'require physical testing.', body)]
    cover = OUT/'X1_revF_review_cover.pdf'
    SimpleDocTemplate(str(cover), pagesize=A4, leftMargin=42, rightMargin=42,
                      topMargin=36, bottomMargin=36).build(story)
    review = OUT/'X1_revF_model_review.pdf'
    with fitz.open(cover) as doc:
        assert doc.page_count == 1, f'Review cover overflows onto {doc.page_count} pages'
    combined = fitz.open()
    for path in (cover, X1/'X1_arc_mount_detail.pdf'):
        with fitz.open(path) as doc:
            combined.insert_pdf(doc)
    combined.save(review)
    combined.close()
    cover.unlink()
    with fitz.open(review) as doc:
        for page in doc:
            for block in page.get_text('dict')['blocks']:
                assert block['type'] != 0 or (page.rect+(-.5,-.5,.5,.5)).contains(fitz.Rect(block['bbox']))
    return review


def collect():
    files = []
    for root in (X1, J9):
        for directory in ('step', 'stl'):
            candidates = [p for p in (root/directory).iterdir() if p.is_file() and p.suffix in ('.step', '.stl')]
            assert not any('_tmp.' in p.name or '.tmp.' in p.name for p in candidates), 'Unfinished CAD export remains'
            files += candidates
        files += [root/name for name in ('README.md', 'ASSEMBLY.md', 'BOM.md', '3D_preview.html', 'browser_validation.json')]
        files += [p for p in (root/'source').iterdir()
                  if p.is_file() and p.suffix in ('.py', '.cjs', '.html', '.gz')]
    files += [X1/'arc_seat_mount_validation.json', X1/'revf_refresh_validation.json', X1/'revf_part_exports.json',
              X1/'revf_leg_sections.json', X1/'arc_mount_drawing.json', X1/'images/X1_arc_mount_detail.png',
              X1/'REV_F_NOTES.md', X1/'X1_arc_mount_detail.pdf', X1/'TURNTABLE.md',
              J9/'validation.json', J9/'revf_track_validation.json', J9/'spring_guide_validation.json',
              X1/'X1_layout.pdf', X1/'images/X1_layout.png', J9/'J9_layout.pdf', J9/'images/J9_layout.png',
              J9/'J9_spring_guide_detail.pdf', J9/'images/J9_spring_guide_detail.png', J9/'motor_selection.json']
    files += [p for p in (X1/'references').rglob('*') if p.is_file()]
    # These two images document retained mechanisms, explicitly labelled as
    # references in their Markdown captions rather than new joint validation.
    files += [X1/'images/X1_swing_sim_p1.png', J9/'images/J9_drive_section.png']
    for root in (X1, J9):
        browser = json.loads((root/'browser_validation.json').read_text())
        files += [root/name for name in browser['views'].values()]
        files += [root/name for name in browser.get('model_views', {}).values()]
    # Include local imports of the packaged scripts. External repository
    # dependencies remain documented requirements rather than duplicated here.
    selected = set(files)
    sources = [J9/'source', X1/'source']
    pending = [p for p in selected if p.suffix == '.py']
    inspected = set()
    while pending:
        p = pending.pop()
        if p in inspected:
            continue
        inspected.add(p)
        modules = set()
        for node in ast.walk(ast.parse(p.read_text())):
            if isinstance(node, ast.Import):
                modules.update(n.name.split('.')[0] for n in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module.split('.')[0])
        for module in modules:
            options = [p.parent/(module+'.py'), *(root/(module+'.py') for root in sources)]
            dependency = next((q for q in options if q.is_file()), None)
            if dependency is not None and dependency not in selected:
                selected.add(dependency)
                pending.append(dependency)
    return sorted(selected)


def main():
    reports, bound = gate()
    review = build_review()
    preview = OUT/'X1_revF_connection.png'
    preview.write_bytes((X1/'images/X1_mounts_model.png').read_bytes())
    files = collect()
    for p in files:
        assert p.is_file(), p
    intro = ('X1 revision F — Straight X101 arms seated in the track main beam\n\n'
             'Read X1_revF_model_review.pdf and track_wheel_jgy370/X1/REV_F_NOTES.md.\n'
             'The actual CAD and matching printable parts are in X1/step, X1/stl, J9/step and J9/stl\n'
             'below track_wheel_jgy370. Use all revision F mating parts together.\n'
             'Open either 3D_preview.html directly in a browser; no server or network is needed.\n'
             'The upper STEP includes the fixed ARM60 base; the moving arm shown in the viewer is a reference.\n'
             'ASSEMBLY.md gives the assembly order, hardware and tool access.\n'
             'No payload or tightening-torque rating has been physically validated.\n'
             'The source uses modules from the original repository and requires CadQuery.\n'
             'All manufacturing files and validation reports are revision F.\n'
             'SHA256SUMS.json checks every payload except the manifest itself.\n').encode()
    generated = {review.name: review.read_bytes(), preview.name: preview.read_bytes(),
                 'START_HERE.txt': intro}
    manifest = {str(p.relative_to(REPO)): sha(p) for p in files}
    manifest.update({name: digest(data) for name, data in generated.items()})
    for name, expected in bound.items():
        assert manifest.get(name) == expected, name
    archive = OUT/'X1_revF_arc_seat_connections.zip'
    temporary = archive.with_suffix('.zip.tmp')
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in files:
            z.write(p, str(p.relative_to(REPO)))
        for name, data in generated.items():
            z.writestr(name, data)
        z.writestr('SHA256SUMS.json', json.dumps(manifest, indent=2)+'\n')
    with zipfile.ZipFile(temporary) as z:
        assert len(z.namelist()) == len(manifest)+1
        assert set(z.namelist()) == set(manifest) | {'SHA256SUMS.json'}
        assert z.testzip() is None
        assert json.loads(z.read('SHA256SUMS.json')) == manifest
        assert all(digest(z.read(name)) == value for name, value in manifest.items())
    # Inputs must remain the checked versions throughout review and packaging.
    gate()
    assert all(sha(p) == manifest[str(p.relative_to(REPO))] for p in files)
    assert sha(review) == manifest[review.name]
    assert sha(preview) == manifest[preview.name]
    temporary.replace(archive)
    delivery = dict(revision='F', archive=str(archive.relative_to(REPO)), bytes=archive.stat().st_size,
                    sha256=sha(archive), entries=len(manifest)+1, review=str(review.relative_to(REPO)),
                    review_sha256=sha(review), preview=str(preview.relative_to(REPO)),
                    preview_sha256=sha(preview), checked_reports=bound, zip_crc=True,
                    payload_checksums=True, **{'pass': True})
    (OUT/'X1_revF_delivery.json').write_text(json.dumps(delivery, indent=2)+'\n')
    print(json.dumps(delivery, indent=2))


if __name__ == '__main__':
    main()

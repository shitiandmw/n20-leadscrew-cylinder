"""Refresh revision F assemblies and offline scenes from current part exports.

Unchanged assembly components keep their original B-reps, names, placements and
colours. Previous joint hardware is replaced by x1_parts.mount_hardware().
STEP exports are checked before replacing existing files.
Run after exporting X101, the left/right J901/J909 parts, J902, J904 and J906.
J904 (the roller) is placed at the seven roller stations of each track and J906 (the idler wheel) at the idler.
J902 (the sprocket) and the bought drive-hub group around it (j9_parts.drive_hub_hardware(): coupling, sprocket
screws, set screw) are replaced as one group, because the hub's part names change with the hub: any earlier hub's
components (the Pololu #1999 hub, its M3 x 25 screws and two set screws until 2026-11-12) are removed and the
current ones added, in the J9 assembly, both tracks of the X1 chassis and both scenes.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import time
import uuid

import cadquery as cq

ROOT = Path(__file__).resolve().parent.parent
J9 = ROOT.parent / 'J9'
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def color_key(color):
    return tuple(round(v, 8) for v in color.toTuple()) if color else None


def step_normalised(shape):
    """A freshly modelled shape as it reads back from STEP.

    STEP stores exact intersection curves (the coupling's set-screw hole through its boss) as B-splines, so the first
    round-trip changes such a shape slightly (0.05 mm3 of 4162 on the coupling, against a 1e-8 relative check) and
    refresh_step() would reject the assembly. After one export and import the shape is stable, and the result is the
    same in every run. Mirrored copies must be normalised again after mirroring."""
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)/'part.step'
        cq.exporters.export(cq.Workplane(obj=shape), str(path))
        result = cq.importers.importStep(str(path)).val()
    assert result.isValid() and len(result.Solids()) == len(shape.Solids())
    return result


def drive_hub(name):
    """J902 and the bought hub group around it, by component name (L_/R_ prefixes in the X1 chassis). The names of
    earlier hubs match too, so that their components are replaced rather than left beside the current ones."""
    base = name[2:] if name.startswith(('L_', 'R_')) else name
    return base == 'J902_sprocket' or base.startswith(('Pololu_1999_hub', 'flange_coupling_', 'hub_screw_',
                                                       'hub_set_screw_'))


def components_from_assembly(assembly):
    """Named placed shapes from a loaded assembly, without regenerating design geometry."""
    result = {}
    for shape, name, location, color in assembly:
        key = name.rsplit('/', 1)[-1]
        assert key not in result, f'Duplicate component name: {key}'
        result[key] = dict(shape=shape.moved(location), raw=shape, color=color_key(color), path=name,
                           location=location)
    return result


def component_metadata(parts):
    return {name: dict(path=row['path'], color=row['color'],
                       location=tuple(tuple(round(v, 8) for v in vec) for vec in row['location'].toTuple()))
            for name, row in parts.items()}


def signature(shape):
    b = shape.BoundingBox()
    return dict(solids=len(shape.Solids()), faces=len(shape.Faces()),
                volume=shape.Volume(), area=shape.Area(),
                bounds=[b.xmin, b.xmax, b.ymin, b.ymax, b.zmin, b.zmax])


def signature_matches(a, b):
    return (a['solids'] == b['solids'] and a['faces'] == b['faces'] and
            abs(a['volume']-b['volume']) <= max(1e-4, abs(a['volume'])*1e-8) and
            abs(a['area']-b['area']) <= max(1e-4, abs(a['area'])*1e-8) and
            max(abs(x-y) for x, y in zip(a['bounds'], b['bounds'])) < 1e-5)


def cached_assembly(path):
    """Read a STEP assembly, reusing only a checked native cache of its bytes.

    XBF stores the original OpenCascade assembly and B-reps. A cache is accepted
    only when its STEP hash, native-file hash, component metadata and geometry
    signatures all match. Missing or damaged caches are regenerated from STEP.
    Final assembly exports still undergo an independent STEP round-trip.
    """
    path = Path(path)
    key = sha(path)
    # The cache identity is the complete STEP hash. Every native hash,
    # component record and geometry signature is verified before reuse.
    directory = Path('/tmp/x1-assembly-cache')
    directory.mkdir(exist_ok=True)
    native, metadata = directory/(key+'.xbf'), directory/(key+'.json')

    def inspect(assembly):
        rows = components_from_assembly(assembly)
        meta = json.loads(json.dumps(component_metadata(rows)))
        sig = {name: signature(row['shape']) for name, row in rows.items()}
        return meta, sig

    def matches(record, meta, sig):
        return (meta == record['components'] and sig.keys() == record['signatures'].keys()
                and all(signature_matches(record['signatures'][n], s) for n, s in sig.items()))

    if native.exists() and metadata.exists():
        try:
            record = json.loads(metadata.read_text())
            if record.get('step_sha256') == key and record.get('xbf_sha256') == sha(native):
                print('Read checked native cache', path.name, flush=True)
                assembly = cq.Assembly.load(str(native))
                if matches(record, *inspect(assembly)):
                    assert sha(path) == key, 'STEP changed while loading cache'
                    return assembly
        except (OSError, ValueError, KeyError):
            pass

    print('Import STEP assembly', path.name, flush=True)
    assembly = cq.Assembly.load(str(path))
    meta, sig = inspect(assembly)
    temporary = directory/(key+'.'+uuid.uuid4().hex+'.xbf')
    assembly.export(str(temporary))
    checked = cq.Assembly.load(str(temporary))
    record = dict(step_sha256=key, xbf_sha256=sha(temporary), components=meta, signatures=sig)
    assert matches(record, *inspect(checked)), 'Native cache changed component geometry or metadata'
    assert sha(path) == key, 'STEP changed while preparing native cache'
    temporary.replace(native)
    temporary_metadata = directory/(key+'.'+uuid.uuid4().hex+'.json.tmp')
    temporary_metadata.write_text(json.dumps(record))
    temporary_metadata.replace(metadata)
    return assembly


def part(path):
    print('Load current part', Path(path).name, flush=True)
    # Final scene refresh reuses the same checked part bytes. Cache only an
    # exact imported B-rep, keyed by the complete STEP hash, to avoid repeating
    # expensive STEP parsing. The cache has its own checksum and round-trip
    # signature; a missing or changed cache falls back to the delivered STEP.
    key = sha(path)
    cache_dir = Path('/tmp/x1-part-cache')
    cache_dir.mkdir(exist_ok=True)
    cache = cache_dir/(key+'.brep')
    metadata = cache_dir/(key+'.json')
    if cache.exists() and metadata.exists():
        try:
            info = json.loads(metadata.read_text())
        except (OSError, ValueError):
            info = {}
        if info.get('step_sha256') == key and info.get('brep_sha256') == sha(cache):
            result = cq.Shape.importBrep(str(cache))
            assert result.isValid() and len(result.Solids()) == 1
            assert signature_matches(info['signature'], signature(result))
            assert sha(path) == key, 'Part changed while loading cached geometry'
            return result
    imported = cq.importers.importStep(str(path)).val()
    assert imported.isValid() and len(imported.Solids()) == 1, path
    assert sha(path) == key, 'Part changed while loading'
    temporary = cache_dir/(key+'.'+uuid.uuid4().hex+'.tmp.brep')
    imported.exportBrep(str(temporary))
    # Return the B-rep read back from the cache file, not the STEP import itself. The two are the same geometry, but
    # they tessellate slightly differently, so a scene written on a first run (empty cache) would fail a later
    # --verify that reads the cache (seen on 2026-11-12). Every run now uses the same shape.
    result = cq.Shape.importBrep(str(temporary))
    assert result.isValid() and len(result.Solids()) == 1, path
    assert signature_matches(signature(imported), signature(result)), path
    brep_sha256 = sha(temporary)
    temporary.replace(cache)
    temporary_metadata = cache_dir/(key+'.'+uuid.uuid4().hex+'.json.tmp')
    temporary_metadata.write_text(json.dumps(dict(step_sha256=key, brep_sha256=brep_sha256, signature=signature(result))))
    temporary_metadata.replace(metadata)
    return result


def mesh(shape):
    vertices, triangles = shape.tessellate(.08, .15)
    return dict(vertices=[[round(p.x, 4), round(p.y, 4), round(p.z, 4)] for p in vertices],
                triangles=[list(t) for t in triangles])


def refresh_step(path, replacements, hardware=None, drive=None):
    """drive: the current drive-hub group {name: dict(shape=, color=)}; every older drive-hub component is removed."""
    before_hash = sha(path)
    print('Read', path.name, flush=True)
    assembly = cached_assembly(path)
    before = components_from_assembly(assembly)
    before_meta = component_metadata(before)
    signatures = {name: signature(row['shape']) for name, row in before.items()}
    assert replacements.keys() <= before.keys(), (path, replacements.keys() - before.keys())
    drive = drive or {}
    assert not set(drive) & set(replacements)
    old_drive = sorted(n for n in before if drive and drive_hub(n))
    drive_current = (set(old_drive) == set(drive) and
                     all(signature_matches(signatures[n], signature(row['shape'])) and
                         before[n]['color'] == color_key(cq.Color(*row['color'])) for n, row in drive.items()))
    # A full J9 build may already have produced and checked this exact assembly.
    # Preserve its bytes so its own export hashes remain meaningful.
    if hardware is None and drive_current and all(signature_matches(signatures[n], signature(s))
                                                  for n, s in replacements.items()):
        compound = assembly.toCompound()
        assert compound.isValid()
        assert sha(path) == before_hash
        print('Already current; preserve checked bytes', path.name, flush=True)
        return dict(file=str(path.relative_to(REPO)), before_sha256=before_hash, sha256=before_hash,
                    components=len(before), solids=len(compound.Solids()), replaced=[],
                    requested_replacements=sorted(replacements), removed=[], added=[],
                    unchanged_components=len(before), names_placements_colors_preserved=True,
                    unchanged_BRep_identity=True, roundtrip_valid=True, already_current=True,
                    **{'pass': True})
    removed = []
    if hardware is not None:
        removed = [name for name in before if name.startswith(('clamp_', 'mount_'))]
        for name in removed:
            assembly.remove(name)
    for name in old_drive:
        assembly.remove(name)
    for name, replacement in replacements.items():
        nodes = [node for key, node in assembly.traverse() if key == name and node.obj is not None]
        assert len(nodes) == 1, name
        node = nodes[0]
        node.obj = replacement.moved(before[name]['location'].inverse)
        for attr in ('_subshape_names', '_subshape_colors', '_subshape_layers'):
            getattr(node, attr).clear()
    for name, row in (hardware or {}).items():
        assert name.startswith('mount_'), 'Hardware must use the mount_ prefix'
        assert name not in before or name in removed
        assembly.add(row['shape'], name=name, color=cq.Color(*row['color']))
    for name, row in drive.items():
        assert drive_hub(name), name
        assembly.add(row['shape'], name=name, color=cq.Color(*row['color']))
    after = components_from_assembly(assembly)
    unchanged = set(before) - set(replacements) - set(removed) - set(old_drive)
    assert set(after) == unchanged | set(replacements) | set(hardware or {}) | set(drive)
    assert all(before[n]['raw'].wrapped.IsSame(after[n]['raw'].wrapped) for n in unchanged)
    after_meta = component_metadata(after)
    assert all(before_meta[n] == after_meta[n] for n in unchanged | set(replacements))
    relocations = {}
    for name in replacements:
        if name.endswith(('insert_M3_0', 'housing_screw_M3x8_0', 'insert_M3_2', 'housing_screw_M3x8_2')):
            old = before[name]['shape'].Center()
            new = after[name]['shape'].Center()
            delta = [new.x-old.x, new.y-old.y, new.z-old.z]
            if max(abs(v) for v in delta) > 1e-6:
                relocations[name] = dict(before_mm=[old.x, old.y, old.z], after_mm=[new.x, new.y, new.z],
                                         translation_mm=delta,
                                         reason='Housing attachment moved to clear the arc-support and external-fastener envelopes')
    expected = {name: signature(row['shape']) for name, row in after.items()}
    temporary = path.with_name(path.stem + '.revf_tmp.step')
    print('Export and round-trip', path.name, len(after), 'components', flush=True)
    assembly.export(str(temporary))
    checked_assembly = cached_assembly(temporary)
    checked = components_from_assembly(checked_assembly)
    assert set(checked) == set(after)
    assert component_metadata(checked) == after_meta, 'Names/colours/placements changed'
    for name, row in checked.items():
        assert signature_matches(expected[name], signature(row['shape'])), name
        if name in unchanged:
            assert signature_matches(signatures[name], signature(row['shape'])), name
    compound = checked_assembly.toCompound()
    assert compound.isValid()
    assert len(compound.Solids()) == sum(row['solids'] for row in expected.values())
    assert sha(path) == before_hash, 'Input changed during refresh'
    temporary.replace(path)
    return dict(file=str(path.relative_to(REPO)), before_sha256=before_hash, sha256=sha(path),
                components=len(checked), solids=len(compound.Solids()), replaced=sorted(replacements),
                removed=removed, added=sorted(hardware or {}),
                drive_hub_removed=old_drive, drive_hub_added=sorted(drive), unchanged_components=len(unchanged),
                names_placements_colors_preserved=True, unchanged_BRep_identity=True,
                intentional_hardware_relocations=relocations,
                roundtrip_valid=True, **{'pass': True})


def drive_rows(drive):
    """Scene rows of the drive-hub group, as build_j9.write_scene() makes them."""
    return [dict(name=name, color=list(row['color']), group='drive', kind=row['kind'], source=row['source'],
                 **mesh(_solid(row['shape']))) for name, row in drive.items()]


def refresh_scenes(frame, left_frame, left_housing, hardware, track_y, track_hardware, drive):
    track_path = J9 / 'source/j9_scene.json.gz'
    path = ROOT / 'source/x1_scene.json.gz'
    track = json.loads(gzip.decompress(track_path.read_bytes()))
    data = json.loads(gzip.decompress(path.read_bytes()))
    changes = {'J901_H_frame': left_frame, 'J909_housing': left_housing}
    changes.update(track_hardware)
    for name, shape in changes.items():
        rows = [row for row in track['unit'] if row['name'] == name]
        assert len(rows) == 1, name
        rows[0].update(mesh(shape))
    # The drive-hub group goes where the old one was, so the unit keeps its order.
    first = next(i for i, row in enumerate(track['unit']) if drive_hub(row['name']))
    kept = [row for row in track['unit'] if not drive_hub(row['name'])]
    track['unit'] = kept[:first] + drive_rows(drive) + kept[first:]
    track['config']['revision'] = 'J9 / X1 revision F mounting stations'
    track_path.write_bytes(gzip.compress(json.dumps(track, separators=(',', ':')).encode(), mtime=0))
    data.update(module=track['unit'], link=track['link'], j9=track['config'])
    matches = [row for row in data['chassis'] if row['name'] == 'X101_X_frame']
    assert len(matches) == 1
    matches[0].update(mesh(frame))
    data['chassis'] = [row for row in data['chassis'] if not row['name'].startswith(('clamp_', 'mount_'))]
    for name, row in hardware.items():
        shape = row['shape'].val() if isinstance(row['shape'], cq.Workplane) else row['shape']
        data['chassis'].append(dict(name=name, color=list(row['color']), group='xframe',
                                    kind='hardware', source=None, **mesh(shape)))
    b = frame.BoundingBox()
    data['config']['revision'] = 'X1 revision F'
    data['config']['track_y'] = track_y
    data['config']['key'].update(x_frame_width=round(b.ylen, 1), x_frame_length=round(b.xlen, 1))
    path.write_bytes(gzip.compress(json.dumps(data, separators=(',', ':')).encode(), mtime=0))
    return [dict(file=str(p.relative_to(REPO)), sha256=sha(p)) for p in (track_path, path)]


def verify_step(path, expected, hardware, drive=None):
    """Confirm an existing assembly already holds the current parts and joint hardware (and drive-hub group)."""
    print('Verify', path.name, flush=True)
    rows = components_from_assembly(cached_assembly(path))
    expected = {**expected, **{n: _solid(row['shape']) for n, row in (drive or {}).items()}}
    stale_drive = sorted(n for n in rows if drive is not None and drive_hub(n) and n not in drive)
    drive_colours = sorted(n for n, row in (drive or {}).items()
                           if n in rows and rows[n]['color'] != color_key(cq.Color(*row['color'])))
    missing = sorted(set(expected) - set(rows))
    mismatched = sorted(n for n, shape in expected.items()
                        if n in rows and not signature_matches(signature(rows[n]['shape']), signature(shape)))
    mounts = {n for n in rows if n.startswith('mount_')}
    hardware_names_match = mounts == set(hardware)
    hardware_mismatched = sorted(n for n in mounts & set(hardware)
                                 if not signature_matches(signature(rows[n]['shape']),
                                                          signature(_solid(hardware[n]['shape']))))
    obsolete = sorted(n for n in rows if n.startswith('clamp_'))
    compound = cq.Compound.makeCompound([row['shape'] for row in rows.values()])
    ok = (not (missing or mismatched or hardware_mismatched or obsolete or stale_drive or drive_colours)
          and hardware_names_match and compound.isValid())
    return dict(file=str(path.relative_to(REPO)), sha256=sha(path), components=len(rows),
                solids=len(compound.Solids()), checked_current_parts=sorted(expected),
                missing=missing, signature_mismatches=mismatched,
                stale_drive_hub_components=stale_drive, drive_hub_colour_mismatches=drive_colours,
                mount_hardware_count=len(mounts), mount_hardware_names_match=hardware_names_match,
                mount_hardware_mismatches=hardware_mismatched, obsolete_clamp_components=obsolete,
                **{'pass': bool(ok)})


def _solid(shape):
    return shape.val() if isinstance(shape, cq.Workplane) else shape


def verify_scenes(frame, left_frame, left_housing, hardware, track_hardware, drive):
    """Confirm both offline scenes hold meshes of the current parts and hardware."""
    track_path = J9 / 'source/j9_scene.json.gz'
    path = ROOT / 'source/x1_scene.json.gz'
    track = json.loads(gzip.decompress(track_path.read_bytes()))
    data = json.loads(gzip.decompress(path.read_bytes()))
    problems = []
    for name, shape in {'J901_H_frame': left_frame, 'J909_housing': left_housing, **track_hardware}.items():
        rows = [row for row in track['unit'] if row['name'] == name]
        if len(rows) != 1 or {k: rows[0][k] for k in ('vertices', 'triangles')} != mesh(_solid(shape)):
            problems.append(f'j9_scene:{name}')
    for want in drive_rows(drive):
        rows = [row for row in track['unit'] if row['name'] == want['name']]
        if len(rows) != 1 or rows[0] != want:
            problems.append(f"j9_scene:{want['name']}")
    problems += [f"j9_scene:stale {row['name']}" for row in track['unit']
                 if drive_hub(row['name']) and row['name'] not in drive]
    if data['module'] != track['unit'] or data['link'] != track['link']:
        problems.append('x1_scene:module copy differs from j9_scene')
    expected = {'X101_X_frame': frame, **{n: row['shape'] for n, row in hardware.items()}}
    chassis = {row['name']: row for row in data['chassis']}
    for name, shape in expected.items():
        row = chassis.get(name)
        if row is None or {k: row[k] for k in ('vertices', 'triangles')} != mesh(_solid(shape)):
            problems.append(f'x1_scene:{name}')
    extra = sorted(n for n in chassis if n.startswith(('clamp_', 'mount_')) and n not in expected)
    problems += [f'x1_scene:unexpected {n}' for n in extra]
    return [dict(file=str(p.relative_to(REPO)), sha256=sha(p)) for p in (track_path, path)], problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenes-only', action='store_true')
    parser.add_argument('--preview-only', action='store_true',
                        help='Prepare scenes for browser review without claiming the complete assembly refresh is checked.')
    parser.add_argument('--warm-cache', action='store_true', help='Prepare native caches for the three current assemblies without changing CAD.')
    parser.add_argument('--verify', action='store_true',
                        help='Check that the existing assemblies and scenes already hold the current parts; writes no CAD.')
    args = parser.parse_args()
    if args.warm_cache:
        for path in (J9/'step/JGY370_track_J9.step', ROOT/'step/X1_crawler_chassis.step', ROOT/'step/X1_turntable_assembly.step'):
            cached_assembly(path)
        print('Assembly caches checked', flush=True)
        return
    import x1_parts as X
    started = time.time()
    paths = {'X101_X_frame': ROOT/'step/X101_X_frame.step',
             'J901_H_frame': J9/'step/J901_H_frame.step',
             'J909_housing': J9/'step/J909_housing.step',
             'J901_H_frame_right': ROOT/'step/J901_H_frame_right.step',
             'J909_housing_right': ROOT/'step/J909_housing_right.step',
             'J904_roller': J9/'step/J904_roller.step',
             'J906_idler_wheel': J9/'step/J906_idler_wheel.step',
             'J902_sprocket': J9/'step/J902_sprocket.step'}
    assert not (args.scenes_only and args.preview_only), 'Choose only one scene refresh mode'
    needed = ({'X101_X_frame', 'J901_H_frame', 'J909_housing', 'J904_roller', 'J906_idler_wheel', 'J902_sprocket'}
              if args.scenes_only or args.preview_only
              else set(paths))
    parts = {name: part(p) for name, p in paths.items() if name in needed}
    hardware = X.mount_hardware()
    # Refresh cosmetic housing attachments if the current geometry moved them
    # to clear the arc-support and external-fastener envelopes. Rebuild their simple hardware shapes from the same
    # source expressions used by J9.unit(), keeping their component names.
    p9 = X.P9
    track_hardware = {}
    for index in (0, 2):
        hx, hz = p9.HOUSING_SCREWS[index]
        track_hardware[f'insert_M3_{index}'] = p9.yring(
            p9.INSERT_M3['r'], 1.5, p9.RIM_Y[0], p9.RIM_Y[0]+p9.INSERT_M3['length'], hx, hz).val()
        track_hardware[f'housing_screw_M3x8_{index}'] = p9.screw_y(
            1.5, p9.M3_BUTTON, p9.SKIRT_Y[0], 8.0, hx, hz, 1).val()
    # The rollers and the idler wheel are refreshed with the hardware above: the same names in the J9 assembly and
    # scene, L_/R_ copies in X1. Each is the delivered export at its station, placed as in J9.unit().
    for x, z, station in p9.ROLLERS:
        track_hardware[f'J904_roller_{station}'] = parts['J904_roller'].translate((x, 0, z))
    track_hardware['J906_idler_wheel'] = parts['J906_idler_wheel'].translate((p9.IDLER_X, 0, p9.AXLE_Z))
    # The drive-hub group: the delivered J902 export (modelled in place, as J9.unit() adds it) and the bought hub parts
    # from the same source function J9.unit() uses. The right track of the X1 chassis carries mirrored copies.
    # The modelled hardware is STEP-normalised (see step_normalised) so that the assembly round-trip check holds.
    drive = {'J902_sprocket': dict(shape=parts['J902_sprocket'], color=p9.DARK, kind='printed', source='J902_sprocket')}
    drive.update({name: dict(shape=step_normalised(_solid(shape)), color=color, kind='hardware', source=None)
                  for name, (shape, color) in p9.drive_hub_hardware().items()})
    crawler_drive = {}
    for side, tag in ((1, 'L'), (-1, 'R')):
        for name, row in drive.items():
            shape = row['shape']
            if side < 0:
                shape = shape.mirror('XZ')
                if row['kind'] == 'hardware':
                    shape = step_normalised(shape)
            crawler_drive[tag+'_'+name] = dict(row, shape=shape.translate((0, side*X.TRACK_Y, 0)))
    if args.preview_only:
        refresh_scenes(parts['X101_X_frame'], parts['J901_H_frame'], parts['J909_housing'], hardware,
                       X.TRACK_Y, track_hardware, drive)
        print('Preview scenes prepared; complete assembly validation remains pending', flush=True)
        return
    inputs = {str(p.relative_to(REPO)): sha(p) for p in paths.values()}
    for source in (Path(__file__), Path(X.__file__), Path(p9.__file__), Path(X.M.__file__),
                   Path(X.D9.__file__), Path(p9.tp.__file__)):
        inputs[str(source.relative_to(REPO))] = sha(source)
    report_path = ROOT/'revf_refresh_validation.json'
    if args.verify:
        crawler = {'X101_X_frame': parts['X101_X_frame']}
        for side, tag in ((1, 'L'), (-1, 'R')):
            for name in ('J901_H_frame', 'J909_housing'):
                crawler[tag+'_'+name] = parts[name if side > 0 else name+'_right'].translate((0, side*X.TRACK_Y, 0))
            for name, shape in track_hardware.items():
                p = shape if side > 0 else shape.mirror('XZ')
                crawler[tag+'_'+name] = p.translate((0, side*X.TRACK_Y, 0))
        reports = [verify_step(J9/'step/JGY370_track_J9.step',
                               {**{n: parts[n] for n in ('J901_H_frame', 'J909_housing')}, **track_hardware}, {}, drive),
                   verify_step(ROOT/'step/X1_crawler_chassis.step', crawler, hardware, crawler_drive),
                   verify_step(ROOT/'step/X1_turntable_assembly.step',
                               {'X101_X_frame': parts['X101_X_frame']}, hardware)]
        scenes, problems = verify_scenes(parts['X101_X_frame'], parts['J901_H_frame'], parts['J909_housing'],
                                         hardware, track_hardware, drive)
        assert all(sha(REPO/name) == value for name, value in inputs.items()), 'Inputs changed during verification'
        ok = all(r['pass'] for r in reports) and not problems
        report = dict(revision='F', mode='verified existing assemblies and scenes; no CAD written',
                      inputs=inputs, assemblies=reports, scenes=scenes, scene_problems=problems,
                      seconds=round(time.time()-started, 1), **{'pass': bool(ok)})
        report_path.write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(dict(passed=ok, assemblies=[(r['file'], r['pass']) for r in reports],
                              scene_problems=problems), indent=1), flush=True)
        if not ok:
            raise SystemExit(1)
        return
    if args.scenes_only:
        prior = json.loads(report_path.read_text())
        assert prior['inputs'] == inputs
        reports = prior['assemblies']
        assert all(sha(REPO/row['file']) == row['sha256'] for row in reports)
    else:
        reports = [refresh_step(J9/'step/JGY370_track_J9.step',
                               {**{n: parts[n] for n in ('J901_H_frame', 'J909_housing')}, **track_hardware},
                               drive=drive)]
        replacements = {'X101_X_frame': parts['X101_X_frame']}
        for side, tag in ((1, 'L'), (-1, 'R')):
            for name in ('J901_H_frame', 'J909_housing'):
                p = parts[name if side > 0 else name+'_right']
                replacements[tag+'_'+name] = p.translate((0, side*X.TRACK_Y, 0))
            for name, shape in track_hardware.items():
                p = shape if side > 0 else shape.mirror('XZ')
                replacements[tag+'_'+name] = p.translate((0, side*X.TRACK_Y, 0))
        reports.append(refresh_step(ROOT/'step/X1_crawler_chassis.step', replacements, hardware, crawler_drive))
        reports.append(refresh_step(ROOT/'step/X1_turntable_assembly.step',
                                    {'X101_X_frame': parts['X101_X_frame']}, hardware))
    scenes = refresh_scenes(parts['X101_X_frame'], parts['J901_H_frame'], parts['J909_housing'], hardware,
                            X.TRACK_Y, track_hardware, drive)
    assert all(sha(REPO/name) == value for name, value in inputs.items())
    report = dict(revision='F', inputs=inputs, assemblies=reports, scenes=scenes,
                  seconds=round(time.time()-started, 1), **{'pass': True})
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    print('Revision F assembly and scene refresh PASS', flush=True)


if __name__ == '__main__':
    main()

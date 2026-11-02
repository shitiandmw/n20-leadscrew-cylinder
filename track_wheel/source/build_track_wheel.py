"""Export the track wheel unit: printable STEP/STL, assembly STEP, viewer scene.

Printable parts are single BREP solids. STL files are in print orientation,
centred on the bed. The left-hand rail is the mirror image of TW06.
Run: python build_track_wheel.py
"""
import gzip, json, math, time
import cadquery as cq
import trimesh
import tw_parts as tp
import tw_design as td

ROOT = tp.ROOT
PETG_KG_MM3 = 1.27e-6

# (rotation axis, degrees, bed face and supports)
PRINT = {
    'TW01_motor_housing': ((1, 0, 0), -90, 'End-wall spigot on the bed. Tree supports under the flange ring only (8.5 mm overhang); the rail face of the flange is cleaned flat after printing.'),
    'TW02_sprocket_hub': ((1, 0, 0), -90, 'Outboard face (cap side) on the bed. No supports; the 3 mm 61808 shoulder bridges.'),
    'TW03_hub_cap': ((1, 0, 0), -90, 'End plate on the bed. No supports. Ring teeth print as vertical walls; 100 % infill around the teeth.'),
    'TW04_bearing_retainer': ((1, 0, 0), 90, 'Clamp face on the bed, counterbores up. No supports.'),
    'TW05_motor_rear_cap': ((1, 0, 0), 90, 'Closed end and both ears on the bed. No supports.'),
    'TW06_track_frame': ((1, 0, 0), -90, 'Outboard face on the bed, placed diagonally on a 256 mm bed. No supports; the channel roof bridges 31 mm.'),
    'TW07_idler_yoke': ((0, 1, 0), 90, 'Front face on the bed. No supports; 4.3 mm nose overhangs.'),
    'TW08_spring_seat': ((0, 1, 0), -90, 'Seat face on the bed, spigot up. No supports.'),
    'TW09_channel_nose': ((1, 0, 0), 0, 'Flat on the bed, bolt holes vertical. No supports.'),
    '05_track_shoe': ((1, 0, 0), 0, 'Unchanged Track R4 orientation.'),
    '07_idler_wheel': ((1, 0, 0), 90, 'Unchanged Track R4 orientation.'),
    '08_road_roller': ((1, 0, 0), 90, 'Unchanged Track R4 orientation.'),
    '24_return_roller': ((1, 0, 0), 90, 'Unchanged Track R4 orientation.'),
}
MIRRORED = ['TW06_track_frame']


def mesh(shape, tol=.08, ang=.15):
    v, f = tp.one(shape).tessellate(tol, ang)
    return {'vertices': [[round(p.x, 4), round(p.y, 4), round(p.z, 4)] for p in v], 'triangles': [list(t) for t in f]}


def to_bed(s, axis, deg):
    if deg:
        s = s.rotate((0, 0, 0), axis, deg)
    b = tp.one(s).BoundingBox()
    return s.translate((-(b.xmin + b.xmax) / 2, -(b.ymin + b.ymax) / 2, -b.zmin))


def export_stl(s, path):
    cq.exporters.export(s, str(path), tolerance=.035, angularTolerance=.12)
    tm = trimesh.load_mesh(path)
    tm.update_faces(tm.nondegenerate_faces(height=1e-8)); tm.remove_unreferenced_vertices(); tm.export(path)
    assert tm.is_watertight and tm.is_winding_consistent and len(tm.split()) == 1, path
    return tm


def export_step(s, path):
    cq.exporters.export(s, str(path))
    rt = cq.importers.importStep(str(path))
    assert tp.one(rt).isValid() and len(rt.solids().vals()) == 1, path


def export_parts(parts):
    (ROOT / 'step').mkdir(exist_ok=True); (ROOT / 'stl').mkdir(exist_ok=True)
    rows = []
    for n, d in parts.items():
        s = d['shape']
        assert tp.one(s).isValid() and len(s.solids().vals()) == 1, n
        print('Export', n, flush=True)
        export_step(s, ROOT / 'step' / f'{n}.step')
        axis, deg, how = PRINT[n]
        tm = export_stl(to_bed(s, axis, deg), ROOT / 'stl' / f'{n}.stl')
        vol = tp.one(s).Volume()
        row = dict(name=n, quantity=d['quantity'], material=d['material'], note=d['note'], print_orientation=how,
                   volume_mm3=round(vol, 1), solid_mass_g=round(vol * PETG_KG_MM3 * 1000, 1),
                   print_bounds_mm=[round(v, 2) for v in tm.extents.tolist()], watertight=True, step_roundtrip=True)
        if n in MIRRORED:
            m = s.mirror('XZ')
            export_step(m, ROOT / 'step' / f'{n}_left.step')
            export_stl(to_bed(m, axis, -deg if axis == (1, 0, 0) else deg), ROOT / 'stl' / f'{n}_left.stl')
            row['mirrored'] = f'{n}_left (left-hand track)'
        rows.append(row)
    return rows


def scene_items(inst):
    items = []
    for n, d in inst.items():
        assert tp.one(d['shape']).isValid(), n
        fine = d['group'] in ['drive', 'pinion'] and n in ['TW03_hub_cap', 'hub_pinion']
        m = mesh(d['shape'], .02, .08) if fine else mesh(d['shape'])
        items.append(dict(name=n, color=list(d['color']), group=d['group'], kind=d['kind'], source=d['source'], **m))
    return items


def export_assembly(inst):
    assy = cq.Assembly(name='Track_wheel_unit_R5')
    for n, d in inst.items():
        assy.add(d['shape'], name=n, color=cq.Color(*d['color']))
    path = ROOT / 'step' / 'track_wheel_unit.step'
    assy.export(str(path))
    rt = cq.importers.importStep(str(path))
    assert tp.one(rt).isValid()
    return len(rt.solids().vals())


def parameters():
    keep = {}
    for k in dir(td):
        v = getattr(td, k)
        if k.isupper() and isinstance(v, (int, float, str, list, tuple, dict)):
            keep[k] = v
    keep['drive_rating'] = td.drive_rating()
    keep['spring_assembled'] = td.spring_state()
    keep['spring_at_recoil_stop'] = td.stop_state()
    keep['recoil_travel_mm'] = td.recoil_travel()
    keep['forward_travel_mm'] = td.forward_travel()
    keep['drive_force_limit'] = td.drive_force_limit()
    return keep


def main():
    t0 = time.time()
    parts = tp.printed_parts()
    rows = export_parts(parts)
    inst = tp.unit_instances(parts)
    print('Scene', len(inst), 'solids', flush=True)
    (ROOT / 'source' / 'track_wheel_scene.json.gz').write_bytes(
        gzip.compress(json.dumps(scene_items(inst), separators=(',', ':')).encode()))
    solids = export_assembly(inst)
    (ROOT / 'parameters.json').write_text(json.dumps(parameters(), indent=2, default=list))
    report = dict(parts=rows, assembly_solids=solids, elapsed_seconds=round(time.time() - t0, 1))
    (ROOT / 'source' / 'export_report.json').write_text(json.dumps(report, indent=2))
    print('Assembly', solids, 'solids;', report['elapsed_seconds'], 's', flush=True)


if __name__ == '__main__':
    main()

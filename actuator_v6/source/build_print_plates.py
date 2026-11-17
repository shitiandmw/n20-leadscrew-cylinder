#!/usr/bin/env python3
"""Print plates for a set of V6 actuators: the print-ready STL files laid out on build plates, ready to slice.

    python3 actuator_v6/source/build_print_plates.py [--variant U60] [--count 4] [--check]

Writes ../print_plates/V6-<variant>_x<count>/ (default V6-U60_x4: the four drives of the R12 arm):
  plate<N>_<name>.3mf   the plate: one object per part, its copies as instances of it, at their places on a 180 x 180 mm
                        bed (the layout is centred on X 90, Y 90; it fits any bed of 180 x 180 or more). Each object carries
                        its print settings for PrusaSlicer (layer height, walls, infill, brim, and the body's 0.12 mm layers
                        for its last 2 mm as a height range). Bambu Studio, OrcaSlicer and Cura load the objects at their
                        places; there, set by hand the settings that differ between the objects of a plate (listed in
                        plates.json, ../PRINT_PLATES.md and the parts showcase).
  plate<N>_<name>.stl   the same layout as one mesh (one object, so one setting for the whole plate)
  plates.json           what is on each plate, where and with which settings, and the checks below
  ../PRINT_PLATES.md    (default set only) the plates, their settings and files, for reading

The parts are the STL files of stl/V6-<variant>/ and stl/fit_samples/, as exported (already turned onto their print face):
the plates only move them, never turn them. The print settings come from the build's own record (validation.json,
print_setup, written from build_v6.PRINT_SETTINGS); SETTINGS below holds them as numbers and fails if they no longer match.

Checks (each one stops the script): the STL files are the released ones (SHA256SUMS.txt); copies are pure translations; the
footprints, brims included, keep at least GAP_MIN mm apart and stay MARGIN mm inside the 180 x 180 bed; the 3MF read back
(XML parsed again) gives exactly the placed triangles of the STL files, with every object's settings and instances; the
merged STL holds the same triangles. The outputs are deterministic (fixed zip dates), so they can be checksummed.
Standard library only.
"""
import argparse
import hashlib
import io
import json
import math
import struct
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import quoteattr

HERE = Path(__file__).resolve().parent
PKG = HERE.parent                              # actuator_v6
PETG = 1.27                                    # g/cm3, as build_v6.PETG_DENSITY
BED = (180.0, 180.0)                           # Prusa MINI, Bambu Lab A1 mini: the smallest common beds
MARGIN = 10.0                                  # mm kept free at the bed edges (skirt, purge line)
GAP_MIN = 6.0                                  # mm between two footprints, brims included
FIXED_DATE = (2026, 11, 12, 0, 0, 0)          # zip entry dates: the same plate gives the same bytes

# The print settings of each part as numbers. 'evidence' must appear in the part's print_setup text (validation.json), so a
# change in build_v6.PRINT_SETTINGS stops this script instead of leaving the plates behind. 'top' = (height, layer): the last
# 'height' mm printed at 'layer' mm. 'as' = the part whose settings a fit sample takes.
SETTINGS = {
    '01_body': dict(layer=0.2, walls=3, infill=25, pattern='gyroid', brim=5.0, top=(2.0, 0.12), supports=False,
                    evidence=['front end down', '5 mm brim', '0.2 mm layers', '3 walls', '25 % gyroid', 'no supports',
                              '0.12 mm layers for the last 2 mm']),
    '02_front_cap': dict(layer=0.16, walls=4, infill=40, pattern='gyroid', brim=0.0, supports=False,
                         evidence=['outer face down', '0.16 mm', '4 walls', '40 % gyroid', 'no supports']),
    '03_rear_cap': dict(layer=0.16, walls=4, infill=60, pattern='gyroid', brim=0.0, supports=False,
                        evidence=['flat front face down', '0.16 mm', '4 walls', '60 % gyroid', 'no supports']),
    '04_rod': dict(layer=0.16, walls=None, infill=100, pattern=None, brim=3.0, supports=False,
                   evidence=['carrier down', '0.16 mm', '100 % infill', '3 mm brim']),
    '05_rod_eye': dict(layer=0.16, walls=None, infill=100, pattern=None, brim=0.0, supports=False,
                       evidence=['socket opening down', '0.16 mm', '100 % infill', 'no supports']),
    '06_cable_clamp': dict(layer=0.16, walls=None, infill=100, pattern=None, brim=0.0, supports=False,
                           evidence=['flat back down', '0.16 mm', '100 % infill', 'no supports']),
    # The fit samples print as their parts, without the brims: those hold the 108 mm body and the 92 mm rod up, and the
    # samples are 5 to 18 mm tall. The last 2 mm at 0.12 mm matter on sample 10 (the hook's bevel); 08 and 11 take them too,
    # so that the three body samples share one setting.
    '08_fit_body_wall': dict(**{'as': '01_body'}, brim=0.0, evidence=['As 01_body', 'front end down']),
    '09_fit_carrier': dict(**{'as': '04_rod'}, brim=0.0, evidence=['As 04_rod']),
    '10_fit_insert_rear': dict(**{'as': '01_body'}, brim=0.0, evidence=['As 01_body', 'front end down', 'end of the motor-side wall on top']),
    '11_fit_insert_front': dict(**{'as': '01_body'}, brim=0.0, evidence=['As 01_body', 'front end down']),
}
FIT_SAMPLES = ['08_fit_body_wall', '09_fit_carrier', '10_fit_insert_rear', '11_fit_insert_front']
NAMES = {'01_body': 'Body', '02_front_cap': 'Front cap', '03_rear_cap': 'Rear cap', '04_rod': 'Rod and nut carrier',
         '05_rod_eye': 'Rod eye', '06_cable_clamp': 'Cable clamp', '08_fit_body_wall': 'Fit sample 08: motor bay and bore',
         '09_fit_carrier': 'Fit sample 09: carrier', '10_fit_insert_rear': 'Fit sample 10: rear end',
         '11_fit_insert_front': 'Fit sample 11: front end'}

# PrusaSlicer's support alert (slice_plates.py) names these parts: why, and why they print without supports all the same.
# A part it names that is not here stops PRINT_PLATES.md and the parts showcase until it is explained.
SUPPORT_ALERT = {                       # part: (as a sentence names it, why)
    '01_body': ('the body', 'the motor wall bridges the carrier bore 77 mm up, and the two motor-screw countersinks open into its underside, '
               'so some bridge lines end in mid-air. Print without supports all the same: they would be trapped in the bore. '
               'Fit sample 08 shows how this bridge prints.'),
    '08_fit_body_wall': ('fit sample 08', 'the same bridge as in the body, the motor wall over the bore, here 6 mm up. Checking it is what the '
                        'sample is for: the M1.6 screws must sit flush with the wall (ASSEMBLY.md step 1). No supports.'),
    '06_cable_clamp': ('the cable clamp', 'its two screw-head counterbores face the bed, so the ring around each screw hole is printed over the '
                      'counterbore. A little sag there does no harm: the screw head presses it flat. No supports.'),
}


def plates_for(count):
    """The plates for 'count' actuators: rows of (part, copies), back row first. Plate 1 is printed once, before the rest."""
    def rows(part, n, per_row):
        return [[(part, min(per_row, n - i))] for i in range(0, n, per_row)]
    return [
        dict(key='fit_test', title='Fit test (print this first)', once=True,
             purpose='The four fit samples and one rear cap: check the motor bay, the carrier in the bore, the nut and magnet seats, '
                     'the board slot, the M1 insert holes and the rear-cap hook before printing the real parts (ASSEMBLY.md step 1).',
             rows=[[('08_fit_body_wall', 1), ('10_fit_insert_rear', 1), ('11_fit_insert_front', 1)],
                   [('09_fit_carrier', 1), ('03_rear_cap', 1)]]),
        dict(key='bodies', title=f'Bodies, {count} off', purpose='The barrels: tall parts with the 1 mm partition, printed front end down.',
             rows=rows('01_body', count, 2)),
        dict(key='rods_eyes_clamps', title=f'Rods, rod eyes and cable clamps, {count} each',
             purpose='The solid (100 % infill) parts at 0.16 mm.',
             rows=[[('04_rod', count)], [('05_rod_eye', count)], [('06_cable_clamp', count)]]),
        dict(key='caps', title=f'Front and rear caps, {count} each', purpose='The end caps at 0.16 mm and 4 walls.',
             rows=[[('02_front_cap', count)], [('03_rear_cap', count)]]),
    ]


# --------------------------------------------------------------------------------------------- files
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_stl(path):
    """Binary STL: triangles as float32 vertex triples (as stored), the indexed mesh (identical vertices merged), bounds."""
    data = Path(path).read_bytes()
    n = struct.unpack_from('<I', data, 80)[0]
    assert len(data) == 84 + 50 * n, f'{path}: not a binary STL'
    tris, index, V, T = [], {}, [], []
    for rec in struct.iter_unpack('<12fH', data[84:]):
        tri = (rec[3:6], rec[6:9], rec[9:12])
        tris.append(tri)
        ids = []
        for v in tri:
            i = index.get(v)
            if i is None:
                i = index[v] = len(V)
                V.append(v)
            ids.append(i)
        T.append(ids)
    lo = [min(v[k] for v in V) for k in range(3)]
    hi = [max(v[k] for v in V) for k in range(3)]
    vol = 0.0
    for a, b, c in tris:
        vol += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6
    return dict(tris=tris, V=V, T=T, lo=lo, hi=hi, volume_mm3=vol, sha256=hashlib.sha256(data).hexdigest(), triangles=n)


def released_hashes():
    out = {}
    for line in (PKG / 'SHA256SUMS.txt').read_text().splitlines():
        h, name = line.split(None, 1)
        out[name.strip().lstrip('*')] = h
    return out


def part_file(name, variant):
    return f'stl/fit_samples/{name}.stl' if name in FIT_SAMPLES else f'stl/V6-{variant}/{name}.stl'


def resolved_settings(name):
    s = SETTINGS[name]
    if 'as' in s:
        base = {k: v for k, v in SETTINGS[s['as']].items() if k != 'evidence'}
        base.update({k: v for k, v in s.items() if k not in ('evidence', 'as')})
        base['as'] = s['as']
        return base
    return {k: v for k, v in s.items() if k != 'evidence'}


def settings_text(s):
    t = f'{s["layer"]:g} mm layers, ' + (f'{s["walls"]} walls, {s["infill"]} % {s["pattern"]}' if s['infill'] < 100 else '100 % infill')
    t += f', {s["brim"]:g} mm brim' if s['brim'] else ', no brim'
    if s.get('top'):
        t += f'; the last {s["top"][0]:g} mm at {s["top"][1]:g} mm layers'
    return t + ', no supports'


def prusa_keys(s):
    """PrusaSlicer per-object options for one part (Slic3r_PE_model.config)."""
    k = dict(layer_height=f'{s["layer"]:g}', fill_density=f'{s["infill"]}%', brim_width=f'{s["brim"]:g}', support_material='0')
    if s['infill'] < 100:
        k.update(perimeters=str(s['walls']), fill_pattern=s['pattern'])
    else:
        k.update(fill_pattern='rectilinear')          # PrusaSlicer refuses gyroid at 100 %; solid infill is rectilinear anyway
    return k


# --------------------------------------------------------------------------------------------- layout
def layout(plate, meshes):
    """Places the copies row by row (back row first), each row centred, the whole plate centred on the bed. Returns the
    instances: part, copy number, translation, footprint (part outline and brim outline, XY rectangles)."""
    rows = []
    for row in plate['rows']:
        cells = []
        for part, n in row:
            m, s = meshes[part], resolved_settings(part)
            w, d = m['hi'][0] - m['lo'][0] + 2 * s['brim'], m['hi'][1] - m['lo'][1] + 2 * s['brim']
            cells += [(part, w, d)] * n
        rows.append(cells)
    gap = 10.0
    row_w = [sum(c[1] for c in r) + gap * (len(r) - 1) for r in rows]
    row_d = [max(c[2] for c in r) for r in rows]
    total_d = sum(row_d) + gap * (len(rows) - 1)
    cx0, cy0 = BED[0] / 2, BED[1] / 2
    out, y_top, copies = [], cy0 + total_d / 2, {}
    for r, w, d in zip(rows, row_w, row_d):
        x = cx0 - w / 2
        yc = y_top - d / 2
        for part, cw, cd in r:
            m = meshes[part]
            xc = x + cw / 2
            t = (round(xc - (m['lo'][0] + m['hi'][0]) / 2, 3), round(yc - (m['lo'][1] + m['hi'][1]) / 2, 3), 0.0)
            copies[part] = copies.get(part, 0) + 1
            b = resolved_settings(part)['brim']
            body = [m['lo'][0] + t[0], m['lo'][1] + t[1], m['hi'][0] + t[0], m['hi'][1] + t[1]]
            out.append(dict(part=part, copy=copies[part], t=t, outline=[round(v, 3) for v in body],
                            footprint=[round(body[0] - b, 3), round(body[1] - b, 3), round(body[2] + b, 3), round(body[3] + b, 3)]))
            x += cw + gap
        y_top -= d + gap
    return out


def check_layout(inst):
    xs = [v for i in inst for v in (i['footprint'][0], i['footprint'][2])]
    ys = [v for i in inst for v in (i['footprint'][1], i['footprint'][3])]
    edge = min(min(xs), min(ys), BED[0] - max(xs), BED[1] - max(ys))
    assert edge >= MARGIN - 1e-9, f'footprint {edge:.1f} mm from the bed edge'
    gaps = []
    for a in range(len(inst)):
        for b in range(a + 1, len(inst)):
            A, B = inst[a]['footprint'], inst[b]['footprint']
            dx = max(0.0, max(A[0], B[0]) - min(A[2], B[2]))
            dy = max(0.0, max(A[1], B[1]) - min(A[3], B[3]))
            g = math.hypot(dx, dy)
            assert g >= GAP_MIN - 1e-9, f'{inst[a]["part"]} {inst[a]["copy"]} and {inst[b]["part"]} {inst[b]["copy"]}: {g:.2f} mm apart'
            gaps.append(g)
    return dict(footprint_mm=[round(min(xs), 2), round(min(ys), 2), round(max(xs), 2), round(max(ys), 2)],
                size_mm=[round(max(xs) - min(xs), 1), round(max(ys) - min(ys), 1)], min_edge_mm=round(edge, 2),
                min_gap_mm=round(min(gaps), 2) if gaps else None, bed_mm=list(BED), margin_mm=MARGIN, gap_min_mm=GAP_MIN)


# --------------------------------------------------------------------------------------------- 3MF and STL writers
def num(v):
    s = f'{v:.7g}'
    return '0' if s in ('-0', '0') else s


def model_xml(objects, items, title):
    """3MF core model: one mesh object per part (STL vertices merged, as stored), one build item per copy."""
    out = io.StringIO()
    w = out.write
    w('<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" '
      'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" xmlns:slic3rpe="http://schemas.slic3r.org/3mf/2017/06">\n')
    w(f' <metadata name="Title">{title}</metadata>\n <metadata name="Application">actuator_v6/source/build_print_plates.py</metadata>\n')
    w(' <metadata name="slic3rpe:Version3mf">1</metadata>\n <resources>\n')
    for o in objects:
        w(f'  <object id="{o["id"]}" type="model" name={quoteattr(o["name"])}>\n   <mesh>\n    <vertices>\n')
        for v in o['mesh']['V']:
            w(f'     <vertex x="{num(v[0])}" y="{num(v[1])}" z="{num(v[2])}"/>\n')
        w('    </vertices>\n    <triangles>\n')
        for t in o['mesh']['T']:
            w(f'     <triangle v1="{t[0]}" v2="{t[1]}" v3="{t[2]}"/>\n')
        w('    </triangles>\n   </mesh>\n  </object>\n')
    w(' </resources>\n <build>\n')
    for it in items:
        tx, ty, tz = it['t']
        w(f'  <item objectid="{it["id"]}" transform="1 0 0 0 1 0 0 0 1 {num(tx)} {num(ty)} {num(tz)}" printable="1"/>\n')
    w(' </build>\n</model>\n')
    return out.getvalue()


def prusa_config_xml(objects):
    """Metadata/Slic3r_PE_model.config: each object's name and print settings, and its single volume (all triangles)."""
    L = ['<?xml version="1.0" encoding="UTF-8"?>', '<config>']
    for o in objects:
        L.append(f' <object id="{o["id"]}" instances_count="{o["copies"]}">')
        L.append(f'  <metadata type="object" key="name" value={quoteattr(o["name"])}/>')
        for k, v in o['prusa'].items():
            L.append(f'  <metadata type="object" key="{k}" value="{v}"/>')
        L.append(f'  <volume firstid="0" lastid="{len(o["mesh"]["T"]) - 1}">')
        L.append(f'   <metadata type="volume" key="name" value={quoteattr(o["name"])}/>')
        L.append('   <metadata type="volume" key="volume_type" value="ModelPart"/>')
        L.append(f'   <metadata type="volume" key="source_file" value={quoteattr(o["file"])}/>')
        L.append('  </volume>')
        L.append(' </object>')
    L.append('</config>')
    return '\n'.join(L) + '\n'


def prusa_ranges_xml(objects):
    """Metadata/Prusa_Slicer_layer_config_ranges.xml: a layer height for a band of an object (the body's last 2 mm)."""
    L = ['<?xml version="1.0" encoding="utf-8"?>', '<objects>']
    n = 0
    for o in objects:
        if o.get('range'):
            z0, z1, h = o['range']
            L += [f' <object id="{o["id"]}">', f'  <range min_z="{num(z0)}" max_z="{num(z1)}">',
                  '   <option opt_key="extruder">0</option>', f'   <option opt_key="layer_height">{h:g}</option>', '  </range>', ' </object>']
            n += 1
    L.append('</objects>')
    return '\n'.join(L) + '\n' if n else None


CONTENT_TYPES = ('<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
                 ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
                 ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n</Types>\n')
RELS = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        ' <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
        '</Relationships>\n')


def write_zip(path, files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        for name, text in files:
            zi = zipfile.ZipInfo(name, date_time=FIXED_DATE)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            z.writestr(zi, text.encode())
    Path(path).write_bytes(buf.getvalue())


def write_stl(path, tris, name):
    head = f'V6 print plate {name}'.encode()[:80].ljust(80, b' ')
    out = [head, struct.pack('<I', len(tris))]
    for a, b, c in tris:
        u = [b[i] - a[i] for i in range(3)]
        v = [c[i] - a[i] for i in range(3)]
        n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
        L = math.sqrt(sum(x * x for x in n)) or 1.0
        out.append(struct.pack('<12fH', *(x / L for x in n), *a, *b, *c, 0))
    Path(path).write_bytes(b''.join(out))


def placed(tris, t):
    """Triangles moved by t, rounded to float32 as an STL stores them."""
    f = struct.Struct('<3f')
    return [tuple(f.unpack(f.pack(*(p[i] + t[i] for i in range(3)))) for p in tri) for tri in tris]


# --------------------------------------------------------------------------------------------- read back
def read_3mf(path):
    """Parse the written 3MF again: objects (meshes), build items, PrusaSlicer object settings and layer ranges."""
    ns = {'m': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        assert {'[Content_Types].xml', '_rels/.rels', '3D/3dmodel.model'} <= names, names
        root = ET.fromstring(z.read('3D/3dmodel.model'))
        cfg = ET.fromstring(z.read('Metadata/Slic3r_PE_model.config'))
        rng = ET.fromstring(z.read('Metadata/Prusa_Slicer_layer_config_ranges.xml')) if 'Metadata/Prusa_Slicer_layer_config_ranges.xml' in names else None
    meta = {m.get('name'): m.text for m in root.findall('m:metadata', ns)}
    objs = {}
    for o in root.find('m:resources', ns).findall('m:object', ns):
        V = [tuple(float(v.get(k)) for k in 'xyz') for v in o.find('m:mesh/m:vertices', ns)]
        T = [tuple(int(t.get(k)) for k in ('v1', 'v2', 'v3')) for t in o.find('m:mesh/m:triangles', ns)]
        objs[o.get('id')] = dict(name=o.get('name'), V=V, T=T)
    items = []
    for it in root.find('m:build', ns).findall('m:item', ns):
        m = [float(x) for x in it.get('transform').split()]
        assert m[:9] == [1, 0, 0, 0, 1, 0, 0, 0, 1], 'a copy is turned'
        items.append((it.get('objectid'), tuple(m[9:])))
    settings = {}
    for o in cfg.findall('object'):
        settings[o.get('id')] = dict(keys={m.get('key'): m.get('value') for m in o.findall('metadata')},
                                     volumes=[(int(v.get('firstid')), int(v.get('lastid'))) for v in o.findall('volume')],
                                     instances=int(o.get('instances_count')))
    ranges = {}
    if rng is not None:
        for o in rng.findall('object'):
            r = o.find('range')
            ranges[o.get('id')] = (float(r.get('min_z')), float(r.get('max_z')),
                                   float(next(x.text for x in r.findall('option') if x.get('opt_key') == 'layer_height')))
    return dict(meta=meta, objects=objs, items=items, settings=settings, ranges=ranges)


def tri_key(tri, nd=4):
    return tuple(tuple(round(c, nd) for c in p) for p in tri)


def check_3mf(path, expected, objects):
    """The 3MF read back holds, for each copy, exactly the placed triangles of its STL file (to 1e-4 mm), in the same order
    and winding; each object has its settings, one volume over all its triangles, and its instance count."""
    r = read_3mf(path)
    assert r['meta'].get('slic3rpe:Version3mf') == '1'
    got = []
    for oid, t in r['items']:
        o = r['objects'][oid]
        got += [tuple(tuple(o['V'][i][k] + t[k] for k in range(3)) for i in tri) for tri in o['T']]
    assert len(got) == len(expected), (len(got), len(expected))
    worst = max(abs(a - b) for g, e in zip(got, expected) for p, q in zip(g, e) for a, b in zip(p, q))
    assert worst < 1e-4, f'{path.name}: read back differs by {worst} mm'
    for o in objects:
        s = r['settings'][str(o['id'])]
        assert s['keys'] == dict(name=o['name'], **o['prusa']), (o['name'], s['keys'])
        assert s['volumes'] == [(0, len(o['mesh']['T']) - 1)] and s['instances'] == o['copies']
        assert sum(1 for oid, _ in r['items'] if oid == str(o['id'])) == o['copies']
        if o.get('range'):
            assert r['ranges'][str(o['id'])] == tuple(float(num(x)) for x in o['range'][:2]) + (o['range'][2],), r['ranges']
        else:
            assert str(o['id']) not in r['ranges']
    return dict(triangles=len(got), max_deviation_mm=worst, objects=len(r['objects']), instances=len(r['items']),
                prusaslicer_settings_objects=len(r['settings']), layer_ranges=len(r['ranges']))


# --------------------------------------------------------------------------------------------- main
# --------------------------------------------------------------------------------------------- the slicer's record, the guide
WORDS = {2: 'two', 3: 'three', 4: 'four', 5: 'five', 6: 'six'}


def hours(s):
    h, m = divmod(round(s / 60), 60)
    return f'{h} h {m:02d} min' if h else f'{m} min'


def slicer_for(report, plate_dir):
    """slice_plates.py's record, and its entry for each plate whose 3MF is the file it sliced (SHA-256)."""
    f = Path(plate_dir) / 'slicer_estimate.json'
    if not f.exists():
        return None, {}
    est = json.loads(f.read_text())
    by = {e['n']: e for e in est['plates']}
    return est, {p['n']: by[p['n']] for p in report['plates'] if p['n'] in by and by[p['n']]['sha256_3mf'] == p['sha256']['3mf']}


def alerts(e):
    """[(part, issues)] of PrusaSlicer's support alert for one plate; every part it names must be in SUPPORT_ALERT."""
    out = []
    for w in e['warnings']:
        assert w[0] == 'Detected print stability issues:' and w[-1] == 'Consider enabling supports.', f'unknown warning {w}'
        body = w[1:-1]
        assert len(body) % 2 == 0, w
        for part, issues in zip(body[::2], body[1::2]):
            assert part in SUPPORT_ALERT, f'PrusaSlicer names {part} ({issues}): explain it in SUPPORT_ALERT'
            out.append((part, issues))
    return out


def write_guide(report, out_dir, path):
    """PRINT_PLATES.md: the plates, their settings and files, and what the slicer said, for reading."""
    est, sl = slicer_for(report, out_dir)
    v, n, folder = report['variant'], report['actuators'], Path(out_dir).name
    every = len(sl) == len(report['plates'])
    head = ['# Print plates: four V6-U60' if (v, n) == ('V6-U60', 4) else f'# Print plates: {v} × {n}', '',
            f'The printed parts of {WORDS.get(n, n)} {v} drives, laid out on {WORDS.get(len(report["plates"]), len(report["plates"]))} '
            f'plates for a {report["bed_mm"][0]:g} × '
            f'{report["bed_mm"][1]:g} mm bed (Prusa MINI, Bambu Lab A1 mini, or anything larger). The files are in `{folder}/`, '
            'and `../parts_showcase.html` shows each plate and part in 3D.', '',
            'Print plate 1 first and check its fits (`ASSEMBLY.md` step 1) before printing the rest. PETG, 1.75 mm; no supports '
            'on any plate.', '',
            '| Plate | What | Pieces | Height | PETG | Time |', '|---|---|---:|---:|---:|---:|']
    for p in report['plates']:
        e = sl.get(p['n'])
        head.append(f'| {p["n"]} | {p["title"]} | {p["pieces"]} | {p["height_mm"]:g} mm | '
                    + (f'{e["filament_g"]:.1f} g | {hours(e["time_normal_s"])} |' if e else '– | – |'))
    if every:
        head.append(f'| | All plates | {sum(p["pieces"] for p in report["plates"])} | | '
                    f'{sum(e["filament_g"] for e in sl.values()):.0f} g | {hours(sum(e["time_normal_s"] for e in sl.values()))} |')
    head.append('')
    if sl:
        head += [f'Filament and times are the estimates of {est["slicer"]} (`{folder}/slicer_estimate.json`, written by '
                 '`source/slice_plates.py`), skirt and brims included, with a generic 0.4 mm nozzle at its default speeds: '
                 'your printer\'s profile gives its own times.', '']
    else:
        head += ['Not sliced yet: run `source/slice_plates.py` for filament and time.', '']
    head += ['## The files', '',
             '- `plate<N>_<name>.3mf`, for PrusaSlicer: every part is an object with its own settings (layer height, walls, '
             'infill, brim, and the body\'s 0.12 mm layers for its last 2 mm as a height range); copies are instances of it. '
             'Open it, pick your printer and filament, and slice.',
             '- Bambu Studio, OrcaSlicer and Cura load the same 3MF with every part in place, but not the settings: set the '
             'settings of each part by hand, as listed below.',
             '- `plate<N>_<name>.stl`: the whole plate as one mesh, with one setting for everything on it. Enough for plate 2; on '
             'the other plates the parts differ, so prefer the 3MF.',
             '- `plates.json`: what is on each plate, where and with which settings, and the checks that were run.', '']
    for p in report['plates']:
        e = sl.get(p['n'])
        head += [f'## Plate {p["n"]}: {p["title"]}', '',
                 f'`{Path(p["files"]["3mf"]).name}` (and `.stl`): {p["pieces"]} pieces, {p["layout"]["size_mm"][0]:g} × '
                 f'{p["layout"]["size_mm"][1]:g} mm on the bed, brims included; {p["height_mm"]:g} mm tall.', '', p['purpose'], '',
                 '| Part | Copies | Settings |', '|---|---:|---|']
        head += [f'| {NAMES.get(o["name"], o["name"])} (`{o["name"]}`) | {o["copies"]} | {o["settings"]} |' for o in p['objects']]
        head.append('')
        notes = []
        if p['once'] and any(o['name'] == '03_rear_cap' for o in p['objects']):
            notes.append('The rear cap is for the hook test on sample 10; afterwards it is a spare.')
        if any(o['name'] == '04_rod' for o in p['objects']):
            notes.append('`BOM.md` asks to slow the last 20 mm of the U60 rods, so that their thin tops can cool. With four rods '
                         'on the plate each of those layers already takes about four times as long; slow down if you print a rod '
                         'on its own.')
        if e:
            notes.append(f'{est["slicer"]}: {e["filament_g"]:.1f} g, about {hours(e["time_normal_s"])}.'
                         + ''.join(f' Its support alert names {SUPPORT_ALERT[part][0]} ({issues.lower()}): '
                                   f'{SUPPORT_ALERT[part][1]}' for part, issues in alerts(e)))
        head += [x for nt in notes for x in (nt, '')]
    Path(path).write_text('\n'.join(head).rstrip('\n') + '\n')


def build(variant='U60', count=4, check_only=False):
    out_dir = PKG / 'print_plates' / f'V6-{variant}_x{count}'
    val = json.loads((PKG / 'validation.json').read_text())
    released = released_hashes()
    setup = dict(val[variant]['parts'])
    setup.update({k: v for k, v in val['S']['parts'].items() if k in FIT_SAMPLES})   # fit samples: cut once, serve every length
    for name, s in SETTINGS.items():
        text = setup[name]['print_setup']
        missing = [e for e in s['evidence'] if e not in text]
        assert not missing, f'{name}: print settings changed (not found: {missing}) in "{text}": update SETTINGS'
    plates = plates_for(count)
    used = sorted({p for pl in plates for row in pl['rows'] for p, _ in row})
    meshes, files = {}, {}
    for name in used:
        rel = part_file(name, variant)
        m = read_stl(PKG / rel)
        assert released.get(rel) == m['sha256'], f'{rel} is not the released file (SHA256SUMS.txt)'
        assert abs(m['lo'][2]) < 1e-4, f'{rel} does not stand on Z 0'
        meshes[name] = m
        files[name] = dict(stl=rel, sha256=m['sha256'], size_mm=[round(m['hi'][k] - m['lo'][k], 2) for k in range(3)],
                           volume_mm3=round(m['volume_mm3'], 1), mass_solid_g=round(m['volume_mm3'] / 1000 * PETG, 2),
                           triangles=m['triangles'], print_setup=setup[name]['print_setup'])
        assert abs(m['volume_mm3'] - setup[name]['volume_mm3']) < 0.01 * setup[name]['volume_mm3'], (name, m['volume_mm3'])
    report = dict(generator='actuator_v6/source/build_print_plates.py', variant=f'V6-{variant}', actuators=count, bed_mm=list(BED),
                  # (not SHA256SUMS.txt, which lists this file: the released part files it was checked against are in 'parts')
                  inputs_sha256={str(p.relative_to(PKG)): sha(p) for p in (PKG / 'validation.json', Path(__file__))},
                  parts=files, plates=[])
    for n, pl in enumerate(plates, 1):
        inst = layout(pl, meshes)
        lay = check_layout(inst)
        order = []
        for i in inst:
            if i['part'] not in order:
                order.append(i['part'])
        objects = []
        for oid, part in enumerate(order, 1):
            s = resolved_settings(part)
            top = s.get('top')
            h = meshes[part]['hi'][2]
            objects.append(dict(id=oid, name=part, file=files[part]['stl'], mesh=meshes[part], prusa=prusa_keys(s),
                                copies=sum(1 for i in inst if i['part'] == part),
                                range=(round(h - top[0], 3), round(h, 3), top[1]) if top else None, settings=s))
        oid_of = {o['name']: o['id'] for o in objects}
        items = [dict(id=oid_of[i['part']], t=i['t']) for i in inst]
        expected = []
        for i in inst:
            expected += placed(meshes[i['part']]['tris'], i['t'])
        stem = f'plate{n}_{pl["key"]}' + ('' if pl.get('once') else f'_x{count}')
        title = f'V6-{variant} x{count}, plate {n}: {pl["title"]}'
        f3, fs = out_dir / f'{stem}.3mf', out_dir / f'{stem}.stl'
        if not check_only:
            out_dir.mkdir(parents=True, exist_ok=True)
            files_3mf = [('[Content_Types].xml', CONTENT_TYPES), ('_rels/.rels', RELS), ('3D/3dmodel.model', model_xml(objects, items, title)),
                         ('Metadata/Slic3r_PE_model.config', prusa_config_xml(objects))]
            rx = prusa_ranges_xml(objects)
            if rx:
                files_3mf.append(('Metadata/Prusa_Slicer_layer_config_ranges.xml', rx))
            write_zip(f3, files_3mf)
            write_stl(fs, expected, stem)
        rb = check_3mf(f3, expected, objects)
        st = read_stl(fs)
        assert [tri_key(t) for t in st['tris']] == [tri_key(t) for t in expected], f'{fs.name}: triangles differ'
        groups = {}
        for o in objects:
            groups.setdefault(settings_text(o['settings']), []).append(o['name'])
        mass = sum(files[i['part']]['mass_solid_g'] for i in inst)
        report['plates'].append(dict(
            n=n, key=pl['key'], title=pl['title'], purpose=pl['purpose'], once=bool(pl.get('once')),
            files={'3mf': str(f3.relative_to(PKG)), 'stl': str(fs.relative_to(PKG))},
            sha256={'3mf': sha(f3), 'stl': sha(fs)}, size_bytes={'3mf': f3.stat().st_size, 'stl': fs.stat().st_size},
            objects=[dict(name=o['name'], file=o['file'], copies=o['copies'], settings=settings_text(o['settings']),
                          settings_as=o['settings'].get('as'), prusaslicer=o['prusa'],
                          layer_range=dict(min_z=o['range'][0], max_z=o['range'][1], layer_height=o['range'][2]) if o['range'] else None)
                     for o in objects],
            same_settings=len(groups) == 1, settings_groups=[dict(settings=k, parts=v) for k, v in groups.items()],
            instances=[dict(part=i['part'], copy=i['copy'], translate_mm=list(i['t']), outline_mm=i['outline'], footprint_mm=i['footprint'])
                       for i in inst],
            pieces=len(inst), height_mm=round(max(meshes[i['part']]['hi'][2] for i in inst), 2), mass_solid_g=round(mass, 1),
            layout=lay, read_back=rb, stl_same_triangles=True))
        print(f'plate {n} {stem}: {len(inst)} pieces, {len(objects)} objects, footprint {lay["size_mm"][0]} x {lay["size_mm"][1]} mm, '
              f'{lay["min_edge_mm"]} mm to the bed edge, gaps >= {lay["min_gap_mm"]} mm, {mass:.1f} g solid'
              + ('' if len(groups) == 1 else f'; {len(groups)} setting groups'))
    # every part of 'count' actuators is on the plates once (plus the fit test's rear cap)
    want = {p: count for p in ('01_body', '02_front_cap', '03_rear_cap', '04_rod', '05_rod_eye', '06_cable_clamp')}
    got = {}
    for pl in report['plates']:
        if pl['once']:
            continue
        for i in pl['instances']:
            got[i['part']] = got.get(i['part'], 0) + 1
    assert got == want, (got, want)
    report['pass'] = True
    if check_only:
        print('checked the existing plates (nothing written)')
        return report
    (out_dir / 'plates.json').write_text(json.dumps(report, indent=1, ensure_ascii=False) + '\n')
    if (variant, count) == ('U60', 4):                 # the R12 arm's set
        write_guide(report, out_dir, out_dir.parent / 'PRINT_PLATES.md')
    return report


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--variant', default='U60')
    ap.add_argument('--count', type=int, default=4)
    ap.add_argument('--check', action='store_true', help='check the existing files only')
    a = ap.parse_args()
    build(a.variant, a.count, a.check)

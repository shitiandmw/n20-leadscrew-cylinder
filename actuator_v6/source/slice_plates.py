#!/usr/bin/env python3
"""Slice the print plates in PrusaSlicer and record what it reports: filament, print time, layers and warnings.

    python3 actuator_v6/source/slice_plates.py [--dir print_plates/V6-U60_x4] [--image local/prusaslicer:trixie] [--keep DIR]

Writes ../print_plates/V6-U60_x4/slicer_estimate.json, which build_print_plates.py (PRINT_PLATES.md) and build_parts_showcase.py
show next to each plate, but only while its 3MF is the file that was sliced (SHA-256).

The plates are sliced as their 3MF files stand, so each object keeps its own settings (layer height, walls, infill, brim, the
body's 0.12 mm top layers), on a generic setup: PROFILE below, a 0.4 mm nozzle on a 180 x 180 bed with PrusaSlicer's default
speeds. The times are for comparing the plates and planning; your printer's profile gives its own. The G-code is not kept
(--keep DIR keeps it): slice the 3MF for your printer.

PrusaSlicer runs in Docker; the image is the Debian package of PrusaSlicer, built once with
    FROM debian:trixie-slim
    RUN apt-get update && apt-get install -y --no-install-recommends prusa-slicer xvfb xauth ca-certificates
Standard library only.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent                                    # actuator_v6
TIMEOUT = 1800                                       # s per plate (a plate takes 0.5 to 5 min on a busy machine)

PROFILE = {                                          # what the objects' own settings do not set
    'bed_shape': '0x0,180x0,180x180,0x180', 'max_print_height': '180', 'nozzle_diameter': '0.4',
    'filament_diameter': '1.75', 'filament_density': '1.27', 'filament_type': 'PETG',
    'temperature': '240', 'first_layer_temperature': '240', 'bed_temperature': '80', 'first_layer_bed_temperature': '80',
    'first_layer_height': '0.2', 'layer_height': '0.2', 'perimeters': '3', 'fill_density': '25%', 'fill_pattern': 'gyroid',
    'gcode_flavor': 'marlin2', 'gcode_label_objects': 'firmware', 'gcode_comments': '0', 'skirts': '1', 'skirt_distance': '3',
}
SUMMARY = {'filament_mm': r'; filament used \[mm\] = ([\d.]+)', 'filament_cm3': r'; filament used \[cm3\] = ([\d.]+)',
           'filament_g': r'; filament used \[g\] = ([\d.]+)', 'time_normal': r'; estimated printing time \(normal mode\) = (.+)',
           'time_first_layer': r'; estimated first layer printing time \(normal mode\) = (.+)'}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def seconds(t):
    """'10h 53m 1s' -> 39181"""
    return sum(int(n) * {'d': 86400, 'h': 3600, 'm': 60, 's': 1}[u] for n, u in re.findall(r'(\d+)([dhms])', t))


def read_gcode(path):
    text = Path(path).read_text(errors='replace')
    out = {}
    for k, rx in SUMMARY.items():
        m = re.search(rx, text)
        assert m, f'{path}: no "{k}" in the G-code'
        out[k] = float(m.group(1)) if k.startswith('filament') else m.group(1).strip()
    out['time_normal_s'] = seconds(out['time_normal'])
    z = sorted({round(float(v), 3) for v in re.findall(r'^;Z:([\d.]+)', text, re.M)})
    out['layers'] = len(z)
    out['top_z'] = z[-1] if z else None
    # objects as the G-code labels them (M486 A<name>, one S<index> per instance), and the layer steps printed
    # (copies of an object are labelled "<name> (Instance <k>)")
    out['objects'] = sorted({re.sub(r' \(Instance \d+\)$', '', n.strip().strip('"')) for n in re.findall(r'^M486 A(.+)$', text, re.M)})
    out['instances'] = len(set(re.findall(r'^M486 S(\d+)\s*$', text, re.M)))
    out['layer_steps_mm'] = sorted({round(b - a, 3) for a, b in zip(z, z[1:])})
    return out


def slicer_version(image):
    r = subprocess.run(['docker', 'run', '--rm', image, 'prusa-slicer', '--help'], capture_output=True, text=True)
    m = re.search(r'PrusaSlicer-([\w.+-]+)', r.stdout + r.stderr)
    assert m, 'PrusaSlicer did not run: ' + (r.stderr or r.stdout)[-400:]
    return m.group(1).replace('+UNKNOWN', '')          # the Debian build carries no commit id


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--dir', default='print_plates/V6-U60_x4', help='plate folder, relative to actuator_v6')
    ap.add_argument('--image', default='local/prusaslicer:trixie')
    ap.add_argument('--keep', help='keep the G-code in this folder')
    a = ap.parse_args()
    plate_dir = (PKG / a.dir).resolve()
    meta = json.loads((plate_dir / 'plates.json').read_text())
    version = slicer_version(a.image)
    work = Path(tempfile.mkdtemp(prefix='v6slice_'))
    (work / 'profile.ini').write_text(''.join(f'{k} = {v}\n' for k, v in PROFILE.items()))
    plates = []
    try:
        for p in meta['plates']:
            f3 = PKG / p['files']['3mf']
            h = sha(f3)
            assert h == p['sha256']['3mf'], f'{f3.name}: not the file plates.json lists'
            gname = f3.stem + '.gcode'
            # --init: xvfb-run waits for Xvfb's ready signal, which never arrives when it runs as the container's PID 1
            name = f'v6slice-{os.getpid()}-{p["n"]}'
            cmd = ['docker', 'run', '--rm', '--init', '--name', name, '--user', f'{os.getuid()}:{os.getgid()}', '-e', 'HOME=/out',
                   '-v', f'{plate_dir}:/in:ro', '-v', f'{work}:/out', a.image, 'xvfb-run', '-a', 'prusa-slicer',
                   '--export-gcode', '--load', '/out/profile.ini', '--output', f'/out/{gname}', f'/in/{f3.name}']
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
            except subprocess.TimeoutExpired:
                subprocess.run(['docker', 'kill', name], capture_output=True)
                raise SystemExit(f'{f3.name}: PrusaSlicer still running after {TIMEOUT} s; stopped')
            log = r.stdout + r.stderr
            assert r.returncode == 0 and (work / gname).exists(), f'{f3.name}: PrusaSlicer failed\n{log[-1500:]}'
            g = read_gcode(work / gname)
            # PrusaSlicer's warnings, line by line (e.g. its support alert: the issue, then the objects it found it on)
            warn = [[ln.strip() for ln in w.splitlines() if ln.strip()]
                    for w in re.findall(r'print warning: (.*?)(?=\n\d+ => |\Z)', log, re.S)]
            names = {o['name'] for o in p['objects']}
            assert set(g['objects']) == names, f'{f3.name}: G-code objects {g["objects"]}, plate {sorted(names)}'
            assert g['instances'] == len(p['instances']), f'{f3.name}: {g["instances"]} instances in the G-code, plate {len(p["instances"])}'
            # the last layer ends within a layer of the top: PrusaSlicer adds a layer to reach it, or drops a remainder thinner
            # than its minimum layer height (0.12 mm layers do not divide the body's last 2 mm evenly)
            assert abs(g['top_z'] - p['height_mm']) < 0.2, f'{f3.name}: top layer at {g["top_z"]}, plate {p["height_mm"]}'
            plates.append(dict(n=p['n'], file=p['files']['3mf'], sha256_3mf=h, filament_g=g['filament_g'],
                               filament_m=round(g['filament_mm'] / 1000, 2), filament_cm3=g['filament_cm3'],
                               time_normal=g['time_normal'], time_normal_s=g['time_normal_s'],
                               time_first_layer=g['time_first_layer'], layers=g['layers'], top_z=g['top_z'],
                               layer_steps_mm=g['layer_steps_mm'], objects=g['objects'], instances=g['instances'],
                               warnings=warn))
            print(f'plate {p["n"]}: {g["filament_g"]} g, {g["time_normal"]}, {g["layers"]} layers, steps {g["layer_steps_mm"]}'
                  + ''.join(f'\n  warning: {" / ".join(w)}' for w in warn))
            if a.keep:
                Path(a.keep).mkdir(parents=True, exist_ok=True)
                shutil.copy(work / gname, Path(a.keep) / gname)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    out = dict(generator='actuator_v6/source/slice_plates.py', slicer=f'PrusaSlicer {version}', image=a.image,
               profile=PROFILE, note='Generic setup: a 0.4 mm nozzle with PrusaSlicer default speeds. Each object prints with '
               'its own settings from the 3MF. The times are for comparing plates; your printer profile gives its own.',
               plates=plates, total=dict(filament_g=round(sum(p['filament_g'] for p in plates), 1),
                                         time_normal_s=sum(p['time_normal_s'] for p in plates)))
    (plate_dir / 'slicer_estimate.json').write_text(json.dumps(out, indent=1, ensure_ascii=False) + '\n')
    print('wrote', (plate_dir / 'slicer_estimate.json').relative_to(PKG))


if __name__ == '__main__':
    sys.exit(main())

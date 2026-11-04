"""Encode the rendered frames (render_r12.cjs frames ...) into ../images/motion_simulation_r12.mp4 with
one chapter per dig phase, then decode it again and check the frame count, size, rate and chapters.
Writes ../video_validation.json."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]


def sha256(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--frames', type=Path, default=Path('/tmp/r12-frames'))
    args = ap.parse_args()
    chunks = sorted((json.loads(p.read_text()) for p in args.frames.glob('render_*.json')), key=lambda c: c['from'])
    assert chunks, 'no rendered chunks'
    end = 0
    for c in chunks:
        assert c['from'] == end and not c['errors'] and not c['network'], c['from']
        assert all(c[k] == chunks[0][k] for k in ('fps', 'total', 'width', 'height', 'html_sha256', 'simulation', 'playback_speed'))
        end = c['to']
    r = chunks[0]
    assert end == r['total'], (end, r['total'])
    names = {p.name for p in args.frames.glob('frame_*.jpg')}
    assert names == {f'frame_{n:05d}.jpg' for n in range(end)}, 'missing or extra frames'
    html = ROOT / '3D_preview.html'
    review = json.loads((ROOT / 'browser_validation.json').read_text())
    assert review['status'] == 'PASS' and review['html_sha256'] == r['html_sha256'] == sha256(html), 'viewer changed after review/render'
    sp = r['playback_speed']
    meta = ';FFMETADATA1\ntitle=R12 excavator arm - 150 g dig cycle, MuJoCo, 20x\n'
    for p in r['phases']:
        meta += (f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={round(p['start'] / sp * 1000)}\nEND={round(p['end'] / sp * 1000)}\n"
                 f"title={p['id'] + 1}. {p['title']}\n")
    chap = args.frames / 'chapters.ffmeta'
    chap.write_text(meta)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    target = ROOT / 'images' / 'motion_simulation_r12.mp4'
    subprocess.run([ff, '-hide_banner', '-loglevel', 'warning', '-y', '-framerate', str(r['fps']), '-i', str(args.frames / 'frame_%05d.jpg'),
                    '-i', str(chap), '-map', '0:v:0', '-map_metadata', '1', '-map_chapters', '1', '-c:v', 'libx264', '-preset', 'medium',
                    '-crf', '20', '-pix_fmt', 'yuv420p', '-an', '-movflags', '+faststart', str(target)], check=True)
    dec = subprocess.run([ff, '-hide_banner', '-v', 'error', '-nostats', '-progress', 'pipe:1', '-i', str(target), '-map', '0:v:0', '-f', 'null', '-'],
                         check=True, capture_output=True, text=True)
    assert not dec.stderr.strip(), dec.stderr
    vals = dict(line.split('=', 1) for line in dec.stdout.splitlines() if '=' in line)
    assert int(vals['frame']) == end
    rd = imageio_ffmpeg.read_frames(str(target))
    info = next(rd)
    rd.close()
    assert list(info['size']) == [r['width'], r['height']] and abs(info['fps'] - r['fps']) < 0.01
    chapters = subprocess.run([ff, '-hide_banner', '-v', 'error', '-i', str(target), '-f', 'ffmetadata', '-'], check=True,
                              capture_output=True, text=True).stdout
    assert chapters.count('[CHAPTER]') == len(r['phases'])
    res = dict(status='PASS', file=str(target.relative_to(ROOT)), scope='150 g dig cycle, MuJoCo trace replayed in 3D_preview.html at 20x',
               duration_s=info['duration'], simulated_s=r['duration'], resolution=list(info['size']), fps=info['fps'],
               frames_decoded=int(vals['frame']), chapters=len(r['phases']), audio=False, size_mb=round(target.stat().st_size / 1e6, 2),
               html_sha256=r['html_sha256'], mp4_sha256=sha256(target))
    (ROOT / 'video_validation.json').write_text(json.dumps(res, indent=1) + '\n')
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()

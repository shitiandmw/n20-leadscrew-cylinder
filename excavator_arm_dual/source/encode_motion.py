"""Encode the reviewed offline motion study and verify the complete MP4."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--frames', type=Path, default=Path('/tmp/r10-frames'))
    args = parser.parse_args()
    chunks = sorted((json.loads(p.read_text()) for p in args.frames.glob('render_*.json')), key=lambda c: c['from'])
    assert chunks, 'No complete rendering chunks'
    end = 0
    for chunk in chunks:
        assert chunk['from'] == end and not chunk['errors'] and not chunk['network']
        assert all(chunk[k] == chunks[0][k] for k in ['fps', 'total', 'width', 'height', 'duration', 'phases', 'html_sha256', 'simulation', 'playback_speed'])
        end = chunk['to']
    render = chunks[0]
    assert render['simulation'] == 'payload_150g' and render['playback_speed'] == 20
    assert end == render['total']
    names = {p.name for p in args.frames.glob('frame_*.jpg')}
    assert names == {f'frame_{n:05d}.jpg' for n in range(end)}, 'Missing or extra frames'
    review = json.loads((ROOT / 'browser_validation.json').read_text())
    digest = sha256(ROOT / '3D_preview.html')
    assert review['status'] == 'PASS' and review['html_sha256'] == render['html_sha256'] == digest
    path_check = json.loads((ROOT / 'path_validation.json').read_text())
    assert path_check['status'] == 'PASS' and path_check['motion_sha256'] == sha256(ROOT / 'motion.json')
    metadata = ';FFMETADATA1\ntitle=R10 双推杆回旋镖形大臂 — 150 g 带载动力学仿真\n'
    for phase in render['phases']:
        metadata += f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={phase['start'] * 1000}\nEND={phase['end'] * 1000}\ntitle={phase['title']}\n"
    chapter_file = args.frames / 'chapters.ffmeta'
    chapter_file.write_text(metadata)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    target = ROOT / 'images/motion_simulation_r10.mp4'
    subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'warning', '-y', '-framerate', str(render['fps']), '-i', str(args.frames / 'frame_%05d.jpg'), '-i', str(chapter_file), '-map', '0:v:0', '-map_metadata', '1', '-map_chapters', '1', '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p', '-an', '-movflags', '+faststart', str(target)], check=True)
    decoded = subprocess.run([ffmpeg, '-hide_banner', '-v', 'error', '-nostats', '-progress', 'pipe:1', '-i', str(target), '-map', '0:v:0', '-f', 'null', '-'], check=True, capture_output=True, text=True)
    assert not decoded.stderr.strip()
    values = dict(line.split('=', 1) for line in decoded.stdout.splitlines() if '=' in line)
    assert int(values['frame']) == end
    frames = imageio_ffmpeg.read_frames(str(target))
    info = next(frames)
    frames.close()
    assert list(info['size']) == [render['width'], render['height']]
    assert abs(info['duration'] - render['duration']) < .1 and abs(info['fps'] - render['fps']) < .01
    chapters = subprocess.run([ffmpeg, '-hide_banner', '-v', 'error', '-i', str(target), '-f', 'ffmetadata', '-'], check=True, capture_output=True, text=True).stdout
    assert chapters.count('[CHAPTER]') == len(render['phases'])
    assert all('title=' + phase['title'] in chapters for phase in render['phases'])
    result = dict(status='PASS', scope='R10 integrated rigid-body 150 g loaded cycle; four independent slides, 100 N each; 20x playback of 1080 seconds', file=str(target.relative_to(ROOT.parent)), duration_seconds=info['duration'], resolution=list(info['size']), fps=info['fps'], frames_decoded=int(values['frame']), chapters=len(render['phases']), audio=False, html_sha256=digest, motion_sha256=sha256(ROOT / 'motion.json'), sha256=sha256(target), bytes=target.stat().st_size, full_decode_errors=[])
    (ROOT / 'video_validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

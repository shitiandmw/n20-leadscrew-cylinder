"""Make a labeled operation sheet from the existing R5 CAD section images."""
from pathlib import Path
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / 'output/track_wheel_r5'
OUT.mkdir(parents=True, exist_ok=True)
BG, INK, MUTED, GOLD = '#f4f5f1', '#203038', '#53636a', '#b68012'
im = Image.new('RGB', (1920, 1120), BG)
d = ImageDraw.Draw(im)


def font(size, bold=False):
    return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans' + ('-Bold' if bold else '') + '.ttf', size)


def txt(x, y, text, size=24, color=INK, bold=False):
    d.text((x, y), text, font=font(size, bold), fill=color)


def para(x, y, text, width=38, size=23, color=MUTED):
    for line in textwrap.wrap(text, width):
        txt(x, y, line, size, color)
        y += size + 10
    return y


def arrow(x0, y0, x1, y1, color=GOLD):
    import math
    d.line((x0, y0, x1, y1), fill=color, width=5)
    a = math.atan2(y1-y0, x1-x0)
    d.polygon([(x1,y1), (x1-16*math.cos(a-.45),y1-16*math.sin(a-.45)),
               (x1-16*math.cos(a+.45),y1-16*math.sin(a+.45))], fill=color)


txt(50, 36, 'INDEPENDENT TRACK WHEEL', 18, MUTED, True)
txt(50, 74, 'R5 · How it works', 49, INK, True)
txt(50, 143, 'Latest workspace design: 31 October 2026  |  CAD sections + recorded MuJoCo simulation', 23, MUTED)
txt(50, 205, 'POWER FLOW', 18, GOLD, True)
boxes = [
    ('12 V motor', 'Electrical input'),
    ('150:1 gearbox', 'Inside fixed housing'),
    ('12T steel pinion', 'Offset output shaft'),
    ('21T internal ring', '1.75:1 hub reduction'),
    ('Sprocket + chain', 'Forward or reverse'),
]
for i, (title, sub) in enumerate(boxes):
    x = 50 + 372*i
    d.rounded_rectangle((x, 245, x+332, 342), 16, fill='#ffffff', outline='#d5dcd5', width=2)
    txt(x+18, 262, title, 25, INK, True)
    txt(x+18, 302, sub, 20, MUTED)
    if i < 4: arrow(x+340, 293, x+364, 293)

panels = [
    ('01  Complete unit', 'unit.png', (240,260,980,650),
     'Rear sprocket drives the track.',
     'The opposite idler and five passive rollers guide 34 linked shoes. Hub bearings carry the track loads into the fixed frame.'),
    ('02  Final drive', 'gear_stage.png', (215,40,1040,780),
     'The small pinion turns the ring.',
     'The ring is part of the hub cap, so the hub and sprocket turn with it. Nominal total reduction is 150 × 1.75 = 262.5:1.'),
    ('03  Recoil idler', 'recoil_section.png', (120,185,885,665),
     'The spring keeps the chain tight.',
     'An M6 adjuster sets preload. Debris pushes the yoke back and compresses the spring. A hard stop limits recoil to 4.0 mm.'),
]
for i, (title, file, crop, lead, body) in enumerate(panels):
    x = 50 + 620*i
    d.rounded_rectangle((x, 388, x+580, 1014), 18, fill='#ffffff', outline='#d5dcd5', width=2)
    txt(x+22, 409, title, 29, INK, True)
    picture = Image.open(ROOT/'images'/file).convert('RGB').crop(crop)
    picture = ImageOps.contain(picture, (536, 370), Image.Resampling.LANCZOS)
    im.paste(picture, (x+22+(536-picture.width)//2, 466+(370-picture.height)//2))
    txt(x+22, 853, lead, 22, INK, True)
    para(x+22, 895, body, width=43, size=21)

txt(50, 1051, 'Recorded debris case: about 3.2 mm recoil, about 97.5 N peak spring force. Driver current limit: 1.0 A.', 22, MUTED)
txt(50, 1087, 'Source: track_wheel/README.md, images/ and simulation/  ·  Digital model; no physical prototype test footage.', 18, MUTED)
im.save(OUT/'track_wheel_r5_operation.png')
im.save(OUT/'track_wheel_r5_operation.pdf', 'PDF', resolution=150)
print(OUT/'track_wheel_r5_operation.png')

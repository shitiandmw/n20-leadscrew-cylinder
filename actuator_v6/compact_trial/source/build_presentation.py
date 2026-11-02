"""Build the offline preview, comparison image and self-contained source/CAD ZIP."""
from pathlib import Path
import base64
import gzip
import json
import shutil
import zipfile
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent
OUT = BASE.parent / "output"
OUT.mkdir(exist_ok=True)
with gzip.open(ROOT / "source" / "scene_U60.json.gz", "rt") as f:
    trial = json.load(f)
with gzip.open(BASE / "source" / "scene_U60.json.gz", "rt") as f:
    original = json.load(f)


def visible(it):
    return it["kind"] == "printed" or it["kind"] == "wire" or it["name"].startswith(("M2", "cable_sleeve", "detail_"))


changed = {"01_body", "02_front_cap", "03_rear_cap", "06_cable_clamp"}
changed.update(it["name"] for it in trial if it["name"].startswith(("M2x8_front", "M2x10_rear", "M2_nut_", "detail_")))
payload = dict(common=[it for it in original if visible(it) and it["name"] not in changed],
               original=[it for it in original if visible(it) and it["name"] in changed],
               trial=[it for it in trial if visible(it) and it["name"] in changed])
packed = base64.b64encode(gzip.compress(json.dumps(payload, separators=(",", ":")).encode(), mtime=0)).decode()
html = (ROOT / "source" / "viewer_template.html").read_text()
html = html.replace("__THREE__", (BASE / "source" / "vendor" / "three.min.js").read_text())
html = html.replace("__ORBIT__", (BASE / "source" / "vendor" / "OrbitControls.js").read_text()).replace("__PAYLOAD__", packed)
(ROOT / "3D_preview.html").write_text(html)
shutil.copyfile(BASE / "source" / "vendor" / "THREE_LICENSE.txt", ROOT / "THREE_LICENSE.txt")

font_dir = Path("/usr/share/fonts/truetype/dejavu")
regular = str(font_dir / "DejaVuSans.ttf")
bold = str(font_dir / "DejaVuSans-Bold.ttf")
font = lambda n, strong=False: ImageFont.truetype(bold if strong else regular, n)
sheet = Image.new("RGB", (1600, 1530), "#f4f3f0")
draw = ImageDraw.Draw(sheet)
draw.text((60, 30), "U60 / Compact nut mounts", font=font(38, True), fill="#222b32")
draw.text((60, 88), "Fastener-side view, same camera and scale. Only the screw corners grow.", font=font(22), fill="#5b6268")
for label, y, title, subtitle in (
    ("original", 160, "01  Original", "16.1 × 14.7 mm body · screws engage plastic"),
    ("trial", 810, "02  Compact revision", "+1.3 mm sideways / +1.7 mm at screw corners"),
):
    image = Image.open(ROOT / "images" / f"{label}.png").convert("RGB")
    sheet.paste(image, (0, y + 55))
    draw.rectangle((0, y - 10, 1600, y + 54), fill="#f4f3f0")
    draw.text((60, y), title, font=font(28, True), fill="#222b32")
    draw.text((570, y + 6), subtitle, font=font(23), fill="#4d555c")
draw.rectangle((0, 1480, 1600, 1530), fill="#f4f3f0")
draw.text((60, 1493), "CAD trial · 60 mm stroke retained · printed fit, strength and excavator clearance remain unverified", font=font(19), fill="#626970")
sheet.save(ROOT / "images" / "comparison.png")
shutil.copyfile(ROOT / "images" / "comparison.png", OUT / "u60-compact-trial-comparison.png")
shutil.copyfile(ROOT / "3D_preview.html", OUT / "u60-compact-trial.html")

# Include the baseline dependencies so geometry, renders and viewer rebuild after extraction.
dependencies = list((BASE / "source").glob("*.py")) + list((BASE / "source" / "vendor").glob("*"))
dependencies += [BASE / "parameters.json", BASE / "source" / "scene_U60.json.gz"]
dependencies += [BASE / "ASSEMBLY.md", BASE / "BOM.md"]
dependencies += [BASE / fmt / "V6-U60" / f"{part}.{fmt}" for fmt in ("step", "stl") for part in ("04_rod", "05_rod_eye")]
files = sorted(p for p in ROOT.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
with zipfile.ZipFile(OUT / "u60-compact-trial.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for p in files + dependencies:
        z.write(p, p.relative_to(BASE.parent))
print(json.dumps({p.name: p.stat().st_size for p in OUT.glob("u60-compact-trial*")}, indent=2))

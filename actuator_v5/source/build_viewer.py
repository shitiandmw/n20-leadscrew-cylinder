"""Single-file interactive 3D preview (works offline in any WebGL browser).

python source/build_viewer.py  -> 3D_preview.html
Meshes come from source/scene_meshes.json (written by build_v5.py) and are embedded
as base64 float32/uint arrays to keep the page small.
"""
from pathlib import Path
import base64
import json
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source"


def pack(items):
    out = []
    for it in items:
        v = np.asarray(it["vertices"], dtype=np.float32)
        t = np.asarray(it["triangles"], dtype=np.uint16 if len(v) < 65536 else np.uint32)
        out.append(dict(name=it["name"], kind=it["kind"], material=it["material"], color=it["color"],
                        moving=it["moving"], rotating=it.get("rotating", False), wire_id=it.get("wire_id"),
                        net=it.get("net"), wide=t.dtype == np.uint32,
                        v=base64.b64encode(v.tobytes()).decode(), t=base64.b64encode(t.tobytes()).decode()))
    return out


def main():
    params = json.loads((ROOT / "parameters.json").read_text())
    trigger = ROOT / "magnet_trigger.json"
    if trigger.exists():
        nominal = next(iter(json.loads(trigger.read_text())["cases"].values()))
        params["hall_operate_mm"] = nominal["operate_offset_mm"]["typ"]
        params["hall_release_mm"] = nominal["release_offset_mm"]["typ"]
    parts = {"__THREE__": (SRC / "vendor/three.min.js").read_text(),
             "__ORBIT__": (SRC / "vendor/OrbitControls.js").read_text(),
             "__MESHES__": json.dumps(pack(json.loads((SRC / "scene_meshes.json").read_text())), separators=(",", ":")),
             "__PARAMETERS__": json.dumps(params),
             "__BEHAVIOR__": (SRC / "viewer_behavior.js").read_text()}
    html = (SRC / "viewer_template.html").read_text()
    for k, v in parts.items():
        assert html.count(k) == 1, k
        html = html.replace(k, v)
    (ROOT / "3D_preview.html").write_text(html, encoding="utf-8")
    print(ROOT / "3D_preview.html", f"{len(html) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()

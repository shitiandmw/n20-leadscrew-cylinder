"""Single-file 3D preview with the schematic linked to the board (works offline in any WebGL browser).

python source/build_viewer.py [--root DIR]  -> DIR/3D_preview.html
Inputs in DIR (default: this package): parameters.json, validation.json and source/scene_<v>.json.gz
for each length in it (build_v6.py), electronics/schematic.svg and source/schematic_links.json
(build_schematic.py). The page template, behaviour, three.js and the circuit simulation come
from this package. Meshes that the lengths share are stored once, with a Z offset where a part
only moved. The Printed parts view takes its slicer data from validation.json; the Assembly view
plays assembly.py's plan, with the clearances of the tool-access check in its captions.
"""
from pathlib import Path
import argparse
import base64
import gzip
import json
import re
import numpy as np
import board as BD
import layout as LY
import assembly as AS

HOME = Path(__file__).resolve().parent.parent       # this package: template, behaviour, simulation
SRC = HOME / "source"
ROOT = HOME                                          # package folder with the lengths (--root)
PT_PER_CM = 72 / 2.54

PIN_NAMES = {"SOT-23/U": {"1": "VCC", "2": "OUT", "3": "GND"}, "SOT-23/Q": {"1": "G", "2": "S", "3": "D"},
             "diode": {"1": "K", "2": "A"}}
NET_INFO = {
    "A": "Cable wire A (red, W1). A positive drives the rod out.",
    "B": "Cable wire B (black, W2). B positive drives the rod in.",
    "MOT+": "Motor + (orange wire W3 to the motor's + terminal).",
    "MOT-": "Motor − (purple wire W4 to the motor's − terminal). Q2 switches it.",
    "A_SW": "Lead A after Q1 and D4; it runs through the fuse F1 to the motor.",
    "G_RET": "Gate of Q1. R1 pulls it up (Q1 on); U1 pulls it low at the retract end.",
    "G_EXT": "Gate of Q2. R2 pulls it up (Q2 on); U2 pulls it low at the extend end.",
    "VCC_RET": "Supply of U1, fed from wire B through D1 and held by C1 (only while retracting).",
    "VCC_EXT": "Supply of U2, fed from wire A through D2 and held by C2 (only while extending).",
}
MECH_INFO = {
    "01_body": "Printed body (PETG), printed rear end down. Square tube with the motor wall, the board slot, the "
               f"screw corners, the {LY.PARTITION_T:g} mm partition that keeps the carrier away from the board, and a "
               "key rib in one bore corner so the rod only goes in with its magnet toward the board.",
    "02_front_cap": "Printed front cap. Rod guide; its spigot is the hard stop at the extend end. 2 × M2 × 8.",
    "03_rear_cap": "Printed rear cap with the rear clevis (Ø3 pin). The cable wires pass a slot in it (a knot "
                   "inside stops them); its pocket holds the cable clamp. 2 × M2 × 10 through the clamp.",
    "04_rod": "Printed rod with the nut carrier: brass M3 nut in the hex slot, "
              f"Ø{LY.MAGNET['d']:g} × {LY.MAGNET['l']:g} magnet in the pocket.",
    "05_rod_eye": "Printed rod eye (Ø3 pin), held by one M2 × 10 cross screw.",
    "06_cable_clamp": "Printed cable clamp plate. The two rear-cap screws press it onto the 3 mm sleeve: a "
                      "2.6 mm groove with ridges, flared at the mouth so the cable bends gently.",
    "cable_sleeve": "Protective sleeve over the two cable wires: 3 mm OD, 2 mm bore, silicone or PVC tube. "
                    "Gripped by the cable clamp; it leaves the rear cap sideways, on the board side.",
    "motor_": "N20 gearmotor, 6 V 150 rpm, with its own M3 × 0.5 leadscrew. Unmodified bought part.",
    "M3_brass_nut": "Brass M3 hex nut (5.5 mm AF), slid into the carrier's slot.",
    "magnet_": f"Ø{LY.MAGNET['d']:g} × {LY.MAGNET['l']:g} mm {LY.MAGNET['grade']} magnet, magnetised along "
               "its axis (the travel). Press fit; the Hall switches see it through the partition.",
    "M1.6x4_countersunk": "M1.6 × 4 countersunk screw: motor to the body wall.",
    "M2x8_front_cap": "M2 × 8 pan-head screw: front cap to the body (self-tapping into the 1.6 mm pilot).",
    "M2x10_rear_cap": "M2 × 10 pan-head screw: cable clamp and rear cap to the body.",
    "M2x10_rod_eye": "M2 × 10 pan-head screw through the rod eye and the rod.",
    "PCB_board": "End-stop board: 2 layers, 0.8 mm FR4, 8 mm wide. It rests on the motor wall and is held "
                 "by the front-cap tongue.",
    "tool_PH1": f"{AS.DRIVERS['PH1']['note']}, for the five M2 pan-head screws (DIN 7985 M2 takes PH1).",
}


def load(v):
    with gzip.open(ROOT / "source" / f"scene_{v}.json.gz", "rt") as f:
        return json.load(f)


def b64(a):
    return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode()


def pack(variants):
    """Geometry pool + per-variant item lists. Returns (geoms, scenes, stats)."""
    geoms, scenes, index = [], {}, {}
    stats = dict(items=0, shared=0)
    for v in variants:
        items = []
        for it in load(v):
            vs = np.asarray(it["vertices"], dtype=np.float32)
            tr = np.asarray(it["triangles"], dtype=np.uint32)
            gid, dz = None, 0.0
            for g in index.get(it["name"], []):
                if g["v"].shape == vs.shape and g["t"].shape == tr.shape and np.array_equal(g["t"], tr):
                    d = vs - g["v"]
                    if np.abs(d[:, :2]).max() < 2e-3 and np.ptp(d[:, 2]) < 2e-3:
                        gid, dz = g["id"], round(float(d[:, 2].mean()), 3)
                        break
            stats["items"] += 1
            if gid is None:
                gid = len(geoms)
                wide = len(vs) >= 65536
                lo = vs.min(axis=0)
                step = np.maximum(vs.max(axis=0) - lo, 1e-6) / 65535      # 16-bit positions, < 0.003 mm steps
                q = np.round((vs - lo) / step).astype(np.uint16)
                geoms.append(dict(v=b64(q), o=[round(float(x), 5) for x in lo], s=[float(x) for x in step],
                                  t=b64(tr.astype(np.uint32 if wide else np.uint16)), wide=wide))
                index.setdefault(it["name"], []).append(dict(id=gid, v=vs, t=tr))
            else:
                stats["shared"] += 1
            meta = {k: x for k, x in it.items() if k not in ("vertices", "triangles")}
            items.append(dict(meta, g=gid, dz=dz))
        scenes[v] = items
    return geoms, scenes, stats


def circuit():
    parts = {}
    for ref, (kind, netmap, role) in BD.COMPONENTS.items():
        if kind == "WIRE":
            wid = {"J_A": "W1", "J_B": "W2", "J_M+": "W3", "J_M-": "W4"}[ref]
            parts[ref] = dict(kind="pad", role=role, net=netmap["1"], wire=wid)
            continue
        value, fp, h, mpn, lcsc, colour = BD.PARTS[kind]
        names = (PIN_NAMES["SOT-23/U"] if kind == "U" else PIN_NAMES["SOT-23/Q"] if kind == "Q"
                 else PIN_NAMES["diode"] if kind.startswith("D_") and kind != "D_TVS" else {})
        parts[ref] = dict(kind="part", value=value, package=fp, mpn=mpn, lcsc=lcsc, role=role, height_mm=h,
                          pins=[dict(pad=p, name=names.get(p, p), net=n) for p, n in netmap.items()])
    parts["M1"] = dict(kind="motor", value="N20 6 V 150 rpm", role="the motor (off the board, wires W3 and W4)",
                       pins=[dict(pad="+", name="+", net="MOT+"), dict(pad="-", name="−", net="MOT-")])
    members = {}
    for ref, p in parts.items():
        for pin in p.get("pins", []):
            members.setdefault(pin["net"], []).append(f"{ref}.{pin['name']}")
    nets = {n: dict(info=NET_INFO[n], members=sorted(members.get(n, []))) for n in BD.NETS}
    res = json.loads((HOME / "electronics" / "simulation" / "results.json").read_text())["scenarios"]
    sim = dict(run_mA=res["mid_speed"]["motor_current_mA"], stall_mA=res["jam_mid_stroke"]["stall_current_mA"],
               after_trip_mA=res["jam_mid_stroke"]["current_after_trip_mA"],
               trip_s=res["jam_mid_stroke"]["ptc_trip_time_s"],
               blocked_supply_mA=res["dc_extend_end"]["supply_current_while_blocked_mA"])
    wires = {"W1": dict(net="A", colour="red"), "W2": dict(net="B", colour="black"),
             "W3": dict(net="MOT+", colour="orange"), "W4": dict(net="MOT-", colour="purple")}
    return dict(parts=parts, nets=nets, wires=wires, mech=MECH_INFO, sim=sim)


def schematic_svg():
    """The A4 schematic with a transparent overlay of clickable part areas and net segments."""
    svg = (ROOT / "electronics" / "schematic.svg").read_text()
    links = json.loads((ROOT / "source" / "schematic_links.json").read_text())
    w_cm, h_cm = links["page_cm"]
    svg = svg[svg.index("<svg"):]
    svg = re.sub(r'<svg([^>]*?) width="[^"]*" height="[^"]*"', r'<svg\1 id="schematic-svg" preserveAspectRatio="xMidYMid meet"',
                 svg, count=1)
    svg = re.sub(r"<metadata>.*?</metadata>", "", svg, flags=re.S)

    def X(x):
        return round(x * PT_PER_CM, 2)

    def Y(y):
        return round((h_cm - y) * PT_PER_CM, 2)
    nets = "".join(f'<path class="net" data-net="{n["net"]}" d="M{X(n["a"][0])} {Y(n["a"][1])}L{X(n["b"][0])} '
                   f'{Y(n["b"][1])}"/>' for n in links["nets"])
    parts = ""
    for ref, (x0, y0, x1, y1) in links["parts"].items():
        parts += (f'<rect class="part" data-ref="{ref}" x="{X(x0)}" y="{Y(y1)}" width="{X(x1) - X(x0)}" '
                  f'height="{Y(y0) - Y(y1)}" rx="4"/>')
    overlay = f'<g id="sch-overlay"><g class="nets">{nets}</g><g class="parts">{parts}</g></g>'
    return svg.replace("</svg>", overlay + "</svg>"), [w_cm * PT_PER_CM, h_cm * PT_PER_CM]


def assembly_data(params):
    """Per length: the assembly plan (with the tool-access clearances) and the slicer data of the six parts."""
    vfile = ROOT / "validation.json"
    val = json.loads(vfile.read_text()) if vfile.exists() else {}
    plans, prints = {}, {}
    for v, p in params.items():
        LY.VARIANTS.setdefault(v, dict(screw_length=p["screw_length_mm"], stroke=p["stroke_mm"]))
        rep = val.get(v, {})
        plans[v] = AS.plan(LY.derived(v), rep.get("tool_access"))
        prints[v] = {n: {k: x[k] for k in ("file", "mass_solid_g", "print_extent_mm", "print_setup")}
                     for n, x in rep.get("parts", {}).items() if n[:2] in ("01", "02", "03", "04", "05", "06")}
    return dict(plans=plans, print=prints)


def main():
    global ROOT
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=HOME, help="package folder with parameters.json and the scenes")
    ROOT = ap.parse_args().root.resolve()
    params = json.loads((ROOT / "parameters.json").read_text())
    geoms, scenes, stats = pack(list(params))
    svg, page = schematic_svg()
    circ = circuit()
    circ["page_pt"] = page
    asm = assembly_data(params)
    reach = ", ".join(f"{pl['tools']['PH0']['blade_len']:g} mm for V6-{v}" for v, pl in asm["plans"].items())
    circ["mech"]["tool_PH0"] = (f"{AS.DRIVERS['PH0']['note']}. It carries the two M1.6 motor screws down the empty "
                                f"bore before the rod goes in. Blade length, 13 mm more than the bore is deep: {reach}. "
                                "A 100 mm blade covers V6-S and V6-U60; for V6-L see Known limits in README.md.")
    buttons = ""
    for i, (v, p) in enumerate(params.items()):
        state = ' class="active" aria-pressed="true"' if i == 0 else ' aria-pressed="false"'
        buttons += f'<button data-variant="{v}"{state}>V6-{v} · {p["screw_length_mm"]:g} mm screw</button>'
    parts = {"__VARIANTS__": buttons,
             "__THREE__": (SRC / "vendor/three.min.js").read_text(),
             "__ORBIT__": (SRC / "vendor/OrbitControls.js").read_text(),
             "__GEOMETRY__": json.dumps(geoms, separators=(",", ":")),
             "__SCENES__": json.dumps(scenes, separators=(",", ":")),
             "__PARAMETERS__": json.dumps(params, separators=(",", ":")),
             "__CIRCUIT__": json.dumps(circ, separators=(",", ":")),
             "__ASSEMBLY__": json.dumps(asm, separators=(",", ":")),
             "__SCHEMATIC__": svg,
             "__BEHAVIOR__": (SRC / "viewer_behavior.js").read_text()}
    html = (SRC / "viewer_template.html").read_text()
    for k, v in parts.items():
        assert html.count(k) == 1, k
        html = html.replace(k, v)
    (ROOT / "3D_preview.html").write_text(html, encoding="utf-8")
    shared = f", {stats['shared']} shared between {' and '.join(params)}" if len(params) > 1 else ""
    print(ROOT / "3D_preview.html", f"{len(html) / 1e6:.1f} MB;", len(geoms), "meshes for", f"{stats['items']} items{shared}")


if __name__ == "__main__":
    main()

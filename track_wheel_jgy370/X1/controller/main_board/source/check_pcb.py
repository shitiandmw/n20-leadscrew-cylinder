"""Check the routed X1 main board and write its manufacturing and 3D files (KiCad 9 in Docker).

- KiCad DRC with schematic parity: no errors, no unconnected items, no parity issues; every warning
  type must be on the accepted list below, with its reason;
- checks of our own against SPEC.md and the X1 body: outline and holes on the bosses, USB-C at
  machine X -98, connectors on their edges, part heights, motor and supply track widths;
- Gerbers and drill files (zip for JLCPCB), the JLCPCB placement file (CPL), the board STEP with
  KiCad's 3D models, top and bottom renders, and a layer-by-layer PDF.

Writes into ../ (STEM = X1_main_board_<rev>): STEM_pcb_checks.json, STEM.step, STEM_top.png,
STEM_bottom.png, STEM_layout.pdf, STEM_parts.json (part envelopes for the body CAD), and fab/ (gerbers
zip, CPL).

    python check_pcb.py
"""
import csv
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import layout as LY
import netlist as NL
import sexp

HERE = Path(__file__).resolve().parent
BOARD = HERE.parent
KDIR = BOARD / "kicad"
FAB = BOARD / "fab"
X1_BODY = BOARD.parents[1] / "source" / "x1_body.py"
STEM = f"X1_main_board_{NL.REV}"
PROJECT = "X1_main"
IMAGE = "kicad/kicad:9.0"
MODEL_DIR = Path(os.environ.get("KICAD9_3DMODEL_DIR", "/tmp/kicad-3d"))
MODEL_URL = "https://gitlab.com/kicad/libraries/kicad-packages3D/-/raw/9.0.0/"
ZIP_DATE = (2026, 11, 10, 0, 0, 0)
# footprints whose 3D model is not in kicad-packages3D 9.0: a stock model of the same body, or one of
# ours from models_3d.py (kicad/3d/)
STAND_INS = {
    "Package_SO.3dshapes/HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm_Mask2.46x2.31mm.step":
        ("kicad", "Package_SO.3dshapes/TSSOP-16-1EP_4.4x5mm_Pitch0.65mm_EP3.4x5mm.step"),
    "Fuse.3dshapes/Fuse_1812_4532Metric.step": ("kicad", "Capacitor_SMD.3dshapes/C_1812_4532Metric.step"),
    "Connector_USB.3dshapes/USB_C_Receptacle_HRO_TYPE-C-31-M-12.step": ("project", None),
    "Button_Switch_SMD.3dshapes/SW_Push_1P1T_XKB_TS-1187A.step": ("project", None),
    "Connector_AMASS.3dshapes/AMASS_XT30PW-M_1x02_P2.50mm_Horizontal.step": ("project", None),
}
LAYERS = "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"
# DRC warnings accepted, with the reason (type -> reason)
ACCEPTED_WARNINGS = {
    "silk_edge_clearance": "the USB-C receptacle and the module overhang the outboard edge by design (face 0.5 mm "
                           "proud, antenna over the edge); their outline silk crosses the edge and the fab clips it",
}


def docker(args, env=()):
    cmd = ["docker", "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}"]
    for e in env:
        cmd += ["-e", e]
    r = subprocess.run(cmd + args, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"docker failed: {' '.join(cmd + args)}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return r.stdout


def download(rel, dst):
    with urllib.request.urlopen(MODEL_URL + rel, timeout=60) as r:
        data = r.read()
    if not data.startswith(b"ISO-10303-21"):
        raise ValueError("not a STEP file")
    dst.write_bytes(data)


def fetch_models(pcb_tree):
    """Put every 3D model the footprints reference into MODEL_DIR: KiCad's own (kicad-packages3D,
    tag 9.0.0, downloaded once), or the stand-in from STAND_INS. Returns (models, stand-ins, missing)."""
    got, subs, missing = set(), set(), []
    for m in sexp.walk(pcb_tree, "model"):
        path = m[1]
        if not path.startswith("${KICAD9_3DMODEL_DIR}/"):
            continue
        rel = path.split("/", 1)[1]
        dst = MODEL_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            if rel in STAND_INS:
                kind, sub = STAND_INS[rel]
                if kind == "project":
                    shutil.copy(KDIR / "3d" / Path(rel).name, dst)
                elif not dst.exists():
                    download(sub, dst)
                subs.add(rel)
            elif not dst.exists():
                download(rel, dst)
        except Exception as e:  # noqa: BLE001 - report and carry on without the model
            missing.append(f"{rel}: {e}")
            continue
        got.add(rel)
    return sorted(got), sorted(subs), sorted(set(missing))


def footprints(tree):
    out = {}
    for fp in sexp.find_all(tree, "footprint"):
        ref = next(p[2] for p in sexp.find_all(fp, "property") if p[1] == "Reference")
        at = sexp.find(fp, "at")
        out[ref] = dict(lib=fp[1], x=float(at[1]), y=float(at[2]), rot=float(at[3]) if len(at) > 3 else 0.0, tree=fp)
    return out


def courtyard_bbox(fp):
    """Courtyard bounding box of a placed footprint in board (u, v), from its F.CrtYd graphics."""
    import math
    x0, y0, rot = fp["x"], fp["y"], math.radians(fp["rot"])
    pts = []
    for g in fp["tree"]:
        if not (isinstance(g, list) and g and g[0] in ("fp_line", "fp_rect", "fp_circle", "fp_poly")):
            continue
        lay = sexp.find(g, "layer")
        if not lay or lay[1] != "F.CrtYd":
            continue
        loc = []
        for k in ("start", "end", "center"):
            e = sexp.find(g, k)
            if e:
                loc.append((float(e[1]), float(e[2])))
        if g[0] == "fp_circle":
            (cx, cy), (ex, ey) = loc
            r = math.hypot(ex - cx, ey - cy)
            loc = [(cx - r, cy - r), (cx + r, cy + r), (cx - r, cy + r), (cx + r, cy - r)]
        elif g[0] == "fp_rect":
            (ax, ay), (bx, by) = loc
            loc = [(ax, ay), (bx, by), (ax, by), (bx, ay)]
        elif g[0] == "fp_poly":
            loc = [(float(p[1]), float(p[2])) for p in sexp.walk(g, "xy")]
        for lx, ly in loc:
            pts.append((x0 + lx * math.cos(rot) + ly * math.sin(rot) - LY.ORIGIN[0],
                        y0 - lx * math.sin(rot) + ly * math.cos(rot) - LY.ORIGIN[1]))
    us, vs = [p[0] for p in pts], [p[1] for p in pts]
    return min(us), min(vs), max(us), max(vs)


def track_widths(tree):
    nets = {n[1]: n[2] for n in sexp.find_all(tree, "net")}
    w = defaultdict(list)
    vias = 0
    for s in sexp.find_all(tree, "segment") + sexp.find_all(tree, "arc"):
        net = sexp.find(s, "net")[1]
        name = nets.get(net, net) if not isinstance(net, str) or net.isdigit() else net
        w[str(name)].append(float(sexp.find(s, "width")[1]))
    vias = len(sexp.find_all(tree, "via"))
    return w, vias


def pth_rings(tree):
    """Smallest annular ring of the plated pads of each footprint (vias are checked by DRC)."""
    out = {}
    for fp in sexp.find_all(tree, "footprint"):
        for pad in sexp.find_all(fp, "pad"):
            if pad[2] != "thru_hole":
                continue
            sx, sy = (float(x) for x in sexp.find(pad, "size")[1:3])
            d = sexp.find(pad, "drill")[1:]
            dx, dy = (float(d[1]), float(d[2])) if d[0] == "oval" else (float(d[0]), float(d[0]))
            ring = min((sx - dx) / 2, (sy - dy) / 2)
            out[fp[1]] = round(min(ring, out.get(fp[1], 9.0)), 3)
    return out


def body_board():
    src = X1_BODY.read_text()
    num = r"(-?\d+(?:\.\d+)?)"
    m = re.search(rf"BOARD = dict\(x=\({num}, {num}\), y=\({num}, {num}\), z=\({num}, {num}\)\)", src)
    return dict(x=(float(m[1]), float(m[2])), y=(float(m[3]), float(m[4])), z=(float(m[5]), float(m[6])))


def cpl(pos_csv):
    rows = list(csv.DictReader(io.StringIO(pos_csv)))
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
    for r in sorted(rows, key=lambda r: (re.sub(r"\d", "", r["Ref"]), int(re.sub(r"\D", "", r["Ref"]) or 0))):
        w.writerow([r["Ref"], f"{float(r['PosX']):.3f}mm", f"{float(r['PosY']):.3f}mm",
                    "Top" if r["Side"] == "top" else "Bottom", f"{float(r['Rot']):.0f}"])
    return out.getvalue(), len(rows)


def main():
    checks = []

    def check(name, ok, value, limit="", note=""):
        checks.append(dict(name=name, ok=bool(ok), value=value, limit=limit, note=note))

    pcb = KDIR / f"{PROJECT}.kicad_pcb"
    tree = sexp.parse(pcb.read_text())[0]
    got, subs, missing = fetch_models(tree)
    check("3D model for every footprint", not missing, f"{len(got)} models, {len(subs)} stand-ins", "all",
          "; ".join(missing) or "stand-ins: " + ", ".join(Path(s).stem for s in subs))

    work = Path(tempfile.mkdtemp(prefix="x1chk-"))
    for f in KDIR.iterdir():
        (shutil.copytree if f.is_dir() else shutil.copy)(f, work / f.name)
    (work / "out").mkdir()
    base = ["-v", f"{work}:/work", "-v", f"{MODEL_DIR}:/models:ro", "-w", "/work", IMAGE]
    env = ["KICAD9_3DMODEL_DIR=/models"]
    cli = lambda *a: docker(base + ["kicad-cli", *a], env)  # noqa: E731
    cli("pcb", "drc", "--schematic-parity", "--severity-all", "--format", "json", "--output", "out/drc.json",
        f"{PROJECT}.kicad_pcb")
    cli("pcb", "export", "gerbers", "--layers", LAYERS, "--use-drill-file-origin", "--subtract-soldermask",
        "--output", "out/gerbers/", f"{PROJECT}.kicad_pcb")
    cli("pcb", "export", "drill", "--format", "excellon", "--drill-origin", "plot", "--excellon-units", "mm",
        "--excellon-separate-th", "--generate-map", "--map-format", "gerberx2", "--output", "out/gerbers/",
        f"{PROJECT}.kicad_pcb")
    cli("pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "front", "--use-drill-file-origin",
        "--output", "out/pos.csv", f"{PROJECT}.kicad_pcb")
    cli("pcb", "export", "step", "--force", "--subst-models", "--drill-origin", "--no-dnp", "--output",
        f"out/{STEM}.step", f"{PROJECT}.kicad_pcb")
    cli("pcb", "export", "pdf", "--layers", "F.Cu,In1.Cu,In2.Cu,B.Cu", "--common-layers", "Edge.Cuts,F.Fab",
        "--mode-multipage", "--include-border-title", "--output", "out/layout/", f"{PROJECT}.kicad_pcb")
    # (multipage mode takes the output as a folder and names the file after the board)
    for side in ("top", "bottom"):
        cli("pcb", "render", "--side", side, "--quality", "high", "--width", "2000", "--height", "1400",
            "--background", "opaque", "--output", f"out/{side}.png", f"{PROJECT}.kicad_pcb")

    # ---- DRC
    drc = json.loads((work / "out" / "drc.json").read_text())
    viol = drc.get("violations", [])
    errors = [v for v in viol if v["severity"] == "error"]
    warn = Counter(v["type"] for v in viol if v["severity"] == "warning")
    unacc = {t: n for t, n in warn.items() if t not in ACCEPTED_WARNINGS}
    check("KiCad DRC errors", not errors, len(errors), 0,
          "; ".join(f"{v['type']}: {v['description']}" for v in errors[:10]))
    check("KiCad DRC unconnected items", not drc.get("unconnected_items"), len(drc.get("unconnected_items", [])), 0)
    check("KiCad schematic parity", not drc.get("schematic_parity"), len(drc.get("schematic_parity", [])), 0,
          "; ".join(v["description"] for v in drc.get("schematic_parity", [])[:10]))
    check("KiCad DRC warnings all of accepted types", not unacc, dict(warn), "accepted list",
          f"not accepted: {unacc}" if unacc else "")

    # ---- geometry against SPEC.md and the body
    fps = footprints(tree)
    bb = body_board()
    edge = [g for g in sexp.find_all(tree, "gr_rect") if sexp.find(g, "layer")[1] == "Edge.Cuts"]
    (sx, sy), (ex, ey) = [(float(sexp.find(edge[0], k)[1]), float(sexp.find(edge[0], k)[2])) for k in ("start", "end")]
    size = (round(ex - sx, 3), round(ey - sy, 3))
    check("Board outline equals the body's BOARD placeholder", size == (bb["x"][1] - bb["x"][0], bb["y"][1] - bb["y"][0]),
          size, f"{bb['x'][1] - bb['x'][0]} x {bb['y'][1] - bb['y'][0]} mm (x1_body.py BOARD)")
    bosses = sorted((x, y) for x in (bb["x"][0] + 4, bb["x"][1] - 4) for y in (bb["y"][0] + 4, bb["y"][1] - 4))
    holes = sorted(LY.machine(fps[h]["x"] - LY.ORIGIN[0], fps[h]["y"] - LY.ORIGIN[1]) for h in ("H1", "H2", "H3", "H4"))
    check("Mounting holes on the body's bosses", all(abs(a[0] - b[0]) < 1e-6 and abs(a[1] - b[1]) < 1e-6
                                                       for a, b in zip(holes, bosses)), holes, bosses)
    usb = fps["J201"]
    ux, _ = LY.machine(usb["x"] - LY.ORIGIN[0], usb["y"] - LY.ORIGIN[1])
    check("USB-C at machine X -98 on the outboard edge (SPEC C3)", abs(ux + 98) < 1e-6, round(ux, 3), -98.0)
    u0, v0, u1, v1 = courtyard_bbox(fps["J201"])
    check("USB-C receptacle face at the outboard edge", -1.2 < v0 < 0.0, round(v0, 2), "-1.2 .. 0 mm (face 0.5 proud)")
    u0, v0, u1, v1 = courtyard_bbox(fps["U201"])
    check("Module antenna end at the outboard edge (SPEC B3)", abs(v0 + 0.25) < 0.3, round(v0, 2), "courtyard 0.25 past the edge")
    _, _, u1, _ = courtyard_bbox(fps["J101"])
    check("XT30 on the front edge (SPEC C1)", abs(u1 - LY.W) < 0.05, round(u1, 2), LY.W)
    inboard = ["J102", "J104", "J105", "J106", "J107", "J103", "J108", "J109"]
    # top entry since 2026-11-14: each header on the pin row of rev B's side-entry one (same pads, so the copper did not
    # change), its courtyard in the strip along the inboard edge; the plugs go on from above
    pin_v = {r: round(fps[r]["y"] - LY.ORIGIN[1], 3) for r in inboard}
    want_v = {r: LY.PH_PIN_V if r in ("J108", "J109") else LY.XH_PIN_V for r in inboard}
    edge_gap = {r: round(LY.H - courtyard_bbox(fps[r])[3], 2) for r in inboard}
    check("Track, actuator, swing, lamp and expansion connectors along the inboard edge, top entry",
          all(fps[r]["lib"].endswith("_Vertical") for r in inboard) and all(abs(pin_v[r] - want_v[r]) < 1e-3 for r in inboard)
          and all(0.0 <= g <= 6.0 for g in edge_gap.values()), edge_gap,
          f"top-entry footprints, pin rows at v {LY.XH_PIN_V:.2f} (XH) / {LY.PH_PIN_V:.2f} (PH), courtyard 0-6 mm from the edge",
          "top entry since 2026-11-14 on the pin rows of rev B's side-entry headers; tracks XH-4 moved here from the front "
          "edge (DESIGN.md, PCB layout)")
    order = sorted(inboard, key=lambda r: -fps[r]["x"])
    check("Inboard connectors front to rear: tracks, boom L, boom R, stick, bucket, swing, lamps, expansion",
          order == inboard, order, inboard)
    nl = NL.build()
    tall = max((nl.info(r)["height"], r) for r in nl.parts)
    check("Tallest part on the board (SPEC B2)", tall[0] <= 20.0, tall[0], "<= 20 mm", tall[1])
    widths, vias = track_widths(tree)
    nmin = {}
    for pat, need in (("OUT1_", 0.4), ("OUT2_", 0.4)):
        for net, ws in widths.items():
            if pat in net:
                nmin[net] = min(ws)
    check("Motor output tracks at least 0.4 mm (1 A on 1 oz outer copper, about 10 C rise)",
          all(w >= 0.4 - 1e-6 for w in nmin.values()) and len(nmin) == 14, {k: v for k, v in sorted(nmin.items())}, ">= 0.4")
    w5 = min(min(ws) for net, ws in widths.items() if net in ("+5V", "+5V_EXP"))
    check("5 V and expansion supply tracks at least 0.8 mm", w5 >= 0.8 - 1e-6, w5, ">= 0.8 mm")
    rings = pth_rings(tree)
    check(f"Plated pad annular ring at least {LY.PTH_MIN_RING} mm (JLCPCB multilayer, 1 oz)",
          min(rings.values()) >= LY.PTH_MIN_RING - 1e-6, min(rings.values()), f">= {LY.PTH_MIN_RING}",
          ", ".join(f"{k.split(':')[1]} {v}" for k, v in sorted(rings.items(), key=lambda kv: kv[1])[:4]))
    check("Routed", vias > 0 and sum(len(w) for w in widths.values()) > 0,
          f"{sum(len(w) for w in widths.values())} segments, {vias} vias")

    # ---- manufacturing files
    FAB.mkdir(exist_ok=True)
    gdir = work / "out" / "gerbers"
    zpath = FAB / f"{STEM}_gerbers.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(gdir.iterdir()):
            zi = zipfile.ZipInfo(f.name, ZIP_DATE)
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, f.read_bytes())
    names = sorted(f.name for f in gdir.iterdir())
    check("Gerber set complete (4 copper, masks, silk, paste, outline, PTH and NPTH drill)",
          sum(n.endswith((".gtl", ".g1", ".g2", ".gbl")) for n in names) == 4 and any(n.endswith("-PTH.drl") for n in names)
          and any(n.endswith("-NPTH.drl") for n in names) and any(n.endswith(".gm1") for n in names), names)
    text, n = cpl((work / "out" / "pos.csv").read_text())
    (FAB / f"{STEM}_CPL_JLCPCB.csv").write_text(text)
    placed = sum(1 for r in nl.parts if nl.info(r).get("lcsc"))
    check("CPL lists every assembled part", n == placed, n, placed, "rotations are KiCad's; confirm in JLCPCB's placement preview")
    shutil.copy(work / "out" / f"{STEM}.step", BOARD / f"{STEM}.step")
    shutil.copy(work / "out" / "layout" / f"{PROJECT}.pdf", BOARD / f"{STEM}_layout.pdf")
    for side in ("top", "bottom"):
        shutil.copy(work / "out" / f"{side}.png", BOARD / f"{STEM}_{side}.png")

    # ---- part envelopes for the body CAD (x1_body.py): courtyard boxes in machine coordinates
    top = bb["z"][1]
    parts = []
    for ref in sorted(nl.parts):
        h = nl.info(ref).get("height") or 0.0
        if nl.parts[ref]["kind"] in ("HOLE", "TP") or h <= 0:
            continue
        u0, v0, u1, v1 = courtyard_bbox(fps[ref])
        (xa, ya), (xb, yb) = LY.machine(u0, v0), LY.machine(u1, v1)
        at = LY.machine(fps[ref]["x"] - LY.ORIGIN[0], fps[ref]["y"] - LY.ORIGIN[1])
        parts.append(dict(ref=ref, value=nl.info(ref)["value"], x=[round(xa, 2), round(xb, 2)],
                          y=[round(min(ya, yb), 2), round(max(ya, yb), 2)], z=[top, round(top + h, 2)],
                          at=[round(at[0], 3), round(at[1], 3)], rot=fps[ref]["rot"]))
    (BOARD / f"{STEM}_parts.json").write_text(json.dumps(dict(
        note="Courtyard boxes of the placed parts in X1 machine coordinates (mm), from the board; heights from "
             "netlist.py; 'at' is the footprint origin (pin 1 of the JST headers) and 'rot' its KiCad rotation. Written "
             "by check_pcb.py for x1_body.py.", board=bb, parts=parts), indent=1) + "\n")

    report = dict(board=f"{NL.TITLE} rev {NL.REV}", all_pass=all(c["ok"] for c in checks),
                  drc=dict(errors=len(errors), warnings=dict(warn), unconnected=len(drc.get("unconnected_items", [])),
                           parity=len(drc.get("schematic_parity", [])), accepted=ACCEPTED_WARNINGS),
                  checks=checks)
    (BOARD / f"{STEM}_pcb_checks.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    for c in checks:
        print(("PASS " if c["ok"] else "FAIL ") + f"{c['name']}: {str(c['value'])[:160]}" + (f"  [{c['note'][:200]}]" if c['note'] else ""))
    print("all_pass", report["all_pass"], "| work files in", work)
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())

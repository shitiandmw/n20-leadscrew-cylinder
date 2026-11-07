"""Project footprint library X1_main.pretty (the parts KiCad's library does not cover as needed).

- ESP32-S3-WROOM-1_X1: KiCad's RF_Module:ESP32-S3-WROOM-1, with the antenna keep-out narrowed from
  +/-24 mm to +/-22 mm about the module centre. The full width cannot fit on a 96 mm board that has
  corner bosses and the USB-C on the same edge. Everything else (pads, keep-out depth, paste) is the
  library footprint, read from the KiCad 9 image.
- Buzzer_XHXDZ_8530: XHXDZ SMD8530-32 ohm (LCSC C49246949), from the LCSC/EasyEDA land pattern:
  4 pads of 1.8 x 1.8 mm on a 6.975 mm square. Viewed from the top, pad 1 (+) is bottom-right and
  pad 2 (-) is top-right. The two left pads are mounting only (no number). The body is 8.5 x 8.5 x 3.0 mm.

Writes ../kicad/X1_main.pretty/*.kicad_mod and ../kicad/fp-lib-table.

    python footprints.py
"""
import os
import subprocess
import uuid
from pathlib import Path

import sexp
from sexp import Sym as S

HERE = Path(__file__).resolve().parent
KDIR = HERE.parent / "kicad"
LIB = KDIR / "X1_main.pretty"
FPDIR = Path(os.environ.get("KICAD_FOOTPRINT_DIR", "/tmp/kicad-lib/fp"))
IMAGE = "kicad/kicad:9.0"
NS = uuid.UUID("0c7d5e4a-31a2-4f3e-8f0b-5e2f7b1d9a64")
MODULE_KEEPOUT_HALF_W = 22.0          # mm about the module centre (library: 24)
BUZ = dict(body=8.5, pitch=6.975, pad=1.8, height=3.0)


def uid(*k):
    return str(uuid.uuid5(NS, "/".join(map(str, k))))


def library_text(rel):
    """A KiCad library footprint: from KICAD_FOOTPRINT_DIR if extracted, else straight from the image."""
    p = FPDIR / rel
    if p.exists():
        return p.read_text()
    r = subprocess.run(["docker", "run", "--rm", IMAGE, "cat", f"/usr/share/kicad/footprints/{rel}"],
                       capture_output=True, text=True, check=True)
    return r.stdout


def module_footprint():
    t = sexp.parse(library_text("RF_Module.pretty/ESP32-S3-WROOM-1.kicad_mod"))[0]
    t[1] = "ESP32-S3-WROOM-1_X1"
    d = sexp.find(t, "descr")
    d[1] = (d[1] + " | X1 copy: antenna keep-out narrowed to +/-22 mm about the module centre to fit the "
            "96 mm board between the corner boss and the USB-C")
    out = []
    for c in t:
        lay = sexp.find(c, "layer") if isinstance(c, list) else None
        if isinstance(c, list) and c[0] == "fp_line" and lay and lay[1] == "F.CrtYd":
            continue                                   # replaced by one rectangle below
        out.append(c)
    t[:] = out
    zone = sexp.find(t, "zone")
    pts = sexp.find(sexp.find(zone, "polygon"), "pts")
    for xy in sexp.find_all(pts, "xy"):
        x = float(xy[1])
        xy[1] = S(sexp.fmt_num(MODULE_KEEPOUT_HALF_W if x > 0 else -MODULE_KEEPOUT_HALF_W))
    crt = [S("fp_rect"), [S("start"), -9.75, -13.0], [S("end"), 9.75, 13.45],
           [S("stroke"), [S("width"), 0.05], [S("type"), S("solid")]], [S("fill"), S("no")], [S("layer"), "F.CrtYd"],
           [S("uuid"), uid("module", "crtyd")]]
    # the keep-out outline, drawn for people on the courtyard-free user layer
    ko = [S("fp_rect"), [S("start"), -MODULE_KEEPOUT_HALF_W, -27.75], [S("end"), MODULE_KEEPOUT_HALF_W, -6.75],
          [S("stroke"), [S("width"), 0.1], [S("type"), S("dash")]], [S("fill"), S("no")], [S("layer"), "Cmts.User"],
          [S("uuid"), uid("module", "keepout")]]
    i = t.index(zone)
    t[i:i] = [crt, ko]
    return t


def text_prop(name, value, at, layer, hide=False, size=1.0):
    p = [S("property"), name, value, [S("at"), *at], [S("layer"), layer]]
    if hide:
        p.append([S("hide"), S("yes")])
    p += [[S("uuid"), uid("buz", name)], [S("effects"), [S("font"), [S("size"), size, size], [S("thickness"), 0.15]]]]
    return p


def line(a, b, layer, w, key):
    return [S("fp_line"), [S("start"), *a], [S("end"), *b], [S("stroke"), [S("width"), w], [S("type"), S("solid")]],
            [S("layer"), layer], [S("uuid"), uid("buz", key)]]


def rect(a, b, layer, w, key):
    return [S("fp_rect"), [S("start"), *a], [S("end"), *b], [S("stroke"), [S("width"), w], [S("type"), S("solid")]],
            [S("fill"), S("no")], [S("layer"), layer], [S("uuid"), uid("buz", key)]]


def buzzer_footprint():
    h, p, s = BUZ["body"] / 2, BUZ["pitch"] / 2, BUZ["pad"]
    crt = round(max(h, p + s / 2) + 0.25, 2)
    t = [S("footprint"), "Buzzer_XHXDZ_8530", [S("version"), 20241229], [S("generator"), "x1_footprints"],
         [S("generator_version"), "9.0"], [S("layer"), "F.Cu"],
         [S("descr"), "XHXDZ SMD8530 passive SMD buzzer 8.5x8.5x3.0 mm, LCSC C49246949 (land pattern from LCSC/EasyEDA)"],
         [S("tags"), "buzzer magnetic SMD 8530"],
         text_prop("Reference", "REF**", (0, -h - 1.4, 0), "F.SilkS"),
         text_prop("Value", "Buzzer_XHXDZ_8530", (0, h + 1.4, 0), "F.Fab"),
         text_prop("Datasheet", "https://www.lcsc.com/product-detail/C49246949.html", (0, 0, 0), "F.Fab", hide=True),
         text_prop("Description", "5 V passive buzzer, 32 ohm", (0, 0, 0), "F.Fab", hide=True),
         [S("attr"), S("smd")],
         rect((-h, -h), (h, h), "F.Fab", 0.1, "fab"),
         rect((-crt, -crt), (crt, crt), "F.CrtYd", 0.05, "crt")]
    # silkscreen: body edges between the corner pads, and a "+" beside pad 1 (bottom-right)
    sk = h + 0.15                         # silk just outside the body
    e = p - s / 2 - 0.3                   # stop the edges 0.3 mm short of the pads
    t += [line((-e, -sk), (e, -sk), "F.SilkS", 0.12, "top"),
          line((-e, sk), (e, sk), "F.SilkS", 0.12, "bot"),
          line((-sk, -e), (-sk, e), "F.SilkS", 0.12, "left"),
          line((sk, -e), (sk, e), "F.SilkS", 0.12, "right"),
          line((sk + 0.5, p), (sk + 1.3, p), "F.SilkS", 0.12, "plus_h"),
          line((sk + 0.9, p - 0.4), (sk + 0.9, p + 0.4), "F.SilkS", 0.12, "plus_v"),
          [S("fp_text"), S("user"), "${REFERENCE}", [S("at"), 0, 0, 0], [S("layer"), "F.Fab"], [S("uuid"), uid("buz", "fabref")],
           [S("effects"), [S("font"), [S("size"), 1, 1], [S("thickness"), 0.15]]]]]
    for num, (x, y) in (("1", (p, p)), ("2", (p, -p)), ("", (-p, -p)), ("", (-p, p))):
        t.append([S("pad"), num, S("smd"), S("rect"), [S("at"), x, y], [S("size"), s, s],
                  [S("layers"), "F.Cu", "F.Paste", "F.Mask"], [S("uuid"), uid("buz", "pad", x, y)]])
    t.append([S("embedded_fonts"), S("no")])
    t.append([S("model"), "${KIPRJMOD}/3d/Buzzer_XHXDZ_8530.step", [S("offset"), [S("xyz"), 0, 0, 0]],
              [S("scale"), [S("xyz"), 1, 1, 1]], [S("rotate"), [S("xyz"), 0, 0, 0]]])
    return t


def main():
    LIB.mkdir(parents=True, exist_ok=True)
    for fp in (module_footprint(), buzzer_footprint()):
        (LIB / f"{fp[1]}.kicad_mod").write_text(sexp.dump(fp) + "\n")
    (KDIR / "fp-lib-table").write_text(
        '(fp_lib_table\n  (version 7)\n  (lib (name "X1_main")(type "KiCad")(uri "${KIPRJMOD}/X1_main.pretty")'
        '(options "")(descr "X1 main board project footprints"))\n)\n')
    print("wrote", ", ".join(sorted(p.name for p in LIB.iterdir())))


if __name__ == "__main__":
    main()

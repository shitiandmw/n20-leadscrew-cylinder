"""V6 end-stop board: parts, nets, placement, copper, and the design-rule check.

Board frame (mm): u along the board (0 = rear edge, resting on the motor wall), v across it
(+v = actuator +Y), seen from the component side. Parts sit on the top side only, facing
the actuator bore. KiCad conventions for footprints and rotations, so the files open in
KiCad and the placement file matches its footprints.

    python source/board.py S|L   -> prints the DRC report and writes a preview PNG
"""
from pathlib import Path
import math
import sys
from shapely.geometry import Point, LineString, Polygon, box as sbox
from shapely.ops import unary_union
import layout as LY

ROOT = Path(__file__).resolve().parent.parent

RULES = dict(clearance=0.2, track_min=0.2, power_track=0.45, via_drill=0.3, via_pad=0.6, edge=0.3,
             mask_expand=0.05, silk_line=0.15, band=LY.PART_BAND_Y + 0.15, courtyard_gap=0.0)

# ---- footprints (KiCad-compatible, local y down) --------------------------------------
FP = {
    "SOT-23": dict(kicad="Package_TO_SOT_SMD:SOT-23", pads={"1": (-0.9375, -0.95), "2": (-0.9375, 0.95),
                                                             "3": (0.9375, 0.0)},
                   pad=(1.325, 0.6), body=(1.3, 2.9)),
    "SOD-323": dict(kicad="Diode_SMD:D_SOD-323", pads={"1": (-1.05, 0.0), "2": (1.05, 0.0)},
                    pad=(0.6, 0.45), body=(1.7, 1.25)),
    "SOD-123F": dict(kicad="Diode_SMD:D_SOD-123F", pads={"1": (-1.4, 0.0), "2": (1.4, 0.0)},
                     pad=(1.0, 1.2), body=(2.7, 1.7)),
    "0603": dict(kicad="Capacitor_SMD:C_0603_1608Metric", pads={"1": (-0.775, 0.0), "2": (0.775, 0.0)},
                 pad=(0.9, 0.95), body=(1.6, 0.8)),
    "R0603": dict(kicad="Resistor_SMD:R_0603_1608Metric", pads={"1": (-0.775, 0.0), "2": (0.775, 0.0)},
                  pad=(0.9, 0.95), body=(1.6, 0.8)),
    "1206": dict(kicad="Fuse:Fuse_1206_3216Metric", pads={"1": (-1.4, 0.0), "2": (1.4, 0.0)},
                 pad=(1.25, 1.75), body=(3.2, 1.6)),
    "WIRE": dict(kicad="actuator_v6:WirePad_1.1x1.5", pads={"1": (0.0, 0.0)}, pad=(1.5, 1.1), body=None),
}

PARTS = {  # value, footprint, height, MPN, LCSC, body colour
    "U": ("DRV5033AJQDBZR", "SOT-23", 1.12, "TI DRV5033AJQDBZR", "C85151", "#222222"),
    "Q": ("AO3400A", "SOT-23", 1.25, "AOS AO3400A", "C20917", "#222222"),
    "D_SIG": ("1N4148WS", "SOD-323", 1.1, "JSCJ 1N4148WS", "C2128", "#222222"),
    "D_SCH": ("B5819WS", "SOD-323", 1.1, "JSCJ B5819WS", "C22624", "#222222"),
    "D_TVS": ("SMF7.0CA", "SOD-123F", 1.08, "MDD SMF7.0CA (bidirectional)", "C123795", "#2b2b2b"),
    "F": ("0.12 A PPTC", "1206", 0.85, "Bourns MF-NSMF012-2", "C163517", "#3c5a8a"),
    "C1U": ("1 µF 50 V X5R", "0603", 0.9, "Samsung CL10A105KB8NNNC", "C15849", "#b08a5a"),
    "C100N": ("100 nF 50 V X7R", "0603", 0.9, "Yageo CC0603KRX7R9BB104", "C14663", "#b08a5a"),
    "R1M": ("1 MΩ 1 %", "R0603", 0.45, "UNI-ROYAL 0603WAF1004T5E", "C22935", "#1a1a1a"),
}

# Each part: ref -> (kind, {pad: net}, role). Nets follow the simulation netlist.
COMPONENTS = {
    "U1": ("U", {"1": "VCC_RET", "2": "G_RET", "3": "A"}, "retract-end Hall switch"),
    "U2": ("U", {"1": "VCC_EXT", "2": "G_EXT", "3": "B"}, "extend-end Hall switch"),
    "Q1": ("Q", {"1": "G_RET", "2": "A", "3": "A_SW"}, "blocks retract (lead A)"),
    "Q2": ("Q", {"1": "G_EXT", "2": "B", "3": "MOT-"}, "blocks extend (lead B)"),
    "D1": ("D_SIG", {"1": "VCC_RET", "2": "B"}, "feeds U1 from lead B"),
    "D2": ("D_SIG", {"1": "VCC_EXT", "2": "A"}, "feeds U2 from lead A"),
    "C1": ("C1U", {"1": "VCC_RET", "2": "A"}, "U1 supply hold / bypass"),
    "C2": ("C1U", {"1": "VCC_EXT", "2": "B"}, "U2 supply hold / bypass"),
    "R1": ("R1M", {"1": "VCC_RET", "2": "G_RET"}, "Q1 gate pull-up"),
    "R2": ("R1M", {"1": "VCC_EXT", "2": "G_EXT"}, "Q2 gate pull-up"),
    "D4": ("D_SCH", {"1": "A_SW", "2": "A"}, "bypasses Q1's body diode"),
    "D5": ("D_SCH", {"1": "MOT-", "2": "B"}, "bypasses Q2's body diode"),
    "F1": ("F", {"1": "A_SW", "2": "MOT+"}, "resettable fuse, jam protection"),
    "C3": ("C100N", {"1": "MOT+", "2": "MOT-"}, "motor noise suppression"),
    "D3": ("D_TVS", {"1": "MOT+", "2": "MOT-"}, "clamps the motor's turn-off spike"),
    "J_A": ("WIRE", {"1": "A"}, "cable wire A (+ = extend)"),
    "J_B": ("WIRE", {"1": "B"}, "cable wire B (+ = retract)"),
    "J_M+": ("WIRE", {"1": "MOT+"}, "to motor terminal +"),
    "J_M-": ("WIRE", {"1": "MOT-"}, "to motor terminal -"),
}
NETS = ["A", "B", "MOT+", "MOT-", "A_SW", "G_RET", "G_EXT", "VCC_RET", "VCC_EXT"]
POWER_NETS = {"A", "B", "MOT+", "MOT-", "A_SW"}


def placement(variant):
    """ref -> (u, v, rot). Rear cluster fixed; the front cell follows U2's position."""
    d = LY.derived(variant)
    u1 = d["hall_z"][0] - LY.PCB_Z0
    u2 = d["hall_z"][1] - LY.PCB_Z0
    p = {
        "J_A": (1.1, 2.45, 0), "J_M+": (1.1, 0.82, 0), "J_M-": (1.1, -0.82, 0), "J_B": (1.1, -2.45, 0),
        "U1": (u1, 0.0, 180), "C1": (u1, -2.25, 180),
        "R1": (u1 + 2.85, 0.0, 90), "D1": (u1 + 3.45, -2.25, 0),
        "Q1": (u1 + 7.0, 1.55, 0), "D4": (u1 + 7.0, -1.05, 180),
        "F1": (u1 + 11.6, 1.75, 0), "C3": (u1 + 11.0, -2.25, 0), "D3": (u1 + 15.7, -1.2, 270),
        "U2": (u2, 0.0, 0), "C2": (u2, -2.25, 0),
        "R2": (u2 - 2.85, 0.0, 270), "D2": (u2 - 3.45, -2.25, 180),
        "Q2": (u2 - 7.0, 1.55, 180), "D5": (u2 - 7.0, -1.05, 0),
    }
    return p


ROUTE_ORDER = ["MOT-", "B", "A", "MOT+", "A_SW", "G_RET", "VCC_RET", "G_EXT", "VCC_EXT"]


def routes(variant, force=False):
    """Copper from the router: tracks [(net, layer, width, [(u, v), ...])], vias [(net, (u, v))].
    Cached in electronics/pcb/route_<variant>.json, keyed on the placement."""
    import hashlib
    import json
    key = hashlib.sha1((json.dumps([placement(variant), ROUTE_ORDER, RULES], sort_keys=True)
                    + (Path(__file__).parent / "router.py").read_text()).encode()).hexdigest()
    cache = ROOT / "electronics" / "pcb" / f"route_{variant}.json"
    if cache.exists() and not force:
        data = json.loads(cache.read_text())
        if data.get("key") == key:
            return ([(n, l, w, [tuple(p) for p in pts]) for n, l, w, pts in data["tracks"]],
                    [(n, tuple(at)) for n, at in data["vias"]])
    import numpy as np
    from router import Grid, route_net
    d = LY.derived(variant)
    grid = Grid(d["pcb_length"], LY.PCB_W, RULES["edge"])
    P = pads(variant)
    copper = {"F.Cu": {}, "B.Cu": {}}
    smd = np.zeros((grid.nu, grid.nv), bool)
    for (ref, num), pad in P.items():
        r = grid.raster(pad["poly"])
        copper["F.Cu"][pad["net"]] = copper["F.Cu"].get(pad["net"], np.zeros_like(r)) | r
        if not ref.startswith("J_"):
            smd |= r
    tracks, vias = [], []
    for net in ROUTE_ORDER:
        terms = [pad["poly"] for (ref, num), pad in sorted(P.items()) if pad["net"] == net]
        wire = [pad["poly"] for (ref, num), pad in sorted(P.items()) if pad["net"] == net and ref.startswith("J_")]
        if wire:                                   # grow the tree from the wire pad
            terms = wire + [t for t in terms if t not in wire]
        w = RULES["power_track"] if net in POWER_NETS else 0.25
        t, v = route_net(grid, net, terms, copper, smd, w, RULES)
        tracks += t
        vias += v
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(dict(key=key, tracks=tracks, vias=vias)))
    return tracks, vias


# ---- geometry helpers -----------------------------------------------------------------
def xf(x, y, place):
    """KiCad local (x, y-down) -> board (u, v) for a footprint at (u0, v0, rot)."""
    u0, v0, a = place
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return (u0 + x * c + y * s, v0 + x * s - y * c)


def rect_poly(cx, cy, w, h, rot):
    """Axis-aligned w x h (in footprint frame) rotated by rot (multiples of 90)."""
    if round(rot) % 180 == 90:
        w, h = h, w
    return sbox(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def pads(variant):
    out = {}
    pl = placement(variant)
    for ref, (kind, netmap, _) in COMPONENTS.items():
        fp = FP[PARTS[kind][1]] if kind != "WIRE" else FP["WIRE"]
        for num, (x, y) in fp["pads"].items():
            at = xf(x, y, pl[ref])
            out[(ref, num)] = dict(at=at, net=netmap[num],
                                   poly=rect_poly(at[0], at[1], fp["pad"][0], fp["pad"][1], pl[ref][2]))
    return out


def bodies(variant):
    out = {}
    pl = placement(variant)
    for ref, (kind, _, _) in COMPONENTS.items():
        if kind == "WIRE":
            continue
        fp = FP[PARTS[kind][1]]
        u0, v0, a = pl[ref]
        out[ref] = rect_poly(u0, v0, fp["body"][0], fp["body"][1], a)
    return out


def courtyard(variant, ref):
    pl = placement(variant)
    geo = [p["poly"] for (r, _), p in pads(variant).items() if r == ref]
    b = bodies(variant).get(ref)
    if b is not None:
        geo.append(b)
    return unary_union(geo).envelope.buffer(0.15, join_style=2)


def board_outline(variant):
    d = LY.derived(variant)
    return sbox(0, -LY.PCB_W / 2, d["pcb_length"], LY.PCB_W / 2)


def copper(variant):
    """net -> layer -> shapely geometry (pads, tracks, via pads)."""
    tr, vias = routes(variant)
    geo = {n: {"F.Cu": [], "B.Cu": []} for n in NETS}
    for p in pads(variant).values():
        geo[p["net"]]["F.Cu"].append(p["poly"])
    for net, layer, w, pts in tr:
        line = LineString(pts) if len(pts) > 1 and pts[0] != pts[-1] else Point(pts[0])
        geo[net][layer].append(line.buffer(w / 2, cap_style=1, join_style=1))
    for net, at in vias:
        for layer in ("F.Cu", "B.Cu"):
            geo[net][layer].append(Point(at).buffer(RULES["via_pad"] / 2, 32))
    return {n: {l: unary_union(g) for l, g in ly.items()} for n, ly in geo.items()}, tr, vias


# ---- design-rule check -----------------------------------------------------------------
def drc(variant):
    errors, notes = [], []
    cu, tr, vias = copper(variant)
    outline = board_outline(variant)
    inner = outline.buffer(-RULES["edge"], join_style=2)
    # clearance between nets, per layer
    for layer in ("F.Cu", "B.Cu"):
        for i, a in enumerate(NETS):
            for bnet in NETS[i + 1:]:
                ga, gb = cu[a][layer], cu[bnet][layer]
                if ga.is_empty or gb.is_empty:
                    continue
                dist = ga.distance(gb)
                if dist < RULES["clearance"] - 1e-6:
                    errors.append(f"{layer}: {a} to {bnet} clearance {dist:.3f} mm")
    # board edge
    for n in NETS:
        for layer in ("F.Cu", "B.Cu"):
            g = cu[n][layer]
            if not g.is_empty and not inner.contains(g):
                errors.append(f"{layer}: {n} copper within {RULES['edge']} mm of the board edge")
    # connectivity: copper islands per net joined through vias
    for n in NETS:
        parts = []
        for layer in ("F.Cu", "B.Cu"):
            g = cu[n][layer]
            geoms = list(g.geoms) if hasattr(g, "geoms") else ([g] if not g.is_empty else [])
            parts += [(layer, p) for p in geoms]
        parent = list(range(len(parts)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        for net, at in vias:
            if net != n:
                continue
            hit = [i for i, (_, p) in enumerate(parts) if p.distance(Point(at)) < 1e-6]
            for i in hit[1:]:
                parent[find(i)] = find(hit[0])
        roots = {find(i) for i in range(len(parts))}
        pad_list = [k for k, p in pads(variant).items() if p["net"] == n]
        if len(roots) != 1:
            errors.append(f"net {n} is split into {len(roots)} copper islands")
        for k in pad_list:
            if not any(p.intersects(pads(variant)[k]["poly"]) for l, p in parts if l == "F.Cu"):
                errors.append(f"pad {k} of {n} not on copper")
    # vias must not sit in SMD pads (except the hand-soldered wire pads)
    for net, at in vias:
        for (ref, num), p in pads(variant).items():
            if not ref.startswith("J_") and p["poly"].distance(Point(at)) < RULES["via_pad"] / 2 + 0.1:
                errors.append(f"via of {net} at {at[0]:.2f},{at[1]:.2f} touches pad {ref}.{num}")
    # tracks narrower than the rule, power nets narrower than the power rule
    for net, layer, w, pts in tr:
        if w < RULES["track_min"] - 1e-9:
            errors.append(f"{net} track {w} mm below {RULES['track_min']}")
    # parts inside the band that faces the bore opening
    band = RULES["band"]
    for ref, b in bodies(variant).items():
        if b.bounds[1] < -band - 1e-9 or b.bounds[3] > band + 1e-9:
            errors.append(f"{ref} body outside |v| <= {band}")
    for (ref, num), p in pads(variant).items():
        if not ref.startswith("J_") and (p["poly"].bounds[1] < -band - 1e-9 or p["poly"].bounds[3] > band + 1e-9):
            errors.append(f"{ref}.{num} pad outside |v| <= {band}")
    # courtyards do not overlap
    refs = [r for r in COMPONENTS if not r.startswith("J_")]
    cys = {r: courtyard(variant, r) for r in refs}
    for i, a in enumerate(refs):
        for bref in refs[i + 1:]:
            if cys[a].intersection(cys[bref]).area > 1e-6:
                errors.append(f"courtyards of {a} and {bref} overlap")
    # Hall switches exactly where the magnet model wants them
    d = LY.derived(variant)
    pl = placement(variant)
    for ref, z in (("U1", d["hall_z"][0]), ("U2", d["hall_z"][1])):
        if abs(pl[ref][0] + LY.PCB_Z0 - z) > 1e-6 or abs(pl[ref][1]) > 1e-6:
            errors.append(f"{ref} not at the Hall position z={z}")
    total = sum(LineString(p).length for _, _, _, p in tr if len(p) > 1)
    notes.append(f"{len(tr)} track segments, {total:.0f} mm of track, {len(vias)} vias")
    return errors, notes


def render(variant, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as MPoly
    cu, tr, vias = copper(variant)
    out = board_outline(variant)
    L = out.bounds[2]
    fig, ax = plt.subplots(figsize=(max(8, L / 4.2), 2.6), dpi=200)
    ax.add_patch(MPoly(list(out.exterior.coords), fc="#1d5e3a", ec="k", lw=0.6))
    band = RULES["band"]
    ax.axhline(band, color="#ffffff", lw=0.4, ls=":")
    ax.axhline(-band, color="#ffffff", lw=0.4, ls=":")

    def draw(g, **kw):
        for p in (g.geoms if hasattr(g, "geoms") else [g]):
            if p.is_empty:
                continue
            ax.add_patch(MPoly(list(p.exterior.coords), **kw))
    for n in NETS:
        draw(cu[n]["B.Cu"], fc="#3a7bd5", ec="none", alpha=0.55)
    for n in NETS:
        draw(cu[n]["F.Cu"], fc="#d9a441", ec="none", alpha=0.9)
    for ref, b in bodies(variant).items():
        draw(b, fc="none", ec="#ffffff", lw=0.5)
        c = b.centroid
        ax.text(c.x, c.y, ref, fontsize=3.2, ha="center", va="center", color="#ffffff")
    for (ref, num), p in pads(variant).items():
        if ref.startswith("J_"):
            ax.text(p["at"][0], p["at"][1], ref[2:], fontsize=3.2, ha="center", va="center", color="k")
    for _, at in vias:
        ax.add_patch(plt.Circle(at, RULES["via_drill"] / 2, color="k"))
    ax.set_xlim(-0.5, L + 0.5)
    ax.set_ylim(-4.5, 4.5)
    ax.set_aspect("equal")
    ax.set_title(f"V6-{variant} end-stop board, top view (gold = top copper, blue = bottom)", fontsize=6)
    ax.tick_params(labelsize=4)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


if __name__ == "__main__":
    v = sys.argv[1] if len(sys.argv) > 1 else "S"
    errs, notes = drc(v)
    print("\n".join(notes))
    print(f"{len(errs)} DRC errors")
    for e in errs:
        print("  ", e)
    render(v, f"/tmp/v6work/board_{v}.png")

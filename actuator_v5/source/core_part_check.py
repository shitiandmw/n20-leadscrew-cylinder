"""Core-part check: the user's drawing and photo next to the modelled N20, V4 and V5 to scale.

python source/core_part_check.py [--v4 path/to/V4/source/scene_meshes.json]
    -> images/core_part_check.png
Side elevations are projections of the exported CAD meshes (axis horizontal, 12 mm side
vertical), aligned at the gearbox front face. The V4 row is drawn only when its mesh file
is given.
"""
from pathlib import Path
import argparse
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
INK, MUTED, RED = "#1d2a30", "#5f6f75", "#b02a1f"
V4_DRIVE = ("motor_", "coupler", "M4_", "bearing", "washer")


def silhouettes(ax, items, keep, z_ref, y0):
    for it in items:
        if not keep(it["name"]):
            continue
        v = np.asarray(it["vertices"])
        t = np.asarray(it["triangles"])
        pts = np.stack([v[:, 2] - z_ref, v[:, 1] + y0], 1)[t]
        c = it["color"]
        ax.add_collection(PolyCollection(pts, facecolors=[c], edgecolors=[c], linewidths=0.15,
                                         zorder=2 + ("screw" in it["name"] or "leadscrew" in it["name"])))


def dim(ax, x0, x1, y, text, color=INK, above=True, left=False):
    ax.annotate("", (x0, y), (x1, y), arrowprops=dict(arrowstyle="<->", lw=0.8, color=color, shrinkA=0, shrinkB=0))
    for x in (x0, x1):
        ax.plot([x, x], [y - 0.8, y + 0.8], color=color, lw=0.6)
    if left:                     # short span: text beside it
        ax.text(x0 - 0.6, y, text, ha="right", va="center", fontsize=8.5, color=color)
    else:
        ax.text((x0 + x1) / 2, y + (0.9 if above else -0.9), text, ha="center", va="bottom" if above else "top",
                fontsize=8.5, color=color)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v4", type=Path, help="V4 source/scene_meshes.json for the comparison row")
    a = ap.parse_args()
    p = json.loads((ROOT / "parameters.json").read_text())
    v5 = json.loads((ROOT / "source" / "scene_meshes.json").read_text())
    v4 = json.loads(a.v4.read_text()) if a.v4 else None
    L = p["screw_length_mm"]

    fig = plt.figure(figsize=(16, 10.6), dpi=130)
    fig.patch.set_facecolor("white")
    ref = ROOT / "references"
    for i, (name, title) in enumerate((("user_motor_dimensions.jpg", "Your drawing (units mm)"),
                                       ("user_motor_photo.jpg", "Your photo: leadscrew straight out of the gearbox"))):
        ax = fig.add_axes([0.03 + 0.5 * i, 0.55, 0.44, 0.40])
        img = Image.open(ref / name)
        if img.width == img.height:
            img = img.crop((240, 170, 1010, 1030))      # drop the seller logo
        ax.imshow(img)
        ax.set_title(title, fontsize=11, color=INK, loc="left")
        ax.axis("off")

    ax = fig.add_axes([0.03, 0.03, 0.94, 0.48])
    ax.set_aspect("equal")
    ax.axis("off")
    y5, y4 = 0.0, 24.0
    silhouettes(ax, v5, lambda n: n.startswith("motor_") or n == "M3_nut", 0.0, y5)
    ax.text(-33, y5 + 11.5, "V5 (this package)", fontsize=11, color=INK, weight="bold")
    ax.text(-33, y5 - 13.5, f"N20 as drawn: gearbox 9, can 15 including the black end cap, boss 1.2, terminals 2.5 "
                            f"beyond the can. The M3 leadscrew ({L:.0f} mm assumed) leaves the gearbox directly;\n"
                            "the brass nut rides on it inside the rod's carrier. Nothing sits between gearbox and nut.",
            fontsize=8.8, color=MUTED, va="top")
    dim(ax, -26.5, -24.0, y5 + 7.0, "2.5", left=True)
    dim(ax, -24.0, -9.0, y5 + 7.0, "15")
    dim(ax, -9.0, 0.0, y5 + 7.0, "9")
    dim(ax, 0.0, L, y5 + 7.0, f"{L:.0f} (measure yours)")
    dim(ax, -25.2, -24.0, y5 - 7.2, "1.2 boss", above=False)
    ax.plot([0, 0], [y5 - 9.5, (y4 + 11.5) if v4 else (y5 + 10.5)], color=MUTED, lw=0.6, ls=":", zorder=1)
    ax.text(0.4, (y4 + 11.5) if v4 else (y5 + 10.5), "gearbox front face", fontsize=8, color=MUTED, va="top")
    if v4:
        silhouettes(ax, v4, lambda n: n.startswith(V4_DRIVE), 28.2, y4)
        ax.text(-33, y4 + 12.0, "V4 (previous package)", fontsize=11, color=INK, weight="bold")
        dim(ax, -25.2, -24.0, y4 - 8.6, "+1.2 extra rear cap (the 15 already includes the end cap)", RED, above=False)
        dim(ax, 0.0, 41.2, y4 + 8.0, "41 mm of added drive train: 8 mm D-shaft, Ø9 × 20 coupler, 624 bearing, "
                                     "washers, 4 lock nuts", RED)
        ax.text(42.5, y4 - 5.5, "separate M4 screw and nut start here", fontsize=8.5, color=RED)
    ax.set_xlim(-34, 104)
    ax.set_ylim(-17, (y4 + 15) if v4 else 14)
    out = ROOT / "images" / "core_part_check.png"
    fig.savefig(out, facecolor="white")
    print(out)


if __name__ == "__main__":
    main()

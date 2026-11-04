"""Trace boom, stick and bucket side outlines from the Cat 320 render into link frames.
Writes references/cat320_traced.json and images/trace_check.png (overlay for review)."""
import json
import numpy as np
from PIL import Image
from scipy import ndimage
import contourpy
from shapely.geometry import Polygon, MultiPolygon
from matplotlib.path import Path as MPath
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import reference_cat as rc

IMG = rc.REF / 'cat320_view_018.jpg'
px = rc.RENDER_PX

# hand-set regions (image px) that separate each part from the machine body, cab and each other
REGIONS = dict(
    boom=[(520, 748), (600, 535), (690, 425), (795, 362), (1100, 314), (1266, 316), (1266, 418), (1200, 418),
          (900, 492), (760, 522), (665, 632), (607, 770), (532, 770)],
    stick=[(1262, 218), (1342, 218), (1408, 388), (1384, 560), (1374, 690), (1372, 800), (1328, 800), (1318, 690),
           (1262, 420)],
    bucket=[(1160, 1015), (1495, 1015), (1495, 832), (1446, 836), (1392, 846), (1340, 850), (1300, 846),
            (1236, 846), (1160, 930)],
)


def yellow_mask(im):
    f = im.astype(float) / 255
    mx, mn = f.max(-1), f.min(-1)
    s = (mx - mn) / np.maximum(mx, 1e-6)
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    h = np.zeros_like(mx)
    d = mx - mn + 1e-9
    isr = (mx == r) & (mx > mn)
    h[isr] = ((60 * (g - b) / d) % 360)[isr]
    isg = (mx == g) & (mx > mn) & ~isr
    h[isg] = (60 * (b - r) / d + 120)[isg]
    return (h > 25) & (h < 60) & (s > 0.35) & (mx > 0.25)


def region_mask(shape, poly):
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    return MPath(poly).contains_points(np.stack([xx.ravel() + 0.5, yy.ravel() + 0.5], 1)).reshape(shape)


def outline(mask):
    lab, n = ndimage.label(mask)
    if n == 0:
        return None
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    m = ndimage.binary_fill_holes(lab == (1 + int(np.argmax(sizes))))
    sm = ndimage.gaussian_filter(m.astype(float), 1.2)
    lines = contourpy.contour_generator(z=sm).lines(0.5)
    best = max(lines, key=len)
    poly = Polygon(best).buffer(0)
    if isinstance(poly, MultiPolygon):
        poly = max(poly.geoms, key=lambda g: g.area)
    return poly.simplify(0.8)


def main():
    im = np.asarray(Image.open(IMG).convert('RGB'))
    y = yellow_mask(im)
    y = ndimage.binary_closing(y, structure=np.ones((9, 9)))           # bridge the lift-cylinder rod and decals
    y = ndimage.binary_opening(y, structure=np.ones((5, 5)))           # drop thin pipes and rails
    out = {}
    polys = {}
    for part, reg in REGIONS.items():
        p = outline(y & region_mask(y.shape, reg))
        polys[part] = p
        xy = np.asarray(p.exterior.coords)
        if part == 'boom':
            loc = rc.px_to_frame(xy, px['O'], px['E'], rc.BOOM)
        elif part == 'stick':
            loc = rc.px_to_frame(xy, px['E'], px['Hs'], rc.STICK)
        else:
            loc = rc.px_to_frame(xy, px['Hb'], px['T'], rc.TIP_R)
        out[part] = np.round(loc, 2).tolist()
    pins = {}
    for k, (a, b, L) in dict(boom=('O', 'E', rc.BOOM), stick=('E', 'Hs', rc.STICK)).items():
        names = dict(boom=['B'], stick=['D', 'J', 'R'])[k]
        for nm in names:
            pins[f'{nm}_{k}'] = np.round(rc.px_to_frame([px[nm]], px[a], px[b], L)[0], 2).tolist()
    meta = dict(source='references/cat320_view_018.jpg (Caterpillar 320 side render, (c) Caterpillar)',
                method='HSV yellow mask, closing 9 px, opening 5 px, region masks, 0.5 contour; near-side pins',
                note='outlines include slight perspective (far side shifted toward the image centre); use as '
                     'proportions, not as exact plate edges. Bucket traced below the quick coupler.',
                frames='boom: O->E = 380; stick: E->H = 193.33; bucket: Hb->T = 104.67 (x along, z CCW)',
                render_px=px, render_pins_in_frames=pins,
                patent_pins={k: np.round(v, 2).tolist() for k, v in rc.REF_PINS.items()})
    (rc.REF / 'cat320_traced.json').write_text(json.dumps(dict(meta=meta, **out), indent=1))
    # overlay for review
    fig, ax = plt.subplots(figsize=(10, 8.2), dpi=120)
    ax.imshow(im[180:1030, 480:1520], extent=(480, 1520, 1030, 180))
    for part, p in polys.items():
        xy = np.asarray(p.exterior.coords)
        ax.plot(xy[:, 0], xy[:, 1], lw=1.2, color=dict(boom='#2a78d6', stick='#eb6834', bucket='#1baf7a')[part])
        r = np.asarray(REGIONS[part] + [REGIONS[part][0]])
        ax.plot(r[:, 0], r[:, 1], lw=0.5, ls='--', color='k')
    for k, (xx, yy) in px.items():
        ax.plot(xx, yy, 'r+', ms=8)
        ax.text(xx + 5, yy - 5, k, color='r', fontsize=8)
    ax.set_xlim(480, 1520)
    ax.set_ylim(1030, 180)
    ax.set_title('Traced outlines (blue boom, orange stick, green bucket) and pins on the Cat 320 render')
    fig.savefig(rc.ROOT / 'images' / 'trace_check.png', bbox_inches='tight')
    print({k: len(v) for k, v in out.items()}, pins)


if __name__ == '__main__':
    main()

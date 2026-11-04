"""Minimal drafting kit on matplotlib: A3 sheets in millimetres, scaled views, dimensions,
title block and tables. Paper units are mm; every view maps model mm -> paper mm."""
import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch, Rectangle, Circle, Arc
from matplotlib.path import Path
from shapely import affinity
from shapely.geometry import Polygon, MultiPolygon, GeometryCollection, LineString, MultiLineString

W, H = 420.0, 297.0
INK, INK2, MUTED, GRIDC = '#1d1f21', '#4b5056', '#8a9096', '#d9dcdf'
COL = dict(struct='#f5d47c', struct2='#ebc25e', bucket='#f7dc8e', act='#ef9457', cap='#5d646c', rod='#d3d9de',
           steel='#a9b1b9', link='#737a82', base='#5c646d', ghost='#cfd5da', ref='#7d93a8', cut='#ffffff')
FS = dict(title=12.5, h=8.6, n=6.8, s=6.0, xs=5.2)
LWT = dict(thick=0.85, thin=0.45, dim=0.35, cl=0.35)
plt.rcParams['hatch.linewidth'] = 0.35
plt.rcParams['font.family'] = 'DejaVu Sans'
CENTER = (0, (9, 2.2, 1.6, 2.2))
DASH = (0, (3.5, 2))


def polys(g):
    if g is None or g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    if isinstance(g, (MultiPolygon, GeometryCollection)):
        out = []
        for x in g.geoms:
            out += polys(x)
        return out
    return []


class Sheet:
    def __init__(self, number, total, title, subtitle, scale_text, status='DESIGN PROPOSAL - FOR REVIEW', rev='Concept C1'):
        self.fig = plt.figure(figsize=(W / 25.4, H / 25.4))
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        ax = self.ax
        ax.set_xlim(0, W)
        ax.set_ylim(0, H)
        ax.set_aspect('equal')
        ax.axis('off')
        ax.add_patch(Rectangle((10, 5), W - 15, H - 10, fill=False, lw=1.1, ec=INK, zorder=50))
        self._title_block(number, total, title, subtitle, scale_text, status, rev)

    def _title_block(self, number, total, title, subtitle, scale_text, status, rev):
        x0, y0, w, h = W - 5 - 182, 5, 182, 30
        ax = self.ax
        ax.add_patch(Rectangle((x0, y0), w, h, fill=True, fc='white', lw=0.9, ec=INK, zorder=40))
        for yy in (y0 + 10, y0 + 20):
            ax.plot([x0, x0 + w], [yy, yy], lw=0.5, color=INK, zorder=41)
        for xx in (x0 + 112, x0 + 146):
            ax.plot([xx, xx], [y0, y0 + 20], lw=0.5, color=INK, zorder=41)
        t = lambda x, y, s, **k: ax.text(x, y, s, zorder=42, **({'color': INK} | k))
        t(x0 + 2, y0 + 23.2, 'R12 excavator arm  -  ' + title, fontsize=FS['h'] + 0.6, weight='bold')
        t(x0 + 2, y0 + 13.4, subtitle, fontsize=FS['s'])
        t(x0 + 2, y0 + 3.6, 'n20-leadscrew-cylinder  |  all four drives V6-U60  |  units mm, angles deg', fontsize=FS['xs'])
        t(x0 + 114, y0 + 13.4, 'Scale', fontsize=FS['xs'], color=INK2)
        t(x0 + 114, y0 + 3.6, scale_text, fontsize=FS['s'])
        t(x0 + 148, y0 + 13.4, 'Sheet', fontsize=FS['xs'], color=INK2)
        t(x0 + 148, y0 + 3.6, f'{number} / {total}', fontsize=FS['s'], weight='bold')
        t(x0 + 166, y0 + 13.4, '2026-11-03', fontsize=FS['xs'], color=INK2)
        t(x0 + 160, y0 + 3.6, rev, fontsize=FS['s'])
        ax.text(14, H - 11, status, fontsize=FS['s'], color='#a14b16', weight='bold', zorder=42)

    def text(self, x, y, s, size=None, **kw):
        kw.setdefault('color', INK)
        kw.setdefault('zorder', 30)
        return self.ax.text(x, y, s, fontsize=size or FS['n'], **kw)

    def heading(self, x, y, s):
        self.ax.text(x, y, s, fontsize=FS['h'], weight='bold', color=INK, zorder=30)

    def notes(self, x, y, lines, size=None, gap=3.4, width=None):
        size = size or FS['s']
        for i, s in enumerate(lines):
            self.ax.text(x, y - i * gap, s, fontsize=size, color=INK, zorder=30, va='top')
        return y - len(lines) * gap

    def table(self, x, y, widths, rows, size=None, rh=4.0, header=True, align=None):
        """Top-left at (x, y). Returns bottom y."""
        size = size or FS['s']
        ax = self.ax
        n = len(rows)
        tw = sum(widths)
        ax.add_patch(Rectangle((x, y - n * rh), tw, n * rh, fill=False, lw=0.5, ec=INK, zorder=31))
        for i in range(1, n):
            ax.plot([x, x + tw], [y - i * rh] * 2, lw=0.6 if (header and i == 1) else 0.25,
                    color=INK if (header and i == 1) else MUTED, zorder=31)
        cx = x
        for j, wd in enumerate(widths):
            if j:
                ax.plot([cx, cx], [y, y - n * rh], lw=0.25, color=MUTED, zorder=31)
            for i, r in enumerate(rows):
                if j < len(r):
                    a = (align[j] if align else ('left' if j == 0 else 'right'))
                    tx = cx + 1.2 if a == 'left' else (cx + wd - 1.2 if a == 'right' else cx + wd / 2)
                    ax.text(tx, y - (i + 0.72) * rh, str(r[j]), fontsize=size, ha=a,
                            weight='bold' if (header and i == 0) else 'normal', color=INK, zorder=32)
            cx += wd
        return y - n * rh

    def chart(self, x, y, w, h):
        a = self.fig.add_axes([x / W, y / H, w / W, h / H])
        for s in ('top', 'right'):
            a.spines[s].set_visible(False)
        for s in ('left', 'bottom'):
            a.spines[s].set_color(MUTED)
            a.spines[s].set_linewidth(0.5)
        a.tick_params(labelsize=FS['xs'], colors=INK2, width=0.4, length=2)
        a.grid(True, color=GRIDC, lw=0.4)
        a.set_axisbelow(True)
        return a

    def save(self, pdf, png=None, dpi=170):
        pdf.savefig(self.fig)
        if png:
            self.fig.savefig(png, dpi=dpi)
        plt.close(self.fig)


class View:
    """Model (mm) -> paper (mm): paper = (x0, y0) + k * R(rot) (p - origin)."""

    def __init__(self, sheet, x0, y0, k, origin=(0.0, 0.0), rot=0.0, label=None, label_xy=None):
        self.s, self.ax = sheet, sheet.ax
        self.x0, self.y0, self.k = x0, y0, k
        self.o = np.asarray(origin, float)
        self.r = math.radians(rot)
        if label:
            lx, ly = label_xy
            self.ax.text(lx, ly, label, fontsize=FS['n'] + 0.4, weight='bold', color=INK, zorder=30)

    def P(self, p):
        p = np.asarray(p, float) - self.o
        c, s = math.cos(self.r), math.sin(self.r)
        q = np.stack([c * p[..., 0] - s * p[..., 1], s * p[..., 0] + c * p[..., 1]], -1)
        return np.array([self.x0, self.y0]) + self.k * q

    def G(self, g):
        g = affinity.translate(g, -self.o[0], -self.o[1])
        g = affinity.rotate(g, math.degrees(self.r), origin=(0, 0))
        g = affinity.scale(g, self.k, self.k, origin=(0, 0))
        return affinity.translate(g, self.x0, self.y0)

    def poly(self, g, fc='none', ec=INK, lw=LWT['thick'], z=5, hatch=None, ls='-', alpha=1.0):
        for p in polys(self.G(g)):
            verts, codes = [], []
            for ring in [p.exterior, *p.interiors]:
                xy = np.asarray(ring.coords)
                verts += xy.tolist()
                codes += [Path.MOVETO] + [Path.LINETO] * (len(xy) - 2) + [Path.CLOSEPOLY]
            self.ax.add_patch(PathPatch(Path(verts, codes), fc=fc, ec=ec, lw=lw, zorder=z, hatch=hatch,
                                        ls=ls, alpha=alpha, joinstyle='round'))

    def line(self, pts, lw=LWT['thin'], color=INK, ls='-', z=6):
        P = self.P(np.asarray(pts, float))
        self.ax.plot(P[:, 0], P[:, 1], lw=lw, color=color, ls=ls, zorder=z, solid_capstyle='round')

    def geomline(self, g, **kw):
        g = self.G(g)
        gs = g.geoms if isinstance(g, MultiLineString) else [g]
        for x in gs:
            xy = np.asarray(x.coords)
            self.ax.plot(xy[:, 0], xy[:, 1], lw=kw.get('lw', LWT['thin']), color=kw.get('color', INK),
                         ls=kw.get('ls', '-'), zorder=kw.get('z', 6))

    def circle(self, c, r, fc='none', ec=INK, lw=LWT['thin'], z=7):
        P = self.P(c)
        self.ax.add_patch(Circle(P, r * self.k, fc=fc, ec=ec, lw=lw, zorder=z))

    def pin(self, c, r, collar=None, z=20, cross=True, label=None, lpos=(2.5, 2.5)):
        P = self.P(c)
        if collar:
            self.ax.add_patch(Circle(P, collar * self.k, fc=COL['steel'], ec=INK, lw=0.45, zorder=z))
        self.ax.add_patch(Circle(P, r * self.k, fc='#e9edf0', ec=INK, lw=0.45, zorder=z + 0.1))
        if cross:
            e = max(r * self.k + 1.4, 2.4)
            self.ax.plot([P[0] - e, P[0] + e], [P[1], P[1]], lw=LWT['cl'], color=INK2, zorder=z + 0.2)
            self.ax.plot([P[0], P[0]], [P[1] - e, P[1] + e], lw=LWT['cl'], color=INK2, zorder=z + 0.2)
        if label:
            self.ax.text(P[0] + lpos[0], P[1] + lpos[1], label, fontsize=FS['s'], weight='bold', color=INK, zorder=z + 1,
                         bbox=dict(boxstyle='round,pad=0.12', fc='white', ec='none', alpha=0.85))

    def centerline(self, p1, p2, ext=0.0, color=INK2):
        p1, p2 = np.asarray(p1, float), np.asarray(p2, float)
        u = (p2 - p1) / np.linalg.norm(p2 - p1)
        self.line([p1 - ext * u, p2 + ext * u], lw=LWT['cl'], color=color, ls=CENTER, z=8)

    def text(self, p, s, dx=0, dy=0, size=None, **kw):
        P = self.P(p)
        kw.setdefault('color', INK)
        kw.setdefault('zorder', 30)
        return self.ax.text(P[0] + dx, P[1] + dy, s, fontsize=size or FS['s'], **kw)

    def balloon(self, p, label, dx, dy, r=2.7):
        P = self.P(p)
        B = P + np.array([dx, dy])
        d = (P - B) / max(np.linalg.norm(P - B), 1e-6)
        self.ax.plot([B[0] + d[0] * r, P[0]], [B[1] + d[1] * r, P[1]], lw=0.4, color=INK, zorder=33)
        self.ax.plot(P[0], P[1], marker='o', ms=1.6, color=INK, zorder=33)
        self.ax.add_patch(Circle(B, r, fc='white', ec=INK, lw=0.6, zorder=34))
        self.ax.text(B[0], B[1] - 0.05, label, fontsize=FS['xs'], ha='center', va='center', weight='bold', zorder=35)

    def leader(self, p, text, dx, dy, size=None, ha=None):
        P = self.P(p)
        B = P + np.array([dx, dy])
        self.ax.plot([P[0], B[0]], [P[1], B[1]], lw=0.4, color=INK, zorder=33)
        self.ax.plot(P[0], P[1], marker='o', ms=1.3, color=INK, zorder=33)
        ha = ha or ('left' if dx >= 0 else 'right')
        self.ax.plot([B[0], B[0] + (3 if ha == 'left' else -3)], [B[1], B[1]], lw=0.4, color=INK, zorder=33)
        self.ax.text(B[0] + (3.6 if ha == 'left' else -3.6), B[1], text, fontsize=size or FS['s'], ha=ha,
                     va='center', zorder=34, color=INK)

    def _arrow(self, a, b):
        self.ax.annotate('', xy=b, xytext=a, zorder=29,
                         arrowprops=dict(arrowstyle='<|-|>', lw=LWT['dim'], color=INK, shrinkA=0, shrinkB=0,
                                         mutation_scale=5.5))

    def dim(self, p1, p2, off, text=None, mode='aligned', fmt='{:.1f}', size=None, tshift=0.0, prefix=''):
        P1, P2 = self.P(p1), self.P(p2)
        q1, q2 = np.asarray(p1, float), np.asarray(p2, float)
        if mode == 'h':
            yl = (max(P1[1], P2[1]) if off > 0 else min(P1[1], P2[1])) + off
            E1, E2 = np.array([P1[0], yl]), np.array([P2[0], yl])
            val = abs(q2[0] - q1[0])
        elif mode == 'v':
            xl = (max(P1[0], P2[0]) if off > 0 else min(P1[0], P2[0])) + off
            E1, E2 = np.array([xl, P1[1]]), np.array([xl, P2[1]])
            val = abs(q2[1] - q1[1])
        else:
            u = (P2 - P1) / np.linalg.norm(P2 - P1)
            n = np.array([-u[1], u[0]])
            E1, E2 = P1 + n * off, P2 + n * off
            val = float(np.linalg.norm(q2 - q1))
        for P, Ep in ((P1, E1), (P2, E2)):
            v = Ep - P
            L = np.linalg.norm(v)
            if L > 0.8:
                u2 = v / L
                self.ax.plot([P[0] + u2[0] * 0.8, Ep[0] + u2[0] * 1.4], [P[1] + u2[1] * 0.8, Ep[1] + u2[1] * 1.4],
                             lw=LWT['dim'], color=INK, zorder=29)
        self._arrow(E1, E2)
        u = (E2 - E1) / max(np.linalg.norm(E2 - E1), 1e-9)
        ang = math.degrees(math.atan2(u[1], u[0]))
        if ang > 90.5 or ang < -89.5:
            ang += 180
            u = -u
        n = np.array([-u[1], u[0]])
        M = (E1 + E2) / 2 + n * 1.1 + u * tshift
        s = text if text is not None else prefix + fmt.format(val)
        self.ax.text(M[0], M[1], s, fontsize=size or FS['s'], rotation=ang, rotation_mode='anchor', ha='center',
                     va='bottom', zorder=30, color=INK, bbox=dict(boxstyle='square,pad=0.05', fc='white', ec='none'))
        return val

    def radius(self, c, r, ang_deg, text, out=6.0, size=None):
        c = np.asarray(c, float)
        a = math.radians(ang_deg)
        p = c + r * np.array([math.cos(a), math.sin(a)])
        P, C = self.P(p), self.P(c)
        u = (P - C) / np.linalg.norm(P - C)
        Q = P + u * out
        self.ax.annotate('', xy=P, xytext=Q, zorder=29,
                         arrowprops=dict(arrowstyle='-|>', lw=LWT['dim'], color=INK, shrinkA=0, shrinkB=0, mutation_scale=5.5))
        ha = 'left' if u[0] >= 0 else 'right'
        self.ax.plot([Q[0], Q[0] + (3 if ha == 'left' else -3)], [Q[1], Q[1]], lw=LWT['dim'], color=INK, zorder=29)
        self.ax.text(Q[0] + (3.3 if ha == 'left' else -3.3), Q[1], text, fontsize=size or FS['s'], ha=ha, va='center',
                     zorder=30, color=INK)

    def angle(self, c, a1, a2, rr, text, size=None):
        C = self.P(c)
        d1 = math.degrees(self.r) + a1
        d2 = math.degrees(self.r) + a2
        lo, hi = min(d1, d2), max(d1, d2)
        self.ax.add_patch(Arc(C, 2 * rr, 2 * rr, theta1=lo, theta2=hi, lw=LWT['dim'], color=INK, zorder=29))
        for a in (lo, hi):
            self.ax.plot([C[0], C[0] + (rr + 1.5) * math.cos(math.radians(a))],
                         [C[1], C[1] + (rr + 1.5) * math.sin(math.radians(a))], lw=LWT['dim'], color=INK2, ls=DASH, zorder=28)
        m = math.radians((lo + hi) / 2)
        self.ax.text(C[0] + (rr + 2.2) * math.cos(m), C[1] + (rr + 2.2) * math.sin(m), text, fontsize=size or FS['s'],
                     ha='center', va='center', zorder=30, color=INK,
                     bbox=dict(boxstyle='square,pad=0.08', fc='white', ec='none'))

    def section_mark(self, p1, p2, label):
        P1, P2 = self.P(p1), self.P(p2)
        self.ax.plot([P1[0], P2[0]], [P1[1], P2[1]], lw=0.4, color=INK, ls=CENTER, zorder=31)
        u = (P2 - P1) / np.linalg.norm(P2 - P1)
        n = np.array([u[1], -u[0]])
        for P in (P1, P2):
            self.ax.plot([P[0], P[0] + n[0] * 3.5], [P[1], P[1] + n[1] * 3.5], lw=0.9, color=INK, zorder=31)
            self.ax.annotate('', xy=P + n * 3.5 + u * 0.0, xytext=P + n * 0.2, zorder=31,
                             arrowprops=dict(arrowstyle='-|>', lw=0.7, color=INK, mutation_scale=6))
            self.ax.text(P[0] - u[0] * 2.2, P[1] - u[1] * 2.2, label, fontsize=FS['n'], weight='bold', ha='center',
                         va='center', zorder=31)

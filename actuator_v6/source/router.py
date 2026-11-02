"""Small two-layer grid router for the end-stop board.

A* on a 0.05 mm grid, 8 directions, vias between layers. Keep-outs come from a distance
transform of the other nets' copper, so a trace of width w keeps the clearance rule to
everything that is already there. The exact check afterwards is board.drc(), on the real
geometry; the router only has to find paths, not prove them.
"""
import heapq
import math
import numpy as np
from scipy.ndimage import distance_transform_edt
from shapely.geometry import LineString, Point
from matplotlib.path import Path as MPath

G = 0.05                                     # grid step, mm
DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]


class Grid:
    def __init__(self, length, width, edge):
        self.nu = int(round(length / G)) + 1
        self.nv = int(round(width / G)) + 1
        self.v0 = -width / 2
        self.length, self.width, self.edge = length, width, edge
        uu = np.arange(self.nu) * G
        vv = self.v0 + np.arange(self.nv) * G
        self.U, self.V = np.meshgrid(uu, vv, indexing="ij")
        self.edge_dist = np.minimum.reduce([self.U, length - self.U, self.V - self.v0, width / 2 - self.V])

    def cell(self, u, v):
        return int(round(u / G)), int(round((v - self.v0) / G))

    def xy(self, i, j):
        return i * G, self.v0 + j * G

    def raster(self, geom):
        """Boolean grid of cells inside a shapely geometry."""
        out = np.zeros((self.nu, self.nv), bool)
        polys = geom.geoms if hasattr(geom, "geoms") else [geom]
        for p in polys:
            if p.is_empty:
                continue
            x0, y0, x1, y1 = p.bounds
            i0, j0 = max(0, int(x0 / G) - 1), max(0, int((y0 - self.v0) / G) - 1)
            i1, j1 = min(self.nu, int(x1 / G) + 2), min(self.nv, int((y1 - self.v0) / G) + 2)
            if i1 <= i0 or j1 <= j0:
                continue
            pts = np.stack([self.U[i0:i1, j0:j1].ravel(), self.V[i0:i1, j0:j1].ravel()], 1)
            inside = MPath(np.asarray(p.exterior.coords)).contains_points(pts, radius=1e-9)
            for hole in p.interiors:
                inside &= ~MPath(np.asarray(hole.coords)).contains_points(pts)
            out[i0:i1, j0:j1] |= inside.reshape(i1 - i0, j1 - j0)
        return out


def route_net(grid, net, terminals, copper, smd_pads, width, rules, layers=("F.Cu", "B.Cu"),
              via_cost=1.2, bottom_cost=0.15, turn_cost=0.08):
    """Connect the terminals (list of shapely pad polygons on F.Cu) of one net.

    copper: {layer: {net: bool grid}} of everything placed so far (updated in place).
    smd_pads: bool grid of all SMD pads except wire pads (no vias there).
    Returns (tracks, vias) for this net.
    """
    clear = rules["clearance"] + 0.06                        # grid margin
    via_r = rules["via_pad"] / 2
    free, via_ok = {}, None
    for layer in layers:
        other = np.zeros((grid.nu, grid.nv), bool)
        for n, g in copper[layer].items():
            if n != net:
                other |= g
        dist = distance_transform_edt(~other) * G if other.any() else np.full(other.shape, 1e9)
        free[layer] = (dist >= clear + width / 2) & (grid.edge_dist >= rules["edge"] + width / 2 + 0.06)
        ok = (dist >= clear + via_r) & (grid.edge_dist >= rules["edge"] + via_r + 0.03)
        via_ok = ok if via_ok is None else via_ok & ok
    pad_dist = distance_transform_edt(~smd_pads) * G
    via_ok &= pad_dist >= via_r + 0.16
    tracks, vias = [], []
    # the first terminal is the tree; connect the others one by one, nearest first
    tree = {layers[0]: grid.raster(terminals[0]), layers[1]: np.zeros((grid.nu, grid.nv), bool)}
    pending = list(terminals[1:])
    while pending:
        cen = [t.centroid for t in pending]
        tree_pts = np.argwhere(tree[layers[0]])
        tu = tree_pts[:, 0] * G
        tv = grid.v0 + tree_pts[:, 1] * G
        k = int(np.argmin([np.min((c.x - tu) ** 2 + (c.y - tv) ** 2) for c in cen]))
        term = pending.pop(k)
        path = astar(grid, term, tree, free, via_ok, layers, via_cost, bottom_cost, turn_cost)
        if path is None:
            raise RuntimeError(f"no route for {net} to pad at {term.centroid.x:.2f},{term.centroid.y:.2f}")
        t, v = path_to_copper(grid, path, net, width, layers)
        tracks += t
        vias += v
        for (n, layer, w, pts) in t:
            geom = LineString(pts).buffer(w / 2) if len(pts) > 1 else Point(pts[0]).buffer(w / 2)
            r = grid.raster(geom)
            tree[layer] |= r
            copper[layer][net] = copper[layer].get(net, np.zeros_like(r)) | r
        for (n, at) in v:
            r = grid.raster(Point(at).buffer(via_r, 24))
            for layer in layers:
                tree[layer] |= r
                copper[layer][net] = copper[layer].get(net, np.zeros_like(r)) | r
        tree[layers[0]] |= grid.raster(term)
    return tracks, vias


def astar(grid, term, tree, free, via_ok, layers, via_cost, bottom_cost, turn_cost):
    start_mask = grid.raster(term)
    start_cells = np.argwhere(start_mask)
    goal = {layers[0]: tree[layers[0]], layers[1]: tree[layers[1]]}
    # heuristic: distance to the nearest goal cell (cheap bound: straight-line to the goal bbox)
    gpts = np.argwhere(goal[layers[0]] | goal[layers[1]])
    gi0, gj0 = gpts.min(0)
    gi1, gj1 = gpts.max(0)

    def h(i, j):
        di = max(gi0 - i, 0, i - gi1)
        dj = max(gj0 - j, 0, j - gj1)
        return G * math.hypot(di, dj)
    best = {}
    heap = []
    for i, j in start_cells:
        s = (0, int(i), int(j), -1)
        best[s] = 0.0
        heapq.heappush(heap, (h(i, j), 0.0, s, None))
    parent = {}
    while heap:
        f, gcost, s, prev = heapq.heappop(heap)
        if best.get(s, 1e18) < gcost - 1e-12:
            continue
        if s in parent:
            continue
        parent[s] = prev
        li, i, j, d = s
        layer = layers[li]
        if goal[layer][i, j] and prev is not None:
            path = []
            while s is not None:
                path.append(s)
                s = parent[s]
            return path[::-1]
        for k, (di, dj) in enumerate(DIRS):
            ni, nj = i + di, j + dj
            if not (0 <= ni < grid.nu and 0 <= nj < grid.nv):
                continue
            inside_start = li == 0 and start_mask[ni, nj]
            if not (free[layer][ni, nj] or goal[layer][ni, nj] or inside_start):
                continue
            step = G * (1.4142 if di and dj else 1.0) * (1 + (bottom_cost if li == 1 else 0))
            if d >= 0 and d != k:
                step += turn_cost
            ns = (li, ni, nj, k)
            ng = gcost + step
            if ng < best.get(ns, 1e18):
                best[ns] = ng
                heapq.heappush(heap, (ng + h(ni, nj), ng, ns, s))
        if via_ok[i, j] and (free[layers[1 - li]][i, j] or goal[layers[1 - li]][i, j]):
            ns = (1 - li, i, j, -1)
            ng = gcost + via_cost
            if ng < best.get(ns, 1e18):
                best[ns] = ng
                heapq.heappush(heap, (ng + h(i, j), ng, ns, s))
    return None


def path_to_copper(grid, path, net, width, layers):
    tracks, vias = [], []
    run = []
    cur = path[0][0]
    for li, i, j, d in path:
        p = grid.xy(i, j)
        if li != cur:
            if len(run) > 1:
                tracks.append((net, layers[cur], width, simplify(run)))
            vias.append((net, p))
            run = [p]
            cur = li
        else:
            run.append(p)
    if len(run) > 1:
        tracks.append((net, layers[cur], width, simplify(run)))
    return tracks, vias


def simplify(pts):
    """Drop points on straight runs."""
    out = [pts[0]]
    for k in range(1, len(pts) - 1):
        a, b, c = out[-1], pts[k], pts[k + 1]
        cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if abs(cross) > 1e-9:
            out.append(b)
    out.append(pts[-1])
    return [(round(x, 3), round(y, 3)) for x, y in out]

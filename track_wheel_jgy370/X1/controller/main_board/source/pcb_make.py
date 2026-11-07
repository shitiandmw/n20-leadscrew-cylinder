"""pcbnew side of build_pcb.py. Runs inside the kicad/kicad:9.0 image; build_pcb.py writes the config.

    python3 pcb_make.py place  CONFIG.json  -> the board, placed and unrouted, plus the Specctra DSN
    python3 pcb_make.py finish CONFIG.json  -> imports the routed session (SES), adds the supply pours
                                               over their straps and the outer ground pours, fills
                                               every zone and saves
"""
import json
import math
import re
import sys

import pcbnew

MM = pcbnew.FromMM


LAYERS = {"F.Cu": pcbnew.F_Cu, "In1.Cu": pcbnew.In1_Cu, "In2.Cu": pcbnew.In2_Cu, "B.Cu": pcbnew.B_Cu,
          "F.SilkS": pcbnew.F_SilkS, "B.SilkS": pcbnew.B_SilkS, "F.Fab": pcbnew.F_Fab, "B.Fab": pcbnew.B_Fab,
          "Edge.Cuts": pcbnew.Edge_Cuts}


def layer(board, name):
    return LAYERS[name]


class Board:
    def __init__(self, cfg, board):
        self.cfg, self.b = cfg, board
        self.ox, self.oy = cfg["origin"]
        self.nets = {}

    def p(self, u, v):
        return pcbnew.VECTOR2I(MM(self.ox + u), MM(self.oy + v))

    def net(self, name):
        if name not in self.nets:
            n = self.b.FindNet(name)
            if n is None:
                n = pcbnew.NETINFO_ITEM(self.b, name)
                self.b.Add(n)
            self.nets[name] = n
        return self.nets[name]

    def polygon(self, zone, pts):
        o = zone.Outline()
        o.NewOutline()
        for u, v in pts:
            q = self.p(u, v)
            o.Append(q.x, q.y)

    def zone(self, z, fill_mode="solid"):
        zn = pcbnew.ZONE(self.b)
        zn.SetLayer(layer(self.b, z["layer"]))
        zn.SetNet(self.net(z["net"]))
        zn.SetAssignedPriority(z["priority"])
        zn.SetLocalClearance(MM(z["clearance"]))
        zn.SetMinThickness(MM(0.2))
        zn.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL if z.get("solid") else pcbnew.ZONE_CONNECTION_THERMAL)
        zn.SetThermalReliefGap(MM(0.3))
        zn.SetThermalReliefSpokeWidth(MM(0.4))
        zn.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        zn.SetZoneName(z.get("name", ""))
        self.polygon(zn, z["poly"])
        self.b.Add(zn)
        return zn

    def keepout(self, k):
        zn = pcbnew.ZONE(self.b)
        zn.SetIsRuleArea(True)
        ls = pcbnew.LSET()
        for name in k["layers"]:
            ls.AddLayer(layer(self.b, name))
        zn.SetLayerSet(ls)
        zn.SetDoNotAllowTracks(True)
        zn.SetDoNotAllowVias(True)
        zn.SetDoNotAllowCopperPour(False)
        zn.SetDoNotAllowPads(False)
        zn.SetDoNotAllowFootprints(False)
        zn.SetZoneName(k["name"])
        n = 32
        self.polygon(zn, [(k["u"] + k["r"] * math.cos(2 * math.pi * i / n), k["v"] + k["r"] * math.sin(2 * math.pi * i / n))
                          for i in range(n)])
        self.b.Add(zn)

    def via(self, net, u, v):
        vi = pcbnew.PCB_VIA(self.b)
        vi.SetViaType(pcbnew.VIATYPE_THROUGH)
        vi.SetPosition(self.p(u, v))
        vi.SetDrill(MM(self.cfg["rules"]["via_drill"]))
        vi.SetWidth(MM(self.cfg["rules"]["via_d"]))
        vi.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        vi.SetNet(self.net(net))
        vi.SetLocked(True)
        self.b.Add(vi)

    def text(self, t):
        tx = pcbnew.PCB_TEXT(self.b)
        tx.SetText(t["text"])
        tx.SetPosition(self.p(t["u"], t["v"]))
        tx.SetLayer(layer(self.b, t["layer"]))
        tx.SetTextSize(pcbnew.VECTOR2I(MM(t["size"]), MM(t["size"])))
        tx.SetTextThickness(MM(t["size"] * 0.15))
        if t.get("rot"):
            tx.SetTextAngleDegrees(t["rot"])
        if t["layer"].startswith("B."):
            tx.SetMirrored(True)
        self.b.Add(tx)


def setup(B):
    b, cfg = B.b, B.cfg
    r = cfg["rules"]
    b.SetCopperLayerCount(4)
    for name in ("In1.Cu", "In2.Cu"):
        b.SetLayerType(layer(b, name), pcbnew.LT_POWER)
    ds = b.GetDesignSettings()
    ds.m_MinClearance = MM(r["clearance"])
    ds.m_TrackMinWidth = MM(r["track_min"])
    ds.m_ViasMinSize = MM(r["via_min_d"])
    ds.m_MinThroughDrill = MM(r["drill_min"])
    ds.m_ViasMinAnnularWidth = MM(r["min_annular"])
    ds.m_HoleClearance = MM(r["hole_clearance"])
    ds.m_HoleToHoleMin = MM(r["hole_to_hole"])
    ds.m_CopperEdgeClearance = MM(r["edge_clearance"])
    ds.m_SilkClearance = MM(r["silk_clearance"])
    ds.SetAuxOrigin(B.p(0, cfg["size"][1]))                 # bottom-left corner: Gerber/drill/CPL origin
    ds.SetGridOrigin(B.p(0, cfg["size"][1]))
    ns = ds.m_NetSettings
    for c in cfg["classes"]:
        nc = ns.GetDefaultNetclass() if c["name"] == "Default" else pcbnew.NETCLASS(c["name"])
        nc.SetTrackWidth(MM(c["width"]))
        nc.SetClearance(MM(c["clearance"]))
        nc.SetViaDiameter(MM(r["via_d"]))
        nc.SetViaDrill(MM(r["via_drill"]))
        if c["name"] != "Default":
            ns.SetNetclass(c["name"], nc)
            for net in c["nets"]:
                ns.SetNetclassPatternAssignment(net, c["name"])
    tb = b.GetTitleBlock()
    tb.SetTitle(cfg["title"])
    tb.SetRevision(cfg["rev"])
    tb.SetDate(cfg["date"])
    tb.SetCompany(cfg["company"])
    tb.SetComment(0, cfg["comment"])


def place(B):
    b, cfg = B.b, B.cfg
    for name in cfg["nets"]:
        B.net(name)
    for part in cfg["parts"]:
        fp = pcbnew.FootprintLoad(cfg["libs"].get(part["lib"], f"/usr/share/kicad/footprints/{part['lib']}.pretty"),
                                  part["fp"])
        assert fp is not None, part
        fp.SetFPID(pcbnew.LIB_ID(part["lib"], part["fp"]))
        fp.SetReference(part["ref"])
        fp.SetValue(part["value"])
        fp.SetPath(pcbnew.KIID_PATH(part["path"]))
        b.Add(fp)
        fp.SetPosition(B.p(part["u"], part["v"]))
        fp.SetOrientationDegrees(part["rot"])
        for k, v in part["fields"].items():
            fp.SetField(k, v)
            f = fp.GetFieldByName(k)
            f.SetVisible(False)
            f.SetLayer(pcbnew.F_Fab)
        ref = fp.Reference()
        ref.SetVisible(part["silk_ref"])
        ref.SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8)))
        ref.SetTextThickness(MM(0.12))
        if part.get("ref_at"):
            ref.SetPosition(B.p(*part["ref_at"]))
            ref.SetTextAngleDegrees(part.get("ref_rot", 0))
        fp.Value().SetVisible(False)
        # test pads and holes are not placed parts; the BOM flag must match the symbol (schematic parity)
        attr = fp.GetAttributes()
        attr = (attr | pcbnew.FP_EXCLUDE_FROM_POS_FILES) if part["no_pos"] else attr
        attr = (attr | pcbnew.FP_EXCLUDE_FROM_BOM) if part["no_bom"] else (attr & ~pcbnew.FP_EXCLUDE_FROM_BOM)
        fp.SetAttributes(attr)
        for pad in fp.Pads():
            net = part["pads"].get(pad.GetNumber())
            if net:
                pad.SetNet(B.net(net))
            if f"{part['ref']}.{pad.GetNumber()}" in cfg.get("solid_pads", []):
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    w, h = cfg["size"]
    edge = pcbnew.PCB_SHAPE(b)
    edge.SetShape(pcbnew.SHAPE_T_RECT)
    edge.SetStart(B.p(0, 0))
    edge.SetEnd(B.p(w, h))
    edge.SetLayer(pcbnew.Edge_Cuts)
    edge.SetWidth(MM(0.1))
    b.Add(edge)
    for z in cfg["zones"]:
        B.zone(z)
    for st in cfg.get("straps", []):
        for a, c in zip(st["pts"], st["pts"][1:]):
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(B.p(*a))
            t.SetEnd(B.p(*c))
            t.SetWidth(MM(st["width"]))
            t.SetLayer(pcbnew.F_Cu)
            t.SetNet(B.net(st["net"]))
            t.SetLocked(True)
            b.Add(t)
    for k in cfg["keepouts"]:
        B.keepout(k)
    for net, u, v in cfg["vias"]:
        B.via(net, u, v)
    for t in cfg["texts"]:
        B.text(t)
    b.SynchronizeNetsAndNetClasses(True)


# ---- plane fan-out ------------------------------------------------------------------------------
# Before routing, every SMD pad of a plane net (GND on inner 1, VBAT and +6V on inner 2) is joined to its
# plane: by a short track to a same-net pad of its own footprint that already reaches the plane (a
# driver's thermal pad with its vias), to a fan-out via already placed within reach, or to a new via
# just outside the pad. The router then only routes signals; the fan-out is locked.
def _pt_seg_d(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def _rect_d(px, py, r):
    x0, y0, x1, y1 = r
    return math.hypot(max(x0 - px, 0.0, px - x1), max(y0 - py, 0.0, py - y1))


def _seg_rect_d(ax, ay, bx, by, r):
    n = max(2, int(math.hypot(bx - ax, by - ay) / 0.05) + 1)
    return min(_rect_d(ax + (bx - ax) * i / (n - 1), ay + (by - ay) * i / (n - 1), r) for i in range(n))


def _in_poly(x, y, pts):
    c = False
    for i in range(len(pts)):
        (x0, y0), (x1, y1) = pts[i - 1], pts[i]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            c = not c
    return c


def _poly_edge_d(x, y, pts):
    return min(_pt_seg_d(x, y, *pts[i - 1], *pts[i]) for i in range(len(pts)))


def fanout(B, nets, only=None, rip=False):
    """Join every SMD pad of `nets` to its plane. Obstacles are read from the board, so this runs before
    routing (VBAT, +6V, and the GND pads in `only`, "REF.PAD") and again after it (the rest of GND, among
    the routed tracks). Pads already joined by a track of their net are left alone.

    With `rip`, the routed (unlocked) tracks and vias are no obstacle: the new via goes where it cuts the
    fewest of them, and those are deleted, for the repair route to put back (mode "finish")."""
    b, cfg = B.b, B.cfg
    r = cfg["rules"]
    fo = cfg["fanout"]
    vr, cl = r["via_d"] / 2, r["clearance"]
    ox, oy = B.ox, B.oy
    W, H = cfg["size"]
    mm = pcbnew.ToMM

    pads = []                                                   # (rect u,v, net, pad, fp ref, is_th)
    # in a fixed order: a saved board lists its footprints by their random ids, and the order decides
    # which of two neighbours gets a new via and which shares it. It is the order of the board place()
    # builds (BOARD.Add puts each new footprint first), so the DSN routed from it stays the same.
    rank = {p["ref"]: i for i, p in enumerate(cfg["parts"])}
    for fp in sorted(b.GetFootprints(), key=lambda f: -rank[f.GetReference()]):
        for pd in fp.Pads():
            bb = pd.GetBoundingBox()
            rect = (mm(bb.GetLeft()) - ox, mm(bb.GetTop()) - oy, mm(bb.GetRight()) - ox, mm(bb.GetBottom()) - oy)
            th = pd.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
            pads.append((rect, pd.GetNetname(), pd, fp.GetReference(), th))
    vias, tracks = [], []                                       # tracks: (u0, v0, u1, v1, half width, net)
    loose = []                                                  # with rip: (item, is via, u0, v0, u1, v1, half width, layer)
    for t in b.GetTracks():
        if rip and not t.IsLocked():
            a, c, isv = t.GetStart(), t.GetEnd(), t.GetClass() == "PCB_VIA"
            loose.append((t, isv, mm(a.x) - ox, mm(a.y) - oy, mm(c.x) - ox, mm(c.y) - oy,
                          mm(t.GetWidth(pcbnew.F_Cu) if isv else t.GetWidth()) / 2, t.GetLayer()))
        elif t.GetClass() == "PCB_VIA":
            q = t.GetPosition()
            vias.append((mm(q.x) - ox, mm(q.y) - oy, t.GetNetname()))
        elif t.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu):
            a, c = t.GetStart(), t.GetEnd()
            tracks.append((mm(a.x) - ox, mm(a.y) - oy, mm(c.x) - ox, mm(c.y) - oy, mm(t.GetWidth()) / 2,
                           t.GetNetname(), t.GetLayer()))
    keep = [(k["u"], k["v"], k["r"]) for k in cfg["keepouts"]]
    rule_polys = []
    for fp in b.GetFootprints():
        for z in fp.Zones():
            if z.GetIsRuleArea():
                o = z.Outline().COutline(0)
                rule_polys.append([(mm(o.CPoint(i).x) - ox, mm(o.CPoint(i).y) - oy) for i in range(o.PointCount())])
    outer = [(z["net"], z["poly"]) for z in cfg.get("late_zones", []) if z["layer"] in ("F.Cu", "B.Cu")]
    planes = {}
    for z in cfg["zones"]:
        if z["layer"] in ("In1.Cu", "In2.Cu"):
            planes.setdefault(z["net"], []).append(z["poly"])

    def via_ok(u, v, net, own, in_pours=False):
        if not (vr + 0.45 <= u <= W - vr - 0.45 and vr + 0.45 <= v <= H - vr - 0.45):
            return False
        for rect, pn, pd, ref, th in pads:
            if pd is own:
                if _rect_d(u, v, rect) < vr + 0.05:
                    return False
            elif pd.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                if _rect_d(u, v, rect) < vr + 1.05:       # the router keeps 1.3 mm about an unplated hole
                    return False
            elif _rect_d(u, v, rect) < vr + (0.1 if pn == net else cl + 0.05):
                return False
        for vu, vv, vn in vias:
            if math.hypot(u - vu, v - vv) < 2 * vr + cl + 0.1:
                return False
        for t in tracks:
            if t[5] != net and _pt_seg_d(u, v, *t[:4]) < vr + t[4] + cl:
                return False
        for ku, kv, kr in keep:
            if math.hypot(u - ku, v - kv) < kr + vr:
                return False
        for poly in rule_polys:
            if _in_poly(u, v, poly) or _poly_edge_d(u, v, poly) < vr + cl + 0.05:
                return False
        for zn, poly in outer:
            if zn != net and not in_pours and (_in_poly(u, v, poly) or _poly_edge_d(u, v, poly) < vr + cl):
                return False
        pl = planes.get(net)
        if pl and not any(_in_poly(u, v, poly) and _poly_edge_d(u, v, poly) > vr + 0.35 for poly in pl):
            return False
        return True

    def crosses_pour(a, c, net):
        """True if the stub a-c runs over another net's outer pour (it would cut the pour)."""
        n = max(2, int(math.hypot(c[0] - a[0], c[1] - a[1]) / 0.1) + 1)
        return any(zn != net and _in_poly(a[0] + (c[0] - a[0]) * i / (n - 1), a[1] + (c[1] - a[1]) * i / (n - 1), poly)
                   for zn, poly in outer for i in range(n))

    def track_ok(a, c, hw, net, own, target=None):
        for rect, pn, pd, ref, th in pads:
            if pd is own or pd is target or pn == net:
                continue
            if _seg_rect_d(a[0], a[1], c[0], c[1], rect) < hw + cl:
                return False
        for vu, vv, vn in vias:
            if vn != net and _pt_seg_d(vu, vv, a[0], a[1], c[0], c[1]) < vr + hw + cl:
                return False
        n = max(2, int(math.hypot(c[0] - a[0], c[1] - a[1]) / 0.05) + 1)
        pts = [(a[0] + (c[0] - a[0]) * i / (n - 1), a[1] + (c[1] - a[1]) * i / (n - 1)) for i in range(n)]
        for t in tracks:
            if t[5] != net and t[6] == pcbnew.F_Cu and min(_pt_seg_d(x, y, *t[:4]) for x, y in pts) < hw + t[4] + cl:
                return False
        return True

    def cut(u, v, a, c, hw):
        """The routed items a new via at (u, v) and its F.Cu stub a-c would touch (rip mode)."""
        n = max(2, int(math.hypot(c[0] - a[0], c[1] - a[1]) / 0.05) + 1)
        pts = [(a[0] + (c[0] - a[0]) * i / (n - 1), a[1] + (c[1] - a[1]) * i / (n - 1)) for i in range(n)]
        out = []
        for it in loose:
            seg, h = it[2:6], it[6]
            if _pt_seg_d(u, v, *seg) < vr + h + cl + 0.02 or ((it[1] or it[7] == pcbnew.F_Cu) and
                                                             min(_pt_seg_d(x, y, *seg) for x, y in pts) < hw + h + cl + 0.02):
                out.append(it)
        return out

    def add_track(a, c, w, net):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(B.p(*a))
        t.SetEnd(B.p(*c))
        t.SetWidth(MM(w))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(B.net(net))
        t.SetLocked(True)
        b.Add(t)
        tracks.append((a[0], a[1], c[0], c[1], w / 2, net, pcbnew.F_Cu))

    stats = {"track to thermal pad": 0, "shared via": 0, "new via": 0, "new via (in another pour)": 0, "failed": []}
    if rip:
        stats["routed items removed"], stats["cut nets"] = 0, []
    th_pads = {(ref, pd.GetNumber(), pn) for rect, pn, pd, ref, th in pads if th}
    todo = [(rect, pn, pd, ref) for rect, pn, pd, ref, th in pads
            if pn in nets and not th and pd.IsOnLayer(pcbnew.F_Cu) and (ref, pd.GetNumber(), pn) not in th_pads
            and (only is None or f"{ref}.{pd.GetNumber()}" in only)]
    stats["on a strap"] = stats["already joined"] = 0
    for rect, net, pd, ref in todo:
        cu, cv = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
        if any(t[5] == net and t[6] == pcbnew.F_Cu and (_rect_d(t[0], t[1], rect) == 0 or _rect_d(t[2], t[3], rect) == 0)
               and t[4] < 0.3 for t in tracks):
            stats["already joined"] += 1        # fanned out before routing (EARLY_FANOUT)
            continue
        if any(t[5] == net and t[6] == pcbnew.F_Cu and t[4] >= 0.3 and _seg_rect_d(t[0], t[1], t[2], t[3], rect) <= t[4]
               for t in tracks):                # straps are the only tracks 0.6 mm or wider at this stage
            stats["on a strap"] += 1            # joined by its strap (and later its pour) to the stitching vias
            continue
        w = fo["width"][net]
        hw = w / 2
        cu, cv = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
        hx, hy = (rect[2] - rect[0]) / 2, (rect[3] - rect[1]) / 2
        # 1. same-footprint pad that reaches the plane through its own vias (thermal pad)
        done = False
        for rect2, pn2, pd2, ref2, th2 in ([] if rip else pads):
            if ref2 == ref and pn2 == net and pd2 is not pd and not th2 and \
                    any(r3 == ref and n3 == net and t3 and _rect_d((rect2[0] + rect2[2]) / 2, (rect2[1] + rect2[3]) / 2, x3) < 3
                        for x3, n3, p3, r3, t3 in pads):
                tu = min(max(cu, rect2[0] + hw), rect2[2] - hw)
                tv = min(max(cv, rect2[1] + hw), rect2[3] - hw)
                if math.hypot(tu - cu, tv - cv) < 2.5 and track_ok((cu, cv), (tu, tv), hw, net, pd, pd2):
                    add_track((cu, cv), (tu, tv), w, net)
                    stats["track to thermal pad"] += 1
                    done = True
                    break
        if done:
            continue
        # 2. a fan-out via of the same net just beside the pad
        near = [] if rip else sorted(((math.hypot(vu - cu, vv - cv), vu, vv) for vu, vv, vn in vias if vn == net
                                      and _rect_d(vu, vv, rect) < 1.3))
        for d, vu, vv in near:
            if track_ok((cu, cv), (vu, vv), hw, net, pd):
                add_track((cu, cv), (vu, vv), w, net)
                stats["shared via"] += 1
                done = True
                break
        if done:
            continue
        # 3. a new via just outside the pad: outward first, then sideways, then inward, then corners
        fu, fv = [mm(c) for c in (pd.GetParent().GetPosition().x, pd.GetParent().GetPosition().y)]
        fu, fv = fu - ox, fv - oy
        du, dv = cu - fu, cv - fv
        prim = (1 if du >= 0 else -1, 0) if abs(du) >= abs(dv) else (0, 1 if dv >= 0 else -1)
        perp = [(prim[1], prim[0]), (-prim[1], -prim[0])]
        dirs = [prim] + perp + [(-prim[0], -prim[1])] + [(prim[0] + q[0], prim[1] + q[1]) for q in perp]
        cands = []
        dirs += [(-prim[0] + q[0], -prim[1] + q[1]) for q in perp]
        for k, (sx, sy) in enumerate(dirs):
            for extra in (0.0, 0.3, 0.6, 1.0, 1.5, 2.0):
                gu = (hx + cl + vr + 0.05 + extra) * sx
                gv = (hy + cl + vr + 0.05 + extra) * sy
                cands.append((cu + gu, cv + gv))
        # last resort: a short stub and via inside another net's outer pour, which then flows around them
        # (a pad inside such a pour gets this; the first pass allows no via or stub over another pour)
        for in_pours in (False, True):
            ok = [(u, v) for u, v in cands if via_ok(u, v, net, pd, in_pours) and track_ok((cu, cv), (u, v), hw, net, pd)
                  and (in_pours or not crosses_pour((cu, cv), (u, v), net))]
            if rip and ok:                                      # the spot that cuts the fewest routed items
                ok = [min(ok, key=lambda q: len(cut(q[0], q[1], (cu, cv), q, hw)))]
            for u, v in ok[:1]:
                if rip:
                    gone = cut(u, v, (cu, cv), (u, v), hw)
                    loose[:] = [it for it in loose if not any(it is g for g in gone)]
                    for it in gone:
                        stats["cut nets"] = sorted(set(stats["cut nets"]) | {it[0].GetNetname()})
                        b.Delete(it[0])
                    stats["routed items removed"] += len(gone)
                B.via(net, u, v)
                vias.append((u, v, net))
                add_track((cu, cv), (u, v), w, net)
                stats["new via (in another pour)" if in_pours else "new via"] += 1
                done = True
            if done:
                break
        if not done:
            stats["failed"].append(f"{ref}.{pd.GetNumber()} {net}")
    return stats


def _blocks(text, head):
    """(start, end) of every balanced s-expression in text that starts with head."""
    out, i = [], text.find(head)
    while i >= 0:
        depth, j = 0, i
        while True:
            ch = text[j]
            if ch == '"':
                j = text.index('"', j + 1)
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out.append((i, j + 1))
        i = text.find(head, j + 1)
    return out


def _keepouts(lines, clearance_um, via_d_um):
    """Specctra keep-outs covering fixed wires and vias (DSN units, um): a wire becomes a polygon around
    its path on its layer, a via an octagon on both routing layers. Each is grown by the clearance."""
    out = []
    for ln in lines:
        m = re.search(r"\(wire \(path (\S+) (\d+)\s+([-\d. ]+)\)", ln)
        if m:
            lay, hw = m[1], int(m[2]) / 2 + clearance_um
            c = [float(x) for x in m[3].split()]
            for (x1, y1), (x2, y2) in zip(zip(c[0::2], c[1::2]), zip(c[2::2], c[3::2])):
                L = math.hypot(x2 - x1, y2 - y1) or 1.0
                ux, uy = (x2 - x1) / L, (y2 - y1) / L
                nx, ny = -uy * hw, ux * hw
                ax, ay, bx, by = x1 - ux * hw, y1 - uy * hw, x2 + ux * hw, y2 + uy * hw
                pts = [(ax + nx, ay + ny), (bx + nx, by + ny), (bx - nx, by - ny), (ax - nx, ay - ny)]
                out.append(f'    (keepout "" (polygon {lay} 0 ' + " ".join(f"{x:.0f} {y:.0f}" for x, y in pts) + "))")
            continue
        m = re.search(r'\(via "[^"]+"\s+(-?[\d.]+) (-?[\d.]+)', ln)
        if m:
            x, y = float(m[1]), float(m[2])
            r = (via_d_um / 2 + clearance_um) / math.cos(math.pi / 8)
            pts = " ".join(f"{x + r * math.cos(math.pi / 8 + k * math.pi / 4):.0f} "
                           f"{y + r * math.sin(math.pi / 8 + k * math.pi / 4):.0f}" for k in range(8))
            out += [f'    (keepout "" (polygon {lay} 0 {pts}))' for lay in ("F.Cu", "B.Cu")]
    return out


def hide_nets(dsn_path, nets, clearance_mm=0.15, via_d_mm=0.45):
    """Remove nets from the router's view: their net entry, plane and fixed wiring go, so their pads are
    plain obstacles. They are joined after routing (fan-out over the pours). Fixed wiring of a hidden net
    (vias placed before routing) stays in the router's view as keep-outs."""
    s = open(dsn_path).read()
    n0 = len(s)
    for net in nets:
        q = f'"{net}"' if any(ch in net for ch in ' /()') else net
        for head in (f"(net {q}\n", f"(plane {q} "):
            for a, e in reversed(_blocks(s, head)):
                s = s[:a] + s[e:]
        fixed = [ln for ln in s.split("\n") if f"(net {q})" in ln]
        s = "\n".join(ln for ln in s.split("\n") if f"(net {q})" not in ln)
        keep = _keepouts(fixed, clearance_mm * 1000, via_d_mm * 1000)
        if keep:
            i = s.index("    (keepout ")                                  # with the other keep-outs, in (structure)
            s = s[:i] + "\n".join(keep) + "\n" + s[i:]
        for a, e in reversed(_blocks(s, "(class ")):
            blk = s[a:e]
            s = s[:a] + re.sub(rf"(?<=\s){re.escape(q)}(?=[\s)])", "", blk) + s[e:]
    open(dsn_path, "w").write(s)
    return n0 - len(s)


def remove_dangling(board, vias=False):
    """Delete unlocked track segments with a free end (router leftovers), repeatedly, since removing one
    can free the next. Locked tracks (straps, fan-out) are never touched. With `vias`, also unlocked vias
    joined on one layer only; run that only with the zones filled, or a via into a plane looks free."""
    kinds = ("PCB_TRACK", "PCB_VIA") if vias else ("PCB_TRACK",)
    n = 0
    for _ in range(20):
        tracks = list(board.GetTracks())          # listed before the connectivity call: the SWIG wrapper
        board.BuildConnectivity()                 # fails to list the tracks again after a removal
        conn = board.GetConnectivity()
        dead = [t for t in tracks if t.GetClass() in kinds and not t.IsLocked()
                and conn.TestTrackEndpointDangling(t, False)]
        del conn
        if not dead:
            break
        for t in dead:
            board.Delete(t)
        n += len(dead)
    return n


def post_fanout(B, cfg):
    post = cfg["fanout"].get("post_nets", [])
    if not post:
        return {}
    st = fanout(B, post)
    print("post-route fan-out: " + ", ".join(f"{k} {v}" for k, v in st.items() if k != "failed") +
          f"; not fanned out: {len(st['failed'])} {st['failed']}")
    return st


def finalize(B, cfg):
    """Clean the router's leftovers, add the outer pours and fill every zone."""
    n = remove_dangling(B.b)
    for z in cfg.get("late_zones", []) + cfg["outer_pours"]:
        B.zone(z)
    pcbnew.ZONE_FILLER(B.b).Fill(B.b.Zones())
    m = remove_dangling(B.b, vias=True)              # vias left on one layer, now that the zones are filled
    if m:
        pcbnew.ZONE_FILLER(B.b).Fill(B.b.Zones())
    pcbnew.SaveBoard(cfg["pcb"], B.b)
    print(f"removed {n} dangling track segments, then {m} dangling vias and tracks; pours added and filled")


def main():
    mode, cfg_path = sys.argv[1], sys.argv[2]
    cfg = json.load(open(cfg_path))
    if mode == "place":
        board = pcbnew.NewBoard(cfg["pcb"])
        B = Board(cfg, board)
        setup(B)
        place(B)
        st = fanout(B, cfg["fanout"]["nets"]) if cfg.get("fanout") else {}
        early = cfg.get("fanout", {}).get("early")
        est = fanout(B, cfg["fanout"]["post_nets"], only=set(early)) if early else {}
        pcbnew.SaveBoard(cfg["pcb"], board)
        assert pcbnew.ExportSpecctraDSN(board, cfg["dsn"]), "DSN export failed"
        cut = hide_nets(cfg["dsn"], cfg.get("router_hidden_nets", []), cfg["rules"]["clearance"], cfg["rules"]["via_d"])
        print(f"placed {len(cfg['parts'])} footprints, {len(cfg['nets'])} nets; DSN written"
              f" (hidden from the router: {cfg.get('router_hidden_nets', [])}, {cut} characters)")
        if st:
            print("fan-out: " + ", ".join(f"{k} {v}" for k, v in st.items() if k != "failed") +
                  f"; not fanned out: {len(st['failed'])} {st['failed']}")
        if est:
            print(f"early ground fan-out ({len(early)} pads): " + ", ".join(f"{k} {v}" for k, v in est.items() if k != "failed")
                  + f"; not fanned out: {len(est['failed'])} {est['failed']}")
    elif mode == "finish":
        # import the routes, then fan GND out among them. A ground pad the routes boxed in still gets its
        # via: the routed tracks in its way are removed, and a short repair route (mode "repair") puts
        # them back around it.
        board = pcbnew.LoadBoard(cfg["pcb"])
        n_before = sum(1 for t in board.GetTracks() if t.GetClass() == "PCB_VIA")
        assert pcbnew.ImportSpecctraSES(board, cfg["ses"]), "SES import failed"
        B = Board(cfg, board)
        tracks = [t for t in board.GetTracks()]
        nv = sum(1 for t in tracks if t.GetClass() == "PCB_VIA")
        print(f"routed: {len(tracks) - nv} track segments, {nv} vias (before import: {n_before})")
        st = post_fanout(B, cfg)
        if st and st["failed"] and cfg.get("repair_dsn"):
            boxed = {f.split()[0] for f in st["failed"]}
            rs = fanout(B, cfg["fanout"]["post_nets"], only=boxed, rip=True)
            print("rip-up fan-out: " + ", ".join(f"{k} {v}" for k, v in rs.items() if k != "failed") +
                  f"; not fanned out: {len(rs['failed'])} {rs['failed']}")
            # A local repair route: every routed track is locked except the cut nets (the router may
            # redraw them whole; a cut net held in place elsewhere may be left no way back) and those
            # within REPAIR_RADIUS of a boxed-in pad, which it may move to make room. Locked tracks are
            # kept by the session import (they are exported as fixed and are not in the session). GND is
            # hidden again: its new vias and stubs are keep-outs.
            centres = []
            for f in st["failed"]:
                ref, num = f.split()[0].split(".")
                pd = [q for q in board.FindFootprintByReference(ref).Pads() if q.GetNumber() == num][0]
                centres.append((pcbnew.ToMM(pd.GetPosition().x), pcbnew.ToMM(pd.GetPosition().y)))
            r, held = cfg["repair_radius"], []
            for t in list(board.GetTracks()):
                if t.IsLocked() or t.GetNetname() in rs["cut nets"]:
                    continue
                a, e = t.GetStart(), t.GetEnd()
                ax, ay, ex, ey = (pcbnew.ToMM(v) for v in (a.x, a.y, e.x, e.y))
                if all(_pt_seg_d(cx, cy, ax, ay, ex, ey) >= r for cx, cy in centres):
                    t.SetLocked(True)
                    held.append(t.m_Uuid.AsString())
            json.dump(held, open(cfg["repair_held"], "w"))
            pcbnew.SaveBoard(cfg["pcb"], board)
            assert pcbnew.ExportSpecctraDSN(board, cfg["repair_dsn"]), "repair DSN export failed"
            hide_nets(cfg["repair_dsn"], cfg.get("router_hidden_nets", []), cfg["rules"]["clearance"], cfg["rules"]["via_d"])
            free = sum(1 for t in board.GetTracks() if not t.IsLocked())
            print(f"repair route needed for {len(st['failed'])} pads; {free} routed items left free"
                  f" (the cut nets, and within {r} mm of the pads)")
            return
        finalize(B, cfg)
    elif mode == "repair":
        board = pcbnew.LoadBoard(cfg["pcb"])
        assert pcbnew.ImportSpecctraSES(board, cfg["repair_ses"]), "repair SES import failed"
        held = set(json.load(open(cfg["repair_held"])))
        for t in board.GetTracks():                # locked only for the repair: unlock again
            if t.m_Uuid.AsString() in held:
                t.SetLocked(False)
        B = Board(cfg, board)
        post_fanout(B, cfg)
        finalize(B, cfg)
    else:
        sys.exit(f"unknown mode {mode}")


if __name__ == "__main__":
    main()

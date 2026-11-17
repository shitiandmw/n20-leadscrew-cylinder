"""Build the X1 main board PCB with KiCad 9 and Freerouting, both in Docker.

1. footprints.py writes the project footprint library;
2. KiCad exports the schematic's netlist: the board takes its net names and symbol links from it,
   so the board matches the schematic (checked by DRC schematic parity in check_pcb.py);
3. pcb_make.py places the footprints at the layout.py positions, draws the inner planes, keep-outs
   and the supply straps, fans every plane pad out to its plane, and exports a Specctra DSN;
4. Freerouting routes the DSN (no network access; the container runs with --network none);
5. pcb_make.py imports the routes and fans the ground pads out among them; a ground pad the routes
   boxed in gets its via anyway, and a short repair route moves the tracks it cut around it;
6. pcb_make.py removes the router's leftover track ends, adds the supply pours over their straps and
   the outer ground pours, and fills every zone.

Writes kicad/X1_main.kicad_pcb and the board rules and net classes into kicad/X1_main.kicad_pro.

    python build_pcb.py                  rebuild from the saved session kicad/X1_main.ses (or route if none)
    python build_pcb.py --reroute        route again (--minutes N, default 40)
    python build_pcb.py --ses FILE       import a session routed elsewhere
    python build_pcb.py --no-route       placement only; --no-install leaves kicad/ untouched
    python build_pcb.py --keep-routes REASON
                                         import both saved sessions although the DSNs changed, and record the new
                                         hashes with REASON: only for a change that keeps every pad where it was
                                         (2026-11-14: the inboard headers' footprints, swapped for top-entry ones
                                         with the same pads)
"""
import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import footprints
import freerouting_patch
import layout as LY
import netlist as NL
import sexp

HERE = Path(__file__).resolve().parent
BOARD = HERE.parent
KDIR = BOARD / "kicad"
PROJECT = "X1_main"
REPAIR = "X1_main_repair"      # the short repair route for ground pads the main route boxed in
REPAIR_MINUTES = 6
REPAIR_RADIUS = 3.0            # mm about each boxed-in pad: routed tracks there may move, all others are held
KICAD = "kicad/kicad:9.0"
# Freerouting 2.1.0 routes this board better than 2.5.0 (11 unrouted against 44 after 25 minutes on the
# same design). Its command line ignores the pass limit, so the run is ended by the job timeout; the
# patched jar then writes the session (freerouting_patch.py).
FREEROUTING = freerouting_patch.FREEROUTING
DATE = "2026-11-14"                     # top-entry inboard headers (rev B amended before ordering; 2026-11-05 before)
SILK_REF = ("J", "U", "SW", "LS", "TP", "L", "Q101", "D102", "C101", "F40")
CONN_LABELS = {  # bottom silkscreen, under each inboard connector (read from below): name, then pins
    "J102": ("TRACKS", "L 1-2  R 3-4"), "J104": ("BOOM L",), "J105": ("BOOM R",), "J106": ("STICK",),
    "J107": ("BUCKET",), "J103": ("SWING",), "J108": ("LAMPS", "+5V 1 2"), "J109": ("EXP", "5V GND TX RX"),
}


def docker(args, home=None, **kw):
    """Run a container as the calling user (the KiCad image's own user is uid 1000 with its library
    tables in /home/kicad; other images get HOME=/tmp)."""
    uid = f"{os.getuid()}:{os.getgid()}"
    cmd = ["docker", "run", "--rm", "--user", uid] + (["-e", f"HOME={home}"] if home else []) + args
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.exit(f"docker failed: {' '.join(cmd)}\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}")
    return r


def kicad_netlist(work):
    docker(["-v", f"{work}:/work", "-w", "/work", KICAD, "kicad-cli", "sch", "export", "netlist", "--format",
            "kicadsexpr", "--output", "/work/sch.net", f"/work/{PROJECT}.kicad_sch"])
    tree = sexp.parse((work / "sch.net").read_text())[0]
    comps = {}
    for c in sexp.find_all(sexp.find(tree, "components"), "comp"):
        ref = sexp.find(c, "ref")[1]
        sp = sexp.find(c, "sheetpath")
        path = sexp.find(sp, "tstamps")[1] + sexp.find(c, "tstamps")[1]
        comps[ref] = dict(value=sexp.find(c, "value")[1], footprint=sexp.find(c, "footprint")[1], path=path)
    pad_net, nets = {}, {}
    for n in sexp.find_all(sexp.find(tree, "nets"), "net"):
        name = sexp.find(n, "name")[1]
        nodes = [(sexp.find(x, "ref")[1], sexp.find(x, "pin")[1]) for x in sexp.find_all(n, "node")]
        nets[name] = nodes            # includes the single-pin "unconnected-(...)" nets, as in the schematic
        for node in nodes:
            pad_net[node] = name
    return comps, nets, pad_net


def name_map(pad_net):
    """netlist.py net name -> KiCad net name (by connectivity)."""
    out = {}
    for name, nodes in NL.build().nets().items():
        kn = {pad_net.get(n) for n in nodes}
        assert len(kn) == 1 and None not in kn, (name, kn)
        out[name] = kn.pop()
    return out


def dsn_fingerprint(path):
    """SHA-256 of a DSN exported from a saved board, in a form that does not depend on the order of its
    items. A saved board lists its items by their random ids, so from one build to the next the export
    lists the same nets' pins, and the same wires, in another order, and joins different wire segments
    into one path. Here the pins are sorted, every path is cut into its segments, and the lines sorted."""
    text = re.sub(r"\(pins ([^()]*)\)", lambda m: "(pins " + " ".join(sorted(m[1].split())) + ")", path.read_text())
    out = []
    for ln in text.splitlines():
        ln = ln.strip()
        m = re.match(r"\(wire \(path (\S+) (\S+)\s+([-\d. ]+)\)(.*)$", ln)
        if not m:
            out.append(ln)
            continue
        c = m[3].split()
        pts = list(zip(c[0::2], c[1::2]))
        for a, b in zip(pts, pts[1:]):
            a, b = sorted((a, b))
            out.append(f"(wire (path {m[1]} {m[2]} {' '.join(a)} {' '.join(b)}){m[4]}")
    return hashlib.sha256("\n".join(sorted(out)).encode()).hexdigest()


def config(work, comps, nets, pad_net):
    place, pours, vias = LY.place_all()
    nmap = name_map(pad_net)
    nl = NL.build()
    assert set(comps) == set(nl.parts), set(comps) ^ set(nl.parts)
    parts = []
    for ref, p in nl.parts.items():
        info = nl.info(ref)
        lib, fp = info["footprint"].split(":")
        assert comps[ref]["footprint"] == info["footprint"], (ref, comps[ref]["footprint"])
        u, v, rot = place[ref]
        pads = {pad: pad_net[(ref, pad)] for pad in p["pins"] if (ref, pad) in pad_net}
        fields = {} if not info.get("lcsc") else {"LCSC": info["lcsc"], "MPN": info["mpn"]}
        parts.append(dict(ref=ref, lib=lib, fp=fp, value=comps[ref]["value"], path=comps[ref]["path"], u=u, v=v,
                          rot=rot, pads=pads, fields=fields, no_pos=not info.get("lcsc"), no_bom=p["kind"] == "HOLE",
                          silk_ref=ref.startswith(SILK_REF) and not ref.startswith("TP")))
        if ref in LY.REF_AT:
            du, dv, ang = LY.REF_AT[ref]
            parts[-1].update(ref_at=[u + du, v + dv], ref_rot=ang)
    classes = []
    for name, (w, c, pats) in LY.NETCLASSES.items():
        members = sorted({nmap[n] for n in nmap if pats and any(fnmatch.fnmatchcase(n, pt) for pt in pats)})
        classes.append(dict(name=name, width=w, clearance=c, nets=members))
    allz = [dict(net=nmap[n], layer=lay, priority=pr, poly=poly, clearance=LY.PLANE_CLEARANCE,
                 solid=lay in ("F.Cu", "B.Cu"), name=f"{n} {lay}") for n, lay, pr, poly in LY.PLANES + pours]
    zones = [z for z in allz if z["layer"] not in ("F.Cu", "B.Cu")]          # planes: in the DSN
    late = [z for z in allz if z["layer"] in ("F.Cu", "B.Cu")]               # pours: after routing, over straps
    straps = [dict(net=nmap[n], width=w, pts=pts) for n, w, pts in LY.STRAPS]
    outer = [dict(net=nmap["GND"], layer=lay, priority=0, clearance=LY.PLANE_CLEARANCE, solid=False,
                  poly=[(0, 0), (LY.W, 0), (LY.W, LY.H), (0, LY.H)], name=f"GND {lay}") for lay in ("F.Cu", "B.Cu")]
    keepouts = [dict(name=f"screw head {h}", u=u, v=v, r=LY.HOLE_KEEPOUT_R, layers=["F.Cu", "B.Cu"])
                for h, (u, v) in LY.HOLES.items()]
    texts = []
    for ref, label in CONN_LABELS.items():
        u, v, _ = place[ref]
        n = len([k for k in nl.parts[ref]["pins"]])
        pitch = 2.5 if ref != "J108" and ref != "J109" else 2.0
        uc = u + (n - 1) * pitch / 2
        if len(label) == 1:
            texts.append(dict(text=label[0], u=uc, v=LY.H - 2.2, layer="B.SilkS", size=1.0))
        else:                                   # two lines, so that long labels stay within their slot
            texts.append(dict(text=label[0], u=uc, v=LY.H - 3.6, layer="B.SilkS", size=1.0))
            texts.append(dict(text=label[1], u=uc, v=LY.H - 2.0, layer="B.SilkS", size=0.8))
    texts.append(dict(text=f"X1 MAIN BOARD  REV {NL.REV}  {DATE}", u=48.0, v=20.0, layer="B.SilkS", size=1.5))
    texts.append(dict(text="XT30: 9-12.6 V IN", u=88.0, v=24.0 - 1.5, layer="B.SilkS", size=1.0, rot=90))
    rules = dict(LY.RULES)
    fanout = dict(nets=[nmap[n] for n in LY.FANOUT_WIDTH if n not in LY.ROUTER_HIDDEN],
                  post_nets=[nmap[n] for n in LY.ROUTER_HIDDEN],
                  width={nmap[n]: w for n, w in LY.FANOUT_WIDTH.items()}, early=LY.EARLY_FANOUT)
    return dict(pcb=f"/work/{PROJECT}.kicad_pcb", dsn=f"/work/{PROJECT}.dsn", ses=f"/work/{PROJECT}.ses",
                repair_dsn=f"/work/{REPAIR}.dsn", repair_ses=f"/work/{REPAIR}.ses",
                repair_held=f"/work/{REPAIR}_held.json", repair_radius=REPAIR_RADIUS,
                origin=list(LY.ORIGIN), size=[LY.W, LY.H], libs={"X1_main": f"/work/X1_main.pretty"},
                rules=rules, classes=classes, nets=sorted(nets), parts=parts, zones=zones, late_zones=late,
                straps=straps, outer_pours=outer, router_hidden_nets=[nmap[n] for n in LY.ROUTER_HIDDEN],
                keepouts=keepouts, vias=[[nmap[n], u, v] for n, u, v in vias], texts=texts, fanout=fanout,
                solid_pads=LY.SOLID_PADS,
                title=f"{NL.TITLE}, revision {NL.REV}", rev=NL.REV, date=DATE, company="X1 crawler excavator",
                comment="Generated by source/build_pcb.py from netlist.py and layout.py; do not edit by hand")


def route(work, minutes, stem=PROJECT):
    """Freerouting, no network, for a fixed time. Its own fan-out stays off: pcb_make.py has joined every
    plane pad already. The log streams to freerouting.log in the work folder.

    The stock 2.1.0 command line can hang at its job timeout without writing the session, so this runs
    its jar with that fixed (freerouting_patch.py). The container is still killed if it runs 10 minutes
    past the timeout."""
    jar = freerouting_patch.patched_jar()
    name = f"x1-freerouting-{os.getpid()}"
    cmd = ["docker", "run", "--rm", "--name", name, "--user", f"{os.getuid()}:{os.getgid()}", "-e", "HOME=/tmp",
           "--network", "none", "--hostname", "localhost", "-v", f"{work}:/work", "-v", f"{jar.parent}:/fr:ro",
           FREEROUTING, "java", "-jar", f"/fr/{jar.name}", "-de", f"/work/{stem}.dsn", "-do", f"/work/{stem}.ses",
           "-mt", "1", f"--router.job_timeout={minutes // 60:02d}:{minutes % 60:02d}:00",
           "--router.automatic_neckdown=false",                  # no tracks under the 0.15 mm minimum at pads
           "--gui.enabled=false", "--user_data_path=/tmp/fr"]
    log_path = work / ("freerouting.log" if stem == PROJECT else f"freerouting_{stem}.log")
    print(f"routing for {minutes} min; log: {log_path}")
    with open(log_path, "w") as log:
        pr = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
        try:
            pr.wait(timeout=(minutes + 10) * 60)
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "kill", name], capture_output=True)
            pr.wait()
            sys.exit(f"Freerouting did not stop after its {minutes} min timeout and was killed; see {log_path}")
    tail = [ln for ln in log_path.read_text().splitlines() if "unrouted" in ln.lower()]
    print("\n".join(tail[-4:]))
    if pr.returncode != 0 or not (work / f"{stem}.ses").exists():
        sys.exit(f"Freerouting exited with {pr.returncode} and no session file; see {log_path}")


def main():
    sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-route", action="store_true")
    ap.add_argument("--minutes", type=int, default=40, help="routing time")
    ap.add_argument("--ses", type=Path, help="import this routed session instead of routing (default when routing "
                    "is skipped: kicad/X1_main.ses, the session the board was built from)")
    ap.add_argument("--reroute", action="store_true", help="route again even if kicad/X1_main.ses exists")
    ap.add_argument("--no-install", action="store_true", help="leave the result in the work folder only")
    ap.add_argument("--keep-routes", metavar="REASON", help="import both saved sessions unchanged although the DSNs "
                    "changed, and record REASON with the new hashes: only when every pad stays where it was")
    a = ap.parse_args()
    saved, record = KDIR / f"{PROJECT}.ses", KDIR / f"{PROJECT}_route.json"
    saved_repair = KDIR / f"{REPAIR}.ses"
    routed_repair = False
    reuse = a.ses is None and saved.exists() and record.exists() and not a.reroute and not a.no_route
    if reuse:
        a.ses = saved
    footprints.main()
    work = Path(tempfile.mkdtemp(prefix="x1pcb-"))
    for f in KDIR.iterdir():
        if f.is_dir():
            shutil.copytree(f, work / f.name)
        elif not f.name.endswith((".kicad_pcb", ".kicad_prl", ".ses")):
            shutil.copy(f, work / f.name)
    comps, nets, pad_net = kicad_netlist(work)
    cfg = config(work, comps, nets, pad_net)
    (work / "config.json").write_text(json.dumps(cfg, indent=1))
    src = ["-v", f"{work}:/work", "-v", f"{HERE}:/src:ro", "-w", "/work", KICAD, "python3"]
    print(docker(src + ["/src/pcb_make.py", "place", "/work/config.json"]).stdout.strip())
    dsn_hash = hashlib.sha256((work / f"{PROJECT}.dsn").read_bytes()).hexdigest()
    if a.keep_routes and not reuse:
        sys.exit("--keep-routes needs the saved sessions and their record, and no --ses / --reroute / --no-route")
    if reuse and json.loads(record.read_text())["dsn_sha256"] != dsn_hash and not a.keep_routes:
        sys.exit(f"the placement changed since {saved.name} was routed (the DSN differs): run with --reroute")
    if not a.no_route:
        if a.ses:
            shutil.copy(a.ses, work / f"{PROJECT}.ses")
            print(f"session: {a.ses}")
        else:
            route(work, a.minutes)
        print(docker(src + ["/src/pcb_make.py", "finish", "/work/config.json"]).stdout.strip())
        rdsn = work / f"{REPAIR}.dsn"
        if rdsn.exists():
            repair_hash = dsn_fingerprint(rdsn)
            rec = json.loads(record.read_text()) if reuse else {}
            if reuse and (rec.get("repair_dsn_sha256") == repair_hash or a.keep_routes) and saved_repair.exists():
                shutil.copy(saved_repair, work / f"{REPAIR}.ses")
                print(f"repair session: {saved_repair}")
            else:
                route(work, REPAIR_MINUTES, stem=REPAIR)
                routed_repair = True
            print(docker(src + ["/src/pcb_make.py", "repair", "/work/config.json"]).stdout.strip())
    if a.no_install:
        print(f"result left in {work}")
        return
    shutil.copy(work / f"{PROJECT}.kicad_pcb", KDIR / f"{PROJECT}.kicad_pcb")
    shutil.copy(work / f"{PROJECT}.kicad_pro", KDIR / f"{PROJECT}.kicad_pro")
    if not a.no_route:                                           # routing is slow and not repeatable: keep it
        if reuse:
            rec = json.loads(record.read_text())
            if a.keep_routes:
                rec.setdefault("kept", []).append(dict(reason=a.keep_routes, dsn_sha256_before=rec["dsn_sha256"],
                                                       repair_dsn_sha256_before=rec.get("repair_dsn_sha256")))
                rec["dsn_sha256"] = dsn_hash
                if (work / f"{REPAIR}.dsn").exists():
                    rec["repair_dsn_sha256"] = repair_hash
        else:
            shutil.copy(work / f"{PROJECT}.ses", saved)
            rec = dict(dsn_sha256=dsn_hash, session=saved.name,
                       routed_by=str(a.ses.name) if a.ses else f"{FREEROUTING}, {a.minutes} min",
                       note="build_pcb.py imports these sessions while the DSNs it exports still have these hashes")
        if routed_repair:
            shutil.copy(work / f"{REPAIR}.ses", saved_repair)
            rec.update(repair_dsn_sha256=repair_hash, repair_session=saved_repair.name,
                       repair_routed_by=f"{FREEROUTING}, {REPAIR_MINUTES} min")
        elif not (work / f"{REPAIR}.dsn").exists():
            for k in ("repair_dsn_sha256", "repair_session", "repair_routed_by"):
                rec.pop(k, None)
            if saved_repair.exists():
                saved_repair.unlink()                            # from an older routing
        record.write_text(json.dumps(rec, indent=1) + "\n")
    print(f"wrote {KDIR / (PROJECT + '.kicad_pcb')}  (work files in {work})")


if __name__ == "__main__":
    main()

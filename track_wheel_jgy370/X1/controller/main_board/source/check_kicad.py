"""Have KiCad 9 check the generated schematic, and compare KiCad's netlist with netlist.py.

Runs kicad-cli in the official kicad/kicad:9.0 Docker image: ERC, netlist export and the PDF.
Writes X1_main_board_<rev>_schematic.pdf and X1_main_board_<rev>_schematic_checks.json next to the
board folder's README. Exit status 1 if anything fails.

    python check_kicad.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import netlist as NL
import sexp

HERE = Path(__file__).resolve().parent
BOARD = HERE.parent
IMAGE = "kicad/kicad:9.0"
STEM = f"X1_main_board_{NL.REV}"
# ERC findings accepted with a reason (type, text in the item) -> reason
ERC_ACCEPTED = {
    ("footprint_link_issues", "LS401"): "custom buzzer footprint lives in the board's footprint library (PCB stage)",
}


def kicad(out):
    cmd = ["docker", "run", "--rm", "-v", f"{BOARD}:/work", "-v", f"{out}:/out", "-w", "/work/kicad", IMAGE, "bash",
           "-c",
           "kicad-cli version && "
           "kicad-cli sch erc --format json --severity-all --output /out/erc.json X1_main.kicad_sch && "
           "kicad-cli sch export netlist --format kicadsexpr --output /out/X1_main.net X1_main.kicad_sch && "
           "kicad-cli sch export pdf --output /out/schematic.pdf X1_main.kicad_sch"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"kicad-cli failed:\n{r.stdout}\n{r.stderr}")
    return r.stdout.splitlines()[0].strip()


def kicad_nets(path):
    tree = sexp.parse(Path(path).read_text())[0]
    comps = {}
    for c in sexp.find_all(sexp.find(tree, "components"), "comp"):
        ref = sexp.find(c, "ref")[1]
        fields = {}
        for f in sexp.walk(c, "field"):
            name = sexp.find(f, "name")
            vals = [v for v in f[1:] if isinstance(v, str)]
            if name and vals:
                fields[name[1]] = vals[-1]
        comps[ref] = dict(value=sexp.find(c, "value")[1], footprint=(sexp.find(c, "footprint") or [None, ""])[1],
                          lcsc=fields.get("LCSC"))
    nets = {}
    for n in sexp.find_all(sexp.find(tree, "nets"), "net"):
        name = sexp.find(n, "name")[1]
        nodes = frozenset((sexp.find(x, "ref")[1], sexp.find(x, "pin")[1]) for x in sexp.find_all(n, "node"))
        if name.startswith("unconnected-"):
            continue
        nets[name.rsplit("/", 1)[-1]] = nodes
    return comps, nets


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        version = kicad(tmp)
        erc = json.loads((tmp / "erc.json").read_text())
        comps, knets = kicad_nets(tmp / "X1_main.net")
        (BOARD / f"{STEM}_schematic.pdf").write_bytes((tmp / "schematic.pdf").read_bytes())

    nl = NL.build()
    want = {net: frozenset(nodes) for net, nodes in ((k, [(r, p) for r, p in v]) for k, v in nl.nets().items())}
    checks = []

    # ERC
    findings, accepted = [], []
    for sh in erc["sheets"]:
        for v in sh["violations"]:
            items = [i["description"] for i in v["items"]]
            key = next((k for k in ERC_ACCEPTED if k[0] == v["type"] and any(k[1] in i for i in items)), None)
            rec = dict(sheet=sh["path"], type=v["type"], severity=v["severity"], items=items)
            if key:
                accepted.append(dict(rec, reason=ERC_ACCEPTED[key]))
            else:
                findings.append(rec)
    checks.append(dict(name="KiCad ERC: no errors or warnings except the accepted ones", ok=not findings,
                       findings=findings, accepted=accepted))

    # Netlist equality, by connectivity: each netlist.py net must be exactly one KiCad net, pin for pin.
    # Nets drawn with labels or power symbols must also carry the same name; nets drawn only with wires
    # get KiCad's automatic names (Net-(...)).
    by_pin = {}
    for kname, nodes in knets.items():
        for node in nodes:
            by_pin[node] = kname
    unmatched, wrong_name, matched = [], [], set()
    for name, nodes in want.items():
        knames = {by_pin.get(n) for n in nodes}
        if len(knames) != 1 or None in knames or knets[next(iter(knames))] != nodes:
            unmatched.append(dict(net=name, kicad={k: sorted(knets[k]) for k in knames if k}, netlist=sorted(nodes)))
            continue
        kname = next(iter(knames))
        matched.add(kname)
        if not kname.startswith("Net-(") and kname != name:
            wrong_name.append((name, kname))
    extra = sorted(k for k in knets if k not in matched)
    named = sum(1 for k in matched if not k.startswith("Net-("))
    checks.append(dict(name="KiCad netlist equals netlist.py, net by net and pin by pin",
                       ok=not (unmatched or wrong_name or extra), nets=len(want), named_in_drawing=named,
                       wired_only=len(matched) - named, unmatched=unmatched, wrong_name=wrong_name, extra=extra))

    # Components: every part present with the footprint and LCSC number from netlist.py
    bad = []
    for ref in nl.parts:
        info = nl.info(ref)
        c = comps.get(ref)
        if c is None:
            if nl.parts[ref]["pins"]:
                bad.append((ref, "missing"))
            continue
        if c["footprint"] != info["footprint"]:
            bad.append((ref, f"footprint {c['footprint']} != {info['footprint']}"))
        if (info.get("lcsc") or None) != c["lcsc"]:
            bad.append((ref, f"LCSC {c['lcsc']} != {info.get('lcsc')}"))
    extra_comps = sorted(set(comps) - set(nl.parts))
    checks.append(dict(name="components, footprints and LCSC numbers match netlist.py", ok=not bad and not extra_comps,
                       parts=len(comps), problems=bad, extra=extra_comps))

    tbd = sorted(r for r in nl.parts if nl.info(r).get("lcsc") == "TBD")
    checks.append(dict(name="every assembled part has a verified LCSC number", ok=not tbd, tbd=tbd))

    report = dict(board=f"{NL.TITLE} rev {NL.REV}", kicad=version, all_pass=all(c["ok"] for c in checks),
                  checks=checks)
    (BOARD / f"{STEM}_schematic_checks.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    for c in checks:
        print(("PASS " if c["ok"] else "FAIL ") + c["name"])
        if not c["ok"]:
            print("     " + json.dumps({k: v for k, v in c.items() if k not in ("name", "ok")}, ensure_ascii=False)[:1500])
    print("all_pass", report["all_pass"])
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())

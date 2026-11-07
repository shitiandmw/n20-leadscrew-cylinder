"""Minimal S-expression reader and writer for KiCad files (symbols, footprints, schematics)."""
import re

_TOKEN = re.compile(r'\s*(?:(\()|(\))|("(?:[^"\\]|\\.)*")|([^\s()"]+))', re.S)


class Sym(str):
    """An unquoted atom (keyword or number), as opposed to a quoted string."""


def parse(text):
    stack, cur = [], []
    pos = 0
    n = len(text)
    while pos < n:
        m = _TOKEN.match(text, pos)
        if not m:
            if text[pos:].strip() == "":
                break
            raise ValueError(f"bad token at {pos}: {text[pos:pos + 40]!r}")
        pos = m.end()
        lp, rp, s, a = m.groups()
        if lp:
            stack.append(cur)
            cur = []
        elif rp:
            done = cur
            cur = stack.pop()
            cur.append(done)
        elif s is not None:
            cur.append(s[1:-1].replace('\\"', '"').replace("\\\\", "\\"))
        elif a is not None:
            cur.append(Sym(a))
    return cur


def dump(x, indent=0):
    """Serialise nested lists; strings are quoted, Sym atoms are bare."""
    if isinstance(x, list):
        if not x:
            return "()"
        inner = [dump(v, indent + 1) for v in x]
        flat = "(" + " ".join(inner) + ")"
        if len(flat) < 100 and "\n" not in flat:
            return flat
        pad = "\n" + "  " * (indent + 1)
        return "(" + inner[0] + "".join(pad + s for s in inner[1:]) + ")"
    if isinstance(x, Sym):
        return str(x)
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, (int, float)):
        return fmt_num(x)
    s = str(x).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{s}"'


def fmt_num(v):
    if isinstance(v, int):
        return str(v)
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def head(x):
    return x[0] if isinstance(x, list) and x else None


def find(x, key):
    """First direct child list whose head is key."""
    for c in x:
        if isinstance(c, list) and c and c[0] == key:
            return c
    return None


def find_all(x, key):
    return [c for c in x if isinstance(c, list) and c and c[0] == key]


def walk(x, key):
    """All nested lists with head key (depth first)."""
    if isinstance(x, list):
        if x and x[0] == key:
            yield x
        for c in x:
            yield from walk(c, key)

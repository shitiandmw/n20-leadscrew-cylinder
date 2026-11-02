"""Exact solid-intersection checks shared by the build and the validation."""
import time
import cadquery as cq


def _one(s):
    vals = s.vals() if hasattr(s, 'vals') else [s]
    return vals[0] if len(vals) == 1 else cq.Compound.makeCompound(vals)


def interference(inst, tol=.01, skip=None, margin=.05):
    """Exact overlap volume (mm^3) of every pair whose boxes touch.

    inst: name -> dict(shape=..., group=..., envelope=optional solid used
    instead of the shape). skip(a, b) -> True drops a pair. Chain-to-chain pairs
    are skipped by default: the Track R4 chain was validated on its own.
    """
    t0 = time.time()
    names = list(inst)
    shp = {n: _one(d.get('envelope', d['shape'])) for n, d in inst.items()}
    bbs = {n: s.BoundingBox() for n, s in shp.items()}
    def chainish(n):
        return inst[n]['group'] == 'track'
    hits, tested = [], 0
    for i, a in enumerate(names):
        A = bbs[a]
        for b in names[i + 1:]:
            if chainish(a) and chainish(b):
                continue
            if skip and skip(a, b):
                continue
            B = bbs[b]
            if (A.xmin > B.xmax + margin or B.xmin > A.xmax + margin or A.ymin > B.ymax + margin or
                    B.ymin > A.ymax + margin or A.zmin > B.zmax + margin or B.zmin > A.zmax + margin):
                continue
            tested += 1
            common = shp[a].intersect(shp[b])
            v = sum(s.Volume() for s in common.Solids()) if common is not None else 0.
            if v > tol:
                hits.append(dict(a=a, b=b, volume_mm3=round(v, 4)))
    return dict(pairs_tested=tested, hits=hits, seconds=round(time.time() - t0, 1))

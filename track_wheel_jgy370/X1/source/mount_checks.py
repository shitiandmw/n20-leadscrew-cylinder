"""Shared exact-geometry helpers for the X1 track connection and J9 track checks.

These are nominal CAD checks: exact solid intersections after a conservative
bounding-box broad phase, and exact OCC boundary distances. They do not
establish printed strength, bolt preload, fatigue life or a payload rating.
"""
import math
import time

import cadquery as cq
from OCP.BRepExtrema import BRepExtrema_DistShapeShape

import x1_parts as X
import tw_checks as checks

P, D, M, tp = X.P9, X.D9, X.M, X.tp
_BOX_CACHE = {}


def volume(shape):
    return sum(s.Volume() for s in X.one(shape).Solids())


def bbox_distance(a, b):
    return math.sqrt(sum(max(getattr(a, f'{k}min')-getattr(b, f'{k}max'),
                             getattr(b, f'{k}min')-getattr(a, f'{k}max'), 0)**2
                         for k in 'xyz'))


def bound(d):
    s = d.get('envelope', d['shape'])
    key = id(s)
    if key not in _BOX_CACHE:
        _BOX_CACHE[key] = (s, X.one(s).BoundingBox())
    return _BOX_CACHE[key][1]


def against(fixed, moving):
    """Exact solid intersections after the shared 0.05 mm box broad phase."""
    def near(a, b):
        return all(getattr(a, f'{k}min') <= getattr(b, f'{k}max')+.05 and
                   getattr(b, f'{k}min') <= getattr(a, f'{k}max')+.05 for k in 'xyz')
    fb = {n: bound(d) for n, d in fixed.items()}
    mb = {n: bound(d) for n, d in moving.items()}
    fixed_names, moving_names = set(), set()
    for a, ba in fb.items():
        for b, bb in mb.items():
            if near(ba, bb):
                fixed_names.add(a)
                moving_names.add(b)
    if not fixed_names:
        return dict(pairs_tested=0, hits=[], seconds=0.0)
    candidates = {n: d for n, d in fixed.items() if n in fixed_names}
    candidates.update({n: d for n, d in moving.items() if n in moving_names})
    return checks.interference(candidates, skip=lambda a, b: (a in moving) == (b in moving))


def tool_check(fixed, shape):
    return against(fixed, {'tool_envelope': dict(shape=shape, group='tool')})


def closest_disjoint(shape, others):
    """Exact whole-shape OCC distance after a fresh solid overlap check.

    SetMultiThread precedes Perform; passing shapes to the constructor would
    start the expensive operation before the setting is applied. Component
    AABB distances provide conservative pruning, and exact point witnesses
    are retained for every tested nearest-distance operation.
    """
    overlap = against(others, {'distance_probe': dict(shape=shape, group='probe')})
    if overlap['hits']:
        return dict(mm=0., overlapping=True, hits=overlap['hits'])
    first = X.one(shape)
    queue = sorted((bbox_distance(first.BoundingBox(), bound(d)), n) for n, d in others.items())
    best, nearest, trials = math.inf, None, []
    for lower, name in queue:
        if lower > best+1e-7:
            break
        began = time.time()
        tool = BRepExtrema_DistShapeShape()
        tool.LoadS1(first.wrapped)
        tool.LoadS2(X.one(others[name]['shape']).wrapped)
        tool.SetMultiThread(True)
        tool.Perform()
        assert tool.IsDone() and tool.NbSolution() > 0, f'Distance failed: {name}'
        value = float(tool.Value())
        assert math.isfinite(value) and value >= 0
        a, b = tool.PointOnShape1(1), tool.PointOnShape2(1)
        pa, pb = [a.X(), a.Y(), a.Z()], [b.X(), b.Y(), b.Z()]
        assert abs(math.dist(pa, pb)-value) < 1e-5
        trials.append(dict(part=name, mm=value, aabb_lower_bound_mm=lower,
                           point_on_first_mm=pa, point_on_second_mm=pb,
                           seconds=round(time.time()-began, 3)))
        if value < best:
            best, nearest = value, name
    return dict(mm=round(best, 5), part=nearest, trials=trials,
                method='OCC BRepExtrema_DistShapeShape, SetMultiThread(True) before Perform; '
                       'fresh non-overlap check and conservative component AABB pruning')


def vehicle(shape, side):
    return (shape if side > 0 else X.mirror_y(shape)).translate((0, side*X.TRACK_Y, 0))


def compound(shapes):
    return cq.Workplane(obj=cq.Compound.makeCompound([X.one(s) for s in shapes]))

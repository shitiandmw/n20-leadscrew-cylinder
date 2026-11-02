"""Exact CAD distance helper used by J8 interface checks."""
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
import tw_parts as p

def distance(a,b):
    d=BRepExtrema_DistShapeShape(p.one(a).wrapped,p.one(b).wrapped)
    d.Perform()
    return d.Value()

"""Shared CadQuery primitives, transforms and mesh export utilities; units mm."""
from pathlib import Path
import json, math, gzip, sys, hashlib, argparse, time
import cadquery as cq
import numpy as np
import trimesh
from shapely.geometry import Point, Polygon, LineString
from shapely.ops import unary_union
from kinematics import *

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parent
YELLOW=(0.90,.57,.045); DARK=(.12,.16,.19); STEEL=(.65,.71,.76); ORANGE=(.93,.42,.09)

def plate(poly,y0,y1):
    if hasattr(poly,'exterior'): pts=list(poly.exterior.coords)[:-1]
    else: pts=poly
    # XZ plane normal is -Y.
    return cq.Workplane('XZ').polyline(pts).close().extrude(float(y1-y0)).translate((0,float(y1),0))

def circle(x,z,r): return Point(x,z).buffer(r,quad_segs=32)

def hull(points,r): return unary_union([circle(*p,r) for p in points]).convex_hull

def ycyl(x,z,r,y0,y1):
    return cq.Workplane('XZ').center(x,z).circle(r).extrude(float(y1-y0)).translate((0,float(y1),0))

def holes(s,points,r):
    for x,z in points:s=s.cut(ycyl(x,z,r,-100,100))
    return s

def box2(x0,x1,z0,z1,y0,y1): return plate([(x0,z0),(x1,z0),(x1,z1),(x0,z1)],y0,y1)

def one(s):
    vals=s.vals();return vals[0] if len(vals)==1 else cq.Compound.makeCompound(vals)

def mesh(s):
    v,f=one(s).tessellate(.08,.15)
    return {'vertices':[[round(p.x,5),round(p.y,5),round(p.z,5)] for p in v], 'triangles':[list(t) for t in f]}

def move(s,origin,angle):
    return s.rotate((0,0,0),(0,1,0),-math.degrees(angle)).translate((float(origin[0]),0,float(origin[1])))

def actmove(s,a,b,stroke=0,moving=False):
    if moving:s=s.translate((0,0,stroke))
    angle=math.atan2(b[1]-a[1],b[0]-a[0])
    return s.translate((0,0,37.5)).rotate((0,0,0),(0,1,0),90-math.degrees(angle)).translate((float(a[0]),0,float(a[1])))

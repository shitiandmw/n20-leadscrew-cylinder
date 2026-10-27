import cadquery as cq
import math

def cylinder(radius, length, z=0):
    return cq.Workplane("XY").circle(radius).extrude(length).translate((0, 0, z))


def box(sx, sy, sz, x=0, y=0, z=0):
    return cq.Workplane("XY").box(sx, sy, sz).translate((x, y, z))


def axial_x(radius, length, x, y, z):
    return cylinder(radius, length).rotate((0, 0, 0), (0, 1, 0), 90).translate((x, y, z))


def hex_z(af, height, z=0, angle=0):
    r = af / math.sqrt(3)
    pts = [(r * math.cos(math.radians(angle + 60 * i)),
            r * math.sin(math.radians(angle + 60 * i))) for i in range(6)]
    return cq.Workplane("XY").polyline(pts).close().extrude(height).translate((0, 0, z))


def hex_x(af, length, x, y, z):
    return hex_z(af, length).rotate((0, 0, 0), (0, 1, 0), 90).translate((x, y, z))


def double_d(diameter, flat_width, length, z=0):
    return cylinder(diameter / 2, length, z).intersect(
        box(flat_width, diameter + 2, length + 2, z=z + length / 2))


def ring(od, id_, length, z):
    return cylinder(od / 2, length, z).cut(cylinder(id_ / 2, length + 0.2, z - 0.1))


def print_orientation(shape, side):
    # x-positive shell: outer flat goes on bed. x-negative shell and rod: opposite.
    q = shape.rotate((0, 0, 0), (0, 1, 0), 90 if side == "+" else -90)
    b = q.val().BoundingBox()
    return q.translate((-b.xmin, -b.ymin, -b.zmin))



def cy(radius, length, x, y, z):
    # Cylinder along +Y starting at y.
    return cylinder(radius, length).rotate((0, 0, 0), (1, 0, 0), -90).translate((x, y, z))


def cone(r1, r2, height, z=0):
    return cq.Workplane(obj=cq.Solid.makeCone(r1, r2, height, cq.Vector(0, 0, z)))


def cx_cone(r1, r2, height, x, y, z):
    return cone(r1, r2, height).rotate((0, 0, 0), (0, 1, 0), 90).translate((x, y, z))


def rr_box(x0, x1, y0, y1, z0, z1, radius):
    # Prism along Z with a rounded-rectangle section; bounds may be asymmetric.
    w, h = x1 - x0, y1 - y0
    solid = cq.Workplane("XY").rect(w, h).extrude(z1 - z0)
    if radius > 0:
        solid = solid.edges("|Z").fillet(radius)
    return solid.translate(((x0 + x1) / 2, (y0 + y1) / 2, z0))


def revolve_profile(points):
    # points are (r, z) pairs of a closed half-section; revolved about Z.
    return cq.Workplane("XZ").polyline(points).close().revolve(360, (0, 0, 0), (0, 1, 0))

"""Draw revision F arm-to-track joint sections from the delivered CAD, rather than a concept sketch."""
from functools import reduce
from pathlib import Path
import hashlib
import json

import cadquery as cq
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.path import Path as PlotPath
from matplotlib.patches import PathPatch
import numpy as np
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
import trimesh

import x1_parts as X
from refresh_revf import part as load_checked_part

INK = '#203a42'
COLORS = {'frame': '#f2c230', 'track': '#8fb4b4', 'housing': '#e7a239', 'hardware': '#66737b'}
_section_meshes = {}


def shape_one(shape):
    return shape.val() if isinstance(shape, cq.Workplane) else shape


def section(shape, origin, normal, axes):
    shape = shape_one(shape)
    key = id(shape)
    if key not in _section_meshes:
        vertices, triangles = shape.tessellate(.06, .16)
        mesh = trimesh.Trimesh(np.array([[v.x, v.y, v.z] for v in vertices]), np.array(triangles), process=True)
        # Retain the source object so its identity cannot be reused in this run.
        _section_meshes[key] = (shape, mesh)
    mesh = _section_meshes[key][1]
    cut = mesh.section(plane_origin=origin, plane_normal=normal)
    if cut is None:
        return None
    polygons = [Polygon(loop[:, axes]).buffer(0) for loop in cut.discrete if len(loop) > 3]
    polygons = [p for p in polygons if p.area > 1e-3]
    return reduce(lambda a, b: a.symmetric_difference(b), polygons) if polygons else None


def fill(ax, geometry, color):
    if geometry is None:
        return
    for polygon in getattr(geometry, 'geoms', [geometry]):
        if polygon.geom_type != 'Polygon':
            continue
        polygon = orient(polygon, sign=1.0)
        vertices, codes = [], []
        for ring in [polygon.exterior, *polygon.interiors]:
            points = list(ring.coords)
            vertices.extend(points)
            codes.extend([PlotPath.MOVETO]+[PlotPath.LINETO]*(len(points)-2)+[PlotPath.CLOSEPOLY])
        # Opposite winding leaves holes transparent, so the screw remains
        # visible through the nut bore when the component sections overlap.
        ax.add_patch(PathPatch(PlotPath(vertices,codes), facecolor=color, edgecolor=INK, lw=.6))


def main():
    sources = [Path(__file__), Path(X.__file__), Path(X.M.__file__), Path(X.P9.__file__),
               Path(__file__).with_name('refresh_revf.py')]
    part_paths = [X.ROOT/'step/X101_X_frame.step', X.ROOT.parent/'J9/step/J901_H_frame.step',
                  X.ROOT.parent/'J9/step/J909_housing.step']
    digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    inputs = {str(p.relative_to(X.REPO)): digest(p) for p in sources+part_paths}
    frame = cq.Workplane(obj=load_checked_part(part_paths[0]))
    track = cq.Workplane(obj=load_checked_part(part_paths[1])).translate((0, X.TRACK_Y, 0))
    housing = cq.Workplane(obj=load_checked_part(part_paths[2])).translate((0, X.TRACK_Y, 0))
    hardware = X.mount_hardware()
    front = [(n, row['shape']) for n, row in hardware.items()
             if shape_one(row['shape']).Center().x > 0 and shape_one(row['shape']).Center().y > 0]
    screws = sorted([(n, s) for n, s in front if 'screw' in n or 'bolt' in n],
                    key=lambda row: shape_one(row[1]).Center().x)
    assert len(screws) == 2, 'Expected one screw on each side of the arm web'
    screw_x = shape_one(screws[0][1]).Center().x
    screw_z = shape_one(screws[0][1]).Center().z
    station_x = max(X.M.STATIONS)
    face_y = X.TRACK_Y+X.M.FACE_Y
    items = [(frame,COLORS['frame']), (track,COLORS['track']), (housing,COLORS['housing'])]
    items += [(s,COLORS['hardware']) for _,s in front]
    print('Sectioning the actual revision F STEP parts', flush=True)
    fig = plt.figure(figsize=(12,8.3), facecolor='white')
    fig.text(.045,.947,'X1 revision F — straight arms seated in the track beam',fontsize=17.5,color=INK,weight='bold')
    fig.text(.045,.909,'Actual CAD sections at the front left joint. Dimensions in mm.',fontsize=10,color=INK)

    def axes(rect, title, xlabel, ylabel, xlim, ylim):
        ax=fig.add_axes(rect)
        ax.set_xlim(*xlim); ax.set_ylim(*ylim); ax.set_aspect('equal')
        ax.set_xlabel(xlabel,fontsize=9,color=INK); ax.set_ylabel(ylabel,fontsize=9,color=INK)
        ax.set_title(title,fontsize=10,loc='left',color=INK)
        ax.grid(color='#dbe2e2',lw=.45); ax.tick_params(labelsize=8,colors=INK)
        return ax

    plan=axes([.055,.49,.41,.33],f'A — Plan through the two screws, Z = {screw_z:g}',
              'Vehicle X','Vehicle Y (inboard → outboard)',
              (station_x-34,station_x+34),(face_y-45,face_y+20))
    for shape,color in items:
        fill(plan,section(shape,[0,0,screw_z],[0,0,1],[0,1]),color)

    centre=axes([.55,.49,.40,.33],f'B — Arm side profile at its centre, X = {station_x:g}',
                'Vehicle Y (inboard → outboard)','Z',
                (face_y-52,face_y+20),(30,88))
    for shape,color in items:
        fill(centre,section(shape,[station_x,0,0],[1,0,0],[1,2]),color)
    centre.annotate(f'{X.M.SEAT_DEPTH:g} mm receiving seat',
                    xy=(face_y-X.M.SEAT_DEPTH/2, X.M.FACE_Z[0]),
                    xytext=(face_y-45, X.M.FACE_Z[0]-13),
                    fontsize=8, color=INK,
                    arrowprops=dict(arrowstyle='->', lw=.8, color=INK))

    side=axes([.055,.12,.24,.28],f'C — Screw axis, X = {screw_x:g}',
              'Vehicle Y','Z',
              (face_y-45,face_y+16),(screw_z-16,screw_z+16))
    for shape,color in items:
        fill(side,section(shape,[screw_x,0,0],[1,0,0],[1,2]),color)
    slot_y = X.TRACK_Y+sum(X.M.SLOT_Y)/2
    across=axes([.33,.12,.17,.28],f'D — Across the arm, Y = {slot_y:g}',
                'Vehicle X','Z',(station_x-22,station_x+22),(50,88))
    for shape,color in items:
        fill(across,section(shape,[0,slot_y,0],[0,1,0],[0,2]),color)

    fig.text(.54,.398,'One straight arm into a plain seat',fontsize=11.5,color=INK,weight='bold')
    notes=[
        f'Each arm stays {X.M.WIDTH:g} mm wide from the root bend to the track plate.',
        f'Its flat end, Z{X.M.FACE_Z[0]:g}–{X.M.FACE_Z[1]:g}, enters a {X.M.SEAT_DEPTH:g} mm deep rectangular seat.',
        f'Two M4 × {X.M.BOLT_L:g} screws pass either side of the {X.M.WEB:g} mm centre web.',
        'Heads and washers sit in side slots; the deck stays closed above.',
        'Plain holes; rear washers and nuts are external, inside the track.',
        'The accepted spring guide and 4.2 mm recoil are retained.',
        'Use the matching revision F X101, J901 and J909 parts.',
        'Printed fit, preload retention and strength need physical tests.',
    ]
    for i,note in enumerate(notes):fig.text(.54,.361-i*.029,note,fontsize=8.9,color=INK)
    fig.text(.055,.067,'Yellow: X101. Blue-green: J901. Orange: J909 housing. Grey: steel hardware. '
                         'Sections use a 0.06 mm tessellation tolerance.',fontsize=8.3,color='#53686c')
    fig.text(.055,.038,'Model coordinates: X forward; Y left; Z up. Right-hand connections are mirrored. '
                         'See ASSEMBLY.md for the fastener and fitting checks.',fontsize=8.3,color='#53686c')
    pdf=X.ROOT/'X1_arc_mount_detail.pdf'; png=X.ROOT/'images/X1_arc_mount_detail.png'
    fig.savefig(pdf); fig.savefig(png,dpi=160); plt.close(fig)
    assert all(digest(X.REPO/name)==expected for name,expected in inputs.items()), 'Drawing inputs changed'
    report=dict(revision='F',inputs=inputs,outputs={str(p.relative_to(X.REPO)):digest(p) for p in (pdf,png)},
                geometry_source='Current STEP exports plus current hardware source',**{'pass':True})
    (X.ROOT/'arc_mount_drawing.json').write_text(json.dumps(report,indent=2)+'\n')
    print(pdf,flush=True)


if __name__ == '__main__':
    main()

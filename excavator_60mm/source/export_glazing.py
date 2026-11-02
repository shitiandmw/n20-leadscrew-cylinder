"""Export actual planar PET panel shapes as STEP and true-size SVG templates."""
import math
import numpy as np
from design import ROOT

def export_glazing(instances):
    import cadquery as cq
    from cad_common import one
    dest=ROOT/'glazing';dest.mkdir(exist_ok=True)
    for name,d in instances.items():
        if d['kind']!='glazing':continue
        cq.exporters.export(d['shape'],str(ROOT/'step'/f'{name}.step'))
        face=max(one(d['shape']).Faces(),key=lambda f:f.Area())
        points=np.array([[v.X,v.Y,v.Z] for v in face.outerWire().Vertices()])
        normal=np.array(face.normalAt().toTuple());u=points[1]-points[0];u=u/np.linalg.norm(u);v=np.cross(normal,u)
        xy=np.column_stack((points@u,points@v));xy-=xy.min(axis=0);centre=xy.mean(axis=0)
        xy=xy[np.argsort(np.arctan2(xy[:,1]-centre[1],xy[:,0]-centre[0]))]
        w,h=xy.max(axis=0);poly=' '.join(f'{x+10:.4f},{y+10:.4f}' for x,y in xy)
        (dest/f'{name}.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w+20:.4f}mm" height="{h+30:.4f}mm" viewBox="0 0 {w+20:.4f} {h+30:.4f}"><polygon points="{poly}" fill="none" stroke="black" stroke-width="0.2"/><text x="5" y="{h+17:.4f}" font-family="sans-serif" font-size="3">{name}</text><text x="5" y="{h+23:.4f}" font-family="sans-serif" font-size="2.5">0.8 mm PET / 100% scale / {w:.2f} x {h:.2f} mm</text></svg>')
    print('Exported four glazing STEP files and 1:1 SVG templates')

if __name__=='__main__':
    from build_vehicle import printable_parts,vehicle_instances
    export_glazing(vehicle_instances(printable_parts()))

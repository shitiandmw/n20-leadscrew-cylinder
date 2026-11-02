"""Export actual profile coordinates for the explanatory side-plate drawings."""
import json
import j8_parts as s
def polygon(p):return dict(outline=list(p.exterior.coords),holes=[list(r.coords) for r in p.interiors])
def main():
    data=dict(inner=polygon(s.inner_profile()),outer=polygon(s.side_profile().difference(s.idler_opening())),axes=s.AXES,ties=s.TIES,
              drive=[s.DX,s.DZ],idler_limits=s.IDLER_LIMITS,plate_thickness_mm=4)
    (s.ROOT/'plate_layout.json').write_text(json.dumps(data,indent=2)+'\n')
if __name__=='__main__':main()

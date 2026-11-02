"""Check that both revised upper rollers actually turn with the free chain."""
import json
from pathlib import Path
import numpy as np
from support_paths import ROOT as J8_ROOT
ROOT=J8_ROOT/'simulation/recomputed_baseline'

def main():
    trace=json.loads((ROOT/'simulation/demo_trace.json').read_text());phases=[]
    for a,b,sign in [(2,5.5,1),(8,11.5,-1)]:
        rows=[r for r in trace if a<=r['t']<=b]
        angles=np.array([r['wheels'] for r in rows]);speed=(angles[-1]-angles[0])/(rows[-1]['t']-rows[0]['t'])
        upper=speed[4:]*15
        phases.append(dict(interval_s=[a,b],all_passive_wheel_mean_rad_s=speed.tolist(),upper_surface_speed_mm_s=upper.tolist(),
                           pass_=bool(np.all(upper*sign>70) and np.all(upper*sign<90))))
    ok=all(r.pop('pass_') for r in phases)
    result=dict(pass_=ok,phases=phases,scope='Both upper rollers turn in both directions in the unloaded simulation. This checks contact-driven rolling, not loaded support strength. The middle lower roller is unloaded and may remain stationary.')
    result['pass']=result.pop('pass_');(ROOT/'simulation/upper_roller_checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2));assert ok

if __name__=='__main__':main()

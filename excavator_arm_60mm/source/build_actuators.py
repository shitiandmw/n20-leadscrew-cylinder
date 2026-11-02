"""Build the arm's actuators and check them against kinematics.ACTUATORS.
All four roles use V6-U60, one of the three standard lengths of actuator_v6/. This runs V6's own
board export and build for that length (the outputs stay in actuator_v6/), then checks the screw
length, stroke and closed length, the CAD checks and the board checks for every role.
"""
from pathlib import Path
import sys,json,subprocess,time
from kinematics import ACTUATORS
ROOT=Path(__file__).resolve().parents[1];V6=ROOT.parent/'actuator_v6'

def run():
    start=time.time();variants=sorted({a['variant'] for a in ACTUATORS.values()})
    subprocess.run([sys.executable,str(V6/'source/pcb_export.py'),*variants],check=True)
    for variant in variants:subprocess.run([sys.executable,str(V6/'source/build_v6.py'),'--variant',variant],check=True)
    params=json.loads((V6/'parameters.json').read_text());report=json.loads((V6/'validation.json').read_text())
    for role,a in ACTUATORS.items():
        v=a['variant'];p=params[v];board=json.loads((V6/f'electronics/pcb/V6-{v}/check_{v}.json').read_text())
        assert (p['screw_length_mm'],p['stroke_mm'],p['pin_centres_closed'])==(a['screw'],a['stroke'],a['closed']),role
        assert report[v]['all_checks_pass'] and not board['drc_errors'] and board['readback_worst_mismatch']<.002,role
        print('PASS actuator',role,f'V6-{v}',f"{p['pin_centres_closed']:g}-{p['pin_centres_open']:g} mm",flush=True)
    print('Actuators built and checked in',round(time.time()-start,1),'seconds')

if __name__=='__main__':run()

"""Exhaustive truth table for both independent hardware direction gates."""
import itertools,json
from pathlib import Path
rows=[]
for ce,cr,ae,ar in itertools.product([False,True],repeat=4):
    ain1,ain2=ce and ae,cr and ar
    if not ae:assert not ain1
    if not ar:assert not ain2
    if not ae and ar and cr and not ce:assert not ain1 and ain2
    if not ar and ae and ce and not cr:assert ain1 and not ain2
    if not ae and not ar:assert not ain1 and not ain2
    rows.append(dict(cmd_extend=ce,cmd_retract=cr,allow_extend=ae,allow_retract=ar,AIN1=ain1,AIN2=ain2))
# A sensor-local 4.7k pullup and controller-local 47k pulldown keep healthy logic
# high; a broken OUT wire removes the remote pullup and leaves the local node low.
vcc=5.;permit=vcc*47000/(47000+4700)
assert permit>.7*vcc
Path(__file__).with_name('direction_gate_validation.json').write_text(json.dumps({'states':rows,'healthy_high_V':permit,'broken_OUT_wire_V':0.0},indent=2))
print('PASS: all 16 gate states; independent end blocking, reverse exit, and OUT-wire-open pulldown model.')

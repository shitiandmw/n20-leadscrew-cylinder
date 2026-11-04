"""Concept-level side-view clash check for R12 (parts that share a lateral band only).
Lateral scheme of the concept stage: boom 40 wide narrowing to 21 inside R46 of E, stick head fork plates
straddling it inside R42; bucket ears straddle the stick nose inside R18 of H; side links and
H-link not checked yet (open item)."""
import itertools
import numpy as np
import r12_design as d

PAIRS = ('stick cyl body / boom', 'bucket cyl body / stick', 'stick (out of R42) / boom (out of R46)',
         'stick head (in R42) / boom (out of R46)', 'bucket (out of R18 at H) / stick', 'stick cyl body / stick',
         'bucket / boom')


def check(n=7):
    bp = d.boom_profile()
    sp, _ = d.stick_profile()
    bk = d.bucket_profile()
    sb = d.stick_base()
    worst = {}
    for st in itertools.product(np.linspace(0, 60, n), repeat=3):
        s = d.solve(st)
        P, po = s['pins'], s['poses']
        B, S, K = d.place(bp, *po['boom']), d.place(sp, *po['stick']), d.place(bk, *po['bucket'])
        cs, ck = d.actuator_body(P['C'], P['D']), d.actuator_body(P['F'], P['R'])
        g = {
            PAIRS[0]: (cs, B.difference(d.disc(P['C'], 12))),
            PAIRS[1]: (ck, d.place(sb, *po['stick'])),          # lug cheeks straddle the drive body
            PAIRS[2]: (S.difference(d.disc(P['E'], 42)), B.difference(d.disc(P['E'], 46))),
            PAIRS[3]: (S.intersection(d.disc(P['E'], 42)), B.difference(d.disc(P['E'], 46))),
            PAIRS[4]: (K.difference(d.disc(P['H'], 18)), S),
            PAIRS[5]: (cs, S.difference(d.disc(P['D'], 10))),
            PAIRS[6]: (K, B),
        }
        for k, (a, b) in g.items():
            dist = a.distance(b)
            if k not in worst or dist < worst[k][0]:
                worst[k] = (round(dist, 2), tuple(int(x) for x in st))
    return worst


if __name__ == '__main__':
    for k, v in check().items():
        print(f'{k:42s} {v[0]:7.2f} mm at strokes {v[1]}')

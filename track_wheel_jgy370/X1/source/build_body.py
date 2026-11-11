"""Build and check the X1 body B1 (three prints, x1_body.py) on the turntable (x1_turntable.py) and the chassis.

Run with the CAD interpreter from this folder:  python build_body.py [stage ...]
Stages (each cached in /tmp/sw-render/body_cache_<hash of the CAD sources>, so a CAD change starts a fresh cache):
  mass        mass properties from the CAD; sizes the steel shot so the upper's CG is on the swing axis (arm stretched);
              reports the lateral CG (rev B: the battery is on the centreline)
              -> ../simulation/body_mass_properties.json (build_turntable.py's 'mass' stage reads it)
  export      ../step/B10x_*.step, ../stl/B10x_*.stl (print orientation), ../step/X1_body_assembly.step, bed fit,
              overhangs that need support, viewer meshes (body_scene.json.gz)
  static      every body solid against the turntable, the ARM60 and each other, at swing 0
  sweep       the body turned every 15° against the chassis and the chassis-side turntable parts
  paths       the battery hatch off (lift); each half off (hatch off, 2 screws out, slide out 10, lift) with the rest in
              place; the counterweight off; the cab interior and operator slid into the left half on the bench
  tools       hex keys down the sleeves, the counterweight L-key, the charge and USB plugs
  clearances  gaps that matter (hood to ARM60, hooks, seam, electronics to the walls, tail radius, ground side)
  final       all of the above -> ../body_validation.json
"""
import json, gzip, math, sys, time
from functools import lru_cache
from pathlib import Path
import numpy as np
import cadquery as cq
import trimesh
from shapely.geometry import box as sbox
import x1_parts as X
import x1_turntable as T
import x1_body as Bd
import board_step as BS
import build_turntable as BT
import tw_checks as checks
import build_track_wheel as export

ROOT, SIM = X.ROOT, X.ROOT / 'simulation'
DENS = BT.DENS
CACHE = Path('/tmp/sw-render') / ('body_cache_' + BT.stamp(*sorted(BT._sources), *sorted((X.ROOT / 'body_concept/source').glob('*.py'))))
STAGES = ('mass', 'export', 'static', 'sweep', 'paths', 'tools', 'clearances', 'final')
WIRING = [('wiring_left_bay', .025, (-90.0, 115.0, 122.0)), ('wiring_right_bay', .015, (-20.0, -115.0, 125.0)),
          ('wiring_hatch_lead', .010, (-110.0, 0.0, 175.0)), ('small_fixings', .010, (-60.0, 0.0, 130.0))]
LATERAL_CG_MAX = 1.0                                   # mm: the user's point 1 (rev B)
BED = 256.0
one, dist, against, tool = BT.one, BT.dist, BT.against, BT.tool


def clip(s, bx):
    """The part of s inside the box bx, as a Workplane (so that dist() and compound() take it)."""
    return cq.Workplane(obj=one(s).intersect(one(bx)))


def cached(name, fn):
    f = CACHE / f'{name}.json'
    if f.exists():
        return json.loads(f.read_text())
    t = time.time()
    r = fn()
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(r, ensure_ascii=False))
    print(f'  [{name}: {time.time() - t:.0f} s]', flush=True)
    return r


stamp, brep_cached = BT.stamp, BT.brep_cached
SRC = X.HERE


@lru_cache(None)
def turntable():
    return BT.turntable_model()


def upper_tt():
    return {n: d for n, d in turntable().items() if BT.is_upper(d)}


def side_tt():
    return {n: d for n, d in turntable().items() if not BT.is_upper(d)}


@lru_cache(None)
def lower():
    return BT.chassis_model()


def fill_z():
    return run_stage('mass')['shot']['fill_z']


def floors():
    return tuple(run_stage('mass')['shot']['floors_z'])


@lru_cache(None)
def body(swing=0.0):
    if swing:
        return {n: {**d, 'shape': d['shape'].rotate((0, 0, 0), (0, 0, 1), swing)} for n, d in body().items()}
    print('Body', flush=True)
    fz, fl = fill_z(), floors()
    return brep_cached(f'body_{stamp(SRC / "x1_body.py", SRC / "x1_turntable.py", SRC / "stdparts.py", SRC / "board_step.py", Bd.MAIN_BOARD_PARTS, BS.STEP, X.ROOT / "body_concept/source/draw_body_concept.py")}'
                       f'_{fz:.3f}_{fl[0]:.2f}_{fl[1]:.2f}', lambda: Bd.body_parts(fz, floors=fl), CACHE)


def printed_volume(s, skin):
    """Solid-modelled block printed with perimeters (skin) and sparse infill: (printed mm^3, modelled mm^3)."""
    o = one(s)
    v, a = o.Volume(), o.Area()
    shell = min(v, a*skin)
    return shell + Bd.INFILL*(v - shell), v


# ------------------------------------------------------------------ mass
def cw_item(fz, fl):
    cw = Bd.counterweight(fz, fl)
    vp, v = printed_volume(cw, Bd.SKIN['B101'])
    return ('B101_counterweight', BT.solid_item(cw, density=DENS['petg']*vp/v), f'{Bd.SKIN["B101"]} mm perimeters + {Bd.INFILL:.0%} infill')


@lru_cache(None)
def fixed_items():
    """(name, (mass, centre, inertia), note) for every body item except the counterweight and the shot."""
    rows = []
    rho = DENS['petg']
    half, block = Bd.right_half(), Bd.tank_block()
    blk = one(half).intersect(one(block))
    vp, v = printed_volume(cq.Workplane(obj=blk), Bd.SKIN['B103'])
    rows.append(('B103_right_half_shell', BT.solid_item(half.cut(block), density=rho), '2 mm walls, printed solid'))
    rows.append(('B103_right_half_tank_block', BT.solid_item(cq.Workplane(obj=blk), density=rho*vp/v),
                 f'{Bd.SKIN["B103"]} mm perimeters + {Bd.INFILL:.0%} infill'))
    rows.append(('B102_left_half', BT.solid_item(Bd.left_half(), density=rho), '2 mm walls (cab shell included), printed solid'))
    for n in ('B104_cab_interior', 'B105_operator', 'B106_battery_hatch', 'B107_left_handrail'):
        s = Bd.PRINT_SHAPES[n]()
        vp, v = printed_volume(s, Bd.SKIN[n[:4]])
        rows.append((n, BT.solid_item(s, density=rho*vp/v), f'{Bd.SKIN[n[:4]]} mm perimeters + {Bd.INFILL:.0%} infill '
                     '(thin parts print solid)'))
    for n, v in Bd.electronics().items():
        rows.append((n, BT.solid_item(v[0], mass=v[2]), 'bought, mass assumed'))
    for n, (s, c, m) in Bd.hardware().items():
        rows.append((n, BT.solid_item(s, density=DENS[m]), m))
    for n, kg, c in WIRING:
        rows.append((n, BT.point_item(kg, c, (40, 40, 20)), 'assumed'))
    return tuple(rows)


def body_items(fz, fl):
    return [cw_item(fz, fl)] + list(fixed_items())


def side_of(name):
    """Which group an item's mass is reported under (the halves' mass rows carry suffixes such as _shell)."""
    for pre, sd in (('B102', 'left'), ('B103', 'right'), ('B101', 'counterweight'), ('ballast', 'shot')):
        if name.startswith(pre):
            return sd
    return Bd.half_of(name) or 'wiring_and_fixings'


def side_moments(rows):
    """Moments about the X axis (kg m, Y + = left) per group: rows of (name, kg, centre_mm)."""
    out = {}
    for n, m, c in rows:
        k = side_of(n)
        out[k] = out.get(k, 0.0) + m*c[1]/1000
    return {k: round(v, 5) for k, v in sorted(out.items())}


def mass_stage():
    tt0 = turntable()
    arm_v, motor_v = BT.arm_motor_volumes(tt0)
    up = []
    for n, d in tt0.items():
        if BT.is_upper(d) and d['group'] != 'pinion':
            it = BT.mass_item(n, d, arm_v, motor_v)
            if it is not None:
                up.append((n, it))
    pin = [BT.mass_item(n, d, arm_v, motor_v) for n, d in tt0.items() if d['group'] == 'pinion']
    up.append(('RU66_inner_ring', BT.solid_item(X.ru66()[1], mass=BT.RU66_KG/2)))
    up_items = [it for _, it in up] + [p for p in pin if p is not None]
    arm = [it for n, it in up if n == 'ARM60_arm_and_actuators'][0]
    base = [it for n, it in up if n == 'ARM60_fixed_pivot_base'][0]
    pocket = Bd.pocket_poly()
    area = pocket.area
    A, C = [], []
    for ps in Bd.pocket_sides():
        a = sum(p.area for p in ps)
        A.append(a); C.append((sum(p.area*p.centroid.x for p in ps)/a, sum(p.area*p.centroid.y for p in ps)/a))
    PF, rho = Bd.POCKET_FLOOR, Bd.SHOT_DENSITY
    fz, fl = 130.4, (PF, PF)                            # concept B1; iterate: the pocket changes the counterweight's mass
    for k in range(8):
        rows = body_items(fz, fl)
        items = up_items + [r[1] for r in rows]
        mx = sum(i[0]*i[1][0] for i in items)
        my = sum(i[0]*i[1][1] for i in items)
        mL, mR = np.linalg.solve([[C[0][0], C[1][0]], [C[0][1], C[1][1]]], [-mx, -my])   # shot per side: X and Y moments zero
        dL, dR = mL/(rho*A[0]), mR/(rho*A[1])
        fz_new = PF + max(dL, dR)
        fl_new = (fz_new - dL, fz_new - dR)
        print(f'  pass {k}: shot {1000*(mL + mR):.0f} g (left {1000*mL:.0f}, right {1000*mR:.0f}), fill to Z {fz_new:.2f}, '
              f'floors {fl_new[0]:.2f} / {fl_new[1]:.2f}', flush=True)
        done = abs(fz_new - fz) < .03 and max(abs(a - b) for a, b in zip(fl_new, fl)) < .03
        fz, fl = round(fz_new, 3), (round(fl_new[0], 2), round(fl_new[1], 2))
        if done:
            break
    m_shot = mL + mR
    rows = body_items(fz, fl)
    sh = BT.solid_item(Bd.shot(fz, fl), mass=m_shot)
    rows.append(('ballast_steel_shot', sh, f'{Bd.SHOT_DENSITY*1e6:.1f} g/cm3 poured steel shot, fills the pocket to Z {fz:.1f} '
                 f'(floors: left {fl[0]:.1f}, right {fl[1]:.1f})'))
    body_list = [r[1] for r in rows]
    U = BT.body_props(up_items + body_list)
    Bp = BT.body_props(body_list)
    c_up = np.array(U['centre_m'])*1000
    # tucked-arm bound (as concept B1): every moving arm part at the ARM60 base centre
    c_tucked = c_up + arm[0]*(np.array(base[1]) - np.array(arm[1]))/U['mass_kg']
    mp = json.loads((SIM / 'turntable_mass_properties.json').read_text())
    low = mp['lower']
    m_low, c_low = low['mass_kg'], np.array(low['centre_m'])*1000
    I_axis = U['inertia_kgm2'][2][2] + U['mass_kg']*((U['centre_m'][0])**2 + (U['centre_m'][1])**2)
    printed = {r[0]: r[1][0] for r in rows if r[0].startswith('B10')}
    per_print = {n: round(sum(v for k, v in printed.items() if k.startswith(n))*1000, 1)
                 for n in ('B101', 'B102', 'B103', 'B104', 'B105', 'B106', 'B107')}
    battery = [r[1] for r in rows if Bd.half_of(r[0]) == 'hatch']
    hatch_kg = sum(i[0] for i in battery)
    side = side_moments([(r[0], r[1][0], r[1][1]) for r in rows])
    side['turntable_arm60_motor (rest of the upper)'] = round(U['mass_kg']*c_up[1]/1000 - sum(side.values()), 5)
    out = dict(
        units='kg, mm, kg mm^2 about each item centre; vehicle frame, swing 0, arm stretched',
        items=[dict(name=n, mass_kg=it[0], centre_mm=[round(c, 3) for c in it[1]], inertia_kgmm2=np.asarray(it[2]).tolist(), note=note)
               for n, it, note in rows],
        shot=dict(kg=m_shot, cm3=m_shot/Bd.SHOT_DENSITY/1000, fill_z=fz, pocket_area_mm2=area, pocket_floor_z=Bd.POCKET_FLOOR,
                  floors_z=list(fl), left_kg=float(mL), right_kg=float(mR),
                  floors_note='left and right pocket floors: the shot is deeper on the heavier-needing side, so it zeroes the '
                              'lateral CG as well as the fore-aft one (rev B)',
                  pause_height_above_bed_mm=fz - Bd.Z_BOT, density_kg_mm3=Bd.SHOT_DENSITY,
                  note='sized so the upper CG is on the swing axis with the arm stretched (as concept B1), sideways too'),
        prints_g=per_print, body_kg=Bp['mass_kg'], body_centre_mm=[c*1000 for c in Bp['centre_m']],
        lateral=dict(upper_cg_y_mm=float(c_up[1]), limit_mm=LATERAL_CG_MAX, hatch_with_battery_kg=hatch_kg,
                     moments_kg_m_about_x=side,
                     note='Y + = machine left. The battery rides on the centreline in the hatch (rev B); the cab and '
                          'controller (left) against the tank, toolbox and switch gear (right).'),
        upper=dict(kg=U['mass_kg'], centre_mm=c_up.tolist(), inertia_about_swing_axis_kgm2=I_axis,
                   centre_arm_tucked_bound_mm=c_tucked.tolist()),
        machine=dict(kg=U['mass_kg'] + m_low, cg_x_arm_stretched_mm=float((U['mass_kg']*c_up[0] + m_low*c_low[0])/(U['mass_kg'] + m_low)),
                     cg_x_arm_tucked_bound_mm=float((U['mass_kg']*c_tucked[0] + m_low*c_low[0])/(U['mass_kg'] + m_low))),
        assumptions=dict(petg_kg_mm3=DENS['petg'], infill=Bd.INFILL, skins_mm=Bd.SKIN, shot_density_kg_mm3=Bd.SHOT_DENSITY,
                         electronics='bought; cells at the Samsung INR18650-35E maximum, 50 g each; others assumed',
                         wiring_fixings_kg=sum(w[1] for w in WIRING)))
    out['summary'] = (f"body {out['body_kg']:.3f} kg incl. {m_shot:.3f} kg shot; upper {U['mass_kg']:.3f} kg, "
                      f"CG X {c_up[0]:.1f}, Y {c_up[1]:.2f}")
    SIM.mkdir(exist_ok=True)
    (SIM / 'body_mass_properties.json').write_text(json.dumps(out, indent=1) + '\n')
    return dict(shot=out['shot'], prints_g=per_print, body_kg=out['body_kg'], upper=out['upper'], machine=out['machine'],
                lateral=out['lateral'])


# ------------------------------------------------------------------ export
def overhang_area(tm, limit_deg=44.0, z_band=None):
    """Down-facing area flatter than limit_deg from horizontal, not on the bed (mm^2): what needs a bridge or support.
    45° faces (the sleeve teardrops, the hook) are left out. z_band: only faces with centres in that height band."""
    n = tm.face_normals
    zc = tm.triangles_center[:, 2]
    m = (n[:, 2] < -math.cos(math.radians(limit_deg))) & (zc > .3)
    if z_band:
        m &= (zc > z_band[0]) & (zc < z_band[1])
    return float(tm.area_faces[m].sum())


def export_stl(s, path, shells=1):
    """As build_track_wheel.export_stl, but B101 has 2 shells: its outside and the sealed shot pocket (a void that the
    slicer prints round; the shot goes in during a pause at the pocket rim)."""
    cq.exporters.export(s, str(path), tolerance=.035, angularTolerance=.12)
    tm = trimesh.load_mesh(path)
    tm.update_faces(tm.nondegenerate_faces(height=1e-8)); tm.remove_unreferenced_vertices(); tm.export(path)
    parts = tm.split(only_watertight=False)
    assert tm.is_watertight and tm.is_winding_consistent and len(parts) == shells, (path, tm.is_watertight, len(parts))
    if shells == 2:                                  # the inner shell must be the void (inward normals: negative volume)
        assert min(q.volume for q in parts) < 0, path
    return tm


def export_stage():
    rows = []
    b = body()
    for n, (mat, (axis, deg, how), note) in Bd.PRINTED.items():
        s = b[n]['shape']
        assert one(s).isValid() and len(s.solids().vals()) == 1, n
        print('Export', n, flush=True)
        export.export_step(s, ROOT / 'step' / f'{n}.step')
        placed = export.to_bed(s, axis, deg)
        tm = export_stl(placed, ROOT / 'stl' / f'{n}.stl', shells=2 if n.startswith('B101') else 1)
        ext = tm.extents.tolist()
        rows.append(dict(name=n, material=mat, print_orientation=how, note=note, volume_mm3=round(one(s).Volume(), 1),
                         print_bounds_mm=[round(v, 1) for v in ext], fits_256_bed=bool(max(ext[:2]) <= BED and ext[2] <= BED),
                         overhang_flatter_than_45deg_mm2=round(overhang_area(tm), 0),
                         of_which_pocket_ceiling_mm2=round(overhang_area(tm, z_band=(fill_z() - Bd.Z_BOT - .5, fill_z() - Bd.Z_BOT + .5)), 0)
                         if n.startswith('B101') else 0, stl_watertight=True,
                         stl_shells=len(tm.split(only_watertight=False)),
                         step_roundtrip=True))
    print('Assembly STEP', flush=True)
    keep = {n: d for n, d in b.items()}
    solids = BT.save_assembly(keep, ROOT / 'step/X1_body_assembly.step', 'X1_body_assembly')
    write_scene(b)
    return dict(rows=rows, assembly_solids=solids)


def write_scene(b):
    print('Viewer scene', flush=True)
    items = []
    for n, d in b.items():
        m = export.mesh(d['shape'], .15, .25) if d['kind'] == 'printed' else export.mesh(d['shape'], .1, .2)
        items.append(dict(name=n, color=list(d['color']), group='body', kind=d['kind'], part=Bd.half_of(n) or
                          ('counterweight' if n.startswith(('B101', 'ballast', 'cw_')) else 'fixed'), **m))
    # the viewer's 'Inside the body' view hides these prints with the shell (the interior, operator and handrail stay)
    payload = dict(items=items, slide_out=Bd.SLIDE_OUT)
    (X.HERE / 'body_scene.json.gz').write_bytes(gzip.compress(json.dumps(payload, separators=(',', ':')).encode()))


# ------------------------------------------------------------------ checks
_SHP = {}


_BB = {}


def bbox(d):
    """Bounding box of an item's shape, once per shape object (the fixed parts recur in every run)."""
    w = d.get('envelope', d['shape'])
    if id(w) not in _BB:
        _BB[id(w)] = (w, one(w).BoundingBox())
    return _BB[id(w)][1]


def _boxes_touch(A, B_, margin=.05):
    return not (A.xmin > B_.xmax + margin or B_.xmin > A.xmax + margin or A.ymin > B_.ymax + margin or
                B_.ymin > A.ymax + margin or A.zmin > B_.zmax + margin or B_.zmin > A.zmax + margin)


def _job(job):
    """Overlap volume of two shapes; a compound (the ARM60 arm) is taken solid by solid, boxes first."""
    k, a, b = job
    t = time.time()
    sa, sb = _SHP[(k, a)], _SHP[(k, b)]
    la = sa.Solids() if len(sa.Solids()) > 1 else [sa]
    lb = sb.Solids() if len(sb.Solids()) > 1 else [sb]
    v = 0.
    for p in la:
        P = p.BoundingBox()
        for q in lb:
            if not _boxes_touch(P, q.BoundingBox()):
                continue
            common = p.intersect(q)
            v += sum(c.Volume() for c in common.Solids()) if common is not None else 0.
    return v, time.time() - t


def batch_interference(runs, tol=.01, margin=.05):
    """tw_checks.interference for many runs: runs = [(inst, skip)]; every pair whose boxes touch intersected exactly.
    Serial: a forked pool deadlocks inside OCC."""
    global _SHP
    t0 = time.time()
    _SHP, jobs = {}, []
    for k, (inst, skip) in enumerate(runs):
        names = list(inst)
        for n, d in inst.items():
            _SHP[(k, n)] = one(d.get('envelope', d['shape']))
        bbs = {n: bbox(inst[n]) for n in names}
        for i, a in enumerate(names):
            A = bbs[a]
            for b in names[i + 1:]:
                if inst[a]['group'] == 'track' and inst[b]['group'] == 'track':
                    continue
                if skip and skip(a, b):
                    continue
                B_ = bbs[b]
                if (A.xmin > B_.xmax + margin or B_.xmin > A.xmax + margin or A.ymin > B_.ymax + margin or
                        B_.ymin > A.ymax + margin or A.zmin > B_.zmax + margin or B_.zmin > A.zmax + margin):
                    continue
                jobs.append((k, a, b))
    print(f'  {len(jobs)} pairs to intersect', flush=True)
    res = []
    for i, j in enumerate(jobs):
        res.append(_job(j))
        if res[-1][1] > 20:
            print(f'    slow pair {j[1]} / {j[2]}: {res[-1][1]:.0f} s', flush=True)
    out = [dict(pairs_tested=0, hits=[]) for _ in runs]
    for (k, a, b), (v, dt) in zip(jobs, res):
        out[k]['pairs_tested'] += 1
        if v > tol:
            out[k]['hits'].append(dict(a=a, b=b, volume_mm3=round(v, 4)))
    slow = sorted(zip(jobs, res), key=lambda jr: -jr[1][1])[:3]
    print(f'  {len(jobs)} pairs in {time.time() - t0:.0f} s; slowest', [(a, b, round(r[1])) for (k, a, b), r in slow], flush=True)
    return out


def against_run(fixed, moving):
    return ({**fixed, **moving}, lambda a, b: (a in moving) == (b in moving))


def static_stage():
    b = body()
    allp = {**upper_tt(), **side_tt(), **b}
    tt_names = set(turntable())
    board = ('board_', 'controller_')                     # the board's colour groups share the courtyard envelopes
    names = sorted(allp, key=len)
    def stem(n):                                          # the shortest part name this one is a piece of ('charge_jack' for 'charge_jack_lugs')
        return next((m for m in names if n == m or n.startswith(m + '_')), n)
    mated = (('battery_lead_XT30', 'feed_socket_XT30'),)  # nested connector pairs (drawn mated)
    def skip(a, c):
        if a in tt_names and c in tt_names:
            return True
        if a.startswith(board) and c.startswith(board):
            return True
        if a.startswith(c + '_') or c.startswith(a + '_'):   # pieces of one bought part (holder and its contacts, a cell and its ends)
            return True
        if stem(a) == stem(c):                                # sibling pieces (the jack's body and lugs, the switch's rocker and terminals)
            return True
        return any(a.startswith(m) and c.startswith(m) or a.startswith(pr[0]) and c.startswith(pr[1]) or a.startswith(pr[1]) and c.startswith(pr[0])
                   for pr in mated for m in pr)
    return batch_interference([(allp, skip)])[0]


def sweep_stage(step=15):
    """The body turns with the upper: against the chassis and the chassis-side turntable parts."""
    fixed = {**lower(), **side_tt()}
    fixed = {n: d for n, d in fixed.items() if n != 'RU66_inner_ring'}
    zmin = min(bbox(d).zmin for d in body().values())
    below = [n for n, d in fixed.items() if bbox(d).zmax < zmin - .05]       # a swing about Z cannot raise them
    fixed = {n: d for n, d in fixed.items() if n not in below}
    print(f'  body lowest Z {zmin:.2f}: {len(below)} chassis parts wholly below it, {len(fixed)} left to sweep', flush=True)
    angles = list(range(0, 360, step))
    res = batch_interference([against_run(fixed, body(float(a)) if a else body()) for a in angles])
    return dict(body_lowest_z=zmin, chassis_parts_below=len(below), swept_against=sorted(fixed),
                rows=[dict(swing_deg=a, pairs=r['pairs_tested'], hits=r['hits']) for a, r in zip(angles, res)])


def moved(items, dx=0.0, dy=0.0, dz=0.0):
    return {n: {**d, 'shape': d['shape'].translate((dx, dy, dz))} for n, d in items.items()}


def paths_stage(which):
    """which: 'hatch' (lifted off, everything else in place); 'right_half' or 'left_half' (hatch off, that half off,
    everything else in place); 'counterweight' (hatch and halves off); 'cab_interior' (B104 with B105 slid into the left
    half on the bench from the open boom side, 2.1 up, then dropped onto the pegs)."""
    b = body()
    up = upper_tt()
    runs, steps = [], []
    if which == 'hatch':
        mv = {n: d for n, d in b.items() if Bd.half_of(n) == 'hatch'}
        fixed = {**up, **{n: d for n, d in b.items() if n not in mv}}
        for dz in (1, 3, 10, 30, 60):
            runs.append(against_run(fixed, moved(mv, dz=dz))); steps.append(dict(lift=dz))
    elif which == 'cab_interior':
        mv = {n: d for n, d in b.items() if n.startswith(('B104', 'B105'))}
        fixed = {n: d for n, d in b.items() if n.startswith(('B102', 'B107'))}
        for dy, dz in ((-75, 2.1), (-40, 2.1), (-15, 2.1), (-3, 2.1), (0, 2.1), (0, 1.0)):
            runs.append(against_run(fixed, moved(mv, dy=dy, dz=dz))); steps.append(dict(slide_from_boom_side=dy, lift=dz))
    elif which in ('right_half', 'left_half'):
        h = which.split('_')[0]
        side = 1 if h == 'left' else -1
        mv = {n: d for n, d in b.items() if Bd.half_of(n) == h}
        own_screws = {f'sleeve_screw_M3x12_{i}' for i in ((0, 1) if h == 'left' else (2, 3))}
        fixed = {**up, **{n: d for n, d in b.items() if Bd.half_of(n) not in (h, 'hatch') and n not in own_screws}}
        for dy, dz in ((2, 0), (5, 0), (Bd.SLIDE_OUT, 0), (Bd.SLIDE_OUT, 5), (Bd.SLIDE_OUT, 20), (Bd.SLIDE_OUT, 60)):
            runs.append(against_run(fixed, moved(mv, dy=side*dy, dz=dz))); steps.append(dict(slide=dy, lift=dz))
    else:
        cw = {n: d for n, d in b.items() if n.startswith(('B101', 'ballast', 'cw_insert'))}
        for dx, dz in ((2, 0), (5, 0), (15, 0), (15, 40)):
            runs.append(against_run(dict(up), moved(cw, dx=-dx, dz=dz))); steps.append(dict(back=dx, lift=dz))
    return [dict(**st, **r) for st, r in zip(steps, batch_interference(runs))]


def tools_stage():
    b = body()
    every = {**upper_tt(), **b}
    runs, keys = [], []
    def add(key, inst, shape):
        runs.append(against_run(inst, tool(shape))); keys.append(key)
    head_top = Bd.Z_DECK + Bd.SLEEVE_FLOOR + T.M3_HEAD['h']
    xy = [(x, sy*Bd.SLEEVE_Y) for sy in (1, -1) for x in Bd.SLEEVE_X]
    for x, y in xy:
        add('sleeve_screw_key_M3_from_above', every, X.zcyl(1.25, head_top + .05, Bd.hood_top_at(x) + 40, x, y))
    no_screws = {n: d for n, d in every.items() if not n.startswith('sleeve_screw')}
    for x, y in xy:
        add('sleeve_screw_out_through_the_bore', no_screws, X.zcyl(T.M3_HEAD['r'] + .05, head_top - T.M3_HEAD['h'], Bd.hood_top_at(x) + 5, x, y))
    halves_off = {n: d for n, d in every.items() if Bd.half_of(n) is None}
    rb = T.R3.REAR_BULK
    for sy in (1, -1):
        y = sy*Bd.CW_BOLT_Y
        arm_short = X.tp.xcyl(1.6, rb[1] + X.M4_HEAD['h'] + .05, -121.0, y, Bd.CW_BOLT_Z)
        arm_long = X.zcyl(1.6, Bd.CW_BOLT_Z, 260.0, -122.6, y)
        add('counterweight_M4_L_key_halves_off', halves_off, arm_short.union(arm_long))
    jx = Bd.TB_X[1] + 1.5
    add('charge_plug_path', {**every, **lower_near()}, X.tp.xcyl(5.5, jx + 7.1, jx + 60, Bd.JACK['y'], Bd.JACK['z']))   # the charger plug's Ø11 overmold butts on the jack's barrel tip, 7 proud of the wall
    u = Bd.USB
    plug = sbox(u['x'] - 6.2, u['z'] - 3.3, u['x'] + 6.2, u['z'] + 3.3).buffer(-2.0).buffer(2.0, 16)    # slim USB-C overmold
    add('USB_C_plug_path', {**every, **lower_near()}, X.tp.xz_prism(plug, 150.7, 200.0))
    t = {}
    for k, r in zip(keys, batch_interference(runs)):
        t.setdefault(k, []).append(r)
    return t


@lru_cache(None)
def lower_near():
    """Chassis parts whose boxes reach above Z 90 (the rest cannot touch anything at the body's height)."""
    return {n: d for n, d in lower().items() if one(d['shape']).BoundingBox().zmax > 90}


def mesh_pts(s, tol=.2):
    v, _ = one(s).tessellate(tol, .3)
    return np.array([[p.x, p.y, p.z] for p in v])


def clearances_stage():
    b = body()
    tt = turntable()
    c = {}
    L, R, CW = (b[n]['shape'] for n in ('B102_left_half', 'B103_right_half', 'B101_counterweight'))
    base, arm = tt['ARM60_fixed_pivot_base']['shape'], tt['ARM60_arm_and_actuators']['shape']
    t101 = tt['T101_centre_frame']['shape']
    c['left half to the ARM60 base (hood front, cab)'] = dist(L, base)
    c['right half to the ARM60 base (hood front, deck strip)'] = dist(R, base)
    c['left half to the ARM60 arm (stretched)'] = dist(L, arm)
    c['right half to the ARM60 arm (stretched)'] = dist(R, arm)
    c['left half to right half (seam, lap)'] = dist(L, R)
    c['halves to the counterweight'] = min(dist(L, CW), dist(R, CW))
    c['hook tongue to the T101 base plate (left)'] = dist(Bd.hook(1), t101)
    c['hook tongue to the T101 base plate (right)'] = dist(Bd.hook(-1), t101)
    c['counterweight to the motor lead space'] = dist(CW, tt['JGY370_lead_space']['shape'])
    H = b['B106_battery_hatch']['shape']
    halves = BT.compound([L, R])
    zl = Bd.Z_LEDGE
    sled = clip(H, X.box(-200, 0, -100, 100, 150, zl - .01))
    c['battery sled (hatch underside) to the halves, lifting path'] = dist(sled, halves)
    c['hatch plate edges to the hood skin (side and front gaps)'] = dist(clip(H, X.box(-200, 0, -100, 100, zl + 1.0, 230)), halves)
    batt = BT.compound([b[n]['shape'] for n in b if n.startswith(('cell_', 'holder_', 'battery_'))])
    c['battery (cells, holders, BMS, lead) to the halves'] = dist(batt, halves)
    c['battery cells to T101 (the frame top below)'] = dist(BT.compound([b[n]['shape'] for n in b if n.startswith('cell_')]), t101)
    CI, OP = b['B104_cab_interior']['shape'], b['B105_operator']['shape']
    c['cab interior to the cab shell, above its floor plate'] = dist(clip(CI, X.box(-100, 120, 0, 160, Bd.Z_DECK + Bd.T_W + 1.3, 260)), L)
    c['cab interior right pillar to the ARM60 base'] = dist(CI, base)
    c['operator to the cab interior, above the seat (hands to joysticks, back to backrest)'] = dist(
        clip(OP, X.box(-100, 120, 0, 160, 166.0, 260)), CI)
    c['operator to the cab shell'] = dist(OP, L)
    c['left handrail pegs to their pillar holes (radial; the handle stands 2.2 off the cab side)'] = dist(
        clip(b['B107_left_handrail']['shape'], X.box(-100, 120, Bd.W + .01, 200, 0, 300)), L)
    grab = BT.compound(Bd.grab_rail())
    c['grab rail to the ARM60 base'] = dist(grab, base)
    c['grab rail to the ARM60 arm (stretched)'] = dist(grab, arm)
    c['main board parts to the left half (the PCB sits on its 4 bosses)'] = dist(b['board_parts']['shape'], L)
    c['main board mated plugs to the left half'] = dist(b['board_plugs']['shape'], L)
    c['controller PCB edges to the left half walls'] = dist(b['controller_PCB']['shape'], L.cut(X.box(-200, 100, 0, 160, 100, Bd.BOARD['z'][0] + .01)))
    c['fuse holder to the right half'] = dist(b['fuse_holder_5A']['shape'], R)
    # radii and heights
    P = np.concatenate([mesh_pts(b[n]['shape']) for n in Bd.PRINTED])
    r = np.hypot(P[:, 0], P[:, 1])
    c['body tail radius (largest radius behind the axis)'] = round(float(r[P[:, 0] < 0].max()), 1)
    c['body front radius (largest radius ahead of the axis)'] = round(float(r[P[:, 0] >= 0].max()), 1)
    c['body lowest point Z'] = round(float(P[:, 2].min()), 2)
    zlow = []
    for n, d in lower_near().items():
        Q = mesh_pts(d['shape'], .3)
        rq = np.hypot(Q[:, 0], Q[:, 1])
        sel = rq > 70
        if sel.any():
            zlow.append(float(Q[sel, 2].max()))
    c['chassis highest point outside r 70 (swept by the body)'] = round(max(zlow), 2)
    c['vertical clearance body to chassis outside r 70'] = round(float(P[:, 2].min()) - max(zlow), 2)
    c['body top Z (the roof lamps)'] = round(float(P[:, 2].max()), 2)
    return c


def bed_check(rows):
    return {r['name']: dict(bounds=r['print_bounds_mm'], fits=r['fits_256_bed']) for r in rows}


# ------------------------------------------------------------------ stages
def run_stage(st):
    if st == 'mass':
        return cached('mass', mass_stage)
    if st == 'export':
        return cached('export', export_stage)
    if st == 'static':
        r = cached('static', static_stage)
        print('  static:', r['pairs_tested'], 'pairs, hits', r['hits'], flush=True); return r
    if st == 'sweep':
        return cached('sweep', sweep_stage)
    if st == 'paths':
        r = {f'{w}_off': cached(f'paths_{w}', lambda w=w: paths_stage(w)) for w in ('hatch', 'right_half', 'left_half', 'counterweight')}
        r['counterweight_off_halves_off'] = r.pop('counterweight_off')
        r['cab_interior_in_on_the_bench'] = cached('paths_cab_interior', lambda: paths_stage('cab_interior'))
        print('  path hits:', {k: [len(x['hits']) for x in v] for k, v in r.items()}, flush=True); return r
    if st == 'tools':
        r = cached('tools', tools_stage)
        print('  tool hits:', {k: [len(x['hits']) for x in v] for k, v in r.items()}, flush=True); return r
    if st == 'clearances':
        r = cached('clearances', clearances_stage)
        print('  clearances:', json.dumps(r, indent=1), flush=True); return r
    if st == 'final':
        return final()
    raise SystemExit(f'unknown stage {st}; one of {STAGES}')


def final():
    ms, ex, static, sweep, seq, tl, clr = (run_stage(s) for s in ('mass', 'export', 'static', 'sweep', 'paths', 'tools', 'clearances'))
    sweep_ok = all(not r['hits'] for r in sweep['rows'])
    path_runs = [r for v in seq.values() for r in v]
    tool_runs = [r for v in tl.values() for r in v]
    fits = all(r['fits_256_bed'] for r in ex['rows'])
    cg_ok = abs(ms['upper']['centre_mm'][0]) < .5 and abs(ms['upper']['centre_mm'][1]) < LATERAL_CG_MAX
    ok = (not static['hits'] and sweep_ok and all(not r['hits'] for r in path_runs + tool_runs) and fits and cg_ok
          and clr['vertical clearance body to chassis outside r 70'] > 3.0)
    sc = X.HERE / 'body_scene.json.gz'
    data = json.loads(gzip.decompress(sc.read_bytes())); data['sweep_ok'] = sweep_ok
    sc.write_bytes(gzip.compress(json.dumps(data, separators=(',', ':')).encode()))
    val = dict(revision='X1 body B1 rev B (CAD), from concept B1 issue 2 and the user review of rev A',
               drawings='body_concept/X1_body_concept_B1.pdf',
               parts=ex['rows'], assembly_solids=ex['assembly_solids'], bed=bed_check(ex['rows']), mass=ms,
               static=static, swing_sweep=dict(step_deg=15, ok=sweep_ok, **sweep), assembly_paths=seq, tool_access=tl,
               clearances_mm=clr,
               scope='Nominal CAD with exact solid intersections: static fit at swing 0 against the turntable, the ARM60 '
                     '(as exported, stretched) and each other; the body swept every 15° against the chassis; the battery '
                     'hatch lifted off; each half off and on (hatch off) with the rest in place; the counterweight off '
                     'with the halves off; the cab interior slid in on the bench; tool and plug paths; bed fit; mass and '
                     'balance (fore-aft and lateral). Not a print-tolerance, load, magnet-force or powered test.')
    val['pass'] = ok
    (ROOT / 'body_validation.json').write_text(json.dumps(val, indent=1, ensure_ascii=False) + '\n')
    print(json.dumps(dict(passed=ok, static_hits=static['hits'][:8], sweep_hits={r['swing_deg']: r['hits'][:3] for r in sweep['rows'] if r['hits']},
                          path_hits={k: [len(r['hits']) for r in v] for k, v in seq.items()},
                          tool_hits={k: [len(r['hits']) for r in v] for k, v in tl.items()},
                          bed=bed_check(ex['rows']), overhang={r['name']: r['overhang_flatter_than_45deg_mm2'] for r in ex['rows']},
                          clearances=clr, mass=ms), indent=1, ensure_ascii=False))
    return ok


def main():
    (ROOT / 'step').mkdir(exist_ok=True); (ROOT / 'stl').mkdir(exist_ok=True); SIM.mkdir(exist_ok=True)
    args = sys.argv[1:] or ['final']
    for st in args:
        run_stage(st)


if __name__ == '__main__':
    main()

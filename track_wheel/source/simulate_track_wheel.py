"""MuJoCo tests of the track wheel unit. Model units are SI.

The Track R4 closed pin chain (34 free shoes, 68 hinge point constraints, steel
bushings on the convex-decomposed sprocket) runs on this unit's final drive and
recoil idler:
  * drive: DC gearmotor model from the Pololu 37D 150:1 datasheet line through
    the 1.75:1 hub stage, a 1.0 A driver current limit, a PI speed loop and the
    reflected rotor inertia (estimated) as joint armature;
  * idler: slide joint with the C-600-072-1500 rate, the assembled preload, the
    frame-fixed recoil stop (-4.0 mm) and the channel nose (+4.2 mm).
Chain tension is read from the hinge constraint forces. Tooth skips are found
by comparing chain travel along the loop with sprocket rotation.

Cases (python simulate_track_wheel.py --case NAME, or --case all):
  fixture        stand test: run-in both ways with +-5 N side pulls on the chain
  reverse_wall   half machine reversing into a wall: drive stalls at the current
                 limit, the worst case for the slack strand under the sprocket
  reverse_wall_r4spring   negative control: same with the old R4 idler spring
  obstacle       half machine driving over a 6 mm bar at the current limit
  debris         stand test in reverse: a 4 mm stone on the lower run is carried
                 round the idler (recoil and peak pin load)
  debris_5mm     the same with a 5 mm stone: the idler reaches its hard stop
  lateral        stand test with +-20 N side pulls on the chain
  lateral_r4spring        negative control: same with the old R4 idler spring
"""
import argparse, json, math, sys, time
import numpy as np
import trimesh
import mujoco
import cadquery as cq
from shapely.geometry import box as sbox, Point
from shapely.ops import triangulate, unary_union
import tw_parts as tp
from tw_design import *

ex = tp.ex
ROOT = tp.ROOT
SIM = ROOT / 'simulation'
PETG_KG_MM3 = 1.27e-6
DT = .0005
SAMPLE = 20                                     # steps per sample (10 ms)
N_TOTAL = GEARMOTOR['ratio'] * HUB_RATIO
R_EFF = ex.PITCH * ex.TEETH / (2 * math.pi)     # mm of chain per radian, averaged over a tooth


def motor_constants():
    g = GEARMOTOR; r = drive_rating()
    R = g['voltage'] / g['stall_A']
    ke = (g['voltage'] - g['no_load_A'] * R) / r['sprocket_no_load_rad_s']    # V s/rad at the sprocket
    return dict(R_ohm=R, ke_V_s_rad=ke, kt_Nm_A=r['torque_per_amp_Nm'], i0_A=g['no_load_A'],
                i_limit_A=DRIVE_CURRENT_LIMIT_A, voltage=g['voltage'],
                reflected_inertia_kg_m2=reflected_inertia(), total_ratio=N_TOTAL)


# ---------------------------------------------------------------- geometry
def convex_pieces(profile):
    pieces = [t for t in triangulate(profile) if profile.covers(t)]
    assert unary_union(pieces).symmetric_difference(profile).area < 1e-6
    changed = True
    while changed:
        changed = False
        for i in range(len(pieces)):
            for j in range(i):
                u = pieces[i].union(pieces[j])
                if u.geom_type == 'Polygon' and abs(u.convex_hull.area - u.area) < 1e-7:
                    pieces[j] = u.convex_hull; pieces.pop(i); changed = True; break
            if changed:
                break
    return pieces


def write_prisms(pieces, spans, dest, prefix=''):
    dest.mkdir(parents=True, exist_ok=True); files = []
    for side, (y0, y1) in enumerate(spans):
        for i, p in enumerate(pieces):
            xz = np.asarray(p.exterior.coords)[:-1]; n = len(xz)
            v = np.array([[x, y, z] for y in [y0, y1] for x, z in xz]) * .001
            f = []
            for k in range(1, n - 1):
                f.extend([[0, k + 1, k], [n, n + k, n + k + 1]])
            for k in range(n):
                j = (k + 1) % n; f.extend([[k, j, n + j], [k, n + j, n + k]])
            path = dest / f'{prefix}{side}_{i:03}.obj'
            trimesh.Trimesh(vertices=v, faces=f, process=False).export(path); files.append(path)
    for old in set(dest.glob('*.obj')) - set(files):
        old.unlink()
    return files


def sprocket_meshes():
    return write_prisms(convex_pieces(ex.sprocket_outline(24, 4)), [(-7, 7)], SIM / 'sprocket_meshes_si')


def shoe_rail_meshes():
    """Convex pieces of the shoe running rail, as in the Track R4 model."""
    profile = sbox(-10, -4, 10, 4).union(Point(-10, 0).buffer(4, quad_segs=12))
    profile = profile.difference(Point(10, 0).buffer(4.3, quad_segs=12))
    return write_prisms(convex_pieces(profile), [(-21, -14), (14, 21)], SIM / 'shoe_rail_meshes_si')


# ---------------------------------------------------------------- inertia from CAD
def combine(items):
    masses, centres, tensors = [], [], []
    for shape, density in items:
        s = tp.one(shape) if hasattr(shape, 'vals') else shape
        m = s.Volume() * density; c = s.Center()
        masses.append(m); centres.append(np.array([c.x, c.y, c.z]))
        tensors.append(np.array(cq.Shape.matrixOfInertia(s)) * density)
    total = sum(masses); centre = sum(m * c for m, c in zip(masses, centres)) / total
    tensor = np.zeros((3, 3))
    for m, c, inertia in zip(masses, centres, tensors):
        d = c - centre; tensor += inertia + m * (np.dot(d, d) * np.eye(3) - np.outer(d, d))
    tensor *= 1e-6
    return dict(mass_kg=total, centre_m=(centre * .001).tolist(),
                fullinertia_kg_m2=[float(tensor[i, j]) for i, j in [(0, 0), (1, 1), (2, 2), (0, 1), (0, 2), (1, 2)]])


def density(n, d, shape):
    if d['kind'] == 'printed':
        return PETG_KG_MM3
    if '608' in n:
        return .012 / tp.one(shape).Volume()
    if n.startswith('bearing_') and n.endswith('_outer'):
        kind = 'inboard' if BEARINGS['inboard']['model'] in n else 'outboard'
        return BEARINGS[kind]['mass_kg'] / tp.one(shape).Volume()
    if 'insert' in n:
        return 8.5e-6
    return 7.85e-6


def mass_properties():
    """Rigid bodies of the model from the unit CAD (kg, m, kg m²), cached."""
    path = SIM / 'mass_properties.json'
    if path.exists():
        return json.loads(path.read_text())
    parts = tp.printed_parts(); inst = tp.unit_instances(parts, with_chain=False)
    off = ex.IDLER_ASSEMBLY_OFFSET
    origins = {'drive': (DRIVE_X, 0, tp.AXLE_Z), 'idler': (IDLER_X + off, 0, tp.AXLE_Z),
               'idler_slide': (IDLER_X + off, 0, tp.AXLE_Z)}
    for j, x in enumerate(ex.ROAD_ROLLERS):
        origins[f'roller{j}'] = (x, 0, 29)
    for j, x in enumerate(ex.RETURN_ROLLERS):
        origins[f'return{j}'] = (x, 0, tp.RETURN_Z)
    out = {}
    for g, o in origins.items():
        items = [(d['shape'].translate(tuple(-v for v in o)), density(n, d, d['shape'])) for n, d in inst.items() if d['group'] == g]
        out[g] = combine(items)
    link = [(parts['05_track_shoe']['shape'], PETG_KG_MM3),
            (tp.yring(ex.BUSH_R, 1.55, -ex.BUSH_LENGTH / 2, ex.BUSH_LENGTH / 2, 10, 0), 7.85e-6),
            (tp.ycyl(1.5, -ex.PIN_LENGTH / 2, ex.PIN_LENGTH / 2, 10, 0), 7.85e-6)]
    link += [(tp.yring(3, 1.5, dy - .3, dy + .3, 10, 0), 7.85e-6) for dy in [-ex.PIN_CLIP_Y, ex.PIN_CLIP_Y]]
    out['shoe'] = combine(link)
    SIM.mkdir(exist_ok=True); path.write_text(json.dumps(out, indent=2))
    return out


# ---------------------------------------------------------------- model
SPRINGS = {
    'R5': dict(label='R5 recoil spring C-600-072-1500', **slide_spring(), friction=.5),
    'R4': dict(label='Track R4 idler spring (negative control)', k=4000., springref=.00375, range=(-.003, .006), friction=.5),
}


def make_model(ground=False, spring='R5', wall=None, bump=None, stone=None):
    mp = mass_properties(); mc = motor_constants(); sp = SPRINGS[spring]
    def inertial(name, mass=None):
        d = mp[name]; pos = ' '.join(f'{v:.6g}' for v in d['centre_m']); t = ' '.join(f'{v:.6g}' for v in d['fullinertia_kg_m2'])
        return f'<inertial pos="{pos}" mass="{d["mass_kg"] if mass is None else mass:.6g}" fullinertia="{t}"/>'
    teeth = sprocket_meshes(); rails = shoe_rail_meshes()
    assets = '\n'.join(f'<mesh name="tooth{i}" file="sprocket_meshes_si/{p.name}"/>' for i, p in enumerate(teeth))
    assets += '\n' + '\n'.join(f'<mesh name="rail{i}" file="shoe_rail_meshes_si/{p.name}"/>' for i, p in enumerate(rails))
    wheel = 'contype="2" conaffinity="5"'
    tooth_geoms = '\n'.join(f'<geom type="mesh" mesh="tooth{i}" {wheel}/>' for i in range(len(teeth)))
    G = ex; hub_r = HUB_OD / 2000
    bodies = [f'''<body name="drive" pos="{DRIVE_X * .001} 0 {G.AXLE_Z * .001}">
<joint name="drive" type="hinge" axis="0 1 0" damping=".0001" armature="{mc['reflected_inertia_kg_m2']:.6g}"/>
{inertial('drive')}{tooth_geoms}
<geom name="hub_drum" type="cylinder" fromto="0 {HUB_Y[0] * .001} 0 0 -.007 0" size="{hub_r}" {wheel}/>
<geom name="hub_cap" type="cylinder" fromto="0 .007 0 0 {CAP_Y[1] * .001} 0" size="{hub_r}" {wheel}/>
</body>
<body name="slider" pos="{IDLER_X * .001} 0 {G.AXLE_Z * .001}">
<joint name="slide" type="slide" axis="1 0 0" limited="true" range="{sp['range'][0]:.6g} {sp['range'][1]:.6g}" stiffness="{sp['k']:.6g}"
 springref="{sp['springref']:.6g}" damping="5" frictionloss="{sp['friction']}" solreflimit=".001 1" solimplimit=".99 .999 .0001"/>
{inertial('idler_slide')}
<body name="idler"><joint name="idler_spin" type="hinge" axis="0 1 0" damping=".0001"/>
{inertial('idler')}
<geom type="cylinder" fromto="0 -.007 0 0 .007 0" size="{G.IDLER_GUIDE_R * .001}" {wheel}/>
<geom type="cylinder" fromto="0 -.020 0 0 -.015 0" size="{G.IDLER_RAIL_R * .001}" {wheel}/>
<geom type="cylinder" fromto="0 .015 0 0 .020 0" size="{G.IDLER_RAIL_R * .001}" {wheel}/>
<geom type="cylinder" fromto="0 -.015 0 0 .015 0" size=".028" {wheel}/>
<geom name="idler_guide_left" type="cylinder" fromto="0 {-G.GUIDE_OUTER_Y * .001} 0 0 {-G.GUIDE_INNER_Y * .001} 0" size="{(G.IDLER_RAIL_R + G.GUIDE_HEIGHT) * .001}" {wheel}/>
<geom name="idler_guide_right" type="cylinder" fromto="0 {G.GUIDE_INNER_Y * .001} 0 0 {G.GUIDE_OUTER_Y * .001} 0" size="{(G.IDLER_RAIL_R + G.GUIDE_HEIGHT) * .001}" {wheel}/>
</body></body>''']
    rollers = [(x, 29, 18, f'roller{j}') for j, x in enumerate(G.ROAD_ROLLERS)] + \
              [(x, tp.RETURN_Z, G.RETURN_ROLLER_R, f'return{j}') for j, x in enumerate(G.RETURN_ROLLERS)]
    for i, (x, z, r, name) in enumerate(rollers):
        bodies.append(f'''<body name="roller{i}" pos="{x * .001} 0 {z * .001}"><joint name="roller_spin{i}" type="hinge" axis="0 1 0" damping=".00002"/>
{inertial(name)}
<geom type="cylinder" fromto="0 -.020 0 0 .020 0" size=".013" {wheel}/>
<geom type="cylinder" fromto="0 {-G.GUIDE_INNER_Y * .001} 0 0 -.015 0" size="{r * .001}" {wheel}/>
<geom type="cylinder" fromto="0 .015 0 0 {G.GUIDE_INNER_Y * .001} 0" size="{r * .001}" {wheel}/>
<geom name="roller{i}_guide_left" type="cylinder" fromto="0 {-G.GUIDE_OUTER_Y * .001} 0 0 {-G.GUIDE_INNER_Y * .001} 0" size="{(r + G.GUIDE_HEIGHT) * .001}" {wheel}/>
<geom name="roller{i}_guide_right" type="cylinder" fromto="0 {G.GUIDE_INNER_Y * .001} 0 0 {G.GUIDE_OUTER_Y * .001} 0" size="{(r + G.GUIDE_HEIGHT) * .001}" {wheel}/></body>''')
    machine = half_machine_mass()
    moving = sum(d['mass_kg'] for n, d in mp.items() if n != 'shoe') + mp['shoe']['mass_kg'] * G.TRACK_LINKS
    frame_mass = max(.5, machine - moving)
    joints = ''
    if ground:
        rng = f' limited="true" range="{wall:.6g} 2"' if wall is not None else ''
        joints = (f'<joint name="travel" type="slide" axis="1 0 0"{rng}/><joint name="heave" type="slide" axis="0 0 1"/>'
                  f'<inertial pos="0 0 .08" mass="{frame_mass:.6g}" diaginertia=".03 .03 .03"/>')
    world = ['<body name="frame">' + joints + ''.join(bodies) + '</body>']
    if ground:
        world.insert(0, '<geom name="floor" type="plane" size="3 1 .1" contype="8" conaffinity="1" friction=".6 .005 .0001"/>')
        if bump:
            x, r = bump
            world.insert(0, f'<geom name="bump" type="cylinder" fromto="{x:.6g} -.06 {r:.6g} {x:.6g} .06 {r:.6g}" size="{r:.6g}" contype="8" conaffinity="1" friction=".6 .005 .0001"/>')
    if stone:
        x, hx, hy, hz = stone                       # an angular stone: a block across both shoe rails
        z = max(p[1] for p in G.track_pins() if abs(p[0] - x) < 15 and p[1] < G.AXLE_Z) + 4 + hz + .3
        world.append(f'<body name="stone" pos="{x * .001:.6g} 0 {z * .001:.6g}"><freejoint/>'
                     f'<geom name="stone" type="box" size="{hx * .001:.6g} {hy * .001:.6g} {hz * .001:.6g}" '
                     f'density="2600" contype="1" conaffinity="3" friction=".6 .005 .0001"/></body>')
    eqs = []
    for i, origin, a in G.track_poses():
        geoms = [f'<geom type="box" pos="0 0 -.005" size=".0094 {G.SHOE_WIDTH * .0005} .001"/>']
        geoms += [f'<geom type="mesh" mesh="rail{k}"/>' for k in range(len(rails))]
        for x in G.GROUSER_CENTRES:
            geoms.append(f'<geom type="box" pos="{x * .001} 0 -.0065" size=".001 {G.SHOE_WIDTH * .0005} .0005"/>')
        for x, y, length in [(10, -11.2, 5), (10, 11.2, 5)]:
            geoms.append(f'<geom type="cylinder" fromto="{x * .001} {(y - length / 2) * .001} 0 {x * .001} {(y + length / 2) * .001} 0" size=".004"/>')
        geoms.append(f'<geom type="cylinder" fromto=".01 {-G.PIN_LENGTH * .0005} 0 .01 {G.PIN_LENGTH * .0005} 0" size=".0015" contype="4" conaffinity="2"/>')
        geoms.append(f'<geom name="bush{i}" type="cylinder" fromto=".01 {-G.BUSH_LENGTH * .0005} 0 .01 {G.BUSH_LENGTH * .0005} 0" size="{G.BUSH_R * .001}" contype="4" conaffinity="2"/>')
        sites = [f'<site name="{end}{i}_{s}" pos="{x} {s * .018} 0" size=".0002"/>' for end, x in [('front', .01), ('rear', -.01)] for s in [-1, 1]]
        world.append(f'<body name="shoe{i}" pos="{origin[0] * .001} 0 {origin[1] * .001}" quat="{math.cos(a / 2)} 0 {-math.sin(a / 2)} 0"><freejoint/>{inertial("shoe")}\n' +
                     '\n'.join(geoms + sites) + '</body>')
        for s in [-1, 1]:
            eqs.append(f'<connect site1="rear{i}_{s}" site2="front{(i + 1) % G.TRACK_LINKS}_{s}" solref=".001 1" solimp=".9999 .99999 .0001"/>')
    xml = f'''<mujoco model="track_wheel_R5"><compiler angle="radian" autolimits="true"/>
<option timestep="{DT}" gravity="0 0 -9.81" integrator="implicitfast" solver="Newton" iterations="100" tolerance="1e-10" cone="elliptic" jacobian="sparse"/>
<default><geom contype="1" conaffinity="11" friction=".2 .001 .00001" condim="3" margin=".00002" solref=".002 1" solimp=".99 .999 .0001"/><joint armature=".00000001"/></default>
<asset>{assets}</asset><worldbody>{''.join(world)}</worldbody><equality>{''.join(eqs)}</equality>
<actuator><motor name="drive_motor" joint="drive" gear="1" ctrllimited="true" ctrlrange="-20 20"/></actuator></mujoco>'''
    name = 'track_wheel_ground.xml' if ground else 'track_wheel_fixture.xml'
    path = SIM / name; path.write_text(xml)
    m = mujoco.MjModel.from_xml_path(str(path)); d = mujoco.MjData(m)
    assert m.neq == 2 * G.TRACK_LINKS
    d.qpos[m.joint('slide').qposadr[0]] = G.IDLER_ASSEMBLY_OFFSET * .001
    return m, d


def half_machine_mass():
    path = tp.REPO / 'excavator_60mm/validation.json'
    try:
        return (json.loads(path.read_text())['loads']['nominal_mass_kg'] + .15) / 2
    except Exception:
        return (11.89 + .15) / 2


# ---------------------------------------------------------------- measurement
class Probe:
    def __init__(self, m, d):
        G = ex
        self.m, self.d = m, d
        self.shoes = [m.body(f'shoe{i}').id for i in range(G.TRACK_LINKS)]
        self.rear = [(m.site(f'rear{i}_-1').id, m.site(f'rear{i}_1').id) for i in range(G.TRACK_LINKS)]
        self.frame = m.body('frame').id
        self.drive_q = m.joint('drive').qposadr[0]; self.drive_v = m.joint('drive').dofadr[0]
        self.slide_q = m.joint('slide').qposadr[0]; self.slide_v = m.joint('slide').dofadr[0]
        self.bush = {m.geom(f'bush{i}').id for i in range(G.TRACK_LINKS)}
        self.teeth = set(np.flatnonzero(m.geom_bodyid == m.body('drive').id)) - {m.geom('hub_drum').id, m.geom('hub_cap').id}
        self.hub = {m.geom('hub_drum').id, m.geom('hub_cap').id}
        self.guides = {i for i in range(m.ngeom) if '_guide_' in (m.geom(i).name or '')}
        mujoco.mj_forward(m, d)
        self.ref = self.pins()                    # reference loop at assembly
        seg = np.diff(np.vstack([self.ref, self.ref[:1]]), axis=0)
        self.seglen = np.linalg.norm(seg, axis=1); self.cum = np.concatenate([[0], np.cumsum(self.seglen)])
        self.loop = float(self.cum[-1])
        self.markers = list(range(0, G.TRACK_LINKS, 4)); self.last = None; self.wraps = np.zeros(len(self.markers))
        self.theta0 = float(d.qpos[self.drive_q])

    def pins(self):
        d = self.d
        p = np.array([(d.site_xpos[a] + d.site_xpos[b]) / 2 for a, b in self.rear]) - d.xpos[self.frame]
        return p[:, [0, 2]] * 1000

    def arc(self, xz):
        a = self.ref; b = np.vstack([a[1:], a[:1]]); ab = b - a
        t = np.clip(np.einsum('ij,ij->i', xz - a, ab) / np.einsum('ij,ij->i', ab, ab), 0, 1)
        dist = np.linalg.norm(a + ab * t[:, None] - xz, axis=1); k = int(np.argmin(dist))
        return self.cum[k] + t[k] * self.seglen[k]

    def chain_travel(self):
        p = self.pins(); s = np.array([self.arc(p[i]) for i in self.markers])
        if self.last is not None:
            jump = s - self.last
            self.wraps -= np.round(jump / self.loop)
        self.last = s
        return float(np.mean(s + self.wraps * self.loop))

    def tensions(self):
        m, d = self.m, self.d
        rows = np.flatnonzero(d.efc_type == mujoco.mjtConstraint.mjCNSTR_EQUALITY)
        ids = d.efc_id[rows]; F = np.zeros((m.neq, 3))
        for j in range(m.neq):
            r = rows[ids == j]
            if len(r) == 3:
                F[j] = d.efc_force[r]
        return np.linalg.norm(F[0::2] + F[1::2], axis=1)

    def strands(self, tension, xz):
        z0 = ex.AXLE_Z; out = {}
        sel = dict(top=(xz[:, 1] > z0 + 20) & (np.abs(xz[:, 0]) < 80),
                   bottom_rear=(xz[:, 1] < z0 - 20) & (xz[:, 0] > DRIVE_X + 8) & (xz[:, 0] < -62),
                   bottom_front=(xz[:, 1] < z0 - 20) & (xz[:, 0] > 62) & (xz[:, 0] < IDLER_X - 8))
        for k, s in sel.items():
            out[k] = float(np.mean(tension[s])) if s.any() else float('nan')
        return out

    def contacts(self):
        m, d = self.m, self.d; seated = 0; hub = 0.; guide = 0.; f6 = np.zeros(6)
        for c in range(d.ncon):
            g1, g2 = d.contact[c].geom1, d.contact[c].geom2
            if (g1 in self.bush and g2 in self.teeth) or (g2 in self.bush and g1 in self.teeth):
                seated += 1
            if g1 in self.hub or g2 in self.hub:
                mujoco.mj_contactForce(m, d, c, f6); hub += abs(f6[0])
            if g1 in self.guides or g2 in self.guides:
                mujoco.mj_contactForce(m, d, c, f6); guide += abs(f6[0])
        return seated, hub, guide


# ---------------------------------------------------------------- cases
def ramp(t, pts):
    """Piecewise-linear speed command from (time, rad/s) points."""
    ts = [p[0] for p in pts]; vs = [p[1] for p in pts]
    return float(np.interp(t, ts, vs))


CASES = {
    'fixture': dict(ground=False, spring='R5', duration=12.0,
                    speed=[(0, 0), (.3, 0), (1.3, 3.0), (5.5, 3.0), (6.5, -3.0), (10.8, -3.0), (11.6, 0), (12, 0)],
                    side=[(2, 4, 5.), (7.5, 9.5, -5.)], trace=True,
                    note='Stand test, no floor: run-in both ways at 3 rad/s with ±5 N side pulls on the chain.'),
    'reverse_wall': dict(ground=True, spring='R5', duration=6.0, wall=-.012,
                         speed=[(0, 0), (.3, 0), (.8, -3.0), (5.8, -3.0), (6.0, -3.0)], trace=True,
                         note='Half machine reverses into a wall 12 mm behind it; the drive stalls at the 1.0 A limit.'),
    'reverse_wall_r4spring': dict(ground=True, spring='R4', duration=6.0, wall=-.012,
                                  speed=[(0, 0), (.3, 0), (.8, -3.0), (5.8, -3.0), (6.0, -3.0)],
                                  note='Negative control: the Track R4 idler spring (15.8 N assembled) in the same test.'),
    'obstacle': dict(ground=True, spring='R5', duration=5.0, bump=(.17, .003),
                     speed=[(0, 0), (.3, 0), (.8, 3.0), (4.5, 3.0), (4.9, 0), (5.0, 0)], trace=True,
                     note='Half machine drives over a Ø6 mm rod lying across its path, 60 mm ahead of the idler.'),
    'debris': dict(ground=False, spring='R5', duration=2.8, stone=(88.0, 3.5, 20.0, 2.0),
                   speed=[(0, 0), (.3, 0), (.8, -2.0), (2.8, -2.0)], trace=True,
                   note='Stand test in reverse: a 7 × 4 × 40 mm stone lying across the shoe rails of the lower run is carried round the idler.'),
    'debris_5mm': dict(ground=False, spring='R5', duration=2.8, stone=(88.0, 3.5, 20.0, 2.5),
                       speed=[(0, 0), (.3, 0), (.8, -2.0), (2.8, -2.0)],
                       note='Beyond the recoil capacity: a 7 × 5 × 40 mm stone puts the idler on its stop.'),
    'lateral': dict(ground=False, spring='R5', duration=6.0,
                    speed=[(0, 0), (.3, 0), (1.0, 3.0), (5.5, 3.0), (6, 0)], side=[(1.5, 3.0, 20.), (3.5, 5.0, -20.)],
                    note='Stand test with ±20 N side pulls on the chain while running.'),
    'lateral_r4spring': dict(ground=False, spring='R4', duration=6.0,
                             speed=[(0, 0), (.3, 0), (1.0, 3.0), (5.5, 3.0), (6, 0)], side=[(1.5, 3.0, 20.), (3.5, 5.0, -20.)],
                             note='Negative control: the Track R4 idler spring with the same ±20 N side pulls.'),
}


def run(name):
    cfg = CASES[name]; t0 = time.time()
    m, d = make_model(cfg['ground'], cfg['spring'], cfg.get('wall'), cfg.get('bump'), cfg.get('stone'))
    mc = motor_constants(); probe = Probe(m, d)
    sp = SPRINGS[cfg['spring']]
    travel = m.joint('travel').dofadr[0] if cfg['ground'] else -1
    mass = float(m.body_mass.sum())
    integ = 0.; rows = []; trace = []
    steps = int(round(cfg['duration'] / DT))
    for k in range(steps + 1):
        w = float(d.qvel[probe.drive_v]); target = ramp(d.time, cfg['speed'])
        # PI speed loop on the PWM duty, then the driver's current limit.
        err = target - w
        u = .6 * err + 3.0 * integ
        if -1 < u < 1:
            integ += err * DT
        u = max(-1., min(1., u))
        current = (mc['voltage'] * u - mc['ke_V_s_rad'] * w) / mc['R_ohm']
        current = max(-mc['i_limit_A'], min(mc['i_limit_A'], current))
        # Gearbox friction (the no-load current) opposes motion; at standstill it
        # opposes the motor torque, up to its size, so stall torque = kt (I - I0).
        moving = math.tanh(w / .05)
        friction = mc['i0_A'] * moving + (1 - abs(moving)) * max(-mc['i0_A'], min(mc['i0_A'], current))
        torque = mc['kt_Nm_A'] * (current - friction)
        d.ctrl[0] = torque
        if not cfg['ground']:
            side = sum(f for a, b, f in cfg.get('side', []) if a < d.time < b)
            d.xfrc_applied[probe.shoes, 1] = side / ex.TRACK_LINKS
        else:
            d.qfrc_applied[travel] = -.04 * mass * 9.81 * math.tanh(d.qvel[travel] / .005)
        if k % SAMPLE == 0:
            mujoco.mj_forward(m, d)
            ten = probe.tensions(); xz = probe.pins()
            seated, hub, guide = probe.contacts()
            q = float(d.qpos[probe.slide_q])
            spring_force = sp['k'] * (sp['springref'] - q)
            lateral = float(np.abs((d.xpos[probe.shoes] - d.xpos[probe.frame])[:, 1]).max() * 1000)
            row = dict(t=round(float(d.time), 4), target=target, speed=w, current_A=current, torque_Nm=torque, duty=u,
                       idler_mm=q * 1000, spring_N=spring_force, chain_travel_mm=probe.chain_travel(),
                       drive_angle=float(d.qpos[probe.drive_q]), max_tension_N=float(ten.max()), min_tension_N=float(ten.min()),
                       seated_bushings=seated, hub_contact_N=hub, guide_contact_N=guide, lateral_mm=lateral,
                       travel_m=float(d.qpos[m.joint('travel').qposadr[0]]) if cfg['ground'] else 0.,
                       travel_speed=float(d.qvel[travel]) if cfg['ground'] else 0., **probe.strands(ten, xz))
            if 'stone' in [m.body(i).name for i in range(m.nbody)]:
                row['stone_mm'] = (d.xpos[m.body('stone').id] * 1000).round(2).tolist()
            rows.append(row)
            if cfg.get('trace') and k % (2 * SAMPLE) == 0:
                rel = d.xpos[probe.shoes] - d.xpos[probe.frame]
                trace.append(dict(t=row['t'], drive=row['drive_angle'], idler_mm=row['idler_mm'],
                                  wheels=[float(d.qpos[m.joint(j).qposadr[0]]) for j in ['idler_spin'] + [f'roller_spin{i}' for i in range(5)]],
                                  frame=(d.xpos[probe.frame] * 1000).round(3).tolist(),
                                  shoes=np.round(rel * 1000, 3).tolist(), quats=np.round(d.xquat[probe.shoes], 5).tolist(),
                                  tension=np.round(ten, 2).tolist(), current_A=round(current, 4), stone=row.get('stone_mm')))
        if k == steps:
            break
        mujoco.mj_step(m, d)
        if k % 4000 == 0:
            print(name, f't={d.time:.2f}', f'w={w:.2f}', f'I={current:.2f}', f'idler={d.qpos[probe.slide_q] * 1000:.2f}mm', flush=True)
    report = analyse(name, cfg, rows, m, d, mc, sp, mass, time.time() - t0)
    (SIM / f'{name}.json').write_text(json.dumps(dict(report=report, samples=rows), separators=(',', ':')))
    if trace:
        (SIM / f'{name}_trace.json').write_text(json.dumps(trace, separators=(',', ':')))
    print(json.dumps(report, indent=1), flush=True)
    return report


def analyse(name, cfg, rows, m, d, mc, sp, mass, elapsed):
    t = np.array([r['t'] for r in rows]); dth = np.array([r['drive_angle'] for r in rows]) - rows[0]['drive_angle']
    travel = np.array([r['chain_travel_mm'] for r in rows]) - rows[0]['chain_travel_mm']
    sign = 1.0 if np.dot(travel, dth) >= 0 else -1.0
    slip = travel - sign * R_EFF * dth
    skips = int(np.round(np.abs(slip - np.median(slip[:5])).max() / ex.PITCH))
    def window(key, a, b, fn=np.mean):
        v = [r[key] for r in rows if a <= r['t'] <= b and not math.isnan(r[key])]
        return float(fn(v)) if v else float('nan')
    rep = dict(case=name, note=cfg['note'], spring=sp['label'], spring_rate_N_mm=sp['k'] / 1000,
               assembled_spring_force_N=round(sp['k'] * (sp['springref'] - ex.IDLER_ASSEMBLY_OFFSET * .001), 2),
               engine='MuJoCo ' + mujoco.__version__ + ' Newton', time_step_s=DT, duration_s=cfg['duration'],
               elapsed_s=round(elapsed, 1), supported_mass_kg=round(mass, 3) if cfg['ground'] else None,
               motor=dict(mc, model=GEARMOTOR['model'], rotor_inertia_kg_m2_estimate=ROTOR_INERTIA),
               max_abs_current_A=round(max(abs(r['current_A']) for r in rows), 4),
               max_abs_torque_Nm=round(max(abs(r['torque_Nm']) for r in rows), 4),
               idler_travel_mm=[round(min(r['idler_mm'] for r in rows), 3), round(max(r['idler_mm'] for r in rows), 3)],
               recoil_stop_mm=round(sp['range'][0] * 1000, 3), forward_stop_mm=round(sp['range'][1] * 1000, 3),
               max_chain_tension_N=round(max(r['max_tension_N'] for r in rows), 2),
               min_seated_bushings=int(min(r['seated_bushings'] for r in rows[5:])),
               max_hub_contact_N=round(max(r['hub_contact_N'] for r in rows), 3),
               max_lateral_drift_mm=round(max(r['lateral_mm'] for r in rows), 3),
               slip_mm=[round(float(slip.min()), 2), round(float(slip.max()), 2)], tooth_skips=skips,
               solver_warnings=int(sum(w.number for w in d.warning)), finite=bool(np.isfinite(d.qpos).all()))
    if name.startswith('fixture') or name.startswith('lateral'):
        a, b = (2.0, 5.0) if name.startswith('fixture') else (1.5, 5.0)
        rep['forward_mean_speed_rad_s'] = round(window('speed', a, b), 3)
        rep['top_strand_N'] = round(window('top', a, b), 2)
        rep['bottom_rear_strand_N'] = round(window('bottom_rear', a, b), 2)
        if name.startswith('fixture'):
            rep['reverse_mean_speed_rad_s'] = round(window('speed', 7.5, 10.5), 3)
    if name.startswith('reverse_wall'):
        a, b = 4.5, 6.0
        rep['sliding_phase'] = dict(window_s=[1.0, 4.5], min_bottom_rear_strand_N=round(window('bottom_rear', 1.0, 4.5, np.min), 2),
                                    mean_bottom_rear_strand_N=round(window('bottom_rear', 1.0, 4.5), 2),
                                    max_tension_N=round(window('max_tension_N', 1.0, 4.5, np.max), 2))
        rep['stall'] = dict(window_s=[a, b], speed_rad_s=round(window('speed', a, b), 4), current_A=round(window('current_A', a, b), 3),
                            torque_Nm=round(window('torque_Nm', a, b), 3), top_strand_N=round(window('top', a, b), 2),
                            bottom_rear_strand_N=round(window('bottom_rear', a, b), 2),
                            min_bottom_rear_strand_N=round(window('bottom_rear', a, b, np.min), 2),
                            bottom_front_strand_N=round(window('bottom_front', a, b), 2),
                            idler_mm=round(window('idler_mm', a, b), 3), spring_N=round(window('spring_N', a, b), 2),
                            predicted_slack_strand_N=round(window('spring_N', a, b) / 2 - window('torque_Nm', a, b, lambda v: abs(np.mean(v))) / (ex.PITCH_R * .001), 2))
    if name.startswith('debris'):
        rep['max_recoil_mm'] = round(-(min(r['idler_mm'] for r in rows) - ex.IDLER_ASSEMBLY_OFFSET), 3)
        rep['peak_spring_N'] = round(max(r['spring_N'] for r in rows), 2)
        rep['stone_final_mm'] = rows[-1]['stone_mm']
        rep['stone_max_height_mm'] = round(max(r['stone_mm'][2] for r in rows), 2)
        rep['pin_bending_at_peak_MPa'] = round(32 * rep['max_chain_tension_N'] * .0174 / 4 / (math.pi * .003 ** 3) / 1e6, 1)
        rep['peak_current_while_jammed_A'] = round(max(abs(r['current_A']) for r in rows if r['t'] > 1.0), 3)
    if name == 'obstacle':
        rep['bump'] = dict(x_m=cfg['bump'][0], rod_diameter_m=2 * cfg['bump'][1])
        rep['max_recoil_mm'] = round(-min(r['idler_mm'] for r in rows) + ex.IDLER_ASSEMBLY_OFFSET, 3)
        rep['travel_m'] = round(rows[-1]['travel_m'], 4)
    checks = dict(finite_and_stable=rep['finite'] and rep['solver_warnings'] == 0,
                  current_within_limit=rep['max_abs_current_A'] <= DRIVE_CURRENT_LIMIT_A + 1e-6,
                  no_tooth_skip=skips == 0, chain_on_sprocket=rep['min_seated_bushings'] >= 2,
                  no_derailment=rep['max_lateral_drift_mm'] < 3.0)
    if name.startswith('reverse_wall'):
        lo = [r['bottom_rear'] for r in rows if a <= r['t'] <= b and not math.isnan(r['bottom_rear'])]
        rep['stall']['p05_bottom_rear_strand_N'] = round(float(np.percentile(lo, 5)), 2)
        checks['slack_strand_stays_tight'] = rep['stall']['bottom_rear_strand_N'] > 2.0 and rep['stall']['p05_bottom_rear_strand_N'] > .5
        checks['drive_stalled_at_limit'] = abs(rep['stall']['current_A']) > .95 * DRIVE_CURRENT_LIMIT_A
    if name.startswith('debris'):
        checks['idler_recoils'] = rep['max_recoil_mm'] > 1.0
        checks['stop_holds'] = rep['idler_travel_mm'][0] > rep['recoil_stop_mm'] - .1
        checks['stone_passed_round_idler'] = rep['stone_max_height_mm'] > ex.AXLE_Z + 30
    if name == 'debris':
        checks['passes_on_spring_alone'] = rep['idler_travel_mm'][0] > rep['recoil_stop_mm'] + .1
    if name == 'obstacle':
        checks['recoil_within_stop'] = rep['idler_travel_mm'][0] > rep['recoil_stop_mm'] + .05
        checks['crossed_bump'] = rep['travel_m'] > cfg['bump'][0] + .15
    if name == 'fixture':
        checks['tracks_speed_forward'] = abs(rep['forward_mean_speed_rad_s'] - 3.0) < .15
        checks['tracks_speed_reverse'] = abs(rep['reverse_mean_speed_rad_s'] + 3.0) < .15
    rep['checks'] = {k: bool(v) for k, v in checks.items()}
    rep['status'] = 'PASS' if all(rep['checks'].values()) else 'FAIL'
    return rep




# ---------------------------------------------------------------- summary and figure
BLUE, ORANGE, AQUA = '#2a78d6', '#eb6834', '#1baf7a'          # categorical slots 1-3 (validated)
INK, INK2, GRID, SURFACE = '#0b0b0b', '#52514e', '#e4e3df', '#fcfcfb'


def summarise():
    reports = {}
    for n in CASES:
        p = SIM / f'{n}.json'
        if p.exists():
            reports[n] = json.loads(p.read_text())['report']
    controls = [n for n in reports if 'r4spring' in n]
    design = [n for n in reports if n not in controls]
    out = dict(design_cases_pass=all(reports[n]['status'] == 'PASS' for n in design),
               design_cases=design, negative_controls=controls,
               cases={n: {k: v for k, v in r.items() if k != 'motor'} for n, r in reports.items()},
               motor=next(iter(reports.values()))['motor'] if reports else None)
    (SIM / 'summary.json').write_text(json.dumps(out, indent=2))
    return out


def plot():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    def load(n):
        return json.loads((SIM / f'{n}.json').read_text())['samples']
    plt.rcParams.update({'font.size': 9, 'axes.edgecolor': INK2, 'axes.labelcolor': INK, 'xtick.color': INK2,
                         'ytick.color': INK2, 'axes.titlecolor': INK, 'axes.facecolor': SURFACE, 'figure.facecolor': SURFACE,
                         'axes.spines.top': False, 'axes.spines.right': False, 'lines.linewidth': 2})
    fig, ax = plt.subplots(2, 3, figsize=(13, 7.2), layout='constrained')
    def finish(a, title, xl, yl):
        a.set_title(title, loc='left', fontsize=10); a.set_xlabel(xl); a.set_ylabel(yl); a.grid(color=GRID, lw=.6)
    def label_end(a, x, y, text, color):
        a.annotate(text, (x[-1], y[-1]), xytext=(4, 0), textcoords='offset points', color=INK, fontsize=8, va='center')
    r5, r4 = load('reverse_wall'), load('reverse_wall_r4spring')
    for rows, c, lab in [(r5, BLUE, 'R5 spring, 77 N'), (r4, ORANGE, 'R4 spring, 16 N')]:
        t = [r['t'] for r in rows]; v = [r['bottom_rear'] for r in rows]
        ax[0, 0].plot(t, v, color=c, lw=1.2, label=lab)
    ax[0, 0].axhline(0, color=INK2, lw=.8)
    finish(ax[0, 0], 'Reversing into a wall: slack strand under the sprocket', 'Time (s)', 'Tension (N)')
    ax[0, 0].legend(frameon=False, loc='upper right')
    for rows, c, lab in [(r5, BLUE, 'R5 spring'), (r4, ORANGE, 'R4 spring')]:
        t = [r['t'] for r in rows]; v = [r['speed'] for r in rows]
        ax[0, 1].plot(t, v, color=c, label=lab); label_end(ax[0, 1], t, v, lab, c)
    finish(ax[0, 1], 'Same test: sprocket speed (R4 track keeps sliding)', 'Time (s)', 'Sprocket speed (rad/s)')
    ax[0, 1].legend(frameon=False, loc='center right')
    for n, c, lab in [('debris', BLUE, '4 mm stone'), ('debris_5mm', ORANGE, '5 mm stone')]:
        rows = load(n); t = [r['t'] for r in rows]; v = [-(r['idler_mm'] - ex.IDLER_ASSEMBLY_OFFSET) for r in rows]
        ax[0, 2].plot(t, v, color=c, label=lab)
    ax[0, 2].axhline(recoil_travel(), color=INK2, lw=1, ls='--')
    ax[0, 2].annotate('recoil stop 4.0 mm', (2.2, recoil_travel()), xytext=(0, 4), textcoords='offset points', color=INK2, fontsize=8)
    finish(ax[0, 2], 'Stone carried into the idler: recoil', 'Time (s)', 'Idler recoil from assembly (mm)')
    ax[0, 2].legend(frameon=False, loc='center left')
    for n, c, lab in [('debris', BLUE, '4 mm stone'), ('debris_5mm', ORANGE, '5 mm stone')]:
        rows = load(n); t = [r['t'] for r in rows]; v = [r['max_tension_N'] for r in rows]
        ax[1, 0].plot(t, v, color=c, lw=1.2, label=lab)
    finish(ax[1, 0], 'Stone test: highest pin force in the chain', 'Time (s)', 'Pin force (N)')
    ax[1, 0].legend(frameon=False, loc='upper right')
    for n, c, lab in [('lateral', BLUE, 'R5 spring'), ('lateral_r4spring', ORANGE, 'R4 spring')]:
        rows = load(n); t = [r['t'] for r in rows]; v = [r['lateral_mm'] for r in rows]
        ax[1, 1].plot(t, v, color=c, lw=1.4, label=lab); label_end(ax[1, 1], t, v, lab, c)
    for a, b in [(1.5, 3.0), (3.5, 5.0)]:
        ax[1, 1].axvspan(a, b, color=GRID, alpha=.6, lw=0)
    finish(ax[1, 1], '±20 N side pulls (shaded): chain drift', 'Time (s)', 'Largest shoe offset (mm)')
    ax[1, 1].legend(frameon=False, loc=(0.02, 0.35))
    rows = load('fixture'); t = [r['t'] for r in rows]
    ax[1, 2].plot(t, [r['target'] for r in rows], color=INK2, lw=1, ls='--', label='Command')
    ax[1, 2].plot(t, [r['speed'] for r in rows], color=BLUE, lw=1.6, label='Sprocket')
    finish(ax[1, 2], 'Stand run-in: speed loop with the DC motor model', 'Time (s)', 'Sprocket speed (rad/s)')
    ax[1, 2].legend(frameon=False, loc='lower left')
    (ROOT / 'images').mkdir(exist_ok=True)
    fig.savefig(ROOT / 'images/track_wheel_simulation.png', dpi=150); plt.close(fig)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--case', default='fixture'); a = ap.parse_args()
    if a.case == 'report':
        print(json.dumps({n: r['status'] for n, r in summarise()['cases'].items()}, indent=1)); plot()
    else:
        for n in (list(CASES) if a.case == 'all' else a.case.split(',')):
            run(n)
        summarise()

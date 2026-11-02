"""Authoritative parametric transmission; mm/radians, right-handed CAD XYZ.

An illustrative 27:1 train, NOT the unknown commercial motor tooth counts.
The output screw is Z, the front face is Z=0. Input and output are coaxial
but terminate at different Z. Compound A/B gears are rigidly united to shafts.
"""
import math

MODULE = 0.09
PRESSURE = math.radians(20)
PINION_TEETH, WHEEL_TEETH = 18, 54
THINNING = 0.004  # per gear, total circular backlash = 0.008 mm
DISTANCE = MODULE * (PINION_TEETH + WHEEL_TEETH) / 2
CENTRES = {'input': (0., 0.), 'compound_a': (-DISTANCE/2, DISTANCE*math.sqrt(3)/2),
           'compound_b': (DISTANCE/2, DISTANCE*math.sqrt(3)/2), 'output': (0., 0.)}
RATIOS = {'input': -27., 'compound_a': 9., 'compound_b': -3., 'output': 1.}
STAGES = [
    dict(id='stage_1', driver='input', driven='compound_a', zmin=-7.85, zmax=-6.95),
    dict(id='stage_2', driver='compound_a', driven='compound_b', zmin=-5.85, zmax=-4.95),
    dict(id='stage_3', driver='compound_b', driven='output', zmin=-3.85, zmax=-2.75),
]
PART_BODIES = {'motor_gear_1':'input', 'motor_gear_2':'compound_a',
               'motor_gear_3':'compound_b', 'motor_gear_4':'output',
               'motor_leadscrew_M3':'output'}


def phases():
    """One selected torque flank, with the 8 um circular backlash taken up.

    z_p*theta_p + z_w*theta_w = (z_p+z_w)*phi+z_w*pi-pi
    +/- 2*THINNING/MODULE. The sign alternates with shaft direction.
    Both teeth on each compound have the same local zero tooth centre.
    """
    ans = {'output': 0.}
    for s in reversed(STAGES):
        p, w = s['driver'], s['driven']
        a, b = CENTRES[p], CENTRES[w]
        phi = math.atan2(b[1]-a[1], b[0]-a[0])
        sign = 1 if RATIOS[p] > 0 else -1
        c = (PINION_TEETH+WHEEL_TEETH)*phi + WHEEL_TEETH*math.pi-math.pi
        c += sign * 2*THINNING/MODULE
        ans[p] = ((c-WHEEL_TEETH*ans[w])/PINION_TEETH) % (2*math.pi/PINION_TEETH)
    return ans


def transmission(screw_length=40., pitch=.5):
    phase = phases()
    bodies = {k:dict(axis_origin_mm=[*c,0.], axis_direction=[0.,0.,1.],
                    angle_per_output_rad=RATIOS[k], initial_phase_rad=phase[k],
                    phase_baked_into_geometry=True)
              for k,c in CENTRES.items()}
    return dict(schema='n20.geartrain.v1', model_status='illustrative_not_commercial_replica',
        units='mm', angles='radians', front_face_z_mm=0.,
        gearbox_envelope_mm=[[-5,-6,-9],[5,6,0]],
        output_diameter_mm=3., screw_pitch_mm=pitch, screw_length_mm=screw_length,
        total_reduction=27., signed_input_per_output=-27.,
        gear=dict(module_mm=MODULE,pressure_angle_deg=20.,pinion_teeth=18,wheel_teeth=54,
                  profile_shift=0.,addendum_modules=1.,dedendum_modules=1.25,
                  tooth_thinning_mm=THINNING,circular_backlash_mm=2*THINNING,
                  root_transition='radial relief below base circle; not a generated cutting fillet'),
        bodies=bodies, parts={name:dict(body=body,**bodies[body]) for name,body in PART_BODIES.items()},
        stages=[dict(**s,driver_teeth=18,driven_teeth=54,centre_distance_mm=DISTANCE,
                     face_overlap_mm=s['zmax']-s['zmin']) for s in STAGES],
        animation=dict(input='output_angle_rad', absolute='phase + ratio * output_angle',
                       exported_mesh_transform='rotate by ratio * output_angle about axis_origin only; phase already baked',
                       v6_mapping='CAD (x,y,z) -> viewer (z-CENTRE,y,-x)',
                       v6_output_angle='-travel_mm / screw_pitch_mm * 2*pi',
                       simulation='prescribed rigid kinematics, no torque/stress/contact dynamics'))


def involute_points(teeth, samples=16):
    """Closed CCW polygon of analytically sampled involute teeth.

    Each flank follows inv(alpha_r)=tan(alpha_r)-alpha_r; no square teeth.
    Straight radial root relief below rb is outside the active line of action.
    Polygon chord approximation is measured separately by verification.
    """
    rp=MODULE*teeth/2; rb=rp*math.cos(PRESSURE)
    ra=rp+MODULE; rf=rp-1.25*MODULE
    half=math.pi/(2*teeth)-THINNING/(2*rp)
    invp=math.tan(PRESSURE)-PRESSURE
    start=max(rb,rf)
    def offset(r):
        a=math.acos(min(1.,rb/r))
        return half+invp-(math.tan(a)-a)
    def polar(r,a): return (r*math.cos(a),r*math.sin(a))
    pts=[]
    for i in range(teeth):
        centre=2*math.pi*i/teeth
        o0=offset(start); oa=offset(ra)
        pts.append(polar(rf,centre-o0))
        for j in range(samples+1):
            # uniform involute parameter, including the base-circle cusp
            t0=math.sqrt(max(0.,(start/rb)**2-1)); t1=math.sqrt((ra/rb)**2-1)
            t=t0+(t1-t0)*j/samples; r=rb*math.sqrt(1+t*t)
            if j==0 and abs(start-rf)<1e-12: continue
            pts.append(polar(r,centre-offset(r)))
        for j in range(1,5): pts.append(polar(ra,centre-oa+2*oa*j/4))
        for j in range(samples-1,-1,-1):
            t=t0+(t1-t0)*j/samples; r=rb*math.sqrt(1+t*t)
            pts.append(polar(r,centre+offset(r)))
        if rf<start-1e-12: pts.append(polar(rf,centre+o0))
        end=centre+2*math.pi/teeth-o0
        for j in range(1,5): pts.append(polar(rf,centre+o0+(end-centre-o0)*j/5))
    return pts

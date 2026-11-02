"""Whole-arm MuJoCo model: real joint topology, CAD inertias and four independent powered slides.
SI units. Printed density and motor internals are explicit modeling assumptions.
"""
from pathlib import Path
import json,math
import numpy as np
from kinematics import *
ROOT=Path(__file__).resolve().parents[1]
SIM=ROOT/'simulation'
PETG_DENSITY=1.27e-6  # kg/mm^3 of modeled solid, including hollow-wall geometry
STEEL_DENSITY=7.85e-6
INTERNAL_MASS=.035  # kg per U60; procurement value not measured
FORCE_LIMIT=100.0  # N, scenario parameter; NOT a certified actuator rating
MOTOR_ROTOR_INERTIA=1e-8  # kg m^2, assumed small N20 rotor
GEAR_RATIO=60.  # assumed 9000 rpm motor / 150 rpm screw
REFLECTED_SLIDE_MASS=MOTOR_ROTOR_INERTIA*(GEAR_RATIO*2*math.pi/.0005)**2
NO_LOAD_SPEED=.00125  # m/s = 150 rpm * .5 mm lead / 60


def export_mass_properties():
    from build_arm import structures,hardware,load_actuators,one,cq
    items={};allparts={**structures(),**hardware()};acts=load_actuators()
    def add(group,name,shape,density):
        solid=one(shape);mass=solid.Volume()*density;c=solid.Center()
        item=dict(name=name,mass_kg=mass,centre_mm=[c.x,c.y,c.z],inertia_kg_mm2=(np.array(cq.Shape.matrixOfInertia(solid))*density).tolist())
        items.setdefault(group,[]).append(item)
    for name,p in allparts.items():add(p['group'],name,p['shape'],PETG_DENSITY if p['kind']=='printed' else STEEL_DENSITY)
    for drive in DRIVES:
        role=drive['role'];label=drive['name']
        for name,shape in acts[role].items():
            group=label+('_rod' if name.startswith(('04','05')) else '_cylinder')
            add(group,label+'_V6_'+name,shape.translate((0,0,37.5)),PETG_DENSITY)
        mass=INTERNAL_MASS;radius=8.;length=35.
        inertia=np.diag([mass*(3*radius**2+length**2)/12]*2+[mass*radius**2/2])
        items[label+'_cylinder'].append(dict(name=label+'_internal_mass_assumption',mass_kg=mass,centre_mm=[0,0,27.5],inertia_kg_mm2=inertia.tolist()))
    result={}
    for group,rows in items.items():
        m=sum(d['mass_kg'] for d in rows);c=sum(d['mass_kg']*np.array(d['centre_mm']) for d in rows)/m;I=np.zeros((3,3))
        for d in rows:
            delta=np.array(d['centre_mm'])-c;I+=np.array(d['inertia_kg_mm2'])+d['mass_kg']*(np.dot(delta,delta)*np.eye(3)-np.outer(delta,delta))
        I*=1e-6
        assert min(np.linalg.eigvalsh(I))>0
        result[group]=dict(mass_kg=m,centre_m=(c*.001).tolist(),fullinertia_kg_m2=[float(I[i,j]) for i,j in [(0,0),(1,1),(2,2),(0,1),(0,2),(1,2)]],components=rows)
    SIM.mkdir(exist_ok=True)
    payload=dict(groups=result,total_mass_kg=sum(d['mass_kg'] for d in result.values()),moving_mass_kg=sum(d['mass_kg'] for n,d in result.items() if n!='base'),
        assumptions=dict(printed_density_kg_m3=1270,steel_density_kg_m3=7850,internal_mass_kg_per_actuator=INTERNAL_MASS,description='Modeled PETG solid volume, steel pins/spacers/collars/screws/nuts; all actuator exterior bodies are printed polymer. 35 g internal mass per actuator is assumed. No measured print masses or motor force-speed curve.'))
    (SIM/'mass_properties.json').write_text(json.dumps(payload,indent=2)+'\n');return payload


def fmt(values):return ' '.join(f'{float(v):.12g}' for v in values)
def xyz(point,y=0):return fmt([point[0]*.001,y*.001,point[1]*.001])


def model_xml(payload_kg=0.,force_limit=FORCE_LIMIT,timestep=.002):
    data=json.loads((SIM/'mass_properties.json').read_text())['groups']
    def inertia(group):
        d=data[group];return f'<inertial pos="{fmt(d["centre_m"])}" mass="{d["mass_kg"]}" fullinertia="{fmt(d["fullinertia_kg_m2"])}"/>'
    def hinge(name,limits=None):
        limit=f'limited="true" range="{fmt(limits)}"' if limits is not None else 'limited="false"'
        return f'<joint name="{name}" type="hinge" axis="0 -1 0" {limit} damping=".002" frictionloss=".001"/>'
    def site(name,p,y=0):return f'<site name="{name}" pos="{xyz(p,y)}" size=".001"/>'
    def actuator(label,point):
        drive=DRIVE_BY_NAME[label]
        return f'''<body name="{label}_cylinder" pos="{xyz(point,drive['y'])}">{hinge(label+'_swivel')}{inertia(label+'_cylinder')}
          <body name="{label}_rod"><joint name="{label}_slide" type="slide" axis="0 0 1" armature="{REFLECTED_SLIDE_MASS}" range="0 .06" limited="true" damping="2" frictionloss=".1" solreflimit=".004 1"/>{inertia(label+'_rod')}
          <site name="{label}_eye" pos="0 0 .140" size=".001"/></body></body>'''
    payload=f'<body name="example_payload" pos="-.025 0 -.05"><inertial mass="{payload_kg}" pos="0 0 0" diaginertia="{fmt([max(payload_kg*.02**2/6,1e-9)]*3)}"/></body>' if payload_kg else ''
    boom_eyes=''.join(site(d['name']+'_target',BOOM_LIFT,d['y']) for d in DRIVES if d['role']=='boom')
    body=f'''<body name="boom" pos="{xyz(ORIGIN)}">{hinge('boom_angle',np.radians([-30,80]))}{inertia('boom')}{boom_eyes}
      {actuator('stick0',STICK_CYL)}
      <body name="stick" pos="{xyz([BOOM,0])}">{hinge('stick_angle',np.radians([-155,-35]))}{inertia('stick')}
       {site('stick0_target',STICK_TAIL)}{actuator('bucket0',BUCKET_CYL)}
       <body name="bucket" pos="{xyz([STICK,0])}">{hinge('bucket_angle',np.radians([-5,145]))}{inertia('bucket')}{site('Q_bucket',HORN_POINT)}{site('tooth_tip',TIP)}{payload}</body>
       <body name="rocker" pos="{xyz(ROCKER_PIVOT)}">{hinge('rocker_angle')}{inertia('rocker')}{site('bucket0_target',[ROCKER,0])}
        <body name="coupler" pos="{xyz([ROCKER,0])}">{hinge('coupler_angle')}{inertia('coupler')}{site('Q_coupler',[COUPLER,0])}</body>
       </body>
      </body>
     </body>'''
    world=''.join(actuator(d['name'],GROUND_CYL) for d in DRIVES if d['role']=='boom')+body
    connections=''.join(f'<connect name="{d["name"]}_pin" site1="{d["name"]}_eye" site2="{d["name"]}_target" solref=".004 1" solimp=".999 .9999 .0001"/>' for d in DRIVES)
    connections+='<connect name="bucket_four_bar" site1="Q_coupler" site2="Q_bucket" solref=".004 1" solimp=".999 .9999 .0001"/>'
    motors=''.join(f'<general name="{d["name"]}_drive" joint="{d["name"]}_slide" gaintype="fixed" gainprm="{force_limit}" biastype="affine" biasprm="0 0 {-force_limit/NO_LOAD_SPEED}" ctrllimited="true" ctrlrange="-1 1" forcelimited="true" forcerange="{-force_limit} {force_limit}"/>' for d in DRIVES)
    return f'''<mujoco model="R10_dual_boom_fixed_arm"><compiler angle="radian" autolimits="true"/><option timestep="{timestep}" gravity="0 0 -9.81" integrator="implicitfast" solver="Newton" iterations="100" tolerance="1e-10"/><size njmax="8000"/><default><joint armature=".000001"/></default><worldbody>{world}</worldbody><equality>{connections}</equality><actuator>{motors}</actuator></mujoco>'''


def set_initial_pose(model,data,strokes=None):
    import mujoco
    strokes=default_strokes() if strokes is None else strokes;s=solve(strokes)
    values={'boom_angle':s['theta'],'stick_angle':s['phi'],'bucket_angle':s['gamma'],'rocker_angle':s['alpha'],'coupler_angle':s['angles']['coupler']-s['angles']['rocker']}
    for drive in DRIVES:
        role=drive['role'];label=drive['name'];a,b=drive['a'],drive['b']
        parent={'boom':0.,'stick':s['theta'],'bucket':s['angles']['stick']}[role]
        direction=s['points'][b]-s['points'][a]
        values[label+'_swivel']=math.atan2(direction[1],direction[0])-parent-math.pi/2
        values[label+'_slide']=strokes[drive['axis']]*.001
    for name,value in values.items():data.qpos[model.joint(name).qposadr[0]]=value
    data.qvel[:]=0;mujoco.mj_forward(model,data)
    return s


if __name__=='__main__':
    import mujoco
    m=export_mass_properties();print('Mass kg:',m['total_mass_kg'],'moving',m['moving_mass_kg'])
    xml=model_xml();(SIM/'arm_r10.xml').write_text(xml)
    model=mujoco.MjModel.from_xml_string(xml);data=mujoco.MjData(model);s=set_initial_pose(model,data)
    print('qpos',model.nq,'dofs',model.nv,'constraints',data.nefc,'max closure m',np.max(np.abs(data.efc_pos[:model.neq*3])))
    print('tip kinematic',s['points']['T']*.001,'dynamic',data.site_xpos[model.site('tooth_tip').id])

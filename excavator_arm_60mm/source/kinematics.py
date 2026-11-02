"""Cat 320 reference proportions at 1:15 with a common 60 mm stroke, adapted V6 electric cylinders.
Factory dimensions: boom 5700, stick 2900, HD bucket 1200 wide, tip radius 1570 mm.
Pin placements and section outlines are engineering adaptations from cited imagery.
Coordinates: X forward, Z up, all hinge axes parallel to Y. No chassis.
"""
import math
import numpy as np
SCALE=15.0
BOOM=5700/SCALE
STICK=2900/SCALE
BUCKET_WIDTH=1200/SCALE
TIP_RADIUS=1570/SCALE
TIP=np.array([-83.2,-math.sqrt(TIP_RADIUS**2-83.2**2)])
ORIGIN=np.array([0.,88.])
GROUND_CYL=np.array([47.27671302,55.77085044])
BOOM_LIFT=np.array([150.,60.])
STICK_CYL=np.array([BOOM-150.,88.])
STICK_TAIL=np.array([-40.,8.])
BUCKET_CYL=np.array([STICK-206.66666666666666,36.])
ROCKER_PIVOT=np.array([STICK-49.66666666666666,16.])
ROCKER=52.0
COUPLER=65.0
HORN=35.0
HORN_DATUM=math.radians(-20.)
HORN_POINT=HORN*np.array([math.cos(HORN_DATUM),math.sin(HORN_DATUM)])
PITCH=.5
ACTUATORS={role:dict(variant='U60',screw=75.,closed=140.,stroke=60.,quantity=2 if role=='boom' else 1,y=[-42.,42.] if role=='boom' else [0.]) for role in ['boom','stick','bucket']}
ORDER=['boom','stick','bucket']
CLOSED=np.array([ACTUATORS[k]['closed'] for k in ORDER])
STROKES=np.array([ACTUATORS[k]['stroke'] for k in ORDER])


def rot(a):return np.array([[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]])

def angle_for_length(anchor,moving,length,branch):
    a,b=np.linalg.norm(anchor),np.linalg.norm(moving)
    c=(a*a+b*b-length*length)/(2*a*b)
    if not -1<=c<=1:raise ValueError(f'Cylinder cannot close: {length}, cosine {c}')
    return math.atan2(anchor[1],anchor[0])-math.atan2(moving[1],moving[0])+branch*math.acos(c)


def default_strokes():
    # Pose close to the manufacturer's unobstructed side reference: boom 31 deg,
    # stick -114 deg relative to boom, rocker 94 deg relative to stick.
    return [float(np.linalg.norm(rot(math.radians(a))@p-b)-c) for a,p,b,c in
            [(31,BOOM_LIFT,GROUND_CYL-ORIGIN,CLOSED[0]),
             (-114,STICK_TAIL,STICK_CYL-[BOOM,0],CLOSED[1]),
             (94,np.array([ROCKER,0]),BUCKET_CYL-ROCKER_PIVOT,CLOSED[2])]]


def solve(strokes=None):
    strokes=default_strokes() if strokes is None else strokes
    lb,ls,lk=CLOSED+np.array(strokes)
    theta=angle_for_length(GROUND_CYL-ORIGIN,BOOM_LIFT,lb,1)
    phi=angle_for_length(STICK_CYL-[BOOM,0],STICK_TAIL,ls,-1)
    alpha=angle_for_length(BUCKET_CYL-ROCKER_PIVOT,np.array([ROCKER,0]),lk,-1)
    r=ROCKER_PIVOT+rot(alpha)@np.array([ROCKER,0]);h=np.array([STICK,0])
    v=r-h;distance=np.linalg.norm(v);u=v/distance
    along=(HORN**2-COUPLER**2+distance**2)/(2*distance)
    height=math.sqrt(HORN**2-along**2)
    q=h+along*u-height*np.array([-u[1],u[0]])
    beta=math.atan2(q[1],q[0]-STICK);gamma=beta-HORN_DATUM
    rb,rs=rot(theta),rot(theta+phi);e=ORIGIN+rb@np.array([BOOM,0]);wrist=e+rs@h
    p={'O':ORIGIN.copy(),'A':GROUND_CYL.copy(),'B':ORIGIN+rb@BOOM_LIFT,'E':e,
       'C':ORIGIN+rb@STICK_CYL,'D':e+rs@STICK_TAIL,'F':e+rs@BUCKET_CYL,
       'J':e+rs@ROCKER_PIVOT,'R':e+rs@r,'H':wrist,'Q':e+rs@q}
    p['T']=wrist+rot(theta+phi+gamma)@TIP
    return dict(strokes=list(strokes),theta=theta,phi=phi,alpha=alpha,beta=beta,gamma=gamma,points=p,
        origins={'base':np.array([0.,0.]),'boom':ORIGIN,'stick':e,'bucket':wrist,'rocker':p['J'],'coupler':p['R']},
        angles={'base':0.,'boom':theta,'stick':theta+phi,'bucket':theta+phi+gamma,'rocker':theta+phi+alpha,
                'coupler':math.atan2(*(p['Q']-p['R'])[::-1])})


def transmission(strokes):
    s=solve(strokes);out={};eps=1e-4
    for i,(n,a) in enumerate([('boom','theta'),('stick','phi'),('bucket','gamma')]):
        p,m=list(strokes),list(strokes);p[i]+=eps;m[i]-=eps
        derivative=(solve(p)[a]-solve(m)[a])/(2*eps)
        out[n]={'degrees_per_mm':math.degrees(derivative),'effective_moment_arm_mm':1/abs(derivative)}
    u=(s['points']['R']-s['points']['Q'])/COUPLER;v=(s['points']['Q']-s['points']['H'])/HORN
    out['four_bar_transmission_angle_deg']=math.degrees(math.acos(np.clip(abs(np.dot(u,v)),0,1)))
    return out


def config():
    return dict(scale=SCALE,boom=BOOM,stick=STICK,bucket_width=BUCKET_WIDTH,tip_radius=TIP_RADIUS,tip=TIP.tolist(),
      origin=ORIGIN.tolist(),ground_cyl=GROUND_CYL.tolist(),boom_lift=BOOM_LIFT.tolist(),stick_cyl=STICK_CYL.tolist(),
      stick_tail=STICK_TAIL.tolist(),bucket_cyl=BUCKET_CYL.tolist(),rocker_pivot=ROCKER_PIVOT.tolist(),
      rocker=ROCKER,coupler=COUPLER,horn=HORN,horn_datum=HORN_DATUM,horn_point=HORN_POINT.tolist(),
      actuators=ACTUATORS,closed=CLOSED.tolist(),strokes=STROKES.tolist(),default=default_strokes(),pitch=PITCH)

if __name__=='__main__':
    import json
    print(json.dumps(config(),indent=2))
    for st in [np.zeros(3),STROKES,default_strokes()]:
        s=solve(st);print(st,{k:round(math.degrees(s[k]),2) for k in ['theta','phi','gamma']},s['points']['T'],transmission(st))

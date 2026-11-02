"""Constrained tool path for the R10 dual-drive boomerang boom."""
from pathlib import Path
import json, math, hashlib
import numpy as np
from scipy.optimize import brentq
import kinematics as k
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent

def inverse(H,psi):
    v=np.asarray(H)-k.ORIGIN;c=(v@v-k.BOOM**2-k.STICK**2)/(2*k.BOOM*k.STICK)
    if not -1<=c<=1:raise ValueError('Unreachable wrist')
    phi=-math.acos(c);theta=math.atan2(v[1],v[0])-math.atan2(k.STICK*math.sin(phi),k.BOOM+k.STICK*math.cos(phi));gamma=psi-theta-phi
    strokes=[np.linalg.norm(k.rot(theta)@k.BOOM_LIFT-(k.GROUND_CYL-k.ORIGIN))-140,np.linalg.norm(k.rot(phi)@k.STICK_TAIL-(k.STICK_CYL-[k.BOOM,0]))-140,brentq(lambda x:k.solve([30,30,x])['gamma']-gamma,0,60)]
    if not all(0<=x<=60 for x in strokes):raise ValueError(('Stroke limit',strokes))
    return [float(x) for x in strokes]

def wrist(T,psi=0):return np.array(T)-k.rot(math.radians(psi))@k.TIP
A=wrist([360,30]);B=wrist([360,-240]);C=wrist([270,-240]);D=np.array([350.,250.])
phases=[
 dict(id='ready',duration=3,title='结构 / 双推杆与回旋镖形大臂',body='左右两根大臂推杆共同驱动。大臂中段截面加深，两端收窄，根部主铰点高度保持 88 mm。',a=A,b=A,pa=0,pb=0),
 dict(id='lower',duration=8,title='01 / 协调下放',body='齿尖垂直下放，斗杆与铲斗同时补偿。保持铲斗角度，先把切削位置对准。',a=A,b=B,pa=0,pb=0),
 dict(id='cut',duration=7,title='02 / 向机身收挖',body='齿尖向机身水平移动 90 mm，保持切削高度和铲斗角度；不是逐轴随意扫动。',a=B,b=C,pa=0,pb=0),
 dict(id='curl',duration=5,title='03 / 收斗',body='保持铲斗主销 H 的位置，转动铲斗，使开口更朝上，为抬升做好准备。',a=C,b=C,pa=0,pb=-30),
 dict(id='lift',duration=10,title='04 / 保姿抬升',body='大臂、斗杆与铲斗协调运动。铲斗绝对角保持 −30°，提升到明确的卸料位置。',a=C,b=D,pa=-30,pb=-30),
 dict(id='dump',duration=7,title='05 / 到位翻斗',body='保持 O–E–H 机构位置，只翻转铲斗。翻斗过程中，齿尖始终高于安装面。',a=D,b=D,pa=-30,pb=70),
 dict(id='reset_bucket',duration=4,title='06 / 收回铲斗姿态',body='先在高位复位铲斗，再回到起点。避免在过低的位置直接向下翻斗。',a=D,b=D,pa=70,pb=0),
 dict(id='return',duration=7,title='07 / 返回起点',body='协调大臂、斗杆与铲斗，在安装面上方返回。下一版应先满足这一类轨迹约束。',a=D,b=A,pa=0,pb=0),
 dict(id='end',duration=3,title='完成一个作业循环',body='两根大臂推杆、斗杆和铲斗推杆完成协调运动。左右推杆采用相同行程目标，各自受力、积分和反馈。',a=A,b=A,pa=0,pb=0),
]
t=0
for p in phases:p['start']=t;t+=p['duration'];p['end']=t
DURATION=t

def target(t):
    p=next((p for p in phases if t<p['end']),phases[-1]);u=np.clip((t-p['start'])/p['duration'],0,1);u=u*u*(3-2*u)
    H=p['a']+(p['b']-p['a'])*u;psi=math.radians(p['pa']+(p['pb']-p['pa'])*u)
    return p,H,psi

def main():
    frames=[];max_tip=max_angle=0.;by_phase={p['id']:[] for p in phases}
    for i in range(DURATION*48+1):
        t=i/48;p,H,psi=target(t);st=inverse(H,psi);s=k.solve(st);T=H+k.rot(psi)@k.TIP
        max_tip=max(max_tip,np.linalg.norm(T-s['points']['T']));max_angle=max(max_angle,abs(s['angles']['bucket']-psi))
        row=dict(t=t,phase=p['id'],strokes=st,tip=s['points']['T'].tolist(),wrist=H.tolist(),bucket_angle_deg=math.degrees(psi));frames.append(row);by_phase[p['id']].append(row)
    for name,axis,value in [('cut',1,-240.),('lower',0,360.)]:assert max(abs(f['tip'][axis]-value) for f in by_phase[name])<1e-7
    assert max(abs(f['bucket_angle_deg']+30) for f in by_phase['lift'])<1e-9
    for name in ['curl','dump','reset_bucket']:assert np.max(np.ptp(np.array([f['wrist'] for f in by_phase[name]]),axis=0))<1e-8
    assert min(f['tip'][1] for f in by_phase['dump'])>140
    assert np.linalg.norm(np.array(frames[0]['tip'])-frames[-1]['tip'])<1e-8
    # Review the actual linear stroke interpolation used by the browser, between samples.
    mid_error=0.;mid_angle=0.
    for a,b in zip(frames,frames[1:]):
        q=k.solve((np.array(a['strokes'])+b['strokes'])/2);_,H,psi=target((a['t']+b['t'])/2)
        mid_error=max(mid_error,np.linalg.norm(q['points']['T']-(H+k.rot(psi)@k.TIP)));mid_angle=max(mid_angle,abs(q['angles']['bucket']-psi))
    assert mid_error<.01 and math.degrees(mid_angle)<.01
    public=[{a:b for a,b in p.items() if a not in ['a','b','pa','pb']} for p in phases]
    data=dict(duration=DURATION,phases=public,frames=frames)
    (ROOT/'motion.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
    report=dict(status='PASS',scope='Kinematic task constraints only. No new forward dynamics, soil or load claim.',geometry_baseline='R10 deeper tapered boomerang section; two symmetric boom drives; retained R9 pivot coordinates',root_xz_mm=k.ORIGIN.tolist(),boom_actuation='Extension raises; retraction lowers',samples=len(frames),max_tool_pose_error_mm=float(max_tip),max_tool_angle_error_deg=math.degrees(max_angle),browser_interpolation_error_mm=float(mid_error),browser_interpolation_angle_error_deg=math.degrees(mid_angle),stroke_ranges_mm=np.array([f['strokes'] for f in frames]).T.tolist(),checks=['Constant-X lowering','90 mm inward horizontal cut at Z=-240 mm','Curl at fixed wrist','Lift with bucket absolute angle held at -30 degrees','Dump at fixed wrist with tip Z>140 mm','Return above mounting plane and close the cycle'],dump_min_tip_z_mm=min(f['tip'][1] for f in by_phase['dump']),source_sha256={n:hashlib.sha256((ROOT/'source'/n).read_bytes()).hexdigest() for n in ['build_motion.py','kinematics.py']})
    report['stroke_ranges_mm']=[[min(a),max(a)] for a in report['stroke_ranges_mm']]
    (ROOT/'motion_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()

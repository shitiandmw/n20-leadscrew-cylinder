// Original arm60 linkage solver; shared by physics and rendering.
import { CONFIG } from './config.js';
const C = CONFIG.arm;
const add=(a,b)=>[a[0]+b[0],a[1]+b[1]],sub=(a,b)=>[a[0]-b[0],a[1]-b[1]],mul=(a,s)=>[a[0]*s,a[1]*s],norm=a=>Math.hypot(...a),rot=(v,a)=>[v[0]*Math.cos(a)-v[1]*Math.sin(a),v[0]*Math.sin(a)+v[1]*Math.cos(a)];
function triangle(a,b,l,branch){return Math.atan2(a[1],a[0])-Math.atan2(b[1],b[0])+branch*Math.acos((norm(a)**2+norm(b)**2-l*l)/(2*norm(a)*norm(b)));}
function solve(s){const theta=triangle(sub(C.ground_cyl,C.origin),C.boom_lift,C.closed[0]+s[0],1),phi=triangle(sub(C.stick_cyl,[C.boom,0]),C.stick_tail,C.closed[1]+s[1],-1),alpha=triangle(sub(C.bucket_cyl,C.rocker_pivot),[C.rocker,0],C.closed[2]+s[2],-1),r=add(C.rocker_pivot,rot([C.rocker,0],alpha)),v=sub(r,[C.stick,0]),d=norm(v),u=mul(v,1/d),t=(C.horn**2-C.coupler**2+d*d)/(2*d),h=Math.sqrt(C.horn**2-t*t),q=add(add([C.stick,0],mul(u,t)),mul([-u[1],u[0]],-h)),beta=Math.atan2(q[1],q[0]-C.stick),gamma=beta-C.horn_datum;
const O=C.origin,E=add(O,rot([C.boom,0],theta)),H=add(E,rot([C.stick,0],theta+phi)),p={O,A:C.ground_cyl,B:add(O,rot(C.boom_lift,theta)),E,C:add(O,rot(C.stick_cyl,theta)),D:add(E,rot(C.stick_tail,theta+phi)),F:add(E,rot(C.bucket_cyl,theta+phi)),J:add(E,rot(C.rocker_pivot,theta+phi)),R:add(E,rot(r,theta+phi)),H,Q:add(E,rot(q,theta+phi))};p.T=add(H,rot(C.tip,theta+phi+gamma));
const uv=mul(sub(p.R,p.Q),1/C.coupler),vv=mul(sub(p.Q,p.H),1/C.horn),mu=Math.acos(Math.min(1,Math.abs(uv[0]*vv[0]+uv[1]*vv[1])))*180/Math.PI;
return {p,theta,phi,alpha,gamma,mu,origins:{base:[0,0],boom:O,stick:E,bucket:H,rocker:p.J,coupler:p.R},angles:{base:0,boom:theta,stick:theta+phi,bucket:theta+phi+gamma,rocker:theta+phi+alpha,coupler:Math.atan2(p.Q[1]-p.R[1],p.Q[0]-p.R[0])}};}

export { solve };

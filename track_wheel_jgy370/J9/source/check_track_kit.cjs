// Exercise the offline installation animation (install_animation.html) in Chromium and save a few screenshots.
// Checks, in all three modes (left track, mirrored right track, both on X101) and at the start and end of every step:
//   which parts are shown (a part appears in its own step and stays), where they end up (every part back at its CAD pose,
//   except the idler slide resting 12 mm forward between the tensioner and chain steps), the chain links, the spring length,
//   the spring cut-away, label placement (inside the view, no overlaps), skip logic for the X101-only step, playback,
//   click-to-identify, the parts-list tab, no console errors, no network access and an English-only interface.
// The chain step is also sampled densely (about 2400 times per mode, without rendering) against the way a track goes on,
//   J9/ASSEMBLY.md 7, and against the solid parts themselves (no sleeve, screw, nut or dummy pin through a link, no link through
//   another, sections of the CAD shoe): see chainCheck below. Its time-windowed labels are checked in the middle of their windows.
// Run: NODE_PATH=<playwright node_modules> node track_wheel_jgy370/J9/source/check_track_kit.cjs
// Options for a quick trial on another copy of the page: [path.html] --modes=left,right,x1 --no-write (no report, no screenshots)
// --chain-only (only the chain step's sampled checks and labels). Negative tests are copies of the page with one fault put in
// (a nut that runs on before its screw is home, a sleeve slid along the screw through the Ø3.2 holes): they must fail.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),crypto=require('crypto'),zlib=require('zlib');
const root=path.resolve(__dirname,'..'),args=process.argv.slice(2),write=!args.includes('--no-write');
const html=path.resolve(args.find(a=>!a.startsWith('--'))||path.join(root,'install_animation.html'));
const chainOnly=args.includes('--chain-only');
const onlyModes=(args.find(a=>a.startsWith('--modes='))||'--modes=left,right,x1').slice(8).split(',');
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const errors=[],network=[],problems=[];const fail=m=>{problems.push(m);console.log('FAIL',m)};
const near=(a,b,tol=1e-6)=>Math.abs(a-b)<=tol;
const SHOT_MS=900000;   // a screenshot under SwiftShader can take minutes when other jobs load the machine
// The step that fits each part, written here from J9/ASSEMBLY.md and X1/ASSEMBLY.md 3 (not read from the page), so that a part
// put in the wrong step in the page's data is caught.
const FITTED_IN=[[/^(J901_H_frame|insert_M3_\d|6800ZZ_\w+)$/,'frame'],[/^(JGY370_\w+|motor_screw_M3x6_\d)$/,'motor'],
 [/^(J904_roller_|624ZZ_|bolt_M4x70_|nyloc_M4_)(road|support)\d/,'rollers'],
 [/^(J906_idler_wheel|608ZZ_\d_\w+|J907_idler_spacer_\d|J908_U_yoke|idler_pin_8x55|recoil_spring)$/,'tensioner'],
 [/^(J909_housing|housing_screw_M3x8_\d)$/,'housing'],[/^(J902_sprocket|flange_coupling_32|hub_screw_M3x20_\d|hub_set_screw_M3x\d)$/,'sprocket'],
 [/^(J903_journal_plug|sprocket_screw_M3x50)$/,'plug']];
// ------------------------------------------------------------------ the chain goes on as J9/ASSEMBLY.md 7 describes
// Written here from the guide, with the CAD geometry read from j9_scene.json.gz (not from the page). First the links are joined into
// one flat strip, level on the bench, with one joint open (its ends are the strip's two ends); no link is bent before that, and the
// track is down on the strip before any joint bends. From then on every joint but the open one stays joined, and no link goes below
// the bench, inside the finished loop, inside the sprocket's pitch circle, into a roller or into the idler's rim. (The idler, resting
// forward over the flat strip or held back at its stop, is up to 1 mm into the sleeves' running path: the real track rides up on it
// that much. The largest such overlap is reported.) The last screw appears only when the two open ends meet, goes in along its own
// axis from outboard while the idler is held at its recoil stop, and is home before the idler is released. At the end every link,
// screw, sleeve and nut is at its CAD pose, the idler at its running position and the track down.
// Solid parts may not pass through each other (see the slab model below): no sleeve, screw, nut or dummy pin through a link, no
// link through another; joined links only bend as far as their plates and shoes allow. Each joint goes together in an order a person
// can follow: its sleeve is between the inner ears before its screw (or the dummy pin) enters, and stays put once something is
// through it; on the track (any link not flat on the bench) every sleeve is held by its screw or, at the open joint, by the dummy pin;
// a nut goes on only when its screw is home, from inboard, along the screw, and never past its seat; the dummy pin stays inside the
// inner ears while the ends meet, is pushed out by the last screw and is taken away only once it is clear of the seat bosses.
// The lock screw (J901/J908 lock-pin holes) is in only while the idler is at its recoil stop: it goes in along the hole's axis in
// the outer wall after the idler has been pushed back, and is out again before the idler is released.
const J9=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(__dirname,'j9_scene.json.gz'))));
const G=J9.config,PIN=G.pins,NL=PIN.length,ZB=Math.min(...PIN.map(p=>p[1])),BUSH=3;
const TH=PIN.map((a,j)=>{const b=PIN[(j+1)%NL];return Math.atan2(b[1]-a[1],b[0]-a[0])});
const ang=(a,b)=>{let d=(a-b)%(2*Math.PI);if(d>Math.PI)d-=2*Math.PI;if(d<=-Math.PI)d+=2*Math.PI;return Math.abs(d)};
const wrap=d=>{d=d%(2*Math.PI);if(d>Math.PI)d-=2*Math.PI;if(d<=-Math.PI)d+=2*Math.PI;return d};
function hull2(p){p=[...new Map(p.map(q=>[q.join(),q])).values()].sort((a,b)=>a[0]-b[0]||a[1]-b[1]);const c=(o,a,b)=>(a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0]),lo=[],up=[];
 for(const q of p){while(lo.length>1&&c(lo[lo.length-2],lo[lo.length-1],q)<=0)lo.pop();lo.push(q)}for(const q of p.reverse()){while(up.length>1&&c(up[up.length-2],up[up.length-1],q)<=0)up.pop();up.push(q)}
 return lo.slice(0,-1).concat(up.slice(0,-1))}
const SHOE=hull2(J9.link[0].vertices.map(v=>[v[0],v[2]]));   // the shoe's outline seen along the pins
const RIM=Math.max(...J9.unit.find(p=>p.name==='J906_idler_wheel').vertices.filter(v=>Math.abs(v[1])<8.6).map(v=>Math.hypot(v[0]-G.idler[0],v[2]-G.idler[1])));
const segD=(p,a,b)=>{const dx=b[0]-a[0],dz=b[1]-a[1],u=Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dz)/(dx*dx+dz*dz)));return Math.hypot(p[0]-a[0]-u*dx,p[1]-a[1]-u*dz)};
function loopDist(p){let d=Infinity,inside=false;for(let i=0,j=NL-1;i<NL;j=i++){const a=PIN[i],b=PIN[j];d=Math.min(d,segD(p,a,b));
 if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])inside=!inside}return inside?-d:d}
// ------------------------------------------------------------------ the shoe in Y slabs, for the overlap tests
// The J910 shoe is a union of pieces extruded along the pins (shoe plate and grousers, inner ears, outer plates and their seat
// bosses; two small holes through the plate), so its section halfway between two consecutive vertex Y values holds for that whole
// Y interval. (Revision B has four lead-in chamfers, 0.8 to 1.1 mm wide; across each of them the section is taken at mid-width.) Links only
// turn about Y and the joint hardware is Y-aligned cylinders, so every overlap is a 2-D test in each shared Y interval. The thin
// intervals across the two plate holes are left out: their sections lie inside the plain plate's, so the test stays conservative.
const SV=J9.link[0].vertices,ST=J9.link[0].triangles,TOL=.05;
const SLABS=(()=>{const ys=[...new Set(SV.map(v=>Math.round(v[1]*1000)/1000))].sort((a,b)=>a-b),all=[];
 for(let i=0;i+1<ys.length;i++){const y0=ys[i],y1=ys[i+1],ym=(y0+y1)/2,segs=[];
  for(const t of ST){const q=t.map(k=>SV[k]),pts=[];for(let k=0;k<3;k++){const a=q[k],b=q[(k+1)%3],sa=a[1]-ym,sb=b[1]-ym;
    if((sa<0)!==(sb<0)){const f=sa/(sa-sb);pts.push([a[0]+f*(b[0]-a[0]),a[2]+f*(b[2]-a[2])])}}
   if(pts.length===2)segs.push([pts[0][0],pts[0][1],pts[1][0],pts[1][1]])}
  all.push({y0,y1,...section(segs)})}
 const thick=all.filter(S=>S.y1-S.y0>=.25),byKey=new Map();
 // a thin interval (the edge of a plate hole, the end of a chamfer) is left out. Its section must lie inside the section of the
 // thick slab next below it or next above it, so that whatever would overlap it also overlaps that slab.
 const within=(S,T)=>{if(!T)return false;for(let i=0;i<S.p.length;i+=2)if(!inside(T,S.p[i],S.p[i+1])&&edgeD(T,S.p[i],S.p[i+1])>.01)return false;return true};
 for(const S of all.filter(S=>S.y1-S.y0<.25)){const below=thick.filter(T=>T.y1<=S.y0+1e-9).pop(),above=thick.find(T=>T.y0>=S.y1-1e-9);
  if(!within(S,below)&&!within(S,above))throw new Error(`thin shoe slab ${S.y0}..${S.y1} is not inside the section of the slab next to it`)}
 for(const S of thick){const k=Array.from(S.a,v=>v.toFixed(3)).join();if(!byKey.has(k))byKey.set(k,{...S,ys:[]});byKey.get(k).ys.push([S.y0,S.y1])}
 return [...byKey.values()]})();
// a section as flat arrays: segments [x1,z1,x2,z2,...], test points (segment ends and middles) and its bounding box
function section(segs){const a=new Float64Array(segs.flat()),p=new Float64Array(segs.flatMap(g=>[g[0],g[1],(g[0]+g[2])/2,(g[1]+g[3])/2]));
 let x0=Infinity,x1=-Infinity,z0=Infinity,z1=-Infinity;for(let i=0;i<a.length;i+=2){x0=Math.min(x0,a[i]);x1=Math.max(x1,a[i]);z0=Math.min(z0,a[i+1]);z1=Math.max(z1,a[i+1])}
 return {a,p,bb:[x0,x1,z0,z1]}}
// (the ray is cast a hair above z: links lying flat side by side have their section vertices at exactly the same heights, and a
// ray through a vertex that two segments each computed for themselves, one unit in the last place apart, would count it wrongly)
function inside(S,x,z){const b=S.bb;if(x<b[0]||x>b[1]||z<b[2]||z>b[3])return false;const a=S.a;let c=false;z+=1.37e-7;
 for(let i=0;i<a.length;i+=4){const z1=a[i+1],z2=a[i+3];if((z1>z)!==(z2>z)&&x<a[i]+(z-z1)*(a[i+2]-a[i])/(z2-z1))c=!c}return c}
function edgeD(S,x,z){const a=S.a;let d=Infinity;
 for(let i=0;i<a.length;i+=4){const x1=a[i],z1=a[i+1],dx=a[i+2]-x1,dz=a[i+3]-z1,L=dx*dx+dz*dz;let u=L>0?((x-x1)*dx+(z-z1)*dz)/L:0;u=u<0?0:u>1?1:u;
  const ex=x-x1-u*dx,ez=z-z1-u*dz,e=ex*ex+ez*ez;if(e<d)d=e}return Math.sqrt(d)}
const boxD=(b,x,z)=>Math.hypot(Math.max(b[0]-x,0,x-b[1]),Math.max(b[2]-z,0,z-b[3]));   // distance from a point to a bounding box
const overlapsY=(S,y0,y1)=>S.ys.some(([a,b])=>Math.min(b,y1)-Math.max(a,y0)>TOL);
// a Y-aligned cylinder (radius r, Y from y0 to y1, axis at world x,z) against a link [cx,cz,angle]: how deep it is in, mm
function cylDepth(r,y0,y1,x,z,L){const c=Math.cos(L[2]),s=Math.sin(L[2]),dx=x-L[0],dz=z-L[1],lx=dx*c+dz*s,lz=-dx*s+dz*c;let worst=0;
 if(Math.hypot(lx,lz)>r+16)return 0;
 for(const S of SLABS){if(!overlapsY(S,y0,y1)||boxD(S.bb,lx,lz)>=r)continue;const d=edgeD(S,lx,lz),dep=inside(S,lx,lz)?r+d:r-d;if(dep>worst)worst=dep}
 return worst}
// two links (they share the slabs): the deepest point of either one's section inside the other's
function linkDepth(A,B){let worst=0;if(Math.hypot(A[0]-B[0],A[1]-B[1])>40)return 0;
 for(const [P,Q] of [[A,B],[B,A]]){const cp=Math.cos(P[2]),sp=Math.sin(P[2]),cq=Math.cos(Q[2]),sq=Math.sin(Q[2]);
  for(const S of SLABS){const p=S.p,b=S.bb;for(let i=0;i<p.length;i+=2){const dx=P[0]+p[i]*cp-p[i+1]*sp-Q[0],dz=P[1]+p[i]*sp+p[i+1]*cp-Q[1],u=dx*cq+dz*sq,v=-dx*sq+dz*cq;
    if(u<b[0]||u>b[1]||v<b[2]||v>b[3]||!inside(S,u,v))continue;const d=edgeD(S,u,v);if(d>worst)worst=d}}}
 return worst}
// how far two joined links may bend, from the shoe itself: links on one pin, the second turned by b about it (+: shoes outward)
const BENDS=(()=>{const lim=sg=>{let last=0;for(let d=.25;d<=90;d+=.25){const b=sg*d*Math.PI/180,B=[10+10*Math.cos(b),10*Math.sin(b),b];
  if(linkDepth([0,0,0],B)>TOL)return last;last=b}return last};return [lim(-1),lim(1)]})();
// the hardware, from the CAD's merged screw + nut + sleeve mesh. |Y| values: sleeve half-length, the seat (head and nut faces), head
// top, nut's far face, screw tip. Radii: shank, sleeve bore, head, sleeve, nut corners. The head is on the +Y side.
const HWY=[...new Set(J9.link[1].vertices.map(v=>+Math.abs(v[1]).toFixed(3)))].sort((a,b)=>a-b);
const HWR=[...new Set(J9.link[1].vertices.map(v=>+Math.hypot(v[0],v[2]).toFixed(3)))].sort((a,b)=>a-b);
if(HWY.length!==5||HWR.length!==5||Math.max(...J9.link[1].vertices.map(v=>v[1]))!==HWY[2])throw new Error(`joint hardware not as expected: Y ${HWY}, r ${HWR}`);
const HW={bush:{r:HWR[3],half:HWY[0]},screw:{r:HWR[0],seat:HWY[1],head:HWR[2],top:HWY[2],tip:HWY[4]},nut:{r:HWR[4],half:(HWY[3]-HWY[1])/2,y:(HWY[1]+HWY[3])/2}};
const FACES=[...new Set(SV.map(v=>+Math.abs(v[1]).toFixed(3)))].filter(y=>y>6.5);
const EARS=[9.2,13.7],PLATES=[14,21],BOSS=HW.screw.seat;   // the shoe's faces across the track: inner ears, outer plates, seat bosses
for(const y of [...EARS,...PLATES,BOSS])if(!FACES.includes(y))throw new Error(`the shoe has no face at |Y| ${y}: ${FACES.sort((a,b)=>a-b)}`);
async function probeAll(page,k,T){const out=[];for(let i=0;i<T.length;i+=200)out.push(...await page.evaluate(([k,T])=>{kit.go(k);return T.map(x=>kit.probe(x))},[k,T.slice(i,i+200)]));
 return out}
async function chainCheck(page,mode,k,meta){
 // uniform samples plus dense ones where parts move fastest (the first joint, a quick one, the dummy pin, the ends meeting, the join)
 const W=meta.chainWindows||[],T=[...new Set([...Array(1201).keys()].map(i=>i/1200).concat(...W.map(([a,b,n])=>[...Array(n+1).keys()].map(i=>a+(b-a)*i/n))).map(x=>+x.toFixed(6)))].sort((a,b)=>a-b);
 const t0=Date.now(),S=await probeAll(page,k,T),t1=Date.now();
 const tag=`${mode}/chain`,out={samples:T.length,bend_limits_deg:BENDS.map(b=>+(b*180/Math.PI).toFixed(2))},seen=new Set(),once=(key,m)=>{if(!seen.has(key)){seen.add(key);fail(m)}};let rim=0,loop=0;
 const deep={sleeve:0,screw:0,nut:0,dummy:0,link:0},bendSeen=[0,0];
 if(!S[0].mods[0].nuts||!S[0].mods[0].lock)throw new Error('this page predates the screw joint: its probe has no nuts or lock screw');
 // the page's hardware against the CAD's
 {const h=meta.hw,ext=(b,i)=>(b[i+3]-b[i])/2,rad=b=>Math.max(ext(b,0),ext(b,2));
  for(const [n,y0,y1,r] of [['pin',-HW.screw.tip,HW.screw.top,HW.screw.head],['lock',-HW.screw.tip,HW.screw.top,HW.screw.head],
    ['bushing',-HW.bush.half,HW.bush.half,HW.bush.r],['nut',-HW.nut.half,HW.nut.half,HW.nut.r]])
   if(!h[n]||Math.abs(h[n][1]-y0)>1e-3||Math.abs(h[n][4]-y1)>1e-3||Math.abs(rad(h[n])-r)>2e-3)fail(`${tag}: the page's ${n} is not the CAD's (${h[n]})`);
  if(!h.dummy||ext(h.dummy,1)>EARS[1]-.2||ext(h.dummy,1)<EARS[0]+1)fail(`${tag}: the dummy pin (half-length ${h.dummy&&ext(h.dummy,1)}) must reach into both inner ears and stay inside them`);
  if(Math.abs(meta.screw.tip-HW.screw.tip)>1e-6||Math.abs(meta.screw.nutY-HW.nut.y)>1e-6)fail(`${tag}: the page's screw tip and nut place ${JSON.stringify(meta.screw)} are not the CAD's`);
  out.dummy_half_mm=h.dummy?+ext(h.dummy,1).toFixed(3):null}
 const DH=(meta.hw.dummy[4]-meta.hw.dummy[1])/2,LK=meta.lockAt;
 S[0].mods.forEach((_,mi)=>{let flat=-1,open=-1,met=-1,home=-1,bentAt=-1,lockHome=-1,lockOut=-1;const bushSet=new Array(NL).fill(-1),pinIn=new Array(NL).fill(-1),wasDummy=[false,null];
  for(let i=0;i<S.length;i++){const s=S[i],m=s.mods[mi],t=s.t,h=s.lift,sh=m.shoes,at=`${tag}@${t.toFixed(4)}`;
   const ends=sh.map(([,x,z,a])=>[[x-G.pitch/2*Math.cos(a),z-G.pitch/2*Math.sin(a)],[x+G.pitch/2*Math.cos(a),z+G.pitch/2*Math.sin(a)]]);
   const gapAt=n=>{const a=ends[(n+NL-1)%NL][1],b=ends[n][0];return Math.hypot(a[0]-b[0],a[1]-b[1])};
   for(let j=0;j<NL;j++)if(sh[j][0]){const [,,z,a]=sh[j];let lo=Infinity;for(const [lx,lz] of SHOE)lo=Math.min(lo,z+h+lx*Math.sin(a)+lz*Math.cos(a));
    if(lo<-.05)once('bench'+mi,`${at}: link ${j} ${(-lo).toFixed(2)} mm below the bench`)}
   const bent=sh.some(q=>q[0]&&ang(q[3],0)>1e-6);
   if(bent&&bentAt<0){bentAt=i;if(flat<0)once('order'+mi,`${at}: links bent before they lie as one flat strip`);if(Math.abs(h)>1e-9)once('down'+mi,`${at}: wrapping starts with the track lifted ${h} mm`)}
   if(flat<0&&!bent&&sh.every(q=>q[0])&&sh.every(q=>Math.abs(q[2]+h-ZB)<.05)){const gaps=[];for(let n=0;n<NL;n++)if(gapAt(n)>.02)gaps.push(n);
    if(gaps.length===1){flat=i;open=gaps[0];out['flat_strip_t_'+mi]=t;
     if(Math.abs(gapAt(open)-NL*G.pitch)>.1)once('ends'+mi,`${at}: the open joint's ends are ${gapAt(open).toFixed(1)} mm apart, not the strip's two ends`);
     if(m.pins[open][0])once('pin0'+mi,`${at}: the open joint already has its screw`)}}
   // --- solid parts: links against links
   const L=sh.map(q=>q[0]?[q[1],q[2],q[3]]:null);
   for(let j=0;j<NL;j++){const A=L[(j+NL-1)%NL],B=L[j];if(!A||!B)continue;   // links j-1 and j meet at pin j
    if(gapAt(j)<.02){const b=wrap(B[2]-A[2]);bendSeen[0]=Math.min(bendSeen[0],b);bendSeen[1]=Math.max(bendSeen[1],b);
     if(b<BENDS[0]-1e-9||b>BENDS[1]+1e-9)once('bend'+mi+'_'+j,`${at}: joint ${j} bent ${(b*180/Math.PI).toFixed(2)}°, outside the ${BENDS.map(x=>(x*180/Math.PI).toFixed(2))}° its plates and shoes allow`)}
    else{const d=linkDepth(A,B);deep.link=Math.max(deep.link,d);if(d>TOL)once('ll'+mi+'_'+j,`${at}: links ${(j+NL-1)%NL} and ${j} ${d.toFixed(2)} mm into each other`)}}
   for(let a=0;a<NL;a++)for(let b=a+2;b<NL;b++){if(!L[a]||!L[b]||(a===0&&b===NL-1))continue;if(Math.hypot(L[a][0]-L[b][0],L[a][1]-L[b][1])>26)continue;
    const d=linkDepth(L[a],L[b]);deep.link=Math.max(deep.link,d);if(d>TOL)once('ln'+mi+'_'+a+'_'+b,`${at}: links ${a} and ${b} ${d.toFixed(2)} mm into each other`)}
   // --- solid parts: the joint hardware against the links. A part at home on a closed joint is in its CAD place and is skipped.
   const flatL=j=>L[j]&&Math.abs(wrap(L[j][2]))<1e-6;
   for(let j=0;j<NL;j++){const pj=(j+NL-1)%NL,F=L[pj]?ends[pj][1]:null,closed=gapAt(j)<.02;
    const at0=(q,dy)=>F&&Math.hypot(q[1]-F[0],q[3]-F[1])<1e-6&&Math.abs(q[2]-dy)<1e-6;
    // each piece: [name, probe row, radius, Y from, Y to (relative to the row's Y), its Y when at home]
    const parts=[['sleeve',m.bushes[j],HW.bush.r,-HW.bush.half,HW.bush.half,0],['screw',m.pins[j],HW.screw.r,-HW.screw.tip,HW.screw.seat,0],
     ['screw',m.pins[j],HW.screw.head,HW.screw.seat,HW.screw.top,0],['nut',m.nuts[j],HW.nut.r,-HW.nut.half,HW.nut.half,-HW.nut.y]];
    if(j===open&&m.dummy[0])parts.push(['dummy',m.dummy,HW.screw.r,-DH,DH,null]);
    for(const [n,q,r,ya,yb,dy] of parts){if(!q[0])continue;const homeHere=dy!==null&&at0(q,dy);
     for(let l=0;l<NL;l++){if(!L[l])continue;if(homeHere&&(l===pj||(l===j&&closed)))continue;if(n==='dummy'&&l===pj&&F&&Math.hypot(q[1]-F[0],q[3]-F[1])<1e-6&&Math.abs(q[2])<1e-6)continue;
      const d=cylDepth(r,q[2]+ya,q[2]+yb,q[1],q[3],L[l]);if(d>deep[n])deep[n]=d;
      if(d>TOL)once(n+mi+'_'+j+'_'+l,`${at}: ${n} of joint ${j} ${d.toFixed(2)} mm into link ${l}${n==='sleeve'&&Math.abs(q[2])>1e-6?' (moving along the screw, through the Ø'+(2*Math.min(...SLABS.flatMap(S=>[edgeD(S,10,0)]))).toFixed(1)+' holes)':''}`)}}
    // --- order: sleeve before screw, held on the track; the nut after the screw, along it from inboard; the dummy pin
    const bu=m.bushes[j],pn=m.pins[j],nt=m.nuts[j],bHome=bu[0]&&at0(bu,0);
    if(bHome&&bushSet[j]<0)bushSet[j]=i;
    const through=(q,ya,yb)=>q[0]&&F&&Math.hypot(q[1]-F[0],q[3]-F[1])<1e-6&&Math.min(q[2]+yb,HW.bush.half)-Math.max(q[2]+ya,-HW.bush.half)>TOL;
    const pinThrough=through(pn,-HW.screw.tip,HW.screw.seat),dumThrough=j===open&&m.dummy[0]&&through(m.dummy,-DH,DH);
    if((pinThrough||dumThrough)&&!bHome)once('bo'+mi+'_'+j,`${at}: ${pinThrough?'screw':'dummy pin'} of joint ${j} through the sleeve's place before the sleeve is there`);
    if(bu[0]&&!bHome&&(pn[0]||(j===open&&m.dummy[0])))once('bm'+mi+'_'+j,`${at}: sleeve of joint ${j} moves with a screw through its ears`);
    if(bu[0]&&L[pj]&&!flatL(pj)&&!pinThrough&&!dumThrough)once('bh'+mi+'_'+j,`${at}: sleeve of joint ${j} on the track with nothing through it: its ears open downward there`);
    if(pinThrough&&pinIn[j]<0)pinIn[j]=i;
    if(pn[0]&&pn[2]<-1e-9)once('ph'+mi+'_'+j,`${at}: screw of joint ${j} pushed past its seat (Y ${pn[2].toFixed(2)}): its head stops on the boss`);
    if(nt[0]){const home=pn[0]&&Math.abs(pn[2])<1e-6;
     if(!home)once('np'+mi+'_'+j,`${at}: nut of joint ${j} going on before its screw is home`);
     if(!F||Math.hypot(nt[1]-F[0],nt[3]-F[1])>1e-6)once('na'+mi+'_'+j,`${at}: nut of joint ${j} off the screw's axis: it runs on along the screw`);
     if(nt[2]>-HW.nut.y+1e-6)once('ns'+mi+'_'+j,`${at}: nut of joint ${j} past its seat (Y ${nt[2].toFixed(2)}): it stops on the inboard boss`);
     if(j===open&&m.dummy[0])once('nd'+mi,`${at}: last nut going on with the dummy pin still on the screw's path`)}}
   // the dummy pin: on the far end's free ears, inside them while the ends meet, pushed out by the last screw, taken away when clear
   if(m.dummy[0]&&open>=0){const pj=(open+NL-1)%NL,F=ends[pj][1],d=m.dummy,lp=m.pins[open];
    if(Math.hypot(d[1]-F[0],d[3]-F[1])>1e-6)once('da'+mi,`${at}: dummy pin off the end link's ear axis`);
    if(bushSet[open]<0||bushSet[open]>i)once('db'+mi,`${at}: dummy pin before the last sleeve is between the ears`);
    if(gapAt(open)<8&&!lp[0]&&Math.abs(d[2])+DH>EARS[1]+1e-6)once('dp'+mi,`${at}: dummy pin stands out of the inner ears as the ends meet`);
    if(lp[0]&&lp[2]-HW.screw.tip<d[2]+DH-1e-6)once('dl'+mi,`${at}: last screw and dummy pin overlap`);
    wasDummy[1]=d.slice()}
   if(!m.dummy[0]&&wasDummy[1]&&!wasDummy[0]){wasDummy[0]=true;if(wasDummy[1][2]+DH>-BOSS-1e-6)once('dg'+mi,`${at}: dummy pin taken away before it is clear of the seat bosses (Y ${wasDummy[1][2].toFixed(1)})`)}
   // the lock screw: on the axis of the outer wall's hole, never deeper than its place, and only with the idler at its recoil stop
   if(m.lock[0]){const k=m.lock;
    if(Math.hypot(k[1]-LK.x,k[3]-LK.z)>1e-6)once('la'+mi,`${at}: lock screw off the axis of the lock-pin hole`);
    if(k[2]<LK.y-1e-6)once('ld'+mi,`${at}: lock screw deeper than the yoke's hole (Y ${k[2].toFixed(2)})`);
    if(Math.abs(m.slide+G.recoil)>1e-6)once('ls'+mi,`${at}: lock screw in sight with the idler at ${m.slide} mm: the holes only line up at the recoil stop`);
    if(Math.abs(k[2]-LK.y)<1e-6&&lockHome<0)lockHome=i}
   else if(lockHome>=0&&lockOut<0)lockOut=i;
   if(flat<0)continue;
   for(let n=0;n<NL;n++)if(n!==open&&gapAt(n)>.02)once('joint'+mi+'_'+n,`${at}: joint ${n} open by ${gapAt(n).toFixed(3)} mm`);
   if(met<0&&gapAt(open)<.02)met=i;
   if(Math.abs(h)<1e-9){const idl=[G.idler[0]+m.slide,G.idler[1]];
    for(let j=0;j<NL;j++){const p=ends[j][0],ds=Math.hypot(p[0]-G.drive[0],p[1]-G.drive[1]);
     if(ds<G.pitch_r-.05)once('spr'+mi,`${at}: pin ${j} ${(G.pitch_r-ds).toFixed(2)} mm inside the sprocket's pitch circle`);
     for(const [r,c] of Object.entries(G.rollers)){const d=G.roller_r+G.rail_face-Math.hypot(p[0]-c[0],p[1]-c[1]);if(d>.05)once('rol'+mi+r,`${at}: link at pin ${j} ${d.toFixed(2)} mm into roller ${r}`)}
     const di=RIM+BUSH-Math.hypot(p[0]-idl[0],p[1]-idl[1]);rim=Math.max(rim,di);if(di>1)once('idl'+mi,`${at}: sleeve ${j} ${di.toFixed(2)} mm into the idler rim`);
     const dl=loopDist(p);loop=Math.min(loop,dl);if(dl<-.6)once('loop'+mi,`${at}: pin ${j} ${(-dl).toFixed(2)} mm inside the finished loop`)}}
   const q=m.pins[open];
   if(q[0]){if(met<0)once('early'+mi,`${at}: last screw shown before the open ends meet`);
    if(Math.hypot(q[1]-ends[open][0][0],q[3]-ends[open][0][1])>.02)once('axis'+mi,`${at}: last screw off the joint's axis`);
    if(q[2]<-1e-9)once('side'+mi,`${at}: last screw from inboard`);
    if(q[2]>1e-6&&Math.abs(m.slide+G.recoil)>1e-6)once('held'+mi,`${at}: last screw going in with the idler at ${m.slide} mm, not held at its recoil stop`);
    if(q[2]>1e-6&&!(m.lock[0]&&Math.abs(m.lock[2]-LK.y)<1e-6))once('lockin'+mi,`${at}: last screw going in without the lock screw holding the idler`);
    if(q[2]<=1e-6&&home<0)home=i}
   if(m.slide<-G.recoil-1e-6)once('stop'+mi,`${at}: idler ${m.slide} mm, behind its recoil stop`);
   if(met>=0&&i>met&&home<0&&m.slide>-G.recoil+1e-6)once('rel'+mi,`${at}: idler leaves its stop before the last screw is in`)}
  if(flat<0)fail(`${tag}: the links never lie as one flat strip on the bench`);
  if(met<0)fail(`${tag}: the open ends never meet`);if(home<0)fail(`${tag}: the last screw never goes home`);
  if(lockHome<0)fail(`${tag}: the lock screw never holds the idler`);else if(lockOut<0)fail(`${tag}: the lock screw is never taken out`);
  else if(home<0||lockOut<=home)fail(`${tag}: the lock screw comes out before the last screw is home`);
  for(let j=0;j<NL;j++)if(bushSet[j]<0)fail(`${tag}: sleeve of joint ${j} never between its ears`);
  Object.assign(out,{['open_joint_'+mi]:open,['ends_meet_t_'+mi]:met<0?null:T[met],['last_screw_home_t_'+mi]:home<0?null:T[home],
   ['lock_screw_in_out_t_'+mi]:[lockHome<0?null:T[lockHome],lockOut<0?null:T[lockOut]]});
  const e=S[S.length-1],m=e.mods[mi];
  m.shoes.forEach(([v,x,z,a],j)=>{if(!v||Math.hypot(x-G.pitch/2*Math.cos(a)-PIN[j][0],z-G.pitch/2*Math.sin(a)-PIN[j][1])>1e-6||ang(a,TH[j])>1e-9)fail(`${tag}@1: link ${j} not at its CAD pose`)});
  m.pins.forEach(([v,x,y,z],j)=>{if(!v||Math.hypot(x-PIN[j][0],y,z-PIN[j][1])>1e-6)fail(`${tag}@1: screw ${j} not at its CAD pose`)});
  m.bushes.forEach(([v,x,y,z],j)=>{if(!v||Math.hypot(x-PIN[j][0],y,z-PIN[j][1])>1e-6)fail(`${tag}@1: sleeve ${j} not at its CAD pose`)});
  m.nuts.forEach(([v,x,y,z],j)=>{if(!v||Math.hypot(x-PIN[j][0],z-PIN[j][1])>1e-6||Math.abs(y+HW.nut.y)>1e-6)fail(`${tag}@1: nut ${j} not at its CAD pose`)});
  if(m.dummy[0])fail(`${tag}@1: the dummy pin is still in`);if(m.lock[0])fail(`${tag}@1: the lock screw is still in`);
  if(Math.abs(m.slide)>1e-9||Math.abs(e.lift)>1e-9)fail(`${tag}@1: idler ${m.slide} mm, track lifted ${e.lift} mm`)});
 out.max_idler_rim_overlap_mm=+rim.toFixed(3);out.min_distance_to_finished_loop_mm=+loop.toFixed(3);
 out.deepest_overlap_mm=Object.fromEntries(Object.entries(deep).map(([k,v])=>[k,+v.toFixed(3)]));
 out.bends_seen_deg=bendSeen.map(b=>+(b*180/Math.PI).toFixed(2));
 out.seconds={probe:(t1-t0)/1000,checks:(Date.now()-t1)/1000};
 return out}
function labelCheck(tag,st){const shown=st.labels.filter(l=>l.shown);const [w,h]=st.stage;
 for(const l of shown){const [x,y,bw,bh]=l.box;if(x<0||y<0||x+bw>w+.5||y+bh>h+.5)fail(`${tag}: label "${l.text}" outside the view`)}
 for(let i=0;i<shown.length;i++)for(let j=0;j<i;j++){const a=shown[i].box,b=shown[j].box;
  if(a[0]<b[0]+b[2]&&b[0]<a[0]+a[2]&&a[1]<b[1]+b[3]-.5&&b[1]<a[1]+a[3]-.5)fail(`${tag}: labels overlap: ${shown[i].text} / ${shown[j].text}`)}
 return shown}
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader']});
 const result={};
 try{
  const page=await browser.newPage({viewport:{width:1500,height:900},deviceScaleFactor:1});page.setDefaultTimeout(240000);
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
  page.on('request',r=>{if(!r.url().startsWith('file:')&&!r.url().startsWith('data:'))network.push(r.url())});
  const t0=Date.now();await page.goto('file://'+html);await page.waitForFunction(()=>window.kit&&window.kit.state(),null,{timeout:240000});
  result.load_seconds=(Date.now()-t0)/1000;
  const meta=await page.evaluate(()=>kit.meta());
  const sid=Object.fromEntries(meta.steps.map((s,i)=>[s.id,i]));
  const slide=new Set(['J906_idler_wheel','J907_idler_spacer_0','J907_idler_spacer_1','J908_U_yoke','idler_pin_8x55',
   ...['0','1'].flatMap(k=>['inner','outer','shield'].map(r=>`608ZZ_${k}_${r}`))]);
  const names=Object.keys(meta.first),first={};
  for(const n of names){const m=FITTED_IN.filter(([re])=>re.test(n));if(m.length!==1){fail(`${n}: ${m.length} expected steps`);continue}
   first[n]=sid[m[0][1]];if(meta.first[n]!==first[n])fail(`${n}: the page fits it in ${meta.steps[meta.first[n]].id}, the guide in ${m[0][1]}`)}
  const sceneParts=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(__dirname,'j9_scene.json.gz')))).unit.length;
  if(names.length!==sceneParts)fail(`${names.length} module parts in the page (${sceneParts} in the J9 scene)`);
  const cases=[];
  for(const mode of onlyModes){
   const expectSteps=meta.steps.filter(s=>mode==='x1'||!s.x1only).map(s=>s.id);
   await page.evaluate(m=>kit.setMode(m,0),mode);
   const st0=await page.evaluate(()=>kit.state());
   if(JSON.stringify(st0.steps)!==JSON.stringify(expectSteps))fail(`${mode}: step list ${st0.steps}`);
   const nmod=mode==='x1'?2:1;
   for(const id of chainOnly?[]:expectSteps){const k=sid[id],final=id==='overview'||id==='test';
    for(const t of [0,1]){
     const st=await page.evaluate(([k,t])=>{kit.go(k);kit.setT(t);return kit.state()},[k,t]);
     const tag=`${mode}/${id}@${t}`;
     if(st.step!==id)fail(`${tag}: landed on ${st.step}`);
     // visible parts: everything fitted in an earlier step, plus this step's parts once they appear
     const vis=new Set(st.visible),want=names.filter(n=>final||first[n]<k);
     for(const n of want)if(!vis.has(n))fail(`${tag}: ${n} hidden`);
     for(const n of vis)if(!final&&first[n]>k)fail(`${tag}: ${n} shown before its step`);
     if(st.visible.length%nmod)fail(`${tag}: modules differ`);
     if(t===1&&!final){const now=names.filter(n=>first[n]<=k);for(const n of now)if(!vis.has(n))fail(`${tag}: ${n} not shown at the end of its step`)}
     // poses: all parts at their CAD pose except the idler slide, 12 mm forward from the end of the tensioner step to the chain step
     if(t===1||final){const restAhead=!final&&k>=sid.tensioner&&k<sid.chain;
      for(const [n,o] of st.moved){if(restAhead&&slide.has(n)&&near(o[0],meta.yokeRest)&&near(o[1],0)&&near(o[2],0))continue;fail(`${tag}: ${n} off its pose by ${o}`)}
      if(restAhead){const ahead=st.moved.filter(([n])=>slide.has(n)).length;if(ahead!==slide.size*nmod)fail(`${tag}: idler slide not resting ahead (${ahead})`)}}
     // chain
     const links=final||k>sid.chain||(k===sid.chain&&t===1)?meta.links:0;
     if(st.links.some(l=>l!==links)||st.links.length!==nmod)fail(`${tag}: links ${st.links} (want ${links})`);
     // spring length: free until the yoke compresses it, fitted (scale 1) with the chain on
     const sc=st.spring_scale[0];
     if(final&&!near(sc,1,1e-9))fail(`${tag}: spring scale ${sc}`);
     if(id==='tensioner'&&t===1&&!near(sc,(meta.spring.set+meta.yokeRest)/meta.spring.set,1e-9))fail(`${tag}: spring scale ${sc}`);
     if(st.cutaway.some(c=>c!==(id==='tensioner'&&t>=.5)))fail(`${tag}: cut-away ${st.cutaway}`);
     // X101 and the joint hardware
     if(mode==='x1'){const ch=st.chassis;
      if(k<sid.xframe&&!final&&ch.length)fail(`${tag}: chassis shown early`);
      if((k>sid.xframe||final||(k===sid.xframe&&t===1))&&(ch.length!==meta.chassis.length||ch.some(([,o])=>o.some(v=>Math.abs(v)>1e-9))))fail(`${tag}: chassis ${ch.length} not seated`);
      if(k===sid.xframe&&t===0){const x=ch.find(([n])=>n==='X101_X_frame');if(!x||!near(x[1][2],80))fail(`${tag}: X101 not 80 mm above (${x&&x[1]})`)}}
     // labels: inside the 3D view, clear of each other
     const shown=labelCheck(tag,st);
     if(t===1&&meta.steps[k].labels&&!shown.length)fail(`${tag}: no label shown`);
     if(!st.card.includes(meta.steps[k].title))fail(`${tag}: card does not show the step`);
     cases.push({mode,step:id,t,visible:st.visible.length,links:st.links,labels_shown:shown.length,moved:st.moved.length});
    }}
   // the chain step: how the chain goes on, and its labels in the middle of their time windows
   result['chain_'+mode]=await chainCheck(page,mode,sid.chain,meta);
   for(const l of meta.steps[sid.chain].windows){const tm=(l.t0+l.t1)/2,tag=`${mode}/chain@${tm}`;
    const st=await page.evaluate(([k,t])=>{kit.go(k);kit.setT(t);return kit.state()},[sid.chain,tm]);
    const shown=labelCheck(tag,st);if(!shown.some(x=>x.text===l.text))fail(`${tag}: label "${l.text}" not shown in its window`);
    cases.push({mode,step:'chain',t:tm,visible:st.visible.length,links:st.links,labels_shown:shown.length,moved:st.moved.length})}
   console.log('Mode',mode,'checked',expectSteps.length,'steps',JSON.stringify(result['chain_'+mode]));
  }
  result.cases=cases;
  if(write){   // with --no-write only the checks above run; the summary and exit code below still apply
  // the X101-only step is skipped on the bench, and switching mode keeps the place
  let s=await page.evaluate(k=>{kit.setMode('left',0);kit.go(k,1);return kit.state()},sid.xframe);if(s.step!=='sprocket')fail('next over the X101 step lands on '+s.step);
  s=await page.evaluate(k=>{kit.go(k,-1);return kit.state()},sid.xframe);if(s.step!=='housing')fail('prev over the X101 step lands on '+s.step);
  s=await page.evaluate(k=>{kit.setMode('x1',k);kit.setMode('right');return kit.state()},sid.xframe);if(s.step!=='housing'||s.mode!=='right')fail('mode switch from the X101 step: '+s.step);
  s=await page.evaluate(()=>{document.querySelector('#steplist li.skip').click();return kit.state()});if(s.mode!=='x1'||s.step!=='xframe')fail('clicking the X101 step: '+s.mode+' '+s.step);
  result.skip_logic=true;
  // playback advances and auto-advance moves on
  // (from 90 % into the step: a software renderer on a busy machine draws few frames per second, and each frame advances at most 0.1 s)
  await page.evaluate(k=>{kit.setMode('left',k);kit.setT(.9);document.querySelector('#speed').value='2';document.querySelector('#speed').dispatchEvent(new Event('change'));kit.play()},sid.plug);
  await page.waitForFunction(k=>kit.state().index>k,sid.plug,{timeout:240000});
  s=await page.evaluate(()=>{kit.pause();return kit.state()});result.playback={reached:s.step,t:s.t};
  if(s.playing)fail('pause');
  // click to identify
  await page.evaluate(()=>{kit.setMode('left',0);kit.snap()});
  const box=await page.locator('#stage canvas').boundingBox();await page.mouse.click(box.x+box.width*.5,box.y+box.height*.45);
  const ident=await page.locator('#part').innerText();result.click_identify=ident.split('\n')[0];
  if(!/\b(print|buy)\b/.test(ident))fail('click to identify: '+ident);
  // parts list tab
  await page.click('[data-tab="parts"]');
  const tables=await page.evaluate(()=>[...document.querySelectorAll('#tab-parts table')].map(t=>t.rows.length-1));
  result.parts_tab_rows=tables;
  const kitRows=[11,1,8,7,3,3,4,9];if(   // chain: screw, sleeve, nut; tools: 9 rows since the Ø3 x 24 dummy pin for the last chain joint (2026-11-11)
   JSON.stringify(tables)!==JSON.stringify(kitRows))fail('parts tab rows '+tables);
  const body=await page.locator('body').innerText();if(/[㐀-鿿]/.test(body))fail('non-English interface text');
  await page.screenshot({path:path.join(root,'images/kit_parts_tab.png'),timeout:SHOT_MS});
  await page.click('[data-tab="steps"]');
  // screenshots
  const shots=[['kit_overview','left','overview',0],['kit_rollers','left','rollers',.75],['kit_tensioner','left','tensioner',.65],['kit_sprocket','left','sprocket',.55],
   ['kit_chain_joint','left','chain',.14],['kit_chain_nut','left','chain',.17],['kit_chain_strip','left','chain',.3],['kit_chain_dummy','left','chain',.385],
   ['kit_chain_wrap','left','chain',.7],['kit_chain_join','left','chain',.8],['kit_x1_chain','x1','chain',.5],['kit_right_tensioner','right','tensioner',.65],['kit_x1_frame','x1','xframe',.3],['kit_x1_joint','x1','xframe',.95]];
  result.screenshots={};
  for(const [name,mode,id,t] of shots){await page.evaluate(([m,k,t])=>{kit.setMode(m,k);kit.setT(t);kit.snap()},[mode,sid[id],t]);
   const f=path.join(root,'images',name+'.png');await page.screenshot({path:f,timeout:SHOT_MS});result.screenshots[name]={file:'images/'+name+'.png',sha256:sha(f)};console.log('Screenshot',name)}
  }
 }finally{await browser.close()}
 if(errors.length)fail('console errors: '+JSON.stringify(errors));if(network.length)fail('network requests: '+JSON.stringify(network));
 const out={pass:!problems.length,html_sha256:sha(html),checker_sha256:sha(__filename),...result,problems,errors,network};
 if(write)fs.writeFileSync(path.join(root,'track_kit_browser.json'),JSON.stringify(out,null,1)+'\n');
 console.log(out.pass?'Animation checks PASS':'Animation checks FAIL',JSON.stringify({cases:(result.cases||[]).length,playback:result.playback,rows:result.parts_tab_rows,problems:problems.length}));
 if(!out.pass)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});

// Exercise the V6 parts showcase (parts_showcase.html) in Chromium and save a few screenshots.
// The list is checked against the files a builder works from, not against the page's own data:
//   BOM.md: every printed part (file, quantity per actuator, solid mass for V6-U60) and every bought mechanical part (quantity per
//   actuator), the board size for V6-U60, the leadscrew cut length and the number of actuators the arm uses; ASSEMBLY.md "What you
//   need": every tool, the test supply and the screwdriver length for V6-U60; print_plates/V6-U60_x4/plates.json: the plates, their
//   files and what each holds, and that they print four of each part and, once, the fit samples and the test rear cap of ASSEMBLY.md
//   step 1; wire_lengths_U60.csv: the wire cut lengths. Every file the page names exists, with the SHA-256 the page shows (and the
//   one in SHA256SUMS.txt where it is listed), and every STL's size, read from the file, is the size in the page.
// For every item with a model, in its own view: the 3D view is not blank; every "Key" dimension and, for printed parts and plates,
//   the three overall sizes are drawn, inside the 3D view and clear of each other (and so is every dimension in "All"); hovering a
//   dimension highlights it; a section cut (X, Y or Z, through the middle) shows cut faces. Printed parts, on the bed: the model
//   stands on Z = 0, centred, at the STL's size; as fitted: the same size, turned. Plates: the parts stand on Z = 0 where
//   plates.json puts them, their brims inside the bed. In the actuator, whole and cut open: as many pieces highlighted as BOM.md
//   lists per actuator, and no dimensions drawn.
// Also: thumbnails, search and filters, keyboard, address (#id) and click-to-identify, hovering a dimension row, a phone-sized
//   window (no sideways scrolling, labels inside the view), no console errors, no network access and an English-only interface.
// Run: NODE_PATH=<playwright node_modules> node actuator_v6/source/check_parts_showcase.cjs
// Options: [path.html] --no-write (no report, no screenshots) --items=01_body,plate2 (only these items; implies --no-write)
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const root=path.resolve(__dirname,'..'),repo=path.resolve(root,'..'),args=process.argv.slice(2);
const html=path.resolve(args.find(a=>!a.startsWith('--'))||path.join(root,'parts_showcase.html'));
const only=(args.find(a=>a.startsWith('--items='))||'').slice(8).split(',').filter(Boolean),write=!args.includes('--no-write')&&!only.length;
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const errors=[],network=[],problems=[];const fail=m=>{problems.push(m);console.log('FAIL',m)};
const near=(a,b,tol)=>Math.abs(a-b)<=tol;
const SHOT_MS=900000;   // a screenshot under SwiftShader can take minutes when other jobs load the machine
const VARIANT='V6-U60',PLATES='print_plates/V6-U60_x4';
// ------------------------------------------------------------------ the files a builder works from
const read=f=>fs.readFileSync(path.join(root,f),'utf8');
const section=(md,head)=>{const i=md.indexOf(head);if(i<0)throw new Error('no section '+head);const j=md.indexOf('\n## ',i+head.length);return md.slice(i,j<0?undefined:j)};
const tableRows=sec=>sec.split('\n').filter(l=>/^\|/.test(l)).slice(2).map(l=>l.split('|').slice(1,-1).map(c=>c.trim()));
const BOM=read('BOM.md'),ASM=read('ASSEMBLY.md');
const WORDS={one:1,two:2,three:3,four:4,five:5,six:6};
const N=WORDS[(BOM.match(/arm uses (\w+) V6-U60/)||[])[1]];if(!N)fail('BOM.md: how many V6-U60 the arm uses not found');
// printed parts: file, quantity per actuator, solid mass for V6-U60 ("same": as V6-S; "–": a fit sample, one for every length)
const gram=s=>{const m=s.match(/^([\d.]+) g$/);return m?Number(m[1]):null};
const PRINTED=tableRows(section(BOM,'## Printed parts')).map(c=>{const file=c[0].match(/`([^`]+)`/)[1];
 return {id:file.replace(/^fit_samples\//,''),file,per:Number(c[1]),mass:gram(c[3])!=null?gram(c[3]):gram(c[2]),fit:file.startsWith('fit_samples/')}});
// bought mechanical parts, matched to the page by name
const BOUGHT=tableRows(section(BOM,'## Bought mechanical parts')).map(c=>({ref:c[0],part:c[1].replace(/\*\*/g,''),qty:c[2],spec:c[3].replace(/\*\*/g,'')}));
const BOUGHT_ID=[[/^N20 gearmotor/,'motor'],[/^Hex nut M4/,'nut'],[/^Magnet$/,'magnet'],[/^Countersunk screw M1\.6 × 4$/,'M1.6x4'],
 [/^Heat-set insert M1,/,'insert'],[/^Pan-head screw M1 × 8$/,'M1x8'],[/^Pan-head screw M2 × 10$/,'M2x10'],[/^Clevis pins/,'pins'],
 [/^Wire, 28 AWG/,'wires'],[/^Sleeve,/,'sleeve']];
const boardSec=section(BOM,'## End-stop board (PCBA)'),BOARD=(boardSec.match(/([\d.]+) × ([\d.]+) mm for V6-U60/)||[]).slice(1);
const CUT=(BOUGHT.find(b=>/^N20/.test(b.part))||{spec:''}).spec.match(/(\d+) mm for V6-U60/);
if(BOARD.length!==2)fail('BOM.md: board size for V6-U60 not found');if(!CUT)fail('BOM.md: leadscrew cut length for V6-U60 not found');
// tools, the test supply and the leadscrew tools of ASSEMBLY.md "What you need"
const need=ASM.slice(ASM.indexOf('## What you need'),ASM.indexOf('\n## 1.'));
const toolBlock=need.slice(need.indexOf('**Tools:**'),need.indexOf('\n- **',need.indexOf('**Tools:**')));
const TOOL_LINES=toolBlock.split('\n').filter(l=>/^\s+- /.test(l)).map(l=>l.trim().slice(2));
const TOOL_ID=[[/soldering iron/,'iron'],[/PH0 screwdriver/,'PH0'],[/PH000 precision screwdriver/,'PH000'],[/PH1 screwdriver/,'PH1'],[/small pliers/,'pliers']];
const LEAD=(need.match(/\*\*For the leadscrew:\*\* (.*)/)||[])[1]||'',POWER=(need.match(/\*\*Power for testing:\*\* (.*)/)||[])[1]||'';
const BLADE=(toolBlock.match(/(\d+) mm for V6-U60/)||[])[1];if(!BLADE)fail('ASSEMBLY.md: screwdriver length for V6-U60 not found');
const TEST_CAP=/Print one rear cap as well/.test(section(ASM,'## 1. Print and check the fit samples'));
// the plates and the wire lengths
const PJ=JSON.parse(read(PLATES+'/plates.json'));
const EST=fs.existsSync(path.join(root,PLATES,'slicer_estimate.json'))?JSON.parse(read(PLATES+'/slicer_estimate.json')):null;   // slice_plates.py
function csvRows(text){const rows=[];let row=[],f='',q=false;
 for(let i=0;i<text.length;i++){const c=text[i];
  if(q){if(c==='"'){if(text[i+1]==='"'){f+='"';i++}else q=false}else f+=c}
  else if(c==='"')q=true;else if(c===','){row.push(f);f=''}else if(c==='\n'){row.push(f);rows.push(row);row=[];f=''}else if(c!=='\r')f+=c}
 if(f||row.length){row.push(f);rows.push(row)}
 const head=rows.shift();return rows.filter(r=>r.length>1).map(r=>Object.fromEntries(head.map((h,i)=>[h,r[i]])))}
const WIRES=csvRows(read('wire_lengths_U60.csv'));
const SUMS=Object.fromEntries(read('SHA256SUMS.txt').split('\n').filter(Boolean).map(l=>{const m=l.match(/^([0-9a-f]{64}) [ *](.+)$/);return [m[2],m[1]]}));
function stlBox(file){const b=fs.readFileSync(file),n=b.readUInt32LE(80);if(b.length!==84+50*n)throw new Error(file+': not a binary STL');
 const lo=[Infinity,Infinity,Infinity],hi=[-Infinity,-Infinity,-Infinity];
 for(let i=0;i<n;i++){const o=84+50*i+12;for(let v=0;v<3;v++)for(let k=0;k<3;k++){const x=b.readFloatLE(o+12*v+4*k);if(x<lo[k])lo[k]=x;if(x>hi[k])hi[k]=x}}
 return {lo,hi,size:hi.map((v,k)=>v-lo[k]),n}}
// ------------------------------------------------------------------ helpers run in the page
async function stageInfo(page){return page.evaluate(()=>{const s=document.getElementById('stage').getBoundingClientRect(),t=document.getElementById('tools').getBoundingClientRect();
 return {W:s.width,H:s.height,toolsBottom:t.bottom-s.top,toolsShown:getComputedStyle(document.getElementById('tools')).display!=='none'}})}
async function labelsOk(page,tag){const st=await stageInfo(page),L=await page.evaluate(()=>showcase.labels());
 for(const l of L){if(l.x<-.5||l.y<st.toolsBottom-.5||l.x+l.w>st.W+.5||l.y+l.h>st.H+.5)fail(`${tag}: label "${l.text}" outside the 3D view (${l.x.toFixed(0)},${l.y.toFixed(0)} ${l.w.toFixed(0)}x${l.h.toFixed(0)})`)}
 for(let i=0;i<L.length;i++)for(let j=i+1;j<L.length;j++){const a=L[i],b=L[j];
  if(a.x<b.x+b.w-.5&&b.x<a.x+a.w-.5&&a.y<b.y+b.h-.5&&b.y<a.y+a.h-.5)fail(`${tag}: labels overlap: "${a.text}" / "${b.text}"`)}
 return L}
// the page only renders when the check reads its pixels (showcase.hold); labels and boxes do not need a frame
const set=(page,o)=>page.evaluate(o=>{showcase.set(o)},o);
const sel=(page,id,o)=>page.evaluate(([id,o])=>{showcase.select(id,o||{});return showcase.state()},[id,o]);
const box=page=>page.evaluate(()=>showcase.partBox());
const legendCount=s=>{const m=(s.legend||'').match(/^(\d+) × /);return m?Number(m[1]):null};
// ------------------------------------------------------------------ run
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader']});
 const result={items:{}};
 try{
  const page=await browser.newPage({viewport:{width:1500,height:900},deviceScaleFactor:1});page.setDefaultTimeout(240000);
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
  page.on('request',r=>{if(!r.url().startsWith('file:')&&!r.url().startsWith('data:'))network.push(r.url())});
  const t0=Date.now();await page.goto('file://'+html);await page.waitForFunction(()=>window.showcase&&window.showcase.ready,null,{timeout:240000});
  result.load_seconds=(Date.now()-t0)/1000;console.log('Loaded in',result.load_seconds,'s');await page.evaluate(()=>showcase.hold(true));
  const meta=await page.evaluate(()=>({variant:showcase.data.variant,totals:showcase.data.totals,bed:showcase.data.plates.bed}));
  const items=await page.evaluate(()=>showcase.data.items.map(i=>({id:i.id,type:i.type,name:i.name,qty:i.qty,per:i.per,size:i.size,files:i.files||[],
   mass:i.mass||null,plates:i.plates||null,objects:i.objects||null,slicer:i.slicer||null,text:[i.spec,i.note].filter(Boolean).join(' '),model:!!i.model,bed:!!(i.model&&i.model.bed),
   context:!!i.context,dims:i.dims.map(d=>({n:d.n,k:d.k,key:!!d.key,label:d.label,text:d.text}))})));
  const BY=Object.fromEntries(items.map(i=>[i.id,i])),seen=new Set(),WANT={};   // WANT: pieces per actuator, from BOM.md
  if(meta.variant!==VARIANT||PJ.variant!==VARIANT)fail(`variant: page ${meta.variant}, plates.json ${PJ.variant}`);
  if(meta.totals.actuators!==N||PJ.actuators!==N)fail(`actuators: page ${meta.totals.actuators}, plates.json ${PJ.actuators}, BOM.md ${N}`);
  if(PJ.pass!==true)fail('plates.json: its own checks did not pass');
  // ---- printed parts against BOM.md and plates.json
  const copies=(name,once)=>PJ.plates.filter(p=>!!p.once===once).reduce((s,p)=>s+p.objects.filter(o=>o.name===name).reduce((a,o)=>a+o.copies,0),0);
  for(const r of PRINTED){const it=BY[r.id];if(!it){fail(`BOM.md printed part ${r.file} is not in the page`);continue}seen.add(it.id);
   if(it.type!==(r.fit?'fit':'print'))fail(`${it.id}: type ${it.type}`);
   const total=r.fit?1:r.per*N;if(it.qty.total!==total)fail(`${it.id}: ${it.qty.total} in the page, BOM.md ${r.per} per actuator`);
   if(!r.fit){if(it.per!==r.per)fail(`${it.id}: ${it.per} per actuator, BOM.md ${r.per}`);WANT[it.id]=r.per}
   if(!it.mass||!near(it.mass.solid_g,r.mass,.051))fail(`${it.id}: ${it.mass&&it.mass.solid_g} g solid, BOM.md ${r.mass} g`);
   const stl=it.files.find(f=>f.path.endsWith('.stl'));if(!stl||stl.path!==`actuator_v6/stl/${r.fit?'':VARIANT+'/'}${r.file}.stl`)fail(`${it.id}: STL ${stl&&stl.path}`);
   // printed on the plates: four of each part on the plates for the arm; once, on the fit-test plate, the fit samples and the test rear cap
   const onPlates=copies(r.id,false),onTest=copies(r.id,true),testWant=r.fit?1:(TEST_CAP&&r.id==='03_rear_cap'?1:0);
   if(onPlates!==(r.fit?0:total)||onTest!==testWant)fail(`${it.id}: ${onPlates} on the plates and ${onTest} on the fit-test plate`);
   const pl=PJ.plates.map(p=>({n:p.n,copies:p.objects.filter(o=>o.name===r.id).reduce((a,o)=>a+o.copies,0)})).filter(p=>p.copies);
   if(JSON.stringify((it.plates||[]).map(p=>({n:p.n,copies:p.copies})))!==JSON.stringify(pl))fail(`${it.id}: plates ${JSON.stringify(it.plates)} / plates.json ${JSON.stringify(pl)}`)}
  // ---- bought parts and the bench items against BOM.md
  for(const b of BOUGHT){const m=BOUGHT_ID.filter(([re])=>re.test(b.part));if(m.length!==1){fail(`BOM.md part "${b.part}": ${m.length} page items match`);continue}
   const it=BY[m[0][1]];if(!it){fail(`BOM.md part "${b.part}" is not in the page`);continue}seen.add(it.id);
   if(it.id==='pins'){if(it.type!=='bench'||!/arm uses its own/.test(b.spec))fail(`pins: ${it.type}; BOM.md "${b.spec}"`);continue}
   if(it.type!=='buy')fail(`${it.id}: type ${it.type}`);
   const q=/^\d+$/.test(b.qty)?Number(b.qty):(it.id==='sleeve'&&/lead length/.test(b.qty)?1:null);if(q==null){fail(`${it.id}: BOM.md quantity "${b.qty}"`);continue}
   if(it.per!==q||it.qty.total!==q*N)fail(`${it.id}: ${it.per} per actuator, ${it.qty.total} in all; BOM.md ${b.qty}`);WANT[it.id]=q}
  {const it=BY.pcba;if(!it)fail('the board is not in the page');else{seen.add('pcba');WANT.pcba=1;
   if(it.per!==1||it.qty.total!==N||!/spare/.test(it.qty.text)||!/spare board/.test(BOM))fail(`pcba: ${JSON.stringify(it.qty)}`);
   for(const v of BOARD)if(!it.dims.some(d=>d.key&&d.k==='len'&&d.text===v))fail(`pcba: board size ${v} (BOM.md) not a key dimension`)}}
  {const it=BY.motor;if(it&&CUT){if(!it.dims.some(d=>d.key&&d.k==='len'&&d.text===CUT[1]&&/cut length/.test(d.label))||!it.text.includes(`cut it to ${CUT[1]} mm`))fail(`motor: leadscrew cut length ${CUT[1]} (BOM.md) not shown`);
   if(!BY.saw||!BY.saw.text.includes(`to ${CUT[1]} mm`))fail('saw: not the cut length of BOM.md')}}
  {const it=BY.wires;if(it){if(it.per!==WIRES.length)fail(`wires: ${it.per} per actuator, ${WIRES.length} in wire_lengths_U60.csv`);
   for(const w of WIRES){const d=it.dims.find(d=>d.label.startsWith(`${w.wire_id} ${w.colour} `)),len=w.cut_length_mm.match(/^[\d.]+/)[0];
    if(!d||!d.text.startsWith(len))fail(`wires: ${w.wire_id} ${w.colour} ${w.cut_length_mm} (CSV) / ${d&&d.text}`)}}}
  // ---- tools and the test supply against ASSEMBLY.md
  for(const l of TOOL_LINES){const m=TOOL_ID.filter(([re])=>re.test(l));if(m.length!==1){fail(`ASSEMBLY.md tool "${l}": ${m.length} page items match`);continue}
   const it=BY[m[0][1]];if(!it||it.type!=='tool')fail(`tool "${l}" is not in the page`);else seen.add(it.id)}
  for(const [re,id] of [[/hacksaw/,'saw'],[/small file/,'file']]){if(!re.test(LEAD))fail(`ASSEMBLY.md leadscrew tools: no ${re}`);else if(!BY[id]||BY[id].type!=='tool')fail(`tool ${id} not in the page`);else seen.add(id)}
  if(!/12 V supply/.test(POWER)||!BY.supply||BY.supply.type!=='bench')fail('the 12 V test supply (ASSEMBLY.md) is not in the page');else seen.add('supply');
  if(BY.PH0&&!BY.PH0.text.includes(`at least ${BLADE} mm`))fail(`PH0: blade length ${BLADE} mm (ASSEMBLY.md) not in the page`);
  // ---- plates against plates.json
  for(const p of PJ.plates){const it=BY['plate'+p.n];if(!it||it.type!=='plate'){fail(`plate ${p.n} is not in the page`);continue}seen.add(it.id);
   const fp=it.files.map(f=>f.path),want=['3mf','stl'].map(k=>'actuator_v6/'+p.files[k]);if(JSON.stringify(fp)!==JSON.stringify(want))fail(`${it.id}: files ${fp}`);
   for(const f of it.files){const k=f.path.endsWith('.3mf')?'3mf':'stl';if(f.sha256!==p.sha256[k])fail(`${it.id}: ${f.path} SHA-256 is not the one in plates.json`)}
   const ob=JSON.stringify((it.objects||[]).map(o=>[o.name,o.copies])),pb=JSON.stringify(p.objects.map(o=>[o.name,o.copies]));if(ob!==pb)fail(`${it.id}: objects ${ob} / plates.json ${pb}`);
   // the slicer's figures, only for the 3MF it sliced. The page shows them to 0.1 g: read the value shown and compare, since
   // a tie such as 61.25 rounds to even in Python (61.2) but up in toFixed (61.3).
   const e=EST&&EST.plates.find(x=>x.n===p.n&&x.sha256_3mf===p.sha256['3mf']);
   const shownG=it.slicer?+((it.slicer.text.match(/(\d+(?:\.\d+)?) g of PETG/)||[])[1]):NaN;
   if(e&&!(Math.abs(shownG-e.filament_g)<=.05+1e-9))fail(`${it.id}: slicer estimate ${e.filament_g} g not shown (the page shows ${shownG} g)`);
   if(!e&&it.slicer)fail(`${it.id}: a slicer estimate for a file that was not sliced`)}
  for(const it of items)if(!seen.has(it.id))fail(`${it.id} is in the page but not in BOM.md, ASSEMBLY.md or plates.json`);
  // ---- the files themselves
  let nfiles=0;
  for(const it of items)for(const f of it.files){const p=path.join(repo,f.path);nfiles++;
   if(!fs.existsSync(p)){fail(`${it.id}: ${f.path} does not exist`);continue}
   const h=sha(p),rel=path.relative(root,p);if(h!==f.sha256)fail(`${it.id}: ${f.path} SHA-256 is not the page's`);if(SUMS[rel]&&SUMS[rel]!==h)fail(`${it.id}: ${rel} is not the file SHA256SUMS.txt lists`);
   if(p.endsWith('.stl')){const b=stlBox(p);if(!it.size||b.size.some((v,k)=>!near(v,it.size[k],.051)))fail(`${it.id}: ${f.path} is ${b.size.map(v=>v.toFixed(2))}, the page says ${it.size}`)}}
  result.sources={bom_printed:PRINTED.length,bom_bought:BOUGHT.length,tools:TOOL_LINES.length+2,plates:PJ.plates.length,wires:WIRES.length,files:nfiles,page_items:items.length};
  console.log('Sources',JSON.stringify({...result.sources,actuators:N,board:BOARD,leadscrew_cut:CUT&&CUT[1],blade:BLADE,test_rear_cap:TEST_CAP,want:WANT}));
  // ---- every item
  for(const it of items){if(only.length&&!only.includes(it.id))continue;const r={};result.items[it.id]=r;const tag=it.id;
   let s=await sel(page,it.id);if(s.sel!==it.id){fail(`${tag}: select landed on ${s.sel}`);continue}
   const st=await stageInfo(page);
   if(!it.model&&!it.context){if(st.toolsShown)fail(`${tag}: tools shown for an item without a model`);
    const msg=await page.evaluate(()=>document.getElementById('msg').textContent);if(!/no 3D model/.test(msg))fail(`${tag}: no "no model" message`);r.model=false;continue}
   const printed=['print','fit','plate'].includes(it.type),px=await page.evaluate(()=>showcase.pixels());r.coverage=+px.model.toFixed(4);
   if(px.model<.004)fail(`${tag}: 3D view blank (${px.model})`);
   const dims=it.dims.filter(d=>d.k!=='spec');
   // dimensions: Key, then All
   if(dims.length||printed){
    let L=await labelsOk(page,tag+'/key');const ns=new Set(L.map(l=>String(l.n)));
    for(const d of dims)if(d.key&&!ns.has(String(d.n)))fail(`${tag}: key dimension ${d.n} (${d.text}) not drawn`);
    const ov=L.filter(l=>l.k==='ov').length;if(printed&&ov!==3)fail(`${tag}: ${ov} overall sizes drawn`);
    r.labels_key=L.length;
    await set(page,{dims:'all',reframe:false});L=await labelsOk(page,tag+'/all');const na=new Set(L.map(l=>String(l.n)));
    const missing=dims.filter(d=>!na.has(String(d.n))).map(d=>d.n);r.labels_all=L.length;if(missing.length)r.all_not_in_view=missing;
    if(missing.filter(n=>dims.find(d=>d.n===n).key).length)fail(`${tag}: key dimensions ${missing} missing in "All"`);
    // hovering a dimension shows it in the table colour and on the model
    const d0=dims.find(d=>d.key)||dims[0];
    if(d0){await set(page,{dims:'key',hover:d0.n,reframe:false});L=await page.evaluate(()=>showcase.labels());const h=L.find(l=>String(l.n)===String(d0.n));
     if(!h||!/\bhot\b/.test(h.cls))fail(`${tag}: hovered dimension ${d0.n} not highlighted`)}
    await set(page,{dims:'key',hover:0,reframe:false})}
   // section cuts through the middle, along X, Y and Z: cut faces appear in at least one (a middle plane can pass between the
   // parts of a plate, or only graze a thin leadscrew seen edge-on)
   const pOff=await page.evaluate(()=>showcase.pixels());r.cut_face_px=[];
   for(const k of [0,1,2]){await set(page,{cut:k,cutT:0,reframe:false});const pOn=await page.evaluate(()=>showcase.pixels());r.cut_face_px.push(Math.round((pOn.cap-pOff.cap)*pOn.w*pOn.h))}
   if(Math.max(...r.cut_face_px)<30)fail(`${tag}: no cut faces in the X, Y or Z section (${r.cut_face_px} px)`);
   await set(page,{cut:-1,reframe:false});
   // a printed part on the bed and as fitted
   if(it.type==='print'||it.type==='fit'){const sz=it.size;
    await set(page,{pose:'bed'});let b=await box(page);
    const ext=b.max.map((v,k)=>v-b.min[k]),c=b.max.map((v,k)=>(v+b.min[k])/2);r.bed={size:ext.map(v=>+v.toFixed(3)),min_z:+b.min[2].toFixed(4)};
    if(!near(b.min[2],0,.005))fail(`${tag}: on the bed, lowest point at Z ${b.min[2]}`);
    if(!near(c[0],0,.05)||!near(c[1],0,.05))fail(`${tag}: not centred on the bed (${c})`);
    if(ext.some((v,k)=>!near(v,sz[k],.051)))fail(`${tag}: bed size ${ext} / ${sz}`);
    await set(page,{pose:'fit'});b=await box(page);const fe=b.max.map((v,k)=>v-b.min[k]).sort((a,b)=>a-b),se=[...sz].sort((a,b)=>a-b);
    if(fe.some((v,k)=>!near(v,se[k],.06)))fail(`${tag}: as fitted ${fe} / ${se}`);
    await set(page,{pose:'bed'})}
   // a plate: the parts where plates.json puts them (the outlines of the parts; the footprints add the brims), on Z = 0, and the
   // footprints inside the bed
   if(it.type==='plate'){const p=PJ.plates.find(q=>'plate'+q.n===it.id),I=p.instances;await set(page,{pose:'bed'});const b=await box(page);
    const ol=[Math.min(...I.map(i=>i.outline_mm[0])),Math.min(...I.map(i=>i.outline_mm[1])),Math.max(...I.map(i=>i.outline_mm[2])),Math.max(...I.map(i=>i.outline_mm[3]))];
    r.bed={min:b.min.map(v=>+v.toFixed(3)),max:b.max.map(v=>+v.toFixed(3))};
    if(!near(b.min[2],0,.005)||!near(b.max[2],p.height_mm,.01))fail(`${tag}: Z ${b.min[2]} to ${b.max[2]}, plates.json height ${p.height_mm}`);
    if([b.min[0],b.min[1],b.max[0],b.max[1]].some((v,k)=>!near(v,ol[k],.01)))fail(`${tag}: on the bed ${r.bed.min} to ${r.bed.max}, plates.json outlines ${ol}`);
    if(I.some(i=>i.footprint_mm[0]<0||i.footprint_mm[1]<0||i.footprint_mm[2]>meta.bed[0]||i.footprint_mm[3]>meta.bed[1]))fail(`${tag}: a footprint off the ${meta.bed} bed`)}
   // in the actuator, whole and cut open: as many pieces highlighted as BOM.md lists per actuator
   if(it.context){const want=WANT[it.id];r.actuator={};if(want==null)fail(`${tag}: no BOM.md quantity to compare`);
    for(const v of ['whole','cut']){await set(page,{view:v});s=await page.evaluate(()=>showcase.state());const n=legendCount(s);r.actuator[v]=n;
     const pp=await page.evaluate(()=>showcase.pixels());if(pp.model<.01)fail(`${tag}: ${v} actuator view blank`);
     if(n!==want)fail(`${tag}/${v}: ${n} highlighted in the actuator, BOM.md ${want}`);
     if(!/: in one actuator(, cut open on the pin plane)?$/.test(s.legend)||(v==='cut')!==/cut open/.test(s.legend))fail(`${tag}: legend "${s.legend}"`);
     const L=await page.evaluate(()=>showcase.labels());if(L.length)fail(`${tag}: dimension labels in the ${v} actuator view`)}
    await set(page,{view:it.model?'part':'whole'})}
   console.log('Checked',it.id,JSON.stringify(r))}
  // ---- the overview, click to identify, keyboard and address
  await page.evaluate(()=>showcase.hold(false));
  if(!only.length){
   let s=await sel(page,'overview');const pv=await page.evaluate(()=>showcase.pixels());result.overview_coverage=+pv.model.toFixed(4);if(pv.model<.03)fail('overview blank');
   if(s.view!=='whole')fail(`overview in the ${s.view} view`);
   // click to identify: in the actuator views the clicked part is shown highlighted, with its count
   const cb=await page.locator('#stage canvas').boundingBox();
   const clickAround=async from=>{for(const [fx,fy] of [[.5,.5],[.45,.52],[.55,.48],[.4,.5],[.6,.5],[.3,.5],[.7,.5]]){await page.mouse.click(cb.x+cb.width*fx,cb.y+cb.height*fy);
    const st=await page.evaluate(()=>showcase.state());if(st.sel!==from)return st}return null};
   const clicked=(st,view,tag)=>{if(!st){fail(`clicking in the ${tag} identifies nothing`);return}
    if(st.view!==view||legendCount(st)!==WANT[st.sel])fail(`clicking ${st.sel} in the ${tag}: ${st.view} "${st.legend}" (BOM.md ${WANT[st.sel]})`)};
   let st=await clickAround('overview');result.click_identify={overview:st&&st.sel};clicked(st,'whole','overview');
   await sel(page,'04_rod');await set(page,{view:'cut'});st=await clickAround('04_rod');result.click_identify.cut_view=st&&st.sel;clicked(st,'cut','04_rod cut view');
   await sel(page,'01_body');await page.keyboard.press('ArrowDown');s=await page.evaluate(()=>showcase.state());if(s.sel!=='02_front_cap')fail('ArrowDown from 01_body lands on '+s.sel);
   await page.keyboard.press('Escape');s=await page.evaluate(()=>showcase.state());if(s.sel!=='overview')fail('Escape lands on '+s.sel);
   await page.evaluate(()=>{location.hash='05_rod_eye'});await page.waitForFunction(()=>showcase.state().sel==='05_rod_eye',null,{timeout:20000}).catch(()=>fail('#05_rod_eye does not open 05_rod_eye'));
   // hovering a row of the dimensions table
   await sel(page,'01_body');await page.hover('#info tr[data-n="1"]');const hov=await page.evaluate(()=>({row:document.querySelector('#info tr[data-n="1"]').classList.contains('hot'),lab:showcase.labels().filter(l=>/\bhot\b/.test(l.cls)).map(l=>l.n)}));
   if(!hov.row||JSON.stringify(hov.lab)!=='[1]')fail('hovering row 1 of 01_body: '+JSON.stringify(hov));await page.mouse.move(5,5);
   // search and filters
   const cards=()=>page.evaluate(()=>[...document.querySelectorAll('#list .card')].map(c=>c.dataset.id));
   const filt=async f=>{await page.click(`#filters button[data-f="${f}"]`);return cards()};
   result.filters={};
   for(const [f,ok] of [['print',i=>['print','fit'].includes(i.type)],['buy',i=>i.type==='buy'],['plate',i=>i.type==='plate'],['tool',i=>['tool','bench'].includes(i.type)]]){
    const c=await filt(f),want=items.filter(ok).map(i=>i.id);result.filters[f]=c.length;if(JSON.stringify(c)!==JSON.stringify(want))fail(`filter ${f}: ${c}`)}
   await filt('all');if((await cards()).length!==items.length+1)fail('filter all: not every item listed');
   await page.fill('#q','countersunk');let c=await cards();result.search_countersunk=c;if(!c.includes('M1.6x4')||['M1x8','M2x10','insert'].some(k=>c.includes(k)))fail('search countersunk: '+c);
   await page.fill('#q','m1 × 8');c=await cards();result.search_m1x8=c;if(!c.includes('M1x8')||['M2x10','M1.6x4'].some(k=>c.includes(k)))fail('search "m1 × 8": '+c);
   await page.fill('#q','');
   await page.click('#list .card[data-id="06_cable_clamp"]');s=await page.evaluate(()=>showcase.state());if(s.sel!=='06_cable_clamp')fail('clicking the 06_cable_clamp card opens '+s.sel);
   const body=await page.locator('body').innerText();if(/[㐀-鿿]/.test(body))fail('non-English interface text');
   // thumbnails: one per model and the overview, on their cards
   await sel(page,'overview');await page.waitForFunction(()=>showcase.pendingThumbs()===0,null,{timeout:600000}).catch(()=>fail('thumbnails not finished'));
   const th=await page.evaluate(()=>({n:showcase.thumbs(),cards:[...document.querySelectorAll('#list .card .th')].filter(e=>/url\(/.test(e.style.backgroundImage)).length}));
   const nm=items.filter(i=>i.model).length+1;result.thumbnails=th;if(th.n!==nm||th.cards!==nm)fail(`thumbnails ${JSON.stringify(th)}, want ${nm}`);
   // screenshots
   if(write){result.screenshots={};
    const shots=[['showcase_overview','overview',{}],['showcase_01_body','01_body',{}],['showcase_04_rod_all','04_rod',{dims:'all',reframe:false}],
     ['showcase_01_body_cut','01_body',{cut:0,cutT:0,reframe:false}],['showcase_02_front_cap_fitted','02_front_cap',{pose:'fit'}],
     ['showcase_insert_cut','insert',{view:'cut'}],['showcase_motor','motor',{}],['showcase_plate1','plate1',{}],['showcase_plate3','plate3',{}]];
    // each from the same start (on the bed, key dimensions, no cut), then its own options
    for(const [name,id,o] of shots){await sel(page,id);await set(page,{pose:'bed',dims:'key',cut:-1});if(Object.keys(o).length)await set(page,o);await page.waitForTimeout(400);await page.evaluate(()=>showcase.render());
     const f=path.join(root,'images',name+'.png');await page.screenshot({path:f,timeout:SHOT_MS});result.screenshots[name]={file:'images/'+name+'.png',sha256:sha(f)};console.log('Screenshot',name)}}
   // a phone-sized window
   await page.setViewportSize({width:390,height:844});await sel(page,'01_body');await set(page,{pose:'bed',dims:'key',cut:-1});await page.waitForTimeout(500);await page.evaluate(()=>showcase.render());
   const m=await page.evaluate(()=>({sw:document.documentElement.scrollWidth,iw:innerWidth,list:getComputedStyle(document.getElementById('list')).display}));
   result.phone={...m};if(m.sw>m.iw)fail(`phone: page ${m.sw} px wide in a ${m.iw} px window`);
   const L=await labelsOk(page,'phone/01_body');result.phone.labels=L.length;const ns=new Set(L.map(l=>String(l.n)));
   for(const d of BY['01_body'].dims)if(d.key&&d.k!=='spec'&&!ns.has(String(d.n)))fail(`phone: key dimension ${d.n} not drawn`);
   if(write){const f=path.join(root,'images','showcase_phone.png');await page.screenshot({path:f,timeout:SHOT_MS});result.screenshots.showcase_phone={file:'images/showcase_phone.png',sha256:sha(f)};console.log('Screenshot showcase_phone')}
  }
 }finally{await browser.close()}
 if(errors.length)fail('console errors: '+JSON.stringify(errors));if(network.length)fail('network requests: '+JSON.stringify(network));
 const out={pass:!problems.length,html_sha256:sha(html),checker_sha256:sha(__filename),...result,problems,errors,network};
 if(write)fs.writeFileSync(path.join(root,'parts_showcase_browser.json'),JSON.stringify(out,null,1)+'\n');
 console.log(out.pass?'Showcase checks PASS':'Showcase checks FAIL',JSON.stringify({items:Object.keys(result.items).length,load:result.load_seconds,problems:problems.length}));
 if(!out.pass)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});

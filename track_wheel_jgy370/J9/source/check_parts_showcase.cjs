// Exercise the offline parts showcase (parts_showcase.html) in Chromium and save a few screenshots.
// The list is checked against the kit files written by build_track_kit.py, not against the page's own data: every row of
//   track_kit.csv (the left and right prints of J901 and J909 are one entry) and every tool of TRACK_KIT.md 3 is in the page, with the
//   same quantity, the same STL file and the same printed size.
// For every part with a model, in its own view: the 3D view is not blank; every "Key" dimension and the three overall sizes are drawn,
//   inside the 3D view and clear of each other (and so is every dimension in "All"); a section cut shows the cut faces. Printed parts,
//   on the bed: the model stands on Z = 0, centred, at the size in track_kit.csv (left and right files); as fitted: the same size,
//   turned. In the track: the number of pieces highlighted is the per-track quantity of track_kit.csv (X101 joints: per machine),
//   for the left and the mirrored right track. The spring is 38.1 long free and 25.8 fitted (track_kit.csv), Ø15.24.
// Also: thumbnails, search and filters, keyboard, address (#id) and click-to-identify, hovering a dimension row, a phone-sized
//   window (no sideways scrolling, labels inside the view), no console errors, no network access and an English-only interface.
// Run: NODE_PATH=<playwright node_modules> node track_wheel_jgy370/J9/source/check_parts_showcase.cjs
// Options: [path.html] --no-write (no report, no screenshots) --items=J901,J904 (only these parts; implies --no-write)
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const root=path.resolve(__dirname,'..'),args=process.argv.slice(2);
const html=path.resolve(args.find(a=>!a.startsWith('--'))||path.join(root,'parts_showcase.html'));
const only=(args.find(a=>a.startsWith('--items='))||'').slice(8).split(',').filter(Boolean),write=!args.includes('--no-write')&&!only.length;
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const errors=[],network=[],problems=[];const fail=m=>{problems.push(m);console.log('FAIL',m)};
const near=(a,b,tol)=>Math.abs(a-b)<=tol;
const SHOT_MS=900000;   // a screenshot under SwiftShader can take minutes when other jobs load the machine
// ------------------------------------------------------------------ the kit files
function csvRows(text){const rows=[];let row=[],f='',q=false;
 for(let i=0;i<text.length;i++){const c=text[i];
  if(q){if(c==='"'){if(text[i+1]==='"'){f+='"';i++}else q=false}else f+=c}
  else if(c==='"')q=true;else if(c===','){row.push(f);f=''}else if(c==='\n'){row.push(f);rows.push(row);row=[];f=''}else if(c!=='\r')f+=c}
 if(f||row.length){row.push(f);rows.push(row)}
 const head=rows.shift();return rows.filter(r=>r.length>1).map(r=>Object.fromEntries(head.map((h,i)=>[h,r[i]])))}
const CSV=csvRows(fs.readFileSync(path.join(root,'track_kit.csv'),'utf8'));
const md=fs.readFileSync(path.join(root,'TRACK_KIT.md'),'utf8'),toolSec=md.slice(md.indexOf('## 3. Tools'),md.indexOf('## 4.'));
const TOOLS=toolSec.split('\n').filter(l=>/^\| /.test(l)&&!/^\| Tool \|/.test(l)).map(l=>l.split('|')[1].trim());
// one entry per part: the left and right print files of a mirrored part are added up
const KIT=new Map();
for(const r of CSV){const name=r.part.replace(/ \((left|right)\)$/,''),side=(r.part.match(/ \((left|right)\)$/)||[])[1];
 const e=KIT.get(name)||{name,type:r.type,rows:0,total:0,per_track:null,files:[],size:r.size_mm,qty_text:r.qty_two_tracks,spec:r.settings_or_spec};
 e.rows++;const n=Number(r.qty_two_tracks);if(Number.isFinite(n)&&r.type!=='bench test')e.total+=n;else e.total=null;   // bench quantities are text
 if(r.per_track)e.per_track=Number(r.per_track);if(r.file)e.files.push({file:r.file,side:side||''});if(e.size!==r.size_mm)fail(`${name}: two sizes in the CSV`);
 KIT.set(name,e)}
// the spring as the kit lists it
const springRow=[...KIT.values()].find(e=>/Compression spring/.test(e.name));
const num=(re,s)=>{const m=s.match(re);return m?Number(m[1]):NaN};
const SPRING={od:num(/OD ([\d.]+)/,springRow.spec),free:num(/free length ([\d.]+)/,springRow.spec),fitted:num(/at the ([\d.]+) mm fitted length/,springRow.spec),solid:num(/solid ([\d.]+) mm/,springRow.spec)};
if(Object.values(SPRING).some(v=>!Number.isFinite(v)))fail('spring values not found in track_kit.csv: '+JSON.stringify(SPRING));
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
  const items=await page.evaluate(()=>showcase.data.items.map(i=>({id:i.id,type:i.type,name:i.name,qty:i.qty,size:i.size,files:i.files,model:!!i.model,
   bed:!!(i.model&&i.model.bed),mirror:!!i.mirror,context:i.context||null,dims:i.dims.filter(d=>d.k!=='spec').map(d=>({n:d.n,k:d.k,key:!!d.key,text:d.text}))})));
  // ---- the list against the kit files
  const byName=new Map(items.map(i=>[i.name,i])),seen=new Set();
  for(const e of KIT.values()){const it=byName.get(e.name);if(!it){fail(`kit row "${e.name}" is not in the page`);continue}seen.add(it.id);
   const total=it.qty.total==null?null:it.qty.total;
   if(e.total!=null&&total!==e.total)fail(`${it.id}: ${total} in the page, ${e.total} in the kit`);
   if(e.total==null&&!it.qty.text.startsWith(e.qty_text))fail(`${it.id}: quantity "${it.qty.text}", kit "${e.qty_text}"`);
   if(e.files.length){const pf=(it.files||[]).map(f=>f.stl).sort(),kf=e.files.map(f=>f.file).sort();if(JSON.stringify(pf)!==JSON.stringify(kf))fail(`${it.id}: files ${pf} / kit ${kf}`)}
   if(e.size){const ks=e.size.split(' x ').map(Number);if(!it.size||it.size.some((v,k)=>!near(v,ks[k],.051)))fail(`${it.id}: size ${it.size} / kit ${e.size}`)}
   e.id=it.id}
  for(const t of TOOLS){const it=byName.get(t);if(!it||it.type!=='tool')fail(`tool "${t}" is not in the page`);else seen.add(it.id)}
  for(const it of items)if(!seen.has(it.id))fail(`${it.id} is in the page but not in the kit files`);
  result.kit={csv_rows:CSV.length,kit_entries:KIT.size,tools:TOOLS.length,page_items:items.length};
  const KITBY=Object.fromEntries([...KIT.values()].filter(e=>e.id).map(e=>[e.id,e]));
  // ---- every part
  for(const it of items){if(only.length&&!only.includes(it.id))continue;const r={};result.items[it.id]=r;const tag=it.id;
   let s=await sel(page,it.id);if(s.sel!==it.id){fail(`${tag}: select landed on ${s.sel}`);continue}
   const st=await stageInfo(page);
   if(!it.model&&!it.context){if(st.toolsShown)fail(`${tag}: tools shown for an item without a model`);
    const msg=await page.evaluate(()=>document.getElementById('msg').textContent);if(!/no 3D model/.test(msg))fail(`${tag}: no "no model" message`);r.model=false;continue}
   const printed=it.type.startsWith('print'),px=await page.evaluate(()=>showcase.pixels());r.coverage=+px.model.toFixed(4);
   if(px.model<.004)fail(`${tag}: 3D view blank (${px.model})`);
   // dimensions: Key, then All
   if(it.dims.length||printed){
    let L=await labelsOk(page,tag+'/key');const ns=new Set(L.map(l=>String(l.n)));
    for(const d of it.dims)if(d.key&&!ns.has(String(d.n)))fail(`${tag}: key dimension ${d.n} (${d.text}) not drawn`);
    const ov=L.filter(l=>l.k==='ov').length;if(printed&&ov!==3)fail(`${tag}: ${ov} overall sizes drawn`);
    r.labels_key=L.length;
    await set(page,{dims:'all',reframe:false});L=await labelsOk(page,tag+'/all');const na=new Set(L.map(l=>String(l.n)));
    const missing=it.dims.filter(d=>!na.has(String(d.n))).map(d=>d.n);r.labels_all=L.length;if(missing.length)r.all_not_in_view=missing;
    if(missing.filter(n=>it.dims.find(d=>d.n===n).key).length)fail(`${tag}: key dimensions ${missing} missing in "All"`);
    // hovering a dimension shows it in the table colour and on the model
    const d0=it.dims.find(d=>d.key)||it.dims[0];
    if(d0){await set(page,{dims:'key',hover:d0.n,reframe:false});L=await page.evaluate(()=>showcase.labels());const h=L.find(l=>String(l.n)===String(d0.n));
     if(!h||!/\bhot\b/.test(h.cls))fail(`${tag}: hovered dimension ${d0.n} not highlighted`)}
    await set(page,{dims:'key',hover:0,reframe:false})}
   // section cut along X through the middle: cut faces appear
   const pOff=await page.evaluate(()=>showcase.pixels());await set(page,{cut:0,cutT:0,reframe:false});const pOn=await page.evaluate(()=>showcase.pixels());
   const cutPx=Math.round((pOn.cap-pOff.cap)*pOn.w*pOn.h);r.cut_face_px=cutPx;if(cutPx<30)fail(`${tag}: no cut faces in the X section (${cutPx} px)`);
   await set(page,{cut:-1,reframe:false});
   // printed: on the bed and as fitted, left and right
   if(printed){const sz=it.size;r.bed={};
    for(const side of it.mirror?['left','right']:['left']){await set(page,{side,pose:'bed'});let b=await box(page);
     const ext=b.max.map((v,k)=>v-b.min[k]),c=b.max.map((v,k)=>(v+b.min[k])/2);r.bed[side]={size:ext.map(v=>+v.toFixed(3)),min_z:+b.min[2].toFixed(4)};
     if(!near(b.min[2],0,.005))fail(`${tag}/${side}: on the bed, lowest point at Z ${b.min[2]}`);
     if(!near(c[0],0,.05)||!near(c[1],0,.05))fail(`${tag}/${side}: not centred on the bed (${c})`);
     if(ext.some((v,k)=>!near(v,sz[k],.051)))fail(`${tag}/${side}: bed size ${ext} / ${sz}`);
     await set(page,{pose:'fit'});b=await box(page);const fe=b.max.map((v,k)=>v-b.min[k]).sort((a,b)=>a-b),se=[...sz].sort((a,b)=>a-b);
     if(fe.some((v,k)=>!near(v,se[k],.06)))fail(`${tag}/${side}: as fitted ${fe} / ${se}`)}
    await set(page,{side:'left',pose:'bed'})}
   // the spring at its three lengths
   if(it.id==='spring'){r.spring={};
    for(const [k,want] of [['free',SPRING.free],['set',SPRING.fitted],['stop',null]]){await set(page,{spring:k});const b=await page.evaluate(()=>showcase.springBox());
     const e=b.max.map((v,j)=>v-b.min[j]);r.spring[k]=e.map(v=>+v.toFixed(3));
     if(want!=null&&!near(e[0],want,.02))fail(`spring ${k}: ${e[0]} long, kit ${want}`);
     if(want==null&&!(e[0]>SPRING.solid&&e[0]<SPRING.fitted))fail(`spring at the recoil stop: ${e[0]} (solid ${SPRING.solid}, fitted ${SPRING.fitted})`);
     if(!near(e[1],SPRING.od,.02)||!near(e[2],SPRING.od,.02))fail(`spring ${k}: ${e[1]} x ${e[2]} across, kit OD ${SPRING.od}`)}
    await set(page,{spring:'free'})}
   // in the track: as many pieces highlighted as the kit lists per track (X101 joints: per machine)
   if(it.context){const k=KITBY[it.id],want=it.context==='x1'?(k&&k.total):(k?k.per_track:null);r.track={};
    for(const side of it.mirror&&it.context==='module'?['left','right']:['left']){await set(page,{view:'track',side});s=await page.evaluate(()=>showcase.state());
     const n=legendCount(s);r.track[side]=n;const pp=await page.evaluate(()=>showcase.pixels());
     if(pp.model<.01)fail(`${tag}: track view blank`);
     if(want==null)fail(`${tag}: no kit quantity to compare`);else if(n!==want)fail(`${tag}/${side}: ${n} highlighted in the track, kit ${want}`);
     if(it.context==='module'&&!s.legend.endsWith(`one ${side} track`))fail(`${tag}: legend "${s.legend}"`);
     const L=await page.evaluate(()=>showcase.labels());if(L.length)fail(`${tag}: dimension labels in the track view`)}
    await set(page,{view:'part',side:'left'})}
   console.log('Checked',it.id,JSON.stringify(r))}
  // ---- the overview, click to identify, keyboard and address
  await page.evaluate(()=>showcase.hold(false));
  if(!only.length){
   let s=await sel(page,'overview');const pv=await page.evaluate(()=>showcase.pixels());result.overview_coverage=+pv.model.toFixed(4);if(pv.model<.03)fail('overview blank');
   if(s.view!=='track')fail('overview not in the track view');
   // click to identify: from the overview the clicked part opens on its own; in a part's track view it is shown in the track
   const cb=await page.locator('#stage canvas').boundingBox(),BY=Object.fromEntries(items.map(i=>[i.id,i]));
   const clickAround=async from=>{for(const [fx,fy] of [[.5,.5],[.45,.55],[.55,.45],[.4,.5],[.6,.5]]){await page.mouse.click(cb.x+cb.width*fx,cb.y+cb.height*fy);
    const st=await page.evaluate(()=>showcase.state());if(st.sel!==from)return st}return null};
   let st=await clickAround('overview');result.click_identify={overview:st&&st.sel};
   if(!st)fail('clicking the track in the overview identifies nothing');else if(st.view!=='part')fail(`clicking ${st.sel} in the overview: ${st.view} view`);
   await sel(page,'J904');await set(page,{view:'track'});st=await clickAround('J904');result.click_identify.track_view=st&&st.sel;
   if(!st)fail('clicking in the J904 track view identifies nothing');
   else{const k=KITBY[st.sel],want=k&&(BY[st.sel].context==='x1'?k.total:k.per_track);
    if(st.view!=='track'||legendCount(st)!==want)fail(`clicking ${st.sel} in the J904 track view: ${st.view} "${st.legend}" (kit ${want})`)}
   await sel(page,'J902');await page.keyboard.press('ArrowDown');s=await page.evaluate(()=>showcase.state());if(s.sel!=='J903')fail('ArrowDown from J902 lands on '+s.sel);
   await page.keyboard.press('Escape');s=await page.evaluate(()=>showcase.state());if(s.sel!=='overview')fail('Escape lands on '+s.sel);
   await page.evaluate(()=>{location.hash='J906'});await page.waitForFunction(()=>showcase.state().sel==='J906',null,{timeout:20000}).catch(()=>fail('#J906 does not open J906'));
   // hovering a row of the dimensions table
   await sel(page,'J904');await page.hover('#info tr[data-n="1"]');const hov=await page.evaluate(()=>({row:document.querySelector('#info tr[data-n="1"]').classList.contains('hot'),lab:showcase.labels().filter(l=>/\bhot\b/.test(l.cls)).map(l=>l.n)}));
   if(!hov.row||JSON.stringify(hov.lab)!=='[1]')fail('hovering row 1 of J904: '+JSON.stringify(hov));await page.mouse.move(5,5);
   // search and filters
   const cards=()=>page.evaluate(()=>[...document.querySelectorAll('#list .card')].map(c=>c.dataset.id));
   const filt=async f=>{await page.click(`#filters button[data-f="${f}"]`);return cards()};
   const T=Object.fromEntries(items.map(i=>[i.id,i]));result.filters={};
   for(const [f,ok] of [['print',i=>i.type.startsWith('print')],['buy',i=>['buy','joint','chain'].includes(i.type)],['chain',i=>i.type==='chain'||i.id==='J910'||i.id==='dummy'],['none',i=>!i.model]]){
    const c=await filt(f),want=items.filter(ok).map(i=>i.id);result.filters[f]=c.length;if(JSON.stringify(c)!==JSON.stringify(want))fail(`filter ${f}: ${c}`)}
   await filt('all');if((await cards()).length!==items.length+1)fail('filter all: not every item listed');
   await page.fill('#q','608');let c=await cards();result.search_608=c;if(!c.includes('608ZZ')||c.includes('J904'))fail('search 608: '+c);
   await page.fill('#q','m3 x 25 socket');c=await cards();result.search_m3x25=c;if(!c.includes('M3x25')||['M3x6','M3x50','M3x8','M4x70'].some(k=>c.includes(k)))fail('search "m3 x 25 socket": '+c);
   await page.fill('#q','');
   await page.click('#list .card[data-id="J907"]');s=await page.evaluate(()=>showcase.state());if(s.sel!=='J907')fail('clicking the J907 card opens '+s.sel);
   const body=await page.locator('body').innerText();if(/[㐀-鿿]/.test(body))fail('non-English interface text');
   // thumbnails: one per model and the overview, on their cards
   await sel(page,'overview');await page.waitForFunction(()=>showcase.pendingThumbs()===0,null,{timeout:600000}).catch(()=>fail('thumbnails not finished'));
   const th=await page.evaluate(()=>({n:showcase.thumbs(),cards:[...document.querySelectorAll('#list .card .th')].filter(e=>/url\(/.test(e.style.backgroundImage)).length}));
   const nm=items.filter(i=>i.model).length+1;result.thumbnails=th;if(th.n!==nm||th.cards!==nm)fail(`thumbnails ${JSON.stringify(th)}, want ${nm}`);
   // screenshots
   if(write){result.screenshots={};
    const shots=[['showcase_overview','overview',{}],['showcase_J901','J901',{}],['showcase_J902_all','J902',{dims:'all',reframe:false}],
     ['showcase_J906_cut','J906',{cut:0,cutT:0,reframe:false}],['showcase_J904_track','J904',{view:'track'}],['showcase_J909_right','J909',{side:'right'}],
     ['showcase_spring','spring',{spring:'set'}],['showcase_X101_joint','M4x25',{view:'track'}]];
    for(const [name,id,o] of shots){await sel(page,id);if(Object.keys(o).length)await set(page,o);await page.waitForTimeout(400);await page.evaluate(()=>showcase.render());
     const f=path.join(root,'images',name+'.png');await page.screenshot({path:f,timeout:SHOT_MS});result.screenshots[name]={file:'images/'+name+'.png',sha256:sha(f)};console.log('Screenshot',name)}}
   // a phone-sized window
   await page.setViewportSize({width:390,height:844});await sel(page,'J904');await page.waitForTimeout(500);await page.evaluate(()=>showcase.render());
   const m=await page.evaluate(()=>({sw:document.documentElement.scrollWidth,iw:innerWidth,list:getComputedStyle(document.getElementById('list')).display}));
   result.phone={...m};if(m.sw>m.iw)fail(`phone: page ${m.sw} px wide in a ${m.iw} px window`);
   const L=await labelsOk(page,'phone/J904');result.phone.labels=L.length;const ns=new Set(L.map(l=>String(l.n)));
   for(const d of items.find(i=>i.id==='J904').dims)if(d.key&&!ns.has(String(d.n)))fail(`phone: key dimension ${d.n} not drawn`);
   if(write){const f=path.join(root,'images','showcase_phone.png');await page.screenshot({path:f,timeout:SHOT_MS});result.screenshots.showcase_phone={file:'images/showcase_phone.png',sha256:sha(f)};console.log('Screenshot showcase_phone')}
  }
 }finally{await browser.close()}
 if(errors.length)fail('console errors: '+JSON.stringify(errors));if(network.length)fail('network requests: '+JSON.stringify(network));
 const out={pass:!problems.length,html_sha256:sha(html),checker_sha256:sha(__filename),...result,problems,errors,network};
 if(write)fs.writeFileSync(path.join(root,'parts_showcase_browser.json'),JSON.stringify(out,null,1)+'\n');
 console.log(out.pass?'Showcase checks PASS':'Showcase checks FAIL',JSON.stringify({items:Object.keys(result.items).length,load:result.load_seconds,problems:problems.length}));
 if(!out.pass)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});

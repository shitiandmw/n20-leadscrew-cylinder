// Exercise the offline viewer, then capture each still in a fresh browser.
// Reuse functional evidence only for identical checker, HTML and scene hashes.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const root=path.resolve(__dirname,'..'),errors=[],network=[];
const allViews=['iso','rear','front','top','seat','under','mounts','springs','frame','drive','hub','exploded','body','cab','bodyright','bodyin','service'];
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
async function withPage(action){
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:900},deviceScaleFactor:1});
  page.setDefaultTimeout(120000);
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
  page.on('request',r=>{if(!r.url().startsWith('file:')&&!r.url().startsWith('data:'))network.push(r.url())});
  await page.goto('file://'+path.join(root,'3D_preview.html'));
  await page.waitForFunction(()=>window.x1&&window.x1.state().meshes>200,null,{timeout:600000});
  await action(page);
 }finally{await browser.close()}
}
(async()=>{
 fs.mkdirSync(path.join(root,'images'),{recursive:true});
 const hashes={html_sha256:sha(path.join(root,'3D_preview.html')),scene_sha256:sha(path.join(root,'source/x1_scene.json.gz')),checker_sha256:sha(__filename)};
 const checkpoint=path.join(require('os').tmpdir(),'x1-browser-functional.json');
 let saved=null;try{saved=JSON.parse(fs.readFileSync(checkpoint,'utf8'))}catch{}
 let st,moving,sw,bd,bs,played=null,tPlayDone=null;
 if(saved&&saved.pass&&Object.entries(hashes).every(([k,v])=>saved[k]===v)){
  ({st,moving,sw,bd,bs,played,tPlayDone}=saved);console.log('Reuse identical functional viewer evidence');
 }else{
 await withPage(async page=>{
  const frameBaseColor=await page.evaluate(()=>x1.state().frameColor);
  for(const v of allViews){
   await page.evaluate(v=>{x1.setView(v);x1.render()},v);
   const state=await page.evaluate(()=>x1.state());console.log('View',v);
   if(v==='mounts'?state.frameColor===frameBaseColor:state.frameColor!==frameBaseColor)throw Error('inspection color/restoration '+v);
   if(state.springSection!==(v==='springs')||state.frameVisible===(v==='springs')||!state.springVisible&&v==='springs')throw Error('spring cutaway/visibility restoration '+v);
  }
  bd=await page.evaluate(()=>{x1.setView('bodyin');return x1.state()});
  if(!(bd.body_items>30)||bd.body_prints_visible)throw Error('body inside view '+JSON.stringify(bd));
  bs=await page.evaluate(()=>{x1.setView('service');return x1.state()});
  if(!bs.service||!bs.body_prints_visible||!bs.hatch_lifted)throw Error('body service view '+JSON.stringify(bs));
  await page.evaluate(()=>{x1.setView('iso');x1.setPhase(.5);x1.render()});
  st=await page.evaluate(()=>x1.state());
  if(Math.abs(st.phase-.5)>1e-9||st.links!==68||!st.chains.every(Boolean))throw Error('phase/links '+JSON.stringify(st));
  await page.locator('#body').evaluate(input=>input.click());
  if(await page.evaluate(()=>x1.state().body_prints_visible))throw Error('body toggle');
  await page.locator('#run').evaluate(input=>input.click());
  await page.waitForFunction(()=>x1.state().phase>.5,null,{timeout:120000});
  moving=await page.evaluate(()=>x1.state());await page.locator('#run').dispatchEvent('click');
  if((await page.evaluate(()=>x1.state())).trackPlaying)throw Error('run stop');
  await page.evaluate(()=>{x1.setView('drive');x1.setSwing(30);x1.render()});
  sw=await page.evaluate(()=>x1.state());
  if(Math.abs(sw.swing-30)>1e-9||Math.abs(sw.pinion_rel_deg-120)>1e-6||!sw.turntable_items)throw Error('swing '+JSON.stringify(sw));
  if(sw.swing_cases.length){
   await page.evaluate(()=>x1.setSwing(0));await page.locator('#play').evaluate(input=>input.click());const tPlay=Date.now();
   await page.waitForFunction(()=>Math.abs(x1.state().swing)>.01,null,{timeout:120000});
   played=await page.evaluate(()=>x1.state().swing);tPlayDone=Date.now()-tPlay;await page.locator('#play').dispatchEvent('click');
   if((await page.evaluate(()=>x1.state())).swingPlaying)throw Error('swing stop');
   if(!(Math.abs(played)>.01))throw Error('swing playback did not move');
  }
  await page.evaluate(()=>{x1.setView('iso');x1.render()});
  if(!(await page.evaluate(()=>x1.state().body_prints_visible)))throw Error('body back on in iso');
  await page.locator('#body').evaluate(input=>input.click());
  if(await page.evaluate(()=>x1.state().body_prints_visible))throw Error('body toggle off');
  await page.locator('#body').evaluate(input=>input.click());
  if(!(await page.evaluate(()=>x1.state().body_prints_visible)))throw Error('body toggle on');
  await page.locator('#track').evaluate(input=>input.click());
  if((await page.evaluate(()=>x1.state())).chains.some(Boolean))throw Error('track toggle');
  if(/[㐀-鿿]/.test(await page.locator('body').innerText()))throw Error('Non-English interface');
 });
 if(errors.length||network.length)throw Error(JSON.stringify({errors,network}));
 fs.writeFileSync(checkpoint,JSON.stringify({pass:true,...hashes,st,moving,sw,bd,bs,played,tPlayDone},null,1)+'\n');
 console.log('Functional viewer checks PASS');
 }
 const shots={},shotHashes={},modelShots={},modelShotHashes={},shotViews=['mounts','frame',...allViews.filter(v=>!['mounts','frame'].includes(v)),'drive_swing30'];
 const capturePath=path.join(require('os').tmpdir(),'x1-browser-captures.json');
 let receipts={};try{const saved=JSON.parse(fs.readFileSync(capturePath,'utf8'));if(Object.entries(hashes).every(([k,v])=>saved[k]===v))receipts=saved.views||{}}catch{}
 const modelRequired=v=>['iso','mounts','frame','springs'].includes(v);
 const currentReceipt=(v,r)=>{try{return r&&sha(path.join(root,r.file))===r.sha256&&(!modelRequired(v)||(r.model_file&&sha(path.join(root,r.model_file))===r.model_sha256))}catch{return false}};
 function saveReceipt(){const temp=capturePath+'.'+process.pid+'.tmp';fs.writeFileSync(temp,JSON.stringify({...hashes,views:receipts},null,1)+'\n');fs.renameSync(temp,capturePath)}
 for(const v of shotViews){
  if(!currentReceipt(v,receipts[v]))await withPage(async page=>{
   await page.evaluate(v=>{x1.setView(v==='drive_swing30'?'drive':v);x1.setPhase(0);x1.setSwing(v==='drive_swing30'?30:0);x1.render()},v);
   const file='images/X1_'+v+'.png';
   await page.screenshot({path:path.join(root,file),timeout:600000});
   const receipt={file,sha256:sha(path.join(root,file))};
   if(modelRequired(v)){
    const rendered=await page.evaluate(()=>document.querySelector('#stage canvas').toDataURL('image/png'));
    const modelFile='images/X1_'+v+'_model.png';fs.writeFileSync(path.join(root,modelFile),Buffer.from(rendered.split(',')[1],'base64'));
    receipt.model_file=modelFile;receipt.model_sha256=sha(path.join(root,modelFile));
   }
   if(errors.length||network.length)throw Error(JSON.stringify({errors,network}));
   receipts[v]=receipt;saveReceipt();console.log('Screenshot',v);
  });else console.log('Reuse identical screenshot',v);
  const r=receipts[v];shots[v]=r.file;shotHashes[v]=r.sha256;
  if(modelRequired(v)){modelShots[v]=r.model_file;modelShotHashes[v]=r.model_sha256}
 }
 if(errors.length||network.length)throw Error(JSON.stringify({errors,network}));
 if(hashes.html_sha256!==sha(path.join(root,'3D_preview.html'))||hashes.scene_sha256!==sha(path.join(root,'source/x1_scene.json.gz')))throw Error('Viewer source changed during checks');
 fs.writeFileSync(path.join(root,'browser_validation.json'),JSON.stringify({pass:true,...hashes,views:shots,screenshot_sha256:shotHashes,model_views:modelShots,model_screenshot_sha256:modelShotHashes,state:st,swing_check:{swing:sw.swing,pinion_rel_deg:sw.pinion_rel_deg,turntable_items:sw.turntable_items,playback_swing:played,playback_wait_ms:tPlayDone},body_check:{items:bd.body_items,inside_view_prints_hidden:!bd.body_prints_visible,service_pose:bs.service,hatch_lifted_in_service:bs.hatch_lifted},run_phase_after_start:moving.phase,errors,network},null,1)+'\n');
 console.log('Viewer PASS',JSON.stringify(st));
})().catch(e=>{console.error(e);process.exitCode=1});

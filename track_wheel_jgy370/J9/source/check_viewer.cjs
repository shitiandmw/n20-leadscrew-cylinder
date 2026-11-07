// Exercise the offline track viewer and save resumable, current-input captures.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),crypto=require('crypto'),os=require('os');
const root=path.resolve(__dirname,'..'),errors=[],network=[];
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const allViews=['iso','outboard','inboard','pod','top','frame','spring','exploded'];
async function withPage(action){
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:900},deviceScaleFactor:1});page.setDefaultTimeout(120000);
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
  page.on('request',r=>{if(!r.url().startsWith('file:')&&!r.url().startsWith('data:'))network.push(r.url())});
  await page.goto('file://'+path.join(root,'3D_preview.html'));
  await page.waitForFunction(()=>window.j9&&window.j9.state().meshes>100,null,{timeout:180000});
  await action(page);
 }finally{await browser.close()}
}
(async()=>{
 fs.mkdirSync(path.join(root,'images'),{recursive:true});
 const hashes={html_sha256:sha(path.join(root,'3D_preview.html')),scene_sha256:sha(path.join(root,'source/j9_scene.json.gz')),checker_sha256:sha(__filename)};
 const functionalPath=path.join(os.tmpdir(),'j9-reve-browser-functional.json');let saved=null;
 try{saved=JSON.parse(fs.readFileSync(functionalPath,'utf8'))}catch{}
 let st,moving;
 if(saved&&saved.pass&&Object.entries(hashes).every(([k,v])=>saved[k]===v)){
  ({st,moving}=saved);console.log('Reuse identical functional viewer evidence');
 }else{
  await withPage(async page=>{
   for(const v of allViews){
    await page.evaluate(v=>{j9.setView(v);j9.render()},v);const section=await page.evaluate(()=>j9.state());
    if(section.springSection!==(v==='spring')||(v==='spring'&&(!section.springVisible||section.track)))throw Error('spring section state '+JSON.stringify(section));
    console.log('View',v);
   }
   await page.evaluate(()=>{j9.setView('outboard');j9.setPhase(.5);j9.render()});st=await page.evaluate(()=>j9.state());
   if(Math.abs(st.phase-.5)>1e-9||st.links!==34)throw Error('phase/links '+JSON.stringify(st));
   await page.locator('#run').evaluate(el=>el.click());await page.waitForFunction(()=>j9.state().phase>.5,null,{timeout:120000});
   moving=await page.evaluate(()=>j9.state());await page.locator('#run').evaluate(el=>el.click());
   if((await page.locator('#run').innerText())!=='Run track')throw Error('run stop');
   await page.locator('#housing').evaluate(el=>{if(el.checked)el.click()});
   await page.locator('#track').evaluate(el=>{if(el.checked)el.click()});
   if((await page.evaluate(()=>j9.state())).track)throw Error('track toggle');
   if(/[㐀-鿿]/.test(await page.locator('body').innerText()))throw Error('Non-English interface');
  });
  if(errors.length||network.length)throw Error(JSON.stringify({errors,network}));
  fs.writeFileSync(functionalPath,JSON.stringify({pass:true,...hashes,st,moving},null,1)+'\n');
  console.log('Functional viewer checks PASS');
 }
 const capturePath=path.join(os.tmpdir(),'j9-reve-browser-captures.json');let receipts={};
 try{const r=JSON.parse(fs.readFileSync(capturePath,'utf8'));if(Object.entries(hashes).every(([k,v])=>r[k]===v))receipts=r.views||{}}catch{}
 const current=r=>{try{return r&&sha(path.join(root,r.file))===r.sha256}catch{return false}};
 const shots={},shotHashes={};
 for(const v of [...allViews,'outboard_half_pitch']){
  if(!current(receipts[v]))await withPage(async page=>{
   await page.evaluate(v=>{j9.setView(v==='outboard_half_pitch'?'outboard':v);j9.setPhase(v==='outboard_half_pitch'?.5:0);j9.render()},v);
   const file='images/J9_'+v+'.png';await page.screenshot({path:path.join(root,file),timeout:180000});
   if(errors.length||network.length)throw Error(JSON.stringify({errors,network}));
   receipts[v]={file,sha256:sha(path.join(root,file))};
   const temp=capturePath+'.'+process.pid+'.tmp';fs.writeFileSync(temp,JSON.stringify({...hashes,views:receipts},null,1)+'\n');fs.renameSync(temp,capturePath);
   console.log('Screenshot',v);
  });else console.log('Reuse identical screenshot',v);
  shots[v]=receipts[v].file;shotHashes[v]=receipts[v].sha256;
 }
 if(errors.length||network.length)throw Error(JSON.stringify({errors,network}));
 if(hashes.html_sha256!==sha(path.join(root,'3D_preview.html'))||hashes.scene_sha256!==sha(path.join(root,'source/j9_scene.json.gz')))throw Error('Viewer changed during checks');
 fs.writeFileSync(path.join(root,'browser_validation.json'),JSON.stringify({pass:true,...hashes,views:shots,screenshot_sha256:shotHashes,state:st,spring_section_and_restoration:true,run_phase_after_start:moving.phase,errors,network},null,1)+'\n');
 console.log('Viewer PASS',JSON.stringify(st));
})().catch(e=>{console.error(e);process.exitCode=1});

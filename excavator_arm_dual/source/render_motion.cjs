'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),zlib=require('zlib'),assert=require('node:assert/strict'),{chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),mode=process.argv[2]||'review',out=process.argv[3]||'/tmp/r10-review';
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath:process.env.BROWSER_PATH,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader']});
 try{
  const context=await browser.newContext({viewport:{width:1280,height:720},offline:true}),page=await context.newPage(),errors=[],network=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))network.push(r.url());});
  await page.goto('file://'+root+'/3D_preview.html');await page.waitForFunction(()=>window.motionReview?.state().ready);await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
  const meta=await page.evaluate(()=>({duration:motionReview.duration,phases:motionReview.phases}));
  const hash=crypto.createHash('sha256').update(fs.readFileSync(root+'/3D_preview.html')).digest('hex');
  if(mode==='review'){
   const comparisons=[];
   for(const name of ['unloaded','payload_150g']){
    const trace=JSON.parse(zlib.gunzipSync(fs.readFileSync(root+'/simulation/'+name+'_trace.json.gz'))),cases=trace.frames.filter((_,i)=>i%100===0);
    await page.evaluate(name=>motionReview.setMode(name),name);
    const result=await page.evaluate(cases=>{
     const render=renderer.render;renderer.render=()=>{};
     try{let tip=0,pose=0,side=0;for(const f of cases){const s=motionReview.seek((f.time+1e-7)/20);tip=Math.max(tip,Math.hypot(s.points.T[0]-f.tip_mm[0],s.points.T[1]-f.tip_mm[2]));for(const group of ['boom','stick','bucket','rocker','coupler']){pose=Math.max(pose,Math.abs(groups[group].rotation.y+f.angles[group]),Math.abs(groups[group].position.x-f.origins[group][0]),Math.abs(groups[group].position.z-f.origins[group][1]));}side=Math.max(side,Math.abs(groups.act_boom0.position.y+50),Math.abs(groups.act_boom1.position.y-50));for(const a of f.actuators){const group=groups['act_'+a.name];pose=Math.max(pose,Math.abs(group.rotation.y-(Math.PI/2-a.angle)),...group.position.toArray().map((v,j)=>Math.abs(v-a.origin[j])));const rod=group.children.find(m=>m.userData.moving);pose=Math.max(pose,Math.abs(rod.position.z-37.5-f.drive_strokes[C.drives.findIndex(d=>d.name===a.name)]));}}return {cases:cases.length,tip_error_mm:tip,body_pose_error:pose,side_error_mm:side};}finally{renderer.render=render;}
    },cases);
    assert.ok(result.tip_error_mm<1e-7&&result.body_pose_error<1e-9&&result.side_error_mm<1e-8,JSON.stringify(result));comparisons.push({name,...result});
   }
   await page.evaluate(()=>motionReview.setMode('kinematic'));
   const cases=JSON.parse(fs.readFileSync(root+'/source/kinematic_cases.json'));
   const kinematics=await page.evaluate(cases=>{let max=0;for(const row of cases){const s=solve(row.strokes);for(const [n,p] of Object.entries(row.points))max=Math.max(max,Math.hypot(s.p[n][0]-p[0],s.p[n][1]-p[1]));}return {cases:cases.length,error_mm:max};},cases);
   assert.ok(kinematics.error_mm<1e-7);
   const framed=[];
   for(const viewport of [{width:1280,height:720},{width:390,height:844}]){
    await page.setViewportSize(viewport);await page.waitForTimeout(100);
    for(const name of ['unloaded','payload_150g','kinematic']){
     await page.evaluate(name=>motionReview.setMode(name),name);
     for(const view of ['side','oblique','front']){
      const r=await page.evaluate(view=>{
       const render=renderer.render;renderer.render=()=>{};
       try{motionReview.setView(view);const bounds={xmin:Infinity,xmax:-Infinity,ymin:Infinity,ymax:-Infinity},p=new THREE.Vector3();for(let t=0;t<=54;t++){motionReview.seek(t);for(const m of objects.filter(m=>m.visible)){if(!m.geometry.boundingBox)m.geometry.computeBoundingBox();const b=m.geometry.boundingBox;for(const x of [b.min.x,b.max.x])for(const y of [b.min.y,b.max.y])for(const z of [b.min.z,b.max.z]){p.set(x,y,z).applyMatrix4(m.matrixWorld).project(camera);bounds.xmin=Math.min(bounds.xmin,p.x);bounds.xmax=Math.max(bounds.xmax,p.x);bounds.ymin=Math.min(bounds.ymin,p.y);bounds.ymax=Math.max(bounds.ymax,p.y);}}}return {bounds,overflow:document.documentElement.scrollWidth>innerWidth};}finally{renderer.render=render;}
      },view);
      assert.equal(r.overflow,false);assert.ok(Object.values(r.bounds).every(x=>Math.abs(x)<.98),JSON.stringify({viewport,name,view,...r}));framed.push({viewport,name,view,...r});
     }
    }
    await page.evaluate(async()=>{await motionReview.setMode('payload_150g');motionReview.setView('oblique');motionReview.seek(28);return new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));});
    await page.screenshot({path:path.join(out,viewport.width===390?'mobile.png':'oblique.png')});
   }
   await page.setViewportSize({width:1280,height:720});await page.evaluate(()=>motionReview.setView('side'));
   for(const p of meta.phases){await page.evaluate(t=>motionReview.seek(t),(p.start+p.end)/2);await page.screenshot({path:path.join(out,p.id+'.png')});}
   await page.evaluate(()=>{motionReview.setView('front');motionReview.seek(0);});await page.screenshot({path:path.join(out,'front.png')});
   await page.locator('#r10-mode').selectOption('payload_150g');await page.waitForFunction(()=>motionReview.state().mode==='payload_150g');await page.locator('#r10-view').selectOption('oblique');await page.locator('#r10-phase').selectOption('4');assert.equal(await page.evaluate(()=>motionReview.state().time),23);
   await page.locator('#r10-play').click();await page.waitForFunction(()=>motionReview.state().time>23.2);await page.locator('#r10-play').click();assert.equal(await page.evaluate(()=>motionReview.state().playing),false);
   assert.deepEqual(errors,[]);assert.deepEqual(network,[]);
   fs.writeFileSync(root+'/browser_validation.json',JSON.stringify({status:'PASS',html_sha256:hash,comparisons,kinematics,framed,checks:['Actual integrated body states','Two independently replayed boom drives at Y=-50/+50 mm','All three modes and views','Desktop/mobile framing','Playback/pause and phase selection','Offline; no errors or network'],errors,network},null,2));console.log('PASS review');
  }else{
   await page.evaluate(()=>motionReview.setMode('payload_150g'));
   const fps=24,total=meta.duration*fps,cdp=await context.newCDPSession(page),from=Number(process.argv[4]||0),to=Math.min(total,Number(process.argv[5]||total));const start=Date.now();
   for(let n=from;n<to;n++){
    await page.evaluate(t=>{motionReview.setView(t<1.5?'front':t<3?'oblique':'side');motionReview.seek(t);},n/fps);
    const s=await cdp.send('Page.captureScreenshot',{format:'jpeg',quality:92,fromSurface:true,captureBeyondViewport:false,optimizeForSpeed:true});fs.writeFileSync(path.join(out,`frame_${String(n).padStart(5,'0')}.jpg`),Buffer.from(s.data,'base64'));
    if(n%120===0)console.log(JSON.stringify({frame:n,total,elapsed_s:Math.round((Date.now()-start)/1000)}));
   }
   assert.deepEqual(errors,[]);assert.deepEqual(network,[]);
   fs.writeFileSync(path.join(out,`render_${from}_${to}.json`),JSON.stringify({fps,total,from,to,width:1280,height:720,html_sha256:hash,simulation:'payload_150g',playback_speed:20,...meta,errors,network},null,2));console.log('PASS frames');
  }
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

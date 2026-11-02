// Offline browser check of ../3D_preview.html; writes images/*.png and browser_validation.json.
// Run: NODE_PATH=<playwright node_modules> node check_viewer.cjs
const {chromium}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader']});
 const out={views:{},playback:{}};
 try{
  const context=await browser.newContext({viewport:{width:1500,height:950},offline:true});
  const page=await context.newPage(),errors=[],requests=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url());});
  await page.goto('file://'+root+'/3D_preview.html');
  await page.waitForFunction(()=>window.trackWheelState?.().renderCalls>0);
  const s0=await page.evaluate(()=>window.trackWheelState());
  assert.ok(s0.meshes>250,'scene meshes '+s0.meshes);
  for(const [v,file] of [['unit','unit'],['drive','final_drive_section'],['recoil','recoil_section'],['exploded','exploded'],['gear','gear_stage']]){
   await page.locator(`[data-view="${v}"]`).click();await page.waitForTimeout(400);
   const s=await page.evaluate(()=>window.trackWheelState());assert.equal(s.view,v);
   assert.equal(s.section,['drive','recoil','gear'].includes(v));
   await page.locator('#stage').screenshot({path:root+'/images/'+file+'.png'});out.views[v]={section:s.section,image:'images/'+file+'.png'};
  }
  await page.locator('[data-view="drive"]').click();await page.locator('#xray').check();await page.waitForTimeout(300);
  assert.equal((await page.evaluate(()=>window.trackWheelState())).xray,true);
  await page.locator('[data-view="unit"]').click();await page.waitForTimeout(300);
  await page.locator('#stage').screenshot({path:root+'/images/xray.png'});await page.locator('#xray').uncheck();
  // Playback: every case loads; readouts follow the trace.
  const cases=(await page.evaluate(()=>window.trackWheelState())).cases;
  for(const c of cases){
   const r=await page.evaluate(c=>{window.setTrackWheelFrame(c,0);const a=window.trackWheelState().readouts;window.setTrackWheelFrame(c,60);return [a,window.trackWheelState()]},c);
   assert.equal(r[1].caseName,c);assert.equal(r[1].frame,60);assert.equal(r[1].visibleTrack,0);assert.equal(r[1].visibleLinks,34);
   assert.ok(Number.isFinite(r[1].readouts.spring)&&Number.isFinite(r[1].readouts.current),JSON.stringify(r[1].readouts));
   out.playback[c]={frame60:r[1].readouts};
  }
  // Debris case at its largest recoil.
  const peak=await page.evaluate(()=>{const p=window.trackWheelPeak('debris');window.setTrackWheelView('recoil');window.setTrackWheelFrame('debris',p.frame);return {frame:p.frame,readouts:window.trackWheelState().readouts}});
  assert.ok(peak.readouts.recoil>2.5&&peak.readouts.recoil<4.1,JSON.stringify(peak));await page.waitForTimeout(300);
  await page.locator('#stage').screenshot({path:root+'/images/debris_recoil.png'});out.playback.debris_peak=peak;
  await page.evaluate(()=>{window.setTrackWheelView('unit');window.setTrackWheelFrame('obstacle',120)});await page.waitForTimeout(300);
  await page.locator('#stage').screenshot({path:root+'/images/obstacle_playback.png'});
  await page.locator('#reset').click();
  const s1=await page.evaluate(()=>window.trackWheelState());assert.equal(s1.frame,-1);assert.ok(s1.visibleTrack>100);
  // Play a second of the fixture case in real time.
  await page.selectOption('#case','fixture');await page.locator('#play').click();await page.waitForTimeout(1200);
  const s2=await page.evaluate(()=>window.trackWheelState());assert.ok(s2.frame>10,'playback advanced '+s2.frame);
  assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
  out.status='PASS';out.page_errors=errors;out.network_requests=requests;out.render_calls=s2.renderCalls;
 }catch(e){out.status='FAIL';out.error=String(e);console.error(e);process.exitCode=1}
 finally{fs.writeFileSync(root+'/browser_validation.json',JSON.stringify(out,null,1));await browser.close()}
 console.log('viewer check',out.status);
})();

const {chromium}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader']});
 try{
  const context=await browser.newContext({viewport:{width:1500,height:1000},offline:true});
  const page=await context.newPage(),errors=[],requests=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url());});
  await page.goto('file://'+root+'/3D_preview.html');
  await page.waitForFunction(()=>window.excavatorState?.().renderCalls>0);
  await page.locator('#stage').screenshot({path:root+'/images/overview.png'});
  console.log('Offline overview rendered');
  const cases=JSON.parse(fs.readFileSync(root+'/source/kinematic_cases.json','utf8'));
  const residuals=await page.evaluate(cases=>{
   let equation=0,rendered=0,gear=0;
   for(const test of cases)for(const yaw of [-150,0,150]){
    window.setExcavator(test.strokes,yaw);const v=window.excavatorState(),a=v.slew*Math.PI/180;
    if(v.slew!==yaw||v.strokes.some((stroke,i)=>stroke!==test.strokes[i]))throw new Error('Arm or slew command was restricted');
    for(const [key,p] of Object.entries(test.points))equation=Math.max(equation,Math.hypot(v.kinematics.p[key][0]-p[0],v.kinematics.p[key][1]-p[1]));
    for(const pin of v.pinPairs){const [r,f]=[['A','B'],['C','D'],['F','R']][pin.i];
     for(const [key,actual] of [[r,pin.rear],[f,pin.front]]){
      const p=test.points[key],x=p[0]+v.armOffset[0],y=pin.y+v.armOffset[1],z=p[1]+v.armOffset[2];
      rendered=Math.max(rendered,Math.hypot(actual[0]-(x*Math.cos(a)-y*Math.sin(a)),actual[1]-(x*Math.sin(a)+y*Math.cos(a)),actual[2]-z));
     }
    }
    gear=Math.max(gear,Math.abs(v.gearAngle+a*96/20));
   }
   return {equation,rendered,gear};
  },cases);
  assert.ok(residuals.equation<1e-8&&residuals.rendered<1e-8&&residuals.gear<1e-10,JSON.stringify(residuals));
  console.log('Arm and slew cases passed');
  await page.locator('#home').click();
  for(const v of ['side','front','mechanism']){
   await page.locator(`[data-view="${v}"]`).click();
   assert.equal((await page.evaluate(()=>window.excavatorState())).view,v);
   await page.locator('#stage').screenshot({path:root+'/images/'+v+'.png'});
  }
  await page.locator('[data-view="battery"]').click();
  const battery=await page.evaluate(()=>window.excavatorState());assert.equal(battery.batteryCells,2);assert.equal(battery.batteryLidVisible,false);
  await page.locator('#stage').screenshot({path:root+'/images/battery_bay.png'});
  await page.locator('#batteryCover').uncheck();assert.equal((await page.evaluate(()=>window.excavatorState())).batteryLidVisible,true);
  await page.locator('[data-view="mechanism"]').click();
  const visible=(await page.evaluate(()=>window.excavatorState())).visible;
  await page.locator('#hideTracks').check();assert.ok((await page.evaluate(()=>window.excavatorState())).visible<visible);
  await page.locator('#stage').screenshot({path:root+'/images/chassis_internals.png'});
  await page.locator('#home').click();
  for(let i=0;i<3;i++)for(const end of [0,60]){
   await page.locator('#stroke'+i).evaluate((el,v)=>{el.value=v;el.dispatchEvent(new Event('input'));},end);
   assert.equal((await page.evaluate(()=>window.excavatorState())).strokes[i],end);
  }
  await page.locator('#home').click();await page.locator('#play').click();
  await page.waitForFunction(()=>Math.abs(window.excavatorState().slew)>1);
  await page.locator('#play').click();assert.equal((await page.evaluate(()=>window.excavatorState())).playing,false);
  const slewAngles=[-150,-90,-21,-20,0,20,21,90,150],boomStrokes=[15.1,15,14.9,0,60];
  for(const yaw of slewAngles){
   await page.evaluate(yaw=>window.setExcavator([30,60,0],yaw),yaw);
   for(const stroke of boomStrokes){
    await page.locator('#stroke0').evaluate((el,v)=>{el.value=v;el.dispatchEvent(new Event('input'));},stroke);
    const state=await page.evaluate(()=>window.excavatorState());
    assert.deepEqual(state.strokes,[stroke,60,0]);assert.equal(state.slew,yaw);
    assert.equal(await page.locator('#stroke0').inputValue(),String(stroke));
    assert.equal(await page.locator('#s0').textContent(),stroke.toFixed(1)+' mm');
    assert.equal(await page.locator('#slew').inputValue(),String(yaw));
   }
  }
  await page.evaluate(()=>window.setExcavator([0,60,0],0));
  for(const yaw of slewAngles){
   await page.locator('#slew').evaluate((el,v)=>{el.value=v;el.dispatchEvent(new Event('input'));},yaw);
   const state=await page.evaluate(()=>window.excavatorState());
   assert.equal(state.slew,yaw);assert.deepEqual(state.strokes,[0,60,0]);
   assert.equal(await page.locator('#slewValue').textContent(),yaw+'°');
  }
  await page.evaluate(()=>window.setExcavator([-1,61,30],151));
  let bounded=await page.evaluate(()=>window.excavatorState());
  assert.deepEqual(bounded.strokes,[0,60,30]);assert.equal(bounded.slew,150);
  await page.evaluate(()=>window.setExcavator([61,-1,30],-151));
  bounded=await page.evaluate(()=>window.excavatorState());
  assert.deepEqual(bounded.strokes,[60,0,30]);assert.equal(bounded.slew,-150);
  console.log('Cameras and independent controls passed');
  // Compare rendered rigid bodies with independently saved SI simulation output.
  const trace=JSON.parse(fs.readFileSync(root+'/simulation/track_ground_trace.json','utf8'));
  const traceHash=crypto.createHash('sha256').update(fs.readFileSync(root+'/simulation/track_ground_trace.json')).digest('hex');
  assert.equal((await page.evaluate(()=>window.trackState())).sourceTraceSha256,traceHash);
  const config=JSON.parse(fs.readFileSync(root+'/parameters.json','utf8'));
  const trackReport=await page.evaluate(({trace,config})=>{
   let closure=0,pitch=0,pin=0,source=0,wheel=0,takeup=0,gear=0,spring=0;let sampled=0;
   const distance=(a,b)=>Math.hypot(...a.map((v,i)=>v-b[i]));
   const checks=t=>{
    window.setTrackTime(t);const r=window.trackState();sampled++;
    for(const side of ['L','R'])for(let i=0;i<config.track_links_per_side;i++){
     const link=r.links[side][i],next=r.links[side][(i+1)%config.track_links_per_side];
     pitch=Math.max(pitch,Math.abs(distance(link.front,link.rear)-config.track_pitch));
     closure=Math.max(closure,distance(link.rear,next.front));
     const actual=r.pinCentres.find(p=>p.name==='track_pin_'+side+String(i).padStart(2,'0'));
     pin=Math.max(pin,distance(actual.centre,link.front));
     const bush=r.bushingCentres.find(p=>p.name==='track_bushing_'+side+String(i).padStart(2,'0'));
     pin=Math.max(pin,distance(bush.centre,link.front));
    }
    takeup=Math.max(takeup,Math.abs(r.idlerX-config.wheel_centres/2-r.carriageX));
    // R5 hub stage and recoil spring follow the drive angle and the yoke.
    for(const a of r.pinionAngles)gear=Math.max(gear,Math.abs(a-config.track_wheel.hub_ratio*r.wheelAngles[0]));
    for(const x of r.springFrontX)spring=Math.max(spring,Math.abs(x-(config.track_wheel.yoke_rear_x_mm+r.carriageX)));
    return r;
   };
   for(let i=0;i<trace.length;i+=37){
    const expected=trace[i],r=checks(expected.t);
    for(const side of ['L','R'])for(let j=0;j<config.track_links_per_side;j++){
     const p=expected.points[j].map((v,k)=>1000*(v+expected.frame[k])+(k===1?(side==='L'?-1:1)*config.track_centres/2:0));
     source=Math.max(source,distance(p,r.links[side][j].position));
    }
    for(let j=0;j<7;j++)wheel=Math.max(wheel,Math.abs(r.wheelAngles[j]-expected.wheels[j]));
   }
   for(let t=.007;t<34;t+=.31)checks(t);
   return {sampled_times:sampled,max_rendered_hinge_gap_mm:closure,max_rigid_pitch_error_mm:pitch,
    max_rendered_pin_offset_mm:pin,max_recorded_pose_error_mm:source,max_wheel_angle_error_rad:wheel,
    max_idler_carriage_error_mm:takeup,max_pinion_angle_error_rad:gear,max_spring_to_yoke_error_mm:spring};
  },{trace,config});
  assert.ok(trackReport.max_rendered_hinge_gap_mm<.06,JSON.stringify(trackReport));
  assert.ok(trackReport.max_rigid_pitch_error_mm<1e-8&&trackReport.max_rendered_pin_offset_mm<.001,JSON.stringify(trackReport));
  assert.ok(trackReport.max_recorded_pose_error_mm<.001&&trackReport.max_wheel_angle_error_rad<1e-5&&trackReport.max_idler_carriage_error_mm<1e-8,JSON.stringify(trackReport));
  assert.ok(trackReport.max_pinion_angle_error_rad<1e-5&&trackReport.max_spring_to_yoke_error_mm<.001,JSON.stringify(trackReport));
  console.log('Recorded track poses passed',trackReport);
  await page.locator('#home').click();await page.locator('[data-view="tracks"]').click();
  await page.evaluate(()=>window.setTrackTime(10.173));
  await page.locator('#stage').screenshot({path:root+'/images/track_motion.png'});
  const moving=await page.evaluate(()=>window.trackState());assert.ok(moving.frame[0]>400);
  await page.locator('#trackPlay').click();await page.waitForFunction(()=>window.trackState().time>10.4);
  await page.locator('#trackPlay').click();const paused=await page.evaluate(()=>window.trackState());
  await page.waitForTimeout(150);assert.equal((await page.evaluate(()=>window.trackState())).time,paused.time);
  await page.locator('#trackRate').selectOption('.5');assert.equal((await page.evaluate(()=>window.trackState())).rate,.5);
  await page.locator('#trackTime').evaluate(el=>{el.value=20;el.dispatchEvent(new Event('input'));});
  assert.equal((await page.evaluate(()=>window.trackState())).time,20);
  assert.equal(await page.locator('#trackPhase').textContent(),'Reverse');
  await page.evaluate(()=>window.setTrackTime(33.98));await page.locator('#trackPlay').click();
  await page.waitForFunction(()=>!window.trackState().playing);assert.ok((await page.evaluate(()=>window.trackState())).time>33.99);
  await page.locator('#trackReset').click();const resetTrack=await page.evaluate(()=>window.trackState());
  assert.equal(resetTrack.time,0);assert.deepEqual(resetTrack.frame,[0,0,0]);assert.equal(resetTrack.playing,false);
  await page.locator('#trackMarker').uncheck();await page.locator('#trackMarker').check();
  console.log('Track playback controls passed');
  await page.locator('#home').click();await page.setViewportSize({width:390,height:844});
  await page.waitForFunction(()=>document.querySelector('canvas').clientWidth<=innerWidth);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.screenshot({path:root+'/images/mobile.png',fullPage:true});
  assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
  const report={status:'PASS',track_motion:trackReport,arm_and_slew_cases:cases.length*3,unrestricted_lowering_cases:slewAngles.length*boomStrokes.length,low_boom_slew_cases:slewAngles.length,max_equation_difference_mm:residuals.equation,max_rendered_pin_difference_mm:residuals.rendered,max_gear_ratio_error_rad:residuals.gear,checks:['offline rendering','full boom stroke at every slew angle and full slew with boom lowered','independent stroke and slew endpoint limits','all actuator endpoints after slew','opposed 96:20 gear rotation','sliders','camera presets','mechanism cutaway','two visible 18650 cells and removable hood hatch','track visibility','recorded loaded track poses and rigid pin closure','wheel phase and idler carriage take-up','ground travel','track timeline, playback speed, pause, end-stop and reset','animation pause/reset','390 px mobile layout','no network requests or browser errors']};
  report.track_revision=config.track_revision;report.track_trace_sha256=traceHash;
  report.preview_sha256=crypto.createHash('sha256').update(fs.readFileSync(root+'/3D_preview.html')).digest('hex');
  fs.writeFileSync(root+'/browser_validation.json',JSON.stringify(report,null,2));console.log(report);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

const {chromium}=require('playwright');const fs=require('fs'),path=require('path');const {spawn}=require('child_process');const {createHash}=require('crypto');
const root=path.resolve(__dirname,'..'),preview=process.argv.includes('--preview'),fps=25;
const chapters=[
 {view:'bracket',seconds:4,title:'The same continuous frame layout on both sides.',text:'Broad continuous plates follow your reference. Both sides locate all five small-wheel axles.',detail:'Current axle positions suit 30 mm upper and 36 mm lower rollers. Cross ties hold the side plates 48 mm apart.',note:'The drive keeps its independent bearings. The idler retains its sliding yoke. Nominal CAD; no load rating established.'},
 {view:'exploded',seconds:6,title:'A full-length removable side plate',text:'Remove five M5 axle screws and three M4 tie screws, then slide the outer plate outboard.',detail:'A broad uninterrupted web joins the wheel mounts. Drive access and the idler travel slot are built into the plate.',note:'For wheel service, open and remove the chain first. Remove the one-piece housing for access to the rear axle heads.'},
 {view:'unit',seconds:3.5,title:'Original package retained',text:'The bracket fits the existing track size and motor location. The motor-to-idler protection remains one piece.',detail:'54 mm shoes. 220 mm nominal wheel centres. Original motor holes and chassis pads.',note:'Actual X-chassis and left motor fit remain unverified. The thin housing is separate from the load-bearing bracket.'},
 {view:'run',seconds:13.5,title:'Forward and reverse demonstration',text:'The continuous J8 side frames surround the retained wheels and moving track.',detail:'Reused J6 unloaded motion trace. Generic +/-20 rpm target; nominal chain speed 80 mm/s.',note:'Digital demonstration, not a new dynamics run or physical footage. Structural strength, vehicle traction and motor heating are not tested here.'}
];
// Save frames before encoding and recycle the software-GPU browser frequently.
// A failed export can resume from its content-keyed cache without losing frames.
(async()=>{
 const errors=[],network=[],samples=[];
 const key=createHash('sha256').update(fs.readFileSync(path.join(root,'3D_preview.html'))).update(JSON.stringify(chapters)).update('checkpoint-render-v1').digest('hex').slice(0,16);
 const cache=path.resolve(root,'../output/.j8_render_cache',key);fs.mkdirSync(cache,{recursive:true});
 let browser,page,currentChapter=-1,captures=0,frames=0,batches=0;
 async function closeBrowser(){if(browser){await browser.close().catch(()=>{});browser=null;page=null;currentChapter=-1;}}
 async function prepare(c){
  if(browser&&(currentChapter!==c||captures>=60))await closeBrowser();
  if(!browser){
   browser=await chromium.launch({headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader']});
   page=await browser.newPage({viewport:{width:1280,height:720},deviceScaleFactor:1});
   page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))network.push(r.url())});
   await page.goto('file://'+path.join(root,'3D_preview.html'),{timeout:60000});
   await page.waitForFunction(()=>window.j8?.state().links===34);await page.evaluate(()=>document.fonts.ready);
   await page.evaluate(({chapter,c})=>{j8.video(chapter,c);j8.liftBolts(0)},{chapter:chapters[c],c});
   currentChapter=c;captures=0;batches++;
  }
 }
 try{
  for(let c=0;c<chapters.length;c++){
   const chapter=chapters[c],count=preview?1:Math.round(chapter.seconds*fps),staticFrames=new Map();
   for(let i=0;i<count;i++){
    const t=preview?(c===3?3:c===1?4:chapter.seconds*.5):i/fps;
    const still=[0,2].includes(c)||(c===1&&t>=3.5),phase=c===0&&t>=2?1:0;
    const stem=String(frames).padStart(4,'0'),jpg=path.join(cache,`frame_${stem}.jpg`),state=path.join(cache,`frame_${stem}.json`);
    let buffer,sample;
    if(!preview&&fs.existsSync(jpg)&&fs.existsSync(state)){
     buffer=fs.readFileSync(jpg);sample=JSON.parse(fs.readFileSync(state,'utf8'));
    }else if(still&&staticFrames.has(phase)){
     ({buffer,sample}=staticFrames.get(phase));
    }else{
     await prepare(c);
     sample=await page.evaluate(({c,t})=>{
      let motion=null;if(c===0)j8.setView(t<2?'bracket':'top');
      if(c===1){const screw=Math.min(1,t/.7)*35,plate=Math.max(0,Math.min(1,(t-1)/2.5))*60;j8.setBracketTravel(plate,screw+plate)}
      if(c===3)motion=j8.setFrame(t);j8.render();return {...j8.state(),motion};
     },{c,t});
     buffer=await page.screenshot({type:'jpeg',quality:93});captures++;
     if(errors.length||network.length)throw Error(JSON.stringify({errors,network}));
    }
    if(still)staticFrames.set(phase,{buffer,sample});
    if(i===0||i===count-1)samples.push({chapter:c+1,frame:frames,...sample});
    if(preview)fs.writeFileSync(path.join(root,'images',`chapter_${c+1}.jpg`),buffer);
    else if(!fs.existsSync(jpg)||!fs.existsSync(state)){
     fs.writeFileSync(jpg+'.tmp',buffer);fs.renameSync(jpg+'.tmp',jpg);
     fs.writeFileSync(state,JSON.stringify(sample));
    }
    frames++;
    if(!preview&&i%50===0)console.log(`Chapter ${c+1}: ${i}/${count}`,JSON.stringify(sample.motion||{}));
   }
   await closeBrowser();console.log('Rendered:',chapter.title);
  }
 }finally{await closeBrowser();}
 if(!preview){
  const ffmpeg=process.env.FFMPEG||'/tmp/venv/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2';
  const output=path.join(root,'J8_operation.pending.mp4');
  console.log(`Encoding ${frames} saved frames...`);
  await new Promise((resolve,reject)=>{
   const encoder=spawn(ffmpeg,['-hide_banner','-loglevel','error','-y','-threads','2','-framerate',String(fps),'-start_number','0','-i',path.join(cache,'frame_%04d.jpg'),'-frames:v',String(frames),'-an','-c:v','libx264','-threads','2','-preset','medium','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',output],{stdio:['ignore','ignore','pipe']});
   let stderr='';encoder.stderr.on('data',d=>stderr+=d);encoder.on('error',reject);encoder.on('close',code=>code===0?resolve():reject(Error(stderr||String(code))));
  });
  fs.renameSync(output,path.join(root,'J8_operation.mp4'));
 }
 const report={pass:true,kind:preview?'preview':'video',width:1280,height:720,fps,frame_count:frames,duration_s:preview?null:frames/fps,chapters,samples,page_errors:errors,network_requests:network,render_batches:batches,checkpoint_key:key};
 fs.writeFileSync(path.join(root,preview?'video_preview_validation.json':'video_validation.json'),JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify({pass:true,frames,duration:report.duration_s}));
})().catch(e=>{console.error(e);process.exitCode=1;});

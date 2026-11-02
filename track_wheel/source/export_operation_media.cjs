// Export the existing R5 CAD viewer and recorded traces as a finite MP4 render.
// NODE_PATH=<playwright modules> FFMPEG=<ffmpeg executable> node source/export_operation_media.cjs
// Add --preview to render one review image per chapter without encoding a video.
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {once} = require('node:events');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '..');
const out = path.resolve(root, '../output/track_wheel_r5');
const fps = 25;
const chapters = [
  {view:'unit', seconds:3, title:'One independent track unit', text:'A rear sprocket drives 34 linked shoes. The front idler and five passive rollers guide the chain.', detail:'Yellow rear cap: enclosed final drive.\nOpposite end: spring-loaded idler.', caption:'R5 · In-hub gearmotor and recoil-spring idler', caseName:null},
  {view:'unit', seconds:4, title:'Forward travel', text:'The motor turns the sprocket. Its teeth engage the steel bushings between the track links.', detail:'The chain drives the idler and rollers.\nRecorded fixture test · normal speed.', caption:'Forward run · the frame is held stationary for this stand test', caseName:'fixture', from:1, rate:1},
  {view:'drive', seconds:4, title:'Motor inside the hub', text:'The 12 V gearmotor is fixed to the frame. Its 150:1 gearbox feeds an extra reduction inside the rotating hub.', detail:'Two hub bearings support track loads.\nThe offset motor shaft drives the pinion.', caption:'Horizontal section through the drive axis · recorded motion at normal speed', caseName:'fixture', from:1, rate:1},
  {view:'gear', seconds:4, title:'Pinion → ring → sprocket', text:'The steel 12-tooth pinion drives the 21-tooth internal ring in the hub cap.', detail:'Hub stage: 21 / 12 = 1.75:1.\nNominal total reduction: 262.5:1.', caption:'Gear section · motion shown at half speed', caseName:'fixture', from:1, rate:0.5},
  {view:'unit', seconds:4, title:'Reverse travel', text:'Reversing the motor reverses the track. Spring preload keeps the return strand tight.', detail:'Driver current limit: 1.0 A.\nRecorded fixture test · normal speed.', caption:'Reverse run · the same complete track unit', caseName:'fixture', from:7.5, rate:1},
  {view:'unit', seconds:5, title:'Crossing an obstacle', text:'The loaded unit travels over a 6 mm diameter rod. The chain, rollers and idler follow the recorded contact simulation.', detail:'Frame-following view: the floor and rod\nmove relative to the track unit.', caption:'Obstacle case · normal speed · the camera follows the unit frame', caseName:'obstacle', from:0, rate:1},
  {view:'recoil', seconds:7, title:'Spring recoil under debris', text:'A stone carried around the idler pushes the yoke back and compresses the spring. The spring returns the idler as the stone clears.', detail:'About 3.2 mm recoil in this simulation.\nMechanical recoil stop: 4.0 mm.', caption:'Vertical section through the spring · debris case at 0.4× speed', caseName:'debris', from:0, rate:0.4},
];

(async () => {
  fs.mkdirSync(out, {recursive:true});
  const preview = process.argv.includes('--preview');
  const browser = await chromium.launch({headless:true, args:['--no-sandbox','--enable-unsafe-swiftshader']});
  let encoder;
  const errors = [], requests = [];
  try {
    const page = await browser.newPage({viewport:{width:1280,height:720}, deviceScaleFactor:1, offline:true});
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', r => {if (/^https?:/.test(r.url())) requests.push(r.url());});
    await page.goto('file://' + path.join(root,'3D_preview.html'));
    await page.waitForFunction(() => window.trackWheelState?.().renderCalls > 0);
    await page.addStyleTag({content:`
      header{height:72px;padding:12px 24px}header h1{font-size:23px}header span{font-size:13px}
      main{height:648px}.bar{display:none}aside{width:340px;padding:25px 22px;overflow:hidden}
      aside h2{font-size:26px;line-height:1.15;margin:12px 0 16px}aside p{font-size:16px;line-height:1.5}
      .chapter{font-size:12px;letter-spacing:2px;color:#8d6305}.detail{white-space:pre-line;font-size:14px;color:#536269;margin:20px 0 24px;line-height:1.5}
      .metric{font-size:14px;padding:9px 0}.caption{bottom:16px;left:18px;right:18px;font-size:14px;padding:12px}
      .provenance{margin-top:24px;font-size:12px;color:#647067;line-height:1.5}
    `});
    await page.evaluate(() => {
      // Drive renders explicitly; do not draw a second frame in the animation loop.
      loop = () => {};
      controls.enableDamping = false;
      document.querySelector('header').innerHTML = '<div><div class="kicker">INDEPENDENT TRACK WHEEL / R5</div><h1>How the drive and recoil idler work</h1></div><span>CAD + recorded simulation · 31 Oct 2026</span>';
      document.querySelector('aside').innerHTML = '<div class="chapter" id="chapter"></div><h2 id="chapterTitle"></h2><p id="chapterText"></p><div class="detail" id="chapterDetail"></div><div id="readouts"><div class="metric"><span>Simulation time</span><b id="mT">—</b></div><div class="metric"><span>Sprocket speed</span><b id="mW">—</b></div><div class="metric"><span>Motor current</span><b id="mI">—</b></div><div class="metric"><span>Idler recoil*</span><b id="mX">—</b></div><div class="metric"><span>Spring force</span><b id="mF">—</b></div><b id="mP" hidden></b></div><div class="provenance">*Relative to the assembly position.<br>Digital model; no physical test footage.</div><input id="time" type="hidden">';
      const play = document.createElement('button');
      play.id = 'play'; play.hidden = true; document.body.appendChild(play);
      resize();
    });
    let encoderDone;
    if (!preview) {
      encoder = spawn(process.env.FFMPEG || 'ffmpeg', ['-hide_banner','-loglevel','error','-y',
        '-f','image2pipe','-framerate',String(fps),'-vcodec','mjpeg','-i','pipe:0',
        '-an','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',
        path.join(out,'track_wheel_r5_operation.mp4')], {stdio:['pipe','ignore','inherit']});
      encoderDone = new Promise((resolve,reject) => {
        encoder.on('error',reject);
        encoder.on('close',code => code === 0 ? resolve() : reject(new Error('ffmpeg exit '+code)));
      });
      // Register immediately so a failed executable cannot become an unhandled rejection.
      encoderDone.catch(() => {});
      encoder.stdin.on('error', e => errors.push('Encoder input: '+e.message));
    }
    const samples = [];
    let frameCount = 0;
    for (let c = 0; c < chapters.length; c++) {
      const chapter = chapters[c];
      await page.evaluate(({chapter,c,total}) => {
        state.playing = false;
        resetPose();
        setView(chapter.view);
        // Reframe closeups for the video aspect ratio, preserving the CAD geometry.
        if (chapter.view === 'gear') {
          camera.position.copy(controls.target.clone().add(camera.position.clone().sub(controls.target).multiplyScalar(1.28)));
        }
        if (chapter.view === 'unit') {
          camera.position.copy(controls.target.clone().add(camera.position.clone().sub(controls.target).multiplyScalar(0.84)));
        }
        controls.update();
        document.getElementById('chapter').textContent = `${String(c+1).padStart(2,'0')} / ${String(total).padStart(2,'0')}`;
        document.getElementById('chapterTitle').textContent = chapter.title;
        document.getElementById('chapterText').textContent = chapter.text;
        document.getElementById('chapterDetail').textContent = chapter.detail;
        document.getElementById('caption').textContent = chapter.caption;
        document.getElementById('readouts').style.visibility = chapter.caseName ? 'visible' : 'hidden';
        renderer.render(scene,camera);
      }, {chapter,c,total:chapters.length});
      const count = preview ? 1 : Math.round(chapter.seconds*fps);
      let still;
      const started = Date.now();
      for (let i = 0; i < count; i++) {
        const localTime = preview ? chapter.seconds/2 : i/fps;
        const sample = await page.evaluate(({chapter,localTime}) => {
          if (chapter.caseName) {
            const T = traces[chapter.caseName], a = trace(chapter.caseName);
            const dt = a[T.stride]-a[0];
            const k = Math.min(T.count-1,Math.max(0,Math.round((chapter.from+localTime*chapter.rate)/dt)));
            window.setTrackWheelFrame(chapter.caseName,k);
          }
          return window.trackWheelState();
        }, {chapter,localTime});
        if (i === 0 || i === count-1) samples.push({chapter:c+1,videoTime:frameCount/fps,...sample});
        const buffer = !chapter.caseName && still ? still : await page.screenshot({type:'jpeg',quality:92,animations:'disabled'});
        if (!chapter.caseName) still = buffer;
        if (preview) fs.writeFileSync(path.join(out,`preview_${c+1}_${chapter.view}.jpg`),buffer);
        else if (!encoder.stdin.write(buffer)) await once(encoder.stdin,'drain');
        frameCount++;
        if (!preview && i > 0 && i % fps === 0) console.log(`Chapter ${c+1}: ${i}/${count} frames, ${Math.round((Date.now()-started)/1000)} s elapsed`);
      }
      console.log(`Rendered ${c+1}/${chapters.length}: ${chapter.title}`);
    }
    if (encoder) {encoder.stdin.end(); await encoderDone;}
    if (errors.length || requests.length) throw new Error(JSON.stringify({errors,requests}));
    const report = {status:'PASS',source:'track_wheel/3D_preview.html',source_commit:require('node:child_process').execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim(),fps,frameCount,duration:preview?null:frameCount/fps,chapters,samples,page_errors:errors,network_requests:requests};
    fs.writeFileSync(path.join(out,preview?'preview_validation.json':'operation_video_validation.json'),JSON.stringify(report,null,2)+'\n');
    console.log(JSON.stringify({status:report.status,frameCount,duration:report.duration,out}));
  } finally {
    if (encoder && encoder.exitCode === null) encoder.kill();
    await browser.close();
  }
})().catch(e => {console.error(e);process.exitCode=1;});

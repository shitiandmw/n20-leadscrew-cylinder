// Load the offline viewer headless, exercise views and the run animation, save review images.
// NODE_PATH must contain playwright (see README).
const {chromium}=require('playwright');const fs=require('fs'),path=require('path');
(async()=>{const root=path.resolve(__dirname,'..');fs.mkdirSync(path.join(root,'images'),{recursive:true});
const browser=await chromium.launch({headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader']});
try{const page=await browser.newPage({viewport:{width:1500,height:900},deviceScaleFactor:1});const errors=[],network=[];
page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
page.on('request',r=>{if(!r.url().startsWith('file:')&&!r.url().startsWith('data:'))network.push(r.url())});
await page.goto('file://'+path.join(root,'3D_preview.html'));await page.waitForFunction(()=>window.j9&&window.j9.state().meshes>100,null,{timeout:120000});
const shots={};for(const v of ['iso','outboard','inboard','pod','top','frame','exploded']){await page.evaluate(v=>{j9.setView(v);j9.render()},v);await page.waitForTimeout(150);
 const file='images/J9_'+v+'.png';await page.screenshot({path:path.join(root,file)});shots[v]=file}
await page.evaluate(()=>{j9.setView('outboard');j9.setPhase(.5);j9.render()});await page.screenshot({path:path.join(root,'images/J9_outboard_half_pitch.png')});
const st=await page.evaluate(()=>j9.state());if(Math.abs(st.phase-.5)>1e-9||st.links!==34)throw Error('phase/links '+JSON.stringify(st));
await page.locator('#run').click();await page.waitForTimeout(700);const moving=await page.evaluate(()=>j9.state());await page.locator('#run').click();if(!(moving.phase>.5))throw Error('run did not advance');
await page.locator('#housing').uncheck();await page.locator('#track').uncheck();const t=await page.evaluate(()=>j9.state());if(t.track)throw Error('track toggle');
if(/[㐀-鿿]/.test(await page.locator('body').innerText()))throw Error('Non-English interface');
if(errors.length||network.length)throw Error(JSON.stringify({errors,network}));
fs.writeFileSync(path.join(root,'browser_validation.json'),JSON.stringify({pass:true,views:shots,state:st,run_phase_after_0_7s:moving.phase,errors,network},null,1)+'\n');console.log('viewer ok',JSON.stringify(st));
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});

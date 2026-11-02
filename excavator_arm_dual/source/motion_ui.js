/* Review actual R10 CAD with constrained targets or recorded MuJoCo states. */
(()=>{
const motion=__MOTION_DATA__;
const style=document.createElement('style');style.textContent=`
html,body{height:100%;margin:0;overflow:hidden;font-family:Arial,'Noto Sans CJK SC',sans-serif;color:#19333e}
body>header,body>main{display:none!important}
#r10{position:fixed;inset:0;display:grid;grid-template-rows:76px minmax(0,1fr) 92px;background:#eff3f1}
#r10-head{display:flex;justify-content:space-between;align-items:center;padding:18px 26px;background:white;border-bottom:1px solid #d6e0dc}
#r10-head b{font-size:23px}#r10-head small{font-size:12px;color:#58727a}
#r10-layout{display:grid;grid-template-columns:320px minmax(0,1fr);min-height:0}
#r10-copy{padding:22px 25px;background:#f9fbf9;overflow:auto;border-right:1px solid #d6e0dc}
#r10-copy h2{font-size:25px;line-height:1.45;margin:14px 0}#r10-copy p{font-size:14px;line-height:1.8;color:#506a72}
#r10-tag{color:#09828c;font-size:12px}#r10-live{font-size:13px;line-height:1.9;color:#156977;border-top:2px solid #dfa82a;padding-top:14px;margin-top:18px;font-variant-numeric:tabular-nums}
#r10-limit{font-size:11px;line-height:1.7;margin-top:20px;color:#60757b}
#r10 #stage{width:100%;height:100%;min-height:0}#stage .viewbar,#stage .stage-note,#stage #depth-label{display:none!important}
#r10-controls{background:white;border-top:1px solid #d6e0dc;padding:10px 22px;display:grid;gap:8px}
.r10-row{display:flex;align-items:center;gap:12px}#r10-controls button,#r10-controls select{border:1px solid #bed0ce;border-radius:4px;background:white;color:#19333e;padding:6px 10px;font-size:12px;cursor:pointer}
#r10-seek{flex:1;min-width:40px;margin:0;accent-color:#09828c}#r10-time{font-size:12px;white-space:nowrap;font-variant-numeric:tabular-nums}
@media(max-width:760px){#r10-head{display:block;padding:12px 16px}#r10-head b{font-size:18px}#r10-head small{display:block;margin-top:7px;font-size:10px}#r10-layout{grid-template-columns:1fr;grid-template-rows:minmax(0,1fr) 250px}#r10-copy{grid-row:2;padding:10px 16px;border-top:1px solid #d6e0dc}#r10-layout #stage{grid-row:1}#r10-copy h2{font-size:17px;margin:5px 0}#r10-copy p{font-size:11px;line-height:1.5;margin:0}#r10-live{font-size:11px;line-height:1.5;margin-top:8px;padding-top:6px}#r10-limit{font-size:10px;line-height:1.4;margin-top:7px}#r10-controls{padding:9px;gap:7px}.r10-row{gap:6px}#r10-controls select{max-width:125px}#r10-controls button{padding:6px}#r10-time{font-size:10px}}
`;document.head.appendChild(style);
const app=document.createElement('div');app.id='r10';app.innerHTML=`
<div id="r10-head"><b>R10 / 双推杆回旋镖形大臂</b><small>参考照片布局 · 2 根对称大臂推杆 · 5 颗可换斗齿</small></div>
<div id="r10-layout"><section id="r10-copy"><div id="r10-tag"></div><h2 id="r10-title"></h2><p id="r10-body"></p><div id="r10-live"></div><div id="r10-limit"></div></section></div>
<div id="r10-controls"><div class="r10-row"><select id="r10-mode" aria-label="仿真模式"><option value="unloaded">动力学 / 空载</option><option value="payload_150g">动力学 / 150 g 负载</option><option value="kinematic">目标运动学</option></select><select id="r10-view" aria-label="观察视角"><option value="oblique">斜视 / 双推杆</option><option value="side">侧视 / 动作轨迹</option><option value="front">正视 / 横向位置</option></select><select id="r10-phase" aria-label="动作阶段"></select></div>
<div class="r10-row"><button id="r10-play">播放</button><input id="r10-seek" type="range" min="0" max="54" step="0.02" value="0" aria-label="演示时间"><span id="r10-time"></span></div></div>`;
document.body.appendChild(app);document.getElementById('r10-layout').appendChild(stage);
const $=id=>document.getElementById(id);
for(const [i,p] of motion.phases.entries()){const o=document.createElement('option');o.value=i;o.textContent=p.title;$('r10-phase').appendChild(o);}
stop();state.cutaway=false;state.teethExploded=false;state.overlay=false;state.view='r10';grid.visible=false;mountingPlane.visible=false;grainGroup.visible=false;controls.enableDamping=false;controls.enabled=false;
renderer.setPixelRatio(1);renderer.shadowMap.enabled=false;
for(const m of objects){const old=m.material;m.material=new THREE.MeshPhongMaterial({color:old.color.clone(),shininess:m.userData.kind==='hardware'?65:25,side:THREE.DoubleSide});old.dispose();}
const targetLine=new THREE.Line(new THREE.BufferGeometry().setFromPoints(motion.frames.map(f=>new THREE.Vector3(f.tip[0],0,f.tip[1]))),new THREE.LineBasicMaterial({color:0x148791,transparent:true,opacity:.55,depthTest:false}));targetLine.renderOrder=8;scene.add(targetLine);
const datum=new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-70,-90,0),new THREE.Vector3(650,-90,0)]),new THREE.LineDashedMaterial({color:0x82979d,dashSize:8,gapSize:5,depthTest:false}));datum.computeLineDistances();scene.add(datum);
let current=0,playing=false,last=performance.now(),mode='kinematic',view='oblique',ready=false;
function cameraPose(){
 camera=orthographic;controls.object=camera;const aspect=stage.clientWidth/stage.clientHeight,h=Math.max(470,440/aspect);
 camera.left=-h*aspect;camera.right=h*aspect;camera.top=h;camera.bottom=-h;camera.zoom=1;camera.updateProjectionMatrix();
 controls.target.set(245,0,105);camera.position.set(...(view==='side'?[245,-1400,105]:view==='front'?[1645,-130,260]:[820,-1400,570]));camera.lookAt(controls.target);camera.updateMatrixWorld(true);
}
function seek(t){
 current=Math.max(0,Math.min(54,t));const q=current*48,i=Math.min(motion.frames.length-1,Math.floor(q)),j=Math.min(motion.frames.length-1,i+1),u=q-i,a=motion.frames[i],b=motion.frames[j];
 const target=a.strokes.map((x,k)=>x+(b.strokes[k]-x)*u);let actual=null;
 if(mode==='kinematic'){state.physicsFrame=null;state.strokes=target;update();}
 else{replay.data=physicsCache[mode];actual=seekPhysics(current*physicsCache[mode].scenario.presentation_time_scale);replay.playing=false;}
 state.view='r10';grainGroup.visible=false;const s=state.physicsFrame?replaySolution(state.physicsFrame):solve(state.strokes);
 const phase=motion.phases.find(p=>current<p.end)||motion.phases.at(-1);targetLine.geometry.setDrawRange(0,i+1);
 $('r10-tag').textContent=mode==='kinematic'?'目标轨迹 / 运动学':`MuJoCo 刚体动力学 / ${mode==='unloaded'?'空载':'固定 150 g 示例负载'}`;
 $('r10-title').textContent=phase.title;$('r10-body').textContent=phase.body;
 const error=actual?Math.max(...actual.drive_strokes.map((x,k)=>Math.abs(x-actual.target_drive_strokes[k]))):0;
 $('r10-live').innerHTML=`齿尖 X / Z：${s.p.T.map(x=>x.toFixed(1)).join(' / ')} mm<br>大臂 / 斗杆 / 铲斗行程：${state.strokes.map(x=>x.toFixed(1)).join(' / ')} mm`+(actual?`<br>左臂 / 右臂 / 斗杆 / 铲斗推力：<br>${actual.force_N.map(x=>x.toFixed(1)).join(' / ')} N<br><span style="color:${error>1?'#b95029':'inherit'}">最大行程跟随误差：${error.toFixed(2)} mm${error>1?'（偏离目标）':''}</span>`:'<br>左右推杆中心面：Y = −50 / +50 mm');
 $('r10-limit').innerHTML=mode==='kinematic'?'青线为目标齿尖轨迹；虚线为安装面 Z = 0。<br>可切换动力学结果，比较受重力后的实际运动。':'实际积分状态回放，播放速度为仿真时间的 20 倍。<br>假设每根推杆限力 100 N；底座固定。<br>未模拟土壤、整车倾覆或支座扭转变形。';
 $('r10-seek').value=current;$('r10-phase').value=motion.phases.indexOf(phase);$('r10-time').textContent=mode==='kinematic'?`${current.toFixed(1)} / 54 s`:`仿真 ${(current*20).toFixed(0)} / 1080 s`;
 cameraPose();scene.updateMatrixWorld(true);renderer.render(scene,camera);needsRender=false;
 return {time:current,mode,view,phase:phase.id,strokes:[...state.strokes],points:s.p,actual};
}
async function setMode(value){playing=false;$('r10-play').textContent='播放';mode=value;if(value!=='kinematic')await loadPhysics(value);else clearPhysics();$('r10-mode').value=value;state.view='r10';return seek(current);}
function setReviewView(value){if(view===value)return;view=value;$('r10-view').value=value;return seek(current);}
$('r10-mode').onchange=e=>setMode(e.target.value).catch(console.error);$('r10-view').onchange=e=>setReviewView(e.target.value);
$('r10-play').onclick=()=>{if(current>=54)seek(0);playing=!playing;$('r10-play').textContent=playing?'暂停':'播放';};
$('r10-seek').oninput=e=>{playing=false;$('r10-play').textContent='播放';seek(+e.target.value);};$('r10-phase').onchange=e=>{playing=false;$('r10-play').textContent='播放';seek(motion.phases[+e.target.value].start);};
function tick(t){const dt=Math.min(.1,(t-last)/1000);last=t;if(playing){seek(current+dt);if(current>=54){playing=false;$('r10-play').textContent='播放';}}requestAnimationFrame(tick);}
new ResizeObserver(()=>{renderer.setSize(stage.clientWidth,stage.clientHeight);if(ready)seek(current);}).observe(stage);
window.motionReview={seek,setMode,setView:setReviewView,duration:54,phases:motion.phases,state:()=>({time:current,mode,view,playing,ready})};
Promise.all(['unloaded','payload_150g'].map(async name=>{const bytes=Uint8Array.from(atob(physicsPacked[name]),c=>c.charCodeAt(0));physicsCache[name]=JSON.parse(await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).text());})).then(async()=>{await setMode('payload_150g');ready=true;requestAnimationFrame(tick);});
})();

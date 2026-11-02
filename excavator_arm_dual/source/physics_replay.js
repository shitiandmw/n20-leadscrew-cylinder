// Offline playback of integrated MuJoCo states; no inverse-kinematic projection.
const physicsPacked=__PHYSICS__,physicsCache={},replay={active:false,playing:false,time:0,data:null,name:null};
document.getElementById('physics-panel').innerHTML=`<div class="legend"><h2>Physics results</h2><p>Replay the simulated arm with gravity and limited motor thrust. Sliders above return to geometry mode.</p><select id="physics-case" aria-label="Physics scenario" style="width:100%;padding:8px"><option value="unloaded">Unloaded · 100 N drive</option><option value="payload_150g">150 g load · 100 N drive</option><option value="underpowered_20N">150 g load · weak 20 N drive</option><option value="grain_contact">Loose particles · contact example</option></select><div class="buttons"><button id="physics-play">▶ Load replay</button><select id="physics-speed" aria-label="Replay speed"><option value="1">1×</option><option value="5">5×</option><option value="10" selected>10×</option></select></div><input type="range" id="physics-time" aria-label="Simulation time" min="0" max="490" step="0.1" value="0"><div id="physics-readout">Select a scenario and load its results.</div><p>100 N and 20 N are assumed drive capacities. Particle contact is a qualitative example, not calibrated soil. The base is fixed.</p></div>`;
const grainGroup=new THREE.Group();scene.add(grainGroup);grainGroup.visible=false;
const grainMesh=new THREE.InstancedMesh(new THREE.SphereGeometry(4,8,6),new THREE.MeshStandardMaterial({color:0xb28b56,roughness:.95}),96);grainMesh.frustumCulled=false;grainGroup.add(grainMesh);
const tray=new THREE.Mesh(new THREE.BoxGeometry(260,150,4),new THREE.MeshStandardMaterial({color:0xb5bbb4,roughness:1}));tray.position.set(330,0,-347);grainGroup.add(tray);
function clearPhysics(){replay.active=false;replay.playing=false;state.physicsFrame=null;grainGroup.visible=false;document.getElementById('physics-play').textContent='▶ Load replay';document.getElementById('physics-readout').textContent='Geometry mode — load a scenario to replay physics.';needsRender=true;}
function replaySolution(f){
 const angles=f.angles,origins=f.origins,world=(g,v)=>add(origins[g],rot(v,angles[g]));
 const p={O:origins.boom,A:C.ground_cyl,B:world('boom',C.boom_lift),E:origins.stick,C:world('boom',C.stick_cyl),D:world('stick',C.stick_tail),F:world('stick',C.bucket_cyl),J:origins.rocker,R:origins.coupler,H:origins.bucket,Q:world('bucket',C.horn_point),T:[f.tip_mm[0],f.tip_mm[2]]};
 const a=sub(p.R,p.Q),b=sub(p.Q,p.H),mu=Math.acos(Math.min(1,Math.abs((a[0]*b[0]+a[1]*b[1])/(norm(a)*norm(b)))))*180/Math.PI;
 return {p,angles,origins,theta:angles.boom,phi:angles.stick-angles.boom,gamma:angles.bucket-angles.stick,mu};
}
async function loadPhysics(name){
 stop();state.teethExploded=false;document.getElementById('explode-teeth').checked=false;
 if(!physicsCache[name]){const bytes=Uint8Array.from(atob(physicsPacked[name]),c=>c.charCodeAt(0));const stream=new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));physicsCache[name]=JSON.parse(await new Response(stream).text());}
 replay.data=physicsCache[name];replay.name=name;replay.active=true;replay.time=0;replay.playing=false;document.getElementById('physics-case').value=name;document.getElementById('physics-time').max=replay.data.scenario.duration_s;setView('side');seekPhysics(0);
}
function seekPhysics(time){
 if(!replay.data)return;replay.active=true;replay.time=Math.max(0,Math.min(replay.data.scenario.duration_s,time));
 const frames=replay.data.frames;let lo=0,hi=frames.length-1;while(lo<hi){const m=Math.ceil((lo+hi)/2);if(frames[m].time<=replay.time)lo=m;else hi=m-1;}const f=frames[lo];
 state.physicsFrame=f;state.strokes=[...f.strokes];state.playing=false;update();grainGroup.visible=!!f.grains_mm;
 if(f.grains_mm){const matrix=new THREE.Matrix4();f.grains_mm.forEach((p,i)=>grainMesh.setMatrixAt(i,matrix.makeTranslation(...p)));grainMesh.instanceMatrix.needsUpdate=true;}
 const error=Math.max(...f.strokes.map((v,i)=>Math.abs(v-f.target_strokes[i])));
 document.getElementById('physics-time').value=replay.time;document.getElementById('physics-readout').innerHTML=`<b>${f.time.toFixed(1)} / ${replay.data.scenario.duration_s} simulated seconds</b><br>Thrust B / S / K: ${f.force_N.map(v=>v.toFixed(1)).join(' / ')} N<br>Largest stroke error: ${error.toFixed(2)} mm${f.grains_mm?'<br>Loose particles: 96':''}`;
 document.getElementById('physics-play').textContent=replay.playing?'Ⅱ Pause replay':'▶ Play replay';needsRender=true;return f;
}
function tickPhysics(dt){if(!replay.active||!replay.playing)return;seekPhysics(replay.time+dt*Number(document.getElementById('physics-speed').value));if(replay.time>=replay.data.scenario.duration_s){replay.playing=false;document.getElementById('physics-play').textContent='▶ Replay again';}}
document.getElementById('physics-play').onclick=async()=>{try{const name=document.getElementById('physics-case').value;if(!replay.active||replay.name!==name)await loadPhysics(name);if(replay.time>=replay.data.scenario.duration_s)seekPhysics(0);replay.playing=!replay.playing;document.getElementById('physics-play').textContent=replay.playing?'Ⅱ Pause replay':'▶ Play replay';}catch(e){document.getElementById('physics-readout').textContent='Could not decode replay: '+e.message;}};
document.getElementById('physics-case').onchange=async e=>{await loadPhysics(e.target.value);};
document.getElementById('physics-time').oninput=e=>{replay.playing=false;seekPhysics(Number(e.target.value));};
window.physicsReplay={load:loadPhysics,seek:seekPhysics,state:()=>({active:replay.active,playing:replay.playing,time:replay.time,name:replay.name,frame:state.physicsFrame})};

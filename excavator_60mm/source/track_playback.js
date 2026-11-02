// Recorded MuJoCo body poses. Millimetres in the viewer; source traces use SI.
const trackData=DATA.track,trackFrames=decode(trackData.frames,Float32Array);
const trackLinks={L:[],R:[]},trackWheels={},trackPinions={},idlerSliding=[],idlerSprings=[],TW=V.track_wheel;
const replayQuaternion=new THREE.Quaternion(),replayNextQuaternion=new THREE.Quaternion();
for(const side of ['L','R']){
  const y=(side==='L'?-1:1)*V.track_centres/2;
  for(let i=0;i<V.track_links_per_side;i++){
    const link=new THREE.Group();groups['vehicle_track_'+side].add(link);trackLinks[side].push(link);
  }
  const centres=[[-V.wheel_centres/2,V.axle_z],[V.wheel_centres/2+V.idler_assembly_offset_mm,V.axle_z],
    ...V.road_roller_x_mm.map(x=>[x,29]),...V.return_roller_x_mm.map(x=>[x,V.return_roller_z_mm])];
  trackWheels[side]=['drive_'+side,'idler_'+side,...V.road_roller_x_mm.map((_,i)=>'roller_'+side+i),
    ...V.return_roller_x_mm.map((_,i)=>'return_'+side+i)].map((name,i)=>{
      const group=groups['vehicle_'+name],centre=new THREE.Vector3(centres[i][0],y,centres[i][1]);
      for(const m of group.children)m.geometry.translate(-centre.x,-centre.y,-centre.z);
      group.position.copy(centre);
      // Painted witness mark makes passive wheel rotation visible.
      const radius=i===0?31:i===1?30:i<5?17.5:V.return_roller_r_mm-.5,start=i===0?24:i===1?19:11.7;
      const mark=new THREE.Mesh(new THREE.BoxGeometry(radius-start,.2,1.1),new THREE.MeshStandardMaterial({color:0xd3a32c,roughness:.8}));
      mark.position.set((radius+start)/2,(side==='L'?-1:1)*(i===0?TW.hub_cap_face_y_mm+.15:V.guide_outer_y_mm+.15),0);
      group.add(mark);return group;
    });
  // Track R5 hub stage: the pinion turns on its own axis, the same way as the hub, hub_ratio times faster.
  const pinion=groups['vehicle_drive_pinion_'+side],pc=new THREE.Vector3(TW.pinion_x_mm,y,TW.pinion_z_mm);
  for(const m of pinion.children)m.geometry.translate(-pc.x,-pc.y,-pc.z);
  pinion.position.copy(pc);trackPinions[side]=pinion;
  idlerSliding.push(...groups['vehicle_idler_slide_'+side].children);
}
for(const m of objects){
  const n=m.userData.name,match=/^(?:shoe_|track_pin_|track_bushing_|pin_clip_)([LR])(\d{2})/.exec(n);
  if(match){
    const [,side,index]=match,i=+index,p=trackData.initial_poses[i],y=(side==='L'?-1:1)*V.track_centres/2;
    m.geometry.translate(-p.origin[0],-y,-p.origin[1]);m.geometry.rotateY(p.angle);m.geometry.computeBoundingBox();
    trackLinks[side][i].add(m);
    if(n==='shoe_'+side+'06'){m.userData.trackMarker=true;m.userData.originalColor=m.material.color.clone();}
  }
  // The spring envelope stretches from its fixed seat to the sliding yoke.
  if(n.startsWith('recoil_spring_envelope_')){m.geometry.translate(-TW.spring_seat_x_mm,0,0);m.geometry.computeBoundingBox();m.position.x=TW.spring_seat_x_mm;idlerSprings.push(m);}
}
function trackSample(time){
  const pos=Math.max(0,Math.min(trackData.count-1,time/trackData.dt)),i=Math.floor(pos);
  return {a:i*trackData.stride,b:Math.min(i+1,trackData.count-1)*trackData.stride,f:pos-i};
}
function updateTrack(time,follow=true){
  state.trackTime=Math.max(0,Math.min(trackData.duration,time));
  const {a,b,f}=trackSample(state.trackTime),value=k=>trackFrames[a+k]*(1-f)+trackFrames[b+k]*f;
  const oldX=vehicleRoot.position.x;vehicleRoot.position.set(value(1),value(2),value(3));
  sun.position.x=-300+vehicleRoot.position.x;sun.target.position.x=vehicleRoot.position.x;
  if(follow){camera.position.x+=vehicleRoot.position.x-oldX;controls.target.x+=vehicleRoot.position.x-oldX;}
  for(const side of ['L','R']){
    const y=(side==='L'?-1:1)*V.track_centres/2;
    trackLinks[side].forEach((link,i)=>{
      const k=16+i*7;link.position.set(value(k),value(k+1)+y,value(k+2));
      replayQuaternion.set(trackFrames[a+k+4],trackFrames[a+k+5],trackFrames[a+k+6],trackFrames[a+k+3]).normalize();
      replayNextQuaternion.set(trackFrames[b+k+4],trackFrames[b+k+5],trackFrames[b+k+6],trackFrames[b+k+3]).normalize();
      link.quaternion.copy(replayQuaternion).slerp(replayNextQuaternion,f);
    });
    trackWheels[side].forEach((wheel,i)=>wheel.rotation.y=value(9+i));
    trackWheels[side][1].position.x=V.wheel_centres/2+value(4);
    trackPinions[side].rotation.y=TW.hub_ratio*value(9);
  }
  for(const m of idlerSliding)m.position.x=value(4)-V.idler_assembly_offset_mm;
  for(const m of idlerSprings)m.scale.x=(TW.spring_length_nominal_mm+value(4))/(TW.spring_length_nominal_mm+V.idler_assembly_offset_mm);
  document.getElementById('trackTime').value=state.trackTime;
  document.getElementById('trackTimeValue').textContent=state.trackTime.toFixed(1)+' / '+trackData.duration.toFixed(0)+' s';
  document.getElementById('trackPhase').textContent=state.trackTime<.5?'Settling':state.trackTime<15?'Forward':state.trackTime<17?'Reversing':state.trackTime<31?'Reverse':state.trackTime<33?'Braking':'Stopped';
  document.getElementById('trackSpeed').textContent=(value(5)*60/(2*Math.PI)).toFixed(1)+' rpm';
  document.getElementById('trackTravel').textContent=value(1).toFixed(0)+' mm';
  document.getElementById('trackTakeup').textContent=value(4).toFixed(2)+' mm';
  needsRender=true;
}
function pauseTracks(){state.trackPlaying=false;document.getElementById('trackPlay').textContent='Play track test';}
function resetTracks(){pauseTracks();updateTrack(0);}
document.getElementById('trackPlay').onclick=()=>{
  if(state.trackPlaying){pauseTracks();return;}
  if(state.trackTime>=trackData.duration)updateTrack(0);
  stop();state.trackPlaying=true;document.getElementById('trackPlay').textContent='Pause tracks';
};
document.getElementById('trackReset').onclick=resetTracks;
document.getElementById('trackTime').max=trackData.duration;
document.getElementById('trackTime').oninput=e=>{pauseTracks();updateTrack(+e.target.value);};
document.getElementById('trackRate').onchange=e=>state.trackRate=+e.target.value;
document.getElementById('trackMarker').onchange=e=>{
  for(const m of objects.filter(o=>o.userData.trackMarker)){
    if(e.target.checked)m.material.color.set('#d39c29').convertSRGBToLinear();else m.material.color.copy(m.userData.originalColor);
  }
  needsRender=true;
};
document.getElementById('trackMarker').dispatchEvent(new Event('change'));
document.addEventListener('visibilitychange',()=>{if(document.hidden)pauseTracks();});
window.setTrackTime=time=>{pauseTracks();updateTrack(Number.isFinite(time)?time:0);};
window.trackState=()=>{
  scene.updateMatrixWorld(true);const {a,b,f}=trackSample(state.trackTime);
  const links=Object.fromEntries(['L','R'].map(side=>[side,trackLinks[side].map(link=>({
    front:link.localToWorld(new THREE.Vector3(10,0,0)).toArray(),
    rear:link.localToWorld(new THREE.Vector3(-10,0,0)).toArray(),
    quaternion:link.quaternion.toArray(),position:link.getWorldPosition(new THREE.Vector3()).toArray()
  }))]));
  return {time:state.trackTime,playing:state.trackPlaying,rate:state.trackRate,links,
    sourceTraceSha256:trackData.source_trace_sha256,
    frame:vehicleRoot.position.toArray(),wheelAngles:trackWheels.R.map(w=>w.rotation.y),
    idlerX:trackWheels.R[1].position.x,carriageX:idlerSliding.find(m=>m.userData.name==='TW07_idler_yoke_R').position.x+V.idler_assembly_offset_mm,
    pinionAngles:['L','R'].map(side=>trackPinions[side].rotation.y),
    springFrontX:idlerSprings.map(m=>m.position.x+m.geometry.boundingBox.max.x*m.scale.x),
    bushingCentres:objects.filter(m=>/^track_bushing_/.test(m.userData.name)).map(m=>({name:m.userData.name,centre:m.localToWorld(m.geometry.boundingBox.getCenter(new THREE.Vector3())).toArray()})),
    pinCentres:objects.filter(m=>/^track_pin_/.test(m.userData.name)).map(m=>({name:m.userData.name,centre:m.localToWorld(m.geometry.boundingBox.getCenter(new THREE.Vector3())).toArray()})),
    sample:[a/trackData.stride,b/trackData.stride,f],duration:trackData.duration};
};

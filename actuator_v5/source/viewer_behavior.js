(() => {
  'use strict';
  // Model axes: z = actuator axis, x = clevis-pin axis, -y = service side (sensor channel).
  // Viewer axes: X = actuator axis, Y (up) = pin axis, Z = model y. Pure rotation, no mirroring.
  const P = JSON.parse(document.getElementById('parameter-data').textContent);
  const items = JSON.parse(document.getElementById('geometry-data').textContent);
  const $ = id => document.getElementById(id);
  const stage = $('stage'), canvas = stage.querySelector('canvas');

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({canvas, antialias: true, preserveDrawingBuffer: true});
  } catch (e) {
    $('error').style.display = 'grid';
    return;
  }
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputEncoding = THREE.sRGBEncoding;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.82;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#f3f3ef');
  scene.environment = studioEnvironment();
  const model = new THREE.Group();
  scene.add(model);
  const CENTRE = (P.rear_eye_z + P.front_eye_z_retracted) / 2 + P.stroke_mm / 4;
  const STROKE = P.stroke_mm, PITCH = P.screw_pitch_mm;
  const OPERATE = P.hall_operate_mm || 3.85, RELEASE = P.hall_release_mm || 4.25;
  const SPEED = 250 * PITCH / 60;          // animation: 250 rpm at the leadscrew

  const camera = new THREE.OrthographicCamera(-100, 100, 60, -60, 0.1, 4000);
  const controls = new THREE.OrbitControls(camera, canvas);
  controls.minZoom = 0.3;
  controls.maxZoom = 10;

  scene.add(new THREE.HemisphereLight(0xffffff, 0x7d8582, 0.45));
  const key = new THREE.DirectionalLight(0xfff5e6, 1.25);
  key.position.set(-60, 220, 140);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  Object.assign(key.shadow.camera, {left: -150, right: 150, top: 90, bottom: -90, near: 1, far: 700});
  key.shadow.bias = -0.0003;
  scene.add(key);
  const fill = new THREE.DirectionalLight(0xe4eeff, 0.45);
  fill.position.set(140, 50, -180);
  scene.add(fill);
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(4000, 4000), new THREE.ShadowMaterial({opacity: 0.13}));
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -11.6;
  ground.receiveShadow = true;
  scene.add(ground);

  function studioEnvironment() {
    // Soft studio gradient with two softboxes, used only for reflections on metal and paint.
    const c = document.createElement('canvas');
    c.width = 512; c.height = 256;
    const g = c.getContext('2d');
    const sky = g.createLinearGradient(0, 0, 0, 256);
    sky.addColorStop(0, '#ffffff'); sky.addColorStop(0.45, '#e3e6e8');
    sky.addColorStop(0.52, '#8f989d'); sky.addColorStop(1, '#30363a');
    g.fillStyle = sky; g.fillRect(0, 0, 512, 256);
    g.fillStyle = '#ffffff';
    g.fillRect(70, 38, 120, 44); g.fillRect(330, 58, 96, 30);
    const tex = new THREE.CanvasTexture(c);
    tex.mapping = THREE.EquirectangularReflectionMapping;
    tex.encoding = THREE.sRGBEncoding;
    const pm = new THREE.PMREMGenerator(renderer);
    const env = pm.fromEquirectangular(tex).texture;
    tex.dispose(); pm.dispose();
    return env;
  }

  function decode(b64, Type) {
    const bin = atob(b64), bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new Type(bytes.buffer);
  }

  const LOOK = {paint: [0.4, 0.0, 0.25], plastic: [0.5, 0.0, 0.45], chrome: [0.2, 0.95, 1.3], rubber: [0.85, 0.0, 0.3],
                steel: [0.32, 0.85, 1.0], brass: [0.33, 0.85, 1.0], tin: [0.35, 0.8, 1.0], black: [0.55, 0.1, 0.5],
                ceramic: [0.6, 0.0, 0.4], blackmetal: [0.4, 0.6, 0.8], wire: [0.45, 0.0, 0.5]};
  const meshes = new Map(), halves = new Set();
  items.forEach(item => {
    const src = decode(item.v, Float32Array), pos = new Float32Array(src.length);
    for (let i = 0; i < src.length; i += 3) {
      pos[i] = src[i + 2] - CENTRE; pos[i + 1] = src[i]; pos[i + 2] = src[i + 1];
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geo.setIndex(new THREE.BufferAttribute(decode(item.t, item.wide ? Uint32Array : Uint16Array), 1));
    geo.computeVertexNormals();
    const [rough, metal, env] = LOOK[item.material] || LOOK.plastic;
    const mat = new THREE.MeshStandardMaterial({color: new THREE.Color(...item.color).convertSRGBToLinear(),
      roughness: rough, metalness: metal, envMapIntensity: env, side: THREE.DoubleSide});
    const mesh = new THREE.Mesh(geo, mat);
    mesh.name = item.name;
    mesh.userData = item;
    mesh.castShadow = true;
    model.add(mesh);
    meshes.set(item.name, mesh);
    if (item.name.endsWith('__half')) halves.add(item.name.slice(0, -6));
  });

  const VIEWS = {
    exterior: {dir: [-0.32, 0.5, 0.8], target: [-6, 0, 0], zoom: 1.0,
               label: 'EXTERIOR<br>Ø21 barrel · Ø23 caps · Ø9 rod · Ø14 clevis eyes'},
    section: {dir: [0, 0.95, 0.3], target: [-4, 0, -1], zoom: 1.15,
              label: 'SECTION ON THE PIN PLANE<br>motor · leadscrew · brass nut in the carrier · magnet'},
    wiring: {dir: [-0.25, 0.42, -0.87], target: [-8, -2, -6], zoom: 1.12,
             label: 'WIRING<br>cover strip removed, rear cap and barrel see-through'},
    core: {dir: [-0.45, 0.55, 0.7], target: [-CENTRE + 6, 0, 0], zoom: 2.6,
           label: 'CORE PART, UNCHANGED<br>N20 gearmotor: 9 mm gearbox · 15 mm can · M3 leadscrew from the gearbox'},
  };
  let travel = Math.round(STROKE / 2), mode = 'exterior', direction = 0, jammed = false, fault = false;
  let lowRet = false, lowExt = false, runMs = 0, highMs = 0, lastTime = 0, raf = null, blocked = '';

  function magnetZ() { return P.magnet_end_positions_z[0] + travel; }
  function hallStates(hysteresis) {
    // DRV5033 output is LOW while the magnet is within the operate distance; it releases further out.
    const dRet = Math.abs(magnetZ() - P.sensor_centres_z[0]), dExt = Math.abs(magnetZ() - P.sensor_centres_z[1]);
    lowRet = hysteresis ? (lowRet ? dRet <= RELEASE : dRet <= OPERATE) : dRet <= OPERATE;
    lowExt = hysteresis ? (lowExt ? dExt <= RELEASE : dExt <= OPERATE) : dExt <= OPERATE;
  }

  function aim(view) {
    const v = VIEWS[view], d = new THREE.Vector3(...v.dir).normalize();
    controls.target.set(...v.target);
    camera.position.copy(controls.target).addScaledVector(d, 900);
    camera.zoom = v.zoom;
    camera.updateProjectionMatrix();
    controls.update();
  }

  function render() { renderer.render(scene, camera); }

  function update() {
    const theta = -travel / PITCH * 2 * Math.PI;
    meshes.forEach((mesh, name) => {
      const u = mesh.userData, half = name.endsWith('__half'), base = half ? name.slice(0, -6) : name;
      mesh.position.set(u.moving ? travel : 0, 0, 0);
      mesh.rotation.set(u.rotating ? theta : 0, 0, 0);
      let visible = true, ghost = false;
      if (half) visible = mode === 'section';
      else if (mode === 'section' && halves.has(base)) visible = false;
      if ((mode === 'section' || mode === 'wiring') && base.startsWith('06_')) visible = false;
      if (mode === 'wiring' && /^(01_|02_|07_)/.test(base)) ghost = true;
      if (mode === 'wiring' && base === 'cable_jacket') ghost = true;
      if (mode === 'core') visible = base.startsWith('motor_');
      mesh.visible = visible;
      mesh.material.transparent = ghost;
      mesh.material.opacity = ghost ? 0.16 : 1;
      mesh.material.depthWrite = !ghost;
      mesh.renderOrder = ghost ? 2 : 0;
      mesh.castShadow = !ghost;
    });
    ground.position.y = mode === 'core' ? -6.1 : -11.6;
    $('travel').value = travel;
    $('travel-value').textContent = travel.toFixed(1);
    $('length-value').textContent = (P.eye_centres_closed_mm + travel).toFixed(1);
    $('led-ret').classList.toggle('low', lowRet);
    $('led-ext').classList.toggle('low', lowExt);
    $('sig-ret').textContent = `U1 retract end · ALLOW_RET ${lowRet ? 'LOW' : 'HIGH'}`;
    $('sig-ext').textContent = `U2 extend end · ALLOW_EXT ${lowExt ? 'LOW' : 'HIGH'}`;
    $('extend').disabled = fault || lowExt;
    $('retract').disabled = fault || lowRet;
    $('fault-reset').disabled = !fault && !jammed;
    $('jam').disabled = jammed;
    $('status').textContent = fault ? 'Overcurrent latched by the firmware. Clear the jam, then reset.'
      : jammed && direction ? 'Jammed: the driver limits the current and the firmware counts 150 ms of overcurrent…'
      : jammed ? 'Jam armed: start a move to see the current trip.'
      : direction ? `Moving ${direction > 0 ? 'out' : 'in'}; the other end stop is clear.`
      : blocked ? blocked
      : lowRet ? 'At the retract end: U1 holds ALLOW_RET LOW, so U3 blocks retract. Extend is allowed.'
      : lowExt ? 'At the extend end: U2 holds ALLOW_EXT LOW, so U3 blocks extend. Retract is allowed.'
      : 'Stopped between the ends. Both directions are allowed.';
    $('view-label').innerHTML = VIEWS[mode].label;
    render();
  }

  function stop() {
    direction = 0;
    if (raf) cancelAnimationFrame(raf);
    raf = null;
    lastTime = 0;
    update();
  }

  function setTravel(v) {
    stop();
    blocked = '';
    travel = THREE.MathUtils.clamp(Number(v), 0, STROKE);
    hallStates(false);
    update();
  }

  function command(dir) {
    if (fault || (dir > 0 && lowExt) || (dir < 0 && lowRet)) return;
    blocked = '';
    direction = dir;
    lastTime = 0; runMs = 0; highMs = 0;
    if (raf) cancelAnimationFrame(raf);
    raf = requestAnimationFrame(tick);
    update();
  }

  function tick(t) {
    if (!direction) return;
    const dt = lastTime ? Math.min((t - lastTime) / 1000, 0.1) : 0;
    lastTime = t;
    step(dt);
    update();
    if (direction) raf = requestAnimationFrame(tick);
  }

  function step(dt) {
    runMs += dt * 1000;
    if (jammed) {
      if (runMs >= 100) highMs += dt * 1000;          // 100 ms start-up blanking, then 150 ms over the limit
      if (highMs >= 150) { fault = true; direction = 0; }
    } else {
      travel = THREE.MathUtils.clamp(travel + direction * SPEED * dt, -P.overtravel_retract_mm, STROKE + P.overtravel_extend_mm);
      hallStates(true);
      if (direction > 0 && lowExt) { direction = 0; blocked = `U2 switched ALLOW_EXT LOW at ${travel.toFixed(2)} mm: extend cut off in hardware.`; }
      if (direction < 0 && lowRet) { direction = 0; blocked = `U1 switched ALLOW_RET LOW at ${travel.toFixed(2)} mm: retract cut off in hardware.`; }
    }
  }

  function simulate(dir, seconds) {
    // Same logic as the animation, in fixed 10 ms steps (used for automated checks).
    command(dir);
    if (raf) cancelAnimationFrame(raf);
    raf = null;
    for (let t = 0; t < seconds && direction; t += 0.01) step(0.01);
    update();
    return window.actuator.getState();
  }

  function setMode(m) {
    mode = m;
    document.querySelectorAll('[data-mode]').forEach(b => {
      b.classList.toggle('active', b.dataset.mode === m);
      b.setAttribute('aria-pressed', String(b.dataset.mode === m));
    });
    aim(m);
    update();
  }

  function resize() {
    const w = stage.clientWidth, h = stage.clientHeight, a = w / h, half = Math.max(30, 100 / a);
    camera.left = -half * a; camera.right = half * a; camera.top = half; camera.bottom = -half;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h, false);
    render();
  }

  $('spec-stroke').textContent = `${STROKE} mm`;
  $('spec-pins').textContent = `${P.eye_centres_closed_mm}–${P.eye_centres_open_mm} mm`;
  $('spec-od').textContent = `Ø${P.barrel_od_mm} / ${P.cap_od_mm} / ${P.rod_d_mm}`;
  $('travel').max = STROKE;
  $('range-max').textContent = `extended · ${STROKE} mm`;
  $('fine').textContent = `Animation: leadscrew at 250 rpm = ${SPEED.toFixed(2)} mm/s (M3 × ${PITCH} mm). End stops use the magnet model: ` +
    `output LOW within ${OPERATE} mm of the sensor, HIGH again beyond ${RELEASE} mm. Hall sensors at z ${P.sensor_centres_z.map(z => z.toFixed(1)).join(' / ')} mm.`;
  $('travel').addEventListener('input', e => setTravel(e.target.value));
  $('extend').onclick = () => command(1);
  $('retract').onclick = () => command(-1);
  $('stop').onclick = () => { blocked = ''; stop(); };
  $('jam').onclick = () => { jammed = true; update(); };
  $('fault-reset').onclick = () => { stop(); fault = false; jammed = false; highMs = 0; update(); };
  $('reset').onclick = () => { aim(mode); render(); };
  document.querySelectorAll('[data-mode]').forEach(b => { b.onclick = () => setMode(b.dataset.mode); });
  controls.addEventListener('change', render);
  new ResizeObserver(resize).observe(stage);
  document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); });

  hallStates(false);
  aim(mode);
  resize();
  update();
  window.actuator = {setTravel, setMode, command, stop, render, simulate,
    setJammed: v => { jammed = v; update(); },
    getState: () => ({travel, mode, direction, jammed, fault, lowRet, lowExt,
                      pinDistance: P.eye_centres_closed_mm + travel})};
  window.viewerReady = true;
})();

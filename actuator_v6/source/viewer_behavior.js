(() => {
  'use strict';
  // Model axes: z = actuator axis, y = clevis-pin axis, +x = board side.
  // Viewer axes: X = model z, Y (up) = model y, Z = -model x. A rotation, no mirroring.
  const $ = id => document.getElementById(id);
  const GEO = JSON.parse($('geometry-data').textContent);
  const SCENES = JSON.parse($('scene-data').textContent);
  const PARAMS = JSON.parse($('parameter-data').textContent);
  const CIR = JSON.parse($('circuit-data').textContent);
  const ASM = JSON.parse($('assembly-data').textContent);   // assembly plan and print data per length
  const stage = $('stage'), canvas = stage.querySelector('canvas'), labelsEl = $('labels');

  const RECORD = /\brecord\b/.test(location.hash);    // video frames: no MSAA or shadows, supersampled instead
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({canvas, antialias: !RECORD, preserveDrawingBuffer: true});
  } catch (e) {
    $('error').style.display = 'grid';
    return;
  }
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputEncoding = THREE.sRGBEncoding;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.85;
  renderer.shadowMap.enabled = !RECORD;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#f3f3ef');
  scene.environment = studioEnvironment();
  const model = new THREE.Group();
  scene.add(model);
  const camera = new THREE.OrthographicCamera(-100, 100, 60, -60, 0.1, 4000);
  const controls = new THREE.OrbitControls(camera, canvas);
  controls.minZoom = 0.3;
  controls.maxZoom = 16;

  scene.add(new THREE.HemisphereLight(0xffffff, 0x7d8582, 0.45));
  const key = new THREE.DirectionalLight(0xfff5e6, 1.2);
  key.position.set(-60, 220, 140);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  Object.assign(key.shadow.camera, {left: -200, right: 200, top: 110, bottom: -110, near: 1, far: 800});
  key.shadow.bias = -0.0003;
  scene.add(key);
  const fill = new THREE.DirectionalLight(0xe4eeff, 0.5);
  fill.position.set(140, 50, 180);
  scene.add(fill);
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(4000, 4000), new THREE.ShadowMaterial({opacity: 0.13}));
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);

  function studioEnvironment() {
    // Soft studio gradient with two softboxes, used only for reflections.
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
  const geoCache = new Map();
  function geometry(id) {
    if (geoCache.has(id)) return geoCache.get(id);
    const g = GEO[id], q = decode(g.v, Uint16Array), pos = new Float32Array(q.length), o = g.o, s = g.s;
    for (let i = 0; i < q.length; i += 3) {             // dequantise and turn into viewer axes
      pos[i] = o[2] + q[i + 2] * s[2]; pos[i + 1] = o[1] + q[i + 1] * s[1]; pos[i + 2] = -(o[0] + q[i] * s[0]);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geo.setIndex(new THREE.BufferAttribute(decode(g.t, g.wide ? Uint32Array : Uint16Array), 1));
    geo.computeVertexNormals();
    geo.computeBoundingBox();
    geoCache.set(id, geo);
    return geo;
  }

  const LOOK = {paint: [0.42, 0.0, 0.3], plastic: [0.5, 0.0, 0.45], silver: [0.34, 0.55, 1.0], rubber: [0.85, 0.0, 0.3],
                steel: [0.32, 0.85, 1.0], brass: [0.33, 0.85, 1.0], tin: [0.3, 0.85, 1.0], black: [0.55, 0.1, 0.5],
                ceramic: [0.6, 0.0, 0.4], pcb: [0.42, 0.0, 0.7], wire: [0.45, 0.0, 0.5]};
  const SEL = new THREE.Color('#ff8f00'), FLOW = new THREE.Color('#ff3b1f');
  const base = n => n.replace(/__(xhalf|half|cut)$/, '');
  const matches = (entry, name) => base(name) === entry || (entry.endsWith('_') && base(name).startsWith(entry));
  const mv = (x, y, z) => new THREE.Vector3(z - CENTRE, y, -x);            // model point -> viewer
  const mdir = (x, y, z) => new THREE.Vector3(z, y, -x);                    // model direction -> viewer
  const clamp01 = x => Math.min(1, Math.max(0, x));
  const ease = x => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);

  // ---- state ---------------------------------------------------------------------------------
  let V = Object.keys(SCENES)[0], P = PARAMS[V], CENTRE = 0, mode = 'exterior', selected = null;
  const meshes = new Map(), labels = new Map();
  const SIMD = CIR.sim;
  const OPERATE = () => P.hall_operate_mm, RELEASE = () => P.hall_release_mm;
  const S = {travel: 0, drive: 0, jam: false, tripped: false, stallS: 0, offS: 0, u1: null, u2: null,
             current: 0, running: false};
  let raf = null, lastT = 0;
  let speedBeforeGears = null;
  const placed = new Map();          // mesh name -> 'show' | 'ghost' | 'hide' in the printed and assembly modes

  function buildVariant(v) {
    meshes.forEach(m => { model.remove(m); m.material.dispose(); });
    meshes.clear();
    labels.forEach(l => l.remove());
    labels.clear();
    asmPause();
    V = v; P = PARAMS[v];
    CENTRE = (P.rear_eye_z + P.eye_front_z) / 2 + P.stroke_mm / 4;
    SCENES[v].forEach(item => {
      const [rough, metal, env] = LOOK[item.material] || LOOK.plastic;
      const mat = new THREE.MeshStandardMaterial({color: new THREE.Color(...item.color).convertSRGBToLinear(),
        roughness: rough, metalness: metal, envMapIntensity: env, side: THREE.DoubleSide});
      const mesh = new THREE.Mesh(geometry(item.g), mat);
      mesh.name = item.name;
      mesh.userData = item;
      mesh.castShadow = true;
      model.add(mesh);
      meshes.set(item.name, mesh);
      if (item.kind === 'board' && item.board_kind === 'part') {
        const el = document.createElement('div');
        el.className = 'plabel';
        el.textContent = item.ref;
        el.onclick = () => select({type: 'part', id: item.ref});
        labelsEl.appendChild(el);
        labels.set(item.ref, el);
      }
    });
    document.querySelectorAll('[data-variant]').forEach(b => {
      b.classList.toggle('active', b.dataset.variant === v);
      b.setAttribute('aria-pressed', String(b.dataset.variant === v));
    });
    const m = P.mechanics;
    $('spec-stroke').textContent = `${P.stroke_mm} mm`;
    $('spec-pins').textContent = `${P.pin_centres_closed}–${P.pin_centres_open} mm`;
    $('spec-body').textContent = `${P.body_section[0]} × ${P.body_section[1]} mm`;
    $('spec-speed').textContent = `${m.speed_simulated_mm_s.toFixed(2)}–${m.speed_no_load_mm_s.toFixed(2)} mm/s`;
    $('spec-force').textContent = `≈${m.thrust_at_fuse_hold_N} N cont.`;
    $('spread').textContent = `${P.stop_spread_mm[0]} / +${P.stop_spread_mm[1]} mm`;
    const t = $('travel');
    t.min = -P.overtravel_mm; t.max = P.stroke_mm + P.overtravel_mm;
    $('range-max').textContent = `extended · ${P.stroke_mm} mm`;
    Object.assign(S, {drive: 0, jam: false, tripped: false, stallS: 0, offS: 0, current: 0, running: false});
    S.travel = Math.round(P.stroke_mm / 2);
    hallUpdate(true);
    buildPrinted();
    buildAssembly(v);
    resize();
    aim(mode);
    update();
  }

  // ---- display modes -------------------------------------------------------------------------
  function visibility(it) {
    const n = it.name, b = base(n);
    if (it.kind === 'tool' || it.kind === 'xsection') return 'hide';     // assembly animation only
    if (mode === 'gears') {
      if (it.kind !== 'hardware' || !n.startsWith('motor_')) return 'hide';
      if (it.geartrain_rotation) return 'show';
      return /gearbox_frame|bushing/.test(n) ? 'ghost' : 'hide';
    }
    if (mode === 'core') return b.startsWith('motor_') && it.kind === 'hardware' ? 'show' : 'hide';
    if (it.kind === 'section') return mode === 'section' ? 'show' : 'hide';
    if (it.kind === 'cutaway') return mode === 'board' ? 'show' : 'hide';
    if (it.kind === 'printed') return mode === 'exterior' || (mode === 'internal' && it.moving) ? 'show' : 'hide';
    if (mode === 'board') {
      if (/^(motor_leadscrew|M3_brass_nut|M2x10_rod_eye|M1\.6)/.test(n)) return 'hide';
      if (n.startsWith('motor_')) return 'ghost';
    }
    if (mode === 'exterior' && it.kind === 'board') return 'hide';      // inside the closed body
    return 'show';
  }

  function views() {
    const zb = (P.pcb_z[0] + P.pcb_z[1]) / 2 - CENTRE;
    const fit = (camera.right - camera.left);
    return {
      exterior: {dir: [-0.34, 0.5, 0.8], target: [0, 0, 0], zoom: 1.0,
                 label: `EXTERIOR · V6-${V}<br>${P.body_section[0]} × ${P.body_section[1]} mm body · Ø${P.rod_d_mm} rod · Ø${P.pin_d_mm} pins`},
      section: {dir: [0.0, 1.0, 0.14], target: [0, 0, 0], zoom: 1.05,
                label: `CUTAWAY ON THE PIN PLANE<br>motor on its wall · leadscrew · brass nut · magnet · ${P.partition_thickness_mm} mm partition before the board`},
      internal: {dir: [-0.3, 0.62, 0.72], target: [0, 0, 0], zoom: 1.0,
                 label: 'INTERNALS<br>housing and partition hidden · rod, motor, board and wires in place'},
      board: {dir: [0.0, 0.2, 1.0], target: [zb - 2.5, 0, -8], zoom: fit / (P.pcb_length * 1.42),
              label: 'CIRCUIT BOARD, SEEN FROM THE BORE<br>body and partition cut away · parts face the magnet'},
      core: {dir: [-0.45, 0.55, 0.7], target: [-12 - CENTRE, 0, 0], zoom: fit / 55,
             label: 'CORE PART, UNCHANGED<br>N20 gearmotor: 9 mm gearbox · 15 mm can · M3 leadscrew from the gearbox'},
      gears: {dir: [0.7, 0.55, 0.65], target: [-4.8 - CENTRE, 1.1, 0], zoom: fit / 22,
              label: 'MESHED MOTOR GEARS · 27:1<br>three 18:54 stages · illustrative internal tooth counts · drag to orbit'},
      printed: {dir: [-0.12, 0.42, 0.9], target: [0, bedView.height * 0.36, 0], zoom: fit / bedView.span,
                label: `PRINTED PARTS · V6-${V}<br>the six parts as they sit on the print bed (the STL orientation) · click one for its settings`},
      assembly: {label: asmLabel()},
    };
  }

  function aim(m) {
    if (m === 'assembly') { asm.freeStep = -1; asmCamera(true); return; }
    const v = views()[m], d = new THREE.Vector3(...v.dir).normalize();
    controls.target.set(...v.target);
    camera.position.copy(controls.target).addScaledVector(d, 900);
    camera.zoom = v.zoom;
    camera.updateProjectionMatrix();
    controls.update();
  }

  function setMode(m) {
    if (m !== 'assembly') asmPause();
    if (m === 'assembly' || m === 'printed') drive(0);
    if (m === 'gears' && mode !== 'gears') {
      speedBeforeGears = $('speed').value;
      $('speed').value = '0.02';
    } else if (mode === 'gears' && m !== 'gears' && speedBeforeGears !== null) {
      $('speed').value = speedBeforeGears;
      speedBeforeGears = null;
    }
    mode = m;
    document.querySelectorAll('[data-mode]').forEach(b => {
      b.classList.toggle('active', b.dataset.mode === m);
      b.setAttribute('aria-pressed', String(b.dataset.mode === m));
    });
    document.body.classList.toggle('asm-on', m === 'assembly');
    document.body.classList.toggle('print-on', m === 'printed');
    resize();
    aim(m);
    update();
  }

  // ---- printed parts: laid out on a print bed in their STL orientation -----------------------
  const printLayout = new Map(), partLabels = new Map(), bedView = {span: 160, height: 60};
  const bed = new THREE.Group();
  scene.add(bed);
  function buildPrinted() {
    printLayout.clear();
    partLabels.forEach(l => l.remove());
    partLabels.clear();
    bed.children.slice().forEach(c => { bed.remove(c); c.geometry.dispose(); c.material.dispose(); });
    // viewer up = the print direction; 02 and 03 print upside down (build_v6.FLIP)
    const up = new THREE.Matrix4().set(0, 0, -1, 0, 1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 0, 1);
    const flip = new THREE.Matrix4().set(0, 0, -1, 0, -1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1);
    const parts = [...meshes.values()].filter(m => m.userData.kind === 'printed').sort((a, b) => a.name.localeCompare(b.name));
    const boxes = parts.map(m => {
      const r = /^0[23]_/.test(m.name) ? flip : up;
      return {m, r, b: m.geometry.boundingBox.clone().applyMatrix4(r)};
    });
    const gap = 9, width = boxes.reduce((w, x) => w + x.b.max.x - x.b.min.x, 0) + gap * (boxes.length - 1);
    let x = -width / 2, height = 0;
    boxes.forEach(({m, r, b}) => {
      const w = b.max.x - b.min.x, cx = x + w / 2, h = b.max.y - b.min.y;
      const pos = new THREE.Vector3(cx - (b.min.x + b.max.x) / 2, -b.min.y, -(b.min.z + b.max.z) / 2);
      printLayout.set(m.name, {matrix: new THREE.Matrix4().makeTranslation(pos.x, pos.y, pos.z).multiply(r),
                               anchor: new THREE.Vector3(cx, h + 5, 0)});
      height = Math.max(height, h);
      x += w + gap;
      const info = (ASM.print[V] || {})[m.name], el = document.createElement('div');
      el.className = 'plabel printed';
      el.innerHTML = `${esc(m.name.replace(/_/g, ' '))}${info ? `<small>${info.mass_solid_g.toFixed(1)} g</small>` : ''}`;
      el.onclick = () => select({type: 'mesh', id: m.name});
      labelsEl.appendChild(el);
      partLabels.set(m.name, el);
    });
    const size = Math.ceil((width + 40) / 10) * 10;
    const plate = new THREE.Mesh(new THREE.BoxGeometry(size, 2, size * 0.55),
      new THREE.MeshStandardMaterial({color: 0xd8dbd6, roughness: 0.75, metalness: 0.0}));
    plate.position.y = -1;
    plate.receiveShadow = true;
    const grid = new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({color: 0xb4bab5}));
    const g = [];
    for (let a = -size / 2; a <= size / 2 + 1e-6; a += 10) g.push(a, 0.02, -size * 0.275, a, 0.02, size * 0.275);
    for (let b = -size * 0.275; b <= size * 0.275 + 1e-6; b += 10) g.push(-size / 2, 0.02, b, size / 2, 0.02, b);
    grid.geometry.setAttribute('position', new THREE.Float32BufferAttribute(g, 3));
    bed.add(plate, grid);
    bed.visible = false;
    bedView.span = size + 30;
    bedView.height = height;
  }

  function printPlace() {
    meshes.forEach((mesh, name) => {
      const lay = printLayout.get(name);
      if (lay) { mesh.matrix.copy(lay.matrix); mesh.matrixAutoUpdate = false; mesh.matrixWorldNeedsUpdate = true; }
      placed.set(name, lay ? 'show' : 'hide');
    });
  }

  // ---- assembly animation: assembly.py's plan, one op list per part --------------------------
  class Tube {                       // a wire or sleeve that follows a changing centre line
    constructor(n, radius, material, radial) {
      Object.assign(this, {n, r: radius, k: radial, pts: new Float32Array(n * 3)});
      this.pos = new Float32Array(n * radial * 3);
      this.nrm = new Float32Array(n * radial * 3);
      const idx = [];
      for (let i = 0; i < n - 1; i++) for (let j = 0; j < radial; j++) {
        const a = i * radial + j, b = i * radial + (j + 1) % radial;
        idx.push(a, a + radial, b, b, a + radial, b + radial);
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.BufferAttribute(this.pos, 3));
      g.setAttribute('normal', new THREE.BufferAttribute(this.nrm, 3));
      g.setIndex(idx);
      this.mesh = new THREE.Mesh(g, material);
      this.mesh.castShadow = true;
      this.mesh.frustumCulled = false;
      this.mesh.visible = false;
    }
    update() {                       // rings around this.pts (model coordinates), parallel-transported
      const {n, k, r, pts, pos, nrm} = this, T = new THREE.Vector3(), N = new THREE.Vector3(),
        B = new THREE.Vector3(), prev = new THREE.Vector3(1, 0, 0), v = i => [pts[3 * i + 2] - CENTRE, pts[3 * i + 1], -pts[3 * i]];
      for (let i = 0; i < n; i++) {
        const a = v(Math.max(0, i - 1)), b = v(Math.min(n - 1, i + 1)), c = v(i);
        T.set(b[0] - a[0], b[1] - a[1], b[2] - a[2]);
        if (T.lengthSq() < 1e-12) T.copy(prev); else T.normalize();
        if (i === 0) N.set(Math.abs(T.y) > 0.9 ? 1 : 0, Math.abs(T.y) > 0.9 ? 0 : 1, 0);
        N.addScaledVector(T, -N.dot(T));
        if (N.lengthSq() < 1e-10) N.set(0, 0, 1).addScaledVector(T, -T.z);
        N.normalize();
        B.crossVectors(T, N);
        prev.copy(T);
        for (let j = 0; j < k; j++) {
          const ang = j / k * Math.PI * 2, cs = Math.cos(ang), sn = Math.sin(ang), o = (i * k + j) * 3;
          const nx = cs * N.x + sn * B.x, ny = cs * N.y + sn * B.y, nz = cs * N.z + sn * B.z;
          nrm[o] = nx; nrm[o + 1] = ny; nrm[o + 2] = nz;
          pos[o] = c[0] + r * nx; pos[o + 1] = c[1] + r * ny; pos[o + 2] = c[2] + r * nz;
        }
      }
      this.mesh.geometry.attributes.position.needsUpdate = true;
      this.mesh.geometry.attributes.normal.needsUpdate = true;
    }
  }
  function sampleInto(src, n, fi, dst, i) {
    const f = Math.min(Math.max(fi, 0), n - 1), a = Math.min(Math.floor(f), n - 2), w = f - a;
    for (let c = 0; c < 3; c++) dst[3 * i + c] = src[3 * a + c] * (1 - w) + src[3 * (a + 1) + c] * w;
  }

  const asm = {t: 0, playing: false, speed: 1, last: 0, raf: null, freeStep: -1};
  const tubes = {}, knots = {};
  let PLAN = null;
  function buildAssembly(v) {
    Object.values(tubes).forEach(w => { model.remove(w.tube.mesh); w.tube.mesh.geometry.dispose(); w.tube.mesh.material.dispose(); });
    Object.values(knots).forEach(k => { model.remove(k.mesh); k.mesh.geometry.dispose(); });
    Object.keys(tubes).forEach(k => delete tubes[k]);
    Object.keys(knots).forEach(k => delete knots[k]);
    const src = ASM.plans[v];
    let t = 0;
    const steps = src.steps.map(s => { const o = Object.assign({}, s, {start: t}); t += s.dur; return o; });
    const plan = {steps, total: t, times: src.screw_times, items: new Map(), tools: {}, drives: []};
    meshes.forEach((m, name) => {
      const it = m.userData;
      if (it.kind !== 'wire' && name !== 'cable_sleeve') return;
      const raw = it.kind === 'wire' ? it.paths : {final: it.path}, paths = {};
      Object.keys(raw).forEach(k => { paths[k] = new Float32Array(raw[k]); });
      const f = paths.final, n = f.length / 3;
      let len = 0;
      for (let i = 1; i < n; i++) len += Math.hypot(f[3 * i] - f[3 * i - 3], f[3 * i + 1] - f[3 * i - 2], f[3 * i + 2] - f[3 * i - 1]);
      const tube = new Tube(n, it.diameter_mm / 2, m.material.clone(), it.kind === 'wire' ? 8 : 14);
      model.add(tube.mesh);
      tubes[name] = {tube, n, len, step: len / (n - 1), paths, ops: []};
      if (it.knot_u) {
        const k = new THREE.Mesh(new THREE.SphereGeometry(0.66, 14, 10), tube.mesh.material);
        k.castShadow = true;
        k.visible = false;
        model.add(k);
        knots[name] = {mesh: k, u: it.knot_u, t0: Infinity};
      }
    });
    const add = (entries, g) => meshes.forEach((m, name) => {
      if (!entries.some(e => matches(e, name))) return;
      if (!plan.items.has(name)) plan.items.set(name, []);
      plan.items.get(name).push(g);
    });
    steps.forEach((s, k) => s.ops.forEach(o => {
      const g = Object.assign({}, o, {k, t0: s.start + o.t0, t1: s.start + (o.t1 === undefined ? o.t0 + 0.35 : o.t1)});
      if (o.items) add(o.items, g);
      if (o.op === 'screw') {
        g.turns = Math.min(4, Math.max(2, Math.round(o.thread / o.pitch)));
        add([o.item], g);
        (plan.tools[o.tool] = plan.tools[o.tool] || []).push(g);
      }
      if (o.op === 'feed') o.wires.forEach(w => tubes[w].ops.push({type: 'feed', t0: g.t0, t1: g.t1, dist: o.from[2], state: 'pre'}));
      if (o.op === 'wire') o.wires.forEach(w => {
        const ops = tubes[w].ops;
        ops.push({type: 'wire', t0: g.t0, t1: g.t1, prev: ops.length ? ops[ops.length - 1].state : 'pre', state: o.to});
      });
      if (o.op === 'knot') o.wires.forEach(w => { knots[w].t0 = g.t0; });
      if (o.op === 'sleeve') tubes.cable_sleeve.ops.push({type: 'slide', t0: g.t0, t1: g.t1, dist: o.from, state: 'final'});
      if (o.op === 'drive') plan.drives.push(g);
    }));
    plan.items.forEach(list => list.sort((a, b) => a.t0 - b.t0));
    PLAN = plan;
    asm.t = Math.min(asm.t, plan.total);
    const bar = $('asm-steps');
    bar.innerHTML = steps.map((s, k) => `<button data-k="${k}" style="flex:${s.dur} 1 0" title="${esc(`${k + 1}. ${s.title} (ASSEMBLY.md step ${s.ref})`)}">${k + 1}</button>`).join('');
    $('asm-time').max = plan.total;
  }

  const latest = (list, t) => { let o = null; if (list) for (const x of list) { if (x.t0 <= t) o = x; else break; } return o; };
  const frac = (o, t) => ease(clamp01((t - o.t0) / Math.max(o.t1 - o.t0, 1e-6)));
  const stepAt = t => { const s = PLAN.steps; let k = 0; while (k < s.length - 1 && t >= s[k + 1].start) k++; return k; };
  function screwPhase(o, t) {        // head distance from home along `out`, driver tip distance, turn angle
    const a = o.t0 + (o.t1 - o.t0) * PLAN.times[0], b = o.t0 + (o.t1 - o.t0) * PLAN.times[1], full = -o.turns * 2 * Math.PI;
    if (t < a) { const d = o.thread + o.approach * (1 - ease(clamp01((t - o.t0) / (a - o.t0)))); return {head: d, tool: d, angle: 0}; }
    if (t < b) { const g = ease(clamp01((t - a) / (b - a))), d = o.thread * (1 - g); return {head: d, tool: d, angle: full * g}; }
    return {head: 0, tool: o.approach * ease(clamp01((t - b) / (o.t1 - b))), angle: full};
  }
  function pose(o, t) {
    const f = frac(o, t);
    if (o.op === 'move') { const to = o.to || [0, 0, 0]; return {off: o.from.map((x, i) => x + (to[i] - x) * f)}; }
    if (o.op === 'feed') return {off: o.from.map(x => x * (1 - f))};
    if (o.op === 'drive') return {off: [0, 0, o.from + (o.to - o.from) * f]};
    if (o.op === 'screw') {
      const s = screwPhase(o, t);
      return {off: o.out.map(x => x * s.head), spin: {axis: o.out, point: o.tip, angle: s.angle}};
    }
    return {off: [0, 0, 0]};
  }
  const M1 = new THREE.Matrix4(), QT = new THREE.Quaternion(), XA = new THREE.Vector3(1, 0, 0);
  function setPose(mesh, ps, theta) {
    const m = mesh.matrix;
    m.makeTranslation(mesh.userData.dz - CENTRE, 0, 0);
    if (theta) m.premultiply(M1.makeRotationX(theta));
    if (ps.spin && ps.spin.angle) {
      const p = mv(...ps.spin.point);
      m.premultiply(M1.makeTranslation(-p.x, -p.y, -p.z));
      m.premultiply(M1.makeRotationAxis(mdir(...ps.spin.axis).normalize(), ps.spin.angle));
      m.premultiply(M1.makeTranslation(p.x, p.y, p.z));
    }
    const o = mdir(...ps.off);
    m.premultiply(M1.makeTranslation(o.x, o.y, o.z));
    mesh.matrixAutoUpdate = false;
    mesh.matrixWorldNeedsUpdate = true;
  }
  function setTool(mesh, o, dist, angle) {
    const out = mdir(...o.out).normalize(), tip = mv(...o.tip).addScaledVector(out, dist), m = mesh.matrix;
    m.makeTranslation(mesh.userData.dz, 0, 0);                    // blade along viewer +X, tip at the origin
    m.premultiply(M1.makeRotationX(angle));
    m.premultiply(M1.makeRotationFromQuaternion(QT.setFromUnitVectors(XA, out)));
    m.premultiply(M1.makeTranslation(tip.x, tip.y, tip.z));
    mesh.matrixAutoUpdate = false;
    mesh.matrixWorldNeedsUpdate = true;
  }
  function wireFrame(w, t) {        // centre line at time t into w.tube.pts; false while not fitted yet
    let o = null;
    for (const x of w.ops) { if (x.t0 <= t) o = x; else break; }
    if (!o) return false;
    const f = frac(o, t), out = w.tube.pts, n = w.n;
    if (o.type === 'feed') {         // the board moves in; its wires run ahead of it down their path
      const src = w.paths.pre, s = o.dist * (1 - f);
      for (let i = 0; i < n; i++) {
        const u = i * w.step;
        if (u < s) { out[3 * i] = src[0]; out[3 * i + 1] = src[1]; out[3 * i + 2] = src[2] + (s - u); }
        else sampleInto(src, n, (u - s) / w.step, out, i);
      }
    } else if (o.type === 'slide') { // the sleeve slides along its own path, from beyond its far end
      const src = w.paths.final, s = o.dist * (1 - f), e = 3 * (n - 1);
      const d = [0, 1, 2].map(c => src[e + c] - src[e - 3 + c]), dl = Math.hypot(...d);
      for (let i = 0; i < n; i++) {
        const u = i * w.step + s;
        if (u <= w.len) sampleInto(src, n, u / w.step, out, i);
        else for (let c = 0; c < 3; c++) out[3 * i + c] = src[e + c] + d[c] / dl * (u - w.len);
      }
    } else {
      const A = w.paths[o.prev], B = w.paths[o.state];
      for (let i = 0; i < 3 * n; i++) out[i] = A[i] + (B[i] - A[i]) * f;
    }
    return true;
  }
  function screwTheta(t) {
    const o = latest(PLAN.drives, t);
    return o ? -(o.from + (o.to - o.from) * frac(o, t)) / P.mechanics.screw_pitch_mm * 2 * Math.PI : 0;
  }

  function asmPlace() {
    const t = asm.t, step = PLAN.steps[stepAt(t)], look = step.look, theta = screwTheta(t);
    meshes.forEach((mesh, name) => {
      const it = mesh.userData;
      let vis = 'hide';
      if (it.kind === 'tool') {
        const o = (PLAN.tools[it.tool] || []).find(x => x.t0 <= t && t <= x.t1);
        if (o) { const s = screwPhase(o, t); setTool(mesh, o, s.tool, s.angle); vis = 'show'; }
      } else if (it.kind !== 'cutaway' && it.kind !== 'wire' && name !== 'cable_sleeve') {
        const o = latest(PLAN.items.get(name), t);
        // solid and ghost show the whole parts, half the pin-plane cut, xhalf the screw-plane cut where a part has one
        const want = {half: 'section', xhalf: meshes.has(`${base(name)}__xhalf`) ? 'xsection' : 'printed'}[look] || 'printed';
        const printed = ['printed', 'section', 'xsection'].includes(it.kind);
        if (o && (!printed || it.kind === want)) {
          setPose(mesh, pose(o, t), it.rotating ? theta : 0);
          vis = look === 'ghost' && it.kind === 'printed' ? 'ghost' : 'show';
        }
      }
      placed.set(name, vis);
    });
    Object.keys(tubes).forEach(n => {
      const w = tubes[n], on = wireFrame(w, t);
      w.tube.mesh.visible = on;
      if (on) w.tube.update();
      const k = knots[n];
      if (k) {
        k.mesh.visible = on && t >= k.t0;
        if (k.mesh.visible) {
          const q = new Float32Array(3);
          sampleInto(w.tube.pts, w.n, k.u / w.step, q, 0);
          k.mesh.position.copy(mv(q[0], q[1], q[2]));
          k.mesh.scale.setScalar(Math.max(0.01, ease(clamp01((t - k.t0) / 0.4))));
        }
      }
    });
  }

  function camAt(t) {
    const k = stepAt(t), s = PLAN.steps[k], tau = t - s.start, keys = s.cams;
    let a = keys[0], b = keys[0], f = 0;
    if (tau < keys[0][0]) {
      const pk = k ? PLAN.steps[k - 1].cams : keys;
      a = pk[pk.length - 1];
      f = ease(clamp01(tau / keys[0][0]));
    } else {
      let i = 0;
      while (i < keys.length - 1 && tau >= keys[i + 1][0]) i++;
      a = keys[i];
      b = keys[Math.min(i + 1, keys.length - 1)];
      f = b === a ? 0 : ease(clamp01((tau - a[0]) / (b[0] - a[0])));
    }
    const lerp = (x, y) => x.map((q, i) => q + (y[i] - q) * f);
    return {target: lerp(a[1], b[1]), dir: lerp(a[2], b[2]), span: a[3] * Math.pow(b[3] / a[3], f), k};
  }
  let camBusy = false;
  function asmCamera(force) {
    const c = camAt(asm.t);
    if (!force && asm.freeStep === c.k) return;
    if (asm.freeStep !== c.k) asm.freeStep = -1;
    const tg = mv(...c.target), d = mdir(...c.dir).normalize();
    camBusy = true;
    controls.target.copy(tg);
    camera.position.copy(tg).addScaledVector(d, 900);
    camera.zoom = (camera.right - camera.left) / c.span;
    camera.updateProjectionMatrix();
    controls.update();
    camBusy = false;
  }
  function asmLabel() {
    if (!PLAN) return '';
    const k = stepAt(asm.t), s = PLAN.steps[k];
    return `ASSEMBLY · V6-${V}<br>step ${k + 1} of ${PLAN.steps.length} · ASSEMBLY.md step ${s.ref}`;
  }
  const clock = x => `${Math.floor(x / 60)}:${String(Math.floor(x % 60)).padStart(2, '0')}`;
  function asmUi() {
    if (!PLAN) return;
    const k = stepAt(asm.t), s = PLAN.steps[k];
    $('asm-title').textContent = `${k + 1} · ${s.title}`;
    $('asm-text').textContent = s.text;
    $('asm-time').value = asm.t;
    $('asm-clock').textContent = `${clock(asm.t)} / ${clock(PLAN.total)}`;
    $('asm-play').textContent = asm.playing ? '❚❚' : '▶';
    $('asm-play').setAttribute('aria-label', asm.playing ? 'Pause' : 'Play');
    $('asm-steps').querySelectorAll('button').forEach((b, i) => {
      b.classList.toggle('on', i === k);
      b.classList.toggle('done', i < k);
    });
  }
  function asmSeek(t) {
    asm.t = THREE.MathUtils.clamp(Number(t), 0, PLAN.total);
    if (mode !== 'assembly') setMode('assembly');
    update();
  }
  function asmLoop(ts) {
    if (!asm.playing) return;
    const dt = asm.last ? Math.min((ts - asm.last) / 1000, 0.1) : 0;
    asm.last = ts;
    asm.t = Math.min(asm.t + dt * asm.speed, PLAN.total);
    update();
    if (asm.t >= PLAN.total) { asmPause(); return; }
    asm.raf = requestAnimationFrame(asmLoop);
  }
  function asmPlay() {
    if (mode !== 'assembly') setMode('assembly');
    if (asm.t >= PLAN.total - 1e-3) asm.t = 0;
    asm.playing = true;
    asm.last = 0;
    if (!asm.raf) asm.raf = requestAnimationFrame(asmLoop);
    asmUi();
  }
  function asmPause() {
    asm.playing = false;
    if (asm.raf) cancelAnimationFrame(asm.raf);
    asm.raf = null;
    asmUi();
  }
  function asmStep(dk) {
    let k = stepAt(asm.t);
    if (dk < 0 && asm.t - PLAN.steps[k].start > 1.0) dk = 0;      // first press: back to the start of this step
    k = THREE.MathUtils.clamp(k + dk, 0, PLAN.steps.length - 1);
    asm.freeStep = -1;
    asmSeek(PLAN.steps[k].start);
  }
  function asmState() {
    const vis = [...meshes.values()].filter(m => m.visible).map(m => m.name);
    return {t: asm.t, step: PLAN.steps[stepAt(asm.t)].id, playing: asm.playing, total: PLAN.total, visible: vis,
            tubes: Object.keys(tubes).filter(n => tubes[n].tube.mesh.visible)};
  }

  // ---- end-stop physics (follows the circuit simulation) -------------------------------------
  function magnetZ() { return P.magnet_end_z[0] + S.travel; }
  function hallState(prev, dist, fresh) {
    // DRV5033: OUT low within the operate distance, back high beyond the release distance
    if (prev === null || fresh) return dist <= OPERATE();
    return prev ? dist <= RELEASE() : dist <= OPERATE();
  }
  function hallUpdate(fresh) {
    // Each Hall switch is fed from the other wire, so it only runs while its own direction is driven.
    const m = magnetZ();
    S.u1 = S.drive < 0 ? hallState(S.u1, Math.abs(m - P.hall_z[0]), fresh) : null;
    S.u2 = S.drive > 0 ? hallState(S.u2, Math.abs(m - P.hall_z[1]), fresh) : null;
  }
  function conducting() {
    return (S.drive > 0 && S.u2 === false) || (S.drive < 0 && S.u1 === false);
  }

  function step(dtMotion, dtReal) {
    hallUpdate(false);
    S.running = false;
    if (S.drive === 0) {
      S.current = 0;
      S.offS += dtReal;
      if (S.tripped && S.offS > 2.0) { S.tripped = false; S.stallS = 0; }
      if (!S.tripped) S.stallS = Math.max(0, S.stallS - dtReal);
      return;
    }
    S.offS = 0;
    if (!conducting()) { S.current = 0; return; }
    if (S.tripped) { S.current = SIMD.after_trip_mA; return; }
    if (S.jam) {
      S.current = SIMD.stall_mA;
      S.stallS += dtReal;
      if (S.stallS >= SIMD.trip_s) S.tripped = true;
      return;
    }
    S.current = SIMD.run_mA;
    S.running = true;
    S.travel = THREE.MathUtils.clamp(S.travel + S.drive * P.mechanics.speed_simulated_mm_s * dtMotion,
                                     -P.overtravel_mm, P.stroke_mm + P.overtravel_mm);
  }

  function loop(t) {
    const dt = lastT ? Math.min((t - lastT) / 1000, 0.1) : 0;
    lastT = t;
    step(dt * Number($('speed').value), dt);
    update();
    if (S.drive !== 0 || S.tripped || S.stallS > 0) raf = requestAnimationFrame(loop);
    else { raf = null; lastT = 0; }
  }
  function kick() { if (!raf) { lastT = 0; raf = requestAnimationFrame(loop); } }

  function drive(dir) {
    S.drive = dir;
    hallUpdate(true);
    kick();
    update();
  }

  function setTravel(v) {
    S.travel = THREE.MathUtils.clamp(Number(v), -P.overtravel_mm, P.stroke_mm + P.overtravel_mm);
    hallUpdate(false);
    update();
  }

  function simulate(dir, seconds) {
    // Same logic as the animation in fixed 10 ms steps (for automated checks).
    S.drive = dir;
    hallUpdate(true);
    for (let t = 0; t < seconds; t += 0.01) step(0.01, 0.01);
    update();
    return getState();
  }

  // the current path through the board for the present state
  function path() {
    const nets = new Set(), parts = new Map();
    if (S.drive === 0) return {nets, parts};
    const ext = S.drive > 0;
    const [uOwn, qOwn, dSup] = ext ? ['U2', 'Q2', 'D2'] : ['U1', 'Q1', 'D1'];
    const uState = ext ? S.u2 : S.u1;
    parts.set(dSup, 'flow');
    if (uState) { parts.set(uOwn, 'trig'); parts.set(qOwn, 'off'); }
    if (S.tripped) parts.set('F1', 'off');
    if (conducting() && !S.tripped) {
      ['A', 'A_SW', 'MOT+', 'MOT-', 'B'].forEach(n => nets.add(n));
      (ext ? ['D4', 'F1', 'M1', 'Q2', 'W1', 'W2', 'W3', 'W4'] : ['D5', 'F1', 'M1', 'Q1', 'W1', 'W2', 'W3', 'W4'])
        .forEach(r => parts.set(r, 'flow'));
    }
    return {nets, parts};
  }

  // ---- selection -----------------------------------------------------------------------------
  function selectedMeshes() {
    const out = new Set();
    if (!selected) return out;
    const {type, id} = selected;
    meshes.forEach((m, name) => {
      const it = m.userData;
      if (type === 'part' && (it.ref === id || (id === 'M1' && it.kind === 'hardware' && name.startsWith('motor_')))) out.add(name);
      if (type === 'net' && it.net === id) out.add(name);
      if (type === 'wire' && it.wire_id === id) out.add(name);
      if (type === 'pad') {
        const p = CIR.parts[id];
        if (it.wire_id === p.wire || (it.board_kind === 'copper' && it.layer === 'top pads' && it.net === p.net)) out.add(name);
      }
      if (type === 'mesh' && base(name) === id) out.add(name);
    });
    return out;
  }

  function selectionFor(it) {
    if (it.ref && it.ref !== 'PCB') return {type: 'part', id: it.ref};
    if (it.board_kind === 'copper') return {type: 'net', id: it.net};
    if (it.kind === 'wire') return {type: 'wire', id: it.wire_id};
    const b = base(it.name);
    if (b.startsWith('motor_')) return {type: 'part', id: 'M1'};
    return {type: 'mesh', id: b};
  }

  function select(sel, fromSchematic) {
    selected = sel;
    if (sel && fromSchematic) {
      const inside = sel.type !== 'mesh' && !(sel.type === 'part' && sel.id === 'M1');
      if (inside && (mode === 'exterior' || mode === 'core')) setMode('board');
      if (sel.type === 'part' && sel.id === 'M1' && mode === 'exterior') setMode('section');
    }
    update();
  }

  // ---- schematic -----------------------------------------------------------------------------
  const schem = $('schem'), svg = schem.querySelector('svg');
  const PAGE = CIR.page_pt;
  let vb = [0, 0, PAGE[0], PAGE[1]], drag = null, dragged = false;
  function setVB() { svg.setAttribute('viewBox', vb.map(x => x.toFixed(2)).join(' ')); }
  function toSvg(x, y) {
    const pt = svg.createSVGPoint();
    pt.x = x; pt.y = y;
    return pt.matrixTransform(svg.getScreenCTM().inverse());
  }
  function zoomAt(f, cx, cy) {
    const w = THREE.MathUtils.clamp(vb[2] * f, PAGE[0] / 10, PAGE[0] * 1.1), k = w / vb[2];
    vb = [cx - (cx - vb[0]) * k, cy - (cy - vb[1]) * k, w, vb[3] * k];
    setVB();
  }
  function zoomCentre(f) { zoomAt(f, vb[0] + vb[2] / 2, vb[1] + vb[3] / 2); }
  schem.addEventListener('wheel', e => {
    e.preventDefault();
    const p = toSvg(e.clientX, e.clientY);
    zoomAt(e.deltaY > 0 ? 1.15 : 1 / 1.15, p.x, p.y);
  }, {passive: false});
  schem.addEventListener('pointerdown', e => {
    drag = {x: e.clientX, y: e.clientY, vb: vb.slice(), scale: svg.getScreenCTM().a};
    dragged = false;
  });
  window.addEventListener('pointermove', e => {
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (!dragged && Math.hypot(dx, dy) < 4) return;
    dragged = true;
    schem.classList.add('dragging');
    vb = [drag.vb[0] - dx / drag.scale, drag.vb[1] - dy / drag.scale, drag.vb[2], drag.vb[3]];
    setVB();
  });
  window.addEventListener('pointerup', () => { drag = null; schem.classList.remove('dragging'); });
  schem.addEventListener('click', e => {
    if (dragged) { dragged = false; return; }
    const t = e.target.closest('[data-ref],[data-net]');
    if (!t) { select(null); return; }
    const ref = t.dataset.ref;
    if (ref) select(/^W\d$/.test(ref) ? {type: 'wire', id: ref} : ref.startsWith('J_') ? {type: 'pad', id: ref}
      : {type: 'part', id: ref}, true);
    else select({type: 'net', id: t.dataset.net}, true);
  });
  $('zin').onclick = () => zoomCentre(1 / 1.3);
  $('zout').onclick = () => zoomCentre(1.3);
  $('zfit').onclick = () => { vb = [0, 0, PAGE[0], PAGE[1]]; setVB(); };

  function updateSchematic(pth) {
    svg.querySelectorAll('#sch-overlay .part').forEach(el => {
      const r = el.dataset.ref, st = pth.parts.get(r);
      let on = false;
      if (selected) {
        if (selected.type === 'part' || selected.type === 'pad' || selected.type === 'wire') on = selected.id === r;
        if (selected.type === 'pad' && CIR.parts[selected.id].wire === r) on = true;
        if (selected.type === 'wire' && CIR.parts[r] && CIR.parts[r].wire === selected.id) on = true;
      }
      el.classList.toggle('on', on);
      el.classList.toggle('flow', st === 'flow');
      el.classList.toggle('off', st === 'off');
      el.classList.toggle('trig', st === 'trig');
    });
    const selNet = selected && selected.type === 'net' ? selected.id : null;
    svg.querySelectorAll('#sch-overlay .net').forEach(el => {
      el.classList.toggle('on', el.dataset.net === selNet);
      el.classList.toggle('flow', pth.nets.has(el.dataset.net));
    });
  }

  // ---- info card -----------------------------------------------------------------------------
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  const chip = (type, id, text) => `<span class="chip" data-type="${type}" data-id="${esc(id)}">${esc(text || id)}</span>`;
  function liveState(ref) {
    const u = r => (r === null ? 'not powered (its direction is not driven)'
      : r ? 'OUT low: magnet in range, its MOSFET is off' : 'OUT high: no magnet, its MOSFET is on');
    if (ref === 'U1') return u(S.u1);
    if (ref === 'U2') return u(S.u2);
    if (ref === 'Q1') return S.drive < 0 ? (S.u1 ? 'off: blocks retracting' : 'on: carries the retract current')
      : S.drive > 0 ? 'bypassed: D4 and the body diode carry the extend current' : 'idle';
    if (ref === 'Q2') return S.drive > 0 ? (S.u2 ? 'off: blocks extending' : 'on: carries the extend current')
      : S.drive < 0 ? 'bypassed: D5 and the body diode carry the retract current' : 'idle';
    if (ref === 'F1') return S.tripped ? 'tripped (hot, high resistance)' : S.jam && S.stallS > 0
      ? `heating at ${SIMD.stall_mA} mA (${S.stallS.toFixed(1)} of ${SIMD.trip_s} s)` : 'cold, about 2 Ω';
    return null;
  }
  let cardSig = '';
  function renderCard() {
    const el = $('card');
    const sig = JSON.stringify([V, mode === 'printed' || mode === 'assembly' ? mode : '', selected,
      selected && selected.type === 'part' ? liveState(selected.id) : 0, mode === 'assembly' && PLAN ? stepAt(asm.t) : 0]);
    if (sig === cardSig) return;
    cardSig = sig;
    if (!selected && mode === 'printed') {
      const pr = ASM.print[V] || {};
      el.innerHTML = `<h2>Printed parts · V6-${esc(V)}</h2><p class="role">Six PETG parts, shown as they sit on the print bed.
        Click a part for its slicer settings. The files are in stl/V6-${esc(V)}/, already in this orientation.</p><table>
        ${Object.keys(pr).sort().map(n => `<tr><td>${chip('mesh', n, n.slice(0, 2))}</td><td>${esc(n.slice(3).replace(/_/g, ' '))} ·
        ${pr[n].print_extent_mm.map(x => x.toFixed(1)).join(' × ')} mm · ${pr[n].mass_solid_g.toFixed(1)} g</td></tr>`).join('')}</table>`;
      return;
    }
    if (!selected && mode === 'assembly' && PLAN) {
      const now = stepAt(asm.t);
      el.innerHTML = `<h2>Assembly · V6-${esc(V)}</h2><p class="role">The order of ASSEMBLY.md, part by part. Click a step to
        jump to it; drag the view at any time.</p><table>${PLAN.steps.map((st, k) => `<tr><td>${chip('step', k, `${k + 1}`)}</td>
        <td${k === now ? ' style="font-weight:650"' : ''}>${esc(st.title)} <span style="color:var(--muted)">· step ${esc(st.ref)}</span></td></tr>`).join('')}</table>`;
      return;
    }
    if (!selected) {
      el.innerHTML = `<h2>Board parts</h2><p class="role">Click a part in the schematic or the 3D view. Board view shows
        the board from the bore side, with the parts facing you.</p><table>
        <tr><td>Retract end</td><td>${['U1', 'C1', 'R1', 'D1', 'Q1', 'D4'].map(r => chip('part', r)).join('')}</td></tr>
        <tr><td>Motor side</td><td>${['F1', 'C3', 'D3', 'M1'].map(r => chip('part', r)).join('')}</td></tr>
        <tr><td>Extend end</td><td>${['U2', 'C2', 'R2', 'D2', 'Q2', 'D5'].map(r => chip('part', r)).join('')}</td></tr>
        <tr><td>Wires</td><td>${['W1', 'W2', 'W3', 'W4'].map(w => chip('wire', w, `${w} ${CIR.wires[w].colour}`)).join('')}</td></tr></table>`;
      return;
    }
    const {type, id} = selected;
    if (type === 'part') {
      const p = CIR.parts[id];
      const pins = p.pins.map(x => `${esc(x.name)}${x.name !== x.pad ? ` (${esc(x.pad)})` : ''} ${chip('net', x.net)}`).join('<br>');
      const live = liveState(id);
      el.innerHTML = `<h2>${esc(id)} · ${esc(p.value)}</h2><p class="role">${esc(p.role)}</p><table>
        ${p.mpn ? `<tr><td>Part</td><td>${esc(p.mpn)}</td></tr><tr><td>LCSC</td><td>${esc(p.lcsc)}</td></tr>
        <tr><td>Package</td><td>${esc(p.package)}, ${p.height_mm} mm high</td></tr>` : ''}
        <tr><td>Pins</td><td>${pins}</td></tr>${live ? `<tr><td>Now</td><td>${esc(live)}</td></tr>` : ''}</table>`;
    } else if (type === 'net') {
      const n = CIR.nets[id];
      el.innerHTML = `<h2>Net ${esc(id)}</h2><p class="role">${esc(n.info)}</p><table>
        <tr><td>Connects</td><td>${n.members.map(esc).join(' · ')}</td></tr></table>`;
    } else if (type === 'wire') {
      const w = CIR.wires[id], it = [...meshes.values()].map(m => m.userData).find(x => x.wire_id === id);
      el.innerHTML = `<h2>${esc(id)} · ${esc(w.colour)}</h2><p class="role">0.8 mm PTFE wire (28 AWG) on net ${chip('net', w.net)}</p><table>
        <tr><td>From</td><td>board pad ${esc(it ? it.start_pad : '')}</td></tr><tr><td>To</td><td>${esc(it ? it.end : '')}</td></tr>
        <tr><td>In the model</td><td>${it ? it.length_mm : '–'} mm</td></tr></table>`;
    } else if (type === 'pad') {
      const p = CIR.parts[id];
      el.innerHTML = `<h2>${esc(id)} · wire pad</h2><p class="role">${esc(p.role)}</p><table>
        <tr><td>Net</td><td>${chip('net', p.net)}</td></tr><tr><td>Wire</td><td>${chip('wire', p.wire)}</td></tr></table>`;
    } else {
      const k = Object.keys(CIR.mech).find(x => id.startsWith(x)), pi = (ASM.print[V] || {})[id];
      const rows = pi ? `<table><tr><td>Print</td><td>${esc(pi.print_setup)}</td></tr>
        <tr><td>On the bed</td><td>${pi.print_extent_mm.map(x => x.toFixed(1)).join(' × ')} mm</td></tr>
        <tr><td>Mass</td><td>${pi.mass_solid_g.toFixed(1)} g as a solid part</td></tr>
        <tr><td>File</td><td>${esc(pi.file)}</td></tr></table>` : '';
      el.innerHTML = `<h2>${esc(id)}</h2><p class="role">${esc(k ? CIR.mech[k] : 'Part of the assembly.')}</p>${rows}`;
    }
  }
  $('card').addEventListener('click', e => {
    const c = e.target.closest('.chip');
    if (c && c.dataset.type === 'step') { asm.freeStep = -1; asmSeek(PLAN.steps[Number(c.dataset.id)].start); }
    else if (c) select({type: c.dataset.type, id: c.dataset.id}, true);
  });

  // ---- 3D picking ----------------------------------------------------------------------------
  const ray = new THREE.Raycaster();
  let down = null;
  canvas.addEventListener('pointerdown', e => { down = {x: e.clientX, y: e.clientY, b: e.button}; });
  canvas.addEventListener('pointerup', e => {
    if (!down || down.b !== 0 || Math.hypot(e.clientX - down.x, e.clientY - down.y) > 5) { down = null; return; }
    down = null;
    const r = canvas.getBoundingClientRect();
    ray.setFromCamera(new THREE.Vector2((e.clientX - r.left) / r.width * 2 - 1, -(e.clientY - r.top) / r.height * 2 + 1), camera);
    const hit = ray.intersectObjects([...meshes.values()].filter(m => m.visible && !m.material.transparent), false)[0];
    select(hit ? selectionFor(hit.object.userData) : null);
  });

  // ---- render --------------------------------------------------------------------------------
  const tmp = new THREE.Vector3();
  function placeLabels() {
    const show = mode === 'board', w = stage.clientWidth, h = stage.clientHeight, pshow = mode === 'printed';
    partLabels.forEach((el, name) => {
      el.style.display = pshow ? '' : 'none';
      if (!pshow) return;
      tmp.copy(printLayout.get(name).anchor).project(camera);
      el.style.left = `${(tmp.x + 1) / 2 * w}px`;
      el.style.top = `${(1 - tmp.y) / 2 * h}px`;
      el.classList.toggle('on', !!selected && selected.type === 'mesh' && selected.id === name);
    });
    labels.forEach((el, ref) => {
      el.style.display = show ? '' : 'none';
      if (!show) return;
      const m = [...meshes.values()].find(x => x.userData.ref === ref && x.userData.board_kind === 'part');
      m.geometry.boundingBox.getCenter(tmp);
      tmp.add(m.position);
      tmp.z += 1.2;
      tmp.project(camera);
      el.style.left = `${(tmp.x + 1) / 2 * w}px`;
      el.style.top = `${(1 - tmp.y) / 2 * h}px`;
      el.classList.toggle('on', !!selected && selected.type === 'part' && selected.id === ref);
    });
  }
  function render() { renderer.render(scene, camera); placeLabels(); }

  function update() {
    const theta = -S.travel / P.mechanics.screw_pitch_mm * 2 * Math.PI;
    const sel = selectedMeshes(), pth = path();
    const pulse = 0.55 + 0.45 * Math.sin(performance.now() / 160);
    const staged = mode === 'assembly' || mode === 'printed';
    if (mode === 'assembly') asmPlace();
    else if (mode === 'printed') printPlace();
    meshes.forEach(mesh => {
      const it = mesh.userData;
      let vis;
      if (staged) vis = placed.get(it.name) || 'hide';
      else {
        mesh.matrixAutoUpdate = true;
        mesh.position.set(it.dz + (it.moving ? S.travel : 0) - CENTRE, 0, 0);
        mesh.rotation.set(it.rotating ? theta : 0, 0, 0);
        if (it.geartrain_rotation) {
          const k = it.geartrain_rotation;
          const pivot = mdir(...k.axis_origin_mm), axis = mdir(...k.axis_direction).normalize();
          // Geometry already contains the tooth phase. Rotate around each
          // shaft in V6's (z,y,-x) coordinates, then apply the scene offset.
          mesh.quaternion.setFromAxisAngle(axis, theta * k.angle_per_output_rad);
          mesh.position.add(pivot.clone().sub(pivot.clone().applyQuaternion(mesh.quaternion)));
        }
        vis = visibility(it);
      }
      const ghost = vis === 'ghost', m = mesh.material;
      mesh.visible = vis !== 'hide';
      m.transparent = ghost;
      m.opacity = ghost ? 0.14 : 1;
      m.depthWrite = !ghost;
      mesh.renderOrder = ghost ? 2 : 0;
      mesh.castShadow = !ghost;
      if (sel.has(it.name)) { m.emissive.copy(SEL); m.emissiveIntensity = 0.6; }
      else if (it.net && pth.nets.has(it.net) && (it.board_kind === 'copper' || it.kind === 'wire')) {
        m.emissive.copy(FLOW); m.emissiveIntensity = 0.45 * pulse;
      } else m.emissive.setRGB(0, 0, 0);
    });
    if (mode === 'assembly') asmCamera(false);
    else {
      Object.values(tubes).forEach(w => { w.tube.mesh.visible = false; });
      Object.values(knots).forEach(k => { k.mesh.visible = false; });
    }
    bed.visible = mode === 'printed';
    ground.position.y = mode === 'core' || mode === 'gears' ? -6.05 : mode === 'printed' ? -2.0 : -7.4;
    asmUi();
    $('travel').value = S.travel;
    $('travel-value').textContent = S.travel.toFixed(1);
    $('length-value').textContent = (P.pin_centres_closed + S.travel).toFixed(1);
    $('current-value').textContent = S.current >= 10 ? Math.round(S.current) : S.current.toFixed(1);
    const led = (id, cls) => { $(id).className = 'led ' + cls; };
    const hs = (u, ref, end) => u === null ? [`${ref} ${end} end · not powered`, '']
      : u ? [`${ref} ${end} end · magnet: OUT low`, 'low'] : [`${ref} ${end} end · OUT high`, 'ok'];
    const [t1, c1] = hs(S.u1, 'U1', 'retract'), [t2, c2] = hs(S.u2, 'U2', 'extend');
    $('sig-u1').textContent = t1; led('led-u1', c1);
    $('sig-u2').textContent = t2; led('led-u2', c2);
    $('sig-f1').textContent = S.tripped ? 'F1 tripped' : S.jam && S.stallS > 0 ? 'F1 heating' : 'F1 cold';
    led('led-f1', S.tripped ? 'bad' : S.jam && S.stallS > 0 ? 'low' : 'ok');
    $('drive-ext').classList.toggle('active', S.drive > 0);
    $('drive-ret').classList.toggle('active', S.drive < 0);
    $('drive-off').classList.toggle('active', S.drive === 0);
    $('jam').textContent = S.jam ? 'Free the rod' : 'Jam the rod';
    $('status').textContent = statusText();
    $('view-label').innerHTML = views()[mode].label;
    updateSchematic(pth);
    renderCard();
    render();
  }

  function statusText() {
    const q = n => n.toFixed(1);
    if (S.tripped && S.drive !== 0) return `F1 has tripped: about ${SIMD.after_trip_mA} mA keeps it hot and the motor stopped. Switch the drive off for a few seconds to reset it.`;
    if (S.tripped) return 'F1 is cooling down; it resets after a few seconds without power.';
    if (S.drive === 0) return 'Off. With both wires open the leadscrew is self-locking, so the rod holds its position.';
    const ext = S.drive > 0;
    if (!conducting()) return ext
      ? `At the extend end (${q(S.travel)} mm): U2 sees the magnet and holds Q2's gate low, so no motor current flows; the board draws about ${SIMD.blocked_supply_mA.toFixed(1)} mA. Reverse to retract.`
      : `At the retract end (${q(S.travel)} mm): U1 sees the magnet and holds Q1's gate low, so no motor current flows; the board draws about ${SIMD.blocked_supply_mA.toFixed(1)} mA. Reverse to extend.`;
    if (S.jam) return `Rod jammed: the motor stalls at about ${SIMD.stall_mA} mA and F1 heats up; it trips after about ${SIMD.trip_s} s.`;
    return ext ? 'Extending: A → D4 → F1 → motor → Q2 → B. U2 is powered through D2 and has not seen the magnet yet.'
      : 'Retracting: B → D5 → motor → F1 → Q1 → A. U1 is powered through D1 and has not seen the magnet yet.';
  }

  function resize() {
    const w = stage.clientWidth, h = stage.clientHeight, a = w / Math.max(h, 1);
    const hw = (P.pin_centres_open + 30) / 2, hh = Math.max(hw / a, 22);
    camera.left = -hh * a; camera.right = hh * a; camera.top = hh; camera.bottom = -hh;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h, false);
    render();
  }

  function getState() {
    return {variant: V, mode, travel: S.travel, drive: S.drive, u1: S.u1, u2: S.u2, current: S.current,
            jam: S.jam, tripped: S.tripped, pinDistance: P.pin_centres_closed + S.travel,
            selected: selected && {...selected}};
  }

  // ---- wiring up -----------------------------------------------------------------------------
  $('travel').addEventListener('input', e => setTravel(e.target.value));
  $('drive-ext').onclick = () => drive(1);
  $('drive-ret').onclick = () => drive(-1);
  $('drive-off').onclick = () => drive(0);
  $('jam').onclick = () => { S.jam = !S.jam; if (!S.jam && !S.tripped) S.stallS = 0; kick(); update(); };
  $('reset').onclick = () => { aim(mode); render(); };
  document.querySelectorAll('[data-mode]').forEach(b => { b.onclick = () => setMode(b.dataset.mode); });
  document.querySelectorAll('[data-variant]').forEach(b => { b.onclick = () => buildVariant(b.dataset.variant); });
  let userCam = false;
  controls.addEventListener('start', () => { userCam = true; });
  controls.addEventListener('end', () => { userCam = false; });
  controls.addEventListener('change', () => {
    if (camBusy) return;
    if (userCam && mode === 'assembly' && PLAN) asm.freeStep = stepAt(asm.t);   // the user's view holds for this step
    render();
  });
  $('asm-play').onclick = () => (asm.playing ? asmPause() : asmPlay());
  $('asm-prev').onclick = () => asmStep(-1);
  $('asm-next').onclick = () => asmStep(1);
  $('asm-time').addEventListener('input', e => { asm.freeStep = -1; asmSeek(e.target.value); });
  $('asm-speed').onchange = e => { asm.speed = Number(e.target.value); };
  $('asm-steps').addEventListener('click', e => {
    const b = e.target.closest('button');
    if (b) { asm.freeStep = -1; asmSeek(PLAN.steps[Number(b.dataset.k)].start); }
  });
  document.addEventListener('keydown', e => {
    if (mode !== 'assembly' || /INPUT|SELECT|TEXTAREA|BUTTON/.test(e.target.tagName)) return;
    if (e.key === ' ') { e.preventDefault(); asm.playing ? asmPause() : asmPlay(); }
    if (e.key === 'ArrowRight') asmStep(1);
    if (e.key === 'ArrowLeft') asmStep(-1);
  });
  new ResizeObserver(resize).observe(stage);
  document.addEventListener('visibilitychange', () => { if (document.hidden) { drive(0); asmPause(); } });

  buildVariant(V);
  window.actuator = {setVariant: buildVariant, setMode, setTravel, drive, simulate, select, render, getState,
    items: () => [...meshes.values()].map(m => ({name: m.name, kind: m.userData.kind})),
    gearTransforms: () => [...meshes.values()].filter(m => m.userData.geartrain_rotation).map(m => ({
      name: m.name, position: m.position.toArray(), quaternion: m.quaternion.toArray(),
      rotation: m.userData.geartrain_rotation, dz: m.userData.dz, centre: CENTRE})),
    assembly: {seek: t => { asmSeek(t); return asmState(); }, play: asmPlay, pause: asmPause, state: asmState,
               steps: () => PLAN.steps.map(x => ({id: x.id, ref: x.ref, title: x.title, start: x.start, dur: x.dur})),
               record: on => { document.body.classList.toggle('record', !!on); resize(); update(); }},
    setJam: v => { S.jam = !!v; update(); }};
  window.viewerReady = true;
})();

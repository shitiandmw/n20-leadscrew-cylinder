'use strict';
// Browser check of ../3D_preview.html (offline, headless Chromium through Playwright) and its screenshots.
//   NODE_PATH=<dir with playwright> node check_viewer.cjs [shots]   -> ../browser_validation.json, ../images/*.png
// Software WebGL is slow with the whole machine in view (several seconds a frame), so every frame is rendered on demand.
const fs = require('fs'), path = require('path'), crypto = require('crypto');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..'), imgDir = path.join(root, 'images');
const R12 = path.resolve(root, '../excavator_arm_r12/source');
const shotsOnly = process.argv[2] === 'shots', checksOnly = process.argv[2] === 'checks';

(async () => {
  fs.mkdirSync(imgDir, { recursive: true });
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist'] });
  const rep = { file: '3D_preview.html', checks: {}, screenshots: [] };
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 860 }, offline: true });
    const page = await context.newPage(), errors = [], network = [];
    page.setDefaultTimeout(300000);
    page.on('pageerror', e => errors.push(e.message));
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
    page.on('request', r => { if (/^https?:/.test(r.url())) network.push(r.url()); });
    const html = fs.readFileSync(path.join(root, '3D_preview.html'));
    rep.sha256 = crypto.createHash('sha256').update(html).digest('hex');
    rep.size_mb = +(html.length / 1e6).toFixed(1);
    const t0 = Date.now();
    await page.goto('file://' + path.join(root, '3D_preview.html'));
    await page.waitForFunction(() => window.demo && window.demo.state().ready, null, { timeout: 300000 });
    rep.load_s = (Date.now() - t0) / 1000;
    const st = await page.evaluate(() => demo.state());
    rep.meshes = st.meshes;
    rep.timeline = { shown_s: st.total, real_s: st.real, segments: await page.evaluate(() => demo.timeline.map(s => s.title)) };

    if (!shotsOnly) {
      // 1. the page's R12 kinematics against poses_r12.body_poses() (R12's own reference cases)
      const cases = JSON.parse(fs.readFileSync(path.join(R12, 'viewer_cases.json')));
      rep.checks.kinematics = await page.evaluate(cases => {
        let pose = 0, tip = 0;
        for (const c of cases) {
          const s = demo.kinematic(c.strokes);
          for (const [b, p] of Object.entries(c.poses)) pose = Math.max(pose, Math.hypot(s.P[b][0] - p[0], s.P[b][1] - p[1]));
          tip = Math.max(tip, Math.hypot(s.tip[0] - c.tip[0], s.tip[1] - c.tip[1]));
        }
        return { cases: cases.length, max_origin_error_mm: pose, max_tip_error_mm: tip, pass: pose < 0.01 && tip < 0.01 };
      }, cases);
      // 2. the timeline: swing, pinion ratio, travel and the arm root
      rep.checks.timeline = await page.evaluate(() => {
        const T = demo.timeline, out = {};
        const at = (seg, u) => { demo.seek(T[seg].v0 + T[seg].vd * u); return demo.state(); };
        let s = at(0, 0); out.start = { swing: s.swing, travel: s.travel, armRoot: s.armRootWorld };
        s = at(0, 0.9999); out.travel_end = s.travel;
        s = at(2, 0.9999); out.swing_out = { swing: s.swing, pinion_deg: s.pinionDeg, armRoot: s.armRootWorld };
        s = at(3, 0.5); out.dump_mid = { swing: s.swing, payload: s.payload };
        s = at(1, 0.9); out.dig_late = { payload: s.payload, armT: s.armT };
        s = at(6, 0.9999); out.end = { travel: s.travel, swing: s.swing };
        const O = demo.config.O, r = out.swing_out.armRoot;
        out.pass = Math.abs(out.start.armRoot[0] - O[0]) < 1e-6 && Math.abs(out.start.armRoot[2] - O[2]) < 1e-6 && Math.abs(out.travel_end - 250) < 0.01
          && Math.abs(out.swing_out.swing - 90) < 0.01 && Math.abs(out.swing_out.pinion_deg - 4 * out.swing_out.swing) < 1e-6
          && Math.abs(r[0] - 250) < 0.01 && Math.abs(r[1] - O[0]) < 0.01 && Math.abs(out.end.travel) < 0.01 && out.dig_late.payload;
        return out;
      });
      // 3. tracks: the ground run does not slip (a shoe on the ground keeps its world X while the machine moves 5 mm)
      rep.checks.ground_run = await page.evaluate(() => {
        demo.setMode('manual'); demo.setTravel(0);
        const shoe = () => { const pts = []; const v = new THREE.Vector3(); scene.traverse(o => { if (o.isMesh && /J910 track shoe 70 \(left track, link (\d+)\)/.test(o.userData.name)) { o.getWorldPosition(v); pts.push([+o.userData.name.match(/link (\d+)/)[1], v.x, v.z]); } }); return pts; };
        const a = shoe(); demo.setTravel(5); const b = shoe();
        // flat run: shoes between the sprocket and the idler (centres X -70..70). The end links are engaged on the sprocket or the
        // idler and follow their pitch circles (chordal action, J9 README: up to 1.3 mm per tooth), so they move slightly in X and Z
        let worst = 0, flat = 0, n = 0, nf = 0;
        for (const p of a) { const q = b.find(x => x[0] === p[0]); if (p[2] < 12 && q[2] < 12) { const d = Math.abs(q[1] - p[1]); worst = Math.max(worst, d); n++; if (p[1] > -80 && p[1] < 80) { flat = Math.max(flat, d); nf++; } } }
        demo.setTravel(0);
        return { ground_shoes: n, flat_run_shoes: nf, max_slip_flat_run_mm: flat, max_slip_all_ground_shoes_mm: worst,
          note: 'a sign error would show 10 mm (twice the 5 mm move); end links follow the sprocket/idler pitch circles', pass: nf > 5 && flat < 1e-6 && worst < 0.5 };
      });
      // 4. assembly order: each step adds parts; the last shows all
      rep.checks.assembly = await page.evaluate(() => {
        demo.setMode('build'); const n = [];
        for (let k = 0; k < 9; k++) { demo.setBuild(k, 1); n.push(demo.state().visible); }
        const all = demo.state().meshes;
        return { visible_after_each_step: n, meshes: all, pass: n.every((v, i) => i === 0 || v > n[i - 1]) && n[8] === all };
      });
      // 5. exploded view and back
      rep.checks.exploded = await page.evaluate(() => {
        demo.setMode('demo'); demo.setView('exploded'); demo.explodeNow(); const e = demo.state();
        demo.setView('iso'); demo.explodeNow(); const b = demo.state();
        return { exploded: e.explode, back: b.explode, armRoot_exploded: e.armRootWorld, armRoot_back: b.armRootWorld, pass: e.explode === 1 && b.explode === 0 };
      });
    }
    // screenshots
    const shots = [
      ['complete_iso', `demo.setMode('demo');demo.seek(0.5);demo.setView('iso')`],
      ['complete_side_dig', `demo.setMode('demo');demo.seek(demo.timeline[1].v0+demo.timeline[1].vd*0.40);demo.setView('side')`],
      ['complete_dump_left', `demo.setMode('demo');demo.seek(demo.timeline[3].v0+demo.timeline[3].vd*0.45);demo.setView('iso')`],
      ['complete_front', `demo.setMode('demo');demo.seek(0.5);demo.setView('front')`],
      ['complete_rear', `demo.setMode('demo');demo.seek(0.5);demo.setView('rear')`],
      ['complete_top', `demo.setMode('demo');demo.seek(0.5);demo.setView('top')`],
      ['arm_mount', `demo.setMode('demo');demo.seek(0.5);demo.setView('mount')`],
      ['inside_body', `demo.setMode('demo');demo.seek(0.5);demo.setView('inside')`],
      ['cab', `demo.setMode('demo');demo.seek(0.5);demo.setView('cab')`],
      ['exploded', `demo.setMode('demo');demo.seek(0.5);demo.setView('exploded');demo.explodeNow()`],
      ['assembly_step2_xframe', `demo.setView('iso');demo.explodeNow();demo.setMode('build');demo.setBuild(1,0.45)`],
      ['assembly_step5_arm', `demo.setMode('build');demo.setBuild(4,0.5)`],
    ];
    for (const [name, js] of (checksOnly ? [] : shots)) {
      const t = Date.now();
      await page.evaluate(js);
      await page.evaluate(() => demo.render());
      const file = path.join(imgDir, name + '.png');
      await page.screenshot({ path: file, timeout: 300000 });
      rep.screenshots.push({ file: 'images/' + name + '.png', bytes: fs.statSync(file).size, seconds: (Date.now() - t) / 1000 });
      console.log('shot', name, (Date.now() - t) / 1000, 's');
    }
    await page.evaluate(() => { demo.setView('iso'); demo.explodeNow(); demo.setMode('demo'); demo.seek(0); });
    rep.errors = errors; rep.network_requests = network;
    rep.pass = !errors.length && !network.length && Object.values(rep.checks).every(c => c.pass);
  } finally { await browser.close(); }
  if (checksOnly) { const old = JSON.parse(fs.readFileSync(path.join(root, 'browser_validation.json'))); rep.screenshots = old.screenshots; rep.screenshots_note = 'from the previous full run on the same file'; }
  if (!shotsOnly) fs.writeFileSync(path.join(root, 'browser_validation.json'), JSON.stringify(rep, null, 1));
  console.log(JSON.stringify({ pass: rep.pass, checks: Object.fromEntries(Object.entries(rep.checks).map(([k, v]) => [k, v.pass])), errors: rep.errors, load_s: rep.load_s }));
})();

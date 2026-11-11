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
      // 4. installation order: each step adds parts (or moves a sub-assembly), the last shows all; the step's labels appear; the
      //    group offsets vanish once the group's step is done
      rep.checks.assembly = await page.evaluate(() => {
        demo.setMode('build'); const n = [], lab = [], ids = demo.stepIds;
        for (let k = 0; k < ids.length; k++) { demo.setBuild(k, 1); n.push(demo.state().visible); lab.push(demo.labelsShown()); }
        const all = demo.state().meshes;
        const grows = n.every((v, i) => i === 0 || v >= n[i - 1]), adds = n.filter((v, i) => i > 0 && v > n[i - 1]).length;
        return { steps: ids, visible_after_each_step: n, labels_per_step: lab, meshes: all,
          pass: grows && adds >= 9 && n[n.length - 1] === all && lab[ids.indexOf('plugs')] >= 8 && lab[ids.indexOf('pack')] >= 4 && lab[ids.indexOf('cells')] >= 3 };
      });
      // 4b. connectors: every joint of the catalogue has a label and the panel can fly to it; markers of the standard parts exist
      rep.checks.connectors = await page.evaluate(() => {
        demo.setMode('demo'); demo.seek(0.5);
        const joints = demo.joints, out = {};
        for (const j of joints.filter(j => demo.labelJoints.includes(j))) { demo.showJoint(j); demo.finishFlight(); demo.render(); out[j] = demo.labelsShown(); }
        demo.stdparts(true, ''); const all = demo.markers(); demo.stdparts(true, 'bearing'); const bearings = demo.markers(); demo.stdparts(false, '');
        const types = demo.catalogue.types.length;
        return { joints: joints.length, labels_when_shown: out, catalogue_types: types, markers_all: all, markers_bearings: bearings,
          pass: joints.length >= 14 && Object.values(out).every(v => v >= 1) && types >= 15 && all > 300 && bearings >= 36 };
      });
      // 5. exploded view and back
      rep.checks.exploded = await page.evaluate(() => {
        demo.setMode('demo'); demo.setView('exploded'); demo.explodeNow(); const e = demo.state();
        demo.setView('iso'); demo.explodeNow(); const b = demo.state();
        return { exploded: e.explode, back: b.explode, armRoot_exploded: e.armRootWorld, armRoot_back: b.armRootWorld, pass: e.explode === 1 && b.explode === 0 };
      });
      // 6. the moving cables: the page's loops, exits and drops against harness.py's lengths at three poses (same rules, same anchors)
      rep.checks.wiring = await page.evaluate(() => {
        demo.setMode('manual'); const rows = []; let worst = 0, n = 0;
        for (const ref of demo.wiringRef) {
          demo.setStrokes(ref.strokes); const got = demo.wiringLengths();
          for (const [name, L] of Object.entries(ref.lengths)) {
            // the page names them by cable: map harness.py's segment names
            const key = Object.keys(got).find(k => (name.includes('loop at O') && k.includes('loop at O') && k.startsWith(name.split(' ')[0])) ||
              (name.includes('loop at E') && k.includes('loop at E')) || (name.endsWith(' exit') && k.includes('exit') && k.startsWith(name.split(' ')[0])) ||
              (name.endsWith(' drop') && k.includes('drop') && k.startsWith(name.split('_')[0] + ' ' + name.split('_')[1].split(' ')[0])));
            const g = key ? got[key] : null; const d = g === null ? 1e9 : Math.abs(g - L); worst = Math.max(worst, d); n++;
            rows.push({ segment: name, page: key, python_mm: L, page_mm: g === null ? null : +g.toFixed(3), diff_mm: +d.toFixed(3) });
          }
        }
        demo.setStrokes(demo.config.default);
        return { poses: demo.wiringRef.length, segments: n, max_diff_mm: +worst.toFixed(3), rows, pass: n >= 21 && worst < 0.6 };
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
      ['harness', `demo.setMode('demo');demo.seek(0.5);demo.setView('harness')`],
      ['harness_boom_down', `demo.setMode('manual');demo.setStrokes([0,0,0]);demo.setView('harness')`],
      ['connectors_board_plugs', `demo.setMode('demo');demo.seek(0.5);demo.setView('connectors')`],
      ['battery_pack', `demo.setMode('demo');demo.seek(0.5);demo.setView('pack')`],
      ['joint_feed_xt30', `demo.setMode('demo');demo.seek(0.5);demo.showJoint('FEED');demo.finishFlight()`],
      ['joint_sm_left_track', `demo.setMode('demo');demo.seek(0.5);demo.showJoint('SM-L');demo.finishFlight()`],
      ['toolbox_switch_fuse_jack', `demo.setMode('demo');demo.seek(0.5);demo.showJoint('JACK');demo.finishFlight()`],
      ['standard_parts_bearings', `demo.setMode('demo');demo.seek(0.5);demo.setView('iso');demo.stdparts(true,'bearing')`],
      ['standard_parts_all', `demo.setView('exploded');demo.explodeNow();demo.stdparts(true,'');`],
      ['install_plugs', `demo.stdparts(false,'');demo.setView('iso');demo.explodeNow();demo.setMode('build');demo.setBuild(demo.stepIds.indexOf('plugs'),0.75);demo.finishFlight()`],
      ['install_pack', `demo.setMode('build');demo.setBuild(demo.stepIds.indexOf('pack'),0.75);demo.finishFlight()`],
      ['install_cells', `demo.setMode('build');demo.setBuild(demo.stepIds.indexOf('cells'),0.75);demo.finishFlight()`],
      ['install_hatch', `demo.setMode('build');demo.setBuild(demo.stepIds.indexOf('hatch'),0.7);demo.finishFlight()`],
      ['install_right_parts', `demo.setMode('build');demo.setBuild(demo.stepIds.indexOf('right_parts'),0.75);demo.finishFlight()`],
      ['cab', `demo.setMode('demo');demo.seek(0.5);demo.setView('cab')`],
      ['exploded', `demo.setMode('demo');demo.seek(0.5);demo.setView('exploded');demo.explodeNow()`],
      ['assembly_step2_xframe', `demo.setView('iso');demo.explodeNow();demo.setMode('build');demo.setBuild(1,0.45);demo.finishFlight()`],
      ['assembly_step5_arm', `demo.setMode('build');demo.setBuild(demo.stepIds.indexOf('arm'),0.5);demo.finishFlight()`],
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
    // the connector gallery page (build_connectors.py): every model rendered on its own
    if (!checksOnly && fs.existsSync(path.join(root, 'connector_gallery.html'))) {
      const gp = await context.newPage(); gp.setDefaultTimeout(300000);
      gp.on('pageerror', e => errors.push('gallery: ' + e.message)); gp.on('console', m => { if (m.type() === 'error') errors.push('gallery: ' + m.text()); });
      await gp.setViewportSize({ width: 1320, height: 1500 });
      await gp.goto('file://' + path.join(root, 'connector_gallery.html'));
      await gp.waitForFunction(() => window.gallery && window.gallery.count > 0, null, { timeout: 300000 });
      await gp.waitForTimeout(4000);
      const t = Date.now(), file = path.join(imgDir, 'connectors_gallery.png');
      await gp.screenshot({ path: file, fullPage: true, timeout: 300000 });
      rep.screenshots.push({ file: 'images/connectors_gallery.png', bytes: fs.statSync(file).size, seconds: (Date.now() - t) / 1000 });
      rep.gallery_models = await gp.evaluate(() => window.gallery.count);
      await gp.close();
    }
    rep.errors = errors; rep.network_requests = network;
    rep.pass = !errors.length && !network.length && Object.values(rep.checks).every(c => c.pass);
  } finally { await browser.close(); }
  if (checksOnly) { const old = JSON.parse(fs.readFileSync(path.join(root, 'browser_validation.json'))); rep.screenshots = old.screenshots; rep.screenshots_note = 'from the previous full run on the same file'; }
  if (!shotsOnly) fs.writeFileSync(path.join(root, 'browser_validation.json'), JSON.stringify(rep, null, 1));
  console.log(JSON.stringify({ pass: rep.pass, checks: Object.fromEntries(Object.entries(rep.checks).map(([k, v]) => [k, v.pass])), errors: rep.errors, load_s: rep.load_s }));
})();

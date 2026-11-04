'use strict';
// Browser check and video frames for ../3D_preview.html (offline, headless Chromium via Playwright).
//   node render_r12.cjs review [outdir]           -> ../browser_validation.json + review screenshots
//   node render_r12.cjs frames outdir from to     -> JPEG frames of the 150 g cycle at 20x, 24 fps
const fs = require('fs'), path = require('path'), crypto = require('crypto'), zlib = require('zlib'), assert = require('node:assert/strict');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..'), mode = process.argv[2] || 'review', out = process.argv[3] || '/tmp/r12-review';
const FPS = 24, SPEED = 20;

// camera path for the video: a slow swing between a front-left oblique and the side view
function cam(t, T) {
  const k = 0.5 - 0.5 * Math.cos(2 * Math.PI * t / T);
  return { az: -48 - 34 * k, el: 19 - 9 * k, dist: 1710 + 20 * k, tx: 342 - 43 * k, tz: -48 - 11 * k };
}

(async () => {
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: process.env.BROWSER_PATH,
    args: ['--no-sandbox', '--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist'] });
  try {
    const context = await browser.newContext({ viewport: { width: 1280, height: 720 }, offline: true });
    const page = await context.newPage(), errors = [], network = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
    page.on('request', r => { if (/^https?:/.test(r.url())) network.push(r.url()); });
    await page.goto('file://' + root + '/3D_preview.html');
    await page.waitForFunction(() => window.r12 && window.r12.state().ready, null, { timeout: 120000 });
    const html = fs.readFileSync(root + '/3D_preview.html'), hash = crypto.createHash('sha256').update(html).digest('hex');
    const meta = await page.evaluate(() => ({ duration: r12.duration, phases: r12.phases }));
    if (mode === 'review') {
      // 1. closed-form kinematics in the page against poses_r12.body_poses()
      const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'viewer_cases.json')));
      const kin = await page.evaluate(cases => {
        let pose = 0, ang = 0, tip = 0;
        for (const c of cases) {
          const s = r12.kinematic(c.strokes);
          for (const [b, p] of Object.entries(c.poses)) { pose = Math.max(pose, Math.hypot(s.P[b][0] - p[0], s.P[b][1] - p[1])); const da = s.P[b][2] - p[2]; ang = Math.max(ang, Math.abs(Math.atan2(Math.sin(da), Math.cos(da)))); }
          tip = Math.max(tip, Math.hypot(s.tip[0] - c.tip[0], s.tip[1] - c.tip[1]));
        }
        return { cases: cases.length, max_origin_error_mm: pose, max_angle_error_rad: ang, max_tip_error_mm: tip };
      }, cases);
      assert.ok(kin.max_origin_error_mm < 0.01 && kin.max_tip_error_mm < 0.01 && kin.max_angle_error_rad < 1e-4, JSON.stringify(kin));
      // 2. the scene shows the integrated MuJoCo states (body groups == trace poses at recorded frames)
      const replay = [];
      for (const name of ['payload_150g', 'unloaded']) {
        const tr = JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(root, 'simulation', name + '_trace.json.gz'))));
        const picks = tr.frames.filter((_, i) => i % 97 === 0);
        await page.evaluate(n => r12.setMode(n), name);
        const r = await page.evaluate(({ picks, bodies }) => {
          let err = 0, tip = 0;
          for (const f of picks) {
            const s = r12.seek(f.t, true);
            bodies.forEach((b, j) => { const g = r12.bodyPose(b); err = Math.max(err, Math.abs(g[0] - f.pose[3 * j]), Math.abs(g[1] - f.pose[3 * j + 1]), Math.abs(g[2] - f.pose[3 * j + 2])); });
            tip = Math.max(tip, Math.hypot(s.tip[0] - f.tip[0], s.tip[1] - f.tip[1]));
          }
          return { frames: picks.length, max_body_pose_error: err, max_tip_error_mm: tip };
        }, { picks, bodies: tr.bodies });
        assert.ok(r.max_body_pose_error < 1e-3 && r.max_tip_error_mm < 1e-3, JSON.stringify(r));
        replay.push({ name, ...r });
      }
      // 3. framing: every visible mesh stays inside the canvas in each view over the cycle
      const framed = [];
      for (const vp of [{ width: 1280, height: 720 }, { width: 390, height: 844 }]) {
        await page.setViewportSize(vp); await page.waitForTimeout(150);
        await page.evaluate(() => r12.setMode('payload_150g'));
        for (const view of ['oblique', 'side', 'front']) {
          const r = await page.evaluate(view => {
            r12.setView(view);
            const v = new THREE.Vector3(), b = { x0: 1, x1: -1, y0: 1, y1: -1 };
            for (let t = 0; t <= r12.duration; t += r12.duration / 40) {
              r12.seek(t, true);
              const cam = r12._camera(); cam.updateMatrixWorld(true);
              for (const m of r12._objects()) {
                if (!m.geometry.boundingBox) m.geometry.computeBoundingBox();
                const bb = m.geometry.boundingBox;
                for (const x of [bb.min.x, bb.max.x]) for (const y of [bb.min.y, bb.max.y]) for (const z of [bb.min.z, bb.max.z]) {
                  v.set(x, y, z).applyMatrix4(m.matrixWorld).project(cam);
                  b.x0 = Math.min(b.x0, v.x); b.x1 = Math.max(b.x1, v.x); b.y0 = Math.min(b.y0, v.y); b.y1 = Math.max(b.y1, v.y);
                }
              }
            }
            return b;
          }, view);
          const inside = Object.values(r).every(x => Math.abs(x) < 0.99);
          framed.push({ viewport: vp, view, ndc_bounds: r, inside });
          assert.ok(inside, JSON.stringify({ vp, view, r }));
        }
        await page.evaluate(() => { r12.setView('oblique'); r12.seek(300); });
        await page.waitForTimeout(500);
        await page.screenshot({ path: path.join(out, vp.width < 500 ? 'mobile.png' : 'oblique.png') });
      }
      await page.setViewportSize({ width: 1280, height: 720 }); await page.waitForTimeout(150);
      // 4. screenshots per phase (side view) and close-ups
      await page.evaluate(() => r12.setView('side'));
      for (const p of meta.phases) { await page.evaluate(t => r12.seek(t), p.move[1]); await page.screenshot({ path: path.join(out, `phase_${p.id + 1}.png`) }); }
      await page.evaluate(() => { r12.setView('front'); r12.seek(0); }); await page.screenshot({ path: path.join(out, 'front.png') });
      await page.evaluate(() => { r12.seek(260); r12.setView('bucket'); r12.seek(260); }); await page.screenshot({ path: path.join(out, 'bucket.png') });
      // 5. controls
      await page.locator('[data-mode="manual"]').click(); await page.waitForFunction(() => r12.state().mode === 'manual');
      await page.locator('#k2').fill('60'); await page.locator('#k1').fill('60');
      const st = await page.evaluate(() => r12.state().strokes); assert.deepEqual(st.slice(1), [60, 60]);
      await page.locator('#xray').click(); await page.locator('#pinbtn').click(); await page.locator('[data-view="side"]').click();
      await page.screenshot({ path: path.join(out, 'manual_xray.png') });
      await page.locator('#xray').click(); await page.locator('#pinbtn').click();
      await page.locator('[data-mode="unloaded"]').click(); await page.waitForFunction(() => r12.state().mode === 'unloaded');
      await page.locator('#phase').selectOption('3'); const t3 = await page.evaluate(() => r12.state().time);
      assert.ok(Math.abs(t3 - meta.phases[3].start) < 1e-6);
      await page.locator('#play').click(); await page.waitForFunction(t => r12.state().time > t + 2, t3); await page.locator('#play').click();
      assert.equal(await page.evaluate(() => r12.state().playing), false);
      await page.mouse.move(1100, 500);
      assert.deepEqual(errors, []); assert.deepEqual(network, []);
      const tri = await page.evaluate(() => r12.state().triangles);
      fs.writeFileSync(path.join(root, 'browser_validation.json'), JSON.stringify({
        status: 'PASS', html_sha256: hash, html_mb: +(html.length / 1e6).toFixed(2), triangles: tri, kinematics: kin, replay, framed,
        checks: ['page kinematics = poses_r12.body_poses on 125 grid poses', 'cycle modes place every body from the MuJoCo trace',
          'all parts framed in oblique/side/front at desktop and mobile size over the whole cycle', 'mode, phase, play/pause, sliders, x-ray, pin labels',
          'offline: no network requests, no page errors'], errors, network }, null, 1));
      console.log('PASS review', JSON.stringify({ kin, replay }));
    } else {
      const total = Math.round(meta.duration / SPEED * FPS), from = Number(process.argv[4] || 0), to = Math.min(total, Number(process.argv[5] || total));
      await page.evaluate(s => { r12.setMode('payload_150g'); r12.setSpeedLabel(s); r12.hideUI(true); }, SPEED);
      await page.waitForFunction(() => r12.state().mode === 'payload_150g' && r12.trace());
      const cdp = await context.newCDPSession(page), t0 = Date.now();
      for (let n = from; n < to; n++) {
        const t = Math.min(meta.duration, n * SPEED / FPS), c = cam(t, meta.duration);
        await page.evaluate(({ t, c }) => { r12.orbit(c.az, c.el, c.dist, new THREE.Vector3(c.tx, 0, c.tz)); r12.seek(t); }, { t, c });
        const s = await cdp.send('Page.captureScreenshot', { format: 'jpeg', quality: 90, fromSurface: true, optimizeForSpeed: true });
        fs.writeFileSync(path.join(out, `frame_${String(n).padStart(5, '0')}.jpg`), Buffer.from(s.data, 'base64'));
        if (n % 120 === 0) console.log(JSON.stringify({ frame: n, total, elapsed_s: Math.round((Date.now() - t0) / 1000) }));
      }
      assert.deepEqual(errors, []); assert.deepEqual(network, []);
      fs.writeFileSync(path.join(out, `render_${from}_${to}.json`), JSON.stringify({ fps: FPS, total, from, to, width: 1280, height: 720,
        html_sha256: hash, simulation: 'payload_150g', playback_speed: SPEED, duration: meta.duration, phases: meta.phases, errors, network }, null, 1));
      console.log('PASS frames', from, to);
    }
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });

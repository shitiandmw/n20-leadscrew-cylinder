'use strict';
// Video of the demonstration, rendered frame by frame from ../3D_preview.html (headless Chromium, software WebGL).
//   NODE_PATH=<dir with playwright> node render_video.cjs <frames dir> <worker> <workers>
// then:  ffmpeg -framerate 12 -i <frames dir>/f%05d.jpg -c:v libx264 -pix_fmt yuv420p -crf 20 ../images/complete_demo.mp4
// Story: the assembly order (9 steps), the work cycle (travel, dig, swing, dump, swing back, carry, travel back), exploded.
const fs = require('fs'), path = require('path');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const out = process.argv[2] || '/tmp/complete-frames', worker = +(process.argv[3] || 0), workers = +(process.argv[4] || 1);
const FPS = 12, BUILD_STEP = 1.8, BUILD_STEPS = 9, END = 3.5;

const lerp = (a, b, u) => a + (b - a) * u, sm = u => (u <= 0 ? 0 : u >= 1 ? 1 : u * u * (3 - 2 * u));
function camAt(k) {     // k: {az, el, dist, tx, ty, tz} -> position and target
  const a = k.az * Math.PI / 180, e = k.el * Math.PI / 180;
  return { pos: [k.tx + k.dist * Math.cos(e) * Math.cos(a), k.ty + k.dist * Math.cos(e) * Math.sin(a), k.tz + k.dist * Math.sin(e)], target: [k.tx, k.ty, k.tz] };
}
function blend(keys, t) {  // keys: [time, cam] sorted; 2 s smooth blend into each key
  let k = keys[0][1];
  for (let i = 1; i < keys.length; i++) {
    const [t1, c1] = keys[i];
    if (t >= t1 - 2) { const u = sm((t - (t1 - 2)) / 2); k = Object.fromEntries(Object.keys(c1).map(n => [n, lerp(k[n], c1[n], u)])); } else break;
  }
  return camAt(k);
}

(async () => {
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist'] });
  try {
    const page = await (await browser.newContext({ viewport: { width: 1280, height: 720 }, offline: true })).newPage();
    page.setDefaultTimeout(300000);
    await page.goto('file://' + path.join(root, '3D_preview.html'));
    await page.waitForFunction(() => window.demo && window.demo.state().ready, null, { timeout: 300000 });
    await page.addStyleTag({ content: 'header,aside{display:none!important}main{height:100vh!important}#hud{max-width:760px}#caption{font-size:14px;max-width:1000px}' });
    await page.waitForTimeout(500);
    const TL = await page.evaluate(() => demo.timeline), TOTAL = TL[TL.length - 1].v0 + TL[TL.length - 1].vd;
    const T_BUILD = BUILD_STEP * BUILD_STEPS, T_ALL = T_BUILD + TOTAL + END, n = Math.round(T_ALL * FPS);
    // camera keys over the work cycle (tau), by segment start
    const s = i => TL[i].v0;
    const keys = [[0, { az: 38, el: 22, dist: 1450, tx: 200, ty: 0, tz: 130 }],
      [s(1) + 1, { az: -62, el: 12, dist: 1550, tx: 330, ty: 0, tz: 70 }],
      [s(2) + 1, { az: 22, el: 30, dist: 1650, tx: 250, ty: 220, tz: 160 }],
      [s(4) + 2, { az: -25, el: 20, dist: 1550, tx: 260, ty: 0, tz: 120 }],
      [s(6) + 1, { az: 38, el: 22, dist: 1450, tx: 150, ty: 0, tz: 130 }]];
    for (let f = worker; f < n; f += workers) {
      const file = path.join(out, `f${String(f).padStart(5, '0')}.jpg`);
      if (fs.existsSync(file)) continue;
      const t = f / FPS;
      let cam;
      if (t < T_BUILD) {
        const k = Math.min(BUILD_STEPS - 1, Math.floor(t / BUILD_STEP)), u = Math.min(1, (t - k * BUILD_STEP) / (BUILD_STEP - 0.5));
        await page.evaluate(([k, u]) => { if (demo.state().mode !== 'build') demo.setMode('build'); demo.setBuild(k, u); }, [k, u]);
        cam = camAt({ az: lerp(55, 25, t / T_BUILD), el: 24, dist: 1250, tx: 90, ty: 0, tz: 140 });
      } else if (t < T_BUILD + TOTAL) {
        const tau = t - T_BUILD;
        await page.evaluate(tau => { if (demo.state().mode !== 'demo') demo.setMode('demo'); demo.seek(tau); }, tau);
        cam = blend(keys, tau);
      } else {
        const u = sm((t - T_BUILD - TOTAL) / 2.5);
        await page.evaluate(([u, total]) => { if (demo.state().view !== 'exploded') { demo.seek(total); demo.setView('exploded'); } demo.setExplode(u); }, [u, TOTAL]);
        cam = camAt({ az: lerp(38, 48, u), el: lerp(22, 30, u), dist: lerp(1450, 1850, u), tx: 80, ty: 0, tz: lerp(130, 230, u) });
      }
      await page.evaluate(c => { demo.setCamera(c.pos, c.target); demo.render(); }, cam);
      await page.screenshot({ path: file, type: 'jpeg', quality: 90 });
      if (f % 50 < workers) console.log('frame', f, '/', n);
    }
  } finally { await browser.close(); }
})();

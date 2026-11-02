// Browser check of 3D_preview.html and frames for the assembly video (Playwright, headless Chromium).
//   node source/assembly_video.cjs check                 -> viewer_check.json (every mode, every length)
//   node source/assembly_video.cjs frames --variant S --fps 25 --from 0 --to 500 --out DIR
//        -> DIR/f_00000.jpg ...: the record layout at 1280 x 720 CSS pixels, rendered at 1.5x (1920 x 1080)
//           without MSAA or shadows (3D_preview.html#record); scale them down to 1280 x 720 when encoding
// NODE_PATH must reach a playwright install. Encode the frames with ffmpeg (README.md, Rebuild).
'use strict';
const path = require('path');
const fs = require('fs');
const {chromium} = require('playwright');

const ROOT = path.resolve(__dirname, '..');
const argv = process.argv.slice(2);
const cmd = argv[0];
const opt = (k, d) => { const i = argv.indexOf(`--${k}`); return i < 0 ? d : argv[i + 1]; };

async function open(record) {
  const browser = await chromium.launch({args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader']});
  const page = await browser.newPage({viewport: {width: 1280, height: 720}, deviceScaleFactor: record ? 1.5 : 1});
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto(`file://${path.join(ROOT, '3D_preview.html')}${record ? '#record' : ''}`);
  await page.waitForFunction(() => window.viewerReady === true, null, {timeout: 180000});
  return {browser, page, errors};
}

async function check() {
  const {browser, page, errors} = await open();
  const variants = await page.evaluate(() => [...document.querySelectorAll('[data-variant]')].map(b => b.dataset.variant));
  const report = {checked: new Date().toISOString().slice(0, 10), variants: {}, errors};
  for (const v of variants) {
    report.variants[v] = await page.evaluate(v => {
      const A = window.actuator, r = {};
      A.setVariant(v);
      for (const m of ['exterior', 'section', 'internal', 'board', 'core', 'printed']) A.setMode(m);
      r.printed_labels = [...document.querySelectorAll('.plabel.printed')].filter(e => e.style.display !== 'none').length;
      A.select({type: 'mesh', id: '03_rear_cap'});
      r.print_card = document.getElementById('card').innerText.includes('flat front face down');
      A.select(null);
      A.setMode('assembly');
      const steps = A.assembly.steps();
      r.steps = steps.map(s => s.id);
      r.duration_s = Math.round(A.assembly.state().total * 10) / 10;
      // drivers show while their screws go in, and only then
      const at = (id, f) => { const s = steps.find(x => x.id === id); return A.assembly.seek(s.start + s.dur * f); };
      const tools = st => st.visible.filter(n => n.startsWith('tool_'));
      r.motor_screw_driver = tools(at('motor_screws', 0.3));
      r.rear_screw_driver = tools(at('rear_screws', 0.3));
      r.board_step_wires = at('board', 0.5).tubes;
      r.first_step_parts = at('body', 0.5).visible;
      const end = A.assembly.seek(1e9), shown = new Set(end.visible);
      r.end_tools = tools(end).length;
      r.end_tubes = end.tubes;
      // assembled: every printed, hardware and board part is in place (the sleeve and wires as tubes)
      const want = A.items().filter(i => ['printed', 'hardware', 'board'].includes(i.kind) && i.name !== 'cable_sleeve');
      r.end_missing = want.filter(i => !shown.has(i.name)).map(i => i.name);
      r.end_extra = end.visible.filter(n => !want.some(i => i.name === n));
      A.setMode('exterior');
      r.extend_stops = A.simulate(1, 120).u2 === true;
      r.pass = r.printed_labels === 6 && r.print_card && r.motor_screw_driver.length === 2 && r.rear_screw_driver.length === 2
        && r.board_step_wires.length === 4 && r.end_tools === 0 && r.end_tubes.length === 5 && !r.end_missing.length
        && !r.end_extra.length && r.extend_stops;
      return r;
    }, v);
  }
  await browser.close();
  report.pass = !errors.length && Object.values(report.variants).every(r => r.pass);
  return report;
}

async function frames() {
  const {browser, page, errors} = await open(true);
  const variant = opt('variant', 'S'), fps = Number(opt('fps', 25)), out = path.resolve(opt('out', '/tmp/frames'));
  fs.mkdirSync(out, {recursive: true});
  const total = await page.evaluate(v => {
    actuator.setVariant(v);
    actuator.setMode('assembly');
    actuator.assembly.record(true);
    return actuator.assembly.state().total;
  }, variant);
  const n = Math.ceil(total * fps) + 1;
  const from = Number(opt('from', 0)), to = Math.min(Number(opt('to', n)), n);
  const t0 = Date.now();
  for (let i = from; i < to; i++) {
    await page.evaluate(t => { actuator.assembly.seek(t); }, Math.min(i / fps, total));
    await page.screenshot({path: path.join(out, `f_${String(i).padStart(5, '0')}.jpg`), type: 'jpeg', quality: 92});
  }
  await browser.close();
  console.log(JSON.stringify({variant, fps, frames_total: n, from, to, seconds: Math.round((Date.now() - t0) / 1000), errors}));
}

(async () => {
  if (cmd === 'check') {
    const report = await check();
    fs.writeFileSync(path.join(ROOT, 'viewer_check.json'), JSON.stringify(report, null, 1) + '\n');
    console.log(JSON.stringify(report));
  } else if (cmd === 'frames') {
    await frames();
  } else {
    console.error('usage: assembly_video.cjs check | frames --variant S --fps 25 [--from N --to M] --out DIR');
    process.exit(2);
  }
})().catch(e => { console.error(e); process.exit(1); });

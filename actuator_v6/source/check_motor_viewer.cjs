// Verify the actual offline V6 viewer, especially its (z,y,-x) shaft pivots.
'use strict';
const fs = require('fs');
const path = require('path');
const assert = require('assert/strict');
const {chromium} = require('playwright');
const ROOT = path.resolve(__dirname, '..');
(async () => {
  const browser = await chromium.launch({args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader']});
  try {
    const page = await browser.newPage({viewport: {width: 1280, height: 900}});
    const errors = [];
    page.on('pageerror', e => errors.push(String(e)));
    await page.goto('file://' + path.join(ROOT, '3D_preview.html') + '#record');
    await page.waitForFunction(() => window.viewerReady, null, {timeout: 120000});
    const results = await page.evaluate(() => {
      const out = {};
      const A = window.actuator;
      for (const variant of ['S', 'U60', 'L']) {
        A.setVariant(variant);
        A.setMode('exterior');
        document.getElementById('speed').value = '5';
        A.setMode('gears');
        const slow = document.getElementById('speed').value === '0.02';
        let maxPivotError = 0, maxRotationError = 0, poses = 0;
        for (const travel of [0, .001, .004, .125, 20.00031, .125, .004, .001, 0]) {
          A.setTravel(travel);
          const transforms = A.gearTransforms();
          if (transforms.length !== 5) throw Error('Missing motor rotors');
          for (const t of transforms) {
            const k = t.rotation, [x, y, z] = k.axis_origin_mm;
            const q = new THREE.Quaternion(...t.quaternion);
            const pivot = new THREE.Vector3(z-t.dz, y, -x).applyQuaternion(q).add(new THREE.Vector3(...t.position));
            maxPivotError = Math.max(maxPivotError, pivot.distanceTo(new THREE.Vector3(z-t.centre, y, -x)));
            const angle = -travel / .5 * 2*Math.PI * k.angle_per_output_rad;
            const expected = new THREE.Quaternion(Math.sin(angle/2), 0, 0, Math.cos(angle/2));
            maxRotationError = Math.max(maxRotationError, 1-Math.abs(q.dot(expected)));
            poses++;
          }
        }
        A.setMode('assembly');
        const end = A.assembly.seek(1e9);
        const missing = A.items().filter(i => i.name.startsWith('motor_')).filter(i => !end.visible.includes(i.name));
        const restoredSpeed = document.getElementById('speed').value === '5';
        A.setMode('gears');
        A.setTravel(.001);
        const restoredRotors = A.gearTransforms().every(t => t.position.every(Number.isFinite));
        out[variant] = {poses, maxPivotError, maxRotationError, slow, restoredSpeed, missingMotorParts: missing, restoredRotors};
      }
      return out;
    });
    for (const r of Object.values(results)) {
      assert(r.maxPivotError < 1e-9 && r.maxRotationError < 1e-12);
      assert(r.slow && r.restoredSpeed && r.restoredRotors && r.missingMotorParts.length === 0);
    }
    await page.evaluate(() => { actuator.setVariant('S'); actuator.setMode('gears'); actuator.setTravel(0); actuator.select(null); });
    await page.screenshot({path: path.join(ROOT, 'images/motor_gears.png'), timeout: 120000});
    assert.equal(errors.length, 0, errors.join('\n'));
    fs.writeFileSync(path.join(ROOT, 'motor_viewer_check.json'), JSON.stringify({passed: true, results, errors}, null, 2)+'\n');
    console.log(JSON.stringify({passed: true, results, errors}));
  } finally {
    await browser.close();
  }
})().catch(e => {console.error(e); process.exitCode=1;});

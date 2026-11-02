// Finite offline browser verification. No HTTP server or persistent process.
const { chromium } = require('playwright');
const path = require('node:path');
const fs = require('node:fs');
const { pathToFileURL } = require('node:url');

(async () => {
  const root = path.resolve(__dirname, '..');
  const browser = await chromium.launch({ executablePath: process.env.BROWSER_PATH, headless: true,
    args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const errors = [], checks = {};
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(pathToFileURL(path.join(root, '3D_preview.html')).href);
    await page.waitForFunction(() => window.trialReady, undefined, { timeout: 90000 });
    checks.loaded_offline = await page.evaluate(() => window.trialState.mode === 'trial' && window.trialState.visible > 10);
    await page.screenshot({ path: path.join(root, 'images', 'viewer_desktop.png'), fullPage: true });
    await page.getByRole('button', { name: 'Original', exact: true }).click();
    checks.original_toggle = await page.evaluate(() => window.trialState.mode === 'original');
    await page.getByRole('button', { name: 'Compact revision', exact: true }).click();
    await page.locator('#stroke').fill('60');
    checks.full_stroke = (await page.locator('#status').textContent()).includes('200 mm between pins');
    await page.getByRole('button', { name: 'Nut detail', exact: true }).click();
    checks.nut_detail = await page.evaluate(() => window.trialState.visible === 6 && document.querySelector('#stroke').disabled);
    await page.getByRole('button', { name: 'Reset view', exact: true }).click();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    checks.mobile_no_horizontal_overflow = await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
    await page.screenshot({ path: path.join(root, 'images', 'viewer_mobile.png'), fullPage: true });
    checks.no_browser_errors = errors.length === 0;
    const report = { checks, all_passed: Object.values(checks).every(Boolean), errors };
    fs.writeFileSync(path.join(root, 'browser_validation.json'), JSON.stringify(report, null, 2) + '\n');
    console.log(JSON.stringify(report, null, 2));
    if (!report.all_passed) process.exitCode = 1;
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });

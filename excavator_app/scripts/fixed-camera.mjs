// Fixed cameras and simulated time for a page that plays recorded frames, for the
// scripts that take pictures of a dig. The client is changed only as it is served:
// nothing here is in the game.

// client/scene.js with a camera that can be put anywhere (window.__aim), a clock
// that follows the frames instead of the wall, and drawing only when asked. Throws
// if the scene has changed too much to be patched.
export function fixCamera(code) {
  const edits = [
    [
      "let dirty = true;",
      "let dirty = true; window.__redraw = () => { dirty = true; };",
    ],
    [
      "sand.setTime(now / 1000);",
      "sand.setTime((renderTick ?? 0) / TICK_RATE);",
    ],
    [
      "if (grains.stepGrains(dt)) dirty = true;",
      `const played = (renderTick ?? 0) - (window.__grainsAt ?? 0);
      window.__grainsAt = renderTick ?? 0;
      if (played > 0 && grains.stepGrains(Math.min(0.1, played / TICK_RATE))) dirty = true;`,
    ],
    [
      "const distance = camera.position.distanceTo(orbit.target) * boomLength,",
      `const distance = window.__aim
        ? Math.hypot(...window.__aim.from.map((v, i) => v - window.__aim.at[i]))
        : camera.position.distanceTo(orbit.target) * boomLength,`,
    ],
    [
      "if (sand.updateDetail(camera)) dirty = true;",
      `if (window.__aim) camera.position.set(...window.__aim.from);
      if (sand.updateDetail(camera)) dirty = true;`,
    ],
    [
      "renderer.render(scene, camera);",
      `if (window.__aim) {
        camera.position.set(...window.__aim.from);
        camera.lookAt(...window.__aim.at);
      }
      if (window.__aim) {
        renderer.render(scene, camera);
        window.__drawn = (window.__drawn ?? 0) + 1;
      }`,
    ],
  ];
  for (const [from, to] of edits) {
    if (!code.includes(from))
      throw new Error(`client/scene.js no longer has: ${from}`);
    code = code.replace(from, to);
  }
  return code;
}

const wait = (ms) => new Promise((done) => setTimeout(done, ms));

// A picture of the page from a camera at `from` looking at `at` (mm, in the world).
// Drawn twice: the first lets the machine and the sand choose their detail. The
// page goes back to playing without drawing afterwards. Software rendering can
// take many seconds a frame, so every wait is long.
export async function takePicture(page, from, at, options) {
  const drawn = () => page.evaluate(() => window.__drawn ?? 0),
    draw = async () => {
      const before = await drawn();
      await page.evaluate(() => window.__redraw());
      await page.waitForFunction((n) => window.__drawn >= n, before + 1, {
        timeout: 240000,
      });
    };
  await page.evaluate(
    ([from, at]) => {
      window.__aim = { from, at };
    },
    [from, at],
  );
  await draw();
  await wait(400);
  await draw();
  const image = await page.screenshot({ timeout: 240000, ...options });
  await page.evaluate(() => {
    window.__aim = null;
  });
  return image;
}

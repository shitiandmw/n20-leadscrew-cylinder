// Deterministic visual check using actual scoop/pour snapshots. The temporary
// Vite server and browser are always closed; no background service is left.
import assert from "node:assert/strict";
import { mkdir, readFile } from "node:fs/promises";
import { gunzipSync } from "node:zlib";
import { chromium } from "@playwright/test";
import { createServer } from "vite";
import { SandSimulation } from "../server/physics.js";
import { neutral } from "../shared/world.js";

const simulation = new SandSimulation();
simulation.speed = 1;
const tiles = new Map(),
  shots = [];
let history = [];
function packet() {
  const origin = new Int32Array(3),
    grains = simulation.packGrains(origin);
  return {
    tick: simulation.tick,
    machine: structuredClone(simulation.machine),
    origin: [...origin],
    grains: [...grains],
    tiles: [],
  };
}
function run(seconds, axes = {}) {
  simulation.axes = { ...neutral(), ...axes };
  const steps = Math.round(seconds * 30);
  history = [];
  for (let i = 0; i < steps; i++) {
    if (i >= steps - 3) history.push(packet());
    simulation.step();
  }
}
function capture(name) {
  const origin = new Int32Array(3),
    grains = simulation.packGrains(origin);
  const changed = simulation.terrain.quantize(tiles);
  shots.push({
    name,
    history,
    stats: { ...simulation.stats },
    frame: {
      tick: simulation.tick,
      machine: structuredClone(simulation.machine),
      origin: [...origin],
      grains: [...grains],
      tiles: changed.map((index) => ({
        index,
        heights: [...tiles.get(index)],
      })),
    },
  });
}
capture("bed");
run(1.2, { boom: -1 });
run(1.6, { stick: 1 });
run(3.5, { bucket: 1 });
capture("scoop");
run(2, { boom: 1 });
capture("lift");
run(1.5, { slew: 1 });
run(1.5, { bucket: -1 });
capture("pour-start");
run(0.7, { bucket: -1 });
capture("pour");
run(0.5, { bucket: -1 });
capture("pour-late");
run(1.3, { bucket: -1 });
run(1.5);
capture("settled");

const model = gunzipSync(
  await readFile(new URL("../public/model.json.gz", import.meta.url)),
);
const servePreview = (req, res, next) => {
  if (req.url === "/model.json") {
    res.setHeader("Content-Type", "application/json");
    res.end(model);
  } else if (req.url === "/sand-check") {
    res.setHeader("Content-Type", "text/html");
    res.end(`<!doctype html><html><head><link rel="icon" href="data:,"><style>
      html,body{margin:0;background:#ddd}#stage{width:100vw;height:100vh;overflow:hidden}
      </style></head><body><div id="stage"></div><script type="module">
      import { createScene } from '/client/scene.js';
      window.preview = await createScene(document.querySelector('#stage'), () => {});
      preview.view('bucket');
      </script></body></html>`);
  } else next();
};
const server = await createServer({
  configFile: false,
  server: { host: "127.0.0.1", port: 0, watch: null },
  logLevel: "warn",
  plugins: [
    {
      name: "sand-preview",
      configureServer(server) {
        server.middlewares.use(servePreview);
      },
    },
  ],
});

let browser;
try {
  await server.listen();
  const origin = `http://127.0.0.1:${server.httpServer.address().port}`;
  browser = await chromium.launch({
    executablePath: process.env.BROWSER_PATH || undefined,
    args: [
      "--no-sandbox",
      "--use-gl=angle",
      "--use-angle=swiftshader",
      "--enable-unsafe-swiftshader",
    ],
  });
  await mkdir("test-results/sand", { recursive: true });
  const errors = [];
  for (const mobile of [false, true]) {
    const context = await browser.newContext({
      viewport: mobile
        ? { width: 800, height: 600 }
        : { width: 1280, height: 960 },
      hasTouch: mobile,
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();
    page.on("pageerror", (error) => {
      errors.push(error.message);
      console.error(error.message);
    });
    page.on("console", (message) => {
      if (
        message.type() === "error" ||
        /Geometry buffers too small/.test(message.text())
      )
        errors.push(message.text());
    });
    await page.goto(`${origin}/sand-check`);
    await page.waitForFunction(() => window.preview, null, { timeout: 90000 });
    for (const shot of shots) {
      await page.evaluate(
        (frames) => {
          for (const frame of frames) {
            const f = {
              ...frame,
              grains: Int16Array.from(frame.grains),
              tiles: frame.tiles.map((t) => ({
                index: t.index,
                heights: Uint16Array.from(t.heights),
              })),
            };
            preview.pushFrame(f);
          }
        },
        [...shot.history, shot.frame],
      );
      await page.waitForFunction(
        (tick) => preview.telemetry().tick >= tick,
        shot.frame.tick,
        { timeout: 45000 },
      );
      const graphics = await page.evaluate(() => preview.telemetry());
      assert.ok(Number.isFinite(graphics.sandUpdateMs));
      if (shot.name === "lift")
        assert.ok(graphics.loadTriangles > 100, "carried load reconstructs");
      if (shot.name === "bed") assert.equal(graphics.loadTriangles, 0);
      if (shot.name === "settled") assert.equal(graphics.loadTriangles, 0);
      if (shot.name === "pour")
        assert.ok(
          graphics.flyingGrains > 0,
          "flow keeps its velocity when the display skips ahead to the final snapshot",
        );
      console.log(
        mobile ? "touch" : "desktop",
        shot.name,
        JSON.stringify({
          load: shot.stats.load,
          grains: graphics.grains,
          flying: graphics.flyingGrains,
          triangles: graphics.loadTriangles,
          updateMs: graphics.sandUpdateMs,
        }),
      );
      await page.screenshot({
        path: `test-results/sand/${mobile ? "touch" : "desktop"}-${shot.name}.png`,
      });
    }
    await page.evaluate(() => preview.newRoom());
    assert.equal(await page.evaluate(() => preview.telemetry().grains), 0);
    assert.equal(
      await page.evaluate(() => preview.telemetry().loadTriangles),
      0,
    );
    await context.close();
  }
  assert.deepEqual(errors, [], "no browser or shader errors");
} finally {
  await browser?.close();
  await server.close();
}

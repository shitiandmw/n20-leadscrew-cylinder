// Renders the same dig from two builds with the same camera, and lays the frames
// out in rows, to see what a change to the sand did. Finite: the temporary servers
// and browsers are always closed.
// Usage: BROWSER_PATH=/path/to/chrome node scripts/capture_comparison.mjs \
//          <older build's folder> [output.png] [what was before] [what is after]
// The older folder is a checkout of excavator_app with its own node_modules. It only
// has to run the same way: server/physics.js, shared/protocol.js and client/scene.js.
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { gunzipSync } from "node:zlib";
import { chromium } from "@playwright/test";
import { createServer } from "vite";

const here = fileURLToPath(new URL("..", import.meta.url));
const [
  olderBuild,
  output = "docs/height-field-before-after.png",
  beforeNote = "about 2,000 grains, solved each tick; surface rebuilt from them",
  afterNote = "height field in the bucket, drawn like the ground",
] = process.argv.slice(2);
if (!olderBuild) {
  console.error("Usage: capture_comparison.mjs <older build's folder> [output.png]");
  process.exit(1);
}
const launch = () =>
  chromium.launch({
    executablePath: process.env.BROWSER_PATH || undefined,
    args: [
      "--no-sandbox",
      "--use-gl=angle",
      "--use-angle=swiftshader",
      "--enable-unsafe-swiftshader",
    ],
  });

// The standard cycle, with a stop wherever a picture is wanted.
const CYCLE = [
  [1.2, { boom: -1 }],
  [1.6, { stick: 1 }],
  [2.4, { bucket: 1 }, "curl"],
  [1.1, { bucket: 1 }],
  [2, { boom: 1 }, "lift"],
  [1.5, { slew: 1 }],
  [1.5, { bucket: -1 }, "start"],
  [0.7, { bucket: -1 }, "pour"],
];
const SHOTS = [
  ["curl", "Curling in the sand"],
  ["lift", "Lifted"],
  ["start", "Starting to pour"],
  ["pour", "Pouring"],
];
const VIEW = { width: 960, height: 720 },
  CROP = { x: 140, y: 240, width: 560, height: 480 },
  SHRINK = 1 / 1.4;

// What a browser would have got at each stop, as plain arrays for the page.
async function simulate(root) {
  const { SandSimulation } = await import(resolve(root, "server/physics.js")),
    { neutral } = await import(resolve(root, "shared/world.js")),
    { decodeFrame, encodeFrame } = await import(resolve(root, "shared/protocol.js"));
  const simulation = new SandSimulation();
  simulation.speed = 1;
  const store = new Map();
  const packet = (tiles = []) => {
    const frame = decodeFrame(
      encodeFrame({
        tick: simulation.tick,
        machines: [
          {
            id: 1,
            ...simulation.machine,
            load: simulation.vehicles[0].load?.pack() ?? null,
          },
        ],
        ...simulation.packGrains(),
        tileData: store,
        tiles,
      }),
    );
    return {
      tick: frame.tick,
      machines: frame.machines.map((machine) => ({
        ...machine,
        load: machine.load ? [...machine.load] : null,
      })),
      slots: [...frame.slots],
      holders: [...frame.holders],
      positions: [...frame.positions],
      tiles: frame.tiles.map(({ index, heights }) => ({
        index,
        heights: [...heights],
      })),
    };
  };
  const stops = [{ frames: [packet(simulation.terrain.quantize(store))] }];
  for (const [seconds, axes, name] of CYCLE) {
    simulation.axes = { ...neutral(), ...axes };
    const steps = Math.round(seconds * 30),
      recent = [];
    for (let i = 0; i < steps; i++) {
      if (i >= steps - 3) recent.push(packet());
      simulation.step();
    }
    recent.push(packet(simulation.terrain.quantize(store)));
    stops.push({ name, frames: recent });
  }
  return stops;
}

// The stops of a build, seen from the machine's side, looking into the bucket.
async function render(root) {
  const stops = await simulate(root),
    model = gunzipSync(await readFile(resolve(root, "public/model.json.gz")));
  const server = await createServer({
    root,
    configFile: false,
    server: { host: "127.0.0.1", port: 0, watch: null },
    logLevel: "warn",
    plugins: [
      {
        name: "comparison",
        configureServer(vite) {
          vite.middlewares.use((req, res, next) => {
            if (req.url === "/model.json") {
              res.setHeader("Content-Type", "application/json");
              res.end(model);
            } else if (req.url === "/comparison") {
              res.setHeader("Content-Type", "text/html");
              res.end(`<!doctype html><html><head><link rel="icon" href="data:,">
                <style>html,body{margin:0}#stage{width:100vw;height:100vh;overflow:hidden}</style>
                </head><body><div id="stage"></div><script type="module">
                import { createScene } from '/client/scene.js';
                window.preview = await createScene(document.querySelector('#stage'), () => {});
                preview.view('bucket');
                </script></body></html>`);
            } else next();
          });
        },
      },
    ],
  });
  const browser = await launch(),
    pictures = {};
  try {
    await server.listen();
    const page = await browser.newPage({ viewport: VIEW, deviceScaleFactor: 1 });
    page.on("pageerror", (error) => console.error(error.message));
    await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/comparison`);
    await page.waitForFunction(() => window.preview, null, { timeout: 120000 });
    let placed = false;
    for (const { name, frames } of stops) {
      await page.evaluate((list) => {
        for (const frame of list)
          preview.pushFrame({
            ...frame,
            machines: frame.machines.map((machine) => ({
              ...machine,
              load: machine.load && Uint16Array.from(machine.load),
            })),
            slots: Uint16Array.from(frame.slots),
            holders: Uint16Array.from(frame.holders),
            positions: Float32Array.from(frame.positions),
            tiles: frame.tiles.map(({ index, heights }) => ({
              index,
              heights: Uint16Array.from(heights),
            })),
          });
      }, frames);
      await page.waitForFunction(
        (tick) => preview.telemetry().tick >= tick,
        frames.at(-1).tick,
        { timeout: 90000 },
      );
      if (!placed) {
        placed = true;
        await page.mouse.move(480, 200);
        await page.mouse.down();
        await page.mouse.move(570, 250, { steps: 4 });
        await page.mouse.up();
        for (let i = 0; i < 8; i++) {
          await page.mouse.wheel(0, -240);
          await page.waitForTimeout(150);
        }
      }
      await page.waitForTimeout(2500);
      if (name) pictures[name] = await page.screenshot({ clip: CROP });
    }
  } finally {
    await browser.close();
    await server.close();
  }
  return pictures;
}

const older = await render(resolve(olderBuild)),
  newer = await render(here);
const picture = (image) =>
  `<img width="${CROP.width * SHRINK}" height="${CROP.height * SHRINK}" src="data:image/png;base64,${image.toString("base64")}">`;
const html = `<!doctype html><style>
  body{margin:0;background:#1d1f22;color:#eee;font:600 22px system-ui,sans-serif;width:max-content;padding:14px}
  .grid{display:grid;grid-template-columns:150px repeat(${SHOTS.length},auto);gap:8px;align-items:center}
  .title{text-align:center;font-size:20px;padding:4px 0}
  small{display:block;font-weight:400;font-size:15px;color:#bbb;margin-top:6px}
  </style><div class="grid"><div></div>
  ${SHOTS.map(([, title]) => `<div class="title">${title}</div>`).join("")}
  <div>Before<small>${beforeNote}</small></div>
  ${SHOTS.map(([name]) => picture(older[name])).join("")}
  <div>After<small>${afterNote}</small></div>
  ${SHOTS.map(([name]) => picture(newer[name])).join("")}
  </div>`;
const browser = await launch();
try {
  const page = await browser.newPage({ viewport: { width: 1900, height: 900 } });
  await page.setContent(html, { waitUntil: "load" });
  await page.locator("body").screenshot({ path: output });
  console.log(`Wrote ${output}`);
} finally {
  await browser.close();
}

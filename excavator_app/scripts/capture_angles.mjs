// Still pictures of a dig and a pour from fixed cameras, to judge how the sand looks.
// The real client plays the real simulation at its real pace, drawing only for the
// pictures, so drying sand and loose grains are where they would be for a player.
// Finite: the temporary server and browser are always closed.
// Usage: BROWSER_PATH=/path/to/chrome node scripts/capture_angles.mjs [folder]
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { gunzipSync } from "node:zlib";
import { chromium } from "@playwright/test";
import { createServer } from "vite";
import { SandSimulation } from "../server/physics.js";
import { neutral } from "../shared/world.js";
import { SCOOP, CARRY, POUR } from "../shared/scoop.js";
import { decodeFrame, encodeFrame } from "../shared/protocol.js";
import { fixCamera, takePicture } from "./fixed-camera.mjs";

const root = fileURLToPath(new URL("..", import.meta.url)),
  folder = process.argv[2]
    ? resolve(process.argv[2])
    : resolve(root, "docs/angles"),
  VIEW = { width: 1600, height: 1000 };

// The standard dig and pour, each part of it under a name.
const [open, reach, lower, crowd, curl] = SCOOP,
  [lift, swing] = CARRY,
  CYCLE = [
    [...open, "open"],
    [...reach, "reach"],
    [...lower, "lower"],
    [...crowd, "crowd"],
    [...curl, "curl"],
    [...lift, "lift"],
    [...swing, "swing"],
    [...POUR[0], "pour"],
    [1.5, {}, "rest"],
  ];
// Each picture: the part of the cycle it belongs to and the seconds from that
// part's end (negative: before it), then the camera and what it looks at, in mm
// from the bed under the bucket at that moment. The machine stands towards -x, and
// the sun is on the -x, -y side. The parts keep their names when their times
// change, so the pictures stay where they belong.
const SHOTS = [
  [
    "01-digging-front",
    "Digging, from in front",
    ["crowd", -0.6],
    [300, -210, 240],
    [-20, 0, 15],
  ],
  [
    "02-digging-far-side",
    "Digging, from the far side",
    ["crowd", -0.6],
    [30, 280, 150],
    [0, 0, 15],
  ],
  [
    "03-full-bucket",
    "Heaped bucket, curled level in the pit",
    ["curl", 0],
    [-90, -250, 130],
    [-20, 0, 20],
  ],
  [
    "04-lifting",
    "Lifting out of the pit",
    ["lift", -1.6],
    [-300, -260, 200],
    [0, 0, 150],
  ],
  [
    "05-carrying",
    "Carried over the pour zone, heaped",
    ["swing", 0],
    [148, -205, 253],
    [0, 0, 208],
  ],
  [
    "06-pouring-side",
    "Pouring, from the side",
    ["pour", -2.9],
    [-190, -330, 150],
    [0, 0, 105],
  ],
  [
    "07-pouring-low",
    "Pouring, from low down",
    ["pour", -2.9],
    [170, -250, 22],
    [0, 0, 120],
  ],
  [
    "08-pouring-above",
    "Pouring, from above",
    ["pour", -2.9],
    [300, -300, 560],
    [0, 0, 40],
  ],
  [
    "09-finished",
    "Finished: the machine, the pit and the pile",
    ["rest", 0],
    [-300, -1250, 720],
    [-110, -250, 40],
  ],
];

const simulation = new SandSimulation();
simulation.speed = 1;
const store = new Map();
function packet(tiles = []) {
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
}
const frames = [packet(simulation.terrain.quantize(store))],
  anchors = [[0, 0, 0]],
  surface = [0, 0, 0],
  // The tick at which each part of the cycle ends.
  ends = {};
for (const [seconds, axes, part] of CYCLE) {
  simulation.axes = { ...neutral(), ...axes };
  for (let i = 0; i < Math.round(seconds * 30); i++) {
    simulation.step();
    frames.push(packet(simulation.terrain.quantize(store)));
    const [x, y] = simulation.vehicles[0].frame.centre;
    simulation.terrain.sample(x, y, surface);
    anchors.push([x, y, surface[0]]);
  }
  ends[part] = simulation.tick;
}
const tickOf = ([part, seconds]) => ends[part] + Math.round(seconds * 30);

// The client gets fixed cameras and simulated time as it is served.
const model = gunzipSync(await readFile(resolve(root, "public/model.json.gz")));
const server = await createServer({
  root,
  configFile: false,
  server: { host: "127.0.0.1", port: 0, watch: null },
  logLevel: "warn",
  plugins: [
    {
      name: "angles",
      transform(code, id) {
        return id.endsWith("client/scene.js") ? fixCamera(code) : null;
      },
      configureServer(vite) {
        vite.middlewares.use((req, res, next) => {
          if (req.url === "/model.json") {
            res.setHeader("Content-Type", "application/json");
            res.end(model);
          } else if (req.url === "/angles") {
            res.setHeader("Content-Type", "text/html");
            res.end(`<!doctype html><html><head><link rel="icon" href="data:,">
              <style>html,body{margin:0}#stage{width:100vw;height:100vh;overflow:hidden}</style>
              </head><body><div id="stage"></div><script type="module">
              import { createScene } from '/client/scene.js';
              window.preview = await createScene(document.querySelector('#stage'), () => {});
              </script></body></html>`);
          } else next();
        });
      },
    },
  ],
});
const browser = await chromium.launch({
  executablePath: process.env.BROWSER_PATH || undefined,
  args: [
    "--no-sandbox",
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
  ],
});
const wait = (ms) => new Promise((done) => setTimeout(done, ms));
try {
  await server.listen();
  await mkdir(folder, { recursive: true });
  const page = await browser.newPage({ viewport: VIEW, deviceScaleFactor: 1 }),
    errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(
    `http://127.0.0.1:${server.httpServer.address().port}/angles`,
  );
  await page.waitForFunction(() => window.preview, null, { timeout: 240000 });
  const push = (frame) =>
    page.evaluate((f) => {
      preview.pushFrame({
        ...f,
        machines: f.machines.map((machine) => ({
          ...machine,
          load: machine.load && Uint16Array.from(machine.load),
        })),
        slots: Uint16Array.from(f.slots),
        holders: Uint16Array.from(f.holders),
        positions: Float32Array.from(f.positions),
        tiles: f.tiles.map(({ index, heights }) => ({
          index,
          heights: Uint16Array.from(heights),
        })),
      });
    }, frame);
  let sent = 0;
  const pictures = [];
  for (const [name, title, when, from, at] of SHOTS) {
    const tick = tickOf(when);
    // At the pace of the simulation, a little past the tick for the playback delay.
    while (sent < Math.min(tick + 3, frames.length)) {
      const start = Date.now();
      await push(frames[sent++]);
      await wait(Math.max(0, 1000 / 30 - (Date.now() - start)));
    }
    await page.waitForFunction((t) => preview.telemetry().tick >= t, tick, {
      timeout: 240000,
    });
    const anchor = anchors[tick],
      place = (offset) => offset.map((value, i) => anchor[i] + value),
      path = resolve(folder, `${name}.jpg`);
    await takePicture(page, place(from), place(at), {
      path,
      type: "jpeg",
      quality: 88,
    });
    pictures.push([title, path]);
    console.log("wrote", name);
  }
  if (errors.length) throw new Error(`page errors: ${errors.join("; ")}`);
  // All of them on one sheet.
  const images = await Promise.all(
    pictures.map(async ([title, path]) => [
      title,
      (await readFile(path)).toString("base64"),
    ]),
  );
  const sheet = await browser.newPage({
    viewport: { width: 2420, height: 1600 },
  });
  await sheet.setContent(
    `<!doctype html><style>
    body{margin:0;background:#16181c;color:#fff;font:600 24px system-ui,sans-serif}
    #grid{display:grid;grid-template-columns:repeat(3,800px);gap:6px;width:max-content;padding:6px}
    figure{position:relative;margin:0}
    img{display:block;width:800px;height:500px}
    figcaption{position:absolute;left:12px;top:8px;text-shadow:0 0 5px #000,0 0 2px #000}
    </style><div id="grid">${images
      .map(
        ([title, data]) =>
          `<figure><img src="data:image/jpeg;base64,${data}"><figcaption>${title}</figcaption></figure>`,
      )
      .join("")}</div>`,
    { waitUntil: "load" },
  );
  const path = resolve(folder, "all-angles.jpg");
  await writeFile(
    path,
    await sheet.locator("#grid").screenshot({ type: "jpeg", quality: 88 }),
  );
  console.log("wrote", path);
} finally {
  await browser.close();
  await server.close();
}

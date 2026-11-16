// Renders the standard dig from two builds with the same cameras, and lays the
// frames out in rows, to see what a change to the sand did. Each build digs the way
// its own shared/scoop.js says, as its README tells a player to. Finite: the
// temporary servers and browsers are always closed.
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
import { fixCamera, takePicture } from "./fixed-camera.mjs";

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

// A build's standard cycle, with a stop wherever a picture is wanted.
const cycleOf = ({ SCOOP, CARRY }) => [
  ...SCOOP.slice(0, 4),
  [...SCOOP[4], "curl"],
  [...CARRY[0], "lift"],
  CARRY[1],
  [1.5, { bucket: -1 }, "start"],
  [1.2, { bucket: -1 }, "pour"],
];
// Each picture: its stop, its title, and where the camera stands and looks, in mm
// from the middle of the bucket: along the arm away from the machine, to the arm's
// left, and up. All four look at the bucket side-on, from the arm's right, so what
// stands above its rims shows.
const SHOTS = [
  ["curl", "Curled, in the pit", [-60, -260, 110], [0, 0, 10]],
  ["lift", "Lifted", [-40, -250, 60], [0, 0, 15]],
  ["start", "Starting to pour", [-40, -260, 70], [0, 0, 0]],
  ["pour", "Pouring", [-60, -300, 30], [0, 0, -45]],
];
const VIEW = { width: 800, height: 600 },
  SHRINK = 0.5,
  // Without fixed cameras: the game's own view into the bucket, cropped.
  BUCKET_VIEW = { width: 960, height: 720 },
  CROP = { x: 140, y: 240, width: 560, height: 480 };

// What a browser would have got at each stop, as plain arrays for the page, with
// the load and where the bucket was.
async function simulate(root) {
  const { SandSimulation } = await import(resolve(root, "server/physics.js")),
    { neutral } = await import(resolve(root, "shared/world.js")),
    { decodeFrame, encodeFrame } = await import(resolve(root, "shared/protocol.js")),
    // A build from before the scripted scoop digs this one's.
    scoop = await import(resolve(root, "shared/scoop.js")).catch(
      () => import("../shared/scoop.js"),
    );
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
  for (const [seconds, axes, name] of cycleOf(scoop)) {
    simulation.axes = { ...neutral(), ...axes };
    const steps = Math.round(seconds * 30),
      recent = [];
    for (let i = 0; i < steps; i++) {
      if (i >= steps - 3) recent.push(packet());
      simulation.step();
    }
    recent.push(packet(simulation.terrain.quantize(store)));
    const frame = simulation.vehicles[0].frame;
    stops.push({
      name,
      frames: recent,
      load: simulation.stats.load,
      bucket: frame?.centre ? { at: [...frame.centre], yaw: frame.yaw } : null,
    });
  }
  return stops;
}

// A point given along the arm, to its left and up from the bucket, in the world.
function fromBucket({ at, yaw }, [along, left, up]) {
  const c = Math.cos(yaw),
    s = Math.sin(yaw);
  return [at[0] + along * c - left * s, at[1] + along * s + left * c, at[2] + up];
}

// The stops of a build. With `fixed`, from the side-on cameras of SHOTS; without,
// from the game's own view into the bucket.
async function render(root, fixed) {
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
        transform(code, id) {
          return fixed && id.endsWith("client/scene.js") ? fixCamera(code) : null;
        },
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
                ${fixed ? "" : "preview.view('bucket');"}
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
    const page = await browser.newPage({
      viewport: fixed ? VIEW : BUCKET_VIEW,
      deviceScaleFactor: 1,
    });
    page.on("pageerror", (error) => console.error(error.message));
    await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/comparison`);
    await page.waitForFunction(() => window.preview, null, { timeout: 240000 });
    let placed = fixed;
    for (const { name, frames, load, bucket } of stops) {
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
        { timeout: 240000 },
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
      if (!name) continue;
      let image;
      if (fixed) {
        const [, , from, at] = SHOTS.find(([stop]) => stop === name);
        image = await takePicture(
          page,
          fromBucket(bucket, from),
          fromBucket(bucket, at),
        );
      } else {
        await page.waitForTimeout(2500);
        image = await page.screenshot({ clip: CROP, timeout: 240000 });
      }
      pictures[name] = { image, load };
      console.log(root, name, `${Math.round(load)} cm³`);
    }
  } finally {
    await browser.close();
    await server.close();
  }
  return pictures;
}

// Fixed cameras need both builds' scenes to take them. An older scene that cannot
// is shown, like the newer one beside it, from the game's own bucket view.
const roots = [resolve(olderBuild), here];
let fixed = true;
for (const root of roots)
  try {
    fixCamera(await readFile(resolve(root, "client/scene.js"), "utf8"));
  } catch {
    fixed = false;
  }
const older = await render(roots[0], fixed),
  newer = await render(roots[1], fixed);
const size = fixed
  ? { width: VIEW.width * SHRINK, height: VIEW.height * SHRINK }
  : { width: CROP.width / 1.4, height: CROP.height / 1.4 };
const picture = ({ image, load }) =>
  `<figure><img width="${size.width}" height="${size.height}" src="data:image/png;base64,${image.toString("base64")}"><figcaption>${Math.round(load)} cm³ in the bucket</figcaption></figure>`;
const html = `<!doctype html><style>
  body{margin:0;background:#1d1f22;color:#eee;font:600 22px system-ui,sans-serif;width:max-content;padding:14px}
  .grid{display:grid;grid-template-columns:150px repeat(${SHOTS.length},auto);gap:8px;align-items:center}
  .title{text-align:center;font-size:20px;padding:4px 0}
  small{display:block;font-weight:400;font-size:15px;color:#bbb;margin-top:6px}
  figure{position:relative;margin:0}
  img{display:block}
  figcaption{position:absolute;left:10px;bottom:8px;font-size:16px;text-shadow:0 0 4px #000,0 0 2px #000}
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

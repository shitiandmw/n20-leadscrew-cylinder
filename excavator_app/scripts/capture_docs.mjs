// Regenerate the README screenshots in docs/ from a scripted dig.
// Finite: a temporary server and headless browser are always closed.
// Usage: BROWSER_PATH=/path/to/chrome node scripts/capture_docs.mjs
import { chromium } from "@playwright/test";
import { once } from "node:events";
import WebSocket from "ws";
import { createApplication } from "../server/index.js";
import { AXES, neutral } from "../shared/world.js";
import { SCOOP, CARRY, POUR, RETURN } from "../shared/scoop.js";
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const TICK_RATE = 30;
const app = createApplication();
await new Promise((r) => app.server.listen(0, "127.0.0.1", r));
const origin = `http://127.0.0.1:${app.server.address().port}`;
let browser;
try {
  browser = await chromium.launch({
    executablePath: process.env.BROWSER_PATH || undefined,
    headless: true,
    args: [
      "--no-sandbox",
      "--use-gl=angle",
      "--use-angle=swiftshader",
      "--enable-unsafe-swiftshader",
    ],
  });
  const page = await (
    await browser.newContext({
      viewport: { width: 1440, height: 1149 },
      deviceScaleFactor: 1,
    })
  ).newPage();
  // Software rendering can take minutes to show the first sand.
  page.setDefaultTimeout(240000);
  await page.goto(origin);
  await page.waitForFunction(
    () => window.sandLab?.getGraphics()?.sandCount > 0,
    null,
    { timeout: 240000 },
  );
  const room = await page.evaluate(() => window.sandLab.getRoom()),
    key = await page.evaluate(() => window.sandLab.getPlayer().key),
    { simulation } = app.rooms.get(room);
  const controller = async (query) => {
    const ws = new WebSocket(
      `${origin.replace("http", "ws")}/ws?room=${room}&role=remote&${query}`,
    );
    await once(ws, "open");
    return ws;
  };
  // Hold these inputs for this long in simulated time, counting only the ticks
  // in which the machines really moved. A software renderer slows the physics
  // down, and when it starves this process the server's 350 ms watchdog stops
  // the machines until the next packet; those ticks are made up, so the dig is
  // the same however slow the host gets.
  const drive = async (sockets, seconds, axes) => {
    for (const ws of sockets) ws.send(JSON.stringify({ type: "claim" }));
    await wait(120);
    const wanted = Math.round(seconds * TICK_RATE),
      driven = [...app.rooms.get(room).players.values()]
        .filter((player) => player.owner)
        .map((player) => player.vehicle),
      moving = () =>
        driven.length > 0 &&
        driven.every((vehicle) => AXES.some((key) => vehicle.axes[key] !== 0)),
      input = (axes) =>
        JSON.stringify({
          type: "input",
          axes: { ...neutral(), ...axes },
          speed: 1,
        });
    let moved = 0,
      lastTick = simulation.tick;
    const deadline = Date.now() + seconds * 20000;
    while (moved < wanted && Date.now() < deadline) {
      for (const ws of sockets) ws.send(input(axes));
      await wait(60);
      if (moving()) moved += simulation.tick - lastTick;
      lastTick = simulation.tick;
    }
    for (const ws of sockets) ws.send(input({}));
  };
  // A phone paired with the page digs a trench; the second scoop is captured
  // mid-lift.
  const paired = [await controller(`key=${key}`)];
  const follow = async (sockets, steps) => {
    for (const [seconds, axes] of steps) await drive(sockets, seconds, axes);
  };
  await follow(paired, [...SCOOP, ...CARRY, ...POUR]);
  await wait(1500);
  await follow(paired, [...RETURN, ...SCOOP.slice(3)]);
  await drive(paired, 0.8, { boom: 1 });
  paired[0].send(JSON.stringify({ type: "release" }));
  await wait(2500);
  await page.screenshot({ path: "docs/desktop.png", timeout: 120000 });
  console.log(
    "state",
    JSON.stringify(await page.evaluate(() => window.sandLab.getState().stats)),
  );

  const phone = await (
    await browser.newContext({
      viewport: { width: 390, height: 780 },
      deviceScaleFactor: 2,
      isMobile: true,
      hasTouch: true,
    })
  ).newPage();
  phone.setDefaultTimeout(240000);
  await phone.goto(`${origin}/remote?room=${room}&pair=${key}`);
  await phone
    .getByText("You have control", { exact: true })
    .waitFor({ timeout: 120000 });
  await wait(800);
  await phone.screenshot({ path: "docs/remote.png" });
  await phone.getByRole("button", { name: "Settings" }).click();
  await wait(400);
  await phone.screenshot({ path: "docs/remote-settings.png" });
  await phone.getByRole("button", { name: "Done" }).click();
  await phone.setViewportSize({ width: 844, height: 390 });
  await wait(400);
  await phone.screenshot({ path: "docs/remote-landscape.png" });
  await phone.context().close();
  paired[0].close();

  // Friends arrive, each with a machine of their own, and start digging.
  const friends = [];
  for (const name of ["Ben", "Cam", "Dee", "Eli", "Fay"])
    friends.push(await controller(`name=${name}`));
  await wait(1000);
  await follow(friends, [...SCOOP, CARRY[0]]);
  for (const ws of friends) ws.send(JSON.stringify({ type: "release" }));
  await page.getByRole("button", { name: "Orbit", exact: true }).click();
  await page.mouse.move(720, 500);
  for (let i = 0; i < 6; i++) {
    await page.mouse.wheel(0, 240);
    await wait(150);
  }
  await wait(2500);
  await page.screenshot({ path: "docs/multiplayer.png", timeout: 120000 });
  console.log("graphics", await page.evaluate(() => window.sandLab.getGraphics()));
  for (const ws of friends) ws.close();
} finally {
  await browser?.close();
  await app.close();
}

// Regenerate the README screenshots in docs/ from a scripted dig.
// Finite: a temporary server and headless browser are always closed.
// Usage: BROWSER_PATH=/path/to/chrome node scripts/capture_docs.mjs
import { chromium } from "@playwright/test";
import WebSocket from "ws";
import { createApplication } from "../server/index.js";
import { neutral } from "../shared/world.js";
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
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
  await page.goto(origin);
  await page.waitForFunction(
    () => window.sandLab?.getGraphics()?.sandCount > 0,
    null,
    { timeout: 90000 },
  );
  const room = await page.evaluate(() => window.sandLab.getRoom());
  const ws = new WebSocket(
    `${origin.replace("http", "ws")}/ws?room=${room}&role=remote`,
  );
  await new Promise((r) => ws.once("open", r));
  const drive = async (seconds, axes) => {
    ws.send(JSON.stringify({ type: "claim" }));
    await wait(120);
    const end = Date.now() + seconds * 1000;
    while (Date.now() < end) {
      ws.send(
        JSON.stringify({
          type: "input",
          axes: { ...neutral(), ...axes },
          speed: 1,
        }),
      );
      await wait(90);
    }
    ws.send(JSON.stringify({ type: "input", axes: neutral(), speed: 1 }));
  };
  // A first pass digs a trench; the second scoop is captured mid-lift.
  await drive(1.2, { boom: -1 });
  await drive(1.6, { stick: 1 });
  await drive(4, { bucket: 1 });
  await drive(2, { boom: 1 });
  await drive(1.5, { slew: 1 });
  await drive(4, { bucket: -1 });
  await wait(1500);
  await drive(1.5, { slew: -1 });
  await drive(0.8, { stick: -1 });
  await drive(2.4, { boom: -1 });
  await drive(1.3, { stick: 1 });
  await drive(4, { bucket: 1 });
  await drive(0.8, { boom: 1 });
  ws.send(JSON.stringify({ type: "release" }));
  await page.getByRole("button", { name: "Bucket", exact: true }).click();
  await wait(2500);
  await page.screenshot({ path: "docs/desktop.png", timeout: 120000 });
  const phone = await (
    await browser.newContext({
      viewport: { width: 390, height: 780 },
      deviceScaleFactor: 2,
      isMobile: true,
      hasTouch: true,
    })
  ).newPage();
  await phone.goto(`${origin}/remote?room=${room}`);
  await phone
    .getByText("You have control", { exact: true })
    .waitFor({ timeout: 30000 });
  await wait(800);
  await phone.screenshot({ path: "docs/remote.png" });
  await phone.getByRole("button", { name: "Settings" }).click();
  await wait(400);
  await phone.screenshot({ path: "docs/remote-settings.png" });
  await phone.getByRole("button", { name: "Done" }).click();
  await phone.setViewportSize({ width: 844, height: 390 });
  await wait(400);
  await phone.screenshot({ path: "docs/remote-landscape.png" });
  console.log(
    "state",
    JSON.stringify(await page.evaluate(() => window.sandLab.getState().stats)),
  );
  ws.close();
} finally {
  await browser?.close();
  await app.close();
}

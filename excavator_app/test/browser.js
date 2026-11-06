import { chromium } from "@playwright/test";
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { createApplication } from "../server/index.js";
import { checkControlClaims } from "./control-claims.js";
import { checkRoomRecovery } from "./room-recovery.js";
import { checkRemoteFace } from "./remote-ui.js";
import { checkMultiplayer } from "./multiplayer-ui.js";

// This is a finite test: its HTTP server and browser are always closed.
const app = createApplication({ maxRooms: 8 });
await new Promise((resolve) => app.server.listen(0, "127.0.0.1", resolve));
const origin = `http://127.0.0.1:${app.server.address().port}`;
let browser;
const errors = [];
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
  await checkRoomRecovery(browser);
  await checkControlClaims(browser, app, origin);
  await mkdir("test-results", { recursive: true });
  await checkRemoteFace(browser, app, origin);
  await checkMultiplayer(browser, app, origin);
  const desktop = await browser.newContext({
    viewport: { width: 1440, height: 1050 },
    deviceScaleFactor: 1,
  });
  const page = await desktop.newPage();
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.setDefaultTimeout(30000);
  await page.goto(origin);
  await page.waitForFunction(
    () => window.sandLab?.getGraphics()?.sandCount > 0,
    { timeout: 45000 },
  );
  assert.equal(
    await page.evaluate(() => window.sandLab.getGraphics().meshes),
    644,
  );
  const room = await page.evaluate(() => window.sandLab.getRoom());
  // A first mouse gesture claims the free simulator without a separate click.
  assert.equal(
    await page.evaluate(() => window.sandLab.getState().owner),
    null,
  );
  const desktopStick = await page.locator("#right-stick").boundingBox();
  await page.mouse.move(
    desktopStick.x + desktopStick.width / 2,
    desktopStick.y + desktopStick.height * 0.78,
  );
  await page.mouse.down();
  await page.waitForFunction(
    () => window.sandLab.getState().machine.strokes[0] > 12,
  );
  await page.mouse.up();
  await page.getByText("You have control", { exact: true }).waitFor();
  const resetWorld = async () => {
    await page.getByRole("button", { name: "Menu", exact: true }).click();
    await page.getByRole("button", { name: "Reset world" }).click();
    await page.getByRole("button", { name: "Menu", exact: true }).click();
  };
  await resetWorld();
  await page.getByRole("button", { name: "Release", exact: true }).click();
  await page.waitForFunction(() => window.sandLab.getState().owner === null);
  await page.screenshot({ path: "test-results/desktop.png" });
  await page.getByRole("button", { name: "Pair your phone" }).click();
  await page.locator("#pair-base").fill(origin);
  await page.waitForFunction(() =>
    document.querySelector("#open-remote").href.includes(location.host),
  );
  const pairLink = await page.locator("#open-remote").getAttribute("href");
  assert.match(pairLink, new RegExp(`/remote\\?room=${room}&pair=`));
  await page.screenshot({ path: "test-results/pairing.png" });
  await page.getByRole("button", { name: "Close pairing dialog" }).click();

  const mobile = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 3,
    isMobile: true,
    hasTouch: true,
  });
  const phone = await mobile.newPage();
  const phoneRequests = [];
  phone.on("request", (request) => phoneRequests.push(request.url()));
  phone.on("pageerror", (error) => errors.push(error.message));
  phone.setDefaultTimeout(30000);
  // The pairing link makes this phone a second device for the same excavator.
  await phone.goto(pairLink.replace(new URL(pairLink).origin, origin));
  await phone.getByText("You have control", { exact: true }).waitFor();
  assert.equal(
    new URL(phone.url()).searchParams.has("pair"),
    false,
    "the key moves out of the address bar",
  );
  assert.equal(app.rooms.get(room).players.size, 1, "no extra excavator");
  assert.ok(
    phoneRequests.every((url) => !/model\.json|\/three-|\/scene-/.test(url)),
    "remote stays free of CAD and Three.js downloads",
  );
  await phone.bringToFront();
  // Returning to a phone remote after it releases control must be recoverable
  // with the next touch, just like a simulator opened directly on a phone.
  await phone.evaluate(() => {
    Object.defineProperty(document, "hidden", {
      configurable: true,
      value: true,
    });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await phone.waitForFunction(() => window.sandLab.getState().owner === null);
  await phone.evaluate(() => {
    delete document.hidden;
    document.dispatchEvent(new Event("visibilitychange"));
  });
  assert.equal(
    await phone.locator("body").evaluate((el) => el.scrollWidth <= innerWidth),
    true,
    "phone must not overflow horizontally",
  );
  console.log(
    "Phone layout",
    await phone.evaluate(() => ({
      width: innerWidth,
      height: innerHeight,
      body: document.body.scrollHeight,
    })),
  );
  await phone.screenshot({ path: "test-results/remote.png" });
  const before = await phone.evaluate(
    () => window.sandLab.getState().machine.strokes[0],
  );
  const box = await phone.locator("#right-stick").boundingBox();
  const cdp = await mobile.newCDPSession(phone);
  await cdp.send("Input.dispatchTouchEvent", {
    type: "touchStart",
    touchPoints: [{ x: box.x + box.width / 2, y: box.y + box.height * 0.78 }],
  });
  await phone.waitForFunction(
    (value) => window.sandLab.getState().machine.strokes[0] > value + 2,
    before,
    { timeout: 8000 },
  );
  await cdp.send("Input.dispatchTouchEvent", {
    type: "touchEnd",
    touchPoints: [],
  });
  const released = await phone.evaluate(
    () => window.sandLab.getState().machine.strokes[0],
  );
  await phone.waitForTimeout(500);
  assert.ok(
    Math.abs(
      (await phone.evaluate(
        () => window.sandLab.getState().machine.strokes[0],
      )) - released,
    ) < 1,
    "touch release stops motion",
  );
  await page.bringToFront();
  await page.waitForFunction(
    (value) => window.sandLab.getState().machine.strokes[0] > value + 2,
    before,
  );
  await page.getByRole("button", { name: "EMERGENCY STOP" }).click();
  await phone.waitForFunction(() => window.sandLab.getState().estop);
  await phone.bringToFront();
  if (
    await phone
      .getByRole("button", { name: "Take control", exact: true })
      .isVisible()
  )
    await phone
      .getByRole("button", { name: "Take control", exact: true })
      .click();
  await phone.getByRole("button", { name: "Resume operation" }).click();
  await phone.waitForFunction(() => !window.sandLab.getState().estop);
  // Two independent touch contacts drive two joystick axes simultaneously.
  const left = await phone.locator("#left-stick").boundingBox(),
    right = await phone.locator("#right-stick").boundingBox();
  const startState = await phone.evaluate(
    () => window.sandLab.getState().machine,
  );
  await cdp.send("Input.dispatchTouchEvent", {
    type: "touchStart",
    touchPoints: [
      { id: 1, x: left.x + left.width * 0.78, y: left.y + left.height / 2 },
      { id: 2, x: right.x + right.width * 0.22, y: right.y + right.height / 2 },
    ],
  });
  await phone.waitForFunction((m) => {
    const now = window.sandLab.getState().machine;
    return now.slew > m.slew + 2 && now.strokes[2] > m.strokes[2] + 1;
  }, startState);
  await cdp.send("Input.dispatchTouchEvent", {
    type: "touchCancel",
    touchPoints: [],
  });
  await phone.getByRole("button", { name: "Settings" }).click();
  await phone.getByRole("button", { name: "Reset world" }).click();
  await phone.waitForFunction(
    () =>
      window.sandLab.getState().machine.strokes[0] === 10 &&
      window.sandLab.getState().machine.slew === 0,
  );
  const previousOwner = await phone.evaluate(
    () => window.sandLab.getState().owner,
  );
  for (const [socket, client] of app.rooms.get(room).clients)
    if (client.role === "remote") socket.terminate();
  await phone.waitForFunction(
    (previous) => {
      const state = window.sandLab.getState();
      return state.owner && state.owner !== previous;
    },
    previousOwner,
    { timeout: 10000 },
  );
  assert.equal(
    await phone.evaluate(() => window.sandLab.getState().machine.strokes[0]),
    10,
    "reconnection must not replay a held input",
  );
  await phone.close();
  await page.bringToFront();
  await page.waitForFunction(() => window.sandLab.getState().owner === null);
  await page.keyboard.down("ArrowDown");
  await page.waitForFunction(
    () => window.sandLab.getState().machine.strokes[0] > 12,
  );
  await page.keyboard.up("ArrowDown");
  await page.getByText("You have control", { exact: true }).waitFor();
  // Both tracks drive the machine, and so does the single drive key.
  await page.keyboard.down("q");
  await page.keyboard.down("e");
  await page.waitForFunction(() => window.sandLab.getState().machine.x > 25);
  await page.keyboard.up("q");
  await page.keyboard.up("e");
  await page.keyboard.down("i");
  await page.waitForFunction(() => window.sandLab.getState().machine.x > 60);
  await page.keyboard.up("i");
  // The camera follows the machine: it never stays at the place it started.
  const followed = await page.evaluate(
    () => window.sandLab.getGraphics().camera[0],
  );
  await page.keyboard.down("i");
  await page.waitForFunction(
    (x) => window.sandLab.getGraphics().camera[0] > x + 40,
    followed,
    { timeout: 30000 },
  );
  await page.keyboard.up("i");
  await resetWorld();
  await page.waitForFunction(() => window.sandLab.getState().machine.x === 0);
  for (const name of ["Side", "Top", "Bucket", "Orbit", "Chase"])
    await page.getByRole("button", { name, exact: true }).click();
  // Every part is drawn in full from close up, and from a simpler index further
  // away, where a frame of one machine stays well under a million triangles.
  await page.waitForFunction(
    () => window.sandLab.getGraphics().machineLevel === "far",
  );
  await page.waitForTimeout(3000);
  const farFrame = await page.evaluate(() => window.sandLab.getGraphics());
  assert.ok(farFrame.triangles < 1000000, `${farFrame.triangles} triangles`);
  assert.ok(farFrame.calls < 400, `${farFrame.calls} draw calls`);
  await page.getByRole("button", { name: "Bucket", exact: true }).click();
  await page.waitForFunction(
    () => window.sandLab.getGraphics().machineLevel === "full",
  );
  await page.getByRole("button", { name: "Chase", exact: true }).click();
  await page.waitForFunction(
    () => window.sandLab.getGraphics().machineLevel === "far",
  );
  await page.screenshot({ path: "test-results/desktop.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(
    await page.locator("body").evaluate((el) => el.scrollWidth <= innerWidth),
    true,
    "mobile simulator must not overflow horizontally",
  );
  await page.screenshot({ path: "test-results/mobile-simulator.png" });
  const touchSimulator = await mobile.newPage();
  touchSimulator.on("pageerror", (error) => errors.push(error.message));
  // A second simulator in the room is a second player, with their own machine.
  await touchSimulator.goto(`${origin}/?room=${room}`);
  await touchSimulator.waitForFunction(
    () => window.sandLab?.getGraphics()?.sandCount > 0,
    null,
    { timeout: 45000 },
  );
  const graphics = await touchSimulator.evaluate(() =>
    window.sandLab.getGraphics(),
  );
  assert.equal(
    graphics.shadows,
    false,
    "touch devices skip expensive shadow rendering",
  );
  assert.equal(graphics.pixelRatio, 1);
  assert.equal(graphics.meshes, 644);
  assert.equal(app.rooms.get(room).players.size, 2);
  await page.getByRole("button", { name: "Release", exact: true }).click();
  await touchSimulator.bringToFront();
  await touchSimulator.waitForFunction(
    () => window.sandLab.getState().owner === null,
  );
  await touchSimulator.locator("#right-stick").waitFor();
  const touchStick = await touchSimulator.locator("#right-stick").boundingBox();
  const touchCdp = await mobile.newCDPSession(touchSimulator);
  await touchCdp.send("Input.dispatchTouchEvent", {
    type: "touchStart",
    touchPoints: [
      {
        x: touchStick.x + touchStick.width / 2,
        y: touchStick.y + touchStick.height * 0.78,
      },
    ],
  });
  await touchSimulator.waitForFunction(
    () => window.sandLab.getState().machine.strokes[0] > 12,
  );
  await touchCdp.send("Input.dispatchTouchEvent", {
    type: "touchEnd",
    touchPoints: [],
  });
  await touchSimulator.getByText("You have control", { exact: true }).waitFor();
  await touchSimulator.close();
  assert.deepEqual(errors, []);
  console.log(
    "PASS: 644 CAD meshes, sand rendering, QR pairing, automatic mouse/keyboard/touch control, phone foreground recovery, multitouch, release/cancel, a player's shared E-stop, reset, reconnect, driving, the following camera, ownership handoff, camera views, mobile layouts and reduced touch graphics cost.",
  );
} finally {
  await browser?.close();
  await app.close();
}

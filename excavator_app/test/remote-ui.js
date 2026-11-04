import assert from "node:assert/strict";
import { once } from "node:events";
import { setTimeout as delay } from "node:timers/promises";
import WebSocket from "ws";
import { neutral } from "../shared/world.js";

// Phones in both orientations, with the browser's bars taking their share:
// from a tall full-screen phone down to an old 4-inch phone under Safari's bars.
const PHONES = [
  [390, 844],
  [390, 664],
  [360, 640],
  [375, 553],
  [320, 568],
  [320, 454],
  [844, 390],
  [844, 340],
  [667, 331],
  [568, 320],
];

async function waitFor(check, what) {
  const deadline = Date.now() + 8000;
  while (!check()) {
    assert.ok(Date.now() < deadline, `timed out waiting for ${what}`);
    await delay(10);
  }
}

const watchErrors = (page, errors) => {
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
};

// Everything on the face must fit one screen, stay thumb-sized and not overlap.
async function checkLayout(page, label) {
  const layout = await page.evaluate(() => {
    const parts = {
      estop: "#estop",
      display: ".lcd",
      claim: "#claim",
      settings: "#settings",
      leftStick: "#left-stick",
      rightStick: "#right-stick",
      leftRocker: ".rocker-left .rocker-well",
      rightRocker: ".rocker-right .rocker-well",
    };
    const box = (selector) => {
      const { left, top, right, bottom } = document
        .querySelector(selector)
        .getBoundingClientRect();
      return { left, top, right, bottom };
    };
    return {
      boxes: Object.fromEntries(
        Object.entries(parts).map(([name, selector]) => [name, box(selector)]),
      ),
      halves: [...document.querySelectorAll(".rocker .hold")].map((button) => {
        const { width, height } = button.getBoundingClientRect();
        return { width, height };
      }),
      width: innerWidth,
      height: innerHeight,
      scrollWidth: document.documentElement.scrollWidth,
      scrollHeight: document.documentElement.scrollHeight,
    };
  });
  assert.ok(layout.scrollWidth <= layout.width, `${label}: scrolls sideways`);
  assert.ok(layout.scrollHeight <= layout.height, `${label}: scrolls down`);
  const entries = Object.entries(layout.boxes);
  for (const [name, b] of entries) {
    assert.ok(
      b.left >= 0 &&
        b.top >= 0 &&
        b.right <= layout.width &&
        b.bottom <= layout.height,
      `${label}: ${name} leaves the screen ${JSON.stringify(b)}`,
    );
  }
  for (const [i, [nameA, a]] of entries.entries()) {
    for (const [nameB, b] of entries.slice(i + 1)) {
      assert.ok(
        a.right <= b.left ||
          b.right <= a.left ||
          a.bottom <= b.top ||
          b.bottom <= a.top,
        `${label}: ${nameA} overlaps ${nameB}`,
      );
    }
  }
  for (const name of ["estop", "claim", "settings"]) {
    const b = layout.boxes[name];
    assert.ok(
      b.right - b.left >= 44 && b.bottom - b.top >= 44,
      `${label}: ${name} is too small for a thumb`,
    );
  }
  for (const half of layout.halves)
    assert.ok(
      half.width >= 44 && half.height >= 44,
      `${label}: a track rocker half is too small for a thumb`,
    );
  const stick = layout.boxes.leftStick;
  assert.ok(stick.right - stick.left >= 130, `${label}: joystick too small`);
}

export async function checkRemoteFace(browser, app, origin) {
  const { room } = await (
    await fetch(`${origin}/api/rooms`, { method: "POST" })
  ).json();
  const sandbox = app.rooms.get(room);
  const url = `${origin}/remote?room=${room}`;
  const axes = () => sandbox.simulation.axes;
  const isNeutral = () => Object.values(axes()).every((n) => n === 0);
  const errors = [];

  for (const [width, height] of PHONES) {
    const label = `${width}x${height}`;
    await waitFor(() => sandbox.owner === null, "the previous phone to leave");
    const context = await browser.newContext({
      viewport: { width, height },
      isMobile: true,
      hasTouch: true,
    });
    const page = await context.newPage();
    watchErrors(page, errors);
    await page.goto(url);
    await page.getByText("You have control", { exact: true }).waitFor();
    await checkLayout(page, label);
    if (width === 844 && height === 390)
      await page.screenshot({ path: "test-results/remote-landscape.png" });
    await context.close();
  }

  await waitFor(() => sandbox.owner === null, "the last phone to leave");
  const context = await browser.newContext({
    viewport: { width: 390, height: 664 },
    isMobile: true,
    hasTouch: true,
  });
  let other;
  try {
    await context.addInitScript(() => {
      window.pulses = [];
      Object.defineProperty(navigator, "vibrate", {
        value: (pattern) => window.pulses.push(pattern),
      });
    });
    const page = await context.newPage();
    watchErrors(page, errors);
    await page.goto(url);
    await page.getByText("You have control", { exact: true }).waitFor();
    const cdp = await context.newCDPSession(page);
    const touch = (type, ...touchPoints) =>
      cdp.send("Input.dispatchTouchEvent", { type, touchPoints });
    const pulses = () => page.evaluate(() => window.pulses.length);

    // The LCD reads the machine's real state.
    await page.waitForFunction(
      () =>
        document.querySelector("#boom-value").getAttribute("aria-label") ===
        "Boom 10.0 millimetres",
    );

    // A thumb landing on the cap grabs it; only pushing moves the machine.
    const stick = await page.locator("#right-stick").boundingBox();
    const centre = {
      x: stick.x + stick.width / 2,
      y: stick.y + stick.height / 2,
    };
    await touch("touchStart", { x: centre.x + 12, y: centre.y + 9 });
    await page.waitForFunction(() =>
      document.querySelector("#right-stick").classList.contains("held"),
    );
    const tick = sandbox.simulation.tick;
    await waitFor(() => sandbox.simulation.tick > tick + 4, "a few ticks");
    assert.ok(
      isNeutral(),
      "pressing the cap off-centre must not move anything",
    );
    assert.equal(
      await page.locator("#right-stick").getAttribute("data-v"),
      "",
      "a grabbed cap stays centred",
    );
    const before = await pulses();
    await touch("touchMove", {
      x: centre.x + 12,
      y: centre.y + 9 + stick.height * 0.3,
    });
    await waitFor(
      () => axes().boom > 0.9,
      "the pushed stick to raise the boom",
    );
    assert.equal(
      await page.locator("#right-stick").getAttribute("data-v"),
      "s",
      "the pushed legend lights up",
    );
    assert.ok(
      (await pulses()) >= before + 2,
      "leaving centre and reaching the stop both pulse",
    );
    const offset = await page
      .locator("#right-stick .knob")
      .evaluate((knob, y) => {
        const { top, height } = knob.getBoundingClientRect();
        return top + height / 2 - y;
      }, centre.y);
    assert.ok(
      offset > stick.height * 0.2,
      `the cap follows the thumb (moved ${offset})`,
    );
    await touch("touchEnd");
    await waitFor(isNeutral, "the released stick to stop");
    await page.waitForFunction(() => {
      const pad = document.querySelector("#right-stick");
      return !pad.classList.contains("held") && pad.dataset.v === "";
    });

    // A rocker is two buttons on one part: the pressed end tips and lights.
    const forward = await page
      .getByRole("button", { name: "Left track forward" })
      .boundingBox();
    await touch("touchStart", {
      x: forward.x + forward.width / 2,
      y: forward.y + forward.height / 2,
    });
    await waitFor(() => axes().leftTrack === 1, "the left track to drive");
    assert.notEqual(
      await page
        .locator(".rocker-left .rocker-body")
        .evaluate((body) => getComputedStyle(body).transform),
      "none",
      "the rocker tips while pressed",
    );
    await touch("touchEnd");
    await waitFor(isNeutral, "the released rocker to stop");

    // Settings is modal, so opening it stops whatever the thumbs are holding.
    await touch("touchStart", {
      x: centre.x,
      y: centre.y + stick.height * 0.3,
    });
    await waitFor(() => axes().boom > 0.9, "the held stick");
    await page.getByRole("button", { name: "Settings" }).click();
    await waitFor(isNeutral, "the settings sheet to stop the held stick");
    assert.equal(await page.locator("#settings-sheet").isVisible(), true);
    await touch("touchEnd");
    // The face is inert under the sheet: a tap on its stop lands on the backdrop,
    // which is why the sheet carries an emergency stop of its own.
    assert.equal(
      await page.locator("#estop").evaluate((button) => {
        const { left, top, width, height } = button.getBoundingClientRect();
        return document.elementFromPoint(left + width / 2, top + height / 2).id;
      }),
      "settings-sheet",
    );
    assert.equal(await page.locator("#estop-sheet").isVisible(), true);

    // The speed fader works by touch, reaches the server and shows on the LCD.
    await page.waitForFunction(
      () => !document.querySelector("#settings-sheet").getAnimations().length,
    );
    const fader = await page.locator("#speed").boundingBox();
    const faderY = fader.y + fader.height / 2;
    await touch("touchStart", { x: fader.x + fader.width * 0.56, y: faderY });
    for (const along of [0.5, 0.4, 0.3, 0.2])
      await touch("touchMove", { x: fader.x + fader.width * along, y: faderY });
    await touch("touchEnd");
    const speed = await page.locator("#speed").inputValue();
    assert.ok(+speed < 50, `the fader follows a touch drag (now ${speed})`);
    await waitFor(
      () => Math.round(sandbox.simulation.speed * 100) === +speed,
      "the new speed to reach the server",
    );
    assert.equal(
      await page.locator("#lcd-speed").textContent(),
      `SPD ${speed}%`,
    );

    // The haptics choice is honoured at once and survives a reload.
    assert.equal(await page.locator("#haptics").isChecked(), true);
    await page.locator("#haptics").uncheck();
    await page.getByRole("button", { name: "Done" }).click();
    assert.equal(await page.locator("#settings-sheet").isVisible(), false);
    await page.evaluate(() => {
      window.pulses.length = 0;
    });
    await touch("touchStart", {
      x: forward.x + forward.width / 2,
      y: forward.y + forward.height / 2,
    });
    await waitFor(() => axes().leftTrack === 1, "the left track to drive");
    await touch("touchEnd");
    await waitFor(isNeutral, "the released rocker to stop");
    assert.equal(await pulses(), 0, "haptics off means no pulses");
    await page.reload();
    await page.getByText("You have control", { exact: true }).waitFor();
    await page.getByRole("button", { name: "Settings" }).click();
    assert.equal(await page.locator("#haptics").isChecked(), false);
    await page.locator("#haptics").check();

    // The sheet's stop latches like the one on the face and shows the face.
    await page
      .locator("#settings-sheet")
      .getByRole("button", { name: "Emergency stop" })
      .click();
    await waitFor(() => sandbox.simulation.estop, "the emergency stop");
    assert.equal(await page.locator("#settings-sheet").isVisible(), false);
    await page.locator("#lcd-stop").waitFor();
    await page.waitForFunction(() =>
      document.querySelector("#estop").classList.contains("engaged"),
    );
    assert.equal(await page.locator("#claim").isVisible(), false);
    await page.getByRole("button", { name: "Resume operation" }).click();
    await waitFor(() => !sandbox.simulation.estop, "resume");
    await page.getByRole("button", { name: "Release", exact: true }).waitFor();
    assert.equal(await page.locator("#lcd-stop").isVisible(), false);

    // A stop from another device brings this operator back to the face too.
    other = new WebSocket(`${origin.replace("http", "ws")}/ws?room=${room}`);
    await once(other, "open");
    await page.getByRole("button", { name: "Settings" }).click();
    other.send(JSON.stringify({ type: "estop" }));
    await page.locator("#lcd-stop").waitFor();
    assert.equal(await page.locator("#settings-sheet").isVisible(), false);
    await page.getByRole("button", { name: "Resume operation" }).click();
    await waitFor(() => !sandbox.simulation.estop, "resume");

    // Reset lives in the sheet; its answer appears on the LCD.
    await page.getByRole("button", { name: "Settings" }).click();
    await page.getByRole("button", { name: "Reset sand" }).click();
    await page
      .locator(".lcd")
      .getByText("Sandbox reset. Ready for a fresh dig.", { exact: true })
      .waitFor();
    assert.equal(await page.locator("#settings-sheet").isVisible(), false);

    // The hard floor stop is explained on the phone as well as the simulator.
    await page.getByRole("button", { name: "Release", exact: true }).click();
    await waitFor(() => sandbox.owner === null, "release");
    const drive = async (seconds, command) => {
      other.send(JSON.stringify({ type: "claim" }));
      const end = Date.now() + seconds * 1000;
      while (Date.now() < end) {
        other.send(
          JSON.stringify({
            type: "input",
            axes: { ...neutral(), ...command },
            speed: 1,
          }),
        );
        await delay(80);
      }
    };
    await drive(1.7, { boom: 1 });
    await drive(3.1, { slew: 1 });
    await drive(1.6, { stick: 1 });
    await drive(6, { boom: -1 });
    await page.locator("#lcd-floor").waitFor();
    other.send(JSON.stringify({ type: "input", axes: neutral(), speed: 1 }));
    other.send(JSON.stringify({ type: "release" }));
    await waitFor(() => sandbox.owner === null, "the other device to release");

    assert.deepEqual(errors, []);
    console.log(
      "PASS: phone remote fits one screen at 10 phone sizes with thumb-sized, non-overlapping controls; cap grab, spring return, rockers, haptics, settings sheet, touch fader, sheet and remote stops, reset and floor warning.",
    );
  } finally {
    other?.terminate();
    await context.close();
  }
}

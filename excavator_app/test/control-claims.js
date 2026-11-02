import assert from "node:assert/strict";
import { setTimeout as delay } from "node:timers/promises";
import { once } from "node:events";
import WebSocket from "ws";
import { neutral } from "../shared/world.js";

async function waitFor(check) {
  const deadline = Date.now() + 5000;
  while (!check()) {
    assert.ok(Date.now() < deadline, "control request timed out");
    await delay(10);
  }
}

export async function checkControlClaims(browser, app, origin) {
  const { room } = await (
    await fetch(`${origin}/api/rooms`, {
      method: "POST",
    })
  ).json();
  const sandbox = app.rooms.get(room);
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
  });
  let competitor;
  try {
    const page = await context.newPage();
    const errors = [],
      commands = [];
    page.on("pageerror", (error) => errors.push(error.message));
    let holdStates = false,
      latestState,
      socket;
    await page.routeWebSocket(/\/ws\?/, (route) => {
      socket = route;
      const server = route.connectToServer();
      route.onMessage((message) => {
        commands.push(JSON.parse(message));
        server.send(message);
      });
      server.onMessage((message) => {
        if (holdStates && JSON.parse(message).type === "state")
          latestState = message;
        else route.send(message);
      });
    });
    const deliverState = async () => {
      await waitFor(() => latestState !== undefined);
      holdStates = false;
      socket.send(latestState);
      latestState = undefined;
    };
    const release = async () => {
      await page.getByRole("button", { name: "Release", exact: true }).click();
      await page.waitForFunction(
        () => window.sandLab.getState().owner === null,
      );
      commands.length = 0;
    };
    await page.goto(`${origin}/remote?room=${room}`);
    await page.getByText("You have control", { exact: true }).waitFor();
    const cdp = await context.newCDPSession(page);
    const touch = async (type) => {
      const touchPoints = [];
      if (type === "touchStart") {
        await page.locator("#right-stick").scrollIntoViewIfNeeded();
        const left = await page.locator("#left-stick").boundingBox();
        const right = await page.locator("#right-stick").boundingBox();
        touchPoints.push(
          { id: 1, x: left.x + left.width / 2, y: left.y + left.height / 2 },
          {
            id: 2,
            x: right.x + right.width / 2,
            y: right.y + right.height * 0.78,
          },
        );
      }
      await cdp.send("Input.dispatchTouchEvent", { type, touchPoints });
    };

    // Delay the actual server's ownership reply while the user changes input.
    for (const ending of ["release", "cancel", "blur", "hold"]) {
      await release();
      const before = sandbox.simulation.machine.strokes[0];
      holdStates = true;
      await touch("touchStart");
      await waitFor(() => sandbox.owner !== null);
      assert.equal(
        commands.filter((c) => c.type === "claim").length,
        1,
        "two fingers must share one pending claim",
      );
      assert.equal(
        commands.filter((c) => c.type === "input").length,
        0,
        "movement must wait for the server's ownership reply",
      );
      if (ending === "blur")
        await page.evaluate(() => window.dispatchEvent(new Event("blur")));
      if (ending !== "hold")
        await touch(ending === "release" ? "touchEnd" : "touchCancel");
      await deliverState();
      await page.getByText("You have control", { exact: true }).waitFor();
      if (ending === "hold") {
        await page.waitForFunction(
          (value) => window.sandLab.getState().machine.strokes[0] > value + 1,
          before,
        );
        await touch("touchEnd");
      } else {
        const tick = sandbox.simulation.tick;
        await waitFor(() => sandbox.simulation.tick > tick + 3);
        assert.equal(
          sandbox.simulation.machine.strokes[0],
          before,
          `${ending} before ownership arrives must not replay movement`,
        );
      }
      await waitFor(() =>
        Object.values(sandbox.simulation.axes).every((n) => n === 0),
      );
    }

    // Switching apps must release even a claim whose reply is still in flight.
    await release();
    holdStates = true;
    await touch("touchStart");
    await waitFor(() => sandbox.owner !== null);
    await page.evaluate(() => {
      Object.defineProperty(document, "hidden", {
        configurable: true,
        value: true,
      });
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await waitFor(
      () =>
        sandbox.owner === null &&
        latestState &&
        JSON.parse(latestState).owner === null,
    );
    await touch("touchCancel");
    await deliverState();
    await page.evaluate(() => {
      delete document.hidden;
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await page.waitForFunction(() => window.sandLab.getState().owner === null);
    assert.deepEqual(sandbox.simulation.axes, neutral());

    // Track buttons can also acquire a free slot on their first press.
    const track = await page
      .getByRole("button", { name: "Left track forward" })
      .boundingBox();
    await page.mouse.move(
      track.x + track.width / 2,
      track.y + track.height / 2,
    );
    await page.mouse.down();
    await page.waitForFunction(
      () => window.sandLab.getState().machine.heading !== 0,
    );
    await page.mouse.up();
    await release();

    // A competing operator claims while this browser still sees a free slot.
    holdStates = true;
    competitor = new WebSocket(
      `${origin.replace("http", "ws")}/ws?room=${room}&role=remote`,
    );
    await once(competitor, "open");
    competitor.send(JSON.stringify({ type: "claim" }));
    await waitFor(() => sandbox.owner !== null);
    const owner = sandbox.owner;
    await touch("touchStart");
    await page
      .getByText("Another operator has control. Ask them to release it.", {
        exact: true,
      })
      .waitFor();
    assert.equal(sandbox.owner, owner, "a rejected claim cannot take over");
    competitor.send(JSON.stringify({ type: "release" }));
    await waitFor(
      () =>
        sandbox.owner === null &&
        latestState &&
        JSON.parse(latestState).owner === null,
    );
    await deliverState();
    await touch("touchCancel");
    assert.deepEqual(sandbox.simulation.axes, neutral());
    assert.equal(
      commands.filter((c) => c.type === "input").length,
      0,
      "a rejected claim must discard the waiting gesture",
    );

    // An emergency stop remains latched even with an empty operator slot.
    await page.getByRole("button", { name: "EMERGENCY STOP" }).click();
    await page.waitForFunction(() => window.sandLab.getState().estop);
    commands.length = 0;
    await touch("touchStart");
    await page
      .getByText("Resume operation before moving.", { exact: true })
      .waitFor();
    await touch("touchEnd");
    assert.equal(commands.filter((c) => c.type === "claim").length, 0);
    assert.equal(sandbox.owner, null);
    assert.equal(sandbox.simulation.estop, true);
    await page
      .getByRole("button", { name: "Take control", exact: true })
      .click();
    await page.getByText("You have control", { exact: true }).waitFor();
    await page.getByRole("button", { name: "Resume operation" }).click();
    await page.waitForFunction(() => !window.sandLab.getState().estop);
    assert.deepEqual(errors, []);
    console.log(
      "PASS: delayed control grants, release/cancel/blur before grant, multitouch claim deduplication, held input, track-button claims, competing operators and latched emergency stop.",
    );
  } finally {
    competitor?.terminate();
    await context.close();
  }
}

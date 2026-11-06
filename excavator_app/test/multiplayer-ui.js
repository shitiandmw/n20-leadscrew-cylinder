import assert from "node:assert/strict";
import { setTimeout as delay } from "node:timers/promises";
import { DEFAULT_PLAYERS, PAINTS } from "../shared/players.js";

async function waitFor(check, what, timeout = 30000) {
  const deadline = Date.now() + timeout;
  while (!check()) {
    assert.ok(Date.now() < deadline, `timed out waiting for ${what}`);
    await delay(20);
  }
}

const ready = (page) =>
  page.waitForFunction(
    () =>
      window.sandLab?.getGraphics()?.sandCount > 0 &&
      window.sandLab.getPlayer(),
    null,
    { timeout: 120000 },
  );
const row = (page, name) =>
  page.locator("#player-list .player", { hasText: name });
const graphics = (page) => page.evaluate(() => window.sandLab.getGraphics());

async function rename(page, name) {
  const menu = page.getByRole("button", { name: "Menu", exact: true });
  await menu.click();
  await page.locator("#player-name").fill(name);
  await page.locator("#player-name").blur();
  await row(page, name).waitFor();
  await menu.click();
}

// How much of a machine's paint the map shows.
const paintOnMap = (page, paint) =>
  page.evaluate((hex) => {
    const map = document.querySelector("#minimap"),
      { data } = map
        .getContext("2d")
        .getImageData(0, 0, map.width, map.height),
      [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
    let pixels = 0;
    for (let i = 0; i < data.length; i += 4)
      if (
        Math.abs(data[i] - r) + Math.abs(data[i + 1] - g) + Math.abs(data[i + 2] - b) <
        6
      )
        pixels++;
    return pixels;
  }, paint);

// The player list opens below the buttons however they wrap, and nothing up there
// sits on anything else.
async function checkHudLayout(page) {
  const parts = {
    brand: ".game .brand",
    session: ".hud-session",
    views: ".view-buttons",
    fullscreen: "#fullscreen",
    invite: "#invite",
    pair: "[data-pair]",
    menu: "#menu-toggle",
    roster: "#roster",
  };
  const overlaps = () =>
    page.evaluate((selectors) => {
      const boxes = Object.entries(selectors).map(([name, selector]) => [
          name,
          document.querySelector(selector).getBoundingClientRect(),
        ]),
        hits = [];
      for (const [i, [nameA, a]] of boxes.entries()) {
        if (a.right > innerWidth || a.bottom > innerHeight)
          hits.push(`${nameA} leaves the screen`);
        for (const [nameB, b] of boxes.slice(i + 1))
          if (
            a.left < b.right &&
            b.left < a.right &&
            a.top < b.bottom &&
            b.top < a.bottom
          )
            hits.push(`${nameA} on ${nameB}`);
      }
      return hits;
    }, parts);
  for (const [width, height] of [
    [390, 844],
    [360, 640],
    [844, 390],
    [768, 1024],
  ]) {
    await page.setViewportSize({ width, height });
    const deadline = Date.now() + 10000;
    let hits = await overlaps();
    while (hits.length && Date.now() < deadline) {
      await delay(200);
      hits = await overlaps();
    }
    assert.deepEqual(hits, [], `at ${width}x${height}`);
    if (width === 390)
      await page.screenshot({ path: "test-results/multiplayer-phone.png" });
  }
  await page.locator("#roster-toggle").click();
  assert.equal(await page.locator("#player-list").isVisible(), false);
  await page.locator("#roster-toggle").click();
  assert.equal(await page.locator("#player-list").isVisible(), true);
}

// One room as its players see it: two people at computers, a phone paired with
// the first of them, and someone who has only a phone.
export async function checkMultiplayer(browser, app, origin) {
  const errors = [],
    contexts = [];
  const open = async (options, url) => {
    const context = await browser.newContext(options);
    contexts.push(context);
    const page = await context.newPage();
    page.setDefaultTimeout(60000);
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") errors.push(message.text());
    });
    await page.goto(url);
    return page;
  };
  const computer = {
      viewport: { width: 1100, height: 760 },
      deviceScaleFactor: 1,
    },
    handset = {
      viewport: { width: 390, height: 664 },
      isMobile: true,
      hasTouch: true,
    };
  try {
    // The first person to arrive is the host of a new room.
    const ana = await open(computer, origin);
    await ready(ana);
    const room = await ana.evaluate(() => window.sandLab.getRoom()),
      sandbox = app.rooms.get(room),
      players = () => [...sandbox.players.values()],
      named = (name) => players().find((player) => player.name === name);
    await rename(ana, "Ana");
    assert.equal(
      await ana.locator("#player-count").textContent(),
      `1/${DEFAULT_PLAYERS}`,
    );
    assert.match(await row(ana, "Ana").textContent(), /you · host/);
    const anaPlayer = named("Ana");

    // Invite links carry the room and never anybody's key.
    await ana.getByRole("button", { name: "Invite players" }).click();
    await ana.locator("#invite-base").fill(origin);
    const inviteLink = () =>
      ana.locator("#open-invite").getAttribute("href");
    await ana.waitForFunction(
      (link) => document.querySelector("#open-invite").href === link,
      `${origin}/?room=${room}`,
    );
    await ana.locator('input[name="invite-kind"][value="remote"]').check();
    await ana.waitForFunction(
      (link) => document.querySelector("#open-invite").href === link,
      `${origin}/remote?room=${room}`,
    );
    assert.doesNotMatch(await inviteLink(), /pair=/);
    await ana.locator('input[name="invite-kind"][value="game"]').check();
    await ana.waitForFunction(
      (link) => document.querySelector("#open-invite").href === link,
      `${origin}/?room=${room}`,
    );
    const invitation = await inviteLink();
    await ana.getByRole("button", { name: "Close invite dialog" }).click();

    // The invited person arrives in the same world with a machine of their own.
    const benMapBefore = await paintOnMap(ana, PAINTS[1]);
    const ben = await open(computer, invitation);
    await ready(ben);
    await rename(ben, "Ben");
    await row(ana, "Ben").waitFor();
    assert.equal(sandbox.players.size, 2);
    assert.equal(await ben.evaluate(() => window.sandLab.getRoom()), room);
    const benPlayer = named("Ben");
    const benPaint = await ben.evaluate(() => window.sandLab.getPlayer().paint),
      anaPaint = await ana.evaluate(() => window.sandLab.getPlayer().paint);
    assert.notEqual(benPaint, anaPaint);
    assert.notDeepEqual(
      [benPlayer.vehicle.machine.x, benPlayer.vehicle.machine.y],
      [anaPlayer.vehicle.machine.x, anaPlayer.vehicle.machine.y],
    );
    for (const page of [ana, ben]) {
      await page.waitForFunction(() => {
        const g = window.sandLab.getGraphics();
        return g.machines === 2 && g.detailed === 1;
      });
    }
    assert.equal(benPaint, PAINTS[1]);
    await ana.waitForFunction(
      () => window.sandLab.getGraphics().following === window.sandLab.getPlayer().id,
    );

    // Everyone else's machine has a name over it and an arrow on the map.
    await ana.getByRole("button", { name: "Top", exact: true }).click();
    const label = ana.locator(".machine-label", { hasText: "Ben" });
    await label.waitFor();
    assert.equal(
      await ana.locator(".machine-label", { hasText: "Ana" }).count(),
      0,
    );
    const deadline = Date.now() + 30000;
    while ((await paintOnMap(ana, benPaint)) <= benMapBefore + 20) {
      assert.ok(Date.now() < deadline, "Ben's arrow never reached the map");
      await delay(200);
    }
    await ana.screenshot({ path: "test-results/multiplayer.png" });
    await ana.getByRole("button", { name: "Chase", exact: true }).click();

    // A phone paired with Ana drives Ana's machine and adds no new one.
    const pairLink = await ana.locator("#remote-link").getAttribute("href");
    assert.ok(pairLink.startsWith(`/remote?room=${room}&pair=`));
    const phone = await open(handset, origin + pairLink);
    await phone.getByText("You have control", { exact: true }).waitFor();
    assert.equal(new URL(phone.url()).searchParams.has("pair"), false);
    assert.equal(sandbox.players.size, 2, "pairing adds no excavator");
    assert.equal(await phone.locator("#rc-player").textContent(), "Ana");
    await ana
      .getByText("Your other device is driving", { exact: true })
      .waitFor();
    const benBefore = structuredClone(benPlayer.vehicle.machine),
      cdp = await phone.context().newCDPSession(phone),
      forward = await phone
        .getByRole("button", { name: "Left track forward" })
        .boundingBox();
    await cdp.send("Input.dispatchTouchEvent", {
      type: "touchStart",
      touchPoints: [
        { x: forward.x + forward.width / 2, y: forward.y + forward.height / 2 },
      ],
    });
    await waitFor(
      () => Math.abs(anaPlayer.vehicle.machine.heading) > 0.02,
      "Ana's machine to turn",
    );
    await cdp.send("Input.dispatchTouchEvent", {
      type: "touchEnd",
      touchPoints: [],
    });
    for (const key of ["x", "y", "heading", "slew"])
      assert.equal(benPlayer.vehicle.machine[key], benBefore[key]);

    // An emergency stop stops one machine: the one it belongs to.
    await phone.getByRole("button", { name: "Emergency stop" }).first().click();
    await waitFor(() => anaPlayer.vehicle.estop, "Ana's stop");
    assert.equal(benPlayer.vehicle.estop, false);
    await ana.locator(".stop-banner").waitFor();
    assert.equal(await ben.locator(".stop-banner").isVisible(), false);
    await phone.getByRole("button", { name: "Resume operation" }).click();
    await waitFor(() => !anaPlayer.vehicle.estop, "Ana's resume");
    await phone.getByRole("button", { name: "Release", exact: true }).click();
    await waitFor(() => anaPlayer.owner === null, "the phone to release");

    // Someone with only a phone joins by typing the room code.
    const cara = await open(handset, `${origin}/remote`);
    await cara.locator("#room-code").fill(room);
    await cara.locator("#join-name").fill("Cara");
    await cara.getByRole("button", { name: "Connect to excavator" }).click();
    await cara.getByText("You have control", { exact: true }).waitFor();
    assert.equal(await cara.locator("#rc-player").textContent(), "Cara");
    await row(ana, "Cara").waitFor();
    assert.equal(sandbox.players.size, 3);
    assert.equal(
      await ana.locator("#player-count").textContent(),
      `3/${DEFAULT_PLAYERS}`,
    );
    await cara.getByRole("button", { name: "Settings" }).click();
    await cara.waitForFunction(
      (text) => document.querySelector("#sheet-players").textContent === text,
      `With 2 others, 3 of ${DEFAULT_PLAYERS}`,
    );
    assert.equal(await cara.locator("#reset").isDisabled(), true);
    assert.equal(
      await cara.locator("#reset-note").textContent(),
      "Only the host of this room can do this.",
    );
    await cara.getByRole("button", { name: "Back to start" }).click();
    await cara
      .locator(".lcd")
      .getByText("Back at a start position.", { exact: true })
      .waitFor();

    // Clicking a name puts the camera on that machine, with room to see it.
    await ana.getByRole("button", { name: "Watch Ben" }).click();
    await ana.locator("#watching").waitFor();
    assert.equal(await ana.locator("#watching-name").textContent(), "Ben");
    await ana.waitForFunction(
      ({ id, x, y }) => {
        const g = window.sandLab.getGraphics();
        return (
          g.following === id &&
          g.detailed === 1 &&
          Math.hypot(g.camera[0] - x, g.camera[1] - y) > 1000
        );
      },
      { id: benPlayer.id, x: benBefore.x, y: benBefore.y },
    );
    await ana.getByRole("button", { name: "Back to my excavator" }).click();
    await ana.waitForFunction(() => {
      const g = window.sandLab.getGraphics();
      return g.following === window.sandLab.getPlayer().id && g.detailed === 1;
    });
    assert.equal(await ana.locator("#watching").isVisible(), false);

    // Two crawlers cannot share a place, and the driver is told why.
    const stopped = anaPlayer.vehicle.machine;
    sandbox.simulation.place(benPlayer.vehicle, {
      ...benPlayer.vehicle.machine,
      x: stopped.x - 620,
      y: stopped.y,
      heading: 0,
    });
    await ben.bringToFront();
    await ben.keyboard.down("i");
    await ben.locator(".obstacle-banner").waitFor();
    assert.equal(
      await ben.locator(".obstacle-banner").textContent(),
      "ANOTHER EXCAVATOR IN THE WAY · BACK UP OR TURN",
    );
    await ben.keyboard.up("i");
    const closest = benPlayer.vehicle.machine.x;
    await ben.keyboard.down("k");
    await waitFor(
      () => benPlayer.vehicle.machine.x < closest - 10,
      "Ben to back away",
    );
    await ben.keyboard.up("k");
    await ben.locator(".obstacle-banner").waitFor({ state: "hidden" });

    // A guest cannot reset the shared world, even in control; the host can, and
    // everyone is told.
    assert.notEqual(benPlayer.owner, null);
    assert.equal(await ben.locator("#reset").isDisabled(), true);
    await ana.bringToFront();
    await ana.keyboard.down("ArrowDown");
    await waitFor(() => anaPlayer.owner !== null, "Ana to take control");
    await ana.keyboard.up("ArrowDown");
    await ana.getByRole("button", { name: "Menu", exact: true }).click();
    await ana.getByRole("button", { name: "Reset world" }).click();
    await ana.getByRole("button", { name: "Menu", exact: true }).click();
    // A toast is brief, and a software renderer can look too late to see it up.
    await ben.waitForFunction(
      () => document.querySelector("#toast").textContent === "Ana reset the world.",
    );
    await waitFor(
      () =>
        benPlayer.vehicle.machine.x === benPlayer.vehicle.home.x &&
        anaPlayer.vehicle.machine.heading === 0,
      "every machine to go back to its start",
    );

    // Someone who leaves stays on the list for a while, in case they come back.
    await cara.context().close();
    await ana.waitForFunction(() =>
      [...document.querySelectorAll("#player-list .player")].some(
        (button) =>
          button.textContent.includes("Cara") &&
          button.textContent.includes("offline"),
      ),
    );
    assert.equal(sandbox.players.size, 3);

    await checkHudLayout(ana);

    // Reloading is not leaving: the tab remembers whose machine it drives.
    await ana.context().close();
    await ben.reload();
    await ready(ben);
    assert.equal(
      await ben.evaluate(() => window.sandLab.getPlayer().id),
      benPlayer.id,
    );
    assert.equal(named("Ben"), benPlayer, "no second machine for the same tab");
    assert.match(await row(ben, "Ben").textContent(), /you/);
    assert.match(await row(ben, "Ana").textContent(), /host/);

    assert.deepEqual(errors, []);
    console.log(
      "PASS: invite links, own excavators with their own paint, names and map arrows, a paired phone on the same machine, a phone-only player, watching, per-machine stops, crawler collisions, host-only reset, grace after leaving, the list at phone sizes and reloading.",
    );
  } finally {
    for (const context of contexts) await context.close().catch(() => {});
  }
}

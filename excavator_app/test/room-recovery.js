import assert from "node:assert/strict";
import { createApplication } from "../server/index.js";

export async function checkRoomRecovery(browser) {
  let app = createApplication({ maxRooms: 1 });
  await new Promise((resolve) => app.server.listen(0, "127.0.0.1", resolve));
  const port = app.server.address().port;
  const origin = `http://127.0.0.1:${port}`;
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1050 },
  });
  const errors = [];
  try {
    const page = await context.newPage();
    page.on("pageerror", (error) => errors.push(error.message));
    let roomCreates = 0;
    const sockets = [];
    page.on("request", (request) => {
      if (request.method() === "POST" && request.url().endsWith("/api/rooms"))
        roomCreates++;
    });
    page.on("websocket", (socket) => sockets.push(socket.url()));

    // A bookmarked simulator URL survives expiry without a failed handshake.
    await page.goto(`${origin}/?room=BD7727`);
    await page.waitForFunction(() => window.sandLab?.getState());
    const room = await page.evaluate(() => window.sandLab.getRoom());
    assert.notEqual(room, "BD7727");
    assert.equal(roomCreates, 1);
    assert.equal(new URL(page.url()).searchParams.get("room"), room);
    assert.equal(await page.locator("#room-label").textContent(), room);
    assert.equal(
      await page.locator("#remote-link").getAttribute("href"),
      `/remote?room=${room}`,
    );
    assert.equal(sockets.length, 1);
    assert.equal(new URL(sockets[0]).searchParams.get("room"), room);
    await page.getByRole("button", { name: "Pair your phone" }).click();
    await page.waitForFunction(
      (code) => document.querySelector("#open-remote").href.endsWith(`room=${code}`),
      room,
    );
    const originalQr = await page.locator("#qr").evaluate((canvas) => canvas.toDataURL());
    await page.getByRole("button", { name: "Close pairing dialog" }).click();

    // An ordinary dropped socket retains the room and simulation.
    const clientId = [...app.rooms.get(room).clients.values()][0].id;
    for (const ws of app.rooms.get(room).clients.keys()) ws.terminate();
    await page.waitForFunction(
      () => document.querySelector("#connection-text").textContent === "Reconnecting",
    );
    await page.waitForFunction(
      () => document.querySelector("#connection-text").textContent === "Connected",
    );
    assert.equal(await page.evaluate(() => window.sandLab.getRoom()), room);
    assert.notEqual([...app.rooms.get(room).clients.values()][0].id, clientId);
    assert.equal(
      roomCreates,
      1,
      "transient network failures must not create another room",
    );

    // A failed room lookup must not be mistaken for an expired room. The
    // explicit retry should restore the connection without a page reload.
    await page.route(`**/api/rooms/${room}`, (route) => route.fulfill({
      status: 503,
      json: { error: "Room lookup unavailable. Retry connection." },
    }));
    for (const ws of app.rooms.get(room).clients.keys()) ws.terminate();
    await page.getByText("Room lookup unavailable. Retry connection.").waitFor();
    assert.equal(await page.evaluate(() => window.sandLab.getRoom()), room);
    assert.equal(roomCreates, 1);
    await page.getByRole("button", { name: "Retry connection" }).waitFor();
    await page.unroute(`**/api/rooms/${room}`);
    // The app also retries by itself. A rendering-heavy page makes a pointer
    // click slow enough to lose that race, so press the button straight away.
    await page.evaluate(() => document.querySelector("#retry-connection").click());
    await page.waitForFunction(
      () => document.querySelector("#connection-text").textContent === "Connected",
    );
    assert.equal(await page.evaluate(() => window.sandLab.getRoom()), room);
    assert.equal(roomCreates, 1);
    await page.getByRole("button", { name: "Pair your phone" }).click();

    // Restart the real server on the same address while pairing is open.
    await app.close();
    app = createApplication({ maxRooms: 1 });
    await new Promise((resolve) => app.server.listen(port, "127.0.0.1", resolve));
    await page.waitForFunction(
      (code) => window.sandLab.getRoom() !== code && window.sandLab.getState(),
      room,
    );
    const replacement = await page.evaluate(() => window.sandLab.getRoom());
    assert.equal(roomCreates, 2);
    assert.equal(new URL(page.url()).searchParams.get("room"), replacement);
    assert.equal(await page.locator("#room-label").textContent(), replacement);
    assert.equal(
      await page.locator("#remote-link").getAttribute("href"),
      `/remote?room=${replacement}`,
    );
    await page.waitForFunction(
      (code) =>
        document.querySelector("#pair-code").textContent === code &&
        document.querySelector("#open-remote").href.endsWith(`room=${code}`),
      replacement,
    );
    await page.waitForFunction(
      (previous) => document.querySelector("#qr").toDataURL() !== previous,
      originalQr,
    );
    assert.equal(await page.locator("#connection-help").isVisible(), false);
    assert.equal(await page.evaluate(() => window.sandLab.getState().owner), null);

    const phone = await context.newPage();
    phone.on("pageerror", (error) => errors.push(error.message));
    const phoneSockets = [];
    phone.on("websocket", (socket) => phoneSockets.push(socket.url()));
    await phone.goto(`${origin}/remote?room=${room}`);
    await phone
      .getByText(/This room has expired or the server has restarted/)
      .waitFor();
    assert.equal(
      await phone.locator("#connection-text").textContent(),
      "Disconnected",
    );
    assert.equal(await phone.locator("#claim").isDisabled(), true);
    assert.equal(await phone.locator("#estop").isDisabled(), true);
    assert.equal(await phone.locator("#retry-connection").isVisible(), false);
    assert.equal(
      phoneSockets.length,
      0,
      "expired phone links must not retry WebSockets",
    );
    assert.equal(
      app.rooms.size,
      1,
      "a phone must not silently open a different sandbox",
    );
    await phone.getByRole("link", { name: "Enter room code" }).click();
    await phone.locator("#room-code").fill(replacement);
    await phone.getByRole("button", { name: "Connect to excavator" }).click();
    await phone.getByText("You have control", { exact: true }).waitFor();
    assert.equal(await phone.evaluate(() => window.sandLab.getRoom()), replacement);
    assert.deepEqual(errors, []);
    console.log(
      "PASS: expired simulator links, transient reconnect, failed lookup/manual retry, server restart, updated QR/pairing links and expired phone recovery.",
    );
  } finally {
    await context.close();
    await app.close();
  }
}

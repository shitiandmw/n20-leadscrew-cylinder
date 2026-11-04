import test from "node:test";
import assert from "node:assert/strict";
import { once } from "node:events";
import { setTimeout as delay } from "node:timers/promises";
import WebSocket from "ws";
import { createApplication } from "../server/index.js";
import { neutral } from "../shared/world.js";
import { decodeFrame, applyTiles } from "../shared/protocol.js";

async function waitFor(check, timeout = 5000) {
  const start = Date.now();
  while (!check()) {
    if (Date.now() - start > timeout) throw new Error("Condition timed out");
    await delay(30);
  }
}
async function connect(url, options) {
  const ws = new WebSocket(url, options),
    client = { ws, messages: [], binary: 0 };
  ws.on("message", (buffer, binary) => {
    if (binary) {
      client.binary++;
      const frame = decodeFrame(Uint8Array.from(buffer));
      client.frame = frame;
      client.terrain ??= new Map();
      client.tiles = (client.tiles || 0) + frame.tiles.length;
      applyTiles(client.terrain, frame.tiles);
    } else {
      const message = JSON.parse(buffer);
      client.messages.push(message);
      if (message.type === "welcome") client.id = message.id;
      if (message.type === "state") client.state = message;
    }
  });
  await once(ws, "open");
  await waitFor(() => client.id);
  client.send = (body) => ws.send(JSON.stringify(body));
  return client;
}

test("room lookup distinguishes expired links and full rooms without creating rooms", async () => {
  const app = createApplication({ maxRooms: 1 });
  await new Promise((resolve) => app.server.listen(0, "127.0.0.1", resolve));
  const origin = `http://127.0.0.1:${app.server.address().port}`;
  try {
    const missing = await fetch(`${origin}/api/rooms/BD7727`);
    assert.equal(missing.status, 404);
    assert.equal((await missing.json()).code, "ROOM_NOT_FOUND");
    assert.equal(
      app.rooms.size,
      0,
      "a stale phone link must not create a room",
    );
    const { room } = await (
      await fetch(`${origin}/api/rooms`, { method: "POST" })
    ).json();
    const lookup = () => fetch(`${origin}/api/rooms/${room.toLowerCase()}`);
    const response = await lookup();
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.deepEqual(await response.json(), { room, clients: 0, capacity: 8 });
    const socket = `${origin.replace("http", "ws")}/ws?room=${room}&role=remote`;
    const foreign = new WebSocket(socket, {
      origin: "https://elsewhere.invalid",
    });
    foreign.on("error", () => {});
    const [request, rejection] = await once(foreign, "unexpected-response");
    assert.equal(
      rejection.statusCode,
      403,
      "cross-origin sockets stay forbidden",
    );
    request.destroy();
    foreign.terminate();
    for (let i = 0; i < 8; i++) await connect(socket, { origin });
    assert.deepEqual(await (await lookup()).json(), {
      room,
      clients: 8,
      capacity: 8,
    });
    assert.equal(app.rooms.size, 1);
  } finally {
    await app.close();
  }
});

test(
  "HTTP and real WebSocket clients share controls with watchdogs and ownership",
  { timeout: 30000 },
  async () => {
    const app = createApplication({ maxRooms: 1, idleMs: 150 });
    await new Promise((resolve) => app.server.listen(0, "127.0.0.1", resolve));
    const origin = `http://127.0.0.1:${app.server.address().port}`,
      socket = origin.replace("http", "ws");
    try {
      assert.equal((await fetch(origin + "/api/health")).status, 200);
      assert.equal((await fetch(origin + "/remote")).status, 200);
      assert.equal(
        (
          await fetch(origin + "/api/rooms", {
            method: "POST",
            headers: { Origin: "https://elsewhere.invalid" },
          })
        ).status,
        403,
      );
      const response = await fetch(origin + "/api/rooms", { method: "POST" });
      assert.equal(response.status, 201);
      const { room } = await response.json();
      assert.equal(
        (await fetch(origin + "/api/rooms", { method: "POST" })).status,
        503,
      );
      const viewer = await connect(`${socket}/ws?room=${room}&role=simulator`);
      const operator = await connect(`${socket}/ws?room=${room}&role=remote`);
      const observer = await connect(`${socket}/ws?room=${room}&role=remote`);
      operator.send({ type: "claim" });
      await waitFor(() => viewer.state?.owner === operator.id);
      observer.send({ type: "claim" });
      await waitFor(() => observer.messages.some((m) => m.type === "error"));
      assert.equal(viewer.state.owner, operator.id);
      observer.send({
        type: "input",
        axes: { ...neutral(), boom: 1 },
        speed: 1,
      });
      await delay(120);
      assert.equal(
        viewer.state.machine.strokes[0],
        10,
        "observer cannot move the machine",
      );
      operator.send({
        type: "input",
        axes: { ...neutral(), boom: 1 },
        speed: 1,
      });
      await waitFor(() => viewer.state.machine.strokes[0] > 11);
      await delay(550);
      const stopped = viewer.state.machine.strokes[0];
      await delay(200);
      assert.equal(
        viewer.state.machine.strokes[0],
        stopped,
        "stale input becomes neutral after 350 ms",
      );
      operator.send({
        type: "input",
        axes: { ...neutral(), boom: "1" },
        speed: 1,
      });
      operator.send({
        type: "input",
        axes: { ...neutral(), boom: 99 },
        speed: 1,
      });
      operator.send({
        type: "input",
        axes: { ...neutral(), boom: 1 },
        speed: null,
      });
      await waitFor(
        () => operator.messages.filter((m) => m.type === "error").length >= 3,
      );
      observer.send({ type: "estop" });
      await waitFor(() => viewer.state.estop);
      operator.send({
        type: "input",
        axes: { ...neutral(), boom: 1 },
        speed: 1,
      });
      await delay(180);
      assert.equal(viewer.state.machine.strokes[0], stopped);
      operator.send({ type: "reset" });
      await waitFor(() => viewer.state.machine.strokes[0] === 10);
      assert.equal(
        viewer.state.estop,
        true,
        "reset must not clear a latched E-stop",
      );
      operator.send({ type: "resume" });
      await waitFor(() => !viewer.state.estop);
      operator.send({
        type: "input",
        axes: { ...neutral(), leftTrack: 1, rightTrack: -1 },
        speed: 1,
      });
      await waitFor(() => viewer.state.machine.heading < -0.01);
      operator.ws.terminate();
      await waitFor(() => viewer.state.owner === null);
      const heading = viewer.state.machine.heading;
      await delay(200);
      assert.equal(viewer.state.machine.heading, heading);
      observer.send({ type: "claim" });
      await waitFor(() => viewer.state.owner === observer.id);
      assert.ok(viewer.binary > 0);
      // The first frame delivers all the sand there is; later frames carry only
      // changed tiles together with the machine pose of the same tick.
      assert.ok(viewer.tiles > 1000);
      assert.ok(
        [...viewer.terrain.values()].some((tile) =>
          tile.some((height) => height > 1000),
        ),
      );
      assert.equal(viewer.frame.grains.length % 4, 0);
      assert.equal(
        viewer.frame.machine.heading,
        Math.fround(viewer.state.machine.heading),
      );
      assert.equal(observer.binary, 0, "phones receive telemetry only");
      observer.send({ type: "release" });
      await waitFor(() => viewer.state.owner === null);
      observer.ws.close();
      const worker = app.rooms.get(room).simulation.worker;
      viewer.ws.close();
      await waitFor(() => app.rooms.size === 0);
      await waitFor(() => worker.threadId === -1);
      const invalid = new WebSocket(`${socket}/ws?room=BADBAD&role=remote`);
      invalid.on("error", () => {});
      const [failed] = await once(invalid, "unexpected-response");
      failed.destroy();
      invalid.terminate();
    } finally {
      await app.close();
    }
  },
);

test(
  "four active rooms keep phone round trips responsive",
  { timeout: 30000 },
  async () => {
    const app = createApplication();
    await new Promise((resolve) => app.server.listen(0, "127.0.0.1", resolve));
    const origin = `http://127.0.0.1:${app.server.address().port}`;
    const clients = [];
    let heartbeat;
    try {
      for (let i = 0; i < 4; i++) {
        const { room } = await (
          await fetch(origin + "/api/rooms", { method: "POST" })
        ).json();
        const client = await connect(
          `${origin.replace("http", "ws")}/ws?room=${room}&role=remote`,
        );
        clients.push(client);
        client.send({ type: "claim" });
        await waitFor(() => client.state?.owner === client.id);
      }
      const input = {
        type: "input",
        axes: { ...neutral(), bucket: 1 },
        speed: 1,
      };
      heartbeat = setInterval(
        () => clients.forEach((client) => client.send(input)),
        100,
      );
      clients.forEach((client) => client.send(input));
      await waitFor(() =>
        clients.every((client) => client.state.machine.strokes[2] > 0),
      );
      const client = clients[0],
        roundTrips = [];
      for (let i = 0; i < 30; i++) {
        const start = performance.now();
        client.send({ type: "ping", at: i });
        while (
          !client.messages.some(
            (message) => message.type === "pong" && message.at === i,
          )
        ) {
          assert.ok(
            performance.now() - start < 1000,
            "physics must not stall the phone connection",
          );
          await delay(2);
        }
        roundTrips.push(performance.now() - start);
        await delay(20);
      }
      roundTrips.sort((a, b) => a - b);
      const p95 = roundTrips[Math.floor(roundTrips.length * 0.95)];
      assert.ok(
        p95 < 350,
        `phone round trips must stay within the input watchdog (${p95.toFixed(1)} ms)`,
      );
      console.log(
        `Four active rooms: phone round-trip p95 ${p95.toFixed(1)} ms; max ${roundTrips.at(-1).toFixed(1)} ms (loopback).`,
      );
      assert.ok(clients.every((client) => client.binary === 0));
    } finally {
      clearInterval(heartbeat);
      await app.close();
    }
  },
);

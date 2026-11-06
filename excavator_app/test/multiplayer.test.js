import test from "node:test";
import assert from "node:assert/strict";
import { once } from "node:events";
import { setTimeout as delay } from "node:timers/promises";
import WebSocket from "ws";
import { SandSimulation, bucketPose } from "../server/physics.js";
import { createApplication } from "../server/index.js";
import { mouthToLocal } from "../shared/bucket-load.js";
import {
  SAND,
  neutral,
  crawlersOverlap,
  initialMachine,
} from "../shared/world.js";
import {
  groundHeight,
  crawlerHitsProp,
  initialSand,
  cameraWall,
  landscape,
} from "../shared/landscape.js";
import { CONFIG } from "../shared/config.js";
import {
  SPAWNS,
  PAINTS,
  DEFAULT_PLAYERS,
  spawnMachine,
  cleanName,
} from "../shared/players.js";
import { decodeFrame, encodeFrame } from "../shared/protocol.js";
import { FrameJitter } from "../client/frame-jitter.js";

const near = (a, b, tolerance) => Math.abs(a - b) <= tolerance;
function world(machines) {
  return new SandSimulation({
    vehicles: machines.map((machine, index) => ({ id: index + 1, machine })),
  });
}
const axesFor = (s, commands) =>
  s.vehicles.forEach((v, n) => {
    v.axes = { ...neutral(), ...commands[n] };
    v.speed = 1;
  });
function run(s, seconds, ...commands) {
  axesFor(s, commands);
  for (let i = 0; i < Math.round(seconds * 30); i++) s.step();
}
// The first scoop from the start position, from any place facing sand.
const SCOOP = [
  [1.2, { boom: -1 }],
  [1.6, { stick: 1 }],
  [3.5, { bucket: 1 }],
  [2, { boom: 1 }],
];

test("every start position is clear, level, on hard ground, facing sand and has its own space", () => {
  assert.ok(SPAWNS.length >= DEFAULT_PLAYERS);
  assert.ok(PAINTS.length >= DEFAULT_PLAYERS);
  assert.equal(new Set(PAINTS).size, PAINTS.length);
  assert.deepEqual(spawnMachine(0), initialMachine(), "the first keeps the original start");
  const halfLength = CONFIG.wheel_centres / 2 + CONFIG.sprocket_tip_radius_mm,
    halfWidth = CONFIG.track_outer_width_mm / 2,
    // From the machine's centre: its arm at the start pose, and the chase camera.
    ARM_REACH = 800,
    CAMERA_BEHIND = 1140,
    CAMERA_MARGIN = 60;
  const toWorld = ({ x, y, heading }, along, across) => [
    x + along * Math.cos(heading) - across * Math.sin(heading),
    y + along * Math.sin(heading) + across * Math.cos(heading),
  ];
  const toMachine = ({ x, y, heading }, px, py) => [
    (px - x) * Math.cos(heading) + (py - y) * Math.sin(heading),
    -(px - x) * Math.sin(heading) + (py - y) * Math.cos(heading),
  ];
  // A wall behind a machine would pull the chase camera right up to it.
  const walls = landscape().colliders.filter(cameraWall);
  const insideWall = (px, py) =>
    walls.some((k) =>
      k.hx === undefined
        ? Math.hypot(px - k.x, py - k.y) < k.r + 70
        : Math.abs((px - k.x) * k.c + (py - k.y) * k.s) < k.hx + 70 &&
          Math.abs(-(px - k.x) * k.s + (py - k.y) * k.c) < k.hy + 70,
    );
  SPAWNS.forEach((_, index) => {
    const seat = spawnMachine(index),
      { x, y, heading } = seat,
      name = `start ${index} at ${x}, ${y}`;
    assert.equal(
      crawlerHitsProp(x, y, Math.cos(heading), Math.sin(heading), halfLength, halfWidth),
      false,
      `${name} is on scenery`,
    );
    for (const along of [-halfLength, 0, halfLength])
      for (const across of [-halfWidth, 0, halfWidth]) {
        const [px, py] = toWorld(seat, along, across);
        assert.equal(initialSand(px, py), 0, `${name} is on sand`);
        assert.ok(
          Math.abs(groundHeight(px, py) - groundHeight(x, y)) < 12,
          `${name} is not level`,
        );
      }
    assert.ok(initialSand(...toWorld(seat, 600, 0)) > 100, `${name} has no sand ahead`);
    for (let along = -CAMERA_BEHIND; along <= 420; along += 20)
      assert.equal(insideWall(...toWorld(seat, along, 0)), false, `${name} has a wall behind`);
    SPAWNS.forEach((_, otherIndex) => {
      if (otherIndex === index) return;
      const other = spawnMachine(otherIndex);
      assert.equal(crawlersOverlap(seat, other), false, `${name} overlaps ${otherIndex}`);
      // Nobody starts between another player and their camera, arm included.
      for (let along = -halfLength; along <= ARM_REACH; along += 20)
        for (let across = -halfWidth; across <= halfWidth; across += 20) {
          const [u, v] = toMachine(seat, ...toWorld(other, along, across));
          assert.ok(
            !(u > -CAMERA_BEHIND && u < 0 && Math.abs(v) < CAMERA_MARGIN),
            `start ${otherIndex} blocks the camera of ${name}`,
          );
        }
    });
  });
});

test("frame jitter is small on a steady link, grows on a bad one and forgets a stall", () => {
  const TICK_MS = 1000 / 30;
  const feed = (jitter, delays) =>
    delays.forEach((delay, tick) => jitter.arrived(tick, tick * TICK_MS + delay));
  const steady = new FrameJitter(30);
  feed(steady, Array(200).fill(4));
  assert.ok(steady.ticks < 0.01);
  // A connection whose frames wander by 40 ms: over a tick's worth of unevenness.
  const bad = new FrameJitter(30);
  feed(bad, Array.from({ length: 200 }, (_, i) => (i % 2 ? 40 : 0)));
  assert.ok(bad.ticks > 1, `${bad.ticks}`);
  // One stall of 300 ms on a good link barely moves it, and soon passes.
  const stall = new FrameJitter(30);
  feed(stall, Array.from({ length: 41 }, (_, i) => (i === 40 ? 300 : 0)));
  assert.ok(stall.ticks < 0.7, `${stall.ticks}`);
  const after = stall.ticks;
  for (let tick = 41; tick < 100; tick++) stall.arrived(tick, tick * TICK_MS + 300);
  assert.ok(stall.ticks < after / 10, `${stall.ticks}`);
  // A frame numbered from zero again is a reset, not a late frame.
  const reset = new FrameJitter(30);
  feed(reset, Array(50).fill(0));
  reset.arrived(0, 99999);
  assert.ok(reset.ticks < 0.01);
});

test("names are short, one line and never empty by accident", () => {
  assert.equal(cleanName("  Ada   Lovelace "), "Ada Lovelace");
  assert.equal(cleanName("a\u0000b‮c\nd"), "abc d");
  assert.equal(cleanName("挖掘机司机"), "挖掘机司机");
  assert.equal([...cleanName("x".repeat(100))].length, 16);
  assert.equal([...cleanName("🚜".repeat(100))].length, 16);
  assert.equal(cleanName("\u0000​  "), "");
  assert.equal(cleanName(7), "");
  assert.equal(cleanName(null), "");
});

test(
  "two machines dig the same sand: each keeps its own load",
  { timeout: 120000 },
  () => {
    const s = world([spawnMachine(0), spawnMachine(1)]),
      volume = s.totalVolume();
    for (const [seconds, axes] of SCOOP) run(s, seconds, axes, axes);
    const [a, b] = s.vehicles;
    assert.ok(a.stats.load > 150, `the first machine loads (${a.stats.load})`);
    assert.ok(b.stats.load > 150, `the second machine loads (${b.stats.load})`);
    // One carries on and pours; the other holds still and keeps its load.
    const held = b.stats.load;
    run(s, 1.5, { slew: 1 }, {});
    run(s, 4, { bucket: -1 }, {});
    run(s, 1.5);
    assert.equal(a.stats.load, 0, "the first machine has poured");
    assert.ok(s.world.deposited > 100, `delivered ${s.world.deposited} cm³`);
    assert.ok(
      b.stats.load > held * 0.85,
      `the other load stays put (${b.stats.load} of ${held} cm³)`,
    );
    assert.ok(near(s.totalVolume(), volume, 1), "sand volume is conserved");
  },
);

test("sand poured into a bucket joins its load, and what does not fit falls on", () => {
  const s = world([{ ...initialMachine(), strokes: [26, 20, 52] }]),
    [v] = s.vehicles,
    load = v.load,
    volume = s.totalVolume(),
    point = mouthToLocal(50, 0, 40, [0, 0, 0]),
    above = [0, 0, 0];
  run(s, 0.1);
  v.frame.toWorld(point[0], point[1], point[2], above);
  // Straight down into the mouth, which faces up in this pose.
  const pour = (amount) => {
    s.spawn(above[0], above[1], above[2], 0, 0, 0, amount, v);
    for (let i = 0; i < 480 && s.grains; i++) s.substep(1 / 120);
    assert.equal(s.grains, 0, "it has landed");
  };
  pour(SAND.grainVolume);
  assert.ok(near(load.total, SAND.grainVolume, 1e-6), `it holds ${load.total} mm³`);
  assert.ok(near(s.totalVolume(), volume + SAND.grainVolume, 1e-3));
  // With room for only a little more, the rest goes on to the ground.
  const add = load.add.bind(load);
  let room = 100;
  load.add = (x, y, z, amount) => {
    const taken = add(x, y, z, Math.min(amount, room));
    room -= taken;
    return taken;
  };
  pour(SAND.grainVolume);
  assert.ok(near(load.total, SAND.grainVolume + 100, 1e-6), `it holds ${load.total} mm³`);
  assert.ok(near(s.totalVolume(), volume + 2 * SAND.grainVolume, 1e-3));
});

test("a second machine does not change what a solo dig does until it arrives", () => {
  // The same scripted dig, alone and with a parked machine far away. Each bucket
  // holds its own sand, so the numbers must match exactly.
  const dig = (machines) => {
    const s = world(machines);
    for (const [seconds, axes] of SCOOP) run(s, seconds, axes);
    return [s.grains, s.vehicles[0].stats.load, s.totalVolume()];
  };
  assert.deepEqual(
    dig([initialMachine(), spawnMachine(16)]),
    dig([initialMachine()]),
  );
});

test("crawlers stop at each other, and can always back away", () => {
  const a = initialMachine(),
    b = { ...initialMachine(), x: 900 },
    s = world([a, b]),
    [first, second] = s.vehicles;
  run(s, 0.1);
  run(s, 4, { leftTrack: 1, rightTrack: 1 });
  assert.equal(first.obstacle, "machine");
  assert.equal(first.stats.obstacle, "machine");
  assert.equal(crawlersOverlap(first.machine, second.machine), false);
  assert.ok(first.machine.x > 500, "it drove up to the other machine");
  assert.equal(second.machine.x, 900, "and did not push it");
  // Backing away works, and so does turning it no longer blocks.
  const stopped = first.machine.x;
  run(s, 0.5, { leftTrack: -1, rightTrack: -1 });
  assert.ok(first.machine.x < stopped - 50);
  assert.equal(first.obstacle, null);
  // Two machines moved on top of each other can part in any direction.
  second.machine.x = first.machine.x + 100;
  second.machine.y = 0;
  assert.equal(crawlersOverlap(first.machine, second.machine), true);
  const before = first.machine.x;
  run(s, 1, { leftTrack: 1, rightTrack: 1 });
  assert.equal(first.machine.x, before, "closer is refused");
  run(s, 2, { leftTrack: -1, rightTrack: -1 });
  assert.ok(first.machine.x < before - 200, "further away is allowed");
  // A turn into a neighbour is refused too, whichever part would hit.
  const c = world([
    { ...initialMachine(), x: -600, y: 0 },
    { ...initialMachine(), x: -600, y: 420 },
  ]);
  run(c, 0.5, { leftTrack: 1, rightTrack: -1 });
  assert.equal(c.vehicles[0].obstacle, "machine");
});

test("the arm stays free: boom and slew travel ignore other machines", () => {
  // Only the hard ground stops a bucket. Parked side by side, one machine's arm
  // swings over the other through its whole travel.
  const s = world([
      initialMachine(),
      { ...initialMachine(), y: 450 },
    ]),
    [first] = s.vehicles;
  run(s, 2, { boom: 1 });
  const stroke = first.machine.strokes[0];
  assert.ok(stroke > 30);
  run(s, 6, { slew: 1 });
  assert.equal(first.machine.slew, 150);
  run(s, 12, { slew: -1 });
  assert.equal(first.machine.slew, -150);
  assert.equal(first.obstacle, null);
  run(s, 3, { boom: 1 });
  assert.equal(first.machine.strokes[0], 60);
});

test("a machine that leaves drops its load and no sand is lost", { timeout: 60000 }, () => {
  const s = world([initialMachine(), spawnMachine(1)]),
    volume = s.totalVolume();
  for (const [seconds, axes] of SCOOP) run(s, seconds, axes, {});
  const [a, b] = s.vehicles,
    held = a.stats.load;
  assert.ok(held > 150);
  s.removeVehicle(a);
  assert.equal(s.vehicles.length, 1);
  assert.equal(a.load.total, 0, "no sand stays in a bucket that has gone");
  assert.ok(s.grains * SAND.grainVolume >= held * 900, "it falls as parcels");
  assert.ok(near(s.totalVolume(), volume, 1));
  for (let i = 0; i < 180; i++) s.step();
  assert.equal(s.grains, 0, "the load falls and settles");
  assert.ok(near(s.totalVolume(), volume, 1));
  assert.equal(b.stats.load, 0);
  // A slot freed by one machine serves the next without any stale sand.
  const c = s.addVehicle(9, spawnMachine(2));
  assert.equal(c.slot, 0);
  for (let i = 0; i < 300; i++) s.step();
  assert.equal(c.stats.load, 0);
  assert.ok(near(s.totalVolume(), volume, 1));
});

test("jumping back to a start position leaves the load behind", { timeout: 60000 }, () => {
  const s = world([initialMachine()]),
    [v] = s.vehicles,
    volume = s.totalVolume();
  for (const [seconds, axes] of SCOOP) run(s, seconds, axes);
  assert.ok(v.stats.load > 150);
  const elsewhere = spawnMachine(2);
  s.placeVehicle(v, elsewhere);
  assert.deepEqual(v.machine, elsewhere);
  assert.deepEqual(
    [v.frame.x, v.frame.y, v.frame.z],
    [v.prevFrame.x, v.prevFrame.y, v.prevFrame.z],
    "the bucket does not sweep through everything between",
  );
  run(s, 4);
  assert.equal(v.stats.load, 0);
  assert.equal(s.grains, 0);
  assert.ok(near(s.totalVolume(), volume, 1));
  assert.ok(s.resting, "the world comes to rest again");
});

test(
  "a full room digging at once: every machine gets a full scoop",
  { timeout: 180000 },
  () => {
    const s = world(
        SPAWNS.slice(0, DEFAULT_PLAYERS).map((_, n) => spawnMachine(n)),
      ),
      volume = s.totalVolume();
    let slowest = 0;
    for (const [seconds, axes] of SCOOP) {
      axesFor(s, s.vehicles.map(() => axes));
      for (let i = 0; i < Math.round(seconds * 30); i++) {
        const start = performance.now();
        s.step();
        slowest = Math.max(slowest, performance.now() - start);
      }
    }
    const loads = s.vehicles.map((v) => v.stats.load);
    assert.ok(
      loads.every((load) => load > 200),
      `everyone gets a load (${loads})`,
    );
    assert.ok(near(s.totalVolume(), volume, 1));
    console.log(
      `${loads.length} machines digging: loads ${loads} cm³, slowest tick ${slowest.toFixed(1)} ms.`,
    );
  },
);

test("a packed world is exact wherever the parcels are and whichever bucket they left", () => {
  const s = world([initialMachine(), { ...initialMachine(), x: -19000, y: 19000 }]),
    [a, b] = s.vehicles;
  // A parcel in each bucket's reach and two far from both, at the world's corners.
  const pose = bucketPose(b.machine);
  const spots = [
    [a.frame.x, a.frame.y, a.frame.z - 40, a],
    [pose.x, pose.y, pose.z - 40, b],
    [20400, -20400, 3000, null],
    [-20400, -20400, -500, null],
  ];
  for (const [x, y, z, holder] of spots) {
    const i = s.spawn(x, y, z, 0, 0, 0, SAND.grainVolume, holder ?? a);
    if (!holder) s.near[i] = 0;
  }
  const { grains, groups } = s.packGrains(),
    frame = decodeFrame(
      encodeFrame({
        tick: 1,
        machines: [],
        grains,
        groups,
        tileData: new Map(),
        tiles: [],
      }),
    );
  assert.equal(frame.slots.length, 4);
  for (let n = 0; n < 4; n++) {
    const i = frame.slots[n];
    for (let d = 0; d < 3; d++)
      assert.ok(
        Math.abs(frame.positions[3 * n + d] - s.pos[3 * i + d]) <=
          SAND.positionQuantum,
        `grain ${i} axis ${d}: ${frame.positions[3 * n + d]} vs ${s.pos[3 * i + d]}`,
      );
    assert.equal(frame.holders[n], spots[i][3] ? spots[i][3].id : 0);
  }
});

// ------------------------------------------------------------------- network
async function waitFor(check, what = "condition", timeout = 6000) {
  const start = Date.now();
  while (!check()) {
    assert.ok(Date.now() - start < timeout, `timed out waiting for ${what}`);
    await delay(15);
  }
}
async function join(socket, room, { role = "simulator", key, name } = {}) {
  const query = new URLSearchParams({ room, role });
  if (key) query.set("key", key);
  if (name) query.set("name", name);
  const ws = new WebSocket(`${socket}/ws?${query}`),
    client = { ws, messages: [], binary: 0 };
  ws.on("message", (buffer, binary) => {
    if (binary) {
      client.binary++;
      client.frame = decodeFrame(Uint8Array.from(buffer));
      return;
    }
    const message = JSON.parse(buffer);
    client.messages.push(message);
    if (message.type === "welcome") {
      client.id = message.id;
      client.player = message.player;
    }
    if (message.type === "state") client.state = message;
    if (message.type === "roster") client.roster = message;
  });
  await once(ws, "open");
  await waitFor(() => client.player && client.state && client.roster, "welcome");
  client.send = (body) => ws.send(JSON.stringify(body));
  client.drive = (axes) =>
    client.send({ type: "input", axes: { ...neutral(), ...axes }, speed: 1 });
  client.errors = () => client.messages.filter((m) => m.type === "error");
  return client;
}
async function startApp(options) {
  const app = createApplication({ maxRooms: 1, ...options });
  await new Promise((resolve) => app.server.listen(0, "127.0.0.1", resolve));
  const origin = `http://127.0.0.1:${app.server.address().port}`,
    { room } = await (
      await fetch(`${origin}/api/rooms`, { method: "POST" })
    ).json();
  return { app, origin, room, socket: origin.replace("http", "ws") };
}
const claim = async (client) => {
  client.send({ type: "claim" });
  await waitFor(() => client.state.owner === client.id, "control");
};

test(
  "everyone in a room gets an excavator of their own and sees all of them",
  { timeout: 30000 },
  async () => {
    const { app, origin, room, socket } = await startApp();
    try {
      const ada = await join(socket, room, { name: "Ada" }),
        ben = await join(socket, room, { name: "  Ben\u0000 " }),
        cam = await join(socket, room, { role: "remote" });
      assert.deepEqual(
        new Set([ada.player.id, ben.player.id, cam.player.id]).size,
        3,
      );
      assert.equal(ada.player.name, "Ada");
      assert.equal(ben.player.name, "Ben");
      assert.equal(cam.player.name, "Player 3");
      assert.equal(new Set([ada, ben, cam].map((c) => c.player.paint)).size, 3);
      assert.ok(
        !crawlersOverlap(ada.state.machine, ben.state.machine) &&
          !crawlersOverlap(ben.state.machine, cam.state.machine),
        "each starts in a free place",
      );
      assert.deepEqual([ada.state.machine.x, ada.state.machine.y], [0, 0]);
      await waitFor(
        () =>
          ada.roster.players.length === 3 && ben.roster.players.length === 3,
        "the roster",
      );
      assert.deepEqual(
        ada.roster.players.map((p) => p.name),
        ["Ada", "Ben", "Player 3"],
      );
      assert.equal(ada.roster.host, ada.player.id);
      assert.equal(ada.state.host, true);
      assert.equal(ben.state.host, false);
      assert.equal(
        JSON.stringify(ada.roster).includes(ben.player.key),
        false,
        "the roster gives away nobody's key",
      );
      assert.equal(
        (await (await fetch(`${origin}/api/health`)).json()).players,
        3,
      );

      // Each frame carries every machine, and a phone still gets only telemetry.
      await waitFor(() => ada.frame?.machines.length === 3, "three machines");
      assert.deepEqual(
        ada.frame.machines.map((m) => m.id).sort(),
        [ada.player.id, ben.player.id, cam.player.id].sort(),
      );
      assert.equal(cam.binary, 0);

      // Controls move your own machine and nobody else's.
      await claim(ada);
      await claim(ben);
      assert.equal(ada.state.owner, ada.id, "both operate at the same time");
      const benBoom = ben.state.machine.strokes[0];
      for (let i = 0; i < 6; i++) {
        ada.drive({ boom: 1 });
        await delay(60);
      }
      await waitFor(() => ada.state.machine.strokes[0] > 11, "the boom");
      assert.equal(ben.state.machine.strokes[0], benBoom);
      const other = ada.frame.machines.find((m) => m.id === ben.player.id);
      assert.equal(other.strokes[0], benBoom, "seen from another browser too");
      ben.drive({ leftTrack: 1, rightTrack: -1 });
      ada.drive({ boom: -1 });
      await waitFor(
        () => ben.state.machine.heading < -0.01,
        "two machines moving in the same tick",
      );
      assert.equal(cam.state.machine.heading, 0);
      assert.ok(ada.state.machine.strokes[0] > 0);

      // An emergency stop stops one machine; the others carry on.
      ben.send({ type: "input", axes: neutral(), speed: 1 });
      ben.send({ type: "estop" });
      await waitFor(() => ben.state.estop, "the stop");
      assert.equal(ada.state.estop, false, "a stop is per machine");
      const heading = ben.state.machine.heading;
      ben.drive({ leftTrack: 1, rightTrack: -1 });
      for (let i = 0; i < 8; i++) {
        ada.drive({ bucket: 1 });
        await delay(40);
      }
      await waitFor(() => ada.state.machine.strokes[2] > 1, "the bucket");
      assert.equal(ben.state.machine.heading, heading);
      ben.send({ type: "resume" });
      await waitFor(() => !ben.state.estop, "resume");

      // Renaming reaches everyone, and is cleaned on the way.
      ben.send({ type: "rename", name: " Ben‮ Two " });
      await waitFor(
        () => ada.roster.players[1].name === "Ben Two",
        "the new name",
      );
      ben.send({ type: "rename", name: "\u0000" });
      await waitFor(() => ben.errors().length === 1, "a refused name");
      assert.equal(ada.roster.players[1].name, "Ben Two");
    } finally {
      await app.close();
    }
  },
);

test(
  "a phone pairs with its owner's excavator by key, and devices share one lease",
  { timeout: 30000 },
  async () => {
    const { app, room, socket } = await startApp();
    try {
      const desktop = await join(socket, room),
        visitor = await join(socket, room),
        phone = await join(socket, room, {
          role: "remote",
          key: desktop.player.key,
        });
      assert.equal(phone.player.id, desktop.player.id, "the same excavator");
      assert.equal(phone.roster.players.length, 2, "no extra machine appeared");
      assert.equal(phone.binary, 0);

      await claim(phone);
      await waitFor(() => desktop.state.owner === phone.id, "the desktop to hear");
      desktop.send({ type: "claim" });
      await waitFor(() => desktop.errors().length === 1, "the refused claim");
      assert.match(desktop.errors()[0].message, /other device/);
      assert.equal(desktop.state.owner, phone.id);
      desktop.drive({ boom: 1 });
      await delay(100);
      assert.equal(desktop.state.machine.strokes[0], 10, "it is not the operator");

      // Someone else in the room is not affected and cannot interfere.
      await claim(visitor);
      assert.equal(desktop.state.owner, phone.id);
      visitor.send({ type: "release" });
      await waitFor(() => visitor.state.owner === null, "the visitor's release");
      assert.equal(desktop.state.owner, phone.id);

      // A stop from either device of a player latches their machine.
      desktop.send({ type: "estop" });
      await waitFor(() => phone.state.estop, "the stop on the phone");
      assert.equal(visitor.state.estop, false);
      phone.send({ type: "resume" });
      await waitFor(() => !desktop.state.estop, "resume");

      // Control moves on when the phone goes away.
      phone.ws.terminate();
      await waitFor(() => desktop.state.owner === null, "the lease to end");
      await claim(desktop);
    } finally {
      await app.close();
    }
  },
);

test(
  "a dropped player gets their machine back, and leaves for good after the grace period",
  { timeout: 30000 },
  async () => {
    const { app, room, socket } = await startApp({ graceMs: 400 });
    try {
      const ada = await join(socket, room, { name: "Ada" }),
        ben = await join(socket, room, { name: "Ben" });
      await claim(ben);
      ben.send({
        type: "input",
        axes: { ...neutral(), leftTrack: 1, rightTrack: 1 },
        speed: 1,
      });
      const { key, id } = ben.player;
      await waitFor(() => ben.state.machine.x > 421, "ben to move");
      const x = ben.state.machine.x;
      ben.ws.terminate();
      // The machine stays where it was, stopped, and shows as offline.
      await waitFor(
        () => ada.roster.players.find((p) => p.id === id)?.online === false,
        "the offline mark",
      );
      const back = await join(socket, room, { key });
      assert.equal(back.player.id, id, "the same excavator");
      assert.equal(back.player.name, "Ben");
      assert.ok(back.state.machine.x >= x, "in the same place");
      assert.equal(back.state.owner, null, "reconnecting starts with no lease");
      await waitFor(
        () => ada.roster.players.find((p) => p.id === id)?.online === true,
        "the online mark",
      );
      back.ws.terminate();
      await waitFor(
        () => ada.roster.players.length === 1,
        "the grace period to end",
      );
      await waitFor(() => ada.frame?.machines.length === 1, "the machine to go");
      assert.equal(app.rooms.get(room).simulation.vehicles.size, 1);
      // The old key means nothing now: it joins as somebody new.
      const stranger = await join(socket, room, { key, name: "Cam" });
      assert.notEqual(stranger.player.id, id);
      assert.notEqual(stranger.player.key, key);
      assert.equal(
        stranger.player.paint,
        ben.player.paint,
        "a freed paint comes back into use",
      );

      // The host's duties pass on, and the room's work goes on.
      assert.equal(ada.state.host, true);
      ada.ws.terminate();
      await waitFor(() => stranger.roster.players.length === 1, "ada to leave");
      await waitFor(() => stranger.state.host, "a new host");
      assert.equal(stranger.roster.host, stranger.player.id);
    } finally {
      await app.close();
    }
  },
);

test("a full room turns newcomers away but not returning players", { timeout: 30000 }, async () => {
  const { app, origin, room, socket } = await startApp({ maxPlayers: 2 });
  try {
    const ada = await join(socket, room),
      ben = await join(socket, room);
    const lookup = async (query = "") =>
      (await fetch(`${origin}/api/rooms/${room}${query}`)).json();
    assert.deepEqual(await lookup(), {
      room,
      players: 2,
      capacity: 2,
      member: false,
    });
    assert.equal((await lookup(`?key=${ada.player.key}`)).member, true);
    const third = new WebSocket(`${socket}/ws?room=${room}`);
    third.on("error", () => {});
    const [failed, rejection] = await once(third, "unexpected-response");
    assert.equal(rejection.statusCode, 403);
    failed.destroy();
    third.terminate();
    // More devices for the same player do not need a new seat.
    const phone = await join(socket, room, {
      role: "remote",
      key: ben.player.key,
    });
    assert.equal(phone.player.id, ben.player.id);
    // But a key cannot open any number of connections.
    const extras = [];
    for (let i = 0; i < 2; i++)
      extras.push(await join(socket, room, { key: ben.player.key }));
    const over = new WebSocket(`${socket}/ws?room=${room}&key=${ben.player.key}`);
    over.on("error", () => {});
    const [refused, status] = await once(over, "unexpected-response");
    assert.equal(status.statusCode, 403);
    refused.destroy();
    over.terminate();
  } finally {
    await app.close();
  }
});

test(
  "only the host resets the world; anyone can go back to a start position",
  { timeout: 30000 },
  async () => {
    const { app, room, socket } = await startApp();
    try {
      const ada = await join(socket, room, { name: "Ada" }),
        ben = await join(socket, room, { name: "Ben" });
      await claim(ada);
      await claim(ben);
      const benStart = ben.state.machine.x;
      for (let i = 0; i < 8; i++) {
        ada.drive({ boom: 1 });
        ben.drive({ leftTrack: 1, rightTrack: 1 });
        await delay(60);
      }
      await waitFor(
        () => ada.state.machine.strokes[0] > 11 && ben.state.machine.x > benStart + 8,
        "both to move",
      );
      ben.send({ type: "reset" });
      await waitFor(() => ben.errors().length === 1, "the refusal");
      assert.match(ben.errors()[0].message, /host/);

      // Going back moves one machine only, and leaves the sand as it is.
      ada.send({ type: "input", axes: neutral(), speed: 1 });
      ben.send({ type: "input", axes: neutral(), speed: 1 });
      ben.send({ type: "respawn" });
      await waitFor(() => ben.state.machine.x === benStart, "ben to go back");
      assert.ok(ada.state.machine.strokes[0] > 10, "ada is untouched");

      // A stop stays latched through either kind of move.
      ben.send({ type: "estop" });
      await waitFor(() => ben.state.estop, "the stop");
      for (let i = 0; i < 4; i++) {
        ada.send({ type: "input", axes: { ...neutral(), bucket: 1 }, speed: 1 });
        await delay(40);
      }
      ada.send({ type: "reset" });
      await waitFor(() => ada.state.machine.strokes[0] === 10, "the reset");
      assert.equal(ben.state.machine.x, benStart);
      assert.equal(ben.state.estop, true, "reset must not clear a latched stop");
      await waitFor(
        () => ben.messages.some((m) => m.type === "notice"),
        "the notice",
      );
      assert.equal(
        ben.messages.find((m) => m.type === "notice").message,
        "Ada reset the world.",
      );
      assert.equal(
        ada.messages.some((m) => m.type === "notice"),
        false,
        "the one who did it is not told",
      );
    } finally {
      await app.close();
    }
  },
);

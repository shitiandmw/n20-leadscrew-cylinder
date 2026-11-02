import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  SandSimulation,
  bucketPose,
  toLocal,
  toWorld,
  insideProfile,
} from "../server/physics.js";
import { solve } from "../shared/kinematics.js";
import {
  WORLD,
  neutral,
  groundHeight,
  crawlerExtent,
} from "../shared/world.js";

test("all 125 original CAD kinematic cases remain unchanged", () => {
  const cases = JSON.parse(
    readFileSync(new URL("./kinematic-cases.json", import.meta.url)),
  );
  for (const c of cases) {
    const actual = solve(c.strokes).p;
    for (const [name, expected] of Object.entries(c.points))
      assert.ok(
        Math.hypot(
          actual[name][0] - expected[0],
          actual[name][1] - expected[1],
        ) < 1e-7,
        `${c.strokes}: ${name}`,
      );
  }
});

test("bucket collision profile has solid walls and an open mouth", () => {
  const s = new SandSimulation(),
    pose = bucketPose(s.machine);
  const roundtrip = toLocal(...toWorld(10, -15, -55, pose), pose);
  assert.ok(
    Math.hypot(...roundtrip.map((v, i) => v - [10, -15, -55][i])) < 1e-9,
  );
  assert.equal(insideProfile(0, -50), true);
  assert.equal(insideProfile(-100, -50), false);
  s.positions.set(toWorld(44, 0, -50, pose), 0); // curved rear wall
  s.collideBucket(0, pose);
  assert.equal(s.bucketContacts[0], 1);
  s.bucketContacts[0] = 0;
  const mouth = toWorld(-38.4, 0, -39.6, pose); // open last-to-first edge
  s.positions.set(mouth, 0);
  s.collideBucket(0, pose);
  assert.equal(s.bucketContacts[0], 0);
  assert.ok(Math.hypot(...mouth.map((v, i) => s.positions[i] - v)) < 1e-4);
  s.positions.set(toWorld(0, 38, -50, pose), 0);
  s.collideBucket(0, pose);
  assert.equal(s.bucketContacts[0], 1, "cheek plates contain grains laterally");
});

test(
  "physical scoop, lift, swing and pour conserves particles",
  { timeout: 60000 },
  () => {
    const s = new SandSimulation();
    s.speed = 1;
    const run = (seconds, axes) => {
      s.axes = { ...neutral(), ...axes };
      for (let i = 0; i < Math.round(seconds * 30); i++) s.step();
      assert.equal(s.count, 1876);
      for (const value of s.positions) assert.ok(Number.isFinite(value));
    };
    run(0.5, {});
    const settled = s.positions.slice();
    run(0.5, {});
    const movement =
      s.positions.reduce((sum, v, i) => sum + Math.abs(v - settled[i]), 0) /
      s.positions.length;
    assert.ok(
      movement < 0.1,
      `resting pile must hold its shape (${movement} mm drift)`,
    );
    assert.equal(s.stats.deposited, 0);
    run(0.8, { boom: -1 });
    run(1.5, { stick: 1 });
    run(4, { bucket: 1 });
    assert.ok(s.stats.carried >= 10, "bucket must scoop real grains");
    const loaded = s.stats.carried;
    run(2, { boom: 1 });
    assert.ok(
      s.stats.carried >= loaded * 0.8,
      "curled bucket must retain its load during lifting",
    );
    assert.ok(
      Math.max(...s.positions.filter((_, i) => i % 3 === 2)) > 150,
      "grains must rise with the bucket",
    );
    run(1.5, { slew: 1 });
    assert.ok(
      s.stats.carried >= loaded * 0.8,
      "load must travel through a 45 degree swing",
    );
    run(4, { bucket: -1 });
    run(1, {});
    assert.equal(s.stats.carried, 0, "opening the bucket releases its load");
    assert.ok(
      s.stats.deposited >= 10,
      "grains must fall into the marked receiving area",
    );
    for (let i = 0; i < s.count; i++) {
      assert.ok(
        s.positions[3 * i + 2] >= WORLD.floor + WORLD.radius - 0.01,
        "no grains below the floor",
      );
      assert.ok(
        s.positions[3 * i] >= WORLD.minX && s.positions[3 * i] <= WORLD.maxX,
      );
    }
    console.log(
      `Scoop/pour: ${loaded} grains loaded; ${s.stats.deposited} deposited; ${s.count} conserved.`,
    );
  },
);

test("boom remains independent of slew and all controls obey their limits", () => {
  const s = new SandSimulation();
  s.speed = 1;
  for (const slew of [-150, -75, 0, 75, 150]) {
    s.machine.slew = slew;
    s.machine.strokes[0] = 20;
    s.axes = { ...neutral(), boom: -1 };
    s.advanceMachine(10);
    assert.equal(s.machine.strokes[0], 0);
    assert.equal(s.machine.slew, slew);
    s.axes.boom = 1;
    s.advanceMachine(10);
    assert.equal(s.machine.strokes[0], 60);
  }
  s.estop = true;
  const before = structuredClone(s.machine);
  s.axes = Object.fromEntries(Object.keys(neutral()).map((k) => [k, 1]));
  s.advanceMachine(10);
  assert.deepEqual(s.machine, before);
});

test("crawler reaches every map edge and turns without crossing the walls", () => {
  const s = new SandSimulation();
  s.speed = 1;
  for (let direction = 0; direction < 8; direction++) {
    s.machine.heading = (direction * Math.PI) / 4;
    s.axes = { ...neutral(), leftTrack: 1, rightTrack: 1 };
    s.advanceMachine(60);
    const extent = crawlerExtent(s.machine.heading);
    if (Math.cos(s.machine.heading) > 0.1)
      assert.equal(s.machine.x, WORLD.maxX - extent.x);
    if (Math.cos(s.machine.heading) < -0.1)
      assert.equal(s.machine.x, WORLD.minX + extent.x);
    if (Math.sin(s.machine.heading) > 0.1)
      assert.equal(s.machine.y, WORLD.maxY - extent.y);
    if (Math.sin(s.machine.heading) < -0.1)
      assert.equal(s.machine.y, WORLD.minY + extent.y);
    s.axes = { ...neutral(), leftTrack: -1, rightTrack: 1 };
    for (let i = 0; i < 100; i++) {
      s.advanceMachine(1 / 30);
      const turned = crawlerExtent(s.machine.heading);
      assert.ok(s.machine.x - turned.x >= WORLD.minX - 1e-9);
      assert.ok(s.machine.x + turned.x <= WORLD.maxX + 1e-9);
      assert.ok(s.machine.y - turned.y >= WORLD.minY - 1e-9);
      assert.ok(s.machine.y + turned.y <= WORLD.maxY + 1e-9);
    }
  }
});

test("crawler and bucket descend the ramp continuously and grains meet the terrain", () => {
  const s = new SandSimulation();
  const initial = bucketPose(s.machine);
  s.speed = 1;
  s.axes = { ...neutral(), leftTrack: 1, rightTrack: 1 };
  let height = 0;
  for (let i = 0; i < 300; i++) {
    s.advanceMachine(1 / 30);
    assert.ok(s.machine.z <= height);
    assert.ok(
      Math.abs(s.machine.z - height) < 2,
      "no vertical teleport at the apron edge",
    );
    height = s.machine.z;
  }
  assert.ok(s.machine.x > 600, "travel goes well beyond the former x=20 limit");
  assert.equal(height, WORLD.floor);
  assert.equal(bucketPose(s.machine).z - initial.z, WORLD.floor);
  for (const x of [0, WORLD.platformEdge, 250, WORLD.rampEnd, 900]) {
    s.positions.set([x, 0, -100], 0);
    s.boundaries(0);
    assert.equal(s.positions[2], groundHeight(x) + WORLD.radius);
  }
  s.axes = { ...neutral(), leftTrack: -1, rightTrack: -1 };
  s.advanceMachine(10);
  assert.equal(s.machine.z, 0, "reverse travel returns to apron height");
});

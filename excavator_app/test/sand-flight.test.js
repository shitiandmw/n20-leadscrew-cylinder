import test from "node:test";
import assert from "node:assert/strict";
import { Scene, Texture } from "three";
import { flightRoom, ParcelMotion } from "../client/sand-flight.js";
import { createLooseSandView } from "../client/loose-sand-view.js";
import { BUCKET, initialMachine } from "../shared/world.js";

test("falling detail clears the mouth and tapers before the bucket", () => {
  assert.equal(flightRoom(0, 0, -45), 0, "carried sand keeps its shape");
  assert.equal(flightRoom(0, BUCKET.innerHalfWidth - 4, -45), 0);
  assert.equal(
    flightRoom(0, BUCKET.outerHalfWidth + 4, -45),
    0,
    "an outside cheek contact cannot spread through the plate",
  );
  assert.ok(
    flightRoom(-120, 0, -40) > 0,
    "clear of the mouth, grains can separate",
  );
  assert.ok(
    flightRoom(-120, 0, -4000) <= 12,
    "spread remains bounded in a long fall",
  );
});

test("stream motion uses simulation time and rejects gaps, jumps and slot reuse", () => {
  const motion = new ParcelMotion(4),
    velocity = [0, 0, 0];
  motion.between(1, 10, 11, 0, 0, 100, 2, 0, 80);
  motion.read(1, 11, velocity);
  assert.deepEqual(velocity, [60, 0, -600]);
  motion.read(1, 11, velocity);
  assert.deepEqual(
    velocity,
    [60, 0, -600],
    "holding a snapshot preserves its exposure",
  );
  motion.read(1, 12, velocity);
  assert.deepEqual(
    velocity,
    [0, 0, 0],
    "a stale velocity is not reused for a new packet",
  );
  motion.between(1, 11, 41, 2, 0, 80, 4, 0, 60);
  motion.read(1, 41, velocity);
  assert.deepEqual(velocity, [0, 0, 0], "reconnection does not create a trail");
  motion.between(1, 41, 42, 4, 0, 60, 1000, 0, 50);
  motion.read(1, 42, velocity);
  assert.deepEqual(velocity, [0, 0, 0], "teleport or reused slot");
  motion.between(1, 42, 43, 4, 0, 60, 4, 0, 40);
  motion.forget(1);
  motion.read(1, 43, velocity);
  assert.deepEqual(velocity, [0, 0, 0]);
  motion.between(1, 42, 43, 4, 0, 60, 4, 0, 40);
  motion.clear();
  motion.read(1, 43, velocity);
  assert.deepEqual(velocity, [0, 0, 0]);
});

test("rendered stream uses each bucket's frame", () => {
  const scene = new Scene(),
    machine = initialMachine(),
    poses = new Map([[3, machine]]);
  const view = createLooseSandView(scene, new Texture(), false, () => 0);
  const makeFrame = (tick, z, holder = 0) => ({
    tick,
    slots: Uint16Array.from([7]),
    holders: Uint16Array.from([holder]),
    positions: Float32Array.from([1000, 1000, z]),
    machines: [],
    byId: new Map(),
  });
  const a = makeFrame(10, 100),
    b = makeFrame(11, 80);
  view.update(a, b, 0.5, poses);
  const points = scene.children.find((child) => child.isPoints);
  const flight = points.geometry.getAttribute("flight").array;
  assert.deepEqual([...flight.slice(0, 3)], [0, 0, -600]);
  assert.ok(flight[3] > 0, "airborne material may spread");
  view.pushFrame(a);
  view.pushFrame(b, a);
  view.update(b, b, 0, poses);
  assert.deepEqual(
    [...flight.slice(0, 3)],
    [0, 0, -600],
    "a skipped render frame retains the motion computed on packet arrival",
  );
  view.clear();
  view.pushFrame(b);
  view.update(b, b, 0, poses);
  assert.deepEqual(
    [...flight.slice(0, 3)],
    [0, 0, 0],
    "reset removes previous flight history",
  );
});

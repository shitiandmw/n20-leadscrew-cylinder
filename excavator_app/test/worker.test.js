import test from "node:test";
import assert from "node:assert/strict";
import { SimulationRunner } from "../server/simulation-runner.js";
import { TILE_COUNT } from "../shared/protocol.js";
import { initialMachine, neutral } from "../shared/world.js";

test("worker coalesces steps, discards pre-reset frames, and preserves a latched stop", async () => {
  let frames = 0;
  const s = new SimulationRunner(
    () => frames++,
    (error) => {
      throw error;
    },
  );
  try {
    await s.ready;
    const v = s.addVehicle(1, initialMachine());
    const received = () =>
      new Promise((resolve) => s.worker.once("message", resolve));
    v.axes.boom = 1;
    let next = received();
    s.step();
    for (let i = 0; i < 100; i++) s.step();
    await next;
    assert.equal(s.tick, 1, "only one step can be in flight");
    assert.ok(v.machine.strokes[0] > 10);
    // A hundred requests leave one more step, not a backlog of a hundred.
    next = received();
    await next;
    assert.equal(s.tick, 2, "an overdue step follows straight away");
    assert.equal(s.busy, false, "and nothing more was queued");
    v.axes = neutral();
    next = received();
    s.step();
    v.estop = true;
    s.reset();
    await next;
    assert.equal(frames, 2, "the old worker frame cannot overwrite reset");
    assert.equal(v.machine.strokes[0], 10);
    v.axes.boom = 1;
    next = received();
    s.step();
    await next;
    assert.equal(v.machine.strokes[0], 10);
    assert.equal(v.estop, true, "a reset does not clear a latched stop");
    assert.ok(s.tileData.size > 1000, "the worker publishes the sand it holds");
    assert.ok(s.tileData.size < TILE_COUNT / 10, "and only that sand");
    assert.equal(s.grains.length % 4, 0);
    assert.equal(s.tileVersions.length, TILE_COUNT);
  } finally {
    await s.close();
  }
});

test("a busy worker cannot move the machine after a stop", async () => {
  const s = new SimulationRunner(
    () => {},
    (error) => {
      throw error;
    },
  );
  try {
    await s.ready;
    const v = s.addVehicle(1, initialMachine()),
      other = s.addVehicle(2, { ...initialMachine(), y: 800 }),
      before = structuredClone(v.machine);
    v.axes.leftTrack = 1;
    v.axes.rightTrack = -1;
    other.axes.leftTrack = 1;
    other.axes.rightTrack = -1;
    let next = new Promise((resolve) => s.worker.once("message", resolve));
    s.step();
    s.stop(v);
    await next;
    assert.deepEqual(
      v.machine,
      before,
      "discard motion computed before the stop",
    );
    assert.ok(
      other.machine.heading < 0,
      "another machine's motion in the same step still counts",
    );
    other.axes.leftTrack = 0;
    other.axes.rightTrack = 0;
    next = new Promise((resolve) => s.worker.once("message", resolve));
    s.step();
    await next;
    assert.deepEqual(
      v.machine,
      before,
      "the worker continues from the stopped pose",
    );
    assert.ok(s.tick > 0, "sand physics continues after stopping the machine");
  } finally {
    await s.close();
  }
});

import test from "node:test";
import assert from "node:assert/strict";
import { SimulationRunner } from "../server/simulation-runner.js";
import { TILE_COUNT } from "../shared/protocol.js";

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
    const received = () =>
      new Promise((resolve) => s.worker.once("message", resolve));
    s.axes.boom = 1;
    let next = received();
    s.step();
    for (let i = 0; i < 100; i++) s.step();
    await next;
    assert.equal(s.tick, 1, "only one step can be in flight");
    assert.ok(s.machine.strokes[0] > 10);
    next = received();
    s.step();
    s.reset();
    s.estop = true;
    await next;
    assert.equal(frames, 1, "the old worker frame cannot overwrite reset");
    assert.equal(s.machine.strokes[0], 10);
    s.axes.boom = 1;
    next = received();
    s.step();
    await next;
    assert.equal(s.machine.strokes[0], 10);
    assert.equal(s.estop, true);
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
    const before = structuredClone(s.machine);
    s.axes.leftTrack = 1;
    s.axes.rightTrack = -1;
    let next = new Promise((resolve) => s.worker.once("message", resolve));
    s.step();
    s.stop();
    await next;
    assert.deepEqual(
      s.machine,
      before,
      "discard motion computed before the stop",
    );
    next = new Promise((resolve) => s.worker.once("message", resolve));
    s.step();
    await next;
    assert.deepEqual(
      s.machine,
      before,
      "the worker continues from the stopped pose",
    );
    assert.ok(s.tick > 0, "sand physics continues after stopping the machine");
  } finally {
    await s.close();
  }
});

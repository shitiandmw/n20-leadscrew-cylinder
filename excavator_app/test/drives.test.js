import test from "node:test";
import assert from "node:assert/strict";
import {
  DRIVE,
  SCREW,
  armGravity,
  driveRate,
  holdForces,
  strokeTime,
} from "../shared/drives.js";
import { SandSimulation } from "../server/physics.js";
import { neutral, initialMachine } from "../shared/world.js";

const near = (a, b, tolerance) => Math.abs(a - b) <= tolerance;

// The R12 arm's own virtual-work statics (excavator_arm_r12/source/physics_r12.py,
// static_forces) with its 150 g payload at the struck load's centroid: boom per
// drive, stick and bucket, N. The first three are the worst holds in its README.
const PAYLOAD = [0.15, 39.8957, 38.1112];
const R12 = [
  [[60, 15, 35], [39.481, -18.258, -4.692], [27.284, -9.685, -1.704]],
  [[0, 60, 45], [21.162, 27.53, 5.97], [19.685, 14.14, 2.135]],
  [[40, 55, 60], [27.672, 4.834, 16.6], [22.673, 1.15, 5.655]],
  [[45, 38, 50], [33.308, -8.159, 0.884], [25.477, -5.256, 0.005]],
  [[0, 0, 0], [36.091, -10.917, -4.721], [27.536, -5.933, -1.71]],
  [[10, 12, 18], [33.875, -7.972, -3.251], [26.063, -4.528, -1.278]],
];

test("drive loads match the R12 arm's virtual-work statics", () => {
  for (const [strokes, loaded, empty] of R12) {
    const withLoad = holdForces(strokes, [0, -9.81], PAYLOAD),
      without = holdForces(strokes, [0, -9.81]);
    // The ends of the travel differ by the step of the finite differences.
    for (let i = 0; i < 3; i++) {
      assert.ok(near(withLoad[i], loaded[i], 0.25), `${strokes} ${i}: ${withLoad[i]}`);
      assert.ok(near(without[i], empty[i], 0.25), `${strokes} ${i}: ${without[i]}`);
    }
  }
  // A machine standing level feels plain gravity in the arm's plane, whatever its
  // slew; nosing down tips gravity forward along the arm.
  for (const slew of [-120, 0, 75]) {
    const g = armGravity({ ...initialMachine(), slew });
    assert.ok(near(g[0], 0, 1e-12) && near(g[1], -9.81, 1e-12));
  }
  const g = armGravity({ ...initialMachine(), pitch: -0.2 });
  assert.ok(g[0] > 1.9 && g[1] > -9.81);
});

test("a drive slows under load, holds by itself and stalls past its limits", () => {
  assert.equal(SCREW.selfLocking, true);
  // 800 rpm on a 0.7 mm lead is 9.3 mm/s at 12 V; the 11.1 V battery and the
  // circuit's losses leave about 8.1 mm/s.
  const free = driveRate(1, 0);
  assert.ok(near(free.rate, 8.15, 0.05), `${free.rate}`);
  assert.ok(near(strokeTime(0), 7.37, 0.05));
  // R12's 38.3 N boom peak takes a full stroke in about 10 s.
  assert.ok(near(strokeTime(38.3), 9.99, 0.05));
  let last = Infinity;
  for (const force of [0, 10, 20, 40, 60, 80]) {
    const { rate, current, state } = driveRate(1, force);
    assert.equal(state, "moving");
    assert.ok(rate < last && current <= DRIVE.currentLimit);
    last = rate;
  }
  // Retracting works the same way, mirrored.
  assert.ok(near(driveRate(-1, -38.3).rate, -driveRate(1, 38.3).rate, 1e-12));
  // A self-locking screw: a load that helps still takes torque, so the drive is
  // faster than against it but slower than with no load.
  const lowering = driveRate(-1, 38.3).rate;
  assert.ok(-lowering > driveRate(1, 38.3).rate && -lowering < free.rate);
  // Stopped, it draws nothing and holds.
  assert.deepEqual(driveRate(0, 38.3), {
    rate: 0,
    force: 38.3,
    current: 0,
    state: "idle",
  });
  // Past the 0.5 A current limit (about 86 N), or below the duty its load needs,
  // it stalls.
  assert.equal(driveRate(1, 86).state, "stalled");
  assert.equal(driveRate(1, 86).current, DRIVE.currentLimit);
  assert.equal(driveRate(0.25, 38.3).state, "stalled");
  assert.equal(driveRate(0.45, 38.3).state, "moving");
});

test("the arm moves at its drives' speed, slower with sand in the bucket", () => {
  const s = new SandSimulation();
  s.speed = 1;
  const v = s.vehicles[0],
    start = s.machine.strokes[0];
  s.axes = { ...neutral(), boom: 1 };
  for (let i = 0; i < 30; i++) s.step();
  const raised = s.machine.strokes[0] - start,
    boom = s.stats.drives[0];
  assert.equal(boom.state, "moving");
  assert.ok(raised > 6 && raised < 7.5, `raised ${raised} mm in 1 s`);
  assert.ok(near(raised, boom.rate, 0.2), `${raised} against ${boom.rate} mm/s`);
  assert.ok(boom.force > 20 && boom.force < 35, `${boom.force} N per boom drive`);
  // The same lift with about 250 cm³ of sand in the bucket is slower.
  const empty = boom.rate;
  s.reset();
  s.speed = 1;
  v.load.add(40, 0, 25, 250000);
  s.axes = { ...neutral(), boom: 1 };
  for (let i = 0; i < 30; i++) s.step();
  const loaded = s.stats.drives[0];
  assert.ok(loaded.force > boom.force + 5, `${loaded.force} N with sand`);
  assert.ok(loaded.rate < empty - 0.3, `${loaded.rate} mm/s with sand`);
  // Half the movement speed is half the duty: much slower, not half as fast.
  s.reset();
  s.speed = 0.5;
  s.axes = { ...neutral(), boom: 1 };
  for (let i = 0; i < 30; i++) s.step();
  assert.ok(s.stats.drives[0].rate < empty / 2, `${s.stats.drives[0].rate}`);
  // Driven past its end, a drive's end stop switches it off, even at a duty too
  // low to move its load.
  s.reset();
  s.speed = 1;
  s.machine.strokes[0] = 59.99;
  s.axes = { ...neutral(), boom: 1 };
  for (let i = 0; i < 3; i++) s.step();
  assert.equal(s.machine.strokes[0], 60);
  assert.equal(s.stats.drives[0].state, "end");
  assert.equal(s.stats.drives[0].current, 0);
  s.speed = 0.2;
  s.step();
  assert.equal(s.stats.drives[0].state, "end");
  assert.equal(s.stats.drives[0].current, 0);
  // Away from its end, the same low duty stalls it.
  s.machine.strokes[0] = 50;
  s.step();
  assert.equal(s.stats.drives[0].state, "stalled");
  assert.ok(s.stats.drives[0].current > 0.1);
  assert.equal(s.machine.strokes[0], 50);
});

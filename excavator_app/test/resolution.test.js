import test from "node:test";
import assert from "node:assert/strict";
import { AdaptiveResolution } from "../client/resolution.js";

// Feeds whole measuring windows of about a second, each of frames of one length.
function run(resolution, ms, windows = 1) {
  let changed = false;
  for (let w = 0; w < windows; w++)
    do changed = resolution.frame(ms) || changed;
    while (resolution.samples.length);
  return changed;
}

test("a machine that keeps up is left alone", () => {
  const resolution = new AdaptiveResolution(1.75);
  assert.equal(run(resolution, 1000 / 60, 120), false);
  assert.equal(resolution.ratio, 1.75);
  // Between fast and slow is good enough too.
  assert.equal(run(resolution, 1000 / 50, 30), false);
  assert.equal(resolution.ratio, 1.75);
});

test("slow frames lower the resolution one step at a time until they are not", () => {
  const resolution = new AdaptiveResolution(1.75),
    ratios = [];
  // Frames that take time in proportion to the pixels drawn.
  for (let i = 0; i < 12; i++) {
    run(resolution, 10 + 20 * resolution.ratio ** 2);
    ratios.push(resolution.ratio);
  }
  assert.ok(ratios[0] < 1.75 && ratios[0] > 1.4, "one step, not all of them");
  for (let i = 1; i < ratios.length; i++) assert.ok(ratios[i] <= ratios[i - 1]);
  assert.ok(ratios.at(-1) < 1, "it can go below the screen's own pixels");
  assert.ok(ratios.at(-1) > resolution.lowest, "and stops when frames are fine");
  assert.equal(ratios.at(-1), ratios.at(-2));
  assert.equal(new AdaptiveResolution(1).lowest, 0.75);
  assert.equal(new AdaptiveResolution(0.5).lowest, 0.5);
});

test("a single long frame is not a trend", () => {
  const resolution = new AdaptiveResolution(1);
  for (let i = 0; i < 300; i++)
    assert.equal(resolution.frame(i === 40 ? 900 : 1000 / 60), false);
  assert.equal(resolution.ratio, 1);
});

test("very slow frames count after only a few of them", () => {
  const resolution = new AdaptiveResolution(1);
  for (let i = 0; i < 3; i++) assert.equal(resolution.frame(1500), false);
  assert.equal(resolution.frame(1500), true);
  assert.ok(resolution.ratio < 1);
});

test("resolution comes back when there is headroom, more cautiously each time", () => {
  const resolution = new AdaptiveResolution(1);
  run(resolution, 30);
  const lowered = resolution.ratio;
  assert.ok(lowered < 1);
  run(resolution, 1000 / 60, 5);
  assert.equal(resolution.ratio, lowered, "not straight away");
  run(resolution, 1000 / 60, 6);
  assert.ok(resolution.ratio > lowered, "after ten seconds of fast frames");
  assert.ok(resolution.ratio <= 1);
  // Too much again: it drops, and waits longer before the next try.
  const raised = resolution.ratio;
  run(resolution, 30);
  const again = resolution.ratio;
  assert.ok(again < raised);
  run(resolution, 1000 / 60, 12);
  assert.equal(resolution.ratio, again, "twice as long this time");
  run(resolution, 1000 / 60, 10);
  assert.ok(resolution.ratio > again);
});

test("a rate that fewer pixels do not improve gets its pixels back for good", () => {
  // A 30 Hz display: every frame is 33 ms, whatever is drawn.
  const resolution = new AdaptiveResolution(1.75);
  run(resolution, 1000 / 30, 20);
  assert.equal(resolution.ratio, 1.75);
  assert.equal(resolution.finished, true);
  assert.equal(run(resolution, 100, 20), false, "and it stops adjusting");
  assert.equal(resolution.ratio, 1.75);
});

test("fewer pixels that help, but not enough, stay at the floor", () => {
  const resolution = new AdaptiveResolution(1.75);
  for (let i = 0; i < 20; i++) run(resolution, 40 + 40 * resolution.ratio ** 2);
  assert.equal(resolution.ratio, resolution.lowest);
  assert.equal(resolution.finished, false);
});

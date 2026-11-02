import test from "node:test";
import assert from "node:assert/strict";
import { createInputSender } from "../client/input-sender.js";

test("control starts and stops send immediately; queued motion uses the latest axes", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  let now = 0;
  t.mock.method(performance, "now", () => now);
  let axes = 1;
  const sent = [],
    sender = createInputSender(() => sent.push(axes));
  sender.schedule(true);
  assert.deepEqual(sent, [1], "touch down must not wait for a heartbeat");
  for (let i = 0; i < 100; i++) {
    axes = i / 100;
    sender.schedule();
  }
  assert.deepEqual(sent, [1], "rapid pointer moves are coalesced");
  now += 34;
  t.mock.timers.tick(34);
  assert.deepEqual(sent, [1, 0.99], "only the latest motion is sent");
  axes = 0.5;
  sender.schedule();
  axes = 0;
  sender.schedule(true);
  assert.deepEqual(sent, [1, 0.99, 0], "touch release is immediate");
  t.mock.timers.tick(100);
  assert.deepEqual(sent, [1, 0.99, 0], "released input is never replayed");
});

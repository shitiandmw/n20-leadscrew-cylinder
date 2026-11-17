import test from "node:test";
import assert from "node:assert/strict";
import { Delivery } from "../server/delivery.js";

test("one update is on its way at a time until the first acknowledgement", () => {
  const d = new Delivery();
  assert.equal(d.behind(0), false, "nothing sent yet");
  d.sent(1, 0);
  assert.equal(d.behind(1), true, "the round trip is not known yet");
  assert.equal(d.behind(60_000), true);
  assert.equal(d.acknowledged(1, 180), 180);
  assert.equal(d.rtt, 180);
  assert.equal(d.behind(181), false);
});

test("a line that keeps up is never held back, and one that falls behind is", () => {
  const d = new Delivery({ backlogMs: 100 });
  d.sent(0, 0);
  d.acknowledged(0, 170);
  // 30 updates a second, each acknowledged a round trip later: about five on
  // their way at any moment, and none of them late.
  let t = 170;
  for (let tick = 1; tick < 300; tick++, t += 1000 / 30) {
    while (d.unacked.length && d.unacked[0].at + 170 <= t)
      d.acknowledged(d.unacked[0].tick, t);
    assert.equal(d.behind(t), false, `held back at tick ${tick}`);
    d.sent(tick, t);
  }
  assert.ok(d.unacked.length <= 6, `${d.unacked.length} on their way`);
  // The line stalls: updates go out until the oldest is 100 ms overdue.
  let sent = 0;
  for (let tick = 300; tick < 400; tick++, t += 1000 / 30)
    if (!d.behind(t)) {
      d.sent(tick, t);
      sent++;
    }
  assert.ok(sent <= 4, `${sent} more sent into a stalled line`);
  // Acknowledging the newest clears everything before it.
  d.acknowledged(d.unacked.at(-1).tick, t);
  assert.equal(d.unacked.length, 0);
  assert.equal(d.behind(t), false);
});

test("acknowledgements of updates never sent change nothing", () => {
  const d = new Delivery();
  d.sent(5, 0);
  d.sent(6, 33);
  assert.equal(d.acknowledged(99, 50), null);
  assert.equal(d.acknowledged("6", 50), null);
  assert.equal(d.unacked.length, 2);
  assert.equal(d.rtt, null);
});

test("ticks that start again after a reset match the oldest update first", () => {
  const d = new Delivery();
  d.sent(2, 0);
  d.sent(3, 33);
  // The world was reset: ticks count from 1 again.
  d.sent(1, 66);
  d.sent(2, 100);
  assert.equal(d.acknowledged(2, 150), 150);
  assert.deepEqual(
    d.unacked.map((u) => u.tick),
    [3, 1, 2],
  );
  assert.equal(d.acknowledged(2, 260), 160);
  assert.equal(d.unacked.length, 0);
});

test("the quickest round trip lately: a line that gets slower is believed within two windows", () => {
  const d = new Delivery({ windowMs: 10_000 });
  let tick = 0;
  const trip = (at, ms) => {
    d.sent(++tick, at);
    d.acknowledged(tick, at + ms);
  };
  trip(0, 50);
  trip(1000, 400);
  assert.equal(d.rtt, 50, "a moment's queue is not the line");
  trip(12_000, 300);
  assert.equal(d.rtt, 50, "the window before still counts");
  trip(23_000, 300);
  assert.equal(d.rtt, 300);
  trip(24_000, 200);
  assert.equal(d.rtt, 200, "a quicker trip counts at once");
});

test("a page that never acknowledges cannot grow the list without bound", () => {
  const d = new Delivery();
  for (let tick = 0; tick < 1000; tick++) d.sent(tick, tick);
  assert.equal(d.unacked.length, 256);
});

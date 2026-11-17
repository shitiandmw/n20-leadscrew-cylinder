// How far behind a connection is with its periodic updates: binary frames to a
// simulator page, state to a phone. A page that acknowledges each update it has
// handled is sent no more than its connection carries.
//
// The server cannot see most of the buffers between itself and a browser: the
// kernel's, a proxy's (Docker's port mapping is one), a router's on a slow line.
// Its own socket stays empty while those fill, and a 30 Hz stream that a slow
// line cannot carry then builds a queue of seconds of old frames, every one of
// which is shown before the machine's answer to a command is. A phone's ping,
// on its own connection with little else on it, still looks fine meanwhile.
//
// So an update waits while the oldest one not yet acknowledged has been on its
// way longer than the quickest round trip lately plus `backlogMs`. The line then
// holds about that much more than it needs, whatever its speed, and the updates
// that wait are skipped: each one carries everything that changed since the
// last one sent. Until the first acknowledgement, one update at a time is on its
// way.
export class Delivery {
  constructor({ backlogMs = 100, windowMs = 10_000 } = {}) {
    this.backlogMs = backlogMs;
    this.windowMs = windowMs;
    // Sent and not yet acknowledged, oldest first: { tick, at }.
    this.unacked = [];
    // The quickest round trip of the last one or two windows, or null before
    // the first: a line that gets slower is believed within two windows, and a
    // moment's queue is never taken for the line itself.
    this.rtt = null;
    this.quickest = Infinity;
    this.before = Infinity;
    this.since = -Infinity;
  }

  behind(now) {
    const oldest = this.unacked[0];
    return !!oldest && (this.rtt === null || now - oldest.at > this.rtt + this.backlogMs);
  }

  sent(tick, now) {
    this.unacked.push({ tick, at: now });
    // A page that stops acknowledging gets nothing more but its changes of
    // control, so this only grows by those; keep it bounded all the same.
    if (this.unacked.length > 256) this.unacked.shift();
  }

  // Updates arrive in order, so this one and every one before it are through.
  // Ticks start again after a world reset; the oldest update with this tick is
  // the one meant.
  acknowledged(tick, now) {
    const k = this.unacked.findIndex((update) => update.tick === tick);
    if (k < 0) return null;
    const rtt = now - this.unacked[k].at;
    this.unacked.splice(0, k + 1);
    if (now - this.since > this.windowMs) {
      this.before = this.quickest;
      this.quickest = Infinity;
      this.since = now;
    }
    this.quickest = Math.min(this.quickest, rtt);
    this.rtt = Math.min(this.quickest, this.before);
    return rtt;
  }
}

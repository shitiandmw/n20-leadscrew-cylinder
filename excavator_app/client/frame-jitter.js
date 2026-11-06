// How unevenly frames arrive, in ticks: the running estimate RTP uses (RFC 3550).
// A moment's stall moves it little; a jittery connection moves it a lot.
export class FrameJitter {
  ticks = 0;
  #tick = null;
  #at = 0;
  constructor(tickRate) {
    this.tickRate = tickRate;
  }
  arrived(tick, now) {
    if (this.#tick !== null && tick > this.#tick) {
      const late =
        ((now - this.#at) * this.tickRate) / 1000 - (tick - this.#tick);
      this.ticks += (Math.abs(late) - this.ticks) / 16;
    }
    this.#tick = tick;
    this.#at = now;
  }
}

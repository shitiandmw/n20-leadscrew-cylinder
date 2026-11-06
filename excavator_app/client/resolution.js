// Draws fewer pixels when frames arrive too slowly, and tries more again later, so
// a weak graphics card gets a softer picture rather than a slideshow.
const SLOW_MS = 1000 / 45,
  FAST_MS = 1000 / 55,
  STEP = 0.85,
  LOWEST = 0.75,
  FIRST_RETRY_MS = 10000,
  LAST_RETRY_MS = 300000;

export class AdaptiveResolution {
  constructor(highest) {
    this.highest = highest;
    this.lowest = Math.min(highest, LOWEST);
    this.ratio = highest;
    this.samples = [];
    this.spent = 0;
    this.fastFor = 0;
    this.retryAfter = FIRST_RETRY_MS;
    this.slowAt = null;
    this.finished = false;
  }

  // The time between two frames drawn one straight after the other, in ms.
  // Returns true if `ratio` changed.
  frame(ms) {
    if (this.finished) return false;
    this.samples.push(ms);
    this.spent += ms;
    if (this.spent < 1000 || this.samples.length < 4) return false;
    // The middle value: one long frame, from a shader or a page of sand, is no trend.
    const typical = this.samples.sort((a, b) => a - b)[this.samples.length >> 1],
      spent = this.spent;
    this.samples = [];
    this.spent = 0;
    if (typical > SLOW_MS) return this.slower(typical);
    if (typical > FAST_MS) {
      this.fastFor = 0;
      return false;
    }
    this.slowAt = null;
    this.fastFor += spent;
    if (this.ratio >= this.highest || this.fastFor < this.retryAfter) return false;
    this.fastFor = 0;
    this.retryAfter = Math.min(2 * this.retryAfter, LAST_RETRY_MS);
    this.ratio = Math.min(this.highest, this.ratio / STEP);
    return true;
  }

  slower(typical) {
    this.fastFor = 0;
    if (this.ratio > this.lowest) {
      this.slowAt ??= typical;
      this.ratio = Math.max(this.lowest, this.ratio * STEP);
      return true;
    }
    // As few pixels as it goes, and no faster for it: something else sets the
    // rate, such as a 30 Hz display or a power saver. Have the pixels back.
    const pointless = this.slowAt !== null && typical > 0.9 * this.slowAt;
    this.slowAt = null;
    if (!pointless) return false;
    this.ratio = this.highest;
    this.finished = true;
    return true;
  }
}

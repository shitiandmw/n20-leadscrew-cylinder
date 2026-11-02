// Send control edges immediately, coalesce motion at 30 Hz, and read the latest
// axes when flushing so a queued move can never replay a released joystick.
export function createInputSender(send) {
  let timer,
    lastSent = -Infinity;
  function flush() {
    clearTimeout(timer);
    timer = undefined;
    lastSent = performance.now();
    send();
  }
  return {
    flush,
    schedule(immediate = false) {
      const remaining = 1000 / 30 - (performance.now() - lastSent);
      if (immediate || remaining <= 0) flush();
      else if (timer === undefined) timer = setTimeout(flush, remaining);
    },
  };
}

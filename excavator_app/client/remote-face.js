// The phone remote's hardware: faceplate markup, the segment LCD and haptics.
// main.js owns the control logic and finds every control by its id or class.
import { BUCKET } from "../shared/world.js";

const chevron = (points) =>
  `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${points}"/></svg>`;
const gear = `<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="5.6"/><circle cx="12" cy="12" r="2"/><path d="M12 2.6v3.2M12 18.2v3.2M2.6 12h3.2M18.2 12h3.2M5.4 5.4l2.2 2.2M16.4 16.4l2.2 2.2M5.4 18.6l2.2-2.2M16.4 7.6l2.2-2.2"/></svg>`;

// Seven-segment digits, drawn as SVG so they stay crisp at any phone density.
// Unlit segments stay faintly visible, as they do on a reflective LCD.
const W = 12,
  H = 22,
  T = 2.9,
  M = H / 2,
  PITCH = 16;
const flipX = (points) => points.map(([x, y]) => [W - x, y]);
const flipY = (points) => points.map(([x, y]) => [x, H - y]);
const BAR = [
  [1, 0],
  [W - 1, 0],
  [W - 1 - T, T],
  [1 + T, T],
];
const SIDE = [
  [0, 1],
  [T, 1 + T],
  [T, M - T / 2 - 0.6],
  [0, M - 0.6],
];
const SEGMENTS = {
  a: BAR,
  b: flipX(SIDE),
  c: flipX(flipY(SIDE)),
  d: flipY(BAR),
  e: flipY(SIDE),
  f: SIDE,
  g: [
    [1.2, M],
    [1.2 + T / 2, M - T / 2],
    [W - 1.2 - T / 2, M - T / 2],
    [W - 1.2, M],
    [W - 1.2 - T / 2, M + T / 2],
    [1.2 + T / 2, M + T / 2],
  ],
};
const GLYPHS = {
  0: "abcdef",
  1: "bc",
  2: "abdeg",
  3: "abcdg",
  4: "bcfg",
  5: "acdfg",
  6: "acdefg",
  7: "abc",
  8: "abcdefg",
  9: "abcdfg",
  "-": "g",
  " ": "",
};
const cellPath = (cell, segments) =>
  [...segments]
    .map(
      (name) =>
        "M" +
        SEGMENTS[name]
          .map(([x, y]) => `${(x + cell * PITCH).toFixed(2)} ${y.toFixed(2)}`)
          .join("L") +
        "Z",
    )
    .join("");
const pointPath = (cell) =>
  `M${(cell * PITCH + W + 1).toFixed(2)} ${H - 2.6}h2.4v2.6h-2.4Z`;

const digits = (id, cells, point = -1) => {
  const ghost = Array.from({ length: cells }, (_, cell) =>
    cellPath(cell, GLYPHS[8]),
  ).join("");
  const dot = point < 0 ? "" : pointPath(point);
  return `<svg class="digits" id="${id}" role="img" viewBox="-2.4 0 ${cells * PITCH - 1} ${H}" data-cells="${cells}" data-point="${dot}"><g transform="skewX(-5)"><path class="ghost" d="${ghost}${dot}"/><path class="lit"/></g></svg>`;
};
function setDigits(svg, text, label) {
  if (svg.dataset.text === text) return;
  svg.dataset.text = text;
  const glyphs = text.replace(".", "").padStart(+svg.dataset.cells, " ");
  svg
    .querySelector(".lit")
    .setAttribute(
      "d",
      [...glyphs].map((glyph, cell) => cellPath(cell, GLYPHS[glyph])).join("") +
        svg.dataset.point,
    );
  svg.setAttribute("aria-label", label);
}

// A curved legend engraved on a joystick's collar. Angles run clockwise from
// 12 o'clock; an arc swept backwards keeps the bottom legend upright.
const onCircle = (angle, radius) => {
  const t = (angle * Math.PI) / 180;
  return `${(100 + radius * Math.sin(t)).toFixed(2)} ${(100 - radius * Math.cos(t)).toFixed(2)}`;
};
const legend = (id, direction, text, from, to, radius) =>
  `<path id="${id}-${direction}" d="M${onCircle(from, radius)}A${radius} ${radius} 0 0 ${to > from ? 1 : 0} ${onCircle(to, radius)}" fill="none"/><text class="legend legend-${direction}"><textPath href="#${id}-${direction}" startOffset="50%" text-anchor="middle">${text}</textPath></text>`;

const stick = (name, label, [north, east, south, west]) =>
  `<div class="stick stick-${name}"><div class="joystick" id="${name}-stick" role="group" aria-label="${label}">
    <span class="stick-collar"></span>
    <svg class="stick-legends" viewBox="0 0 200 200" aria-hidden="true">${legend(name, "n", north, -56, 56, 84.5)}${legend(name, "e", east, 34, 146, 84.5)}${legend(name, "s", south, 236, 124, 93.5)}${legend(name, "w", west, 214, 326, 84.5)}</svg>
    <span class="stick-well"></span>
    <span class="boot" style="--size:68%;--k:.3"></span><span class="boot" style="--size:58%;--k:.55"></span><span class="boot" style="--size:49%;--k:.8"></span>
    <div class="knob"></div>
  </div></div>`;

const rocker = (name, axis, label) =>
  `<div class="rocker rocker-${name}" role="group" aria-label="${label} track">
    <span class="rocker-label">${name === "left" ? "L" : "R"} TRACK</span>
    <div class="rocker-well"><div class="rocker-body">
      <button class="hold" data-axis="${axis}" data-value="1" aria-label="${label} track forward">${chevron("M5 15l7-7 7 7")}</button>
      <button class="hold" data-axis="${axis}" data-value="-1" aria-label="${label} track reverse">${chevron("M5 9l7 7 7-7")}</button>
    </div></div>
  </div>`;

const reading = (label, id, cells, point, unit) =>
  `<div class="lcd-reading"><span>${label} <small>${unit}</small></span>${digits(id, cells, point)}</div>`;

const fineControls = [
  ["boom", "Boom"],
  ["stick", "Stick"],
  ["bucket", "Bucket"],
  ["slew", "Slew"],
]
  .map(
    ([axis, label]) =>
      `<div><span>${label}</span><button class="hold" data-axis="${axis}" data-value="-1" aria-label="Decrease ${label}">−</button><button class="hold" data-axis="${axis}" data-value="1" aria-label="Increase ${label}">+</button></div>`,
  )
  .join("");

export const remoteFace = ({ connection, connectionHelp }) => `
<main class="rc" aria-label="Excavator remote control">
  <div class="rc-face">
    <div class="rc-plate">
      <div class="rc-logo">SAND<span>/</span>LAB</div>
      <div class="rc-leds" aria-hidden="true"><span><i class="led led-link"></i>LINK</span><span><i class="led led-ctrl"></i>CTRL</span><span><i class="led led-stop"></i>STOP</span></div>
    </div>
    <button id="estop" class="rc-estop" data-estop aria-label="Emergency stop">
      <svg viewBox="0 0 100 100" aria-hidden="true"><path id="estop-top" d="M9.5 50a40.5 40.5 0 0 1 81 0" fill="none"/><text><textPath href="#estop-top" startOffset="50%" text-anchor="middle">EMERGENCY</textPath></text></svg>
      <span class="dome"><b>STOP</b></span>
    </button>
    <section class="lcd" aria-label="Machine status"><div class="lcd-glass">
      <div class="lcd-row lcd-link">${connection}<span class="lcd-signal" id="signal" aria-hidden="true"><i></i><i></i><i></i><i></i></span><span class="lcd-ping"><span id="latency-value">--</span> ms</span><span class="lcd-room"><span>ROOM</span> <strong id="room-label">------</strong></span></div>
      <div class="lcd-readings">${reading("BOOM", "boom-value", 3, 1, "mm")}${reading("STICK", "stick-value", 3, 1, "mm")}${reading("BUCKET", "bucket-value", 3, 1, "mm")}${reading("SLEW", "slew-value", 4, -1, "deg")}</div>
      <div class="lcd-row lcd-load"><span>LOAD</span><span class="lcd-bar" id="load-bar" aria-hidden="true">${"<i></i>".repeat(12)}</span>${digits("load-value", 3)}<small>cm³</small><span class="lcd-speed" id="lcd-speed">SPD 65%</span></div>
      <div class="lcd-row ownership"><span id="operator-status">Waiting for connection</span><span class="lcd-flag" id="lcd-floor" hidden><span class="lcd-wide">ON CONCRETE · </span>RAISE BOOM</span><span class="lcd-flag lcd-blink" id="lcd-stop" hidden>E-STOP</span></div>
      <div id="toast" role="status" hidden></div>
    </div></section>
    ${rocker("left", "leftTrack", "Left")}
    <div class="rc-keys">
      <button id="claim" class="rc-key" disabled>Take control</button>
      <button id="resume" class="rc-key rc-key-go" aria-label="Resume operation" hidden><i class="led"></i>Resume</button>
      <button id="settings" class="rc-key rc-key-icon" aria-label="Settings">${gear}<span>Settings</span></button>
    </div>
    ${rocker("right", "rightTrack", "Right")}
    ${stick("left", "Left joystick: stick and slew", ["STICK OUT", "SLEW R", "STICK IN", "SLEW L"])}
    ${stick("right", "Right joystick: boom and bucket", ["BOOM LOWER", "BUCKET OPEN", "BOOM RAISE", "BUCKET CURL"])}
  </div>
  ${connectionHelp}
</main>
<dialog id="settings-sheet" class="rc-sheet" aria-labelledby="settings-title"><div class="sheet">
  <header class="sheet-head">
    <h2 id="settings-title">Settings</h2>
    <button id="estop-sheet" class="sheet-estop" data-estop aria-label="Emergency stop"><i></i>STOP</button>
    <button id="settings-close" class="rc-key" autofocus>Done</button>
  </header>
  <div class="sheet-body">
    <section class="sheet-group" aria-label="Operation">
      <div class="setting setting-speed"><label for="speed">Movement speed</label><output id="speed-value">65%</output><input id="speed" type="range" min="20" max="100" step="5" value="65"></div>
      <div class="setting"><div><strong>Sand and machine</strong><small>Back to the start position. You need control to do this.</small></div><button id="reset" class="rc-key">Reset sand</button></div>
    </section>
    <section class="sheet-group" aria-label="This phone">
      <label class="setting" id="haptics-row" hidden><div><strong>Haptic feedback</strong><small>A short pulse from buttons and stick stops.</small></div><span class="switch"><input id="haptics" type="checkbox" role="switch"><i></i></span></label>
      <label class="setting" id="fullscreen-row" hidden><div><strong>Full screen</strong><small>Hides the browser bars.</small></div><span class="switch"><input id="fullscreen-toggle" type="checkbox" role="switch"><i></i></span></label>
      <div class="setting"><div><strong>Room <span id="sheet-room">------</span></strong><small>Scan a new code to drive another sandbox.</small></div><a class="rc-key" href="/remote">Change room</a></div>
    </section>
    <details class="sheet-group sheet-guide"><summary>Control guide</summary>
      <dl>
        <dt>Left stick</dt><dd>Up and down moves the stick out and in. Left and right slews the upper body.</dd>
        <dt>Right stick</dt><dd>Up lowers the boom, down raises it. Left curls the bucket, right opens it.</dd>
        <dt>Track rockers</dt><dd>Push both up to drive forward, both down to reverse, one of each to turn.</dd>
        <dt>First scoop</dt><dd>Boom down to 0, stick to about 20 mm, curl past 50 mm, then lift and swing to the pour zone.</dd>
        <dt>Emergency stop</dt><dd>Works from any device and stays latched until the operator presses Resume.</dd>
      </dl>
      <p>Keep this page open while operating. Switching apps releases control.</p>
    </details>
    <details class="sheet-group sheet-guide"><summary>Button controls</summary>
      <p>The same motions as hold-to-move buttons. Hold Enter to use them from a keyboard.</p>
      <div class="accessible-controls">${fineControls}</div>
    </details>
  </div>
</div></dialog>`;

export const joinFace = () => `
<main class="rc rc-join"><form id="join" class="rc-join-face">
  <div class="rc-logo">SAND<span>/</span>LAB</div>
  <label for="room-code">Room code</label>
  <div class="lcd"><div class="lcd-glass"><input id="room-code" placeholder="A1B2C3" maxlength="6" minlength="6" pattern="[a-fA-F0-9]{6}" required autocomplete="off" autocapitalize="characters" spellcheck="false"></div></div>
  <p>Enter the six-character code shown on your simulator.</p>
  <button class="rc-key rc-key-wide">Connect to excavator</button>
  <a href="/">Open a new sandbox ↗</a>
</form></main>`;

// The LCD: fixed-format readouts, updated only when a shown value changes.
export function createDisplay() {
  const $ = (selector) => document.querySelector(selector);
  const boom = $("#boom-value"),
    stickValue = $("#stick-value"),
    bucket = $("#bucket-value"),
    slew = $("#slew-value"),
    load = $("#load-value"),
    bar = [...$("#load-bar").children],
    signal = [...$("#signal").children];
  let barLevel = -1,
    signalLevel = -1;
  const fill = (cells, level) =>
    cells.forEach((cell, index) => cell.classList.toggle("on", index < level));
  return {
    machine(machine, stats) {
      const [b, s, c] = machine.strokes.map((value) => value.toFixed(1));
      setDigits(boom, b, `Boom ${b} millimetres`);
      setDigits(stickValue, s, `Stick ${s} millimetres`);
      setDigits(bucket, c, `Bucket ${c} millimetres`);
      const angle = Math.round(machine.slew);
      setDigits(slew, `${angle}`, `Slew ${angle} degrees`);
      const cm3 = Math.min(999, Math.round(stats.load));
      setDigits(load, `${cm3}`, `Bucket load ${cm3} cubic centimetres`);
      const level = Math.min(
        bar.length,
        Math.ceil((stats.load / BUCKET.ratedLoad) * bar.length),
      );
      if (level !== barLevel) fill(bar, (barLevel = level));
    },
    speed(value) {
      $("#lcd-speed").textContent = `SPD ${Math.round(value * 100)}%`;
    },
    latency(ms) {
      $("#latency-value").textContent = ms === null ? "--" : ms;
      const level =
        ms === null ? 0 : ms < 40 ? 4 : ms < 100 ? 3 : ms < 250 ? 2 : 1;
      if (level !== signalLevel) fill(signal, (signalLevel = level));
    },
    flags(stopped, blocked) {
      $("#lcd-stop").hidden = !stopped;
      $("#lcd-floor").hidden = !blocked;
    },
  };
}

export function createHaptics() {
  const supported = typeof navigator.vibrate === "function",
    KEY = "sandlab-haptics";
  let enabled = supported;
  try {
    enabled = supported && localStorage.getItem(KEY) !== "off";
  } catch {
    /* Private browsing: the choice just lasts until the page closes. */
  }
  return {
    supported,
    get enabled() {
      return enabled;
    },
    set(value) {
      enabled = value;
      try {
        localStorage.setItem(KEY, value ? "on" : "off");
      } catch {
        /* See above. */
      }
    },
    pulse(pattern) {
      if (enabled) navigator.vibrate(pattern);
    },
  };
}

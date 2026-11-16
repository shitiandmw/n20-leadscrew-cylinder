// The phone remote's hardware: faceplate markup, the segment LCD and haptics.
// main.js owns the control logic and finds every control by its id or class.
import { BUCKET, SAND } from "../shared/world.js";
import { NAME_LENGTH } from "../shared/players.js";
import { TRUCK_LOAD } from "../shared/truck.js";

const chevron = (points) =>
  `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${points}"/></svg>`;
// Line icons of the two machines, for the key that changes between them.
export const REMOTE_ICONS = {
  truck: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 16V8h11v8M13 11h4.5l3 3v2H13"/><circle cx="6" cy="17.5" r="1.8"/><circle cx="17" cy="17.5" r="1.8"/></svg>`,
  excavator: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 19h8m-6-3h5v3H5zm4 0V9l4-4 5 7m-6-6 5-2 4 8-4 3-3-3 3-2"/></svg>`,
};
// What the sticks' collars say for each machine: north, east, south, west.
export const REMOTE_LEGENDS = {
  excavator: {
    left: ["STICK OUT", "SLEW R", "STICK IN", "SLEW L"],
    right: ["BOOM LOWER", "BUCKET OPEN", "BOOM RAISE", "BUCKET CURL"],
  },
  truck: {
    left: ["FORWARD", "STEER R", "REVERSE", "STEER L"],
    right: ["BODY RAISE", "", "BODY LOWER", ""],
  },
};
export const REMOTE_STICKS = {
  excavator: {
    left: "Left joystick: stick and slew",
    right: "Right joystick: boom and bucket",
  },
  truck: {
    left: "Left joystick: drive and steer",
    right: "Right joystick: raise and lower the body",
  },
};
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

// Hold-to-move buttons for every control, each row marked with its machine; only
// the rows of the machine being driven show.
export const holdRows = () =>
  [
    ["excavator", "boom", "Boom"],
    ["excavator", "stick", "Stick"],
    ["excavator", "bucket", "Bucket"],
    ["excavator", "slew", "Slew"],
    ["truck", "drive", "Drive"],
    ["truck", "steer", "Steer"],
    ["truck", "hoist", "Body"],
  ]
    .map(
      ([machine, axis, label]) =>
        `<div data-machine="${machine}"${machine === "truck" ? " hidden" : ""}><span>${label}</span><button class="hold" data-axis="${axis}" data-value="-1" aria-label="Decrease ${label}">−</button><button class="hold" data-axis="${axis}" data-value="1" aria-label="Increase ${label}">+</button></div>`,
    )
    .join("");

export const remoteFace = ({ connection, connectionHelp }) => `
<main class="rc" aria-label="Excavator remote control">
  <div class="rc-face">
    <div class="rc-plate">
      <div class="rc-title"><div class="rc-logo">SAND<span>/</span>LAB</div><div class="rc-player" id="rc-player" hidden><i></i><span></span></div></div>
      <div class="rc-leds" aria-hidden="true"><span><i class="led led-link"></i>LINK</span><span><i class="led led-ctrl"></i>CTRL</span><span><i class="led led-stop"></i>STOP</span></div>
    </div>
    <button id="estop" class="rc-estop" data-estop aria-label="Emergency stop">
      <svg viewBox="0 0 100 100" aria-hidden="true"><path id="estop-top" d="M9.5 50a40.5 40.5 0 0 1 81 0" fill="none"/><text><textPath href="#estop-top" startOffset="50%" text-anchor="middle">EMERGENCY</textPath></text></svg>
      <span class="dome"><b>STOP</b></span>
    </button>
    <section class="lcd" aria-label="Machine status"><div class="lcd-glass">
      <div class="lcd-row lcd-link">${connection}<span class="lcd-signal" id="signal" aria-hidden="true"><i></i><i></i><i></i><i></i></span><span class="lcd-ping"><span id="latency-value">--</span> ms</span><span class="lcd-room"><span>ROOM</span> <strong id="room-label">------</strong></span></div>
      <div class="lcd-readings" data-machine="excavator">${reading("BOOM", "boom-value", 3, 1, "mm")}${reading("STICK", "stick-value", 3, 1, "mm")}${reading("BUCKET", "bucket-value", 3, 1, "mm")}${reading("SLEW", "slew-value", 4, -1, "deg")}</div>
      <div class="lcd-readings" data-machine="truck" hidden>${reading("SPEED", "truck-speed", 3, -1, "mm/s")}${reading("STEER", "truck-steer", 3, -1, "deg")}${reading("BODY", "truck-tip", 3, -1, "deg")}${reading("HAULED", "truck-hauled", 4, 2, "L")}</div>
      <div class="lcd-row lcd-load"><span>LOAD</span><span class="lcd-bar" id="load-bar" aria-hidden="true">${"<i></i>".repeat(12)}</span><span class="lcd-load-digits" data-machine="excavator">${digits("load-value", 3)}<small>cm³</small></span><span class="lcd-load-digits" data-machine="truck" hidden>${digits("truck-load", 3, 1)}<small>L</small></span><span class="lcd-lip"><span class="lcd-wide" id="lcd-lip-label">LIP </span><span id="lcd-lip">--</span></span><span class="lcd-speed" id="lcd-speed">SPD 65%</span></div>
      <div class="lcd-row ownership"><span id="operator-status">Waiting for connection</span><span class="lcd-flag" id="lcd-floor" hidden><span class="lcd-wide">ON GROUND · </span>RAISE BOOM</span><span class="lcd-flag lcd-blink" id="lcd-stop" hidden>E-STOP</span></div>
      <div id="toast" role="status" hidden></div>
    </div></section>
    ${rocker("left", "leftTrack", "Left")}
    <div class="rc-keys">
      <button id="claim" class="rc-key" disabled>Take control</button>
      <button id="resume" class="rc-key rc-key-go" aria-label="Resume operation" hidden><i class="led"></i>Resume</button>
      <button id="switch-machine" class="rc-key rc-key-icon" aria-label="Drive your truck" disabled>${REMOTE_ICONS.truck}<span>Truck</span></button>
      <button id="settings" class="rc-key rc-key-icon" aria-label="Settings">${gear}<span>Settings</span></button>
    </div>
    ${rocker("right", "rightTrack", "Right")}
    ${stick("left", REMOTE_STICKS.excavator.left, REMOTE_LEGENDS.excavator.left)}
    ${stick("right", REMOTE_STICKS.excavator.right, REMOTE_LEGENDS.excavator.right)}
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
      <div class="setting"><div><strong id="respawn-title">Your excavator</strong><small id="respawn-note">Back to a start position, leaving the sand as it is. You need control to do this.</small></div><button id="respawn" class="rc-key">Back to start</button></div>
      <div class="setting"><div><strong>Sand and every machine</strong><small id="reset-note">Everything goes back to the start. You need control to do this.</small></div><button id="reset" class="rc-key">Reset world</button></div>
    </section>
    <section class="sheet-group" aria-label="This phone">
      <label class="setting" id="haptics-row" hidden><div><strong>Haptic feedback</strong><small>A short pulse from buttons and stick stops.</small></div><span class="switch"><input id="haptics" type="checkbox" role="switch"><i></i></span></label>
      <label class="setting" id="fullscreen-row" hidden><div><strong>Full screen</strong><small>Hides the browser bars.</small></div><span class="switch"><input id="fullscreen-toggle" type="checkbox" role="switch"><i></i></span></label>
      <label class="setting setting-name"><div><strong>Your name</strong><small>Shown to the others in this room.</small></div><input id="player-name" maxlength="${NAME_LENGTH}" autocomplete="nickname" spellcheck="false"></label>
      <div class="setting"><div><strong>Room <span id="sheet-room">------</span></strong><small><span id="sheet-players">Only you here</span>. Scan a new code to join another game.</small></div><a class="rc-key" href="/remote">Change room</a></div>
    </section>
    <details class="sheet-group sheet-guide"><summary>Control guide</summary>
      <dl>
        <dt>Left stick</dt><dd>Up and down moves the stick out and in. Left and right slews the upper body.</dd>
        <dt>Right stick</dt><dd>Up lowers the boom, down raises it. Left curls the bucket, right opens it.</dd>
        <dt>Track rockers</dt><dd>Push both up to drive forward, both down to reverse, one of each to turn.</dd>
        <dt>First scoop</dt><dd>Open the bucket to 15 mm, stick out to 9 mm, boom down to 29 mm until the teeth touch the sand, then stick in to 33 mm. Curl until LIP reads level, about 56 mm. Raise the boom, curling a little more as it rises to keep the lip level, and swing to the pour zone.</dd>
        <dt>Heaped bucket</dt><dd>The LOAD bar is full at ${BUCKET.heapedLoad} cm³, a heaped bucket. The heap stays on only while LIP is within about ${SAND.heapDeg - SAND.heapSlideDeg}° of level: tip the bucket further and it runs off.</dd>
        <dt>Your truck</dt><dd>The Truck key gets you into your dump truck, and Digger back into the excavator. Load the truck with the bucket, then drive it with the left stick and raise the body with the right: the rear wall swings open and the load slides out. HAULED counts the litres tipped beyond the sand yard.</dd>
        <dt>Emergency stop</dt><dd>Stops both your machines from any of your devices and stays latched until you press Resume.</dd>
      </dl>
      <p>Keep this page open while operating. Switching apps releases control.</p>
    </details>
    <details class="sheet-group sheet-guide"><summary>Button controls</summary>
      <p>The same motions as hold-to-move buttons. Hold Enter to use them from a keyboard.</p>
      <div class="accessible-controls">${holdRows()}</div>
    </details>
  </div>
</div></dialog>`;

export const joinFace = () => `
<main class="rc rc-join"><form id="join" class="rc-join-face">
  <div class="rc-logo">SAND<span>/</span>LAB</div>
  <label for="room-code">Room code</label>
  <div class="lcd"><div class="lcd-glass"><input id="room-code" placeholder="A1B2C3" maxlength="6" minlength="6" pattern="[a-fA-F0-9]{6}" required autocomplete="off" autocapitalize="characters" spellcheck="false"></div></div>
  <p>Enter the six-character code shown in the game. You get an excavator of your own in that room.</p>
  <label for="join-name">Your name</label>
  <input id="join-name" class="rc-field" maxlength="${NAME_LENGTH}" placeholder="Optional" autocomplete="nickname" spellcheck="false">
  <button class="rc-key rc-key-wide">Connect to excavator</button>
  <a href="/">Open a new game ↗</a>
</form></main>`;

// The LCD: fixed-format readouts, updated only when a shown value changes.
export function createDisplay() {
  const $ = (selector) => document.querySelector(selector);
  const boom = $("#boom-value"),
    stickValue = $("#stick-value"),
    bucket = $("#bucket-value"),
    slew = $("#slew-value"),
    load = $("#load-value"),
    lip = $("#lcd-lip"),
    truckSpeed = $("#truck-speed"),
    truckSteer = $("#truck-steer"),
    truckTip = $("#truck-tip"),
    truckHauled = $("#truck-hauled"),
    truckLoad = $("#truck-load"),
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
      // Full at a heaped bucket.
      const level = Math.min(
        bar.length,
        Math.ceil((stats.load / BUCKET.heapedLoad) * bar.length),
      );
      if (level !== barLevel) fill(bar, (barLevel = level));
      // How far the bucket's mouth is from level, and which way its lip points.
      const tilt = stats.tilt,
        away = Math.abs(tilt),
        text = !Number.isFinite(tilt)
          ? "--"
          : away < 3
            ? "LEVEL"
            : `${away}° ${tilt > 0 ? "DN" : "UP"}`;
      if (lip.textContent !== text) lip.textContent = text;
    },
    // The truck's readings: litres in the body and tipped, speed, steering and
    // the body's angle.
    truck(stats) {
      const speed = Math.min(999, Math.abs(stats.velocity));
      setDigits(truckSpeed, `${speed}`, `Speed ${speed} millimetres a second`);
      const steer = Math.max(-99, Math.min(99, stats.steer));
      setDigits(
        truckSteer,
        `${steer}`,
        `Steering ${Math.abs(steer)} degrees ${steer > 0 ? "left" : steer < 0 ? "right" : ""}`.trim(),
      );
      const tip = Math.round(stats.tip);
      setDigits(truckTip, `${tip}`, `Body raised ${tip} degrees`);
      const hauled = Math.min(999.9, stats.hauled / 1000).toFixed(1);
      setDigits(truckHauled, hauled, `Hauled ${hauled} litres`);
      const litres = Math.min(99.9, stats.load / 1000).toFixed(1);
      setDigits(truckLoad, litres, `Truck load ${litres} litres`);
      // Full when level with the side walls.
      const level = Math.min(
        bar.length,
        Math.ceil((stats.load / (TRUCK_LOAD.struck / 1000)) * bar.length),
      );
      if (level !== barLevel) fill(bar, (barLevel = level));
      const text = stats.gate ? "OPEN" : "SHUT";
      if (lip.textContent !== text) lip.textContent = text;
    },
    // Which machine's readings show.
    mode(machine) {
      document
        .querySelectorAll(".lcd [data-machine]")
        .forEach((part) => (part.hidden = part.dataset.machine !== machine));
      $("#lcd-lip-label").textContent = machine === "truck" ? "GATE " : "LIP ";
      lip.textContent = "--";
      barLevel = -1;
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

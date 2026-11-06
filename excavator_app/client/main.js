import "./style.css";
import "./remote.css";
import QRCode from "qrcode";
import { AXES, neutral, BUCKET } from "../shared/world.js";
import { decodeFrame, applyTiles } from "../shared/protocol.js";
import { NAME_LENGTH, cleanName } from "../shared/players.js";
import { createInputSender } from "./input-sender.js";
import {
  remoteFace,
  joinFace,
  createDisplay,
  createHaptics,
} from "./remote-face.js";

const remote = location.pathname === "/remote",
  app = document.querySelector("#app");
const $ = (selector) => document.querySelector(selector);
// A joystick stops moving this close to centre (fraction of full deflection).
const DEAD_ZONE = 0.12;
if (remote) {
  document.body.classList.add("remote");
  // Blend the phone's browser bars into the controller's shell.
  document.querySelector('meta[name="theme-color"]').content = "#313433";
}
const icons = {
  arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>',
  phone:
    '<rect x="7" y="2" width="10" height="20" rx="2"/><path d="M10 5h4m-3 14h2"/>',
  rotate: '<path d="M4 10a8 8 0 1 1 2 8M4 4v6h6"/>',
  expand: '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>',
  link: '<path d="m9 15 6-6m-6 8-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0m0-1 1-1a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0"/>',
  shovel:
    '<path d="M3 19h8m-6-3h5v3H5zm4 0V9l4-4 5 7m-6-6 5-2 4 8-4 3-3-3 3-2"/>',
  people:
    '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.8a3.5 3.5 0 0 1 0 6.4M18 14.3a6.5 6.5 0 0 1 3.5 5.7"/>',
};
const icon = (name) =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name]}</svg>`;
const brand = `<a class="brand" href="/" aria-label="Sand Lab home"><span class="brand-icon">${icon("shovel")}</span><span>SAND<span class="slash">/</span>LAB<small>REMOTE EARTHWORKS</small></span></a>`;
const connection = `<span class="connection" role="status"><i></i><span id="connection-text">Connecting</span></span>`;
const connectionHelp = `<div id="connection-help" role="alert" hidden><p id="connection-message"></p><div><button id="retry-connection" class="button small">Retry connection</button><a class="button small" href="${remote ? "/remote" : "/"}">${remote ? "Enter room code" : "Open a new game"}</a></div></div>`;

// One stick of the on-screen controls, with the track rocker beside it.
const stickPad = (id, label, top, bottom, left, right) =>
  `<div class="joystick-group"><div class="stick-label">${label}</div><span class="pad-top">${top}</span><div class="joystick" id="${id}" role="group" aria-label="${label} joystick"><span class="cross horizontal"></span><span class="cross vertical"></span><span class="pad-left">${left}</span><span class="pad-right">${right}</span><div class="knob"></div></div><span class="pad-bottom">${bottom}</span></div>`;
const trackPad = (axis, name) =>
  `<div class="track-pad"><span>${name}<br>TRACK</span><button class="hold" data-axis="${axis}" data-value="1" aria-label="${name} track forward">↑</button><button class="hold" data-axis="${axis}" data-value="-1" aria-label="${name} track reverse">↓</button></div>`;
const iconText = (name, text) => `${icon(name)}<span>${text}</span>`;

// The game fills the window: the world behind, instruments over it.
function gameScreen() {
  return `<main class="game"><section id="stage" aria-label="Excavator in an open world">
    <div id="loading"><span class="loader"></span>Preparing the valley…</div>
    <div class="hud-top">
      <div class="hud-identity">${brand}<div class="hud-session">${connection}<span class="session-code">ROOM <strong id="room-label">———</strong></span></div>${connectionHelp}<canvas id="minimap" width="360" height="360" role="img" aria-label="Map of the valley"></canvas></div>
      <div class="hud-actions"><div class="view-buttons" role="group" aria-label="Camera views"><button data-view="chase" class="active">Chase</button><button data-view="orbit">Orbit</button><button data-view="side">Side</button><button data-view="top">Top</button><button data-view="bucket">Bucket</button></div><button id="fullscreen" class="icon-button" aria-label="Toggle full screen">${icon("expand")}</button><button class="button hud-button" id="invite" aria-label="Invite players">${iconText("people", "Invite players")}</button><button class="button hud-button" data-pair aria-label="Pair your phone">${iconText("phone", "Pair your phone")}</button><button id="menu-toggle" class="button hud-button" aria-expanded="false" aria-controls="menu">Menu</button></div>
    </div>
    <aside id="roster" class="roster" aria-label="Players in this room"><button id="roster-toggle" class="roster-head" aria-expanded="true" aria-controls="player-list"><span>PLAYERS</span><strong id="player-count">—</strong></button><ol id="player-list"></ol></aside>
    <div class="hud-messages"><div id="watching" class="watching" hidden><span>Watching <strong id="watching-name"></strong></span><button id="watch-self" class="button small">Back to my excavator</button></div><div class="stop-banner" hidden>EMERGENCY STOP ENGAGED</div><div class="contact-banner" hidden>BUCKET ON HARD GROUND · RAISE THE BOOM</div><div class="obstacle-banner" hidden></div></div>
    <aside id="menu" class="menu" hidden aria-label="Game menu">
      <div class="menu-section menu-name"><label for="player-name">Your name</label><input id="player-name" maxlength="${NAME_LENGTH}" autocomplete="nickname" spellcheck="false"></div>
      <div class="menu-section"><span class="eyebrow">HOW TO PLAY</span><p>Drive with <kbd>I</kbd> <kbd>K</kbd> <kbd>J</kbd> <kbd>L</kbd>. The yard is straight ahead: lower the boom, crowd the stick, curl past 50 mm, lift, swing left to the pour zone and open the bucket. Everything else is yours to explore. The map shows where you are.</p><p class="key-table"><span><kbd>I</kbd> <kbd>K</kbd> drive</span><span><kbd>J</kbd> <kbd>L</kbd> turn</span><span><kbd>W</kbd> <kbd>S</kbd> stick</span><span><kbd>A</kbd> <kbd>D</kbd> slew</span><span><kbd>↑</kbd> <kbd>↓</kbd> boom down / up</span><span><kbd>←</kbd> <kbd>→</kbd> bucket</span><span><kbd>Q</kbd> <kbd>Z</kbd> left track</span><span><kbd>E</kbd> <kbd>C</kbd> right track</span></p></div>
      <div class="speed-control menu-section"><label for="speed">Movement speed</label><output id="speed-value">65%</output><input id="speed" type="range" min="20" max="100" step="5" value="65"></div>
      <div class="menu-section joint-readouts"><span>STICK <output id="stick-value">0.0 mm</output></span><span>BUCKET <output id="bucket-value">0.0 mm</output></span></div>
      <details class="keyboard-help menu-section"><summary>Hold-to-move buttons <span>↗</span></summary><div class="accessible-controls">${[
        ["boom", "Boom"],
        ["stick", "Stick"],
        ["bucket", "Bucket"],
        ["slew", "Slew"],
      ]
        .map(
          ([axis, label]) =>
            `<div><span>${label}</span><button class="hold" data-axis="${axis}" data-value="-1" aria-label="Decrease ${label}">−</button><button class="hold" data-axis="${axis}" data-value="1" aria-label="Increase ${label}">+</button></div>`,
        )
        .join("")}</div></details>
      <div class="menu-section menu-actions"><button id="respawn" class="button">Back to start</button><button id="reset" class="button">${iconText("rotate", "Reset world")}</button><a id="remote-link" class="button" href="/remote" target="_blank" rel="noopener">Remote control ↗</a></div>
      <p class="menu-status"><span id="particle-count">0</span> falling parcels · <span id="performance">30 Hz physics</span> · <span id="latency-value">— ms</span></p>
    </aside>
    <div class="hud-bottom">
      <div class="control-cluster">${stickPad("left-stick", "STICK / SLEW", "STICK OUT", "STICK IN", "L", "R")}${trackPad("leftTrack", "Left")}</div>
      <div class="hud-centre">
        <div class="ownership"><span id="operator-status">Waiting for connection</span><button id="claim" class="button small" disabled>Take control</button></div>
        <div class="telemetry"><div><span>BUCKET LOAD</span><strong id="load-value">0<small>cm³</small></strong><div class="meter"><i id="load-meter"></i></div></div><div><span>BOOM</span><strong id="boom-value">10.0<small>mm</small></strong><div class="meter"><i id="boom-meter"></i></div></div><div><span>SLEW</span><strong id="slew-value">0<small>°</small></strong><div class="meter"><i id="slew-meter"></i></div></div><div><span>DELIVERED</span><strong id="deposited-value">0<small>cm³</small></strong><div class="meter meter-empty"></div></div></div>
        <button id="estop" class="estop" data-estop><span class="stop-icon"></span><span>EMERGENCY STOP</span><kbd>SPACE</kbd></button>
        <button id="resume" class="button resume" hidden>Resume operation</button>
      </div>
      <div class="control-cluster control-cluster-right">${trackPad("rightTrack", "Right")}${stickPad("right-stick", "BOOM / BUCKET", "LOWER", "RAISE", "CURL", "OPEN")}</div>
    </div>
  </section></main>
  <dialog id="pair-dialog"><button class="dialog-close icon-button" aria-label="Close pairing dialog">×</button><span class="eyebrow">TAKE THE CONTROLS WITH YOU</span><h2>Your phone.<br>Your excavator.</h2><p>Connect both devices to the same network, then scan to open the remote.</p><div class="qr-wrap"><canvas id="qr"></canvas></div><div class="pair-room">ROOM <strong id="pair-code"></strong></div><label for="pair-base">Server address reachable from your phone</label><input id="pair-base" type="url"><p class="pair-hint">Use your computer’s LAN address or public HTTPS domain. localhost only works on this device.</p><div class="pair-actions"><button class="button primary" id="copy-link">Copy remote link</button><a class="button" id="open-remote" target="_blank" rel="noopener">Open remote ↗</a></div><p id="pair-feedback" role="status"></p></dialog>
  <dialog id="invite-dialog"><button class="dialog-close icon-button" aria-label="Close invite dialog">×</button><span class="eyebrow">ONE ROOM, ONE SAND YARD</span><h2>Everyone gets<br>an excavator.</h2><p>Anyone with this link joins this room with a machine of their own, in the same world.</p><div class="qr-wrap"><canvas id="invite-qr"></canvas></div><div class="pair-room">ROOM <strong id="invite-code"></strong></div><div class="invite-kind" role="radiogroup" aria-label="What the link opens"><label><input type="radio" name="invite-kind" value="game" checked><span>The full game</span></label><label><input type="radio" name="invite-kind" value="remote"><span>A phone controller</span></label></div><p class="pair-hint" id="invite-hint"></p><label for="invite-base">Server address your friends can reach</label><input id="invite-base" type="url"><div class="pair-actions"><button class="button primary" id="copy-invite">Copy invite link</button><a class="button" id="open-invite" target="_blank" rel="noopener">Open ↗</a></div><p id="invite-feedback" role="status"></p></dialog>
  <div id="toast" role="status" hidden></div>`;
}

// Storage can be missing in private browsing: choices then last as long as the
// page does, and a reload joins as a new player.
function stored(area, key, value) {
  try {
    if (value === undefined) return window[area].getItem(key) ?? "";
    window[area].setItem(key, value);
  } catch {
    /* See above. */
  }
  return value ?? "";
}
const savedName = () => stored("localStorage", "sandlab-name");
const saveName = (name) => stored("localStorage", "sandlab-name", name);

if (remote && !new URLSearchParams(location.search).get("room")) {
  app.innerHTML = joinFace();
  $("#join-name").value = savedName();
  $("#join").onsubmit = (event) => {
    event.preventDefault();
    saveName(cleanName($("#join-name").value));
    location.href =
      "/remote?room=" + $("#room-code").value.trim().toUpperCase();
  };
} else {
  start().catch((error) => fatal(error.message));
}

function fatal(message) {
  const target = $("#loading") || $("#toast");
  if (target) {
    target.hidden = false;
    target.textContent = message;
    target.classList.add("error");
  }
  const status = $("#connection-text");
  if (status) status.textContent = "Unavailable";
}

async function start() {
  app.innerHTML = remote
    ? remoteFace({ connection, connectionHelp })
    : gameScreen();

  let room = new URLSearchParams(location.search).get("room")?.toUpperCase();
  if (room && !/^[A-F0-9]{6}$/.test(room))
    throw new Error(
      "Invalid room code. Open /remote and enter the six-character code.",
    );
  let refreshLinks = () => {};
  // This device's claim on an excavator in this room. A paired phone arrives with
  // the owner's key in its link; a reloaded page finds its own in this tab.
  const playerSlot = () => `sandlab-player-${room}`;
  let playerKey = new URLSearchParams(location.search).get("pair") || "";
  function setRoom(code) {
    room = code;
    const url = new URL(location.href);
    url.searchParams.set("room", room);
    history.replaceState(null, "", url);
    $("#room-label").textContent = room;
    if ($("#sheet-room")) $("#sheet-room").textContent = room;
    refreshLinks();
  }
  if (room) {
    setRoom(room);
    playerKey ||= stored("sessionStorage", playerSlot());
  }
  let ws,
    id,
    state,
    me = null,
    roster = null,
    scene,
    sandFrame,
    sandBed = new Map(),
    retry = 0,
    reconnectTimer,
    toastTimer,
    speed = 0.65,
    claimPending = false,
    connecting = false,
    closed = false;
  let axes = neutral();
  const keyState = new Set(),
    pointerSources = new Map();
  const estops = document.querySelectorAll("[data-estop]");
  const display = remote ? createDisplay() : null,
    haptics = remote ? createHaptics() : { pulse() {} },
    settingsSheet = $("#settings-sheet");
  const send = (data) => {
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(data));
  };
  const isOwner = () => state?.owner === id && !!id;
  const controlsAvailable = () =>
    !!id &&
    !!state &&
    (!state.owner || isOwner()) &&
    !state.estop &&
    ws?.readyState === WebSocket.OPEN;
  const inputSender = createInputSender(() => {
    if (
      isOwner() &&
      !document.hidden &&
      ws?.readyState === WebSocket.OPEN &&
      ws.bufferedAmount === 0
    )
      send({ type: "input", axes, speed });
  });
  const toast = (message) => {
    const el = $("#toast");
    el.textContent = message;
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      el.hidden = true;
    }, 4500);
  };
  function requestControl() {
    if (isOwner() || claimPending) return;
    claimPending = true;
    send({ type: "claim" });
  }
  function beginInput() {
    if (document.hidden) return false;
    if (!controlsAvailable()) {
      toast(
        !id || !state || ws?.readyState !== WebSocket.OPEN
          ? "Waiting for connection. Try again when connected."
          : state.estop
            ? "Resume operation before moving."
            : "Your other device has control. Release it there first.",
      );
      return false;
    }
    requestControl();
    return true;
  }
  function clearInputs() {
    axes = neutral();
    keyState.clear();
    pointerSources.clear();
    document
      .querySelectorAll(".joystick")
      .forEach((el) => el.dispatchEvent(new Event("controlsreset")));
    document
      .querySelectorAll(".hold.pressed")
      .forEach((el) => el.classList.remove("pressed"));
    // Even a hidden page must send its final neutral packet before releasing.
    inputSender.flush();
    if (document.hidden && isOwner()) send({ type: "input", axes, speed });
  }
  const keys = {
    w: [["stick", -1]],
    s: [["stick", 1]],
    a: [["slew", -1]],
    d: [["slew", 1]],
    ArrowUp: [["boom", -1]],
    ArrowDown: [["boom", 1]],
    ArrowLeft: [["bucket", 1]],
    ArrowRight: [["bucket", -1]],
    q: [["leftTrack", 1]],
    z: [["leftTrack", -1]],
    e: [["rightTrack", 1]],
    c: [["rightTrack", -1]],
    // Both tracks together, so one finger can steer the machine anywhere.
    i: [
      ["leftTrack", 1],
      ["rightTrack", 1],
    ],
    k: [
      ["leftTrack", -1],
      ["rightTrack", -1],
    ],
    j: [
      ["leftTrack", -1],
      ["rightTrack", 1],
    ],
    l: [
      ["leftTrack", 1],
      ["rightTrack", -1],
    ],
  };
  function gatherAxes() {
    const previous = axes;
    axes = neutral();
    for (const source of pointerSources.values())
      for (const [axis, value] of Object.entries(source)) axes[axis] += value;
    for (const key of keyState)
      for (const [axis, value] of keys[key]) axes[axis] += value;
    for (const key of AXES) axes[key] = Math.max(-1, Math.min(1, axes[key]));
    if (AXES.some((key) => axes[key] !== previous[key]))
      inputSender.schedule(
        AXES.some((key) => Math.sign(axes[key]) !== Math.sign(previous[key])),
      );
  }
  for (const [name, horizontal, vertical] of [
    ["left", "slew", "stick"],
    ["right", "bucket", "boom"],
  ]) {
    const pad = $("#" + name + "-stick"),
      knob = pad.querySelector(".knob");
    let pointer = null,
      grabX = 0,
      grabY = 0,
      pushed = false,
      atStop = false;
    // The stylesheet draws the stick from --x/--y, each -1..1 of its travel.
    function tilt(x, y) {
      pad.style.setProperty("--x", x);
      pad.style.setProperty("--y", y);
      pad.classList.toggle("held", pointer !== null);
      pad.dataset.h = Math.abs(x) < DEAD_ZONE ? "" : x < 0 ? "w" : "e";
      pad.dataset.v = Math.abs(y) < DEAD_ZONE ? "" : y < 0 ? "n" : "s";
    }
    function letGo() {
      pointer = null;
      pushed = atStop = false;
      tilt(0, 0);
    }
    pad.addEventListener("controlsreset", () => {
      if (pointer !== null && pad.hasPointerCapture(pointer))
        pad.releasePointerCapture(pointer);
      letGo();
    });
    function move(event) {
      if (pointer !== event.pointerId || !controlsAvailable()) return;
      const rect = pad.getBoundingClientRect(),
        radius = rect.width * (remote ? 0.24 : 0.32);
      let x = (event.clientX - rect.left - rect.width / 2 - grabX) / radius,
        y = (event.clientY - rect.top - rect.height / 2 - grabY) / radius;
      const length = Math.hypot(x, y);
      if (length > 1) {
        x /= length;
        y /= length;
      }
      pad.style.setProperty("--reach", radius + "px");
      tilt(x, y);
      const offCentre = Math.abs(x) >= DEAD_ZONE || Math.abs(y) >= DEAD_ZONE;
      if (offCentre && !pushed) haptics.pulse(8);
      if (length >= 1 && !atStop) haptics.pulse(14);
      pushed = offCentre;
      atStop = length >= 1;
      pointerSources.set(name, {
        [horizontal]:
          (Math.abs(x) < DEAD_ZONE ? 0 : x) * (name === "right" ? -1 : 1),
        [vertical]: Math.abs(y) < DEAD_ZONE ? 0 : y,
      });
      gatherAxes();
    }
    pad.addEventListener("pointerdown", (event) => {
      if (pointer !== null) return;
      if (!beginInput()) return;
      pointer = event.pointerId;
      pad.setPointerCapture(pointer);
      // A thumb landing on the cap grabs it where it is, so a press alone never
      // moves the machine. Pressing beside the cap jumps the stick to the thumb.
      const rect = pad.getBoundingClientRect(),
        fromCentreX = event.clientX - rect.left - rect.width / 2,
        fromCentreY = event.clientY - rect.top - rect.height / 2,
        onCap = Math.hypot(fromCentreX, fromCentreY) <= knob.offsetWidth / 2;
      grabX = onCap ? fromCentreX : 0;
      grabY = onCap ? fromCentreY : 0;
      move(event);
      event.preventDefault();
    });
    pad.addEventListener("pointermove", move);
    const end = (event) => {
      if (event.pointerId !== pointer) return;
      letGo();
      pointerSources.delete(name);
      gatherAxes();
    };
    for (const event of ["pointerup", "pointercancel", "lostpointercapture"])
      pad.addEventListener(event, end);
  }
  document.querySelectorAll(".hold").forEach((button, index) => {
    const name = "button" + index;
    const down = () => {
      if (!beginInput()) return;
      pointerSources.set(name, {
        [button.dataset.axis]: +button.dataset.value,
      });
      if (!button.classList.contains("pressed")) haptics.pulse(10);
      button.classList.add("pressed");
      gatherAxes();
    };
    const up = () => {
      pointerSources.delete(name);
      button.classList.remove("pressed");
      gatherAxes();
    };
    button.onpointerdown = (event) => {
      button.setPointerCapture(event.pointerId);
      down();
      event.preventDefault();
    };
    for (const event of [
      "pointerup",
      "pointercancel",
      "lostpointercapture",
      "blur",
    ])
      button.addEventListener(event, up);
    button.onkeydown = (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        down();
      }
    };
    button.onkeyup = (event) => {
      if (event.key === "Enter") up();
    };
  });
  window.addEventListener("keydown", (event) => {
    if (
      ["INPUT", "TEXTAREA"].includes(event.target.tagName) ||
      $("#pair-dialog")?.open ||
      $("#invite-dialog")?.open ||
      settingsSheet?.open
    )
      return;
    if (event.code === "Space") {
      event.preventDefault();
      clearInputs();
      send({ type: "estop" });
      return;
    }
    const key = event.key.length === 1 ? event.key.toLowerCase() : event.key;
    if (keys[key] && beginInput()) {
      event.preventDefault();
      keyState.add(key);
      gatherAxes();
    }
  });
  window.addEventListener("keyup", (event) => {
    const key = event.key.length === 1 ? event.key.toLowerCase() : event.key;
    keyState.delete(key);
    gatherAxes();
  });
  window.addEventListener("blur", clearInputs);
  document.addEventListener("visibilitychange", () => {
    clearInputs();
    if (document.hidden && (isOwner() || claimPending)) {
      send({ type: "release" });
      claimPending = false;
    }
  });
  window.addEventListener("pagehide", () => {
    closed = true;
    clearInputs();
    send({ type: "release" });
    ws?.close();
    clearTimeout(reconnectTimer);
  });
  $("#claim").onclick = () => {
    clearInputs();
    if (isOwner() || claimPending) {
      send({ type: "release" });
      claimPending = false;
    } else requestControl();
  };
  function showSpeed() {
    setReadout("#speed-value", Math.round(speed * 100) + "%");
    display?.speed(speed);
  }
  $("#speed").oninput = (event) => {
    speed = +event.target.value / 100;
    showSpeed();
    haptics.pulse(5);
    inputSender.schedule();
  };
  estops.forEach((button) => {
    button.onclick = () => {
      clearInputs();
      send({ type: "estop" });
      haptics.pulse([30, 40, 30]);
      settingsSheet?.close();
    };
  });
  $("#resume").onclick = () => {
    clearInputs();
    send({ type: "resume" });
  };
  $("#reset").onclick = () => {
    if (!isOwner()) return toast("Take control before resetting the world.");
    if (!state.host) return toast("Only the host can reset the world.");
    clearInputs();
    send({ type: "reset" });
    settingsSheet?.close();
    toast("World reset. Back at the sand yard.");
  };
  $("#respawn").onclick = () => {
    if (!isOwner()) return toast("Take control before moving the excavator.");
    clearInputs();
    send({ type: "respawn" });
    settingsSheet?.close();
    toast("Back at a start position.");
  };
  $("#player-name").value = savedName();
  $("#player-name").onchange = (event) => {
    const name = cleanName(event.target.value);
    if (!name) {
      event.target.value = me?.name ?? "";
      return;
    }
    event.target.value = name;
    saveName(name);
    send({ type: "rename", name });
  };
  if (remote) setupSettings(settingsSheet, clearInputs, haptics);

  let controlMode;
  function setReadout(selector, value) {
    const element = $(selector);
    if (element.innerHTML !== value) element.innerHTML = value;
  }
  function updateUI(next) {
    const ownedBefore = isOwner(),
      stoppedBefore = state?.estop,
      blockedBefore = state?.stats.blocked;
    state = next;
    if (
      (ownedBefore && !isOwner()) ||
      (!stoppedBefore && state.estop) ||
      (claimPending && state.owner && !isOwner())
    )
      clearInputs();
    // A stop from any device brings the operator back to the controls.
    if (!stoppedBefore && state.estop) settingsSheet?.close();
    if (state.owner) claimPending = false;
    // Only send the current, still-held input after the server grants control.
    if (!ownedBefore && isOwner()) inputSender.flush();
    const owner = isOwner(),
      live = ws?.readyState === WebSocket.OPEN;
    const nextMode = `${owner}:${state.owner}:${state.estop}:${live}:${state.host}`;
    if (nextMode !== controlMode) {
      controlMode = nextMode;
      $("#claim").disabled = !live;
      $("#claim").textContent = owner ? "Release" : "Take control";
      $("#operator-status").textContent = owner
        ? "You have control"
        : state.owner
          ? "Your other device is driving"
          : state.estop
            ? "Take control to resume"
            : "Move a control to start";
      $(".ownership").classList.toggle("owned", owner);
      document.querySelectorAll(".hold").forEach((el) => {
        el.disabled = !controlsAvailable();
      });
      $("#speed").disabled = !owner || state.estop || !live;
      document
        .querySelectorAll(".joystick")
        .forEach((el) => el.classList.toggle("disabled", !controlsAvailable()));
      $("#reset").disabled = !owner || !live || !state.host;
      $("#reset").title = state.host ? "" : "Only the host can reset the world.";
      if ($("#reset-note"))
        $("#reset-note").textContent = state.host
          ? "Everything goes back to the start. You need control to do this."
          : "Only the host of this room can do this.";
      $("#respawn").disabled = !owner || !live;
      // The remote has one key for both: an operator stopped by the E-stop
      // needs Resume, and anyone else needs to take control first.
      const resumeKey = state.estop && (owner || !remote);
      $("#resume").hidden = !resumeKey;
      $("#resume").disabled = !owner;
      if (remote) $("#claim").hidden = resumeKey;
      estops.forEach((el) => el.classList.toggle("engaged", state.estop));
      if ($(".stop-banner")) $(".stop-banner").hidden = !state.estop;
    }
    if (!owner) {
      speed = state.speed;
      $("#speed").value = speed * 100;
      showSpeed();
    }
    if (remote) {
      const blocked = state.stats.blocked && !state.estop;
      display.machine(state.machine, state.stats);
      display.flags(state.estop, blocked);
      if (blocked && !blockedBefore) haptics.pulse(40);
    } else {
      setReadout(
        "#boom-value",
        state.machine.strokes[0].toFixed(1) + "<small>mm</small>",
      );
      setReadout(
        "#load-value",
        Math.round(state.stats.load) + "<small>cm³</small>",
      );
      setReadout("#stick-value", state.machine.strokes[1].toFixed(1) + " mm");
      setReadout("#bucket-value", state.machine.strokes[2].toFixed(1) + " mm");
      setReadout(
        "#slew-value",
        state.machine.slew.toFixed(0) + "<small>°</small>",
      );
      setReadout(
        "#deposited-value",
        Math.round(state.stats.deposited) + "<small>cm³</small>",
      );
      setReadout("#particle-count", state.count.toLocaleString("en-US"));
      $("#load-meter").style.width =
        Math.min(100, (state.stats.load / BUCKET.ratedLoad) * 100) + "%";
      $(".contact-banner").hidden = !state.stats.blocked || state.estop;
      const obstacle = !state.estop && state.stats.obstacle,
        obstacleBanner = $(".obstacle-banner");
      obstacleBanner.hidden = !obstacle;
      if (obstacle)
        obstacleBanner.textContent = {
          object: "SOMETHING IN THE WAY · BACK UP OR TURN",
          steep: "TOO STEEP TO CLIMB · BACK DOWN",
          water: "TOO DEEP · BACK UP",
          machine: "ANOTHER EXCAVATOR IN THE WAY · BACK UP OR TURN",
        }[obstacle];
      $("#boom-meter").style.width =
        (state.machine.strokes[0] / 60) * 100 + "%";
      $("#slew-meter").style.width = (state.machine.slew + 150) / 3 + "%";
      if (scene) {
        scene.setState(state);
        const { fps, pixelRatio } = scene.telemetry();
        $("#performance").textContent =
          `${fps ? `${fps} fps at ${pixelRatio.toFixed(2)}×` : "View idle"} · ${state.stepMs} ms physics`;
      }
    }
  }
  // Who this device drives. The key moves out of a pairing link and into the tab,
  // so the address bar stays safe to share: as a link it invites a new player.
  function becomePlayer(player) {
    me = player;
    playerKey = player.key;
    stored("sessionStorage", playerSlot(), playerKey);
    const url = new URL(location.href);
    if (url.searchParams.has("pair")) {
      url.searchParams.delete("pair");
      history.replaceState(null, "", url);
    }
    $("#player-name").value = player.name;
    if (remote) {
      const chip = $("#rc-player");
      chip.hidden = false;
      chip.style.setProperty("--paint", player.paint);
      chip.lastElementChild.textContent = player.name;
    }
    scene?.setSelf(player.id);
    refreshLinks();
  }
  function updateRoster(next) {
    const before = roster?.players ?? [],
      known = new Set(before.map((p) => p.id)),
      now = new Set(next.players.map((p) => p.id));
    roster = next;
    // Say who came and went, once this page knows who was there.
    if (me && before.length) {
      for (const player of next.players)
        if (!known.has(player.id) && player.id !== me.id)
          toast(`${player.name} joined the room.`);
      for (const player of before)
        if (!now.has(player.id)) toast(`${player.name} left the room.`);
    }
    const self = next.players.find((p) => p.id === me?.id);
    if (self && me.name !== self.name) {
      me.name = self.name;
      if (document.activeElement !== $("#player-name"))
        $("#player-name").value = self.name;
      if (remote) $("#rc-player").lastElementChild.textContent = self.name;
    }
    if (remote) {
      const others = next.players.length - 1;
      $("#sheet-players").textContent = others
        ? `With ${others} other${others > 1 ? "s" : ""}, ${next.players.length} of ${next.capacity}`
        : "Only you here";
      return;
    }
    scene?.setRoster(next.players);
    drawRoster();
  }
  function drawRoster() {
    if (!roster || remote) return;
    $("#player-count").textContent = `${roster.players.length}/${roster.capacity}`;
    const following = scene?.following ?? me?.id;
    const rows = roster.players.map((player) => {
      const row = document.createElement("li"),
        button = document.createElement("button"),
        swatch = document.createElement("i"),
        name = document.createElement("span"),
        note = document.createElement("small"),
        mine = player.id === me?.id;
      button.className = "player";
      button.classList.toggle("followed", player.id === following);
      button.classList.toggle("offline", !player.online);
      button.setAttribute(
        "aria-label",
        mine ? "Follow my excavator" : `Watch ${player.name}`,
      );
      swatch.style.background = player.paint;
      name.textContent = player.name;
      note.textContent = [
        mine ? "you" : "",
        roster.host === player.id ? "host" : "",
        player.online ? "" : "offline",
      ]
        .filter(Boolean)
        .join(" · ");
      button.append(swatch, name, note);
      button.onclick = () => watch(player.id);
      row.append(button);
      return row;
    });
    $("#player-list").replaceChildren(...rows);
    const watched =
      following !== me?.id &&
      roster.players.find((player) => player.id === following);
    $("#watching").hidden = !watched;
    if (watched) $("#watching-name").textContent = watched.name;
  }
  function watch(playerId) {
    scene?.follow(playerId);
    drawRoster();
  }
  function disableControls() {
    $("#claim").disabled = true;
    estops.forEach((el) => {
      el.disabled = true;
    });
    $("#resume").disabled = true;
    if (remote) {
      $("#claim").hidden = false;
      $("#resume").hidden = true;
      display.latency(null);
    }
    $("#reset").disabled = true;
    $("#respawn").disabled = true;
    $("#operator-status").textContent = "Waiting for connection";
    $(".ownership").classList.remove("owned");
    document.querySelectorAll(".hold, #speed").forEach((el) => {
      el.disabled = true;
    });
    document.querySelectorAll(".joystick").forEach((el) => {
      el.classList.add("disabled");
    });
  }
  function connectionFailed(message, retryable = true) {
    connecting = false;
    if (closed) return;
    $("#connection-help").hidden = false;
    $("#connection-message").textContent = message;
    $("#retry-connection").hidden = !retryable;
    if (retryable && ++retry < 6) {
      $("#connection-text").textContent = "Reconnecting";
      reconnectTimer = setTimeout(connect, Math.min(8000, 500 * 2 ** retry));
    } else $("#connection-text").textContent = "Disconnected";
  }
  async function connect() {
    if (closed || connecting) return;
    connecting = true;
    clearTimeout(reconnectTimer);
    $("#connection-help").hidden = true;
    $("#connection-text").textContent = "Connecting";
    try {
      let missing = !room;
      if (room) {
        // Browser WebSocket errors hide the HTTP rejection reason. Check the
        // room first so an expired link can recover without retrying forever.
        const response = await fetch(
          `/api/rooms/${room}?key=${encodeURIComponent(playerKey)}`,
          { signal: AbortSignal.timeout(10000) },
        );
        const result = await response.json();
        if (closed) return;
        missing = response.status === 404 && result.code === "ROOM_NOT_FOUND";
        if (missing && remote) {
          connectionFailed(
            "This room has expired or the server has restarted. Scan the simulator’s new QR code or enter its current room code.",
            false,
          );
          return;
        }
        if (!response.ok && !missing) throw new Error(result.error);
        if (!missing && !result.member && result.players >= result.capacity)
          throw new Error(
            `This room is full: all ${result.capacity} excavators are taken. Retry when someone leaves, or open a new game.`,
          );
      }
      if (missing) {
        const response = await fetch("/api/rooms", {
          method: "POST",
          signal: AbortSignal.timeout(10000),
        });
        const result = await response.json();
        if (closed) return;
        if (!response.ok) throw new Error(result.error);
        const previousRoom = room;
        playerKey = "";
        setRoom(result.room);
        if (previousRoom) {
          state = null;
          me = null;
          roster = null;
          sandFrame = null;
          sandBed.clear();
          scene?.newRoom();
          toast(
            "The previous room ended. A new game is ready; pair your phone and invite your friends again.",
          );
        }
      }
      const query = new URLSearchParams({
        room,
        role: remote ? "remote" : "simulator",
      });
      if (playerKey) query.set("key", playerKey);
      if (savedName()) query.set("name", savedName());
      ws = new WebSocket(
        `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws?${query}`,
      );
    } catch (error) {
      connectionFailed(
        error.message ||
          "Could not reach the server. Check your connection and retry.",
      );
      return;
    }
    ws.binaryType = "arraybuffer";
    ws.onopen = () => {
      connecting = false;
      retry = 0;
      $(".connection").classList.add("online");
      $("#connection-text").textContent = "Connected";
      estops.forEach((el) => {
        el.disabled = false;
      });
    };
    ws.onmessage = (event) => {
      if (typeof event.data !== "string") {
        // Machine poses and loads, falling sand and changed sand-bed tiles of one tick.
        const frame = decodeFrame(event.data);
        if (scene) scene.pushFrame(frame);
        else {
          applyTiles(sandBed, frame.tiles);
          sandFrame = frame;
        }
        return;
      }
      const message = JSON.parse(event.data);
      if (message.type === "welcome") {
        id = message.id;
        becomePlayer(message.player);
        if (remote && !document.hidden) requestControl();
      }
      if (message.type === "state") updateUI(message);
      if (message.type === "roster") updateRoster(message);
      if (message.type === "notice") toast(message.message);
      if (message.type === "error") {
        if (claimPending) {
          claimPending = false;
          clearInputs();
        }
        toast(message.message);
      }
      if (message.type === "pong") {
        const ms = Math.round(performance.now() - message.at);
        if (remote) display.latency(ms);
        else $("#latency-value").textContent = `${ms} ms`;
      }
    };
    ws.onclose = () => {
      clearInputs();
      id = null;
      claimPending = false;
      controlMode = undefined;
      $(".connection").classList.remove("online");
      disableControls();
      connectionFailed(
        "Connection lost. Retrying this room. If it persists, check that the server allows WebSocket connections.",
      );
    };
    ws.onerror = () => {
      /* close handler owns reconnection */
    };
  }
  $("#retry-connection").onclick = () => {
    retry = 0;
    connect();
  };
  disableControls();
  connect();
  // Held controls keep the 350 ms server watchdog alive.
  setInterval(() => inputSender.schedule(), 100);
  setInterval(() => send({ type: "ping", at: performance.now() }), 2000);
  // Read-only telemetry is also useful to automated browser checks.
  window.sandLab = {
    getState: () => state,
    getGraphics: () => scene?.telemetry(),
    getRoom: () => room,
    getRoster: () => roster,
    getPlayer: () => me,
  };

  if (!remote) {
    const menu = $("#menu"),
      menuToggle = $("#menu-toggle");
    menuToggle.onclick = () => {
      menu.hidden = !menu.hidden;
      menuToggle.setAttribute("aria-expanded", String(!menu.hidden));
    };
    // The top buttons wrap on a narrow screen; what opens below them follows.
    const stage = $("#stage"),
      actions = $(".hud-actions");
    new ResizeObserver(() =>
      stage.style.setProperty(
        "--actions-bottom",
        `${actions.getBoundingClientRect().bottom - stage.getBoundingClientRect().top}px`,
      ),
    ).observe(actions);
    $("#roster-toggle").onclick = () => {
      const list = $("#player-list");
      list.hidden = !list.hidden;
      $("#roster-toggle").setAttribute("aria-expanded", String(!list.hidden));
    };
    // There is little room on a phone: the list opens when it is asked for.
    if (matchMedia("(max-width: 760px), (max-height: 620px)").matches)
      $("#roster-toggle").click();
    $("#watch-self").onclick = () => watch(me?.id ?? null);
    setupSharing(() => room, () => (me ? playerKey : null), toast, clearInputs).then(
      (update) => {
        refreshLinks = update;
        update();
      },
    );
    $("#fullscreen").onclick = async () => {
      try {
        if (document.fullscreenElement) await document.exitFullscreen();
        else await $("#stage").requestFullscreen();
      } catch {
        toast("Full screen is unavailable in this browser.");
      }
    };
    try {
      const { createScene } = await import("./scene.js");
      scene = await createScene($("#stage"), (message) => {
        $("#loading").hidden = !message;
        if (message) $("#loading").textContent = message;
      });
      if (state) scene.setState(state);
      if (me) scene.setSelf(me.id);
      if (roster) scene.setRoster(roster.players);
      drawRoster();
      // Frames that arrived while the model loaded are already in sandBed.
      if (sandBed.size) scene.setTerrain(sandBed);
      sandBed.clear();
      if (sandFrame) scene.pushFrame({ ...sandFrame, tiles: [] });
      scene.attachMinimap($("#minimap"));
      document.querySelectorAll("[data-view]").forEach((button) => {
        button.onclick = () => {
          scene.view(button.dataset.view);
          document
            .querySelectorAll("[data-view]")
            .forEach((b) => b.classList.toggle("active", b === button));
        };
      });
    } catch (error) {
      fatal(
        error.message +
          " Try a browser with WebGL enabled. The phone remote still works.",
      );
    }
  }
}

// The remote's settings sheet. It is modal, so opening it stops this operator's
// movement first; it carries its own emergency stop for the same reason.
function setupSettings(sheet, clearInputs, haptics) {
  $("#settings").onclick = () => {
    clearInputs();
    sheet.showModal();
  };
  $("#settings-close").onclick = () => sheet.close();
  // A tap outside the panel lands on the dialog element itself.
  sheet.addEventListener("click", (event) => {
    if (event.target === sheet) sheet.close();
  });
  // Touch browsers need a touch listener before they show :active presses.
  document.addEventListener("touchstart", () => {}, { passive: true });
  document.querySelectorAll(".rc-key, .rc-estop").forEach((key) => {
    key.addEventListener("pointerdown", () => {
      if (!key.disabled) haptics.pulse(10);
    });
  });
  if (haptics.supported) {
    $("#haptics-row").hidden = false;
    $("#haptics").checked = haptics.enabled;
    $("#haptics").onchange = (event) => {
      haptics.set(event.target.checked);
      haptics.pulse(20);
    };
  }
  if (document.documentElement.requestFullscreen) {
    const toggle = $("#fullscreen-toggle");
    $("#fullscreen-row").hidden = false;
    toggle.onchange = () => {
      const request = toggle.checked
        ? document.documentElement.requestFullscreen()
        : document.exitFullscreen();
      // A refused request leaves the switch showing the real state.
      request.catch(() => {
        toggle.checked = !!document.fullscreenElement;
      });
    };
    document.addEventListener("fullscreenchange", () => {
      toggle.checked = !!document.fullscreenElement;
    });
  }
}

// The two links a page hands out, each with a QR code: one pairs your phone with
// your excavator, the other brings someone new into the room.
async function setupSharing(getRoom, getKey, toast, clearInputs) {
  let base = location.origin;
  try {
    const network = await (await fetch("/api/network")).json();
    if (network.publicUrl) base = network.publicUrl;
    else if (
      ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname) &&
      network.origins.length
    )
      base = network.origins[0];
  } catch {
    /* The displayed address remains editable. */
  }
  const inviteKind = () =>
    document.querySelector('input[name="invite-kind"]:checked').value;
  const dialogs = [
    {
      dialog: $("#pair-dialog"),
      qr: $("#qr"),
      baseInput: $("#pair-base"),
      code: $("#pair-code"),
      copy: $("#copy-link"),
      open: $("#open-remote"),
      feedback: $("#pair-feedback"),
      copied: "Remote link copied.",
      link(origin, room) {
        const key = getKey();
        return (
          key &&
          `${origin}/remote?room=${room}&pair=${encodeURIComponent(key)}`
        );
      },
    },
    {
      dialog: $("#invite-dialog"),
      qr: $("#invite-qr"),
      baseInput: $("#invite-base"),
      code: $("#invite-code"),
      copy: $("#copy-invite"),
      open: $("#open-invite"),
      feedback: $("#invite-feedback"),
      copied: "Invite link copied.",
      link(origin, room) {
        return `${origin}${inviteKind() === "remote" ? "/remote" : "/"}?room=${room}`;
      },
    },
  ];
  async function refresh(share) {
    const room = getRoom();
    share.code.textContent = room || "———";
    share.current = null;
    share.open.removeAttribute("href");
    share.copy.disabled = true;
    if (!room) {
      share.feedback.textContent =
        "Waiting for a game. Check the server connection.";
      return;
    }
    let link;
    try {
      const url = new URL(share.baseInput.value);
      if (!["http:", "https:"].includes(url.protocol)) throw new Error();
      link = share.link(url.origin, room);
    } catch {
      share.feedback.textContent =
        "Enter a complete http:// or https:// server address.";
      return;
    }
    if (!link) {
      share.feedback.textContent = "Waiting for your excavator…";
      return;
    }
    share.current = link;
    share.open.href = link;
    share.copy.disabled = false;
    share.feedback.textContent = "";
    await QRCode.toCanvas(share.qr, link, {
      width: 208,
      margin: 1,
      color: { dark: "#26332b", light: "#ffffff" },
      errorCorrectionLevel: "M",
    });
  }
  const refreshAll = () => {
    const room = getRoom(),
      remoteLink = $("#remote-link");
    if (remoteLink && room && getKey())
      remoteLink.href = `/remote?room=${room}&pair=${encodeURIComponent(getKey())}`;
    return Promise.all(dialogs.map(refresh));
  };
  const hints = {
    game: "Opens the whole game, on a computer or a phone with a good graphics chip.",
    remote:
      "Opens just the controls, for everyone sharing a big screen. Click a name in the player list there to watch that machine.",
  };
  const showHint = () => {
    $("#invite-hint").textContent = hints[inviteKind()];
  };
  showHint();
  document.querySelectorAll('input[name="invite-kind"]').forEach((radio) => {
    radio.onchange = () => {
      showHint();
      refresh(dialogs[1]);
    };
  });
  for (const share of dialogs) {
    share.baseInput.value = base;
    share.baseInput.oninput = () => refresh(share);
    share.dialog.querySelector(".dialog-close").onclick = () =>
      share.dialog.close();
    share.dialog.addEventListener("click", (event) => {
      const box = share.dialog.getBoundingClientRect();
      if (
        event.target === share.dialog &&
        (event.clientX < box.left ||
          event.clientX > box.right ||
          event.clientY < box.top ||
          event.clientY > box.bottom)
      )
        share.dialog.close();
    });
    share.copy.onclick = async () => {
      if (!share.current) return;
      try {
        await navigator.clipboard.writeText(share.current);
        share.feedback.textContent = share.copied;
      } catch {
        share.feedback.textContent = share.current;
        toast("Copy the address shown below the buttons.");
      }
    };
  }
  document.querySelectorAll("[data-pair]").forEach((button) => {
    button.onclick = () => {
      clearInputs();
      dialogs[0].dialog.showModal();
    };
  });
  $("#invite").onclick = () => {
    clearInputs();
    dialogs[1].dialog.showModal();
  };
  await refreshAll();
  return refreshAll;
}

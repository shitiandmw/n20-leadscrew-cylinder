import "./style.css";
import QRCode from "qrcode";
import { AXES, neutral } from "../shared/world.js";
import { createInputSender } from "./input-sender.js";

const remote = location.pathname === "/remote",
  app = document.querySelector("#app");
const $ = (selector) => document.querySelector(selector);
const icons = {
  arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>',
  phone:
    '<rect x="7" y="2" width="10" height="20" rx="2"/><path d="M10 5h4m-3 14h2"/>',
  rotate: '<path d="M4 10a8 8 0 1 1 2 8M4 4v6h6"/>',
  expand: '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>',
  link: '<path d="m9 15 6-6m-6 8-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0m0-1 1-1a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0"/>',
  shovel:
    '<path d="M3 19h8m-6-3h5v3H5zm4 0V9l4-4 5 7m-6-6 5-2 4 8-4 3-3-3 3-2"/>',
};
const icon = (name) =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name]}</svg>`;
const brand = `<a class="brand" href="/" aria-label="Sand Lab home"><span class="brand-icon">${icon("shovel")}</span><span>SAND<span class="slash">/</span>LAB<small>REMOTE EARTHWORKS</small></span></a>`;
const connection = `<span class="connection" role="status"><i></i><span id="connection-text">Connecting</span></span>`;
const connectionHelp = `<div id="connection-help" role="alert" hidden><p id="connection-message"></p><div><button id="retry-connection" class="button small">Retry connection</button><a class="button small" href="${remote ? "/remote" : "/"}">${remote ? "Enter room code" : "Open a new sandbox"}</a></div></div>`;

function controls() {
  return `<div class="operator-heading"><div><span class="eyebrow">OPERATOR STATION</span><h2>${remote ? "Make your move." : "You’re in the driver’s seat."}</h2></div><span class="mode-tag">ISO</span></div>
  <div class="ownership"><span id="operator-status">Waiting for connection</span><button id="claim" class="button small" disabled>Take control</button></div>
  <div class="joysticks">
    <div class="joystick-group"><div class="stick-label"><b>01</b> STICK / SLEW</div><span class="pad-top">STICK OUT</span><div class="joystick" id="left-stick" role="group" aria-label="Left joystick: stick and slew"><span class="cross horizontal"></span><span class="cross vertical"></span><span class="pad-left">L</span><span class="pad-right">R</span><div class="knob"></div><span class="pad-dot"></span></div><span class="pad-bottom">STICK IN</span></div>
    <div class="joystick-group"><div class="stick-label"><b>02</b> BOOM / BUCKET</div><span class="pad-top">LOWER</span><div class="joystick" id="right-stick" role="group" aria-label="Right joystick: boom and bucket"><span class="cross horizontal"></span><span class="cross vertical"></span><span class="pad-left">CURL</span><span class="pad-right">OPEN</span><div class="knob"></div><span class="pad-dot"></span></div><span class="pad-bottom">RAISE</span></div>
  </div>
  <div class="joint-readouts"><span>STICK <output id="stick-value">0.0 mm</output></span><span>BUCKET <output id="bucket-value">0.0 mm</output></span></div>
  <p class="control-tip">Hold to move. Curl past 50 mm before lifting.</p>
  <div class="track-heading"><span class="eyebrow">TRACK DRIVE</span><span>Hold to travel</span></div>
  <div class="track-controls"><div><span>LEFT TRACK</span><button class="hold" data-axis="leftTrack" data-value="1" aria-label="Left track forward">↑</button><button class="hold" data-axis="leftTrack" data-value="-1" aria-label="Left track reverse">↓</button></div><div><span>RIGHT TRACK</span><button class="hold" data-axis="rightTrack" data-value="1" aria-label="Right track forward">↑</button><button class="hold" data-axis="rightTrack" data-value="-1" aria-label="Right track reverse">↓</button></div></div>
  <div class="speed-control"><label for="speed">Movement speed</label><output id="speed-value">65%</output><input id="speed" type="range" min="20" max="100" step="5" value="65"></div>
  <button id="estop" class="estop"><span class="stop-icon"></span><span>EMERGENCY STOP</span><kbd>SPACE</kbd></button>
  <button id="resume" class="button resume" hidden>Resume operation</button>
  <details class="keyboard-help"><summary>${remote ? "Button controls & guide" : "Keyboard & button controls"} <span>↗</span></summary><p>W/S · stick out/in &nbsp; A/D · slew<br>↑/↓ · boom lower/raise &nbsp; ←/→ · curl/open<br>Q/Z · left track &nbsp; E/C · right track</p><div class="accessible-controls">${[
    ["boom", "Boom"],
    ["stick", "Stick"],
    ["bucket", "Bucket"],
    ["slew", "Slew"],
  ]
    .map(
      ([axis, label]) =>
        `<div><span>${label}</span><button class="hold" data-axis="${axis}" data-value="-1" aria-label="Decrease ${label}">−</button><button class="hold" data-axis="${axis}" data-value="1" aria-label="Increase ${label}">+</button></div>`,
    )
    .join("")}</div></details>`;
}

if (remote && !new URLSearchParams(location.search).get("room")) {
  app.innerHTML = `<div class="join-page">${brand}<div class="join-art">${icon("phone")}<span>YOUR PHONE. THE CONTROLS.</span></div><h1>Let’s move<br>some earth.</h1><p>Enter the six-character room code shown on your simulator.</p><form id="join"><label for="room-code">ROOM CODE</label><input id="room-code" placeholder="A1B2C3" maxlength="6" minlength="6" pattern="[a-fA-F0-9]{6}" required autocomplete="off" autocapitalize="characters"><button class="button primary">Connect to excavator ${icon("arrow")}</button></form><a href="/">Open a new sandbox ↗</a></div>`;
  $("#join").onsubmit = (event) => {
    event.preventDefault();
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
  document.body.classList.toggle("remote", remote);
  app.innerHTML = remote
    ? `
    <header class="remote-header">${brand}${connection}</header>${connectionHelp}
    <main class="remote-main"><div class="remote-machine"><div><span class="eyebrow">ARM60 / TRACKED EXCAVATOR</span><div class="room-display">ROOM <strong id="room-label">———</strong></div></div><div class="live-indicator"><i></i> LIVE</div></div>
    <section class="remote-telemetry"><div><span>BOOM</span><strong id="boom-value">10.0<small>mm</small></strong></div><div><span>BUCKET LOAD</span><strong id="load-value">0<small>grains</small></strong></div><div><span>LATENCY</span><strong id="latency-value">—<small>ms</small></strong></div></section>
    <section class="operator-panel">${controls()}</section><div class="remote-bottom"><span id="remote-status">Connected to your live sandbox</span><button id="reset" class="text-button">Reset sand ${icon("rotate")}</button></div><p class="remote-note">Keep this page open while operating. Switching apps releases the controls.</p></main><div id="toast" role="status" hidden></div>`
    : `
    <header class="site-header">${brand}<nav><span class="nav-selected">Sandbox</span><a id="remote-link" href="/remote" target="_blank" rel="noopener">Remote control ↗</a></nav><div class="header-actions">${connection}<button class="button primary" data-pair>${icon("phone")} Pair your phone</button></div></header>${connectionHelp}
    <main class="workspace"><section class="page-heading"><div><span class="eyebrow">THE DIGITAL DIG SITE <span class="eyebrow-dash">/</span> 001</span><h1>Small machine. <span>Real motion.</span></h1></div><div class="session-info"><span>SESSION</span><strong id="room-label">———</strong><button class="icon-button" data-pair aria-label="Show pairing code">${icon("link")}</button></div></section>
    <div class="workbench"><section class="simulation" aria-label="Excavator sandbox"><div id="stage"><div class="scene-top"><span class="scene-tag"><i></i> LIVE SIMULATION</span><span class="scene-scale">1:15 SCALE <span>·</span> ARM60 / R4</span></div><div id="loading"><span class="loader"></span>Preparing your dig site…</div><div class="view-buttons" role="group" aria-label="Camera views"><button data-view="orbit" class="active">Orbit</button><button data-view="side">Side</button><button data-view="top">Top</button><button data-view="bucket">Bucket</button></div><div class="scene-bottom"><span>DRAG TO ORBIT <b>·</b> SCROLL TO ZOOM</span><button id="fullscreen" class="icon-button" aria-label="Toggle full screen">${icon("expand")}</button></div><div class="stop-banner" hidden>EMERGENCY STOP ENGAGED</div></div>
    <div class="telemetry"><div><span>BUCKET LOAD</span><strong id="load-value">0<small>grains</small></strong><div class="meter"><i id="load-meter"></i></div></div><div><span>BOOM STROKE</span><strong id="boom-value">10.0<small>mm</small></strong><div class="meter"><i id="boom-meter"></i></div></div><div><span>SLEW ANGLE</span><strong id="slew-value">0<small>°</small></strong><div class="meter"><i id="slew-meter"></i></div></div><div><span>POUR ZONE</span><strong id="deposited-value">0<small>grains</small></strong><span class="metric-note">Material deposited</span></div></div>
    <div class="below-scene"><div><span class="number-chip">01</span><div><strong>Dig. Lift. Swing. Repeat.</strong><p>Lower into the sand, crowd the stick, then curl the bucket. Lift and swing toward the marked pour zone.</p></div></div><button id="reset" class="button">${icon("rotate")} Reset sandbox</button></div></section>
    <aside class="sidebar"><section class="operator-panel">${controls()}</section><button class="phone-card" data-pair><span class="phone-card-icon">${icon("phone")}</span><span><strong>A pocket-sized cockpit.</strong><small>Scan, connect, and dig from your phone.</small></span>${icon("arrow")}</button></aside></div>
    <footer><span><i class="footer-dot"></i><span id="particle-count">1,876</span> sand particles <b>·</b> Live granular fluid</span><span><span id="performance">30 Hz physics</span><b>·</b><span id="latency-value">— ms</span> <b>·</b> WebSocket</span></footer></main>
    <dialog id="pair-dialog"><button class="dialog-close icon-button" aria-label="Close pairing dialog">×</button><span class="eyebrow">TAKE THE CONTROLS WITH YOU</span><h2>Your phone.<br>Your excavator.</h2><p>Connect both devices to the same network, then scan to open the remote.</p><div class="qr-wrap"><canvas id="qr"></canvas></div><div class="pair-room">ROOM <strong id="pair-code"></strong></div><label for="pair-base">Server address reachable from your phone</label><input id="pair-base" type="url"><p class="pair-hint">Use your computer’s LAN address or public HTTPS domain. localhost only works on this device.</p><div class="pair-actions"><button class="button primary" id="copy-link">Copy remote link</button><a class="button" id="open-remote" target="_blank" rel="noopener">Open remote ↗</a></div><p id="pair-feedback" role="status"></p></dialog><div id="toast" role="status" hidden></div>`;

  let room = new URLSearchParams(location.search).get("room")?.toUpperCase();
  if (room && !/^[A-F0-9]{6}$/.test(room))
    throw new Error(
      "Invalid room code. Open /remote and enter the six-character code.",
    );
  let refreshPairing = () => {};
  function setRoom(code) {
    room = code;
    const url = new URL(location.href);
    url.searchParams.set("room", room);
    history.replaceState(null, "", url);
    $("#room-label").textContent = room;
    if ($("#remote-link")) $("#remote-link").href = `/remote?room=${room}`;
    refreshPairing();
  }
  if (room) setRoom(room);
  let ws,
    id,
    state,
    scene,
    positions,
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
            : "Another operator has control. Ask them to release it.",
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
    document.querySelectorAll(".knob").forEach((el) => {
      el.style.transform = "translate(-50%, -50%)";
    });
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
    w: ["stick", -1],
    s: ["stick", 1],
    a: ["slew", -1],
    d: ["slew", 1],
    ArrowUp: ["boom", -1],
    ArrowDown: ["boom", 1],
    ArrowLeft: ["bucket", 1],
    ArrowRight: ["bucket", -1],
    q: ["leftTrack", 1],
    z: ["leftTrack", -1],
    e: ["rightTrack", 1],
    c: ["rightTrack", -1],
  };
  function gatherAxes() {
    const previous = axes;
    axes = neutral();
    for (const source of pointerSources.values())
      for (const [axis, value] of Object.entries(source)) axes[axis] += value;
    for (const key of keyState) {
      const [axis, value] = keys[key];
      axes[axis] += value;
    }
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
    let pointer = null;
    pad.addEventListener("controlsreset", () => {
      if (pointer !== null && pad.hasPointerCapture(pointer))
        pad.releasePointerCapture(pointer);
      pointer = null;
    });
    function move(event) {
      if (pointer !== event.pointerId || !controlsAvailable()) return;
      const rect = pad.getBoundingClientRect(),
        radius = rect.width * 0.32;
      let x = (event.clientX - rect.left - rect.width / 2) / radius,
        y = (event.clientY - rect.top - rect.height / 2) / radius;
      const length = Math.hypot(x, y);
      if (length > 1) {
        x /= length;
        y /= length;
      }
      knob.style.transform = `translate(calc(-50% + ${x * radius}px), calc(-50% + ${y * radius}px))`;
      pointerSources.set(name, {
        [horizontal]:
          (Math.abs(x) < 0.12 ? 0 : x) * (name === "right" ? -1 : 1),
        [vertical]: Math.abs(y) < 0.12 ? 0 : y,
      });
      gatherAxes();
    }
    pad.addEventListener("pointerdown", (event) => {
      if (pointer !== null) return;
      if (!beginInput()) return;
      pointer = event.pointerId;
      pad.setPointerCapture(pointer);
      move(event);
      event.preventDefault();
    });
    pad.addEventListener("pointermove", move);
    const end = (event) => {
      if (event.pointerId !== pointer) return;
      pointer = null;
      pointerSources.delete(name);
      knob.style.transform = "translate(-50%, -50%)";
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
      $("#pair-dialog")?.open
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
  $("#speed").oninput = (event) => {
    speed = +event.target.value / 100;
    $("#speed-value").textContent = Math.round(speed * 100) + "%";
    inputSender.schedule();
  };
  $("#estop").onclick = () => {
    clearInputs();
    send({ type: "estop" });
  };
  $("#resume").onclick = () => {
    clearInputs();
    send({ type: "resume" });
  };
  $("#reset").onclick = () => {
    if (!isOwner()) return toast("Take control before resetting the sandbox.");
    clearInputs();
    send({ type: "reset" });
    toast("Sandbox reset. Ready for a fresh dig.");
  };

  let controlMode;
  function setReadout(selector, value) {
    const element = $(selector);
    if (element.innerHTML !== value) element.innerHTML = value;
  }
  function updateUI(next) {
    const ownedBefore = isOwner(),
      stoppedBefore = state?.estop;
    state = next;
    if (
      (ownedBefore && !isOwner()) ||
      (!stoppedBefore && state.estop) ||
      (claimPending && state.owner && !isOwner())
    )
      clearInputs();
    if (state.owner) claimPending = false;
    // Only send the current, still-held input after the server grants control.
    if (!ownedBefore && isOwner()) inputSender.flush();
    const owner = isOwner(),
      live = ws?.readyState === WebSocket.OPEN;
    const nextMode = `${owner}:${state.owner}:${state.estop}:${live}`;
    if (nextMode !== controlMode) {
      controlMode = nextMode;
      $("#claim").disabled = !live;
      $("#claim").textContent = owner ? "Release" : "Take control";
      $("#operator-status").textContent = owner
        ? "You have control"
        : state.owner
          ? "Another operator is driving"
          : "Move a control to start";
      $(".ownership").classList.toggle("owned", owner);
      document.querySelectorAll(".hold").forEach((el) => {
        el.disabled = !controlsAvailable();
      });
      $("#speed").disabled = !owner || state.estop || !live;
      document
        .querySelectorAll(".joystick")
        .forEach((el) => el.classList.toggle("disabled", !controlsAvailable()));
      $("#reset").disabled = !owner || !live;
      $("#resume").hidden = !state.estop;
      $("#resume").disabled = !owner;
      $("#estop").classList.toggle("engaged", state.estop);
      if ($(".stop-banner")) $(".stop-banner").hidden = !state.estop;
    }
    setReadout(
      "#boom-value",
      state.machine.strokes[0].toFixed(1) + "<small>mm</small>",
    );
    setReadout("#load-value", state.stats.carried + "<small>grains</small>");
    setReadout("#stick-value", state.machine.strokes[1].toFixed(1) + " mm");
    setReadout("#bucket-value", state.machine.strokes[2].toFixed(1) + " mm");
    if (!owner) {
      speed = state.speed;
      $("#speed").value = speed * 100;
      setReadout("#speed-value", Math.round(speed * 100) + "%");
    }
    if (!remote) {
      setReadout(
        "#slew-value",
        state.machine.slew.toFixed(0) + "<small>°</small>",
      );
      setReadout(
        "#deposited-value",
        state.stats.deposited + "<small>grains</small>",
      );
      setReadout("#particle-count", state.count.toLocaleString());
      $("#load-meter").style.width =
        Math.min(100, state.stats.carried * 2) + "%";
      $("#boom-meter").style.width =
        (state.machine.strokes[0] / 60) * 100 + "%";
      $("#slew-meter").style.width = (state.machine.slew + 150) / 3 + "%";
      if (scene) {
        scene.setState(state);
        const fps = scene.telemetry().fps;
        $("#performance").textContent =
          `${fps ? fps + " fps" : "View idle"} · ${state.stepMs} ms physics`;
      }
    }
  }
  function disableControls() {
    $("#claim").disabled = true;
    $("#estop").disabled = true;
    $("#resume").disabled = true;
    $("#reset").disabled = true;
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
        const response = await fetch(`/api/rooms/${room}`, {
          signal: AbortSignal.timeout(10000),
        });
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
        if (!missing && result.clients >= result.capacity)
          throw new Error(
            "This room is full. Close another tab or device, then retry.",
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
        setRoom(result.room);
        if (previousRoom) {
          state = null;
          positions = null;
          toast(
            "The previous room ended. A new sandbox is ready; pair your phone again.",
          );
        }
      }
      ws = new WebSocket(
        `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws?room=${room}&role=${remote ? "remote" : "simulator"}`,
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
      $("#estop").disabled = false;
    };
    ws.onmessage = (event) => {
      if (typeof event.data !== "string") {
        positions = new Float32Array(event.data);
        scene?.setSand(positions);
        return;
      }
      const message = JSON.parse(event.data);
      if (message.type === "welcome") {
        id = message.id;
        if (remote && !document.hidden) requestControl();
      }
      if (message.type === "state") updateUI(message);
      if (message.type === "error") {
        if (claimPending) {
          claimPending = false;
          clearInputs();
        }
        toast(message.message);
      }
      if (message.type === "pong") {
        const ms = Math.round(performance.now() - message.at);
        $("#latency-value").innerHTML = remote
          ? `${ms}<small>ms</small>`
          : `${ms} ms`;
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
  };

  if (!remote) {
    setupPairing(() => room, toast, clearInputs).then((update) => {
      refreshPairing = update;
      refreshPairing();
    });
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
      if (positions) scene.setSand(positions);
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

async function setupPairing(getRoom, toast, clearInputs) {
  const dialog = $("#pair-dialog");
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
  $("#pair-base").value = base;
  let link;
  async function update() {
    const room = getRoom();
    $("#pair-code").textContent = room || "———";
    if (!room) {
      link = null;
      $("#open-remote").removeAttribute("href");
      $("#copy-link").disabled = true;
      $("#pair-feedback").textContent =
        "Waiting for a sandbox. Check the server connection.";
      return;
    }
    try {
      const url = new URL($("#pair-base").value);
      if (!["http:", "https:"].includes(url.protocol)) throw new Error();
      link = url.origin + "/remote?room=" + room;
      $("#open-remote").href = link;
      await QRCode.toCanvas($("#qr"), link, {
        width: 208,
        margin: 1,
        color: { dark: "#26332b", light: "#ffffff" },
        errorCorrectionLevel: "M",
      });
      $("#pair-feedback").textContent = "";
      $("#copy-link").disabled = false;
    } catch {
      link = null;
      $("#open-remote").removeAttribute("href");
      $("#copy-link").disabled = true;
      $("#pair-feedback").textContent =
        "Enter a complete http:// or https:// server address.";
    }
  }
  $("#pair-base").oninput = update;
  await update();
  document.querySelectorAll("[data-pair]").forEach((button) => {
    button.onclick = () => {
      clearInputs();
      dialog.showModal();
    };
  });
  $(".dialog-close").onclick = () => dialog.close();
  dialog.addEventListener("click", (event) => {
    if (
      event.target === dialog &&
      (event.clientX < dialog.getBoundingClientRect().left ||
        event.clientX > dialog.getBoundingClientRect().right ||
        event.clientY < dialog.getBoundingClientRect().top ||
        event.clientY > dialog.getBoundingClientRect().bottom)
    )
      dialog.close();
  });
  $("#copy-link").onclick = async () => {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link);
      $("#pair-feedback").textContent = "Remote link copied.";
    } catch {
      $("#pair-feedback").textContent = link;
      toast("Copy the remote address shown below the buttons.");
    }
  };
  return update;
}

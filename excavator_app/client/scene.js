import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { CONFIG as V } from "../shared/config.js";
import { solve } from "../shared/kinematics.js";
import {
  WORLD,
  SAND,
  armFrame,
  clamp,
  initialMachine,
} from "../shared/world.js";
import { cameraWall, groundHeight, landscape } from "../shared/landscape.js";
import { FrameJitter } from "./frame-jitter.js";
import { createWorld } from "./world-view.js";
import { createSandView } from "./sand-view.js";
import { createLooseSandView } from "./loose-sand-view.js";
import { loadMachineModel } from "./machine-model.js";
import { AdaptiveResolution } from "./resolution.js";

const TICK_RATE = 30,
  // Render this many ticks behind the newest frame, so there is always a
  // later frame to interpolate toward despite network jitter.
  DELAY_TICKS = 1.75,
  MAX_JITTER_DELAY = 6;

export async function createScene(stage, onProgress) {
  const scene = new THREE.Scene();
  const mobile = matchMedia("(pointer: coarse)").matches;
  const renderer = new THREE.WebGLRenderer({
    antialias: !mobile,
    alpha: false,
    powerPreference: "high-performance",
  });
  // Automated browsers keep to one resolution: tests and pictures depend on it.
  const resolution = new AdaptiveResolution(
    Math.min(devicePixelRatio, mobile ? 1 : 1.75),
  );
  renderer.setPixelRatio(resolution.ratio);
  renderer.shadowMap.enabled = !mobile;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.92;
  // Reset by hand, because three.js otherwise forgets the shadow pass in its count.
  renderer.info.autoReset = false;
  renderer.domElement.setAttribute(
    "aria-label",
    "Live 3D excavator in an open world",
  );
  stage.prepend(renderer.domElement);
  let dirty = true;
  const camera = new THREE.PerspectiveCamera(42, 1, 15, 320000);
  camera.up.set(0, 0, 1);
  const orbit = new OrbitControls(camera, renderer.domElement);
  orbit.enableDamping = true;
  orbit.addEventListener("change", () => {
    dirty = true;
  });
  orbit.minDistance = 220;
  orbit.maxDistance = 16000;
  orbit.maxPolarAngle = Math.PI * 0.495;
  orbit.enablePan = false;

  const sunDirection = new THREE.Vector3(-0.42, -0.5, 0.76).normalize();
  scene.add(new THREE.HemisphereLight(0xcfe3ff, 0x8d8466, 1.45));
  const sun = new THREE.DirectionalLight(0xfff0d6, 3.2);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.normalBias = 1.4;
  Object.assign(sun.shadow.camera, {
    left: -2100,
    right: 2100,
    top: 2100,
    bottom: -2100,
    near: 200,
    far: 9000,
  });
  scene.add(sun, sun.target);
  const fill = new THREE.DirectionalLight(0xdbe6ff, 0.55);
  fill.position.set(800, 900, 700);
  scene.add(fill);

  onProgress("Building the valley…");
  const world = createWorld(scene, renderer, sunDirection, mobile),
    sand = createSandView(scene, renderer);

  const grains = createLooseSandView(
    scene,
    sand.texture,
    mobile,
    sand.surfaceHeight,
    sand.lumps,
  );

  // ------------------------------------------------------------- the machines
  onProgress("Loading original CAD assembly…");
  const model = await loadMachineModel();
  // Compile now what a first dig or another player would otherwise stall the
  // game for; three.js otherwise waits for a shader's first use.
  const sample = model.createSimplified(null, !mobile);
  scene.add(sample.root);
  renderer.compile(scene, camera);
  scene.remove(sample.root);
  sample.dispose();
  let state,
    lastAt = performance.now(),
    latestAt = 0,
    frames = 0,
    fpsAt = performance.now(),
    fps = 60;
  // Every excavator in the room, by id. The one the camera follows is drawn in
  // full and the others simplified, so more players add little to the picture.
  const views = new Map(),
    poses = new Map(),
    labelLayer = document.createElement("div");
  labelLayer.className = "machine-labels";
  stage.append(labelLayer);
  let selfId = null,
    followId = null,
    paints = new Map(),
    names = new Map();
  function viewOf(id) {
    let view = views.get(id);
    if (!view) {
      view = {
        id,
        pose: initialMachine(),
        drawn: null,
        assembly: null,
        paint: paints.get(id) ?? null,
        label: null,
      };
      views.set(id, view);
      poses.set(id, view.pose);
      followId ??= selfId ?? id;
      dressView(view);
    }
    return view;
  }
  function dressView(view) {
    const detailed = view.id === followId;
    if (
      view.assembly &&
      view.assembly.detailed === detailed &&
      view.assemblyPaint === view.paint
    )
      return;
    if (view.assembly) {
      scene.remove(view.assembly.root);
      view.assembly.dispose();
    }
    view.assembly = detailed
      ? model.createDetailed(view.paint)
      : model.createSimplified(view.paint, !mobile);
    view.assemblyPaint = view.paint;
    scene.add(view.assembly.root);
    view.assembly.update(view.pose);
    view.drawn = structuredClone(view.pose);
    dirty = true;
  }
  function dropView(id) {
    const view = views.get(id);
    if (!view) return;
    scene.remove(view.assembly.root);
    view.assembly.dispose();
    view.label?.remove();
    views.delete(id);
    poses.delete(id);
    if (followId === id) follow(selfId);
    dirty = true;
  }
  // Whose excavator the camera is on; null goes back to your own.
  function follow(id) {
    const next = id ?? selfId;
    if (next === followId) return;
    followId = next;
    for (const view of views.values()) dressView(view);
    if (followId !== null) {
      viewOf(followId);
      view(mode);
    }
  }
  const followed = () => views.get(followId)?.pose ?? fallbackPose;
  const fallbackPose = initialMachine();
  function drawView(view) {
    if (view.drawn && samePose(view.drawn, view.pose)) return false;
    view.assembly.update(view.pose);
    view.drawn = structuredClone(view.pose);
    return true;
  }
  // Names float over the other machines, and stay out of the pointer's way.
  const labelAt = new THREE.Vector3();
  function placeLabels() {
    for (const view of views.values()) {
      if (view.id === selfId) continue;
      const name = names.get(view.id);
      if (!name) continue;
      if (!view.label) {
        view.label = document.createElement("div");
        view.label.className = "machine-label";
        view.label.append(document.createElement("i"), document.createElement("span"));
        labelLayer.append(view.label);
      }
      const [swatch, text] = view.label.children;
      if (text.textContent !== name) text.textContent = name;
      swatch.style.background = view.paint ?? "#e89912";
      labelAt.set(view.pose.x, view.pose.y, view.pose.z + 400).project(camera);
      const shown =
        labelAt.z < 1 && Math.abs(labelAt.x) < 1 && Math.abs(labelAt.y) < 1;
      view.label.hidden = !shown;
      if (shown)
        view.label.style.transform = `translate(${(((labelAt.x + 1) / 2) * stage.clientWidth).toFixed(1)}px, ${(((1 - labelAt.y) / 2) * stage.clientHeight).toFixed(1)}px) translate(-50%, -100%)`;
    }
  }

  // ------------------------------------------- synchronised frame playback
  // Binary frames carry the machine pose and the sand of the same tick. They
  // are played back slightly delayed and interpolated, so the bucket and its
  // load always move together.
  const queue = [],
    jitter = new FrameJitter(TICK_RATE);
  let renderTick = null,
    content = 0,
    drawnKey = "";
  const samePose = (a, b) =>
    a.strokes.every((v, i) => v === b.strokes[i]) &&
    a.tracks.every((v, i) => v === b.tracks[i]) &&
    a.slew === b.slew &&
    a.x === b.x &&
    a.y === b.y &&
    a.z === b.z &&
    a.heading === b.heading &&
    a.pitch === b.pitch &&
    a.roll === b.roll;
  const sameArray = (a, b) =>
    a.length === b.length && a.every((value, i) => value === b[i]);
  const sameLoad = (a, b) => a === b || (a && b && sameArray(a, b));
  const sameMachines = (a, b) =>
    a.machines.length === b.machines.length &&
    a.machines.every(
      (machine, i) =>
        machine.id === b.machines[i].id &&
        samePose(machine, b.machines[i]) &&
        sameLoad(machine.load, b.machines[i].load),
    );
  function settle(frame) {
    if (frame.applied) return;
    frame.applied = true;
    // The first frames of a room, a reset or a connection restore the world;
    // nothing in them has just been dug.
    const fresh = frame.tick > 2 && frame.tiles.length < 400,
      // Catching up after a hidden tab or a stall, the moment for this has passed.
      live = renderTick !== null && renderTick - frame.tick < 8;
    if (live) grains.settle(frame, camera.position);
    if (
      frame.tiles.length &&
      sand.applyTiles(frame.tiles, fresh, fresh && live ? grains.moved : null)
    )
      dirty = true;
  }
  function pushFrame(frame) {
    jitter.arrived(frame.tick, performance.now());
    const last = queue[queue.length - 1];
    if (last && frame.tick <= last.tick) {
      // A reset or a new room restarts the tick count: show it at once.
      for (const f of queue) settle(f);
      queue.length = 0;
      renderTick = null;
    }
    const previous = queue[queue.length - 1];
    grains.pushFrame(frame, previous);
    if (
      !previous ||
      frame.tiles.length ||
      !sameMachines(previous, frame) ||
      !sameArray(previous.slots, frame.slots) ||
      !sameArray(previous.positions, frame.positions)
    )
      content++;
    frame.content = content;
    frame.byId = new Map(frame.machines.map((machine) => [machine.id, machine]));
    queue.push(frame);
    // Bound memory if the tab is hidden: older frames only matter for tiles.
    while (queue.length > 90) settle(queue.shift());
    latestAt = performance.now();
  }
  function play(dt) {
    if (!queue.length) return false;
    const newest = queue[queue.length - 1].tick,
      // On a jittery connection, wait until the next frame has usually arrived.
      target = newest - DELAY_TICKS - Math.min(MAX_JITTER_DELAY, 3 * jitter.ticks);
    if (renderTick === null || Math.abs(target - renderTick) > 15)
      renderTick = target;
    else
      renderTick +=
        dt *
        TICK_RATE *
        Math.min(1.6, Math.max(0.6, 1 + (target - renderTick) * 0.12));
    renderTick = Math.min(renderTick, newest);
    while (queue.length > 1 && queue[1].tick <= renderTick)
      settle(queue.shift());
    const a = queue[0],
      b = queue[1] || a;
    settle(a);
    const alpha =
      b === a
        ? 0
        : Math.min(1, Math.max(0, (renderTick - a.tick) / (b.tick - a.tick)));
    if (alpha >= 0.5) settle(b);
    const key =
      a.content === b.content
        ? `${a.content}`
        : `${a.content}:${b.content}:${alpha.toFixed(3)}`;
    if (key === drawnKey) return false;
    drawnKey = key;
    // Machines that left are gone from the newer frame; one that just arrived
    // has nothing to interpolate from.
    for (const id of views.keys()) if (!b.byId.has(id)) dropView(id);
    for (const to of b.machines) {
      const from = a.byId.get(to.id) ?? to,
        view = viewOf(to.id),
        pose = view.pose;
      for (let i = 0; i < 3; i++)
        pose.strokes[i] =
          from.strokes[i] + (to.strokes[i] - from.strokes[i]) * alpha;
      for (let i = 0; i < 2; i++)
        pose.tracks[i] =
          from.tracks[i] + (to.tracks[i] - from.tracks[i]) * alpha;
      for (const k of ["slew", "x", "y", "z", "heading", "pitch", "roll"])
        pose[k] = from[k] + (to[k] - from[k]) * alpha;
      drawView(view);
    }
    grains.update(a, b, alpha, poses);
    return true;
  }

  // ------------------------------------------------------- following camera
  // The orbit target follows the machine and the camera moves with it, so a
  // view chosen by dragging survives driving. Chase, Side and Bucket also turn
  // with the machine; Orbit and Top keep their compass direction.
  const focus = new THREE.Vector3(),
    move = new THREE.Vector3(),
    offset = new THREE.Vector3();
  let mode = "chase",
    rigHeading = 0;
  const VIEWS = {
    // Camera offset from the focus, in the frame that follows the heading.
    chase: { offset: [-1560, 0, 330], ahead: 420, turns: true },
    orbit: { offset: [760, -1220, 860], ahead: 120, turns: false },
    side: { offset: [90, -1500, 300], ahead: 180, turns: true },
    top: { offset: [0, -40, 3400], ahead: 0, turns: false },
    bucket: { offset: [120, -640, 300], ahead: 0, turns: true },
  };
  function focusPoint(out) {
    const pose = followed();
    if (mode === "bucket") {
      const s = solve(pose.strokes),
        frame = armFrame(
          pose,
          s.origins.bucket[0] + V.arm_offset[0],
          s.origins.bucket[1] + V.arm_offset[2],
          s.angles.bucket,
        );
      return out.set(frame.x, frame.y, frame.z);
    }
    // Aim a little ahead of the machine, to show where it is going.
    const ahead = VIEWS[mode].ahead;
    return out.set(
      pose.x + Math.cos(pose.heading) * ahead,
      pose.y + Math.sin(pose.heading) * ahead,
      pose.z + 170,
    );
  }
  const followHeading = () => {
    const pose = followed();
    return pose.heading + (mode === "bucket" ? (pose.slew * Math.PI) / 180 : 0);
  };
  function view(name) {
    mode = name;
    const v = VIEWS[name];
    focusPoint(focus);
    rigHeading = v.turns ? followHeading() : 0;
    offset.set(...v.offset);
    const c = Math.cos(rigHeading),
      s = Math.sin(rigHeading);
    camera.position.set(
      focus.x + offset.x * c - offset.y * s,
      focus.y + offset.x * s + offset.y * c,
      focus.z + offset.z,
    );
    orbit.target.copy(focus);
    keepAboveGround();
    orbit.update();
    dirty = true;
  }
  function keepAboveGround() {
    const floor = groundHeight(camera.position.x, camera.position.y) + 45;
    if (camera.position.z < floor) camera.position.z = floor;
  }
  // A building behind the machine shortens the camera boom rather than letting
  // the view start inside its walls. Only the drawn position changes: the orbit
  // keeps the distance the player chose, and the boom eases back to it.
  const WALL_MARGIN = 70,
    WALL_HEIGHT = 900,
    walls = landscape()
      .colliders.filter(cameraWall)
      .map((k) => ({
        x: k.x,
        y: k.y,
        c: k.c ?? 1,
        s: k.s ?? 0,
        hx: (k.hx ?? k.r) + WALL_MARGIN,
        hy: (k.hy ?? k.r) + WALL_MARGIN,
        reach: k.r + WALL_MARGIN,
      })),
    drawnFrom = new THREE.Vector3();
  let boomLength = 1;
  // Fraction of the way from the focus to the camera that is clear of walls.
  function clearBoom() {
    const from = orbit.target,
      to = camera.position;
    if (to.z - groundHeight(to.x, to.y) > WALL_HEIGHT) return 1;
    const dx = to.x - from.x,
      dy = to.y - from.y,
      middleX = (from.x + to.x) / 2,
      middleY = (from.y + to.y) / 2,
      half = Math.hypot(dx, dy) / 2;
    let clear = 1;
    for (const w of walls) {
      if (Math.hypot(w.x - middleX, w.y - middleY) > half + w.reach) continue;
      const ox = from.x - w.x,
        oy = from.y - w.y,
        origin = [ox * w.c + oy * w.s, -ox * w.s + oy * w.c],
        along = [dx * w.c + dy * w.s, -dx * w.s + dy * w.c],
        size = [w.hx, w.hy];
      let enter = -Infinity,
        leave = Infinity;
      for (let d = 0; d < 2; d++) {
        if (Math.abs(along[d]) < 1e-6) {
          if (Math.abs(origin[d]) > size[d]) enter = Infinity;
          continue;
        }
        const a = (-size[d] - origin[d]) / along[d],
          b = (size[d] - origin[d]) / along[d];
        enter = Math.max(enter, Math.min(a, b));
        leave = Math.min(leave, Math.max(a, b));
      }
      // Starting inside means the focus point itself is at the wall, and the
      // camera behind it is not: only a wall ahead along the boom counts.
      if (enter >= 0 && enter <= leave && enter < clear) clear = enter;
    }
    return Math.max(clear, 0.1);
  }
  function updateBoom(dt) {
    const clear = clearBoom(),
      next =
        clear < boomLength
          ? clear
          : boomLength + (clear - boomLength) * (1 - Math.exp(-dt / 0.35));
    if (Math.abs(next - boomLength) > 1e-4) dirty = true;
    boomLength = next > 0.9995 ? 1 : next;
  }
  function followMachine(dt) {
    focusPoint(focus);
    move.copy(focus).sub(orbit.target);
    const far = move.length() > 1800,
      k = far ? 1 : 1 - Math.exp(-dt / 0.09);
    move.multiplyScalar(k);
    let moved = move.lengthSq() > 1e-4;
    camera.position.add(move);
    orbit.target.add(move);
    if (VIEWS[mode].turns) {
      let delta = followHeading() - rigHeading;
      delta = Math.atan2(Math.sin(delta), Math.cos(delta));
      const step = far ? delta : delta * (1 - Math.exp(-dt / 0.28));
      if (Math.abs(step) > 1e-5) {
        offset.copy(camera.position).sub(orbit.target);
        const c = Math.cos(step),
          s = Math.sin(step),
          x = offset.x * c - offset.y * s,
          y = offset.x * s + offset.y * c;
        camera.position.set(
          orbit.target.x + x,
          orbit.target.y + y,
          camera.position.z,
        );
        rigHeading += step;
        moved = true;
      }
    }
    if (moved) {
      keepAboveGround();
      dirty = true;
    }
  }
  // The shadow frustum travels with the machine, on a grid so it does not shimmer.
  let sunX = NaN,
    sunY = NaN;
  function followSun() {
    const pose = followed(),
      x = Math.round(pose.x / 60) * 60,
      y = Math.round(pose.y / 60) * 60;
    if (x === sunX && y === sunY) return;
    sunX = x;
    sunY = y;
    sun.target.position.set(x, y, pose.z);
    sun.position.set(x, y, pose.z).addScaledVector(sunDirection, 4600);
  }

  // How finely to draw the followed machine, from how large it is on the screen.
  function updateMachineDetail() {
    const assembly = views.get(followId)?.assembly;
    if (!assembly?.detailed) return false;
    const distance = camera.position.distanceTo(orbit.target) * boomLength,
      visible = 2 * distance * Math.tan((camera.fov * Math.PI) / 360);
    return assembly.setScale(renderer.domElement.height / visible);
  }

  // ---------------------------------------------------------------- minimap
  let minimap, mapContext, mapKey;
  function drawMinimap() {
    if (!minimap) return;
    const moved = [...views.values()],
      key = moved
        .map(
          ({ id, pose, paint }) =>
            `${id}${paint}:${Math.round(pose.x / 40)}:${Math.round(pose.y / 40)}:${Math.round(pose.heading * 12)}`,
        )
        .join() + followId;
    if (key === mapKey) return;
    mapKey = key;
    const size = minimap.width,
      span = WORLD.maxX - WORLD.minX,
      c = mapContext,
      u = size / 180;
    c.drawImage(world.map, 0, 0, size, size);
    // Draw the followed machine last, so it is always on top.
    moved.sort((a, b) => (a.id === followId) - (b.id === followId));
    for (const { id, pose, paint } of moved) {
      const big = id === followId ? 1 : 0.8;
      c.save();
      c.translate(
        ((pose.x - WORLD.minX) / span) * size,
        ((WORLD.maxY - pose.y) / span) * size,
      );
      c.rotate(-pose.heading);
      c.scale(big, big);
      c.fillStyle = paint ?? "#ffd24a";
      c.strokeStyle = id === followId ? "#ffffff" : "#1c241f";
      c.lineWidth = 1.5 * u;
      c.beginPath();
      c.moveTo(8 * u, 0);
      c.lineTo(-5.5 * u, -5 * u);
      c.lineTo(-3 * u, 0);
      c.lineTo(-5.5 * u, 5 * u);
      c.closePath();
      c.fill();
      c.stroke();
      c.restore();
    }
  }

  view("chase");
  followSun();
  new ResizeObserver(() => {
    renderer.setSize(stage.clientWidth, stage.clientHeight);
    camera.aspect = stage.clientWidth / stage.clientHeight;
    // A portrait screen needs a taller view to keep the machine's width in it.
    camera.fov = 42 + 24 * clamp((1 - camera.aspect) / 0.55, 0, 1);
    camera.updateProjectionMatrix();
    dirty = true;
  }).observe(stage);
  renderer.domElement.addEventListener("webglcontextlost", (event) => {
    event.preventDefault();
    onProgress("Graphics context lost. Reload to restore the scene.");
  });
  let stateKey = "",
    detailAt = 0,
    drawnAt = null;
  function animate(now) {
    const dt = Math.min(0.1, (now - lastAt) / 1000);
    lastAt = now;
    sand.setTime(now / 1000);
    if (document.hidden) {
      requestAnimationFrame(animate);
      return;
    }
    if (queue.length) {
      if (play(dt)) dirty = true;
    } else if (state && followId !== null) {
      // Before the first binary frame, show the pose from telemetry.
      const key = JSON.stringify(state.machine);
      if (key !== stateKey) {
        const view = viewOf(selfId ?? followId);
        Object.assign(view.pose, state.machine);
        drawView(view);
        stateKey = key;
        dirty = true;
      }
    }
    if (grains.stepGrains(dt)) dirty = true;
    followMachine(dt);
    followSun();
    orbit.update();
    updateBoom(dt);
    if (now - detailAt > 250) {
      detailAt = now;
      if (sand.updateDetail(camera)) dirty = true;
      if (updateMachineDetail()) dirty = true;
      drawMinimap();
    }
    if (dirty && !document.hidden) {
      // Only frames drawn straight after another say how fast this machine is.
      if (
        drawnAt !== null &&
        !navigator.webdriver &&
        resolution.frame(now - drawnAt)
      )
        renderer.setPixelRatio(resolution.ratio);
      drawnAt = now;
      world.placeSky(camera);
      drawnFrom.copy(camera.position);
      if (boomLength < 1)
        camera.position.lerpVectors(orbit.target, drawnFrom, boomLength);
      renderer.info.reset();
      renderer.render(scene, camera);
      placeLabels();
      camera.position.copy(drawnFrom);
      dirty = false;
      frames++;
    } else drawnAt = null;
    if (now - fpsAt > 1000) {
      fps = Math.round((frames * 1000) / (now - fpsAt));
      fpsAt = now;
      frames = 0;
    }
    requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);
  onProgress(null);
  return {
    view,
    pushFrame,
    setTerrain(store) {
      const tiles = [...store].map(([index, heights]) => ({ index, heights }));
      if (sand.applyTiles(tiles, false)) dirty = true;
    },
    newRoom() {
      queue.length = 0;
      renderTick = null;
      grains.clear();
      drawnKey = "";
      dirty = true;
      selfId = followId = null;
      for (const id of [...views.keys()]) dropView(id);
      if (sand.clear()) dirty = true;
    },
    // Your own excavator: where the camera goes, and the one without a name tag.
    setSelf(id) {
      const wasFollowingSelf = followId === null || followId === selfId;
      selfId = id;
      viewOf(id);
      if (wasFollowingSelf) follow(id);
    },
    follow,
    get following() {
      return followId;
    },
    setRoster(players) {
      paints = new Map(players.map(({ id, paint }) => [id, paint]));
      names = new Map(players.map(({ id, name }) => [id, name]));
      for (const v of views.values()) {
        v.paint = paints.get(v.id) ?? v.paint;
        dressView(v);
      }
      mapKey = "";
      dirty = true;
    },
    setState(value) {
      state = value;
      if (!queue.length) latestAt = performance.now();
    },
    attachMinimap(canvas) {
      minimap = canvas;
      mapContext = canvas.getContext("2d");
      mapKey = "";
      drawMinimap();
    },
    telemetry() {
      return {
        fps,
        age: performance.now() - latestAt,
        meshes: model.meshes,
        machines: views.size,
        detailed: [...views.values()].filter((v) => v.assembly.detailed).length,
        machineLevel: views.get(followId)?.assembly.level ?? null,
        following: followId,
        triangles: renderer.info.render.triangles,
        calls: renderer.info.render.calls,
        sandCount: sand.ready ? sand.chunkCount * SAND.page * SAND.page : 0,
        chunks: sand.chunkCount,
        grains: grains.count,
        loadTriangles: grains.triangles,
        flyingGrains: grains.flying,
        looseGrains: grains.looseGrains,
        sandUpdateMs: grains.updateMs,
        tick: renderTick,
        jitterTicks: jitter.ticks,
        pixelRatio: renderer.getPixelRatio(),
        shadows: renderer.shadowMap.enabled,
        camera: camera.position.toArray(),
      };
    },
  };
}

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { CONFIG as V } from "../shared/config.js";
import { bucketBody } from "../shared/kinematics.js";
import {
  WORLD,
  SAND,
  armFrame,
  freshPose,
  clamp,
  initialMachine,
} from "../shared/world.js";
import { cameraWall, groundHeight, landscape } from "../shared/landscape.js";
import { FrameJitter } from "./frame-jitter.js";
import { createWorld } from "./world-view.js";
import { createSandView } from "./sand-view.js";
import { createLooseSandView } from "./loose-sand-view.js";
import { loadMachineModel } from "./machine-model.js";
import { createTruckModel } from "./truck-model.js";
import { TRUCK, TRUCK_LOAD, bodyInTruck, initialTruck } from "../shared/truck.js";
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
  onProgress("Loading the excavator…");
  const model = await loadMachineModel((done) =>
    onProgress(`Preparing the excavator… ${Math.round(done * 100)} %`),
  );
  // Compile now what a first dig or another player would otherwise stall the
  // game for; three.js otherwise waits for a shader's first use.
  const sample = model.createSimplified(null, !mobile),
    truckModel = createTruckModel(),
    sampleTruck = truckModel.create(null, !mobile);
  sampleTruck.update(initialTruck());
  scene.add(sample.root, sampleTruck.root);
  renderer.compile(scene, camera);
  scene.remove(sample.root, sampleTruck.root);
  sample.dispose();
  sampleTruck.dispose();
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
    names = new Map(),
    // Which machine each player is in: "excavator" or "truck".
    driving = new Map();
  // Every player's dump truck, by the player's id, drawn the same near and far
  // but for the wheels' detail.
  const truckViews = new Map(),
    truckPoses = new Map();
  function truckViewOf(id) {
    let view = truckViews.get(id);
    if (!view) {
      const paint = paints.get(id) ?? null;
      view = {
        id,
        pose: initialTruck(),
        drawn: null,
        paint,
        model: truckModel.create(paint, !mobile),
      };
      truckViews.set(id, view);
      truckPoses.set(id, view.pose);
      scene.add(view.model.root);
      view.model.update(view.pose);
      dirty = true;
    }
    return view;
  }
  function dropTruckView(id) {
    const view = truckViews.get(id);
    if (!view) return;
    scene.remove(view.model.root);
    view.model.dispose();
    truckViews.delete(id);
    truckPoses.delete(id);
    dirty = true;
  }
  const TRUCK_POSE = ["x", "y", "z", "heading", "pitch", "roll", "steer", "tip", "wheels"];
  const sameTruckPose = (a, b) => TRUCK_POSE.every((key) => a[key] === b[key]);
  function drawTruckView(view) {
    if (view.drawn && sameTruckPose(view.drawn, view.pose)) return false;
    view.model.update(view.pose);
    view.drawn = { ...view.pose };
    return true;
  }
  // The machine a player is in: its pose, and whether it is their truck.
  const inTruck = (id) => driving.get(id) === "truck" && truckViews.has(id);
  const machineOf = (id) =>
    inTruck(id) ? truckViews.get(id).pose : views.get(id)?.pose;
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
  // A player got into their other machine. A camera following them goes along
  // and keeps its view, but for the views a truck is seen from another side in.
  function setDriving(id, machine) {
    const next = machine === "truck" ? "truck" : "excavator";
    if ((driving.get(id) ?? "excavator") === next) {
      driving.set(id, next);
      return;
    }
    driving.set(id, next);
    mapKey = "";
    dirty = true;
    if (id === followId && TRUCK_VIEWS[mode]) view(mode);
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
  const followed = () => machineOf(followId) ?? fallbackPose;
  const fallbackPose = initialMachine();
  function drawView(view) {
    if (view.drawn && samePose(view.drawn, view.pose)) return false;
    view.assembly.update(view.pose);
    view.drawn = structuredClone(view.pose);
    return true;
  }
  // Names float over the machines the others are in, and stay out of the
  // pointer's way.
  const labelAt = new THREE.Vector3();
  function placeLabels() {
    for (const view of views.values()) {
      if (view.id === selfId) continue;
      const name = names.get(view.id);
      if (!name) continue;
      const pose = machineOf(view.id),
        above = inTruck(view.id) ? TRUCK.cabHeight + 160 : 400;
      if (!view.label) {
        view.label = document.createElement("div");
        view.label.className = "machine-label";
        view.label.append(document.createElement("i"), document.createElement("span"));
        labelLayer.append(view.label);
      }
      const [swatch, text] = view.label.children;
      if (text.textContent !== name) text.textContent = name;
      swatch.style.background = view.paint ?? "#e89912";
      labelAt.set(pose.x, pose.y, pose.z + above).project(camera);
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
  const sameTrucks = (a, b) =>
    a.trucks.length === b.trucks.length &&
    a.trucks.every(
      (truck, i) =>
        truck.id === b.trucks[i].id &&
        sameTruckPose(truck, b.trucks[i]) &&
        sameLoad(truck.load, b.trucks[i].load),
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
      !sameTrucks(previous, frame) ||
      !sameArray(previous.slots, frame.slots) ||
      !sameArray(previous.positions, frame.positions)
    )
      content++;
    frame.content = content;
    frame.byId = new Map(frame.machines.map((machine) => [machine.id, machine]));
    frame.trucksById = new Map(frame.trucks.map((truck) => [truck.id, truck]));
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
    for (const id of truckViews.keys()) if (!b.trucksById.has(id)) dropTruckView(id);
    for (const to of b.trucks) {
      const from = a.trucksById.get(to.id) ?? to,
        view = truckViewOf(to.id);
      for (const k of TRUCK_POSE)
        view.pose[k] = from[k] + (to[k] - from[k]) * alpha;
      drawTruckView(view);
    }
    grains.update(a, b, alpha, poses, truckPoses);
    return true;
  }

  // ------------------------------------------------------- following camera
  // The orbit target follows the machine and the camera moves with it, so a
  // view chosen by dragging survives driving. Chase, Side and Bucket also turn
  // with the machine; Orbit and Top keep their compass direction.
  const focus = new THREE.Vector3(),
    move = new THREE.Vector3(),
    offset = new THREE.Vector3(),
    bucketAt = new Float64Array(3),
    bucketFrame = freshPose();
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
  // A truck is seen from its left, the driver's side: the first player's has the
  // excavator on its right. Its Bucket view looks into the body from behind.
  const TRUCK_VIEWS = {
      side: { offset: [90, 1500, 300], ahead: 180, turns: true },
      bucket: { offset: [-700, 620, 520], ahead: 0, turns: true },
    },
    bodyAt = new Float64Array(4);
  const viewOfMode = () =>
    (inTruck(followId) && TRUCK_VIEWS[mode]) || VIEWS[mode];
  function focusPoint(out) {
    const pose = followed();
    if (mode === "bucket" && inTruck(followId)) {
      // The middle of the floor, wherever the body is tipped.
      const [x, z, c, s] = bodyInTruck(pose.tip, bodyAt),
        along = x + c * (TRUCK_LOAD.length / 2),
        up = z + s * (TRUCK_LOAD.length / 2);
      return out.set(
        pose.x + Math.cos(pose.heading) * along,
        pose.y + Math.sin(pose.heading) * along,
        pose.z + up,
      );
    }
    if (mode === "bucket") {
      bucketBody(pose.strokes, bucketAt);
      const frame = armFrame(
        pose,
        bucketAt[0] + V.arm_offset[0],
        bucketAt[1] + V.arm_offset[2],
        bucketAt[2],
        bucketFrame,
      );
      return out.set(frame.x, frame.y, frame.z);
    }
    // Aim a little ahead of the machine, to show where it is going.
    const ahead = viewOfMode().ahead;
    return out.set(
      pose.x + Math.cos(pose.heading) * ahead,
      pose.y + Math.sin(pose.heading) * ahead,
      pose.z + 170,
    );
  }
  const followHeading = () => {
    const pose = followed();
    return (
      pose.heading +
      (mode === "bucket" && !inTruck(followId) ? (pose.slew * Math.PI) / 180 : 0)
    );
  };
  function view(name) {
    mode = name;
    const v = viewOfMode();
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
    if (viewOfMode().turns) {
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
  // Excavators are arrows and trucks are blocks with a cab at the front.
  function drawMinimap() {
    if (!minimap) return;
    const marks = [
        ...[...views.values()].map((view) => ({ ...view, truck: false })),
        ...[...truckViews.values()].map((view) => ({ ...view, truck: true })),
      ],
      key =
        marks
          .map(
            ({ id, pose, paint, truck }) =>
              `${truck ? "t" : ""}${id}${paint}:${Math.round(pose.x / 40)}:${Math.round(pose.y / 40)}:${Math.round(pose.heading * 12)}`,
          )
          .join() +
        followId +
        driving.get(followId);
    if (key === mapKey) return;
    mapKey = key;
    const size = minimap.width,
      span = WORLD.maxX - WORLD.minX,
      c = mapContext,
      u = size / 180,
      isFollowed = ({ id, truck }) => id === followId && truck === inTruck(id);
    c.drawImage(world.map, 0, 0, size, size);
    // Draw the followed machine last, so it is always on top.
    marks.sort((a, b) => isFollowed(a) - isFollowed(b));
    for (const mark of marks) {
      const { pose, paint, truck } = mark,
        big = isFollowed(mark) ? 1 : 0.8;
      c.save();
      c.translate(
        ((pose.x - WORLD.minX) / span) * size,
        ((WORLD.maxY - pose.y) / span) * size,
      );
      c.rotate(-pose.heading);
      c.scale(big, big);
      c.fillStyle = paint ?? "#ffd24a";
      c.strokeStyle = isFollowed(mark) ? "#ffffff" : "#1c241f";
      c.lineWidth = 1.5 * u;
      c.beginPath();
      if (truck) {
        c.rect(-4.5 * u, -3 * u, 7 * u, 6 * u);
        c.rect(3.5 * u, -3 * u, 3 * u, 6 * u);
      } else {
        c.moveTo(8 * u, 0);
        c.lineTo(-5.5 * u, -5 * u);
        c.lineTo(-3 * u, 0);
        c.lineTo(-5.5 * u, 5 * u);
        c.closePath();
      }
      c.fill();
      c.stroke();
      c.restore();
    }
  }
  // Far trucks lose the wheels' lugs and nuts.
  const TRUCK_DETAIL_WITHIN = 2600,
    truckAt = new THREE.Vector3();
  function updateTruckDetail() {
    let changed = false;
    for (const view of truckViews.values()) {
      const far =
        camera.position.distanceTo(truckAt.set(view.pose.x, view.pose.y, view.pose.z)) >
        TRUCK_DETAIL_WITHIN;
      if (view.model.setFar(far, view.pose)) changed = true;
    }
    return changed;
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
      if (updateTruckDetail()) dirty = true;
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
      for (const id of [...truckViews.keys()]) dropTruckView(id);
      driving.clear();
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
      for (const { id, driving: machine } of players)
        if (id !== selfId || !state) setDriving(id, machine);
      for (const v of views.values()) {
        v.paint = paints.get(v.id) ?? v.paint;
        dressView(v);
      }
      for (const v of truckViews.values()) {
        v.paint = paints.get(v.id) ?? v.paint;
        v.model.setPaint(v.paint);
      }
      mapKey = "";
      dirty = true;
    },
    setState(value) {
      state = value;
      // Your own machine follows your state, which comes sooner than the roster.
      if (selfId !== null) setDriving(selfId, value.driving);
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
        trucks: truckViews.size,
        driving: driving.get(followId) ?? "excavator",
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

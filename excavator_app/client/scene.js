import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { CONFIG as V } from "../shared/config.js";
import { solve } from "../shared/kinematics.js";
import {
  WORLD,
  SAND,
  armFrame,
  clamp,
  initialMachine,
} from "../shared/world.js";
import { groundHeight, landscape } from "../shared/landscape.js";
import { createWorld } from "./world-view.js";
import { createSandView } from "./sand-view.js";
import { createLooseSandView } from "./loose-sand-view.js";

const TICK_RATE = 30,
  // Render this many ticks behind the newest frame, so there is always a
  // later frame to interpolate toward despite network jitter.
  DELAY_TICKS = 1.75;

export async function createScene(stage, onProgress) {
  const scene = new THREE.Scene();
  const mobile = matchMedia("(pointer: coarse)").matches;
  const renderer = new THREE.WebGLRenderer({
    antialias: !mobile,
    alpha: false,
    powerPreference: "high-performance",
  });
  renderer.setPixelRatio(Math.min(devicePixelRatio, mobile ? 1 : 1.75));
  renderer.shadowMap.enabled = !mobile;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.92;
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
  );

  // ----------------------------------------------------------- CAD assembly
  const root = new THREE.Group(),
    upper = new THREE.Group(),
    arm = new THREE.Group();
  // Same rotation as chassisAxes(): heading, then pitch, then roll.
  root.rotation.order = "ZYX";
  scene.add(root);
  root.add(upper);
  upper.add(arm);
  arm.position.set(...V.arm_offset);
  onProgress("Loading original CAD assembly…");
  const response = await fetch("/model.json");
  if (!response.ok) throw new Error("The excavator model could not be loaded.");
  const data = await response.json(),
    groups = {},
    batches = new Map(),
    links = { L: [], R: [] },
    wheels = [];
  const decode = (encoded, Type) => {
    const bytes = Uint8Array.from(atob(encoded), (c) => c.charCodeAt(0));
    return new Type(bytes.buffer);
  };
  const wheelCenters = {};
  for (const side of ["L", "R"]) {
    const y = ((side === "L" ? -1 : 1) * V.track_centres) / 2;
    const centres = [
      [-V.wheel_centres / 2, V.axle_z],
      [V.wheel_centres / 2 + V.idler_assembly_offset_mm, V.axle_z],
      ...V.road_roller_x_mm.map((x) => [x, 29]),
      ...V.return_roller_x_mm.map((x) => [x, V.return_roller_z_mm]),
    ];
    [
      "drive_" + side,
      "idler_" + side,
      ...V.road_roller_x_mm.map((_, i) => "roller_" + side + i),
      ...V.return_roller_x_mm.map((_, i) => "return_" + side + i),
    ].forEach((name, i) => {
      wheelCenters[name] = {
        centre: [centres[i][0], y, centres[i][1]],
        side,
        radius: i === 0 ? V.pitch_radius : i === 1 ? 30 : i < 5 ? 17.5 : 13.5,
      };
    });
  }
  for (const item of data.meshes) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
      "position",
      new THREE.BufferAttribute(decode(item.v, Float32Array), 3),
    );
    geometry.setIndex(
      new THREE.BufferAttribute(
        decode(item.t, item.wide ? Uint32Array : Uint16Array),
        1,
      ),
    );
    geometry.computeVertexNormals();
    let key = (item.arm ? "arm_" : "vehicle_") + item.group,
      parent = item.arm ? arm : item.group === "upper" ? upper : root;
    const link =
      /^(?:shoe_|track_pin_|track_bushing_|pin_clip_)([LR])(\d{2})/.exec(
        item.name,
      );
    if (link) {
      const [, side, index] = link,
        pose = data.track.initial_poses[+index],
        y = ((side === "L" ? -1 : 1) * V.track_centres) / 2;
      key = "link_" + side + index;
      geometry.translate(-pose.origin[0], -y, -pose.origin[1]);
      geometry.rotateY(pose.angle);
      if (!groups[key]) {
        groups[key] = new THREE.Group();
        root.add(groups[key]);
        links[side][+index] = groups[key];
      }
    }
    if (!groups[key]) {
      groups[key] = new THREE.Group();
      parent.add(groups[key]);
    }
    if (!item.arm && wheelCenters[item.group]) {
      const w = wheelCenters[item.group];
      geometry.translate(-w.centre[0], -w.centre[1], -w.centre[2]);
      groups[key].position.set(...w.centre);
      if (!wheels.some((w) => w.group === groups[key]))
        wheels.push({ ...w, group: groups[key] });
    }
    if (key === "vehicle_slew_pinion") {
      geometry.translate(-V.slew_centre_distance, 0, 0);
      groups[key].position.x = V.slew_centre_distance;
    }
    const batchKey =
      key + ":" + item.color.join(",") + ":" + item.kind + ":" + !!item.moving;
    if (!batches.has(batchKey))
      batches.set(batchKey, { geometries: [], item, group: groups[key] });
    batches.get(batchKey).geometries.push(geometry);
  }
  for (const { geometries, item, group } of batches.values()) {
    const geometry = mergeGeometries(geometries),
      glass = item.kind === "glazing";
    const mesh = new THREE.Mesh(
      geometry,
      new THREE.MeshStandardMaterial({
        color: new THREE.Color(...item.color).convertSRGBToLinear(),
        roughness: glass ? 0.18 : item.kind === "hardware" ? 0.42 : 0.66,
        metalness: item.kind === "hardware" ? 0.55 : 0.12,
        transparent: glass,
        opacity: glass ? 0.42 : 1,
        depthWrite: !glass,
      }),
    );
    mesh.castShadow = !glass;
    mesh.receiveShadow = true;
    mesh.userData.moving = item.moving;
    group.add(mesh);
    for (const g of geometries) g.dispose();
  }
  let state,
    lastAt = performance.now(),
    latestAt = 0,
    frames = 0,
    fpsAt = performance.now(),
    fps = 60;
  // The CAD names its tracks from the opposite end: "L" is on the -Y side, which
  // is the operator's right. Each track must turn with its own drive command.
  const trackOf = { L: 1, R: 0 };
  function updateMachine(machine) {
    const s = solve(machine.strokes);
    for (const name of [
      "base",
      "boom",
      "stick",
      "bucket",
      "rocker",
      "coupler",
    ]) {
      groups["arm_" + name].position.set(
        s.origins[name][0],
        0,
        s.origins[name][1],
      );
      groups["arm_" + name].rotation.y = -s.angles[name];
    }
    for (const [i, role] of ["boom", "stick", "bucket"].entries()) {
      const [a, b] = [
        ["A", "B"],
        ["C", "D"],
        ["F", "R"],
      ][i];
      V.arm.actuators[role].y.forEach((y, side) => {
        const group = groups["arm_act_" + role + side];
        group.position.set(s.p[a][0], y, s.p[a][1]);
        group.rotation.y =
          Math.PI / 2 -
          Math.atan2(s.p[b][1] - s.p[a][1], s.p[b][0] - s.p[a][0]);
        for (const mesh of group.children)
          mesh.position.z =
            37.5 + (mesh.userData.moving ? machine.strokes[i] : 0);
      });
    }
    root.position.set(machine.x, machine.y, machine.z ?? 0);
    root.rotation.set(
      machine.roll ?? 0,
      -(machine.pitch ?? 0),
      machine.heading,
    );
    upper.rotation.z = (machine.slew * Math.PI) / 180;
    groups.vehicle_slew_pinion.rotation.z = (-upper.rotation.z * 96) / 20;
    for (const side of ["L", "R"]) {
      const offset = machine.tracks[trackOf[side]] / V.track_pitch;
      for (let i = 0; i < links[side].length; i++) {
        const phase =
            (((i + offset) % links[side].length) + links[side].length) %
            links[side].length,
          j = Math.floor(phase),
          f = phase - j;
        const a = data.track.initial_poses[j],
          b = data.track.initial_poses[(j + 1) % links[side].length];
        links[side][i].position.set(
          a.origin[0] * (1 - f) + b.origin[0] * f,
          ((side === "L" ? -1 : 1) * V.track_centres) / 2,
          a.origin[1] * (1 - f) + b.origin[1] * f,
        );
        let delta = b.angle - a.angle;
        delta = Math.atan2(Math.sin(delta), Math.cos(delta));
        links[side][i].rotation.y = -(a.angle + delta * f);
      }
    }
    for (const w of wheels)
      w.group.rotation.y = machine.tracks[trackOf[w.side]] / w.radius;
    return s;
  }

  // ------------------------------------------- synchronised frame playback
  // Binary frames carry the machine pose and the sand of the same tick. They
  // are played back slightly delayed and interpolated, so the bucket and its
  // load always move together.
  const queue = [],
    pose = initialMachine();
  let renderTick = null,
    content = 0,
    drawnKey = "",
    poseKey = "";
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
  const sameGrains = (a, b) =>
    a.length === b.length && a.every((value, i) => value === b[i]);
  function settle(frame) {
    if (frame.applied) return;
    frame.applied = true;
    // The first frames of a room, a reset or a connection restore the world;
    // nothing in them has just been dug.
    if (
      frame.tiles.length &&
      sand.applyTiles(frame.tiles, frame.tick > 2 && frame.tiles.length < 400)
    )
      dirty = true;
  }
  function pushFrame(frame) {
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
      !samePose(previous.machine, frame.machine) ||
      !sameGrains(previous.grains, frame.grains)
    )
      content++;
    frame.content = content;
    queue.push(frame);
    // Bound memory if the tab is hidden: older frames only matter for tiles.
    while (queue.length > 90) settle(queue.shift());
    latestAt = performance.now();
  }
  function play(dt) {
    if (!queue.length) return false;
    const newest = queue[queue.length - 1].tick,
      target = newest - DELAY_TICKS;
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
    for (let i = 0; i < 3; i++)
      pose.strokes[i] =
        a.machine.strokes[i] +
        (b.machine.strokes[i] - a.machine.strokes[i]) * alpha;
    for (let i = 0; i < 2; i++)
      pose.tracks[i] =
        a.machine.tracks[i] +
        (b.machine.tracks[i] - a.machine.tracks[i]) * alpha;
    for (const k of ["slew", "x", "y", "z", "heading", "pitch", "roll"])
      pose[k] = a.machine[k] + (b.machine[k] - a.machine[k]) * alpha;
    const nextPose = JSON.stringify(pose);
    if (nextPose !== poseKey) {
      updateMachine(pose);
      poseKey = nextPose;
    }
    grains.update(a, b, alpha, pose);
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
  const followHeading = () =>
    pose.heading + (mode === "bucket" ? (pose.slew * Math.PI) / 180 : 0);
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
      .colliders.filter((k) => k.hx !== undefined || k.r >= 100)
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
    const x = Math.round(pose.x / 60) * 60,
      y = Math.round(pose.y / 60) * 60;
    if (x === sunX && y === sunY) return;
    sunX = x;
    sunY = y;
    sun.target.position.set(x, y, pose.z);
    sun.position.set(x, y, pose.z).addScaledVector(sunDirection, 4600);
  }

  // ---------------------------------------------------------------- minimap
  let minimap, mapContext, mapKey;
  function drawMinimap() {
    if (!minimap) return;
    const key = `${Math.round(pose.x / 40)}:${Math.round(pose.y / 40)}:${Math.round(pose.heading * 12)}`;
    if (key === mapKey) return;
    mapKey = key;
    const size = minimap.width,
      span = WORLD.maxX - WORLD.minX,
      x = ((pose.x - WORLD.minX) / span) * size,
      y = ((WORLD.maxY - pose.y) / span) * size,
      c = mapContext;
    c.drawImage(world.map, 0, 0, size, size);
    c.save();
    c.translate(x, y);
    c.rotate(-pose.heading);
    c.fillStyle = "#ffd24a";
    c.strokeStyle = "#1c241f";
    c.lineWidth = 1.5 * (size / 180);
    c.beginPath();
    const u = size / 180;
    c.moveTo(8 * u, 0);
    c.lineTo(-5.5 * u, -5 * u);
    c.lineTo(-3 * u, 0);
    c.lineTo(-5.5 * u, 5 * u);
    c.closePath();
    c.fill();
    c.stroke();
    c.restore();
  }

  view("chase");
  updateMachine(pose);
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
    detailAt = 0;
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
    } else if (state) {
      // Before the first binary frame, show the pose from telemetry.
      const key = JSON.stringify(state.machine);
      if (key !== stateKey) {
        Object.assign(pose, state.machine);
        updateMachine(pose);
        stateKey = key;
        dirty = true;
      }
    }
    followMachine(dt);
    followSun();
    orbit.update();
    updateBoom(dt);
    if (now - detailAt > 250) {
      detailAt = now;
      if (sand.updateDetail(camera)) dirty = true;
      drawMinimap();
    }
    if (dirty && !document.hidden) {
      world.placeSky(camera);
      drawnFrom.copy(camera.position);
      if (boomLength < 1)
        camera.position.lerpVectors(orbit.target, drawnFrom, boomLength);
      renderer.render(scene, camera);
      camera.position.copy(drawnFrom);
      dirty = false;
      frames++;
    }
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
      if (sand.clear()) dirty = true;
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
        meshes: data.meshes.length,
        triangles: renderer.info.render.triangles,
        calls: renderer.info.render.calls,
        sandCount: sand.ready ? sand.chunkCount * SAND.page * SAND.page : 0,
        chunks: sand.chunkCount,
        grains: grains.count,
        loadTriangles: grains.triangles,
        flyingGrains: grains.flying,
        sandUpdateMs: grains.updateMs,
        tick: renderTick,
        pixelRatio: renderer.getPixelRatio(),
        shadows: renderer.shadowMap.enabled,
        camera: camera.position.toArray(),
      };
    },
  };
}

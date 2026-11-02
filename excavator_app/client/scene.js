import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { CONFIG as V } from "../shared/config.js";
import { solve } from "../shared/kinematics.js";
import { WORLD, initialMachine } from "../shared/world.js";

export async function createScene(stage, onProgress) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color("#e6e2d9");
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
  renderer.toneMappingExposure = 1.25;
  renderer.domElement.setAttribute(
    "aria-label",
    "Live 3D excavator and simulated sand",
  );
  stage.prepend(renderer.domElement);
  let dirty = true;
  const camera = new THREE.PerspectiveCamera(38, 1, 2, 6500);
  camera.up.set(0, 0, 1);
  const orbit = new OrbitControls(camera, renderer.domElement);
  orbit.enableDamping = true;
  orbit.addEventListener("change", () => {
    dirty = true;
  });
  orbit.minDistance = 450;
  orbit.maxDistance = 3000;
  orbit.maxPolarAngle = Math.PI * 0.48;
  scene.add(new THREE.HemisphereLight(0xffffff, 0xa69b80, 2.3));
  const sun = new THREE.DirectionalLight(0xfff5db, 3.2);
  sun.position.set(-250, -650, 1400);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.normalBias = 1.3;
  Object.assign(sun.shadow.camera, {
    left: -1200,
    right: 1200,
    top: 1100,
    bottom: -1100,
    near: 1,
    far: 2800,
  });
  scene.add(sun);
  const fill = new THREE.DirectionalLight(0xdbe6ff, 1);
  fill.position.set(800, 900, 700);
  scene.add(fill);
  const mat = (color, roughness = 0.9) =>
    new THREE.MeshStandardMaterial({ color, roughness });
  function box(w, d, h, x, y, z, material) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, d, h), material);
    mesh.position.set(x, y, z);
    mesh.receiveShadow = true;
    mesh.castShadow = true;
    scene.add(mesh);
    return mesh;
  }
  const concrete = mat("#c9c6bb"),
    ground = mat("#c8b697"),
    dark = mat("#454d45"),
    stripe = mat("#dbaa3d");
  box(1640, 1230, 50, 225, 0, -126, concrete);
  box(1550, 1140, 12, 225, 0, WORLD.floor - 6, ground);
  box(740, 1140, 90, -180, 0, -45, concrete);
  // The ramp shares its dimensions with particle contacts and crawler travel.
  const rampGeometry = new THREE.BufferGeometry();
  rampGeometry.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(
      [
        WORLD.platformEdge,
        WORLD.minY,
        0,
        WORLD.rampEnd,
        WORLD.minY,
        WORLD.floor,
        WORLD.rampEnd,
        WORLD.maxY,
        WORLD.floor,
        WORLD.platformEdge,
        WORLD.maxY,
        0,
      ],
      3,
    ),
  );
  rampGeometry.setIndex([0, 1, 2, 0, 2, 3]);
  rampGeometry.computeVertexNormals();
  const ramp = new THREE.Mesh(rampGeometry, concrete);
  ramp.receiveShadow = true;
  scene.add(ramp);
  for (const y of [-585, 585]) box(1640, 30, 75, 225, y, -66, concrete);
  for (const x of [-565, 1015]) box(30, 1140, 75, x, 0, -66, concrete);
  // Flat painted apron markings and a receiving area within the same sand pit.
  for (let y = -500; y < 520; y += 65) box(20, 34, 1, 157, y, 0.6, stripe);
  for (const y of [220, 490]) box(360, 4, 1, 440, y, WORLD.floor + 1, stripe);
  for (const x of [260, 620]) box(4, 270, 1, x, 355, WORLD.floor + 1, stripe);
  function label(text, x, y, z, width, color = "#5e6258") {
    const canvas = document.createElement("canvas");
    canvas.width = 1024;
    canvas.height = 128;
    const c = canvas.getContext("2d");
    c.fillStyle = color;
    c.font = "500 48px monospace";
    c.textAlign = "center";
    c.fillText(text, 512, 80);
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    const mesh = new THREE.Mesh(
      new THREE.PlaneGeometry(width, width / 8),
      new THREE.MeshBasicMaterial({
        map: texture,
        transparent: true,
        depthWrite: false,
      }),
    );
    mesh.position.set(x, y, z);
    scene.add(mesh);
  }
  label("ARM60 / DRIVE TO THE PIT", -215, -420, 1, 420);
  label("02 / POUR ZONE", 440, 435, WORLD.floor + 2, 260, "#8c713d");
  label("01 / SAND PIT", 690, -415, WORLD.floor + 2, 300);
  box(20, 85, 2, -430, 390, 1, dark);
  box(85, 20, 2, -430, 390, 1, dark);
  const root = new THREE.Group(),
    upper = new THREE.Group(),
    arm = new THREE.Group();
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
  let sand,
    sandTarget,
    sandCurrent,
    state,
    machineSignature,
    sandAnimating = false,
    latestAt = 0,
    lastAt = performance.now(),
    frames = 0,
    fpsAt = performance.now(),
    fps = 60;
  const dummy = new THREE.Object3D(),
    color = new THREE.Color();
  function setSand(positions) {
    if (sandTarget && positions.every((value, i) => value === sandTarget[i]))
      return;
    if (!sand) {
      sand = new THREE.InstancedMesh(
        new THREE.IcosahedronGeometry(WORLD.radius, 1),
        mat("#c79344"),
        positions.length / 3,
      );
      sand.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      sand.receiveShadow = true;
      sand.castShadow = true;
      sand.frustumCulled = false;
      scene.add(sand);
      for (let i = 0; i < sand.count; i++) {
        color.setHSL(0.103 + (i % 7) * 0.002, 0.46, 0.44 + (i % 11) * 0.012);
        sand.setColorAt(i, color);
      }
      sandCurrent = positions.slice();
    }
    sandTarget = positions;
    sandAnimating = true;
    dirty = true;
  }
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
    root.rotation.z = machine.heading;
    upper.rotation.z = (machine.slew * Math.PI) / 180;
    groups.vehicle_slew_pinion.rotation.z = (-upper.rotation.z * 96) / 20;
    for (const [sideIndex, side] of ["L", "R"].entries()) {
      const offset = machine.tracks[sideIndex] / V.track_pitch;
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
      w.group.rotation.y = machine.tracks[w.side === "L" ? 0 : 1] / w.radius;
    return s;
  }
  function view(name) {
    const poses = {
      orbit: [1300, -1500, 1150],
      side: [260, -1800, 470],
      top: [220, -30, 2100],
      bucket: [880, -620, 480],
    };
    camera.position.set(...poses[name]);
    orbit.target.set(name === "bucket" ? 470 : 220, 0, name === "top" ? 0 : 70);
    orbit.update();
  }
  view("orbit");
  updateMachine(initialMachine());
  new ResizeObserver(() => {
    renderer.setSize(stage.clientWidth, stage.clientHeight);
    camera.aspect = stage.clientWidth / stage.clientHeight;
    camera.updateProjectionMatrix();
    dirty = true;
  }).observe(stage);
  renderer.domElement.addEventListener("webglcontextlost", (event) => {
    event.preventDefault();
    onProgress("Graphics context lost. Reload to restore the scene.");
  });
  function animate(now) {
    const dt = Math.min(0.1, (now - lastAt) / 1000);
    lastAt = now;
    if (document.hidden) {
      requestAnimationFrame(animate);
      return;
    }
    if (state) {
      const signature = JSON.stringify(state.machine);
      if (signature !== machineSignature) {
        updateMachine(state.machine);
        machineSignature = signature;
        dirty = true;
      }
    }
    if (sandAnimating) {
      const blend = 1 - Math.exp(-dt * 24);
      let difference = 0;
      for (let i = 0; i < sand.count; i++) {
        for (let d = 0; d < 3; d++) {
          const index = 3 * i + d;
          difference = Math.max(
            difference,
            Math.abs(sandTarget[index] - sandCurrent[index]),
          );
          sandCurrent[index] +=
            (sandTarget[index] - sandCurrent[index]) * blend;
        }
        dummy.position.fromArray(sandCurrent, i * 3);
        dummy.updateMatrix();
        sand.setMatrixAt(i, dummy.matrix);
      }
      sand.instanceMatrix.needsUpdate = true;
      dirty = true;
      if (difference < 0.03) sandAnimating = false;
    }
    orbit.update();
    if (dirty && !document.hidden) {
      renderer.render(scene, camera);
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
    setSand,
    setState(value) {
      state = value;
      latestAt = performance.now();
    },
    telemetry() {
      return {
        fps,
        age: performance.now() - latestAt,
        meshes: data.meshes.length,
        triangles: renderer.info.render.triangles,
        sandCount: sand?.count || 0,
        pixelRatio: renderer.getPixelRatio(),
        shadows: renderer.shadowMap.enabled,
      };
    },
  };
}

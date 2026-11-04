import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { CONFIG as V } from "../shared/config.js";
import { solve } from "../shared/kinematics.js";
import {
  WORLD,
  SAND,
  POUR_ZONE,
  initialMachine,
  groundHeight,
  cellX,
  cellY,
} from "../shared/world.js";
import { tileCells, TILE_COUNT } from "../shared/protocol.js";

const NX = SAND.nx,
  NY = SAND.ny,
  CELLS = NX * NY,
  TICK_RATE = 30,
  // Render this many ticks behind the newest frame, so there is always a
  // later frame to interpolate toward despite network jitter.
  DELAY_TICKS = 1.75;

// Fine, seamless sand grain texture. It multiplies the sand colour, so it is
// kept near white; a few darker mineral grains break up the surface.
function sandTexture(renderer) {
  const size = 512,
    canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const c = canvas.getContext("2d"),
    image = c.createImageData(size, size),
    d = image.data;
  let seed = 11;
  const random = () =>
    (seed = (1664525 * seed + 1013904223) >>> 0) / 4294967296;
  for (let i = 0; i < size * size; i++) {
    const v = 0.84 + random() * 0.18,
      mineral = random() < 0.035 ? 0.72 + random() * 0.2 : 1;
    d[4 * i] = 255 * Math.min(1, v * mineral);
    d[4 * i + 1] = 255 * Math.min(1, v * 0.985 * mineral);
    d[4 * i + 2] = 255 * Math.min(1, v * 0.95 * mineral);
    d[4 * i + 3] = 255;
  }
  c.putImageData(image, 0, 0);
  for (let k = 0; k < 2400; k++) {
    const x = random() * size,
      y = random() * size,
      r = 0.6 + random() * 1.3,
      l = 165 + random() * 90;
    c.fillStyle = `rgb(${l | 0},${(l * 0.96) | 0},${(l * 0.88) | 0})`;
    for (const [ox, oy] of [
      [0, 0],
      [size, 0],
      [-size, 0],
      [0, size],
      [0, -size],
    ]) {
      c.beginPath();
      c.arc(x + ox, y + oy, r, 0, 2 * Math.PI);
      c.fill();
    }
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
  return texture;
}

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
    ground = mat("#b9b2a3"),
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
  const zone = POUR_ZONE,
    zoneX = (zone.minX + zone.maxX) / 2,
    zoneY = (zone.minY + zone.maxY) / 2;
  for (const y of [zone.minY, zone.maxY])
    box(zone.maxX - zone.minX, 4, 1, zoneX, y, WORLD.floor + 1, stripe);
  for (const x of [zone.minX, zone.maxX])
    box(4, zone.maxY - zone.minY, 1, x, zoneY, WORLD.floor + 1, stripe);
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

  // ---------------------------------------------------------------- sand bed
  const base = Float32Array.from({ length: NX }, (_, i) =>
      groundHeight(cellX(i)),
    ),
    thickness = new Float32Array(CELLS),
    sandPosition = new Float32Array(CELLS * 3),
    sandNormal = new Float32Array(CELLS * 3),
    sandColor = new Float32Array(CELLS * 3),
    sandUv = new Float32Array(CELLS * 2),
    // x: sand thickness (mm), y: time it was last disturbed (s).
    sandInfo = new Float32Array(CELLS * 2);
  const dry = new THREE.Color("#d3b88d").convertSRGBToLinear();
  for (let j = 0; j < NY; j++)
    for (let i = 0; i < NX; i++) {
      const c = j * NX + i,
        // Edge vertices reach the walls.
        x = i === 0 ? WORLD.minX : i === NX - 1 ? WORLD.maxX : cellX(i),
        y = j === 0 ? WORLD.minY : j === NY - 1 ? WORLD.maxY : cellY(j);
      sandPosition.set([x, y, base[i]], 3 * c);
      sandNormal.set([0, 0, 1], 3 * c);
      sandUv.set([x / 70, y / 70], 2 * c);
      sandInfo.set([0, -1e6], 2 * c);
      // Gentle low-frequency patchiness of colour and moisture.
      const patch =
        0.04 * Math.sin(x * 0.013 + Math.sin(y * 0.021) * 2) +
        0.03 * Math.sin(y * 0.017 - x * 0.006);
      sandColor.set(
        [dry.r * (1 + patch), dry.g * (1 + patch), dry.b * (1 + patch * 1.2)],
        3 * c,
      );
    }
  const sandIndex = new Uint16Array((NX - 1) * (NY - 1) * 6);
  for (let j = 0, o = 0; j < NY - 1; j++)
    for (let i = 0; i < NX - 1; i++) {
      const a = j * NX + i,
        b = a + 1,
        c = a + NX,
        d = c + 1;
      sandIndex.set([a, b, d, a, d, c], o);
      o += 6;
    }
  const sandGeometry = new THREE.BufferGeometry();
  const positionAttribute = new THREE.BufferAttribute(sandPosition, 3),
    normalAttribute = new THREE.BufferAttribute(sandNormal, 3),
    infoAttribute = new THREE.BufferAttribute(sandInfo, 2);
  for (const a of [positionAttribute, normalAttribute, infoAttribute])
    a.setUsage(THREE.DynamicDrawUsage);
  sandGeometry.setAttribute("position", positionAttribute);
  sandGeometry.setAttribute("normal", normalAttribute);
  sandGeometry.setAttribute("color", new THREE.BufferAttribute(sandColor, 3));
  sandGeometry.setAttribute("uv", new THREE.BufferAttribute(sandUv, 2));
  sandGeometry.setAttribute("sandInfo", infoAttribute);
  sandGeometry.setIndex(new THREE.BufferAttribute(sandIndex, 1));
  const grain = sandTexture(renderer),
    time = { value: 0 };
  const sandMaterial = new THREE.MeshStandardMaterial({
    color: 0xffffff,
    vertexColors: true,
    map: grain,
    bumpMap: grain,
    bumpScale: 1.4,
    roughness: 0.97,
    metalness: 0,
    polygonOffset: true,
    polygonOffsetFactor: -1,
    polygonOffsetUnits: -2,
  });
  // Bare concrete shows through where there is no sand; freshly dug or
  // dumped sand is darker (moist) and dries over about a minute.
  sandMaterial.onBeforeCompile = (shader) => {
    shader.uniforms.sandTime = time;
    shader.vertexShader = shader.vertexShader
      .replace(
        "#include <common>",
        "#include <common>\nattribute vec2 sandInfo;\nuniform float sandTime;\nvarying vec2 vSand;",
      )
      .replace(
        "#include <begin_vertex>",
        "#include <begin_vertex>\nvSand = vec2(sandInfo.x, exp(-max(0.0, sandTime - sandInfo.y) / 55.0));\nvSandXY = position.xy;",
      )
      .replace(
        "varying vec2 vSand;",
        "varying vec2 vSand;\nvarying vec2 vSandXY;",
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        "#include <common>\nvarying vec2 vSand;\nvarying vec2 vSandXY;\nfloat sandHash(vec2 p) { return fract(sin(dot(floor(p), vec2(12.9898, 78.233))) * 43758.5453); }",
      )
      .replace(
        "#include <map_fragment>",
        // Thin sand breaks up into scattered grains instead of a hard edge.
        "#include <map_fragment>\nif (vSand.x < 0.15 + 2.2 * sandHash(vSandXY * 1.6)) discard;\ndiffuseColor.rgb *= mix(1.0, 0.78, vSand.y) * mix(0.88, 1.0, smoothstep(0.3, 4.0, vSand.x));",
      );
  };
  const sandMesh = new THREE.Mesh(sandGeometry, sandMaterial);
  sandMesh.receiveShadow = true;
  sandMesh.castShadow = true;
  sandMesh.frustumCulled = false;
  scene.add(sandMesh);
  let terrainReady = false;
  const surface = (i, j) => base[i] + thickness[j * NX + i];
  function updateNormals(i0, i1, j0, j1) {
    for (let j = Math.max(0, j0); j <= Math.min(NY - 1, j1); j++)
      for (let i = Math.max(0, i0); i <= Math.min(NX - 1, i1); i++) {
        const il = Math.max(0, i - 1),
          ir = Math.min(NX - 1, i + 1),
          jd = Math.max(0, j - 1),
          ju = Math.min(NY - 1, j + 1),
          dx = (surface(ir, j) - surface(il, j)) / ((ir - il) * SAND.cell),
          dy = (surface(i, ju) - surface(i, jd)) / ((ju - jd) * SAND.cell),
          n = 1 / Math.sqrt(1 + dx * dx + dy * dy),
          c = 3 * (j * NX + i);
        sandNormal[c] = -dx * n;
        sandNormal[c + 1] = -dy * n;
        sandNormal[c + 2] = n;
      }
  }
  function markRows(j0, j1) {
    const start = Math.max(0, j0) * NX,
      count = (Math.min(NY - 1, j1) - Math.max(0, j0) + 1) * NX;
    for (const [attribute, size] of [
      [positionAttribute, 3],
      [normalAttribute, 3],
      [infoAttribute, 2],
    ]) {
      attribute.addUpdateRange(start * size, count * size);
      attribute.needsUpdate = true;
    }
  }
  // Apply sand-bed tiles; `fresh` marks changed cells as newly disturbed.
  function applyTiles(tiles, fresh) {
    let i0 = NX,
      i1 = -1,
      j0 = NY,
      j1 = -1;
    for (const { index, heights } of tiles) {
      const { i0: ti, j0: tj } = tileCells(index);
      let o = 0;
      for (let j = tj; j < tj + SAND.tile; j++)
        for (let i = ti; i < ti + SAND.tile; i++, o++) {
          if (i >= NX || j >= NY) continue;
          const c = j * NX + i,
            h = heights[o] * SAND.heightQuantum;
          if (h === thickness[c]) continue;
          if (fresh && Math.abs(h - thickness[c]) > 0.08)
            sandInfo[2 * c + 1] = time.value;
          thickness[c] = h;
          sandInfo[2 * c] = h;
          sandPosition[3 * c + 2] = base[i] + h;
          i0 = Math.min(i0, i);
          i1 = Math.max(i1, i);
          j0 = Math.min(j0, j);
          j1 = Math.max(j1, j);
        }
    }
    terrainReady = true;
    if (i1 < 0) return;
    updateNormals(i0 - 1, i1 + 1, j0 - 1, j1 + 1);
    markRows(j0 - 1, j1 + 1);
    dirty = true;
  }
  function setTerrain(full) {
    const tiles = [];
    for (let t = 0; t < TILE_COUNT; t++) {
      const { i0, j0 } = tileCells(t),
        heights = new Uint16Array(SAND.tile * SAND.tile);
      for (let j = 0; j < SAND.tile; j++)
        for (let i = 0; i < SAND.tile; i++)
          if (i0 + i < NX && j0 + j < NY)
            heights[j * SAND.tile + i] = full[(j0 + j) * NX + i0 + i];
      tiles.push({ index: t, heights });
    }
    applyTiles(tiles, false);
  }

  // ------------------------------------------------------------ free grains
  const grainMaterial = new THREE.MeshStandardMaterial({
    color: 0xffffff,
    roughness: 0.96,
    metalness: 0,
    flatShading: true,
  });
  // Drawn at the physical radius so grains touch, never cut, the bucket.
  const grains = new THREE.InstancedMesh(
    new THREE.IcosahedronGeometry(WORLD.radius, 0),
    grainMaterial,
    SAND.maxGrains,
  );
  grains.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  grains.count = 0;
  grains.castShadow = !mobile;
  grains.receiveShadow = true;
  grains.frustumCulled = false;
  scene.add(grains);
  const slotColor = new Float32Array(SAND.maxGrains * 3),
    slotTurn = new Float32Array(SAND.maxGrains * 4),
    slotScale = new Float32Array(SAND.maxGrains * 3),
    color = new THREE.Color(),
    turn = new THREE.Quaternion(),
    axis = new THREE.Vector3(),
    place = new THREE.Vector3(),
    size = new THREE.Vector3(),
    matrix = new THREE.Matrix4();
  for (let s = 0; s < SAND.maxGrains; s++) {
    // Freshly dug sand: the bed's colour, moist and a little darker.
    const shade = 0.66 + ((s * 11) % 9) * 0.018,
      warm = 1 + (((s * 7) % 5) - 2) * 0.02;
    color.copy(dry).multiplyScalar(shade);
    slotColor.set([color.r * warm, color.g, color.b / warm], 3 * s);
    axis
      .set(Math.sin(s * 12.9), Math.cos(s * 78.2), Math.sin(s * 3.7))
      .normalize();
    turn.setFromAxisAngle(axis, s * 2.399);
    slotTurn.set([turn.x, turn.y, turn.z, turn.w], 4 * s);
    // Irregular clumps, never larger than the physical grain.
    for (let d = 0; d < 3; d++)
      slotScale[3 * s + d] = 0.86 + ((s * (37 + 13 * d)) % 11) * 0.013;
  }
  grains.instanceColor = new THREE.InstancedBufferAttribute(
    new Float32Array(SAND.maxGrains * 3),
    3,
  );
  grains.instanceColor.setUsage(THREE.DynamicDrawUsage);
  const seenA = new Uint32Array(SAND.maxGrains),
    matched = new Uint32Array(SAND.maxGrains),
    indexA = new Int32Array(SAND.maxGrains);
  let serial = 0;
  function drawGrain(n, slot, x, y, z) {
    place.set(x, y, z);
    turn.fromArray(slotTurn, 4 * slot);
    size.fromArray(slotScale, 3 * slot);
    matrix.compose(place, turn, size);
    grains.setMatrixAt(n, matrix);
    grains.instanceColor.array.set(
      slotColor.subarray(3 * slot, 3 * slot + 3),
      3 * n,
    );
  }
  // Grains present in both frames move smoothly; new grains appear, and
  // settled grains vanish, halfway between frames as the bed tiles change.
  function drawGrains(a, b, alpha) {
    serial++;
    const ga = a.grains,
      gb = b.grains,
      q = SAND.positionQuantum;
    for (let n = 0; n < ga.length; n += 4) {
      seenA[ga[n] & 0xffff] = serial;
      indexA[ga[n] & 0xffff] = n;
    }
    let count = 0;
    for (let n = 0; n < gb.length; n += 4) {
      const slot = gb[n] & 0xffff;
      let x = gb[n + 1] * q,
        y = gb[n + 2] * q,
        z = gb[n + 3] * q;
      if (seenA[slot] === serial) {
        matched[slot] = serial;
        const m = indexA[slot],
          ax = ga[m + 1] * q,
          ay = ga[m + 2] * q,
          az = ga[m + 3] * q;
        if ((x - ax) ** 2 + (y - ay) ** 2 + (z - az) ** 2 < 3600) {
          x = ax + (x - ax) * alpha;
          y = ay + (y - ay) * alpha;
          z = az + (z - az) * alpha;
        }
      } else if (alpha < 0.5) continue;
      drawGrain(count++, slot, x, y, z);
    }
    if (alpha < 0.5)
      for (let n = 0; n < ga.length; n += 4) {
        const slot = ga[n] & 0xffff;
        if (matched[slot] !== serial)
          drawGrain(count++, slot, ga[n + 1] * q, ga[n + 2] * q, ga[n + 3] * q);
      }
    grains.count = count;
    grains.instanceMatrix.needsUpdate = true;
    grains.instanceColor.needsUpdate = true;
  }

  // ----------------------------------------------------------- CAD assembly
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
  let state,
    lastAt = performance.now(),
    latestAt = 0,
    frames = 0,
    fpsAt = performance.now(),
    fps = 60;
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

  // ------------------------------------------- synchronised frame playback
  // Binary frames carry the machine pose and the sand of the same tick. They
  // are played back slightly delayed and interpolated, so the bucket and its
  // load always move together.
  const queue = [],
    pose = {
      strokes: [0, 0, 0],
      slew: 0,
      x: 0,
      y: 0,
      z: 0,
      heading: 0,
      tracks: [0, 0],
    };
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
    a.heading === b.heading;
  const sameGrains = (a, b) =>
    a.length === b.length && a.every((value, i) => value === b[i]);
  function settle(frame) {
    if (frame.applied) return;
    frame.applied = true;
    if (frame.tiles.length)
      applyTiles(frame.tiles, frame.tiles.length < TILE_COUNT);
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
    for (const k of ["slew", "x", "y", "z", "heading"])
      pose[k] = a.machine[k] + (b.machine[k] - a.machine[k]) * alpha;
    const nextPose = JSON.stringify(pose);
    if (nextPose !== poseKey) {
      updateMachine(pose);
      poseKey = nextPose;
    }
    drawGrains(a, b, alpha);
    return true;
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
  let stateKey = "";
  function animate(now) {
    const dt = Math.min(0.1, (now - lastAt) / 1000);
    lastAt = now;
    time.value = now / 1000;
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
        updateMachine(state.machine);
        stateKey = key;
        dirty = true;
      }
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
    pushFrame,
    setTerrain,
    setState(value) {
      state = value;
      if (!queue.length) latestAt = performance.now();
    },
    telemetry() {
      return {
        fps,
        age: performance.now() - latestAt,
        meshes: data.meshes.length,
        triangles: renderer.info.render.triangles,
        sandCount: terrainReady ? CELLS : 0,
        grains: grains.count,
        pixelRatio: renderer.getPixelRatio(),
        shadows: renderer.shadowMap.enabled,
      };
    },
  };
}

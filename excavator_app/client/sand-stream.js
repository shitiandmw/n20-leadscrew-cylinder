import * as THREE from "three";
import { SAND, WORLD } from "../shared/world.js";
import { streakTexture } from "./sand-material.js";

const GRAIN = 0.5,
  SOLID = 0.6,
  // The area all the grains of one parcel can hide, in mm². Each parcel is drawn
  // as a streak with this much cover, so a stream is as dense as real sand would
  // be: nearly solid at the lip and thinning into streamers as it speeds up.
  HIDES = (1.5 * SOLID * SAND.grainVolume) / GRAIN,
  // The same grains, loosened in flight, as a sausage of volume π/4 d² length.
  LOOSE = (4 / Math.PI) * (SAND.grainVolume * 2.5),
  RADIUS = WORLD.radius.toFixed(1);

// Where a parcel's streak runs, shared by its quad and its grains. It reaches a
// little over a tick each way, so that the parcels of a stream overlap, and even a
// slow one hangs a few millimetres ahead. Only behind must it keep clear of the
// plates, because a parcel leaving the bucket is moving away from them.
const STREAK_VERTEX = `
  vec3 streakDirection = normalize(flight.xyz + vec3(0.0, 0.0, -60.0));
  float streakSpeed = length(flight.xyz);
  float streakClearance = ${RADIUS} + flight.w;
  float streakAhead = max(streakSpeed * 0.04, 8.0);
  float streakBehind = min(streakSpeed * 0.04,
    streakClearance + 500.0 * smoothstep(6.0, 12.0, flight.w));`;

// One quad a parcel turned to the camera around the way it is moving, and a few
// fine grains on top of that. Uploads remain one record per physics parcel. Both are
// always in the scene, drawing nothing when no sand falls, so that a first dig does
// not wait on their shaders.
export function createSandStream(scene, mobile) {
  const parcels = new THREE.InstancedBufferAttribute(
    new Float32Array(SAND.maxGrains * 4),
    4,
  );
  const motion = new THREE.InstancedBufferAttribute(
    new Float32Array(SAND.maxGrains * 4),
    4,
  );
  const slots = new THREE.InstancedBufferAttribute(
    new Float32Array(SAND.maxGrains),
    1,
  );
  const attributes = [parcels, motion, slots];
  for (const attribute of attributes)
    attribute.setUsage(THREE.DynamicDrawUsage);
  const instanced = (geometry) => {
    geometry.setAttribute("parcel", parcels);
    geometry.setAttribute("flight", motion);
    geometry.setAttribute("parcelSlot", slots);
    geometry.instanceCount = 0;
    return geometry;
  };
  const sandColour = () =>
    new THREE.Color("#e4d9c3").convertSRGBToLinear().multiplyScalar(0.78);

  // ------------------------------------------------------------------ the mass
  const quad = instanced(new THREE.InstancedBufferGeometry());
  quad.setAttribute(
    "position",
    new THREE.BufferAttribute(
      new Float32Array([-1, -1, 0, 1, -1, 0, 1, 1, 0, -1, 1, 0]),
      3,
    ),
  );
  quad.setIndex([0, 1, 2, 0, 2, 3]);
  const tile = { value: streakTexture() };
  const streakMaterial = new THREE.MeshLambertMaterial({
    color: sandColour(),
    transparent: true,
    depthWrite: false,
  });
  streakMaterial.onBeforeCompile = (shader) => {
    shader.uniforms.streakTile = tile;
    shader.vertexShader = shader.vertexShader
      .replace(
        "#include <common>",
        `#include <common>
        attribute vec4 parcel;
        attribute vec4 flight;
        attribute float parcelSlot;
        varying vec2 vStreak;
        varying vec2 vStreakTile;
        varying vec3 vStreakCover;`,
      )
      .replace(
        "#include <beginnormal_vertex>",
        `${STREAK_VERTEX}
        vec3 toCamera = normalize(cameraPosition - parcel.xyz);
        vec3 side = cross(streakDirection, toCamera);
        if (dot(side, side) < 0.0001) side = cross(vec3(0.31, 0.17, 0.93), toCamera);
        side = normalize(side);
        vec3 up = cross(toCamera, side);
        // How much of the way it runs can be seen from here, and how long it is.
        float facing = length(streakDirection - toCamera * dot(streakDirection, toCamera));
        float travel = streakAhead + streakBehind;
        // As it stretches a parcel draws in, keeping its volume.
        float core = 0.5 * sqrt(${LOOSE.toFixed(1)} / (travel + 8.0));
        float halfWidth = min(core * 3.0, streakClearance);
        // End on, it is still a blob of about its width.
        float round = max(0.0, halfWidth * 0.8 - 0.5 * travel * facing);
        float halfLength = 0.5 * travel * facing + round;
        float reach = position.y > 0.0 ? streakAhead : -streakBehind;
        vec3 streakOffset = side * position.x * halfWidth
          + streakDirection * reach + up * position.y * round;
        vStreak = position.xy;
        float slide = fract(parcelSlot * 0.618034);
        vStreakTile = vec2(position.x * halfWidth, position.y * halfLength)
          / vec2(32.0, 32.0 * (1.0 + streakSpeed / 400.0))
          + vec2(slide, fract(parcelSlot * 0.414214));
        vStreakCover = vec3(parcel.w * ${HIDES.toFixed(1)} / (halfWidth * halfLength * 1.5),
          min(1.0, core / halfWidth) * 0.45, 0.94 + 0.12 * slide);
        // Lit as a loose bundle of grains, a little brighter from above.
        vec3 objectNormal = normalize(toCamera + side * position.x * 0.35 + vec3(0.0, 0.0, 0.5));`,
      )
      .replace(
        "#include <begin_vertex>",
        "vec3 transformed = parcel.xyz + streakOffset;",
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        `#include <common>
        uniform sampler2D streakTile;
        varying vec2 vStreak;
        varying vec2 vStreakTile;
        varying vec3 vStreakCover;`,
      )
      .replace(
        "#include <color_fragment>",
        `#include <color_fragment>
        vec2 pattern = texture2D(streakTile, vStreakTile, -1.0).rg;
        float sigma = vStreakCover.y, halo = 0.55;
        float acrossCore = vStreak.x / sigma, acrossHalo = vStreak.x / halo;
        // Three quarters of the grains in the streamer, the rest flying round it.
        float profile = (0.75 * exp(-0.5 * acrossCore * acrossCore) / sigma
          + 0.25 * exp(-0.5 * acrossHalo * acrossHalo) / halo) * 0.3989;
        // To nothing at the edges of the quad, however dense the middle.
        float edges = (1.0 - smoothstep(0.6, 1.0, abs(vStreak.x)))
          * (1.0 - smoothstep(0.35, 1.0, abs(vStreak.y)));
        // Capped before the pattern, so that its grains and clumps still show.
        float cover = min(vStreakCover.x * profile, 2.0) * edges
          * pattern.r * 2.5 * pattern.g * 2.0;
        diffuseColor.a *= 1.0 - exp(-cover);
        if (diffuseColor.a < 0.004) discard;
        diffuseColor.rgb *= vStreakCover.z * (0.84 + 0.32 * pattern.g);`,
      )
      .replace(
        "#include <lights_fragment_end>",
        `#include <lights_fragment_end>
        // Light passes between flying grains and scatters: in shade they stay brighter
        // than a solid surface would.
        reflectedLight.indirectDiffuse *= 1.7;`,
      );
  };
  const streaks = new THREE.Mesh(quad, streakMaterial);
  streaks.name = "falling sand";
  streaks.receiveShadow = true;
  streaks.frustumCulled = false;
  scene.add(streaks);

  // ------------------------------------------------------------------ the grit
  // Fine grains along each streak, with subpixel coverage and a short exposure.
  const samples = mobile ? 24 : 64,
    fine = instanced(new THREE.InstancedBufferGeometry()),
    offsets = new Float32Array(samples * 3),
    seeds = new Float32Array(samples);
  let seed = 19;
  const random = () =>
    (seed = (1664525 * seed + 1013904223) >>> 0) / 4294967296;
  for (let i = 0; i < samples; i++) {
    const turn = random() * Math.PI * 2,
      out = Math.sqrt(random());
    // Across the streak in two directions, and where along it.
    offsets.set([out * Math.cos(turn), out * Math.sin(turn), random()], i * 3);
    seeds[i] = (i + random()) / samples;
  }
  fine.setAttribute("position", new THREE.BufferAttribute(offsets, 3));
  fine.setAttribute("grainSeed", new THREE.BufferAttribute(seeds, 1));
  const viewport = { value: new THREE.Vector2() };
  const grainMaterial = new THREE.MeshLambertMaterial({
    color: sandColour(),
    transparent: true,
    depthWrite: false,
  });
  grainMaterial.onBeforeCompile = (shader) => {
    shader.uniforms.grainViewport = viewport;
    shader.vertexShader = shader.vertexShader
      .replace(
        "#include <common>",
        `#include <common>
        attribute vec4 parcel;
        attribute vec4 flight;
        attribute float parcelSlot;
        attribute float grainSeed;
        uniform vec2 grainViewport;
        varying vec4 vGrainShape;
        varying vec3 vGrainInk;`,
      )
      .replace(
        "#include <beginnormal_vertex>",
        `${STREAK_VERTEX}
        float phase = fract(grainSeed + parcelSlot * 0.618034);
        vec3 objectNormal = normalize(vec3(phase - 0.5, fract(phase * 7.0) - 0.5, 0.9));`,
      )
      .replace(
        "#include <begin_vertex>",
        `float angle = parcelSlot * 2.399963;
        vec2 turned = mat2(cos(angle), sin(angle), -sin(angle), cos(angle)) * position.xy;
        // Spread as far as the streak's halo, and less where a plate is close.
        float spread = min(streakClearance, 1.2 + 14.0 * sqrt(1.0 / (1.0 + 0.012 * (streakAhead + streakBehind))));
        vec3 transformed = parcel.xyz
          + streakDirection * mix(-streakBehind, streakAhead, position.z)
          + vec3(turned * spread, 0.0);
        vGrainInk = vec3(parcel.w, 0.8 + 0.42 * phase, 0.38 + 0.28 * fract(phase * 3.0));`,
      )
      .replace(
        "#include <project_vertex>",
        `#include <project_vertex>
        float pixelsPerMM = 0.5 * grainViewport.y * projectionMatrix[1][1] / max(1.0, -mvPosition.z);
        float diameter = vGrainInk.z * pixelsPerMM;
        vec3 viewFlow = mat3(modelViewMatrix) * flight.xyz;
        // A 1/500 s exposure, capped in world space.
        vec2 blur = (viewFlow.xy + mvPosition.xy * viewFlow.z / max(1.0, -mvPosition.z))
          * 0.002 * pixelsPerMM;
        float blurLength = min(length(blur), 7.0);
        vec2 direction = length(blur) > 0.0001 ? normalize(blur) : vec2(0.0, 1.0);
        float raster = max(1.5, diameter + blurLength + 2.0);
        gl_PointSize = raster;
        vGrainShape = vec4(direction, blurLength, raster);
        vGrainInk.z = diameter;`,
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        `#include <common>
        varying vec4 vGrainShape;
        varying vec3 vGrainInk;`,
      )
      .replace(
        "#include <color_fragment>",
        `#include <color_fragment>
        vec2 pixel = (gl_PointCoord - 0.5) * vGrainShape.w;
        pixel.y = -pixel.y;
        vec2 direction = vGrainShape.xy;
        float along = max(0.0, abs(dot(pixel, direction)) - 0.5 * vGrainShape.z);
        float across = dot(pixel, vec2(-direction.y, direction.x));
        float diameter = vGrainInk.z;
        float sigma = max(0.42, diameter * 0.35);
        float footprint = exp(-0.5 * (along * along + across * across) / (sigma * sigma));
        // Conserve apparent coverage below a pixel and along a blurred path:
        // distant grains do not become bright, full-pixel specks.
        float ink = diameter * diameter / max(1.0, diameter * (diameter + vGrainShape.z));
        diffuseColor.a *= footprint * ink * vGrainInk.x;
        if (diffuseColor.a < 0.004) discard;
        diffuseColor.rgb *= vGrainInk.y;`,
      )
      .replace(
        "#include <lights_fragment_end>",
        `#include <lights_fragment_end>
        reflectedLight.indirectDiffuse *= 1.7;`,
      );
  };
  const grains = new THREE.Points(fine, grainMaterial);
  grains.name = "falling grains";
  grains.receiveShadow = true;
  grains.frustumCulled = false;
  grains.onBeforeRender = (renderer) =>
    renderer.getDrawingBufferSize(viewport.value);
  scene.add(grains);

  return {
    write(index, slot, x, y, z, coverage, velocity, room) {
      const k = index * 4;
      parcels.array[k] = x;
      parcels.array[k + 1] = y;
      parcels.array[k + 2] = z;
      parcels.array[k + 3] = coverage;
      slots.array[index] = slot;
      motion.array[k] = velocity[0];
      motion.array[k + 1] = velocity[1];
      motion.array[k + 2] = velocity[2];
      motion.array[k + 3] = room;
    },
    finish(count) {
      quad.instanceCount = fine.instanceCount = count;
      for (const attribute of attributes) {
        attribute.clearUpdateRanges();
        if (count) attribute.addUpdateRange(0, count * attribute.itemSize);
        attribute.needsUpdate = true;
      }
    },
    clear() {
      quad.instanceCount = fine.instanceCount = 0;
    },
  };
}

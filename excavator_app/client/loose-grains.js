import * as THREE from "three";
import { WORLD } from "../shared/world.js";

// Grains knocked loose: thrown up where a stream lands, rolling down a slope that
// has just moved, dropping off a bucket's rim. They are only what the eye expects
// to see. The physics knows nothing of them and they carry no sand.
const GRAVITY = WORLD.gravity,
  // Rolling and sliding together: they run on down a slope at the angle of repose
  // and stop on anything much flatter.
  FRICTION = 0.5,
  RESTITUTION = 0.3,
  // Below this speed into the bed (mm/s) a grain stays on it.
  BOUNCE_FROM = 200,
  LIFT = 0.3,
  // How long a grain that has stopped lasts before it is one with the bed.
  AT_REST = 0.1;

export function createLooseGrains(scene, bedHeight, capacity) {
  const positions = new Float32Array(capacity * 3),
    velocities = new Float32Array(capacity * 3),
    ages = new Float32Array(capacity),
    lives = new Float32Array(capacity),
    looks = new Float32Array(capacity * 3);
  let count = 0,
    seed = 91;
  const random = () =>
    (seed = (1664525 * seed + 1013904223) >>> 0) / 4294967296;
  const geometry = new THREE.BufferGeometry(),
    position = new THREE.BufferAttribute(positions, 3),
    velocity = new THREE.BufferAttribute(velocities, 3),
    look = new THREE.BufferAttribute(looks, 3),
    uploads = [position, velocity, look];
  for (const attribute of uploads) attribute.setUsage(THREE.DynamicDrawUsage);
  geometry.setAttribute("position", position);
  geometry.setAttribute("grainVelocity", velocity);
  geometry.setAttribute("grainLook", look);
  geometry.setDrawRange(0, 0);
  const viewport = { value: new THREE.Vector2() },
    material = new THREE.MeshLambertMaterial({
      color: new THREE.Color("#e4d9c3")
        .convertSRGBToLinear()
        .multiplyScalar(0.7),
      transparent: true,
      depthWrite: false,
    });
  material.onBeforeCompile = (shader) => {
    shader.uniforms.grainViewport = viewport;
    shader.vertexShader = shader.vertexShader
      .replace(
        "#include <common>",
        `#include <common>
        attribute vec3 grainVelocity;
        attribute vec3 grainLook;
        uniform vec2 grainViewport;
        varying vec2 vGrainLook;
        varying vec4 vGrainShape;`,
      )
      .replace(
        "#include <beginnormal_vertex>",
        "vec3 objectNormal = vec3(0.0, 0.0, 1.0);",
      )
      .replace(
        "#include <project_vertex>",
        `#include <project_vertex>
        float pixelsPerMM = 0.5 * grainViewport.y * projectionMatrix[1][1] / max(1.0, -mvPosition.z);
        // Never less than a speck: at a distance one stands for many grains.
        float diameter = max(1.4, grainLook.y * pixelsPerMM);
        // A 1/250 s exposure: a fast grain is a short streak, not a dot jumping about.
        vec3 viewFlow = mat3(modelViewMatrix) * grainVelocity;
        vec2 blur = (viewFlow.xy + mvPosition.xy * viewFlow.z / max(1.0, -mvPosition.z))
          * 0.004 * pixelsPerMM;
        float blurLength = min(length(blur), 14.0);
        vec2 direction = length(blur) > 0.0001 ? normalize(blur) : vec2(0.0, 1.0);
        gl_PointSize = diameter + blurLength + 1.0;
        vGrainShape = vec4(direction, blurLength, diameter);
        vGrainLook = vec2(grainLook.x, grainLook.z);`,
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        `#include <common>
        varying vec2 vGrainLook;
        varying vec4 vGrainShape;`,
      )
      .replace(
        "#include <color_fragment>",
        `#include <color_fragment>
        vec2 pixel = (gl_PointCoord - 0.5) * (vGrainShape.w + vGrainShape.z + 1.0);
        pixel.y = -pixel.y;
        vec2 direction = vGrainShape.xy;
        float along = max(0.0, abs(dot(pixel, direction)) - 0.5 * vGrainShape.z);
        float across = dot(pixel, vec2(-direction.y, direction.x));
        float fromCentre = 2.0 * length(vec2(along, across)) / vGrainShape.w;
        // Spread along its path, it covers each pixel for less of the exposure.
        diffuseColor.a *= vGrainLook.x * (1.0 - smoothstep(0.55, 1.0, fromCentre))
          * vGrainShape.w / (vGrainShape.w + 0.6 * vGrainShape.z);
        if (diffuseColor.a < 0.01) discard;
        diffuseColor.rgb *= vGrainLook.y;`,
      );
  };
  const points = new THREE.Points(geometry, material);
  points.name = "loose grains";
  points.receiveShadow = true;
  points.frustumCulled = false;
  points.onBeforeRender = (renderer) =>
    renderer.getDrawingBufferSize(viewport.value);
  scene.add(points);

  function emit(x, y, z, vx, vy, vz, life, diameter) {
    if (count >= capacity) return;
    const k = 3 * count;
    positions[k] = x;
    positions[k + 1] = y;
    positions[k + 2] = z;
    velocities[k] = vx;
    velocities[k + 1] = vy;
    velocities[k + 2] = vz;
    ages[count] = 0;
    lives[count] = life;
    looks[k] = 1;
    looks[k + 1] = diameter;
    looks[k + 2] = 0.72 + 0.36 * random();
    count++;
  }
  function remove(n) {
    count--;
    if (n === count) return;
    const k = 3 * n,
      last = 3 * count;
    for (let d = 0; d < 3; d++) {
      positions[k + d] = positions[last + d];
      velocities[k + d] = velocities[last + d];
      looks[k + d] = looks[last + d];
    }
    ages[n] = ages[count];
    lives[n] = lives[count];
  }
  function step(dt) {
    if (!count) return false;
    let n = 0;
    while (n < count) {
      ages[n] += dt;
      if (ages[n] >= lives[n]) {
        remove(n);
        continue;
      }
      const k = 3 * n;
      let vx = velocities[k],
        vy = velocities[k + 1],
        vz = velocities[k + 2] - GRAVITY * dt;
      const x = positions[k] + vx * dt,
        y = positions[k + 1] + vy * dt;
      let z = positions[k + 2] + vz * dt;
      const bed = bedHeight(x, y);
      if (z <= bed + LIFT) {
        z = bed + LIFT;
        const sx = (bedHeight(x + 4, y) - bed) / 4,
          sy = (bedHeight(x, y + 4) - bed) / 4,
          scale = 1 / Math.sqrt(1 + sx * sx + sy * sy),
          // Speed along the bed's normal, negative going into it.
          into = (vz - sx * vx - sy * vy) * scale;
        if (into < 0) {
          const push = -into * (into < -BOUNCE_FROM ? 1 + RESTITUTION : 1);
          vx += -sx * scale * push;
          vy += -sy * scale * push;
          vz += scale * push;
          // Coulomb friction: the same push against the bed, times the friction.
          const speed = Math.hypot(vx, vy, vz),
            drag = FRICTION * push;
          if (speed <= drag) {
            vx = vy = vz = 0;
            lives[n] = Math.min(lives[n], ages[n] + AT_REST);
          } else {
            const keep = 1 - drag / speed;
            vx *= keep;
            vy *= keep;
            vz *= keep;
          }
        }
      }
      positions[k] = x;
      positions[k + 1] = y;
      positions[k + 2] = z;
      velocities[k] = vx;
      velocities[k + 1] = vy;
      velocities[k + 2] = vz;
      looks[k] = Math.min(1, (4 * (lives[n] - ages[n])) / lives[n]);
      n++;
    }
    geometry.setDrawRange(0, count);
    for (const attribute of uploads) {
      attribute.clearUpdateRanges();
      if (count) attribute.addUpdateRange(0, 3 * count);
      attribute.needsUpdate = true;
    }
    return true;
  }
  return {
    emit,
    step,
    random,
    clear() {
      count = 0;
      geometry.setDrawRange(0, 0);
    },
    get count() {
      return count;
    },
  };
}

// A faint haze where sand lands or is turned over. Each puff is worked out on the
// graphics card from where and when it began, so a puff costs one upload, once.
export function createDust(scene, capacity) {
  const POINT = 8,
    data = new Float32Array(capacity * POINT),
    buffer = new THREE.InterleavedBuffer(data, POINT).setUsage(
      THREE.DynamicDrawUsage,
    ),
    geometry = new THREE.BufferGeometry(),
    time = { value: 0 },
    viewport = { value: new THREE.Vector2() };
  geometry.setAttribute(
    "position",
    new THREE.InterleavedBufferAttribute(buffer, 3, 0),
  );
  geometry.setAttribute(
    "dustDrift",
    new THREE.InterleavedBufferAttribute(buffer, 3, 3),
  );
  geometry.setAttribute(
    "dustBorn",
    new THREE.InterleavedBufferAttribute(buffer, 2, 6),
  );
  geometry.setDrawRange(0, 0);
  const material = new THREE.MeshLambertMaterial({
    color: new THREE.Color("#e8dcc4").convertSRGBToLinear(),
    transparent: true,
    depthWrite: false,
  });
  material.onBeforeCompile = (shader) => {
    shader.uniforms.dustTime = time;
    shader.uniforms.dustViewport = viewport;
    shader.vertexShader = shader.vertexShader
      .replace(
        "#include <common>",
        `#include <common>
        attribute vec3 dustDrift;
        attribute vec2 dustBorn;
        uniform float dustTime;
        uniform vec2 dustViewport;
        varying float vDust;`,
      )
      .replace(
        "#include <beginnormal_vertex>",
        "vec3 objectNormal = vec3(0.0, 0.0, 1.0);",
      )
      .replace(
        "#include <begin_vertex>",
        `float dustAge = clamp((dustTime - dustBorn.x) / dustBorn.y, 0.0, 1.0);
        // It slows in the air as it spreads.
        vec3 transformed = position + dustDrift * dustBorn.y * dustAge * (1.0 - 0.45 * dustAge);
        vDust = smoothstep(0.0, 0.12, dustAge) * (1.0 - dustAge) * (1.0 - dustAge);`,
      )
      .replace(
        "#include <project_vertex>",
        `#include <project_vertex>
        gl_PointSize = min(160.0, (22.0 + 90.0 * sqrt(dustAge)) * 0.5 * dustViewport.y
          * projectionMatrix[1][1] / max(1.0, -mvPosition.z));`,
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        `#include <common>
        varying float vDust;`,
      )
      .replace(
        "#include <color_fragment>",
        `#include <color_fragment>
        float dustRadius = 2.0 * length(gl_PointCoord - 0.5);
        float dustSoft = max(0.0, 1.0 - dustRadius * dustRadius);
        diffuseColor.a *= 0.1 * vDust * dustSoft * dustSoft;
        if (diffuseColor.a < 0.002) discard;`,
      );
  };
  const points = new THREE.Points(geometry, material);
  points.name = "dust";
  points.frustumCulled = false;
  points.receiveShadow = true;
  points.onBeforeRender = (renderer) =>
    renderer.getDrawingBufferSize(viewport.value);
  scene.add(points);
  let next = 0,
    used = 0,
    lastDeath = 0;
  return {
    emit(x, y, z, vx, vy, vz, life) {
      const k = next * POINT;
      data[k] = x;
      data[k + 1] = y;
      data[k + 2] = z;
      data[k + 3] = vx;
      data[k + 4] = vy;
      data[k + 5] = vz;
      data[k + 6] = time.value;
      data[k + 7] = life;
      next = (next + 1) % capacity;
      used = Math.max(used, next === 0 ? capacity : next);
      lastDeath = Math.max(lastDeath, time.value + life);
      geometry.setDrawRange(0, used);
      buffer.needsUpdate = true;
    },
    // Returns whether any is still in the air.
    step(dt) {
      if (!used) return false;
      time.value += dt;
      if (time.value < lastDeath) return true;
      used = next = 0;
      geometry.setDrawRange(0, 0);
      return false;
    },
    clear() {
      used = next = 0;
      geometry.setDrawRange(0, 0);
    },
  };
}

import * as THREE from "three";
import { MarchingCubes } from "three/addons/objects/MarchingCubes.js";
import { SAND, armFrame } from "../shared/world.js";
import { CONFIG } from "../shared/config.js";
import { solve } from "../shared/kinematics.js";
import { BucketFrame } from "../shared/bucket.js";
import { groundHeight } from "../shared/landscape.js";
import { flightRoom, ParcelMotion } from "./sand-flight.js";
import { createSandStream } from "./sand-stream.js";
import {
  SandSurfaceField,
  SURFACE_CENTRE,
  SURFACE_SIZE,
  SURFACE_LEVEL,
} from "./sand-surface.js";

export function createLooseSandView(
  scene,
  texture,
  mobile,
  bedHeight = groundHeight,
) {
  const dry = new THREE.Color("#e4d9c3").convertSRGBToLinear();
  const material = new THREE.MeshStandardMaterial({
    color: dry.clone().multiplyScalar(0.78),
    map: texture,
    bumpMap: texture,
    bumpScale: 0.35,
    roughness: 0.97,
    metalness: 0,
  });
  // The same 70 mm texture repeat as the bed, projected on all three axes.
  // Bucket-local coordinates keep the grain pattern still on a carried load.
  material.onBeforeCompile = (shader) => {
    shader.vertexShader = shader.vertexShader
      .replace(
        "#include <common>",
        `#include <common>
        varying vec3 vGrainPosition;
        varying vec3 vGrainNormal;`,
      )
      .replace(
        "#include <begin_vertex>",
        `#include <begin_vertex>
        vGrainPosition = position * ${SURFACE_SIZE / 2}.0 + vec3(${SURFACE_CENTRE.map((v) => v.toFixed(1)).join(",")});
        vGrainNormal = normal;`,
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        `#include <common>
        varying vec3 vGrainPosition;
        varying vec3 vGrainNormal;`,
      )
      .replace(
        "#include <map_fragment>",
        `
        vec3 sandWeights = pow(abs(normalize(vGrainNormal)), vec3(4.0));
        sandWeights /= max(dot(sandWeights, vec3(1.0)), 0.0001);
        vec4 sandTexel = texture2D(map, vGrainPosition.yz / 70.0) * sandWeights.x
          + texture2D(map, vGrainPosition.xz / 70.0) * sandWeights.y
          + texture2D(map, vGrainPosition.xy / 70.0) * sandWeights.z;
        diffuseColor *= sandTexel;`,
      )
      .replace(
        "#include <normal_fragment_maps>",
        `
        float relief = sandTexel.r * bumpScale;
        normal = perturbNormalArb(-vViewPosition, normal,
          vec2(dFdx(relief), dFdy(relief)), faceDirection);`,
      );
  };
  const surface = new MarchingCubes(
    mobile ? 32 : 40,
    material,
    false,
    false,
    20000,
  );
  surface.isolation = SURFACE_LEVEL;
  surface.position.set(...SURFACE_CENTRE);
  surface.scale.setScalar(SURFACE_SIZE / 2);
  surface.castShadow = !mobile;
  surface.receiveShadow = true;
  surface.frustumCulled = false;
  surface.visible = false;
  const load = new THREE.Group();
  load.matrixAutoUpdate = false;
  load.add(surface);
  scene.add(load);
  const field = new SandSurfaceField(surface.resolution, surface.field);

  const stream = createSandStream(scene, mobile);
  const motion = new ParcelMotion(SAND.maxGrains),
    velocity = [0, 0, 0];

  const frame = new BucketFrame(),
    local = [0, 0, 0];
  const basis = [new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()];
  const seen = new Uint32Array(SAND.maxGrains),
    matched = new Uint32Array(SAND.maxGrains);
  const index = new Int32Array(SAND.maxGrains);
  let serial = 0,
    count = 0,
    flying = 0,
    updateMs = 0,
    lastTick = -1,
    drawTick = 0;
  function add(slot, x, y, z, coverage, velocities, offset) {
    if (coverage <= 0 || count >= SAND.maxGrains) return;
    frame.toLocal(x, y, z, local);
    if (velocities) {
      velocity[0] = velocities[offset];
      velocity[1] = velocities[offset + 1];
      velocity[2] = velocities[offset + 2];
    } else motion.read(slot, drawTick, velocity);
    const room = flightRoom(...local, z - bedHeight(x, y));
    if (room > 0 && velocity[2] < -60) flying++;
    stream.write(count++, slot, x, y, z, coverage, velocity, room);
    field.add(...local, coverage);
  }
  function update(a, b, alpha, machine) {
    const start = performance.now(),
      solution = solve(machine.strokes);
    frame.set(
      armFrame(
        machine,
        solution.origins.bucket[0] + CONFIG.arm_offset[0],
        solution.origins.bucket[1] + CONFIG.arm_offset[2],
        solution.angles.bucket,
      ),
    );
    basis[0].fromArray(frame.ex);
    basis[1].fromArray(frame.ey);
    basis[2].fromArray(frame.ez);
    load.matrix.makeBasis(...basis).setPosition(frame.x, frame.y, frame.z);
    load.matrixWorldNeedsUpdate = true;
    field.clear();
    if (b.tick < lastTick) motion.clear();
    lastTick = b.tick;
    drawTick = b.tick;
    count = 0;
    flying = 0;
    serial++;
    const ga = a.grains,
      gb = b.grains,
      q = SAND.positionQuantum;
    // Crossfade at the bed's midpoint switch without changing apparent grain
    // size. The fine stream blends coverage while testing against scene depth.
    const t = Math.max(0, Math.min(1, (alpha - 0.25) * 2));
    const arrival = t * t * (3 - 2 * t);
    for (let n = 0; n < ga.length; n += 4) {
      seen[ga[n] & 0xffff] = serial;
      index[ga[n] & 0xffff] = n;
    }
    for (let n = 0; n < gb.length; n += 4) {
      const slot = gb[n] & 0xffff;
      let x = b.origin[0] + gb[n + 1] * q,
        y = b.origin[1] + gb[n + 2] * q,
        z = b.origin[2] + gb[n + 3] * q,
        coverage = arrival;
      if (seen[slot] === serial) {
        matched[slot] = serial;
        const m = index[slot],
          ax = a.origin[0] + ga[m + 1] * q,
          ay = a.origin[1] + ga[m + 2] * q,
          az = a.origin[2] + ga[m + 3] * q;
        coverage = 1;
        if (a.tick !== b.tick && !b.velocities)
          motion.between(slot, a.tick, b.tick, ax, ay, az, x, y, z);
        if ((x - ax) ** 2 + (y - ay) ** 2 + (z - az) ** 2 < 3600) {
          x = ax + (x - ax) * alpha;
          y = ay + (y - ay) * alpha;
          z = az + (z - az) * alpha;
        }
      } else motion.forget(slot);
      add(slot, x, y, z, coverage, b.velocities, (n / 4) * 3);
    }
    drawTick = a.tick;
    if (arrival < 1)
      for (let n = 0; n < ga.length; n += 4) {
        const slot = ga[n] & 0xffff;
        if (matched[slot] !== serial)
          add(
            slot,
            a.origin[0] + ga[n + 1] * q,
            a.origin[1] + ga[n + 2] * q,
            a.origin[2] + ga[n + 3] * q,
            1 - arrival,
            a.velocities,
            (n / 4) * 3,
          );
      }
    if (count) {
      field.finish();
      surface.normal_cache.fill(0);
      surface.update();
    } else {
      surface.count = 0;
    }
    surface.visible = surface.count > 0;
    // MarchingCubes marks its full preallocated buffers dirty. Upload just the
    // generated portion, including on devices with a small graphics budget.
    for (const attribute of Object.values(surface.geometry.attributes)) {
      attribute.clearUpdateRanges();
      if (surface.count)
        attribute.addUpdateRange(0, surface.count * attribute.itemSize);
    }
    stream.finish(count);
    updateMs = performance.now() - start;
  }
  return {
    pushFrame(frame, previous) {
      motion.attach(previous, frame);
    },
    update,
    clear() {
      count = 0;
      flying = 0;
      stream.clear();
      motion.clear();
      lastTick = -1;
      surface.visible = false;
      surface.count = 0;
    },
    get count() {
      return count;
    },
    get flying() {
      return flying;
    },
    get triangles() {
      return surface.count / 3;
    },
    get updateMs() {
      return updateMs;
    },
  };
}

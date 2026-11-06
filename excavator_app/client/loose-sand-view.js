import * as THREE from "three";
import { BUCKET, SAND, armFrame } from "../shared/world.js";
import { LOAD, mouthToLocal } from "../shared/bucket-load.js";
import { CONFIG } from "../shared/config.js";
import { solve } from "../shared/kinematics.js";
import { BucketFrame } from "../shared/bucket.js";
import { groundHeight } from "../shared/landscape.js";
import { flightRoom, MAX_TICK_TRAVEL, ParcelMotion } from "./sand-flight.js";
import { createSandStream } from "./sand-stream.js";
import { createLoadMeshes } from "./load-mesh.js";
import { createDust, createLooseGrains } from "./loose-grains.js";
import { SAND_LUMPS } from "./sand-relief.js";

const TICK = 1 / 30,
  // Past this distance from the camera (mm), loose grains are not worth working out.
  GRAINS_WITHIN = 3500,
  // Grains flung up by one landing parcel at full speed, and the speed that is.
  SPLASH = 10,
  SPLASH_SPEED = 1800,
  // Grains set moving per mm a cell of the bed rises or falls in a tick.
  FLOW_PER_MM = 0.9,
  FLOW_FROM = 0.1,
  // Chance of a puff of dust from one parcel landing, and from a mm of bed moving.
  DUST_PER_LANDING = 0.14,
  DUST_PER_MM = 0.012,
  // Grains shaken off a rim in a tick, per mm/s the bucket moves, and at most. A rim
  // only sheds where the sand reaches within this many mm of it.
  SHAKEN_PER_SPEED = 0.05,
  SHAKEN_MOST = 10,
  SHAKEN_WITHIN = 2,
  // When a stream stops, the last of the sand goes on dribbling off the lip: grains
  // a tick at first, and how much of that is left a tick later.
  DRIBBLE = 26,
  DRIBBLE_KEEP = 0.96,
  // The parcels near its bucket that count as a machine pouring in full flow.
  FULL_FLOW = 10;

export function createLooseSandView(
  scene,
  texture,
  mobile,
  bedHeight = groundHeight,
  lumps = null,
) {
  const dry = new THREE.Color("#e4d9c3").convertSRGBToLinear();
  const material = new THREE.MeshStandardMaterial({
    color: dry.clone().multiplyScalar(0.8),
    map: texture,
    bumpMap: texture,
    bumpScale: 1.4,
    roughness: 0.97,
    metalness: 0,
  });
  // The grain and lumps of the bed, in the bucket's own coordinates so that they
  // stay still on a carried load: along the bucket from its lip, across it, and out
  // of its mouth. The grain repeats every 70 mm on all three axes, as on the bed.
  const origin = mouthToLocal(0, 0, 0, [0, 0, 0]),
    alongEnd = mouthToLocal(1, 0, 0, [0, 0, 0]),
    outEnd = mouthToLocal(0, 0, 1, [0, 0, 0]),
    along = new THREE.Vector3(
      alongEnd[0] - origin[0],
      0,
      alongEnd[2] - origin[2],
    ),
    out = new THREE.Vector3(outEnd[0] - origin[0], 0, outEnd[2] - origin[2]);
  material.onBeforeCompile = (shader) => {
    shader.uniforms.sandLumps = { value: lumps };
    shader.uniforms.loadAlong = { value: along };
    shader.uniforms.loadOut = { value: out };
    shader.vertexShader = shader.vertexShader
      .replace(
        "#include <common>",
        `#include <common>
        attribute float loadDepth;
        uniform vec3 loadAlong;
        uniform vec3 loadOut;
        varying vec3 vGrainPosition;
        varying vec3 vGrainNormal;
        varying vec3 vLoadAt;
        varying vec3 vLoadAlong;
        varying vec3 vLoadAcross;
        varying float vLoadDepth;`,
      )
      .replace(
        "#include <begin_vertex>",
        `#include <begin_vertex>
        vGrainPosition = position;
        vGrainNormal = normal;
        vLoadAt = vec3(dot(position, loadAlong), position.y, dot(position, loadOut));
        vLoadAlong = normalMatrix * loadAlong;
        vLoadAcross = normalMatrix * vec3(0.0, 1.0, 0.0);
        vLoadDepth = loadDepth;`,
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        `#include <common>
        varying vec3 vGrainPosition;
        varying vec3 vGrainNormal;
        varying vec3 vLoadAt;
        varying vec3 vLoadAlong;
        varying vec3 vLoadAcross;
        varying float vLoadDepth;
        ${SAND_LUMPS}`,
      )
      .replace(
        "#include <map_fragment>",
        `
        vec3 sandWeights = pow(abs(normalize(vGrainNormal)), vec3(4.0));
        sandWeights /= max(dot(sandWeights, vec3(1.0)), 0.0001);
        vec4 sandTexel = texture2D(map, vGrainPosition.yz / 70.0) * sandWeights.x
          + texture2D(map, vGrainPosition.xz / 70.0) * sandWeights.y
          + texture2D(map, vGrainPosition.xy / 70.0) * sandWeights.z;
        diffuseColor *= sandTexel;
        // Just dug: as lumpy as the bed gets. Flat in its own frame, for the grooves.
        sandRelief(vLoadAt, vec3(0.0, 0.0, 1.0), 1.0);
        // Thin sand breaks up into patches, as it does on the bed.
        if (vLoadDepth < 0.35 + 0.9 * clamp(0.5 - sandPatch, 0.0, 1.0)) discard;
        diffuseColor.rgb *= sandShade;`,
      )
      .replace(
        "#include <normal_fragment_maps>",
        `
        float relief = sandTexel.r * bumpScale;
        normal = perturbNormalArb(-vViewPosition, normal,
          vec2(dFdx(relief), dFdy(relief)), faceDirection);
        normal = normalize(normal - vLoadAlong * sandSlope.x - vLoadAcross * sandSlope.y);`,
      );
  };
  const loads = createLoadMeshes(scene, material, !mobile);

  const stream = createSandStream(scene, mobile);
  const motion = new ParcelMotion(SAND.maxGrains),
    velocity = [0, 0, 0],
    loose = createLooseGrains(scene, bedHeight, mobile ? 700 : 2400),
    dust = createDust(scene, mobile ? 24 : 80);

  // Where the buckets near falling sand or holding a load are this frame, by
  // machine id.
  const buckets = new Map(),
    spareBuckets = [],
    local = [0, 0, 0],
    // Machines whose buckets have held sand, and so are no longer clean.
    used = new Set();
  const seen = new Uint32Array(SAND.maxGrains),
    matched = new Uint32Array(SAND.maxGrains);
  const index = new Int32Array(SAND.maxGrains);
  let serial = 0,
    count = 0,
    flying = 0,
    updateMs = 0,
    lastTick = -1,
    drawTick = 0,
    viewer = null,
    shakenAt = 0;
  function add(slot, x, y, z, coverage, velocities, offset, holder) {
    if (coverage <= 0 || count >= SAND.maxGrains) return;
    const bucket = holder ? buckets.get(holder) : undefined;
    if (bucket) bucket.toLocal(x, y, z, local);
    // A grain near no bucket has nothing to keep clear of but the bed.
    else local[0] = local[1] = local[2] = 1e6;
    if (velocities) {
      velocity[0] = velocities[offset];
      velocity[1] = velocities[offset + 1];
      velocity[2] = velocities[offset + 2];
    } else motion.read(slot, drawTick, velocity);
    const room = flightRoom(...local);
    if (room > 0 && velocity[2] < -60) flying++;
    stream.write(count++, slot, x, y, z, coverage, velocity, room);
  }
  function bucketOf(id, poses) {
    let frame = buckets.get(id);
    if (frame || !poses.has(id)) return frame;
    const machine = poses.get(id),
      solution = solve(machine.strokes);
    frame = spareBuckets.pop() ?? new BucketFrame();
    frame.set(
      armFrame(
        machine,
        solution.origins.bucket[0] + CONFIG.arm_offset[0],
        solution.origins.bucket[1] + CONFIG.arm_offset[2],
        solution.angles.bucket,
      ),
    );
    buckets.set(id, frame);
    return frame;
  }
  function noteHolders(frame, poses) {
    let last = 0;
    for (const holder of frame.holders) {
      if (holder === last) continue;
      last = holder;
      if (holder) bucketOf(holder, poses);
    }
  }
  function update(a, b, alpha, poses) {
    const start = performance.now();
    for (const frame of buckets.values()) spareBuckets.push(frame);
    buckets.clear();
    noteHolders(a, poses);
    noteHolders(b, poses);
    loads.begin();
    for (const id of used) if (!b.byId.has(id)) used.delete(id);
    for (const machine of b.machines) {
      const from = a.byId.get(machine.id)?.load ?? null,
        holding = from || machine.load;
      if (holding) used.add(machine.id);
      // The dusting of an empty bucket is not worth a draw from far away.
      const frame =
        (holding ||
          (used.has(machine.id) &&
            nearViewer(machine.x, machine.y, machine.z))) &&
        bucketOf(machine.id, poses);
      if (frame) loads.draw(frame, from, machine.load, alpha);
    }
    loads.end();
    shakeRims(b.tick, b, poses);
    if (b.tick < lastTick) {
      motion.clear();
      used.clear();
    }
    lastTick = b.tick;
    drawTick = b.tick;
    count = 0;
    flying = 0;
    serial++;
    const sa = a.slots,
      sb = b.slots,
      pa = a.positions,
      pb = b.positions;
    // Crossfade at the bed's midpoint switch without changing apparent grain
    // size. The fine stream blends coverage while testing against scene depth.
    const t = Math.max(0, Math.min(1, (alpha - 0.25) * 2));
    const arrival = t * t * (3 - 2 * t);
    for (let n = 0; n < sa.length; n++) {
      seen[sa[n]] = serial;
      index[sa[n]] = n;
    }
    for (let n = 0; n < sb.length; n++) {
      const slot = sb[n];
      let x = pb[3 * n],
        y = pb[3 * n + 1],
        z = pb[3 * n + 2],
        coverage = arrival;
      if (seen[slot] === serial) {
        matched[slot] = serial;
        const m = index[slot],
          ax = pa[3 * m],
          ay = pa[3 * m + 1],
          az = pa[3 * m + 2];
        coverage = 1;
        if (a.tick !== b.tick && !b.velocities)
          motion.between(slot, a.tick, b.tick, ax, ay, az, x, y, z);
        if (
          (x - ax) ** 2 + (y - ay) ** 2 + (z - az) ** 2 <
          MAX_TICK_TRAVEL * MAX_TICK_TRAVEL
        ) {
          x = ax + (x - ax) * alpha;
          y = ay + (y - ay) * alpha;
          z = az + (z - az) * alpha;
        }
      } else motion.forget(slot);
      add(slot, x, y, z, coverage, b.velocities, 3 * n, b.holders[n]);
    }
    drawTick = a.tick;
    if (arrival < 1)
      for (let n = 0; n < sa.length; n++) {
        const slot = sa[n];
        if (matched[slot] !== serial)
          add(
            slot,
            pa[3 * n],
            pa[3 * n + 1],
            pa[3 * n + 2],
            1 - arrival,
            a.velocities,
            3 * n,
            a.holders[n],
          );
      }
    stream.finish(count);
    updateMs = performance.now() - start;
  }
  // Parcels that were in the last frame and are not in this one have landed, or
  // have fallen into a bucket. Noted now, on arrival, and shown when played.
  function noteLandings(previous, frame) {
    const before = previous?.slots;
    if (!before?.length || !previous.velocities) return;
    const after = frame.slots,
      mark = ++serial;
    for (let n = 0; n < after.length; n++) seen[after[n]] = mark;
    for (let n = 0; n < before.length; n++) {
      if (seen[before[n]] === mark) continue;
      const p = previous.positions,
        v = previous.velocities;
      (frame.landings ??= []).push(
        p[3 * n],
        p[3 * n + 1],
        p[3 * n + 2],
        v[3 * n],
        v[3 * n + 1],
        v[3 * n + 2],
      );
    }
  }
  const nearViewer = (x, y, z) =>
    !viewer ||
    (x - viewer.x) ** 2 + (y - viewer.y) ** 2 + (z - viewer.z) ** 2 <
      GRAINS_WITHIN * GRAINS_WITHIN;
  const puff = (x, y, bed) =>
    dust.emit(
      x + 16 * (loose.random() - 0.5),
      y + 16 * (loose.random() - 0.5),
      bed + 8,
      70 * (loose.random() - 0.5),
      70 * (loose.random() - 0.5),
      25 + 45 * loose.random(),
      0.9 + 1.1 * loose.random(),
    );
  function splash(x, y, z, vx, vy, vz) {
    // It went on falling for up to a tick after the last we saw of it.
    const lx = x + vx * TICK,
      ly = y + vy * TICK,
      bed = bedHeight(lx, ly),
      fall = Math.hypot(vx, vy, vz);
    if (
      z + vz * TICK - 4905 * TICK * TICK > bed + 10 ||
      !nearViewer(lx, ly, bed)
    )
      return;
    const number = Math.round(SPLASH * Math.min(1, fall / SPLASH_SPEED));
    if (loose.random() < (DUST_PER_LANDING * number) / SPLASH)
      puff(lx, ly, bed);
    for (let k = 0; k < number; k++) {
      const turn = 2 * Math.PI * loose.random(),
        out = loose.random(),
        speed = fall * (0.05 + 0.22 * loose.random() ** 2),
        // Mostly out and low, as sand scatters.
        along = speed * (0.45 + 0.5 * out),
        up = speed * (1.15 - 0.6 * out);
      loose.emit(
        lx + 5 * out * Math.cos(turn),
        ly + 5 * out * Math.sin(turn),
        bed + 1,
        0.1 * vx + along * Math.cos(turn),
        0.1 * vy + along * Math.sin(turn),
        up,
        0.25 + 0.5 * loose.random(),
        0.5 + 0.7 * loose.random(),
      );
    }
  }
  const rim = [0, 0, 0],
    rimWorld = [0, 0, 0],
    lastCentre = new Map(),
    dribbles = new Map(),
    pouring = new Map();
  const beyondLip = () => -1 - 8 * loose.random();
  // One grain off a bucket moving at this speed, from this point in its mouth.
  function shed(bucket, u, y, w, vx, vy, vz) {
    mouthToLocal(u, y, w, rim);
    bucket.toWorld(rim[0], rim[1], rim[2], rimWorld);
    loose.emit(
      rimWorld[0],
      rimWorld[1],
      rimWorld[2],
      vx + 40 * (loose.random() - 0.5),
      vy + 40 * (loose.random() - 0.5),
      vz + 40 * (loose.random() - 0.5),
      0.7 + 0.6 * loose.random(),
      0.5 + 0.7 * loose.random(),
    );
  }
  // A moving bucket shakes a few grains off wherever its sand reaches a rim, and a
  // bucket that has just stopped pouring goes on dribbling off its lip for a while.
  function shakeRims(tick, frame, poses) {
    if (tick === shakenAt) return;
    const ticks = tick - shakenAt;
    shakenAt = tick;
    pouring.clear();
    for (const holder of frame.holders)
      if (holder) pouring.set(holder, (pouring.get(holder) ?? 0) + 1);
    for (const machine of frame.machines) {
      const parcels = pouring.get(machine.id) ?? 0,
        dribble = Math.max(
          (dribbles.get(machine.id) ?? 0) * DRIBBLE_KEEP ** ticks,
          Math.min(1, parcels / FULL_FLOW),
        );
      dribbles.set(machine.id, dribble < 0.02 ? 0 : dribble);
      const bucket =
        (machine.load || dribble >= 0.02) && bucketOf(machine.id, poses);
      if (!bucket) {
        lastCentre.delete(machine.id);
        continue;
      }
      const [x, y, z] = bucket.centre;
      const last = lastCentre.get(machine.id);
      lastCentre.set(machine.id, [x, y, z]);
      if (!last || ticks > 12 || !nearViewer(x, y, z)) continue;
      const scale = 30 / ticks,
        vx = (x - last[0]) * scale,
        vy = (y - last[1]) * scale,
        vz = (z - last[2]) * scale;
      // Only once the stream itself has gone; it is plenty on its own.
      if (parcels < 3)
        for (let n = 0; n < dribble * DRIBBLE * ticks; n++)
          shed(
            bucket,
            beyondLip(),
            LOAD.rowY(Math.floor(loose.random() * LOAD.nv)) +
              LOAD.dv * loose.random(),
            1,
            vx,
            vy,
            vz,
          );
      if (!machine.load) continue;
      const tries =
        ticks *
        Math.min(SHAKEN_MOST, Math.hypot(vx, vy, vz) * SHAKEN_PER_SPEED);
      for (let n = 0; n < tries; n++) {
        // At the lip, or over one or other cheek.
        const place = loose.random(),
          row = Math.floor(loose.random() * LOAD.nv),
          column = Math.floor(loose.random() * LOAD.nu),
          i = place < 0.5 ? 0 : column,
          j = place < 0.5 ? row : place < 0.75 ? 0 : LOAD.nv - 1,
          u = (i + 0.5) * LOAD.du,
          top = LOAD.floorAt(u) + machine.load[j * LOAD.nu + i] * LOAD.quantum;
        if (top < -SHAKEN_WITHIN) continue;
        if (place < 0.5)
          shed(
            bucket,
            beyondLip(),
            LOAD.rowY(j) + LOAD.dv * loose.random(),
            top + 1,
            vx,
            vy,
            vz,
          );
        else
          shed(
            bucket,
            u,
            (place < 0.75 ? -1 : 1) * (BUCKET.outerHalfWidth + 0.5),
            1,
            vx,
            vy,
            vz,
          );
      }
    }
  }
  // A cell of the bed rose or fell: some of its surface sets off down the slope.
  function moved(x, y, delta) {
    const amount = Math.abs(delta);
    if (amount < FLOW_FROM || loose.random() > amount * FLOW_PER_MM) return;
    const px = x + SAND.cell * (loose.random() - 0.5),
      py = y + SAND.cell * (loose.random() - 0.5),
      bed = bedHeight(px, py);
    if (!nearViewer(px, py, bed)) return;
    if (loose.random() < amount * DUST_PER_MM) puff(px, py, bed);
    const reach = 8,
      sx =
        (bedHeight(px + reach, py) - bedHeight(px - reach, py)) / (2 * reach),
      sy =
        (bedHeight(px, py + reach) - bedHeight(px, py - reach)) / (2 * reach),
      speed = 30 + 120 * loose.random();
    loose.emit(
      px,
      py,
      bed + 0.5,
      -sx * speed + 30 * (loose.random() - 0.5),
      -sy * speed + 30 * (loose.random() - 0.5),
      20 * loose.random(),
      0.3 + 0.5 * loose.random(),
      0.5 + 0.8 * loose.random(),
    );
  }
  return {
    pushFrame(frame, previous) {
      motion.attach(previous, frame);
      noteLandings(previous, frame);
    },
    // A frame has come up for playing: what it carried happens now.
    settle(frame, camera) {
      viewer = camera;
      const landings = frame.landings;
      if (!landings) return;
      for (let k = 0; k < landings.length; k += 6)
        splash(
          landings[k],
          landings[k + 1],
          landings[k + 2],
          landings[k + 3],
          landings[k + 4],
          landings[k + 5],
        );
      frame.landings = null;
    },
    moved,
    // Returns whether any loose grains are still on the move.
    stepGrains(dt) {
      const airborne = dust.step(dt);
      return loose.step(dt) || airborne;
    },
    update,
    clear() {
      count = 0;
      flying = 0;
      stream.clear();
      motion.clear();
      loose.clear();
      dust.clear();
      used.clear();
      lastCentre.clear();
      dribbles.clear();
      shakenAt = 0;
      lastTick = -1;
      loads.begin();
      loads.end();
    },
    get count() {
      return count;
    },
    get flying() {
      return flying;
    },
    get looseGrains() {
      return loose.count;
    },
    get triangles() {
      return loads.triangles;
    },
    get updateMs() {
      return updateMs;
    },
  };
}

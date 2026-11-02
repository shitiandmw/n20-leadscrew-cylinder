import { solve } from "../shared/kinematics.js";
import { CONFIG } from "../shared/config.js";
import {
  WORLD,
  BUCKET_PROFILE,
  clamp,
  neutral,
  groundHeight,
  crawlerExtent,
  initialMachine,
} from "../shared/world.js";

export function bucketPose(machine) {
  const s = solve(machine.strokes),
    a = machine.heading + (machine.slew * Math.PI) / 180;
  const reach = s.origins.bucket[0] + CONFIG.arm_offset[0];
  return {
    x: machine.x + Math.cos(a) * reach,
    y: machine.y + Math.sin(a) * reach,
    z: (machine.z ?? 0) + s.origins.bucket[1] + CONFIG.arm_offset[2],
    yaw: a,
    pitch: s.angles.bucket,
  };
}
export function toLocal(x, y, z, b) {
  const dx = x - b.x,
    dy = y - b.y,
    dz = z - b.z;
  const forward = dx * Math.cos(b.yaw) + dy * Math.sin(b.yaw);
  return [
    forward * Math.cos(b.pitch) + dz * Math.sin(b.pitch),
    -dx * Math.sin(b.yaw) + dy * Math.cos(b.yaw),
    -forward * Math.sin(b.pitch) + dz * Math.cos(b.pitch),
  ];
}
export function toWorld(x, y, z, b) {
  const f = x * Math.cos(b.pitch) - z * Math.sin(b.pitch);
  return [
    b.x + f * Math.cos(b.yaw) - y * Math.sin(b.yaw),
    b.y + f * Math.sin(b.yaw) + y * Math.cos(b.yaw),
    b.z + x * Math.sin(b.pitch) + z * Math.cos(b.pitch),
  ];
}
export function insideProfile(x, z) {
  let inside = false;
  for (
    let i = 0, j = BUCKET_PROFILE.length - 1;
    i < BUCKET_PROFILE.length;
    j = i++
  ) {
    const a = BUCKET_PROFILE[i],
      b = BUCKET_PROFILE[j];
    if (
      a[1] > z !== b[1] > z &&
      x < ((b[0] - a[0]) * (z - a[1])) / (b[1] - a[1]) + a[0]
    )
      inside = !inside;
  }
  return inside;
}

// 3-D position-based granular fluid. Double-density relaxation supplies a
// short-range pressure; finite-size contacts and tangential friction give
// sand its resting pile. All grains remain simulated during scoop and pour.
export class SandSimulation {
  constructor() {
    this.reset();
  }
  reset() {
    this.machine = initialMachine();
    this.axes = neutral();
    this.speed = 0.65;
    this.estop = false;
    this.tick = 0;
    this.resting = false;
    const positions = [];
    let seed = 60;
    const random = () =>
      (seed = (1664525 * seed + 1013904223) >>> 0) / 4294967296 - 0.5;
    for (let layer = 0; layer < 7; layer++) {
      const nx = 24 - 2 * layer,
        ny = 20 - 2 * layer;
      for (let x = 0; x < nx; x++)
        for (let y = 0; y < ny; y++)
          positions.push(
            490 + (x - (nx - 1) / 2) * 12.05 + (layer % 2) * 6 + random() * 0.1,
            (y - (ny - 1) / 2) * 12.05 + (layer % 2) * 6 + random() * 0.1,
            WORLD.floor + 6.1 + layer * 8.6,
          );
    }
    this.positions = new Float32Array(positions);
    this.previous = this.positions.slice();
    this.velocities = new Float32Array(positions.length);
    this.count = positions.length / 3;
    this.density = new Float32Array(this.count);
    this.nearDensity = new Float32Array(this.count);
    this.contacts = new Uint8Array(this.count);
    this.bucketContacts = new Uint8Array(this.count);
    this.bucket = bucketPose(this.machine);
    this.stats = { carried: 0, deposited: 0, active: 0 };
  }

  advanceMachine(dt) {
    const a = this.estop ? neutral() : this.axes,
      m = this.machine,
      speed = this.speed;
    for (const [i, key] of ["boom", "stick", "bucket"].entries())
      m.strokes[i] = clamp(m.strokes[i] + a[key] * 13 * speed * dt, 0, 60);
    m.slew = clamp(m.slew + a.slew * 30 * speed * dt, -150, 150);
    const l = a.leftTrack * 65 * speed,
      r = a.rightTrack * 65 * speed;
    m.heading += ((r - l) / CONFIG.track_centres) * dt;
    const extent = crawlerExtent(m.heading);
    m.x = clamp(
      m.x + ((l + r) / 2) * Math.cos(m.heading) * dt,
      WORLD.minX + extent.x,
      WORLD.maxX - extent.x,
    );
    m.y = clamp(
      m.y + ((l + r) / 2) * Math.sin(m.heading) * dt,
      WORLD.minY + extent.y,
      WORLD.maxY - extent.y,
    );
    // A level chassis rests on the highest terrain under its footprint.
    // The sandbox does not simulate suspension or vehicle tipping.
    m.z = groundHeight(m.x - extent.x);
    m.tracks[0] += l * dt;
    m.tracks[1] += r * dt;
  }

  // Resolve the open CAD bucket shell and its two cheek plates in local space.
  collideBucket(i, pose) {
    const p = this.positions,
      k = i * 3;
    if (
      Math.abs(p[k] - pose.x) > 145 ||
      Math.abs(p[k + 1] - pose.y) > 145 ||
      Math.abs(p[k + 2] - pose.z) > 145
    )
      return;
    let [x, y, z] = toLocal(p[k], p[k + 1], p[k + 2], pose),
      hit = false;
    const radius = WORLD.radius,
      shellDistance = radius + 2;
    if (Math.abs(y) < 40 + radius) {
      for (let j = 0; j < BUCKET_PROFILE.length - 1; j++) {
        const a = BUCKET_PROFILE[j],
          b = BUCKET_PROFILE[j + 1],
          dx = b[0] - a[0],
          dz = b[1] - a[1];
        const t = clamp(
          ((x - a[0]) * dx + (z - a[1]) * dz) / (dx * dx + dz * dz),
          0,
          1,
        );
        const nx = x - a[0] - dx * t,
          nz = z - a[1] - dz * t,
          distance = Math.hypot(nx, nz);
        if (distance < shellDistance && distance > 1e-6) {
          x += (nx / distance) * (shellDistance - distance);
          z += (nz / distance) * (shellDistance - distance);
          hit = true;
        }
      }
    }
    if (insideProfile(x, z))
      for (const side of [-38.25, 38.25]) {
        const d = y - side,
          limit = radius + 1.75;
        if (Math.abs(d) < limit) {
          y = side + (d < 0 ? -limit : limit);
          hit = true;
        }
      }
    if (hit) {
      const world = toWorld(x, y, z, pose);
      p[k] = world[0];
      p[k + 1] = world[1];
      p[k + 2] = world[2];
      this.contacts[i] = 1;
      this.bucketContacts[i] = 1;
    }
  }

  boundaries(i) {
    const p = this.positions,
      k = 3 * i,
      r = WORLD.radius;
    p[k] = clamp(p[k], WORLD.minX + r, WORLD.maxX - r);
    p[k + 1] = clamp(p[k + 1], WORLD.minY + r, WORLD.maxY - r);
    const floor = groundHeight(p[k]);
    if (p[k + 2] < floor + r) {
      p[k + 2] = floor + r;
      this.contacts[i] = 1;
    }
  }

  substep(dt) {
    this.advanceMachine(dt);
    const pose = bucketPose(this.machine),
      p = this.positions,
      v = this.velocities,
      prev = this.previous;
    prev.set(p);
    this.contacts.fill(0);
    this.bucketContacts.fill(0);
    for (let i = 0; i < this.count; i++) {
      const k = i * 3;
      v[k + 2] -= WORLD.gravity * dt;
      for (let d = 0; d < 3; d++) p[k + d] += clamp(v[k + d], -1300, 1300) * dt;
      this.boundaries(i);
      this.collideBucket(i, pose);
    }
    const h = WORLD.radius * 2.6,
      diameter = WORLD.radius * 2;
    // Spatial hashing restricts pressure and contact work to local neighbours.
    const hash = new Map(),
      cells = new Int32Array(this.count * 3),
      pairs = [];
    const key = (x, y, z) => x + 256 + (y + 256) * 1024 + (z + 256) * 1048576;
    for (let i = 0; i < this.count; i++) {
      const k = i * 3,
        x = Math.floor(p[k] / h),
        y = Math.floor(p[k + 1] / h),
        z = Math.floor(p[k + 2] / h);
      cells[k] = x;
      cells[k + 1] = y;
      cells[k + 2] = z;
      const cell = key(x, y, z);
      if (!hash.has(cell)) hash.set(cell, []);
      hash.get(cell).push(i);
    }
    this.density.fill(0);
    this.nearDensity.fill(0);
    for (let i = 0; i < this.count; i++) {
      const k = 3 * i;
      for (let x = -1; x <= 1; x++)
        for (let y = -1; y <= 1; y++)
          for (let z = -1; z <= 1; z++) {
            const cell = hash.get(
              key(cells[k] + x, cells[k + 1] + y, cells[k + 2] + z),
            );
            if (!cell) continue;
            for (const j of cell)
              if (j > i) {
                const n = 3 * j,
                  dx = p[k] - p[n],
                  dy = p[k + 1] - p[n + 1],
                  dz = p[k + 2] - p[n + 2],
                  distanceSquared = dx * dx + dy * dy + dz * dz;
                if (distanceSquared < h * h && distanceSquared > 1e-12) {
                  const distance = Math.sqrt(distanceSquared);
                  pairs.push(i, j);
                  const q = 1 - distance / h;
                  this.density[i] += q * q;
                  this.density[j] += q * q;
                  this.nearDensity[i] += q * q * q;
                  this.nearDensity[j] += q * q * q;
                }
              }
          }
    }
    for (let pass = 0; pass < 5; pass++) {
      for (let index = 0; index < pairs.length; index += 2) {
        const i = pairs[index],
          j = pairs[index + 1],
          k = 3 * i,
          n = 3 * j;
        const dx = p[k] - p[n],
          dy = p[k + 1] - p[n + 1],
          dz = p[k + 2] - p[n + 2];
        const distance = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (distance < 1e-6 || distance > h) continue;
        const q = 1 - distance / h;
        const pressure = Math.max(0, this.density[i] + this.density[j] - 1.5);
        const near = this.nearDensity[i] + this.nearDensity[j];
        const relaxation =
          pass === 0 && pressure > 0
            ? Math.min(0.5, dt * dt * 18000 * (pressure * q + near * q * q))
            : 0;
        const overlap = Math.max(0, diameter - distance),
          correction = (overlap * 0.48 + relaxation) / distance;
        p[k] += dx * correction;
        p[n] -= dx * correction;
        p[k + 1] += dy * correction;
        p[n + 1] -= dy * correction;
        p[k + 2] += dz * correction;
        p[n + 2] -= dz * correction;
        if (overlap > 0) {
          this.contacts[i] = 1;
          this.contacts[j] = 1;
          // Coulomb-style tangential position friction, limited by penetration.
          const ux = p[k] - prev[k] - (p[n] - prev[n]);
          const uy = p[k + 1] - prev[k + 1] - (p[n + 1] - prev[n + 1]);
          const uz = p[k + 2] - prev[k + 2] - (p[n + 2] - prev[n + 2]);
          const dot = (ux * dx + uy * dy + uz * dz) / (distance * distance);
          const tx = ux - dot * dx,
            ty = uy - dot * dy,
            tz = uz - dot * dz;
          const friction = Math.min(
            0.5,
            (overlap * 0.85) / (Math.sqrt(tx * tx + ty * ty + tz * tz) + 1e-6),
          );
          p[k] -= tx * friction;
          p[n] += tx * friction;
          p[k + 1] -= ty * friction;
          p[n + 1] += ty * friction;
          p[k + 2] -= tz * friction;
          p[n + 2] += tz * friction;
        }
      }
      for (let i = 0; i < this.count; i++) {
        this.boundaries(i);
        this.collideBucket(i, pose);
      }
    }
    for (let i = 0; i < this.count; i++) {
      const k = 3 * i;
      for (let d = 0; d < 3; d++)
        v[k + d] = clamp((p[k + d] - prev[k + d]) / dt, -1300, 1300) * 0.997;
      // Static-friction sleep prevents tiny constraint corrections from
      // liquefying a resting pile. Bucket contacts and faster impacts wake it.
      if (
        this.contacts[i] &&
        !this.bucketContacts[i] &&
        Math.hypot(v[k], v[k + 1], v[k + 2]) < 32
      ) {
        for (let d = 0; d < 3; d++) {
          p[k + d] = prev[k + d];
          v[k + d] = 0;
        }
      }
      if (
        this.contacts[i] &&
        p[k + 2] <= groundHeight(p[k]) + WORLD.radius + 0.1
      ) {
        const speed = Math.hypot(v[k], v[k + 1]);
        const friction = Math.max(
          0,
          1 - (WORLD.gravity * dt * 0.8) / (speed + 1e-6),
        );
        v[k] *= friction;
        v[k + 1] *= friction;
        v[k + 2] = Math.max(0, v[k + 2]) * 0.05;
      }
    }
    this.bucket = pose;
  }

  step(dt = 1 / 30) {
    if (
      this.resting &&
      (this.estop || Object.values(this.axes).every((value) => value === 0))
    ) {
      this.tick++;
      return;
    }
    // Four substeps prevent the thin, moving bucket shell tunnelling through grains.
    for (let i = 0; i < 4; i++) this.substep(dt / 4);
    this.tick++;
    let carried = 0,
      deposited = 0,
      active = 0;
    for (let i = 0; i < this.count; i++) {
      const k = i * 3,
        p = this.positions;
      const [x, y, z] = toLocal(p[k], p[k + 1], p[k + 2], this.bucket);
      if (Math.abs(y) < 36.5 && insideProfile(x, z)) carried++;
      if (
        p[k] > 260 &&
        p[k] < 620 &&
        p[k + 1] > 220 &&
        p[k + 1] < 490 &&
        p[k + 2] < 0
      )
        deposited++;
      if (
        Math.hypot(
          this.velocities[k],
          this.velocities[k + 1],
          this.velocities[k + 2],
        ) > 35
      )
        active++;
    }
    this.stats = { carried, deposited, active };
    this.resting = this.velocities.every((value) => Math.abs(value) < 0.5);
  }
}

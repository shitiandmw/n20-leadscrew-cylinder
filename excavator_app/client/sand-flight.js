import { BUCKET, BUCKET_PROFILE, SAND, WORLD } from "../shared/world.js";
import { WALLS, TEETH, insideCavity, insidePolygon } from "../shared/bucket.js";

const PLATES = [...WALLS, TEETH];
const clamp01 = (value) => Math.max(0, Math.min(1, value));

function segmentDistance2(x, z, ax, az, dx, dz, len2) {
  const t = clamp01(((x - ax) * dx + (z - az) * dz) / len2);
  return (x - ax - t * dx) ** 2 + (z - az - t * dz) ** 2;
}

// Extra room for visual breakup beyond the physical particle's sphere. Use
// finite plate segments, including the teeth and cheeks, so the stream may
// spread after clearing the mouth but never fan through a bucket wall.
export function flightRoom(x, y, z, heightAboveBed) {
  if (insideCavity(x, y, z) || heightAboveBed <= WORLD.radius) return 0;
  const beyondCheek = Math.max(0, Math.abs(y) - BUCKET.outerHalfWidth);
  let distance = Infinity;
  for (const wall of PLATES) {
    const d2 = segmentDistance2(
      x,
      z,
      wall.ax,
      wall.az,
      wall.dx,
      wall.dz,
      wall.len2,
    );
    distance = Math.min(
      distance,
      Math.sqrt(d2 + beyondCheek ** 2) - Math.max(wall.inner, wall.outer),
    );
  }
  let edge2 = 0;
  if (!insidePolygon(x, z)) {
    edge2 = Infinity;
    for (let i = 0; i < BUCKET_PROFILE.length; i++) {
      const a = BUCKET_PROFILE[i],
        b = BUCKET_PROFILE[(i + 1) % BUCKET_PROFILE.length];
      const dx = b[0] - a[0],
        dz = b[1] - a[1];
      edge2 = Math.min(
        edge2,
        segmentDistance2(x, z, ...a, dx, dz, dx * dx + dz * dz),
      );
    }
  }
  distance = Math.min(
    distance,
    Math.hypot(Math.sqrt(edge2), Math.abs(y) - BUCKET.cheekCentre) -
      (BUCKET.outerHalfWidth - BUCKET.innerHalfWidth) / 2,
  );
  return Math.max(
    0,
    Math.min(
      12,
      distance - WORLD.radius - 0.5,
      (heightAboveBed - WORLD.radius) * 0.65,
    ),
  );
}

// Derive motion only from nearby simulation ticks. Never stretch a reconnect,
// reused slot, or teleport into a long trail. The last valid velocity is kept
// for a frozen snapshot, without advancing or inventing new particle motion.
export class ParcelMotion {
  constructor(capacity) {
    this.velocity = new Float32Array(capacity * 3);
    this.tick = new Float64Array(capacity).fill(-1);
    this.indices = new Int32Array(capacity);
  }
  attach(previous, frame) {
    this.indices.fill(-1);
    const before = previous?.grains;
    if (before)
      for (let n = 0; n < before.length; n += 4)
        this.indices[before[n] & 0xffff] = n;
    const output = (frame.velocities = new Float32Array(
      (frame.grains.length / 4) * 3,
    ));
    const q = SAND.positionQuantum;
    for (let n = 0; n < frame.grains.length; n += 4) {
      const slot = frame.grains[n] & 0xffff,
        m = this.indices[slot];
      if (m < 0) {
        this.forget(slot);
        continue;
      }
      this.between(
        slot,
        previous.tick,
        frame.tick,
        previous.origin[0] + before[m + 1] * q,
        previous.origin[1] + before[m + 2] * q,
        previous.origin[2] + before[m + 3] * q,
        frame.origin[0] + frame.grains[n + 1] * q,
        frame.origin[1] + frame.grains[n + 2] * q,
        frame.origin[2] + frame.grains[n + 3] * q,
      );
      output.set(this.velocity.subarray(slot * 3, slot * 3 + 3), (n / 4) * 3);
    }
  }
  between(slot, fromTick, toTick, ax, ay, az, bx, by, bz) {
    const dt = (toTick - fromTick) / 30;
    const dx = bx - ax,
      dy = by - ay,
      dz = bz - az;
    const valid = dt > 0 && dt <= 0.1 && dx * dx + dy * dy + dz * dz < 3600;
    const k = slot * 3;
    this.velocity[k] = valid ? dx / dt : 0;
    this.velocity[k + 1] = valid ? dy / dt : 0;
    this.velocity[k + 2] = valid ? dz / dt : 0;
    this.tick[slot] = toTick;
  }
  read(slot, tick, out) {
    const k = slot * 3,
      valid = Number.isFinite(tick) && this.tick[slot] === tick;
    out[0] = valid ? this.velocity[k] : 0;
    out[1] = valid ? this.velocity[k + 1] : 0;
    out[2] = valid ? this.velocity[k + 2] : 0;
  }
  forget(slot) {
    this.tick[slot] = -1;
  }
  clear() {
    this.tick.fill(-1);
  }
}

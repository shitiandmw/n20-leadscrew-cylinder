import { BUCKET, BUCKET_PROFILE } from "./world.js";

// Bucket local frame: x along the bucket, y lateral, z normal to both. The
// cavity is the closed polygon BUCKET_PROFILE; its last-to-first edge is the
// open mouth. The polygon is clockwise in (x, z), so the cavity lies to the
// right of each edge.
const P = BUCKET_PROFILE;
const LAST = P.length - 1;

function segment(a, b, inner = BUCKET.shellHalfThickness, outer = inner) {
  const dx = b[0] - a[0],
    dz = b[1] - a[1],
    length = Math.hypot(dx, dz);
  return {
    ax: a[0],
    az: a[1],
    dx,
    dz,
    len2: dx * dx + dz * dz,
    // Unit normal pointing into the cavity (right of a clockwise edge).
    nx: dz / length,
    nz: -dx / length,
    // Plate surfaces measured from the CAD mesh, relative to the centreline.
    inner,
    outer,
  };
}
// Shell walls and the tooth row ahead of the lip. The top plate is 4 mm; the
// back and floor plates of the CAD bucket are 6 mm, thickened inwards.
const INNER_SURFACE = [2, 2, 4.1, 4.1, 4.1, 3.5];
export const WALLS = P.slice(0, LAST).map((a, i) =>
  segment(a, P[i + 1], INNER_SURFACE[i], BUCKET.shellHalfThickness),
);
export const TEETH = segment(P[LAST], BUCKET.tip, 1.5);
// Region swept when cutting the sand bed: cavity plus the tooth triangle.
export const REGION = [...P, BUCKET.tip];
export const REGION_EDGE_MOUTH = REGION.length - 1; // tip -> P[0]
export const CENTROID = (() => {
  let ax = 0,
    az = 0;
  for (const [x, z] of P) {
    ax += x;
    az += z;
  }
  return [ax / P.length, az / P.length];
})();
export const BOUNDING_RADIUS = Math.max(
  ...REGION.map(([x, z]) => Math.hypot(x - CENTROID[0], z - CENTROID[1])),
);

export function insidePolygon(x, z) {
  let inside = false;
  for (let i = 0, j = LAST; i <= LAST; j = i++) {
    const a = P[i],
      b = P[j];
    if (
      a[1] > z !== b[1] > z &&
      x < ((b[0] - a[0]) * (z - a[1])) / (b[1] - a[1]) + a[0]
    )
      inside = !inside;
  }
  return inside;
}
export const insideCavity = (x, y, z) =>
  Math.abs(y) < BUCKET.cheekCentre && insidePolygon(x, z);

// A rigid bucket pose in the world: local x, y and z axes ex, ey and ez, at any
// chassis tilt. Matches toLocal/toWorld in physics.js and the Three.js bucket
// group (rotation.y = -pitch inside the tilted root group).
export class BucketFrame {
  constructor() {
    this.regionF = new Float64Array(REGION.length);
    this.regionZ = new Float64Array(REGION.length);
    this.ex = [1, 0, 0];
    this.ey = [0, 1, 0];
    this.ez = [0, 0, 1];
    this.centre = [0, 0, 0];
  }
  set(pose) {
    this.x = pose.x;
    this.y = pose.y;
    this.z = pose.z;
    this.yaw = pose.yaw;
    this.pitch = pose.pitch;
    const { ex, ey, ez } = pose;
    for (let d = 0; d < 3; d++) {
      this.ex[d] = ex[d];
      this.ey[d] = ey[d];
      this.ez[d] = ez[d];
    }
    // World "up" seen from the bucket. A vertical column is a straight line
    // along it, so these projections make column() cheap.
    this.upX = this.ex[2];
    this.upY = this.ey[2];
    this.upZ = this.ez[2];
    this.upArea = this.upX * this.upX + this.upZ * this.upZ;
    for (let k = 0; k < REGION.length; k++) {
      const [x, z] = REGION[k];
      this.regionF[k] = x * this.upZ - z * this.upX;
      this.regionZ[k] = x * this.upX + z * this.upZ;
    }
    this.toWorld(CENTROID[0], 0, CENTROID[1], this.centre);
    return this;
  }
  copy(other) {
    return this.set(other);
  }
  toLocal(x, y, z, out) {
    const dx = x - this.x,
      dy = y - this.y,
      dz = z - this.z,
      { ex, ey, ez } = this;
    out[0] = dx * ex[0] + dy * ex[1] + dz * ex[2];
    out[1] = dx * ey[0] + dy * ey[1] + dz * ey[2];
    out[2] = dx * ez[0] + dy * ez[1] + dz * ez[2];
    return out;
  }
  toWorld(x, y, z, out) {
    const { ex, ey, ez } = this;
    out[0] = this.x + x * ex[0] + y * ey[0] + z * ez[0];
    out[1] = this.y + x * ex[1] + y * ey[1] + z * ez[1];
    out[2] = this.z + x * ex[2] + y * ey[2] + z * ez[2];
    return out;
  }
  // Vertical extent of the cutting region above world column (x, y).
  // Writes [zLow, zHigh, lowIsMouth, highIsMouth]; returns false if missed.
  column(x, y, out) {
    const half = BUCKET.outerHalfWidth,
      dx = x - this.x,
      dy = y - this.y,
      { ex, ey, ez } = this,
      // The column's local position at world height z = this.z.
      ax = dx * ex[0] + dy * ex[1],
      ay = dx * ey[0] + dy * ey[1],
      az = dx * ez[0] + dy * ez[1],
      upY = this.upY;
    let tMin = -Infinity,
      tMax = Infinity;
    // Across the bucket: a tilted column can enter or leave through a cheek.
    if (Math.abs(upY) < 1e-9) {
      if (Math.abs(ay) > half) return false;
    } else {
      const a = (-half - ay) / upY,
        b = (half - ay) / upY;
      tMin = Math.min(a, b);
      tMax = Math.max(a, b);
    }
    const f = ax * this.upZ - az * this.upX,
      start = ax * this.upX + az * this.upZ,
      F = this.regionF,
      Z = this.regionZ,
      n = REGION.length;
    let low = Infinity,
      high = -Infinity,
      lowMouth = 0,
      highMouth = 0;
    for (let k = 0; k < n; k++) {
      const k1 = k + 1 === n ? 0 : k + 1,
        fa = F[k],
        fb = F[k1];
      if (fa > f === fb > f) continue;
      const z =
        (Z[k] + ((f - fa) / (fb - fa)) * (Z[k1] - Z[k]) - start) / this.upArea;
      const mouth = k === REGION_EDGE_MOUTH ? 1 : 0;
      if (z < low) {
        low = z;
        lowMouth = mouth;
      }
      if (z > high) {
        high = z;
        highMouth = mouth;
      }
    }
    if (low === Infinity) return false;
    if (low < tMin) {
      low = tMin;
      lowMouth = 0;
    }
    if (high > tMax) {
      high = tMax;
      highMouth = 0;
    }
    if (low >= high) return false;
    out[0] = this.z + low;
    out[1] = this.z + high;
    out[2] = lowMouth;
    out[3] = highMouth;
    return true;
  }
}

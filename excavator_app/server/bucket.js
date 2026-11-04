import { BUCKET, BUCKET_PROFILE } from "../shared/world.js";

// Bucket local frame: x along the bucket, y lateral, z normal to both. The
// cavity is the closed polygon BUCKET_PROFILE; its last-to-first edge is the
// open mouth. The polygon is clockwise in (x, z), so the cavity lies to the
// right of each edge.
const P = BUCKET_PROFILE;
const LAST = P.length - 1;
export const MOUTH = LAST; // edge index P[LAST] -> P[0]

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
const MOUTH_EDGE = segment(P[LAST], P[0]);
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

// Parameter t in [0, 1] where segment p0->p1 crosses edge e, or -1.
function crossEdge(p0x, p0z, p1x, p1z, e) {
  const rx = p1x - p0x,
    rz = p1z - p0z,
    den = rx * e.dz - rz * e.dx;
  if (Math.abs(den) < 1e-12) return -1;
  const qx = e.ax - p0x,
    qz = e.az - p0z,
    t = (qx * e.dz - qz * e.dx) / den,
    u = (qx * rz - qz * rx) / den;
  return t >= 0 && t <= 1 && u >= 0 && u <= 1 ? t : -1;
}

// How did a point travel from local a to local b relative to the bucket?
// Returns the first boundary it crossed: 0 none, 1 mouth, 2 wall, 3 cheek.
// `hit` receives [t, wall index, cheek sign].
export const CROSS_NONE = 0,
  CROSS_MOUTH = 1,
  CROSS_WALL = 2,
  CROSS_CHEEK = 3;
export function firstCrossing(a, b, hit) {
  let best = 2,
    type = CROSS_NONE;
  const dy = b[1] - a[1],
    half = BUCKET.cheekCentre;
  for (let k = 0; k <= LAST; k++) {
    const edge = k === LAST ? MOUTH_EDGE : WALLS[k],
      t = crossEdge(a[0], a[2], b[0], b[2], edge);
    if (t < 0 || t >= best || Math.abs(a[1] + dy * t) >= half) continue;
    best = t;
    type = k === LAST ? CROSS_MOUTH : CROSS_WALL;
    hit[1] = k;
  }
  for (const sign of [-1, 1]) {
    const plane = sign * half;
    if ((a[1] - plane) * (b[1] - plane) >= 0) continue;
    const t = (plane - a[1]) / dy;
    if (
      t < best &&
      insidePolygon(a[0] + (b[0] - a[0]) * t, a[2] + (b[2] - a[2]) * t)
    ) {
      best = t;
      type = CROSS_CHEEK;
      hit[2] = sign;
    }
  }
  hit[0] = best;
  return type;
}

// A rigid bucket pose with cached trigonometry. Matches toLocal/toWorld in
// physics.js and the Three.js bucket group (rotation.y = -pitch).
export class BucketFrame {
  constructor() {
    this.regionF = new Float64Array(REGION.length);
    this.regionZ = new Float64Array(REGION.length);
  }
  set(pose) {
    this.x = pose.x;
    this.y = pose.y;
    this.z = pose.z;
    this.yaw = pose.yaw;
    this.pitch = pose.pitch;
    this.cy = Math.cos(pose.yaw);
    this.sy = Math.sin(pose.yaw);
    this.cp = Math.cos(pose.pitch);
    this.sp = Math.sin(pose.pitch);
    for (let k = 0; k < REGION.length; k++) {
      const [x, z] = REGION[k];
      this.regionF[k] = x * this.cp - z * this.sp;
      this.regionZ[k] = x * this.sp + z * this.cp;
    }
    const [cx, cz] = CENTROID,
      f = cx * this.cp - cz * this.sp;
    this.centre = [
      this.x + f * this.cy,
      this.y + f * this.sy,
      this.z + cx * this.sp + cz * this.cp,
    ];
    return this;
  }
  copy(other) {
    return this.set(other);
  }
  toLocal(x, y, z, out) {
    const dx = x - this.x,
      dy = y - this.y,
      dz = z - this.z,
      f = dx * this.cy + dy * this.sy;
    out[0] = f * this.cp + dz * this.sp;
    out[1] = -dx * this.sy + dy * this.cy;
    out[2] = -f * this.sp + dz * this.cp;
    return out;
  }
  toWorld(x, y, z, out) {
    const f = x * this.cp - z * this.sp;
    out[0] = this.x + f * this.cy - y * this.sy;
    out[1] = this.y + f * this.sy + y * this.cy;
    out[2] = this.z + x * this.sp + z * this.cp;
    return out;
  }
  // Vertical extent of the cutting region above world column (x, y).
  // Writes [zLow, zHigh, lowIsMouth, highIsMouth]; returns false if missed.
  column(x, y, out) {
    const dx = x - this.x,
      dy = y - this.y,
      lateral = -dx * this.sy + dy * this.cy;
    if (Math.abs(lateral) > BUCKET.outerHalfWidth) return false;
    const f = dx * this.cy + dy * this.sy,
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
      const z = Z[k] + ((f - fa) / (fb - fa)) * (Z[k1] - Z[k]);
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
    out[0] = this.z + low;
    out[1] = this.z + high;
    out[2] = lowMouth;
    out[3] = highMouth;
    return true;
  }
}

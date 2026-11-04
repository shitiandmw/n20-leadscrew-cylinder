import { BUCKET, WORLD } from "../shared/world.js";
import { WALLS } from "../shared/bucket.js";

// A bounded reconstruction around the bucket. The lattice follows the bucket,
// so a resting load does not crawl across voxels when the arm moves. Outside
// this region sand is drawn as fine loose grains until it rejoins the bed.
export const SURFACE_CENTRE = [-20, 0, -36];
export const SURFACE_SIZE = 160;
export const SURFACE_LEVEL = 2.6;
const SUPPORT = WORLD.radius * 4;
const MARGIN = 0.35;

// The shell is convex; omit the mouth plane so the heap can rise above it.
// Limit the reconstructed load to the inside of the actual CAD plates. Loose
// grains beyond the cheeks/mouth still render independently.
export function loadClearance(x, y, z) {
  let distance = BUCKET.innerHalfWidth - Math.abs(y);
  for (const wall of WALLS)
    distance = Math.min(
      distance,
      (x - wall.ax) * wall.nx + (z - wall.az) * wall.nz - wall.inner,
    );
  return distance - MARGIN;
}

export class SandSurfaceField {
  constructor(resolution, field = new Float32Array(resolution ** 3)) {
    this.resolution = resolution;
    this.field = field;
    this.spacing = SURFACE_SIZE / resolution;
    this.origin = SURFACE_CENTRE.map((v) => v - SURFACE_SIZE / 2);
    this.limits = new Float32Array(field.length);
    const [ox, oy, oz] = this.origin,
      h = this.spacing;
    for (let z = 0; z < resolution; z++)
      for (let y = 0; y < resolution; y++)
        for (let x = 0; x < resolution; x++) {
          // min(density, wall distance) clips the iso-surface. The distance
          // is linear at each wall, so even a coarse lattice respects it.
          this.limits[x + resolution * (y + resolution * z)] =
            SURFACE_LEVEL +
            loadClearance(ox + x * h, oy + y * h, oz + z * h) / h;
        }
  }

  clear() {
    this.field.fill(0);
  }

  add(x, y, z, weight = 1) {
    if (weight <= 0 || loadClearance(x, y, z) < 0) return;
    const n = this.resolution,
      h = this.spacing,
      [ox, oy, oz] = this.origin;
    const x0 = Math.max(1, Math.ceil((x - SUPPORT - ox) / h)),
      x1 = Math.min(n - 2, Math.floor((x + SUPPORT - ox) / h)),
      y0 = Math.max(1, Math.ceil((y - SUPPORT - oy) / h)),
      y1 = Math.min(n - 2, Math.floor((y + SUPPORT - oy) / h)),
      z0 = Math.max(1, Math.ceil((z - SUPPORT - oz) / h)),
      z1 = Math.min(n - 2, Math.floor((z + SUPPORT - oz) / h));
    for (let k = z0; k <= z1; k++) {
      const dz2 = (oz + k * h - z) ** 2;
      for (let j = y0; j <= y1; j++) {
        const dyz2 = (oy + j * h - y) ** 2 + dz2;
        for (let i = x0; i <= x1; i++) {
          const q = 1 - ((ox + i * h - x) ** 2 + dyz2) / SUPPORT ** 2;
          if (q > 0) this.field[i + n * (j + n * k)] += weight * q * q * q;
        }
      }
    }
  }

  finish() {
    // One isolated parcel peaks at 1, below the iso-level: it never produces
    // a big bead. Several overlapping neighbours form a continuous heap.
    for (let i = 0; i < this.field.length; i++)
      this.field[i] = Math.min(this.field[i], this.limits[i]);
  }
}

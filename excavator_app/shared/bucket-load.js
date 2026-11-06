import { BUCKET, BUCKET_PROFILE, SAND } from "./world.js";
import { WALLS } from "./bucket.js";

// The sand in a bucket is a small height field fixed to the bucket, shared by the
// server and the browser. Its axes are the bucket's mouth:
//   u  along the mouth, from the lip towards the far rim,
//   y  across the bucket, between the cheek plates,
//   w  out of the mouth, so w = 0 is the plane of the rims.
// Every column runs from the inner surface of the plates (its floor) up to the
// sand's surface. Columns past the far rim end under the top plate (their ceiling).
const lip = BUCKET_PROFILE[BUCKET_PROFILE.length - 1],
  rim = BUCKET_PROFILE[0],
  LENGTH = Math.hypot(rim[0] - lip[0], rim[1] - lip[1]),
  UX = (rim[0] - lip[0]) / LENGTH,
  UZ = (rim[1] - lip[1]) / LENGTH,
  WX = -UZ,
  WZ = UX;

// From mouth axes to the bucket's local (x, y, z), and back.
export function mouthToLocal(u, y, w, out) {
  out[0] = lip[0] + u * UX + w * WX;
  out[1] = y;
  out[2] = lip[1] + u * UZ + w * WZ;
  return out;
}
export const localU = (x, z) => (x - lip[0]) * UX + (z - lip[1]) * UZ;
export const localW = (x, z) => (x - lip[0]) * WX + (z - lip[1]) * WZ;
// World "up" seen in mouth axes, from its components in the bucket's frame.
export const upAlongU = (upX, upZ) => upX * UX + upZ * UZ;
export const upAlongW = (upX, upZ) => upX * WX + upZ * WZ;

// Each plate's inner surface as a line in (u, w). The plates face into the cavity,
// so one with a normal towards +w is a floor and one towards -w is a ceiling.
const PLATES = WALLS.map((wall) => {
  const normalU = wall.nx * UX + wall.nz * UZ,
    normalW = wall.nx * WX + wall.nz * WZ,
    startU = localU(wall.ax, wall.az),
    startW = localW(wall.ax, wall.az),
    endU = localU(wall.ax + wall.dx, wall.az + wall.dz);
  return {
    height: (u) =>
      startW + (wall.inner - (u - startU) * normalU) / normalW,
    isFloor: normalW > 0,
    // Where this plate's inner surface begins along the mouth.
    from: Math.min(startU, endU) + normalU * wall.inner,
  };
});
const floorAt = (u) =>
  Math.max(...PLATES.filter((p) => p.isFloor).map((p) => p.height(u)));
const ceilingAt = (u) =>
  Math.min(
    Infinity,
    ...PLATES.filter((p) => !p.isFloor && u >= p.from).map((p) => p.height(u)),
  );

// The cavity ends where its floor meets its ceiling.
let reach = LENGTH;
while (floorAt(reach + 0.1) < ceilingAt(reach + 0.1)) reach += 0.1;

const NU = 22,
  NV = 15,
  DU = reach / NU,
  DV = (2 * BUCKET.innerHalfWidth) / NV,
  AREA = DU * DV,
  columnU = (i) => (i + 0.5) * DU;
const floors = Float64Array.from({ length: NU }, (_, i) => floorAt(columnU(i))),
  ceilings = Float64Array.from({ length: NU }, (_, i) =>
    ceilingAt(columnU(i)),
  );
// The last column open to the sky: past it, the top plate covers the cavity.
const lastOpen = ceilings.findIndex((value) => value !== Infinity) - 1;
// The cavity filled level with the rims.
const struck =
  floors.reduce(
    (sum, floor, i) => sum + Math.max(0, Math.min(0, ceilings[i]) - floor),
    0,
  ) *
  AREA *
  NV;

export const LOAD = Object.freeze({
  nu: NU,
  nv: NV,
  cells: NU * NV,
  du: DU,
  dv: DV,
  area: AREA,
  length: LENGTH,
  halfWidth: BUCKET.innerHalfWidth,
  columnU,
  rowY: (j) => (j + 0.5) * DV - BUCKET.innerHalfWidth,
  floors,
  ceilings,
  lastOpen,
  floorAt,
  ceilingAt,
  struck,
  // A heap on top of a struck load, at the angle of repose, holds about 50 cm3.
  capacity: struck + 50000,
  // Network quantisation of column thickness, the same as the sand bed's.
  quantum: SAND.heightQuantum,
});

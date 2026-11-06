import { CONFIG } from "./config.js";

// Model and simulation use X forward, Y left, Z up, in millimetres. The world
// is 40.96 m square: about 600 m at the machine's 1:15 scale.
const HALF = 20480;
export const WORLD = Object.freeze({
  minX: -HALF,
  maxX: HALF,
  minY: -HALF,
  maxY: HALF,
  // Radius of a parcel of falling sand (a clump at 1:15 scale).
  radius: 4,
  gravity: 9810,
});
export const AXES = [
  "boom",
  "stick",
  "bucket",
  "slew",
  "leftTrack",
  "rightTrack",
];
export const neutral = () => Object.fromEntries(AXES.map((key) => [key, 0]));
export const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

// Sand anywhere in the world is a cell-centred height field of sand thickness
// above the hard ground. Each bucket carries a small height field of its own
// (bucket-load.js), and sand in the air falls as parcels. Storage is sparse: only
// pages that have held sand exist.
const CELL = 10;
const GRAIN_PACKING = 0.6;
export const SAND = Object.freeze({
  cell: CELL,
  nx: (2 * HALF) / CELL,
  ny: (2 * HALF) / CELL,
  // Network tiles and storage pages, in cells per side.
  tile: 16,
  tilesX: (2 * HALF) / CELL / 16,
  tilesY: (2 * HALF) / CELL / 16,
  page: 64,
  // Network quantisation: Uint16 sand thickness (up to 1.3 m) and Int16 parcel
  // positions relative to the frame origin.
  heightQuantum: 0.02,
  positionQuantum: 0.1,
  // Bulk (not solid) volume of one parcel of falling sand: a sphere at random
  // loose packing.
  grainVolume: ((4 / 3) * Math.PI * WORLD.radius ** 3) / GRAIN_PACKING,
  // Dry sand: the bed relaxes to its angle of repose.
  reposeDeg: 34,
  maxGrains: 6000,
});
export const cellX = (i) => WORLD.minX + (i + 0.5) * CELL;
export const cellY = (j) => WORLD.minY + (j + 0.5) * CELL;

// The sand yard: 6.4 m x 6.4 m of deep sand (96 m square at full scale), level
// with the ground around it. The north-west notch keeps the pad and the machine's
// starting place on hard ground.
export const YARD = Object.freeze({
  minX: 170,
  maxX: 6570,
  minY: -3200,
  maxY: 3200,
  notchMaxX: 700,
  notchMinY: 150,
  // The hard floor under the sand drops this far over `ramp` from the edge.
  depth: 220,
  ramp: 320,
});

// Sand reaching this marked hard pad counts as delivered.
export const POUR_ZONE = Object.freeze({
  minX: 260,
  maxX: 620,
  minY: 220,
  maxY: 490,
});

// Include the whole crawler footprint when turning near the map edge.
export function crawlerExtent(heading) {
  const halfLength =
    CONFIG.wheel_centres / 2 + CONFIG.sprocket_tip_radius_mm + 10;
  const halfWidth = CONFIG.track_outer_width_mm / 2;
  const c = Math.abs(Math.cos(heading)),
    s = Math.abs(Math.sin(heading));
  return {
    x: halfLength * c + halfWidth * s,
    y: halfLength * s + halfWidth * c,
  };
}

// Crawlers keep this far apart: their footprint, with room at the ends for the
// upper body's rear corners as they swing past the tracks.
const SEPARATION_LENGTH =
    CONFIG.wheel_centres / 2 + CONFIG.sprocket_tip_radius_mm + 30,
  SEPARATION_WIDTH = CONFIG.track_outer_width_mm / 2 + 10,
  SEPARATION_REACH = 2 * Math.hypot(SEPARATION_LENGTH, SEPARATION_WIDTH);

// Separating-axis test between two crawler footprints, seen from above.
export function crawlersOverlap(a, b) {
  const dx = b.x - a.x,
    dy = b.y - a.y;
  if (dx * dx + dy * dy > SEPARATION_REACH * SEPARATION_REACH) return false;
  const ca = Math.cos(a.heading),
    sa = Math.sin(a.heading),
    cb = Math.cos(b.heading),
    sb = Math.sin(b.heading),
    ac = Math.abs(ca * cb + sa * sb),
    as = Math.abs(sb * ca - cb * sa),
    alongReach =
      SEPARATION_LENGTH + SEPARATION_LENGTH * ac + SEPARATION_WIDTH * as,
    acrossReach =
      SEPARATION_WIDTH + SEPARATION_LENGTH * as + SEPARATION_WIDTH * ac;
  return !(
    Math.abs(dx * ca + dy * sa) > alongReach ||
    Math.abs(-dx * sa + dy * ca) > acrossReach ||
    Math.abs(dx * cb + dy * sb) > alongReach ||
    Math.abs(-dx * sb + dy * cb) > acrossReach
  );
}

export const initialMachine = () => ({
  strokes: [10, 0, 0],
  slew: 0,
  x: 0,
  y: 0,
  z: 0,
  heading: 0,
  pitch: 0,
  roll: 0,
  tracks: [0, 0],
});

// World directions of the chassis axes. Pitch is positive nose up and roll is
// positive with the +Y side up: R = Rz(heading) Ry(-pitch) Rx(roll), the same
// rotation as the Three.js root group with Euler order ZYX.
export function chassisAxes(machine) {
  const ch = Math.cos(machine.heading),
    sh = Math.sin(machine.heading),
    cp = Math.cos(machine.pitch ?? 0),
    sp = Math.sin(machine.pitch ?? 0),
    cr = Math.cos(machine.roll ?? 0),
    sr = Math.sin(machine.roll ?? 0);
  return {
    forward: [ch * cp, sh * cp, sp],
    left: [-ch * sp * sr - sh * cr, -sh * sp * sr + ch * cr, cp * sr],
    up: [-ch * sp * cr + sh * sr, -sh * sp * cr - ch * sr, cp * cr],
  };
}

// Rigid frame of a part hinged in the arm plane, `reach` ahead of the slew axis
// and `height` above the chassis base, turned `angle` in the arm plane. Local
// x runs along the part, y across the arm and z is normal to both. The frame
// stays exact when the chassis is tilted on a slope.
export function armFrame(machine, reach, height, angle) {
  const { forward, left, up } = chassisAxes(machine),
    s = (machine.slew * Math.PI) / 180,
    cs = Math.cos(s),
    ss = Math.sin(s),
    cq = Math.cos(angle),
    sq = Math.sin(angle),
    along = [0, 1, 2].map((d) => cs * forward[d] + ss * left[d]),
    across = [0, 1, 2].map((d) => -ss * forward[d] + cs * left[d]);
  return {
    x: machine.x + along[0] * reach + up[0] * height,
    y: machine.y + along[1] * reach + up[1] * height,
    z: (machine.z ?? 0) + along[2] * reach + up[2] * height,
    yaw: machine.heading + s,
    pitch: angle,
    ex: [0, 1, 2].map((d) => cq * along[d] + sq * up[d]),
    ey: across,
    ez: [0, 1, 2].map((d) => -sq * along[d] + cq * up[d]),
  };
}

// Centreline of the 4 mm shell in build_arm.py, with its original 0.8 scale.
// The final-to-first edge is the OPEN mouth; do not collide with it.
export const BUCKET_PROFILE = [
  [-7, -22],
  [30, -24],
  [56, -42],
  [55, -73],
  [30, -96],
  [-28, -102],
  [-89, -77],
].map((p) => p.map((v) => v * 0.8));
// Dimensions of the CAD bucket (06_inward_digging_bucket) in its local frame.
export const BUCKET = Object.freeze({
  // Tooth tips ahead of the lip, from the original arm configuration.
  tip: CONFIG.arm.tip,
  shellHalfThickness: 2,
  // Cheek plates span |y| 36.5..40 mm.
  innerHalfWidth: 36.5,
  outerHalfWidth: 40,
  cheekCentre: 38.25,
  // Struck capacity inside the plates (cm^3), the 100 % mark of the load meter.
  ratedLoad: 300,
});

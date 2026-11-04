import { CONFIG } from "./config.js";

// Model and simulation use X forward, Y left/right, Z up, in millimetres.
export const WORLD = Object.freeze({
  minX: -550,
  maxX: 1000,
  minY: -570,
  maxY: 570,
  floor: -75,
  platformEdge: 190,
  rampEnd: 310,
  // Radius of one simulated loose-sand grain (a clump at 1:15 scale).
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
export const groundHeight = (x) =>
  WORLD.floor *
    clamp(
      (x - WORLD.platformEdge) / (WORLD.rampEnd - WORLD.platformEdge),
      0,
      1,
    ) || 0;
// Slope dz/dx of the concrete apron, ramp and pit floor.
export const groundSlope = (x) =>
  x > WORLD.platformEdge && x < WORLD.rampEnd
    ? WORLD.floor / (WORLD.rampEnd - WORLD.platformEdge)
    : 0;

// Sand bed: a cell-centred height field of sand thickness above the concrete,
// plus free grains for material that is moving, carried or falling.
const CELL = 10;
const GRAIN_PACKING = 0.6;
export const SAND = Object.freeze({
  cell: CELL,
  nx: (WORLD.maxX - WORLD.minX) / CELL,
  ny: (WORLD.maxY - WORLD.minY) / CELL,
  tile: 16,
  tilesX: Math.ceil((WORLD.maxX - WORLD.minX) / CELL / 16),
  tilesY: Math.ceil((WORLD.maxY - WORLD.minY) / CELL / 16),
  // Network quantisation: Uint16 sand thickness and Int16 grain positions.
  heightQuantum: 0.01,
  positionQuantum: 0.1,
  // Bulk (not solid) volume represented by one grain: a sphere at random
  // loose packing. Converting between grains and the bed conserves it.
  grainVolume: ((4 / 3) * Math.PI * WORLD.radius ** 3) / GRAIN_PACKING,
  // Dry sand: the bed relaxes to its angle of repose.
  reposeDeg: 34,
  maxGrains: 6000,
});
export const cellX = (i) => WORLD.minX + (i + 0.5) * CELL;
export const cellY = (j) => WORLD.minY + (j + 0.5) * CELL;

// Material reaching the marked receiving area counts as deposited.
export const POUR_ZONE = Object.freeze({
  minX: 260,
  maxX: 620,
  minY: 220,
  maxY: 490,
});

// Include the whole crawler footprint when turning near the map walls.
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

export const initialMachine = () => ({
  strokes: [10, 0, 0],
  slew: 0,
  x: 0,
  y: 0,
  z: 0,
  heading: 0,
  tracks: [0, 0],
});
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

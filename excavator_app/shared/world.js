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
  radius: 6,
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

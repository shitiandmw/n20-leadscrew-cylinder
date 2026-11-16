import { clamp, chassisAxes } from "./world.js";

// The dump truck: a real 6x4 rigid tipper at the excavator's 1:15, so that its
// body is the size the R12 arm would really load. Sources, at full scale:
//
// - Chassis and cab: Volvo Trucks model range sheet "FMX13 6x4 Rigid - B/T Ride",
//   FMX 64R 3L (GBR, 2026-09-25). 1520 mm from the front of the bumper to the
//   front axle; the Day cab's back 515 mm behind the front axle; the 3700 mm
//   wheelbase, one of 3400 to 5600; 1370 mm between the rear axles; a frame
//   1111 mm high (CHH-HIGH); the Day cab 3144 mm high and 2500 mm wide;
//   315/80R22.5 tyres on every axle; a 15 500 mm turning circle kerb to kerb at
//   that wheelbase. The side and front views on its first page give the cab's
//   outline.
// - Body: Schwarzmüller "3-way tipper body for 3A truck - building site".
//   5100 x 2420 mm inside, 2550 mm wide over all, a 980 mm front wall, 880 mm
//   side walls and a 980 mm rear wall that swings from raised upper bearings;
//   about 440 mm of body height over the frame; about 11 m³; tips back to about 49°.
//
// Assumed, where neither says: 100 mm between the cab and the body, 60 mm thick
// walls (the side walls' aluminium profile is 60 mm), 2050 mm between the front
// wheels and 1830 mm between the middles of the rear twin tyres, set 350 mm
// apart, and the rear pivot 100 mm ahead of the inside of the rear wall, 120 mm
// over the frame.
const SCALE = 15,
  mm = (full) => full / SCALE,
  RAD = Math.PI / 180;
const FULL = Object.freeze({
  frontOverhang: 1520,
  cabBack: 515,
  wheelbase: 3700,
  tandem: 1370,
  frame: 1111,
  cabHeight: 3144,
  cabWidth: 2500,
  rim: 22.5 * 25.4,
  tyreWidth: 315,
  tyreAspect: 0.8,
  turningCircle: 15500,
  trackFront: 2050,
  trackRear: 1830,
  twinSpacing: 350,
  bodyGap: 100,
  innerLength: 5100,
  innerWidth: 2420,
  outerWidth: 2550,
  frontWall: 980,
  sideWall: 880,
  rearWall: 980,
  wall: 60,
  bodyHeight: 440,
  pivotAhead: 100,
  pivotOverFrame: 120,
  tipDeg: 49,
});

// The truck's own frame: x forward, y left, z up, in mm, with its origin on the
// ground under the middle of the rear tandem. That is where a truck turns about,
// so the kinematics are simplest there.
const tyreDiameter = FULL.rim + 2 * FULL.tyreAspect * FULL.tyreWidth,
  theoretical = FULL.wheelbase + FULL.tandem / 2,
  frontAxle = mm(theoretical),
  bodyFront = mm(theoretical - FULL.cabBack - FULL.bodyGap),
  innerFront = bodyFront - mm(FULL.wall),
  innerRear = innerFront - mm(FULL.innerLength),
  floor = mm(FULL.frame + FULL.bodyHeight);

export const TRUCK = Object.freeze({
  full: FULL,
  scale: SCALE,
  frontAxle,
  rearAxles: Object.freeze([mm(FULL.tandem / 2), -mm(FULL.tandem / 2)]),
  // From the front axle to the middle of the tandem: the wheelbase a truck with
  // two rear axles steers by.
  wheelbase: frontAxle,
  bumper: mm(theoretical + FULL.frontOverhang),
  cabBack: mm(theoretical - FULL.cabBack),
  cabHalfWidth: mm(FULL.cabWidth / 2),
  cabHeight: mm(FULL.cabHeight),
  frame: mm(FULL.frame),
  tyreRadius: mm(tyreDiameter / 2),
  tyreWidth: mm(FULL.tyreWidth),
  rimRadius: mm(FULL.rim / 2),
  // Wheel centres stand at the loaded radius over the ground (the drawing's 535 mm).
  axleHeight: mm(535),
  frontTrack: mm(FULL.trackFront) / 2,
  rearTrack: mm(FULL.trackRear) / 2,
  twinHalf: mm(FULL.twinSpacing) / 2,
  // The body: outside faces, then the space inside it.
  bodyFront,
  bodyRear: innerRear - mm(FULL.wall),
  bodyHalfWidth: mm(FULL.outerWidth / 2),
  innerFront,
  innerRear,
  innerLength: mm(FULL.innerLength),
  innerHalfWidth: mm(FULL.innerWidth / 2),
  wall: mm(FULL.wall),
  floor,
  frontWall: mm(FULL.frontWall),
  sideWall: mm(FULL.sideWall),
  rearWall: mm(FULL.rearWall),
  // The body tips about this line across the truck, at the rear of the frame.
  pivotX: innerRear + mm(FULL.pivotAhead),
  pivotZ: mm(FULL.frame + FULL.pivotOverFrame),
  maxTip: FULL.tipDeg * RAD,
});

// The steering angle of a bicycle with the truck's wheelbase that drives the
// outer front tyre round the sheet's turning circle: about 40 degrees.
const kerb = mm(FULL.turningCircle) / 2 - TRUCK.tyreWidth / 2,
  rearRadius =
    Math.sqrt(kerb * kerb - TRUCK.wheelbase * TRUCK.wheelbase) - TRUCK.frontTrack;
export const MAX_STEER = Math.atan(TRUCK.wheelbase / rearRadius);

// How the truck moves. Its top speed, acceleration and the body's raise and
// lower rates are a game's, as the excavator's tracks and slew are; at 1:15,
// 650 mm/s is about 35 km/h.
export const TRUCK_DRIVE = Object.freeze({
  topSpeed: 650,
  reverseSpeed: 220,
  // With the body raised the truck only creeps, to spread what it tips.
  raisedSpeed: 120,
  raisedFrom: 3 * RAD,
  accelerate: 300,
  brake: 900,
  steerRate: 60 * RAD,
  raiseRate: 4 * RAD,
  lowerRate: 6 * RAD,
  // A loaded rigid truck climbs far less than a crawler.
  maxTilt: 25 * RAD,
});

// The footprint the truck keeps clear of scenery and other machines: from the
// back of the body to the bumper, as wide as the body. Its centre lies this far
// ahead of the truck's origin.
export const TRUCK_FOOTPRINT = Object.freeze({
  centre: (TRUCK.bumper + TRUCK.bodyRear) / 2,
  halfLength: (TRUCK.bumper - TRUCK.bodyRear) / 2,
  halfWidth: TRUCK.bodyHalfWidth,
});

// The tyres, as [x, y] of each tyre's middle in the truck's frame: the two front
// tyres, then the twin tyres of both rear axles.
export const TYRES = Object.freeze(
  [
    [frontAxle, TRUCK.frontTrack],
    [frontAxle, -TRUCK.frontTrack],
    ...TRUCK.rearAxles.flatMap((x) =>
      [1, -1].flatMap((side) => [
        [x, side * (TRUCK.rearTrack + TRUCK.twinHalf)],
        [x, side * (TRUCK.rearTrack - TRUCK.twinHalf)],
      ]),
    ),
  ].map(Object.freeze),
);
// Where the truck stands on the ground: under each front tyre and under the
// middle of each pair of twins.
export const WHEEL_SAMPLES = Object.freeze(
  [
    [frontAxle, TRUCK.frontTrack],
    [frontAxle, -TRUCK.frontTrack],
    ...TRUCK.rearAxles.flatMap((x) => [
      [x, TRUCK.rearTrack],
      [x, -TRUCK.rearTrack],
    ]),
  ].map(Object.freeze),
);

export const initialTruck = () => ({
  x: 0,
  y: 0,
  z: 0,
  heading: 0,
  pitch: 0,
  roll: 0,
  // The steering angle of the front wheels (radians, + to the left), the speed
  // along the heading (mm/s, + forward), the body's angle over the frame
  // (radians) and how far the wheels have rolled (mm), for drawing them.
  steer: 0,
  velocity: 0,
  tip: 0,
  wheels: 0,
});

// The controls the truck answers to. On the excavator they are not used.
export const TRUCK_AXES = ["drive", "steer", "hoist"];

// The sand in the body: a height field of columns on the floor, in the body's own
// frame, with x from the inside of the rear wall forward, y across and z up from
// the floor. Columns are 10 mm along and about 10 mm across, the bed's cells.
const NU = 34,
  NV = 16,
  DU = TRUCK.innerLength / NU,
  DV = (2 * TRUCK.innerHalfWidth) / NV;
export const TRUCK_LOAD = Object.freeze({
  nu: NU,
  nv: NV,
  cells: NU * NV,
  du: DU,
  dv: DV,
  area: DU * DV,
  length: TRUCK.innerLength,
  halfWidth: TRUCK.innerHalfWidth,
  // Network quantisation of a column's thickness (mm).
  quantum: 0.02,
  // Filled level with the side walls (mm³): about 3.2 litres, 11 m³ at full scale.
  struck: TRUCK.innerLength * 2 * TRUCK.innerHalfWidth * TRUCK.sideWall,
  columnX: (i) => (i + 0.5) * DU,
  rowY: (j) => (j + 0.5) * DV - TRUCK.innerHalfWidth,
});

// Where the body's frame is in the truck's: its origin on the floor at the inside
// of the rear wall, turned `tip` up about the pivot. Writes [x, z, cos, sin].
export function bodyInTruck(tip, out = new Float64Array(4)) {
  const c = Math.cos(tip),
    s = Math.sin(tip),
    dx = TRUCK.innerRear - TRUCK.pivotX,
    dz = TRUCK.floor - TRUCK.pivotZ;
  out[0] = TRUCK.pivotX + dx * c - dz * s;
  out[1] = TRUCK.pivotZ + dx * s + dz * c;
  out[2] = c;
  out[3] = s;
  return out;
}

const IN_TRUCK = new Float64Array(4);
// The body's frame in the world, for a truck pose: the same form as a bucket's
// pose (an origin and three axes), so a TruckFrame can take it.
export function bodyPose(truck, out) {
  const { forward: f, left: l, up: u } = chassisAxes(truck),
    [bx, bz, c, s] = bodyInTruck(truck.tip, IN_TRUCK);
  out.x = truck.x + f[0] * bx + u[0] * bz;
  out.y = truck.y + f[1] * bx + u[1] * bz;
  out.z = truck.z + f[2] * bx + u[2] * bz;
  for (let d = 0; d < 3; d++) {
    out.ex[d] = f[d] * c + u[d] * s;
    out.ey[d] = l[d];
    out.ez[d] = -f[d] * s + u[d] * c;
  }
  return out;
}

// The body's frame in the world, with conversions both ways.
export class TruckFrame {
  constructor() {
    this.x = this.y = this.z = 0;
    this.ex = [1, 0, 0];
    this.ey = [0, 1, 0];
    this.ez = [0, 0, 1];
    this.centre = [0, 0, 0];
  }
  set(pose) {
    this.x = pose.x;
    this.y = pose.y;
    this.z = pose.z;
    for (let d = 0; d < 3; d++) {
      this.ex[d] = pose.ex[d];
      this.ey[d] = pose.ey[d];
      this.ez[d] = pose.ez[d];
    }
    this.toWorld(TRUCK.innerLength / 2, 0, TRUCK.sideWall / 2, this.centre);
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
}
export const freshBodyPose = () => ({
  x: 0,
  y: 0,
  z: 0,
  ex: [1, 0, 0],
  ey: [0, 1, 0],
  ez: [0, 0, 1],
});

// The rear wall hangs from its upper bearings. Latched while the body is down, it
// swings free once the body lifts and hangs plumb, opening at the bottom by as
// much as the body leans back. Returns its angle out from the body (radians).
export const GATE_LATCH = 0.5 * RAD;
export function gateAngle(truck) {
  if (truck.tip <= GATE_LATCH) return 0;
  const { forward } = chassisAxes(truck),
    lean = Math.asin(clamp(forward[2], -1, 1)) + truck.tip;
  return clamp(lean, 0, 70 * RAD);
}

// The truck's footprint as a box for overlap tests: centre, direction and half
// sizes, with `margin` added all round.
export function truckBox(truck, margin = 0) {
  const c = Math.cos(truck.heading),
    s = Math.sin(truck.heading);
  return {
    x: truck.x + c * TRUCK_FOOTPRINT.centre,
    y: truck.y + s * TRUCK_FOOTPRINT.centre,
    c,
    s,
    halfLength: TRUCK_FOOTPRINT.halfLength + margin,
    halfWidth: TRUCK_FOOTPRINT.halfWidth + margin,
  };
}

// Separating-axis test between two boxes seen from above.
export function boxesOverlap(a, b) {
  const dx = b.x - a.x,
    dy = b.y - a.y,
    reach =
      Math.hypot(a.halfLength, a.halfWidth) + Math.hypot(b.halfLength, b.halfWidth);
  if (dx * dx + dy * dy > reach * reach) return false;
  const cos = Math.abs(a.c * b.c + a.s * b.s),
    sin = Math.abs(a.s * b.c - a.c * b.s);
  return !(
    Math.abs(dx * a.c + dy * a.s) >
      a.halfLength + b.halfLength * cos + b.halfWidth * sin ||
    Math.abs(-dx * a.s + dy * a.c) >
      a.halfWidth + b.halfLength * sin + b.halfWidth * cos ||
    Math.abs(dx * b.c + dy * b.s) >
      b.halfLength + a.halfLength * cos + a.halfWidth * sin ||
    Math.abs(-dx * b.s + dy * b.c) >
      b.halfWidth + a.halfLength * sin + a.halfWidth * cos
  );
}

// How far the truck's footprint reaches from its origin along x and y at a
// heading, so it can be kept on the map.
export function truckExtent(heading) {
  const c = Math.cos(heading),
    s = Math.sin(heading),
    { centre, halfLength, halfWidth } = TRUCK_FOOTPRINT;
  let x = 0,
    y = 0;
  for (const along of [centre - halfLength, centre + halfLength])
    for (const across of [-halfWidth, halfWidth]) {
      x = Math.max(x, Math.abs(along * c - across * s));
      y = Math.max(y, Math.abs(along * s + across * c));
    }
  return { x, y };
}

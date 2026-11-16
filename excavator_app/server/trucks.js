import {
  WORLD,
  SAND,
  clamp,
  neutral,
  cellX,
  cellY,
  crawlerBox,
} from "../shared/world.js";
import {
  WATER,
  crawlerHitsProp,
  groundHeight,
  yardInside,
} from "../shared/landscape.js";
import {
  TRUCK,
  TRUCK_DRIVE,
  TRUCK_FOOTPRINT,
  TRUCK_LOAD,
  TRUCK_AXES,
  MAX_STEER,
  WHEEL_SAMPLES,
  TruckFrame,
  bodyPose,
  freshBodyPose,
  gateAngle,
  truckBox,
  boxesOverlap,
  truckExtent,
} from "../shared/truck.js";
import { TruckLoad, RIM_REAR, RIM_FRONT, RIM_LEFT } from "./truck-load.js";

const { nx: NX, ny: NY, cell: CELL } = SAND,
  R = WORLD.radius,
  DEG = 180 / Math.PI,
  // The chassis follows the ground as the crawler's does.
  TILT_TIME = 0.14,
  RISE_RATE = 700,
  FALL_RATE = 450,
  // Loose sand gives this far under a tyre the first time it is driven over (mm).
  TYRE_SINK = 4,
  // Deeper water than this over the ground stops the truck (mm).
  WADE_DEPTH = 40,
  // A tyre presses the sand over this length of its tread at a time (mm): more
  // than the truck moves in a substep at full speed.
  PATCH = 8,
  // How high the underside stands over the ground (mm): between the axles, under
  // the bumper, and under the body behind the rear axle.
  BELLY = 18,
  NOSE = 28,
  TAIL = 70,
  // Sand leaves over a rim at this speed (mm/s), sliding, before it falls.
  SPILL_SPEED = 90,
  // Pushed-aside sand lands over a disc this wide (mm).
  SPREAD = 28,
  // Within this distance of the body's centre a falling parcel may land in it.
  NEAR = Math.hypot(TRUCK.innerLength / 2, TRUCK.innerHalfWidth, TRUCK.sideWall) + 40,
  // A parcel caught this far under the floor still lands in the body: no parcel
  // falls further than this in a substep.
  UNDER_FLOOR = 30,
  // The rear wall's bearings stand this far over the floor (mm).
  GATE_HINGE = TRUCK.rearWall + 2;

// The plane through the wheels' footing, z = a + b u + c v, by least squares.
// The samples are symmetric across the truck, so it splits into two small fits.
const SAMPLE_COUNT = WHEEL_SAMPLES.length,
  SUM_U = WHEEL_SAMPLES.reduce((sum, [u]) => sum + u, 0),
  SUM_UU = WHEEL_SAMPLES.reduce((sum, [u]) => sum + u * u, 0),
  SUM_VV = WHEEL_SAMPLES.reduce((sum, [, v]) => sum + v * v, 0),
  DETERMINANT = SAMPLE_COUNT * SUM_UU - SUM_U * SUM_U;

// One dump truck: its controls, its pose, the frame of its body and the sand in it.
export class Truck {
  constructor(id, pose) {
    this.id = id;
    this.home = structuredClone(pose);
    this.frame = new TruckFrame();
    this.prevFrame = new TruckFrame();
    this.body = freshBodyPose();
    this.load = new TruckLoad();
    this.poseVersion = 0;
    this.restart();
  }

  restart(pose = this.home) {
    this.pose = structuredClone(pose);
    this.axes = neutral();
    this.speed = 0.65;
    this.estop = false;
    this.obstacle = null;
    this.drove = false;
    this.busy = false;
    this.chassisMoving = false;
    this.hauled = 0;
    this.stats = truckStats(this);
    this.load.clear();
    this.frame.set(bodyPose(this.pose, this.body));
    this.prevFrame.copy(this.frame);
  }
}

const truckStats = (t) => ({
  load: Math.round(t.load.total / 100) / 10,
  tip: Math.round(t.pose.tip * DEG * 10) / 10,
  velocity: Math.round(t.pose.velocity),
  steer: Math.round(t.pose.steer * DEG),
  gate: gateAngle(t.pose) > 0,
  hauled: Math.round(t.hauled / 100) / 10,
  obstacle: t.obstacle,
});
export { truckStats };

// The trucks' part of the simulation. Each function takes the SandSimulation,
// which owns the bed, the falling sand and every machine.
//
// The footing under each wheel, and the plane through it. A truck standing still
// does not ride up on sand that runs in under its tyres, as the dumped load does:
// given its pose, only the hard ground can lift it.
export function fitTruck(sim, x, y, heading, out, standing = null) {
  const t = sim.terrain,
    s = sim.surf,
    ch = Math.cos(heading),
    sh = Math.sin(heading),
    b = standing ? Math.tan(standing.pitch) : 0,
    c = standing ? Math.tan(standing.roll) / Math.cos(standing.pitch) : 0;
  let sumH = 0,
    sumUH = 0,
    sumVH = 0;
  for (let n = 0; n < SAMPLE_COUNT; n++) {
    const [u, v] = WHEEL_SAMPLES[n],
      px = x + u * ch - v * sh,
      py = y + u * sh + v * ch,
      cell = t.cellAt(px, py),
      sand = t.get(cell);
    t.sample(px, py, s);
    let height =
      s[0] - (sand > 0.5 && !t.pressed(cell) ? Math.min(sand, TYRE_SINK) : 0);
    if (standing)
      height = Math.max(
        groundHeight(px, py),
        Math.min(height, standing.z + b * u + c * v),
      );
    out.h[n] = height;
    sumH += height;
    sumUH += u * height;
    sumVH += v * height;
  }
  out.b = (SAMPLE_COUNT * sumUH - SUM_U * sumH) / DETERMINANT;
  out.c = sumVH / SUM_VV;
  return out;
}

// Rest the truck on its wheels: the tilt follows the fitted plane with a short
// lag, and the height is the lowest that clears every wheel.
function restTruck(sim, dt, m, truck, standing) {
  const fit = fitTruck(sim, m.x, m.y, m.heading, sim.truckFit, standing ? m : null),
    k = 1 - Math.exp(-dt / TILT_TIME),
    z = m.z,
    pitch = m.pitch,
    roll = m.roll;
  m.pitch += (Math.atan(fit.b) - m.pitch) * k;
  m.roll += (Math.atan(fit.c * Math.cos(m.pitch)) - m.roll) * k;
  if (Math.abs(m.pitch) < 1e-7) m.pitch = 0;
  if (Math.abs(m.roll) < 1e-7) m.roll = 0;
  const b = Math.tan(m.pitch),
    c = Math.tan(m.roll) / Math.cos(m.pitch);
  let target = -Infinity;
  for (let n = 0; n < SAMPLE_COUNT; n++) {
    const [u, v] = WHEEL_SAMPLES[n];
    target = Math.max(target, fit.h[n] - b * u - c * v);
  }
  const change = target - m.z;
  m.z =
    change > 0
      ? m.z + Math.min(change, RISE_RATE * dt)
      : m.z + Math.max(change, -FALL_RATE * dt);
  if (Math.abs(m.z - target) < 1e-7) m.z = target + 0;
  truck.chassisMoving =
    Math.abs(m.z - z) > 1e-4 ||
    Math.abs(m.pitch - pitch) > 1e-5 ||
    Math.abs(m.roll - roll) > 1e-5;
}

// Why the truck cannot stand here, or null if it can.
function truckObstacle(sim, m) {
  const c = Math.cos(m.heading),
    s = Math.sin(m.heading),
    { centre, halfLength, halfWidth } = TRUCK_FOOTPRINT;
  if (
    crawlerHitsProp(m.x + c * centre, m.y + s * centre, c, s, halfLength, halfWidth)
  )
    return "object";
  const surface = sim.surf;
  for (const along of [TRUCK.rearAxles[1], TRUCK.frontAxle]) {
    const x = m.x + c * along,
      y = m.y + s * along;
    sim.terrain.sample(x, y, surface);
    if (
      surface[0] < WATER.level - WADE_DEPTH &&
      Math.hypot(x - WATER.x, y - WATER.y) < WATER.radius * 1.5
    )
      return "water";
  }
  return null;
}

// Another machine in the way of a truck moving from `before` to `m`. Machines
// that already touch can always move apart.
function machineInTheWay(sim, m, before, truck) {
  const box = truckBox(m),
    was = truckBox(before);
  const closer = (other) =>
    Math.hypot(box.x - other.x, box.y - other.y) <
    Math.hypot(was.x - other.x, was.y - other.y);
  for (const v of sim.vehicles) {
    const other = crawlerBox(v.machine);
    if (!boxesOverlap(box, other)) continue;
    if (!boxesOverlap(was, other) || closer(other)) return true;
  }
  for (const t of sim.trucks) {
    if (t === truck) continue;
    const other = truckBox(t.pose);
    if (!boxesOverlap(box, other)) continue;
    if (!boxesOverlap(was, other) || closer(other)) return true;
  }
  return false;
}

// Does a crawler at `m`, coming from `before`, run into a truck?
export function crawlerMeetsTruck(sim, m, before) {
  const box = crawlerBox(m),
    was = crawlerBox(before);
  for (const t of sim.trucks) {
    const other = truckBox(t.pose);
    if (!boxesOverlap(box, other)) continue;
    if (!boxesOverlap(was, other)) return true;
    if (
      Math.hypot(m.x - other.x, m.y - other.y) <
      Math.hypot(before.x - other.x, before.y - other.y)
    )
      return true;
  }
  return false;
}

// The truck's controls: the body's hoist, the steering, which follows the wheel
// at a limited rate, and the speed, which rises and falls at limited rates. The
// truck turns as a bicycle with the truck's wheelbase.
export function advanceTruck(sim, dt, truck) {
  const m = truck.pose,
    a = truck.estop ? null : truck.axes,
    setting = truck.speed,
    drive = a ? clamp(a.drive, -1, 1) : 0,
    steer = a ? clamp(a.steer, -1, 1) : 0,
    hoist = a ? clamp(a.hoist, -1, 1) : 0,
    tip = m.tip,
    wheel = m.steer,
    velocity = m.velocity;
  if (hoist)
    m.tip = clamp(
      m.tip +
        hoist *
          (hoist > 0 ? TRUCK_DRIVE.raiseRate : TRUCK_DRIVE.lowerRate) *
          setting *
          dt,
      0,
      TRUCK.maxTip,
    );
  const turn = TRUCK_DRIVE.steerRate * dt;
  m.steer += clamp(steer * MAX_STEER - m.steer, -turn, turn);
  if (Math.abs(m.steer) < 1e-9) m.steer = 0;
  // With the body up the truck only creeps.
  const limit =
      m.tip > TRUCK_DRIVE.raisedFrom ? TRUCK_DRIVE.raisedSpeed : Infinity,
    want =
      drive > 0
        ? Math.min(drive * TRUCK_DRIVE.topSpeed * setting, limit)
        : drive < 0
          ? -Math.min(-drive * TRUCK_DRIVE.reverseSpeed * setting, limit)
          : 0,
    speeding = Math.abs(want) > Math.abs(velocity) && want * velocity >= 0,
    rate =
      (speeding ? TRUCK_DRIVE.accelerate : TRUCK_DRIVE.brake) *
      (truck.estop ? 3 : 1) *
      dt;
  m.velocity = velocity + clamp(want - velocity, -rate, rate);
  if (Math.abs(m.velocity) < 1e-6) m.velocity = 0;
  truck.drove = false;
  truck.busy = m.tip !== tip || m.steer !== wheel || m.velocity !== velocity;
  const travel = ((velocity + m.velocity) / 2) * dt;
  if (!travel) {
    restTruck(sim, dt, m, truck, true);
    return;
  }
  const before = {
    x: m.x,
    y: m.y,
    z: m.z,
    heading: m.heading,
    pitch: m.pitch,
    roll: m.roll,
  };
  const turned = (travel * Math.tan(m.steer)) / TRUCK.wheelbase,
    middle = m.heading + turned / 2;
  m.heading += turned;
  const extent = truckExtent(m.heading);
  m.x = clamp(
    m.x + travel * Math.cos(middle),
    WORLD.minX + extent.x,
    WORLD.maxX - extent.x,
  );
  m.y = clamp(
    m.y + travel * Math.sin(middle),
    WORLD.minY + extent.y,
    WORLD.maxY - extent.y,
  );
  // Scenery, deep water, other machines and slopes it cannot climb stop the truck,
  // but a motion that makes things better is always allowed.
  let obstacle = truckObstacle(sim, m);
  if (obstacle && truckObstacle(sim, before) === obstacle) obstacle = null;
  if (!obstacle && machineInTheWay(sim, m, before, truck)) obstacle = "machine";
  if (!obstacle) {
    const fit = fitTruck(sim, m.x, m.y, m.heading, sim.truckFit),
      tilt = Math.atan(Math.hypot(fit.b, fit.c));
    if (tilt > TRUCK_DRIVE.maxTilt) {
      const was = fitTruck(sim, before.x, before.y, before.heading, sim.truckFit);
      if (tilt > Math.atan(Math.hypot(was.b, was.c))) obstacle = "steep";
    }
  }
  if (obstacle) {
    truck.obstacle = obstacle;
    Object.assign(m, before);
    m.velocity = 0;
    truck.busy = true;
    restTruck(sim, dt, m, truck, true);
    return;
  }
  restTruck(sim, dt, m, truck, false);
  m.wheels += travel;
  truck.drove = true;
}

// Sand pressed by a moving truck: a rut under each tyre, with the sand it
// displaces pushed up beside it, and whatever stands higher than the underside
// pushed out from under the truck.
export function pressTruckSand(sim, truck) {
  // Standing still, the tyres keep their footing clear and nothing else moves, so
  // that slumping sand can come to rest against the truck.
  const drove = truck.drove,
    m = truck.pose,
    t = sim.terrain,
    ch = Math.cos(m.heading),
    sh = Math.sin(m.heading),
    b = Math.tan(m.pitch),
    c = Math.tan(m.roll) / Math.cos(m.pitch),
    extent = truckExtent(m.heading),
    i0 = clamp(Math.floor((m.x - extent.x - WORLD.minX) / CELL), 0, NX - 1),
    i1 = clamp(Math.floor((m.x + extent.x - WORLD.minX) / CELL), 0, NX - 1),
    j0 = clamp(Math.floor((m.y - extent.y - WORLD.minY) / CELL), 0, NY - 1),
    j1 = clamp(Math.floor((m.y + extent.y - WORLD.minY) / CELL), 0, NY - 1),
    halfTyre = TRUCK.tyreWidth / 2,
    halfTwins = TRUCK.twinHalf + halfTyre;
  for (let j = j0; j <= j1; j++)
    for (let i = i0; i <= i1; i++) {
      const cell = j * NX + i;
      // Pages that never held sand are skipped 64 cells at a time.
      if (!t.hasPage(cell)) {
        i |= 63;
        continue;
      }
      const sand = t.get(cell);
      if (sand < 0.01) continue;
      const dx = cellX(i) - m.x,
        dy = cellY(j) - m.y,
        u = dx * ch + dy * sh,
        v = -dx * sh + dy * ch;
      if (
        u < TRUCK.bodyRear ||
        u > TRUCK.bumper ||
        Math.abs(v) > TRUCK.bodyHalfWidth
      )
        continue;
      // Under a tyre's tread, or under the truck.
      let band = 0,
        clearance;
      if (Math.abs(u - TRUCK.frontAxle) <= PATCH) {
        if (Math.abs(Math.abs(v) - TRUCK.frontTrack) <= halfTyre)
          band = TRUCK.frontTrack + halfTyre;
      } else if (
        TRUCK.rearAxles.some((axle) => Math.abs(u - axle) <= PATCH) &&
        Math.abs(Math.abs(v) - TRUCK.rearTrack) <= halfTwins
      )
        band = TRUCK.rearTrack + halfTwins;
      if (band) clearance = 0;
      else if (!drove) continue;
      else if (u > TRUCK.frontAxle + TRUCK.tyreRadius) clearance = NOSE;
      else if (u < TRUCK.rearAxles[1] - TRUCK.tyreRadius) clearance = TAIL;
      else clearance = BELLY;
      const excess = Math.min(sand, t.surface(cell) - (m.z + b * u + c * v + clearance));
      if (excess <= 0.01) continue;
      if (band) t.press(cell);
      // Beside the tyre it came from, or out from under the truck.
      const side = v < 0 ? -1 : 1,
        across =
          side *
          ((band || TRUCK.bodyHalfWidth) + 4 + 14 * (sim.random() + 0.5)),
        along = u + 8 * sim.random();
      t.add(cell, -excess);
      t.touch(cell);
      t.spread(
        m.x + along * ch - across * sh,
        m.y + along * sh + across * ch,
        excess * CELL * CELL,
        SPREAD,
      );
    }
}

// A parcel near a truck lands in its body if it is over the floor and has come
// down to the sand there. Returns true if it did.
export function catchInTruck(sim, truck, i) {
  const p = sim.pos,
    k = 3 * i,
    centre = truck.frame.centre,
    ex = p[k] - centre[0],
    ey = p[k + 1] - centre[1],
    ez = p[k + 2] - centre[2];
  if (ex * ex + ey * ey + ez * ez > NEAR * NEAR) return false;
  const l = truck.frame.toLocal(p[k], p[k + 1], p[k + 2], sim.l3);
  if (
    l[0] < 0 ||
    l[0] > TRUCK_LOAD.length ||
    Math.abs(l[1]) > TRUCK_LOAD.halfWidth ||
    l[2] < -UNDER_FLOOR ||
    l[2] > truck.load.surface(l[0], l[1]) + R
  )
    return false;
  truck.load.add(l[0], l[1], sim.volumes[i]);
  sim.release(i);
  return true;
}

// The open rear wall's gap at its foot (mm), from how far it hangs out.
export const gateGap = (pose) => 2 * GATE_HINGE * Math.sin(gateAngle(pose) / 2);

// A parcel leaves the body: under the open rear wall at the floor, or over the top
// of a wall, moving with the body as it starts to fall.
export function emitFromTruck(sim, truck, rim, index, volume, dt) {
  const point = sim.l3,
    now = sim.w3,
    before = sim.m3,
    spread = sim.random(),
    open = gateAngle(truck.pose) > 0;
  let x,
    y,
    z,
    slideX = 0,
    slideY = 0;
  if (rim === RIM_REAR) {
    x = open ? -R - 1 : -TRUCK.wall - R;
    y = TRUCK_LOAD.rowY(index) + spread * TRUCK_LOAD.dv;
    z = (open ? 0 : TRUCK.rearWall) + R * 0.5;
    slideX = -1;
  } else if (rim === RIM_FRONT) {
    x = TRUCK_LOAD.length + TRUCK.wall + R;
    y = TRUCK_LOAD.rowY(index) + spread * TRUCK_LOAD.dv;
    z = TRUCK.frontWall + R * 0.5;
    slideX = 1;
  } else {
    const side = rim === RIM_LEFT ? 1 : -1;
    x = TRUCK_LOAD.columnX(index) + spread * TRUCK_LOAD.du;
    y = side * (TRUCK_LOAD.halfWidth + TRUCK.wall + R);
    z = TRUCK.sideWall + R * 0.5;
    slideY = side;
  }
  truck.prevFrame.toWorld(x, y, z, before);
  const bx = before[0],
    by = before[1],
    bz = before[2];
  truck.frame.toWorld(x, y, z, now);
  const wx = now[0],
    wy = now[1],
    wz = now[2];
  if (rim === RIM_REAR && open && yardInside(wx, wy) <= 0) truck.hauled += volume;
  // Already down in the bed, it has nowhere to fall: it joins the bed here, over a
  // small disc.
  sim.terrain.sample(wx, wy, sim.surf);
  if (wz - R <= sim.surf[0]) {
    sim.terrain.spread(wx, wy, volume, SPREAD);
    return;
  }
  truck.frame.toWorld(x + slideX, y + slideY, z, point);
  const speed = SPILL_SPEED * (1 + 0.6 * sim.random());
  sim.spawn(
    wx,
    wy,
    wz,
    (wx - bx) / dt + (point[0] - wx) * speed,
    (wy - by) / dt + (point[1] - wy) * speed,
    (wz - bz) / dt + (point[2] - wz) * speed,
    volume,
    null,
  );
}

// Everything in a body joins the bed where it stands: for a truck that leaves the
// world or jumps back to its place.
export function dropTruckLoad(sim, truck) {
  const load = truck.load,
    world = sim.w3;
  for (let j = 0; j < TRUCK_LOAD.nv; j++)
    for (let i = 0; i < TRUCK_LOAD.nu; i++) {
      const volume = load.thickness[j * TRUCK_LOAD.nu + i] * TRUCK_LOAD.area;
      if (volume <= 0) continue;
      truck.frame.toWorld(TRUCK_LOAD.columnX(i), TRUCK_LOAD.rowY(j), 0, world);
      sim.terrain.deposit(world[0], world[1], volume);
    }
  for (const [rim, pending] of load.pending.entries()) {
    for (let n = 0; n < pending.length; n++)
      if (pending[n] > 0)
        emitFromTruck(sim, truck, rim, n, pending[n], 1 / 120);
    if (load.dregs[rim] > 0)
      emitFromTruck(sim, truck, rim, load.dregAt[rim], load.dregs[rim], 1 / 120);
  }
  load.clear();
}

// Is anything about this truck still changing?
export const truckIdle = (truck) =>
  (truck.estop || TRUCK_AXES.every((key) => !truck.axes[key])) &&
  truck.pose.velocity === 0 &&
  truck.pose.steer === 0;

// One substep of a truck: drive, press the sand, and let its load slump and spill.
export function stepTruck(sim, dt, truck) {
  truck.prevFrame.copy(truck.frame);
  advanceTruck(sim, dt, truck);
  pressTruckSand(sim, truck);
  truck.frame.set(bodyPose(truck.pose, truck.body));
  truck.load.relax(truck.frame, gateGap(truck.pose));
  sim.spillPending(truck, truck.load, dt, sim.emitTruck);
}

// Once a tick, before the substeps: what the bed behind the open rear holds in.
export function propTruck(sim, truck) {
  truck.obstacle = null;
  truck.load.propBy(truck.frame, sim.terrain, gateAngle(truck.pose) > 0);
}

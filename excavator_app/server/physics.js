import { solve } from "../shared/kinematics.js";
import { CONFIG } from "../shared/config.js";
import {
  WORLD,
  AXES,
  SAND,
  BUCKET,
  POUR_ZONE,
  clamp,
  neutral,
  crawlerExtent,
  crawlersOverlap,
  initialMachine,
  armFrame,
  cellX,
  cellY,
} from "../shared/world.js";
import {
  WATER,
  groundHeight,
  crawlerHitsProp,
} from "../shared/landscape.js";
import { Terrain, initialTerrain, CELL_AREA } from "./terrain.js";
import {
  BucketFrame,
  REGION,
  REGION_EDGE_MOUTH,
  BOUNDING_RADIUS,
  insidePolygon,
  insideCavity,
} from "../shared/bucket.js";
import { LOAD, mouthToLocal } from "../shared/bucket-load.js";
import {
  BucketLoad,
  RIM_LIP,
  RIM_FAR,
  RIM_LEFT,
  RIM_RIGHT,
  RIM_BED,
} from "./bucket-load.js";

export function bucketPose(machine) {
  const s = solve(machine.strokes);
  return armFrame(
    machine,
    s.origins.bucket[0] + CONFIG.arm_offset[0],
    s.origins.bucket[1] + CONFIG.arm_offset[2],
    s.angles.bucket,
  );
}
export function toLocal(x, y, z, b) {
  const dx = x - b.x,
    dy = y - b.y,
    dz = z - b.z;
  return [
    dx * b.ex[0] + dy * b.ex[1] + dz * b.ex[2],
    dx * b.ey[0] + dy * b.ey[1] + dz * b.ey[2],
    dx * b.ez[0] + dy * b.ez[1] + dz * b.ez[2],
  ];
}
export function toWorld(x, y, z, b) {
  return [
    b.x + x * b.ex[0] + y * b.ey[0] + z * b.ez[0],
    b.y + x * b.ex[1] + y * b.ey[1] + z * b.ez[1],
    b.z + x * b.ex[2] + y * b.ey[2] + z * b.ez[2],
  ];
}
export const insideProfile = insidePolygon;

const R = WORLD.radius,
  GRAIN = SAND.grainVolume,
  MAX = SAND.maxGrains,
  SHELL = BUCKET.shellHalfThickness,
  SUBSTEPS = 4,
  MAX_SPEED = 2500,
  // A falling parcel this far from a bucket's centre has left its reach.
  NEAR = Math.hypot(BOUNDING_RADIUS, BUCKET.outerHalfWidth) + R + 8,
  // The bed goes into a bucket or round it at no more than this per substep (mm),
  // so a bucket buried in deep sand does not open a pit at once.
  CUT_RATE = 6,
  // Sand leaves over a rim at this speed (mm/s), sliding, before it falls.
  SPILL_SPEED = 90,
  TRACK_HALF_LENGTH = CONFIG.wheel_centres / 2 + CONFIG.sprocket_tip_radius_mm,
  TRACK_Y = CONFIG.track_centres / 2,
  SHOE_HALF = CONFIG.shoe_width / 2,
  BELLY_CLEARANCE = 40,
  // Full track speed (mm/s), about 12 km/h at 1:15: a game's travel speed.
  TRACK_SPEED = 220,
  // Loose sand gives this far under a shoe the first time it is driven over.
  SHOE_SINK = 4,
  // Working tracks break up firm sand this far around them (mm).
  TRACK_REACH = 60,
  // The crawler climbs up to this tilt, a little past the sand's repose, so a
  // machine that dug itself into a pit can always drive out.
  MAX_TILT = (37 * Math.PI) / 180,
  // Deeper water than this above the track shoes stops the crawler.
  WADE_DEPTH = 40,
  // The chassis follows the ground with these time constant and rates.
  TILT_TIME = 0.14,
  RISE_RATE = 700,
  FALL_RATE = 450,
  // The rotating upper body (CAD bounds, above its slew ring).
  UPPER_MIN_X = -145,
  UPPER_MAX_X = 145,
  UPPER_MIN_Y = -158,
  UPPER_MAX_Y = 136,
  UPPER_BOTTOM = 110,
  // Network groups of parcels: positions fit Int16 within half this span of a centre.
  GROUP_SPAN = 6400;
const { nx: NX, ny: NY, cell: CELL } = SAND;
const FOOT = 48; // max cut footprint, in cells per side
// A cell's cut class is only needed while the bucket stays over that cell, so
// it lives in a small torus indexed by the low bits of the cell coordinates.
const CUT_MASK = 127,
  cutIndex = (i, j) => ((j & CUT_MASK) << 7) | (i & CUT_MASK);
// Fourteen points along the tracks that the chassis rests on.
const SAMPLE_U = [-130, -87, -43, 0, 43, 87, 130],
  SAMPLE_SUM_U2 = SAMPLE_U.reduce((sum, u) => sum + u * u, 0) * 2,
  SAMPLE_SUM_V2 = TRACK_Y * TRACK_Y * SAMPLE_U.length * 2;

// One excavator: its controls, its pose, where its bucket is and the sand in it.
// The bed and the sand in the air are shared by all the machines in the world.
class Vehicle {
  constructor(id, slot, machine) {
    this.id = id;
    // Falling parcels name the bucket they are near by this small index.
    this.slot = slot;
    this.home = structuredClone(machine);
    this.frame = new BucketFrame();
    this.prevFrame = new BucketFrame();
    this.cutClass = new Uint8Array((CUT_MASK + 1) * (CUT_MASK + 1));
    this.load = new BucketLoad();
    this.touchingBed = false;
    this.poseVersion = 0;
    this.restart();
  }

  restart(machine = this.home) {
    this.machine = structuredClone(machine);
    this.axes = neutral();
    this.speed = 0.65;
    this.estop = false;
    this.blocked = false;
    this.obstacle = null;
    this.chassisMoving = false;
    this.drove = false;
    this.bodyMoved = false;
    this.stats = { load: 0, blocked: false, obstacle: null };
    this.cutClass.fill(0);
    this.load.clear();
    this.touchingBed = false;
    this.bucket = bucketPose(this.machine);
    this.frame.set(this.bucket);
    this.prevFrame.set(this.bucket);
  }
}

// Sand as height fields: the bed is one that slumps to its angle of repose, and
// each bucket carries a small one in its own frame. Moving sand changes field by
// exact volumes. Sand spilled over a rim falls as parcels, with no contacts, until
// it lands on the bed or in a bucket.
export class SandSimulation {
  // A simulation starts with one excavator at the start position unless told
  // otherwise. The worker starts empty and follows the players in the room.
  constructor({ vehicles = [{ id: 1 }] } = {}) {
    this.terrain = new Terrain();
    this.pos = new Float64Array(3 * MAX);
    this.vel = new Float64Array(3 * MAX);
    this.volumes = new Float64Array(MAX);
    this.alive = new Uint8Array(MAX);
    // Which vehicle's bucket a parcel is still near, by slot; valid while near[i].
    this.near = new Uint8Array(MAX);
    this.holder = new Uint8Array(MAX);
    this.freeList = new Int32Array(MAX);
    this.footLow = new Float64Array(FOOT * FOOT);
    this.testFrame = new BucketFrame();
    this.w3 = new Float64Array(3);
    this.l3 = new Float64Array(3);
    this.m3 = new Float64Array(3);
    this.col = new Float64Array(4);
    this.surf = new Float64Array(3);
    this.fit = { b: 0, c: 0, h: new Float64Array(2 * SAMPLE_U.length) };
    this.vehicles = [];
    this.bySlot = [];
    for (const { id, machine } of vehicles) this.addVehicle(id, machine);
    this.reset();
  }

  reset() {
    for (const v of this.vehicles) v.restart();
    this.tick = 0;
    this.resting = false;
    this.terrain.copyFrom(initialTerrain());
    this.alive.fill(0);
    this.grains = 0;
    for (let i = 0; i < MAX; i++) this.freeList[i] = i;
    this.freeHead = 0;
    this.freeCount = MAX;
    this.seed = 60;
    this.world = this.measure();
  }

  addVehicle(id, machine = initialMachine()) {
    let slot = this.bySlot.indexOf(null);
    if (slot < 0) slot = this.bySlot.length;
    const vehicle = new Vehicle(id, slot, machine);
    this.bySlot[slot] = vehicle;
    this.vehicles.push(vehicle);
    this.resting = false;
    return vehicle;
  }

  // Its load falls where it is: the sand itself stays in the world.
  removeVehicle(vehicle) {
    this.dropLoad(vehicle);
    this.vehicles.splice(this.vehicles.indexOf(vehicle), 1);
    this.bySlot[vehicle.slot] = null;
    this.resting = false;
  }

  // Move a machine in one jump, leaving behind any sand in its bucket.
  placeVehicle(vehicle, machine) {
    this.dropLoad(vehicle);
    vehicle.restart(machine);
    this.resting = false;
  }

  // Everything in a bucket falls out where it is.
  dropLoad(vehicle) {
    const load = vehicle.load,
      frame = vehicle.frame,
      point = this.l3,
      world = this.w3;
    for (let j = 0; j < LOAD.nv; j++)
      for (let i = 0; i < LOAD.nu; i++) {
        let volume = load.thickness[j * LOAD.nu + i] * LOAD.area;
        if (volume <= 0) continue;
        const u = LOAD.columnU(i),
          y = LOAD.rowY(j),
          bottom = LOAD.floors[i],
          parcels = Math.max(1, Math.ceil(volume / GRAIN)),
          each = volume / parcels;
        for (let k = 0; k < parcels; k++) {
          mouthToLocal(
            u + this.random() * LOAD.du,
            y + this.random() * LOAD.dv,
            bottom + ((k + 0.5) * (volume / LOAD.area)) / parcels,
            point,
          );
          frame.toWorld(point[0], point[1], point[2], world);
          this.spawn(world[0], world[1], world[2], 0, 0, 0, each, vehicle);
        }
      }
    for (const [rim, pending] of load.pending.entries())
      for (let n = 0; n < pending.length; n++)
        if (pending[n] > 0) this.emit(vehicle, rim, n, pending[n], 1 / 120);
    load.clear();
  }

  // Follow the server's list of machines before a step. The server's pose wins
  // after a stop invalidates a busy step.
  syncVehicles(commands) {
    for (const v of [...this.vehicles])
      if (!commands.some((command) => command.id === v.id))
        this.removeVehicle(v);
    for (const command of commands) {
      let v = this.vehicles.find((candidate) => candidate.id === command.id);
      if (!v) {
        v = this.addVehicle(command.id, command.machine);
        v.poseVersion = command.poseVersion;
      } else if (v.poseVersion !== command.poseVersion) {
        this.placeVehicle(v, command.machine);
        v.poseVersion = command.poseVersion;
      }
      v.axes = command.axes;
      v.speed = command.speed;
      v.estop = command.estop;
      v.machine = command.machine;
    }
  }

  // The first machine, for a solo drive and the numerical tests.
  get machine() {
    return this.vehicles[0].machine;
  }
  set machine(value) {
    this.vehicles[0].machine = value;
  }
  get axes() {
    return this.vehicles[0].axes;
  }
  set axes(value) {
    this.vehicles[0].axes = value;
  }
  get speed() {
    return this.vehicles[0].speed;
  }
  set speed(value) {
    this.vehicles[0].speed = value;
  }
  get estop() {
    return this.vehicles[0].estop;
  }
  set estop(value) {
    this.vehicles[0].estop = value;
  }
  get bucket() {
    return this.vehicles[0].bucket;
  }
  set bucket(value) {
    this.vehicles[0].bucket = value;
  }
  get frame() {
    return this.vehicles[0].frame;
  }
  get prevFrame() {
    return this.vehicles[0].prevFrame;
  }
  get blocked() {
    return this.vehicles[0].blocked;
  }
  get obstacle() {
    return this.vehicles[0].obstacle;
  }
  set obstacle(value) {
    this.vehicles[0].obstacle = value;
  }
  get stats() {
    return { ...this.vehicles[0].stats, ...this.world };
  }

  random() {
    this.seed = (1664525 * this.seed + 1013904223) >>> 0;
    return this.seed / 4294967296 - 0.5;
  }

  // Exact sand volume: the bed, every bucket and the sand in the air (mm^3).
  totalVolume() {
    let sum = this.terrain.volume();
    for (const v of this.vehicles) sum += v.load.total;
    for (let i = 0; i < MAX; i++) if (this.alive[i]) sum += this.volumes[i];
    return sum;
  }

  // A parcel of falling sand. With no slot free it lands straight away.
  spawn(x, y, z, vx, vy, vz, volume, vehicle) {
    if (!this.freeCount) {
      this.terrain.deposit(x, y, volume);
      return -1;
    }
    const i = this.freeList[this.freeHead];
    this.freeHead = (this.freeHead + 1) % MAX;
    this.freeCount--;
    this.grains++;
    const k = 3 * i;
    this.alive[i] = 1;
    this.pos[k] = x;
    this.pos[k + 1] = y;
    this.pos[k + 2] = z;
    this.vel[k] = vx;
    this.vel[k + 1] = vy;
    this.vel[k + 2] = vz;
    this.volumes[i] = volume;
    this.near[i] = 1;
    this.holder[i] = vehicle.slot;
    return i;
  }

  release(i) {
    this.alive[i] = 0;
    this.grains--;
    this.freeList[(this.freeHead + this.freeCount) % MAX] = i;
    this.freeCount++;
  }

  // Lowest clearance of the bucket shell and teeth above the hard ground.
  bucketClearance(machine) {
    const frame = this.testFrame.set(bucketPose(machine)),
      w = this.w3;
    let clearance = Infinity;
    for (const [x, z] of REGION)
      for (const y of [-BUCKET.outerHalfWidth, BUCKET.outerHalfWidth]) {
        frame.toWorld(x, y, z, w);
        clearance = Math.min(clearance, w[2] - SHELL - groundHeight(w[0], w[1]));
      }
    return clearance;
  }

  // Surface under the fourteen track samples, and the plane z = a + b u + c v
  // fitted to them by least squares (u along the heading, v across it).
  fitFootprint(x, y, heading) {
    const t = this.terrain,
      fit = this.fit,
      ch = Math.cos(heading),
      sh = Math.sin(heading),
      s = this.surf;
    let sumU = 0,
      sumV = 0,
      n = 0;
    for (const v of [-TRACK_Y, TRACK_Y])
      for (const u of SAMPLE_U) {
        const px = x + u * ch - v * sh,
          py = y + u * sh + v * ch,
          cell = t.cellAt(px, py),
          sand = t.get(cell);
        t.sample(px, py, s);
        const height =
          s[0] - (sand > 0.5 && !t.pressed(cell) ? Math.min(sand, SHOE_SINK) : 0);
        fit.h[n++] = height;
        sumU += u * height;
        sumV += v * height;
      }
    fit.b = sumU / SAMPLE_SUM_U2;
    fit.c = sumV / SAMPLE_SUM_V2;
    return fit;
  }

  // Rest the chassis on the footprint: the tilt follows the fitted plane with
  // a short lag, and the height is the lowest that clears every sample.
  restChassis(dt, m, v) {
    const fit = this.fitFootprint(m.x, m.y, m.heading),
      k = 1 - Math.exp(-dt / TILT_TIME);
    const before = [m.z, m.pitch, m.roll];
    m.pitch += (Math.atan(fit.b) - m.pitch) * k;
    m.roll += (Math.atan(fit.c * Math.cos(m.pitch)) - m.roll) * k;
    if (Math.abs(m.pitch) < 1e-7) m.pitch = 0;
    if (Math.abs(m.roll) < 1e-7) m.roll = 0;
    const b = Math.tan(m.pitch),
      c = Math.tan(m.roll) / Math.cos(m.pitch);
    let target = -Infinity,
      n = 0;
    for (const v of [-TRACK_Y, TRACK_Y])
      for (const u of SAMPLE_U)
        target = Math.max(target, fit.h[n++] - b * u - c * v);
    const change = target - m.z;
    m.z =
      change > 0
        ? m.z + Math.min(change, RISE_RATE * dt)
        : m.z + Math.max(change, -FALL_RATE * dt);
    if (Math.abs(m.z - target) < 1e-7) m.z = target + 0;
    v.chassisMoving =
      Math.abs(m.z - before[0]) > 1e-4 ||
      Math.abs(m.pitch - before[1]) > 1e-5 ||
      Math.abs(m.roll - before[2]) > 1e-5;
  }

  // Why the crawler cannot stand here, or null if it can.
  obstacleAt(m) {
    const ch = Math.cos(m.heading),
      sh = Math.sin(m.heading);
    if (
      crawlerHitsProp(
        m.x,
        m.y,
        ch,
        sh,
        TRACK_HALF_LENGTH,
        TRACK_Y + SHOE_HALF,
      )
    )
      return "object";
    const s = this.surf;
    this.terrain.sample(m.x, m.y, s);
    if (
      s[0] < WATER.level - WADE_DEPTH &&
      Math.hypot(m.x - WATER.x, m.y - WATER.y) < WATER.radius * 1.5
    )
      return "water";
    return null;
  }

  // Kinematic machine riding on the ground and the sand. The bucket cannot be
  // driven through the hard ground: a motion that would push it deeper stops.
  advanceMachine(dt, v = this.vehicles[0]) {
    const a = v.estop ? neutral() : v.axes,
      m = v.machine,
      speed = v.speed;
    // Nothing below looks at the clearance unless an axis is commanded.
    let clearance = AXES.some((key) => a[key])
      ? this.bucketClearance(m)
      : Infinity;
    const accept = () => {
      const next = this.bucketClearance(m);
      if (next < 0 && next < clearance - 1e-9) {
        v.blocked = true;
        return false;
      }
      clearance = next;
      return true;
    };
    v.bodyMoved = false;
    for (const [i, key] of ["boom", "stick", "bucket"].entries()) {
      const old = m.strokes[i];
      m.strokes[i] = clamp(old + a[key] * 13 * speed * dt, 0, 60);
      if (m.strokes[i] !== old && !accept()) m.strokes[i] = old;
    }
    const slew = m.slew;
    m.slew = clamp(slew + a.slew * 30 * speed * dt, -150, 150);
    if (m.slew !== slew) {
      if (accept()) v.bodyMoved = true;
      else m.slew = slew;
    }
    const l = a.leftTrack * TRACK_SPEED * speed,
      r = a.rightTrack * TRACK_SPEED * speed;
    v.drove = false;
    v.crawling = Boolean(l || r);
    if (!l && !r) {
      this.restChassis(dt, m, v);
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
    m.heading += ((r - l) / CONFIG.track_centres) * dt;
    const extent = crawlerExtent(m.heading);
    m.x = clamp(
      m.x + ((l + r) / 2) * Math.cos(m.heading) * dt,
      WORLD.minX + extent.x,
      WORLD.maxX - extent.x,
    );
    m.y = clamp(
      m.y + ((l + r) / 2) * Math.sin(m.heading) * dt,
      WORLD.minY + extent.y,
      WORLD.maxY - extent.y,
    );
    // Solid scenery and deep water stop the crawler, and so does a slope it
    // cannot climb. A motion that makes things better is always allowed.
    let obstacle = this.obstacleAt(m);
    if (obstacle && this.obstacleAt(before) === obstacle) obstacle = null;
    if (!obstacle && this.machineInTheWay(m, before, v)) obstacle = "machine";
    if (!obstacle) {
      const fit = this.fitFootprint(m.x, m.y, m.heading),
        tilt = Math.atan(Math.hypot(fit.b, fit.c));
      if (tilt > MAX_TILT) {
        const was = this.fitFootprint(before.x, before.y, before.heading);
        if (tilt > Math.atan(Math.hypot(was.b, was.c))) obstacle = "steep";
      }
    }
    if (obstacle) {
      v.obstacle = obstacle;
      Object.assign(m, before);
      this.restChassis(dt, m, v);
      return;
    }
    this.restChassis(dt, m, v);
    if (!accept()) {
      Object.assign(m, before);
      return;
    }
    m.tracks[0] += l * dt;
    m.tracks[1] += r * dt;
    v.drove = true;
    v.bodyMoved = true;
  }

  // Crawlers cannot drive through each other. Two that somehow touch can always
  // part: only a motion that brings them closer is refused.
  machineInTheWay(m, before, v) {
    for (const other of this.vehicles) {
      if (other === v || !crawlersOverlap(m, other.machine)) continue;
      if (!crawlersOverlap(before, other.machine)) return true;
      const o = other.machine;
      if (
        Math.hypot(m.x - o.x, m.y - o.y) <
        Math.hypot(before.x - o.x, before.y - o.y)
      )
        return true;
    }
    return false;
  }

  // Sand displaced by the machine goes off to the side of its tracks, spread
  // over a band so it never stacks up in one column of cells.
  displace(cell, excess, u, side, ch, sh, m) {
    const t = this.terrain,
      v = side * (TRACK_Y + SHOE_HALF + 8 + 36 * (this.random() + 0.5)),
      along = u + 12 * this.random();
    t.add(cell, -excess);
    t.touch(cell);
    t.deposit(
      m.x + along * ch - v * sh,
      m.y + along * sh + v * ch,
      excess * CELL_AREA,
    );
  }

  // Working tracks break up the firm sand under and around them, so whatever they
  // run into slumps: a machine can always drive out of a pit it dug, even when a cut
  // face is too steep to climb.
  breakUpSand(m, ch, sh) {
    const t = this.terrain,
      extent = crawlerExtent(m.heading),
      i0 = clamp(Math.floor((m.x - extent.x - TRACK_REACH - WORLD.minX) / CELL), 0, NX - 1),
      i1 = clamp(Math.floor((m.x + extent.x + TRACK_REACH - WORLD.minX) / CELL), 0, NX - 1),
      j0 = clamp(Math.floor((m.y - extent.y - TRACK_REACH - WORLD.minY) / CELL), 0, NY - 1),
      j1 = clamp(Math.floor((m.y + extent.y + TRACK_REACH - WORLD.minY) / CELL), 0, NY - 1);
    for (let j = j0; j <= j1; j++)
      for (let i = i0; i <= i1; i++) {
        const dx = cellX(i) - m.x,
          dy = cellY(j) - m.y;
        if (
          Math.abs(dx * ch + dy * sh) <= TRACK_HALF_LENGTH + TRACK_REACH &&
          Math.abs(-dx * sh + dy * ch) <= TRACK_Y + SHOE_HALF + TRACK_REACH
        )
          t.loosen(j * NX + i);
      }
  }

  // Moving tracks press a shallow rut into loose sand; the lower frame and the
  // upper body push aside whatever stands in their way. Nothing here runs while
  // the machine stands still, so slumping sand can come to rest against it.
  pressSand(vehicle) {
    const m = vehicle.machine,
      t = this.terrain,
      ch = Math.cos(m.heading),
      sh = Math.sin(m.heading),
      b = Math.tan(m.pitch),
      c = Math.tan(m.roll) / Math.cos(m.pitch);
    if (vehicle.crawling) this.breakUpSand(m, ch, sh);
    if (vehicle.drove) {
      const extent = crawlerExtent(m.heading),
        i0 = clamp(Math.floor((m.x - extent.x - WORLD.minX) / CELL), 0, NX - 1),
        i1 = clamp(Math.floor((m.x + extent.x - WORLD.minX) / CELL), 0, NX - 1),
        j0 = clamp(Math.floor((m.y - extent.y - WORLD.minY) / CELL), 0, NY - 1),
        j1 = clamp(Math.floor((m.y + extent.y - WORLD.minY) / CELL), 0, NY - 1);
      for (let j = j0; j <= j1; j++)
        for (let i = i0; i <= i1; i++) {
          const dx = cellX(i) - m.x,
            dy = cellY(j) - m.y,
            u = dx * ch + dy * sh,
            v = -dx * sh + dy * ch;
          if (
            Math.abs(u) > TRACK_HALF_LENGTH ||
            Math.abs(v) > TRACK_Y + SHOE_HALF
          )
            continue;
          const cell = j * NX + i,
            sand = t.get(cell);
          if (sand < 0.01) continue;
          const onShoe = Math.abs(Math.abs(v) - TRACK_Y) <= SHOE_HALF,
            limit = m.z + b * u + c * v + (onShoe ? 0 : BELLY_CLEARANCE),
            excess = Math.min(sand, t.surface(cell) - limit);
          if (excess <= 0.01) continue;
          if (onShoe) t.press(cell);
          this.displace(cell, excess, u, v < 0 ? -1 : 1, ch, sh, m);
        }
    }
    if (!vehicle.bodyMoved) return;
    // The upper body turns with the slew; its footprint is a rotated box.
    const a = m.heading + (m.slew * Math.PI) / 180,
      ca = Math.cos(a),
      sa = Math.sin(a),
      reach = Math.hypot(UPPER_MAX_X, UPPER_MIN_Y),
      i0 = clamp(Math.floor((m.x - reach - WORLD.minX) / CELL), 0, NX - 1),
      i1 = clamp(Math.floor((m.x + reach - WORLD.minX) / CELL), 0, NX - 1),
      j0 = clamp(Math.floor((m.y - reach - WORLD.minY) / CELL), 0, NY - 1),
      j1 = clamp(Math.floor((m.y + reach - WORLD.minY) / CELL), 0, NY - 1);
    for (let j = j0; j <= j1; j++)
      for (let i = i0; i <= i1; i++) {
        const dx = cellX(i) - m.x,
          dy = cellY(j) - m.y,
          ux = dx * ca + dy * sa,
          uy = -dx * sa + dy * ca;
        if (
          ux < UPPER_MIN_X ||
          ux > UPPER_MAX_X ||
          uy < UPPER_MIN_Y ||
          uy > UPPER_MAX_Y
        )
          continue;
        const cell = j * NX + i,
          sand = t.get(cell);
        if (sand < 0.01) continue;
        const u = dx * ch + dy * sh,
          v = -dx * sh + dy * ch,
          excess = Math.min(
            sand,
            t.surface(cell) - (m.z + b * u + c * v + UPPER_BOTTOM),
          );
        if (excess > 0.01)
          this.displace(cell, excess, u, v < 0 ? -1 : 1, ch, sh, m);
      }
  }

  // Cells pushed by a closed wall move along the bucket's motion until they
  // clear its footprint; they lie loose there, and relaxation shapes the berm.
  pushTarget(cell, x, y, dx, dy, i0, j0, w, h) {
    const t = this.terrain;
    let target = cell;
    for (let step = 1; step <= 40; step++) {
      const px = clamp(x + dx * step * 6, WORLD.minX + 1, WORLD.maxX - 1),
        py = clamp(y + dy * step * 6, WORLD.minY + 1, WORLD.maxY - 1);
      target = t.cellAt(px, py);
      if (target === cell) continue;
      const ti = target % NX,
        tj = (target - ti) / NX,
        fi = ti - i0,
        fj = tj - j0;
      if (fi < 0 || fj < 0 || fi >= w || fj >= h) return target;
      if (Number.isNaN(this.footLow[fj * FOOT + fi])) return target;
    }
    return target;
  }

  // Sand met by a closed wall, or with no room left in the bucket, is pushed just
  // ahead of it.
  bulldoze(cell, amount, cx, cy, v, i0, j0, fw, fh) {
    const frame = v.frame,
      t = this.terrain,
      w = this.w3,
      before = this.m3,
      now = this.l3;
    // Push along the bucket's horizontal motion at this point.
    frame.toWorld(now[0], now[1], now[2], w);
    v.prevFrame.toWorld(now[0], now[1], now[2], before);
    let dx = w[0] - before[0],
      dy = w[1] - before[1],
      length = Math.hypot(dx, dy);
    if (length < 0.02) {
      dx = cx - frame.centre[0];
      dy = cy - frame.centre[1];
      length = Math.hypot(dx, dy);
    }
    if (length < 1e-6) {
      dx = Math.cos(frame.yaw);
      dy = Math.sin(frame.yaw);
      length = 1;
    }
    const target = this.pushTarget(
        cell,
        cx,
        cy,
        dx / length,
        dy / length,
        i0,
        j0,
        fw,
        fh,
      ),
      side = 36 * this.random(),
      ahead = 4 + 20 * (this.random() + 0.5) ** 2;
    t.cut(cell, amount);
    t.deposit(
      cellX(target & (NX - 1)) + (dx / length) * ahead - (dy / length) * side,
      cellY(Math.floor(target / NX)) +
        (dy / length) * ahead +
        (dx / length) * side,
      amount * CELL_AREA,
    );
  }

  // Sand from a bed cell into the bucket, under the point in this.l3. Returns the
  // thickness the bucket had room for. Rounding in the volumes is not a refusal.
  takeSand(v, cell, amount) {
    const now = this.l3,
      taken = v.load.add(now[0], now[1], now[2], amount * CELL_AREA) / CELL_AREA;
    if (taken <= 0) return 0;
    this.terrain.cut(cell, taken);
    return taken < amount - 1e-9 ? taken : amount;
  }

  // Excavate the bed where the bucket occupies it. Sand that reaches the cutting
  // region through the mouth or teeth goes into the bucket, while there is room,
  // and so does sand lying above an open mouth. The rest is bulldozed.
  cutTerrain(v) {
    const frame = v.frame,
      prev = v.prevFrame,
      cutClass = v.cutClass,
      t = this.terrain,
      w = this.w3,
      col = this.col,
      now = this.l3,
      before = this.m3;
    let x0 = Infinity,
      x1 = -Infinity,
      y0 = Infinity,
      y1 = -Infinity,
      lowest = Infinity;
    for (const [x, z] of REGION)
      for (const y of [-BUCKET.outerHalfWidth, BUCKET.outerHalfWidth]) {
        frame.toWorld(x, y, z, w);
        x0 = Math.min(x0, w[0]);
        x1 = Math.max(x1, w[0]);
        y0 = Math.min(y0, w[1]);
        y1 = Math.max(y1, w[1]);
        lowest = Math.min(lowest, w[2]);
      }
    const i0 = clamp(Math.floor((x0 - WORLD.minX) / CELL - 0.5), 0, NX - 1),
      i1 = clamp(Math.ceil((x1 - WORLD.minX) / CELL - 0.5), 0, NX - 1),
      j0 = clamp(Math.floor((y0 - WORLD.minY) / CELL - 0.5), 0, NY - 1),
      j1 = clamp(Math.ceil((y1 - WORLD.minY) / CELL - 0.5), 0, NY - 1),
      fw = Math.min(FOOT, i1 - i0 + 1),
      fh = Math.min(FOOT, j1 - j0 + 1);
    // Quick exit when the bucket is clear of the bed.
    let highest = -Infinity;
    for (let j = j0; j < j0 + fh; j++)
      for (let i = i0; i < i0 + fw; i++)
        highest = Math.max(highest, t.surface(j * NX + i));
    v.touchingBed = highest >= lowest - SHELL;
    if (!v.touchingBed) {
      for (let j = j0; j < j0 + fh; j++)
        for (let i = i0; i < i0 + fw; i++) cutClass[cutIndex(i, j)] = 0;
      return;
    }
    for (let fj = 0; fj < fh; fj++)
      for (let fi = 0; fi < fw; fi++)
        this.footLow[fj * FOOT + fi] = frame.column(
          cellX(i0 + fi),
          cellY(j0 + fj),
          col,
        )
          ? col[0]
          : NaN;
    for (let fj = 0; fj < fh; fj++)
      for (let fi = 0; fi < fw; fi++) {
        const i = i0 + fi,
          j = j0 + fj,
          cell = j * NX + i,
          cx = cellX(i),
          cy = cellY(j);
        if (Number.isNaN(this.footLow[fj * FOOT + fi])) {
          cutClass[cutIndex(i, j)] = 0;
          continue;
        }
        frame.column(cx, cy, col);
        const surface = t.surface(cell),
          low = col[0] - (col[2] ? 0 : SHELL),
          high = col[1] + (col[3] ? 0 : SHELL);
        t.setCeiling(cell, low);
        const sand = t.get(cell);
        if (surface <= low + 0.05 || sand <= 1e-9) {
          cutClass[cutIndex(i, j)] = 0;
          continue;
        }
        const removable = Math.min(sand, surface - low),
          inside = Math.min(removable, Math.max(0, high - low)),
          above = removable - inside,
          top = low + inside;
        // Which face did this sand cross to enter the bucket's region?
        const middle = (low + top) / 2;
        frame.toLocal(cx, cy, middle, now);
        prev.toLocal(cx, cy, middle, before);
        let type = cutClass[cutIndex(i, j)];
        const entered = this.regionEntry(before, now);
        if (entered) type = entered;
        if (!type) type = col[2] ? 1 : 2;
        cutClass[cutIndex(i, j)] = type;
        if (inside > 0) {
          const amount = Math.min(inside, CUT_RATE),
            taken = type === 1 ? this.takeSand(v, cell, amount) : 0;
          if (taken < amount)
            this.bulldoze(cell, inside - taken, cx, cy, v, i0, j0, fw, fh);
        }
        if (above > 0) {
          const amount = Math.min(above, CUT_RATE);
          frame.toLocal(cx, cy, col[1], now);
          const taken = col[3] ? this.takeSand(v, cell, amount) : 0;
          if (taken < amount)
            this.bulldoze(cell, amount - taken, cx, cy, v, i0, j0, fw, fh);
        }
      }
  }

  // 1 if a point moving from local a to b entered the cutting region through
  // the mouth or teeth, 2 through a wall or cheek, 0 if it was already inside.
  regionEntry(a, b) {
    const half = BUCKET.outerHalfWidth,
      n = REGION.length;
    const inside = (x, y, z) => {
      if (Math.abs(y) > half) return false;
      let result = false;
      for (let i = 0, j = n - 1; i < n; j = i++) {
        const p = REGION[i],
          q = REGION[j];
        if (
          p[1] > z !== q[1] > z &&
          x < ((q[0] - p[0]) * (z - p[1])) / (q[1] - p[1]) + p[0]
        )
          result = !result;
      }
      return result;
    };
    if (inside(a[0], a[1], a[2])) return 0;
    let best = 2,
      type = 0;
    const rx = b[0] - a[0],
      rz = b[2] - a[2];
    for (let k = 0; k < n; k++) {
      const p = REGION[k],
        q = REGION[(k + 1) % n],
        ex = q[0] - p[0],
        ez = q[1] - p[1],
        den = rx * ez - rz * ex;
      if (Math.abs(den) < 1e-12) continue;
      const qx = p[0] - a[0],
        qz = p[1] - a[2],
        s = (qx * ez - qz * ex) / den,
        u = (qx * rz - qz * rx) / den;
      if (s < 0 || s > 1 || u < 0 || u > 1 || s >= best) continue;
      if (Math.abs(a[1] + (b[1] - a[1]) * s) > half) continue;
      best = s;
      type = k === REGION_EDGE_MOUTH ? 1 : 2;
    }
    for (const plane of [-half, half]) {
      if ((a[1] - plane) * (b[1] - plane) >= 0) continue;
      const s = (plane - a[1]) / (b[1] - a[1]);
      if (s < best && inside(a[0] + rx * s, plane * 0.999, a[2] + rz * s)) {
        best = s;
        type = 2;
      }
    }
    return type;
  }

  // A parcel leaves over a rim: from along the teeth at the lip, and from outside
  // the plates elsewhere, moving with the bucket as it starts to fall.
  emit(v, rim, index, volume, dt) {
    const point = this.l3,
      now = this.w3,
      before = this.m3,
      spread = this.random();
    let u, y, w, slideU = 0, slideY = 0;
    if (rim === RIM_LIP) {
      const along = this.random() + 0.5;
      u = -11 * along - 1;
      w = 5.1 * along + R * 0.5;
      y = LOAD.rowY(index) + spread * LOAD.dv;
      slideU = -1;
    } else if (rim === RIM_FAR) {
      u = LOAD.length + 3 + 4 * (this.random() + 0.5);
      w = R * 0.5;
      y = LOAD.rowY(index) + spread * LOAD.dv;
      slideU = 1;
    } else if (rim === RIM_BED) {
      u = LOAD.columnU(v.load.lipColumn[index]) - LOAD.du / 2;
      w = R;
      y = LOAD.rowY(index) + spread * LOAD.dv;
      slideU = -1;
    } else {
      const side = rim === RIM_LEFT ? -1 : 1;
      u = LOAD.columnU(index) + spread * LOAD.du;
      w = R * 0.5;
      y = side * (BUCKET.outerHalfWidth + R + 0.5);
      slideY = side;
    }
    mouthToLocal(u, y, w, point);
    v.prevFrame.toWorld(point[0], point[1], point[2], before);
    const bx = before[0],
      by = before[1],
      bz = before[2];
    v.frame.toWorld(point[0], point[1], point[2], now);
    const x = now[0],
      wy = now[1],
      z = now[2];
    // The slide's direction in the world.
    mouthToLocal(u + slideU, y + slideY, w, point);
    v.frame.toWorld(point[0], point[1], point[2], before);
    const speed = SPILL_SPEED * (1 + 0.6 * this.random());
    this.spawn(
      x,
      wy,
      z,
      (x - bx) / dt + (before[0] - x) * speed,
      (wy - by) / dt + (before[1] - wy) * speed,
      (z - bz) / dt + (before[2] - z) * speed,
      volume,
      v,
    );
  }

  // What has gone over a rim leaves as parcels of one size, and the last of a
  // stream as a smaller one.
  spillLoad(v, dt) {
    const { pending, flowing } = v.load;
    for (const [rim, amounts] of pending.entries())
      for (let n = 0; n < amounts.length; n++) {
        while (amounts[n] >= GRAIN) {
          amounts[n] -= GRAIN;
          this.emit(v, rim, n, GRAIN, dt);
        }
        if (amounts[n] > 0 && !flowing[rim][n]) {
          this.emit(v, rim, n, amounts[n], dt);
          amounts[n] = 0;
        }
      }
  }

  // Falling sand touches nothing on the way down. It joins a bucket it falls into,
  // if there is room, or the bed where it lands.
  moveParcels(dt) {
    const p = this.pos,
      vel = this.vel,
      s = this.surf,
      l = this.l3,
      g = WORLD.gravity;
    for (let i = 0; i < MAX; i++) {
      if (!this.alive[i]) continue;
      const k = 3 * i;
      vel[k + 2] -= g * dt;
      p[k] = clamp(
        p[k] + clamp(vel[k], -MAX_SPEED, MAX_SPEED) * dt,
        WORLD.minX + R,
        WORLD.maxX - R,
      );
      p[k + 1] = clamp(
        p[k + 1] + clamp(vel[k + 1], -MAX_SPEED, MAX_SPEED) * dt,
        WORLD.minY + R,
        WORLD.maxY - R,
      );
      p[k + 2] += clamp(vel[k + 2], -MAX_SPEED, MAX_SPEED) * dt;
      let caught = false;
      for (const v of this.vehicles) {
        const c = v.frame.centre,
          ex = p[k] - c[0],
          ey = p[k + 1] - c[1],
          ez = p[k + 2] - c[2];
        if (ex * ex + ey * ey + ez * ez > NEAR * NEAR) {
          if (this.near[i] && this.holder[i] === v.slot) this.near[i] = 0;
          continue;
        }
        v.frame.toLocal(p[k], p[k + 1], p[k + 2], l);
        if (insideCavity(l[0], l[1], l[2])) {
          this.volumes[i] -= v.load.add(l[0], l[1], l[2], this.volumes[i]);
          if (this.volumes[i] <= 0) {
            this.release(i);
            caught = true;
            break;
          }
        }
      }
      if (caught) continue;
      this.terrain.sample(p[k], p[k + 1], s);
      if (p[k + 2] - R <= s[0]) {
        this.terrain.deposit(p[k], p[k + 1], this.volumes[i]);
        this.release(i);
      }
    }
  }

  substep(dt) {
    this.terrain.clearCeilings();
    for (const v of this.vehicles) {
      v.prevFrame.copy(v.frame);
      this.advanceMachine(dt, v);
      this.pressSand(v);
      v.bucket = bucketPose(v.machine);
      v.frame.set(v.bucket);
      this.cutTerrain(v);
      v.load.relax(v.frame);
      this.spillLoad(v, dt);
    }
    this.moveParcels(dt);
  }

  step(dt = 1 / 30) {
    const idle = this.vehicles.every(
      (v) => v.estop || Object.values(v.axes).every((value) => value === 0),
    );
    if (this.resting && idle) {
      this.tick++;
      for (const v of this.vehicles)
        if (v.stats.blocked || v.stats.obstacle)
          v.stats = { ...v.stats, blocked: false, obstacle: null };
      return;
    }
    for (const v of this.vehicles) {
      v.blocked = false;
      v.obstacle = null;
      v.load.coverBy(v.frame, this.terrain, v.touchingBed);
    }
    for (let i = 0; i < SUBSTEPS; i++) this.substep(dt / SUBSTEPS);
    this.terrain.relax(3, 0.5);
    this.tick++;
    this.world = this.measure();
    this.resting =
      idle &&
      !this.grains &&
      !this.terrain.activeCount &&
      this.vehicles.every((v) => !v.chassisMoving && v.load.settled);
  }

  // What is true of the whole world. Each machine's own numbers go in its stats.
  measure() {
    let landing = 0;
    const p = this.pos,
      z = POUR_ZONE;
    for (let i = 0; i < MAX; i++) {
      if (!this.alive[i]) continue;
      const k = 3 * i;
      if (
        p[k] > z.minX &&
        p[k] < z.maxX &&
        p[k + 1] > z.minY &&
        p[k + 1] < z.maxY &&
        p[k + 2] < 40
      )
        landing += this.volumes[i];
    }
    const cm3 = (mm3) => Math.round(mm3 / 100) / 10;
    for (const vehicle of this.vehicles)
      vehicle.stats = {
        load: cm3(vehicle.load.total),
        blocked: vehicle.blocked,
        obstacle: vehicle.obstacle,
      };
    return {
      deposited: cm3(this.terrain.volumeIn(z) + landing),
      grains: this.grains,
    };
  }

  // Falling parcels for the network: [slot, x, y, z] as Int16 in 0.1 mm units. The
  // machines can be far apart, so parcels are grouped by the bucket they are near
  // and by a block of the world, with positions relative to the block's centre.
  // `groups` holds five numbers for each: the centre (x, y, z), the parcel count
  // and the id of the vehicle they are near (0 for none).
  packGrains() {
    const p = this.pos,
      scale = 1 / SAND.positionQuantum,
      found = new Map();
    for (let i = 0; i < MAX; i++) {
      if (!this.alive[i]) continue;
      const k = 3 * i,
        bx = Math.floor((p[k] - WORLD.minX) / GROUP_SPAN),
        by = Math.floor((p[k + 1] - WORLD.minY) / GROUP_SPAN),
        bz = Math.floor(p[k + 2] / GROUP_SPAN),
        holder = this.near[i] ? this.holder[i] + 1 : 0,
        key = holder + 256 * (bx + 16 * (by + 16 * (bz + 64)));
      let group = found.get(key);
      if (!group)
        found.set(
          key,
          (group = {
            x: WORLD.minX + (bx + 0.5) * GROUP_SPAN,
            y: WORLD.minY + (by + 0.5) * GROUP_SPAN,
            z: (bz + 0.5) * GROUP_SPAN,
            id: holder && this.bySlot[holder - 1] ? this.bySlot[holder - 1].id : 0,
            members: [],
          }),
        );
      group.members.push(i);
    }
    const grains = new Int16Array(4 * this.grains),
      groups = new Int32Array(5 * found.size);
    let o = 0,
      g = 0;
    for (const { x, y, z, id, members } of found.values()) {
      groups.set([x, y, z, members.length, id], g);
      g += 5;
      for (const i of members) {
        const k = 3 * i;
        grains[o++] = i;
        grains[o++] = Math.round((p[k] - x) * scale);
        grains[o++] = Math.round((p[k + 1] - y) * scale);
        grains[o++] = Math.round((p[k + 2] - z) * scale);
      }
    }
    return { grains, groups };
  }
}

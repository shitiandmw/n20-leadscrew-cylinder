import { solve } from "../shared/kinematics.js";
import { CONFIG } from "../shared/config.js";
import {
  WORLD,
  SAND,
  BUCKET,
  POUR_ZONE,
  clamp,
  neutral,
  crawlerExtent,
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
  WALLS,
  TEETH,
  REGION,
  REGION_EDGE_MOUTH,
  CENTROID,
  BOUNDING_RADIUS,
  insidePolygon,
  insideCavity,
  firstCrossing,
  CROSS_MOUTH,
  CROSS_CHEEK,
} from "../shared/bucket.js";

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
  D = 2 * R,
  GRAIN = SAND.grainVolume,
  MAX = SAND.maxGrains,
  BUDGET = SAND.grainBudget,
  SHELL = BUCKET.shellHalfThickness,
  // Centre-to-shell-centreline contact distance and lateral cheek limits.
  RR = R + SHELL,
  INNER = BUCKET.innerHalfWidth - R,
  OUTER = BUCKET.outerHalfWidth + R,
  ALL_WALLS = [...WALLS, TEETH],
  SUBSTEPS = 4,
  ITERATIONS = 3,
  // Coulomb friction (static, kinetic): sand on sand ~32 degrees internal
  // friction; sand on the bucket's printed plastic and steel teeth.
  MU_S = 0.62,
  MU_K = 0.5,
  MU_BS = 0.55,
  MU_BK = 0.4,
  // Height-based mass scaling keeps deep stacks of grains from springing.
  STACK = 0.08,
  MAX_SPEED = 2500,
  HASH = 1 << 15,
  MASK = HASH - 1,
  NEAR = Math.hypot(BOUNDING_RADIUS, BUCKET.outerHalfWidth) + RR + 6,
  TRACK_HALF_LENGTH = CONFIG.wheel_centres / 2 + CONFIG.sprocket_tip_radius_mm,
  TRACK_Y = CONFIG.track_centres / 2,
  SHOE_HALF = CONFIG.shoe_width / 2,
  BELLY_CLEARANCE = 40,
  // Full track speed (mm/s), about 12 km/h at 1:15: a game's travel speed.
  TRACK_SPEED = 220,
  // Loose sand gives this far under a shoe the first time it is driven over.
  SHOE_SINK = 4,
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
  UPPER_BOTTOM = 110;
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

// Hybrid sand model used by excavation simulators: the bulk of the sand is a
// height field that slumps to its angle of repose; material the bucket scoops,
// or that is falling, becomes free grains solved with position-based granular
// dynamics (contacts with Coulomb friction). Grains that come to rest on the
// bed rejoin it. Bucket contacts remember which side of every wall a grain is
// on, so grains can enter or leave the cavity only through its open mouth.
export class SandSimulation {
  constructor() {
    this.terrain = new Terrain();
    this.pos = new Float64Array(3 * MAX);
    this.prev = new Float64Array(3 * MAX);
    this.vel = new Float64Array(3 * MAX);
    this.local = new Float64Array(3 * MAX);
    this.localStart = new Float64Array(3 * MAX);
    this.alive = new Uint8Array(MAX);
    this.side = new Uint8Array(MAX);
    this.sideStart = new Uint8Array(MAX);
    this.near = new Uint8Array(MAX);
    this.touchAge = new Uint8Array(MAX);
    this.rest = new Uint8Array(MAX);
    this.ground = new Uint8Array(MAX);
    this.weight = new Float64Array(MAX);
    this.list = new Int32Array(MAX);
    this.freeList = new Int32Array(MAX);
    this.cellOf = new Int32Array(3 * MAX);
    this.hashOf = new Int32Array(MAX);
    this.start = new Int32Array(HASH + 1);
    this.fill = new Int32Array(HASH);
    this.entries = new Int32Array(MAX);
    this.pairs = new Int32Array(MAX * 24);
    this.cutClass = new Uint8Array((CUT_MASK + 1) * (CUT_MASK + 1));
    this.footLow = new Float64Array(FOOT * FOOT);
    this.frame = new BucketFrame();
    this.prevFrame = new BucketFrame();
    this.testFrame = new BucketFrame();
    this.v3 = new Float64Array(3);
    this.w3 = new Float64Array(3);
    this.l3 = new Float64Array(3);
    this.m3 = new Float64Array(3);
    this.hit = new Float64Array(3);
    this.col = new Float64Array(4);
    this.surf = new Float64Array(3);
    this.normal = new Float64Array(3);
    this.fit = { b: 0, c: 0, h: new Float64Array(2 * SAMPLE_U.length) };
    this.penetration = 0;
    this.reset();
  }

  reset() {
    this.machine = initialMachine();
    this.axes = neutral();
    this.speed = 0.65;
    this.estop = false;
    this.tick = 0;
    this.resting = false;
    this.blocked = false;
    this.obstacle = null;
    this.chassisMoving = false;
    this.terrain.copyFrom(initialTerrain());
    this.cutClass.fill(0);
    this.alive.fill(0);
    this.grains = 0;
    this.listCount = 0;
    for (let i = 0; i < MAX; i++) this.freeList[i] = i;
    this.freeHead = 0;
    this.freeCount = MAX;
    this.seed = 60;
    this.converted = 0;
    this.bucket = bucketPose(this.machine);
    this.frame.set(this.bucket);
    this.prevFrame.set(this.bucket);
    this.stats = this.measure();
  }

  random() {
    this.seed = (1664525 * this.seed + 1013904223) >>> 0;
    return this.seed / 4294967296 - 0.5;
  }

  // Exact bulk sand volume: bed + free grains (mm^3).
  totalVolume() {
    return this.terrain.volume() + this.grains * GRAIN;
  }

  spawn(x, y, z, vx, vy, vz, side, local) {
    if (!this.freeCount) return -1;
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
    this.side[i] = side;
    this.near[i] = local ? 1 : 0;
    if (local)
      for (let d = 0; d < 3; d++)
        this.local[k + d] = this.localStart[k + d] = local[d];
    this.touchAge[i] = 0;
    this.rest[i] = 0;
    this.ground[i] = 0;
    return i;
  }

  // How many more grains the solver can take on within its time budget.
  spawnRoom() {
    return Math.min(this.freeCount, BUDGET - this.grains);
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
  restChassis(dt, m) {
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
    this.chassisMoving =
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
  advanceMachine(dt) {
    const a = this.estop ? neutral() : this.axes,
      m = this.machine,
      speed = this.speed;
    let clearance = this.bucketClearance(m);
    const accept = () => {
      const next = this.bucketClearance(m);
      if (next < 0 && next < clearance - 1e-9) {
        this.blocked = true;
        return false;
      }
      clearance = next;
      return true;
    };
    this.bodyMoved = false;
    for (const [i, key] of ["boom", "stick", "bucket"].entries()) {
      const old = m.strokes[i];
      m.strokes[i] = clamp(old + a[key] * 13 * speed * dt, 0, 60);
      if (m.strokes[i] !== old && !accept()) m.strokes[i] = old;
    }
    const slew = m.slew;
    m.slew = clamp(slew + a.slew * 30 * speed * dt, -150, 150);
    if (m.slew !== slew) {
      if (accept()) this.bodyMoved = true;
      else m.slew = slew;
    }
    const l = a.leftTrack * TRACK_SPEED * speed,
      r = a.rightTrack * TRACK_SPEED * speed;
    this.drove = false;
    if (!l && !r) {
      this.restChassis(dt, m);
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
    if (!obstacle) {
      const fit = this.fitFootprint(m.x, m.y, m.heading),
        tilt = Math.atan(Math.hypot(fit.b, fit.c));
      if (tilt > MAX_TILT) {
        const was = this.fitFootprint(before.x, before.y, before.heading);
        if (tilt > Math.atan(Math.hypot(was.b, was.c))) obstacle = "steep";
      }
    }
    if (obstacle) {
      this.obstacle = obstacle;
      Object.assign(m, before);
      this.restChassis(dt, m);
      return;
    }
    this.restChassis(dt, m);
    if (!accept()) {
      Object.assign(m, before);
      return;
    }
    m.tracks[0] += l * dt;
    m.tracks[1] += r * dt;
    this.drove = true;
    this.bodyMoved = true;
  }

  // Sand displaced by the machine goes off to the side of its tracks, spread
  // over a band so it never stacks up in one column of cells.
  displace(cell, excess, u, side, ch, sh) {
    const t = this.terrain,
      m = this.machine,
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

  // Moving tracks press a shallow rut into loose sand; the lower frame and the
  // upper body push aside whatever stands in their way. Nothing here runs while
  // the machine stands still, so slumping sand can come to rest against it.
  pressSand() {
    const m = this.machine,
      t = this.terrain,
      ch = Math.cos(m.heading),
      sh = Math.sin(m.heading),
      b = Math.tan(m.pitch),
      c = Math.tan(m.roll) / Math.cos(m.pitch);
    if (this.drove) {
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
          this.displace(cell, excess, u, v < 0 ? -1 : 1, ch, sh);
        }
    }
    if (!this.bodyMoved) return;
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
        if (excess > 0.01) this.displace(cell, excess, u, v < 0 ? -1 : 1, ch, sh);
      }
  }

  // Cells pushed by a closed wall move along the bucket's motion until they
  // clear its footprint; relaxation then shapes the berm.
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

  // Excavate the bed where the bucket occupies it. Sand that reaches the
  // cutting region through the mouth or teeth becomes grains in the cavity;
  // sand met by a closed wall or cheek is bulldozed; overburden resting on
  // a buried bucket becomes grains above it.
  cutTerrain(dt) {
    const frame = this.frame,
      prev = this.prevFrame,
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
    if (highest < lowest - SHELL) {
      for (let j = j0; j < j0 + fh; j++)
        for (let i = i0; i < i0 + fw; i++) this.cutClass[cutIndex(i, j)] = 0;
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
          this.cutClass[cutIndex(i, j)] = 0;
          continue;
        }
        frame.column(cx, cy, col);
        const surface = t.surface(cell),
          low = col[0] - (col[2] ? 0 : SHELL),
          high = col[1] + (col[3] ? 0 : SHELL);
        const sand = t.get(cell);
        if (surface <= low + 0.05 || sand <= 1e-9) {
          this.cutClass[cutIndex(i, j)] = 0;
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
        let type = this.cutClass[cutIndex(i, j)];
        const entered = this.regionEntry(before, now);
        if (entered) type = entered;
        if (!type) type = col[2] ? 1 : 2;
        this.cutClass[cutIndex(i, j)] = type;
        if (inside > 0) {
          if (type === 1 && this.spawnRoom() > 0) {
            const n = Math.min(
              this.spawnRoom(),
              10,
              Math.floor((inside * CELL_AREA) / GRAIN),
            );
            const spawned = n ? this.spawnInCavity(cx, cy, low, top, n, dt) : 0;
            if (spawned) {
              t.add(cell, (-spawned * GRAIN) / CELL_AREA);
              t.touch(cell);
            }
          } else {
            // Push along the bucket's horizontal motion at this point.
            frame.toWorld(now[0], now[1], now[2], w);
            prev.toWorld(now[0], now[1], now[2], before);
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
            );
            // Sand flows ahead of and around a pushing bucket: spread it widely,
            // so it forms a broad berm instead of a spike.
            const side = 130 * this.random(),
              ahead = 8 + 80 * (this.random() + 0.5) ** 2;
            t.add(cell, -inside);
            t.touch(cell);
            t.deposit(
              cellX(target & (NX - 1)) + (dx / length) * ahead - (dy / length) * side,
              cellY(Math.floor(target / NX)) +
                (dy / length) * ahead +
                (dx / length) * side,
              inside * CELL_AREA,
            );
          }
        }
        if (above > 0) {
          const n = Math.min(
            this.spawnRoom(),
            10,
            Math.floor((above * CELL_AREA) / GRAIN),
          );
          let spawned = 0;
          for (let k = 0; k < n; k++) {
            const x = cx + this.random() * CELL * 0.8,
              y = cy + this.random() * CELL * 0.8,
              z = col[1] + RR + 0.5 + k * D * 0.95;
            frame.toLocal(x, y, z, now);
            const inCavity = insideCavity(now[0], now[1], now[2]) ? 1 : 0;
            if (this.spawn(x, y, z, 0, 0, 0, inCavity, now) >= 0) spawned++;
          }
          if (spawned) {
            t.add(cell, (-spawned * GRAIN) / CELL_AREA);
            t.touch(cell);
          }
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

  // Scooped sand starts inside the cavity, moving with the bucket.
  spawnInCavity(cx, cy, low, top, n, dt) {
    const frame = this.frame,
      prev = this.prevFrame,
      l = this.l3,
      w = this.w3,
      b = this.v3;
    const span = Math.max(0, top - low - D);
    let spawned = 0;
    for (let k = 0; k < n; k++) {
      const z = low + R + (n > 1 ? (span * k) / (n - 1) : span / 2);
      frame.toLocal(
        cx + this.random() * CELL * 0.8,
        cy + this.random() * CELL * 0.8,
        z,
        l,
      );
      l[1] = clamp(l[1], -INNER, INNER);
      for (let iteration = 0; iteration < 8; iteration++) {
        if (!insidePolygon(l[0], l[2])) {
          l[0] += (CENTROID[0] - l[0]) * 0.35;
          l[2] += (CENTROID[1] - l[2]) * 0.35;
          continue;
        }
        let moved = false;
        for (const wall of WALLS) {
          const t =
            ((l[0] - wall.ax) * wall.dx + (l[2] - wall.az) * wall.dz) /
            wall.len2;
          if (t <= 0 || t >= 1) continue;
          const signed =
              (l[0] - wall.ax) * wall.nx + (l[2] - wall.az) * wall.nz,
            reach = R + wall.inner;
          if (signed < reach) {
            l[0] += wall.nx * (reach - signed);
            l[2] += wall.nz * (reach - signed);
            moved = true;
          }
        }
        if (!moved) break;
      }
      if (!insideCavity(l[0], l[1], l[2])) continue;
      frame.toWorld(l[0], l[1], l[2], w);
      prev.toWorld(l[0], l[1], l[2], b);
      spawned++;
      this.spawn(
        w[0],
        w[1],
        w[2],
        (w[0] - b[0]) / dt,
        (w[1] - b[1]) / dt,
        (w[2] - b[2]) / dt,
        1,
        l,
      );
    }
    return spawned;
  }

  buildPairs() {
    const p = this.pos,
      list = this.list,
      n = this.listCount,
      start = this.start,
      fill = this.fill,
      entries = this.entries,
      cellOf = this.cellOf,
      hashOf = this.hashOf;
    start.fill(0);
    const key = (x, y, z) =>
      (Math.imul(x, 73856093) ^
        Math.imul(y, 19349663) ^
        Math.imul(z, 83492791)) &
      MASK;
    for (let a = 0; a < n; a++) {
      const i = list[a],
        k = 3 * i,
        x = Math.floor(p[k] / D),
        y = Math.floor(p[k + 1] / D),
        z = Math.floor(p[k + 2] / D);
      cellOf[k] = x;
      cellOf[k + 1] = y;
      cellOf[k + 2] = z;
      const h = key(x, y, z);
      hashOf[i] = h;
      start[h + 1]++;
    }
    for (let h = 0; h < HASH; h++) start[h + 1] += start[h];
    fill.set(start.subarray(0, HASH));
    for (let a = 0; a < n; a++) {
      const i = list[a];
      entries[fill[hashOf[i]]++] = i;
    }
    let pairs = this.pairs,
      count = 0;
    const reach = (D + 1) * (D + 1);
    for (let a = 0; a < n; a++) {
      const i = list[a],
        k = 3 * i,
        cx = cellOf[k],
        cy = cellOf[k + 1],
        cz = cellOf[k + 2];
      for (let dz = -1; dz <= 1; dz++)
        for (let dy = -1; dy <= 1; dy++)
          for (let dx = -1; dx <= 1; dx++) {
            const x = cx + dx,
              y = cy + dy,
              z = cz + dz,
              h = key(x, y, z);
            for (let e = start[h], end = start[h + 1]; e < end; e++) {
              const j = entries[e];
              if (j <= i) continue;
              const m = 3 * j;
              if (cellOf[m] !== x || cellOf[m + 1] !== y || cellOf[m + 2] !== z)
                continue;
              const ex = p[k] - p[m],
                ey = p[k + 1] - p[m + 1],
                ez = p[k + 2] - p[m + 2];
              if (ex * ex + ey * ey + ez * ez >= reach) continue;
              if (count + 2 > pairs.length) {
                const grown = new Int32Array(pairs.length * 2);
                grown.set(pairs);
                pairs = this.pairs = grown;
              }
              pairs[count++] = i;
              pairs[count++] = j;
            }
          }
    }
    this.pairCount = count;
  }

  solvePairs() {
    const p = this.pos,
      q = this.prev,
      wt = this.weight,
      pairs = this.pairs,
      count = this.pairCount;
    for (let e = 0; e < count; e += 2) {
      const i = pairs[e],
        j = pairs[e + 1],
        k = 3 * i,
        m = 3 * j;
      const dx = p[k] - p[m],
        dy = p[k + 1] - p[m + 1],
        dz = p[k + 2] - p[m + 2],
        d2 = dx * dx + dy * dy + dz * dz;
      if (d2 >= D * D || d2 < 1e-12) continue;
      const d = Math.sqrt(d2),
        pen = D - d,
        nx = dx / d,
        ny = dy / d,
        nz = dz / d,
        si = wt[i] / (wt[i] + wt[j]),
        sj = 1 - si;
      p[k] += nx * pen * si;
      p[k + 1] += ny * pen * si;
      p[k + 2] += nz * pen * si;
      p[m] -= nx * pen * sj;
      p[m + 1] -= ny * pen * sj;
      p[m + 2] -= nz * pen * sj;
      // Coulomb friction on the relative tangential displacement.
      const rx = p[k] - q[k] - p[m] + q[m],
        ry = p[k + 1] - q[k + 1] - p[m + 1] + q[m + 1],
        rz = p[k + 2] - q[k + 2] - p[m + 2] + q[m + 2],
        rn = rx * nx + ry * ny + rz * nz,
        tx = rx - rn * nx,
        ty = ry - rn * ny,
        tz = rz - rn * nz,
        lt = Math.sqrt(tx * tx + ty * ty + tz * tz);
      if (lt < 1e-9) continue;
      const f = lt < MU_S * pen ? 1 : (MU_K * pen) / lt;
      p[k] -= tx * f * si;
      p[k + 1] -= ty * f * si;
      p[k + 2] -= tz * f * si;
      p[m] += tx * f * sj;
      p[m + 1] += ty * f * sj;
      p[m + 2] += tz * f * sj;
    }
  }

  // Grain against the sand bed (with friction) and the hard ground underneath.
  collideBed(i) {
    const p = this.pos,
      q = this.prev,
      k = 3 * i,
      s = this.surf;
    this.terrain.sample(p[k], p[k + 1], s);
    const nz = 1 / Math.sqrt(1 + s[1] * s[1] + s[2] * s[2]),
      nx = -s[1] * nz,
      ny = -s[2] * nz,
      distance = (p[k + 2] - s[0]) * nz;
    if (distance >= R) return;
    const pen = R - distance;
    p[k] += nx * pen;
    p[k + 1] += ny * pen;
    p[k + 2] += nz * pen;
    this.ground[i] = 1;
    const rx = p[k] - q[k],
      ry = p[k + 1] - q[k + 1],
      rz = p[k + 2] - q[k + 2],
      rn = rx * nx + ry * ny + rz * nz,
      tx = rx - rn * nx,
      ty = ry - rn * ny,
      tz = rz - rn * nz,
      lt = Math.sqrt(tx * tx + ty * ty + tz * tz);
    if (lt < 1e-9) return;
    const f = lt < MU_S * pen ? 1 : (MU_K * pen) / lt;
    p[k] -= tx * f;
    p[k + 1] -= ty * f;
    p[k + 2] -= tz * f;
  }

  // Push a local position out of every shell plate and the tooth row, onto
  // the side of each plate that the remembered position is on. Returns true
  // on contact; the last contact normal and depth are kept for friction.
  wallPass(l, memory, side) {
    let contact = false;
    // The shell only exists between the cheek plates. Past their outer faces
    // nothing but the plates can touch a grain: treating the shell as wider
    // would hold up a grain resting against a tilted cheek from outside.
    if (Math.abs(l[1]) > BUCKET.outerHalfWidth) return false;
    for (const wall of ALL_WALLS) {
      const t =
        ((l[0] - wall.ax) * wall.dx + (l[2] - wall.az) * wall.dz) / wall.len2;
      if (t > 0 && t < 1) {
        const tm =
            ((memory[0] - wall.ax) * wall.dx +
              (memory[2] - wall.az) * wall.dz) /
            wall.len2,
          signed = (l[0] - wall.ax) * wall.nx + (l[2] - wall.az) * wall.nz;
        let sign;
        if (tm > 0 && tm < 1)
          sign =
            (memory[0] - wall.ax) * wall.nx + (memory[2] - wall.az) * wall.nz >=
            0
              ? 1
              : -1;
        else sign = signed >= 0 ? 1 : -1;
        const reach = R + (sign > 0 ? wall.inner : wall.outer);
        if (sign * signed < reach) {
          const move = sign * reach - signed;
          l[0] += wall.nx * move;
          l[2] += wall.nz * move;
          contact = true;
          this.normal[0] = sign * wall.nx;
          this.normal[2] = sign * wall.nz;
          this.penetration = Math.abs(move);
        }
      } else {
        const qx = t <= 0 ? wall.ax : wall.ax + wall.dx,
          qz = t <= 0 ? wall.az : wall.az + wall.dz,
          vx = l[0] - qx,
          vz = l[2] - qz,
          d = Math.hypot(vx, vz),
          reach = R + (side ? wall.inner : wall.outer);
        if (d < reach && d > 1e-9) {
          l[0] = qx + (vx / d) * reach;
          l[2] = qz + (vz / d) * reach;
          contact = true;
          this.normal[0] = vx / d;
          this.normal[2] = vz / d;
          this.penetration = reach - d;
        }
      }
    }
    return contact;
  }

  // Bucket shell, teeth and cheek plates in the bucket frame. Each wall is
  // two-sided: a grain is held on the side its last valid position was on,
  // so fast grains or a fast bucket cannot tunnel through the 4 mm shell.
  // A grain's cavity membership changes only if its path relative to the
  // bucket crosses the open mouth; any other change is rolled back.
  collideBucket(i) {
    const p = this.pos,
      k = 3 * i,
      frame = this.frame,
      c = frame.centre,
      ex = p[k] - c[0],
      ey = p[k + 1] - c[1],
      ez = p[k + 2] - c[2];
    if (ex * ex + ey * ey + ez * ez > NEAR * NEAR) {
      this.near[i] = 0;
      this.side[i] = 0;
      return;
    }
    const l = this.l3,
      m = this.local,
      start = this.localStart,
      hit = this.hit,
      memory = this.m3;
    frame.toLocal(p[k], p[k + 1], p[k + 2], l);
    if (!this.near[i]) {
      this.near[i] = 1;
      for (let d = 0; d < 3; d++) m[k + d] = start[k + d] = l[d];
    }
    memory[0] = m[k];
    memory[1] = m[k + 1];
    memory[2] = m[k + 2];
    // The remembered position is always valid; its side is authoritative.
    const before = insideCavity(memory[0], memory[1], memory[2]) ? 1 : 0;
    let side = before;
    if ((insideCavity(l[0], l[1], l[2]) ? 1 : 0) !== before) {
      const type = firstCrossing(memory, l, hit);
      if (type === CROSS_MOUTH) side = 1 - before;
      else if (type === CROSS_CHEEK) l[1] = hit[2] * (before ? INNER : OUTER);
    }
    const contact = this.wallPass(l, memory, side),
      normal = this.normal;
    let touching = contact,
      pen = this.penetration,
      nlx = normal[0],
      nly = 0,
      nlz = normal[2];
    if (side) {
      if (l[1] > INNER || l[1] < -INNER) {
        const limit = l[1] > 0 ? INNER : -INNER;
        pen = Math.abs(l[1] - limit);
        l[1] = limit;
        touching = true;
        nlx = 0;
        nly = limit > 0 ? -1 : 1;
        nlz = 0;
      }
    } else if (Math.abs(l[1]) < OUTER && insidePolygon(l[0], l[2])) {
      const sign = (l[1] || memory[1] || 1) > 0 ? 1 : -1;
      pen = OUTER - Math.abs(l[1]);
      l[1] = sign * OUTER;
      touching = true;
      nlx = 0;
      nly = sign;
      nlz = 0;
    }
    if (touching) {
      // Friction on the grain's motion relative to the bucket surface.
      const rx = l[0] - start[k],
        ry = l[1] - start[k + 1],
        rz = l[2] - start[k + 2],
        rn = rx * nlx + ry * nly + rz * nlz,
        tx = rx - rn * nlx,
        ty = ry - rn * nly,
        tz = rz - rn * nlz,
        lt = Math.sqrt(tx * tx + ty * ty + tz * tz);
      if (lt > 1e-9) {
        const f = lt < MU_BS * pen ? 1 : (MU_BK * pen) / lt;
        l[0] -= tx * f;
        l[1] -= ty * f;
        l[2] -= tz * f;
        // Sliding along one wall must not cut into the next at a corner.
        if (contact) this.wallPass(l, memory, side);
      }
      this.touchAge[i] = 0;
    }
    const after = insideCavity(l[0], l[1], l[2]) ? 1 : 0;
    if (after === before) side = before;
    else if (firstCrossing(memory, l, hit) === CROSS_MOUTH) {
      side = after;
      if (side) l[1] = clamp(l[1], -INNER, INNER);
    } else {
      l[0] = memory[0];
      l[1] = memory[1];
      l[2] = memory[2];
      side = before;
    }
    this.side[i] = side;
    m[k] = l[0];
    m[k + 1] = l[1];
    m[k + 2] = l[2];
    frame.toWorld(l[0], l[1], l[2], this.w3);
    p[k] = this.w3[0];
    p[k + 1] = this.w3[1];
    p[k + 2] = this.w3[2];
  }

  solveGrains(dt) {
    const p = this.pos,
      q = this.prev,
      v = this.vel,
      list = this.list,
      g = WORLD.gravity,
      stackBase = this.machine.z;
    let n = 0;
    for (let i = 0; i < MAX; i++) if (this.alive[i]) list[n++] = i;
    this.listCount = n;
    if (!n) return;
    for (let a = 0; a < n; a++) {
      const i = list[a],
        k = 3 * i;
      v[k + 2] -= g * dt;
      for (let d = 0; d < 3; d++) {
        q[k + d] = p[k + d];
        p[k + d] += clamp(v[k + d], -MAX_SPEED, MAX_SPEED) * dt;
        this.localStart[k + d] = this.local[k + d];
      }
      this.ground[i] = 0;
      this.sideStart[i] = this.side[i];
      if (this.touchAge[i] < 255) this.touchAge[i]++;
      // Inverse mass rises with height: lower grains are heavier, so an
      // upper grain takes most of a contact correction.
      this.weight[i] = Math.exp(STACK * clamp(p[k + 2] - stackBase, -300, 900));
    }
    this.buildPairs();
    for (let iteration = 0; iteration < ITERATIONS; iteration++) {
      this.solvePairs();
      for (let a = 0; a < n; a++) {
        const i = list[a],
          k = 3 * i;
        p[k] = clamp(p[k], WORLD.minX + R, WORLD.maxX - R);
        p[k + 1] = clamp(p[k + 1], WORLD.minY + R, WORLD.maxY - R);
        if (!this.side[i]) this.collideBed(i);
        this.collideBucket(i);
      }
    }
    for (let a = 0; a < n; a++) {
      const i = list[a],
        k = 3 * i;
      // Grains at rest in the bucket ride with it exactly instead of jittering.
      if (this.side[i] && this.sideStart[i] && this.near[i]) {
        const ux = this.local[k] - this.localStart[k],
          uy = this.local[k + 1] - this.localStart[k + 1],
          uz = this.local[k + 2] - this.localStart[k + 2];
        if (ux * ux + uy * uy + uz * uz < 0.006 * 0.006) {
          this.frame.toWorld(
            this.localStart[k],
            this.localStart[k + 1],
            this.localStart[k + 2],
            this.w3,
          );
          for (let d = 0; d < 3; d++) {
            this.local[k + d] = this.localStart[k + d];
            p[k + d] = this.w3[d];
          }
        }
      }
      for (let d = 0; d < 3; d++)
        v[k + d] = clamp(
          ((p[k + d] - q[k + d]) / dt) * 0.998,
          -MAX_SPEED,
          MAX_SPEED,
        );
    }
    this.settleGrains();
  }

  // Grains resting on the bed (and clear of the bucket) rejoin it.
  settleGrains() {
    const p = this.pos,
      v = this.vel,
      list = this.list,
      n = this.listCount,
      s = this.surf,
      col = this.col;
    for (let a = 0; a < n; a++) {
      const i = list[a],
        k = 3 * i;
      if (this.side[i]) {
        this.rest[i] = 0;
        continue;
      }
      if (this.ground[i] && this.touchAge[i] < 2) {
        // Squeezed between the bucket and the bed: becomes bed material that
        // the cut then bulldozes or scoops.
        this.terrain.sample(p[k], p[k + 1], s);
        if (p[k + 2] < s[0]) {
          this.terrain.deposit(p[k], p[k + 1], GRAIN);
          this.release(i);
          this.converted++;
          continue;
        }
      }
      const speed2 = v[k] * v[k] + v[k + 1] * v[k + 1] + v[k + 2] * v[k + 2];
      if (!this.ground[i] || this.touchAge[i] < 8 || speed2 > 30 * 30) {
        this.rest[i] = 0;
        continue;
      }
      if (++this.rest[i] < 6) continue;
      if (
        this.frame.column(p[k], p[k + 1], col) &&
        col[0] < p[k + 2] + R + 10
      ) {
        this.rest[i] = 0;
        continue;
      }
      this.terrain.deposit(p[k], p[k + 1], GRAIN);
      this.release(i);
      this.converted++;
    }
  }

  substep(dt) {
    this.prevFrame.copy(this.frame);
    this.advanceMachine(dt);
    this.pressSand();
    this.bucket = bucketPose(this.machine);
    this.frame.set(this.bucket);
    this.cutTerrain(dt);
    this.solveGrains(dt);
  }

  step(dt = 1 / 30) {
    const idle =
      this.estop || Object.values(this.axes).every((value) => value === 0);
    if (this.resting && idle) {
      this.tick++;
      if (this.stats.blocked || this.stats.obstacle)
        this.stats = { ...this.stats, blocked: false, obstacle: null };
      return;
    }
    this.blocked = false;
    this.obstacle = null;
    for (let i = 0; i < SUBSTEPS; i++) this.substep(dt / SUBSTEPS);
    this.terrain.relax(3, 0.5);
    this.tick++;
    this.stats = this.measure();
    this.resting =
      idle &&
      !this.grains &&
      !this.terrain.activeCount &&
      !this.chassisMoving;
  }

  measure() {
    let carried = 0,
      active = 0,
      falling = 0;
    const p = this.pos,
      v = this.vel,
      z = POUR_ZONE;
    for (let i = 0; i < MAX; i++) {
      if (!this.alive[i]) continue;
      const k = 3 * i;
      if (this.side[i]) carried++;
      if (Math.hypot(v[k], v[k + 1], v[k + 2]) > 35) active++;
      if (
        !this.side[i] &&
        p[k] > z.minX &&
        p[k] < z.maxX &&
        p[k + 1] > z.minY &&
        p[k + 1] < z.maxY &&
        p[k + 2] < 40
      )
        falling++;
    }
    const cm3 = (mm3) => Math.round(mm3 / 100) / 10;
    return {
      carried,
      load: cm3(carried * GRAIN),
      deposited: cm3(this.terrain.volumeIn(z) + falling * GRAIN),
      grains: this.grains,
      active,
      blocked: this.blocked,
      obstacle: this.obstacle,
    };
  }

  // Free grains for the network: [slot, x, y, z] as Int16 in 0.1 mm units,
  // relative to whole-millimetre origin, which is written to the given array.
  packGrains(origin) {
    const m = this.machine,
      out = new Int16Array(4 * this.grains),
      scale = 1 / SAND.positionQuantum,
      p = this.pos;
    origin[0] = Math.round(m.x);
    origin[1] = Math.round(m.y);
    origin[2] = Math.round(m.z);
    let o = 0;
    for (let i = 0; i < MAX && o < out.length; i++) {
      if (!this.alive[i]) continue;
      const k = 3 * i;
      out[o++] = i;
      for (let d = 0; d < 3; d++)
        out[o++] = clamp(
          Math.round((p[k + d] - origin[d]) * scale),
          -32767,
          32767,
        );
    }
    return out;
  }
}

import test from "node:test";
import assert from "node:assert/strict";
import {
  BucketLoad,
  RIM_LIP,
  RIM_FAR,
  RIM_LEFT,
  RIM_RIGHT,
} from "../server/bucket-load.js";
import { bucketPose } from "../server/physics.js";
import { LOAD, localU, mouthToLocal } from "../shared/bucket-load.js";
import { BucketFrame, WALLS } from "../shared/bucket.js";
import { BUCKET, SAND, initialMachine } from "../shared/world.js";

const { nu: NU, nv: NV, cells: CELLS, area: AREA, du: DU, dv: DV } = LOAD,
  RADIANS = Math.PI / 180,
  REPOSE = SAND.reposeDeg * RADIANS;
const sum = (values) => values.reduce((total, value) => total + value, 0);
const out = (load, rim) => sum(load.pending[rim]);
const surface = (load, c) => LOAD.floors[c % NU] + load.thickness[c];

// The world's up, seen from a bucket tilted theta from mouth-up towards its lip
// (positive lowers the lip), and leaning sideways so that +y is higher.
function tilted(theta, lean = 0) {
  const o = mouthToLocal(0, 0, 0, [0, 0, 0]),
    u = mouthToLocal(1, 0, 0, [0, 0, 0]),
    w = mouthToLocal(0, 0, 1, [0, 0, 0]),
    along = Math.sin(theta) * Math.cos(lean),
    away = Math.cos(theta) * Math.cos(lean);
  return {
    upX: along * (u[0] - o[0]) + away * (w[0] - o[0]),
    upY: Math.sin(lean),
    upZ: along * (u[2] - o[2]) + away * (w[2] - o[2]),
  };
}
// A bucket filled level with its rims.
function struck() {
  const load = new BucketLoad();
  for (let c = 0; c < CELLS; c++) {
    const i = c % NU;
    load.thickness[c] = Math.max(0, Math.min(0, LOAD.ceilings[i]) - LOAD.floors[i]);
  }
  load.volume = sum(load.thickness) * AREA;
  load.settled = false;
  return load;
}
const settle = (load, frame, passes = 2400) => {
  for (let n = 0; n < passes; n++) load.relax(frame);
};

test("the columns stand on the plates and end under the top plate", () => {
  // How far inside all the plates a point is.
  const clearance = (u, y, w) => {
    const [x, , z] = mouthToLocal(u, y, w, [0, 0, 0]);
    let distance = BUCKET.innerHalfWidth - Math.abs(y);
    for (const wall of WALLS)
      distance = Math.min(
        distance,
        (x - wall.ax) * wall.nx + (z - wall.az) * wall.nz - wall.inner,
      );
    return distance;
  };
  for (let i = 0; i < NU; i++) {
    const u = LOAD.columnU(i);
    assert.ok(Math.abs(clearance(u, 0, LOAD.floors[i])) < 1e-6, `floor ${i}`);
    assert.equal(i > LOAD.lastOpen, Number.isFinite(LOAD.ceilings[i]));
    if (i > LOAD.lastOpen)
      assert.ok(Math.abs(clearance(u, 0, LOAD.ceilings[i])) < 1e-6, `top ${i}`);
    const [x, , z] = mouthToLocal(u, 0, -5, [0, 0, 0]);
    assert.ok(Math.abs(localU(x, z) - u) < 1e-9);
  }
  // A struck load is the space inside the plates below the rims.
  let area = 0;
  for (let u = 0.25; u < 130; u += 0.5)
    for (let w = -90.25; w < 0; w += 0.5) if (clearance(u, 0, w) > 0) area += 0.25;
  const exact = area * 2 * BUCKET.innerHalfWidth;
  assert.ok(Math.abs(LOAD.struck - exact) < exact * 0.015, `${LOAD.struck} ${exact}`);
  assert.ok(LOAD.capacity > LOAD.struck);
});

test("a level bucket holds a struck load: nothing spills or creeps", () => {
  const load = struck(),
    before = load.thickness.slice(),
    volume = load.volume;
  settle(load, tilted(0), 200);
  for (let c = 0; c < CELLS; c++)
    assert.ok(Math.abs(load.thickness[c] - before[c]) < 1e-9);
  assert.ok(Math.abs(load.total - volume) < 1e-6);
  assert.equal(load.settled, true);
});

test("a tilted load slumps to repose and leaves over the low rim", () => {
  for (const degrees of [50, 65, 80]) {
    const theta = degrees * RADIANS,
      load = struck(),
      volume = load.total;
    settle(load, tilted(theta));
    const lip = out(load, RIM_LIP),
      cheeks = out(load, RIM_LEFT) + out(load, RIM_RIGHT);
    assert.ok(lip > 0, `${degrees}°: over the lip`);
    assert.ok(cheeks < 0.05 * lip, `${degrees}°: little over the cheeks (${cheeks})`);
    assert.equal(out(load, RIM_FAR), 0);
    assert.ok(Math.abs(load.total - volume) < 1e-6, "no sand is lost");
    assert.equal(load.settled, true);
    // The surface lies within repose of level, wherever there is sand to slide.
    for (let c = 0; c + 1 < CELLS; c++) {
      if (c % NU === NU - 1 || !load.thickness[c] || !load.thickness[c + 1]) continue;
      const slope = (surface(load, c + 1) - surface(load, c)) / DU,
        world = Math.atan(slope) + theta;
      assert.ok(Math.abs(world) < REPOSE + 0.02, `${degrees}°, ${c}: ${world}`);
    }
  }
});

test("held mouth down it empties, with no favourite side", () => {
  for (const degrees of [95, 130, 175, -175, -130]) {
    const load = struck(),
      volume = load.total;
    settle(load, tilted(degrees * RADIANS));
    assert.ok(load.volume < 1, `${degrees}°: ${load.volume} mm³ left`);
    assert.equal(out(load, RIM_FAR), 0, `${degrees}°`);
    assert.ok(out(load, RIM_LIP) > volume / 2, `${degrees}°`);
    const [left, right] = [out(load, RIM_LEFT), out(load, RIM_RIGHT)];
    assert.ok(Math.abs(left - right) < 0.02 * left, `${degrees}°: ${left}, ${right}`);
  }
});

test("over-curled it spills over the far rim, and the back pocket keeps some", () => {
  const load = struck(),
    volume = load.total;
  settle(load, tilted(-90 * RADIANS));
  assert.ok(out(load, RIM_FAR) > 0);
  assert.equal(out(load, RIM_LIP), 0);
  assert.ok(load.volume > 0.05 * volume, `${load.volume}`);
  assert.ok(Math.abs(load.total - volume) < 1e-6);
});

test("leaning sideways it spills over the lower cheek only", () => {
  const up = struck(),
    down = struck();
  settle(up, tilted(0, 50 * RADIANS));
  settle(down, tilted(0, -50 * RADIANS));
  assert.ok(out(up, RIM_LEFT) > 0);
  assert.equal(out(up, RIM_RIGHT), 0);
  assert.ok(out(down, RIM_RIGHT) > 0);
  assert.equal(out(down, RIM_LEFT), 0);
  const [a, b] = [out(up, RIM_LEFT), out(down, RIM_RIGHT)];
  assert.ok(Math.abs(a - b) < 0.02 * a, `the same either way (${a}, ${b})`);
});

test("sand goes into the columns under its bed cell, up to the bucket's capacity", () => {
  const load = new BucketLoad(),
    point = mouthToLocal(50, 3, -10, [0, 0, 0]);
  assert.equal(load.add(point[0], point[1], point[2], 600), 600);
  const wet = load.thickness.filter((value) => value > 0).length;
  assert.ok(wet >= 4 && wet <= 9, `${wet} columns`);
  assert.ok(Math.abs(sum(load.thickness) * AREA - 600) < 1e-9);
  assert.equal(load.total, 600);
  // Beside a cheek, and past it under its plate, all of it stays in the bucket.
  const edge = mouthToLocal(50, -LOAD.halfWidth - 3, -10, [0, 0, 0]);
  assert.equal(load.add(edge[0], edge[1], edge[2], 600), 600);
  assert.ok(Math.abs(sum(load.thickness) * AREA - 1200) < 1e-9);
  // Past its capacity it refuses what does not fit.
  let taken = 1200;
  for (let n = 0; n < 2000; n++) taken += load.add(point[0], point[1], point[2], 600);
  assert.ok(Math.abs(taken - LOAD.capacity) < 1e-6);
  assert.equal(load.room, 0);
  assert.equal(load.add(point[0], point[1], point[2], 600), 0);
});

// A flat bed at a height above a bucket posed by these strokes.
function buried(strokes) {
  const frame = new BucketFrame().set(
    bucketPose({ ...initialMachine(), strokes }),
  );
  const lip = mouthToLocal(0, 0, 0, [0, 0, 0]),
    world = [0, 0, 0];
  frame.toWorld(lip[0], lip[1], lip[2], world);
  return {
    frame,
    bed: (above) => ({ cellAt: () => 0, surface: () => world[2] + above }),
  };
}
const fillAtMouth = (load, volume) => {
  const point = mouthToLocal(40, 0, -20, [0, 0, 0]);
  let taken = 0;
  for (let step = 0; step < volume / 600; step++)
    for (let j = 0; j < NV; j++) {
      taken += load.add(point[0], LOAD.rowY(j), point[2], 600 / NV);
    }
  return taken;
};

test("under the bed it fills to the mouth; the rest stays in the bed", () => {
  // The mouth stands on end, the lip 60 mm down in the bed.
  const { frame, bed } = buried([0, 20, 0]),
    terrain = bed(60),
    load = new BucketLoad();
  load.coverBy(frame, terrain, true);
  load.relax(frame);
  let taken = 0;
  for (let n = 0; n < 200; n++) {
    taken += fillAtMouth(load, 3000);
    load.relax(frame);
  }
  assert.ok(taken > 0.2 * LOAD.struck, `it takes in ${taken} mm³`);
  assert.ok(taken < LOAD.capacity);
  assert.ok(load.add(0, 0, -40, 600) < 1e-6, "full at this tilt, it refuses more");
  const lidded = load.lid.reduce((count, value) => count + value, 0);
  assert.ok(lidded > 0 && lidded < (LOAD.lastOpen + 1) * NV, `${lidded} lidded`);
  for (let c = 0; c < CELLS; c++)
    if (load.lid[c])
      assert.ok(
        surface(load, c) <= Math.max(0, LOAD.floors[c % NU]) + 1e-6,
        `a lidded column keeps below the mouth (${surface(load, c)})`,
      );
  assert.equal(out(load, RIM_LIP), 0, "nothing passes the buried lip");
  // Lifted clear of the bed, what the lid held in spills.
  const volume = load.total;
  load.coverBy(frame, terrain, false);
  settle(load, frame);
  assert.ok(out(load, RIM_LIP) > 0);
  assert.ok(Math.abs(load.total - volume) < 1e-6);
});

test("with the rims buried and the mouth clear, the load is a heap, not a slab", () => {
  // Curled nearly level, with the bed just above the rims but below a lid's reach.
  const { frame, bed } = buried([0, 20, 50]),
    terrain = bed(30),
    load = new BucketLoad();
  load.coverBy(frame, terrain, true);
  for (let n = 0; n < 400; n++) {
    fillAtMouth(load, 600);
    load.relax(frame);
  }
  for (let i = 0; i <= LOAD.lastOpen; i++)
    for (const j of [0, NV - 1]) {
      const c = j * NU + i;
      assert.ok(
        surface(load, c) <= 6 + Math.tan(REPOSE + 0.2) * DV,
        `cheek column ${i}: ${surface(load, c)}`,
      );
    }
});

test("a packed load is what the columns hold, and an empty bucket packs to nothing", () => {
  const load = struck(),
    packed = load.pack();
  assert.equal(packed.length, CELLS);
  for (let c = 0; c < CELLS; c++)
    assert.ok(Math.abs(packed[c] * LOAD.quantum - load.thickness[c]) <= LOAD.quantum / 2);
  load.clear();
  assert.equal(load.pack(), null);
  assert.equal(load.room, LOAD.capacity);
});

test("any sequence of tilts, beds and additions conserves the sand exactly", () => {
  let seed = 7;
  const random = () => (seed = (1664525 * seed + 1013904223) >>> 0) / 4294967296;
  const load = new BucketLoad(),
    poses = [
      [0, 0, 0],
      [0, 20, 0],
      [0, 20, 30],
      [0, 20, 60],
      [60, 0, 0],
      [0, 60, 60],
      [26, 20, 52],
    ].map((strokes) => buried(strokes));
  let added = 0,
    gone = 0;
  for (let round = 0; round < 300; round++) {
    const { frame, bed } = poses[Math.floor(random() * poses.length)],
      terrain = bed(random() * 160 - 40),
      touching = random() < 0.6,
      passes = 2 + Math.floor(random() * 20);
    load.coverBy(frame, terrain, touching);
    for (let n = 0; n < passes; n++) {
      const u = random() * 110,
        y = (random() - 0.5) * 80,
        point = mouthToLocal(u, y, -10, [0, 0, 0]);
      added += load.add(point[0], point[1], point[2], random() * 600);
      load.relax(frame);
      for (const value of load.thickness)
        assert.ok(Number.isFinite(value) && value >= 0);
    }
    assert.ok(Math.abs(load.total + gone - added) < 1e-5, `round ${round}`);
    assert.ok(load.total <= LOAD.capacity + 1e-6);
    // Parcels leave whatever has gone over a rim.
    for (const pending of load.pending) {
      gone += sum(pending);
      pending.fill(0);
    }
  }
  assert.ok(gone > LOAD.capacity, `${gone} mm³ went through`);
});

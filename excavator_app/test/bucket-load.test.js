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

const { nu: NU, nv: NV, cells: CELLS, area: AREA, du: DU } = LOAD,
  RADIANS = Math.PI / 180,
  // Sand at rest in a bucket holds up to HOLD; sand that slides stops at SLIDE.
  HOLD = SAND.heapDeg * RADIANS,
  SLIDE = SAND.heapSlideDeg * RADIANS;
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
// What has gone over the rims, taken away as the parcels would.
const carryOff = (load) => {
  let gone = 0;
  for (const pending of load.pending) {
    gone += sum(pending);
    pending.fill(0);
  }
  return gone;
};
// The highest the sand stands above the rims (mm), and the steepest it lies along
// the bucket, in the world (radians), where both columns are open to the sky.
const highest = (load) => {
  let top = -Infinity;
  for (let c = 0; c < CELLS; c++)
    if (c % NU <= LOAD.lastOpen && load.thickness[c] > 0)
      top = Math.max(top, surface(load, c));
  return top;
};
const steepest = (load, theta) => {
  let worst = 0;
  for (let c = 0; c + 1 < CELLS; c++) {
    if (c % NU >= LOAD.lastOpen || !load.thickness[c] || !load.thickness[c + 1])
      continue;
    const slope = (surface(load, c + 1) - surface(load, c)) / DU;
    worst = Math.max(worst, Math.abs(Math.atan(slope) + theta));
  }
  return worst;
};
// A struck load with sand poured loose on its middle until it runs over the rims:
// a heap lying as sliding sand comes to rest.
function heaped() {
  const load = struck(),
    frame = tilted(0),
    middle = mouthToLocal(LOAD.length / 2, 0, 5, [0, 0, 0]);
  for (let n = 0; n < 4000; n++) {
    load.add(middle[0], middle[1], middle[2], 60, true);
    load.relax(frame);
  }
  settle(load, frame, 600);
  carryOff(load);
  return load;
}

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
  assert.ok(Math.abs(LOAD.struck / 1000 - BUCKET.ratedLoad) < 5);
  // Heaped as ISO 7451 rates a hoe bucket: 1:1 above a mouth L long and W wide.
  const L = LOAD.length,
    W = 2 * LOAD.halfWidth;
  assert.ok(Math.abs(LOAD.heaped - LOAD.struck - ((L * W * W) / 4 - W ** 3 / 12)) < 1);
  assert.ok(Math.abs(LOAD.heaped / 1000 - BUCKET.heapedLoad) < 5);
  assert.ok(LOAD.capacity > LOAD.heaped);
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

test("a tilted load slides out over the low rim, and what stays lies as sand holds", () => {
  // Level-full, the sand holds while the mouth tilts less than it can stand.
  for (const degrees of [15, 35]) {
    const load = struck(),
      before = load.thickness.slice();
    settle(load, tilted(degrees * RADIANS), 600);
    assert.equal(carryOff(load), 0, `${degrees}°: nothing leaves`);
    assert.deepEqual(load.thickness, before, `${degrees}°: nothing moves`);
  }
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
    // What slid has come to rest no steeper than sand holds, and near where
    // sliding sand stops.
    const slope = steepest(load, theta);
    assert.ok(slope < HOLD + 0.02, `${degrees}°: ${slope}`);
    assert.ok(slope > SLIDE - 0.05, `${degrees}°: ${slope}`);
  }
});

test("held mouth down it empties, with no favourite side", () => {
  for (const degrees of [100, 130, 175, -175, -130]) {
    const load = struck(),
      volume = load.total;
    settle(load, tilted(degrees * RADIANS));
    assert.ok(load.volume < 1, `${degrees}°: ${load.volume} mm³ left`);
    assert.equal(out(load, RIM_FAR), 0, `${degrees}°`);
    assert.ok(out(load, RIM_LIP) > volume / 2, `${degrees}°`);
    const [left, right] = [out(load, RIM_LEFT), out(load, RIM_RIGHT)];
    assert.ok(Math.abs(left - right) < 0.02 * left, `${degrees}°: ${left}, ${right}`);
  }
  // On end, the floor plate behind the lip is still flat enough to keep a little.
  const load = struck();
  settle(load, tilted(90 * RADIANS));
  assert.ok(load.volume > 0.02 * LOAD.struck && load.volume < 0.15 * LOAD.struck);
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
  assert.ok(wet >= 4 && wet <= 12, `${wet} columns`);
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

test("a heap stays put through a small tilt, and slides to rest at a bigger one", () => {
  const load = heaped(),
    heap = load.volume - LOAD.struck;
  // Sand that fell in has slid to rest: a ridge well above the rims, as high as
  // sliding sand leaves it and nowhere steeper than sand holds.
  assert.ok(heap > 35000, `a heap of ${heap} mm³`);
  assert.ok(highest(load) > 25, `${highest(load)} mm above the rims`);
  assert.ok(
    highest(load) < LOAD.halfWidth * Math.tan(SLIDE) + 2,
    `${highest(load)} mm above the rims`,
  );
  assert.ok(steepest(load, 0) < HOLD + 0.02, `${steepest(load, 0)}`);
  // Between how steeply sand slides and how steeply it holds, it stays where it
  // is, but for the few places that had stopped right at the limit.
  const margin = (SAND.heapDeg - SAND.heapSlideDeg) * RADIANS;
  settle(load, tilted(0.7 * margin), 600);
  const lost = carryOff(load);
  assert.ok(lost < 0.05 * heap, `tilted ${0.7 * margin} rad it lost ${lost} mm³`);
  // Tilted further it lets go, and comes to rest again.
  const theta = 4 * margin;
  settle(load, tilted(theta));
  const slid = carryOff(load);
  assert.ok(slid > 0.1 * heap, `tilted ${theta} rad it lost ${slid} mm³`);
  assert.ok(out(load, RIM_FAR) === 0);
  assert.ok(load.volume > LOAD.struck, "most of the heap is still there");
  assert.ok(steepest(load, theta) < HOLD + 0.02);
  assert.equal(load.settled, true);
  // Back level, nothing more moves: sand does not flow uphill.
  const kept = load.thickness.slice();
  settle(load, tilted(0), 600);
  assert.deepEqual(load.thickness, kept);
});

test("sand pressed in stands steeper than sand that fell in", () => {
  const poured = heaped(),
    { frame, bed } = buried([29.2, 32.8, 56]),
    pressed = new BucketLoad();
  // Level, with the bed just below the rims: it holds nothing in.
  pressed.coverBy(frame, bed(-10), true);
  pressed.relax(frame);
  for (let n = 0; n < 600; n++) {
    fillAtMouth(pressed, 1200);
    pressed.relax(frame);
    carryOff(pressed);
  }
  assert.ok(
    pressed.volume > poured.volume + 3000,
    `${pressed.volume} mm³ pressed in, ${poured.volume} poured`,
  );
  assert.ok(pressed.volume <= LOAD.heaped + 1000, "but no more than a 1:1 heap");
  assert.ok(steepest(pressed, 0) < HOLD + 0.03);
});

// A flat bed at a height above a bucket posed by these strokes. Nothing stands
// over any of its cells.
function buried(strokes) {
  const frame = new BucketFrame().set(
    bucketPose({ ...initialMachine(), strokes }),
  );
  const lip = mouthToLocal(0, 0, 0, [0, 0, 0]),
    world = [0, 0, 0];
  frame.toWorld(lip[0], lip[1], lip[2], world);
  return {
    frame,
    bed: (above) => ({
      cellAt: () => 0,
      surface: () => world[2] + above,
      ceilingAt: () => Infinity,
    }),
  };
}
// Sand offered all across the mouth, as a bucket moving through the bed meets it.
function fillAtMouth(load, volume) {
  let taken = 0;
  for (const u of [10, 30, 50, 70]) {
    const point = mouthToLocal(u, 0, -5, [0, 0, 0]);
    for (let j = 0; j < NV; j++)
      taken += load.add(point[0], LOAD.rowY(j), point[2], volume / (4 * NV));
  }
  return taken;
}

test("down in the sand it fills to the mouth; the rest stays in the bed", () => {
  // The mouth stands on end, hanging over the bed, its lip 60 mm down in it.
  const { frame, bed } = buried([0, 20, 0]),
    terrain = bed(60),
    load = new BucketLoad();
  load.coverBy(frame, terrain, true);
  load.relax(frame);
  let taken = 0;
  for (let n = 0; n < 400; n++) {
    taken += fillAtMouth(load, 2400);
    load.relax(frame);
  }
  assert.ok(taken > 0.8 * LOAD.struck, `it takes in ${taken} mm³`);
  assert.ok(taken < LOAD.struck);
  assert.ok(fillAtMouth(load, 2400) < 1, "full at this tilt, it refuses more");
  assert.equal(carryOff(load), 0, "and none of it leaves while the bed holds it");
  // Below the bed's level every column is full to the mouth and no further: past
  // the mouth is the bed.
  let full = 0;
  for (let c = 0; c < CELLS; c++) {
    if (c % NU > LOAD.lastOpen) continue;
    assert.ok(surface(load, c) <= 1e-6, `column ${c} at ${surface(load, c)}`);
    if (surface(load, c) > -0.01) full++;
  }
  assert.ok(full > 0.7 * (LOAD.lastOpen + 1) * NV, `${full} columns full`);
  assert.ok(full < (LOAD.lastOpen + 1) * NV, "the top of the mouth is above the bed");
  // The bed gone from in front of it for a moment, it only starts to pour: one
  // tick is four passes.
  const volume = load.total;
  load.coverBy(frame, bed(-100), true);
  for (let n = 0; n < 4; n++) load.relax(frame);
  assert.ok(carryOff(load) < 0.05 * volume, "a moment without the bed loses little");
  // Lifted clear of the bed, it all runs out, nearly all of it over the lip.
  load.coverBy(frame, terrain, false);
  settle(load, frame);
  assert.ok(out(load, RIM_LIP) > 0.75 * volume, `${out(load, RIM_LIP)} of ${volume}`);
  assert.equal(out(load, RIM_FAR), 0);
  assert.ok(load.volume < 1);
});

test("buried over its rims a level bucket takes a heap and a little more, and keeps the heap", () => {
  const { frame, bed } = buried([29.2, 32.8, 56]),
    load = new BucketLoad();
  load.coverBy(frame, bed(30), true);
  load.relax(frame);
  for (let n = 0; n < 400; n++) {
    fillAtMouth(load, 2400);
    load.relax(frame);
  }
  // The bed holds it in on every side: nothing leaves, and it is a heap with the
  // layer that will run off, not a slab as high as the bed.
  assert.equal(carryOff(load), 0);
  assert.ok(load.volume > LOAD.heaped, `${load.volume} mm³ under the bed`);
  assert.ok(load.volume <= LOAD.capacity + 1e-6);
  const cheek = surface(load, 10),
    middle = surface(load, (NV >> 1) * NU + 10);
  assert.ok(middle > cheek + 20, `a heap: ${middle} mm in the middle, ${cheek} at a cheek`);
  // Lifted out, the layer runs off all round and the heap stays, lying as sliding
  // sand comes to rest: close to the rated heaped load.
  load.coverBy(frame, bed(30), false);
  settle(load, frame);
  for (const rim of [RIM_LIP, RIM_FAR, RIM_LEFT, RIM_RIGHT])
    assert.ok(out(load, rim) > 0, `some runs off rim ${rim}`);
  carryOff(load);
  assert.ok(load.volume > 0.94 * LOAD.heaped, `it keeps ${load.volume} mm³`);
  assert.ok(load.volume < LOAD.heaped + 1000);
  assert.ok(highest(load) > 28, `${highest(load)} mm above the rims`);
  assert.ok(steepest(load, 0) < HOLD + 0.03);
  assert.equal(load.settled, true);
});

test("the bed holds a load in only as high as it stands beside the rim", () => {
  // Level, with the bed 8 mm above the rims on every side.
  const { frame, bed } = buried([29.2, 32.8, 56]),
    load = new BucketLoad(),
    above = 8;
  load.coverBy(frame, bed(above), true);
  load.relax(frame);
  for (let n = 0; n < 400; n++) {
    fillAtMouth(load, 2400);
    load.relax(frame);
    carryOff(load);
  }
  // The rims are not quite level with each other, so allow a millimetre.
  for (let i = 0; i <= LOAD.lastOpen; i++)
    for (const j of [0, NV - 1]) {
      const c = j * NU + i;
      assert.ok(
        surface(load, c) <= above + 1 + (Math.tan(HOLD) * LOAD.dv) / 2 + 1e-6,
        `cheek column ${i}: ${surface(load, c)}`,
      );
    }
  assert.ok(surface(load, 10) > above - 2, "and that high it does stand");
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
    gone += carryOff(load);
  }
  assert.ok(gone > LOAD.capacity, `${gone} mm³ went through`);
});

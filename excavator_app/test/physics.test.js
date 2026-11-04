import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  SandSimulation,
  bucketPose,
  toLocal,
  toWorld,
  insideProfile,
} from "../server/physics.js";
import {
  BucketFrame,
  REGION,
  insideCavity,
  firstCrossing,
  CROSS_MOUTH,
  WALLS,
  TEETH,
} from "../shared/bucket.js";
import { CELL_AREA, Terrain, initialTerrain } from "../server/terrain.js";
import { solve } from "../shared/kinematics.js";
import { CONFIG } from "../shared/config.js";
import {
  WORLD,
  SAND,
  BUCKET,
  YARD,
  POUR_ZONE,
  neutral,
  crawlerExtent,
  chassisAxes,
  armFrame,
} from "../shared/world.js";
import {
  WATER,
  groundHeight,
  groundSample,
  landscape,
} from "../shared/landscape.js";
import {
  encodeFrame,
  decodeFrame,
  TILE_COUNT,
  TILE_CELLS,
} from "../shared/protocol.js";

const insideRegion = (x, z) => {
  let inside = false;
  for (let i = 0, j = REGION.length - 1; i < REGION.length; j = i++) {
    const a = REGION[i],
      b = REGION[j];
    if (
      a[1] > z !== b[1] > z &&
      x < ((b[0] - a[0]) * (z - a[1])) / (b[1] - a[1]) + a[0]
    )
      inside = !inside;
  }
  return inside;
};
const R = WORLD.radius;
const TALUS = Math.tan((SAND.reposeDeg * Math.PI) / 180);
const NX = SAND.nx;

// Track every grain in the bucket frame after each substep: its cavity
// membership may change only along a path through the open mouth.
function watchBucket(s) {
  const record = {
    wallCrossings: 0,
    mouthCrossings: 0,
    minClearance: Infinity,
  };
  const last = new Float64Array(3 * SAND.maxGrains),
    seen = new Uint8Array(SAND.maxGrains),
    was = new Uint8Array(SAND.maxGrains),
    l = new Float64Array(3),
    a = new Float64Array(3),
    hit = new Float64Array(3),
    substep = s.substep.bind(s);
  s.substep = (dt) => {
    substep(dt);
    for (let i = 0; i < SAND.maxGrains; i++) {
      if (!s.alive[i]) {
        seen[i] = 0;
        continue;
      }
      s.frame.toLocal(s.pos[3 * i], s.pos[3 * i + 1], s.pos[3 * i + 2], l);
      const inside = insideCavity(l[0], l[1], l[2]) ? 1 : 0;
      // Gap between the grain surface and the CAD plate surface it faces.
      if (Math.abs(l[1]) < 40)
        for (const w of [...WALLS, TEETH]) {
          const t = ((l[0] - w.ax) * w.dx + (l[2] - w.az) * w.dz) / w.len2;
          if (t <= 0 || t >= 1) continue;
          const signed = (l[0] - w.ax) * w.nx + (l[2] - w.az) * w.nz;
          record.minClearance = Math.min(
            record.minClearance,
            (signed > 0 ? signed - w.inner : -signed - w.outer) - R,
          );
        }
      if (seen[i] && inside !== was[i]) {
        a.set(last.subarray(3 * i, 3 * i + 3));
        if (firstCrossing(a, l, hit) === CROSS_MOUTH) record.mouthCrossings++;
        else record.wallCrossings++;
      }
      last.set(l, 3 * i);
      seen[i] = 1;
      was[i] = inside;
    }
  };
  return record;
}
function runner(s) {
  return (seconds, axes = {}) => {
    s.axes = { ...neutral(), ...axes };
    for (let i = 0; i < Math.round(seconds * 30); i++) s.step();
  };
}
// Steepest slope that sand could still slide down: the higher column must hold
// sand, since bare hard ground may be steeper than repose. Only pages that hold
// sand are visited.
function maxBedSlope(s) {
  const t = s.terrain;
  let steepest = 0;
  t.pages.forEach((page, p) => {
    if (!page) return;
    const row = (p >>> 6) * SAND.page,
      col = (p & 63) * SAND.page;
    for (let j = row; j < row + SAND.page; j++)
      for (let i = col; i < col + SAND.page; i++) {
        const c = j * NX + i;
        for (const n of [c + 1, c + NX]) {
          const drop = t.surface(c) - t.surface(n);
          if (t.get(drop > 0 ? c : n) >= 0.5)
            steepest = Math.max(steepest, Math.abs(drop) / SAND.cell);
        }
      }
  });
  return steepest;
}
// The worst fin near the machine: how far any column stands above the average
// of the columns three cells away. A wall of sand beside a track scores high,
// a pile or a trench does not.
function worstFin(s) {
  const t = s.terrain,
    m = s.machine,
    i0 = Math.floor((m.x - 900 - WORLD.minX) / SAND.cell),
    j0 = Math.floor((m.y - 900 - WORLD.minY) / SAND.cell);
  let worst = 0;
  for (let j = j0; j < j0 + 180; j++)
    for (let i = i0; i < i0 + 180; i++) {
      const c = j * NX + i,
        ring =
          (t.surface(c + 3) +
            t.surface(c - 3) +
            t.surface(c + 3 * NX) +
            t.surface(c - 3 * NX)) /
          4;
      worst = Math.max(worst, t.surface(c) - ring);
    }
  return worst;
}
// How far sand stands above the plane of the track shoes, under the crawler.
function sandAboveTracks(s) {
  const t = s.terrain,
    m = s.machine,
    ch = Math.cos(m.heading),
    sh = Math.sin(m.heading),
    b = Math.tan(m.pitch),
    c = Math.tan(m.roll) / Math.cos(m.pitch);
  let worst = -Infinity;
  for (let u = -140; u <= 140; u += 10)
    for (let v = -190; v <= 190; v += 10) {
      const cell = t.cellAt(m.x + u * ch - v * sh, m.y + u * sh + v * ch);
      if (t.get(cell) > 0.01)
        worst = Math.max(worst, t.surface(cell) - (m.z + b * u + c * v));
    }
  return worst;
}
const snapshot = (t) => t.pages.map((page) => page && page.slice());
const near = (a, b, tolerance) => Math.abs(a - b) <= tolerance;
// Stand the machine somewhere, as if it had driven there.
function place(s, x, y, heading = 0) {
  Object.assign(s.machine, { x, y, heading, pitch: 0, roll: 0 });
  s.machine.z = groundHeight(x, y);
  s.resting = false;
  for (let i = 0; i < 60; i++) s.advanceMachine(1 / 120);
  s.bucket = bucketPose(s.machine);
  s.frame.set(s.bucket);
  s.prevFrame.set(s.bucket);
}

test("all 125 original CAD kinematic cases remain unchanged", () => {
  const cases = JSON.parse(
    readFileSync(new URL("./kinematic-cases.json", import.meta.url)),
  );
  for (const c of cases) {
    const actual = solve(c.strokes).p;
    for (const [name, expected] of Object.entries(c.points))
      assert.ok(
        Math.hypot(
          actual[name][0] - expected[0],
          actual[name][1] - expected[1],
        ) < 1e-7,
        `${c.strokes}: ${name}`,
      );
  }
});

test("bucket shell and cheeks are solid from both sides; the mouth is open", () => {
  const s = new SandSimulation(),
    pose = bucketPose(s.machine);
  const roundtrip = toLocal(...toWorld(10, -15, -55, pose), pose);
  assert.ok(
    Math.hypot(...roundtrip.map((v, i) => v - [10, -15, -55][i])) < 1e-9,
  );
  assert.equal(insideProfile(0, -50), true);
  assert.equal(insideProfile(-100, -50), false);
  // Fire grains at 2.5 m/s through every wall and cheek plate, in both
  // directions. None may come out on the far side.
  const shots = [];
  for (const w of WALLS) {
    const mx = w.ax + w.dx / 2,
      mz = w.az + w.dz / 2;
    shots.push([mx + w.nx * 9, 0, mz + w.nz * 9, -w.nx, 0, -w.nz, 1]);
    shots.push([mx - w.nx * 9, 0, mz - w.nz * 9, w.nx, 0, w.nz, 0]);
  }
  for (const y of [-1, 1]) {
    shots.push([5, y * 28, -55, 0, y, 0, 1]);
    shots.push([5, y * 48, -55, 0, -y, 0, 0]);
  }
  for (const [x, y, z, dx, dy, dz, inside] of shots) {
    s.reset();
    s.machine.strokes = [40, 0, 30]; // high above the bed
    s.bucket = bucketPose(s.machine);
    s.frame.set(s.bucket);
    s.prevFrame.set(s.bucket);
    const w = toWorld(x, y, z, s.bucket),
      v = toWorld(x + dx, y + dy, z + dz, s.bucket).map(
        (c, i) => (c - w[i]) * 2500,
      );
    const local = toLocal(...w, s.bucket);
    s.spawn(...w, ...v, inside, local);
    for (let i = 0; i < 4; i++) s.substep(1 / 120);
    const after = toLocal(s.pos[0], s.pos[1], s.pos[2], s.frame);
    assert.equal(
      insideCavity(...after) ? 1 : 0,
      inside,
      `grain fired from ${inside ? "inside" : "outside"} at ${[x, y, z]} passed through`,
    );
  }
  // A grain falling past the lip and out of the mouth leaves the cavity.
  s.reset();
  s.machine.strokes = [40, 0, 0];
  s.bucket = bucketPose(s.machine);
  s.frame.set(s.bucket);
  s.prevFrame.set(s.bucket);
  // Just inside the middle of the mouth (its inward normal is (0.557, -0.83)).
  const mouth = toWorld(-33.9, 0, -46.2, s.bucket);
  const local = toLocal(...mouth, s.bucket);
  assert.equal(insideCavity(...local), true);
  s.spawn(...mouth, 0, 0, -300, 1, local);
  for (let i = 0; i < 60; i++) s.substep(1 / 120);
  assert.equal(s.side[0], 0, "the open mouth releases grains");
});

test("the sand yard starts at rest, below its angle of repose", () => {
  const s = new SandSimulation(),
    run = runner(s);
  const before = snapshot(s.terrain),
    volume = s.totalVolume();
  assert.ok(volume > 5e9, "the yard holds several cubic metres of sand");
  assert.ok(maxBedSlope(s) <= TALUS + 0.01);
  run(1);
  assert.equal(s.resting, true);
  assert.equal(s.grains, 0);
  assert.deepEqual(snapshot(s.terrain), before, "an idle bed does not creep");
  assert.equal(s.terrain.volumeIn(POUR_ZONE), 0, "the pad starts clean");
  // Storage is sparse: an open world costs only the pages that hold sand.
  const pages = s.terrain.pages.filter(Boolean).length;
  assert.ok(pages < 200, `only ${pages} of ${s.terrain.pages.length} pages`);
});

test(
  "scoop, lift, swing and pour: a full load, no leaks, volume conserved",
  { timeout: 120000 },
  () => {
    const s = new SandSimulation(),
      run = runner(s),
      watch = watchBucket(s),
      volume = s.totalVolume();
    s.speed = 1;
    run(1.2, { boom: -1 });
    run(1.6, { stick: 1 });
    run(3.5, { bucket: 1 });
    const loaded = s.stats.load;
    assert.ok(loaded > 200, `the bucket fills (${loaded} cm³)`);
    run(2, { boom: 1 });
    assert.ok(
      Math.max(
        ...[...s.pos].filter((_, i) => i % 3 === 2 && s.alive[(i - 2) / 3]),
      ) > 120,
      "the load rises with the bucket",
    );
    assert.ok(s.stats.load >= loaded * 0.9, "a curled bucket keeps its load");
    run(1.5, { slew: 1 });
    assert.ok(
      s.stats.load >= loaded * 0.85,
      "the load travels through the swing",
    );
    const carried = s.stats.load;
    run(4, { bucket: -1 });
    run(1.5);
    assert.equal(s.stats.carried, 0, "opening the bucket empties it");
    assert.ok(
      s.stats.deposited >= carried * 0.85,
      `the load lands in the pour zone (${s.stats.deposited} of ${carried} cm³)`,
    );
    assert.equal(watch.wallCrossings, 0, "no grain passes through a wall");
    assert.ok(watch.mouthCrossings > 100);
    assert.ok(
      watch.minClearance > -0.25,
      `grains stay outside the plates (${watch.minClearance.toFixed(2)} mm)`,
    );
    assert.ok(
      near(s.totalVolume(), volume, 1),
      "sand volume is conserved to under a cubic millimetre",
    );
    assert.ok(
      maxBedSlope(s) <= TALUS + 0.02,
      "the dumped pile slumps to repose",
    );
    for (let i = 0; i < SAND.maxGrains; i++)
      if (s.alive[i]) {
        assert.ok(
          s.pos[3 * i + 2] >=
            groundHeight(s.pos[3 * i], s.pos[3 * i + 1]) + R - 0.5,
        );
        assert.ok(s.pos[3 * i] >= WORLD.minX && s.pos[3 * i] <= WORLD.maxX);
      }
    console.log(
      `Scoop/pour: ${loaded} cm³ loaded; ${carried} cm³ carried; ${s.stats.deposited} cm³ deposited; ${watch.mouthCrossings} mouth crossings, ${watch.wallCrossings} wall crossings.`,
    );
  },
);

test(
  "aggressive digging, sweeping and shaking never leaks through the bucket",
  { timeout: 120000 },
  () => {
    const s = new SandSimulation(),
      run = runner(s),
      watch = watchBucket(s),
      volume = s.totalVolume();
    s.speed = 1;
    run(1.2, { boom: -1 });
    run(3, { stick: 1, bucket: 0.3 });
    run(2, { bucket: 1, stick: 1 });
    run(1.5, { slew: -1 });
    run(2, { boom: 1 });
    for (let k = 0; k < 5; k++) {
      run(0.4, { slew: 1, stick: 1, bucket: -0.5 });
      run(0.4, { slew: -1, stick: -1, bucket: 0.5 });
    }
    run(2, { stick: -1, boom: -1 });
    assert.equal(watch.wallCrossings, 0);
    assert.ok(watch.minClearance > -0.25, `${watch.minClearance} mm`);
    assert.ok(near(s.totalVolume(), volume, 1));
  },
);

test("an over-steep sand heap avalanches to its angle of repose", () => {
  const s = new SandSimulation(),
    run = runner(s);
  // Drop a tall column of sand on bare ground, far from any existing sand.
  const [x, y] = [-3000, -700];
  assert.equal(s.terrain.pages[0], null);
  for (let k = 0; k < 40; k++) s.terrain.deposit(x, y, 4000);
  const volume = s.totalVolume();
  assert.ok(maxBedSlope(s) > 2);
  run(6);
  assert.ok(maxBedSlope(s) <= TALUS + 0.01);
  assert.ok(near(s.totalVolume(), volume, 1e-3));
  assert.equal(s.resting, true);
});

test("boom remains independent of slew and all controls obey their limits", () => {
  const s = new SandSimulation();
  s.speed = 1;
  for (const slew of [-150, -75, 0, 75, 150]) {
    s.machine.slew = slew;
    s.machine.strokes[0] = 20;
    s.axes = { ...neutral(), boom: -1 };
    s.advanceMachine(10);
    assert.equal(s.machine.strokes[0], 0);
    assert.equal(s.machine.slew, slew);
    s.axes.boom = 1;
    s.advanceMachine(10);
    assert.equal(s.machine.strokes[0], 60);
  }
  s.estop = true;
  const before = structuredClone(s.machine);
  s.axes = Object.fromEntries(Object.keys(neutral()).map((k) => [k, 1]));
  s.advanceMachine(10);
  assert.deepEqual(s.machine, before);
});

test("the bucket cannot be driven through the hard ground", () => {
  const s = new SandSimulation();
  s.speed = 1;
  // Bucket beside the crawler, over bare ground: lowering with the stick
  // crowded would put the teeth 60 mm into it.
  s.machine.slew = 90;
  s.machine.strokes = [30, 20, 0];
  s.axes = { ...neutral(), boom: -1 };
  for (let i = 0; i < 400; i++) s.advanceMachine(1 / 120);
  assert.ok(s.machine.strokes[0] > 0, "the boom stops on contact");
  assert.ok(s.bucketClearance(s.machine) >= -0.2);
  assert.equal(s.blocked, true);
  // Raising is always allowed.
  s.axes = { ...neutral(), boom: 1 };
  const stopped = s.machine.strokes[0];
  s.advanceMachine(0.5);
  assert.ok(s.machine.strokes[0] > stopped);
});

test("the machine starts level on hard ground and stays put", () => {
  const s = new SandSimulation(),
    run = runner(s),
    before = structuredClone(s.machine);
  run(0.5);
  assert.deepEqual(s.machine, before);
  assert.equal(s.resting, true);
});

test("the bucket frame stays exact on a tilted chassis", () => {
  const machine = {
    strokes: [20, 15, 30],
    slew: 37,
    x: 1234,
    y: -567,
    z: 89,
    heading: 0.7,
    pitch: 0.3,
    roll: -0.2,
    tracks: [0, 0],
  };
  // The chassis axes are right-handed and unit length...
  const { forward, left, up } = chassisAxes(machine),
    dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2],
    cross = (a, b) => [
      a[1] * b[2] - a[2] * b[1],
      a[2] * b[0] - a[0] * b[2],
      a[0] * b[1] - a[1] * b[0],
    ];
  for (const axis of [forward, left, up]) assert.ok(near(dot(axis, axis), 1, 1e-12));
  assert.ok(near(dot(forward, left), 0, 1e-12));
  cross(forward, left).forEach((v, d) => assert.ok(near(v, up[d], 1e-12)));
  // ...pitch raises the nose and roll raises the +Y side.
  assert.ok(forward[2] > 0);
  const rolled = chassisAxes({ ...machine, pitch: 0, roll: 0.2 });
  assert.ok(rolled.left[2] > 0);
  // The frame maps the world and back, and level it matches the plain formula.
  const pose = bucketPose(machine),
    point = [14, -9, -33],
    back = toLocal(...toWorld(...point, pose), pose);
  back.forEach((v, d) => assert.ok(near(v, point[d], 1e-9)));
  const level = { ...machine, pitch: 0, roll: 0 },
    s = solve(level.strokes),
    a = level.heading + (level.slew * Math.PI) / 180,
    reach = s.origins.bucket[0] + CONFIG.arm_offset[0],
    flat = armFrame(
      level,
      reach,
      s.origins.bucket[1] + CONFIG.arm_offset[2],
      s.angles.bucket,
    );
  assert.ok(near(flat.x, level.x + Math.cos(a) * reach, 1e-9));
  assert.ok(near(flat.y, level.y + Math.sin(a) * reach, 1e-9));
  // A vertical column through the tilted bucket finds its real top and bottom.
  const frame = new BucketFrame().set(pose),
    w = [0, 0, 0],
    col = [0, 0, 0, 0],
    inside = [10, 0, -55];
  frame.toWorld(...inside, w);
  assert.equal(frame.column(w[0], w[1], col), true);
  assert.ok(col[0] < w[2] && w[2] < col[1]);
  for (const [z, expected] of [
    [col[0] + 0.05, true],
    [col[1] - 0.05, true],
    [col[0] - 0.5, false],
    [col[1] + 0.5, false],
  ]) {
    const l = frame.toLocal(w[0], w[1], z, [0, 0, 0]),
      found = Math.abs(l[1]) <= BUCKET.outerHalfWidth && insideRegion(l[0], l[2]);
    assert.equal(found, expected, `height ${z}`);
  }
  // The walls still hold at this tilt: fire a grain at each shell plate.
  const sim = new SandSimulation();
  for (const wall of WALLS) {
    sim.reset();
    Object.assign(sim.machine, machine, {
      x: 0,
      y: 0,
      z: 0,
      strokes: [40, 0, 30],
    });
    sim.bucket = bucketPose(sim.machine);
    sim.frame.set(sim.bucket);
    sim.prevFrame.set(sim.bucket);
    const mx = wall.ax + wall.dx / 2,
      mz = wall.az + wall.dz / 2,
      from = toWorld(mx + wall.nx * 9, 0, mz + wall.nz * 9, sim.bucket),
      to = toWorld(mx - wall.nx, 0, mz - wall.nz, sim.bucket),
      velocity = to.map((c, d) => (c - from[d]) * 250);
    sim.spawn(...from, ...velocity, 1, toLocal(...from, sim.bucket));
    const frozen = structuredClone(sim.machine);
    for (let i = 0; i < 4; i++) {
      sim.substep(1 / 120);
      sim.machine = structuredClone(frozen);
    }
    assert.equal(
      insideCavity(...toLocal(sim.pos[0], sim.pos[1], sim.pos[2], sim.frame))
        ? 1
        : 0,
      1,
      "a grain stays inside the tilted bucket",
    );
  }
});

test("a grain cannot hang on the outside of a tilted bucket cheek", () => {
  // Parked across a real hillside, one cheek's outer face tips up, so gravity
  // holds a grain against it. With nothing under it, it must slide off and fall.
  const s = new SandSimulation();
  s.machine.strokes = [50, 45, 50];
  place(s, -2200, 9450, 0);
  for (let i = 0; i < 240; i++) s.substep(1 / 120);
  const tilt = s.frame.ey[2];
  assert.ok(Math.abs(tilt) > 0.05, `the cheek leans (${tilt.toFixed(3)})`);
  // The face whose outward normal points up, and a spot just above the floor.
  const start = toWorld(-20, Math.sign(tilt) * 44, -72, s.bucket);
  s.spawn(...start, 0, 0, 0, 0, null);
  for (let i = 0; i < 30; i++) s.substep(1 / 120);
  assert.ok(
    !s.alive[0] || s.pos[2] < start[2] - 100,
    `the grain hangs ${(start[2] - s.pos[2]).toFixed(1)} mm below its start`,
  );
});

test("the ground is one surface for the physics and the scenery", () => {
  const land = landscape();
  // Every vertex of the drawn grid is exactly the height the physics uses.
  for (const [i, j] of [
    [128, 128],
    [40, 200],
    [200, 60],
    [10, 245],
  ]) {
    const x = WORLD.minX + i * 160,
      y = WORLD.minY + j * 160;
    assert.ok(near(groundHeight(x, y), land.heights[j * 257 + i], 1e-3));
  }
  const out = [0, 0, 0];
  for (const [x, y] of [
    [-5000, 3000],
    [9000, -9000],
    [-14000, 14000],
  ]) {
    groundSample(x, y, out);
    assert.ok(near(out[0], groundHeight(x, y), 1e-9));
    // The reported slope predicts a small step on the same triangle.
    const stepX = groundHeight(x + 1, y) - groundHeight(x - 1, y);
    assert.ok(Math.abs(stepX / 2 - out[1]) < 0.5);
  }
  // The start, the pad and the road from them are all bare and flat enough.
  assert.equal(groundHeight(0, 0), 0);
  assert.equal(groundHeight(440, 355), 0);
  assert.equal(land.props.length > 1000, true);
  // Nothing grows in the water or stands on the machine's starting place.
  const start = crawlerExtent(0);
  for (const p of land.props) {
    if (p.kind === "pine" || p.kind === "broadleaf")
      assert.ok(groundHeight(p.x, p.y) > WATER.level);
    assert.ok(
      Math.abs(p.x) > start.x || Math.abs(p.y) > start.y,
      `${p.kind} at the start`,
    );
  }
});

test("the crawler stays on the map and turns without leaving it", () => {
  const s = new SandSimulation();
  s.speed = 1;
  // Standing right at the edges, whichever way it drives or turns.
  for (const [x, y] of [
    [WORLD.maxX - 260, 0],
    [WORLD.minX + 260, 0],
    [0, WORLD.maxY - 260],
    [0, WORLD.minY + 260],
  ])
    for (let direction = 0; direction < 8; direction++) {
      place(s, x, y, (direction * Math.PI) / 4);
      s.axes = { ...neutral(), leftTrack: 1, rightTrack: 1 };
      for (let i = 0; i < 60; i++) s.advanceMachine(1 / 30);
      s.axes = { ...neutral(), leftTrack: -1, rightTrack: 1 };
      for (let i = 0; i < 30; i++) {
        s.advanceMachine(1 / 30);
        const extent = crawlerExtent(s.machine.heading);
        assert.ok(s.machine.x - extent.x >= WORLD.minX - 1e-9);
        assert.ok(s.machine.x + extent.x <= WORLD.maxX + 1e-9);
        assert.ok(s.machine.y - extent.y >= WORLD.minY - 1e-9);
        assert.ok(s.machine.y + extent.y <= WORLD.maxY + 1e-9);
      }
    }
});

test("the crawler follows the hills: level on a road, tilted on a slope", () => {
  const s = new SandSimulation();
  s.speed = 1;
  s.machine.strokes = [60, 0, 0];
  // Along the site road and on across the valley.
  place(s, -1000, -60, Math.PI);
  s.axes = { ...neutral(), leftTrack: 1, rightTrack: 1 };
  let previousZ = s.machine.z,
    steepest = 0;
  const startX = s.machine.x;
  for (let i = 0; i < 3000; i++) {
    s.advanceMachine(1 / 120);
    const m = s.machine;
    assert.ok(Math.abs(m.z - previousZ) < 8, "no vertical jump");
    previousZ = m.z;
    steepest = Math.max(steepest, Math.abs(m.pitch), Math.abs(m.roll));
    // The shoes rest on the ground: never far above it, never below it.
    const bottom = m.z - groundHeight(m.x, m.y);
    assert.ok(bottom > -40 && bottom < 60, `chassis height ${bottom} mm`);
  }
  assert.ok(startX - s.machine.x > 4000, "travel covers real distance");
  assert.ok(steepest > 0.005, "the chassis tilts with the ground");
  // The bucket frame moves with the chassis.
  assert.ok(near(bucketPose(s.machine).z - s.machine.z, 643, 400));
});

test("hills too steep to climb, scenery and deep water stop the crawler", () => {
  const s = new SandSimulation();
  s.speed = 1;
  s.machine.strokes = [60, 0, 0];
  s.axes = { ...neutral(), leftTrack: 1, rightTrack: 1 };
  const driveFor = (seconds) => {
    let last = null;
    for (let i = 0; i < seconds * 120; i++) {
      s.obstacle = null;
      s.advanceMachine(1 / 120);
      last = s.obstacle ?? last;
    }
    return last;
  };
  // The ridge around the valley.
  place(s, 15500, 0, 0);
  assert.equal(driveFor(30), "steep");
  assert.ok(s.machine.x < 19000, `stopped at x=${s.machine.x}`);
  const onRidge = s.machine.x;
  // It can always back away.
  s.axes = { ...neutral(), leftTrack: -1, rightTrack: -1 };
  assert.equal(driveFor(1), null);
  assert.ok(s.machine.x < onRidge - 100);
  // A building.
  s.axes = { ...neutral(), leftTrack: 1, rightTrack: 1 };
  place(s, -820, -500, -Math.PI / 2);
  assert.equal(driveFor(4), "object");
  assert.ok(s.machine.y > -1020, "the office is solid");
  s.axes = { ...neutral(), leftTrack: -1, rightTrack: -1 };
  assert.equal(driveFor(1), null);
  // The lake.
  s.axes = { ...neutral(), leftTrack: 1, rightTrack: 1 };
  place(s, WATER.x, 9700, Math.PI / 2);
  assert.equal(driveFor(30), "water");
  assert.ok(s.machine.y < WATER.y, "it stops at the lake shore");
  assert.ok(groundHeight(s.machine.x, s.machine.y) < WATER.level);
});

test(
  "driving through the sand leaves ruts, not a wall of sand through the machine",
  { timeout: 120000 },
  () => {
    const s = new SandSimulation(),
      run = runner(s),
      volume = s.totalVolume();
    s.speed = 1;
    run(1.5, { boom: 1 });
    let worst = 0;
    const drive = (seconds, axes) => {
      for (let i = 0; i < seconds * 3; i++) {
        run(1 / 3, axes);
        worst = Math.max(worst, worstFin(s));
        assert.ok(
          sandAboveTracks(s) < 60,
          `sand stands ${sandAboveTracks(s).toFixed(0)} mm into the machine`,
        );
      }
    };
    // Into the yard, then straight up and over the big stockpile.
    const forward = { leftTrack: 1, rightTrack: 1 };
    drive(12, forward);
    const before = s.machine.x;
    assert.ok(before > 2000, "the machine drives into the yard");
    const m = s.machine,
      want = Math.atan2(-1500 - m.y, 2600 - m.x);
    run(Math.abs(want - m.heading) / ((2 * 220) / CONFIG.track_centres), {
      leftTrack: 1,
      rightTrack: -1,
    });
    let highest = 0,
      nose = 0;
    for (let i = 0; i < 30; i++) {
      drive(1 / 3, forward);
      highest = Math.max(highest, s.machine.z);
      nose = Math.max(nose, s.machine.pitch);
    }
    assert.ok(highest > 300, `rides up the pile (${highest.toFixed(0)} mm)`);
    assert.ok(nose > 0.2, `pitches on its flank (${nose.toFixed(2)} rad)`);
    // Turning on the spot on top of it is the worst case for the old plow.
    drive(3, { leftTrack: 1, rightTrack: -1 });
    drive(2, forward);
    assert.ok(worst < 70, `tallest fin ${worst.toFixed(0)} mm`);
    run(3);
    assert.ok(maxBedSlope(s) <= TALUS + 0.02, "slopes settle back to repose");
    assert.ok(near(s.totalVolume(), volume, 1));
    assert.equal(s.resting, true);
  },
);

test("the tracks press a shallow rut and heap the sand beside it", () => {
  const s = new SandSimulation(),
    run = runner(s),
    volume = s.totalVolume();
  s.speed = 1;
  s.machine.strokes = [60, 0, 0];
  place(s, 3000, 2600, 0);
  const before = snapshot(s.terrain),
    height = (x, y) => {
      const c = s.terrain.cellAt(x, y);
      return s.terrain.get(c);
    },
    was = (x, y) => {
      const c = s.terrain.cellAt(x, y),
        o = (((c >>> 12) & 63) << 6) | (c & 63);
      return before[((c >>> 18) << 6) | ((c & 4095) >>> 6)][o];
    };
  run(4, { leftTrack: 1, rightTrack: 1 });
  run(1);
  const x = 3000 + 160;
  const shoe = height(x, 2600 + 170) - was(x, 2600 + 170);
  assert.ok(shoe < -1 && shoe > -12, `rut depth ${shoe.toFixed(1)} mm`);
  // A second pass over the same rut does not sink the machine any further.
  const z = s.machine.z;
  run(3.9, { leftTrack: -1, rightTrack: -1 });
  run(3.9, { leftTrack: 1, rightTrack: 1 });
  run(1);
  assert.ok(Math.abs(s.machine.z - z) < 4, "it rides its own rut");
  assert.ok(near(s.totalVolume(), volume, 1));
});

test("the turning upper body pushes aside a pile it swings into", () => {
  const s = new SandSimulation();
  s.speed = 1;
  s.machine.strokes = [60, 0, 0];
  place(s, -3000, -700, 0);
  // A tall heap right behind the cab, as if dumped there.
  for (let k = 0; k < 600; k++)
    s.terrain.deposit(-3000 - 40 * (k % 2), -700 + 90 + 10 * (k % 5), 12000);
  const volume = s.totalVolume();
  s.axes = { ...neutral(), slew: 1 };
  for (let i = 0; i < 400; i++) s.substep(1 / 120);
  const m = s.machine,
    a = (m.slew * Math.PI) / 180;
  for (let u = -130; u <= 130; u += 20)
    for (let v = -140; v <= 120; v += 20) {
      const cell = s.terrain.cellAt(
        m.x + u * Math.cos(a) - v * Math.sin(a),
        m.y + u * Math.sin(a) + v * Math.cos(a),
      );
      assert.ok(
        s.terrain.surface(cell) <= m.z + 110 + 20,
        "no sand stands inside the turning body",
      );
    }
  assert.ok(near(s.totalVolume(), volume, 1e-3));
});

test("a full grain budget falls back to bulldozing without losing sand", () => {
  const s = new SandSimulation(),
    run = runner(s),
    volume = s.totalVolume();
  s.speed = 1;
  const before = snapshot(s.terrain);
  s.freeCount = 0; // no grains available
  run(1.2, { boom: -1 });
  run(1.6, { stick: 1 });
  assert.equal(s.grains, 0);
  assert.ok(near(s.totalVolume(), volume, 1));
  // The cut still displaced the bed around the bucket.
  let moved = 0;
  s.terrain.pages.forEach((page, p) => {
    if (!page) return;
    const old = before[p];
    for (let o = 0; o < page.length; o++)
      moved += Math.abs(page[o] - (old ? old[o] : 0)) * CELL_AREA;
  });
  assert.ok(moved > 20000, `the bucket bulldozed ${moved.toFixed(0)} mm³`);
});

test(
  "hard digging in deep sand stays on budget and raises no spike",
  { timeout: 120000 },
  () => {
    const s = new SandSimulation(),
      run = runner(s),
      volume = s.totalVolume();
    s.speed = 1;
    run(1.2, { boom: -1 });
    run(2, { stick: 1 });
    let most = 0,
      worst = 0;
    for (const [seconds, axes] of [
      [3, { leftTrack: 1, rightTrack: 1 }],
      [3, { slew: 1 }],
      [3, { slew: -1, stick: -0.5 }],
    ])
      for (let i = 0; i < seconds * 6; i++) {
        run(1 / 6, axes);
        most = Math.max(most, s.grains);
        worst = Math.max(worst, worstFin(s));
      }
    assert.ok(
      most <= SAND.grainBudget + 40,
      `free grains stay within the budget (${most})`,
    );
    assert.ok(worst < 90, `bulldozing raises a berm, not a spike (${worst})`);
    assert.ok(near(s.totalVolume(), volume, 1));
  },
);

test("sand can be dumped anywhere in the world and stays there", () => {
  const s = new SandSimulation(),
    t = s.terrain,
    [x, y] = [-9000, 800],
    volume = s.totalVolume();
  assert.equal(t.get(t.cellAt(x, y)), 0);
  const pages = t.pages.filter(Boolean).length;
  for (let k = 0; k < 40; k++)
    s.spawn(
      x + 3 * (k % 7),
      y + 3 * (k % 5),
      groundHeight(x, y) + 30 + 9 * k,
      0,
      0,
      0,
      0,
      null,
    );
  assert.ok(near(s.totalVolume(), volume + 40 * SAND.grainVolume, 1e-3));
  const settled = s.totalVolume();
  for (let i = 0; i < 2400 && s.grains; i++) s.substep(1 / 120);
  assert.equal(s.grains, 0, "the grains land on the ground and join the bed");
  assert.ok(near(s.totalVolume(), settled, 1e-3));
  assert.ok(t.get(t.cellAt(x, y)) > 0, "the sand is on the road");
  const added = t.pages.filter(Boolean).length - pages;
  assert.ok(added >= 1 && added <= 4, `${added} pages hold the new sand`);
});

test("only changed tiles are published, and a reset restores exactly them", () => {
  const s = new SandSimulation(),
    t = s.terrain,
    store = new Map(),
    first = t.quantize(store);
  assert.ok(first.length > 1000);
  assert.ok(first.length < TILE_COUNT / 10);
  assert.deepEqual(t.quantize(store), [], "nothing changes on its own");
  const [x, y] = [-9000, 800],
    original = new Map(store);
  t.deposit(x, y, 5000);
  const changed = t.quantize(store);
  assert.ok(changed.length >= 1 && changed.length <= 4);
  s.reset();
  const back = s.terrain.quantize(store);
  assert.deepEqual(
    back.sort((a, b) => a - b),
    [...changed].sort((a, b) => a - b),
    "a reset resends only what the player changed",
  );
  for (const tile of changed) {
    assert.ok(store.get(tile).every((v) => v === 0));
    assert.equal(original.has(tile), false);
  }
});

test("binary frames carry far-away positions and any tile exactly", () => {
  const machine = {
      strokes: [1, 2, 3],
      slew: 40,
      x: 18765.5,
      y: -19000.25,
      z: 1234.5,
      heading: 1.5,
      pitch: 0.25,
      roll: -0.125,
      tracks: [5000, -4000],
    },
    origin = [18766, -19000, 1235],
    q = SAND.positionQuantum,
    grains = Int16Array.from([17, 12.3 / q, -45.6 / q, 7.8 / q]),
    heights = new Uint16Array(TILE_CELLS).map((_, k) => k * 3),
    frame = decodeFrame(
      encodeFrame({
        tick: 99,
        machine,
        grains,
        origin,
        tileData: new Map([[TILE_COUNT - 1, heights]]),
        tiles: [TILE_COUNT - 1, 5],
      }),
    );
  assert.equal(frame.tick, 99);
  assert.deepEqual(frame.origin, origin);
  assert.deepEqual(frame.machine, machine);
  assert.deepEqual([...frame.grains], [...grains]);
  assert.equal(frame.tiles[0].index, TILE_COUNT - 1);
  assert.deepEqual([...frame.tiles[0].heights], [...heights]);
  assert.equal(frame.tiles[1].index, 5, "a tile with no data is sent empty");
  assert.ok(frame.tiles[1].heights.every((v) => v === 0));
  assert.ok(YARD.maxX > 6000, "the yard is many times the old pit");
  assert.ok(initialTerrain() instanceof Terrain);
});

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
  insideCavity,
  firstCrossing,
  CROSS_MOUTH,
  WALLS,
  TEETH,
} from "../server/bucket.js";
import { CELL_AREA } from "../server/terrain.js";
import { solve } from "../shared/kinematics.js";
import {
  WORLD,
  SAND,
  neutral,
  groundHeight,
  crawlerExtent,
} from "../shared/world.js";

const R = WORLD.radius;
const TALUS = Math.tan((SAND.reposeDeg * Math.PI) / 180);

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
function maxBedSlope(s) {
  const { nx, ny } = SAND,
    t = s.terrain;
  let steepest = 0;
  for (let j = 0; j < ny; j++)
    for (let i = 0; i + 1 < nx; i++) {
      const c = j * nx + i;
      if (t.h[c] < 0.5 && t.h[c + 1] < 0.5) continue;
      steepest = Math.max(
        steepest,
        Math.abs(t.surface(c) - t.surface(c + 1)) / SAND.cell,
      );
    }
  return steepest;
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

test("the initial sand bed is at rest below its angle of repose", () => {
  const s = new SandSimulation(),
    run = runner(s);
  const before = s.terrain.h.slice(),
    volume = s.totalVolume();
  assert.ok(volume > 8e6, "the pit holds several litres of sand");
  assert.ok(maxBedSlope(s) <= TALUS + 0.01);
  run(1);
  assert.equal(s.resting, true);
  assert.equal(s.grains, 0);
  assert.deepEqual(s.terrain.h, before, "an idle bed does not creep");
  assert.equal(
    s.terrain.volumeIn({ minX: 260, maxX: 620, minY: 220, maxY: 490 }),
    0,
  );
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
      Math.abs(s.totalVolume() - volume) / volume < 1e-9,
      "sand volume is conserved",
    );
    assert.ok(
      maxBedSlope(s) <= TALUS + 0.02,
      "the dumped pile slumps to repose",
    );
    for (let i = 0; i < SAND.maxGrains; i++)
      if (s.alive[i]) {
        assert.ok(s.pos[3 * i + 2] >= groundHeight(s.pos[3 * i]) + R - 0.5);
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
    assert.ok(Math.abs(s.totalVolume() - volume) / volume < 1e-9);
  },
);

test("an over-steep sand heap avalanches to its angle of repose", () => {
  const s = new SandSimulation(),
    run = runner(s);
  // Drop a tall column of sand onto the pit floor.
  for (let k = 0; k < 40; k++) s.terrain.deposit(850, 300, 4000);
  const volume = s.totalVolume();
  assert.ok(maxBedSlope(s) > 2);
  run(6);
  assert.ok(maxBedSlope(s) <= TALUS + 0.01);
  assert.ok(Math.abs(s.totalVolume() - volume) / volume < 1e-12);
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

test("the bucket cannot be driven through the concrete apron or pit floor", () => {
  const s = new SandSimulation();
  s.speed = 1;
  // Bucket beside the crawler, over the apron: lowering with the stick
  // crowded would put the teeth 60 mm into the concrete.
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

test("crawler reaches every map edge and turns without crossing the walls", () => {
  const s = new SandSimulation();
  s.speed = 1;
  for (let direction = 0; direction < 8; direction++) {
    s.machine.heading = (direction * Math.PI) / 4;
    s.axes = { ...neutral(), leftTrack: 1, rightTrack: 1 };
    s.advanceMachine(60);
    const extent = crawlerExtent(s.machine.heading);
    if (Math.cos(s.machine.heading) > 0.1)
      assert.equal(s.machine.x, WORLD.maxX - extent.x);
    if (Math.cos(s.machine.heading) < -0.1)
      assert.equal(s.machine.x, WORLD.minX + extent.x);
    if (Math.sin(s.machine.heading) > 0.1)
      assert.equal(s.machine.y, WORLD.maxY - extent.y);
    if (Math.sin(s.machine.heading) < -0.1)
      assert.equal(s.machine.y, WORLD.minY + extent.y);
    s.axes = { ...neutral(), leftTrack: -1, rightTrack: 1 };
    for (let i = 0; i < 100; i++) {
      s.advanceMachine(1 / 30);
      const turned = crawlerExtent(s.machine.heading);
      assert.ok(s.machine.x - turned.x >= WORLD.minX - 1e-9);
      assert.ok(s.machine.x + turned.x <= WORLD.maxX + 1e-9);
      assert.ok(s.machine.y - turned.y >= WORLD.minY - 1e-9);
      assert.ok(s.machine.y + turned.y <= WORLD.maxY + 1e-9);
    }
  }
});

test("crawler and bucket descend the ramp continuously and grains meet the terrain", () => {
  const s = new SandSimulation();
  const initial = bucketPose(s.machine);
  s.speed = 1;
  s.axes = { ...neutral(), leftTrack: 1, rightTrack: 1 };
  let height = 0;
  for (let i = 0; i < 300; i++) {
    s.advanceMachine(1 / 30);
    assert.ok(s.machine.z <= height);
    assert.ok(
      Math.abs(s.machine.z - height) < 2,
      "no vertical teleport at the apron edge",
    );
    height = s.machine.z;
  }
  assert.ok(s.machine.x > 600, "travel goes well beyond the former x=20 limit");
  assert.equal(height, WORLD.floor);
  assert.equal(bucketPose(s.machine).z - initial.z, WORLD.floor);
  // A grain dropped on bare concrete lands one radius above it everywhere
  // (along the surface normal on the ramp), then settles into the bed.
  for (const x of [0, WORLD.platformEdge, 250, WORLD.rampEnd]) {
    s.reset();
    s.spawn(x, -450, groundHeight(x) + 30, 0, 0, 0, 0, null);
    const volume = s.totalVolume();
    let landed = false;
    for (let i = 0; i < 40 && !landed; i++) {
      s.substep(1 / 120);
      if (s.alive[0] && s.ground[0]) {
        landed = true;
        assert.ok(Math.abs(s.pos[2] - (groundHeight(s.pos[0]) + R)) < 1);
      }
    }
    assert.ok(landed, `grain lands at x=${x}`);
    for (let i = 0; i < 240 && s.grains; i++) s.substep(1 / 120);
    assert.equal(s.grains, 0, "a resting grain rejoins the bed");
    assert.ok(Math.abs(s.totalVolume() - volume) < 1e-6);
  }
  s.axes = { ...neutral(), leftTrack: -1, rightTrack: -1 };
  s.advanceMachine(10);
  assert.equal(s.machine.z, 0, "reverse travel returns to apron height");
});

test(
  "tracks plow through the stockpile and conserve the sand",
  { timeout: 60000 },
  () => {
    const s = new SandSimulation(),
      run = runner(s),
      volume = s.totalVolume();
    s.speed = 1;
    run(2, { boom: 1 });
    run(9, { leftTrack: 1, rightTrack: 1 });
    const m = s.machine,
      c = Math.cos(m.heading),
      sn = Math.sin(m.heading);
    // No sand above the shoes under either track.
    for (const side of [-1, 1])
      for (let u = -140; u <= 140; u += 20) {
        const x = m.x + u * c - side * 170 * sn,
          y = m.y + u * sn + side * 170 * c,
          cell = s.terrain.cellAt(x, y);
        assert.ok(
          s.terrain.surface(cell) <= m.z + 1.5,
          `sand under the track at ${u}`,
        );
      }
    assert.ok(Math.abs(s.totalVolume() - volume) / volume < 1e-9);
  },
);

test("a full grain pool falls back to bulldozing without losing sand", () => {
  const s = new SandSimulation(),
    run = runner(s),
    volume = s.totalVolume();
  s.speed = 1;
  const before = s.terrain.h.slice();
  s.freeCount = 0; // no grains available
  run(1.2, { boom: -1 });
  run(1.6, { stick: 1 });
  assert.equal(s.grains, 0);
  assert.ok(Math.abs(s.totalVolume() - volume) / volume < 1e-9);
  // The cut still displaced the bed around the bucket.
  let moved = 0;
  for (let c = 0; c < before.length; c++)
    moved += Math.abs(s.terrain.h[c] - before[c]) * CELL_AREA;
  assert.ok(moved > 20000, `the bucket bulldozed ${moved.toFixed(0)} mm³`);
});

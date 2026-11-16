import test from "node:test";
import assert from "node:assert/strict";
import { SandSimulation } from "../server/physics.js";
import { neutral, crawlerBox, YARD } from "../shared/world.js";
import { crawlerHitsProp, groundHeight, initialSand } from "../shared/landscape.js";
import { SCOOP, TO_TRUCK, POUR } from "../shared/scoop.js";
import {
  DEFAULT_PLAYERS,
  SPAWNS,
  TRUCK_BAYS,
  parkedTruck,
  spawnMachine,
} from "../shared/players.js";
import {
  TRUCK,
  TRUCK_DRIVE,
  TRUCK_LOAD,
  TYRES,
  WHEEL_SAMPLES,
  MAX_STEER,
  boxesOverlap,
  gateAngle,
  truckBox,
} from "../shared/truck.js";
import { decodeFrame, encodeFrame } from "../shared/protocol.js";

const DEG = Math.PI / 180,
  near = (a, b, tolerance) => Math.abs(a - b) <= tolerance,
  full = (mm) => mm * TRUCK.scale;

// A world with trucks in the given bays, and excavators at the given starts.
function world({ bays = [1], starts = [] } = {}) {
  return new SandSimulation({
    vehicles: starts.map((start, n) => ({ id: n + 1, machine: spawnMachine(start) })),
    trucks: bays.map((bay, n) => ({ id: n + 1, pose: parkedTruck(bay) })),
  });
}
// Hold a machine's controls for a while, at full speed, then let go.
function hold(s, machine, seconds, axes = {}) {
  machine.axes = { ...neutral(), ...axes };
  machine.speed = 1;
  for (let i = 0; i < Math.round(seconds * 30); i++) s.step();
  machine.axes = neutral();
}
const follow = (s, machine, steps) => {
  for (const [seconds, axes] of steps) hold(s, machine, seconds, axes);
};
// Pour sand into a truck's body from above, in passes along it, as an excavator
// would: `volume` mm³ in parcels the size the bed sheds.
function pour(s, truck, volume) {
  const parcel = 447.7,
    world = [0, 0, 0];
  let seed = 7,
    poured = 0;
  const random = () => (seed = (1664525 * seed + 1013904223) >>> 0) / 4294967296;
  for (let pass = 0; poured < volume; pass++) {
    const along = 60 + 220 * ((pass * 0.37) % 1);
    for (let k = 0; k < 600 && poured < volume; k++) {
      truck.frame.toWorld(along + 40 * (random() - 0.5), 50 * (random() - 0.5), 130, world);
      s.spawn(...world, 0, 0, -300, parcel, null);
      poured += parcel;
      if (k % 25 === 0) {
        s.resting = false;
        s.step();
      }
    }
    s.resting = false;
    for (let i = 0; i < 30; i++) s.step();
  }
  for (let i = 0; i < 60; i++) s.step();
  return poured;
}

test("the truck is a Volvo FMX13 6x4 with a Schwarzmüller tipper body, at 1:15", () => {
  // Volvo's model range sheet for the FMX 6x4 rigid.
  assert.ok(near(full(TRUCK.wheelbase), 3700 + 1370 / 2, 1e-9));
  assert.ok(near(full(TRUCK.rearAxles[0] - TRUCK.rearAxles[1]), 1370, 1e-9));
  assert.ok(near(full(TRUCK.bumper - TRUCK.frontAxle), 1520, 1e-9));
  assert.ok(near(full(TRUCK.frontAxle - TRUCK.cabBack), 515, 1e-9));
  assert.ok(near(full(TRUCK.cabHeight), 3144, 1e-9));
  assert.ok(near(full(2 * TRUCK.cabHalfWidth), 2500, 1e-9));
  assert.ok(near(full(TRUCK.frame), 1111, 1e-9));
  // 315/80R22.5 tyres: a 22.5 inch rim and two sidewalls 80 % of 315 mm high.
  assert.ok(near(full(2 * TRUCK.tyreRadius), 22.5 * 25.4 + 2 * 0.8 * 315, 1e-9));
  assert.equal(TYRES.length, 10, "single front tyres, twins on both rear axles");
  // At full lock the outer front tyre runs round the 15.5 m kerb-to-kerb circle.
  const centre = TRUCK.wheelbase / Math.tan(MAX_STEER),
    kerb =
      Math.hypot(TRUCK.wheelbase, centre + TRUCK.frontTrack) + TRUCK.tyreWidth / 2;
  assert.ok(near(full(2 * kerb), 15500, 1e-6));
  assert.ok(MAX_STEER > 38 * DEG && MAX_STEER < 42 * DEG);
  // Schwarzmüller's 3-way tipper body.
  assert.ok(near(full(TRUCK.innerLength), 5100, 1e-9));
  assert.ok(near(full(2 * TRUCK.innerHalfWidth), 2420, 1e-9));
  assert.ok(near(full(2 * TRUCK.bodyHalfWidth), 2550, 1e-9));
  assert.ok(near(full(TRUCK.sideWall), 880, 1e-9));
  assert.ok(near(full(TRUCK.frontWall), 980, 1e-9));
  assert.ok(near(full(TRUCK.rearWall), 980, 1e-9));
  assert.ok(near(TRUCK.maxTip, 49 * DEG, 1e-12));
  const cubicMetres = (TRUCK_LOAD.struck * TRUCK.scale ** 3) / 1e9;
  assert.ok(cubicMetres > 10.5 && cubicMetres < 11.5, `about 11 m³: ${cubicMetres}`);
  assert.ok(
    near(TRUCK_LOAD.cells * TRUCK_LOAD.area * TRUCK.sideWall, TRUCK_LOAD.struck, 1e-6),
    "the load's columns fill the body",
  );
  // The body sits behind the cab, over the rear tandem.
  assert.ok(TRUCK.bodyFront < TRUCK.cabBack);
  assert.ok(TRUCK.bodyRear < TRUCK.rearAxles[1] - TRUCK.tyreRadius);
});

test("every truck bay is level hard ground, in no start's way, and its truck drives straight out", () => {
  assert.equal(TRUCK_BAYS.length, SPAWNS.length, "a bay for every seat");
  const parked = TRUCK_BAYS.map((_, bay) => truckBox(parkedTruck(bay))),
    starts = SPAWNS.map((_, seat) => crawlerBox(spawnMachine(seat)));
  TRUCK_BAYS.forEach((_, bay) => {
    const pose = parkedTruck(bay),
      c = Math.cos(pose.heading),
      s = Math.sin(pose.heading),
      name = `bay ${bay}`;
    for (const [u, v] of WHEEL_SAMPLES) {
      const x = pose.x + u * c - v * s,
        y = pose.y + u * s + v * c;
      assert.equal(initialSand(x, y), 0, `${name} stands on sand`);
      assert.ok(
        Math.abs(groundHeight(x, y) - groundHeight(pose.x, pose.y)) < 3,
        `${name} is not level`,
      );
    }
    // Out of its bay with every other truck parked and every machine at its start.
    for (let ahead = 0; ahead <= 600; ahead += 20) {
      const box = truckBox({ ...pose, x: pose.x + ahead * c, y: pose.y + ahead * s });
      assert.equal(
        crawlerHitsProp(box.x, box.y, c, s, box.halfLength, box.halfWidth),
        false,
        `${name} meets the scenery ${ahead} mm out`,
      );
      parked.forEach((other, k) =>
        assert.ok(k === bay || !boxesOverlap(box, other), `${name} meets bay ${k}`),
      );
      starts.forEach((start, seat) =>
        assert.equal(boxesOverlap(box, start), false, `${name} meets start ${seat}`),
      );
    }
  });
  // No truck stands between a start and its chase camera, 1140 mm behind it.
  SPAWNS.forEach((_, seat) => {
    const { x, y, heading } = spawnMachine(seat);
    for (let behind = 0; behind <= 1140; behind += 20) {
      const point = {
        x: x - behind * Math.cos(heading),
        y: y - behind * Math.sin(heading),
        c: 1,
        s: 0,
        halfLength: 60,
        halfWidth: 60,
      };
      parked.forEach((box, bay) =>
        assert.equal(boxesOverlap(point, box), false, `bay ${bay} hides start ${seat}`),
      );
    }
  });
  // The first player's truck stands beside the start, its body where the bucket
  // swings at 90 degrees right; everyone else's truck waits on their side.
  assert.ok(
    boxesOverlap(truckBox(parkedTruck(0)), { ...starts[0], halfLength: 600, halfWidth: 600 }),
  );
  for (let seat = 1; seat < DEFAULT_PLAYERS; seat++)
    assert.equal(
      Math.sign(TRUCK_BAYS[seat][1]),
      Math.sign(SPAWNS[seat][1]),
      `seat ${seat}'s truck waits on its side of the yard`,
    );
});

test("the truck drives, steers like a bicycle with its wheelbase, and stops at things in its way", () => {
  const s = world(),
    truck = s.trucks[0],
    start = { ...truck.pose };
  hold(s, truck, 3, { drive: 1 });
  assert.ok(near(truck.pose.velocity, TRUCK_DRIVE.topSpeed, 1e-6), "at top speed");
  hold(s, truck, 1.5);
  assert.equal(truck.pose.velocity, 0, "it stops when let go");
  assert.equal(truck.stats.velocity, 0);
  const travelled = truck.pose.x - start.x;
  assert.ok(travelled > 1200, `it drove ${travelled} mm`);
  assert.ok(near(truck.pose.y, start.y, 1e-6) && near(truck.pose.heading, start.heading, 1e-9));
  assert.ok(near(truck.pose.wheels, travelled, 1e-6), "the wheels roll with it");
  // Full lock to the left: once the wheels are over, it turns about a point the
  // wheelbase over tan(lock) to its left.
  truck.axes = { ...neutral(), drive: 0.5, steer: 1 };
  truck.speed = 1;
  for (let i = 0; i < 60; i++) s.step();
  assert.ok(near(truck.pose.steer, MAX_STEER, 1e-9));
  const heading = truck.pose.heading,
    wheels = truck.pose.wheels;
  for (let i = 0; i < 45; i++) s.step();
  const radius = (truck.pose.wheels - wheels) / (truck.pose.heading - heading);
  assert.ok(
    near(radius, TRUCK.wheelbase / Math.tan(MAX_STEER), 2),
    `turning radius ${radius} mm`,
  );
  // Reversing is slower.
  hold(s, truck, 1.5);
  truck.axes = { ...neutral(), drive: -1 };
  for (let i = 0; i < 60; i++) s.step();
  assert.ok(near(truck.pose.velocity, -TRUCK_DRIVE.reverseSpeed, 1e-6));
  hold(s, truck, 1);

  // An excavator in the way stops the truck, and the excavator cannot drive into
  // it either; backing away is always allowed.
  const meet = new SandSimulation({
      vehicles: [{ id: 1, machine: { ...spawnMachine(1), x: -500, y: 1650 } }],
      trucks: [{ id: 1, pose: parkedTruck(1) }],
    }),
    blocked = meet.trucks[0],
    excavator = meet.vehicles[0];
  hold(meet, blocked, 3, { drive: 1 });
  assert.equal(blocked.stats.obstacle, "machine");
  assert.ok(!boxesOverlap(truckBox(blocked.pose), crawlerBox(excavator.machine)));
  assert.ok(blocked.pose.x > -1300, "it got close first");
  const x = blocked.pose.x;
  hold(meet, blocked, 1, { drive: -1 });
  assert.ok(blocked.pose.x < x - 50, "it can back away");
  hold(meet, blocked, 1);
  const crawler = excavator.machine.x;
  hold(meet, excavator, 4, { leftTrack: -1, rightTrack: -1 });
  assert.ok(!boxesOverlap(truckBox(blocked.pose), crawlerBox(excavator.machine)));
  assert.ok(excavator.machine.x < crawler - 50, "the excavator came closer, and stopped");
});

test("sand poured into a truck's body stays in it, and none is lost", { timeout: 60000 }, () => {
  const s = world(),
    truck = s.trucks[0],
    before = s.totalVolume(),
    poured = pour(s, truck, 0.9 * TRUCK_LOAD.struck);
  assert.ok(near(s.totalVolume(), before + poured, 1), "volume is conserved");
  assert.ok(truck.load.total > 0.97 * poured, `${truck.load.total} of ${poured} mm³`);
  assert.ok(truck.stats.load > 0.9 * TRUCK_LOAD.struck * 0.97 * 1e-3);
  assert.equal(s.grains, 0, "nothing is left in the air");
  // It comes to rest below its angle of repose, and stays put while driven.
  const load = truck.load.total;
  hold(s, truck, 3, { drive: 1 });
  hold(s, truck, 1.5, {});
  assert.ok(truck.load.total > 0.99 * load, "a load does not trickle away on the road");
  assert.equal(gateAngle(truck.pose), 0, "the rear wall stays latched");
});

test(
  "raising the body tips the load out over the rear, and sand tipped beyond the yard counts as hauled",
  { timeout: 90000 },
  () => {
    const s = world(),
      truck = s.trucks[0],
      before = s.totalVolume(),
      poured = pour(s, truck, TRUCK_LOAD.struck),
      load = truck.load.total;
    // Lifting: the rear wall swings open, and the truck only creeps.
    hold(s, truck, 2, { hoist: 1 });
    assert.ok(truck.pose.tip > 7 * DEG && truck.pose.tip < 9 * DEG, `${truck.pose.tip}`);
    assert.ok(gateAngle(truck.pose) > 0, "the rear wall swings free");
    assert.ok(truck.stats.gate);
    truck.axes = { ...neutral(), drive: 1 };
    for (let i = 0; i < 45; i++) s.step();
    assert.ok(near(truck.pose.velocity, TRUCK_DRIVE.raisedSpeed, 1e-6));
    hold(s, truck, 1, {});
    // All the way up, it empties.
    hold(s, truck, 13, { hoist: 1 });
    assert.ok(near(truck.pose.tip, TRUCK.maxTip, 1e-9));
    for (let i = 0; i < 90; i++) s.step();
    const left = truck.load.total;
    assert.ok(left < 0.03 * load, `${left} of ${load} mm³ left`);
    assert.equal(s.grains, 0);
    // The sand lies in a heap behind the truck.
    const behind = [0, 0, 0];
    truck.frame.toWorld(-60, 0, 0, behind);
    const c = Math.cos(truck.pose.heading),
      sn = Math.sin(truck.pose.heading),
      rear = truck.pose.x + c * TRUCK.bodyRear;
    let heap = 0;
    for (let d = 20; d <= 400; d += 10)
      heap = Math.max(heap, groundSand(s, rear - c * d, truck.pose.y - sn * d));
    assert.ok(heap > 40, `a heap ${heap} mm high behind the truck`);
    // This bay is outside the yard: everything that left over the rear counts.
    assert.ok(truck.pose.x < YARD.minX);
    assert.ok(
      near(truck.stats.hauled * 1000, load - left, 0.02 * load),
      `${truck.stats.hauled} cm³ of ${load - left} mm³`,
    );
    // Down again, the rear wall latches.
    hold(s, truck, 10, { hoist: -1 });
    assert.equal(truck.pose.tip, 0);
    assert.equal(gateAngle(truck.pose), 0);
    assert.ok(near(s.totalVolume(), before + poured, 1), "volume is conserved");
  },
);
// Sand over the hard ground at a point (mm).
function groundSand(s, x, y) {
  const surface = [0, 0, 0];
  s.terrain.sample(x, y, surface);
  return surface[0] - groundHeight(x, y);
}

test(
  "the first excavator loads the first truck from the start position, and the truck hauls it away",
  { timeout: 90000 },
  () => {
    const s = world({ bays: [0], starts: [0] }),
      [excavator] = s.vehicles,
      [truck] = s.trucks,
      before = s.totalVolume();
    follow(s, excavator, [...SCOOP, ...TO_TRUCK]);
    const dug = excavator.load.total;
    assert.ok(dug > 250000, `a full bucket: ${dug} mm³`);
    assert.ok(near(excavator.machine.slew, -90, 0.5));
    follow(s, excavator, POUR);
    hold(s, excavator, 2);
    assert.ok(truck.load.total > 0.95 * dug, `${truck.load.total} of ${dug} mm³ in the truck`);
    assert.equal(s.world.deposited, 0, "none on the pour zone");
    // Off it goes, and tips its load out by the road.
    const load = truck.load.total;
    hold(s, truck, 2.5, { drive: 1 });
    hold(s, truck, 1.5);
    assert.ok(truck.pose.x < -500, "it drove off");
    assert.ok(truck.load.total > 0.99 * load);
    hold(s, truck, 14, { hoist: 1 });
    hold(s, truck, 3);
    assert.ok(truck.load.total < 0.02 * load);
    assert.ok(near(truck.stats.hauled * 1000, load, 0.03 * load));
    assert.ok(near(s.totalVolume(), before, 1), "volume is conserved");
  },
);

test("a truck that leaves or jumps back to its bay leaves its load on the ground", { timeout: 60000 }, () => {
  const s = world({ bays: [1, 3] }),
    [first, second] = s.trucks;
  let poured = pour(s, first, 0.5 * TRUCK_LOAD.struck);
  poured += pour(s, second, 0.5 * TRUCK_LOAD.struck);
  const before = s.totalVolume(),
    ground = s.terrain.volume();
  assert.ok(first.load.total > 0 && second.load.total > 0);
  s.placeTruck(first, parkedTruck(1));
  assert.equal(first.load.total, 0);
  s.removeTruck(second);
  assert.equal(s.trucks.length, 1);
  for (let i = 0; i < 30; i++) s.step();
  assert.ok(s.terrain.volume() > ground + 0.97 * poured - 1);
  assert.ok(near(s.totalVolume(), before, 1));
});

test("binary frames carry each truck's pose and load exactly", () => {
  const truck = {
      id: 3,
      x: -1600.25,
      y: 1650.5,
      z: 2.25,
      heading: 0.5,
      pitch: -0.125,
      roll: 0.0625,
      steer: 0.25,
      tip: 0.75,
      wheels: 12345.5,
    },
    load = new Uint16Array(TRUCK_LOAD.cells).map((_, k) => k * 7 + 1),
    frame = decodeFrame(
      encodeFrame({
        tick: 5,
        machines: [{ ...spawnMachine(0), id: 3, load: null }],
        trucks: [
          { ...truck, load },
          { ...truck, id: 4, load: null },
        ],
        grains: new Int16Array(0),
        groups: new Int32Array(0),
        tileData: new Map(),
        tiles: [],
      }),
    );
  assert.equal(frame.trucks.length, 2);
  assert.deepEqual({ ...frame.trucks[0], load: null }, { ...truck, load: null });
  assert.deepEqual([...frame.trucks[0].load], [...load]);
  assert.equal(frame.trucks[1].id, 4);
  assert.equal(frame.trucks[1].load, null, "an empty body sends nothing");
  assert.equal(frame.machines[0].id, 3);
});

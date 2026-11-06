import test from "node:test";
import assert from "node:assert/strict";
import { Scene, Texture } from "three";
import { createDust, createLooseGrains } from "../client/loose-grains.js";
import { createLooseSandView } from "../client/loose-sand-view.js";
import { initialMachine } from "../shared/world.js";

const positionOf = (scene, name) =>
  scene.getObjectByName(name).geometry.attributes.position.array;
const run = (grains, seconds) => {
  for (let t = 0; t < seconds; t += 1 / 60) grains.step(1 / 60);
};

test("a loose grain falls, rolls on down a slope at repose and stops on the flat", () => {
  const scene = new Scene(),
    repose = Math.tan((34 * Math.PI) / 180),
    // Down towards +x until x = 0, and level after that.
    grains = createLooseGrains(scene, (x) => Math.max(0, -repose * x), 10);
  grains.emit(-200, 0, 300, 0, 0, 0, 5, 1);
  const position = positionOf(scene, "loose grains");
  run(grains, 0.1);
  assert.ok(position[2] > 200, `still in the air at ${position[2]}`);
  run(grains, 0.25);
  assert.ok(position[0] > -200, `on its way down the slope, at ${position[0]}`);
  assert.ok(
    position[2] <= repose * -position[0] + 1,
    "on the slope, not under it",
  );
  run(grains, 5);
  assert.equal(grains.count, 0, "stopped, and gone into the bed");
});

test("a grain that stops on level sand does not last, and one in the air does", () => {
  const scene = new Scene(),
    grains = createLooseGrains(scene, () => 0, 10);
  grains.emit(0, 0, 0.5, 40, 0, 0, 5, 1);
  grains.emit(0, 0, 1e5, 0, 0, 0, 5, 1);
  run(grains, 1);
  assert.equal(grains.count, 1);
  assert.ok(positionOf(scene, "loose grains")[2] > 9e4);
});

test("loose grains keep to their pool, and report whether any are left", () => {
  const scene = new Scene(),
    grains = createLooseGrains(scene, () => 0, 3);
  assert.equal(grains.step(1 / 60), false);
  for (let n = 0; n < 5; n++) grains.emit(n, 0, 100, 0, 0, 0, 0.5, 1);
  assert.equal(grains.count, 3);
  assert.equal(grains.step(1 / 60), true);
  assert.equal(
    scene.getObjectByName("loose grains").geometry.drawRange.count,
    3,
  );
  grains.clear();
  assert.equal(grains.count, 0);
  assert.equal(
    scene.getObjectByName("loose grains").geometry.drawRange.count,
    0,
  );
});

test("dust is only worth drawing for as long as it lasts", () => {
  const scene = new Scene(),
    dust = createDust(scene, 4),
    range = scene.getObjectByName("dust").geometry.drawRange;
  assert.equal(dust.step(1 / 60), false, "none yet");
  for (let n = 0; n < 6; n++) dust.emit(0, 0, 0, 0, 0, 30, 1);
  assert.equal(range.count, 4, "the oldest make way");
  assert.equal(dust.step(0.5), true);
  assert.equal(dust.step(0.6), false);
  assert.equal(range.count, 0);
});

// Parcels in two frames, as the network delivers them.
function parcels(tick, list) {
  return {
    tick,
    slots: Uint16Array.from(list.map(([slot]) => slot)),
    holders: new Uint16Array(list.length),
    positions: Float32Array.from(list.flatMap(([, ...at]) => at)),
    machines: [],
    byId: new Map(),
    tiles: [],
  };
}

test("a parcel throws up grains where it lands, not where it goes into a bucket", () => {
  const scene = new Scene(),
    view = createLooseSandView(scene, new Texture(), false, () => 0),
    camera = { x: 0, y: 0, z: 500 };
  const fly = (height) => {
    const first = parcels(10, [[3, 0, 0, height + 60]]),
      second = parcels(11, [[3, 0, 0, height]]),
      third = parcels(12, []);
    view.pushFrame(first);
    view.pushFrame(second, first);
    view.pushFrame(third, second);
    view.settle(third, camera);
    view.stepGrains(1 / 60);
  };
  fly(400);
  assert.equal(
    view.looseGrains,
    0,
    "gone high above the bed: caught by a bucket",
  );
  fly(40);
  assert.ok(view.looseGrains > 0, "landed");
  const landed = view.looseGrains;
  view.settle(parcels(12, []), camera);
  assert.equal(view.looseGrains, landed, "a landing happens once");
  view.clear();
  assert.equal(view.looseGrains, 0);
});

test("loose grains are not worth working out far from the camera", () => {
  const scene = new Scene(),
    view = createLooseSandView(scene, new Texture(), false, () => 0),
    first = parcels(10, [[3, 0, 0, 100]]),
    second = parcels(11, [[3, 0, 0, 40]]),
    third = parcels(12, []);
  view.pushFrame(first);
  view.pushFrame(second, first);
  view.pushFrame(third, second);
  view.settle(third, { x: 20000, y: 0, z: 500 });
  view.moved(0, 0, -5);
  assert.equal(view.looseGrains, 0);
});

test("the bed moving sets grains off down its slope, in proportion", () => {
  const scene = new Scene(),
    view = createLooseSandView(scene, new Texture(), false, (x) => 200 - x),
    camera = { x: 0, y: 0, z: 500 };
  view.settle(parcels(1, []), camera);
  for (let n = 0; n < 200; n++) view.moved(0, 0, 0.05);
  assert.equal(view.looseGrains, 0, "too little to see: a slope creeping");
  for (let n = 0; n < 200; n++) view.moved(0, 0, -1);
  assert.ok(view.looseGrains > 100, `${view.looseGrains}`);
  const position = positionOf(scene, "loose grains"),
    count = view.looseGrains,
    start = position[0] + position[3];
  view.stepGrains(0.02);
  assert.ok(view.looseGrains <= count);
  assert.ok(position[0] + position[3] > start, "towards the low side");
});

test("a bucket goes on dribbling for a while after its stream stops", () => {
  const scene = new Scene(),
    machine = initialMachine(),
    poses = new Map([[1, machine]]),
    view = createLooseSandView(scene, new Texture(), false, () => -1e4);
  view.settle(parcels(1, []), { x: machine.x, y: machine.y, z: 500 });
  const frame = (tick, count) => {
    const list = Array.from({ length: count }, (_, n) => [n, n, 0, 900]),
      result = parcels(tick, list);
    result.holders.fill(1);
    result.machines = [{ id: 1, load: null }];
    result.byId = new Map([[1, result.machines[0]]]);
    return result;
  };
  let last = frame(1, 12);
  view.update(last, last, 1, poses);
  assert.equal(view.looseGrains, 0, "there is nothing to add to a full stream");
  for (let tick = 2; tick < 6; tick++) {
    const next = frame(tick, tick === 2 ? 12 : 0);
    view.update(last, next, 1, poses);
    last = next;
  }
  assert.ok(
    view.looseGrains > 20,
    `${view.looseGrains} grains after it stopped`,
  );
  for (let tick = 6; tick < 200; tick++) {
    const next = frame(tick, 0);
    view.update(last, next, 1, poses);
    last = next;
    view.stepGrains(1 / 30);
  }
  const before = view.looseGrains;
  view.update(last, frame(201, 0), 1, poses);
  assert.equal(view.looseGrains, before, "and then it stops");
});

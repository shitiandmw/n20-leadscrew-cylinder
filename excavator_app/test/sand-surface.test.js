import test from "node:test";
import assert from "node:assert/strict";
import { MeshStandardMaterial, Scene, Texture } from "three";
import { MarchingCubes } from "three/addons/objects/MarchingCubes.js";
import {
  SandSurfaceField,
  SURFACE_SIZE,
  SURFACE_CENTRE,
  SURFACE_LEVEL,
  loadClearance,
} from "../client/sand-surface.js";
import { createLooseSandView } from "../client/loose-sand-view.js";
import { bucketPose, toWorld } from "../server/physics.js";
import { initialMachine, SAND } from "../shared/world.js";

test("isolated moving sand never reconstructs a large bead", () => {
  const field = new SandSurfaceField(40);
  field.add(0, 0, -45);
  field.finish();
  assert.ok(field.field.every((value) => value < SURFACE_LEVEL));
});

for (const resolution of [32, 40])
  test(`dense load stays inside CAD plates at resolution ${resolution}`, () => {
    const surface = new MarchingCubes(
      resolution,
      new MeshStandardMaterial(),
      false,
      false,
      20000,
    );
    surface.isolation = SURFACE_LEVEL;
    const field = new SandSurfaceField(resolution, surface.field);
    for (let x = -75; x <= 50; x += 7)
      for (let y = -33; y <= 33; y += 7)
        for (let z = -80; z <= 5; z += 7)
          if (loadClearance(x, y, z) >= 4) field.add(x, y, z);
    field.finish();
    surface.update();
    assert.ok(surface.count > 300, "a dense load forms a continuous surface");
    assert.ok(
      surface.count < surface.positionArray.length / 3,
      "mesh fits the bounded buffer",
    );
    for (let i = 0; i < surface.count; i++) {
      const point = [0, 1, 2].map(
        (d) =>
          (surface.positionArray[i * 3 + d] * SURFACE_SIZE) / 2 +
          SURFACE_CENTRE[d],
      );
      assert.ok(point.every(Number.isFinite));
      assert.ok(
        loadClearance(...point) >= -1e-4,
        `surface crossed a bucket plate at ${point}`,
      );
    }
    field.clear();
    field.add(2000, 0, 0);
    field.finish();
    surface.update();
    assert.equal(
      surface.count,
      0,
      "empty/distant material leaves no residual load",
    );
    surface.geometry.dispose();
    surface.material.dispose();
  });

test("loose sand follows snapshot origin, fades transfers, and clears on reset", () => {
  const scene = new Scene(),
    view = createLooseSandView(scene, new Texture(), false);
  const machine = initialMachine(),
    pose = bucketPose(machine);
  const point = toWorld(0, 0, -45, pose),
    origin = [100, -200, 50];
  const empty = { grains: new Int16Array(), origin };
  const full = {
    origin,
    grains: Int16Array.from([
      17,
      ...point.map((value, d) =>
        Math.round((value - origin[d]) / SAND.positionQuantum),
      ),
    ]),
  };
  view.update(empty, full, 0, machine);
  assert.equal(view.count, 0, "new grains start hidden");
  view.update(empty, full, 1, machine);
  assert.equal(view.count, 1);
  assert.equal(view.triangles, 0, "a lone grain is fine detail only");
  const points = scene.children.find((child) => child.isPoints);
  const parcel = points.geometry.getAttribute("parcel");
  for (let d = 0; d < 3; d++)
    assert.ok(Math.abs(parcel.array[d] - point[d]) <= 0.051);
  view.update(full, empty, 0.5, machine);
  assert.equal(
    parcel.array[3],
    0.5,
    "settling fades coverage, not grain diameter",
  );
  view.clear();
  assert.equal(view.count, 0);
  assert.equal(points.geometry.instanceCount, 0);
  assert.equal(view.triangles, 0);
});

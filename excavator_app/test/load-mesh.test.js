import test from "node:test";
import assert from "node:assert/strict";
import { MeshBasicMaterial, Scene, Texture, Vector3 } from "three";
import { createLoadMeshes, LOAD_TRIANGLES } from "../client/load-mesh.js";
import { createLooseSandView } from "../client/loose-sand-view.js";
import { bucketPose, toWorld } from "../server/physics.js";
import { LOAD, localU, localW } from "../shared/bucket-load.js";
import { BucketFrame } from "../shared/bucket.js";
import { initialMachine } from "../shared/world.js";

const { nu: NU, nv: NV, cells: CELLS } = LOAD,
  frameOf = (machine) => new BucketFrame().set(bucketPose(machine));
// A load whose every column stands at a height in the mouth's axes.
function level(w) {
  const load = new Uint16Array(CELLS);
  for (let c = 0; c < CELLS; c++) {
    const i = c % NU;
    load[c] = Math.round(
      Math.max(0, Math.min(w, LOAD.ceilings[i]) - LOAD.floors[i]) / LOAD.quantum,
    );
  }
  return load;
}
function draw(load, from = load, alpha = 1) {
  const scene = new Scene(),
    meshes = createLoadMeshes(scene, new MeshBasicMaterial(), false);
  meshes.begin();
  meshes.draw(frameOf(initialMachine()), from, load, alpha);
  meshes.end();
  return { scene, meshes, mesh: scene.children[0] };
}
const node = (mesh, n) => {
  const p = mesh.geometry.attributes.position;
  return new Vector3(p.getX(n), p.getY(n), p.getZ(n));
};

test("the sheet is level where the load is, and hides behind the plates where it is not", () => {
  const { mesh } = draw(level(-20)),
    total = (NU + 1) * (NV + 1);
  for (let n = 0; n < total; n++) {
    const p = node(mesh, n),
      u = localU(p.x, p.z),
      w = localW(p.x, p.z),
      floor = LOAD.floorAt(u),
      ceiling = LOAD.ceilingAt(u);
    assert.ok(w <= ceiling + 1e-3, `under the top plate at ${u}`);
    assert.ok(w >= floor - 1.5 - 1e-3, `no deeper than the plate at ${u}`);
    // Clear of the sloping lip and of the back, where the top plate closes in.
    // A little relief is drawn on it, and at a corner of the plates a node can lie
    // within a millimetre of the level.
    if (u > 40 && ceiling > -18)
      assert.ok(Math.abs(w + 20) < 3.2, `${u}: ${w}`);
    if (u < 15) assert.ok(w < floor, `empty near the lip at ${u}`);
  }
});

test("the sheet faces out of the mouth, and its skirt faces away from the sand", () => {
  const { mesh } = draw(level(3)),
    index = mesh.geometry.index,
    normals = mesh.geometry.attributes.normal,
    a = new Vector3(),
    b = new Vector3(),
    surface = new Vector3();
  assert.equal(index.count / 3, LOAD_TRIANGLES);
  const out = new Vector3(-0.557, 0, 0.83);
  for (let t = 0; t < 2 * NU * NV; t++) {
    const p = node(mesh, index.getX(3 * t)),
      q = node(mesh, index.getX(3 * t + 1)),
      r = node(mesh, index.getX(3 * t + 2));
    surface.crossVectors(a.subVectors(q, p), b.subVectors(r, p));
    assert.ok(surface.dot(out) > 0, `triangle ${t} faces out of the mouth`);
  }
  for (let n = 0; n < normals.count; n++) {
    const normal = new Vector3(normals.getX(n), normals.getY(n), normals.getZ(n));
    assert.ok(Math.abs(normal.length() - 1) < 1e-3, "unit normals");
    assert.ok(normal.dot(out) > 0, `node ${n} looks out of the mouth`);
  }
  // A skirt triangle on the cheek at y < 0 faces that way.
  const skirt = 2 * NU * NV,
    p = node(mesh, index.getX(3 * skirt)),
    q = node(mesh, index.getX(3 * skirt + 1)),
    r = node(mesh, index.getX(3 * skirt + 2));
  surface.crossVectors(a.subVectors(q, p), b.subVectors(r, p));
  assert.ok(surface.y < 0);
});

test("the relief on a load moves along the bucket as the load changes, and not otherwise", () => {
  const nodes = (load) => {
    const { mesh } = draw(load),
      positions = mesh.geometry.attributes.position.array;
    return Array.from(positions);
  };
  const full = level(-10),
    less = level(-12);
  assert.deepEqual(nodes(full), nodes(full), "a load at rest stays as it is");
  // The level moves by the same amount everywhere; the relief does not.
  const a = nodes(full),
    b = nodes(less);
  const differences = new Set();
  for (let k = 2; k < a.length; k += 3)
    differences.add(Math.round((a[k] - b[k]) * 10));
  assert.ok(differences.size > 5, `${differences.size} different changes`);
});

test("a load is drawn between two frames, and from nothing", () => {
  const full = level(-10);
  const between = (from, to, alpha) => {
    const { mesh } = draw(to, from, alpha),
      p = node(mesh, Math.floor(NV / 2) * (NU + 1) + 12);
    return localW(p.x, p.z);
  };
  const w = between(full, full, 0.5),
    half = between(null, full, 0.5),
    none = between(full, null, 1),
    floor = LOAD.floorAt(12 * LOAD.du);
  assert.ok(Math.abs(w + 10) < 1.5);
  assert.ok(Math.abs(half - (floor + (w - floor) / 2)) < 2, `${half}`);
  assert.ok(none < floor, "an emptied column hides");
});

test("every bucket that has held sand draws what is in it, and one that has not draws nothing", () => {
  const scene = new Scene(),
    view = createLooseSandView(scene, new Texture(), false, () => -1000),
    load = level(0),
    machines = new Map([
      [1, { ...initialMachine(), strokes: [40, 0, 40] }],
      [2, { ...initialMachine(), strokes: [40, 0, 40], x: 9000, y: -7000 }],
      [3, { ...initialMachine(), strokes: [40, 0, 40], x: -3000 }],
    ]);
  const frame = (tick, carrying) => {
    const list = [...machines.keys()].map((id) => ({
      id,
      load: carrying.includes(id) ? load : null,
    }));
    return {
      tick,
      slots: new Uint16Array(),
      holders: new Uint16Array(),
      positions: new Float32Array(),
      machines: list,
      byId: new Map(list.map((machine) => [machine.id, machine])),
    };
  };
  const shown = () =>
    scene.children.filter(
      (child) => child.isMesh && child.visible && child.name !== "falling sand",
    );
  const both = frame(5, [1, 2]);
  view.update(both, both, 1, machines);
  assert.equal(shown().length, 2, "the machine with no load draws none");
  assert.equal(view.triangles, 2 * LOAD_TRIANGLES);
  // Each surface rides in its own bucket: a long way apart in the world.
  const [p, q] = shown().map((mesh) => mesh.matrix.elements.slice(12, 15));
  assert.ok(Math.hypot(p[0] - q[0], p[1] - q[1]) > 10000);
  // Machine 2 pours its last: it is still drawn on its way down, and it never comes
  // quite clean, while a machine that has yet to dig draws nothing.
  const one = frame(6, [1]);
  view.update(both, one, 0.5, machines);
  assert.equal(shown().length, 2);
  view.update(one, one, 1, machines);
  assert.equal(shown().length, 2);
  const depth = shown()
    .map((mesh) => Math.max(...mesh.geometry.attributes.loadDepth.array))
    .sort((p, q) => p - q)[0];
  assert.ok(depth < 3, `what is left is a dusting: ${depth} mm`);
  view.clear();
  view.update(one, one, 1, machines);
  assert.equal(shown().length, 1, "a new room starts with clean buckets");
  view.clear();
  assert.equal(shown().length, 0);
  assert.equal(view.triangles, 0);
});

test("falling sand follows its snapshot, fades transfers, and clears on reset", () => {
  const scene = new Scene(),
    view = createLooseSandView(scene, new Texture(), false);
  const machine = initialMachine(),
    pose = bucketPose(machine),
    poses = new Map([[1, machine]]);
  const point = toWorld(0, 0, -45, pose);
  const snapshot = (fields) => ({ machines: [], byId: new Map(), ...fields });
  const empty = snapshot({
    slots: new Uint16Array(),
    holders: new Uint16Array(),
    positions: new Float32Array(),
  });
  const full = snapshot({
    slots: Uint16Array.from([17]),
    holders: Uint16Array.from([1]),
    positions: Float32Array.from(point),
  });
  view.update(empty, full, 0, poses);
  assert.equal(view.count, 0, "new parcels start hidden");
  view.update(empty, full, 1, poses);
  assert.equal(view.count, 1);
  assert.equal(view.triangles, 0, "a falling parcel is not a load");
  const points = scene.children.find((child) => child.isPoints);
  const parcel = points.geometry.getAttribute("parcel");
  for (let d = 0; d < 3; d++)
    assert.ok(Math.abs(parcel.array[d] - point[d]) <= 0.051);
  view.update(full, empty, 0.5, poses);
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

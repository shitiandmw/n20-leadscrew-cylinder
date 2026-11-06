import test from "node:test";
import assert from "node:assert/strict";
import { clusterMesh } from "../client/decimate.js";

// A box with its own four vertices per face, as a CAD export has at hard edges,
// with each face cut into `n` × `n` quads.
function box(size, n) {
  const positions = [],
    normals = [],
    index = [];
  const face = (origin, u, v, normal) => {
    const first = positions.length / 3;
    for (let j = 0; j <= n; j++)
      for (let i = 0; i <= n; i++) {
        for (let d = 0; d < 3; d++)
          positions.push(origin[d] + (u[d] * i * size) / n + (v[d] * j * size) / n);
        normals.push(...normal);
      }
    for (let j = 0; j < n; j++)
      for (let i = 0; i < n; i++) {
        const a = first + j * (n + 1) + i,
          b = a + 1,
          c = a + n + 1,
          d = c + 1;
        index.push(a, b, d, a, d, c);
      }
  };
  face([0, 0, 0], [0, 1, 0], [1, 0, 0], [0, 0, -1]);
  face([0, 0, size], [1, 0, 0], [0, 1, 0], [0, 0, 1]);
  face([0, 0, 0], [1, 0, 0], [0, 0, 1], [0, -1, 0]);
  face([0, size, 0], [0, 0, 1], [1, 0, 0], [0, 1, 0]);
  face([0, 0, 0], [0, 0, 1], [0, 1, 0], [-1, 0, 0]);
  face([size, 0, 0], [0, 1, 0], [0, 0, 1], [1, 0, 0]);
  return {
    positions: Float32Array.from(positions),
    normals: Float32Array.from(normals),
    index: Uint32Array.from(index),
  };
}

test("without normals a cell becomes one vertex", () => {
  const { positions, index } = box(10, 10);
  const far = clusterMesh(positions, index, 2.5);
  assert.equal(far.normals, null);
  assert.ok(far.index.length < index.length / 2);
  // The vertices keep the part's outline to within a cell.
  for (let v = 0; v < far.positions.length; v++) {
    assert.ok(far.positions[v] >= 0 && far.positions[v] <= 10);
  }
  const seen = new Set();
  for (let v = 0; v < far.positions.length; v += 3)
    seen.add([far.positions[v], far.positions[v + 1], far.positions[v + 2]].join());
  assert.equal(seen.size, far.positions.length / 3);
});

test("with normals a hard edge stays hard and the surface stays closed", () => {
  const { positions, normals, index } = box(10, 10),
    far = clusterMesh(positions, index, 2.5, normals);
  assert.ok(far.index.length < index.length / 2, "far fewer triangles");
  assert.ok(far.positions.length / 3 < positions.length / 3 / 2);
  const places = new Map();
  for (let v = 0; v < far.positions.length / 3; v++) {
    const place = [0, 1, 2].map((d) => far.positions[3 * v + d]).join();
    if (!places.has(place)) places.set(place, []);
    places.get(place).push(v);
    // Unit length, and still along an axis: the box's faces are flat.
    const n = [0, 1, 2].map((d) => far.normals[3 * v + d]);
    assert.ok(Math.abs(Math.hypot(...n) - 1) < 1e-5);
  }
  // On an edge, two faces share a place and each keeps its own direction.
  assert.ok(
    [...places.values()].some((list) => list.length > 1),
    "vertices at one place, facing different ways",
  );
  // Closed: every edge, by where its ends are, is used equally in each direction.
  const key = (v) => [0, 1, 2].map((d) => far.positions[3 * v + d]).join();
  const edges = new Map();
  for (let t = 0; t < far.index.length; t += 3)
    for (let e = 0; e < 3; e++) {
      const a = key(far.index[t + e]),
        b = key(far.index[t + (e + 1) % 3]),
        name = a < b ? `${a}|${b}` : `${b}|${a}`,
        sign = a < b ? 1 : -1;
      edges.set(name, (edges.get(name) ?? 0) + sign);
    }
  assert.ok([...edges.values()].every((balance) => balance === 0));
});

test("a part smaller than a cell can vanish, but no triangle is left degenerate", () => {
  const { positions, normals, index } = box(1, 2),
    far = clusterMesh(positions, index, 8, normals);
  assert.equal(far.index.length, 0);
  const small = box(10, 4),
    big = clusterMesh(small.positions, small.index, 3);
  for (let t = 0; t < big.index.length; t += 3) {
    assert.notEqual(big.index[t], big.index[t + 1]);
    assert.notEqual(big.index[t + 1], big.index[t + 2]);
    assert.notEqual(big.index[t], big.index[t + 2]);
  }
});

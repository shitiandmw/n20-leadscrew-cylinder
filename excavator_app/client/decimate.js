// Vertex clustering: every vertex in a cubic cell becomes one vertex at their
// average, and triangles that collapse disappear. It is quick, keeps a part's
// outline, and needs nothing but the mesh.
//
// Given normals, vertices in a cell still meet at one point, so a closed surface
// stays closed, but those facing different ways stay separate vertices, each with
// its own averaged normal: a hard edge stays hard and a flat face stays evenly lit.
export function clusterMesh(positions, index, cell, normals = null) {
  const count = positions.length / 3,
    remap = new Int32Array(count),
    cells = new Map(),
    corners = new Map(),
    sums = [],
    placeOf = [],
    facing = [];
  for (let v = 0; v < count; v++) {
    const x = positions[3 * v],
      y = positions[3 * v + 1],
      z = positions[3 * v + 2],
      key =
        (Math.floor(x / cell) + 8192) * 67108864 +
        (Math.floor(y / cell) + 8192) * 16384 +
        (Math.floor(z / cell) + 8192);
    let place = cells.get(key);
    if (place === undefined) {
      place = sums.length / 4;
      cells.set(key, place);
      sums.push(0, 0, 0, 0);
    }
    sums[4 * place] += x;
    sums[4 * place + 1] += y;
    sums[4 * place + 2] += z;
    sums[4 * place + 3]++;
    // One of 27 directions: a right angle always parts, a gentle curve mostly not.
    const nx = normals ? normals[3 * v] : 0,
      ny = normals ? normals[3 * v + 1] : 0,
      nz = normals ? normals[3 * v + 2] : 0,
      corner =
        place * 27 +
        (Math.round(nx * 1.4) + 1) * 9 +
        (Math.round(ny * 1.4) + 1) * 3 +
        (Math.round(nz * 1.4) + 1);
    let id = corners.get(corner);
    if (id === undefined) {
      id = placeOf.length;
      corners.set(corner, id);
      placeOf.push(place);
      facing.push(0, 0, 0);
    }
    remap[v] = id;
    facing[3 * id] += nx;
    facing[3 * id + 1] += ny;
    facing[3 * id + 2] += nz;
  }
  const vertices = placeOf.length,
    out = new Float32Array(vertices * 3),
    outNormals = normals ? new Float32Array(vertices * 3) : null;
  for (let id = 0; id < vertices; id++) {
    const place = placeOf[id],
      length =
        Math.hypot(facing[3 * id], facing[3 * id + 1], facing[3 * id + 2]) || 1;
    for (let d = 0; d < 3; d++) {
      out[3 * id + d] = sums[4 * place + d] / sums[4 * place + 3];
      if (normals) outNormals[3 * id + d] = facing[3 * id + d] / length;
    }
  }
  const triangles = [];
  for (let t = 0; t < index.length; t += 3) {
    const a = remap[index[t]],
      b = remap[index[t + 1]],
      c = remap[index[t + 2]];
    if (
      placeOf[a] !== placeOf[b] &&
      placeOf[b] !== placeOf[c] &&
      placeOf[c] !== placeOf[a]
    )
      triangles.push(a, b, c);
  }
  return {
    positions: out,
    normals: outNormals,
    index: Uint32Array.from(triangles),
  };
}

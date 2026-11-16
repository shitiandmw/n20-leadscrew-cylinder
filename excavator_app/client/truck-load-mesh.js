import * as THREE from "three";
import { TRUCK, TRUCK_LOAD } from "../shared/truck.js";

// The sand in a truck's body, drawn from its columns as one sheet in the body's
// own frame: x along the floor from the inside of the rear wall, y across and z
// up from the floor. It is drawn as a bucket's load is (load-mesh.js), on a flat
// floor between four walls. A skirt round the edge closes the sheet down to the
// floor.
const { nu: NU, nv: NV, cells: CELLS, du: DU, dv: DV } = TRUCK_LOAD,
  ACROSS = NU + 1,
  NODES = ACROSS * (NV + 1),
  // Where the sand runs out, the sheet dips under the floor's top.
  SINK = 1.5,
  FADE = 1,
  // At the walls it reaches a little into them, leaving no gap.
  OVERLAP = 0.4,
  // Drawn relief (mm), as on a bucket's load: no volume, and it fades out where the
  // sand is thin.
  RELIEF = 2.2,
  RELIEF_DEPTH = 8,
  relief = (u, y) =>
    0.5 * Math.sin(0.21 * u + 1.7 * Math.sin(0.09 * y + 0.6)) +
    0.3 * Math.sin(0.13 * u - 0.19 * y + 2.1) +
    0.2 * Math.sin(0.43 * u + 0.37 * y + 4 + 1.3 * Math.sin(0.17 * u)),
  nodeX = (i) =>
    i === 0 ? -OVERLAP : i === NU ? TRUCK_LOAD.length + OVERLAP : i * DU,
  nodeY = (j) =>
    j === 0
      ? -TRUCK_LOAD.halfWidth - OVERLAP
      : j === NV
        ? TRUCK_LOAD.halfWidth + OVERLAP
        : j * DV - TRUCK_LOAD.halfWidth;

// The sand in column i of row j, or just past a wall, what the two columns nearest
// it lead on to: a node on a wall then stands where the sand's slope meets it.
function columnAt(cells, i, j) {
  if (j < 0) return 2 * columnAt(cells, i, 0) - columnAt(cells, i, 1);
  if (j >= NV) return 2 * columnAt(cells, i, NV - 1) - columnAt(cells, i, NV - 2);
  if (i < 0) return 2 * cells[j * NU] - cells[j * NU + 1];
  if (i >= NU) return 2 * cells[j * NU + NU - 1] - cells[j * NU + NU - 2];
  return cells[j * NU + i];
}

// The edge of the sheet, anticlockwise seen from above.
const EDGE = [];
for (let i = 0; i < NU; i++) EDGE.push(i);
for (let j = 0; j < NV; j++) EDGE.push(j * ACROSS + NU);
for (let i = NU; i > 0; i--) EDGE.push(NV * ACROSS + i);
for (let j = NV; j > 0; j--) EDGE.push(j * ACROSS);

const INDICES = [];
for (let j = 0; j < NV; j++)
  for (let i = 0; i < NU; i++) {
    const a = j * ACROSS + i,
      b = a + 1,
      c = a + ACROSS,
      d = c + 1;
    INDICES.push(a, b, d, a, d, c);
  }
EDGE.forEach((top, k) => {
  const next = (k + 1) % EDGE.length;
  INDICES.push(top, NODES + k, NODES + next, top, NODES + next, EDGE[next]);
});
export const TRUCK_LOAD_TRIANGLES = INDICES.length / 3;

// Everything a load can reach, in the body's frame: the body heaped well over its
// walls, and the drawn relief.
const BOUNDS = new THREE.Sphere(
  new THREE.Vector3(TRUCK_LOAD.length / 2, 0, TRUCK.sideWall / 2),
  Math.hypot(TRUCK_LOAD.length / 2, TRUCK_LOAD.halfWidth, TRUCK.sideWall) + 60,
);

export function createTruckLoadMeshes(scene, material, castShadow) {
  const meshes = [],
    cells = new Float32Array(CELLS),
    heights = new Float32Array(NODES),
    depths = new Float32Array(NODES),
    basis = [new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()];
  let used = 0;

  function createMesh() {
    const geometry = new THREE.BufferGeometry(),
      count = NODES + EDGE.length,
      position = new THREE.BufferAttribute(new Float32Array(count * 3), 3),
      normal = new THREE.BufferAttribute(new Float32Array(count * 3), 3),
      depth = new THREE.BufferAttribute(new Float32Array(count), 1);
    position.setUsage(THREE.DynamicDrawUsage);
    normal.setUsage(THREE.DynamicDrawUsage);
    depth.setUsage(THREE.DynamicDrawUsage);
    geometry.setAttribute("position", position);
    geometry.setAttribute("normal", normal);
    geometry.setAttribute("loadDepth", depth);
    geometry.setIndex(INDICES);
    geometry.boundingSphere = BOUNDS;
    const mesh = new THREE.Mesh(geometry, material);
    mesh.castShadow = castShadow;
    mesh.receiveShadow = true;
    mesh.matrixAutoUpdate = false;
    scene.add(mesh);
    meshes.push(mesh);
    return mesh;
  }

  // One truck's load between two frames, in its body's frame (a pose with an
  // origin and three axes). Either frame may have none.
  function draw(frame, from, to, alpha) {
    const mesh = meshes[used] ?? createMesh();
    used++;
    mesh.visible = true;
    basis[0].fromArray(frame.ex);
    basis[1].fromArray(frame.ey);
    basis[2].fromArray(frame.ez);
    mesh.matrix.makeBasis(...basis).setPosition(frame.x, frame.y, frame.z);
    mesh.matrixWorldNeedsUpdate = true;
    // A parked load is drawn once.
    if (from === to && mesh.userData.from === from && mesh.userData.to === to) return;
    mesh.userData.from = from;
    mesh.userData.to = to;
    for (let c = 0; c < CELLS; c++)
      cells[c] =
        ((from ? from[c] : 0) * (1 - alpha) + (to ? to[c] : 0) * alpha) *
        TRUCK_LOAD.quantum;
    for (let j = 0; j <= NV; j++) {
      const y = nodeY(j);
      for (let i = 0; i <= NU; i++) {
        const thickness = Math.max(
            0,
            (columnAt(cells, i - 1, j - 1) +
              columnAt(cells, i, j - 1) +
              columnAt(cells, i - 1, j) +
              columnAt(cells, i, j)) /
              4,
          ),
          f = Math.min(1, thickness / FADE);
        depths[j * ACROSS + i] = thickness;
        heights[j * ACROSS + i] =
          thickness -
          SINK * (1 - f * f * (3 - 2 * f)) +
          RELIEF * Math.min(1, thickness / RELIEF_DEPTH) * relief(i * DU, y);
      }
    }
    const positions = mesh.geometry.attributes.position,
      normals = mesh.geometry.attributes.normal,
      depth = mesh.geometry.attributes.loadDepth;
    depth.array.set(depths);
    for (let j = 0; j <= NV; j++) {
      const y = nodeY(j),
        lower = Math.max(0, j - 1),
        upper = Math.min(NV, j + 1);
      for (let i = 0; i <= NU; i++) {
        const n = j * ACROSS + i,
          back = Math.max(0, i - 1),
          ahead = Math.min(NU, i + 1),
          slopeU =
            (heights[j * ACROSS + ahead] - heights[j * ACROSS + back]) /
            ((ahead - back) * DU),
          slopeY =
            (heights[upper * ACROSS + i] - heights[lower * ACROSS + i]) /
            ((upper - lower) * DV),
          scale = 1 / Math.hypot(slopeU, slopeY, 1);
        positions.setXYZ(n, nodeX(i), y, heights[n]);
        normals.setXYZ(n, -slopeU * scale, -slopeY * scale, scale);
      }
    }
    EDGE.forEach((top, k) => {
      const i = top % ACROSS,
        j = (top - i) / ACROSS;
      depth.array[NODES + k] = depths[top];
      positions.setXYZ(NODES + k, nodeX(i), nodeY(j), -SINK);
      normals.setXYZ(
        NODES + k,
        normals.getX(top),
        normals.getY(top),
        normals.getZ(top),
      );
    });
    positions.needsUpdate = true;
    normals.needsUpdate = true;
    depth.needsUpdate = true;
  }

  return {
    begin() {
      used = 0;
    },
    draw,
    // Whatever was not drawn this frame has no load to show.
    end() {
      for (let n = used; n < meshes.length; n++) meshes[n].visible = false;
    },
    get triangles() {
      return used * TRUCK_LOAD_TRIANGLES;
    },
  };
}

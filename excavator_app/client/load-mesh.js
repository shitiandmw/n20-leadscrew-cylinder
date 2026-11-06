import * as THREE from "three";
import { LOAD, mouthToLocal } from "../shared/bucket-load.js";

// The sand in a bucket, drawn from its columns as one sheet in the bucket's own
// frame, so a carried load stays still on the bucket. Nodes sit at the corners of
// the columns. A skirt round the edge closes the sheet down to the plates.
const { nu: NU, nv: NV, cells: CELLS, du: DU, dv: DV } = LOAD,
  ACROSS = NU + 1,
  NODES = ACROSS * (NV + 1),
  // Where the sand runs out, the sheet dips behind the plates' inner faces.
  SINK = 1.5,
  FADE = 1,
  // At the cheeks it reaches a little into the plates, leaving no gap.
  OVERLAP = 0.4,
  // Sand does not lie flat. This relief (mm) is drawn only; it has no volume, and
  // fades out where the sand is thin. It travels along the bucket as sand comes
  // and goes, at about the speed sand would through this cross-section (mm²).
  RELIEF = 2.2,
  RELIEF_DEPTH = 8,
  FLOW_SECTION = 1500,
  relief = (u, y) =>
    0.5 * Math.sin(0.21 * u + 1.7 * Math.sin(0.09 * y + 0.6)) +
    0.3 * Math.sin(0.13 * u - 0.19 * y + 2.1) +
    0.2 * Math.sin(0.43 * u + 0.37 * y + 4 + 1.3 * Math.sin(0.17 * u)),
  nodeY = (j) =>
    j === 0
      ? -LOAD.halfWidth - OVERLAP
      : j === NV
        ? LOAD.halfWidth + OVERLAP
        : j * DV - LOAD.halfWidth,
  NODE_FLOOR = Float64Array.from({ length: ACROSS }, (_, i) =>
    LOAD.floorAt(i * DU),
  ),
  NODE_CEILING = Float64Array.from({ length: ACROSS }, (_, i) =>
    LOAD.ceilingAt(i * DU),
  );

// A bucket that has held sand never comes quite clean. This is what stays, in mm:
// sand caught at the back and a few patches by the cheeks. Drawn only, like the
// relief, and carrying no sand. The material breaks anything this thin into patches.
const smooth = (low, high, value) => {
    const t = Math.max(0, Math.min(1, (value - low) / (high - low)));
    return t * t * (3 - 2 * t);
  },
  DUSTING = Float32Array.from({ length: NODES }, (_, n) => {
    const i = n % ACROSS,
      y = nodeY((n - i) / ACROSS),
      u = i * DU;
    return Math.max(
      0,
      0.15 +
        1.2 * smooth(LOAD.length * 0.55, LOAD.length, u) +
        0.35 * smooth(LOAD.halfWidth - 12, LOAD.halfWidth, Math.abs(y)) +
        0.45 * relief(2.3 * u + 11, 3.1 * y + 5),
    );
  });

// The edge of the sheet, anticlockwise seen from outside the mouth.
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
export const LOAD_TRIANGLES = INDICES.length / 3;

// Everything a load can reach, in the bucket's frame.
const BOUNDS = new THREE.Sphere(new THREE.Vector3(-20, 0, -36), 90);

export function createLoadMeshes(scene, material, castShadow) {
  const meshes = [],
    cells = new Float32Array(CELLS),
    heights = new Float32Array(NODES),
    depths = new Float32Array(NODES),
    point = [0, 0, 0],
    origin = [0, 0, 0],
    across = [0, 0, 0],
    outward = [0, 0, 0],
    basis = [new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()];
  mouthToLocal(0, 0, 0, origin);
  mouthToLocal(1, 0, 0, across);
  mouthToLocal(0, 0, 1, outward);
  const alongX = across[0] - origin[0],
    alongZ = across[2] - origin[2],
    outX = outward[0] - origin[0],
    outZ = outward[2] - origin[2];
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

  // There from the start, so its shader is compiled with the others at load.
  createMesh().visible = false;

  // One machine's load between two frames; either of them may have none, and with
  // neither there is still the dusting left in the bucket.
  function draw(frame, from, to, alpha) {
    const mesh = meshes[used] ?? createMesh();
    used++;
    mesh.visible = true;
    basis[0].fromArray(frame.ex);
    basis[1].fromArray(frame.ey);
    basis[2].fromArray(frame.ez);
    mesh.matrix.makeBasis(...basis).setPosition(frame.x, frame.y, frame.z);
    mesh.matrixWorldNeedsUpdate = true;
    const onlyDusting = !from && !to;
    if (onlyDusting && mesh.userData.onlyDusting) return;
    mesh.userData.onlyDusting = onlyDusting;
    for (let c = 0; c < CELLS; c++)
      cells[c] =
        ((from ? from[c] : 0) * (1 - alpha) + (to ? to[c] : 0) * alpha) *
        LOAD.quantum;
    let volume = 0;
    for (let c = 0; c < CELLS; c++) volume += cells[c];
    const flow = (volume * LOAD.area) / FLOW_SECTION;
    for (let j = 0; j <= NV; j++) {
      const below = Math.max(0, j - 1) * NU,
        above = Math.min(NV - 1, j) * NU,
        y = nodeY(j);
      for (let i = 0; i <= NU; i++) {
        const back = Math.max(0, i - 1),
          ahead = Math.min(NU - 1, i),
          thickness = onlyDusting
            ? DUSTING[j * ACROSS + i]
            : (cells[below + back] +
                cells[below + ahead] +
                cells[above + back] +
                cells[above + ahead]) /
              4,
          f = Math.min(1, thickness / FADE);
        depths[j * ACROSS + i] = thickness;
        heights[j * ACROSS + i] = Math.min(
          NODE_CEILING[i],
          NODE_FLOOR[i] +
            thickness -
            SINK * (1 - f * f * (3 - 2 * f)) +
            RELIEF *
              Math.min(1, thickness / RELIEF_DEPTH) *
              relief(i * DU - flow, y),
        );
      }
    }
    const positions = mesh.geometry.attributes.position,
      normals = mesh.geometry.attributes.normal,
      depth = mesh.geometry.attributes.loadDepth;
    const place = (n, u, y, w, nx, ny, nz) => {
      mouthToLocal(u, y, w, point);
      positions.setXYZ(n, point[0], point[1], point[2]);
      normals.setXYZ(n, nx, ny, nz);
    };
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
          scale = 1 / Math.hypot(slopeU, slopeY, 1),
          nx = (-slopeU * alongX + outX) * scale,
          ny = -slopeY * scale,
          nz = (-slopeU * alongZ + outZ) * scale;
        place(n, i * DU, y, heights[n], nx, ny, nz);
      }
    }
    EDGE.forEach((top, k) => {
      const i = top % ACROSS,
        j = (top - i) / ACROSS;
      depth.array[NODES + k] = depths[top];
      place(
        NODES + k,
        i * DU,
        nodeY(j),
        NODE_FLOOR[i] - SINK,
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
      return used * LOAD_TRIANGLES;
    },
  };
}

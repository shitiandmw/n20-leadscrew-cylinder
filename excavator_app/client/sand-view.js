import * as THREE from "three";
import { SAND, WORLD, cellX, cellY } from "../shared/world.js";
import { groundHeight } from "../shared/landscape.js";

import { sandTexture } from "./sand-material.js";

const CHUNK = SAND.page,
  SIDE = CHUNK + 1,
  VERTICES = SIDE * SIDE,
  PAGE_CELLS = CHUNK * CHUNK;
const pageKey = (col, row) => row * 64 + col;
const offset = (i, j) => ((j & 63) << 6) | (i & 63);

// The sand is drawn as chunks of the height field, created where sand exists.
// A chunk's far edge repeats its neighbour's first row, so the sheet has no
// seams. Chunks far from the camera draw every second or fourth vertex.
export function createSandView(scene, renderer) {
  const dry = new THREE.Color("#e4d9c3").convertSRGBToLinear(),
    grain = sandTexture(renderer),
    time = { value: 0 };
  const material = new THREE.MeshStandardMaterial({
    color: 0xffffff,
    vertexColors: true,
    map: grain,
    bumpMap: grain,
    bumpScale: 1.4,
    roughness: 0.97,
    metalness: 0,
    polygonOffset: true,
    polygonOffsetFactor: -1,
    polygonOffsetUnits: -2,
  });
  // Bare ground shows through where there is no sand; freshly dug or dumped
  // sand is darker (moist) and dries over about a minute.
  material.onBeforeCompile = (shader) => {
    shader.uniforms.sandTime = time;
    shader.vertexShader = shader.vertexShader
      .replace(
        "#include <common>",
        "#include <common>\nattribute vec2 sandInfo;\nuniform float sandTime;\nvarying vec2 vSand;\nvarying vec2 vSandXY;",
      )
      .replace(
        "#include <begin_vertex>",
        "#include <begin_vertex>\nvSand = vec2(sandInfo.x, exp(-max(0.0, sandTime - sandInfo.y) / 55.0));\nvSandXY = position.xy;",
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        "#include <common>\nvarying vec2 vSand;\nvarying vec2 vSandXY;\nfloat sandHash(vec2 p) { return fract(sin(dot(mod(floor(p), 1024.0), vec2(12.9898, 78.233))) * 43758.5453); }",
      )
      .replace(
        "#include <map_fragment>",
        // Thin sand breaks up into scattered grains instead of a hard edge.
        "#include <map_fragment>\nif (vSand.x < 0.15 + 2.2 * sandHash(vSandXY * 1.6)) discard;\ndiffuseColor.rgb *= mix(1.0, 0.78, vSand.y) * mix(0.88, 1.0, smoothstep(0.3, 4.0, vSand.x));",
      );
  };
  const indexes = new Map(
    [1, 2, 4].map((stride) => {
      const n = CHUNK / stride,
        index = new Uint16Array(n * n * 6);
      let o = 0;
      for (let j = 0; j < n; j++)
        for (let i = 0; i < n; i++) {
          const a = j * stride * SIDE + i * stride,
            b = a + stride,
            c = a + stride * SIDE,
            d = c + stride;
          index.set([a, b, d, a, d, c], o);
          o += 6;
        }
      return [stride, new THREE.BufferAttribute(index, 1)];
    }),
  );
  const thickness = new Map(),
    disturbed = new Map(),
    baseHeights = new Map(),
    chunks = new Map();
  let ready = false,
    changedSinceDraw = false;
  const heightAt = (i, j) => {
    const page = thickness.get(pageKey(i >> 6, j >> 6));
    return page ? page[offset(i, j)] : 0;
  };
  const baseAt = (i, j) => {
    const key = pageKey(i >> 6, j >> 6);
    let page = baseHeights.get(key);
    if (!page) {
      page = new Float32Array(PAGE_CELLS);
      const i0 = (i >> 6) * CHUNK,
        j0 = (j >> 6) * CHUNK;
      for (let b = 0; b < CHUNK; b++)
        for (let a = 0; a < CHUNK; a++)
          page[(b << 6) | a] = groundHeight(cellX(i0 + a), cellY(j0 + b));
      baseHeights.set(key, page);
    }
    return page[offset(i, j)];
  };
  const NX = SAND.nx,
    NY = SAND.ny;
  const surface = (i, j) => {
    const ci = Math.max(0, Math.min(NX - 1, i)),
      cj = Math.max(0, Math.min(NY - 1, j));
    return baseAt(ci, cj) + heightAt(ci, cj);
  };

  function ensureChunk(col, row) {
    const key = pageKey(col, row);
    let chunk = chunks.get(key);
    if (chunk) return chunk;
    const i0 = col * CHUNK,
      j0 = row * CHUNK,
      position = new Float32Array(VERTICES * 3),
      normal = new Float32Array(VERTICES * 3),
      color = new Float32Array(VERTICES * 3),
      uv = new Float32Array(VERTICES * 2),
      info = new Float32Array(VERTICES * 2);
    for (let b = 0; b < SIDE; b++)
      for (let a = 0; a < SIDE; a++) {
        const v = b * SIDE + a,
          x = cellX(i0 + a),
          y = cellY(j0 + b);
        position[3 * v] = x;
        position[3 * v + 1] = y;
        normal[3 * v + 2] = 1;
        uv[2 * v] = x / 70;
        uv[2 * v + 1] = y / 70;
        info[2 * v + 1] = -1e6;
        // Gentle low-frequency patchiness of colour and moisture.
        const patch =
          0.04 * Math.sin(x * 0.0043 + Math.sin(y * 0.007) * 2) +
          0.03 * Math.sin(y * 0.0057 - x * 0.002);
        color[3 * v] = dry.r * (1 + patch);
        color[3 * v + 1] = dry.g * (1 + patch);
        color[3 * v + 2] = dry.b * (1 + patch * 1.2);
      }
    const geometry = new THREE.BufferGeometry(),
      positions = new THREE.BufferAttribute(position, 3),
      normals = new THREE.BufferAttribute(normal, 3),
      infos = new THREE.BufferAttribute(info, 2);
    for (const a of [positions, normals, infos])
      a.setUsage(THREE.DynamicDrawUsage);
    geometry.setAttribute("position", positions);
    geometry.setAttribute("normal", normals);
    geometry.setAttribute("color", new THREE.BufferAttribute(color, 3));
    geometry.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
    geometry.setAttribute("sandInfo", infos);
    geometry.setIndex(indexes.get(1));
    geometry.boundingSphere = new THREE.Sphere();
    const mesh = new THREE.Mesh(geometry, material);
    mesh.receiveShadow = true;
    mesh.castShadow = true;
    scene.add(mesh);
    chunk = {
      col,
      row,
      i0,
      j0,
      mesh,
      positions,
      normals,
      infos,
      stride: 1,
      zMin: Infinity,
      zMax: -Infinity,
      cx: cellX(i0 + CHUNK / 2),
      cy: cellY(j0 + CHUNK / 2),
    };
    chunks.set(key, chunk);
    refreshChunk(chunk, 0, CHUNK, 0, CHUNK);
    return chunk;
  }

  // Rewrite the vertices a..a1, b..b1 (inclusive) of one chunk.
  function refreshChunk(chunk, a0, a1, b0, b1) {
    const { i0, j0, positions, normals, infos } = chunk,
      position = positions.array,
      normal = normals.array,
      info = infos.array,
      spacing = 2 * SAND.cell;
    for (let b = b0; b <= b1; b++)
      for (let a = a0; a <= a1; a++) {
        const v = b * SIDE + a,
          i = i0 + a,
          j = j0 + b,
          h = i < NX && j < NY ? heightAt(i, j) : 0,
          z = surface(i, j),
          dx = (surface(i + 1, j) - surface(i - 1, j)) / spacing,
          dy = (surface(i, j + 1) - surface(i, j - 1)) / spacing,
          n = 1 / Math.sqrt(1 + dx * dx + dy * dy),
          page = disturbed.get(pageKey(i >> 6, j >> 6));
        position[3 * v + 2] = z;
        normal[3 * v] = -dx * n;
        normal[3 * v + 1] = -dy * n;
        normal[3 * v + 2] = n;
        info[2 * v] = h;
        info[2 * v + 1] = page ? page[offset(i, j)] : -1e6;
        if (z < chunk.zMin) chunk.zMin = z;
        if (z > chunk.zMax) chunk.zMax = z;
      }
    const start = b0 * SIDE,
      count = (b1 - b0 + 1) * SIDE;
    for (const [attribute, size] of [
      [positions, 3],
      [normals, 3],
      [infos, 2],
    ]) {
      attribute.addUpdateRange(start * size, count * size);
      attribute.needsUpdate = true;
    }
    const half = (CHUNK * SAND.cell) / 2,
      zHalf = (chunk.zMax - chunk.zMin) / 2;
    chunk.mesh.geometry.boundingSphere.center.set(
      chunk.cx,
      chunk.cy,
      (chunk.zMin + chunk.zMax) / 2,
    );
    chunk.mesh.geometry.boundingSphere.radius =
      Math.hypot(half, half, zHalf) + SAND.cell;
  }

  // Apply sand-bed tiles; `fresh` marks changed cells as newly disturbed.
  function applyTiles(tiles, fresh) {
    for (const { index, heights } of tiles) {
      const ti = index & 255,
        tj = index >>> 8,
        i0 = ti * SAND.tile,
        j0 = tj * SAND.tile;
      let iLow = NX,
        iHigh = -1,
        jLow = NY,
        jHigh = -1,
        o = 0;
      for (let j = j0; j < j0 + SAND.tile; j++)
        for (let i = i0; i < i0 + SAND.tile; i++, o++) {
          const h = heights[o] * SAND.heightQuantum,
            key = pageKey(i >> 6, j >> 6);
          let page = thickness.get(key);
          if (!page) {
            if (!h) continue;
            thickness.set(key, (page = new Float32Array(PAGE_CELLS)));
          }
          const c = offset(i, j),
            old = page[c];
          if (h === old) continue;
          if (fresh && Math.abs(h - old) > 0.08) {
            let moist = disturbed.get(key);
            if (!moist) {
              moist = new Float32Array(PAGE_CELLS).fill(-1e6);
              disturbed.set(key, moist);
            }
            moist[c] = time.value;
          }
          page[c] = h;
          if (i < iLow) iLow = i;
          if (i > iHigh) iHigh = i;
          if (j < jLow) jLow = j;
          if (j > jHigh) jHigh = j;
        }
      ready = true;
      if (iHigh < 0) continue;
      changedSinceDraw = true;
      // A changed cell moves its vertex and the normals around it, in every
      // chunk that shares them.
      const left = iLow - 1,
        right = iHigh + 1,
        down = jLow - 1,
        up = jHigh + 1;
      for (let row = (down - 1) >> 6; row <= up >> 6; row++)
        for (let col = (left - 1) >> 6; col <= right >> 6; col++) {
          if (col < 0 || row < 0 || col > 63 || row > 63) continue;
          const chunk =
            chunks.get(pageKey(col, row)) ??
            (thickness.has(pageKey(col, row)) ? ensureChunk(col, row) : null);
          if (!chunk) continue;
          const a0 = Math.max(0, left - chunk.i0),
            a1 = Math.min(CHUNK, right - chunk.i0),
            b0 = Math.max(0, down - chunk.j0),
            b1 = Math.min(CHUNK, up - chunk.j0);
          if (a0 <= a1 && b0 <= b1) refreshChunk(chunk, a0, a1, b0, b1);
        }
    }
    if (changedSinceDraw) {
      changedSinceDraw = false;
      return true;
    }
    return false;
  }

  // Coarser triangles for distant chunks. Returns true if anything changed.
  function updateDetail(camera) {
    let changed = false;
    for (const chunk of chunks.values()) {
      const dx = chunk.cx - camera.position.x,
        dy = chunk.cy - camera.position.y,
        dz = (chunk.zMin + chunk.zMax) / 2 - camera.position.z,
        d = Math.hypot(dx, dy, dz),
        stride = d < 2400 ? 1 : d < 6000 ? 2 : 4;
      if (stride !== chunk.stride) {
        chunk.stride = stride;
        chunk.mesh.geometry.setIndex(indexes.get(stride));
        changed = true;
      }
    }
    return changed;
  }

  // Forget everything, for a new room: it only ever sends the sand it has.
  function clear() {
    const empty = new Uint16Array(SAND.tile * SAND.tile),
      tiles = [];
    for (const key of thickness.keys()) {
      const row = key >> 6,
        col = key & 63;
      for (let tj = 0; tj < 4; tj++)
        for (let ti = 0; ti < 4; ti++)
          tiles.push({
            index: (row * 4 + tj) * 256 + col * 4 + ti,
            heights: empty,
          });
    }
    return applyTiles(tiles, false);
  }

  return {
    texture: grain,
    // Sample the same two triangles as the nearby rendered bed. Loose-grain
    // breakup tapers before this surface, including freshly deposited sand.
    surfaceHeight(x, y) {
      const gx = (x - WORLD.minX) / SAND.cell - 0.5,
        gy = (y - WORLD.minY) / SAND.cell - 0.5,
        i = Math.floor(gx),
        j = Math.floor(gy),
        u = gx - i,
        v = gy - j,
        a = surface(i, j),
        b = surface(i + 1, j),
        c = surface(i, j + 1),
        d = surface(i + 1, j + 1);
      return u >= v
        ? a + u * (b - a) + v * (d - b)
        : a + v * (c - a) + u * (d - c);
    },
    applyTiles,
    clear,
    updateDetail,
    setTime(seconds) {
      time.value = seconds;
    },
    get ready() {
      return ready;
    },
    get chunkCount() {
      return chunks.size;
    },
  };
}

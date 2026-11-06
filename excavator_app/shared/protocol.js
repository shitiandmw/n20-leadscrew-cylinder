import { SAND } from "./world.js";
import { LOAD } from "./bucket-load.js";

// Binary simulator frame, little-endian. One frame per physics tick carries
// every machine's pose and the sand from the same instant, so the browser can
// draw each bucket and its load in sync.
//   u8 magic 'S', u8 version, u16 machine count, u32 tick,
//   u16 grain group count, u16 tile count, u32 grain count,
//   machines: u16 id, u16 1 if a load follows for it, f32 x12 strokes[3], slew, x,
//             y, z, heading, pitch, roll, tracks[2],
//   groups: i32 x3 origin in whole mm, u16 grain count, u16 id of the machine
//           whose bucket the grains are near (0 for none),
//   grains: i16 x4 [slot, x, y, z] of each falling parcel, in group order, with the
//           position relative to the group's origin in SAND.positionQuantum units,
//   loads: LOAD.cells u16 column thickness in LOAD.quantum, for each machine with
//          a load, in machine order,
//   tiles: u16 tile index + TILE*TILE u16 thickness in SAND.heightQuantum.
export const FRAME_MAGIC = 0x53;
export const FRAME_VERSION = 5;
export const HEADER_BYTES = 16;
export const MACHINE_BYTES = 52;
export const GROUP_BYTES = 16;
export const TILE_CELLS = SAND.tile * SAND.tile;
export const TILE_COUNT = SAND.tilesX * SAND.tilesY;

export function tileCells(tile) {
  const ti = tile % SAND.tilesX,
    tj = (tile - ti) / SAND.tilesX;
  return { i0: ti * SAND.tile, j0: tj * SAND.tile };
}

// machines: poses, each with its id and its load (a Uint16Array, or null); grains: Int16Array of 4 values per grain;
// groups: Int32Array of 5 values per group [x, y, z, count, machine id]; tileData:
// Map of tile index to its Uint16Array of cells (a missing tile is empty); tiles:
// the indices to include.
export function encodeFrame({ tick, machines, grains, groups, tileData, tiles }) {
  const count = grains.length / 4,
    groupCount = groups.length / 5,
    grainStart =
      HEADER_BYTES + machines.length * MACHINE_BYTES + groupCount * GROUP_BYTES,
    loadStart = grainStart + count * 8,
    loaded = machines.filter((machine) => machine.load),
    tileStart = loadStart + loaded.length * LOAD.cells * 2,
    bytes = tileStart + tiles.length * (TILE_CELLS + 1) * 2,
    buffer = new ArrayBuffer(bytes),
    view = new DataView(buffer);
  view.setUint8(0, FRAME_MAGIC);
  view.setUint8(1, FRAME_VERSION);
  view.setUint16(2, machines.length, true);
  view.setUint32(4, tick >>> 0, true);
  view.setUint16(8, groupCount, true);
  view.setUint16(10, tiles.length, true);
  view.setUint32(12, count, true);
  let at = HEADER_BYTES;
  for (const machine of machines) {
    view.setUint16(at, machine.id, true);
    view.setUint16(at + 2, machine.load ? 1 : 0, true);
    const pose = [
      ...machine.strokes,
      machine.slew,
      machine.x,
      machine.y,
      machine.z ?? 0,
      machine.heading,
      machine.pitch ?? 0,
      machine.roll ?? 0,
      ...machine.tracks,
    ];
    pose.forEach((value, i) => view.setFloat32(at + 4 + 4 * i, value, true));
    at += MACHINE_BYTES;
  }
  for (let g = 0; g < groups.length; g += 5) {
    for (let d = 0; d < 3; d++) view.setInt32(at + 4 * d, groups[g + d], true);
    view.setUint16(at + 12, groups[g + 3], true);
    view.setUint16(at + 14, groups[g + 4], true);
    at += GROUP_BYTES;
  }
  new Int16Array(buffer, grainStart, count * 4).set(grains);
  const loads = new Uint16Array(buffer, loadStart, loaded.length * LOAD.cells);
  loaded.forEach(({ load }, n) => loads.set(load, n * LOAD.cells));
  const out = new Uint16Array(
    buffer,
    tileStart,
    tiles.length * (TILE_CELLS + 1),
  );
  let o = 0;
  for (const tile of tiles) {
    out[o] = tile;
    const heights = tileData.get(tile);
    if (heights) out.set(heights, o + 1);
    o += TILE_CELLS + 1;
  }
  return new Uint8Array(buffer);
}

export function decodeFrame(data) {
  const buffer =
    data instanceof ArrayBuffer
      ? data
      : data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength);
  const view = new DataView(buffer);
  if (
    buffer.byteLength < HEADER_BYTES ||
    view.getUint8(0) !== FRAME_MAGIC ||
    view.getUint8(1) !== FRAME_VERSION
  )
    throw new Error("Unsupported sand frame");
  const machineCount = view.getUint16(2, true),
    groupCount = view.getUint16(8, true),
    tileCount = view.getUint16(10, true),
    count = view.getUint32(12, true),
    machines = [];
  let at = HEADER_BYTES;
  for (let n = 0; n < machineCount; n++) {
    const f = (i) => view.getFloat32(at + 4 + 4 * i, true);
    machines.push({
      id: view.getUint16(at, true),
      load: view.getUint16(at + 2, true),
      strokes: [f(0), f(1), f(2)],
      slew: f(3),
      x: f(4),
      y: f(5),
      z: f(6),
      heading: f(7),
      pitch: f(8),
      roll: f(9),
      tracks: [f(10), f(11)],
    });
    at += MACHINE_BYTES;
  }
  // Grains are handed on with absolute positions: the groups only exist so the
  // positions fit the wire.
  const grainStart = at + groupCount * GROUP_BYTES,
    grains = new Int16Array(buffer, grainStart, count * 4),
    slots = new Uint16Array(count),
    holders = new Uint16Array(count),
    positions = new Float32Array(count * 3),
    q = SAND.positionQuantum;
  let n = 0;
  for (let g = 0; g < groupCount; g++, at += GROUP_BYTES) {
    const x = view.getInt32(at, true),
      y = view.getInt32(at + 4, true),
      z = view.getInt32(at + 8, true),
      members = view.getUint16(at + 12, true),
      holder = view.getUint16(at + 14, true);
    for (const end = n + members; n < end; n++) {
      const o = n * 4,
        k = n * 3;
      slots[n] = grains[o];
      holders[n] = holder;
      positions[k] = x + grains[o + 1] * q;
      positions[k + 1] = y + grains[o + 2] * q;
      positions[k + 2] = z + grains[o + 3] * q;
    }
  }
  const loadStart = grainStart + count * 8;
  let loaded = 0;
  for (const machine of machines)
    machine.load = machine.load
      ? new Uint16Array(buffer, loadStart + 2 * LOAD.cells * loaded++, LOAD.cells)
      : null;
  const tiles = [],
    data16 = new Uint16Array(
      buffer,
      loadStart + 2 * LOAD.cells * loaded,
      tileCount * (TILE_CELLS + 1),
    );
  for (let t = 0; t < tileCount; t++) {
    const o = t * (TILE_CELLS + 1);
    tiles.push({
      index: data16[o],
      heights: data16.subarray(o + 1, o + 1 + TILE_CELLS),
    });
  }
  return { tick: view.getUint32(4, true), machines, slots, holders, positions, tiles };
}

// Keep decoded tiles in a Map of tile index to thickness.
export function applyTiles(store, tiles) {
  for (const { index, heights } of tiles) store.set(index, heights.slice());
}

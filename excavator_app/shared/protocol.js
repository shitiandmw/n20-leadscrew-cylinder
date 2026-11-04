import { SAND } from "./world.js";

// Binary simulator frame, little-endian. One frame per physics tick carries
// the machine pose and the sand from the same instant, so the browser can
// draw the bucket and its load in sync.
//   u8 magic 'S', u8 version, u16 reserved, u32 tick,
//   f32 x10 machine: strokes[3], slew, x, y, z, heading, tracks[2],
//   u16 grain count, u16 tile count,
//   grains: i16 x4 [slot, x, y, z] in SAND.positionQuantum units,
//   tiles: u16 tile index + TILE*TILE u16 thickness in SAND.heightQuantum.
export const FRAME_MAGIC = 0x53;
export const FRAME_VERSION = 2;
export const HEADER_BYTES = 52;
export const TILE_CELLS = SAND.tile * SAND.tile;
export const TILE_COUNT = SAND.tilesX * SAND.tilesY;

export function tileCells(tile) {
  const ti = tile % SAND.tilesX,
    tj = (tile - ti) / SAND.tilesX;
  return { i0: ti * SAND.tile, j0: tj * SAND.tile };
}

// grains: Int16Array of 4 values per grain; terrain: Uint16Array of all
// cells; tiles: indices of the tiles to include.
export function encodeFrame({ tick, machine, grains, terrain, tiles }) {
  const count = grains.length / 4,
    bytes = HEADER_BYTES + count * 8 + tiles.length * (TILE_CELLS + 1) * 2,
    buffer = new ArrayBuffer(bytes),
    view = new DataView(buffer);
  view.setUint8(0, FRAME_MAGIC);
  view.setUint8(1, FRAME_VERSION);
  view.setUint32(4, tick >>> 0, true);
  const pose = [
    ...machine.strokes,
    machine.slew,
    machine.x,
    machine.y,
    machine.z ?? 0,
    machine.heading,
    ...machine.tracks,
  ];
  pose.forEach((value, i) => view.setFloat32(8 + 4 * i, value, true));
  view.setUint16(48, count, true);
  view.setUint16(50, tiles.length, true);
  new Int16Array(buffer, HEADER_BYTES, count * 4).set(grains);
  const out = new Uint16Array(
    buffer,
    HEADER_BYTES + count * 8,
    tiles.length * (TILE_CELLS + 1),
  );
  let o = 0;
  for (const tile of tiles) {
    out[o++] = tile;
    const { i0, j0 } = tileCells(tile);
    for (let j = j0; j < j0 + SAND.tile; j++)
      for (let i = i0; i < i0 + SAND.tile; i++, o++)
        if (i < SAND.nx && j < SAND.ny) out[o] = terrain[j * SAND.nx + i];
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
  const f = (i) => view.getFloat32(8 + 4 * i, true),
    count = view.getUint16(48, true),
    tileCount = view.getUint16(50, true);
  const tiles = [],
    data16 = new Uint16Array(
      buffer,
      HEADER_BYTES + count * 8,
      tileCount * (TILE_CELLS + 1),
    );
  for (let t = 0; t < tileCount; t++) {
    const o = t * (TILE_CELLS + 1);
    tiles.push({
      index: data16[o],
      heights: data16.subarray(o + 1, o + 1 + TILE_CELLS),
    });
  }
  return {
    tick: view.getUint32(4, true),
    machine: {
      strokes: [f(0), f(1), f(2)],
      slew: f(3),
      x: f(4),
      y: f(5),
      z: f(6),
      heading: f(7),
      tracks: [f(8), f(9)],
    },
    grains: new Int16Array(buffer, HEADER_BYTES, count * 4),
    tiles,
  };
}

// Copy decoded tiles into a full-grid Uint16Array of sand thickness.
export function applyTiles(terrain, tiles) {
  for (const { index, heights } of tiles) {
    const { i0, j0 } = tileCells(index);
    let o = 0;
    for (let j = j0; j < j0 + SAND.tile; j++)
      for (let i = i0; i < i0 + SAND.tile; i++, o++)
        if (i < SAND.nx && j < SAND.ny) terrain[j * SAND.nx + i] = heights[o];
  }
}

import { WORLD, SAND, YARD, clamp, cellX, cellY } from "../shared/world.js";
import {
  BEACH,
  groundHeight,
  groundSample,
  initialSand,
} from "../shared/landscape.js";

const { nx: NX, ny: NY, cell: CELL, tile: TILE, tilesX: TX, tilesY: TY } = SAND;
export const CELLS = NX * NY;
export const CELL_AREA = CELL * CELL;
export const TILE_CELLS = TILE * TILE;
const TALUS = Math.tan((SAND.reposeDeg * Math.PI) / 180);
// Height differences below this are treated as settled (mm).
const SETTLED = 0.02;
const DI = [1, -1, 0, 0, 1, 1, -1, -1];
const DJ = [0, 0, 1, -1, 1, -1, 1, -1];
const LIMIT = DI.map((_, k) => TALUS * CELL * (k < 4 ? 1 : Math.SQRT2));

// Cells are addressed by one number, c = j * NX + i, across the whole world.
// With NX = 4096 and 64-cell pages the page and offset come from a few bits.
const PAGE_CELLS = SAND.page * SAND.page,
  PAGES = (NX / SAND.page) * (NY / SAND.page);
const pageOf = (c) => ((c >>> 18) << 6) | ((c & 4095) >>> 6);
const offsetOf = (c) => (((c >>> 12) & 63) << 6) | (c & 63);
const pageCell = (page, offset) =>
  (((page >>> 6) << 6) | (offset >>> 6)) * NX +
  (((page & 63) << 6) | (offset & 63));

// The hard ground under every cell never changes, so all Terrains in a thread
// share one lazily built copy.
const basePages = new Array(PAGES).fill(null);
function basePage(page) {
  const out = (basePages[page] = new Float32Array(PAGE_CELLS));
  for (let o = 0; o < PAGE_CELLS; o++) {
    const c = pageCell(page, o);
    out[o] = groundHeight(cellX(c & 4095), cellY(c >>> 12));
  }
  return out;
}
const baseAt = (c) => {
  const page = pageOf(c);
  return (basePages[page] ?? basePage(page))[offsetOf(c)];
};

// Sand thickness above the hard ground on a sparse cell-centred grid. Material
// is only ever moved between cells or exchanged with free grains, so the total
// sand volume is conserved exactly (to floating-point rounding).
export class Terrain {
  constructor() {
    this.pages = new Array(PAGES).fill(null);
    this.flags = new Array(PAGES).fill(null);
    this.pressedPages = new Array(PAGES).fill(null);
    this.active = new Int32Array(1 << 15);
    this.work = new Int32Array(1 << 15);
    this.activeCount = 0;
    this.tileDirty = new Uint8Array(TX * TY);
    this.excess = new Float64Array(8);
  }

  copyFrom(other) {
    for (let p = 0; p < PAGES; p++) {
      const mine = this.pages[p],
        theirs = other.pages[p];
      if (mine || theirs) this.dirtyPage(p);
      this.pages[p] = theirs ? theirs.slice() : null;
    }
    this.flags.fill(null);
    this.pressedPages.fill(null);
    this.activeCount = 0;
  }

  dirtyPage(page) {
    const row = page >>> 6,
      col = page & 63,
      span = SAND.page / TILE;
    for (let tj = 0; tj < span; tj++)
      for (let ti = 0; ti < span; ti++)
        this.tileDirty[(row * span + tj) * TX + col * span + ti] = 1;
  }

  get(c) {
    const page = this.pages[pageOf(c)];
    return page === null ? 0 : page[offsetOf(c)];
  }

  add(c, amount) {
    const p = pageOf(c),
      page = this.pages[p] ?? (this.pages[p] = new Float64Array(PAGE_CELLS));
    page[offsetOf(c)] += amount;
  }

  surface(c) {
    return baseAt(c) + this.get(c);
  }

  // Tracks have already compacted this cell, so it gives no further.
  pressed(c) {
    const page = this.pressedPages[pageOf(c)];
    return page !== null && page[offsetOf(c)] === 1;
  }

  press(c) {
    const p = pageOf(c),
      page =
        this.pressedPages[p] ??
        (this.pressedPages[p] = new Uint8Array(PAGE_CELLS));
    page[offsetOf(c)] = 1;
  }

  flag(c) {
    const p = pageOf(c),
      page = this.flags[p] ?? (this.flags[p] = new Uint8Array(PAGE_CELLS)),
      o = offsetOf(c);
    if (page[o]) return;
    page[o] = 1;
    if (this.activeCount === this.active.length) {
      const grown = new Int32Array(this.active.length * 2);
      grown.set(this.active);
      this.active = grown;
      this.work = new Int32Array(grown.length);
    }
    this.active[this.activeCount++] = c;
  }

  // Mark a changed cell: its tile must be resent, and it and its neighbours
  // may now exceed the angle of repose.
  touch(c) {
    const i = c & 4095,
      j = c >>> 12;
    this.tileDirty[(j >> 4) * TX + (i >> 4)] = 1;
    for (let dj = -1; dj <= 1; dj++) {
      const nj = j + dj;
      if (nj < 0 || nj >= NY) continue;
      for (let di = -1; di <= 1; di++) {
        const ni = i + di;
        if (ni >= 0 && ni < NX) this.flag(nj * NX + ni);
      }
    }
  }

  cellAt(x, y) {
    const i = clamp(Math.floor((x - WORLD.minX) / CELL), 0, NX - 1),
      j = clamp(Math.floor((y - WORLD.minY) / CELL), 0, NY - 1);
    return j * NX + i;
  }

  // Sand surface: bilinear sand over the exact hard ground underneath.
  // Writes [height, dz/dx, dz/dy] to out.
  sample(x, y, out) {
    const u = clamp((x - WORLD.minX) / CELL - 0.5, 0, NX - 1.000001),
      v = clamp((y - WORLD.minY) / CELL - 0.5, 0, NY - 1.000001),
      i = Math.floor(u),
      j = Math.floor(v),
      fu = u - i,
      fv = v - j,
      c = j * NX + i,
      h00 = this.get(c),
      h10 = this.get(c + 1),
      h01 = this.get(c + NX),
      h11 = this.get(c + NX + 1),
      a = h00 + (h10 - h00) * fu,
      b = h01 + (h11 - h01) * fu;
    groundSample(x, y, out);
    out[0] += a + (b - a) * fv;
    out[1] += ((h10 - h00) * (1 - fv) + (h11 - h01) * fv) / CELL;
    out[2] += (b - a) / CELL;
  }

  // Spread a volume (mm^3) bilinearly over the four nearest cells.
  deposit(x, y, volume) {
    const u = clamp((x - WORLD.minX) / CELL - 0.5, 0, NX - 1.000001),
      v = clamp((y - WORLD.minY) / CELL - 0.5, 0, NY - 1.000001),
      i = Math.floor(u),
      j = Math.floor(v),
      fu = u - i,
      fv = v - j,
      c = j * NX + i,
      d = volume / CELL_AREA;
    this.add(c, d * (1 - fu) * (1 - fv));
    this.add(c + 1, d * fu * (1 - fv));
    this.add(c + NX, d * (1 - fu) * fv);
    this.add(c + NX + 1, d * fu * fv);
    this.touch(c);
    this.touch(c + 1);
    this.touch(c + NX);
    this.touch(c + NX + 1);
  }

  // Avalanche every over-steep slope toward the angle of repose. Each sweep
  // moves part of the steepest excess, so a cut face collapses over a few ticks
  // instead of instantly, while a tall spike falls apart at full speed. Only
  // recently disturbed cells are visited.
  relax(sweeps = 3, rate = 0.5) {
    const excess = this.excess;
    let moved = 0;
    for (let sweep = 0; sweep < sweeps && this.activeCount; sweep++) {
      const count = this.activeCount,
        work = this.work;
      work.set(this.active.subarray(0, count));
      this.activeCount = 0;
      for (let k = 0; k < count; k++) {
        const c = work[k];
        this.flags[pageOf(c)][offsetOf(c)] = 0;
      }
      for (let k = 0; k < count; k++) {
        const c = work[sweep % 2 ? count - 1 - k : k],
          hc = this.get(c);
        if (hc <= 1e-9) continue;
        const i = c & 4095,
          j = c >>> 12,
          sc = baseAt(c) + hc;
        let total = 0,
          steepest = 0;
        for (let n = 0; n < 8; n++) {
          const ni = i + DI[n],
            nj = j + DJ[n];
          excess[n] = 0;
          if (ni < 0 || ni >= NX || nj < 0 || nj >= NY) continue;
          const e = sc - this.surface(nj * NX + ni) - LIMIT[n];
          if (e > SETTLED) {
            excess[n] = e;
            total += e;
            if (e > steepest) steepest = e;
          }
        }
        if (!total) continue;
        const move = Math.min(hc, 0.5 * steepest * (steepest > 12 ? 1 : rate));
        for (let n = 0; n < 8; n++)
          if (excess[n]) {
            const target = (j + DJ[n]) * NX + i + DI[n];
            this.add(target, (move * excess[n]) / total);
            this.touch(target);
          }
        this.add(c, -move);
        this.touch(c);
        moved += move;
      }
    }
    return moved * CELL_AREA;
  }

  settle(maxSweeps = 4000) {
    for (let p = 0; p < PAGES; p++) {
      const page = this.pages[p];
      if (!page) continue;
      for (let o = 0; o < PAGE_CELLS; o++)
        if (page[o] > 0) this.touch(pageCell(p, o));
    }
    for (let i = 0; i < maxSweeps && this.activeCount; i++) this.relax(1, 1);
  }

  volume() {
    let sum = 0;
    for (const page of this.pages)
      if (page) for (let o = 0; o < PAGE_CELLS; o++) sum += page[o];
    return sum * CELL_AREA;
  }

  // Volume inside an axis-aligned rectangle of cell centres.
  volumeIn(zone) {
    const i0 = Math.ceil((zone.minX - WORLD.minX) / CELL - 0.5),
      i1 = Math.floor((zone.maxX - WORLD.minX) / CELL - 0.5),
      j0 = Math.ceil((zone.minY - WORLD.minY) / CELL - 0.5),
      j1 = Math.floor((zone.maxY - WORLD.minY) / CELL - 0.5);
    let sum = 0;
    for (let j = Math.max(0, j0); j <= Math.min(NY - 1, j1); j++)
      for (let i = Math.max(0, i0); i <= Math.min(NX - 1, i1); i++)
        sum += this.get(j * NX + i);
    return sum * CELL_AREA;
  }

  // Quantise changed tiles for the network into `store` (tile -> Uint16Array).
  // Returns the indices of tiles whose quantised contents really changed.
  quantize(store) {
    const changed = [],
      q = 1 / SAND.heightQuantum,
      scratch = new Uint16Array(TILE_CELLS);
    for (let t = 0; t < TX * TY; t++) {
      if (!this.tileDirty[t]) continue;
      this.tileDirty[t] = 0;
      const ti = t & (TX - 1),
        tj = t >>> 8;
      let o = 0,
        any = 0;
      for (let j = tj * TILE; j < (tj + 1) * TILE; j++)
        for (let i = ti * TILE; i < (ti + 1) * TILE; i++, o++) {
          const value = Math.min(65535, Math.round(this.get(j * NX + i) * q));
          scratch[o] = value;
          any |= value;
        }
      const held = store.get(t);
      if (held ? held.every((value, k) => value === scratch[k]) : !any)
        continue;
      store.set(t, scratch.slice());
      changed.push(t);
    }
    return changed;
  }
}

// The sand the world starts with: the yard and a beach. Built once per thread
// and copied on every reset.
let initial;
export function initialTerrain() {
  if (initial) return initial;
  initial = new Terrain();
  for (const area of [YARD, BEACH]) {
    const i0 = Math.floor((area.minX - WORLD.minX) / CELL),
      i1 = Math.ceil((area.maxX - WORLD.minX) / CELL),
      j0 = Math.floor((area.minY - WORLD.minY) / CELL),
      j1 = Math.ceil((area.maxY - WORLD.minY) / CELL);
    for (let j = j0; j <= j1; j++)
      for (let i = i0; i <= i1; i++) {
        const height = initialSand(cellX(i), cellY(j));
        if (height > 0) initial.add(j * NX + i, height);
      }
  }
  initial.settle();
  initial.activeCount = 0;
  initial.flags.fill(null);
  return initial;
}

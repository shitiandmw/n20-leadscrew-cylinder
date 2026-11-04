import {
  WORLD,
  SAND,
  clamp,
  cellX,
  cellY,
  groundHeight,
  groundSlope,
} from "../shared/world.js";

const { nx: NX, ny: NY, cell: CELL, tile: TILE, tilesX: TX, tilesY: TY } = SAND;
export const CELLS = NX * NY;
export const CELL_AREA = CELL * CELL;
const TALUS = Math.tan((SAND.reposeDeg * Math.PI) / 180);
// Height differences below this are treated as settled (mm).
const SETTLED = 0.02;
const DI = [1, -1, 0, 0, 1, 1, -1, -1];
const DJ = [0, 0, 1, -1, 1, -1, 1, -1];
const LIMIT = DI.map((_, k) => TALUS * CELL * (k < 4 ? 1 : Math.SQRT2));

// Sand thickness above the concrete on a cell-centred grid. Material is only
// ever moved between cells or exchanged with free grains, so the total sand
// volume is conserved exactly (to floating-point rounding).
export class Terrain {
  constructor() {
    this.h = new Float64Array(CELLS);
    this.base = Float64Array.from({ length: NX }, (_, i) =>
      groundHeight(cellX(i)),
    );
    this.flag = new Uint8Array(CELLS);
    this.active = new Int32Array(CELLS);
    this.work = new Int32Array(CELLS);
    this.activeCount = 0;
    this.tileDirty = new Uint8Array(TX * TY);
    this.excess = new Float64Array(8);
  }

  copyFrom(other) {
    this.h.set(other.h);
    this.flag.fill(0);
    this.activeCount = 0;
    this.tileDirty.fill(1);
  }

  surface(c) {
    return this.base[c % NX] + this.h[c];
  }

  // Mark a changed cell: its tile must be resent, and it and its neighbours
  // may now exceed the angle of repose.
  touch(c) {
    const i = c % NX,
      j = (c - i) / NX;
    this.tileDirty[(j >> 4) * TX + (i >> 4)] = 1;
    for (let dj = -1; dj <= 1; dj++) {
      const nj = j + dj;
      if (nj < 0 || nj >= NY) continue;
      for (let di = -1; di <= 1; di++) {
        const ni = i + di;
        if (ni < 0 || ni >= NX) continue;
        const n = nj * NX + ni;
        if (!this.flag[n]) {
          this.flag[n] = 1;
          this.active[this.activeCount++] = n;
        }
      }
    }
  }

  cellAt(x, y) {
    const i = clamp(Math.floor((x - WORLD.minX) / CELL), 0, NX - 1),
      j = clamp(Math.floor((y - WORLD.minY) / CELL), 0, NY - 1);
    return j * NX + i;
  }

  // Bilinear sand surface with the exact concrete profile underneath.
  // Writes [height, dz/dx, dz/dy] to out.
  sample(x, y, out) {
    const u = clamp((x - WORLD.minX) / CELL - 0.5, 0, NX - 1.000001),
      v = clamp((y - WORLD.minY) / CELL - 0.5, 0, NY - 1.000001);
    const i = Math.floor(u),
      j = Math.floor(v),
      fu = u - i,
      fv = v - j,
      c = j * NX + i,
      h = this.h;
    const h00 = h[c],
      h10 = h[c + 1],
      h01 = h[c + NX],
      h11 = h[c + NX + 1];
    const a = h00 + (h10 - h00) * fu,
      b = h01 + (h11 - h01) * fu;
    out[0] = groundHeight(x) + a + (b - a) * fv;
    out[1] =
      groundSlope(x) + ((h10 - h00) * (1 - fv) + (h11 - h01) * fv) / CELL;
    out[2] = (b - a) / CELL;
  }

  // Spread a volume (mm^3) bilinearly over the four nearest cells.
  deposit(x, y, volume) {
    const u = clamp((x - WORLD.minX) / CELL - 0.5, 0, NX - 1.000001),
      v = clamp((y - WORLD.minY) / CELL - 0.5, 0, NY - 1.000001);
    const i = Math.floor(u),
      j = Math.floor(v),
      fu = u - i,
      fv = v - j,
      c = j * NX + i,
      d = volume / CELL_AREA;
    this.h[c] += d * (1 - fu) * (1 - fv);
    this.h[c + 1] += d * fu * (1 - fv);
    this.h[c + NX] += d * (1 - fu) * fv;
    this.h[c + NX + 1] += d * fu * fv;
    this.touch(c);
    this.touch(c + 1);
    this.touch(c + NX);
    this.touch(c + NX + 1);
  }

  // Avalanche every over-steep slope toward the angle of repose. Each sweep
  // moves half of the steepest excess, so a cut face collapses over a few
  // ticks instead of instantly. Only recently disturbed cells are visited.
  relax(sweeps = 3, rate = 0.5) {
    const h = this.h,
      base = this.base,
      excess = this.excess;
    let moved = 0;
    for (let sweep = 0; sweep < sweeps && this.activeCount; sweep++) {
      const count = this.activeCount;
      this.work.set(this.active.subarray(0, count));
      this.activeCount = 0;
      for (let k = 0; k < count; k++) this.flag[this.work[k]] = 0;
      for (let k = 0; k < count; k++) {
        const c = this.work[sweep % 2 ? count - 1 - k : k],
          hc = h[c];
        if (hc <= 1e-9) continue;
        const i = c % NX,
          j = (c - i) / NX,
          sc = base[i] + hc;
        let total = 0,
          steepest = 0;
        for (let n = 0; n < 8; n++) {
          const ni = i + DI[n],
            nj = j + DJ[n];
          excess[n] = 0;
          if (ni < 0 || ni >= NX || nj < 0 || nj >= NY) continue;
          const e = sc - base[ni] - h[nj * NX + ni] - LIMIT[n];
          if (e > SETTLED) {
            excess[n] = e;
            total += e;
            if (e > steepest) steepest = e;
          }
        }
        if (!total) continue;
        const move = Math.min(hc, 0.5 * steepest * rate);
        for (let n = 0; n < 8; n++)
          if (excess[n]) {
            const target = (j + DJ[n]) * NX + i + DI[n];
            h[target] += (move * excess[n]) / total;
            this.touch(target);
          }
        h[c] -= move;
        this.touch(c);
        moved += move;
      }
    }
    return moved * CELL_AREA;
  }

  settle(maxSweeps = 4000) {
    for (let c = 0; c < CELLS; c++) this.touch(c);
    for (let i = 0; i < maxSweeps && this.activeCount; i++) this.relax(1, 1);
  }

  volume() {
    let sum = 0;
    for (let c = 0; c < CELLS; c++) sum += this.h[c];
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
        sum += this.h[j * NX + i];
    return sum * CELL_AREA;
  }

  // Quantise changed tiles for the network copy; returns true if any changed.
  quantize(target, versions, version) {
    let changed = false;
    const q = 1 / SAND.heightQuantum;
    for (let t = 0; t < TX * TY; t++) {
      if (!this.tileDirty[t]) continue;
      this.tileDirty[t] = 0;
      changed = true;
      versions[t] = version;
      const ti = t % TX,
        tj = (t - ti) / TX;
      for (let j = tj * TILE; j < Math.min(NY, (tj + 1) * TILE); j++)
        for (let i = ti * TILE; i < Math.min(NX, (ti + 1) * TILE); i++) {
          const c = j * NX + i;
          target[c] = Math.min(65535, Math.round(this.h[c] * q));
        }
    }
    return changed;
  }
}

// Deterministic value noise for a natural, slightly uneven stockpile surface.
function hash(i, j) {
  let n = Math.imul(i, 374761393) ^ Math.imul(j, 668265263);
  n = Math.imul(n ^ (n >>> 13), 1274126177);
  return ((n ^ (n >>> 16)) >>> 0) / 4294967296;
}
function noise(x, y) {
  const i = Math.floor(x),
    j = Math.floor(y),
    fx = x - i,
    fy = y - j,
    sx = fx * fx * (3 - 2 * fx),
    sy = fy * fy * (3 - 2 * fy);
  const a = hash(i, j) + (hash(i + 1, j) - hash(i, j)) * sx,
    b = hash(i, j + 1) + (hash(i + 1, j + 1) - hash(i, j + 1)) * sx;
  return a + (b - a) * sy - 0.5;
}

// Stockpiles in the pit, dumped at slightly below the angle of repose and
// clear of the marked pour zone. Built once and copied on every reset.
export const STOCKPILES = [
  { x: 575, y: -60, rx: 235, ry: 225, top: 125 },
  { x: 770, y: -250, rx: 190, ry: 185, top: 95 },
  { x: 440, y: 55, rx: 120, ry: 115, top: 42 },
];
let initial;
export function initialTerrain() {
  if (initial) return initial;
  initial = new Terrain();
  const slope = Math.tan((30 * Math.PI) / 180);
  for (let j = 0; j < NY; j++)
    for (let i = 0; i < NX; i++) {
      const x = cellX(i),
        y = cellY(j);
      let height = 0;
      for (const pile of STOCKPILES) {
        const r = Math.hypot((x - pile.x) / pile.rx, (y - pile.y) / pile.ry);
        const edge = (1 - r) * Math.min(pile.rx, pile.ry);
        height = Math.max(height, Math.min(pile.top, edge * slope));
      }
      if (height > 0)
        height = Math.max(
          0,
          height +
            Math.min(1, height / 12) *
              (3.2 * noise(x / 41, y / 41) + 1.4 * noise(x / 13, y / 13)),
        );
      initial.h[j * NX + i] = height;
    }
  initial.settle();
  initial.activeCount = 0;
  initial.flag.fill(0);
  return initial;
}

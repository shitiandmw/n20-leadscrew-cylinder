import { SAND } from "../shared/world.js";
import {
  LOAD,
  localU,
  mouthToLocal,
  upAlongU,
  upAlongW,
} from "../shared/bucket-load.js";

const { nu: NU, nv: NV, cells: CELLS, du: DU, dv: DV, area: AREA } = LOAD,
  { floors: FLOORS, ceilings: CEILINGS, lastOpen: LAST_OPEN } = LOAD,
  REPOSE = (SAND.reposeDeg * Math.PI) / 180,
  // Slopes past this are as good as vertical in a grid this size.
  STEEPEST = (85 * Math.PI) / 180,
  STEEP = Math.tan(STEEPEST),
  // With the mouth down past this, nothing in the cavity can stay: the plates
  // that would hold it are overhead, so all of it leaves by the lip.
  TIPPED = Math.PI / 2 + REPOSE,
  // Below this the sand counts as settled (mm).
  SETTLED = 0.01,
  // No column stands higher above the rims than the ridge of a heap at repose.
  OPEN_CAP = 26,
  // How far outside the bucket to look for the bed that covers its mouth (mm).
  OUTSIDE = 12,
  // How far past a rim the bed that buries it props the sand up (mm).
  PROPPED = OUTSIDE / 2,
  // The most a column at a rim loses per pass (mm): about 170 cm3/s over a lip.
  SPILL_RATE = 4,
  // Half the width of a cell of the bed, whose sand spreads over several columns.
  HALF_CELL = SAND.cell / 2;
const FLOOR = new Float64Array(CELLS);
for (let c = 0; c < CELLS; c++) FLOOR[c] = FLOORS[c % NU];
// Fixed limit of a column: the top plate, or the highest a heap stands.
const CEILING = new Float64Array(CELLS);
for (let c = 0; c < CELLS; c++) CEILING[c] = Math.min(OPEN_CAP, CEILINGS[c % NU]);
// The rims a column at the lip, at the far rim and at each cheek can spill over.
export const RIM_LIP = 0,
  RIM_FAR = 1,
  RIM_LEFT = 2,
  RIM_RIGHT = 3,
  RIM_BED = 4;
const RIMS = [RIM_LIP, RIM_FAR, RIM_LEFT, RIM_RIGHT, RIM_BED],
  rimLength = (rim) => (rim === RIM_LEFT || rim === RIM_RIGHT ? NU : NV);

// How steeply the surface may rise and fall along an axis, in the bucket, with the
// axis tilted `theta` above the horizontal: the world slope stays within repose.
function slopeLimits(theta, out) {
  const rise = REPOSE - theta,
    fall = -REPOSE - theta;
  out[0] = rise >= STEEPEST ? STEEP : rise <= -STEEPEST ? -STEEP : Math.tan(rise);
  out[1] = fall <= -STEEPEST ? -Infinity : fall >= STEEPEST ? STEEP : Math.tan(fall);
}

// What share of a bed cell, from `low` to `high` in grid units, lies over strip k of
// a grid. The strips at its ends take in what lies beyond them.
const shareOf = (low, high, k, count) =>
  (Math.min(high, k === count - 1 ? Infinity : k + 1) -
    Math.max(low, k === 0 ? -Infinity : k)) /
  (high - low);
const stripOf = (at, count) => Math.max(0, Math.min(count - 1, Math.floor(at)));

// One bucket's load: columns of sand that slump to the angle of repose in the
// bucket's own frame, whichever way it is tilted. A rim with sand above it spills,
// unless the bed buries that rim: then the bed holds the sand in, up to the mouth.
export class BucketLoad {
  constructor() {
    this.thickness = new Float64Array(CELLS);
    // How high each column may stand now, and which ones the bed lids.
    this.cap = new Float64Array(CELLS);
    this.lid = new Uint8Array(CELLS);
    // How much more this bucket holds, and down in the sand, each row of it.
    this.room = LOAD.capacity;
    this.rowRoom = new Float64Array(NV).fill(Infinity);
    this.volume = 0;
    // Volume on its way over each rim, by column, until there is a parcel of it.
    this.pending = RIMS.map((rim) => new Float64Array(rimLength(rim)));
    this.flowing = RIMS.map((rim) => new Uint8Array(rimLength(rim)));
    this.buriedRim = RIMS.map((rim) => new Uint8Array(rimLength(rim)));
    // Along each row, the first column the bed does not cover: the sand's lip.
    this.lipColumn = new Uint8Array(NV);
    this.alongU = new Float64Array(2);
    this.alongY = new Float64Array(2);
    this.point = new Float64Array(3);
    this.world = new Float64Array(3);
    this.settled = true;
    this.covered = false;
    this.sweep = 0;
    this.tilt = [0, 0];
    this.cap.set(CEILING);
  }

  clear() {
    this.thickness.fill(0);
    this.volume = 0;
    for (const pending of this.pending) pending.fill(0);
    this.room = LOAD.capacity;
    this.settled = true;
  }

  // Everything this bucket holds, including what has not left over a rim yet.
  get total() {
    let sum = this.volume;
    for (const pending of this.pending) for (const value of pending) sum += value;
    return sum;
  }

  // Put sand into the columns under a bed cell centred on a point in the bucket's
  // frame. Takes what its rows have room for and returns how much that was.
  add(x, y, z, volume) {
    const rowLow = (y + LOAD.halfWidth - HALF_CELL) / DV,
      rowHigh = (y + LOAD.halfWidth + HALF_CELL) / DV,
      u = localU(x, z),
      columnLow = (u - HALF_CELL) / DU,
      columnHigh = (u + HALF_CELL) / DU,
      lastRow = stripOf(rowHigh, NV),
      firstColumn = stripOf(columnLow, NU),
      lastColumn = stripOf(columnHigh, NU),
      wanted = Math.min(volume, this.room);
    let refused = volume - wanted;
    for (let j = stripOf(rowLow, NV); j <= lastRow; j++) {
      const share = wanted * shareOf(rowLow, rowHigh, j, NV),
        part = Math.min(share, this.rowRoom[j]);
      refused += share - part;
      this.rowRoom[j] -= part;
      for (let i = firstColumn; i <= lastColumn; i++)
        this.thickness[j * NU + i] +=
          (part * shareOf(columnLow, columnHigh, i, NU)) / AREA;
    }
    const taken = volume - refused;
    this.volume += taken;
    this.room -= taken;
    if (taken > 0) this.settled = false;
    return taken;
  }

  // Which rims the bed buries now, and where it lids the mouth. Only needed while
  // the bucket is down in the sand.
  coverBy(frame, terrain, touching) {
    if (!touching) {
      if (this.covered) {
        this.cap.set(CEILING);
        this.lid.fill(0);
        this.lipColumn.fill(0);
        this.rowRoom.fill(Infinity);
        for (const rims of this.buriedRim) rims.fill(0);
        this.covered = false;
        this.settled = false;
      }
      return;
    }
    this.covered = true;
    // Just outside the mouth and the rims: the bucket has cut away the bed at the
    // mouth itself.
    const point = this.point,
      world = this.world,
      under = (u, y, w) => {
        mouthToLocal(u, y, w, point);
        frame.toWorld(point[0], point[1], point[2], world);
        return terrain.surface(terrain.cellAt(world[0], world[1])) >= world[2];
      };
    let changed = false;
    const mark = (rims, index, value) => {
      if (rims[index] !== value) changed = true;
      rims[index] = value;
    };
    for (let j = 0; j < NV; j++) {
      const y = LOAD.rowY(j);
      for (let i = 0; i <= LAST_OPEN; i++) {
        mark(this.lid, j * NU + i, under(LOAD.columnU(i), y, OUTSIDE) ? 1 : 0);
      }
      mark(this.buriedRim[RIM_LIP], j, under(-OUTSIDE, y, OUTSIDE / 2) ? 1 : 0);
      mark(
        this.buriedRim[RIM_FAR],
        j,
        under(LOAD.length + OUTSIDE, y, OUTSIDE / 2) ? 1 : 0,
      );
    }
    for (let i = 0; i < NU; i++) {
      const u = LOAD.columnU(i),
        y = LOAD.halfWidth + OUTSIDE;
      mark(this.buriedRim[RIM_LEFT], i, under(u, -y, 0) ? 1 : 0);
      mark(this.buriedRim[RIM_RIGHT], i, under(u, y, 0) ? 1 : 0);
    }
    if (changed) this.settled = false;
  }

  // Down in the sand, the bed holds the load in. A column under the bed may fill to
  // the mouth; past that, the sand stands at repose from the bed's edge and from the
  // rims, which stand higher where the bed props it up. This is the most the bucket
  // can hold at this tilt.
  fitUnderBed(limitsU, limitsY) {
    const cap = this.cap,
      rise = limitsU[0],
      fall = -limitsU[1],
      riseY = limitsY[0],
      fallY = -limitsY[1],
      halfWidth = LOAD.halfWidth,
      length = LOAD.length,
      rimAt = (rim, index) => (this.buriedRim[rim][index] ? PROPPED : 0);
    let surplus = 0;
    for (let j = 0; j < NV; j++) {
      const y = LOAD.rowY(j),
        row = j * NU;
      let lipAt = 0;
      while (lipAt <= LAST_OPEN && this.lid[row + lipAt]) lipAt++;
      this.lipColumn[j] = lipAt;
      const lipU = lipAt ? LOAD.columnU(lipAt) - DU / 2 : 0,
        lipW = lipAt ? 0 : Math.max(FLOOR[0], rimAt(RIM_LIP, j)),
        farW = rimAt(RIM_FAR, j);
      for (let i = 0; i < NU; i++) {
        const c = row + i,
          u = LOAD.columnU(i);
        if (this.lid[c]) {
          cap[c] = Math.max(0, FLOOR[c]);
          continue;
        }
        let limit = CEILING[c];
        if (i <= LAST_OPEN)
          limit = Math.min(
            limit,
            lipW + rise * (u - lipU),
            farW + fall * (length - u),
            rimAt(RIM_LEFT, i) + riseY * (y + halfWidth),
            rimAt(RIM_RIGHT, i) + fallY * (halfWidth - y),
          );
        cap[c] = limit;
      }
    }
    // Pressed in past its limit, sand goes on along the row, then to the next row.
    const by = this.sweep % 2 === 0 ? 1 : -1,
      first = by > 0 ? 0 : NV - 1;
    for (let n = 0, j = first; n < NV; n++, j += by)
      surplus = this.settleRow(j, surplus);
    for (let n = 0, j = first + (NV - 1) * by; n < NV && surplus > 0; n++, j -= by)
      surplus = this.settleRow(j, surplus);
    // Nothing has room and no rim is open: it goes back to the bed it is in.
    this.pending[RIM_BED][NV >> 1] += surplus * AREA;
    for (let j = 0; j < NV; j++) {
      let room = 0;
      for (let c = j * NU; c < (j + 1) * NU; c++)
        room += Math.max(0, cap[c] - FLOOR[c] - this.thickness[c]);
      this.rowRoom[j] = room * AREA;
    }
  }

  // Whether this row's sand can leave by its lip: the bucket's, or the edge of the
  // bed that covers part of the mouth.
  lipOpen(j) {
    const lipAt = this.lipColumn[j];
    return lipAt <= LAST_OPEN && (lipAt > 0 || !this.buriedRim[RIM_LIP][j]);
  }

  // Past its limit, sand goes deeper, to the first column with room, or else back
  // towards the lip. What finds no room leaves by the lip, at its own pace, or is
  // passed on to the next row.
  settleRow(j, surplus) {
    const row = j * NU;
    for (let i = 0; i < NU; i++) surplus = this.settleColumn(row + i, surplus);
    for (let i = NU - 2; i >= 0 && surplus > 0; i--)
      surplus = this.settleColumn(row + i, surplus);
    if (surplus > 0 && this.lipOpen(j)) {
      this.thickness[row + this.lipColumn[j]] += surplus;
      return 0;
    }
    return surplus;
  }

  settleColumn(c, surplus) {
    const t = this.thickness;
    t[c] += surplus;
    const over = Math.min(t[c], Math.max(0, FLOOR[c] + t[c] - this.cap[c]));
    t[c] -= over;
    return over;
  }

  // Sand moves between two neighbours, b on the positive side of a.
  exchange(a, b, spacing, limits) {
    const t = this.thickness,
      cap = this.cap,
      wa = FLOOR[a] + t[a],
      wb = FLOOR[b] + t[b],
      difference = wb - wa,
      high = limits[0] * spacing,
      low = limits[1] * spacing;
    let move = 0;
    if (difference > high + SETTLED)
      move = Math.min(Math.max(0, cap[a] - wa), t[b], (difference - high) / 2);
    else if (difference < low - SETTLED)
      move = -Math.min(Math.max(0, cap[b] - wb), t[a], (low - difference) / 2);
    if (move === 0) return 0;
    t[a] += move;
    t[b] -= move;
    return Math.abs(move);
  }

  // Past a rim there is no sand to lean on: a column may stand above the rim only
  // as far as the slope allows. Whatever is above that leaves.
  spill(rim, index, c, rimW, rise, distance) {
    const t = this.thickness,
      excess = FLOOR[c] + t[c] - rimW - rise * distance;
    if (excess <= SETTLED || (rim !== RIM_BED && this.buriedRim[rim][index]))
      return 0;
    const move = Math.min(excess, t[c], SPILL_RATE);
    t[c] -= move;
    this.pending[rim][index] += move * AREA;
    this.flowing[rim][index] = 1;
    return move;
  }

  // One pass of slumping and spilling for this bucket's present tilt.
  relax(frame) {
    for (const flowing of this.flowing) flowing.fill(0);
    const up = upAlongU(frame.upX, frame.upZ),
      out = upAlongW(frame.upX, frame.upZ),
      tilt = this.tilt;
    if (Math.abs(up - tilt[0]) + Math.abs(out - tilt[1]) > 1e-6) {
      tilt[0] = up;
      tilt[1] = out;
      this.settled = false;
    }
    if (this.settled && !this.covered) return;
    const limitsU = this.alongU,
      limitsY = this.alongY;
    let theta = Math.atan2(up, out);
    if (theta < -TIPPED) theta = Math.PI;
    slopeLimits(theta, limitsU);
    slopeLimits(Math.atan2(frame.upY, Math.abs(out)), limitsY);
    if (this.covered) this.fitUnderBed(limitsU, limitsY);
    let moved = 0;
    // Each pass reverses the order of the moves, and those across the bucket run
    // in mirror image from its middle, so the sand has no favourite side.
    const forward = this.sweep++ % 2 === 0;
    for (let j = 0; j < NV; j++)
      for (let k = 0; k + 1 < NU; k++) {
        const c = j * NU + (forward ? k : NU - 2 - k);
        moved += this.exchange(c, c + 1, DU, limitsU);
      }
    const pairs = NV >> 1;
    for (let i = 0; i < NU; i++)
      for (let k = 0; k < pairs; k++) {
        const out = forward ? k : pairs - 1 - k,
          left = i + (pairs - 1 - out) * NU,
          right = i + (pairs + out) * NU;
        moved += forward
          ? this.exchange(left, left + NU, DV, limitsY) +
            this.exchange(right, right + NU, DV, limitsY)
          : this.exchange(right, right + NU, DV, limitsY) +
            this.exchange(left, left + NU, DV, limitsY);
      }
    // The sand's lip is the bucket's, or the edge of the bed that covers part of
    // the mouth, where the sand falls back on the bed. Surfaces falling towards a
    // rim on the far side are read from the falling limit.
    for (let j = 0; j < NV; j++) {
      const lipAt = this.lipColumn[j];
      if (this.lipOpen(j))
        moved += this.spill(
          lipAt ? RIM_BED : RIM_LIP,
          j,
          j * NU + lipAt,
          lipAt ? 0 : Math.max(0, FLOOR[0]),
          limitsU[0],
          DU / 2,
        );
      moved += this.spill(
        RIM_FAR,
        j,
        j * NU + LAST_OPEN,
        0,
        -limitsU[1],
        LOAD.length - LOAD.columnU(LAST_OPEN),
      );
    }
    for (let i = 0; i <= LAST_OPEN; i++) {
      moved += this.spill(RIM_LEFT, i, i, 0, limitsY[0], DV / 2);
      moved += this.spill(RIM_RIGHT, i, (NV - 1) * NU + i, 0, -limitsY[1], DV / 2);
    }
    this.settled = moved < SETTLED;
    // Recounted from the columns, so rounding in the moves cannot build up.
    let thickness = 0;
    for (let c = 0; c < CELLS; c++) thickness += this.thickness[c];
    this.volume = thickness * AREA;
    this.room = Math.max(0, LOAD.capacity - this.total);
  }

  // Thickness of every column for the network, or null for an empty bucket.
  pack() {
    if (this.volume <= 1) return null;
    const out = new Uint16Array(CELLS),
      q = 1 / LOAD.quantum;
    for (let c = 0; c < CELLS; c++)
      out[c] = Math.min(65535, Math.round(this.thickness[c] * q));
    return out;
  }
}

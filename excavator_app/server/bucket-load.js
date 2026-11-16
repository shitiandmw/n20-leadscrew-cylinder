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
  RADIANS = Math.PI / 180,
  // Sand at rest in a bucket holds up to this slope, and sand on the move comes to
  // rest at this one. Between the two a heap stays put while the bucket tilts.
  HOLD = SAND.heapDeg * RADIANS,
  SLIDE = SAND.heapSlideDeg * RADIANS,
  // Slopes past this are as good as vertical in a grid this size.
  STEEPEST = 85 * RADIANS,
  STEEP = Math.tan(STEEPEST),
  COS_STEEPEST = Math.cos(STEEPEST),
  // With the mouth down past this, nothing in the cavity can stay: the plates
  // that would hold it are overhead, so all of it leaves by the lip.
  TIPPED = Math.PI / 2 + SLIDE,
  // Below this the sand counts as settled (mm).
  SETTLED = 0.01,
  // Down in the sand a bucket takes this much more than a heap (mm): the layer
  // that runs off its sides as it comes out.
  SURCHARGE = 5,
  // No column stands higher above the rims than the ridge of that.
  OPEN_CAP = LOAD.halfWidth * Math.tan(HOLD) + SURCHARGE + 1,
  // The most a column at a rim loses per pass (mm): about 130 cm3/s over the lip.
  SPILL_RATE = 4,
  // Sand that has just moved goes on sliding for this many passes, a tenth of a
  // second, and only a move of at least this much (mm) counts: the last creep of a
  // slide that is coming to rest does not keep it going.
  MOBILE = 12,
  MOVING = 0.05,
  // Half the width of a cell of the bed, whose sand spreads over several columns.
  HALF_CELL = SAND.cell / 2,
  // Looking for the bed beside a rim: in steps of half a cell, as far as the
  // bucket's own plates and teeth can reach past that rim.
  STEP = SAND.cell / 2,
  REACH_LIP = 8,
  REACH_UNDER = 20,
  REACH_FAR = 12,
  REACH_CHEEK = 4,
  // A bed level that differs by less than this is the same bed (mm).
  SAME = 0.05;
const FLOOR = new Float64Array(CELLS);
for (let c = 0; c < CELLS; c++) FLOOR[c] = FLOORS[c % NU];
// Fixed limit of a column: the top plate, or the highest a heap stands.
const CEILING = new Float64Array(CELLS);
for (let c = 0; c < CELLS; c++) CEILING[c] = Math.min(OPEN_CAP, CEILINGS[c % NU]);
// The rims a column at the lip, at the far rim and at each cheek can spill over.
export const RIM_LIP = 0,
  RIM_FAR = 1,
  RIM_LEFT = 2,
  RIM_RIGHT = 3;
const RIMS = [RIM_LIP, RIM_FAR, RIM_LEFT, RIM_RIGHT],
  rimLength = (rim) => (rim === RIM_LEFT || rim === RIM_RIGHT ? NU : NV);

// How steeply the surface may rise and fall along an axis, in the bucket, with the
// axis tilted `theta` above the horizontal: the world slope stays within `phi`.
function slopeLimits(phi, theta, out) {
  const rise = phi - theta,
    fall = -phi - theta;
  out[0] = rise >= STEEPEST ? STEEP : rise <= -STEEPEST ? -STEEP : Math.tan(rise);
  out[1] = fall <= -STEEPEST ? -Infinity : fall >= STEEPEST ? STEEP : Math.tan(fall);
}

// The bed standing above a rim holds the load up from there. This is how far out
// of the mouth (mm) each millimetre of bed above the rim lets the sand at that rim
// stand, with the mouth tilted `theta` towards the rim and sand that lies at `phi`:
// the line at `phi` through the top of the bed, read where the rim is.
function propFactor(theta, phi) {
  if (Math.cos(theta) >= 0)
    return Math.cos(phi) / Math.max(Math.cos(theta - phi), COS_STEEPEST);
  // Past upright the mouth hangs over the sand in front of it, which holds in
  // everything below its own level.
  if (Math.sin(theta) <= 0) return Math.cos(phi) / COS_STEEPEST;
  return (
    (theta - phi >= STEEPEST ? STEEP : Math.tan(theta - phi)) /
    Math.max(Math.sin(theta), 0.05)
  );
}

// What share of a bed cell, from `low` to `high` in grid units, lies over strip k of
// a grid. The strips at its ends take in what lies beyond them.
const shareOf = (low, high, k, count) =>
  (Math.min(high, k === count - 1 ? Infinity : k + 1) -
    Math.max(low, k === 0 ? -Infinity : k)) /
  (high - low);
const stripOf = (at, count) => Math.max(0, Math.min(count - 1, Math.floor(at)));

// One bucket's load: columns of sand that slump in the bucket's own frame, whichever
// way it is tilted. Sand at rest holds up to HOLD, and sand that slides stops at
// SLIDE. Sand standing above a rim by more than that spills over it, unless the bed
// stands beside that rim: then the bed holds the sand in, as high as it stands itself.
export class BucketLoad {
  constructor() {
    this.thickness = new Float64Array(CELLS);
    // How high each column may stand now for more sand to be pressed into it, and
    // how high before it meets the bed in front of the mouth.
    this.cap = new Float64Array(CELLS);
    this.space = new Float64Array(CELLS);
    // Columns whose sand is on the move: passes left before it counts as at rest.
    this.mobile = new Uint8Array(CELLS);
    // How much more this bucket holds, and down in the sand, each row of it.
    this.room = LOAD.capacity;
    this.rowRoom = new Float64Array(NV).fill(Infinity);
    this.volume = 0;
    // Volume on its way over each rim, by column, until there is a parcel of it.
    this.pending = RIMS.map((rim) => new Float64Array(rimLength(rim)));
    this.flowing = RIMS.map((rim) => new Uint8Array(rimLength(rim)));
    // What a stream leaves behind along each rim when it stops, too little for a
    // parcel anywhere: its volume, where the last of it was, and for how many
    // passes that rim has been still.
    this.dregs = new Float64Array(RIMS.length);
    this.dregAt = new Uint8Array(RIMS.length);
    this.still = new Uint16Array(RIMS.length);
    // How far the bed stands above each rim, beside it (mm, never below the rim),
    // and how far above each row's lip the bed in front of the mouth stands.
    this.props = RIMS.map((rim) => new Float64Array(rimLength(rim)));
    this.front = new Float64Array(NV).fill(-Infinity);
    // Along each row, the first column the bed in front does not reach: where that
    // row's sand can leave by the lip.
    this.lipColumn = new Uint8Array(NV);
    this.holdU = new Float64Array(2);
    this.holdY = new Float64Array(2);
    this.slideU = new Float64Array(2);
    this.slideY = new Float64Array(2);
    this.point = new Float64Array(3);
    this.world = new Float64Array(3);
    this.column = new Float64Array(4);
    this.centreAt = new Float64Array(3);
    this.settled = true;
    this.covered = false;
    this.sweep = 0;
    this.tilt = [0, 0];
    this.theta = 0;
    this.out = 1;
    this.cap.set(CEILING);
    this.space.set(CEILING);
  }

  clear() {
    this.thickness.fill(0);
    this.mobile.fill(0);
    this.volume = 0;
    for (const pending of this.pending) pending.fill(0);
    this.dregs.fill(0);
    this.room = LOAD.capacity;
    this.settled = true;
  }

  // Everything this bucket holds, including what has not left over a rim yet.
  get total() {
    let sum = this.volume;
    for (const pending of this.pending) for (const value of pending) sum += value;
    for (const value of this.dregs) sum += value;
    return sum;
  }

  // Where the sand in the columns has its centre, in the bucket's frame: x and z
  // into out[1] and out[2] (mm). Returns the columns' volume (mm³).
  centre(out) {
    let sum = 0,
      alongU = 0,
      alongW = 0;
    for (let c = 0; c < CELLS; c++) {
      const t = this.thickness[c];
      if (t <= 0) continue;
      sum += t;
      alongU += t * LOAD.columnU(c % NU);
      alongW += t * (FLOOR[c] + t / 2);
    }
    if (sum <= 0) {
      out[1] = out[2] = 0;
      return 0;
    }
    mouthToLocal(alongU / sum, 0, alongW / sum, this.centreAt);
    out[1] = this.centreAt[0];
    out[2] = this.centreAt[2];
    return sum * AREA;
  }

  // Put sand into the columns under a bed cell centred on a point in the bucket's
  // frame. Takes what its rows have room for and returns how much that was. Sand
  // dug out of the bed is pressed in and stays where it is put; `loose` sand, which
  // fell in from above, arrives on the move.
  add(x, y, z, volume, loose = false) {
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
      if (part <= 0) continue;
      const row = j * NU;
      let over = 0;
      for (let i = firstColumn; i <= lastColumn; i++)
        over += this.press(
          row + i,
          (part * shareOf(columnLow, columnHigh, i, NU)) / AREA,
          loose,
        );
      // Down in the sand a column holds only so much. What is pressed in past that
      // goes on to the columns of its row that have room: deeper first, then back
      // towards the lip.
      for (let i = lastColumn + 1; i < NU && over > 0; i++)
        over = this.press(row + i, over, loose);
      for (let i = lastColumn; i >= 0 && over > 0; i--)
        over = this.press(row + i, over, loose);
      // Rounding only: the row had room for all of it.
      if (over > 0) this.thickness[row + firstColumn] += over;
    }
    const taken = volume - refused;
    this.volume += taken;
    this.room -= taken;
    if (taken > 0) this.settled = false;
    return taken;
  }

  // Sand (mm of thickness) into one column, as far as it holds down in the sand,
  // and all of it in the open. Returns what did not fit.
  press(c, amount, loose) {
    const t = this.thickness,
      given = this.covered
        ? Math.min(amount, Math.max(0, this.cap[c] - FLOOR[c] - t[c]))
        : amount;
    if (given > 0) {
      t[c] += given;
      if (loose) this.mobile[c] = MOBILE;
    }
    return amount - given;
  }

  // The level of the bed beside the bucket: the surface of the first cell with
  // nothing standing over it, going from a point in steps of (dx, dy). Cells under
  // this or any bucket have had their sand cut away, so they say nothing about the
  // bed that holds a load in. -Infinity if the bed is further off than `reach`.
  bedBeside(terrain, x, y, dx, dy, reach) {
    for (let k = 1; k <= reach; k++) {
      const cell = terrain.cellAt(x + k * dx, y + k * dy);
      if (terrain.ceilingAt(cell) === Infinity) return terrain.surface(cell);
    }
    return -Infinity;
  }

  // The highest the bed stands under a mouth that hangs over it, from a point on
  // the lip towards the machine: under such a mouth the bed is cut to the mouth's
  // own shape, and it holds the load in from below.
  bedUnder(frame, terrain, x, y, dx, dy) {
    const column = this.column;
    let highest = -Infinity;
    for (let k = 1; k <= REACH_UNDER; k++) {
      const px = x + k * dx,
        py = y + k * dy,
        cell = terrain.cellAt(px, py);
      if (terrain.ceilingAt(cell) === Infinity)
        return Math.max(highest, terrain.surface(cell));
      // Only where the mouth itself faces down on this cell.
      if (frame.column(px, py, column) && column[2])
        highest = Math.max(highest, terrain.surface(cell));
    }
    return highest;
  }

  // How high the bed stands beside each rim, and in front of the mouth. Only needed
  // while the bucket is down in the sand, once a tick.
  coverBy(frame, terrain, touching) {
    if (!touching) {
      if (this.covered) {
        this.cap.set(CEILING);
        this.space.set(CEILING);
        this.lipColumn.fill(0);
        this.rowRoom.fill(Infinity);
        this.front.fill(-Infinity);
        for (const props of this.props) props.fill(0);
        this.covered = false;
        this.settled = false;
      }
      return;
    }
    this.covered = true;
    const point = this.point,
      world = this.world,
      { ey } = frame,
      // Level directions: across the bucket, and from the bucket to its machine.
      across = Math.hypot(ey[0], ey[1]) || 1,
      sideX = (ey[0] / across) * STEP,
      sideY = (ey[1] / across) * STEP,
      nearX = (-ey[1] / across) * STEP,
      nearY = (ey[0] / across) * STEP,
      overhangs = upAlongW(frame.upX, frame.upZ) < 0;
    let changed = false;
    const note = (values, index, value) => {
      if (
        values[index] !== value &&
        !(Math.abs(values[index] - value) < SAME)
      ) {
        values[index] = value;
        changed = true;
      }
    };
    const rimAt = (u, y) => {
      mouthToLocal(u, y, 0, point);
      frame.toWorld(point[0], point[1], point[2], world);
    };
    for (let j = 0; j < NV; j++) {
      const y = LOAD.rowY(j);
      rimAt(0, y);
      const ahead = overhangs
        ? this.bedUnder(frame, terrain, world[0], world[1], nearX, nearY)
        : this.bedBeside(terrain, world[0], world[1], nearX, nearY, REACH_LIP);
      note(this.front, j, ahead - world[2]);
      note(this.props[RIM_LIP], j, Math.max(0, ahead - world[2]));
      rimAt(LOAD.length, y);
      note(
        this.props[RIM_FAR],
        j,
        Math.max(
          0,
          this.bedBeside(terrain, world[0], world[1], -nearX, -nearY, REACH_FAR) -
            world[2],
        ),
      );
    }
    for (let i = 0; i <= LAST_OPEN; i++) {
      const u = LOAD.columnU(i);
      rimAt(u, -LOAD.halfWidth);
      note(
        this.props[RIM_LEFT],
        i,
        Math.max(
          0,
          this.bedBeside(terrain, world[0], world[1], -sideX, -sideY, REACH_CHEEK) -
            world[2],
        ),
      );
      rimAt(u, LOAD.halfWidth);
      note(
        this.props[RIM_RIGHT],
        i,
        Math.max(
          0,
          this.bedBeside(terrain, world[0], world[1], sideX, sideY, REACH_CHEEK) -
            world[2],
        ),
      );
    }
    if (changed) this.settled = false;
  }

  // Down in the sand, the bed holds the load in. Where the bed stands in front of
  // the mouth a column fills to the mouth, or as far as the bed's face; past that,
  // the sand stands from the bed's edge and from each rim as steeply as it holds,
  // higher where the bed stands above that rim. On top of what the posture would
  // carry in the open goes a little more, which runs off as the bucket comes out.
  // This is the most that can be pressed into the bucket at this tilt. Where the
  // sand is on the move it is less: only as steep as sliding sand comes to rest,
  // or the digging would press in again what has just slid away, for ever.
  fitToBed(theta, up, out) {
    const cap = this.cap,
      space = this.space,
      mobile = this.mobile,
      props = this.props,
      holdU = this.holdU,
      holdY = this.holdY,
      slideU = this.slideU,
      slideY = this.slideY,
      halfWidth = LOAD.halfWidth,
      length = LOAD.length,
      level = up * up + out * out,
      lipHold = propFactor(theta, HOLD),
      lipSlide = propFactor(theta, SLIDE),
      farHold = propFactor(-theta, HOLD),
      farSlide = propFactor(-theta, SLIDE),
      side = out > 0.05 ? 1 / out : 20;
    for (let j = 0; j < NV; j++) {
      const y = LOAD.rowY(j),
        row = j * NU,
        front = this.front[j],
        lip = props[RIM_LIP][j],
        far = props[RIM_FAR][j];
      let lipAt = -1;
      for (let i = 0; i < NU; i++) {
        const c = row + i,
          u = LOAD.columnU(i),
          // Past the far rim the top plate covers a pocket: nothing leaves there,
          // but sand gets in only as far as the rest of the load holds it up.
          pocket = i > LAST_OPEN,
          // The bed's face stands in front of this column where the column,
          // followed out of the mouth, meets it below the bed's own level.
          faced =
            up > 0 &&
            front > 0 &&
            (out >= 0 ? u * level < front * up : u * up <= front),
          room = faced
            ? Math.min(CEILING[c], Math.max(0, (u * out) / up))
            : CEILING[c],
          moving = mobile[c] > 0,
          alongU = moving ? slideU : holdU,
          alongY = moving ? slideY : holdY,
          rise = alongU[0] * u,
          fall = pocket ? Infinity : -alongU[1] * (length - u),
          left = alongY[0] * (y + halfWidth),
          right = -alongY[1] * (halfWidth - y),
          open = Math.min(rise, fall, left, right),
          held = Math.min(
            faced ? Infinity : lip * (moving ? lipSlide : lipHold) + rise,
            far * (moving ? farSlide : farHold) + fall,
            props[RIM_LEFT][Math.min(i, LAST_OPEN)] * side + left,
            props[RIM_RIGHT][Math.min(i, LAST_OPEN)] * side + right,
          );
        if (!faced && !pocket && lipAt < 0) lipAt = i;
        space[c] = room;
        cap[c] = Math.min(room, held, Math.max(open + SURCHARGE, 0));
      }
      this.lipColumn[j] = lipAt < 0 ? NU : lipAt;
    }
  }

  // The sand in the columns, counted afresh so that rounding in the moves cannot
  // build up, and how much more each row can take down in the sand.
  recount() {
    const t = this.thickness,
      cap = this.cap,
      covered = this.covered;
    let thickness = 0;
    for (let j = 0; j < NV; j++) {
      let room = 0;
      for (let c = j * NU; c < (j + 1) * NU; c++) {
        thickness += t[c];
        room += Math.max(0, cap[c] - FLOOR[c] - t[c]);
      }
      this.rowRoom[j] = covered ? room * AREA : Infinity;
    }
    this.volume = thickness * AREA;
    this.room = Math.max(0, LOAD.capacity - this.total);
  }

  // How steeply the sand may lie at this tilt, and down in the sand, what the bed
  // lets the bucket hold. Returns false for a tilt at which nothing can move.
  fit(frame) {
    let up = upAlongU(frame.upX, frame.upZ),
      out = upAlongW(frame.upX, frame.upZ);
    const tilt = this.tilt;
    if (Math.abs(up - tilt[0]) + Math.abs(out - tilt[1]) > 1e-6) {
      tilt[0] = up;
      tilt[1] = out;
      this.settled = false;
    }
    if (this.settled) return false;
    let theta = Math.atan2(up, out);
    if (theta < -TIPPED) {
      theta = Math.PI;
      out = -Math.hypot(up, out);
      up = 0;
    }
    const lean = Math.atan2(frame.upY, Math.abs(out));
    slopeLimits(HOLD, theta, this.holdU);
    slopeLimits(SLIDE, theta, this.slideU);
    slopeLimits(HOLD, lean, this.holdY);
    slopeLimits(SLIDE, lean, this.slideY);
    this.theta = theta;
    this.out = out;
    if (this.covered) this.fitToBed(theta, up, out);
    return true;
  }

  // The bucket has just met the bed: from now on the bed holds its load in, and
  // limits what goes into it.
  meetBed(frame, terrain) {
    this.coverBy(frame, terrain, true);
    this.settled = false;
    this.fit(frame);
    this.recount();
  }

  // Sand moves between two neighbours, b on the positive side of a. Sand at rest
  // lets go only past what it holds, unless the sand below it is already moving;
  // once it goes, it slides until the slope is the one sliding sand stops at.
  exchange(a, b, spacing, hold, slide) {
    const t = this.thickness,
      space = this.space,
      mobile = this.mobile,
      wa = FLOOR[a] + t[a],
      wb = FLOOR[b] + t[b],
      difference = wb - wa;
    let move = 0;
    if (difference > (mobile[a] ? slide[0] : hold[0]) * spacing + SETTLED)
      move = Math.min(
        Math.max(0, space[a] - wa),
        t[b],
        (difference - slide[0] * spacing) / 2,
      );
    else if (difference < (mobile[b] ? slide[1] : hold[1]) * spacing - SETTLED)
      move = -Math.min(
        Math.max(0, space[b] - wb),
        t[a],
        (slide[1] * spacing - difference) / 2,
      );
    if (!(Math.abs(move) > 0)) return 0;
    t[a] += move;
    t[b] -= move;
    if (Math.abs(move) > MOVING) mobile[a] = mobile[b] = MOBILE;
    return Math.abs(move);
  }

  // Past a rim there is no sand to lean on: a column may stand above the rim only
  // as far as the slope allows, `holdAt` at rest and `slideAt` once it is moving.
  // Whatever is above that leaves, at a limited rate.
  spill(rim, index, c, holdAt, slideAt) {
    const t = this.thickness,
      top = FLOOR[c] + t[c];
    if (top - (this.mobile[c] ? slideAt : holdAt) <= SETTLED) return 0;
    const move = Math.min(top - slideAt, t[c], SPILL_RATE);
    if (!(move > 0)) return 0;
    t[c] -= move;
    this.pending[rim][index] += move * AREA;
    this.flowing[rim][index] = 1;
    if (move > MOVING) this.mobile[c] = MOBILE;
    return move;
  }

  // One pass of slumping and spilling for this bucket's present tilt.
  relax(frame) {
    for (const flowing of this.flowing) flowing.fill(0);
    if (!this.fit(frame)) return;
    const { holdU, holdY, slideU, slideY, theta, out } = this;
    let moved = 0;
    // Each pass reverses the order of the moves, and those across the bucket run
    // in mirror image from its middle, so the sand has no favourite side.
    const forward = this.sweep++ % 2 === 0;
    for (let j = 0; j < NV; j++)
      for (let k = 0; k + 1 < NU; k++) {
        const c = j * NU + (forward ? k : NU - 2 - k);
        moved += this.exchange(c, c + 1, DU, holdU, slideU);
      }
    const pairs = NV >> 1;
    for (let i = 0; i < NU; i++)
      for (let k = 0; k < pairs; k++) {
        const out = forward ? k : pairs - 1 - k,
          left = i + (pairs - 1 - out) * NU,
          right = i + (pairs + out) * NU;
        moved += forward
          ? this.exchange(left, left + NU, DV, holdY, slideY) +
            this.exchange(right, right + NU, DV, holdY, slideY)
          : this.exchange(right, right + NU, DV, holdY, slideY) +
            this.exchange(left, left + NU, DV, holdY, slideY);
      }
    // A row's sand leaves by the lip from the first column the bed in front does
    // not reach: the lip itself, in the open. Surfaces falling towards a rim on the
    // far side are read from the falling limit.
    const props = this.props,
      lipHold = propFactor(theta, HOLD),
      lipSlide = propFactor(theta, SLIDE),
      farHold = propFactor(-theta, HOLD),
      farSlide = propFactor(-theta, SLIDE),
      side = out > 0.05 ? 1 / out : 20,
      farAway = LOAD.length - LOAD.columnU(LAST_OPEN);
    for (let j = 0; j < NV; j++) {
      const lipAt = this.lipColumn[j],
        prop = props[RIM_LIP][j],
        back = props[RIM_FAR][j];
      if (lipAt <= LAST_OPEN) {
        const u = LOAD.columnU(lipAt);
        moved += this.spill(
          RIM_LIP,
          j,
          j * NU + lipAt,
          prop * lipHold + holdU[0] * u,
          prop * lipSlide + slideU[0] * u,
        );
      }
      moved += this.spill(
        RIM_FAR,
        j,
        j * NU + LAST_OPEN,
        back * farHold - holdU[1] * farAway,
        back * farSlide - slideU[1] * farAway,
      );
    }
    for (let i = 0; i <= LAST_OPEN; i++) {
      const left = props[RIM_LEFT][i] * side,
        right = props[RIM_RIGHT][i] * side;
      moved += this.spill(
        RIM_LEFT,
        i,
        i,
        left + (holdY[0] * DV) / 2,
        left + (slideY[0] * DV) / 2,
      );
      moved += this.spill(
        RIM_RIGHT,
        i,
        (NV - 1) * NU + i,
        right - (holdY[1] * DV) / 2,
        right - (slideY[1] * DV) / 2,
      );
    }
    this.settled = moved < SETTLED;
    const mobile = this.mobile;
    for (let c = 0; c < CELLS; c++)
      if (mobile[c]) mobile[c] = this.settled ? 0 : mobile[c] - 1;
    this.recount();
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

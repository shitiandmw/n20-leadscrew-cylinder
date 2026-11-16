import { SAND } from "../shared/world.js";
import { TRUCK, TRUCK_LOAD } from "../shared/truck.js";

const { nu: NU, nv: NV, cells: CELLS, du: DU, dv: DV, area: AREA } = TRUCK_LOAD,
  RADIANS = Math.PI / 180,
  // Sand poured into a body lands loose, as it does on the bed: at rest it stands
  // as steep as the bed's angle of repose, and what slides comes to rest a little
  // flatter, so a load does not trickle away at every bump in the road.
  HOLD = SAND.reposeDeg * RADIANS,
  SLIDE = (SAND.reposeDeg - 3) * RADIANS,
  STEEPEST = 85 * RADIANS,
  STEEP = Math.tan(STEEPEST),
  // Below this the sand counts as settled (mm).
  SETTLED = 0.01,
  // The most a column at a rim loses per pass (mm), as from a bucket.
  SPILL_RATE = 4,
  // Under the swinging rear wall the sand gets out through the gap at its foot;
  // a gap this wide (mm) lets it go as fast as over a rim.
  FULL_GAP = 16,
  MOBILE = 12,
  MOVING = 0.05,
  // A bed level that differs by less than this is the same bed (mm).
  SAME = 0.05,
  // Looking for the bed behind the open rear: this far beyond the rim (mm).
  BEHIND = 12;

// The rims a column can leave the body over: the rear, under or over the rear
// wall, the front wall, and the right (-y) and left (+y) side walls.
export const RIM_REAR = 0,
  RIM_FRONT = 1,
  RIM_RIGHT = 2,
  RIM_LEFT = 3;
const RIMS = [RIM_REAR, RIM_FRONT, RIM_RIGHT, RIM_LEFT],
  rimLength = (rim) => (rim === RIM_REAR || rim === RIM_FRONT ? NV : NU);

// How steeply the surface may rise and fall along an axis tilted `theta` above the
// horizontal, so that in the world it stays within `phi`.
function slopeLimits(phi, theta, out) {
  const rise = phi - theta,
    fall = -phi - theta;
  out[0] = rise >= STEEPEST ? STEEP : rise <= -STEEPEST ? -STEEP : Math.tan(rise);
  out[1] = fall <= -STEEPEST ? -STEEP : fall >= STEEPEST ? STEEP : Math.tan(fall);
}

// The sand in a truck's body: columns standing on its flat floor, slumping in the
// body's frame however the truck leans and the body tips. Sand that stands above a
// wall by more than its slope allows leaves over it; once the rear wall swings
// open, the rear is open at the floor and the load runs out there, unless the
// sand already tipped behind the truck stands as high as the opening.
export class TruckLoad {
  constructor() {
    this.thickness = new Float64Array(CELLS);
    this.mobile = new Uint8Array(CELLS);
    this.pending = RIMS.map((rim) => new Float64Array(rimLength(rim)));
    this.flowing = RIMS.map((rim) => new Uint8Array(rimLength(rim)));
    this.dregs = new Float64Array(RIMS.length);
    this.dregAt = new Uint8Array(RIMS.length);
    this.still = new Uint16Array(RIMS.length);
    // How high the bed behind the open rear stands over the floor's edge, by row.
    this.props = new Float64Array(NV);
    this.holdU = new Float64Array(2);
    this.holdY = new Float64Array(2);
    this.slideU = new Float64Array(2);
    this.slideY = new Float64Array(2);
    this.point = new Float64Array(3);
    this.tilt = [NaN, NaN];
    this.gap = 0;
    this.volume = 0;
    this.settled = true;
    this.sweep = 0;
  }

  clear() {
    this.thickness.fill(0);
    this.mobile.fill(0);
    for (const pending of this.pending) pending.fill(0);
    this.dregs.fill(0);
    this.props.fill(0);
    this.volume = 0;
    this.settled = true;
  }

  // Everything the body holds, including what has not left over a rim yet (mm³).
  get total() {
    let sum = this.volume;
    for (const pending of this.pending) for (const value of pending) sum += value;
    for (const value of this.dregs) sum += value;
    return sum;
  }

  // The top of the sand over a point of the floor (mm over the floor).
  surface(x, y) {
    const i = Math.max(0, Math.min(NU - 1, Math.floor(x / DU))),
      j = Math.max(0, Math.min(NV - 1, Math.floor((y + TRUCK_LOAD.halfWidth) / DV)));
    return this.thickness[j * NU + i];
  }

  // Sand that has fallen in at a point of the floor, shared among the four columns
  // round it. It arrives on the move.
  add(x, y, volume) {
    const u = Math.max(0, Math.min(NU - 1, x / DU - 0.5)),
      v = Math.max(0, Math.min(NV - 1, (y + TRUCK_LOAD.halfWidth) / DV - 0.5)),
      i = Math.min(NU - 2, Math.floor(u)),
      j = Math.min(NV - 2, Math.floor(v)),
      fu = u - i,
      fv = v - j,
      depth = volume / AREA;
    const put = (c, share) => {
      if (share <= 0) return;
      this.thickness[c] += depth * share;
      this.mobile[c] = MOBILE;
    };
    put(j * NU + i, (1 - fu) * (1 - fv));
    put(j * NU + i + 1, fu * (1 - fv));
    put((j + 1) * NU + i, (1 - fu) * fv);
    put((j + 1) * NU + i + 1, fu * fv);
    this.volume += volume;
    this.settled = false;
    return volume;
  }

  // Once the rear is open, the sand tipped behind the truck holds the load in as
  // high as it stands over the floor's edge. Only needed once a tick.
  propBy(frame, terrain, open) {
    const props = this.props;
    if (!open) {
      if (props.some((value) => value > 0)) {
        props.fill(0);
        this.settled = false;
      }
      return;
    }
    const point = this.point,
      { ex, ez } = frame,
      level = Math.hypot(ex[0], ex[1]) || 1,
      backX = (-ex[0] / level) * BEHIND,
      backY = (-ex[1] / level) * BEHIND,
      // Columns stand along the body's z: a height in the world is this much longer
      // along it.
      along = 1 / Math.max(ez[2], 0.3);
    for (let j = 0; j < NV; j++) {
      frame.toWorld(0, TRUCK_LOAD.rowY(j), 0, point);
      const bed = terrain.surface(terrain.cellAt(point[0] + backX, point[1] + backY)),
        prop = Math.max(0, (bed - point[2]) * along);
      if (Math.abs(prop - props[j]) >= SAME) {
        props[j] = prop;
        this.settled = false;
      }
    }
  }

  // The slopes the sand may take at the body's present tilt. Returns false when
  // nothing has changed for a settled load.
  fit(frame, gap) {
    const theta = Math.atan2(frame.ex[2], frame.ez[2]),
      lean = Math.atan2(frame.ey[2], frame.ez[2]),
      tilt = this.tilt;
    if (
      !(Math.abs(theta - tilt[0]) < 1e-6 && Math.abs(lean - tilt[1]) < 1e-6) ||
      gap !== this.gap
    ) {
      tilt[0] = theta;
      tilt[1] = lean;
      this.gap = gap;
      this.settled = false;
    }
    if (this.settled) return false;
    slopeLimits(HOLD, theta, this.holdU);
    slopeLimits(SLIDE, theta, this.slideU);
    slopeLimits(HOLD, lean, this.holdY);
    slopeLimits(SLIDE, lean, this.slideY);
    return true;
  }

  // Sand moves between neighbours, b on the positive side of a: at rest it lets go
  // only past what it holds; once moving it slides until the slope is the one
  // sliding sand stops at.
  exchange(a, b, spacing, hold, slide) {
    const t = this.thickness,
      mobile = this.mobile,
      difference = t[b] - t[a];
    let move = 0;
    if (difference > (mobile[a] ? slide[0] : hold[0]) * spacing + SETTLED)
      move = Math.min(t[b], (difference - slide[0] * spacing) / 2);
    else if (difference < (mobile[b] ? slide[1] : hold[1]) * spacing - SETTLED)
      move = -Math.min(t[a], (slide[1] * spacing - difference) / 2);
    if (!(Math.abs(move) > 0)) return 0;
    t[a] += move;
    t[b] -= move;
    if (Math.abs(move) > MOVING) mobile[a] = mobile[b] = MOBILE;
    return Math.abs(move);
  }

  // A column beside a rim may stand above the rim only as far as its slope allows;
  // what stands higher leaves, at a limited rate.
  spill(rim, index, c, holdAt, slideAt, rate) {
    const t = this.thickness,
      top = t[c];
    if (top - (this.mobile[c] ? slideAt : holdAt) <= SETTLED) return 0;
    const move = Math.min(top - slideAt, top, rate);
    if (!(move > 0)) return 0;
    t[c] -= move;
    this.pending[rim][index] += move * AREA;
    this.flowing[rim][index] = 1;
    if (move > MOVING) this.mobile[c] = MOBILE;
    return move;
  }

  // One pass of slumping and spilling. `gap` is how far the rear wall stands open
  // at its foot (mm), 0 while it is latched.
  relax(frame, gap) {
    for (const flowing of this.flowing) flowing.fill(0);
    if (!this.fit(frame, gap)) return;
    const { holdU, holdY, slideU, slideY } = this;
    let moved = 0;
    // Each pass reverses the order of the moves, and those across the body run in
    // mirror image from its middle, so the sand has no favourite side.
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
          right = i + (pairs - 1 - out) * NU,
          left = i + (pairs + out) * NU;
        moved += forward
          ? this.exchange(right, right + NU, DV, holdY, slideY) +
            this.exchange(left, left + NU, DV, holdY, slideY)
          : this.exchange(left, left + NU, DV, holdY, slideY) +
            this.exchange(right, right + NU, DV, holdY, slideY);
      }
    // The rear: over the latched wall, or out at the floor under the open one, as
    // fast as its gap allows and only above the sand already tipped behind.
    const open = gap > 0,
      rearRate = open ? SPILL_RATE * Math.min(1, gap / FULL_GAP) : SPILL_RATE;
    for (let j = 0; j < NV; j++) {
      const rim = Math.max(open ? 0 : TRUCK.rearWall, this.props[j]);
      moved += this.spill(
        RIM_REAR,
        j,
        j * NU,
        rim + (holdU[0] * DU) / 2,
        rim + (slideU[0] * DU) / 2,
        rearRate,
      );
      moved += this.spill(
        RIM_FRONT,
        j,
        j * NU + NU - 1,
        TRUCK.frontWall - (holdU[1] * DU) / 2,
        TRUCK.frontWall - (slideU[1] * DU) / 2,
        SPILL_RATE,
      );
    }
    for (let i = 0; i < NU; i++) {
      moved += this.spill(
        RIM_RIGHT,
        i,
        i,
        TRUCK.sideWall + (holdY[0] * DV) / 2,
        TRUCK.sideWall + (slideY[0] * DV) / 2,
        SPILL_RATE,
      );
      moved += this.spill(
        RIM_LEFT,
        i,
        (NV - 1) * NU + i,
        TRUCK.sideWall - (holdY[1] * DV) / 2,
        TRUCK.sideWall - (slideY[1] * DV) / 2,
        SPILL_RATE,
      );
    }
    this.settled = moved < SETTLED;
    const mobile = this.mobile;
    for (let c = 0; c < CELLS; c++)
      if (mobile[c]) mobile[c] = this.settled ? 0 : mobile[c] - 1;
    // Counted afresh, so that rounding in the moves cannot build up.
    let thickness = 0;
    for (let c = 0; c < CELLS; c++) thickness += this.thickness[c];
    this.volume = thickness * AREA;
  }

  // Thickness of every column for the network, or null for an empty body.
  pack() {
    if (this.volume <= 1) return null;
    const out = new Uint16Array(CELLS),
      q = 1 / TRUCK_LOAD.quantum;
    for (let c = 0; c < CELLS; c++)
      out[c] = Math.min(65535, Math.round(this.thickness[c] * q));
    return out;
  }
}

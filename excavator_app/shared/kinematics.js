// Generated R12 table solver; shared by physics and rendering.
import { CONFIG } from './config.js';
const C = CONFIG.arm;
const STEP = C.pitch;
const ROWS = { boom: C.tables.boom.rows, stick: C.tables.stick.rows, bucket: C.tables.bucket.rows };
const BODIES = C.tables.bucket.bodies;
const BUCKET_AT = 3 * BODIES.indexOf('bucket');
const PINS = Object.entries(C.pins).map(([name, local]) => ({ name, body: C.pin_body[name], x: local[0], z: local[1] }));
const DRIVES = C.drives.map((drive) => ({ a: drive.a, b: drive.b, barrel: drive.name + '_barrel', rod: drive.name + '_rod' }));
const CLOSED = C.closed[0];
// The table row below a stroke, leaving the way towards the next row in `frac`.
let frac = 0;
const rowAt = (rows, stroke) => {
  const x = Math.min(Math.max(stroke / STEP, 0), rows.length - 1.000001), i = Math.floor(x);
  frac = x - i;
  return i;
};
const value = (rows, i, j) => rows[i][j] + (rows[i + 1][j] - rows[i][j]) * frac;
const compose = (p, rx, rz, ra) => {
  const c = Math.cos(p[2]), s = Math.sin(p[2]);
  return [p[0] + c * rx - s * rz, p[1] + s * rx + c * rz, p[2] + ra];
};
// The bucket's pose on the arm, [x, z, turn] into `out`: what the physics asks for
// many times a tick, with nothing allocated.
function bucketBody(strokes, out) {
  const bi = rowAt(ROWS.boom, strokes[0]), bx = value(ROWS.boom, bi, 0), bz = value(ROWS.boom, bi, 1), ba = value(ROWS.boom, bi, 2);
  const si = rowAt(ROWS.stick, strokes[1]), sx = value(ROWS.stick, si, 0), sz = value(ROWS.stick, si, 1), sa = value(ROWS.stick, si, 2);
  const cb = Math.cos(ba), sb = Math.sin(ba);
  const px = bx + cb * sx - sb * sz, pz = bz + sb * sx + cb * sz, pa = ba + sa;
  const ki = rowAt(ROWS.bucket, strokes[2]), kx = value(ROWS.bucket, ki, BUCKET_AT), kz = value(ROWS.bucket, ki, BUCKET_AT + 1), ka = value(ROWS.bucket, ki, BUCKET_AT + 2);
  const cp = Math.cos(pa), sp = Math.sin(pa);
  out[0] = px + cp * kx - sp * kz;
  out[1] = pz + sp * kx + cp * kz;
  out[2] = pa + ka;
  return out;
}
// Every body, pin and drive: what the renderer draws from.
function solve(strokes) {
  const P = { base: [0, 0, 0] };
  const bi = rowAt(ROWS.boom, strokes[0]);
  P.boom = [value(ROWS.boom, bi, 0), value(ROWS.boom, bi, 1), value(ROWS.boom, bi, 2)];
  const si = rowAt(ROWS.stick, strokes[1]);
  P.stick = compose(P.boom, value(ROWS.stick, si, 0), value(ROWS.stick, si, 1), value(ROWS.stick, si, 2));
  const ki = rowAt(ROWS.bucket, strokes[2]), f = frac;
  for (let n = 0; n < BODIES.length; n++) {
    frac = f;
    P[BODIES[n]] = compose(P.stick, value(ROWS.bucket, ki, 3 * n), value(ROWS.bucket, ki, 3 * n + 1), value(ROWS.bucket, ki, 3 * n + 2));
  }
  const W = {};
  for (let n = 0; n < PINS.length; n++) {
    const pin = PINS[n], p = P[pin.body], c = Math.cos(p[2]), s = Math.sin(p[2]);
    W[pin.name] = [p[0] + c * pin.x - s * pin.z, p[1] + s * pin.x + c * pin.z, p[2]];
  }
  for (let n = 0; n < DRIVES.length; n++) {
    const drive = DRIVES[n], a = W[drive.a], b = W[drive.b];
    const ax = b[0] - a[0], az = b[1] - a[1];
    const length = Math.hypot(ax, az), k = (length - CLOSED) / length;
    const angle = Math.atan2(az, ax);
    P[drive.barrel] = [a[0], a[1], angle];
    P[drive.rod] = [a[0] + k * ax, a[1] + k * az, angle];
  }
  const rocker = P.side_link ?? P.bucket, coupler = P.h_link ?? P.bucket;
  return {
    P, W,
    p: W,
    origins: {
      base: [P.base[0], P.base[1]],
      boom: [P.boom[0], P.boom[1]],
      stick: [P.stick[0], P.stick[1]],
      bucket: [P.bucket[0], P.bucket[1]],
      rocker: [rocker[0], rocker[1]],
      coupler: [coupler[0], coupler[1]],
    },
    angles: {
      base: 0,
      boom: P.boom[2],
      stick: P.stick[2],
      bucket: P.bucket[2],
      rocker: rocker[2],
      coupler: coupler[2],
    },
  };
}
export { solve, bucketBody };

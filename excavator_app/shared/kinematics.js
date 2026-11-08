// Generated R12 table solver; shared by physics and rendering.
import { CONFIG } from './config.js';
const C = CONFIG.arm;
const STEP = C.pitch;
const compose = (p, r) => {
  const c = Math.cos(p[2]), s = Math.sin(p[2]);
  return [p[0] + c * r[0] - s * r[1], p[1] + s * r[0] + c * r[1], p[2] + r[2]];
};
const look = (key, stroke) => {
  const rows = C.tables[key].rows;
  const x = Math.min(Math.max(stroke / STEP, 0), rows.length - 1.000001);
  const i = Math.floor(x), f = x - i, a = rows[i], b = rows[i + 1];
  return a.map((v, j) => v + (b[j] - v) * f);
};
const pinsOf = (P) => {
  const W = {};
  for (const [name, local] of Object.entries(C.pins))
    W[name] = compose(P[C.pin_body[name]], [local[0], local[1], 0]);
  return W;
};
function solve(strokes) {
  const P = { base: [0, 0, 0] };
  P.boom = compose(P.base, look('boom', strokes[0]));
  P.stick = compose(P.boom, look('stick', strokes[1]));
  const bucket = look('bucket', strokes[2]);
  C.tables.bucket.bodies.forEach((body, i) => {
    P[body] = compose(P.stick, bucket.slice(3 * i, 3 * i + 3));
  });
  const W = pinsOf(P);
  for (const drive of C.drives) {
    const ax = W[drive.b][0] - W[drive.a][0];
    const az = W[drive.b][1] - W[drive.a][1];
    const length = Math.hypot(ax, az), k = (length - C.closed[0]) / length;
    const angle = Math.atan2(az, ax);
    P[drive.name + '_barrel'] = [W[drive.a][0], W[drive.a][1], angle];
    P[drive.name + '_rod'] = [W[drive.a][0] + k * ax, W[drive.a][1] + k * az, angle];
  }
  return {
    P, W,
    p: W,
    origins: {
      base: [P.base[0], P.base[1]],
      boom: [P.boom[0], P.boom[1]],
      stick: [P.stick[0], P.stick[1]],
      bucket: [P.bucket[0], P.bucket[1]],
      rocker: [P.side_link?.[0] ?? P.bucket[0], P.side_link?.[1] ?? P.bucket[1]],
      coupler: [P.h_link?.[0] ?? P.bucket[0], P.h_link?.[1] ?? P.bucket[1]],
    },
    angles: {
      base: 0,
      boom: P.boom[2],
      stick: P.stick[2],
      bucket: P.bucket[2],
      rocker: P.side_link?.[2] ?? P.bucket[2],
      coupler: P.h_link?.[2] ?? P.bucket[2],
    },
  };
}
export { solve };

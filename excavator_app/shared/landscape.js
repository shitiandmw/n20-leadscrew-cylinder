import { WORLD, YARD, clamp } from "./world.js";

// The open world's hard ground and everything standing on it. It is built once
// from fixed numbers with no trigonometry in any decision, so the server's
// collisions and the browser's scenery always describe the same place.
const GRID = 160;
const N = (WORLD.maxX - WORLD.minX) / GRID;
export const GROUND = Object.freeze({ spacing: GRID, quads: N, side: N + 1 });
export const WATER = Object.freeze({
  level: -150,
  x: -600,
  y: 13200,
  radius: 3600,
});

const smoothstep = (a, b, x) => {
  const t = clamp((x - a) / (b - a), 0, 1);
  return t * t * (3 - 2 * t);
};
const mix = (a, b, t) => a + (b - a) * t;

function hash(i, j) {
  let n = Math.imul(i, 374761393) ^ Math.imul(j, 668265263);
  n = Math.imul(n ^ (n >>> 13), 1274126177);
  return ((n ^ (n >>> 16)) >>> 0) / 4294967296;
}
// Deterministic value noise in -0.5..0.5.
export function noise(x, y) {
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

// Signed distance to an axis-aligned box: negative inside.
function boxDistance(x, y, minX, maxX, minY, maxY) {
  const dx = Math.max(minX - x, x - maxX),
    dy = Math.max(minY - y, y - maxY);
  return dx > 0 || dy > 0
    ? Math.hypot(Math.max(dx, 0), Math.max(dy, 0))
    : Math.max(dx, dy);
}

// Millimetres inside the sand yard; zero or negative outside it.
export function yardInside(x, y) {
  const outer = boxDistance(x, y, YARD.minX, YARD.maxX, YARD.minY, YARD.maxY),
    notch = boxDistance(x, y, -1e6, YARD.notchMaxX, YARD.notchMinY, 1e6);
  return -Math.max(outer, -notch);
}

// Roads: centrelines in mm, as a loop around the valley with spurs.
export const ROADS = [
  [
    [-900, -60],
    [-2600, -120],
    [-4400, 300],
    [-6000, 200],
  ],
  [
    [-6000, 200],
    [-6800, 3000],
    [-5600, 6200],
    [-3000, 8600],
    [0, 9300],
    [4000, 8900],
    [8000, 7600],
    [10800, 4800],
  ],
  [
    [10800, 4800],
    [11600, 1000],
    [11200, -2600],
    [9600, -6200],
    [6000, -8600],
  ],
  [
    [6000, -8600],
    [1800, -9800],
    [-2600, -9200],
    [-5200, -6200],
    [-6400, -2800],
    [-6000, 200],
  ],
  [
    [-5200, -6200],
    [-8600, -8000],
    [-11600, -10400],
  ],
  [
    [-6000, 200],
    [-9000, 800],
    [-12000, 2400],
  ],
  [
    [6750, 0],
    [9000, 300],
    [11400, 200],
  ],
];
const ROAD_HALF_WIDTH = 170;
const ROAD_BLEND = 460;

// Smooth a polyline with Catmull-Rom segments, sampled about every 300 mm.
function roadPoints(points) {
  const out = [];
  for (let k = 0; k + 1 < points.length; k++) {
    const p0 = points[Math.max(0, k - 1)],
      p1 = points[k],
      p2 = points[k + 1],
      p3 = points[Math.min(points.length - 1, k + 2)],
      steps = Math.max(
        2,
        Math.round(Math.hypot(p2[0] - p1[0], p2[1] - p1[1]) / 300),
      );
    for (let s = 0; s < steps; s++) {
      const t = s / steps,
        t2 = t * t,
        t3 = t2 * t,
        at = (d) =>
          0.5 *
          (2 * p1[d] +
            (p2[d] - p0[d]) * t +
            (2 * p0[d] - 5 * p1[d] + 4 * p2[d] - p3[d]) * t2 +
            (3 * p1[d] - p0[d] - 3 * p2[d] + p3[d]) * t3);
      out.push([at(0), at(1)]);
    }
  }
  out.push(points[points.length - 1]);
  return out;
}

// Levelled places for buildings, as [x, y, radius].
const PADS = [
  [-12500, 2900, 1700],
  [-12200, -11000, 2100],
  [11900, 200, 1200],
  [4200, 11100, 700],
];

function rawHeight(x, y) {
  // Rolling hills that fade out around the flat work site.
  const site = boxDistance(x, y, -2300, 7500, -4300, 4300);
  let h =
    150 +
    1150 * noise(x / 9000 + 7.1, y / 9000 + 3.3) +
    320 * noise(x / 3300 + 1.7, y / 3300 + 9.2) +
    70 * noise(x / 1250 + 4.4, y / 1250 + 2.6);
  // Low ground flattens into a valley floor, always above the lake's level.
  if (h < 0) h *= 0.3;
  h *= smoothstep(0, 3200, site);
  // The lake basin.
  const shore =
    Math.hypot((x - WATER.x) / 1.25, y - WATER.y) +
    300 * noise(x / 2400 + 3.3, y / 2400 + 8.1);
  // Gentle enough everywhere for sand to rest on its banks.
  h = mix(h, -560, smoothstep(WATER.radius, WATER.radius * 0.38, shore));
  // A ridge of hills encloses the rounded valley; its steep face stops the
  // machine. The noise keeps its foot from reading as a drawn circle.
  const edge =
      Math.sqrt(Math.sqrt(x ** 4 + y ** 4)) +
      1500 * noise(x / 4300 + 2.9, y / 4300 + 7.7),
    ridge = smoothstep(16000, 19800, edge);
  return h + ridge * (2500 + 900 * noise(x / 2700 + 6.2, y / 2700 + 1.4));
}

let built;
function build() {
  if (built) return built;
  const S = N + 1,
    heights = new Float32Array(S * S),
    roadWeight = new Float32Array(S * S);
  const vertexX = (i) => WORLD.minX + i * GRID,
    vertexY = (j) => WORLD.minY + j * GRID;
  for (let j = 0; j < S; j++)
    for (let i = 0; i < S; i++)
      heights[j * S + i] = rawHeight(vertexX(i), vertexY(j));
  // Level the building pads.
  for (const [px, py, radius] of PADS) {
    const level = rawHeight(px, py);
    forVertices(px, py, radius * 1.7, (c, x, y) => {
      const t = smoothstep(radius * 1.7, radius, Math.hypot(x - px, y - py));
      heights[c] = mix(heights[c], level, t);
    });
  }
  // Cut the roads along a smoothed height profile.
  const paths = ROADS.map(roadPoints);
  const sampleGrid = (x, y) => {
    const i = clamp(Math.round((x - WORLD.minX) / GRID), 0, N),
      j = clamp(Math.round((y - WORLD.minY) / GRID), 0, N);
    return heights[j * S + i];
  };
  const blended = new Map();
  for (const path of paths) {
    const profile = path.map(([x, y]) => sampleGrid(x, y));
    for (let pass = 0; pass < 6; pass++)
      for (let k = 1; k + 1 < profile.length; k++)
        profile[k] = (profile[k - 1] + 2 * profile[k] + profile[k + 1]) / 4;
    const reach = ROAD_HALF_WIDTH + ROAD_BLEND;
    for (let k = 0; k + 1 < path.length; k++) {
      const [ax, ay] = path[k],
        [bx, by] = path[k + 1],
        dx = bx - ax,
        dy = by - ay,
        len2 = dx * dx + dy * dy;
      forVertices(
        (ax + bx) / 2,
        (ay + by) / 2,
        Math.sqrt(len2) / 2 + reach,
        (c, x, y) => {
          const t = clamp(((x - ax) * dx + (y - ay) * dy) / len2, 0, 1),
            d = Math.hypot(x - ax - dx * t, y - ay - dy * t),
            weight = smoothstep(reach, ROAD_HALF_WIDTH, d);
          if (weight > (blended.get(c)?.weight ?? 0))
            blended.set(c, {
              weight,
              level: mix(profile[k], profile[k + 1], t),
            });
        },
      );
    }
  }
  for (const [c, { weight, level }] of blended) {
    heights[c] = mix(heights[c], level, weight);
    roadWeight[c] = weight;
  }
  // The hard floor of the sand yard, which sits under deep sand.
  forVertices(
    (YARD.minX + YARD.maxX) / 2,
    (YARD.minY + YARD.maxY) / 2,
    Math.hypot(YARD.maxX - YARD.minX, YARD.maxY - YARD.minY) / 2 + GRID,
    (c, x, y) => {
      heights[c] -= YARD.depth * smoothstep(0, YARD.ramp, yardInside(x, y));
    },
  );
  function forVertices(cx, cy, radius, visit) {
    const i0 = clamp(Math.floor((cx - radius - WORLD.minX) / GRID), 0, N),
      i1 = clamp(Math.ceil((cx + radius - WORLD.minX) / GRID), 0, N),
      j0 = clamp(Math.floor((cy - radius - WORLD.minY) / GRID), 0, N),
      j1 = clamp(Math.ceil((cy + radius - WORLD.minY) / GRID), 0, N);
    for (let j = j0; j <= j1; j++)
      for (let i = i0; i <= i1; i++)
        visit(j * S + i, vertexX(i), vertexY(j));
  }
  built = { heights, roadWeight, paths };
  built.props = placeProps(built);
  built.colliders = collidersOf(built.props);
  return built;
}

// Height of the hard ground, on the same triangles the browser draws.
export function groundHeight(x, y) {
  const { heights } = built ?? build(),
    S = N + 1,
    u = clamp((x - WORLD.minX) / GRID, 0, N - 1e-6),
    v = clamp((y - WORLD.minY) / GRID, 0, N - 1e-6),
    i = Math.floor(u),
    j = Math.floor(v),
    fu = u - i,
    fv = v - j,
    c = j * S + i,
    h00 = heights[c],
    h11 = heights[c + S + 1];
  return fu >= fv
    ? h00 + fu * (heights[c + 1] - h00) + fv * (h11 - heights[c + 1])
    : h00 + fv * (heights[c + S] - h00) + fu * (h11 - heights[c + S]);
}

// Writes [height, dz/dx, dz/dy] of the hard ground to out.
export function groundSample(x, y, out) {
  const { heights } = built ?? build(),
    S = N + 1,
    u = clamp((x - WORLD.minX) / GRID, 0, N - 1e-6),
    v = clamp((y - WORLD.minY) / GRID, 0, N - 1e-6),
    i = Math.floor(u),
    j = Math.floor(v),
    fu = u - i,
    fv = v - j,
    c = j * S + i,
    h00 = heights[c],
    h11 = heights[c + S + 1];
  if (fu >= fv) {
    const h10 = heights[c + 1];
    out[0] = h00 + fu * (h10 - h00) + fv * (h11 - h10);
    out[1] = (h10 - h00) / GRID;
    out[2] = (h11 - h10) / GRID;
  } else {
    const h01 = heights[c + S];
    out[0] = h00 + fv * (h01 - h00) + fu * (h11 - h01);
    out[1] = (h11 - h01) / GRID;
    out[2] = (h01 - h00) / GRID;
  }
  return out;
}

export const landscape = () => built ?? build();

// Stockpiles on the level sand, dumped below the angle of repose and clear of
// the pad. `top` flattens a pile's crown.
const STOCKPILES = [
  { x: 720, y: -320, rx: 340, ry: 300, top: 110 },
  { x: 2600, y: -1500, rx: 1120, ry: 1050, top: 560 },
  { x: 4300, y: 1450, rx: 1750, ry: 560, top: 270 },
  { x: 5350, y: -1250, rx: 780, ry: 760, top: 370 },
  { x: 1800, y: 1800, rx: 640, ry: 620, top: 300 },
  { x: 3950, y: -2500, rx: 420, ry: 400, top: 190 },
  { x: 1500, y: 2750, rx: 380, ry: 360, top: 170 },
];
const PILE_SLOPE = 0.5; // about 27 degrees
function pileHeight(x, y) {
  let height = 0;
  for (const pile of STOCKPILES) {
    const r = Math.hypot((x - pile.x) / pile.rx, (y - pile.y) / pile.ry),
      edge = (1 - r) * Math.min(pile.rx, pile.ry);
    height = Math.max(height, Math.min(pile.top, edge * PILE_SLOPE));
  }
  return height;
}

// A narrow sand beach on the lake's south shore, to find while exploring.
export const BEACH = Object.freeze({
  minX: -2600,
  maxX: 1500,
  minY: 9700,
  maxY: 10500,
});

// Sand thickness the world starts with at (x, y), in mm.
export function initialSand(x, y) {
  const inside = yardInside(x, y);
  if (inside > 0) {
    const dunes =
      smoothstep(0, 500, inside) *
      (32 * noise(x / 900 + 3.1, y / 900 + 5.7) +
        9 * noise(x / 240 + 8.3, y / 240 + 1.9));
    let piles = pileHeight(x, y);
    if (piles > 0)
      piles = Math.max(
        0,
        piles +
          Math.min(1, piles / 14) *
            (5 * noise(x / 61, y / 61) + 1.2 * noise(x / 21, y / 21)),
      );
    return Math.max(0, dunes + piles - groundHeight(x, y));
  }
  const beach = -boxDistance(
    x,
    y,
    BEACH.minX,
    BEACH.maxX,
    BEACH.minY,
    BEACH.maxY,
  );
  if (beach > 0)
    return (
      smoothstep(0, 340, beach) *
      (46 + 40 * noise(x / 700 + 2.2, y / 700 + 4.6))
    );
  return 0;
}

// ---------------------------------------------------------------- scenery
// `kind` picks the model the browser draws. Size is in mm.
function placeProps({ roadWeight }) {
  const props = [];
  const add = (kind, x, y, rot = 0, size = 1) =>
    props.push({ kind, x, y, rot, size });
  // The work site beside the sand yard.
  add("office", -820, -1020, 0);
  add("container", -1520, -930, 0, 0);
  add("container", -1520, -1240, 0, 1);
  add("container", -1860, -930, 0, 2);
  add("shed", -1560, 1120, 0);
  add("fueltank", -760, 1120, 0);
  add("truck", -240, 1320, 0);
  add("sign", 40, -640, 1.5708);
  add("lighttower", -520, -1500, 0);
  add("lighttower", 6720, 3360, 0);
  add("lighttower", 6720, -3360, 0);
  add("lighttower", 340, -3380, 0);
  add("barrier", 96, 620, 1.5708);
  add("barrier", 96, 910, 1.5708);
  for (const [x, y] of [
    [230, 190],
    [650, 190],
    [230, 520],
    [650, 520],
  ])
    add("cone", x, y);
  // Far from the yard: places to find along the roads.
  for (const [x, y, rot] of [
    [-13300, 3700, 0.5],
    [-12100, 3650, -0.3],
    [-11300, 3300, 0.9],
    [-13500, 2300, 0.1],
    [-12500, 1450, -0.7],
    [-11200, 1750, 0.3],
  ])
    add("house", x, y, rot);
  add("watertower", 4200, 11100, 0);
  add("barn", 12150, 860, 0.2);
  add("silo", 12500, -220, 0);
  add("silo", 12050, -420, 0);
  add("crusher", -12650, -11550, 0.6);
  add("pier", -1000, 11300, 0);
  add("turbine", 14200, -12200, 0);
  add("turbine", 12300, -13800, 0);
  add("turbine", -9500, 13400, 0);
  for (let k = 0; k < 9; k++) {
    const angle = k * 0.71,
      radius = 1050 + 170 * ((k * 5) % 7);
    add(
      "boulder",
      -12200 + radius * Math.cos(angle),
      -11000 + radius * Math.sin(angle),
      k,
      150 + 26 * ((k * 3) % 6),
    );
  }
  // Power poles march along the site road and the north arm.
  const poleRoute = [
    [-1100, -360],
    [-3400, -340],
    [-5700, -180],
    [-7300, 2700],
    [-6200, 5900],
    [-3600, 8050],
    [-200, 8800],
  ];
  for (const [x, y] of poleRoute) add("pole", x, y);
  // Trees and rocks: rejection-sampled, clear of roads, water and buildings.
  const S = N + 1,
    random = (() => {
      let seed = 1991;
      return () =>
        (seed = (1664525 * seed + 1013904223) >>> 0) / 4294967296;
    })(),
    standing = props.slice(),
    clearStanding = (x, y, margin) => {
      for (const p of standing)
        if (Math.hypot(p.x - x, p.y - y) < margin + extentOf(p)) return false;
      return true;
    };
  let trees = 0,
    rocks = 0;
  for (let k = 0; k < 16000 && (trees < 900 || rocks < 220); k++) {
    const x = WORLD.minX + random() * (WORLD.maxX - WORLD.minX),
      y = WORLD.minY + random() * (WORLD.maxY - WORLD.minY),
      kindRoll = random(),
      sizeRoll = random(),
      rotRoll = random();
    if (boxDistance(x, y, -2300, 7400, -4100, 4100) < 260) continue;
    const i = clamp(Math.round((x - WORLD.minX) / GRID), 0, N),
      j = clamp(Math.round((y - WORLD.minY) / GRID), 0, N);
    if (roadWeight[j * S + i] > 0.02) continue;
    const h = groundHeight(x, y);
    if (h < WATER.level + 60) continue;
    const dzx = groundHeight(x + 120, y) - groundHeight(x - 120, y),
      dzy = groundHeight(x, y + 120) - groundHeight(x, y - 120),
      slope = Math.hypot(dzx, dzy) / 240;
    if (slope > 0.75) continue;
    if (!clearStanding(x, y, 260)) continue;
    if (kindRoll < 0.2) {
      if (rocks >= 220) continue;
      rocks++;
      add("rock", x, y, rotRoll * 6.28, 34 + 90 * sizeRoll * sizeRoll);
      continue;
    }
    if (trees >= 900) continue;
    // Woods gather in patches.
    if (
      noise(x / 3400 + 2.4, y / 3400 + 7.7) +
        0.28 * noise(x / 900, y / 900) <
      -0.05 + 0.12 * kindRoll
    )
      continue;
    trees++;
    const pine = noise(x / 5200 + 9.1, y / 5200 + 0.6) > -0.02;
    add(
      pine ? "pine" : "broadleaf",
      x,
      y,
      rotRoll * 6.28,
      (pine ? 800 : 640) + 560 * sizeRoll,
    );
  }
  return props;
}

function extentOf(p) {
  return (
    {
      office: 420,
      container: 260,
      shed: 560,
      fueltank: 200,
      truck: 460,
      lighttower: 60,
      barrier: 150,
      house: 520,
      watertower: 330,
      barn: 640,
      silo: 200,
      crusher: 620,
      pier: 1100,
      turbine: 90,
    }[p.kind] ?? 40
  );
}

// Footprints the crawler cannot drive through: circles and rotated boxes.
function collidersOf(props) {
  const colliders = [];
  const circle = (x, y, r) => colliders.push({ x, y, r });
  const box = (p, hx, hy) =>
    colliders.push({
      x: p.x,
      y: p.y,
      hx,
      hy,
      c: Math.cos(p.rot),
      s: Math.sin(p.rot),
      r: Math.hypot(hx, hy),
    });
  for (const p of props) {
    if (p.kind === "office") box(p, 320, 125);
    else if (p.kind === "container") box(p, 200, 80);
    else if (p.kind === "shed") box(p, 400, 300);
    else if (p.kind === "fueltank") circle(p.x, p.y, 140);
    else if (p.kind === "truck") box(p, 400, 130);
    else if (p.kind === "barrier") box(p, 130, 24);
    else if (p.kind === "house") box(p, 330, 250);
    else if (p.kind === "barn") box(p, 500, 340);
    else if (p.kind === "crusher") box(p, 460, 300);
    else if (p.kind === "silo") circle(p.x, p.y, 140);
    else if (p.kind === "watertower") circle(p.x, p.y, 240);
    else if (p.kind === "turbine") circle(p.x, p.y, 60);
    else if (p.kind === "pier") box({ ...p, y: p.y - 100 }, 115, 860);
    else if (p.kind === "lighttower") circle(p.x, p.y, 34);
    else if (p.kind === "sign" || p.kind === "pole") circle(p.x, p.y, 12);
    else if (p.kind === "pine" || p.kind === "broadleaf")
      circle(p.x, p.y, 0.022 * p.size);
    else if (p.kind === "rock") circle(p.x, p.y, 0.72 * p.size);
    else if (p.kind === "boulder") circle(p.x, p.y, 0.8 * p.size);
  }
  return colliders;
}

// Does a crawler rectangle centred at (x, y) touch a collider? The rectangle
// is `halfLength` along the heading and `halfWidth` across it.
export function crawlerHitsProp(x, y, cosH, sinH, halfLength, halfWidth) {
  const { colliders } = built ?? build(),
    reach = Math.hypot(halfLength, halfWidth);
  for (const k of colliders) {
    const dx = k.x - x,
      dy = k.y - y;
    if (dx * dx + dy * dy > (reach + k.r) * (reach + k.r)) continue;
    const u = dx * cosH + dy * sinH,
      v = -dx * sinH + dy * cosH;
    if (k.hx === undefined) {
      const gu = Math.max(Math.abs(u) - halfLength, 0),
        gv = Math.max(Math.abs(v) - halfWidth, 0);
      if (gu * gu + gv * gv < k.r * k.r) return true;
      continue;
    }
    // Separating-axis test between the two rectangles.
    const cos = k.c * cosH + k.s * sinH,
      sin = k.s * cosH - k.c * sinH,
      ac = Math.abs(cos),
      as = Math.abs(sin);
    if (Math.abs(u) > halfLength + k.hx * ac + k.hy * as) continue;
    if (Math.abs(v) > halfWidth + k.hx * as + k.hy * ac) continue;
    const a = dx * k.c + dy * k.s,
      b = -dx * k.s + dy * k.c;
    if (Math.abs(a) > k.hx + halfLength * ac + halfWidth * as) continue;
    if (Math.abs(b) > k.hy + halfLength * as + halfWidth * ac) continue;
    return true;
  }
  return false;
}

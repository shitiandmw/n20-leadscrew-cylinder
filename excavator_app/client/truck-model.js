import * as THREE from "three";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { TRUCK as T, TYRES, gateAngle } from "../shared/truck.js";

// The dump truck as drawn: the Volvo FMX13 6x4 Day cab and chassis and the
// Schwarzmüller 3-way tipper body of shared/truck.js, at 1:15, in the truck's
// frame (x forward, y left, z up, origin on the ground under the rear tandem).
// The cab's outline is traced from the side and front views of Volvo's model range
// sheet; parts the sheet does not show (tanks, lamps, the body's stiffeners) are
// placed as on photographs of the type, and marked so below.
//
// Painted parts take the player's paint: the cab and the body's steel. The side
// walls are bare aluminium, as on the real body.

const COLOURS = {
  paint: "#ffffff",
  chassis: "#26292c",
  black: "#17181a",
  rubber: "#1c1d1f",
  grille: "#2d3135",
  bumper: "#3b3f43",
  silver: "#b7bbbf",
  alloy: "#c9cdd1",
  alloyLine: "#9a9fa4",
  lamp: "#eef3f6",
  amber: "#e4931c",
  red: "#a8221b",
  floor: "#8c7b66",
};

// Geometry pieces with a colour, a paint mask and a glass mask, merged into one
// mesh per moving part so that a truck costs a few draw calls.
class Parts {
  constructor() {
    this.list = [];
  }
  add(geometry, colour, painted = false, glass = false) {
    let g = geometry;
    if (g.index) {
      g = geometry.toNonIndexed();
      geometry.dispose();
    }
    for (const name of Object.keys(g.attributes))
      if (name !== "position" && name !== "normal") g.deleteAttribute(name);
    const count = g.attributes.position.count,
      colour3 = new THREE.Color(colour),
      colours = new Float32Array(count * 3);
    for (let n = 0; n < count; n++) colour3.toArray(colours, n * 3);
    g.setAttribute("color", new THREE.BufferAttribute(colours, 3));
    g.setAttribute(
      "paintMask",
      new THREE.BufferAttribute(new Float32Array(count).fill(painted ? 1 : 0), 1),
    );
    g.setAttribute(
      "glassMask",
      new THREE.BufferAttribute(new Float32Array(count).fill(glass ? 1 : 0), 1),
    );
    this.list.push(g);
    return g;
  }
  // A box from (x0, y0, z0) to (x1, y1, z1).
  box(x0, x1, y0, y1, z0, z1, colour, painted = false) {
    return this.add(
      new THREE.BoxGeometry(x1 - x0, y1 - y0, z1 - z0).translate(
        (x0 + x1) / 2,
        (y0 + y1) / 2,
        (z0 + z1) / 2,
      ),
      colour,
      painted,
    );
  }
  rounded(x0, x1, y0, y1, z0, z1, radius, colour, painted = false) {
    return this.add(
      new RoundedBoxGeometry(x1 - x0, y1 - y0, z1 - z0, 2, radius).translate(
        (x0 + x1) / 2,
        (y0 + y1) / 2,
        (z0 + z1) / 2,
      ),
      colour,
      painted,
    );
  }
  // A round bar from a to b.
  bar(a, b, radius, colour, segments = 10, painted = false) {
    const from = new THREE.Vector3(...a),
      to = new THREE.Vector3(...b),
      length = from.distanceTo(to),
      g = new THREE.CylinderGeometry(radius, radius, length, segments);
    g.applyQuaternion(
      new THREE.Quaternion().setFromUnitVectors(
        new THREE.Vector3(0, 1, 0),
        to.clone().sub(from).normalize(),
      ),
    );
    g.translate((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2);
    return this.add(g, colour, painted);
  }
  // A flat convex polygon through the points, facing the side they wind round
  // anticlockwise.
  polygon(points, colour, painted = false, glass = false) {
    const g = new THREE.BufferGeometry(),
      flat = [];
    for (let k = 1; k + 1 < points.length; k++)
      flat.push(...points[0], ...points[k], ...points[k + 1]);
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(flat), 3));
    g.computeVertexNormals();
    return this.add(g, colour, painted, glass);
  }
  merge() {
    const merged = mergeGeometries(this.list);
    for (const g of this.list) g.dispose();
    this.list = [];
    merged.computeBoundingSphere();
    return merged;
  }
}

// --------------------------------------------------------------------- the cab
// Side outline of the Day cab over the frame, traced from the sheet's side view
// at 0.4057 mm (1:15) per pixel of its 400 dpi rendering: back of cab 515 mm
// behind the front axle, roof 3144 mm, a windscreen leaning back about 10
// degrees, the grille face 1340 mm ahead of the front axle.
const CAB_PROFILE = [
  ["move", 258, 84],
  ["line", 334, 70],
  ["line", 382.5, 70],
  ["line", 382.5, 126],
  ["curve", 382.5, 131.5, 381.5, 134],
  ["line", 370.5, 194.5],
  ["curve", 369.2, 200.6, 363, 202],
  ["line", 345, 209.6],
  ["line", 266, 209.6],
  ["curve", 258, 209.6, 258, 201.6],
];
const CAB_EDGE = 5;
// Seen from the front the cab narrows towards the roof: 2500 mm at the door
// handles, about 2140 mm over the roof. The sides are upright up to the waist and
// lean in above it.
const WAIST = 120;
const cabTaper = (z) => 1 - 0.14 * Math.min(1, Math.max(0, (z - WAIST) / 90));
const cabHalfWidth = (z) => T.cabHalfWidth * cabTaper(z);
const windscreenX = (z) => 381.5 - ((z - 134) * 11) / 60.5;

// Cut every triangle that crosses the waist into pieces that do not, so that the
// taper, which bends there, keeps the flat sides flat (an uncut side triangle
// reaching from the floor to the roof would stand up to 3 mm proud).
function cutAtWaist(geometry) {
  const position = geometry.attributes.position,
    normal = geometry.attributes.normal,
    points = [],
    normals = [],
    vertex = (n) => [
      position.getX(n),
      position.getY(n),
      position.getZ(n),
      normal.getX(n),
      normal.getY(n),
      normal.getZ(n),
    ],
    emit = (v) => {
      points.push(v[0], v[1], v[2]);
      normals.push(v[3], v[4], v[5]);
    };
  for (let n = 0; n < position.count; n += 3) {
    const triangle = [vertex(n), vertex(n + 1), vertex(n + 2)],
      heights = triangle.map((v) => v[2]);
    if (Math.max(...heights) <= WAIST || Math.min(...heights) >= WAIST) {
      triangle.forEach(emit);
      continue;
    }
    for (const keep of [(z) => z <= WAIST, (z) => z >= WAIST]) {
      const piece = [];
      triangle.forEach((a, k) => {
        const b = triangle[(k + 1) % 3];
        if (keep(a[2])) piece.push(a);
        if ((a[2] - WAIST) * (b[2] - WAIST) < 0) {
          const t = (WAIST - a[2]) / (b[2] - a[2]);
          piece.push(a.map((value, i) => value + t * (b[i] - value)));
        }
      });
      for (let k = 1; k + 1 < piece.length; k++)
        [piece[0], piece[k], piece[k + 1]].forEach(emit);
    }
  }
  const cut = new THREE.BufferGeometry();
  cut.setAttribute("position", new THREE.Float32BufferAttribute(points, 3));
  cut.setAttribute("normal", new THREE.Float32BufferAttribute(normals, 3));
  geometry.dispose();
  return cut;
}

function cabShell() {
  const shape = new THREE.Shape();
  for (const [kind, ...p] of CAB_PROFILE) {
    if (kind === "move") shape.moveTo(p[0], p[1]);
    else if (kind === "line") shape.lineTo(p[0], p[1]);
    else shape.quadraticCurveTo(p[0], p[1], p[2], p[3]);
  }
  shape.closePath();
  const depth = 2 * T.cabHalfWidth - 2 * CAB_EDGE,
    g = new THREE.ExtrudeGeometry(shape, {
      depth,
      bevelEnabled: true,
      bevelThickness: CAB_EDGE,
      bevelSize: CAB_EDGE,
      bevelOffset: -CAB_EDGE,
      bevelSegments: 3,
      curveSegments: 6,
    });
  // Shape x, y and depth become the truck's x, z and -y; centred across.
  g.rotateX(Math.PI / 2);
  g.translate(0, depth / 2, 0);
  const cut = cutAtWaist(g);
  // Narrow the upper cab, carrying the normals with the stretch; each triangle
  // lies wholly above or below the waist.
  const position = cut.attributes.position,
    normal = cut.attributes.normal;
  for (let n = 0; n < position.count; n++) {
    const first = n - (n % 3),
      middle =
        (position.getZ(first) + position.getZ(first + 1) + position.getZ(first + 2)) / 3,
      y = position.getY(n),
      z = position.getZ(n),
      s = cabTaper(z),
      slope = middle > WAIST && middle < WAIST + 90 ? -0.14 / 90 : 0,
      nx = normal.getX(n),
      ny = normal.getY(n) / s,
      nz = normal.getZ(n) - (y * slope * normal.getY(n)) / s,
      length = Math.hypot(nx, ny, nz) || 1;
    normal.setXYZ(n, nx / length, ny / length, nz / length);
  }
  for (let n = 0; n < position.count; n++)
    position.setY(n, position.getY(n) * cabTaper(position.getZ(n)));
  return cut;
}

// Flat pieces on both cab sides (windows, seams, the handle recesses), outlined
// anticlockwise in (x, z), just proud of the side. Cut at the waist so that each
// piece lies flat on the part of the side it covers.
function onCabSides(p, outline, colour, glass = false) {
  for (const keep of [(z) => z <= WAIST, (z) => z >= WAIST]) {
    const piece = [];
    outline.forEach((a, k) => {
      const b = outline[(k + 1) % outline.length];
      if (keep(a[1])) piece.push(a);
      if ((a[1] - WAIST) * (b[1] - WAIST) < 0) {
        const t = (WAIST - a[1]) / (b[1] - a[1]);
        piece.push([a[0] + t * (b[0] - a[0]), WAIST]);
      }
    });
    if (piece.length < 3) continue;
    for (const side of [-1, 1]) {
      // Seen from the left, x runs the other way: wind the other way round.
      const points = piece.map(([x, z]) => [x, side * (cabHalfWidth(z) + 0.3), z]);
      p.polygon(side > 0 ? points.reverse() : points, colour, false, glass);
    }
  }
}

// A seam line on both sides, 0.8 mm wide, from a to b in (x, z).
function cabSeam(p, a, b) {
  const length = Math.hypot(b[0] - a[0], b[1] - a[1]),
    nx = (-(b[1] - a[1]) / length) * 0.4,
    nz = ((b[0] - a[0]) / length) * 0.4;
  onCabSides(
    p,
    [
      [a[0] - nx, a[1] - nz],
      [b[0] - nx, b[1] - nz],
      [b[0] + nx, b[1] + nz],
      [a[0] + nx, a[1] + nz],
    ],
    COLOURS.black,
  );
}

function buildFrame() {
  const p = new Parts(),
    c = COLOURS;
  p.add(cabShell(), c.paint, true);
  // The lower front: corner panels with the lamps, steps in front of the wheels,
  // and the steel bumper with its skid plate.
  p.rounded(333, 389.5, -81.5, 81.5, 32, 76, 3, c.paint, true);
  p.box(380, T.bumper, -79, 79, 29, 52, c.bumper);
  p.box(373, 391.5, -34, 34, 25, 31, c.silver);
  for (const side of [-1, 1]) {
    const y = side * 81.8;
    for (const [z0, z1] of [
      [35, 40],
      [48, 53],
    ])
      p.box(337, 362, y - 0.5, y + 0.5, z0, z1, c.black);
    // Headlamps and indicators in the corners of the face.
    p.box(389.3, 390.3, side * 52, side * 76, 61, 71, c.lamp);
    p.box(389.3, 390.3, side * 44, side * 51, 63, 69, c.amber);
    // Fog lamps in the bumper.
    p.box(393.5, 394.2, side * 58, side * 70, 36, 41, c.lamp);
  }
  // Grille: the upper panel with the iron mark's diagonal, and the lower one.
  p.box(382.3, 383.6, -65, 65, 95, 126, c.grille);
  p.box(382.3, 383.6, -54, 54, 72, 93, c.grille);
  for (let z = 99; z < 125; z += 4.5) p.box(383.5, 384, -63, 63, z, z + 1.2, c.black);
  // The iron mark: its diagonal rises to the truck's left (to the right seen from
  // the front), through the ring, as on the sheet's front view.
  {
    const a = new THREE.Vector3(384.3, -32.5, 104.8),
      b = new THREE.Vector3(384.3, 32, 118.1),
      g = new THREE.BoxGeometry(1.2, a.distanceTo(b), 2);
    g.rotateX(Math.atan2(b.z - a.z, b.y - a.y));
    g.translate((a.x + b.x) / 2, (a.y + b.y) / 2, (a.z + b.z) / 2);
    p.add(g, c.silver);
    p.add(
      new THREE.CylinderGeometry(5.1, 5.1, 1.4, 20)
        .rotateZ(Math.PI / 2)
        .translate(384.6, 0, 111),
      c.silver,
    );
  }
  // Sun visor over the windscreen.
  p.box(364, 372, -cabHalfWidth(200) + 4, cabHalfWidth(200) - 4, 196.5, 201, c.black);
  // Mirrors on long arms from the door pillars: a main glass and a wide angle
  // under it (the front view's outline, 2.9 m to 3.2 m across).
  for (const side of [-1, 1]) {
    const inner = cabHalfWidth(182) - 1;
    p.bar([369, side * inner, 182], [377, side * 92, 176], 0.9, c.black, 6);
    p.bar([371, side * inner, 132], [377, side * 92, 136], 0.9, c.black, 6);
    p.rounded(374.5, 379.5, side * 89.5 - 2, side * 89.5 + 2, 143, 176, 1.2, c.black);
    p.rounded(374.5, 379.5, side * 89.5 - 2, side * 89.5 + 2, 124, 139, 1.2, c.black);
  }
  // The doors, traced from the sheet's side view: the front seam behind the
  // corner pillar, the rear seam 1110 mm behind it, the top seam under the roof,
  // and the handle recess low at the back of the door.
  cabSeam(p, [365.5, 88], [365.5, 186.5]);
  cabSeam(p, [291.5, 89], [291.5, 186.5]);
  cabSeam(p, [291.1, 186.5], [365.9, 186.5]);
  onCabSides(
    p,
    [
      [293.5, 101.4],
      [315.9, 97.4],
      [313.8, 104.1],
      [294.9, 109.5],
    ],
    c.black,
  );
  // Frame rails, 850 mm across, and cross members.
  for (const side of [-1, 1])
    p.box(T.bodyRear + 0.5, 376, side * 22.3, side * 28.3, 54, T.frame, c.chassis);
  for (const x of [-90, -10, 90, 160, 250, 330])
    p.box(x - 1.5, x + 1.5, -22.3, 22.3, 58, 71, c.chassis);
  // Front axle on its leaf springs, the rear tandem on the bogie's springs.
  p.box(T.frontAxle - 2.5, T.frontAxle + 2.5, -57, 57, 31, 38, c.chassis);
  for (const side of [-1, 1]) {
    p.box(T.frontAxle - 32, T.frontAxle + 32, side * 21.5, side * 29, 40, 46, c.black);
    p.box(-40, 40, side * 21, side * 29, 40, 47, c.black);
    p.box(-6, 6, side * 20, side * 30, 46, 58, c.chassis);
  }
  for (const x of T.rearAxles) {
    p.bar([x, -50, T.axleHeight], [x, 50, T.axleHeight], 4.2, c.chassis, 12);
    p.add(
      new THREE.SphereGeometry(10, 14, 10).scale(1, 0.9, 0.85).translate(x, 0, T.axleHeight),
      c.chassis,
    );
  }
  // On the left: the fuel tank and the AdBlue tank (as on photographs of the type).
  p.rounded(176, 238, 29, 62, 33, 70, 4, c.alloy);
  p.rounded(160, 173, 32, 56, 40, 63, 3, c.silver);
  // On the right: batteries, air tanks and the exhaust's silencer, its stack
  // rising behind the cab.
  p.rounded(200, 236, -62, -30, 40, 66, 1.5, c.black);
  p.bar([150, -46, 52], [192, -46, 52], 6, c.silver, 14);
  p.bar([150, -46, 38], [192, -46, 38], 6, c.silver, 14);
  p.rounded(238, 256, -64, -36, 42, 66, 3, c.silver);
  p.bar([252, -58, 60], [252, -58, 222], 3.4, c.black, 12);
  p.bar([252, -58, 214], [252, -58, 224], 3.7, c.silver, 12);
  // Mudguards over the tandem, with flaps behind it.
  for (const side of [-1, 1]) {
    p.box(-84, 84, side * 39, side * 84, 74.5, 76.5, c.black);
    p.box(-84, -82, side * 39, side * 84, 22, 76, c.black);
  }
  // The tail: a lamp bar with red lamps and a fold-up underrun bar.
  p.box(T.bodyRear - 1, T.bodyRear + 3, -76, 76, 41, 50, c.black);
  for (const side of [-1, 1]) {
    p.box(T.bodyRear - 1.6, T.bodyRear - 0.6, side * 58, side * 73, 42.5, 48.5, c.red);
    p.box(T.bodyRear - 1.6, T.bodyRear - 0.6, side * 50, side * 57, 42.5, 48.5, c.amber);
    p.box(T.bodyRear - 2, T.bodyRear + 2, side * 40, side * 44, 25, 54, c.chassis);
  }
  p.box(T.bodyRear - 5, T.bodyRear - 1, -72, 72, 24, 32, c.silver);
  // The tipper's subframe on the rails, with the pivot brackets at its end and
  // the trunnion the tipping ram stands on.
  for (const side of [-1, 1]) {
    p.box(T.pivotX - 2, T.bodyFront - 4, side * 22, side * 28.6, T.frame, SUBFRAME_TOP, c.black);
    p.box(T.pivotX - 5, T.pivotX + 5, side * 18, side * 32, T.frame, T.pivotZ + 3, c.chassis);
  }
  p.box(RAM_BASE[0] - 6, RAM_BASE[0] + 6, -14, 14, T.frame, RAM_BASE[2] + 2, c.chassis);
  addGlass(p);
  return p.merge();
}

// The windows, in the frame's mesh: glossy where the glass mask is set.
const GLASS = "#1a252e";
function addGlass(p) {
  // The windscreen narrows with the cab; it stands just proud of the face.
  const pane = (z) => [windscreenX(z) + 0.3, cabHalfWidth(z) - 7, z];
  {
    const [xb, wb, zb] = pane(137),
      [xt, wt, zt] = pane(192);
    p.polygon(
      [
        [xb, -wb, zb],
        [xb, wb, zb],
        [xt, wt, zt],
        [xt, -wt, zt],
      ],
      GLASS,
      false,
      true,
    );
  }
  // The door windows, as on the sheet's side view: the sill falls 240 mm towards
  // the front, the front edge stands upright behind the mirror's pillar, and the
  // top runs level 400 mm under the roof.
  onCabSides(
    p,
    [
      [299, 134],
      [358.5, 118],
      [358.5, 171],
      [356, 176.5],
      [350.5, 179],
      [299, 179],
    ],
    GLASS,
    true,
  );
}

// ------------------------------------------------------------------- the body
// Built at rest and placed relative to the pivot, about which it tips. Its long
// members sit on the tipper's subframe, whose top is this high.
const BODY_FLOOR = T.floor,
  SUBFRAME_TOP = T.frame + 11.3;
function buildBody() {
  const p = new Parts(),
    c = COLOURS,
    inner = T.innerHalfWidth,
    outer = T.bodyHalfWidth,
    side = BODY_FLOOR + T.sideWall,
    front = BODY_FLOOR + T.frontWall;
  // Floor (5 mm Hardox), worn bare on top.
  p.box(T.bodyRear, T.bodyFront, -outer, outer, BODY_FLOOR - 1.2, BODY_FLOOR, c.floor);
  // The body's base: trapezoidal side members along its lower edges, and cross
  // members and the two long members that sit on the subframe.
  for (const s of [-1, 1]) {
    p.add(sideMember(s), c.paint, true);
    p.box(T.bodyRear + 2, T.bodyFront - 2, s * 22, s * 28.6, SUBFRAME_TOP, BODY_FLOOR - 1.2, c.black);
  }
  for (let x = T.innerRear + 18; x < T.innerFront - 30; x += 40)
    p.box(x - 1.5, x + 1.5, -outer + 2, outer - 2, BODY_FLOOR - 8, BODY_FLOOR - 1.2, c.chassis);
  // Ram bracket under the front of the floor.
  {
    const x = T.innerRear + RAM_TOP_BODY[0];
    p.box(x - 7, x + 7, -10, 10, BODY_FLOOR + RAM_TOP_BODY[2] - 3, BODY_FLOOR - 1.2, c.chassis);
  }
  // Front wall, 980 mm, with its stiffeners and corner posts.
  p.box(T.innerFront, T.bodyFront, -outer, outer, BODY_FLOOR, front, c.paint, true);
  for (const y of [-42, 0, 42])
    p.box(T.bodyFront, T.bodyFront + 2.6, y - 2, y + 2, BODY_FLOOR, front - 1, c.paint, true);
  p.box(T.innerFront - 1, T.bodyFront + 2.6, -outer - 0.5, outer + 0.5, front - 2.2, front, c.paint, true);
  // Side walls: 880 mm aluminium hollow profiles, their plank joints showing.
  for (const s of [-1, 1]) {
    p.box(T.innerRear, T.innerFront, s * inner, s * outer, BODY_FLOOR, side, c.alloy);
    for (const z of [14.7, 29.3, 44])
      p.box(T.innerRear, T.innerFront, s * (outer - 0.1), s * (outer + 0.25), BODY_FLOOR + z - 0.35, BODY_FLOOR + z + 0.35, c.alloyLine);
    p.box(T.innerRear, T.innerFront, s * (inner - 0.4), s * (outer + 0.4), side - 1.4, side, c.alloyLine);
    // Hinges along the foot, for tipping to the side.
    for (const x of [-40, 60, 160])
      p.box(x - 3, x + 3, s * outer, s * (outer + 1.4), BODY_FLOOR - 4, BODY_FLOOR + 3, c.black);
    // Raised rear corner posts carrying the rear wall's upper bearings.
    p.box(T.bodyRear, T.innerRear + 2.5, s * (inner - 2.5), s * (outer + 0.4), BODY_FLOOR - 4, GATE_HINGE[1] + 3.5, c.paint, true);
    p.bar(
      [GATE_HINGE[0], s * (inner - 3), GATE_HINGE[1]],
      [GATE_HINGE[0], s * (outer + 1.2), GATE_HINGE[1]],
      2.2,
      c.black,
      10,
    );
  }
  // Placed relative to the pivot.
  return p.merge().translate(-T.pivotX, 0, -T.pivotZ);
}

// One of the base's side members: a trapezoid, deep at the front and shallow at the
// back, under each side wall.
function sideMember(s) {
  const outer = T.bodyHalfWidth,
    shape = new THREE.Shape();
  shape.moveTo(T.bodyRear, BODY_FLOOR);
  shape.lineTo(T.bodyFront, BODY_FLOOR);
  shape.lineTo(T.bodyFront, BODY_FLOOR - 11);
  shape.lineTo(T.bodyRear + 30, BODY_FLOOR - 7);
  shape.lineTo(T.bodyRear, BODY_FLOOR - 5);
  shape.closePath();
  const g = new THREE.ExtrudeGeometry(shape, { depth: 5, bevelEnabled: false });
  g.rotateX(Math.PI / 2);
  g.translate(0, s > 0 ? outer : -outer + 5, 0);
  return g;
}

// The rear wall swings from its bearings at the top of the corner posts. Built
// relative to the bearings.
const GATE_HINGE = [T.innerRear - T.wall / 2, T.floor + T.rearWall + 2];
function buildGate() {
  const p = new Parts(),
    c = COLOURS,
    inner = T.innerHalfWidth - 0.4,
    top = T.floor + T.rearWall,
    rear = T.bodyRear;
  p.box(rear, T.innerRear, -inner, inner, T.floor + 0.2, top, c.paint, true);
  for (const y of [-38, 38])
    p.box(rear - 2.4, rear, y - 2, y + 2, T.floor + 1, top, c.paint, true);
  p.box(rear - 2.4, rear, -inner, inner, T.floor + 26, T.floor + 30, c.paint, true);
  p.box(rear - 2.6, rear, -inner, inner, top - 3, top, c.paint, true);
  for (const s of [-1, 1])
    p.box(GATE_HINGE[0] - 2.5, GATE_HINGE[0] + 2.5, s * (inner - 6), s * (inner - 1), top - 2, GATE_HINGE[1] + 2.5, c.black);
  return p.merge().translate(-GATE_HINGE[0], 0, -GATE_HINGE[1]);
}

// ---------------------------------------------------------------- the wheels
// A 315/80R22.5 tyre with its shoulder lugs on a steel disc wheel, its axis along
// y and its face to +y.
function buildWheel(detailed) {
  const p = new Parts(),
    c = COLOURS,
    r = T.tyreRadius,
    half = T.tyreWidth / 2,
    bead = T.rimRadius,
    segments = detailed ? 30 : 16;
  const profile = [
    [bead, -half + 1],
    [bead + 6, -half - 0.2],
    [r - 6, -half],
    [r - 1.6, -half + 1.2],
    [r, -half + 3.2],
    [r, -4.6],
    [r - 0.8, -4.2],
    [r - 0.8, -3.2],
    [r, -2.8],
    [r, 2.8],
    [r - 0.8, 3.2],
    [r - 0.8, 4.2],
    [r, 4.6],
    [r, half - 3.2],
    [r - 1.6, half - 1.2],
    [r - 6, half],
    [bead + 6, half + 0.2],
    [bead, half - 1],
  ].map(([radius, y]) => new THREE.Vector2(radius, y));
  p.add(new THREE.LatheGeometry(profile, segments), c.rubber);
  if (detailed)
    for (let k = 0; k < 26; k++) {
      const angle = (k / 26) * Math.PI * 2;
      for (const s of [-1, 1])
        p.add(
          new THREE.BoxGeometry(3.2, 4.4, 1.6)
            .translate(0, s * 7.2, r + 0.3)
            .rotateY(angle),
          c.rubber,
        );
    }
  // The disc wheel, dished to its hub, with ten nuts.
  const rim = [
    [bead + 0.6, -half + 1.2],
    [bead + 0.6, half - 0.6],
    [bead - 1.2, half - 0.2],
    [bead - 4, half - 2.2],
    [10, half - 2],
    [9.2, half - 0.9],
    [3.5, half - 0.9],
    [0.01, half - 0.6],
  ].map(([radius, y]) => new THREE.Vector2(radius, y));
  p.add(new THREE.LatheGeometry(rim, segments), c.silver);
  if (detailed)
    for (let k = 0; k < 10; k++) {
      const angle = (k / 10) * Math.PI * 2;
      p.add(
        new THREE.CylinderGeometry(0.8, 0.8, 1.6, 6).translate(
          7 * Math.cos(angle),
          half - 0.3,
          7 * Math.sin(angle),
        ),
        c.chassis,
      );
    }
  return p.merge();
}

// ------------------------------------------------------------ the tipping ram
// A five-stage telescopic ram from a trunnion on the frame to a bracket under the
// front of the floor, lying almost flat with the body down and standing nearly
// upright at 49 degrees.
const RAM_BASE = [170, 0, 78],
  RAM_TOP_BODY = [330, 0, -9],
  RAM_STAGES = 5,
  RAM_RADII = [6.4, 5.5, 4.7, 3.9, 3.1];
const ramTop = (tip, out) => {
  const c = Math.cos(tip),
    s = Math.sin(tip),
    x = T.innerRear + RAM_TOP_BODY[0] - T.pivotX,
    z = T.floor + RAM_TOP_BODY[2] - T.pivotZ;
  return out.set(T.pivotX + x * c - z * s, 0, T.pivotZ + x * s + z * c);
};
const RAM_CLOSED = ramTop(0, new THREE.Vector3()).distanceTo(
  new THREE.Vector3(...RAM_BASE),
);
// Spheres that hold the wheels and the ram in any pose, for culling.
const WHEELS_BOUND = new THREE.Sphere(
    new THREE.Vector3((T.frontAxle + T.rearAxles[1]) / 2, 0, T.axleHeight),
    Math.hypot(
      (T.frontAxle - T.rearAxles[1]) / 2 + T.tyreRadius,
      T.frontTrack + T.tyreWidth,
      T.tyreRadius,
    ),
  ),
  RAM_BOUND = new THREE.Sphere().setFromPoints([
    new THREE.Vector3(...RAM_BASE),
    ramTop(0, new THREE.Vector3()),
    ramTop(T.maxTip, new THREE.Vector3()),
  ]);
RAM_BOUND.radius += RAM_RADII[0];

// ------------------------------------------------------------------ materials
// One material for each kind of surface. Painted vertices take the truck's paint
// from a uniform, so the trucks of all players share one shader.
function paintable(options) {
  const material = new THREE.MeshStandardMaterial({ vertexColors: true, ...options }),
    paint = { value: new THREE.Color(1, 1, 1) };
  material.userData.paint = paint;
  material.onBeforeCompile = (shader) => {
    shader.uniforms.truckPaint = paint;
    shader.vertexShader = shader.vertexShader
      .replace(
        "#include <common>",
        `#include <common>
        attribute float paintMask;
        attribute float glassMask;
        varying float vPaintMask;
        varying float vGlassMask;`,
      )
      .replace(
        "#include <begin_vertex>",
        `#include <begin_vertex>
        vPaintMask = paintMask;
        vGlassMask = glassMask;`,
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        `#include <common>
        uniform vec3 truckPaint;
        varying float vPaintMask;
        varying float vGlassMask;`,
      )
      .replace(
        "#include <color_fragment>",
        `#include <color_fragment>
        diffuseColor.rgb *= mix(vec3(1.0), truckPaint, vPaintMask);`,
      )
      .replace(
        "#include <roughnessmap_fragment>",
        `#include <roughnessmap_fragment>
        roughnessFactor = mix(roughnessFactor, 0.1, vGlassMask);`,
      )
      .replace(
        "#include <metalnessmap_fragment>",
        `#include <metalnessmap_fragment>
        metalnessFactor = mix(metalnessFactor, 0.55, vGlassMask);`,
      );
  };
  material.customProgramCacheKey = () => "truck-paint";
  return material;
}

// Everything every truck shares, built once.
export function createTruckModel() {
  const geometry = {
      frame: buildFrame(),
      body: buildBody(),
      gate: buildGate(),
      wheel: buildWheel(true),
      farWheel: buildWheel(false),
      ram: new THREE.CylinderGeometry(1, 1, 1, 16, 1, false),
    },
    tyres = new THREE.MeshStandardMaterial({
      vertexColors: true,
      roughness: 0.82,
      metalness: 0.1,
    }),
    ram = new THREE.MeshStandardMaterial({ roughness: 0.22, metalness: 0.85 });
  const ramColours = RAM_RADII.map((_, k) =>
    new THREE.Color(k === 0 ? "#2a2d30" : "#d9dde0"),
  );

  // One truck in the world.
  function create(paint, castShadow = true) {
    const painted = paintable({ roughness: 0.5, metalness: 0.18 });
    painted.userData.paint.value.set(paint ?? "#e89912");
    const root = new THREE.Group(),
      body = new THREE.Group(),
      gate = new THREE.Group(),
      meshes = [];
    root.rotation.order = "ZYX";
    const mesh = (g, material, parent, shadow = castShadow) => {
      const m = new THREE.Mesh(g, material);
      m.castShadow = shadow;
      m.receiveShadow = true;
      parent.add(m);
      meshes.push(m);
      return m;
    };
    mesh(geometry.frame, painted, root);
    body.position.set(T.pivotX, 0, T.pivotZ);
    root.add(body);
    mesh(geometry.body, painted, body);
    // The rear wall and the ram are small beside the body: their shadows are not
    // worth a draw each.
    gate.position.set(GATE_HINGE[0] - T.pivotX, 0, GATE_HINGE[1] - T.pivotZ);
    body.add(gate);
    mesh(geometry.gate, painted, gate, false);
    const wheels = new THREE.InstancedMesh(geometry.wheel, tyres, TYRES.length),
      farWheels = new THREE.InstancedMesh(geometry.farWheel, tyres, TYRES.length);
    for (const w of [wheels, farWheels]) {
      w.castShadow = castShadow;
      w.receiveShadow = true;
      // Wherever they turn and roll, the wheels stay inside this.
      w.boundingSphere = WHEELS_BOUND;
      root.add(w);
    }
    farWheels.visible = false;
    const rams = new THREE.InstancedMesh(geometry.ram, ram, RAM_STAGES);
    ramColours.forEach((colour, k) => rams.setColorAt(k, colour));
    rams.boundingSphere = RAM_BOUND;
    root.add(rams);

    const matrix = new THREE.Matrix4(),
      turn = new THREE.Quaternion(),
      spin = new THREE.Quaternion(),
      position = new THREE.Vector3(),
      scale = new THREE.Vector3(1, 1, 1),
      zAxis = new THREE.Vector3(0, 0, 1),
      yAxis = new THREE.Vector3(0, 1, 0),
      top = new THREE.Vector3(),
      base = new THREE.Vector3(...RAM_BASE),
      along = new THREE.Vector3(),
      centre = new THREE.Vector3();
    function placeWheels(pose, target) {
      const roll = pose.wheels / T.tyreRadius,
        tan = Math.tan(pose.steer);
      TYRES.forEach(([x, y], i) => {
        const left = y > 0,
          front = x === T.frontAxle,
          // Ackermann: each front wheel points at the turn's centre.
          steer = front
            ? Math.atan2(T.wheelbase * tan, T.wheelbase - y * tan)
            : 0;
        turn.setFromAxisAngle(zAxis, steer + (left ? 0 : Math.PI));
        spin.setFromAxisAngle(yAxis, left ? roll : -roll);
        turn.multiply(spin);
        position.set(x, y, T.axleHeight);
        target.setMatrixAt(i, matrix.compose(position, turn, scale));
      });
      target.instanceMatrix.needsUpdate = true;
    }
    function placeRam(tip) {
      ramTop(tip, top);
      const length = top.distanceTo(base),
        step = (length - RAM_CLOSED) / (RAM_STAGES - 1);
      along.copy(top).sub(base).normalize();
      turn.setFromUnitVectors(yAxis, along);
      for (let k = 0; k < RAM_STAGES; k++) {
        const from = k * step;
        centre.copy(along).multiplyScalar(from + RAM_CLOSED / 2).add(base);
        rams.setMatrixAt(
          k,
          matrix.compose(
            centre,
            turn,
            position.set(RAM_RADII[k], RAM_CLOSED - k * 1.2, RAM_RADII[k]),
          ),
        );
      }
      rams.instanceMatrix.needsUpdate = true;
    }
    let far = false;
    return {
      root,
      update(pose) {
        root.position.set(pose.x, pose.y, pose.z ?? 0);
        root.rotation.set(pose.roll ?? 0, -(pose.pitch ?? 0), pose.heading);
        body.rotation.y = -pose.tip;
        gate.rotation.y = gateAngle(pose);
        placeWheels(pose, far ? farWheels : wheels);
        placeRam(pose.tip);
      },
      // Far away, the wheels lose their lugs and nuts.
      setFar(value, pose) {
        if (value === far) return false;
        far = value;
        wheels.visible = !far;
        farWheels.visible = far;
        if (pose) placeWheels(pose, far ? farWheels : wheels);
        return true;
      },
      setPaint(value) {
        painted.userData.paint.value.set(value ?? "#e89912");
      },
      dispose() {
        painted.dispose();
        wheels.dispose();
        farWheels.dispose();
        rams.dispose();
      },
      meshes,
    };
  }
  return { create };
}

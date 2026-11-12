import { CONFIG } from "./config.js";

// The arm's four leadscrew drives as the X1 would carry them with a 12 V N20
// gearmotor (1:50, 800 rpm without load) turning an M4 × 0.7 leadscrew. Each
// stroke moves as fast as its motor can push the load it carries: the weight of
// the arm and of the sand in the bucket, from the R12 CAD masses. The two boom
// drives share the boom's load equally. Digging resistance is not modelled.
//
// Sources and assumptions:
// - Motor: the seller's N20 table, row "1:50, 12 V": 800 rpm and 0.08 A with
//   no load. Its stall current is hidden in the screenshot; 1.1 A (as in the
//   1000 rpm row beside it) is assumed. The table's torque columns are not
//   physically possible and are not used. Gearbox efficiency 0.65 is assumed.
// - Leadscrew: M4 × 0.7, steel in a brass nut, friction 0.15. It is
//   self-locking, so lowering a load also takes motor torque.
// - Supply: the X1's 3S battery at 11.1 V nominal, switched by the main board's
//   DRV8876 (PWM duty = stick × movement speed, as in the X1 firmware), with
//   its 0.5 A current limit per actuator channel. The actuator's own end-stop
//   board (actuator_v6 rev 6.2) drops 0.35 V across a Schottky diode; its
//   resettable fuse (0.65 Ω, 0.35 A hold), its MOSFET, the cable and the driver
//   add 1.7 Ω. The fuse's trip is not modelled.
// - Masses: excavator_arm_r12/simulation/mass_properties.json, the same bodies
//   and frames as the R12 MuJoCo model. Sand weighs 1.6 g per cm³ loose.
export const DRIVE = Object.freeze({
  label: "N20 12 V 1:50 · M4 × 0.7",
  ratio: 50,
  ratedVoltage: 12,
  noLoadRpm: 800,
  noLoadCurrent: 0.08,
  stallCurrent: 1.1,
  gearEfficiency: 0.65,
  lead: 0.7,
  screwDiameter: 4,
  friction: 0.15,
  supply: 11.1,
  diodeDrop: 0.35,
  seriesResistance: 1.7,
  currentLimit: 0.5,
  sandDensity: 1.6e-6,
});

const G = 9.81,
  RESISTANCE = DRIVE.ratedVoltage / DRIVE.stallCurrent,
  CIRCUIT = RESISTANCE + DRIVE.seriesResistance,
  MOTOR_NO_LOAD = (DRIVE.noLoadRpm * DRIVE.ratio * 2 * Math.PI) / 60,
  // Back-EMF and torque constant (V s/rad = N m/A).
  K = (DRIVE.ratedVoltage - DRIVE.noLoadCurrent * RESISTANCE) / MOTOR_NO_LOAD,
  // Torque at the leadscrew per ampere above the no-load current (N m/A).
  SCREW_TORQUE_PER_AMP = K * DRIVE.ratio * DRIVE.gearEfficiency,
  // Thread geometry: pitch diameter, lead angle and friction angle.
  PITCH_DIAMETER = DRIVE.screwDiameter - 0.6495 * DRIVE.lead,
  LEAD_ANGLE = Math.atan(DRIVE.lead / (Math.PI * PITCH_DIAMETER)),
  FRICTION_ANGLE = Math.atan(DRIVE.friction / Math.cos(Math.PI / 6)),
  // Leadscrew torque per newton of load (N m/N), against the load and with it.
  RAISE = (Math.tan(LEAD_ANGLE + FRICTION_ANGLE) * PITCH_DIAMETER) / 2000,
  LOWER = (Math.tan(FRICTION_ANGLE - LEAD_ANGLE) * PITCH_DIAMETER) / 2000,
  // Stroke speed per motor speed (mm/s per rad/s).
  STROKE_PER_RAD = DRIVE.lead / (2 * Math.PI * DRIVE.ratio);

export const SCREW = Object.freeze({
  efficiency: Math.tan(LEAD_ANGLE) / Math.tan(LEAD_ANGLE + FRICTION_ANGLE),
  selfLocking: FRICTION_ANGLE > LEAD_ANGLE,
});

// A drive's state: its stroke rate (mm/s, + extends), the load it carries (N,
// + is a push), its motor current (A), and what it is doing: "idle", "moving",
// "stalled" (it cannot move its load, or is held against hard ground) or "end"
// (its end stop has switched it off).
export const freshDrive = () => ({ rate: 0, force: 0, current: 0, state: "idle" });

// The current through a stalled motor at a duty: no back-EMF, up to the limit.
const stallCurrent = (duty) =>
  Math.min(
    DRIVE.currentLimit,
    Math.max(0, (Math.abs(duty) * DRIVE.supply - DRIVE.diodeDrop) / CIRCUIT),
  );

// How fast a drive moves at a PWM duty (-1..1, + extends) while carrying a load:
// the motor turns as fast as the voltage left after the circuit's losses allows.
// A drive that cannot overcome its load, or would need more than the current
// limit, stalls; the leadscrew then holds the load where it is.
export function driveRate(duty, force, out = freshDrive()) {
  out.force = force;
  if (!duty) {
    out.rate = 0;
    out.current = 0;
    out.state = "idle";
    return out;
  }
  const direction = Math.sign(duty),
    torque = Math.abs(force) * (force * direction > 0 ? RAISE : LOWER),
    current = DRIVE.noLoadCurrent + torque / SCREW_TORQUE_PER_AMP,
    emf = Math.abs(duty) * DRIVE.supply - DRIVE.diodeDrop - current * CIRCUIT;
  if (current > DRIVE.currentLimit || emf <= 0) return stallDrive(duty, out);
  out.rate = (direction * emf * STROKE_PER_RAD) / K;
  out.current = current;
  out.state = "moving";
  return out;
}

// A drive that cannot move: against its load, or held against something solid.
export function stallDrive(duty, out) {
  out.rate = 0;
  out.current = stallCurrent(duty);
  out.state = "stalled";
  return out;
}

// A drive at the end of its stroke and driven further: its end stop has opened
// the motor circuit in that direction.
export function endDrive(out) {
  out.rate = 0;
  out.current = 0;
  out.state = "end";
  return out;
}

// Seconds for a full stroke at full duty under a constant load against the motion.
export function strokeTime(force = 0) {
  const { rate } = driveRate(1, force);
  return rate > 0 ? CONFIG.arm.strokes[0] / rate : Infinity;
}

// --- Gravity loads -----------------------------------------------------------------

// Mass (kg) and centre of mass (x, z in mm, in the body's frame) of every moving
// body, from the R12 CAD (excavator_arm_r12/simulation/mass_properties.json).
const MASSES = {
  boom: [0.312245, 188.758, 40.4228],
  stick: [0.190816, 76.2543, 10.5483],
  side_link: [0.010134, 31.5079, -0.0002],
  h_link: [0.007504, 11.7509, -0.0003],
  bucket: [0.085396, 34.089, 36.6557],
  boom_L_barrel: [0.050692, 39.7886, -0.7696],
  boom_L_rod: [0.0076, 85.3499, -0.0173],
  boom_R_barrel: [0.050692, 39.7886, -0.7696],
  boom_R_rod: [0.0076, 85.3499, -0.0173],
  stick_barrel: [0.050692, 39.7886, 0.7696],
  stick_rod: [0.0076, 85.3499, 0.0173],
  bucket_barrel: [0.050692, 39.7886, 0.7696],
  bucket_rod: [0.0076, 85.3499, 0.0173],
};

const ARM = CONFIG.arm,
  STEP = ARM.pitch,
  BOOM_ROWS = ARM.tables.boom.rows,
  STICK_ROWS = ARM.tables.stick.rows,
  LINK_ROWS = ARM.tables.bucket.rows,
  LINKS = ARM.tables.bucket.bodies,
  BODIES = ["base", "boom", "stick", ...LINKS],
  index = (name) => BODIES.indexOf(name),
  BOOM_BODY = index("boom"),
  STICK_BODY = index("stick"),
  BUCKET_BODY = index("bucket"),
  CLOSED = ARM.closed[0],
  MAX_STROKE = ARM.strokes[0],
  // Central differences over this stroke step (mm): two rows of the tables.
  H = 2 * STEP;
const LINK_BODY_MASSES = LINKS.map((name) => ({
  body: index(name),
  mass: MASSES[name],
}));
const BOOM_MASS = MASSES.boom,
  STICK_MASS = MASSES.stick;
// Each drive: its pins (body and local position) and its barrel's and rod's masses.
const PIN = (name) => ({
  body: index(ARM.pin_body[name]),
  x: ARM.pins[name][0],
  z: ARM.pins[name][1],
});
const DRIVES = ARM.drives.map((drive) => ({
  a: PIN(drive.a),
  b: PIN(drive.b),
  barrel: MASSES[`${drive.name}_barrel`],
  rod: MASSES[`${drive.name}_rod`],
}));
// The two boom drives share the boom's stroke.
const SHARE = [
  ARM.drives.filter((d) => d.a === ARM.drives[0].a && d.b === ARM.drives[0].b).length,
  1,
  1,
];

// Body frames in the arm's base frame, filled without allocating: x, z, turn
// and the turn's cosine and sine, five numbers each.
const POSE = new Float64Array(5 * BODIES.length);
function interpolate(rows, stroke, column, at) {
  const x = Math.min(Math.max(stroke / STEP, 0), rows.length - 1.000001),
    i = Math.floor(x),
    f = x - i,
    r0 = rows[i],
    r1 = rows[i + 1];
  POSE[at] = r0[column] + (r1[column] - r0[column]) * f;
  POSE[at + 1] = r0[column + 1] + (r1[column + 1] - r0[column + 1]) * f;
  POSE[at + 2] = r0[column + 2] + (r1[column + 2] - r0[column + 2]) * f;
}
// The frame at `at`, held relative to the frame at `parent` (or to the base,
// without one), made absolute.
function attach(parent, at) {
  if (parent >= 0) {
    const c = POSE[parent + 3],
      s = POSE[parent + 4],
      x = POSE[at],
      z = POSE[at + 1];
    POSE[at] = POSE[parent] + c * x - s * z;
    POSE[at + 1] = POSE[parent + 1] + s * x + c * z;
    POSE[at + 2] += POSE[parent + 2];
  }
  POSE[at + 3] = Math.cos(POSE[at + 2]);
  POSE[at + 4] = Math.sin(POSE[at + 2]);
}
function frames(s0, s1, s2) {
  POSE[0] = POSE[1] = POSE[2] = POSE[4] = 0;
  POSE[3] = 1;
  interpolate(BOOM_ROWS, s0, 0, 5);
  attach(-1, 5);
  interpolate(STICK_ROWS, s1, 0, 10);
  attach(5, 10);
  for (let n = 0; n < LINKS.length; n++) {
    interpolate(LINK_ROWS, s2, 3 * n, 15 + 5 * n);
    attach(10, 15 + 5 * n);
  }
}

// Mass moment of the arm and its load about the base frame's origin: sum of
// mass × centre of mass (kg mm), into `out` as [x, z].
const PA = new Float64Array(2),
  PB = new Float64Array(2),
  SUM = new Float64Array(2);
function pinAt(pin, out) {
  const at = 5 * pin.body,
    c = POSE[at + 3],
    s = POSE[at + 4];
  out[0] = POSE[at] + c * pin.x - s * pin.z;
  out[1] = POSE[at + 1] + s * pin.x + c * pin.z;
}
// A part with its centre `along` further out on the x axis of a frame at
// (ox, oz) whose axes turn by cos c and sin s.
function addMass(ox, oz, c, s, part, along) {
  const mass = part[0],
    x = part[1] + along,
    z = part[2];
  SUM[0] += mass * (ox + c * x - s * z);
  SUM[1] += mass * (oz + s * x + c * z);
}
const addBody = (body, part) => {
  const at = 5 * body;
  addMass(POSE[at], POSE[at + 1], POSE[at + 3], POSE[at + 4], part, 0);
};
function moment(s0, s1, s2, payload, out) {
  frames(s0, s1, s2);
  SUM[0] = SUM[1] = 0;
  addBody(BOOM_BODY, BOOM_MASS);
  addBody(STICK_BODY, STICK_MASS);
  for (let n = 0; n < LINK_BODY_MASSES.length; n++)
    addBody(LINK_BODY_MASSES[n].body, LINK_BODY_MASSES[n].mass);
  if (payload[0] > 0) addBody(BUCKET_BODY, payload);
  // A drive's barrel turns about its rear pin, along the line to its rod pin; the
  // rod slides out along that line by the stroke beyond the closed length.
  for (let n = 0; n < DRIVES.length; n++) {
    const drive = DRIVES[n];
    pinAt(drive.a, PA);
    pinAt(drive.b, PB);
    const dx = PB[0] - PA[0],
      dz = PB[1] - PA[1],
      length = Math.sqrt(dx * dx + dz * dz),
      c = dx / length,
      s = dz / length;
    addMass(PA[0], PA[1], c, s, drive.barrel, 0);
    addMass(PA[0], PA[1], c, s, drive.rod, length - CLOSED);
  }
  out[0] = SUM[0];
  out[1] = SUM[1];
  return out;
}

// Gravity in the arm's plane (m/s²): its components along the arm's base x
// (forward, turned with the slew) and z (the chassis' up), for a machine that
// may stand tilted. Level, it is [0, -9.81].
export function armGravity(machine, out = new Float64Array(2)) {
  const cp = Math.cos(machine.pitch ?? 0),
    sp = Math.sin(machine.pitch ?? 0),
    cr = Math.cos(machine.roll ?? 0),
    sr = Math.sin(machine.roll ?? 0),
    s = (machine.slew * Math.PI) / 180;
  out[0] = -G * (Math.cos(s) * sp + Math.sin(s) * cp * sr);
  out[1] = -G * cp * cr;
  return out;
}

// The load on each drive (N, + is a push) holding the arm still: boom (each of
// its two drives), stick and bucket. By virtual work, F_i = -g · dM/ds_i, with M
// the arm's mass moment. `payload` is [mass kg, x mm, z mm] in the bucket's frame.
const UP = new Float64Array(2),
  DOWN = new Float64Array(2),
  STROKES = new Float64Array(3),
  NO_PAYLOAD = [0, 0, 0];
export function holdForces(
  strokes,
  gravity = [0, -G],
  payload = NO_PAYLOAD,
  out = new Float64Array(3),
) {
  for (let i = 0; i < 3; i++) {
    STROKES[0] = strokes[0];
    STROKES[1] = strokes[1];
    STROKES[2] = strokes[2];
    const high = Math.min(MAX_STROKE, strokes[i] + H),
      low = Math.max(0, strokes[i] - H);
    STROKES[i] = high;
    moment(STROKES[0], STROKES[1], STROKES[2], payload, UP);
    STROKES[i] = low;
    moment(STROKES[0], STROKES[1], STROKES[2], payload, DOWN);
    const span = high - low;
    out[i] =
      -(gravity[0] * (UP[0] - DOWN[0]) + gravity[1] * (UP[1] - DOWN[1])) /
      span /
      SHARE[i];
  }
  return out;
}

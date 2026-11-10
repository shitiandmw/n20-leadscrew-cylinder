// The first scoop from a start position, as the README describes it, at full
// speed: how many seconds to hold each control. Tests, the load test and the
// pictures all dig this way, from the carry pose the machine starts in.
export const SCOOP = Object.freeze([
  [2.7, { bucket: -1 }], // open the bucket, 50 to 15 mm
  [2.2, { stick: -1 }], // reach out, 38 to 9 mm
  [1.2, { boom: -1 }], // lower the teeth onto the sand, 45 to 29 mm
  [1.8, { stick: 1 }], // crowd the stick, to 33 mm
  [3.5, { bucket: 1 }], // curl the bucket full, to 60 mm
]);
export const CARRY = Object.freeze([
  [1.5, { boom: 1 }], // lift, to 49 mm
  [1.5, { slew: 1 }], // swing 45 degrees over the pour zone
]);
export const POUR = Object.freeze([
  [3.5, { bucket: -1 }], // open, to 15 mm
]);
// Back to the sand for another scoop: the next SCOOP can start at its crowd.
export const RETURN = Object.freeze([
  [1.5, { slew: -1 }],
  [1.8, { stick: -1 }],
  [1.5, { boom: -1 }],
]);

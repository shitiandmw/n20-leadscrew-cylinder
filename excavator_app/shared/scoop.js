// The first scoop from a start position, as the README describes it, at full
// speed: how many seconds to hold each control. Tests, the load test and the
// pictures all dig this way, from the carry pose the machine starts in. The arm's
// times are those of the 12 V N20 leadscrew drives (shared/drives.js), carrying
// the arm and the sand, at full duty; each ends its stroke within 0.2 mm of the
// end shown.
export const SCOOP = Object.freeze([
  [4.33, { bucket: -1 }], // open the bucket, 50 to 15 mm
  [3.7, { stick: -1 }], // reach out, 38 to 9.5 mm
  [2.1, { boom: -1 }], // lower the teeth onto the sand, 45 to 29.4 mm
  [2.97, { stick: 1 }], // crowd the stick, to 33 mm
  [5.8, { bucket: 1 }], // curl the bucket full, to 60 mm
]);
export const CARRY = Object.freeze([
  [3.5, { boom: 1 }], // lift, to 49 mm
  [1.5, { slew: 1 }], // swing 45 degrees over the pour zone
]);
export const POUR = Object.freeze([
  [5.7, { bucket: -1 }], // open, to 15 mm
]);
// Back to the sand for another scoop: the next SCOOP can start at its crowd.
export const RETURN = Object.freeze([
  [1.5, { slew: -1 }],
  [3.07, { stick: -1 }], // to 9.4 mm
  [2.6, { boom: -1 }], // to 29.6 mm
]);

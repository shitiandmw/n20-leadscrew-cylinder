// The first scoop from a start position, as the README describes it: how many
// seconds to hold each control, at full speed unless a part of it is given. Tests,
// the load test and the pictures all dig this way, from the carry pose the machine
// starts in. The arm's times are those of the 12 V N20 leadscrew drives
// (shared/drives.js), carrying the arm and the sand; each ends its stroke within
// 0.3 mm of the end shown.
//
// A heaped bucket only stays heaped while its mouth is level. So the curl in the
// sand stops with the mouth level, and the rest of it goes with the lift: raising
// the boom alone would tip the lip down by 28 degrees and pour the heap off.
export const SCOOP = Object.freeze([
  [4.33, { bucket: -1 }], // open the bucket, 50 to 15 mm
  [3.7, { stick: -1 }], // reach out, 38 to 9.5 mm
  [2.1, { boom: -1 }], // lower the teeth onto the sand, 45 to 29.4 mm
  [2.97, { stick: 1 }], // crowd the stick, to 33 mm
  [5.17, { bucket: 1 }], // curl the bucket until its mouth is level, at 56 mm
]);
export const CARRY = Object.freeze([
  [3.5, { boom: 1, bucket: 0.4 }], // lift to 49 mm, curling on to 60 mm to stay level
  [1.5, { slew: 1 }], // swing 45 degrees over the pour zone
]);
export const POUR = Object.freeze([
  [5.7, { bucket: -1 }], // open, to 15 mm
]);
// Instead of the pour zone, the first player's dump truck, whose body stands
// beside the start position: from the lift, on up until the bucket clears the
// truck's side wall, and round to the right over the middle of the body. Then
// POUR.
export const TO_TRUCK = Object.freeze([
  [3.5, { boom: 1, bucket: 0.4 }], // the lift of CARRY, to 49 mm
  [1.2, { boom: 1 }], // on up to 55.5 mm
  [3.0, { slew: -1 }], // swing 90 degrees right
]);
// Back to the sand for another scoop: the next SCOOP can start at its crowd.
export const RETURN = Object.freeze([
  [1.5, { slew: -1 }],
  [3.07, { stick: -1 }], // to 9.4 mm
  [2.6, { boom: -1 }], // to 29.4 mm
]);

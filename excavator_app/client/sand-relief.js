// Disturbed sand, and in a lesser way all sand, is not smooth. Works in the world:
// lumps seen from above, as strong as the sand is disturbed, and on any slope near
// the angle of repose lines running down it, seen from the side it faces. Sets
// sandSlope, the tilt to add to the normal, sandShade, what to multiply the colour
// by, and sandPatch, blotches for whatever sand does unevenly: thin sand breaking
// up, damp sand drying. Read by the bed and by the load in a bucket.
export const SAND_LUMPS = `
  uniform sampler2D sandLumps;
  vec2 sandSlope;
  float sandShade;
  float sandPatch;
  void sandRelief(vec3 at, vec3 up, float disturbed) {
    vec3 fine = texture2D(sandLumps, at.xy / 192.0).xyz - 0.5,
      broad = texture2D(sandLumps, vec2(at.x * 0.8 - at.y * 0.6, at.x * 0.6 + at.y * 0.8) / 560.0).xyz - 0.5;
    sandPatch = fine.z + broad.z * 1.3;
    // Moved a little, the lumps come up patchily and not along the cells of the bed.
    float strength = mix(0.35, 1.0, smoothstep(0.15, 0.75, disturbed + (sandPatch - 0.1) * 0.5 * smoothstep(0.0, 0.25, disturbed)));
    float hollow = sandPatch * strength;
    // Only where sand lies near its angle of repose, which here is 0.56.
    float steep = length(up.xy), streaks = smoothstep(0.3, 0.52, steep);
    // Seen at a low angle, tilted lumps on a slope would squeeze into feathers.
    sandSlope = (fine.xy * 1.25 + broad.xy * 0.8) * strength * (1.0 - 0.7 * streaks);
    if (streaks > 0.0) {
      vec2 facing = up.xy * up.xy / (steep * steep);
      // Stretched up the slope, so that lumps become grooves.
      vec3 alongX = texture2D(sandLumps, vec2(at.y / 128.0, at.z / 640.0)).xyz - 0.5,
        alongY = texture2D(sandLumps, vec2(at.x / 128.0, at.z / 640.0)).xyz - 0.5;
      sandSlope += streaks * vec2(alongY.x * facing.y, alongX.x * facing.x) * 0.5;
      hollow += streaks * (alongX.z * facing.x + alongY.z * facing.y) * 0.4;
    }
    sandShade = 1.0 + clamp(hollow, -0.6, 0.6) * 0.38;
  }`;

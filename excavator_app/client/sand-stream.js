import * as THREE from "three";
import { SAND, WORLD } from "../shared/world.js";

// Fine grains with lighting, subpixel coverage and a short camera exposure.
// All detail is instanced; uploads remain one record per physics parcel.
export function createSandStream(scene, mobile) {
  const samples = mobile ? 48 : 96;
  const geometry = new THREE.InstancedBufferGeometry();
  const offsets = new Float32Array(samples * 3),
    normals = new Float32Array(samples * 3);
  const seeds = new Float32Array(samples);
  let seed = 19;
  const random = () =>
    (seed = (1664525 * seed + 1013904223) >>> 0) / 4294967296;
  for (let i = 0; i < samples; i++) {
    const z = random() * 2 - 1,
      phi = random() * Math.PI * 2;
    const r = (WORLD.radius - 0.4) * Math.cbrt(random()),
      xy = Math.sqrt(1 - z * z);
    offsets.set([r * xy * Math.cos(phi), r * xy * Math.sin(phi), r * z], i * 3);
    // Independent tiny grain faces, not normals of the large parcel sphere.
    const nx = random() - 0.5,
      ny = random() - 0.5,
      nz = 0.7 + random();
    const length = Math.hypot(nx, ny, nz);
    normals.set([nx / length, ny / length, nz / length], i * 3);
    seeds[i] = (i + random()) / samples;
  }
  geometry.setAttribute("position", new THREE.BufferAttribute(offsets, 3));
  geometry.setAttribute("normal", new THREE.BufferAttribute(normals, 3));
  geometry.setAttribute("grainSeed", new THREE.BufferAttribute(seeds, 1));
  const parcels = new THREE.InstancedBufferAttribute(
    new Float32Array(SAND.maxGrains * 4),
    4,
  );
  const motion = new THREE.InstancedBufferAttribute(
    new Float32Array(SAND.maxGrains * 4),
    4,
  );
  const slots = new THREE.InstancedBufferAttribute(
    new Float32Array(SAND.maxGrains),
    1,
  );
  const attributes = [parcels, motion, slots];
  for (const attribute of attributes)
    attribute.setUsage(THREE.DynamicDrawUsage);
  geometry.setAttribute("parcel", parcels);
  geometry.setAttribute("flight", motion);
  geometry.setAttribute("parcelSlot", slots);
  geometry.instanceCount = 0;
  const viewport = { value: new THREE.Vector2() };
  const material = new THREE.MeshLambertMaterial({
    color: new THREE.Color("#e4d9c3")
      .convertSRGBToLinear()
      .multiplyScalar(0.78),
    transparent: true,
    depthWrite: false,
  });
  material.onBeforeCompile = (shader) => {
    shader.uniforms.grainViewport = viewport;
    shader.vertexShader = shader.vertexShader
      .replace(
        "#include <common>",
        `#include <common>
        attribute vec4 parcel;
        attribute vec4 flight;
        attribute float parcelSlot;
        attribute float grainSeed;
        uniform vec2 grainViewport;
        varying vec4 vGrainShape;
        varying vec3 vGrainInk;`,
      )
      .replace(
        "#include <begin_vertex>",
        `#include <begin_vertex>
        float phase = fract(grainSeed + parcelSlot * 0.618034);
        float angle = parcelSlot * 2.399963;
        transformed.xy = mat2(cos(angle), sin(angle), -sin(angle), cos(angle)) * transformed.xy;
        float falling = smoothstep(60.0, 450.0, -flight.z);
        // Resolve a parcel into slightly different release times. The short
        // ballistic segment joins gaps in a fast stream without large beads.
        float releaseTime = (phase - 0.5) * 0.014 * falling;
        vec3 breakup = flight.xyz * releaseTime;
        breakup.z -= 4905.0 * releaseTime * releaseTime;
        breakup.xy += transformed.xy * flight.w * 0.08 * falling;
        breakup *= min(1.0, 0.75 * flight.w / max(length(breakup), 0.0001));
        transformed += parcel.xyz + breakup;
        vGrainInk = vec3(parcel.w, 0.9 + 0.2 * phase, 0.38 + 0.28 * phase);`,
      )
      .replace(
        "#include <project_vertex>",
        `#include <project_vertex>
        float pixelsPerMM = 0.5 * grainViewport.y * projectionMatrix[1][1] / max(1.0, -mvPosition.z);
        float diameter = vGrainInk.z * pixelsPerMM;
        vec3 viewFlow = mat3(modelViewMatrix) * flight.xyz;
        // A 1/500 s exposure, capped in world space and disabled at contacts.
        float exposure = min(0.002, 0.5 * flight.w / max(length(flight.xyz), 1.0));
        vec2 blur = (viewFlow.xy + mvPosition.xy * viewFlow.z / max(1.0, -mvPosition.z))
          * exposure * pixelsPerMM;
        float blurLength = min(length(blur), 7.0);
        vec2 direction = length(blur) > 0.0001 ? normalize(blur) : vec2(0.0, 1.0);
        float raster = max(1.5, diameter + blurLength + 2.0);
        gl_PointSize = raster;
        vGrainShape = vec4(direction, blurLength, raster);
        vGrainInk.z = diameter;`,
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        `#include <common>
        varying vec4 vGrainShape;
        varying vec3 vGrainInk;`,
      )
      .replace(
        "#include <color_fragment>",
        `#include <color_fragment>
        vec2 pixel = (gl_PointCoord - 0.5) * vGrainShape.w;
        pixel.y = -pixel.y;
        vec2 direction = vGrainShape.xy;
        float along = max(0.0, abs(dot(pixel, direction)) - 0.5 * vGrainShape.z);
        float across = dot(pixel, vec2(-direction.y, direction.x));
        float diameter = vGrainInk.z;
        float sigma = max(0.42, diameter * 0.35);
        float footprint = exp(-0.5 * (along * along + across * across) / (sigma * sigma));
        // Conserve apparent coverage below a pixel and along a blurred path:
        // distant grains do not become bright, full-pixel specks.
        float ink = diameter * diameter / max(1.0, diameter * (diameter + vGrainShape.z));
        diffuseColor.a *= footprint * ink * vGrainInk.x;
        if (diffuseColor.a < 0.004) discard;
        diffuseColor.rgb *= vGrainInk.y;`,
      );
  };
  const grains = new THREE.Points(geometry, material);
  grains.receiveShadow = true;
  grains.frustumCulled = false;
  grains.onBeforeRender = (renderer) =>
    renderer.getDrawingBufferSize(viewport.value);
  scene.add(grains);
  return {
    write(index, slot, x, y, z, coverage, velocity, room) {
      const k = index * 4;
      parcels.array[k] = x;
      parcels.array[k + 1] = y;
      parcels.array[k + 2] = z;
      parcels.array[k + 3] = coverage;
      slots.array[index] = slot;
      motion.array[k] = velocity[0];
      motion.array[k + 1] = velocity[1];
      motion.array[k + 2] = velocity[2];
      motion.array[k + 3] = room;
    },
    finish(count) {
      geometry.instanceCount = count;
      for (const attribute of attributes) {
        attribute.clearUpdateRanges();
        if (count) attribute.addUpdateRange(0, count * attribute.itemSize);
        attribute.needsUpdate = true;
      }
    },
    clear() {
      geometry.instanceCount = 0;
    },
  };
}

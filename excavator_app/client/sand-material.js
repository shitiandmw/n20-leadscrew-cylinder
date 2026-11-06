import * as THREE from "three";

// Fine, seamless sand grain texture. It multiplies the sand colour, so it is
// kept near white; a few darker mineral grains break up the surface.
export function sandTexture(renderer) {
  const size = 512,
    canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const c = canvas.getContext("2d"),
    image = c.createImageData(size, size),
    d = image.data;
  let seed = 11;
  const random = () =>
    (seed = (1664525 * seed + 1013904223) >>> 0) / 4294967296;
  for (let i = 0; i < size * size; i++) {
    const v = 0.84 + random() * 0.18,
      mineral = random() < 0.035 ? 0.72 + random() * 0.2 : 1;
    d[4 * i] = 255 * Math.min(1, v * mineral);
    d[4 * i + 1] = 255 * Math.min(1, v * 0.985 * mineral);
    d[4 * i + 2] = 255 * Math.min(1, v * 0.95 * mineral);
    d[4 * i + 3] = 255;
  }
  c.putImageData(image, 0, 0);
  for (let k = 0; k < 2400; k++) {
    const x = random() * size,
      y = random() * size,
      r = 0.6 + random() * 1.3,
      l = 165 + random() * 90;
    c.fillStyle = `rgb(${l | 0},${(l * 0.96) | 0},${(l * 0.88) | 0})`;
    for (const [ox, oy] of [
      [0, 0],
      [size, 0],
      [-size, 0],
      [0, size],
      [0, -size],
    ]) {
      c.beginPath();
      c.arc(x + ox, y + oy, r, 0, 2 * Math.PI);
      c.fill();
    }
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
  return texture;
}

const wrap = (value, size) => ((value % size) + size) % size;

// Add a soft blob to a square field that repeats at its edges.
function splat(field, size, x, y, radius, amount) {
  const reach = Math.ceil(radius * 2.6),
    x0 = Math.floor(x),
    y0 = Math.floor(y),
    scale = -0.5 / (radius * radius);
  for (let j = -reach; j <= reach; j++) {
    const dy = y0 + j - y,
      row = wrap(y0 + j, size) * size;
    for (let i = -reach; i <= reach; i++) {
      const dx = x0 + i - x;
      field[row + wrap(x0 + i, size)] +=
        amount * Math.exp(scale * (dx * dx + dy * dy));
    }
  }
}

// What a falling stream looks like up close, one 32 mm tile. Red holds single
// 0.5 mm grains, averaging 0.4 so that its mipmaps fade to the same coverage from
// far away. Green holds the clumps a stream breaks up into, averaging 0.5.
export function streakTexture() {
  const size = 256,
    grains = new Float32Array(size * size),
    clumps = new Float32Array(size * size);
  let seed = 7;
  const random = () =>
    (seed = (1664525 * seed + 1013904223) >>> 0) / 4294967296;
  for (let k = 0; k < 5200; k++)
    splat(grains, size, random() * size, random() * size, 1.5, 1);
  for (let k = 0; k < 90; k++)
    splat(
      clumps,
      size,
      random() * size,
      random() * size,
      5 + random() * 18,
      random() < 0.5 ? -1 : 1,
    );
  const mean = (field) => field.reduce((sum, v) => sum + v, 0) / field.length,
    deviation = (field, average) =>
      Math.sqrt(
        field.reduce((sum, v) => sum + (v - average) ** 2, 0) / field.length,
      ),
    grainMean = mean(grains),
    clumpMean = mean(clumps),
    clumpSpread = deviation(clumps, clumpMean),
    data = new Uint8Array(size * size * 4);
  for (let n = 0; n < size * size; n++) {
    data[4 * n] = 255 * Math.min(1, (0.4 * grains[n]) / grainMean);
    data[4 * n + 1] =
      255 *
      Math.max(
        0,
        Math.min(1, 0.5 + (0.28 * (clumps[n] - clumpMean)) / clumpSpread),
      );
    data[4 * n + 3] = 255;
  }
  const texture = new THREE.DataTexture(data, size, size, THREE.RGBAFormat);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.magFilter = THREE.LinearFilter;
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.generateMipmaps = true;
  texture.needsUpdate = true;
  return texture;
}

// Lumps from half a millimetre to a few centimetres, one 256 mm tile. Red and green
// hold the slope along x and y around 0.5, and blue the height around 0.5. Their
// mipmaps fade to no relief at all, so distant sand does not sparkle.
export function lumpTexture(renderer) {
  const size = 512,
    height = new Float32Array(size * size);
  let seed = 23;
  const random = () =>
    (seed = (1664525 * seed + 1013904223) >>> 0) / 4294967296;
  // Many small and few large. Radius in texels of 0.5 mm, how many, how high.
  for (const [radius, number, amount] of [
    [1.5, 9000, 0.3],
    [3, 3200, 0.55],
    [6, 800, 1],
    [12, 200, 1.7],
    [24, 40, 2.6],
  ])
    for (let k = 0; k < number; k++)
      splat(
        height,
        size,
        random() * size,
        random() * size,
        radius * (0.7 + 0.6 * random()),
        amount * (random() < 0.5 ? -1 : 1) * (0.5 + random()),
      );
  const at = (i, j) => height[wrap(j, size) * size + wrap(i, size)];
  let meanHeight = 0,
    spreadHeight = 0,
    spreadSlope = 0;
  const slopes = new Float32Array(size * size * 2);
  for (let j = 0; j < size; j++)
    for (let i = 0; i < size; i++) {
      const n = j * size + i,
        sx = at(i + 1, j) - at(i - 1, j),
        sy = at(i, j + 1) - at(i, j - 1);
      slopes[2 * n] = sx;
      slopes[2 * n + 1] = sy;
      spreadSlope += sx * sx + sy * sy;
      meanHeight += height[n];
    }
  meanHeight /= height.length;
  for (const value of height) spreadHeight += (value - meanHeight) ** 2;
  spreadHeight = Math.sqrt(spreadHeight / height.length);
  spreadSlope = Math.sqrt(spreadSlope / (2 * height.length));
  const data = new Uint8Array(size * size * 4),
    byte = (value) => 255 * Math.max(0, Math.min(1, value));
  for (let n = 0; n < size * size; n++) {
    data[4 * n] = byte(0.5 + (0.2 * slopes[2 * n]) / spreadSlope);
    data[4 * n + 1] = byte(0.5 + (0.2 * slopes[2 * n + 1]) / spreadSlope);
    data[4 * n + 2] = byte(
      0.5 + (0.2 * (height[n] - meanHeight)) / spreadHeight,
    );
    data[4 * n + 3] = 255;
  }
  const texture = new THREE.DataTexture(data, size, size, THREE.RGBAFormat);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.magFilter = THREE.LinearFilter;
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.generateMipmaps = true;
  texture.anisotropy = Math.min(4, renderer.capabilities.getMaxAnisotropy());
  texture.needsUpdate = true;
  return texture;
}

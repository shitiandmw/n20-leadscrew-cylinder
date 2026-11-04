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

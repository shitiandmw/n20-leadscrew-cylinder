import * as THREE from "three";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { WORLD, YARD, POUR_ZONE } from "../shared/world.js";
import {
  BEACH,
  GROUND,
  WATER,
  groundHeight,
  groundSample,
  landscape,
  noise,
} from "../shared/landscape.js";

const SIZE = WORLD.maxX - WORLD.minX;
const clamp01 = (v) => Math.max(0, Math.min(1, v));
const smooth = (a, b, x) => {
  const t = clamp01((x - a) / (b - a));
  return t * t * (3 - 2 * t);
};
const rgb = (hex) => [(hex >> 16) & 255, (hex >> 8) & 255, hex & 255];
const blend = (a, b, t) => a.map((v, k) => v + (b[k] - v) * t);
// Horizon colour shared by the sky and the distance fog (linear light).
const HORIZON = new THREE.Color(0.74, 0.8, 0.86);

// ------------------------------------------------------------ ground colours
// Everything is painted once into one canvas: hills from noise, then the
// site, roads and footprints on top. North (+Y) is at the top of the canvas,
// so it doubles as the minimap.
function paintGround(land, size) {
  const coarse = 640,
    low = document.createElement("canvas");
  low.width = low.height = coarse;
  const lowContext = low.getContext("2d", { willReadFrequently: true }),
    image = lowContext.createImageData(coarse, coarse),
    sample = [0, 0, 0];
  const meadow = rgb(0x6c8a49),
    fresh = rgb(0x7f9c50),
    dry = rgb(0xa09556),
    dirt = rgb(0x8a7650),
    rock = rgb(0x8d877c),
    snowline = rgb(0xb2aea2),
    silt = rgb(0xa89a70),
    deep = rgb(0x3f6b70);
  for (let py = 0; py < coarse; py++)
    for (let px = 0; px < coarse; px++) {
      const x = WORLD.minX + ((px + 0.5) / coarse) * SIZE,
        y = WORLD.maxY - ((py + 0.5) / coarse) * SIZE;
      groundSample(x, y, sample);
      const slope = Math.hypot(sample[1], sample[2]),
        h = sample[0],
        tone = noise(x / 2600 + 3.7, y / 2600 + 1.2) + 0.5,
        fine = noise(x / 520 + 8.1, y / 520 + 6.6) + 0.5,
        patch = noise(x / 1400 + 5.3, y / 1400 + 2.8) + 0.5;
      let c = blend(meadow, fresh, smooth(0.3, 0.72, tone));
      c = blend(c, dry, smooth(0.52, 0.8, patch) * 0.8);
      c = blend(c, dirt, smooth(0.62, 0.9, fine * patch * 1.7) * 0.6);
      c = blend(c, rock, smooth(0.5, 0.85, slope));
      c = blend(c, snowline, smooth(2200, 3200, h));
      c = blend(c, silt, smooth(WATER.level + 70, WATER.level - 10, h));
      c = blend(c, deep, smooth(WATER.level - 50, WATER.level - 330, h));
      const o = 4 * (py * coarse + px),
        grainTone = 0.96 + 0.08 * fine;
      image.data[o] = c[0] * grainTone;
      image.data[o + 1] = c[1] * grainTone;
      image.data[o + 2] = c[2] * grainTone;
      image.data[o + 3] = 255;
    }
  lowContext.putImageData(image, 0, 0);
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  // This canvas is painted once and never redrawn, so it stays in main memory.
  const main = canvas.getContext("2d", { willReadFrequently: true });
  main.imageSmoothingQuality = "high";
  main.drawImage(low, 0, 0, size, size);
  let g = main;
  const px = (x) => ((x - WORLD.minX) / SIZE) * size,
    py = (y) => ((WORLD.maxY - y) / SIZE) * size,
    mm = (v) => (v / SIZE) * size;
  // Paint small and scale up: the enlargement softens every edge for the cost
  // of one image draw, and it works in browsers without canvas filters.
  const soft = (blur, paint) => {
    const factor = Math.max(1, blur / 1.6),
      layer = document.createElement("canvas");
    layer.width = layer.height = Math.ceil(size / factor);
    g = layer.getContext("2d", { willReadFrequently: true });
    g.scale(1 / factor, 1 / factor);
    paint();
    g = main;
    g.drawImage(layer, 0, 0, layer.width * factor, layer.height * factor);
  };
  const rect = (minX, maxX, minY, maxY) =>
    g.fillRect(px(minX), py(maxY), mm(maxX - minX), mm(maxY - minY));
  // Roads: a soft verge, the surface, and two pale wheel paths.
  const stroke = (path, width, style) => {
    g.lineJoin = g.lineCap = "round";
    g.lineWidth = mm(width);
    g.strokeStyle = style;
    g.beginPath();
    path.forEach(([x, y], k) =>
      k ? g.lineTo(px(x), py(y)) : g.moveTo(px(x), py(y)),
    );
    g.stroke();
  };
  soft(mm(30), () => {
    for (const path of land.paths) stroke(path, 520, "#7d7252");
  });
  for (const path of land.paths) stroke(path, 340, "#8f7e61");
  soft(mm(9), () => {
    for (const path of land.paths) {
      const offset = (side) =>
        path.map(([x, y], k) => {
          const a = path[Math.max(0, k - 1)],
            b = path[Math.min(path.length - 1, k + 1)],
            dx = b[0] - a[0],
            dy = b[1] - a[1],
            d = Math.hypot(dx, dy) || 1;
          return [x - (side * 80 * dy) / d, y + (side * 80 * dx) / d];
        });
      stroke(offset(-1), 46, "#a3917a");
      stroke(offset(1), 46, "#a3917a");
    }
  });
  // The work site: gravel around the machine's start, sand under the yard.
  soft(mm(190), () => {
    g.fillStyle = "#86765a";
    rect(-2250, 900, -1650, 1800);
    g.fillStyle = "#7f7157";
    rect(5900, 7500, -3900, 3900);
    rect(170, 6900, -3950, -3150);
    rect(170, 6900, 3150, 3950);
  });
  // Worn, uneven ground: patches of darker earth and pale gravel.
  soft(mm(34), () => {
    let seed = 4242;
    const random = () =>
      (seed = (1664525 * seed + 1013904223) >>> 0) / 4294967296;
    for (let k = 0; k < 260; k++) {
      const x = -2300 + random() * 3200,
        y = -1700 + random() * 3500,
        r = 50 + 240 * random() * random();
      g.fillStyle =
        random() < 0.55
          ? `rgba(92, 76, 52, ${0.1 + 0.2 * random()})`
          : `rgba(204, 190, 158, ${0.08 + 0.18 * random()})`;
      g.beginPath();
      g.ellipse(px(x), py(y), mm(r), mm(r * (0.45 + 0.5 * random())), random() * 3, 0, 7);
      g.fill();
    }
  });
  // Tyre tracks across the site, from the road to the yard and the pad.
  soft(mm(7), () => {
    g.lineCap = "round";
    g.lineWidth = mm(34);
    g.strokeStyle = "rgba(70, 58, 40, 0.34)";
    for (const [y0, y1, y2, shift] of [
      [-60, -30, 40, 0],
      [-60, 120, 300, 90],
      [-60, -220, -480, -60],
    ])
      for (const side of [-58, 58]) {
        g.beginPath();
        g.moveTo(px(-1200), py(y0 + side));
        g.bezierCurveTo(
          px(-700),
          py(y1 + side),
          px(-300 + shift),
          py(y2 + side),
          px(120),
          py(y2 + side),
        );
        g.stroke();
      }
  });
  soft(mm(70), () => {
    g.fillStyle = "#c8ad80";
    rect(YARD.minX, YARD.maxX, YARD.minY, YARD.notchMinY);
    rect(YARD.notchMaxX, YARD.maxX, YARD.notchMinY - 10, YARD.maxY);
    g.fillStyle = "#d8c398";
    rect(BEACH.minX, BEACH.maxX, BEACH.minY, BEACH.maxY - 70);
  });
  // The pad where sand is delivered.
  g.fillStyle = "#c6c3b8";
  const pad = POUR_ZONE;
  rect(pad.minX - 40, pad.maxX + 40, pad.minY - 40, pad.maxY + 40);
  // Shaded ground under things that stand on it.
  g.fillStyle = "rgba(38, 46, 30, 0.34)";
  for (const p of land.props) {
    const radius = {
      pine: 0.17,
      broadleaf: 0.3,
    }[p.kind];
    if (!radius) continue;
    g.beginPath();
    g.arc(px(p.x + 0.09 * p.size), py(p.y + 0.09 * p.size), mm(radius * p.size), 0, 7);
    g.fill();
  }
  return canvas;
}

// A small tiling noise that adds grain to the painted ground.
function detailTexture(renderer) {
  const size = 256,
    canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const c = canvas.getContext("2d"),
    image = c.createImageData(size, size);
  let seed = 77;
  const random = () =>
    (seed = (1664525 * seed + 1013904223) >>> 0) / 4294967296;
  for (let i = 0; i < size * size; i++) {
    const v = 90 + random() * 165;
    image.data.set([v, v, v, 255], 4 * i);
  }
  c.putImageData(image, 0, 0);
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
  return texture;
}

function buildGround(scene, land, map, detail) {
  const material = new THREE.MeshStandardMaterial({
    map,
    roughness: 0.96,
    metalness: 0,
  });
  material.onBeforeCompile = (shader) => {
    shader.uniforms.groundDetail = { value: detail };
    shader.vertexShader = shader.vertexShader
      .replace(
        "#include <common>",
        "#include <common>\nvarying vec2 vGroundXY;",
      )
      .replace(
        "#include <begin_vertex>",
        "#include <begin_vertex>\nvGroundXY = position.xy;",
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        "#include <common>\nuniform sampler2D groundDetail;\nvarying vec2 vGroundXY;",
      )
      .replace(
        "#include <map_fragment>",
        "#include <map_fragment>\ndiffuseColor.rgb *= 0.78 + 0.44 * texture2D(groundDetail, vGroundXY / 340.0).r;\ndiffuseColor.rgb *= 0.86 + 0.28 * texture2D(groundDetail, vGroundXY / 2900.0).r;",
      );
  };
  const S = GROUND.side,
    PATCH = 32,
    spacing = GROUND.spacing,
    heights = land.heights;
  const at = (i, j) =>
    heights[
      Math.max(0, Math.min(S - 1, j)) * S + Math.max(0, Math.min(S - 1, i))
    ];
  const index = new Uint16Array(PATCH * PATCH * 6),
    side = PATCH + 1;
  for (let j = 0, o = 0; j < PATCH; j++)
    for (let i = 0; i < PATCH; i++, o += 6) {
      const a = j * side + i,
        b = a + 1,
        c = a + side,
        d = c + 1;
      // Same diagonal as groundHeight(), so the physics matches this surface.
      index.set([a, b, d, a, d, c], o);
    }
  const indexAttribute = new THREE.BufferAttribute(index, 1);
  for (let row = 0; row < GROUND.quads / PATCH; row++)
    for (let col = 0; col < GROUND.quads / PATCH; col++) {
      const position = new Float32Array(side * side * 3),
        normal = new Float32Array(side * side * 3),
        uv = new Float32Array(side * side * 2);
      for (let b = 0; b < side; b++)
        for (let a = 0; a < side; a++) {
          const i = col * PATCH + a,
            j = row * PATCH + b,
            v = b * side + a,
            x = WORLD.minX + i * spacing,
            y = WORLD.minY + j * spacing,
            dx = (at(i + 1, j) - at(i - 1, j)) / (2 * spacing),
            dy = (at(i, j + 1) - at(i, j - 1)) / (2 * spacing),
            n = 1 / Math.sqrt(1 + dx * dx + dy * dy);
          position.set([x, y, at(i, j)], 3 * v);
          normal.set([-dx * n, -dy * n, n], 3 * v);
          uv.set([(x - WORLD.minX) / SIZE, (y - WORLD.minY) / SIZE], 2 * v);
        }
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(position, 3));
      geometry.setAttribute("normal", new THREE.BufferAttribute(normal, 3));
      geometry.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
      geometry.setIndex(indexAttribute);
      const mesh = new THREE.Mesh(geometry, material);
      mesh.receiveShadow = true;
      scene.add(mesh);
    }
}

// ------------------------------------------------------------------ the sky
// Painted once into a small texture: the frame then only pays for one texture
// lookup per pixel, which matters on phones and software renderers. Colours are
// linear light, so the sky's horizon and the distance fog end up identical.
function buildSky(scene, sunDirection) {
  const width = 1024,
    height = 384,
    canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d"),
    image = context.createImageData(width, height),
    zenith = [0.16, 0.34, 0.66],
    encode = (v) =>
      255 *
      (v <= 0.0031308
        ? 12.92 * Math.max(0, v)
        : 1.055 * Math.min(1, v) ** (1 / 2.4) - 0.055);
  const fbm = (x, y) => {
    let value = 0,
      amplitude = 0.5,
      px = x,
      py = y;
    for (let k = 0; k < 5; k++) {
      value += amplitude * (noise(px, py) + 0.5);
      px = px * 2.03 + 13.7;
      py = py * 2.03 + 7.1;
      amplitude *= 0.5;
    }
    return value;
  };
  for (let row = 0; row < height; row++) {
    // The texture holds the upper hemisphere and a band just below the horizon.
    const elevation = ((1 - (row + 0.5) / height) * 1.08 - 0.08) * (Math.PI / 2),
      z = Math.sin(elevation),
      flat = Math.cos(elevation),
      up = Math.max(0, z),
      mixUp = up ** 0.55;
    for (let column = 0; column < width; column++) {
      const azimuth = ((column + 0.5) / width) * 2 * Math.PI,
        dx = flat * Math.cos(azimuth),
        dy = flat * Math.sin(azimuth),
        sun = Math.max(
          0,
          dx * sunDirection.x + dy * sunDirection.y + z * sunDirection.z,
        ),
        glow = 0.2 * sun ** 18 + 1.6 * sun ** 900;
      const color = [
        HORIZON.r + (zenith[0] - HORIZON.r) * mixUp + glow,
        HORIZON.g + (zenith[1] - HORIZON.g) * mixUp + glow * 0.86,
        HORIZON.b + (zenith[2] - HORIZON.b) * mixUp + glow * 0.62,
      ];
      if (z > 0.01) {
        const scale = 1.3 / (z + 0.12),
          shape = fbm(dx * scale + 3.1, dy * scale + 1.7),
          cloud = smooth(0.5, 0.68, shape) * smooth(0.01, 0.16, z) * 0.86,
          lit = 0.82 + 0.33 * smooth(0.54, 0.76, shape);
        color[0] += (lit - color[0]) * cloud;
        color[1] += (lit * 1.01 - color[1]) * cloud;
        color[2] += (lit * 1.04 - color[2]) * cloud;
      }
      const o = 4 * (row * width + column);
      image.data[o] = encode(color[0]);
      image.data[o + 1] = encode(color[1]);
      image.data[o + 2] = encode(color[2]);
      image.data[o + 3] = 255;
    }
  }
  context.putImageData(image, 0, 0);
  const map = new THREE.CanvasTexture(canvas);
  map.colorSpace = THREE.SRGBColorSpace;
  map.wrapS = THREE.RepeatWrapping;
  // A sphere with its pole on +Z: u is the azimuth and v the elevation band.
  const geometry = new THREE.SphereGeometry(1, 48, 24, 0, Math.PI * 2, 0, Math.PI);
  geometry.rotateX(Math.PI / 2);
  const position = geometry.attributes.position,
    uv = geometry.attributes.uv;
  for (let k = 0; k < position.count; k++) {
    const elevation = Math.asin(Math.max(-1, Math.min(1, position.getZ(k))));
    // The sphere's own u runs half a turn away from the painted azimuth.
    uv.setXY(
      k,
      uv.getX(k) - 0.5,
      Math.max(0, (elevation / (Math.PI / 2) + 0.08) / 1.08),
    );
  }
  const material = new THREE.MeshBasicMaterial({
    map,
    side: THREE.BackSide,
    depthWrite: false,
    depthTest: false,
    fog: false,
  });
  material.onBeforeCompile = (shader) => {
    // Always behind everything, whatever the camera's far plane.
    shader.vertexShader = shader.vertexShader.replace(
      "#include <project_vertex>",
      "#include <project_vertex>\ngl_Position = gl_Position.xyww;",
    );
  };
  const sky = new THREE.Mesh(geometry, material);
  sky.frustumCulled = false;
  sky.renderOrder = -10;
  scene.add(sky);
  return sky;
}

// Far hills beyond the walkable ridge, on a polar grid that fog dissolves.
function buildDistance(scene) {
  const rings = 26,
    segments = 180,
    position = [],
    color = [],
    index = [];
  const near = new THREE.Color("#6e7f62"),
    far = new THREE.Color("#7b8ea0"),
    c = new THREE.Color();
  for (let r = 0; r <= rings; r++) {
    const t = r / rings;
    for (let s = 0; s <= segments; s++) {
      // The first ring traces the world's square edge, just inside it.
      const a = ((s % segments) / segments) * Math.PI * 2,
        ca = Math.cos(a),
        sa = Math.sin(a),
        radius =
          (WORLD.maxX - 300) / Math.max(Math.abs(ca), Math.abs(sa)) +
          190000 * t * t,
        x = ca * radius,
        y = sa * radius,
        px = x,
        py = y,
        peaks =
          0.62 * (noise(px / 26000 + 4.2, py / 26000 + 9.5) + 0.5) +
          0.3 * (noise(px / 9800 + 7.3, py / 9800 + 1.1) + 0.5) +
          0.08 * (noise(px / 3300 + 2.4, py / 3300 + 6.8) + 0.5),
        // Hidden behind the ridge at first, then rising to the far range.
        height = 1200 + smooth(0.03, 0.42, t) * (800 + 19000 * peaks * peaks);
      position.push(x, y, height);
      c.copy(near).lerp(far, smooth(0.1, 0.6, t));
      c.multiplyScalar(0.86 + 0.28 * peaks);
      color.push(c.r, c.g, c.b);
    }
  }
  for (let r = 0; r < rings; r++)
    for (let s = 0; s < segments; s++) {
      const a = r * (segments + 1) + s,
        b = a + 1,
        d = a + segments + 1,
        e = d + 1;
      index.push(a, b, e, a, e, d);
    }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(position, 3),
  );
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(color, 3));
  geometry.setIndex(index);
  geometry.computeVertexNormals();
  const mesh = new THREE.Mesh(
    geometry,
    new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 1 }),
  );
  mesh.frustumCulled = false;
  scene.add(mesh);
}

function buildWater(scene) {
  const mesh = new THREE.Mesh(
    new THREE.CircleGeometry(WATER.radius * 1.5, 64),
    new THREE.MeshStandardMaterial({
      color: "#3e8596",
      roughness: 0.16,
      metalness: 0.15,
      transparent: true,
      opacity: 0.8,
      depthWrite: false,
    }),
  );
  mesh.position.set(WATER.x, WATER.y, WATER.level);
  scene.add(mesh);
}

// ------------------------------------------------------------------ scenery
// A list of coloured shapes merged into one geometry.
class Parts {
  constructor() {
    this.parts = [];
    this.matrix = new THREE.Matrix4();
    this.color = new THREE.Color();
    this.place = new THREE.Vector3();
    this.turn = new THREE.Quaternion();
    this.euler = new THREE.Euler();
    this.scale = new THREE.Vector3(1, 1, 1);
  }
  add(geometry, color, x, y, z, rotZ = 0, rotX = 0, rotY = 0) {
    let g = geometry.index ? geometry.toNonIndexed() : geometry.clone();
    g.deleteAttribute("uv");
    this.euler.set(rotX, rotY, rotZ, "ZYX");
    this.turn.setFromEuler(this.euler);
    this.place.set(x, y, z);
    this.matrix.compose(this.place, this.turn, this.scale);
    g.applyMatrix4(this.matrix);
    g.computeVertexNormals();
    this.color.set(color);
    const n = g.attributes.position.count,
      colors = new Float32Array(n * 3);
    for (let i = 0; i < n; i++)
      colors.set([this.color.r, this.color.g, this.color.b], 3 * i);
    g.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    this.parts.push(g);
    return this;
  }
  // A box of width w (x), depth d (y) and height h with its base at z.
  box(w, d, h, x, y, z, color, rotZ = 0) {
    return this.add(
      new THREE.BoxGeometry(w, d, h),
      color,
      x,
      y,
      z + h / 2,
      rotZ,
    );
  }
  // An upright cylinder with its base at z.
  cylinder(top, bottom, h, x, y, z, color, segments = 12) {
    return this.add(
      new THREE.CylinderGeometry(top, bottom, h, segments).rotateX(Math.PI / 2),
      color,
      x,
      y,
      z + h / 2,
    );
  }
  // A gable roof ridge along x, over a w by d footprint, eaves at z.
  gable(w, d, h, x, y, z, color, rotZ = 0) {
    const hw = w / 2,
      hd = d / 2,
      p = [
        [-hw, -hd, 0],
        [hw, -hd, 0],
        [hw, 0, h],
        [-hw, 0, h],
        [-hw, hd, 0],
        [hw, hd, 0],
      ],
      faces = [
        [0, 1, 2],
        [0, 2, 3],
        [5, 4, 3],
        [5, 3, 2],
        [1, 5, 2],
        [4, 0, 3],
        [4, 5, 1],
        [4, 1, 0],
      ],
      position = [];
    for (const f of faces) for (const v of f) position.push(...p[v]);
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(position, 3));
    return this.add(g, color, x, y, z, rotZ);
  }
  geometry() {
    const merged = mergeGeometries(this.parts);
    for (const part of this.parts) part.dispose();
    this.parts = [];
    return merged;
  }
}

// Draw a part of a building placed at (px, py) and turned by rot: lx and ly
// are relative to the building.
function placer(parts, p, z) {
  const c = Math.cos(p.rot),
    s = Math.sin(p.rot);
  const at = (lx, ly) => [p.x + lx * c - ly * s, p.y + lx * s + ly * c];
  return {
    box(w, d, h, lx, ly, lz, color, turn = 0) {
      const [x, y] = at(lx, ly);
      parts.box(w, d, h, x, y, z + lz, color, p.rot + turn);
    },
    cylinder(top, bottom, h, lx, ly, lz, color, segments) {
      const [x, y] = at(lx, ly);
      parts.cylinder(top, bottom, h, x, y, z + lz, color, segments);
    },
    gable(w, d, h, lx, ly, lz, color, turn = 0) {
      const [x, y] = at(lx, ly);
      parts.gable(w, d, h, x, y, z + lz, color, p.rot + turn);
    },
    wheel(radius, width, lx, ly, lz, color) {
      const [x, y] = at(lx, ly);
      parts.add(
        new THREE.CylinderGeometry(radius, radius, width, 14),
        color,
        x,
        y,
        z + lz,
        p.rot,
      );
    },
  };
}

const BUILDERS = {
  office(b) {
    b.box(640, 250, 16, 0, 0, 0, "#6d6a60");
    b.box(630, 240, 180, 0, 0, 16, "#e7e2d2");
    b.box(650, 256, 12, 0, 0, 196, "#7c8a84");
    b.box(560, 4, 12, 0, -122, 92, "#e0a93b");
    for (const x of [-220, -80, 90, 230])
      b.box(84, 4, 66, x, -121.5, 102, "#3e5968");
    b.box(66, 4, 130, 0, -121.5, 22, "#59605c");
    b.box(90, 50, 12, 0, -150, 6, "#8b8f85");
  },
  container(b, p) {
    const color = ["#a5482f", "#336f88", "#c79a2e"][p.size];
    b.box(400, 160, 170, 0, 0, 0, color);
    for (let x = -180; x <= 180; x += 40) {
      b.box(10, 164, 150, x, 0, 10, color);
    }
    b.box(404, 164, 8, 0, 0, 170, "#5c5e58");
  },
  shed(b) {
    b.box(800, 600, 250, 0, 0, 0, "#9aa39b");
    b.gable(830, 640, 150, 0, 0, 250, "#6c7a7c");
    b.box(300, 6, 200, 0, -301, 0, "#49504d");
    b.box(60, 6, 60, 300, -301, 110, "#3e5968");
    b.box(60, 6, 60, -300, -301, 110, "#3e5968");
  },
  fueltank(b, p) {
    b.box(60, 200, 60, -130, 0, 0, "#5c5e58");
    b.box(60, 200, 60, 130, 0, 0, "#5c5e58");
    const [x, y, z] = [p.x, p.y, p.z + 150];
    b.parts.add(
      new THREE.CylinderGeometry(95, 95, 400, 18).rotateZ(Math.PI / 2),
      "#c9cdc3",
      x,
      y,
      z,
    );
    b.box(26, 26, 60, 0, 0, 240, "#5c5e58");
    b.box(410, 6, 26, 0, -94, 140, "#c2412d");
  },
  truck(b) {
    b.box(820, 170, 34, 0, 0, 60, "#2f3236");
    for (const x of [-320, -210, 300])
      for (const y of [-92, 92]) b.wheel(62, 44, x, y, 62, "#1f2123");
    // The cab.
    b.box(220, 240, 180, 290, 0, 92, "#2f6f9a");
    b.box(8, 210, 86, 402, 0, 178, "#28404e");
    b.box(180, 6, 76, 288, -121, 178, "#28404e");
    b.box(180, 6, 76, 288, 121, 178, "#28404e");
    b.box(230, 246, 14, 290, 0, 272, "#245a7e");
    b.box(30, 250, 18, 408, 0, 80, "#c9cdc3");
    // The dump body.
    b.box(560, 256, 16, -110, 0, 104, "#c25a2b");
    b.box(560, 12, 130, -110, -122, 118, "#c25a2b");
    b.box(560, 12, 130, -110, 122, 118, "#c25a2b");
    b.box(12, 256, 150, 168, 0, 118, "#c25a2b");
    b.box(12, 256, 90, -388, 0, 118, "#a94d24");
  },
  sign(b) {
    b.box(10, 10, 170, -130, 0, 0, "#5c5e58");
    b.box(10, 10, 170, 130, 0, 0, "#5c5e58");
    b.box(320, 8, 100, 0, 0, 120, "#e4b34e");
  },
  lighttower(b) {
    b.box(170, 90, 36, 0, 0, 16, "#c9a227");
    b.wheel(22, 14, 0, -52, 22, "#1f2123");
    b.wheel(22, 14, 0, 52, 22, "#1f2123");
    b.cylinder(7, 11, 640, 0, 0, 50, "#7c8a84", 8);
    b.box(130, 16, 42, 0, 0, 676, "#3c3f3e");
    for (const x of [-46, 0, 46]) b.box(36, 6, 30, x, -10, 682, "#f6f2d4");
  },
  barrier(b) {
    b.box(260, 44, 20, 0, 0, 0, "#c6c3b8");
    b.box(250, 20, 56, 0, 0, 20, "#d3d0c5");
    b.box(60, 21, 14, -60, 0, 44, "#c2412d");
    b.box(60, 21, 14, 60, 0, 44, "#c2412d");
  },
  cone(b) {
    b.box(40, 40, 4, 0, 0, 0, "#2b2d2c");
    b.cylinder(4, 16, 64, 0, 0, 4, "#e8642c", 10);
    b.cylinder(10, 12, 12, 0, 0, 24, "#f4f0e4", 10);
  },
  house(b, p) {
    const walls = ["#e9dfc9", "#d6c7a8", "#c9d1c4", "#e2cdb4"][
        Math.abs(Math.round(p.x)) % 4
      ],
      roof = ["#a14c35", "#70574a", "#55625e"][Math.abs(Math.round(p.y)) % 3];
    b.box(660, 500, 250, 0, 0, 0, walls);
    b.gable(710, 560, 190, 0, 0, 250, roof);
    b.box(84, 6, 150, 0, -251, 0, "#5b4634");
    for (const x of [-190, 190]) b.box(90, 6, 90, x, -251, 120, "#3e5968");
    b.box(56, 56, 120, 220, 110, 320, "#8b7f73");
  },
  watertower(b) {
    for (const [x, y] of [
      [-170, -170],
      [170, -170],
      [-170, 170],
      [170, 170],
    ])
      b.box(20, 20, 900, x, y, 0, "#7c8a84");
    b.box(380, 12, 12, 0, -170, 440, "#7c8a84");
    b.box(380, 12, 12, 0, 170, 440, "#7c8a84");
    b.box(12, 380, 12, -170, 0, 440, "#7c8a84");
    b.box(12, 380, 12, 170, 0, 440, "#7c8a84");
    b.cylinder(250, 250, 300, 0, 0, 900, "#c9d5d4", 20);
    b.cylinder(10, 262, 90, 0, 0, 1200, "#8d9c9c", 20);
  },
  barn(b) {
    b.box(1000, 680, 300, 0, 0, 0, "#964f39");
    b.gable(1040, 740, 240, 0, 0, 300, "#4d4a44");
    b.box(300, 6, 240, 0, -341, 0, "#e9dfc9");
  },
  silo(b) {
    b.cylinder(140, 140, 700, 0, 0, 0, "#c8cbc6", 18);
    b.cylinder(8, 146, 90, 0, 0, 700, "#92989a", 18);
  },
  crusher(b) {
    b.box(920, 600, 120, 0, 0, 0, "#59605c");
    b.box(360, 360, 360, -180, 0, 120, "#c79a2e");
    b.box(220, 220, 170, -180, 0, 480, "#a07a22");
    b.parts.add(
      new THREE.BoxGeometry(980, 110, 24).rotateY(-0.42),
      "#3c3f3e",
      b.world(460, 0)[0],
      b.world(460, 0)[1],
      b.z + 420,
      b.rot,
    );
    for (const x of [420, 760]) b.box(22, 90, 330, x, 0, 80, "#59605c");
  },
  pier(b, p) {
    for (let y = -900; y <= 700; y += 200)
      for (const x of [-92, 92])
        b.box(22, 22, 420, x, y, -420 + (WATER.level + 30 - p.z), "#6b5a45");
    b.box(230, 1720, 14, 0, -100, WATER.level + 30 - p.z, "#8d7656");
  },
  turbine(b) {
    b.cylinder(44, 80, 3300, 0, 0, 0, "#e9ebe6", 16);
    b.box(240, 90, 90, 40, 0, 3290, "#dcdeda");
    const hub = b.world(170, 0);
    for (let k = 0; k < 3; k++) {
      const a = 0.35 + (k * Math.PI * 2) / 3;
      b.parts.add(
        new THREE.BoxGeometry(10, 74, 1500).translate(0, 0, 750),
        "#f0f1ec",
        hub[0],
        hub[1],
        b.z + 3335,
        b.rot,
        a,
      );
    }
  },
  pole(b) {
    b.cylinder(8, 12, 880, 0, 0, 0, "#6b5a45", 8);
    b.box(10, 150, 10, 0, 0, 840, "#5a4b3a");
  },
};

// Conifers and broadleaves share one unit-height geometry per species, and
// each tree is an instance with its own size, turn and tint.
function treeGeometries() {
  const pine = new Parts();
  pine.cylinder(0.022, 0.036, 0.2, 0, 0, 0, "#5b4332", 7);
  const greens = ["#3d6340", "#35583a", "#2f5036"];
  for (const [k, [radius, z, h]] of [
    [0.25, 0.13, 0.42],
    [0.2, 0.36, 0.38],
    [0.14, 0.6, 0.4],
  ].entries())
    pine.add(
      new THREE.ConeGeometry(radius, h, 8).rotateX(Math.PI / 2),
      greens[k],
      0,
      0,
      z + h / 2,
    );
  const leaf = new Parts();
  leaf.cylinder(0.035, 0.055, 0.42, 0, 0, 0, "#5e4835", 7);
  for (const [x, y, z, radius, color] of [
    [0, 0, 0.56, 0.27, "#5e8a45"],
    [0.15, 0.06, 0.45, 0.19, "#527c3e"],
    [-0.13, 0.1, 0.5, 0.2, "#6a964c"],
    [0.02, -0.15, 0.43, 0.18, "#588442"],
    [-0.03, 0.03, 0.77, 0.17, "#6f9b50"],
  ])
    leaf.add(new THREE.IcosahedronGeometry(radius, 1), color, x, y, z);
  return { pine: pine.geometry(), broadleaf: leaf.geometry() };
}

function rockGeometry(seed) {
  const g = new THREE.IcosahedronGeometry(1, 1),
    p = g.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i),
      y = p.getY(i),
      z = p.getZ(i),
      s =
        0.74 +
        0.55 * (noise(x * 1.6 + seed, y * 1.6 + 3.1 * seed) + 0.5) +
        0.12 * (noise(z * 3.1 + seed, x * 3.1) + 0.5);
    p.setXYZ(i, x * s, y * s, z * s * 0.72);
  }
  g.deleteAttribute("uv");
  g.computeVertexNormals();
  return g;
}

function buildScenery(scene, land, mobile) {
  const parts = new Parts();
  const dummy = new THREE.Object3D();
  for (const p of land.props) {
    const build = BUILDERS[p.kind];
    if (!build) continue;
    const z = groundHeight(p.x, p.y),
      b = placer(parts, p, z);
    build(
      {
        ...b,
        parts,
        z,
        rot: p.rot,
        world: (lx, ly) => [
          p.x + lx * Math.cos(p.rot) - ly * Math.sin(p.rot),
          p.y + lx * Math.sin(p.rot) + ly * Math.cos(p.rot),
        ],
      },
      { ...p, z },
    );
  }
  const yellow = "#e4b34e",
    zone = POUR_ZONE,
    x = (zone.minX + zone.maxX) / 2,
    y = (zone.minY + zone.maxY) / 2;
  for (const edge of [zone.minY, zone.maxY])
    parts.box(zone.maxX - zone.minX + 10, 10, 0.5, x, edge, 0.1, yellow);
  for (const edge of [zone.minX, zone.maxX])
    parts.box(10, zone.maxY - zone.minY + 10, 0.5, edge, y, 0.1, yellow);
  const built = new THREE.Mesh(
    parts.geometry(),
    new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.82 }),
  );
  built.castShadow = !mobile;
  built.receiveShadow = true;
  built.frustumCulled = false;
  scene.add(built);

  const trees = treeGeometries(),
    tint = new THREE.Color();
  for (const kind of ["pine", "broadleaf"]) {
    const list = land.props.filter((p) => p.kind === kind),
      mesh = new THREE.InstancedMesh(
        trees[kind],
        new THREE.MeshStandardMaterial({
          vertexColors: true,
          roughness: 0.92,
          flatShading: true,
        }),
        list.length,
      );
    list.forEach((p, k) => {
      dummy.position.set(p.x, p.y, groundHeight(p.x, p.y) - 6);
      dummy.rotation.set(0, 0, p.rot);
      dummy.scale.setScalar(p.size);
      dummy.updateMatrix();
      mesh.setMatrixAt(k, dummy.matrix);
      const shade = 0.82 + 0.4 * (noise(p.x / 500 + 3, p.y / 500) + 0.5);
      tint.setRGB(shade * 1.03, shade, shade * 0.94);
      mesh.setColorAt(k, tint);
    });
    mesh.castShadow = !mobile;
    mesh.receiveShadow = true;
    mesh.frustumCulled = false;
    scene.add(mesh);
  }
  const rocks = land.props.filter(
      (p) => p.kind === "rock" || p.kind === "boulder",
    ),
    rock = new THREE.InstancedMesh(
      rockGeometry(2),
      new THREE.MeshStandardMaterial({
        color: "#99948a",
        roughness: 0.95,
        flatShading: true,
      }),
      rocks.length,
    );
  rocks.forEach((p, k) => {
    dummy.position.set(p.x, p.y, groundHeight(p.x, p.y) + 0.1 * p.size);
    dummy.rotation.set(0.3 * ((k % 5) - 2), 0.2 * ((k % 3) - 1), p.rot);
    dummy.scale.setScalar(p.size);
    dummy.updateMatrix();
    rock.setMatrixAt(k, dummy.matrix);
    tint.setScalar(0.76 + 0.3 * (noise(p.x / 310, p.y / 310) + 0.5));
    rock.setColorAt(k, tint);
  });
  rock.castShadow = !mobile;
  rock.receiveShadow = true;
  rock.frustumCulled = false;
  scene.add(rock);

  // Power lines sag between the poles.
  const poles = land.props.filter((p) => p.kind === "pole"),
    wire = [];
  for (let k = 0; k + 1 < poles.length; k++) {
    const a = poles[k],
      b = poles[k + 1],
      az = groundHeight(a.x, a.y) + 840,
      bz = groundHeight(b.x, b.y) + 840;
    for (const side of [-60, 60])
      for (let s = 0; s < 10; s++)
        for (const t of [s / 10, (s + 1) / 10])
          wire.push(
            a.x + (b.x - a.x) * t,
            a.y + (b.y - a.y) * t + side,
            az + (bz - az) * t - 160 * 4 * t * (1 - t),
          );
  }
  const lines = new THREE.BufferGeometry();
  lines.setAttribute("position", new THREE.Float32BufferAttribute(wire, 3));
  scene.add(
    new THREE.LineSegments(
      lines,
      new THREE.LineBasicMaterial({ color: "#34383a" }),
    ),
  );
}

// Flat text lying on a surface or standing on a sign.
function label(scene, text, x, y, z, width, color, options = {}) {
  const canvas = document.createElement("canvas");
  canvas.width = 1024;
  canvas.height = 160;
  const c = canvas.getContext("2d");
  c.fillStyle = color;
  c.font = "700 92px Inter, Helvetica, Arial, sans-serif";
  c.textAlign = "center";
  c.textBaseline = "middle";
  c.fillText(text, 512, 84);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const mesh = new THREE.Mesh(
    new THREE.PlaneGeometry(width, (width * 160) / 1024),
    new THREE.MeshBasicMaterial({
      map: texture,
      transparent: true,
      depthWrite: false,
      toneMapped: false,
    }),
  );
  mesh.position.set(x, y, z);
  // Read from the west, the way the machine first faces.
  if (options.standing) mesh.rotation.set(Math.PI / 2, 0, -Math.PI / 2, "ZYX");
  else mesh.rotation.z = -Math.PI / 2;
  scene.add(mesh);
}

export function createWorld(scene, renderer, sunDirection, mobile) {
  const land = landscape();
  scene.background = HORIZON.clone();
  scene.fog = new THREE.Fog(HORIZON.clone(), 9000, 150000);
  const canvas = paintGround(land, mobile ? 1024 : 2048),
    map = new THREE.CanvasTexture(canvas);
  map.colorSpace = THREE.SRGBColorSpace;
  map.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
  buildGround(scene, land, map, detailTexture(renderer));
  const sky = buildSky(scene, sunDirection);
  buildDistance(scene);
  buildWater(scene);
  buildScenery(scene, land, mobile);
  label(scene, "POUR ZONE", 440, 355, 0.8, 230, "#a57f27");
  label(scene, "SAND YARD", 35.5, -640, 170, 300, "#26332b", {
    standing: true,
  });
  // A small copy of the painted ground serves as the minimap's background.
  const miniature = document.createElement("canvas");
  miniature.width = miniature.height = 360;
  const smaller = miniature.getContext("2d", { willReadFrequently: true });
  smaller.imageSmoothingQuality = "high";
  smaller.drawImage(canvas, 0, 0, 360, 360);
  return {
    sky,
    map: miniature,
    placeSky(camera) {
      sky.position.copy(camera.position);
    },
  };
}

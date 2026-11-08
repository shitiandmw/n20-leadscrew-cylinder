import * as THREE from "three";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { CONFIG as V } from "../shared/config.js";
import { solve } from "../shared/kinematics.js";
import { PAINTS } from "../shared/players.js";
import { clusterMesh } from "./decimate.js";

// The complete-machine export uses the same frames as the offline X1 viewer:
// ground and upper parts are in the vehicle frame, while R12 arm parts are in
// their body frames. Track modules are in one J9 track frame and are mirrored
// for the right hand side.
const SIMPLE_CELL = 5,
  SHOE_CELL = 6,
  TRACK_LINKS = V.track_links_per_side,
  FAR_CELL = 1.5,
  FULL_FROM_PIXELS_PER_MM = 2 / FAR_CELL,
  DRAW_FIRST = -3,
  trackOf = { 1: 0, "-1": 1 };
const PAINTED = new Set([
  "0.95,0.74,0.22",
  "0.88,0.64,0.16",
  "0.93,0.66,0.1",
  "0.91,0.6,0.07",
]);
const decode = (encoded, Type) => {
  const bytes = Uint8Array.from(atob(encoded), (c) => c.charCodeAt(0));
  return new Type(bytes.buffer);
};
const linear = (r, g, b) => new THREE.Color(r, g, b).convertSRGBToLinear();
const isPainted = (item) => PAINTED.has(item.color.join(","));
const repaint = (paint) => (paint === PAINTS[0] ? null : paint);

function addFarLevel(geometry) {
  const position = geometry.attributes.position.array,
    normal = geometry.attributes.normal.array,
    index = geometry.index.array,
    far = clusterMesh(position, index, FAR_CELL, normal),
    first = position.length / 3,
    vertices = first + far.positions.length / 3,
    joined = (a, b) => {
      const all = new Float32Array(a.length + b.length);
      all.set(a);
      all.set(b, a.length);
      return all;
    },
    indices = new (vertices > 65535 ? Uint32Array : Uint16Array)(
      index.length + far.index.length,
    );
  indices.set(index);
  far.index.forEach((v, i) => (indices[index.length + i] = first + v));
  geometry.setAttribute(
    "position",
    new THREE.BufferAttribute(joined(position, far.positions), 3),
  );
  geometry.setAttribute(
    "normal",
    new THREE.BufferAttribute(joined(normal, far.normals), 3),
  );
  geometry.setIndex(new THREE.BufferAttribute(indices, 1));
  return { full: [0, index.length], far: [index.length, far.index.length] };
}

function geometry(item, simplified = false, cell = SIMPLE_CELL) {
  const source = new THREE.BufferGeometry();
  source.setAttribute(
    "position",
    new THREE.BufferAttribute(decode(item.v, Float32Array), 3),
  );
  source.setIndex(
    new THREE.BufferAttribute(
      decode(item.t, item.wide ? Uint32Array : Uint16Array),
      1,
    ),
  );
  if (!simplified) {
    source.computeVertexNormals();
    return source;
  }
  const { positions, index } = clusterMesh(
    source.attributes.position.array,
    source.index.array,
    cell,
  );
  source.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  source.setIndex(new THREE.BufferAttribute(index, 1));
  source.computeVertexNormals();
  return source;
}

function materialFor(item, paint, materials) {
  const share = repaint(paint) && isPainted(item) ? paint : "";
  const key = `${item.color.join(",")}:${item.kind}:${share}`;
  if (!materials.has(key)) {
    const glass = item.kind === "glazing",
      color = linear(...item.color);
    if (share) color.set(share);
    materials.set(
      key,
      new THREE.MeshStandardMaterial({
        color,
        roughness: glass ? 0.18 : item.kind === "hardware" ? 0.42 : 0.66,
        metalness: item.kind === "hardware" ? 0.55 : 0.12,
        transparent: glass,
        opacity: glass ? 0.42 : 1,
        depthWrite: !glass,
      }),
    );
  }
  return materials.get(key);
}

function armParentFor(mover) {
  if (mover === "upper") return "arm_mount";
  if (mover.startsWith("arm:")) return `arm_${mover.slice(4)}`;
  return mover;
}

function skeleton() {
  const root = new THREE.Group(),
    upper = new THREE.Group(),
    armMount = new THREE.Group(),
    armRoot = new THREE.Group(),
    pinOrigin = new THREE.Group(),
    pinInner = new THREE.Group();
  root.rotation.order = "ZYX";
  root.add(upper);
  upper.add(armMount, pinOrigin);
  armRoot.position.set(...V.arm_offset);
  armMount.add(armRoot);
  pinOrigin.position.set(V.complete.pinion_axis[0], V.complete.pinion_axis[1], 0);
  pinOrigin.add(pinInner);
  pinInner.position.set(-V.complete.pinion_axis[0], -V.complete.pinion_axis[1], 0);
  const groups = {};
  const armGroup = (name) => {
    const key = `arm_${name}`;
    if (!groups[key]) {
      groups[key] = new THREE.Group();
      armRoot.add(groups[key]);
    }
    return groups[key];
  };
  return { root, upper, armMount, armRoot, pinInner, groups, armGroup };
}

function poseCommon(machine, rig) {
  const s = solve(machine.strokes), { groups, root, upper } = rig;
  for (const name of ["boom", "stick", "bucket", "side_link", "h_link"]) {
    const p = s.P[name], group = groups[`arm_${name}`];
    if (!group || !p) continue;
    group.position.set(p[0], 0, p[1]);
    group.rotation.y = -p[2];
  }
  for (const drive of V.arm.drives) {
    for (const suffix of ["_barrel", "_rod"]) {
      const p = s.P[drive.name + suffix], group = groups[`arm_${drive.name + suffix}`];
      if (!group || !p) continue;
      group.position.set(p[0], drive.y || 0, p[1]);
      group.rotation.y = -p[2];
    }
  }
  root.position.set(machine.x, machine.y, machine.z ?? 0);
  root.rotation.set(machine.roll ?? 0, -(machine.pitch ?? 0), machine.heading);
  upper.rotation.z = (machine.slew * Math.PI) / 180;
  return s;
}

function circlePoint(a, c, radius) {
  return Math.abs(Math.hypot(a[0] - c[0], a[1] - c[1]) - radius) < 1e-4;
}
function trackInterp(a, b, f, cfg) {
  for (const center of [cfg.drive, cfg.idler]) {
    if (circlePoint(a, center, cfg.pitch_r) && circlePoint(b, center, cfg.pitch_r)) {
      let ta = Math.atan2(a[1] - center[1], a[0] - center[0]),
        tb = Math.atan2(b[1] - center[1], b[0] - center[0]);
      if (tb < ta) tb += 2 * Math.PI;
      const t = ta + (tb - ta) * f;
      return [center[0] + cfg.pitch_r * Math.cos(t), center[1] + cfg.pitch_r * Math.sin(t)];
    }
  }
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
}
function chainPose(cfg, travel) {
  const pins = cfg.pins,
    n = pins.length,
    phase = ((-travel / cfg.pitch) % n + n) % n,
    k = Math.floor(phase),
    f = phase - k,
    q = [];
  for (let j = 0; j < n; j++)
    q.push(trackInterp(pins[(j + k) % n], pins[(j + k + 1) % n], f, cfg));
  return { q, phase };
}
const matrix = new THREE.Matrix4();
function placeTrack(track, machine, cfg) {
  const { q, phase } = chainPose(cfg, machine.tracks[trackOf[track.side]]);
  for (let j = 0; j < q.length; j++) {
    const a = q[j], b = q[(j + 1) % q.length], angle = Math.atan2(b[1] - a[1], b[0] - a[0]);
    for (const shoes of track.shoes) {
      matrix.makeRotationY(-angle).setPosition((a[0] + b[0]) / 2, 0, (a[1] + b[1]) / 2);
      shoes.setMatrixAt(j, matrix);
    }
    for (const pins of track.pins) {
      matrix.makeRotationY(0).setPosition(a[0], 0, a[1]);
      pins.setMatrixAt(j, matrix);
    }
  }
  const wheelPhase = (-phase * Math.PI) / 6;
  track.pivots.drive.rotation.y = wheelPhase;
  track.pivots.idler.rotation.y = wheelPhase;
  for (const name of Object.keys(cfg.rollers))
    track.pivots[name].rotation.y = (-phase * cfg.pitch) / cfg.roller_r;
  for (const mesh of [...track.shoes, ...track.pins]) mesh.instanceMatrix.needsUpdate = true;
}

function buildTracks(data, paint, detailed, materials, root, detailLevels) {
  const tracks = [], cfg = data.cfg.j9;
  for (const side of [1, -1]) {
    const outer = new THREE.Group(), g = new THREE.Group();
    root.add(outer); outer.add(g); g.position.set(0, side * data.cfg.track_y, 0);
    if (side < 0) g.scale.set(1, -1, 1);
    const pivots = {}, groups = {};
    const pivot = (name, pos) => {
      const o = new THREE.Group(), i = new THREE.Group();
      o.position.set(pos[0], 0, pos[1]); i.position.set(-pos[0], 0, -pos[1]); o.add(i); g.add(o);
      pivots[name] = o; groups[name] = i;
    };
    for (const [name, pos] of Object.entries({ drive: cfg.drive, idler: cfg.idler, ...cfg.rollers })) pivot(name, pos);
    const moduleBatches = new Map();
    for (const item of data.module) {
      const key = `${item.group}:${item.color.join(",")}:${item.kind}`;
      if (!moduleBatches.has(key)) moduleBatches.set(key, { item, geometries: [] });
      moduleBatches.get(key).geometries.push(geometry(item, !detailed));
    }
    for (const { item, geometries } of moduleBatches.values()) {
      const merged = mergeGeometries(geometries);
      geometries.forEach((part) => part.dispose());
      merged.computeVertexNormals();
      if (detailed) {
        const levels = addFarLevel(merged);
        merged.setDrawRange(...levels.far);
        detailLevels.push({ geometry: merged, levels });
      }
      const mesh = new THREE.Mesh(merged, materialFor(item, paint, materials));
      mesh.castShadow = item.kind !== "glazing"; mesh.receiveShadow = true; mesh.renderOrder = DRAW_FIRST;
      (groups[item.group] || g).add(mesh);
    }
    const chain = new THREE.Group();
    g.add(chain);
    const shoes = [], pins = [];
    for (const [index, item] of data.link.entries()) {
      const geo = geometry(item, !detailed, SHOE_CELL);
      if (detailed) {
        const levels = addFarLevel(geo);
        geo.setDrawRange(...levels.far);
        detailLevels.push({ geometry: geo, levels });
      }
      const mesh = new THREE.InstancedMesh(geo, materialFor(item, paint, materials), TRACK_LINKS);
      mesh.frustumCulled = false; mesh.castShadow = true; mesh.receiveShadow = true; mesh.renderOrder = DRAW_FIRST;
      chain.add(mesh); (index === 0 ? shoes : pins).push(mesh);
    }
    tracks.push({ side, outer, g, pivots, shoes, pins });
  }
  return tracks;
}

function prepareParts(data, detailed) {
  const batches = new Map();
  for (const item of data.parts) {
    const parent = armParentFor(item.mover), key = `${parent}:${item.color.join(",")}:${item.kind}`;
    if (!batches.has(key)) batches.set(key, { item, parent, geometries: [] });
    batches.get(key).geometries.push(geometry(item, !detailed));
  }
  return [...batches.values()].map(({ item, parent, geometries }) => {
    const merged = mergeGeometries(geometries);
    geometries.forEach((part) => part.dispose());
    merged.computeVertexNormals();
    if (!detailed) return { parent, item, geometry: merged, levels: null };
    const levels = addFarLevel(merged);
    merged.setDrawRange(...levels.far);
    return { parent, item, geometry: merged, levels };
  });
}
function attachParent(rig, parent) {
  if (parent === "root") return rig.root;
  if (parent === "upper") return rig.upper;
  if (parent === "arm_mount") return rig.armMount;
  if (parent === "pinion") return rig.pinInner;
  if (parent.startsWith("arm_")) return rig.armGroup(parent.slice(4));
  return rig.root;
}

export async function loadMachineModel() {
  const response = await fetch("/model.json");
  if (!response.ok) throw new Error("The excavator model could not be loaded.");
  const data = await response.json();
  const make = (paint, detailed, castShadow = true) => {
    const rig = skeleton(), materials = new Map(), parts = prepareParts(data, detailed),
      detailLevels = parts.filter((part) => part.levels).map((part) => ({ geometry: part.geometry, levels: part.levels })),
      tracks = buildTracks(data, paint, detailed, materials, rig.root, detailLevels);
    let level = "far";
    for (const part of parts) {
      const mesh = new THREE.Mesh(part.geometry, materialFor(part.item, paint, materials));
      mesh.castShadow = castShadow && part.item.kind !== "glazing"; mesh.receiveShadow = true; mesh.renderOrder = DRAW_FIRST;
      mesh.userData.moving = part.item.mover.startsWith("arm:"); mesh.userData.modelSystem = part.item.sys;
      attachParent(rig, part.parent).add(mesh);
    }
    return {
      detailed, root: rig.root,
      meshes: data.parts.length + 2 * data.module.length + 2 * data.link.length,
      setScale(pixelsPerMm) {
        if (!detailed) return false;
        const limit = FULL_FROM_PIXELS_PER_MM * (level === "far" ? 1.08 : 0.92), next = pixelsPerMm > limit ? "full" : "far";
        if (next === level) return false; level = next;
        for (const { geometry, levels } of detailLevels)
          geometry.setDrawRange(...levels[level]);
        return true;
      },
      get level() { return level; },
      update(machine) {
        const solution = poseCommon(machine, rig);
        rig.pinInner.rotation.z = rig.upper.rotation.z * V.complete.ratio;
        for (const track of tracks) placeTrack(track, machine, data.cfg.j9);
        return solution;
      },
      dispose() {
        const geometries = new Set(), materials = new Set();
        rig.root.traverse((object) => {
          if (object.geometry) geometries.add(object.geometry);
          if (object.material) {
            const list = Array.isArray(object.material)
              ? object.material
              : [object.material];
            list.forEach((material) => materials.add(material));
          }
        });
        geometries.forEach((geometry) => geometry.dispose());
        materials.forEach((material) => material.dispose());
      },
    };
  };
  return {
    meshes: data.parts.length + 2 * data.module.length + 2 * data.link.length,
    createDetailed: (paint) => make(paint, true),
    createSimplified: (paint, castShadow) => make(paint, false, castShadow),
  };
}

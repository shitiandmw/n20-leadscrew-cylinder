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
  // The drive meshes carry their own lateral position (the boom pair sits at
  // y = +-34 mm in its frames), so the groups stay on the arm's centre plane.
  for (const drive of V.arm.drives) {
    for (const suffix of ["_barrel", "_rod"]) {
      const p = s.P[drive.name + suffix], group = groups[`arm_${drive.name + suffix}`];
      if (!group || !p) continue;
      group.position.set(p[0], 0, p[1]);
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

// Let the page breathe between slices of work, so that messages and pings are
// answered while the machine is being built.
const SLICE_MS = 40,
  breathe = () => new Promise((resolve) => setTimeout(resolve, 0));

// Build one batch of parts into a single geometry, with its far level if detailed.
function batchGeometry(items, detailed, cell = SIMPLE_CELL) {
  const geometries = items.map((item) => geometry(item, !detailed, cell)),
    merged = geometries.length === 1 ? geometries[0] : mergeGeometries(geometries);
  if (geometries.length > 1) geometries.forEach((part) => part.dispose());
  merged.computeVertexNormals();
  if (!detailed) return { geometry: merged, levels: null };
  const levels = addFarLevel(merged);
  merged.setDrawRange(...levels.far);
  return { geometry: merged, levels };
}

// The geometry is the same for every machine; only the paint differs. It is
// built once for each level of detail, in slices that let the page breathe, and
// shared by every assembly drawn from it, so another player's machine costs a
// few meshes rather than a rebuild. The right-hand track reuses the left one's
// geometry, mirrored by its group.
async function prepare(data, detailed, progress) {
  const batches = new Map();
  for (const item of data.parts) {
    const parent = armParentFor(item.mover), key = `${parent}:${item.color.join(",")}:${item.kind}`;
    if (!batches.has(key)) batches.set(key, { item, parent, items: [] });
    batches.get(key).items.push(item);
  }
  const moduleBatches = new Map();
  for (const item of data.module) {
    const key = `${item.group}:${item.color.join(",")}:${item.kind}`;
    if (!moduleBatches.has(key)) moduleBatches.set(key, { item, items: [] });
    moduleBatches.get(key).items.push(item);
  }
  const jobs = [
    ...[...batches.values()].map((batch) => () => ({ kind: "part", parent: batch.parent, item: batch.item, ...batchGeometry(batch.items, detailed) })),
    ...[...moduleBatches.values()].map((batch) => () => ({ kind: "module", item: batch.item, ...batchGeometry(batch.items, detailed) })),
    ...data.link.map((item, index) => () => ({ kind: "link", index, item, ...batchGeometry([item], detailed, SHOE_CELL) })),
  ];
  const parts = [], modules = [], links = [];
  let since = performance.now();
  for (const [n, job] of jobs.entries()) {
    const built = job();
    (built.kind === "part" ? parts : built.kind === "module" ? modules : links).push(built);
    if (performance.now() - since > SLICE_MS) {
      progress((n + 1) / jobs.length);
      await breathe();
      since = performance.now();
    }
  }
  progress(1);
  return { parts, modules, links };
}

function buildTracks(data, prepared, paint, materials, root) {
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
    for (const { item, geometry } of prepared.modules) {
      const mesh = new THREE.Mesh(geometry, materialFor(item, paint, materials));
      mesh.castShadow = item.kind !== "glazing"; mesh.receiveShadow = true; mesh.renderOrder = DRAW_FIRST;
      (groups[item.group] || g).add(mesh);
    }
    const chain = new THREE.Group();
    g.add(chain);
    const shoes = [], pins = [];
    for (const { index, item, geometry } of prepared.links) {
      const mesh = new THREE.InstancedMesh(geometry, materialFor(item, paint, materials), TRACK_LINKS);
      mesh.frustumCulled = false; mesh.castShadow = true; mesh.receiveShadow = true; mesh.renderOrder = DRAW_FIRST;
      chain.add(mesh); (index === 0 ? shoes : pins).push(mesh);
    }
    tracks.push({ side, outer, g, pivots, shoes, pins });
  }
  return tracks;
}
function attachParent(rig, parent) {
  if (parent === "root") return rig.root;
  if (parent === "upper") return rig.upper;
  if (parent === "arm_mount") return rig.armMount;
  if (parent === "pinion") return rig.pinInner;
  if (parent.startsWith("arm_")) return rig.armGroup(parent.slice(4));
  return rig.root;
}

export async function loadMachineModel(onProgress = () => {}) {
  const response = await fetch("/model.json");
  if (!response.ok) throw new Error("The excavator model could not be loaded.");
  const data = await response.json();
  // Both levels of detail are prepared now, so that the first other player and
  // the first zoom in cost nothing but meshes.
  const prepared = {
    detailed: await prepare(data, true, (done) => onProgress(done / 2)),
    simplified: await prepare(data, false, (done) => onProgress(0.5 + done / 2)),
  };
  const make = (paint, detailed, castShadow = true) => {
    const rig = skeleton(), materials = new Map(), shared = detailed ? prepared.detailed : prepared.simplified,
      parts = shared.parts,
      detailLevels = [...shared.parts, ...shared.modules, ...shared.links]
        .filter((entry) => entry.levels)
        .map(({ geometry, levels }) => ({ geometry, levels })),
      tracks = buildTracks(data, shared, paint, materials, rig.root);
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
      // The geometry is shared with every other assembly and stays; the
      // materials and the links' instance buffers are this assembly's own.
      dispose() {
        const own = new Set();
        rig.root.traverse((object) => {
          if (object.isInstancedMesh) object.dispose();
          if (object.material) {
            const list = Array.isArray(object.material)
              ? object.material
              : [object.material];
            list.forEach((material) => own.add(material));
          }
        });
        own.forEach((material) => material.dispose());
      },
    };
  };
  return {
    meshes: data.parts.length + 2 * data.module.length + 2 * data.link.length,
    createDetailed: (paint) => make(paint, true),
    createSimplified: (paint, castShadow) => make(paint, false, castShadow),
  };
}

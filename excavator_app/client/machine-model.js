import * as THREE from "three";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { CONFIG as V } from "../shared/config.js";
import { solve } from "../shared/kinematics.js";
import { PAINTS } from "../shared/players.js";
import { clusterMesh } from "./decimate.js";

// The CAD meshes are shared by every excavator in the world. The one the camera
// follows has every part: in full (776,942 triangles) from close up, and from a
// simplified index when each part's fine detail would be smaller than a pixel or
// two. The others are simplified further, so they are recognisably the same
// machine at a small cost.
const SIMPLE_CELL = 5,
  SHOE_CELL = 6,
  TRACK_LINKS = 34,
  // The far level's cell, and how many drawn pixels a millimetre must span at
  // the machine before that cell would show: it is 2 pixels wide there.
  FAR_CELL = 1.5,
  FULL_FROM_PIXELS_PER_MM = 2 / FAR_CELL;
// Drawn first, because what they hide then costs nothing to shade.
const DRAW_FIRST = -3;
// The yellow paint the CAD model uses, as sRGB, and each one's share of a new paint.
const PAINTED = { "0.91,0.6,0.07": 1, "0.9,0.57,0.045": 0.96 };
const LINK = /^(?:shoe_|track_pin_|track_bushing_|pin_clip_)([LR])(\d{2})/,
  LINKS = "links";
// Parts a simplified machine does without: too small to see, or inside it.
const HIDDEN =
  /^(?:track_pin_|track_bushing_|pin_clip_|battery|electronics|motor|steel_ballast|gear_standoff|slew_|flexible_coupling|.*axle|.*_slew_pinion)/;
const TINY_HARDWARE = 30,
  TINY_PART = 8;
// The CAD names its tracks from the opposite end: "L" is on the -Y side, which
// is the operator's right. Each track must turn with its own drive command.
const trackOf = { L: 1, R: 0 };
const decode = (encoded, Type) => {
  const bytes = Uint8Array.from(atob(encoded), (c) => c.charCodeAt(0));
  return new Type(bytes.buffer);
};
const linear = (r, g, b) => new THREE.Color(r, g, b).convertSRGBToLinear();

// Appends a coarser copy of a merged mesh to its own buffers, so that choosing
// between the two is only a matter of which range of the index to draw.
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
  far.index.forEach((v, i) => {
    indices[index.length + i] = first + v;
  });
  geometry.setAttribute(
    "position",
    new THREE.BufferAttribute(joined(position, far.positions), 3),
  );
  geometry.setAttribute(
    "normal",
    new THREE.BufferAttribute(joined(normal, far.normals), 3),
  );
  geometry.setIndex(new THREE.BufferAttribute(indices, 1));
  return {
    full: [0, index.length],
    far: [index.length, far.index.length],
  };
}
// The first paint is the model's own, so nothing needs repainting for it.
const repaint = (paint) => (paint === PAINTS[0] ? null : paint);

// The arm, its four cylinders and the slew: the same for both levels of detail.
function poseCommon(machine, root, upper, groups) {
  const s = solve(machine.strokes);
  for (const name of ["base", "boom", "stick", "bucket", "rocker", "coupler"]) {
    groups["arm_" + name].position.set(
      s.origins[name][0],
      0,
      s.origins[name][1],
    );
    groups["arm_" + name].rotation.y = -s.angles[name];
  }
  for (const [i, role] of ["boom", "stick", "bucket"].entries()) {
    const [a, b] = [
      ["A", "B"],
      ["C", "D"],
      ["F", "R"],
    ][i];
    V.arm.actuators[role].y.forEach((y, side) => {
      const group = groups["arm_act_" + role + side];
      group.position.set(s.p[a][0], y, s.p[a][1]);
      group.rotation.y =
        Math.PI / 2 - Math.atan2(s.p[b][1] - s.p[a][1], s.p[b][0] - s.p[a][0]);
      for (const mesh of group.children)
        mesh.position.z =
          37.5 + (mesh.userData.moving ? machine.strokes[i] : 0);
    });
  }
  root.position.set(machine.x, machine.y, machine.z ?? 0);
  root.rotation.set(machine.roll ?? 0, -(machine.pitch ?? 0), machine.heading);
  upper.rotation.z = (machine.slew * Math.PI) / 180;
  return s;
}

// Where track link i of a side is, part way round its chain.
function linkPose(poses, i, offset) {
  const count = TRACK_LINKS,
    phase = (((i + offset) % count) + count) % count,
    j = Math.floor(phase),
    f = phase - j,
    a = poses[j],
    b = poses[(j + 1) % count];
  let delta = b.angle - a.angle;
  delta = Math.atan2(Math.sin(delta), Math.cos(delta));
  return {
    x: a.origin[0] * (1 - f) + b.origin[0] * f,
    z: a.origin[1] * (1 - f) + b.origin[1] * f,
    angle: -(a.angle + delta * f),
  };
}

// Puts every link of both tracks in its place. Each mesh draws one part, once per
// link, in the machine's frame.
const linkMatrix = new THREE.Matrix4();
function placeLinks(meshes, poses, machine) {
  let n = 0;
  for (const side of ["L", "R"]) {
    const offset = machine.tracks[trackOf[side]] / V.track_pitch,
      y = ((side === "L" ? -1 : 1) * V.track_centres) / 2;
    for (let i = 0; i < TRACK_LINKS; i++, n++) {
      const pose = linkPose(poses, i, offset);
      linkMatrix.makeRotationY(pose.angle).setPosition(pose.x, y, pose.z);
      for (const mesh of meshes) mesh.setMatrixAt(n, linkMatrix);
    }
  }
  for (const mesh of meshes) mesh.instanceMatrix.needsUpdate = true;
}

function skeleton() {
  const root = new THREE.Group(),
    upper = new THREE.Group(),
    arm = new THREE.Group();
  // Same rotation as chassisAxes(): heading, then pitch, then roll.
  root.rotation.order = "ZYX";
  root.add(upper);
  upper.add(arm);
  arm.position.set(...V.arm_offset);
  return { root, upper, arm };
}

export async function loadMachineModel() {
  const response = await fetch("/model.json");
  if (!response.ok) throw new Error("The excavator model could not be loaded.");
  const data = await response.json(),
    poses = data.track.initial_poses,
    groupsOf = new Map(),
    batches = new Map(),
    simpleParts = new Map();
  const wheelCenters = {};
  for (const side of ["L", "R"]) {
    const y = ((side === "L" ? -1 : 1) * V.track_centres) / 2;
    const centres = [
      [-V.wheel_centres / 2, V.axle_z],
      [V.wheel_centres / 2 + V.idler_assembly_offset_mm, V.axle_z],
      ...V.road_roller_x_mm.map((x) => [x, 29]),
      ...V.return_roller_x_mm.map((x) => [x, V.return_roller_z_mm]),
    ];
    [
      "drive_" + side,
      "idler_" + side,
      ...V.road_roller_x_mm.map((_, i) => "roller_" + side + i),
      ...V.return_roller_x_mm.map((_, i) => "return_" + side + i),
    ].forEach((name, i) => {
      wheelCenters[name] = {
        centre: [centres[i][0], y, centres[i][1]],
        side,
        radius: i === 0 ? V.pitch_radius : i === 1 ? 30 : i < 5 ? 17.5 : 13.5,
      };
    });
  }
  // Simplify a mesh and file it under the rigid part of a simplified machine.
  function simplify(geometry, item, key) {
    const position = geometry.attributes.position.array,
      box = (geometry.computeBoundingBox(), geometry.boundingBox),
      size = box.max.distanceTo(box.min);
    if (
      HIDDEN.test(item.name) ||
      size < (item.kind === "hardware" ? TINY_HARDWARE : TINY_PART)
    )
      return;
    const { positions, index } = clusterMesh(
      position,
      geometry.index.array,
      SIMPLE_CELL,
    );
    if (!index.length) return;
    const simple = new THREE.BufferGeometry();
    simple.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    simple.setIndex(new THREE.BufferAttribute(index, 1));
    const color = linear(...item.color),
      paint = PAINTED[item.color.join(",")] ?? 0,
      colors = new Float32Array(positions.length),
      shares = new Float32Array(positions.length / 3);
    for (let v = 0; v < positions.length / 3; v++) {
      colors.set([color.r, color.g, color.b], 3 * v);
      shares[v] = paint;
    }
    simple.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    simple.setAttribute("paint", new THREE.BufferAttribute(shares, 1));
    const partKey = `${key}:${!!item.moving}`;
    if (!simpleParts.has(partKey))
      simpleParts.set(partKey, { key, moving: !!item.moving, geometries: [] });
    simpleParts.get(partKey).geometries.push(simple);
  }
  let shoe = null;
  for (const item of data.meshes) {
    const link = LINK.exec(item.name);
    // Every link of both tracks is the same parts, moved round the chain, so
    // one link's meshes are drawn once for each of them.
    if (link && !(link[1] === "R" && link[2] === "00")) continue;
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
      "position",
      new THREE.BufferAttribute(decode(item.v, Float32Array), 3),
    );
    geometry.setIndex(
      new THREE.BufferAttribute(
        decode(item.t, item.wide ? Uint32Array : Uint16Array),
        1,
      ),
    );
    let key = (item.arm ? "arm_" : "vehicle_") + item.group,
      parent = item.arm ? "arm" : item.group === "upper" ? "upper" : "root";
    if (item.arm) simplify(geometry, item, key);
    else if (item.group === "upper") simplify(geometry, item, "vehicle_upper");
    else if (!link) simplify(geometry, item, "vehicle_chassis");
    const spec = {};
    if (link) {
      const pose = poses[+link[2]];
      geometry.translate(-pose.origin[0], -V.track_centres / 2, -pose.origin[1]);
      geometry.rotateY(pose.angle);
      key = LINKS;
      parent = "root";
      if (item.name.startsWith("shoe_")) {
        const { positions, index: triangles } = clusterMesh(
          geometry.attributes.position.array,
          geometry.index.array,
          SHOE_CELL,
        );
        shoe = new THREE.BufferGeometry();
        shoe.setAttribute("position", new THREE.BufferAttribute(positions, 3));
        shoe.setIndex(new THREE.BufferAttribute(triangles, 1));
        shoe.userData.color = linear(...item.color);
      }
    }
    if (!item.arm && wheelCenters[item.group]) {
      const w = wheelCenters[item.group];
      geometry.translate(-w.centre[0], -w.centre[1], -w.centre[2]);
      spec.position = w.centre;
      spec.wheel = w;
    }
    if (key === "vehicle_slew_pinion") {
      geometry.translate(-V.slew_centre_distance, 0, 0);
      spec.position = [V.slew_centre_distance, 0, 0];
    }
    if (!groupsOf.has(key)) groupsOf.set(key, { parent, ...spec });
    geometry.computeVertexNormals();
    const batchKey =
      key + ":" + item.color.join(",") + ":" + item.kind + ":" + !!item.moving;
    if (!batches.has(batchKey))
      batches.set(batchKey, { geometries: [], item, key });
    batches.get(batchKey).geometries.push(geometry);
  }
  // Full detail: one merged mesh for each rigid group, colour and kind.
  const detailBatches = [...batches.values()].map(
    ({ geometries, item, key }) => {
      const geometry = mergeGeometries(geometries);
      for (const g of geometries) g.dispose();
      return { geometry, item, key, levels: addFarLevel(geometry) };
    },
  );
  // Simplified: one merged mesh for each rigid part, painted by vertex.
  const simpleBase = [...simpleParts.values()].map(
    ({ key, moving, geometries }) => {
      const geometry = mergeGeometries(geometries);
      for (const g of geometries) g.dispose();
      geometry.computeBoundingSphere();
      return { key, moving, geometry };
    },
  );

  // One material for each surface and paint. They are shared between machines,
  // and geometries that share attributes must not be disposed, so both last as
  // long as the page; paint is the only thing that varies, in a fixed palette.
  const materials = new Map();
  function detailMaterial(item, paint) {
    const share = repaint(paint) ? (PAINTED[item.color.join(",")] ?? 0) : 0,
      key = `${item.color}:${item.kind}:${share ? paint : ""}`;
    if (!materials.has(key)) {
      const glass = item.kind === "glazing",
        color = linear(...item.color);
      if (share) color.set(paint).multiplyScalar(share);
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
  const simpleMaterial = new THREE.MeshStandardMaterial({
    vertexColors: true,
    roughness: 0.62,
    metalness: 0.14,
    flatShading: true,
  });
  const shoeMaterial = new THREE.MeshStandardMaterial({
    color: shoe.userData.color,
    roughness: 0.66,
    metalness: 0.12,
    flatShading: true,
  });
  // The simplified parts in one paint; they share all but the colours.
  const paintedParts = new Map();
  function simpleFor(paint) {
    if (!repaint(paint)) return simpleBase;
    if (paintedParts.has(paint)) return paintedParts.get(paint);
    const color = new THREE.Color(paint),
      parts = simpleBase.map((part) => {
        const shares = part.geometry.attributes.paint.array;
        if (!shares.some((share) => share > 0)) return part;
        const geometry = new THREE.BufferGeometry(),
          colors = part.geometry.attributes.color.array.slice();
        geometry.setIndex(part.geometry.index);
        geometry.setAttribute("position", part.geometry.attributes.position);
        geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
        geometry.boundingSphere = part.geometry.boundingSphere;
        shares.forEach((share, v) => {
          if (share)
            colors.set(
              [color.r * share, color.g * share, color.b * share],
              3 * v,
            );
        });
        return { ...part, geometry };
      });
    paintedParts.set(paint, parts);
    return parts;
  }

  return {
    meshes: data.meshes.length,
    // paint: a colour from PAINTS, or null for the model's own yellow.
    createDetailed(paint) {
      const { root, upper, arm } = skeleton(),
        parents = { root, upper, arm },
        groups = {},
        linkMeshes = [],
        wheels = [];
      for (const [key, spec] of groupsOf) {
        const group = (groups[key] = new THREE.Group());
        parents[spec.parent].add(group);
        if (spec.position) group.position.set(...spec.position);
        if (spec.wheel) wheels.push({ ...spec.wheel, group });
      }
      let level = "far",
        tracks = null;
      for (const { geometry, item, key, levels } of detailBatches) {
        const material = detailMaterial(item, paint),
          mesh =
            key === LINKS
              ? new THREE.InstancedMesh(geometry, material, 2 * TRACK_LINKS)
              : new THREE.Mesh(geometry, material);
        if (key === LINKS) {
          mesh.frustumCulled = false;
          linkMeshes.push(mesh);
        }
        mesh.castShadow = item.kind !== "glazing";
        mesh.receiveShadow = true;
        if (item.kind !== "glazing") mesh.renderOrder = DRAW_FIRST;
        mesh.userData.moving = item.moving;
        geometry.setDrawRange(...levels.far);
        // The shadow map's texels are about as wide as the far level's cell.
        mesh.onBeforeShadow = () => geometry.setDrawRange(...levels.far);
        mesh.onAfterShadow = () => geometry.setDrawRange(...levels[level]);
        groups[key].add(mesh);
      }
      return {
        detailed: true,
        root,
        // How many drawn pixels a millimetre at the machine spans now. A little
        // slack keeps a camera at the limit from changing level back and forth.
        // Returns true if the picture will change.
        setScale(pixelsPerMm) {
          const limit =
              FULL_FROM_PIXELS_PER_MM * (level === "far" ? 1.08 : 0.92),
            next = pixelsPerMm > limit ? "full" : "far";
          if (next === level) return false;
          level = next;
          for (const { geometry, levels } of detailBatches)
            geometry.setDrawRange(...levels[level]);
          return true;
        },
        get level() {
          return level;
        },
        update(machine) {
          const s = poseCommon(machine, root, upper, groups);
          groups.vehicle_slew_pinion.rotation.z =
            (-upper.rotation.z * 96) / 20;
          if (
            !tracks ||
            tracks[0] !== machine.tracks[0] ||
            tracks[1] !== machine.tracks[1]
          ) {
            tracks = [...machine.tracks];
            placeLinks(linkMeshes, poses, machine);
          }
          for (const w of wheels)
            w.group.rotation.y = machine.tracks[trackOf[w.side]] / w.radius;
          return s;
        },
        dispose() {
          for (const mesh of linkMeshes) mesh.dispose();
        },
      };
    },
    createSimplified(paint, castShadow = true) {
      const { root, upper, arm } = skeleton(),
        groups = {};
      for (const { key, moving, geometry } of simpleFor(paint)) {
        if (!groups[key]) {
          const spec = groupsOf.get(key),
            group = (groups[key] = new THREE.Group());
          (key === "vehicle_upper"
            ? upper
            : key === "vehicle_chassis"
              ? root
              : arm
          ).add(group);
          if (spec?.position && key !== "vehicle_chassis")
            group.position.set(...spec.position);
        }
        const mesh = new THREE.Mesh(geometry, simpleMaterial);
        mesh.castShadow = castShadow;
        mesh.receiveShadow = true;
        mesh.renderOrder = DRAW_FIRST;
        mesh.userData.moving = moving;
        groups[key].add(mesh);
      }
      // Every shoe is the same part, moved round its chain.
      const shoes = new THREE.InstancedMesh(shoe, shoeMaterial, 2 * TRACK_LINKS);
      shoes.castShadow = castShadow;
      shoes.receiveShadow = true;
      shoes.renderOrder = DRAW_FIRST;
      shoes.frustumCulled = false;
      root.add(shoes);
      let tracks = null;
      return {
        detailed: false,
        root,
        update(machine) {
          const s = poseCommon(machine, root, upper, groups);
          if (
            !tracks ||
            tracks[0] !== machine.tracks[0] ||
            tracks[1] !== machine.tracks[1]
          ) {
            tracks = [...machine.tracks];
            placeLinks([shoes], poses, machine);
          }
          return s;
        },
        dispose() {
          shoes.dispose();
        },
      };
    },
  };
}

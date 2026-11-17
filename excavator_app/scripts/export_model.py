"""Export the complete excavator viewer data for the game.

The complete-machine viewer is a generated single HTML file. It contains the
CAD meshes and R12 table kinematics used by the offline viewer, so the app can
be rebuilt without CadQuery, NumPy, or the original CAD toolchain.
"""
import gzip
import hashlib
import json
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent
SOURCE_REL = Path("excavator_complete/3D_preview.html")
SOURCE = REPO / SOURCE_REL


def embedded_data(html: str) -> dict:
    """Decode the JSON assigned to ``const D=`` in the generated viewer."""
    marker = "const D={"
    start = html.find(marker)
    if start < 0:
        raise ValueError(f"{SOURCE_REL} has no complete-machine data object")
    start += len("const D=")
    data, _ = json.JSONDecoder().raw_decode(html[start:])
    return data


def app_config(cfg: dict) -> dict:
    """Project complete-machine dimensions into fields used by the app."""
    j9 = cfg["j9"]
    key = cfg["key"]
    rollers = j9["rollers"]
    road_x = [float(rollers[k][0]) for k in sorted(rollers) if k.startswith("road")]
    support_x = [float(rollers[k][0]) for k in sorted(rollers) if k.startswith("support")]
    arm = {
        "scale": 15.0,
        "boom": 380.0,
        "stick": 193.333,
        "bucket_width": 80.0,
        "tip": cfg["pins"]["T"],
        "origin": [0.0, 0.0],
        "closed": [float(cfg["closed"])] * 3,
        "strokes": [60.0] * 3,
        "default": cfg["default"],
        "pitch": float(cfg["step"]),
        "tables": cfg["tables"],
        "pins": cfg["pins"],
        "pin_body": cfg["pin_body"],
        "drives": cfg["drives"],
        "actuators": {
            "boom": {"y": [float(d["y"]) for d in cfg["drives"] if d["name"].startswith("boom_")]},
            "stick": {"y": [float(d["y"]) for d in cfg["drives"] if d["name"] == "stick"]},
            "bucket": {"y": [float(d["y"]) for d in cfg["drives"] if d["name"] == "bucket"]},
        },
    }
    # Keep dimensions that existing terrain and model code reads. Values not
    # present in the J9 scene are stable mechanical constants from this model.
    return {
        "revision": 4,
        "units": "mm",
        "track_pitch": float(j9["pitch"]),
        "sprocket_teeth": 12,
        "pitch_radius": float(j9["pitch_r"]),
        "wheel_centres": float(j9["key"]["centres"]),
        "axle_z": float(j9["key"]["axle_z"]),
        "end_wheel_rise_mm": 0.0,
        "idler_assembly_offset_mm": 0.0,
        "return_roller_z_mm": float(rollers["support0"][1]),
        "ground_support_half_length_mm": 79.3,
        "track_centres": float(key["track_gauge"]),
        "track_links_per_side": len(j9["pins"]),
        "track_pin_diameter": 3.0,          # J910 revision B: each joint is an M3 x 60 screw with a nyloc nut
        "track_pin_length": 60.0,
        "track_screw_seat_y_mm": 25.0,
        "shoe_width": float(j9["key"]["shoe"]),
        "idler_adjustment_mm": [-3.0, 6.0],
        "idler_tension_adjustment_mm": [-3.0, 6.0],
        "track_revision": "J9 / X1 revision F",
        "track_outer_width_mm": float(key["overall_width"]),
        "frame_lateral_shift_mm": 0.0,
        "guide_clearance_per_side_mm": 0.6,
        "guide_flange_height_mm": 2.0,
        "guide_inner_y_mm": 21.6,
        "guide_outer_y_mm": 23.0,
        "sprocket_tip_radius_mm": float(j9["pitch_r"] + 2.2),
        "idler_guide_radius_mm": float(j9["pitch_r"] - 3.4),
        "grouser_height_mm": 1.0,
        "grouser_width_mm": 2.0,
        "idler_rail_radius_mm": float(j9["pitch_r"] - 5.5),
        "road_roller_x_mm": road_x,
        "return_roller_x_mm": support_x,
        "arm_offset": [float(x) for x in cfg["O"]],
        "arm": arm,
        "slew_centre_distance": float(-cfg["pinion_axis"][0]),
        "slew_gear_teeth": 80,
        "slew_module": 1.5,
        "normal_drive_speed_limit_m_s": 0.22,
        "nominal_floor_slope_deg": 37.0,
        "complete": cfg,
    }


KINEMATICS = """// Generated R12 table solver; shared by physics and rendering.
import { CONFIG } from './config.js';
const C = CONFIG.arm;
const STEP = C.pitch;
const ROWS = { boom: C.tables.boom.rows, stick: C.tables.stick.rows, bucket: C.tables.bucket.rows };
const BODIES = C.tables.bucket.bodies;
const BUCKET_AT = 3 * BODIES.indexOf('bucket');
const PINS = Object.entries(C.pins).map(([name, local]) => ({ name, body: C.pin_body[name], x: local[0], z: local[1] }));
const DRIVES = C.drives.map((drive) => ({ a: drive.a, b: drive.b, barrel: drive.name + '_barrel', rod: drive.name + '_rod' }));
const CLOSED = C.closed[0];
// The table row below a stroke, leaving the way towards the next row in `frac`.
let frac = 0;
const rowAt = (rows, stroke) => {
  const x = Math.min(Math.max(stroke / STEP, 0), rows.length - 1.000001), i = Math.floor(x);
  frac = x - i;
  return i;
};
const value = (rows, i, j) => rows[i][j] + (rows[i + 1][j] - rows[i][j]) * frac;
const compose = (p, rx, rz, ra) => {
  const c = Math.cos(p[2]), s = Math.sin(p[2]);
  return [p[0] + c * rx - s * rz, p[1] + s * rx + c * rz, p[2] + ra];
};
// The bucket's pose on the arm, [x, z, turn] into `out`: what the physics asks for
// many times a tick, with nothing allocated.
function bucketBody(strokes, out) {
  const bi = rowAt(ROWS.boom, strokes[0]), bx = value(ROWS.boom, bi, 0), bz = value(ROWS.boom, bi, 1), ba = value(ROWS.boom, bi, 2);
  const si = rowAt(ROWS.stick, strokes[1]), sx = value(ROWS.stick, si, 0), sz = value(ROWS.stick, si, 1), sa = value(ROWS.stick, si, 2);
  const cb = Math.cos(ba), sb = Math.sin(ba);
  const px = bx + cb * sx - sb * sz, pz = bz + sb * sx + cb * sz, pa = ba + sa;
  const ki = rowAt(ROWS.bucket, strokes[2]), kx = value(ROWS.bucket, ki, BUCKET_AT), kz = value(ROWS.bucket, ki, BUCKET_AT + 1), ka = value(ROWS.bucket, ki, BUCKET_AT + 2);
  const cp = Math.cos(pa), sp = Math.sin(pa);
  out[0] = px + cp * kx - sp * kz;
  out[1] = pz + sp * kx + cp * kz;
  out[2] = pa + ka;
  return out;
}
// Every body, pin and drive: what the renderer draws from.
function solve(strokes) {
  const P = { base: [0, 0, 0] };
  const bi = rowAt(ROWS.boom, strokes[0]);
  P.boom = [value(ROWS.boom, bi, 0), value(ROWS.boom, bi, 1), value(ROWS.boom, bi, 2)];
  const si = rowAt(ROWS.stick, strokes[1]);
  P.stick = compose(P.boom, value(ROWS.stick, si, 0), value(ROWS.stick, si, 1), value(ROWS.stick, si, 2));
  const ki = rowAt(ROWS.bucket, strokes[2]), f = frac;
  for (let n = 0; n < BODIES.length; n++) {
    frac = f;
    P[BODIES[n]] = compose(P.stick, value(ROWS.bucket, ki, 3 * n), value(ROWS.bucket, ki, 3 * n + 1), value(ROWS.bucket, ki, 3 * n + 2));
  }
  const W = {};
  for (let n = 0; n < PINS.length; n++) {
    const pin = PINS[n], p = P[pin.body], c = Math.cos(p[2]), s = Math.sin(p[2]);
    W[pin.name] = [p[0] + c * pin.x - s * pin.z, p[1] + s * pin.x + c * pin.z, p[2]];
  }
  for (let n = 0; n < DRIVES.length; n++) {
    const drive = DRIVES[n], a = W[drive.a], b = W[drive.b];
    const ax = b[0] - a[0], az = b[1] - a[1];
    const length = Math.hypot(ax, az), k = (length - CLOSED) / length;
    const angle = Math.atan2(az, ax);
    P[drive.barrel] = [a[0], a[1], angle];
    P[drive.rod] = [a[0] + k * ax, a[1] + k * az, angle];
  }
  const rocker = P.side_link ?? P.bucket, coupler = P.h_link ?? P.bucket;
  return {
    P, W,
    p: W,
    origins: {
      base: [P.base[0], P.base[1]],
      boom: [P.boom[0], P.boom[1]],
      stick: [P.stick[0], P.stick[1]],
      bucket: [P.bucket[0], P.bucket[1]],
      rocker: [rocker[0], rocker[1]],
      coupler: [coupler[0], coupler[1]],
    },
    angles: {
      base: 0,
      boom: P.boom[2],
      stick: P.stick[2],
      bucket: P.bucket[2],
      rocker: rocker[2],
      coupler: coupler[2],
    },
  };
}
export { solve, bucketBody };
"""


def export() -> None:
    html = SOURCE.read_text()
    complete = embedded_data(html)
    cfg = complete["cfg"]
    source = {
        "file": SOURCE_REL.as_posix(),
        "sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    }

    # The timeline, traces and validation reports belong to the offline page.
    # The game needs only CAD geometry and kinematic tables.
    model = {
        "version": 2,
        "source": source,
        "cfg": cfg,
        "module": complete["module"],
        "link": complete["link"],
        "parts": complete["parts"],
        "sys": complete.get("sys", {}),
    }
    packed = json.dumps(model, separators=(",", ":")).encode()
    (APP / "public").mkdir(exist_ok=True)
    (APP / "shared").mkdir(exist_ok=True)
    (APP / "public/model.json.gz").write_bytes(gzip.compress(packed, mtime=0))

    config = app_config(cfg)
    (APP / "shared/config.js").write_text(
        "// Generated by scripts/export_model.py; dimensions in mm.\n"
        + "export const CONFIG = "
        + json.dumps(config, indent=2)
        + ";\n"
    )
    (APP / "shared/kinematics.js").write_text(KINEMATICS)
    print(
        f"Exported complete model: {len(model['parts'])} parts, "
        f"{len(model['module'])} track modules, {len(model['link'])} link meshes; "
        f"{len(packed):,} bytes before gzip"
    )


if __name__ == "__main__":
    export()

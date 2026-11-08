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
        "track_pin_diameter": 3.0,
        "track_pin_length": 56.0,
        "track_pin_clip_y_mm": 33.0,
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
const compose = (p, r) => {
  const c = Math.cos(p[2]), s = Math.sin(p[2]);
  return [p[0] + c * r[0] - s * r[1], p[1] + s * r[0] + c * r[1], p[2] + r[2]];
};
const look = (key, stroke) => {
  const rows = C.tables[key].rows;
  const x = Math.min(Math.max(stroke / STEP, 0), rows.length - 1.000001);
  const i = Math.floor(x), f = x - i, a = rows[i], b = rows[i + 1];
  return a.map((v, j) => v + (b[j] - v) * f);
};
const pinsOf = (P) => {
  const W = {};
  for (const [name, local] of Object.entries(C.pins))
    W[name] = compose(P[C.pin_body[name]], [local[0], local[1], 0]);
  return W;
};
function solve(strokes) {
  const P = { base: [0, 0, 0] };
  P.boom = compose(P.base, look('boom', strokes[0]));
  P.stick = compose(P.boom, look('stick', strokes[1]));
  const bucket = look('bucket', strokes[2]);
  C.tables.bucket.bodies.forEach((body, i) => {
    P[body] = compose(P.stick, bucket.slice(3 * i, 3 * i + 3));
  });
  const W = pinsOf(P);
  for (const drive of C.drives) {
    const ax = W[drive.b][0] - W[drive.a][0];
    const az = W[drive.b][1] - W[drive.a][1];
    const length = Math.hypot(ax, az), k = (length - C.closed[0]) / length;
    const angle = Math.atan2(az, ax);
    P[drive.name + '_barrel'] = [W[drive.a][0], W[drive.a][1], angle];
    P[drive.name + '_rod'] = [W[drive.a][0] + k * ax, W[drive.a][1] + k * az, angle];
  }
  return {
    P, W,
    p: W,
    origins: {
      base: [P.base[0], P.base[1]],
      boom: [P.boom[0], P.boom[1]],
      stick: [P.stick[0], P.stick[1]],
      bucket: [P.bucket[0], P.bucket[1]],
      rocker: [P.side_link?.[0] ?? P.bucket[0], P.side_link?.[1] ?? P.bucket[1]],
      coupler: [P.h_link?.[0] ?? P.bucket[0], P.h_link?.[1] ?? P.bucket[1]],
    },
    angles: {
      base: 0,
      boom: P.boom[2],
      stick: P.stick[2],
      bucket: P.bucket[2],
      rocker: P.side_link?.[2] ?? P.bucket[2],
      coupler: P.h_link?.[2] ?? P.bucket[2],
    },
  };
}
export { solve };
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

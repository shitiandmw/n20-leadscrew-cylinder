"""Collect every R12 check into ../validation_summary.json (and fail loudly if one is missing or red)."""
import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(p):
    return json.loads((ROOT / p).read_text())


def sha(p):
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def main():
    cad, clash, dc = load('cad/cad_report.json'), load('cad/clash_check.json'), load('design_check.json')
    sim = {k: load(f'simulation/{k}_report.json') for k in ('payload_150g', 'unloaded', 'hold', 'sync_bias', 'half_step')}
    hold_diff = max(abs(v['mujoco_force_N'][k] - v['virtual_work_N']['boom_each' if k.startswith('boom') else k])
                    for v in sim['hold']['poses'].values() for k in ('boom_L', 'boom_R', 'stick', 'bucket'))
    out = dict(
        cad=dict(printed_parts=len(cad['printed_parts']),
                 all_valid_watertight_step_ok=all(p['valid'] and p['watertight'] and p['step_roundtrip_valid'] for p in cad['printed_parts']),
                 assembly_solids=cad['assembly_solids'], printed_mass_g=round(sum(p['mass_g'] for p in cad['printed_parts']), 1),
                 moving_masses_kg=cad['masses_kg']),
        clash_3d=dict(status=clash['status'], poses=clash['poses_grid'] + clash['poses_cycle'], parts=clash['parts'],
                      penetrations=clash['penetrations'], same_body_overlaps=len(clash['same_body_overlaps']),
                      closest_inplane=clash['closest_inplane'][:4]),
        design_check_2p5d=dict(status=dc['status'], hits=dc['n_hits'], closest=dc['closest_pairs'][:3],
                               hold_N_150g=dc['hold_force_per_drive_N_150g'], working_ranges_mm=dc['working_ranges_mm']),
        dynamics={k: dict(passed=v['pass'], peak_force_N=v['peak_force_N'], tracking_mm=v['max_stroke_tracking_error_mm'],
                          closure_mm=v['max_pin_closure_error_mm'], seconds_at_clamp=v['time_at_force_clamp_s'])
                  for k, v in sim.items() if k in ('payload_150g', 'unloaded')},
        hold_mujoco_vs_virtual_work_max_diff_N=round(hold_diff, 3),
        half_step_max_peak_difference_N=sim['half_step']['compare_full_step']['max_peak_difference_N'],
        boom_sync_0p5mm=sim['sync_bias']['poses']['boom']['mujoco_force_N'],
        files=dict(motion_json_sha256=sha('motion.json'), preview_sha256=sha('3D_preview.html')))
    for f, key in (('browser_validation.json', 'browser'), ('video_validation.json', 'video')):
        if (ROOT / f).exists():
            v = load(f)
            out[key] = {k: v[k] for k in v if k in ('status', 'html_sha256', 'duration_s', 'frames_decoded', 'resolution', 'chapters',
                                                    'kinematics', 'replay', 'size_mb')}
    ok = (out['cad']['all_valid_watertight_step_ok'] and clash['status'] == 'PASS' and dc['status'] == 'PASS'
          and all(v['passed'] for v in out['dynamics'].values()) and hold_diff < 0.1
          and out.get('browser', {}).get('status') == 'PASS' and out.get('video', {}).get('status') == 'PASS'
          and out['browser']['html_sha256'] == out['files']['preview_sha256'] == out['video']['html_sha256'])
    out = dict(status='PASS' if ok else 'INCOMPLETE', **out)
    (ROOT / 'validation_summary.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1)[:3000])


if __name__ == '__main__':
    main()

"""Verify the retained J6 playback without requiring archived release folders."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    provenance=json.loads((ROOT/'simulation/motion_provenance.json').read_text())
    assert provenance['new_simulation'] is False and provenance['source_revision']=='J6'
    for name,expected in provenance['source_files'].items():
        assert digest(ROOT/'simulation'/name)==expected, f'Playback changed: {name}'
    for name,expected in provenance['moving_input_files'].items():
        assert digest(ROOT.parent/name)==expected, f'Moving geometry input changed: {name}'
    source=json.loads((ROOT/'simulation/demo_report.json').read_text())
    assert source['playback_checks_pass']
    print('Retained J6 trace and moving-input SHA256 checks pass; no new dynamics simulation claimed.')
if __name__=='__main__':main()

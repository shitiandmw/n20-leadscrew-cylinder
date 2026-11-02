# J8 build support

These small modules define the geometry and interface checks still used by J8. Their original names preserve part lineage and imports. They are a dependency library, not archived releases. The old CAD exports, viewers, videos, packaging scripts and release folders have been removed.

- `structure.py` and `check_packaging.py`: retained direct drive and motor envelope geometry.
- `j2_parts.py` through `j7_parts.py`: inherited geometry used to construct the current frame, housing, docking beam, rollers and axle hardware.
- `build_j2.py` and `build_structure.py`: interface checks, assembly export and exact distance helper; old build entry points removed.
- `support_paths.py`: paths to J8 and the repository.

Use `../build_j8.py` for the current design. Retained dimensional regression inputs are in `../../references/retained_dimensions.json`.

## Motion provenance

The delivered playback remains the original unloaded J6 trace, stored in `../../simulation/`. Run `../reuse_motion.py` to verify its hashes. Historical input hashes remain in `motion_provenance.json`; the relocated geometry module has a separate current hash.

For optional reproduction of the original baseline simulation, run `simulate_demo.py` and then `verify_motion_trace.py` from this directory using the CAD interpreter with MuJoCo installed. They write to `../../simulation/recomputed_baseline/simulation/` and do not overwrite the delivered playback. A newly generated result needs separate review before it can replace the saved trace. These scripts do not simulate payload, electrical motor behavior or J8 structural strength.

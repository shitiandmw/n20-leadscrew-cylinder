Track R4 is integrated with the upstream fix for independent boom and slew controls. Rebase conflicts are resolved, the combined preview passes its browser checks, and reports/checksums/archive have been regenerated. No further implementation work is needed.

## Rebase and current behavior

- Branch: `at/093640ce`, rebased onto `d6d4724` (upstream boom-control fix).
- Original track commits: `71d9754` (R3) and `2302f7e` (R4). The rebased R3 commit is `9ba9e91`; the branch tip contains the integrated R4 resolution.
- Preserve the upstream user decision: full 0–60 mm boom stroke is available at every slew angle within ±150°. The old 15 mm / ±20° control interlock must not be reintroduced.
- CAD clearance uses the same sampled region as before, now named `motion.collision_reference_envelope`. Its passing result does not cover every independent control combination. The documented bucket/track collision remains; operators manage clearance.
- `excavator_60mm/HANDOFF.md` preserves the upstream control decision and historical R2 verification. Its new preface directs readers to the current R4 README for mechanical data.

## Track R4 retained

- Real references: Berco sprockets, rollers, track chains and idlers; Caterpillar 320 specifications. Source URLs and manufacturer images are in `excavator_60mm/references/TRACK_SYSTEM.md`.
- A 12-tooth sprocket drives Ø6 OD × Ø3.1 ID × 17 mm steel sleeves on Ø3 × 56 mm pins. Rounded swept pockets, six web openings and 0.5 mm nominal tooth/web clearance are retained.
- Outer guide flanges on road/carrier/idler wheels project 2 mm, with 0.6 mm clearance per side. Carrier centres are X±35 mm.
- Shoes are 54 mm wide on 340 mm centres: 394 mm outside width against a 294 mm aligned platform. Frame/wheel shifts and 92/79 mm drive/free shafts remain unchanged.
- End-wheel axes are raised 2 mm to Z46.321. Exact 20 mm link pitch uses transition slopes and 0.2005025 mm initial idler retraction. The conservative ground-contact half-length is 79.29975 mm.
- The original arm geometry remains unchanged. Physical printing, wear, strength, powered operation and endurance remain untested. The study payload is not a rating.

## Verification

- New browser run passes 375 arm/slew cases, 45 lowering cases through 15.1/15/14.9 mm to zero at nine angles, nine low-boom slew cases, independent endpoint limits and 156 track-playback samples. Offline use, mobile layout, sleeve attachment, wheel phase, take-up, travel and playback controls pass.
- Confirmed all R4 STEP/STL geometry, track physics source, CAD-derived inertias, track traces and track-motion reports are byte-for-byte unchanged from `2302f7e`. Every numerical CAD result also matches after normalizing the report schema rename. These physical simulations were retained, not rerun for the control-only merge.
- Retained CAD results: 644 solids; 1,330 assembly and 1,663 cross-system exact checks; no collisions in the reference samples; 666 reference-boundary cases and the known collision outside the region remain documented.
- Retained physics: two 68,000-step tests; all links complete forward/reverse circuits. Loaded road rollers carry 98.6% of the supported weight. Alternating ±5 N side loads produce at most 0.6219 mm lateral movement. Moving-CAD checks cover 36 poses and 2,449 intersections.
- Calculated mass remains 11.2889 kg; minimum sampled quasi-static stability margin is 33.07 mm. Loaded physics guides chassis pitch/roll/yaw and omits soil, elasticity and dynamic chassis-rail collisions.
- Python/JavaScript syntax checks pass. Regenerated PDFs pass page-bound checks. Package gates, ZIP CRC and every SHA-256 manifest entry pass.

## Outputs and references

- Offline preview: `excavator_60mm/3D_preview.html`.
- Current package: `output/excavator_arm60_tracked_r4.zip`, 101,569,822 bytes, 528 files.
- Archive SHA-256: `38ad029cdaa964e523c08a8ae64a34f0bb4218723bdfeab87fcf7a873bd811b5`.
- Package details: `output/excavator_arm60_delivery.json`; content manifest: `excavator_60mm/SHA256SUMS.txt`.
- Instructions and reports: `excavator_60mm/README.md`, `ASSEMBLY.md`, `BOM.md`, `build_guide.pdf`, `simulation_report.pdf`, `dimension_sheet.pdf`, `track_interfaces.pdf`.
- Latest logs: `/tmp/track-r4-rebase-browser.log`, `/tmp/track-r4-rebase-docs.log`, `/tmp/track-r4-rebase-delivery.log`.

## Environment and future work

- Workspace: `/home/tower/Work/shitian/.worktrees/at/093640ce`.
- Python: `/tmp/venv/bin/python`; CadQuery needs `LD_LIBRARY_PATH=/tmp/v6-cad-libs/extracted/usr/lib/x86_64-linux-gnu`.
- Browser checks: `NODE_PATH=/tmp/v6-preview-tools/node_modules`, the same library path and cached Chromium. Use the offline file URL; no server is needed.
- Shared handoff/service MCP tools were unavailable; this is the local handoff fallback. All jobs were finite. No background service or subagent was started.
- No software follow-up is required. For a later physical build, start with coupons/two links and hand-driven circuits, then follow the assembly guide. Keep paired-cylinder synchronization and independent travel limits; manage bucket/track clearance as documented. Printer-bed splitting remains deferred.

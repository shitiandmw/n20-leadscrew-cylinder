# Open world and sand yard — 2026-11-04 (task 16776c7b)

**Status: the open-world game is built and passes every test, and runs as a preview on port 8090. It is not deployed.** The container on port 8080 still serves the old pit build; rebuilding it needs the user's OK. The sand model and gameplay discussion (item 2 below) is waiting for the user's decision, and nothing from it has been built. This section also includes the phone remote redesign below, since 8080 has neither.

## User request
1. "Make it directly into an open-world game instead of this kind of platform, and make a larger sand yard."
2. "The current sand implementation has problems and will cause many issues, such as the situation in the picture, and particles becoming larger after being dug into the bucket, etc. Discuss a more suitable gameplay approach."

## What changed
- `shared/landscape.js` (new): the world, run by both server and browser. Hard ground on a 160 mm triangle grid, roads, lake, ridge, initial sand, scenery and colliders.
- `shared/world.js`: a 40.96 m world, the 6.4 m `YARD`, chassis pitch and roll, and `armFrame`, the exact tilted frame. The old floor, apron and ramp constants are gone.
- `server/terrain.js`: sparse height field (4096 x 4096 cells of 10 mm, in 64-cell pages that exist only where sand has been).
- `server/physics.js`, `server/bucket.js`: the chassis rides on ground and sand, with pitch and roll. New stops for steep slopes, scenery and deep water. `pressSand` replaces the old track plow. A 2,000-grain budget, past which the bucket bulldozes.
- `shared/protocol.js`: frame version 3, with pitch, roll, a grain origin and sparse tiles.
- `client/world-view.js`, `client/sand-view.js` (new); `client/scene.js`, `client/main.js`, `client/style.css` rewritten or patched: full-window game screen, minimap, following cameras, camera boom that clears buildings, sand chunks with level of detail.

## Root causes found (measured)
- **The fin in the user's screenshot:** the old track plow moved every column under the tracks into one cell beside them. Driving into a 127 mm pile made a 449 mm column at 88 degrees. Now the tracks press a rut of about 4 mm and spread the sand beside them, and the machine rides up piles. The worst fin in the stress run is 44 mm.
- **Particles growing in the bucket (not fixed, see item 2):** two drawings of one material. The bed's speckle is 0.1-0.25 mm and a free grain is an 8 mm ball, about 40 times bigger. Finer grains are not affordable: the solver costs 14 us per grain per tick, so a full 300 cm3 bucket needs 9 ms at 4 mm radius, 75 ms at 2 mm and 600 ms at 1 mm, against a 33 ms tick.

## Other bugs fixed on the way
- **Grains hanging outside a tilted bucket cheek**, caused by the new tilt: `wallPass` treated the shell as wider than the plates. The regression test was confirmed to fail on the old line.
- **Cliff at the lake:** a levelled pad made a 1.2-slope bank. Removed; the shore is now at most 0.5 slope.
- **Room reaped during startup:** rooms now take about 650 ms to create, so the idle clock starts when the room is ready.
- **First frame took 200 s under software rendering:** per-draw canvas blur. Now about 4 s.

## Verification
- `npm test`: 29/29. `npm run test:browser`: all four PASS lines. `bash scripts/check_docker.sh`: PASS (it builds only the test image, so 8080 was untouched).
- Real keyboard playthrough: drove into the yard, climbed the 560 mm pile, pivoted on it, dug, lifted and poured. First scoop from the start: 312 cm3 loaded, 289 after the swing, 296 delivered, 0 wall crossings.
- Stress ticks p99 27 ms, worst 36.7 ms (budget 33 ms). Four digging rooms peak at 242 MB (limit 768 MB). First frame 876 KB, then about 10 KB per frame.
- Seen only under software rendering. **Not tried on a real GPU or a physical phone.**

## Known limits
- The arm and bucket do not collide with buildings or trees, and grains pass through the machine body.
- Trees can block the camera; only buildings shorten its boom.
- `output/arm60-sand-lab.zip` is stale.

## Item 2: what was proposed to the user
- **Sand model, recommended:** height field everywhere, plus a small height field for the load in the bucket's own frame, drawn with the same material. Spill streams are visual-only fine particles and the volume lands on the terrain. Estimated at 1-2 ms per tick (an estimate, not measured). It removes the grain solver.
- **Gameplay, recommended:** free roam plus a job board: load the truck to a target, dig to a blueprint with a percentage overlay, level or build a ramp, clear a road slide. All are scored by comparing height fields.

## Next steps
1. Get the user's choice on the sand model and gameplay, then build it. Keep the full independent 0-60 mm boom stroke at every slew angle within +/-150 degrees; only hard ground stops the bucket.
2. Get a fresh OK before rebuilding: `cd excavator_app && docker compose up --build -d`. It restarts the service and drops open rooms.
3. Try it on a real phone and a real GPU.

---

# Phone remote redesign — 2026-11-04 (task 0c4a82fb)

**Status: built and passing every test, but not deployed.** The container on port 8080 still serves the previous remote; rebuilding it needs the user's OK (see Next steps). The change is in `excavator_app/`, left for the workspace auto-commit. The shared handoff tools and the workspace service tools were unavailable again, so this file is the handoff.

## User request
- "Rebuild the style of the mobile phone remote control so that it looks like a clean remote control with a realistic feel, and add a separate settings button."

## What changed
- `client/remote-face.js` (new): faceplate markup, the SVG seven-segment LCD and haptics.
- `client/remote.css` (new): the hardware look. The old `.remote` rules are gone from `client/style.css`. The desktop simulator looks the same as before.
- **Face:** emergency stop, LCD, two track rockers, a control key (Release / Take control, or Resume while stopped), a separate Settings key and two joysticks. It fills one screen with no scrolling, upright or sideways.
- **Settings sheet:** speed fader, Reset sand, haptics, full screen, room code and Change room, control guide, hold-to-move buttons. It is modal, so opening it stops held input. It has its own emergency stop, because the face is inert underneath, and it closes if anyone hits a stop.
- **Feel:** the thumb cap is grabbed where it lands, so a press alone moves nothing. The boot flexes, the stick springs back, the pushed legend lights up, and rockers tip on a pivot. Haptic pulses need the Vibration API, so iPhone gets none and the setting is hidden there.
- **`client/main.js`:** joysticks are now drawn from CSS variables `--x`, `--y` and `--reach`, on both the remote and the desktop. New LCD status "Take control to resume" for a latched stop with a free operator slot. The remote shows the floor-stop warning too.
- **`index.html`:** inline favicon, which removes the `/favicon.ico` 404 that failed my check of the deployed container.

## Verification
- `npm test`: 18/18. `npm run test:browser`: all four PASS lines, including new `test/remote-ui.js`. `bash scripts/check_docker.sh`: PASS.
- `test/remote-ui.js` covers: 10 phone sizes (390x844 down to 320x454, 844x390 down to 568x320) with no scrolling, controls on screen, no overlaps and thumb-sized targets; cap grab, rockers, haptics and their setting, touch fader, stops from the sheet and from another device, reset, floor warning; and no browser console errors.
- All looks were reviewed from screenshots in emulated mobile Chromium with software rendering. **Not tried on a physical phone**, so real haptics, Safari on iPhone, frame rate and thumb comfort are unconfirmed.

## Next steps
1. Ask the user before rebuilding the container: `cd excavator_app && docker compose up --build -d`. It restarts the service and drops open rooms. The earlier OK covered the sand-physics rebuild only.
2. Try the remote on a real phone and adjust stick size, throw (24 % of the stick's width) and haptic strength if needed.

---

# Sand physics upgrade — 2026-11-03/04 (task 0c4a82fb)

**Status: complete, verified and deployed on 2026-11-04.** Auto-committed as `26d0e00`. The shared task-handoff tools (get/update_task_handoff) and the workspace service tools were unavailable in this session, so this file is the handoff and no long-running service was started.

## User request
- "The sand isn't realistic enough, the physics seems off, and sand sometimes clips through the bucket and ends up outside."

## Root causes found (measured before changing anything)
- Clipping was mainly a **render desync**: the browser drew sand at 15 Hz with exponential smoothing while the bucket moved at 30 Hz unsmoothed. Loaded grains were drawn up to 13.5 mm into the plates (10–23 % of loaded-grain frames). Server-side grains never crossed a wall in 4 aggressive scenarios.
- The old model was 1,876 × 6 mm balls with a liquid (double-density) pressure term, already 23 ms of the 33 ms tick, and the bucket could be driven ~25–60 mm into the concrete.

## What changed
- `server/terrain.js`: sand bed as a 155 × 114 height field (10 mm cells, Float64), angle-of-repose avalanching (34°), exact volume bookkeeping, stockpiles built once.
- `server/bucket.js`: bucket frame, wall segments with CAD-measured plate surfaces (4 mm top, 6 mm back/floor), mouth-crossing tests.
- `server/physics.js`: hybrid model — cutting turns sand entering via the mouth into free grains (4 mm PBD grains with Coulomb friction), closed walls/cheeks bulldoze, overburden becomes grains; resting grains rejoin the bed. Bucket collision uses side memory: cavity membership can only change through the mouth (rollback otherwise). Hard floor stop for the bucket (boom/slew stay independent; no interlock). Tracks plow sand aside.
- `shared/protocol.js` + server/runner/worker: one binary frame per tick with machine pose, grains (Int16) and changed bed tiles; per-client tile versions so skipped frames catch up.
- `client/scene.js`, `client/main.js`: deformable sand mesh (grain texture, damp-looking fresh cuts, dithered edges), instanced grains at physical radius, delayed interpolated playback of pose + sand from the same tick, cm³ load/pour readouts, "bucket on concrete" banner.
- Tests, `scripts/check_docker.sh` (now also checks binary sand frames), new `scripts/capture_docs.mjs`, README and screenshots updated.

## Verification (final code)
- `npm test`: 18/18 pass (re-run 2026-11-04, and again from the extracted zip after `npm run build`). Scoop ≈ 261 cm³, 242 cm³ after lift + 45° swing, 268 cm³ deposited, 0 wall crossings, grain surfaces > −0.25 mm from CAD plates, volume drift < 1e-9.
- `npm run build`, `npm run test:browser` (all PASS), `bash scripts/check_docker.sh` (PASS, no test containers left).
- Render-sync replay: worst drawn grain-to-plate overlap 0.8 mm, none > 1 mm.
- Tick time after warm-up: p50 5.6 ms, p99 13.7 ms (budget 33 ms).

## Deliverable
- `output/arm60-sand-lab.zip` (gitignored download copy, refreshed with the remote redesign): 7,486,710 bytes, 42 files under `arm60-sand-lab/` — source, lockfile, CAD asset, Docker files, tests, scripts, docs, screenshots; no node_modules/dist/test-results. SHA-256 `52167d904b67147968992af168f92dcf1a6a74327742f0145d3c574ad35f0da8` (`output/arm60-sand-lab.sha256`). The source of truth is the tracked `excavator_app/`.

## Open / next
- Done with the user's OK: `excavator_app-sand-lab-1` (port 8080) was rebuilt from this worktree with the new physics. Its server and shared code matched the repo by checksum. A real scoop on it carried 260 cm³ after lifting and 237 cm³ after the swing, and put 250 cm³ in the pour zone. The previous image is still on disk as `170edb8ca0f6`.
- Optional: hydraulic acceleration ramps (would change stop semantics), finer bed cells / overhangs.

---

# Earlier history (2026-10-30)

The notes below describe the first release and a rebase. Where they describe the sand model (1,876 fluid grains), test counts or the old 26-file zip, they are superseded by the section above.

The Docker excavator application is complete in `excavator_app/`. Its original release passed physics, network, browser (including reconnect), dependency audit and container checks. The standalone source package is at `output/arm60-sand-lab.zip`. The current task integrates this application commit with the upstream R3 upper-body changes; see the rebase note below.

## Rebase integration — 2026-10-30

- Requested operation: `30fdd710-a5c7-45c7-9754-e4425e0da9e8`, rebase `at/3883faa9` onto `at/9b573a21` in this worktree. Verified active rebase metadata: source commit `9353248e2717af8ccf5161e6971c065d361c04ff`, target `29a9e0619c01ab2ba12941215fcd22bfd0d06a72`; no remaining todo entries.
- The sole conflict is the root README introduction. The resolution retains the Sand / Lab paragraph and the exact upstream R3 description, including the 308 mm platform, revised cab/equipment/hood layout, counterweight and battery cradle.
- Application files and upstream CAD changes are preserved. This resolution does not regenerate application assets or rerun application tests; the checks below describe the original release. Its exported 644-mesh asset remains based on the pre-R3 viewer, while upstream now has a newer viewer. Regenerating that asset would be a separate application update requiring renewed model-count, rendering and physics validation.
- Shared handoff tools remain unavailable; this local file records the integration. The rebase is continued after staging the resolved README and this note, with branch, clean-tree, ancestry and content preservation checked afterward.

## User request and constraints

- Build from the existing excavator model: a sand-digging simulator with fluid physics, a phone remote, WebSocket communication, and Docker deployment.
- Preserve the earlier mechanical decision: full independent 0–60 mm boom stroke at every slew angle within ±150°. Do not reintroduce a boom/slew interlock.
- Long-running services must use Agent Tower workspace service tools. Those tools and the shared task handoff tools were unavailable in this session. All servers used here are scoped to finite tests and shut down afterward. This file is the local handoff fallback for task `cfd6db38-19af-4d90-8c3f-40e2dc44865a`.
- No subagents were requested or used. No changes to existing CAD or mechanical simulation outputs were made.

## Implementation and decisions

- Application lives separately under `excavator_app/`; the root README links to it.
- Exported all 644 meshes from `excavator_60mm/3D_preview.html`, plus original arm configuration/solver. Export is reproducible with Python 3 and does not require CadQuery. `public/model.json.gz` is committed for standalone Docker builds.
- Node.js authoritative room simulation: 1,876 finite-size grains, 3D position-based granular fluid pressure, contacts, friction and static sleep. Moving bucket colliders use the original shell profile and cheek plates, with an open mouth. Grains are physically carried and spilled.
- Physics is an interactive approximation, not calibrated soil/water or structural analysis. The vehicle is kinematic, with flat-apron differential drive; no two-way soil force, vehicle tipping or self-collision. Track animation follows original chain poses with interpolation.
- Desktop: original CAD, instanced sand, four cameras, local joystick/keyboard controls, telemetry, fullscreen, QR pairing. Phone: separate light page, dual multitouch joysticks, independent tracks, speed control and telemetry.
- WebSocket: one operator per room, observers, input validation/rate limits, 350 ms input watchdog, five-second stale lease, reconnect with neutral input, latched emergency stop. Reset preserves the E-stop latch. Idle rooms expire after ten minutes; defaults allow four rooms and eight clients per room.
- Docker: Node 22 Alpine multi-stage build, locked npm dependencies, non-root runtime, health check, read-only Compose filesystem. Runtime dependencies and development dependencies have zero reported npm audit vulnerabilities after upgrading ws to 8.22.0 and Vite to 7.3.7.

## Verification and references

- `npm test`: five tests pass, including all 125 original kinematic poses, bucket geometry, independent joint limits and real WebSocket clients.
- Physical cycle: lower boom to 0 mm, stick to ~19.5 mm, curl to ~52 mm, lift boom to ~26 mm, swing +45°, open bucket. Collects 23 grains, retains 23 during lift/swing, deposits 21 in the pour zone, conserves all 1,876 grains. Stable pile and floor bounds pass.
- `npm run test:browser`: final full run passed 644-mesh rendering, mobile/desktop layouts, QR links, touch/multitouch/cancel, E-stop, reset, keyboard, ownership handoff, camera views, socket reconnect and neutral-input assertions. Final desktop and phone screenshots were visually inspected and copied into `excavator_app/docs/`.
- `bash scripts/check_docker.sh`: builds `arm60-sand-lab:test`, starts a finite in-container test, verifies non-root UID, HTTP/remote page, all model meshes and WebSocket ownership under read-only/capability-free execution. Passed; no container remains running.
- Container log: `/tmp/sand-lab-docker-check.log`. Browser screenshots: `excavator_app/test-results/desktop.png`, `remote.png`, `mobile-simulator.png`, `pairing.png`.
- Browser command in this environment: `BROWSER_PATH=/home/tower/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome npm run test:browser`. Software WebGL is slow; rendering now sleeps when unchanged and when hidden.
- Read `excavator_app/README.md` for deployment, LAN/Docker pairing address, control mappings, first-scoop sequence, physics limitations, protocol behavior and test commands.
- Node engine metadata is >=22.12 in both package files. At original delivery, the exported asset's source hash matched the then-current offline viewer; ZIP integrity and required contents passed. The upstream R3 viewer now differs as described above.
- Workspace: `/home/tower/Work/shitian/.worktrees/at/3883faa9`; original starting commit `967404e`. Agent Tower committed the application as `9353248` before starting the current rebase.

## Deliverable

- `output/arm60-sand-lab.zip`: 4,605,969 bytes; 26 files. Contains source, locked dependencies, standalone CAD asset, Docker configuration, tests, setup documentation and screenshots. Excludes node_modules, dist and test-results.
- SHA-256: `aa3c5d4fc1d8108d25e185d9330cb3240ddd5a9aa4a03241d7339fed6a3f6418`.
- Manifest: `output/arm60-sand-lab-delivery.json`; checksum: `output/arm60-sand-lab.sha256`.

## Run or continue

1. From `excavator_app/`, run `docker compose up --build -d` in an environment that permits starting the service. In Agent Tower, use its workspace service tools when available.
2. Open `http://localhost:8080`, then use Pair your phone. Set `PUBLIC_URL` or edit the pairing address to the host's reachable LAN IP; Docker automatic discovery may return its internal container IP.
3. Future enhancements could add worker-isolated room simulations, higher particle counts, rigid-body vehicle/soil force feedback, or authenticated public hosting. These are optional extensions, not unfinished requested work.

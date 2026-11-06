# How digging and pouring look — 2026-11-05 (task 57b21694)

**Status: finished and passes every test. Live on port 8092 (workspace service `sand-lab-height-field`). Not deployed; :8080 is still the old pit build. The user asked for angle shots and was given them (`excavator_app/docs/angles/`), but has not said what they think yet. Nothing has been tried on a real GPU.**

## User request
"I just don't think the effect of digging and pouring the sand looks realistic." This also explains the earlier "The performance of this 8092 is not very good": they meant how it looks (performance as in effect), not speed. The speed work below answered the wrong question, though it is still useful.

## What looked fake, from films of the old build
- **Falling sand had about 1/40 of its real cover.** 96 faint dots stood for a parcel whose real grains could hide about 800 mm², so a 170 cm³/s stream was a grey ghost.
- **Velocities were being thrown away:** anything over 60 mm a tick (1.8 m/s, the last part of a tall pour) counted as a teleport. A slot is not reused until thousands of others have been, so the limit is now 100 mm.
- **Nothing happened where sand landed,** or at the end of a pour: full flow to a spotless bucket in under 0.4 s.
- **The bed was smooth,** with detail only below a pixel at the default distance, and changed like soft clay: no moving grains. A dark airbrushed stain spread wherever a cell moved 0.08 mm.
- **The load was a flat pale wedge.**

## What changed (client only; the physics is untouched and tested the same)
- `client/sand-stream.js`: one streak per parcel along its velocity, with cover worked out from what the grains can hide, plus 64 fine grains (24 on touch) for grit. Both stay in the scene drawing nothing when no sand falls. **Do not hide them:** a hidden material's first use moves into the first dig, and under software rendering that cost 6.6 s of blocking calls.
- `client/loose-grains.js` (new): up to 2,400 grains (700 on touch) that fall, bounce and roll with Coulomb friction on the real bed, and dust worked out on the graphics card. Drawn only, per browser, within 3.5 m of the camera.
- `client/loose-sand-view.js`: where they come from. A parcel in one frame and not the next landed, unless it vanished well above the bed, when a bucket caught it. Cells that moved set grains off down the slope. A moving bucket sheds where its sand reaches a rim, and a bucket dribbles off its lip for a second or two after a stream stops.
- `client/sand-relief.js` (new) and `client/sand-material.js`: tiling lump texture (slopes in red and green, height in blue), used by the bed and the load. Lumps by how far sand has moved, lines down slopes near repose, side-projected and stretched in height.
- `client/sand-view.js`: `sandInfo` is now four numbers: thickness, time last dug, crease (Laplacian, no extra height lookups) and how far it has moved. Damp needs 1.5 mm moved and dries in patches. Sand restored by a reset or a new room counts as undisturbed.
- `client/load-mesh.js`: 2.2 mm of relief, thin sand breaks into patches in the shader, and a drawn dusting in a bucket that has held sand.
- `client/sand-flight.js`: `flightRoom` no longer takes the bed height; the bed hides what runs into it.
- `client/scene.js`: grains step by real time in `animate`, so they finish even if frames stop. Catching up after a hidden tab does not fire old splashes (`live`).
- `scripts/capture_comparison.mjs`: takes labels. New `docs/sand-look-before-after.png`, and the README pictures are regenerated.
- `scripts/capture_angles.mjs` (new, finite, about 90 s): nine stills of the standard dig and pour from fixed cameras into `docs/angles/`, plus the sheet `all-angles.jpg`. It serves the real client from a private Vite server, with the camera and clock patched as it is served, so it uses no rooms on 8092. Its `SHOTS` list must stay in tick order.
- Tests: new `test/loose-grains.test.js` (8 cases), updated `test/load-mesh.test.js`, `test/sand-flight.test.js`, `test/sand-visual.js`.

## Flaws still visible in the angle shots (not fixed, waiting on the user)
- Darker blotches with soft, map-like edges on the rim around the pit (full bucket, lifting, finished). This is the first thing I suggested changing.
- The stream splits into long separate strands that look like hanging threads (pouring from the side and far side).
- From low down, the sand still in the bucket is a hard faceted clump at the lip, with a tooth showing through (pouring from low down).
- The bucket stays spotless, flat-shaded orange after digging, which looks clean next to the sand (digging from in front, full bucket).
- A thin jagged bright line along the sand's edge beside the pad, where it lies in shadow (digging from the far side, lower right). Cause not traced.
- Single grains are small rectangles against plain backgrounds, such as the sky or the bucket's underside (lifting, pouring from low down).

## Traps found on the way
- **Hair-like stripes on pit walls** came from the lump tilt, not from the grooves, damp, crease or thin sand; all of those were tested by switching them off. Seen at a low angle, tilted lumps squeeze into feathers, so the tilt fades out as sand reaches repose.
- **Grooves on gentle slopes** become long scratches, because a height-based coordinate stretches. They start only near repose.
- **A dusting that raised the sheet covered the whole floor:** the inner panels sit deeper than the sheet's hidden level, so it needs the shader's patch discard, and is only used when the bucket is really empty.
- **A yes/no "dug" flag per cell** draws stair-steps along the grid. It is a ramp now, broken up with noise.

## Measured
- Peak pour and dig, software rendering, 1000 × 700: frame time +6-7% (pour 42.1 to 44.8 s for 69 ticks, dig 51.9 to 55.8 s for 90 ticks). Script 5 to 7 ms/s while digging, 4 to 5 while pouring, at the 1-2 fps software rendering gives. 2,400 grains cost at most 0.76 ms a frame on this host's CPU, and about 900 are alive at peak.
- Draw calls 243 to 246 in the side view. 294 draw calls and 617 k triangles from the default view on the live preview.
- `npm test` 87/87, `npm run test:browser` all PASS, `npm run test:sand` passes, `scripts/check_docker.sh` PASS, `npm audit` 0, and a live dig and pour on 8092 with no page errors. The service was restarted afterwards, to free its room.

## Not done or not known
- No real GPU, phone or Internet link. Whether 1,000 grains and dust stay smooth on a weak integrated GPU is untested; grains and dust are the things to cut if not.
- The shapes come from the same physics: a dig still raises a broad ring, and a bucket drains at a constant rate to nothing, hidden by the dribble. Cuts stay at 34°, not the steeper faces damp sand holds.
- Grains differ between browsers, and a late joiner sees old digs with grooves but only faint lumps.

---

# Performance — 2026-11-05 (task 57b21694)

**Status: finished and passes every test. Live on port 8092 (workspace service `sand-lab-height-field`). Not deployed; :8080 is still the old pit build. Nothing has been tried on a real GPU or a real Internet link, and the user has not yet said what they see.**

## User request
"The performance of this 8092 is not very good." Taken to mean speed and smoothness, and the user was told so; it could also mean how the sand behaves.

## What was wrong
- **Browser script was not the bottleneck.** With draw calls stubbed, the main thread was about 63% idle at 60 fps.
- **The frame was twice what the counter said:** 2.33 M triangles and 572 draw calls against 1.21 M and 325 shown, because `renderer.info` resets after the shadow pass. The full CAD was drawn in both passes, and every tree and rock in the valley was drawn in both, wherever the camera was.
- **The server cut off busy pages.** It dropped any connection that missed a pong within 5-10 s, and a page cannot answer while it builds the model or while the 897 KB first frame is arriving. It then reconnected and got all the sand again. Through a simulated 1 Mbit/s link that was an 8.5 s freeze with close code 1006.
- **Downloads:** 67 of 68 track links repeated the same geometry (45% of the model), scripts were sent uncompressed, and with no validator every reload fetched the whole model again.

## What changed
- `client/decimate.js`: `clusterMesh` takes optional normals. A cell's vertices meet at one point, so surfaces stay closed, but different directions keep their own vertex, so hard edges stay hard.
- `client/machine-model.js`: `addFarLevel` appends a 1.5 mm level to each batch's own buffers; levels are draw ranges, so changing level does not rebind anything. `setScale` chooses it from pixels per mm, full above 1.33 with slack. `onBeforeShadow`/`onAfterShadow` put the far level in the shadow pass. Links are `InstancedMesh`es (`placeLinks`).
- `client/scene.js`: `renderer.info.autoReset = false`, so `triangles` and `calls` include the shadow pass. `updateMachineDetail`, `AdaptiveResolution`, and `renderer.compile` at load with a sample simplified machine.
- `client/resolution.js` (new): below 45 fps it drops 0.85× a step to a floor of 0.75; it retries after 10 s of fast frames, doubling up to 5 min. If the floor is no faster it restores full resolution and stops. It is off under `navigator.webdriver`.
- `client/world-view.js`: `addInstances` splits trees and rocks into 6 m blocks with bounding spheres. Ground `renderOrder` 1, detail texture anisotropy 2.
- `client/sand-view.js`: no `castShadow`, `renderOrder` -2, and a separate bump texture at anisotropy 2.
- `client/load-mesh.js`: one hidden mesh from the start, so its shader compiles at load.
- `server/index.js`: `heartbeatMs` and `silence` options (simulator 45 s, phone 10 s); any message counts as a sign of life. gzip for text files, `ETag` and 304 for all files.
- `public/model.json.gz` and `scripts/export_model.py`: repeated link geometry removed; all 644 meshes stay listed.
- `client/main.js`: the readout shows fps and resolution.
- Tests: new `test/resolution.test.js`, `test/decimate.test.js`, `test/static-files.test.js`; a new case in `test/network.test.js`; level and frame-budget checks in `test/browser.js`.

## Decisions and traps
- **The model file was stripped in place, not re-exported.** `excavator_60mm/3D_preview.html` no longer matches the sha256 in the asset, so running `scripts/export_model.py` would also bring in whatever changed there. Decide that separately.
- **Sand shadows looked like they mattered and do not.** I first thought removing them cost the pit its depth, and said so to the user. Forcing them on and off in one build differs by at most 1 colour level out of 255. What looked different was bump anisotropy, which is why it is 2, not 1.
- **All 68 links match:** bounding boxes within 0.001 mm. Vertex order differs on the round hardware, because it starts at another angle.
- **Do not load 8092 repeatedly in tests.** Every page without a room link opens a room, the limit is 4, and idle rooms last 10 minutes, so real visitors get "All game rooms are in use". Use `createApplication()` on a private port, or restart the service afterwards.
- **Timings come from SwiftShader,** whose balance differs from a real GPU: draw calls and anisotropic filtering cost it more, and PCF type and early depth rejection hardly register. Triangles and draw calls are exact counts; "real GPUs will gain" is reasoning.

## Verification
- `npm test` 79/79; `npm run test:browser` all five PASS; `npm run test:sand` passes; `bash scripts/check_docker.sh` PASS (test image only); `npm audit --include=dev` 0.
- 1280×800, default view: 2.33 M to 615 k triangles; 572 to 290 draw calls. Bucket view close up: 845 k. Sixteen in view: 1.13 M and 430; pulled right back: 1.42 M and 675.
- Software frame time 3.0 s to about 1.7 s. Script at 60 fps while digging, solo, 283 to about 190 ms/s. Page ready about 4 s, unchanged.
- Simulated link, 240 ms, ±30 ms, 4 Mbit/s: first load 16.0 to 9.9 s (6.31 to 3.62 MB), reload 12.9 to 3.7 s (5.61 to 0.88 MB), no stalls in two further runs. 1 Mbit/s: no disconnect or freeze after the fix. The simulation has no packet loss or TCP backpressure.
- Live on 8092: first scoop lifted 321.5 cm³, 616,700 triangles, 293 calls, no page errors, gzip and 304 confirmed.
- Side-by-side renders at pixel ratios 1 and 1.75, including tracks after driving.

## What it gives up
- Near the switch distance on a high-density screen, the fine ridges on the track shoes merge. Full detail returns on zooming in.
- Each non-link batch carries extra vertex and index data for the far level. The instanced links more than repay it: JS heap after load was about 78 MB on 8092, against 96-154 MB on the older 8091 build.
- A dead simulator connection lingers up to 45 s rather than 10 s. Motion still stops within 350 ms and the control lease ends after 5 s.

## Not fixed
- One digging machine needs about 0.65 Mbit/s; below that the queue and ping grow. `bufferedAmount` only sees Node's buffer, so kernel buffering can hide congestion. Client acknowledgements would fix that if it proves to matter.
- Controls wait for a server round trip plus playback delay; there is no local prediction.
- The first frame is 897 KB; deflate only saves 28% because of the noisy low bytes.
- One small depth shader (`USE_MAP`, for the load) compiles during the first dig.

## Next steps
1. Ask the user for the menu's fps, resolution and ping, their GPU and screen, and whether the problem is frame rate, control lag or how the sand looks.
2. Everything under "Next steps" in the bucket height field section below still stands.

# Bucket height field — 2026-11-05 (task 57b21694)

**Status: built and passes every test. Running as a preview on port 8092 (workspace service `sand-lab-height-field`), beside the previous build on 8091 (`sand-lab-before`, from a temporary copy in `/tmp/sand-lab-before`). It is not deployed.** The container on port 8080 still serves the old pit build; rebuilding it needs the user's fresh OK. The user has not tried it yet.

## User request
"What does the bucket height field approach refer to?", then "Implement it and let me see the effect."

## What changed
- **Grain solver removed** from `server/physics.js`, along with `grainBudget`, `carried`, the marching-cubes surface (`client/sand-surface.js`) and the mouth-crossing tests (`firstCrossing`).
- **`shared/bucket-load.js`**: a 22 × 15 grid in the mouth's axes (u along the mouth from the lip, y across, w out of the mouth, w = 0 at the rims). Each column's floor is the inner plate surface, and columns past the far rim end under the top plate. Struck 306.7 cm³, capacity 356.7.
- **`server/bucket-load.js`**: `BucketLoad`. Surface slopes stay within 34° of level at any tilt. Sand above a rim by more than that goes to `pending`, at up to `SPILL_RATE` a pass, and `spillLoad` in physics emits it as parcels.
- **Down in the sand** (`coverBy`, `fitUnderBed`): the bed is sampled 12 mm *outside* the mouth, because the bucket has already cut the bed at the mouth. Columns under the bed fill to the mouth. Otherwise the sand stands at repose from the bed's edge and from each rim, `PROPPED` = 6 mm higher where the bed buries that rim. `rowRoom` limits inflow per row, and the rest of the cut is bulldozed.
- **Falling parcels** reuse the `grains` wire channel and the stream renderer. They touch nothing on the way down, and join a bucket they fall into or the bed where they land.
- **Protocol v5**: a machine's u16 flag says its load follows; 330 u16 columns per loaded machine.
- **`client/load-mesh.js`**: one sheet per loaded machine, 808 triangles, in bucket-local coordinates. It has a skirt, and dips 1.5 mm behind the plates where sand runs out. A ±1 mm drawn relief, with no volume, slides along u as the load's volume changes. It uses the bed's bump scale (1.4).

## Decisions and traps
- **The load has to be limited to what the posture can hold while digging.** Without `rowRoom`, hundreds of cm³ per half second went in and straight back out at the bed's edge. Without per-row limits, cells earlier in the loop order filled the bucket first, which made a left/right bias.
- **A bed cell spreads over the columns under its 10 mm footprint** (`add`). Dropping it in one column filled every other row.
- **Moves run in mirror order** from the middle row (`relax`), with reversing order each pass. Sweeping rows in one direction gave a 5:1 cheek bias at some tilts.
- **No rim gets an unlimited height.** Buried rims used to mean "no limit", which stood a flat slab 26 mm above the mouth, with a vertical skirt. That is why `PROPPED` exists.
- Tuned by eye and by measurement, not from data: `PROPPED`, `SPILL_RATE`, capacity (struck + 50 cm³), `RELIEF`.
- The solo fingerprint from the multiplayer work no longer applies. Solo physics changed on purpose.

## Verification
- `npm test`: 66/66, about 11 s (it was about a minute). `npm run test:browser`: all five PASS. `npm run test:sand`: passes. `bash scripts/check_docker.sh`: PASS (test image only). `npm audit --include=dev`: 0.
- Live: five bots dug on the running preview with a real browser page watching: loads 313–317 cm³ after the lift, no page errors, largest frame 18 KB.
- First scoop, physics test: 337.6 cm³ loaded, 319.8 carried, 321.2 delivered (old model 311.9, 288.6, 296.3). Volume drift under 1 mm³.
- All 16 machines digging at once: 322–340 cm³ each (old model 30–60).
- `npm run test:load` (4-core host, same process as the clients, no rendering), every machine digging:

| Machines | Ticks/s | Step median / p99 | Ping p99 | Per browser | Memory | Old: ticks, p99, per browser |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 30.2 | 0.4 / 2.2 ms | 0.8 ms | 45 KB/s | 115 MB | 30.1, 21.0 ms, 92 KB/s |
| 4 | 30.1 | 1.0 / 4.7 ms | 1.4 ms | 102 KB/s | 129 MB | 30.1, 34.0 ms, 266 KB/s |
| 8 | 30.1 | 2.0 / 8.8 ms | 1.9 ms | 253 KB/s | 144 MB | 29.7, 39.6 ms, 503 KB/s |
| 16 | 30.1 | 3.6 / 16.7 ms | 3.2 ms | 517 KB/s | 154 MB | 27.7, 47.9 ms, 708 KB/s |

- **Not tried:** a real GPU, a physical phone, a real Internet connection or a real person. The look was judged from software-rendered screenshots only (`docs/height-field-before-after.png`, made by `scripts/capture_comparison.mjs` against commit 1e94d54).

## What it gives up
No grains or clods in a bucket: sand slumps and spills, it does not tumble. Falling parcels pass through machines and plates. A load tilted to its limit is close to a plane, with only the drawn relief on it.

## Next steps
1. See what the user thinks of the look on 8092 against 8091. Stop `sand-lab-before` when it is no longer wanted; its copy in `/tmp` will not last.
2. Ask before rebuilding the :8080 container: `cd excavator_app && docker compose up --build -d`. It drops open rooms.
3. The job-board gameplay is still the user's choice.

---

# Online multiplayer — 2026-11-04 (task 57b21694)

**Status: built and passes every test, and runs as a preview on port 8091 (workspace service `sand-lab-multiplayer`). It is not deployed.** The container on port 8080 still serves the old pit build; rebuilding it needs the user's OK. Nothing is committed by hand: the workspace auto-commits the branch.

## User request
"feat: Add online multiplayer to the excavator app, allowing many people to enter the same room at once, with many excavators appearing."

## How it works
- **Player model.** Each person is a player with an excavator, paint, name and secret key. A room holds up to 16 (`MAX_PLAYERS`). `/?room=CODE` or `/remote?room=CODE` makes a new player. `/remote?room=CODE&pair=KEY` (from **Pair your phone**) attaches a phone to an existing player. The key then moves to `sessionStorage` (`sandlab-player-CODE`) and out of the address bar, so reloading keeps the machine.
- **Control is per machine.** Operator lease, watchdogs and E-stop belong to one machine, and only its player's devices (up to 4) can drive it.
- **Host.** The first player. Only the host can **Reset world**; it passes to the oldest remaining player. Anyone in control can **Back to start**.
- **Leaving.** The machine stays for 30 s marked offline (`graceMs`). After that it is removed, its load falls, and its paint and seat are free.
- **One physics worker per room, shared world.** `server/physics.js` has `Vehicle` objects; each grain answers to one bucket at a time. Solo physics is bit-identical to before (fingerprint checked).
- **Crawlers stop at crawlers** (`obstacle: "machine"`); moves that increase separation are always allowed. Arms and buckets pass through other machines, by design and like scenery.
- **Protocol v4** (`shared/protocol.js`): all machine poses, grain groups with their holder, tiles.
- **Rendering.** Only the machine the camera follows is full CAD. Others are a clustered proxy (`client/decimate.js`, `client/machine-model.js`). Clicking a roster row watches that machine.
- **Playback delay** grows with measured frame jitter, by up to 200 ms (`client/frame-jitter.js`).

## Bugs found by looking, not by tests
- **Start positions blocked cameras.** The back-row seats stood on other players' chase cameras. All 17 seats now face sand along the yard's west, south and north edges (`shared/players.js`), and a test forbids a seat between another's camera and machine. Every seat scoops 273-311 cm3 alone.
- **Camera wall filter** still counted low barriers; one rule now lives in `cameraWall` in `shared/landscape.js`, shared with the test.
- **Load ranking** took a `Vector3` as an array, giving NaN distances.
- **Physics tick rate halved** once a step passed 33 ms (timer quantization); an overdue step now starts when the last ends (`overdue` in the runner).
- **Player list covered the buttons at phone width.** `--actions-bottom` now follows the wrapped button row.
- `scripts/capture_docs.mjs` and visual checks must drive by simulation ticks, not wall-clock time: under software rendering the physics slows and a timed dig never reaches the sand.

## Verification
- `npm test`: 53/53. `npm run test:browser`: all five PASS lines, including the new `test/multiplayer-ui.js`. `npm run test:sand`: passes, scoop still 311.9 cm3. `bash scripts/check_docker.sh`: PASS (it builds only the test image, so 8080 was untouched). `npm audit --include=dev`: 0 vulnerabilities.
- `npm run test:load` (4-core host, same process as the clients, no rendering), every machine digging:

| Machines | Ticks/s | Step median / p99 | Ping p99 | Per browser | Memory |
| --- | --- | --- | --- | --- | --- |
| 1 | 30.1 | 1.4 / 21.0 ms | 0.7 ms | 92 KB/s | 120 MB |
| 4 | 30.1 | 5.8 / 34.0 ms | 1.3 ms | 266 KB/s | 139 MB |
| 8 | 29.7 | 8.2 / 39.6 ms | 2.1 ms | 503 KB/s | 175 MB |
| 16 | 27.7 | 9.7 / 47.9 ms | 3.6 ms | 708 KB/s | 176 MB |

- Scene under software rendering: 1.20 M triangles and 321 draw calls alone; 1.40 M and 352 with 16 machines in Chase; 1.65 M and 593 with all 16 in frame. Frame rate was 0-1 fps there, so it says nothing about a real GPU.
- **Not tried:** a real GPU, a physical phone, a real Internet connection or more than one real person. All clients were on this host, and jitter handling has only a unit test.

## Known limits
- **Scoop size shrinks when many dig at the same moment.** About 2,000 free grains are shared: 2-3 machines still fill a bucket, 4 get about 220 cm3, 8 get 70-110, 16 get 30-60. Lifting this needs the height-field load in the sand-model decision below, not more tuning.
- A full room is about 90 Mbit/s upload from the server, and 16 digging at once runs at about 92% of real time.
- The room code is not authentication; Internet hosting needs HTTPS and access control in front (README).
- A big-screen page is itself a player and owns an idle excavator.
- `scripts/capture_docs.mjs` once failed with a one-off `Page.captureScreenshot` protocol error under load; rerunning passed.

## Next steps
1. Get a fresh OK before rebuilding: `cd excavator_app && docker compose up --build -d`. It restarts the service and drops open rooms.
2. Try it with real people on real devices, over the Internet if that is the goal. Host it with `PUBLIC_URL` set, behind HTTPS.
3. The sand model and job-board decision from the section below is still the user's.

---

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

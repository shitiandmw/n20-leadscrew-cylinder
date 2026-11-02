# Sand / Lab

A Docker-deployable excavator sandbox with a phone remote. The desktop renders the existing **ARM60 / Track R4 model, including all 644 CAD meshes**. A Node.js server simulates the excavator and 1,876 sand particles; browsers exchange controls and live state over WebSocket.

![Desktop sandbox](docs/desktop.png)

## Run with Docker

From this directory:

```sh
docker compose up --build -d
```

Open **http://localhost:8080** on your computer. A new sandbox gets a six-character room code. Click **Pair your phone**, scan the QR code, and keep the simulator visible on the computer. The remote automatically takes control when the operator slot is free. If the desktop already has control, click **Release** first.

Both devices must be able to reach the server. From a phone, use the computer's LAN IP, for example `http://192.168.1.20:8080`. A phone's `localhost` points to the phone itself. The pairing dialog lets you correct the address; automatic address discovery inside Docker may show a container IP, so explicitly set the host address when needed:

```sh
PUBLIC_URL=http://192.168.1.20:8080 docker compose up --build -d
```

The simulator is at `/`; the touch remote is at `/remote`. You can also enter the displayed code on `/remote`, or share `/remote?room=A1B2C3`. Several simulator pages can observe the same room using `/?room=A1B2C3`. The physics continues when only a remote is connected.

```sh
docker compose logs --tail=100
docker compose down
```

The image runs as the unprivileged `node` user, supports a read-only filesystem, has a health check, and handles SIGTERM/SIGINT. No database, GPU, volume, or external CDN is required by the server. Building requires access to the npm registry and Docker base image; browser assets are served locally after the build.

## Operate

Move a joystick, hold a drive button, or press a movement key to take control when the operator slot is free, on either a computer or a phone. **Take control** is also available. If another operator is driving, they must select **Release** first. On a phone, use the two touch joysticks together; each supports an independent touch contact. Release a joystick or track button to stop that input. Movement starts only after the server grants control, using inputs that are still held.

| Control                       | Motion                     | Keyboard |
| ----------------------------- | -------------------------- | -------- |
| Left joystick up / down       | Stick out / in             | W / S    |
| Left joystick left / right    | Upper body slew            | A / D    |
| Right joystick up / down      | Boom lower / raise         | ↑ / ↓    |
| Right joystick left / right   | Bucket curl / open         | ← / →    |
| Left track forward / reverse  | Left track drive           | Q / Z    |
| Right track forward / reverse | Right track drive          | E / C    |
| Emergency stop                | Latch all drive inputs off | Space    |

The expandable control guide also provides keyboard-focusable buttons: hold Enter to operate them. Movement speed scales every axis. The current stick and bucket strokes are shown beneath the joysticks; boom stroke and bucket load appear in the telemetry.

**A first scoop from the reset pose:**

1. Lower the boom to **0 mm**.
2. Crowd the stick to approximately **20 mm** to cut into the pile.
3. Curl the bucket to approximately **52 mm**. Curling fully enough keeps the lip above the load during lifting.
4. Raise the boom to approximately **26 mm**.
5. Swing approximately **+45°** toward the outlined pour zone.
6. Open the bucket toward **0 mm** and watch the grains fall.

The deterministic physics test runs this cycle, collects 21 grains, carries them through the lift and swing, and deposits 19 in the receiving zone. The remaining grains land outside the marked zone; no grains are created or removed. Counts describe simulation particles, not real payload capacity.

**Emergency stop** is available to every connected client. The current operator must explicitly select **Resume operation** to clear it. Resetting the sandbox does not clear a latched stop. Input becomes neutral after 350 ms without a valid control packet, on socket disconnect, on touch cancellation, and when the page loses focus. Changing apps releases ownership; use a control after returning to reclaim it if the slot is free. An operator lease expires after five seconds without input. Reconnection starts with neutral controls and does not displace an existing operator.

![Phone remote](docs/remote.png)

## Simulation and model

`scripts/export_model.py` extracts the committed offline viewer at `../excavator_60mm/3D_preview.html` and the original arm solver. It requires Python 3 only, not CadQuery. The exported `public/model.json.gz`, `shared/config.js`, and `shared/kinematics.js` are committed so this folder can be built independently of the rest of the repository. The compressed model includes the original viewer's SHA-256 for provenance. Run `npm run export:model` from the full repository to regenerate it.

The shared linkage solver retains all 0–60 mm actuator travel and independent ±150° slew. Rendering moves the boom, stick, bucket, four cylinders, linkage, slew gearing, track shoes and wheels. The crawler uses differential-drive kinematics across the entire map, including a ramp between the raised apron and sand pit. Both tracks together drive forward or backward; opposing tracks turn in place. Its rotated footprint stays inside the outer walls. The chassis remains level at the highest terrain beneath its footprint, and the bucket collision height follows the chassis. This is a simplified terrain model without suspension or tipping. It does not replay or rerun the original MuJoCo track experiment. Track articulation is interpolated along the original chain poses, so the animation is a visual approximation between those poses.

The sand uses **3D position-based granular fluid physics**:

- Gravity in model millimetres, finite-size particle contacts, double-density pressure relaxation, tangential friction, and static-friction sleep.
- A spatial hash for neighbouring grains; four 1/120 s substeps and five contact passes per 1/30 s simulation tick.
- Moving colliders derived from the actual bucket shell profile and cheek plates. The mouth is open. Grains enter, remain physically contained, and spill through it under gravity; they are never attached to the bucket or replaced by a fill animation.
- Pit floor, boundary walls, apron and ramp contacts, a fixed particle count, and measured receiving-zone counts. Fully settled sand sleeps until controls or motion disturb it.

This is an interactive approximation of coarse sand flow, not a calibrated soil, water, load, traction, or structural engineering model. It uses 6 mm-radius proxy grains, a simplified bucket collider without individual teeth, and kinematic machinery. There is no two-way soil force feedback, deformable terrain under the tracks, self-collision protection, water phase, or rigid-body vehicle tipping. The full independent boom/slew travel intentionally preserves the original model's operator-managed clearance. At high CPU load the fixed-step simulation runs slower than real time instead of increasing the step size.

The simulator needs WebGL2. The phone remote uses only HTML controls and telemetry; it does not download Three.js or the CAD asset. On touch devices the 3D simulator caps pixel ratio at 1 and disables shadows and antialiasing to reduce GPU cost while retaining all CAD parts. Rendering is skipped for an unchanged scene, and hidden tabs also skip scene updates. Software-only graphics can be slow; a hardware-accelerated browser is recommended for the 776,942-triangle assembly.

Control starts, reversals and stops send immediately. Continuous pointer motion is coalesced at 30 Hz, with a 100 ms heartbeat while holding controls. Each room runs physics in its own worker, leaving the HTTP/WebSocket thread free to process input, pings, ownership and watchdogs. Only one physics step per room can be in flight; slower hardware does not build a queue of old inputs. Machine state is published after each completed step (up to 30 Hz), with sand at up to 15 Hz for simulator clients only. Congested sockets skip snapshots until they can accept fresh state. Worker resources are released on room expiry and server shutdown.

## Configuration and hosting

| Setting      | Default | Meaning                                                                                                     |
| ------------ | ------- | ----------------------------------------------------------------------------------------------------------- |
| `PORT`       | `8080`  | Native server port; Compose uses this for the published host port and keeps port 8080 inside the container. |
| `PUBLIC_URL` | empty   | Public or LAN origin encoded in the pairing QR code. Use an origin without a path prefix.                   |
| `MAX_ROOMS`  | `4`     | Maximum in-memory sandboxes. Lower it on small CPUs.                                                        |

Each room permits eight clients and one active operator. Empty rooms expire after ten minutes. Rooms and sand state are held in memory and reset on server restart. Health status is available at `/api/health`.

Opening an expired simulator link, or reconnecting after a server restart, automatically creates a fresh sandbox and updates the URL, room code and pairing links. Pair your phone again using the new code. An expired phone link displays an explanation and an **Enter room code** link; it never creates a separate sandbox. Temporary connection failures retry the existing room. A persistent connection notice provides a manual retry when needed.

The six-character code is a pairing mechanism for a trusted network, not user authentication. For Internet hosting, place access control and HTTPS in front of the app. Serve it at the domain root and proxy `/ws` with WebSocket upgrades. The browser automatically selects `wss://` for HTTPS. Preserve the original Host header so the server's same-origin checks pass. An Nginx location inside an existing HTTPS server can use:

```nginx
location / {
    proxy_pass http://127.0.0.1:8080;
    proxy_http_version 1.1;
    proxy_set_header Host $http_host;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 60s;
}
```

If the phone cannot connect, first open the server's `/api/health` URL from the phone. Check the host IP/port, local firewall, Wi-Fi client isolation, and the QR address. If control is occupied, release it on the other device. A new sandbox is created by opening `/` without a room query.

## Develop and verify

Use Node.js 22.12 or newer and npm:

```sh
npm ci --include=dev
npm run build
npm start
```

The production server serves the built `dist/` directory. Rebuild after client changes; restart after server changes. A separate Vite development server is unnecessary.

```sh
npm test
npx playwright install chromium
npm run test:browser
bash scripts/check_docker.sh
npm audit --include=dev
```

The browser test starts a temporary server and always closes it. `BROWSER_PATH` can select an existing Chromium executable. Screenshots are written to `test-results/`.

Checks cover all 125 original CAD kinematic poses, bucket contacts and its open mouth, stable sand, a complete physical scoop/lift/swing/pour cycle, conservation, independent slew/boom travel, whole-map driving and ramp heights, WebSocket ownership and validation, stale-input/disconnect stops, a latched E-stop, worker reset and cleanup, four-room phone round trips, immediate/coalesced input, touch/multitouch/cancel, reconnect, keyboard controls, QR links, camera views, and desktop/mobile layouts and graphics settings. The Docker smoke test runs the actual server inside a non-root, read-only container and checks HTTP, model delivery and WebSocket operation.

## Files

| Path                         | Purpose                                                            |
| ---------------------------- | ------------------------------------------------------------------ |
| `server/index.js`            | HTTP, WebSocket rooms, operator leases, watchdogs and snapshots    |
| `server/simulation-runner.js`, `server/physics-worker.js` | Isolated room physics, bounded work, reset synchronization and cleanup |
| `server/physics.js`          | Granular fluid solver, machine motion and bucket contacts          |
| `shared/`                    | Original configuration and kinematics; simulation dimensions       |
| `client/main.js`             | Simulator and remote interfaces, pairing, touch and keyboard input |
| `client/scene.js`            | Three.js model assembly, sand instances, cameras and track motion  |
| `public/model.json.gz`       | Original CAD meshes and provenance                                 |
| `test/`                      | Numerical, network and browser checks                              |
| `Dockerfile`, `compose.yaml` | Production deployment                                              |

The existing model retains its original licensing status; this application does not assign it a new license. Three.js and the other npm packages retain their respective licenses.

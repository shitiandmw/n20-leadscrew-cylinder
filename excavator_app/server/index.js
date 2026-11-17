import http from "node:http";
import { readFile, stat } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { randomBytes, randomUUID } from "node:crypto";
import { networkInterfaces } from "node:os";
import { promisify } from "node:util";
import { gunzipSync, gzip } from "node:zlib";
import { WebSocketServer, WebSocket } from "ws";
import { SimulationRunner } from "./simulation-runner.js";
import { Delivery } from "./delivery.js";
import { AXES, crawlerBox, crawlersOverlap } from "../shared/world.js";
import { TRUCK_AXES, boxesOverlap, truckBox } from "../shared/truck.js";
import { encodeFrame, TILE_COUNT } from "../shared/protocol.js";
import {
  DEFAULT_PLAYERS,
  PAINTS,
  SPAWNS,
  TRUCK_BAYS,
  spawnMachine,
  parkedTruck,
  cleanName,
} from "../shared/players.js";

const ROOT = fileURLToPath(new URL("../dist/", import.meta.url));
// Text files are compressed once, on first request, away from the game's thread.
const COMPRESSIBLE = /\.(?:html|js|css|svg)$/,
  compressed = new Map(),
  gzipped = promisify(gzip);
// Control messages are small and must arrive even on a socket that is behind
// with its frames (frames and state wait for an empty buffer; see publishFrame):
// a player on a slow computer would otherwise miss notices, errors and pongs.
// Only a socket whose buffer has grown past all reason is left alone.
const send = (ws, message) => {
  if (ws.readyState === WebSocket.OPEN && ws.bufferedAmount < 8_000_000)
    ws.send(JSON.stringify(message));
};
// A person's computer and phone drive one excavator; a few tabs are fine too.
const DEVICES_PER_PLAYER = 4;
// The controls of each machine; the one a player is not driving keeps them at 0.
const EXCAVATOR_AXES = AXES.filter((key) => !TRUCK_AXES.includes(key)),
  MACHINES = ["excavator", "truck"];
export function createApplication({
  maxRooms = Number(process.env.MAX_ROOMS) || 4,
  maxPlayers = Number(process.env.MAX_PLAYERS) || DEFAULT_PLAYERS,
  idleMs = 600_000,
  // A reloading page or a phone that lost signal keeps its excavator this long.
  graceMs = 30_000,
  heartbeatMs = 5000,
  // How long a connection may stay silent before it is given up on. A simulator
  // page cannot answer while it builds the model or while the first frame, nearly
  // a megabyte of sand, is on its way down a slow link; dropping it then only means
  // sending all that again. A phone gets little data, and its silence means more.
  silence = { simulator: 45_000, remote: 10_000 },
} = {}) {
  const rooms = new Map(),
    capacity = Math.min(maxPlayers, SPAWNS.length, PAINTS.length);
  const json = (res, status, body) => {
    res.writeHead(status, {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    });
    res.end(JSON.stringify(body));
  };
  const server = http.createServer(async (req, res) => {
    res.setHeader("X-Content-Type-Options", "nosniff");
    res.setHeader("Referrer-Policy", "same-origin");
    res.setHeader(
      "Content-Security-Policy",
      "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' ws: wss:; frame-ancestors 'self'",
    );
    try {
      const url = new URL(req.url, "http://localhost");
      if (url.pathname === "/api/health") {
        let players = 0;
        for (const room of rooms.values()) players += room.players.size;
        return json(res, 200, { ok: true, rooms: rooms.size, players });
      }
      if (url.pathname === "/api/network") {
        const port = server.address().port;
        const origins = Object.values(networkInterfaces())
          .flat()
          .filter((a) => a.family === "IPv4" && !a.internal)
          .map((a) => `http://${a.address}:${port}`);
        return json(res, 200, {
          publicUrl: process.env.PUBLIC_URL || null,
          origins,
        });
      }
      if (url.pathname.startsWith("/api/rooms/") && req.method === "GET") {
        const code = url.pathname.slice("/api/rooms/".length).toUpperCase();
        const room = rooms.get(code);
        if (!room)
          return json(res, 404, {
            code: "ROOM_NOT_FOUND",
            error: "This room has expired or the server has restarted.",
          });
        return json(res, 200, {
          room: code,
          players: room.players.size,
          capacity,
          // A returning player still has a seat, even in a full room.
          member: !!findPlayer(room, url.searchParams.get("key")),
        });
      }
      if (url.pathname === "/api/rooms" && req.method === "POST") {
        if (
          req.headers.origin &&
          new URL(req.headers.origin).host !== req.headers.host
        )
          return json(res, 403, {
            error: "Origin does not match this server.",
          });
        if (rooms.size >= maxRooms)
          return json(res, 503, {
            error:
              "All game rooms are in use. Join an existing room or try again later.",
          });
        let code;
        do {
          code = randomBytes(3).toString("hex").toUpperCase();
        } while (rooms.has(code));
        const room = {
          code,
          clients: new Map(),
          players: new Map(),
          nextPlayer: 1,
          // The first player in the room; passes on when they leave for good.
          host: null,
          rosterVersion: 0,
          // The idle clock starts once the room can be joined.
          emptySince: Infinity,
          frame: 0,
          stepMs: 0,
        };
        room.simulation = new SimulationRunner(
          () => publishFrame(room),
          (error) => {
            console.error(`Room ${code}:`, error);
            for (const ws of room.clients.keys())
              ws.close(1011, "Simulation unavailable");
            rooms.delete(code);
            void room.simulation.close();
          },
        );
        rooms.set(code, room);
        await room.simulation.ready;
        room.emptySince = Date.now();
        return json(res, 201, { room: code });
      }
      if (url.pathname.startsWith("/api/"))
        return json(res, 404, { error: "Unknown endpoint." });
      if (!["GET", "HEAD"].includes(req.method))
        return json(res, 405, { error: "Method not allowed." });
      const requested = decodeURIComponent(url.pathname);
      const filename =
        requested === "/" || requested === "/remote"
          ? "index.html"
          : requested.replace(/^\/+/, "");
      const target = path.resolve(
        ROOT,
        filename === "model.json" ? "model.json.gz" : filename,
      );
      if (!target.startsWith(ROOT))
        return json(res, 403, { error: "Forbidden." });
      const types = {
        ".html": "text/html; charset=utf-8",
        ".js": "text/javascript",
        ".css": "text/css",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".json": "application/json",
      };
      res.setHeader(
        "Content-Type",
        filename === "model.json"
          ? "application/json"
          : types[path.extname(filename)] || "application/octet-stream",
      );
      res.setHeader(
        "Cache-Control",
        filename.startsWith("assets/")
          ? "public, max-age=31536000, immutable"
          : "no-cache",
      );
      res.setHeader("Vary", "Accept-Encoding");
      // A reload over a slow link costs nothing if the file has not changed.
      const { size, mtimeMs } = await stat(target),
        tag = `W/"${size.toString(36)}-${Math.round(mtimeMs).toString(36)}"`;
      res.setHeader("ETag", tag);
      if (req.headers["if-none-match"] === tag) {
        res.writeHead(304);
        return res.end();
      }
      let body = await readFile(target);
      const acceptsGzip = /\bgzip\b/.test(req.headers["accept-encoding"] || "");
      if (filename === "model.json") {
        if (acceptsGzip) res.setHeader("Content-Encoding", "gzip");
        else body = gunzipSync(body);
      } else if (acceptsGzip && COMPRESSIBLE.test(filename)) {
        const key = target + tag;
        if (!compressed.has(key)) compressed.set(key, gzipped(body));
        body = await compressed.get(key);
        res.setHeader("Content-Encoding", "gzip");
      }
      res.setHeader("Content-Length", body.length);
      res.writeHead(200);
      res.end(req.method === "HEAD" ? undefined : body);
    } catch (error) {
      json(res, error.code === "ENOENT" ? 404 : 400, {
        error: error.code === "ENOENT" ? "Not found." : "Invalid request.",
      });
    }
  });
  const wss = new WebSocketServer({
    noServer: true,
    maxPayload: 2048,
    perMessageDeflate: false,
  });
  server.on("upgrade", (req, socket, head) => {
    try {
      const url = new URL(req.url, "http://localhost"),
        room = rooms.get(url.searchParams.get("room")),
        player = room && findPlayer(room, url.searchParams.get("key"));
      if (
        url.pathname !== "/ws" ||
        !room ||
        (player
          ? player.sockets.size >= DEVICES_PER_PLAYER
          : room.players.size >= capacity) ||
        (req.headers.origin &&
          new URL(req.headers.origin).host !== req.headers.host)
      ) {
        socket.end("HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n");
        return;
      }
      wss.handleUpgrade(req, socket, head, (ws) =>
        wss.emit(
          "connection",
          ws,
          req,
          room,
          player ?? addPlayer(room, url.searchParams.get("name")),
          url.searchParams.get("role") === "remote" ? "remote" : "simulator",
        ),
      );
    } catch {
      socket.destroy();
    }
  });
  function findPlayer(room, key) {
    if (key)
      for (const player of room.players.values())
        if (player.key === key) return player;
    return null;
  }
  // A place to start that nobody else is using and no machine is parked on. If
  // every free place has a machine on it, the two can drive apart again.
  function freeSpawn(room, self) {
    const others = [...room.players.values()].filter((p) => p !== self),
      assigned = new Set(others.map((p) => p.spawn));
    let fallback = -1;
    for (let spawn = 0; spawn < SPAWNS.length; spawn++) {
      if (assigned.has(spawn)) continue;
      if (fallback < 0) fallback = spawn;
      const pose = spawnMachine(spawn),
        box = crawlerBox(pose);
      if (
        !others.some((p) => crawlersOverlap(pose, p.vehicle.machine)) &&
        ![...room.players.values()].some((p) =>
          boxesOverlap(box, truckBox(p.truck.pose)),
        )
      )
        return spawn;
    }
    return fallback;
  }
  // Where a player's truck waits: the bay of their seat if it is clear, or the
  // first other bay nobody has and no machine stands on.
  function freeBay(room, self, seat) {
    const others = [...room.players.values()].filter((p) => p !== self),
      assigned = new Set(others.map((p) => p.bay)),
      clear = (bay) => {
        const box = truckBox(parkedTruck(bay));
        return !others.some(
          (p) =>
            boxesOverlap(box, crawlerBox(p.vehicle.machine)) ||
            boxesOverlap(box, truckBox(p.truck.pose)),
        );
      };
    if (seat < TRUCK_BAYS.length && !assigned.has(seat) && clear(seat)) return seat;
    let fallback = -1;
    for (let bay = 0; bay < TRUCK_BAYS.length; bay++) {
      if (assigned.has(bay)) continue;
      if (fallback < 0) fallback = bay;
      if (clear(bay)) return bay;
    }
    return fallback;
  }
  function addPlayer(room, name) {
    const inUse = new Set([...room.players.values()].map((p) => p.seat));
    let seat = 0;
    while (inUse.has(seat)) seat++;
    const id = room.nextPlayer++,
      spawn = freeSpawn(room, null),
      bay = freeBay(room, null, seat),
      player = {
        id,
        // Possession of this secret is what makes a device this player: a page
        // that reloads, or a phone that scans the pairing code.
        key: randomBytes(16).toString("base64url"),
        seat,
        spawn,
        bay,
        name: cleanName(name) || `Player ${seat + 1}`,
        vehicle: room.simulation.addVehicle(id, spawnMachine(spawn)),
        // Each player has a dump truck too, and drives one machine at a time.
        truck: room.simulation.addTruck(id, parkedTruck(bay)),
        driving: "excavator",
        sockets: new Set(),
        owner: null,
        lastInput: 0,
        leftAt: 0,
      };
    room.players.set(id, player);
    room.host ??= id;
    room.rosterVersion++;
    return player;
  }
  function removePlayer(room, player) {
    room.players.delete(player.id);
    room.simulation.removeVehicle(player.vehicle);
    room.simulation.removeTruck(player.truck);
    if (room.host === player.id)
      room.host = room.players.keys().next().value ?? null;
    room.rosterVersion++;
  }
  function snapshot(room, player) {
    const s = room.simulation,
      v = player.vehicle;
    return {
      type: "state",
      machine: v.machine,
      speed: v.speed,
      estop: v.estop,
      tick: s.tick,
      count: s.count,
      stats: { ...v.stats, ...s.world },
      // Which machine this player's controls drive, and their truck.
      driving: player.driving,
      truck: player.truck.pose,
      truckStats: player.truck.stats,
      owner: player.owner,
      clients: [...player.sockets].map((ws) => {
        const { id, role } = room.clients.get(ws);
        return { id, role };
      }),
      host: room.host === player.id,
      stepMs: Math.round(room.stepMs * 10) / 10,
    };
  }
  // Each player hears about their own excavator. A socket that is behind with
  // its frames skips the periodic telemetry, but never a change of who is in
  // control, of the stop or of the host: a page that did not hear its claim was
  // granted never starts sending inputs, loses the lease, and its next press of
  // the control key releases instead of claiming. A simulator page draws the
  // machines from its frames, so its readouts come at most every third tick:
  // three ticks after the last, not on ticks that are multiples of three, which
  // a socket that keeps being busy on those ticks would never be sent.
  function broadcast(room, player, periodic = false) {
    const control = `${player.owner}:${player.vehicle.estop}:${room.host === player.id}:${player.driving}`,
      tick = room.simulation.tick,
      now = performance.now();
    let packet;
    for (const ws of player.sockets) {
      const client = room.clients.get(ws);
      if (ws.readyState !== WebSocket.OPEN) continue;
      if (
        client?.control === control &&
        (ws.bufferedAmount !== 0 ||
          client.delivery?.behind(now) ||
          // Ticks start again after a reset.
          (periodic &&
            client.role === "simulator" &&
            Math.abs(tick - client.stateTick) < 3))
      )
        continue;
      packet ??= JSON.stringify(snapshot(room, player));
      ws.send(packet);
      if (!client) continue;
      client.control = control;
      client.stateTick = tick;
      // A phone acknowledges its state; a simulator page, its frames.
      if (client.role === "remote") client.delivery?.sent(tick, now);
    }
  }
  // Who is here. Each client tracks the version it holds, so a congested socket
  // catches up later instead of losing a change.
  function publishRoster(room) {
    let packet;
    for (const [ws, client] of room.clients) {
      if (
        client.rosterVersion === room.rosterVersion ||
        ws.readyState !== WebSocket.OPEN ||
        ws.bufferedAmount !== 0
      )
        continue;
      packet ??= JSON.stringify({
        type: "roster",
        capacity,
        host: room.host,
        players: [...room.players.values()].map(
          ({ id, name, seat, sockets, driving }) => ({
            id,
            name,
            paint: PAINTS[seat],
            online: sockets.size > 0,
            driving,
          }),
        ),
      });
      ws.send(packet);
      client.rosterVersion = room.rosterVersion;
    }
  }
  function publishFrame(room) {
    room.stepMs = room.simulation.stepMs;
    publishRoster(room);
    for (const player of room.players.values()) broadcast(room, player, true);
    // Simulators get every machine's pose and load, the falling sand and changed
    // sand-bed tiles of the same tick. Each client tracks which tile versions it holds, so
    // a congested socket, or one that is behind (see server/delivery.js), can
    // skip frames and later catch up on every change.
    const s = room.simulation,
      frame = {
        tick: s.tick,
        machines: [...s.vehicles.values()].map((v) => ({
          id: v.id,
          ...v.machine,
          load: v.load,
        })),
        trucks: [...s.trucks.values()].map((t) => ({
          id: t.id,
          ...t.pose,
          load: t.load,
        })),
        grains: s.grains,
        groups: s.groups,
        tileData: s.tileData,
      };
    room.frame++;
    const now = performance.now();
    for (const [ws, client] of room.clients) {
      if (
        client.role !== "simulator" ||
        ws.readyState !== WebSocket.OPEN ||
        ws.bufferedAmount !== 0 ||
        client.delivery?.behind(now)
      )
        continue;
      client.tiles ??= new Uint32Array(TILE_COUNT);
      const tiles = [];
      for (const t of s.tileData.keys())
        if (client.tiles[t] !== s.tileVersions[t]) tiles.push(t);
      ws.send(encodeFrame({ ...frame, tiles }));
      client.delivery?.sent(s.tick, now);
      for (const t of tiles) client.tiles[t] = s.tileVersions[t];
    }
  }
  // Both of a player's machines stop.
  function halt(room, player) {
    room.simulation.stop(player.vehicle);
    room.simulation.stopTruck(player.truck);
  }
  function release(room, player) {
    player.owner = null;
    halt(room, player);
  }
  wss.on("connection", (ws, req, room, player, role) => {
    const vehicle = player.vehicle,
      client = {
        id: randomUUID(),
        role,
        heardAt: Date.now(),
        window: Date.now(),
        messages: 0,
        rosterVersion: 0,
        stateTick: -Infinity,
        // A page that acknowledges its updates is sent no more than its
        // connection carries; one from before that is sent what its socket takes.
        delivery:
          new URL(req.url, "http://localhost").searchParams.get("acks") === "1"
            ? new Delivery()
            : null,
      };
    room.clients.set(ws, client);
    player.sockets.add(ws);
    room.emptySince = null;
    room.rosterVersion++;
    send(ws, {
      type: "welcome",
      id: client.id,
      room: room.code,
      player: {
        id: player.id,
        key: player.key,
        name: player.name,
        paint: PAINTS[player.seat],
      },
    });
    publishRoster(room);
    broadcast(room, player);
    ws.on("pong", () => {
      client.heardAt = Date.now();
    });
    ws.on("error", () => ws.close());
    ws.on("message", (bytes, binary) => {
      client.heardAt = Date.now();
      const now = Date.now();
      if (now - client.window > 1000) {
        client.window = now;
        client.messages = 0;
      }
      // Inputs come at up to 30 a second and acknowledgements with every update.
      if (++client.messages > 160) return ws.close(1008, "Too many commands");
      try {
        if (binary) throw new Error("Text commands required");
        const data = JSON.parse(bytes.toString());
        if (!data || typeof data !== "object")
          throw new Error("Invalid command");
        if (data.type === "ping")
          return send(ws, { type: "pong", at: data.at });
        if (data.type === "ack") {
          client.delivery?.acknowledged(data.tick, performance.now());
          return;
        }
        if (data.type === "rename") {
          const name = cleanName(data.name);
          if (!name) throw new Error("Enter a name with letters or numbers.");
          player.name = name;
          room.rosterVersion++;
          publishRoster(room);
          return;
        }
        if (data.type === "claim") {
          if (player.owner && player.owner !== client.id)
            return send(ws, {
              type: "error",
              message:
                "Your other device has control. Release it there first.",
            });
          player.owner = client.id;
          player.lastInput = now;
          halt(room, player);
          broadcast(room, player);
          return;
        }
        if (data.type === "estop") {
          vehicle.estop = player.truck.estop = true;
          halt(room, player);
          broadcast(room, player);
          return;
        }
        if (player.owner !== client.id)
          return send(ws, {
            type: "error",
            message: `Take control before operating the ${player.driving}.`,
          });
        if (data.type === "input") {
          // A page from before the truck sends no truck controls: they are at 0.
          if (
            !data.axes ||
            AXES.some((key) => {
              const value = data.axes[key] ?? (TRUCK_AXES.includes(key) ? 0 : null);
              return (
                typeof value !== "number" ||
                !Number.isFinite(value) ||
                Math.abs(value) > 1
              );
            })
          )
            throw new Error("Invalid control axes");
          if (
            typeof data.speed !== "number" ||
            !Number.isFinite(data.speed) ||
            data.speed < 0.2 ||
            data.speed > 1
          )
            throw new Error("Invalid speed");
          // The controls drive the machine the player is in; the other stays still.
          const inTruck = player.driving === "truck",
            truck = player.truck,
            keys = inTruck ? TRUCK_AXES : EXCAVATOR_AXES,
            machine = inTruck ? truck : vehicle;
          if (inTruck) {
            if (AXES.some((key) => vehicle.axes[key] !== 0))
              room.simulation.stop(vehicle);
          } else if (AXES.some((key) => truck.axes[key] !== 0))
            room.simulation.stopTruck(truck);
          if (vehicle.estop || keys.every((key) => !data.axes[key])) {
            if (AXES.some((key) => machine.axes[key] !== 0))
              if (inTruck) room.simulation.stopTruck(truck);
              else room.simulation.stop(vehicle);
          } else {
            machine.axes = Object.fromEntries(
              AXES.map((key) => [key, keys.includes(key) ? data.axes[key] : 0]),
            );
          }
          vehicle.speed = truck.speed = data.speed;
          player.lastInput = now;
        } else if (data.type === "release") {
          release(room, player);
          broadcast(room, player);
        } else if (data.type === "resume") {
          vehicle.estop = player.truck.estop = false;
          halt(room, player);
          broadcast(room, player);
        } else if (data.type === "drive") {
          // Into the other machine: both stop, and the controls change hands.
          if (!MACHINES.includes(data.machine))
            throw new Error("Choose the excavator or the truck.");
          halt(room, player);
          if (player.driving !== data.machine) {
            player.driving = data.machine;
            room.rosterVersion++;
            publishRoster(room);
          }
          player.lastInput = now;
          broadcast(room, player);
        } else if (data.type === "respawn") {
          // Whichever machine the player is in goes back to its place.
          if (player.driving === "truck") {
            player.bay = freeBay(room, player, player.seat);
            room.simulation.placeTruck(player.truck, parkedTruck(player.bay));
          } else {
            player.spawn = freeSpawn(room, player);
            room.simulation.place(vehicle, spawnMachine(player.spawn));
          }
          player.lastInput = now;
          broadcast(room, player);
        } else if (data.type === "reset") {
          if (room.host !== player.id)
            throw new Error("Only the host can reset the world.");
          room.simulation.reset();
          player.lastInput = now;
          for (const other of room.players.values()) {
            broadcast(room, other);
            if (other !== player)
              for (const socket of other.sockets)
                send(socket, {
                  type: "notice",
                  message: `${player.name} reset the world.`,
                });
          }
        } else throw new Error("Unknown command");
      } catch (error) {
        send(ws, { type: "error", message: error.message });
      }
    });
    ws.on("close", () => {
      room.clients.delete(ws);
      player.sockets.delete(ws);
      if (player.owner === client.id) release(room, player);
      if (!player.sockets.size) player.leftAt = Date.now();
      if (!room.clients.size) room.emptySince = Date.now();
      room.rosterVersion++;
      publishRoster(room);
      broadcast(room, player);
    });
  });
  const timer = setInterval(() => {
    const now = Date.now();
    for (const [code, room] of rooms) {
      for (const player of room.players.values()) {
        if (!player.sockets.size) {
          if (now - player.leftAt > graceMs) removePlayer(room, player);
          continue;
        }
        const v = player.vehicle,
          t = player.truck;
        if (now - player.lastInput > 350) {
          if (AXES.some((key) => v.axes[key] !== 0)) room.simulation.stop(v);
          if (AXES.some((key) => t.axes[key] !== 0)) room.simulation.stopTruck(t);
        }
        // A suspended phone must not keep the operator lease forever.
        if (player.owner && now - player.lastInput > 5000)
          release(room, player);
      }
      if (!room.clients.size) {
        if (now - room.emptySince > idleMs) {
          rooms.delete(code);
          void room.simulation.close();
        }
        continue;
      }
      room.simulation.step();
    }
  }, 1000 / 30);
  const heartbeat = setInterval(() => {
    const now = Date.now();
    for (const room of rooms.values())
      for (const [ws, client] of room.clients) {
        if (now - client.heardAt > silence[client.role]) ws.terminate();
        else ws.ping();
      }
  }, heartbeatMs);
  return {
    server,
    rooms,
    async close() {
      clearInterval(timer);
      clearInterval(heartbeat);
      for (const ws of wss.clients) ws.terminate();
      await Promise.all(
        [...rooms.values()].map((room) => room.simulation.close()),
      );
      await new Promise((resolve) => wss.close(resolve));
      await new Promise((resolve) => server.close(resolve));
    },
  };
}

if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  const app = createApplication();
  app.server.listen(Number(process.env.PORT) || 8080, "0.0.0.0", () =>
    console.log(
      `Sand / Lab listening on http://0.0.0.0:${app.server.address().port}`,
    ),
  );
  for (const signal of ["SIGTERM", "SIGINT"])
    process.once(signal, async () => {
      await app.close();
      process.exit(0);
    });
}

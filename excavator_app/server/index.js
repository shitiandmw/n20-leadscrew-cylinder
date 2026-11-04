import http from "node:http";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { randomBytes, randomUUID } from "node:crypto";
import { networkInterfaces } from "node:os";
import { gunzipSync } from "node:zlib";
import { WebSocketServer, WebSocket } from "ws";
import { SimulationRunner } from "./simulation-runner.js";
import { AXES } from "../shared/world.js";
import { encodeFrame, TILE_COUNT } from "../shared/protocol.js";

const ROOT = fileURLToPath(new URL("../dist/", import.meta.url));
const send = (ws, message) => {
  if (ws.readyState === WebSocket.OPEN && ws.bufferedAmount < 256_000)
    ws.send(JSON.stringify(message));
};
export function createApplication({
  maxRooms = Number(process.env.MAX_ROOMS) || 4,
  idleMs = 600_000,
} = {}) {
  const rooms = new Map();
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
      if (url.pathname === "/api/health")
        return json(res, 200, { ok: true, rooms: rooms.size });
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
          clients: room.clients.size,
          capacity: 8,
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
          owner: null,
          lastInput: 0,
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
      let body = await readFile(target);
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
      if (filename === "model.json") {
        res.setHeader("Vary", "Accept-Encoding");
        if (/\bgzip\b/.test(req.headers["accept-encoding"] || ""))
          res.setHeader("Content-Encoding", "gzip");
        else body = gunzipSync(body);
      }
      res.setHeader(
        "Cache-Control",
        filename.startsWith("assets/")
          ? "public, max-age=31536000, immutable"
          : "no-cache",
      );
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
        room = rooms.get(url.searchParams.get("room"));
      if (
        url.pathname !== "/ws" ||
        !room ||
        room.clients.size >= 8 ||
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
          url.searchParams.get("role") === "remote" ? "remote" : "simulator",
        ),
      );
    } catch {
      socket.destroy();
    }
  });
  function snapshot(room) {
    const s = room.simulation;
    return {
      type: "state",
      machine: s.machine,
      speed: s.speed,
      estop: s.estop,
      tick: s.tick,
      count: s.count,
      stats: s.stats,
      owner: room.owner,
      clients: [...room.clients.values()].map((c) => ({
        id: c.id,
        role: c.role,
      })),
      stepMs: Math.round(room.stepMs * 10) / 10,
    };
  }
  function broadcast(room) {
    const packet = JSON.stringify(snapshot(room));
    for (const ws of room.clients.keys())
      if (ws.readyState === WebSocket.OPEN && ws.bufferedAmount === 0)
        ws.send(packet);
  }
  function publishFrame(room) {
    room.stepMs = room.simulation.stepMs;
    broadcast(room);
    // Simulators get the machine pose, loose grains and changed sand-bed tiles
    // of the same tick. Each client tracks which tile versions it holds, so a
    // congested socket can skip frames and later catch up on every change.
    const s = room.simulation,
      frame = {
        tick: s.tick,
        machine: s.machine,
        grains: s.grains,
        origin: s.origin,
        tileData: s.tileData,
      };
    room.frame++;
    for (const [ws, client] of room.clients) {
      if (
        client.role !== "simulator" ||
        ws.readyState !== WebSocket.OPEN ||
        ws.bufferedAmount !== 0
      )
        continue;
      client.tiles ??= new Uint32Array(TILE_COUNT);
      const tiles = [];
      for (const t of s.tileData.keys())
        if (client.tiles[t] !== s.tileVersions[t]) tiles.push(t);
      ws.send(encodeFrame({ ...frame, tiles }));
      for (const t of tiles) client.tiles[t] = s.tileVersions[t];
    }
  }
  function release(room) {
    room.owner = null;
    room.simulation.stop();
  }
  wss.on("connection", (ws, req, room, role) => {
    const client = {
      id: randomUUID(),
      role,
      alive: true,
      window: Date.now(),
      messages: 0,
    };
    room.clients.set(ws, client);
    room.emptySince = null;
    send(ws, { type: "welcome", id: client.id, room: room.code });
    broadcast(room);
    ws.on("pong", () => {
      client.alive = true;
    });
    ws.on("error", () => ws.close());
    ws.on("message", (bytes, binary) => {
      const now = Date.now();
      if (now - client.window > 1000) {
        client.window = now;
        client.messages = 0;
      }
      if (++client.messages > 80) return ws.close(1008, "Too many commands");
      try {
        if (binary) throw new Error("Text commands required");
        const data = JSON.parse(bytes.toString());
        if (!data || typeof data !== "object")
          throw new Error("Invalid command");
        if (data.type === "ping")
          return send(ws, { type: "pong", at: data.at });
        if (data.type === "claim") {
          if (room.owner && room.owner !== client.id)
            return send(ws, {
              type: "error",
              message: "Another operator has control. Ask them to release it.",
            });
          room.owner = client.id;
          room.lastInput = now;
          room.simulation.stop();
          broadcast(room);
          return;
        }
        if (data.type === "estop") {
          room.simulation.estop = true;
          room.simulation.stop();
          broadcast(room);
          return;
        }
        if (room.owner !== client.id)
          return send(ws, {
            type: "error",
            message: "Take control before operating the excavator.",
          });
        if (data.type === "input") {
          if (
            !data.axes ||
            AXES.some(
              (key) =>
                typeof data.axes[key] !== "number" ||
                !Number.isFinite(data.axes[key]) ||
                Math.abs(data.axes[key]) > 1,
            )
          )
            throw new Error("Invalid control axes");
          if (
            typeof data.speed !== "number" ||
            !Number.isFinite(data.speed) ||
            data.speed < 0.2 ||
            data.speed > 1
          )
            throw new Error("Invalid speed");
          if (
            room.simulation.estop ||
            AXES.every((key) => data.axes[key] === 0)
          ) {
            if (AXES.some((key) => room.simulation.axes[key] !== 0))
              room.simulation.stop();
          } else {
            room.simulation.axes = Object.fromEntries(
              AXES.map((key) => [key, data.axes[key]]),
            );
          }
          room.simulation.speed = data.speed;
          room.lastInput = now;
        } else if (data.type === "release") {
          release(room);
          broadcast(room);
        } else if (data.type === "resume") {
          room.simulation.estop = false;
          room.simulation.stop();
          broadcast(room);
        } else if (data.type === "reset") {
          const stopped = room.simulation.estop;
          room.simulation.reset();
          room.simulation.estop = stopped;
          room.lastInput = now;
          broadcast(room);
        } else throw new Error("Unknown command");
      } catch (error) {
        send(ws, { type: "error", message: error.message });
      }
    });
    ws.on("close", () => {
      room.clients.delete(ws);
      if (room.owner === client.id) release(room);
      if (!room.clients.size) room.emptySince = Date.now();
      broadcast(room);
    });
  });
  const timer = setInterval(() => {
    const now = Date.now();
    for (const [code, room] of rooms) {
      if (!room.clients.size) {
        if (now - room.emptySince > idleMs) {
          rooms.delete(code);
          void room.simulation.close();
        }
        continue;
      }
      if (
        now - room.lastInput > 350 &&
        AXES.some((key) => room.simulation.axes[key] !== 0)
      )
        room.simulation.stop();
      // A suspended phone must not keep the operator lease forever.
      if (room.owner && now - room.lastInput > 5000) release(room);
      room.simulation.step();
    }
  }, 1000 / 30);
  const heartbeat = setInterval(() => {
    for (const room of rooms.values())
      for (const [ws, client] of room.clients) {
        if (!client.alive) ws.terminate();
        else {
          client.alive = false;
          ws.ping();
        }
      }
  }, 5000);
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

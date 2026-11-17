// How long a command from the phone takes to reach the computer's screen when
// the server is far away and the computer's connection is slow. A finite check:
// it starts a temporary server in this process and puts an emulated network
// link in front of a computer (a simulator page) and a phone (the remote). The
// phone drives the standard dig; for every command, the script measures how
// long until the computer receives the frame in which the excavator answers it,
// and how old each frame is when it arrives. The browser's playback delay (60 to
// 260 ms) and drawing come on top of these figures.
// Usage: node scripts/latency_test.mjs [computer kbit/s] [round trip ms] [seconds] [--no-acks]
// A rate of 0 leaves the computer's link unlimited. --no-acks connects as a page
// from before acknowledgements did (see server/delivery.js).
import net from "node:net";
import WebSocket from "ws";
import { createApplication } from "../server/index.js";
import { decodeFrame } from "../shared/protocol.js";
import { neutral } from "../shared/world.js";
import { SCOOP, CARRY, POUR, RETURN } from "../shared/scoop.js";

const args = process.argv.slice(2).filter((arg) => !arg.startsWith("--")),
  acks = !process.argv.includes("--no-acks"),
  kbits = Number(args[0] ?? 600),
  rtt = Number(args[1] ?? 170),
  seconds = Number(args[2] ?? 60),
  // What waits at the bottleneck before the server's side has to wait too: a
  // router's queue and the sending socket's buffer. The server's own socket
  // buffers come on top, as they do in front of a real line.
  queueBytes = 256 * 1024,
  wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
  now = () => performance.now();

// A link with a round trip of `rtt` ms whose downstream carries `bytesPerSecond`.
function emulatedLink(port, bytesPerSecond) {
  const counts = { offered: 0 };
  const server = net.createServer((near) => {
    const far = net.connect(port, "127.0.0.1");
    near.setNoDelay(true);
    far.setNoDelay(true);
    // Chunks leave in order, each at its own time.
    const scheduler = (socket) => {
      const pending = [];
      let timer = null;
      const fire = () => {
        timer = null;
        while (pending.length && pending[0].at <= now() + 0.5) {
          const { chunk } = pending.shift();
          if (!socket.destroyed) socket.write(chunk);
        }
        arm();
      };
      const arm = () => {
        if (timer === null && pending.length)
          timer = setTimeout(fire, Math.max(0, pending[0].at - now()));
      };
      return (chunk, at) => {
        pending.push({ chunk, at });
        arm();
      };
    };
    const toFar = scheduler(far),
      toNear = scheduler(near);
    near.on("data", (chunk) => toFar(chunk, now() + rtt / 2));
    let free = 0,
      queued = 0;
    far.on("data", (chunk) => {
      counts.offered += chunk.length;
      const t = now(),
        sent = Math.max(t, free) + (chunk.length / bytesPerSecond) * 1000;
      free = sent;
      queued += chunk.length;
      if (queued > queueBytes) far.pause();
      toNear(chunk, sent + rtt / 2);
      setTimeout(() => {
        queued -= chunk.length;
        if (queued <= queueBytes / 2) far.resume();
      }, sent - t);
    });
    near.on("close", () => far.destroy());
    far.on("close", () => near.destroy());
    near.on("error", () => {});
    far.on("error", () => {});
  });
  return new Promise((resolve) =>
    server.listen(0, "127.0.0.1", () =>
      resolve({ server, counts, port: server.address().port }),
    ),
  );
}

const app = createApplication();
await new Promise((resolve) => app.server.listen(0, "127.0.0.1", resolve));
const port = app.server.address().port,
  computerLink = await emulatedLink(port, kbits > 0 ? (kbits * 1000) / 8 : Infinity),
  phoneLink = await emulatedLink(port, Infinity),
  query = acks ? "&acks=1" : "";
try {
  const { room } = await (
    await fetch(`http://127.0.0.1:${port}/api/rooms`, { method: "POST" })
  ).json();
  const sim = app.rooms.get(room).simulation,
    producedAt = new Map();
  // The runner publishes each step to the sockets before this listener runs.
  sim.worker.on("message", () => producedAt.set(sim.tick, now()));

  // The computer: every frame's arrival, age and size, and the machine's pose.
  const computer = new WebSocket(
    `ws://127.0.0.1:${computerLink.port}/ws?room=${room}&role=simulator${query}`,
  );
  const frames = [],
    responses = [],
    pings = { computer: [], phone: [] };
  let key,
    watch = null,
    previous = null;
  computer.on("message", (data, binary) => {
    const at = now();
    if (!binary) {
      const message = JSON.parse(data);
      if (message.type === "welcome") key = message.player.key;
      if (message.type === "pong") pings.computer.push(at - message.at);
      return;
    }
    const frame = decodeFrame(data),
      machine = frame.machines[0];
    if (acks) computer.send(JSON.stringify({ type: "ack", tick: frame.tick }));
    frames.push({
      at,
      tick: frame.tick,
      bytes: data.length,
      age: producedAt.has(frame.tick) ? at - producedAt.get(frame.tick) : null,
    });
    // Has the joint of the latest command started to answer it?
    if (watch && previous && machine) {
      const moved =
        watch.joint === "slew"
          ? (machine.slew - previous.slew) * watch.sign
          : (machine.strokes[watch.joint] - previous.strokes[watch.joint]) *
            watch.sign;
      if (moved > 1e-4) {
        responses.push({ ...watch, ms: at - watch.sentAt });
        watch = null;
      }
    }
    if (machine) previous = machine;
  });
  await new Promise((resolve, reject) => {
    computer.once("open", resolve);
    computer.once("error", reject);
  });
  while (!key) await wait(20);
  // The first frame carries all the sand there is; start once it is through.
  const loading = now();
  while (!(frames.length && frames.at(-1).age < rtt / 2 + 100)) {
    if (now() - loading > 120_000) throw new Error("The first frame never got through");
    await wait(50);
  }
  console.log(`The first frame took ${((now() - loading) / 1000).toFixed(1)} s.`);

  // The phone, paired with the computer's player, takes control.
  const phone = new WebSocket(
    `ws://127.0.0.1:${phoneLink.port}/ws?room=${room}&role=remote&key=${encodeURIComponent(key)}${query}`,
  );
  let phoneId,
    owner = null;
  phone.on("message", (data) => {
    const message = JSON.parse(data);
    if (message.type === "welcome") {
      phoneId = message.id;
      phone.send(JSON.stringify({ type: "claim" }));
    }
    if (message.type === "state") {
      owner = message.owner;
      if (acks) phone.send(JSON.stringify({ type: "ack", tick: message.tick }));
    }
    if (message.type === "pong") pings.phone.push(now() - message.at);
  });
  await new Promise((resolve) => phone.once("open", resolve));
  while (!phoneId || owner !== phoneId) await wait(20);

  // The standard dig, round and round, crowding straight in after the first.
  const prelude = SCOOP.slice(0, 3),
    cycle = [...prelude, ...SCOOP.slice(3), ...CARRY, ...POUR, ...RETURN],
    joints = { boom: 0, stick: 1, bucket: 2, slew: "slew" };
  frames.length = 0;
  computerLink.counts.offered = 0;
  const start = now(),
    startTick = sim.tick,
    until = start + seconds * 1000;
  let phase = -1,
    phaseEnd = start,
    axes = neutral(),
    lastPing = 0;
  while (now() < until) {
    if (now() >= phaseEnd) {
      const before = axes;
      phase = phase + 1 < cycle.length ? phase + 1 : prelude.length;
      axes = { ...neutral(), ...cycle[phase][1] };
      phaseEnd = now() + cycle[phase][0] * 1000;
      // Watch a joint this command starts or reverses.
      const name = Object.keys(cycle[phase][1]).find(
        (axis) => Math.sign(axes[axis]) !== Math.sign(before[axis]),
      );
      phone.send(JSON.stringify({ type: "input", axes, speed: 1 }));
      if (watch) responses.push({ ...watch, ms: null });
      watch = name
        ? {
            command: name,
            joint: joints[name],
            sign: Math.sign(axes[name]),
            sentAt: now(),
          }
        : null;
    } else phone.send(JSON.stringify({ type: "input", axes, speed: 1 }));
    if (now() - lastPing > 2000) {
      lastPing = now();
      for (const ws of [computer, phone])
        ws.send(JSON.stringify({ type: "ping", at: lastPing }));
    }
    await wait(100);
  }
  const elapsed = (now() - start) / 1000,
    sorted = (values) => values.filter((v) => v !== null).sort((a, b) => a - b),
    at = (values, p) =>
      values[Math.min(values.length - 1, Math.floor(values.length * p))] ?? NaN,
    ms = (v) => (Number.isFinite(v) ? `${Math.round(v)} ms` : "-"),
    ages = sorted(frames.map((f) => f.age)),
    answered = sorted(responses.map((r) => r.ms)),
    received = frames.reduce((sum, f) => sum + f.bytes, 0);
  console.log(
    `Computer line ${kbits > 0 ? `${kbits} kbit/s` : "unlimited"}, round trip ${rtt} ms, ` +
      `${acks ? "acknowledging" : "not acknowledging"}, ${elapsed.toFixed(0)} s of digging ` +
      `(physics ${((sim.tick - startTick) / elapsed).toFixed(1)} ticks/s, 30 is real time):`,
  );
  console.log(
    `  sent to the computer ${(computerLink.counts.offered / elapsed / 1024).toFixed(1)} KB/s, ` +
      `of it frames ${(received / elapsed / 1024).toFixed(1)} KB/s, ${(frames.length / elapsed).toFixed(1)} frames/s`,
  );
  console.log(
    `  frame age on arrival: median ${ms(at(ages, 0.5))}, p95 ${ms(at(ages, 0.95))}, max ${ms(at(ages, 1))}`,
  );
  console.log(
    `  command to the first frame showing it: median ${ms(at(answered, 0.5))}, max ${ms(at(answered, 1))} ` +
      `(${answered.length} of ${responses.length} commands seen)`,
  );
  console.log(
    `  ping: phone ${ms(at(sorted(pings.phone), 0.5))}, computer ${ms(at(sorted(pings.computer), 0.5))} median, ${ms(at(sorted(pings.computer), 1))} max`,
  );
  // How the age of arriving frames develops, in 5 s windows.
  const windows = [];
  for (let t = 0; t + 2.5 < elapsed; t += 5) {
    const inWindow = sorted(
      frames
        .filter((f) => f.at - start >= t * 1000 && f.at - start < (t + 5) * 1000)
        .map((f) => f.age),
    );
    windows.push(inWindow.length ? Math.round(at(inWindow, 0.5)) : "-");
  }
  console.log(`  median frame age in each 5 s (ms): ${windows.join(" ")}`);
  console.log(
    `  each command (ms): ${responses.map((r) => `${r.command}${r.sign > 0 ? "+" : "-"} ${r.ms === null ? "-" : Math.round(r.ms)}`).join(", ")}`,
  );
  computer.close();
  phone.close();
} finally {
  await app.close();
  computerLink.server.close();
  phoneLink.server.close();
}

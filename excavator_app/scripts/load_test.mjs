// How a room behaves with many excavators digging at once. A finite check: it
// starts a temporary server in this process, connects N players and N browsers'
// worth of binary frames over real sockets, and prints what each would see.
// Usage: node scripts/load_test.mjs [players] [seconds]
import WebSocket from "ws";
import { createApplication } from "../server/index.js";
import { neutral } from "../shared/world.js";
import { SCOOP, CARRY, POUR, RETURN } from "../shared/scoop.js";

const players = Number(process.argv[2]) || 8,
  seconds = Number(process.argv[3]) || 20,
  wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const app = createApplication({ maxPlayers: players });
await new Promise((resolve) => app.server.listen(0, "127.0.0.1", resolve));
const origin = `http://127.0.0.1:${app.server.address().port}`;
try {
  const { room } = await (
    await fetch(`${origin}/api/rooms`, { method: "POST" })
  ).json();
  const bots = [];
  for (let n = 0; n < players; n++) {
    const ws = new WebSocket(
      `${origin.replace("http", "ws")}/ws?room=${room}&role=simulator`,
    );
    const bot = { ws, bytes: 0, frames: 0, pongs: [], state: null };
    ws.on("message", (data, binary) => {
      bot.bytes += data.length;
      if (binary) return bot.frames++;
      const message = JSON.parse(data);
      if (message.type === "state") bot.state = message;
      if (message.type === "pong")
        bot.pongs.push(performance.now() - message.at);
    });
    await new Promise((resolve) => ws.once("open", resolve));
    bots.push(bot);
  }
  // Everyone digs the standard scoop, lifts, swings, pours and comes back for
  // another, crowding straight in from then on.
  const prelude = SCOOP.slice(0, 3),
    cycle = [...prelude, ...SCOOP.slice(3), ...CARRY, ...POUR, ...RETURN];
  const send = (bot, body) => bot.ws.send(JSON.stringify(body));
  for (const bot of bots) send(bot, { type: "claim" });
  await wait(300);
  const sim = app.rooms.get(room).simulation,
    steps = [];
  let most = 0;
  for (const bot of bots) {
    bot.bytes = 0;
    bot.frames = 0;
  }
  const startTick = sim.tick,
    start = performance.now();
  const until = start + seconds * 1000;
  let phase = 0,
    phaseEnd = start + cycle[0][0] * 1000;
  while (performance.now() < until) {
    if (performance.now() > phaseEnd) {
      phase = phase + 1 < cycle.length ? phase + 1 : prelude.length;
      phaseEnd = performance.now() + cycle[phase][0] * 1000;
    }
    for (const bot of bots) {
      send(bot, {
        type: "input",
        axes: { ...neutral(), ...cycle[phase][1] },
        speed: 1,
      });
      send(bot, { type: "ping", at: performance.now() });
    }
    steps.push(sim.stepMs);
    most = Math.max(most, sim.count);
    await wait(100);
  }
  const elapsed = (performance.now() - start) / 1000,
    ticks = sim.tick - startTick,
    sorted = (values) => values.slice().sort((a, b) => a - b),
    stepsSorted = sorted(steps),
    pings = sorted(bots.flatMap((bot) => bot.pongs)),
    at = (values, p) => values[Math.floor(values.length * p)] ?? 0,
    bytes = bots.reduce((sum, bot) => sum + bot.bytes, 0) / bots.length,
    memory = process.memoryUsage().rss / 1048576;
  console.log(
    `${players} players digging for ${elapsed.toFixed(0)} s: ` +
      `${(ticks / elapsed).toFixed(1)} physics ticks/s (30 is real time), ` +
      `step ${at(stepsSorted, 0.5).toFixed(1)} ms median, ${at(stepsSorted, 0.99).toFixed(1)} ms p99; ` +
      `${most} falling parcels at most; ` +
      `ping ${at(pings, 0.5).toFixed(1)} ms median, ${at(pings, 0.99).toFixed(1)} ms p99; ` +
      `${(bytes / elapsed / 1024).toFixed(0)} KB/s to each browser, ${(bots[0].frames / elapsed).toFixed(1)} frames/s; ` +
      `${memory.toFixed(0)} MB resident.`,
  );
  console.log(
    "Loads (cm³):",
    bots.map((bot) => Math.round(bot.state.stats.load)).join(" "),
  );
  for (const bot of bots) bot.ws.close();
} finally {
  await app.close();
}

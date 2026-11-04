import { parentPort } from "node:worker_threads";
import { SandSimulation } from "./physics.js";
import { TILE_CELLS } from "../shared/protocol.js";

const simulation = new SandSimulation();
// The quantised bed persists across resets and every changed tile carries a
// version no client has seen, so a reset only resends what the player changed.
const store = new Map();
let resetVersion = 0,
  version = 0;
function publish(stepMs = 0, motionVersion = 0) {
  const origin = new Int32Array(3),
    grains = simulation.packGrains(origin),
    message = {
      machine: simulation.machine,
      tick: simulation.tick,
      count: simulation.grains,
      stats: simulation.stats,
      grains,
      origin,
      stepMs,
      resetVersion,
      motionVersion,
    },
    transfer = [grains.buffer, origin.buffer],
    changed = simulation.terrain.quantize(store);
  if (changed.length) {
    const tileIndex = Int32Array.from(changed),
      tileData = new Uint16Array(changed.length * TILE_CELLS);
    changed.forEach((tile, k) => tileData.set(store.get(tile), k * TILE_CELLS));
    message.tileIndex = tileIndex;
    message.tileData = tileData;
    message.tileVersion = ++version;
    transfer.push(tileIndex.buffer, tileData.buffer);
  }
  parentPort.postMessage(message, transfer);
}
publish();
parentPort.on("message", (command) => {
  if (command.resetVersion !== resetVersion) {
    simulation.reset();
    resetVersion = command.resetVersion;
  }
  simulation.axes = command.axes;
  simulation.speed = command.speed;
  simulation.estop = command.estop;
  // The server's last accepted pose wins after a stop invalidates a busy step.
  simulation.machine = command.machine;
  const start = performance.now();
  simulation.step();
  publish(performance.now() - start, command.motionVersion);
});

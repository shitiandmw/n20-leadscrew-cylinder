import { parentPort } from "node:worker_threads";
import { SandSimulation } from "./physics.js";
import { CELLS } from "./terrain.js";
import { TILE_COUNT } from "../shared/protocol.js";

const simulation = new SandSimulation();
// The quantised bed and its per-tile versions persist across resets, so every
// change (including a reset) carries a version no client has seen.
const terrain = new Uint16Array(CELLS),
  versions = new Uint32Array(TILE_COUNT);
let resetVersion = 0,
  version = 0;
function publish(stepMs = 0, motionVersion = 0) {
  const grains = simulation.packGrains(),
    message = {
      machine: simulation.machine,
      tick: simulation.tick,
      count: simulation.grains,
      stats: simulation.stats,
      grains,
      stepMs,
      resetVersion,
      motionVersion,
    },
    transfer = [grains.buffer];
  if (simulation.terrain.quantize(terrain, versions, ++version)) {
    message.terrain = terrain.slice();
    message.tileVersions = versions.slice();
    transfer.push(message.terrain.buffer, message.tileVersions.buffer);
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

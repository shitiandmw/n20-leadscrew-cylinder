import { parentPort } from "node:worker_threads";
import { SandSimulation } from "./physics.js";
import { TILE_CELLS } from "../shared/protocol.js";

// The machines follow the players in the room; each command lists them.
const simulation = new SandSimulation({ vehicles: [] });
// The quantised bed persists across resets and every changed tile carries a
// version no client has seen, so a reset only resends what the players changed.
const store = new Map();
let resetVersion = 0,
  version = 0;
function publish(stepMs = 0, commands = []) {
  const { grains, groups } = simulation.packGrains(),
    message = {
      vehicles: commands.map(({ id, motionVersion, poseVersion }) => {
        const v = simulation.vehicles.find((vehicle) => vehicle.id === id);
        return {
          id,
          motionVersion,
          poseVersion,
          machine: v.machine,
          stats: v.stats,
          load: v.load.pack(),
        };
      }),
      tick: simulation.tick,
      count: simulation.grains,
      world: simulation.world,
      grains,
      groups,
      stepMs,
      resetVersion,
    },
    transfer = [grains.buffer, groups.buffer],
    changed = simulation.terrain.quantize(store);
  for (const { load } of message.vehicles) if (load) transfer.push(load.buffer);
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
  simulation.syncVehicles(command.vehicles);
  const start = performance.now();
  simulation.step();
  publish(performance.now() - start, command.vehicles);
});

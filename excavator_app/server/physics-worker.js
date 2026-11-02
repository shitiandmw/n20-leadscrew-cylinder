import { parentPort } from "node:worker_threads";
import { SandSimulation } from "./physics.js";

const simulation = new SandSimulation();
let resetVersion = 0;
function publish(stepMs = 0, motionVersion = 0) {
  const positions = simulation.positions.slice();
  parentPort.postMessage(
    {
      machine: simulation.machine,
      tick: simulation.tick,
      count: simulation.count,
      stats: simulation.stats,
      positions,
      stepMs,
      resetVersion,
      motionVersion,
    },
    [positions.buffer],
  );
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

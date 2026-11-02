import { Worker } from "node:worker_threads";
import { initialMachine, neutral } from "../shared/world.js";

// One in-flight step per room: slow physics cannot block sockets or accumulate
// a backlog of old control commands. Ownership and watchdogs stay on the server.
export class SimulationRunner {
  constructor(onStep, onFailure) {
    this.resetVersion = 0;
    this.motionVersion = 0;
    this.worker = new Worker(new URL("./physics-worker.js", import.meta.url), {
      // A host launched from stdin (including the Docker smoke test) may use
      // --input-type, which Node does not permit for a worker loaded from a file.
      execArgv: process.execArgv.filter(
        (arg, index, args) =>
          arg !== "--input-type" &&
          !arg.startsWith("--input-type=") &&
          args[index - 1] !== "--input-type",
      ),
    });
    this.ready = new Promise((resolve, reject) => {
      this.rejectReady = reject;
      this.worker.on("message", ({ motionVersion, ...frame }) => {
        this.busy = false;
        if (!this.initialized) {
          this.initialPositions = frame.positions;
          this.reset();
          this.resetVersion = 0;
          this.initialized = true;
          Object.assign(this, frame);
          resolve();
          return;
        }
        // Neither a reset nor a stop may be overwritten by an older step.
        if (
          frame.resetVersion !== this.resetVersion ||
          motionVersion !== this.motionVersion
        )
          return;
        Object.assign(this, frame);
        onStep();
      });
      const fail = (error) => {
        if (this.closed || this.failed) return;
        this.failed = true;
        reject(error);
        onFailure(error);
      };
      this.worker.on("error", fail);
      this.worker.on("exit", (code) =>
        fail(new Error(`Physics worker exited (${code})`)),
      );
    });
  }

  reset() {
    this.resetVersion++;
    this.machine = initialMachine();
    this.axes = neutral();
    this.speed = 0.65;
    this.estop = false;
    this.tick = 0;
    this.stats = { carried: 0, deposited: 0, active: 0 };
    this.positions = this.initialPositions;
    this.count = this.positions.length / 3;
    this.stepMs = 0;
  }

  step() {
    if (!this.initialized || this.busy || this.failed || this.closed) return;
    this.busy = true;
    this.worker.postMessage({
      axes: this.axes,
      speed: this.speed,
      estop: this.estop,
      resetVersion: this.resetVersion,
      motionVersion: this.motionVersion,
      machine: this.machine,
    });
  }

  stop() {
    this.axes = neutral();
    this.motionVersion++;
  }

  async close() {
    this.closed = true;
    if (!this.initialized) this.rejectReady(new Error("Simulation closed"));
    await this.worker.terminate();
  }
}

import { Worker } from "node:worker_threads";
import { initialMachine, neutral } from "../shared/world.js";
import { TILE_CELLS, TILE_COUNT } from "../shared/protocol.js";

// One in-flight step per room: slow physics cannot block sockets or accumulate
// a backlog of old control commands. Ownership and watchdogs stay on the server.
export class SimulationRunner {
  constructor(onStep, onFailure) {
    this.resetVersion = 0;
    this.motionVersion = 0;
    // The latest quantised sand: tile index -> cells, each with a version.
    this.tileData = new Map();
    this.tileVersions = new Uint32Array(TILE_COUNT);
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
        // Sand updates are never discarded, not even from before a reset: the
        // worker only ever sends a tile again if it changes again.
        if (frame.tileIndex)
          frame.tileIndex.forEach((tile, k) => {
            this.tileData.set(
              tile,
              frame.tileData.subarray(k * TILE_CELLS, (k + 1) * TILE_CELLS),
            );
            this.tileVersions[tile] = frame.tileVersion;
          });
        if (!this.initialized) {
          this.reset();
          this.resetVersion = 0;
          this.initialized = true;
          this.origin = frame.origin;
          resolve();
          return;
        }
        // Frames computed before a reset are otherwise discarded entirely.
        if (frame.resetVersion !== this.resetVersion) return;
        // The sand always mirrors the worker, including a step that a stop
        // invalidated: only that step's machine motion is discarded.
        this.grains = frame.grains;
        this.origin = frame.origin;
        this.count = frame.count;
        this.stats = frame.stats;
        if (motionVersion !== this.motionVersion) return;
        this.machine = frame.machine;
        this.tick = frame.tick;
        this.stepMs = frame.stepMs;
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
    this.stats = {
      carried: 0,
      load: 0,
      deposited: 0,
      grains: 0,
      active: 0,
      blocked: false,
      obstacle: null,
    };
    this.grains = new Int16Array(0);
    this.count = 0;
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

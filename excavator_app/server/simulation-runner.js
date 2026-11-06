import { Worker } from "node:worker_threads";
import { neutral } from "../shared/world.js";
import { TILE_CELLS, TILE_COUNT } from "../shared/protocol.js";

const noStats = () => ({
  load: 0,
  blocked: false,
  obstacle: null,
});

// One in-flight step per room: slow physics cannot block sockets or accumulate
// a backlog of old control commands. A step asked for while another is running
// starts as soon as that one ends, so a step of 36 ms costs 36 ms, not the two
// whole timer periods it would otherwise wait for. Ownership and watchdogs stay
// on the server.
export class SimulationRunner {
  constructor(onStep, onFailure) {
    this.resetVersion = 0;
    this.vehicles = new Map();
    this.tick = 0;
    this.world = { deposited: 0, grains: 0 };
    this.grains = new Int16Array(0);
    this.groups = new Int32Array(0);
    this.count = 0;
    this.stepMs = 0;
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
      this.worker.on("message", ({ vehicles, ...frame }) => {
        this.busy = false;
        const overdue = this.overdue;
        this.overdue = false;
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
          this.initialized = true;
          resolve();
          return;
        }
        if (overdue) this.step();
        // Frames computed before a reset are otherwise discarded entirely.
        if (frame.resetVersion !== this.resetVersion) return;
        // The sand always mirrors the worker, including a step that a stop
        // invalidated: only that machine's motion in that step is discarded.
        this.grains = frame.grains;
        this.groups = frame.groups;
        this.count = frame.count;
        this.world = frame.world;
        this.tick = frame.tick;
        this.stepMs = frame.stepMs;
        for (const { id, machine, stats, load, motionVersion, poseVersion } of vehicles) {
          const v = this.vehicles.get(id);
          if (!v || poseVersion !== v.poseVersion) continue;
          v.stats = stats;
          v.load = load;
          if (motionVersion === v.motionVersion) v.machine = machine;
        }
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

  addVehicle(id, machine) {
    const vehicle = {
      id,
      home: machine,
      machine: structuredClone(machine),
      axes: neutral(),
      speed: 0.65,
      estop: false,
      motionVersion: 0,
      poseVersion: 0,
      stats: noStats(),
      load: null,
    };
    this.vehicles.set(id, vehicle);
    return vehicle;
  }

  removeVehicle(vehicle) {
    this.vehicles.delete(vehicle.id);
  }

  // Move a machine in one jump, and make that its home for a world reset.
  place(vehicle, machine) {
    vehicle.home = machine;
    vehicle.machine = structuredClone(machine);
    vehicle.axes = neutral();
    vehicle.poseVersion++;
    vehicle.stats = noStats();
    vehicle.load = null;
  }

  // Sand and machines go back to the start. A latched stop stays latched.
  reset() {
    this.resetVersion++;
    for (const vehicle of this.vehicles.values()) {
      this.place(vehicle, vehicle.home);
      vehicle.speed = 0.65;
    }
    this.tick = 0;
    this.world = { deposited: 0, grains: 0 };
    this.grains = new Int16Array(0);
    this.groups = new Int32Array(0);
    this.count = 0;
    this.stepMs = 0;
  }

  step() {
    if (!this.initialized || this.failed || this.closed) return;
    if (this.busy) {
      this.overdue = true;
      return;
    }
    this.busy = true;
    this.worker.postMessage({
      resetVersion: this.resetVersion,
      vehicles: [...this.vehicles.values()].map(
        ({ id, axes, speed, estop, machine, motionVersion, poseVersion }) => ({
          id,
          axes,
          speed,
          estop,
          machine,
          motionVersion,
          poseVersion,
        }),
      ),
    });
  }

  stop(vehicle) {
    vehicle.axes = neutral();
    vehicle.motionVersion++;
  }

  async close() {
    this.closed = true;
    if (!this.initialized) this.rejectReady(new Error("Simulation closed"));
    await this.worker.terminate();
  }
}

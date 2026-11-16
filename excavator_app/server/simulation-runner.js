import { Worker } from "node:worker_threads";
import { neutral } from "../shared/world.js";
import { TILE_CELLS, TILE_COUNT } from "../shared/protocol.js";

const noStats = () => ({
  load: 0,
  tilt: null,
  blocked: false,
  obstacle: null,
  drives: null,
});
const noTruckStats = () => ({
  load: 0,
  tip: 0,
  velocity: 0,
  steer: 0,
  gate: false,
  hauled: 0,
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
    this.trucks = new Map();
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
      // The worker needs no command-line flags of its own, and must not inherit
      // the host's: a host launched from stdin (the Docker smoke test) carries
      // --input-type, and Node's test runner hands its children every
      // process-wide option, neither of which a worker accepts.
      execArgv: [],
    });
    this.ready = new Promise((resolve, reject) => {
      this.rejectReady = reject;
      this.worker.on("message", ({ vehicles, trucks, ...frame }) => {
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
        for (const { id, pose, stats, load, motionVersion, poseVersion } of trucks) {
          const t = this.trucks.get(id);
          if (!t || poseVersion !== t.poseVersion) continue;
          t.stats = stats;
          t.load = load;
          if (motionVersion === t.motionVersion) t.pose = pose;
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

  // A player's dump truck, by the player's id.
  addTruck(id, pose) {
    const truck = {
      id,
      home: pose,
      pose: structuredClone(pose),
      axes: neutral(),
      speed: 0.65,
      estop: false,
      motionVersion: 0,
      poseVersion: 0,
      stats: noTruckStats(),
      load: null,
    };
    this.trucks.set(id, truck);
    return truck;
  }

  removeTruck(truck) {
    this.trucks.delete(truck.id);
  }

  // Move a truck in one jump, and make that its home for a world reset.
  placeTruck(truck, pose) {
    truck.home = pose;
    truck.pose = structuredClone(pose);
    truck.axes = neutral();
    truck.poseVersion++;
    truck.stats = noTruckStats();
    truck.load = null;
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
    for (const truck of this.trucks.values()) {
      this.placeTruck(truck, truck.home);
      truck.speed = 0.65;
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
      trucks: [...this.trucks.values()].map(
        ({ id, axes, speed, estop, pose, motionVersion, poseVersion }) => ({
          id,
          axes,
          speed,
          estop,
          pose,
          motionVersion,
          poseVersion,
        }),
      ),
    });
  }

  // Stops an excavator: its controls go neutral, and the motion of a step already
  // under way is not kept.
  stop(vehicle) {
    vehicle.axes = neutral();
    vehicle.motionVersion++;
  }

  // A truck's controls go neutral. It has way on, so it brakes to a stop in the
  // simulation rather than freezing where the server last saw it.
  stopTruck(truck) {
    truck.axes = neutral();
  }

  async close() {
    this.closed = true;
    if (!this.initialized) this.rejectReady(new Error("Simulation closed"));
    await this.worker.terminate();
  }
}

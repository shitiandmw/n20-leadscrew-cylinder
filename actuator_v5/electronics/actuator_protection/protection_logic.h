#pragma once
#include <stdint.h>

// Example thresholds for commissioning. Measure the actual motor before use.
enum class Fault : uint8_t { None, Overcurrent, Driver, Sensor, Timeout };
struct ProtectionConfig {
  uint16_t trip_mA = 550;
  uint32_t startup_blank_ms = 100;
  uint32_t current_trip_ms = 150;
  uint32_t reversal_dead_ms = 30;
  uint32_t maximum_run_ms = 30000;
};
struct Protection {
  ProtectionConfig cfg;
  Fault fault = Fault::None;
  int8_t direction = 0;
  uint32_t run_started = 0, stopped_at = 0, high_started = 0;
  bool high_pending = false, reset_was_down = false;
  void stop(uint32_t now) {
    if (direction) stopped_at = now;
    direction = 0; high_pending = false;
  }
  int8_t update(uint32_t now, int8_t request, uint16_t current_mA,
                bool driver_ok, bool sensor_ok, bool reset_down) {
    const bool reset_edge = reset_down && !reset_was_down;
    reset_was_down = reset_down;
    if (!sensor_ok) fault = Fault::Sensor;
    else if (!driver_ok) fault = Fault::Driver;
    if (fault != Fault::None) {
      stop(now);
      // No automatic restart, and no reset while a direction is held.
      if (reset_edge && request == 0 && sensor_ok && driver_ok) {
        fault = Fault::None; stopped_at = now;
      }
      return 0;
    }
    if (!request) { stop(now); return 0; }
    if (direction && direction != request) { stop(now); return 0; }
    if (!direction) {
      if (uint32_t(now-stopped_at) < cfg.reversal_dead_ms) return 0;
      direction = request; run_started = now; high_pending = false;
    }
    if (uint32_t(now-run_started) >= cfg.maximum_run_ms) {
      fault = Fault::Timeout; stop(now); return 0;
    }
    if (uint32_t(now-run_started) < cfg.startup_blank_ms) return direction;
    if (current_mA >= cfg.trip_mA) {
      if (!high_pending) { high_pending = true; high_started = now; }
      else if (uint32_t(now-high_started) >= cfg.current_trip_ms) {
        fault = Fault::Overcurrent; stop(now); return 0;
      }
    } else high_pending = false;
    return direction;
  }
};

// X1 machine control logic: see control_logic.h.
#include "control_logic.h"

#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

namespace x1 {

namespace {

constexpr uint16_t TRACK_BUTTONS =
    x1link::BTN_LEFT_FWD | x1link::BTN_LEFT_REV | x1link::BTN_RIGHT_FWD | x1link::BTN_RIGHT_REV;

float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }
float axis(int16_t v) { return clampf(float(v) / float(x1link::AXIS_FULL), -1.f, 1.f); }
float neg(float v) { return v == 0.f ? 0.f : -v; }  // no -0 in the printouts
bool is_boom(int ch) { return ch == BOOM_L || ch == BOOM_R; }
float pressed(uint16_t buttons, uint16_t bit) { return (buttons & bit) ? 1.f : 0.f; }

int hexval(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return -1;
}

void appendf(char *buf, size_t n, size_t &k, const char *fmt, ...) {
  if (k + 1 >= n) return;
  va_list ap;
  va_start(ap, fmt);
  const int w = vsnprintf(buf + k, n - k, fmt, ap);
  va_end(ap);
  if (w > 0) k = (k + size_t(w) < n) ? k + size_t(w) : n - 1;
}

}  // namespace

float dead_band(float v, float band) { return fabsf(v) < band ? 0.f : v; }

Axes map_inputs(const x1link::Control &c, float band) {
  using namespace x1link;
  Axes a;
  // Left pad: x is slew (R = +1); its top is STICK OUT, which the app sends as stick -1.
  a.slew = dead_band(axis(c.lx), band);
  a.stick = neg(dead_band(axis(c.ly), band));
  // Right pad: the app sends bucket = -x (CURL on the left = +1); its top is LOWER = boom -1.
  a.bucket = neg(dead_band(axis(c.rx), band));
  a.boom = neg(dead_band(axis(c.ry), band));
  // Hold-to-travel buttons sum as in the app, so both buttons of a pair give 0: that track stops.
  a.left_track = pressed(c.buttons, BTN_LEFT_FWD) - pressed(c.buttons, BTN_LEFT_REV);
  a.right_track = pressed(c.buttons, BTN_RIGHT_FWD) - pressed(c.buttons, BTN_RIGHT_REV);
  return a;
}

bool inputs_centred(const x1link::Control &c, float band) {
  const Axes a = map_inputs(c, band);
  return a.boom == 0.f && a.stick == 0.f && a.bucket == 0.f && a.slew == 0.f &&
         !(c.buttons & (TRACK_BUTTONS | x1link::BTN_RESYNC));
}

float ramp_toward(float v, float target, uint32_t dt_ms, uint16_t full_scale_ms) {
  if (full_scale_ms == 0) return target;
  // The small allowance stops float rounding from adding a tick to the end of a ramp.
  const float step = float(dt_ms) / float(full_scale_ms), reach = step + 1e-5f;
  if (target > v) return (target - v <= reach) ? target : v + step;
  return (v - target <= reach) ? target : v - step;
}

// ---------------------------------------------------------------------------------------------
// Radio

x1link::Check Controller::on_packet(const uint8_t *data, size_t len, uint32_t now) {
  using namespace x1link;
  Control c;
  const Check r = validate(data, len, c);
  if (r != Check::OK) {
    ++rx_bad_;
    return r;
  }
  const bool live = link_ && uint32_t(now - last_rx_ms_) < cfg_.link_timeout_ms;
  if (live) {
    // Only newer packets; after a link loss any sequence is taken (the handle may have restarted).
    const int16_t step = int16_t(uint16_t(c.seq - pkt_.seq));
    if (step <= 0) {
      ++rx_old_;
      return Check::SEQUENCE;
    }
    lost_ += uint32_t(step - 1);
  }
  // Button edges count only between consecutive packets of one link, so a button held through a
  // link loss or at power-up is not a press.
  const uint16_t before = live ? pkt_.buttons : uint16_t(0xFFFF);
  pkt_ = c;
  last_rx_ms_ = now;
  link_ = true;
  if (rx_count_ < 0xFFFF) ++rx_count_;
  if (c.buttons & BTN_ESTOP) estop_ = true;  // S2: latched
  const uint16_t edges = uint16_t(c.buttons & ~before);
  if (edges & BTN_RESUME) resume();
  if (edges & BTN_RESYNC) resync_edge_ = true;
  return Check::OK;
}

void Controller::resume() {
  // S2: RESUME clears the stop only with every input centred, as the app's "Resume operation".
  if ((pkt_.buttons & x1link::BTN_ESTOP) || !inputs_centred(pkt_, cfg_.dead_band)) return;
  estop_ = false;
  boom_fault_ = false;
  resync_failed_ = false;
  boom_.reset();
  if (!nfault_now_) driver_fault_ = false;
}

// ---------------------------------------------------------------------------------------------
// Control step

void Controller::update(uint32_t now, const Sense &s) {
  const bool first = !started_;
  uint32_t dt = first ? 0 : uint32_t(now - last_ms_);
  if (dt > 100) dt = 100;  // a stalled loop must not jump the ramps or the filters
  last_ms_ = now;
  if (first) rx_window_ms_ = now;
  started_ = true;

  // S5: battery on a 2 s filter, so load sag does not trip it.
  const float vbat = float(s.vbat_adc_mV) / x1pins::VBAT_DIVIDER / 1000.f;
  vbat_f_ = first ? vbat : vbat_f_ + (vbat - vbat_f_) * float(dt) / (cfg_.vbat_tau_ms + float(dt));
  if (vbat_f_ < cfg_.vbat_warn_v) batt_warn_ = true;
  else if (vbat_f_ >= cfg_.vbat_warn_clear_v) batt_warn_ = false;
  if (vbat_f_ < cfg_.vbat_stop_v) batt_stop_ = true;
  else if (vbat_f_ >= cfg_.vbat_stop_clear_v) batt_stop_ = false;
  v6_ = float(s.v6_adc_mV) / x1pins::V6_DIVIDER / 1000.f;

  // Currents: IPROPI V = I x 1000 uA/A x R, so I[mA] = 1000 x mV / R.
  for (int ch = 0; ch < NUM_CH; ++ch) {
    float mv = float(s.isns_mV[ch]) - offset_mV_[ch];
    if (mv < 0) mv = 0;
    const float ma = 1000.f * mv / CHANNEL[ch].r_ipropi_ohm;
    cur_mA_[ch] = first ? ma : cur_mA_[ch] + (ma - cur_mA_[ch]) * float(dt) / (cfg_.current_tau_ms + float(dt));
  }

  // S6: the shared nFAULT line, debounced, ignored for a moment after the drivers wake.
  nfault_now_ = s.nfault_low;
  const bool waking = awake_ && uint32_t(now - wake_ms_) < cfg_.nfault_wake_blank_ms;
  if (s.nfault_low && !waking) {
    if (!nfault_pending_) {
      nfault_pending_ = true;
      nfault_since_ = now;
    }
    if (uint32_t(now - nfault_since_) >= cfg_.nfault_debounce_ms) driver_fault_ = true;
  } else {
    nfault_pending_ = false;
  }

  // S1: link watchdog. Once lost, only a new packet brings it back (so a timer wrap cannot).
  if (link_ && uint32_t(now - last_rx_ms_) >= cfg_.link_timeout_ms) link_ = false;
  if (uint32_t(now - rx_window_ms_) >= 1000) {
    rx_per_s_ = uint8_t(rx_count_ > 255 ? 255 : rx_count_);
    rx_count_ = 0;
    rx_window_ms_ = now;
  }

  // Stops that hold every channel (S2, S5, S6, pairing), then arming (S3).
  const bool hard_stop = estop_ || batt_stop_ || driver_fault_ || pairing_;
  if (bench_ && (link_ || hard_stop || uint32_t(now - bench_since_) >= bench_ms_)) bench_ = false;
  if (!link_ || hard_stop) armed_ = false;
  else if (!armed_ && inputs_centred(pkt_, cfg_.dead_band)) armed_ = true;
  if (!armed_) {
    resync_ = false;
    resync_edge_ = false;
  }

  // Requests (the inputs before the speed scaling) and the speed.
  float req[NUM_CH] = {};
  float speed = 0, boom_cmd = 0;
  if (armed_) {
    const Axes a = map_inputs(pkt_, cfg_.dead_band);
    speed = float(pkt_.speed_pct) / 100.f;
    req[TRACK_L] = a.left_track;
    req[TRACK_R] = a.right_track;
    req[SWING] = a.slew;
    req[BOOM_L] = req[BOOM_R] = a.boom;
    req[STICK] = a.stick;
    req[BUCKET] = a.bucket;
    // Boom re-sync button: drive both sides to the retract end stops (boom down). A second press
    // or any boom input cancels it. It also clears a boom fault, since re-syncing is the remedy.
    if (resync_edge_) {
      resync_edge_ = false;
      if (resync_) {
        resync_ = false;
      } else if (a.boom == 0.f) {
        resync_ = true;
        resync_since_ = now;
        resync_failed_ = false;
        boom_fault_ = false;
        boom_.reset();
      }
    }
    if (resync_ && a.boom != 0.f) resync_ = false;
    if (resync_ && uint32_t(now - resync_since_) >= cfg_.resync_timeout_ms) {
      resync_ = false;
      resync_failed_ = true;
    }
    boom_cmd = resync_ ? -speed : a.boom * speed;
  } else if (bench_) {
    speed = 1;
    if (is_boom(bench_ch_)) {
      req[BOOM_L] = req[BOOM_R] = bench_duty_;
      boom_cmd = bench_duty_;
    } else {
      req[bench_ch_] = bench_duty_;
    }
  }

  float target[NUM_CH];
  for (int ch = 0; ch < NUM_CH; ++ch) target[ch] = req[ch] * speed;
  float boom_out[2];
  boom_update(now, dt, boom_cmd, boom_out);
  target[BOOM_L] = boom_out[0];
  target[BOOM_R] = boom_out[1];

  // Per channel: ramps (SPEC 2), the stop behaviour of S1/S2 and the S4 stall cut-out.
  const bool driving = armed_ || bench_;
  for (int ch = 0; ch < NUM_CH; ++ch) {
    if (stall_cut_[ch] && req[ch] == 0.f) stall_cut_[ch] = false;
    float &d = duty_[ch];
    if (!driving) {
      // The swing ramps down to protect its pinion; every other channel stops at once.
      d = (ch == SWING) ? ramp_toward(d, 0.f, dt, CHANNEL[ch].ramp_ms) : 0.f;
      stall_pending_[ch] = false;
      continue;
    }
    if (stall_cut_[ch] || (boom_fault_ && is_boom(ch))) {
      d = 0;
      stall_pending_[ch] = false;
      continue;
    }
    d = ramp_toward(d, target[ch], dt, CHANNEL[ch].ramp_ms);
    // S4: the current a stalled motor would draw at this duty (the driver caps it at its limit); the IPROPI reading
    // follows the motor current at any duty (low-side sensing in both drive and brake phases, DRV8876 7.3.3.1)
    const float i_stall = fminf(CHANNEL[ch].limit_a, fabsf(d) * vbat_f_ / cfg_.motor_ohm);
    if (CHANNEL[ch].vbat && d != 0.f && i_stall >= cfg_.stall_min_a && cur_mA_[ch] >= cfg_.stall_fraction * i_stall * 1000.f) {
      if (!stall_pending_[ch]) {
        stall_pending_[ch] = true;
        stall_since_[ch] = now;
      } else if (uint32_t(now - stall_since_[ch]) >= cfg_.stall_ms) {
        stall_cut_[ch] = true;  // off until its input returns to centre
        stall_pending_[ch] = false;
        d = 0;
      }
    } else {
      stall_pending_[ch] = false;
    }
  }
  if (bench_ && stall_cut_[bench_ch_]) bench_ = false;

  // Drivers awake while armed, on the bench, or while anything still runs (the swing ramp).
  bool moving = false;
  for (int ch = 0; ch < NUM_CH; ++ch) moving = moving || duty_[ch] != 0.f;
  const bool awake = driving || moving;
  if (awake && !awake_) wake_ms_ = now;
  awake_ = awake;

  out_.nsleep = awake;
  for (int ch = 0; ch < NUM_CH; ++ch) {
    if (duty_[ch] != 0.f) ph_[ch] = ((duty_[ch] > 0.f) != CHANNEL[ch].invert) != bool((flip_ >> ch) & 1u);
    out_.ph[ch] = ph_[ch];
    out_.en[ch] = fabsf(duty_[ch]);
  }
  if (link_) {  // the lamps keep their last state through a link loss
    out_.lamp[0] = pkt_.buttons & x1link::BTN_LAMP1;
    out_.lamp[1] = pkt_.buttons & x1link::BTN_LAMP2;
  }
  out_.buzzer = buzzer_on(now);
  out_.led = led_on(now);
}

void Controller::boom_update(uint32_t now, uint32_t dt, float cmd, float out[2]) {
  Boom &b = boom_;
  out[0] = out[1] = 0;
  if (boom_fault_ || cmd == 0.f) {
    b.running = b.imb_pending = b.end_mode = false;
    return;
  }
  const int8_t dir = cmd > 0 ? 1 : -1;
  if (dir != b.dir) {  // a reversal: new trims, and a new start (inrush blank)
    b.dir = dir;
    b.trim[0] = b.trim[1] = 0;
    b.running = false;
  }
  if (!b.running) {
    b.running = true;
    b.since = now;
    b.imb_pending = b.end_mode = false;
    b.end[0] = b.end[1] = false;
  }
  const float iL = cur_mA_[BOOM_L], iR = cur_mA_[BOOM_R];
  const bool judged = uint32_t(now - b.since) >= cfg_.boom_blank_ms && fabsf(duty_[BOOM_L]) >= cfg_.boom_min_duty &&
                      fabsf(duty_[BOOM_R]) >= cfg_.boom_min_duty;
  if (!judged) {
    b.imb_pending = false;
  } else {
    b.end[0] = iL < cfg_.boom_zero_mA;
    b.end[1] = iR < cfg_.boom_zero_mA;
    if (b.end[0] && b.end[1]) {
      // Both end stops open: the sides are level again.
      b.trim[0] = b.trim[1] = 0;
      b.end_mode = b.imb_pending = false;
      resync_ = false;  // a re-sync is complete
    } else if (b.end[0] || b.end[1]) {
      // One end stop has opened: keep driving the other side, untrimmed, until it stops too.
      b.trim[0] = b.trim[1] = 0;
      b.imb_pending = false;
      if (!b.end_mode) {
        b.end_mode = true;
        b.end_since = now;
      } else if (!resync_ && uint32_t(now - b.end_since) >= cfg_.boom_end_timeout_ms) {
        boom_fault_ = true;
      }
    } else {
      // Load balancing: the side drawing more current is ahead; trim it down, slowly.
      b.end_mode = false;
      const float diff = iL - iR;
      const float step = cfg_.boom_trim_rate * float(dt) / 1000.f;
      for (int lead = 0; lead < 2; ++lead) {
        const float ahead = lead == 0 ? diff : -diff;
        if (ahead <= cfg_.boom_balance_tol_mA) continue;
        float &other = b.trim[1 - lead];
        if (other > 0) other = other > step ? other - step : 0.f;
        else b.trim[lead] = b.trim[lead] + step < cfg_.boom_trim_max ? b.trim[lead] + step : cfg_.boom_trim_max;
      }
      if (!resync_ && fabsf(diff) > cfg_.boom_imbalance_mA) {
        if (!b.imb_pending) {
          b.imb_pending = true;
          b.imb_since = now;
        } else if (uint32_t(now - b.imb_since) >= cfg_.boom_imbalance_ms) {
          boom_fault_ = true;  // the boom stops; the handle reports it
        }
      } else {
        b.imb_pending = false;
      }
    }
  }
  if (boom_fault_) {
    b.running = b.imb_pending = b.end_mode = false;
    return;
  }
  out[0] = cmd * (1.f - b.trim[0]);
  out[1] = cmd * (1.f - b.trim[1]);
}

// ---------------------------------------------------------------------------------------------
// Buzzer and LED

bool Controller::buzzer_on(uint32_t now) const {
  using namespace x1link;
  if (link_ && (pkt_.buttons & BTN_HORN)) return true;
  if (duty_[TRACK_L] != 0.f || duty_[TRACK_R] != 0.f) return now % 800 < 400;  // travel alarm
  if (faults() & (F_DRIVER | F_BOOM | F_RESYNC_TIMEOUT | F_STALL | F_BATTERY_LOW)) return now % 1000 < 100;
  if (batt_warn_) return now % 5000 < 100;
  return false;
}

bool Controller::led_on(uint32_t now) const {
  using namespace x1link;
  if (pairing_) return now % 200 < 100;  // fast blink
  if (estop_ || (faults() & (F_DRIVER | F_BOOM | F_RESYNC_TIMEOUT | F_STALL | F_BATTERY_LOW))) {
    const uint32_t p = now % 1000;  // double flash
    return p < 100 || (p >= 200 && p < 300);
  }
  if (armed_ || bench_) return true;
  if (link_) return now % 1000 < 500;  // linked, waiting for centred inputs
  return now % 2000 < 100;             // no handle
}

// ---------------------------------------------------------------------------------------------
// Telemetry, console, state

uint8_t Controller::state_bits() const {
  using namespace x1link;
  return uint8_t((armed_ ? ST_ARMED : 0) | (link_ ? ST_LINK : 0) | (estop_ ? ST_ESTOP : 0) |
                 (pairing_ ? ST_PAIRING : 0) | (resync_ ? ST_RESYNC : 0) | (bench_ ? ST_BENCH : 0));
}

uint16_t Controller::faults() const {
  using namespace x1link;
  uint16_t f = 0;
  if (driver_fault_) f |= F_DRIVER;
  if (nfault_now_) f |= F_DRIVER_LINE;
  if (boom_fault_) f |= F_BOOM;
  if (resync_failed_) f |= F_RESYNC_TIMEOUT;
  for (int ch = 0; ch < NUM_CH; ++ch)
    if (stall_cut_[ch]) f |= F_STALL;
  if (batt_stop_) f |= F_BATTERY_LOW;
  if (batt_warn_) f |= F_BATTERY_WARN;
  if (vbat_f_ >= 7.5f && v6_ < cfg_.v6_low_v) f |= F_RAIL_6V_LOW;
  return f;
}

void Controller::make_telemetry(x1link::Telemetry &t, int8_t rssi_dBm) {
  using namespace x1link;
  memset(&t, 0, sizeof t);
  t.state = state_bits();
  t.seq = tlm_seq_++;
  t.ack_seq = pkt_.seq;
  t.faults = faults();
  t.vbat_mV = uint16_t(clampf(vbat_f_ * 1000.f + 0.5f, 0.f, 65535.f));
  t.v6_mV = uint16_t(clampf(v6_ * 1000.f + 0.5f, 0.f, 65535.f));
  t.rssi_dBm = rssi_dBm;
  t.rx_per_s = rx_per_s_;
  for (int ch = 0; ch < NUM_CH; ++ch) {
    ChannelReport &r = t.ch[ch];
    r.duty_pct = int8_t(lroundf(clampf(duty_[ch], -1.f, 1.f) * 100.f));
    r.flags = uint8_t((stall_cut_[ch] ? CH_STALL_CUT : 0) | (boom_fault_ && is_boom(ch) ? CH_BOOM_CUT : 0) |
                      (ph_[ch] ? CH_PH : 0) | (ch == BOOM_L && boom_.end[0] ? CH_AT_END : 0) |
                      (ch == BOOM_R && boom_.end[1] ? CH_AT_END : 0));
    r.current_mA = uint16_t(clampf(cur_mA_[ch] + 0.5f, 0.f, 65535.f));
  }
  encode(t);
}

const char *Controller::bench_drive(Ch ch, float duty, uint32_t ms, uint32_t now) {
  if (ch >= NUM_CH) return "no such channel";
  if (link_) return "a handle is connected";
  if (estop_) return "E-stop latched (RESUME on the handle clears it)";
  if (driver_fault_) return "driver fault latched (S6)";
  if (batt_stop_) return "battery low (S5)";
  if (pairing_) return "pairing";
  if (is_boom(ch) && boom_fault_) return "boom fault latched";
  bench_ = true;
  bench_ch_ = ch;
  bench_duty_ = clampf(duty, -1.f, 1.f);
  bench_since_ = now;
  bench_ms_ = ms == 0 ? 1 : (ms > cfg_.bench_max_ms ? cfg_.bench_max_ms : ms);
  return nullptr;
}

bool Controller::clear_faults() {
  if (link_) return false;
  boom_fault_ = false;
  resync_failed_ = false;
  boom_.reset();
  if (!nfault_now_) driver_fault_ = false;
  return true;
}

void Controller::set_current_offset(Ch ch, float mV) {
  if (ch < NUM_CH) offset_mV_[ch] = clampf(mV, 0.f, 300.f);
}

size_t Controller::describe(char *buf, size_t n) const {
  using namespace x1link;
  size_t k = 0;
  if (!buf || n == 0) return 0;
  buf[0] = 0;
  appendf(buf, n, k, "state: %s, link %s%s%s%s%s\n", armed_ ? "ARMED" : "disarmed", link_ ? "up" : "down",
          estop_ ? ", E-STOP latched" : "", pairing_ ? ", pairing" : "", resync_ ? ", boom re-sync" : "",
          bench_ ? ", bench drive" : "");
  appendf(buf, n, k, "battery: %.2f V (2 s filtered)%s%s; 6 V rail %.2f V\n", double(vbat_f_),
          batt_stop_ ? " LOW: motors stopped" : "", batt_warn_ && !batt_stop_ ? " low: warning" : "", double(v6_));
  const uint16_t f = faults();
  appendf(buf, n, k, "faults: 0x%04x", unsigned(f));
  static const char *const names[] = {"driver(latched)", "nFAULT-low", "boom", "resync-timeout",
                                      "stall",           "battery-low", "battery-warn", "6V-rail-low"};
  for (int i = 0; i < 8; ++i)
    if (f & (1u << i)) appendf(buf, n, k, " %s", names[i]);
  appendf(buf, n, k, "\n");
  appendf(buf, n, k, "handle: lx %d ly %d rx %d ry %d, speed %u %%, buttons 0x%03x, seq %u\n", pkt_.lx, pkt_.ly,
          pkt_.rx, pkt_.ry, unsigned(pkt_.speed_pct), unsigned(pkt_.buttons), unsigned(pkt_.seq));
  appendf(buf, n, k, "radio: %u packets/s, %lu lost, %lu bad, %lu stale\n", unsigned(rx_per_s_),
          (unsigned long)lost_, (unsigned long)rx_bad_, (unsigned long)rx_old_);
  appendf(buf, n, k, "boom: trim L %.1f %% R %.1f %%, end stop L %s R %s\n", double(boom_.trim[0] * 100.f),
          double(boom_.trim[1] * 100.f), boom_.end[0] ? "open" : "-", boom_.end[1] ? "open" : "-");
  appendf(buf, n, k, "ch name          duty   PH  I mA    offset mV  flags\n");
  for (int ch = 0; ch < NUM_CH; ++ch) {
    appendf(buf, n, k, "%d  %-12s %+6.3f  %d  %6.1f  %6.1f    %s%s%s\n", ch + 1, CHANNEL[ch].name, double(duty_[ch]),
            int(ph_[ch]), double(cur_mA_[ch]), double(offset_mV_[ch]), stall_cut_[ch] ? "stall-cut " : "",
            (flip_ >> ch) & 1u ? "flipped " : "", CHANNEL[ch].invert ? "mirrored" : "");
  }
  return k;
}

bool parse_hex(const char *s, uint8_t *out, size_t n) {
  if (!s || strlen(s) != 2 * n) return false;
  for (size_t i = 0; i < n; ++i) {
    const int hi = hexval(s[2 * i]), lo = hexval(s[2 * i + 1]);
    if (hi < 0 || lo < 0) return false;
    out[i] = uint8_t(hi * 16 + lo);
  }
  return true;
}

bool parse_mac(const char *s, uint8_t mac[6]) {
  if (!s || strlen(s) != 17) return false;
  uint8_t m[6];
  for (int i = 0; i < 6; ++i) {
    const char *p = s + 3 * i;
    const int hi = hexval(p[0]), lo = hexval(p[1]);
    if (hi < 0 || lo < 0) return false;
    if (i < 5 && p[2] != ':' && p[2] != '-') return false;
    m[i] = uint8_t(hi * 16 + lo);
  }
  memcpy(mac, m, 6);
  return true;
}

}  // namespace x1

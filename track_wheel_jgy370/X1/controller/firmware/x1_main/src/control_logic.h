// X1 machine control logic (SPEC C1 sections 2, 4 and 5). Plain C++17 with no Arduino headers: the
// sketch feeds it the ADC readings, the nFAULT level, the radio packets and millis(), and copies
// its outputs to the pins. Every time is a uint32_t millisecond count; intervals are taken as
// uint32_t(now - then), so the 49.7-day millis() wrap does no harm.
//
// Sign convention: a channel's positive duty is the app's positive axis (see Axes). The PH pin is
// that sign, inverted for the mirrored right track (SPEC 2) and for any channel flipped on the
// console. Which way "OUT1 high" turns each motor is a wiring fact checked at bring-up.
#pragma once
#include <stddef.h>
#include <stdint.h>

#include "x1_link.h"
#include "x1_main_pins.h"

namespace x1 {

// Channel order is x1pins::CHANNELS order; the static_asserts below hold the two together.
enum Ch : uint8_t { TRACK_L, TRACK_R, SWING, BOOM_L, BOOM_R, STICK, BUCKET, NUM_CH };

struct ChannelSpec {
  const char *name;
  int en, ph, isns;    // GPIO
  float r_ipropi_ohm;  // IPROPI resistor
  float limit_a;       // the driver's current limit (ITRIP) from the board
  uint16_t ramp_ms;    // time for a full-scale change of duty (SPEC 2)
  bool invert;         // PH inverted: the right track is mounted mirrored
  bool vbat;           // 12 V channel: the S4 stall cut-out applies
};

namespace detail {
constexpr ChannelSpec make(int i, uint16_t ramp_ms, bool invert, bool vbat) {
  return ChannelSpec{x1pins::CHANNELS[i].name, x1pins::CHANNELS[i].en, x1pins::CHANNELS[i].ph,
                     x1pins::CHANNELS[i].isns, x1pins::CHANNELS[i].r_ipropi_ohm, x1pins::CHANNELS[i].limit_a,
                     ramp_ms, invert, vbat};
}
constexpr bool pins_are(int i, int en, int ph, int isns) {
  return x1pins::CHANNELS[i].en == en && x1pins::CHANNELS[i].ph == ph && x1pins::CHANNELS[i].isns == isns;
}
}  // namespace detail

static_assert(sizeof(x1pins::CHANNELS) / sizeof(x1pins::CHANNELS[0]) == NUM_CH, "seven channels");
static_assert(detail::pins_are(TRACK_L, x1pins::EN_TL, x1pins::PH_TL, x1pins::ISNS_TL), "track left");
static_assert(detail::pins_are(TRACK_R, x1pins::EN_TR, x1pins::PH_TR, x1pins::ISNS_TR), "track right");
static_assert(detail::pins_are(SWING, x1pins::EN_SW, x1pins::PH_SW, x1pins::ISNS_SW), "swing");
static_assert(detail::pins_are(BOOM_L, x1pins::EN_BL, x1pins::PH_BL, x1pins::ISNS_BL), "boom left");
static_assert(detail::pins_are(BOOM_R, x1pins::EN_BR, x1pins::PH_BR, x1pins::ISNS_BR), "boom right");
static_assert(detail::pins_are(STICK, x1pins::EN_ST, x1pins::PH_ST, x1pins::ISNS_ST), "stick");
static_assert(detail::pins_are(BUCKET, x1pins::EN_BK, x1pins::PH_BK, x1pins::ISNS_BK), "bucket");

// SPEC 2: ramps 0.3 s tracks, 0.4 s swing (mandatory), 0.1 s actuators.
inline constexpr ChannelSpec CHANNEL[NUM_CH] = {
    detail::make(TRACK_L, 300, false, true),
    detail::make(TRACK_R, 300, true, true),
    detail::make(SWING, 400, false, true),
    detail::make(BOOM_L, 100, false, false),
    detail::make(BOOM_R, 100, false, false),
    detail::make(STICK, 100, false, false),
    detail::make(BUCKET, 100, false, false),
};

// The app's six axes (excavator_app/shared/world.js AXES), -1..1, with the app's signs:
//   boom +1 = RAISE, stick +1 = STICK IN, bucket +1 = CURL, slew +1 = R (right),
//   left_track / right_track +1 = forward (the up button).
// In the app's model a + boom, stick or bucket axis lengthens that cylinder's stroke.
struct Axes {
  float boom = 0, stick = 0, bucket = 0, slew = 0, left_track = 0, right_track = 0;
};

// The app's dead band: a component under the band is zero, anything else passes unchanged.
float dead_band(float v, float band);
// ISO mapping, SPEC 4, with the app's pad signs (main.js: left pad x = slew, y = stick; right pad
// x = -bucket, y = boom; screen y grows downward, so pushing a stick forward is the pad's top).
Axes map_inputs(const x1link::Control &c, float band);
// Sticks inside the dead band, no track button and no re-sync button (the RESUME condition).
bool inputs_centred(const x1link::Control &c, float band);
// Moves v toward target by at most dt / full_scale_ms.
float ramp_toward(float v, float target, uint32_t dt_ms, uint16_t full_scale_ms);

// Tunables. The boom values are the spec's starting points, to be tuned on the bench.
struct Config {
  uint32_t link_timeout_ms = x1link::LINK_TIMEOUT_MS;  // S1
  float dead_band = 0.12f;                             // the app's 12 %
  float stall_fraction = 0.90f;                        // S4: at or above 90 % of the stalled current at this duty...
  uint32_t stall_ms = 2000;                            // ...for 2 s
  // A stalled brushed motor at duty D draws D x Vbat / R (no back-EMF), capped by the driver's limit. The JGY-370-1260 is
  // 12 V / 1.3 A at stall (vendor table): 9.2 ohm. Below stall_min_a the stalled current heats the motor little and a loaded
  // running motor comes too close to it, so S4 is not judged there (0.4 A = 2 x the rated 0.2 A).
  float motor_ohm = 9.2f;                              // 12 V track and swing motors; measure on the bench
  float stall_min_a = 0.40f;
  float vbat_tau_ms = 2000.f;                          // S5: first-order filter, 2 s time constant
  float vbat_warn_v = 10.5f, vbat_warn_clear_v = 10.7f;
  float vbat_stop_v = 9.6f, vbat_stop_clear_v = 10.5f;  // the stop holds until the battery is above 10.5 V
  float v6_low_v = 5.5f;                                // report only
  float current_tau_ms = 20.f;                          // current filter
  uint32_t nfault_debounce_ms = 4;                      // S6
  uint32_t nfault_wake_blank_ms = 5;                    // nFAULT ignored just after nSLEEP rises
  // Boom pair (SPEC 4)
  float boom_trim_max = 0.15f;          // at most 15 % off the leading side's duty
  float boom_trim_rate = 0.05f;         // trim change per second ("slowly")
  float boom_balance_tol_mA = 10.f;     // currents count as matched within this
  float boom_imbalance_mA = 40.f;       // imbalance fault: difference over 40 mA...
  uint32_t boom_imbalance_ms = 3000;    // ...for 3 s
  float boom_zero_mA = 25.f;            // below this a side's end stop has opened
  float boom_min_duty = 0.15f;          // below this duty the currents are not judged
  uint32_t boom_blank_ms = 300;         // start-up inrush is not judged
  uint32_t boom_end_timeout_ms = 10000; // one side at its end, the other must follow within this
  uint32_t resync_timeout_ms = 120000;  // re-sync button: full stroke is 50-75 s at full duty
  uint32_t bench_max_ms = 10000;        // console bench drive
};

struct Sense {
  uint16_t isns_mV[NUM_CH] = {};  // ADC millivolts at each IPROPI filter, channel order
  uint16_t vbat_adc_mV = 0;       // battery divider output
  uint16_t v6_adc_mV = 0;         // 6 V rail divider output
  bool nfault_low = false;        // shared nFAULT line is low
};

struct Outputs {
  bool nsleep = false;     // 1 = all seven drivers awake
  float en[NUM_CH] = {};   // EN PWM duty 0..1; 0 brakes
  bool ph[NUM_CH] = {};    // PH level, 1 = OUT1 high
  bool lamp[2] = {};
  bool buzzer = false;
  bool led = false;
};

class Controller {
 public:
  explicit Controller(const Config &cfg = Config()) : cfg_(cfg) {}

  // A payload received from the paired handle (the sketch checks the sender MAC).
  x1link::Check on_packet(const uint8_t *data, size_t len, uint32_t now_ms);
  // One control step; call every few ms with fresh readings, then read outputs().
  void update(uint32_t now_ms, const Sense &s);
  const Outputs &outputs() const { return out_; }
  // Telemetry for the handle, sealed and ready to send.
  void make_telemetry(x1link::Telemetry &t, int8_t rssi_dBm);

  // Console. bench_drive returns nullptr when started, else why it was refused. It runs only
  // without a handle link; the ramps and S4-S6 still apply; channels 4 and 5 drive the boom pair.
  const char *bench_drive(Ch ch, float duty, uint32_t ms, uint32_t now_ms);
  void bench_stop() { bench_ = false; }
  // Clears the boom, re-sync and driver faults (driver only with nFAULT high). Not the E-stop:
  // only the handle's RESUME clears that (S2). Refused while a handle link is up.
  bool clear_faults();
  void set_pairing(bool on) { pairing_ = on; }
  void set_current_offset(Ch ch, float mV);
  float current_offset(Ch ch) const { return offset_mV_[ch]; }
  void set_flip(uint8_t mask) { flip_ = uint8_t(mask & 0x7F); }
  uint8_t flip() const { return flip_; }

  // State
  bool armed() const { return armed_; }
  bool link() const { return link_; }
  bool estop() const { return estop_; }
  bool driver_fault() const { return driver_fault_; }
  bool battery_warn() const { return batt_warn_; }
  bool battery_stop() const { return batt_stop_; }
  float battery_v() const { return vbat_f_; }
  float rail_6v() const { return v6_; }
  float duty(Ch ch) const { return duty_[ch]; }
  float current_mA(Ch ch) const { return cur_mA_[ch]; }
  bool stall_cut(Ch ch) const { return stall_cut_[ch]; }
  bool boom_fault() const { return boom_fault_; }
  bool resync_active() const { return resync_; }
  bool resync_failed() const { return resync_failed_; }
  float boom_trim(int side) const { return boom_.trim[side ? 1 : 0]; }
  bool bench_active() const { return bench_; }
  bool pairing() const { return pairing_; }
  const x1link::Control &last_packet() const { return pkt_; }
  uint32_t rx_bad() const { return rx_bad_; }
  uint32_t rx_old() const { return rx_old_; }
  uint32_t rx_lost() const { return lost_; }
  uint8_t rx_per_s() const { return rx_per_s_; }
  uint8_t state_bits() const;
  uint16_t faults() const;
  // Human-readable state for the console; returns the length written.
  size_t describe(char *buf, size_t n) const;

 private:
  struct Boom {
    float trim[2] = {0, 0};
    int8_t dir = 0;
    bool running = false, imb_pending = false, end_mode = false;
    bool end[2] = {false, false};
    uint32_t since = 0, imb_since = 0, end_since = 0;
    void reset() { *this = Boom(); }
  };

  void resume();
  void boom_update(uint32_t now, uint32_t dt, float cmd, float out[2]);
  bool buzzer_on(uint32_t now) const;
  bool led_on(uint32_t now) const;

  Config cfg_;
  bool started_ = false;
  uint32_t last_ms_ = 0;

  // link
  bool link_ = false;
  x1link::Control pkt_{};
  uint32_t last_rx_ms_ = 0;
  uint32_t rx_bad_ = 0, rx_old_ = 0, lost_ = 0;
  uint16_t rx_count_ = 0;
  uint8_t rx_per_s_ = 0;
  uint32_t rx_window_ms_ = 0;
  uint16_t tlm_seq_ = 0;

  // safety
  bool armed_ = false, estop_ = false, driver_fault_ = false, pairing_ = false;
  bool nfault_now_ = false, nfault_pending_ = false;
  uint32_t nfault_since_ = 0;
  bool awake_ = false;
  uint32_t wake_ms_ = 0;
  float vbat_f_ = 0, v6_ = 0;
  bool batt_warn_ = false, batt_stop_ = false;

  // channels
  float duty_[NUM_CH] = {}, cur_mA_[NUM_CH] = {}, offset_mV_[NUM_CH] = {};
  bool ph_[NUM_CH] = {};
  bool stall_cut_[NUM_CH] = {}, stall_pending_[NUM_CH] = {};
  uint32_t stall_since_[NUM_CH] = {};
  uint8_t flip_ = 0;

  // boom pair
  Boom boom_;
  bool boom_fault_ = false, resync_ = false, resync_failed_ = false, resync_edge_ = false;
  uint32_t resync_since_ = 0;

  // console bench drive
  bool bench_ = false;
  Ch bench_ch_ = TRACK_L;
  float bench_duty_ = 0;
  uint32_t bench_since_ = 0, bench_ms_ = 0;

  Outputs out_{};
};

// Console helpers. "aa:bb:cc:dd:ee:ff" (or '-' separators); exactly 2n hex digits.
bool parse_mac(const char *s, uint8_t mac[6]);
bool parse_hex(const char *s, uint8_t *out, size_t n);

}  // namespace x1

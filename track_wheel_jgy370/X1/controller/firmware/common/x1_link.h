// X1 radio link: the ESP-NOW packets between the handle and the machine (SPEC C1, sections 6 and 7).
//
// Master copy: firmware/common/x1_link.h. The Arduino build copies only the sketch folder, so each
// sketch keeps a byte-identical copy in its src/ (firmware/sync_headers.sh writes it, and
// firmware/test/run_tests.sh fails if a copy differs). Edit the master, then run the script.
//
// All packets are packed, little-endian (ESP32 and x86/ARM hosts), and start with MAGIC, VERSION
// and a type byte. The last two bytes are a CRC-16/CCITT-FALSE over everything before them.
// Plain C++17, no Arduino headers: the same file builds on the ESP32 and on the host.
#pragma once
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#if defined(__BYTE_ORDER__) && defined(__ORDER_LITTLE_ENDIAN__)
static_assert(__BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__, "x1_link packets are little-endian");
#endif

namespace x1link {

constexpr uint8_t MAGIC = 0x58;  // 'X'
constexpr uint8_t VERSION = 1;   // bump on any change to a packet layout

enum Type : uint8_t {
  CONTROL = 1,       // handle -> machine, 50 Hz
  TELEMETRY = 2,     // machine -> handle, 10 Hz
  PAIR_REQUEST = 3,  // handle -> broadcast, unencrypted, while both are in pairing mode
  PAIR_ACCEPT = 4,   // machine -> handle, unencrypted: the link key and the radio channel
  PAIR_CONFIRM = 5,  // handle -> machine, unencrypted: proves the key arrived
};

constexpr uint32_t CONTROL_PERIOD_MS = 20;     // 50 Hz (SPEC L2)
constexpr uint32_t TELEMETRY_PERIOD_MS = 100;  // 10 Hz (SPEC L2)
constexpr uint32_t LINK_TIMEOUT_MS = 350;      // the app's input watchdog (SPEC S1)
constexpr uint8_t DEFAULT_WIFI_CHANNEL = 1;    // SPEC L3
constexpr int16_t AXIS_FULL = 1000;            // stick axes are per mille
constexpr uint8_t SPEED_MIN = 20, SPEED_MAX = 100, SPEED_STEP = 5, SPEED_DEFAULT = 65;  // the app's slider

// ESP-NOW primary master key (esp_now_set_pmk). It only wraps the per-pair local key (LMK), which
// pairing generates at random on the machine; both ends must use the same PMK.
constexpr uint8_t PMK[16] = {'X', '1', '-', 'e', 'x', 'c', 'a', 'v', 'a', 't', 'o', 'r', '-', 'p', 'm', 'k'};

// Control.buttons. Track and re-sync bits are held buttons. ESTOP is set while the red button is
// pressed (the machine latches it); RESUME is a press of the RESUME button. LAMP1/LAMP2 are the
// wanted lamp states (the handle toggles them); HORN is held.
enum Button : uint16_t {
  BTN_LEFT_FWD = 1u << 0,   // LEFT TRACK up
  BTN_LEFT_REV = 1u << 1,   // LEFT TRACK down
  BTN_RIGHT_FWD = 1u << 2,  // RIGHT TRACK up
  BTN_RIGHT_REV = 1u << 3,  // RIGHT TRACK down
  BTN_ESTOP = 1u << 4,
  BTN_RESUME = 1u << 5,
  BTN_LAMP1 = 1u << 6,  // roof work lamps
  BTN_LAMP2 = 1u << 7,  // toolbox lamp
  BTN_HORN = 1u << 8,
  BTN_RESYNC = 1u << 9,  // boom re-sync: drive both boom sides to the retract end stops
};
constexpr uint16_t BTN_ALL = 0x03FF;

// Telemetry.state
enum State : uint8_t {
  ST_ARMED = 1u << 0,    // drivers awake, inputs are obeyed
  ST_LINK = 1u << 1,     // a valid control packet within LINK_TIMEOUT_MS
  ST_ESTOP = 1u << 2,    // EMERGENCY STOP latched; RESUME with inputs centred clears it
  ST_PAIRING = 1u << 3,  // machine in pairing mode (disarmed)
  ST_RESYNC = 1u << 4,   // boom re-sync running
  ST_BENCH = 1u << 5,    // console bench drive running (no handle)
};

// Telemetry.faults
enum Fault : uint16_t {
  F_DRIVER = 1u << 0,        // S6: nFAULT went low; latched until RESUME with the line high
  F_DRIVER_LINE = 1u << 1,   // nFAULT is low now
  F_BOOM = 1u << 2,          // boom pair imbalance (or one side never reached its end stop)
  F_RESYNC_TIMEOUT = 1u << 3,
  F_STALL = 1u << 4,         // S4: a 12 V channel is cut; see the channel flags
  F_BATTERY_LOW = 1u << 5,   // S5: motors stopped (9.6 V)
  F_BATTERY_WARN = 1u << 6,  // S5: warning (10.5 V); the handle vibrates
  F_RAIL_6V_LOW = 1u << 7,   // 6 V actuator rail low while the battery is up (report only)
};

// ChannelReport.flags
enum ChannelFlag : uint8_t {
  CH_STALL_CUT = 1u << 0,  // S4 cut-out; clears when the channel's input returns to centre
  CH_BOOM_CUT = 1u << 1,   // stopped by the boom fault
  CH_PH = 1u << 2,         // PH pin level (1 = OUT1 high)
  CH_AT_END = 1u << 3,     // boom side reads zero current: its end stop has opened
};

#pragma pack(push, 1)

// Handle -> machine, every CONTROL_PERIOD_MS. Stick axes are the handle's calibrated positions,
// -1000..1000: x + = pushed right, y + = pushed forward (away from the operator). The machine
// applies the app's 12 % dead band, the ISO mapping and the speed scaling (SPEC 4).
struct Control {
  uint8_t magic, version, type;
  uint16_t seq;       // +1 per packet, wraps
  int16_t lx, ly;     // left stick: swing (x), stick (y)
  int16_t rx, ry;     // right stick: bucket (x), boom (y)
  uint8_t speed_pct;  // movement speed, 20..100 (the handle steps it by 5)
  uint16_t buttons;   // Button bits
  uint16_t crc;
};

struct ChannelReport {
  int8_t duty_pct;      // signed output after the ramp; + = the channel's positive motion
  uint8_t flags;        // ChannelFlag bits
  uint16_t current_mA;  // from IPROPI, offset removed, filtered
};

// Machine -> handle, every TELEMETRY_PERIOD_MS.
struct Telemetry {
  uint8_t magic, version, type;
  uint8_t state;        // State bits
  uint16_t seq;
  uint16_t ack_seq;     // seq of the last control packet accepted
  uint16_t faults;      // Fault bits
  uint16_t vbat_mV;     // battery, 2 s filtered (the value S5 acts on)
  uint16_t v6_mV;       // 6 V actuator rail
  int8_t rssi_dBm;      // of the last control packet; 0 = none yet
  uint8_t rx_per_s;     // control packets accepted in the last second (50 expected)
  ChannelReport ch[7];  // x1pins::CHANNELS order: track L, track R, swing, boom L, boom R, stick, bucket
  uint16_t crc;
};

// Pairing (SPEC L1). Both ends enter pairing mode by hand. The handle broadcasts PairRequest on the
// machine's radio channel; the machine answers with a fresh random LMK and the channel; the handle
// stores the machine MAC and the key and sends PairConfirm; the machine then stores the handle MAC
// and the key and leaves pairing mode. After that, all traffic is encrypted with the LMK, and the
// machine accepts control packets only from that MAC. The key crosses the air in clear once, during
// the pairing window.
struct PairRequest {
  uint8_t magic, version, type;
  uint32_t nonce;  // random, echoed in the answer
  uint16_t crc;
};

struct PairAccept {
  uint8_t magic, version, type;
  uint32_t nonce;        // the request's nonce
  uint8_t wifi_channel;  // 1..13
  uint8_t lmk[16];
  uint16_t crc;
};

struct PairConfirm {
  uint8_t magic, version, type;
  uint32_t nonce;      // the request's nonce
  uint16_t key_check;  // crc16(lmk, 16)
  uint16_t crc;
};

#pragma pack(pop)

static_assert(sizeof(Control) == 18, "Control layout");
static_assert(sizeof(ChannelReport) == 4, "ChannelReport layout");
static_assert(sizeof(Telemetry) == 46, "Telemetry layout");
static_assert(sizeof(PairRequest) == 9, "PairRequest layout");
static_assert(sizeof(PairAccept) == 26, "PairAccept layout");
static_assert(sizeof(PairConfirm) == 11, "PairConfirm layout");

// CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, no reflection; "123456789" -> 0x29B1.
inline uint16_t crc16(const uint8_t *p, size_t n, uint16_t crc = 0xFFFF) {
  while (n--) {
    crc = uint16_t(crc ^ (uint16_t(*p++) << 8));
    for (int i = 0; i < 8; ++i) crc = (crc & 0x8000) ? uint16_t((crc << 1) ^ 0x1021) : uint16_t(crc << 1);
  }
  return crc;
}

enum class Check : uint8_t { OK, LENGTH, MAGIC, VERSION, TYPE, CRC, RANGE, SEQUENCE /* used by the receiver */ };

inline const char *check_name(Check c) {
  switch (c) {
    case Check::OK: return "ok";
    case Check::LENGTH: return "length";
    case Check::MAGIC: return "magic";
    case Check::VERSION: return "version";
    case Check::TYPE: return "type";
    case Check::CRC: return "crc";
    case Check::RANGE: return "range";
    case Check::SEQUENCE: return "sequence";
  }
  return "?";
}

// Type byte of a frame with the right magic and version, or -1.
inline int frame_type(const uint8_t *data, size_t len) {
  if (!data || len < 5 || data[0] != MAGIC || data[1] != VERSION) return -1;
  return data[2];
}

// Fills the header and the CRC; the struct's bytes are then the frame.
template <class P>
inline void seal(P &p, uint8_t type) {
  p.magic = MAGIC;
  p.version = VERSION;
  p.type = type;
  const uint16_t c = crc16(reinterpret_cast<const uint8_t *>(&p), sizeof(P) - 2);
  uint8_t *b = reinterpret_cast<uint8_t *>(&p);
  b[sizeof(P) - 2] = uint8_t(c & 0xFF);
  b[sizeof(P) - 1] = uint8_t(c >> 8);
}

// Length, header and CRC; copies the frame into out when they pass.
template <class P>
inline Check open_frame(const uint8_t *data, size_t len, uint8_t type, P &out) {
  if (!data || len != sizeof(P)) return Check::LENGTH;
  if (data[0] != MAGIC) return Check::MAGIC;
  if (data[1] != VERSION) return Check::VERSION;
  if (data[2] != type) return Check::TYPE;
  const uint16_t got = uint16_t(data[len - 2] | (uint16_t(data[len - 1]) << 8));
  if (crc16(data, len - 2) != got) return Check::CRC;
  memcpy(&out, data, sizeof(P));
  return Check::OK;
}

inline void encode(Control &p) { seal(p, CONTROL); }
inline void encode(Telemetry &p) { seal(p, TELEMETRY); }
inline void encode(PairRequest &p) { seal(p, PAIR_REQUEST); }
inline void encode(PairAccept &p) { seal(p, PAIR_ACCEPT); }
inline void encode(PairConfirm &p) { seal(p, PAIR_CONFIRM); }

inline bool axis_ok(int16_t v) { return v >= -AXIS_FULL && v <= AXIS_FULL; }

inline Check validate(const uint8_t *data, size_t len, Control &out) {
  const Check c = open_frame(data, len, CONTROL, out);
  if (c != Check::OK) return c;
  if (!axis_ok(out.lx) || !axis_ok(out.ly) || !axis_ok(out.rx) || !axis_ok(out.ry)) return Check::RANGE;
  if (out.speed_pct < SPEED_MIN || out.speed_pct > SPEED_MAX) return Check::RANGE;
  if (out.buttons & uint16_t(~BTN_ALL)) return Check::RANGE;
  return Check::OK;
}

inline Check validate(const uint8_t *data, size_t len, Telemetry &out) {
  return open_frame(data, len, TELEMETRY, out);
}

inline Check validate(const uint8_t *data, size_t len, PairRequest &out) {
  return open_frame(data, len, PAIR_REQUEST, out);
}

inline Check validate(const uint8_t *data, size_t len, PairAccept &out) {
  const Check c = open_frame(data, len, PAIR_ACCEPT, out);
  if (c != Check::OK) return c;
  return (out.wifi_channel >= 1 && out.wifi_channel <= 13) ? Check::OK : Check::RANGE;
}

inline Check validate(const uint8_t *data, size_t len, PairConfirm &out) {
  return open_frame(data, len, PAIR_CONFIRM, out);
}

inline uint16_t key_check(const uint8_t lmk[16]) { return crc16(lmk, 16); }

}  // namespace x1link

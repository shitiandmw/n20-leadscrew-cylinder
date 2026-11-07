// X1 main board firmware, machine side (SPEC C1, F1 and F2). Arduino-ESP32 3.x (ESP-IDF 5).
//
// This file is the hardware layer only: pins, MCPWM, ADC, LEDC, ESP-NOW, NVS and the USB console.
// Every control and safety decision is in src/control_logic.cpp, which the host tests cover.
// Board: ESP32S3 Dev Module, USB CDC On Boot: Enabled, Flash Size: 8MB (see README.md).
#include <Arduino.h>
#include <Preferences.h>
#include <WiFi.h>
#include <driver/mcpwm_prelude.h>
#include <esp_now.h>
#include <esp_random.h>
#include <esp_wifi.h>

#include "src/control_logic.h"

#if !defined(CONFIG_IDF_TARGET_ESP32S3)
#error "Build for the ESP32-S3 (board esp32:esp32:esp32s3)"
#endif
#if !ARDUINO_USB_CDC_ON_BOOT
#error "The console is on the native USB: set USB CDC On Boot = Enabled (FQBN option CDCOnBoot=cdc)"
#endif

using namespace x1;

// ---- constants and state ---------------------------------------------------------------------

static constexpr uint32_t PWM_RESOLUTION_HZ = 20000000;                 // MCPWM timer clock
static constexpr uint32_t PWM_FREQ_HZ = 20000;                          // SPEC 2: 20 kHz
static constexpr uint32_t PWM_TICKS = PWM_RESOLUTION_HZ / PWM_FREQ_HZ;  // 1000 steps
static constexpr uint32_t CONTROL_PERIOD_MS = 2;
static constexpr uint32_t PAIR_WINDOW_MS = 60000;
static constexpr uint32_t BOOT_PAIR_WINDOW_MS = 10000;  // BOOT pressed within 10 s of power-up...
static constexpr uint32_t BOOT_HOLD_MS = 2000;          // ...and held for 2 s starts pairing
static constexpr uint32_t LAMP_PWM_HZ = 2000, BUZZER_HZ = 2700;
static constexpr int RXQ = 8, RX_MAX = 64;
static const char *const NVS_NS = "x1main";

struct RxItem {
  uint8_t mac[6];
  int8_t rssi;
  uint8_t len;
  uint8_t data[RX_MAX];
};

struct PwmOut {
  mcpwm_cmpr_handle_t cmp = nullptr;
  mcpwm_gen_handle_t gen = nullptr;
  int mode = -1;  // 0 forced low, 1 forced high, 2 PWM
};

struct PairingState {
  bool active = false, have = false;
  uint32_t since = 0, nonce = 0;
  uint8_t mac[6] = {}, lmk[16] = {};
};

static Controller core;
static Preferences prefs;
static PwmOut pwm[NUM_CH];
static bool pwm_ok = false;

// ESP-NOW receive queue: filled in the Wi-Fi task, drained in loop().
static RxItem rxq[RXQ];
static uint8_t rx_head = 0, rx_tail = 0;
static uint32_t rx_dropped = 0;
static portMUX_TYPE rx_mux = portMUX_INITIALIZER_UNLOCKED;

static bool radio_ok = false, paired = false;
static uint8_t peer_mac[6] = {}, peer_lmk[16] = {};
static uint8_t wifi_channel = x1link::DEFAULT_WIFI_CHANNEL;
static int8_t last_rssi = 0;
static PairingState pairing;

static uint32_t last_control = 0, last_telemetry = 0, log_period = 0, last_log = 0;
static uint32_t boot_down_since = 0;
static bool boot_was_down = false;
static char line[128];
static size_t line_len = 0;
static char text[1800];

static const uint8_t ADC_PINS[] = {x1pins::ISNS_TL, x1pins::ISNS_TR, x1pins::ISNS_SW,  x1pins::ISNS_BL, x1pins::ISNS_BR,
                                   x1pins::ISNS_ST, x1pins::ISNS_BK, x1pins::VBAT_SNS, x1pins::V6_SNS};

// ---- motor PWM: MCPWM on the seven EN pins -----------------------------------------------------

static bool pwm_begin() {
  // One timer per group. Each operator has two comparators and two generators: channels 0-5 use
  // the three operators of group 0, channel 6 one operator of group 1.
  mcpwm_timer_handle_t timer[2] = {};
  for (int g = 0; g < 2; ++g) {
    mcpwm_timer_config_t tc = {};
    tc.group_id = g;
    tc.clk_src = MCPWM_TIMER_CLK_SRC_DEFAULT;
    tc.resolution_hz = PWM_RESOLUTION_HZ;
    tc.count_mode = MCPWM_TIMER_COUNT_MODE_UP;
    tc.period_ticks = PWM_TICKS;
    if (mcpwm_new_timer(&tc, &timer[g]) != ESP_OK) return false;
  }
  mcpwm_oper_handle_t oper[4] = {};
  for (int i = 0; i < 4; ++i) {
    mcpwm_operator_config_t oc = {};
    oc.group_id = i < 3 ? 0 : 1;
    if (mcpwm_new_operator(&oc, &oper[i]) != ESP_OK) return false;
    if (mcpwm_operator_connect_timer(oper[i], timer[oc.group_id]) != ESP_OK) return false;
  }
  for (int ch = 0; ch < NUM_CH; ++ch) {
    PwmOut &p = pwm[ch];
    mcpwm_comparator_config_t cc = {};
    cc.flags.update_cmp_on_tez = true;
    if (mcpwm_new_comparator(oper[ch / 2], &cc, &p.cmp) != ESP_OK) return false;
    mcpwm_comparator_set_compare_value(p.cmp, 0);
    mcpwm_generator_config_t gc = {};
    gc.gen_gpio_num = CHANNEL[ch].en;
    if (mcpwm_new_generator(oper[ch / 2], &gc, &p.gen) != ESP_OK) return false;
    mcpwm_generator_set_force_level(p.gen, 0, true);  // EN low = brake until driven
    p.mode = 0;
    mcpwm_gen_timer_event_action_t at_zero = {};
    at_zero.direction = MCPWM_TIMER_DIRECTION_UP;
    at_zero.event = MCPWM_TIMER_EVENT_EMPTY;
    at_zero.action = MCPWM_GEN_ACTION_HIGH;
    mcpwm_gen_compare_event_action_t at_cmp = {};
    at_cmp.direction = MCPWM_TIMER_DIRECTION_UP;
    at_cmp.comparator = p.cmp;
    at_cmp.action = MCPWM_GEN_ACTION_LOW;
    if (mcpwm_generator_set_action_on_timer_event(p.gen, at_zero) != ESP_OK) return false;
    if (mcpwm_generator_set_action_on_compare_event(p.gen, at_cmp) != ESP_OK) return false;
  }
  for (int g = 0; g < 2; ++g) {
    if (mcpwm_timer_enable(timer[g]) != ESP_OK) return false;
    if (mcpwm_timer_start_stop(timer[g], MCPWM_TIMER_START_NO_STOP) != ESP_OK) return false;
  }
  return true;
}

// 0 and 100 % are forced levels, so no compare edge case can leave a glitch.
static void pwm_set(int ch, float duty) {
  PwmOut &p = pwm[ch];
  const long t = lroundf(duty * float(PWM_TICKS));
  if (t <= 0) {
    if (p.mode != 0) mcpwm_generator_set_force_level(p.gen, 0, true);
    p.mode = 0;
  } else if (t >= long(PWM_TICKS)) {
    if (p.mode != 1) mcpwm_generator_set_force_level(p.gen, 1, true);
    p.mode = 1;
  } else {
    mcpwm_comparator_set_compare_value(p.cmp, uint32_t(t));
    if (p.mode != 2) mcpwm_generator_set_force_level(p.gen, -1, true);
    p.mode = 2;
  }
}

// ---- pins --------------------------------------------------------------------------------------

static Sense read_sense() {
  Sense s;
  for (int ch = 0; ch < NUM_CH; ++ch) s.isns_mV[ch] = uint16_t(analogReadMilliVolts(CHANNEL[ch].isns));
  s.vbat_adc_mV = uint16_t(analogReadMilliVolts(x1pins::VBAT_SNS));
  s.v6_adc_mV = uint16_t(analogReadMilliVolts(x1pins::V6_SNS));
  s.nfault_low = digitalRead(x1pins::NFAULT) == LOW;
  return s;
}

static void apply(const Outputs &o) {
  // Direction and EN first, then nSLEEP, so a waking driver sees a braked bridge.
  for (int ch = 0; ch < NUM_CH; ++ch) {
    digitalWrite(CHANNEL[ch].ph, o.ph[ch] ? HIGH : LOW);
    if (pwm_ok) pwm_set(ch, o.nsleep ? o.en[ch] : 0.f);
  }
  digitalWrite(x1pins::NSLEEP, (o.nsleep && pwm_ok) ? HIGH : LOW);
  static int last[3] = {-1, -1, -1};  // LEDC duties, written only when they change
  const int want[3] = {o.lamp[0] ? 255 : 0, o.lamp[1] ? 255 : 0, o.buzzer ? 128 : 0};
  const uint8_t pin[3] = {x1pins::LAMP1_PWM, x1pins::LAMP2_PWM, x1pins::BUZ_PWM};
  for (int i = 0; i < 3; ++i)
    if (want[i] != last[i]) ledcWrite(pin[i], uint32_t(last[i] = want[i]));
  digitalWrite(x1pins::LED_STAT, o.led ? HIGH : LOW);
}

// ---- settings (NVS) ----------------------------------------------------------------------------

static void save_offsets() {
  int16_t off[NUM_CH];
  for (int ch = 0; ch < NUM_CH; ++ch) off[ch] = int16_t(lroundf(core.current_offset(Ch(ch)) * 10.f));  // 0.1 mV
  prefs.putBytes("ioff", off, sizeof off);
}

static void load_settings() {
  prefs.begin(NVS_NS, false);
  paired = prefs.isKey("peer") && prefs.isKey("lmk") && prefs.getBytes("peer", peer_mac, 6) == 6 &&
           prefs.getBytes("lmk", peer_lmk, 16) == 16;
  const uint8_t ch = prefs.isKey("chan") ? prefs.getUChar("chan", x1link::DEFAULT_WIFI_CHANNEL)
                                         : x1link::DEFAULT_WIFI_CHANNEL;
  wifi_channel = (ch >= 1 && ch <= 13) ? ch : x1link::DEFAULT_WIFI_CHANNEL;
  int16_t off[NUM_CH];
  if (prefs.isKey("ioff") && prefs.getBytes("ioff", off, sizeof off) == sizeof off)
    for (int c = 0; c < NUM_CH; ++c) core.set_current_offset(Ch(c), off[c] / 10.f);
  core.set_flip(prefs.isKey("flip") ? prefs.getUChar("flip", 0) : 0);
}

// ---- radio: ESP-NOW ----------------------------------------------------------------------------

static void on_recv(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (!info || !info->src_addr || !data || len <= 0 || len > RX_MAX) return;
  portENTER_CRITICAL(&rx_mux);
  const uint8_t next = uint8_t((rx_head + 1) % RXQ);
  if (next == rx_tail) {
    ++rx_dropped;
  } else {
    RxItem &it = rxq[rx_head];
    memcpy(it.mac, info->src_addr, 6);
    it.rssi = info->rx_ctrl ? int8_t(info->rx_ctrl->rssi) : 0;
    it.len = uint8_t(len);
    memcpy(it.data, data, size_t(len));
    rx_head = next;
  }
  portEXIT_CRITICAL(&rx_mux);
}

static bool rx_pop(RxItem &out) {
  bool got = false;
  portENTER_CRITICAL(&rx_mux);
  if (rx_tail != rx_head) {
    out = rxq[rx_tail];
    rx_tail = uint8_t((rx_tail + 1) % RXQ);
    got = true;
  }
  portEXIT_CRITICAL(&rx_mux);
  return got;
}

static bool set_wifi_channel(uint8_t ch) {
  esp_wifi_set_promiscuous(true);
  const esp_err_t e = esp_wifi_set_channel(ch, WIFI_SECOND_CHAN_NONE);
  esp_wifi_set_promiscuous(false);
  return e == ESP_OK;
}

// lmk == nullptr: unencrypted (pairing replies only).
static bool add_peer(const uint8_t mac[6], const uint8_t *lmk) {
  if (esp_now_is_peer_exist(mac)) esp_now_del_peer(mac);
  esp_now_peer_info_t p = {};
  memcpy(p.peer_addr, mac, 6);
  p.channel = 0;  // follow the station's fixed channel
  p.ifidx = WIFI_IF_STA;
  p.encrypt = lmk != nullptr;
  if (lmk) memcpy(p.lmk, lmk, 16);
  return esp_now_add_peer(&p) == ESP_OK;
}

static bool radio_begin() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.disconnect();
  if (!set_wifi_channel(wifi_channel)) return false;
  if (esp_now_init() != ESP_OK) return false;
  if (esp_now_set_pmk(x1link::PMK) != ESP_OK) return false;
  if (esp_now_register_recv_cb(on_recv) != ESP_OK) return false;
  if (paired) add_peer(peer_mac, peer_lmk);
  return true;
}

static void print_mac(const char *label, const uint8_t m[6]) {
  Serial.printf("%s%02x:%02x:%02x:%02x:%02x:%02x\n", label, m[0], m[1], m[2], m[3], m[4], m[5]);
}

static void pairing_start(uint32_t now) {
  if (!radio_ok) {
    Serial.println("pairing: radio not running");
    return;
  }
  if (paired) esp_now_del_peer(peer_mac);  // the stored pair stays in NVS until a new one is confirmed
  pairing = PairingState();
  pairing.active = true;
  pairing.since = now;
  core.set_pairing(true);
  Serial.printf("pairing: on for %lu s on Wi-Fi channel %u; start pairing on the handle\n",
                (unsigned long)(PAIR_WINDOW_MS / 1000), unsigned(wifi_channel));
}

static void pairing_end(bool ok) {
  if (!ok) {
    if (pairing.have) esp_now_del_peer(pairing.mac);
    if (paired) add_peer(peer_mac, peer_lmk);  // back to the old handle
  }
  pairing = PairingState();
  core.set_pairing(false);
}

static void pairing_rx(const RxItem &it) {
  using namespace x1link;
  const int type = frame_type(it.data, it.len);
  if (type == PAIR_REQUEST) {
    PairRequest rq;
    if (validate(it.data, it.len, rq) != Check::OK) return;
    if (!pairing.have || memcmp(pairing.mac, it.mac, 6) != 0) {
      if (pairing.have) esp_now_del_peer(pairing.mac);
      memcpy(pairing.mac, it.mac, 6);
      esp_fill_random(pairing.lmk, sizeof pairing.lmk);
      pairing.have = true;
    }
    pairing.nonce = rq.nonce;
    add_peer(it.mac, nullptr);  // the answer goes out unencrypted
    PairAccept ac = {};
    ac.nonce = rq.nonce;
    ac.wifi_channel = wifi_channel;
    memcpy(ac.lmk, pairing.lmk, sizeof ac.lmk);
    encode(ac);
    esp_now_send(it.mac, reinterpret_cast<const uint8_t *>(&ac), sizeof ac);
    print_mac("pairing: request from ", it.mac);
  } else if (type == PAIR_CONFIRM) {
    PairConfirm cf;
    if (validate(it.data, it.len, cf) != Check::OK || !pairing.have || memcmp(pairing.mac, it.mac, 6) != 0 ||
        cf.nonce != pairing.nonce || cf.key_check != key_check(pairing.lmk))
      return;
    memcpy(peer_mac, pairing.mac, 6);
    memcpy(peer_lmk, pairing.lmk, 16);
    paired = true;
    prefs.putBytes("peer", peer_mac, 6);
    prefs.putBytes("lmk", peer_lmk, 16);
    add_peer(peer_mac, peer_lmk);  // from now on encrypted
    pairing.have = false;
    pairing_end(true);
    print_mac("pairing: paired with ", peer_mac);
  }
}

static void radio_poll(uint32_t now) {
  RxItem it;
  while (rx_pop(it)) {
    if (pairing.active) {
      pairing_rx(it);
      continue;
    }
    if (!paired || memcmp(it.mac, peer_mac, 6) != 0) continue;  // only the paired handle (SPEC L1)
    if (core.on_packet(it.data, it.len, now) == x1link::Check::OK) last_rssi = it.rssi;
  }
}

static void send_telemetry() {
  if (!radio_ok || !paired || pairing.active) return;
  x1link::Telemetry t;
  core.make_telemetry(t, last_rssi);
  esp_now_send(peer_mac, reinterpret_cast<const uint8_t *>(&t), sizeof t);
}

// ---- console -----------------------------------------------------------------------------------

static void print_help() {
  Serial.println(
      "X1 main board console\n"
      "  show                     state, inputs, outputs, currents, battery, radio\n"
      "  log <ms> | log off       print a status line every <ms>\n"
      "  zero                     measure the current offsets at rest and save them (disarmed only)\n"
      "  wifi [1-13]              show or set the radio channel (saved; default 1)\n"
      "  pair                     pairing mode for 60 s (or: BOOT held 2 s in the first 10 s after power-up)\n"
      "  peer [<mac> <key>]       show the paired handle, or set it by hand (key: 32 hex digits)\n"
      "  unpair                   forget the paired handle\n"
      "  drive <1-7> <%> [ms]     bench drive, -100..100 %, default 1000 ms, max 10000 (no handle link)\n"
      "  stop                     stop a bench drive\n"
      "  clear                    clear boom, re-sync and driver faults (no handle link; not the E-stop)\n"
      "  flip <1-7>               invert a channel's direction (saved), if its motor runs the wrong way\n"
      "  reboot");
}

static void print_status_line(uint32_t now) {
  Serial.printf("t=%lu st=0x%02x f=0x%04x vbat=%.2f duty", (unsigned long)now, unsigned(core.state_bits()),
                unsigned(core.faults()), double(core.battery_v()));
  for (int ch = 0; ch < NUM_CH; ++ch) Serial.printf(" %+.2f", double(core.duty(Ch(ch))));
  Serial.print(" mA");
  for (int ch = 0; ch < NUM_CH; ++ch) Serial.printf(" %.0f", double(core.current_mA(Ch(ch))));
  Serial.printf(" rssi=%d\n", int(last_rssi));
}

static void cmd_zero() {
  if (core.outputs().nsleep) {
    Serial.println("zero: refused, the drivers are awake (disarm first)");
    return;
  }
  // Awake and braked (EN = 0): no current flows, so the readings are the offsets.
  digitalWrite(x1pins::NSLEEP, HIGH);
  delay(5);
  for (int ch = 0; ch < NUM_CH; ++ch) {
    uint32_t sum = 0;
    for (int i = 0; i < 64; ++i) sum += analogReadMilliVolts(CHANNEL[ch].isns);
    core.set_current_offset(Ch(ch), sum / 64.f);
  }
  digitalWrite(x1pins::NSLEEP, LOW);
  save_offsets();
  Serial.print("zero: offsets (mV)");
  for (int ch = 0; ch < NUM_CH; ++ch) Serial.printf(" %.1f", double(core.current_offset(Ch(ch))));
  Serial.println(" saved");
}

static void console_command(char *cmd, uint32_t now) {
  char *argv[4] = {};
  int argc = 0;
  for (char *tok = strtok(cmd, " \t"); tok && argc < 4; tok = strtok(nullptr, " \t")) argv[argc++] = tok;
  if (argc == 0) return;
  const char *c = argv[0];
  if (!strcmp(c, "help") || !strcmp(c, "?")) {
    print_help();
  } else if (!strcmp(c, "show")) {
    core.describe(text, sizeof text);
    Serial.print(text);
    uint8_t own[6] = {};
    esp_wifi_get_mac(WIFI_IF_STA, own);
    print_mac("machine MAC: ", own);
    Serial.printf("radio: %s, Wi-Fi channel %u, last RSSI %d dBm, queue drops %lu, MCPWM %s\n",
                  radio_ok ? "running" : "FAILED", unsigned(wifi_channel), int(last_rssi), (unsigned long)rx_dropped,
                  pwm_ok ? "ok" : "FAILED (drivers kept asleep)");
    if (paired) print_mac("paired handle: ", peer_mac);
    else Serial.println("paired handle: none (type pair)");
  } else if (!strcmp(c, "log")) {
    log_period = (argc > 1 && strcmp(argv[1], "off") != 0) ? uint32_t(strtoul(argv[1], nullptr, 10)) : 0;
    if (log_period && log_period < 20) log_period = 20;
    Serial.printf("log: %s\n", log_period ? "on" : "off");
  } else if (!strcmp(c, "zero")) {
    cmd_zero();
  } else if (!strcmp(c, "wifi")) {
    if (argc > 1) {
      const long ch = strtol(argv[1], nullptr, 10);
      if (ch < 1 || ch > 13) {
        Serial.println("wifi: channel 1-13");
        return;
      }
      wifi_channel = uint8_t(ch);
      prefs.putUChar("chan", wifi_channel);
      if (radio_ok) set_wifi_channel(wifi_channel);
      Serial.println("wifi: saved; the handle must use the same channel (pairing tells it)");
    }
    Serial.printf("wifi: channel %u\n", unsigned(wifi_channel));
  } else if (!strcmp(c, "pair")) {
    pairing_start(now);
  } else if (!strcmp(c, "peer")) {
    if (argc == 3) {
      uint8_t mac[6], key[16];
      if (!parse_mac(argv[1], mac) || !parse_hex(argv[2], key, 16)) {
        Serial.println("peer: usage peer aa:bb:cc:dd:ee:ff <32 hex digits>");
        return;
      }
      if (paired && radio_ok) esp_now_del_peer(peer_mac);
      memcpy(peer_mac, mac, 6);
      memcpy(peer_lmk, key, 16);
      paired = true;
      prefs.putBytes("peer", peer_mac, 6);
      prefs.putBytes("lmk", peer_lmk, 16);
      if (radio_ok) add_peer(peer_mac, peer_lmk);
    }
    if (paired) print_mac("peer: ", peer_mac);
    else Serial.println("peer: none");
  } else if (!strcmp(c, "unpair")) {
    if (paired && radio_ok) esp_now_del_peer(peer_mac);
    paired = false;
    prefs.remove("peer");
    prefs.remove("lmk");
    Serial.println("unpair: done");
  } else if (!strcmp(c, "drive")) {
    if (argc < 3) {
      Serial.println("drive: usage drive <1-7> <-100..100> [ms]");
      return;
    }
    const long ch = strtol(argv[1], nullptr, 10), pct = strtol(argv[2], nullptr, 10);
    const uint32_t ms = argc > 3 ? uint32_t(strtoul(argv[3], nullptr, 10)) : 1000;
    if (ch < 1 || ch > NUM_CH || pct < -100 || pct > 100) {
      Serial.println("drive: channel 1-7, duty -100..100");
      return;
    }
    const char *why = core.bench_drive(Ch(ch - 1), pct / 100.f, ms, now);
    if (why) Serial.printf("drive: refused, %s\n", why);
    else Serial.printf("drive: %s at %ld %% for up to %lu ms\n", CHANNEL[ch - 1].name, pct, (unsigned long)ms);
  } else if (!strcmp(c, "stop")) {
    core.bench_stop();
    Serial.println("stop: done");
  } else if (!strcmp(c, "clear")) {
    Serial.println(core.clear_faults() ? "clear: done" : "clear: refused while a handle is connected");
  } else if (!strcmp(c, "flip")) {
    const long ch = argc > 1 ? strtol(argv[1], nullptr, 10) : 0;
    if (ch < 1 || ch > NUM_CH) {
      Serial.println("flip: usage flip <1-7>");
      return;
    }
    core.set_flip(uint8_t(core.flip() ^ (1u << (ch - 1))));
    prefs.putUChar("flip", core.flip());
    Serial.printf("flip: %s is now %s\n", CHANNEL[ch - 1].name, (core.flip() >> (ch - 1)) & 1 ? "flipped" : "normal");
  } else if (!strcmp(c, "reboot")) {
    Serial.println("reboot");
    Serial.flush();
    ESP.restart();
  } else {
    Serial.printf("unknown command '%s'; type help\n", c);
  }
}

static void console_poll(uint32_t now) {
  while (Serial.available() > 0) {
    const int ch = Serial.read();
    if (ch == '\r' || ch == '\n') {
      if (line_len) {
        line[line_len] = 0;
        line_len = 0;
        console_command(line, now);
      }
    } else if (line_len + 1 < sizeof line) {
      line[line_len++] = char(ch);
    }
  }
}

// BOOT is the GPIO0 strap: held through a reset it starts the ROM downloader instead, so the
// pairing press has to begin after power-up.
static void boot_poll(uint32_t now) {
  if (pairing.active || now > BOOT_PAIR_WINDOW_MS + BOOT_HOLD_MS) return;
  const bool down = digitalRead(x1pins::BOOT) == LOW;
  if (down && !boot_was_down) boot_down_since = now;
  boot_was_down = down;
  if (down && boot_down_since <= BOOT_PAIR_WINDOW_MS && now - boot_down_since >= BOOT_HOLD_MS) pairing_start(now);
}

// ---- Arduino entry points ----------------------------------------------------------------------

void setup() {
  pinMode(x1pins::NSLEEP, OUTPUT);
  digitalWrite(x1pins::NSLEEP, LOW);  // S3: drivers asleep until armed
  for (int ch = 0; ch < NUM_CH; ++ch) {
    pinMode(CHANNEL[ch].ph, OUTPUT);
    digitalWrite(CHANNEL[ch].ph, LOW);
  }
  pinMode(x1pins::NFAULT, INPUT);  // 10k pull-up on the board
  pinMode(x1pins::BOOT, INPUT);    // 10k pull-up on the board
  pinMode(x1pins::LED_STAT, OUTPUT);

  Serial.begin(115200);
  Serial.setTxTimeoutMs(0);  // never block the control loop when no host reads the console

  pwm_ok = pwm_begin();
  analogReadResolution(12);
  // 11 dB (ESP-IDF 5 calls it 12 dB), about 0-3.1 V: the default for every channel and for the
  // calibration curve. The first read attaches each pin at that setting.
  analogSetAttenuation(ADC_11db);
  for (uint8_t pin : ADC_PINS) analogReadMilliVolts(pin);
  ledcAttach(x1pins::LAMP1_PWM, LAMP_PWM_HZ, 8);
  ledcAttach(x1pins::LAMP2_PWM, LAMP_PWM_HZ, 8);
  ledcAttach(x1pins::BUZ_PWM, BUZZER_HZ, 8);
  ledcWrite(x1pins::LAMP1_PWM, 0);
  ledcWrite(x1pins::LAMP2_PWM, 0);
  ledcWrite(x1pins::BUZ_PWM, 0);

  load_settings();
  radio_ok = radio_begin();
  Serial.printf("X1 main board: MCPWM %s, radio %s, %s; type help\n", pwm_ok ? "ok" : "FAILED",
                radio_ok ? "ok" : "FAILED", paired ? "paired" : "not paired");
}

void loop() {
  const uint32_t now = millis();
  radio_poll(now);
  if (now - last_control >= CONTROL_PERIOD_MS) {
    last_control = now;
    core.update(now, read_sense());
    apply(core.outputs());
  }
  if (now - last_telemetry >= x1link::TELEMETRY_PERIOD_MS) {
    last_telemetry = now;
    send_telemetry();
  }
  if (pairing.active && now - pairing.since >= PAIR_WINDOW_MS) {
    pairing_end(false);
    Serial.println("pairing: timed out, previous pairing kept");
  }
  boot_poll(now);
  console_poll(now);
  if (log_period && now - last_log >= log_period) {
    last_log = now;
    print_status_line(now);
  }
  delay(1);
}

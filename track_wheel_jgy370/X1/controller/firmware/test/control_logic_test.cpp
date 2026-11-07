// Host tests for the X1 machine logic (SPEC C1 F4). No hardware: a Rig plays the handle (a packet
// every 20 ms) and the board (readings every 2 ms). Build and run with ./run_tests.sh.
#include "control_logic.h"

#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <iostream>

using namespace x1;
using namespace x1link;

namespace {

bool near(float a, float b, float tol = 2e-3f) { return std::fabs(a - b) <= tol; }
uint16_t isns_mV(Ch ch, float mA) { return uint16_t(std::lround(mA * CHANNEL[ch].r_ipropi_ohm / 1000.f)); }
uint16_t vbat_adc(float v) { return uint16_t(std::lround(v * 1000.f * x1pins::VBAT_DIVIDER)); }
float limit_mA(Ch ch) { return CHANNEL[ch].limit_a * 1000.f; }

struct Rig {
  Controller c;
  Sense s;
  Control in{};  // what the handle sends
  bool handle = true;
  uint32_t now, next_tx, last_sent = 0;
  uint16_t seq = 0;
  float mA[NUM_CH] = {};

  explicit Rig(uint32_t t0 = 1000, const Config &cfg = Config()) : c(cfg), now(t0), next_tx(t0) {
    in.speed_pct = SPEED_DEFAULT;
    battery(12.0f);
    s.v6_adc_mV = uint16_t(std::lround(6000.f * x1pins::V6_DIVIDER));
    c.update(now, s);  // power-up, no packet yet
  }
  void battery(float v) { s.vbat_adc_mV = vbat_adc(v); }
  Check send() {
    Control p = in;
    p.seq = seq++;
    encode(p);
    last_sent = now;
    return c.on_packet(reinterpret_cast<const uint8_t *>(&p), sizeof p, now);
  }
  void step() {
    now += 2;
    if (handle && int32_t(now - next_tx) >= 0) {
      send();
      next_tx = now + CONTROL_PERIOD_MS;
    }
    for (int ch = 0; ch < NUM_CH; ++ch) s.isns_mV[ch] = isns_mV(Ch(ch), mA[ch]);
    c.update(now, s);
  }
  void run(uint32_t ms) {
    for (uint32_t t = 0; t < ms; t += 2) step();
  }
  void centre() {
    in.lx = in.ly = in.rx = in.ry = 0;
    in.buttons = uint16_t(in.buttons & (BTN_LAMP1 | BTN_LAMP2));
  }
  void arm() {
    centre();
    handle = true;
    send();
    run(40);
    assert(c.armed() && c.outputs().nsleep);
  }
  void press(uint16_t bits) {  // a fresh button press, sent at once
    in.buttons = uint16_t(in.buttons | bits);
    send();
  }
  void release(uint16_t bits) {
    in.buttons = uint16_t(in.buttons & ~bits);
    send();
  }
  float d(Ch ch) const { return c.duty(ch); }
};

// The app's pad handler (excavator_app/client/main.js, move()): x right, screen y down, each
// component zeroed under 0.12; the right pad's horizontal is negated.
Axes app_pad(bool right, float x, float y) {
  Axes a;
  const float hx = (std::fabs(x) < 0.12f ? 0 : x) * (right ? -1.f : 1.f);
  const float vy = std::fabs(y) < 0.12f ? 0 : y;
  if (right) {
    a.bucket = hx;
    a.boom = vy;
  } else {
    a.slew = hx;
    a.stick = vy;
  }
  return a;
}

void test_packets() {
  const char *v = "123456789";
  assert(crc16(reinterpret_cast<const uint8_t *>(v), 9) == 0x29B1);

  Control p{};
  p.seq = 0x1234;
  p.lx = -1000;
  p.ly = 1000;
  p.rx = 5;
  p.ry = -5;
  p.speed_pct = 65;
  p.buttons = BTN_ESTOP | BTN_LAMP1;
  encode(p);
  const uint8_t *b = reinterpret_cast<const uint8_t *>(&p);
  assert(b[0] == 'X' && b[1] == VERSION && b[2] == CONTROL);
  assert(b[3] == 0x34 && b[4] == 0x12);  // little-endian seq
  assert(b[5] == 0x18 && b[6] == 0xFC);  // lx = -1000
  const uint16_t crc = crc16(b, sizeof p - 2);
  assert(b[16] == (crc & 0xFF) && b[17] == (crc >> 8));
  Control q;
  assert(validate(b, sizeof p, q) == Check::OK && q.seq == 0x1234 && q.lx == -1000 && q.buttons == p.buttons);
  assert(validate(b, sizeof p - 1, q) == Check::LENGTH);
  assert(validate(nullptr, sizeof p, q) == Check::LENGTH);
  uint8_t bad[sizeof p];
  for (size_t i = 0; i < sizeof p; ++i) {  // any single flipped bit is caught
    memcpy(bad, b, sizeof p);
    bad[i] ^= 0x04;
    assert(validate(bad, sizeof p, q) != Check::OK);
  }
  memcpy(bad, b, sizeof p);
  bad[7] ^= 1;
  assert(validate(bad, sizeof p, q) == Check::CRC);
  memcpy(bad, b, sizeof p);
  bad[0] = 'Y';
  assert(validate(bad, sizeof p, q) == Check::MAGIC);
  memcpy(bad, b, sizeof p);
  bad[1] = VERSION + 1;
  assert(validate(bad, sizeof p, q) == Check::VERSION);
  Control t = p;
  seal(t, TELEMETRY);
  assert(validate(reinterpret_cast<const uint8_t *>(&t), sizeof t, q) == Check::TYPE);
  struct Case { int16_t lx; uint8_t speed; uint16_t buttons; };
  const Case range[] = {{1001, 65, 0}, {-1001, 65, 0}, {0, 19, 0}, {0, 101, 0}, {0, 65, 0x0400}};
  for (const Case &k : range) {
    Control r = p;
    r.lx = k.lx;
    r.speed_pct = k.speed;
    r.buttons = k.buttons;
    encode(r);
    assert(validate(reinterpret_cast<const uint8_t *>(&r), sizeof r, q) == Check::RANGE);
  }
  assert(frame_type(b, sizeof p) == CONTROL && frame_type(bad, 4) == -1);

  Telemetry tl{};
  tl.vbat_mV = 11800;
  tl.ch[6].current_mA = 321;
  encode(tl);
  Telemetry tr;
  assert(validate(reinterpret_cast<const uint8_t *>(&tl), sizeof tl, tr) == Check::OK && tr.ch[6].current_mA == 321);

  PairRequest rq{};
  rq.nonce = 0xA5A5F00Du;
  encode(rq);
  PairRequest rq2;
  assert(validate(reinterpret_cast<const uint8_t *>(&rq), sizeof rq, rq2) == Check::OK && rq2.nonce == rq.nonce);
  PairAccept ac{};
  ac.nonce = rq.nonce;
  ac.wifi_channel = 1;
  for (int i = 0; i < 16; ++i) ac.lmk[i] = uint8_t(i * 17);
  encode(ac);
  PairAccept ac2;
  assert(validate(reinterpret_cast<const uint8_t *>(&ac), sizeof ac, ac2) == Check::OK && ac2.lmk[15] == 255);
  ac.wifi_channel = 14;
  encode(ac);
  assert(validate(reinterpret_cast<const uint8_t *>(&ac), sizeof ac, ac2) == Check::RANGE);
  PairConfirm cf{};
  cf.nonce = rq.nonce;
  cf.key_check = key_check(ac2.lmk);
  encode(cf);
  PairConfirm cf2;
  assert(validate(reinterpret_cast<const uint8_t *>(&cf), sizeof cf, cf2) == Check::OK && cf2.key_check == cf.key_check);
}

void test_channel_table() {
  for (int ch = 0; ch < NUM_CH; ++ch) {
    assert(CHANNEL[ch].limit_a == x1pins::CHANNELS[ch].limit_a);
    assert(CHANNEL[ch].r_ipropi_ohm == x1pins::CHANNELS[ch].r_ipropi_ohm);
    assert(std::strcmp(CHANNEL[ch].name, x1pins::CHANNELS[ch].name) == 0);
    assert(CHANNEL[ch].invert == (ch == TRACK_R));  // only the mirrored right track
    assert(CHANNEL[ch].vbat == (ch <= SWING));      // tracks and swing are on VBAT
  }
  assert(CHANNEL[TRACK_L].ramp_ms == 300 && CHANNEL[TRACK_R].ramp_ms == 300 && CHANNEL[SWING].ramp_ms == 400);
  for (int ch = BOOM_L; ch <= BUCKET; ++ch) assert(CHANNEL[ch].ramp_ms == 100);
}

void test_mapping_matches_app() {
  // The app's keyboard bindings (main.js `keys`) and the on-screen control each one stands for.
  struct Key { const char *key; float Axes::*axis; float value; int16_t lx, ly, rx, ry; uint16_t buttons; };
  const Key keys[] = {
      {"w (STICK OUT)", &Axes::stick, -1, 0, 1000, 0, 0, 0},
      {"s (STICK IN)", &Axes::stick, 1, 0, -1000, 0, 0, 0},
      {"a (slew L)", &Axes::slew, -1, -1000, 0, 0, 0, 0},
      {"d (slew R)", &Axes::slew, 1, 1000, 0, 0, 0, 0},
      {"ArrowUp (LOWER)", &Axes::boom, -1, 0, 0, 0, 1000, 0},
      {"ArrowDown (RAISE)", &Axes::boom, 1, 0, 0, 0, -1000, 0},
      {"ArrowLeft (CURL)", &Axes::bucket, 1, 0, 0, -1000, 0, 0},
      {"ArrowRight (OPEN)", &Axes::bucket, -1, 0, 0, 1000, 0, 0},
      {"q (left track up)", &Axes::left_track, 1, 0, 0, 0, 0, BTN_LEFT_FWD},
      {"z (left track down)", &Axes::left_track, -1, 0, 0, 0, 0, BTN_LEFT_REV},
      {"e (right track up)", &Axes::right_track, 1, 0, 0, 0, 0, BTN_RIGHT_FWD},
      {"c (right track down)", &Axes::right_track, -1, 0, 0, 0, 0, BTN_RIGHT_REV},
  };
  for (const Key &k : keys) {
    Control c{};
    c.lx = k.lx, c.ly = k.ly, c.rx = k.rx, c.ry = k.ry, c.buttons = k.buttons, c.speed_pct = 65;
    const Axes a = map_inputs(c, 0.12f);
    if (a.*(k.axis) != k.value) {
      std::printf("mapping mismatch for %s\n", k.key);
      assert(false);
    }
    const float total = a.boom * a.boom + a.stick * a.stick + a.bucket * a.bucket + a.slew * a.slew +
                        a.left_track * a.left_track + a.right_track * a.right_track;
    assert(total == 1.f);  // no other axis moves
  }
  // Every pad position, including the dead-band edges, gives the app's values. Pushing a stick
  // forward is the pad's top, so the handle's y is minus the screen's.
  const float pos[] = {-1.f, -0.5f, -0.13f, -0.12f, -0.11f, 0.f, 0.11f, 0.12f, 0.13f, 0.5f, 1.f};
  for (float x : pos)
    for (float y : pos)
      for (int right = 0; right < 2; ++right) {
        Control c{};
        c.speed_pct = 65;
        const int16_t hx = int16_t(std::lround(x * 1000)), hy = int16_t(std::lround(-y * 1000));
        if (right) c.rx = hx, c.ry = hy;
        else c.lx = hx, c.ly = hy;
        const Axes m = map_inputs(c, 0.12f), e = app_pad(right, x, y);
        assert(near(m.boom, e.boom, 1e-6f) && near(m.stick, e.stick, 1e-6f) && near(m.bucket, e.bucket, 1e-6f) &&
               near(m.slew, e.slew, 1e-6f));
      }
  assert(dead_band(0.1199f, 0.12f) == 0.f && dead_band(0.12f, 0.12f) == 0.12f && dead_band(-0.5f, 0.12f) == -0.5f);
}

void test_ramps_speed_and_direction() {
  Rig r;
  r.arm();
  // Track: 0.3 s full scale, at the 65 % default speed.
  r.press(BTN_LEFT_FWD | BTN_RIGHT_FWD);
  r.run(100);
  assert(near(r.d(TRACK_L), 100.f / 300.f) && near(r.d(TRACK_R), 100.f / 300.f));
  r.run(100);
  assert(r.d(TRACK_L) == 0.65f && r.d(TRACK_R) == 0.65f);
  // Forward on both: the mirrored right track gets the opposite PH.
  assert(r.c.outputs().ph[TRACK_L] == 1 && r.c.outputs().ph[TRACK_R] == 0);
  assert(near(r.c.outputs().en[TRACK_L], 0.65f) && r.c.outputs().nsleep);
  // Release: ramps down over 0.3 s of full scale too.
  r.release(BTN_LEFT_FWD | BTN_RIGHT_FWD);
  r.run(100);
  assert(near(r.d(TRACK_L), 0.65f - 100.f / 300.f));
  r.run(100);
  assert(r.d(TRACK_L) == 0.f && r.c.outputs().en[TRACK_L] == 0.f);  // EN 0 = brake
  // Reversal passes through zero.
  r.press(BTN_LEFT_FWD);
  r.run(200);
  r.release(BTN_LEFT_FWD);
  r.press(BTN_LEFT_REV);
  r.run(190);
  assert(r.d(TRACK_L) > 0.f);
  r.run(10);
  assert(r.d(TRACK_L) < 0.f && r.c.outputs().ph[TRACK_L] == 0);
  r.run(200);
  assert(r.d(TRACK_L) == -0.65f);
  r.release(BTN_LEFT_REV);
  r.run(200);
  // Actuators: 0.1 s full scale. Stick pulled back = STICK IN = +.
  r.in.ly = -1000;
  r.send();
  r.run(50);
  assert(near(r.d(STICK), 0.5f));
  r.run(20);
  assert(r.d(STICK) == 0.65f && r.c.outputs().ph[STICK] == 1);
  // Speed scales every axis.
  r.in.speed_pct = 100;
  r.send();
  r.run(50);
  assert(r.d(STICK) == 1.f);
  r.in.speed_pct = 20;
  r.send();
  r.run(100);
  assert(r.d(STICK) == 0.2f);
  // Dead band: 11 % is nothing, 12 % passes unscaled (as the app).
  r.in.speed_pct = 100;
  r.in.ly = 110;
  r.send();
  r.run(100);
  assert(r.d(STICK) == 0.f);
  r.in.ly = 120;
  r.send();
  r.run(100);
  assert(near(r.d(STICK), -0.12f, 1e-5f));
  // The swing ramps over 0.4 s.
  r.centre();
  r.in.lx = 1000;
  r.send();
  r.run(200);
  assert(near(r.d(SWING), 0.5f) && r.c.outputs().ph[SWING] == 1);
  r.run(200);
  assert(r.d(SWING) == 1.f);
}

void test_track_buttons() {
  Rig r;
  r.arm();
  r.in.speed_pct = 100;
  r.press(BTN_LEFT_FWD | BTN_RIGHT_FWD);
  r.run(400);
  assert(r.d(TRACK_L) == 1.f && r.d(TRACK_R) == 1.f);
  // Both buttons of the left pair: the left track stops (ramped); the right keeps going.
  r.press(BTN_LEFT_REV);
  r.run(400);
  assert(r.d(TRACK_L) == 0.f && r.d(TRACK_R) == 1.f);
  // Pivot turn: left up with right down. Both PH pins read 1 because the right is mirrored.
  r.release(BTN_LEFT_REV | BTN_RIGHT_FWD);
  r.press(BTN_RIGHT_REV);
  r.run(800);
  assert(r.d(TRACK_L) == 1.f && r.d(TRACK_R) == -1.f);
  assert(r.c.outputs().ph[TRACK_L] == 1 && r.c.outputs().ph[TRACK_R] == 1);
}

void test_powerup_arming() {
  Rig r;
  r.handle = false;
  r.run(1000);  // S3: nothing moves on boot, the drivers sleep
  assert(!r.c.armed() && !r.c.outputs().nsleep && !r.c.link());
  // A handle with a stick held does not arm the machine.
  r.in.ly = 500;
  r.handle = true;
  r.run(500);
  assert(r.c.link() && !r.c.armed() && !r.c.outputs().nsleep && r.d(STICK) == 0.f);
  r.in.ly = 0;
  r.in.buttons = BTN_LEFT_FWD;  // nor a held track button
  r.run(100);
  assert(!r.c.armed());
  r.in.buttons = BTN_LEFT_FWD | BTN_LEFT_REV;  // nor both (the track would stop, but it is not centred)
  r.run(100);
  assert(!r.c.armed());
  r.in.buttons = 0;
  r.run(40);
  assert(r.c.armed() && r.c.outputs().nsleep);
  for (int ch = 0; ch < NUM_CH; ++ch) assert(r.c.outputs().en[ch] == 0.f);  // armed, all braked
}

void test_link_loss() {
  Rig r;
  r.arm();
  r.in.speed_pct = 100;
  r.in.lx = 1000;   // swing right
  r.in.ly = -1000;  // stick in
  r.press(BTN_LEFT_FWD);
  r.run(500);
  assert(r.d(SWING) == 1.f && r.d(TRACK_L) == 1.f && r.d(STICK) == 1.f);
  r.handle = false;
  while (r.now - r.last_sent < 348) r.step();
  assert(r.c.link() && r.d(TRACK_L) == 1.f);  // 348 ms: still running
  r.step();                                    // 350 ms without a valid packet (S1)
  assert(!r.c.link() && !r.c.armed());
  assert(r.d(TRACK_L) == 0.f && r.d(STICK) == 0.f);   // the others stop at once
  assert(r.d(SWING) > 0.99f && r.d(SWING) < 1.f);     // the swing ramps down...
  assert(r.c.outputs().nsleep);                       // ...with the drivers still awake
  r.run(200);
  assert(near(r.d(SWING), 0.495f));
  r.run(196);
  assert(r.d(SWING) > 0.f && r.c.outputs().nsleep);
  r.step();  // 0.4 s after the loss
  assert(r.d(SWING) == 0.f && !r.c.outputs().nsleep);
  // The handle comes back with the inputs still held: stays disarmed until they are centred.
  r.handle = true;
  r.run(200);
  assert(r.c.link() && !r.c.armed() && r.d(SWING) == 0.f && r.d(TRACK_L) == 0.f);
  r.centre();
  r.run(40);
  assert(r.c.armed());
  // A corrupt packet does not feed the watchdog.
  r.handle = false;
  Control p = r.in;
  p.seq = r.seq++;
  encode(p);
  reinterpret_cast<uint8_t *>(&p)[8] ^= 0x10;
  const uint32_t t_last = r.last_sent;
  while (r.now - t_last < 300) r.step();
  assert(r.c.on_packet(reinterpret_cast<const uint8_t *>(&p), sizeof p, r.now) == Check::CRC);
  while (r.now - t_last < 350) r.step();
  assert(!r.c.link() && r.c.rx_bad() == 1);
}

void test_sequence() {
  Rig r;
  r.arm();
  const uint16_t s = r.seq;
  assert(r.send() == Check::OK);
  r.seq = s;  // the same packet again
  assert(r.send() == Check::SEQUENCE);
  r.seq = uint16_t(s - 5);
  assert(r.send() == Check::SEQUENCE);
  r.seq = uint16_t(s + 4);  // three lost
  assert(r.send() == Check::OK && r.c.rx_lost() == 3);
  r.run(100);
  // After a link loss any sequence is taken: the handle may have restarted.
  r.handle = false;
  r.run(400);
  assert(!r.c.link());
  r.seq = 0;
  assert(r.send() == Check::OK && r.c.link());
}

void test_estop_resume() {
  Rig r;
  r.arm();
  r.in.speed_pct = 100;
  r.in.lx = 1000;
  r.press(BTN_RIGHT_FWD);
  r.run(500);
  r.press(BTN_ESTOP);  // S2
  r.step();
  assert(r.c.estop() && !r.c.armed());
  assert(r.d(TRACK_R) == 0.f && r.d(SWING) > 0.99f);  // swing ramps as in S1
  r.run(400);
  assert(r.d(SWING) == 0.f && !r.c.outputs().nsleep);
  // The red button released: still latched.
  r.release(BTN_ESTOP);
  r.run(200);
  assert(r.c.estop() && !r.c.armed());
  // RESUME with a stick still held is refused.
  r.release(BTN_RIGHT_FWD);
  r.press(BTN_RESUME);
  r.run(100);
  assert(r.c.estop());
  // Centred, but RESUME still held from before: not a fresh press.
  r.in.lx = 0;
  r.run(100);
  assert(r.c.estop());
  r.release(BTN_RESUME);
  r.run(40);
  r.press(BTN_RESUME);
  r.run(40);
  assert(!r.c.estop() && r.c.armed());
  r.release(BTN_RESUME);
  // E-stop and RESUME in one packet: the stop wins.
  r.press(BTN_ESTOP | BTN_RESUME);
  r.run(40);
  assert(r.c.estop());
  // RESUME held through a new E-stop does not clear it.
  r.release(BTN_ESTOP);
  r.run(40);
  assert(r.c.estop());
  r.release(BTN_RESUME);
  r.press(BTN_RESUME);
  r.run(40);
  assert(!r.c.estop() && r.c.armed());
  r.release(BTN_RESUME);
  // The latch survives a link loss.
  r.press(BTN_ESTOP);
  r.release(BTN_ESTOP);
  r.handle = false;
  r.run(1000);
  r.handle = true;
  r.run(100);
  assert(r.c.estop() && !r.c.armed());
  // A RESUME already held when the link returns is not a press either.
  r.handle = false;
  r.run(400);
  r.in.buttons = BTN_RESUME;
  r.handle = true;
  r.run(100);
  assert(r.c.estop());
}

void test_stall_cutout() {
  Rig r;
  r.arm();
  r.in.speed_pct = 100;
  const float high = 0.95f * limit_mA(TRACK_L);
  r.mA[TRACK_L] = high;
  r.run(100);  // the current filter settles
  r.press(BTN_LEFT_FWD);
  r.step();  // first non-zero duty: the 2 s start here
  r.run(1996);
  assert(!r.c.stall_cut(TRACK_L) && r.d(TRACK_L) == 1.f);
  r.step();
  r.step();  // 2 s at >= 90 % of the limit (S4)
  assert(r.c.stall_cut(TRACK_L) && r.d(TRACK_L) == 0.f);
  assert(r.c.faults() & F_STALL);
  r.mA[TRACK_L] = 0;
  r.run(2000);  // stays off while the button is held
  assert(r.c.stall_cut(TRACK_L) && r.d(TRACK_L) == 0.f && r.c.armed());
  Telemetry t;
  r.c.make_telemetry(t, -60);
  assert(t.ch[TRACK_L].flags & CH_STALL_CUT);
  r.release(BTN_LEFT_FWD);  // input back to centre
  r.step();
  assert(!r.c.stall_cut(TRACK_L));
  r.press(BTN_LEFT_FWD);
  r.run(400);
  assert(r.d(TRACK_L) == 1.f);
  // A short dip restarts the timer.
  r.mA[TRACK_L] = high;
  r.run(1500);
  r.mA[TRACK_L] = 0;
  r.run(10);
  r.mA[TRACK_L] = high;
  r.run(1500);
  assert(!r.c.stall_cut(TRACK_L));
  r.run(600);
  assert(r.c.stall_cut(TRACK_L));
  // Just under 90 % never trips.
  r.release(BTN_LEFT_FWD);
  r.mA[TRACK_L] = 0.89f * limit_mA(TRACK_L);
  r.run(100);
  r.press(BTN_LEFT_FWD);
  r.run(5000);
  assert(!r.c.stall_cut(TRACK_L) && r.d(TRACK_L) == 1.f);
  // The swing (12 V) is covered; the 6 V actuators are not (they have their own PTCs).
  r.mA[SWING] = 0.95f * limit_mA(SWING);
  r.mA[STICK] = 0.95f * limit_mA(STICK);
  r.in.lx = 1000;
  r.in.ly = -1000;
  r.send();
  r.run(2500);
  assert(r.c.stall_cut(SWING) && r.d(SWING) == 0.f);
  assert(!r.c.stall_cut(STICK) && r.d(STICK) == 1.f);
}

void test_low_battery() {
  Rig r;
  r.arm();
  r.in.speed_pct = 100;
  r.press(BTN_LEFT_FWD);
  r.run(400);
  // A 0.5 s sag to 8 V under load trips nothing.
  r.battery(8.0f);
  r.run(500);
  r.battery(12.0f);
  r.run(100);
  assert(!r.c.battery_warn() && !r.c.battery_stop() && r.d(TRACK_L) == 1.f);
  r.run(10000);
  // A step to 9.0 V: warning after the 2 s filter crosses 10.5 V (~1.4 s), stop at 9.6 V (~3.2 s).
  r.battery(9.0f);
  r.run(1200);
  assert(!r.c.battery_warn());
  r.run(400);
  assert(r.c.battery_warn() && !r.c.battery_stop() && r.c.armed() && r.d(TRACK_L) == 1.f);
  assert(r.c.faults() & F_BATTERY_WARN);
  r.run(1400);  // 3.0 s
  assert(!r.c.battery_stop() && r.d(TRACK_L) == 1.f);
  r.run(500);   // 3.5 s
  assert(r.c.battery_stop() && !r.c.armed() && r.d(TRACK_L) == 0.f);
  assert(r.c.faults() & F_BATTERY_LOW);
  Telemetry t;
  r.c.make_telemetry(t, 0);
  assert(t.vbat_mV > 9000 && t.vbat_mV < 9600 && (t.faults & F_BATTERY_LOW));
  // The resting pack recovers a little: still stopped below 10.5 V.
  r.release(BTN_LEFT_FWD);
  r.battery(10.3f);
  r.run(10000);
  assert(r.c.battery_stop() && !r.c.armed());
  // A charged pack clears it; the inputs are centred, so the machine arms again.
  r.battery(12.4f);
  r.run(10000);
  assert(!r.c.battery_stop() && !r.c.battery_warn() && r.c.armed());
}

void test_nfault() {
  Rig r;
  r.arm();
  r.press(BTN_LEFT_FWD);
  r.run(400);
  // A 2-sample glitch is ignored.
  r.s.nfault_low = true;
  r.step();
  r.step();
  r.s.nfault_low = false;
  r.step();
  assert(!r.c.driver_fault() && r.c.armed());
  // Low for 4 ms: S6 stops everything and reports.
  r.s.nfault_low = true;
  r.run(6);
  assert(r.c.driver_fault() && !r.c.armed() && r.d(TRACK_L) == 0.f);
  assert((r.c.faults() & F_DRIVER) && (r.c.faults() & F_DRIVER_LINE));
  // RESUME while the line is still low does not clear it.
  r.release(BTN_LEFT_FWD);
  r.press(BTN_RESUME);
  r.run(40);
  assert(r.c.driver_fault());
  r.release(BTN_RESUME);
  r.s.nfault_low = false;
  r.run(40);
  assert(r.c.driver_fault() && !r.c.armed());  // latched
  r.press(BTN_RESUME);
  r.run(40);
  assert(!r.c.driver_fault() && r.c.armed());
  // nFAULT low just after the drivers wake (the first 5 ms) is ignored.
  Rig w;
  w.handle = false;
  w.run(100);
  w.centre();
  w.send();
  w.step();  // arms: nSLEEP rises here
  assert(w.c.outputs().nsleep);
  w.s.nfault_low = true;
  w.step();
  w.step();
  w.s.nfault_low = false;
  w.run(20);
  assert(!w.c.driver_fault() && w.c.armed());
}

void test_boom_balance() {
  Rig r;
  r.arm();
  r.in.speed_pct = 100;
  r.mA[BOOM_L] = r.mA[BOOM_R] = 120;
  r.run(100);
  r.in.ry = -1000;  // right stick back: RAISE = boom +
  r.send();
  r.run(1000);
  assert(r.d(BOOM_L) == 1.f && r.d(BOOM_R) == 1.f && r.c.boom_trim(0) == 0.f && !r.c.boom_fault());
  assert(r.c.outputs().ph[BOOM_L] == 1 && r.c.outputs().ph[BOOM_R] == 1);  // same command to both
  // The left side draws 35 mA more: it is ahead, so its duty is trimmed down slowly.
  r.mA[BOOM_L] = 155;
  r.run(1000);
  assert(near(r.c.boom_trim(0), 0.05f, 0.004f) && r.c.boom_trim(1) == 0.f);
  assert(near(r.d(BOOM_L), 1.f - r.c.boom_trim(0), 1e-4f) && r.d(BOOM_R) == 1.f);
  r.run(4000);
  assert(r.c.boom_trim(0) == 0.15f && near(r.d(BOOM_L), 0.85f, 1e-4f));  // capped at 15 %
  assert(!r.c.boom_fault());  // 35 mA is under the 40 mA fault level
  // Within the 10 mA tolerance the trim holds.
  r.mA[BOOM_R] = 150;
  r.run(1000);
  assert(r.c.boom_trim(0) == 0.15f);
  // Now the right side leads: the left trim is given back first.
  r.mA[BOOM_R] = 175;
  r.run(1000);
  assert(near(r.c.boom_trim(0), 0.10f, 0.004f) && r.c.boom_trim(1) == 0.f);
  // Reversing starts the trims afresh.
  r.in.ry = 1000;  // LOWER
  r.send();
  r.run(300);
  assert(r.c.boom_trim(0) == 0.f && r.c.boom_trim(1) == 0.f && r.d(BOOM_L) == -1.f);
}

void test_boom_imbalance_fault() {
  Rig r;
  r.arm();
  r.in.speed_pct = 100;
  r.mA[BOOM_L] = 200;
  r.mA[BOOM_R] = 120;
  r.run(100);
  r.in.ry = -1000;
  r.press(BTN_LEFT_FWD);  // drive a track at the same time
  r.run(3200);            // judged from 0.3 s: 2.9 s over 40 mA
  assert(!r.c.boom_fault() && r.d(BOOM_R) == 1.f);
  r.run(200);
  assert(r.c.boom_fault());
  assert(r.d(BOOM_L) == 0.f && r.d(BOOM_R) == 0.f);  // the boom stops at once...
  assert(r.d(TRACK_L) == 1.f && r.c.armed());  // ...the rest keeps working
  Telemetry t;
  r.c.make_telemetry(t, 0);
  assert((t.faults & F_BOOM) && (t.ch[BOOM_L].flags & CH_BOOM_CUT) && (t.ch[BOOM_R].flags & CH_BOOM_CUT));
  r.run(2000);
  assert(r.d(BOOM_L) == 0.f);  // still held off
  // RESUME (all centred) clears it.
  r.centre();
  r.send();
  r.press(BTN_RESUME);
  r.run(40);
  r.release(BTN_RESUME);
  assert(!r.c.boom_fault());
  r.mA[BOOM_L] = 120;
  r.in.ry = -1000;
  r.send();
  r.run(500);
  assert(r.d(BOOM_L) == 1.f && r.d(BOOM_R) == 1.f);
}

void test_boom_end_stops() {
  Rig r;
  r.arm();
  r.in.speed_pct = 100;
  r.mA[BOOM_L] = 140;
  r.mA[BOOM_R] = 120;
  r.run(100);
  r.in.ry = -1000;
  r.send();
  r.run(2000);
  assert(r.c.boom_trim(0) > 0.f);
  // The left end stop opens: its current drops to zero. The right side is driven on, untrimmed.
  r.mA[BOOM_L] = 0;
  r.run(5000);
  assert(!r.c.boom_fault() && r.c.boom_trim(0) == 0.f && r.d(BOOM_R) == 1.f);
  Telemetry t;
  r.c.make_telemetry(t, 0);
  assert((t.ch[BOOM_L].flags & CH_AT_END) && !(t.ch[BOOM_R].flags & CH_AT_END));
  // Then the right one stops too: both level at the end, no fault while the stick is held.
  r.mA[BOOM_R] = 0;
  r.run(15000);
  assert(!r.c.boom_fault() && r.c.boom_trim(0) == 0.f && r.c.boom_trim(1) == 0.f);
  // One side at its end and the other never arriving: a fault after 10 s.
  Rig e;
  e.arm();
  e.in.speed_pct = 100;
  e.mA[BOOM_L] = 0;
  e.mA[BOOM_R] = 120;
  e.run(100);
  e.in.ry = -1000;
  e.send();
  e.run(10200);
  assert(!e.c.boom_fault());
  e.run(200);
  assert(e.c.boom_fault() && e.d(BOOM_R) == 0.f);
}

void test_boom_resync() {
  Rig r;
  r.arm();
  r.mA[BOOM_L] = r.mA[BOOM_R] = 120;
  r.run(100);
  // One press drives both sides to the retract end stops (boom down) at the movement speed.
  r.press(BTN_RESYNC);
  r.run(40);
  r.release(BTN_RESYNC);
  r.run(1000);
  assert(r.c.resync_active() && r.d(BOOM_L) == -0.65f && r.d(BOOM_R) == -0.65f);
  assert(r.c.state_bits() & ST_RESYNC);
  assert(r.c.outputs().ph[BOOM_L] == 0 && r.c.outputs().ph[BOOM_R] == 0);
  // The imbalance check is off during a re-sync (the sides are expected to differ).
  r.mA[BOOM_L] = 200;
  r.run(4000);
  assert(!r.c.boom_fault() && r.c.resync_active());
  // Left reaches its end: the right keeps going at full (untrimmed) duty.
  r.mA[BOOM_L] = 0;
  r.run(15000);
  assert(r.c.resync_active() && r.d(BOOM_R) == -0.65f && !r.c.boom_fault());
  // Right reaches its end: done, the boom stops.
  r.mA[BOOM_R] = 0;
  r.run(100);
  assert(!r.c.resync_active());
  r.run(100);
  assert(r.d(BOOM_L) == 0.f && r.d(BOOM_R) == 0.f && !r.c.boom_fault() && !r.c.resync_failed());
  // A boom input cancels it, and the boom follows the stick.
  r.mA[BOOM_L] = r.mA[BOOM_R] = 120;
  r.press(BTN_RESYNC);
  r.run(40);
  r.release(BTN_RESYNC);
  r.run(500);
  assert(r.c.resync_active());
  r.in.ry = -1000;
  r.send();
  r.run(300);
  assert(!r.c.resync_active() && r.d(BOOM_L) == 0.65f);
  // A second press cancels it.
  r.centre();
  r.send();
  r.run(100);
  r.press(BTN_RESYNC);
  r.run(40);
  r.release(BTN_RESYNC);
  r.run(500);
  r.press(BTN_RESYNC);
  r.run(200);
  assert(!r.c.resync_active() && r.d(BOOM_L) == 0.f);
  r.release(BTN_RESYNC);
  // It gives up after 120 s and reports it.
  r.press(BTN_RESYNC);
  r.run(40);
  r.release(BTN_RESYNC);
  r.run(119800);
  assert(r.c.resync_active());
  r.run(400);
  assert(!r.c.resync_active() && r.c.resync_failed() && (r.c.faults() & F_RESYNC_TIMEOUT));
  r.run(200);
  assert(r.d(BOOM_L) == 0.f);
  // Pressing it again clears a boom fault and starts over (re-syncing is the remedy).
  Rig f;
  f.arm();
  f.in.speed_pct = 100;
  f.mA[BOOM_L] = 200;
  f.mA[BOOM_R] = 120;
  f.in.ry = -1000;
  f.send();
  f.run(4000);
  assert(f.c.boom_fault());
  f.centre();
  f.send();
  f.press(BTN_RESYNC);
  f.run(40);
  assert(!f.c.boom_fault() && f.c.resync_active() && f.d(BOOM_L) < 0.f);
  // A link loss ends it.
  f.handle = false;
  f.run(400);
  f.release(BTN_RESYNC);
  f.handle = true;
  f.run(100);
  assert(!f.c.resync_active() && f.d(BOOM_L) == 0.f);
}

void test_millis_wrap() {
  // Ramps, the link watchdog and the stall timer straddling the 32-bit wrap.
  Rig r(0xFFFFFF00u);
  r.arm();
  r.in.speed_pct = 100;
  r.press(BTN_LEFT_FWD);
  r.run(150);
  assert(near(r.d(TRACK_L), 0.5f));
  r.run(150);
  assert(r.now < 0x1000u && r.c.link() && r.d(TRACK_L) == 1.f);  // past the wrap
  Rig s(0xFFFFFFFFu - 1000u);
  s.arm();
  s.in.speed_pct = 100;
  s.mA[TRACK_L] = 0.95f * limit_mA(TRACK_L);
  s.run(100);
  s.press(BTN_LEFT_FWD);
  s.step();
  s.run(1996);
  assert(s.now < 0x1000u && !s.c.stall_cut(TRACK_L));
  s.run(4);
  assert(s.c.stall_cut(TRACK_L));
  Rig l(0xFFFFFFFFu - 200u);
  l.arm();
  l.handle = false;
  const uint32_t t_last = l.last_sent;
  while (l.now - t_last < 348) l.step();
  assert(l.now < 0x1000u && l.c.link());
  l.step();
  assert(!l.c.link() && !l.c.armed());
  // 2^32 ms later the counter shows "100 ms since the last packet" again: still lost.
  l.c.update(t_last + 100, l.s);
  assert(!l.c.link() && !l.c.armed() && !l.c.outputs().nsleep);
}

void test_telemetry() {
  Rig r;
  r.arm();
  r.in.speed_pct = 100;
  r.mA[STICK] = 120;
  r.in.ly = 1000;  // STICK OUT
  r.in.buttons = BTN_LAMP2;
  r.send();
  r.run(1000);
  Telemetry t;
  r.c.make_telemetry(t, -57);
  Telemetry u;
  assert(validate(reinterpret_cast<const uint8_t *>(&t), sizeof t, u) == Check::OK);
  assert(u.state == (ST_ARMED | ST_LINK) && u.faults == 0 && u.rssi_dBm == -57);
  assert(u.vbat_mV > 11950 && u.vbat_mV < 12050 && u.v6_mV > 5950 && u.v6_mV < 6050);
  assert(u.ch[STICK].duty_pct == -100 && !(u.ch[STICK].flags & CH_PH));
  assert(u.ch[STICK].current_mA >= 119 && u.ch[STICK].current_mA <= 121);
  assert(u.rx_per_s >= 48 && u.rx_per_s <= 53 && u.ack_seq == uint16_t(r.seq - 1));  // 50/s plus manual sends
  Telemetry v;
  r.c.make_telemetry(v, -57);
  assert(uint16_t(v.seq - t.seq) == 1);
  // Lamps follow the handle and hold through a link loss; the horn needs the link.
  assert(!r.c.outputs().lamp[0] && r.c.outputs().lamp[1]);
  r.in.buttons = BTN_LAMP1 | BTN_HORN;
  r.send();
  r.step();
  assert(r.c.outputs().lamp[0] && !r.c.outputs().lamp[1] && r.c.outputs().buzzer);
  r.handle = false;
  r.run(400);
  assert(r.c.outputs().lamp[0] && !r.c.outputs().buzzer);
  // 6 V rail low with the battery up is reported.
  r.s.v6_adc_mV = uint16_t(std::lround(4000.f * x1pins::V6_DIVIDER));
  r.step();
  assert(r.c.faults() & F_RAIL_6V_LOW);
  // Current offsets are removed before scaling.
  r.c.set_current_offset(STICK, 50.f);
  r.run(200);
  assert(near(r.c.current_mA(STICK), 120.f - 1000.f * 50.f / CHANNEL[STICK].r_ipropi_ohm, 0.6f));
  char buf[2048];
  const size_t n = r.c.describe(buf, sizeof buf);
  assert(n > 200 && n < sizeof buf && std::strstr(buf, "Boom right") && std::strstr(buf, "battery"));
  assert(r.c.describe(buf, 40) == 39);  // truncates safely
}

void test_travel_alarm() {
  Rig r;
  r.arm();
  r.press(BTN_RIGHT_FWD);
  int on = 0, n = 0;
  for (int i = 0; i < 800; ++i, ++n) {  // 1.6 s
    r.step();
    on += r.c.outputs().buzzer;
  }
  assert(on > n / 3 && on < 2 * n / 3);  // beeping while a track moves
  r.release(BTN_RIGHT_FWD);
  r.run(400);
  on = 0;
  for (int i = 0; i < 800; ++i) {
    r.step();
    on += r.c.outputs().buzzer;
  }
  assert(on == 0);
}

void test_bench_drive() {
  Rig r;
  r.arm();
  assert(r.c.bench_drive(TRACK_L, 0.5f, 1000, r.now) != nullptr);  // not with a handle
  r.handle = false;
  r.run(400);
  assert(r.c.bench_drive(TRACK_L, 0.5f, 1000, r.now) == nullptr);
  r.run(400);
  assert(r.c.bench_active() && r.d(TRACK_L) == 0.5f && r.c.outputs().nsleep);
  r.run(700);
  assert(!r.c.bench_active() && r.d(TRACK_L) == 0.f);
  // Channels 4 and 5 drive the boom pair together.
  r.mA[BOOM_L] = r.mA[BOOM_R] = 120;
  assert(r.c.bench_drive(BOOM_L, -0.4f, 2000, r.now) == nullptr);
  r.run(500);
  assert(r.d(BOOM_L) == -0.4f && r.d(BOOM_R) == -0.4f);
  r.c.bench_stop();
  r.step();
  assert(r.d(BOOM_L) == 0.f);
  // The stall cut-out still applies, and ends the bench run.
  r.mA[SWING] = 0.95f * limit_mA(SWING);
  assert(r.c.bench_drive(SWING, 1.f, 10000, r.now) == nullptr);
  r.run(2600);
  assert(r.c.stall_cut(SWING) == false && !r.c.bench_active() && r.d(SWING) == 0.f);
  // Refused with the E-stop latched or the battery low.
  r.handle = true;
  r.press(BTN_ESTOP);
  r.handle = false;
  r.run(400);
  assert(r.c.bench_drive(TRACK_L, 0.5f, 1000, r.now) != nullptr);
  Rig b;
  b.battery(9.0f);
  b.handle = false;
  b.c = Controller();
  b.c.update(b.now, b.s);
  assert(b.c.battery_stop() && b.c.bench_drive(TRACK_L, 0.5f, 1000, b.now) != nullptr);
}

void test_parsers_and_flip() {
  uint8_t mac[6], key[16];
  assert(parse_mac("24:6f:28:AB:cd:EF", mac) && mac[0] == 0x24 && mac[5] == 0xEF);
  assert(parse_mac("24-6f-28-ab-cd-ef", mac));
  assert(!parse_mac("24:6f:28:ab:cd", mac) && !parse_mac("24:6f:28:ab:cd:eg", mac) && !parse_mac(nullptr, mac));
  assert(parse_hex("00112233445566778899aabbccddeeff", key, 16) && key[1] == 0x11 && key[15] == 0xFF);
  assert(!parse_hex("00112233445566778899aabbccddeef", key, 16) && !parse_hex("zz112233445566778899aabbccddeeff", key, 16));
  // A channel flipped on the console inverts its PH.
  Rig r;
  r.c.set_flip(1u << STICK);
  r.arm();
  r.in.ly = -1000;  // STICK IN, + duty
  r.send();
  r.run(100);
  assert(r.d(STICK) > 0.f && r.c.outputs().ph[STICK] == 0);
}

}  // namespace

int main() {
  test_packets();
  test_channel_table();
  test_mapping_matches_app();
  test_ramps_speed_and_direction();
  test_track_buttons();
  test_powerup_arming();
  test_link_loss();
  test_sequence();
  test_estop_resume();
  test_stall_cutout();
  test_low_battery();
  test_nfault();
  test_boom_balance();
  test_boom_imbalance_fault();
  test_boom_end_stops();
  test_boom_resync();
  test_millis_wrap();
  test_telemetry();
  test_travel_alarm();
  test_bench_drive();
  test_parsers_and_flip();
  std::cout << "PASS: packets/CRC, channel table, app mapping signs, ramps, speed, dead band, track buttons, "
               "power-up arming, link loss, sequence, E-stop/RESUME, stall cut-out, low battery, nFAULT, "
               "boom balance/imbalance/end stops/re-sync, millis wrap, telemetry, travel alarm, bench drive, "
               "parsers\n";
}

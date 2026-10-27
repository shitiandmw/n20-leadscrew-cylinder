// Arduino Nano/Uno ATmega328P, 5 V logic; example 6 V motor supply.
// Actuator V5. Circuit: electronics/schematic.pdf (sheet 2, U6); pin numbers checked by build_schematic.py.
// Copy protection_logic.h into this sketch directory before compiling.
// Hall outputs gate each direction through a 74HC08 independently of firmware.
// Fit 10k pulldowns at BOTH HC08 command inputs and both DRV8833 AIN inputs.
#include "protection_logic.h"

constexpr uint8_t EXTEND_BUTTON=2, RETRACT_BUTTON=3, RESET_BUTTON=4;
constexpr uint8_t DRIVER_FAULT=7, DRIVER_SLEEP=8, IN1=9, IN2=10;
constexpr uint8_t CURRENT=A0, FAULT_LED=13, ALLOW_EXTEND=5, ALLOW_RETRACT=6;
constexpr uint8_t PWM_DUTY=180; // Commission at low voltage/load; tune after measuring.
constexpr uint16_t ADC_REFERENCE_MV=5000; // Measure the actual Nano 5 V rail.
constexpr uint16_t ACS_SENSITIVITY_MV_A=185; // ACS712-05B ONLY (5 A version).
Protection protection;
uint16_t zero_adc=512;

void coast() {
  analogWrite(IN1,0); analogWrite(IN2,0); digitalWrite(DRIVER_SLEEP,LOW);
}
void setup() {
  pinMode(IN1,OUTPUT); pinMode(IN2,OUTPUT); pinMode(DRIVER_SLEEP,OUTPUT);
  coast(); pinMode(FAULT_LED,OUTPUT);
  pinMode(EXTEND_BUTTON,INPUT_PULLUP); pinMode(RETRACT_BUTTON,INPUT_PULLUP);
  pinMode(RESET_BUTTON,INPUT_PULLUP); pinMode(DRIVER_FAULT,INPUT_PULLUP);
  // NO internal pullups: 47k pulldowns at the controller must detect a broken signal wire.
  pinMode(ALLOW_EXTEND,INPUT); pinMode(ALLOW_RETRACT,INPUT);
  delay(100);
  uint32_t total=0;
  for (int i=0;i<256;i++) { total += analogRead(CURRENT); delay(1); }
  zero_adc=total/256;
  if (zero_adc<409 || zero_adc>614) protection.fault=Fault::Sensor;
}
void loop() {
  uint32_t total=0;
  for (int i=0;i<16;i++) total += analogRead(CURRENT);
  uint16_t sample=total/16;
  bool sensor_ok=sample>102 && sample<921 && zero_adc>=409 && zero_adc<=614;
  int delta=int(sample)-int(zero_adc); if(delta<0) delta=-delta;
  uint16_t current_mA=uint32_t(delta)*ADC_REFERENCE_MV*1000UL/(1023UL*ACS_SENSITIVITY_MV_A);
  bool ext=digitalRead(EXTEND_BUTTON)==LOW, ret=digitalRead(RETRACT_BUTTON)==LOW;
  bool allowExt=digitalRead(ALLOW_EXTEND)==HIGH, allowRet=digitalRead(ALLOW_RETRACT)==HIGH;
  sensor_ok=sensor_ok && (allowExt || allowRet);
  int8_t request=ext==ret?0:(ext?1:-1);
  if ((request>0&&!allowExt)||(request<0&&!allowRet)) request=0;
  // DRV8833 nFAULT may be low in sleep. Only evaluate it while enabled.
  bool driver_ok=protection.direction==0 || digitalRead(DRIVER_FAULT)==HIGH;
  int8_t dir=protection.update(millis(),request,current_mA,driver_ok,sensor_ok,digitalRead(RESET_BUTTON)==LOW);
  static int8_t previous=0;
  if (!dir) coast();
  else {
    if (!previous) {digitalWrite(DRIVER_SLEEP,HIGH); delay(2);} // >=1 ms wake-up
    if (dir>0) {analogWrite(IN2,0); analogWrite(IN1,PWM_DUTY);}
    else {analogWrite(IN1,0); analogWrite(IN2,PWM_DUTY);}
  }
  previous=dir;
  digitalWrite(FAULT_LED,protection.fault!=Fault::None);
  delay(2);
}

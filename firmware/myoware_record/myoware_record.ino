/*
  MyoWare 2.0 Wireless Shield - RECORD mode for the TrueRehab-RF recorder (recorder/record.py).

  The demo sketch (firmware/myoware_demo) is for watching; this one is for recording. It sends
  every sample with the ESP32's own microsecond clock, so the recorder can undo Bluetooth jitter:

    E,<micros>,<raw>,<env>                 1000 per second  (sEMG)
    I,<micros>,ax,ay,az,gx,gy,gz           200 per second   (MPU6050, only if USE_IMU is 1)
    # ...                                  comments (start-up info), ignored by the recorder

  Why RAW too: the envelope (ENV) shows how hard the muscle works, but the classic fatigue sign,
  a drop in the signal's median frequency, needs the raw signal sampled at >= 1 kHz.
  IMU values are raw int16: accel 16384 per g (+-2 g), gyro 131 per deg/s (+-250 deg/s).

  Hardware: MyoWare 2.0 Muscle Sensor + MyoWare 2.0 Wireless Shield (ESP32-WROOM).
    RAW -> GPIO36, ENV -> GPIO39 (pin numbers used directly, not A-names).
  Arduino IDE: "esp32" boards package (Espressif), board "ESP32 Dev Module".

  SAFETY (SparkFun's warning): do not have the shield on a person while USB-C is plugged in
  (programming or charging). For recordings on a person: unplug USB, run on the battery, and
  record over Bluetooth ("TrueRehab-MyoWare"). USB at 921600 baud is for bench tests only.

  Compiles (2026-11-04, arduino-cli, esp32:esp32:esp32, USE_IMU 0 and 1: 83% flash, 13% RAM).
  NOT YET RUN on the board.
*/

#include "BluetoothSerial.h"
#include <Wire.h>

#define USE_IMU 0  // 1 = read an MPU6050 on I2C (set the pins below to the ones you wired)

BluetoothSerial SerialBT;
const char *BT_NAME = "TrueRehab-MyoWare";

const uint8_t RAW_PIN = 36;
const uint8_t ENV_PIN = 39;
const uint8_t LED_PIN = 13;
const unsigned long SAMPLE_US = 1000;  // 1 kHz
const uint8_t IMU_EVERY = 5;           // 1 kHz / 5 = 200 Hz

#if USE_IMU
const int SDA_PIN = 21;  // ESP32 default I2C pins; change if the shield routes them elsewhere
const int SCL_PIN = 22;
const uint8_t MPU_ADDR = 0x68;
bool imuOk = false;
#endif

// Lines are collected and sent in batches: far fewer Bluetooth packets than one per sample.
char batch[2048];
size_t batchLen = 0;
unsigned long lastSendUs = 0;
unsigned long nextSampleUs = 0;
uint8_t tick = 0;
bool hadClient = false;

void sendBatch() {
  if (batchLen == 0) return;
  Serial.write((const uint8_t *)batch, batchLen);
  if (SerialBT.hasClient()) SerialBT.write((const uint8_t *)batch, batchLen);
  batchLen = 0;
  lastSendUs = micros();
}

void addLine(const char *line) {
  size_t n = strlen(line);
  if (batchLen + n + 1 > sizeof(batch)) sendBatch();
  memcpy(batch + batchLen, line, n);
  batchLen += n;
  batch[batchLen++] = '\n';
}

void sayHello() {
  char buf[160];
  snprintf(buf, sizeof(buf), "# truerehab-record v1 emg_hz=1000 raw_pin=%d env_pin=%d imu=%s",
           RAW_PIN, ENV_PIN,
#if USE_IMU
           imuOk ? "mpu6050_200hz" : "not_found"
#else
           "off"
#endif
  );
  addLine(buf);
  addLine("# E,micros,raw,env | I,micros,ax,ay,az,gx,gy,gz");
}

#if USE_IMU
void imuWrite(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

bool imuBegin() {
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(400000);
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x75);  // WHO_AM_I
  if (Wire.endTransmission(false) != 0) return false;
  Wire.requestFrom(MPU_ADDR, (uint8_t)1);
  if (!Wire.available()) return false;
  // 0x68 = MPU-6050. Many "MPU-6050" boards carry an MPU-6500-family chip instead (0x70, 0x72,
  // 0x74, ...; the project's IMU board reads 0x74) with the same registers for everything used here.
  const uint8_t id = Wire.read();
  if (id == 0x00 || id == 0xFF) return false;
  imuWrite(0x6B, 0x00);  // wake up
  imuWrite(0x1A, 0x03);  // low-pass ~44 Hz
  imuWrite(0x1B, 0x00);  // gyro +-250 deg/s
  imuWrite(0x1C, 0x00);  // accel +-2 g
  if (id != 0x68) imuWrite(0x1D, 0x03);  // 6500 family: accel low-pass ~45 Hz is in ACCEL_CONFIG2
  return true;
}

void imuRead(unsigned long t) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);  // ACCEL_XOUT_H: ax ay az temp gx gy gz, big-endian int16
  if (Wire.endTransmission(false) != 0) return;
  if (Wire.requestFrom(MPU_ADDR, (uint8_t)14) != 14) return;
  int16_t v[7];
  for (int i = 0; i < 7; i++) v[i] = (int16_t)((Wire.read() << 8) | Wire.read());
  char buf[96];
  snprintf(buf, sizeof(buf), "I,%lu,%d,%d,%d,%d,%d,%d", t, v[0], v[1], v[2], v[4], v[5], v[6]);
  addLine(buf);
}
#endif

void setup() {
  Serial.begin(921600);
  SerialBT.begin(BT_NAME);
  pinMode(LED_PIN, OUTPUT);
  analogReadResolution(12);  // 0-4095
#if USE_IMU
  imuOk = imuBegin();
#endif
  sayHello();
  nextSampleUs = micros();
}

void loop() {
  while ((long)(micros() - nextSampleUs) < 0) {}
  unsigned long t = nextSampleUs;
  nextSampleUs += SAMPLE_US;
  // If sending stalled us, restart the clock instead of bursting; the recorder sees the gap in micros.
  if ((long)(micros() - nextSampleUs) > (long)(10 * SAMPLE_US)) nextSampleUs = micros();

  int raw = analogRead(RAW_PIN);
  int env = analogRead(ENV_PIN);
  char buf[48];
  snprintf(buf, sizeof(buf), "E,%lu,%d,%d", t, raw, env);
  addLine(buf);

#if USE_IMU
  if (imuOk && ++tick >= IMU_EVERY) {
    tick = 0;
    imuRead(t);
  }
#endif

  bool client = SerialBT.hasClient();
  if (client && !hadClient) sayHello();  // the recorder just connected: tell it what's coming
  hadClient = client;
  digitalWrite(LED_PIN, client ? HIGH : LOW);

  if (micros() - lastSendUs > 20000) sendBatch();  // at least every 20 ms
}

/*
 * TrueRehab-RF (AEII 2026) - IMU ground-truth firmware
 * =====================================================
 * Board : ESP32 DevKit (classic ESP32; Arduino board "ESP32 Dev Module")
 * Sensor: MPU-6050, or the MPU-6500-family chip that many cheap "MPU-6050" boards really carry
 *         (WHO_AM_I 0x70 / 0x72 / 0x74 / 0x98 ...). I2C address 0x68 (AD0 -> GND) or 0x69.
 * Screen: SSD1306 128x64 OLED, I2C 0x3C (0x3D is tried too)
 *
 * Wiring: two separate I2C buses, so slow OLED writes (~25 ms each) never delay an IMU sample.
 *   MPU-6050 VCC -> 3V3    GND -> GND    SDA -> GPIO 27    SCL -> GPIO 26    AD0 -> GND
 *   OLED     VCC -> 3V3    GND -> GND    SDA -> GPIO 32    SCL -> GPIO 33
 *
 * Output (RECORD_MODE below). Lines starting with '#' are comments in both modes.
 *   LIVE   (0) 115200 baud, 50 Hz CSV for people and log_imu.py:
 *              t_ms,ax_g,ay_g,az_g,gx_dps,gy_dps,gz_dps,temp_c,pitch_deg,roll_deg
 *   RECORD (1) 921600 baud, 200 Hz line for the session recorder (recorder/record.py --imu <port>):
 *              I,<micros>,ax,ay,az,gx,gy,gz      counts: 16384 per g, 131 per deg/s, raw
 *   WIFI_LINK 1 (either mode): the same lines also go over Wi-Fi to one TCP client, port 3333, at
 *              truerehab-imu.local (recorder: --imu tcp://truerehab-imu.local:3333). USB keeps working.
 *              Needs wifi_secrets.h next to this file: copy wifi_secrets.example.h and fill it in.
 *
 * Keys (type in the Serial Monitor or the Wi-Fi client, then Enter) and the BOOT button:
 *   c  gyro calibration: keep the board still ~2 s        BOOT: short press
 *   a  accelerometer calibration: 6 faces, saved in flash  BOOT: hold 3 s, then release
 *   x  cancel the accelerometer calibration                BOOT: short press while it runs
 *   X  erase the saved accelerometer calibration
 *   ?  print settings and status
 *
 * Libraries (Arduino Library Manager): Adafruit SSD1306, Adafruit GFX Library.
 * The IMU is driven through its registers, so no MPU library is needed (the Adafruit MPU6050
 * library refuses every chip whose WHO_AM_I isn't 0x68 - including the one on our board).
 *
 * Development / validation tool (IMU ground truth), not part of the radar-only product.
 * See README.md next to this folder for wiring, calibration, recording and troubleshooting.
 */

#include <Wire.h>
#include <Preferences.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ============================================================================
// Settings
// ============================================================================
#ifndef RECORD_MODE
#define RECORD_MODE 0        // 0 = LIVE, 1 = RECORD (see the top of the file)
#endif
#ifndef RECORD_WIDE_RANGE
#define RECORD_WIDE_RANGE 1  // RECORD only. 1 = sensor at +-4 g / +-500 deg/s, counts sent at the
                             // recorder's 16384 per g and 131 per deg/s (= 2 x register value), so a
                             // fast rep can't clip at +-2 g / +-250 deg/s; values may then pass +-32767.
                             // 0 = sensor at +-2 g / +-250 deg/s, raw int16 as in firmware/myoware_record.
#endif
#define USE_BOOT_BUTTON 1    // BOOT button (GPIO 0) starts calibrations; 0 = ignore it
#ifndef IMU_SIMULATE
#define IMU_SIMULATE 0       // 1 = TEST ONLY: no sensor needed; synthetic data (still 4 s, then a slow
                             // +-60 deg swing about X, ~1 deg/s gyro bias). Every header says SIMULATED.
#endif
#ifndef WIFI_LINK
#define WIFI_LINK 0          // 1 = also send every line over Wi-Fi (see the top of the file); 0 = USB only
#endif

#if WIFI_LINK
#if __has_include("wifi_secrets.h")
#include "wifi_secrets.h"
#else
#error "WIFI_LINK 1 needs wifi_secrets.h next to the .ino: copy wifi_secrets.example.h to wifi_secrets.h and fill in your Wi-Fi name and password"
#endif
#include <WiFi.h>
#include <ESPmDNS.h>
#include <freertos/stream_buffer.h>
const char *LINK_HOSTNAME = "truerehab-imu";  // reachable as truerehab-imu.local
constexpr uint16_t LINK_PORT = 3333;
constexpr size_t LINK_BUF_BYTES = 32768;      // ~4 s of RECORD output, kept while Wi-Fi stalls
constexpr size_t LINK_LINE_MAX = 512;         // longer than any line the firmware prints
constexpr uint32_t LINK_REJOIN_MS = 15000;    // not joined after this long: start joining again
#endif

constexpr int MPU_SDA = 27, MPU_SCL = 26;    // IMU bus  (Wire)
constexpr int OLED_SDA = 32, OLED_SCL = 33;  // OLED bus (Wire1)
constexpr int BUTTON_PIN = 0;               // the DevKit's BOOT button

constexpr uint32_t MPU_I2C_HZ = 400000;      // drops to 100 kHz by itself after repeated bus errors
constexpr uint32_t OLED_I2C_HZ = 400000;
constexpr uint16_t I2C_TIMEOUT_MS = 5;       // a failed read costs at most ~1 slot at 200 Hz (a read
                                             // takes 0.45 ms at 400 kHz, 1.8 ms at 100 kHz)

#if RECORD_MODE
constexpr uint32_t SERIAL_BAUD = 921600;     // recorder/record.py --imu-baud default
constexpr uint32_t SAMPLE_HZ = 200;          // the recorder's IMU rate
constexpr uint8_t DLPF_CFG = 3;              // sensor low-pass ~41-45 Hz, below 200 Hz / 2
#else
constexpr uint32_t SERIAL_BAUD = 115200;
constexpr uint32_t SAMPLE_HZ = 50;
constexpr uint8_t DLPF_CFG = 4;              // sensor low-pass ~20 Hz, below 50 Hz / 2
#endif
constexpr uint32_t PERIOD_US = 1000000UL / SAMPLE_HZ;

#if RECORD_MODE && !RECORD_WIDE_RANGE
constexpr uint8_t ACCEL_FS = 0;              // +-2 g:       16384 per g
constexpr uint8_t GYRO_FS = 0;               // +-250 deg/s: 131 per deg/s
#else
constexpr uint8_t ACCEL_FS = 1;              // +-4 g:       8192 per g
constexpr uint8_t GYRO_FS = 1;               // +-500 deg/s: 65.5 per deg/s
#endif
constexpr float ACC_LSB_PER_G = 16384.0f / (1 << ACCEL_FS);
constexpr float GYRO_LSB_PER_DPS = 131.0f / (1 << GYRO_FS);
constexpr long REC_ACC_MULT = 1L << ACCEL_FS;  // register value -> recorder counts (16384 per g)
constexpr long REC_GYRO_MULT = 1L << GYRO_FS;  // register value -> recorder counts (131 per deg/s)
constexpr const char *RANGE_NAME = (ACCEL_FS == 0) ? "2g_250dps" : "4g_500dps";

constexpr uint32_t DISPLAY_HZ = 10;
constexpr uint32_t STATUS_EVERY_MS = 5000;   // '# status' line
constexpr uint32_t HEADER_EVERY_MS = 10000;  // RECORD: header repeated - opening the port from the
                                             // recorder does not reset the board, so the boot header is missed
constexpr uint32_t VERIFY_EVERY_MS = 1000;   // read the sensor settings back (catches a sensor reset)
constexpr uint32_t RETRY_EVERY_MS = 1000;    // look for a missing IMU again

// A window counts as "still" when every axis stays within these peak-to-peak limits.
constexpr float STILL_GYRO_PP_DPS = 3.0f;
constexpr float STILL_ACC_PP_G = 0.05f;
constexpr uint32_t GYRO_CAL_MS = 1500;          // still time needed for the gyro bias
constexpr uint32_t GYRO_CAL_GIVEUP_MS = 30000;
constexpr uint32_t LIVE_WAIT_CAL_MS = 5000;     // LIVE: data starts after the first gyro calibration
constexpr uint32_t ACCEL_FACE_MS = 1000;        // still time per face
constexpr uint32_t ACCEL_CAL_GIVEUP_MS = 180000;
constexpr uint32_t GYRO_CAL_SAMPLES = SAMPLE_HZ * GYRO_CAL_MS / 1000;
constexpr uint32_t ACCEL_FACE_SAMPLES = SAMPLE_HZ * ACCEL_FACE_MS / 1000;
constexpr uint32_t FROZEN_LIMIT = SAMPLE_HZ / 5;  // identical readings for 0.2 s = sensor not updating

constexpr float FILTER_KP = 1.0f;            // accelerometer pull on the angle: ~1 s time constant
constexpr float ACCEL_GATE = 0.15f;          // ignore the accelerometer when |a| is >15 % off its rest value
constexpr float R2D = 57.29578f, D2R = 0.01745329f;  // float, not Arduino's double RAD_TO_DEG

const char *FW_VERSION = "2.1";
const char *NVS_NAMESPACE = "truerehab_imu";
constexpr uint32_t ACAL_MAGIC = 0x31414354;  // marks a saved accelerometer calibration ("TCA1")
const char *FACE_NAME[6] = {"+X", "-X", "+Y", "-Y", "+Z", "-Z"};

// ============================================================================
// Types
// ============================================================================
enum ImuState : uint8_t { IMU_SEARCHING, IMU_OK, IMU_LOST };
enum CalState : uint8_t { CAL_NONE, CAL_RUNNING, CAL_OK, CAL_FAILED };
enum LinkState : uint8_t { LINK_OFF, LINK_JOINING, LINK_UP, LINK_STREAMING };  // Wi-Fi (WIFI_LINK 1)

struct Raw {                       // one burst read: register values
  int16_t ax, ay, az, temp, gx, gy, gz;
};

struct AccelCal {                  // corrected a = (nominal a - off) / scale, per axis, in g
  float off[3];
  float scale[3];
};

struct AccelCalBlob {              // what is stored in flash
  uint32_t magic;
  uint32_t chip;                   // WHO_AM_I of the chip it was measured on
  AccelCal cal;
};

// Collects samples while the board should be still; any axis moving too much -> start again.
struct StillWindow {
  uint32_t n = 0;
  float sumA[3], sumG[3], sumMag, minA[3], maxA[3], minG[3], maxG[3];

  void add(const float a[3], const float g[3], float mag) {
    if (n == 0) {
      sumMag = 0;
      for (int i = 0; i < 3; i++) {
        sumA[i] = sumG[i] = 0;
        minA[i] = maxA[i] = a[i];
        minG[i] = maxG[i] = g[i];
      }
    }
    for (int i = 0; i < 3; i++) {
      sumA[i] += a[i];
      sumG[i] += g[i];
      minA[i] = fminf(minA[i], a[i]);
      maxA[i] = fmaxf(maxA[i], a[i]);
      minG[i] = fminf(minG[i], g[i]);
      maxG[i] = fmaxf(maxG[i], g[i]);
    }
    sumMag += mag;
    n++;
  }

  bool moving() const {
    for (int i = 0; i < 3; i++) {
      if (maxG[i] - minG[i] > STILL_GYRO_PP_DPS || maxA[i] - minA[i] > STILL_ACC_PP_G) return true;
    }
    return false;
  }
};

// Mahony attitude filter (quaternion): gyro integration, pulled toward the accelerometer's
// gravity direction. Same pitch/roll convention as atan2(ay, az) / atan2(-ax, sqrt(ay2 + az2)),
// but no small-angle shortcut, so combined pitch + roll and steep angles stay right.
struct Mahony {
  float q0 = 1, q1 = 0, q2 = 0, q3 = 0;

  void seed(const float a[3]) {    // start from the accelerometer's tilt, yaw = 0
    const float roll = atan2f(a[1], a[2]);
    const float pitch = atan2f(-a[0], sqrtf(a[1] * a[1] + a[2] * a[2]));
    const float cr = cosf(roll / 2), sr = sinf(roll / 2), cp = cosf(pitch / 2), sp = sinf(pitch / 2);
    q0 = cr * cp;
    q1 = sr * cp;
    q2 = cr * sp;
    q3 = -sr * sp;
  }

  // g in rad/s (bias removed), a in any unit, dt in s. useAccel = false while the arm accelerates.
  void update(float gx, float gy, float gz, float ax, float ay, float az, bool useAccel, float dt) {
    const float norm = sqrtf(ax * ax + ay * ay + az * az);
    if (useAccel && norm > 1e-6f) {
      ax /= norm;
      ay /= norm;
      az /= norm;
      const float vx = q1 * q3 - q0 * q2;          // half the gravity direction the filter expects
      const float vy = q0 * q1 + q2 * q3;
      const float vz = q0 * q0 - 0.5f + q3 * q3;
      const float ex = ay * vz - az * vy;           // measured x expected (cross product)
      const float ey = az * vx - ax * vz;
      const float ez = ax * vy - ay * vx;
      gx += 2.0f * FILTER_KP * ex;
      gy += 2.0f * FILTER_KP * ey;
      gz += 2.0f * FILTER_KP * ez;
    }
    gx *= 0.5f * dt;
    gy *= 0.5f * dt;
    gz *= 0.5f * dt;
    const float qa = q0, qb = q1, qc = q2;
    q0 += -qb * gx - qc * gy - q3 * gz;
    q1 += qa * gx + qc * gz - q3 * gy;
    q2 += qa * gy - qb * gz + q3 * gx;
    q3 += qa * gz + qb * gy - qc * gx;
    const float n = 1.0f / sqrtf(q0 * q0 + q1 * q1 + q2 * q2 + q3 * q3);
    q0 *= n;
    q1 *= n;
    q2 *= n;
    q3 *= n;
  }

  float rollDeg() const { return atan2f(q0 * q1 + q2 * q3, 0.5f - q1 * q1 - q2 * q2) * R2D; }
  float pitchDeg() const {
    const float s = -2.0f * (q1 * q3 - q0 * q2);
    return asinf(s > 1 ? 1 : (s < -1 ? -1 : s)) * R2D;
  }
};

// Everything the OLED task draws. The sampling loop fills a copy and hands it over under a lock,
// so the two cores never touch the same data at the same time.
struct View {
  uint8_t imuState = IMU_SEARCHING;
  char problem[64] = "";
  float a[3] = {0, 0, 0}, g[3] = {0, 0, 0};
  float tempC = 0, pitch = 0, roll = 0, rateHz = 0;
  uint32_t i2cErrors = 0;
  bool errRecent = false, satRecent = false;
  uint8_t gyroCal = CAL_NONE, gyroCalPct = 0;
  bool accelCalValid = false;
  bool accelCalActive = false;
  uint8_t accelDone = 0, accelPct = 0;
  int8_t accelFace = -1;
  bool buttonLong = false;
  char note[22] = "";
  uint32_t noteUntilMs = 0;
  uint8_t linkState = LINK_OFF;
  uint32_t linkIp = 0;               // IPv4, IPAddress byte order
};

// ============================================================================
// State
// ============================================================================
Adafruit_SSD1306 display(128, 64, &Wire1, -1, OLED_I2C_HZ, OLED_I2C_HZ);
TaskHandle_t oledTaskHandle = nullptr;
volatile bool oledOk = false;
volatile uint8_t oledAddr = 0;

portMUX_TYPE viewLock = portMUX_INITIALIZER_UNLOCKED;
View sharedView;   // read by the OLED task (core 0)
View view;         // written by the sampling loop (core 1)

// IMU
uint8_t mpuAddr = 0x68;
uint8_t chipId = 0;
bool chipKnown = false;
bool accelLpfOk = true;            // 6500 family: the accel low-pass register read back correctly
uint32_t mpuI2cHz = MPU_I2C_HZ;
ImuState imuState = IMU_SEARCHING;
char imuProblem[64] = "";
char lastPrintedProblem[64] = "";

// Sampling
uint32_t nextSampleUs = 0, lastSampleUs = 0;
uint32_t bootMs = 0;
uint32_t samplesRead = 0, samplesOut = 0, skipped = 0;
uint32_t i2cErrors = 0, recoveries = 0, frozenEvents = 0, satSamples = 0;
uint32_t readFails = 0, frozenRun = 0;
uint32_t lastErrMs = 0, lastSatMs = 0;
Raw prevRaw;
bool havePrev = false;
float lastTempC = 0;
bool liveStarted = false;

// Attitude
Mahony ahrs;
bool filterSeeded = false;
float pitchDeg = 0, rollDeg = 0;

// Gyro calibration
CalState gyroCal = CAL_NONE;
uint32_t gyroCalStartMs = 0;
StillWindow gyroWin;
float gyroBias[3] = {0, 0, 0};     // deg/s
float gRest = 1.0f;                // |a| while still (g); the accelerometer gate is centred on it

// Accelerometer calibration
AccelCal acal = {{0, 0, 0}, {1, 1, 1}};
bool accelCalValid = false;
AccelCalBlob storedCal;
bool storedCalLoaded = false;
struct {
  bool active = false;
  uint8_t done = 0;                // bit f set = face f captured
  float face[6][3];                // mean nominal accel per face (g)
  StillWindow win;
  int8_t now = -1;                 // face being held right now
  uint32_t startMs = 0;
} acr;

// Timers and button
uint32_t lastStatusMs = 0, lastHeaderMs = 0, lastVerifyMs = 0, lastRetryMs = 0;
uint32_t lastPublishMs = 0, rateWindowMs = 0, rateWindowSamples = 0;
bool buttonLong = false;
int oledReported = -1;             // -1 unknown, 0 missing, 1 present

// ============================================================================
// Output: everything the firmware prints goes through `tee`
// ============================================================================
#if WIFI_LINK
// Shared with the Wi-Fi link task (core 0). Every value has a single writer.
StreamBufferHandle_t linkOut = nullptr;   // whole lines for the client: written by tee, read by the link task
StreamBufferHandle_t linkKeys = nullptr;  // keys from the client: written by the link task, read by loop()
TaskHandle_t linkTaskHandle = nullptr;
volatile bool linkClient = false;         // link task: a client is connected and gets the lines
volatile bool linkHello = false;          // set by the link task, cleared by loop(): send header + status now
volatile uint8_t linkState = LINK_JOINING;
volatile uint32_t linkIp = 0;             // IPv4, IPAddress byte order; 0 = not joined
volatile int8_t linkRssi = 0;             // dBm
volatile uint32_t linkClients = 0;        // clients accepted since boot
volatile uint32_t linkSendFails = 0;      // clients dropped after a failed send: it closed, or took nothing for ~10 s
uint32_t linkDropped = 0;                 // core 1 only: lines not sent because the buffer was full

// To USB as always, plus a copy of every whole line for the Wi-Fi client while one is connected. Only
// setup() and loop() print (core 1), so linkOut has one writer and one reader, as a FreeRTOS stream
// buffer requires. A line that doesn't fit is dropped whole and counted: the client never gets half a line.
class Tee : public Print {
 public:
  using Print::write;
  size_t write(uint8_t c) override { return write(&c, 1); }
  size_t write(const uint8_t *p, size_t n) override {
    Serial.write(p, n);
    for (size_t i = 0; i < n; i++) {
      line_[len_++] = p[i];
      if (p[i] == '\n' || len_ == sizeof line_) pushLine();
    }
    return n;
  }

 private:
  uint8_t line_[LINK_LINE_MAX];
  size_t len_ = 0;

  void pushLine() {
    if (linkClient && linkOut) {
      if (xStreamBufferSpacesAvailable(linkOut) >= len_) {
        xStreamBufferSend(linkOut, line_, len_, 0);
      } else {
        linkDropped++;
      }
    }
    len_ = 0;
  }
};
Tee tee;
#else
auto &tee = Serial;  // USB only: the same output as before WIFI_LINK existed
#endif

// ============================================================================
// I2C helpers
// ============================================================================
bool i2cProbe(TwoWire &bus, uint8_t addr) {
  bus.beginTransmission(addr);
  return bus.endTransmission() == 0;
}

// Free a bus whose SDA is held low by a device that was cut off mid-transfer (e.g. the ESP32
// reset while the IMU was sending): clock SCL until SDA is released, then send a STOP.
// Only while the I2C driver is detached from the pins. False = a line stays low (wiring fault).
bool i2cBusClear(int sda, int scl) {
  pinMode(sda, INPUT_PULLUP);
  pinMode(scl, INPUT_PULLUP);
  delayMicroseconds(50);
  if (digitalRead(scl) == LOW) return false;
  if (digitalRead(sda) == HIGH) return true;
  pinMode(scl, OUTPUT_OPEN_DRAIN | PULLUP);
  for (int i = 0; i < 9 && digitalRead(sda) == LOW; i++) {
    digitalWrite(scl, LOW);
    delayMicroseconds(5);
    digitalWrite(scl, HIGH);
    delayMicroseconds(5);
  }
  pinMode(sda, OUTPUT_OPEN_DRAIN | PULLUP);  // STOP: SDA rises while SCL is high
  digitalWrite(sda, LOW);
  delayMicroseconds(5);
  digitalWrite(sda, HIGH);
  delayMicroseconds(5);
  pinMode(sda, INPUT_PULLUP);
  pinMode(scl, INPUT_PULLUP);
  delayMicroseconds(50);
  return digitalRead(sda) == HIGH && digitalRead(scl) == HIGH;
}

// ============================================================================
// MPU-6050 / MPU-6500-family register driver
// ============================================================================
namespace Reg {
constexpr uint8_t SMPLRT_DIV = 0x19, CONFIG = 0x1A, GYRO_CONFIG = 0x1B, ACCEL_CONFIG = 0x1C,
                  ACCEL_CONFIG2 = 0x1D, ACCEL_XOUT_H = 0x3B, USER_CTRL = 0x6A, PWR_MGMT_1 = 0x6B,
                  PWR_MGMT_2 = 0x6C, WHO_AM_I = 0x75;
}

// 0x68 is the MPU-6050 register map. Every other ID is treated as the MPU-6500 family: same
// registers for everything used here, plus ACCEL_CONFIG2 for the accelerometer low-pass.
bool fam6500() { return chipId != 0x68; }

bool mpuWrite(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(mpuAddr);
  Wire.write(reg);
  Wire.write(val);
  return Wire.endTransmission() == 0;
}

bool mpuRead(uint8_t reg, uint8_t *dst, size_t n) {
  Wire.beginTransmission(mpuAddr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(mpuAddr, n) != n) return false;
  for (size_t i = 0; i < n; i++) dst[i] = Wire.read();
  return true;
}

#if IMU_SIMULATE
uint32_t simStartUs = 0;

// Synthetic sensor: still for 4 s, then a +-60 deg swing about X every 4 s (like an elbow curl),
// with noise and a gyro bias. Takes about as long as a real 400 kHz burst read.
bool simReadSample(Raw &r) {
  static uint32_t seed = 12345;
  auto noise = [&]() {
    seed = seed * 1664525u + 1013904223u;
    return (int)((seed >> 24) % 7) - 3;
  };
  const float t = (micros() - simStartUs) * 1e-6f;
  float th = 0, thDot = 0;  // rad, rad/s
  if (t > 4) {
    const float w = 2 * PI / 4;
    th = 1.0472f * sinf(w * (t - 4));
    thDot = 1.0472f * w * cosf(w * (t - 4));
  }
  r.ax = (int16_t)noise();                                             // gravity: (0, sin th, cos th) g
  r.ay = (int16_t)(sinf(th) * ACC_LSB_PER_G + noise());
  r.az = (int16_t)(cosf(th) * ACC_LSB_PER_G + noise());
  r.temp = 2270;
  r.gx = (int16_t)(thDot * R2D * GYRO_LSB_PER_DPS + GYRO_LSB_PER_DPS + noise());  // + 1 deg/s bias
  r.gy = (int16_t)(-0.5f * GYRO_LSB_PER_DPS + noise());
  r.gz = (int16_t)(0.25f * GYRO_LSB_PER_DPS + noise());
  delayMicroseconds(450);
  return true;
}
#endif

bool mpuReadSample(Raw &r) {
#if IMU_SIMULATE
  return simReadSample(r);
#endif
  uint8_t b[14];
  if (!mpuRead(Reg::ACCEL_XOUT_H, b, sizeof b)) return false;
  r.ax = (int16_t)((b[0] << 8) | b[1]);
  r.ay = (int16_t)((b[2] << 8) | b[3]);
  r.az = (int16_t)((b[4] << 8) | b[5]);
  r.temp = (int16_t)((b[6] << 8) | b[7]);
  r.gx = (int16_t)((b[8] << 8) | b[9]);
  r.gy = (int16_t)((b[10] << 8) | b[11]);
  r.gz = (int16_t)((b[12] << 8) | b[13]);
  return true;
}

float tempFromRaw(int16_t raw) {
  switch (chipId) {
    case 0x68: return raw / 340.0f + 36.53f;                              // MPU-6050
    case 0x11: case 0x12: case 0x20: case 0x98: case 0xA6: case 0xA9:
    case 0xAE: case 0xAF: return raw / 326.8f + 25.0f;                    // ICM-206xx
    default: return raw / 333.87f + 21.0f;                                // MPU-6500 family
  }
}

// Read the settings back. 0 = as written, 1 = read failed, 2 = different (sensor was reset).
int mpuCheck() {
#if IMU_SIMULATE
  return 0;
#endif
  uint8_t r[3], pm;
  if (!mpuRead(Reg::CONFIG, r, 3) || !mpuRead(Reg::PWR_MGMT_1, &pm, 1)) return 1;
  if ((r[0] & 0x07) != DLPF_CFG) return 2;
  if ((r[1] & 0x1B) != (GYRO_FS << 3)) return 2;   // range + FCHOICE_B (low-pass on)
  if ((r[2] & 0x18) != (ACCEL_FS << 3)) return 2;
  if (pm & 0x40) return 2;                          // asleep
  return 0;
}

bool mpuConfigure() {
  if (!mpuWrite(Reg::PWR_MGMT_1, 0x80)) return false;  // reset every register
  delay(100);
  bool ok = mpuWrite(Reg::PWR_MGMT_1, 0x01);            // awake, clock from the gyro PLL (stabler)
  delay(30);
  ok &= mpuWrite(Reg::PWR_MGMT_2, 0x00);                // all six axes on
  ok &= mpuWrite(Reg::USER_CTRL, 0x00);                 // FIFO and aux I2C master off
  ok &= mpuWrite(Reg::SMPLRT_DIV, 0x00);                // 1 kHz inside the chip; we read at SAMPLE_HZ
  ok &= mpuWrite(Reg::CONFIG, DLPF_CFG);                // low-pass: gyro (and accel on the 6050)
  ok &= mpuWrite(Reg::GYRO_CONFIG, GYRO_FS << 3);
  ok &= mpuWrite(Reg::ACCEL_CONFIG, ACCEL_FS << 3);
  accelLpfOk = true;
  if (fam6500()) {                                      // 6500 family: accel low-pass lives here
    uint8_t v = 0xFF;
    ok &= mpuWrite(Reg::ACCEL_CONFIG2, DLPF_CFG);
    accelLpfOk = mpuRead(Reg::ACCEL_CONFIG2, &v, 1) && (v & 0x0F) == DLPF_CFG;
  }
  delay(20);                                            // let the low-pass settle
  return ok && mpuCheck() == 0;
}

// With the I2C driver detached: a line with an external pull-up (a few kOhm, on the IMU board)
// reads HIGH even against the ESP32's ~45 kOhm pull-down. No pull-up usually means a loose wire.
bool hasPullup(int pin) {
  pinMode(pin, INPUT_PULLDOWN);
  delayMicroseconds(100);
  const bool up = digitalRead(pin) == HIGH;
  pinMode(pin, INPUT_PULLUP);
  return up;
}

bool sdaPullup = true, sclPullup = true;  // seen at the last bus restart

// Restart the IMU bus: detach, check the lines, free a stuck SDA, attach again with a short timeout.
bool imuBusRestart() {
  Wire.end();
  sdaPullup = hasPullup(MPU_SDA);
  sclPullup = hasPullup(MPU_SCL);
  const bool linesOk = i2cBusClear(MPU_SDA, MPU_SCL);
  Wire.begin(MPU_SDA, MPU_SCL, mpuI2cHz);
  Wire.setTimeOut(I2C_TIMEOUT_MS);
  return linesOk;
}

bool imuFind() {
  if (i2cProbe(Wire, 0x68)) {
    mpuAddr = 0x68;
  } else if (i2cProbe(Wire, 0x69)) {
    mpuAddr = 0x69;
  } else {
    return false;
  }
  return true;
}

// Find the IMU (0x68, then 0x69), read its ID and configure it. On failure imuProblem says why
// (short lines for the OLED).
bool imuConnect() {
#if IMU_SIMULATE
  chipId = 0x00;
  chipKnown = true;
  imuProblem[0] = 0;
  simStartUs = micros();
  return true;
#endif
  if (!imuBusRestart()) {
    snprintf(imuProblem, sizeof imuProblem, "SDA/SCL stuck LOW:\nshort, no power, or\nSDA/SCL swapped?");
    return false;
  }
  bool found = imuFind();
  if (!found && mpuI2cHz > 100000) {  // weak pull-ups / long wires: 400 kHz can fail where 100 kHz works
    const uint32_t fast = mpuI2cHz;
    mpuI2cHz = 100000;
    imuBusRestart();
    found = imuFind();
    if (found) {
      tee.printf("# imu answers only at 100 kHz, not %lu (weak pull-ups or long wires?) - staying at 100 kHz\n",
                 (unsigned long)fast);
    } else {
      mpuI2cHz = fast;
    }
  }
  if (!found) {
    int other = -1;
    for (uint8_t a = 0x08; a < 0x78 && other < 0; a++) {
      if (i2cProbe(Wire, a)) other = a;
    }
    if (other == 0x68 || other == 0x69) {  // missed the probe a moment ago, answers now: bad contact
      snprintf(imuProblem, sizeof imuProblem, "IMU 0x%02X answers\nonly sometimes:\nloose wire/contact?", other);
    } else if (other >= 0) {
      snprintf(imuProblem, sizeof imuProblem, "only 0x%02X answers\n(IMU is 0x68/0x69)\nwrong device?", other);
    } else if (!sdaPullup && !sclPullup) {
      snprintf(imuProblem, sizeof imuProblem, "no pull-ups at all:\nIMU VCC/GND loose?\nthen SDA/SCL wires");
    } else if (!sdaPullup || !sclPullup) {  // also what a half-powered module (loose VCC/GND) looks like
      snprintf(imuProblem, sizeof imuProblem, "no pull-up on %s%d:\nthat wire loose, or\nIMU VCC/GND loose?",
               sdaPullup ? "SCL" : "SDA", sdaPullup ? MPU_SCL : MPU_SDA);
    } else {
      snprintf(imuProblem, sizeof imuProblem, "nothing answers.\nCheck VCC, GND and\nSDA%d / SCL%d wires", MPU_SDA,
               MPU_SCL);
    }
    return false;
  }
  uint8_t id = 0;
  if (!mpuRead(Reg::WHO_AM_I, &id, 1)) {
    snprintf(imuProblem, sizeof imuProblem, "0x%02X answers but\nreads fail (loose\nwire, long cable?)", mpuAddr);
    return false;
  }
  chipId = id;
  chipKnown = true;
  if (!mpuConfigure()) {
    snprintf(imuProblem, sizeof imuProblem, "0x%02X id 0x%02X:\nsetup didn't stick:\nloose wire? not MPU?", mpuAddr, id);
    return false;
  }
  imuProblem[0] = 0;
  return true;
}

// ============================================================================
// Accelerometer calibration storage (flash, survives power-off)
// ============================================================================
void loadStoredAccelCal() {
  Preferences p;
  if (!p.begin(NVS_NAMESPACE, true)) return;  // nothing saved yet
  storedCalLoaded = p.getBytes("acal", &storedCal, sizeof storedCal) == sizeof storedCal && storedCal.magic == ACAL_MAGIC;
  p.end();
}

void applyStoredAccelCal() {
  accelCalValid = storedCalLoaded && storedCal.chip == chipId;
  if (accelCalValid) {
    acal = storedCal.cal;
    gRest = 1.0f;
  } else if (storedCalLoaded) {
    tee.printf("# saved accel calibration is for chip 0x%02lX, this chip is 0x%02X - not used\n",
               (unsigned long)storedCal.chip, chipId);
  }
}

bool saveAccelCal(const AccelCal &c) {
  Preferences p;
  if (!p.begin(NVS_NAMESPACE, false)) return false;
  AccelCalBlob b = {ACAL_MAGIC, chipId, c};
  const bool ok = p.putBytes("acal", &b, sizeof b) == sizeof b;
  p.end();
  if (ok) {
    storedCal = b;
    storedCalLoaded = true;
  }
  return ok;
}

void eraseAccelCal() {
  Preferences p;
  if (p.begin(NVS_NAMESPACE, false)) {
    p.remove("acal");
    p.end();
  }
  storedCalLoaded = false;
  accelCalValid = false;
  acal = {{0, 0, 0}, {1, 1, 1}};
  filterSeeded = false;
  tee.println("# accel calibration erased");
}

void accelCorrect(const float an[3], float out[3]) {
  for (int i = 0; i < 3; i++) out[i] = accelCalValid ? (an[i] - acal.off[i]) / acal.scale[i] : an[i];
}

// ============================================================================
// Messages
// ============================================================================
void note(const char *text) {
  strncpy(view.note, text, sizeof view.note - 1);
  view.note[sizeof view.note - 1] = 0;
  view.noteUntilMs = millis() + 3000;
}

void printProblem(const char *prefix) {
  tee.print(prefix);
  for (const char *c = imuProblem; *c; c++) tee.print(*c == '\n' ? ' ' : *c);
  tee.println();
}

void printCsvHeader() {
  tee.println("# t_ms,ax_g,ay_g,az_g,gx_dps,gy_dps,gz_dps,temp_c,pitch_deg,roll_deg");
}

void printHeader() {
#if RECORD_MODE
  tee.printf("# truerehab-imu-record v2 fw=%s rate_hz=%lu counts_per_g=16384 counts_per_dps=131 range=%s dlpf_cfg=%u",
             FW_VERSION, (unsigned long)SAMPLE_HZ, RANGE_NAME, DLPF_CFG);
#else
  tee.printf("# TrueRehab-RF IMU ground truth fw=%s mode=live rate_hz=%lu range=%s dlpf_cfg=%u", FW_VERSION,
             (unsigned long)SAMPLE_HZ, RANGE_NAME, DLPF_CFG);
#endif
  if (IMU_SIMULATE) {
    tee.println(" imu=SIMULATED");
    tee.println("# WARNING: IMU_SIMULATE=1 - synthetic test data, NOT a real sensor");
  } else if (chipKnown) {
    tee.printf(" addr=0x%02X who_am_i=0x%02X family=%s accel_lpf=%s i2c_hz=%lu pullup_sda=%s pullup_scl=%s\n",
               mpuAddr, chipId, fam6500() ? "6500" : "6050", accelLpfOk ? "ok" : "unverified",
               (unsigned long)mpuI2cHz, sdaPullup ? "yes" : "no", sclPullup ? "yes" : "no");
  } else {
    tee.println(" imu=not_found");
  }
#if WIFI_LINK
  tee.printf("# wifi link: tcp port %u at %s.local, one client at a time\n", LINK_PORT, LINK_HOSTNAME);
#endif
  if (accelCalValid) {
    tee.printf("# accel_cal on off_g=%.4f,%.4f,%.4f scale=%.4f,%.4f,%.4f%s\n", acal.off[0], acal.off[1],
               acal.off[2], acal.scale[0], acal.scale[1], acal.scale[2],
               RECORD_MODE ? " (raw I lines: apply offline as (counts/16384 - off)/scale)" : "");
  } else {
    tee.println("# accel_cal none (send a, or hold BOOT 3 s, to calibrate)");
  }
#if RECORD_MODE
  tee.println("# I,micros,ax,ay,az,gx,gy,gz  (counts: 16384 per g, 131 per deg/s; raw, no bias or calibration)");
#else
  if (liveStarted) printCsvHeader();
#endif
}

void printHelp() {
  tee.println("# keys: c = gyro calibration (hold still) | a = accel 6-face calibration | x = cancel it"
              " | X = erase saved accel calibration | ? = settings + status");
#if USE_BOOT_BUTTON
  tee.println("# BOOT button: press = gyro calibration, hold 3 s = accel calibration");
#endif
}

const char *calName(CalState s) {
  switch (s) {
    case CAL_RUNNING: return "running";
    case CAL_OK: return "ok";
    case CAL_FAILED: return "failed";
    default: return "none";
  }
}

const char *linkStateName(uint8_t s) {
  switch (s) {
    case LINK_JOINING: return "joining";
    case LINK_UP: return "up";
    case LINK_STREAMING: return "streaming";
    default: return "off";
  }
}

void printStatus() {
  const char *imu = imuState == IMU_OK ? "ok" : (imuState == IMU_LOST ? "lost" : "not_found");
  tee.printf("# status up_s=%lu imu=%s samples=%lu rate_hz=%.1f skipped=%lu i2c_err=%lu recoveries=%lu"
             " frozen=%lu saturated=%lu i2c_hz=%lu gyro_cal=%s gyro_bias_dps=%.3f,%.3f,%.3f",
             (unsigned long)((millis() - bootMs) / 1000), imu, (unsigned long)samplesOut, view.rateHz,
             (unsigned long)skipped, (unsigned long)i2cErrors, (unsigned long)recoveries,
             (unsigned long)frozenEvents, (unsigned long)satSamples, (unsigned long)mpuI2cHz, calName(gyroCal),
             gyroBias[0], gyroBias[1], gyroBias[2]);
#if RECORD_MODE
  tee.printf(" gyro_bias_counts=%ld,%ld,%ld", lroundf(gyroBias[0] * 131.0f), lroundf(gyroBias[1] * 131.0f),
             lroundf(gyroBias[2] * 131.0f));
#endif
#if WIFI_LINK
  const IPAddress ip((uint32_t)linkIp);
  tee.printf(" wifi=%s ip=%u.%u.%u.%u rssi_dbm=%d link_clients=%lu link_dropped=%lu link_send_fails=%lu",
             linkStateName(linkState), ip[0], ip[1], ip[2], ip[3], (int)linkRssi, (unsigned long)linkClients,
             (unsigned long)linkDropped, (unsigned long)linkSendFails);
#endif
  tee.printf(" a_rest_g=%.3f accel_cal=%s temp_c=%.1f oled=%s\n", gRest, accelCalValid ? "on" : "none",
             lastTempC, oledOk ? "ok" : "missing");
}

void printDebug() {
  tee.printf("# debug: heap_free=%lu oled_task_stack_free=%lu loop_stack_free=%lu",
             (unsigned long)ESP.getFreeHeap(),
             (unsigned long)(oledTaskHandle ? uxTaskGetStackHighWaterMark(oledTaskHandle) : 0),
             (unsigned long)uxTaskGetStackHighWaterMark(nullptr));
#if WIFI_LINK
  tee.printf(" link_task_stack_free=%lu link_buf_free=%lu",
             (unsigned long)(linkTaskHandle ? uxTaskGetStackHighWaterMark(linkTaskHandle) : 0),
             (unsigned long)(linkOut ? xStreamBufferSpacesAvailable(linkOut) : 0));
#endif
  tee.print("\n");
}

// ============================================================================
// Calibrations (both run inside the sampling loop, so the data stream never stops)
// ============================================================================
void startGyroCal(const char *why) {
  gyroCal = CAL_RUNNING;
  gyroCalStartMs = millis();
  gyroWin.n = 0;
  tee.printf("# gyro calibration started (%s) - keep the board still\n", why);
}

// g: deg/s without bias removal; a: corrected accel (g)
void gyroCalFeed(const float g[3], const float a[3], float mag) {
  if (gyroCal != CAL_RUNNING) return;
  gyroWin.add(a, g, mag);
  if (gyroWin.moving()) {
    gyroWin.n = 0;
    if (millis() - gyroCalStartMs > GYRO_CAL_GIVEUP_MS) {
      gyroCal = CAL_FAILED;
      tee.println("# gyro calibration gave up: the board kept moving (bias unchanged; press BOOT or send c)");
      note("gyro cal: moving");
    }
    return;
  }
  if (gyroWin.n < GYRO_CAL_SAMPLES) return;
  for (int i = 0; i < 3; i++) gyroBias[i] = gyroWin.sumG[i] / gyroWin.n;
  gRest = gyroWin.sumMag / gyroWin.n;
  gyroCal = CAL_OK;
  tee.printf("# gyro bias dps: %.3f %.3f %.3f  (|a| at rest %.3f g)\n", gyroBias[0], gyroBias[1], gyroBias[2],
             gRest);
  note("gyro calibrated");
}

int8_t faceOf(const float m[3]) {
  int k = 0;
  for (int i = 1; i < 3; i++) {
    if (fabsf(m[i]) > fabsf(m[k])) k = i;
  }
  if (fabsf(m[k]) < 0.7f) return -1;
  for (int i = 0; i < 3; i++) {
    if (i != k && fabsf(m[i]) > 0.4f) return -1;  // tilted too far from a face
  }
  return (int8_t)(k * 2 + (m[k] < 0 ? 1 : 0));
}

void startAccelCal(const char *why) {
  acr.active = true;
  acr.done = 0;
  acr.win.n = 0;
  acr.now = -1;
  acr.startMs = millis();
  tee.printf("# accel calibration started (%s): put each of the 6 faces up in turn and hold still ~1 s;"
             " x cancels\n", why);
}

void stopAccelCal(const char *why) {
  acr.active = false;
  tee.printf("# accel calibration stopped: %s\n", why);
  note("accel cal stopped");
}

void finishAccelCal() {
  AccelCal c;
  bool sane = true;
  for (int i = 0; i < 3; i++) {
    const float up = acr.face[2 * i][i], down = acr.face[2 * i + 1][i];
    c.off[i] = (up + down) / 2;
    c.scale[i] = (up - down) / 2;
    if (c.scale[i] < 0.8f || c.scale[i] > 1.2f || fabsf(c.off[i]) > 0.3f) sane = false;
  }
  tee.printf("# accel calibration result: off_g=%.4f,%.4f,%.4f scale=%.4f,%.4f,%.4f\n", c.off[0], c.off[1],
             c.off[2], c.scale[0], c.scale[1], c.scale[2]);
  acr.active = false;
  if (!sane) {
    tee.println("# accel calibration NOT saved: result out of range (offset > 0.3 g or scale off by > 20 %)");
    note("accel cal rejected");
    return;
  }
  acal = c;
  accelCalValid = true;
  gRest = 1.0f;
  filterSeeded = false;  // restart the angle from the corrected accelerometer
  if (saveAccelCal(c)) {
    tee.println("# accel calibration saved to flash");
    note("accel cal saved");
  } else {
    tee.println("# accel calibration applied, but saving to flash FAILED (lost at power-off)");
    note("accel cal not saved");
  }
}

// an: nominal accel (g, no calibration); g: deg/s
void accelCalFeed(const float an[3], const float g[3]) {
  if (!acr.active) return;
  if (millis() - acr.startMs > ACCEL_CAL_GIVEUP_MS) {
    stopAccelCal("timeout (3 min)");
    return;
  }
  acr.win.add(an, g, 0);
  if (acr.win.moving()) {
    acr.win.n = 0;
    acr.now = -1;
    return;
  }
  float m[3];
  for (int i = 0; i < 3; i++) m[i] = acr.win.sumA[i] / acr.win.n;
  acr.now = faceOf(m);
  if (acr.win.n < ACCEL_FACE_SAMPLES) return;
  acr.win.n = 0;  // window complete: start the next one
  if (acr.now < 0 || (acr.done & (1 << acr.now))) return;
  memcpy(acr.face[acr.now], m, sizeof m);
  acr.done |= 1 << acr.now;
  tee.printf("# accel calibration: %s captured (%d/6)\n", FACE_NAME[acr.now], __builtin_popcount(acr.done));
  if (acr.done == 0x3F) finishAccelCal();
}

// ============================================================================
// OLED task (core 0): finds the display (hot-plug), draws the latest View 10 times a second
// ============================================================================
void drawText(int x, int y, const char *s) {
  display.setCursor(x, y);
  display.print(s);
}

void drawBar(int x, int y, int w, int h, int pct) {
  display.drawRect(x, y, w, h, SSD1306_WHITE);
  display.fillRect(x + 1, y + 1, (w - 2) * constrain(pct, 0, 100) / 100, h - 2, SSD1306_WHITE);
}

void drawNoImu(const View &v) {
  drawText(0, 0, v.imuState == IMU_LOST ? "IMU LOST - retrying" : "Looking for IMU...");
  drawText(0, 14, v.problem);
  char s[24];
  snprintf(s, sizeof s, "IMU bus SDA%d SCL%d", MPU_SDA, MPU_SCL);
  drawText(0, 56, s);
}

void drawAccelCal(const View &v) {
  char s[24];
  snprintf(s, sizeof s, "ACCEL CAL  %d/6", __builtin_popcount(v.accelDone));
  drawText(0, 0, s);
  for (int f = 0; f < 6; f++) {
    const int x = f * 21;
    if (v.accelDone & (1 << f)) {
      display.fillRect(x, 11, 20, 11, SSD1306_WHITE);
      display.setTextColor(SSD1306_BLACK);
    }
    drawText(x + 4, 13, FACE_NAME[f]);
    display.setTextColor(SSD1306_WHITE);
  }
  drawText(0, 26, "Turn each face up,");
  drawText(0, 36, "hold still ~1 s.");
  if (v.accelFace < 0) {
    drawText(0, 46, "now: moving/tilted");
  } else {
    snprintf(s, sizeof s, "now: %s", FACE_NAME[v.accelFace]);
    drawText(0, 46, s);
    if (v.accelDone & (1 << v.accelFace)) {
      drawText(64, 46, "done");
    } else {
      drawBar(64, 46, 64, 8, v.accelPct);
    }
  }
  drawText(0, 56, "BOOT/x = cancel");
}

void drawNormal(const View &v) {
  char s[32];
  snprintf(s, sizeof s, "%s %3.0fHz %5.1fC%s", IMU_SIMULATE ? "SIM " : (RECORD_MODE ? "REC " : "LIVE"), v.rateHz,
           v.tempC, v.linkState == LINK_STREAMING ? " W" : "");  // W = a Wi-Fi client gets the data
  drawText(0, 0, s);
  snprintf(s, sizeof s, "a%6.2f%6.2f%6.2f", v.a[0], v.a[1], v.a[2]);
  drawText(0, 11, s);
  snprintf(s, sizeof s, "w%6ld%6ld%6ld", lroundf(v.g[0]), lroundf(v.g[1]), lroundf(v.g[2]));
  drawText(0, 21, s);
  display.setTextSize(2);
  snprintf(s, sizeof s, "P%ld", lroundf(v.pitch));
  drawText(0, 34, s);
  snprintf(s, sizeof s, "R%ld", lroundf(v.roll));
  drawText(64, 34, s);
  display.setTextSize(1);

  // Bottom line: the most important thing right now
  if ((int32_t)(millis() - v.noteUntilMs) < 0) {
    drawText(0, 56, v.note);
  } else if (v.buttonLong) {
    drawText(0, 56, "release: accel cal");
  } else if (v.gyroCal == CAL_RUNNING) {
    drawText(0, 56, "hold STILL");
    drawBar(64, 56, 64, 8, v.gyroCalPct);
  } else if (v.satRecent) {
    drawText(0, 56, "SATURATED: too fast");
  } else if (v.errRecent) {
    snprintf(s, sizeof s, "I2C errors: %lu", (unsigned long)v.i2cErrors);
    drawText(0, 56, s);
#if WIFI_LINK
  } else if (v.linkState == LINK_JOINING) {
    drawText(0, 56, "wifi: joining...");
  } else if (v.linkState == LINK_UP) {  // joined, nobody connected yet: show where to connect
    const IPAddress ip(v.linkIp);
    snprintf(s, sizeof s, "wifi %u.%u.%u.%u", ip[0], ip[1], ip[2], ip[3]);
    drawText(0, 56, s);
#endif
  } else if (v.gyroCal == CAL_FAILED) {
    drawText(0, 56, "gyro uncal: BOOT");
  } else if (!v.accelCalValid) {
    drawText(0, 56, "accel uncal:hold BOOT");
  } else {
    drawText(0, 56, v.linkState == LINK_STREAMING ? "ok, wifi streaming" : "ok");
  }
}

uint8_t oledFind() {
  if (i2cProbe(Wire1, 0x3C)) return 0x3C;
  if (i2cProbe(Wire1, 0x3D)) return 0x3D;
  return 0;
}

void oledTask(void *) {
  Wire1.begin(OLED_SDA, OLED_SCL, OLED_I2C_HZ);
  Wire1.setTimeOut(20);
  uint32_t lastCheckMs = millis() - 1000;
  TickType_t wake = xTaskGetTickCount();
  for (;;) {
    vTaskDelayUntil(&wake, pdMS_TO_TICKS(1000 / DISPLAY_HZ));
    const uint32_t now = millis();
    if (now - lastCheckMs >= 1000) {  // once a second: is the OLED (still) there?
      lastCheckMs = now;
      const uint8_t found = oledFind();
      if (!found) {
        oledOk = false;
      } else if (!oledOk || found != oledAddr) {  // new or re-plugged: initialise it
        oledOk = display.begin(SSD1306_SWITCHCAPVCC, found, false, false);
        oledAddr = found;
      }
    }
    if (!oledOk) continue;
    View v;
    portENTER_CRITICAL(&viewLock);
    v = sharedView;
    portEXIT_CRITICAL(&viewLock);
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    if (v.imuState != IMU_OK) {
      drawNoImu(v);
    } else if (v.accelCalActive) {
      drawAccelCal(v);
    } else {
      drawNormal(v);
    }
    display.display();
  }
}

#if WIFI_LINK
// ============================================================================
// Wi-Fi link task (core 0): joins Wi-Fi, serves one TCP client and sends it the lines `tee` collected.
// Only this task ever waits for the network; the sampling loop on core 1 never does.
// ============================================================================
WiFiServer linkServer(LINK_PORT);

void linkDiscard() {  // only from the link task (linkOut's single reader)
  static uint8_t junk[256];
  while (xStreamBufferReceive(linkOut, junk, sizeof junk, 0) > 0) {
  }
}

void linkTask(void *) {
  WiFi.setHostname(LINK_HOSTNAME);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);  // Wi-Fi power save holds packets back for 100+ ms
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  uint32_t joinStartMs = millis(), lastRssiMs = 0;
  bool serving = false;
  WiFiClient client;
  static uint8_t chunk[1024];
  for (;;) {
    const uint32_t now = millis();
    if (WiFi.status() != WL_CONNECTED) {
      if (linkClient) {
        linkClient = false;
        client.stop();
      }
      linkIp = 0;
      linkState = LINK_JOINING;
      linkDiscard();
      if (now - joinStartMs >= LINK_REJOIN_MS) {  // still not joined (e.g. the network was off at boot): try again
        joinStartMs = now;
        WiFi.disconnect();
        WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
      }
      vTaskDelay(pdMS_TO_TICKS(100));
      continue;
    }
    joinStartMs = now;
    if (!serving) {  // first join: the server and the .local name then stay up across Wi-Fi drops
      linkServer.begin();
      linkServer.setNoDelay(true);
      MDNS.begin(LINK_HOSTNAME);
      MDNS.addService("truerehab-imu", "tcp", LINK_PORT);
      serving = true;
    }
    linkIp = (uint32_t)WiFi.localIP();
    if (now - lastRssiMs >= 1000) {
      lastRssiMs = now;
      linkRssi = (int8_t)WiFi.RSSI();
    }

    WiFiClient incoming = linkServer.accept();
    if (incoming) {  // a new client replaces the old one (e.g. the recorder reconnecting after a drop)
      linkClient = false;
      client.stop();
      client = incoming;
      client.setNoDelay(true);
      linkDiscard();  // nothing from before this client
      linkClients = linkClients + 1;
      linkClient = true;
      linkHello = true;
    } else if (linkClient && !client.connected()) {
      linkClient = false;
      client.stop();
    }
    linkState = linkClient ? LINK_STREAMING : LINK_UP;
    if (!linkClient) {
      linkDiscard();
      vTaskDelay(pdMS_TO_TICKS(20));
      continue;
    }

    while (client.available() > 0) {  // keys typed by the client
      const int c = client.read();
      if (c < 0) break;
      const uint8_t b = (uint8_t)c;
      xStreamBufferSend(linkKeys, &b, 1, 0);
    }
    // Take what is waiting; if nothing is, wait for 1 KB or 20 ms. Sent as one packet: ~50 packets/s.
    const size_t n = xStreamBufferReceive(linkOut, chunk, sizeof chunk, pdMS_TO_TICKS(20));
    if (n > 0 && client.write(chunk, n) != n) {  // the client closed, or took nothing for ~10 s
      linkClient = false;
      client.stop();
      linkSendFails = linkSendFails + 1;
    }
  }
}
#endif

void publishView() {
  const uint32_t now = millis();
  view.imuState = imuState;
  strncpy(view.problem, imuProblem, sizeof view.problem);
  view.i2cErrors = i2cErrors;
  view.errRecent = i2cErrors && now - lastErrMs < 5000;
  view.satRecent = satSamples && now - lastSatMs < 1000;
  view.gyroCal = gyroCal;
  view.gyroCalPct = gyroCal == CAL_RUNNING ? (uint8_t)(100 * gyroWin.n / GYRO_CAL_SAMPLES) : 0;
  view.accelCalValid = accelCalValid;
  view.accelCalActive = acr.active;
  view.accelDone = acr.done;
  view.accelFace = acr.now;
  view.accelPct = (uint8_t)(100 * min(acr.win.n, ACCEL_FACE_SAMPLES) / ACCEL_FACE_SAMPLES);
  view.buttonLong = buttonLong;
#if WIFI_LINK
  view.linkState = linkState;
  view.linkIp = linkIp;
#endif
  portENTER_CRITICAL(&viewLock);
  sharedView = view;
  portEXIT_CRITICAL(&viewLock);
  lastPublishMs = now;
}

// ============================================================================
// Sampling
// ============================================================================
void afterConnect() {
  imuState = IMU_OK;
  readFails = frozenRun = 0;
  havePrev = false;
  filterSeeded = false;
  applyStoredAccelCal();
  if (gyroCal == CAL_NONE) startGyroCal("start-up");
  nextSampleUs = micros();
  lastVerifyMs = millis();
  publishView();
}

// Something is wrong with the IMU: reconnect now; if that fails, retry once a second.
void recoverImu(const char *why) {
  recoveries++;
  if (recoveries >= 3 && mpuI2cHz > 100000) {
    mpuI2cHz = 100000;
    tee.println("# imu bus slowed to 100 kHz after repeated errors");
  }
  tee.printf("# imu problem: %s - reconnecting\n", why);
  if (imuConnect()) {
    tee.println("# imu reconnected");
    afterConnect();
    return;
  }
  imuState = IMU_LOST;
  lastRetryMs = millis();
  printProblem("# imu lost: ");
  strncpy(lastPrintedProblem, imuProblem, sizeof lastPrintedProblem);
  publishView();
}

void takeSample() {
  Raw r;
  const uint32_t tUs = micros();
  const uint32_t tMs = millis();
  if (!mpuReadSample(r)) {
    i2cErrors++;
    lastErrMs = tMs;
    if (++readFails >= 3) recoverImu("reads failing");  // a single glitch only skips that sample
    return;
  }
  readFails = 0;

  // A working sensor never repeats all six axes for long: identical data = it stopped updating.
  if (havePrev && r.ax == prevRaw.ax && r.ay == prevRaw.ay && r.az == prevRaw.az && r.gx == prevRaw.gx &&
      r.gy == prevRaw.gy && r.gz == prevRaw.gz) {
    if (++frozenRun >= FROZEN_LIMIT) {
      frozenEvents++;
      recoverImu("data frozen");
      return;
    }
  } else {
    frozenRun = 0;
  }
  prevRaw = r;
  havePrev = true;
  samplesRead++;

  const int16_t axes[6] = {r.ax, r.ay, r.az, r.gx, r.gy, r.gz};
  for (int16_t v : axes) {
    if (v == 32767 || v == -32768) {
      satSamples++;
      lastSatMs = tMs;
      break;
    }
  }

  const float an[3] = {r.ax / ACC_LSB_PER_G, r.ay / ACC_LSB_PER_G, r.az / ACC_LSB_PER_G};    // g, nominal
  const float gr[3] = {r.gx / GYRO_LSB_PER_DPS, r.gy / GYRO_LSB_PER_DPS, r.gz / GYRO_LSB_PER_DPS};  // deg/s
  float ac[3];
  accelCorrect(an, ac);
  const float mag = sqrtf(ac[0] * ac[0] + ac[1] * ac[1] + ac[2] * ac[2]);

  gyroCalFeed(gr, ac, mag);
  accelCalFeed(an, gr);

  const float gc[3] = {gr[0] - gyroBias[0], gr[1] - gyroBias[1], gr[2] - gyroBias[2]};
  lastTempC = tempFromRaw(r.temp);

  const float dt = (tUs - lastSampleUs) * 1e-6f;
  lastSampleUs = tUs;
  if (!filterSeeded || dt <= 0 || dt > 0.1f) {
    ahrs.seed(ac);
    filterSeeded = true;
  } else {
    const bool useAccel = fabsf(mag - gRest) < ACCEL_GATE * gRest;
    ahrs.update(gc[0] * D2R, gc[1] * D2R, gc[2] * D2R, ac[0], ac[1], ac[2], useAccel, dt);
  }
  pitchDeg = ahrs.pitchDeg();
  rollDeg = ahrs.rollDeg();

  char line[112];
  int n = 0;
#if RECORD_MODE
  n = snprintf(line, sizeof line, "I,%lu,%ld,%ld,%ld,%ld,%ld,%ld\n", (unsigned long)tUs, r.ax * REC_ACC_MULT,
               r.ay * REC_ACC_MULT, r.az * REC_ACC_MULT, r.gx * REC_GYRO_MULT, r.gy * REC_GYRO_MULT,
               r.gz * REC_GYRO_MULT);
#else
  if (!liveStarted && (gyroCal != CAL_RUNNING || tMs - gyroCalStartMs >= LIVE_WAIT_CAL_MS)) {
    liveStarted = true;
    printCsvHeader();
  }
  if (liveStarted) {
    n = snprintf(line, sizeof line, "%lu,%.3f,%.3f,%.3f,%.2f,%.2f,%.2f,%.1f,%.1f,%.1f\n", (unsigned long)tMs, ac[0],
                 ac[1], ac[2], gc[0], gc[1], gc[2], lastTempC, pitchDeg, rollDeg);
  }
#endif
  if (n > 0) {
    tee.write((const uint8_t *)line, n);
    samplesOut++;
  }

  for (int i = 0; i < 3; i++) {
    view.a[i] = ac[i];
    view.g[i] = gc[i];
  }
  view.tempC = lastTempC;
  view.pitch = pitchDeg;
  view.roll = rollDeg;
}

// ============================================================================
// Keys, BOOT button, periodic work
// ============================================================================
int nextKey() {  // USB first, then the Wi-Fi client; -1 = none
  if (Serial.available()) return Serial.read();
#if WIFI_LINK
  uint8_t b;
  if (linkKeys && xStreamBufferReceive(linkKeys, &b, 1, 0) == 1) return b;
#endif
  return -1;
}

void handleCommands() {
  for (int key; (key = nextKey()) >= 0;) {
    switch (key) {
      case 'c': startGyroCal("key c"); break;
      case 'a': startAccelCal("key a"); break;
      case 'x':
        if (acr.active) stopAccelCal("key x");
        break;
      case 'X': eraseAccelCal(); break;
      case '?':
      case 'h':
        printHeader();
        printStatus();
        printHelp();
        printDebug();
        break;
      default: break;  // Enter, spaces, anything else
    }
  }
}

void handleBootButton() {
#if USE_BOOT_BUTTON
  static bool wasDown = false;
  static uint32_t downMs = 0;
  const bool down = digitalRead(BUTTON_PIN) == LOW;
  const uint32_t now = millis();
  if (down && !wasDown) downMs = now;
  buttonLong = down && now - downMs >= 3000;
  if (!down && wasDown) {  // act on release, so holding it never triggers twice
    const uint32_t held = now - downMs;
    if (held >= 3000) {
      if (!acr.active) startAccelCal("BOOT held");
    } else if (held >= 50) {
      if (acr.active) {
        stopAccelCal("BOOT pressed");
      } else {
        startGyroCal("BOOT pressed");
      }
    }
  }
  wasDown = down;
#endif
}

void service() {
  handleCommands();
  handleBootButton();
  const uint32_t now = millis();
#if WIFI_LINK
  if (linkHello) {  // a Wi-Fi client just connected: tell it what's coming now, not at the next repeat
    linkHello = false;
    printHeader();
    printStatus();
  }
#endif

  if (imuState == IMU_OK && now - lastVerifyMs >= VERIFY_EVERY_MS) {
    lastVerifyMs = now;
    const int check = mpuCheck();
    if (check == 1) {
      i2cErrors++;
      lastErrMs = now;
    } else if (check == 2) {
      recoverImu("sensor settings lost (power glitch?)");
    }
  }
  if (now - rateWindowMs >= 1000) {
    view.rateHz = (samplesRead - rateWindowSamples) * 1000.0f / (now - rateWindowMs);
    rateWindowMs = now;
    rateWindowSamples = samplesRead;
  }
  if (now - lastStatusMs >= STATUS_EVERY_MS) {
    lastStatusMs = now;
    printStatus();
  }
#if RECORD_MODE
  if (now - lastHeaderMs >= HEADER_EVERY_MS) {
    lastHeaderMs = now;
    printHeader();
  }
#endif
  const int present = oledOk ? 1 : 0;
  if (present != oledReported && (present || now - bootMs > 2000)) {
    oledReported = present;
    if (present) {
      tee.printf("# oled ok at 0x%02X\n", oledAddr);
    } else {
      tee.printf("# oled not found on SDA%d/SCL%d (data continues without it)\n", OLED_SDA, OLED_SCL);
    }
  }
  if (now - lastPublishMs >= 50) publishView();
}

// ============================================================================
// setup / loop
// ============================================================================
void setup() {
  Serial.setTxBufferSize(4096);  // printing never waits for the USB-serial chip
  Serial.begin(SERIAL_BAUD);
  bootMs = millis();
#if USE_BOOT_BUTTON
  pinMode(BUTTON_PIN, INPUT_PULLUP);
#endif
  xTaskCreatePinnedToCore(oledTask, "oled", 8192, nullptr, 1, &oledTaskHandle, 0);  // core 0
#if WIFI_LINK
  linkOut = xStreamBufferCreate(LINK_BUF_BYTES, 1024);  // an idle link task wakes at 1 KB (or after 20 ms)
  linkKeys = xStreamBufferCreate(64, 1);
  if (linkOut && linkKeys) {
    xTaskCreatePinnedToCore(linkTask, "link", 8192, nullptr, 2, &linkTaskHandle, 0);  // core 0, with Wi-Fi
  }
#endif
  loadStoredAccelCal();

  tee.printf("\n# TrueRehab-RF IMU firmware %s  mode=%s rate_hz=%lu baud=%lu\n", FW_VERSION,
             RECORD_MODE ? "record" : "live", (unsigned long)SAMPLE_HZ, (unsigned long)SERIAL_BAUD);
#if WIFI_LINK
  if (linkTaskHandle) {
    tee.printf("# wifi link: joining \"%s\", then tcp port %u at %s.local\n", WIFI_SSID, LINK_PORT, LINK_HOSTNAME);
  } else {
    tee.println("# wifi link: not enough memory - USB only");
  }
#endif
  if (imuConnect()) {
    afterConnect();
  } else {
    imuState = IMU_SEARCHING;
    lastRetryMs = millis();
    printProblem("# imu not found: ");
    strncpy(lastPrintedProblem, imuProblem, sizeof lastPrintedProblem);
  }
  printHeader();
  printHelp();
  lastStatusMs = lastHeaderMs = rateWindowMs = millis();
  publishView();
}

void loop() {
  if (imuState != IMU_OK) {  // no IMU: keep the screen, keys and status alive, retry once a second
    service();
    if (millis() - lastRetryMs >= RETRY_EVERY_MS) {
      lastRetryMs = millis();
      if (imuConnect()) {
        tee.println(chipKnown && recoveries ? "# imu reconnected" : "# imu found");
        afterConnect();
        printHeader();
      } else if (strcmp(imuProblem, lastPrintedProblem) != 0) {
        printProblem("# imu not found: ");
        strncpy(lastPrintedProblem, imuProblem, sizeof lastPrintedProblem);
      }
    }
    delay(5);
    return;
  }

  // Fixed-rate schedule on the microsecond clock. Far from the next sample: sleep a tick;
  // close: spin, so the sample is taken on time.
  const int32_t wait = (int32_t)(nextSampleUs - micros());
  if (wait > 0) {
    if (wait > 2500) vTaskDelay(1);
    return;
  }
  // A whole slot late (a failed I2C read, a flash write): count the missed slots and restart the
  // schedule. No catch-up burst: a read <1 ms after the last returns the same sensor data again.
  if (-wait >= (int32_t)PERIOD_US) {
    skipped += (uint32_t)(-wait) / PERIOD_US;
    nextSampleUs = micros();
  }
  nextSampleUs += PERIOD_US;
  takeSample();
  service();
}

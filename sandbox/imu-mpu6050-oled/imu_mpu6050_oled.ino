/*
 * TrueRehab-RF (AEII 2026) - IMU ground-truth firmware
 * ----------------------------------------------------
 * Board : ESP32 (3.3 V)
 * Sensor: MPU-6050 6-axis IMU (accel + gyro + temp), I2C addr 0x68
 * Screen: SSD1306 128x64 OLED, I2C addr 0x3C
 *
 * Shared I2C bus (ESP32 default):
 *   MPU-6050 VCC -> 3V3        OLED VCC -> 3V3
 *   MPU-6050 GND -> GND        OLED GND -> GND
 *   MPU-6050 SDA -> GPIO 21    OLED SDA -> GPIO 21
 *   MPU-6050 SCL -> GPIO 22    OLED SCL -> GPIO 22
 *   (MPU-6050 AD0 -> GND keeps its address at 0x68)
 *
 * The OLED shows live accel (g), gyro (deg/s), temperature and a
 * complementary-filtered pitch/roll angle. The same values are streamed
 * over Serial as CSV so the notebook can log them as radar ground truth.
 *
 * Libraries (Arduino Library Manager):
 *   - Adafruit MPU6050
 *   - Adafruit SSD1306
 *   - Adafruit GFX Library
 *   - Adafruit Unified Sensor   (pulled in by the above)
 *
 * This is a development / validation tool (IMU ground truth), not part of
 * the final radar-only product. See CLAUDE/PROJECT.md non-goals.
 */

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

// ---- Pin / bus configuration -------------------------------------------
#define I2C_SDA        21
#define I2C_SCL        22
#define I2C_FREQ_HZ    400000UL   // 400 kHz fast-mode I2C

// ---- OLED configuration -------------------------------------------------
#define SCREEN_WIDTH   128
#define SCREEN_HEIGHT  64
#define OLED_RESET     -1         // no dedicated reset pin on most modules
#define OLED_ADDR      0x3C

// ---- Mode ---------------------------------------------------------------
// 0 = standalone: human-readable CSV + OLED (pair with log_imu.py).
// 1 = record:     emits the recorder's raw line
//                   I,<micros>,ax,ay,az,gx,gy,gz
//                 int16 register counts (16384/g @ +-2 g, 131/(deg/s) @
//                 +-250 deg/s) at 200 Hz on 921600 baud. Plugs into
//                 recorder/record.py as  --imu <port>  (a SerialLineSource;
//                 read back with session.record_mode("imu", "I")). Matches
//                 firmware/myoware_record's IMU format. OLED still shows
//                 pitch/roll as a live check.
#define RECORD_MODE    0

#if RECORD_MODE
  #define SERIAL_BAUD  921600UL   // matches record.py --imu-baud default
  #define SAMPLE_HZ    200        // recorder's documented IMU rate
#else
  #define SERIAL_BAUD  115200UL
  #define SAMPLE_HZ    50         // plenty for the live display + log_imu.py
#endif
#define DISPLAY_HZ     10         // OLED refresh rate (OLED I2C is slow)

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
Adafruit_MPU6050 mpu;

// Complementary filter state (fused pitch/roll in degrees)
float pitch = 0.0f;
float roll  = 0.0f;
const float ALPHA = 0.98f;        // trust gyro 98% / accel 2% per step

// Gyro resting bias (rad/s), measured at startup while the board is still.
// Subtracted from every reading to cut pitch/roll drift.
float gyroBiasX = 0.0f;
float gyroBiasY = 0.0f;
float gyroBiasZ = 0.0f;
#define GYRO_CAL_SAMPLES 600      // ~ a couple of seconds at the read rate

uint32_t lastSampleUs  = 0;
uint32_t lastDisplayMs = 0;

// Latest sensor values (kept global so display + serial share them)
sensors_event_t accel, gyro, temp;

// ------------------------------------------------------------------------
void haltWithMessage(const char *msg) {
  // Show a fatal message on the OLED (if it came up) and the Serial log,
  // then stop. Easier to diagnose than a silent hang.
  Serial.print(F("FATAL: "));
  Serial.println(msg);
  display.clearDisplay();
  display.setCursor(0, 0);
  display.println(F("FATAL:"));
  display.println(msg);
  display.display();
  while (true) {
    delay(1000);
  }
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(200);

  Wire.begin(I2C_SDA, I2C_SCL, I2C_FREQ_HZ);

  // --- OLED first so we can report later errors on screen ---
  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
    Serial.println(F("FATAL: SSD1306 not found at 0x3C"));
    while (true) delay(1000);
  }
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println(F("TrueRehab-RF IMU"));
  display.println(F("booting..."));
  display.display();

  // --- MPU-6050 ---
  if (!mpu.begin(0x68, &Wire)) {
    haltWithMessage("MPU6050 0x68?");
  }
#if RECORD_MODE
  // +-2 g / +-250 deg/s so the raw counts match the recorder's assumed
  // scale (16384 LSB/g, 131 LSB/(deg/s)) - same as firmware/myoware_record.
  mpu.setAccelerometerRange(MPU6050_RANGE_2_G);
  mpu.setGyroRange(MPU6050_RANGE_250_DEG);
#else
  mpu.setAccelerometerRange(MPU6050_RANGE_4_G);     // +/-4 g: rehab motion
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);          // +/-500 deg/s
#endif
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);       // smooth out tremor noise

  // Measure the gyro's resting offset. The board MUST be still for this.
  calibrateGyro();

  // Seed pitch/roll from the first accelerometer reading so the filter
  // doesn't have to drift up from zero.
  mpu.getEvent(&accel, &gyro, &temp);
  roll  = atan2f(accel.acceleration.y, accel.acceleration.z) * 57.2957795f;
  pitch = atan2f(-accel.acceleration.x,
                 sqrtf(accel.acceleration.y * accel.acceleration.y +
                       accel.acceleration.z * accel.acceleration.z)) * 57.2957795f;

#if RECORD_MODE
  Serial.println(F("# truerehab-imu-record v1 imu=mpu6050_200hz scale=2g_250dps"));
  Serial.println(F("# I,micros,ax,ay,az,gx,gy,gz  (raw int16; 16384/g, 131/(deg/s))"));
#else
  Serial.println(F("# TrueRehab-RF IMU ground truth"));
  Serial.println(F("# t_ms,ax_g,ay_g,az_g,gx_dps,gy_dps,gz_dps,temp_c,pitch_deg,roll_deg"));
#endif

  lastSampleUs  = micros();
  lastDisplayMs = millis();
}

void loop() {
  const uint32_t nowUs = micros();
  if (nowUs - lastSampleUs < (1000000UL / SAMPLE_HZ)) {
    return;  // not time for the next sample yet
  }
  const float dt = (nowUs - lastSampleUs) * 1e-6f;   // seconds since last sample
  lastSampleUs = nowUs;

  mpu.getEvent(&accel, &gyro, &temp);

#if RECORD_MODE
  // Emit the recorder's raw line from the UNCORRECTED reading - offline
  // tools handle the bias. Must come before the display bias subtraction.
  emitRecordLine(nowUs);
#endif

  // Remove the resting bias measured at startup (rad/s). Display only.
  gyro.gyro.x -= gyroBiasX;
  gyro.gyro.y -= gyroBiasY;
  gyro.gyro.z -= gyroBiasZ;

  // Accelerometer-only angle estimate (noisy, no drift)
  const float accRoll  = atan2f(accel.acceleration.y, accel.acceleration.z) * 57.2957795f;
  const float accPitch = atan2f(-accel.acceleration.x,
                                sqrtf(accel.acceleration.y * accel.acceleration.y +
                                      accel.acceleration.z * accel.acceleration.z)) * 57.2957795f;

  // Gyro gives deg/s; integrate for a smooth short-term angle.
  const float gyroRollRate  = gyro.gyro.x * 57.2957795f;
  const float gyroPitchRate = gyro.gyro.y * 57.2957795f;

  // Complementary filter: fuse the two.
  roll  = ALPHA * (roll  + gyroRollRate  * dt) + (1.0f - ALPHA) * accRoll;
  pitch = ALPHA * (pitch + gyroPitchRate * dt) + (1.0f - ALPHA) * accPitch;

#if !RECORD_MODE
  // --- Serial CSV (every sample) for notebook logging ---
  Serial.print(millis());                      Serial.print(',');
  Serial.print(accel.acceleration.x / 9.80665f, 3); Serial.print(',');  // g
  Serial.print(accel.acceleration.y / 9.80665f, 3); Serial.print(',');
  Serial.print(accel.acceleration.z / 9.80665f, 3); Serial.print(',');
  Serial.print(gyro.gyro.x * 57.2957795f, 2);  Serial.print(',');       // deg/s
  Serial.print(gyro.gyro.y * 57.2957795f, 2);  Serial.print(',');
  Serial.print(gyro.gyro.z * 57.2957795f, 2);  Serial.print(',');
  Serial.print(temp.temperature, 1);           Serial.print(',');       // deg C
  Serial.print(pitch, 1);                      Serial.print(',');
  Serial.println(roll, 1);
#endif

  // --- OLED (rate-limited) ---
  const uint32_t nowMs = millis();
  if (nowMs - lastDisplayMs >= (1000UL / DISPLAY_HZ)) {
    lastDisplayMs = nowMs;
    updateDisplay();
  }
}

// Average many gyro samples while the board sits still and store the mean
// as the resting bias. Call once at startup. Blocks for ~2 s.
void calibrateGyro() {
  Serial.println(F("# calibrating gyro - keep the board still"));
  display.clearDisplay();
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println(F("Calibrating gyro"));
  display.println(F("keep it STILL..."));
  display.display();

  double sx = 0.0, sy = 0.0, sz = 0.0;
  sensors_event_t a, g, t;
  for (int i = 0; i < GYRO_CAL_SAMPLES; i++) {
    mpu.getEvent(&a, &g, &t);
    sx += g.gyro.x;
    sy += g.gyro.y;
    sz += g.gyro.z;
    delay(3);
  }
  gyroBiasX = (float)(sx / GYRO_CAL_SAMPLES);
  gyroBiasY = (float)(sy / GYRO_CAL_SAMPLES);
  gyroBiasZ = (float)(sz / GYRO_CAL_SAMPLES);

  Serial.print(F("# gyro bias rad/s: "));
  Serial.print(gyroBiasX, 5); Serial.print(' ');
  Serial.print(gyroBiasY, 5); Serial.print(' ');
  Serial.println(gyroBiasZ, 5);
}

#if RECORD_MODE
// Print the recorder's raw line: I,<micros>,ax,ay,az,gx,gy,gz
// Converts the library's SI values back to int16 register counts at the
// +-2 g / +-250 deg/s scale. Call with the UNCORRECTED reading (no bias
// removal) so offline processing matches firmware/myoware_record.
void emitRecordLine(uint32_t tDevUs) {
  const float COUNTS_PER_G   = 16384.0f;   // +-2 g full scale
  const float COUNTS_PER_DPS = 131.0f;     // +-250 deg/s full scale
  const float RAD2DEG        = 57.2957795f;
  const int16_t ax = (int16_t)lroundf(accel.acceleration.x / 9.80665f * COUNTS_PER_G);
  const int16_t ay = (int16_t)lroundf(accel.acceleration.y / 9.80665f * COUNTS_PER_G);
  const int16_t az = (int16_t)lroundf(accel.acceleration.z / 9.80665f * COUNTS_PER_G);
  const int16_t gx = (int16_t)lroundf(gyro.gyro.x * RAD2DEG * COUNTS_PER_DPS);
  const int16_t gy = (int16_t)lroundf(gyro.gyro.y * RAD2DEG * COUNTS_PER_DPS);
  const int16_t gz = (int16_t)lroundf(gyro.gyro.z * RAD2DEG * COUNTS_PER_DPS);
  char buf[72];
  snprintf(buf, sizeof(buf), "I,%lu,%d,%d,%d,%d,%d,%d",
           (unsigned long)tDevUs, ax, ay, az, gx, gy, gz);
  Serial.println(buf);
}
#endif

void updateDisplay() {
  display.clearDisplay();
  display.setTextSize(1);

  // Header
  display.setCursor(0, 0);
  display.print(F("IMU  "));
  display.print(temp.temperature, 1);
  display.println(F(" C"));

  // Accel (g)
  display.setCursor(0, 12);
  display.print(F("a "));
  display.print(accel.acceleration.x / 9.80665f, 2); display.print(' ');
  display.print(accel.acceleration.y / 9.80665f, 2); display.print(' ');
  display.print(accel.acceleration.z / 9.80665f, 2);

  // Gyro (deg/s)
  display.setCursor(0, 22);
  display.print(F("w "));
  display.print(gyro.gyro.x * 57.2957795f, 0); display.print(' ');
  display.print(gyro.gyro.y * 57.2957795f, 0); display.print(' ');
  display.print(gyro.gyro.z * 57.2957795f, 0);

  // Fused angles (large, the useful rehab number)
  display.setTextSize(2);
  display.setCursor(0, 38);
  display.print(F("P"));
  display.print(pitch, 0);
  display.setCursor(64, 38);
  display.print(F("R"));
  display.print(roll, 0);

  display.display();
}

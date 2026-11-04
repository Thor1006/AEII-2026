/*
 * TrueRehab-RF (AEII 2026) - I2C wiring check (ESP32)
 * ---------------------------------------------------
 * Diagnostic for the two buses used by imu_mpu6050_oled.ino. Upload it when the main sketch
 * can't find the IMU or the OLED, then open the Serial Monitor at 115200 baud.
 *
 *   IMU bus  (Wire):  SDA -> GPIO 27, SCL -> GPIO 26   expect 0x68 (0x69 if AD0 is high)
 *   OLED bus (Wire1): SDA -> GPIO 32, SCL -> GPIO 33   expect 0x3C (some modules 0x3D)
 *   Power both from 3V3.
 *
 * For each bus, every 5 s (so you can re-wire while it runs):
 *   1. line check: is there a pull-up on SDA/SCL, is a line stuck LOW (short / unpowered module)?
 *   2. frees a stuck bus (clocks SCL until SDA is released)
 *   3. lists every address that answers, with timeouts, and reads the IMU's WHO_AM_I
 *   4. one-line verdict
 */

#include <Wire.h>

struct Bus {
  TwoWire *wire;
  const char *name;
  int sda, scl;
  uint8_t expectA, expectB;  // the addresses this project expects on the bus
};

Bus buses[] = {
    {&Wire, "IMU bus ", 27, 26, 0x68, 0x69},
    {&Wire1, "OLED bus", 32, 33, 0x3C, 0x3D},
};

constexpr uint32_t SCAN_HZ = 100000;  // 100 kHz: the most forgiving speed for a scan

// What the line does on its own: an external pull-up (a few kOhm) beats the ESP32's ~45 kOhm
// internal pull-down; with the internal pull-up on, a line that still reads LOW is held down.
const char *lineState(int pin, bool *stuckLow) {
  pinMode(pin, INPUT_PULLDOWN);
  delayMicroseconds(100);
  const bool externalPullup = digitalRead(pin) == HIGH;
  pinMode(pin, INPUT_PULLUP);
  delayMicroseconds(100);
  const bool high = digitalRead(pin) == HIGH;
  pinMode(pin, INPUT);
  *stuckLow = !high;
  if (!high) return "STUCK LOW";
  return externalPullup ? "ok (pull-up found)" : "no external pull-up";
}

// Clock SCL until a device that was cut off mid-byte lets go of SDA, then send a STOP.
bool busClear(int sda, int scl) {
  pinMode(scl, OUTPUT_OPEN_DRAIN | PULLUP);
  pinMode(sda, INPUT_PULLUP);
  for (int i = 0; i < 9 && digitalRead(sda) == LOW; i++) {
    digitalWrite(scl, LOW);
    delayMicroseconds(10);
    digitalWrite(scl, HIGH);
    delayMicroseconds(10);
  }
  pinMode(sda, OUTPUT_OPEN_DRAIN | PULLUP);
  digitalWrite(sda, LOW);
  delayMicroseconds(10);
  digitalWrite(sda, HIGH);
  delayMicroseconds(10);
  pinMode(sda, INPUT_PULLUP);
  pinMode(scl, INPUT_PULLUP);
  delayMicroseconds(100);
  return digitalRead(sda) == HIGH;
}

const char *imuName(uint8_t id) {
  switch (id) {
    case 0x68: return "MPU-6050 (genuine ID)";
    case 0x70: return "MPU-6500";
    case 0x71: return "MPU-9250";
    case 0x73: return "MPU-9255";
    case 0x74: return "MPU-6515 ID, MPU-6500 family";
    case 0x78: return "MPU-6880";
    case 0x98: return "ICM-20689";
    case 0x12: return "ICM-20602";
    case 0x11: return "ICM-20600";
    case 0xAF: return "ICM-20608";
    default: return "unknown ID - a clone; the main sketch tries it anyway";
  }
}

const char *knownName(uint8_t addr) {
  switch (addr) {
    case 0x68: return "MPU-6050 family (AD0 low)";
    case 0x69: return "MPU-6050 family (AD0 high)";
    case 0x3C:
    case 0x3D: return "SSD1306 OLED";
    default: return "?";
  }
}

void checkBus(Bus &b) {
  Serial.printf("%s  SDA=GPIO%d  SCL=GPIO%d\n", b.name, b.sda, b.scl);

  b.wire->end();  // free the pins for the line check
  bool sdaLow = false, sclLow = false;
  const char *sdaState = lineState(b.sda, &sdaLow);
  const char *sclState = lineState(b.scl, &sclLow);
  Serial.printf("  lines: SDA %s, SCL %s\n", sdaState, sclState);
  if (sclLow) {
    Serial.println("  SCL held LOW: short to GND, or a module without power (check VCC)");
  } else if (sdaLow) {
    Serial.printf("  SDA held LOW - trying to free the bus... %s\n",
                  busClear(b.sda, b.scl) ? "freed" : "still LOW: short to GND, or a module without power");
  }

  b.wire->begin(b.sda, b.scl, SCAN_HZ);
  b.wire->setTimeOut(20);
  int found = 0, timeouts = 0, otherErrors = 0;
  bool expected = false;
  for (uint8_t addr = 0x08; addr <= 0x77; addr++) {
    b.wire->beginTransmission(addr);
    const uint8_t err = b.wire->endTransmission();
    if (err == 5) timeouts++;
    if (err == 4) otherErrors++;
    if (err != 0) continue;
    found++;
    if (addr == b.expectA || addr == b.expectB) expected = true;
    Serial.printf("  found 0x%02X  %s", addr, knownName(addr));
    if (addr == 0x68 || addr == 0x69) {
      b.wire->beginTransmission(addr);
      b.wire->write(0x75);  // WHO_AM_I
      b.wire->endTransmission(false);
      if (b.wire->requestFrom(addr, (size_t)1) == 1) {
        const uint8_t id = b.wire->read();
        Serial.printf("  WHO_AM_I=0x%02X (%s)", id, imuName(id));
      } else {
        Serial.print("  WHO_AM_I read failed");
      }
    }
    Serial.println();
  }
  if (timeouts) Serial.printf("  %d timeouts: a line is held or very noisy\n", timeouts);
  if (otherErrors) Serial.printf("  %d other bus errors\n", otherErrors);

  if (expected) {
    Serial.printf("  => OK: 0x%02X/0x%02X answers\n", b.expectA, b.expectB);
  } else if (found) {
    Serial.printf("  => devices answer, but not the expected 0x%02X/0x%02X - wrong bus or wrong address\n",
                  b.expectA, b.expectB);
  } else {
    Serial.println("  => nothing answers: check VCC (3V3) and GND, SDA/SCL wires (swapped?), loose jumpers");
  }
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\nTrueRehab-RF I2C wiring check (scans every 5 s)");
}

void loop() {
  for (Bus &b : buses) checkBus(b);
  Serial.println();
  delay(5000);
}

/*
 * TrueRehab-RF (AEII 2026) - I2C scanner (ESP32)
 * ----------------------------------------------
 * Throwaway diagnostic: scans the I2C bus and prints every device address
 * it finds over Serial. Upload this FIRST to confirm wiring before running
 * imu_mpu6050_oled.ino.
 *
 * Expected on this project:
 *   0x68  MPU-6050   (0x69 if AD0 is tied HIGH instead of GND)
 *   0x3C  SSD1306 OLED   (some modules are 0x3D)
 *
 * Wiring is the same shared I2C bus as the main sketch:
 *   SDA -> GPIO 21,  SCL -> GPIO 22,  power both from 3V3.
 *
 * Open the Serial Monitor at 115200 baud.
 */

#include <Wire.h>

#define I2C_SDA     21
#define I2C_SCL     22
#define I2C_FREQ_HZ 100000UL   // 100 kHz is safest for a scan

void setup() {
  Serial.begin(115200);
  delay(300);
  Wire.begin(I2C_SDA, I2C_SCL, I2C_FREQ_HZ);
  Serial.println(F("\nTrueRehab-RF I2C scanner"));
  Serial.println(F("SDA=GPIO21  SCL=GPIO22"));
}

void loop() {
  byte count = 0;

  Serial.println(F("Scanning..."));
  for (byte addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    const byte err = Wire.endTransmission();

    if (err == 0) {
      count++;
      Serial.print(F("  found 0x"));
      if (addr < 16) Serial.print('0');
      Serial.print(addr, HEX);

      // Annotate the addresses we expect for this project.
      if (addr == 0x68)                 Serial.print(F("  <- MPU-6050"));
      else if (addr == 0x69)            Serial.print(F("  <- MPU-6050 (AD0 HIGH)"));
      else if (addr == 0x3C || addr == 0x3D) Serial.print(F("  <- SSD1306 OLED"));
      Serial.println();
    } else if (err == 4) {
      Serial.print(F("  error at 0x"));
      if (addr < 16) Serial.print('0');
      Serial.println(addr, HEX);
    }
  }

  if (count == 0) {
    Serial.println(F("  no devices found - check wiring/power"));
  } else {
    Serial.print(F("done, "));
    Serial.print(count);
    Serial.println(F(" device(s)"));
  }

  delay(3000);  // rescan every few seconds
}

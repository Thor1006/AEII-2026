// Wi-Fi network for the IMU board's Wi-Fi link (WIFI_LINK 1 in imu_mpu6050_oled.ino).
//
// Copy this file to wifi_secrets.h in this same folder, then put your network's name and password there.
// wifi_secrets.h is git-ignored, so the password stays on your computer. Never put a real password here.
//
// The ESP32 joins 2.4 GHz networks only. iPhone hotspot: turn on "Maximize Compatibility".
// School/enterprise (username + password) and guest networks usually won't work: use a home network or
// the phone hotspot, with the Mac on the same network.
#pragma once

#define WIFI_SSID "your-network-name"
#define WIFI_PASSWORD "your-wifi-password"

# Plan: fix the ESP32 + MPU IMU firmware

**Status:** done — user asked 2026-11-04 to "fix the firmware for the ESP32 and IMU thoroughly" and to minimize questions; verified on the real board ([report](../output/2026-11-04-2232-imu-firmware-fix.md)); left: 6-face accel calibration, BOOT button and OLED screens by eye, recording on a moving arm after the IMU wiring is fixed
**Date:** 2026-11-04

## Why
Measured on the connected board (ESP32 DevKit, CP2102 `/dev/cu.usbserial-0001`) running the local sketch:
- The chip answers WHO_AM_I **0x74** (MPU-6500-family clone, not a genuine 0x68 MPU-6050). The teammate's
  record-mode version (`660e66d`, Adafruit MPU6050 library) refuses any ID except 0x68, so it can't start here.
- OLED refreshes block the sampling loop ~29 ms: 50 Hz becomes ~46 Hz with uneven steps (20/29 ms). At the
  200 Hz record rate this would drop roughly a quarter of all samples in 25–30 ms gaps.
- Accelerometer magnitude at rest is 0.88 g (clone offsets/gain) → pitch/roll off by several degrees.
- Failures are silent or fatal: a lost read repeats the old values with a new timestamp; a missing OLED or
  IMU halts the board forever; no recovery if a wire comes loose mid-session; `display.begin()` never
  actually detects a missing OLED; gyro calibration accepts a moving board.
- Two divergent copies: local (two I2C buses, register driver, sketch moved into its own folder) and the
  teammate's (old shared bus, Adafruit library, record mode for `recorder/`).

## Approach
1. Sync to `origin/main` (fast-forward `660e66d`), keep local edits in `git stash` + scratchpad backup.
2. One sketch, `sandbox/imu-mpu6050-oled/imu_mpu6050_oled/imu_mpu6050_oled.ino`, merging both:
   - Two buses kept (MPU 27/26 on `Wire`, OLED 32/33 on `Wire1`); register-level driver for 0x68 and
     6500-family clones, accepted by config read-back rather than by ID.
   - Sampling in `loop()` on core 1 with a micros() schedule; OLED in its own FreeRTOS task on core 0,
     so screen writes never delay a sample.
   - Record mode from `660e66d`: `I,<micros>,ax,ay,az,gx,gy,gz` at 200 Hz / 921600 baud, counts at the
     recorder's documented 16384/g and 131/(°/s); default wide range ±4 g/±500 °/s (2×raw) so fast reps
     don't clip; `RECORD_WIDE_RANGE 0` gives the exact old ±2 g/±250 °/s raw int16.
   - Robustness: I2C bus clear, short timeouts, read-error/stale/frozen detection, config read-back every
     second, automatic reconnect (and 100 kHz fallback), OLED hot-plug, never halts.
   - Non-blocking gyro calibration with a stillness check (BOOT short press or `c` to redo).
   - Optional 6-face accelerometer calibration (`a` or hold BOOT 3 s), saved in flash, applied to the
     display/live CSV; record mode stays raw and reports the calibration in `#` lines.
   - Mahony quaternion filter instead of the small-angle complementary filter (same pitch/roll convention).
   - Self-describing `#` header + status lines every 5 s (rate, errors, skipped samples, bias, calibration).
3. I2C scanner: pull-up / stuck-line checks, bus clear, WHO_AM_I decode, timeouts reported.
4. `firmware/myoware_record` optional IMU path: accept 6500-family IDs too (same chip problem).
5. README (wiring, modes, calibration, troubleshooting), recorder README status line.

## Files touched
- `sandbox/imu-mpu6050-oled/imu_mpu6050_oled/imu_mpu6050_oled.ino` — rewritten sketch
- `sandbox/imu-mpu6050-oled/imu_mpu6050_oled.ino` — removed (old path; sketch lives in its folder)
- `sandbox/imu-mpu6050-oled/i2c_scanner/i2c_scanner.ino` — better diagnostics
- `sandbox/imu-mpu6050-oled/README.md`, `log_imu.py` (docs/port examples only)
- `firmware/myoware_record/myoware_record.ino` — IMU ID check only (USE_IMU stays 0)
- `recorder/README.md` — IMU status line

## Risks / needs OK
- Uploading sketches to the IMU ESP32 (not a radar board; reversible by re-uploading). Radar untouched.
- Record wide range changes values beyond int16 when motion exceeds ±2 g/±250 °/s (documented in `#` lines).
- Accel 6-face calibration needs a person to turn the board; only the first face can be tested unattended.

## How we'll verify
- `arduino-cli compile` for ESP32 Dev Module: live mode, record mode (wide + narrow), scanner, myoware_record with USE_IMU 1.
- On the board: scanner output; live mode rate/jitter/|a|/noise; record mode through `recorder/record.py --imu`
  and `session.record_mode("imu","I")`: 200 Hz, gaps, values; status lines; OLED task not stalling sampling.

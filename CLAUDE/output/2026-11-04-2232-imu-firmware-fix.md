# Report: ESP32 + MPU IMU firmware fix

<!-- Filename: YYYY-MM-DD-HHMM-<slug>.md -->

**Date:** 2026-11-04 22:32 · **Result:** ✅ done (6-face accel calibration, BOOT button and the OLED picture not exercised; IMU wiring is loose) · **Plan:** [plans/2026-11-04-imu-firmware-fix.md](../plans/2026-11-04-imu-firmware-fix.md)

## Goal
Make the IMU ground-truth firmware reliable on the actual board and able to feed the session recorder ("fix the firmware for the ESP32 and IMU thoroughly", minimal questions).

## Found on the board (CP2102 DevKit `/dev/cu.usbserial-0001`, before changes)
- Chip answers WHO_AM_I **0x74** (MPU-6500 family), not 0x68. The teammate's record-mode version (`660e66d`, Adafruit MPU6050 library) refuses that ID, so it could not start here.
- OLED refresh blocked the sampling loop ~29 ms: 45.85 Hz instead of 50, steps 20/29 ms. At the 200 Hz record rate about a quarter of the samples would have been lost.
- |a| at rest 0.88 g (upside down) and 1.05 g (on its side): clone accelerometer offset/gain, several degrees of angle error.
- Silent or fatal failures: a failed read reprinted old values with a new timestamp; a missing OLED or IMU halted forever; no recovery from a loose wire; `Adafruit_SSD1306::begin()` never detects a missing OLED; gyro calibration accepted a moving board.
- **IMU wiring is loose**: during the session the scanner, the old sketch and the new one all lost the IMU (missing pull-up on SCL, later SDA). It dropped while the board was being moved.
- Host side: on this Mac, opening the serial port replays one stale line ~50 times; the last copy is spliced onto a new line and passes `record_mode()` as a bad sample.

## What changed
- `sandbox/imu-mpu6050-oled/imu_mpu6050_oled/imu_mpu6050_oled.ino` — rewritten (fw 2.0); merges the local two-bus register driver with the teammate's record mode. Sampling in `loop()` on core 1 with a µs schedule, OLED in its own FreeRTOS task on core 0 (own bus). RECORD: `I,<micros>,…` at 200 Hz / 921600, counts at 16384/g and 131/(°/s), wide range ±4 g/±500 °/s by default (`RECORD_WIDE_RANGE 0` = old ±2 g/±250 °/s int16). Chip accepted by settings read-back. Bus clear, 5 ms I2C timeout, read-error/frozen/settings-lost detection, reconnect each second, 100 kHz fallback, pull-up diagnosis, OLED hot-plug, never halts. Missed slots counted, no catch-up bursts. Non-blocking gyro calibration with stillness check (BOOT press / `c`). 6-face accel calibration saved to flash (`a` / hold BOOT 3 s, `x`, `X`). Mahony filter instead of the small-angle complementary filter. `#` header (RECORD: every 10 s) and `# status` every 5 s. `IMU_SIMULATE` test build.
- `sandbox/imu-mpu6050-oled/imu_mpu6050_oled.ino` — removed (sketch now lives in its folder).
- `sandbox/imu-mpu6050-oled/i2c_scanner/i2c_scanner.ino` — line checks (pull-up / stuck), bus clear, timeouts, WHO_AM_I names, verdict per bus.
- `sandbox/imu-mpu6050-oled/log_imu.py` — drops the port-open replay; macOS port in usage.
- `sandbox/imu-mpu6050-oled/README.md` — rewritten (wiring, modes, `#` lines, calibration, recorder, troubleshooting, verified, limits).
- `firmware/myoware_record/myoware_record.ino` — optional IMU path accepts 6500-family IDs and sets their accel low-pass (USE_IMU stays 0).
- `recorder/rec/sources.py`, `recorder/rec/session.py`, `recorder/tests/test_recorder.py`, `recorder/README.md` — discard bytes from the first 50 ms after opening a serial port; `record_mode()` drops rows repeating the previous device time; new test; IMU board section and status lines.
- Git: `main` fast-forwarded to the teammate's `660e66d` (no new commit). The pre-sync local IMU edits are folded in and kept in `stash@{0}`.

## Verified by
- `arduino-cli compile` (ESP32 core 3.3.12, `-Wall -Wextra`): LIVE, RECORD wide, RECORD narrow, two simulated builds: no warnings. `myoware_record` with USE_IMU 0 and 1 compiles (only the existing `BluetoothSerial` deprecation warning).
- Real sensor, RECORD through `recorder/record.py --imu`, 40 s: 8032 samples, 200.00 Hz, steps 4999–5001 µs, no gaps, `skipped=0 i2c_err=0`, host alignment p99 0.32 ms, gyro noise 0.06 °/s.
- Real sensor, LIVE 10 s: every step 20 ms, gyro noise 0.05–0.07 °/s, angles steady to 0.06°. Gyro bias matches the old sketch (−1.0/1.3/0.7 °/s).
- While the wiring dropped out, the real board reconnected, switched to 100 kHz and reported the missing pull-up. An earlier 25 s recording showed one 10 ms I2C timeout (`i2c_err=2` in 107 s), which led to the 5 ms timeout and skipping missed slots instead of catching up.
- Simulated sensor on the same board: roll tracked a known ±60° swing within 0.9° RMS (2.0° max at 94 °/s). Keys `a` (captured +Z), `x`, `c` (refused while moving), `?` worked. OLED task stack 6.1 KB free.
- `recorder` unit tests: 9/9 OK.

## Issues / not done
- Not exercised: full 6-face accel calibration and its flash save, the BOOT button, and the OLED screens as seen by a person.
- IMU wiring drops out when the board moves; it must be soldered or strain-relieved before recording on an arm.
- Record wide range changes values beyond int16 when motion passes ±2 g/±250 °/s (documented in the `#` header).
- `BluetoothSerial` (MyoWare sketches) is deprecated for ESP32 core 4.0; fine on 3.3.12.
- The board was left running the LIVE build (repo default). `stash@{0}` still holds the pre-sync edits.

## Next
1. Solder or strain-relieve the four IMU wires, then run the 6-face accel calibration once (`a`, or hold BOOT 3 s).
2. Look at the OLED screens and press BOOT once to check them by eye.
3. Record radar + IMU (`RECORD_MODE 1`, `--imu /dev/cu.usbserial-0001`) with the shrug marker on a moving arm.
4. Commit when satisfied (new folder + deletions included), then `git stash drop`.

**Uncommitted work:** yes

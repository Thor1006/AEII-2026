# Plan: IMU board streams over Wi-Fi (or Bluetooth) instead of only USB

**Status:** done — user chose Wi-Fi (Recommended) on 2026-11-04; uploaded with the user's OK and verified on the board 2026-11-05 ([report](../output/2026-11-05-0012-imu-wifi-link.md)). Added on the way: IPv4-first name lookup (5 ms vs 5 s), lower-edge clock fit in `align_device_time` (37 ms wander → constant 4.1 ms), `link_stalls` renamed `link_send_fails`. Not tested: Wi-Fi off mid-recording, power bank, moving arm, hotspot/school network
**Date:** 2026-11-04

## Why
The user asked for the IMU ESP32 (`sandbox/imu-mpu6050-oled/`) to send its data "via bluetooth or on the WiFi".
A USB cable on a moving arm pulls on the board, and the MPU wiring already dropped out when the board moved
(Nov 4: 113 I2C errors and 29 bus restarts in 23 min). Today the data only leaves through USB serial.

## Recommendation: Wi-Fi (TCP), Bluetooth as the alternative
- **Wi-Fi:** the board joins your Wi-Fi network and the recorder connects to `tcp://truerehab-imu.local:3333`.
  TCP delivers every byte in order. Build: 991 KB (75 % of flash, measured with esp32 core 3.3.12).
- **Bluetooth Classic:** this would appear as `/dev/cu.TrueRehab-IMU` after pairing, with no recorder change. But
  it relies on the same Mac Bluetooth serial connection that will not connect to the MyoWare right now (Nov 4:
  the device is in range, macOS lists it "Not Connected", 0 bytes in 15 s). Build: 1,119 KB (85 %).
- The current build (USB only) is 337 KB (25 %). Both radio builds fit the default partition, so the upload
  command stays the same and the saved accelerometer calibration survives.

## Approach (Wi-Fi)
1. **Firmware option `WIFI_LINK`.** The default stays 0, which keeps the USB-only build behaving exactly as
   today. With 1, the board joins Wi-Fi as `truerehab-imu` (mDNS) with power save off and serves one TCP
   client on port 3333. A new client replaces the old one.
2. **Same output on both paths.** Every line still goes to USB. Complete lines are also copied into a 32 KB
   buffer that a separate task on core 0 sends to the TCP client. The 200 Hz sampling on core 1 never waits
   for the network. If the buffer fills, whole lines are dropped and counted (`link_dropped` in the status
   line), so the recorder never gets half a line.
3. **Board details over the link.**
   - On connect the board sends its header and status at once, instead of waiting up to 10 s for the repeat.
   - The keys `c`, `a`, `x`, `X` and `?` also work from the TCP client.
   - The status line adds `link=wifi ip=… rssi=… client=yes/no link_dropped=…`.
   - The OLED shows the Wi-Fi state and the IP address.
4. **Wi-Fi name and password** go in `wifi_secrets.h`. That file is git-ignored, and you fill it in yourself from
   `wifi_secrets.example.h`; I never open it. Building with `WIFI_LINK 1` and no secrets file stops with a
   message that says what to do.
5. **Recorder changes.**
   - `--imu tcp://truerehab-imu.local:3333` reads from a plain socket instead of through pyserial, which would
     read the network stream 1 byte per call.
   - If the link drops, the recorder writes `# recorder: link lost` / `# link back` rows and reconnects once a
     second; the gap shows in the device clock.
   - Serial ports work as before.
6. **Docs:** the IMU README gets a Wi-Fi section (setup, upload command, recorder command, troubleshooting). The
   recorder README and `record.py --help` get one line each. `.gitignore` gets `wifi_secrets.h`.

## Files touched
- `sandbox/imu-mpu6050-oled/imu_mpu6050_oled/imu_mpu6050_oled.ino`: the `WIFI_LINK` option, the output path that
  sends each line to both USB and Wi-Fi, the link task, keys from the link, the OLED/status additions.
- `sandbox/imu-mpu6050-oled/imu_mpu6050_oled/wifi_secrets.example.h` (new), `.gitignore`.
- `recorder/rec/sources.py`: `tcp://` sources, reconnects. `recorder/record.py`: help text.
- `recorder/tests/test_recorder.py`: a fake TCP IMU that drops the connection once mid-stream.
- `sandbox/imu-mpu6050-oled/README.md`, `recorder/README.md`.

## Risks / needs OK
- **Upload to the IMU ESP32:** I'll upload with the IDE's bundled `arduino-cli` only after you OK it, or you upload it.
- **Network:**
  - The classic ESP32 has 2.4 GHz Wi-Fi only.
  - School/enterprise and guest networks often block traffic between devices. Fallback: your iPhone's hotspot with
    "Maximize Compatibility" on, with both the Mac and the board joined to it.
  - Anyone on the same network can read the stream or send the calibration keys. That's fine at home; don't use it on
    public Wi-Fi.
- **Power:** for wireless use, run the board from a USB power bank.
- **Uncommitted edits:** the earlier IMU-fix edits to these files are uncommitted; this builds on them and keeps them.
- **Board reboot mid-session (unchanged limitation):** the device clock restarts, so that session's IMU timeline
  breaks. The reconnect handles Wi-Fi drops, not reboots.

## How we'll verify
- Compile all four builds: LIVE and RECORD, each with `WIFI_LINK` 0 and 1. The `WIFI_LINK 0` builds behave as
  before.
- Recorder tests: the existing 4 + 4 tests, plus the fake TCP IMU. Every line before and after the drop must be
  recorded, the reconnect must happen, and the aligned times must stay in order.
- On the board, RECORD over Wi-Fi into `record.py` for 2 minutes:
  - 200.00 Hz, `skipped=0`, `link_dropped=0`.
  - Device-clock steps of 5 ms with no gaps, the same samples the USB copy received at the same time.
  - Switch Wi-Fi off and on once: the recorder reconnects and the gap is visible and counted.

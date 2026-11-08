# Report: MyoWare record sketch uploaded; Wi-Fi link checked on the real board

**Date:** 2026-11-07 16:01 · **Result:** ✅ done (not yet worn) · **Plan:** [plans/2026-11-07-semg-support.md](../plans/2026-11-07-semg-support.md)

## Goal
The user: "Yes, copy it" (the IMU's Wi-Fi file for the MyoWare sketch), then "Plugged in: upload it" (board on USB,
nobody wearing it). Put `firmware/myoware_record` (Wi-Fi link) on the MyoWare and check it end to end.

## What changed
- **`firmware/myoware_record/wifi_secrets.h`:** copied from the IMU's sketch folder without opening it.
  - `cmp`: byte-identical to the IMU's file.
  - Git ignores it (`.gitignore:12`).
  - It has the two Wi-Fi `#define` lines (checked by counting them, never printing them).
- **The MyoWare board** (ESP32-D0WD-V3 rev 3.1, MAC `68:fe:71:fb:78:68`; USB chip CH340 `1a86:7523` at
  `/dev/cu.usbserial-210`): the old demo sketch was replaced by the Wi-Fi record sketch. All 4 flash parts were
  written with "Hash of data verified".
- The build folders were deleted afterwards, because the compiled file holds the Wi-Fi password.
- No repository code changed.

## Verified by
- **Before writing:** the board printed the old demo's lines ("ENV:…,Smooth:…"), and the chip answered esptool's
  read-only `chip-id`.
  - At first it was silent: the shield's power switch was off. The switch cuts the ESP32 even with USB in; the USB
    chip still shows up because it runs on cable power.
- **Wi-Fi link** (10 s, with the USB copy read at the same time):
  - `truerehab-myoware.local` resolved in 5 ms to 192.168.1.89, on the same network as this Mac.
  - 9,461 samples at 1000.1/s, 0 gaps, 0 repeats; the header came first.
  - The board's own status: `wifi=streaming`, RSSI −43 to −48 dBm, `link_dropped=0`, `link_send_fails=0`.
- **Through the Pi bridge** (installed v0.2 on the SSD, the `emg` provider only),
  `check_bridge.py --commands` for 20 s:
  - PASS, 14 passed, 0 failed;
  - envelope: 1083 values; no gaps in 1103 messages; Start/marker/Stop all work;
  - the recording's `emg.csv` starts with the board's header;
  - the 1 warning: no median frequency in 20 s. That's expected: it's sent only during movement, and nobody was
    wearing the sensor.

## Issues / not done
- **The USB copy can't be read on this Mac.** macOS's built-in CH340 driver doesn't set 921,600 baud correctly:
  - the data arrives garbled at every setting;
  - the first upload failed the moment esptool switched to 921,600, and it worked at 115,200
    (`--board-options UploadSpeed=115200`).

  This doesn't matter for recordings (they use Wi-Fi). On the Mac use `tcp://truerehab-myoware.local:3334`, never the
  USB port. A Pi (Linux driver) has not been tried.
- **Off the body the signal is meaningless:** raw swings 0–4095 and the envelope sits at ~3890 of 4095. With no
  electrodes on skin, the sensor's inputs float. This needs checking on the arm: the envelope should drop low at rest.
- **26 sample slots skipped at start-up** (counter `skipped`, unchanged afterwards); none during the 10-s check.
- **Not yet done:** worn on battery, a longer run (the IMU showed ~1-s Wi-Fi pauses now and then), recording with
  the radar.

## Next
1. **Wear it on battery** (switch ON, USB unplugged, fresh pads on the biceps). Record a few curls with the radar:
   the Pi set's Start/Stop, or `recorder/record.py --emg tcp://truerehab-myoware.local:3334`.
2. Then run `model/check_session.py` on it, and `python -m trnet.calibrate` (replaces the textbook sEMG numbers).
   Check the live thresholds (activity gate 9×, rep rule 15× noise) on the real signal.

**Uncommitted work:** yes, this report and the CONTEXT/plan updates (the user commits on request).

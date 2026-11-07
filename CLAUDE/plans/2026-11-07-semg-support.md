# Plan: sEMG (MyoWare) support across the kit, while the IMU is unreliable

**Status:** done (2026-11-07): all 5 parts built, tested and pushed; see [report](../output/2026-11-07-1535-semg-support.md). Still needs the user: the MyoWare upload and a worn test.
**Date:** 2026-11-07

## Why
The user (2026-11-07): "can we make it support sEMG? IMU have some problem right now".

Today:
- **IMU:** loses half its data on the moving arm (I²C wiring).
- **Pi set v0.1:** handles the radar only.
- **MyoWare record sketch** (1 kHz `E,<micros>,<raw>,<env>`):
  - has never run;
  - sends over Bluetooth Classic, which didn't connect to the Mac (Nov 4) and would need extra Linux setup on a Pi.
- **Model:** finds reps only from the IMU or camera, so a radar + sEMG recording can't train anything, not even
  fatigue, which comes from sEMG.

## Approach: 5 parts, each tested and pushed on its own
1. **MyoWare firmware** (`firmware/myoware_record`):
   - **Wi-Fi link**, the same design as the IMU's fw 2.1 (verified Nov 5).
     - It joins your Wi-Fi as `truerehab-myoware.local` and serves one TCP client on port 3334.
     - Every line still goes to USB as well. Sampling stays on core 1 and never waits for the network; a core-0 task
       sends from a buffer.
     - Status lines report the rate, dropped lines and the link.
   - **Pins:** RAW and ENV are on ADC1, which keeps working while Wi-Fi is on.
   - **Bluetooth** stays available with `WIFI_LINK 0`.
   - **Compile:** both variants.
   - **Upload:** needs your "upload it", the board on USB with **nobody wearing it**, and `wifi_secrets.h` next to the
     sketch. I can copy your existing IMU one without opening it, if you say so.
2. **Pi bridge: an sEMG source and shared recording.**
   - **New `emg` provider:** reads `E,` lines from `tcp://truerehab-myoware.local:3334` (or a serial port).
     - **Live in the dashboard:** the sEMG envelope (50/s) and the **median frequency** (4/s, 0.5-s windows,
       20–450 Hz, mains removed: the classic fatigue sign).
     - **Health in plain words:** not reachable, flat signal (electrodes?), clipping, gaps.
   - **Recording:** one session folder per Start/Stop for every sensor. The radar's `radar.bin` and the MyoWare's
     `emg.csv` share the same clock, in the recorder's format. `record_dir` moves to `[bridge]`; the radar's old
     option is still read.
   - **Tests:** a fake MyoWare on localhost (like the recorder's fake Wi-Fi IMU), plus a recording with the radar
     replay and the fake sEMG together.
3. **Model: reps from sEMG when there's no IMU or camera.**
   - Each curl is a burst of biceps activity in the envelope; reps are cut from those bursts.
   - **Fatigue labels** (median-frequency drop) work. Quality and compensation stay masked, because they need joint
     angles.
   - `check_session.py` says "reps from the sEMG envelope (fallback)" and "can train: fatigue ✓".
   - **Tests:** fake sessions with radar + sEMG only.
4. **Dashboard:** the new channel names in English, Thai and Traditional Chinese; they show in the existing
   "Reference signals" panel.
5. **Pi set v0.2:**
   - **Files:** config (the `emg` source, off until the MyoWare runs the Wi-Fi sketch), self-test (is the MyoWare
     reachable?), README.
   - **Rebuild:** copy to the SSD and update the install there.
   - **Verify end to end without hardware:** replayed radar + fake MyoWare → `check_bridge` (the sEMG streams
     arrive) → dashboard → Start/Stop recording → `check_session` says fatigue ✓.

## When I need you
- **MyoWare on USB** (nobody wearing it) to upload, plus your OK to copy the Wi-Fi file.
- **Then wear it on battery** for a real check: a few curls with the radar, recorded by the Pi set on the SSD.

## Risks / limits
- **Bandwidth:** 1 kHz over Wi-Fi is ~24 KB/s; the IMU's 8 KB/s ran without loss.
- **Network:** 2.4 GHz only, and school Wi-Fi may block devices from talking to each other, so use your phone
  hotspot there.
- **sEMG reps are a fallback.** Curls with no pause between them may merge into one burst, so the IMU or camera stay
  better for rep timing.
- **The live median frequency is a measured signal,** not a model score. It needs good electrode contact.
- **Safety:** only on battery when worn, never with USB plugged in (SparkFun).
- Teammates' code is untouched.

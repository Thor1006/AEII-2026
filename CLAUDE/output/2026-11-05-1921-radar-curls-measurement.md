# Report: first radar recording with a person, current settings (P0) — speed limit, IMU, left/right

<!-- Filename: YYYY-MM-DD-HHMM-<slug>.md -->

**Date:** 2026-11-05 19:21 · **Result:** ⚠️ partial: speed limit answered, left/right not · **Plan:** [plans/2026-11-05-radar-tuning-and-dashboard.md](../plans/2026-11-05-radar-tuning-and-dashboard.md)

## Goal
Measure whether the radar's current settings (`fullmap_awr2x44p.cfg`, ±1.09 m/s, 0.137 m/s per Doppler bin) can
follow real elbow curls without the speed wrapping around. Also find which way its angle axis runs. The user
chose "Only measure current", and wore only the IMU (no sEMG).

## What was done
- **Two guided recordings with spoken cues** (macOS `say`; the cue times were logged on the recorder's clock):
  - `2026-11-05_191441_TEST_radar_curls` (75 s): still → 3 shrugs → 3 slow → 3 normal → 3 + 3 fast curls.
  - `2026-11-05_191602_TEST_radar_leftright` (49 s): centre → 1 m to own left → centre → 1 m to own right → centre.
- **`check_session.py`** on both, then a read-only analysis of Doppler at the arm against the IMU's arm speed,
  range over time, and left/right in still pictures and detected points.
- **Check fix (`model/trnet/check.py`):** the IMU sketch's wide range sends counts up to ±65534. The old "int16
  limit" message flagged 104 normal samples; it now counts samples at the real ±4 g / ±500 °/s limit (18, the same
  as the board's own counter). The check tests still pass.

## Results
- **Radar:**
  - 4,367 + 2,790 frames at 60.00 fps, 0 missing;
  - 48–51 °C;
  - delivery after the fitted clock: median 1.7 ms, p99 3.3 ms.
- **Where you were:** about 1 m from the radar for the first 54 s. Every curl shows as a V at 0.8–1.2 m (the hand
  swinging toward the radar and back); see the [range-time figure](2026-11-05-radar-range-time.png). At ~55 s you
  walked up to ~0.5 m, so the second fast set was very close to the radar.
- **Speed limit (first 54 s, Doppler at 0.59–1.31 m):** 95 % of the arm's moving echo stayed within
  0.55–0.68 m/s in every segment, fast curls included. At most 0.2 % reached the ±1.09 m/s edges, and no
  wrap-around pattern is visible ([figure](2026-11-05-radar-curls.png)). The cleaned IMU puts the hand's total
  speed above 1.09 m/s in 16 % of the fast segment. The speed toward the radar is lower, because at mid-curl the
  hand moves mostly up and down. **For this person at ~1 m, the current settings were fast enough.**
- **IMU on the arm, unreliable:**
  - board counters: `i2c_err` 179–206, `recoveries` 51–60, `skipped` 49–58;
  - the I²C bus dropped to 100 kHz and its gyro calibration failed;
  - it lost 36 of 72 s (23 gaps) and 14 of 46 s;
  - 18 samples at ±500 °/s;
  - spikes next to the gaps.

  On the desk earlier today the same board was clean, so the wiring fails when the arm moves (same as Nov 4).
- **Left/right: not determined.** Neither the still pictures nor the detected points show you as a clear spot.
  "Right" only adds a band at 0.4 m across every angle, and the points sit at 0.4–0.5 m whatever the position
  ([figure](2026-11-05-radar-left-right.png)).
- **Shrug sync:** couldn't be measured. There was no `s` marker (keys can't be pressed from my shell), the IMU had
  gaps, and the left/right run has no shrugs.
- **Session check:** the curls run is usable for "quality" (reps from the IMU, unreliable with these gaps); the
  left/right run is not usable for training (it has no reps).

## Issues / not done
- The IMU wiring needs fixing (soldered joints or a connector with strain relief) before it can serve as ground
  truth on a moving arm.
- One person, one distance (~1 m) and one radar height. Faster curls or other geometries could still go past
  ±1.09 m/s.
- Left/right direction still open.
- The automatic "arm seen" figure (frames above the Nov-4 empty-room level) is 31–34 % for the curl segments.
  That threshold comes from a different setup, so it doesn't reflect how clearly the arm shows in the range-time
  picture.
- The figures and analysis scripts were made ad hoc (scratchpad) and are not part of `model/`.

## Next
1. Fix the IMU wiring (solder or a locking connector; tape the cable to the arm), then redo the curls run with the
   IMU to confirm its speeds.
2. Left/right with a still, strong target: hold a flat metal object (a baking tray or a laptop lid) at radar
   height ~1 m in front, then 0.5 m to the left, then to the right, 10 s each.
3. Then the first full session with sEMG: upload `myoware_record` with the user's "upload it", and fix Bluetooth
   pairing.

**Uncommitted work:** yes.

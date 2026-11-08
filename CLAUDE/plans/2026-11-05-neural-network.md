# Plan: radar-only neural network + data pipeline, built and tested untrained (no sensors)

**Status:** done — built and verified 2026-11-05 ([report](../output/2026-11-05-1316-neural-network-pipeline.md)); untrained by design, no real sessions with a person yet. Approved by the user ("Approve and build"). Changes made during the build are listed in the report. Updated before approval:
- user asked to add (1) fake data tuned from the real recordings and (2) a one-command session check;
- the radar heatmap input was corrected after checking the real recordings (see "Radar facts").
**Date:** 2026-11-05

## Why
The user asked whether the models can be built now, without sensors attached, and wants to work on them at school
with this Mac. The recorder exists, but nothing yet turns a session into training data. No network exists past
`sandbox/Encoder_0.1` (one frame encoder, synthetic input only).
Design reviewed with the user on 2026-11-05 as an 18-step detailed view (pipeline 1–7, network 8–18). This plan
supersedes that view where they differ (Stem A input).

## Radar facts (measured 2026-11-05 from the 3 recorder radar sessions, radar-lab profile `fullmap_awr2x44p.cfg`)
- **Frame rate:**
  - 60.00 fps (mean interval 16.667 ms over 15.3 s).
  - 0 missing frame numbers in 1,792 frames.
  - Arrival at the Mac comes in bunches: median 15.9 ms apart, p99 19.4 ms, max 40.6 ms.
- **Static heatmap (TLV 4):**
  - 64 range bins × **8 azimuth virtual antennas**, complex int16. These are antennas, not angle bins.
  - The antennas sit at columns `[0,2,7,9,3,5,10,12]` of a 13-wide row (radar-lab `cfg.load` → `az_cols`).
  - Angles need a host angle FFT, as radar-lab's `maps.range_azimuth` does. The values are complex, so phase is
    available at 60 fps.
- **Range-Doppler (TLV 5):** 64 range × 16 Doppler, uint16.
- **Resolution:** range 5.94 cm per bin, so 64 bins = 3.80 m; Doppler 0.137 m/s per bin.
- **Also sent:** points (TLV 1/7), stats (TLV 6), temperature (TLV 9).
- **Recordings:** 2 of the 3 are noted "nobody in front", so they are empty-room backgrounds.
- **Correction to the reviewed design:**
  - The earlier "64 range × 8 angle" was wrong. The magnitude of the raw 8 antennas holds almost no angle
    information.
  - Stem A now takes the angle FFT instead: 16 angle bins (about the real ~9° resolution of a 13-wide aperture).
  - It gets 2 channels: magnitude in dB, and the frame-to-frame phase change.

## Scope
- **In:**
  - all code from a recorder session folder to scores and a recommendation;
  - fake data tuned from the real recordings;
  - a one-command session check for every new recording;
  - all of it tested without hardware.
- **Out:**
  - training on real data (none recorded yet);
  - choosing clinical thresholds;
  - freezing the real `InputContract`;
  - ONNX/Pi export;
  - dashboard wiring;
  - any firmware.

## Approach
New top-level folder `model/`, set up like `recorder/`: a package `trnet/`, plus tests, a README and a `.gitignore`.

1. **Draft input contract** (`trnet/contract.py`).
   - Shapes:
     - H `[T,2,64,16]`: angle-FFT magnitude in dB, plus the phase change since the previous frame (set to 0 where the
       magnitude is near the noise floor);
     - D `[T,1,64,16]`;
     - mask `[T]`;
     - T = 128 frames at 60 fps.
   - Clearly marked `v0-draft`. It is saved with the weights, and loading refuses a mismatch.
   - It records the radar cfg lines it was built from.
2. **Network** (`trnet/network.py`), about 239k parameters, as reviewed:
   - Stem A for the heatmap (2 input channels, pool 2×2) and Stem B for range-Doppler (pool 2×2). Both give
     `[16,32,8]`.
   - Shared CNN trunk giving 128 numbers per frame (Encoder_0.1's blocks, written fresh; the sandbox is unchanged).
   - Within-rep dilated Conv1d with masked attention pooling, plus rep duration, giving a 64-number rep vector.
   - Personal baseline: `[v, v − mean(reps 1–3)]`.
   - Causal GRU over the reps.
   - Heads: fatigue 1, quality 1, compensation 3, next-rep risk 1.
   - Training-only extra head: ROM, shoulder rise, trunk lean and MDF ratio.
   - The phase channel can be switched off, so real data can show whether it helps.
3. **Fake data, tuned from real recordings** (`trnet/calibrate.py`, `trnet/synth.py`).
   - **`calibrate.py`** reads the recordings on this Mac once and saves the numbers to `model/calib/real_stats.json`.
     The file is small, contains no personal data, and is committed, so the generator also works on a teammate's
     computer.
     - **Radar**, from the 3 radar recordings (1,792 frames):
       - noise floor and static clutter per range bin and angle;
       - phase noise from frame to frame;
       - Doppler noise;
       - frame timing: 60.00 fps, bunched arrival, missing-frame rate.
     - **IMU**, from the 6 IMU recordings:
       - noise and bias per axis, measured in still stretches that are found automatically;
       - Wi-Fi delivery delays and pauses, from the 2-minute run that has the USB and Wi-Fi copies side by side
         (median 15 ms, about 1-s pauses).
   - **`synth.py`** builds fake sessions in the exact recorder format: `meta.json`, `radar.bin` +
     `radar_index.csv` (via radar-lab's `encode_frame`), `emg.csv` (`E,` lines), `imu.csv` (`I,` lines),
     `pose.csv` and `markers.csv`. They go through the same code as real sessions.
     - **Radar background:** real empty-room frames when the recordings are present (the most realistic), otherwise
       the saved numbers.
     - **Simulated person doing elbow flexion:** point reflectors placed with the real antenna columns, range bins
       and Doppler bins. It follows the idea of radar-lab's `sim.py`, but uses the real profile's numbers; that sim
       uses 128 bins at 10 fps, which doesn't match the recordings.
     - **Fatigue:** reps get slower and smaller, and the fake sEMG's MDF drops.
     - **Compensation:** shoulder and trunk reflectors move, and the pose angles change.
     - **Problems on purpose:** frame gaps, Wi-Fi pauses and missing sensors, the same kinds the real setup has
       shown.
   - **Not tuned yet:** there are no real sEMG or pose recordings, so those use textbook values, marked
     `uncalibrated` in the stats file. Rerun `calibrate.py` after the first real sessions to update everything.
   - **Plumbing only:** results on fake data say nothing about real radar.
4. **Radar preprocessing** (`trnet/radar.py`).
   - Read `radar.bin` + `radar_index.csv` with radar-lab's frame reader, through `recorder/rec/radar_lab.py`.
   - **Static heatmap:** place the 8 antennas at their real columns, do the angle FFT to 16 bins (same method as
     `maps.range_azimuth`), then compute the magnitude dB and the phase change.
   - **Range-Doppler:** to dB.
   - **Scaling:** -40 dB floor, scaled to 0–1, normalised per session from the first 5 s.
   - **Gap frames:** zeros with mask 0. The phase change is not computed across a gap.
5. **Ground-truth signals** (`trnet/truth.py`).
   - **sEMG:** 20–450 Hz band-pass and 50 Hz notch with numpy FFT (no scipy needed), then MDF in 0.5-s windows.
   - **IMU:** forearm angle through a complementary filter.
   - **Pose:** reuse `angles()` from `recorder/rec/pose.py`, with 5-frame median smoothing.
   - Uses the existing `align_device_time` and session reader.
6. **Shrug offset** (`trnet/sync.py`).
   - Measure each sensor's leftover offset from the 3 shrugs: radar Doppler energy, IMU gyro, pose ear–shoulder gap
     and sEMG envelope.
   - Report it, apply it, and warn if it is over 17 ms.
7. **Reps and labels** (`trnet/reps.py`, `trnet/labels.py`).
   - Cut reps from elbow angle peaks: at least 30° and 0.8 s. Cross-check against space markers.
   - Pad or crop each rep to 128 frames with a mask.
   - Labels as reviewed. All thresholds live in one `PLACEHOLDER_THRESHOLDS` dict.
   - A missing sensor means its label is masked.
8. **Session check** (`model/check_session.py`): one command to run straight after each recording.
   - Usage: `python check_session.py <session folder>` (or `--all`). It prints a short report and saves it to
     `model/runs/checks/`. It never changes the session folder. The exit code is non-zero when the session can't
     be used.
   - **Files and format:** each sensor file is present and has the right line type. sEMG must be `E,<micros>,<raw>,<env>`.
     Example: the two Wi-Fi test sessions have IMU `I,` lines in their `emg.csv`, and the check must flag that.
   - **Rates and gaps:**
     - radar 60 fps and missing frame numbers;
     - IMU 200 Hz and device-clock steps of 5 ms;
     - sEMG 1 kHz;
     - pose fps, and how many frames have shoulders, elbows and hips visible;
     - Wi-Fi link drops;
     - the board's own `skipped`, `i2c_err` and `saturated` counts from its status lines.
   - **Signal sanity:**
     - IMU values stuck at the int16 limits;
     - sEMG flat or clipped;
     - radar temperature (TLV 9), with a warning at 85 °C;
     - radar sees movement in front.
   - **Timing:** clock-fit spread per sensor, the 3 shrugs found in each sensor, offsets between sensors (warning
     over 17 ms).
   - **Reps:** count found vs space markers; reps longer than 2.1 s get cropped.
   - **What it can train:** fatigue needs sEMG RAW, compensation needs pose, quality needs pose or IMU. Example line:
     `quality ✓ compensation ✓ fatigue ✗ (no sEMG)`.
   - **Privacy and safety:**
     - the subject must be a code (`S01`…, or `TEST`), never a name;
     - raw video is off unless meant;
     - warn if the MyoWare was recorded over a USB port with a non-TEST subject. SparkFun says the shield must
       not be on a person while USB is plugged in.
9. **Dataset and training** (`trnet/dataset.py`, `train.py`).
   - Session folders → per-set samples, cached as `.npz`.
   - Only sessions that pass the check are used.
   - Leave one subject out, with a validation person taken from the training group.
   - Augmentation: range shift, gain, frame hiding.
   - Masked Huber/BCE loss, AdamW, early stopping.
   - Runs on the Mac CPU or Apple GPU (MPS is available).
   - Writes a short report with per-person scores and the majority-class baseline.
10. **Recommendation rules** (`trnet/recommend.py`): the 5 reviewed rules, with placeholder numbers in one place.
11. **README:** calibrate, generate fake data, check a session, run the tests, train on fake or real sessions.
    Everything runs without sensors.

## Files touched
- `model/` (new):
  - `trnet/`: contract, network, calibrate, synth, radar, truth, sync, reps, labels, dataset, recommend;
  - `check_session.py`, `train.py`;
  - `calib/real_stats.json`;
  - `tests/`, `README.md`;
  - `.gitignore` (`.venv/`, `data/`, `runs/`).
- Read-only reuse, not edited: `recorder/rec/session.py`, `recorder/rec/pose.py`, `recorder/rec/radar_lab.py`, and
  radar-lab's `tlv.py`, `cfg.py`, `maps.py` and `sim.py` ideas. If a small change is needed there, I'll ask first.
- Read-only data: the 9 recorder sessions in `recorder/data/sessions/` (git-ignored; never modified).
- `CLAUDE/` plan, report and CONTEXT at wrap-up.

## Risks / needs OK
- **No new installs needed:**
  - PyTorch 2.14.1 and numpy 2.5.3 are already in the system Python (also in the recorder and radar-lab venvs).
  - `model/.venv` would be created with `--system-site-packages` so it reuses them, with no download.
  - scipy and onnx are not installed. scipy is avoided; onnx is out of scope.
- **Fake data can mislead:** a model that scores well on it proves only that the code runs. The README and every
  report will say so.
- **One room only:** the radar background is your home room. School and other rooms will look different until we
  record a few seconds of empty room there.
- **Not final:** shapes are a `v0-draft` and thresholds are placeholders. They change once real data and a
  physio's input exist.
- **Antenna order still not checked:** left/right and antenna ordering are unverified on the real board. A wrong but
  consistent order still trains. But pictures and any left/right reading wait for the known-target test already
  in CONTEXT.
- **Fatigue from radar is still unproven:** the phase channel gives it a chance, but real data decides.
- Teammates' `Phisit/`, `frontend/` and `pi-bridge/` are untouched.

## How we'll verify
- **Unit tests (`model/tests/`):**
  - shapes at every layer;
  - parameter count about 239k;
  - causality: changing rep r+1 never changes outputs for reps ≤ r;
  - masking: padded frames don't change the output;
  - baseline subtraction;
  - save/load refuses a mismatched contract;
  - angle FFT matches radar-lab's `maps.range_azimuth` on the same frame;
  - phase change is 0 across a gap;
  - MDF on a known signal, and a 20% MDF drop gives fatigue 1.0;
  - rep cutting on a known angle curve;
  - a missing sensor masks its labels;
  - the leave-one-subject-out split never leaks a person into training;
  - the rules give the expected recommendation on hand-made scores.
- **Fake data vs real:**
  - empty-room fake radar noise floor within 1 dB of the real one per range bin;
  - frame timing reproduces 60.00 fps and the bunching;
  - IMU still-noise within 20% of the real one per axis;
  - fake Wi-Fi delay median within 5 ms of the real 15 ms.
- **Session check on the 9 existing sessions, with these expected results:**
  - 3 radar sessions: 60 fps, 0 missing, nobody in front → "no ground truth, can't train";
  - 4 USB IMU sessions: 200 Hz, board counts 0;
  - 2 Wi-Fi sessions: `emg.csv` flagged as IMU lines, and `wifi_check` shows `link_drops=1`.
- **Session check on broken fake sessions:** each warning must fire. Cases: a missing shrug, a radar gap, IMU
  saturation, sEMG over USB with a non-TEST subject, a name instead of a code, raw video on, and a rep longer
  than 2.1 s.
- **End to end:**
  - fake sessions go through check → preprocess → reps → labels → dataset → a short training run;
  - loss drops, and the model can overfit a tiny batch;
  - on fake data it beats the majority baseline (plumbing check only).
- **Real-file check:** the existing radar session `2026-11-04_183625_TEST_radar_check` is parsed into H, D and
  mask without errors.
- **Runtime:** forward-pass time per frame and per rep on the Mac. This is a reference, not a Pi measurement.
